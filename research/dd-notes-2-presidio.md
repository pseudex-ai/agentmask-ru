# DD Notes 2 — Microsoft Presidio: Reversible PII De-identification (source-grounded)

Scope: Presidio CORE only (analyzer, anonymizer, structured). Reverse-engineered from
the actual `.py` files in `github.com/microsoft/presidio` (commit pin
`83ab7eb85609c49d9b0b17c44b5c025575966876`, the `main` branch state, June 2026).
Out of scope by instruction: Skyflow, LangChain wrapper, LiteLLM/Portkey/MCP guardrails,
FPE libs, Russian NER.

Evidence grades: **[A]** = read it in source · **[B]** = docs only · **[C]** = asserted ·
**[D]** = inference from source.

---

## 0. Repo layout (the packages that matter)

`presidio-analyzer/` (detection), `presidio-anonymizer/` (de-identify + the reversible
path), `presidio-structured/` (PII inside tabular/JSON), `presidio-image-redactor/`
(images, irrelevant here), `presidio-cli/`. Each is a **separately installable PyPI
package**; analyzer and anonymizer have no hard dependency on each other — they
communicate via the plain `RecognizerResult` list. **[A]**

This loose coupling is the single most reusable property for a gateway: you can run
detection and de-identification independently, feed your own detector results into the
anonymizer, or feed analyzer output into a totally custom redaction layer.

---

## 1. Analyzer architecture

### 1.1 AnalyzerEngine.analyze() pipeline
`presidio-analyzer/presidio_analyzer/analyzer_engine.py` **[A]**

`analyze(text, language, entities=None, score_threshold, ad_hoc_recognizers,
allow_list, context, nlp_artifacts=None, ...)` orchestration:
1. `nlp_artifacts = self.nlp_engine.process_text(text, language)` — runs the NLP model
   **once** (tokens, lemmas, and the model's own NER spans) and passes it to every
   recognizer so NER isn't recomputed per recognizer.
2. `recognizers = self.registry.get_recognizers(language, entities, all_fields,
   ad_hoc_recognizers)`.
3. For each recognizer: `current_results = recognizer.analyze(text=text,
   entities=entities, nlp_artifacts=nlp_artifacts)`, then tag each result with the
   recognizer id/name into `recognition_metadata`.
4. `results = self._enhance_using_context(text, results, nlp_artifacts, recognizers,
   context)` — context-aware score boosting (e.g. the word "card" near a number).
5. `results = EntityRecognizer.remove_duplicates(results)`.
6. `results = self.__remove_low_scores(results, score_threshold)`.
7. allow-list filtering; strip `analysis_explanation` unless `return_decision_process`.

Return type: `List[RecognizerResult]`. **[A]**

### 1.2 RecognizerResult — the detection data structure
`presidio-analyzer/presidio_analyzer/recognizer_result.py` **[A]**

Fields:
- `entity_type: str`
- `start: int`, `end: int`  (char offsets into the original text)
- `score: float`
- `analysis_explanation: AnalysisExplanation` (optional; debug provenance)
- `recognition_metadata: Dict` (optional; recognizer id + name)

> **CRITICAL: `RecognizerResult` does NOT carry the matched substring.** Only offsets.
> The actual PII text is recovered later by slicing `text[start:end]`. This matters for
> a gateway: detection output alone is not enough to build a token map — you must keep
> the source text. **[A]**

Methods: `intersects(other)->int` (overlap char count), `contains`/`contained_in`,
`equal_indices`, `has_conflict`, `__gt__` (sort by position), `to_dict`/`from_json`. **[A]**

### 1.3 EntityRecognizer base + dedupe
`presidio-analyzer/presidio_analyzer/entity_recognizer.py` **[A]**

- Constants `MIN_SCORE = 0`, `MAX_SCORE = 1.0`.
- Abstract `analyze(text, entities, nlp_artifacts) -> List[RecognizerResult]`.
- `remove_duplicates(results)` (static): sorts by
  `key=lambda x: (-x.score, x.start, -(x.end - x.start))` (highest score, then earliest,
  then longest span), skips zero-score, and drops any result **contained within** an
  already-kept result **of the same entity_type**. This is a *cross-recognizer* dedupe,
  distinct from the anonymizer's own conflict resolution (§2.4). **[A]**

### 1.4 PatternRecognizer (predefined regex recognizers)
`presidio-analyzer/presidio_analyzer/pattern_recognizer.py` + `pattern.py` **[A]**

- `Pattern` is a tiny class: `name`, `regex`, `score (0..1)`, plus lazily compiled regex.
  (`pattern.py` imports `regex as re` — the third-party `regex` module, not stdlib.) **[A]**
- A `PatternRecognizer` holds `patterns: List[Pattern]`, an optional `deny_list`
  (converted to a word-boundary regex via `_deny_list_to_regex`), `context` words, and
  `supported_entity`.
- `analyze()` -> `__analyze_patterns()`: compiles each regex (with flags), iterates
  matches, emits a `RecognizerResult` per match using the pattern's base `score`, with an
  `AnalysisExplanation`.
- Two override hooks: `validate_result()` (promotes a verified match to MAX_SCORE — used
  e.g. by credit-card checksum logic) and `invalidate_result()` (demotes to MIN_SCORE).
  Only results with `score > MIN_SCORE` are kept. **[A]**

Predefined recognizers live in
`presidio-analyzer/presidio_analyzer/predefined_recognizers/` (CreditCard, Email, Phone,
IBAN, IP, US SSN, crypto, etc.) and NER ones under `.../predefined_recognizers/ner/`. **[A]**

### 1.5 NlpEngine abstraction — spaCy / Transformers / Stanza (NOT GLiNER)
`presidio-analyzer/presidio_analyzer/nlp_engine/` **[A]**

`nlp_engine.py` defines the abstract `NlpEngine`: `load`, `is_loaded`, `process_text`,
`process_batch`, `is_stopword`, `is_punct`, `get_supported_entities`,
`get_supported_languages`. **[A]**

Concrete engines present in that directory:
`spacy_nlp_engine.py`, `slim_spacy_nlp_engine.py`, `stanza_nlp_engine.py`,
`transformers_nlp_engine.py`. **[A]**

> **CORRECTION to the brief's premise: there is NO `GLiNER` NlpEngine.** GLiNER is
> implemented as an **`EntityRecognizer`**, not an NlpEngine:
> `predefined_recognizers/ner/gliner_recognizer.py` -> class `GLiNERRecognizer`. **[A]**
> The "slim" config (`conf/slim.yaml`) pairs a tokenize-only slim spaCy engine with
> `GLiNERRecognizer` for the actual entity extraction — i.e. the NlpEngine does
> tokenization/lemmatization and a recognizer does NER. The same pattern holds for
> HuggingFace NER (`HuggingFaceNerRecognizer`) and medical NER. Dependency is optional:
> `pyproject.toml` has a `gliner = ["transformers", "gliner (>=0.2.26,<1.0.0)", ...]`
> extra. **[A]**
> Practical takeaway: NER backends are swappable two ways — as an `NlpEngine`
> (spaCy/Stanza/Transformers) OR as a self-contained recognizer (GLiNER/HF/LM). For a
> gateway, GLiNER-as-recognizer is the lighter integration. **[D]**

`NlpArtifacts` (`nlp_artifacts.py`) carries `tokens`, `lemmas`, `entities`, `scores`,
`nlp_engine`, etc., produced once per `process_text` call. **[A]**

### 1.6 RecognizerRegistry
`presidio-analyzer/presidio_analyzer/recognizer_registry/` **[A]** — holds the recognizer
instances; `get_recognizers()` filters by language + requested entity types and appends
any `ad_hoc_recognizers` passed at call time. Recognizers are loaded lazily.

---

## 2. Anonymizer operators

### 2.1 AnonymizerEngine.anonymize()
`presidio-anonymizer/presidio_anonymizer/anonymizer_engine.py` **[A]**

Signature:
```python
anonymize(text, analyzer_results: List[RecognizerResult],
          operators: Optional[Dict[str, OperatorConfig]] = None,
          conflict_resolution = MERGE_SIMILAR_OR_CONTAINED,
          merge_entities_with_spaces = True) -> EngineResult
```
Flow:
1. `_copy_recognizer_results` — copies **only** `start/end/entity_type/score`
   (drops metadata/explanation). **[A]**
2. sort by `(start, end)`.
3. `_remove_conflicts_and_get_text_manipulation_data(...)` (§2.4).
4. optional `_merge_entities_with_spaces_between` (joins adjacent same-type entities
   separated only by spaces).
5. `__check_or_add_default_operator` — injects `{"DEFAULT": OperatorConfig("replace")}`
   if no `DEFAULT` given. **`DEFAULT = "replace"`.** **[A]**
6. delegates to `EngineBase._operate(..., OperatorType.Anonymize)`.

### 2.2 OperatorConfig — the per-entity config data structure
`presidio-anonymizer/presidio_anonymizer/entities/engine/operator_config.py` **[A]**
```python
OperatorConfig(operator_name: str, params: Dict = None)
# e.g. OperatorConfig("replace", {"new_value": "<NAME>"})
#      OperatorConfig("encrypt", {"key": "WmZq4t7w!z%C&F)J"})
#      OperatorConfig("mask", {"masking_char":"*","chars_to_mask":4,"from_end":True})
```
Keyed in the `operators` dict by **entity_type** (e.g. `"PHONE_NUMBER"`), with `"DEFAULT"`
as fallback. `from_json` reads `{"type": <name>, ...rest as params}`. **[A]**

### 2.3 EngineBase._operate — the shared anonymize/deanonymize loop
`presidio-anonymizer/presidio_anonymizer/core/engine_base.py` **[A]**

```python
text_replace_builder = TextReplaceBuilder(original_text=text)
sorted_pii_entities = sorted(pii_entities, reverse=True)   # end -> start
for entity in sorted_pii_entities:
    text_to_operate_on = builder.get_text_in_position(entity.start, entity.end)
    operator_metadata = __get_entity_operator_metadata(entity.entity_type, operators)
    changed_text = __operate_on_text(...)   # picks operator from factory, validate(), operate()
    index_from_end = builder.replace_text_get_insertion_index(changed_text, start, end)
    engine_result.add_item(OperatorResult(0, index_from_end, entity.entity_type,
                                          changed_text, operator_metadata.operator_name))
engine_result.set_text(builder.output_text)
engine_result.normalize_item_indexes()
```
Note: it processes **end→start** so earlier offsets stay valid as the string mutates;
indexes are stored as offset-from-end then normalized at the end. Operators are resolved
via `OperatorsFactory.create_operator_class(name, type)`. Each operator gets
`params` **plus an injected `params["entity_type"]`**. **[A]**

`__operate_on_text` does `operator.validate(params)` then `operator.operate(text, params)`.
**Per-entity validation runs on every call** (perf note for high-throughput gateways). **[D]**

### 2.4 Conflict / overlap resolution (anonymizer side)
`_remove_conflicts_and_get_text_manipulation_data` **[A]**:
- Pass 1: **merge same-entity-type overlaps** — if two results of the same type
  intersect, widen one to `min(start)..max(end)` with `max(score)` and drop the other.
- Pass 2: drop a result if `has_conflict` with any kept result (same indices + lower
  score, OR contained within another).
- If `conflict_resolution == REMOVE_INTERSECTIONS`: additionally trims overlapping spans
  of *different* types by adjusting start/end so they no longer intersect (higher score
  wins the contested chars).
`ConflictResolutionStrategy` enum: `MERGE_SIMILAR_OR_CONTAINED` (default) vs
`REMOVE_INTERSECTIONS`. **[A]**

### 2.5 The full operator set (each = a subclass of `Operator`)
Base: `operators/operator.py` — abstract `operate(text, params)->str`, `validate`,
`operator_name`, `operator_type`. `OperatorType` enum = `{Anonymize=1, Deanonymize=2}`. **[A]**

Registered in `operators_factory.py`:
`ANONYMIZERS = [Custom, Encrypt, Hash, Keep, Mask, Redact, Replace]` (+ optional
`AHDSSurrogate` if Azure Health Data Services deps present);
`DEANONYMIZERS = [Decrypt, DeanonymizeKeep]`. **[A]**

| Operator | File | Behavior | Reversible? | Consistent (same in→same out)? |
|---|---|---|---|---|
| `replace` | `replace.py` | returns `new_value`, else `f"<{entity_type}>"` | No | **No** (all instances get the *same constant* label, so they collide rather than stay distinct — see §5) |
| `redact` | `redact.py` | returns `""` (deletes the span) | No | n/a |
| `mask`   | `mask.py` | replace N chars from start/end with `masking_char` | No | Yes-ish (deterministic on identical input) |
| `hash`   | `hash.py` | sha256/sha512 of `text + salt` | No (one-way) | **Only if a fixed `salt` is supplied**; default is `os.urandom(32)` per entity → non-deterministic |
| `encrypt`| `encrypt.py` | AES-CBC, returns base64(iv‖ciphertext) | **Yes (via decrypt)** | **No** — random IV per call (see §3) |
| `keep`   | `keep.py` | returns text unchanged (tracked but not altered) | n/a | n/a |
| `custom` | `custom.py` | returns `params["lambda"](text)` (must return str) | Depends on the lambda | **This is the hook used to build consistent/reversible mappings** (§3.4, §5) |

`Hash` detail **[A]**: if `salt` provided it must be ≥16 bytes; if omitted, a fresh random
32-byte salt is generated per entity (so default hashing is NOT reproducible/consistent).

`Custom.validate()` deliberately does **not** invoke the lambda (avoids side effects in
stateful lambdas that accumulate a token map — explicit comment references issue #2024).
This confirms the maintainers expect `custom` to be used for stateful pseudonymization. **[A]**

### 2.6 OperatorResult — what was changed
`presidio-anonymizer/presidio_anonymizer/entities/engine/result/operator_result.py` **[A]**
Fields: `start: int`, `end: int`, `entity_type: str`, `text: str` (the *resulting*
post-operation text, e.g. the ciphertext), `operator: str` (operator name applied).
`to_dict`/`from_json`/`__eq__`. Extends `PIIEntity`.

`EngineResult` (`.../result/engine_result.py`) **[A]**: `{text: str, items: List[OperatorResult]}`,
with `add_item`, `set_text`, `normalize_item_indexes` (`start = len(text) - end;
end = start + len(item.text)`), `to_json`.

> **Reversal state lives in `EngineResult.items` (the `List[OperatorResult]`).** For the
> built-in reversible path, that list — specifically each item's `start/end/operator/
> entity_type` and the post-anonymization ciphertext sitting in `EngineResult.text` — is
> exactly what you must persist to call `deanonymize` later. **[A]/[D]**

---

## 3. THE REVERSIBLE PATH (most important)

### 3.1 encrypt / decrypt operators
`operators/encrypt.py`, `operators/decrypt.py` **[A]**

- `Encrypt.operate`: `key = params["key"]` (str→utf8 bytes), returns
  `AESCipher.encrypt(key, text)`. Validates key is 128/192/256-bit. `operator_type =
  Anonymize`.
- `Decrypt.operate`: same key handling, returns `AESCipher.decrypt(key, text)`.
  `operator_type = Deanonymize`. `Decrypt.validate` just calls `Encrypt().validate`.
- The **key is a parameter passed in `OperatorConfig` at call time** — Presidio stores no
  key. The consumer owns key management entirely. **[A]**

### 3.2 AESCipher — the actual crypto
`operators/aes_cipher.py` **[A]**
```python
# encrypt: AES-CBC, PKCS7 pad, random 16-byte IV, output = urlsafe_b64(iv + ciphertext)
iv = os.urandom(16)
cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
return base64.urlsafe_b64encode(iv + ct).decode()
# decrypt: b64decode, iv = first 16 bytes, AES-CBC decrypt, PKCS7 unpad
```
Built on the `cryptography` library (`cryptography.hazmat`). `is_valid_key_size` checks
`len(key)*8 in algorithms.AES.key_sizes`. **[A]**

> **Decisive fact for tokenization design: AES-CBC with a FRESH RANDOM IV means the same
> plaintext encrypts to DIFFERENT ciphertext every call.** Therefore `encrypt` is
> reversible but **NOT consistent / NOT deterministic**: it cannot give you "same real
> value → same placeholder," cannot be used as a stable token, and is not suitable as a
> join key. The ciphertext is also long/non-human-readable (base64 of IV+blocks) — a poor
> "placeholder" to show an LLM. **[A]/[D]**
> If you need deterministic reversible tokens you must build it yourself (deterministic
> IV/AES-SIV/FPE, or a vault mapping) — Presidio core does not provide it.

### 3.3 DeanonymizeEngine
`presidio-anonymizer/presidio_anonymizer/deanonymize_engine.py` **[A]**
```python
deanonymize(text: str,
            entities: List[OperatorResult],
            operators: Dict[str, OperatorConfig]) -> EngineResult:
    return self._operate(text, entities, operators, OperatorType.Deanonymize)
```
It reuses the **same `EngineBase._operate` loop** as anonymize, just with the
Deanonymize operator set. So to reverse you must supply: (a) the anonymized `text`,
(b) the `List[OperatorResult]` (the offsets/entity_types from the anonymize step), and
(c) `{entity_type: OperatorConfig("decrypt", {"key": ...})}`. **[A]**

> **There is no implicit linkage between anonymize and deanonymize.** The consumer is
> responsible for storing `EngineResult.items` and the key, and handing them back. The
> built-in reversible flow is essentially: `encrypt` on the way in → keep
> `OperatorResult` spans + key → `decrypt` on the way out. **[A]/[D]**

### 3.4 Entity-mapping CONSISTENCY — NOT in core; built by the consumer via `custom`
The canonical Microsoft pattern (docs sample `docs/samples/python/pseudonymization.ipynb`) **[A/B]**:
- `InstanceCounterAnonymizer` — a **custom `Operator`** the user registers via
  `engine.add_anonymizer(...)`. It holds a shared dict and on each call:
  `if text in entity_mapping[entity_type]: return existing_placeholder; else assign
  <ENTITY_TYPE_N> with an incrementing counter`.
- **Mapping dict shape:** `Dict[str, Dict[str, str]]` =
  `{ entity_type: { original_value: placeholder } }`, e.g.
  `{'PERSON': {'Peter': '<PERSON_1>', 'Nicole': '<PERSON_0>'},
    'LOCATION': {'London': '<LOCATION_1>'}}`.
- `InstanceCounterDeanonymizer` — a custom `Deanonymize` operator doing reverse lookup
  `_find_key_by_value(entity_mapping[entity_type], placeholder)`.
- The notebook explicitly warns the mapping logic is **not thread-safe**. **[B]**

This is the real "same value → same placeholder, reversible later" mechanism — and it is
**application code the consumer writes**, using `custom` + their own dict, not a built-in
Presidio feature. The reversal state to persist here is the entity_mapping dict itself
(plus the `OperatorResult` spans for re-insertion). **[A]/[D]**

---

## 4. presidio-structured (PII inside structured / JSON — relevant to tool-call args)

`presidio-structured/presidio_structured/` **[A]**

### 4.1 Two-phase model
1. **AnalysisBuilder** (`analysis_builder.py`) → produces a `StructuredAnalysis`, whose
   core is `entity_mapping: Dict[str, str]` = **{column-or-json-key → entity_type}**
   (NOT char offsets — for structured data the *field* is the unit, not a span). **[A]**
   - `JsonAnalysisBuilder`: uses `BatchAnalyzerEngine.analyze_dict()`, recurses nested
     dicts in `_generate_analysis_from_results_json` (checks `isinstance(result.value,
     dict)`), building **dot-notation keys** like `"user.address.street"`. Takes the
     first recognizer result per key: `{key: result.entity_type}`. **[A]**
   - `PandasAnalysisBuilder`: per-column; entity-selection strategies
     `most_common` (default), `highest_confidence`, `mixed`; uses
     `BatchAnalyzerEngine.analyze_iterator()`. **[A]**
2. **StructuredEngine** (`structured_engine.py`) `.anonymize(data, structured_analysis,
   operators)` → delegates to a `DataProcessor`. Same `operators: Dict[entity_type,
   OperatorConfig]` shape as the text anonymizer, same `DEFAULT="replace"` fallback. **[A]**

### 4.2 DataProcessors
`data/data_processors.py` **[A]**
- `DataProcessorBase._generate_operator_mapping()` builds **callables once** per
  entity_type from `OperatorsFactory` (so the same operator instance is reused across all
  values of that type — relevant if you want the *same* stateful lambda to see every value
  in the structure, which is exactly what enables structure-wide consistency).
- `PandasDataProcessor`: applies operator to each cell of the mapped column.
- `JsonDataProcessor`: splits dot-keys, `_get_nested_value` traverses dicts AND lists
  (applies to **each element** when a list is encountered mid-path), `_operate_on_text`
  runs the operator callable, `_set_nested_value` writes back. **[A]**

### 4.3 Fit for tool-call arguments **[D]**
Tool-call arguments are JSON. `JsonAnalysisBuilder` + `JsonDataProcessor` can detect and
de-identify PII inside a parsed dict, including nested objects and arrays — a direct fit
for redacting/tokenizing values inside a tool-call `arguments` object **once you have
parsed it to a dict**. Caveats: (a) it keys on **field name → single entity_type** per
key, so a free-text field containing mixed PII gets one operator for the whole value (it
does not do span-level multi-entity within a string value the way the text engine does);
(b) structured does not return offsets, so reversal again relies on a stateful/custom
operator carrying the mapping; (c) it operates on a Python dict/DataFrame — JSON
parse/serialize, schema validation, and re-injection into the live tool call are the
consumer's job.

---

## 5. Honest limitations for a tool-call tokenization gateway

1. **No tool-call / function-call / MCP interception anywhere in Presidio.** Code search
   for `tool`/`tool_call`/`function_call` in `presidio-anonymizer` = **0 hits**. **[A]**
   Presidio is text/tabular PII detection + de-identification primitives. All
   LLM/tool-call wiring (intercepting requests, parsing tool args, swapping placeholders
   back into responses, streaming) is **entirely the consumer's responsibility**.
   Confirmed: Presidio itself does NOT do tool-call interception.

2. **Base `replace` does NOT keep cross-instance entity consistency.** `replace.py`
   returns a single constant (`new_value` or `<ENTITY_TYPE>`) for *every* match. Two
   different people both become `<PERSON>` (collision, info loss) and it is **not
   reversible** — there's no per-instance token, no back-map. To get distinct, stable,
   reversible placeholders you must build a stateful operator (the
   `InstanceCounterAnonymizer` / `custom`-lambda pattern, §3.4). **[A]**

3. **`encrypt` is reversible but not deterministic** (random IV, §3.2). Same input →
   different ciphertext each call. So it cannot be a stable token / join key / cache key,
   and its output is long and unreadable. Good for "store ciphertext, decrypt on return";
   bad as a human/LLM-facing placeholder or as a consistency mechanism. **[A]/[D]**

4. **No persistence / vault.** Presidio holds **no key store and no token store**. The
   AES key is passed per call; the reversal state (`EngineResult.items` for encrypt, or
   the `{entity_type:{value:placeholder}}` dict for the counter pattern) must be persisted
   by the consumer, keyed to the conversation/session. The counter-pattern dict is
   explicitly flagged non-thread-safe in the sample. **[A]/[B]**

5. **Detection is the weak link, not de-identification.** Recall depends entirely on
   recognizers/NER model chosen; regex recognizers are brittle; NER misses novel formats.
   For a gateway, false negatives = PII leaks to the model. (Out-of-scope NER engine
   quality covered by another agent.) **[D]**

6. **What the consumer must build on top of Presidio for a reversible tokenization
   gateway:** (a) request/response interceptor + tool-arg JSON parser; (b) a stateful,
   thread-safe token map `{entity_type:{original→token}}` + reverse map, scoped per
   session, persisted; (c) a custom `Operator` (anonymize) + custom `Deanonymize` operator
   wired via `add_anonymizer`/`add_deanonymizer`, OR post-process `EngineResult` yourself;
   (d) re-injection of original values into the model's tool-call response before
   execution; (e) key/secret management if using `encrypt`. Presidio gives you steps of
   detection + the operator framework + offset bookkeeping; the gateway loop and the
   consistency/reversal store are yours. **[D]**

---

## 6. Key data-structure cheat-sheet (verbatim field shapes)

```python
# Detection output (analyzer)
RecognizerResult:
    entity_type: str
    start: int; end: int          # offsets only — NO matched text stored
    score: float
    analysis_explanation: AnalysisExplanation | None
    recognition_metadata: Dict | None

# Per-entity de-identify config (anonymizer input)
OperatorConfig(operator_name: str, params: Dict)   # keyed by entity_type, plus "DEFAULT"

# De-identify output / reversal state (anonymizer + deanonymizer)
EngineResult:
    text: str                       # the anonymized (or deanonymized) full text
    items: List[OperatorResult]
OperatorResult:
    start: int; end: int            # span in the NEW text
    entity_type: str
    text: str                       # post-operation value (e.g. ciphertext / placeholder)
    operator: str                   # which operator ran

# Consumer-built consistency map (pseudonymization sample — NOT in core)
entity_mapping: Dict[str, Dict[str, str]]
    # { entity_type: { original_value: placeholder } }

# Structured analysis (presidio-structured)
StructuredAnalysis:
    entity_mapping: Dict[str, str]  # { column_or_dotted_json_key: entity_type }
```

---

## 7. File path index (all read in source unless noted)
- `presidio-analyzer/presidio_analyzer/analyzer_engine.py`
- `presidio-analyzer/presidio_analyzer/recognizer_result.py`
- `presidio-analyzer/presidio_analyzer/entity_recognizer.py`
- `presidio-analyzer/presidio_analyzer/pattern_recognizer.py`, `pattern.py`
- `presidio-analyzer/presidio_analyzer/nlp_engine/nlp_engine.py` (+ spacy/slim_spacy/stanza/transformers engines)
- `presidio-analyzer/presidio_analyzer/predefined_recognizers/ner/gliner_recognizer.py` (GLiNER = recognizer)
- `presidio-anonymizer/presidio_anonymizer/anonymizer_engine.py`
- `presidio-anonymizer/presidio_anonymizer/deanonymize_engine.py`
- `presidio-anonymizer/presidio_anonymizer/core/engine_base.py`
- `presidio-anonymizer/presidio_anonymizer/operators/{operator,operators_factory,encrypt,decrypt,aes_cipher,replace,redact,mask,hash,keep,deanonymize_keep,custom}.py`
- `presidio-anonymizer/presidio_anonymizer/entities/engine/operator_config.py`
- `presidio-anonymizer/presidio_anonymizer/entities/engine/recognizer_result.py`
- `presidio-anonymizer/presidio_anonymizer/entities/engine/result/{operator_result,engine_result}.py`
- `presidio-structured/presidio_structured/{structured_engine,analysis_builder}.py`
- `presidio-structured/presidio_structured/data/data_processors.py`
- `docs/samples/python/pseudonymization.ipynb` (consumer consistency pattern) — [B]
- `docs/samples/python/gliner.md`, `presidio-analyzer/presidio_analyzer/conf/slim.yaml` — [B/A]
