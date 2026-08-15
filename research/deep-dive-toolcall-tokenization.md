# Deep-Dive: Tool-Call PII Tokenization Middleware — Frontier Practices & Reference Architecture

**Date:** 2026-06-07 · **For:** Pseudex (152-ФЗ PII gateway for LLM agents, CIS) · **Method:** /deep-dive — 4 parallel primary-source excavations (Skyflow / Presidio core / OSS proxies+MCP / FPE+RU-detection), lead-synthesized with adversarial analysis.
**Raw notes:** `dd-notes-1-skyflow.md`, `dd-notes-2-presidio.md`, `dd-notes-3-proxies-mcp.md`, `dd-notes-4-fpe-ru-detection.md`.
**Evidence grades:** [A] read in primary source / [B] single primary, limited / [C] asserted by primary as rationale / [D] folklore or our inference.

---

## TL;DR — the answer

1. **The tool-call "loop" is not the hard part.** A working end-to-end implementation is ~300 lines (`anon_proxy` proves it [A]). The plumbing — detokenize tool args before execution, re-tokenize tool results — is well-understood. **Do not over-invest engineering here; copy the known design.**
2. **The hard parts (= the moat) are two:** (a) **detection recall** on Russian PII (local NER tops out ~0.81 recall → ~19% silent leak on hard text [B]); every miss is a compliance breach. (b) **consistency-without-leakage** — the cryptographic tradeoff between stable tokens (enable joins, but leak equality patterns) and per-context random tokens.
3. **FPE is a trap — abandon FF3-1.** NIST's 2025 draft **removed FF3/FF3-1** (Beyne 2021 cryptanalysis breaks them on small domains = exactly phones/СНИЛС); FF1 is approved but **patented until Feb 2029**. → Use **random-token + vault-lookup**, deterministic FPE only where a join genuinely needs it. [A]
4. **Nobody — including Skyflow — publicly documents the clean "model emits token → detokenize arg → run tool → re-tokenize result" round-trip.** Skyflow documents de-identifying tool *output* + rehydrating at point-of-use; the literal arg round-trip is *inferred* even there [B/D]. The only end-to-end OSS implementation is a 28★ hobby repo. **This is the genuine, ownable gap.**

---

## Phase 0 — hypotheses vs findings

| Hypothesis | Verdict |
|---|---|
| H1: Skyflow's magic is a gateway/MCP proxy that detokenizes args at exec & re-tokenizes results; tokens format-preserving+deterministic | **Partly.** Token props confirmed [A]; the proxy/MCP placement confirmed [A]; but the literal arg round-trip is **inferred, not documented** [B/D]. Skyflow's documented pattern is "de-identify tool *output* + rehydrate at point-of-use." |
| H2: OSS gives reversible de-id but nothing does the tool-call round-trip | **Mostly confirmed, with one exception.** Presidio = detection+operators only, zero tool-call code [A]. LiteLLM does *half* (unmasks tool-call args, per-request only) [A]. Lasso mcp-gateway has the *seams* but empty stub [A]. **Exception:** `anon_proxy` does the full loop [A]. |
| H3: FF3-1 + strong RU NER is the buildable core | **FALSE on FPE.** FF3-1 is withdrawn/broken; use random-token+vault [A]. RU NER part holds but recall is the risk [B]. |

---

## Part A — Skyflow mechanism, decoded

**What Skyflow actually is:** a classic **data privacy vault** (tokenize-in / store-ciphertext / detokenize-out under policy), repositioned at two agent chokepoints. The privacy primitives are old and documented; the "agent" story is those primitives placed at the data source and the point-of-use. [A]

**Documented tool-call flow** [A for steps, [B/D] for the literal arg round-trip]:
1. Traffic flows through the **MCP Gateway** (proxy in front of the data source) or an **SDK-wrapped** tool.
2. Skyflow inspects the tool **output/payload**, classifies sensitive fields, applies per-field **polymorphic transform** (tokenize / mask / pass) per policy + caller permission. *"This gateway wraps outbound queries, enforcing redaction, masking, and tokenization before any sensitive data reaches the agent or underlying model."*
3. The **de-identified** result enters the prompt; the model reasons over tokens.
4. **Rehydration** restores plaintext *"only at the exact point... where it is permitted and required"* — when a downstream tool genuinely needs the real value.

**Integration modes** [A]: (1) **MCP Gateway** zero-code proxy; (2) **MCP Server SDK — wrap** existing tool functions; (3) **MCP Server SDK — embed** in a new server. Plus AWS variants (AgentCore identity-binding).

**Token properties** [A]: types = random/UUID, **deterministic**, non-deterministic, **format-preserving**, length-preserving, transient/TTL. Format-preserving keeps tokens valid-looking (`johndoe@acme.com → bwe09f@fg7d8.com`) so validators + model pattern-reasoning don't break. **Deterministic + token-groups** give entity consistency (same email → same token within the group) enabling coreference/joins; cross-field homographs stay distinct.

**Polymorphic encryption** (patent US20230005391A1) [B]: same data stored in multiple partitions under different schemes, each permitting one operation class (exact-match / range / aggregation) on ciphertext.

**Access & audit** [A]: PBAC (RBAC+ABAC), field-level visibility, per-role max redaction (`PLAIN_TEXT/MASKED/REDACTED`). Auth via **OAuth 2.0 token-exchange (RFC 8693)** server-side: user IdP token → role-scoped Skyflow STS token; the vault (not the LLM) decides per-field resolution, and **"Skyflow tokens are never exposed to the client or the LLM."** Field-level audit of every access/transform/rehydration.

**Proprietary/unknown:** the parse-and-intercept internals, detection engine, token-gen algorithm, key management, latency numbers, policy DSL. **The arg-detokenize-then-retokenize round-trip is inferred, not documented.** [D]

---

## Part B — OSS landscape map (what to steal / what's missing)

| Project | What it does | STEAL | MISSING | Grade |
|---|---|---|---|---|
| **`KevinXuxuxu/anon_proxy`** (~28★, Apr 2026) | **Only end-to-end loop.** `mask_request` masks `tool_use.input` + `tool_result.content`; `unmask_response` unmasks emitted `tool_use.input` so the tool runs on real values; result re-masked next turn via persistable per-conversation `PIIStore`; **longest-first token sort** (fixes `_1`/`_10`); `unmask_json` for **streaming partial_json** args | The entire loop design; PIIStore; longest-first reverse; partial_json handling | Toy scale; thread-safety/perf/HA unproven; detection quality | [A] read source |
| **LiteLLM** Presidio guardrail | Calls external Presidio; `output_parse_pii` builds `<TYPE_N>` tokens; **does unmask `tool_calls[].function.arguments`** | The model→tool unmask hop; numbered-token scheme | **Per-request map only** — no cross-turn persistence; doesn't re-tokenize tool *result* to same token. **Half the loop** | [A] |
| **Lasso `mcp-gateway`** (~376★) | MCP security gateway with the right seams: `sanitize_tool_call_args` / `sanitize_tool_call_result` | The MCP interception seam architecture | Presidio plugin is a **pass-through stub** (masking commented out); response redaction is **irreversible** (no map) | [A] |
| **LangChain `PresidioReversibleAnonymizer`** | Reversible de-id library; `DeanonymizerMapping = {entity_type:{fake:original}}`; consistency via `seen_values` dedup + `_N` suffix on collisions; faker-realistic fakes | The mapping/consistency design; faker replacements; the fuzzy-fallback idea | **Default reverse = naive `str.replace`, NO longest-first** (the brief's assumption was wrong); process-local map; **zero tool-call awareness** | [A] |
| **Portkey / cloakpipe / veilstream / mirage-proxy / ctxproxy** | One-way or chat-content-only redaction | — | None handle tool calls; mostly irreversible or text-only | [A] |
| **Microsoft Presidio (core)** | Detection + operator framework (see Part C) | Analyzer/recognizer framework; presidio-structured for JSON; operator pattern | **Zero** tool-call/MCP code; `encrypt` non-deterministic; consistency is consumer code | [A] |

**Verdict [A]:** the full, *persistent, session-keyed* tool-call loop that re-tokenizes a tool RESULT to the SAME token as its matching CALL is **unsolved in production-grade OSS.** Only `anon_proxy` does it, at hobby scale. **That is the gap to own.**

---

## Part C — Presidio internals (the detection/operator substrate)

**Pipeline** (decoupled via `List[RecognizerResult]`) [A]:
- **AnalyzerEngine** (`analyzer_engine.py`): NlpEngine once → recognizers fan-out → context score-boost → `remove_duplicates` + threshold. `RecognizerResult{entity_type, start, end, score}` **stores offsets, NOT matched text** → you must keep source text to build the token map.
- **AnonymizerEngine** (`engine_base.py`): `operators: Dict[entity_type → OperatorConfig]`; walks entities **end→start** applying operators; `EngineResult{text, items:List[OperatorResult]}`.
- **Reversible path:** `encrypt.py` = **AES-CBC + PKCS7 + fresh random IV** → `urlsafe_b64(iv‖ct)`; `decrypt.py` reverses; `DeanonymizeEngine` reuses the `_operate` loop. **Key is a per-call param — Presidio stores no key, no token store.** [A]
- **Critical caveat:** random IV ⇒ **same plaintext → different ciphertext each call** → `encrypt` is reversible but **not deterministic** → cannot be a stable token. [A]
- **Consistency is consumer code:** Microsoft's own `pseudonymization.ipynb` uses a stateful `InstanceCounterAnonymizer` holding `{entity_type:{original:placeholder}}` + a matching deanonymizer; **explicitly flagged not thread-safe.** [A]
- **`presidio-structured`** fits tool-call JSON: recurses nested dicts → dot-notation keys → applies operators per value. Limit: **one entity_type per field**, no span-level multi-PII inside a string value, no offsets. [A]
- **GLiNER correction:** there is **no GLiNER NlpEngine**; GLiNER is a `GLiNERRecognizer` (EntityRecognizer). NlpEngines = spaCy/Stanza/Transformers. [A]

---

## Part D — Tokenization primitive & RU detection (the build decisions)

**Tokenization — use random-token + vault, NOT FPE** [A]:
- NIST SP 800-38G Rev.1 2nd draft (2025-02-03) **removed FF3 and FF3-1**; only **FF1** approved. Cause: Beyne CRYPTO-2021 linear cryptanalysis breaks FF3-1 on small domains (N=10³ distinguishable in ~2²³ queries = phone/СНИЛС/passport sizes).
- **FF1 is patent-encumbered** (US 7,864,952, expires 2029-02-20). OSS Python FF1 is weak; Go `capitalone/fpe` (Apache-2.0) has FF1.
- **Decision:** default **random-token + vault-lookup** (sidesteps patent + cryptanalysis; cost = a mapping store, which we need anyway for the session loop). Use deterministic FPE only for a field that *needs* cross-record joins AND is high-cardinality AND tolerates equality-pattern leakage. **Do not build new on FF3-1.**
- Reference taxonomy = HashiCorp Vault transform engine: `fpe` (stateless, deterministic) vs `tokenization` (random, stateful, not format-preserving).

**RU PII detection — ensemble, recall-first** [B unless noted]:
- Recall numbers from SPbLitGuide (arXiv 2506.02589, 2025; PERSON-only, adversarial literary RU text — conditions matter, real support/order data is likely easier).
- **Free-text (ФИО/адрес):** `spaCy ru_core_news_lg` (MIT) best local recall **0.81**; **Natasha/Slovnet** (MIT, 27MB) PER F1 ~0.97 on news (self-reported); **GLiNER `gliner_multi_pii-v1`** (Apache-2.0) via Presidio `GLiNERRecognizer` = best multilingual coverage incl. IDs/dates but **RU not separately benchmarked — must validate**; DeepPavlov BERT high precision 0.96 but **recall 0.65 = worst for leak-aversion**; LLM (GPT-4o) recall 0.90–0.95 but egress concern → use as offline second-pass only.
- **Structural fact:** телефон/СНИЛС/ИНН/паспорт/карта need **regex + checksum PatternRecognizers** — **no pre-built RU recognizer pack exists in Presidio; must author it.**
- **Recall is THE privacy metric** — best clinical de-id ~95% recall still misses ~5%; mitigate by **ensemble (union) + regex safety-nets**, never a single model.

---

## Reference architecture for Pseudex (the synthesized gold)

```
┌─────────── Pseudex Gateway (in RF) ───────────────────────────────┐
│  Interceptor: OpenAI-compatible proxy  +  MCP-gateway mode         │
│      │                                                             │
│  1) Inbound (user msg + RAG context)                              │
│      → Detector(ensemble) → real→token, write to Session PIIStore  │
│  2) → LLM  (tokens only; cheap/local/foreign — fungible)          │
│  3) LLM emits tool_call(args w/ tokens)                            │
│      → parse args (JSON; handle streaming partial_json; recurse    │
│        nested) → token→real  SERVER-SIDE ONLY                      │
│  4) → execute tool with REAL values                               │
│  5) tool result (new PII) → Detector → real→token                 │
│        (reuse existing token for known values = consistency)       │
│  6) → LLM (tokenized result) → loop 3–6 until final answer        │
│  7) final answer → token→real → user                              │
│                                                                    │
│  Vault: token↔value map, encrypted, RBAC/PBAC, field-level audit  │
│  Token: random + format-preserving render; session-consistent     │
└────────────────────────────────────────────────────────────────────┘
```

### Implementation checklist (steal-from-source)
- [ ] **Persistent, session-keyed `PIIStore`** (real↔token, both directions), thread-safe — *fix Presidio/LangChain's process-local + not-thread-safe limitation*. (anon_proxy design + Presidio InstanceCounter pattern)
- [ ] **Reverse by longest-token-first + canonicalization** — fixes `<PERSON_1>`/`<PERSON_10>` collision and is robust to model mangling. (anon_proxy)
- [ ] **Fuzzy fallback** for LLM-mangled tokens. (LangChain)
- [ ] **Unmask `tool_calls[].function.arguments` / `function_call.arguments`**, incl. **streaming `partial_json`** (`unmask_json`). (LiteLLM + anon_proxy)
- [ ] **Re-tokenize tool RESULT to the SAME token** as the matching value (the loop closure nobody but anon_proxy does).
- [ ] **`presidio-structured`** for typed JSON args; **span-level** handling for free-text args (Presidio structured does one-entity-per-field only).
- [ ] **MCP seams** `sanitize_tool_call_args` / `sanitize_tool_call_result`. (Lasso)
- [ ] **PBAC + RFC 8693 token-exchange** so detoken rights are role-scoped and **tokens never reach the LLM/client**. (Skyflow)
- [ ] **Random-token + vault**, format-preserving *rendering* for validators; deterministic only where a join needs it. (NIST/Beyne)
- [ ] **RU recognizer pack**: regex+checksum for телефон/СНИЛС/ИНН/паспорт/карта **+** ensemble NER (spaCy ru_lg ∪ Natasha ∪ GLiNER multi_pii) for ФИО/адрес.
- [ ] **Fail-safe on low confidence** (block/redact rather than pass when detector unsure) — recall insurance.

---

## Hard edge cases everyone gets wrong
1. **Entity consistency across turns** — needs a persistent session store; per-request maps (LiteLLM) break the agent loop. [A]
2. **Nested / structured tool args** — must recurse JSON; presidio-structured is field-level only, free-text fields need span-level. [A]
3. **Model mangles the token** — cheap/local models (our target!) are *more* likely to not copy `<PHONE_7f3a>` verbatim → format-preserving tokens + fuzzy/longest-first reverse are mandatory, not optional. [A/D]
4. **Detection recall <100% = silent leak** — ~19% miss on hard RU text; ensemble + regex + fail-safe. [B]
5. **Quasi-identifiers** — Sweeney: **87% of US population unique on {ZIP, gender, DOB}** [A]; perfect direct-PII tokenization still leaks via {address+date+amount}. Token-level detection never touches this — needs a separate k-anonymity control if outputs are aggregated/logged.
6. **Consistency vs equality-leakage** — BRATsynthetic (arXiv 2210.16125): you can have stateless cross-record consistency OR no equality-pattern leakage, **not both** without per-context state. → choose **session-scoped** consistency. [B]
7. **Streaming `partial_json`** — token spans split across chunks; buffer or use `unmask_json`. [A]
8. **Latency on the critical path** — detection (NER) is the cost; the vault is a SPOF. Cache, run detectors async/parallel, keep the hot path tight. [D inference]

---

## Phase 2 — critical analysis (where this breaks)
- **The compliance story has an engineering hole.** "Tokens to a foreign model = no PII transfer" only holds if detection is complete. At ~0.81 local recall it is *not* — a missed ФИО in free text is an actual breach. The honest mitigation (ensemble + regex + fail-safe) raises recall but never to 100%. **This is the central risk and must be designed for, not assumed away.** [B]
- **anon_proxy is [A] but unproven.** We read working code, but it's one author, 28★, Apr 2026 — no thread-safety/perf/HA evidence. **Steal the design, not the maturity.**
- **Skyflow's round-trip is [B/D] inferred.** Its documented pattern ("de-identify tool *output*, rehydrate at point-of-use") is subtly *different* from "model emits a token as an argument." Don't assume Skyflow secretly solved a thing we can't see; the literal arg round-trip may be deliberately avoided (because of the token-mangling risk above). **anon_proxy may genuinely be ahead of documented Skyflow on the literal round-trip** — opportunity *and* yellow flag.
- **RU recall numbers are one adversarial literary dataset (PERSON-only).** [B] Our real use case — *identifier passthrough* in support/order chats — is dominated by phones/IDs that are **regex+checksum-detectable at near-100%**, and names that appear in structured fields. So practical recall for the MVP scope is plausibly far better than 0.81. **Validate on real customer-shaped data before believing either the pessimistic or optimistic number.**

## Phase 3 — insights (the 0.01% pass)
1. **The defensibility is detection + the RU recognizer pack, not the loop.** The loop is copyable in a weekend; high-recall RU PII detection (especially the unbuilt regex+checksum pack + ensemble) is the part that takes real work and that competitors can't trivially clone. **Put the effort there.**
2. **The product's own value proposition (cheap/local models) is in tension with its hardest failure mode (token mangling).** Weaker models are exactly the ones that mangle pass-through tokens. Format-preserving tokens that look like *real* phones/emails make the model treat them as opaque literals → this is *why* format-preserving matters, beyond validator-compatibility. A first-class "token-fidelity" test harness across the cheap models you intend to support is a non-obvious must-have.
3. **FF3-1's death is a strategic gift.** It removes the temptation to build a clever stateless crypto core and forces the stateful-vault design — which you need anyway for session consistency and which doubles as the 152-ФЗ "data stays in RF" artifact. The vault is both the crypto answer and the compliance story.
4. **"Re-tokenize the tool result to the same token as the call" is the single technical signature of a real product vs a demo.** Everyone can mask a prompt; almost no one closes that specific loop with persistence. It's also the precise thing the MVP success-test should assert.

---

## Uncertainty ledger / open questions
- **[B→needs A] Real-data recall** for our actual use case (support/order/booking chats) — must benchmark the ensemble on RU customer-shaped data, not literary text.
- **[D] Skyflow's literal arg round-trip** — unconfirmed; treat as inference. (Could probe via Skyflow sales/PoC or SDK source.)
- **[open] Legal:** does sending session-consistent (deterministic-within-conversation) tokens abroad change the 152-ФЗ analysis vs fully random per-call? (Equality-pattern leakage could be argued to retain identifiability.) Confirm with the 152-ФЗ lawyer.
- **[open] GLiNER RU recall** — not separately benchmarked; validate before relying on it for names/addresses.
- **[open] Latency budget** — no public Skyflow numbers; must measure our detection+vault hot path.
- **[open] Reasoning-over-PII cases** — partial detokenization or semantic-preserving tokens? Out of MVP scope (identifier passthrough), but design the token format so it's not foreclosed.

---

## Sources (primary, actually read)
**Skyflow:** docs.skyflow.com (tokenization types, PBAC, MCP Gateway/SDK), skyflow.com engineering blog, Descope×Skyflow MCP integration writeup, Google Patents US20230005391A1. **Presidio:** github.com/microsoft/presidio source (`analyzer_engine.py`, `anonymizer/operators/encrypt.py`/`decrypt.py`, `engine_base.py`, `structured`, `pseudonymization.ipynb`). **Proxies/MCP:** github.com/KevinXuxuxu/anon_proxy, BerriAI/litellm (presidio guardrail), lasso-security/mcp-gateway, langchain `PresidioReversibleAnonymizer`. **FPE/RU:** NIST SP 800-38G Rev.1 2nd draft (2025), Beyne CRYPTO-2021 (FF3-1 cryptanalysis), HashiCorp Vault transform docs, capitalone/fpe, arXiv 2506.02589 (SPbLitGuide RU NER), arXiv 2210.16125 (BRATsynthetic), Sweeney k-anonymity. Per-claim URLs + file paths in `dd-notes-1..4`.
