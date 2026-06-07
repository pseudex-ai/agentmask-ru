# Russian PII Detection: Datasets, Detection Methods, Reusable Components & Checksums

Research for the RU PII detection / tokenization gateway. Date: 2026-06-07.

Scope: labeled evaluation data for RU PII, the detection method per PII type, reusable OSS
detection components, and the load-bearing checksum algorithms (СНИЛС, ИНН-10/12, Luhn).

---

## TL;DR

1. **No public dataset covers all RU PII types** (ФИО + телефон + email + СНИЛС + ИНН +
   паспорт + адрес + дата рождения + карта + полис ОМС + ВУ + ГРЗ) with span labels.
   RU NER corpora label only PER/LOC/ORG (and a few extend to dates/money). The structured
   IDs (СНИЛС/ИНН/паспорт/карта/ОМС/ВУ/ГРЗ) are **absent from every labeled RU corpus** found.
   → We must **build our own golden set** (synthetic, validator-backed). Design is in Part 4.
2. Detection split: **structured IDs = REGEX (+CHECKSUM where one exists)**; **ФИО / адрес /
   дата рождения in free text = ML NER** (Natasha/Slovnet or GLiNER). email/phone/card = regex.
3. **Reuse, don't reinvent**: Microsoft Presidio (engine + global recognizers) + custom RU
   `PatternRecognizer`/`EntityRecognizer` classes + the **`petrovna`** validator library for
   checksums + **Natasha/Slovnet** (or **GLiNER `gliner_multi_pii-v1`** via Presidio's
   `GLiNERRecognizer`) for ФИО/адрес. Two ready RU recognizer packs already exist on GitHub
   (`gbvolkov/data_protection`, `arshinov-dev/pii-leak-detector`) — copy/adapt them.
4. Checksums confirmed against the official ПФР algorithm (СНИЛС, mod 101) and ФНС weight-
   coefficient algorithm (ИНН-10/12, mod 11→mod 10); card = Luhn; полис ОМС (ЕНП 16 digits) = Luhn/Mod10.

---

## PART 1 — Existing public RU PII / NER datasets

### Hard finding: no all-PII-types RU dataset exists

Standard RU NER corpora annotate only **PER / LOC / ORG** (some add MISC, dates, events,
nested entities, relations). **None** of them label телефон, email, СНИЛС, ИНН, паспорт,
карта, полис ОМС, ВУ, ГРЗ. The structured-ID side of our problem has **zero labeled RU data**.

| Dataset | Entities labeled | Size | License | Covers structured IDs? |
|---|---|---|---|---|
| **Nerus** (natasha) | PER, LOC, ORG (auto-labeled via Slovnet on Lenta news) | ~700K news docs, silver labels | open (natasha ecosystem) | ❌ |
| **Collection3 / Persons-1000** | PER, LOC, ORG | ~1,000 news docs, ~26K entities (11K PER / 7K LOC / 8K ORG) | research use | ❌ |
| **Gareev / FactRuEval-2016** | PER, LOC, ORG | small news/eval sets | research use | ❌ |
| **NEREL** | 29 nested entity types, 49 relations, events | 900+ docs, ~56K entities | research use (arXiv 2108.13112) | ❌ (no SNILS/INN/etc.) |
| **RuNNE-2022** | nested NER (NEREL-based, 29 types) | shared-task split | research use (arXiv 2205.11159) | ❌ |
| **RURED** | OntoNotes-style entities + relations | 500+ texts, 5K+ relations | research use | ❌ |
| **AlexKly/Detailed-NER-Dataset-RU** | PER (LAST/FIRST/MIDDLE_NAME) + LOC (COUNTRY/REGION/CITY/DISTRICT/STREET/HOUSE) | 7,532 samples, BIOLU, pickle | not specified | ⚠️ ФИО + address sub-spans only; **no phone/email/IDs** |
| **DeepPavlov RU NER (ontonotes/collection-rus)** | PER, LOC, ORG (+ OntoNotes types) | model + data | Apache-2.0 (models) | ❌ |

### PII-specific datasets — and why they don't solve RU

| Dataset | Language | Entities | Verdict |
|---|---|---|---|
| **SPY** (`mks-logic/SPY`, NAACL-SRW 2025, HSE/Savkin) | **English only** | URL, email, username, address, name, phone, **id_num (generic)** | Great *methodology* (LLM generates templates with placeholders → Faker fills entities at load), **wrong language** and only a generic `id_num` (no СНИЛС/ИНН split). Reusable as a **blueprint** for our generator. License **CC-BY-4.0**. Repo: github.com/LogicZMaksimka/SPY_Dataset |
| **ai4privacy/pii-masking-200k/300k/400k** | multilingual (incl. some RU) | 50+ PII classes (name, email, phone, address, etc.) | Broad PII taxonomy and some RU rows, but **not RU-document-specific** (no СНИЛС/ИНН/паспорт-РФ semantics or checksums). Useful for ФИО/email/phone/address augmentation only. |
| **nvidia/Nemotron-PII** | English | 55+ PII/PHI categories, 100K synthetic records | English; methodology reference only. |
| **ZeroAgency/ru-big-russian-dataset** | Russian | **none — raw LLM-training text**, PII explicitly *filtered out* (`score.pii_leak < 1`) | 1.7M rows, MIT. **Not labeled**; opposite of what we need (it removes PII). |

**Conclusion for Part 1:** There is **no usable off-the-shelf all-types RU PII evaluation set**.
We must **build a synthetic golden set** backed by real checksum validators (Part 4). RU NER
corpora (Nerus, Collection3, NEREL) can still be used to *evaluate the ФИО/адрес ML branch*,
but not the structured IDs.

---

## PART 2 — Complete RU PII type list with detection method

Legend: **R** = regex only · **R+C** = regex + checksum/validation · **ML** = needs ML NER
(free-text, no fixed format) · **R+ML** = regex catches canonical forms, ML for free-text mentions.

| # | PII type (RU) | Detection | Notes |
|---|---|---|---|
| 1 | **ФИО** (фамилия/имя/отчество) | **ML** (+ dictionary/morphology assist) | No fixed format; needs NER. Natasha parses PER → first/last/middle via Yargy + pymorphy. GLiNER also works. Regex alone is unreliable (capitalized words). |
| 2 | **Телефон РФ** | **R** | `+7 / 8 / 7` + 10 digits, many separators. Optional normalization to E.164. No checksum. |
| 3 | **Email** | **R** | Presidio `EMAIL_ADDRESS` (RFC-822-ish) reusable as-is. |
| 4 | **СНИЛС** | **R+C** | 11 digits `XXX-XXX-XXX YY`; last 2 = control via **mod 101** (Part 3). |
| 5 | **ИНН-10** (юр. лицо) | **R+C** | 10 digits; 1 control digit, weights `[2,4,10,3,5,9,4,6,8]`, mod 11 → mod 10. |
| 6 | **ИНН-12** (физ. лицо/ИП) | **R+C** | 12 digits; 2 control digits, two weight vectors (Part 3). |
| 7 | **Паспорт РФ** (серия+номер) | **R** (weak, context-boosted) | `СС СС НННННН` = 4-digit series + 6-digit number (10 digits). **No checksum** → high false-positive risk; rely on `\b\d{2}\s?\d{2}\s?\d{6}\b` + context words («паспорт», «серия», «выдан»). |
| 8 | **Адрес** | **R+ML** | Regex for postal index / «ул./д./кв.» markers; ML (Natasha `AddrExtractor`, GLiNER) for free-text. |
| 9 | **Дата рождения** | **R + context** | Date regex (`DD.MM.YYYY`, etc.) is easy; *distinguishing birth date* needs context («дата рождения», «род.», «д.р.») or ML. Presidio `DATE_TIME` + context window. |
| 10 | **Номер банковской карты** | **R+C** | 13–19 digits; **Luhn** (mod 10). Presidio `CREDIT_CARD` reusable (does Luhn). |
| 11 | **Полис ОМС** (ЕНП) | **R+C** | Единый номер полиса = **16 digits**, last digit = control via **Luhn/Mod10** (per ФОМС/ISO 27931). Older format: серия (6) + номер (10). |
| 12 | **Водительское удостоверение** | **R** | Modern (2011+): **10 digits** = 4-digit серия + 6-digit номер (`\b\d{2}\s?\d{2}\s?\d{6}\b` — same shape as passport! disambiguate by context «в/у», «права»). Old format had letters. No public checksum. |
| 13 | **Автомобильный номер (ГРЗ)** | **R** | Format `Б ЦЦЦ ББ ЦЦ(Ц)`: 1 letter + 3 digits + 2 letters + 2–3 region digits. Only 12 Cyrillic letters allowed: **А В Е К М Н О Р С Т У Х** (look-alikes to Latin). No checksum. |

Also worth adding (RU legal-entity context, optional): **ОГРН** (13)/**ОГРНИП** (15), **КПП** (9),
**БИК** (9), **р/с** (20), **к/с** (20) — all R+C via `petrovna`/`vitya`.

**Method summary**: REGEX-only → телефон, email, паспорт, ВУ, ГРЗ, (адрес markers).
REGEX+CHECKSUM → СНИЛС, ИНН-10, ИНН-12, карта, полис ОМС (+ОГРН/р/с if needed).
ML NER → ФИО, адрес (free text), дата рождения disambiguation.

---

## PART 3 — Checksum / validation algorithms (LOAD-BEARING)

> All three verified against authoritative sources and cross-checked with the worked example
> for СНИЛС. ИНН weight vectors confirmed against ФНС-derived implementations and against the
> `petrovna`-based recognizer in `gbvolkov/data_protection`.

### 3.1 СНИЛС — 11 digits, control = last 2 (mod 101)

Source: official ПФР algorithm (КонсультантПлюс `cons_doc_LAW_142584`), Wikipedia «Контрольное число».

```
Input:  11 digits. base = first 9 digits d[1..9]; control = last 2 digits (d10 d11).
Step 1: sum = Σ d[i] * (10 - i)   for i = 1..9
        i.e. weights left→right = 9,8,7,6,5,4,3,2,1
              (each digit * its position counted FROM THE RIGHT of the 9-digit base)
Step 2: control_calc =
            if sum  < 100:  sum
            elif sum == 100 or sum == 101: 0       # remainder rule edge
            else:           sum mod 101
                              (and if that remainder == 100, control_calc = 0)
Step 3: valid  <=>  control_calc == (the two-digit control field, as integer)
Validity scope: only insurance numbers > 001-001-998 are checksum-checked.
```

Worked example (from the standard): СНИЛС `112-233-445 95`
base = 112233445 → 1·9+1·8+2·7+2·6+3·5+3·4+4·3+4·2+5·1 = 9+8+14+12+15+12+12+8+5 = **95**.
95 < 100 → control = **95** → matches the stated control field → **valid**. ✓

### 3.2 ИНН-10 (legal entity) — 10 digits, 1 control digit (mod 11 → mod 10)

Source: ФНС algorithm; confirmed by `gbvolkov/data_protection` (`recognizers/regex_recognisers.py`).

```
weights10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]      # applied to digits d[0..8]
n = (Σ weights10[i] * d[i]) mod 11
n = n mod 10                                   # if n > 9, take last digit
valid  <=>  n == d[9]                          # the 10th digit
```

### 3.3 ИНН-12 (individual / ИП) — 12 digits, 2 control digits

```
weights11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]        # for the 11th digit, over d[0..10]
weights12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]     # for the 12th digit, over d[0..10]
n11 = ((Σ weights11[i] * d[i]) mod 11) mod 10
n12 = ((Σ weights12[i] * d[i]) mod 11) mod 10
valid  <=>  n11 == d[10]  AND  n12 == d[11]
```

Reference implementation (verbatim, the patched `petrovna` logic from `gbvolkov/data_protection`):

```python
def check_digits(_inn, coefficients):
    n = 0
    for idx, coefficient in enumerate(coefficients):
        n += coefficient * int(_inn[idx])
    return n % 11 % 10

if len(inn) == 10:
    valid = check_digits(inn, [2, 4, 10, 3, 5, 9, 4, 6, 8]) == int(inn[9])
elif len(inn) == 12:
    n11 = check_digits(inn, [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
    n12 = check_digits(inn, [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
    valid = n11 == int(inn[10]) and n12 == int(inn[11])
```

> Note: `n % 11 % 10` is the idiomatic "if >9 take mod 10" — for ИНН the only case where
> `n % 11` exceeds 9 is when it equals 10, which maps to 0; correct.

### 3.4 Bank card — Luhn (mod 10)

Source: standard Luhn; confirmed by `gbvolkov/data_protection` `validate_card` and Presidio `CREDIT_CARD`.

```
digits = [int(c) for c in number if c.isdigit()]   # 13..19 digits
checksum = 0
for i, d in enumerate(reversed(digits)):
    if i % 2 == 1:          # every 2nd digit from the right
        d *= 2
        if d > 9: d -= 9
    checksum += d
valid  <=>  checksum % 10 == 0
```

### 3.5 Полис ОМС (ЕНП) — 16 digits, Luhn/Mod10

Source: ФОМС / ТФОМС структура ЕНП (rostov-tfoms «enp-struct»), references ISO/HL7 27931:2009 Mod10.
The 16th digit is the control digit, computed with the **same Luhn (Mod10)** procedure as 3.4
applied over the first 15 digits. (Older paper polis: серия 6 + номер 10, no public checksum.)

---

## PART 4 — Reusable GitHub / OSS detection components

### 4.1 Microsoft Presidio (the engine)

- Repo: `microsoft/presidio` (MIT). Use `presidio-analyzer` for detection,
  `presidio-anonymizer` for masking/tokenization.
- **Predefined recognizers directly reusable for RU text** (language-agnostic patterns):
  - `EMAIL_ADDRESS` — reuse as-is (email type 3).
  - `CREDIT_CARD` — reuse as-is; **does Luhn** (type 10).
  - `IP_ADDRESS`, `IBAN_CODE`, `CRYPTO`, `URL`, `PHONE_NUMBER` (phonenumbers lib),
    `DATE_TIME` (for birth-date branch + context), `MAC_ADDRESS`.
  - `PERSON`, `LOCATION`, `NRP` — only as good as the NLP engine; for RU prefer Natasha/GLiNER.
- **No Russian-specific recognizers ship with Presidio** (it has US/UK/ES/IT/PL/SG/AU/IN/FI/KR/NG/TH,
  but **not RU**). So СНИЛС/ИНН/паспорт/ОМС/ВУ/ГРЗ must be **custom recognizers**.
- Two ways to add custom RU recognizers:
  - **`PatternRecognizer`** — regex + context words (good for passport/phone/ОГРН).
  - **`EntityRecognizer` subclass** — regex match **+ checksum validation** in `analyze()`
    (the correct pattern for СНИЛС/ИНН/карта/ОМС — set high score on checksum pass, low on fail).
- Language wiring: each recognizer has `supported_language`; either run a RU spaCy/Stanza
  NlpEngine, or (as `arshinov-dev` does) run the multilingual `xx` / `xx_ent_wiki_sm` model and
  register recognizers under `"xx"`. Docs: `microsoft.github.io/presidio/analyzer/adding_recognizers/`,
  `.../analyzer/languages/`.

### 4.2 Ready-made RU recognizer packs on GitHub (REUSE THESE)

| Repo | What it gives | Notes |
|---|---|---|
| **`gbvolkov/data_protection`** — `recognizers/regex_recognisers.py` | Presidio recognizers for **RU_PASSPORT, SNILS (checksum via `petrovna`), INN-10/12 (checksum), RU_BANK_ACC, CREDIT_CARD (Luhn), PHONE**. Includes a **patched `validate_inn`** (upstream petrovna had a missing `else`). | **Closest match to our need.** Copy the `EntityRecognizer` subclasses (SNILS/INN/card) and the `validate_inn`/`validate_card` functions directly. |
| **`gbvolkov/PalimpsestLib`** — `palimpsest/recognizers/regex_recognisers.py` | Same family, packaged as a lib (Palimpsest anonymization toolkit). | Library-form of the above; good if we want a dependency vs. copy-paste. |
| **`arshinov-dev/pii-leak-detector`** — `pii_ner.py` | Full **PII taxonomy** (fio, address, snils, inn_person, inn_legal, bank_card, bik, bank_account, cvv, passport_rf, mrz, birth_date…), Presidio under `xx`, **birth-date via context regex**, masking helpers, Presidio→category mapping. | Best **architecture reference** for category design + birth-date-by-context + masking. |
| **`dradns/AI-IDE-BAS`, `kinzhalproject/AI-IDE-BAS`, `alpik941/AI-IDE-BAS`** — `pii-masking-proxy/.../recognizers.py` | RU passport + INN `PatternRecognizer`s in a masking proxy. | Forks of the same idea; lower priority. |
| **`IvanKorch1289/client_analyze_agent`** — `app/shared/pii_protection.py` | Custom `RU_ADDRESS`, `RU_PASSPORT`, `RU_PHONE`. | Address regex ideas. |
| **`Pioneer113/mcp-152fz-anonymizer`** — `analyzer_setup.py` | `RU_INT_PASSPORT`, СНИЛС with context. | 152-ФЗ-flavored; naming reference. |
| **`arterm-sedov/cmw-rag`** — `rag_engine/scripts/test_*` | `PASSPORT_RU`, `SNILS_RU` PatternRecognizers + spaCy-vs-regex test. | Test/eval scaffolding ideas. |

### 4.3 Validator libraries (checksums — don't hand-roll)

- **`petrovna`** (PyPI, MIT). `validate_snils`, `validate_inn`, `validate_ogrn`, `validate_ogrnip`,
  `validate_kpp`, `validate_bic`, корр./расч. счёт. **Use for СНИЛС/ИНН/ОГРН/счета.**
  ⚠️ Known bug: `validate_inn` historically missed an `else` branch (returned valid on wrong
  checksum) — `gbvolkov` ships a patched copy; verify the installed version or vendor the patch.
- **`hicebank/vitya`** (GitHub) — Pydantic validators for RU banking values (ИНН, КПП, БИК, счета, СНИЛС…). Good typed alternative.
- **`asiniy/faker-russian`**, **`DooGer1/russian-data-generator`** — generators for ФИО, ИНН,
  СНИЛС, ОГРН, addresses, phones. **Use to synthesize the golden set** (Part 5), guaranteeing
  checksum-valid samples.

### 4.4 ФИО / адрес — RU NER

- **Natasha** (`natasha/natasha`, MIT) — high-level API: `NamesExtractor` (PER→first/last/middle
  via **Yargy** + pymorphy), `AddrExtractor`, `DatesExtractor`, `MoneyExtractor`. Compact, CPU,
  no GPU. **First choice for ФИО + адрес + dates** in RU free text.
  - **Slovnet** (`natasha/slovnet`, MIT) — the DL NER behind Natasha; ~30 MB, CPU ~25 docs/s,
    1–2% below BERT SOTA. Wrappable as a Presidio `EntityRecognizer`.
  - **Yargy** (`natasha/yargy`) — rule grammars; use to add ГРЗ/passport-with-context rules.
- **GLiNER `urchade/gliner_multi_pii-v1`** (HF, **Apache-2.0**) — zero-shot PII NER (person,
  org, phone, address, passport number, email…), multilingual incl. RU-ish. **Wire via Presidio's
  built-in `GLiNERRecognizer`** (docs: `microsoft.github.io/presidio/samples/python/gliner/`).
  Strong for ФИО/адрес when Natasha misses, at higher compute. Also `E3-JSI/gliner-multi-pii-domains-v1`.
- **DeepPavlov** — RU NER models (ner_rus_bert, ontonotes), Apache-2.0. Heavier (BERT/GPU);
  use only if accuracy needs it over Slovnet.

### 4.5 Recommended wiring (the gateway pipeline)

```
text
 └─> Presidio AnalyzerEngine (NlpEngine: RU spaCy OR multilingual "xx")
      ├─ predefined: EMAIL_ADDRESS, CREDIT_CARD(Luhn), PHONE_NUMBER, IP, DATE_TIME, URL
      ├─ custom EntityRecognizers w/ checksum (from gbvolkov/data_protection, adapted):
      │    SNILS (mod101), INN-10/12 (mod11→10), CARD(Luhn), OMS(Luhn-16)
      ├─ custom PatternRecognizers (regex + context): PASSPORT_RU, DRIVER_LICENSE_RU, GRZ, ADDRESS markers
      ├─ ФИО/адрес ML: NatashaRecognizer (Slovnet/Yargy) OR GLiNERRecognizer(gliner_multi_pii-v1)
      └─ birth-date: DATE_TIME + birth-context window (per arshinov-dev pattern)
 └─> Presidio AnonymizerEngine -> tokenize/mask/encrypt per entity type
```

---

## PART 5 — Recommended 100-golden-case evaluation set design

**Why synthetic:** no labeled RU all-types set exists (Part 1), and using real PII is a 152-ФЗ
liability. Generate synthetic, **checksum-valid** data with `faker-russian` / `russian-data-generator`
+ `petrovna` (to guarantee valid IDs), embed into realistic RU sentences (SPY-style templates).

**Format:** JSONL, one case per line, with character-offset span labels (Presidio-eval / CoNLL-convertible):

```json
{
  "id": "case_017",
  "text": "Иванов Иван Петрович, СНИЛС 112-233-445 95, ИНН 770708389312, тел. +7 (912) 345-67-89.",
  "spans": [
    {"type": "FIO",   "start": 0,  "end": 20, "value": "Иванов Иван Петрович"},
    {"type": "SNILS", "start": 28, "end": 41, "value": "112-233-445 95"},
    {"type": "INN",   "start": 47, "end": 59, "value": "770708389312"},
    {"type": "PHONE", "start": 65, "end": 84, "value": "+7 (912) 345-67-89"}
  ],
  "domain": "gosuslugi_form"
}
```

**Coverage matrix — all 13 types, ~100 cases.** Each type appears in ≥6 positive cases, across
formats and contexts; plus hard negatives and tricky overlaps.

| Type | +cases | Format variations to include |
|---|---|---|
| ФИО | 12 | full ФИО, И.О. initials, genitive/dative inflection, ФИО in address line, foreign-transliterated |
| Телефон | 10 | `+7`, `8`, `(XXX)`, dashes/spaces/dots, no separators, inline «тел.» |
| Email | 6 | plain, with `+tag`, cyrillic-domain edge, uppercase |
| СНИЛС | 8 | `XXX-XXX-XXX YY`, no separators, valid + invalid-checksum (negative) |
| ИНН-10 | 6 | with/without «ИНН», valid + invalid-checksum |
| ИНН-12 | 6 | физлицо, with «ИНН №», valid + invalid-checksum |
| Паспорт | 8 | `СС СС НННННН`, `СССС НННННН`, with «серия/номер/выдан», bare 10-digit (ambiguous) |
| Адрес | 10 | full postal w/ index, «г. … ул. … д. … кв. …», abbreviations, free-text |
| Дата рождения | 8 | `DD.MM.YYYY`, `DD месяц YYYY`, with «д.р.»/«род.», + a non-birth date (negative) |
| Карта | 6 | 16-digit grouped/ungrouped, Visa/MC/Мир BINs, valid Luhn + invalid (negative) |
| Полис ОМС | 6 | 16-digit ЕНП (valid Luhn), old серия+номер |
| ВУ | 6 | `СС СС НННННН`, with «в/у»/«права» (disambiguate from passport) |
| ГРЗ | 6 | `А123ВС 77`, `А123ВС 199`, lowercase, Latin look-alike (negative) |

**Plus ~15 hard-negative / mixed cases:**
- ОГРН (13/15 digits) that must NOT be flagged as ИНН.
- A phone-like string that is actually an order number (context says «заказ №»).
- Passport-shaped 10-digit that is a driver-license (context «в/у») and vice-versa.
- Invalid checksums for СНИЛС/ИНН/карта/ОМС → must be **rejected** (tests the C in R+C).
- ГРЗ with Latin letters (invalid) and with non-allowed Cyrillic letters.
- Multiple entities in one sentence with adjacent/overlapping spans (boundary tests).
- A document with zero PII (true negative).

**Metrics:** per-type precision/recall/F1 + span-exact and token-overlap, run via
`microsoft/presidio-research` (`presidio_evaluator`) which consumes exactly this span format.

**Generation recipe:**
1. Write ~40 RU templates with `{FIO}`, `{SNILS}`, `{INN12}`, … placeholders (gosuslugi forms,
   medical intake, banking, support tickets, contracts — mirror SPY's domain split).
2. Fill via `faker-russian`/`russian-data-generator`; **pass every ID through `petrovna`** so
   positives are checksum-valid; for negative-checksum cases, mutate one digit and assert invalid.
3. Compute spans programmatically at fill time (offsets are exact, no manual labeling).
4. Freeze 100 cases; keep the generator to expand later.

---

## Sources

Datasets / NER:
- Nerus / Natasha ecosystem — https://github.com/natasha/natasha , https://github.com/natasha/nerus
- Collection3 / FactRuEval — https://www.researchgate.net/publication/262203599 ; https://www.researchgate.net/publication/309151030
- NEREL — https://arxiv.org/pdf/2108.13112
- RuNNE-2022 — https://arxiv.org/pdf/2205.11159
- RURED — https://www.researchgate.net/publication/346752013
- AlexKly/Detailed-NER-Dataset-RU — https://github.com/AlexKly/Detailed-NER-Dataset-RU
- SPY dataset — https://huggingface.co/datasets/mks-logic/SPY ; https://github.com/LogicZMaksimka/SPY_Dataset ; https://aclanthology.org/2025.naacl-srw.23/
- ai4privacy — https://huggingface.co/datasets/ai4privacy/pii-masking-300k
- nvidia Nemotron-PII — https://huggingface.co/datasets/nvidia/Nemotron-PII
- ZeroAgency/ru-big-russian-dataset — https://huggingface.co/datasets/ZeroAgency/ru-big-russian-dataset

Checksums:
- СНИЛС (ПФР) — https://www.consultant.ru/document/cons_doc_LAW_142584/1d9155a863a5949b14b95ecbb536aa84856a2a2e/ ; https://ru.wikipedia.org/wiki/Контрольное_число
- ИНН (ФНС) — https://logachev.pro/programmirovanie/proverka-inn-po-kontrolnoy-summe-php-javascript/ ; https://calcal.ru/validator-inn
- Luhn / карта — Presidio CREDIT_CARD; gbvolkov validate_card (below)
- Полис ОМС (ЕНП, Mod10) — https://rostov-tfoms.ru/services/zasedaniya-rabochih-grupp/erp/enp-struct ; https://www.consultant.ru/document/cons_doc_LAW_98654/4370570773dbf9366f62cc1c7a6de248c2e0296e/

Components:
- Microsoft Presidio — https://github.com/microsoft/presidio ; supported entities https://microsoft.github.io/presidio/supported_entities/ ; adding recognizers https://microsoft.github.io/presidio/analyzer/adding_recognizers/ ; GLiNER sample https://microsoft.github.io/presidio/samples/python/gliner/ ; presidio-research https://github.com/microsoft/presidio-research
- RU recognizer packs — https://github.com/gbvolkov/data_protection ; https://github.com/gbvolkov/PalimpsestLib ; https://github.com/arshinov-dev/pii-leak-detector ; https://github.com/dradns/AI-IDE-BAS
- Validators — petrovna https://pypi.org/project/petrovna/ ; vitya https://github.com/hicebank/vitya
- Natasha/Slovnet/Yargy — https://github.com/natasha/natasha ; https://github.com/natasha/slovnet ; https://github.com/natasha/yargy ; https://natasha.github.io/ner/
- GLiNER PII — https://huggingface.co/urchade/gliner_multi_pii-v1 ; https://huggingface.co/E3-JSI/gliner-multi-pii-domains-v1
- Generators — https://github.com/asiniy/faker-russian ; https://github.com/DooGer1/russian-data-generator
- ГРЗ format — https://en.wikipedia.org/wiki/Vehicle_registration_plates_of_Russia
