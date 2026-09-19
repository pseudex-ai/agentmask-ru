# A2 — Western commercial products: how deep does "agent transparency" go? (as of 2026-09-20)

Excavation date: 2026-09-20. Scope: transparency axis (reversibility, tool-call plumbing, agent's-own-form restore, scope, morphology, collisions), deployment, published measurement. NOT detection recall. Russian/CIS, OSS and academic work excluded (other agents).

Evidence grades: [A] proven with stated conditions · [B] primary but limited · [C] vendor-asserted · [D] folklore / inference / LLM-synthesised.

Raw copies of every fetched source are in `scratchpad/raw/src/` (file names given per quote). Fetch budget used: ~30 web calls (search/fetch/extract) plus direct `curl` of docs `.md` endpoints and GitHub raw files.

---

## 0. Method notes that affect the verdict

1. **Skyflow's Detect / Agents / Accuracy / MCP-server docs are login-gated.** `curl` of `/docs/de-identification/agents.md`, `/docs/de-identification/reidentify-data/text.md`, `/docs/de-identification/capabilities/accuracy.md`, `/docs/de-identification/capabilities/performance.md`, `/docs/external-integrations/mcp-server.md` and `/api/detect/llms.txt` all return the literal string `User is not logged in` (saved: `skyflow-deid-agents.md`, `skyflow-deid-capabilities-accuracy.md`, `skyflow-deid-capabilities-performance.md`, `skyflow-mcp-server.md`, `skyflow-reidentify-text.md`). Tavily "advanced" extraction of the HTML routes returned the identical 15 626-byte login page four times. Skyflow's own docs MCP server (`https://docs.skyflow.com/_mcp/server`, `fern-docs-mcp-server 1.0.0`, one tool `searchDocs`) answers anonymously but returns an LLM-synthesised answer, and for the gated pages it says: *"I wasn't able to find an 'Agents page' or MCP server documentation in the retrieved content."* and *"The de-identification documentation available on docs.skyflow.com does not publish any specific accuracy or performance figures such as precision, recall, or latency benchmarks for the Detect API."* (saved: `skyflow-mcp-search.txt`; grade [D] — synthesised, but consistent with the gating observed directly). **Consequence:** every Skyflow claim about agent/tool-call mechanics is graded [C] at best; the public SDK source (grade [B]) is the only hard evidence of the API shape.
2. Protecto's docs are fully open in `.md` form (`docs.protecto.ai/llms.txt`, 119 lines) and its 2026-09 LibreChat engineering post is the single most explicit primary source on tool-call plumbing found anywhere in the Western commercial set.
3. Limina's OpenAPI for re-identify is public; the new `privateai/limina-postprocessor` repo (created 2026-09-15) is public source.

---

## 1. Skyflow (Data Privacy Vault · Detect · "Agentic AI Security Layer" · MCP Data Protection Layer / MCP Gateway)

**URLs:** https://docs.skyflow.com/docs/de-identification · https://docs.skyflow.com/docs/tokenization/tokenize · https://docs.skyflow.com/docs/fundamentals/patterns/llm-privacy · https://docs.skyflow.com/docs/fundamentals/deployment-models · https://github.com/skyflowapi/skyflow-python (pushed 2026-09-18) · https://www.skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault · https://www.skyflow.com/post/building-secure-ai-agent-architecture-mcp · https://www.skyflow.com/product/skyflow-for-agents · https://www.skyflow.com/post/what-is-tokenization-what-every-engineer-should-know

**Date of latest primary material:** SDK repo push 2026-09-18 (skyflow-python; node/java same day). Docs de-identification page current (fetched 2026-09-20). Gated "Agents" doc page exists in the nav (title only). Press: "Skyflow for Glean" (Yahoo Finance syndication, 2026, undated in snippet).

### Verbatim quotes

Q-S1 (docs, de-identification overview, `skyflow-deid-llms.txt`):
> "Custom redaction/tokenization options customize how Skyflow masks or redacts sensitive entities in your data. Choose vault tokens (like `NAME_ABC123`), entity-unique counters, or entity-only tokens. You can also select from format-preserving tokens, UUIDs, or numeric combinations for vault tokens."
> "Many languages and entities supported. De-identify a broad range of personally identifiable information including names, addresses, and credit card numbers across more than 40 languages with support for 60 entity types."
> "Re-identifying redacted unstructured data applies role-based controls to define who can see masked, redacted, or plaintext data, ensuring compliance and protection of privacy policies at all levels."

Q-S2 (SDK source, `skyvault/skyflow/vault/detect/_reidentify_text_request.py`, saved `skyflow-sdk-_reidentify_text_request.py`):
```python
class ReidentifyTextRequest:
    def __init__(self, text: str,
                redacted_entities: Optional[List[DetectEntities]] = None,
                masked_entities: Optional[List[DetectEntities]] = None,
                plain_text_entities: Optional[List[DetectEntities]] = None):
```
and `_token_format.py`:
```python
class TokenFormat:
    def __init__(self, default: TokenType = TokenType.ENTITY_UNIQUE_COUNTER,
                 vault_token: List[DetectEntities] = None,
                 entity_unique_counter: List[DetectEntities] = None,
                 entity_only: List[DetectEntities] = None):
```
`TokenType`: `VAULT_TOKEN = "vault_token"`, `ENTITY_UNIQUE_COUNTER = "entity_unq_counter"`, `ENTITY_ONLY = "entity_only"`. `DeidentifyTextResponse(processed_text, entities: List[EntityInfo], word_count, char_count)`; `EntityInfo(token, value, text_index, processed_index, entity, scores)`. `DetectEntities` enum: 70 members incl. `NAME`, `NAME_GIVEN`, `NAME_FAMILY`, `PHONE_NUMBER`, `SSN`, `CREDIT_CARD`, `DOB`, `LOCATION_ADDRESS`, `PASSPORT_NUMBER` … (saved `skyflow-sdk-detect_entities.py`). The `detect` module contains **no** tool-call, JSON-argument, conversation-scope, or MCP primitive (tree scan of the whole repo for `mcp|agent|llm|tool|json_|structured` outside `generated/` returned nothing; saved `skyflow-python-tree.json`).

Q-S3 (tokenize docs, `skyflow-tokenize.md`):
> "Format preserving deterministic token: This format generates random tokens but preserves the format based on the specified regular expression (regex) expression. If a value appears in the column more than once, each instance of the value generates the same token."
> "Transient UUID token: … If the token expires, detokenization fails."

Q-S4 (LLM Privacy Vault blog, `skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault`):
> "Skyflow-generated tokens used to protect sensitive data from LLMs are deterministic, meaning that a given sensitive data value will consistently tokenize into the same token string."
> "When an LLM generates a response, the Skyflow-generated tokens are detokenized as the LLM response is sent to the user, replacing these tokens with the original sensitive data elements. Only authorized users are permitted to detokenize plaintext sensitive data that's included in the LLM's response because of the fine-grained access controls configured in the vault."

Q-S5 (what-is-tokenization blog):
> "The same deterministic stand-in appears for a given value throughout a conversation, so the model's output stays coherent. Skyflow detokenizes authorized responses on the way out under the end user's policy."

Q-S6 (MCP architecture blog):
> "Skyflow MCP Gateway: A proxy layer (which can be integrated into existing proxy servers) that sits between MCP servers or agents and backend data sources, enforcing field-level privacy policies without requiring application changes."
(WebFetch verdict on that page: *"the article does not include verbatim information on … how the Skyflow MCP Gateway handles tool call arguments; tool responses/results; … what happens when models alter tokens; language support; measurement or benchmark numbers; deployment options; pricing; publication date."*)

Q-S7 (Skyflow for Agents product page):
> "Policy-based data rehydration — Restore original values only where policy allows in the workflow."
> "Traditional security tools block sensitive data — and break the agent. Skyflow protects data in motion so agents stay functional and compliant."
> "Skyflow keeps PII out of context graphs, memory stores, and prompts."

Q-S8 (deployment models doc, `skyflow-deployment-models.md`):
> "Skyflow supports three deployment models … Multi-tenant SaaS | Shared, fully managed | Logical isolation; Virtual Private Skyflow | Dedicated VPC (managed) | Physical isolation; Bring Your Own Cloud (BYOC) | Customer cloud account | Full infrastructure control"
> "With BYOC, Skyflow runs inside your cloud environment. Skyflow is deployed into your cloud account (AWS or GCP) … All traffic stays within your network boundaries."

Q-S9 (third party, WorkOS comparison, https://workos.com/blog/skyflow-vs-workos-agentic-security):
> "Skyflow does not publish public pricing tiers. The platform is available through AWS and Google Cloud marketplaces."

### Checklist — Skyflow

| # | Item | Verdict | Evidence / grade |
|---|---|---|---|
| 1 | Reversible in answer | **Yes** | Q-S4, Q-S2 `reidentify_text` [B] |
| 2 | Tool-call args restored, JSON kept valid | **Not documented (public)** | Only Q-S6/Q-S7 marketing "rehydration"; no API for JSON args in SDK; gated docs [C] |
| 3 | Tool results re-masked, same substitute | **Asserted** | Q-S5 "throughout a conversation"; Q-S6 gateway "sits between MCP servers … and backend data sources" [C] |
| 4 | Format-preserving; gender; checksum-invalid | **Partial** | Format-preserving = regex-based (Q-S3) [B]; default Detect token is `NAME_1`-style counter or `NAME_ABC123` (Q-S1/Q-S2) [B]; gender-matched fake names: **not documented**; checksum-invalid guarantee: **not documented** (a regex-FPT 16-digit token has no stated Luhn property) |
| 5 | Multi-turn consistency + canonicalisation of variants | **Partial** | Deterministic per value (Q-S4) [B]; canonicalisation of `+1 (555)` vs `555…` or inflected names: **not documented** |
| 6 | Streaming detok; tool-arg deltas buffered | **Not documented** | nothing public |
| 7 | Restore when model REWROTE the token | **No / not documented** | SDK re-identify is exact-token substitution on `text`; docs-MCP synthesis says "even a single character difference will cause a 'not found' error" [D] |
| 8 | Memory / cross-conversation scope | **Not documented** | Q-S7 "keeps PII out of … memory stores" is a prevention claim, not a scoping mechanism [C] |
| 9 | Partial mentions / corrections → one substitute | **Not documented** | — |
| 10 | Declension-aware mask/restore | **No** | 40+ languages for *detection* (Q-S1) [B]; no morphology statement anywhere |
| 11 | Collisions (fake == later real) | **Structurally moot for counter/UUID tokens; not documented for FPT** | `NAME_1`/`NAME_ABC123` are not in the real-value space; regex-FPT tokens are [B inference] |
| 12 | Deployment / residency / pricing | **SaaS, Virtual Private (VPC), BYOC (AWS/GCP)**; no public pricing | Q-S8 [A]; Q-S9 [B] |
| 13 | Published "agent unaffected" measurement | **None found** | gated Accuracy page; docs-MCP: no precision/recall/latency published [D]; blog has no numbers [B] |

**Skyflow bottom line:** The public SDK proves a flat `text`-in / `processed_text`-out de-identify and a flat `text`-in re-identify keyed on exact tokens. Everything about tool calls, MCP, "two-way rehydration" and agents is (a) marketing prose or (b) behind login. The owner's suspicion is *consistent* with all public evidence: Skyflow has a policy-gated rehydration proxy, not a documented agent-form-tolerant restore. Nothing public refutes it; nothing public proves it either — grade [C] for the whole tool-call story.

---

## 2. Protecto (Privacy Vault · AI Data Control Plane · Privacy Gateway for AI Chat)

**URLs:** https://docs.protecto.ai (llms.txt, 119 pages) · https://docs.protecto.ai/core-concepts/tokenization-basics · https://docs.protecto.ai/core-concepts/tokens-vs-formats · https://docs.protecto.ai/core-concepts/entity-tags · https://docs.protecto.ai/core-concepts/unmasking · https://docs.protecto.ai/errors-limits/unmasking-errors · https://docs.protecto.ai/use-cases/genai-llm-prompts · https://docs.protecto.ai/use-cases/crm-support · https://docs.protecto.ai/deployment/overview · https://www.protecto.ai/blog/protecto-gateway-librechat-integration · https://www.protecto.ai/product/privacy-vault · https://www.protecto.ai/solutions/data-access-control-for-ai-agents

**Date of latest primary material:** LibreChat gateway post, September 2026 (OG banner asset `2026-09-02_OG-Banner_Protecto-LibreChat-Integration`; WebFetch reported "Published: September 17, 2026"; page header shows "Published:" with no visible date in the extracted markdown). Docs fetched 2026-09-20.

### Verbatim quotes

Q-P1 (LibreChat post, tool calls):
> "Say a support workflow inside LibreChat has a tool wired to a billing system. Someone asks the assistant to check the status of a specific invoice for a named customer. The model reasons over masked values, because that's all it was ever given, and it calls the billing tool with the masked customer identifier. Before LibreChat or an MCP server runs that call, the Gateway sends the masked argument to Protecto for resolution and passes the tool the real one. The lookup runs against your actual customer record, not a token that matches nothing. When the tool returns a result, the Gateway masks it again before it goes back to the model for the next turn."

Q-P2 (LibreChat post, stated limit):
> "One limitation worth stating plainly. This is boundary resolution, authorized by a per-user Protecto token. It is not yet a policy decision made per tool or per field. Today, if a tagged value appears and the requesting user's token permits unmasking, the Gateway resolves it. It doesn't yet ask whether this specific tool, or this specific task, should be allowed to see this specific kind of value. That's a real gap, on the roadmap rather than shipped"

Q-P3 (LibreChat post, streaming + state):
> "On the way back, the Gateway watches the streamed response for masked values it needs to resolve. One it already has from earlier in the request gets swapped back in locally. Anything it hasn't seen yet is resolved with a call to Protecto."
> "Streaming adds one more constraint worth knowing if you're debugging this yourself. A tool-calling turn has to stay a tool-calling turn from start to finish. It can't look like an ordinary text answer partway through and then switch to a tool call, because LibreChat will treat the early text as the complete response and skip the tool entirely."
> "The Gateway keeps no conversation database of its own. LibreChat stores the conversation and masked replay information. On the next turn, the Gateway rebuilds protected history from a valid saved checkpoint and masks only new content, including new prompts and tool results."
> "The Gateway is a stateless, OpenAI-compatible layer. … whichever model you connect (OpenAI or Gemini today)."

Q-P4 (LibreChat post, failure + measurement):
> "An unmasking failure is the safest of the three outcomes. If Protecto can't resolve a value on the response path, the Gateway returns the masked version rather than guessing at the real one. A tool call downstream might get no match or the wrong result, but it won't be handed data it shouldn't see."
> "We haven't published a retrieval-quality number for that effect because we don't have one we'd stand behind yet."
> "LibreChat is the integration we've built, tested, and shipped … Other chat interfaces are protocol-compatible in principle, and we won't claim they work until we've verified that end to end the same way."

Q-P5 (docs, token semantics):
> "Deterministic — The same input value always produces the same token (when using the same token type). This means you can join, group, and compare tokenized values." (tokenization-basics)
> "| `9876543210` | `<PHONE>8349201756</PHONE>` | The output looks like a valid phone number, has the same length and character set, but does not reveal the original value." (tokens-vs-formats)
> "Contact <PERSON>VJYe 03W</PERSON> at <EMAIL>0gN3SkjL@0ffM3CDS</EMAIL>" … "**\"Entity tags are optional.\"** No. Tags are part of Protecto's output model and are always included." (entity-tags)

Q-P6 (docs, altered token):
> "Unmask failure (token not found) — The token does not exist in the namespace. This can happen if: The token was created under a different namespace; The personal data mapping was deleted (data retention policy); **The token value was modified or truncated**" (unmasking-errors)

Q-P7 (docs, deployment):
> "Protecto supports SaaS and on-premises deployments. Both expose identical APIs — the difference is where Protecto runs and who operates it." / "On-Premises Deployment: Run Protecto inside your own infrastructure or private cloud for full data residency control and air-gapped environments."

Q-P8 (marketing pages, search snippets, saved in this file only):
> "200+ PII / PHI entity types · 50+ Languages supported" (product/privacy-vault)
> "99% PII detection accuracy across 50+ entity types in production — Protecto internal benchmark · <1% Response accuracy degradation after context-preserving masking" (solutions/data-access-control-for-ai-agents)
> "Agent Memory — Cross-session storage — \"Customer: bLsJi 0ABo, Card: 3261833118\" — Masked before storage. Access-controlled on reveal" (same page)

### Checklist — Protecto

| # | Item | Verdict | Evidence / grade |
|---|---|---|---|
| 1 | Reversible in answer | **Yes** | Q-P3, docs unmask [B] |
| 2 | Tool-call args restored before execution | **Yes, asserted for the LibreChat gateway; JSON-validity of quoted real values not stated** | Q-P1 [C→B: engineering post, one shipped integration]; nothing on escaping |
| 3 | Tool results re-masked, same substitute | **Yes (asserted)** | Q-P1 last sentence; determinism Q-P5 [C/B] |
| 4 | Format-preserving; gender; checksum-invalid | **Partial** | "format" mode preserves length/charset (Q-P5) [B]; default tokens are random strings inside XML-like tags; **no gender-matched names; no checksum statement** (`<PHONE>8349201756</PHONE>` could be a real number) |
| 5 | Multi-turn consistency + canonicalisation | **Consistency yes (deterministic, namespace-wide); canonicalisation not documented** | Q-P5 [B] |
| 6 | Streaming detok; tool-arg buffering | **Streamed content: yes; tool turn: "has to stay a tool-calling turn"** | Q-P3 [B] |
| 7 | Restore when model REWROTE token | **No** | Q-P6 "modified or truncated" = failure; Q-P4 returns masked version [A — vendor documents the failure] |
| 8 | Memory / cross-conversation scope | **Namespace(customer)-global determinism; no conversation scope** | Q-P8 memory "masked before storage"; Q-P3 history rebuilt per LibreChat conversation [B] |
| 9 | Partial mentions / corrections | **Not documented** | — |
| 10 | Declension-aware | **No** | 50+ languages for detection only [C] |
| 11 | Collisions | **Structurally avoided while tags survive** (tags `<PERSON>…</PERSON>` make substitutes syntactically distinct); **format tokens are in the real-value space** | Q-P5 [B inference] |
| 12 | Deployment / pricing | SaaS + on-prem/air-gapped (Q-P7) [A]; pricing: "Talk to an Expert", free trial API; no list |
| 13 | Published "agent unaffected" measurement | **Marketing numbers only** ("<1% Response accuracy degradation", "internal benchmark", no conditions) [C]; engineering post explicitly declines to publish a retrieval number (Q-P4) |

**Protecto bottom line:** The most explicit Western tool-call story, shipped for exactly one host (LibreChat), OpenAI/Gemini only, per-user (not per-tool) authorization, exact-token resolution, and an honest "no number we'd stand behind" on quality impact. Items 7, 9, 10, 11, 13: not covered.

---

## 3. Limina (formerly Private AI)

**URLs:** https://docs.getlimina.ai/latest/reidentify-text (OpenAPI 4.3.0 / privateai_4.5.0.json) · https://docs.getlimina.ai/configuration-and-operations/advanced-features/llms · https://docs.private-ai.com/introduction · https://www.getlimina.ai/en/pricing · https://github.com/privateai/limina-postprocessor (created 2026-09-15, pushed 2026-09-18)

**Date of latest primary material:** limina-postprocessor 2026-09-18; docs API 4.5.0 (current).

### Verbatim quotes

Q-L1 (reidentify OpenAPI):
> "This route is intended to improve integrations with LLMs such as ChatGPT. Entities that are removed prior to sending to the LLM can be re-injected into the response from the LLM to improve user experience."
> "processed_text — The text with redaction markers. The markers will be replaced with the entity texts. E.g. `Hi [NAME_1], nice to meet you.`"
> "model — The LLM that provides the completions. E.g. `gpt3.5-turbo`. Whilst optional, this is used to improve the re-identification process by accounting for the model's unique behaviour surrounding redaction markers"
> "reidentify_sensitive_fields — When this parameter is set to `False`, the re-identifier will mask fields ['BANK_ACCOUNT', 'CREDIT_CARD', … 'SSN', …] with '#' instead of re-identifying them."
> request body `required: [processed_text, entities]` where each entity is `{processed_text: "NAME_1", text: "Sansa"}`.

Q-L2 (intro):
> "Limina is a stateless, container-based entity detection and redaction engine … No data leaves your environment and no data is ever shared with any third parties."

Q-L3 (LLM guide): the caller keeps the mapping —
> "Let's create a function that will redact personal data from user input, and generate entity mappings that will later be used to re-identify the response"

Q-L4 (limina-postprocessor README):
> "Replaces de-identified name placeholders with realistic synthetic names while preserving: Global uniqueness … Within-document coreference - Same name gets same replacement · Gender matching - Male/female names matched (~90% on the sample corpus) · Leading honorifics … · Index accuracy"
> "Measured: 90.7% agreement on the 100-doc sample corpus (175/193 entities where gender was resolvable on both sides)"
> "`last_name_to_full` / `first_name_to_full` let a partial mention reuse an already-assigned full name (`_smart_match`) — Example: "John Smith" → "Champ Dannenmueller", then "Smith" → "Dannenmueller""
> "Known limitation: trailing suffixes (`Jr.`, `Sr.`, `III`, `IV`) are dropped"

Q-L5 (pricing page): "Starter — Free — Up to 75 API calls / day (10 calls / minute)"; "Batch — Volume Pricing — GET A QUOTE"; "Your data is never stored or logged—processed and immediately discarded".

### Checklist — Limina

| # | Item | Verdict | Evidence / grade |
|---|---|---|---|
| 1 | Reversible in answer | **Yes** (marker → text) | Q-L1 [A] |
| 2 | Tool-call args | **No** — API is `processed_text: [str]`; caller must apply it to each JSON string itself | Q-L1 [A] |
| 3 | Tool results re-masked | **Not a product feature** (stateless; caller loops) | Q-L2 [A] |
| 4 | Format-preserving / gender / checksum | **Synthetic entities exist (`process/text` "replaced with AI-generated synthetic entities"); gender ~90.7% in the NEW postprocessor, which is a batch ETL tool for DEID JSON, not the LLM loop; no checksum statement** | Q-L4 [A for the number; scope limited] |
| 5 | Multi-turn consistency | **Caller's responsibility** (stateless); postprocessor coreference is per-document | Q-L2, Q-L4 [A] |
| 6 | Streaming | **Not documented** | — |
| 7 | Model rewrote marker | **Partially acknowledged, mechanism undisclosed** — the `model` parameter "accounting for the model's unique behaviour surrounding redaction markers" | Q-L1 [B] |
| 8 | Memory / scope | **N/A** (no vault) | Q-L2 [A] |
| 9 | Partial mentions | **Only in the batch postprocessor** (`_smart_match`) | Q-L4 [B] |
| 10 | Declension | **No** ("52 languages" detection; no morphology) | [C] |
| 11 | Collisions | **N/A for markers; not addressed for synthetic** | — |
| 12 | Deployment / pricing | Container in your environment; free tier 75 calls/day; quotes | Q-L2, Q-L5 [A] |
| 13 | Agent-fidelity measurement | **None** | — |

---

## 4. Tonic Textual

**URLs:** https://docs.tonic.ai/llms.txt (819 lines) · https://docs.tonic.ai/textual/dataset-configure-redaction/textual-datasets-synthesis-options/synthesis-options-for-specific-entity-types/synthesis-name · https://docs.tonic.ai/textual/textual-integrations/textual-langchain-integration

**Date:** docs current (fetched 2026-09-20).

Q-T1: "To replace source names with a names that have the same gender, check **Preserve Gender**. For example, when this is checked, John might be replaced with Michael … John would not be replaced with Mary"
Q-T2: "To treat the same name with different casing as different source values, check **Is Consistency Case Sensitive**. … when this is not checked, then john and John are treated as the same source value, and get the same replacement."
Q-T3 (index): no page titled re-identify / unredact / reverse exists in the 819-line index; pages present: "Textual Agent", "Textual LangChain integration", per-entity synthesis options (name, location, phone, DOB, date/time).

| # | Verdict | Grade |
|---|---|---|
| 1 | **Not documented in the current index** (prior June note said "reversible proxy"; nothing found now) | [B] absence |
| 2, 3, 6, 7, 8, 9, 13 | **No / not documented** | — |
| 4 | **Yes for gender-preserving, consistent name synthesis** (Q-T1/Q-T2); no checksum statement | [A] |
| 5 | Consistency within a dataset job (case-sensitivity option) | [A] |
| 10 | No | — |
| 12 | Self-hosted install docs exist ("textual-install-administer"); pricing not on docs | [B] |

---

## 5. LiteLLM (Enterprise guardrails · Presidio guardrail)

**URLs:** https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2 · https://docs.litellm.ai/docs/tutorials/presidio_pii_masking · https://github.com/BerriAI/litellm/issues/22821 (created 2026-03-04, closed, updated 2026-06-12)

Q-LL1 (docs modes): "`pre_call`: Run before LLM call, on input · `post_call`: Run after LLM call, on input & output · `logging_only`: … Not on the actual llm api request / response · `pre_mcp_call`: Run before MCP call, on input. Use this mode when you want to apply PII masking/blocking for MCP requests"
Q-LL2 (docs output parsing): "LLM responses can sometimes contain the masked tokens. For presidio 'replace' operations, LiteLLM can check the LLM response and replace the masked token with the user-submitted values." Languages: "`en` - English (default), `es` - Spanish, `de` - German".
Q-LL3 (issue #22821, verbatim): "PII is masked on input but never unmasked in responses, and using tools (e.g. via Claude Code) causes a 400 error." · "No unmask path in `apply_guardrail()`: Only a masking path exists — when called with `input_type=\"response\"` and `output_parse_pii=True`, PII tokens are never restored." · "`AnthropicMessagesHandler.process_output_response()` creates a fresh `request_data` dict, discarding any `pii_tokens` stored during input masking."

| # | Verdict | Grade |
|---|---|---|
| 1 | Yes (per-request `pii_tokens`, exact `<PERSON>`-style placeholders; Presidio's `<PERSON>` is not even unique per entity) | [A] |
| 2 | **No** — `pre_mcp_call` masks the *input to the tool*, i.e. the tool receives masked values; no restore of tool arguments exists; presence of tools broke the Anthropic path (Q-LL3) | [A] |
| 3 | `presidio_filter_scope: both` can mask MCP output — detection-only, no vault/consistency | [B] |
| 4 | No (Presidio placeholders) | [A] |
| 5 | Per-request only; `pii_tokens` lives in `request_data` (Q-LL3) | [A] |
| 6 | Streaming unmask exists for OpenAI-shaped chunks; was broken for Anthropic SSE bytes (Q-LL3) | [A] |
| 7, 8, 9, 10, 11, 13 | No | — |
| 12 | OSS gateway, self-host; enterprise licence | [A] |

---

## 6. Portkey → **Prisma AIRS AI Gateway** (Palo Alto Networks)

**URLs:** https://docs.portkey.ai/docs/product/guardrails/pii-redaction · https://docs.portkey.ai/docs/guides/use-cases/guardrail-pii-use-case · https://www.paloaltonetworks.com/company/press/2026/palo-alto-networks-completes-acquisition-of-portkey-to-secure-ai-agents (2026-05-29) · https://investors.paloaltonetworks.com/… (intent 2026-04-30) · https://docs.portkey.ai/docs/changelog/2026/april

Q-PK1 (PANW press 2026-05-29): "today announced it has closed the acquisition of Portkey, a pioneer in AI Gateways. … By establishing Portkey as the core AI Gateway for Prisma AIRS"
Q-PK2 (docs, PII Redaction): "Toggle the **Redact PII** option to automatically replace detected PII with placeholders." · "Security Considerations: Redaction is irreversible by design" · "Limitations: Transformation is one-way (non-reversible)"
Q-PK3 (docs banner, 2026-08-03): "Portkey is now PRISMA AIRS AI Gateway, generally available for all enterprises."
Q-PK4 (secondary, Startup Stash buyer's guide): "General availability started 16 July 2026" · "PII detection and Moderation are 'Not included' in gateway guardrails. Docs send those to AI Runtime" [C — trade guide quoting docs; not re-verified].

| # | Verdict | Grade |
|---|---|---|
| 1 | **No — irreversible by design** | [A] |
| 2–11, 13 | No | [A]/[B] |
| 12 | OSS gateway self-host; enterprise via PANW | [A] |

---

## 7. Kong AI Gateway — AI PII Sanitizer plugin

**URL:** https://developer.konghq.com/plugins/ai-sanitizer/ (saved `kong-ai-sanitizer.txt`)

Q-K1: "It supports multiple sanitization modes, including replacing sensitive information with fixed placeholders or generating synthetic replacements that retain category-specific characteristics. Additionally, AI PII Sanitizer offers an optional restoration feature, allowing the original request data to be reinstated in responses when needed."
Q-K2: "placeholder: Replaces sensitive data with a fixed placeholder pattern, PLACEHOLDER{i}, where i is a sequence number. Identical original values receive the same placeholder. … synthetic: Redact the sensitive data with a word in the same type. For example, the name John might be replaced with Amir."
Q-K3: "(Only applies to input data sanitization) If restoration is enabled, the plugin restores the original request data in responses before returning them to the client." · "Available language tags: -en -es -fr -de -it -ja -ko -pt -tr" · "it will be downloaded at startup from the spaCy models repository" (i.e. Presidio/spaCy-class engine).

| # | Verdict | Grade |
|---|---|---|
| 1 | Yes, per request | [A] |
| 2, 3 | No (request body / response body only; nothing on tool calls) | [A absence] |
| 4 | Synthetic "same type" words; no gender/checksum statement | [B] |
| 5 | Per-request placeholder consistency only | [A] |
| 6, 7, 8, 9, 11, 13 | No / not documented | — |
| 10 | No; 9 languages, no Russian | [A] |
| 12 | Self-hosted Docker service (private registry) + Kong Enterprise | [A] |

---

## 8. Cloudflare AI Gateway — DLP (Beta)

**URL:** https://developers.cloudflare.com/ai-gateway/features/dlp/ (saved `cf-dlp.md`)

Q-CF1: "Tool call arguments and results: DLP scans the text content present in the message body, which includes tool call arguments and results if they appear in the JSON request or response payload."
Q-CF2: "Streaming (SSE) responses: DLP buffers the full streamed response before scanning."
Q-CF3: "| Flag | … the original response is returned to the client. | · | Block | The provider response is discarded and replaced with a DLP error response (status `400`). |"

| # | Verdict | Grade |
|---|---|---|
| 1 | **No** — actions are Flag / Block only | [A] |
| 2, 3 | **Scanned, not transformed** (Q-CF1) — the only gateway that explicitly names tool-call args/results, and it blocks them | [A] |
| 4–11, 13 | No | [A] |
| 12 | Cloudflare SaaS only | [A] |

---

## 9. DLP / firewall class (not individually excavated this round)

Prompt Security (SentinelOne), Nightfall, Lakera, Zscaler, Netskope, Palo Alto AI Runtime, Robust Intelligence/Cisco, Arthur. A targeted search for reversible / tool-call-aware PII features dated ≥ 2026-06-01 returned nothing relevant (saved in session log). Their documented model remains detect → block/flag/redact (irreversible); LiteLLM lists "PANW Prisma AIRS - Threat detection, DLP, and policy enforcement" and "Lakera - AI safety guardrails" as apply_guardrail providers, none with an unmask path. Grade [B] absence-of-evidence; treat every checklist row as **No**.

---

## 10. NEW since June 2026 (entrants and changes)

| What | Date | Evidence | Grade |
|---|---|---|---|
| **Palo Alto Networks closed the Portkey acquisition**; Portkey rebranded "Prisma AIRS AI Gateway" (GA 16 Jul 2026); PII redaction remains irreversible | 2026-05-29 close; docs banner 2026-08-03 | Q-PK1..4 | [A]/[C] |
| **Protecto Privacy Gateway for AI Chat** — first Western engineering write-up that states tool-argument resolution + tool-result re-masking with a named limitation (per-user, not per-tool/field); LibreChat only; OpenAI/Gemini only | Sep 2026 | Q-P1..P4 | [B] |
| **Limina `limina-postprocessor`** — synthetic, gender-matched (90.7%), globally-unique names with within-doc coreference and partial-mention reuse; batch ETL over DEID JSON, not the LLM loop | repo created 2026-09-15 | Q-L4 | [A] |
| **Skyflow for Glean** (runtime tokenize-on-ingest + policy rehydration for enterprise search/agents); Skyflow SDKs pushed 2026-09-18; no new public tool-call doc | 2026 | Yahoo/press snippet; GitHub | [C] |
| **Weilliptic TCrypt** (MCP server + API; JSONPath/XPath-selected fields; FPE tokens; threshold-quorum detokenize; WeilChain audit) — structured-field tokenizer the *agent* calls as a tool; no free-text detection claimed | 2026 (LinkedIn post by A. Lakshman; weilliptic.ai) | "it uses native JSONPath/XPath selectors to mask fields locally in-memory using format-preserving execution (tokfpe) or a fixed size execution (tokenize) … (4532-7182-9381-0293 -> 8430-9247-1563-0293)"; "Detokenization requires an identity-gated threshold quorum." | [C] |
| Third-party framing: Arcjet, "How to prevent PII leakage from AI agents" — "Tool call arguments are the leak point most products miss, because the model writes them after every inbound check has run." "Most products in this category cover one or two of the five points well." | 2026 | https://arcjet.com/learn/prevent-pii-leakage-ai-agents | [B] (vendor content, but the claim is a market observation) |
| Lead only (academic, out of scope): Piotrovskyi, "Controlling PII Disclosure in Database MCP Connectors", American Impact Review, 2026-08-10 — "deterministic reversible tokenization, and egress redaction" in a reference MCP DB gateway on synthetic data | 2026-08-10 | https://americanimpactreview.com/article/e2026067 | lead |

No Western product launched between June and September 2026 that documents restoring a substitute the model **rewrote**, conversation-scoped substitutes, declension-aware substitution, or fake-vs-real collision handling.

---

## 11. Cross-product matrix (Y = documented yes · P = partial · A = asserted only · — = no / not documented)

| Item | Skyflow | Protecto | Limina | Tonic | LiteLLM | Portkey/PrismaAIRS | Kong | Cloudflare | TCrypt |
|---|---|---|---|---|---|---|---|---|---|
| 1 Reversible answer | Y | Y | Y | — | Y | — | Y(req) | — | A |
| 2 Tool args restored, JSON valid | A | A (LibreChat; escaping unstated) | — | — | — (masks tool INPUT) | — | — | — (scan/block) | A (agent calls detokenize) |
| 3 Tool results re-masked, same sub | A | A | — | — | P (mask only) | — | — | — (scan) | A |
| 4 FP + gender + checksum-invalid | P (regex FPT; no gender; no checksum) | P (format mode; no gender; no checksum) | P (postprocessor gender 90.7%, batch) | P (gender Y; no checksum) | — | — | P (synthetic word) | — | P (FPE; no checksum) |
| 5 Multi-turn + canonicalisation | P (deterministic; no canon.) | P (deterministic; no canon.) | caller | job-level | request-level | — | request-level | — | — |
| 6 Streaming + tool-delta buffering | — | P | — | — | P | — | — | buffers whole response | — |
| 7 Model REWROTE substitute | — (exact token) | **No** (documented failure) | P (`model` param, undisclosed) | — | — | — | — | — | — |
| 8 Memory / cross-conversation scope | — | namespace-global | n/a | — | — | — | — | — | — |
| 9 Partial mention / correction | — | — | P (batch only) | — | — | — | — | — | — |
| 10 Declension-aware | — | — | — | — | — | — | — | — | — |
| 11 Fake==real collision | moot for counters; — for FPT | moot while tags survive; — for formats | — | — | — | — | — | — | — |
| 12 Self-host / residency | SaaS·VPC·BYOC; no price | SaaS·on-prem; no price | container; free tier | self-host | OSS | OSS + PANW | Docker + Enterprise | SaaS | vendor |
| 13 Agent-fidelity measurement | — | "<1%" marketing, no conditions | — | — | — | — | — | — | — |

---

## 12. Verdict

**Which checklist items NO Western commercial product covers (confidence):**

- **7 — restore when the model rewrote the substitute (inflected, transliterated, initials, hyphen-joined, digits reformatted, partial name): NOT covered — high confidence (≈0.9).** Protecto documents the modified/truncated token as an unmask failure and returns the masked value; Skyflow's SDK re-identify is exact-token substitution on flat text; LiteLLM/Kong restore exact placeholders per request; Limina's only gesture is an optional `model` hint "accounting for the model's unique behaviour surrounding redaction markers" with no disclosed mechanism. The reason is structural: every product uses tokens *outside* the real-value space (`NAME_1`, `<PERSON>VJYe 03W</PERSON>`, `PLACEHOLDER{i}`), which buys collision-freedom by construction and forfeits any grammatical/scriptural handling — a model cannot decline `NAME_1`, and if it does the mapping is lost.
- **8 — agent-memory / cross-conversation scoping: NOT covered — high confidence (≈0.85).** The two vault products scope determinism to the vault/namespace (customer), never to a conversation; Protecto's gateway rebuilds "protected history" from the host's own conversation record, i.e. the host, not the vault, defines the boundary. No product describes a rule for a substitute echoed from another dialogue.
- **10 — declension-aware masking/restore: NOT covered — very high confidence (≈0.95).** "40+ / 50+ / 52 languages" is detection coverage; no product mentions morphology, case agreement or an inflected substitute. Kong ships 9 languages and none Cyrillic.
- **11 — fake-equals-real collision: NOT addressed — high confidence (≈0.85).** It is moot for counter/UUID/tagged tokens, but the moment a product offers format-preserving or synthetic substitutes (Skyflow regex-FPT, Protecto "format" mode, Kong "synthetic", Tonic/Limina synthetic names, TCrypt FPE) the substitute re-enters the real-value space and no product states a checksum-invalid or "refuse a candidate equal to any stored real value" rule.
- **13 — a published measurement of "agent unaffected" (tool-call fidelity through the layer, with conditions): NOT covered — very high confidence (≈0.95).** The only numbers are Protecto's "<1% Response accuracy degradation … internal benchmark" (no corpus, no conditions, no tool-call axis) and Skyflow's gated "Accuracy" page (not published; the docs' own MCP says no precision/recall/latency is published). Protecto's engineers explicitly say of a related effect: "We haven't published a retrieval-quality number for that effect because we don't have one we'd stand behind yet."
- **9 — partial mentions / in-dialogue corrections: NOT covered in the LLM loop — high confidence (≈0.85);** Limina's batch postprocessor does a `_smart_match` from surname to an already-assigned full name, per document, in ETL.
- **2 — tool-call args with JSON kept valid: covered by ASSERTION only (Skyflow marketing; Protecto for LibreChat).** Neither states how a real value containing quotes is escaped back into a JSON string; Cloudflare is the only gateway that names tool-call arguments in its docs, and it scans/blocks them.
- **4/5/6** are partially covered by Skyflow and Protecto (deterministic tokens; format modes; streamed-content unmask); canonicalisation of surface variants and gender-matched fake names inside the loop are not.

**On the owner's suspicion re Skyflow:** confirmed as far as public evidence reaches. Skyflow has the plumbing story (vault + policy-gated "rehydration" + a proxy positioned between MCP servers and backends) and the deterministic-token property, but every public artefact — SDK source, open docs, blog — shows a flat-text, exact-token re-identify with no tool-argument primitive, no agent-form tolerance, no conversation scope, no morphology, and no published fidelity number. The specific "Agents" and "Accuracy" pages exist in the nav and are login-gated; this report could not read them, so the residual uncertainty is "Skyflow may document more behind login" — but their own anonymous docs index does not contain them, and nothing on GitHub (14 repos, all SDK/sample) touches it.

**Closest competitor on the transparency axis today:** Protecto (Sep 2026) — and its own text bounds it: one host (LibreChat), two providers, per-user authorization, exact-token resolution, failure = masked value reaches the tool.
