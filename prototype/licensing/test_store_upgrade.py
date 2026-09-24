"""Апгрейд лицензионного сервера на СУЩЕСТВУЮЩИХ данных.

ЗАЧЕМ ОТДЕЛЬНЫЙ ФАЙЛ. Всё остальное про этот сервер запускается на ЧИСТОЙ базе:
гейты делают `down -v`, атаки на метрику берут временный каталог, стенд
пересоздаёт том. То есть путь «поднялись на том, который уже жил», не проверял
никто — а он единственный, которым сервер пойдёт в проде, потому что второй раз
чистой базы не будет уже никогда.

ЧТО ЭТО ПОЙМАЛО. `CREATE INDEX leases_org_pubkey ON leases(org_id, pubkey)`
стоял ДО `ALTER TABLE leases ADD COLUMN pubkey`, поэтому на томе, пережившем
релиз без этой колонки, процесс умирал на старте с `no such column: pubkey` и до
своей же миграции не доходил никогда.

СЛОТ-МИГРАЦИЯ УДАЛЕНА ВМЕСТЕ С МЕХАНИЗМОМ (docs/tz-license-volume-quota.md §A):
таблицы `slots`/`generations`/`admissions` и колонка `meter.release_echoes` на
боевых томах остаются лежать — новый код их не читает и не создаёт. Проверка
«ничего из удалённого не читается» стоит грепом в конце.

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

    # ПОТОЛОК: таблица заводится миграцией на существующем томе, чтения не падают.
    ceiling_columns = {row[1] for row in
                       store._conn.execute("PRAGMA table_info(ceilings)")}
    check("таблица потолка заведена на существующем томе",
          "ceiling_requests" in ceiling_columns, f"{sorted(ceiling_columns)}")

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

    # УДАЛЁННЫЕ МЕХАНИЗМЫ БОЛЬШЕ НЕ ЧИТАЮТСЯ — ГРЕПОМ, А НЕ ПАМЯТЬЮ. Строки
    # `admissions`, `meter.release_echoes`, таблицы `slots`/`generations` на
    # боевом томе остаются; красным здесь обязано быть не их присутствие на
    # диске, а обращение к ним из кода.
    source = (Path(__file__).resolve().parent / "store.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.split("\n")
                     if not line.lstrip().startswith("#"))
    stale = [name for name in ("FROM admissions", "INTO admissions",
                               "release_echoes", "FROM slots", "INTO slots",
                               "FROM generations", "INTO generations",
                               "lease_generation", "admit_generation")
             if name in code]
    check("удалённые слот-механизмы не читаются ни одной строкой кода",
          not stale, f"читается: {stale}" if stale else "slots/generations/admissions/echoes")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} provaleno: {', '.join(FAILURES)}")
        return 1
    print("апгрейд на существующем томе работает")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
