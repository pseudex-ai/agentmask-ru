"""Obscura sidecar service — /mask + /unmask for a host gateway (e.g. the Diva
LiteLLM callback). We do NOT call the provider; the host does. We only transform
text + keep the per-org vault + audit. Runs in the customer's contour.

  POST /mask    {org_id, messages}      -> {messages}   (real -> tokens, audited)
  POST /unmask  {org_id, response}      -> {response}   (tokens -> real)
  GET  /usage?org_id=...                -> protected counts + recent (for UI)

Vault is keyed per org_id and persistent, so the host can run many workers/pods
and still share one consistent token map (the in-process approach can't).
Streaming chunk detok is phase 2 (needs per-stream carry state).
"""

import copy
import os
import threading
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from obscura.audit import AuditLog, _preview
from obscura.detect_all import Detector
from obscura.maskcache import MaskCache, content_key
from obscura.redact import mask_text, unmask_text
from obscura.vault import Vault

# Persistent vault + audit live under OBSCURA_DB_DIR (a mounted volume in
# production) so tokens stay reversible across restarts and workers.
_DB_DIR = os.environ.get("OBSCURA_DB_DIR", ".")
DETECTOR = Detector()
AUDIT = AuditLog(os.path.join(_DB_DIR, "audit.db"))
_VAULTS: dict[str, Vault] = {}

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


@asynccontextmanager
async def _lifespan(_app: "FastAPI"):
    # Warm the models in a thread so per-worker startup doesn't pin the loop, and
    # the first real /mask doesn't pay the multi-hundred-ms dictionary load.
    await anyio.to_thread.run_sync(_warmup)
    yield


app = FastAPI(title="Obscura sidecar", lifespan=_lifespan)

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


def _mask_one(text: str, vault: Vault, org_id: str, agent_id: str) -> str:
    """Mask one text. A content-keyed cache makes re-masking the SAME raw text
    (the O(n^2) growing-transcript case) an O(1) hit; the audit is recorded only
    on the cache MISS, so a value is counted once per unique (org, content), not
    once per resend.

    EVERY text goes through full detection — there is NO pre-filter skip. A
    pre-filter would have to stay a perfect superset of every recognizer's
    triggers forever; it silently failed that invariant (single Latin names and
    Latin-keyed KV like {"name":"john"} leaked raw to the model). In a
    fail-closed PII gateway that risk is unacceptable, and the cache already
    removes the repeated-work cost, so detection is never skipped."""
    def _compute() -> str:
        spans = DETECTOR.detect(text)
        for span in spans:
            token = vault.tokenize(span.value, span.entity_type)
            AUDIT.record(org_id, agent_id, span.entity_type, token, span.value)
        return mask_text(text, vault, spans)

    masked, _hit = _MASK_CACHE.get_or_compute(content_key(org_id, text), _compute)
    return masked


def _mask_messages(
    messages: list[dict[str, object]],
    vault: Vault,
    org_id: str,
    agent_id: str,
    skip_system: bool = False,
) -> list[dict[str, object]]:
    masked: list[dict[str, object]] = []
    for message in messages:
        new_message = dict(message)
        # `skip_system` is OPT-IN (the engine leg sets it): the agent's system
        # prompt is its own template, not user PII, and NER over tens of KB on
        # every call is the bulk of the cost + could corrupt instructions. The
        # PUBLIC /v1 leg does NOT skip — there the customer controls the system
        # message and may put PII in it, which MUST be masked (else it reaches
        # the provider raw, breaking the Protected-key promise).
        if skip_system and message.get("role") == "system":
            masked.append(new_message)
            continue
        content = new_message.get("content")
        if isinstance(content, str):
            new_message["content"] = _mask_one(content, vault, org_id, agent_id)
        elif isinstance(content, list):
            # Multi-part content (vision / content blocks): mask the text of
            # each text block; non-text blocks (image_url, input_audio, etc.)
            # pass through untouched. Without this, PII in a text block of a
            # multi-part message would reach the provider unmasked.
            new_blocks: list[object] = []
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    nb = dict(block)
                    nb["text"] = _mask_one(nb["text"], vault, org_id, agent_id)
                    new_blocks.append(nb)
                else:
                    new_blocks.append(block)
            new_message["content"] = new_blocks
        tool_calls = new_message.get("tool_calls")
        if isinstance(tool_calls, list):
            new_calls: list[object] = []
            for call in tool_calls:
                new_call = dict(call) if isinstance(call, dict) else call
                if isinstance(new_call, dict) and isinstance(new_call.get("function"), dict):
                    fn = dict(new_call["function"])
                    if isinstance(fn.get("arguments"), str):
                        fn["arguments"] = _mask_one(fn["arguments"], vault, org_id, agent_id)
                    new_call["function"] = fn
                new_calls.append(new_call)
            new_message["tool_calls"] = new_calls
        masked.append(new_message)
    return masked


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


def _unmask_response(response: dict[str, object], vault: Vault) -> dict[str, object]:
    result = copy.deepcopy(response)
    choices = result.get("choices")
    if not isinstance(choices, list):
        return result
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict):
            continue
        if isinstance(message.get("content"), str):
            message["content"] = unmask_text(message["content"], vault)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                fn = call.get("function") if isinstance(call, dict) else None
                if isinstance(fn, dict) and isinstance(fn.get("arguments"), str):
                    fn["arguments"] = unmask_text(fn["arguments"], vault)
    return result


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mask")
async def mask(request: Request) -> JSONResponse:
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    agent_id = str(body.get("agent_id", ""))
    messages = body.get("messages")
    if not isinstance(messages, list):
        return JSONResponse({"error": "messages must be a list"}, status_code=400)
    skip_system = bool(body.get("skip_system", False))
    # CPU-heavy morphology runs in a worker thread (NOT the event loop), so
    # /health and other requests stay responsive while a large /mask is in
    # flight. The capacity limiter applies backpressure: a burst beyond
    # OBSCURA_MASK_CONCURRENCY QUEUES on the limiter instead of thrashing every
    # core at once. FAIL-CLOSED is preserved: any exception in masking propagates
    # to a 5xx, which the caller treats as a block (it never sees raw PII).
    masked = await anyio.to_thread.run_sync(
        _mask_messages, messages, _vault(org_id), org_id, agent_id, skip_system,
        limiter=_MASK_LIMITER,
    )
    return JSONResponse({"messages": masked})


@app.post("/unmask")
async def unmask(request: Request) -> JSONResponse:
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    response = body.get("response")
    if not isinstance(response, dict):
        return JSONResponse({"error": "response must be an object"}, status_code=400)
    # Unmask scans every known token + a numeric reindex; offload so it never
    # blocks the loop (a vault with many tokens makes this non-trivial).
    result = await anyio.to_thread.run_sync(
        _unmask_response, response, _vault(org_id), limiter=_MASK_LIMITER
    )
    return JSONResponse({"response": result})


def _spans_for_texts(texts: list[object], vault: Vault) -> list[list[dict[str, object]]]:
    return [_spans_for(text, vault) if isinstance(text, str) else [] for text in texts]


@app.post("/spans")
async def spans(request: Request) -> JSONResponse:
    """PII spans per text for dialog highlighting (read-only).
    Body: {org_id, texts: [str]} -> {results: [[{start,end,type,token,preview}], ...]}."""
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    texts = body.get("texts")
    if not isinstance(texts, list):
        return JSONResponse({"error": "texts must be a list"}, status_code=400)
    # Detection runs morphology per text -> offload off the loop.
    results = await anyio.to_thread.run_sync(
        _spans_for_texts, texts, _vault(org_id), limiter=_MASK_LIMITER
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
