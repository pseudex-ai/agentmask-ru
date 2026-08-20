"""Multi-tenant API keys — the monetization + drop-in foundation.

Each customer gets an Pseudex key (sk-ps-…) we issue. They point their agent's
base_url at Pseudex and use THAT key. Pseudex resolves the key → which customer
(→ their own token vault namespace) and which upstream provider + provider key to
forward to. So a customer plugs us in with one URL + one key, and we bill per key.
"""

import secrets
import logging
import threading
from dataclasses import dataclass

from pseudex.sqlite_setup import connect as sqlite_connect


@dataclass(frozen=True)
class Tenant:
    customer_id: str
    upstream_base_url: str
    upstream_key: str


_log = logging.getLogger("pseudex.tenants")


class Tenants:
    """Connector to the tenant/key store (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tenants ("
            "pseudex_key TEXT PRIMARY KEY, customer_id TEXT, "
            "upstream_base_url TEXT, upstream_key TEXT)"
        )
        self._migrate_key_column()
        self._conn.commit()

    # The product was called obscura, then veilgate, then pseudex, and the key
    # column was renamed with it — twice, with no migration. `CREATE TABLE IF
    # NOT EXISTS` SILENTLY SKIPS an existing table, so a database written under
    # an older name keeps its old column and the first write fails with
    # `no column named pseudex_key`. Reproduced on this repository's own
    # `tenants.db`, which still holds `obscura_key`.
    #
    # No customer can have one — nothing shipped under those names — so this is
    # a footgun for us and for anyone building a stand from an old volume. It is
    # written down anyway because the NEXT rename would do the same thing to a
    # customer, and a rename is exactly the change that looks free.
    _LEGACY_KEY_COLUMNS = ("veilgate_key", "obscura_key")

    def _migrate_key_column(self) -> None:
        columns = [row[1] for row in
                   self._conn.execute("PRAGMA table_info(tenants)").fetchall()]
        if "pseudex_key" in columns:
            return
        legacy = next((name for name in self._LEGACY_KEY_COLUMNS if name in columns), None)
        if legacy is None:
            return
        # RENAME, not copy-into-a-new-table: the keys are live credentials a
        # customer already pasted into their deployment, and reissuing them
        # would be a silent outage rather than a migration.
        self._conn.execute(f"ALTER TABLE tenants RENAME COLUMN {legacy} TO pseudex_key")
        _log.warning("tenants: migrated key column %s -> pseudex_key", legacy)

    def issue(self, customer_id: str, upstream_base_url: str, upstream_key: str) -> str:
        pseudex_key = "sk-ps-" + secrets.token_urlsafe(24)
        self.upsert(pseudex_key, customer_id, upstream_base_url, upstream_key)
        return pseudex_key

    def upsert(self, pseudex_key: str, customer_id: str, upstream_base_url: str, upstream_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tenants "
                "(pseudex_key, customer_id, upstream_base_url, upstream_key) VALUES (?,?,?,?)",
                (pseudex_key, customer_id, upstream_base_url, upstream_key),
            )
            self._conn.commit()

    def resolve(self, pseudex_key: str) -> Tenant | None:
        row = self._conn.execute(
            "SELECT customer_id, upstream_base_url, upstream_key FROM tenants WHERE pseudex_key=?",
            (pseudex_key,),
        ).fetchone()
        return Tenant(row[0], row[1], row[2]) if row is not None else None
