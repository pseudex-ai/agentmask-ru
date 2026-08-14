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

import threading
import time

from obscura.profiling import stage
from obscura.sqlite_setup import connect as sqlite_connect


def _preview(value: str) -> str:
    """Masked preview: keep first 2 + last 2 chars, hide the middle."""
    if len(value) <= 4:
        return value[0] + "•" * (len(value) - 1)
    return value[:2] + "•" * (len(value) - 4) + value[-2:]


class AuditLog:
    """Connector to the append-only audit store (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path)
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

    def record_many(self, customer: str, agent_id: str,
                    events: list[tuple[str, str, str]]) -> None:
        """All spans of ONE message in ONE transaction.

        `record` commits per span, which the note below has flagged since it was
        written. It stopped being a latency remark and became a correctness bug
        once several worker PROCESSES shared the file: a message with eight
        entities was eight commits, and four workers under a 16-way burst turned
        that into `sqlite3.OperationalError: database is locked` on 46 of 64
        requests. In a fail-closed gateway every one of those is a blocked user
        request.

        `events` is (entity_type, token, real_value); only a masked preview of
        the value is stored, as with `record`."""
        if not events:
            return
        now = time.time()
        rows = [(now, customer, agent_id, entity_type, token, _preview(real_value))
                for entity_type, token, real_value in events]
        with stage("audit.record_many"), self._lock:
            self._conn.executemany(
                "INSERT INTO events (ts, customer, agent_id, entity_type, token, preview) "
                "VALUES (?,?,?,?,?,?)",
                rows,
            )
            self._conn.commit()

    def record(self, customer: str, agent_id: str, entity_type: str, token: str, real_value: str) -> None:
        # NOTE: one commit — hence one fsync — per DETECTED SPAN. A message with
        # 10 entities pays 10 fsyncs on the request's critical path. The audit is
        # not needed to answer the request, so batching it behind a queue with a
        # background writer is the obvious win; see docs/spec.md §4.2. Profile
        # first: this stage tells you whether it actually costs anything here.
        with stage("audit.record"), self._lock:
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

    def billing_totals(self) -> dict[str, object]:
        """Instance-wide aggregates for the licensing server.

        Instance-wide, not per-org: the licence is bought by the organisation that
        runs the container, and the org_id inside it is that customer's own
        tenancy — not something we bill separately.

        This is the ONLY thing that leaves the customer's contour, so it is
        deliberately shaped so that it cannot carry personal data: counts and a
        total, no tokens, no previews, no free-text fields. Gate L12 greps the
        request body for every injected value to keep it that way."""
        # Under the lock, unlike the other read paths: this one is called from the
        # LICENCE THREAD on every renewal while mask workers are writing on the
        # same connection. sqlite3 with check_same_thread=False does not make a
        # connection concurrent — interleaving an aggregate with a locked
        # INSERT+commit raises ProgrammingError or returns a torn count, and the
        # exception would surface inside the renewal path.
        with self._lock:
            rows = self._conn.execute(
                "SELECT entity_type, COUNT(*) FROM events GROUP BY entity_type"
            ).fetchall()
        entities = {row[0]: row[1] for row in rows}
        return {"requests": sum(entities.values()), "entities": entities}

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
