"""Multi-tenant API keys — the monetization + drop-in foundation.

Each customer gets an Pseudex key (sk-ps-…) we issue. They point their agent's
base_url at Pseudex and use THAT key. Pseudex resolves the key → which customer
(→ their own token vault namespace) and which upstream provider + provider key to
forward to. So a customer plugs us in with one URL + one key, and we bill per key.
"""

import secrets
import threading
from dataclasses import dataclass

from pseudex.sqlite_setup import connect as sqlite_connect


@dataclass(frozen=True)
class Tenant:
    customer_id: str
    upstream_base_url: str
    upstream_key: str


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
        self._conn.commit()

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
