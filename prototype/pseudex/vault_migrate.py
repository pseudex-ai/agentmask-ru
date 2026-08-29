"""Turning an existing plaintext store into an encrypted one, in place.

There is no downtime problem to solve here: 50 000 rows export in hundredths of a
second, shorter than the natasha model load every worker already pays at startup.
Dual-write with a backfill would be engineering for a problem that does not
exist. So the migration runs inside the connection factory, once, before the
first query.

THE FIVE THINGS THAT ARE NOT OBVIOUS, each of which was a defect waiting:

  * THE LOCK LIVES HERE, not in `entrypoint.sh`. `uvicorn pseudex.service:app` is
    a supported launch shape (CLAUDE.md, deployment shape B), and eight workers
    behind one SO_REUSEPORT port start simultaneously by design. Whoever opens
    the file first must migrate it and the rest must wait, whatever started them.

  * IDEMPOTENCY IS DECIDED BY THE FILE HEADER, never by catching an exception.
    SQLCipher answers `file is not a database` to a wrong key, a corrupt file and
    an unencrypted database alike, so "it threw, therefore it was already
    encrypted" would quietly skip a real migration and hand the caller a store it
    could not read.

  * EACH FILE MIGRATES SEPARATELY. A volume can be half-migrated — the container
    was killed between `vault.db` and `audit.db` — and the second start must
    finish the job rather than refuse the whole directory.

  * `PRAGMA wal_checkpoint(TRUNCATE)` COMES FIRST OR THE PERSONAL DATA STAYS IN
    THE `-wal`. Measured on a live vault: zero matches for the phone and the name
    inside `vault.db`, both present in `vault.db-wal`. Exporting the main file
    and leaving the write-ahead log beside it would produce an encrypted database
    with the plaintext still on disk next to it.

  * THE PLAINTEXT COPY IS UNLINKED, NOT ERASED, and the difference is the whole
    honesty of the sentence. `os.replace` and `os.remove` remove DIRECTORY
    ENTRIES; the blocks that held the plaintext database and its `-wal` are
    returned to the filesystem with their contents intact, and a forensic tool
    reads them until they are overwritten by something else. A volume that ever
    held plaintext must be treated as still holding it — the encryption protects
    what is written from now on, not what the disk already learned.

    Overwriting them deliberately is NOT done and will not be: secure erase is
    unreliable on overlay2, on copy-on-write filesystems and on SSDs, whose
    controllers move blocks out from under any write we could issue. Gate L14b
    rejected byte-absence assertions about freed MEMORY for exactly this reason,
    and inventing a guarantee here that the product cannot keep would be worse
    than naming the gap.

    No plaintext copy is kept by default: PSEUDEX_VAULT_MIGRATION_BACKUP is a
    deliberate act by the operator, because keeping one automatically would mean
    creating with our own hands the second plaintext copy the whole product
    exists to prevent.

The tokens already sitting in the customer's CRM are untouched:
`sqlcipher_export` copies rows verbatim. That is the entire reason this is a
migration and not a re-issue.
"""

import fcntl
import logging
import os
import shutil

from sqlcipher3 import dbapi2 as sqlcipher

from pseudex.vault_key import key_literal

# Every SQLite file starts with this. An encrypted one starts with the ciphertext
# of its first page, which is indistinguishable from random.
_PLAIN_HEADER = b"SQLite format 3\x00"

MISSING = "missing"
EMPTY = "empty"
PLAINTEXT = "plaintext"
ENCRYPTED = "encrypted"

_log = logging.getLogger("pseudex.vault_migrate")


class VaultMigrationError(RuntimeError):
    """The migration could not be completed safely, so nothing was replaced."""


def file_state(db_path: str) -> str:
    """What is on disk, decided by the first sixteen bytes and nothing else."""
    try:
        with open(db_path, "rb") as handle:
            header = handle.read(16)
    except FileNotFoundError:
        return MISSING
    if not header:
        return EMPTY
    return PLAINTEXT if header == _PLAIN_HEADER else ENCRYPTED


def _quote(value: str) -> str:
    """SQL string literal. `PRAGMA key` and `ATTACH ... KEY` take no parameters
    (`near "?": syntax error`), so every value here is substituted by hand."""
    return "'" + value.replace("'", "''") + "'"


def _tables(conn: sqlcipher.Connection) -> list[str]:
    return [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _row_counts(conn: sqlcipher.Connection) -> dict[str, int]:
    return {name: conn.execute(f"SELECT COUNT(*) FROM \"{name}\"").fetchone()[0]
            for name in _tables(conn)}


def _sidecar_files(db_path: str) -> tuple[str, str]:
    return db_path + "-wal", db_path + "-shm"


def _discard(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _fsync_dir(path: str) -> None:
    """A rename is only durable once the DIRECTORY entry is on disk."""
    handle = os.open(path, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _fsync_file(path: str) -> None:
    handle = os.open(path, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def _backup(db_path: str) -> None:
    destination = os.environ.get("PSEUDEX_VAULT_MIGRATION_BACKUP", "").strip()
    if not destination:
        return
    os.makedirs(destination, exist_ok=True)
    target = os.path.join(destination, os.path.basename(db_path) + ".plain")
    shutil.copy2(db_path, target)
    _log.warning(
        "vault: PSEUDEX_VAULT_MIGRATION_BACKUP kept a PLAINTEXT copy at %s. It "
        "holds every real value the vault held. Delete it once the encrypted "
        "store is proven, or it is the leak the encryption was bought to stop.",
        target,
    )


def _export(source: sqlcipher.Connection, tmp_path: str, key_hex: str,
            db_path: str) -> None:
    """Copy every row into a fresh file, encrypted (key_hex) or not (empty).

    `sqlcipher_export` is SQLCipher's own bulk copy: schema, indexes, rows,
    verbatim. It is used in both directions, which is what makes the door two-way
    — the `decrypt` role is this same call with an empty key.
    """
    key_clause = key_literal(key_hex) if key_hex else "''"
    source.execute(
        f"ATTACH DATABASE {_quote(tmp_path)} AS target KEY {key_clause}")
    try:
        source.execute("SELECT sqlcipher_export('target')")
        source.commit()
    finally:
        source.execute("DETACH DATABASE target")
    # The freshly written file is verified through a SECOND connection, opened
    # the way the product will open it. Reading back through the attach handle
    # would prove only that the copy is consistent with itself.
    check = sqlcipher.connect(tmp_path)
    try:
        if key_hex:
            check.execute(f"PRAGMA key = {key_literal(key_hex)}")
        expected = _row_counts(source)
        actual = _row_counts(check)
    finally:
        check.close()
    if expected != actual:
        differing = {name: (expected.get(name), actual.get(name))
                     for name in set(expected) | set(actual)
                     if expected.get(name) != actual.get(name)}
        raise VaultMigrationError(
            f"{db_path}: row counts differ after export, nothing was replaced. "
            f"table -> (before, after): {differing}"
        )


def _swap(tmp_path: str, db_path: str) -> None:
    _fsync_file(tmp_path)
    for stray in _sidecar_files(tmp_path):
        _discard(stray)
    os.replace(tmp_path, db_path)
    # The old write-ahead log belongs to the file that no longer exists, and it
    # is where the plaintext lived. It goes with it.
    for stray in _sidecar_files(db_path):
        _discard(stray)
    _fsync_dir(os.path.dirname(os.path.abspath(db_path)) or ".")


def _convert(db_path: str, open_key: str, write_key: str) -> None:
    """One conversion, under the caller's lock. `open_key` reads what is there,
    `write_key` writes the replacement; either may be empty."""
    tmp_path = db_path + ".migrate.tmp"
    _discard(tmp_path)
    source = sqlcipher.connect(db_path)
    try:
        if open_key:
            source.execute(f"PRAGMA key = {key_literal(open_key)}")
            # Proved before a single byte is written, and with our own sentence.
            # Without it the first statement below fails as `file is not a
            # database` from inside a half-started conversion, and the operator
            # is told their file is corrupt when their key is simply the wrong
            # one. Nothing is replaced either way — the swap is the last step —
            # but the message is what they will act on.
            try:
                source.execute("SELECT count(*) FROM sqlite_master").fetchone()
            except sqlcipher.DatabaseError as error:
                raise VaultMigrationError(
                    f"{db_path}: этот ключ не открывает файл ({error}). Ничего "
                    f"не изменено. PSEUDEX_ROLE=probe покажет состояние каждого "
                    f"файла тома."
                ) from None
        # Before anything else: the personal data is in the -wal until this runs.
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        if write_key:
            _backup(db_path)
        _export(source, tmp_path, write_key, db_path)
    finally:
        source.close()
    _swap(tmp_path, db_path)


class _Lock:
    """flock on `<db>.lock`, held across the header re-check and the swap.

    A lock ON the database file itself would be wrong twice: SQLite takes its own
    locks there, and the file is about to be replaced by `os.replace`, which
    would leave every waiter holding a lock on an unlinked inode.
    """

    def __init__(self, db_path: str) -> None:
        self._path = db_path + ".lock"
        self._fd = -1

    def __enter__(self) -> "_Lock":
        self._fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)


def ensure_encrypted(db_path: str, key_hex: str) -> str:
    """Make `db_path` an encrypted store. Returns what was done."""
    state = file_state(db_path)
    if state != PLAINTEXT:
        return state
    with _Lock(db_path):
        # Re-read under the lock. Six processes starting together all saw
        # plaintext outside it; exactly one may act on that.
        if file_state(db_path) != PLAINTEXT:
            return ENCRYPTED
        _log.warning("vault: %s is plaintext — encrypting it in place", db_path)
        _convert(db_path, "", key_hex)
        # «unlinked», never «gone»: the directory entries are removed and the
        # BLOCKS are not overwritten. An operator who reads «gone» stops
        # worrying about the disk that volume has been living on.
        _log.warning("vault: %s encrypted; the plaintext file and its -wal are "
                     "unlinked, NOT securely erased — their blocks stay readable "
                     "on this disk until something else overwrites them. Treat a "
                     "volume that once held plaintext as still holding it. "
                     "Tokens already issued are unchanged.", db_path)
    return "migrated"


def rekey_store(db_path: str, old_key: str, new_key: str) -> str:
    """Move one store from one key to another, in place, without re-exporting.

    `PRAGMA rekey` re-encrypts every page with the new key and leaves the rows
    untouched, so the substitutes already sitting in the customer's CRM keep
    meaning what they meant. That is the whole reason rotation is cheap enough
    to be a routine act rather than an incident.

    THE CHECKPOINT IS NOT OPTIONAL. Pages in the write-ahead log are encrypted
    under the OLD key and `rekey` does not walk them; without truncating the WAL
    first, the database ends up on the new key with frames beside it that only
    the old one opens.

    A store is either fully on the new key or untouched — but a VOLUME is not:
    each file is rekeyed separately, so an interruption leaves some files on one
    key and some on the other. The caller reports which is which, and
    PSEUDEX_ROLE=probe answers the same question afterwards; there is no way to
    make it atomic across files, so the honest thing is to make the state
    legible instead of pretending.
    """
    state = file_state(db_path)
    if state in (MISSING, EMPTY):
        return state
    if state == PLAINTEXT:
        # Not "rekeyed silently": a plaintext file has no key to rotate, and the
        # ordinary connection path is what encrypts it.
        return PLAINTEXT
    with _Lock(db_path):
        connection = sqlcipher.connect(db_path)
        try:
            connection.execute(f"PRAGMA key = {key_literal(old_key)}")
            try:
                connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            except sqlcipher.DatabaseError as error:
                raise VaultMigrationError(
                    f"{db_path}: текущий ключ не открывает файл ({error}). Ничего "
                    f"не изменено."
                ) from None
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute(f"PRAGMA rekey = {key_literal(new_key)}")
            connection.commit()
        finally:
            connection.close()
    # Proved through a NEW connection with the new key. Asking the connection
    # that just performed the rekey would only prove it still holds the page
    # cache it wrote.
    check = sqlcipher.connect(db_path)
    try:
        check.execute(f"PRAGMA key = {key_literal(new_key)}")
        check.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlcipher.DatabaseError as error:
        raise VaultMigrationError(
            f"{db_path}: после rekey файл не открывается НОВЫМ ключом ({error}). "
            f"Не выключайте старый ключ."
        ) from None
    finally:
        check.close()
    return "rekeyed"


def decrypt_store(db_path: str, key_hex: str) -> str:
    """The reverse. The door is not one-way, and this is why it is not.

    An operator leaving the product must be able to take their data with them in
    a form any tool reads, and an operator evaluating it must be able to see that
    they can before they commit.
    """
    state = file_state(db_path)
    if state in (MISSING, EMPTY):
        return state
    if state == PLAINTEXT:
        return PLAINTEXT
    with _Lock(db_path):
        if file_state(db_path) != ENCRYPTED:
            return PLAINTEXT
        _log.warning("vault: decrypting %s — the result is PLAIN TEXT on disk", db_path)
        _convert(db_path, key_hex, "")
    return "decrypted"
