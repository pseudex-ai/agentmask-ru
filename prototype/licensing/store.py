"""Licensing state: who has a key, what leases were issued, what was used.

Deliberately the same SQLite setup the sidecar uses (`pseudex/sqlite_setup.py`,
WAL + busy_timeout armed before journal_mode) — the licensing server is a small
service and a second storage stack would be a second thing to operate.

The key is stored HASHED. It is a bearer credential: anyone holding it can lease
the product, so a dump of this table must not be enough to serve customers. SHA-256
without a salt is correct here and a per-row salt would be worse — the key is 32
bytes of `secrets.token_urlsafe` entropy, so there is no dictionary to attack, and
an unsalted digest is what lets a lookup be a single indexed point query.
"""

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass

from pseudex.sqlite_setup import LICENSING_STORE, connect as sqlite_connect

from .registry import LEGACY_VERSION

KEY_PREFIX = "ps_live_"

_log = logging.getLogger("licensing.store")

# КОД ОТКАЗА В НОВОЙ ЁМКОСТИ, И ЕГО ФОРМА — ЭТО ТРЕБОВАНИЕ К ВЫПУЩЕННОМУ ФЛОТУ,
# А НЕ НАЗВАНИЕ.
#
# `_ANSWER_CODES` каждого выпущенного движка — `{instance_limit,
# release_budget}`; код ОТТУДА читается как окончательный ответ, ставит
# `_terminal_code` и зовёт `_expire()` — бандл выгружается немедленно, `/mask`
# отдаёт 503 в ту же секунду, а уже оплаченный остаток сгорает (Б30). Комментарий
# сервера при этом обещал, что «процесс доживает на уже купленном кванте»: флот
# этого обещания не выполнял.
#
# `fenced` вне `_ANSWER_CODES`, а 409 входит в `_GRACE_WORTHY_STATUS`, поэтому
# ВЕСЬ выпущенный флот читает этот ответ как временный сбой: `_TransientLeaseError`
# → WARN → обслуживание до `_consumed >= _granted` → 503 `capacity_exhausted`.
# Ровно то, что требуется: отказ в НОВОЙ ёмкости не гасит поколение, гасит его
# обычная проверка `has_capacity()`.
#
# Новый код вне 409 брать нельзя: неизвестный статус вне `_GRACE_WORTHY_STATUS`
# выпущенный движок трактует как `LicenseError` — то есть K8s-раскатка убивала бы
# старый под до его `terminationGracePeriodSeconds`.
FENCED = "fenced"

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
STATUS_SUSPENDED = "suspended"
STATUS_UNPAID = "unpaid"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def ago(seconds: float) -> str:
    """Возраст словами: «41 с», «12 мин», «3 ч». Секунды в отказе, который
    читает человек, — шум ровно там, где речь идёт о часах."""
    seconds = max(0.0, seconds)
    if seconds < 90:
        return f"{int(seconds)} с"
    if seconds < 5400:
        return f"{int(seconds // 60)} мин"
    return f"{int(seconds // 3600)} ч"


def version_tuple(version: str) -> tuple[int, ...]:
    """Сравнивать версии ЧИСЛАМИ И В PYTHON, никогда строками и никогда в SQL.

    `SELECT '0.3.9' >= '0.3.14'` возвращает 1, и на этом уже обожглась
    прежняя `active_instances`: «0.3.9» > «0.3.10» как строки держали
    обновившийся инстанс на старой версии целое окно. Правило занятости версий
    больше не читает вовсе, но гистограмма флота читает — поэтому сравнение
    по-прежнему живёт здесь, а не в запросе."""
    parts = []
    for chunk in version.split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class SlotRefused(RuntimeError):
    """Правило допуска отказало заявке на слот.

    Сегодня не поднимается ни на одном пути: вариант А (§6.1) всегда выдаёт
    слот. Существует потому, что вариант В подключается ЗАМЕНОЙ
    `admit_generation`, и форма, которой ответ доедет до ручки, не должна
    изобретаться в тот момент.
    """


@dataclass(frozen=True)
class KeyRecord:
    org_id: str
    status: str
    plan: str


class LicenseStore:
    """Connector to the licensing database (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        # RLock, НЕ Lock, И ЭТО НЕ ВКУСОВЩИНА. `_accumulate_values` читает и
        # пишет, будучи вызванным ИЗ-ПОД уже взятого лока в `record_usage`;
        # обычный `Lock` встанет там намертво и остановит учёт целиком.
        self._lock = threading.RLock()
        # Потолок частоты `/v1/meter` — два ведра по секунде (см.
        # `metered_too_recently`). Не состояние счёта: наша полоса.
        self._meter_bucket: int = -1
        self._meter_seen: dict[tuple[str, str], float] = {}
        self._meter_seen_prev: dict[tuple[str, str], float] = {}
        self._conn = sqlite_connect(db_path, LICENSING_STORE)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS keys ("
            "key_hash TEXT PRIMARY KEY, org_id TEXT, plan TEXT, status TEXT, created_at REAL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS grants ("
            "org_id TEXT, pubkey TEXT, granted INTEGER DEFAULT 0, issued_at REAL, "
            "PRIMARY KEY (org_id, pubkey))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS process_reports ("
            "org_id TEXT, pubkey TEXT, secret TEXT DEFAULT '', "
            "seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', signature TEXT DEFAULT '', "
            "chain_breaks INTEGER DEFAULT 0, updated_at REAL, "
            "build TEXT DEFAULT '', build_changes INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, pubkey))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS leases ("
            "lease_id TEXT PRIMARY KEY, org_id TEXT, instance_id TEXT, process_id TEXT, "
            # КЛЮЧ ПРОЦЕССА — ЕДИНСТВЕННЫЙ ИДЕНТИФИКАТОР, КОТОРЫЙ КЛИЕНТ НЕ
            # ВЫБИРАЕТ. Он генерируется в памяти воркера, на него запечатывается
            # бандл, и два процесса не могут иметь один и тот же, не будучи
            # пропатченными. Всё остальное, чем контейнер представляется, —
            # переменные окружения.
            "pubkey TEXT, "
            # ОСВОБОЖДЁННЫЙ СЛОТ ОСТЫВАЕТ, А НЕ ИСЧЕЗАЕТ. Строка удалялась, и
            # это обнуляло единственную границу, которую мы принуждаем:
            # контейнер отдавал слот сам, поднимался следующий, и на тарифе в
            # один инстанс их поднималось пять подряд.
            "released_at REAL, released_by TEXT, "
            "issued_at REAL, ttl_seconds INTEGER)"
        )
        # Keyed by (org, instance) and holding the LATEST CUMULATIVE totals — not
        # one row per report.
        #
        # The client reports `audit.billing_totals()`, which is everything that
        # instance has ever protected, on every renewal. Summing those rows would
        # bill a customer once per renewal for the same traffic: at a 24 h lease
        # that is a month's usage counted thirty times over.
        #
        # Cumulative-and-overwrite also survives a lost report, which a delta
        # scheme does not: a delta that never arrives is gone, while a missed
        # cumulative report is corrected by the next one.
        #
        # Per INSTANCE, because every worker process of one container shares one
        # audit database and therefore reports the same instance-wide number —
        # summing workers would multiply the bill by the worker count.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "org_id TEXT, instance_id TEXT, updated_at REAL, reports INTEGER, "
            "requests INTEGER, entities TEXT, "
            # The billed quantity, accumulated MONOTONICALLY on our side.
            # `values_reported` is the last number the installation sent;
            # `values_total` never decreases.
            "values_reported INTEGER DEFAULT 0, values_total INTEGER DEFAULT 0, "
            "resets INTEGER DEFAULT 0, "
            # Доказательная часть ПРОТИВ КАНАЛА: последний номер в цепи, хеш
            # предыдущей подписи, сама подпись и вердикт о ней. Против самого
            # клиента она ничего не доказывает — см. `bundle.py::mac_report`. `chain_breaks` считает
            # разрывы — пропуск, перестановку или подмену старым отчётом.
            "seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', signature TEXT DEFAULT '', "
            "trust TEXT DEFAULT 'unsigned', chain_breaks INTEGER DEFAULT 0, "
            "unverified_reports INTEGER DEFAULT 0, "
            "unverified_requests INTEGER DEFAULT 0, "
            # «Не смогли разобрать» — это НЕ «расхода не было». Без отдельной
            # колонки испорченный отчёт был неотличим от молчания.
            "malformed_reports INTEGER DEFAULT 0, "
            # Продление ПРИШЛО, а отчёта в нём НЕ БЫЛО. Раньше это была полная
            # тишина: перехватчик, выбрасывающий поле `usage`, не двигал ни
            # одного счётчика — подделать отчёт было видно, повторить видно, а
            # снять целиком не видно ничем.
            "reports_missing INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, instance_id))"
        )
        # МИГРАЦИЯ КОЛОНОК ИДЁТ ДО ЛЮБОГО ИНДЕКСА, И ЭТО НЕ СТИЛЬ.
        #
        # Она стояла ПОСЛЕ, а `leases_org_pubkey` строится по `pubkey` — то
        # есть на томе, пережившем релиз без этой колонки, процесс умирал на
        # старте с `no such column: pubkey` и до миграции не доходил никогда.
        # Апгрейд лицензионного сервера на существующих данных не поднимался
        # вовсе, а это единственный сервер, и его простой останавливает КАЖДОГО
        # клиента, у которого кончилась аренда.
        #
        # Порядок теперь такой, каким он обязан быть у любой схемы: таблицы,
        # потом колонки, потом всё, что на колонки ссылается.
        # Существующие тома пережили релизы без этой колонки.
        columns = {row[1] for row in
                   self._conn.execute("PRAGMA table_info(leases)")}
        if "pubkey" not in columns:
            self._conn.execute("ALTER TABLE leases ADD COLUMN pubkey TEXT")
        # `engine_version` — какой движок арендовал (D-056): без неё пол
        # минимальной версии двигался бы вслепую, а «кто ещё на 0.3»
        # отвечалось бы только по логам. Старые ряды остаются пустой строкой.
        # `process_id` и `ttl_seconds` — колонки, которых не было в самой первой
        # схеме (`expires_at` вместо TTL). Проверка колонок их не искала, а
        # запись аренды на таком томе падала «no column named process_id» —
        # нашлось, когда test_store_upgrade впервые ЗАПИСАЛ аренду, а не только
        # посмотрел на PRAGMA table_info.
        for column, ddl in (("process_id", "process_id TEXT DEFAULT ''"),
                            ("ttl_seconds", "ttl_seconds INTEGER DEFAULT 0"),
                            ("released_at", "released_at REAL"),
                            ("released_by", "released_by TEXT"),
                            ("engine_version", "engine_version TEXT DEFAULT ''"),
                            # `lease_contract` — какой формы ответ клиент ЗАЯВИЛ,
                            # что прочтёт (D-063). NULL — не заявил: движок до
                            # 0.3.16 шлёт только `engine_version`. По этой
                            # колонке видно, когда мост контракта 2 можно снять.
                            ("lease_contract", "lease_contract INTEGER"),
                            # ПРИВЯЗКА КЛЮЧА ПРОЦЕССА К (СЛОТ, ЭПОХ) — ПО НЕЙ И
                            # ТОЛЬКО ПО НЕЙ `/v1/meter` решает, фенсить ли.
                            # Живёт на строке АРЕНДЫ, а не отдельной таблицей:
                            # ключ процесса связывается с поколением ровно один
                            # раз и ровно здесь, а вторая таблица с тем же
                            # ключом была бы вторым мнением о той же привязке —
                            # ошибка, которой этот файл уже платил дважды.
                            # NULL у ряда, записанного до миграции: такой ключ
                            # не с чем сравнивать, поэтому он не фенсится
                            # вовсе и уходит вместе со своим окном (§7.1).
                            ("start_id", "start_id TEXT DEFAULT ''"),
                            ("slot_no", "slot_no INTEGER"),
                            ("epoch", "epoch INTEGER")):
            if column not in columns:
                self._conn.execute(f"ALTER TABLE leases ADD COLUMN {ddl}")
        usage_columns = {row[1] for row in
                         self._conn.execute("PRAGMA table_info(usage)")}
        for column, ddl in (("seq", "seq INTEGER DEFAULT 0"),
                            ("prev", "prev TEXT DEFAULT ''"),
                            ("signature", "signature TEXT DEFAULT ''"),
                            ("trust", "trust TEXT DEFAULT 'unsigned'"),
                            ("chain_breaks", "chain_breaks INTEGER DEFAULT 0"),
                            ("unverified_reports",
                             "unverified_reports INTEGER DEFAULT 0"),
                            ("unverified_requests",
                             "unverified_requests INTEGER DEFAULT 0"),
                            ("malformed_reports",
                             "malformed_reports INTEGER DEFAULT 0"),
                            ("reports_missing",
                             "reports_missing INTEGER DEFAULT 0")):
            if column not in usage_columns:
                self._conn.execute(f"ALTER TABLE usage ADD COLUMN {ddl}")

        # НИ ОДНОГО ИНДЕКСА ЗДЕСЬ НЕ БЫЛО. `leases` растёт примерно на три
        # строки в сутки на воркера и никогда не чистится (`lease_id` свежий на
        # каждое продление, поэтому `INSERT OR REPLACE` ничего не заменяет), а
        # допуск сканировал её целиком на КАЖДОЙ аренде — то есть на запросе,
        # который решает, обслуживать ли клиента. Скана больше нет (решение
        # стоит на двух точечных чтениях `slots`/`generations`), но индекс
        # остаётся: по нему читается привязка ключа к поколению.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS leases_org_issued "
            "ON leases(org_id, issued_at)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS leases_org_pubkey ON leases(org_id, pubkey)")
        # СЛОТЫ ТАРИФА. ВЫДАЁМ ИХ МЫ, ПРИ ВЫПУСКЕ КЛЮЧА, И ЭТО ВСЯ РАЗНИЦА
        # С ШЕСТЬЮ ПРЕДЫДУЩИМИ ЗАХОДАМИ.
        #
        # До сих пор место занимал ПРОЦЕСС, а процесс рождается заново на
        # каждом перезапуске — поэтому OOM-килл упирал клиента в собственный
        # потолок до истечения окна старой аренды, и это воспроизведено на
        # нашем же стенде. Место занимает СЛОТ, строка здесь; перезапуск
        # поднимает на нём НОМЕР ПОКОЛЕНИЯ, а не заводит вторую строку. Новой
        # стороне спроса взяться неоткуда, значит и отказывать не в чем.
        #
        # ЗАВОДЯТСЯ ПРИ ВЫДАЧЕ КЛЮЧА, а не при первой аренде: «есть ли
        # свободный слот» обязано быть ответом по НАШЕЙ таблице. Выведи его из
        # отсутствия строк — и потолок снова считается по тому, что прислал
        # клиент, то есть ровно так, как считался в Б26 … Б26sexies.
        #
        # `epoch` МОНОТОНЕН, ДОЛГОВЕЧЕН И НИКОГДА НЕ ПЕРЕИСПОЛЬЗУЕТСЯ. Фенсинг
        # безопасен только при строгой монотонности И durable-памяти
        # наибольшего виденного номера (Paxos P1a; Kleppmann): рестарт
        # лицензионного сервера не имеет права вернуть номер назад, иначе
        # отфенсенное поколение снова окажется старшим. 0 — слот пуст.
        #
        # `last_heard_at` — ОТМЕТКА, А НЕ ДЕТЕКТОР. Её ставит сервер своими
        # часами на любом аутентифицированном сообщении текущего поколения, и
        # читается она ровно в двух местах: РАНЖИРОВАНИЕ при выборе слота
        # (`admit_generation`, шаг «слышали раньше всех») и экран. Ни одно
        # правило не сравнивает её с порогом — порог и есть тот детектор
        # отказов, которого не существует (Chandra–Toueg).
        #
        # `retired` — слот выше нынешнего потолка после понижения тарифа.
        # Строка не удаляется, потому что удалить её значит потерять эпох, а
        # потеря эпоха — это возврат номера назад под работающим поколением.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS slots ("
            "org_id TEXT, slot_no INTEGER, epoch INTEGER DEFAULT 0, "
            "holder_start_id TEXT DEFAULT '', holder_installation TEXT DEFAULT '', "
            "opened_at REAL, last_heard_at REAL DEFAULT 0, "
            "fenced_at REAL, fenced_by TEXT DEFAULT '', "
            "retired INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, slot_no))")
        # ПОКОЛЕНИЕ — ОДНА СТРОКА НА СТАРТ КОНТЕЙНЕРА, А НЕ НА АРЕНДУ.
        #
        # У одного старта N воркеров и по три аренды на воркера в сутки;
        # «сколько было запусков» обязано быть `COUNT(*)` по строке на старт, а
        # не `COUNT(DISTINCT …)` по строкам аренд — на последнем уже обжёгся
        # бюджет перевыдач (Б26bis), где одно и то же событие давало два разных
        # числа в зависимости от того, как его считали.
        #
        # `claims` — сколько раз это поколение ЗАЯВЛЯЛО слот. У честного
        # перезапуска единица; перезаявка после фенсинга прибавляет, и это вход
        # аномалии `slot_contention`. `released_at` — ЗАПИСЬ ДЛЯ ЭКРАНА, ни
        # одно решение её не читает (§3.2).
        #
        # ИМЯ ПОКОЛЕНИЯ ЧЕКАНИМ МЫ (`_generation_name`), А КЛИЕНТСКОЕ ЛЕЖИТ В
        # `declared_start_id`. Поколение, найденное по одному клиентскому
        # `start_id`, принимало в себя контейнер с ЧУЖОГО тома: оба покупали
        # ёмкость под одним эпохом, никем не отфенсенные, — то есть фенсинг
        # снимался целиком одной переменной окружения и не оставлял следа.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS generations ("
            "org_id TEXT, start_id TEXT, declared_start_id TEXT DEFAULT '', "
            "installation_id TEXT DEFAULT '', "
            "slot_no INTEGER, epoch INTEGER, "
            "first_lease_at REAL, last_lease_at REAL, "
            "engine_version TEXT DEFAULT '', lease_contract INTEGER, "
            "fenced_at REAL, fenced_by TEXT DEFAULT '', released_at REAL, "
            "claims INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, start_id))")
        # Колонки моложе таблиц — тот же порядок и та же причина, что у
        # `leases` выше: том, переживший релиз без колонки, обязан подняться.
        slot_columns = {row[1] for row in
                        self._conn.execute("PRAGMA table_info(slots)")}
        if "retired" not in slot_columns:
            self._conn.execute(
                "ALTER TABLE slots ADD COLUMN retired INTEGER DEFAULT 0")
        generation_columns = {row[1] for row in
                              self._conn.execute("PRAGMA table_info(generations)")}
        # ПРИЧИНА ФЕНСИНГА ХРАНИТСЯ У ПОКОЛЕНИЯ, А НЕ ЧИТАЕТСЯ У СЛОТА. У слота
        # она ОДНА — последняя; взяв её для списка доцеживающих, экран подписал
        # бы «освободила поддержка» под поколением, которое вытеснил обычный
        # перезапуск. Слово рядом с числом не имеет права спорить с числом.
        if "fenced_by" not in generation_columns:
            self._conn.execute(
                "ALTER TABLE generations ADD COLUMN fenced_by TEXT DEFAULT ''")
        # ЧТО НАЗВАЛ КЛИЕНТ — ОТДЕЛЬНО ОТ ТОГО, ЧЕМ ЭТО ОКАЗАЛОСЬ. По этой
        # колонке считается единственное число, которым виден общий
        # `PSEUDEX_START_ID` (`_installations_per_generation`): по имени,
        # которое чеканим мы, все установки различны по построению, и след
        # пропал бы ровно вместе с дефектом, который его оставлял.
        if "declared_start_id" not in generation_columns:
            self._conn.execute(
                "ALTER TABLE generations ADD COLUMN declared_start_id TEXT DEFAULT ''")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS generations_org_declared "
            "ON generations(org_id, declared_start_id)")
        # СУТОЧНЫЕ СЧЁТЫ ПО ОРГАНИЗАЦИИ («запусков за сутки», аномалии) идут по
        # первой аренде поколения, и без индекса это скан таблицы на каждом
        # открытии экрана.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS generations_org_first "
            "ON generations(org_id, first_lease_at)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS generations_org_slot "
            "ON generations(org_id, slot_no, epoch)")
        # ЛЕДЖЕР ЁМКОСТИ. Ключ строки — ключ ПРОЦЕССА: единственный
        # идентификатор, который клиент не выбирает.
        #
        # `granted` — потолок, растёт только у нас и только вверх. `acked` —
        # высшее подтверждённое значение расхода, названное клиентом под MAC.
        # Счёт строится на `acked`, ЗАЖАТОМ между `granted - Q - R` и
        # `granted`: отчёт может двигать сумму только внутри полосы, которую
        # чеканим мы, поэтому занизить его выгодно ровно до нуля.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meter ("
            "org_id TEXT, pubkey TEXT, first_seen REAL, updated_at REAL, "
            "quantum_seq INTEGER DEFAULT 0, quantum_size INTEGER DEFAULT 0, "
            "reserve INTEGER DEFAULT 0, granted INTEGER DEFAULT 0, "
            # Порог, на котором движок обязан прийти за следующим квантом. Сам
            # факт прихода — это и есть оценка расхода, когда отчёта нет.
            "prefetch_at INTEGER DEFAULT 0, "
            "acked INTEGER DEFAULT 0, acked_at REAL, "
            "ack_trust TEXT DEFAULT 'none', rate_per_second REAL DEFAULT 0, "
            # Кванты подряд без проверенного отчёта. Молчание перестаёт быть
            # тишиной: оно видно числом и стоит клиенту скидки.
            "unacked_quanta INTEGER DEFAULT 0, "
            # Расход поехал назад под одним ключом процесса. Процесс не может
            # обслужить меньше, чем уже обслужил, — значит либо два процесса на
            # одном ключе, либо повтор.
            "ack_regressions INTEGER DEFAULT 0, "
            # УДАЛЕНО: `release_echoes` — «сколько раз ключ покупал ёмкость
            # после собственного /v1/release». Оно лечило Б26sexies (кольцо
            # покупало ёмкость отпущенными ключами) тем, что возвращало место
            # занятым. Лечится теперь по построению: купить можно только при
            # ТЕКУЩЕМ эпохе своего слота, а отпустивший и вернувшийся — это
            # новое поколение, то есть новый эпох, то есть фенсинг предыдущего.
            # Колонка на существующих томах остаётся лежать и не читается.
            "PRIMARY KEY (org_id, pubkey))"
        )
        # Колонка моложе таблицы: тома, пережившие релиз без неё, обязаны
        # подняться, а не умереть на «no such column» — тот же порядок и та же
        # причина, что у `leases` выше.
        meter_columns = {row[1] for row in
                         self._conn.execute("PRAGMA table_info(meter)")}
        # ТЕГ СТРОКИ, А НЕ ЕЁ КЛЮЧ. Леджер остаётся ПО ПРОЦЕССУ: у одного
        # поколения N воркеров, у каждого свой расход, свой порог предвыборки и
        # свой ack, и «леджер на слоте» для N воркеров не определён ни одним
        # полем протокола (§3bis.4) — переносить его туда значило бы менять
        # контракт `/v1/meter`, мимо которого прошёл бы весь выпущенный флот.
        # Слот и эпох — тег, по которому считаются агрегаты S_granted/S_acked и
        # аномалии; наследования остатка между поколениями НЕТ намеренно: оно
        # спрятало бы кольцо, показав один баланс там, где его обслужили N раз
        # (§3bis.2).
        for column, ddl in (("slot_no", "slot_no INTEGER"),
                            ("epoch", "epoch INTEGER")):
            if column not in meter_columns:
                self._conn.execute(f"ALTER TABLE meter ADD COLUMN {ddl}")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS meter_org ON meter(org_id)")
        # МЕМОРИ-ТРИППВАЙР: попытки прочитать память движка, которые засёк
        # привилегированный наблюдатель (pseudex/tripwire.py) на стороне клиента и
        # сообщил СРАЗУ — чтобы улика ушла с машины прежде, чем root затрёт локальный
        # лог. Хранится КТО (reader uid/pid/comm/exe/cmdline), НИКОГДА содержимое.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tripwire ("
            "org_id TEXT, ts REAL, method TEXT, reader_uid INTEGER, "
            "reader_pid INTEGER, reader_comm TEXT, reader_exe TEXT, reader_cmdline TEXT)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS tripwire_org ON tripwire(org_id, ts)")
        # ТАРИФ — СТРОКА, А НЕ КОНСТАНТА. Числа тарифа стояли классовыми
        # словарями, поэтому поправить потолок инстансов одному клиенту значило
        # выкатить релиз. Словари никуда не делись: они СИД для чистой базы и
        # последний рубеж, если строки нет, — а источником истины стала таблица.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS plans ("
            "code TEXT PRIMARY KEY, max_instances INTEGER, "
            "processes_per_instance INTEGER, grant_size INTEGER, "
            "quantum_min INTEGER, quantum_max INTEGER, reserve_max INTEGER, "
            # Пусто — значит строка как её посеяли; непусто — кто-то правил.
            # Дешевле и честнее, чем сравнивать шесть чисел с сидом.
            "updated_at REAL, updated_by TEXT DEFAULT '')"
        )
        # СУТОЧНЫЙ СРЕЗ ИСПОЛЬЗОВАНИЯ, и это требование записано до нас:
        # docs/tz-site.md §6 — «таблица `usage` хранит по одному снимку на
        # инстанс… для графика по времени нужны периодические срезы. Решить это
        # надо до того, как будет нарисован экран».
        #
        # СУТКИ, А НЕ ОТЧЁТ, и это арифметика. Отчёт едет на продлении, а
        # `renew_after = ttl // 3` — трижды в сутки на процесс; построчно это
        # порядка полусотни строк в сутки на клиента и десятки миллионов в год на
        # тысяче. Строка на инстанс в сутки даёт тысячи, а не миллионы.
        #
        # Хранится НАКОПИТЕЛЬНЫЙ снимок на конец суток, как и в `usage`, а не
        # прирост: график — разность соседних суток, ровно та же вычитаемая
        # ватермарка, которой уже считает `billing/services.py::build_invoice`.
        # Прирост пришлось бы вычислять на записи, а значит доверять тому, что
        # предыдущая запись случилась.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS usage_daily ("
            "org_id TEXT, instance_id TEXT, day TEXT, "
            "requests INTEGER DEFAULT 0, values_total INTEGER DEFAULT 0, "
            "reports INTEGER DEFAULT 0, updated_at REAL, "
            "PRIMARY KEY (org_id, instance_id, day))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS usage_daily_org ON usage_daily(org_id, day)")
        self._conn.commit()
        self._seed_plans()
        self._adopt_existing_volume()

    def _adopt_existing_volume(self) -> None:
        """Перенести том, который УЖЕ ЖИЛ, в конструкцию слотов. Идемпотентно.

        ЗАСЕВАЮТСЯ ТОЛЬКО СЛОТЫ. ДЕРЖАТЕЛЕЙ МИГРАЦИЯ НЕ НАЗНАЧАЕТ НИ ОДНОГО —
        И ЭТО НЕ ОСТОРОЖНОСТЬ, А ЕДИНСТВЕННЫЙ ВАРИАНТ, КОТОРЫЙ НЕ ВРЁТ.

        Здесь усыновлялась каждая установка с открытой арендой: ей отдавался
        свободный слот, чтобы «каждая установка, державшая слот ДО, держала
        слот ПОСЛЕ» (§7.3, S-14). Требование написано в предположении, что
        установка — это ТОМ. На боевом флоте это неверно: выпущенный
        `entrypoint.sh` (0.3.17, строки 99–101) чеканит `PSEUDEX_INSTANCE_ID`
        из `/dev/urandom` НА КАЖДЫЙ СТАРТ КОНТЕЙНЕРА, а `service.py:125` берёт
        переменную раньше, чем идентификатор тома. Значит установка выпущенного
        флота не переживает перезапуск ВООБЩЕ, и в окне аренды (24 ч) лежит
        столько «установок», сколько раз контейнер поднимался за сутки.

        Замер на рабочем дереве: ОДИН контейнер, шесть честных перезапусков,
        тариф «Промышленный» — после миграции «занято 6 из 12», шесть держателей
        `rand-0 … rand-5`, из которых жив ноль или один. На «Рабочем» (4 слота)
        те же шесть перезапусков дают «занято 4 из 4» клиенту с одним
        контейнером. Это ровно дефект Б26bis — экран, врущий о том, кто держит
        слот, — и вдобавок он вреден по существу: ранжирование 2c вытесняет
        слот, который слышали раньше всех, а мёртвые призраки со свежими
        отметками аренды стоят в очереди впереди живого соседа.

        ЧЕМ ЗАМЕНЕНО ТО, ЧТО УСЫНОВЛЕНИЕ ДАВАЛО:

          * «клиент не видит чужого на своём месте» — слот берётся на первой же
            аренде после релиза по ОБЫЧНОМУ правилу (`admit_generation`), и
            занимает его тот, кто реально пришёл, а не тот, кто оставил запись;
          * «никто не заперт» — держится сильнее, чем при усыновлении: у ключа
            выпущенного движка нет привязки, а покупка без привязки не фенсится
            вовсе (`meter_if_allowed`, ветка `binding is None`). Контейнер
            обслуживает без перерыва и получает слот на продлении (≤ 8 ч);
          * «экран не врёт» — вместо назначенных призраков `slots_view` называет
            ЧИСЛО установок прошлого релиза, ещё не занявших слот
            (`pending_installations`): «занято 0 из 4» без него читается как
            «ничего не работает», а это такая же догадка, как «занято 4 из 4».

        ЧТО ЭТО СТОИТ, СКАЗАНО ПРЯМО: до восьми часов после платформенного
        релиза экран показывает занятость НИЖЕ фактической, и фенсинг для
        выпущенного флота начинается не мгновенно, а с его следующего продления.
        Первое названо числом рядом; второе — окно, в котором флот ведёт себя
        ровно так, как вёл все предыдущие месяцы, то есть регрессии нет.
        """
        with self._lock:
            orgs = [str(row[0]) for row in self._conn.execute(
                "SELECT DISTINCT org_id FROM keys")]
        for org_id in orgs:
            plan = self.org_plan(org_id)
            if not plan:
                continue
            # СЛОТЫ ЗАВОДЯТСЯ ПО ТАРИФУ, А НЕ ПО ТОМУ, ЧТО ПРИСЛАЛ КЛИЕНТ:
            # «есть ли свободный слот» обязано быть ответом по НАШЕЙ таблице.
            self.ensure_slots(org_id, plan)

    def pending_installations(self, org_id: str, now: float) -> int:
        """Установки прошлого релиза, у которых аренда ещё жива, а слота ещё нет.

        ЧИСЛО ВМЕСТО ДОГАДКИ. Миграция намеренно не назначает держателей
        (`_adopt_existing_volume`), поэтому сразу после платформенного релиза
        занятость ниже фактической. «0 из 4» без этого числа читается человеком
        как ответ «у вас ничего не работает» — та же ошибка, что и «4 из 4» с
        призраками, только в другую сторону. Здесь она названа: столько-то
        контейнеров прошлого релиза ещё держат аренду и займут слоты на
        ближайшем продлении.

        `slot_no IS NULL` — признак строки, записанной ДО этого релиза: новый
        сервер привязку пишет всегда. Окно считается по самой аренде
        (`issued_at + ttl_seconds`), а не по константе: константа здесь была бы
        седьмым таймером, а строка аренды уже носит свой срок.
        """
        row = self._fetchone(
            "SELECT COUNT(DISTINCT instance_id) FROM leases "
            "WHERE org_id=? AND released_at IS NULL AND slot_no IS NULL "
            "AND COALESCE(instance_id,'')<>'' "
            "AND issued_at + COALESCE(ttl_seconds, 0) >= ?", (org_id, now))
        return int(row[0] or 0) if row else 0

    def _seed_plans(self) -> None:
        """Посеять тарифы из констант — `INSERT OR IGNORE`, НЕ `REPLACE`.

        СТРОКА ПОБЕЖДАЕТ КОНСТАНТУ, иначе таблица бессмысленна: правка тарифа
        обязана пережить рестарт, а `REPLACE` возвращал бы её к сиду на каждом
        подъёме процесса.

        Обратную сторону надо назвать вслух, потому что она неочевидна и укусит
        того, кто про неё не знает: **поправить константу и выкатить релиз больше
        НЕ меняет работающий тариф**. Поэтому расхождение видно снаружи —
        `plans()` отдаёт `source`, и `edited` означает, что здесь правили руками.

        Гонки нет: лицензионный сервер — один процесс (`devserver.py` поднимает
        два ASGI-приложения на одном `STORE` под `RLock`).
        """
        # НЕПОЛНЫЙ СИД — ОШИБКА В КОДЕ, И ОНА ПАДАЕТ ЗДЕСЬ, А НЕ У КЛИЕНТА.
        #
        # Раньше недостающие значения добирались через `.get(code, …)` с
        # умолчаниями «старта», и тариф, добавленный в `PLAN_INSTANCES` и
        # забытый в `PLAN_GRANT`, тихо оседал в таблице с грантом младшего
        # тарифа. Это ровно тот дефект, ради которого заводился `known_plan`, —
        # он просто переехал бы на одну таблицу дальше и стал невидим, потому
        # что строка-то теперь есть.
        incomplete = {
            code: [name for name, table in (("PLAN_GRANT", self.PLAN_GRANT),
                                            ("QUANTUM_BOUNDS", self.QUANTUM_BOUNDS),
                                            ("RESERVE_MAX", self.RESERVE_MAX))
                   if code not in table]
            for code in self.PLAN_INSTANCES
        }
        incomplete = {code: missing for code, missing in incomplete.items() if missing}
        if incomplete:
            raise ValueError(
                "неполный сид тарифов, тариф объявлен не во всех таблицах: "
                + "; ".join(f"{code} нет в {', '.join(tables)}"
                            for code, tables in sorted(incomplete.items())))
        with self._lock:
            for code, instances in self.PLAN_INSTANCES.items():
                low, high = self.QUANTUM_BOUNDS[code]
                self._conn.execute(
                    "INSERT OR IGNORE INTO plans (code, max_instances, "
                    "processes_per_instance, grant_size, quantum_min, quantum_max, "
                    "reserve_max, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,'')",
                    (code, instances, self.PROCESSES_PER_INSTANCE,
                     self.PLAN_GRANT[code], low, high, self.RESERVE_MAX[code],
                     time.time()),
                )
            self._conn.commit()

    def _fetchall(self, sql: str, params: tuple) -> list[tuple]:
        """Every READ goes through here, under the same lock the writes take.

        The rule and the measurement behind it are `pseudex/audit.py::_fetchall`:
        `check_same_thread=False` lets threads share one connection, it does not
        make the connection concurrent, and a read interleaved with another
        thread's INSERT+commit returns a row with COLUMNS MISSING rather than an
        error anyone would recognise as a locking bug.

        Here it is worse than in the audit, because one of the readers is
        `binding_of` — the query that decides whether a customer's process may
        buy the capacity it needs to serve at all — and `devserver.py` runs the
        admin app on a second thread against this same connection.
        """
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _fetchone(self, sql: str, params: tuple) -> tuple | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def issue_key(self, org_id: str, plan: str) -> str:
        key = KEY_PREFIX + secrets.token_urlsafe(32)
        with self._lock:
            self._conn.execute(
                "INSERT INTO keys (key_hash, org_id, plan, status, created_at) VALUES (?,?,?,?,?)",
                (hash_key(key), org_id, plan, STATUS_ACTIVE, time.time()),
            )
            self._conn.commit()
        # СЛОТЫ ВЫДАЁМ МЫ, И ИМЕННО ЗДЕСЬ. Потолок обязан быть посчитан ПРИ
        # ВЫДАЧЕ ключа, а не выведен из того, что потом пришлёт клиент: второе
        # и есть корень всех шести заходов.
        self.ensure_slots(org_id, plan)
        return key

    def lookup(self, key: str) -> KeyRecord | None:
        row = self._fetchone(
            "SELECT org_id, status, plan FROM keys WHERE key_hash=?", (hash_key(key),)
        )
        return KeyRecord(row[0], row[1], row[2]) if row is not None else None

    def revoke_key_hash(self, key_hash: str) -> int:
        """Revoke ONE key. Statuses were per-organisation only, so the cabinet's
        "отозвать ключ" button set a local flag, reported success, and left the
        key leasing forever — the departing engineer's copy kept working.

        Matched on the hash because that is all the storefront holds: the key
        itself is shown once and never stored in readable form on either side.

        ПОТОЛОК СЛОТОВ ПЕРЕСЧИТЫВАЕТСЯ ТУТ ЖЕ. Отзыв ключа И ЕСТЬ понижение
        тарифа, когда организацию переводили не через `/admin/replan`, а выдачей
        нового ключа и отзывом старого: `org_plan` читает только ДЕЙСТВУЮЩИЕ
        ключи и отвечает «Старт» сразу, а строки `slots` оставались от
        «Промышленного» до чьей-нибудь следующей аренды. Всё это время
        `/admin/instances` отдавал двенадцать живых слотов при `slot_count`
        один, и занятость на экране могла превысить потолок — тот же дефект
        Б26bis, и чинить его надо там, где меняется причина.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT org_id FROM keys WHERE key_hash=?", (key_hash,)).fetchone()
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE key_hash=? AND status=?",
                (STATUS_REVOKED, key_hash, STATUS_ACTIVE),
            )
            self._conn.commit()
            revoked = cursor.rowcount
        if revoked and row is not None:
            org_id = str(row[0])
            self.ensure_slots(org_id, self.org_plan(org_id))
        return revoked

    def set_status(self, org_id: str, status: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE org_id=?", (status, org_id)
            )
            self._conn.commit()
        return cursor.rowcount

    def set_org_plan(self, org_id: str, plan: str) -> int:
        """Перевести ВСЕ ключи организации на другой тариф.

        ТАРИФ ЖИВЁТ НА КЛЮЧЕ, а не на организации, и это делает смену тарифа
        отдельной операцией, а не полем в одной таблице. Пересоздавать ключ
        нельзя: он прописан в конфиге работающего контейнера клиента, и смена
        тарифа не имеет права останавливать его шлюз — это ровно тот случай,
        когда наши деньги останавливают чужой прод.

        Возвращает число тронутых ключей. Ноль значит, что ключей у организации
        нет вовсе, и вызывающему это надо отличать от успеха: он только что
        пообещал клиенту лимиты, которых сервер не выдаст.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET plan=? WHERE org_id=?", (plan, org_id)
            )
            self._conn.commit()
        # ВВЕРХ — НОВЫЕ СЛОТЫ СВОБОДНЫМИ, ВНИЗ — ВЕРХНИЕ `retired`. Держатель
        # выведенного слота узнаёт об этом на следующей ПОКУПКЕ, текстом про
        # тариф; уже купленную ёмкость он доцеживает, как и всякий отфенсенный.
        self.ensure_slots(org_id, plan)
        return cursor.rowcount

    def record_lease(self, lease_id: str, org_id: str, instance_id: str,
                     process_id: str, ttl_seconds: int, pubkey: str = "",
                     engine_version: str = "",
                     lease_contract: int | None = None,
                     start_id: str = "", slot_no: int | None = None,
                     epoch: int | None = None) -> None:
        """Строка аренды. `slot_no`/`epoch` — ПРИВЯЗКА КЛЮЧА К ПОКОЛЕНИЮ, и
        только по ней `/v1/meter` решает, фенсить ли. `None` значит «привязки
        нет»: такой ключ не фенсится вовсе — ни у старого ряда, ни у вызова
        мимо `lease_generation`."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO leases "
                "(lease_id, org_id, instance_id, process_id, pubkey, issued_at, "
                "ttl_seconds, engine_version, lease_contract, start_id, slot_no, "
                "epoch) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (lease_id, org_id, instance_id, process_id, pubkey, time.time(),
                 ttl_seconds, engine_version, lease_contract, start_id, slot_no,
                 epoch),
            )
            self._conn.commit()

    def _accumulate_values(self, org_id: str, instance_id: str, reported: int) -> int:
        """Fold a new reading into a counter that never goes backwards.

        The vault lives on the customer's volume, so `docker volume rm` restarts
        `first_seen` and the reported count drops to zero. Billing the reported
        number directly would make deleting the vault a way not to pay.

        A drop is treated as a NEW INSTALLATION rather than as a correction: the
        growth since the reset is added on top of what was already accumulated.
        Re-protecting the same people after a reset therefore counts again,
        which is the honest reading — the engine did the work a second time.

        It is not evidence of anything. A vault can be lost honestly, in a
        migration or a disk failure. It is recorded as a `reset` so a pattern is
        visible, and a pattern is a conversation, not an accusation.
        """
        row = self._fetchone(
            "SELECT values_reported, values_total, resets FROM usage "
            "WHERE org_id=? AND instance_id=?", (org_id, instance_id),
        )
        if row is None:
            return reported
        previous, total, resets = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
        if reported >= previous:
            return total + (reported - previous)
        _log.warning("usage counter went backwards for org=%s instance=%s: "
                     "%d -> %d (vault reset or restore); accumulating on top",
                     org_id, instance_id, previous, reported)
        self._conn.execute(
            "UPDATE usage SET resets=? WHERE org_id=? AND instance_id=?",
            (resets + 1, org_id, instance_id),
        )
        return total + reported

    def record_report_secret(self, org_id: str, pubkey: str,
                             secret_hex: str) -> None:
        """КЛЮЧ — ОТКРЫТЫЙ КЛЮЧ ПРОЦЕССА, А НЕ `instance_id`.

        `instance_id` приходит из переменной окружения, которую ставит клиент —
        то самое, что мы убрали из подсчёта тарифа именно потому, что клиент его
        выбирает. Пока секрет лежал под ним, ломались ОБЕ стороны:

          * держатель ключа организации мог назваться чужим `instance_id`, и мы
            чеканили свежий секрет, запечатанный ЕГО ключу, поверх честного —
            после чего его отчёты проходили как `signed`, а настоящие падали в
            `bad_signature`;
          * и без всякой атаки: `entrypoint.sh` даёт всем воркерам ОДИН
            `instance_id`, у каждого свой ключ процесса и свой секрет, и все
            писали в одну строку — «подписанным» оставался только последний
            арендовавший, остальные навсегда `bad_signature`.

        Ключ процесса решает обе задачи разом: секрет, запечатанный ключу K,
        проверяется только против отчёта, назвавшего K, и у N воркеров N строк.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO process_reports (org_id, pubkey, secret, updated_at) "
                "VALUES (?,?,?,?) ON CONFLICT(org_id, pubkey) DO UPDATE SET "
                "secret=excluded.secret, updated_at=excluded.updated_at",
                (org_id, pubkey, secret_hex, time.time()),
            )
            self._conn.commit()

    def report_secret(self, org_id: str, pubkey: str) -> str:
        row = self._fetchone(
            "SELECT secret FROM process_reports WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        return (row[0] or "") if row else ""

    def record_usage(self, org_id: str, instance_id: str, requests: int,
                     entities: dict[str, int], values: int, seq: int = 0,
                     prev: str = "", signature: str = "",
                     trust: str = "unsigned", report_pubkey: str = "",
                     build: str = "") -> None:
        """Record the newest report.

        `requests` and `entities` are OVERWRITTEN — each report restates the
        instance's own cumulative totals, so the latest one is the truth.

        `values` is different, because it is what the invoice is computed from:
        it is folded into a counter that never decreases, so a customer who
        deletes their vault does not thereby delete what they owe. See
        docs/billing-integrity.md §2.1.
        """
        if not signature:
            trust = "unsigned"
        breaks = self._chain_breaks(org_id, instance_id, seq, prev, trust,
                                    report_pubkey)
        fresh = self._report_advances(org_id, report_pubkey, seq)
        if report_pubkey:
            self._record_process_report(org_id, report_pubkey, seq, prev,
                                        signature, breaks, fresh)
            self._record_build(org_id, report_pubkey, build, trust)
        # ПОВТОР НЕ ДЕРЖИТ МЁРТВЫЙ КОНТЕЙНЕР ЖИВЫМ. Отметка `updated_at` — это
        # признак жизни, по которому инстанс занимает слот тарифа; двигая её
        # на каждом POST, мы позволяли пересылать один и тот же честный отчёт
        # (у него настоящий MAC) и держать слот остановленного контейнера
        # сколько угодно — то есть блокировать самого себя или соседа.
        # Двигает её только отчёт, продвинувший цепь своего ключа.
        seen = "updated_at=excluded.updated_at, " if fresh else ""
        # НЕПРОВЕРЕННЫЙ ОТЧЁТ НЕ СТАНОВИТСЯ СЧЁТОМ. Раньше вердикт писался в
        # колонку и на этом всё: цифры принимались одинаково при `signed`,
        # `bad_signature` и `unsigned`, а `usage_totals` — то, из чего считается
        # инвойс — этих колонок не отдавал вовсе. Снять подпись было ТИШЕ, чем
        # подделать: без неё проверка даже не запускалась.
        #
        # Обслуживать продолжаем в любом случае — падать из-за спора о биллинге
        # значит наказывать конечного пользователя. Но в billable-счётчики
        # непроверенное не идёт: оно копится отдельно, чтобы разговор был
        # предметным, а не «поверьте нам».
        if trust != "signed":
            with self._lock:
                self._conn.execute(
                    "INSERT INTO usage (org_id, instance_id, updated_at, reports, "
                    "unverified_reports, unverified_requests, trust) "
                    "VALUES (?,?,?,0,1,?,?) "
                    "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                    f"{seen}"
                    "unverified_reports=usage.unverified_reports+1, "
                    "unverified_requests=excluded.unverified_requests, "
                    "trust=excluded.trust",
                    (org_id, instance_id, time.time(), requests, trust),
                )
                self._conn.commit()
            _log.warning("usage report NOT billed for org=%s instance=%s: trust=%s",
                         org_id, instance_id, trust)
            return
        # ПОВТОР СТАРОГО ЧЕСТНОГО ОТЧЁТА НЕ ОПУСКАЕТ СЧЁТЧИК. У него настоящий
        # MAC — он и был настоящим, — поэтому проверка подписи его пропускает, а
        # `requests` перезаписывается последним пришедшим. Root на хосте ловит
        # вчерашний отчёт и шлёт его снова: 5000 -> 1000. `values` защищён
        # монотонным накоплением, `requests` не был.
        #
        # Разрыв цепи — это ровно тот случай, и при нём счётчики не двигаются
        # вниз: берём максимум. Честному клиенту это ничего не стоит, его
        # `requests` и так растёт.
        with self._lock:
            accumulated = self._accumulate_values(org_id, instance_id, values)
            previous = self._fetchone(
                "SELECT requests FROM usage WHERE org_id=? AND instance_id=?",
                (org_id, instance_id))
            if previous is not None:
                requests = max(requests, int(previous[0] or 0))
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, requests, "
                "entities, values_reported, values_total, seq, prev, signature, "
                "trust, chain_breaks) VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                f"{seen}"
                "reports=usage.reports+1, "
                "requests=excluded.requests, entities=excluded.entities, "
                "values_reported=excluded.values_reported, "
                "values_total=excluded.values_total, seq=excluded.seq, "
                "prev=excluded.prev, signature=excluded.signature, "
                "trust=excluded.trust, chain_breaks=excluded.chain_breaks",
                (org_id, instance_id, time.time(), requests, json.dumps(entities),
                 values, accumulated, seq, prev, signature, trust, breaks),
            )
            # СУТОЧНЫЙ СРЕЗ ПИШЕТСЯ ТОЛЬКО ЗДЕСЬ — на подтверждённой ветке.
            # Неподтверждённое не входит в счёт, значит не должно входить и в
            # график счёта: иначе экран показывал бы объём, за который никто не
            # выставит, и расхождение с инвойсом пришлось бы объяснять словами.
            # Отдельно оно и так видно — `unverified_reports`/`unverified_requests`.
            self._record_daily(org_id, instance_id, requests, accumulated)
            self._conn.commit()

    def _record_daily(self, org_id: str, instance_id: str,
                      requests: int, values_total: int) -> None:
        """Снимок накопительных счётчиков на конец суток. Зовётся ИЗ-ПОД лока.

        Перезаписывает числа и увеличивает `reports`: за сутки отчётов несколько,
        и верен последний — ровно так же, как в `usage`. График рисуется
        разностью соседних суток, поэтому хранить надо накопительное, а не
        прирост: прирост требовал бы верить, что предыдущая запись случилась.
        """
        now = time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        self._conn.execute(
            "INSERT INTO usage_daily (org_id, instance_id, day, requests, "
            "values_total, reports, updated_at) VALUES (?,?,?,?,?,1,?) "
            "ON CONFLICT(org_id, instance_id, day) DO UPDATE SET "
            # МАКСИМУМ, А НЕ ПРИСВОЕНИЕ. Повтор старого честного отчёта имеет
            # настоящий MAC и проходит проверку подписи; `record_usage` уже
            # защищает от него `requests` максимумом, и срез обязан вести себя
            # так же, иначе график поедет вниз там, где счёт не поехал.
            "requests=MAX(usage_daily.requests, excluded.requests), "
            "values_total=MAX(usage_daily.values_total, excluded.values_total), "
            "reports=usage_daily.reports+1, updated_at=excluded.updated_at",
            (org_id, instance_id, day, requests, values_total, now),
        )

    def usage_history(self, org_id: str, days: int = 30) -> list[dict[str, object]]:
        """Накопительные счётчики организации по суткам, старые первыми.

        МОЛЧАВШИЙ ИНСТАНС ПЕРЕНОСИТСЯ ВПЕРЁД, А НЕ ИСЧЕЗАЕТ, и без этого ряд
        получался НЕ МОНОТОННЫМ. Считать `SUM(...) GROUP BY day` — значит взять
        сумму по тем инстансам, которые отчитались именно в эти сутки: два
        инстанса в понедельник и один во вторник дают падение, разность соседних
        суток становится отрицательной, и последняя точка расходится с
        `usage_totals`, который суммирует все инстансы, какие вообще видел.
        Инстанс молчит не когда обнулился, а когда его остановили или он не успел
        отчитаться в эти сутки; его накопительный итог никуда не делся.

        Перенос делается здесь, а не в SQL: оконная функция дала бы то же самое
        ценой зависимости от версии SQLite внутри SQLCipher, а строк тут — сутки
        на инстансы одной организации.
        """
        window = max(1, min(int(days), 365))
        rows = self._fetchall(
            "SELECT day, instance_id, requests, values_total, reports "
            "FROM usage_daily WHERE org_id=? ORDER BY day", (org_id,))
        latest: dict[str, tuple[int, int]] = {}
        by_day: dict[str, dict[str, object]] = {}
        for day, instance_id, requests, values_total, reports in rows:
            latest[instance_id] = (int(requests or 0), int(values_total or 0))
            bucket = by_day.setdefault(day, {"day": day, "reports": 0})
            bucket["reports"] = int(bucket["reports"]) + int(reports or 0)
            # Итог суток — состояние ВСЕХ известных инстансов на конец этих
            # суток, включая тех, кто сегодня промолчал.
            bucket["requests"] = sum(value[0] for value in latest.values())
            bucket["values"] = sum(value[1] for value in latest.values())
            bucket["instances"] = len(latest)
        return [by_day[day] for day in sorted(by_day)][-window:]

    def fleet_totals(self, window_seconds: int) -> dict[str, object]:
        """One row of numbers about the WHOLE fleet, for the scrape.

        AGGREGATED IN SQL AND NOT BY WALKING `list_orgs()`. The console reads
        per-organisation rows because a human is going to look at one of them;
        a scrape every fifteen seconds must not carry a cost that grows with the
        customer base, and `/admin/list` is the operator-only catalogue anyway.

        `breaks_by_org` is the ONE thing labelled by organisation, and only
        organisations that actually have a break appear in it. Prometheus keeps
        a series per label combination for ever, so labelling by customer
        normally means the series count grows with sales and never shrinks —
        here it grows with TROUBLE, which is bounded, drops back to nothing when
        the trouble is fixed, and is exactly the list somebody needs to be handed
        rather than to go looking for.
        """
        totals = self._fetchone(
            "SELECT COUNT(DISTINCT org_id), COALESCE(SUM(requests), 0), "
            "COALESCE(SUM(values_total), 0), 0, "
            "COALESCE(SUM(unverified_reports), 0), COALESCE(SUM(malformed_reports), 0), "
            "COALESCE(SUM(reports_missing), 0), COALESCE(SUM(resets), 0) FROM usage", ()
        ) or (0, 0, 0, 0, 0, 0, 0, 0)
        keys = self._fetchall("SELECT status, COUNT(*) FROM keys GROUP BY status", ())
        cutoff = time.time() - window_seconds
        # СЧИТАЮТСЯ ЛИЧНОСТИ, А НЕ СТРОКИ, и разница здесь кратная. `lease_id`
        # свежий на КАЖДОМ продлении, а `released_at` ставится только при явном
        # освобождении: при TTL 86400 и продлении через TTL//3 один живой воркер
        # оставляет в окне три-четыре строки, и `COUNT(*)` завысил бы флот
        # втрое. Считается `pubkey` — единственный идентификатор, который клиент
        # НЕ выбирает: он рождается в памяти воркера, на него запечатывается
        # бандл, и два процесса не могут иметь один и тот же, не будучи
        # пропатченными.
        #
        # Инстанс считается ПАРОЙ с организацией: `instance_id` приходит из
        # переменной окружения, то есть его выбирает клиент, и два разных
        # клиента, оставивших умолчание, слились бы в один. SQLite не умеет
        # `COUNT(DISTINCT a, b)`, отсюда подзапрос.
        live = "FROM leases WHERE issued_at >= ? AND released_at IS NULL"
        instances = self._fetchone(
            f"SELECT (SELECT COUNT(DISTINCT org_id) {live}), "
            f"(SELECT COUNT(*) FROM (SELECT DISTINCT org_id, instance_id {live})), "
            f"(SELECT COUNT(DISTINCT pubkey) {live})",
            (cutoff, cutoff, cutoff)) or (0, 0, 0)
        # ЦЕПЬ БЕРЁТСЯ ИЗ `process_reports`, А НЕ ИЗ `usage`, и это не выбор
        # источника, а исправление. `usage.chain_breaks` ПЕРЕЗАПИСЫВАЕТСЯ
        # накопительным счётчиком того процесса, чей отчёт пришёл последним, —
        # при нескольких воркерах на инстанс число скачет и может УМЕНЬШАТЬСЯ.
        # Экспортированное как `counter` и опрошенное через `increase()`, оно
        # рисовало бы призрачные сбросы и приросты. `process_reports` хранит
        # строку на (организация, процесс) и растёт только вверх — и это же то,
        # что суммирует `/admin/chains`, так что метрика и консоль больше не
        # спорят.
        broken = self._fetchall(
            "SELECT org_id, SUM(chain_breaks) FROM process_reports GROUP BY org_id "
            "HAVING SUM(chain_breaks) > 0", ())
        chain_total = self._fetchone(
            "SELECT COALESCE(SUM(chain_breaks), 0) FROM process_reports", ()) or (0,)
        return {
            "orgs_with_usage": int(totals[0] or 0),
            "requests": int(totals[1] or 0),
            "values": int(totals[2] or 0),
            "chain_breaks": int(chain_total[0] or 0),
            "unverified_reports": int(totals[4] or 0),
            "malformed_reports": int(totals[5] or 0),
            "reports_missing": int(totals[6] or 0),
            "resets": int(totals[7] or 0),
            "keys_by_status": {str(row[0] or "unknown"): int(row[1] or 0) for row in keys},
            "orgs_serving": int(instances[0] or 0),
            "instances_serving": int(instances[1] or 0),
            "processes_serving": int(instances[2] or 0),
            "breaks_by_org": {str(row[0]): int(row[1] or 0) for row in broken},
        }

    def chain_detail(self, org_id: str, limit: int = 200) -> dict[str, object]:
        """Строки цепи отчётов по каждому ПРОЦЕССУ организации.

        `usage_totals` отдаёт СУММУ разрывов по организации — число, по которому
        видно, что что-то не так, и совершенно нечего делать дальше. Это
        детализация за ним: какой процесс, на каком месте цепи, когда последний
        раз слышали. Ключ процесса режется до префикса — целиком он нужен только
        для сверки подписи, а на экране это шум, который вдобавок приглашает
        куда-нибудь его скопировать.

        ОГРАНИЧЕН, КАК И ВСЯКОЕ ДРУГОЕ ПЕРЕЧИСЛЕНИЕ ЗДЕСЬ. `process_reports`
        получает строку на КАЖДЫЙ воркер на КАЖДЫЙ перезапуск — ключ процесса
        живёт ровно столько, сколько процесс, — и не чистится ничем. У давнего
        клиента на старшем тарифе это десятки тысяч строк, и собирать их все
        значит держать лок store, который в этот момент нужен выдаче аренд всем
        остальным.
        """
        window = max(1, min(int(limit), 1000))
        total = self._fetchone(
            "SELECT COUNT(*), COALESCE(SUM(chain_breaks), 0) "
            "FROM process_reports WHERE org_id=?", (org_id,))
        rows = self._fetchall(
            "SELECT pubkey, seq, prev, chain_breaks, build_changes, build, updated_at "
            "FROM process_reports WHERE org_id=? "
            # Порванные первыми: если строк больше, чем влезает, отрезать надо
            # тишину, а не сигнал.
            "ORDER BY chain_breaks DESC, updated_at DESC LIMIT ?",
            (org_id, window))
        return {
            "processes": [{"pubkey": (r[0] or "")[:16], "seq": int(r[1] or 0),
                           "prev": (r[2] or "")[:16], "chain_breaks": int(r[3] or 0),
                           "build_changes": int(r[4] or 0), "build": (r[5] or "")[:24],
                           "updated_at": r[6]}
                          for r in rows],
            # Сумма считается по ВСЕМ строкам, а не по показанным: иначе экран,
            # обрезанный лимитом, показывал бы разрывов меньше, чем их есть.
            "processes_total": int(total[0] or 0) if total else 0,
            "chain_breaks": int(total[1] or 0) if total else 0,
        }

    def record_missing_report(self, org_id: str, instance_id: str) -> None:
        """Продление без отчёта, хотя `lease_id` в теле есть.

        `lease_id` клиент шлёт с самого начала, и сервер его НЕ ЧИТАЛ вовсе —
        поэтому «это продление, отчёт обязан быть» установить было нечем.
        Теперь установить есть чем, и молчание стало записью.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, "
                "reports_missing) VALUES (?,?,?,0,1) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, "
                "reports_missing=usage.reports_missing+1",
                (org_id, instance_id, time.time()))
            self._conn.commit()

    def record_malformed(self, org_id: str, instance_id: str) -> None:
        """Отчёт пришёл и не разобрался. Считается отдельно от всего.

        Раньше такой отчёт ронял сервер в 500, а 500 у клиента grace-worthy —
        то есть отравить собственный отчёт было способом уехать в grace, не
        трогая сеть. Теперь это запись, и она видна в итогах: инвойс не должен
        путать «расхода не было» с «расход был, но мы его не прочитали».
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, "
                "malformed_reports) VALUES (?,?,?,0,1) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, "
                "malformed_reports=usage.malformed_reports+1",
                (org_id, instance_id, time.time()))
            self._conn.commit()

    def _chain_breaks(self, org_id: str, instance_id: str, seq: int, prev: str,
                      trust: str, report_pubkey: str = "") -> int:
        """Разрывы цепи отчётов ОДНОГО ПРОЦЕССА.

        Строка заведена под ключ процесса, поэтому перезапуск — это новая
        строка, а не особый случай: `seq` внутри одной строки обязан расти на
        единицу, `prev` — совпадать с хешем нашей записанной подписи. Повтор
        старого отчёта и вечная единица ловятся этим же условием, без отдельной
        эвристики про «мнимый перезапуск», которая была нужна, только пока
        строка делилась между воркерами.
        """
        if not report_pubkey:
            return 0
        row = self._fetchone(
            "SELECT seq, signature, chain_breaks FROM process_reports "
            "WHERE org_id=? AND pubkey=?", (org_id, report_pubkey),
        )
        if row is None:
            return 0
        last_seq, last_signature, breaks = (int(row[0] or 0), row[1] or "",
                                            int(row[2] or 0))
        if last_seq == 0:
            return breaks
        expected_prev = hashlib.sha256(last_signature.encode("ascii")).hexdigest()
        if seq == last_seq + 1 and (not prev or prev == expected_prev):
            return breaks
        _log.warning("usage chain break for org=%s pubkey=%s: seq %d -> %d, prev %s "
                     "(trust=%s)", org_id, report_pubkey[:12], last_seq, seq,
                     "ok" if prev == expected_prev else "mismatch", trust)
        return breaks + 1

    def _report_advances(self, org_id: str, pubkey: str, seq: int) -> bool:
        """Продвинул ли этот отчёт цепь СВОЕГО ключа процесса.

        Признак жизни обязан двигаться только вперёд: повтор старого честного
        отчёта проходит проверку подписи (MAC настоящий — он и был настоящим) и
        до этой правки обновлял `updated_at`, то есть держал слот
        остановленного контейнера ровно столько, сколько его повторяли.

        Ключ процесса — единственная цепь, по которой это решается: `seq`
        растёт внутри одного процесса, а `usage` пишут все воркеры инстанса,
        и их номера между собой не сравнимы.

        БЕЗ КЛЮЧА СУДИТЬ НЕЧЕМ, и тогда отметка двигается: это движок
        контракта ниже третьего, у которого отчёт едет только вместе с
        продлением, — а продление и так признак жизни. Никакого нового окна
        это не открывает.
        """
        if not pubkey:
            return True
        row = self._fetchone(
            "SELECT seq FROM process_reports WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        if row is None or row[0] is None:
            return True
        return int(seq) > int(row[0] or 0)

    def _record_process_report(self, org_id: str, pubkey: str, seq: int,
                               prev: str, signature: str, breaks: int,
                               fresh: bool) -> None:
        # UPSERT, А НЕ UPDATE. Строка процесса создаётся при выдаче секрета, но
        # отчёт может прийти и для ключа, которому мы секрета не выдавали, — и
        # тогда `UPDATE` молча ничего не делал, `seq` навсегда оставался нулём,
        # а `_chain_breaks` возвращал ноль на любой последовательности. Вечная
        # единица проходила незамеченной.
        # ПОВТОР ДВИГАЕТ ТОЛЬКО ВЕРДИКТ О ЦЕПИ. Не отметку жизни — иначе один
        # пересылаемый отчёт держал бы место ключа под потолком процессов
        # сколько угодно (`_report_advances`), — и не саму цепь: записав
        # `seq` назад, мы бы и открыли обход (следующий повтор снова «растёт»),
        # и выписали честному клиенту разрыв на его же следующем отчёте, чей
        # `prev` считается от ПОСЛЕДНЕЙ записанной подписи.
        moved = ("seq=excluded.seq, prev=excluded.prev, "
                 "signature=excluded.signature, updated_at=excluded.updated_at, "
                 if fresh else "")
        with self._lock:
            self._conn.execute(
                "INSERT INTO process_reports (org_id, pubkey, seq, prev, signature, "
                "chain_breaks, updated_at) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, pubkey) DO UPDATE SET "
                f"{moved}"
                "chain_breaks=excluded.chain_breaks",
                (org_id, pubkey, seq, prev, signature, breaks, time.time()),
            )
            self._conn.commit()

    # How many containers each plan may run at once. THE ONE THING WE ENFORCE,
    # and the only thing that can be enforced: it is decided here, on our side,
    # when a lease is requested. Everything the container reports about itself —
    # values, requests, rate — is produced on the customer's hardware and can
    # say anything, so none of it can be a plan boundary.
    #
    # Instances are also the honest proxy for scale: one container handles a
    # given load, and more traffic needs more of them.
    PLAN_INSTANCES = {"start": 1, "work": 4, "industrial": 12, "enterprise": 100}
    # ПОТОЛОК ПРОЦЕССОВ НА КОНТЕЙНЕР — СТРОКА ТАРИФА ДЛЯ ЭКРАНА, НЕ ЗАМОК.
    #
    # Он был замком, и замок не работал: `instance_id` приходит из переменной
    # окружения, поэтому пятьдесят контейнеров с одним значением читались как
    # один инстанс (E7), а поколение из 32 ключей переоткрывалось каждые
    # T_alive (Б26quater). Теперь потолок принуждается фенсингом на ёмкости, а
    # это число печатается рядом с «воркеров слышно N»: «тариф рассчитан на 32».
    # Ни одно решение его не читает.
    PROCESSES_PER_INSTANCE = 32

    # ─────────────────────────────────────────────────────────────────────────
    # ЧЕГО ЗДЕСЬ БОЛЬШЕ НЕТ, И КАКОЙ ДЕФЕКТ КАЖДОЕ ЧИСЛО ЛЕЧИЛО. Удалить таймер
    # молча — потерять память шести заходов, поэтому инвентарь стоит в коде, а
    # не только в ТЗ (§5).
    #
    #   `ALIVE_SECONDS` (600 с), `LIVENESS_SINCE`, `HEARTBEAT_PROOF_SECONDS`
    #       лечили Б26: труп держал слот 16–24 ч, а старый движок без пульса не
    #       мог быть судим по молчанию. ЛЕЧИТСЯ ТЕПЕРЬ: занятость не решается
    #       вовсе. Вернувшаяся установка берёт СВОЙ слот по свидетельству
    #       личности, чужая — по РАНЖИРОВАНИЮ («слышали раньше всех»), а
    #       ранжирование ничего не утверждает о мире и потому не бывает ложным.
    #   `RELEASE_ECHO_SECONDS` (30 с)
    #       лечило Б26/Б26quinquies: отпустивший процесс продолжал обслуживать,
    #       и его надо было «заслушать». ЛЕЧИТСЯ: `/v1/release` не читает ни
    #       одно решение; обслуживать после ухода — значит покупать при чужом
    #       эпохе, а это `fenced`.
    #   `RELEASE_BUDGET_PER_HOUR`, `TURNOVER_WINDOW_SECONDS`
    #       лечили Б26bis/ter: бюджет перевыдач был единственным ограничителем
    #       темпа карусели. ЛЕЧИТСЯ: карусель — это поколения на ОДНОМ слоте, из
    #       которых покупает ровно одно; умножения нет, поэтому ограничивать
    #       темп не нужно — а бюджет всё равно не ограничивал остаток («молчащее
    #       кольцо не ограничено», Б26sexies).
    #
    # Чего НЕ удалено и почему: TTL 24 ч и grace 48 ч остаются — они про бандл и
    # про НАШУ аварию, а не про то, жив ли контейнер.
    # ─────────────────────────────────────────────────────────────────────────

    # Mirrors billing/management/commands/seed_plans.py. Two places, because
    # the licensing server must not depend on the storefront — but they are
    # checked against each other by test_storefront.py.

    # СКОЛЬКО ЗАПРОСОВ ДАЁТ ОДНА АРЕНДА. Гранулярность — компромисс: мелкий
    # грант точнее считает и чаще ходит к нам, крупный наоборот. Порядок «час
    # ожидаемого трафика» выбран так, чтобы клиент, остановившийся посреди
    # гранта, переплатил незначительно — гранты не возвращаются, и это цена
    # того, что число неподделываемо.
    # СКОЛЬКО СЕКУНД СОБСТВЕННОГО ТРАФИКА КЛИЕНТА СОСТАВЛЯЮТ КВАНТ И РЕЗЕРВ.
    #
    # Погрешность счёта при таком выборе равна `(τ_Q + τ_R) / период` и НЕ
    # зависит ни от объёма, ни от числа воркеров, ни от тарифа. При 300 с и 6 ч
    # это 0.84% в худшем случае — когда цепь отчётов порвана и счёт идёт по
    # потолку, — и РОВНО НОЛЬ, когда отчёты доходят.
    #
    # Квант вносит в эту цифру 23 миллионных, резерв — почти всё. Поэтому квант
    # выгодно делать КРУПНЫМ (в пять раз меньше обращений при той же точности),
    # а торговаться стоит за часы резерва: каждый час страховки от НАШЕГО
    # простоя стоит 0.14% худшей погрешности.
    METER_TARGET_SECONDS = int(os.environ.get("PSEUDEX_METER_TARGET_SECONDS", "300"))
    # СОРОК ВОСЕМЬ ЧАСОВ, А НЕ ШЕСТЬ, И ЦЕНА НАЗВАНА ЧИСЛОМ.
    #
    # Резерв — это страховка от НАШЕГО простоя, и он же НАШ долг клиенту: пока
    # связи нет, счёт идёт по потолку `granted`, потому что отчёта нет. Отсюда
    # прямо следует, что каждый час страховки стоит `1/720` худшей погрешности
    # за месячный период (комментарий выше считает эту величину):
    #
    #     6 ч → 0.84%      24 ч → 3.34%      48 ч → 6.68%
    #
    # Шесть часов были выбраны, когда отчёт уходил раз в ВОСЕМЬ часов: тогда
    # любая погрешность была теоретической, потому что к моменту отчёта окно
    # уже закрывалось. Теперь отчёт уходит раз в ДВЕ МИНУТЫ (`_report_usage`),
    # и 6.68% остаются ТОЛЬКО у того, кто потратил и не отчитался НИКОГДА —
    # то есть у контейнера, который умер офлайн и не вернулся. Вернувшийся
    # отчитывается накопительно, и отчёт УМЕНЬШАЕТ начисление до фактического.
    #
    # Сорок восемь часов выбраны по обещанию на лендинге и по делу: наша
    # авария не должна останавливать прод клиента, а «двое суток» — тот срок,
    # за который мы обязаны поднять свой сервис.
    RESERVE_SECONDS = int(os.environ.get("PSEUDEX_RESERVE_SECONDS", str(48 * 3600)))
    # Порог предвыборки внутри РЕЗЕРВА: движок идёт за следующим квантом, пока
    # страховка ещё цела. Резерв — страховка, а не оборотный капитал.
    PREFETCH_FRACTION = 0.25

    # Нижние и верхние границы кванта и резерва по тарифам. Нижняя нужна, чтобы
    # почти простаивающий процесс не ходил к нам за единицами; верхняя — чтобы
    # всплеск не выдал вперёд месячный объём.
    QUANTUM_BOUNDS = {"start": (200, 2_000), "work": (200, 10_000),
                      "industrial": (500, 40_000), "enterprise": (500, 100_000)}
    # ПОТОЛКИ НЕ ПОДНИМАЛИ, КРОМЕ ENTERPRISE, И ЭТО ПОСЧИТАНО. Потолок
    # начинает резать при `RESERVE_MAX / 48 ч` собственного темпа клиента:
    #
    #     start       417/ч   — это 30x его проектного темпа (14/ч)
    #     work      2 083/ч   — 15x (139/ч)
    #     industrial 8 333/ч  —  6x (1 389/ч)
    #     enterprise 41 667/ч —  0.3x (138 889/ч)  ← РЕЗАЛ БЫ на 14-м часу
    #
    # Первые три трогать не за чем: поднять их значило бы увеличить
    # неоплаченный долг без единого клиента, которому это нужно. Enterprise —
    # единственный, где потолок противоречил обещанию, и он поднят ровно до
    # `проектный темп × 48 ч`.
    RESERVE_MAX = {"start": 20_000, "work": 100_000,
                   "industrial": 400_000, "enterprise": 8_000_000}

    PLAN_GRANT = {"start": 5_000, "work": 25_000, "industrial": 100_000,
                  "enterprise": 500_000}

    _PLAN_FIELDS = ("max_instances", "processes_per_instance", "grant_size",
                    "quantum_min", "quantum_max", "reserve_max")

    def plan_row(self, plan: str) -> dict[str, object] | None:
        """Числа тарифа, или `None`, если такого тарифа нет.

        ЕДИНСТВЕННЫЙ ЧИТАТЕЛЬ ТАБЛИЦЫ, и все, кому нужен тариф, идут через него.
        Кеша здесь нет НАМЕРЕННО: кеш вернул бы ровно ту болезнь, ради которой
        таблица заводилась, — правка перестала бы действовать до перезапуска.
        Цена нулевая: чтение по первичному ключу, и зовут его на аренде и раз в
        225 секунд на процесс, а не на пути запроса.
        """
        row = self._fetchone(
            "SELECT code, max_instances, processes_per_instance, grant_size, "
            "quantum_min, quantum_max, reserve_max, updated_at, updated_by "
            "FROM plans WHERE code=?", (plan,))
        if row is None:
            return None
        return {"code": row[0], "max_instances": int(row[1] or 0),
                "processes_per_instance": int(row[2] or 0),
                "grant_size": int(row[3] or 0), "quantum_min": int(row[4] or 0),
                "quantum_max": int(row[5] or 0), "reserve_max": int(row[6] or 0),
                "updated_at": row[7],
                # Пустой `updated_by` — строка как её посеяли. Непустой — здесь
                # правили руками, и константа в коде больше не описывает
                # реальность. Это единственное, что отличает одно от другого
                # снаружи, поэтому оно и отдаётся.
                "source": "edited" if (row[8] or "") else "seed",
                "updated_by": row[8] or ""}

    def plans(self) -> list[dict[str, object]]:
        """Все тарифы, в порядке потолка инстансов — от младшего к старшему."""
        rows = self._fetchall("SELECT code FROM plans ORDER BY max_instances", ())
        return [row for row in (self.plan_row(r[0]) for r in rows) if row]

    def set_plan(self, code: str, values: dict[str, object], actor: str) -> dict:
        """Создать или поправить тариф. Возвращает строку, какой она стала.

        `actor` обязателен и пишется в `updated_by`: строка, которую правили,
        обязана отличаться от посеянной, иначе `source` — выдумка. Роль та же,
        что у `actor` в журнале раскрытий: запись о том, кто это сделал.
        """
        current = self.plan_row(code) or {field: 0 for field in self._PLAN_FIELDS}
        merged = {field: int(values.get(field, current.get(field, 0)) or 0)
                  for field in self._PLAN_FIELDS}
        # ПРОВЕРЯЕТСЯ ДО ЗАПИСИ И НА СЛИТОЙ СТРОКЕ, а не на теле запроса.
        #
        # До записи — потому что иначе несогласованная строка успевает лечь на
        # диск и остаётся там после отказа: вызывающий видит 400 и считает, что
        # ничего не произошло. На слитой — потому что править можно одно поле из
        # пары, и тогда противоречие рождается сложением нового значения с тем,
        # что уже лежало, а в теле запроса его не видно вовсе.
        #
        # `issue_quantum` зажимает квант между этими двумя, так что перевёрнутая
        # пара молча делает потолок ниже пола.
        # КАЖДОЕ ПОЛЕ ОБЯЗАНО БЫТЬ ПОЛОЖИТЕЛЬНЫМ, И ЭТО ПРО СОЗДАНИЕ НОВОГО
        # ТАРИФА, А НЕ ПРО ПРАВКУ СУЩЕСТВУЮЩЕГО.
        #
        # `current` для неизвестного кода — нули, поэтому запрос вида
        # `{"code": "gold", "max_instances": 4}` создавал строку, где всё
        # остальное ноль. Дальше `known_plan` такой тариф признаёт, а
        # `ensure_slots` заводит НОЛЬ слотов, `admit_generation` поднимает
        # «plan has no slots to hand out», и клиент не поднимается вовсе;
        # нулевой `quantum_max` делает то же с ёмкостью.
        # Проверка на `quantum_min > quantum_max` на паре 0/0 не срабатывает, а
        # диапазонная проверка в ручке видит только присланные поля.
        zeroed = sorted(field for field in self._PLAN_FIELDS if merged[field] < 1)
        if zeroed:
            raise ValueError(
                f"plan {code} would have non-positive {', '.join(zeroed)}; "
                "a new plan must name every field")
        if merged["quantum_min"] > merged["quantum_max"]:
            raise ValueError(
                f"quantum_min {merged['quantum_min']} above quantum_max "
                f"{merged['quantum_max']} for plan {code}")
        with self._lock:
            self._conn.execute(
                "INSERT INTO plans (code, max_instances, processes_per_instance, "
                "grant_size, quantum_min, quantum_max, reserve_max, updated_at, "
                "updated_by) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(code) DO UPDATE SET "
                "max_instances=excluded.max_instances, "
                "processes_per_instance=excluded.processes_per_instance, "
                "grant_size=excluded.grant_size, quantum_min=excluded.quantum_min, "
                "quantum_max=excluded.quantum_max, reserve_max=excluded.reserve_max, "
                "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                (code, merged["max_instances"], merged["processes_per_instance"],
                 merged["grant_size"], merged["quantum_min"], merged["quantum_max"],
                 merged["reserve_max"], time.time(), actor),
            )
            self._conn.commit()
        return self.plan_row(code) or {}

    def known_plan(self, plan: str) -> bool:
        """Есть ли такой тариф вообще.

        СПРАШИВАЕТСЯ ПРИ ВЫПУСКЕ КЛЮЧА, ПОТОМУ ЧТО ДАЛЬШЕ КАЖДЫЙ LOOKUP МОЛЧА
        ПОДСТАВЛЯЕТ УМОЛЧАНИЕ. `instances_allowed` откатывался на 1, `grant_size`
        на 5 000, границы кванта и резерва — на значения «старта»: тариф, которого
        нет, не ломался, он тихо становился самым младшим. `/admin/issue`
        подставлял `"standard"`, которого нет нигде, поэтому ключ без явного
        тарифа был невидимым «стартом» независимо от того, что купили.
        """
        return self.plan_row(plan) is not None

    def known_plans(self) -> list[str]:
        """Тарифы, которые есть, — чтобы отказ называл допустимое, а не только
        недопустимое."""
        return sorted(row["code"] for row in self.plans())

    def grant_size(self, plan: str) -> int:
        row = self.plan_row(plan)
        return row["grant_size"] if row else 5_000

    def record_grant(self, org_id: str, pubkey: str, size: int) -> None:
        """ВЫДАННОЕ КОПИТСЯ У НАС И НЕ ЗАВИСИТ НИ ОТ ЧЕГО, ЧТО ПРИШЛО СНАРУЖИ.

        Это и есть счёт: клиент не может занизить число, которое мы записали
        сами, а перестать просить он может только перестав обслуживать.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO grants (org_id, pubkey, granted, issued_at) "
                "VALUES (?,?,?,?) ON CONFLICT(org_id, pubkey) DO UPDATE SET "
                "granted=grants.granted+excluded.granted, issued_at=excluded.issued_at",
                (org_id, pubkey, size, time.time()),
            )
            self._conn.commit()

    def meter_row(self, org_id: str, pubkey: str) -> dict[str, object]:
        row = self._fetchone(
            "SELECT quantum_seq, quantum_size, reserve, granted, acked, acked_at, "
            "unacked_quanta, ack_regressions, prefetch_at "
            "FROM meter WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        if row is None:
            return {"quantum_seq": 0, "quantum_size": 0, "reserve": 0,
                    "granted": 0, "acked": 0, "acked_at": 0.0,
                    "unacked_quanta": 0, "ack_regressions": 0, "prefetch_at": 0}
        return {"quantum_seq": int(row[0] or 0), "quantum_size": int(row[1] or 0),
                "reserve": int(row[2] or 0), "granted": int(row[3] or 0),
                "acked": int(row[4] or 0), "acked_at": float(row[5] or 0.0),
                "unacked_quanta": int(row[6] or 0),
                "ack_regressions": int(row[7] or 0),
                "prefetch_at": int(row[8] or 0)}

    def record_tripwire(self, org_id: str, event: dict) -> None:
        """Record a reported memory-read attempt on an org's engine. Counts/attribution
        only — the reader's identity, never the memory contents."""
        def _int(value: object) -> int:
            # NB: not `value or -1` — a root reader has uid 0, which is falsy, so that
            # idiom silently rewrote the single most important attribution (uid=0) to -1.
            try:
                return int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return -1
        with self._lock:
            self._conn.execute(
                "INSERT INTO tripwire (org_id, ts, method, reader_uid, reader_pid, "
                "reader_comm, reader_exe, reader_cmdline) VALUES (?,?,?,?,?,?,?,?)",
                (org_id, time.time(), str(event.get("method", ""))[:32],
                 _int(event.get("reader_uid")), _int(event.get("reader_pid")),
                 str(event.get("reader_comm", ""))[:128], str(event.get("reader_exe", ""))[:512],
                 str(event.get("reader_cmdline", ""))[:1024]))
            self._conn.commit()

    def tripwire_events(self, org_id: str = "", since: float = 0.0, limit: int = 200) -> list[dict]:
        """Reported memory-read attempts, newest first — the fleet surface for 'who tried
        to read the engine'. Filter by org and time window."""
        where = "ts >= ?"
        params: tuple = (since,)
        if org_id:
            where += " AND org_id = ?"
            params = (since, org_id)
        rows = self._fetchall(
            f"SELECT org_id, ts, method, reader_uid, reader_pid, reader_comm, reader_exe, "
            f"reader_cmdline FROM tripwire WHERE {where} ORDER BY ts DESC LIMIT ?",
            params + (int(limit),))
        return [{"org_id": r[0], "ts": r[1], "method": r[2], "reader_uid": r[3],
                 "reader_pid": r[4], "reader_comm": r[5], "reader_exe": r[6],
                 "reader_cmdline": r[7]} for r in rows]

    def metering_anomalies(self, min_unacked: int = 10, min_regressions: int = 1,
                           active_within_seconds: float = 3600.0,
                           window_seconds: float = 86400.0) -> list[dict]:
        """Организации, чей учёт выглядит как молчащий, делящий ключ или
        крутящий кольцо движок, — для разбора оператором (WS-6/M2).

        НАБЛЮДЕНИЕ СЧИТАЕТ ТЕМИ ЖЕ ЕДИНИЦАМИ, ЧТО И ЛЕДЖЕР — поколениями и
        эпохами. Урок Б26bis: наблюдение и ограничитель, разошедшиеся в
        единицах, — это два ответа на один вопрос, и дороже всего они стоят
        тогда, когда расходятся молча.

        Причины и чем каждая заменила прежнюю:

          * `unacked_quanta`, `ack_regressions` — без изменений;
          * `epochs_unacked` — поколения за сутки, ни разу не подтвердившие
            расход. ЗАМЕНЯЕТ `silent_reclaims` («сколько раз слот перешёл к
            новому контейнеру, потому что прежний замолчал»): перевыдач больше
            нет как события, а кольцо «аренда → молчание → аренда» видно здесь
            числом оборотов;
          * `slot_contention` — перезаявки слота поколением, которое уже было
            отфенсено. Честный движок делает одну и не чаще раза в час; два
            живых контейнера на одном слоте перезаявляют друг друга постоянно;
          * `installations_per_generation` — сколько РАЗНЫХ установок назвали
            одно и то же имя старта: контейнеры, поделившие `PSEUDEX_START_ID`.
            ЗАМЕНЯЕТ `installations_per_slot` («установок на слот»), который
            считал честную раскатку на `emptyDir` — новый том на том же слоте —
            клоном и красил ею каждый деплой.

        `release_echoes` удалена вместе с механизмом, который её считал: эхо
        ухода лечило «покупку ёмкости отпущенным ключом», а сегодня покупка
        мимо текущего эпоха невозможна по построению.
        """
        now = time.time()
        cutoff = now - active_within_seconds
        since = now - window_seconds
        rows = self._fetchall(
            "SELECT org_id, COALESCE(SUM(unacked_quanta),0), COALESCE(SUM(ack_regressions),0), "
            "COALESCE(SUM(granted),0), COALESCE(SUM(acked),0), COUNT(*) "
            "FROM meter WHERE updated_at >= ? GROUP BY org_id",
            (cutoff,))
        metered = {str(row[0]): row for row in rows}
        # ОРГАНИЗАЦИЯ ПОПАДАЕТ СЮДА, ДАЖЕ ЕСЛИ ЕЁ СЧЁТЧИК МОЛЧИТ. Ровно этот
        # случай и интересен: поколения крутятся, ёмкость не подтверждается, и
        # по одному только `meter` клиента не видно вовсе.
        churn = {str(row[0]): (int(row[1] or 0), int(row[2] or 0))
                 for row in self._fetchall(
                     "SELECT org_id, COUNT(*), COALESCE(SUM(claims-1),0) "
                     "FROM generations WHERE first_lease_at>=? GROUP BY org_id",
                     (since,))}
        out: list[dict] = []
        for org_id in sorted(set(metered) | set(churn)):
            row = metered.get(org_id)
            unacked = int(row[1] or 0) if row else 0
            regressions = int(row[2] or 0) if row else 0
            granted = int(row[3] or 0) if row else 0
            acked = int(row[4] or 0) if row else 0
            procs = int(row[5] or 0) if row else 0
            generations, contention = churn.get(org_id, (0, 0))
            streak = self._reclaim_streak(org_id, since)
            silent_epochs = self._epochs_unacked(org_id, since)
            installations = self._installations_per_generation(org_id, since)
            allowed = self.instances_allowed(self.org_plan(org_id))
            reasons = []
            if unacked >= min_unacked:
                reasons.append(f"silent: {unacked} quanta served with no verified report")
            if regressions >= min_regressions:
                reasons.append(f"{regressions} usage regression(s) — one key, two engines or replay")
            # ПОРОГ ТОТ ЖЕ, ЧТО У ПРЕЖНЕГО `silent_reclaims`: больше запусков
            # без единого подтверждения, чем контейнеров по тарифу в сутки, —
            # это либо кольцо, либо клиент, у которого контейнеры падают и он
            # об этом не знает. И то и другое мы обязаны увидеть первыми.
            if silent_epochs > allowed:
                reasons.append(f"{silent_epochs} generation(s) in 24 h acknowledged "
                               f"nothing on a plan of {allowed} — a ring or a crash loop")
            if streak >= self.RECLAIM_STREAK_ANOMALY:
                reasons.append(f"one generation re-claimed its slot {streak} time(s) "
                               f"in 24 h ({contention} re-claims in all) — an honest "
                               f"engine comes back once per fencing")
            if installations > 1:
                reasons.append(f"{installations} different installations declared one "
                               f"PSEUDEX_START_ID in 24 h — containers sharing a start "
                               f"identity; one container has one installation, however "
                               f"many workers it runs")
            if not reasons:
                continue
            out.append({"org_id": org_id, "unacked_quanta": unacked,
                        "ack_regressions": regressions, "granted": granted,
                        "acked": acked, "processes": procs,
                        "generations_24h": generations,
                        "epochs_unacked": silent_epochs,
                        "slot_contention": contention,
                        "reclaim_streak": streak,
                        "installations_per_generation": installations,
                        "instances_allowed": allowed,
                        "reasons": reasons})
        out.sort(key=lambda a: a["unacked_quanta"] + a["ack_regressions"]
                 + a["epochs_unacked"] + a["slot_contention"], reverse=True)
        return out

    def _installations_per_generation(self, org_id: str, since: float) -> int:
        """Сколько РАЗНЫХ установок назвали ОДНО И ТО ЖЕ имя старта за окно.

        ПО ЗАЯВЛЕННОМУ ИМЕНИ, А НЕ ПО СЛОТУ, И ЭТО ДВЕ РАЗНЫЕ ПРАВКИ В ОДНОЙ.

        Первая — точность. Считалось «сколько установок говорили за один СЛОТ»,
        и в это число попадала честная раскатка: под на `emptyDir` — это новый
        том, то есть новая установка на том же слоте, и ТЗ §4.4 называет такую
        раскатку штатной. Клиент, катящийся раз в день, попадал в аномалии
        каждый день с формулировкой про клон тома. Аномалия, срабатывающая на
        поведении, которое ТЗ объявило нормальным, — это шум, а не наблюдение.

        Вторая — след. Общий `PSEUDEX_START_ID` теперь ломается о
        `_generation_name`: чужая установка получает СВОЁ имя поколения и
        фенсится как всякий сосед. Но остаток есть — контейнер, назвавший и
        чужой `start_id`, и чужой `installation_id`, неотличим от восьмого
        воркера того же старта, — и §2 Т1 обещает, что каждый обход виден
        числом. Видно его ровно здесь: у честного контейнера на одно
        ЗАЯВЛЕННОЕ имя приходится ровно одна установка, сколько бы воркеров он
        ни поднял и сколько бы раз ни продлевался.

        ВЫПУЩЕННЫЙ ФЛОТ ИСКЛЮЧЁН. Старый `entrypoint.sh` чеканил
        `PSEUDEX_INSTANCE_ID` случайно НА КАЖДЫЙ СТАРТ, поэтому его установка
        не идентифицирует ничего, и честный перезапуск выглядел бы как вторая
        установка. Такие поколения носят префикс `legacy:` — по нему и
        отсекаются.
        """
        rows = self._fetchall(
            "SELECT declared_start_id, COUNT(DISTINCT installation_id) "
            "FROM generations WHERE org_id=? AND last_lease_at>=? "
            "AND COALESCE(declared_start_id,'')<>'' "
            "AND COALESCE(installation_id,'')<>'' "
            "AND declared_start_id NOT LIKE 'legacy:%' "
            "GROUP BY declared_start_id", (org_id, since))
        return max((int(row[1] or 0) for row in rows), default=0)

    # ДВЕ ПЕРЕЗАЯВКИ ОДНОГО ПОКОЛЕНИЯ — УЖЕ НЕ РАСКАТКА. Честный движок
    # возвращается за слотом один раз на фенсинг (§3.6); поколение, сделавшее
    # это дважды за сутки, либо делит слот с живым соседом, либо крутит кольцо.
    RECLAIM_STREAK_ANOMALY = 2

    MIN_METER_INTERVAL_SECONDS = 1.0

    def metered_too_recently(self, org_id: str, pubkey: str, now: float) -> bool:
        """Просил ли этот процесс квант меньше секунды назад — И ЗАПОМНИТЬ, ЧТО
        ПРОСИЛ. Один вопрос, одна запись: разделить их значило бы завести два
        места, где решается одно.

        СЧИТАЮТСЯ ПОПЫТКИ, А НЕ ВЫДАЧИ, и это вся суть правки. Здесь читался
        `meter.updated_at`, а его двигает только УСПЕШНАЯ покупка: отказ
        `fenced` до `issue_quantum` не доходит и колонку не трогает, поэтому
        потолок резал кого угодно, кроме единственного трафика, ради которого
        заведён. §3.4 ТЗ прямо закладывает, что отфенсенный ВЫПУЩЕННЫЙ движок
        повторяет `/v1/meter` каждый тик до продления — до восьми часов, — и §7
        переводит в это состояние весь флот на время миграции; замер показал
        сорок отказов подряд за 0.04 с, каждый под глобальным локом хранилища.

        В ПАМЯТИ, А НЕ В ТАБЛИЦЕ: это наша полоса, а не свойство счёта, и
        пережившая рестарт отметка не стоит записи на диск на каждый запрос.
        Решает ОТМЕТКА ВРЕМЕНИ, а не ведро: интервал обязан быть ровно секундой,
        иначе честный клиент ловит 429 там, где пришёл через 1.05 с. Вёдра
        нужны только чтобы чистка стоила одну ссылку, а память была ограничена
        ключами последних двух секунд.
        """
        bucket = int(now // self.MIN_METER_INTERVAL_SECONDS)
        with self._lock:
            if bucket != self._meter_bucket:
                self._meter_seen_prev = (self._meter_seen
                                         if bucket == self._meter_bucket + 1
                                         else {})
                self._meter_seen = {}
                self._meter_bucket = bucket
            mark = (org_id, pubkey)
            last = self._meter_seen.get(mark, self._meter_seen_prev.get(mark))
            if last is not None and now - last < self.MIN_METER_INTERVAL_SECONDS:
                return True
            self._meter_seen[mark] = now
            return False

    def _holder_pressure(self, org_id: str) -> tuple[int, int]:
        """Сколько слотов ДЕРЖАТ против того, сколько допускает тариф. Пара
        чисел, которыми проверяется совет «остановите один контейнер»: без них
        это совет на веру, а совет на веру и был дефектом Б26.

        Верхняя граница, а не «сколько живо»: держателем числится и то, что уже
        умерло, и сказать иначе нельзя ни при каком механизме (§1.2). Поэтому
        число едет со словом «слышно», а не «работает».

        СЧИТАЮТСЯ И ТЕ, КОГО СМЕНА ТАРИФА УЖЕ СНЯЛА СО СЛОТА. Иначе число
        опровергало бы собственный совет: понижение с четырёх до одного
        очищает три слота, и «слышно 1» рядом с «остановите один контейнер»
        — это две строки, спорящие друг с другом в одном абзаце.
        """
        held = self._fetchone(
            "SELECT COUNT(*) FROM slots WHERE org_id=? "
            "AND COALESCE(holder_start_id,'')<>''", (org_id,))
        displaced = self._fetchone(
            "SELECT COUNT(DISTINCT installation_id) FROM generations "
            "WHERE org_id=? AND fenced_by='plan' AND COALESCE(installation_id,'')<>''",
            (org_id,))
        return ((int(held[0] or 0) if held else 0)
                + (int(displaced[0] or 0) if displaced else 0),
                self.instances_allowed(self.org_plan(org_id)))

    def _fence_detail(self, org_id: str, slot: dict[str, object],
                      standing: dict[str, object], now: float) -> str:
        """Текст, который выпущенный движок печатает ДОСЛОВНО (`service.py`,
        `proxy.py` выводят `detail`). Поэтому он обязан называть событие, а не
        запрет, и не советовать останавливать то, чего может не быть.

        Отдельно от статического `REMEDIES` клиента: тот едет с образом и здесь
        неисправим, а эта строка доезжает до старого флота без релиза движка.
        """
        if slot["retired"]:
            # ЧИСЛА, А НЕ СОВЕТ НА ВЕРУ. Стоял текст «освободите лишний
            # контейнер», и он повторял дефект Б26 через тариф: контейнер,
            # стоявший на слоте 3, выводился понижением по НОМЕРУ, хотя был
            # единственным, — клиенту советовали остановить то, чего нет.
            # `ensure_slots` теперь выводит пустые слоты раньше занятых,
            # поэтому сюда попадает только держатель, который действительно
            # лишний; текст называет оба числа, чтобы совет можно было
            # проверить, а не принять на слово.
            held, allowed = self._holder_pressure(org_id)
            return (f"тариф допускает {allowed} контейнер(ов), а слышно {held}: "
                    f"слот {slot['slot_no']} выведен сменой тарифа. Этот запуск "
                    f"доработает на уже купленной ёмкости и остановится сам. "
                    f"Остановите один контейнер или вернитесь на прежний тариф: "
                    f"https://pseudex.ru/app/")
        # ПУСТОЙ СЛОТ НЕ НАЗЫВАЕТ ДЕРЖАТЕЛЯ — НИ ПО ОДНОЙ ПРИЧИНЕ ФЕНСИНГА.
        # Сказать «место занял более новый запуск» там, где держателя вообще
        # нет, — это тот же дефект, что «остановите лишний контейнер», которого
        # нет (Б26): совет, который опровергается собственным экраном клиента.
        # Проверка стояла только в ветке поддержки, и понижение тарифа с
        # возвратом обратно (эпох поднят, держатель снят, `retired` уже снят)
        # проваливалось в общий текст: клиенту называли поколение и «слышали
        # столько-то назад» про ПУСТОЙ слот.
        if not slot["holder_start_id"]:
            if slot["fenced_by"] == "admin":
                return (f"слот {slot['slot_no']} освободила поддержка по "
                        f"обращению: этот запуск числился на нём как работающий. "
                        f"Он доработает на уже купленной ёмкости и остановится "
                        f"сам; чтобы занять слот снова, перезапустите контейнер.")
            return (f"слот {slot['slot_no']} свободен, но поколение на нём уже "
                    f"сменилось ({slot['epoch']} против {standing['epoch']} у этого "
                    f"запуска) — место освободила смена тарифа или поддержка. "
                    f"Этот запуск доработает на уже купленной ёмкости и "
                    f"остановится сам; чтобы занять слот снова, перезапустите "
                    f"контейнер.")
        since = ago(max(0.0, now - float(slot["last_heard_at"] or now)))
        return (f"место этого запуска занял более новый запуск того же тарифа "
                f"(слот {slot['slot_no']}, поколение {slot['epoch']}, слышали "
                f"{since} назад); этот запуск работает на поколении "
                f"{standing['epoch']}. Он доработает на уже купленной ёмкости и "
                f"остановится сам. Если это переразвёртывание — ничего делать не "
                f"нужно. Если контейнеров действительно больше, чем по тарифу, — "
                f"остановите один или смените тариф: https://pseudex.ru/app/")

    def meter_if_allowed(self, org_id: str, pubkey: str, plan: str,
                         acked: int | None, ack_slot: int | None,
                         ack_epoch: int | None, window_seconds: float,
                         now: float) -> tuple[dict[str, int] | None, dict[str, object]]:
        """ФЕНСИНГ: старший эпох отказывает младшему в НОВОЙ ёмкости.

        Это секвенсер Chubby, у которого «recipient server» — мы сами. Нужное
        для него предусловие («проверять обязан сам ресурс») у плавающих
        лицензий недостижимо — там ресурс чужой бинарник, поэтому вся категория
        живёт на таймаутах. У нас право обслуживать — непрерывно выдаваемое
        нами разрешение, и это единственная точка, где фенсинг вообще возможен.

        ОТКАЗ ТОЛЬКО В НОВОЙ ЁМКОСТИ. Уже выданное не отзывается: отфенсенное
        поколение доцеживает свою полосу и встаёт само, обычной проверкой
        `has_capacity()`. Отзывать выданное значило бы гасить процесс,
        оплаченный остаток которого ещё не израсходован, — это Б30, и именно
        поэтому код отказа взят вне `_ANSWER_CODES` выпущенных движков.

        Проверка идёт в одной секции с выдачей: между отдельным предикатом и
        отдельной записью лок отпускается, и N одновременных покупок все видят
        себя старшими.
        """
        with self._lock:
            binding = self.binding_of(org_id, pubkey, now - window_seconds)
            if binding is None:
                # НИ ОДНОЙ ПРИВЯЗАННОЙ АРЕНДЫ В ОКНЕ — НИ ОДНОГО БАНДЛА.
                # Маскировать такому ключу нечем, квант ему бесполезен, и
                # заводить здесь вторую границу значило бы судить по молчанию
                # ровно там, где сказать нечего. Так же вёл себя и прежний
                # быстрый путь; логируем, отказа не заводим.
                _log.info("capacity for org=%s pubkey=%s without a bound lease",
                          org_id, pubkey[:12])
                return self.issue_quantum(org_id, pubkey, plan, acked, None, None,
                                          now), {}
            # СУДИТ ПОКОЛЕНИЕ, А НЕ СТРОКА АРЕНДЫ ЭТОГО КЛЮЧА.
            #
            # Единица потолка — покупающее ПОКОЛЕНИЕ (§3.3), и его положение мы
            # держим в `generations`, а не в строке аренды каждого воркера.
            # Пока сверялся эпох СТРОКИ, перезаявка одного воркера фенсила его
            # же братьев: `lease_generation` поднимает эпох всего поколения,
            # а привязки остальных воркеров остаются на прежнем номере — и
            # контейнер, ДЕРЖАЩИЙ слот, темнел на всех воркерах, кроме
            # перезаявившего. Отказ при этом дословно говорил «место занял
            # более новый запуск», называя тот же самый старт.
            standing = self._generation_standing(org_id, binding["start_id"])
            if standing is None:
                # Привязанная аренда без строки поколения — наша испорченная
                # запись, а не состояние клиента. Судить по ней нечем, и
                # молча выдать квант значило бы завести вторую, невидимую
                # ветку допуска.
                raise ValueError(f"lease of {pubkey[:12]} names a generation "
                                 f"{binding['start_id']!r} that has no row")
            slot = self.slot_state(org_id, standing["slot_no"])
            if slot is None:
                return self.issue_quantum(org_id, pubkey, plan, acked,
                                          standing["slot_no"], standing["epoch"],
                                          now), {}
            # ТРИ ПРИЧИНЫ, ОДИН ОТВЕТ. Эпох поколения ниже текущего — поколение
            # вытеснено; слот выведен тарифом — то же самое другой дверью; тег
            # в `ack` не сходится с АРЕНДОЙ этого ключа — ключ покупает не за
            # то, за что арендовал (в том числе «эпох новее»: такого мы не
            # чеканили, значит его назвал клиент).
            mismatched = ((ack_slot is not None and ack_slot != binding["slot_no"])
                          or (ack_epoch is not None and ack_epoch != binding["epoch"]))
            if standing["epoch"] < slot["epoch"] or slot["retired"] or mismatched:
                if self._never_granted(org_id, pubkey):
                    # ПЕРВЫЙ КВАНТ ПРОЦЕССА ПРОДАЁТСЯ ВСЕГДА, ДАЖЕ ОТФЕНСЕННОМУ.
                    #
                    # Выпущенный движок покупает его ВНУТРИ `acquire()`
                    # (`license.py:950`), а всё, что оттуда вылетело, — это три
                    # попытки и `bundle_unavailable`: контейнер не поднимается
                    # вовсе. Значит вердикт «ты отфенсен», прилетевший в окно
                    # между арендой и первой покупкой, запирал бы клиента ровно
                    # так же, как заходы четвёртый, пятый и шестой, — только
                    # новой дверью. Окно не теоретическое: сосед, перезаявивший
                    # слот между этими двумя запросами, открывает его при каждой
                    # раскатке K8s и при каждом старте второго контейнера.
                    #
                    # ЧЕГО ЭТО СТОИТ: `Q_min` тарифа на процесс на аренду — ровно
                    # та полоса, которую §3bis.2 уже назвала остатком и которую
                    # ни фенсинг, ни бюджет перевыдач не ограничивали и до этого
                    # («молчащее кольцо не ограничено»). Новой ёмкости не
                    # появляется: поколение, отфенсенное ПОСЛЕ первой покупки,
                    # больше не купит ничего, а поколение, которое слот
                    # перезаявило, и так было бы старшим.
                    _log.warning("first quantum sold past a fence for org=%s "
                                 "pubkey=%s slot=%s epoch=%s (current %s): a cold "
                                 "start must not be locked out",
                                 org_id, pubkey[:12], binding["slot_no"],
                                 standing["epoch"], slot["epoch"])
                    return self.issue_quantum(org_id, pubkey, plan, acked,
                                              standing["slot_no"],
                                              standing["epoch"], now), {}
                refusal: dict[str, object] = {
                    "error": FENCED,
                    # ТЕКСТ — ПРО ПОКОЛЕНИЕ, ПОЛЯ ОТВЕТА — ПРО ЭТОТ КЛЮЧ.
                    # Клиент сверяет `epoch` со своей арендой, чтобы понять,
                    # сменилось ли поколение; человек читает `detail`, и там
                    # номер слота обязан совпадать с тем, который мы судили.
                    "detail": self._fence_detail(org_id, slot, standing, now),
                    "slot_no": binding["slot_no"],
                    "epoch": binding["epoch"],
                    "current_epoch": slot["epoch"]}
                # ДЕРЖАТЕЛЬ НАЗЫВАЕТСЯ, ТОЛЬКО ЕСЛИ ОН ЕСТЬ. Поля стояли
                # безусловно, и на фенсинге по тарифу или по рычагу поддержки
                # уезжали пустая строка и ноль — из которых клиентский экран
                # рисует «место занял запуск  · слышали 56 лет назад». Отказ,
                # называющий держателя, которого нет, — это дефект Б26 в
                # машиночитаемой форме: `detail` уже был исправлен, а поля
                # рядом продолжали утверждать обратное. `None` доезжает как
                # «сервер не назвал» и рисуется словом «неизвестно».
                if slot["holder_start_id"]:
                    refusal["holder_start_id"] = slot["holder_start_id"]
                    refusal["holder_since"] = slot["last_heard_at"]
                return None, refusal
            quantum = self.issue_quantum(org_id, pubkey, plan, acked,
                                         standing["slot_no"], standing["epoch"], now)
            self._conn.execute(
                "UPDATE slots SET last_heard_at=? WHERE org_id=? AND slot_no=? "
                "AND epoch=?", (now, org_id, standing["slot_no"], standing["epoch"]))
            self._conn.commit()
            return quantum, {}

    def _never_granted(self, org_id: str, pubkey: str) -> bool:
        """Покупал ли этот ключ процесса ёмкость хоть раз.

        ПО НАШЕЙ СТРОКЕ ЛЕДЖЕРА, А НЕ ПО СЛОВАМ КЛИЕНТА: `quantum_seq` растёт
        только у нас и только на выдаче, поэтому «я ещё ни разу не покупал» —
        не утверждение клиента, а наша запись. Подделать её нечем: ключ
        процесса генерируется в памяти воркера, и второй раз тем же ключом
        первого кванта не бывает.
        """
        row = self._fetchone(
            "SELECT quantum_seq FROM meter WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        return row is None or int(row[0] or 0) == 0

    def _generation_standing(self, org_id: str,
                             start_id: str) -> dict[str, int] | None:
        """Где стоит ПОКОЛЕНИЕ сейчас — слот и эпох из нашей записи.

        Отдельно от `binding_of` потому, что это разные вопросы: аренда
        отвечает «за что этот КЛЮЧ платил, когда приходил», поколение —
        «держит ли этот КОНТЕЙНЕР слот сейчас». Воркеров у контейнера N, и
        перезаявляет слот один из них; остальные узнают об этом только на своём
        продлении, до восьми часов спустя.
        """
        row = self._fetchone(
            "SELECT slot_no, epoch FROM generations WHERE org_id=? AND start_id=?",
            (org_id, start_id))
        if row is None or row[0] is None:
            return None
        return {"slot_no": int(row[0]), "epoch": int(row[1] or 0)}

    def issue_quantum(self, org_id: str, pubkey: str, plan: str,
                      acked: int | None, slot_no: int | None, epoch: int | None,
                      now: float) -> dict[str, int]:
        """Выдать следующий квант ёмкости. ОДНА транзакция, одна запись.

        `acked` — подтверждённый расход процесса, или `None`, если отчёта не
        было или он не сошёлся. Тогда шаг СЛЕПОЙ: считаем, что предыдущий квант
        выбран целиком. Слепой шаг не может быть выгоднее честного — он
        завышает, — и это то, что делает молчание невыгодным без единого
        механизма принуждения.

        ЦЕЛЬ, А НЕ ПРИБАВКА. `granted += Q` — это учёт по числу ОБРАЩЕНИЙ, то
        есть по времени: ровно тот дефект, из-за которого простаивающий воркер
        накапливал 45 000 выданных за полторы минуты и тринадцать запросов.
        `granted = max(granted, consumed + Q + R)` делает прирост равным
        расходу, а разрыв `granted - consumed` — КОНСТАНТОЙ на процесс.
        """
        with self._lock:
            row = self.meter_row(org_id, pubkey)
            regressed = acked is not None and acked < row["acked"]
            if acked is None or regressed:
                # СЛЕПАЯ ОЦЕНКА — ЭТО ПОРОГ ПРЕДВЫБОРКИ, А НЕ «ПОТОЛОК МИНУС
                # КВАНТ». Движок приходит за следующим квантом ТОЛЬКО перейдя
                # порог, поэтому сам факт прихода и есть измерение: он обслужил
                # не меньше, чем `prefetch_at`.
                #
                # Первая версия считала `granted - quantum_size`, и на первом же
                # слепом шаге это давало НОЛЬ (потолок 200 при кванте 200), то
                # есть занижала счёт ровно там, где снятие отчёта и должно было
                # стать невыгодным. Найдено прогоном: расход 150, к счёту 0.
                consumed = max(row["prefetch_at"], row["acked"])
                trust_step = "blind"
            else:
                consumed = acked
                trust_step = "acked"

            elapsed = now - row["acked_at"] if row["acked_at"] else 0.0
            gained = max(0, consumed - row["acked"])
            rate = gained / elapsed if elapsed > 1.0 else 0.0

            # Границы кванта и резерва читаются ИЗ СТРОКИ ТАРИФА. Фолбэк —
            # «старт», как и был: тариф здесь уже проверен при выпуске ключа,
            # так что путь фолбэка означает строку, удалённую под работающим
            # клиентом, и самый тесный тариф — правильный ответ на это.
            plan_row = self.plan_row(plan)
            low = plan_row["quantum_min"] if plan_row else self.QUANTUM_BOUNDS["start"][0]
            high = plan_row["quantum_max"] if plan_row else self.QUANTUM_BOUNDS["start"][1]
            quantum = min(max(int(rate * self.METER_TARGET_SECONDS), low), high)
            # РЕЗЕРВ ВЫДАЁТСЯ СО ВТОРОГО КВАНТА. Процессу, который ещё ничего не
            # обслужил, нечего страховать от нашего простоя, а выдавая резерв
            # сразу, мы заставили бы платить за него каждый воркер каждого
            # перезапуска — дефект «грант по времени» вернулся бы другой дверью.
            if row["quantum_seq"] == 0:
                reserve = 0
            else:
                reserve_max = (plan_row["reserve_max"] if plan_row
                               else self.RESERVE_MAX["start"])
                reserve = min(max(int(rate * self.RESERVE_SECONDS), quantum),
                              reserve_max)
            granted = max(row["granted"], consumed + quantum + reserve)
            prefetch_at = max(1, granted - reserve
                              - max(1, int(quantum * self.PREFETCH_FRACTION)))
            unacked = 0 if trust_step == "acked" else row["unacked_quanta"] + 1

            self._conn.execute(
                "INSERT INTO meter (org_id, pubkey, first_seen, updated_at, "
                "quantum_seq, quantum_size, reserve, granted, acked, acked_at, "
                "ack_trust, rate_per_second, unacked_quanta, ack_regressions, "
                "prefetch_at, slot_no, epoch) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, pubkey) DO UPDATE SET updated_at=excluded.updated_at, "
                "quantum_seq=excluded.quantum_seq, quantum_size=excluded.quantum_size, "
                "reserve=excluded.reserve, granted=excluded.granted, "
                "acked=excluded.acked, acked_at=excluded.acked_at, "
                "ack_trust=excluded.ack_trust, rate_per_second=excluded.rate_per_second, "
                "unacked_quanta=excluded.unacked_quanta, "
                "ack_regressions=meter.ack_regressions+excluded.ack_regressions, "
                # ТЕГ ОБНОВЛЯЕТСЯ НА КАЖДОЙ ПОКУПКЕ: ключ переживает смену
                # эпоха только у того же поколения (перезаявка), и тогда его
                # расход обязан считаться за НОВЫЙ эпох, а не за похороненный.
                "prefetch_at=excluded.prefetch_at, slot_no=excluded.slot_no, "
                "epoch=excluded.epoch",
                (org_id, pubkey, now, now, row["quantum_seq"] + 1, quantum, reserve,
                 granted, max(consumed, row["acked"]), now, trust_step, rate,
                 unacked, 1 if regressed else 0, prefetch_at, slot_no, epoch))
            self._conn.commit()
        if regressed:
            _log.warning("consumed went backwards under one process key for "
                         "org=%s pubkey=%s: %d -> %s", org_id, pubkey[:12],
                         row["acked"], acked)
        return {"quantum_seq": row["quantum_seq"] + 1, "quantum_size": quantum,
                "reserve": reserve, "grant_total": granted,
                "prefetch_at": prefetch_at}

    def billable(self, org_id: str) -> dict[str, int]:
        """Сколько выставить. ПОДТВЕРЖДЁННОЕ, ЗАЖАТОЕ ВЫДАННЫМ.

        `clamp(acked, granted - Q - R, granted)` на каждый процесс, и сумма.
        Верхнюю границу клиент не перепрыгнет — без гранта движок не
        обслуживает; нижнюю не продавит — она наша запись. Значит отчёт двигает
        счёт только ВНУТРИ полосы шириной `Q + R`, и снять его — значит
        отказаться от скидки за неиспользованное, а не спрятать расход.
        """
        rows = self._fetchall(
            "SELECT granted, acked, quantum_size, reserve, unacked_quanta "
            "FROM meter WHERE org_id=?", (org_id,))
        billable = ceiling = acknowledged = unacked = 0
        for granted, acked, quantum, reserve, row_unacked in rows:
            floor = max(0, int(granted or 0) - int(quantum or 0) - int(reserve or 0))
            billable += min(max(int(acked or 0), floor), int(granted or 0))
            ceiling += int(granted or 0)
            acknowledged += int(acked or 0)
            unacked += int(row_unacked or 0)
        return {"billable": billable, "granted": ceiling, "acked": acknowledged,
                "processes": len(rows), "unacked_quanta": unacked}

    def _record_build(self, org_id: str, pubkey: str, build: str,
                      trust: str) -> None:
        """Какая сборка отчиталась, и менялась ли она под одним ключом процесса.

        Ключ процесса живёт ровно столько же, сколько процесс, поэтому у ЧЕСТНОГО
        процесса мера под ним меняться не может: тот же процесс исполняет тот же
        файл. Смена — это либо подмена отчёта, либо сборка, которая врёт о себе;
        и то и другое стоит записать с датой, а не обсуждать по памяти. Это
        доказуемость, а не невозможность: пропатченный бинарник соврёт и о мере
        тоже.
        """
        if not build or trust != "signed":
            return
        row = self._fetchone(
            "SELECT build FROM process_reports WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        previous = (row[0] or "") if row else ""
        with self._lock:
            if previous and previous != build:
                _log.warning("build measurement CHANGED under one process key for "
                             "org=%s pubkey=%s: %s -> %s", org_id, pubkey[:12],
                             previous[:20], build[:20])
                self._conn.execute(
                    "UPDATE process_reports SET build_changes=build_changes+1 "
                    "WHERE org_id=? AND pubkey=?", (org_id, pubkey))
            self._conn.execute(
                "UPDATE process_reports SET build=? WHERE org_id=? AND pubkey=?",
                (build, org_id, pubkey))
            self._conn.commit()

    def builds_seen(self, org_id: str) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT build, count(*), sum(build_changes) FROM process_reports "
            "WHERE org_id=? AND build!='' GROUP BY build", (org_id,))
        return [{"build": r[0], "processes": r[1], "changes": int(r[2] or 0)}
                for r in rows]

    def granted_total(self, org_id: str) -> int:
        row = self._fetchone(
            "SELECT COALESCE(SUM(granted), 0) FROM grants WHERE org_id=?",
            (org_id,))
        return int(row[0] or 0)

    def instances_allowed(self, plan: str) -> int:
        row = self.plan_row(plan)
        return row["max_instances"] if row else 1

    def processes_allowed(self, plan: str) -> int:
        """Потолок процессов на инстанс. Тоже из строки: тариф, которому нужно
        больше воркеров на узел, теперь настраивается, а не выкатывается."""
        row = self.plan_row(plan)
        return (row["processes_per_instance"] if row
                else self.PROCESSES_PER_INSTANCE)

    # ─────────────────────────────────────────────────────────────────────
    # СЛОТЫ И ПОКОЛЕНИЯ
    #
    # Ниже нет ни одного предиката живости, и это не аккуратность, а теорема:
    # даже слабейший полезный детектор отказов нереализуем в асинхронной
    # системе (Chandra–Toueg, JACM 43(2) 1996, сноска 6 — иначе он противоречил
    # бы FLP). Шесть заходов задавали серверу вопрос «жив ли контейнер» и
    # отвечали шестью таймерами; каждый приземлялся на честного клиента.
    # Отрасль эту теорему не решает, а обходит: монотонный номер привязывается
    # не к актору, а к ПРАВУ ДЕЙСТВОВАТЬ, и место действия отказывает всему,
    # что ниже наибольшего виденного номера. Инвариант становится «в каждый
    # момент операционен не более чем один раунд» — в нём предиката живости нет
    # вовсе.
    # ─────────────────────────────────────────────────────────────────────

    def ensure_slots(self, org_id: str, plan: str) -> int:
        """Завести строки слотов организации по её тарифу. Идемпотентно.

        ЗАВОДИТ ИХ СЕРВЕР, А НЕ ПРИХОД КЛИЕНТА. Зовётся при выпуске ключа и при
        смене тарифа; на пути аренды стоит как страховка для ключа, выпущенного
        до этой миграции, — и стоит она два точечных запроса, а не скан.

        ПОНИЖЕНИЕ ТАРИФА НЕ УДАЛЯЕТ СТРОКУ. Удалить — значит забыть эпох, а
        забытый эпох возвращает номер назад под работающим поколением: то
        самое, что фенсинг обязан исключать. Лишний слот помечается `retired`,
        его держатель отфенсится на следующей покупке — и текст отказа будет
        про ТАРИФ, а не про соседа (§9, S-24).

        ВЫВОДЯТСЯ ПУСТЫЕ СЛОТЫ, А НЕ СТАРШИЕ ПО НОМЕРУ, И ЭТО ПРАВКА ДЕФЕКТА, А
        НЕ ВКУСОВЩИНА. Выводилось `slot_no > allowed`, то есть по номеру. Номер
        слота ничего не говорит о том, занят ли он: контейнер, переживший пару
        перезапусков на четырёхслотовом тарифе, стоит на слоте 3, — и переход на
        «Старт» (один слот) отправлял ЕДИНСТВЕННЫЙ контейнер клиента в `fenced`
        текстом «остановите лишний контейнер», при том что свободный слот 1 стоял
        рядом пустой, а лишнего контейнера не было ни одного. Это тот же дефект,
        ради которого переписан весь этот файл (Б26: совет остановить то, чего
        нет), просто пришедший через тариф. Теперь потолок — это ЧИСЛО живых
        слотов, а какие именно, решаем мы: сначала занятые (кого слышали
        позже — тот остаётся), потом свободные по номеру. Отфенсить держателя
        приходится, только когда держателей БОЛЬШЕ, чем допускает новый тариф, —
        и тогда текст отказа честен, потому что лишний контейнер действительно
        есть.

        Номера остаются непрерывными только при повышении: после понижения
        живым может оказаться слот 3 при отсутствии слотов 1 и 2. Экраны ничего
        не выводят из номера — они показывают `slot_no` и считают занятость по
        полю `occupied`, — и это прямое требование Б26bis: число на экране обязано
        быть числом сервера, а не длиной списка или разностью номеров.
        """
        # САМЫЙ ЩЕДРЫЙ ИЗ ТАРИФОВ ОРГАНИЗАЦИИ, А НЕ ТАРИФ ПРЕДЪЯВЛЕННОГО КЛЮЧА.
        # Ключей у организации может быть несколько, и брать тариф того, кто
        # пришёл сейчас, значило бы дышать потолком: старый, более тесный ключ
        # выводил бы в `retired` слоты, которые оплачены новым. При смене
        # тарифа `set_org_plan` двигает ВСЕ ключи, поэтому понижение проходит.
        allowed = max(self.instances_allowed(plan),
                      self.instances_allowed(self.org_plan(org_id)))
        now = time.time()
        with self._lock:
            existing = {int(row[0]): (int(row[1] or 0), str(row[2] or ""),
                                      float(row[3] or 0.0))
                        for row in self._conn.execute(
                            "SELECT slot_no, retired, COALESCE(holder_start_id,''), "
                            "COALESCE(last_heard_at,0) FROM slots WHERE org_id=?",
                            (org_id,))}
            for slot_no in range(1, allowed + 1):
                if slot_no not in existing:
                    self._conn.execute(
                        "INSERT INTO slots (org_id, slot_no, epoch, opened_at, "
                        "last_heard_at) VALUES (?,?,0,?,0)", (org_id, slot_no, now))
                    existing[slot_no] = (0, "", 0.0)
            # ЗАНЯТЫЕ ВПЕРЁД, И СРЕДИ НИХ — КОГО СЛЫШАЛИ ПОЗЖЕ. Та же отметка и
            # тот же смысл, что у `admit_generation`: это РАНЖИРОВАНИЕ, а не
            # порог. Сказать «слот молчит дольше T, значит свободен» здесь было
            # бы тем же несуществующим детектором отказов; сказать «из занятых
            # этих слышали раньше всех» нельзя опровергнуть ничем.
            order = sorted(existing.items(),
                           key=lambda row: (0 if row[1][1] else 1,
                                            -row[1][2] if row[1][1] else 0,
                                            row[0]))
            keep = {slot_no for slot_no, _ in order[:allowed]}
            for slot_no, (retired, holder, _heard) in order:
                if slot_no in keep:
                    if retired:
                        self._conn.execute(
                            "UPDATE slots SET retired=0 WHERE org_id=? AND slot_no=?",
                            (org_id, slot_no))
                    continue
                if retired:
                    continue
                # ВЫВЕДЕННЫЙ СЛОТ ТЕРЯЕТ ДЕРЖАТЕЛЯ ТУТ ЖЕ, А НЕ ПРИ ВОЗВРАТЕ
                # ТАРИФА. Оставить его — значит показать этот слот занятым
                # поколением, которому мы уже отказали в новой ёмкости: экран
                # сказал бы «занято» про то, что доцеживает и встанет само, и
                # после обратного повышения тарифа слот приехал бы занятым
                # трупом. Эпох поднимается по той же причине, что и везде:
                # понизить его нельзя никогда.
                self._conn.execute(
                    "UPDATE slots SET retired=1, epoch=epoch+? , holder_start_id='', "
                    "holder_installation='', fenced_at=?, fenced_by='plan' "
                    "WHERE org_id=? AND slot_no=?",
                    (1 if holder else 0, now, org_id, slot_no))
                if holder:
                    self._conn.execute(
                        "UPDATE generations SET fenced_at=?, fenced_by='plan' "
                        "WHERE org_id=? AND start_id=?", (now, org_id, holder))
                    _log.info("slot %s of org=%s retired by plan change (held by %s)",
                              slot_no, org_id, holder[:12])
            self._conn.commit()
        return allowed

    def _slot_rows(self, org_id: str) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT slot_no, epoch, COALESCE(holder_start_id,''), "
            "COALESCE(holder_installation,''), COALESCE(last_heard_at,0), "
            "COALESCE(opened_at,0), fenced_at, COALESCE(fenced_by,''), "
            "COALESCE(retired,0) FROM slots WHERE org_id=? ORDER BY slot_no",
            (org_id,))
        return [{"slot_no": int(r[0]), "epoch": int(r[1] or 0),
                 "holder_start_id": str(r[2]), "holder_installation": str(r[3]),
                 "last_heard_at": float(r[4] or 0.0), "opened_at": float(r[5] or 0.0),
                 "fenced_at": r[6], "fenced_by": str(r[7]),
                 "retired": bool(r[8])} for r in rows]

    def admit_generation(self, slots: list[dict[str, object]],
                         installation_id: str) -> dict[str, object]:
        """ПРАВИЛО ДОПУСКА — ОДНА ФУНКЦИЯ, И ЭТО НАМЕРЕННО.

        Вариант владельца А (§6.1): «N — это упаковка, параллелизм бесплатен,
        объём оплачен». Заявка ВСЕГДА получает слот: отказ на N-м контейнере
        ломает каждую раскатку самой распространённой формы деплоя — K8s
        удваивает однорепличный Deployment по умолчанию (`maxUnavailable` 25 %
        округляется вниз до 0, `maxSurge` вверх до 1), — а Keygen для раскаток
        прямо рекомендует «rather than deny».

        ВАРИАНТ В (порог против ЧУЖОЙ установки) подключается ЗАМЕНОЙ ЭТОЙ
        ФУНКЦИИ и ничем больше: она — единственное место, где решается, какой
        слот отдать и отдавать ли вообще. Поэтому она возвращает `slot_no`
        вместе с `refusal`, хотя сегодня `refusal` всегда пуст: форма ответа не
        должна меняться вместе с решением владельца.

        Порядок предпочтения, и он НЕ случайный:

          a. слот, чей держатель — ТА ЖЕ УСТАНОВКА: перезапуск, OOM, раскатка
             на том же PVC;
          b. свободный слот;
          c. слот, чей держатель слышен РАНЬШЕ ВСЕХ (`MIN(last_heard_at)`).

        ЛИЧНОСТЬ ИДЁТ ПЕРЕД СВОБОДНЫМ СЛОТОМ, А НЕ ПОСЛЕ НЕГО, И ЭТО ОТСТУПЛЕНИЕ
        ОТ БУКВЫ §3.2 ТЗ (там порядок «свободный → своя установка»). На тарифе в
        один слот оба порядка совпадают — свободных не бывает, — и все девять
        сценариев ТЗ написаны на нём. На тарифе в четыре слота буква даёт
        экран, который врёт: ОДИН контейнер, перезапущенный трижды, занимает
        четыре слота (каждый следующий старт берёт очередной свободный, а
        прежний остаётся за мёртвым поколением), и кабинет печатает «занято 4 из
        4» клиенту с одним работающим контейнером — то есть продаёт ему апгрейд,
        которого не нужно. Это ровно класс Б26bis: экран, врущий о том, кто
        держит слот, и есть дефект. Установка в новом движке — это ТОМ
        (`audit.installation_id`, `entrypoint.sh` её больше не чеканит), а не
        запуск, поэтому «та же установка» значит «тот же том»: два контейнера на
        одном томе — это раскатка на одном PVC (§4.4), которой ТЗ само велит
        жить на ОДНОМ слоте, а четыре контейнера клиента — это четыре тома и
        четыре слота.

        ПУНКТ c — РАНЖИРОВАНИЕ, А НЕ ПОРОГ, И МИНИМУМ, А НЕ МАКСИМУМ.
        «Молчит дольше T» — утверждение о мире, и оно бывает ложным для трёх
        состояний из четырёх (медленный, отрезанный, пропатченный молчат так
        же, как мёртвый). «Из занятых этого слышали раньше всех» не утверждает
        ничего и ложным быть не может. Исследование в этом месте написало
        «позже всех» (`MAX`) и тут же объяснило перезапуск словами «его прежний
        эпох — самый старый среди занятых, потому что он мёртв»: первое
        вытесняет самого живого, второе — самого мёртвого, и верно второе
        (§3bis.1). С `MAX` пришедший после OOM отфенсил бы работающего соседа,
        а труп остался бы держателем.
        """
        live = [slot for slot in slots if not slot["retired"]]
        mine = [slot for slot in live
                if installation_id and slot["holder_installation"] == installation_id]
        if mine:
            return {"slot_no": mine[0]["slot_no"], "reason": "installation",
                    "refusal": ""}
        free = [slot for slot in live if not slot["holder_start_id"]]
        if free:
            return {"slot_no": free[0]["slot_no"], "reason": "free", "refusal": ""}
        ranked = sorted(live, key=lambda slot: (slot["last_heard_at"], slot["slot_no"]))
        if not ranked:
            # Тариф без единого слота — это не состояние клиента, а наша
            # испорченная строка тарифа. Поднимать её молча нельзя: клиент
            # получил бы отказ, причину которого не объясняет ни один экран.
            raise ValueError("plan has no slots to hand out")
        return {"slot_no": ranked[0]["slot_no"], "reason": "ranked", "refusal": ""}

    def _generation_name(self, org_id: str, declared: str,
                         installation_id: str) -> str:
        """Имя поколения ЧЕКАНИМ МЫ. Клиент называет корреляцию, не личность.

        ДЕФЕКТ, КОТОРЫЙ ЭТО ЗАКРЫВАЕТ, СНИМАЛ ФЕНСИНГ ЦЕЛИКОМ. Поколение
        искалось по одному только клиентскому `start_id`, а шаг 1
        `lease_generation` («это ещё один воркер того же старта») отдавал
        нашедшему ТОТ ЖЕ слот и ТОТ ЖЕ эпох даром. Значит два контейнера на
        разных томах, запущенные с одной переменной `PSEUDEX_START_ID`,
        становились одним поколением: оба покупали ёмкость под текущим эпохом,
        ни один не был отфенсен, и на слоте покупало не «ровно одно поколение»
        (§3.3), а сколько угодно. Замер на рабочем дереве: два контейнера,
        `pk1` и `pk2`, оба 200 на `/v1/meter`, `fenced` ни разу.

        ПРАВИЛО: ПОКОЛЕНИЕ ПРИНАДЛЕЖИТ ОДНОЙ УСТАНОВКЕ. Заявка, назвавшая
        занятое имя из-под ДРУГОЙ установки, в него не попадает — она получает
        имя, которое чеканим мы, и дальше идёт общим путём: свой слот по
        `admit_generation`, свой эпох, обычный фенсинг. Для честного клиента не
        меняется ничего: у воркеров одного контейнера установка одна (том один),
        поэтому все они по-прежнему одно поколение.

        ЧЕГО ЭТО НЕ ЗАКРЫВАЕТ, СКАЗАНО ПРЯМО. Контейнер, назвавший И чужой
        `start_id`, И чужой `installation_id`, неотличим от восьмого воркера
        того же старта: сервер получает байты, а «я тот же контейнер» —
        утверждение клиента (та же теорема §1.2, применённая к личности вместо
        живости). Остаток не закрывается техникой и поэтому обязан быть виден
        числом: `_installations_per_generation` считает установки по ЗАЯВЛЕННОМУ
        имени, и обе половины — и та, что теперь фенсится, и та, что нет, —
        попадают в аномалии.

        ИМЯ ДЕТЕРМИНИРОВАНО, а не случайно: продление того же чужого контейнера
        обязано находить СВОЁ поколение, иначе каждая его аренда заводила бы
        новое и он фенсил бы сам себя каждые восемь часов.
        """
        row = self._fetchone(
            "SELECT COALESCE(installation_id,'') FROM generations "
            "WHERE org_id=? AND start_id=?", (org_id, declared))
        if row is None or str(row[0]) == installation_id:
            return declared
        minted = (declared + "~"
                  + hashlib.sha256(installation_id.encode()).hexdigest()[:16])
        _log.warning("start_id %r of org=%s is claimed by installation %r; "
                     "installation %r gets its own generation %r",
                     declared[:24], org_id, str(row[0])[:16],
                     installation_id[:16], minted[:40])
        return minted

    def lease_generation(self, lease_id: str, org_id: str, plan: str,
                         start_id: str, installation_id: str, process_id: str,
                         ttl_seconds: int, pubkey: str, engine_version: str = "",
                         lease_contract: int | None = None) -> dict[str, object]:
        """Выдать поколению слот и записать аренду — В ОДНОЙ критической секции.

        Та же дисциплина, что была у `lease_if_allowed`: между предикатом и
        записью лок не отпускается. Замер прошлого захода: 71 гонка из 100
        проходила потолок, когда отпускался. Лок реентрантный, вложенные
        вызовы берут его повторно.

        ОТКАЗА ЗДЕСЬ НЕТ (вариант А, `admit_generation`): аренда всегда
        получает слот. Потолок принуждается не тем, что кому-то не дали
        подняться, а тем, что на слоте ПОКУПАЕТ ёмкость ровно одно поколение —
        старшее (`meter_if_allowed`).
        """
        with self._lock:
            # ЧИСЛО СЛОТОВ БЕРЁТСЯ У ТОЙ ЖЕ ФУНКЦИИ, КОТОРАЯ ИХ ЗАВОДИТ. Считать
            # его отдельно по тарифу предъявленного ключа значило бы назвать
            # клиенту одно число, а завести другое — у организации ключей может
            # быть несколько, и `ensure_slots` берёт самый щедрый из них.
            slot_count = self.ensure_slots(org_id, plan)
            now = time.time()
            slots = self._slot_rows(org_id)
            by_number = {slot["slot_no"]: slot for slot in slots}
            # ИМЯ ПОКОЛЕНИЯ РАЗРЕШАЕТСЯ ДО ПОИСКА, В ТОЙ ЖЕ СЕКЦИИ. Разреши его
            # снаружи — и между проверкой «чьё это имя» и записью поколения лок
            # отпускался бы ровно там, где решается, фенсить ли.
            declared, start_id = start_id, self._generation_name(
                org_id, start_id, installation_id)
            known = self._fetchone(
                "SELECT slot_no, epoch, claims, first_lease_at FROM generations "
                "WHERE org_id=? AND start_id=?", (org_id, start_id))
            fresh_claim = True
            if known is not None and known[0] is not None:
                held = by_number.get(int(known[0]))
                # ЕЩЁ ОДИН ВОРКЕР ТОГО ЖЕ СТАРТА (или его продление): поколение
                # уже держит свой слот на своём эпохе. Даром, без предела, без
                # единой записи в `slots` — иначе N воркеров одного контейнера
                # фенсили бы друг друга и контейнер был бы сломан по
                # построению.
                if held is not None and held["epoch"] == int(known[1] or 0) \
                        and not held["retired"]:
                    fresh_claim = False
                    slot_no, epoch = int(known[0]), int(known[1] or 0)
            if fresh_claim:
                admission = self.admit_generation(slots, installation_id)
                if admission["refusal"]:
                    # Ветка варианта В (§6.1). Сегодня недостижима — оставлена
                    # потому, что подключение варианта не должно требовать
                    # правки ЗДЕСЬ, только замены `admit_generation`.
                    raise SlotRefused(str(admission["refusal"]))
                slot_no = int(admission["slot_no"])
                previous = by_number[slot_no]
                epoch = previous["epoch"] + 1
                displaced = previous["holder_start_id"]
                self._conn.execute(
                    "UPDATE slots SET epoch=?, holder_start_id=?, "
                    "holder_installation=?, last_heard_at=?, "
                    "fenced_at=CASE WHEN ?<>'' THEN ? ELSE fenced_at END, "
                    "fenced_by=CASE WHEN ?<>'' THEN 'claim' ELSE fenced_by END "
                    "WHERE org_id=? AND slot_no=?",
                    (epoch, start_id, installation_id, now, displaced, now,
                     displaced, org_id, slot_no))
                if displaced:
                    self._conn.execute(
                        "UPDATE generations SET fenced_at=?, fenced_by='claim' "
                        "WHERE org_id=? AND start_id=?", (now, org_id, displaced))
                    _log.info("slot %s of org=%s moved to epoch %s (was %s)",
                              slot_no, org_id, epoch, displaced[:12])
            self._conn.execute(
                "INSERT INTO generations (org_id, start_id, declared_start_id, "
                "installation_id, slot_no, epoch, first_lease_at, last_lease_at, "
                "engine_version, lease_contract, claims) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, start_id) DO UPDATE SET "
                "installation_id=excluded.installation_id, "
                "slot_no=excluded.slot_no, epoch=excluded.epoch, "
                "last_lease_at=excluded.last_lease_at, "
                "engine_version=excluded.engine_version, "
                "lease_contract=excluded.lease_contract, "
                "claims=generations.claims+excluded.claims",
                (org_id, start_id, declared, installation_id, slot_no, epoch,
                 now, now, engine_version, lease_contract,
                 1 if fresh_claim else 0))
            self._conn.execute(
                "UPDATE slots SET last_heard_at=? WHERE org_id=? AND slot_no=?",
                (now, org_id, slot_no))
            self.record_lease(lease_id, org_id, installation_id, process_id,
                              ttl_seconds, pubkey=pubkey,
                              engine_version=engine_version,
                              lease_contract=lease_contract,
                              start_id=start_id, slot_no=slot_no, epoch=epoch)
            self._conn.commit()
        return {"slot_no": slot_no, "epoch": epoch, "slot_count": slot_count,
                "claimed": fresh_claim}

    def binding_of(self, org_id: str, pubkey: str,
                   cutoff: float) -> dict[str, object] | None:
        """К какому (слоту, эпоху) привязан ЭТОТ ключ процесса.

        По ПОСЛЕДНЕЙ аренде ключа в окне: продление вставляет новую строку, и
        читать надо свежайшую — иначе продлившееся поколение судилось бы по
        эпоху, который оно уже переросло.

        `None` значит «в окне аренд этого ключа нет»: бандла у него нет,
        поэтому квант ему бесполезен, и заводить здесь вторую границу незачем
        (так же вело себя и прежнее правило).
        """
        row = self._fetchone(
            "SELECT slot_no, epoch, COALESCE(start_id,'') FROM leases "
            "WHERE org_id=? AND pubkey=? AND issued_at>=? AND slot_no IS NOT NULL "
            "ORDER BY issued_at DESC LIMIT 1", (org_id, pubkey, cutoff))
        if row is None:
            return None
        return {"slot_no": int(row[0]), "epoch": int(row[1] or 0),
                "start_id": str(row[2])}

    def slot_state(self, org_id: str, slot_no: int) -> dict[str, object] | None:
        for slot in self._slot_rows(org_id):
            if slot["slot_no"] == slot_no:
                return slot
        return None

    def touch_slot(self, org_id: str, slot_no: int, epoch: int, now: float) -> bool:
        """Отметить, что текущее поколение слота с нами говорило.

        ТОЛЬКО ТЕКУЩЕЕ. Отчёт отфенсенного поколения мы принимаем всегда (это
        счёт, он нужен нам целиком), но двигать им отметку слота нельзя: она
        ранжирует слоты при выборе, и отфенсенный сосед, продолжающий
        отчитываться, вечно выталкивал бы себя из головы очереди.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE slots SET last_heard_at=? WHERE org_id=? AND slot_no=? "
                "AND epoch=?", (now, org_id, slot_no, epoch))
            self._conn.commit()
        return cursor.rowcount > 0

    def touch_for_process(self, org_id: str, pubkey: str, window_seconds: float,
                          now: float) -> bool:
        """Отметить слот, который держит ПОКОЛЕНИЕ этого ключа процесса.

        Одна функция, потому что вопрос один: «этот ключ только что с нами
        говорил — чей это слот». Ответ строится по НАШИМ записям (аренда →
        поколение → слот), а не по тому, что ключ назвал в теле: поля верхнего
        уровня отчёта подпись не покрывает, и сервер, веривший им, позволял
        любому ключу организации держать чужой мёртвый слот «свежим».

        Стоит на положении ПОКОЛЕНИЯ, а не строки аренды, по той же причине,
        что и фенсинг: перезаявляет слот один воркер, а отчитываются все.
        """
        binding = self.binding_of(org_id, pubkey, now - window_seconds)
        if binding is None:
            return False
        standing = self._generation_standing(org_id, str(binding["start_id"]))
        if standing is None:
            return False
        return self.touch_slot(org_id, standing["slot_no"], standing["epoch"], now)

    def slots_view(self, org_id: str, plan: str, window_seconds: float,
                   now: float) -> dict[str, object]:
        """Ответ `/admin/instances`: ПО СЛОТАМ, потому что потолок считается по ним.

        Прежняя форма (`active_instances`: `state ∈ {active, silent, released}`,
        `occupies`, `free_at`, `live_processes`, `held_places`) отвечала на
        вопрос «жив ли контейнер», которого больше нет. Экран, врущий о том, кто
        держит слот, и есть дефект (Б26bis), поэтому форма и витрина едут одним
        платформенным релизом.

        `band_left_estimate` — ОЦЕНКА СВЕРХУ и подписана словом «до»: `granted −
        max(acked, prefetch_at)` по строкам отфенсенного эпоха. Точного числа
        здесь быть не может — расход живёт в памяти чужого процесса.

        ОТФЕНСЕННОЕ ПОКОЛЕНИЕ НАЗЫВАЕТСЯ ДАЖЕ С НУЛЕВОЙ ПОЛОСОЙ. Список
        фильтровался по `band_left_estimate > 0`, и поколение, у которого
        соперник занял слот МЕЖДУ арендой и первым квантом (штатный холодный
        старт второго контейнера), не попадало в ответ вовсе: контейнер
        поднялся, `/mask` отдаёт 503 с первой секунды, а оператор, которому
        клиент пишет «второй контейнер не маскирует», не находил на экране
        ничего. Именно нулевая полоса и значит «не обслуживает». Окно —
        то же, что у остального ответа, иначе кольцо из полусотни оборотов
        осталось бы на экране навсегда.
        """
        slots = self._slot_rows(org_id)
        day_ago = now - 86400.0
        generations = self._fetchall(
            "SELECT start_id, COALESCE(installation_id,''), slot_no, epoch, "
            "first_lease_at, last_lease_at, COALESCE(engine_version,''), "
            "fenced_at, COALESCE(fenced_by,''), released_at, COALESCE(claims,0) "
            "FROM generations WHERE org_id=? ORDER BY epoch", (org_id,))
        workers = {}
        purchases = {}
        bands = {}
        for slot_no, epoch, heard, granted, acked, prefetch in self._fetchall(
                "SELECT slot_no, epoch, MAX(updated_at), SUM(granted), SUM(acked), "
                "SUM(prefetch_at) FROM meter WHERE org_id=? AND slot_no IS NOT NULL "
                "GROUP BY slot_no, epoch", (org_id,)):
            key = (int(slot_no), int(epoch or 0))
            purchases[key] = float(heard or 0.0)
            bands[key] = max(0, int(granted or 0)
                             - max(int(acked or 0), int(prefetch or 0)))
        for slot_no, epoch, count in self._fetchall(
                "SELECT slot_no, epoch, COUNT(DISTINCT pubkey) FROM leases "
                "WHERE org_id=? AND slot_no IS NOT NULL AND issued_at>=? "
                "GROUP BY slot_no, epoch", (org_id, now - window_seconds)):
            workers[(int(slot_no), int(epoch or 0))] = int(count)
        listed: list[dict[str, object]] = []
        live_slots = [slot for slot in slots if not slot["retired"]]
        for slot in live_slots:
            holder = None
            draining = []
            for (start_id, installation, slot_no, epoch, first_at, last_at,
                 version, fenced_at, fenced_by, released_at, claims) in generations:
                if slot_no is None or int(slot_no) != slot["slot_no"]:
                    continue
                key = (slot["slot_no"], int(epoch or 0))
                if start_id == slot["holder_start_id"] and int(epoch or 0) == slot["epoch"]:
                    holder = {"start_id": str(start_id),
                              "installation_id": str(installation),
                              "engine_version": str(version),
                              "since": float(first_at or 0.0),
                              "workers_heard": workers.get(key, 0),
                              "last_heard_at": slot["last_heard_at"],
                              "last_purchase_at": purchases.get(key, 0.0),
                              "claims": int(claims or 0),
                              "released": released_at is not None}
                elif (fenced_at is not None
                      and float(fenced_at) >= now - window_seconds):
                    draining.append({"start_id": str(start_id),
                                     "epoch": int(epoch or 0),
                                     "fenced_at": float(fenced_at),
                                     "fenced_by": str(fenced_by),
                                     "band_left_estimate": bands.get(key, 0)})
            listed.append({"slot_no": slot["slot_no"], "epoch": slot["epoch"],
                           "holder": holder, "draining": draining})
        started = self._fetchone(
            "SELECT COUNT(*) FROM generations WHERE org_id=? AND first_lease_at>=?",
            (org_id, day_ago))
        return {"org_id": org_id,
                "slot_count": self.instances_allowed(plan),
                "processes_per_instance": self.processes_allowed(plan),
                # «ЗАНЯТО» — ЧИСЛО СЕРВЕРА, А НЕ ДЛИНА СПИСКА. Список содержит
                # и свободные слоты; считать по нему занятость — ровно тот
                # дефект, ради которого поле и появилось (Б26bis).
                "occupied": sum(1 for row in listed if row["holder"] is not None),
                "slots": listed,
                "generations_24h": int(started[0] or 0) if started else 0,
                "epochs_unacked_24h": self._epochs_unacked(org_id, day_ago),
                "slot_contention_24h": self._slot_contention(org_id, day_ago),
                # УСТАНОВКИ ПРОШЛОГО РЕЛИЗА, ЕЩЁ НЕ ЗАНЯВШИЕ СЛОТ. Без этого
                # числа «занято 0 из 4» сразу после платформенного релиза
                # читается как «ничего не работает» — догадка ровно того же
                # рода, что «занято 4 из 4» с призраками усыновления.
                "pending_installations": self.pending_installations(org_id, now),
                # ЁМКОСТЬ, КУПЛЕННАЯ МИМО СЛОТА. Ключ без привязанной аренды в
                # окне покупает и не фенсится (`meter_if_allowed`): бандла у
                # него нет, квант ему бесполезен, и заводить там вторую границу
                # значило бы судить по молчанию. Но выданное — это выданное, а
                # агрегаты слотов его не видят по построению (тег пуст), и без
                # этой пары чисел оно не видно НИГДЕ. §2 Т1 обещает «каждый
                # обход виден числом», поэтому число стоит здесь, рядом с
                # остальными, а не в логе.
                **self._unbound_capacity(org_id),
                "window_seconds": int(window_seconds),
                "meter_target_seconds": self.METER_TARGET_SECONDS}

    def _unbound_capacity(self, org_id: str) -> dict[str, int]:
        """Строки леджера без тега слота: сколько таких ключей и сколько им
        выдано. Это ёмкость, которая в агрегаты по слотам не попадает никогда —
        назвать её отдельно дешевле, чем объяснять потом, почему суммы по
        слотам не сходятся с `capacity_granted` организации."""
        row = self._fetchone(
            "SELECT COUNT(*), COALESCE(SUM(granted),0) FROM meter "
            "WHERE org_id=? AND slot_no IS NULL", (org_id,))
        return {"unbound_processes": int(row[0] or 0) if row else 0,
                "unbound_granted": int(row[1] or 0) if row else 0}

    def _epochs_unacked(self, org_id: str, since: float) -> int:
        """Поколения за окно, ни разу не подтвердившие расход.

        Кольцо «аренда → молчание → аренда» видно ровно этим: каждый оборот —
        поколение, купившее первый квант и не сказавшее о нём ни слова.
        """
        # ЧЕРЕЗ КЛЮЧИ ПОКОЛЕНИЯ, А НЕ ЧЕРЕЗ ТЕГ СТРОКИ ЛЕДЖЕРА.
        #
        # Джойн `generations.epoch = meter.epoch` читается верно ровно до первой
        # перезаявки: эпох поколения растёт в момент заявки, а тег строки
        # леджера — только на СЛЕДУЮЩЕЙ покупке. Поколение, подтвердившее
        # подписанным ack сто восемьдесят запросов, после своей единственной
        # разрешённой (§3.6) перезаявки читалось как «не подтвердило ничего», и
        # одна честная раскатка K8s клала клиента в аномалии с формулировкой
        # «кольцо или крэшлуп». Связь «ключ → поколение» тегов не имеет и не
        # дрейфует: её пишет `lease_generation` в ту же секцию, что и слот.
        rows = self._fetchall(
            "SELECT g.start_id, COALESCE(SUM(m.acked),0) FROM generations g "
            "LEFT JOIN (SELECT DISTINCT org_id, start_id, pubkey FROM leases "
            "           WHERE start_id IS NOT NULL) l "
            "  ON l.org_id=g.org_id AND l.start_id=g.start_id "
            "LEFT JOIN meter m ON m.org_id=l.org_id AND m.pubkey=l.pubkey "
            "WHERE g.org_id=? AND g.first_lease_at>=? GROUP BY g.start_id",
            (org_id, since))
        return sum(1 for _, acked in rows if int(acked or 0) == 0)

    def _slot_contention(self, org_id: str, since: float) -> int:
        """Перезаявки слота поколениями, которые уже были отфенсены — ЧИСЛО
        ДЛЯ ЭКРАНА: сколько раз за окно кто-то возвращался за своим слотом.

        Считается по НАШЕЙ записи (`claims`), а не по самоотчёту. Порог аномалии
        стоит НЕ на этой сумме — см. `_reclaim_streak`.
        """
        row = self._fetchone(
            "SELECT COALESCE(SUM(claims-1),0) FROM generations "
            "WHERE org_id=? AND first_lease_at>=? AND claims>1", (org_id, since))
        return int(row[0] or 0) if row else 0

    def _reclaim_streak(self, org_id: str, since: float) -> int:
        """Сколько раз перезаявляло САМОЕ НАСТОЙЧИВОЕ поколение за окно.

        ПОРОГ СТОИТ ЗДЕСЬ, А НЕ НА СУММЕ, И ЭТО РАЗНИЦА МЕЖДУ НАБЛЮДЕНИЕМ И
        ЛОЖНОЙ ТРЕВОГОЙ. Честная раскатка K8s (§4.4 ТЗ — «штатно, при каждом
        обновлении») даёт РОВНО ОДНУ перезаявку вытесненного пода, и клиент,
        катящийся трижды в день, даёт сумму три: на сумме порог «≥ 1» красил
        каждое обновление в «кольцо или два живых контейнера». Два живых
        контейнера на одном слоте выглядят иначе — ОДНО поколение возвращается
        снова и снова, пока живо, — и это видно по максимуму, а не по сумме.
        """
        row = self._fetchone(
            "SELECT COALESCE(MAX(claims-1),0) FROM generations "
            "WHERE org_id=? AND first_lease_at>=?", (org_id, since))
        return int(row[0] or 0) if row else 0

    def fleet_versions(self, window_seconds: int) -> list[dict]:
        """The fleet by engine version: how many live instances and organisations
        run each one, within the lease window (D-056). This is the number the
        floor is moved against — a cycle is closed when nobody is on it, not
        when the calendar says so. An empty string is a pre-D-053 image that
        reported nothing useful ("1.0.0" is recorded as such)."""
        cutoff = time.time() - window_seconds
        rows = self._fetchall(
            "SELECT COALESCE(engine_version, ''), lease_contract, "
            "COUNT(DISTINCT instance_id), COUNT(DISTINCT org_id) FROM leases "
            "WHERE issued_at>=? AND released_at IS NULL "
            "GROUP BY COALESCE(engine_version, ''), lease_contract ORDER BY 3 DESC",
            (cutoff,),
        )
        return [{"engine_version": str(version),
                 "lease_contract": None if contract is None else int(contract),
                 "instances": int(instances), "orgs": int(orgs)}
                for version, contract, instances, orgs in rows]

    def release_instance(self, org_id: str, instance_id: str,
                         slot_no: int | None) -> int:
        """Рычаг поддержки: освободить слот этой УСТАНОВКИ — названный или все.

        Семантика новая, аудитория та же. Раньше это была пометка строк аренды
        `released_by='admin'`, и она освобождала «места рабочих процессов»,
        которых больше нет. Теперь — поднять эпох слота и снять держателя:
        поколение на нём получит `fenced` на следующей покупке и доцедит
        купленное.

        ЗАЧЕМ ОН НУЖЕН, ЕСЛИ 2b/2c РЕШАЮТ САМИ: для редкого случая «клиент
        говорит, что контейнера нет, а его слышали позже всех» — например,
        клиент удалил том и поднял замену, а прежний слот всё ещё числится за
        исчезнувшей установкой при полностью занятом тарифе. Рычаг редкий
        именно потому, что 2b (возврат своей установки) закрывает подавляющее
        большинство обращений, ради которых он заводился.

        `slot_no` НАЗЫВАЕТСЯ, И ЭТО ПРАВКА, А НЕ УДОБСТВО. Рычаг освобождал ВСЕ
        слоты установки, а установка у клиента одна на том — то есть на тарифе
        в четыре контейнера, поднятых с одного `PSEUDEX_INSTANCE_ID` (E7,
        законная конфигурация), обращение «у меня застрял один контейнер»
        отфенсивало все четыре. Поддержка не имела формы задать вопрос уже,
        поэтому единственный доступный ей ответ был самым крупным. `None`
        оставлено как прежнее поведение — им пользуется «клиента больше нет», —
        но теперь это ВЫБОР вызывающего, а не единственная возможность.

        ПОМЕЧАЮТСЯ ПОКОЛЕНИЯ, КОТОРЫЕ СЛОТ ДЕРЖАЛИ, А НЕ ВСЕ ПОКОЛЕНИЯ
        УСТАНОВКИ. Пометка шла по `installation_id`, и один вызов переписывал
        `fenced_at`/`fenced_by` КАЖДОМУ прошлому запуску этого тома: давно
        вытесненные обычной перезаявкой поколения получали свежую дату и слово
        «освободила поддержка», всплывали в списке доцеживающих на экране и
        рассказывали про событие, которого с ними не происходило. Слово рядом с
        числом не имеет права спорить с числом (Б26bis).

        Возвращает число освобождённых слотов: ноль — это не успех, а «такой
        установки среди держателей нет», и вызывающий обязан их различать.
        """
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT slot_no, COALESCE(holder_start_id,'') FROM slots "
                "WHERE org_id=? AND holder_installation=?",
                (org_id, instance_id)).fetchall()
            held = [(int(row[0]), str(row[1])) for row in rows
                    if slot_no is None or int(row[0]) == slot_no]
            for number, holder in held:
                self._conn.execute(
                    "UPDATE slots SET epoch=epoch+1, holder_start_id='', "
                    "holder_installation='', fenced_at=?, fenced_by='admin' "
                    "WHERE org_id=? AND slot_no=?", (now, org_id, number))
                if holder:
                    self._conn.execute(
                        "UPDATE generations SET fenced_at=?, fenced_by='admin' "
                        "WHERE org_id=? AND start_id=?", (now, org_id, holder))
            self._conn.commit()
        if held:
            _log.info("admin freed slots %s of org=%s held by installation %s",
                      [number for number, _ in held], org_id, instance_id)
        return len(held)

    # ─────────────────────────────────────────────────────────────────────
    # ЗДЕСЬ ЖИЛИ ВСЕ ОТКАЗЫ НА АРЕНДЕ, И ИХ БОЛЬШЕ НЕТ НИ ОДНОГО.
    #
    # `_refuse_occupied`, `_refuse_reclaimed`, `_refuse_turnover`,
    # `_refuse_processes`, `_admission`, `may_lease`, `_NOTHING_TAKEN`,
    # `_REDEPLOY_HINT` — шесть заходов текстов, объясняющих клиенту, почему его
    # контейнер не поднялся. Каждый лечил свой дефект предыдущего и заводил
    # следующий: «остановите лишний контейнер», которого нет (Б26); «слот
    # занят» при полном потолке после двух честных остановок (Б26quinquies);
    # «места рабочих процессов» у поколения из 32 ключей (Б26quater); отказ на
    # 6-м, 9-м и 3-м честном старте у выпущенного 0.3.17 (Б26sexies).
    #
    # ЧЕМ ЛЕЧИТСЯ ТЕПЕРЬ: на аренде отказов нет вовсе (`admit_generation`,
    # вариант А). Единственный отказ переехал на ёмкость и называется `fenced`
    # — он адресован не человеку, поднимающему контейнер, а процессу, которому
    # больше не продают НОВУЮ ёмкость; уже купленную он доцеживает и встаёт
    # сам. Текст для человека живёт рядом с ним, в одном месте вместо шести.
    # ─────────────────────────────────────────────────────────────────────

    def prune_leases(self, window_seconds: int) -> int:
        """Выбросить аренды и поколения, которые давно не считаются ни в одном
        окне.

        Ни одно решение их уже не видит (`binding_of` смотрит в окно); смысл
        в том, чтобы таблица не росла вечно на машине, где мы сами и живём.

        ПОКОЛЕНИЯ ЧИСТЯТСЯ ТОЖЕ, И ЭТО НЕ КОСМЕТИКА. Строка пишется на КАЖДЫЙ
        старт контейнера, а `/admin/instances` читает их все и гоняет по ним
        цикл на каждый слот: замер дал 0.8 мс при 50 поколениях и 4.6 мс при
        2000, и эту страницу открывают кабинет клиента и консоль поддержки.
        Крэшлуп ТЗ считает ожидаемым трафиком (§3.7), а докеровский бэкофф
        упирается в 60 с — это до полутора тысяч строк в сутки с одного
        контейнера.

        ДЕРЖАТЕЛЯ НЕ ТРОГАЕМ НИКОГДА, сколько бы он ни молчал: удалить строку
        поколения, которое держит слот, значило бы забыть, чей это слот, —
        `meter_if_allowed` перестал бы находить его положение и отказал бы
        работающему контейнеру. Эпох слота при этом не трогается вовсе: он
        живёт в `slots` и не понижается ни при какой чистке.
        """
        cutoff = time.time() - 2 * window_seconds
        with self._lock:
            cursor = self._conn.execute("DELETE FROM leases WHERE issued_at<?",
                                        (cutoff,))
            self._conn.execute(
                "DELETE FROM generations WHERE last_lease_at<? AND NOT EXISTS ("
                "  SELECT 1 FROM slots s WHERE s.org_id=generations.org_id "
                "  AND s.holder_start_id=generations.start_id)", (cutoff,))
            self._conn.commit()
        return cursor.rowcount

    def usage_totals(self, org_id: str) -> dict[str, object]:
        """Billing view: the org's consumption, summed across its INSTANCES.

        Summing instances is right (two containers are two deployments doing real
        work); summing reports would not be, because each report restates the same
        cumulative total."""
        rows = self._fetchall(
            "SELECT instance_id, reports, requests, entities, values_total, resets, "
            # СЧЁТ ОБЯЗАН ВИДЕТЬ, ЧТО ЕМУ НЕ ПОКАЗАЛИ. Без этих двух колонок
            # инвойс не мог отличить «расхода не было» от «расход был, но его
            # никто не подтвердил».
            "unverified_reports, unverified_requests, chain_breaks, "
            "malformed_reports, reports_missing FROM usage WHERE org_id=?",
            (org_id,),
        )
        entities: dict[str, int] = {}
        requests = reports = values = resets = 0
        unverified_reports = unverified_requests = breaks = malformed = 0
        missing = 0
        for row in rows:
            (_instance, row_reports, row_requests, row_entities, row_values,
             row_resets, row_unver, row_unver_req, row_breaks, row_malformed,
             row_missing) = row
            requests += int(row_requests or 0)
            reports += int(row_reports or 0)
            values += int(row_values or 0)
            resets += int(row_resets or 0)
            unverified_reports += int(row_unver or 0)
            unverified_requests += int(row_unver_req or 0)
            breaks += int(row_breaks or 0)
            malformed += int(row_malformed or 0)
            missing += int(row_missing or 0)
            # ТЕРПИМО К ТОМУ, ЧТО УЖЕ ЛЕЖИТ. Вход теперь проверяется, но в
            # проде могут лежать строки, записанные до этого: нечисловое
            # значение здесь давало TypeError, то есть `/admin/usage` отвечал
            # 500 НАВСЕГДА для этой организации — а вместе с ним падали кабинет
            # и выставление счёта. Первая же правка обязана поднять ручку, а не
            # ждать чистки (`licensing/repair_usage.py`).
            try:
                stored = json.loads(row_entities or "{}")
            except ValueError:
                _log.warning("unreadable entities for org=%s instance=%s", org_id, _instance)
                continue
            for entity_type, count in stored.items():
                if isinstance(count, bool) or not isinstance(count, int):
                    _log.warning("non-numeric count %r for %s in org=%s instance=%s",
                                 count, entity_type, org_id, _instance)
                    continue
                entities[entity_type] = entities.get(entity_type, 0) + count
        return {"org_id": org_id, "instances": len(rows), "reports": reports,
                "requests": requests, "entities": entities,
                # THE BILLED QUANTITY. Monotonic and summed across instances,
                # because two containers are two deployments doing real work.
                "values": values,
                # Times an instance's counter went backwards. Not evidence — a
                # vault can be lost honestly — but a pattern worth seeing.
                "resets": resets,
                # ЧТО НЕ ВОШЛО В СЧЁТ И ПОЧЕМУ. Отчёт без подтверждённого MAC
                # не попадает в `requests`/`values`; он копится здесь, чтобы
                # инвойс не путал «расхода не было» с «расход не подтверждён».
                "unverified_reports": unverified_reports,
                "unverified_requests": unverified_requests,
                "chain_breaks": breaks,
                # Отчёты, которые пришли и не разобрались.
                "malformed_reports": malformed,
                # Продления, в которых отчёта не было вовсе.
                "reports_missing": missing,
                # ЧИСЛО, НА КОТОРОМ СТРОИТСЯ СЧЁТ, И ВСЁ, ЧЕМ ОНО ЗАЖАТО.
                **{f"capacity_{name}": value
                   for name, value in self.billable(org_id).items()},
                # ЧИСЛО, НА КОТОРОМ СТРОИТСЯ СЧЁТ. Сумма выданной ёмкости —
                # целиком наша запись; `requests` рядом остаётся справочным.
                "granted": self.granted_total(org_id)}

    def release_process(self, org_id: str, pubkey: str) -> bool:
        """Записать, что процесс попрощался. НИ ОДНО РЕШЕНИЕ ЭТОГО НЕ ЧИТАЕТ.

        И это единственное правило, которое разом выполняет требование
        Б26quinquies («честный уход не стоит ничего») и требование
        конструкции («прощание не нужно»): OOM-килл и `docker stop` идут по
        серверу байт в байт одним путём, потому что различающее их поле не
        читается нигде. Освобождение слота происходит в момент, когда за ним
        приходит НОВОЕ поколение, и только там сервер что-то решает.

        Строка остаётся ради экрана — «остановлен сам» — и ради выпущенных
        движков, которые эту ручку зовут.
        """
        now = time.time()
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE leases SET released_at=?, released_by='process' "
                "WHERE org_id=? AND pubkey=? AND released_at IS NULL",
                (now, org_id, pubkey))
            self._conn.execute(
                "UPDATE generations SET released_at=? WHERE org_id=? AND start_id="
                "(SELECT COALESCE(start_id,'') FROM leases WHERE org_id=? AND pubkey=? "
                " ORDER BY issued_at DESC LIMIT 1)", (now, org_id, org_id, pubkey))
            self._conn.commit()
        return cursor.rowcount > 0

    def org_plan(self, org_id: str) -> str:
        """Тариф организации. Тариф живёт на КЛЮЧЕ, а ключей может быть
        несколько — берём самый щедрый из ДЕЙСТВУЮЩИХ, чтобы наблюдение не
        обвинило клиента по его же старому, более тесному ключу.

        ТОЛЬКО ДЕЙСТВУЮЩИЕ, И ЭТО НЕ ПРИДИРКА. Без фильтра по статусу
        организация, у которой отозвали ключ «Промышленного» и выдали ключ
        «Старта», навсегда сохраняла двенадцать слотов: понижение тарифа
        отзывом ключа (или выдачей через `/admin/issue` напрямую, мимо
        `/admin/replan`) не доходило до потолка вовсе. Слоты под вариантом А
        ничего не запрещают, но именно они задают единственное, что
        принуждается, — «на слоте покупает одно поколение»."""
        rows = self._fetchall("SELECT DISTINCT plan FROM keys WHERE org_id=? "
                              "AND status=?", (org_id, STATUS_ACTIVE))
        plans = [str(row[0]) for row in rows if row[0]]
        return max(plans, key=self.instances_allowed) if plans else ""

    def instances(self, org_id: str) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT instance_id, process_id, issued_at FROM leases WHERE org_id=? "
            "ORDER BY issued_at DESC LIMIT 100", (org_id,)
        )
        return [{"instance_id": r[0], "process_id": r[1], "issued_at": r[2]} for r in rows]

    def list_orgs(self) -> list[dict[str, object]]:
        """Каталог абонентов — ОДНА СТРОКА НА ОРГАНИЗАЦИЮ.

        Была строка на КАЖДЫЙ КЛЮЧ (`FROM keys k`), поэтому организация с тремя
        ключами троилась. Для сторожа это не косметика: он печатает `late[:20]`,
        и один клиент с тремя ключами занимал в этом списке три места из
        двадцати — то есть список «кто вот-вот встанет» тем короче, чем больше у
        клиентов ключей.

        `last_lease` ОТДАЁТСЯ ЗДЕСЬ, И ЭТО НЕ УКРАШЕНИЕ. `deploy/watch.sh` читает
        это поле, чтобы поймать клиента, который вот-вот встанет; поля не было,
        поэтому проверка «не продлевают аренду больше суток» была ВСЕГДА ПУСТОЙ —
        а это ровно тот сигнал, который поймал бы и блэкхол, и повтор лизы: и то
        и другое выглядит как «клиент перестал продлеваться».

        `plan` берётся с ПОСЛЕДНЕГО выпущенного ключа: тарифы ключей одной
        организации расходятся только при смене тарифа, и тогда верен свежий.

        `status` ОРГАНИЗАЦИИ — ЭТО «ОБСЛУЖИВАЕТСЯ ЛИ ОНА», А НЕ СТАТУС КАКОГО-ТО
        ОДНОГО КЛЮЧА. `set_status` действительно двигает все ключи разом, но
        `revoke_key_hash` отзывает РОВНО ОДИН — им и отзывают утёкший ключ, не
        останавливая клиента. Взяв статус свежайшего, каталог показал бы
        организацию отозванной ровно потому, что у неё отозвали последний
        выпущенный ключ, — при живой работе на остальных. Поэтому: есть хоть один
        активный ключ — организация активна, а полная раскладка отдаётся рядом
        (`statuses`), чтобы «активна, но один ключ отозван» было видно, а не
        додумывалось.
        """
        rows = self._fetchall(
            "SELECT k.org_id, MIN(k.created_at), COUNT(*), "
            "(SELECT MAX(issued_at) FROM leases l WHERE l.org_id=k.org_id), "
            # Тариф свежайшего ключа: коррелированный подзапрос по `created_at`,
            # а не `MAX(k.plan)` — последнее вернуло бы лексикографический
            # максимум, то есть тариф наугад.
            "(SELECT plan FROM keys k2 WHERE k2.org_id=k.org_id "
            " ORDER BY k2.created_at DESC LIMIT 1), "
            "(SELECT status FROM keys k3 WHERE k3.org_id=k.org_id "
            " ORDER BY k3.created_at DESC LIMIT 1), "
            "SUM(CASE WHEN k.status='active' THEN 1 ELSE 0 END), "
            "GROUP_CONCAT(k.status) "
            "FROM keys k GROUP BY k.org_id ORDER BY MIN(k.created_at)", ())
        catalogue = []
        for row in rows:
            active = int(row[6] or 0)
            statuses: dict[str, int] = {}
            for status in (row[7] or "").split(","):
                if status:
                    statuses[status] = statuses.get(status, 0) + 1
            catalogue.append({
                "org_id": row[0], "created_at": row[1], "keys": int(row[2] or 0),
                "last_lease": row[3], "plan": row[4],
                "status": STATUS_ACTIVE if active else row[5],
                "active_keys": active, "statuses": statuses,
            })
        return catalogue
