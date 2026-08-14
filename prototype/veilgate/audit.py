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

from veilgate.profiling import stage
from veilgate.sqlite_setup import connect as sqlite_connect

# Day buckets follow the CONTAINER's local time, not UTC. The screens that read
# them say "сегодня" to an operator sitting in one office, and a Moscow customer
# reading a UTC bucket at 01:00 would be shown yesterday. Docker defaults to UTC;
# a customer who cares sets TZ, and then every number here agrees with their wall
# clock. Stored as a string so the aggregate is a plain indexed GROUP BY.
def _day(when: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(when))


# The self-check runs the REAL masking path, so it mints real tokens and writes
# real audit rows — that is what makes it a check rather than an assertion. It
# does so under this org, which is excluded from the billed totals: a customer
# pressing "проверить сейчас" before calling support must not be charged for
# proving our product works.
SELFCHECK_ORG = "__veilgate_selfcheck__"


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
        # Requests are counted SEPARATELY from entities, and the difference is
        # not cosmetic. `billing_totals` used to report sum(entities) as
        # "requests", so the number the licensing server bills on was the count
        # of detected VALUES. A customer whose messages carry six entities each
        # burned a 100 000-request plan in under 17 000 requests. The two numbers
        # also mean different things to the operator ("запросов обработано" vs
        # "значений защищено") and the UI shows both.
        #
        # A request with no PII in it is still a request, so this cannot be
        # derived from the events table at any level of cleverness — it has to be
        # its own counter, incremented once per masking call.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS requests ("
            "customer TEXT, agent_id TEXT, day TEXT, n INTEGER, "
            "PRIMARY KEY (customer, agent_id, day))"
        )
        # Who looked at a real value, and when. NOT what they saw: storing the
        # revealed value would make this log a second copy of the personal data
        # the vault exists to contain, which is the failure this table is meant
        # to prevent rather than cause.
        #
        # Written by the ENGINE on the /reveal path, not by the UI that asked.
        # The UI is one caller among possible others (curl against the sidecar
        # port is a supported shape), and a log the caller writes about itself is
        # not a log. Without this table the product hands the customer a
        # disclosure channel with no accountability — worse for them under 152-ФЗ
        # than not having it at all.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS reveals ("
            "ts REAL, customer TEXT, actor TEXT, token TEXT, entity_type TEXT, found INTEGER)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS events_customer_ts "
                           "ON events (customer, ts DESC)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS reveals_customer_ts "
                           "ON reveals (customer, ts DESC)")
        self._migrate_agent_id()
        self._conn.commit()

    def record_request(self, customer: str, agent_id: str) -> None:
        """One masking call. Deliberately its own commit rather than folded into
        the audit write: a request that found no PII writes no events but is
        still billable, so the counter cannot ride along with the entity rows."""
        with stage("audit.record_request"), self._lock:
            self._conn.execute(
                "INSERT INTO requests (customer, agent_id, day, n) VALUES (?,?,?,1) "
                "ON CONFLICT(customer, agent_id, day) DO UPDATE SET n = n + 1",
                (customer, agent_id, _day(time.time())),
            )
            self._conn.commit()

    def record_reveal(self, customer: str, actor: str, token: str,
                      entity_type: str, found: bool) -> None:
        """A disclosure happened. `found` records misses too — a sweep of guessed
        tokens is exactly the pattern this log needs to make visible, and it
        leaves no other trace."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO reveals (ts, customer, actor, token, entity_type, found) "
                "VALUES (?,?,?,?,?,?)",
                (time.time(), customer, actor, token, entity_type, 1 if found else 0),
            )
            self._conn.commit()

    def reveals(self, customer: str, limit: int, offset: int) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT ts, actor, token, entity_type, found FROM reveals WHERE customer=? "
            "ORDER BY ts DESC LIMIT ? OFFSET ?",
            (customer, limit, offset),
        ).fetchall()
        return [{"ts": r[0], "actor": r[1], "token": r[2], "type": r[3],
                 "found": bool(r[4])} for r in rows]

    def reveals_count(self, customer: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM reveals WHERE customer=?", (customer,)
        ).fetchone()
        return int(row[0]) if row else 0

    def request_totals(self, customer: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(n), 0) FROM requests WHERE customer=?", (customer,)
        ).fetchone()
        return int(row[0]) if row else 0

    def daily_series(self, customer: str, days: int) -> list[dict[str, object]]:
        """Requests and protected values per day, oldest first, with empty days
        filled in. A chart that silently omits a zero day compresses the gap and
        reads as steady traffic across an outage."""
        now = time.time()
        wanted = [_day(now - (days - 1 - index) * 86400) for index in range(days)]
        request_rows = dict(self._conn.execute(
            "SELECT day, SUM(n) FROM requests WHERE customer=? GROUP BY day",
            (customer,),
        ).fetchall())
        event_rows = dict(self._conn.execute(
            "SELECT DATE(ts, 'unixepoch', 'localtime'), COUNT(*) FROM events "
            "WHERE customer=? GROUP BY 1",
            (customer,),
        ).fetchall())
        return [{"day": day,
                 "requests": int(request_rows.get(day, 0)),
                 "values": int(event_rows.get(day, 0))}
                for day in wanted]

    def by_agent(self, customer: str) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT agent_id, SUM(n) FROM requests WHERE customer=? "
            "GROUP BY agent_id ORDER BY 2 DESC",
            (customer,),
        ).fetchall()
        return [{"agent_id": row[0] or "—", "requests": int(row[1])} for row in rows]

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
                "SELECT entity_type, COUNT(*) FROM events WHERE customer<>? "
                "GROUP BY entity_type",
                (SELFCHECK_ORG,),
            ).fetchall()
            total = self._conn.execute(
                "SELECT COALESCE(SUM(n), 0) FROM requests WHERE customer<>?",
                (SELFCHECK_ORG,),
            ).fetchone()
        entities = {row[0]: row[1] for row in rows}
        # `requests` is the REQUEST counter, not sum(entities). It used to be the
        # latter, which meant the plan limit the customer bought ("до 100 000
        # запросов") was consumed once per detected VALUE — several times faster
        # than the thing they were quoted, and impossible to reconcile against
        # their own gateway's request log.
        return {"requests": int(total[0]) if total else 0, "entities": entities}

    def counts_for_agent(self, customer: str, agent_id: str) -> dict[str, int]:
        """Counts per entity type for a single agent."""
        rows = self._conn.execute(
            "SELECT entity_type, COUNT(*) FROM events WHERE customer=? AND agent_id=? GROUP BY entity_type",
            (customer, agent_id),
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def _event_filter(self, customer: str, since: float, agent_id: str,
                      entity_type: str, token_query: str) -> tuple[str, list[object]]:
        """Shared WHERE for the log screen, so the page and its total can never
        disagree about what is being counted."""
        clauses = ["customer=?", "ts>=?"]
        params: list[object] = [customer, since]
        if agent_id:
            clauses.append("agent_id=?")
            params.append(agent_id)
        if entity_type:
            clauses.append("entity_type=?")
            params.append(entity_type)
        if token_query:
            # instr(), not LIKE: a token search is a substring search, and with
            # LIKE the user's own `%` and `_` would silently become wildcards.
            clauses.append("instr(token, ?) > 0")
            params.append(token_query)
        return " AND ".join(clauses), params

    def search_events(self, customer: str, since: float, agent_id: str,
                      entity_type: str, token_query: str,
                      limit: int, offset: int) -> dict[str, object]:
        """One page of the log plus the total the pagination footer needs."""
        where, params = self._event_filter(
            customer, since, agent_id, entity_type, token_query
        )
        total = self._conn.execute(
            f"SELECT COUNT(*) FROM events WHERE {where}", params
        ).fetchone()
        rows = self._conn.execute(
            f"SELECT ts, agent_id, entity_type, token, preview FROM events "
            f"WHERE {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return {
            "total": int(total[0]) if total else 0,
            "events": [{"ts": r[0], "agent_id": r[1], "type": r[2],
                        "token": r[3], "preview": r[4]} for r in rows],
        }

    def known_orgs(self) -> list[str]:
        """Orgs this container has actually seen traffic for. One container may
        serve several of the customer's own tenants, and the interface has to
        offer what exists rather than make the operator guess an id."""
        rows = self._conn.execute(
            "SELECT DISTINCT customer FROM requests WHERE customer<>? ORDER BY customer",
            (SELFCHECK_ORG,),
        ).fetchall()
        return [row[0] for row in rows]

    def known_agents(self, customer: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT agent_id FROM events WHERE customer=? AND agent_id<>'' "
            "ORDER BY agent_id",
            (customer,),
        ).fetchall()
        return [row[0] for row in rows]

    def known_types(self, customer: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT entity_type FROM events WHERE customer=? ORDER BY entity_type",
            (customer,),
        ).fetchall()
        return [row[0] for row in rows]

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
