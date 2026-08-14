# Integration design: Veilgate ⇄ Diva-Soft-Back (via LiteLLM)

**Status:** DESIGN for review. Nothing in Diva-Soft-Back is modified yet.
**Goal:** every LLM call on the Diva platform gets PII masking/unmasking, with **zero changes to IskariotAGI** and **minimal, billing-safe** changes to the LiteLLM callback.

---

## 1. Where things stand in Diva (verified)
- All LLM traffic: `IskariotAGI → http://litellm:4000/v1 → providers` (`config_builder.py` injects baseUrl + `LITELLM_MASTER_KEY`).
- LiteLLM = official image `ghcr.io/berriai/litellm@sha256:fb55…` (v1.86.1), **config + `custom_callbacks.py` volume-mounted** (`docker-compose.litellm.yml:211-214`). No Dockerfile.
- One callback registered: `UniversalAttributionHook` (`config.yaml:369`). It implements:
  - `async_pre_call_hook` — parses `iskariot/{slug}/{real}` model prefix → resolves **`org_id, agent_id`** via HTTP to Diva (`/api/v1/billing/internal/resolve-agent-slug/{slug}`) → sets `data["user"]`, strips prefix. **org_id is available here** — this is our masking point.
  - `async_log_success_event` / `_push_billing_event` — billing (logging only).
- Tools are **MCP-based**, executed engine-side. PII still flows through LiteLLM inside chat `messages` + model `tool_calls` + `role:tool` results → so masking at LiteLLM is sufficient (engine↔MCP is internal and receives the unmasked values after our post-call hook).
- Streaming (SSE) IS used (`src/api/public/llm_api.py`).
- Existing PII bits (audit_log mask, moderation regex, hook redact_fields) are audit/tool-result side — **no general request-level masking exists**; no conflict.

## 2. Architecture decision — Veilgate as a SIDECAR service (not inside LiteLLM)
LiteLLM image can't easily take heavy deps (natasha/pymorphy3). So:
```
IskariotAGI → LiteLLM (callback) ──HTTP──> Veilgate sidecar (/mask, /unmask)
                  │                              (our code + deps + vault + audit)
                  └──────────────> provider (sees only tokens)
```
- **Veilgate runs as its own container** in Diva's `devbackend_default` network — same pattern the callback already uses (HTTP to Diva API).
- LiteLLM container stays clean (callback needs only `httpx`, already present).
- Everything stays **in the customer's contour** → 152-ФЗ-safe; Diva is already the operator/processor.

## 3. The LiteLLM callback changes (minimal, billing-safe) — FOR REVIEW
Add to `UniversalAttributionHook`. Billing logic untouched.

**(a) pre-call: mask** — inside `async_pre_call_hook`, AFTER org resolution (right after line ~363 where metadata is set), before `data["model"] = real_model`:
```python
# --- Veilgate PII masking (only when we know the org) ---
if os.environ.get("VEILGATE_ENABLED") == "1" and resolved is not None:
    masked = await self._veilgate_mask(org_id, data.get("messages"), data.get("tools"))
    if masked is None:
        # FAIL-CLOSED: do not send real PII to the model if Veilgate is down.
        raise HTTPException(status_code=503, detail="PII gateway unavailable")
    data["messages"] = masked
```
*(Note the contrast: billing is fail-open; PII is **fail-closed**. If you prefer availability over strict no-leak, make it configurable: `VEILGATE_FAIL_OPEN=1` → log loud + pass through.)*

**(b) post-call: unmask** — NEW method (mutates the response; the logging hook can't):
```python
async def async_post_call_success_hook(self, data, user_api_key_dict, response):
    if os.environ.get("VEILGATE_ENABLED") != "1":
        return response
    org_id = (data.get("user")
              or (data.get("metadata") or {}).get("diva_org_id"))
    if org_id:
        await self._veilgate_unmask(org_id, response)  # mutates response in place
    return response
```

**(c) streaming: unmask chunks** — PHASE 2:
```python
async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
    org_id = (request_data.get("user") or (request_data.get("metadata") or {}).get("diva_org_id"))
    async for chunk in response:
        yield await self._veilgate_unmask_chunk(org_id, chunk) if org_id else chunk
```

**(d) the HTTP helpers** reuse the existing `_get_http_client()` + `VEILGATE_URL` env, calling the sidecar `/mask` and `/unmask`. ~30 lines, no new deps.

> ⚠️ Verify exact hook signatures against LiteLLM v1.86.1 before applying (`async_post_call_success_hook`, `async_post_call_streaming_iterator_hook`) — they exist on `CustomLogger` in 1.8x but confirm arg order.

## 4. Veilgate sidecar API (our side — see `prototype/veilgate/service.py`)
- `POST /mask` → `{org_id, messages, tools}` → `{messages}` (masked) + records audit. Detect→tokenize per `org_id` vault.
- `POST /unmask` → `{org_id, response}` → `{response}` (detokenized: content + tool_calls[].arguments).
- `POST /unmask_chunk` → streaming delta detok (StreamDetokenizer per stream).
- `GET /usage?org_id=` → audit counts + recent (for the UI).
- **Vault keyed by `org_id`** (persistent SQLite/Redis) → cross-turn consistency, multi-tenant. Centralized in the sidecar → correct even with multiple LiteLLM workers/pods (shared vault, unlike per-worker in-process).

## 5. Key decisions / risks (don't miss)
1. **Fail-closed (default) vs fail-open** — privacy vs availability. Default fail-closed (don't leak); make Veilgate HA (it's light, ~3 ms detect). Flag to switch.
2. **unmask MUST be `async_post_call_success_hook`**, not the logging hook (logging can't change what the engine receives).
3. **Tool/MCP**: we only protect what reaches the LLM (messages + response). The engine gets unmasked tool args from our post-call hook, then calls MCP tools with real values — correct.
4. **Vault scope**: `org_id` baseline; add conversation/session id from metadata if available for tighter token namespaces.
5. **Latency**: + one in-network HTTP hop + ~3 ms detect per call. Acceptable vs seconds of LLM.
6. **Multi-worker LiteLLM**: in-process vault would desync across workers → that's why the vault lives in the **sidecar** (single source of truth).
7. **Rollout**: `VEILGATE_ENABLED` off by default → enable per-env → canary one org → watch `/usage` + leak logs. Billing path unchanged when off.
8. **LiteLLM spend logs** then contain only masked text — a bonus (even billing logs hold no PII).

## 6. Test plan
- Unit: our `/mask` `/unmask` (we have the core tests).
- Integration: mock LiteLLM callback → Veilgate sidecar (mask→unmask round-trip, fail-closed on sidecar down).
- E2E: one real IskariotAGI agent run through the full stack on a dev org; assert provider logs show only tokens, tool got real values, `/usage` populated.
- Eval: run the existing stress/holdout sets through `/mask` to confirm 0-leak holds in this packaging.

## 7. What we touch vs not
- **Touch (after review):** `docker/litellm/custom_callbacks.py` (+~50 lines), add `docker-compose.veilgate.yml` overlay, Veilgate container image.
- **Do NOT touch:** IskariotAGI, the engine, Diva backend business logic, the billing logic inside the callback.
