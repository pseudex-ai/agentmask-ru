# Western PII Protection for LLM Agents — Tool-Call / Function-Calling SOTA

Research date: 2026-06-07. Focus: reversible PII tokenization for the **function-calling / tool-call** case, and whether this is a **proven PAID category**.

## The technical problem (restated)

An LLM agent must call tools whose parameters ARE the PII: `find_order(phone=...)`, `book(name=...)`. You cannot one-way-mask, because the tool needs the real value. The correct pattern is **reversible tokenization with a vault**:

1. Real PII → token **before** the model sees it.
2. Model reasons over tokens, emits a tool call containing tokens.
3. Token → real value **server-side, just before tool execution** (detokenize / "rehydrate").
4. Tool result is **re-tokenized before** being returned to the model.
5. Raw PII is rehydrated to plaintext **only** at the final boundary for an authorized human/user, never to the model.

This is sometimes called "two-way data rehydration" (Skyflow) or "de-identify / re-identify" (Private AI/Limina). Key technical requirements: **format-preserving tokens** (token looks like a valid phone/email so downstream validation/regex/tools don't break), **entity consistency / deterministic tokens** (same value → same token within a session so the model can correlate references), and a **secure vault** holding the token↔value map under access control.

---

## 1. Is "PII for LLM" a proven PAID category? — YES. Evidence.

| Signal | Detail | Source |
|---|---|---|
| Skyflow total funding | ~$100M over 4 rounds, 12 investors; latest **$30M Series B-II, 28 Mar 2024**, led by Khosla Ventures (Foundation Capital, Insight Partners; angels Jeff Immelt, Jonathan Bush) | crunchbase.com/organization/skyflow-8a8d ; skyflow.com/press |
| Skyflow scale | Secures ~**1 billion** personal-data records; ~**2 billion vault API calls/quarter**; multi-tens-of-millions ARR run-rate, >2x YoY (early 2024); customers GoodRx, Lenovo | diginomica.com/skyflow-raises-$30m-data-privacy-enterprise-llms ; thebrandhopper.com 2025-07-07 |
| Skyflow enterprise pricing | Quote-based; Vendr internal data shows enterprise contracts ~**$195K/yr**; priced on data-subjects, regions, features | vendr.com/buyer-guides/skyflow ; saasworthy.com |
| Prompt Security acquisition | **SentinelOne acquiring Prompt Security for ~$250M** (announced 5 Aug 2025, cash+stock, closes FY-Q3 2026) — runtime AI security incl. data-leak prevention | finance.yahoo.com ; calcalistech.com ; sec.gov 8-K |
| Palo Alto | Built **Prisma AIRS** (AI Runtime Security) — AI app/model/data/agent protection, prompt-injection + sensitive-data-leak interception | paloaltonetworks.com/prisma/prisma-ai-runtime-security ; pan.dev/airs |
| Private AI → Limina | Rebranded **5 Mar 2026**; total funding **$11.2M** (Lightscape Partners, BDC Capital, U of T, C100, +18 investors); customers Boehringer Ingelheim, Zurich Insurance, MUFG Bank, Providence Health | getlimina.ai/en/blog/private-ai-rebrands-limina ; pitchbook 434266-39 |
| Protecto | Launched **Protecto Vault** (10 Dec 2025) — API-first, pay-as-you-go SaaS for AI-agent builders; integrates n8n, LangGraph, Zapier, MCP | helpnetsecurity.com/2025/12/10/protecto-vault |
| HoundDog.ai | Raised **$3.1M** (Mozilla Ventures, E14, Amjad Masad) — but this is static *code* scanning, not runtime | pulse2.com ; crunchbase.com/organization/hounddog-ai |
| Opaque Systems | Confidential-AI platform on Azure Marketplace (Apr 2025); "Opaque Studio" for confidential AI agents; TEE-based | prnewswire.com 302432859 ; opaque.co |

**Verdict:** Multiple funded vendors, one $250M acquisition, an established $100M-funded category leader with real ARR/enterprise ACVs, and the hyperscalers (AWS AgentCore integration, Cloudflare, Palo Alto, Microsoft) shipping adjacent product. This is a **proven, paid, and consolidating** category as of mid-2026.

---

## 2. Who handles the TOOL-CALL case specifically (and how)

Most "PII for LLM" tools only do **prompt/response masking** (chat in, chat out). The tool-call case — tokenize args, detokenize before tool exec, re-tokenize results — is handled by a small subset.

### Skyflow LLM Privacy Vault / Runtime AI Data Security — STRONGEST, tool-call native
- **Tool-call handling: YES, explicitly.** Skyflow launched an **Agentic AI Security & Privacy Layer** (Dec 2024) and an **MCP Data Protection Layer** (mid-2025). The **MCP Gateway acts as a proxy between the agent/MCP server and the backend tool/data source**, so all tool traffic flows through Skyflow.
  - Source: skyflow.com/post/building-secure-ai-agent-architecture-mcp ; businesswire.com/news/home/20241202242238
- **Two-way data rehydration:** "de-identification of sensitive fields before reaching the model" on the way in; "contextual re-identification only for authorized users and responses" on the way out. **Rehydration happens at "the exact point for a specific task in a workflow."**
  - Source: helpnetsecurity.com/2025/12/02/skyflow-runtime-ai-data-security-platform-aws
- **Three integration patterns** (key architecture detail):
  1. **Gateway Proxy** (no code access) — drop Skyflow MCP Gateway between SaaS tool and data source.
  2. **SDK wrapping** (partial access) — Skyflow MCP Server SDK intercepts functions.
  3. **Embedded SDK** (full control) — build privacy controls into the MCP server.
- **Format-preserving tokenization: YES.** PartyRock engineering blog shows name → UUID token, phone → **format-preserving token `PHONE:(765) 978-2342`** (keeps phone structure). `tokenizePii()` → Lambda → Skyflow detect endpoint; `reIdentifyData()` restores via token map; production guidance is to use the detokenize API with fine-grained access controls.
  - Source: skyflow.com/post/adding-a-privacy-layer-to-aws-partyrock
- **Deterministic / entity consistency: YES.** "Skyflow-generated tokens … are deterministic, meaning that a given sensitive data value will consistently tokenize into the same token string." Marketed as "entity-preserving transformations so agents can reason over obfuscated data."
  - Source: skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault
- **Underlying tech:** API-first data privacy vault, **tokenization + "polymorphic encryption"**, fine-grained access controls (who/what agent/purpose/data-type/region). AWS AgentCore + Amazon Quick Suite runtime integration (Dec 2025). Compliance posture GDPR/HIPAA/PCI/CCPA.
- **Ecosystem:** Descope + Skyflow joint pattern for MCP data controls (descope.com/blog/post/descope-skyflow-mcp).

### Protecto / Protecto Vault — tool-call/agent-native, less public technical depth
- **Tool-call handling: YES (positioned).** Protecto Vault is an **API-first layer that sits between enterprise data and agents, scanning/masking/rewriting before reaching the AI**; integrates MCP, LangGraph, n8n, Zapier. CBAC (Context-Based Access Control) "validates that requested fields are appropriate for the current task context **before an MCP tool returns data to the LLM**."
  - Source: helpnetsecurity.com/2025/12/10/protecto-vault ; protecto.ai/blog/handling-sensitive-data-mcp-systems-pii-context-aware-security
- **Tokenization:** "entropy-based" tokens (no math link to source), **format/semantic-preserving** so "LLMs still understand what they're working with"; DeepSight detector handles typos/slang.
- **Gaps:** Marketing-level on whether tokens are applied to args, results, or both, and on reversibility mechanics — technical docs (docs.protecto.ai) not exposed in public blogs. Pay-as-you-go pricing.

### Private AI / Limina — reversible de-identify/re-identify, NOT explicitly tool-call
- **Reversible: YES** (redaction, masking, encryption, **tokenization**, pseudonymization, synthetic-PII). **Entity consistency: YES** — "preserves meaning across multiple documents by anonymizing information consistently," catches "credit cards spoken across turns." 50+ entity types, 52 languages, context-aware (not regex).
  - Source: getlimina.ai/en ; aws.amazon.com/marketplace (Private AI)
- **Tool-call: NOT marketed.** Positioned for de-identify→LLM→re-identify on **free text / training / RAG**, not specifically tool-arg interception. A common pattern (reversible mapping → LLM → restore) but not an agent-tool gateway product.

### Tonic Textual — reversible tokens, chat/RAG proxy, NOT tool-call
- **Reversible tokens: YES**, used so "the chatbot can display the original text to users while the LLM processes only redacted data," and to "maintain consistency between chatbot prompts and the underlying RAG system." JSON-aware (key vs value), HTML-aware. Synthesis modes (ReplacementSynthesis, GroupingSynthesis) regenerate realistic format-correct values.
  - Source: tonic.ai/solutions/use-case/llm-privacy-proxy ; docs.tonic.ai
- **Tool-call: NO.** Scope is **free-text user inputs / chatbot / RAG**, not function-call argument interception.

### Microsoft Presidio (OSS) — reversible ONLY via encryption; consistency via LangChain wrapper
- **Reversible: PARTIAL.** Core Presidio is reversible **only for the `encrypt`/`decrypt` operator** (AES-CBC, same key both ways). **Hash, mask, redact, replace are irreversible by design.** `DeanonymizerEngine` needs the original `OperatorResult` location metadata.
  - Source: deepwiki.com/microsoft/presidio/3.2.2-deanonymization ; microsoft.github.io/presidio
- **Entity consistency:** Core Presidio does NOT maintain consistent fake-value mapping by itself. **`PresidioReversibleAnonymizer` (LangChain experimental)** adds a stored mapping so the same value → same fake value and `deanonymize()` reverses it — this is the building-block teams use for a DIY tool-call vault.
  - Source: reference.langchain.com (PresidioReversibleAnonymizer)
- **Tool-call: DIY.** Presidio is the detection+mapping engine; you build the gateway/proxy yourself. Detection-recall risk is on you (NER misses → leaks).

### NOT reversible / NOT tool-call (detection-and-block / redaction guardrails)
- **Nightfall AI** — "Firewall for AI," ML detection, **redact/block/quarantine** prompt-sanitization; no reversible tokenization. (nightfall.ai/blog/prompt-sanitization-5-steps ; help.nightfall.ai)
- **Lakera Guard** — prompt-injection/jailbreak firewall + PII detect/redact; 98%+ detection, <50ms; **flag/block**, not reversible tokenization for tool args. (docs.lakera.ai/guard)
- **Cloudflare AI Gateway / Firewall for AI** — Guardrails via Llama Guard, DLP scanning to **block/flag** PII; not reversible, no streaming yet. (blog.cloudflare.com/guardrails-in-ai-gateway)
- **Palo Alto Prisma AIRS** — runtime detection/blocking of data leaks, prompt injection, agent identity; guardrail not vault-tokenization. (paloaltonetworks.com/prisma/prisma-ai-runtime-security)
- **Prompt Security (→SentinelOne)** — runtime data-leak prevention; redaction/guardrail orientation. ($250M acquisition is the category proof-point.)
- **Opaque Systems** — orthogonal approach: **confidential computing / TEEs** so raw data is processed inside an attested enclave invisible to the cloud/model host — protects data-in-use cryptographically rather than tokenizing it. Relevant alternative architecture for agentic RAG. (opaque.co/confidential-agents-for-rag)
- **HoundDog.ai** — **static code scanning** for PII leaks / data-flow mapping / RoPA; shift-left, not a runtime tool-call gateway. ($3.1M raised.)

---

## 3. Real technical limitations of the tokenization approach

1. **The model cannot REASON over tokenized PII.** This is the central, unavoidable limitation. Once `address` is a token, the model cannot "extract the city," compute distance, or do geo/temporal reasoning. Canonical example (Attic Security): mask two login IPs (NL then RU) → both become arbitrary placeholders → Claude can no longer detect "impossible travel" because it can't tell they're on different continents.
   - Source: atticsecurity.com/en/blog/why-llms-hate-fake-data-token-proxy ; aiengineerweekly.substack.com "Privacy Filter Is Not an LLM"
   - **Partial mitigations:** (a) **context-preserving / semantically-aware tokens** — e.g. replace an IP with a *different* IP from the same ASN/subnet (MaxMind GeoLite2) so geo signal survives; Skyflow/Protecto market "entity-preserving transformations." But this is per-entity engineering and leaks coarse info by design. (b) Selectively leave low-sensitivity quasi-identifiers (e.g. city) in cleartext — a privacy/utility trade-off decision.
2. **Detection-recall risk (the real failure mode).** Tokenization only protects what detection catches. NER/regex misses novel formats, obfuscated data, PII spoken across turns, context-dependent secrets → silent leakage to the model. "Token classifiers cannot reason about context the way an LLM can." Recall is never 100%; this is the dominant risk and demands defense-in-depth.
   - Source: arxiv 2504.12308 (Unmasking the Reality of PII Masking Models) ; atticsecurity.com ; arxiv 2402.13846
3. **Pseudonymization ≠ anonymization (legal).** Reversible tokens are **pseudonymization** under GDPR — still personal data, vault still in regulatory scope; the token map is a high-value target requiring strong key/access governance.
   - Source: agentic-patterns.com/patterns/pii-tokenization ; deepwiki Presidio (governance note)
4. **PII inference not prevented.** Even with all literal PII tokenized, a model can deduce sensitive attributes from remaining context. Tokenization doesn't stop inference.
   - Source: agentic-patterns.com/patterns/pii-tokenization
5. **Format-preserving tokens can break validation/uniqueness.** A format-preserving fake phone/email must still pass downstream validators yet not collide with real records or fail checksum (e.g. Luhn for cards) — non-trivial to generate correctly; naive FPT breaks tools too.
6. **Latency / ops cost.** Every prompt, every tool call, and every tool result passes through detection + (de)tokenization (Skyflow does ~2B vault calls/quarter). Adds round-trips; vault becomes a critical-path dependency and availability/SPOF concern.
7. **Re-tokenization consistency across the loop.** The token for a value seen in a tool *result* must match the token the model already holds for that value, or the model loses correlation — requires a session-scoped consistent map across both directions.

---

## 4. The architecture bar a competitor (CIS) would need to match

Reference architectures: Skyflow MCP/agent blog, Skyflow Runtime AI Data Security + AWS AgentCore, agentic-patterns.com PII-tokenization pattern, Microsoft "PII Shield" privacy proxy (techcommunity.microsoft.com/.../4514726), Attic context-aware token proxy.

To be credible, match:
1. **Bidirectional tool-call interception** — a proxy/gateway (MCP-compatible) that tokenizes inbound prompts AND tool-call args, **detokenizes args server-side immediately before tool execution**, and **re-tokenizes tool results before they return to the model**. Raw PII never enters model context; plaintext rehydrated only at the final authorized boundary.
2. **Three integration modes** (Skyflow's bar): zero-code gateway proxy, SDK-wrap of existing MCP/tools, and embedded SDK.
3. **Format-preserving tokenization** with type-correct, validator-passing tokens (phone keeps phone shape, email keeps email shape, card passes Luhn) — distinct from UUID tokens where the tool can accept opaque IDs.
4. **Deterministic, session-consistent entity mapping** — same value → same token across prompt, args, and results, so the model can correlate; bidirectional consistency across the loop.
5. **Secure vault + fine-grained, context-aware access control** — RBAC/CBAC keyed on user + agent identity + purpose + data type + region; "minimum necessary"; field-level audit of every tokenize/detokenize/rehydrate event.
6. **High-recall, context-aware detection** (not pure regex) across 50+ entity types and multilingual, with the explicit acknowledgement that recall<100% and a defense-in-depth story (e.g. confidential-compute fallback à la Opaque, or local models for max-sensitivity fields).
7. **Entity-preserving / semantically-aware tokenization option** to mitigate the reasoning-loss limitation (e.g. ASN-preserving IPs, region-preserving placeholders) — the current frontier differentiator.
8. **Data residency / sovereignty** controls (in-region tokenization even when agents run globally).
9. **Compliance posture** mapped to GDPR (pseudonymization framing), HIPAA, PCI DSS, CCPA; documented that the vault/token-map is in regulatory scope.
10. **Low-latency, HA design** — vault is on the critical path of every call; needs caching, batching, and failover.

---

## Source index (URLs)

- Skyflow LLM Privacy Vault: https://www.skyflow.com/post/generative-ai-data-privacy-skyflow-llm-privacy-vault
- Skyflow GenAI / re-identify: https://www.skyflow.com/product/llm-privacy-vault
- Skyflow MCP secure agent architecture: https://www.skyflow.com/post/building-secure-ai-agent-architecture-mcp
- Skyflow Agentic AI layer launch (Dec 2024): https://www.businesswire.com/news/home/20241202242238/en/Skyflow-Launches-Agentic-AI-Security-and-Privacy-Layer
- Skyflow Runtime AI Data Security + AWS (Dec 2025): https://www.helpnetsecurity.com/2025/12/02/skyflow-runtime-ai-data-security-platform-aws/
- Skyflow PartyRock (format-preserving tokens, code flow): https://www.skyflow.com/post/adding-a-privacy-layer-to-aws-partyrock
- Skyflow funding: https://diginomica.com/skyflow-raises-$30m-data-privacy-enterprise-llms ; https://www.crunchbase.com/organization/skyflow-8a8d
- Skyflow pricing: https://www.vendr.com/buyer-guides/skyflow
- Descope + Skyflow MCP: https://www.descope.com/blog/post/descope-skyflow-mcp
- Protecto Vault: https://www.helpnetsecurity.com/2025/12/10/protecto-vault/ ; https://www.protecto.ai/ ; https://www.protecto.ai/blog/handling-sensitive-data-mcp-systems-pii-context-aware-security/
- Private AI → Limina: https://www.getlimina.ai/en ; https://www.getlimina.ai/en/blog/private-ai-rebrands-limina-sensitive-data-privacy ; https://pitchbook.com/profiles/company/434266-39
- Tonic Textual: https://www.tonic.ai/solutions/use-case/llm-privacy-proxy ; https://www.tonic.ai/products/textual
- Presidio deanonymization: https://deepwiki.com/microsoft/presidio/3.2.2-deanonymization ; https://microsoft.github.io/presidio/anonymizer/
- PresidioReversibleAnonymizer (LangChain): https://reference.langchain.com/python/ (langchain_experimental data_anonymizer)
- Nightfall: https://www.nightfall.ai/blog/prompt-sanitization-5-steps-for-protecting-data-privacy-in-ai-apps
- Lakera Guard: https://docs.lakera.ai/guard
- Cloudflare AI Gateway Guardrails: https://blog.cloudflare.com/guardrails-in-ai-gateway/
- Palo Alto Prisma AIRS: https://www.paloaltonetworks.com/prisma/prisma-ai-runtime-security ; https://pan.dev/airs/
- Prompt Security / SentinelOne $250M: https://finance.yahoo.com/news/sentinelone-acquire-prompt-security-250m-182354008.html
- Opaque Systems: https://www.opaque.co/confidential-agents-for-rag ; https://www.prnewswire.com/news-releases/opaques-industry-first-confidential-ai-platform-debuts-on-azure-marketplace-302432859.html
- HoundDog.ai: https://hounddog.ai/ ; https://pulse2.com/hounddog-ai-3-1-million-raised-to-help-organizations-protect-sensitive-data-from-exposure/
- Agentic-patterns PII tokenization: https://www.agentic-patterns.com/patterns/pii-tokenization/
- Microsoft PII Shield privacy proxy: https://techcommunity.microsoft.com/blog/azuredevcommunityblog/introducing-pii-shield-a-privacy-proxy-for-every-llm-call/4514726
- Attic context-aware token proxy (reasoning-loss limitation): https://atticsecurity.com/en/blog/why-llms-hate-fake-data-token-proxy/
- "Privacy Filter Is Not an LLM": https://aiengineerweekly.substack.com/p/privacy-filter-is-not-an-llm
- arXiv: Unmasking the Reality of PII Masking Models (2504.12308); LLMs are Advanced Anonymizers (2402.13846); Semantically-Aware LLM Agent for Privacy (2510.27016)
