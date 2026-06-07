# DD2 Notes D — Defense-in-Depth PII Detector: Architecture + Eval Methodology

**Objective:** A recall-first, defense-in-depth PII detector that maximizes RECALL (recall is
the privacy metric — every miss leaks) without destroying precision, running **LOCALLY**
(no cloud-LLM egress — sending PII to a cloud LLM to detect PII defeats the product), plus
the eval methodology to measure and push recall toward 95–99%.

**Out of scope (other agents):** RU NER models, address grammars, the context/collision
algorithm internals. This note is **architecture + local-LLM-verifier + eval methodology**.

**Evidence grades:** **[A]** = read it in source code · **[B]** = official docs · **[C]** =
peer-reviewed paper / measured benchmark · **[D]** = inference/synthesis · **[E]** = blog/secondary.

---

## 0. The core thesis (why defense-in-depth, why recall-first)

PII detection has an **asymmetric loss function**: a false negative (missed PII) is a
compliance/privacy breach that leaks data downstream; a false positive (over-redaction) is a
usability cost. Therefore **recall is the privacy SLA** and precision is a UX/utility budget.
The whole architecture follows from this asymmetry:

1. **Stage 1 (recall maximizer):** run *many* recognizers in parallel and take the **UNION**
   of their spans (catch-if-any). Each detector's job is to never miss its specialty. This
   pushes recall up but tanks precision (you collect everyone's false positives too).
2. **Stage 2 (precision recovery):** a second pass — checksum/validation, context scoring,
   conflict resolution, and optionally a **local** verifier (GLiNER or small local LLM) —
   *demotes or drops* spurious spans **without removing true PII**.
3. **Fail-safe disposition:** spans that survive Stage 1 but are *uncertain* after Stage 2 are
   **not silently dropped** — they are redacted/tokenized anyway (block-on-uncertain), because
   the cost of leaking > the cost of over-redacting.

This is exactly the two-stage pattern that the literature converged on:
> "we propose a two-stage detection pipeline that first identifies potential sensitive data
> with **high recall**, then uses contextual information to **improve precision**."
> — *Towards Contextual Sensitive Data Detection*, arXiv 2512.04120 **[C]**
> (>90% recall first pass; LLM context verifier removes FPs; code at
> github.com/trl-lab/sensitive-data-detection)

---

## 1. The recall/precision tradeoff — quantified

The union-of-detectors strategy has a documented, severe precision cost in practice:

- **Presidio default precision measured at 22.7%** on mixed-language enterprise data (Alvaro
  et al. 2024). I.e. fewer than 1 in 4 detections is real PII. A system at **95% recall ×
  22.7% precision** raises ~3.4 wrong alerts per true entity → ~44k total alerts for 10k real
  entities, ~34k of them wrong. This is the "**false positive tax**."
  — anonym.legal, "The False Positive Tax" **[E]** (cites Alvaro 2024)
- Root cause is structural: checksum-validated recognizers (e.g. a number that passes a
  Luhn/TFN checksum) get **max score regardless of context**, so *threshold filtering cannot
  recover precision* — "The scores are already at maximum." Precision recovery must be a
  **separate stage** (context / second model), not a threshold knob. **[E][D]**
- The hybrid/ensemble study confirms the direction: "combining detectors via **union maximizes
  recall at the cost of precision**." — *An Evaluation Study of Hybrid Methods for Multilingual
  PII Detection*, arXiv 2510.07551 **[C]** (combined regex + 5 multilingual NER models +
  LLM; union flag-if-any).

**The recovery numbers** (what the second stage buys back) — from *Contextual Sensitive Data
Detection* reflection experiments: a context/reflection pass took **Qwen3-14B to 0.73 precision
at 0.94 recall** (i.e. it trades a *small* recall drop for a *large* precision gain). **[C]**
The design principle: Stage 2 should be tuned to **preserve recall** (only drop spans it is
confident are non-PII), accepting that some precision is left on the table.

**Takeaway for the architecture:** union → high recall, low precision; a recall-preserving
second stage moves precision from ~0.23 to ~0.7+ while keeping recall ≥0.94. The product's
recall SLA is set in Stage 1; Stage 2 only ever *removes* FPs, never adds FNs.

---

## 2. Recall ceiling references (what "good" looks like)

Clinical de-id (i2b2 2014) is the best-studied recall benchmark — use it as the north star:

- **i2b2 2014 shared task:** mean entity-level F1 0.872, **max 0.964** across 10 teams.
  — *Overview of 2014 i2b2/UTHealth shared task Track 1*, PMC4989908 **[C]**
- **Philter (UCSF, rule-based + statistical):** **99.92% recall, F2 = 94.77%** on i2b2 2014
  discharge summaries — the canonical *recall-first* system. It is explicitly built to find
  "parts of text that are **highly unlikely to be PHI**" (i.e. it errs toward redaction).
  — *Philter*, npj Digital Medicine, s41746-020-0258-y **[C]**
- **Fine-tuned small NER ≥ GPT-4:** expert DeBERTa/BERT NER models hit **F1-micro 0.966**
  (English), **macro 0.931 vs GPT-4o's 0.5775** on the same i2b2 categories.
  — *LLMs-in-the-Loop Part 2*, arXiv 2412.10918 **[C]** (detail in §4).
- **GLiNER fine-tuned (clinical):** micro-F1 **0.980**, "**95% of documents completely
  sanitised**", residual **2% entity-level false-negative rate** → authors keep
  **human-in-the-loop** because 2% FN is still too high to fully trust. Runs on a **laptop
  without GPU**. — *LOGICAL*, arXiv 2510.19346 **[C]**

**Honest framing:** 95–99% recall is achievable, but the *last few %* of recall is where the
leaks live, and even SOTA keeps a human/fail-safe loop. Design for "minimize residual FN,"
not "claim 100%."

---

## 3. Recommended defense-in-depth architecture

```
                          ┌─────────────────────────────────────────────┐
   input text ───────────►│  STAGE 1 — RECALL UNION (catch-if-any)       │
                          │  run all recognizers in PARALLEL, union spans │
                          ├─────────────────────────────────────────────┤
                          │  1a. Regex + checksum (structured PII):       │
                          │      SSN/INN/SNILS/card(Luhn)/email/IP/IBAN…  │
                          │      → high precision, near-perfect recall    │
                          │      for well-formed identifiers              │
                          │  1b. NER #1 — spaCy/transformer (names,       │
                          │      orgs, locations)                         │
                          │  1c. NER #2 — GLiNER zero-shot (catches what  │
                          │      1b misses; different error profile)      │
                          │  1d. deny-lists / gazetteers (known values)   │
                          │  → LOW per-recognizer score threshold here    │
                          └───────────────────────┬─────────────────────┘
                                                  │ union of RecognizerResult spans
                                                  ▼
                          ┌─────────────────────────────────────────────┐
                          │  STAGE 2 — PRECISION RECOVERY (recall-safe)   │
                          │  2a. checksum/format validation → boost/keep  │
                          │  2b. context scoring (proximity words boost;  │
                          │      absence demotes) — Presidio LemmaContext │
                          │  2c. conflict resolution / dedupe (overlap,   │
                          │      keep highest-score, longest span)        │
                          │  2d. OPTIONAL local verifier (GLiNER or       │
                          │      small local LLM) on AMBIGUOUS spans only │
                          │  → drop a span ONLY if confidently non-PII    │
                          └───────────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                          ┌─────────────────────────────────────────────┐
                          │  STAGE 3 — FAIL-SAFE DISPOSITION              │
                          │  high-confidence → tokenize (reversible)      │
                          │  uncertain      → redact (block-on-uncertain) │
                          │  never silently pass an uncertain span        │
                          └─────────────────────────────────────────────┘
```

### 3.1 Why union in Stage 1 (recall = OR of detectors)

Recall of a union ≈ `1 − Π(1 − recall_i)` when detector errors are *independent*. Two detectors
each at 0.90 recall, if independent, union ≈ 0.99. The leverage is **error-profile diversity**:
regex catches well-formed IDs that NER misses; NER catches names/locations regex can't express;
GLiNER (different training data) catches what spaCy misses. Stack detectors whose *misses* don't
correlate. This is the single biggest recall lever and it is free precision-wise *because Stage 2
recovers it*. **[D]** (grounded in 2510.07551 union finding **[C]**)

### 3.2 Score thresholds — recall-first knob

- Set **Stage-1 per-recognizer thresholds LOW** so weak detections survive into Stage 2.
  Presidio applies a global `score_threshold` and per-recognizer scores; lowering it raises
  recall at the cost of FPs that Stage 2 then prunes. **[A]** (from dd-notes-2 §1.1:
  `__remove_low_scores(results, score_threshold)` runs *after* recognizers).
- **Entity-specific thresholds** are the right granularity (not one global number). GuardrailsPII
  uses: `EMAIL_ADDRESS = 1.0` (pattern, perfect-match), `PERSON/LOCATION/PHONE/DATE = 0.5`
  (ML), GLiNER-mapped `= 0.5`, others `= 0.0` (no filtering). **[B]**
- **Critical caveat:** thresholds *cannot* fix the checksum-FP problem (scores already maxed) —
  that's what context (2b) and the verifier (2d) are for. **[E]**

### 3.3 Stage 2 precision recovery, ordered cheapest→most expensive

1. **Checksum/format validation** (Luhn for cards, INN/SNILS control digits, IBAN mod-97):
   essentially free, turns "looks like a card" into "is a valid card." High-precision *boost*.
2. **Context scoring**: Presidio's `LemmaContextAwareEnhancer` boosts score when context words
   ("card", "passport", "СНИЛС") appear within a window; this is the documented precision lever
   for the checksum-maxed case. **[A]** (dd-notes-2) / **[E]**
3. **Conflict resolution / dedupe**: Presidio `remove_duplicates` sorts by
   `(-score, start, -length)` and drops same-type spans *contained within* a kept span — handles
   the union's overlapping detections. **[A]** (dd-notes-2 §1.3)
4. **Local verifier on ambiguous spans ONLY** (§5) — most expensive, so gate it: only run the
   LLM/GLiNER verifier on spans whose post-context score sits in a middle band (e.g. 0.3–0.6),
   not on every span. Keeps cost bounded.

### 3.4 Stage 3 — fail-safe disposition (the recall backstop)

- **block-on-uncertain**: an uncertain span is treated as PII. The literature supports a
  "delay the definitive decision" mechanism that gathers more context before classifying;
  in a batch/non-conversational gateway, the safe default is **redact rather than pass**. **[E]**
- **Redaction vs tokenization for uncertain spans**: tokenization (reversible) is the right
  default for *confident* PII (preserves downstream utility + round-trip). For *uncertain* spans,
  prefer **destructive redaction or a generic placeholder** — you don't want a reversible token
  pointing at maybe-PII, and you don't need to round-trip a low-confidence guess. (Reversibility
  detail is dd-notes-2 territory; the *disposition decision* belongs here.) **[D]**

---

## 4. Local NER vs local LLM as the second-pass catcher

The "second model" can be (a) another NER (GLiNER), or (b) a small local LLM. Both run **on the
customer's own hardware — no egress**. Evidence:

### 4.1 GLiNER as a cheap local NER recognizer

- **What it is:** zero-shot generalist NER — you pass a label list at runtime
  (`["first name","credit card","passport"]`) and it finds them, no retraining. Bidirectional
  transformer. — GLiNER paper, arXiv 2311.08526 **[C]**
- **Runs on CPU.** Presidio ships a first-class `GLiNERRecognizer`; recommended model
  `urchade/gliner_multi_pii-v1`; registered like any recognizer; `map_location="cpu"`,
  optional `load_onnx_model=True`; entity_mapping translates GLiNER labels → Presidio labels;
  you can `registry.remove_recognizer("SpacyRecognizer")` to avoid double-NER. **[B]**
  ```python
  gliner_recognizer = GLiNERRecognizer(
      model_name="urchade/gliner_multi_pii-v1",
      entity_mapping={"person":"PERSON","name":"PERSON","location":"LOCATION", ...},
      flat_ner=False, multi_label=True, map_location="cpu")
  analyzer_engine.registry.add_recognizer(gliner_recognizer)
  ```
- **Quality:** off-the-shelf `knowledgator/gliner-pii-*` — base **P 79.28 / R 82.78 / F1 80.99**;
  large F1 83.25; edge F1 75.50 (synthetic-multi-pii-ner-v1). Apache-2.0. Rust impl ~4× Python on
  CPU. **[B]** Fine-tuned on-domain it jumps dramatically (LOGICAL: F1 0.980 on clinical). **[C]**
- **Latency:** GLiNER2 reports **~130–208 ms CPU** per call depending on #labels, ~2.6× faster
  than GPT-4o. (ONNX conversion was *slower* in one issue; int8 quant can help but degraded
  quality in some reports — measure before trusting quant.) **[C][E]**

### 4.2 Small local LLM (quantized 1–3B on llama.cpp/CPU) as verifier

- **Feasible & private:** TinyLlama-1.1B Q4_K_M fits <1 GB RAM; Q4_K_M keeps ~95% of FP16 quality
  at ~25% memory. llama.cpp is the CPU-first runtime; no cloud, no egress. **[E]**
- **Best use is VERIFICATION, not primary detection.** A small LLM is a strong *judge* of "is
  this span actually PII in context?" (binary/boolean over a candidate) but a weak *exhaustive
  finder* (recall of generative span extraction at 1–3B is unreliable; small LLMs hallucinate
  spans and miss formats). So: **use it in Stage 2 (2d) on ambiguous spans**, prompted
  "Given context X, is the span S personal data? yes/no + which type." Keep regex+NER as the
  recall engine.
- **Important counter-evidence — don't make the LLM the detector:** fine-tuned *small NER*
  beats general LLMs on de-id. *LLMs-in-the-Loop Part 2* (2412.10918) deliberately **does not
  run an LLM at inference** ("we don't implement LLMs directly… we developed Expert Small NER
  Models with the LLM-in-the-loop methodology") precisely for **on-prem privacy**, and their
  fine-tuned **deberta-v3-small + regex** hits **F1-micro 0.966 (EN)** / macro **0.931 vs
  GPT-4o 0.5775**. **[C]** The LLM's value is in *building/labelling training data offline*,
  not in the hot path.
- **Their architecture is itself the recommended pattern:** *regex/rule-based for structured
  labels* (ACCOUNT, DLN, EMAIL, FAX, IP, LICENSE, PLATE, SSN, URL, VIN) ∪ *DL-NER for free-text
  labels* (AGE, CITY, DOCTOR, HOSPITAL, IDNUM, PATIENT, PROFESSION, STREET, …). Exactly the
  regex-structured ∪ NER-unstructured union of §3. **[C]**

### 4.3 Decision: GLiNER vs small LLM for Stage 2

| Criterion | GLiNER (NER) | Small local LLM (1–3B) |
|---|---|---|
| Local / no egress | yes | yes |
| Primary recall finder | **yes** (use in Stage 1c) | no (unreliable) |
| Span verifier / judge | ok | **yes** (context reasoning) |
| Latency (CPU) | ~130–200 ms **[C]** | seconds (slower; gate it) |
| Determinism / auditability | high | lower (sampling) |
| Best role | **Stage 1 union member + cheap verifier** | **Stage 2d judge on ambiguous spans only** |

**Recommendation:** GLiNER in **Stage 1c** (recall union, cheap, deterministic). A small local
LLM is **optional Stage-2d** — run it only on the middle-confidence band to recover precision
with contextual reasoning, never as the primary detector, never in the recall path. Both stay
on-prem.

---

## 5. Eval methodology — `microsoft/presidio-research` (`presidio_evaluator`)

This is how to **measure recall honestly**. Read against current `master` (June 2026). The
package now has **two evaluators**: a deprecated token-level `Evaluator`/`TokenEvaluator` and a
**span-level `SpanEvaluator`** (the one to use). Files under
`presidio_evaluator/evaluation/`: `base_evaluator.py`, `span_evaluator.py`, `token_evaluator.py`,
`scorers.py`, `model_error.py`, `evaluation_result.py`. **[A]**

### 5.1 The metric math (`base_evaluator.py`) **[A]**

```python
precision(tp, num_predicted) = tp / num_predicted        # else nan if 0
recall(tp, num_annotated)    = tp / num_annotated         # else nan
f_beta(p, r, beta) = (1+beta**2)*p*r / (beta**2*p + r)
```
- **`beta` defaults to 2.0** in `calculate_score`, and `score_model()` even uses **beta=2.5** —
  i.e. the framework *bakes in recall-weighting*. F2 weights recall 4× more than precision; the
  docs say outright: "**recall is often more important than precision… β=2 is recommended.**"
  **[A][B]** This is the metric the product should report (F2 + raw recall), not F1.
- `pii_recall` / `pii_precision` = micro across all PII; `entity_recall_dict` /
  `entity_precision_dict` = **per-entity** recall/precision (so you can see *which* entity type
  is leaking). **[A]**

### 5.2 Token-level vs span-level matching — the honesty question

**Token-level (`TokenEvaluator`, legacy, deprecated):** compares tag-per-token via a
`Counter[(annotation, prediction)]`; TP where annotation==prediction, FN where prediction=="O",
FP where annotation=="O". `compare_by_io=True` collapses BILUO/BIO→IO. It also **reverts
"known errors"**: skip-words (stop words/punct) are not counted, and **generic predictions**
(`PII, ID, NUMBER, GENERIC_PII, PHI`) matched against a specific annotation are *credited as
correct* — important so a detector that says "PII" instead of "PERSON" isn't penalized on recall.
**[A]** (`base_evaluator.compare` + `__revert_known_errors`).

**Span-level (`SpanEvaluator`, recommended):** matches **spans** by **IoU (Intersection over
Union)** with a configurable threshold. **[A]**
- Defaults: `iou_threshold = 0.9`, `char_based = True`. **[A]** (docstring misleadingly says
  "default 0.5" but the actual default is 0.9 — verify per version.)
- `calculate_iou(span1, span2, ignore_entity_type=True, …)` — character-level overlap by default.
- Matching: for each annotation span, `_find_best_match` picks the highest-IoU unmatched
  prediction (type ignored for the IoU search), then a **7-scenario taxonomy** classifies it:
  - 1 overlap, IoU≥thr, same type → **TP**;
  - 1 overlap, IoU≥thr, diff type → **Wrong Entity**;
  - 1 overlap, IoU<thr → low-overlap (partial) error;
  - multiple overlaps → cumulative IoU per type (scenarios 6A/6B same-type, 7A/7B diff-type);
  - annotation with no overlap → **FN** (a miss = a leak); prediction with no overlap → **FP**.
  **[A]** (`_match_predictions_with_annotations`, `_compare_single_overlaps`,
  `_compare_multiple_overlaps`, `_handle_unmatched_predictions`).
- `_merge_adjacent_spans` merges adjacent same-type spans before matching (handles tokenizer
  fragmentation); skip-words/punct normalized out of token boundaries. **[A]**

**Why span-level matters for honest recall:** token-level can *inflate* recall (a multi-token
name where you catch 3/4 tokens still scores partial TP per token). Span-level with high IoU asks
"did you catch the *whole entity*?" — much closer to the privacy question ("did any PII char
leak?"). For a privacy product, also consider reporting at **low IoU (e.g. 0.5) for recall** —
*any* overlap means the PII was at least partially caught/redacted — while reporting precision at
high IoU. Run the evaluator twice with different `iou_threshold` to separate "found it at all"
(recall-relevant) from "found it cleanly" (precision-relevant). **[D]**

### 5.3 Span-mismatch is not always an error

Docs note `<Southern France>` vs `Southern <France>` — boundary disagreements aren't necessarily
mistakes; the IoU threshold + skip-word normalization absorb these. Don't hand-count exact-match;
let the IoU/skip-word logic handle benign boundary noise. **[B][A]**

### 5.4 Running an eval (the harness shape) **[A][B]**

```python
from presidio_evaluator.evaluation import SpanEvaluator
from presidio_evaluator.models import PresidioAnalyzerWrapper
from presidio_evaluator import InputSample

samples = InputSample.read_dataset_json("data/synth_dataset_v2.json")   # ground truth
model   = PresidioAnalyzerWrapper(analyzer_engine=my_analyzer, entities_to_keep=ENTITIES)
ev      = SpanEvaluator(model=model, entities_to_keep=ENTITIES,
                        iou_threshold=0.5, char_based=True)   # 0.5 for recall-honest
results = ev.evaluate_all(samples)
score   = ev.calculate_score(results, beta=2.0)
print(score.pii_recall, score.pii_precision, score.pii_f)
print(score.entity_recall_dict)          # per-entity recall → find the leaks
# score.model_errors → list of FN/FP/WrongEntity ModelError objects for error analysis
```
- `score_model()` in `scorers.py` is the canned E2E pipeline (prints precision/recall/Fβ, per-
  entity dicts, and FN/FP/other error dumps when `verbose=True`). **[A]**
- `model_error.py` gives **per-span error objects** (`ErrorType.FN/FP/WrongEntity`, the token,
  full_text, metadata) — this is how you do **FN error analysis**: dump every FN, cluster by
  entity type, and that list *is* your recall-improvement backlog. **[A]**

### 5.5 Building the eval dataset

- presidio-research ships a **synthetic data generator** (Faker-style templates → labelled
  spans) so you can mint labelled PII at scale without using real PII; `InputSample` /
  `read_dataset_json` is the canonical format (full_text + spans + tokens + tags). **[A][B]**
- Use `Evaluator.align_entity_types(samples, entities_mapping)` to map your label set ↔ the
  detector's labels before scoring (and `generic_entities` so PII/ID predictions aren't
  penalized). **[A]**
- **Other tools:** Gretel has open PII/NER eval datasets + synthetic generators; the hybrid
  paper (2510.07551) and clinical i2b2 2014 test set are external benchmarks worth running for
  cross-check. **[C][E]**

### 5.6 How to report recall honestly (anti-gaming checklist)

1. Report **per-entity recall**, not just micro — micro hides a single catastrophically-missed
   type (e.g. SNILS at 40% recall buried under emails at 99%). **[A]**
2. Report **F2 (β=2) + raw recall**, the framework default; never headline F1 for a privacy tool. **[A][B]**
3. Run **span-level** SpanEvaluator, and report **two IoU points** (low for "any overlap caught",
   high for "clean catch"). **[A][D]**
4. **Dump and read every FN** (`model_errors`) — residual FN is the privacy risk; it's the
   roadmap. **[A]**
5. Eval on **adversarial/realistic** text (typos, mixed scripts, formatting noise), not just
   clean templates — clean synthetic over-states recall. **[C]** (2510.07551 hybrid multilingual)
6. Keep a **human-in-the-loop / fail-safe** acknowledgment: SOTA (LOGICAL 2% FN, Philter 99.92%
   recall) still backstops; "minimize residual FN," don't claim zero. **[C]**

---

## 6. Concrete recommendation (the stack)

- **Stage 1 (recall union, low thresholds, parallel):** regex+checksum for structured IDs ∪
  spaCy/transformer NER for names/orgs/locations ∪ GLiNER (`gliner_multi_pii-v1`, CPU,
  zero-shot) ∪ deny-lists. Take the union of spans. Target Stage-1 recall ≥ 0.97.
- **Stage 2 (recall-safe precision recovery):** checksum validation → context scoring
  (`LemmaContextAwareEnhancer`) → conflict dedupe (`remove_duplicates`) → optional local
  small-LLM verifier (llama.cpp, 1–3B, Q4) **only on middle-confidence spans (≈0.3–0.6)**,
  prompted as a yes/no PII judge with context. Drop a span only when confidently non-PII.
- **Stage 3 (fail-safe):** confident PII → reversible tokenization; uncertain → destructive
  redaction (block-on-uncertain). Never silently pass an uncertain span.
- **Local everywhere:** every model (NER, GLiNER, verifier LLM) runs on-prem. The only place a
  cloud LLM is *acceptable* is **offline training-data labelling** (LLM-in-the-loop), never the
  inference hot path.
- **Eval:** `SpanEvaluator`, β=2, per-entity recall dicts, two IoU thresholds, FN dump as the
  improvement backlog, synthetic + adversarial + i2b2 cross-check. Headline metric = **recall
  and F2**, target 95–99% with explicit residual-FN reporting and a human/fail-safe backstop.

---

## 7. Sources (primary first)

**Source code [A]** (microsoft/presidio-research, master, fetched June 2026):
- `presidio_evaluator/evaluation/base_evaluator.py` (precision/recall/f_beta, compare, generic-entity & skip-word reverts)
- `presidio_evaluator/evaluation/span_evaluator.py` (IoU matching, iou_threshold=0.9 / char_based=True default, 7-scenario taxonomy)
- `presidio_evaluator/evaluation/token_evaluator.py` (deprecated TokenEvaluator + `Evaluator` alias w/ DeprecationWarning)
- `presidio_evaluator/evaluation/scorers.py` (`score_model` beta=2.5, `score_presidio_recognizer`)
- `presidio_evaluator/evaluation/model_error.py` (ErrorType FN/FP/WrongEntity, per-span errors)
- (cross-ref) dd-notes-2-presidio.md — analyzer pipeline, `remove_duplicates`, context enhancer **[A]**

**Papers [C]:**
- *Towards Contextual Sensitive Data Detection*, arXiv 2512.04120 — two-stage high-recall→context-precision; Qwen3-14B 0.73P/0.94R
- *An Evaluation Study of Hybrid Methods for Multilingual PII Detection*, arXiv 2510.07551 — union maximizes recall at cost of precision
- *LLMs-in-the-Loop Part 2: Expert Small AI Models…*, arXiv 2412.10918 — local deberta-v3-small+regex, F1-micro 0.966 EN, macro 0.931 vs GPT-4o 0.5775; no LLM at inference (on-prem privacy)
- *LOGICAL (Local Obfuscation by GLINER)*, arXiv 2510.19346 — fine-tuned GLiNER, F1 0.980, 95% docs fully sanitised, 2% FN, runs on laptop CPU, human-in-the-loop
- *Philter*, npj Digital Medicine s41746-020-0258-y — 99.92% recall, F2 94.77% on i2b2 2014
- *2014 i2b2/UTHealth shared task overview*, PMC4989908 — mean F1 0.872, max 0.964
- *GLiNER*, arXiv 2311.08526 — zero-shot generalist NER
- *GLiNER2*, arXiv 2507.18546 — ~130–208 ms CPU latency, ~2.6× vs GPT-4o

**Docs [B]:**
- Presidio "Using GLiNER as an external PII model" — GLiNERRecognizer, gliner_multi_pii-v1, cpu/onnx params
- Presidio "PII detection evaluation" — β=2 recall-weighting guidance, span-mismatch note
- knowledgator/gliner-pii-base-v1.0 model card — P79.28/R82.78/F1 80.99, Apache-2.0
- GuardrailsPII detection thresholds (DeepWiki) — entity-specific defaults (EMAIL 1.0, ML 0.5)

**Secondary [E]:**
- anonym.legal "The False Positive Tax" — Presidio 22.7% precision (Alvaro 2024), checksum-maxed-score problem
- llama.cpp / quantization guides — TinyLlama 1.1B Q4_K_M <1GB, ~95% quality at 25% memory
