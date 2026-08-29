"""Shared SQLite connection setup for the four stores (vault, audit, tenants, licensing).

WHY THIS EXISTS: the default connection settings deadlock-by-polling under real
agent traffic. A masking request touches the vault and the audit log from several
worker threads at once, and with the stock settings a blocked writer raises
`database is locked` — but only AFTER python's sqlite3 has spent its timeout
BUSY-POLLING in a retry loop. That loop is pure CPU: the proxy was observed
pinned at 97% with `pysqlite_connection_execute` dominating the stack while doing
no useful work at all, and the agent driving it simply stalled.

Two settings fix it:

  WAL      readers no longer block the writer and the writer no longer blocks
           readers, so the contention that triggered the spin mostly disappears.
           WAL persists on the database file, so it is set once per connection
           and survives restarts.
  busy_timeout
           when contention does happen, wait on a proper condition instead of
           failing fast into the caller. Set explicitly rather than relying on
           the `timeout` connect argument so the value is visible at the call
           site and applies to every statement.

NOT a substitute for the per-connector locks: those still serialize use of a
single connection object across threads, which the DB-API requires when a
connection is created with check_same_thread=False.

THE DRIVER IS SQLCIPHER, ALWAYS, AND THERE IS NO FALLBACK TO STDLIB `sqlite3`.
This is the most dangerous line that could have been written in this file:

    try: from sqlcipher3 import dbapi2 as driver
    except ImportError: import sqlite3 as driver

Stdlib `sqlite3` accepts `PRAGMA key` WITHOUT RAISING and writes plain text
(verified in this tree: the marker value is in the file afterwards, and the
header is still `SQLite format 3\\0`). So that fallback is a product which
claims encryption, logs that it is encrypting, and is not. One driver, no
branch, and a packaging gate proves the branch is absent from the shipped image.

Using SQLCipher for an UNencrypted store costs nothing: without `PRAGMA key` it
is ordinary SQLite and reads ordinary SQLite files. That is what makes one driver
possible at all.

EXCEPTION CLASSES ARE EXPORTED FROM HERE, and callers must use them. This is the
sharp edge of the whole change:

    sqlcipher3.dbapi2.IntegrityError is sqlite3.IntegrityError      -> False
    issubclass(sqlcipher3.IntegrityError, sqlite3.IntegrityError)   -> False

Same for OperationalError. A handler that still names `sqlite3.IntegrityError`
does not fire — and the one in `vault.py` that catches the INSERT race between
workers is exactly the failure gate P5 exists to catch, so it would come back as
a 500 in a burst rather than as a test failure here.
"""

import os
import time

from sqlcipher3 import dbapi2 as sqlcipher

from pseudex import vault_key
from pseudex.vault_migrate import ENCRYPTED, MISSING, PLAINTEXT, ensure_encrypted, file_state

# The store labels, re-exported so a caller names one thing and not two.
VAULT_STORE = vault_key.VAULT_STORE
AUDIT_STORE = vault_key.AUDIT_STORE
TENANTS_STORE = vault_key.TENANTS_STORE
LICENSING_STORE = vault_key.LICENSING_STORE

# What every `except` in the codebase must name. See the module docstring.
Connection = sqlcipher.Connection
Error = sqlcipher.Error
DatabaseError = sqlcipher.DatabaseError
IntegrityError = sqlcipher.IntegrityError
OperationalError = sqlcipher.OperationalError

# Long enough to ride out a WRITE STORM from several worker processes, short
# enough that a genuine deadlock still surfaces as an error rather than hanging a
# request forever. Raised from 5 s after four workers under a 16-way burst
# produced `database is locked` on 46 of 64 requests: in a fail-closed gateway a
# request that waits is strictly better than one that 500s, because the
# customer's gateway has to block the user either way.
_BUSY_TIMEOUT_MS = 15000

# The journal-mode switch is retried by hand — see `_enable_wal`.
_WAL_ATTEMPTS = 40
_WAL_RETRY_SECONDS = 0.25


class VaultLocked(RuntimeError):
    """The store is encrypted and the configured key does not open it."""


def _enable_wal(connection: sqlcipher.Connection) -> None:
    """Switch the database to WAL, waiting out other processes doing the same.

    `busy_timeout` does NOT cover this. SQLite takes an exclusive lock to change
    journal mode and, unlike ordinary statements, returns SQLITE_BUSY straight
    away instead of invoking the busy handler when another connection holds the
    file. So N workers starting together against a FRESH database file is a real
    race: one wins and the others get `database is locked` while merely importing
    the module.

    That failure is nastier than it sounds — the container kept answering on the
    surviving worker, so a half-dead deployment looked healthy.

    Retrying is safe and idempotent: WAL is a property of the FILE, so once any
    process has set it the rest read back "wal" and stop."""
    deadline_attempts = _WAL_ATTEMPTS
    while True:
        try:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()
        except OperationalError as error:
            if "locked" not in str(error) and "busy" not in str(error):
                raise
            mode = None
        if mode is not None and str(mode[0]).lower() == "wal":
            return
        deadline_attempts -= 1
        if deadline_attempts <= 0:
            current = connection.execute("PRAGMA journal_mode").fetchone()
            raise OperationalError(
                f"could not switch {connection} to WAL after "
                f"{_WAL_ATTEMPTS} attempts over "
                f"{_WAL_ATTEMPTS * _WAL_RETRY_SECONDS:.0f}s; journal_mode is "
                f"{current[0] if current else 'unknown'}. Another process is "
                f"holding the database in a different journal mode."
            )
        time.sleep(_WAL_RETRY_SECONDS)


def store_key(db_path: str, store: str) -> str:
    """The 64-hex key for this file, or "" when encryption is switched off.

    The master secret is resolved from the DIRECTORY the database lives in, so
    the three stores of one volume share one secret and derive three different
    keys from it. `:memory:` has no directory and nothing on disk to protect.
    """
    if db_path == ":memory:":
        return ""
    data_dir = os.path.dirname(os.path.abspath(db_path)) or "."
    secret = vault_key.resolve(data_dir)
    return "" if secret is None else secret.store_key(store)


def _explain_locked(db_path: str, driver_message: str) -> VaultLocked:
    """Our message, not the driver's — L21 exists because the driver's is useless.

    SQLCipher answers `file is not a database` to a wrong key, to a corrupt file
    and to an unencrypted database alike. Only the header tells those apart, and
    we have already read it. The customer needs to be told the one thing that is
    actually true and actually expensive: without the key, nobody restores the
    substitute-to-value map, us included.
    """
    return VaultLocked(
        f"\n"
        f"волт зашифрован, а текущий ключ его не открывает.\n"
        f"\n"
        f"    файл:      {db_path}\n"
        f"    ключ:      {vault_key.state(os.path.dirname(os.path.abspath(db_path)) or '.')['key_source']}\n"
        f"    SQLCipher: {driver_message}\n"
        f"\n"
        f"это НЕ порча файла. SQLCipher отвечает одинаково на неверный ключ, на\n"
        f"испорченный файл и на попытку открыть незашифрованную базу; здесь\n"
        f"заголовок файла говорит «зашифровано», значит дело в ключе.\n"
        f"\n"
        f"без верного ключа соответствия «подмена → значение» не восстановит\n"
        f"никто, включая нас. подмены, уже записанные в вашу CRM, останутся\n"
        f"строками без обратного пути.\n"
        f"\n"
        f"PSEUDEX_ROLE=probe покажет, какой из файлов тома открывается текущим\n"
        f"ключом, а какой нет.\n"
    )


def _arm(connection: sqlcipher.Connection, db_path: str, key: str) -> None:
    """Key first, then the concurrency settings, then prove the key worked."""
    if key:
        # ORDER: before anything that reads a page. A connection that touches
        # the database before the key is set is already wrong.
        connection.execute(f"PRAGMA key = {vault_key.key_literal(key)}")
    # busy_timeout next, so every ordinary statement waits on a condition
    # instead of failing fast into the caller — including the verification below.
    connection.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    try:
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except DatabaseError as error:
        connection.close()
        if key:
            # `from None`: the driver's sentence would otherwise be the last line
            # of the traceback and the one an operator reads, and it says the
            # wrong thing. It is quoted inside our message instead.
            raise _explain_locked(db_path, str(error)) from None
        raise VaultLocked(
            f"\n"
            f"{db_path} зашифрован, а PSEUDEX_VAULT_ENCRYPTION=off.\n"
            f"SQLCipher: {error}\n"
            f"\n"
            f"уберите off и задайте тот ключ, которым эта база была зашифрована.\n"
            f"расшифровать её на месте можно ролью PSEUDEX_ROLE=decrypt.\n"
        ) from None


def connect(db_path: str, store: str) -> sqlcipher.Connection:
    """Open a store with settings that survive concurrent workers.

    Encrypted unless PSEUDEX_VAULT_ENCRYPTION=off, and a plaintext file found
    here is migrated in place before the first query — see `vault_migrate` for
    why that belongs in the connection factory rather than in `entrypoint.sh`.
    """
    key = store_key(db_path, store)
    if key:
        ensure_encrypted(db_path, key)
    connection = sqlcipher.connect(db_path, check_same_thread=False)
    _arm(connection, db_path, key)
    # `:memory:` databases do not support WAL; tests use them heavily.
    if db_path != ":memory:":
        _enable_wal(connection)
        # In WAL mode this is the documented safe setting: a commit no longer
        # waits for an fsync, and the only exposure is losing the last few
        # transactions on a power cut — not corruption. It matters here because
        # several worker PROCESSES share these files and every masked entity is a
        # write; with the default `FULL` the per-commit fsync was most of the
        # contention that produced `database is locked` under a burst.
        connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def connect_readonly(db_path: str, store: str) -> sqlcipher.Connection:
    """A read-only handle for a reader that must not create or migrate anything.

    Used by the billing counter and by the bench tools. It reads what is on disk
    and the HEADER decides how: a store that has not been migrated yet is still
    plaintext, and answering "it is encrypted because the environment says so"
    would make the counter fail on the one start where the migration has not run.
    That is not a fallback to plaintext — nothing is written here, so nothing can
    silently become unencrypted.
    """
    state = file_state(db_path)
    if state == MISSING:
        raise FileNotFoundError(db_path)
    key = "" if state == PLAINTEXT else store_key(db_path, store)
    connection = sqlcipher.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
    _arm(connection, db_path, key)
    return connection


def preflight(db_path: str, store: str) -> None:
    """Open a store once at startup, then close it, and let a failure propagate.

    THE VAULT IS THE ONE STORE NOTHING TOUCHES AT IMPORT TIME. `AuditLog` and
    `Tenants` are process singletons, so a key that does not open them stops the
    worker while it is still starting; a `Vault` is built per org on the first
    request that names one. Without this call a wrong key produced a container
    that started, reported healthy, answered `/health`, and then 500'd on the
    first real message — which is the worst of the three possible behaviours,
    because the customer's gateway had already been told we were up.

    It also finishes the plaintext-to-encrypted migration here rather than inside
    the first customer request, where it would be latency nobody could explain.
    """
    connect(db_path, store).close()


def describe(db_path: str, store: str) -> dict[str, object]:
    """What `PSEUDEX_ROLE=probe` reports for one file: state, and does it open.

    Needed because SQLCipher's one answer covers three different situations. The
    header separates "encrypted" from "plaintext"; actually opening it separates
    "the right key" from "the wrong one".
    """
    state = file_state(db_path)
    record: dict[str, object] = {"path": db_path, "state": state, "opens": None,
                                 "error": ""}
    if state == MISSING:
        return record
    try:
        connection = connect_readonly(db_path, store)
    except (VaultLocked, DatabaseError, Error, vault_key.VaultKeyError) as error:
        record["opens"] = False
        record["error"] = str(error).strip().splitlines()[0] if str(error).strip() else ""
        return record
    try:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    finally:
        connection.close()
    record["opens"] = True
    record["tables"] = tables
    return record


__all__ = [
    "AUDIT_STORE", "Connection", "DatabaseError", "ENCRYPTED", "Error",
    "IntegrityError", "LICENSING_STORE", "OperationalError", "PLAINTEXT",
    "TENANTS_STORE", "VAULT_STORE", "VaultLocked", "connect", "connect_readonly",
    "describe", "preflight", "store_key",
]
