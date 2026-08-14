"""Shared SQLite connection setup for the three stores (vault, audit, tenants).

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
single connection object across threads, which sqlite3 requires when it is
created with check_same_thread=False.
"""

import sqlite3
import time

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


def _enable_wal(connection: sqlite3.Connection) -> None:
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
        except sqlite3.OperationalError as error:
            if "locked" not in str(error) and "busy" not in str(error):
                raise
            mode = None
        if mode is not None and str(mode[0]).lower() == "wal":
            return
        deadline_attempts -= 1
        if deadline_attempts <= 0:
            current = connection.execute("PRAGMA journal_mode").fetchone()
            raise sqlite3.OperationalError(
                f"could not switch {connection} to WAL after "
                f"{_WAL_ATTEMPTS} attempts over "
                f"{_WAL_ATTEMPTS * _WAL_RETRY_SECONDS:.0f}s; journal_mode is "
                f"{current[0] if current else 'unknown'}. Another process is "
                f"holding the database in a different journal mode."
            )
        time.sleep(_WAL_RETRY_SECONDS)


def connect(db_path: str) -> sqlite3.Connection:
    """Open a store with settings that survive concurrent workers."""
    connection = sqlite3.connect(db_path, check_same_thread=False)
    # ORDER MATTERS: busy_timeout first, so every ordinary statement waits on a
    # condition instead of failing fast into the caller.
    connection.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
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
