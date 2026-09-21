# INVARIANTS — rules that changes must not break

Every rule here was paid for: by a leak, a broken tool call, a false mask, a
false red, or a customer-facing number that was wrong. The rule says what may
not change; the two to four lines under it say which failure it closes, with
the number when one was measured; **Pins** names the in-repo test that goes red
when the rule is broken. The story of how each was found — what was tried,
what it cost, why the alternative lost — lives in [STATE.md](STATE.md).

**UNPINNED** means no in-repo test holds the rule: it was validated by reading
the code or on an external corpus (NEREL, MASSIVE, RuDevices — in
`~/.cache/pseudex-bench/`, run through `bench/`). Those are listed again at the
end as the test backlog. `wiki/check.py` refuses a rule that names no test and
is not marked UNPINNED.

Anchors (`#address`, `#vault`, …) are referenced from [MAP.md](MAP.md).

---

## Engine-wide

- **Fail closed.** Any error in masking propagates to a 5xx; never fall back to
  passing text through unmasked. The caller treats an error as a block, and that
  is the whole safety story. Pins: `test_perf_masking` (leak regression),
  `test_loop`.
- **No PII pre-filter, ever.** A `maybe_contains_pii` gate existed, silently
  stopped being a superset of the recognizers (Latin names, `{"name":"john"}`)
  and leaked raw PII. The content cache removes the repeated-work cost; detection
  always runs. Pins: `test_perf_masking`.
- **Never re-feed masked output into detection.** `mask(mask(x)) != mask(x)` — a
  fake phone is a valid phone shape. The cache keys on RAW content; «skip
  already-masked messages» is a wrong optimization. Pins: `test_hard_cases`
  (`test_masked_output_is_not_remasked`, `test_repeated_masking_is_stable`).
- **No bundle means no detection, not less.** `pseudex/names.py` once treated an empty
  dictionary as a supported state; a gateway detecting with half its gazetteer
  leaks silently, which is worse than a stopped service. `BundleNotLeased` is
  raised, `/mask` answers 503. Pins: `test_tuning_lease_security`,
  `test_unload_scrub`.
- **`pseudex/` never imports from `licensing/`.** The import would drag the
  authored assets into the image and defeat the lease. Shared code goes the
  other way (`pseudex/bundle.py` is imported BY the server). Pins:
  `e2e/pack_gates.py P1` (no `/app/pseudex`, no asset strings in the image).
- **`pseudex/` never `import sqlite3`.** Stdlib sqlite3 accepts `PRAGMA key`
  without raising and writes plain text — a product that claims encryption and
  has none. One driver (`sqlcipher3`), no branch; both Dockerfiles fail the build
  on the import. The driver's exceptions are NOT subclasses of the stdlib ones.
  Pins: `e2e/pack_gates.py P9` (stdlib SQLite cannot open the release volume).
- **The engine writes nothing to its own filesystem** (`PYTHONDONTWRITEBYTECODE=1`),
  so «did the container write a file» has a clean answer. Pins: `e2e/gates.py L5`.
- **A leased regex carries its own case flag** (`(?i)` in the source). A uniform
  `re.IGNORECASE` turned `[А-ЯЁ][а-яё]+` from «a Capitalised word» into «any
  word»; «течение 12» became an address and the inflated LOC spans swallowed
  real people (−12 PERSON on NEREL). UNPINNED — measured on NEREL via
  `bench/eval_external_ner.py`.

## Morph compat

- **`_morph_compat` is imported before any `from natasha import …`.** It aliases
  pymorphy2 → pymorphy3 at module load; natasha binds the name eagerly, so a
  later import is too late. Pins: every detector test fails at import
  (`test_loop` is the cheapest).

## Pipeline

- **`pseudex/detect_all.py` is the only place that composes the pipeline**, and the
  order is normalize → recognizers → `context.suppress` → `_resolve`.
  Suppression after resolution cannot rescue a NAME a false LOC already swallowed.
  Pins: `test_overmasking`, `test_hard_cases`.
- **`_PRIORITY` is the arbiter:** checksum IDs 6 > phone/email 5 > ADDR 4 >
  NAME 3 > DATE/PASSPORT/LOC 2, longest-first, non-overlapping. `ADDR` exists
  solely to outrank a NAME inside a street name and is remapped to `LOC` after.
  Pins: `test_hard_cases` (`test_addresses`), `test_coverage_152fz`.
- **A KV-typed span carries its own evidence and skips `suppress`.** The KEY
  typed the value, which is stronger than any nearby word; re-gating it lost
  `{"passport": "4509123456"}` because the cue list holds «паспорт» and not the
  Latin «passport». Pins: `test_persona_defects`, `test_hard_cases`
  (`test_json_payload`).
- **Cheap gates run before morphology.** The bare-street pattern fires on any
  word plus a number and almost every hit dies on a set lookup or a regex;
  ordering those first is a third of the whole detection cost. UNPINNED —
  measured with `profile_deep.py`.

## Normalize

- **Normalization is 1:1.** Any substitution that changes length breaks every
  span offset downstream, including `/spans` (which the UI uses to highlight the
  original). Pins: `test_product`, `e2e/parity.py`.
- **A look-alike is folded only when it is not glued to a letter.** «ч» is a
  look-alike for 4; at a word edge «Валентинович» became «Валентинови4», the name
  span ended a character early and the orphaned «ч» glued itself to the
  substitute — a string in no vault, so `/unmask` and `/reveal` both returned
  nothing. Pins: `test_persona_defects`.

## Structured IDs

- **Checksum-gated, and the checksums stay in the binary.** СНИЛС mod 101, ИНН
  weight vectors, Luhn, ОГРН — they are the algorithm, not the tuned data; cue
  words and priority are leased. Pins: `test_coverage_152fz`, `test_product`.
- **A passport needs a cue, and the window after it is sixteen characters.**
  «Паспортные данные: 4518123456» needed nine and the pattern allowed eight.
  UNPINNED.
## Credentials

- **Credentials are anchored to published prefixes, never to entropy.** A git
  SHA, a UUID, a content hash and a base64 image are all high-entropy and none is
  a secret; `pk_live_` is publishable by Stripe's design; placeholders (`${VAR}`,
  `xxxx`, AWS's own EXAMPLE key) must not mask. Pins: `test_credentials`.

## Structured KV

- **A `KEY_TYPE` entry types the WHOLE value with no shape check, so an
  ambiguous business word may never be one.** «счёт» is an invoice more often
  than an account, «Реквизиты:» introduces a LIST — adding them cost 12 of 298 on
  the golden set because «Реквизиты: СНИЛС …, карта …» became one account number
  that swallowed the СНИЛС. Those words belong in `CTX_TYPES`, where the 20-digit
  shape keeps an invoice number out. Pins: `test_persona_defects`.
- **A TOOL RESULT arrives as JSON, and JSON puts a quote where prose puts a
  space.** `_TOK` held whitespace, comma, semicolon, paren, № and #, so
  `"addr": "г. Пермь, ул. Добролюбова, д. 154б"` lost its «г. » and
  `{"a": "д. 12, кв. 5"}` was not found at all — 189 of 267 leaked LOC tails on
  AgentPII v3; coverage 70.0% → 80.4%. Pins: `test_product`.

## Dates

- **A bare date is not personal data; it becomes personal by ASSOCIATION** —
  next to a personal identifier or a birth cue — and a document word directly
  before it («наряд от», «счёт от») wins over a person elsewhere in the sentence.
  A deny-list of document words fails open; this fails closed. Pins:
  `test_overmasking`, `test_persona_defects`.
- **A DOB substitute keeps the YEAR and the SIDE OF TODAY** — the owner's
  decision, one bit of leak budget beyond the year. The year alone left the
  derived age off by one in 37 triples. A year identifies nobody; day and month
  stay fake. Pins: `test_hard_cases` (`test_tool_result_with_a_future_date_masks`).
- **A spoken date is replaced by a date in words, and the span reaches the year
  without «года».** «родился одиннадцатого сентября пятьдесят пятого» was masked
  as «родился 28.03.1972 пятьдесят пятого». `spoken.date_to_words` mirrors the
  customer's century style; the ISO the agent writes resolves through
  `date_owner`. Pins: `test_hard_cases` (`test_spoken_birth_date_keeps_its_register`).

## Context

- **A cue word reaches 60 characters and never across a sentence end.** One
  «адрес» near the top of a system prompt licensed every capitalised-word-plus-
  number for the rest of it; the candidate's own first letter joins the tail
  before splitting, because a sentence end is a period FOLLOWED BY A CAPITAL and
  that capital is the span being judged. UNPINNED.
- **A cue word may be misspelt.** «пасспорт» and «догвор» disabled the guards
  the word provides; deny matching tolerates one edit, bounded at one and at a
  two-letter prefix. UNPINNED.
- **A cue word licenses its neighbour, it does not name it.** «фамилия волков»
  must mask «волков» (the bulk surname dictionary is capital-only) and «фамилия
  клиента не указана» must not — the cue AND morphology saying the word can
  name a person. Pins: `test_product`.
- **A settlement plus a number is not an address, and that is a VETO.** «погода
  в Сочи 25 градусов», «в Москве 12 филиалов» — a city takes no house number,
  whatever the context says. Street names that ARE toponyms («Тверская» ADJF,
  «Ленина» Surn) are untouched, checked across EVERY parse. UNPINNED — measured
  on NEREL via `bench/eval_external_precision.py`.
- **A marked street with no house number needs an INTENT word, not a
  preposition.** «на улицах Каира собрались десятки» opens with «на» too;
  `prep_before` alone cost 0.1pp of NEREL precision. `площад\w+` is excluded
  from that arm entirely (площадка, площади, площадью). Pins: `test_hard_cases`.

## Names

- **Never take `parse(word)[0]` for a gazetteer lookup.** «марину» has «марин»
  and «марина» at the SAME score and the winner is arbitrary; «запишите марину
  петрову» went to the model in the clear. Consider every name-tagged reading
  tied for first — unbounded costs 0.7pp NEREL precision («жене»→«Женя»).
  Pins: `test_hard_cases`, `test_persona_defects`.
- **A single-token NER person is kept unless the dictionary claims the word.**
  The gate demanded a known name or a Russian surname suffix and threw away
  Обама, Месси, Бейонсе. NEREL PERSON 80.6% → 91.5% at no precision cost; the
  `is_known` half is what makes it free (dropping it admits «Цветы», «Девочки» —
  72 on NEREL). UNPINNED — `bench/eval_external_ner.py`.
- **A mistyped name is reachable, but only with THREE signals:** adjacent to a
  detected name, within one edit of the gazetteer, AND unknown to morphology. In
  a 197k dictionary «заказ»→«Закар», «адрес»→«Адрей», «клиент»→«Клинт» are real
  rare surnames. Index by the DELETION NEIGHBOURHOOD (Mor-Fraenkel / SymSpell):
  the first-three/last-three filter reached 77.9% at length five. Pins:
  `test_product` (the «Яков Роман Карпов Василий» case), `bench/blocking_recall.py`
  for the index's completeness.
- **Extending a name to its neighbour needs two signals:** morphology says the
  neighbour can name a person AND its best reading is not a function word.
  Any-parse alone ate «В», «из», «по» in news prose. UNPINNED — NEREL.
- **A stray space inside a surname needs FOUR signals.** «Фёдо ров Кирилл»
  leaked half a surname. Joined must be a name or surname shape; the pair must
  touch a detected name; the left fragment may not be a function word («на» +
  «Лебедева» → «наЛебедева» passes the shape test); at least one fragment must
  not be a word AND the left one may not be a whole word of five letters or more.
  «Вол ков» is deliberately NOT joined. UNPINNED.
- **NER spans are trimmed to one token when the leading word is a verb.** The
  dictionary trim stopped at two, presuming «Имя Фамилия»; «Наберите Игорю»
  became one name and deleted the sentence's verb. UNPINNED.
- **A HYPHEN glues one token, and half of one is not a name.** «Лос-Анджелесе»
  reached the model as «Любовь-Анджелесе», «де-юре» as «де-Ивану» — 86 spans on
  933 NEREL documents, invisible to both instruments (NEREL precision credits a
  span overlapping ANY gold entity; the clean suite had no hyphenated toponym).
  The `_lowercase_dictionary_ok` test is asked of the WHOLE token, so «Жан-Клод»
  passes and «Петров-то» passes. UNPINNED — NEREL.
- **An invented lemma against 197k surnames is a lottery the dictionary wins.**
  pymorphy3 guesses «каока» for «каоке» and that guess is a real entry. The lemma
  path stays (it finds «джоли», «зеленского» — 365 hits) gated on morphology's
  own opinion of the word: consult the lemma only when the word is known, or when
  some reading calls it a name. Pins: `test_overmasking`.
- **A POSSESSIVE from a given name carries the BASE NAME.** «женин день
  рождения», «олино письмо» sit in no dictionary; three gates (the `Poss`
  reading, the base-name dictionary — «мамин», «бабушкин» have `Poss` and no
  name behind them — and agreement with the following noun). `span.value` is the
  vault key AND the source of gender, so «Женя» and «женин» must be ONE row.
  Pins: `test_hard_cases` («олино»).
- **`_LOWER_DICT_MIN = 5` is measured.** Lowering to 4 finds nine names and
  masks thirty ordinary words («вейп», «мега», «слыш», «джек») — three false
  masks per person found; every other instrument called the change free.
  UNPINNED — measured on MASSIVE + the clean suite.
- **A given name that is also a surname wins the tie.** `any(Surn)` is right
  for every real surname and wrong for «Регина» tied at 0.33 — the shape became
  (surn, surn, patr) and one person got two pseudonyms in one dialogue. UNPINNED.
- **The composite «neighbour unknown to morphology and both dictionaries» veto
  is REMOVED.** It looked principled and cost four real people (Ирина Аллегрова
  among them) to buy two fewer false masks on MASSIVE. Measure the price of any
  veto on MASSIVE before accepting it. UNPINNED — `bench/eval_massive_ru.py`.

## Name morphology

- **A name part with no dictionary NAME reading is not thereby indeclinable,
  and a surname-shaped word never out-votes the given name** (Б21). «София» is
  in OpenCorpora only as the city: `_name_parses` falls back to the feminine
  first-declension readings (lemma in -а/-я, known) so case, gender, nominative
  and inflection all see the same word; a part with a `Surn` reading votes with
  a surname's weight whatever `Name` tags its oblique forms carry. On the way
  back, a form syncretic between cases («Виктории Мещеряковой») restores in
  the case the CUSTOMER wrote (`Vault.written_form`, `cases_spelled_as`), not
  in pymorphy3's prior. Pins: `test_names_morphology` (its Б21 block forces
  the three pool draws that made the file flake).
- **Canonicalisation needs EVIDENCE of an oblique case.** pymorphy3 reaches the
  nominative through the lemma, which is masculine for surnames and invented for
  unknown ones. No conversion without evidence, none of a part already
  nominative; a gender target and a stem guard were both tried and removed —
  they broke «Руслану» and «Петру». Pins: `test_names_morphology`.
- **`to_nominative` is called from two sides and only one may carry a guard.**
  `canonicalize` calls it on the REAL value (the key for «have we met this
  person»); `name_key` calls it on the FAKE one (the index that resolves a token
  the model inflected). A guard inside `to_nominative` stopped «Тарасова»
  finding «Тарасов» — `survives_round_trip` rejected all 28 pool surnames. The
  guard lives in `canonicalize` alone (`lone_nominative_gender`) and
  `detect_gender` uses it too. Pins: `test_names_morphology`.
- **A surname alone may not decide gender, and the case must then be read in
  that gender.** «Кузнецова Ольго»: `-ова` scores higher as a man's genitive, so
  the span canonicalised to «Кузнецов Ольго». Both halves are gated on
  `has_given_name` — unconditionally it cost −14 round trips («Ким Викдор» →
  «Ким Викдоры»). Pins: `test_names_morphology`.
- **A plural reading, an unknown word and the VOCATIVE are not evidence of a
  case.** «Тагиев» read as genitive plural of an invented «Тагии»; «Ань» had
  nothing left but a vocative and became «Аня». A person is never plural; the
  vocative survives only as address. The guard lives in `detect_case` and only
  there (the substitute pool is known singular names). UNPINNED.
- **Prose case breaks on a homograph of another gender's name** — see
  `research/2026-09-17-prose-case-homography.md` for the open shape. UNPINNED.

## Address

- **An address span drops its leading CUE words.** «адрес ленинский проспект
  55» sent «адрес» to the tool inside the street name, «мой адрес …» sent two.
  Trimmed with `addr_ctx` for the cue vocabulary and the `Apro` grammeme for
  «мой»/«наш»; a street TYPE word passes both tests so «улица Тверская» stays
  whole. UNPINNED.
- **An address span stops at a sentence boundary.** The gap vocabulary must hold
  the period («ул.», «д.»), so «…, д. 14. Часы 9-21» masked as one address
  ending in «Часы 9». UNPINNED.
- **The trailing house number joins BEFORE the second merge.** «ул. Гагарина,
  45, кв. 12» lost its flat while «ул. Гагарина 45 кв 12» kept it. UNPINNED.
- **The apartment marker is usually glued to the house number.** «д.5кв12»,
  «Строителей 53к193», «Гагарина88кв152» — `_TOK` demanded whitespace before the
  marker. A bare «к» is admitted only glued to a digit («за 100к 5 штук» is not
  a flat); both branches stay SUPPORT. Pins: `bench/eval_metamorphic.py` only —
  UNPINNED in the shipping suite.
- **A lower-case marker-less street is gated on the VOCABULARY, never on
  morphology.** With the capital gone, morphology admits «течение 12»; a leased
  vocabulary cannot generalise to prose, which is the property needed. A month in
  it («марта», for «8 Марта») names a street only behind a number. UNPINNED.
- **A fuzzy street match needs THREE signals and a fourth condition:** a type
  word adjacent, the other word in the ГАР vocabulary as written / lemma /
  nominative, and address intent; the fuzzy hit is accepted only for a word
  pymorphy3 does NOT know and never for both words at once («линии»,
  «территории», «алло» match only exactly). Full curve in
  `docs/gar-street-vocabulary.md`. Pins: `test_hard_cases`.
- **Cutting the street vocabulary by frequency CONCENTRATES the risk.** The
  share of entries pymorphy3 calls an ordinary word rises from 22.9% at no cut to
  65.1% at twelve — the commonest street names ARE ordinary words. The whole
  tail costs nothing on NEREL / the clean suite / news prose and buys 0% → 90% on
  tail streets in the typo register. `STREET_MIN_OBJECTS = 1`. UNPINNED —
  `bench/eval_gar_cut.py`.
- **Regex alternation picks the earliest POSITION, not the preferred branch.**
  `street_lower_nohouse`'s marker-last branch matched «адрес москве проспекте»
  before the marker-first branch reached «проспекте мира» — ten of fourteen
  street values at the no-punctuation rung. A lookahead leaves the marker
  unconsumed. UNPINNED — `bench/eval_noise_by_type.py`.
- **A number with a unit of measure after it is not a house number.** «территория
  завода 5 гектаров» satisfied every signal because nothing looked PAST the
  number. The veto is on the NUMBER, not the span; «кв» is deliberately NOT in
  the unit list (after a house number it is квартира) — only «кв.м» / «кв м»
  counts. Pins: `test_overmasking`, `test_hard_cases`.
- **The ГАР attribution rides IN THE BUNDLE.** ФНС's open licence requires the
  source and the dump date; the customer loads a bundle, never the repository.
  `licensing/fetch_gar.py` writes the line, `licensing/pack.py` reads it back rather than restating
  it. UNPINNED.
- **A spoken numeral matches WHOLE, longest-class-first, closed with `\b`.**
  «два» is a prefix of «двести»; «квартира двести двадцать девять» matched «две»
  and the span ended three words early. The ceiling of ninety-nine was wrong for
  flats. Pins: `test_hard_cases`.
- **A spoken house letter is decided by what FOLLOWS it, never by which letter
  it is** — a litera ends the address or hands over to the next marker; a
  conjunction or pronoun drags a clause. **The house litera forbids exactly one
  letter, «я».** A lookahead demanding the letter end the phrase cut the house
  number on every third real address. UNPINNED — RuDevices via `bench/voice/`.
- **The spoken address TAIL is SUPPORT, exactly like `apt`.** «улица
  дербенёвская двадцать четыре строение пять» masked through «четыре» — four of
  six voice truncations. «дом» is deliberately not in it. UNPINNED — `bench/voice/`.
- **A bare street name in front of «дом N» is gated on ГАР AS WRITTEN.**
  «бибиревская дом семнадцать» has no type word, capital or digit; in lower case
  «бибиревская», «широкая», «пустая» are one part of speech, so not morphology,
  not the normal form. The second signal is word ORDER («дом культуры» puts the
  register word after the marker). Pins: `test_hard_cases`, `test_product`.
- **A street with NO type word is the MAJORITY form of a spoken address** (100
  of 156 dispatch values). `_bare_street_candidates` is the riskiest shape in the
  engine and is admitted past FOUR gates: ГАР in three forms; the shape of the
  name (surname in any case, adjective only nominative or licensed by a
  preposition, never plural / pronominal / a bare settlement); no age, measure or
  numeral agreement after the number; a DIGIT must satisfy the shape test even
  when the register names the form as written. Zero false addresses on 2 691
  NEREL sentences. UNPINNED — NEREL + `bench/voice/`.
- **Prose writes house numbers as DIGITS, speech as WORDS, and that separates
  the register from the language.** Letting ГАР alone decide cost 21 false
  addresses on news prose behind a digit («статьи 19 Федерации 2») and none
  behind a spelled number. UNPINNED — `bench/eval_overmasking_volume.py`.
- **A numeral GOVERNS what it counts; a house number governs nothing.** «один
  день» nominative, «два дня» genitive singular, «восемь обвиняемых» genitive
  plural — agreement, not a word list, separates «свободы один день» from
  «клубная восемьдесят пять». UNPINNED.
- **A CAPITALISED bare street costs six people on NEREL and is not worth it.**
  Voice coverage 79.5% → 84.1% against PERSON Cyrillic 93.4% → 93.1%: a LOC
  outranks NAME and swallows whoever is inside. The arm stays lower-case;
  «Лермонтова тридцать три» stays uncovered on purpose. UNPINNED.
- **The entrance is named with an ORDINAL and it stands BEFORE the marker.**
  «первый подъезд» — every arm expected «подъезд первый»; 73 truncations of 156.
  UNPINNED — `bench/voice/`.
- **EIGHT of the ten digit-words are real ГАР entries («Семь Ветров», «Пятая
  Парковая»).** «номер заказа шесть семь восемь девять» became the street
  «шесть» at house «семь восемь»; a dictated phone came back as an ADDRESS. A
  numeral names a street only INSIDE a longer name; `NUMR` and `Anum` are the
  test. Held by TWO independent vetoes. Pins: `test_overmasking`.
- **A NOUN names a street in the GENITIVE, so a noun with no genitive form is a
  thing next to a number.** «школа двести десять», «вышка триста тридцать три»,
  «время двадцать двадцать один» are all in the register. An adjective is
  exempt; so is a word a PREPOSITION put into an oblique case («на литейном
  четыре»). UNPINNED.
- **A street in the GENITIVE PLURAL is admitted only with the DOOR after it.**
  «Коммунаров», «Строителей», «Космонавтов» are a large class the plural veto
  discarded; lifting it is NOT available («строителей пять пришло на объект» —
  ten of twelve became false addresses). A house takes an entrance or flat, a
  quantity takes a verb; the continuation must begin IMMEDIATELY. UNPINNED.
- **A STREET TYPE is not a street name.** «улица», «проезд», «дорога» sit inside
  the ГАР NAME vocabulary, so «на дороге семьдесят» read as street «дороге» at
  house 70; the leased type stems already answer it. «дорог» was also MISSING
  from those stems. Pins: `test_overmasking`.
- **«КВАРТИРА» IS NOT «КВАРТАЛ», and five letters cannot tell them apart.**
  The type scan matched a generic by its first five characters; «химзаводская
  пять квартира пятнадцать» minted «квартира Сосновый 66». Pins:
  `test_hard_cases`, `test_product`.
- **A spoken house number is still a house number in three places that each
  decided it with `\d`:** `looks_like_street`, `place_shape`, `inflect_place`.
  Fixing one alone fixes nothing. Pins: `test_hard_cases`.
- **A ONE-LETTER PREPOSITION in front of what it governs is not a litera.**
  «двадцать семь в третий подъезд» went to the courier as «27в». The test is the
  word after the letter (an ordinal or an oblique marker), only for в/к/с/у/о;
  the rule lives in TWO places — the leased `_LITERA` and `_word_number_for` of
  the role split. Pins: `test_hard_cases` (`test_preposition_is_not_a_litera`).
- **ONE real street in a dialogue is ONE fake street.** A corrected house kept
  the street and minted two unrelated fakes (32 of 36 two-address `correction`
  cases). `_same_street_in_conversation` reuses the fake street for an equal or
  one-typo stem; a bare street with two owners answers with the LATEST row.
  Pins: `test_hard_cases` (`test_corrected_address_shares_its_street`).
- **A street the customer MISTYPED reaches the TOOL as the register spells it,
  and only the tool.** Without the gateway the agent silently repairs
  «мончгорская»; with a clean substitute there is nothing to repair — 88 of 141
  value conflicts. `address.register_spelling`: the register does not reach the
  word in ANY of the three forms, exactly one entry is one Damerau edit away
  («лениа» reaches four and is refused), the word is ≥ 6 letters. PROSE keeps the
  customer's words. Pins: `test_hard_cases`.
- **A SUBSTITUTE HOUSE NUMBER keeps the MAGNITUDE of the real one.** «we do not
  deliver above house 100» in the customer's prompt inverted under a fake 157 for
  a real 33 — 12 triples of `prompt_rule` with zero calls on the gateway leg. The
  band is under one and a half bits. Owner's decision 07.09. Pins:
  `test_hard_cases` (`test_the_substitute_keeps_the_house_magnitude`).
- **ONE ADDRESS IS ONE KEY, and the city may not be in it.** «центральная сто»
  vs the directory's «Тульская область, г Одоев, ул Центральная, д 100»:
  `street_house_key` dropped the city by `Geox`, the dictionary knows Краснодар
  and not Одоев, ONE address was minted TWICE (−91pp `tool_chain`). The city is
  named by `split_roles`, morphology stays a fallback. Pins: `test_product`.
- **A TWO-WORD CITY without a comma is still a city.** «нижний новгород проезд
  калашникова 12» parsed as one street. An adjective before a toponym, and only
  that; it cannot eat a street because a street's first word is followed by a
  GENERIC word. UNPINNED.
- **A settlement inside an address is REAL and stays.** The substitute keeps the
  customer's city (Одоев stays Одоев); only street and house are fake — the city
  identifies nobody and the directory lookup needs it. Pins: `test_hard_cases`.

## Spoken

- **An identifier dictated aloud has NO digit, and every recognizer waited for
  one** — 281 phones, cards, СНИЛС, ИНН and passports spoken as words, none
  found. `pseudex/spoken.py` only turns words into digits; whether the string is an
  identifier is decided by the SAME validators. The run scanner alone fires once
  in 9 300 utterances and never in 2 691 prose sentences. Pins: `test_product`,
  `test_hard_cases` (`test_a_dictated_phone_survives_a_deny_word`).
- **FUZZY MATCHING IS FORBIDDEN ON NUMERALS.** 99 ordinary words sit within one
  edit of a numeral («есть» beside «шесть», «ночь» beside «ноль»); distance-1
  would CORRUPT the digits, and a wrong digit string can pass a checksum. The
  typo table is MINED from real transcripts; three forms our own generator writes
  are deliberately absent. UNPINNED.
- **An EMPTY canonical is a collision generator.** «strip everything that is not
  a digit» returns "" for a value spoken aloud, so every spoken СНИЛС collapsed
  onto ONE row and two people shared one substitute. Pins: `test_collisions`.
- **Every written corpus we own is structurally BLIND to spoken numbers.** NEREL,
  golden, dirty, the clean suite and news prose all write digits as digits; all
  declared the bare-street change free while it masked every dictated order
  number. The class lives in `test_overmasking.py`, which ships and needs no
  corpus. Pins: `test_overmasking`.

## Swap

- **CONTENT FROM THE VAULT, FORM FROM THE AGENT — FOR EVERY TYPE, ON BOTH
  LEGS, WITH NO EXCEPTION FOR NAMES.** On the way in the substitute mirrors
  the form the CUSTOMER wrote (a name's grammatical case, letter case and
  word order; a date's notation — «2 июня 1975», «10.4.82», ISO, spoken; an
  identifier's digit grouping — «4509 123456», «11223344595»); on the way
  back the real value takes the form the AGENT wrote the substitute in — copied
  verbatim, re-cased, re-inflected, re-notated, re-grouped. «Игорь Анфалов»
  for an agent that wrote «Максима Дмитрова» was a guess about a CRM we know
  nothing about and the one written exception to the rule; the public
  benchmark's verbatim agent showed it as 78 values «repaired» into a form
  nobody wrote. Numbers are the boundary: a house number is never inflected
  («ленина пятидесяти», 506 diverged calls), so addresses go through
  `in_form_of`, never an inflector. Prose is still restored in AGREEMENT with
  the sentence. Pins: `test_argument_form` (`_forms_follow`, one case per
  type, both directions), `test_hard_cases`, `test_product`
  (`test_spoken_birth_date_in_the_agents_form`, `test_card_leaves_link_by_position`).
- **COPIED VERBATIM COMES BACK VERBATIM — the customer's literal string,
  typos and look-alike letters included.** The vault remembers per
  conversation what the dialogue was SHOWN where the customer wrote what
  (`shown_forms`, the original text slice, never the normalised value), and
  the verbatim pass runs before any form is rebuilt. Recorded for an address
  only when the customer wrote the street word himself, because the address
  substitute still adds one (the open half of Б24). Pins: `test_argument_form`
  (`_verbatim_is_literal`).
- **THE WAY BACK IS SCOPED TO THE SAME CONVERSATION AS THE WAY IN.** The proxy
  derives `conversation_key(messages)` for both legs; the sidecar's
  `/unmask*` take the `conversation_id` the host gave `/mask`. Without it
  nothing a dialogue decided on the way in (a linked address, `token_uses`,
  `shown_forms`) can be read back — which is how Б23 and Б24 would have been
  fixed in tests and dead in production. Pins: `test_argument_form`,
  `test_collisions`; UNPINNED at the HTTP surface — `test_perf_masking` should
  send `conversation_id` on `/unmask_arguments` and expect the literal.
- **DETECTION WITHOUT A MATCHING SUBSTITUTE IS A NET LOSS on the tool axis.**
  Hearing spoken identifiers raised detection and LOWERED the tool axis five
  points, because values that used to pass through went through a lossy restore.
  Any new recognizer is measured on BOTH axes. UNPINNED — `bench/agentpii4/`.
- **A pool a customer can exhaust is a permanent 5xx for that customer.** It
  happened twice: addresses at 33, gender-invariant surnames at 6. Any generator
  drawing from a fixed list needs a floor check at the pool, not a stack trace in
  someone's traffic. UNPINNED.
- **TWO SUBSTITUTES the model glued with a hyphen are TWO substitutes.**
  «Мухина-Бирюкова» resolved by no key and BOTH fakes reached the CRM. The
  vault answers, not morphology — a real toponym has no halves in the vault.
  UNPINNED.
- **A piece or a derivative of a substitute in the ANSWER to the customer is
  restored too** (known-issues Б11). Pins: `test_prose_fragments`.
- **`/spans` and `peek_token` are read-only** — rendering a dialog must never
  mint tokens or write audit. Pins: `test_localui`.
- **THE WHOLE SUBSTITUTE IS A WINDOW ON THE WAY BACK — as many words as the
  pool mints.** A two-word patronymic mints four words; with name windows
  capped at three the token came back as a three-word tail resolved by parts
  plus a lone fake surname, and once two people of one customer shared that
  surname (no conversation scope in a customer-wide vault) the chimera «Ершов
  Рустам Ахмед оглы» reached the customer (known-issues Б22). Widening the
  pool's shape widens `redact._name_windows` in the same change. Pins:
  `test_product` (`test_four_word_token_survives_a_shared_fake_surname`).

## Streaming

- **Tool arguments may NEVER go through `/unmask_chunk`.** It substitutes flat
  text and a real value is arbitrary text: «ООО "Заря"» put into a JSON string
  by plain replacement injects two bare quotes and the tool call stops parsing —
  on Russian business traffic the common case. Pinned from BOTH sides because
  the tempting simplification is one endpoint. Pins: `test_perf_masking`.
- **The tool call is buffered, and that is the trade.** Nothing inside a JSON
  string can be emitted before it closes — the escaping depends on the whole
  value and a sent prefix cannot be retracted. Same choice as the proxy's
  `_stream_as_single`. Pins: `test_product`.
- **One carry per `choice.index`.** With `n > 1` the deltas interleave and a
  shared carry splices one answer's tail onto another's head. Pins: `test_product`.
- **`/unmask_arguments` returns `residual_tokens`** — a substitute that fails to
  resolve inside a tool call is a fake reaching the tool with a 200. Pins:
  `test_perf_masking`, `test_detok_security`.

## Derived forms

- **A model transliterates BY LETTER, not by standard, and the restored name
  follows the MODEL.** No table reproduces «Meshcheryakova»; 96 of 1 812 Latin
  words follow endings no standard lists; when several tables explained a word
  the FIRST won (ICAO «iu» in «BITIUKOVA» against the control's «BITYUKOVA», 38
  triples). `translit.align` learns the model's choice per unit from the
  substitute, `render` applies it; the vault indexes one `fold`. Pins:
  `test_derived_forms`.
- **A piece of a name is ambiguous across a CUSTOMER and unambiguous in a
  CONVERSATION; a single initial is ambiguous even there.** `residual_of` breaks
  the tie by `minted_in` and refuses when two substitutes of ONE conversation
  share the piece; a lone «С.» is one letter and resolves only by its OBJECT —
  the name restored one key over in the same call (`_join_initials`). 50 of 56
  divergent initials were single and every call carried `first_name`. Pins:
  `test_derived_forms`.

## Agent form

- **THE FORM BELONGS TO THE AGENT, THE CONTENT TO THE VAULT.** The vault stores
  lower case and `_pick_value` handed it straight into the argument: «ким
  виктор» in the CRM — 262 field divergences, the largest class. `cased_like`
  carries the case word by word and the rule is SYMMETRIC. PROSE is untouched.
  Pins: `test_argument_form`, `test_hard_cases` (`test_the_form_belongs_to_the_agent`).
- **The agent's GENERIC word survives even when ours is absent.** `_street_like`
  had «we have no street type — return our name» and the agent's «ул.» fell on
  the floor. The type word is a marker of the same class as «д.» and «кв.»,
  which `in_form_of` already takes from the agent verbatim. UNPINNED.

## Vault

- **Canonicalization collapses spellings to one key → one token**: `+7 999…` /
  `8 999…` / `89991234567`; detokenization returns the canonical form. Pins:
  `vault_test`.
- **Substitutes are format-preserving and checksum-INVALID.** A fake СНИЛС / ИНН /
  card deliberately fails its own checksum, so a token can never collide with a
  real person's ID. Pins: `test_loop`, `test_product`.
- **`unmask_text` reindexes by digit signature**, so a numeric token the model
  reformatted (`+7…` → `8…`, separators stripped) still detokenizes. Pins:
  `test_product`.
- **A LINKED row is stored under a conversation-scoped canonical**; written
  plainly it would leak the link past the scope on the next request. Full
  addresses keep the plain key. `place_parts` expires after a day. Pins:
  `test_product`.
- **The host may declare its OWN values** (`with_own_values`) that are never
  masked. Pins: `test_hard_cases` (`test_the_host_may_declare_its_own_values`).

## Collisions

- **A substitute is drawn from the same string space as real values, so sooner
  or later it IS one** — 3–7 backwards and 2–3 forwards per run on 2 979 NEREL
  people, plus 10 dates of birth per 800. **BACKWARDS is knowable at mint
  time:** `_unique_token` refuses a candidate equal to any `canonical`, any
  `canonical_fold`, or the value being minted right now («15.06.1963» was minted
  as itself). Written as one `OR` it scanned every row (1.27 ms at 20 000 rows,
  up to 200× per request); `UNION ALL` gives each branch its own index, 2 µs.
  Pins: `test_collisions`.
- **FORWARDS is not knowable at mint time; the discriminator is the
  CONVERSATION.** Our substitute comes back inside the dialogue it was handed
  to; a customer's contact who bears that name walks in from another one.
  `tokens.minted_in` carries it and `is_minted_token` compares; a NULL and an
  empty scope behave as before. Pins: `test_collisions`.
- **The message ROLE is NOT that discriminator, and using it would leak
  everything.** The answer is detokenized before it is returned, so re-sent
  assistant messages carry REAL values; «assistant means echo, do not mask» would
  hand the model every value it ever mentioned. Demonstrated, not argued. Pins:
  `test_perf_masking`, `test_product`.

## Conversation scope

- **A PIECE OF A SUBSTITUTE RESOLVES ONLY IN A DIALOGUE THAT WAS SHOWN THE
  WHOLE.** «николая» in a street the customer wrote in the clear resolved to
  the one dialogue in the customer's vault that had drawn «Николай Крылов», and
  the tool received another person (known-issues Б23). `token_uses` records
  which name substitutes each conversation saw — minted or reused — and
  `Vault.residual_of` answers from that set: one owner shown here wins, none
  means the word is the customer's own. Pins: `test_collisions`
  (`test_b23_customer_word_equal_to_another_dialogue_substitute`).

- **A partial mention resolves against a fuller one only inside ONE
  conversation, and the reason is arithmetic.** «Ленина 14» exists in every
  city; at tenant scope the single-candidate rule finds a dozen owners and
  refuses every time — dead, not careful. The scope makes the rule mean anything
  and makes it safe. Pins: `test_product`.
- **`Vault.for_conversation()` hands out a shallow-copied VIEW, never a field on
  the shared object** — one vault per org, used from several threads. Pins:
  `test_product`.
- **`content_key` carries the conversation**, or the mask cache serves the first
  conversation's link to every later one. Pins: `test_collisions`,
  `test_perf_masking`.
- **`conversation_key(messages)` derives an identity from the first TWO messages
  when the caller names none.** Weaker than a given id, knowingly; the price is
  identity churn (a trimmed transcript is a new conversation, a second pseudonym,
  a second billed entity — the round trip still returns the real value). Pass an
  explicit `conversation_id`. Pins: `test_product`.
- **AGENT MEMORY IS AN ECHO FROM ANOTHER DIALOGUE, and the default does NOT
  move.** Every memory store keys by USER, so injected text carries a substitute
  from an earlier dialogue and is masked a SECOND time (200 OK, empty residual).
  Widening costs a real person (2–3 per run at customer scope), and 152-ФЗ
  counts the leak, not the broken tool call — so a host with memory declares
  `pseudonym_scope` / `PSEUDEX_PSEUDONYM_SCOPE`. Pins: `test_collisions` (BOTH
  halves of the trade).

## Cache

- **`MaskCache` is per worker, holds only MASKED output, keys on RAW content.**
  The vault and audit are shared, which keeps tokens consistent across workers.
  Pins: `test_perf_masking`, `bench_masking`.
- **Audit is recorded on the cache MISS only** — the same value re-sent in a
  growing transcript is one protected value, not N. Pins: `test_perf_masking`.
- **`bench_masking.py` and `profile_latency.py` cannot see the storage layer**
  (`Vault(":memory:")`); «the bench did not move» is not evidence a disk-layer
  change is free. UNPINNED by construction.

## Audit

- **Audit stores type + token + a masked preview only** — never the value; the
  full value lives only in the vault and `/reveal`. The preview shows ≤ 1 char at
  each end (pentest B4). Pins: `test_detok_security`, `test_localui`.
- **Every `/reveal` is recorded and `actor` is required.** The record holds who /
  which token / when, never the value; misses are recorded too; the ENGINE writes
  it, not the UI (`curl` against the sidecar is a supported shape). Pins:
  `test_localui`.
- **Every `/unmask*` writes a counts-only detok row and is rate-limited per
  org** — a compromised gateway credential must not trawl the vault without a
  trace (pentest B1). Pins: `test_detok_security`.
- **`requests` is a REQUEST counter, not `sum(entities)`.** A plan sold as
  «100 000 запросов» was consumed once per detected VALUE; a request that finds
  no PII is still billable, so it cannot be derived from the events table.
  Pins: `test_localui`, `e2e/gates.py L12`.
- **The self-check runs the REAL `/mask` + `/unmask` under `SELFCHECK_ORG`, which
  `billing_totals` excludes.** Pins: `test_localui`.

## Lease

- **The bundle is sealed to ONE process key generated in memory** — a captured
  lease is useless elsewhere, there is no portable form, restart → new keypair →
  new lease. Pins: `licensing/test_admin_api.py`, `e2e/gates.py L1–L4`.
- **Encryption and signature answer different questions.** age says who may
  open it; Ed25519 says who made it — age x25519 does not authenticate the
  sender, and a swapped bundle is a silent leak. Pins: `test_tuning_lease_security`.
- **EVERYTHING authored travels in the LEASED bundle — bulk AND tuning.** The
  tuning used to be a static-key-sealed blob in the binary; a memory dump
  recovered the key in ~1 s and decrypted it OFFLINE, forever, past revocation
  (A2). Now there is no compiled blob and no static key; extraction is one lease
  window, not forever. Pins: `test_tuning_lease_security`.
- **Grace covers OUR outage only.** 402/403 (unpaid, revoked) bypass it. Grace is
  counted on `time.monotonic()` plus a WALL-CLOCK CEILING: past TTL + grace +
  skew on the wall while monotonic looks fresh → EXPIRED, fail closed (a root
  customer LD_PRELOAD-froze the clock — pentest W2). Pins: `test_clock_freeze`,
  `e2e/gates.py L6–L9`.
- **EXPIRED unloads the assets and SCRUBS the caches**; `/mask` answers 503,
  `/unmask*` keeps answering by design. Pins: `test_unload_scrub`,
  `e2e/gates.py`.
- **Every leased bundle carries the customer's canaries, Tardos fingerprint and
  watermark**, so a leaked or cloned bundle names its organisation — attribution
  replaces the drift lever an offline licence removes. Pins: `test_canary`,
  `test_fingerprint`, `test_watermark`.
- **ONE key is compiled into the release binary: the Ed25519 VERIFICATION key**
  (`pseudex/_release.py`). A fresh one forces a full Nuitka rebuild; there is no
  tuning key. Pins: `e2e/pack_gates.py`.
- **Docstrings are stripped BEFORE Nuitka.** `--python-flag=no_docstrings`
  leaves the literals in the constants blob where `grep -a` finds them; here the
  docstrings are the design record and the part most worth withholding. Pins:
  `e2e/pack_gates.py P2`.
- **The version verdict rides UNDER the lease signature and is retracted by
  absence** (D-055). Every top-level key of the lease response except `bundle`
  and `signature` is signed, and the client verifies over what it received —
  so a 0.3.14 engine accepts a `version` block it does not read, and a newer
  one parses it ONCE into `LicenseStatus` (RFC 9745 `@unix`, RFC 8594
  HTTP-date → unix seconds). A block missing from the next lease clears the
  verdict and the notice; the server's silence is «неизвестно» on every
  screen, never «новейшая». Pins: `licensing/test_admin_api.py` (ЛЕСТНИЦА
  ВЕРСИЙ НА КЛИЕНТЕ), `test_pseudexctl`, `test_localui`.
- **426 `unsupported_client` is a VERDICT outside grace, like 402/403** (D-056).
  The server answers it only to a cycle whose `eol` passed AND was announced
  ≥ 90 days ahead; the client treats it as terminal at renewal (assets
  unloaded, `/mask` 503) and as a startup refusal with the upgrade remedy.
  Deprecation before that changes nothing but the log and the banner (RFC
  9745). Pins: `licensing/test_admin_api.py`, `test_pseudexctl`,
  `test_localui_renders` (the banner in a real browser).
- **A bundle format above `SUPPORTED_BUNDLE_FORMAT` is «обновите движок», not
  «бандл повреждён»** (D-064). `bundle_format` is signed; a larger number is
  `BundleFormatError` — grace on renewal (the leased bundle stays loaded,
  because the mismatch is OUR deployment order), `bundle_format_unsupported`
  at startup. The client declares `lease_contract` in every request and the
  server records it beside the version, so «when can the contract-2 bridge
  go» is a query, not a guess (D-063). Pins: `licensing/test_admin_api.py`,
  `licensing/test_store_upgrade.py`.

## Billing

- **`metering.bill` is the ONE point where a request is counted and capacity
  consumed, called AFTER a successful mask and never before.** Two counters in
  two places drifted twice, both silently (`{"requests": 0}` forever on the proxy
  leg; `consume` before validation charged for 400s). `grep -c 'metering.bill('
  pseudex/` must equal the number of legs. Pins: `test_perf_masking`,
  `e2e/gates.py L12`, `licensing/test_metering_attacks.py`.
- **THE RATE LADDER MUST PAY TO CLIMB.** Each overage rate is ~80% of that
  tier's included price and DECLINES up the ladder, so overage is never cheaper
  than the tier above — a flat rate once made volume through overage tens of
  times cheaper than inside a tier. Pins: `storefront/test_billing_lifecycle.py`
  (the PROPERTY, not the numbers).
- **METERING STARTS AT 300 000 REQUESTS OF EXCESS on every tier** — metrology,
  not generosity: the error of granted capacity is `(quantum + reserve) /
  period`, and below ~300k the lower quantum bounds dominate. The threshold is
  on the VOLUME, not the tier. Pins: `test_published_claims`,
  `storefront/test_billing_lifecycle.py`.
- **`run_billing_cycle` is the ONLY caller of the billing primitives**, idempotent
  by a ROW, shipped as its own hourly compose service — never a thread in
  gunicorn. Health means «the last pass SUCCEEDED» (a stamp written on success),
  or the service that issues every invoice is dead behind a green dashboard.
  Pins: `storefront/test_billing_lifecycle.py`.
- **A transition that changes service is proved by the CONTAINER, not by a
  row.** `Subscription.state` is a mirror; the test POSTs `/mask` into a live
  container after every such transition. Pins: `storefront/test_billing_lifecycle.py`.
- **Numbers printed to the customer come from the code.** The landing promised
  volume billing that did not exist and «48 hours on non-payment» that described
  the lease reserve. The test also asserts the ABSENCE of the literals it
  replaced. Pins: `test_published_claims`.
- **ONE free entry, and a key is what the money (or a live trial) buys.** The
  trial is the `free` plan only; a paid plan chosen on the landing is `pending`
  — no trial, no key — until `mark_paid`. `services.may_issue_keys` gates every
  key path; a form without a plan is refused, never defaulted to «Старт». Pins:
  `storefront/test_paywall.py`, `storefront/test_signup_forms.py`,
  `storefront/test_billing_lifecycle.py`.
- **Gift days and the post-trial discount are mirrors and never both.** Decided
  by the engine request counter on the FIRST payment: zero requests →
  `first_payment_bonus_days`; any request → `post_trial_discount_pct`; a second
  payment gets neither. Pins: `storefront/test_paywall.py`.

## Surfaces

- **Both surfaces wrap ONE core** (`envelope.mask_messages` / `mask_tools` /
  `unmask_response`); the only intended difference is that the proxy has no
  `skip_system`. When masking semantics change, decide explicitly whether both
  legs need it. Pins: `test_perf_masking`, `test_persona_defects`.
- **Gateway and operator surfaces are gated by DIFFERENT tokens.**
  `PSEUDEX_GATEWAY_TOKEN` is a cheap credential the customer's gateway holds and
  cannot reveal values; `PSEUDEX_ADMIN_TOKEN` can. Test harnesses read the token
  off `pseudex.service`, never restate it (`test_perf_masking` failing with 401
  is what that drift looks like). Pins: `test_localui`, `test_perf_masking`.
- **`PSEUDEX_ADMIN_TOKEN` (and the gateway token) are set by `entrypoint.sh`
  ONCE for all workers.** N workers each generating their own means N valid
  tokens on one SO_REUSEPORT port and a UI that 401s at random. Pins:
  `test_preflight` (the shell contract), `e2e/gates.py`.
- **A bound container (`PSEUDEX_ORG`) refuses any other `org_id`** (pentest B2).
  Pins: `test_detok_security`.

## Local UI

- **The UI is a SEPARATE process** (`PSEUDEX_ROLE=ui`, :8081) so it can report
  «движок не отвечает»; it never imports `pseudex.service` and never leases.
  Pins: `test_localui`.
- **The session token rides in the Authorization header, never a cookie** — a
  cookie would make `/reveal` reachable by CSRF. UNPINNED.
- **The engine proxy is an ALLOWLIST of exact paths, not a prefix match** — it
  holds a credential the page does not, so a pass-through is an open relay into
  the container's network. Pins: `test_localui`.
- **Page files ship at `/app/ui`, never under a directory called `pseudex`** —
  P1 asserts `/app/pseudex` does not exist as evidence the package did not ship.
  Pins: `e2e/pack_gates.py P1`.
- **Rendering is vendored Preact+htm, never string-concatenated `innerHTML`.**
  Every screen renders values from the customer's own traffic, in a page holding
  a session that can reveal personal data. Pins: `test_localui_renders`.
- **The sign-in token is generated in `entrypoint.sh`**, so a UI restart does
  not invalidate the link the operator already followed. UNPINNED.

## Storage

- **Encrypted at rest (SQLCipher), and the driver has no fallback.** One key
  resolver (`pseudex/vault_key.py`): `PSEUDEX_VAULT_KEY` → `_KEY_FILE` → `_KEY_CMD` →
  generated beside the data and announced on every start; HKDF-SHA256 per store.
  `required` refuses to generate; `off` is what the LICENSING image sets (its
  data holds zero personal data and `deploy/backup.sh` needs it plain). Pins:
  `e2e/gates.py` (vault gates), `e2e/pack_gates.py P9`.
- **A plaintext store found on disk is migrated in place** — under `flock`,
  idempotent by file header, `wal_checkpoint(TRUNCATE)` first because the real
  values live in the `-wal`. A store is atomic, a VOLUME is not: the role names
  which files moved. Pins: `test_pseudexctl`, `e2e/gates.py`.
- **A volume is numbered, and an older image never opens a newer volume**
  (D-058). Each store carries `application_id` (which store it is) and
  `user_version`, moved only by numbered idempotent steps in historical order
  (`vault.VAULT_MIGRATIONS` …); `schema.ensure` refuses `user_version` above the
  image's maximum BEFORE any DDL, with both numbers and the file, and
  `PSEUDEX_ROLE=probe` exits 2 (container 6) for it — an older image that opened
  a newer volume would write rows the newer one reads half-filled. `0` is the
  pre-versioned state every existing volume is in: all steps run, then the
  stamp. Pins: `test_schema`, `test_preflight`, `e2e/gates.py L24`.
- **A snapshot precedes the first step, under the same key, or nothing moves**
  (D-059). `<store>.pre-<from>-<to>.db` by `VACUUM INTO` after
  `wal_checkpoint(TRUNCATE)`, fsync of file and directory; free space ≥ 2×
  (store + WAL) is checked before anything is touched. Once per volume in
  `PSEUDEX_ROLE=migrate` before the fan-out; workers take the fast path. A
  fresh store is stamped without a snapshot — there is nothing to restore to.
  Pins: `test_schema` (the snapshot is OPENED with the store's key, not assumed),
  `e2e/gates.py L25`.
- **The maximum `user_version` per store is pinned per MINOR** (D-060):
  `prototype/schema_lock.json` must equal `schema.versions()` for the minor in
  `version.txt`. Adding a migration step under an already-pinned minor is red —
  a patch keeps the number (rollback to the previous patch is free), a minor may
  raise it one way, and opening a minor is the act of adding its line. Pins:
  `test_schema`.
- **The licensing server's schema MIGRATES before any index is built.**
  `CREATE INDEX … (org_id, pubkey)` ran before `ADD COLUMN pubkey`; upgrading on
  existing data did not come up. Every other path starts from an empty database
  — the one state production never has again. Pins: `licensing/test_store_upgrade.py`
  (a VERBATIM snapshot of the old schema).

## Hardening

- **The worker hardens itself BEFORE any role touches the tuning or the vault**
  — non-dumpable, non-traceable, swap-locked. Pins: `test_memory_hardening`,
  `e2e/gates.py L14`.
- **A memory read is detected and ATTRIBUTED to the vendor** (tripwire, WS-7).
  Pins: `test_tripwire`, `test_metering_anomaly`.
- **What this buys, stated honestly:** a root leaseholder still sees their
  ACTIVE lease's tuning in RAM — a theorem, closed by no software on any
  hardware. The bar is commercial desktop software: native code, no
  `uncompyle6`-shaped path back; confidential computing protects the wrong thing.
  UNPINNED by nature — `research/2026-09-15-ram-extraction-hardening.md`.

## Process

- **Real parallelism comes from processes, not threads** — pymorphy3 holds the
  GIL. N uvicorn workers, ~350 MB each; inside a worker detection is offloaded via
  `anyio.to_thread` under a `CapacityLimiter` so `/health` stays responsive.
  Pins: `test_perf_masking` (loop responsiveness).
- **`PSEUDEX_ROLE=preflight` does the memory arithmetic against the cgroup
  limit BEFORE the fan-out** and refuses or lowers N, rather than leaving it to
  the OOM killer (status 137 names neither memory nor us). Pins: `test_preflight`.
- **uvicorn does not configure the root logger.** The licensing server had no
  operational log; `basicConfig` lives in `licensing/devserver.py`. UNPINNED.
- **The customer image pulls WITHOUT a login, and ONLY the customer image
  does.** The site hands out `docker run …` with the image path and a licence
  key — there is no `docker login` step and there must not be. The registry is
  private; exactly one repository, `pseudex`, carries `allUsers` →
  `container-registry.images.puller`. The four server images (licensing — with
  the leased dictionaries and tuning inside — storefront, backup, supportbot)
  stay closed. Found 2026-09-20: nothing pulled the image as a customer (personas
  and gates build it locally), customers got `unauthorized`. UNPINNED by any
  test script — the registry is not reachable from one; enforced on every
  release by the `.github/workflows/release.yml` step «the customer can pull the
  customer image, and ONLY it» (anonymous `DOCKER_CONFIG`, both directions).
- **The deploy agent follows «platform/v*» only and compares versions by
  NUMBER.** Two release streams (D-051): engine tags `vX.Y.Z` are the customer's
  and never reach our host; the agent picks `git tag -l 'platform/v[0-9]*'`,
  strips «platform/» and `v` before `sort -V` (raw strings put `p` before `v`,
  and every platform release would read as a downgrade of the last old-scheme
  tag `.deployed` remembers), refuses an identity regexp that cannot match
  `refs/tags/platform/v…` in words before any signature check, and waits when no
  platform tag exists. It also syncs the versions registry every tick from
  «origin/main» — accepted only after `cosign verify` of the newest cycle's
  digest with the image identity; an unparseable file or an unsigned digest
  never replaces the last good copy, and says so. Pins: `deploy/test_agent.sh`.
- **The engine is versioned only when the engine changed** (D-051, D-052). A
  commit is attributed to a stream by the files it touches; the engine's
  shipped set is derived from the `COPY` lines of `prototype/Dockerfile.nuitka`
  (`deploy/shipped_paths.sh`). Three layers: release-please excludes
  `licensing/`, `bench/`, `e2e/`; `deploy/lint_engine_commits.sh` refuses a
  visible-type commit that touches `prototype/` and nothing shipped; the engine
  publish job is red when the shipped set is unchanged since the previous
  `v*` tag — `0.3.12` and `0.3.13` were one image under two numbers. No root
  package `"."` in `release-please-config.json`: it receives every commit.
  Pins: `.github/workflows/checks.yml` (lint + config gate); publish gate in
  `.github/workflows/release.yml` — UNPINNED by a test script, enforced by CI.
- **The versions registry is additive and announces closings 90 days ahead**
  (D-054, D-056). `deploy/releases.json`: `latest`/`digest` are written by the
  pipeline only; a recorded version never changes digest, `latest` never walks
  back, a cycle is never removed; `eol` requires `eol_announced` ≤ today and
  `eol ≥ eol_announced + 90 d`; the newest cycle alone carries `X` and `latest`.
  The server refuses to enforce a late `eol` (`registry.check` returns «late»,
  not a 426). Pins: `licensing/test_registry.py`; `.github/workflows/checks.yml`
  validates against the previous file and requires tag `v<latest>` to exist.
- **The engine version has ONE source, `prototype/version.txt`** (D-053): baked
  into `pseudex/_release.py` next to the verification key, read by
  `pseudex/license.py`, sent in the lease, shown by `/status`, the UI and
  `pseudexctl doctor`. It used to be `ENGINE_VERSION = "1.0.0"` in code, on every
  image ever shipped. Pins: `test_localui` (`/status` equals the file);
  `.github/workflows/release.yml` publish is red when the tag differs from the file.
- **Only `security:` commits reach a «release/X.Y» branch, and only by
  cherry-pick from `main`** (D-057). `.github/workflows/backport.yml` opens the
  cherry-pick PR into every live support branch when a PR carrying such a
  commit merges; release-please on the branch mints `X.Y.Z+1`;
  `.github/workflows/release.yml` measures the empty-release gate against the previous tag of the SAME cycle
  and moves alias `X.Y` only. An ordinary `fix:` is not backported — the
  customer gets it with the next minor, or the support branch becomes a second
  `main` with none of its gates. `deploy/watch.sh` warns when a cycle's `eol`
  is ≤ 30 days away and containers still run on it. Pins: UNPINNED by a test
  script — enforced by the workflows; the registry half by `licensing/test_registry.py`.
- **`pseudexctl upgrade` is an ORDER, and the volume is never the thing that
  pays for a failed one** (D-062): pull → probe with the NEW image, read-only,
  before anything stops (key opens, volume not from the future) → stop →
  archive of the volume → rename → run with the same name, ports, mounts,
  environment (container env minus image env, via a 0600 `--env-file` —
  secrets never in argv) → `/health`. Unhealthy: the old image's probe decides
  — 0 → the previous container comes back by itself, 2 → nothing is deleted
  and the `restore` command is printed. A compose-managed container is
  refused. The tool ships in both images at `/app/pseudexctl`. Pins:
  `test_pseudexctl` (order, shape, secrets, both rollback branches, dry-run).
- **The image tag the site advertises comes from the versions registry, never
  from a hand-set variable** (D-061). `engine_release.current_image()` returns
  the floating minor of the newest cycle in the copy the agent synced; `latest`
  when there is no file; `PSEUDEX_DOCKER_IMAGE` only as an explicit override.
  `CUSTOMER_IMAGE=…:1.0.0` set once by hand advertised a tag the registry did
  not hold; deriving it from the platform `VERSION` would have advertised a
  platform number. Pins: `storefront/test_engine_release.py`.

## Instruments

- **AN INSTRUMENT THAT CANNOT FAIL IS NOT AN INSTRUMENT.** v4 could not fail in
  four places at once: a triple with nothing to compare passed all five levels
  (`not any([])`), `FieldSpec.required` was read by no scorer, there was no level
  for «did the arm act at all», over-masking was measured by nothing. Each was
  found by reading the code. `LevelVerdict.comparable`, `absent_required`, the
  call level and `Case.negatives` exist because of it. Pins:
  `e2e/audit_gates.py` (the mechanical version, `--selftest`).
- **Every NEGATIVE atom needs a POSITIVE atom over THE SAME SOURCE.** `P1`
  proved the absence of four strings and would have passed grepping a missing
  file; `L12` asserted `requests > 0` after twelve calls. Lambdas are walked;
  helpers return `(the search ran, what it found)`. Pins: `e2e/audit_gates.py`,
  `e2e/lint_tests.py`.
- **NEITHER McNEMAR NOR A CONFIDENCE INTERVAL CAN PROVE «NO EFFECT».** The
  report publishes a TOST verdict at δ = 3pp — one margin for every level — from
  the same cluster bootstrap, with a resolution floor of 1/n. UNPINNED —
  `bench/agentpii4/stats.py`.
- **Read the CALL level first, the field level only for calls both arms made.**
  `extra +131` was thirteen net extra CALLS counted once per field. UNPINNED.
- **A benchmark's own convention is a FOURTH convention.** The instrument
  accepted three transliteration standards and scored the control's own
  «Kuznetsov Dmitry»/«Dmitriy» as failures; widened by SYLLABLE, never by
  distance. UNPINNED — `bench/agentpii4/`.
- **AN OVERLAP OF THE WRONG TYPE IS NOT RECALL.** A СНИЛС masked as a STREET is
  a broken tool call, not a protected value. `bench/agentpii/score.py` requires
  `span.entity_type == item["type"]`; `eval_dirty.py` prints type-aware miss and
  type-blind TRUE-LEAK as two lines; `bench/voice/score.py` filters to LOC.
  UNPINNED.
- **Overlap is not coverage, and the difference is a leak.** «Кзнецов Дмитрий»
  detected as «Дмитрий» is recall with the surname in the clear; 97.6% recall vs
  95.0% coverage was 69 partial leaks. Both numbers are printed, never merged.
  UNPINNED — `bench/agentpii/score.py`.
- **A benchmark's SELECTION FILTER can be part of the detector.** `bench/voice`
  admitted an utterance only if it held a type word or a house marker — the
  engine's own signals — and reported 100%; widened to «any numeral or digit»,
  122 candidates became 1 373 and the truth was 38.6%. Ask of any corpus «what
  could never have entered it». UNPINNED.
- **A census of one stratum is not a census of the corpus.** RuDevices: all 400
  marker-carrying utterances and a random 250 of 4 805 number-only; any rate over
  the second is weighted 250/4805 and kept under a `filter` field so the two
  cannot be added. UNPINNED.
- **Ground truth is the canonical form of WHAT WAS WRITTEN, derived from what
  the generator BUILT, never by searching the finished string.** `_canonical_name`
  matched by substring and every part a register had TOUCHED vanished — 162 of
  183 sloppy failures. A scorer fallback («came back as written») hid it.
  UNPINNED — `bench/agentpii/`.
- **An eval must take the PRODUCTION path.** The round trip minted tokens from
  the raw corpus value, skipping normalization, and reported ~180 phone breaks
  that do not exist. Read the vault read-only for the token masking actually
  minted. UNPINNED.
- **Our own sets cannot tell the truth about precision** — 100% while «Счёт 1234
  от 15.05.2025» was being masked, because they held no ordinary business text.
  Three external measurements exist for that reason and none replaces the others:
  `test_overmasking.py`, NEREL precision, AgentPII. Pins: `test_overmasking`.
- **A CLEAN-TEXT SUITE PRINTS WHAT IT CERTIFIES, NOT WHAT IT OBSERVED.** Zero
  errors on 42 phrases certifies ≥ 93.1%, not 100%; 99.4% needs 498 flawless
  phrases; the exact one-sided Clopper-Pearson floor is printed. On NEREL 1 922
  spans make the whole budget at 99.4% twelve spans. Pins: `test_overmasking`.
- **GROW A CLEAN SET BY SOMEBODY ELSE'S ANNOTATION, NEVER BY OUR OWN SILENCE.**
  The 496 phrases were selected because MASSIVE's annotators marked no PII slot,
  then read by hand; selecting phrases because our detector stayed quiet builds a
  suite that cannot fail. Brands and museums stay IN. Pins: `test_overmasking`.
- **`bench/gate` labels OCCURRENCES pinned to a SNAPSHOT, and prints MOVEMENT.**
  A frequency list answers nothing («ленина» is a street in one utterance and a
  person in another); pinned to the live engine the first fix reshuffled it and
  228 of 600 labels survived. UNPINNED — `bench/gate/`.
- **TWO INDEPENDENT CORPORA AGREE ON NAMES, and that is the number to defend:**
  69.6% on AgentPII-RU v3 and 68.0% on MASSIVE ru-RU. Any improvement must move
  BOTH; a gain visible only on ours is imaginary. MASSIVE `place_name` 0.1% is
  CORRECT (bare cities are refused by law). UNPINNED — `bench/eval_massive_ru.py`.
- **THE DICTIONARY IS NOT THE BOTTLENECK FOR NAMES, THE GATE IS.** 474 of 569
  missed names on real speech are in the leased dictionary, refused because a
  lower-case surname needs a cue AND morphology; a perfect gate would take NAME
  полнота 69.6% → 94.8%, and that decision is contextual. Widening the
  dictionary is not available (a sixth is homonymous with ordinary words).
  UNPINNED — `research/2026-08-31-ml-gate-or-rules.md`.
- **An identifier left without a dictionary is the only thing that leaks:** 0 of
  2 172 values inside the leased lists, 8 of 272 outside. The zero the corpus
  used to print described how much it resembled the dictionary. UNPINNED.
- **Datasets are generated, not committed, and `make_stress` / `make_holdout` /
  `make_addr_real` were built INDEPENDENTLY of the detector and must not be
  tuned against** (`make_addr_real.py` takes the seed as an argument). `negatives`
  must stay unmasked. UNPINNED by policy.
- **MUTATE YOUR OWN FIX BEFORE CALLING IT DONE.** Each repair is reverted in
  place and the analyser confirmed red, then restored byte-exact. Pins:
  `e2e/audit_gates.py --selftest`, `wiki/check.py --selftest`.

## Operations

- **THE STAND BUILDS `pseudex:local`, THE GATES BUILD `pseudex:source`.** They
  bake different verification keys; a shared tag made a gate run silently replace
  the stand's image (`lease signature is not ours`). Pins: `e2e/gates.py`.
- **`deploy/local.sh` proves the stand is up before saying so** — a 401 from the
  admin port is proof of life, a refused connection proves nothing. UNPINNED.
- **Both licensing tokens go to the SERVER, not just to the storefront.**
  `deploy/compose.local.yml` declared `PSEUDEX_LICENSE_STOREFRONT_TOKEN` for the
  storefront only; «no figures» and «we are not being let in» are different
  facts. Pins: `storefront/test_deploy_references.py` (names in deploy vs real
  tables) — the token wiring itself UNPINNED.
- **`$VAR` inside a compose `command:` is interpolated by compose, not the
  shell.** The once-a-day guard on the digest arrived empty; escape as `$$VAR`;
  the absence of «variable is not set» in `docker compose config` is the check.
  UNPINNED.
- **Both images are pinned to the same Debian release** — a Nuitka binary links
  against the build stage's glibc. Pins: `e2e/pack_gates.py`.

## False reds

A false red is worse than a false green: it gets ignored, and then it gets
ignored together with a true one.

- **A check must not depend on a number the ENVIRONMENT happens to carry.**
  `test_billing_lifecycle` read the lease TTL from `STAND_LEASE_TTL` of the
  current shell while the stand ran with whatever it was created with; the test
  now ASKS THE SERVER (`/admin/fleet` returns `window_seconds`). Pins:
  `storefront/test_billing_lifecycle.py`.
- **A check that stops a container goes LAST.** Every later step depended on
  whether the port was listening yet; the fix is ordering, not timing. Pins:
  `storefront/test_billing_lifecycle.py`.
- **A replace-based edit can silently drop a line.** After any such edit, read
  the region back rather than trusting that the anchor matched. UNPINNED — a
  working habit.
- **Verify a response shape against the LIVE service, not its docstring.**
  `_detect_first_lease` read `row["instances"]`; the answer nests under `usage`,
  and the field that matters is `capacity_granted` (monotonic, «has it EVER
  leased»), not `instances` (windowed by TTL). UNPINNED.

---

## Unpinned — the test backlog

Rules above marked UNPINNED, by section. Each is a test nobody has written yet;
until one exists the rule holds by code reading and by the external benchmark
named next to it.

- Engine-wide: leased regex case flag.
- Pipeline: cheap gates before morphology.
- Structured IDs: passport cue window.
- Context: cue distance / sentence end; misspelt cue; settlement veto.
- Names: single-token NER keep; neighbour extension; split surname; verb trim;
  hyphen glue; `_LOWER_DICT_MIN`; Регина tie; the removed composite veto.
- Name morphology: plural / vocative / unknown-word guard; prose homography.
- Address: cue-word trim; sentence boundary; trailing house before merge;
  glued apartment marker; lower-case vocabulary gate; ГАР cut; alternation
  position; ГАР attribution; litera rules; spoken tail; bare-street four gates;
  digits vs words; numeral government; capitalised bare street; ordinal
  entrance; noun genitive; genitive plural door; two-word city.
- Spoken: no fuzzy on numerals.
- Swap: both-axes measurement; pool floor; hyphen-glued substitutes.
- Agent form: the agent's generic word.
- Local UI: header not cookie; sign-in token from entrypoint.
- Process: root logger.
- Operations: `deploy/local.sh` liveness; token wiring; compose `$$VAR`.
- Instruments and false reds: the ones that are policy rather than code.
