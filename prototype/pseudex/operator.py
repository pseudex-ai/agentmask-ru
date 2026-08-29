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

from pseudex import sqlite_setup
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
                "processes": processes(),
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
            "lease_ttl_s": state.ttl_seconds,
            "renew_after_s": state.renew_after_seconds,
            "next_renewal_in_s": (None if state.next_renewal_in_seconds is None
                                  else round(state.next_renewal_in_seconds)),
            "lease_id": state.lease_id,
            "bundle_version": state.bundle_version,
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
        return JSONResponse({
            "env": {name: os.environ[name] for name in _SHOWN_ENV if name in os.environ},
            "profile": profiling_snapshot(),
            "processes": processes(),
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
