"""Obscura sidecar service — /mask + /unmask for a host gateway (e.g. the Diva
LiteLLM callback). We do NOT call the provider; the host does. We only transform
text + keep the per-org vault + audit. Runs in the customer's contour.

  POST /mask          {org_id, messages, tools}    -> {messages, tools}  (audited)
  POST /unmask        {org_id, response}           -> {response}
  POST /unmask_chunk  {org_id, delta, carry, flush}-> {text, carry}      (SSE leg)
  POST /spans         {org_id, texts}              -> offsets for highlighting
  GET  /usage?org_id=...                           -> counts + recent (for UI)
  GET  /license                                    -> lease state, for monitoring

Vault is keyed per org_id and persistent, so the host can run many workers/pods
and still share one consistent token map (the in-process approach can't).

The process will not start without a detection lease, and gives it up when the
lease expires — `obscura/license.py` has the reasoning. Only the DETECTION
endpoints go to 503 for that; see `_license_block`.
"""

import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from obscura.assets import ASSETS, BundleNotLeased
from obscura.audit import AuditLog, _preview
from obscura.detect_all import Detector
from obscura.envelope import MaskContext, mask_messages, mask_tools, unmask_response
from obscura.license import LicenseClient, LicenseError
from obscura.maskcache import MaskCache
from obscura.profiling import snapshot as profiling_snapshot
from obscura.redact import unmask_stream_chunk
from obscura.vault import Vault

# Without this the sidecar has NO logging configuration at all, so everything
# below WARNING is silently discarded — including every "lease renewed" line. The
# effect is not cosmetic: the customer's only way to see that the subscription is
# alive is this log, and a renewal that leaves no trace is indistinguishable from
# one that never happened. (`proxy.py` has always configured it; the sidecar was
# the leg that did not.)
logging.basicConfig(level=os.environ.get("OBSCURA_LOG_LEVEL", "INFO").upper())
_log = logging.getLogger("obscura.service")

# Persistent vault + audit live under OBSCURA_DB_DIR (a mounted volume in
# production) so tokens stay reversible across restarts and workers.
_DB_DIR = os.environ.get("OBSCURA_DB_DIR", ".")
DETECTOR = Detector()
AUDIT = AuditLog(os.path.join(_DB_DIR, "audit.db"))
_VAULTS: dict[str, Vault] = {}

# One licence per PROCESS. Each worker generates its own keypair and leases
# independently: no shared secret on disk, no IPC, and a worker that cannot lease
# fails alone instead of taking a healthy sibling with it.
LICENSE = LicenseClient(
    base_url=os.environ.get("OBSCURA_LICENSE_URL", "https://license.obscura.ru"),
    key=os.environ.get("OBSCURA_LICENSE_KEY", ""),
    # Set by entrypoint.sh so every worker of one container reports the same
    # instance; a bare process would otherwise look like a separate deployment.
    instance_id=os.environ.get("OBSCURA_INSTANCE_ID", "") or uuid.uuid4().hex[:12],
    ca_path=os.environ.get("OBSCURA_LICENSE_CA", ""),
    usage_provider=lambda: AUDIT.billing_totals(),
)

# Content-keyed masking cache: re-masking an identical (org, content) is an O(1)
# hit instead of re-running morphology. Bounded so the process can't grow without
# limit. Size is env-tunable (entries are short masked strings, ~cheap RAM).
_MASK_CACHE = MaskCache(int(os.environ.get("OBSCURA_MASK_CACHE_SIZE", "20000")))

# Backpressure: cap concurrent CPU-heavy mask passes so a burst QUEUES (graceful
# degradation) instead of thrashing all cores at once. Default tracks the
# threadpool size; tune per deployment. Acquired around the to_thread offload.
_MASK_CONCURRENCY = int(os.environ.get("OBSCURA_MASK_CONCURRENCY", "8"))


def _warmup() -> None:
    """Pay the dictionary-load cost ONCE at startup so the first real request
    doesn't. pymorphy3's MorphAnalyzer + natasha's NER/AddrExtractor lazily load
    their dictionaries on first parse; a dummy detect() forces all of them."""
    DETECTOR.detect("Иван Петров, телефон +7 999 123-45-67, улица Ленина 5")


def _acquire_license() -> None:
    """Lease before serving. Raising here aborts uvicorn startup with a non-zero
    exit — which is the point: a process with no assets has nothing to degrade to,
    so it must not come up and pretend to be a PII gateway."""
    if not os.environ.get("OBSCURA_LICENSE_KEY"):
        raise LicenseError("license_missing", "OBSCURA_LICENSE_KEY is not set")
    LICENSE.acquire()
    LICENSE.start()


@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    # The lease is blocking network I/O and the warmup is CPU; both go to a
    # thread so the event loop is never pinned during startup.
    try:
        await anyio.to_thread.run_sync(_acquire_license)
    except LicenseError as error:
        _log.error("refusing to start — %s: %s", error.code, error.detail)
        raise
    # Warm the models AFTER the bundle is loaded: warmup runs a real detection
    # pass, which needs the leased assets.
    await anyio.to_thread.run_sync(_warmup)
    yield
    LICENSE.stop()


app = FastAPI(title="Obscura sidecar", lifespan=_lifespan)


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


def _context(org_id: str, agent_id: str) -> MaskContext:
    return MaskContext(
        detector=DETECTOR,
        vault=_vault(org_id),
        audit=AUDIT,
        cache=_MASK_CACHE,
        org_id=org_id,
        agent_id=agent_id,
    )


def _mask_request(
    messages: list[dict[str, object]],
    tools: object,
    org_id: str,
    agent_id: str,
    skip_template: bool,
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
    context = _context(org_id, agent_id)
    return (
        mask_messages(messages, context, skip_template),
        mask_tools(tools, context, skip_template),
    )


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
    thing worth optimizing. Empty unless OBSCURA_PROFILE=1. Counts are per WORKER
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
    return JSONResponse(
        {
            "error": status.code or "license_expired",
            "detail": (
                f"no valid detection lease (state={status.state}); "
                f"last successful lease {status.seconds_since_lease:.0f}s ago"
                if status.seconds_since_lease is not None
                else "no detection lease was ever obtained"
            ),
            "license": {
                "state": status.state,
                "last_error": status.last_error,
                "bundle_version": status.bundle_version,
            },
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
    so an expiring subscription is visible before it stops the agents."""
    status = LICENSE.status()
    return JSONResponse({
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


@app.post("/mask")
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
    # `skip_system` names the wire field the host gateway already sends; it means
    # "this payload carries the agent's own TEMPLATE", which covers both the
    # system prompt and the tool schemas.
    skip_template = bool(body.get("skip_system", False))
    tools = body.get("tools")
    # CPU-heavy morphology runs in a worker thread (NOT the event loop), so
    # /health and other requests stay responsive while a large /mask is in
    # flight. The capacity limiter applies backpressure: a burst beyond
    # OBSCURA_MASK_CONCURRENCY QUEUES on the limiter instead of thrashing every
    # core at once. FAIL-CLOSED is preserved: any exception in masking propagates
    # to a 5xx, which the caller treats as a block (it never sees raw PII).
    masked_messages, masked_tools = await anyio.to_thread.run_sync(
        _mask_request, messages, tools, org_id, agent_id, skip_template,
        limiter=_MASK_LIMITER,
    )
    payload: dict[str, object] = {"messages": masked_messages}
    if tools is not None:
        payload["tools"] = masked_tools
    return JSONResponse(payload)


@app.post("/unmask")
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
    return JSONResponse({"response": result})


@app.post("/unmask_chunk")
async def unmask_chunk(request: Request) -> JSONResponse:
    """Detokenize one SSE delta on the streaming leg.

    STATELESS: the caller passes back the `carry` it received from the previous
    call and sets `flush` on the final chunk. The host gateway runs many worker
    processes and a stream can die mid-flight, so per-stream state kept here would
    need a shared store plus TTL reaping; the caller already owns the connection,
    so it owns the carry.

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


def _unmask_for(response: dict[str, object], org_id: str) -> dict[str, object]:
    """Vault resolved inside the worker thread — see _mask_request."""
    return unmask_response(response, _vault(org_id))


def _unmask_chunk_for(delta: str, carry: str, org_id: str,
                      flush: bool) -> tuple[str, str]:
    """Vault resolved inside the worker thread — see _mask_request."""
    return unmask_stream_chunk(delta, carry, _vault(org_id), flush)


@app.post("/spans")
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


@app.get("/usage")
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
        "protected_counts": AUDIT.counts(org_id),
        "recent": AUDIT.recent(org_id, 50),
    })


@app.post("/reveal")
async def reveal(request: Request) -> JSONResponse:
    """Reveal the real value behind a token. The operator's organisation is the
    data controller and is entitled to see the original; the value is fetched
    only on explicit request and is never stored in the audit log (the audit
    keeps a masked preview). Body: {org_id, token} -> {value: <real> | null}."""
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    token = body.get("token")
    if not isinstance(token, str) or not token:
        return JSONResponse({"error": "token must be a non-empty string"}, status_code=400)
    return JSONResponse({"value": _vault(org_id).detokenize(token)})
