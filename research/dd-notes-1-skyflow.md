# DD Notes 1 — Skyflow: PII protection for LLM agents across tool-calls

Research date: 2026-06-07. Scope: ONLY Skyflow (LLM Privacy Vault / GPT Privacy Vault, MCP Gateway + MCP Server SDK, Runtime AI Data Security, token mechanics, polymorphic encryption, governance, audit). One competitor note (Protecto) at the end.

Evidence grades: **[A]** proven/documented in official primary · **[B]** supported/single source · **[C]** asserted by Skyflow as rationale · **[D]** folklore/inference.

---

## 0. TL;DR of the decoded mechanism

Skyflow is **not** a single "intercept-the-function-call" widget. It is a **data privacy vault** (tokenize on the way in, store ciphertext, detokenize under policy on the way out) that Skyflow has wrapped in three placements for agentic/MCP workflows. The actual protection primitives are old and well-documented (insert→token, detokenize→plaintext, redaction levels, deterministic + format-preserving tokens, polymorphic encryption, PBAC governance). The "AI agent / tool-call" story is those same primitives positioned at two new chokepoints:

1. **At the data source** (proxy / gateway): de-identify tool OUTPUT (data fetched from CRM/EHR/DB) *before* it reaches the agent or model.
2. **At point of use** (rehydration): restore plaintext "only at the exact point for a specific task in a workflow where it is permitted and required" — i.e. when a downstream tool genuinely needs the real value (e.g. send to Twilio/email).

The model sees and reasons over **tokens/masked values**; tokens are deterministic + format/entity preserving so reasoning, matching and validators don't break; detokenization is gated by **PBAC + a role-scoped Skyflow token obtained via server-side OAuth token exchange**, and every access/transform/rehydration is logged at field level. The precise interception/parse logic of the Gateway and SDK (how it parses an MCP message, which fields it picks, the rehydration trigger semantics) is **proprietary and not publicly documented** — boundary called out in §6.

---

## 1. The tool-call / function-call mechanism

### 1.1 The base de-identify→re-identify loop (prompt/response path) [A]
This is the canonical Skyflow GPT/LLM Privacy Vault flow and the substrate everything else builds on.

> "User input is sent from the front-end UI directly to Skyflow. Skyflow detects sensitive data that's included in this input data according to the fields defined in the sensitive data dictionary and replaces this sensitive data with deterministic tokens while storing the plaintext sensitive data securely within the vault." [A]

> "Skyflow-generated tokens from the LLM response are replaced with plaintext sensitive data (based on defined data governance policies) and returned to the user in the context of LLM-generated text." [A]

Governing principle (Skyflow's own framing): de-identify **as early as possible**, re-identify **as late as possible**. [C]
- Source: https://www.skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault
- Source: https://www.skyflow.com/post/llm-data-privacy-how-to-implement-effective-data-de-identification

**Note:** the input is sent **directly from the UI to Skyflow first** (Skyflow is on the ingress path), not after the model. So the model never sees plaintext on the prompt side. This is the "two-way" property: tokenize inbound, detokenize outbound.

### 1.2 Tool-call protection in the MCP architecture [A/B]
Primary source: https://www.skyflow.com/post/building-secure-ai-agent-architecture-mcp (worked insurance example) and the launch PR https://www.businesswire.com/news/home/20250731908143 (Aug 2025).

The documented direction of protection is **tool OUTPUT → agent**, via a proxy that wraps the queries the tool makes to its backend:

> "This gateway wraps outbound queries, enforcing redaction, masking, and tokenization before any sensitive data reaches the agent or underlying model." [A]

Worked insurance/claims example (verbatim fragments) — agent handling a denied medical claim must hit CRM + policy DB + claims system: [A]
> "The CRM call retrieves a tokenized version of the customer's name and member ID, ensuring only necessary identifiers are used in the LLM prompt."
> "Insurance and claim details are fetched, but PII like date of birth and address are masked."
> "The assistant receives just enough structured data to reason through the rejection—the claim was denied due to a missing document—and to propose a draft response."
> Then a human-in-the-loop "Plan mode" sends the proposed message + rationale to a human rep for approval before it reaches the customer.

**Decoded sequence of operations (per tool call):** [A for steps drawn from quotes, B for ordering inference]
1. Agent (LLM) decides to call a tool (e.g. `crm.getCustomer`, `claims.lookup`).
2. The call's backend traffic passes through the **Skyflow MCP Gateway** (proxy in front of the data source) OR through a Skyflow-**SDK-wrapped** tool function.
3. Skyflow inspects the **response/payload** from the data source, classifies sensitive fields against the sensitive-data dictionary / vault schema, and applies a per-field **polymorphic transform**: tokenize (name, member ID → deterministic token), mask (DOB, address), or pass-through, per policy + the caller's permissions.
4. The **de-identified** structured result is what enters the LLM prompt/context. The model reasons over tokens/masked entities.
5. If a downstream action needs the real value, **rehydration** restores plaintext **only at that exact step** and only if the caller's role permits (see §1.3). Final user-facing text gets tokens swapped back to plaintext under governance, as in the base loop (§1.1).

**Important nuance / gap:** Skyflow's public material describes detokenizing/masking what comes **out** of a tool, and rehydrating at the **point of use** of a *downstream* tool. It does **not** publicly spell out a clean "the model emits a token as a function argument → gateway silently detokenizes that argument in-flight → runs the tool on plaintext → re-tokenizes the result" round-trip with concrete parse logic. The "detokenize the arg server-side at execution" behavior is **implied** by the rehydration statement in §1.3 but the exact trigger/parse is not documented. Grade the literal arg-detokenize-then-retokenize round-trip as **[B/D]** (inferred), while the output-side de-identification is **[A]**.

### 1.3 "Rehydration" — the point-of-use detokenization (the closest thing to arg-detokenize) [A]
Sharpest primary statement is the Dec 2025 Runtime AI Data Security launch:
> "Fine-grained, governed restoration of original values only at the exact point for a specific task in a workflow where it is permitted and required, allowing agents to finish end-to-end tasks without overexposing sensitive data." [A]
- Source: https://www.helpnetsecurity.com/2025/12/02/skyflow-runtime-ai-data-security-platform-aws/ (covers https://www.businesswire.com/news/home/20251201650237)

This is the mechanism that lets a tool that *must* have plaintext (e.g. "send SMS via Twilio", "email the customer") get the real value at the moment of execution while the model/agent context never held it. It is "rehydration" in the gateway's vocabulary: masking/tokenizing/**rehydrating** fields "contextually based on policy and user permissions." [A] (https://www.skyflow.com/post/building-secure-ai-agent-architecture-mcp)

### 1.4 The "polymorphic data protection engine" framing [A/C]
> "Skyflow's polymorphic data protection engine dynamically transforms sensitive information in real time by masking, tokenizing, or rehydrating fields based on policy and user permissions." [A]
This single engine choosing per-field, per-policy among {mask | tokenize | rehydrate | pass} is the heart of the agent story. The "polymorphic" word is doing double duty — see §3.4 (it is also the name of the underlying encryption patent).

---

## 2. Integration modes — what each intercepts and where it sits

All three named explicitly in the MCP blog and the Aug-2025 PR. Two deployment models marketed: **MCP Gateway** (proxy) and **MCP Server SDK** (embeddable lib). The SDK splits into "wrap existing" vs "embed new." [A]

| Mode | Where it sits | What it intercepts | Code change | Quote |
|---|---|---|---|---|
| **MCP Gateway (zero-code proxy)** | "A proxy layer (which can be integrated into existing proxy servers) that sits between MCP servers or agents and backend data sources." Inserted "as a proxy between the tool and the data source (e.g. Salesforce)." | All traffic flowing tool↔data-source; transforms payloads in flight | None — "without requiring application changes" | "insert the Skyflow MCP Gateway as a proxy between the tool and the data source…allowing all traffic to flow through Skyflow" [A] |
| **MCP Server SDK — wrap** | Inside an MCP server you can edit | "wrap existing functions, intercepting inputs and outputs to apply redaction and enforce policies" | Light wrap of tool fns | "you can use the Skyflow MCP Server SDK to wrap existing functions" [A] |
| **MCP Server SDK — embed** | Inside a new MCP server you build | Privacy controls built in at design time | Full | "If you're building a new MCP server…you can embed the SDK directly" [A] |

- Source: https://www.skyflow.com/post/building-secure-ai-agent-architecture-mcp
- Source: https://www.businesswire.com/news/home/20250731908143/en/Skyflow-Unveils-MCP-Data-Security-for-Enterprises-and-SaaS-Companies

SDK description (PR): "an embeddable library that developers can use to build privacy controls directly into MCP server implementations and agentic apps." [A]

**AWS placement variants (Dec 2025):** integrates with **Amazon AgentCore** by "binding identity to each agent and enforcing 'minimum necessary' access based on user, agent, purpose, data type, and regulatory rules"; with **Amazon Quick Suite** does "runtime sensitive data protection, inspecting and de-identifying PII/PHI before it reaches any agent or model." [A] (helpnetsecurity, Dec 2025). Also on Google Cloud Marketplace (Oct 2025, businesswire 20251020852053). [B]

---

## 3. Token properties

### 3.1 Token type catalog [A]
From the tokenization overview docs: Skyflow offers "a variety of token types, including random tokens, format-preserving tokens, deterministic tokens, and more." Concrete types: **random/UUID**, **deterministic**, **non-deterministic ("cell tokens")**, **format-preserving**, **length-preserving**, **transient (TTL)**.
- Source: https://docs.skyflow.com/docs/tokenization/overview
- Source: https://docs.skyflow.com/docs/fundamentals/product-overview

Documented examples (verbatim from docs):
- Email `johndoe@acme.com` → **format-preserving** token `bwe09f@fg7d8.com`; or → **UUID** token `c7db3f3a-5d01-4a98-961e-9cbdb6241b0d`. [A]
- **Deterministic:** two inserts of `johndoe@acme.com` both → `bwe09f@fg7d8.com`. "Deterministic tokens enable matching and JOINing through tokens" and "provide the same token for raw values that are inserted multiple times." [A]
- **Non-deterministic / cell tokens:** same email → different tokens (`oel87e@wx8w1.com`, `tqc42k@vd0n3.com`); "do not change when the underlying value changes so no ongoing sync is required." [A]
- **Transient fields:** "enable temporary storage of data and return non-deterministic tokens. You define the time to live (TTL) of the data." [A]

### 3.2 Format-preserving = tools + validators don't break [A]
> "The benefit of format preservation is that you can replace the sensitive values in your database without changing the schema or any validation rules." [A]
- Email tokens still look like emails; "an email address requires a format-preserving token, but not necessarily a length-preserving token."
- "Format-preserving phone numbers are both format-preserving and length-preserving."
- Built-in email data type already ships with "a deterministic format-preserving tokenization method" preset. [A]
- Source: https://docs.skyflow.com/docs/tokenization/overview ; https://www.skyflow.com/post/overcoming-the-challenges-and-limitations-of-tokenization
This is exactly what keeps a tool's input validators (regex for email/phone/card) and the model's pattern-reasoning intact while the value is fake.

### 3.3 Entity consistency / scope = column groups (a.k.a. token groups) [A]
> "Column groups make sure that fields across tables use the same tokenization settings and return consistent tokens. As long as they're in the same column group, a value in `email` columns across multiple tables return the same token value." [A]
Scoping subtlety (the "Austin problem"): the column group "defines the boundaries within which your deterministic tokens span… two First Name values of 'Austin' will generate the same UUID, but the City of 'Austin' will result in a different UUID." [A]
- Source: https://docs.skyflow.com/docs/tokenization/overview ; https://www.skyflow.com/post/solving-the-austin-problem-with-a-data-privacy-vault
**Implication for agents:** within a session/context, the same person's email is the same token everywhere, so the model can coreference/join entities — but homographs across field types stay distinct. This is the "entity-preserving transformations so agents can reason over obfuscated data" claim. [A/C]

### 3.4 "Polymorphic" encryption (distinct from polymorphic *data protection engine*) [A]
The underlying at-rest crypto. Patents: **US20230005391A1** and **US20240331576A1**, assignee SKYFLOW, INC. ("Polymorphic encryption for security of a data vault").
Patent abstract (verbatim): [A]
> "the data vault has a primary partition with a first subset of records having an encrypted value… encrypted according to a first encryption scheme. A secondary partition has a second subset of the records encrypted according to a second encryption scheme that is different from the first… The first encryption scheme is configured to permit a first set of operations on the values when the values are encrypted and the second encryption scheme is configured to permit a second set of operations…"
- Mechanism: **multiple encryption schemes over the same data in separate partitions**, each scheme permitting a different operation class on ciphertext: **exact-match**, **aggregation** (SUM/AVG/MAX), **order/range** (>,<). Different field portions encrypted differently (e.g. area code encrypted for aggregation; SSN last-4 hashed for exact-match identity check). [A]
- Positioned vs homomorphic: "tailored to specific functions associated with real-world use cases," "limiting the operational search space to practical uses… avoiding the latency issues associated with homomorphic encryption." [C]
- Twilio example: phone number partly encrypted for analytics, but "integrating with Twilio will require the full phone number" — illustrates per-use rehydration. [A/C]
- Sources: https://patents.google.com/patent/US20230005391A1/en ; https://www.skyflow.com/post/what-is-polymorphic-encryption ; https://www.skyflow.com/encryption

### 3.5 Detokenization governance / redaction levels [A]
The detokenize call carries a per-token **redaction type**; SDK enum: `DEFAULT`, `REDACTED`, `MASKED`, `PLAIN_TEXT`. The requested redaction "will be honored up to the maximum level allowed by the user's role." So a token resolves to plaintext, a partial mask, or stays redacted depending on caller policy. [A]
- Source: https://github.com/skyflowapi/skyflow-python (README) ; https://docs.descope.com/mcp/integrations/skyflow

Python SDK shapes (verbatim): [A]
```python
# insert → returns tokens
insert_request = InsertRequest(table='table1',
    values=[{'<FIELD_NAME_1>': '<VALUE_1>'}], return_tokens=True)
response = skyflow_client.vault('<VAULT_ID>').insert(insert_request)

# detokenize → tokens back to (possibly redacted) plaintext
from skyflow.vault.tokens import DetokenizeRequest
from skyflow.utils.enums import RedactionType
detokenize_request = DetokenizeRequest(
    data=[{'token': 'token1', 'redaction_type': RedactionType.PLAIN_TEXT}],
    continue_on_error=True)
response = skyflow_client.vault('<VAULT_ID>').detokenize(detokenize_request)
```
SDKs exist for Node, Python, Java, Go (github.com/skyflowapi/*). [A]

---

## 4. Access control & audit

### 4.1 Governance model [A]
- **PBAC** umbrella combining **RBAC** ("Assign roles to users and machine identities") + **ABAC** ("Define context to enforce access even at the row-level"). Field/column-level visibility + row-level security + per-role max redaction. [A]
- Source: https://docs.skyflow.com/docs/fundamentals/product-overview

### 4.2 How a tool-call gets the right to detokenize — the real auth flow [A]
The Descope×Skyflow MCP integration is the most concrete primary evidence of how detokenization is *authorized inside a tool call*:
- **OAuth 2.0 Token Exchange (RFC 8693)**: user authenticates to MCP server (Descope) → server **exchanges** the Descope token for a **Skyflow token** via Skyflow **STS**, **server-side** → Skyflow evaluates token claims (roles → `request.context.roles`) to assign permissions → tool calls Skyflow vault with the role-scoped token → vault auto-enforces field visibility, redaction level, table + row-level security. [A]
- Load-bearing: "the token exchange occurs server-side during authentication. **Skyflow tokens are never exposed to the client or the LLM.**" [A]
- STS config + token-exchange + tool-call code (verbatim):
```bash
curl -X POST https://manage.skyflowapis.com/v1/sts/config -H "Authorization: Bearer <token>" \
 -d '{"issuer":"https://api.descope.com/v1/apps/customized/<PID>",
      "publicKeyJWKURI":"https://api.descope.com/<PID>/.well-known/jwks.json",
      "contextClaims":["roles"],"serviceAccountIDs":["<SA_ID>"]}'

curl -X POST https://manage.skyflowapis.com/v1/auth/sts/token \
 -d '{"grant_type":"urn:ietf:params:oauth:grant-type:token-exchange",
      "subject_token":"<DESCOPE_ACCESS_TOKEN>",
      "subject_token_type":"urn:ietf:params:oauth:token-type:jwt",
      "service_account_id":"<SA_ID>"}'
```
```javascript
const skyflowToken = context?.authInfo?.extra?.skyflowToken;
await fetch(vaultUrl, { headers: { Authorization: `Bearer ${skyflowToken}` }});
```
- Conditional policy example: `"'Viewer' in request.context.roles"` activates that role's masking/redaction/row policies. [A]
- Source: https://docs.descope.com/mcp/integrations/skyflow

**This resolves the "who can detokenize what" question:** the *agent's caller identity* is bound to a Skyflow role via server-side token exchange; the vault — not the agent, not the model — decides per field whether the token resolves to PLAIN_TEXT / MASKED / REDACTED. The LLM never holds a vault credential.

### 4.3 Audit [A]
- Base vault: "Isolating sensitive data in Skyflow LLM Privacy Vault also gives your company a sensitive data audit trail." [A]
- Runtime AI platform (Dec 2025): "field-level logging for complete auditability," recording "every access, transformation, residency decision, and rehydration event." [A]
- Source: https://www.helpnetsecurity.com/2025/12/02/skyflow-runtime-ai-data-security-platform-aws/

---

## 5. Adjacent / supporting facts
- **Vault architecture** = Isolate / Protect / Govern / Use (zero-trust, data segregated from app infra). [A] (docs product-overview)
- **Sensitive data dictionary** = customer-defined terms/fields that must be tokenized/withheld from the model. [A]
- **Secure embeddings / governed vectorization** for RAG so vectors don't leak raw PII (Dec 2025). [A/C]
- **Data residency** decisions are part of the runtime policy + logged. [B]
- GPT Privacy Vault first launched May 2023 (businesswire 20230518005391); LLM Privacy Vault is the evolution; MCP Data Security Aug 2025; Runtime AI Data Security (AgentCore/Quick Suite) Dec 2025. [A] (timeline from PRs)

---

## 6. What is proprietary / NOT publicly knowable (the boundary)

Explicitly **not** in primary sources (treat any specific claim here as unknown, not [A]):
1. **Gateway/SDK internal parse + intercept logic.** How the MCP Gateway actually parses an MCP/JSON-RPC message, which fields it selects, how it matches them to vault schema in flight, and the exact rehydration *trigger* (does the model emit a token literal as an arg? does the gateway pattern-match tokens in arbitrary tool args? is it schema-driven?) — **undocumented**. The clean "detokenize-arg→run-tool→re-tokenize-result" round-trip is **inferred [B/D]**, not stated.
2. **Sensitive-data detection engine internals.** What classifier/NER/regex/ML detects PII in free-text prompts and tool outputs (precision/recall, model, on-prem vs cloud) — not disclosed. (Boundary: Presidio etc. are other agents' turf; Skyflow's own detector internals are simply private.)
3. **Token generation algorithm.** How deterministic format-preserving tokens are derived (FPE cipher? keyed PRF? lookup table?), key management, collision handling — only outputs/examples shown, not the construction. (FPE *libraries* are off-limits per task; here the point is Skyflow doesn't reveal its own.)
4. **Polymorphic encryption scheme specifics.** Patent gives the partition/operation-class framing but not the concrete ciphers per operation, key hierarchy, or how partitions stay consistent on update.
5. **Performance/latency numbers** for inline transformation per tool call — none published; the "low latency vs homomorphic" claim is qualitative [C].
6. **Exact MCP Gateway config/API surface** (the Gateway's own admin API, policy DSL) — not in public docs as of research date; the Descope flow shows the *vault* API, not the Gateway's internal policy language.

Any number or precise internal claim about the above should be marked **conditional / unverified**.

---

## 7. Competitor note (max 1 paragraph) — Protecto
Encountered as a direct competitor on tool-call PII. **Protecto** markets a similar "tokenize PII before the LLM, detokenize the response" pattern but emphasizes *format- and context-preserving* tokens generated by its own PII detection, and an agent/MCP-oriented "Protecto Vault / Data Guardrails" that intercepts agent I/O. Mechanistically comparable to Skyflow (de-identify in, re-identify out, deterministic format-preserving tokens) — the differentiators it claims are detection accuracy and a lighter-weight token-vault vs Skyflow's full polymorphic-encryption data-residency platform. Not independently verified here; flagged only as a lead for the competitor-coverage agent. [D]

---

## 8. Source ledger (primary first)
- LLM/GPT Privacy Vault flow: https://www.skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault [A]
- De-identify/re-identify how-to: https://www.skyflow.com/post/llm-data-privacy-how-to-implement-effective-data-de-identification [A]
- MCP architecture + integration modes + insurance example: https://www.skyflow.com/post/building-secure-ai-agent-architecture-mcp [A]
- MCP Data Security launch PR (Aug 2025): https://www.businesswire.com/news/home/20250731908143 [A]
- Runtime AI Data Security / AgentCore / rehydration + audit (Dec 2025): https://www.helpnetsecurity.com/2025/12/02/skyflow-runtime-ai-data-security-platform-aws/ ; https://www.businesswire.com/news/home/20251201650237 [A]
- Tokenization overview (token types, examples, column groups): https://docs.skyflow.com/docs/tokenization/overview [A]
- Product overview (vault, PBAC/RBAC/ABAC, polymorphic, token variety): https://docs.skyflow.com/docs/fundamentals/product-overview [A]
- Format-preserving / "Austin problem": https://www.skyflow.com/post/overcoming-the-challenges-and-limitations-of-tokenization ; https://www.skyflow.com/post/solving-the-austin-problem-with-a-data-privacy-vault [A]
- Polymorphic encryption patent: https://patents.google.com/patent/US20230005391A1/en (also US20240331576A1) [A]
- Polymorphic encryption blog: https://www.skyflow.com/post/what-is-polymorphic-encryption [A/C]
- Detokenize + redaction + OAuth token-exchange auth flow (most concrete tool-call auth): https://docs.descope.com/mcp/integrations/skyflow [A]
- SDKs (API shapes): https://github.com/skyflowapi/skyflow-python (+ -node, -java, -go) [A]
