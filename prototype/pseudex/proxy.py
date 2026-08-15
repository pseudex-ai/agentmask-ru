"""OpenAI-compatible reverse proxy — multi-tenant, with streaming.

Drop-in: a customer points their agent's `base_url` at this server and uses an
Pseudex API key we issued (sk-ps-…). The key resolves to that customer's
upstream provider + key (we forward there) and their own token vault. Real PII is
masked before the model and restored on the way back, so tools get real values.

Dev: if PSEUDEX_UPSTREAM_BASE_URL/KEY are set, a tenant "pseudex-dev" is seeded.
"""

import json
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager

import anyio
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from pseudex.assets import BundleNotLeased
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, mask_messages, mask_tools, unmask_response
from pseudex.license import LicenseClient, LicenseError
from pseudex.maskcache import MaskCache
from pseudex.profiling import snapshot as profiling_snapshot, stage
from pseudex.redact import StreamDetokenizer
from pseudex.tenants import Tenant, Tenants
from pseudex.vault import Vault

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("pseudex")

DETECTOR = Detector()
# Same volume convention as the sidecar. These used to be bare relative paths,
# which in a container put the tenant table and the audit log in the process's
# working directory instead of the mounted volume — every tenant key and every
# counter gone on restart, silently.
_DB_DIR = os.environ.get("PSEUDEX_DB_DIR", ".")
TENANTS = Tenants(os.path.join(_DB_DIR, "tenants.db"))
AUDIT = AuditLog(os.path.join(_DB_DIR, "audit.db"))
_VAULTS: dict[str, Vault] = {}

# PASS-THROUGH: the customer keeps their own provider key and we forward it
# untouched. Set PSEUDEX_UPSTREAM and the proxy needs no tenant table, no key
# minting, and never stores anyone else's credential — the customer changes one
# environment variable in their app and nothing else.
#
# This is the DEFAULT shape because the tariff is per container: one container
# is one customer, so a table mapping many keys to many upstreams buys nothing
# and costs an onboarding step. The tenant table still works when it is set up,
# for a host serving several organisations with different providers.
_UPSTREAM_BASE = os.environ.get("PSEUDEX_UPSTREAM", "").rstrip("/")
_UPSTREAM_ORG = os.environ.get("PSEUDEX_ORG_ID", "default")

# The proxy is a deployment SHAPE, not a different product: it leases the same
# bundle, on the same terms, with the same ladder. Without this leg the licence
# would be trivially bypassable by choosing the other entry point.
LICENSE = LicenseClient(
    base_url=os.environ.get("PSEUDEX_LICENSE_URL", "https://license.pseudex.ru"),
    key=os.environ.get("PSEUDEX_LICENSE_KEY", ""),
    instance_id=os.environ.get("PSEUDEX_INSTANCE_ID", "") or uuid.uuid4().hex[:12],
    ca_path=os.environ.get("PSEUDEX_LICENSE_CA", ""),
    usage_provider=lambda: AUDIT.billing_totals(),
)

# Same tuning knobs as the sidecar — this leg runs the identical morphology.
_MASK_CACHE = MaskCache(int(os.environ.get("PSEUDEX_MASK_CACHE_SIZE", "20000")))
_MASK_CONCURRENCY = int(os.environ.get("PSEUDEX_MASK_CONCURRENCY", "8"))

# Guards lazy creation of per-customer Vaults: without it two concurrent requests
# for the same customer could open two SQLite connections (two locks, one map).
_VAULTS_LOCK = threading.Lock()


def _warmup() -> None:
    """Pay the dictionary-load cost ONCE at startup so the first real request
    doesn't. pymorphy3's MorphAnalyzer + natasha's NER/AddrExtractor lazily load
    their dictionaries on first parse; a dummy detect() forces all of them."""
    DETECTOR.detect("Иван Петров, телефон +7 999 123-45-67, улица Ленина 5")


# ONE pooled client for the whole process, created on the running loop.
#
# It used to be `async with httpx.AsyncClient(...)` INSIDE the request handler,
# i.e. a fresh connection pool — and therefore a fresh TCP + TLS handshake — for
# every single upstream call. That is invisible at one request at a time and
# brutal under concurrency: against a real provider it produced 76 client-side
# timeouts in a 50-task agent benchmark, while the control arm (an SDK with a
# persistent pool) had none. Connection reuse is not an optimization here, it is
# the difference between working and not.
_UPSTREAM: httpx.AsyncClient | None = None


def _upstream_client() -> httpx.AsyncClient:
    if _UPSTREAM is None:
        raise RuntimeError("upstream client used before startup")
    return _UPSTREAM


@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    global _UPSTREAM
    base_url = os.environ.get("PSEUDEX_UPSTREAM_BASE_URL")
    key = os.environ.get("PSEUDEX_UPSTREAM_KEY")
    if base_url is not None and key is not None:
        TENANTS.upsert("pseudex-dev", "demo", base_url, key)
    _UPSTREAM = httpx.AsyncClient(
        timeout=httpx.Timeout(300.0, connect=10.0),
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
    )
    # Lease before warming: the warmup runs a real detection pass, which needs
    # the leased assets. Raising here aborts startup with a non-zero exit.
    try:
        await anyio.to_thread.run_sync(_acquire_license)
    except LicenseError as error:
        _log.error("refusing to start — %s: %s", error.code, error.detail)
        await _UPSTREAM.aclose()
        _UPSTREAM = None
        raise
    await anyio.to_thread.run_sync(_warmup)
    try:
        yield
    finally:
        LICENSE.stop()
        await _UPSTREAM.aclose()
        _UPSTREAM = None


def _acquire_license() -> None:
    if not os.environ.get("PSEUDEX_LICENSE_KEY"):
        raise LicenseError("license_missing", "PSEUDEX_LICENSE_KEY is not set")
    LICENSE.acquire()
    LICENSE.start()


app = FastAPI(title="Pseudex proxy", lifespan=_lifespan)

# Bounded semaphore created on the running loop (anyio limiter is loop-bound).
_MASK_LIMITER = anyio.CapacityLimiter(_MASK_CONCURRENCY)


def _get_vault(customer_id: str) -> Vault:
    vault = _VAULTS.get(customer_id)
    if vault is not None:
        return vault
    with _VAULTS_LOCK:
        vault = _VAULTS.get(customer_id)
        if vault is None:
            vault = Vault(os.path.join(_DB_DIR, "vault.db"), customer_id)
            _VAULTS[customer_id] = vault
        return vault


def _tenant(request: Request) -> Tenant:
    header = request.headers.get("authorization", "")
    presented = (header[7:] if header.lower().startswith("bearer ") else header).strip()
    tenant = TENANTS.resolve(presented)
    if tenant is not None:
        return tenant
    if _UPSTREAM_BASE:
        # The presented key is the CUSTOMER'S OWN provider key. It is forwarded
        # upstream verbatim and never written down: the provider decides whether
        # it is valid, which is the only party that can. An empty one is still
        # refused here rather than sent on, so the failure names itself instead
        # of arriving as someone else's 401.
        if not presented:
            raise HTTPException(status_code=401, detail="missing Authorization header")
        return Tenant(customer_id=_UPSTREAM_ORG,
                      upstream_base_url=_UPSTREAM_BASE,
                      upstream_key=presented)
    raise HTTPException(status_code=401, detail="invalid Pseudex API key")


def _context(customer_id: str) -> MaskContext:
    """This leg has no per-agent attribution — the Pseudex key identifies the
    customer, and everything under it is one audit scope."""
    return MaskContext(
        detector=DETECTOR,
        vault=_get_vault(customer_id),
        audit=AUDIT,
        cache=_MASK_CACHE,
        org_id=customer_id,
        agent_id="",
    )


def _mask_request(
    messages: list[dict[str, object]],
    tools: object,
    customer_id: str,
) -> tuple[list[dict[str, object]], object]:
    """The PUBLIC leg never skips the template: here the customer writes the
    system prompt and the tool schemas, so PII in either MUST be masked or it
    reaches the provider raw.

    Resolves the vault HERE rather than taking a ready context, so the lazy
    SQLite open (which can wait out another worker's journal-mode switch) happens
    on the worker thread and not on the event loop — same reasoning as the
    sidecar leg."""
    context = _context(customer_id)
    result = (
        mask_messages(messages, context, False),
        mask_tools(tools, context, False),
    )
    # Counted here too, and it was not. `record_request` was added on the
    # sidecar leg only, so every customer on THIS deployment shape reported
    # {"requests": 0} forever: their plan limit was unenforceable and the
    # cabinet's usage bar sat at zero. It is a regression rather than an
    # omission — before the counter existed, `billing_totals` returned
    # sum(entities), which this path did populate.
    #
    # After masking succeeds, never before: masking is fail-closed, so a request
    # that raised was blocked and never reached a model.
    AUDIT.record_request(customer_id, "")
    return result


async def _forward(body: dict[str, object], tenant: Tenant) -> dict[str, object]:
    url = f"{tenant.upstream_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {tenant.upstream_key}", "Content-Type": "application/json"}
    with stage("proxy.upstream_call"):
        response = await _upstream_client().post(url, json=body, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"upstream error: {response.text}")
    payload = response.json()
    _record_prefix_cache(payload)
    return payload


# Providers that cache prompt prefixes (DeepSeek, Anthropic, OpenAI) only hit the
# cache on a byte-identical prefix. Masking sits directly on that prefix, so a
# masker that is not perfectly deterministic silently destroys the customer's
# cache and multiplies their input cost — on DeepSeek v4-flash, cache-miss input
# is 50x the cache-hit price. That makes this a CORRECTNESS signal, not a nicety:
# a falling hit rate means tokens are not stable across turns.
_PREFIX_CACHE = {"hit_tokens": 0, "miss_tokens": 0, "responses": 0}
_PREFIX_CACHE_LOCK = threading.Lock()


def _record_prefix_cache(payload: dict[str, object]) -> None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return
    hit = usage.get("prompt_cache_hit_tokens")
    miss = usage.get("prompt_cache_miss_tokens")
    if not isinstance(hit, int) or not isinstance(miss, int):
        return  # provider does not report prefix-cache accounting
    with _PREFIX_CACHE_LOCK:
        _PREFIX_CACHE["hit_tokens"] += hit
        _PREFIX_CACHE["miss_tokens"] += miss
        _PREFIX_CACHE["responses"] += 1


async def _stream_content(body: dict[str, object], tenant: Tenant, vault: Vault):
    """True token-by-token streaming for plain chat (content carry-buffer detok)."""
    url = f"{tenant.upstream_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {tenant.upstream_key}", "Content-Type": "application/json"}
    detok: dict[int, StreamDetokenizer] = {}
    async with _upstream_client().stream("POST", url, json=body, headers=headers) as response:
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                for stream in detok.values():
                    tail = stream.flush()
                    if tail:
                        yield _delta_chunk(tail)
                yield "data: [DONE]\n\n"
                return
            obj = json.loads(payload)
            for choice in obj.get("choices", []):
                index = choice.get("index", 0)
                delta = choice.get("delta", {})
                if isinstance(delta.get("content"), str):
                    delta["content"] = detok.setdefault(index, StreamDetokenizer(vault)).feed(delta["content"])
            yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _delta_chunk(content: str) -> str:
    chunk = {"object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


async def _stream_as_single(body: dict[str, object], tenant: Tenant, vault: Vault):
    """Tool-call requests: do it non-streamed (correct arg detok), emit as one SSE
    chunk. Token-by-token detok of streamed tool args can't retract an already-sent
    fake prefix, so we buffer — correctness over smoothness."""
    body = dict(body)
    body["stream"] = False
    unmasked = unmask_response(await _forward(body, tenant), vault)
    for choice in unmasked.get("choices", []):
        message = choice.get("message", {})
        delta = {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
        chunk = {"id": unmasked.get("id"), "object": "chat.completion.chunk",
                 "model": unmasked.get("model"),
                 "choices": [{"index": choice.get("index", 0), "delta": delta,
                              "finish_reason": choice.get("finish_reason")}]}
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/health")
async def health() -> JSONResponse:
    status = LICENSE.status()
    body: dict[str, object] = {
        "status": "ok" if LICENSE.is_serving() else "degraded",
        "license": status.state,
        "pid": os.getpid(),
    }
    if status.grace_left_seconds is not None and status.state == "stale":
        body["grace_left_s"] = round(status.grace_left_seconds)
    return JSONResponse(body, status_code=200 if LICENSE.is_serving() else 503)


@app.get("/license")
async def license_status() -> JSONResponse:
    status = LICENSE.status()
    return JSONResponse({
        "state": status.state, "code": status.code, "lease_id": status.lease_id,
        "bundle_version": status.bundle_version, "last_error": status.last_error,
        "grace_left_s": (None if status.grace_left_seconds is None
                         else round(status.grace_left_seconds)),
    })


@app.exception_handler(BundleNotLeased)
async def _bundle_not_leased(_request: Request, error: BundleNotLeased) -> JSONResponse:
    """Fail-closed on the race the licence check cannot cover: the renewal thread
    can unload the assets between the check and the masking pass."""
    return JSONResponse(
        {"error": "bundle_unavailable", "detail": str(error),
         "license": {"state": LICENSE.state()}},
        status_code=503,
    )


@app.get("/profile")
async def profile() -> dict[str, object]:
    """Per-stage timings for this leg. Empty unless PSEUDEX_PROFILE=1. The proxy
    needs this as much as the sidecar: it carries the same masking work plus the
    upstream call, so a stall here has to be attributable without guesswork."""
    snapshot = profiling_snapshot()
    with _PREFIX_CACHE_LOCK:
        cache = dict(_PREFIX_CACHE)
    total = cache["hit_tokens"] + cache["miss_tokens"]
    cache["hit_rate"] = round(cache["hit_tokens"] / total, 4) if total else None
    snapshot["upstream_prefix_cache"] = cache
    return snapshot


@app.get("/usage")
async def usage(request: Request) -> dict[str, object]:
    """For the future UI: what PII we protected for this customer (counts +
    recent events with masked previews). No full PII is stored or returned."""
    tenant = _tenant(request)
    return {
        "protected_counts": AUDIT.counts(tenant.customer_id, 0.0),
        "recent": AUDIT.recent(tenant.customer_id, 50),
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Everything on this path is staged, not just the masking: a stall here was
    # once narrowed only by an external sampler because these steps were blind
    # spots. Body parse and serialization are pure CPU and grow with the
    # transcript; the upstream call is I/O and should dominate wall time.
    if not LICENSE.is_serving():
        status = LICENSE.status()
        raise HTTPException(
            status_code=503,
            detail={
                "error": status.code or "license_expired",
                "detail": f"no valid detection lease (state={status.state})",
                "license": {"state": status.state, "last_error": status.last_error},
            },
        )
    with stage("proxy.tenant"):
        tenant = _tenant(request)
    vault = _get_vault(tenant.customer_id)
    with stage("proxy.parse_body"):
        body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise HTTPException(status_code=400, detail="missing messages array")

    # CPU-heavy morphology runs off the event loop under a capacity limiter, so a
    # burst QUEUES instead of thrashing every core. FAIL-CLOSED is preserved: any
    # exception propagates to a 5xx and nothing is forwarded upstream.
    masked_messages, masked_tools = await anyio.to_thread.run_sync(
        _mask_request, body["messages"], body.get("tools"), tenant.customer_id,
        limiter=_MASK_LIMITER,
    )
    masked_body = dict(body)
    masked_body["messages"] = masked_messages
    if body.get("tools") is not None:
        masked_body["tools"] = masked_tools
    # This log is the leak-evidence trail — it is what proves no real PII crossed
    # the wire. It re-formats the WHOLE transcript on every call, so it grows
    # quadratically over a long agent turn; staged to keep that visible.
    with stage("proxy.log_upstream"):
        for message in masked_body["messages"]:
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                _log.info("upstream role=%s content=%s", message.get("role"), message["content"])

    if body.get("stream") is True:
        streamer = _stream_as_single if body.get("tools") else _stream_content
        return StreamingResponse(streamer(masked_body, tenant, vault), media_type="text/event-stream")

    upstream = await _forward(masked_body, tenant)
    with stage("proxy.unmask_response"):
        restored = unmask_response(upstream, vault)
    with stage("proxy.serialize"):
        return JSONResponse(restored)
