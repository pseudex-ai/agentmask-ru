# Diva backend API for Pseudex (per-agent toggle + stats)

**Status:** DESIGN for review. Nothing in Diva-Soft-Back is modified yet.
**Scope:** full backend API so the front (later) can (1) turn PII protection on/off **per agent**, (2) read **stats** ("что поймано / на что заменили"). IskariotAGI and the billing logic are NOT touched. UI is out of scope for now.
**Verified against Diva** via code map — all integration points reuse existing patterns.

---

## 0. Data model split (decision)
- **Vault keyed by `org_id`** (token consistency across all agents of an org, cross-turn). Already so.
- **Audit keyed by `(org_id, agent_id)`** → per-agent stats. ✅ done on the Pseudex side (`audit.py`, `service.py`): `/mask` accepts `agent_id`; `GET /usage?org_id&agent_id` returns per-agent counts + recent `{type, token, preview}`.

## 1. Per-agent config storage
Add a JSONB column `pii_config` to the `agents` table (model `src/database/models/agent.py`, same `MutableDict.as_mutable(JSONB)` pattern as `llm_settings`/`memory_settings`).

```python
# src/database/models/agent.py — after schedule_settings
pii_config: Mapped[dict[str, Any]] = mapped_column(
    MutableDict.as_mutable(JSONB),
    nullable=False,
    server_default=text("'{\"enabled\": false}'::jsonb"),
    comment="Pseudex PII masking: {enabled: bool}",
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
GET /api/v1/usage/pseudex/agent/{agent_id}/pii-stats
  -> { "agent_id", "protected_counts": {"PHONE": 12, "NAME": 5, ...},
       "recent": [ {ts, type, token, preview}, ... ] }
```
Handler: verify the agent belongs to `tenant.organization_id`, then call the Pseudex sidecar `GET /usage?org_id={org}&agent_id={id}` via `PseudexClient` and return its body. (Pseudex is the source of truth for stats; Diva just scopes + authorizes.)

Optional org-wide rollup: `GET /usage/pseudex/pii-stats` → Pseudex `/usage?org_id=` (all agents).

## 4. Internal config endpoint for the LiteLLM callback
The callback already resolves `(org_id, agent_id)` via `GET /api/v1/billing/internal/resolve-agent-slug/{slug}` (`src/api/v1/routers/billing.py:112`, `X-Internal-Auth` header). Add a sibling internal endpoint so the callback knows whether to mask:

```
GET /api/v1/agents/internal/{agent_id}/pii-config   (X-Internal-Auth)
  -> { "enabled": true }
```
Or fold it into the existing resolve response: extend `resolve-agent-slug` to also return `pii_config` → **one HTTP call, no extra round-trip** (preferred). Cache in the callback by `agent_id` with a short TTL (e.g. 30–60 s); the agent-update cache-bust (§2) keeps it fresh enough.

## 5. LiteLLM callback flow (the actual masking) — see integration-diva-litellm.md
`docker/litellm/custom_callbacks.py`, inside `UniversalAttributionHook`:
- `async_pre_call_hook`: after slug resolve, **if `pii_config.enabled` for this agent** → call Pseudex `POST /mask {org_id, agent_id, messages}`, replace `data["messages"]`. Fail-closed (503) if Pseudex is down. If disabled → pass through untouched.
- `async_post_call_success_hook` (NEW): `POST /unmask {org_id, response}` → mutate response so the engine/MCP tools get real values.
- Streaming unmask: phase 2.

### 5.1 `conversation_id` on the way back — optional, and worth sending

`POST /unmask {org_id, response}` as written above works and stays working. But
the same body takes an optional `conversation_id`, and a callback that sends it
gets strictly more back.

**What it buys.** A WHOLE substitute resolves either way — it is unique, and
only the dialogue it was handed to could have written it. The difference is a
FRAGMENT: a `street` field with no house number, a house number on its own, a
date, the last four digits of a phone or a СНИЛС. Those strings are not unique —
«Полевая», «35», «15.05.2025» look the same in every dialogue — so the engine
will only answer one when it can tell WHOSE it is. `conversation_id` tells it:
the answer comes from the dialogue that minted the substitute, every time.

**What happens without it.** The request stands in no dialogue, so a fragment is
answered only when the whole vault holds exactly ONE candidate for it. One
dialogue talking about that street → it resolves, as today. Two dialogues of the
same org holding a substitute on the same street → the engine refuses rather
than guessing, because guessing would put one customer's real address into
another customer's tool call.

**A refusal is never silent, whatever the fragment was, on whichever leg it
stood.** What did not resolve comes back in `residual_tokens` (and as the count
in the `X-Pseudex-Residual` header), with the substitute named — a street, a
house number, a date the agent renotated, a group of digits cut out of a longer
value — and it is named the same way whether it stood in a tool call's arguments
or in the assistant's own prose to the customer. The status is still 200 and the
JSON is still well formed, so that list is the only way the callback can tell a
restored value from a fake that reached the tool — treat a non-empty
`residual_tokens` as "do not execute this tool call yet".

**And the list is about the substitute, never about the answer.** It names only
strings the MODEL wrote that the engine MINTED and could not resolve, and that
are therefore still standing in what you are reading. A value that was restored
correctly never appears there, even when the customer's own street or name
happens to look like a substitute minted for another dialogue; and a value the
engine never produced — an order quantity, a warehouse's own flat number — is
not named at all, because the question asked is "did we mint this", not "does
this look like something we mint".

**The one case where that question has no clean answer is a bare number with no
dialogue named.** «47» under a `house` key, with no `conversation_id` and no
street beside it, is two digits: if several of your substitutes carry that house
the engine cannot tell one of them from a number of your own, and it names it
rather than staying silent about a possible fake. Passing `conversation_id`
removes the ambiguity entirely — the dialogue that minted the substitute answers,
and the list is empty.

Same id as `/mask` (the one the callback already passes there, or nothing at all
on both legs), and the same field on `/unmask_arguments` and `/unmask_chunk`.

**`pseudonym_scope` travels with it.** If the callback declares
`pseudonym_scope: "customer"` on `/mask` (an agent with long-term memory that
recalls substitutes across dialogues), it must declare it on `/unmask*` too, or
the value is minted account-wide and restored per dialogue. The declaration
reaches FRAGMENTS as well, in two steps and in this order: the dialogue named in
the request answers first and competes with nobody, and only when it has nothing
to say is the whole account asked — under the same single-candidate rule as
above. The order matters to you: without it, your own dialogue's address would
stop resolving the moment another dialogue mentioned the same street. The body
wins over `PSEUDEX_PSEUDONYM_SCOPE`; an unknown value is a 400, never a silent
fallback.

## 6. HTTP client (matches Diva pattern)
`PseudexClient` = `httpx.AsyncClient` with timeout + bounded retries on transient errors (pattern: `src/domain/ai/core/.../api_client.py`). `PSEUDEX_URL` env. Methods: `mask(org_id, agent_id, messages, conversation_id=None)`, `unmask(org_id, response, conversation_id=None)` (§5.1 — the id is optional and worth passing; `unmask` also returns `residual_tokens`), `stats(org_id, agent_id)`. Wrapped by `PseudexService` (reads `Agent.pii_config`, decides to mask) and dependency-injected into routers like other services.

## 7. Full API surface (what the front will consume later)
| Purpose | Method + path | Auth |
|---|---|---|
| Enable/disable per agent | `PUT /agents/{id}` `{pii_config:{enabled}}` | TenantContext |
| Read current toggle | `GET /agents/{id}` → `pii_config` | TenantContext |
| Per-agent stats | `GET /usage/pseudex/agent/{id}/pii-stats` | TenantContext |
| Org-wide stats (opt.) | `GET /usage/pseudex/pii-stats` | TenantContext |
| (internal) agent PII cfg | `GET /agents/internal/{id}/pii-config` or via resolve-slug | X-Internal-Auth |

## 8. What we touch vs not
- **Touch (after review):** `agents.py` model (+1 col) + 1 Alembic migration; `schemas/agent.py` (+2 fields); new stats route; internal config endpoint (or extend resolve-slug); `custom_callbacks.py` (+mask/unmask, §5); new `PseudexClient`/`PseudexService`; `docker-compose.pseudex.yml` overlay (the sidecar container).
- **Do NOT touch:** IskariotAGI/engine, billing logic, existing agent business logic.

## 9. Rollout
`pii_config.enabled` defaults **false** for every agent → zero behavior change until a customer flips it. No global env needed for behavior (per-agent flag is the switch); keep `PSEUDEX_ENABLED` only as a kill-switch for the whole integration. Canary: enable one agent, watch `/pii-stats` + fail-closed logs.
