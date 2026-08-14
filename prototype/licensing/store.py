"""Licensing state: who has a key, what leases were issued, what was used.

Deliberately the same SQLite setup the sidecar uses (`obscura/sqlite_setup.py`,
WAL + busy_timeout armed before journal_mode) — the licensing server is a small
service and a second storage stack would be a second thing to operate.

The key is stored HASHED. It is a bearer credential: anyone holding it can lease
the product, so a dump of this table must not be enough to serve customers. SHA-256
without a salt is correct here and a per-row salt would be worse — the key is 32
bytes of `secrets.token_urlsafe` entropy, so there is no dictionary to attack, and
an unsalted digest is what lets a lookup be a single indexed point query.
"""

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass

from obscura.sqlite_setup import connect as sqlite_connect

KEY_PREFIX = "obsc_live_"

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
STATUS_SUSPENDED = "suspended"
STATUS_UNPAID = "unpaid"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KeyRecord:
    org_id: str
    status: str
    plan: str


class LicenseStore:
    """Connector to the licensing database (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS keys ("
            "key_hash TEXT PRIMARY KEY, org_id TEXT, plan TEXT, status TEXT, created_at REAL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS leases ("
            "lease_id TEXT PRIMARY KEY, org_id TEXT, instance_id TEXT, process_id TEXT, "
            "issued_at REAL, ttl_seconds INTEGER)"
        )
        # Keyed by (org, instance) and holding the LATEST CUMULATIVE totals — not
        # one row per report.
        #
        # The client reports `audit.billing_totals()`, which is everything that
        # instance has ever protected, on every renewal. Summing those rows would
        # bill a customer once per renewal for the same traffic: at a 24 h lease
        # that is a month's usage counted thirty times over.
        #
        # Cumulative-and-overwrite also survives a lost report, which a delta
        # scheme does not: a delta that never arrives is gone, while a missed
        # cumulative report is corrected by the next one.
        #
        # Per INSTANCE, because every worker process of one container shares one
        # audit database and therefore reports the same instance-wide number —
        # summing workers would multiply the bill by the worker count.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "org_id TEXT, instance_id TEXT, updated_at REAL, reports INTEGER, "
            "requests INTEGER, entities TEXT, PRIMARY KEY (org_id, instance_id))"
        )
        self._conn.commit()

    def issue_key(self, org_id: str, plan: str) -> str:
        key = KEY_PREFIX + secrets.token_urlsafe(32)
        with self._lock:
            self._conn.execute(
                "INSERT INTO keys (key_hash, org_id, plan, status, created_at) VALUES (?,?,?,?,?)",
                (hash_key(key), org_id, plan, STATUS_ACTIVE, time.time()),
            )
            self._conn.commit()
        return key

    def lookup(self, key: str) -> KeyRecord | None:
        row = self._conn.execute(
            "SELECT org_id, status, plan FROM keys WHERE key_hash=?", (hash_key(key),)
        ).fetchone()
        return KeyRecord(row[0], row[1], row[2]) if row is not None else None

    def set_status(self, org_id: str, status: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE org_id=?", (status, org_id)
            )
            self._conn.commit()
        return cursor.rowcount

    def record_lease(self, lease_id: str, org_id: str, instance_id: str,
                     process_id: str, ttl_seconds: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO leases "
                "(lease_id, org_id, instance_id, process_id, issued_at, ttl_seconds) "
                "VALUES (?,?,?,?,?,?)",
                (lease_id, org_id, instance_id, process_id, time.time(), ttl_seconds),
            )
            self._conn.commit()

    def record_usage(self, org_id: str, instance_id: str, requests: int,
                     entities: dict[str, int]) -> None:
        """Overwrite this instance's cumulative totals with the newest report."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, requests, entities) "
                "VALUES (?,?,?,1,?,?) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, reports=usage.reports+1, "
                "requests=excluded.requests, entities=excluded.entities",
                (org_id, instance_id, time.time(), requests, json.dumps(entities)),
            )
            self._conn.commit()

    def usage_totals(self, org_id: str) -> dict[str, object]:
        """Billing view: the org's consumption, summed across its INSTANCES.

        Summing instances is right (two containers are two deployments doing real
        work); summing reports would not be, because each report restates the same
        cumulative total."""
        rows = self._conn.execute(
            "SELECT instance_id, reports, requests, entities FROM usage WHERE org_id=?",
            (org_id,),
        ).fetchall()
        entities: dict[str, int] = {}
        requests = 0
        reports = 0
        for _instance, row_reports, row_requests, row_entities in rows:
            requests += row_requests
            reports += row_reports
            for entity_type, count in json.loads(row_entities).items():
                entities[entity_type] = entities.get(entity_type, 0) + count
        return {"org_id": org_id, "instances": len(rows), "reports": reports,
                "requests": requests, "entities": entities}

    def instances(self, org_id: str) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT instance_id, process_id, issued_at FROM leases WHERE org_id=? "
            "ORDER BY issued_at DESC LIMIT 100", (org_id,)
        ).fetchall()
        return [{"instance_id": r[0], "process_id": r[1], "issued_at": r[2]} for r in rows]

    def list_orgs(self) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT org_id, plan, status, created_at FROM keys ORDER BY created_at"
        ).fetchall()
        return [{"org_id": r[0], "plan": r[1], "status": r[2], "created_at": r[3]}
                for r in rows]
