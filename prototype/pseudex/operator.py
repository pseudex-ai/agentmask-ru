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
from pseudex.profiling import PERCENTILES, snapshot as profiling_snapshot

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

# THE IDENTITY-INVARIANT PROBE (D-081), MIRRORED HERE FOR THE INTERFACE.
#
# WHAT IT ANSWERS. One identity written several ways — «4512 345678» and
# «4512345678», «Иванов Пётр Сергеевич» and «Иванов П. С.», «улица Лермонтова
# дом 38 квартира 7» and «ул. Лермонтова 38 кв 42» — must mint ONE substitute.
# The interface's statistics screen prints that per type, so an operator can see
# a canonicalisation regression on the same page as the counters it moves.
#
# WHY THE FORMS ARE COPIED AND NOT IMPORTED. `pseudex/` may never import from
# `bench/` — bench does not ship (Dockerfile.nuitka's COPY set), so an import
# would be an ImportError in the release image, on the one screen an operator
# opens when something is wrong. The metric
# (`bench/identity_invariant.py`) is the source of truth and compares this exact
# list on every run: it prints `UI-зеркало … agrees` or `DRIFT` and names the
# group that moved, so a mirror cannot diverge quietly.
#
# THE FORMS ARE FULLY SYNTHETIC — invented numbers, a fictional person, a street
# nobody lives on — so they carry no personal data and are safe to keep in RAM
# and in the shipped binary. Only COUNTS leave /stats; no form, no canonical and
# no token is ever returned.
#
# (entity_type, expect, (form, ...)) — `collapse` = all forms must mint ONE fake;
# `differ` = all forms must mint DIFFERENT fakes (the negative control).
IDENTITY_PROBE = (
    ("NAME", "collapse", ("Иванов Пётр", "Иванову Петру", "Иванова Петра",
                          "Пётр Иванов")),
    ("NAME", "differ", ("Иванов Пётр", "Иванов Николай")),
    ("NAME", "collapse", ("Иванов Пётр Сергеевич", "Иванов Пётр",
                          "Иванов П. С.")),
    ("LOC", "collapse", ("улица Лермонтова, дом 38, квартира 7",
                         "ул. Лермонтова 38 кв 7",
                         "улица лермонтова дом 38 квартира 7")),
    ("LOC", "collapse", ("улица лермонтова дом тридцать восемь квартира семь",
                         "улица Лермонтова дом 38 квартира 7")),
    ("LOC", "collapse", ("улица Лермонтова дом 38 квартира 7",
                         "улица Лермонтова дом 38 квартира 42")),
    ("LOC", "collapse", ("улица Лермонтова дом 38 подъезд 1 квартира 7",
                         "улица Лермонтова дом 38 подъезд 3 квартира 7")),
    ("PHONE", "collapse", ("+7 916 402-11-87", "8 916 402-11-87",
                           "89164021187")),
    ("EMAIL", "collapse", ("Ivanov@Example.RU", " ivanov@example.ru ")),
    ("EMAIL", "differ", ("ivanov@example.ru", "petrov@example.ru")),
    ("PASSPORT", "collapse", ("4512 345678", "4512345678")),
    ("PASSPORT", "differ", ("4512 345678", "4512 345679")),
    ("SNILS", "collapse", ("123-456-789 01", "12345678901")),
    ("SNILS", "differ", ("123-456-789 01", "123-456-789 02")),
    ("INN", "collapse", ("7712345678", "77 12345678")),
    ("INN", "differ", ("7712345678", "7712345679")),
    ("CARD", "collapse", ("4276 1234 5678 9012", "4276123456789012")),
    ("CARD", "differ", ("4276 1234 5678 9012", "4276 1234 5678 9013")),
    ("OGRN", "collapse", ("1027700132195", "1 0277 00132195")),
    ("OGRN", "differ", ("1027700132195", "1027700132196")),
    ("OGRNIP", "collapse", ("304500000012345", "3045000000 12345")),
    ("OGRNIP", "differ", ("304500000012345", "304500000012346")),
    # DATE is a NON-ITEM date (`item_type=False`): its substitute mirrors the
    # customer's notation by design, so the three writings are three rows — the
    # control asserts that shape rather than the invariant. The identity-bearing
    # date is DOB, and the same three forms collapse there.
    ("DATE", "differ", ("21.01.1979", "21/01/1979", "1979-01-21")),
    ("DOB", "collapse", ("21.01.1979", "21/01/1979", "1979-01-21")),
    ("DOB", "differ", ("21.01.1979", "22.01.1979")),
    ("OMS_ENP", "collapse", ("1234567890123456", "1234 5678 9012 3456")),
    ("OMS_ENP", "differ", ("1234567890123456", "1234567890123457")),
    ("IBAN", "collapse", ("RU0204452560040702810412345678901",
                          "ru02 0445 2560 0407 0281 0412 3456 78901")),
    ("IBAN", "differ", ("RU0204452560040702810412345678901",
                        "RU0204452560040702810412345678902")),
    ("VIN", "collapse", ("XTA210990Y2765499", "xta 210990 y2765499")),
    ("VIN", "differ", ("XTA210990Y2765499", "XTA210990Y2765498")),
    ("PTS_NUMBER", "collapse", ("78 УВ 123456", "78УВ123456", "78 YB 123456")),
    ("PTS_NUMBER", "differ", ("78 УВ 123456", "78 УВ 123457")),
)

# Computed once per process: the invariant is a property of this build's
# canonicalisation, not of any traffic, so a 5-second poll must not re-run it.
# `None` means "not computed yet"; the dict is replaced atomically under the
# GIL, and two workers racing to compute it compute the same value.
_IDENTITY_RESULT: dict[str, object] | None = None


def _identity_of(entity_type: str, value: str) -> str:
    """The identity key of ONE real writing — no vault, nothing minted.

    `canonicalize` is the row key, and on a fresh vault equal row key means
    equal substitute. NAME is the one exception the metric documents: D-081
    renders one substitute at the named granularity, so «Иванов Пётр Сергеевич»
    and «Иванов П. С.» canonicalise to different STRINGS that are the same
    person. The fold is surname + given-name initial, exactly what
    `bench/identity_invariant.py::fake_identity` applies to substitutes; the
    metric's UI-mirror check compares the two group lists, and both
    implementations are probed against each other on every metric run.
    """
    from pseudex import morph_names, ru_pii_v6
    from pseudex.vault import canonicalize
    canonical = canonicalize(entity_type, value)
    if ru_pii_v6.engine_label(entity_type) != "NAME":
        return canonical
    words = canonical.split()
    shape = morph_names.name_shape(canonical)
    if len(shape) != len(words):
        return canonical
    surname = [w for w, kind in zip(words, shape) if kind == "surn"]
    given = [w for w, kind in zip(words, shape) if kind in ("name", "init")]
    if surname and given:
        return f"{surname[0].casefold()}|{given[0].strip('.').casefold()[:1]}"
    return canonical


def identity_stability() -> dict[str, object]:
    """Per-type identity stability for the statistics screen — COUNTS ONLY.

    Never a form, a canonical or a token: this crosses /stats, which the
    interface polls, and a value there would be personal data on an operator
    screen. The type vocabulary is the closed set the screen already prints.

    A failure (an unleased bundle, a store that will not open) is reported as
    `available: False` with a short reason rather than raised: /stats must keep
    answering while the licence is degraded, and a statistical screen that goes
    dark exactly when the container is in trouble is the wrong instrument.
    """
    global _IDENTITY_RESULT
    if _IDENTITY_RESULT is not None:
        return _IDENTITY_RESULT
    result: dict[str, object] = {
        "available": False, "error": "", "scope": "row key (canonicalize)",
        "by_type": {}, "collapse_groups": 0, "collapse_stable": 0,
        "differ_groups": 0, "differ_ok": 0, "types_with_groups": 0,
        "types_stable": 0, "rate": 0.0,
    }
    try:
        by_type: dict[str, dict[str, int]] = {}
        for entity_type, expect, forms in IDENTITY_PROBE:
            keys = {_identity_of(entity_type, form) for form in forms}
            row = by_type.setdefault(entity_type, {
                "collapse_groups": 0, "collapse_stable": 0,
                "differ_groups": 0, "differ_ok": 0})
            if expect == "collapse":
                row["collapse_groups"] += 1
                row["collapse_stable"] += 1 if len(keys) == 1 else 0
            else:
                row["differ_groups"] += 1
                row["differ_ok"] += 1 if len(keys) == len(forms) else 0
        groups = sum(r["collapse_groups"] for r in by_type.values())
        stable = sum(r["collapse_stable"] for r in by_type.values())
        result.update({
            "available": True,
            "by_type": by_type,
            "collapse_groups": groups,
            "collapse_stable": stable,
            "differ_groups": sum(r["differ_groups"] for r in by_type.values()),
            "differ_ok": sum(r["differ_ok"] for r in by_type.values()),
            "types_with_groups": sum(1 for r in by_type.values()
                                     if r["collapse_groups"]),
            "types_stable": sum(1 for r in by_type.values()
                                if r["collapse_groups"]
                                and r["collapse_stable"] == r["collapse_groups"]),
            "rate": stable / groups if groups else 0.0,
        })
    except Exception as exc:  # noqa: BLE001 — /stats must answer regardless
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    _IDENTITY_RESULT = result
    return result


# THE LATENCY READOUT — the cost the ENGINE adds, by phase.
#
# WHY IT EXISTS. «Движок тормозит агента» is the one complaint about a gateway
# that cannot be answered from the audit journal: every row there counts a
# value, and a value has no duration. profiling.py already measures each phase
# into a bounded ring buffer (PSEUDEX_PROFILE=1); this block is the operator's
# view of it, so the number comes from the process that actually paid it rather
# than from a benchmark run somewhere else.
#
# WHICH MEASURED STAGE EACH ROW IS, named explicitly, and HOW THE STAGES NEST —
# a row called «detect» that silently meant one sub-stage would be worse than no
# row at all, and so would a «total» that added phases which contain each other:
#   normalize -> `detect.normalize`  one Layer-0 fold        (inside detect.total)
#   detect    -> `detect.total`      the whole detect pass   (inside mask.one)
#   mask      -> `mask.one`          masking ONE TEXT — a message content or a
#                                    whole tool-arguments JSON — including the
#                                    detection pass that text runs (`_mask_one`
#                                    calls `detector.detect` inside its own
#                                    `_compute`), plus mint/audit and splice
#   unmask    -> `unmask.total`      one restore call
# `nested_in` carries that containment to the screen, so the operator can see
# that the normalize and detect rows are INSIDE the mask row rather than beside
# it. (The `detect.*` counters also collect detection runs that happen WITHOUT
# masking — the interface's own `/spans` highlighting, `/selfcheck` — so they
# describe all detection in this worker, which is why the mask row, not the
# detect row, is the one the cumulative masking figure is taken from.)
#
# TWO CONSEQUENCES, BOTH LOAD-BEARING:
#   * the `total` row sums only stages that CANNOT overlap — `mask.one` and
#     `unmask.total`, the two legs a caller waits on — never `detect.total`,
#     which is already inside `mask.one`. It is still marked `derived: true`
#     with its `sources`, because it adds per-phase percentiles and quantiles do
#     not add: a planning figure, not the percentile of one operation.
#   * `total_mask_ms` is the cumulative total of ONE enclosing stage
#     (`mask.one`), never a prefix sum over `mask.*`: `mask.tokenize_and_audit`
#     and `mask.splice` run inside `mask.one`, so summing the prefix would count
#     them twice — the same overlap `profile_deep.py` warns about for `detect.*`.
#
# WHY p90 IS NOT DECORATION: a gateway is sized on the near-tail, and p95/p99
# alone hide the shoulder that most slow requests actually sit on. p50 is the
# number that never hurts. p90 is the one an operator can act on.
#
# NEVER PII. A stage name is ours, a duration is a float, a count is an integer:
# nothing here can carry a token or a value, which is what lets it ride the
# endpoint the interface already polls. When PSEUDEX_PROFILE is off every group
# is `null` — never a zero that reads as «instant» — so the screen can print «—»
# and the operator learns the feature needs enabling instead of believing a
# fabricated number.
_LATENCY_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("normalize", "detect.normalize", "detect.total"),
    ("detect", "detect.total", "mask.one"),
    ("mask", "mask.one", ""),
    ("unmask", "unmask.total", ""),
)
# The legs a caller waits on. Disjoint by construction: masking a request and
# restoring a response are different endpoints, and neither contains the other.
_LATENCY_TOTAL_SOURCES: tuple[str, ...] = ("mask.one", "unmask.total")
# The enclosing mask stage, for the cumulative figure. See the overlap note above.
_LATENCY_MASK_TOTAL_STAGE = "mask.one"
_PERCENTILE_KEYS: tuple[str, ...] = tuple(f"{label}_ms" for label, _ in PERCENTILES)


def latency_snapshot() -> dict[str, object]:
    """Per-phase latency for /stats — durations and counts only, never a value.

    Read-only and lock-scoped: `profiling_snapshot()` takes the profiler's lock
    only to freeze the sample deques, so this endpoint stays cheap enough for the
    5-second poll the stats screen runs.
    """
    profile = profiling_snapshot()
    stages = profile.get("stages") or {}
    groups: dict[str, object] = {}
    for label, stage_name, nested_in in _LATENCY_GROUPS:
        row = stages.get(stage_name)
        if row:
            groups[label] = {"stage": stage_name, "nested_in": nested_in or None, **row}
        else:
            groups[label] = None
    present = [name for name in _LATENCY_TOTAL_SOURCES if name in stages]
    total: dict[str, object] | None = None
    if present:
        total = {"derived": True, "sources": present, "nested_in": None}
        for key in _PERCENTILE_KEYS:
            total[key] = round(sum(stages[name][key] for name in present), 4)
        # The cumulative column IS exact: summing disjoint phase totals is the
        # total time spent in those phases. Only the percentile columns are the
        # planning approximation the `derived` flag announces.
        total["total_ms"] = round(sum(stages[name]["total_ms"] for name in present), 3)
    mask_total_ms = round(
        (stages.get(_LATENCY_MASK_TOTAL_STAGE) or {}).get("total_ms", 0.0), 3)
    return {
        "enabled": bool(profile.get("enabled")),
        "percentiles": list(_PERCENTILE_KEYS),
        "groups": groups,
        "total": total,
        "total_mask_ms": mask_total_ms,
        "stages": stages,
    }


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
        # THE OVER-MASKING GUARD, BESIDE THE MASK COUNTS. `by_type` above is read
        # from the audit journal over the requested window; this one is counted
        # in the detector, because a DENIED span writes no row at all (see
        # `metrics.TypeCounter`). The two therefore do NOT share a denominator,
        # and the response says so: `suppressed_since` is when this worker first
        # denied a span, so the interface can print «в этом процессе с …» instead
        # of implying the numbers cover the same period.
        #
        # COUNTS ONLY, like every other figure here: no token, no preview, no
        # value crosses this endpoint, and a type name is a closed vocabulary.
        suppressed = metrics_format.suppressed_snapshot()
        # THE IDENTITY READOUT, BESIDE THE COUNTS IT QUALIFIES. `by_type` says
        # how many values were protected; this says whether the SAME identity
        # written two ways was protected ONCE. A regression here is invisible in
        # the counts (they grow either way) and visible at a glance here. It is
        # the build's own canonicalisation, so it is computed once and cached;
        # the offload keeps the first poll off the event loop (canonicalisation
        # runs morphology, and this endpoint also serves /health's neighbours).
        # COUNTS ONLY — see `identity_stability`.
        identity = await anyio.to_thread.run_sync(identity_stability)
        # THE ENGINE'S OWN COST, BESIDE THE COUNTS IT EXPLAINS. «Защищено
        # значений» says how much was protected and nothing about what that cost
        # the agent waiting on the gateway; this block is that answer, measured in
        # this worker. It does NOT share the period above: the percentiles come
        # from a bounded ring buffer of RECENT samples (and `count`/`total_ms` are
        # process-lifetime), which is why the screen gives it its own caption
        # instead of filing it under «за N дней».
        #
        # Counts and durations only: a stage name is ours, a float carries no
        # token. `latency.enabled` is False (and every group null) unless the
        # container runs with PSEUDEX_PROFILE=1, and the screen prints «—» rather
        # than a zero: an unconfigured profiler must not read as «instant».
        #
        # OFF THE LOOP, like the identity probe: the snapshot sorts the retained
        # window per stage, and this endpoint is polled every 5 s by a screen
        # that must not make /health late.
        latency = await anyio.to_thread.run_sync(latency_snapshot)
        return JSONResponse({
            "org_id": org_id,
            "days": await anyio.to_thread.run_sync(audit.daily_series, org_id, days, agent_id),
            "by_type": await anyio.to_thread.run_sync(audit.counts, org_id, since, agent_id),
            "by_agent": await anyio.to_thread.run_sync(audit.by_agent, org_id, since_day),
            "requests_total": await anyio.to_thread.run_sync(
                audit.request_totals, org_id, since_day, agent_id),
            "suppressed_by_type": suppressed["by_type"],
            "suppressed_total": suppressed["total"],
            "suppressed_since": suppressed["since"],
            "identity": identity,
            "latency": latency,
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
        # The over-masking guard on the same scrape as the mask counts. It is a
        # COUNTER, not a gauge: it only rises for the life of the process, which
        # is exactly what Prometheus's `rate()`/`increase()` are defined over.
        # A label is safe here for the reason entity types are: the vocabulary is
        # closed (10 v5 + the v6 registry + CVC/OTP), never a customer value.
        suppressed = metrics_format.suppressed_snapshot()

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
            # THE OTHER HALF OF THE TYPE PICTURE, and the reason it is a separate
            # metric rather than a subtraction: `pseudex_values_today` counts spans
            # that WERE masked; this counts near-masks the deny layer deliberately
            # LEFT ALONE (an order number that looks like a phone, a version string
            # that looks like an IP). One rising while the other falls is the
            # over-masking guard moving, and no single series shows that.
            #
            # Process-lifetime, this worker: a scrape of N workers sees the share
            # of the worker Prometheus happened to reach, the same property
            # `pseudex_requests_today` has and the same reason the interface prints
            # «в этом процессе». The `since` gauge carries the window with it, so a
            # dashboard never reads a small count as a quiet business day.
            metrics_format.series(
                "pseudex_suppressed_total", suppressed["by_type"],
                "Near-masks the deny layer kept OUT of masking, by type — values "
                "the context evidence said were never PII, not PII left "
                "unprotected", "type", kind="counter"),
            metrics_format.render(
                "pseudex_suppressed_since_seconds", suppressed["since"],
                "Unix time of this worker's first suppressed span; absent until "
                "the guard has fired at least once"),
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
