"""Multi-tenant API keys — the monetization + drop-in foundation.

Each customer gets an Obscura key (sk-obsc-…) we issue. They point their agent's
base_url at Obscura and use THAT key. Obscura resolves the key → which customer
(→ their own token vault namespace) and which upstream provider + provider key to
forward to. So a customer plugs us in with one URL + one key, and we bill per key.
"""

import secrets
import sqlite3
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Tenant:
    customer_id: str
    upstream_base_url: str
    upstream_key: str


class Tenants:
    """Connector to the tenant/key store (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tenants ("
            "obscura_key TEXT PRIMARY KEY, customer_id TEXT, "
            "upstream_base_url TEXT, upstream_key TEXT)"
        )
        self._conn.commit()

    def issue(self, customer_id: str, upstream_base_url: str, upstream_key: str) -> str:
        obscura_key = "sk-obsc-" + secrets.token_urlsafe(24)
        self.upsert(obscura_key, customer_id, upstream_base_url, upstream_key)
        return obscura_key

    def upsert(self, obscura_key: str, customer_id: str, upstream_base_url: str, upstream_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tenants "
                "(obscura_key, customer_id, upstream_base_url, upstream_key) VALUES (?,?,?,?)",
                (obscura_key, customer_id, upstream_base_url, upstream_key),
            )
            self._conn.commit()

    def resolve(self, obscura_key: str) -> Tenant | None:
        row = self._conn.execute(
            "SELECT customer_id, upstream_base_url, upstream_key FROM tenants WHERE obscura_key=?",
            (obscura_key,),
        ).fetchone()
        return Tenant(row[0], row[1], row[2]) if row is not None else None
