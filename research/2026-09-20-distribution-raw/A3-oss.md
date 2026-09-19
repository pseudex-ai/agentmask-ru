# A3 — OSS: is any open-source PII layer TRANSPARENT to an LLM agent? (tool calls + tool results + the agent's own rewriting)

Date: 2026-09-20. Method: source read from raw.githubusercontent.com / `gh api` (GitHub REST), not READMEs, wherever a claim is graded [A]. Local copies of every file read are in `raw/src/` next to this report (prefix per project: `lc_`, `lg_`, `pres_`, `ll_`, `nemo_`, `gr_`, `pk_`, `kb_`, `pa_`, `pg_`, `pgd_`, `dfta_`, `ghost_`, `dw_`). ~31 fetch batches, ~55 files.

Grades: **[A]** verified in source · **[B]** documented, not verified in source · **[C]** README-asserted · **[D]** inference.

Checklist key (per the brief): 1 restore in answer text · 2 restore INSIDE `tool_calls[].function.arguments` keeping JSON valid · 3 tool results re-masked with the same substitute · 4 format-preserving fakes · 5 multi-turn persistence + canonicalisation · 6 streaming restore (split substitute, tool-arg deltas) · 7 survives the model's own rewriting (inflection / translit / initials / digit reformat) · 8 memory / cross-conversation scope · 9 partial mentions / corrections · 10 non-English morphology at mask time · 11 collision (fake == real) · 12 vault persistence / encryption · 13 published "agent unaffected" benchmark.

---

## 0. Executive verdict

**The owner's "no" is no longer literally true, but it is true on the axis that matters.** As of Sep 2026:

- **Items 2 + 3 together** (restore inside tool-call JSON, re-mask tool results with the same token) are now implemented in source by **six** projects: LiteLLM's Presidio hook (partially, and buggy), Elastic **Kibana**'s inference plugin (Elastic License 2.0, not OSI), and four 2026-born hobby-scale proxies — **PrivAiTe** (41★), **pasteguard** (754★), **DontFeedTheAI** (655★), **OpenGradient/ghost** (147★) — plus **piighost** (13★) as a LangChain/Pydantic-AI middleware rather than a proxy.
- **Item 7** (the agent's own form — inflected, transliterated, initials, reformatted digits) is covered by **nobody**. Every restore path found is exact `str.replace` / `indexOf` / `split().join()` / regex-alternation on a **placeholder** (`<PERSON_1>`, `[[PERSON_1]]`, `[PERSON:1]`, `PER_<hmac>`, `{{PERSON_1}}`). The only "fuzzy" options (LangChain `fuzzy_matching_strategy`, LLM Guard `MatchingStrategy.FUZZY`, PrivAiTe `_deanonymize_fuzzy`) are Levenshtein/SequenceMatcher over the placeholder string — they tolerate a typo in `<PERSON_1>`, not a declined «Ивановой» or «I.I. Ivanov». The single exception is a digit-signature reindex for phones in the Russian **dewil/pii-mask** (1★), which is a `/mask`+`/unmask` text service with no proxy, no tool calls, no streaming.
- **Items 10, 11, 9** (Russian morphology at mask time, fake==real collision, partial-mention resolution): **not implemented anywhere**. Realistic (Faker) fakes exist in LangChain, LLM Guard (`use_faker`), PrivAiTe (optional), DontFeedTheAI, daslabhq/pii-proxy, but none is inflected to the source's case, none is checksum-invalid by design, and none checks the fake against real values already in the vault (DontFeedTheAI checks uniqueness among *surrogates* only).
- **Item 13**: no project publishes an "agent unaffected" / tool-axis benchmark. cloakpipe and gaze publish detection numbers; PrivAiTe ships `verify.py` + `examples/demo_tool_call_leak.py` (a leak demo, not an agent-behaviour metric).

**So: 2+3 = yes (six projects, all placeholder-based, all 2026). 2+3+7 together = no OSS project.** The thing that remains unique to Pseudex is the combination: format-preserving *and* morphologically agreed fakes, restore that follows the model's rewriting (case, translit, initials, digit signature), conversation-scoped collision handling, and a measured tool-call axis.

---

## 1. Microsoft Presidio (`presidio-anonymizer` + `DeanonymizeEngine`)

- Repo: https://github.com/microsoft/presidio · ~5k★ · MIT · active (2026-09, `AHDSSurrogate` operator recently added).
- Files read: `presidio_anonymizer/deanonymize_engine.py`, `operators/__init__.py`, `operators/decrypt.py`, `core/engine_base.py`.

**What is reversible:** exactly one operator pair — `Encrypt` (AES) / `Decrypt`. Everything else (`Replace`, `Mask`, `Redact`, `Hash`, `Keep`, `Custom`, `AHDSSurrogate`) is one-way. `DeanonymizeKeep` exists only to pass an entity through.

**What metadata the reversal needs — the load-bearing point:** `DeanonymizeEngine.deanonymize()` is **positional**, not lookup-based:

```python
def deanonymize(self, text: str, entities: List[OperatorResult], operators: Dict[str, OperatorConfig]) -> EngineResult:
    """
    :param text: the full text with the encrypted entities
    :param entities: list of encrypted entities
    """
    return self._operate(text, entities, operators, OperatorType.Deanonymize)
```
and `engine_base._operate` slices by the recorded offsets:
```python
sorted_pii_entities = sorted(pii_entities, reverse=True)
for entity in sorted_pii_entities:
    text_to_operate_on = text_replace_builder.get_text_in_position(entity.start, entity.end)
```
So it can only restore a string in which the ciphertext still sits at the exact `start`/`end` recorded at anonymize time — i.e. the *same* string, or one edited only after every entity. A model response is a different string; a tool-call argument is a different string. Presidio itself has no notion of a mapping table, conversation, tool call, or stream.

| # | Verdict | Cite |
|---|---|---|
| 1 | not implemented (positional decrypt only) | `deanonymize_engine.py:deanonymize` [A] |
| 2 | no | — [A] |
| 3 | no | — [A] |
| 4 | no (AES ciphertext); `AHDSSurrogate` gives realistic surrogates but one-way | `operators/__init__.py` [A] |
| 5 | no mapping at all | [A] |
| 6 | no | [A] |
| 7 | no — offsets | `engine_base.py:_operate` [A] |
| 8–13 | no | [A] |

Presidio is a *detector + text operator*; every downstream project below re-implements the mapping/vault themselves.

---

## 2. LangChain `PresidioReversibleAnonymizer` (`langchain_experimental.data_anonymizer`)

- Repo: https://github.com/langchain-ai/langchain-experimental · (langchain_experimental, ~1.5k★ split-out) · MIT · low activity in 2026.
- Files read: `data_anonymizer/presidio.py`, `data_anonymizer/deanonymizer_matching_strategies.py`.

**Mapping:** in-process dict `self._deanonymizer_mapping` (`DeanonymizerMapping`), keyed `{entity_type: {fake: original}}`; `save_deanonymizer_mapping()` / `load_deanonymizer_mapping()` write **plaintext JSON/YAML** to disk. Faker fakes by default (`add_default_faker_operators=True`, `faker_seed`), so fakes are realistic names/emails/phones — format-preserving but **not** checksum-invalid, **not** collision-checked.

**Multi-turn consistency** is by exact original string:
```python
# Thanks to the built-in memory, all previously anonymised entities
# will be remembered and replaced by the same fake values:
>>> anonymizer.anonymize("My name is John Doe. Hi John Doe!")
'My name is Noah Rhodes. Hi Noah Rhodes!'
```
No canonicalisation: `+7 999…` and `8 999…` are two keys → two fakes.

**Deanonymize = the matching strategy over the whole text.** Default `exact_matching_strategy`:
```python
for entity_type in deanonymizer_mapping:
    for anonymized, original in deanonymizer_mapping[entity_type].items():
        text = text.replace(anonymized, original)
```
`case_insensitive_matching_strategy` does `re.sub(anonymized, original, text, flags=re.IGNORECASE)` — **the fake is used as a regex pattern unescaped** (a fake containing `.` or `(` is a regex bug). `fuzzy_matching_strategy` uses `fuzzysearch.find_near_matches(anonymized, text, max_l_dist=3)`; `ngram_fuzzy_matching_strategy` uses `fuzz.ratio(anonymized.lower(), segment.lower()) > 85` over word n-grams **and then rebuilds the text with `" ".join(text_words)`** — flattening all whitespace/newlines in the response.

What "fuzzy" buys for item 7: a Levenshtein-3 tolerance around the *fake name* — so «Noah Rhodes» ↔ «Noah Rhods» yes; a Russian fake declined («Ноа Роудса») is within distance ≤3 by accident for short endings but the same tolerance admits any similar-length word; transliteration («Noa Rouds» for «Ноа Роудс») is not reachable; initials («N. Rhodes») not reachable; a reformatted phone («+1-202-555-0143» → «(202) 555-0143») not reachable.

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `presidio.py:_deanonymize` [A] |
| 2 | **no** — text-only API; nothing walks `tool_calls` | [A] |
| 3 | no — the caller would have to call `anonymize()` on tool output themselves; mapping is shared so the same fake would result | [A]/[D] |
| 4 | Faker realistic, not checksum-invalid | `presidio.py:__init__` (`get_pseudoanonymizer_mapping`) [A] |
| 5 | in-process dict, exact-string key, plaintext JSON save/load | `save_deanonymizer_mapping` [A] |
| 6 | no | [A] |
| 7 | exact by default; optional Levenshtein-3 / n-gram ratio on the fake; no morphology/translit/initials/digits | `deanonymizer_matching_strategies.py` [A] |
| 8 | one object = one scope; `reset_deanonymizer_mapping()` | [A] |
| 9–11 | no | [A] |
| 12 | plaintext JSON/YAML file | [A] |
| 13 | no | — |

---

## 3. LLM Guard (protectai) — `Anonymize` / `Deanonymize` / `Vault`

- Repo: https://github.com/protectai/llm-guard · ~1.7k★ · MIT · active.
- Files read: `llm_guard/input_scanners/anonymize.py`, `llm_guard/output_scanners/deanonymize.py`, `llm_guard/vault.py`.

**Vault is a list of tuples in memory, nothing more:**
```python
class Vault:
    def __init__(self, tuples: Optional[List[Tuple]] = None):
        self._tuples = tuples or []
    def get(self) -> List[Tuple]: return self._tuples
    def placeholder_exists(self, placeholder: str) -> bool: ...
```
Placeholders are `[REDACTED_PERSON_1]`; `use_faker=True` swaps in `get_fake_value(entity_type)`.

**Deanonymize = exact `str.replace` by default**, with `CASE_INSENSITIVE` (`re.sub(vault_item[0], …, flags=re.IGNORECASE)`, again unescaped), `FUZZY` (fuzzysearch, `max_l_dist=3`), `COMBINED_EXACT_FUZZY`:
```python
def _match_exact(text, vault_items):
    for vault_item in vault_items:
        text = text.replace(vault_item[0], vault_item[1])
```

**A defect found by reading (grade A, not executed):** the multi-turn dedup in `Anonymize._anonymize` only recognises vault rows whose placeholder starts with the bracket prefix:
```python
vault_entities = [
    (entity_placeholder, entity_vault_value)
    for entity_placeholder, entity_vault_value in vault.get()
    if entity_placeholder.startswith(f"[REDACTED_{entity_type}_")
]
```
With `use_faker=True` the stored placeholder IS the faker value (`_get_entity_placeholder` returns `get_fake_value(...)`), so it never starts with `[REDACTED_` — the same real value gets a **fresh fake on every turn**, and `Deanonymize` restores all of them (they are all in the vault), so it looks correct on the way back while the model saw N names for one person.

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `deanonymize.py:Deanonymize.scan` [A] |
| 2 | **no** — `scan(prompt, output)` is text; nothing knows tool calls | [A] |
| 3 | no (caller could run `Anonymize` on tool output; dedup works only with bracket placeholders) | [A] |
| 4 | placeholder by default; Faker optional; not checksum-invalid | `anonymize.py:_get_entity_placeholder` [A] |
| 5 | in-memory list; exact value match; faker mode breaks consistency (above) | `anonymize.py:_anonymize` [A] |
| 6 | no | [A] |
| 7 | exact default; optional Levenshtein-3 on the placeholder | `deanonymize.py:MatchingStrategy` [A] |
| 8 | one `Vault` object per scope; nothing else | [A] |
| 9–11 | no | [A] |
| 12 | in-memory only | `vault.py` [A] |
| 13 | no | — |

---

## 4. LiteLLM proxy — Presidio guardrail hook (`litellm/proxy/guardrails/guardrail_hooks/presidio.py`)

- Repo: https://github.com/BerriAI/litellm · ~30k★ · MIT · **very active** (this file: commits 2026-08-29 and 2026-09-02, "fix(guardrails): keep the presidio output masker from unmasking after an in-memory update"). File is 1 649 lines.

This is the one big-name OSS gateway that now touches tool calls — and the details are the story.

**Masking (pre-call), `async_pre_call_hook`:** iterates *every* message's `content` (string or `text` parts) and replaces with `<TYPE_n>` tokens when `output_parse_pii=True`. It does **not** read `messages[].tool_calls[].function.arguments` in the history — only `content`. So a real value the proxy itself restored into a previous assistant tool call and that the client faithfully re-sends goes **upstream in the clear** on the next turn. `role: tool` content IS masked (as content).

**Token numbering restarts per message, into a shared map — a collision by construction (grade A by reading):**
```python
sorted_forward = sorted(analyze_results, key=lambda x: x["start"])
seq_map = {}
for idx, ar in enumerate(sorted_forward, start=1):
    seq_map[(ar["start"], ar["end"])] = idx
...
    replacement = f"<{entity_type}_{seq}>"
    pii_tokens[replacement] = text[start:end]
```
`_finalize_presidio_anonymize_numbered_tokens` is called once per message (via `asyncio.gather` over `check_pii(text=…)`), `seq` starts at 1 each time, and `pii_tokens` is the single `request_data["metadata"]["pii_tokens"]`. Two messages that each open with a different person both become `<PERSON_1>`; the last writer wins; both are restored to the same person. There is no value→token dedup either, so the same person in two messages gets `<PERSON_1>` only by luck of position.

**Unmasking (post-call), `_process_response_for_pii`, "2. Process tool calls":**
```python
tool_calls = getattr(message, "tool_calls", None)
if tool_calls:
    for tool_call in tool_calls:
        function = getattr(tool_call, "function", None)
        if function and hasattr(function, "arguments"):
            args = function.arguments
            if isinstance(args, str):
                if mode == "unmask":
                    function.arguments = self._unmask_pii_text(args, pii_tokens)
```
and `_unmask_pii_text` is `text.replace(token, original_text)` — **no JSON escaping**. A real value containing `"` or `\` (Russian «ООО "Заря"», any Windows path) is spliced raw into the JSON string literal; the tool call stops parsing. The fallback for a token truncated by `max_tokens` (suffix overlap `min(20, len(token)//2)`) is the only non-exact matching.

**Streaming, `_stream_pii_unmasking`:** collects **every** chunk into `remaining_chunks`, then `stream_chunk_builder(...)`, unmasks the assembled response, and yields **one** synthetic stream via `convert_model_response_to_streaming`. Streaming is disabled in effect (the client sees one chunk at the end). `except Exception: … for chunk in remaining_chunks: yield chunk` — on any error the raw chunks with `<PERSON_n>` tokens go to the client (fail-open for the token, not the PII).

**Scope:** `pii_tokens` lives in `request_data["metadata"]` — per request. No vault, no persistence, no cross-turn map (the whole transcript is re-masked per request, which is what makes the numbering collision reachable).

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `_process_response_for_pii` [A] |
| 2 | **yes, but plain `str.replace`, no JSON escaping** | `_unmask_pii_text`, "2. Process tool calls" [A] |
| 3 | tool `content` masked; history `tool_calls.arguments` NOT masked; per-message numbering → cross-message token collisions | `async_pre_call_hook`, `_finalize_presidio_anonymize_numbered_tokens` [A] |
| 4 | `<TYPE_n>` placeholders | [A] |
| 5 | per-request only; no canonicalisation | [A] |
| 6 | buffers the whole stream, emits one chunk; tool-arg deltas restored only inside that assembled response | `_stream_pii_unmasking` [A] |
| 7 | exact; suffix-overlap fallback for truncation only | `_unmask_pii_text` [A] |
| 8 | none | [A] |
| 9–11 | no | [A] |
| 12 | none (request metadata) | [A] |
| 13 | no | — |

Also read: the Anthropic-shape path (`_process_anthropic_response_for_pii`) restores `block["text"]` only; `tool_use.input` on the Anthropic shape is not walked (the OpenAI shape is).

---

## 5. NVIDIA NeMo Guardrails — `sensitive_data_detection`

- Repo: https://github.com/NVIDIA/NeMo-Guardrails · ~5k★ · Apache-2.0.
- File read: `nemoguardrails/library/sensitive_data_detection/actions.py` (201 lines).

```python
operators: dict[str, Any] = {}
for entity in entities:
    operators[entity] = OperatorConfig("replace")
...
anonymizer = AnonymizerEngine()
masked_results = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
```
`replace` with no `new_value` → Presidio's default `<ENTITY_TYPE>` (un-numbered), no mapping is kept, no deanonymize action exists in the module. **Irreversible.** Items 1–13: no [A]. (NVIDIA's separate `NVIDIA-NeMo/Anonymizer`, 122★, created 2026-01, is a *dataset* anonymiser: "No deanonymization capability is mentioned" — one-way, batch CSV, English-tested. [B])

---

## 6. Guardrails AI — `DetectPII` validator

- Repo: https://github.com/guardrails-ai/detect_pii (hub validator) · Apache-2.0.
- File read: `validator/main.py` (223 lines).

```python
anonymized_text = self.pii_anonymizer.anonymize(text=text, analyzer_results=results)
...
return FailResult(error_message=..., fix_value=anonymized_text)
```
`AnonymizerEngine.anonymize` with default operators → `<PERSON>`; the validator either fails or substitutes `fix_value`. **Irreversible.** Items 1–13: no [A].

---

## 7. Portkey AI Gateway (OSS)

- Repo: https://github.com/Portkey-AI/gateway · ~8k★ · MIT.
- Read: `plugins/` listing (acuvity aporia azure bedrock crowdstrike-aidr default exa f5-guardrails javelin lasso mistral pangea panw-prisma-airs patronus pillar portkey promptfoo promptsecurity qualifire sydelabs walledai) and `plugins/portkey/pii.ts` (199 lines).

`pii.ts` calls Portkey's hosted service, takes `item.processed_text` as `redactedText`, and when `parameters.redact && hasPII` sets `transformedData` — the request is rewritten; **nothing on the response side restores anything**, and `embed` requests refuse redaction. All third-party plugins (Pangea, Lasso, Patronus…) are detect/redact verdicts against hosted APIs. **Irreversible.** Items 1–13: no [A].

---

## 8. Bifrost (maximhq) and Kong

- Bifrost OSS `plugins/`: `compat governance jsonparser logging maxim mocker modelcatalogresolver otel prompts routing semanticcache telemetry` — **no PII module at all** in the open-source tree [A].
- Kong `ai-sanitizer` is an Enterprise plugin (commercial, out of scope per the brief); nothing reversible in Kong OSS [D].

---

## 9. Elastic Kibana — inference plugin anonymization (**new, 2026-03**)

- Repo: https://github.com/elastic/kibana · ~20k★ · **Elastic License 2.0** (x-pack: source-available, not OSI open source) · PR #252616 "Anonymization Platform Service — Backend primitives + policy + replacements + inference runtime" (2026-03-05), #256112 "Fix deanonymization offset drift" (2026-03-05).
- Files read: `x-pack/platform/plugins/shared/inference/server/chat_complete/anonymization/{deanonymize_message.ts, deanonymize.ts, get_entity_mask.ts, anonymize_messages.ts, get_anonymizable_message_parts.ts}`.

**What is anonymized per role** (`get_anonymizable_message_parts.ts`):
```ts
if (message.role === MessageRole.Tool) {
  return { response: message.response, ...(message.data !== undefined ? { data: message.data } : {}) };
}
if (message.role === MessageRole.Assistant) {
  return { content: message.content, toolCalls: message.toolCalls?.map((toolCall) => ({ function: toolCall.function })) };
}
return { content: message.content };
```
So **tool results (`response`, `data`) and historical `toolCalls.function` (name+arguments object) are masked on the way in** — item 3 yes, and the LiteLLM gap above is closed here.

**Mask = deterministic token, not a counter:** `get_entity_mask.ts` → `generateToken(salt, class_name, field, value)` (HMAC-SHA256 per Kibana space) or legacy `${class_name}_${objectHash({value, class_name})}` — e.g. `PER_3f9a…`. Same value → same mask across every conversation in a space; a `replacementsId` / `knownReplacements` table is persisted in Elasticsearch so the map survives. Format-preserving: no.

**Deanonymize = exact `indexOf` over masks, walking the parsed structure** (`deanonymize.ts`):
```ts
for (const [mask, entity] of entitiesByMask) {
  let index = content.indexOf(mask);
  while (index !== -1) { matches.push({ start: index, mask, entity }); index = content.indexOf(mask, index + mask.length); }
}
```
`deanonymizeStructure` recurses into `toolCalls[].function.arguments` **as an object** (Kibana's internal `Message` keeps arguments parsed), so item 2 is JSON-safe by construction; `deanonymize_message.ts` re-serialises with `JSON.stringify(tc.function.arguments)`.

**Streaming:** `filter(event => event.type !== ChatCompletionChunk)` — "Filter out original chunk events (we recreate a single deanonymized chunk later)" → one synthetic chunk at the end. Collapsed, like LiteLLM.

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `deanonymize.ts` [A] |
| 2 | yes, on the parsed args object → JSON-safe | `deanonymize.ts:deanonymizeStructure`, `deanonymize_message.ts` [A] |
| 3 | yes: tool `response`/`data` masked; history `toolCalls.function` masked; deterministic mask ⇒ same token | `get_anonymizable_message_parts.ts`, `get_entity_mask.ts` [A] |
| 4 | no — `PER_<hash>` | [A] |
| 5 | yes by deterministic HMAC + persisted `knownReplacements`; keyed on exact value (no canonicalisation) | `anonymize_messages.ts` [A] |
| 6 | collapsed to one chunk | `deanonymize_message.ts` [A] |
| 7 | exact `indexOf` | [A] |
| 8 | per-space salt: "stable within a space and prevents cross-space correlation" — i.e. **customer-wide**, no conversation scope | `get_entity_mask.ts` [A] |
| 9–11 | no | [A] |
| 12 | Elasticsearch-persisted replacements | [B] |
| 13 | no | — |

Detection is Elastic's NER model + regex rules; English-centric [D].

---

## 10. PrivAiTe (crp4222) — **new, created 2026-05-07, pushed 2026-09-18**

- https://github.com/crp4222/PrivAiTe · 41★ · BSD-3 · Python · "Self-hosted PII redaction proxy for LLM APIs and agent CLIs … tool-call arguments included, then restores them in the reply."
- Files read: `privaite/gateway/{scrub.py, restore.py}`, `privaite/pii/{deanonymizer.py, mapping.py, anonymizer.py}`, `privaite/streaming/handler.py` (skimmed).

This is the most carefully engineered of the new wave on the tool-call axis, and its own comments read like the Pseudex CLAUDE.md.

**Item 2 — JSON-aware restore of `arguments`** (`restore.py`):
```python
def _restore_json_arguments(engine, arguments, mapping):
    """Restore a function/MCP call's `arguments`: a JSON document inside a
    string. Plain substitution would splice a raw quote, backslash or newline
    from the original into a JSON string literal and the client's json.loads
    of the arguments would fail; restore on the parsed tree and re-encode
    instead."""
    plain = engine.restore_document(arguments, mapping)
    if plain == arguments: return arguments
    try: parsed = json.loads(arguments)
    except ValueError: return plain
    restored = restore_tree(engine, parsed, mapping, frozenset())
    return json.dumps(restored, ensure_ascii=False)
```
Scrub side (`scrub.py:_scrub_json_arguments`) mirrors it: `json.loads` → walk leaves → `json.dumps`.

**Item 3 — tool results and echoed tool calls re-scrubbed:** Anthropic `tool_use / server_tool_use / mcp_tool_use` inputs and `tool_result / mcp_tool_result` content; Responses `function_call.arguments`, `custom_tool_call.input`, `function_call_output`, `custom_tool_call_output`, `mcp_call`. The comment records a real round-trip leak they fixed:
> "Missing server_tool_use here was a confirmed round-trip leak (Claude Code's WebSearch/WebFetch input restored on turn N, forwarded raw on turn N+1)."

**Item 6 — streaming with holdback, per channel, JSON-escaped for argument deltas** (`restore.py:_SSERestorer._feed`):
```python
# A JSON-fragment channel (streamed tool arguments) restores with
# escaped originals, so the spliced value stays a valid piece of
# the JSON string literal it lands in.
mapping = json_escaped_mapping(self._mapping) if json_fragment else self._mapping
buffer = self._buffers[channel] = StreamingDeAnonymizer(mapping)
```
plus `flush()` emitting synthetic delta events so a partial placeholder at a block boundary is never dropped. Thinking blocks are skipped on both legs (Anthropic rejects modified thinking).

**Item 7 — matching:** `_deanonymize_exact` = `text.replace(fake, original)` longest-first; optional `_deanonymize_fuzzy` = `SequenceMatcher(...).ratio() >= fuzzy_threshold` over same-word-count token windows, edge punctuation stripped, with a guard that refuses to fuzzy-match an intact-but-unknown placeholder (`<PERSON_3>` hallucinated). No inflection/translit/initials/digit logic.

**Items 4/5/8/12 — scope:** `PIIMapping` is a per-request in-memory dataclass keyed on the **exact original string** (`_original_to_fake[original]`), default placeholder `f"<{entity_type}_{idx}>"`, Faker optional per type (`faker_providers.py`), `mask`/`redact` per type for secrets/cards. README (June 2026): "The reversible mapping is still per-request and still dropped when the request ends." No vault, no cross-turn persistence, no canonicalisation, no conversation id — consistency exists only because the whole transcript is re-scrubbed every request.

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `restore.py:restore_tree` [A] |
| 2 | **yes, JSON-safe** | `restore.py:_restore_json_arguments` [A] |
| 3 | **yes** (Anthropic, Responses, Chat) | `scrub.py` `_TOOL_USE_TYPES`/`_TOOL_RESULT_TYPES`, `_scrub_json_arguments` [A] |
| 4 | placeholder default; Faker optional; not checksum-invalid | `anonymizer.py:_make_placeholder` [A] |
| 5 | per request only; exact-string key | `mapping.py` [A] |
| 6 | **yes**, holdback per channel, JSON-escaped argument deltas | `restore.py:_SSERestorer` [A] |
| 7 | exact + optional SequenceMatcher; none of the four agent forms | `deanonymizer.py` [A] |
| 8 | none (per request) | [A] |
| 9–11 | no | [A] |
| 12 | none; optional detection cache holds salted hashes only | README [B] |
| 13 | `verify.py`, `examples/demo_tool_call_leak.py` — a leak demo, not an agent-effect metric | [B] |
| lang | FR/EN recognizers (`recognizer_fr_date.py`); no RU | [A] |

---

## 11. piighost (Athroniaeth) — **new, created 2026-03-12, pushed 2026-09-18**

- https://github.com/Athroniaeth/piighost · 13★ · MIT · Python · "tokens stable across a conversation and tool calls … LangChain, Pydantic AI, LlamaIndex, plus a dockerized OpenAI-compatible proxy … optional AES-GCM encrypted Redis memory".
- Files read: `src/piighost/integrations/langchain/middleware.py`, `pipeline/thread.py`, `components/anonymizer/base.py`, `components/placeholder/streaming.py` (listed).

Architecturally the closest OSS to Pseudex's *sidecar* shape, but as an **in-process framework middleware**: the tool call is intercepted where it executes.

**Item 2/3 — `awrap_tool_call`** (LangChain agent middleware):
```python
if deanonymize_input:
    # Never mutate request.tool_call: it is the same dict LangGraph keeps
    # in the AIMessage.tool_calls of the state, so mutating it would leave
    # the deanonymized values in the state and feed them back to the model
    # on the next turn. Build a new call and a new request instead.
    deanonymized = await self._deid.deanonymize_value(request.tool_call["args"], thread_id)
    new_call = cast("ToolCall", {**request.tool_call, "args": deanonymized})
    request = request.override(tool_call=new_call)
response = await handler(request)
if anonymize_output:
    await self._anonymize_tool_output(response, thread_id)
```
`args` is already a dict (LangChain parsed it) → JSON-safe by construction. `_reanonymize_tool_calls` re-masks every `AIMessage.tool_calls` before the model call ("a clear value that slipped into them must not reach the model"). `ToolMessage` is anonymized under the USER role.

**Item 5/8/12 — thread memory:** `ThreadAnonymizationPipeline` — "A value keeps one placeholder for the whole thread"; `thread_id` is **required** ("there is no shared default, so two callers … cannot share"); backends `InMemoryConversationMemory`, `redis_backend.py`, `sqlalchemy_backend.py`; `crypto/cipher/aesgcm.py`. There is a `forget_thread()`. So: conversation-scoped, persisted, encryptable. Entity linking across surface variants exists at *detection* time (`entity_resolver/fuzzy.py`, `linker/exact.py`) — that is the "same entity → one token" mechanism, not restore-time matching.

**Item 7 — restore matching** (`anonymizer/base.py:BaseAnonymizer.deanonymize`): "a single regex pass over an alternation of the tokens, longest first" — `re.escape(token)` for each, exact. Placeholder factories: `label` (`[PERSON:1]`), `label_counter`, `label_hash`, `mask`, `redact`, `tags`; no Faker. A model cannot inflect `[PERSON:1]`, so the question is moot inside placeholders — and the price is that the model sees brackets, not a person (their `examples/strategies/invented_placeholder.py` handles the model *inventing* a placeholder).

**Item 6:** `components/placeholder/streaming.py` (244 lines) + `deanonymize_stream(source, thread_id)` — a holdback streaming restorer for content; tool-arg deltas N/A in the middleware shape (LangChain hands complete args). [B]

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `pipeline/thread.py:deanonymize` [A] |
| 2 | yes (dict args, middleware) | `middleware.py:awrap_tool_call` [A] |
| 3 | yes, same thread token | `middleware.py:_anonymize_tool_output`, `_reanonymize_tool_calls` [A] |
| 4 | no — label placeholders | `components/placeholder/*` [A] |
| 5 | yes: per-thread memory, Redis/SQL, detection-time entity linking | `pipeline/thread.py` [A] |
| 6 | content streaming holdback | `placeholder/streaming.py` [B] |
| 7 | exact regex alternation | `anonymizer/base.py` [A] |
| 8 | thread-scoped, explicit id required | [A] |
| 9 | partial mentions linked at detection (`entity_resolver`), not resolved against earlier fuller mention in the vault | [B] |
| 10–11 | no | [A] |
| 12 | Redis / SQLAlchemy, AES-GCM optional | file list [A]/[B] |
| 13 | no | — |
| proxy | the OpenAI-compatible proxy leg (`integrations/client/remote.py`) was **not** read; whether the *proxy* walks `tool_calls` is unverified | [C] |

---

## 12. pasteguard (sgasser) — **new, created 2026-01-08, 754★** (the largest of the wave)

- https://github.com/sgasser/pasteguard · Apache-2.0 · TypeScript · "Local-first privacy proxy for browser chat, AI APIs, and coding agents."
- Files read: `src/masking/{restorer.ts, stream-restorer.ts, placeholders.ts, restore-policy.ts, context.ts}`, `src/masking/extractors/openai.ts`, `src/providers/openai/stream-transformer.ts`.

**Item 2 — escaping-aware restore in `function.arguments`** (`extractors/openai.ts:66`):
```ts
arguments: restorePlaceholders(functionCall.arguments, context, (original) =>
  JSON.stringify(formatValue ? formatValue(original) : original).slice(1, -1),
```
i.e. the original is JSON-string-escaped before being spliced into the serialized arguments. History re-masking: `remaskSerializedJsonValues(functionCall.arguments, replacements)` for `role === "assistant"` messages with `tool_calls` (lines 287–318).

**Item 3:** `extractTexts` walks every message's `content` regardless of role (tool results included); tokens are per-request `[[TYPE_N]]` from `createPlaceholderContext()` so the same value maps to the same token within the request.

**Item 6 — real streaming, per tool-call channel:** `stream-transformer.ts` keeps one `StreamRestorer` per `(choiceIndex, toolCallIndex)` (`argumentChannelsByPosition`), feeds `delta.tool_calls[].function.arguments` through `restoreChunk`, flushes on finish; holdback rule in `findPartialPlaceholderStart` (an open `[[` without `]]`, or a trailing `[`). Argument channels use a separate `argumentPiiContext` (escaping for the streamed fragment is implied by the separate context; not read line-by-line) [A for holdback, B for escaping in the stream path].

**Item 7:** `restorePlaceholders` = `result.split(placeholder).join(replacement)`, longest first. Exact only.

| # | Verdict | Cite |
|---|---|---|
| 1 | yes | `context.ts:restorePlaceholders` [A] |
| 2 | yes, JSON-escaped splice | `extractors/openai.ts:66` [A] |
| 3 | yes (content of every role; assistant tool_calls re-masked) | `extractors/openai.ts:287–318` [A] |
| 4 | no — `[[PERSON_1]]` | `placeholders.ts` [A] |
| 5 | per request (`PlaceholderContext` dict) | `context.ts` [A] |
| 6 | **yes**, incl. tool-arg deltas per channel | `providers/openai/stream-transformer.ts:116–135` [A] |
| 7 | exact | [A] |
| 8 | none | [A] |
| 9–11 | no | [A] |
| 12 | none | [A] |
| 13 | `benchmarks/pii-accuracy/` — detection only | [A] |

---

## 13. DontFeedTheAI (zeroc00I) — **new, created 2026-04-13, 655★**

- https://github.com/zeroc00I/DontFeedTheAI · MIT · Python · pentest-oriented ("engagement" = client scope).
- Files read: `src/providers/openai_compat.py`, `src/anonymizer.py`, `src/vault.py`, `src/surrogates.py`.

- Item 2: `_deanon_message` → `parsed = json.loads(args); fn["arguments"] = json.dumps(deanon_value(parsed))` — walks the parsed tree, JSON-safe [A].
- Item 3: `anonymize_chat_request` anonymizes `role in ("user", "tool")` content (system handled separately); assistant history not re-masked [A].
- Item 4: **Faker realistic surrogates** (`surrogates.py`: `Faker()`, `_unique(...)` guarantees uniqueness among surrogates; no checksum-invalid, no real-collision check) [A].
- Item 5/12: **SQLite vault** `pii_vault(engagement, original, entity_type, surrogate)` UNIQUE(engagement, original, entity_type) — persistent, plaintext `sqlite3`, exact-string key [A].
- Item 6: `emit_chat_completion_sse` — "Upstream is called with stream=false so the full body can be deanonymized first" → fake stream [A].
- Item 7: `deanonymize` = `result.replace(surrogate, original)` longest-first, exact [A].
- Item 8: engagement scope (customer-wide), no conversation scope [A].
- 9–11, 13: no.

---

## 14. OpenGradient/ghost — created 2026-06-09, 147★, MIT

- File read: `privacy/scrubbing_proxy.py` (613 lines; Presidio-backed).
- `_walk_strings` reaches "messages[].content, tool_calls[].function.arguments, tool / …" with a per-request mapping; `_deanonymize_body` restores `msg["content"]` and `fn["arguments"]` via `presidio_scrub.deanonymize(fn["arguments"], mapping)` — on the **serialized string** (no JSON re-encode seen) and "Tool-call arguments are de-anonymized only for LOCAL tools" [A]. Streaming de-anon claimed in comments, not read [C]. Per-request mapping, placeholders. Item 7 exact [D].

---

## 15. Rust pair: CertaMesh/gaze and rohansx/cloakpipe (README-level only)

- **gaze** (12★, Apache-2.0, created 2026-04-11): "The JSON the model fills in carries placeholders, and Gaze restores them before your tool runs" [C]; placeholders `<Name_1>` / `<{session_hex}:Name_1>`; "A placeholder Gaze never issued is refused, never guessed" (exact) [C]; session manifest signed, `scope = "persistent" ttl_secs = 86400` [C]; no streaming mentioned; German NER focus; a *detection* benchmark ("still let 20.7 % of PII bytes through") — no agent benchmark.
- **cloakpipe** (43★, MIT, created 2026-03-06): "SSE streaming rehydration", "AES-256-GCM" vault, tokens `PERSON_042` "deterministic within a session… non-deterministic across sessions" [C]; **no mention of tool calls** [C]; E2E protection 91.7% (detection) — no agent benchmark.

---

## 16. Russian-language OSS

- **dewil/pii-mask** (1★, MIT, created 2026-07-24, pushed 2026-09-02) — «Локальный шлюз маскировки персональных данных перед отправкой текста в облачные LLM: mask/unmask, stateless mapping, ПД-форматы РФ и русский NER». Files read: `pii_mask/core.py`, `api.py`.
  - Surface: `POST /mask`, `POST /unmask` only — **no proxy, no tool calls, no streaming** [A].
  - Placeholders `{{PERSON_1}}`; **format-preserving fakes for PHONE/EMAIL** (`+7 000 000-NN-NN`, `userN@example.com`) [A].
  - **Digit-signature reindex on unmask** — the one item-7 mechanism found anywhere in OSS:
    ```python
    phone_by_digits = {digits(placeholder): rec["original"] for placeholder, rec in labels.items() if rec["type"] == "PHONE"}
    def sub_phone(m):
        d = digits(m.group(0))
        if d in phone_by_digits: return phone_by_digits[d]
        if d[1:4] == "000":  # выдуманный моделью номер из фейкового диапазона
            return UNKNOWN
    ```
    and an unknown-label guard: «метка, которой не было во входе, при unmask превращается в UNKNOWN — защита от выдуманных моделью данных».
  - Word-form linking at mask time: «одинаковая сущность (включая словоформы) -> одна метка на весь диалог» via `ent.key` + `aliases` (Natasha NER) [A]; nothing inflects the placeholder (it is a `{{…}}` label).
  - Golden test asserts «Обратимость: Roundtrip mask -> unmask, в том числе когда модель переформатировала телефон» [B].
  - Design doc explicitly says this is pseudonymisation, not 152-ФЗ обезличивание: «Пока он [mapping.json] существует, данные остаются персональными».
- **Pioneer113/mcp-152fz-anonymizer** (4★, MIT) — MCP server + API; placeholders `<PASSPORT_RF>`, `<SNILS>`, `<PERSON>` **un-numbered** → irreversible [C].
- natasha / deeppavlov / pullenti — detection only (not re-verified; well known) [D].
- Hivetrace — publishes `pii-bench` dataset (used by Pseudex's own eval); no reversible OSS layer found [D].
- Jay Guard (Just AI), GPTunneL «Обфускатор» — commercial, out of scope; noted only because the RU search surfaces them first.

---

## 17. Others surfaced (not read at source; leads only)

daslabhq/pii-proxy (7★, "Mask entire objects (e.g., tool call inputs)", Faker + "format-preserving fake date") [C]; GetSHIM/shim (8★, `privacy/deanonymizer.py`) [C]; KevinXuxuxu/anon_proxy (32★) [C]; SteamedFish/opencode-guard (`response-unmasker.js`) [C]; coreyt/airlock, keefar/proxymus-prive, maskflow/maskflow, arturoaguileraa/sift-llm (`rehydrate.rs`), DavidCarliez/cover (49★, Go, coding agents), censgate/redact (22★, Rust gateway), occludra/gateway (39★), fishonbike/vault-engine (24★, Chinese), akazah/prompt-anonymizer (29★, browser), Privalyse/privalyse-mask (3★), lotharschulz/pii-redaction-guard (0★, Presidio exploration), st-gr/sail-proxy pseudonymization plugin (1★, AGPL), Kiji Privacy Proxy (Dataiku-backed, ONNX local; repo not located under `dataiku/kiji`). Semantic Kernel / Chainlit / OpenLLMetry: no reversible PII layer known; not investigated [D].

---

## 18. Cross-project matrix

Legend: ✔ implemented (source) · ◐ partial · ✗ no · ? unverified · — n/a

| Project | 1 text | 2 tool args JSON-safe | 3 tool results re-masked | 4 fmt-preserving | 5 multi-turn + canon | 6 streaming (args) | 7 agent's own form | 8 scope | 9 partial | 10 RU morph | 11 collision | 12 vault | 13 agent bench |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Presidio | ✗ positional | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | — | ✗ |
| LangChain Reversible | ✔ | ✗ | ✗ | ◐ Faker | ◐ dict, no canon | ✗ | ◐ Lev-3 on fake | object | ✗ | ✗ | ✗ | JSON file | ✗ |
| LLM Guard | ✔ | ✗ | ✗ | ◐ Faker (breaks consistency) | ◐ list, no canon | ✗ | ◐ Lev-3 | object | ✗ | ✗ | ✗ | memory | ✗ |
| LiteLLM presidio | ✔ | ◐ **raw replace, no escaping** | ◐ content yes; history args no; **token collision** | ✗ | ✗ per request | ◐ collapsed | ✗ | none | ✗ | ✗ | ✗ | none | ✗ |
| NeMo Guardrails | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | — | ✗ |
| Guardrails AI | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | — | ✗ |
| Portkey | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | — | ✗ |
| Bifrost / Kong OSS | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **Kibana** (ELv2) | ✔ | ✔ parsed obj | ✔ | ✗ hash token | ✔ HMAC + ES, no canon | ◐ collapsed | ✗ exact | space-wide | ✗ | ✗ | ✗ | ES | ✗ |
| **PrivAiTe** | ✔ | ✔ | ✔ | ◐ Faker opt | ✗ per request | ✔ holdback + escaped arg deltas | ◐ SequenceMatcher | none | ✗ | ✗ | ✗ | none | ◐ leak demo |
| **piighost** (middleware) | ✔ | ✔ dict args | ✔ | ✗ labels | ✔ thread, Redis/SQL | ◐ content | ✗ exact | thread | ◐ detection-time linking | ✗ | ✗ | Redis/SQL, AES-GCM | ✗ |
| **pasteguard** | ✔ | ✔ escaped | ✔ | ✗ | ✗ per request | ✔ per-channel arg deltas | ✗ exact | none | ✗ | ✗ | ✗ | none | ✗ |
| **DontFeedTheAI** | ✔ | ✔ parsed | ◐ user+tool only | ◐ Faker | ✔ SQLite, no canon | ✗ fake stream | ✗ exact | engagement | ✗ | ✗ | ◐ unique among fakes | SQLite plain | ✗ |
| OpenGradient/ghost | ✔ | ◐ string replace | ◐ | ✗ | ✗ per request | ? | ✗ | none | ✗ | ✗ | ✗ | none | ✗ |
| gaze (README) | ✔ | ? claimed | ? | ✗ | ◐ session manifest | ✗ | ✗ exact | session | ✗ | ✗ | ✗ | signed blob | ✗ |
| cloakpipe (README) | ✔ | ✗ not mentioned | ? | ✗ | ◐ session | ◐ content | ? | session | ✗ | ✗ | ✗ | AES-GCM | ✗ |
| dewil/pii-mask (RU) | ✔ | ✗ no proxy | ✗ | ◐ phone/email | ◐ stateless mapping, word-form aliases | ✗ | ◐ **digit reindex (phone)** | caller-held | ◐ aliases | ◐ NER lemma linking | ✗ | none (caller) | ✗ |

**Columns 2+3 together:** Kibana, PrivAiTe, piighost, pasteguard, DontFeedTheAI (partial), LiteLLM (partial/buggy), ghost (partial).
**Columns 2+3+7 together:** none.
**Column 10 or 11 anywhere:** none.

---

## 19. What is new Jun–Sep 2026 (relative to a "no" verdict formed earlier)

1. **LiteLLM** added tool-call unmasking to the Presidio hook and reworked streaming (commits 2026-08-29, 2026-09-02). It is plain `str.replace` into serialized JSON, per-message token numbering collides across messages, history tool-call args are not re-masked, and streaming is collapsed. Real, but not a transparent layer.
2. A **wave of ≥15 hobby proxies** created Jan–Aug 2026 (PrivAiTe May, piighost Mar, gaze Apr, cloakpipe Mar, pasteguard Jan, DontFeedTheAI Apr, ghost Jun, cover Aug, shim Aug, maskflow Aug, dewil/pii-mask Jul, vault-engine Jun…). Four of them (PrivAiTe, pasteguard, DontFeedTheAI, Kibana) got tool-call JSON handling right; PrivAiTe and pasteguard got streaming tool-arg deltas right. None went past placeholders, none has a vault with canonicalisation + conversation scope + collision handling together, none measures the tool axis.
3. **Kibana** shipped an anonymization platform (March 2026, Elastic License 2.0): deterministic HMAC tokens, persisted replacements, tool results and tool calls covered, streaming collapsed.
4. **NVIDIA NeMo Anonymizer** (Jan 2026) — one-way dataset tool, not a runtime layer.
5. Presidio gained `AHDSSurrogate` (Azure Health Data Services realistic surrogates) — still one-way.

---

## 20. Defects worth citing when arguing the point

- **LiteLLM `<PERSON_1>` collision** — `_finalize_presidio_anonymize_numbered_tokens` restarts `seq` at 1 per message and writes into one shared `pii_tokens`; `asyncio.gather` makes the winner order-dependent. [A, by reading]
- **LiteLLM raw splice into JSON** — `function.arguments = self._unmask_pii_text(args, pii_tokens)`; `_unmask_pii_text` is `text.replace(token, original_text)`. [A]
- **LiteLLM history leak** — `async_pre_call_hook` reads only `m.get("content")`; assistant `tool_calls[].function.arguments` in the transcript pass through unmasked. [A]
- **LLM Guard faker mode** — vault dedup filters `startswith("[REDACTED_{type}_")`, so `use_faker=True` mints a new fake per turn. [A]
- **LangChain / LLM Guard case-insensitive** — `re.sub(fake, original, …)` with the fake unescaped as a regex. [A]
- **LangChain ngram strategy** — rebuilds output with `" ".join(text_words)`, flattening whitespace. [A]
- **Kibana / LiteLLM / DontFeedTheAI streaming** — the entire stream is buffered and re-emitted as one chunk (or upstream is called with `stream=false`). [A]

---

## 21. Fetch log (batches)

1 LangChain+LLM Guard (5 raw) · 2 Presidio (4 raw) · 3 engine_base + LiteLLM path probe · 4 LiteLLM presidio.py · 5 LiteLLM commits API · 6 NeMo + Guardrails AI · 7 Portkey listing + pii.ts · 8 Bifrost listing · 9 tavily EN search · 10 metadata ×14 · 11 trees PrivAiTe+piighost · 12 PrivAiTe ×6 · 13–14 piighost branch + ×4 · 15 gaze README · 16 cloakpipe README · 17 NeMo Anonymizer README · 18 tavily RU search · 19 metadata (rate-limited) · 20 gh metadata ×5 · 21 gh code search ×4 · 22 Kibana dir + deanonymize_message.ts · 23 Kibana ×3 · 24 Kibana parts + commits · 25 survey ×11 (partly rate-limited) · 26 pasteguard tree · 27 pasteguard ×5 · 28 pasteguard ×2 + README · 29 DontFeedTheAI + ghost · 30 DontFeedTheAI anonymizer + pii-mask tree · 31 pii-mask core/api · 32 DontFeedTheAI vault/surrogates.
