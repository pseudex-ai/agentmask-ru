"""Апгрейд лицензионного сервера на СУЩЕСТВУЮЩИХ данных.

ЗАЧЕМ ОТДЕЛЬНЫЙ ФАЙЛ. Всё остальное про этот сервер запускается на ЧИСТОЙ базе:
гейты делают `down -v`, атаки на метрику берут временный каталог, стенд
пересоздаёт том. То есть путь «поднялись на том, который уже жил», не проверял
никто — а он единственный, которым сервер пойдёт в проде, потому что второй раз
чистой базы не будет уже никогда.

ЧТО ЭТО ПОЙМАЛО. `CREATE INDEX leases_org_pubkey ON leases(org_id, pubkey)`
стоял ДО `ALTER TABLE leases ADD COLUMN pubkey`, поэтому на томе, пережившем
релиз без этой колонки, процесс умирал на старте с `no such column: pubkey` и до
своей же миграции не доходил никогда. Снаружи это выглядит как «сервер не
поднялся после обновления», и останавливает он КАЖДОГО клиента, у которого
кончилась аренда, — у нас он один.

    python3 -m licensing.test_store_upgrade
"""

import tempfile
import time
from pathlib import Path

from pseudex.sqlite_setup import connect
from licensing.store import LICENSING_STORE, LicenseStore

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


# СХЕМА ДО МИГРАЦИЙ, ДОСЛОВНО. Не «текущая минус колонка»: если завтра кто-то
# уберёт колонку из `CREATE TABLE`, вычитание уедет вместе с ней и фикстура
# перестанет описывать то, что реально лежит на дисках. Это снимок прошлого, и
# он не должен меняться.
_OLD_SCHEMA = [
    "CREATE TABLE keys (key_hash TEXT PRIMARY KEY, org_id TEXT, plan TEXT, "
    "status TEXT, created_at REAL)",
    "CREATE TABLE leases (lease_id TEXT PRIMARY KEY, org_id TEXT, "
    "instance_id TEXT, issued_at REAL, expires_at REAL)",
    "CREATE TABLE usage (org_id TEXT, instance_id TEXT, updated_at REAL, "
    "reports INTEGER, requests INTEGER, entities TEXT, "
    "PRIMARY KEY (org_id, instance_id))",
]

# СХЕМА НАКАНУНЕ СЛОТОВ, ДОСЛОВНО — ТО, ЧТО ЛЕЖИТ НА БОЕВОМ ТОМЕ ПРЯМО СЕЙЧАС.
#
# Второй снимок нужен потому, что первый описывает схему трёхлетней давности и
# на нём НЕ ПРОВЕРЯЕТСЯ главное свойство миграции слотов: установка, державшая
# слот до платформенного релиза, обязана держать его после (§7.3, S-14). Для
# этого нужны строки в той форме, в какой их писал предыдущий сервер, —
# с `admissions`, с `meter.release_echoes`, с `leases.released_*`.
#
# И ЗДЕСЬ ТОЖЕ НЕ «ТЕКУЩАЯ МИНУС КОЛОНКА»: вычитание уехало бы вместе с
# правкой `CREATE TABLE`, и фикстура перестала бы описывать боевой том.
_PRE_SLOTS_SCHEMA = [
    "CREATE TABLE keys (key_hash TEXT PRIMARY KEY, org_id TEXT, plan TEXT, "
    "status TEXT, created_at REAL)",
    "CREATE TABLE leases (lease_id TEXT PRIMARY KEY, org_id TEXT, "
    "instance_id TEXT, process_id TEXT, pubkey TEXT, released_at REAL, "
    "released_by TEXT, issued_at REAL, ttl_seconds INTEGER, "
    "engine_version TEXT DEFAULT '', lease_contract INTEGER)",
    "CREATE TABLE usage (org_id TEXT, instance_id TEXT, updated_at REAL, "
    "reports INTEGER, requests INTEGER, entities TEXT, "
    "values_reported INTEGER DEFAULT 0, values_total INTEGER DEFAULT 0, "
    "resets INTEGER DEFAULT 0, seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', "
    "signature TEXT DEFAULT '', trust TEXT DEFAULT 'unsigned', "
    "chain_breaks INTEGER DEFAULT 0, unverified_reports INTEGER DEFAULT 0, "
    "unverified_requests INTEGER DEFAULT 0, malformed_reports INTEGER DEFAULT 0, "
    "reports_missing INTEGER DEFAULT 0, PRIMARY KEY (org_id, instance_id))",
    "CREATE TABLE admissions (org_id TEXT, instance_id TEXT, at REAL, "
    "displaced TEXT, reason TEXT)",
    "CREATE TABLE meter (org_id TEXT, pubkey TEXT, first_seen REAL, "
    "updated_at REAL, quantum_seq INTEGER DEFAULT 0, quantum_size INTEGER DEFAULT 0, "
    "reserve INTEGER DEFAULT 0, granted INTEGER DEFAULT 0, "
    "prefetch_at INTEGER DEFAULT 0, acked INTEGER DEFAULT 0, acked_at REAL, "
    "ack_trust TEXT DEFAULT 'none', rate_per_second REAL DEFAULT 0, "
    "unacked_quanta INTEGER DEFAULT 0, ack_regressions INTEGER DEFAULT 0, "
    "release_echoes INTEGER DEFAULT 0, PRIMARY KEY (org_id, pubkey))",
    "CREATE TABLE plans (code TEXT PRIMARY KEY, max_instances INTEGER, "
    "processes_per_instance INTEGER, grant_size INTEGER, quantum_min INTEGER, "
    "quantum_max INTEGER, reserve_max INTEGER, updated_at REAL, "
    "updated_by TEXT DEFAULT '')",
]


def _pre_slots_volume() -> Path:
    """Том в форме предыдущего релиза: два клиента, живые аренды, мёртвая."""
    path = Path(tempfile.mkdtemp(prefix="pseudex-preslots-")) / "license.db"
    old = connect(str(path), LICENSING_STORE)
    for statement in _PRE_SLOTS_SCHEMA:
        old.execute(statement)
    now = time.time()
    old.execute("INSERT INTO keys VALUES ('h-work', 'work', 'work', 'active', 1.0)")
    old.execute("INSERT INTO keys VALUES ('h-start', 'tiny', 'start', 'active', 1.0)")
    old.execute("INSERT INTO plans VALUES ('work',4,32,25000,200,10000,100000,NULL,'')")
    old.execute("INSERT INTO plans VALUES ('start',1,32,5000,200,2000,20000,NULL,'')")
    # Две живые установки одной организации, по два воркера в каждой.
    for instance, key in (("vol-a", "ka1"), ("vol-a", "ka2"),
                          ("vol-b", "kb1"), ("vol-b", "kb2")):
        old.execute("INSERT INTO leases VALUES (?,?,?,?,?,NULL,NULL,?,?,?,3)",
                    (f"ls-{instance}-{key}", "work", instance, "p", key,
                     now - 60, 86400, "0.3.17"))
    # Установка, чья аренда истекла сутки назад: слот ей не нужен.
    old.execute("INSERT INTO leases VALUES ('ls-dead','work','vol-dead','p','kd',"
                "NULL,NULL,?,3600,'0.3.17',3)", (now - 90000,))
    # ЧЕТЫРЕ ПЕРЕЗАПУСКА ОДНОГО КОНТЕЙНЕРА — И ЭТО НЕ ЭКЗОТИКА, А ФОРМА БОЕВОГО
    # ФЛОТА. Выпущенный `entrypoint.sh` (0.3.17:99–101) чеканит
    # `PSEUDEX_INSTANCE_ID` из /dev/urandom НА КАЖДЫЙ СТАРТ, а `service.py:125`
    # берёт переменную раньше идентификатора тома, — значит установка там не
    # переживает перезапуск, и в окне аренды лежит столько «установок», сколько
    # раз контейнер поднимался за сутки. Жив из них ноль или один.
    for number in range(4):
        old.execute("INSERT INTO leases VALUES (?,?,?,?,?,NULL,NULL,?,?,?,3)",
                    (f"ls-rand-{number}", "work", f"rand-{number}", "p",
                     f"kr{number}", now - 600 * (number + 1), 86400, "0.3.17"))
    # И строки механизмов, которых больше нет.
    old.execute("INSERT INTO admissions VALUES ('work','vol-b',?,'vol-a','instance')",
                (now - 600,))
    old.execute("INSERT INTO meter (org_id, pubkey, first_seen, updated_at, "
                "quantum_seq, granted, acked, release_echoes) "
                "VALUES ('work','ka1',?,?,3,600,400,2)", (now - 600, now - 60))
    old.commit()
    old.close()
    return path


def main() -> int:
    path = Path(tempfile.mkdtemp(prefix="pseudex-upgrade-")) / "license.db"

    # Том, который уже жил: старая схема и строки в ней.
    old = connect(str(path), LICENSING_STORE)
    for statement in _OLD_SCHEMA:
        old.execute(statement)
    old.execute("INSERT INTO keys VALUES ('h1', 'acme', 'start', 'active', 1.0)")
    old.execute("INSERT INTO leases VALUES ('l1', 'acme', 'i1', 1.0, 2.0)")
    old.execute("INSERT INTO usage VALUES ('acme', 'i1', 1.0, 3, 42, '{}')")
    old.commit()
    old.close()

    opened = None
    try:
        store = LicenseStore(str(path))
        opened = True
    except Exception as error:  # noqa: BLE001 — любой отказ здесь и есть дефект
        opened = False
        check("сервер поднимается на томе прошлой версии", False,
              f"{type(error).__name__}: {error}")

    if not opened:
        print("\n1 provalen")
        return 1

    check("сервер поднимается на томе прошлой версии", True)

    columns = {row[1] for row in
               store._conn.execute("PRAGMA table_info(leases)")}
    check("колонка pubkey доехала миграцией", "pubkey" in columns,
          f"leases: {sorted(columns)}")
    # ВЕРСИЯ ДВИЖКА В АРЕНДЕ (D-056): старый ряд без неё читается как пустая
    # строка, новый — записывает то, что назвал контейнер, и гистограмма флота
    # считает живые инстансы по версиям. Без этого пол минимальной версии
    # двигался бы вслепую.
    check("колонка engine_version доехала миграцией", "engine_version" in columns)
    store.record_lease("l2", "acme", "i2", "p2", 3600, pubkey="k2", engine_version="0.3.16")
    fleet = {row["engine_version"]: row for row in store.fleet_versions(86400 * 365 * 100)}
    check("старый ряд — пустая версия, новый — своя; гистограмма считает по инстансам",
          fleet.get("", {}).get("instances") == 1 and fleet.get("0.3.16", {}).get("instances") == 1,
          f"{fleet}")
    # УДАЛЕНО ВМЕСТЕ С `active_instances`: «экран называет версию инстанса» и
    # «после 0.3.9 → 0.3.10 инстанс числится на 0.3.10, а не на строковом
    # максимуме». Первое лечило Б26bis (экран врал о том, кто держит слот) и
    # держится теперь формой по слотам (`slots_view`, проверка ниже); второе
    # лечило сравнение версий строками в SQL и держится `fleet_versions`, где
    # это сравнение и осталось, — проверка над ним стоит строкой выше.
    # ЗАЯВЛЕННЫЙ КОНТРАКТ (D-063): старый ряд — NULL (не заявлял), новый — то,
    # что клиент назвал; гистограмма делит версию по контрактам, чтобы было
    # видно, когда мост контракта 2 можно снять.
    check("колонка lease_contract доехала миграцией", "lease_contract" in columns)
    store.record_lease("l3", "acme", "i3", "p3", 3600, pubkey="k3", engine_version="0.3.16",
                       lease_contract=3)
    rows = store.fleet_versions(86400 * 365 * 100)
    check("старый ряд — контракт NULL, новый — 3, и это две строки одной версии",
          any(r["engine_version"] == "0.3.16" and r["lease_contract"] is None for r in rows)
          and any(r["engine_version"] == "0.3.16" and r["lease_contract"] == 3 for r in rows),
          f"{rows}")

    usage_columns = {row[1] for row in
                     store._conn.execute("PRAGMA table_info(usage)")}
    check("колонки цепи отчётов доехали",
          {"seq", "prev", "signature", "trust"} <= usage_columns,
          f"usage: {len(usage_columns)} колонок")

    indexes = {row[0] for row in store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    check("индекс по pubkey построен, а не пропущен",
          "leases_org_pubkey" in indexes, f"{sorted(indexes)}")

    # ДАННЫЕ ПЕРЕЖИЛИ. Миграция, которая поднимается ценой пустой таблицы, —
    # это не миграция, а `down -v` с хорошим настроением.
    rows = store._conn.execute("SELECT requests FROM usage WHERE org_id='acme'").fetchall()
    check("старые счётчики на месте", rows and rows[0][0] == 42, f"{rows}")

    # И ВТОРОЙ ПОДЪЁМ. Миграция обязана быть идемпотентной: процесс
    # перезапускается чаще, чем обновляется.
    try:
        LicenseStore(str(path))
        check("повторный подъём на уже мигрированном томе", True)
    except Exception as error:  # noqa: BLE001
        check("повторный подъём на уже мигрированном томе", False,
              f"{type(error).__name__}: {error}")

    # ── S-25/S-26: ТОМ НАКАНУНЕ СЛОТОВ ─────────────────────────────────────
    pre = _pre_slots_volume()
    try:
        store = LicenseStore(str(pre))
        check("сервер поднимается на томе предыдущего релиза", True)
    except Exception as error:  # noqa: BLE001
        check("сервер поднимается на томе предыдущего релиза", False,
              f"{type(error).__name__}: {error}")
        print(f"\n{len(FAILURES)} provaleno")
        return 1

    slots = {int(row[0]): (str(row[1]), int(row[2])) for row in store._conn.execute(
        "SELECT slot_no, COALESCE(holder_installation,''), epoch FROM slots "
        "WHERE org_id='work'")}
    check("слоты засеяны по тарифу ключа, а не по тому, что прислал клиент",
          sorted(slots) == [1, 2, 3, 4], f"{sorted(slots)}")
    held = {installation for installation, _ in slots.values() if installation}
    # МИГРАЦИЯ НЕ НАЗНАЧАЕТ НИ ОДНОГО ДЕРЖАТЕЛЯ, И ЭТО ЗАМЕНА ПРЕЖНЕГО S-14.
    #
    # Требование «каждая установка, державшая слот ДО, держит слот ПОСЛЕ»
    # написано в предположении, что установка — это ТОМ. На боевом флоте это
    # неверно: 0.3.17 чеканит её на каждый старт (см. фикстуру выше), поэтому
    # усыновление отдавало слот КАЖДОМУ мёртвому перезапуску. Здесь шесть
    # установок на четыре слота, из них жив максимум один, — и прежний код
    # печатал «занято 4 из 4» клиенту с одним контейнером. Это дефект Б26bis, а
    # не соблюдение приёмки.
    check("миграция не назначает держателей: перезапуски выпущенного флота "
          "неразличимы, и призраков быть не должно",
          held == set(), f"держат слоты {sorted(held)}")
    view = store.slots_view("work", "work", 86400.0, time.time())
    check("занятость 0, а не 4 из 4 у клиента, у которого жив один контейнер",
          view["occupied"] == 0 and view["slot_count"] == 4,
          f"занято {view['occupied']} из {view['slot_count']}")
    # НО И НУЛЬ САМ ПО СЕБЕ ЧИТАЕТСЯ КАК ОТВЕТ «У ВАС НИЧЕГО НЕ РАБОТАЕТ» —
    # догадка того же рода, что и призраки, только в другую сторону. Поэтому
    # рядом стоит число: сколько установок прошлого релиза ещё держат аренду.
    check("установки прошлого релиза названы числом, а не молчанием",
          view["pending_installations"] == 6,
          f"pending={view['pending_installations']} (vol-a, vol-b, rand-0..3)")
    check("установка с истёкшей арендой в это число не входит",
          view["pending_installations"] == 6, "vol-dead не считается")
    # НИ ОДИН КЛЮЧ ВЫПУЩЕННОГО ФЛОТА НЕ ЗАПЕРТ. Привязки у него нет, а покупка
    # без привязки не фенсится вовсе: бандла у такого ключа нет, квант ему
    # бесполезен, и заводить там вторую границу значило бы судить по молчанию.
    quantum, fenced = store.meter_if_allowed("work", "ka1", "work", None, None,
                                             None, 86400.0, time.time())
    check("выпущенный ключ покупает ёмкость сразу после миграции, не отфенсен",
          quantum is not None and not fenced, f"fenced={fenced}")

    # СЛОТ БЕРЁТСЯ НА ПЕРВОЙ ЖЕ АРЕНДЕ ПОСЛЕ РЕЛИЗА, И БЕРЁТ ЕГО ТОТ, КТО
    # ПРИШЁЛ. Это и есть замена усыновления: место достаётся контейнеру,
    # который реально поднялся, а не тому, кто оставил запись в окне аренды.
    reopened = LicenseStore(str(pre))
    claimed = reopened.lease_generation("ls-new", "work", "work", "legacy:vol-a",
                                        "vol-a", "p", 86400, pubkey="ka9",
                                        engine_version="0.3.17")
    check("старый движок берёт свободный слот на ближайшей аренде, без отказа",
          claimed["claimed"] is True and claimed["epoch"] == 1
          and claimed["slot_count"] == 4, f"{claimed}")
    # И ВТОРАЯ ЕГО АРЕНДА (продление другого воркера) НЕ ФЕНСИТ ПЕРВУЮ: та же
    # установка — то же синтетическое поколение — тот же слот и тот же эпох.
    second = reopened.lease_generation("ls-new2", "work", "work", "legacy:vol-a",
                                       "vol-a", "p", 86400, pubkey="ka10",
                                       engine_version="0.3.17")
    check("второй воркер той же установки попадает в СВОЁ поколение, не фенсит себя",
          second["claimed"] is False and second["epoch"] == claimed["epoch"]
          and second["slot_no"] == claimed["slot_no"], f"{second}")

    # ЭПОХ DURABLE (S-26): рестарт сервера между заявками не понижает номер.
    # ПРОВЕРЯЕТСЯ ПОСЛЕ ЗАЯВКИ, А НЕ ДО НЕЁ. Стояло до — то есть на слотах с
    # эпохом ноль, где «не понизился» верно при любой реализации, включая ту,
    # что теряет номер целиком. Проверка, которая не может упасть, — не
    # проверка.
    before = {int(row[0]): int(row[1]) for row in reopened._conn.execute(
        "SELECT slot_no, epoch FROM slots WHERE org_id='work'")}
    restored = LicenseStore(str(pre))
    after = {int(row[0]): int(row[1]) for row in restored._conn.execute(
        "SELECT slot_no, epoch FROM slots WHERE org_id='work'")}
    check("рестарт сервера не понижает эпох занятого слота",
          max(before.values()) >= 1 and after == before, f"{before} -> {after}")

    # МИГРАЦИЯ ОДНОРАЗОВАЯ, И ЭТО ПРОВЕРЯЕТСЯ НА СОВРЕМЕННОМ КЛИЕНТЕ.
    #
    # Найдено чтением кода, а не числом: усыновление отбирало ЛЮБУЮ открытую
    # аренду, поэтому на каждом подъёме процесса рядом с настоящим поколением
    # (`S-modern`) заводилось призрачное `legacy:<том>` и занимало свободный
    # слот. Через три рестарта у клиента с ОДНИМ контейнером «занято 4 из 4», а
    # экран, врущий о том, кто держит слот, и есть дефект (Б26bis). Отбор идёт
    # только по строкам БЕЗ привязки — их пишет лишь предыдущий сервер.
    reopened.lease_generation("ls-modern", "work", "work", "S-modern", "vol-new",
                              "p", 86400, pubkey="k-modern",
                              engine_version="0.3.18")
    occupied_before = sum(1 for row in reopened._slot_rows("work")
                          if row["holder_start_id"])
    restarted = LicenseStore(str(pre))
    occupied_after = sum(1 for row in restarted._slot_rows("work")
                         if row["holder_start_id"])
    phantom = [str(row[0]) for row in restarted._conn.execute(
        "SELECT start_id FROM generations WHERE org_id='work' AND start_id=?",
        ("legacy:vol-new",))]
    check("рестарт сервера не усыновляет современную аренду вторым поколением",
          occupied_after == occupied_before and not phantom,
          f"занято {occupied_before} -> {occupied_after}, призраки {phantom}")

    # УДАЛЁННОЕ БОЛЬШЕ НЕ ЧИТАЕТСЯ — ГРЕПОМ, А НЕ ПАМЯТЬЮ. Строки `admissions` и
    # `meter.release_echoes` на томе остались; красным здесь обязано быть не их
    # присутствие, а обращение к ним из кода.
    source = (Path(__file__).resolve().parent / "store.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.split("\n")
                     if not line.lstrip().startswith("#"))
    stale = [name for name in ("FROM admissions", "INTO admissions",
                               "release_echoes=", "SUM(release_echoes)")
             if name in code]
    check("механизмы бюджета и эха не читаются ни одной строкой кода",
          not stale, f"читается: {stale}" if stale else "admissions, release_echoes")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} provaleno: {', '.join(FAILURES)}")
        return 1
    print("апгрейд на существующем томе работает")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
