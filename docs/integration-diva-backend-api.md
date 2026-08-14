# Diva backend API for Veilgate (per-agent toggle + stats)

**Status:** DESIGN for review. Nothing in Diva-Soft-Back is modified yet.
**Scope:** full backend API so the front (later) can (1) turn PII protection on/off **per agent**, (2) read **stats** ("что поймано / на что заменили"). IskariotAGI and the billing logic are NOT touched. UI is out of scope for now.
**Verified against Diva** via code map — all integration points reuse existing patterns.

---

## 0. Data model split (decision)
- **Vault keyed by `org_id`** (token consistency across all agents of an org, cross-turn). Already so.
- **Audit keyed by `(org_id, agent_id)`** → per-agent stats. ✅ done on the Veilgate side (`audit.py`, `service.py`): `/mask` accepts `agent_id`; `GET /usage?org_id&agent_id` returns per-agent counts + recent `{type, token, preview}`.

## 1. Per-agent config storage
Add a JSONB column `pii_config` to the `agents` table (model `src/database/models/agent.py`, same `MutableDict.as_mutable(JSONB)` pattern as `llm_settings`/`memory_settings`).

```python
# src/database/models/agent.py — after schedule_settings
pii_config: Mapped[dict[str, Any]] = mapped_column(
    MutableDict.as_mutable(JSONB),
    nullable=False,
    server_default=text("'{\"enabled\": false}'::jsonb"),
    comment="Veilgate PII masking: {enabled: bool}",
)
```
**Needs a 1-column Alembic migration** (additive, nullable-with-default → safe, no backfill). Pattern: `alembic/versions/186_add_meta_agent_type.py`. *(A new ORM column does require a migration; only adding keys INSIDE an existing JSONB column would be migration-free — but there is no generic catch-all column, so a clean dedicated `pii_config` column + migration is the right call.)*

Config shape (start minimal, room to grow):
```json
{ "enabled": true }
```
Future keys (not now): `entity_types` (which types to mask), `fail_open`, `vault_scope`.

## 2. Toggle API — reuse existing agent CRUD (no new route)
`PUT /api/v1/agents/{agent_id}` already exists (`src/api/v1/routers/agents.py:637`). Add the field to the schemas:
- `AgentUpdate` (`src/api/v1/schemas/agent.py:353`): `pii_config: Optional[Dict[str, Any]] = None`
- `AgentResponse` (`:158`): `pii_config: Dict[str, Any] = Field(default_factory=dict)`

Enable/disable for an agent = `PUT /agents/{id} {"pii_config": {"enabled": true}}`. `GET /agents/{id}` returns current state. Auth: existing `TenantContext` (org-scoped). After update, the existing `_invalidate_agent_caches` runs → also bust the PII-config cache (see §4).

## 3. Stats API — new route, mirrors usage.py
New router (or add to `src/api/v1/routers/usage.py`), same `TenantContext` auth + Dict response style as `/usage/agent/{id}/analytics`:

```
GET /api/v1/usage/veilgate/agent/{agent_id}/pii-stats
  -> { "agent_id", "protected_counts": {"PHONE": 12, "NAME": 5, ...},
       "recent": [ {ts, type, token, preview}, ... ] }
```
Handler: verify the agent belongs to `tenant.organization_id`, then call the Veilgate sidecar `GET /usage?org_id={org}&agent_id={id}` via `VeilgateClient` and return its body. (Veilgate is the source of truth for stats; Diva just scopes + authorizes.)

Optional org-wide rollup: `GET /usage/veilgate/pii-stats` → Veilgate `/usage?org_id=` (all agents).

## 4. Internal config endpoint for the LiteLLM callback
The callback already resolves `(org_id, agent_id)` via `GET /api/v1/billing/internal/resolve-agent-slug/{slug}` (`src/api/v1/routers/billing.py:112`, `X-Internal-Auth` header). Add a sibling internal endpoint so the callback knows whether to mask:

```
GET /api/v1/agents/internal/{agent_id}/pii-config   (X-Internal-Auth)
  -> { "enabled": true }
```
Or fold it into the existing resolve response: extend `resolve-agent-slug` to also return `pii_config` → **one HTTP call, no extra round-trip** (preferred). Cache in the callback by `agent_id` with a short TTL (e.g. 30–60 s); the agent-update cache-bust (§2) keeps it fresh enough.

## 5. LiteLLM callback flow (the actual masking) — see integration-diva-litellm.md
`docker/litellm/custom_callbacks.py`, inside `UniversalAttributionHook`:
- `async_pre_call_hook`: after slug resolve, **if `pii_config.enabled` for this agent** → call Veilgate `POST /mask {org_id, agent_id, messages}`, replace `data["messages"]`. Fail-closed (503) if Veilgate is down. If disabled → pass through untouched.
- `async_post_call_success_hook` (NEW): `POST /unmask {org_id, response}` → mutate response so the engine/MCP tools get real values.
- Streaming unmask: phase 2.

## 6. HTTP client (matches Diva pattern)
`VeilgateClient` = `httpx.AsyncClient` with timeout + bounded retries on transient errors (pattern: `src/domain/ai/core/.../api_client.py`). `VEILGATE_URL` env. Methods: `mask(org_id, agent_id, messages)`, `unmask(org_id, response)`, `stats(org_id, agent_id)`. Wrapped by `VeilgateService` (reads `Agent.pii_config`, decides to mask) and dependency-injected into routers like other services.

## 7. Full API surface (what the front will consume later)
| Purpose | Method + path | Auth |
|---|---|---|
| Enable/disable per agent | `PUT /agents/{id}` `{pii_config:{enabled}}` | TenantContext |
| Read current toggle | `GET /agents/{id}` → `pii_config` | TenantContext |
| Per-agent stats | `GET /usage/veilgate/agent/{id}/pii-stats` | TenantContext |
| Org-wide stats (opt.) | `GET /usage/veilgate/pii-stats` | TenantContext |
| (internal) agent PII cfg | `GET /agents/internal/{id}/pii-config` or via resolve-slug | X-Internal-Auth |

## 8. What we touch vs not
- **Touch (after review):** `agents.py` model (+1 col) + 1 Alembic migration; `schemas/agent.py` (+2 fields); new stats route; internal config endpoint (or extend resolve-slug); `custom_callbacks.py` (+mask/unmask, §5); new `VeilgateClient`/`VeilgateService`; `docker-compose.veilgate.yml` overlay (the sidecar container).
- **Do NOT touch:** IskariotAGI/engine, billing logic, existing agent business logic.

## 9. Rollout
`pii_config.enabled` defaults **false** for every agent → zero behavior change until a customer flips it. No global env needed for behavior (per-agent flag is the switch); keep `VEILGATE_ENABLED` only as a kill-switch for the whole integration. Canary: enable one agent, watch `/pii-stats` + fail-closed logs.
