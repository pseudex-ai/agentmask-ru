# DD2 Notes A — Local High-Recall RU PERSON (ФИО) Detection

Scope: LOCAL (CPU / small-GPU, no cloud egress) detection of Russian PERSON names at HIGH RECALL,
fixing Natasha/Slovnet failure modes: Latin-script names ("Ivan Petrov"), diminutives ("света", "Маша"),
oblique/declined forms, initials ("Сидоров И.И."), lowercase, plus over-tagging (false positives).
Evidence grades: [A] read/benchmarked source · [B] single source · [C] asserted by vendor · [D] inference.

---

## TL;DR / Recommendation

1. **Primary NER model: a DEDICATED supervised Russian NER, not GLiNER.** The original GLiNER multilingual
   scores only **33.3 F1 on Russian** zero-shot (Multi-CoNER), and the production GLiNER PII variants
   (`urchade/gliner_multi_pii-v1`, `knowledgator/gliner-pii-*`, `knowledgator/gliner-x-*`) **do not list Russian**
   among supported languages. GLiNER is a strong *English/EU* PII tool; for Russian ФИО it is a recall liability.
2. Best dedicated RU PERSON options, in order:
   - **`Gherman/bert-base-NER-Russian`** (mBERT, 0.2B, MIT). Separate `FIRST_NAME/LAST_NAME/MIDDLE_NAME`
     labels; reported overall **F1 0.988** on the Detailed-NER-Dataset-RU test (but small/partly synthetic set — see caveats).
   - **`DeepPavlov/ner_rus_bert`** (RuBERT, trained on Collection3/Persons-1000). Top-tier RU NER, but heaviest.
   - **`spaCy ru_core_news_lg`** (MIT, 489 MB): PER **F1 0.958 / P 0.961 / R 0.956** in-domain news — best
     Presidio-native path (it *is* a usable NlpEngine + tokenizer in one).
   - **Natasha/Slovnet (current)**: ceiling ~0.97–0.99 F1 PER on its own *synthetic news* eval; same news-domain
     blind spots as the others. This is your baseline, not a fix.
3. **None of these alone fix Latin / diminutive / lowercase**, because they are all trained on capitalized
   canonical news text. The fix is an **add-on gazetteer recognizer** (Presidio `PatternRecognizer`/custom
   `EntityRecognizer`) built from a RU first-name + diminutive list, expanded through all grammatical cases with
   **pytrovich / pymorphy3**, matched **case-insensitively** with `pytrovich`/`russiannames` gender filtering to
   curb false positives. This is the actual recall lever for света/Маша/Сидорова/declensions.
4. **CPU-viable**: yes. spaCy lg ~ tens of ms/msg; mBERT/RuBERT ~50–200 ms/msg on CPU (acceptable for a gateway;
   use ONNX/quantization or a tiny model if you need <30 ms). Gazetteer lookup is sub-ms.

---

## 1. GLiNER family — does it work for RUSSIAN PERSON?

### 1.1 Core fact: original GLiNER is weak on Russian [A]
Source: GLiNER NAACL 2024 paper (Zaratiana et al.), `aclanthology.org/2024.naacl-long.300.pdf`, **Table 3 (p.5369)**
"Zero-Shot Scores on Different Languages" (Multi-CoNER, Malmasi et al. 2022):

| Language (Non-Latin) | Sup. (XLM-R) | ChatGPT | GLiNER-En | GLiNER-Multi |
|---|---|---|---|---|
| **Russian** | **59.7** | 27.4 | 30.3 | **33.3** |
| Korean | 55.8 | 30.0 | 20.5 | 28.7 |
| Turkish | 46.8 | 31.9 | 22.0 | 30.0 |
| Chinese | 53.1 | 18.8 | 6.59 | 24.3 |

Latin langs are far better (German 39.5, Spanish 42.1, English 41.7). Paper explicitly states non-Latin
underperforms and Conclusion notes future work "to better adapt it for low-resource languages." [A]
→ **Vanilla GLiNER-Multi at 33.3 F1 Russian is far below the supervised baseline (59.7) and below
Natasha/spaCy-ru (~0.95 PER in-domain). Do NOT use it as the RU primary.** [A]/[D for the comparison framing]

### 1.2 Precision/Recall is tunable via negative sampling + threshold [A]
Same paper, **Table 5 (p.5371) "Effect of negative entity types sampling"**:
| Neg. Samples | Prec | Rec | F1 |
|---|---|---|---|
| 0% | 49.3 | **58.1** | 53.3 |
| 50% | **62.3** | 59.7 | **60.9** |
| 75% | 61.1 | 56.5 | 58.6 |
→ Lower negatives / lower threshold = higher recall, more false positives; the knowledgator PII cards expose
this directly: `threshold` default **0.3**, "0.2 for higher recall, 0.6 for higher precision". [A]
This is the GLiNER mechanism for the "tune for recall" requirement — but it only helps where GLiNER already works (EN/EU).

### 1.3 Production PII / multilingual GLiNER variants — language coverage
- `urchade/gliner_multi_pii-v1` — fine-tuned on `urchade/synthetic-pii-ner-mistral-v1`; **6 languages: EN, FR, DE, ES, IT, PT. Russian NOT included.** Apache-2.0. Backbone `gliner_multi-v2.1` (mDeBERTa-like). This is exactly the model in Presidio's GLiNER sample. [A] (HF card + search)
- `knowledgator/gliner-pii-{edge,small,base,large}-v1.0` — trained `synthetic-multi-pii-ner-v1`; cards list **English** (large also tagged "multilingual" but no RU evidence). Apache-2.0. Benchmarks (synthetic-multi-pii-ner-v1): [A]
  - large: **F1 83.25 / P 87.42 / R 79.4**
  - base: F1 80.99
  - edge: **F1 75.50 / P 78.96 / R 72.34** ("trades recall for latency/footprint")
  - ONNX FP16 (330 MB) + UINT8 (197 MB); threshold 0.3 default. **No RU benchmark.** [A]
- `knowledgator/gliner-x-*` (GLiNER-X) — **MT5 encoder**, trained on `gliner-multilingual-synthetic` (LLM-annotated FineWeb-2). Card lists **20+ langs incl. Ukrainian, NOT Russian.** Apache-2.0, ONNX available, 0.5B (base). Benchmarks given for da/de/en UD only. [A]
- `knowledgator/gliner-multitask-large-v0.5` — **English only**; avg F1 0.6276 (CrossNER/MIT). Multitask (NER+RE+QA). [A]

**Conclusion on GLiNER for RU:** No officially RU-supported GLiNER PII model exists as of 2026-06. The MT5/mDeBERTa
backbones have *some* incidental Cyrillic capacity (FineWeb-2/mC4 contain Russian), so zero-shot label `"человек"`/`"имя"`/`"person"`
might fire — but there is **no published RU recall number** and the one comparable data point (Multi-CoNER 33.3) is poor. [A for cards; D for "might fire"]

### 1.4 Presidio's built-in `GLiNERRecognizer` — integration path [A]
Source: `microsoft.github.io/presidio/samples/python/gliner/`. Install `pip install 'presidio-analyzer[gliner]'`.
```python
from presidio_analyzer.predefined_recognizers import GLiNERRecognizer
gliner_recognizer = GLiNERRecognizer(
    model_name="urchade/gliner_multi_pii-v1",
    entity_mapping={"person": "PERSON", "name": "PERSON",
                    "organization": "ORGANIZATION", "location": "LOCATION"},
    flat_ner=False, multi_label=True, map_location="cpu",
    # load_onnx_model=True  # for ONNX runtime
)
analyzer_engine.registry.add_recognizer(gliner_recognizer)
analyzer_engine.registry.remove_recognizer("SpacyRecognizer")
```
→ Path exists and is clean, but with a RU-supporting model it would need a RU GLiNER (none available). Usable as a
*secondary* recognizer for Latin-script names alongside a RU NlpEngine. [A]

### 1.5 GLiNER CPU latency [A/B]
- GLiNER2 paper (arXiv 2507.18546): CPU latency **130 ms (5 labels) → 208 ms (50 labels)** per text. [A]
- `gline-rs` (Rust ONNX engine, Apache-2.0): **6.67 seq/s CPU** (i9, 8c) vs 1.61 Python (~4×); 248 seq/s on RTX 4080.
  Models: gliner_small-v2.1, gliner-multitask-large-v0.5, gliner-x-large (ONNX). [A]
- ONNX quantization for GLiNER is **finicky**: GitHub issues #191 (ONNX slower than torch in some configs) and #218
  (UINT8 quant returns empty list at default threshold) — test before trusting. [B]
→ CPU-viable for a per-message gateway (~100–200 ms/msg torch, ~150 ms/msg ÷4 with gline-rs), but RU coverage is the blocker, not speed.

---

## 2. spaCy RU models — best Presidio-native primary [A]

Source: spaCy model `meta` JSON (`github.com/explosion/spacy-models`), trained on news (`newswritten`), license **MIT**.
NER labels: PER, LOC, ORG. Numbers are **in-domain news test** (clean, capitalized, canonical) — the optimistic ceiling.

| Model | Size | PER F1 | PER P | PER R | Overall ents_f |
|---|---|---|---|---|---|
| `ru_core_news_lg` 3.8 | 489 MB | **0.958** | 0.961 | 0.956 | 0.947 |
| `ru_core_news_sm` 3.8 | 14 MB | 0.954 | 0.957 | 0.951 | 0.944 |

→ Interesting: **sm PER F1 (0.954) ≈ lg (0.958)**; the lg advantage is mostly ORG + vectors. For PERSON-only on CPU,
`ru_core_news_sm` (14 MB, fastest) is a strong cost/perf pick. [A]
→ All spaCy-ru NER is news-trained ⇒ same Latin/lowercase/diminutive blind spots as Natasha. The number is a ceiling, not field recall. [A card; D field-degradation]
→ Presidio uses spaCy as the default NlpEngine, so this is the **lowest-friction integration**.

---

## 3. DeepPavlov / Natasha-Slovnet ceiling [A/B]

- **`DeepPavlov/ner_rus_bert`** — RuBERT backbone, fine-tuned Collection3 / Persons-1000 (+LOC/ORG). Among the
  strongest published RU NER (the project claims it beats PullEnti, Stanza; Slovnet README says Slovnet-BERT ≈ DeepPavlov).
  Heavy (RuBERT ~180M); CPU latency notable (DeepPavlov's own note: tiny 4× / base 2× faster than full). Apache-2.0.
  Heavy install (DeepPavlov framework). [B]
- **`ner_ontonotes`** — multilingual OntoNotes; weaker for RU ФИО than ner_rus_bert; not recommended. [D]
- **Natasha/Slovnet (current system)** — Slovnet README/site: NER **F1 ≈ 0.91 avg (PER/LOC/ORG)**; Slovnet-BERT 0.92;
  on their *synthetic news markup* by-token PER **99%**, LOC 98%, ORG 97%. Comparable to DeepPavlov. [A — natasha.github.io/ner, github.com/natasha/slovnet]
  → Ceiling is high *on news*. Your observed misses are **distribution shift** (Latin, lowercase, diminutive, oblique,
  initials), not a weak model. Swapping Slovnet→spaCy-lg/RuBERT will NOT fix those failure modes materially. [D, strongly supported]

---

## 4. The actual recall fix — GAZETTEER + morphology add-on

The failure modes are out-of-distribution for *every* news-trained Russian NER. The correct fix is a
deterministic gazetteer recognizer layered on top of the NER. Components:

### 4.1 Name + diminutive lists (offline, local) [A]
- **`kenoma/RussianNameVariants`** — CSV `Name;InvariantName` mapping variants/diminutives → base, **incl. Cyrillic AND
  Latin transliterations**: `Леночка→Елена`, `Ленчик→Елена`, `Lena→Елена`. Directly solves diminutives ("света","Маша")
  AND Latin-script names in one table. [A] (license unstated — verify before bundling).
- **`datacoon/russiannames`** (BSD-3) — 32k first names, 375k surnames, 48k patronymics + **gender detection** +
  9 ethnicity classes. Great for (a) seeding the gazetteer and (b) **false-positive control** (is this token a real RU name?).
  Needs MongoDB (or extract the BSON dumps to a flat dict for offline use). [A]
- **`ulzr/realistic-russian-names`** (Ruby gem) — first/last/patronymic + popularity weights + male→female surname
  derivation (Иванов→Сидорова). Useful for surname-gender variants. [A]
- **`sorokinpf/russian_names`** — plain sorted name/surname wordlists (quick seed). [B]

### 4.2 Declension / oblique-form expansion [A]
- **`pytrovich`** (petrovich port) — inflects RU first/last/middle names across **all 6 cases** + gender detection.
  Use it to *generate* declined surface forms ("Сидорова","Сидорову","Сидоровым") from each gazetteer base form so the
  matcher catches oblique forms. Purpose-built for anthroponyms. [A]
- **`pymorphy3`** (pymorphy2 successor, MIT) — general morphological analyzer/inflector; at *match time* lemmatize each
  token and compare the lemma to the gazetteer (handles cases without pre-expanding). Note: pymorphy is documented as
  weak on diminutives specifically — that is exactly why you also need the explicit diminutive list (4.1). [A/B]
→ Two viable strategies: (a) pre-expand the gazetteer to all cases with pytrovich (fast match, big set), or
  (b) lemmatize-then-lookup with pymorphy3 at runtime (small set, slight per-token cost). (a) is better for a hot gateway path. [D]

### 4.3 Initials ("Сидоров И.И.") and lowercase
- Initials: a **regex `PatternRecognizer`** — `\b[А-ЯA-Z]\.\s?[А-ЯA-Z]\.` adjacent to a gazetteer/NER surname, OR
  `Surname И.О.` pattern. Pure pattern, deterministic. [D]
- Lowercase: match the gazetteer **case-insensitively** (NER models won't fire on lowercase; the gazetteer will). [D]
- Latin: covered by the Latin transliterations in `kenoma/RussianNameVariants` + a transliteration normalizer
  (e.g. `transliterate` lib) to map "Ivan Petrov" → Cyrillic for gazetteer hit, or keep Latin entries in the list. [D]

### 4.4 False-positive control (over-tagging)
- Gazetteers over-fire on ambiguous tokens (e.g. "Вера"=faith/name, "Роман"=novel/name, "света"=light/name).
  Mitigate with: (a) `russiannames` gender/validity check, (b) Presidio **context words** + score, (c) require ≥2 name
  parts OR NER agreement for a high-confidence hit, single-token lowercase diminutive gets a lower score. [D]
- Presidio `PatternRecognizer` supports `context` words and per-pattern `score`; combine recognizer scores so a
  gazetteer-only single-token hit is "possible" not "certain". [A — Presidio docs]

---

## 5. Presidio integration paths (exact)

### Path A (recommended) — spaCy-ru NlpEngine + custom gazetteer recognizer
```yaml
# nlp config
nlp_engine_name: spacy
models:
  - lang_code: ru
    model_name: ru_core_news_lg   # or _sm for speed; PER F1 ~equal
```
spaCy's `SpacyRecognizer` maps PER→PERSON automatically. Then add a custom RU name gazetteer recognizer:
```python
from presidio_analyzer import EntityRecognizer, RecognizerResult
# load_method: load gazetteer set (base + pytrovich-expanded cases, lowercased) + diminutive map
# analyze(): tokenize, case-insensitive lookup, emit RecognizerResult("PERSON", start, end, score)
analyzer.registry.add_recognizer(RuNameGazetteerRecognizer(supported_language="ru"))
```
(Custom recognizer = implement `load()` + `analyze()`; Presidio docs `analyzer/adding_recognizers/`.) [A]

### Path B — HF transformers model as NlpEngine (RuBERT / Gherman)
```yaml
nlp_engine_name: transformers
models:
  - lang_code: ru
    model_name:
      spacy: ru_core_news_sm            # tokenizer only
      transformers: Gherman/bert-base-NER-Russian   # or a RuBERT NER
ner_model_configuration:
  aggregation_strategy: max
  alignment_mode: expand
  model_to_presidio_entity_mapping:
    PER: PERSON
    FIRST_NAME: PERSON
    LAST_NAME: PERSON
    MIDDLE_NAME: PERSON
  low_confidence_score_multiplier: 0.4
```
Then add the same gazetteer recognizer as in Path A. [A — Presidio transformers docs]

### Path C — GLiNER as a *secondary* recognizer (Latin-script catch only)
Add `GLiNERRecognizer(model_name="urchade/gliner_multi_pii-v1", entity_mapping={"person":"PERSON","name":"PERSON"}, ...)`
*alongside* the RU NlpEngine, scoped to Latin-script spans, low score (it's the only one of these that's strong on
"Ivan Petrov"). Keep `SpacyRecognizer` (don't remove it as in the Presidio sample). [A path; D scoping idea]

**Recommended stack:** Path A (spaCy-ru_core_news_lg NlpEngine) + custom gazetteer recognizer (kenoma variants +
datacoon validity + pytrovich case-expansion, case-insensitive, with context-word FP control) + optional Path C
GLiNER for Latin names. Tune thresholds toward recall; let the gazetteer be "possible-PII" with FP control downstream.

---

## 6. Per-option scorecard

| Option | RU PER recall/F1 (cond.) | License | CPU gateway | Presidio path | Fixes Latin/dim/decl/initials? |
|---|---|---|---|---|---|
| spaCy `ru_core_news_lg` | PER F1 0.958 (in-domain news) [A] | MIT | ✅ ~10s ms | Native NlpEngine | ❌ none (news-trained) |
| spaCy `ru_core_news_sm` | PER F1 0.954 (in-domain news) [A] | MIT | ✅ fastest, 14 MB | Native NlpEngine | ❌ none |
| `Gherman/bert-base-NER-Russian` | F1 0.988 overall (small/synthetic set) [A/caveat] | MIT | ⚠️ ~50–150 ms (mBERT 0.2B) | transformers NlpEngine | partial: separate name parts; still news/canonical |
| `DeepPavlov/ner_rus_bert` | top-tier RU (≈Slovnet-BERT 0.92) [B] | Apache-2.0 | ⚠️ heaviest | custom EntityRecognizer | ❌ news-trained |
| Natasha/Slovnet (current) | PER ~0.97–0.99 synthetic-news [A] | MIT | ✅ light | custom recognizer | ❌ (your current misses) |
| GLiNER multi/PII/X | RU **not supported**; Multi-CoNER RU 33.3 [A] | Apache-2.0 | ✅ ~100–200 ms / 4× w/ gline-rs | built-in GLiNERRecognizer | ✅ Latin only; ❌ RU oblique/dim |
| **Gazetteer add-on** (kenoma+datacoon+pytrovich/pymorphy3) | the recall lever for dim/lowercase/Latin/oblique | mixed (BSD/MIT; verify kenoma) | ✅ sub-ms | PatternRecognizer / custom EntityRecognizer | ✅✅ all four, with FP control |

---

## 7. Open questions / caveats
- `Gherman/bert-base-NER-Russian` 0.988 F1 is on a small, partly ChatGPT-generated set (Detailed-NER-Dataset-RU) →
  likely optimistic vs real chat/oblique text. Needs your own eval. [A/caveat]
- Whether `Detailed-NER-Dataset-RU` includes declined/oblique name forms is unconfirmed (couldn't read the data dir). [open]
- No published RU recall number for any GLiNER PII model — empirically test gliner-x-large with `["имя","человек"]`
  before dismissing entirely, but expectations should be low (Multi-CoNER 33.3). [open]
- `kenoma/RussianNameVariants` license not stated on the card — confirm before bundling into a product. [open]
- datacoon `russiannames` ships as MongoDB BSON — extract to a flat in-memory dict/set for the gateway (avoid a DB dep). [D]

## 8. Primary sources
- GLiNER NAACL 2024 (Tables 3 & 5): https://aclanthology.org/2024.naacl-long.300.pdf · arXiv 2311.08526
- Presidio GLiNER sample: https://microsoft.github.io/presidio/samples/python/gliner/
- Presidio transformers NlpEngine: https://microsoft.github.io/presidio/analyzer/nlp_engines/transformers/
- Presidio custom recognizers: https://microsoft.github.io/presidio/analyzer/adding_recognizers/ ; .../developing_recognizers/
- urchade/gliner_multi_pii-v1: https://huggingface.co/urchade/gliner_multi_pii-v1
- knowledgator gliner-pii-{edge,large}-v1.0: https://huggingface.co/knowledgator/gliner-pii-large-v1.0 ; .../gliner-pii-edge-v1.0
- knowledgator gliner-x-base: https://huggingface.co/knowledgator/gliner-x-base
- gliner-multitask-large-v0.5: https://huggingface.co/knowledgator/gliner-multitask-large-v0.5
- spaCy ru meta: https://raw.githubusercontent.com/explosion/spacy-models/master/meta/ru_core_news_lg-3.8.0.json ; .../ru_core_news_sm-3.8.0.json
- Gherman/bert-base-NER-Russian: https://huggingface.co/Gherman/bert-base-NER-Russian (data: github.com/AlexKly/Detailed-NER-Dataset-RU)
- DeepPavlov NER: https://docs.deeppavlov.ai/en/master/features/models/ner.html
- Natasha/Slovnet: https://natasha.github.io/ner/ ; https://github.com/natasha/slovnet
- Gazetteers: kenoma/RussianNameVariants · datacoon/russiannames · ulzr/realistic-russian-names · sorokinpf/russian_names
- Morphology: petrovich/pytrovich · pymorphy3 (pypi.org/project/pymorphy3/)
- gline-rs (Rust CPU ONNX): https://github.com/fbilhaut/gline-rs · GLiNER2 arXiv 2507.18546
