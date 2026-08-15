# Deep-Dive: Fixing Pseudex's RU PII Detection (names, addresses, collisions, recall)

**Date:** 2026-06-07 · **Method:** /deep-dive — 4 parallel primary-source excavations (RU NER / address / disambiguation / architecture+eval), lead-synthesized with adversarial analysis.
**Raw notes:** `dd2-notes-A-ru-ner.md`, `dd2-notes-B-ru-address.md`, `dd2-notes-C-disambiguation.md`, `dd2-notes-D-architecture-eval.md`.
**Grades:** [A] read in source/benchmarked · [B] single primary · [C] asserted by primary · [D] inference.

---

## TL;DR — the answer

1. **The name problem is a DATA problem, not a MODEL problem.** Every RU NER (Slovnet, spaCy-lg, DeepPavlov, ruBERT) scores ~0.95 PER F1 *on news* but fails the same way on field text (Latin, diminutives, lowercase, oblique) because all are trained on capitalized canonical text — distribution shift, not capacity. **Swapping the model will not fix our failures.** The fix is a **name gazetteer + lemmatization + case-insensitive matching**.
2. **GLiNER is the WRONG primary for Russian** — gliner-multi RU F1 = **33.3** (Multi-CoNER) and *none* of the production GLiNER-PII models support RU. (My going-in hypothesis was wrong.) Keep it only as a low-score *union* member for Latin-script names.
3. **Presidio's context-awareness is boost-only — there is NO deny/negative-context code path.** That is exactly why naive Presidio precision is ~22.7%. The hard-negative fix (track/order/sum) must be **built**: a char-window deny + trigger + checksum layer (~30 lines, zero deps). Every big tool (Google DLP, AWS Macie, Nightfall) ships signed context + exclusion; Presidio doesn't.
4. **Recall is a union; precision is a second stage.** Architecture = Stage 1 recall-union (catch-if-any, low thresholds) → Stage 2 precision recovery (checksum → deny/trigger context → optional local LLM judge on middle-confidence spans only) → Stage 3 fail-safe (confident→tokenize, uncertain→redact, never pass). Quantified: a union is high-recall/low-precision; a context/reflection 2nd pass took a model to **0.73P @ 0.94R**.
5. **Fine-tuned small LOCAL NER beats cloud LLMs** (DeBERTa-v3-small+regex F1 0.966 vs GPT-4o 0.931) — so a cloud LLM belongs only in *offline labelling*, never the hot path. Confirms our local-only constraint is also the *better* engineering choice.

---

## Problem A — Russian ФИО detection

**SOTA reality** (recall/F1 with conditions):
- `spaCy ru_core_news_lg` — PER **F1 0.958 / P 0.961 / R 0.956** in-domain news, MIT [A]. `ru_core_news_sm` (14 MB) ≈ 0.954 PER — great CPU pick [A].
- `Gherman/bert-base-NER-Russian` — separate FIRST/LAST/MIDDLE labels, F1 0.988 but small/synthetic eval → optimistic [A]. `DeepPavlov/ner_rus_bert` — top-tier, heaviest [B].
- Our **Slovnet ≈ 0.97–0.99 PER on synthetic news [A]** — already near the ceiling. **Swapping models buys ~nothing on our failures.**
- GLiNER-multi RU zero-shot F1 **33.3** (Multi-CoNER, NAACL 2024 Table 3) [A]; gliner_multi_pii-v1 = 6 EU langs, no RU; knowledgator gliner-pii = English [A].

**Why they all miss Latin/diminutive/lowercase/oblique:** trained on capitalized canonical news → distribution shift, not capacity [A/D-inference].

**The fix = gazetteer add-on (the real lever):**
- `kenoma/RussianNameVariants` — maps diminutives AND Latin translits → base (`Леночка/Lena→Елена`) — fixes "света/Маша" and "Ivan Petrov" in one table [A].
- `datacoon/russiannames` — 32k names + gender/validity → false-positive control, BSD-3 [A].
- Expand to all 6 cases via **pytrovich**/**pymorphy3** lemmatize-then-lookup; **case-insensitive** match for lowercase; regex `PatternRecognizer` for initials (`Сидоров И.И.`).
- Over-tag control: gender/validity check + context words + require NER-agreement or ≥2 name parts for high confidence.

**Integration:** spaCy `ru_core_news_lg`/`_sm` as Presidio NlpEngine (PER→PERSON) + custom gazetteer `EntityRecognizer` via `registry.add_recognizer()` + optional low-score GLiNERRecognizer for Latin. CPU: spaCy tens of ms; gazetteer sub-ms [A].

---

## Problem B — Russian free-form addresses

**Honest headline: no local tool "solves" marker-less RU addresses; use a layered detector** [A across notes].
- **Natasha AddrExtractor (Yargy)** — matches address *parts* independently (улица/дом/корп/кв/мкр…), each gated by its marker, merges consecutive → high recall on **marker-bearing** free-form ("мкр Северный д12 кв 8", reordered forms OK) [A]. But top-level STREET rule **requires** the marker → truly marker-less "Ленина 5" falls to `UNPARSED_*` → the **precision hole** (matches "Windows 10"). MIT, tiny, CPU [A].
- **pymorphy3 fix (real & simple):** natasha pins pymorphy2 but the working fix is a 3-line `sys.modules["pymorphy2"]=pymorphy3` alias before import — verified in production (`evenikkal/hhanalyst`); pymorphy3 fixed pkg_resources, MIT, Py3.9–3.14 [A]. (Our 3.12 `pkg_resources` error → use this alias and avoid pymorphy2 entirely.)
- **libpostal/pypostal** — wrong tool (parser, not free-text detector; explicit non-goal), 1.8 GB; use only as downstream normalizer [A].
- **GLiNER addr** (gliner_multi_pii-v1, Apache-2.0, ONNX/CPU, first-class Presidio recognizer) — only candidate targeting marker-less forms semantically, best recall booster, but RU recall **unbenchmarked → must validate** [B].
- **DaData/ФИАС/ГАР** = normalization, not detection; offline only via self-hosted ГАР dump [B].

**Recommendation:** marker-regex (have) ∪ AddrExtractor+pymorphy3 ∪ GLiNER(validated), union for recall; **precision via app-code gates** — require ≥1 typed part or ≥2 parts, drop bare `UNPARSED_*`, stoplist ("и т.д.", "5 кв.м", version numbers), raise GLiNER threshold. Signal: real RU anonymizer `Winkey86/AnonimisationModule` *skipped* AddrExtractor for NER-LOC+markers — its precision is hard to tame [A].

---

## Problem C — numeric-ID collisions & hard-negative FPs

**Presidio context is boost-only** (`LemmaContextAwareEnhancer`, read verbatim): if a context lemma is in the window (5 before, **0 after**) it does `score += 0.35; score = max(score,0.4); min(…,1.0)` — **no score-lowering path exists**; contradictory neighbours are ignored [A]. So **deny-context must be built**, via the hooks Presidio gives: `validate_result()` (promote on checksum) / `invalidate_result()` (demote→drop), `allow_list`, `global_regex_flags`.

**How the big tools do it** (two-tier signed context + exclusion):
- **Google DLP** — `HotwordRule` char window (`windowBefore/After`) + signed `relativeLikelihoodAdjustment` (negative=suppress) + `ExclusionRule.excludeByHotword` (true deny-context) [A].
- **AWS Macie** — positive keyword as *required gate* (`MaximumMatchDistance` default 50) + value `IgnoreWords` [A].
- **Nightfall** — signed Context Rules + Exclusion Rules [A]. **Comprehend** — ML threshold only.
- Research: **RECAP** (arXiv 2510.07551) — multi-label disambiguation + one-sentence contextual filtering → +28.57% F1 [C].

**Algorithm to adopt (checksum → deny → trigger, precision-first), ~30 lines, zero deps:**
1. **Checksum gate** first (СНИЛС/ИНН/Luhn — already in `ru_pii.py`): pass = strong evidence.
2. **Deny veto:** 14-digit run = postal track → hard-drop; if a deny lemma (`трек/заказ/артикул/сумма/№/руб/чек`) within ~40 chars → drop.
3. **Trigger gate** for checksum-less colliders: bare phone kept only if PHONE trigger (`тел/моб/+7`) in-window OR strict shape; 16-digit Luhn → CARD vs ОМС by `карт`/`полис`.
4. Assemble signed score; deny→0.
- Open tie-break: trigger AND deny co-occur → deterministic "nearest-word-wins" or privacy-conservative keep; tune on `research/realistic-ru-queries.md`.

---

## Problem D — defense-in-depth architecture + recall-first eval

**The asymmetry:** FN leaks PII (breach); FP over-redacts (utility cost). Recall = privacy SLA; precision = utility budget.

**3-stage stack:**
- **Stage 1 — recall union (catch-if-any):** regex+checksum ∪ NER ∪ GLiNER ∪ deny-lists in parallel, *low* thresholds, take the **union**. Recall ≈ `1 − Π(1−recallᵢ)` for diverse error profiles — the biggest lever [C/D].
- **Stage 2 — recall-safe precision recovery:** checksum → context (deny/trigger from Problem C) → dedupe → **optional local small LLM** (llama.cpp 1–3B Q4) as a yes/no judge **only on middle-confidence (~0.3–0.6) spans**; drop only if confidently non-PII.
- **Stage 3 — fail-safe:** confident→reversible tokenize; uncertain→destructive redact; never silently pass.

**Tradeoff, quantified:** union → high recall, low precision (**Presidio measured ~22.7% precision** [B]); thresholds can't fix it (checksum detectors score max regardless of context) → precision needs a separate stage. A context/reflection 2nd pass reached **0.73P @ 0.94R** [C]. Recall ceilings: Philter 99.92% recall (i2b2) [C]; fine-tuned GLiNER F1 0.980, 2% residual FN [C]; **local DeBERTa-v3-small+regex F1 0.966 > GPT-4o 0.931** [C] → local beats cloud; cloud LLM only offline.

**Eval (presidio-research):** use **`SpanEvaluator`** (token `Evaluator` deprecated) — IoU span match (`iou_threshold` default 0.9, `char_based`), 7-scenario taxonomy; unmatched annotation = FN, unmatched prediction = FP. Framework is **F2-weighted** (β=2) by design. Practices: report **per-entity recall** (micro hides a catastrophically-missed type), headline **F2 + raw recall**, run **two IoU thresholds** (≈0.5 recall-honest + high precision), **dump every FN** as the backlog [A].

---

## Recommended upgrade for Pseudex (synthesis)

| Layer | Action | Source-of-gold |
|---|---|---|
| **Names** | spaCy `ru_core_news_lg` NlpEngine **+ gazetteer recognizer** (RussianNameVariants diminutives/translit + russiannames validity) + pymorphy3 lemmatize + case-insensitive + initials regex | dd2-A |
| **Addresses** | marker-regex (have) + **AddrExtractor via pymorphy3 alias** + app-gates (≥1 typed part, drop UNPARSED, stoplist); GLiNER addr only if RU-validated | dd2-B |
| **Disambiguation** | build **deny+trigger+checksum** char-window layer; 14-digit→drop; phone needs trigger/shape; 16-Luhn→card/ОМС by карт/полис | dd2-C |
| **Architecture** | 3-stage: recall-union → precision recovery → fail-safe; local LLM judge on mid-confidence later | dd2-D |
| **Eval** | switch to presidio-research **SpanEvaluator**, F2 + per-entity recall, two IoU, dump FNs | dd2-D |

---

## Phase 2 — critical analysis (where this breaks / what I got wrong)
- **My GLiNER hypothesis was wrong** [A refutation]: GLiNER-multi RU F1 33.3 and no RU PII variant. Lesson: don't assume the trendy zero-shot model transfers cross-lingual; the Multi-CoNER number is the refutation.
- **The "swap to a bigger model" instinct is a trap.** All RU NERs are ~0.95 on news; our failures are *out-of-distribution* (Latin/lowercase/diminutive). A bigger in-domain model = same blind spots. This is the load-bearing insight; if it's wrong (i.e., a model trained on noisy field text exists), the plan changes — but no such RU model surfaced.
- **Precision is not just UX for us.** Over-masking a number the model must reason over (e.g., an order # it should echo) can corrupt task logic, not merely "redact too much." So Stage-2 precision recovery is functionally required, not cosmetic. (Counter: in our tokenizing proxy, over-masked non-PII still round-trips, so harm is bounded — but vault pollution + reasoning loss remain.)
- **The 22.7% Presidio precision figure** is [B] (one practitioner measurement) — directionally trustworthy (union math guarantees precision drops) but not a universal constant; our checksum-gating already lifts structured-ID precision to ~100%, so our real precision pain is concentrated in NAME/LOC, matching our own eval.
- **Local-LLM verifier is attractive but unproven on our hot path** — latency of a 1–3B Q4 per middle-confidence span could blow the gateway budget; treat as Stage-2 *optional*, benchmark before adopting.

## Phase 3 — insights (0.01% pass)
1. **Diversity > strength.** Union recall `1−Π(1−rᵢ)` means three *mediocre, error-diverse* detectors (regex, NER, gazetteer) beat one strong model. Our cheapest path to high recall is *adding* members (gazetteer, GLiNER) at low thresholds, not upgrading one.
2. **Presidio is a half-product for our use case** — it gives recall (recognizers) and boost-context but *no deny-context*; the precision half (the thing that makes it shippable) is ours to build. Knowing this saves weeks of expecting `context=` to suppress FPs.
3. **The gazetteer is the single highest-ROI artifact** — one CSV (RussianNameVariants) simultaneously fixes diminutives + Latin translit, the two failure modes no RU NER handles. Unfork-able-ish data moat aligned with our 152-ФЗ/RU edge.
4. **Eval choice changes the story:** reporting F1 (what we did) hides recall pain; switching to F2 + per-entity recall + FN-dump turns eval into a prioritized backlog. Our "91% recall" headline should become "per-entity recall, F2, at IoU 0.5 and 0.9".

## Open questions / uncertainty ledger
- **[validate] GLiNER RU recall on addresses & Latin names** — unbenchmarked; test before adding to the union.
- **[validate] gazetteer FP rate** — 32k-name dictionary will tag common-word names (e.g., "Вера", "Любовь") → need validity/context gating; measure on realistic set.
- **[benchmark] local-LLM-verifier latency** on the per-message hot path (1–3B Q4 CPU) — unknown; may be Stage-2-offline only.
- **[open] tie-break** when trigger AND deny co-occur — deterministic rule vs LLM (RECAP) — tune on realistic data.
- **[B-only] Presidio 22.7% precision** and the **0.73P@0.94R** reflection number — single-source; treat as directional.

## Sources (primary, read)
GLiNER: arXiv 2311.08526 + Multi-CoNER NAACL-2024; HF urchade/gliner, knowledgator/gliner_multi_pii-v1. spaCy ru_core_news_lg/sm model cards; DeepPavlov; Gherman/bert-base-NER-Russian. Gazetteers: github kenoma/RussianNameVariants, datacoon/russiannames; pytrovich; pymorphy3. natasha/yargy source (AddrExtractor), natasha issue #138, evenikkal/hhanalyst (pymorphy3 alias), Winkey86/AnonimisationModule; libpostal. Presidio source: `lemma_context_aware_enhancer.py`, `PatternRecognizer.validate/invalidate_result`; Google DLP HotwordRule/ExclusionRule docs; AWS Macie custom-identifier docs; Nightfall context/exclusion docs; arXiv 2510.07551 (RECAP). microsoft/presidio-research `SpanEvaluator`; Philter (i2b2) paper. Per-claim URLs/paths in `dd2-notes-A..D`.
