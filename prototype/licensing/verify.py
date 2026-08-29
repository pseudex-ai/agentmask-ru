"""Is this copy of the licensing database a WORKING database, and how full is it.

    python -m licensing.verify /path/to/license.db

Exists for the weekly restore drill (`deploy/restore-drill.sh`), which used the
HOST's `sqlite3` and degraded to a header probe when the host did not have one.
Two problems with that, and the second arrived with encryption:

  * a header probe is the weaker check `docs/decisions.md` explicitly rejected —
    a dump truncated half way reads perfectly, restores into nothing, and passes
    every freshness test there is. The drill exists to catch exactly that, so the
    assertion has to be on ROWS;
  * a header probe cannot work at all on an encrypted store, and neither can the
    host's `sqlite3`: it has no SQLCipher, so it answers `file is not a database`
    to a perfectly good backup.

So the check moves into the image that already knows how to open the store, and
opens it through the PRODUCT's own factory rather than restating the key
handling. One place knows how a store is opened; this is a caller of it.

It never writes and never migrates: `connect_readonly` decides plaintext from
encrypted by the file header, so a copy taken before the migration is still
readable and a copy taken after is readable only with its key — which is the
truth the drill needs to report, not something to paper over.
"""

import sys

from pseudex.sqlite_setup import LICENSING_STORE, connect_readonly

# The tables that make the licensing database worth restoring. `keys` is the one
# that cannot be rebuilt from code — losing it stops every deployment in the
# field — so an empty one is a failed drill and not a quiet zero.
REQUIRED_TABLES = ("keys",)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m licensing.verify <license.db>", file=sys.stderr)
        return 2
    path = argv[1]
    try:
        connection = connect_readonly(path, LICENSING_STORE)
    except Exception as error:  # noqa: BLE001 — every failure is the same verdict
        # Deliberately broad and deliberately loud. A copy that cannot be opened
        # is a failed drill whatever the reason — wrong key, truncated file,
        # missing file — and the drill must never be able to read this as a pass.
        print(f"cannot open {path}: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    try:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts = {name: connection.execute(
            f"SELECT COUNT(*) FROM \"{name}\"").fetchone()[0] for name in names}
    finally:
        connection.close()

    for name in sorted(counts):
        print(f"{name}={counts[name]}")
    empty = [name for name in REQUIRED_TABLES if counts.get(name, 0) <= 0]
    if empty:
        print(f"tables present but EMPTY: {', '.join(empty)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
