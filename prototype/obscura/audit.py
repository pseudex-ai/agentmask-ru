"""Audit log of what was caught and what it was replaced with — feeds a future
UI so customers see what they pay for.

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
            "ts REAL, customer TEXT, entity_type TEXT, token TEXT, preview TEXT)"
        )
        self._conn.commit()

    def record(self, customer: str, entity_type: str, token: str, real_value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (ts, customer, entity_type, token, preview) VALUES (?,?,?,?,?)",
                (time.time(), customer, entity_type, token, _preview(real_value)),
            )
            self._conn.commit()

    def counts(self, customer: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT entity_type, COUNT(*) FROM events WHERE customer=? GROUP BY entity_type",
            (customer,),
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def recent(self, customer: str, limit: int) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT ts, entity_type, token, preview FROM events WHERE customer=? "
            "ORDER BY ts DESC LIMIT ?",
            (customer, limit),
        ).fetchall()
        return [{"ts": r[0], "type": r[1], "token": r[2], "preview": r[3]} for r in rows]
