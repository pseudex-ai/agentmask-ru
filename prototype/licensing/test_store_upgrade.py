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

    print()
    if FAILURES:
        print(f"{len(FAILURES)} provaleno: {', '.join(FAILURES)}")
        return 1
    print("апгрейд на существующем томе работает")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
