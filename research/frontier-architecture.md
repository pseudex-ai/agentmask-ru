# Obscura — Frontier Detection Architecture (path to 99%+ on noisy RU PII)

**Date:** 2026-06-07 · Synthesis of proven/SOTA research (dd2-A..D, dd3, dd4-A/B/C + this doc's primary checks) into one combined stack. Every layer is a *battle-tested* component, combined for diversity.

## Principle
Recall is the privacy SLA. Get it from a **diverse recall-union** (recall ≈ `1 − Π(1−rᵢ)` when detectors fail differently), recover precision with deterministic context rules + an optional in-contour LLM verifier, and — crucially — **normalize the input first** so the whole obfuscation class disappears before detection.

---

## Layer 0 — Normalization (offset-safe) — fixes our #1 stress leak (typo/OCR/homoglyph)
Proven facts: `unicodedata.normalize("NFKC")` does **NOT** fold Cyrillic «О»(U+041E)→0 (different script) [A: Unicode confusables util + TR39]; confusables.txt is for *detection*, not normalization [A: UTS#39]. So:
- **Dash fold:** `– — ‒ − −` → `-`. **Space fold:** NBSP/thin/odd → ` `. **Strip zero-width** (U+200B/C/D, U+FEFF).
- **Targeted confusable→digit map, applied only inside candidate numeric runs** (don't touch names): `О о→0, З→3, б→6, Ч→4, З/з, Б, и т.д.` Plus NFKC for fullwidth digits.
- **Offset safety:** use only **1:1 (length-preserving)** substitutions → detection offsets map straight back to the ORIGINAL bytes; handle zero-width removal with a tiny index map. (This is the clean offset technique — no fragile remap.)
Evidence: kills the entire class that leaked in stress (`89545297О85`, `8–948–564–66–58`, odd spaces).

## Layer 1 — Structured pass (JSON / forms) — fixes JSON-embedded-name leak
Presidio **`BatchAnalyzerEngine.analyze_dict`** analyzes each value with the **key as context** [A: read source]. Reusable in ~30 lines without vendoring Presidio:
- detect JSON / `ключ: значение` → parse → run detectors on each value **with the key as context** + a RU **key→type map** (`имя→NAME, телефон→PHONE, снилс→SNILS, инн→INN, адрес→LOC, почта→EMAIL`) → remap offsets (exact for kv; `json.JSONDecoder.raw_decode` or replace-by-value for JSON).
Key-name typing is deterministic, zero-ML, and catches surnames NER misses in `{"имя":"Анна Смирнова"}`.

## Layer 2 — Recall union of diverse detectors
- **Structured IDs:** regex + checksum (СНИЛС mod-101, ИНН mod-11, Luhn for card/ОМС) — have. Confidence calibrated to checksum strength (INN-10 needs context).
- **Phone → Google libphonenumber** `PhoneNumberMatcher(text,"RU",Leniency.POSSIBLE)` [A: python-phonenumbers] **∪ hardened regex.** Format-tolerant, battle-tested; replaces brittle regex. (After Layer-0 normalization it also catches the homoglyph cases.)
- **Names:** Natasha NER ∪ gazetteer (diminutives/Latin/initials) ∪ **pymorphy3 lemmatize-then-lookup** → fixes declensions ("Ивана"→Иван). (pymorphy3 also unblocks Natasha AddrExtractor via the `sys.modules` alias — dd2-B.)
- **Address:** marker + кв/дом-anchor + bare — have; optionally AddrExtractor (pymorphy3) for messy free-form.
- **Quasi-identifiers (new, HIPAA-18):** DOB/age via regex+context (`года рождения/г.р.`), **age ≥ 90 → "90+"**, explicit dates; **medical** = МКБ-10/ICD gazetteer (tier 1) + RU biomedical NER (RuDR-BERT, tier 2). Per dd4-C: single-message → **detect-and-mask**, NOT k-anonymity (undefined on one message).
- Low thresholds, take the **union**.

## Layer 3 — Context disambiguation (precision, recall-safe)
deny/trigger char-windows (order/track words), checksum priority over bare-phone, **location-as-PII** rule (HIPAA granularity × person-link), INN-10 context gate — all implemented.

## Layer 4 — Fail-safe + optional in-contour LLM verifier (the last %)
Confident → reversible tokenize; uncertain → destructive redact; **never silently pass**. Optional final recall net: a **small LOCAL LLM** (llama.cpp 1–3B Q4, in the customer's RF contour, **no egress**) judges middle-confidence / residual spans. Frontier finding (dd2-D): fine-tuned small LOCAL models beat cloud LLMs and keep privacy — cloud LLM only for offline labelling.

## Eval discipline (so 99%+ is real, not claimed)
presidio-research **`SpanEvaluator`** (IoU), headline **F2 + per-entity recall + true-leak (value masked by ANY type)**, dump every FN, validate on **stress + fresh seeds + REAL data**. Never tune on the test set; confirm gains on an unseen seed.

---

## Honest path to 99%+
Clean text is already ~99/100. Each stress gap maps to exactly one proven layer:
| Stress failure | Closed by |
|---|---|
| typo/OCR/homoglyph phone (#1) | **Layer 0 normalization + libphonenumber** |
| name in JSON/form | **Layer 1 structured pass** |
| name declensions ("Ивана") | **pymorphy3 lemmatize (Layer 2)** |
| quasi-identifiers (DOB/medical) | **Layer 2 quasi + HIPAA-18 rules** |
| over-mask city / order# | **Layer 3 (done)** |

**Realistic verdict:** Layers 0–3 (all proven, deterministic/light, CPU) credibly push noisy-text recall to ~97–99% at high precision. The final climb to a *robust* 99%+ on truly adversarial + quasi-identifier text needs **Layer 4 (local LLM verifier)** as the recall net, accepting a small precision/over-mask cost (correct bias for privacy). This is a frontier-grade, 152-ФЗ-safe (all local) stack — not a topic-level answer.

## Recommended build order (each validated on a FRESH stress seed)
1. **Layer 0 + libphonenumber** (biggest leak class, ~highest ROI).
2. **pymorphy3 lemmatize** for name declensions (small, clean).
3. **Layer 1 structured/JSON pass.**
4. **Quasi-identifier layer** (DOB/age + МКБ-10 gazetteer).
5. **Layer 4 local-LLM verifier** (the last %, when 1–4 plateau).

## Sources
python-phonenumbers (PhoneNumberMatcher / Leniency), PyPI phonenumbers; Unicode UTS#39 confusables + util.unicode.org; confusables-vs-NFKC analysis; Microsoft Presidio `BatchAnalyzerEngine` source; HIPAA 45 CFR §164.514(b)(2); ARX/sdcMicro (k-anon); i2b2 2014 de-id; RuDR-BERT/RuCCoD. Per-claim detail in `dd4-A-noise-phone.md` (this doc), `dd4-B-structured.md`, `dd4-C-quasi-identifiers.md`, `dd2-notes-D-architecture-eval.md`, `dd3-location-pii.md`.
