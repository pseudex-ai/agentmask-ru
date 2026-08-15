# DD4-B — Detecting PII in SEMI-STRUCTURED text (JSON / labeled forms / key-value / tables)

Scope: structured & semi-structured PII detection only. The problem: free-text NER
stumbles when a value sits inside structure (a surname inside `{"имя":"Анна Смирнова"}`,
or after a label `ФИО: Анна Смирнова`) — the NER context is destroyed by braces/labels,
so the value is missed. We want PROVEN ways to (a) detect the structure, (b) analyze each
value, (c) use the KEY/LABEL as a signal, (d) remap spans back to original offsets.

Out of scope (other agents): phone/noise normalization; quasi-identifiers.

Evidence grades: **[A]** read it in source · **[B]** docs only · **[C]** asserted by vendor ·
**[D]** inference from source.

Source pin: `github.com/microsoft/presidio` `main` (June 2026). Raw files fetched directly.

---

## 0. TL;DR — the proven approach

1. **Microsoft Presidio already ships the exact machinery**: `BatchAnalyzerEngine.analyze_dict`
   analyzes each value independently AND injects the **key name as `context`** so the analyzer's
   context-aware enhancer can boost/qualify the value's score. `presidio-structured` wraps this to
   produce a **key→entity_type mapping** (`StructuredAnalysis.entity_mapping`). All **MIT-licensed**. **[A]**
2. **The established mixed-text pattern** (free text with embedded JSON/kv): detect the structure,
   parse it (`json.loads` / kv-split), analyze each value WITH the key as context, then **remap the
   value-local offsets back to the absolute offsets in the original string** by adding the byte/char
   offset where that value started. Presidio's own `structured` package does NOT do this remap — it
   replaces whole values per key (offset-agnostic). The remap is YOUR glue. **[A]/[D]**
3. **Key-name → entity-type** is a first-class production technique. Presidio supports it two ways:
   (a) implicitly, key-as-context boosting; (b) explicitly, a hand-authored `entity_mapping` dict
   (`{"имя":"PERSON","телефон":"PHONE_NUMBER",...}`) fed straight to `StructuredEngine`/anonymizer,
   bypassing detection entirely. Google DLP (`recordTransformations`) and AWS Macie do the same:
   if a column is named `SSN`, you don't inspect — you transform the whole field. **[A]/[B]/[C]**

---

## 1. Microsoft Presidio — `BatchAnalyzerEngine` (the real engine)

File: `presidio-analyzer/presidio_analyzer/batch_analyzer_engine.py` **[A]**

### 1.1 `analyze_dict` — verbatim core (the key-as-context line is the whole story)

```python
def analyze_dict(
    self,
    input_dict: Dict[str, Union[Any, Iterable[Any]]],
    language: str,
    keys_to_skip: Optional[List[str]] = None,
    batch_size: int = 1,
    n_process: int = 1,
    **kwargs,
) -> Iterator[DictAnalyzerResult]:
    context = []
    if "context" in kwargs:
        context = kwargs["context"]
        del kwargs["context"]
    if not keys_to_skip:
        keys_to_skip = []
    for key, value in input_dict.items():
        if not value or key in keys_to_skip:
            yield DictAnalyzerResult(key=key, value=value, recognizer_results=[])
            continue
        # Add the key as an additional context
        specific_context = context[:]
        specific_context.append(key)
        if type(value) in (str, int, bool, float):
            results = self.analyzer_engine.analyze(
                text=str(value), language=language, context=[key], **kwargs
            )
        elif isinstance(value, dict):
            new_keys_to_skip = self._get_nested_keys_to_skip(key, keys_to_skip)
            results = self.analyze_dict(
                input_dict=value, language=language,
                context=specific_context, keys_to_skip=new_keys_to_skip, **kwargs,
            )
        elif isinstance(value, Iterable):
            results = self.analyze_iterator(
                texts=value, language=language, context=specific_context,
                n_process=n_process, batch_size=batch_size, **kwargs,
            )
        else:
            raise ValueError(f"type {type(value)} is unsupported.")
        yield DictAnalyzerResult(key=key, value=value, recognizer_results=results)
```

CLAIMS:
- **Each value is analyzed independently** via `analyzer_engine.analyze(text=str(value), ...)`. **[A]**
- **The KEY NAME is passed as context**: scalar values get `context=[key]`; nested values get the
  accumulated path `specific_context = parent_context + [key]`. So `{"телефон":"..."}` calls
  `analyze(text="...", context=["телефон"])`. **[A]** — *this is the answer to "can the key be used
  as a signal?": YES, it is, by design, in the core library.*
- Recurses into nested dicts (path-context accumulates) and lists (`analyze_iterator`). **[A]**
- Returns `Iterator[DictAnalyzerResult(key, value, recognizer_results)]`. The `recognizer_results`
  carry **value-local char offsets** (start/end into `str(value)`), NOT offsets into any outer text. **[A]**
- `analyze_iterator(texts, language, batch_size, n_process, ...) -> List[List[RecognizerResult]]`
  batches values through the NLP engine once, then analyzes each with its NLP artifacts. **[A]**

### 1.2 How `context` actually helps — `LemmaContextAwareEnhancer`

File: `presidio-analyzer/presidio_analyzer/context_aware_enhancers/lemma_context_aware_enhancer.py` **[A]**

- The enhancer combines the **supplied `context` list** (here: the key name) with words surrounding
  the match, then matches them against each recognizer's own `context` keyword list
  (`_find_supportive_word_in_context(surrounding_words, recognizer.context, ...)`). **[A]**
- On a hit it boosts: `result.score += context_similarity_factor` (default **0.35**), floored to
  `min_score_with_context_similarity` (default **0.4**), capped at `MAX_SCORE`. **[A]**
- CONSEQUENCE for us: a built-in recognizer whose `context=["phone","telephone","mobile"]` is NOT
  triggered by the Russian key `"телефон"` unless that recognizer's context list contains the RU word.
  **The key-as-context mechanism only fires if the recognizer's `context` keywords are localized to RU.**
  This is the gap to close for RU keys: add `context=["телефон","тел","моб"]` etc. to your recognizers,
  OR use explicit key→entity mapping (§3). **[A]/[D]**

### 1.3 `BatchAnonymizerEngine` — structure-preserving write-back

File: `presidio-anonymizer/presidio_anonymizer/batch_anonymizer_engine.py` **[A]**

`anonymize_dict(analyzer_results)` walks the `DictAnalyzerResult` stream and rebuilds the dict,
anonymizing each string value via the normal `anonymizer_engine.anonymize(text=value, analyzer_results=...)`
and recursing on nested dicts/lists. Keys are preserved verbatim. So within a single value the
anonymizer DOES splice by offset, but the surrounding structure is reconstructed key-by-key,
not by global offsets. **[A]**

---

## 2. `presidio-structured` — the column/key-mapping layer

Files: `presidio-structured/presidio_structured/analysis_builder.py`,
`.../structured_engine.py`, `.../data/data_processors.py`. **MIT.** **[A]**

### 2.1 `JsonAnalysisBuilder.generate_analysis` — verbatim

```python
def generate_analysis(self, data: Dict, language: str = "en") -> StructuredAnalysis:
    analyzer_results = self.batch_analyzer.analyze_dict(
        input_dict=data, language=language,
        n_process=self.n_process, batch_size=self.batch_size)
    key_recognizer_result_map = self._generate_analysis_from_results_json(analyzer_results)
    key_entity_map = {
        key: result.entity_type for key, result in key_recognizer_result_map.items()
    }
    return StructuredAnalysis(entity_mapping=key_entity_map)
```

`_generate_analysis_from_results_json` flattens nested keys with dot-notation
(`"users.name"`), and for each key keeps the **first** `RecognizerResult` (`next(iter(...))`).
So JSON analysis collapses to ONE entity type per key path. **[A]**

NUANCE worth flagging: `JsonAnalysisBuilder` itself does not add extra context — but it doesn't
have to, because the `analyze_dict` it calls already injects the key as context (§1.1). So the
key-as-signal IS in effect through the JSON path. The earlier "JSON does not use key as context"
claim seen in secondary summaries is **wrong at the `analyze_dict` level**. **[A]**

### 2.2 `PandasAnalysisBuilder` — per-column aggregation strategies **[A]**

For tabular data each column's cell-values are analyzed via `analyze_iterator`, then aggregated to
ONE entity type per column with a `selection_strategy`:
- `"most_common"` (default): `Counter` over entity types; score = proportion of cells that hit.
- `"highest_confidence"`: pick the entity with the max score.
- `"mixed"` (`mixed_strategy_threshold`, e.g. 0.75): highest-confidence if above threshold else most-common.

```python
def _select_most_common_entity(self, flat_results):
    type_counter = Counter(res.entity_type for _, res in flat_results)
    most_common_type, most_common_count = type_counter.most_common(1)[0]
    score = most_common_count / len(flat_results)
    return RecognizerResult(entity_type=most_common_type, start=0, end=1, score=score)
```

Note `start=0, end=1` — column-level results are **offset-meaningless**; the structured engine
operates per-column, not by offset. **[A]**

### 2.3 `StructuredEngine.anonymize` / data processors — OFFSET-AGNOSTIC (the caveat)

`StructuredEngine.anonymize(data, structured_analysis, operators)` delegates to
`data_processor.operate(...)`. Write-back is **whole-value, per-key**: **[A]**
- Pandas: `data.at[row.Index, key] = operated_text`
- JSON: `self._set_nested_value(data, keys, operated_text)`

i.e. the operator output replaces the ENTIRE value of a mapped key/column. There is **no
character-offset splicing** at the structured layer and **no concept of an offset into a larger
surrounding free-text document**. This is the central caveat for our use case (§4). **[A]**

### 2.4 `StructuredAnalysis.entity_mapping` — the explicit map (production technique)

`StructuredAnalysis(entity_mapping={"users.name":"PERSON","users.email":"EMAIL_ADDRESS"})` can be
**hand-authored and passed directly** to `StructuredEngine.anonymize` — detection is skipped
entirely; every value under that key is treated as that entity. This is the canonical
"column-name → entity-type dictionary" pattern, supported first-class. **[A]/[B]**

---

## 3. Key-name → entity-type mapping as a production technique

### 3.1 In Presidio
- **Implicit**: key-as-context boosting (§1.1 + §1.2). Works only if recognizer `context` lists
  contain the localized key words.
- **Explicit**: `StructuredAnalysis.entity_mapping` dict (§2.4) — deterministic, no ML, no false
  negatives for known keys. Best fit for a regex-first detector. **[A]**
- **Recognizer-level**: you can also build a `PatternRecognizer` whose `context=["имя","фио"]`
  raises the score of a name pattern when the RU key is nearby — same enhancer mechanism. **[A]/[D]**

### 3.2 RU key dictionary (to author — no canonical public RU map found in source repos)
A practical RU key→entity dict to drive both explicit mapping and recognizer context:
- PERSON: `имя`, `фио`, `ф.и.о`, `фамилия`, `отчество`, `name`, `client`, `клиент`, `получатель`, `контакт`
- PHONE_NUMBER: `телефон`, `тел`, `моб`, `мобильный`, `phone`, `mobile`, `contact_phone`, `номер`
- EMAIL_ADDRESS: `email`, `e-mail`, `почта`, `эл.почта`, `mail`
- LOCATION/ADDRESS: `адрес`, `address`, `город`, `улица`, `дом`, `кв`, `индекс`, `регион`
- ID (RU): `снилс`, `инн`, `паспорт`, `серия`, `номер_паспорта`, `карта`, `счёт`, `счет`
- DATE: `дата`, `др`, `дата_рождения`, `birthdate`, `dob`

GH search for a published RU-key→entity map returned no authoritative source — treat as **[C]**
(author it yourself; it's a config asset, not code).

---

## 4. The proven pipeline for MIXED free-text-with-embedded-JSON/kv (our case)

Presidio's `structured` package solves *pure* JSON/tabular but NOT "JSON embedded in a sentence with
correct global offsets." The established composition (confirmed by how `analyze_dict` returns
value-local offsets + how the structured engine is offset-agnostic) is: **[A]/[D]**

```
1. DETECT structure inside the free text:
   - JSON object/array substrings: scan for balanced { ... } / [ ... ] and try json.loads on the slice.
   - labeled forms / kv: regex for "LABEL: VALUE" lines (^\s*([\wА-Яа-яё .]+?)\s*[:=]\s*(.+)$).
   Record, per parsed unit, the ABSOLUTE start offset of each VALUE in the original string.

2. ANALYZE each value with the KEY as context:
   - reuse BatchAnalyzerEngine.analyze_dict(parsed_obj, context-from-key)  [for JSON]
   - or call analyzer.analyze(text=value, context=[key]) per kv pair
   - or short-circuit via the explicit key→entity map (§3) when the key is known (no ML cost).

3. REMAP value-local spans to original offsets:
   absolute_start = value_origin_offset + result.start
   absolute_end   = value_origin_offset + result.end
   (works for JSON only if you locate the value's literal position in the RAW json text, because
    json.loads discards source positions — see CAVEAT below.)

4. EMIT spans in the original-string coordinate system; feed to your existing overlap resolver.
```

### 4.1 The OFFSET-REMAP CAVEAT (the load-bearing gotcha)
- `json.loads` throws away source positions. `result.start/end` are offsets into `str(value)`
  (the *decoded* Python string), which is NOT the same as the substring in the raw JSON text
  (escapes `\"`, `\n`, `\uXXXX`, non-ASCII, whitespace all differ). You CANNOT just add the decoded
  offset to the raw offset. **[A]/[D]**
- Robust options:
  1. **Re-find the value literal in the raw slice**: locate the raw value token via a streaming
     parser that preserves positions (`json.JSONDecoder.raw_decode` over slices, or `ijson`,
     or a regex over the matched key) and compute the absolute offset of that raw token; then map
     the recognizer's decoded offsets onto the raw token (re-escape or re-find the matched value
     substring inside the raw token). For most PII values (names, phones, emails) there are no
     escapes, so `raw_value.find(decoded_match)` + token_offset is reliable in practice.
  2. **Replace-by-value, not by-offset**: if you only need to REDACT (not report precise spans),
     skip remapping — anonymize each value and re-serialize, OR do a literal string replace of the
     matched value in the original text (safe when the value is long/unique like a phone/email/INN;
     risky for short common tokens — gate by length/entity type). This mirrors Presidio's own
     whole-value write-back (§2.3) and is the simpler, proven path. **[D]**
- For LABELED/kv text (not JSON) there is NO decode step — the value substring is literal in the
  original, so `value_origin_offset + result.start` is exact and safe. **[A]/[D]**

### 4.2 Why this beats running NER on the raw structured string
The motivating failure (surname missed inside `{"имя":"Анна Смирнова"}`): the model sees
`{"имя":"Анна Смирнова"}` and the punctuation/JSON wrapper degrades NER. Extracting `"Анна Смирнова"`
and analyzing it as clean text — with `context=["имя"]` boosting PERSON — restores NER accuracy and
adds a deterministic key signal. This is precisely what `analyze_dict` automates. **[A]/[D]**

---

## 5. How commercial DLP handles structured vs free text

### 5.1 Google Cloud DLP / Sensitive Data Protection **[B]**
- **`recordTransformations`** = field/column-aware: apply a transformation per field (hash/tokenize
  every value in a column) keyed by field/header name — **no inspection needed** when the field type
  is known (a column named `SSN` → just transform it). This is the field-name-as-signal pattern,
  productized.
- **`infoTypeTransformations`** = free-text: inspect for infoTypes (e.g. an SSN inside a sentence),
  transform only the finding, leave surrounding text intact. Docs explicitly say infoType inspection
  is "more resources and therefore more costly" — use it only when the data type is unknown.
- Guidance verbatim sense: known column → record transform; free-form column ("Additional Details")
  → inspect infoTypes first. (`docs.cloud.google.com/sensitive-data-protection/docs/deidentify-sensitive-data`,
  `.../inspecting-structured-text`)

### 5.2 AWS Macie **[B]**
- For JSON / JSON Lines / Parquet / Avro, findings report the **path to the field/array** containing
  sensitive data (field-path-level, not just byte offset). Nested-element quota: 256 levels for JSON.
- Managed Data Identifiers (built-in detectors) + Custom Data Identifiers (regex) + **Allow lists**
  (text / regex patterns to ignore — the deny-context analogue). So Macie is value-scanning but
  *reports by field path*, i.e. structure-aware output. (`docs.aws.amazon.com/macie/.../findings-locate-sd-schema.html`,
  `.../managed-data-identifiers.html`)

### 5.3 Nightfall **[B]/[C]**
- Detection rules are JSON configs (`.nightfalldlp/config.json`) listing detector objects + logicalOp.
- For structured datastores their own tutorial serializes records with `json.dumps` and scans the
  serialized text, returning byte ranges — and the docs **explicitly acknowledge the limitation**:
  "in use-cases such as this where the data is well-structured, it can be more informative to call out
  which fields are found to contain sensitive data, as opposed to the location of the data."
  i.e. even a commercial vendor's default path is serialize→scan→byte-offset, with field-level
  reporting as the aspiration. Validates that our extract-values + field-mapping approach is the
  *better* design, not the lazy one. (`help.nightfall.ai/firewall-for-ai/tutorials/datastore_protection/elasticsearch`)

---

## 6. Maturity / license summary

| Component | Package | License | Maturity |
|---|---|---|---|
| `BatchAnalyzerEngine.analyze_dict/iterator` | presidio-analyzer | MIT | stable, in main, shipped on PyPI **[A]/[B]** |
| `BatchAnonymizerEngine.anonymize_dict/list` | presidio-anonymizer | MIT | stable **[A]** |
| `StructuredEngine`, `Json/PandasAnalysisBuilder`, `StructuredAnalysis` | presidio-structured | MIT | GA package on PyPI; smaller surface, fewer releases **[A]/[B]** |
| Google DLP record/infoType transforms | GCP (SaaS) | commercial | GA **[B]** |
| AWS Macie structured findings | AWS (SaaS) | commercial | GA **[B]** |
| Nightfall structured | SaaS | commercial | GA; field-level reporting aspirational **[B]/[C]** |

Weight: pulling in `presidio-structured` adds `presidio-analyzer` + spaCy model — heavy. For a
regex-first detector you do NOT need the whole package: the reusable idea is small enough to
reimplement (detect structure → per-value analyze with key-context → remap). You can lift just
`analyze_dict`'s key-as-context idea (~30 lines) without the spaCy dependency, using your existing
regex/Natasha detectors as the per-value analyzer.

---

## 7. Concrete plug-in recommendation for Pseudex's regex-first detector

Current state (`prototype/pseudex/`): `detect.py` (regex phone/email), `detect_all.py` (regex +
checksum IDs + Natasha NER + priority overlap resolver), `ru_pii.py::detect_structured` (RU IDs),
`context.py` (deny-context suppression). There is NO JSON/kv structural pass yet. **[A]**

Recommended addition (a new `detect_kv_json` pass run BEFORE/ALONGSIDE the flat detectors, feeding
the same `Span` list into `_resolve`):

1. **Structure detection** (pure functions, no new heavy deps):
   - JSON: find balanced-brace substrings, attempt `json.JSONDecoder().raw_decode` over each
     candidate to get parse + end position; on success, walk key→value with raw positions.
   - kv/labeled: line regex `^\s*([^\s:=][^:=]*?)\s*[:=]\s*(\S.*)$` (handles `ФИО: ...`, `телефон=...`).
2. **Per-value analysis with key context**:
   - First consult the explicit RU key→entity map (§3.2). If the key is known, type the value
     directly (deterministic; covers the `{"имя":"Анна Смирнова"}` miss with zero ML).
   - Else run your existing detectors on the clean value string (regex IDs/phone/email; Natasha for
     PERSON/LOC), passing the key as a context hint to your boosting/suppression layer.
3. **Offset remap** to the original string:
   - kv/labeled values: literal — `abs_start = value_offset_in_original + local_start` (exact).
   - JSON values: use the RAW value-token offset from `raw_decode` walk, then `raw_token.find(value)`
     for the inner span; or for redaction-only, replace-by-value for long/unique entities (§4.1).
4. **Merge** the produced `Span`s into `detect_all`'s `_resolve` (give key-mapped spans high priority,
   on par with checksum IDs, since a typed key is strong evidence).

Net: closes the "value hidden in structure" gap, adds a deterministic RU key signal, reuses the
existing detectors as the per-value analyzer, and keeps offsets correct for kv (exact) and JSON
(via raw-token remap or replace-by-value). MIT-clean; no obligation to vendor `presidio-structured`.

---

## 8. Open questions / uncertainties
- Exact RU localization needed in recognizer `context` lists for implicit boosting to fire — must be
  authored; no public RU map found. **[C]**
- For deeply nested / mixed arrays of objects, `raw_decode` walking needs care to track per-value raw
  offsets; the simpler replace-by-value path may be preferable for the redaction use case. **[D]**
- `presidio-structured` collapses to ONE entity per key (first result / column aggregate) — fine for
  homogeneous fields, lossy if one key holds mixed content (rare in forms). **[A]**
