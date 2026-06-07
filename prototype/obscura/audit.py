"""Audit log of what was caught and what it was replaced with — feeds the Diva
backend stats API (and a future UI) so customers see what they pay for.

Scope: every event is keyed by (customer/org, agent_id). Org-wide queries
(`counts`/`recent`) aggregate all agents; per-agent queries
(`counts_for_agent`/`recent_for_agent`) power the per-agent stats endpoint.

Privacy: the log stores entity_type + the fake token + a MASKED preview of the
original (first/last chars only). It deliberately does NOT store the full real
value — the only place that lives is the in-RF vault. So the audit log is not a
second PII exposure surface.
"""

import sqlite3
import threading
import time


def _preview(value: str) -> str:
    """Masked preview: keep first 2 + last 2 chars, hide the middle."""
    if len(value) <= 4:
        return value[0] + "•" * (len(value) - 1)
    return value[:2] + "•" * (len(value) - 4) + value[-2:]


class AuditLog:
    """Connector to the append-only audit store (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "ts REAL, customer TEXT, agent_id TEXT, entity_type TEXT, token TEXT, preview TEXT)"
        )
        self._migrate_agent_id()
        self._conn.commit()

    def _migrate_agent_id(self) -> None:
        """Add agent_id to a pre-existing table created before this column."""
        columns = [row[1] for row in self._conn.execute("PRAGMA table_info(events)").fetchall()]
        if "agent_id" not in columns:
            self._conn.execute("ALTER TABLE events ADD COLUMN agent_id TEXT DEFAULT ''")

    def record(self, customer: str, agent_id: str, entity_type: str, token: str, real_value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, customer, agent_id, entity_type, token, preview) "
                "VALUES (?,?,?,?,?,?)",
                (time.time(), customer, agent_id, entity_type, token, _preview(real_value)),
            )
            self._conn.commit()

    def counts(self, customer: str) -> dict[str, int]:
        """Counts per entity type across all of an org's agents."""
        rows = self._conn.execute(
            "SELECT entity_type, COUNT(*) FROM events WHERE customer=? GROUP BY entity_type",
            (customer,),
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def counts_for_agent(self, customer: str, agent_id: str) -> dict[str, int]:
        """Counts per entity type for a single agent."""
        rows = self._conn.execute(
            "SELECT entity_type, COUNT(*) FROM events WHERE customer=? AND agent_id=? GROUP BY entity_type",
            (customer, agent_id),
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def recent(self, customer: str, limit: int) -> list[dict[str, object]]:
        """Most recent caught items across all of an org's agents."""
        rows = self._conn.execute(
            "SELECT ts, agent_id, entity_type, token, preview FROM events WHERE customer=? "
            "ORDER BY ts DESC LIMIT ?",
            (customer, limit),
        ).fetchall()
        return [{"ts": r[0], "agent_id": r[1], "type": r[2], "token": r[3], "preview": r[4]} for r in rows]

    def recent_for_agent(self, customer: str, agent_id: str, limit: int) -> list[dict[str, object]]:
        """Most recent caught items for a single agent (type / token / masked original)."""
        rows = self._conn.execute(
            "SELECT ts, entity_type, token, preview FROM events WHERE customer=? AND agent_id=? "
            "ORDER BY ts DESC LIMIT ?",
            (customer, agent_id, limit),
        ).fetchall()
        return [{"ts": r[0], "type": r[1], "token": r[2], "preview": r[3]} for r in rows]
