# dd4-A — Noisy / obfuscated PHONE detection + Unicode normalization (RU context)

Scope: phone-number detection in noisy/obfuscated free text (Cyrillic homoglyph digits,
unicode dashes, stray spaces, OCR errors) + the normalization layer that feeds detection.
OUT of scope (other agents): structured/JSON PII, quasi-identifiers/k-anonymity.

Evidence grades: [A] read source / benchmarked  ·  [B] single source  ·  [C] asserted  ·  [D] inference.

> Supersedes the earlier verified-lead stub; same conclusions, now backed by primary-source quotes.
> One correction vs the stub: libphonenumber **natively** accepts unicode dashes + fullwidth digits
> (read from source), so dash-folding is NOT required for the phone detector itself (§1).

---

## TL;DR / ranked recommendation

1. **Use `phonenumbers` (Python port of Google libphonenumber) `PhoneNumberMatcher` as the
   detector.** Battle-tested industry standard (Apache-2.0). It already handles the *easy* noise
   classes natively: arbitrary spaces, ASCII hyphen **and all unicode dashes** (en-dash, em-dash,
   figure dash, minus sign, fullwidth dash), parentheses, **fullwidth/Arabic-Indic digits**. [A]
2. **It does NOT handle homoglyph LETTERS** (Cyrillic «О»→0, «З»→3, «б»→6). Its matching-regex
   digit class is `\d` = Unicode `\p{Nd}`, which excludes Cyrillic letters, so a phone with a
   Cyrillic «О» substituted for `0` is **not found**. This is the same gap our regex has —
   libphonenumber alone does not close it. [A]
3. **Therefore: normalize-then-detect.** Pre-fold homoglyph *digits* to ASCII, then run the
   matcher. This "normalize → detect" split is the established pattern (Presidio, Chromium, Rust
   compiler, django all keep the two stages separate). [A/B]
4. **The one real gotcha: offset mapping.** Non-1:1 folds (NFKC, multi-char skeletons) change
   string length, so spans found in normalized text don't line up with the original. Use
   **length-preserving 1:1 substitutions** for the homoglyph step → offsets stay valid with zero
   bookkeeping. Reserve a full offset-table only where NFKC's length deltas are unavoidable. [A/B]

Confusable-fold library ranking for our case:
- **Custom 1:1 homoglyph→ASCII-digit map** (the ~10–15 Cyrillic/Greek glyphs that look like
  digits), generated from a pinned UTS #39 `confusables.txt`. Offset-stable by construction,
  no dependency, no combinatorial blow-up. **Recommended.** [B/D]
- **`confusables` (woodgern), MIT** — has `normalize()`/`confusable_regex()` that actually fold to
  ASCII, but unmaintained (last release 2021) and `normalize()` returns a *combinatorial list*. [A]
- **`confusable_homoglyphs`, MIT** — DETECTION ONLY (no fold). Use to *flag* mixed-script. [A]
- **`unicodedata.normalize('NFKC', …)` (stdlib)** — folds fullwidth/compat digits & forms; does
  **NOT** fold Cyrillic homoglyphs (canonical, not compatibility equivalents). [A]
- **`unidecode`, GPL/Artistic** — transliterates Cyrillic words too; destructive + copyleft. Avoid. [B]

---

## 1. Google libphonenumber / Python `phonenumbers` — the standard

**Maturity / license.** Google's libphonenumber (Java/C++/JS) is the de-facto standard for
parse/format/validate. `phonenumbers` is David Drysdale's Python port; both **Apache-2.0**.
- https://github.com/google/libphonenumber  [A]
- https://github.com/daviddrysdale/python-phonenumbers (LICENSE Apache-2.0)  [A]
- https://pypi.org/project/phonenumbers/  · `phonenumberslite` exists if metadata size matters  [B]

**`PhoneNumberMatcher` finds phones in free text.** `PhoneNumberMatcher(text, region, leniency,
max_tries)`; iterate → `PhoneNumberMatch` with `.start`, `.end`, `.raw_string`, `.number`.
Purpose-built for "a block of text that may or may not contain numbers."
- docs: https://daviddrysdale.github.io/python-phonenumbers/phonenumbers.phonenumbermatcher.html [B]
- source: https://github.com/daviddrysdale/python-phonenumbers/blob/dev/python/phonenumbers/phonenumbermatcher.py [A]

**Tolerance to spaces / dashes / parens — the matching regex (read from source):** [A]
```python
_REGEX_FLAGS = re.UNICODE | re.IGNORECASE        # phonenumberutil.py
_PATTERN = re.compile("(?:" + _LEAD_CLASS + _PUNCTUATION + ")" + _LEAD_LIMIT +
                      _DIGIT_SEQUENCE + "(?:" + _PUNCTUATION + _DIGIT_SEQUENCE + ")" + _BLOCK_LIMIT +
                      "(?:" + _EXTN_PATTERNS_FOR_MATCHING + ")?", _REGEX_FLAGS)
_DIGIT_SEQUENCE = "\\d" + _limit(1, _DIGIT_BLOCK_LIMIT)   # \d = \p{Nd} under re.UNICODE
```
- `_PUNCTUATION` = `[_VALID_PUNCTUATION]{0,4}` between digit blocks → tolerates **stray spaces,
  dots, slashes, multiple dashes**.
- `_VALID_PUNCTUATION` (phonenumberutil.py) includes the **whole unicode dash range**:
  `-x` + `‐-―` (hyphen, non-breaking hyphen, **figure dash U+2012**, **en-dash U+2013**,
  **em-dash U+2014**, horizontal bar) + **minus sign U+2212** + katakana prolonged `ー` +
  fullwidth forms `－-／` + space. [A]
  → **Our en-dash/em-dash/figure-dash problem is already solved by libphonenumber natively.**
- `_PLUS_CHARS = "+＋"` → handles `+` and fullwidth `＋`. RU `+7` and trunk `8` both parse. [A]

**Leniency levels (read from source — note the integer values):** [A]
```python
class Leniency:
    POSSIBLE = 0   # is_possible_number() only — length-plausible, NOT validated (highest recall)
    VALID = 1      # is_possible_number() AND is_valid_number() (+ national-prefix rules)  [DEFAULT]
    STRICT_GROUPING = 2
    EXACT_GROUPING = 3
```
- Default = `VALID`. For **max recall on noisy text use `Leniency.POSSIBLE` (0)** — skips validity,
  tolerates malformed/OCR'd numbers, at the cost of more false positives.
- RU fully supported (CC +7, trunk prefix `8`); VALID knows the RU numbering plan so it rejects
  blobs that aren't real RU ranges — POSSIBLE does not. [A/D]

**Homoglyph letters — NOT handled (the key limitation).** Digit class `\d`=`\p{Nd}` never includes
Cyrillic letters, so `+7 (9О5) ЗЗЗ-44-55` (Cyrillic О/З) is **not matched** — the regex never sees
a contiguous digit run. Internal `normalize_digits_only()` DOES convert *Unicode-digit* chars
(fullwidth `０`, Arabic-Indic `٠`) via `unicode_digit()`, but only on an *already-matched
candidate* — useless for homoglyph letters that break matching upstream.
- normalize_digits_only docstring: "converts wide-ascii and arabic-indic numerals to European
  numerals, and strips punctuation and alpha characters". [A]
- → **libphonenumber fixes fullwidth digits but not Cyrillic-letter homoglyphs.** [A]

**CPU cost.** Coarse regex prefilter → metadata-backed validation of candidates; cost ∝
#regions × text length (Presidio runs one matcher per region — §3). Heavier than a single regex
but bounded/optimized; run once per region set. [A/D]

**Recall vs hand regex.** Documented design stance is **precision over recall** (validator trims
candidates) — so use POSSIBLE to recover recall. vs a hand regex it wins on format diversity
(international, extensions, grouping) + dash/space/fullwidth tolerance; loses only on homoglyph
letters (which a hand regex also loses). No public head-to-head recall benchmark found. [B/C]
- https://github.com/ZwEin27/phone-number-matcher ("precision more important than recall …
  validator added at the end based on Google's libphonenumber"). [B]

---

## 2. Unicode confusables / homoglyph normalization

**Spec.** UTS #39 "Unicode Security Mechanisms" ships `confusables.txt` (~6,500 chars → visual
prototype) and the **skeleton algorithm** (§4): NFD-decompose → map via confusable table →
re-decompose; two strings confusable iff skeletons equal. Used by ICU SpoofChecker, Chromium, Rust
compiler — the gold-standard folding primitive.
- http://www.unicode.org/reports/tr39/  [B]
- skeleton/NFD + count: https://www.namesilo.com/blog/en/brand-protection/confusable-detection-101-unicode-skeletons-and-mixed-script-checks-for-your-brands  [B]

**Critical fact: NFKC ≠ confusable folding.** [A]
- `unicodedata.normalize('NFKC', s)` folds **compatibility** chars: fullwidth digits/letters →
  ASCII, ligatures (`ﬁ`→`fi`), super/subscripts, math-styled letters. FIXES `０１２`, `①`.
- It does **NOT** fold Cyrillic/Greek homoglyphs (`а`=U+0430, `О`=U+041E, `З`=U+0417) — *canonical*,
  not compatibility equivalents → stay distinct after NFKC. Exactly why homograph attacks survive
  NFKC. So NFKC is **necessary but insufficient** for our Cyrillic case.
  - https://hacktricks.wiki/en/pentesting-web/unicode-injection/unicode-normalization.html [B]
  - https://symbolfyi.com/guides/unicode-normalization-guide/ [B]

**Pipeline-ordering insight (high value).** confusables.txt and NFKC *disagree on 31 chars*; you
can't blindly chain them. Almost no real system chains NFKC *into* confusable detection — they
keep normalization and confusable detection as **separate independent stages** (ICU/Chromium/Rust
use explicit NFD; django/dnstwist apply the map to raw input). "Pipeline ordering matters more than
map contents."
- https://paultendo.github.io/posts/confusable-detection-without-nfkc/ [B]
- https://paultendo.github.io/posts/unicode-confusables-nfkc-conflict/ [B]
- **TR39 also says the skeleton/confusable mapping is for DETECTION, not for normalizing text** —
  blanket-applying it would mangle legitimate Cyrillic words. Scope any fold to numeric runs. [B/D]

**Library landscape:**

| lib | folds to ASCII? | license | maintained | offset-safe? | verdict |
|---|---|---|---|---|---|
| `unicodedata` (stdlib) | NFKC: fullwidth/compat only, NOT Cyrillic | PSF | yes | NFKC can change length | base layer for fullwidth/compat [A] |
| `confusables` (woodgern) | **YES** `normalize()`,`confusable_regex()` | MIT | last rel **2021**, 64★ | combinatorial list, no offset guarantee | functional but stale + blow-up risk [A] |
| `confusable_homoglyphs` (vhf→~valhalla) | **NO** (detect only) | MIT | archived 2024, fork active | n/a | flag mixed-script, not fold [A] |
| `unidecode` | transliterates ALL non-ASCII | **GPL/Artistic** | yes | destructive | avoid (license + over-folds RU) [B] |
| **custom 1:1 digit-homoglyph map** | YES (digit subset) | ours | — | **offset-stable** | **recommended** [B/D] |

`confusables` examples (from source/README): [A]
```python
from confusables import normalize, is_confusable, confusable_regex
normalize('Ʀỏ𝕍3ℛ', prioritize_alpha=True)   # ['rov3r', 'rover']   (combinatorial!)
is_confusable('rover', 'Ʀỏ𝕍3ℛ')             # True
confusable_regex('rover')                     # regex matching confusable variants
```
- https://github.com/woodgern/confusables · https://pypi.org/project/confusables/ (MIT) [A]

**Battle-tested choice for us.** For *attack detection* the TR39 skeleton (ICU/Chromium/Rust) is
gold. For *our need* — fold a small known set of homoglyph **digits** to ASCII inside candidate
numeric runs — a tiny explicit **1:1** map from confusables.txt is most robust: offset-preserving,
no combinatorial expansion, no stale dependency. Order: NFKC (fullwidth/compat) → digit-homoglyph
map (scoped to numeric runs). [B/D]

**Spaces & dashes.** NFKC folds fullwidth space/dash forms; the rest of the space family
(NBSP, thin/zero-width) and dash family need an explicit map for *general* PII. **But for phones
specifically libphonenumber already accepts all those dashes (§1)** — so dash/space canonicalization
helps your *other* detectors, not the phone detector. Zero-width chars are the one thing that can
sit *inside* a digit run and break it → strip them (length-changing → handle offsets). [A/D]

---

## 3. How Presidio / Google DLP / AWS handle obfuscated PII

**Microsoft Presidio (read source):** `PhoneRecognizer` wraps `phonenumbers.PhoneNumberMatcher`
directly. **No homoglyph/confusable/unicode normalization of its own** — inherits exactly
libphonenumber's tolerances. [A]
```python
# presidio-analyzer/.../predefined_recognizers/generic/phone_recognizer.py
SCORE = 0.4
CONTEXT = ["phone","number","telephone","cell","cellphone","mobile","call"]
DEFAULT_SUPPORTED_REGIONS = ("US","UK","DE","FR","IL","IN","CA","BR")   # NO "RU" by default!
leniency: Optional[int] = 1                                             # == Leniency.VALID
for region in self.supported_regions:
    for match in phonenumbers.PhoneNumberMatcher(text, region, leniency=self.leniency):
        ... start=match.start, end=match.end ...    # offsets straight from libphonenumber, raw text
```
Implications for us: (a) **add "RU"** to `supported_regions`; (b) default leniency=1 (VALID) → drop
to **0 (POSSIBLE)** for noisy recall; (c) base confidence only 0.4, boosted by CONTEXT words; (d)
matcher loops **once per region** → cost ∝ #regions; (e) **no homoglyph/leet handling anywhere** —
harden by adding a normalize pre-step or custom recognizer.
- source: https://github.com/microsoft/presidio/blob/main/presidio-analyzer/presidio_analyzer/predefined_recognizers/generic/phone_recognizer.py [A]
- "uses the phonenumbers package … extendable to every region": https://github.com/microsoft/presidio/issues/772 [B]
- https://microsoft.github.io/presidio/tutorial/02_regex/ [B]

**Google Cloud DLP / Sensitive Data Protection:** infoType `PHONE_NUMBER` + custom infoTypes
(regex/dictionary); de-identify via redact/mask/FPE/date-shift. **No documented
homoglyph/confusable normalization** for matching; no leet handling. [B/C]
- https://docs.cloud.google.com/sensitive-data-protection/docs/infotypes-reference [B]
- https://docs.cloud.google.com/sensitive-data-protection/docs/concepts-infotypes [B]

**AWS Comprehend `DetectPiiEntities`:** ML model → entity type + char offsets + confidence;
**English-only**; **no** statement of homoglyph/confusable/unicode-normalization support. Treat
obfuscation handling as undocumented/likely absent. [B/C]
- https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html [B]
- https://docs.aws.amazon.com/comprehend/latest/dg/realtime-pii-api.html [B]

**Conclusion:** None of the three ships confusable/homoglyph normalization; all implicitly assume
you **normalize upstream yourself**. Presidio is closest to our stack and is literally
`phonenumbers` underneath → our pipeline = Presidio's + a normalize pre-step + RU region +
POSSIBLE leniency. [A/D]

---

## 4. The proven pipeline: normalize-then-detect + the offset gotcha

**Is "normalize → detect" the established pattern? Yes.** Confusable/security stacks
(ICU/Chromium/Rust/django/dnstwist), NLP tokenizer stacks (HF), and PII redactors all run a
normalizer stage first, then detection on normalized text; Presidio = optional-normalize →
`PhoneNumberMatcher` → results. [A/B]

**Recommended concrete pipeline (RU phone, 99%+ noisy recall):**
1. `s1 = unicodedata.normalize('NFKC', s0)` — folds fullwidth/compat digits & forms (may change length).
2. `s2 = fold_homoglyph_digits(s1)` — explicit **1:1** Cyrillic/Greek→ASCII-digit map
   (`О/о→0, З/з→3, б→6, Ч/ч→4, …`) from a pinned confusables.txt, **scoped to numeric-looking runs**
   so real Cyrillic words are untouched. Length-preserving. Strip zero-width chars here.
3. Detect: `PhoneNumberMatcher(s2, region="RU", leniency=phonenumbers.Leniency.POSSIBLE)` (+ other
   regions for multilingual). Each match → `.start/.end` in `s2` coordinates. (Optionally union a
   hardened fallback regex.)
4. Map spans **back to s0** and redact on the ORIGINAL.

**The offset-mapping pitfall (the real production gotcha):** [A/B]
- NFKC and any non-1:1 fold **change string length** (`ﬁ`→`fi` grows; some folds shrink), so
  `.start/.end` from normalized text do **not** index the original → blind use redacts wrong chars.
- Two proven fixes:
  - **(preferred) length-preserving 1:1 folds** for the homoglyph + dash steps (1 codepoint → 1
    codepoint) → offsets identical to the original (if you also hand-map the handful of fullwidth
    digits 1:1 and skip NFKC's lossy folds, **no offset bookkeeping at all**). Best for a
    phone-digit pipeline.
  - **(general) carry an offset map**: build normalized-index → original-index during
    normalization; translate spans on exit. Production redactors also apply replacements
    **right-to-left** so earlier offsets aren't shifted.
    - https://blog.logrocket.com/build-local-ai-proxy-redact-pii-before-llms/ ("replacement loop
      runs right to left … preserves original character offsets"). [B]
    - HF tokenizers `offset_mapping` = canonical carry-offsets-through-a-normalizer example:
      https://huggingface.co/learn/llm-course/chapter6/4 [B]
- **Recommendation:** for phones, prefer 1:1 length-preserving homoglyph/dash folds + zero-width
  removal handled by a tiny cumulative-shift map → spans map cleanly to the original. Reserve the
  full offset-table for the general PII path where NFKC is unavoidable. [D]

---

## 5. SOTA note
Frontier work on obfuscated/adversarial PII and homoglyph filter-evasion confirms the
"normalize-then-detect + **targeted** confusable fold" pattern. Blanket NFKC misses Cyrillic;
blanket confusable-skeleton mangles legitimate Cyrillic. Robust production pattern = targeted,
context-scoped (numeric-run) normalization + the standard validator (libphonenumber). [B/C]

## Open questions / caveats
- No public recall benchmark of `PhoneNumberMatcher` vs hardened regex on RU noisy text → build a
  small labeled set to quantify. [C]
- `confusables.normalize()` combinatorial output is unbounded in principle; cap candidates if used.
  We avoid this with the explicit 1:1 digit map. [A/D]
- Generate the Cyrillic→digit set from a **pinned** confusables.txt (Unicode version drift), not
  hand-typed, to stay complete. [D]
- Verify `region="RU"` + POSSIBLE accepts `8XXXXXXXXXX` trunk form (POSSIBLE skips validity). [D]

## Source index (primary first)
- libphonenumber (Google) — https://github.com/google/libphonenumber — Apache-2.0 [A]
- phonenumbers matcher source — https://github.com/daviddrysdale/python-phonenumbers/blob/dev/python/phonenumbers/phonenumbermatcher.py [A]
- phonenumbers util constants — https://github.com/daviddrysdale/python-phonenumbers/blob/dev/python/phonenumbers/phonenumberutil.py [A]
- Presidio PhoneRecognizer source — https://github.com/microsoft/presidio/blob/main/presidio-analyzer/presidio_analyzer/predefined_recognizers/generic/phone_recognizer.py [A]
- UTS #39 — http://www.unicode.org/reports/tr39/ [B]
- confusables (woodgern, fold) — https://github.com/woodgern/confusables · https://pypi.org/project/confusables/ — MIT [A]
- confusable_homoglyphs (detect) — https://github.com/vhf/confusable_homoglyphs · https://pypi.org/project/confusable-homoglyphs/ — MIT [A]
- NFKC vs confusables divergence — https://paultendo.github.io/posts/confusable-detection-without-nfkc/ [B]
- NFKC homograph limitation — https://hacktricks.wiki/en/pentesting-web/unicode-injection/unicode-normalization.html [B]
- offset-preserving redaction — https://blog.logrocket.com/build-local-ai-proxy-redact-pii-before-llms/ [B]
- HF tokenizers offset_mapping — https://huggingface.co/learn/llm-course/chapter6/4 [B]
- Google DLP infoTypes — https://docs.cloud.google.com/sensitive-data-protection/docs/infotypes-reference [B]
- AWS Comprehend PII — https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html [B]
