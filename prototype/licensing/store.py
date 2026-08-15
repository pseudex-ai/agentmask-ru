"""Licensing state: who has a key, what leases were issued, what was used.

Deliberately the same SQLite setup the sidecar uses (`pseudex/sqlite_setup.py`,
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
import logging
import secrets
import threading
import time
from dataclasses import dataclass

from pseudex.sqlite_setup import connect as sqlite_connect

KEY_PREFIX = "ps_live_"

_log = logging.getLogger("licensing.store")

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
            "requests INTEGER, entities TEXT, "
            # The billed quantity, accumulated MONOTONICALLY on our side.
            # `values_reported` is the last number the installation sent;
            # `values_total` never decreases.
            "values_reported INTEGER DEFAULT 0, values_total INTEGER DEFAULT 0, "
            "resets INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, instance_id))"
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

    def revoke_key_hash(self, key_hash: str) -> int:
        """Revoke ONE key. Statuses were per-organisation only, so the cabinet's
        "отозвать ключ" button set a local flag, reported success, and left the
        key leasing forever — the departing engineer's copy kept working.

        Matched on the hash because that is all the storefront holds: the key
        itself is shown once and never stored in readable form on either side.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE key_hash=? AND status=?",
                (STATUS_REVOKED, key_hash, STATUS_ACTIVE),
            )
            self._conn.commit()
            return cursor.rowcount

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

    def _accumulate_values(self, org_id: str, instance_id: str, reported: int) -> int:
        """Fold a new reading into a counter that never goes backwards.

        The vault lives on the customer's volume, so `docker volume rm` restarts
        `first_seen` and the reported count drops to zero. Billing the reported
        number directly would make deleting the vault a way not to pay.

        A drop is treated as a NEW INSTALLATION rather than as a correction: the
        growth since the reset is added on top of what was already accumulated.
        Re-protecting the same people after a reset therefore counts again,
        which is the honest reading — the engine did the work a second time.

        It is not evidence of anything. A vault can be lost honestly, in a
        migration or a disk failure. It is recorded as a `reset` so a pattern is
        visible, and a pattern is a conversation, not an accusation.
        """
        row = self._conn.execute(
            "SELECT values_reported, values_total, resets FROM usage "
            "WHERE org_id=? AND instance_id=?", (org_id, instance_id),
        ).fetchone()
        if row is None:
            return reported
        previous, total, resets = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
        if reported >= previous:
            return total + (reported - previous)
        _log.warning("usage counter went backwards for org=%s instance=%s: "
                     "%d -> %d (vault reset or restore); accumulating on top",
                     org_id, instance_id, previous, reported)
        self._conn.execute(
            "UPDATE usage SET resets=? WHERE org_id=? AND instance_id=?",
            (resets + 1, org_id, instance_id),
        )
        return total + reported

    def record_usage(self, org_id: str, instance_id: str, requests: int,
                     entities: dict[str, int], values: int) -> None:
        """Record the newest report.

        `requests` and `entities` are OVERWRITTEN — each report restates the
        instance's own cumulative totals, so the latest one is the truth.

        `values` is different, because it is what the invoice is computed from:
        it is folded into a counter that never decreases, so a customer who
        deletes their vault does not thereby delete what they owe. See
        docs/billing-integrity.md §2.1.
        """
        with self._lock:
            accumulated = self._accumulate_values(org_id, instance_id, values)
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, requests, "
                "entities, values_reported, values_total) VALUES (?,?,?,1,?,?,?,?) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, reports=usage.reports+1, "
                "requests=excluded.requests, entities=excluded.entities, "
                "values_reported=excluded.values_reported, "
                "values_total=excluded.values_total",
                (org_id, instance_id, time.time(), requests, json.dumps(entities),
                 values, accumulated),
            )
            self._conn.commit()

    def usage_totals(self, org_id: str) -> dict[str, object]:
        """Billing view: the org's consumption, summed across its INSTANCES.

        Summing instances is right (two containers are two deployments doing real
        work); summing reports would not be, because each report restates the same
        cumulative total."""
        rows = self._conn.execute(
            "SELECT instance_id, reports, requests, entities, values_total, resets "
            "FROM usage WHERE org_id=?",
            (org_id,),
        ).fetchall()
        entities: dict[str, int] = {}
        requests = reports = values = resets = 0
        for _instance, row_reports, row_requests, row_entities, row_values, row_resets in rows:
            requests += row_requests
            reports += row_reports
            values += int(row_values or 0)
            resets += int(row_resets or 0)
            for entity_type, count in json.loads(row_entities).items():
                entities[entity_type] = entities.get(entity_type, 0) + count
        return {"org_id": org_id, "instances": len(rows), "reports": reports,
                "requests": requests, "entities": entities,
                # THE BILLED QUANTITY. Monotonic and summed across instances,
                # because two containers are two deployments doing real work.
                "values": values,
                # Times an instance's counter went backwards. Not evidence — a
                # vault can be lost honestly — but a pattern worth seeing.
                "resets": resets}

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
