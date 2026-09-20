"""The schema contract of a volume (D-058, D-059, D-060), each promise a check.

What is pinned and why each one could be red:

- a FRESH store is stamped with the image's maximum and its application id,
  and no snapshot is written — there is nothing to restore to;
- a LEGACY volume (the pre-versioned state, `user_version` 0, rows in it) is
  snapshotted BEFORE the first step, brought through every step, stamped; the
  snapshot opens with the SAME key (SQLCipher's `VACUUM INTO`, verified, not
  assumed) and holds the same rows; the rows still detokenize afterwards;
- a volume stamped ABOVE the image's maximum is refused with both numbers and
  the file named, and NOTHING is touched — the bytes are the same after;
- no room for the snapshot → refused BEFORE anything is touched;
- a repeat open is a no-op: no second snapshot, no DDL beyond IF NOT EXISTS;
- another store's application id is refused — `vault.db` that is an audit log;
- D-060: the maximum per store equals `schema_lock.json` for the minor in
  `version.txt`. A new step under an already-pinned minor is RED: adding a
  migration means opening a minor;
- step numbers are 1…n in historical order — a reordering would renumber what
  existing volumes were stamped with;
- `PSEUDEX_ROLE=probe` exits 2 on a volume from the future and names it;
  `PSEUDEX_ROLE=migrate` brings a legacy volume forward once and exits 0.

    python3 test_schema.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pseudex import schema, sqlite_setup, vault_key
from pseudex.sqlite_setup import AUDIT_STORE, TENANTS_STORE, VAULT_STORE
from pseudex.vault import Vault

FAILURES: list[str] = []
_ROOT = Path(__file__).resolve().parent
_KEY = "a" * 64


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _fresh_dir() -> str:
    directory = tempfile.mkdtemp(prefix="pseudex-schema-")
    os.environ["PSEUDEX_VAULT_KEY"] = _KEY
    vault_key.reset_cache()
    return directory


def _legacy_vault(path: str) -> None:
    """A vault.db as the FIRST shipped image wrote it: base tables only, no
    migrated columns, `user_version` 0, and rows in it."""
    conn = sqlite_setup.connect(path, VAULT_STORE)
    conn.execute("CREATE TABLE tokens (customer TEXT, canonical TEXT, entity_type TEXT, "
                 "token TEXT, PRIMARY KEY (customer, canonical))")
    conn.execute("CREATE TABLE name_parts (customer TEXT, part TEXT, canonical TEXT, "
                 "PRIMARY KEY (customer, part, canonical))")
    conn.executemany("INSERT INTO tokens VALUES (?,?,?,?)", [
        ("acme", "+79991112233", "PHONE", "+79995550101"),
        ("acme", "Иванов Пётр", "NAME", "Сидоров Олег"),
    ])
    conn.commit()
    conn.close()


def _open(path: str, store: str):
    return sqlite_setup.connect(path, store)


def _snapshots(directory: str) -> list[str]:
    return sorted(name for name in os.listdir(directory) if ".pre-" in name)


def main() -> int:
    lock = json.loads((_ROOT / "schema_lock.json").read_text(encoding="utf-8"))
    version = (_ROOT / "version.txt").read_text(encoding="utf-8").strip()
    minor = ".".join(version.split(".")[:2])

    # ── D-060: the lock file is the contract ────────────────────────────────
    check("schema_lock.json has a line for the minor in version.txt",
          minor in lock, f"version {version}, lock keys {sorted(lock)}")
    check("the image's maxima equal the lock for this minor — a new step means a new minor",
          lock.get(minor) == schema.versions(), f"lock {lock.get(minor)} image {schema.versions()}")
    for store, entry in schema.registry().items():
        numbers = [step.number for step in entry.steps]
        check(f"{schema.short_name(store)}: steps numbered 1…{len(numbers)} in order, no gaps",
              numbers == list(range(1, len(numbers) + 1)), str(numbers))
    vault_names = [step.name for step in schema.registry()[VAULT_STORE].steps]
    check("vault steps keep the historical order the constructor called them in",
          vault_names == ["digit_signatures", "name_keys", "original_form", "first_seen",
                          "place_created", "place_has_city", "fold_key", "minted_in", "extends"],
          str(vault_names))

    # ── fresh store: stamped, no snapshot ───────────────────────────────────
    directory = _fresh_dir()
    fresh_path = os.path.join(directory, "vault.db")
    Vault(fresh_path, "acme").tokenize("+7 999 000 11 22", "PHONE")
    conn = _open(fresh_path, VAULT_STORE)
    found, app_id = schema.on_disk(conn)
    conn.close()
    check("a fresh vault is stamped with the image's maximum and its application id",
          found == schema.max_version(VAULT_STORE) and app_id == schema.APPLICATION_IDS[VAULT_STORE],
          f"user_version={found} application_id={app_id:#x}")
    check("a fresh store gets no snapshot — there is nothing to restore to",
          _snapshots(directory) == [], str(_snapshots(directory)))
    check("/status sees what this process verified",
          schema.running()["vault"] == schema.max_version(VAULT_STORE), str(schema.running()))

    # ── legacy volume: snapshot, steps, stamp, rows survive ─────────────────
    directory = _fresh_dir()
    legacy_path = os.path.join(directory, "vault.db")
    _legacy_vault(legacy_path)
    vault = Vault(legacy_path, "acme")
    conn = _open(legacy_path, VAULT_STORE)
    found, app_id = schema.on_disk(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tokens)")}
    conn.close()
    check("a legacy volume is brought through every step and stamped",
          found == schema.max_version(VAULT_STORE)
          and {"digits", "name_key", "original", "first_seen", "canonical_fold", "minted_in",
               "extends"} <= columns, f"user_version={found} columns={sorted(columns)}")
    check("and its application id is set", app_id == schema.APPLICATION_IDS[VAULT_STORE])
    check("the rows written before the numbering still detokenize",
          vault.detokenize("+79995550101") == "+79991112233"
          and vault.detokenize("Сидоров Олег") == "Иванов Пётр",
          f"{vault.detokenize('+79995550101')!r} {vault.detokenize('Сидоров Олег')!r}")
    snaps = _snapshots(directory)
    expected_snapshot = f"vault.db.pre-0-{schema.max_version(VAULT_STORE)}.db"
    check("a snapshot named <store>.pre-<from>-<to>.db was written first",
          snaps == [expected_snapshot], str(snaps))
    snapshot_path = os.path.join(directory, expected_snapshot)
    # THE SNAPSHOT OPENS WITH THE STORE'S KEY — the property `VACUUM INTO`
    # under SQLCipher is trusted for, proved here rather than cited.
    try:
        copy = sqlite_setup.connect_readonly(snapshot_path, VAULT_STORE)
        rows = sorted(copy.execute("SELECT customer, canonical, token FROM tokens").fetchall())
        copy_columns = {row[1] for row in copy.execute("PRAGMA table_info(tokens)")}
        copy_version = int(copy.execute("PRAGMA user_version").fetchone()[0])
        copy.close()
        opened = True
    except (sqlite_setup.VaultLocked, sqlite_setup.DatabaseError) as error:
        rows, copy_columns, copy_version, opened = [], set(), -1, False
        print(f"      snapshot did not open: {error}")
    check("the snapshot opens with the same key and holds the pre-migration rows",
          opened and rows == [("acme", "+79991112233", "+79995550101"),
                              ("acme", "Иванов Пётр", "Сидоров Олег")], str(rows))
    check("the snapshot is the BEFORE state: no migrated columns, user_version 0",
          opened and "digits" not in copy_columns and copy_version == 0,
          f"columns={sorted(copy_columns)} user_version={copy_version}")
    check("the snapshot is encrypted on disk, like the store",
          sqlite_setup.file_state(snapshot_path) == sqlite_setup.ENCRYPTED)

    # ── repeat: no-op, no second snapshot ───────────────────────────────────
    before = os.path.getmtime(snapshot_path)
    Vault(legacy_path, "acme")
    check("a second open is a no-op: same one snapshot, untouched",
          _snapshots(directory) == [expected_snapshot]
          and os.path.getmtime(snapshot_path) == before)

    # ── a volume from the future: refused, untouched ────────────────────────
    directory = _fresh_dir()
    future_path = os.path.join(directory, "vault.db")
    Vault(future_path, "acme").tokenize("+7 999 000 11 22", "PHONE")
    too_new = schema.max_version(VAULT_STORE) + 1
    conn = _open(future_path, VAULT_STORE)
    conn.execute(f"PRAGMA user_version = {too_new}")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.commit()
    conn.close()
    bytes_before = Path(future_path).read_bytes()
    try:
        Vault(future_path, "acme")
        refused = ""
    except schema.SchemaTooNew as error:
        refused = str(error)
    check("a volume stamped above the image's maximum is refused with both numbers and the file",
          refused and str(too_new) in refused and str(schema.max_version(VAULT_STORE)) in refused
          and future_path in refused, refused[:160])
    conn = _open(future_path, VAULT_STORE)
    still, _ = schema.on_disk(conn)
    conn.close()
    check("and nothing was touched: the stamp stands, the file bytes are the same",
          still == too_new and Path(future_path).read_bytes() == bytes_before
          and _snapshots(directory) == [])

    # ── probe says 2, migrate brings a legacy volume forward ────────────────
    env = {**os.environ, "PSEUDEX_DB_DIR": directory, "PSEUDEX_VAULT_KEY": _KEY,
           "PSEUDEX_ROLE": "probe"}
    probe = subprocess.run([sys.executable, "serve_main.py"], cwd=str(_ROOT), env=env,
                           capture_output=True, text=True, timeout=120)
    check("PSEUDEX_ROLE=probe exits 2 on a volume from the future and names it",
          probe.returncode == 2 and "ТОМ НОВЕЕ ОБРАЗА" in probe.stdout and str(too_new) in probe.stdout,
          f"rc={probe.returncode} {probe.stdout[-300:]} {probe.stderr[-200:]}")

    directory = _fresh_dir()
    _legacy_vault(os.path.join(directory, "vault.db"))
    env = {**os.environ, "PSEUDEX_DB_DIR": directory, "PSEUDEX_VAULT_KEY": _KEY,
           "PSEUDEX_ROLE": "migrate"}
    migrate = subprocess.run([sys.executable, "serve_main.py"], cwd=str(_ROOT), env=env,
                             capture_output=True, text=True, timeout=120)
    check("PSEUDEX_ROLE=migrate brings a legacy volume forward, names the snapshot, exits 0",
          migrate.returncode == 0 and "0 → 9" in migrate.stdout and "снимок" in migrate.stdout
          and "audit.db" in migrate.stdout,
          f"rc={migrate.returncode} {migrate.stdout[-400:]} {migrate.stderr[-200:]}")
    check("migrate created and stamped the audit log too",
          os.path.exists(os.path.join(directory, "audit.db")) and _snapshots(directory) == ["vault.db.pre-0-9.db"],
          str(_snapshots(directory)))
    probe = subprocess.run([sys.executable, "serve_main.py"], cwd=str(_ROOT),
                           env={**env, "PSEUDEX_ROLE": "probe"},
                           capture_output=True, text=True, timeout=120)
    check("probe after migrate: exit 0, the stamp shown, the snapshot listed with the advice",
          probe.returncode == 0 and f"схема {schema.max_version(VAULT_STORE)}" in probe.stdout
          and "vault.db.pre-0-9.db" in probe.stdout and "удалите" in probe.stdout,
          f"rc={probe.returncode} {probe.stdout[-400:]}")

    # ── no room for the snapshot: refused before anything is touched ────────
    directory = _fresh_dir()
    cramped_path = os.path.join(directory, "vault.db")
    _legacy_vault(cramped_path)
    real_statvfs = schema.os.statvfs

    class _Cramped:
        f_bavail = 1
        f_frsize = 1

    schema.os.statvfs = lambda _path: _Cramped()  # type: ignore[assignment]
    try:
        Vault(cramped_path, "acme")
        no_space = ""
    except schema.SchemaNoSpace as error:
        no_space = str(error)
    finally:
        schema.os.statvfs = real_statvfs
    conn = _open(cramped_path, VAULT_STORE)
    still, _ = schema.on_disk(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tokens)")}
    conn.close()
    check("no room for the snapshot: refused, with the numbers",
          "свободного места" in no_space and "байт" in no_space, no_space[:160])
    check("and refused BEFORE touching: user_version still 0, no column added, no file",
          still == 0 and "digits" not in columns and _snapshots(directory) == [])

    # ── another store's id ──────────────────────────────────────────────────
    directory = _fresh_dir()
    wrong_path = os.path.join(directory, "vault.db")
    conn = _open(wrong_path, VAULT_STORE)
    conn.execute(f"PRAGMA application_id = {schema.APPLICATION_IDS[AUDIT_STORE]}")
    conn.commit()
    conn.close()
    try:
        Vault(wrong_path, "acme")
        mismatch = ""
    except schema.SchemaMismatch as error:
        mismatch = str(error)
    check("a file carrying another store's application id is refused",
          "application_id" in mismatch and "не тронуто" in mismatch, mismatch[:120])

    # ── the other two stores stamp too ──────────────────────────────────────
    from pseudex.audit import AuditLog  # noqa: PLC0415
    from pseudex.tenants import Tenants  # noqa: PLC0415
    directory = _fresh_dir()
    AuditLog(os.path.join(directory, "audit.db"))
    Tenants(os.path.join(directory, "tenants.db"))
    stamps = {}
    for filename, store in ((("audit.db"), AUDIT_STORE), (("tenants.db"), TENANTS_STORE)):
        conn = _open(os.path.join(directory, filename), store)
        stamps[filename] = schema.on_disk(conn)
        conn.close()
    check("audit and tenants stores are stamped with their maxima and ids",
          stamps["audit.db"] == (schema.max_version(AUDIT_STORE), schema.APPLICATION_IDS[AUDIT_STORE])
          and stamps["tenants.db"] == (schema.max_version(TENANTS_STORE), schema.APPLICATION_IDS[TENANTS_STORE]),
          str({k: (v[0], hex(v[1])) for k, v in stamps.items()}))
    described = sqlite_setup.describe(os.path.join(directory, "audit.db"), AUDIT_STORE)
    check("describe() reports the header numbers for probe and doctor",
          described.get("user_version") == schema.max_version(AUDIT_STORE)
          and described.get("application_id") == schema.APPLICATION_IDS[AUDIT_STORE], str(described))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        return 1
    print("schema OK — a volume is numbered, snapshotted before it moves, and refused when it is from the future")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
