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
    `active_instances`: «0.3.9» > «0.3.10» как строки держали обновившийся
    инстанс на старой версии целое окно. То же самое в правиле занятости стоило
    бы клиенту слота, поэтому сравнение живёт здесь, а не в запросе."""
    parts = []
    for chunk in version.split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


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
                            ("lease_contract", "lease_contract INTEGER")):
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
        # `may_lease` сканирует её целиком на КАЖДОЙ аренде — то есть на
        # запросе, который решает, обслуживать ли клиента.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS leases_org_issued "
            "ON leases(org_id, issued_at)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS leases_org_pubkey ON leases(org_id, pubkey)")
        # ЛЕДЖЕР ДОПУСКОВ — ЕДИНИЦЫ БЮДЖЕТА ПЕРЕВЫДАЧИ, И ТОЛЬКО ОНИ.
        #
        # Бюджет считался по строкам `leases.released_*`, и это давало два
        # разных числа за одно и то же событие: `COUNT(*)` по `released_by
        # ='process'` брал с честной остановки четырёхворкерного контейнера,
        # продлевавшегося трижды, ДВЕНАДЦАТЬ единиц (весь часовой бюджет — и
        # клиент блокировал сам себе редеплой), а `COUNT(DISTINCT instance_id)`
        # по `released_by='silence'` насыщался на двух значениях: карусель,
        # чередующая ДВА `PSEUDEX_INSTANCE_ID`, переставала тратить бюджет
        # вообще, и потолок обхода уезжал вверх.
        #
        # Единица тратится ДОПУСКОМ, вытеснившим чужой слот, — одна строка на
        # один допуск, что бы он ни вытеснил и сколько бы у контейнера ни было
        # воркеров. Поэтому леджер отдельный: строки аренды описывают аренды,
        # а не события перевыдачи, и считать одно по другому — это ровно та
        # ошибка, которую здесь чинят.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS admissions ("
            "org_id TEXT, instance_id TEXT, at REAL, displaced TEXT, reason TEXT)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS admissions_org_at ON admissions(org_id, at)")
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
            "PRIMARY KEY (org_id, pubkey))"
        )
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
        `may_lease` — the query that decides whether a customer may serve
        traffic at all — and `devserver.py` runs the admin app on a second
        thread against this same connection.
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
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE key_hash=? AND status=?",
                (STATUS_REVOKED, key_hash, STATUS_ACTIVE),
            )
            self._conn.commit()
            return cursor.rowcount

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
        return cursor.rowcount

    def record_lease(self, lease_id: str, org_id: str, instance_id: str,
                     process_id: str, ttl_seconds: int, pubkey: str = "",
                     engine_version: str = "",
                     lease_contract: int | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO leases "
                "(lease_id, org_id, instance_id, process_id, pubkey, issued_at, "
                "ttl_seconds, engine_version, lease_contract) VALUES (?,?,?,?,?,?,?,?,?)",
                (lease_id, org_id, instance_id, process_id, pubkey, time.time(),
                 ttl_seconds, engine_version, lease_contract),
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
        значит держать лок store, который в этот момент нужен `may_lease`, чтобы
        выдавать аренды всем остальным.
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
    # ПОТОЛОК ПРОЦЕССОВ НА КОНТЕЙНЕР. Тариф ПУБЛИКУЕТСЯ в контейнерах, а
    # ПРИНУЖДАЕТСЯ в процессах, потому что `instance_id` приходит из переменной
    # окружения (`service.py`), которую ставит клиент: пятьдесят контейнеров с
    # одним значением читались как один инстанс, и тариф обходился одной строкой
    # в compose-файле. Ключ процесса — единственное, что клиент не выбирает.
    #
    # Число щедрое намеренно. `entrypoint.sh` берёт воркеров по числу ядер, и
    # отказать честному клиенту на большой машине хуже, чем пропустить лишнее:
    # обход тарифа этим потолком становится дороже ровно настолько, насколько
    # клиенту придётся поднимать контейнеры с малым числом воркеров, то есть
    # тратить память впустую. 32 покрывает любой разумный узел.
    PROCESSES_PER_INSTANCE = 32
    # СКОЛЬКО МЫ СЧИТАЕМ ИНСТАНС ЖИВЫМ ПОСЛЕ ПОСЛЕДНЕГО ПРИЗНАКА ЖИЗНИ.
    #
    # ТРИ СРОКА, КОТОРЫЕ РАНЬШЕ БЫЛИ ОДНИМ. Окно аренды (TTL) отвечало сразу на
    # два вопроса: «сколько движок работает, не дозвонившись до нас» и «держит
    # ли этот контейнер слот тарифа прямо сейчас». Первый — терпимость к НАШЕЙ
    # аварии, и он остаётся 24 ч; второй — про клиента, и по нему слот убитого
    # контейнера держался 16–24 часа, а отказ предлагал «остановите лишний
    # контейнер», которого нет (Б26).
    #
    # ПЯТЬ ПЕРИОДОВ ОТЧЁТА. Движок 0.3.14+ шлёт `/v1/usage` раз в 120 с ПО
    # ТАЙМЕРУ, без всякой связи с трафиком — простаивающий контейнер тоже
    # отчитывается, — а один потерянный POST стоит полного периода (следующая
    # попытка через 120 с, разрыв 240 с). 600 с переживают три потери подряд с
    # запасом, а по инстансу сигнал ещё и кратно избыточен: отметку обновляет
    # КАЖДЫЙ воркер. Вверх от этого числа покупается только терпимость к нашему
    # же недоступному `/v1/usage`; вниз — время простоя клиента после падения.
    ALIVE_SECONDS = float(os.environ.get("PSEUDEX_ALIVE_SECONDS", "600"))
    # ЭХО УХОДА: НАСКОЛЬКО ПОЗЖЕ `/v1/release` ОТЧЁТ ЕЩЁ СЧИТАЕТСЯ ЕГО
    # СОБСТВЕННЫМ ХВОСТОМ, А НЕ ПРИЗНАКОМ ТОГО, ЧТО ПРОЦЕСС ПРОДОЛЖАЕТ РАБОТАТЬ.
    #
    # `LicenseClient.stop()` глушит цикл продления (join до 5 с) и только потом
    # зовёт `/v1/release`, поэтому отчёт ПОСЛЕ ухода бывает ровно один — тот,
    # что был в полёте, когда join истёк. Пульс идёт раз в 120 с, так что
    # работающий процесс всё равно объявится следующим тиком; 30 с отделяют
    # застрявший POST от работы и не дают атакующему ничего, кроме полуминуты.
    # Настраивается из окружения по той же причине, что и `ALIVE_SECONDS`:
    # стенд сжимает минуты в секунды, а замер потолка обязан гонять НАСТОЯЩИЙ
    # сервер, а не свою копию его арифметики.
    RELEASE_ECHO_SECONDS = float(
        os.environ.get("PSEUDEX_RELEASE_ECHO_SECONDS", "30"))
    # ПЕРВЫЙ ДВИЖОК, КОТОРЫЙ И ШЛЁТ ПУЛЬС, И НАЗЫВАЕТ СВОЮ ВЕРСИЮ. До 0.3.14
    # отчёт уходил только вместе с продлением, поэтому «молчит 10 минут» для
    # такого образа означает «работает и не имеет что сказать». Такие инстансы
    # считаются по-старому, по окну аренды: правило занятости не имеет права
    # останавливать чужой прод за то, чего его версия не умеет.
    #
    # ПОЧЕМУ 0.3.15, А НЕ 0.3.14. Пульс появился в 0.3.14 — и ровно в нём
    # `ENGINE_VERSION` ЗАХАРДКОЖЕН СТРОКОЙ «1.0.0» (проверено по тегу:
    # `pseudex/license.py:61`), потому что `version.txt` завели только в
    # D-053. То есть 0.3.14 присылает нам версию каждого образа ДО D-053 и по
    # строке неотличим от них. Ставить порог на 0.3.14 значило бы применить
    # новое правило к любому древнему образу — то есть отобрать слот у
    # работающего контейнера. Порог стоит на первой версии, которая себя
    # называет, а сам 0.3.14 ловится наблюдением ниже.
    LIVENESS_SINCE = (0, 3, 15)
    # ПУЛЬС, ДОКАЗАННЫЙ ПОВЕДЕНИЕМ, А НЕ ЗАЯВЛЕННЫЙ СТРОКОЙ.
    #
    # `POST /v1/usage` появился В 0.3.14 и не существует ни в одном образе до
    # него (проверено по тегам 0.3.12, 0.3.13 — ручку не зовёт никто). Старый
    # движок пишет строку `usage` ТОЛЬКО внутри запроса на аренду, поэтому у
    # него `usage.updated_at` никогда не бывает заметно новее последней аренды.
    # Отчёт, пришедший ОТДЕЛЬНО от аренды, — доказательство пульса, которое
    # подделать нечем: его ставим мы, своими часами.
    #
    # ОШИБКА ЗДЕСЬ ВОЗМОЖНА ТОЛЬКО В БЕЗОПАСНУЮ СТОРОНУ. Не увидев разрыва
    # (например, сразу после продления), мы считаем инстанс по окну — он всего
    # лишь подержит слот дольше. Обратное — счесть старый образ умеющим пульс и
    # отобрать слот у работающего — по построению невозможно.
    #
    # `meter.updated_at` для ЭТОГО непригоден, хотя и годится как признак
    # жизни: `/v1/meter` есть и в 0.3.12 — старый простаивающий контейнер,
    # однажды купивший ёмкость, был бы признан умеющим пульс и потерял бы слот.
    HEARTBEAT_PROOF_SECONDS = 60.0
    # ТЕМП ПЕРЕВЫДАЧИ СЛОТОВ — ЕДИНСТВЕННЫЙ НАСТОЯЩИЙ ОГРАНИЧИТЕЛЬ.
    #
    # Остывание слота на 300 с отсюда убрано: замер показал, что оно не
    # связывает никогда — бюджет (3 в час) жёстче его (12 в час) в 4–12 раз на
    # любом тарифе, и снятие остывания не меняет ни одного достижимого
    # сценария.
    #
    # ЕДИНИЦУ ТРАТИТ ДОПУСК, А НЕ ОСВОБОЖДЕНИЕ. Считать освобождения нельзя ни
    # одним способом: по строкам — честная остановка многоворкерного контейнера
    # выносит весь бюджет, по разным `instance_id` — карусель из двух имён
    # насыщает счётчик и он перестаёт связывать. Считается то, что ограничитель
    # и обязан ограничивать: появление НОВОГО обслуживающего контейнера на
    # месте, которое пришлось освободить, — чем бы оно ни освободилось.
    #
    # Потолок обхода = темп перевыдачи × время работы без связи с нами. Окно
    # занятости сокращается в 144 раза (24 ч -> 10 мин), а темп остаётся
    # прежним, поэтому потолок остаётся прежним.
    RELEASE_BUDGET_PER_HOUR = int(
        os.environ.get("PSEUDEX_RELEASE_BUDGET_PER_HOUR", "0")) or 0
    TURNOVER_WINDOW_SECONDS = 3600.0
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
        # `may_lease` считает `ceiling = allowed * 0 = 0` и отказывает клиенту в
        # ПЕРВОЙ ЖЕ аренде; нулевой `quantum_max` делает то же с ёмкостью.
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
                           reclaim_window_seconds: float = 86400.0) -> list[dict]:
        """Orgs whose meter looks like a SILENT or key-sharing engine, or whose
        containers keep LAPSING, for operator review — the fleet-wide surface the
        per-org signals never had (WS-6/M2).

        `unacked_quanta`: quanta served with no verified report. A root-patched engine
        that stopped calling /v1/meter shows here — it is already billed the floor
        (billing clamps acked into [granted-Q-R, granted]), so this DETECTS the pattern
        for review, it does not enforce. `ack_regressions`: reported usage went BACKWARDS
        under one process key — two engines on one key, or a replay. Aggregated per org
        over processes seen within the window. Attribution/deterrence, like the canary —
        the residual against a root client is bounded (the band) and now visible.

        `silent_reclaims`: сколько раз за сутки слот переходил к новому контейнеру
        потому, что прежний замолчал. Одно падение в сутки — это жизнь; больше
        перевыдач, чем инстансов по тарифу, — это либо карусель контейнеров, либо
        клиент, у которого контейнеры падают и он об этом не знает. И то и другое
        мы обязаны увидеть первыми, а не узнать из его письма.
        """
        now = time.time()
        cutoff = now - active_within_seconds
        rows = self._fetchall(
            "SELECT org_id, COALESCE(SUM(unacked_quanta),0), COALESCE(SUM(ack_regressions),0), "
            "COALESCE(SUM(granted),0), COALESCE(SUM(acked),0), COUNT(*) "
            "FROM meter WHERE updated_at >= ? GROUP BY org_id",
            (cutoff,))
        metered = {str(row[0]): row for row in rows}
        # НАБЛЮДЕНИЕ СЧИТАЕТ ТЕМИ ЖЕ ЕДИНИЦАМИ, ЧТО И ОГРАНИЧИТЕЛЬ. Считалось
        # `COUNT(DISTINCT instance_id)` по закрытым строкам — то есть карусель
        # из двух идентификаторов давала вечную двойку и в отчёт не попадала,
        # а перезапуск с шестнадцатью воркерами под одним `instance_id` был
        # виден единицей независимо от того, сколько раз он повторился.
        reclaims = {str(row[0]): int(row[1] or 0) for row in self._fetchall(
            "SELECT org_id, COUNT(*) FROM admissions WHERE at>=? GROUP BY org_id",
            (now - reclaim_window_seconds,))}
        out: list[dict] = []
        # ОРГАНИЗАЦИЯ С ПЕРЕВЫДАЧАМИ ПОПАДАЕТ СЮДА, ДАЖЕ ЕСЛИ ЕЁ СЧЁТЧИК МОЛЧИТ.
        # Ровно этот случай и интересен: контейнеры лапсируют, ёмкость не
        # покупается, и по одному только `meter` клиента не видно вовсе.
        for org_id in sorted(set(metered) | set(reclaims)):
            row = metered.get(org_id)
            unacked = int(row[1] or 0) if row else 0
            regressions = int(row[2] or 0) if row else 0
            granted = int(row[3] or 0) if row else 0
            acked = int(row[4] or 0) if row else 0
            procs = int(row[5] or 0) if row else 0
            taken = reclaims.get(org_id, 0)
            churn_floor = self.instances_allowed(self.org_plan(org_id))
            reasons = []
            if unacked >= min_unacked:
                reasons.append(f"silent: {unacked} quanta served with no verified report")
            if regressions >= min_regressions:
                reasons.append(f"{regressions} usage regression(s) — one key, two engines or replay")
            if taken > churn_floor:
                reasons.append(f"{taken} silent slot reclaim(s) in 24 h on a plan of "
                               f"{churn_floor} — containers lapsing or a carousel")
            if not reasons:
                continue
            out.append({"org_id": org_id, "unacked_quanta": unacked,
                        "ack_regressions": regressions, "granted": granted,
                        "acked": acked, "processes": procs,
                        "silent_reclaims": taken, "instances_allowed": churn_floor,
                        "reasons": reasons})
        out.sort(key=lambda a: a["unacked_quanta"] + a["ack_regressions"]
                 + a["silent_reclaims"], reverse=True)
        return out

    MIN_METER_INTERVAL_SECONDS = 1.0

    def metered_too_recently(self, org_id: str, pubkey: str, now: float) -> bool:
        """Просил ли этот процесс квант меньше секунды назад."""
        row = self._fetchone(
            "SELECT updated_at FROM meter WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        if row is None or row[0] is None:
            return False
        return now - float(row[0]) < self.MIN_METER_INTERVAL_SECONDS

    def issue_quantum(self, org_id: str, pubkey: str, plan: str,
                      acked: int | None, now: float) -> dict[str, int]:
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
                "prefetch_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, pubkey) DO UPDATE SET updated_at=excluded.updated_at, "
                "quantum_seq=excluded.quantum_seq, quantum_size=excluded.quantum_size, "
                "reserve=excluded.reserve, granted=excluded.granted, "
                "acked=excluded.acked, acked_at=excluded.acked_at, "
                "ack_trust=excluded.ack_trust, rate_per_second=excluded.rate_per_second, "
                "unacked_quanta=excluded.unacked_quanta, "
                "ack_regressions=meter.ack_regressions+excluded.ack_regressions, "
                "prefetch_at=excluded.prefetch_at",
                (org_id, pubkey, now, now, row["quantum_seq"] + 1, quantum, reserve,
                 granted, max(consumed, row["acked"]), now, trust_step, rate,
                 unacked, 1 if regressed else 0, prefetch_at))
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

    def _liveness_capable(self, engine_version: str, heard_apart: float) -> bool:
        """Умеет ли этот образ сам по себе говорить «я жив» — по ВЕРСИИ или по
        уже увиденному поведению.

        Пустая строка и «1.0.0» — это КАЖДЫЙ образ до D-053 И САМ 0.3.14:
        версии они не сообщают, а «1.0.0» парсится как цикл 1.0, то есть новее
        всего выпущенного, и читать его как новый нельзя
        (`registry.LEGACY_VERSION`). Поэтому вторым слагаемым идёт `heard_apart`
        — на сколько секунд отчёт обогнал последнюю аренду."""
        if heard_apart >= self.HEARTBEAT_PROOF_SECONDS:
            return True
        if not engine_version or engine_version == LEGACY_VERSION:
            return False
        return version_tuple(engine_version) >= self.LIVENESS_SINCE

    def _speaks_after_release(self, record: dict) -> bool:
        """ОТПУСТИЛ СЛОТ И ПРОДОЛЖАЕТ ГОВОРИТЬ — ЗНАЧИТ, НЕ ОТПУСКАЛ.

        `/v1/release` — непроверяемое заявление: отпустивший процесс держит
        запечатанный бандл до конца аренды и продолжает обслуживать. Проверить
        его нечем, ЗАСЛУШАТЬ — можно: чтобы обслужить хоть один запрос сверх
        предоплаченного кванта, движок обязан прийти за ёмкостью
        (`license.has_capacity` — ноль `granted` перестал быть безлимитом), а
        отчёт о потреблении уходит своим таймером раз в 120 с. Обе отметки
        ставит СЕРВЕР.

        Отсюда и разделение, которого иначе нет ни в одном поле: честно
        остановленный контейнер замолкает навсегда — его место свободно в ту же
        секунду, и документированный редеплой остаётся мгновенным; контейнер,
        который «ушёл» и продолжает работать, слышно, и место он занимает.

        Без этого правила снятие платы за возврат на СВОЙ слот (Б26ter)
        осталось бы вообще без ограничителя: цикл «аренда — release — аренда»
        под одним `instance_id` выдавал бы запечатанные бандлы со скоростью
        сети. Правило названо ещё в Б26 («кто продолжает отчитываться после
        release — снова занимает слот») и до этого прохода не было реализовано.
        """
        if not record["last_release"]:
            return False
        return record["heard"] > record["last_release"] + self.RELEASE_ECHO_SECONDS

    def _occupancy(self, org_id: str, window_seconds: float,
                   alive_seconds: float, now: float) -> tuple[list[dict], dict[str, dict]]:
        """КТО ЗАНИМАЕТ СЛОТЫ ЭТОЙ ОРГАНИЗАЦИИ ПРЯМО СЕЙЧАС — одно определение.

        Их было два, и они расходились: `may_lease` считала занятым всякого,
        кто брал аренду за сутки, а `active_instances` в ту же секунду
        показывала «остывает» — то есть отказ и кабинет говорили клиенту
        разное про один и тот же контейнер.

        ДВЕ ЗАНЯТОСТИ, ДВА СРОКА, И ПУТАТЬ ИХ НЕЛЬЗЯ — ТРИ ЗАХОДА СЛОМАЛИСЬ
        ИМЕННО ОБ ЭТО (Б26quater):

          * СЛОТ КОНТЕЙНЕРА (`instances[…]['occupies']`) — на ПРИЗНАКЕ ЖИЗНИ,
            T_alive = 600 с. Это и была жалоба Б26: упавший контейнер держал
            слот до суток, и отказ предлагал остановить то, чего нет;
          * МЕСТО РАБОЧЕГО ПРОЦЕССА (`processes[…]['holds_place']`) — на ОКНЕ
            АРЕНДЫ, как в базе: ключ занимает место, пока в окне стоит хоть
            одна его строка, чем бы он аренду ни закончил.

        Тариф продаётся контейнерами, а принуждается и тем, и другим, потому
        что `instance_id` выбирает клиент, а ключ процесса — нет. Перевести
        второе на признак жизни значит умножить потолок тарифа на
        `T_offline / T_alive`.

        ЗАНЯТ — ЗНАЧИТ НЕДАВНО ВИДЕЛИ, и видели ПО НАШИМ ЧАСАМ: все четыре
        отметки ставит сервер, поэтому подкрученные часы контейнера в
        занятость не входят вообще. Источники признака жизни:

          * `leases.issued_at`   — продление (раз в TTL/3, до 8 часов);
          * `usage.updated_at`   — отчёт о потреблении, раз в 120 с по таймеру
                                   у движка 0.3.14+, по инстансу;
          * `process_reports.updated_at` — тот же отчёт, но по КЛЮЧУ ПРОЦЕССА:
                                   `instance_id` выбирает клиент, ключ — нет;
          * `meter.updated_at`   — покупка кванта ёмкости. Без неё контейнер
                                   не обслуживает, поэтому «молчу, но работаю»
                                   перестаёт быть состоянием: чтобы работать,
                                   процесс обязан прийти за ёмкостью, а придя —
                                   отметиться живым.

        ОТПУЩЕННЫЙ СЛОТ СВОБОДЕН, ПОКА ЕГО ХОЗЯИН МОЛЧИТ. `release` —
        заявление, а не факт, поэтому оно действует ровно до первого слова
        после него (`_speaks_after_release`).

        ПРИЗНАК ЖИЗНИ ПРОЦЕССА — ТОЛЬКО ЕГО СОБСТВЕННЫЙ. `usage` пишется по
        инстансу, то есть любым воркером; сложив его в признак жизни КЛЮЧА, мы
        бы считали живыми ключи мёртвых воркеров, пока жив хоть один сосед, —
        то есть печатали бы оператору «живых 32» у контейнера с одним рабочим
        процессом.

        Возвращает (инстансы, процессы). Миграции не нужны: все четыре таблицы
        и все индексы под этот запрос уже существуют.
        """
        cutoff = now - window_seconds
        alive_from = now - alive_seconds
        rows = self._fetchall(
            "SELECT l.instance_id, COALESCE(l.pubkey, ''), l.issued_at, l.released_at, "
            "COALESCE(l.released_by, ''), COALESCE(l.engine_version, ''), "
            "COALESCE(u.updated_at, 0), COALESCE(p.updated_at, 0), "
            "COALESCE(m.updated_at, 0) "
            "FROM leases l "
            "LEFT JOIN usage u ON u.org_id=l.org_id AND u.instance_id=l.instance_id "
            "LEFT JOIN process_reports p ON p.org_id=l.org_id AND p.pubkey=l.pubkey "
            "LEFT JOIN meter m ON m.org_id=l.org_id AND m.pubkey=l.pubkey "
            "WHERE l.org_id=? AND l.issued_at>=? ORDER BY l.issued_at",
            (org_id, cutoff),
        )
        instances: dict[str, dict] = {}
        processes: dict[str, dict] = {}
        for (instance_id, pubkey, issued_at, released_at, released_by,
             engine_version, seen_usage, seen_report, seen_meter) in rows:
            issued = float(issued_at or 0.0)
            # СКАЗАННОЕ ОТДЕЛЬНО ОТ АРЕНДЫ. Аренду процесс берёт сам и в момент
            # ухода тоже, поэтому «говорил ли он ПОСЛЕ release» считается только
            # по отметкам, которые ставит отчёт и покупка ёмкости.
            spoke = max(float(seen_report or 0.0), float(seen_meter or 0.0))
            key_seen = max(issued, spoke)
            record = instances.setdefault(instance_id, {
                "instance_id": instance_id, "last_lease": 0.0, "last_seen": 0.0,
                "reported": 0.0, "engine_version": "", "open_rows": 0,
                "heard": 0.0, "last_release": 0.0, "released_by": ""})
            record["last_lease"] = max(record["last_lease"], issued)
            record["last_seen"] = max(record["last_seen"], key_seen,
                                      float(seen_usage or 0.0))
            record["heard"] = max(record["heard"], spoke, float(seen_usage or 0.0))
            # ТОЛЬКО `usage`: см. HEARTBEAT_PROOF_SECONDS — `meter` есть и у
            # старых образов, а `/v1/usage` нет ни у одного.
            record["reported"] = max(record.get("reported", 0.0),
                                     float(seen_usage or 0.0))
            # ВЕРСИЯ НОВЕЙШЕЙ АРЕНДЫ, не строковый максимум: строки приходят от
            # старых к новым, поэтому последняя записанная и есть новейшая.
            record["engine_version"] = str(engine_version)
            if released_at is None:
                record["open_rows"] += 1
            else:
                # ПРИЧИНА ПОСЛЕДНЕГО УХОДА ЕДЕТ НА ЭКРАН. `released` покрывает
                # три разных события — клиент остановил контейнер сам
                # (`process`), место у молчащего забрали мы (`silence`), слот
                # освободила поддержка (`admin`), — и клиенту это три разные
                # новости. Без этого поля витрина показывала отобранное место
                # как «вы сами остановили»: она читает `released_by`
                # (`storefront/billing/slots.py::_state_of`), а сервер его не
                # отдавал, поэтому охраняющая проверка не могла упасть.
                if float(released_at) >= record["last_release"]:
                    record["released_by"] = str(released_by)
                record["last_release"] = max(record["last_release"],
                                             float(released_at))
            if not pubkey:
                continue
            process = processes.setdefault(pubkey, {
                "pubkey": pubkey, "owners": [], "open": False, "reclaimed": False,
                "last_seen": 0.0, "heard": 0.0, "last_release": 0.0,
                "rows": 0, "rows_by_admin": 0, "last_lease": 0.0})
            if instance_id not in process["owners"]:
                process["owners"].append(instance_id)
            process["last_seen"] = max(process["last_seen"], key_seen)
            process["heard"] = max(process["heard"], spoke)
            process["last_lease"] = max(process["last_lease"], issued)
            process["rows"] += 1
            if released_at is None:
                process["open"] = True
            else:
                process["last_release"] = max(process["last_release"],
                                              float(released_at))
                if released_by == "silence":
                    # СЛОТ ОТОБРАЛИ МЫ, И ЭТО ТЕРМИНАЛЬНО ДЛЯ КЛЮЧА. Отметка
                    # читается в `_admission`: отобранный ключ теряет быстрый
                    # путь и получает 409 на следующем продлении.
                    process["reclaimed"] = True
                elif released_by == "admin":
                    # НАШ СОБСТВЕННЫЙ РЫЧАГ — ЕДИНСТВЕННОЕ, ЧТО ОСВОБОЖДАЕТ
                    # МЕСТО ПРОЦЕССА ДОСРОЧНО. См. `holds_place` ниже.
                    process["rows_by_admin"] += 1
        for record in instances.values():
            capable = self._liveness_capable(
                record["engine_version"], record["reported"] - record["last_lease"])
            record["liveness"] = capable
            # ОТПУЩЕННЫЙ СЛОТ СВОБОДЕН СРАЗУ. Остывание убрано: оно не
            # связывало (бюджет перевыдачи жёстче в 4–12 раз), а платил за него
            # тот, кто честно остановил контейнер и поднялся на новом томе.
            record["released"] = (record["open_rows"] == 0
                                  and not self._speaks_after_release(record))
            record["occupies"] = (not record["released"]
                                  and (record["last_seen"] >= alive_from if capable else True))
        for process in processes.values():
            # МЕСТО ПРОЦЕССА ДЕРЖИТСЯ ОКНОМ АРЕНДЫ, А НЕ ОКНОМ МОЛЧАНИЯ, И ЭТО
            # РОВНО БАЗОВАЯ АРИФМЕТИКА (Б26quater).
            #
            # Признак жизни правит слотом КОНТЕЙНЕРА — это и была жалоба Б26:
            # упавший контейнер держал слот сутки. Потолок РАБОЧИХ ПРОЦЕССОВ
            # внутри контейнера на признак жизни переводить нельзя, и цена
            # этого измерена на трёх заходах: поколение из 32 ключей
            # переоткрывалось каждые T_alive, то есть один допуск покупал 32
            # обслуживающих процесса против базовой единицы, а цикл
            # «аренда → /v1/release» под ОДНИМ `instance_id` не ограничивался
            # вообще (база отказывала на 35-м). Оба обхода живут одной и той же
            # арифметикой: `потолок × (T_offline / период переоткрытия)`.
            # Сделать период короче суток — значит умножить потолок тарифа на
            # отношение суток к этому периоду, чем бы период ни назывался.
            #
            # Поэтому: ключ занимает место, пока в окне аренды стоит хоть
            # одна его строка. Ни молчание, ни `/v1/release` места не освобождают —
            # «ушёл» и «замолчал» суть заявления о будущем, а запечатанный
            # бандл у процесса в памяти действителен до `ttl + grace` при любом
            # из них. Единственное досрочное освобождение — НАШЕ: `/admin/release`
            # (`released_by='admin'`), потому что его выполняем мы, а не клиент,
            # и оно и в базе удаляло строки.
            #
            # ЧЕМ ЗА ЭТО ПЛАТИТ ЧЕСТНЫЙ КЛИЕНТ, СКАЗАНО ВСЛУХ: ключи мёртвых
            # воркеров держат места до конца окна, поэтому контейнер на 16
            # воркеров при тарифе в один контейнер поднимается заново один раз,
            # а не десять (E8). Это поведение выпущенного 0.3.17, а не регресс
            # относительно него; отказ обязан назвать срок и действие
            # (`_refuse_processes`).
            process["holds_place"] = process["rows"] > process["rows_by_admin"]
            # КОГДА МЕСТО ОСВОБОДИТСЯ САМО — по ПОСЛЕДНЕЙ аренде ключа, а не
            # по первой: окно отбирает строки по `issued_at`, и пока в нём
            # стоит хоть одна строка ключа, место занято. Продлевавшийся ключ
            # держит место дольше, и обещать по первой аренде значило бы
            # назвать клиенту срок, который наступит раньше освобождения.
            process["frees_at"] = process["last_lease"] + window_seconds
            # Правило ключа — правило его инстанса. Пока ХОТЯ БЫ ОДИН из
            # назвавших его образов не умеет пульс, ключ считается живым по
            # окну: иначе мы бы применили к старому движку срок, которого он не
            # знает. ЭТО НЕ ПОТОЛОК, а то, что показывается оператору и клиенту
            # («живых процессов N»): сколько воркеров мы СЛЫШИМ.
            capable = all(instances[owner]["liveness"] for owner in process["owners"])
            process["alive"] = ((process["open"] or self._speaks_after_release(process))
                                and (process["last_seen"] >= alive_from if capable else True))
        ordered = sorted(instances.values(), key=lambda r: r["last_lease"], reverse=True)
        return ordered, processes

    def active_instances(self, org_id: str, window_seconds: int) -> list[dict]:
        """The instances currently holding a slot, newest lease first.

        The plan is sold in containers and the limit is enforced on them, but
        there was nowhere to SEE them: a persona whose single slot was held by a
        container they had already deleted was told to «остановите лишний
        контейнер или перейдите на больший тариф» — asked to stop something that
        did not exist and offered a more expensive plan as the remedy.

        ЧТО ВИДИТ ПОДДЕРЖКА, ТО И ПРИМЕНЯЕТСЯ: и здесь, и в `may_lease` занятость
        считает `_occupancy`, поэтому третьего мнения о том же контейнере больше
        нет. Три состояния:

          * `active`   — занимает слот (признак жизни свежее T_alive, а для
                         образов до 0.3.14 — аренда в окне);
          * `silent`   — аренда не отпущена, но признака жизни нет: слот УЖЕ
                         свободен, и труп больше не показан работающим;
          * `released` — контейнер отпустил слот сам (и с тех пор молчит), мы
                         признали его замолчавшим или слот освободила
                         поддержка. Отпустивший и продолжающий работать стоит
                         здесь `active`: заявление об уходе действует до
                         первого слова после него.

        КОТОРОЕ ИЗ ТРЁХ — ГОВОРИТ `released_by`, и без него экран врал. Одно
        слово `released` покрывает «вы остановили контейнер» (`process`), «мы
        забрали место у молчащего» (`silence`) и «поддержка освободила слот»
        (`admin`); клиенту это три разные новости, и во втором случае его
        движок ещё работает, но встанет на следующем продлении. Витрина эту
        развилку уже умеет (`storefront/billing/slots.py::_state_of`) — поля не
        было в ответе.

        `free_at` — когда слот освободится САМ, если больше ничего не услышим;
        `None` там, где сказать нечего (старый образ не шлёт признак жизни).
        """
        now = time.time()
        instances, processes = self._occupancy(org_id, window_seconds,
                                               self.ALIVE_SECONDS, now)
        listed = []
        for record in instances:
            if record["occupies"]:
                state = "active"
            elif record["released"]:
                state = "released"
            else:
                state = "silent"
            mine = [process for process in processes.values()
                    if record["instance_id"] in process["owners"]]
            live_processes = sum(1 for process in mine if process["alive"])
            held_places = sum(1 for process in mine if process["holds_place"])
            listed.append({"instance_id": record["instance_id"],
                           "last_lease": record["last_lease"],
                           "last_seen": record["last_seen"],
                           "state": state,
                           # ПОЧЕМУ МЕСТО СВОБОДНО — СЛОВОМ, А НЕ ДОГАДКОЙ
                           # ЭКРАНА: `process` клиент сделал сам, `silence` —
                           # забрали мы, `admin` — освободила поддержка. Пустая
                           # строка значит «не отпускал».
                           "released_by": record["released_by"],
                           # ЗАНЯТОСТЬ ОТДАЁТСЯ ЧИСЛОМ, А НЕ ВЫВОДИТСЯ ИЗ
                           # НАЗВАНИЯ СОСТОЯНИЯ: считает её одна функция, и
                           # витрина обязана складывать «занято» по этому полю,
                           # а не по длине списка.
                           "occupies": record["occupies"],
                           "free_at": (record["last_seen"] + self.ALIVE_SECONDS
                                       if record["occupies"] and record["liveness"]
                                       else None),
                           # ДВА РАЗНЫХ ЧИСЛА, И ОБА НУЖНЫ, ПОТОМУ ЧТО ОТКАЗ
                           # СЧИТАЕТ НЕ ТО, ЧТО ЭКРАН ПОКАЗЫВАЕТ.
                           # `live_processes` — сколько воркеров мы СЛЫШИМ
                           # (это и есть «работает ли контейнер»);
                           # `held_places` — сколько мест под потолком тарифа
                           # заняли его ключи, включая мёртвые: место держится
                           # до конца окна аренды. Показать одно и отказать по
                           # другому — это и есть «два мнения об одном
                           # контейнере», которыми этот файл уже платил.
                           "live_processes": live_processes,
                           "held_places": held_places,
                           "engine_version": record["engine_version"]})
        return listed

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

    def release_instance(self, org_id: str, instance_id: str) -> bool:
        """Give a slot back before its window expires. Operator lever.

        A release happens on every `docker stop`, which is every deploy, and a
        customer who recreated a volume is a NEW instance by construction — so
        without this they wait out the whole window to run the product they are
        paying for. A persona client called that disqualifying for production
        and they were right.

        ONE DEFINITION, UNDER THE SAME LOCK AS EVERY OTHER WRITE. There were two
        of these, and the second silently replaced the first: same name, same
        class, different return type and different locking. The survivor was the
        one that wrote under `with self._conn` instead of `self._lock`, which
        made slot release the only unserialized writer on a connection opened
        `check_same_thread=False` — while `devserver.py` runs the admin app on a
        second thread.

        ПОМЕТКА, А НЕ УДАЛЕНИЕ, И ЭТО ЕДИНСТВЕННОЕ ДОСРОЧНОЕ ОСВОБОЖДЕНИЕ МЕСТ.
        Удаляя строки, мы стирали и сам факт: экран показывал контейнер
        исчезнувшим, а клиенту оставалось гадать, кто его остановил. Теперь
        причина уезжает в `active_instances` словом `admin` — «слот освободила
        поддержка», — и это третья новость, отличная от «вы остановили» и «мы
        забрали». `released_by='admin'` ставится и поверх уже закрытых строк:
        оператор говорит «этого контейнера нет», и места его рабочих процессов
        обязаны освободиться СРАЗУ, чем бы они ни были закрыты раньше
        (`_occupancy::holds_place`). Это и есть наш ручной рычаг для клиента,
        который упёрся в потолок процессов после нескольких перезапусков.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE leases SET released_at=COALESCE(released_at, ?), "
                "released_by='admin' WHERE org_id=? AND instance_id=? "
                "AND COALESCE(released_by, '')<>'admin'",
                (time.time(), org_id, instance_id))
            self._conn.commit()
        return cursor.rowcount > 0

    # ОТКАЗ ОБЯЗАН НАЗВАТЬ ПУТЬ, КОТОРЫЙ РАБОТАЕТ, И НЕ НАЗЫВАТЬ ТОГО, КОТОРЫЙ
    # НЕ РАБОТАЕТ. Эта строка — `detail` ответа 409, и уже выпущенные движки
    # печатают её ДОСЛОВНО (`service.py::_lifespan`, `proxy.py`), поэтому она
    # доезжает до клиента без единого релиза движка. Вторая строка, статическая
    # (`license.REMEDIES`), едет с образом и здесь не исправима.
    # ВЕРДИКТ, КОТОРЫЙ НИКОГО НЕ ПОДВИНУЛ. Хвост общий, потому что забыть его
    # — значит списать единицу за допуск, который ничего не освобождал, и
    # именно так бюджет и оказался на стороне освобождения.
    _NOTHING_TAKEN = {"reclaim": ""}

    _REDEPLOY_HINT = (" Если это переразвёртывание, поднимите контейнер НА ТОМ ЖЕ "
                      "ТОМЕ (-v pseudex-data:/data): он сохранит свой идентификатор "
                      "и займёт слот сразу.")

    def _refuse_occupied(self, occupying: list[dict], allowed: int,
                         window_seconds: float, now: float) -> str:
        """Слот занят — и ЧЕМ ИМЕННО занят, решает, какую фразу здесь можно
        писать.

        «Остановите лишний контейнер» — правда только про тот, который на
        связи. Про контейнер на движке до 0.3.15 мы не знаем ровно ничего: он
        не шлёт признак жизни, его слот держится до конца аренды, и если он
        УЖЕ остановлен или упал, то «остановите» — совет сделать то, что
        клиент сделал. Это и есть Б26 в его исходном виде, и печатать его
        здесь снова нельзя.
        """
        alive = [record for record in occupying if record["liveness"]]
        legacy = [record for record in occupying if not record["liveness"]]
        parts = [f"тариф допускает {allowed} контейнер(ов), занято "
                 f"{len(occupying)}."]
        if alive:
            named = ", ".join(f"{record['instance_id']} (на связи "
                              f"{ago(now - record['last_seen'])} назад)"
                              for record in alive[:3])
            # «ОСТАНОВИТЕ ЛИШНИЙ» ВЕРНО, ПОКА КОНТЕЙНЕР ЖИВ, А ЖИВ ОН ДЛЯ НАС
            # ЕЩЁ T_alive ПОСЛЕ СМЕРТИ. Контейнер, убитый минуту назад, стоит
            # здесь как работающий — и без второй фразы клиент опять читает
            # совет остановить то, чего нет. Срок считается по тому, кто
            # замолчит раньше всех: он и освободит слот.
            soonest = min(record["last_seen"] for record in alive)
            frees_in = max(0.0, soonest + self.ALIVE_SECONDS - now)
            parts.append(f"На связи: {named} — остановите лишний, слот "
                         f"освободится сразу. Если он уже остановлен или упал, "
                         f"слот освободится сам через {int(frees_in // 60) + 1} мин "
                         f"молчания.")
        if legacy:
            # СРОК НАЗЫВАЕТСЯ ПО САМОЙ ПОЗДНЕЙ АРЕНДЕ: раньше него не
            # освободится ни один из них, и обещать меньшее значит обещать то,
            # чего не будет.
            latest = max(record["last_lease"] for record in legacy)
            # ВЕРСИЯ У КАЖДОГО СВОЯ. Одна на всех была бы наугад: в списке
            # может стоять и пустая строка, и «1.0.0», и 0.3.13.
            named = ", ".join(f"{record['instance_id']} "
                              f"({record['engine_version'] or 'версия не сообщается'})"
                              for record in legacy[:3])
            parts.append(
                f"Слот держат {named}: движок до 0.3.15 не сообщает признак "
                f"жизни, поэтому его слот занят до конца аренды (ещё "
                f"{ago(latest + window_seconds - now)}) — даже если контейнер уже "
                f"остановлен или упал. Корректная остановка (docker stop) "
                f"освобождает слот сразу; обновите движок (pseudexctl upgrade), и "
                f"упавший контейнер будет отдавать слот через "
                f"{int(self.ALIVE_SECONDS // 60)} минут молчания.")
        parts.append(f"Или смените тариф в личном кабинете.{self._REDEPLOY_HINT}")
        return " ".join(parts)

    def _refuse_reclaimed(self, held: dict, now: float) -> str:
        """Место этого процесса уже отдано, и продлевать его аренду нельзя.

        ЧТО ЭТО ЗНАЧИТ ДЛЯ РАБОТАЮЩЕГО КОНТЕЙНЕРА, СКАЗАНО ВСЛУХ: строка едет в
        409 `instance_limit`, а он входит в `_ANSWER_CODES` КАЖДОГО выпущенного
        движка (`pseudex/license.py`) — то есть это ОТВЕТ, а не наш сбой, и
        grace к нему не применяется. Воркер, получивший его на продлении,
        выгружает бандл и перестаёт маскировать: `/mask` отвечает 503, запросы
        блокируются, персональные данные никуда не уходят. Именно это и
        требуется: отбор обязан обесценивать, иначе отобранное поколение
        продлевается вечно и тариф обходится накоплением (Б26ter).

        Поэтому отказ обязан назвать ДЕЙСТВИЕ, а не только запрет: перезапуск
        даёт процессу новый ключ, и на свободном тарифе он поднимется сразу.
        """
        return (f"место этого рабочего процесса уже отдано другому запуску: он "
                f"молчал дольше {int(self.ALIVE_SECONDS // 60)} мин (последний "
                f"признак жизни {ago(now - held['last_seen'])} назад) и был "
                f"признан остановленным. Продлить отобранную аренду нельзя — "
                f"иначе на тарифе копились бы поколения рабочих процессов. "
                f"Перезапустите контейнер (docker restart): его процессы возьмут "
                f"новые места, если тариф их допускает.{self._REDEPLOY_HINT}")

    def _refuse_turnover(self, org_id: str, lapsed: list[dict],
                         allowed: int, spent: int, budget: int, now: float) -> str:
        """Слот свободен, но за час он уже переходил столько раз, сколько можно.

        СРОК — ЭТО КОГДА РАЗБЛОКИРУЕТСЯ КЛИЕНТ, А НЕ КОГДА ВЫПАДЕТ ОДНА
        ЕДИНИЦА. Печаталось второе: при `spent` выше бюджета (тариф понизили,
        несколько допусков подряд) выпадение самой старой единицы не пускало
        никого, клиент приходил в названную минуту и получал тот же отказ.
        Нужно, чтобы выпало `spent − budget + 1`.
        """
        needed = spent - budget + 1
        frees_in = max(0.0, self.turnover_frees_at(org_id, needed) - now)
        oldest = min(lapsed, key=lambda record: record["last_seen"])
        # ОТПУСТИЛ, ЗАМОЛЧАЛ И «МЫ ЗАБРАЛИ» — ТРИ РАЗНЫХ СОБЫТИЯ, И КЛИЕНТ
        # ЗНАЕТ, КОТОРОЕ СЛУЧИЛОСЬ. «Молчит 0 с» про контейнер, который сам
        # сказал «я ухожу», — та же ложь, что «остановите лишний» про труп,
        # только в другую сторону; а «отпустил слот» про контейнер, чьи строки
        # закрыли МЫ (`reclaim_silent`), — ровно то враньё, из-за которого
        # экрану и понадобился `released_by`. Признак «строк не осталось»
        # одинаков во всех трёх случаях, поэтому спрашивается ПРИЧИНА.
        if oldest["released_by"] == "process":
            gone = "отпустил слот"
        elif oldest["released_by"] == "admin":
            gone = "освобождён поддержкой"
        else:
            gone = (f"молчит {ago(now - oldest['last_seen'])} и больше не "
                    f"считается работающим")
        what = (f"прежний контейнер ({oldest['instance_id']}) {gone}, но "
                f"занять его слот")
        return (f"тариф допускает {allowed} контейнер(ов), и {what} "
                f"сейчас нельзя: за последний час слот уже переходил к новому "
                f"контейнеру {spent} раз(а) при потолке {budget} — иначе тариф "
                f"обходится каруселью контейнеров. Слот освободится через "
                f"{int(frees_in // 60) + 1} мин.{self._REDEPLOY_HINT} "
                f"Переразвёртывание на том же томе бюджет не тратит.")

    def _refuse_processes(self, held: list[dict], allowed: int, ceiling: int,
                          now: float) -> str:
        """Потолок МЕСТ РАБОЧИХ ПРОЦЕССОВ. Этот отказ не объяснялся ничем:
        клиент читал про «рабочие процессы» — слово, которого нет ни на одном
        его экране, — и не мог знать ни что это, ни когда отпустит.

        ОН ОБЯЗАН НАЗВАТЬ СРОК, ПОТОМУ ЧТО СРОК ЗДЕСЬ ДЛИННЫЙ. Место ключа
        держится до конца окна аренды (Б26quater), а не до конца молчания:
        контейнер на много воркеров, поднявшийся заново, занимает вторую пачку
        мест, и третья упрётся сюда. Клиент, который этого не знает, читает
        отказ как поломку — поэтому здесь и срок освобождения, и три действия,
        которые работают СЕЙЧАС: меньше воркеров, больший тариф или поддержка
        (`POST /admin/release` — единственное досрочное освобождение мест).
        """
        owners = {owner for process in held for owner in process["owners"]}
        named = ", ".join(sorted(owners)[:3])
        # КОГДА ОСВОБОДИТСЯ ПЕРВОЕ МЕСТО — по самому старому ключу: раньше него
        # не освободится ни одно, и назвать меньшее значило бы пообещать то,
        # чего не будет.
        soonest = min(process["frees_at"] for process in held) if held else now
        # БЕЗ ПОДСКАЗКИ ПРО ТОТ ЖЕ ТОМ. Она про слот КОНТЕЙНЕРА, а здесь
        # кончились места РАБОЧИХ ПРОЦЕССОВ: клиент чаще всего уже на своём
        # томе, и совет сделать сделанное — ровно та болезнь Б26, которую этот
        # файл лечит.
        return (f"тариф допускает {allowed} контейнер(ов) — это {ceiling} рабочих "
                f"процесса(ов), и все места заняты ({len(held)}"
                f"{f', инстанс {named}' if named else ''}). Место рабочего процесса "
                f"держится до конца его аренды, даже если процесс уже остановлен: "
                f"первое освободится через {ago(max(0.0, soonest - now))}. "
                f"Если это повторный перезапуск многоворкерного контейнера — "
                f"уменьшите PSEUDEX_WORKERS или смените тариф в личном кабинете; "
                f"если контейнер нужно поднять немедленно, напишите в поддержку: "
                f"мы освобождаем места вручную.")

    def _admission(self, org_id: str, plan: str, instance_id: str,
                   window_seconds: float, pubkey: str, now: float) -> dict:
        """Пускать ли этот контейнер, что ему сказать и ЧЕЙ слот при этом
        переходит к нему — одно решение и одна его причина.

        Отдельно от `may_lease`, потому что перевыдача слота — это ЗАПИСЬ, а
        предикат обязан оставаться предикатом: `may_lease` зовут и тесты, и
        `/admin`, и списать единицу бюджета на вопрос «а можно было бы?» нельзя.
        Пометку делает `lease_if_allowed`, в той же критической секции, что и
        саму аренду.
        """
        instances, processes = self._occupancy(org_id, window_seconds,
                                               self.ALIVE_SECONDS, now)
        # ПРОДЛЕНИЕ ДЕЙСТВУЮЩЕЙ АРЕНДЫ НЕ МОЖЕТ БЫТЬ ОТКАЗАНО. Ключ процесса
        # создаётся один раз в конструкторе клиента и живёт, пока живёт
        # процесс, поэтому «этот ключ уже держит слот» — точный признак
        # продления, а не нового контейнера. Быстрый путь стоит на ОКНЕ АРЕНДЫ,
        # а не на признаке жизни: движок, у которого потерялись отчёты, обязан
        # продлиться, иначе мы убьём работающий контейнер своей бухгалтерией.
        #
        # НО ОТОБРАННЫЙ КЛЮЧ БЫСТРОГО ПУТИ НЕ ИМЕЕТ, И ЭТО ГЛАВНОЕ ЗДЕСЬ.
        # Раньше он его имел: `silence` читался как «мы ошиблись, он работал»,
        # и поколение, у которого забрали места, продлевалось вечно. Замер: 128
        # живых аренд на тарифе в ОДИН контейнер после трёх единиц бюджета, и
        # число росло — то есть отбор не обесценивал ничего, а бюджет покупал
        # новые поколения, не отнимая старых (Б26ter). Отбор обязан
        # ОБЕСЦЕНИВАТЬ: честный движок встаёт, а не копится.
        held = processes.get(pubkey) if pubkey else None
        if held is not None and held["reclaimed"]:
            return {"allowed": False, **self._NOTHING_TAKEN,
                    "detail": self._refuse_reclaimed(held, now)}
        if held is not None and held["open"]:
            # КЛЮЧ ПРИВЯЗАН К ПЕРВОМУ НАЗВАВШЕМУ ЕГО ИНСТАНСУ. Без этого быстрый
            # путь пропускал пятьсот контейнеров, предъявивших ОДИН ключ.
            owners = held["owners"]
            if owners and instance_id not in owners:
                _log.warning("process key reused across instance ids for org=%s: "
                             "%s now claimed by %r, first seen under %r",
                             org_id, pubkey[:12], instance_id, sorted(owners)[:3])
                return {"allowed": False, **self._NOTHING_TAKEN, "detail": (
                    "этот рабочий процесс уже учтён под другим идентификатором "
                    "контейнера. Перезапустите контейнер.")}
            return {"allowed": True, **self._NOTHING_TAKEN, "detail": ""}
        allowed = self.instances_allowed(plan)
        ceiling = allowed * self.processes_allowed(plan)
        occupying = [record for record in instances if record["occupies"]]
        mine = next((record for record in instances
                     if record["instance_id"] == instance_id), None)
        reclaim = ""
        if mine is None or not mine["occupies"]:
            # СТАРАЯ ГРАНИЦА ОСТАЁТСЯ ВЕРХНЕЙ. Клиент, который честно называет
            # свои контейнеры, упирается в неё раньше и читает про контейнеры,
            # а не про процессы.
            if len(occupying) >= allowed:
                return {"allowed": False, **self._NOTHING_TAKEN,
                        "detail": self._refuse_occupied(occupying, allowed,
                                                        window_seconds, now)}
            # ЛАПСИРОВАВШИЕ — ЭТО И ОТПУСТИВШИЕ, И ЗАМОЛЧАВШИЕ, ПО ОДНОЙ ЦЕНЕ.
            # Считать только молчание значило бы отдавать карусель через
            # `/v1/release` даром; считать только `/v1/release` — отдавать её
            # даром тому, кто просто замолкает. Причина ухода не меняет того,
            # что слот пришлось освободить.
            #
            # СЕБЯ В ЭТОТ СПИСОК НЕ БЕРЁМ НИКОГДА, И ЭТО ВЕСЬ «ПЕРЕЗАПУСК НА
            # ТОМ ЖЕ ТОМЕ БЕСПЛАТЕН»: инстанс, который возвращается на СВОЁ
            # место, не вытесняет никого, чем бы он его ни освободил — падением
            # или корректной остановкой. Это и случай Б26 (OOM, kill, ребут
            # хоста), и документированное обновление (`docker compose up -d`,
            # `pseudexctl upgrade`), которое идёт через `/v1/release`.
            #
            # ОТПУСТИВШИЙ СЕБЯ ЗДЕСЬ СТОЯЛ, И ЭТО БЫЛА ПЛОСКАЯ ОШИБКА: каждый
            # редеплой списывал единицу, и ПЯТЫЙ `docker compose up -d` за час
            # получал 409 (замер). Документированная команда обновления не может
            # стоить бюджета (Б26ter).
            #
            # Чем тогда связан цикл «аренда — release — аренда» под одним
            # именем, за который эта строка и платила: тем, что МЕСТО КЛЮЧА
            # держится до конца окна аренды (`holds_place`), а не до конца
            # молчания. Ключей у тарифа конечное число, круг тратит по ключу за
            # оборот — и упирается ровно в ту же арифметику, что в базе.
            lapsed = [record for record in instances
                      if not record["occupies"]
                      and record["instance_id"] != instance_id]
            if len(occupying) + len(lapsed) >= allowed:
                reclaim = min(lapsed,
                              key=lambda record: record["last_seen"])["instance_id"]
        # МЕСТА ПРОЦЕССОВ СЧИТАЮТСЯ ПО ОКНУ АРЕНДЫ, И БЮДЖЕТ ИХ НЕ ПОКУПАЕТ.
        #
        # Здесь стояло обратное — места молчащих ключей переоткрывались одним
        # допуском за единицу бюджета, — и замер назвал цену: единица покупала
        # 32 обслуживающих процесса против базовой единицы, а круг «аренда →
        # /v1/release» под одним `instance_id` не тратил ничего и не
        # ограничивался ничем. Потолок нельзя ставить на окно молчания ни за
        # какую цену: `потолок × T_offline / T_alive` — это умножение тарифа на
        # 432 (Б26quater).
        #
        # Поэтому переоткрывать нечего: место освобождается САМО, когда истечёт
        # аренда ключа, и купить это время нельзя. Бюджет остаётся ровно там,
        # где он и должен быть, — на переходе слота КОНТЕЙНЕРА.
        held_places = [process for process in processes.values()
                       if process["holds_place"]]
        if len(held_places) >= ceiling:
            # ОТНОШЕНИЕ КЛЮЧЕЙ К ИНСТАНСАМ — НАШЕ НАБЛЮДЕНИЕ, а не то, что
            # контейнер о себе сообщил. Значение много выше правдоподобного
            # числа воркеров означает, что несколько контейнеров называются
            # одним `instance_id`. Считается по тем, кто ДЕРЖИТ МЕСТА, а не по
            # занятым слотам: слот замолчавшего уже свободен, и деление на ноль
            # занятых печатало бы отношение, которого нет.
            owners = {owner for process in held_places for owner in process["owners"]}
            _log.warning("process ceiling reached for org=%s: %d held places across "
                         "%d instance ids (ratio %.1f)", org_id, len(held_places),
                         len(owners), len(held_places) / max(len(owners), 1))
            return {"allowed": False, **self._NOTHING_TAKEN,
                    "detail": self._refuse_processes(held_places, allowed, ceiling,
                                                     now)}
        if not reclaim:
            return {"allowed": True, **self._NOTHING_TAKEN, "detail": ""}
        # ОДИН ДОПУСК — ОДНА ЕДИНИЦА, что бы он ни вытеснил. Проверка бюджета
        # стоит ЗДЕСЬ, а не на освобождении: освобождение — это событие, за
        # которое клиент не просил ничего, а допуск — то самое, ради чего
        # ограничитель существует.
        spent = self.turnover_last_hour(org_id)
        budget = self.release_budget(plan)
        if spent >= budget:
            _log.warning("turnover budget exhausted for org=%s: %d of %d in "
                         "the last hour", org_id, spent, budget)
            lapsed_named = [record for record in instances
                            if record["instance_id"] == reclaim]
            return {"allowed": False, **self._NOTHING_TAKEN,
                    "detail": self._refuse_turnover(org_id, lapsed_named, allowed,
                                                    spent, budget, now)}
        return {"allowed": True, "reclaim": reclaim, "detail": ""}

    def may_lease(self, org_id: str, plan: str, instance_id: str,
                  window_seconds: int, pubkey: str = "") -> tuple[bool, str]:
        """Whether this instance may take a lease under the org's plan.

        Counts instances we have HEARD FROM recently, not instances that leased
        recently: a live engine renews once every eight hours, so «leased within
        the window» never distinguished a running container from one killed by
        the OOM reaper — and the customer waited up to a day for a slot held by
        a container that no longer existed (Б26).

        The instance asking is always allowed if it already holds a slot, so a
        renewal can never be refused by this check — only a genuinely NEW
        container beyond the plan can.

        ПРЕДИКАТ, И ТОЛЬКО. Ничего не пишет; перевыдачу слота исполняет
        `lease_if_allowed`.
        """
        verdict = self._admission(org_id, plan, instance_id, window_seconds,
                                  pubkey, time.time())
        return bool(verdict["allowed"]), str(verdict["detail"])

    def lease_if_allowed(self, lease_id: str, org_id: str, plan: str,
                         instance_id: str, process_id: str, window_seconds: int,
                         pubkey: str, engine_version: str = "",
                         lease_contract: int | None = None) -> tuple[bool, str]:
        """Проверить потолок, ПЕРЕВЫДАТЬ слот и занять его В ОДНОЙ секции.

        ПОТОЛОК ДЕРЖАЛСЯ НА ТОМ, ЧТО КЛИЕНТЫ СТУЧАТСЯ ПО ОЧЕРЕДИ. `may_lease` и
        `record_lease` — два отдельных публичных вызова, между которыми сервер
        отпускал лок: N одновременных запросов на аренду все видели
        `len(instances) < allowed` и все проходили. Это не гонка в драйвере, это
        дыра в единственной границе, которую мы вообще принуждаем.

        Лок реентрантный, поэтому вложенные вызовы берут его повторно и это
        по-прежнему одна секция.
        """
        with self._lock:
            now = time.time()
            verdict = self._admission(org_id, plan, instance_id, window_seconds,
                                      pubkey, now)
            if not verdict["allowed"]:
                return False, str(verdict["detail"])
            # ЕДИНИЦА СПИСЫВАЕТСЯ ЗДЕСЬ И ОДИН РАЗ — в той же секции, что и
            # решение. Тратит её ровно одно событие: слот КОНТЕЙНЕРА перешёл к
            # тому, кто просит. Мест рабочих процессов бюджет не покупает —
            # они освобождаются только временем (Б26quater).
            if verdict["reclaim"]:
                self.reclaim_silent(org_id, str(verdict["reclaim"]), now)
                self.record_admission(org_id, instance_id, str(verdict["reclaim"]),
                                      "instance", now)
            self.record_lease(lease_id, org_id, instance_id, process_id,
                              window_seconds, pubkey=pubkey,
                              engine_version=engine_version,
                              lease_contract=lease_contract)
            return True, ""

    def prune_leases(self, window_seconds: int) -> int:
        """Выбросить аренды, которые давно не считаются ни в одном окне.

        `may_lease` их и так не видит; смысл в том, чтобы таблица не росла
        вечно на машине, где мы сами и живём."""
        cutoff = time.time() - 2 * window_seconds
        with self._lock:
            cursor = self._conn.execute("DELETE FROM leases WHERE issued_at<?",
                                        (cutoff,))
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
        """Пометить слот процесса освобождённым. Строка остаётся — она ЗАПИСЬ.

        СЛОТ КОНТЕЙНЕРА свободен с этой секунды И РОВНО ПОКА ЭТОТ ПРОЦЕСС
        МОЛЧИТ. Остывание на 300 с убрано (оно не связывало — бюджет перевыдачи
        жёстче его в 4–12 раз), поэтому клиент, честно остановивший контейнер,
        поднимается сразу; а тот, кто «ушёл» и продолжает покупать ёмкость,
        слышен и слот занимает (`_speaks_after_release`).

        МЕСТО РАБОЧЕГО ПРОЦЕССА ПОД ПОТОЛКОМ ТАРИФА ЭТИМ НЕ ОСВОБОЖДАЕТСЯ, и
        это второй из двух сроков, которые тремя заходами подряд мерили одним
        счётчиком (Б26quater). `/v1/release` — заявление о будущем: бандл
        остаётся у процесса в памяти и действителен до `ttl + grace`, поэтому
        освободить по нему МЕСТО значит отдать круг «аренда — release —
        аренда» со скоростью сети. Место держится до конца окна аренды
        (`_occupancy::holds_place`), как в базе.

        И НИЧЕГО НЕ СТОИТ. Освобождение — событие, которого клиент не просил, и
        брать за него единицу значило наказывать за корректный `docker stop`:
        контейнер с четырьмя воркерами, продлившийся трижды, выписывал двенадцать
        единиц и блокировал сам себе редеплой. Платит ДОПУСК, который без этого
        ухода не состоялся бы (`_admission`).

        Возвращает, освободилось ли что-нибудь: раньше ручка отвечала
        `{"released": true}` даже когда ни одна строка не совпала.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE leases SET released_at=?, released_by='process' "
                "WHERE org_id=? AND pubkey=? AND released_at IS NULL",
                (time.time(), org_id, pubkey))
            self._conn.commit()
        return cursor.rowcount > 0

    def reclaim_silent(self, org_id: str, instance_id: str, now: float) -> int:
        """Закрыть строки замолчавшего инстанса: его слот перешёл сменщику.

        ЗАПИСЬ О СОСТОЯНИИ, А НЕ СЧЁТЧИК. Бюджет считает `admissions`, поэтому
        сколько строк закроется здесь — шестнадцать у контейнера с
        шестнадцатью воркерами или одна — на цену допуска не влияет никак;
        раньше влияло, и это был весь дефект.

        `released_at` — СЕЙЧАС, а не момент последнего признака жизни: строка
        отвечает на вопрос «занимает ли», а занимать он перестал в тот момент,
        когда место отдали.

        `released_at IS NULL` в условии оставлено: закрывать уже закрытое
        второй раз незачем, и `released_by` честно хранит первую причину ухода.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE leases SET released_at=?, released_by='silence' "
                "WHERE org_id=? AND instance_id=? AND released_at IS NULL",
                (now, org_id, instance_id))
            self._conn.commit()
        if cursor.rowcount:
            _log.info("slot reclaimed for org=%s instance=%s: silent for more than "
                      "%d s (%d lease rows)", org_id, instance_id,
                      int(self.ALIVE_SECONDS), cursor.rowcount)
        return cursor.rowcount

    def record_admission(self, org_id: str, instance_id: str, displaced: str,
                         reason: str, now: float) -> None:
        """Одна строка — одна единица бюджета.

        Лок берётся здесь, хотя зовут отсюда уже из-под него: он реентрантный,
        вложенный захват ничего не стоит, а запись, которая ПОЛАГАЕТСЯ на
        чужой лок, рано или поздно окажется вызвана без него — соединение
        открыто `check_same_thread=False`, и админка живёт на втором потоке.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO admissions (org_id, instance_id, at, displaced, reason) "
                "VALUES (?,?,?,?,?)", (org_id, instance_id, now, displaced, reason))
            self._conn.commit()
        _log.info("turnover unit spent by org=%s: %s admitted over %s (%s)",
                  org_id, instance_id, displaced, reason)

    def turnover_last_hour(self, org_id: str) -> int:
        """Сколько единиц бюджета перевыдачи эта организация потратила за час.

        ЕДИНИЦУ ТРАТИТ ДОПУСК, ВЫТЕСНИВШИЙ ЧУЖОЙ СЛОТ, И БОЛЬШЕ НИЧЕГО. Раньше
        считалось освобождение — и оба его вида считались неверно, каждый в
        свою сторону:

          * `COUNT(*)` по `released_by='process'` брал с ЧЕСТНОЙ остановки
            четырёхворкерного контейнера, продлевавшегося трижды, двенадцать
            единиц — весь часовой бюджет, после чего клиент не мог поднять
            собственный редеплой. Наказание за корректный `docker stop`;
          * `COUNT(DISTINCT instance_id)` по `released_by='silence'` насыщался:
            карусель, чередующая ДВА значения `PSEUDEX_INSTANCE_ID`, давала
            вечную двойку, бюджет переставал связывать вообще, и потолок обхода
            уезжал вверх — то есть ограничитель отменял сам себя ровно на той
            атаке, ради которой существует.

        Отсюда: корректная остановка стоит НОЛЬ (ничего не допущено),
        перезапуск на том же томе — ноль (инстанс возвращается на своё место),
        N воркеров одного контейнера — одну на всех (это один допуск одного
        инстанса), а карусель платит за каждый поднятый контейнер, какими бы
        идентификаторами ни крутила.

        Бюджет остаётся прежним — `max(3, инстансов по тарифу)` в час: потолок
        обхода равен темпу перевыдачи, умноженному на время работы без связи с
        нами, и сохранив темп, мы сохраняем потолок при том, что окно занятости
        сократилось в 144 раза.
        """
        cutoff = time.time() - self.TURNOVER_WINDOW_SECONDS
        row = self._fetchone(
            "SELECT COUNT(*) FROM admissions WHERE org_id=? AND at>=?",
            (org_id, cutoff))
        return int(row[0] or 0) if row else 0

    def turnover_frees_at(self, org_id: str, needed: int = 1) -> float:
        """Когда клиент РАЗБЛОКИРУЕТСЯ: когда из часового окна выпадут `needed`
        самых старых единиц.

        `needed` — это `потрачено − бюджет + 1`, а не единица. Печаталось
        выпадение ОДНОЙ, и при `потрачено` выше бюджета (тариф понизили, два
        допуска проскочили подряд) названная минута наступала, а отказ
        оставался тем же — срок в отказе врал ровно тем клиентам, которым он
        нужнее всего.

        Ноль, когда считать нечего: «через ноль минут» не пишется никогда,
        потому что тогда и отказа бы не было.
        """
        cutoff = time.time() - self.TURNOVER_WINDOW_SECONDS
        row = self._fetchone(
            "SELECT at FROM admissions WHERE org_id=? AND at>=? "
            "ORDER BY at LIMIT 1 OFFSET ?", (org_id, cutoff, max(1, needed) - 1))
        oldest = float(row[0]) if row and row[0] is not None else 0.0
        return oldest + self.TURNOVER_WINDOW_SECONDS if oldest else 0.0

    def silent_reclaims(self, org_id: str, since: float) -> int:
        """Сколько раз слот этой организации переходил к новому контейнеру
        потому, что прежний ушёл или замолчал.

        Наблюдение поверх ограничителя, а не вместо него: «клиент, у которого
        контейнеры постоянно лапсируют» — это то, что мы обязаны замечать сами,
        а не то, что он терпит. Считается тем же, чем считается бюджет:
        наблюдение и ограничитель, расходящиеся в единицах, — это два ответа на
        один вопрос, и в отчёте виден тот, который не принуждается."""
        row = self._fetchone(
            "SELECT COUNT(*) FROM admissions WHERE org_id=? AND at>=?",
            (org_id, since))
        return int(row[0] or 0) if row else 0

    def org_plan(self, org_id: str) -> str:
        """Тариф организации. Тариф живёт на КЛЮЧЕ, а ключей может быть
        несколько — берём самый щедрый, чтобы наблюдение не обвинило клиента по
        его же старому, более тесному ключу."""
        rows = self._fetchall("SELECT DISTINCT plan FROM keys WHERE org_id=?",
                              (org_id,))
        plans = [str(row[0]) for row in rows if row[0]]
        return max(plans, key=self.instances_allowed) if plans else ""

    def release_budget(self, plan: str) -> int:
        """Потолок ПЕРЕВЫДАЧ в час. По умолчанию выводится из тарифа:
        `max(3, инстансов)` — переразвёртывание одного контейнера укладывается,
        карусель нет."""
        return self.RELEASE_BUDGET_PER_HOUR or max(3, self.instances_allowed(plan))

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
