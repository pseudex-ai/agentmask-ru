"""OpenAI-compatible reverse proxy.

The client points its `base_url` at this server. We mask PII in the outgoing
request, forward to the real upstream provider, and unmask PII in the response
(assistant content + tool_call arguments) so the client's tools run on real
values while the model only ever sees tokens.

Env:
  OBSCURA_UPSTREAM_BASE_URL  e.g. https://api.openai.com/v1  or  http://localhost:11434/v1
  OBSCURA_UPSTREAM_KEY       the real provider key (or any value for local models)
"""

import copy
import logging
import os

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from obscura.detect_all import Detector
from obscura.redact import mask_text, unmask_text
from obscura.vault import Vault

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("obscura")

# Prototype: a single process-wide vault gives consistency across requests
# (the agent framework re-sends history each turn). Real product: per-customer,
# persisted, in RF.
VAULT = Vault("vault.db", "demo")

# Full ensemble detector (regex + checksum IDs + Natasha NER), loaded once.
DETECTOR = Detector()

app = FastAPI(title="Obscura proxy (prototype)")


def _upstream_config() -> tuple[str, str]:
    base_url = os.environ.get("OBSCURA_UPSTREAM_BASE_URL")
    key = os.environ.get("OBSCURA_UPSTREAM_KEY")
    if base_url is None or key is None:
        raise HTTPException(
            status_code=500,
            detail="Set OBSCURA_UPSTREAM_BASE_URL and OBSCURA_UPSTREAM_KEY",
        )
    return base_url, key


def _mask_messages(messages: list[dict[str, object]], vault: Vault) -> list[dict[str, object]]:
    masked: list[dict[str, object]] = []
    for message in messages:
        new_message = dict(message)
        content = new_message.get("content")
        if isinstance(content, str):
            new_message["content"] = mask_text(content, vault, DETECTOR.detect(content))
        # Assistant tool_calls carry PII back in their arguments on later turns —
        # mask them too, or real values leak to the model on the next request.
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
                        new_function["arguments"] = mask_text(
                            arguments, vault, DETECTOR.detect(arguments)
                        )
                    new_tool_call["function"] = new_function
                new_tool_calls.append(new_tool_call)
            new_message["tool_calls"] = new_tool_calls
        masked.append(new_message)
    return masked


def _unmask_response(data: dict[str, object], vault: Vault) -> dict[str, object]:
    result = copy.deepcopy(data)
    choices = result.get("choices")
    if not isinstance(choices, list):
        return result
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            message["content"] = unmask_text(content, vault)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if isinstance(function, dict):
                    arguments = function.get("arguments")
                    if isinstance(arguments, str):
                        function["arguments"] = unmask_text(arguments, vault)
    return result


async def _forward(body: dict[str, object]) -> dict[str, object]:
    base_url, key = _upstream_config()
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=body, headers=headers)
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"upstream error {response.status_code}: {response.text}",
        )
    return response.json()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    if body.get("stream") is True:
        raise HTTPException(
            status_code=400, detail="streaming not supported in prototype"
        )
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="missing messages array")

    masked_body = dict(body)
    masked_body["messages"] = _mask_messages(messages, VAULT)

    # Proof that the model never sees real PII: log exactly what leaves to upstream.
    for message in masked_body["messages"]:
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            _log.info("upstream_message role=%s content=%s", message.get("role"), message["content"])

    upstream = await _forward(masked_body)
    return JSONResponse(_unmask_response(upstream, VAULT))
