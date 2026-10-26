"""A deterministic local provider fixture, never a relay to client systems.

The live provider is deliberately unavailable until a separately verified budget
ledger can reserve its worst-case cost. Merely mounting corporate credentials
must not turn an integration test into a paid call. The one exception is the
read-only metadata GET behind ``/v1/pilot/upstream-check``: it returns no model
text and creates no reservation, so it can prove the transport path is alive
BEFORE a dead path strands budget.
"""

import json
import os
from pathlib import Path
import re
import secrets
import time
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from budget import BudgetRefused, Ledger, load_pricing, quote

# The only external route this process may take. Both are literals: a client
# never supplies a URL, a redirect target or a proxy.
UPSTREAM_BASE = os.environ.get('PILOT_UPSTREAM_BASE', 'https://litellm.inf.2up.dev').rstrip('/')
UPSTREAM_COMPLETIONS = UPSTREAM_BASE + "/v1/chat/completions"
UPSTREAM_MODEL_INFO = UPSTREAM_BASE + "/v1/model/info"
DIRECT = UPSTREAM_BASE != "https://litellm.inf.2up.dev"

# httpcore bills the TLS handshake to the CONNECT budget, not to read. A path
# that answers SYN and then never answers ClientHello therefore surfaces as
# httpx.ConnectTimeout at the connect deadline, which is why a dead upstream used
# to take the full 120 s. Measured here: TCP connect 6 ms, TLS never completes,
# TCP/TLS on every other host succeeds. 10 s is ~1600x the healthy handshake and
# keeping 120 s only lengthened the hang. Do not raise it to hide a dead path.
READ_DEADLINE_SECONDS = 300.0     # a long buffered generation; caller waits 360
CONNECT_DEADLINE_SECONDS = 10.0   # TCP + TLS, both local-network fast
WRITE_DEADLINE_SECONDS = 30.0     # a large masked transcript, not a stall
POOL_DEADLINE_SECONDS = 10.0      # one in-flight request per bridge step

# The pre-flight is a metadata GET, not a generation: it has diagnostic value
# only if it answers long before the caller gives up.
PROBE_READ_DEADLINE_SECONDS = 20.0
PROBE_CONNECT_DEADLINE_SECONDS = 5.0

# Bind-mounted from the host, so it survives the finally-disable recreation of
# this container -- which is when the evidence would otherwise be thrown away.
DIAGNOSTIC_DIRECTORY = Path("/pilot-ledger")


# A FRESH TLS HANDSHAKE PER REQUEST IS THE FAILURE SURFACE ON THIS PATH. The
# corporate endpoint accepts TCP and then sometimes never answers ClientHello
# (measured: ConnectTimeout at exactly the connect budget, from host and from
# this container). One warm keep-alive pool means a handshake that succeeded
# once serves the later requests of the same run instead of being re-rolled.
_UPSTREAM_CLIENT: "httpx.AsyncClient | None" = None


def _upstream_client(timeout: httpx.Timeout) -> httpx.AsyncClient:
    global _UPSTREAM_CLIENT
    # A substituted transport (tests) is never cached: only a real client is,
    # so patching httpx.AsyncClient keeps working and no stale session leaks
    # from one run into the next.
    cached = _UPSTREAM_CLIENT
    if type(cached) is not httpx.AsyncClient:
        cached = None
    if cached is None or getattr(cached, "is_closed", True):
        _UPSTREAM_CLIENT = httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=8, keepalive_expiry=600))
    return _UPSTREAM_CLIENT


async def _post_with_warm_connection(headers: dict, payload: dict, timeout: httpx.Timeout) -> httpx.Response:
    """Send on the SHARED warm connection; never re-send an unobserved call.

    A retry is deliberately absent: even in the connect phase this code cannot
    prove the upstream never received anything, so the paid attempt stays a
    single, held, delivery-unknown reservation. What reuse buys is fewer
    handshakes (the phase this path fails in), not a second attempt.
    """
    attempt = 0
    while True:
        try:
            return await _upstream_client(timeout).post(UPSTREAM_COMPLETIONS, headers=headers, json=payload)
        except httpx.ConnectTimeout:
            # A stalled TLS handshake is the ONE failure that provably never
            # delivered the request: TCP/TLS complete before any HTTP byte
            # leaves the client. Reconnecting once is therefore not a second
            # paid call; every other error stays a single, held attempt.
            attempt += 1
            if attempt > 1:
                raise
            global _UPSTREAM_CLIENT
            _UPSTREAM_CLIENT = None


app = FastAPI(title="DoubleUp pilot deterministic model fixture", version="1")


@app.get("/health")
async def health() -> dict[str, str]:
    mode = os.environ.get("PILOT_GATEWAY_MODE", "fixture")
    return {"status": "ok", "mode": mode,
            "paid_calls": "budgeted" if mode == "live" else "disabled"}


def _live_config() -> dict:
    path = Path("/run/live-gateway.json")
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise BudgetRefused("live_credentials_not_private")
    config = json.loads(path.read_text())
    if config.get("enabled") is not True:
        raise BudgetRefused("live_not_enabled")
    if not all(isinstance(config.get(key), str) and len(config[key]) >= 20
               for key in ("request_key", "upstream_key")):
        raise BudgetRefused("live_credentials_missing")
    return config


def safe_error_type(error_type: object) -> str:
    """A class name is the whole diagnosis; a message can carry private text."""
    return re.sub(r"[^A-Za-z0-9_]", "", str(error_type))[:64] or "UnknownError"


def diagnostic_path(identifier: str, directory, attempt: int = 0) -> Path:
    """A name derived from the budget id, never from operator or client input.

    O_EXCL needs a deterministic name, so a collision is resolved by suffixing
    instead of overwriting. The identifier is reduced to a filename alphabet so a
    literal ``../`` cannot walk out of the diagnostic directory.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(identifier))[:64] or "unknown"
    suffix = "" if attempt == 0 else "-%d" % attempt
    return Path(directory) / ("transport-" + safe + suffix + ".json")


def record_transport_failure(identifier: str, error_type: str, elapsed_seconds: float,
                             *, transition: str = "delivery_unknown",
                             directory=None) -> dict:
    """Write one sanitized transport diagnostic that outlives this container.

    Fields are class/timing/id only: never exception text, headers, URL params or
    key material. The write is best-effort ON PURPOSE -- a failing diagnostic
    must not replace the classified 502 with an unhandled 500 and must not lose
    the fact that the reservation is still held, so this returns the record even
    when no byte reached the disk.
    """
    try:
        elapsed = round(float(elapsed_seconds), 3)
    except (TypeError, ValueError):
        elapsed = -1.0
    diagnostic = {
        "event": "pilot_upstream_transport_error",
        "error_type": safe_error_type(error_type),
        "elapsed_seconds": elapsed,
        "budget_id": str(identifier),
        "reservation": str(transition),
    }
    payload = json.dumps(diagnostic, sort_keys=True)
    target_directory = DIAGNOSTIC_DIRECTORY if directory is None else directory
    for attempt in range(100):
        try:
            descriptor = os.open(diagnostic_path(identifier, target_directory, attempt),
                                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            continue
        except OSError:
            break
        try:
            with os.fdopen(descriptor, "w") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            pass
        break
    print(payload, flush=True)
    return diagnostic


async def _live(request: Request, body: dict) -> JSONResponse:
    try:
        config = _live_config()
        presented = request.headers.get("authorization", "")
        if not secrets.compare_digest(presented, "Bearer " + config["request_key"]):
            raise HTTPException(401, detail="live_auth_required")
        if body.get("model") != config.get("model"):
            raise HTTPException(400, detail="live_model_not_approved")
        pricing = load_pricing(Path("/pilot-pricing.json"))
        estimate = quote(body, pricing)
        ledger = Ledger(Path("/pilot-ledger/spend.sqlite3"))
        identifier = ledger.reserve(estimate)
    except BudgetRefused as error:
        raise HTTPException(429, detail=str(error)) from None
    # The only external route is this literal endpoint. Never forward arbitrary
    # client Authorization, URLs, cookies, sidecar credentials or redirect targets.
    headers = {"Content-Type": "application/json"}
    headers["Authorization" if DIRECT else "x-litellm-api-key"] = ("Bearer " + config["upstream_key"]) if DIRECT else config["upstream_key"]
    for name in ("x-litellm-spend-logs-metadata", "x-request-id", "traceparent"):
        value = request.headers.get(name)
        if value:
            headers[name] = value
    started = time.monotonic()
    try:
        timeout = httpx.Timeout(READ_DEADLINE_SECONDS, connect=CONNECT_DEADLINE_SECONDS,
                                write=WRITE_DEADLINE_SECONDS, pool=POOL_DEADLINE_SECONDS)
        # LiteLLM's documented per-request flag avoids duplicating original
        # client text into shared telemetry. The gateway may centrally disable
        # this flag; request it explicitly, never claim global enforcement.
        remote_body = {**body, "no-log": True}
        response = await _post_with_warm_connection(headers, remote_body, timeout)
    except httpx.HTTPError as error:
        elapsed = round(time.monotonic() - started, 3)
        # The reservation is retained either way: a delivery we could not observe
        # is never refunded and never re-sent. If the transition itself fails the
        # row simply stays 'reserved', which is still accounted for, so a ledger
        # hiccup must not silence the classification.
        transition = "delivery_unknown"
        try:
            ledger.unknown(identifier)
        except BudgetRefused:
            transition = "reservation_unchanged"
        diagnostic = record_transport_failure(identifier, type(error).__name__, elapsed,
                                              transition=transition)
        raise HTTPException(502, detail="live_delivery_unknown_reservation_retained", headers={
            'Cache-Control': 'no-store', 'X-Pilot-Budget-Id': diagnostic["budget_id"],
            'X-Pilot-Transport-Error': diagnostic["error_type"],
            'X-Pilot-Elapsed-Seconds': str(diagnostic["elapsed_seconds"]),
            'X-Pilot-Reservation': diagnostic["reservation"]}) from None
    try:
        result = response.json()
    except ValueError:
        ledger.unknown(identifier)
        raise HTTPException(502, detail="live_response_invalid_reservation_retained") from None
    try:
        ledger.settle(identifier, result if isinstance(result, dict) else {})
    except BudgetRefused as error:
        raise HTTPException(503, detail=str(error)) from None
    return JSONResponse(result, status_code=response.status_code,
                        headers={"X-Pilot-Budget-Id": identifier, "Cache-Control": "no-store"})


@app.get("/v1/pilot/upstream-check")
async def upstream_check(request: Request) -> JSONResponse:
    """Prove the fixed upstream can complete TLS, without reserving or spending.

    A GET of the documented metadata route returns no model text and costs
    nothing, so it may run before any reservation exists. That ordering is the
    point: on a dead path every arm otherwise creates a reservation, marks it
    delivery_unknown, and holds it for ever. Refuses in fixture mode, where a
    corporate credential must never be used at all.

    Fail closed: 200 means the path answered with a healthy metadata response and
    a run may proceed. 503 always carries the reason -- ``transport_ok=false`` is
    a dead path (error_type names the phase), ``transport_ok=true`` with a
    non-2xx ``http_status`` means TLS works but the route or credential refused,
    which is still not a reason to spend.
    """
    if os.environ.get("PILOT_GATEWAY_MODE", "fixture") != "live":
        raise HTTPException(409, detail="live_mode_required")
    try:
        config = _live_config()
    except BudgetRefused as error:
        raise HTTPException(429, detail=str(error)) from None
    presented = request.headers.get("authorization", "")
    if not secrets.compare_digest(presented, "Bearer " + config["request_key"]):
        raise HTTPException(401, detail="live_auth_required")
    started = time.monotonic()
    timeout = httpx.Timeout(PROBE_READ_DEADLINE_SECONDS, connect=PROBE_CONNECT_DEADLINE_SECONDS,
                            write=PROBE_READ_DEADLINE_SECONDS, pool=PROBE_CONNECT_DEADLINE_SECONDS)
    try:
        probe_headers = ({"Authorization": "Bearer " + config["upstream_key"]} if DIRECT
                         else {"x-litellm-api-key": config["upstream_key"]})
        response = await _upstream_client(timeout).get(UPSTREAM_MODEL_INFO, headers=probe_headers)
    except httpx.HTTPError as error:
        # Same rule as the relay: the class and the clock, never the message.
        return JSONResponse({"transport_ok": False, "http_status": None,
            "error_type": safe_error_type(type(error).__name__),
            "elapsed_seconds": round(time.monotonic() - started, 3)},
            status_code=503, headers={"Cache-Control": "no-store"})
    healthy = 200 <= response.status_code < 300
    return JSONResponse({"transport_ok": True, "http_status": response.status_code,
        "error_type": None, "elapsed_seconds": round(time.monotonic() - started, 3)},
        status_code=200 if healthy else 503, headers={"Cache-Control": "no-store"})


@app.get("/v1/models")
async def models() -> dict:
    return {"object": "list", "data": [{"id": "pilot-fixture", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    mode = os.environ.get("PILOT_GATEWAY_MODE", "fixture")
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, detail="request_object_required")
    if mode == "live":
        return await _live(request, body)
    if mode != "fixture":
        raise HTTPException(503, detail="unknown_gateway_mode")
    if body.get("stream"):
        raise HTTPException(400, detail="fixture_stream_not_supported")
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(400, detail="messages_required")
    if request.headers.get("x-pilot-tool-loop-fixture") == "1":
        declared = {tool.get('function', {}).get('name') for tool in body.get('tools', [])}
        if 'run_code' not in declared:
            raise HTTPException(400, detail='fixture_run_code_schema_required')
        if messages[-1].get('role') == 'tool':
            reply = {'role': 'assistant', 'content': 'Локальный Python действительно вернул результат.'}
            finish = 'stop'
        else:
            reply = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_' + uuid.uuid4().hex,
                'type': 'function', 'function': {'name': 'run_code',
                'arguments': json.dumps({'code': 'print(2 + 3)', 'title': 'Local protocol fixture'})}}]}
            finish = 'tool_calls'
        return {'id': 'chatcmpl-local-tool-' + uuid.uuid4().hex, 'object': 'chat.completion', 'created': 0,
            'model': body.get('model'), 'choices': [{'index': 0, 'message': reply, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
    # This fixture tests exact copying and transport, not an agent's intelligence.
    # The schema declares the argument. Never guess a real tool's signature.
    choice = body.get("tool_choice")
    tool_name = (choice.get("function", {}).get("name")
                 if isinstance(choice, dict) else None)
    tools = body.get("tools") or []
    four_hop = next((tool for tool in tools if tool.get("function", {}).get("name") == "pseudex_pilot_contact"), None)
    last_user_index = max((i for i, message in enumerate(messages) if message.get("role") == "user"), default=-1)
    tool_result = next((message for i, message in reversed(list(enumerate(messages))) if i > last_user_index and message.get("role") == "tool"), None)
    if not tool_name and four_hop and tool_result:
        try:
            result = json.loads(tool_result["content"])
            final = chr(10).join((f"Контакт инструмента: **{result['tool_contact']}**.", result['received_text'], f"Почта инструмента: {result['tool_email']}"))
        except (ValueError, TypeError, KeyError):
            raise HTTPException(400, detail="four_hop_fixture_result_malformed") from None
        return {"id": "chatcmpl-pilot-" + uuid.uuid4().hex, "object": "chat.completion", "created": 0,
            "model": body.get("model", "pilot-fixture"), "choices": [{"index": 0,
            "message": {"role": "assistant", "content": final}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    if not tool_name and four_hop:
        tool_name = "pseudex_pilot_contact"
    if tool_name:
        selected = next((t for t in tools if t.get("function", {}).get("name") == tool_name), None)
        if selected is None:
            raise HTTPException(400, detail="fixture_tool_not_declared")
        fields = (selected.get("function", {}).get("parameters") or {}).get("properties") or {}
        if list(fields) != ["text"]:
            raise HTTPException(400, detail="fixture_requires_single_text_argument")
        user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        text = user.get("content")
        if not isinstance(text, str):
            raise HTTPException(400, detail="fixture_requires_text")
        message = {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_" + uuid.uuid4().hex, "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps({"text": text}, ensure_ascii=False)},
        }]}
        finish = "tool_calls"
    else:
        message = {"role": "assistant", "content": "Локальная проверка завершена."}
        finish = "stop"
    return {
        "id": "chatcmpl-pilot-" + uuid.uuid4().hex, "object": "chat.completion",
        "created": 0, "model": body.get("model", "pilot-fixture"),
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
