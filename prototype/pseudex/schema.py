"""The schema of a volume, numbered (D-058, D-059, D-060).

WHY A NUMBER AT ALL. Every store migrated in place with `ALTER TABLE … ADD
COLUMN` guarded by `PRAGMA table_info`, idempotent and unnumbered. That is fine
for going forward and silent about going back: an OLDER image on a NEWER volume
does not refuse, it opens the file, ignores the columns it does not know and
writes rows the newer image will then read as half-filled. There was no snapshot
before a migration either, so «restore to before the upgrade» meant «find last
night's backup». And `pseudexctl upgrade` cannot promise a rollback it cannot
see the shape of.

SQLite reserves two header integers for the application — `application_id`
(offset 68) and `user_version` (offset 60) — and never touches them itself.
`schema_version` is SQLite's own cookie: it moves on any DDL and on `VACUUM`,
and writing it is documented as a way to corrupt the file. SQLCipher encrypts
the header with the rest, so both numbers are readable only after `PRAGMA key`
— which is why the refusal below lives in `PSEUDEX_ROLE=probe`, the role that
already resolves the key before a single worker starts.

THE CONTRACT A VERSION NUMBER MAKES (D-060), in Gitea's words: a patch keeps
`user_version` (rolling back to the previous patch is free); a minor may raise
it, one way; a major may require an operator role named in the release notes.
`prototype/schema_lock.json` pins the maximum per minor, and `test_schema.py`
is red when a step is added under a minor that is already pinned: adding a
migration step means opening a minor.

WHAT HAPPENS ON A VOLUME WRITTEN BEFORE THIS FILE. `user_version` is 0 — the
pre-versioned state. Every step is idempotent by construction (they were run
on every open for a year), so all of them run and the volume is stamped with
the maximum. A snapshot is taken first, because from the volume's point of view
this IS a migration: the next image will refuse anything stamped above what it
knows, and the snapshot is what «restore to before» points at.

THE SNAPSHOT (D-059): `PRAGMA wal_checkpoint(TRUNCATE)` — the real values live
in the `-wal` until then — then `VACUUM INTO '<store>.pre-<from>-<to>.db'` on
the same connection, so SQLCipher writes the copy under the SAME key (verified
by `test_schema.py` opening it with the store's key, not assumed), then fsync
of the file and of the directory. Free space is checked BEFORE anything is
touched: a snapshot that fails half-way is worse than none, because it looks
like one. `os.statvfs` must show at least twice the store plus its WAL.

ONCE PER VOLUME, NOT ONCE PER WORKER. `entrypoint.sh` runs `PSEUDEX_ROLE=migrate`
between `probe` and the fan-out, so N workers find every store at the maximum
and take the fast path — no lock, no snapshot, no DDL beyond the idempotent
`CREATE … IF NOT EXISTS` they always ran. A worker that does find a store
behind (a volume mounted into a process that skipped the entrypoint) takes the
same `flock` the plaintext-to-encrypted conversion takes and does the same work;
the second worker through the lock re-reads the version and finds nothing to do.

A step and its stamp are not one transaction — `ALTER TABLE` autocommits under
the driver's isolation rules — and they need not be: a crash between them
leaves an idempotent step to re-run and a stamp still behind, which the next
open repairs. What must never happen is the stamp ahead of the step, and the
order of the two lines below is what guarantees it.
"""

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pseudex.sqlite_setup import (
    AUDIT_STORE, Connection, DatabaseError, STORES, TENANTS_STORE, VAULT_STORE,
)
from pseudex.vault_migrate import _Lock, _fsync_dir, _fsync_file

_log = logging.getLogger("pseudex.schema")

# Which STORE a file is, stamped into the header the first time this module
# opens it. Not a version: a check that `vault.db` is a vault and not an audit
# log someone renamed. Four ASCII letters each, readable in a hex dump.
APPLICATION_IDS: dict[str, int] = {
    VAULT_STORE: 0x50535856,    # PSXV
    AUDIT_STORE: 0x50535841,    # PSXA
    TENANTS_STORE: 0x50535854,  # PSXT
}

# The oldest `user_version` an image can bring forward. 0 is the pre-versioned
# state every existing volume is in; a major that drops the idempotent steps
# raises this and names the image that still carries them.
MIN_VERSION = 0

# The pin: maximum `user_version` per store per MINOR (D-060). Read by
# `test_schema.py` against `version.txt`; opening a minor means adding its line.
LOCK_FILE = Path(__file__).resolve().parent.parent / "schema_lock.json"

# What THIS process has verified on the stores it opened, by store label:
# the number the volume is at now. `/status` reads it; it is per process on
# purpose — a worker that has not opened the vault yet has nothing to report.
RUNNING: dict[str, int] = {}


class SchemaError(RuntimeError):
    """The volume and the image disagree about the schema. Fail closed."""


class SchemaTooNew(SchemaError):
    """A newer image wrote this volume. This one must not touch it."""


class SchemaTooOld(SchemaError):
    """The volume predates what this image can bring forward."""


class SchemaMismatch(SchemaError):
    """The file carries another store's application id."""


class SchemaNoSpace(SchemaError):
    """Not enough room for the snapshot that must precede the migration."""


@dataclass(frozen=True)
class Step:
    number: int
    name: str
    # The engine version that first shipped this step — the answer to «which
    # image do I need for a volume at N».
    introduced: str
    # NOT `apply`: build_mangle_names renames every unique module-level def
    # by NAME across the tree, and `translit.apply` is one — the field's
    # annotation was rewritten with it while `step.apply(...)` was not, and the
    # compiled image died on the first migration with «no attribute apply».
    run: Callable[[Connection], None]


@dataclass(frozen=True)
class StoreSchema:
    store: str
    # Base DDL, `CREATE … IF NOT EXISTS`, run on every open: the part of the
    # schema that is not versioned because it was never migrated.
    create: Callable[[Connection], None]
    steps: tuple[Step, ...]
    # Indexes over columns the STEPS added; must run after them, every open.
    finish: Callable[[Connection], None]


def _no_finish(_conn: Connection) -> None:
    return None


def registry() -> dict[str, StoreSchema]:
    """The three stores' schemas, imported lazily: each store module imports
    this one for `ensure`, so this one cannot import them at module scope."""
    from pseudex import audit, tenants, vault  # noqa: PLC0415 (import cycle)
    return {
        VAULT_STORE: StoreSchema(VAULT_STORE, vault.create_tables,
                                 vault.VAULT_MIGRATIONS, vault.create_indexes),
        AUDIT_STORE: StoreSchema(AUDIT_STORE, audit.create_tables,
                                 audit.AUDIT_MIGRATIONS, _no_finish),
        TENANTS_STORE: StoreSchema(TENANTS_STORE, tenants.create_tables,
                                   tenants.TENANTS_MIGRATIONS, _no_finish),
    }


def short_name(store: str) -> str:
    """`vault` for the vault store label — the name `schema_lock.json`, `/status`
    and the operator use; the label itself is the HKDF info string."""
    for filename, label in STORES:
        if label == store:
            return filename.removesuffix(".db")
    raise KeyError(store)


def max_version(store: str) -> int:
    """The highest `user_version` this image understands for a store."""
    steps = registry()[store].steps
    return steps[-1].number if steps else 0


def versions() -> dict[str, int]:
    """`{vault: 9, audit: 1, tenants: 1}` — the image's side of the contract."""
    return {short_name(store): max_version(store) for store in registry()}


def running() -> dict[str, int | None]:
    """What this process has verified on the stores it opened, by short name;
    `None` for a store it has not opened yet."""
    return {short_name(store): RUNNING.get(store) for store in registry()}


def read_lock() -> dict[str, dict[str, int]]:
    """`schema_lock.json`: `{minor: {store: max}}`."""
    return json.loads(LOCK_FILE.read_text(encoding="utf-8"))


def on_disk(conn: Connection) -> tuple[int, int]:
    """(`user_version`, `application_id`) of an open store."""
    user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    application_id = int(conn.execute("PRAGMA application_id").fetchone()[0])
    return user_version, application_id


def explain_too_new(db_path: str, store: str, found: int, known: int) -> str:
    """The sentence the operator acts on: both numbers, the file, the two ways
    out. Snapshots beside the file are named when they exist."""
    snapshots = _snapshots_beside(db_path)
    restore = (f"либо восстановите снимок {', '.join(snapshots)}" if snapshots
               else "либо восстановите снимок <store>.pre-<from>-<to>.db, если он есть")
    return (f"{db_path}: схема user_version {found}, этот образ ({store}) понимает "
            f"до {known}. Том писал более новый образ. Нужен образ не старше того, "
            f"что его писал, {restore}. Этот образ том не тронул.")


def _snapshots_beside(db_path: str) -> list[str]:
    directory = os.path.dirname(os.path.abspath(db_path)) or "."
    base = os.path.basename(db_path)
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    return [name for name in names
            if name.startswith(base + ".pre-") and name.endswith(".db")]


def snapshots(data_dir: str) -> list[dict[str, object]]:
    """Every `<store>.pre-<from>-<to>.db` in a data directory, with sizes — for
    `probe` and `pseudexctl doctor`, which advise deleting them once the new
    version has been running for a while."""
    found: list[dict[str, object]] = []
    for filename, _store in STORES:
        for name in _snapshots_beside(os.path.join(data_dir, filename)):
            path = os.path.join(data_dir, name)
            found.append({"name": name, "bytes": os.path.getsize(path)})
    return found


def ensure(conn: Connection, store: str, db_path: str) -> dict[str, object]:
    """Bring one open store to this image's schema, or refuse.

    Returns what was done: `{"from", "to", "snapshot", "applied"}`. The order
    of the checks is the point — nothing below the refusals touches the file.
    """
    schema = registry()[store]
    known = max_version(store)
    found, application_id = on_disk(conn)
    expected_id = APPLICATION_IDS[store]
    if application_id not in (0, expected_id):
        raise SchemaMismatch(
            f"{db_path}: application_id {application_id:#x} — это не {short_name(store)} "
            f"(ожидалось {expected_id:#x}). Файл переименован или подменён; "
            f"ничего не тронуто.")
    if found > known:
        raise SchemaTooNew(explain_too_new(db_path, short_name(store), found, known))
    if found < MIN_VERSION:
        raise SchemaTooOld(
            f"{db_path}: схема user_version {found}, этот образ поднимает только "
            f"от {MIN_VERSION}. Сначала образ, который ещё несёт шаги "
            f"{found + 1}…{MIN_VERSION}.")
    if found == known:
        # THE FAST PATH: what every worker does on every open. Idempotent DDL
        # only, no lock, no snapshot, no stamp.
        schema.create(conn)
        schema.finish(conn)
        conn.commit()
        RUNNING[store] = known
        return {"from": found, "to": known, "snapshot": None, "applied": []}
    if db_path == ":memory:":
        return _migrate(conn, schema, db_path, found, known, take_snapshot=False)
    with _Lock(db_path):
        # Re-read under the lock: N workers started together all saw the store
        # behind; exactly one may act on that, the rest find it done.
        found, _ = on_disk(conn)
        if found >= known:
            return ensure(conn, store, db_path)
        return _migrate(conn, schema, db_path, found, known, take_snapshot=True)


def _migrate(conn: Connection, schema: StoreSchema, db_path: str, found: int,
             known: int, take_snapshot: bool) -> dict[str, object]:
    snapshot_path: str | None = None
    # A FRESH store is created here for the first time and has nothing to snap.
    # «Fresh» is decided by the tables, not by the number: a legacy volume is at
    # 0 with a year of rows in it, and that is exactly the one to snapshot.
    if take_snapshot and _has_user_tables(conn):
        snapshot_path = snapshot(conn, db_path, found, known)
    schema.create(conn)
    applied: list[str] = []
    for step in schema.steps:
        if step.number <= found:
            continue
        step.run(conn)
        # STEP FIRST, STAMP SECOND. See the module note.
        conn.execute(f"PRAGMA user_version = {int(step.number)}")
        conn.commit()
        applied.append(step.name)
    if _application_id(conn) == 0:
        conn.execute(f"PRAGMA application_id = {int(APPLICATION_IDS[schema.store])}")
    schema.finish(conn)
    conn.commit()
    RUNNING[schema.store] = known
    if snapshot_path is not None:
        # A volume with rows in it was brought forward: that is the line an
        # operator searches for after an upgrade, so it is a WARNING and names
        # the snapshot. A fresh store getting its columns is just creation.
        _log.warning("schema: %s brought from user_version %d to %d (%s); snapshot %s",
                     db_path, found, known, ", ".join(applied), snapshot_path)
    else:
        _log.info("schema: %s created at user_version %d", db_path, known)
    return {"from": found, "to": known, "snapshot": snapshot_path, "applied": applied}


def _application_id(conn: Connection) -> int:
    return int(conn.execute("PRAGMA application_id").fetchone()[0])


def _has_user_tables(conn: Connection) -> bool:
    row = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchone()
    return int(row[0]) > 0


def snapshot(conn: Connection, db_path: str, from_version: int,
             to_version: int) -> str:
    """`<db>.pre-<from>-<to>.db` beside the store, under the same key.

    Space first, then the checkpoint, then the copy, then fsync — and the
    copy is refused rather than attempted when the space is not there.
    """
    directory = os.path.dirname(os.path.abspath(db_path)) or "."
    target = f"{db_path}.pre-{from_version}-{to_version}.db"
    needed = 2 * (_size(db_path) + _size(db_path + "-wal"))
    stats = os.statvfs(directory)
    free = stats.f_bavail * stats.f_frsize
    if free < needed:
        raise SchemaNoSpace(
            f"{db_path}: для снимка перед миграцией нужно {needed} байт свободного "
            f"места в {directory}, есть {free}. Ничего не тронуто — освободите "
            f"место или перенесите том, и запустите снова.")
    # The real values are in the -wal until this; the copy below reads through
    # the connection and would include them anyway, but the file the operator
    # copies by hand next to the snapshot would not.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    # A half-written snapshot of the SAME pair from an earlier attempt: the
    # store is still at `from`, so this copy supersedes it.
    if os.path.exists(target):
        os.unlink(target)
    quoted = target.replace("'", "''")
    try:
        conn.execute(f"VACUUM INTO '{quoted}'")
    except DatabaseError as error:
        raise SchemaError(f"{db_path}: снимок {target} не записан ({error}). "
                          f"Миграция не начата.") from None
    _fsync_file(target)
    _fsync_dir(directory)
    _log.warning("schema: snapshot of %s before migration %d→%d: %s (%d bytes)",
                 db_path, from_version, to_version, target, _size(target))
    return target


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


__all__ = [
    "APPLICATION_IDS", "LOCK_FILE", "MIN_VERSION", "RUNNING", "SchemaError",
    "SchemaMismatch", "SchemaNoSpace", "SchemaTooNew", "SchemaTooOld", "Step",
    "StoreSchema", "ensure", "explain_too_new", "max_version", "on_disk",
    "read_lock", "registry", "running", "short_name", "snapshot", "snapshots",
    "versions",
]
