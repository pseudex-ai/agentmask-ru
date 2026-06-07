"""OpenAI-compatible reverse proxy — multi-tenant, with streaming.

Drop-in: a customer points their agent's `base_url` at this server and uses an
Obscura API key we issued (sk-obsc-…). The key resolves to that customer's
upstream provider + key (we forward there) and their own token vault. Real PII is
masked before the model and restored on the way back, so tools get real values.

Dev: if OBSCURA_UPSTREAM_BASE_URL/KEY are set, a tenant "obscura-dev" is seeded.
"""

import copy
import json
import logging
import os

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from obscura.audit import AuditLog
from obscura.detect_all import Detector
from obscura.redact import StreamDetokenizer, mask_text, unmask_text
from obscura.tenants import Tenant, Tenants
from obscura.vault import Vault

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("obscura")

DETECTOR = Detector()
TENANTS = Tenants("tenants.db")
AUDIT = AuditLog("audit.db")
_VAULTS: dict[str, Vault] = {}

app = FastAPI(title="Obscura proxy")


@app.on_event("startup")
def _seed_dev_tenant() -> None:
    base_url = os.environ.get("OBSCURA_UPSTREAM_BASE_URL")
    key = os.environ.get("OBSCURA_UPSTREAM_KEY")
    if base_url is not None and key is not None:
        TENANTS.upsert("obscura-dev", "demo", base_url, key)


def _get_vault(customer_id: str) -> Vault:
    vault = _VAULTS.get(customer_id)
    if vault is None:
        vault = Vault("vault.db", customer_id)
        _VAULTS[customer_id] = vault
    return vault


def _tenant(request: Request) -> Tenant:
    header = request.headers.get("authorization", "")
    obscura_key = header[7:] if header.lower().startswith("bearer ") else header
    tenant = TENANTS.resolve(obscura_key.strip())
    if tenant is None:
        raise HTTPException(status_code=401, detail="invalid Obscura API key")
    return tenant


def _mask_and_log(text: str, vault: Vault, customer: str) -> str:
    """Mask PII and record each detection (type, token, masked preview) for audit."""
    spans = DETECTOR.detect(text)
    for span in spans:
        token = vault.tokenize(span.value, span.entity_type)
        AUDIT.record(customer, span.entity_type, token, span.value)
    return mask_text(text, vault, spans)


def _mask_messages(messages: list[dict[str, object]], vault: Vault, customer: str) -> list[dict[str, object]]:
    masked: list[dict[str, object]] = []
    for message in messages:
        new_message = dict(message)
        content = new_message.get("content")
        if isinstance(content, str):
            new_message["content"] = _mask_and_log(content, vault, customer)
        tool_calls = new_message.get("tool_calls")
        if isinstance(tool_calls, list):
            new_tool_calls: list[object] = []
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    new_tool_calls.append(tool_call)
                    continue
                new_tool_call = dict(tool_call)
                function = new_tool_call.get("function")
                if isinstance(function, dict):
                    new_function = dict(function)
                    arguments = new_function.get("arguments")
                    if isinstance(arguments, str):
                        new_function["arguments"] = _mask_and_log(arguments, vault, customer)
                    new_tool_call["function"] = new_function
                new_tool_calls.append(new_tool_call)
            new_message["tool_calls"] = new_tool_calls
        masked.append(new_message)
    return masked


def _unmask_response(data: dict[str, object], vault: Vault) -> dict[str, object]:
    result = copy.deepcopy(data)
    for choice in result.get("choices", []) if isinstance(result.get("choices"), list) else []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        if isinstance(message.get("content"), str):
            message["content"] = unmask_text(message["content"], vault)
        for tool_call in message.get("tool_calls", []) if isinstance(message.get("tool_calls"), list) else []:
            function = tool_call.get("function") if isinstance(tool_call, dict) else None
            if isinstance(function, dict) and isinstance(function.get("arguments"), str):
                function["arguments"] = unmask_text(function["arguments"], vault)
    return result


async def _forward(body: dict[str, object], tenant: Tenant) -> dict[str, object]:
    url = f"{tenant.upstream_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {tenant.upstream_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=body, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"upstream error: {response.text}")
    return response.json()


async def _stream_content(body: dict[str, object], tenant: Tenant, vault: Vault):
    """True token-by-token streaming for plain chat (content carry-buffer detok)."""
    url = f"{tenant.upstream_base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {tenant.upstream_key}", "Content-Type": "application/json"}
    detok: dict[int, StreamDetokenizer] = {}
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("POST", url, json=body, headers=headers) as response:
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
    unmasked = _unmask_response(await _forward(body, tenant), vault)
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
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/usage")
async def usage(request: Request) -> dict[str, object]:
    """For the future UI: what PII we protected for this customer (counts +
    recent events with masked previews). No full PII is stored or returned."""
    tenant = _tenant(request)
    return {
        "protected_counts": AUDIT.counts(tenant.customer_id),
        "recent": AUDIT.recent(tenant.customer_id, 50),
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    tenant = _tenant(request)
    vault = _get_vault(tenant.customer_id)
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise HTTPException(status_code=400, detail="missing messages array")

    masked_body = dict(body)
    masked_body["messages"] = _mask_messages(body["messages"], vault, tenant.customer_id)
    for message in masked_body["messages"]:
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            _log.info("upstream role=%s content=%s", message.get("role"), message["content"])

    if body.get("stream") is True:
        streamer = _stream_as_single if body.get("tools") else _stream_content
        return StreamingResponse(streamer(masked_body, tenant, vault), media_type="text/event-stream")

    return JSONResponse(_unmask_response(await _forward(masked_body, tenant), vault))
