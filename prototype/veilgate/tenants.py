"""Multi-tenant API keys — the monetization + drop-in foundation.

Each customer gets an Veilgate key (sk-vg-…) we issue. They point their agent's
base_url at Veilgate and use THAT key. Veilgate resolves the key → which customer
(→ their own token vault namespace) and which upstream provider + provider key to
forward to. So a customer plugs us in with one URL + one key, and we bill per key.
"""

import secrets
import threading
from dataclasses import dataclass

from veilgate.sqlite_setup import connect as sqlite_connect


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
            "veilgate_key TEXT PRIMARY KEY, customer_id TEXT, "
            "upstream_base_url TEXT, upstream_key TEXT)"
        )
        self._conn.commit()

    def issue(self, customer_id: str, upstream_base_url: str, upstream_key: str) -> str:
        veilgate_key = "sk-vg-" + secrets.token_urlsafe(24)
        self.upsert(veilgate_key, customer_id, upstream_base_url, upstream_key)
        return veilgate_key

    def upsert(self, veilgate_key: str, customer_id: str, upstream_base_url: str, upstream_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tenants "
                "(veilgate_key, customer_id, upstream_base_url, upstream_key) VALUES (?,?,?,?)",
                (veilgate_key, customer_id, upstream_base_url, upstream_key),
            )
            self._conn.commit()

    def resolve(self, veilgate_key: str) -> Tenant | None:
        row = self._conn.execute(
            "SELECT customer_id, upstream_base_url, upstream_key FROM tenants WHERE veilgate_key=?",
            (veilgate_key,),
        ).fetchone()
        return Tenant(row[0], row[1], row[2]) if row is not None else None
