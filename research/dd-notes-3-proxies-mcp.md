# DD Notes 3 — PII De-identification Proxies / Gateways / MCP Middleware in front of LLMs & Agents

**Scope:** The OSS layer that puts PII de-identification IN FRONT of LLMs/agents.
**Load-bearing question:** Does ANY OSS project handle the **tool-call argument round-trip** —
detokenize a function-call argument before the tool executes, then re-tokenize the tool's
RESULT before it re-enters the model?

**Date:** 2026-06-07.
**Evidence grades:** [A] read source · [B] docs · [C] asserted by project · [D] inference.

**Boundaries honored:** Skyflow, Presidio CORE operator internals, FPE libs, Russian NER — NOT covered (other agents). Here we read only the LangChain *wrapper* and the proxies/gateways.

---

## 0. TL;DR VERDICT

- **The full tool-call tokenization loop is essentially a GAP, with ONE near-complete exception.**
- **`KevinXuxuxu/anon_proxy`** (~28★, Apr 2026, nascent) is the **only OSS project read that genuinely does the tool-call round-trip** end-to-end: it masks `tool_use.input` and `tool_result.content` on the request, and **unmasks `tool_use.input` on the response** so the client/tool executes with real values; the tool result returns with real PII and is re-masked on the next request. [A]
- **`LiteLLM`** does a *partial / single-hop* version: with `output_parse_pii=True` it **unmasks tool-call `function.arguments`** in the model's response (and can re-mask them via `apply_to_output`), but the token→original map (`pii_tokens`) lives in `request_data["metadata"]` and is **per-request / not persisted across the agent loop** — so it does not close the multi-turn loop on its own. [A]
- The flagship **MCP** security gateway, **`lasso-security/mcp-gateway`** (~376★), has the *structural hooks* for a round-trip (`sanitize_tool_call_args` + `sanitize_tool_call_result`) but its Presidio/Basic plugins are **one-way & irreversible**: request masking is a pass-through (commented-out), response masking destroys the value with no stored mapping. **No round-trip.** [A]
- **Portkey gateway** PII plugin: one-way redaction, text-only, no tool-call handling, redaction logic in closed Portkey API. [A]
- The other reversible proxies (`cloakpipe`, `veilstream`, `mirage-proxy`, `cloakbot`, `ctxproxy`) are **chat-content only** (prompt→mask, response→rehydrate). No structured tool-call argument handling read. [B]
- **LangChain `PresidioReversibleAnonymizer`** is a *library*, not a proxy: stateful consistent reversible anonymization of TEXT. No concept of tool calls. Default deanonymize is naive `str.replace`. [A]

---

## 1. LangChain `PresidioReversibleAnonymizer` (langchain-experimental)

**Repo:** `langchain-ai/langchain-experimental`, path `libs/experimental/langchain_experimental/data_anonymizer/`.
Files read [A]: `presidio.py`, `deanonymizer_mapping.py`, `deanonymizer_matching_strategies.py`, `base.py`, `faker_presidio_mapping.py` (commit `f10d5c3`).

### 1.1 What it is / intercepts
A **library wrapper** over Microsoft Presidio (analyzer + anonymizer). NOT a proxy and NOT agent/tool aware. You call `.anonymize(text)` and later `.deanonymize(text)`. It only sees plain strings. Reversible: **YES**. Entity consistency: **YES**.

### 1.2 How the mapping is stored
`DeanonymizerMapping` (`deanonymizer_mapping.py`) wraps a nested dict:
```
MappingDataType = Dict[str, Dict[str, str]]   # {entity_type: {anonymized: original}}
mapping: defaultdict(lambda: defaultdict(str))
```
The reversible anonymizer holds `self._deanonymizer_mapping = DeanonymizerMapping()` (state lives for the life of the object). `.deanonymizer_mapping` returns `{type: {fake: original}}`; `.anonymizer_mapping` returns the inverse `{type: {original: fake}}` (computed by inverting). [A]

### 1.3 Consistency across calls — the "add to mapping" logic
Two layers:

(a) **Within one `_anonymize` call** — `create_anonymizer_mapping(original_text, analyzer_results, anonymizer_results, is_reversed=True)`:
- sorts analyzer & anonymizer results by `.start` and `zip`s them positionally;
- `original_value = original_text[analyzed.start:analyzed.end]`;
- if `original_value` already mapped for that entity type → `continue` (skip, reuse);
- if the produced `anonymized.text` collides with an existing fake for that type → it renames via `format_duplicated_operator(anonymized.text, count+2)` → e.g. `<PERSON_2>`. [A]

(b) **Across calls** — `DeanonymizerMapping.update(new_mapping)`:
```python
seen_values = set()
for entity_type, values in new_mapping.items():
    count = len(self.mapping[entity_type]) + 1
    for key, value in values.items():
        if value not in seen_values and value not in self.mapping[entity_type].values():
            new_key = format_duplicated_operator(key, count) if key in self.mapping[entity_type] else key
            self.mapping[entity_type][new_key] = value
            seen_values.add(value); count += 1
```
**Duplicated originals are NOT re-added** (dedup by `value`), so the SAME original PII keeps the SAME fake across `.anonymize()` calls — that is the documented "built-in memory" behavior:
> `anonymizer.anonymize("My name is John Doe. Hi John Doe!")` → twice → identical `Noah Rhodes` both times (docstring in `presidio.py`). [A]

The mechanism that makes the fake *stable* on a re-anonymize is **not** the deanonymizer mapping itself — it is `_anonymize` calling `exact_matching_strategy(text, self.anonymizer_mapping)` (original→fake) AFTER presidio has run, so a previously-seen original is rewritten to its already-stored fake. (Presidio still re-generates a fresh fake internally, but the prior mapping wins on replace.) [A][D]

### 1.4 `.deanonymize()` reverse — and the "longest-match" nuance
- **Default** strategy = `exact_matching_strategy` (set in `base.py`: `DEFAULT_DEANONYMIZER_MATCHING_STRATEGY = exact_matching_strategy`). [A]
- `exact_matching_strategy` is **naive**:
```python
for entity_type in deanonymizer_mapping:
    for anonymized, original in deanonymizer_mapping[entity_type].items():
        text = text.replace(anonymized, original)
```
i.e. plain `str.replace`, iterating the dict. **No sort-by-length in the default path.** [A]
- The **"reverse-by-longest-match" detail the brief asked about does NOT exist in the default.** Longest-first ordering only appears in the OPT-IN fuzzy strategies:
  - `ngram_fuzzy_matching_strategy`: collects `(start_index, length, replacement)` and `replacements.sort(key=lambda x: x[0], reverse=True)` — that's **reverse by START INDEX** (so later substitutions don't shift earlier offsets), not by entity length. [A]
  - `fuzzy_matching_strategy` (needs `fuzzysearch`, Levenshtein `max_l_dist=3`) and `combined_exact_fuzzy_matching_strategy` (exact then fuzzy) exist for when the LLM slightly mangles the fake (e.g. "Kaenu Reves" ≈ "Keanu Reeves"). [A][B]
  - **Genuine STEAL:** the naive default is buggy for prefix-collision (`<PERSON_1>` shadowing `<PERSON_10>`) — anon_proxy and others fix this by sorting tokens **longest-first** before regex replace (see §5). LangChain's default does NOT.

### 1.5 Faker-based realistic replacements
`faker_presidio_mapping.get_pseudoanonymizer_mapping(seed)` returns `{ENTITY: lambda _: faker_call}` for ~30 Presidio entity types (PERSON→`fake.name()`, EMAIL_ADDRESS→`fake.email()`, US_SSN→`fake.ssn()`, CREDIT_CARD, IBAN, CRYPTO, LOCATION, DATE_TIME, plus UK/ES/IT/SG/AU specifics). Wired as Presidio `OperatorConfig(operator_name="custom", params={"lambda": fn})`. `faker_seed` makes it reproducible. Realistic fakes (vs `<REDACTED>`) keep the prompt natural so the model behaves normally. [A]

### 1.6 Persistence
`save_deanonymizer_mapping(path)` / `load_deanonymizer_mapping(path)` → JSON or YAML; load calls `.update()` (so it merges, dedup-by-value). [A]

### 1.7 Documented limitations (from source + docs) [A][B]
- **n-to-n / collision:** mapping is keyed `{type: {fake: original}}`; nothing guarantees a fake is globally unique across entity types, and the inverse `anonymizer_mapping` assumes 1:1. Two different originals producing the same faker output within a type is handled by the `_N` suffix, but a fake equal to real surrounding text → false reversal on `str.replace`. This is the well-known **n-to-n mapping** caveat.
- **LLM mangles the fake** → exact reverse fails → must switch to fuzzy strategies (opt-in, extra deps).
- **False positives / missed detection** inherit entirely from Presidio recall.
- **Mapping is process-local** unless explicitly saved/loaded; concurrency unsafe.
- **No tool/function-call awareness whatsoever** — text in, text out.

**STEAL:** consistent reversible mapping with `_N` disambiguation; faker realistic operators; save/load; fuzzy fallback for LLM-mangled tokens.
**MISSING:** tool-call args, default longest-first reverse, cross-process/session store, n-to-n safety, crypto-anchored reversal.

---

## 2. LiteLLM — Presidio PII guardrail (`litellm/proxy/guardrails/guardrail_hooks/presidio.py`)

**Repo:** `BerriAI/litellm` (commit `aaf1e24`). Class `_OPTIONAL_PresidioPIIMasking(CustomGuardrail)`. File read in full [A].

### 2.1 What it intercepts
A proxy guardrail with hooks: `async_pre_call_hook` (request), `async_post_call_success_hook` (response), `async_post_call_streaming_iterator_hook`, `async_logging_hook`. Calls out to a **separate Presidio analyzer + anonymizer HTTP service** (`PRESIDIO_ANALYZER_API_BASE` / `PRESIDIO_ANONYMIZER_API_BASE`). [A]

### 2.2 Masking modes (input)
`async_pre_call_hook` walks `data["messages"]`, masks string and list-content text via `check_pii` → `/analyze` then `/anonymize`. Two finalizers:
- `_finalize_presidio_anonymize_simple`: uses Presidio's already-anonymized text directly. **Irreversible** (no token map). [A]
- `_finalize_presidio_anonymize_numbered_tokens` (when `output_parse_pii=True`): builds `<ENTITY_TYPE_N>` tokens numbered left-to-right, applies replacements **reverse by start position**, and stores `request_data["metadata"]["pii_tokens"][token] = original`. **Reversible.** [A]

### 2.3 Output: unmask AND the TOOL-CALL handling (important)
`async_post_call_success_hook`:
- `apply_to_output=True` → **mask** the model output (PII the model itself produced).
- `output_parse_pii=True` (or `litellm.output_parse_pii`) → **unmask** tokens back to originals.

`_process_response_for_pii(response, request_data, mode)` is the key — it processes, for each choice:
1. message `content` (str/list),
2. **`message.tool_calls[].function.arguments`** (str) — masks OR unmasks,
3. legacy **`message.function_call.arguments`**.
```python
if function and hasattr(function, "arguments"):
    args = function.arguments
    if isinstance(args, str):
        if mode == "unmask":
            function.arguments = self._unmask_pii_text(args, pii_tokens)
        elif mode == "mask":
            function.arguments = await self.check_pii(...)
```
So **LiteLLM DOES detokenize tool-call arguments in the model's response** → the downstream tool receives REAL values. [A] This is half the round-trip (model→tool unmask).

`_unmask_pii_text` = exact `str.replace`, **plus a truncation fallback** (if `max_tokens` cut a token mid-string, match a prefix of length `min(20, len(token)//2)` at the very end and restore). Nice robustness trick. [A] **STEAL.**

### 2.4 Why it's only PARTIAL for the round-trip
- The token→original map `pii_tokens` is stored in **`request_data["metadata"]` — per single proxy request**. There is **no cross-request/session persistence** of `pii_tokens` in this file. [A]
- In an agent loop the tool RESULT comes back as a NEW request; its PII would be masked by `async_pre_call_hook` (good), but the new request's `pii_tokens` map is FRESH — so consistency of the SAME entity's token across turns is **not guaranteed** within this hook alone, and the numbering restarts. [A][D]
- Net: LiteLLM closes the **single-hop** model→tool unmask (and tool→model mask if you enable apply_to_output), but does **not** itself maintain a stable, persistent tokenization across the full multi-turn tool loop. It does not re-tokenize a tool result *using the same tokens* a prior turn assigned.
- Known issues corroborate gaps (e.g. #8359 "doesn't scrub effective request and response", #22821 Anthropic native API breakage). [B]

**Reversible:** y (only when `output_parse_pii=True`). **Entity-consistency across turns:** weak/no (per-request map). **Tool args:** YES (unmask/mask). **Tool results re-tokenized with same tokens:** NO. [A]

**STEAL:** tool_calls + function_call argument unmask/mask; numbered `<TYPE_N>` tokens; truncation-prefix fallback; mask-output vs unmask-output split; streaming reassembly via `stream_chunk_builder` then unmask.
**MISSING:** persistent cross-turn token store; stable tokens across the agent loop; the tool-RESULT side is masked by Presidio fresh each time (not reconciled to existing tokens).

---

## 3. Lasso Security MCP Gateway (`lasso-security/mcp-gateway`) — the flagship MCP case

**~376★, Python, Apache-ish. Files read [A]:** `sanitizers.py`, `plugins/base.py`, `plugins/guardrails/presidio.py` (commit `7e7f1f6`).

### 3.1 Structure (has the hooks!)
A plugin-based MCP proxy that sits between MCP client and downstream MCP servers. `sanitizers.py` exposes BOTH directions:
- `sanitize_tool_call_args(...)` → `plugin_manager.process_request(context)` (request: client→server).
- `sanitize_tool_call_result(...)` → `plugin_manager.process_response(context)` (response: server→client).
Also `sanitize_resource_read`, prompt results. So **the architecture is round-trip-capable.** [A]

### 3.2 But the Presidio plugin is ONE-WAY / irreversible
`PresidioGuardrailPlugin`:
- **`process_request`** = **pass-through**. The args-masking is literally **commented out**:
  ```python
  # if context.arguments and 'user_input' in context.arguments ...
  #     context.arguments['user_input'] = self._pii_anonymizer(...)
  return context.arguments  # Pass through for now
  ```
  → **PII in tool-call ARGS is not touched.** [A]
- **`process_response`** = anonymize TextContent in `CallToolResult`, resource reads, prompt results via `_pii_anonymizer`, which calls `anonymizer.anonymize(text, analyzer_results)` with **NO operator config** → default Presidio redaction (`<EMAIL_ADDRESS>` style), **no mapping stored** → **NOT reversible**. [A]

### 3.3 Verdict on Lasso
It masks tool RESULTS one-way (destroys value) and does NOT detokenize tool-call args. **No round-trip, no reversibility, no consistency.** The README's "masks PII in requests and responses" is, for the Presidio plugin, really "response-side anonymization"; request masking is unimplemented. The Basic plugin (secret patterns) and Lasso-API plugin are similar one-way. [A][B]

**STEAL:** clean request/response plugin split with `PluginContext`; explicit `sanitize_tool_call_args` / `sanitize_tool_call_result` seams (the right place to add a real round-trip); MCP-native (`CallToolResult`, `GetPromptResult`, resource tuples) typing.
**MISSING:** the actual reversible round-trip — both seams exist but the de/re-tokenization logic is absent. This is precisely the gap to fill.

---

## 4. Portkey Gateway (`Portkey-AI/gateway`, ~12k★) — PII plugin

File read [A]: `plugins/portkey/pii.ts`.
- **One-way redaction.** Replaces detected PII with the Portkey service's `processed_text`; **stores no reversal mapping.** [A]
- Runs on **both** request and response hooks (`getCurrentContentPart` per `eventType`), but **text content only — no tool-call/function-arg handling.** [A]
- Actual detection+redaction happens in **closed Portkey API**, not in OSS. Other plugins (gibberish, language, moderateContent) are also content filters.
- **Reversible:** n. **Consistency:** n/a. **Tool args/results:** n. **Round-trip:** n.

**STEAL:** nothing tokenization-relevant. **MISSING:** everything for round-trip.

---

## 5. anon_proxy (`KevinXuxuxu/anon_proxy`) — THE round-trip exception

**~28★, Python, Apr 2026, nascent.** Anthropic/OpenAI **API-format proxy** ("between your local environment and LLM providers"). Files read [A]: `masker.py`, `mapping.py`, `adapters/anthropic.py` (+ server.py flow). Commit `27b0a71`.

### 5.1 The store (`mapping.py` `PIIStore`)
Bidirectional in-memory map, **one store per conversation**:
- `_forward: {(label, canonical_value): Placeholder}`, `_reverse: {token: original}`, `_counters: {label: int}`.
- `get_or_create(label, value)`: canonicalizes (`_canonical` = collapse whitespace + casefold) so the SAME entity (modulo case/space) always returns the SAME token `<{LABEL}_{N}>`. **Consistency: YES.** [A]
- `original(token)` reverses (preserves first-seen casing). `to_dict`/`from_dict`/`save`/`load` → JSON persistence; round-trip rebuilds forward map. [A]

### 5.2 The masker (`masker.py`)
- `mask(text)`: two-pass detection — regex detectors first (substituted inline), then ML model on partly-masked text; overlaps resolved **longest-first** (`_resolve_overlaps` sorts by `(-length, -score, start, label)`). Substitution allocates tokens left-to-right but **applies right-to-left** to keep offsets valid. LRU caches by content hash; skips `<system-reminder>` blocks. [A]
- `unmask(text)` / `unmask_json(text)`: `_sub` builds a regex of all tokens **sorted longest-first** (`sorted(tokens, key=len, reverse=True)`) so `<PERSON_1>` can't shadow `<PERSON_10>` — the exact bug LangChain's default has. `unmask_json` JSON-escapes the restored original (for `input_json_delta.partial_json` streaming tool args). [A] **STEAL.**

### 5.3 The tool-call ROUND-TRIP (adapters/anthropic.py) — the answer to the brief
- **`mask_request`** walks every content block (`_mask_block`):
  - `tool_use` block → `input` recursively string-walked through `masker.mask` → tool-call args from history are masked. [A]
  - `tool_result` block → `content` (str or nested) masked. [A]
  - normal text masked.
  → **the model NEVER sees real PII, even inside tool results or prior tool-call args.**
- **`unmask_response`** (`_unmask_block`):
  - `tool_use` block → `input` recursively unmasked via `masker.unmask` → **the function-call arguments the model just emitted are detokenized to REAL values** before they leave the proxy to the client/tool. [A]
  - **asymmetry:** `_unmask_block` does NOT touch `tool_result` (only `tool_use`) — by design (results only flow on requests). [A]
  - streaming: `transform_stream` + `unmask_json` for `input_json_delta.partial_json`. [A]

**Confirmed end-to-end flow [A]:**
1. client sends real PII → `mask_request` → model sees `<PERSON_1>` etc.
2. model emits `tool_use` with placeholders in args → `unmask_response` restores real values → client executes tool with REAL data.
3. tool returns result with real PII → client sends it back as a `tool_result` block → `mask_request` re-masks (same store ⇒ same tokens) → model sees placeholders again.

That IS "detokenize a function-call argument before tool execution, then re-tokenize the tool's RESULT before it re-enters the model." **YES — anon_proxy does the full tool-call tokenization loop.** [A]

### 5.4 Nuances / limits
- It's a **format-level API proxy**, not an in-process agent hook. The round-trip works because the **client re-submits the tool_result through the proxy** each turn; the proxy is stateless-per-request on the result side and relies on the per-conversation `PIIStore` for token stability. [A][D]
- One store **per conversation** — cross-conversation isolation good, but store identity must be keyed correctly (it accumulates across turns). [A]
- Detection quality = its `PrivacyFilter` (ML) + regex; not the brief's concern.
- README caveat: tools that need the *literal* PII (e.g. DB lookup by email) DO get real values back via unmask — which is the point — but if a tool's arg PII was a *false positive*, the placeholder reaching the model could degrade behavior. [B]
- Extended-thinking / signed blocks deliberately NOT masked (would break signatures). [B] **STEAL** (also seen in mirage-proxy).

**Reversible:** y. **Consistency:** y (canonicalized, per-conversation, persistable). **Tool args:** y (mask in history + unmask emitted). **Tool results:** y (masked on re-entry). **Round-trip:** **YES.** [A]

---

## 6. Other reversible chat-only proxies (scanned; round-trip = NO)

| Repo | Lang | ★ | Reversible | Consistency | Tool-call round-trip | Notes |
|---|---|---|---|---|---|---|
| `rohansx/cloakpipe` | Rust | ~29 | y | within-session deterministic; random across sessions | **NO** (chat prompt→response only; AES-256-GCM vault; `cloakpipe-mcp` exists but tool/arg handling undocumented) | [B] |
| `nikshepsvn/veilstream` | Py | ~6 | y | per-session vault | **NO** (chat streams only; **PASP**: HMAC-SHA256 crypto anchor on each pseudonym so only *anchored* matches are reversed — blocks false-attribution) | [B] **STEAL the crypto anchor** |
| `chandika/mirage-proxy` | Rust | ~58 | y | within-session | **NO/undocumented** (format-preserving plausible fakes — valid AWS key, Luhn-valid CC; skips signed thinking/encrypted blocks) | [B] **STEAL format-preserving fakes** |
| `spire-studio/cloakbot` | Py | ~131 | (local LLM sanitize) | — | **NO** (local-LLM prompt sanitizer before forwarding) | [B] |
| `jakobhuss/ctxproxy` | Py | ~8 | y (placeholders) | — | **NO** (OpenAI call interception, placeholder swap) | [B] |
| `fabriziosalmi/aidlp` | Py | ~11 | likely one-way | — | **NO** (mitmproxy + presidio DLP) | [B] |
| `aisecuritygateway/...` | Py | ~18 | redaction | — | **NO** (OpenAI-compatible security proxy) | [B] |
| `dativo-io/talon` | Go | ~9 | policy/redact | — | **NO** (governance gateway, EU/GDPR) | [B] |

(Stars approximate, June 2026.)

### Notable external corroboration of the pattern (non-OSS / blog) [B]
- AWS Bedrock AgentCore "MCP proxy" blog describes EXACTLY the desired pattern (tokenize args before upstream MCP, detokenize tokens in response) — but as a build-your-own sample, not a maintained OSS product.
- Microsoft "PII Shield" privacy proxy and dev.to "PII tokenization middleware" describe detector+vault+HTTP tokenize/detokenize for **text**, leaning on the LLM echoing `<Person_1>` tokens — chat-level, not tool-loop.

---

## 7. FINAL VERDICT (the load-bearing answer)

**Does any OSS do the full tool-call tokenization loop?**

- **Almost no.** The ecosystem overwhelmingly does **chat-content** masking (prompt-in, response-rehydrate). The tool-call argument round-trip is the **genuine gap**.
- **Exactly one OSS project read does it end-to-end: `KevinXuxuxu/anon_proxy`** — masks `tool_use.input` + `tool_result.content` on requests and **unmasks emitted `tool_use.input`** on responses, with a consistent persistable per-conversation store. But it's tiny (~28★), April-2026-new, an API-format proxy (relies on the client to round-trip tool_result back through it), and unproven in production. [A]
- **`LiteLLM`** does the **single model→tool hop** (unmask `function.arguments`, optionally re-mask output args) but its token map is **per-request**, so it does NOT itself maintain stable tokens across the multi-turn agent loop or reconcile a tool result to prior tokens. [A]
- **The flagship MCP gateway (`lasso-security/mcp-gateway`)** has the perfect *seams* (`sanitize_tool_call_args` + `sanitize_tool_call_result`) but ships **one-way irreversible** Presidio masking with the request side commented out. The hooks exist; the round-trip does not. [A]
- **Everything else** (Portkey, cloakpipe, veilstream, mirage, etc.) is one-way redaction or chat-content-only reversibility. [A][B]

**Conclusion:** A robust, persistent, consistent, production-grade **tool-call de-/re-tokenization loop (esp. MCP-native, with the result re-tokenized to the SAME tokens as the matching call)** is **NOT solved in OSS.** anon_proxy proves the concept at toy scale; LiteLLM and Lasso provide the nearest reusable pieces (LiteLLM's arg-unmask code; Lasso's MCP plugin seams). That is the real opportunity.

### What to STEAL (composite)
1. anon_proxy: `tool_use.input` / `tool_result.content` walking; `unmask_json` for streaming `partial_json`; longest-token-first regex; canonicalized consistent store; per-conversation persistable PIIStore.
2. LiteLLM: tool_calls/function_call arg unmask; truncation-prefix fallback for `max_tokens`-cut tokens; mask-output vs unmask-output split; streaming reassembly.
3. Lasso: MCP-native request/response plugin seams as the integration point.
4. LangChain: `_N` disambiguation; faker realistic operators; fuzzy fallback for LLM-mangled tokens; save/load.
5. veilstream: HMAC crypto-anchored pseudonyms (anti false-attribution). mirage: format-preserving fakes (Luhn-valid CC, valid-format keys); skip signed/encrypted blocks.

### What's MISSING across ALL of them (the gap to own)
- A **persistent, consistent token store keyed to the agent session** that re-tokenizes a tool RESULT to the SAME token a prior tool CALL used, across many turns.
- **MCP-native** round-trip (de-tokenize args at the gateway before the downstream MCP server executes; re-tokenize the server's result before it returns to the model) — Lasso has the seam, nobody filled it.
- n-to-n safety + crypto-anchored reversal + format-preserving fakes, **combined** with the tool-loop.
