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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from obscura.audit import AuditLog, _preview
from obscura.detect_all import Detector
from obscura.redact import mask_text, unmask_text
from obscura.vault import Vault

# Persistent vault + audit live under OBSCURA_DB_DIR (a mounted volume in
# production) so tokens stay reversible across restarts and workers.
_DB_DIR = os.environ.get("OBSCURA_DB_DIR", ".")
DETECTOR = Detector()
AUDIT = AuditLog(os.path.join(_DB_DIR, "audit.db"))
_VAULTS: dict[str, Vault] = {}

app = FastAPI(title="Obscura sidecar")


def _vault(org_id: str) -> Vault:
    vault = _VAULTS.get(org_id)
    if vault is None:
        vault = Vault(os.path.join(_DB_DIR, "vault.db"), org_id)
        _VAULTS[org_id] = vault
    return vault


def _mask_one(text: str, vault: Vault, org_id: str, agent_id: str) -> str:
    spans = DETECTOR.detect(text)
    for span in spans:
        token = vault.tokenize(span.value, span.entity_type)
        AUDIT.record(org_id, agent_id, span.entity_type, token, span.value)
    return mask_text(text, vault, spans)


def _mask_messages(
    messages: list[dict[str, object]], vault: Vault, org_id: str, agent_id: str
) -> list[dict[str, object]]:
    masked: list[dict[str, object]] = []
    for message in messages:
        new_message = dict(message)
        # Never mask the system prompt: it carries the agent's instructions,
        # not user PII. Running NER over it is the bulk of the per-call cost
        # (tens of KB on every LLM call of a turn) and could corrupt the
        # instructions sent to the model. Pass it through untouched.
        if message.get("role") == "system":
            masked.append(new_message)
            continue
        content = new_message.get("content")
        if isinstance(content, str):
            new_message["content"] = _mask_one(content, vault, org_id, agent_id)
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
    return JSONResponse({"messages": _mask_messages(messages, _vault(org_id), org_id, agent_id)})


@app.post("/unmask")
async def unmask(request: Request) -> JSONResponse:
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    response = body.get("response")
    if not isinstance(response, dict):
        return JSONResponse({"error": "response must be an object"}, status_code=400)
    return JSONResponse({"response": _unmask_response(response, _vault(org_id))})


@app.post("/spans")
async def spans(request: Request) -> JSONResponse:
    """PII spans per text for dialog highlighting (read-only).
    Body: {org_id, texts: [str]} -> {results: [[{start,end,type,token,preview}], ...]}."""
    body = await request.json()
    org_id = str(body.get("org_id", "")) or "default"
    texts = body.get("texts")
    if not isinstance(texts, list):
        return JSONResponse({"error": "texts must be a list"}, status_code=400)
    vault = _vault(org_id)
    results = [_spans_for(text, vault) if isinstance(text, str) else [] for text in texts]
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
