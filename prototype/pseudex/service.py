"""Pseudex sidecar service — /mask + /unmask for a host gateway (e.g. the Diva
LiteLLM callback). We do NOT call the provider; the host does. We only transform
text + keep the per-org vault + audit. Runs in the customer's contour.

  POST /mask          {org_id, messages, tools, conversation_id?}
                                                   -> {messages, tools}  (audited)
  POST /unmask        {org_id, response}           -> {response}
  POST /unmask_arguments {org_id, arguments[]}     -> {arguments[]}   (streamed tool calls)
  POST /unmask_chunk  {org_id, delta, carry, flush}-> {text, carry}      (SSE leg)
  POST /spans         {org_id, texts}              -> offsets for highlighting
  GET  /usage?org_id=...                           -> counts + recent (for UI)
  GET  /license                                    -> lease state, for monitoring

Vault is keyed per org_id and persistent, so the host can run many workers/pods
and still share one consistent token map (the in-process approach can't).

The process will not start without a detection lease, and gives it up when the
lease expires — `pseudex/license.py` has the reasoning. Only the DETECTION
endpoints go to 503 for that; see `_license_block`.
"""

import hmac
import logging
import os
import sys
import secrets
import threading
import uuid
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pseudex import sqlite_setup
from pseudex.assets import ASSETS, BundleNotLeased
from pseudex.audit import AuditLog, _preview
from pseudex.detect_all import Detector
from pseudex.envelope import (
    MaskContext,
    conversation_key,
    mask_messages,
    mask_tools,
    unmask_response,
)
from pseudex.license import (
    ENGINE_VERSION, STATE_LEASED, LicenseClient, LicenseError, explain)
from pseudex import metering
from pseudex.maskcache import MaskCache
from pseudex.operator import build_router
from pseudex.profiling import snapshot as profiling_snapshot
from pseudex.redact import residual_tokens, unmask_arguments, unmask_stream_chunk
from pseudex.vault import PSEUDONYM_SCOPES, Vault, count_values_since

# Without this the sidecar has NO logging configuration at all, so everything
# below WARNING is silently discarded — including every "lease renewed" line. The
# effect is not cosmetic: the customer's only way to see that the subscription is
# alive is this log, and a renewal that leaves no trace is indistinguishable from
# one that never happened. (`proxy.py` has always configured it; the sidecar was
# the leg that did not.)
logging.basicConfig(level=os.environ.get("PSEUDEX_LOG_LEVEL", "INFO").upper())
_log = logging.getLogger("pseudex.service")

# Persistent vault + audit live under PSEUDEX_DB_DIR (a mounted volume in
# production) so tokens stay reversible across restarts and workers.
_DB_DIR = os.environ.get("PSEUDEX_DB_DIR", ".")
# The default scope for «is this string our own substitute?», overridable per
# request. Read once: a setting that changed under a running process would make
# two halves of one dialogue disagree about whose the substitute is.
_PSEUDONYM_SCOPE = os.environ.get("PSEUDEX_PSEUDONYM_SCOPE", "").strip() or "conversation"
if _PSEUDONYM_SCOPE not in PSEUDONYM_SCOPES:
    raise SystemExit(f"PSEUDEX_PSEUDONYM_SCOPE must be one of {list(PSEUDONYM_SCOPES)}, got {_PSEUDONYM_SCOPE!r}")
# THE VAULT IS OPENED FIRST, before any other store is constructed, and that is
# not redundant with the `Vault` built per org further down. `AuditLog` and
# `Tenants` are process singletons, so a key that does not open THEM stops the
# worker while it is still starting; the vault is only touched by the first
# request that names an org. Without this, a wrong key produced a container that
# started, reported healthy, and then 500'd on the customer's first real message
# — after their gateway had already been told we were up.
#
# Before the others because opening a store CREATES it when it is missing: with
# a mistyped key, whichever store is opened first is written as a new file that
# the corrected key will then refuse. The vault is the file that matters and the
# one most likely to already exist, so it is the one that gets to object first.
# (`entrypoint.sh` runs PSEUDEX_ROLE=probe ahead of every worker, which is
# read-only and creates nothing — that is the real defence; this is the one that
# also covers `uvicorn pseudex.service:app`.)
sqlite_setup.preflight(os.path.join(_DB_DIR, "vault.db"), sqlite_setup.VAULT_STORE)
DETECTOR = Detector()
AUDIT = AuditLog(os.path.join(_DB_DIR, "audit.db"))
_VAULTS: dict[str, Vault] = {}

# One licence per PROCESS. Each worker generates its own keypair and leases
# independently: no shared secret on disk, no IPC, and a worker that cannot lease
# fails alone instead of taking a healthy sibling with it.
LICENSE = LicenseClient(
    base_url=os.environ.get("PSEUDEX_LICENSE_URL", "https://license.pseudex.ru"),
    key=os.environ.get("PSEUDEX_LICENSE_KEY", ""),
    # Keyed to the DATA DIRECTORY, not to the container. The licensing server
    # sums usage across instance ids, so an id that changes on restart while the
    # counters persist multiplies the bill by the number of restarts. The env
    # override stays for the e2e stand, which pins it as configuration.
    instance_id=os.environ.get("PSEUDEX_INSTANCE_ID", "") or AUDIT.installation_id(),
    ca_path=os.environ.get("PSEUDEX_LICENSE_CA", ""),
    # PROTECTED VALUES is what the invoice charges on, and it comes from the
    # VAULT, not from the audit: one row per distinct real value, ever. The
    # audit's own counts stay in the report because the operator's screens show
    # them, but nothing is billed on a number that moves with cache size.
    usage_provider=lambda: {
        **AUDIT.billing_totals(),
        "values": count_values_since(os.path.join(_DB_DIR, "vault.db"), 0.0),
    },
)

# Content-keyed masking cache: re-masking an identical (org, content) is an O(1)
# hit instead of re-running morphology. Bounded so the process can't grow without
# limit. Size is env-tunable (entries are short masked strings, ~cheap RAM).
_MASK_CACHE = MaskCache(int(os.environ.get("PSEUDEX_MASK_CACHE_SIZE", "20000")))

# Backpressure: cap concurrent CPU-heavy mask passes so a burst QUEUES (graceful
# degradation) instead of thrashing all cores at once. Default tracks the
# threadpool size; tune per deployment. Acquired around the to_thread offload.
_MASK_CONCURRENCY = int(os.environ.get("PSEUDEX_MASK_CONCURRENCY", "8"))

# TWO SURFACES, TWO CREDENTIALS, held by two different parties: the gateway
# token lives in the customer's gateway configuration, the operator token in
# their interface. Reachability from inside the contour is not authority to read
# — that principle was already written here, and then applied to only half the
# port.
#
# Credential for the GATEWAY surface. Separate from the operator token because
# they are held by different parties: this one lives in the customer's gateway
# config, the operator one in their interface.
#
# It exists because the masking endpoints were open, and that was wrong in a way
# the original comment argued itself out of. /unmask is a DETOKENIZATION ORACLE:
# hand it a token, get the real personal value. /usage listed the tokens to try.
# Together, anyone who could open a socket to this port could enumerate and
# decode the whole vault — with no record, while /reveal next door demanded an
# actor and wrote an access log. The audit guarantee was decorative.
#
# Required, not optional. An "only enforced when set" flag is a hole that ships
# enabled by default, and there are no deployments in the field to migrate.
GATEWAY_TOKEN = os.environ.get("PSEUDEX_GATEWAY_TOKEN", "")
ADMIN_TOKEN = os.environ.get("PSEUDEX_ADMIN_TOKEN", "")
if not GATEWAY_TOKEN:
    GATEWAY_TOKEN = secrets.token_urlsafe(24)
    _log.warning("PSEUDEX_GATEWAY_TOKEN was not set — generated a per-process one. "
                 "With more than one worker the gateway will be rejected at random. "
                 "entrypoint.sh sets it once for the container.")
if not ADMIN_TOKEN:
    ADMIN_TOKEN = secrets.token_urlsafe(24)
    # Loud, because the failure it causes is baffling otherwise: with several
    # workers behind one SO_REUSEPORT port, each would generate a DIFFERENT
    # valid token, and the interface would work and then 401 as the kernel moved
    # it to a sibling. entrypoint.sh sets one for the whole container.
    _log.warning("PSEUDEX_ADMIN_TOKEN was not set — generated a per-process one. "
                 "With more than one worker the operator interface will fail "
                 "intermittently. Set it once for the container.")


def _same_secret(presented: str, expected: str) -> bool:
    """Constant-time compare that survives a non-ASCII header.

    `hmac.compare_digest` raises TypeError on a `str` outside ASCII, so
    «Authorization: Bearer левый» answered 500 with a traceback instead of 401 —
    on the authorisation path, which is the last place that should answer with a
    stack. Encoding first keeps the comparison constant-time and makes every
    wrong credential fail the same way.
    """
    return hmac.compare_digest(presented.encode("utf-8", "surrogatepass"),
                               expected.encode("utf-8"))


def _require_operator(request: Request) -> None:
    """Gate the operator surface on a bearer token.

    `hmac.compare_digest`, not `==`: the comparison is against a secret and a
    short-circuiting compare leaks its prefix through timing. Cheap here,
    impossible to retrofit convincingly later.
    """
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    if not presented or not _same_secret(presented, ADMIN_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="operator token required (Authorization: Bearer …)",
        )


def _require_gateway(request: Request) -> None:
    """Gate the masking surface on the gateway token."""
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    if not presented or not _same_secret(presented, GATEWAY_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="gateway token required (Authorization: Bearer …)",
        )


def _warmup() -> None:
    """Pay the dictionary-load cost ONCE at startup so the first real request
    doesn't. pymorphy3's MorphAnalyzer + natasha's NER/AddrExtractor lazily load
    their dictionaries on first parse; a dummy detect() forces all of them."""
    DETECTOR.detect("Иван Петров, телефон +7 999 123-45-67, улица Ленина 5")


def _acquire_license() -> None:
    """Lease before serving. Raising here aborts uvicorn startup with a non-zero
    exit — which is the point: a process with no assets has nothing to degrade to,
    so it must not come up and pretend to be a PII gateway."""
    if not os.environ.get("PSEUDEX_LICENSE_KEY"):
        raise LicenseError("license_missing", "PSEUDEX_LICENSE_KEY is not set")
    LICENSE.acquire()
    LICENSE.start()


@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    # The lease is blocking network I/O and the warmup is CPU; both go to a
    # thread so the event loop is never pinned during startup.
    try:
        await anyio.to_thread.run_sync(_acquire_license)
    except LicenseError as error:
        # Printed, not just logged at ERROR: this is the last thing the operator
        # sees before the container exits, and a structured log line scrolls past
        # inside a traceback. The remedy is the point — the refusal is correct
        # behaviour, and without it the operator cannot tell correct from broken.
        print(f"\n{'=' * 72}\n  PSEUDEX НЕ ЗАПУСТИЛСЯ — {error.code}\n{'=' * 72}\n"
              f"  {error.detail}\n\n  {explain(error.code)}\n{'=' * 72}\n",
              file=sys.stderr, flush=True)
        _log.error("refusing to start — %s: %s", error.code, error.detail)
        raise
    # Warm the models AFTER the bundle is loaded: warmup runs a real detection
    # pass, which needs the leased assets.
    await anyio.to_thread.run_sync(_warmup)
    yield
    LICENSE.stop()


app = FastAPI(
    title="Pseudex sidecar",
    lifespan=_lifespan,
    # No /docs, /redoc or /openapi.json. They served an unauthenticated map of
    # the operator surface — every path, every parameter — to anyone who could
    # reach the port. The integration contract lives in docs/integration.md,
    # which is where a customer reads it.
    docs_url=None, redoc_url=None, openapi_url=None,
)


@app.exception_handler(BundleNotLeased)
async def _bundle_not_leased(_request: Request, error: BundleNotLeased) -> JSONResponse:
    """Defence in depth against the race the licence check cannot cover: the
    renewal thread may unload the assets between the check at the top of a
    request and the detection pass in the worker thread. Fail-closed either way —
    this becomes a 503, never a pass-through."""
    return JSONResponse(
        {"error": "bundle_unavailable", "detail": str(error),
         "license": {"state": LICENSE.state()}},
        status_code=503,
    )

# Bounded semaphore created on the running loop (anyio limiter is loop-bound).
_MASK_LIMITER = anyio.CapacityLimiter(_MASK_CONCURRENCY)

# Guards lazy creation of the per-org Vault objects. Without it two worker
# threads could open two SQLite connections for the same org (wasteful + two
# separate locks). With it, one Vault (one connection, one lock) per org.
_VAULTS_LOCK = threading.Lock()


def _vault(org_id: str) -> Vault:
    vault = _VAULTS.get(org_id)
    if vault is not None:
        return vault
    with _VAULTS_LOCK:
        vault = _VAULTS.get(org_id)
        if vault is None:
            vault = Vault(os.path.join(_DB_DIR, "vault.db"), org_id)
            _VAULTS[org_id] = vault
        return vault


def _context(org_id: str, agent_id: str, conversation_id: str,
             pseudonym_scope: str = "") -> MaskContext:
    return MaskContext(
        detector=DETECTOR,
        vault=(_vault(org_id).for_conversation(conversation_id)
               .with_pseudonym_scope(pseudonym_scope or _PSEUDONYM_SCOPE)),
        audit=AUDIT,
        cache=_MASK_CACHE,
        org_id=org_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    )


def _mask_request(
    messages: list[dict[str, object]],
    tools: object,
    org_id: str,
    agent_id: str,
    conversation_id: str,
    skip_template: bool,
    pseudonym_scope: str = "",
) -> tuple[list[dict[str, object]], object]:
    """One unit of CPU-heavy work, so messages and tools share a single hop onto
    the worker thread instead of paying the offload twice.

    Takes the IDS, not a ready MaskContext, and resolves the vault HERE. Building
    the context at the call site looked harmless but ran on the event loop: the
    first request for a new org constructs a Vault, which opens SQLite and may
    wait out another worker's journal-mode switch — up to ten seconds of
    `time.sleep` on the loop, stalling /health and every other in-flight request
    in this worker. That is the exact failure the threadpool offload exists to
    prevent."""
    context = _context(org_id, agent_id, conversation_id, pseudonym_scope)
    result = (
        mask_messages(messages, context, skip_template),
        mask_tools(tools, context, skip_template),
    )
    # Counted AFTER masking succeeds, and never before: masking is fail-closed,
    # so a request that raised was blocked and never reached a model. Billing a
    # blocked request would charge the customer for the one outcome they did not
    # get. Runs on this thread, so the commit is off the event loop.
    metering.bill(AUDIT, LICENSE, org_id, agent_id)
    return result


def _spans_for(text: str, vault: Vault) -> list[dict[str, object]]:
    """PII spans for UI highlighting — offsets map into the ORIGINAL text
    (normalization is 1:1), so the caller highlights text[start:end]. token is
    what the value was replaced with for the model (None if never masked).
    Read-only: does NOT mint tokens or write audit."""
    out: list[dict[str, object]] = []
    for span in DETECTOR.detect(text):
        out.append({
            "start": span.start,
            "end": span.end,
            "type": span.entity_type,
            "token": vault.peek_token(span.value, span.entity_type),
            "preview": _preview(span.value),
        })
    return out


@app.get("/profile")
async def profile() -> JSONResponse:
    """Where the time goes, per stage, sorted by total cost — the top row is the
    thing worth optimizing. Empty unless PSEUDEX_PROFILE=1. Counts are per WORKER
    process, so query with --workers 1 when attributing a benchmark run."""
    return JSONResponse(profiling_snapshot())


def _license_block() -> JSONResponse | None:
    """The 503 that makes the subscription real, or None when we may serve.

    Only the DETECTION endpoints are gated. `/unmask`, `/unmask_chunk` and
    `/reveal` stay open even when expired, because those read the customer's own
    vault — tokens they already hold, for values that are already theirs.
    Withholding those would be holding their data hostage, and it is not needed
    for the lever to work: without `/mask` a fail-closed gateway cannot send
    anything to a model at all, so the agents stop regardless."""
    if LICENSE.is_serving():
        return None
    status = LICENSE.status()
    # ИСЧЕРПАНИЕ ЁМКОСТИ — НЕ ИСТЁКШАЯ ЛИЦЕНЗИЯ, и называть его так значило
    # отправлять оператора проверять оплату вместо исходящего доступа. Подписка
    # цела, ключ валиден, аренда свежая — кончилась предоплаченная ёмкость, а
    # взять следующую не у кого.
    code = status.code
    if code is None:
        code = ("capacity_exhausted"
                if status.capacity_left == 0 else "license_expired")
    return JSONResponse(
        {
            "error": code,
            # Ведущая фраза — ОТДЕЛЬНАЯ КОНСТАНТА, а не часть f-строки: так её
            # берёт `build_harden_strings.py` (фрагмент f-строки закодировать
            # нельзя), и говорящий маяк не лежит в бинарнике открытым текстом.
            "detail": (
                "no valid detection lease"
                + f" (state={status.state}); "
                + f"last successful lease {status.seconds_since_lease:.0f}s ago"
                if status.seconds_since_lease is not None
                else "no detection lease was ever obtained"
            ),
            "license": {
                "state": status.state,
                "last_error": status.last_error,
                "bundle_version": status.bundle_version,
                "consumed": status.consumed,
                "granted": status.granted,
            },
            "remedy": explain(code),
        },
        status_code=503,
    )


@app.get("/health")
async def health() -> JSONResponse:
    status = LICENSE.status()
    body: dict[str, object] = {
        "status": "ok" if LICENSE.is_serving() else "degraded",
        "license": status.state,
        # Which worker answered. The container runs N independent processes
        # sharing one port via SO_REUSEPORT, and this is what makes that
        # observable — both for our own load gate and for a customer diagnosing
        # "one worker is wedged" without exec'ing into the container.
        "pid": os.getpid(),
    }
    if status.grace_left_seconds is not None and status.state == "stale":
        body["grace_left_s"] = round(status.grace_left_seconds)
    return JSONResponse(body, status_code=200 if LICENSE.is_serving() else 503)


@app.get("/license")
async def license_status() -> JSONResponse:
    """What the licence is doing right now — for the customer's own monitoring,
    so an expiring subscription is visible before it stops the agents.

    ANSWERS 503 WHILE DEGRADED, and that is the whole point of it being a
    separate endpoint from `/health`. All three personas raised the same gap:
    during the grace window `/health` answers 200 «ok» and only a FIELD changes,
    so an ordinary probe — a docker healthcheck, an uptime check, a blackbox
    exporter — stays silent through the entire degradation and learns about it
    when the gateway stops.

    The fix is NOT to make `/health` fail. Grace exists precisely so a working
    gateway keeps serving through OUR outage, and a healthcheck that fails would
    have the orchestrator restart the container — which needs a fresh lease,
    which is the thing that is unavailable. That turns a survivable outage into
    an unrecoverable one.

    So liveness and alerting are split, the way they always should be:

        docker healthcheck / orchestration -> /health   (200 while serving)
        monitoring and alerting            -> /license  (503 while degraded)

    The body is unchanged and still parses on either code, so anything already
    reading it keeps working.
    """
    status = LICENSE.status()
    # `LEASED` is the only healthy state. `stale` is serving on grace and
    # `expired` is not serving at all — both are things somebody must be told
    # about, and the difference between them is in the body.
    #
    # COMPARED AGAINST THE CONSTANT, NEVER AGAINST A LITERAL. The wire value of
    # `STATE_LEASED` is `"active"`, not `"leased"` — so `state != "leased"` was
    # true on a perfectly healthy container and this endpoint, the one the
    # docstring above designates for monitoring and alerting, answered 503 for
    # its whole life. Every customer who wired an alert to it as documented got
    # a page that never cleared, and the natural remedy is to stop trusting the
    # alert. Nothing caught it: `e2e/gates.py::license_state` read `.json()` and
    # never looked at the status code, and L7/L8 assert on the body's `state`.
    degraded = status.state != STATE_LEASED
    return JSONResponse(status_code=503 if degraded else 200, content={
        "state": status.state,
        "code": status.code,
        "lease_id": status.lease_id,
        "bundle_version": status.bundle_version,
        "assets_loaded": ASSETS.is_loaded,
        "seconds_since_lease": (
            None if status.seconds_since_lease is None else round(status.seconds_since_lease, 1)
        ),
        "grace_left_s": (
            None if status.grace_left_seconds is None else round(status.grace_left_seconds)
        ),
        "last_error": status.last_error,
    })


@app.post("/mask", dependencies=[Depends(_require_gateway)])
async def mask(request: Request) -> JSONResponse:
    blocked = _license_block()
    if blocked is not None:
        return blocked
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    agent_id = str(body.get("agent_id", ""))
    messages = body.get("messages")
    if not isinstance(messages, list):
        return JSONResponse({"error": "messages must be a list"}, status_code=400)
    # The host gateway MAY name the conversation and should where it can; when it
    # does not, the transcript names itself (see `conversation_key`). Falling back
    # rather than requiring the field keeps every existing caller working — a
    # gateway that suddenly had to send a new field would simply not send it, and
    # a scope nobody sets is a scope that does nothing.
    conversation_id = str(body.get("conversation_id", "")) or conversation_key(messages)
    # `skip_system` names the wire field the host gateway already sends; it means
    # "this payload carries the agent's own TEMPLATE", which covers both the
    # system prompt and the tool schemas.
    skip_template = bool(body.get("skip_system", False))
    # THE HOST DECLARES WHETHER ITS AGENT HAS MEMORY. A substitute recalled from
    # an earlier dialogue is only recognisable as ours at customer scope; the
    # default stays `conversation`, because widening it also stops us masking a
    # real person who bears a name we minted elsewhere. `Vault.with_pseudonym_
    # scope` states the whole trade. An unknown value is a 400 rather than a
    # silent fallback: a host that misspells the field must not believe it asked
    # for a scope it did not get.
    pseudonym_scope = str(body.get("pseudonym_scope", "")) or _PSEUDONYM_SCOPE
    if pseudonym_scope not in PSEUDONYM_SCOPES:
        return JSONResponse(
            {"error": f"pseudonym_scope must be one of {list(PSEUDONYM_SCOPES)}"}, status_code=400)
    tools = body.get("tools")
    # CPU-heavy morphology runs in a worker thread (NOT the event loop), so
    # /health and other requests stay responsive while a large /mask is in
    # flight. The capacity limiter applies backpressure: a burst beyond
    # PSEUDEX_MASK_CONCURRENCY QUEUES on the limiter instead of thrashing every
    # core at once. FAIL-CLOSED is preserved: any exception in masking propagates
    # to a 5xx, which the caller treats as a block (it never sees raw PII).
    masked_messages, masked_tools = await anyio.to_thread.run_sync(
        _mask_request, messages, tools, org_id, agent_id, conversation_id,
        skip_template, pseudonym_scope,
        limiter=_MASK_LIMITER,
    )
    payload: dict[str, object] = {"messages": masked_messages}
    if tools is not None:
        payload["tools"] = masked_tools
    return JSONResponse(payload)


@app.post("/unmask", dependencies=[Depends(_require_gateway)])
async def unmask(request: Request) -> JSONResponse:
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    response = body.get("response")
    if not isinstance(response, dict):
        return JSONResponse({"error": "response must be an object"}, status_code=400)
    # Detokenization is indexed lookups now, but still SQLite I/O per answer —
    # offload so it never blocks the loop.
    result = await anyio.to_thread.run_sync(
        _unmask_for, response, org_id, limiter=_MASK_LIMITER
    )
    # WHAT DID NOT COME BACK. Detokenization is best-effort by construction: a
    # model that reorders or shortens a substitute produces a string that
    # resolves to nothing, and the FAKE then reaches the customer's tool. Until
    # now that happened with a 200, empty counters and nothing in the log —
    # every persona in the 18.08 run asked for this field by name.
    #
    # A LIST, not a boolean, and the values are OUR substitutes: naming them
    # discloses nothing about the customer's data, and the caller needs them to
    # decide what to do — refuse the tool call, retry, or ask the model again.
    residual = _residual_for(result, org_id)
    payload: dict[str, object] = {"response": result}
    if residual:
        payload["residual_tokens"] = residual
    return JSONResponse(payload, headers=({"X-Pseudex-Residual": str(len(residual))}
                                          if residual else None))


@app.post("/unmask_arguments", dependencies=[Depends(_require_gateway)])
async def unmask_arguments_endpoint(request: Request) -> JSONResponse:
    """Detokenize the ARGUMENTS of a tool call the gateway assembled from a stream.

    WHY THIS EXISTS AND `/unmask_chunk` CANNOT DO IT. The streaming endpoint
    substitutes flat text, and a real value is arbitrary text: «ООО "АЭРОМЭП"»
    put into a JSON string by plain replacement injects two bare quotes and the
    object stops parsing. Measured, not theorised —

        через /unmask_chunk : {"company":"ООО "АЭРОМЭП""}      JSON сломан
        через сюда         : {"company": "ООО \\"АЭРОМЭП\\""}   ок

    — and on Russian business traffic it is the common case, because every legal
    entity is written with quotes. So the arguments are parsed and each string
    LEAF is detokenised on its own, which escapes whatever the real value turns
    out to contain by construction.

    THE CALLER MUST BUFFER, and that is the deliberate trade this endpoint
    encodes. A tool call arrives as `arguments` FRAGMENTS across SSE chunks, and
    nothing inside a JSON string can be emitted before the string closes —
    the escaping depends on the whole value, and an already-sent prefix cannot
    be retracted. The proxy leg made the same choice (`_stream_as_single`);
    having the two halves of the product disagree about it would be worse than
    the smoothness either one buys.

    So the gateway's SSE loop is PER FIELD, never per chunk:
      * `delta.content`                        -> /unmask_chunk, as it streams
      * `delta.tool_calls[].function.arguments` -> accumulate, then here once

    Body: {org_id, arguments: [str, ...]} -> {arguments: [str, ...]}.
    A list because one streamed response may carry several tool calls, and the
    gateway should not pay a round trip for each.
    """
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    arguments = body.get("arguments")
    if not isinstance(arguments, list) or not all(isinstance(a, str) for a in arguments):
        return JSONResponse({"error": "arguments must be a list of strings"},
                            status_code=400)
    restored, residual = await anyio.to_thread.run_sync(
        _unmask_arguments_for, arguments, org_id, limiter=_MASK_LIMITER
    )
    # The same signal `/unmask` carries, and it matters MORE here: a substitute
    # that fails to resolve inside a tool call is a fake reaching the tool, which
    # is the one outcome this product exists to prevent. The caller cannot see it
    # any other way — the JSON is well-formed and the status is 200.
    payload: dict[str, object] = {"arguments": restored}
    if residual:
        payload["residual_tokens"] = residual
    return JSONResponse(payload, headers=({"X-Pseudex-Residual": str(len(residual))}
                                          if residual else None))


@app.post("/unmask_chunk", dependencies=[Depends(_require_gateway)])
async def unmask_chunk(request: Request) -> JSONResponse:
    """Detokenize one SSE delta of ASSISTANT TEXT on the streaming leg.

    TEXT ONLY — `delta.content`, never `delta.tool_calls[].function.arguments`.
    This path substitutes flat text, and a real value is arbitrary text: a
    company name carrying quotes injects them bare into the JSON and the tool
    call stops parsing. Tool arguments go to `/unmask_arguments`, which parses
    the object and escapes by construction; the reasoning and the measurement
    are there.

    Nothing here can detect the misuse, and deliberately does not try. A brace in
    prose is prose, so sniffing the content would refuse real answers to guess at
    a mistake the CALLER's own loop cannot make once it reads the two fields
    separately — which is what an SSE loop does anyway.

    STATELESS: the caller passes back the `carry` it received from the previous
    call and sets `flush` on the final chunk. The host gateway runs many worker
    processes and a stream can die mid-flight, so per-stream state kept here would
    need a shared store plus TTL reaping; the caller already owns the connection,
    so it owns the carry.

    ONE CARRY PER CHOICE. With `n > 1` the deltas of different choices interleave
    on the same connection, and a shared carry would splice one answer's tail
    onto another's head. The proxy leg keys its detokenizers on `choice.index`
    for exactly this; a caller here must do the same.

    Body: {org_id, delta, carry, flush} -> {text, carry}."""
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    delta = body.get("delta", "")
    carry = body.get("carry", "")
    if not isinstance(delta, str) or not isinstance(carry, str):
        return JSONResponse({"error": "delta and carry must be strings"}, status_code=400)
    text, new_carry = await anyio.to_thread.run_sync(
        _unmask_chunk_for, delta, carry, org_id, bool(body.get("flush", False)),
        limiter=_MASK_LIMITER,
    )
    return JSONResponse({"text": text, "carry": new_carry})


def _spans_for_texts(texts: list[object], org_id: str) -> list[list[dict[str, object]]]:
    vault = _vault(org_id)
    return [_spans_for(text, vault) if isinstance(text, str) else [] for text in texts]


def _unmask_arguments_for(arguments: list[str],
                          org_id: str) -> tuple[list[str], list[str]]:
    """Vault resolved inside the worker thread — see _mask_request."""
    vault = _vault(org_id)
    restored = [unmask_arguments(raw, vault) for raw in arguments]
    residual: list[str] = []
    for text in restored:
        residual.extend(residual_tokens(text, vault))
    return restored, sorted(set(residual))


def _unmask_for(response: dict[str, object], org_id: str) -> dict[str, object]:
    """Vault resolved inside the worker thread — see _mask_request."""
    return unmask_response(response, _vault(org_id))


def _residual_for(response: dict[str, object], org_id: str) -> list[str]:
    """Substitutes still standing in an already-detokenized answer.

    Walks the same text the caller will read, so what it reports is exactly what
    would have reached their tool. Read-only: no token is minted and nothing is
    audited — a diagnostic that changes the vault would change the thing it is
    diagnosing.
    """
    vault = _vault(org_id)
    found: list[str] = []
    for text in _response_texts(response):
        found.extend(residual_tokens(text, vault))
    return sorted(set(found))


def _response_texts(response: dict[str, object]) -> list[str]:
    """Every string in a chat completion a customer's code might act on."""
    out: list[str] = []
    for choice in response.get("choices", []) or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            out.append(content)
        for call in message.get("tool_calls", []) or []:
            if isinstance(call, dict):
                arguments = (call.get("function") or {}).get("arguments")
                if isinstance(arguments, str):
                    out.append(arguments)
    return out


def _unmask_chunk_for(delta: str, carry: str, org_id: str,
                      flush: bool) -> tuple[str, str]:
    """Vault resolved inside the worker thread — see _mask_request."""
    return unmask_stream_chunk(delta, carry, _vault(org_id), flush)


@app.post("/spans", dependencies=[Depends(_require_gateway)])
async def spans(request: Request) -> JSONResponse:
    """PII spans per text for dialog highlighting (read-only).
    Body: {org_id, texts: [str]} -> {results: [[{start,end,type,token,preview}], ...]}."""
    blocked = _license_block()
    if blocked is not None:
        return blocked
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    texts = body.get("texts")
    if not isinstance(texts, list):
        return JSONResponse({"error": "texts must be a list"}, status_code=400)
    # Detection runs morphology per text -> offload off the loop.
    results = await anyio.to_thread.run_sync(
        _spans_for_texts, texts, org_id, limiter=_MASK_LIMITER
    )
    return JSONResponse({"results": results})


@app.get("/usage", dependencies=[Depends(_require_operator)])
async def usage(request: Request) -> JSONResponse:
    """Org-wide stats. Pass ?agent_id=... to scope to a single agent."""
    org_id = request.query_params.get("org_id", "default")
    agent_id = request.query_params.get("agent_id")
    if agent_id:
        return JSONResponse({
            "org_id": org_id,
            "agent_id": agent_id,
            "protected_counts": AUDIT.counts_for_agent(org_id, agent_id),
            "recent": AUDIT.recent_for_agent(org_id, agent_id, 50),
        })
    return JSONResponse({
        "org_id": org_id,
        # 0.0 = all time, said explicitly. This endpoint is the org-wide
        # summary and has no period in its contract.
        "protected_counts": AUDIT.counts(org_id, 0.0, ""),
        "recent": AUDIT.recent(org_id, 50),
    })


@app.post("/reveal", dependencies=[Depends(_require_operator)])
async def reveal(request: Request) -> JSONResponse:
    """Reveal the real value behind a token.

    The customer's organisation is the data controller and is entitled to the
    original — but an entitlement without a record is what turns a masking
    gateway into an unaudited disclosure channel, which is worse for them under
    152-ФЗ than having no reveal at all. So `actor` is REQUIRED (who is asking:
    a UI session, an operator name, a script), and the access record is written
    BEFORE the value is returned. Misses are recorded too, because a sweep of
    guessed tokens leaves no other trace.

    The record carries who / which token / when, never the value: storing that
    would make the log the second copy of the data the vault exists to contain.

    Body: {org_id, token, actor} -> {value: <real> | null}.
    """
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    token = body.get("token")
    actor = body.get("actor")
    if not isinstance(token, str) or not token:
        return JSONResponse({"error": "token must be a non-empty string"}, status_code=400)
    if not isinstance(actor, str) or not actor.strip():
        return JSONResponse(
            {"error": "actor is required",
             "detail": "every reveal is recorded against whoever asked for it"},
            status_code=400,
        )
    value = await anyio.to_thread.run_sync(_reveal_for, org_id, token, actor.strip())
    return JSONResponse({"value": value})


def _reveal_for(org_id: str, token: str, actor: str) -> str | None:
    """Vault lookup plus the access record, on a worker thread — both are SQLite
    writes/reads and neither belongs on the event loop."""
    value, entity_type = _vault(org_id).reveal(token)
    AUDIT.record_reveal(org_id, actor, token, entity_type, value is not None)
    return value


async def _selfcheck(org_id: str, text: str) -> dict[str, object]:
    """The round trip, on the real path: detect, mask, then detokenize what the
    mask produced. Anything short of running the actual endpoints would let this
    pass while the product is broken, which is the one thing a self-check must
    never do."""
    return await anyio.to_thread.run_sync(_selfcheck_sync, org_id, text)


def _selfcheck_sync(org_id: str, text: str) -> dict[str, object]:
    from pseudex.envelope import mask_one
    from pseudex.redact import unmask_text

    # The self-check is its own conversation and names itself: it must never
    # share a scope with the customer's traffic, or a link made there could be
    # served into a real dialogue.
    context = _context(org_id, "selfcheck", "selfcheck")
    detected = DETECTOR.detect(text)
    masked = mask_one(text, context)
    vault = _vault(org_id)
    # Tokens are read AFTER masking, because before it there is nothing to read:
    # `peek_token` is read-only by design and returns None for a value that has
    # never been minted. The interface needs them to highlight what the model saw.
    spans = [
        {"start": span.start, "end": span.end, "type": span.entity_type,
         "value": span.value,
         "token": vault.peek_token(span.value, span.entity_type)}
        for span in detected
    ]
    restored = unmask_text(masked, vault)
    return {
        # The check passes only if the model-facing text lost every detected
        # value AND the original came back. Either half alone can be true while
        # the product is broken.
        "ok": masked != text and restored == text and bool(spans),
        "original": text,
        "masked": masked,
        "restored": restored,
        "spans": spans,
    }


app.include_router(
    build_router(AUDIT, LICENSE, ASSETS, ENGINE_VERSION, _selfcheck),
    dependencies=[Depends(_require_operator)],
)
