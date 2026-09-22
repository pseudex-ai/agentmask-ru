# Brief — component `comparator` (owner code **F**)

You build `form_match(type, produced, reference) -> FormVerdict`: the
deterministic check «is the FORM of one string the form of another», per PII
type, with the exact feature names of `docs/tz-agentpii5.md` §8.4. It is the
main new axis of v5. It must be written WITHOUT importing `pseudex/` — an
instrument that imports the engine cannot fail the engine — and without any
dictionary of the engine's (no names list, no street list). pymorphy3 (a
third-party morphological dictionary) IS allowed for `gram_case`; nothing
else external.

## Read first, in this order

1. `docs/tz-agentpii5.md` §1, §1.1, §8.4.
2. `bench/agentpii5/contracts.py` §4: `FORM_FEATURES`, `FEATURE_LABELS`,
   `TRANSLIT_TABLES`, `FIELD_SEP`, `FormVerdict`, `FormMatcher`,
   `FeatureExtractor`, `feature_pairs()`.
3. `bench/agentpii5/CHECKLIST.md` items marked **F** (C-019–C-026, C-170–C-181).
4. `bench/agentpii4/parts.py` — the ONE splitter the benchmark allows on
   unknown text (`parts_of`, `_PATRONYMIC_TAIL`, `_PLATE`, `_DATE_*`). You
   may import `bench.agentpii4.parts` (it imports no `pseudex`) for the
   patronymic tail and the date regexes; you may not import
   `pseudex.morph_names`, `pseudex.morph_places`, `pseudex.translit`,
   `pseudex.date_form`, `pseudex.agent_form` — those are the engine's own
   opinions on the very question you decide.
5. `~/.claude/...` is not available to you; the product policy in one line:
   the engine must mirror the customer's form on the way in and the agent's
   form on the way out, for every type, with no «the tool wants X» exception.
   Your comparator is what turns a violation of that into a number.

## Rules

- Comments in English; docstrings are the design record; no default
  parameter values; strict typing; no `Any`.
- **Pure and deterministic**: no I/O, no randomness, no global state; the
  same pair gives the same verdict in any process.
- **Every feature is extracted from ONE string** (`FeatureExtractor`) into a
  label of `FEATURE_LABELS[(type, feature)]`, then compared pairwise. The
  verdict's `differs` is the set of features whose labels differ. `same` iff
  `differs` is empty. Never add a feature outside `FORM_FEATURES`, never skip
  one: the test asserts the extractor keys equal `contracts.feature_pairs()`.
- `form_match` raises `ValueError` for a type without features.
- `FIELD_SEP` (`\x1f`) joins the leaves of a multi-field value; treat it as
  the strongest separator (it decides `by_fields`, it is not a comma).
- Do not commit. Test: `cd prototype && source .venv/bin/activate && python3
  -m bench.agentpii5.test_form`.

## Files to create

| file | what |
|---|---|
| `bench/agentpii5/form.py` | `FEATURE_EXTRACTORS: dict[tuple[str, str], FeatureExtractor]`, `form_match`, `features_of(type, text) -> dict[str, str]` (every feature's label, for the report's histogram) |
| `bench/agentpii5/test_form.py` | see «Acceptance tests» |

You may put the transliteration signatures and the generic-word tables in
`form.py` or in `bench/agentpii5/form_tables.py`; nothing else.

## The extractors — exact rules

Letters = Unicode alphabetic characters; «Cyrillic» = in the Cyrillic block;
«word» = a maximal run of letters, digits, hyphens and apostrophes.

### NAME

- `case_class`: over all letters — all lower → `lower`; all upper and ≥ 2
  letters → `upper`; every word has its first letter upper and the rest
  lower (initials like «И.» count as title) → `title`; else `mixed`.
- `gram_case`: for every Cyrillic word of ≥ 2 letters (hyphen-parts
  separately, initials excluded) take pymorphy3's best parse
  (`MorphAnalyzer().parse(word)[0]`), read `tag.case` (`nomn`, `gent`,
  `datv`, `accs`, `ablt`, `loct`); vote by count, tie → the case of the
  FIRST voting word; no voting word → `unknown`. Build the analyzer once at
  module import.
- `order`: split into parts (whitespace); role each part — `P` if it ends
  with `parts._PATRONYMIC_TAIL`, `S` if it matches the surname-suffix regex
  `(ов|ев|ёв|ин|ын|ск|цк|ой|ий|ая|яя|ых|их|ко|ук|юк|енко|ман|ер)(а|у|ым|ом|е|ой|ую|ая|ие|ых|им|ими|ого|ому)?$`
  (case-insensitive) and is not `P`, else `G`; sequence `[S,G,P]`/`[S,G]` →
  `F-I-O`; `[G,S]` → `I-F`; `[G,P,S]` → `I-O-F`; one part → `single`; else
  `other`. Heuristic on purpose — both strings are the same person, so a
  consistent heuristic compares correctly; test it on the examples below.
- `parts`: number of whitespace-separated parts: `1`, `2`, `3`, `4+`.
- `initials`: count tokens matching `^[А-ЯЁA-Z]\.$` (or `И.О.` joined):
  0 → `none`, 1 → `given`, ≥ 2 → `given_patronymic`.
- `script`: all letters Cyrillic → `cyrillic`; Latin and Cyrillic both
  present → `mixed`; all Latin → decide the table by digraph SIGNATURES
  present anywhere in the lower-cased string, first match wins in this
  order: `shch`, `iu`, `ia`, `ii` (word-final) → `latin:icao`;
  `shh`, `cz`, `yu`+`j`, `ya`+`j`, `e'` → `latin:gost`; `yu`, `ya`, `kh`,
  `ts`, `y` (word-final) → `latin:bgn`; nothing discriminating →
  `latin:unknown`. Write the three tables from their standards (ICAO Doc
  9303, ГОСТ 7.79-2000 system B, BGN/PCGN) in a `TRANSLIT_SIGNATURES` table
  with a comment citing each.
- `hyphen_particle`: a hyphen inside a word → `hyphen`; a particle token in
  `{де, фон, ван, дер, оглы, кызы, ибн, бен, аль, эль, дель, ди, да, ла, ле,
  ду, дос}` (case-insensitive) → `particle`; both → `both`; else `none`.

### PHONE

- Strip to digits + keep the original for separators. `prefix`: text starts
  with `+7` → `plus7`; 11 digits starting with `8` → `eight`; 11 digits
  starting with `7` without `+` → `seven`; 10 digits → `bare`.
- `grouping`: after removing the prefix digit(s), the sizes of digit runs
  separated by non-digits: `[3,3,2,2]` → `3-3-2-2`; `[3,3,4]` → `3-3-4`;
  `[10]` → `solid`; else `other`.
- `separators`: the set of non-digit characters between digit runs,
  excluding `(`, `)` and `+`: empty → `none`; `{" "}` → `space`; `{"-"}` →
  `hyphen`; `{"."}` → `dot`; else `mixed`.
- `parens`: `(` present → `yes`, else `no`.

### LOC

- `case_class`: as NAME, over words that are not markers (`ул`, `д`, `кв`…).
- `generic`: search words for a FULL generic word (`улица, проспект,
  переулок, бульвар, шоссе, площадь, набережная, проезд, аллея, тупик,
  микрорайон, квартал, линия, тракт` in any case form — match by stem
  `улиц|проспект|переулк|переулок|бульвар|шоссе|площад|набережн|проезд|алле|тупик|микрорайон|квартал|лини|тракт`)
  → `full:<stem>`; else an ABBREVIATION token (`ул`, `ул.`, `пр-т`, `пр.`,
  `просп.`, `пер.`, `пер`, `б-р`, `ш.`, `пл.`, `наб.`, `пр-д`, `мкр`, `мкр.`,
  `кв-л`) → `abbr:<token lower-cased, dot kept>`; else `none`. `д.` followed
  by digits is a HOUSE marker, not a generic; `г.`/`г`/`город`, `с.`,
  `пос.`, `д.` followed by a word are SETTLEMENT markers (used by
  `city_present`).
- `generic_position`: generic token before the street-name word → `before`;
  after → `after`; no generic → `none`. The street-name word = the first
  word that is not a generic, not a settlement marker, not a marker, not
  digits, in the segment holding the generic.
- `house_marker`: `д. 10` → `d_dot_space`; `д.10` → `d_dot_nospace`; `д 10`
  → `d_nodot`; `дом 10` → `dom`; a number with no marker → `none`; anything
  else before the house number → `other`.
- `flat_marker`: same scheme with `кв.`/`кв`/`квартира` → `kv_dot_space`,
  `kv_dot_nospace`, `kv_nodot`, `kvartira`, `none`, `other`.
- `commas`: `,` present → `yes`, else `no`.
- `city_present`: a settlement marker present, OR a comma-separated segment
  (or `FIELD_SEP` field) with no digits, no street generic, no marker and
  1–2 words, standing first or last → `yes`; else `no`.
- `city_position`: the position of that segment: `first`, `last`, `middle`
  (only via a settlement marker in the middle), `none`.
- `by_fields`: `FIELD_SEP` in text → `fields`, else `string`.
- `building_entrance_markers`: the sorted set of `korp` (`корп`, `к.`,
  `корпус`), `str` (`стр`, `строение`), `podezd` (`под`, `подъезд`, `п.`),
  `etazh` (`эт`, `этаж`), `lit` (`лит`, `литера`) present →
  `markers:<a+b+…>`; none → `none`.

### DOB / DATE (same extractors, registered under both types)

- `notation`: `\d{1,2}\.\d{1,2}\.\d{2,4}` → `dmy_dots`; `\d{1,2}/\d{1,2}/\d{2,4}`
  → `dmy_slashes`; `\d{4}-\d{2}-\d{2}` → `iso`; a month word (`январ…`,
  `феврал…`, …) → `words`; `\d{8}` alone → `solid`; else `other`.
- `separator`: the character between day and month: `dot`, `slash`,
  `hyphen`, `space` (words with a space), `none`.
- `padding`: day and month both two digits → `padded`; else `unpadded`
  (for `words`: day two digits → padded).
- `year_len`: `2`, `4`, or `none` (no year).
- `month_form`: numeric month → `number`; month word ending in a nominative
  form (`январь`, `март`, `май`…) → `word_nominative`; genitive (`января`,
  `марта`, `мая`…) → `word_genitive`.

### EMAIL — `case_class` over letters: `lower` / `upper` / `mixed`.

### CARD — `grouping`: digit runs `[4,4,4,4]` → `4x4`; `[16]` → `solid`;
else `other`. `separator`: `space` / `hyphen` / `none` (mixed → `none`
only when there is no separator; else the first separator seen).

### SNILS — `separators`: `\d{3}-\d{3}-\d{3} \d{2}` → `canonical`; `\d{11}` →
`solid`; else `other`.

### INN — `length`: digit count `10` / `12` / `other`; `separators`: `none`
/ `space` / `other`.

### PASSPORT — `series_number_split`: digit runs `[2,2,6]` → `2-2-6`;
`[4,6]` → `4-6`; `[10]` → `solid`; else `other`.

### PLATE — `case_class` over letters (`lower`/`upper`/`mixed`); `spaces`:
any whitespace → `yes`; `region_sep`: whitespace immediately before the
final 2–3 digits → `space`; none → `none`; another character → `other`.

## `form_match`

```
def form_match(type: str, produced: str, reference: str) -> FormVerdict
```
1. `type not in FORM_FEATURES` → `ValueError`.
2. For each feature of the type: `a = extractor(produced)`,
   `b = extractor(reference)`; add the feature to `differs` iff `a != b`.
3. Return `FormVerdict(same=not differs, differs=frozenset(differs))`.

## Acceptance tests you must ship — `bench/agentpii5/test_form.py`

- `test_no_pseudex` — import `bench.agentpii5.form`; no `sys.modules` key
  starts with `pseudex`; also `grep`-style: the source of `form.py` contains
  no line starting with `from pseudex` / `import pseudex`.
- `test_extractor_keys_equal_contract` — `set(FEATURE_EXTRACTORS) ==
  set(contracts.feature_pairs())`.
- `test_labels_closed` — for every extractor and every string in the fixture
  table, the label is in `FEATURE_LABELS[pair]`, or starts with one of its
  `*`-prefixes.
- `test_verdict_consistency` — for every fixture pair `same == (not differs)`
  and `differs <= set(FORM_FEATURES[type])`.
- `test_deterministic` — every fixture pair judged twice gives equal verdicts.
- `test_symmetry_of_features` — `differs` is the same for `(a, b)` and
  `(b, a)` (feature labels are compared, so the set must be symmetric).
- Per type — `test_name_features`, `test_phone_features`, `test_loc_features`,
  `test_date_features` (DOB and DATE), `test_email_features`,
  `test_card_features`, `test_snils_features`, `test_inn_features`,
  `test_passport_features`, `test_plate_features`: for EVERY feature of the
  type, ≥ 1 pair whose verdict is `same` and ≥ 1 pair whose `differs` is
  EXACTLY `{feature}`. Minimum pairs to include (add more):
  - NAME: («Иванов Пётр», «Иванов Пётр») same; («иванов пётр», «Иванов
    Пётр») → {case_class}; («Иванову Петру», «Иванов Пётр») → {gram_case};
    («Пётр Иванов», «Иванов Пётр») → {order}; («Иванов Пётр Сергеевич»,
    «Иванов Пётр») → {parts}; («Иванов П.», «Иванов Пётр») → {initials};
    («Ivanov Petr», «Иванов Пётр») → {script}; («Petrov Iurii», «Petrov
    Yuriy») → {script} (icao vs bgn); («Иванов-Петров Пётр», «Иванов Пётр»)
    → {hyphen_particle}.
  - PHONE: («+7 916 123-45-67», «8 916 123-45-67») → {prefix};
    («+79161234567», «+7 916 123 45 67») → {grouping, separators};
    («+7 (916) 123-45-67», «+7 916 123-45-67») → {parens}.
  - LOC: («ул. Ленина, д. 14, кв. 3», «улица Ленина, дом 14, квартира 3») →
    {generic, house_marker, flat_marker}; («Ленина 14», «ул. Ленина 14») →
    {generic}; («Самара, Ленина 14», «Ленина 14, Самара») → {city_position};
    («Ленина 14», «Самара, Ленина 14») → {city_present, city_position,
    commas}; («Ленина\x1f14», «Ленина 14») → {by_fields}; («Ленина 14
    корп. 2», «Ленина 14») → {building_entrance_markers}.
  - DOB: («14.03.1987», «14/03/87») → {notation, separator, year_len};
    («14 марта 1987», «14.03.1987») → {notation, separator, month_form};
    («4.3.1987», «04.03.1987») → {padding}; («1987-03-14», «14.03.1987») →
    {notation, separator}.
  - EMAIL: («Ivan@Mail.ru», «ivan@mail.ru») → {case_class}.
  - CARD: («2200 1234 5678 9010», «2200123456789010») → {grouping, separator}.
  - SNILS: («112-233-445 95», «11223344595») → {separators}.
  - INN: («7707083893», «770708389312») → {length}; («7707 083893»,
    «7707083893») → {separators}.
  - PASSPORT: («45 09 123456», «4509 123456») → {series_number_split}.
  - PLATE: («а123вс 77», «А123ВС 77») → {case_class}; («А123ВС77», «А123ВС
    77») → {spaces, region_sep}.
- `test_by_fields_sentinel` — `FIELD_SEP` decides `by_fields` and is not a
  comma.
- `test_unknown_type_raises`.

## What you must NOT touch

`bench/agentpii4/**`, `pseudex/**`, `public/**`, every other
`bench/agentpii5/` file. Contract questions go in your final message.

## Checklist items you own

C-003 (determinism), C-019–C-026, C-170–C-181 (histogram half is M).

## Definition of done

`python3 -m bench.agentpii5.test_form` prints PASS; `grep -n "pseudex"
bench/agentpii5/form.py` shows only the docstring; final message lists files,
commands, output, questions.
