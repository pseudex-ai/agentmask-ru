"""Read-mostly endpoints for the operator's own local interface.

These answer "what is this container doing", not "mask this text". They are kept
out of `service.py` because they have a different audience, a different risk
profile and a different auth rule: the masking endpoints are called by the
customer's gateway on every request and must stay open on the contour network,
while everything here can disclose personal data or infrastructure detail and is
gated behind an operator token.

WHY THE ENGINE OWNS THEM, not the UI process. The UI is one caller among
several — `curl` against the sidecar port is a supported shape and the way
support asks a customer to collect evidence. If the UI held the reveal log, any
other caller would disclose values leaving no trace, which is precisely the
accountability gap this module exists to close.

Everything here is read-only with one deliberate exception: /reveal writes an
access record BEFORE returning the value.
"""

import os
import re
import time

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from pseudex import metrics as metrics_format
from pseudex import preflight, schema, sqlite_setup
from pseudex.audit import SELFCHECK_ORG
from pseudex.profiling import snapshot as profiling_snapshot

# Config worth showing an operator, and nothing else. An allowlist rather than a
# denylist of secret-looking names: a denylist silently starts leaking the moment
# someone adds a variable whose name does not match the pattern, and the variable
# most worth withholding — PSEUDEX_LICENSE_KEY — is the one that buys our
# service. Values of these are non-secret by construction.
_SHOWN_ENV = (
    "PSEUDEX_WORKERS",
    "PSEUDEX_MASK_CONCURRENCY",
    "PSEUDEX_MASK_CACHE_SIZE",
    "PSEUDEX_DB_DIR",
    # The MODE only — auto/required/off. Not PSEUDEX_VAULT_KEY, obviously, and
    # not _KEY_CMD either: a command line is where an operator puts a token by
    # accident, and /status already names WHICH source answered.
    "PSEUDEX_VAULT_ENCRYPTION",
    "PSEUDEX_PROFILE",
    "PSEUDEX_LOG_LEVEL",
    "PSEUDEX_ADDR_EXTRACTOR",
    "PSEUDEX_LICENSE_URL",
    "PSEUDEX_UI_PORT",
    "PSEUDEX_WORKER_MB",
    "PSEUDEX_HEADROOM_MB",
    "PSEUDEX_MEMORY_LIMIT_MB",
    "TZ",
)

# The self-check message. Hard-coded and obviously synthetic on purpose: the
# check runs through the REAL /mask and /unmask, so whatever it contains is
# minted into the customer's vault and written to their audit. Using the
# operator's own text would put a support action into their production data.
_SELFCHECK_TEXT = (
    "Здравствуйте! Меня зовут Иванов Пётр Сергеевич, "
    "перезвоните на +7 916 214-88-03."
)


def _clock_ticks() -> int:
    try:
        return os.sysconf("SC_CLK_TCK")
    except (ValueError, OSError, AttributeError):
        return 100


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def processes() -> list[dict[str, object]]:
    """Every engine process in this container, with uptime and resident memory.

    Read from /proc rather than tracked in-process, because with SO_REUSEPORT the
    workers are independent processes that never learn about each other — a
    worker can only ever report itself, and "one worker is wedged" is exactly the
    question this list has to answer.

    Returns an empty list off Linux (developer machines), which the UI renders as
    "недоступно" rather than as "no processes".
    """
    if not os.path.isdir("/proc"):
        return []
    ticks = _clock_ticks()
    boot = _read("/proc/uptime").split()
    machine_uptime = float(boot[0]) if boot else 0.0
    found: list[dict[str, object]] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        cmdline = _read(f"/proc/{entry}/cmdline").replace("\0", " ")
        if "pseudex" not in cmdline and "serve_main" not in cmdline:
            continue
        stat = _read(f"/proc/{entry}/stat")
        uptime_seconds = 0.0
        if stat:
            # Field 22 is starttime, but the command name in field 2 may itself
            # contain spaces and parentheses, so the split has to start after the
            # LAST ')' rather than at the beginning of the line.
            tail = stat[stat.rfind(")") + 1:].split()
            if len(tail) >= 20:
                uptime_seconds = max(0.0, machine_uptime - float(tail[19]) / ticks)
        rss_kb = 0
        for line in _read(f"/proc/{entry}/status").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                rss_kb = int(parts[1]) if len(parts) > 1 else 0
                break
        found.append({
            "pid": int(entry),
            "uptime_s": round(uptime_seconds),
            "rss_mb": round(rss_kb / 1024),
        })
    found.sort(key=lambda item: item["pid"])
    # The oldest process is the one the entrypoint started; the rest are its
    # workers. Deriving the role from age rather than asking each process keeps
    # this working identically for the source and the compiled image.
    if found:
        oldest = max(found, key=lambda item: item["uptime_s"])
        for item in found:
            item["role"] = "master" if item is oldest else "worker"
    return found


def memory(snapshot: list[dict[str, object]] | None = None) -> dict[str, object]:
    """What the preflight decided, re-asked against what is actually running.

    THE PREFLIGHT'S ANSWER GOES STALE AND THIS ONE DOES NOT. The budget was
    computed from a measured 350 MB per worker; a customer whose traffic holds
    longer transcripts, or a container whose limit was raised without a restart,
    lives at a different number. So this reports the same arithmetic beside the
    RESIDENT sizes the processes actually have, and the interesting line is where
    the two disagree — that is the container which will be killed later today,
    visible before it is.

    IT DOES NOT CLAIM TO KNOW WHICH PROCESS IS A WORKER, and the first version
    did. `processes()` derives its `role` from AGE — the oldest is the master —
    which is right for the picture it draws and wrong here twice over: the shell
    that fans the workers out is not in the list at all, so the oldest entry is a
    real worker labelled «master», and the interface IS in the list, so filtering
    on `role == "worker"` dropped one worker and counted a 50 MB UI process as
    one. With one worker and the interface on, the «largest worker» was the
    interface and the drift warning could never fire.

    Nothing distinguishes them from outside: the interface is the same binary
    under a different role, so its cmdline is identical. So the honest report is
    the LARGEST process — a worker whenever any worker runs, since the
    interface is an order of magnitude smaller — and it is named that way.

    Takes the snapshot so `/status` does not scan `/proc` twice for one answer:
    two scans are two moments, and `used_mb` describing a different set of
    processes than the count beside it is a small lie that costs nothing to
    avoid.
    """
    limit = preflight.memory_limit_mb()
    found = processes() if snapshot is None else snapshot
    used_mb = sum(int(item.get("rss_mb", 0)) for item in found)
    # The same arithmetic the preflight ran, asked the same way: from the
    # environment and the affinity, never from the process list — a container
    # whose workers are being killed one by one would otherwise report a
    # shrinking budget as though that were the plan.
    plan = preflight.plan(limit, preflight.cpus_available())
    return {
        "limit_mb": limit,
        "used_mb": used_mb,
        "processes_running": len(found),
        "worker_mb_budget": plan["worker_mb"],
        "largest_process_mb": max((int(item.get("rss_mb", 0)) for item in found),
                                  default=0),
        "headroom_mb": (limit - used_mb) if limit is not None else None,
        "verdict": plan["verdict"],
        "reason": plan["reason"],
    }


def release_verdict(state) -> dict[str, object]:
    """What the licensing server said about THIS version at the last lease
    (D-055), for the operator's screen and `pseudexctl doctor`. `None` fields
    mean the server said nothing — no registry yet, or a server older than the
    engine — and the interface must render that as unknown, not as current.
    Dates are unix seconds; the interface formats them."""
    return {
        "version": state.engine_version,
        "running_latest": state.running_latest,
        "latest": state.latest,
        "latest_in_cycle": state.latest_in_cycle,
        "min_supported": state.min_supported,
        "deprecated_at": (None if state.deprecated_at is None
                          else int(state.deprecated_at)),
        "sunset_at": None if state.sunset_at is None else int(state.sunset_at),
        "notice": state.notice,
        "cycles": state.cycles,
        # The one command every verdict ends in. Named here so the interface
        # and the CLI print the same words as the server's own 426.
        "upgrade": (None if state.latest is None
                    else f"pseudexctl upgrade --to {'.'.join(state.latest.split('.')[:2])}"),
    }


def _period_start(period: str) -> float:
    """Start of a named period. Unknown values collapse to 14 days rather than
    raising: this comes off a query string, and a typo should narrow nothing."""
    days = {"today": 1, "7d": 7, "14d": 14, "30d": 30, "all": 0}.get(period, 14)
    if days == 0:
        return 0.0
    if days == 1:
        local = time.localtime()
        return time.mktime((local.tm_year, local.tm_mon, local.tm_mday,
                            0, 0, 0, 0, 0, -1))
    return time.time() - days * 86400


def build_router(audit, license_client, assets, detector_version: str,
                 selfcheck_runner) -> APIRouter:
    """Wire the router to the process singletons.

    Passed in rather than imported so this module stays free of `service.py` —
    the two would otherwise import each other, and a router that reaches back
    into the app it is mounted on cannot be exercised on its own.

    The router is created HERE rather than at module scope: a shared global
    would accumulate a second copy of every route if this were ever called
    twice, and duplicate routes fail by shadowing rather than by raising.
    """
    router = APIRouter()

    @router.get("/status")
    async def status(request: Request) -> JSONResponse:
        org_id = request.query_params.get("org_id", "default")
        state = license_client.status()
        # ONE SCAN OF /proc for both the process list and the memory report:
        # they are drawn side by side on one screen, and two scans would be two
        # different moments rendered as one.
        running = processes()
        series = await anyio.to_thread.run_sync(audit.daily_series, org_id, 1, "")
        today = series[0] if series else {"requests": 0, "values": 0}
        # The breakdown beside "СЕГОДНЯ" must cover the same day the numbers
        # above it do. It was all-time, so a quiet day rendered "0 запросов"
        # next to "PHONE 5000".
        by_type = await anyio.to_thread.run_sync(
            audit.counts, org_id, _period_start("today"), ""
        )
        return JSONResponse({
            "engine": {
                "version": detector_version,
                "assets_loaded": assets.is_loaded,
                "bundle_version": state.bundle_version,
                "release": release_verdict(state),
                # THE SCHEMA CONTRACT, BOTH SIDES (D-060): what this image
                # understands per store and what the volume was found at by
                # this process (None for a store it has not opened). The
                # two numbers are what `pseudexctl upgrade` reads before it
                # promises a rollback.
                "schema": {"binary": schema.versions(), "volume": schema.running()},
                "processes": running,
                # HERE AND NOT ONLY IN /diagnostics. The preflight refuses at
                # START; this is the same arithmetic asked of a container that
                # already started and has since drifted — a raised limit nobody
                # restarted for, or traffic heavier than the 350 MB the budget
                # was measured on. The operator's screen is where that is worth
                # seeing, and /diagnostics is the screen they open after the
                # trouble rather than before it.
                "memory": memory(running),
            },
            "license": {
                "state": state.state,
                "code": state.code,
                "grace_left_s": (None if state.grace_left_seconds is None
                                 else round(state.grace_left_seconds)),
                "seconds_since_lease": (None if state.seconds_since_lease is None
                                        else round(state.seconds_since_lease)),
                "last_error": state.last_error,
            },
            # Where the key comes from, never the key — plus what is ON DISK,
            # file by file. The operator's questions are whether the volume they
            # back up carries its own key (`key_beside_data`, answered without
            # them reading a log line from a start they were not present for)
            # and whether it is actually encrypted. The second used to be
            # answered from the CONFIGURATION, so a volume whose files had not
            # been migrated yet rendered as encrypted on the one screen that
            # exists to say otherwise.
            "vault": sqlite_setup.volume_state(
                os.environ.get("PSEUDEX_DB_DIR", ".")),
            "today": {
                "requests": today["requests"],
                "values": today["values"],
                "by_type": by_type,
            },
        })

    @router.get("/orgs")
    async def orgs() -> JSONResponse:
        return JSONResponse({"orgs": await anyio.to_thread.run_sync(audit.known_orgs)})

    @router.get("/events")
    async def events(request: Request) -> JSONResponse:
        params = request.query_params
        org_id = params.get("org_id", "default")
        try:
            limit = min(200, max(1, int(params.get("limit", "50"))))
            offset = max(0, int(params.get("offset", "0")))
        except ValueError:
            return JSONResponse({"error": "limit and offset must be integers"},
                                status_code=400)
        page = await anyio.to_thread.run_sync(
            audit.search_events, org_id,
            _period_start(params.get("period", "14d")),
            params.get("agent_id", ""), params.get("type", ""),
            params.get("q", ""), limit, offset,
        )
        page["agents"] = await anyio.to_thread.run_sync(audit.known_agents, org_id)
        page["types"] = await anyio.to_thread.run_sync(audit.known_types, org_id)
        return JSONResponse(page)

    @router.get("/stats")
    async def stats(request: Request) -> JSONResponse:
        org_id = request.query_params.get("org_id", "default")
        # The journal already filtered by agent and these did not, so «этот агент
        # за эту неделю» answered with the whole container.
        agent_id = request.query_params.get("agent_id", "")
        try:
            days = min(90, max(1, int(request.query_params.get("days", "14"))))
        except ValueError:
            return JSONResponse({"error": "days must be an integer"}, status_code=400)
        # Every figure here is scoped to the window the caller asked for. They
        # were not: the screen said "период последние N дней" over all-time
        # numbers, and the printed report carried that claim to an auditor.
        since = time.time() - days * 86400
        since_day = time.strftime("%Y-%m-%d", time.localtime(since))
        return JSONResponse({
            "org_id": org_id,
            "days": await anyio.to_thread.run_sync(audit.daily_series, org_id, days, agent_id),
            "by_type": await anyio.to_thread.run_sync(audit.counts, org_id, since, agent_id),
            "by_agent": await anyio.to_thread.run_sync(audit.by_agent, org_id, since_day),
            "requests_total": await anyio.to_thread.run_sync(
                audit.request_totals, org_id, since_day, agent_id),
        })

    @router.get("/stats.csv")
    async def stats_csv(request: Request) -> PlainTextResponse:
        """The period report, as a file the operator can hand to their own
        auditor. Counts only — no tokens, no previews, no values — so exporting
        it never turns a report into a second copy of the personal data."""
        org_id = request.query_params.get("org_id", "default")
        agent_id = request.query_params.get("agent_id", "")
        try:
            days = min(365, max(1, int(request.query_params.get("days", "14"))))
        except ValueError:
            return PlainTextResponse("days must be an integer", status_code=400)
        lines = ["day,requests,protected_values"]
        for row in await anyio.to_thread.run_sync(audit.daily_series, org_id, days, agent_id):
            lines.append(f'{row["day"]},{row["requests"]},{row["values"]}')
        return PlainTextResponse(
            "\n".join(lines) + "\n",
            # The org id reaches this header from a query string, and a quote in
            # it splits the filename parameter. Restricted to characters that
            # cannot mean anything to the header parser.
            headers={"Content-Disposition":
                     'attachment; filename="pseudex-'
                     + re.sub(r"[^A-Za-z0-9_.-]", "_", org_id)
                     + f'-{days}d.csv"'},
        )

    @router.get("/metrics")
    async def prometheus(request: Request) -> PlainTextResponse:
        """Everything /status shows, in the format a scraper reads.

        WHY IT IS ON THE OPERATOR TOKEN AND NOT OPEN. Every other product puts
        /metrics behind no auth because metrics are «just numbers»; here the
        numbers say how many people this customer protected today and in which
        categories, which is a description of their business and, at a small
        enough scale, of their traffic. It is also a live inventory of a
        container holding personal data. The whole of `operator.py` is behind
        one token for that reason and this endpoint has no claim to be the
        exception — Prometheus carries a bearer token (`authorization` in the
        scrape config) and that is the whole integration.

        NO VALUES AND NO TOKENS, ONLY COUNTS — the same rule the audit log
        lives by, and here it is also a cardinality rule: a label whose values
        come from traffic would give Prometheus a new time series per person.
        The entity TYPE is a closed set of nine, so it is safe as a label; an
        org id is not, and the container knows only its own anyway.

        A SCRAPE MUST NOT MINT ANYTHING OR WRITE AUDIT, exactly like `/spans`
        and `peek_token`: it runs every fifteen seconds for ever, and a
        diagnostic that changes what it measures is not one. Everything below
        is a read.
        """
        org_id = request.query_params.get("org_id", os.environ.get("PSEUDEX_UI_ORG", "default"))
        state = license_client.status()
        running = processes()
        mem = memory(running)
        today = await anyio.to_thread.run_sync(
            audit.counts, org_id, _period_start("today"), "")
        series = await anyio.to_thread.run_sync(audit.daily_series, org_id, 1, "")
        volume = sqlite_setup.volume_state(os.environ.get("PSEUDEX_DB_DIR", "."))

        out = [
            # THE LADDER AS FOUR SERIES, NOT ONE NUMBER. An enum encoded as
            # 0/1/2/3 forces every alert and every panel to carry the mapping,
            # and the mapping is exactly what changes: `STATE_LEASED` is the
            # string "active", which has already cost this product a /license
            # endpoint that answered 503 for the life of every healthy
            # container. One series per state, valued 0 or 1, needs no legend.
            metrics_format.series(
                "pseudex_license_state",
                {name: int(state.state == name)
                 for name in ("boot", "active", "stale", "expired")},
                "1 for the state the licence is in, 0 for the others", "state"),
            metrics_format.render(
                "pseudex_license_seconds_since_lease",
                None if state.seconds_since_lease is None else round(state.seconds_since_lease),
                "Seconds since the last successful lease"),
            metrics_format.render(
                "pseudex_license_grace_seconds_left",
                None if state.grace_left_seconds is None else round(state.grace_left_seconds),
                "Seconds of grace remaining; absent while the lease is healthy"),
            metrics_format.render(
                "pseudex_assets_loaded", int(assets.is_loaded),
                "1 when the detection bundle is in memory; 0 means /mask answers 503"),
            metrics_format.render(
                "pseudex_processes", len(running),
                "Engine processes of this container, the interface included"),
            metrics_format.render(
                "pseudex_memory_used_bytes", mem["used_mb"] * 1024 * 1024,
                "Resident memory of those processes"),
            metrics_format.render(
                "pseudex_memory_limit_bytes",
                None if mem["limit_mb"] is None else mem["limit_mb"] * 1024 * 1024,
                "The container's memory limit; absent when it has none"),
            metrics_format.render(
                "pseudex_memory_largest_process_bytes",
                mem["largest_process_mb"] * 1024 * 1024,
                "The biggest single process — the one the OOM killer would take"),
            metrics_format.render(
                "pseudex_memory_worker_budget_bytes",
                mem["worker_mb_budget"] * 1024 * 1024,
                "What the preflight budgeted per worker; compare with the largest process"),
            metrics_format.render(
                "pseudex_requests_today", int(series[0]["requests"]) if series else 0,
                "Requests protected today — the BILLED quantity, not sum(values)",
                "gauge"),
            metrics_format.series(
                "pseudex_values_today", {k: int(v) for k, v in today.items()},
                "Personal values protected today, by type", "type"),
            # FOUR STATES, NOT A BOOLEAN, for the same reason the licence
            # ladder is four series: `== ENCRYPTED` collapsed «a correctly
            # configured volume nobody has written to yet» (EMPTY) and «half the
            # stores are still plain text» (MIXED) into the same zero, and those
            # two need opposite responses — wait, versus stop and look now.
            metrics_format.series(
                "pseudex_vault_state",
                {name: int(volume.get("on_disk") == name)
                 for name in (sqlite_setup.ENCRYPTED, sqlite_setup.PLAINTEXT,
                              sqlite_setup.MIXED, sqlite_setup.EMPTY)},
                "1 for what is ON DISK, 0 for the others: encrypted, plaintext, "
                "mixed (a migration stopped half way), empty (nothing written yet)",
                "state"),
        ]
        return PlainTextResponse("".join(out),
                                 media_type="text/plain; version=0.0.4; charset=utf-8")

    @router.get("/reveals")
    async def reveals(request: Request) -> JSONResponse:
        """The access log: who revealed which token and when. Never the value."""
        org_id = request.query_params.get("org_id", "default")
        try:
            limit = min(200, max(1, int(request.query_params.get("limit", "50"))))
            offset = max(0, int(request.query_params.get("offset", "0")))
        except ValueError:
            return JSONResponse({"error": "limit and offset must be integers"},
                                status_code=400)
        return JSONResponse({
            "total": await anyio.to_thread.run_sync(audit.reveals_count, org_id),
            "reveals": await anyio.to_thread.run_sync(
                audit.reveals, org_id, limit, offset),
        })

    @router.get("/detoks")
    async def detoks(request: Request) -> JSONResponse:
        """Detok activity (counts only, never values): call volume and miss rate.
        /unmask* returns real vault values, so a compromised gateway credential can
        trawl the vault — that shows here as a spike in `calls` and a high
        `miss_rate` (guessed tokens don't resolve). The operator-visible half of the
        detok audit; the rate limiter reads the same table."""
        org_id = request.query_params.get("org_id", "default")
        now = time.time()
        return JSONResponse({
            "last_minute": await anyio.to_thread.run_sync(audit.detok_summary, org_id, now - 60),
            "last_hour": await anyio.to_thread.run_sync(audit.detok_summary, org_id, now - 3600),
            "last_day": await anyio.to_thread.run_sync(audit.detok_summary, org_id, now - 86400),
        })

    @router.get("/subscription")
    async def subscription(request: Request) -> JSONResponse:
        """The licence, mirrored locally, so "почему встало" is answerable inside
        the customer's own contour without asking us."""
        org_id = request.query_params.get("org_id", "default")
        state = license_client.status()
        return JSONResponse({
            "state": state.state,
            "code": state.code,
            "plan": state.plan,
            # Ёмкость на экране подписки: до этого оператор не мог узнать, что
            # именно кончилось — время аренды или оплаченный объём.
            "consumed": state.consumed,
            "granted": state.granted,
            "capacity_left": state.capacity_left,
            "lease_ttl_s": state.ttl_seconds,
            "renew_after_s": state.renew_after_seconds,
            "next_renewal_in_s": (None if state.next_renewal_in_seconds is None
                                  else round(state.next_renewal_in_seconds)),
            "lease_id": state.lease_id,
            "bundle_version": state.bundle_version,
            "release": release_verdict(state),
            "seconds_since_lease": (None if state.seconds_since_lease is None
                                    else round(state.seconds_since_lease)),
            "grace_left_s": (None if state.grace_left_seconds is None
                             else round(state.grace_left_seconds)),
            "last_error": state.last_error,
            "errors": license_client.recent_errors(),
            "last_report": license_client.last_report(),
            "requests_total": await anyio.to_thread.run_sync(
                audit.request_totals, org_id, "", ""),
        })

    @router.get("/diagnostics")
    async def diagnostics(request: Request) -> JSONResponse:
        diagnostics_processes = processes()
        return JSONResponse({
            "env": {name: os.environ[name] for name in _SHOWN_ENV if name in os.environ},
            "profile": profiling_snapshot(),
            "processes": diagnostics_processes,
            "memory": memory(diagnostics_processes),
            "lease_errors": license_client.recent_errors(),
        })

    @router.post("/selfcheck")
    async def selfcheck() -> JSONResponse:
        """Prove the round trip on a canned message: real /mask, real /unmask.

        The one screen a customer is asked to look at before contacting support,
        so it must exercise the actual path rather than assert about it. It runs
        under its own org so the synthetic values never mix into the customer's
        vault or their counters.
        """
        started = time.monotonic()
        result = await selfcheck_runner(SELFCHECK_ORG, _SELFCHECK_TEXT)
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        return JSONResponse(result)

    return router
