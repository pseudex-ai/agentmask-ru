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
import uuid

from pseudex.profiling import stage
from pseudex.sqlite_setup import AUDIT_STORE, connect as sqlite_connect

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
SELFCHECK_ORG = "__pseudex_selfcheck__"


def _preview(value: str) -> str:
    """Masked preview: at most the first and last char, and nothing for a short
    value. The preview rides into /events and /spans, replicated across every
    read, so first-2+last-2 of a short field (a house number, a 4-digit code)
    disclosed most of it — a partial second copy of the data the vault exists to
    contain (pentest B4). Reveal only enough to recognise a row, never enough to
    reconstruct the value."""
    n = len(value)
    if n <= 3:
        return "•" * n
    if n <= 8:
        return value[0] + "•" * (n - 1)
    return value[0] + "•" * (n - 2) + value[-1]


class AuditLog:
    """Connector to the append-only audit store (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path, AUDIT_STORE)
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
        # Detokenization is a disclosure path too: /unmask* returns real values
        # from the vault. Legitimate detok restores tokens just masked in the same
        # conversation; a sweep of guessed tokens (a compromised gateway credential
        # trawling the vault) shows here as volume plus a high MISS rate. We record
        # only counts — never the values — so the trace itself is not a second copy
        # (pentest B1: /unmask* had no trace at all, so a sweep left none).
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS detoks ("
            "ts REAL, customer TEXT, actor TEXT, resolved INTEGER, misses INTEGER)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS events_customer_ts "
                           "ON events (customer, ts DESC)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS reveals_customer_ts "
                           "ON reveals (customer, ts DESC)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS detoks_customer_ts "
                           "ON detoks (customer, ts DESC)")
        self._migrate_agent_id()
        self._conn.commit()

    def installation_id(self) -> str:
        """A stable id for THIS DATA DIRECTORY, minted once and kept beside the
        counters it identifies.

        The licensing server de-duplicates usage reports by instance id, keeping
        the latest cumulative total per instance and SUMMING across instances.
        That is only correct if the id lives exactly as long as the counter it
        reports. It did not: `entrypoint.sh` minted a fresh one from
        /dev/urandom on every container start, while the counters live on the
        mounted volume and survive.

        So every restart opened a NEW row holding the volume's full lifetime
        total, and the server added them up. A customer at 500k requests who
        redeployed once was billed for a million. Restarted daily for a month,
        roughly fifteen times their real usage, growing without bound.

        Gate L12 could not see it because the e2e stand pins the instance id as
        configuration, and nothing in the shipped run command pins it for a
        customer.

        Stored here rather than in a file of its own because this is already the
        thing that shares the counters' lifetime — same volume, same backup,
        same deletion.
        """
        row = self._fetchone("SELECT value FROM meta WHERE key='installation_id'", ())
        if row is not None:
            return str(row[0])
        fresh = uuid.uuid4().hex
        with self._lock:
            # INSERT OR IGNORE, then read back: several worker processes open
            # this database at the same moment on a cold start, and the loser of
            # that race must adopt the winner's id rather than overwrite it.
            self._conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('installation_id', ?)",
                (fresh,),
            )
            self._conn.commit()
        row = self._fetchone("SELECT value FROM meta WHERE key='installation_id'", ())
        return str(row[0]) if row is not None else fresh

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

    def record_detok(self, customer: str, actor: str, resolved: int,
                     misses: int) -> None:
        """One /unmask* call disclosed `resolved` real values and failed to
        resolve `misses` substitutes. Aggregate only (no tokens, no values), so
        the trace is not a second copy of the vault — but a sweep of a compromised
        credential still shows as call volume and a high miss rate (pentest B1)."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO detoks (ts, customer, actor, resolved, misses) "
                "VALUES (?,?,?,?,?)",
                (time.time(), customer, actor, int(resolved), int(misses)),
            )
            self._conn.commit()

    def detok_calls_since(self, customer: str, since: float) -> int:
        """How many /unmask* calls this customer made since `since` — the trace of
        activity (a sweep shows as call volume). NOT what the rate limiter reads:
        one call can resolve many values, so a per-call cap let a batch trawl the
        vault under it (pentest F2). The limiter reads `detok_values_since`."""
        row = self._fetchone(
            "SELECT COUNT(*) FROM detoks WHERE customer=? AND ts>=?",
            (customer, since),
        )
        return int(row[0]) if row else 0

    def detok_values_since(self, customer: str, since: float) -> int:
        """Real VALUES this customer's detok disclosed since `since` — SUM(resolved),
        not COUNT(*). The disclosure bound is the number of values pulled, and a
        single /unmask* call can resolve many (batching evaded a per-call cap,
        pentest F2), so the cross-worker rate limiter reads this. Misses do not
        count — a sweep of guessed tokens discloses nothing, and shows in the trace
        (`detok_calls_since`, `detok_summary` miss_rate) instead."""
        row = self._fetchone(
            "SELECT COALESCE(SUM(resolved),0) FROM detoks WHERE customer=? AND ts>=?",
            (customer, since),
        )
        return int(row[0]) if row else 0

    def detok_summary(self, customer: str, since: float) -> dict:
        """Detok activity since `since` — the OPERATOR-visible half of the B1 trace.
        Counts only, never values.

        A vault sweep shows in TWO shapes, and `miss_rate` alone hid the second
        (pentest WS-7 exfiltrator #2): a TOKEN-guess sweep (guessing our-format
        tokens) fails to resolve and drives `misses`/`miss_rate` up; but a
        NAME/VALUE-guess sweep (feeding words that were never our tokens) resolves
        nothing AND leaves no residual, so `misses`=0 and `miss_rate`=0 while the
        trawl runs. The shape that catches BOTH is UNPRODUCTIVE calls — a call that
        disclosed nothing (`resolved`=0). Legitimate detok resolves values; a sweep
        does not. `unproductive`/`unproductive_rate` is the sweep signal that does
        not hide, whatever the attacker guesses."""
        row = self._fetchone(
            "SELECT COUNT(*), COALESCE(SUM(resolved),0), COALESCE(SUM(misses),0), "
            "COALESCE(SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END),0) "
            "FROM detoks WHERE customer=? AND ts>=?",
            (customer, since),
        )
        calls = int(row[0]) if row else 0
        resolved = int(row[1]) if row else 0
        misses = int(row[2]) if row else 0
        unproductive = int(row[3]) if row else 0
        total = resolved + misses
        return {"calls": calls, "resolved": resolved, "misses": misses,
                "miss_rate": round(misses / total, 3) if total else 0.0,
                "unproductive": unproductive,
                "unproductive_rate": round(unproductive / calls, 3) if calls else 0.0}

    def _fetchall(self, sql: str, params: tuple) -> list[tuple]:
        """Every READ goes through here, under the same lock the writes take.

        `check_same_thread=False` lets several threads share one connection; it
        does not make the connection concurrent. Interleaving a read with
        another thread's INSERT+commit raises `InterfaceError`, or — worse and
        reproducibly — returns a row with COLUMNS MISSING, which surfaces
        upstream as an IndexError on a tuple index rather than as an error
        anyone would recognise as a locking bug.

        Measured before this existed: 4 writer threads and 2 readers over 1.2M
        events failed 7.7% of reads, and the operator's screens rendered
        "движок не отвечает" against a perfectly healthy engine — the single
        diagnosis this interface exists to make trustworthy.

        `Vault` has always done this (see `peek_token`), and `sqlite_setup.py`
        states the rule. The audit read paths were simply never brought along,
        and the polling UI is the first caller that hits them hard enough for
        it to matter.
        """
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _fetchone(self, sql: str, params: tuple) -> tuple | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def reveals(self, customer: str, limit: int, offset: int) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT ts, actor, token, entity_type, found FROM reveals WHERE customer=? "
            "ORDER BY ts DESC LIMIT ? OFFSET ?",
            (customer, limit, offset),
        )
        return [{"ts": r[0], "actor": r[1], "token": r[2], "type": r[3],
                 "found": bool(r[4])} for r in rows]

    def reveals_count(self, customer: str) -> int:
        row = self._fetchone("SELECT COUNT(*) FROM reveals WHERE customer=?", (customer,))
        return int(row[0]) if row else 0

    def request_totals(self, customer: str, since_day: str, agent_id: str) -> int:
        """Requests over a window. `since_day` is a 'YYYY-MM-DD' string compared
        against the stored day buckets; pass "" for all time, explicitly — the
        screens that call this label their numbers with a period, and a method
        that silently means "ever" put lifetime figures under that label."""
        where, params = "customer=? AND day>=?", [customer, since_day]
        if agent_id:
            where += " AND agent_id=?"
            params.append(agent_id)
        row = self._fetchone(
            f"SELECT COALESCE(SUM(n), 0) FROM requests WHERE {where}", params)
        return int(row[0]) if row else 0

    def daily_series(self, customer: str, days: int, agent_id: str) -> list[dict[str, object]]:
        """Requests and protected values per day, oldest first, with empty days
        filled in. A chart that silently omits a zero day compresses the gap and
        reads as steady traffic across an outage.

        BOTH queries are bounded by the window. They were not, and /status calls
        this on a three-second poll: measured at 1.2M events the unbounded scan
        took 0.39 s, so one open browser tab held a worker's event loop ~13% of
        the time — and because the interface keeps one connection alive, always
        the same worker. At ten million events the query outruns the poll and
        that worker's /health starts timing out, which reads to an orchestrator
        as a container to restart.
        """
        now = time.time()
        wanted = [_day(now - (days - 1 - index) * 86400) for index in range(days)]
        since = now - days * 86400
        # THE FILTER REACHES EVERY QUERY OR IT REACHES NONE. An integrator
        # showing a security officer «этот агент за эту неделю» got the whole
        # container's totals instead, because the parameter existed on the
        # endpoint and was dropped before the SQL.
        agent_clause = " AND agent_id=?" if agent_id else ""
        agent_param: list[str] = [agent_id] if agent_id else []
        request_rows = dict(self._fetchall(
            f"SELECT day, SUM(n) FROM requests WHERE customer=? AND day>=?{agent_clause} "
            f"GROUP BY day",
            [customer, wanted[0], *agent_param],
        ))
        # COUNT(DISTINCT token), NOT COUNT(*). The same words — «значений
        # защищено» — were computed two ways in one product: this screen counted
        # OCCURRENCES while the figure reported for billing counts values in the
        # vault. A customer comparing their own two screens saw 19 here and 10 in
        # the cabinet, with no way to reconcile them. A protected value is a
        # person's phone number; the number of times it was sent is what the
        # journal below is for.
        event_rows = dict(self._fetchall(
            f"SELECT DATE(ts, 'unixepoch', 'localtime'), COUNT(DISTINCT token) "
            f"FROM events WHERE customer=? AND ts>=?{agent_clause} GROUP BY 1",
            [customer, since, *agent_param],
        ))
        return [{"day": day,
                 "requests": int(request_rows.get(day, 0)),
                 "values": int(event_rows.get(day, 0))}
                for day in wanted]

    def by_agent(self, customer: str, since_day: str) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT agent_id, SUM(n) FROM requests WHERE customer=? AND day>=? "
            "GROUP BY agent_id ORDER BY 2 DESC",
            (customer, since_day),
        )
        return [{"agent_id": row[0] or "—", "requests": int(row[1])} for row in rows]

    def _migrate_agent_id(self) -> None:
        """Add agent_id to a pre-existing table created before this column."""
        columns = [row[1] for row in self._fetchall("PRAGMA table_info(events)", ())]
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

    def counts(self, customer: str, since: float, agent_id: str) -> dict[str, int]:
        """Counts per entity type over a window.

        `since` is REQUIRED, and that is the fix rather than the inconvenience:
        this returned all-time numbers while the status screen printed them
        under "СЕГОДНЯ" and the printed report put them under a stated period.
        A container up for a month with no traffic today rendered "0 запросов"
        beside "PHONE 5000" in the same cell, and the document handed to the
        customer's auditor claimed lifetime figures were the period's. Pass 0.0
        to mean all time, explicitly."""
        where, params = "customer=? AND ts>=?", [customer, since]
        if agent_id:
            where += " AND agent_id=?"
            params.append(agent_id)
        rows = self._fetchall(
            f"SELECT entity_type, COUNT(*) FROM events WHERE {where} "
            f"GROUP BY entity_type",
            params,
        )
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
        # Called from the LICENCE THREAD on every renewal while mask workers are
        # writing on the same connection, so both reads must be serialised
        # against those writes — which `_fetchall`/`_fetchone` now do. They must
        # NOT be wrapped in another `with self._lock` here: threading.Lock is not
        # reentrant, and doing so deadlocks the renewal thread permanently, which
        # expires the lease and stops the container.
        #
        # The two reads are deliberately not one atomic snapshot. They are
        # counters that only grow, reported cumulatively, so a renewal that
        # catches them a few microseconds apart understates by at most one
        # request and is corrected by the next report.
        rows = self._fetchall(
            "SELECT entity_type, COUNT(*) FROM events WHERE customer<>? "
            "GROUP BY entity_type",
            (SELFCHECK_ORG,),
        )
        total = self._fetchone(
            "SELECT COALESCE(SUM(n), 0) FROM requests WHERE customer<>?",
            (SELFCHECK_ORG,),
        )
        entities = {row[0]: row[1] for row in rows}
        # `requests` is the REQUEST counter, not sum(entities). It used to be the
        # latter, which meant the plan limit the customer bought ("до 100 000
        # запросов") was consumed once per detected VALUE — several times faster
        # than the thing they were quoted, and impossible to reconcile against
        # their own gateway's request log.
        return {"requests": int(total[0]) if total else 0, "entities": entities}

    def counts_for_agent(self, customer: str, agent_id: str) -> dict[str, int]:
        """Counts per entity type for a single agent."""
        rows = self._fetchall(
            "SELECT entity_type, COUNT(*) FROM events WHERE customer=? AND agent_id=? GROUP BY entity_type",
            (customer, agent_id),
        )
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
        total = self._fetchone(
            f"SELECT COUNT(*) FROM events WHERE {where}", params
        )
        rows = self._fetchall(
            f"SELECT ts, agent_id, entity_type, token, preview FROM events "
            f"WHERE {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return {
            "total": int(total[0]) if total else 0,
            "events": [{"ts": r[0], "agent_id": r[1], "type": r[2],
                        "token": r[3], "preview": r[4]} for r in rows],
        }

    def known_orgs(self) -> list[str]:
        """Orgs this container has actually seen traffic for. One container may
        serve several of the customer's own tenants, and the interface has to
        offer what exists rather than make the operator guess an id."""
        rows = self._fetchall(
            "SELECT DISTINCT customer FROM requests WHERE customer<>? ORDER BY customer",
            (SELFCHECK_ORG,),
        )
        return [row[0] for row in rows]

    def known_agents(self, customer: str) -> list[str]:
        rows = self._fetchall(
            "SELECT DISTINCT agent_id FROM events WHERE customer=? AND agent_id<>'' "
            "ORDER BY agent_id",
            (customer,),
        )
        return [row[0] for row in rows]

    def known_types(self, customer: str) -> list[str]:
        rows = self._fetchall(
            "SELECT DISTINCT entity_type FROM events WHERE customer=? ORDER BY entity_type",
            (customer,),
        )
        return [row[0] for row in rows]

    def recent(self, customer: str, limit: int) -> list[dict[str, object]]:
        """Most recent caught items across all of an org's agents."""
        rows = self._fetchall(
            "SELECT ts, agent_id, entity_type, token, preview FROM events WHERE customer=? "
            "ORDER BY ts DESC LIMIT ?",
            (customer, limit),
        )
        return [{"ts": r[0], "agent_id": r[1], "type": r[2], "token": r[3], "preview": r[4]} for r in rows]

    def recent_for_agent(self, customer: str, agent_id: str, limit: int) -> list[dict[str, object]]:
        """Most recent caught items for a single agent (type / token / masked original)."""
        rows = self._fetchall(
            "SELECT ts, entity_type, token, preview FROM events WHERE customer=? AND agent_id=? "
            "ORDER BY ts DESC LIMIT ?",
            (customer, agent_id, limit),
        )
        return [{"ts": r[0], "type": r[1], "token": r[2], "preview": r[3]} for r in rows]
