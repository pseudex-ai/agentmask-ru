"""OpenAI-compatible reverse proxy — multi-tenant, with streaming.

Drop-in: a customer points their agent's `base_url` at this server and uses an
Pseudex API key we issued (sk-ps-…). The key resolves to that customer's
upstream provider + key (we forward there) and their own token vault. Real PII is
masked before the model and restored on the way back, so tools get real values.

Dev: if PSEUDEX_UPSTREAM_BASE_URL/KEY are set, a tenant "pseudex-dev" is seeded.
"""

import hmac
import json
import logging
import os
import re
import sys
import secrets
import threading
import urllib.parse
from contextlib import asynccontextmanager

import anyio
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

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
from pseudex.profiling import snapshot as profiling_snapshot, stage
from pseudex.redact import StreamDetokenizer, surviving_substitutes
from pseudex.tenants import Tenant, Tenants
from pseudex.vault import PSEUDONYM_SCOPES, Vault, count_values_since

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("pseudex")

DETECTOR = Detector()
# Same volume convention as the sidecar. These used to be bare relative paths,
# which in a container put the tenant table and the audit log in the process's
# working directory instead of the mounted volume — every tenant key and every
# counter gone on restart, silently.
_DB_DIR = os.environ.get("PSEUDEX_DB_DIR", ".")
# The default scope for «is this string our own substitute?». The proxy has no
# per-request field for it — its wire is OpenAI's — so a tenant that turns agent
# memory on sets it for the process. `Vault.with_pseudonym_scope` states the trade.
_PSEUDONYM_SCOPE = os.environ.get("PSEUDEX_PSEUDONYM_SCOPE", "").strip() or "conversation"


def _own_values_from_env() -> tuple[str, ...]:
    """Значения хоста, объявленные процессом: имя ассистента, адрес компании.

    Разделитель — перевод строки или `;`: имя и адрес сами содержат запятые
    («Ленина 14, корп. 2»), и запятая как разделитель разрезала бы объявление
    пополам. Пусто по умолчанию — см. `Vault.with_own_values`.
    """
    raw = os.environ.get("PSEUDEX_OWN_VALUES", "")
    return tuple(part.strip() for part in raw.replace(";", "\n").split("\n") if part.strip())


_OWN_VALUES = _own_values_from_env()

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
# The operator surface is gated exactly as it is on the sidecar, and for the
# same reason: these screens disclose real values and the list of what exists to
# disclose. Kept in step with `service.py` deliberately — the two deployment
# shapes are parallel, so a customer must not get a weaker interface by choosing
# the proxy.
ADMIN_TOKEN = os.environ.get("PSEUDEX_ADMIN_TOKEN", "")
if not ADMIN_TOKEN:
    ADMIN_TOKEN = secrets.token_urlsafe(24)
    _log.warning("PSEUDEX_ADMIN_TOKEN was not set — generated a per-process one. "
                 "With more than one worker the operator interface will fail "
                 "intermittently. entrypoint.sh sets one for the container.")


# The masking surface uses the SAME credential in both entry points, because the
# local interface presents one token for it and cannot know which shape it is
# talking to. `/spans` was put behind the operator token here while the sidecar
# gates it on the gateway one, and the interface — which sends the gateway token
# for `/spans` — got a 401 that reads like a broken session rather than a wrong
# door. The sandbox was dead in proxy mode for exactly that reason.
GATEWAY_TOKEN = os.environ.get("PSEUDEX_GATEWAY_TOKEN", "")
if not GATEWAY_TOKEN:
    GATEWAY_TOKEN = secrets.token_urlsafe(24)
    _log.warning("PSEUDEX_GATEWAY_TOKEN was not set — generated a per-process one. "
                 "With more than one worker the gateway will be rejected at random. "
                 "entrypoint.sh sets it once for the container.")


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


def _require_gateway(request: Request) -> None:
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    if not presented or not _same_secret(presented, GATEWAY_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="gateway token required (Authorization: Bearer …)")


def _require_operator(request: Request) -> None:
    """`hmac.compare_digest`, not `==`: the comparison is against a secret, and
    a short-circuiting compare leaks its prefix through timing."""
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    if not presented or not _same_secret(presented, ADMIN_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="operator token required (Authorization: Bearer …)",
        )


_UPSTREAM_BASE = os.environ.get("PSEUDEX_UPSTREAM", "").rstrip("/")
_UPSTREAM_ORG = os.environ.get("PSEUDEX_ORG_ID", "default")

# The proxy is a deployment SHAPE, not a different product: it leases the same
# bundle, on the same terms, with the same ladder. Without this leg the licence
# would be trivially bypassable by choosing the other entry point.
LICENSE = LicenseClient(
    base_url=os.environ.get("PSEUDEX_LICENSE_URL", "https://license.pseudex.ru"),
    key=os.environ.get("PSEUDEX_LICENSE_KEY", ""),
    # STABLE PER DATA DIRECTORY, never random. A fresh id on every start makes
    # each restart look like a brand-new machine to the licensing server, which
    # holds the slot for 36 h — so on a one-instance plan a single `docker
    # restart` locks the customer out of their own product until tomorrow, with
    # no self-service way back. Two persona runs hit exactly this and both
    # called it disqualifying for production, where a restart happens on every
    # release. The sidecar has used `installation_id()` since the billing fix;
    # this line was the same bug, left behind in the shape we now recommend.
    instance_id=os.environ.get("PSEUDEX_INSTANCE_ID", "") or AUDIT.installation_id(),
    ca_path=os.environ.get("PSEUDEX_LICENSE_CA", ""),
    # PROTECTED VALUES, same as the sidecar. This leg reported only the audit
    # totals, so the field the landing page shows «дословно» — and the number the
    # pricing page tells customers to choose a plan by — was simply absent, and
    # the cabinet read «0 значений защищено» forever while requests climbed. All
    # three personas noticed; one had 900 protected values against a displayed
    # zero. The count comes from the VAULT, one row per distinct real value ever,
    # so it cannot move with cache size or worker count.
    usage_provider=lambda: {
        **AUDIT.billing_totals(),
        "values": count_values_since(os.path.join(_DB_DIR, "vault.db"), 0.0),
    },
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
        # Printed, not merely logged — this is the last thing the operator sees
        # before the container exits, and a structured log line scrolls past
        # inside a traceback. PROXY mode is what `docker run` hands out by
        # default, so this path is the one a customer actually meets; it was
        # added to the sidecar only, and a persona following the documented
        # command got the bare `[Errno -2] Name or service not known` with no
        # host named, no variable named, and nothing to try.
        print(f"\n{'=' * 72}\n  PSEUDEX НЕ ЗАПУСТИЛСЯ — {error.code}\n{'=' * 72}\n"
              f"  {error.detail}\n\n  {explain(error.code)}\n{'=' * 72}\n",
              file=sys.stderr, flush=True)
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


app = FastAPI(
    docs_url=None, redoc_url=None, openapi_url=None,title="Pseudex proxy", lifespan=_lifespan)

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


# The customer's own gateway names the agent; we cannot infer it. A header
# rather than a body field because the body is an OpenAI request and this leg
# forwards it: adding a key of ours to it would reach the provider, and some
# reject unknown fields outright.
AGENT_HEADER = "x-pseudex-agent"
_AGENT_SAFE = re.compile(r"[^\w .:@/-]", re.UNICODE)


def _agent_of(request: Request) -> str:
    """The agent label, or empty when the caller did not send one.

    PERCENT-DECODED FIRST. HTTP header values are latin-1, so «менеджер-заказов»
    cannot be put in one — an http client raises before the request is even sent,
    and the caller sees a UnicodeEncodeError from inside their own gateway rather
    than anything about us. On a Russian-market product the natural label is
    Russian, so the header carries it percent-encoded, which is what every client
    can produce and what this undoes.

    Bounded and stripped of anything that is not a plain label. It lands in the
    audit log, in a filter, and on a screen that renders values from customer
    traffic — an unbounded string from a header would be all three at once.
    """
    raw = (request.headers.get(AGENT_HEADER) or "").strip()
    if not raw:
        return ""
    # RAW UTF-8 IS REPAIRED, NOT ONLY PERCENT-ENCODING. Percent-decoding alone
    # assumed every caller would encode; an integrator sent
    # «X-Pseudex-Agent: поддержка» literally, and the header arrived as
    # «Ð¿Ð¾Ð´Ð´ÐµÑ€Ð¶ÐºÐ°» — 200 OK, no error, and mojibake in the journal the
    # customer's security officer is meant to read. HTTP header values are
    # latin-1 by the spec, so an ASGI server hands us the bytes decoded that
    # way; encoding them back and decoding as UTF-8 recovers the original.
    #
    # Tried in order and the first clean reading wins: a percent-encoded label
    # is unchanged by the latin-1 round trip, and an ASCII label is unchanged by
    # either, so neither can be damaged by trying both.
    try:
        repaired = raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = raw
    decoded = urllib.parse.unquote(repaired, encoding="utf-8", errors="replace")
    return _AGENT_SAFE.sub("", decoded)[:64]


def _context(customer_id: str, agent_id: str, conversation_id: str) -> MaskContext:
    """The Pseudex key identifies the CUSTOMER; the agent, if there is one, is
    named by the caller in `X-Pseudex-Agent`.

    It used to be hard-wired to the empty string here, and the interface offered
    a working-looking agent filter that could never return a row — which reads
    as «такого агента не было», not as «атрибуции нет».
    """
    return MaskContext(
        detector=DETECTOR,
        vault=(_get_vault(customer_id).for_conversation(conversation_id)
               .with_pseudonym_scope(_PSEUDONYM_SCOPE).with_own_values(_OWN_VALUES)),
        audit=AUDIT,
        cache=_MASK_CACHE,
        org_id=customer_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    )


def _mask_request(
    messages: list[dict[str, object]],
    tools: object,
    customer_id: str,
    agent_id: str,
) -> tuple[list[dict[str, object]], object]:
    """The PUBLIC leg never skips the template: here the customer writes the
    system prompt and the tool schemas, so PII in either MUST be masked or it
    reaches the provider raw.

    Resolves the vault HERE rather than taking a ready context, so the lazy
    SQLite open (which can wait out another worker's journal-mode switch) happens
    on the worker thread and not on the event loop — same reasoning as the
    sidecar leg."""
    # OpenAI's chat API carries no conversation id, so this leg always derives
    # one from the transcript — there is no caller field to prefer over it.
    context = _context(customer_id, agent_id, conversation_key(messages))
    # Billing is NOT done here. This helper is shared by the real request leg
    # (`/v1/chat/completions`) and the SANDBOX `/mask`, and the sandbox is «the
    # only way a security officer can verify masking works WITHOUT sending real
    # traffic» — billing it would charge the customer for proving the product
    # works, the same reason the sidecar excludes SELFCHECK_ORG. The real leg
    # bills at its own call site, after masking succeeds.
    return (
        mask_messages(messages, context, False),
        mask_tools(tools, context, False),
    )



def _upstream_failure(error: Exception, base_url: str) -> dict[str, object]:
    """The structured body for a provider we could not reach.

    THE ASYMMETRY THIS REMOVES. A licence failure gets a named code, the host it
    could not reach and a command to check it; a PROVIDER failure got an
    unhandled `httpx` exception — a bare 500 and a stack trace in the log. All
    three personas noticed the contrast, and it is the wrong way round: the
    licensing server is ours to keep up, the provider is not, so provider
    outages are the ones a customer will actually meet.

    502 and not 500: the request was fine and WE are fine — an upstream we
    depend on is not, and that is what the code means. A customer's own retry
    logic keys on it.

    The host is NAMED. «Не удалось связаться» without saying with whom leaves
    nothing to put in a firewall rule or a search box; that was the single most
    expensive finding of the persona run, on the licence side.
    """
    host = base_url.split("//", 1)[-1].split("/", 1)[0]
    return {
        "error": "upstream_unreachable",
        "detail": f"{type(error).__name__}: {error}",
        "upstream": {
            "host": host,
            "remedy": (
                "Проверьте, что из контейнера есть исходящий доступ к провайдеру:\n"
                f"    docker exec <контейнер> getent hosts {host}\n"
                "Чаще всего мешает закрытый исходящий трафик или корпоративный "
                "прокси. Адрес задан у ключа тенанта — см. issue_key.py."
            ),
        },
    }


async def _forward(body: dict[str, object], tenant: Tenant) -> dict[str, object]:
    url = f"{tenant.upstream_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {tenant.upstream_key}", "Content-Type": "application/json"}
    with stage("proxy.upstream_call"):
        try:
            response = await _upstream_client().post(url, json=body, headers=headers)
        except httpx.HTTPError as error:
            _log.warning("upstream unreachable: %s: %s", type(error).__name__, error)
            raise HTTPException(status_code=502,
                                detail=_upstream_failure(error, tenant.upstream_base_url)) from error
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
    # A STREAM CANNOT CHANGE ITS STATUS CODE once it has begun, so a provider
    # that dies mid-answer is reported as an SSE error EVENT and the stream is
    # closed. Letting the exception escape the generator hands the client a
    # TRUNCATED stream behind a 200 already sent — indistinguishable from a
    # short answer, which is the worst shape an error can take: the caller
    # cannot tell a finished reply from a dead connection.
    try:
        async with _upstream_client().stream("POST", url, json=body,
                                             headers=headers) as response:
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
                        delta["content"] = detok.setdefault(
                            index, StreamDetokenizer(vault)).feed(delta["content"])
                yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
    except httpx.HTTPError as error:
        _log.warning("upstream stream failed: %s: %s", type(error).__name__, error)
        # WHAT WAS HELD BACK IS FLUSHED FIRST. The carry buffer is holding the
        # tail of the answer the customer already paid for, and it may contain a
        # detokenised value — dropping it on the floor loses real text that had
        # nothing to do with the failure.
        for stream in detok.values():
            tail = stream.flush()
            if tail:
                yield _delta_chunk(tail)
        failure = _upstream_failure(error, tenant.upstream_base_url)
        yield f"data: {json.dumps({'error': failure}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


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
    """What the licence is doing right now — the ALARM endpoint, on this leg too.

    `/health` is liveness and answers 200 while serving; this one answers 503
    while the state is anything but LEASED. The sidecar's docstring carries the
    full argument for the split; what matters here is that both legs owe the
    same contract, and this one did not pay it: it answered 200 unconditionally,
    so a customer on the proxy leg who wired the documented alert got an alarm
    that could not fire — through grace and through expiry alike. The sidecar had
    the mirror-image defect (503 forever, comparing against a literal that is not
    the state's wire value), which is why neither leg's monitoring worked and why
    both are fixed together.
    """
    status = LICENSE.status()
    return JSONResponse({
        "state": status.state, "code": status.code, "lease_id": status.lease_id,
        "bundle_version": status.bundle_version, "last_error": status.last_error,
        "grace_left_s": (None if status.grace_left_seconds is None
                         else round(status.grace_left_seconds)),
    }, status_code=200 if status.state == STATE_LEASED else 503)


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
    recent events with masked previews). No full PII is stored or returned.

    A KNOWN PSEUDEX KEY, never the pass-through one. `_tenant` deliberately
    accepts an unrecognised key when an upstream is configured — on
    `/v1/chat/completions` that is right, because the key is the customer's own
    provider credential and the PROVIDER is the only party that can judge it.

    Here nothing is ever sent upstream, so nobody judges it, and any string at
    all returned the shared org's counters, its token list and its masked
    previews. The recommended command publishes this port on every interface
    (`-p 8000:8000`), so on a cloud host that was a feed of «what we protected
    today» readable by anyone who could reach it. This surface is the one
    `service.py` gates behind the admin credential for exactly that reason.
    """
    header = request.headers.get("authorization", "")
    presented = (header[7:] if header.lower().startswith("bearer ")
                 else header).strip()
    tenant = TENANTS.resolve(presented)
    if tenant is not None:
        customer = tenant.customer_id
    elif presented and hmac.compare_digest(presented.encode("utf-8"),
                                           GATEWAY_TOKEN.encode("utf-8")):
        # THE GATEWAY TOKEN OPENS IT TOO, and without this the endpoint was
        # unreachable in the shape the site recommends. `PSEUDEX_UPSTREAM` is the
        # default deployment — one container, one customer, no tenant table — so
        # there is no issued key for `resolve` to recognise and every credential
        # a customer holds answered 401. The quick start calls this check
        # mandatory and prints, in capitals, that empty counters mean traffic is
        # bypassing the container. Three of five personas ran it, got 401 on a
        # working product, and two said they would have stopped there.
        #
        # The gateway token and not the admin one, because this discloses exactly
        # what `/spans` does — counts and masked previews, never a value — and
        # `/spans` is gated the same way on this leg. It is printed by
        # `entrypoint.sh` at startup, so the customer has it without asking.
        customer = _UPSTREAM_ORG
    else:
        raise HTTPException(
            status_code=401,
            detail="use the gateway token printed at container startup, "
                   "or a Pseudex API key")
    return {
        "protected_counts": AUDIT.counts(customer, 0.0, ""),
        "recent": AUDIT.recent(customer, 50),
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
                "detail": "no valid detection lease" + f" (state={status.state})",
                "license": {"state": status.state, "last_error": status.last_error},
            },
        )
    with stage("proxy.tenant"):
        tenant = _tenant(request)
    with stage("proxy.parse_body"):
        body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise HTTPException(status_code=400, detail="missing messages array")
    # THE WAY BACK IS SCOPED TO THE SAME CONVERSATION AS THE WAY IN. The mask
    # leg keys everything a dialogue decides — a linked address, the
    # substitutes it was shown (`token_uses`, `shown_forms`) — under
    # `conversation_key(messages)`; the unmask leg used the bare customer
    # vault, so none of it was ever read back on this shape: a piece of a
    # substitute resolved against the customer's whole vault (Б23), a verbatim
    # copy could not be handed the customer's literal string (Б24). Same
    # derivation, same key, on both legs.
    #
    # AND AT THE SAME PSEUDONYM SCOPE. `_context` declares it on the way in; the
    # way back built a vault without it, so a customer running
    # `PSEUDEX_PSEUDONYM_SCOPE=customer` — an agent with memory — got
    # account-wide minting and conversation-scoped restoring. One setting, both
    # legs, or the setting is a promise only half kept.
    vault = (_get_vault(tenant.customer_id)
             .for_conversation(conversation_key(body["messages"]))
             .with_pseudonym_scope(_PSEUDONYM_SCOPE))

    # CPU-heavy morphology runs off the event loop under a capacity limiter, so a
    # burst QUEUES instead of thrashing every core. FAIL-CLOSED is preserved: any
    # exception propagates to a 5xx and nothing is forwarded upstream.
    masked_messages, masked_tools = await anyio.to_thread.run_sync(
        _mask_request, body["messages"], body.get("tools"), tenant.customer_id,
        _agent_of(request),
        limiter=_MASK_LIMITER,
    )
    # Billed HERE, on the real request leg, and only after masking succeeded (a
    # failure raised above and never reached a model — fail-closed). The sandbox
    # `/mask` shares `_mask_request` but not this call, so verifying the product
    # does not draw the customer's capacity. `record_request` was added on the
    # sidecar leg only, so before this every customer on THIS shape reported
    # {"requests": 0} and their plan limit was unenforceable.
    metering.bill(AUDIT, LICENSE, tenant.customer_id, _agent_of(request))
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
        # THE ANSWER IS OPENAI-SHAPED AND MUST STAY SO, so the residual signal
        # rides in a HEADER rather than in the body: the customer's SDK parses
        # this JSON, and an extra key is a field their client library did not
        # expect. A header is invisible to a parser and readable by anyone who
        # looks — which is exactly the audience for it.
        residual = _residual_in(upstream, restored, vault)
        headers = {"X-Pseudex-Residual": str(len(residual))} if residual else None
        return JSONResponse(restored, headers=headers)


def _residual_in(written: dict[str, object], restored: dict[str, object],
                 vault) -> list[str]:
    """Substitutes still standing in an answer that has already been restored.

    When the model reorders or shortens a fake, nothing resolves and the FAKE
    reaches the customer's tool — with a 200 and an empty log. Every persona in
    the 18.08 run asked for a way to see that from their own code.

    BOTH ANSWERS, PAIRED PART BY PART, exactly as the sidecar's `_residual_for`
    does and for the same reason: asked of the restored half alone the signal
    fires on a CORRECT restoration whenever a real value happens to look like
    one of our substitutes (`redact.surviving_substitutes`). Detokenization changes
    strings and never their number, so walking the two objects in step lines
    the pairs up by construction.
    """
    found: list[str] = []
    for choice_index, choice in enumerate(restored.get("choices", []) or []):
        message = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(message, dict):
            continue
        before_message = _message_at(written, choice_index)
        content = message.get("content")
        if isinstance(content, str):
            said = before_message.get("content")
            found.extend(surviving_substitutes(said if isinstance(said, str) else content,
                                         content, vault, False))
        before_calls = before_message.get("tool_calls") or []
        for call_index, call in enumerate(message.get("tool_calls", []) or []):
            arguments = (call.get("function") or {}).get("arguments") \
                if isinstance(call, dict) else None
            if not isinstance(arguments, str):
                continue
            before_call = before_calls[call_index] if call_index < len(before_calls) else {}
            asked = ((before_call.get("function") or {}).get("arguments")
                     if isinstance(before_call, dict) else None)
            # THE ARGUMENT LEG'S OWN WINDOWS. A lower-case street standing
            # alone in a schema field is the shape that leaks, and the
            # restoring side offers it only here (`_tool_windows`); a
            # signal that looked for less than the restorer did would go
            # quiet on exactly those.
            found.extend(surviving_substitutes(asked if isinstance(asked, str) else arguments,
                                         arguments, vault, True))
    return sorted(set(found))


def _message_at(response: dict[str, object], index: int) -> dict:
    """The message of one choice, or an empty one. The restored answer is built
    from the upstream answer key by key, so the same index names the same
    choice; an empty dict falls back to «the text is its own written form»,
    which is what the signal did before it had two texts to compare."""
    choices = response.get("choices", []) or []
    if index >= len(choices) or not isinstance(choices[index], dict):
        return {}
    message = choices[index].get("message")
    return message if isinstance(message, dict) else {}


async def _selfcheck(org_id: str, text: str) -> dict[str, object]:
    """The round trip on the REAL path — detect, mask, then detokenize what the
    mask produced. Anything less would let this pass while the product is
    broken, which is the one thing a self-check must never do."""
    return await anyio.to_thread.run_sync(_selfcheck_sync, org_id, text)


def _selfcheck_sync(org_id: str, text: str) -> dict[str, object]:
    from pseudex.envelope import mask_one
    from pseudex.redact import unmask_text

    context = _context(org_id, "самопроверка")
    detected = DETECTOR.detect(text)
    masked = mask_one(text, context)
    vault = _get_vault(org_id)
    spans = [
        {"start": span.start, "end": span.end, "type": span.entity_type,
         "value": span.value,
         "token": vault.peek_token(span.value, span.entity_type)}
        for span in detected
    ]
    restored = unmask_text(masked, vault)
    return {
        "ok": masked != text and restored == text and bool(spans),
        "original": text,
        "masked": masked,
        "restored": restored,
        "spans": spans,
    }


# The operator screens — status, journal, statistics, subscription, diagnostics,
# reveals. They existed only on the sidecar, so a customer following our own
# onboarding (which recommends `PSEUDEX_ROLE=proxy`) opened the local interface
# and every screen answered 404. Two persona clients hit that and both counted
# it against a feature they are billed for in every tariff.
# THE OPERATOR SURFACE NEEDS THESE, AND PROXY MODE DID NOT HAVE THEM.
#
# `docker run` hands out proxy mode by default, the landing points the customer's
# security officer at the local interface, and its two most-asked-for screens —
# the sandbox and revealing a value behind a token — called engine endpoints that
# only the sidecar had. A persona following the documented path clicked РАСКРЫТЬ
# and got «Не вышло: 404», then found /spans and /reveal missing by curl. Their
# words: "это ровно то, что попросит показать мой безопасник в первую очередь,
# и сейчас показать нечего".
#
# Implemented here rather than shared with `service.py` because the two entry
# points keep their own vault and audit wiring; what IS shared is the behaviour
# these must have — /spans stays read-only (no token minted, nothing audited)
# and /reveal still refuses without an actor and records the miss.
@app.post("/spans", dependencies=[Depends(_require_gateway)])
async def spans(request: Request) -> JSONResponse:
    """PII spans for dialog highlighting. Read-only: mints nothing, writes nothing."""
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    texts = body.get("texts")
    if not isinstance(texts, list):
        return JSONResponse({"error": "texts must be a list"}, status_code=400)
    results = await anyio.to_thread.run_sync(_spans_for_texts, texts, org_id)
    return JSONResponse({"results": results})


def _spans_for_texts(texts: list[object], org_id: str) -> list[list[dict[str, object]]]:
    vault = _get_vault(org_id)
    out: list[list[dict[str, object]]] = []
    for text in texts:
        if not isinstance(text, str):
            out.append([])
            continue
        out.append([{
            "start": span.start,
            "end": span.end,
            "type": span.entity_type,
            "token": vault.peek_token(span.value, span.entity_type),
            "preview": _preview(span.value),
        } for span in DETECTOR.detect(text)])
    return out


@app.post("/mask", dependencies=[Depends(_require_gateway)])
async def mask(request: Request) -> JSONResponse:
    """Mask a conversation. Present in proxy mode FOR THE SANDBOX.

    Masking on the request path happens inside `/v1/chat/completions` and needs
    no separate endpoint — which is why this one was absent, and why the local
    interface's sandbox was half dead here: «прогнать полностью» called it and
    got a 404.

    That matters more than it sounds. The sandbox is the only way a customer's
    security officer can satisfy themselves that masking works WITHOUT sending
    real traffic through it, and it is the first thing they ask to see. An
    endpoint that exists only in the other deployment shape makes the answer
    depend on which command the customer happened to copy.

    THE CONTRACT IS THE SIDECAR'S, VERBATIM — {messages: [...]} in, the same
    shape out. It was `{texts: [...]}` here, and the page, which is one page and
    cannot know which shape it is talking to, sent `messages` and got
    «400 texts must be a list». Adding a second accepted shape would have fixed
    the symptom and kept the cause: two endpoints with one name and two
    contracts. Same lesson as the token gate three comments up.
    """
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    agent_id = str(body.get("agent_id", "")) or "песочница"
    messages = body.get("messages")
    if not isinstance(messages, list):
        return JSONResponse({"error": "messages must be a list"}, status_code=400)
    tools = body.get("tools")
    masked_messages, masked_tools = await anyio.to_thread.run_sync(
        _mask_request, messages, tools, org_id, agent_id,
        limiter=_MASK_LIMITER,
    )
    payload: dict[str, object] = {"messages": masked_messages}
    if tools is not None:
        payload["tools"] = masked_tools
    return JSONResponse(payload)


@app.post("/reveal", dependencies=[Depends(_require_operator)])
async def reveal(request: Request) -> JSONResponse:
    """The real value behind a token. `actor` is REQUIRED and the access record
    is written BEFORE the value is returned — misses too, because a sweep of
    guessed tokens leaves no other trace. The record never holds the value."""
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
    value, entity_type = _get_vault(org_id).reveal(token)
    AUDIT.record_reveal(org_id, actor, token, entity_type, value is not None)
    return value


app.include_router(
    build_router(AUDIT, LICENSE, ASSETS, ENGINE_VERSION, _selfcheck),
    dependencies=[Depends(_require_operator)],
)
