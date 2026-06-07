# DD2 Notes C — Numeric-ID Disambiguation & Hard-Negative FP Suppression (source-grounded)

Scope (narrow): how to DISAMBIGUATE ambiguous numeric tokens by context and SUPPRESS
hard-negative false positives, so we don't mask track/order/sum numbers but still catch
real PII. NOT in scope: name NER, address extraction, eval harness, local-LLM (other agents).

The collision reality this note must solve (RU domain):
- 10 digits = phone OR order# OR ИНН-юрлицо OR лицевой счёт
- 16 digits = bank card OR полис ОМС
- 11 digits = СНИЛС-no-dash OR phone (e.g. 8 + 10)
- 14 digits = почтовый трек (NEVER PII) — a hard negative
- 12 digits = ИНН-физлицо (checksum) OR random order#
- short (2–4 digits) = CVV/age/sum/№ — high-FP

Evidence grades: **[A]** = read in source · **[B]** = official docs · **[C]** = asserted ·
**[D]** = inference. Per-claim URL/file-path inline.

Companion notes already in repo: `dd-notes-2-presidio.md` (Presidio core architecture),
`ru-pii-dataset-and-detectors.md`. Prototype detector: `prototype/obscura/ru_pii.py`
(regex + СНИЛС/ИНН/Luhn checksums, NO context disambiguation yet).

---

## 1. Microsoft Presidio context enhancement — how the BOOST works, and the deny gap

### 1.1 Where it runs in the pipeline
`AnalyzerEngine.analyze()` calls `_enhance_using_context(text, results, nlp_artifacts,
recognizers, context)` **after** all recognizers emit raw results and **before**
`remove_duplicates` and `__remove_low_scores`. So context boosting happens, then the
score threshold filter. **[A]**
File: `presidio-analyzer/presidio_analyzer/analyzer_engine.py`
(https://github.com/microsoft/presidio/blob/main/presidio-analyzer/presidio_analyzer/analyzer_engine.py)

### 1.2 The default enhancer: `LemmaContextAwareEnhancer`
File: `presidio-analyzer/presidio_analyzer/context_aware_enhancers/lemma_context_aware_enhancer.py`
(https://github.com/microsoft/presidio/blob/main/presidio-analyzer/presidio_analyzer/context_aware_enhancers/lemma_context_aware_enhancer.py) **[A]**

Constructor defaults (read in source) **[A]**:
- `context_similarity_factor: float = 0.35`  — the additive boost
- `min_score_with_context_similarity: float = 0.4` — a floor, NOT a threshold
- `context_prefix_count: int = 5`  — words BEFORE the entity to scan
- `context_suffix_count: int = 0`  — words AFTER (default: zero! suffix context off by default)

Base class constants (`context_aware_enhancer.py`): `MIN_SCORE = 0`, `MAX_SCORE = 1.0`. **[A]**
(https://github.com/microsoft/presidio/blob/main/presidio-analyzer/presidio_analyzer/context_aware_enhancers/context_aware_enhancer.py)

### 1.3 The EXACT boost arithmetic (this is the whole mechanism)
When a supportive context word is found near the match: **[A]**
```python
result.score += self.context_similarity_factor                       # +0.35
result.score = max(result.score, self.min_score_with_context_similarity)  # floor at 0.4
result.score = min(result.score, ContextAwareEnhancer.MAX_SCORE)     # cap at 1.0
```
Interaction with `supported_score` / threshold:
- A recognizer's base `Pattern.score` (e.g. 0.3 for a weak phone regex) gets `+0.35` →
  0.65 when a context word ("тел", "телефон") is present in the window.
- The `max(..., min_score_with_context_similarity)` is a **floor**: even if the base
  score was tiny, a context hit pulls it up to at least 0.4. This means a low-confidence
  pattern + context word ≈ guaranteed to survive a default threshold.
- Then `__remove_low_scores` drops anything `< score_threshold`
  (`score_threshold` arg → else `self.default_score_threshold`, default 0). **[A]**

> **Net effect: context only ever RAISES a score (or floors it). There is no path that
> lowers a score.** Unsupportive / contradictory surrounding words are *ignored*, never
> penalized. **[A]**

### 1.4 The reusable window-extraction algorithm (the genuinely useful part) **[A]**
This is the trigger-word-window mechanic we want, already implemented:

`_extract_surrounding_words(nlp_artifacts, word, start)`:
1. `token_index = _find_index_of_match_token(word, start, tokens, tokens_indices)` —
   maps the entity's char `start` to a token index. Loop: `for i, token in
   enumerate(tokens): if tokens_indices[i] == start or start < tokens_indices[i] +
   len(token)`. **[A]**
2. `backward_context = _add_n_words_backward(token_index, context_prefix_count, lemmas,
   lemmatized_keywords)`
3. `forward_context  = _add_n_words_forward(token_index, context_suffix_count, lemmas,
   lemmatized_keywords)`
4. concatenate → `context_list`.

`_add_n_words` core loop **[A]**:
```python
while 0 <= i < len(lemmas) and remaining > 0:
    lower_lemma = lemmas[i].lower()
    if lower_lemma in lemmatized_filtered_keywords:   # only collect keyword-ish lemmas
        context_words.append(lower_lemma)
        remaining -= 1
    i = i - 1 if is_backward else i + 1
```
> Subtlety **[A]/[D]**: the window is counted in *keyword lemmas*, not raw tokens — it
> walks until it has collected `n` lemmas that appear in the recognizers' combined context
> vocabulary. It does NOT explicitly skip stopwords/punctuation; it just only counts
> lemmas present in the keyword set. Window is **lemma-based**, so "телефоны"→"телефон"
> matches via spaCy lemmatization (needs a lemmatizing NLP engine for the RU model).

`_find_supportive_word_in_context(context_list, recognizer_context_words)` — two modes **[A]**:
- substring (default): `predefined_context_word.lower() in keyword.lower()`
- whole-word: `predefined_context_word.lower() == keyword.lower()`

### 1.5 VERDICT on Presidio for our need
- **Positive context (BOOST): supported out of the box.** Put `context=["тел","телефон",
  "моб","whatsapp"]` on the phone `PatternRecognizer`; a hit adds +0.35 / floors to 0.4. **[A]**
- **Negative / deny / suppress context: NOT supported. Must be built.** No code path
  reduces a score; `LemmaContextAwareEnhancer` is boost-only; the abstract
  `ContextAwareEnhancer.enhance_using_context` could be subclassed to do it, but nothing
  ships. **[A]**
- Confirmed by the maintainers' own feature request to add ML/embedding context awareness
  — current state is rule/lemma boost only.
  (https://github.com/microsoft/presidio/issues/1686) **[B]**

### 1.6 Adjacent Presidio knobs for FP suppression (all [A], analyzer_engine.py)
- **`allow_list`** + **`allow_list_match`** (`"exact"` default, or `"regex"`) +
  **`regex_flags`** (`re.DOTALL|re.MULTILINE|re.IGNORECASE`). In `_remove_allow_list`:
  regex mode does `re.compile("|".join(allow_list), flags).search(word, timeout=...)`;
  exact mode does `word not in allow_list`. This drops a *whole matched value* if it is
  allow-listed. Useful for known non-PII constants but NOT for context-conditioned
  suppression (it ignores neighbours). **[A]**
- **`PatternRecognizer` `global_regex_flags`** (default `re.DOTALL|re.MULTILINE|
  re.IGNORECASE`) applied to every `Pattern` regex. **[A]** (`pattern_recognizer.py`)
- **`PatternRecognizer.invalidate_result()`** override → demotes a match to `MIN_SCORE`
  (dropped). THIS is the built-in hook to implement deny-context: subclass the recognizer,
  inspect neighbours in `invalidate_result`/`validate_result`, kill or keep. **[A]/[D]**
- **`validate_result()`** → promote a checksum-verified match to MAX_SCORE (already how
  CreditCard/Luhn works). **[A]**
- `default_score_threshold` / `score_threshold` arg gates the final cut. **[A]**

> **Practical Presidio recipe for us [D]:** implement deny-context by subclassing the
> numeric `PatternRecognizer` and overriding `invalidate_result(self, pattern_text)` /
> using `analyze`'s access to surrounding text to: (a) run checksum, (b) scan a char
> window for trigger vs deny words, (c) return invalidation. Presidio gives us the regex
> engine, the offset bookkeeping, `validate/invalidate` hooks, `allow_list`, and positive
> context boost; we supply the deny-context scan.

---

## 2. How the big commercial tools disambiguate (hotword / likelihood / exclusion)

### 2.1 Google Cloud DLP / Sensitive Data Protection — the richest model (has BOTH directions)
Docs: https://docs.cloud.google.com/sensitive-data-protection/docs/creating-custom-infotypes-rules
and https://cloud.google.com/sensitive-data-protection/docs/creating-custom-infotypes-likelihood **[B]**

DLP findings carry a **likelihood** enum (VERY_UNLIKELY → UNLIKELY → POSSIBLE → LIKELY →
VERY_LIKELY). Two rule families adjust it:

**(a) HotwordRule — boost OR suppress by proximity** **[B]**
```json
{ "hotwordRule": {
    "hotwordRegex": { "pattern": "тел|телефон|моб" },
    "proximity": { "windowBefore": 50, "windowAfter": 50 },   // CHARACTERS, not tokens
    "likelihoodAdjustment": { "relativeLikelihoodAdjustment": 2 }   // can be NEGATIVE
}}
```
- `proximity.windowBefore` / `windowAfter` = **character counts** measured from the
  finding's start (before) and end (after). For a finding at 100–110, windowBefore:50 →
  scan 50–100, windowAfter:50 → scan 110–160. **[B]**
- `likelihoodAdjustment` = either `fixedLikelihood` (set absolutely) or
  `relativeLikelihoodAdjustment` (step up/down; **positive boosts, NEGATIVE suppresses**).
  Clamped to [VERY_UNLIKELY, VERY_LIKELY]. **[B]**
- This is exactly trigger-word-window + signed adjustment — the model we want.

**(b) ExclusionRule — hard suppression** **[B]**
- `matchingType`: `MATCHING_TYPE_FULL_MATCH` / `PARTIAL_MATCH` / `INVERSE_MATCH`.
- rule types: `dictionary` (word list), `regex`, `excludeInfoTypes` (drop a finding that
  overlaps another infoType), and crucially **`excludeByHotword`**:
```json
{ "exclusionRule": {
    "excludeByHotword": {
      "hotwordRegex": { "pattern": "трек|заказ|артикул|накладн" },
      "proximity": { "windowBefore": 30, "windowAfter": 30 }
}}}
```
> **`excludeByHotword` = a true DENY-CONTEXT primitive: if the deny word is within the
> char window of the finding, drop the finding entirely.** This is the canonical
> commercial pattern for "don't mask the number if 'трек'/'заказ' is next to it." **[B]**
- `MATCHING_TYPE_INVERSE_MATCH` is also powerful: keep ONLY if the surrounding/the value
  does NOT match — e.g. exclude all phone candidates whose context lacks a phone hotword. **[B]**

### 2.2 AWS Macie — Custom Data Identifier: required keyword proximity + ignore words
Docs: https://docs.aws.amazon.com/macie/latest/user/cdis-options.html and
https://docs.aws.amazon.com/macie/latest/APIReference/custom-data-identifiers.html **[B]**

A Macie CDI = `Regex` + optional `Keywords` + `MaximumMatchDistance` + `IgnoreWords`:
- **`Keywords`** (≤50, 3–90 chars, case-INsensitive): "one of which must **precede** and
  be in proximity of the regex match" — i.e. the regex match is **only** reported when a
  keyword is nearby. This is *positive context as a hard GATE*, not a soft boost. **[B]**
- **`MaximumMatchDistance`** (1–300 chars, default 50): max chars between the **end of a
  keyword** and the **end of the regex match**. The proximity window. **[B]**
- **`IgnoreWords`** (1–10, 4–90 chars, case-SENSITIVE): if the regex match *contains* one
  of these strings, the match is dropped. A value-level deny list (not context). **[B]**
- Macie's `Regex` is PCRE-subset and **explicitly forbids look-behind/look-ahead** — so
  proximity must be expressed via the keyword+distance mechanism, not regex assertions. **[B]**

> **Macie's lesson: for high-collision numeric types, make the trigger word REQUIRED
> (gate), not just a booster.** A bare 10-digit run reports as phone *only if* "тел" is
> within N chars. This is stricter (higher precision, lower recall) than Presidio's boost. **[B]**

### 2.3 Nightfall AI — Context Rules (signed) + Exclusion Rules + confidence ladder
Docs: https://help.nightfall.ai/detection_platform/faq/context_rules ,
https://help.nightfall.ai/detection_platform/faq/confidence_levels ,
https://help.nightfall.ai/detection_platform/faq/reduce_false_positives **[B]**
- Confidence ladder: POSSIBLE → LIKELY → VERY_LIKELY. "POSSIBLE is triggered by the token
  alone, without context; LIKELY and VERY_LIKELY take context into account." A custom
  regex defaults to LIKELY, adjusted from there by context. **[B]**
- **Context Rules**: regex hot-word pattern + char window + direction (**before / after /
  both**) → **up-weight OR down-weight** the confidence level. Signed, like DLP. **[B]**
- **Exclusion Rules**: disqualify tokens entirely (vs Context which only re-weights). **[B]**
- Explicit framing: "Context Rules increase/decrease confidence; Exclusion Rules
  disqualify items from detection." Same two-tier design as DLP (adjust vs exclude). **[B]**

### 2.4 AWS Comprehend (DetectPiiEntities) — ML model + confidence threshold only
Docs: https://docs.aws.amazon.com/comprehend/latest/dg/realtime-pii-api.html ,
https://docs.aws.amazon.com/comprehend/latest/APIReference/API_DetectPiiEntities.html **[B]**
- Pure ML: each entity gets type, offsets, and a `Score` (0–1). Disambiguation is implicit
  in the model; the only knob is the client-side confidence **threshold**. No declarative
  hotword/exclusion/proximity rules. **[B]**
- Implication: Comprehend "disambiguates" phone-vs-order only as well as its training data
  did; you cannot inject "трек"/"заказ" deny rules. Contrast with DLP/Macie/Nightfall which
  are rule-tunable. **[B]/[D]**

### 2.5 Skyflow — proprietary; context is governance, not numeric disambiguation
Docs: https://docs.skyflow.com/docs/fundamentals/patterns/pii , product pages. **[B]**
- Skyflow does detect+tokenize PII (structured + unstructured) and markets "context-aware"
  protection — but "context-aware" there means **identity/purpose/policy-aware access
  governance** (which agent, what purpose, which regulation), NOT public docs on numeric
  collision resolution. No documented hotword/proximity disambiguation primitive at the
  detector level. Treat as a black box for our specific question. **[B]/[D]**

### 2.6 Cross-tool synthesis (the common pattern)
Every tunable tool converges on the SAME two-tier design:
1. **Re-weight tier (soft):** hotword within a proximity window → ±adjust a confidence
   score/likelihood. (DLP HotwordRule, Nightfall Context Rule, Presidio boost [boost-only].)
2. **Exclude/gate tier (hard):** drop or require, regardless of score. (DLP
   ExclusionRule/`excludeByHotword`, Macie required-Keyword + IgnoreWords, Presidio
   allow_list + invalidate_result.)
Proximity is measured in **characters** (DLP, Macie, Nightfall) — simpler and language-
agnostic than Presidio's lemma-token window (which needs a lemmatizer). **[B]/[D]**

---

## 3. Academic grounding — RECAP & checksum/context combination

### 3.1 RECAP: multi-label disambiguation + contextual filtering (most on-point)
"An Evaluation Study of Hybrid Methods for Multilingual PII Detection", arXiv 2510.07551
(https://arxiv.org/html/2510.07551v1 , https://arxiv.org/pdf/2510.07551) **[B]**
Three-phase pipeline directly aimed at numeric collisions:
1. **Phase I — regex/NER baseline** (weighted F1 ≈ 0.511).
2. **Phase II — multi-label disambiguation**: when one char span gets MULTIPLE candidate
   labels (the phone-OR-ID case), pass `(original text, char span, candidate labels)` to an
   LLM with a prompt to "analyze the surrounding context and select the single most
   appropriate label." (+14.48% → 0.585). **[B]**
3. **Phase III — span consolidation + contextual filtering**: for high-FP **short numeric**
   entities (CVV, AGE), extract a **local context window of one sentence before + after**,
   ask the LLM whether the number is "semantically plausible as the predicted PII type";
   **retain only on confirmation** → "drastically reduces false positives that arise from
   numeric coincidences in non-PII settings." (+12.30% → 0.657). **[B]**
- Total +28.57% weighted F1; +82% vs fine-tuned NER, +17% vs zero-shot LLM; +67% recall
  vs NER. The paper explicitly names the exact problems we have: identical digit patterns
  across types, short-numeric FPs, and span overlaps (number embedded in address). **[B]**
> Takeaway: the SOTA recipe = cheap regex/checksum first, then **context-window
> verification** (rules or an LLM) to resolve the multi-label collision and kill numeric
> coincidences. RECAP uses an LLM for the verify step; we can use deny/trigger words +
> checksum for the deterministic cases and reserve an LLM only for the residual ambiguous
> ones (other agent owns the LLM path). **[B]/[D]**

### 3.2 Checksum + context as the precision backbone (commercial practice)
- Checksum is the strongest deterministic disambiguator we already have:
  `prototype/obscura/ru_pii.py` does СНИЛС (mod 101), ИНН (weight vectors, mod 11),
  Luhn (card). **[A]**
- Commercial tools combine checksum-style validators with hotword context exactly as DLP's
  built-in infoTypes do (e.g. credit card built-in uses Luhn AND a card hotword to lift
  likelihood). Presidio's CreditCard recognizer does the same: Luhn in `validate_result`
  → MAX_SCORE. **[A]/[B]**
- The principle: **checksum gives precision on the FORMAT; context resolves WHICH type a
  format-valid number is** (a Luhn-valid 16-digit is card vs ОМС → need "карта"/"полис");
  **and context/deny resolves format-AMBIGUOUS, checksum-less numbers** (10-digit order vs
  phone — no checksum on phone, so only context decides). **[D]**

---

## 4. THE CONCRETE ALGORITHM TO ADOPT (trigger-window + checksum + deny-context)

A deterministic, language-aware disambiguator for a bare numeric token, combining all
sources above. Per candidate numeric span `T` (offsets `start..end`, digits `d = digits(T)`):

### 4.0 Inputs (build once, RU-tuned)
```
TRIGGER  = { TYPE: [lemmas/substrings that ASSERT this type] }
  PHONE : тел, телефон, моб, звон, +7, 8(, whatsapp, ватсап, viber, позвон, номер тел
  CARD  : карт, card, оплат, перевод, списан, visa, mastercard, мир
  SNILS : снилс, пенсионн, страхов свидетельств
  INN   : инн, налогоплат, налогов
  OMS   : полис, омс, медицинск страхов
  PASSPORT: паспорт, серия, выдан
DENY (hard negatives — суppress for ALL numeric PII types when nearby):
  трек, трек-номер, отслежив, накладн, заказ, заказа №, order, артикул, sku,
  сумма, итого, руб, ₽, кол-во, количеств, штрих, ean, инвойс, счёт №, позиция, стр., таб.
WINDOW = 40 chars before + 40 chars after (DLP/Macie-style CHAR window, not tokens)
```

### 4.1 Decision procedure (precision-first ladder)
```
1. CHECKSUM GATE (deterministic types first — highest precision):
   - len(d)==11 and validate_snils(d)  -> candidate SNILS (very high prior)
   - len(d) in (10,12) and validate_inn(d) -> candidate INN
   - len(d)==16 and validate_luhn(d)   -> candidate CARD-or-OMS (Luhn passes both? card; else OMS)
   If a checksum passes AND no DENY word in window -> ACCEPT with high score.
   (Checksum passing is itself strong evidence; deny word can still veto, e.g.
    "сумма заказа 1234567890" that happens to be Luhn/INN-valid — rare but deny wins.)

2. DENY-CONTEXT VETO (the hard-negative suppressor):
   - 14-digit run -> почтовый трек -> NEVER PII -> DROP unconditionally.
   - If any DENY lemma is within WINDOW of the span -> DROP (treat as order/track/sum/№).
     This is DLP excludeByHotword / Macie IgnoreWords applied at context level.

3. TRIGGER-CONTEXT GATE (for checksum-less / format-ambiguous numbers, esp. phone):
   - Phone has NO checksum. A 10/11-digit run is phone ONLY IF a PHONE trigger word is
     within WINDOW (Macie-style REQUIRED keyword) OR it matches a strict phone shape
     (+7/8 prefix, separators). Otherwise it is ambiguous -> DROP (precision) or route
     to LLM verifier (recall; other agent).
   - For 16-digit Luhn-valid: pick CARD if CARD trigger in window, OMS if OMS/полис
     trigger; default CARD (Luhn implies card numbering).

4. SCORE ASSEMBLY (Presidio-compatible, signed like DLP/Nightfall):
   base = format prior (e.g. phone-shape 0.3, bare 10-digit 0.05)
   if checksum_pass: base = max(base, 0.85)
   if trigger_in_window(type): base += 0.35 ; base = max(base, 0.4)   # Presidio boost
   if deny_in_window:          base = 0.0                             # our added deny step
   keep iff base >= threshold (e.g. 0.4)
```

### 4.2 Why this order (precision rationale) **[D]**
- Checksum first because it is the cheapest near-zero-FP signal we already have.
- Deny veto **before** trigger-accept so "заказ № 8 999 123 45 67" (phone-shaped but
  inside an order context) is suppressed — deny outranks weak triggers. (Edge: if BOTH a
  strong PHONE trigger AND a deny word appear, prefer the NEAREST word by char distance —
  RECAP-style local-context tie-break; or, conservatively for a privacy gateway, prefer
  KEEPing PII = let trigger win to avoid leaks.)
- Trigger gate (REQUIRED, not just boost) for phone because phone has no checksum and is
  the worst collider; Macie proves required-keyword raises precision on exactly this.
- 14-digit hard-drop is a free precision win (track numbers are unambiguously non-PII).

### 4.3 How to implement IN / AROUND Presidio
Three viable integrations, increasing invasiveness:
- **(a) Subclass `PatternRecognizer` per numeric type** and override `validate_result`
  (checksum → boost) and `invalidate_result` (deny window → drop). Add positive `context=
  TRIGGER[type]` so Presidio's own enhancer gives the +0.35. You add the DENY scan +
  REQUIRED-trigger gate inside the recognizer (Presidio has no deny primitive). **[A]/[D]**
  Files to mirror: `pattern_recognizer.py` (the `validate_result`/`invalidate_result`
  hooks), and the CreditCard recognizer for the checksum-in-validate pattern.
- **(b) Post-process pass** on `List[RecognizerResult]` before anonymize: for each numeric
  result, slice `text[max(0,start-40):end+40]`, run the deny/trigger char-window logic,
  and drop or re-score. Keeps Presidio stock; all disambiguation in one auditable function.
  (Recommended for the prototype — least coupling, easiest to test.) **[D]**
- **(c) Custom `ContextAwareEnhancer` subclass** implementing signed adjustment
  (boost AND deny) — the "proper" Presidio extension point, but more code and it operates
  on the lemma window (needs the RU lemmatizer wired). **[A]/[D]**

> For Obscura's regex-first prototype (`ru_pii.py` already returns its own `Span` objects,
> not via Presidio), the cleanest move is option (b)-style: keep the checksum gating you
> have, ADD a `_deny_in_window()` and `_trigger_in_window()` char-scan around each numeric
> Span, and a 14-digit hard-drop. This buys the DLP/Macie behavior with ~30 lines and zero
> new deps. **[D]**

### 4.4 Pseudocode (drop-in shape for the prototype)
```python
DENY = compile_word_regex(["трек","накладн","заказ","артикул","sku","сумма","итог",
                           "руб","₽","кол-во","количеств","штрих","ean","инвойс","позиц"])
TRIG = { "PHONE": compile_word_regex(["тел","телефон","моб","звон","whatsapp","ватсап","viber"]),
         "CARD" : compile_word_regex(["карт","оплат","перевод","списан","visa","mastercard","мир"]),
         "OMS"  : compile_word_regex(["полис","омс"]) }
W = 40

def keep_numeric(text, span):              # span: start,end,label,value
    d = digits(span.value)
    if len(d) == 14:                       # postal track — never PII
        return False
    ctx = text[max(0, span.start-W): span.end+W].lower()
    if DENY.search(ctx):                   # deny-context veto (DLP excludeByHotword)
        return False
    if span.label in ("SNILS","INN","CARD") and checksum_ok(span):
        return True                        # checksum precision backbone
    if span.label == "PHONE":              # no checksum -> require trigger (Macie gate)
        return bool(TRIG["PHONE"].search(ctx)) or strict_phone_shape(span.value)
    return True
```

---

## 5. Quick-reference: where each capability lives

| Need | Presidio | Google DLP | AWS Macie | Nightfall | Comprehend |
|---|---|---|---|---|---|
| Positive context BOOST | ✅ `context=` +0.35 (lemma window) [A] | ✅ HotwordRule +adj [B] | ✅ (as required gate) [B] | ✅ Context Rule up-weight [B] | ❌ (ML only) |
| Negative/DENY context | ❌ build it (invalidate_result) [A] | ✅ excludeByHotword / -adj [B] | ✅ IgnoreWords (value) [B] | ✅ Exclusion + down-weight [B] | ❌ |
| Required-keyword GATE | ❌ (boost not gate) | partial (INVERSE_MATCH) [B] | ✅ Keywords+MaxDistance [B] | partial | ❌ |
| Proximity window unit | tokens/lemmas [A] | **chars** [B] | **chars** (1–300) [B] | **chars** [B] | n/a |
| Checksum integration | ✅ validate_result [A] | ✅ built-in infoTypes [B] | regex-only [B] | built-in [B] | implicit [B] |
| Allow-list value drop | ✅ allow_list [A] | dictionary exclusion [B] | IgnoreWords [B] | Exclusion [B] | ❌ |
| LLM context verify | ❌ | ❌ | ❌ | ❌ | ❌ (RECAP = research [B]) |

---

## 6. Open questions / uncertainties
- **Tie-break when trigger AND deny both in window** (e.g. "позвоните по заказу 8999...").
  RECAP would ask an LLM; deterministic options: nearest-word-wins (char distance) or
  privacy-conservative keep. Needs an empirical call on RU data. **[D]**
- **Window size (40 chars)** is a guess seeded by DLP/Macie defaults (50; Macie default
  MaxMatchDistance 50). Must be tuned on the realistic-RU-queries dataset
  (`research/realistic-ru-queries.md`). **[D]**
- **Phone-required-trigger lowers recall**: bare "8 999 123 45 67" with no nearby word
  would be dropped. Mitigation: a strict phone *shape* (separators / +7 / 8-prefix) acts
  as its own positive signal even without a trigger word — already in the pseudocode. **[D]**
- **Skyflow/Comprehend internals** not publicly documented at the disambiguation level —
  graded [B]/[D], not [A]. Do not over-trust those rows.

---

## 7. Source index (graded)
PRIMARY source code [A]:
- `presidio-analyzer/.../context_aware_enhancers/lemma_context_aware_enhancer.py`
- `presidio-analyzer/.../context_aware_enhancers/context_aware_enhancer.py`
- `presidio-analyzer/presidio_analyzer/analyzer_engine.py` (allow_list, threshold, enhance)
- `presidio-analyzer/presidio_analyzer/pattern_recognizer.py` (validate/invalidate, flags)
- `prototype/obscura/ru_pii.py` (existing checksum gating)
Official docs [B]:
- Google DLP rules: https://docs.cloud.google.com/sensitive-data-protection/docs/creating-custom-infotypes-rules
- Google DLP likelihood: https://cloud.google.com/sensitive-data-protection/docs/creating-custom-infotypes-likelihood
- AWS Macie CDI options: https://docs.aws.amazon.com/macie/latest/user/cdis-options.html
- AWS Macie CDI API: https://docs.aws.amazon.com/macie/latest/APIReference/custom-data-identifiers.html
- Nightfall Context Rules: https://help.nightfall.ai/detection_platform/faq/context_rules
- Nightfall Confidence Levels: https://help.nightfall.ai/detection_platform/faq/confidence_levels
- AWS Comprehend PII: https://docs.aws.amazon.com/comprehend/latest/dg/realtime-pii-api.html
- Presidio context tutorial: https://microsoft.github.io/presidio/tutorial/06_context/
- Presidio ML-context feature request: https://github.com/microsoft/presidio/issues/1686
Research [B]:
- RECAP / hybrid multilingual PII: https://arxiv.org/html/2510.07551v1 (pdf: https://arxiv.org/pdf/2510.07551)
