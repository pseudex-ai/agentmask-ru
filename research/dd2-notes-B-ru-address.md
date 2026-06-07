# DD2-B — Best LOCAL approach to extract Russian ADDRESSES at high recall (incl. marker-less free-form)

Research date: 2026-06-07. Scope: address detection ONLY. Out of scope (other agents): person-name NER, numeric-ID collisions, eval harness/architecture.

Problem framing: our marker-based regex has **low recall** on free-form / marker-less forms
("Ленина 5 кв 3", "мкр Северный д12 кв 8", "квартира 45 дом 12 по Ленина") and **over-fires
(precision ~18%)**. Goal: a local, CPU-viable, license-clean approach that raises recall on
marker-less addresses without destroying precision, plus a Presidio integration path.

Evidence grades: **[A]** primary source code / spec; **[B]** peer-reviewed paper / official docs;
**[C]** vendor/reputable secondary; **[D]** blog / unverified.

---

## TL;DR / RECOMMENDATION

1. **No off-the-shelf local tool "solves" marker-less RU addresses at high recall.** This is the
   honest headline. Every option trades recall for precision somewhere. The realistic target is a
   **layered detector**, not a single library.
2. **Best single local engine = Natasha `AddrExtractor` (Yargy grammar) — but understand its real
   behaviour.** It is NOT a chain matcher; it independently matches *individual* address parts
   (улица / дом / корпус / квартира / мкр / etc.), each gated by its own marker word, then merges
   consecutive part-matches into one span. So:
   - It **does** catch marker-bearing free-form ("мкр Северный д12 кв 8", "квартира 45 дом 12") —
     these have markers, just no canonical "г. … ул. … д. …" order. ✅
   - It **partially** catches "Ленина 5" via a marker-less `STREET_NAME = INT | ADDR_NAME` rule,
     but that same rule is the **precision hole**: a bare capitalised word + INT can match almost
     anything, and there are `UNPARSED_INT` / `UNPARSED_VARCHAR` fallbacks at the bottom of
     `ADDR_PART` that scoop up loose tokens. This is the mechanism behind over-firing. ⚠️
   - Truly marker-less + inverted ("Ленина 5 кв 3" → has кв marker; "Ленина 5" alone → weak) is
     where it is weakest. ⚠️
3. **The pymorphy3 fix is real, simple, and verified in the wild** — a 3-line `sys.modules` alias
   before importing natasha. Natasha (1.6.0, the latest release, still pins `pymorphy2`) works
   today on Python 3.11–3.13 as-is; the pkg_resources issue only becomes a hard error on **Python
   3.14+**. So the fix is needed for 3.14 / clean installs, not 3.12 urgently. See §2.
4. **libpostal is the wrong tool for this job** — by explicit design it does *parsing*, not
   *detection*: "Extracting addresses from free text" is a stated non-goal. Use it only as a
   downstream normalizer/validator on spans another detector already found. See §4.
5. **GLiNER (`gliner_multi_pii-v1`, Apache-2.0) via Presidio `GLiNERRecognizer`** is the best
   *recall-oriented zero-shot* layer and is the only candidate that genuinely targets marker-less
   forms semantically — BUT zero-shot GLiNER multilingual on Russian is weak (Multi-CoNER RU
   zero-shot F1 ≈ 33), so trust only after RU validation; the PII-tuned variant is better than the
   base multilingual but still unbenchmarked on RU addresses specifically. See §5.
6. **DaData / ФИАС / ГАР**: the registry + DaData are *normalization/standardization* tools, not
   free-text spotters; usable offline only via DaData's paid on-prem build or a self-hosted ГАР
   dump. Not a detector. See §6.

**Recommended build (layered, local, CPU):**
> (a) Keep + tighten the marker regex for canonical forms; (b) add **Natasha AddrExtractor** (with
> pymorphy3 alias) as the primary free-form-with-markers detector; (c) add **GLiNER
> gliner_multi_pii-v1 (ONNX, CPU)** as a recall booster for marker-less/semantic forms, validated
> on RU; (d) **precision controls**: require ≥2 address parts OR a marker OR digit+street-token
> co-occurrence; drop bare `UNPARSED_*` / single-token matches; (e) optional **libpostal** as a
> confirm/normalize gate on candidate spans. Recall is bought by the union of (b)+(c); precision is
> bought by (d).

---

## 1. NATASHA AddrExtractor + YARGY — how it actually works

### 1.1 Architecture (read from source)

- `natasha.morph.vocab.MorphVocab` **subclasses** `pymorphy2.analyzer.MorphAnalyzer`:
  ```python
  from pymorphy2.analyzer import (
      Parse as PymorphyParse,
      MorphAnalyzer as PymorphyAnalyzer)
  class MorphVocab(PymorphyAnalyzer):
      def __init__(self):
          PymorphyAnalyzer.__init__(self, result_type=MorphForm)
  ```
  [A] https://github.com/natasha/natasha/blob/master/natasha/morph/vocab.py
  → This single subclass is the *entire* coupling to pymorphy2. Swapping the backend = making
  `pymorphy2.analyzer.MorphAnalyzer` resolve to pymorphy3's (see §2).

- `AddrExtractor` is a Yargy-based `Extractor`. The base `Extractor.__call__` does
  `for match in self.parser.findall(text): yield adapt_match(match)`. AddrExtractor's `find()`
  collects ALL part-matches, sorts by start, and wraps them into one `obj.Addr(parts)` spanning
  first.start → last.stop:
  ```python
  matches = list(self(text))
  matches = sorted(matches, key=lambda _: _.start)
  start = matches[0].start; stop = matches[-1].stop
  parts = [_.fact for _ in matches]
  return Match(start, stop, obj.Addr(parts))
  ```
  [A] https://github.com/natasha/natasha/blob/master/natasha/extractors.py
  → **Key consequence:** it is a *bag of independently-matched parts*, NOT a single contiguous
  grammar. Recall on "messy"/reordered addresses is therefore *better than a strict chain grammar*
  (good for free-form), but precision is *worse* because each part fires independently and loose
  numbers/words get captured.

### 1.2 The grammar (`natasha/grammars/addr.py`, ~3100 lines) [A]
https://github.com/natasha/natasha/blob/master/natasha/grammars/addr.py

Top-level rule is a flat `or_` of single-part recognizers:
```python
ADDR_PART = or_(
    INDEX, COUNTRY, FED_OKRUG, RESPUBLIKA, KRAI, OBLAST, AUTO_OKRUG,
    RAION, GOR_OKRUG, MUN_OBRAZ, GOROD, OKRUG, STANCIYA, DEREVNYA, SELO,
    POSELOK, OSTROV, AIRPORT, TERRITORY, GSK, SNT, KIZ, TIZ,
    STREET, KVARTAL, KILOMETR, LINIA, PROEZD, PROSPEKT, PEREULOK, PLOSHAD,
    SHOSSE, NABEREG, BULVAR, GARAG, DOM, KORPUS, STROENIE, LITERA,
    MASHINOMESTO, ETAZH, SEKCIYA, HRANILISHCHE, OFIS, BLOK, BOKS,
    KVARTIRA, KOMNATA, POMESHENIE, UCHASTOK,
    UNPARSED_INT, UNPARSED_VARCHAR        # ← precision hole
).interpretation(AddrPart.value).interpretation(AddrPart)
```

Each component = `<MARKER_WORDS> <VALUE>` (or value+marker). Examples (verbatim):
- **DOM** requires a marker: `DOM = rule(DOM_WORDS, DOM_VALUE)` where
  `DOM_WORDS = or_(rule(normalized('дом'), DOT.optional()), rule(caseless('д'), DOT.optional()))`.
  → "д12" / "дом 12" match; a bare "12" does NOT match DOM (only UNPARSED_INT).
- **KORPUS** markers: `{'корп','копр','кор','корс','корус','корпс'}`, `корпус`, `к.`, `/`.
- **STROENIE** markers: `{'с','ст','стр_','стр','строй','строен'}`, `строение`.
- **KVARTIRA** = `rule(KVARTIRA_WORDS, KVARTIRA_VALUE)` (кв / квартира + value).
- **STREET** is the recall+precision pivot:
  ```python
  STREET_WORDS = or_(rule(normalized('улица')), rule(caseless('ул'), DOT.optional()))
  STREET_NAME  = or_(
      rule(INT, ADDR_NAME).interpretation(Street.name),  # "2-я Парковая"
      ADDR_NAME.interpretation(Street.name),             # "Ленина"  ← MARKER-LESS
      INT.interpretation(Street.name))                   # bare INT  ← precision risk
  STREET = or_(rule(STREET_WORDS, STREET_NAME),
               rule(STREET_NAME, STREET_WORDS))          # both forms REQUIRE ул-marker
  ```
  → Note: the top-level `STREET` rule that fires inside `ADDR_PART` **requires** `STREET_WORDS`
  (улица/ул) on one side. So a *bare* "Ленина" is NOT matched as STREET by ADDR_PART; "Ленина"
  only becomes a street when combined with a building marker chain or when caught as
  ADDR_NAME/UNPARSED_VARCHAR. **This is why "Ленина 5" alone is weak: "Ленина"→UNPARSED_VARCHAR,
  "5"→UNPARSED_INT, merged into one low-confidence Addr — present in output but indistinguishable
  from noise.** ⚠️
- **мкр (микрорайон)** is covered — there are settlement/territory recognizers
  (POSELOK/TERRITORY/мкр-family); "мкр Северный" matches as a settlement, then "д12 кв 8" match as
  Building+Room → all merged. ✅

### 1.3 Recall / precision verdict for AddrExtractor [A from grammar reading + B context]

| Free-form pattern | AddrExtractor behaviour |
|---|---|
| "г. Москва, ул. Ленина, д. 5, кв. 3" (canonical) | **Full match**, high precision ✅ |
| "мкр Северный д12 кв 8" | **Full match** (settlement + building + room markers) ✅ |
| "квартира 45 дом 12 по Ленина" | **Matches** квартира+дом as parts; "Ленина" via UNPARSED_VARCHAR; reordering OK because parts are independent ✅ (span may include/exclude "по Ленина" oddly) |
| "Ленина 5 кв 3" | кв marker → Room matches; "Ленина"/"5" → UNPARSED → merged. **Detected but fuzzy span + low confidence** ⚠️ |
| "Ленина 5" (no marker at all) | **Weak**: only UNPARSED_VARCHAR + UNPARSED_INT → over-fires on any "Capitalised + number" (e.g. "Windows 10", "Châtillon 12") ❌ precision |

- **Recall (marker-bearing free-form): high (~good).** The independent-part design is its strength.
- **Recall (truly marker-less "Ленина 5"): low/fuzzy**, and what little it catches comes from the
  UNPARSED fallbacks that *cause* the over-firing.
- **Precision: poor out of the box** because of `STREET_NAME→INT`, `UNPARSED_INT`,
  `UNPARSED_VARCHAR`. **Mitigation = post-filter Addr objects: drop those whose parts are
  exclusively `Unparsedint`/`Unparsedvarchar`; require ≥1 typed part (Building/Street/Settlement/
  Room) OR ≥2 parts total.** This is the single highest-leverage precision lever and is done in
  application code, not by editing the grammar.
- License: **MIT** (natasha, yargy, slovnet). CPU-only, tiny. [A] https://github.com/natasha/natasha
- It does **not** validate against ФИАС — it's pure pattern/morphology, so "ул. Несуществующая 999"
  matches happily (fine for *redaction*, where we want recall, not real-address verification).

### 1.4 Existing OSS that uses AddrExtractor for PII / the alternative they chose
- `RussianNLP/DRAGON` `pipe/src/utils.py` imports `AddrExtractor` + `from pymorphy3 import
  MorphAnalyzer` together — i.e. real projects already pair AddrExtractor with pymorphy3. [A]
  https://github.com/RussianNLP/DRAGON/blob/main/pipe/src/utils.py
- **Counter-signal:** a production RU anonymizer, `Winkey86/AnonimisationModule`
  (`anonymizer/ner.py`), deliberately does **NOT** use AddrExtractor. It detects addresses only via
  Natasha-NER `LOC` + spaCy `LOC/FAC/GPE` mapped to LOCATION, and even keeps a regex
  (`проспект|улица|шоссе|бульвар|переулок|набережная|...`) as a *garbage filter* to drop street
  words from PERSON/LOC noise. Uses spaCy `ru_core_news_lg` + Natasha NER + **pymorphy3**. [A]
  https://github.com/Winkey86/AnonimisationModule/blob/master/anonymizer/ner.py
  → Read: practitioners often skip AddrExtractor and lean on NER LOC + markers because
  AddrExtractor's precision is hard to tame. Worth weighing.

---

## 2. THE pymorphy2 → pymorphy3 FIX (Python 3.12 / 3.14) — status & exact steps

### 2.1 Status of the premise (corrected) [A]
- Natasha's **latest release is 1.6.0 (2023-07-24)** and `setup.py` `install_requires` still lists
  **`pymorphy2`** (unpinned), `razdel>=0.5.0`, `navec>=0.9.0`, `slovnet>=0.6.0`, `yargy>=0.16.0`,
  `ipymarkup>=0.8.0`. [A] https://github.com/natasha/natasha/blob/master/setup.py ,
  https://pypi.org/project/natasha/
- **Maintainer explicitly declined migrating to pymorphy3.** PR #127 instead *revived pymorphy2*
  (via pymorphy2 PR #161) so `natasha==1.6.0` works on Python **3.11**. Maintainer (kuk),
  2023-07-24: "pip install natasha==1.6.0 Должен работать на Python 3.11 … Исправлено в … pull/127".
  [A] https://github.com/natasha/natasha/issues/120#issuecomment-1647621446
- **The pkg_resources warning is only a hard ERROR on Python 3.14+**, NOT 3.12/3.13. Confirmed by
  commenter insolor on issue #138 (2025-12-18): "Не после 30.11.2025, а в Python 3.14 и новее … 3.13
  будет поддерживаться до октября 2029." [A]
  https://github.com/natasha/natasha/issues/138#issuecomment-3671205749
  → So: **on Python 3.12/3.13 natasha+pymorphy2 runs today** (with a deprecation warning). The
  pymorphy3 swap is mandatory only for Python 3.14+, and *nice-to-have* now (kills the warning,
  uses a maintained backend, `pymorphy3` already fixed the pkg_resources deprecation in v2.0.1).

### 2.2 Can you swap to pymorphy3? YES — and the API is compatible
- `pymorphy3.analyzer.MorphAnalyzer.__init__` accepts the same `result_type` kwarg natasha passes:
  `def __init__(self, path=None, lang=None, result_type=Parse, units=None, ...)`. Module also
  exports `Parse`. So pymorphy3.analyzer is a drop-in for pymorphy2.analyzer for natasha's needs.
  [A] https://github.com/no-plagiarism/pymorphy3/blob/master/pymorphy3/analyzer.py
- pymorphy3: **MIT license**, supports **Python 3.9–3.14**, latest 2.0.6 (2025-10-09). Deps:
  `dawg2-python>=0.8.0` (pure-Python DAWG → no C-build pain on 3.12), `pymorphy3-dicts-ru`, and
  `setuptools` only for 3.12+. pkg_resources DeprecationWarning fixed in **v2.0.1 (2024-01-13)**.
  [A] https://pypi.org/project/pymorphy3/ , https://github.com/no-plagiarism/pymorphy3/blob/master/CHANGES.rst , https://github.com/no-plagiarism/pymorphy3/blob/master/setup.py

### 2.3 EXACT FIX — the `sys.modules` alias (verified in the wild) [A]
Place this **before** importing natasha. Verified production usage in
`evenikkal/hhanalyst/python_analyzer/analyzer/nlp.py` (comment: "Natasha internally uses pymorphy2
which requires pkg_resources (removed in Python 3.14). We patch it to use pymorphy3 instead."):

```python
import sys
import pymorphy3
sys.modules["pymorphy2"] = pymorphy3
sys.modules["pymorphy2.analyzer"] = pymorphy3.analyzer

# now safe to import natasha
from natasha import (
    Segmenter, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsNERTagger,
    AddrExtractor, Doc,
)
```
[A] https://github.com/evenikkal/hhanalyst/blob/master/python_analyzer/analyzer/nlp.py

Why it works: natasha's only pymorphy2 touch is
`from pymorphy2.analyzer import Parse, MorphAnalyzer` inside `MorphVocab`. The alias makes both
names resolve to pymorphy3's equivalents, which expose the same `MorphAnalyzer(result_type=...)`
and `Parse` API (§2.2). `MorphVocab()` then constructs a pymorphy3 analyzer transparently.

Install: `pip install natasha pymorphy3 pymorphy3-dicts-ru` (drop/keep `pymorphy2` — the alias wins
at import time regardless).

Caveats / honesty:
- This is a community monkeypatch, **not endorsed by natasha maintainers** (they declined the
  migration). Pin versions and add a smoke test (parse a known address) in CI.
- Minor lemma/tag differences between pymorphy2 and pymorphy3 dictionaries are possible; for address
  *detection* (markers + numbers) the morphology dependence is light, so risk is low — but validate.
- Alternative (lower-magic): pin **Python ≤3.13** and `setuptools<81`, keep pymorphy2, accept the
  warning. Valid until ~2029. The alias is preferred for forward-compat and a maintained backend.

---

## 3. YARGY STANDALONE — custom address grammar

- Yargy is an Earley parser with Russian morphology (via pymorphy), pure Python, **MIT**, used in
  prod at Sberbank/Interfax/RIA. Depends only on pymorphy2 (→ same pymorphy3 alias applies).
  [B] https://github.com/natasha/yargy , https://github.com/natasha/yargy-examples
- **You do not need to write a grammar from scratch** — `natasha/grammars/addr.py` *is* a complete,
  battle-tested Yargy address grammar (улица/дом/корпус/строение/квартира/офис/мкр/СНТ/ГСК/литера/
  машиноместо/…). Fork it and (a) add a *marker-less* `STREET_NAME` path that requires morphology
  evidence (e.g. ADJF/Geox-tagged token + INT) and (b) tighten/remove the `UNPARSED_*` fallbacks to
  raise precision. This is the lowest-risk way to attack marker-less "Ленина 5" while controlling
  over-firing. [A] grammar file above.
- Custom marker-less rule sketch (recall for "Ленина 5" without false-firing on "Windows 10"):
  require the name token to be morphologically plausible as a RU toponym/surname-derived adjective
  (ADJF or `Surn`/`Geox` gram) AND adjacent INT in a small range, AND boost only when near other
  address cues. Yargy supports `gram('ADJF')`, `gram('Geox')`, custom predicates, and
  `interpretation` for this. (No ready public "marker-less RU street" grammar found beyond natasha's
  own; searches surfaced only natasha/yargy + yargy-examples.) [B]
- Existing OSS Yargy address grammars on GitHub: the dominant one *is* natasha's `addr.py`; forks/
  copies appear inside app repos (e.g. RussianNLP/DRAGON imports AddrExtractor). No widely-maintained
  independent "better RU address Yargy grammar" was found — natasha's is the reference. [B/C]

---

## 4. libpostal / pypostal — RU quality, weight, license, CPU

- **What it is:** C library, CRF statistical parser/normalizer trained on >1B OSM/OpenAddresses
  addresses, 60+ languages; **99.45% full-parse accuracy on held-out (global) addresses**.
  Python bindings = `pypostal` (`postal`). [B/C] https://github.com/openvenues/libpostal ,
  https://github.com/openvenues/pypostal
- **DECISIVE: it does parsing, NOT detection.** Project explicitly lists "Extracting addresses from
  free text" as a **non-goal**; input must already be an address string. → It cannot raise our
  *recall of spotting addresses inside chat text*. Only useful as a **downstream
  normalizer/validator** on candidate spans found by AddrExtractor/GLiNER/regex. [A]
  https://github.com/openvenues/libpostal (Non-goals section)
- **RU quality:** documented mis-tagging of Cyrillic addresses — "округ"→city, "область"→state,
  street/district→house/house_number (issue #138). No published RU recall/precision; anecdotal
  weakness. Russian is in training data but underperforms vs Latin scripts. [C]
  https://github.com/openvenues/libpostal/issues/138
- **License:** MIT. **Footprint:** model data ~**1.8 GB** (Senzing build ~2.2 GB) on disk; runtime
  designed for **<1 GB RAM/process**; country-specific models exist for mobile. Fully **offline**
  after the one-time S3 data download. CPU-only, fast. [C] https://github.com/openvenues/libpostal
- **Verdict:** **NOT** the recall solution. Heavy (1.8 GB) for a non-detector. Keep out of the
  primary path; consider only as an optional confirm/normalize gate if structured output is needed.

---

## 5. GLiNER for addresses (zero-shot "address"/"адрес")

- **Architecture:** BERT-like bidirectional encoder, zero-shot — you pass entity labels at
  inference; extracts spans in parallel; original paper beats ChatGPT zero-shot on NER. [B]
  https://arxiv.org/abs/2311.08526
- **Best model for our case:** `urchade/gliner_multi_pii-v1` — **Apache-2.0**, the model Presidio's
  `GLiNERRecognizer` recommends; PII-tuned, multilingual base (~209M params), CPU-runnable
  (ONNX). [C] https://microsoft.github.io/presidio/samples/python/gliner/ ,
  https://huggingface.co/urchade/gliner_multi-v2.1 (same family, Apache-2.0, 209M)
- **(a) Recall on free-form/marker-less RU:** This is the ONE candidate that targets marker-less
  forms *semantically* (no markers needed — it learns "this span looks like an address"). BUT honest
  caveats:
  - **Zero-shot GLiNER-multi on Russian is weak**: Multi-CoNER **RU zero-shot F1 ≈ 33** in the
    GLiNER paper (vs ChatGPT 59.7). [B] paper / https://arxiv.org/pdf/2311.08526
  - The **PII-tuned** `gliner_multi_pii-v1` is better than base multi for PII labels, and
    `knowledgator/gliner-pii-large-v1.0` reports overall **P 87.4 / R 79.4 / F1 83.25** with 60+ PII
    types incl. *address* — but **on an English-centric set; Russian address recall is NOT separately
    benchmarked** in any card. [C] https://huggingface.co/knowledgator/gliner-pii-large-v1.0
  - → **Treat GLiNER as a recall booster you MUST validate on RU data.** Expect it to catch
    marker-less "Ленина 5"-type spans that AddrExtractor misses, at the cost of new FP types (it may
    tag generic places). Use label `"address"` (English label works better than `"адрес"` for these
    English-base models — verify both).
- **(b) Precision / FP:** zero-shot models over-tag when the label is broad; tune the confidence
  threshold (GLiNER exposes `threshold`), and require overlap/agreement with a marker or with
  AddrExtractor to keep precision. multi_label=True + flat_ner=False per Presidio sample.
- **(c) License / CPU / offline:** Apache-2.0 model + MIT gliner lib; **ONNX CPU path**
  (`load_onnx_model=True`, `map_location="cpu"`) — avoids AVX2 crashes; ~200M params runs on CPU
  (slower than Natasha; batch). Fully offline once the model is cached. [C] Presidio GLiNER sample.
- **(d) Presidio integration:** first-class. Built-in recognizer:
  ```python
  from presidio_analyzer.predefined_recognizers import GLiNERRecognizer
  entity_mapping = {"person":"PERSON","organization":"ORGANIZATION",
                    "location":"LOCATION","address":"LOCATION"}  # fold address→LOCATION
  gliner_recognizer = GLiNERRecognizer(
      model_name="urchade/gliner_multi_pii-v1",
      entity_mapping=entity_mapping,
      flat_ner=False, multi_label=True, map_location="cpu",
      # load_onnx_model=True for CPU/AVX2 safety
  )
  analyzer.registry.add_recognizer(gliner_recognizer)
  ```
  [C] https://microsoft.github.io/presidio/samples/python/gliner/
- **(e) Does it solve marker-less?** **Partially / best-available** — it's the only local option
  that *can* spot "Ленина 5" with no markers, but RU recall is unproven and must be measured. It
  will not be a silver bullet at the ~95% recall level on its own.

---

## 6. DaData / ФИАС / ГАР — registry-based normalization

- **ФИАС/ГАР** = the official RF address registry (ФНС). DaData splits a string into
  region/city/street/house/flat per ФИАС/ГАР and enriches (index, geo, metro). [C]
  https://dadata.ru/api/clean/address/ , https://dadata.ru/suggestions/usage/address/
- **It is normalization/standardization + suggest, NOT free-text detection.** Same shape as
  libpostal: you feed it a string believed to be an address; it does not spot addresses inside chat
  text. → not a recall solution for our task. [C] DaData docs above.
- **Offline feasibility:** DaData offers an **on-prem** build for high volume / no-cloud security
  policy (paid). The raw **ГАР dump is publicly downloadable** from ФНС and can be loaded into a DB
  for offline lookup, but **building a free-text *parser/spotter* on top is a project, not a
  library** — no maintained OSS RU free-text address *detector* using ФИАС was found. [C]
  https://dadata.ru/ ; ГАР dump is from the ФНС portal.
- **Verdict:** useful only as an **offline validator/normalizer** (confirm a detected span is a real
  RF address, fill structured fields) — same role as libpostal but RU-native and registry-backed.
  Not a detector; cloud DaData also leaks PII to a third party (avoid for the privacy use-case unless
  on-prem).

---

## 7. Existing GitHub repos: ready RU address detection / anonymization

| Repo | What it does for addresses | Backend | Signal |
|---|---|---|---|
| `Winkey86/AnonimisationModule` | Addresses via **NER LOC** (Natasha + spaCy LOC/FAC/GPE→LOCATION), street-word regex used as a *garbage filter*; **no AddrExtractor** | spaCy `ru_core_news_lg` + Natasha + **pymorphy3** | Real anonymizer; chose NER-LOC over AddrExtractor. [A] https://github.com/Winkey86/AnonimisationModule/blob/master/anonymizer/ner.py |
| `RussianNLP/DRAGON` | Imports `AddrExtractor` directly | natasha + **pymorphy3** | Confirms AddrExtractor+pymorphy3 pairing in practice. [A] https://github.com/RussianNLP/DRAGON/blob/main/pipe/src/utils.py |
| `ekinohito/nerpda` | NER anonymization notebook; Natasha pipeline + Faker('ru_RU') + pymorphy3 | natasha + pymorphy3 | Template for synthetic RU + anonymization. [C] https://github.com/ekinohito/nerpda |
| `evenikkal/hhanalyst` | Not address-specific, but the **canonical pymorphy3 alias patch** | natasha + pymorphy3 | The fix in §2.3. [A] https://github.com/evenikkal/hhanalyst |
| (prior DD note) `gbvolkov/data_protection`, `arshinov-dev/pii-leak-detector` | RU Presidio recognizer packs | Presidio + RU recognizers | Copy/adapt RU PatternRecognizers (from ru-pii-dataset notes). [C] |

→ No single repo provides a high-recall marker-less RU address detector. The field converges on
**NER-LOC + markers + (optionally) AddrExtractor**, with precision handled in app code.

---

## 8. HONEST PRECISION CAVEATS (the over-firing problem)

Our current ~18% precision is consistent with: (a) bare regex markers matching "д.", "к.", "с."
(which collide with initials, abbreviations "т.д.", "и т.п.", "к. н."), and (b) AddrExtractor-style
`UNPARSED_*` capture. Raising recall with AddrExtractor/GLiNER **will add new false positives** unless
gated. Precision levers (all in app code, cheap):
1. **Require structure:** accept an Addr only if it has ≥1 *typed* part (Street/Building/Settlement/
   Room) OR ≥2 parts; reject Addr made solely of `Unparsedint`/`Unparsedvarchar`.
2. **Co-occurrence gate:** a lone street-marker or lone "Capitalised+number" must co-occur with a
   second address cue (digit+street-token, or another marker) within N tokens.
3. **Confidence threshold + agreement:** for GLiNER, raise `threshold`; prefer spans where
   AddrExtractor OR a marker agrees.
4. **Negative dictionary:** "д." in "и т.д.", "к." in "т.к.", version numbers ("Windows 10",
   "Python 3.12"), measurements ("5 кв.м" vs "кв. 5" — note "кв.м"!) — these are classic FP sources;
   add stoplists.
5. **Optional libpostal/ФИАС confirm** on candidate spans for structured fields (precision↑, recall
   unaffected).
- Note these are *redaction* heuristics: we want recall-leaning detection; over-redaction (FP) is
  safer than leakage but hurts utility — tune the gate to the product's tolerance.

---

## 9. SOURCES (primary first)
- Natasha grammar: https://github.com/natasha/natasha/blob/master/natasha/grammars/addr.py [A]
- Natasha extractors: https://github.com/natasha/natasha/blob/master/natasha/extractors.py [A]
- Natasha MorphVocab: https://github.com/natasha/natasha/blob/master/natasha/morph/vocab.py [A]
- Natasha setup.py (pymorphy2 pin): https://github.com/natasha/natasha/blob/master/setup.py [A]
- Natasha issue #120 (3.11 fix, pymorphy3 declined): https://github.com/natasha/natasha/issues/120 [A]
- Natasha issue #138 (pkg_resources → error only on 3.14+): https://github.com/natasha/natasha/issues/138 [A]
- pymorphy3 analyzer (API compat): https://github.com/no-plagiarism/pymorphy3/blob/master/pymorphy3/analyzer.py [A]
- pymorphy3 CHANGES/setup/PyPI: https://github.com/no-plagiarism/pymorphy3/blob/master/CHANGES.rst , https://pypi.org/project/pymorphy3/ [A]
- pymorphy3 alias patch (verified): https://github.com/evenikkal/hhanalyst/blob/master/python_analyzer/analyzer/nlp.py [A]
- RU anonymizer (NER-LOC choice): https://github.com/Winkey86/AnonimisationModule/blob/master/anonymizer/ner.py [A]
- AddrExtractor+pymorphy3 in prod: https://github.com/RussianNLP/DRAGON/blob/main/pipe/src/utils.py [A]
- yargy: https://github.com/natasha/yargy , examples https://github.com/natasha/yargy-examples [B]
- libpostal (parsing-only, non-goal): https://github.com/openvenues/libpostal ; RU issue https://github.com/openvenues/libpostal/issues/138 [A/C]
- pypostal: https://github.com/openvenues/pypostal [C]
- GLiNER paper (RU Multi-CoNER F1≈33): https://arxiv.org/abs/2311.08526 , https://arxiv.org/pdf/2311.08526 [B]
- GLiNER+Presidio: https://microsoft.github.io/presidio/samples/python/gliner/ [C]
- GLiNER PII model: https://huggingface.co/knowledgator/gliner-pii-large-v1.0 , https://huggingface.co/urchade/gliner_multi-v2.1 [C]
- SPbLitGuide RU NER recall (context): https://arxiv.org/pdf/2506.02589 [B]
- DaData/ФИАС: https://dadata.ru/api/clean/address/ , https://dadata.ru/suggestions/usage/address/ [C]
