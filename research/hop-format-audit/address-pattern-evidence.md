# Address transformations at each hop — literal evidence extract

Task: `hop-sprint-loc-patterns-20260927`. Read-only. English. Owner of this file only.
Sources read (literal, no aggregation): `research/hop-format-audit/evidence/cases/`
`tool_chain-017.md`, `long_support-027.md`, `prompt_rule-026.md`, `memory_anaphora-119.md`
plus their `.controls.C.json` / `.controls.C2.json`. No engine edits, no policy calls.
Line cites are `file:line`; control cites are the control file.

## 0. What was and was not read

- Each case `.md` holds `## Case specification` (the authored conversation, seed records, declared
  PII), `## Actual gateway arm` with `"arm": "I"` (written/restored calls, tool results, answers,
  mentions), and `## Recorded observer hops` (individual `produced` / `reference` / `status` /
  `verdict` records).
- "I arm" below = that `"arm": "I"` payload. "C" and "C2" = the control arms; both carry
  `"substitutes": {}` and `"masked_spans": {}` in all four cases, i.e. they are the no-engine arm.
- Aggregate metric blocks (`README.md`, `PROGRESS.md`) were not used. Only literal strings and
  per-hop records.
- Case provenance as recorded in each spec: `tool_chain-017` kind `tool_chain`, register `chat`;
  `prompt_rule-026` kind `prompt_rule`, register `voice_raw`; `long_support-027` kind `long_support`,
  register `chat`; `memory_anaphora-119` kind `long_support`, register `chat`. All authored templates.

Terminology used below:

- **marker** — the generated substitute surface the engine emits for a real address part
  (`base.substitutes` / `text_masked`), e.g. `барбарисовая`, `вишнёвая`, `мятная`.
- **sender** — whoever wrote the text under inspection: the user on the IN leg, the agent on the
  OUT leg. The sender owns *form*; the vault link owns *identity*.

## 1. The address objects the transformations act on

For each case the relevant literals are:

| layer | field | key cite |
|---|---|---|
| user text | `base.messages[n].content` | `long_support-027.md:39` |
| masked text shown to the model | `base.masked_spans`, `base.substitutes` | `long_support-027.md:1770` |
| agent call, as written | `calls[].written` | `long_support-027.md:1527` |
| agent call, restored | `calls[].restored` | `long_support-027.md:1538` |
| leftover fake in a restored call | `calls[].residual` | `tool_chain-017.md:1222` |
| tool result, real vs masked | `tool_results[].text_real` / `text_masked` / `pieces` | `long_support-027.md:1860` |
| prose shown to the user | `turn_replies` (restored) vs `reply_raw` (as the model wrote it) | `memory_anaphora-119.md:1224`, `:1411` |
| observer record | `hop.path`, `produced`, `reference`, `status`, `verdict.differs` | `long_support-027.md:3481` |

The observer's form-difference vocabulary that actually appears in these four cases:
`case_class`, `commas`, `generic`, `generic_position`, `city_present`, `city_position`,
`flat_marker`, `parts`, `grouping`, `prefix`, `separators`.

## 2. General transformations, with literal evidence

### 2.1 Parts added by the sender (generic word, house/flat markers, punctuation)

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T1 | house marker added by the agent; the user's generic word kept | user: `сарапул улица новая 119 кв 176` (generic `улица`, bare house `119`) | agent reply: `Сарапул, ул. Ивовая, д. 146, кв. 68` — adds `д.` | `memory_anaphora-119.md:39` vs `:1224` |
| T2 | type word + `д.`/`кв.` added around structured fields | card fields `city/street/house/flat` | agent order arg `"address": "ул. Барбарисовая, д. 3, кв. 228"` | `tool_chain-017.md:1495` (masked fields) vs `:1194` |
| T3 | spelled flat marker replaced by abbreviation | user `квартира сто восемьдесят три` | engine substitute `Кинешма, улица Мятная 34, кв. 186` — `квартира` → `кв.` | `prompt_rule-026.md:39` vs `:1098` |
| T4 | commas and city position added | user `кинешма переулок комиссарова …` (no commas) | engine substitute `Кинешма, улица Мятная 34, кв. 186` | `prompt_rule-026.md:39` vs `:1098`; hop `:1523-1524` |

### 2.2 Parts moved / reordered

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T5 | generic word moved **into** a structured street field that holds it bare in the seed | seed field `"street": "загородный"`, type declared apart (`:87`, `:269`) | agent field `"street": "переулок Вишнёвая"`; C2 does the same without an engine | `long_support-027.md:1527`, `long_support-027.controls.C2.json:131` vs `:87` |
| T6 | one-line address decomposed into `city / street / house / flat` | user: `курск переулок загородный 16 кв 142` | agent: `city Курск`, `street переулок Вишнёвая`, `house 99`, `flat 158` | `long_support-027.md:39` vs `:1523-1527` |
| T7 | marker order in prose changed by the restorer | agent wrote `Сарапул, ул. Ивовая, д. 146, кв. 68` | answer text produced `сарапул улица новая 119 кв 176` | `memory_anaphora-119.md:1224` vs `:1121`; hops `:1873-1874`, `:1901-1902` (`case_class`, `commas`, `generic`) |

### 2.3 Parts removed / dropped

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T8 | generic/type dropped on restore | written `"street": "переулок Вишнёвая"` | restored `"street": "загородный"` — `переулок` gone | `long_support-027.md:1527` vs `:1538`; hop `:3481-3482` `differs ["case_class","generic"]` |
| T9 | `ул.` inside a quoted span dropped with the marker | written `(в карточке было «ул. Вишнёвая» — исправлено на переулок)` | restored `(в карточке было «загородный» — исправлено на переулок)` | `long_support-027.md:1564` vs `:1569` |
| T10 | non-street part dropped in a repeat order | seed `Республика Татарстан, г Казань, ул Зацепская, д 7` | agent arg `ул. Барбарисовая, д. 3, кв. 228` (no region) | `tool_chain-017.md:92` vs `:1194` |
| T11 | `д.` dropped when rendering the real value back | agent wrote `Сарапул, ул. Ивовая, д. 146, кв. 68` | answer `сарапул улица новая 119 кв 176` | `memory_anaphora-119.md:1224` vs `:1121` |

### 2.4 Street type: correction, substitution, abbreviation

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T12 | sender (agent) corrects its own type word in the control arm | C seq 2 `"address": "ул. Комиссарова, д. 64, кв. 183"` | C seq 3 `"address": "пер. Комиссарова, д. 64, кв. 183"` | `prompt_rule-026.controls.C.json:42` vs `:108` |
| T13 | same real type, three different sender spellings | `пер.` (C) | `переулок` (C2), `Загородный пр-д` (C2 prose) | `prompt_rule-026.controls.C.json:108`; `prompt_rule-026.controls.C2.json:20`; `long_support-027.controls.C2.json:66` |
| T14 | user's type word overwritten by the engine's substitute type | user `переулок` | substitute `улица` (`Кинешма, улица Мятная…`) | `prompt_rule-026.md:39` vs `:1098`; hop `:1523-1524` `differs` includes `generic`, `generic_position` |
| T15 | user's type word preserved by the engine's substitute | user `курск переулок загородный 16 кв 142` | substitute `курск переулок вишнёвая 99 кв 158` (`переулок` kept) | `long_support-027.md:39` vs `:1770`; hop `:2847-2848` `differs []` |
| T16 | real seed carries type separately from the street value | seed `"street": "загородный"`, declared `"street_type": "переулок"` | agent field `"street": "переулок Вишнёвая"` | `long_support-027.md:87`, `:269` vs `:1527` |

### 2.5 Case (uppercase/lowercase)

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T17 | same address, sender case choice | C `query: "Казань Зацепская 7"` (Title) | I `query: "казань барбарисовая 3"` (lower) | `tool_chain-017.controls.C.json:49` vs `tool_chain-017.md:1079` |
| T18 | restored answer lower-cases the agent's Title form | agent wrote `Сарапул` | produced answer `сарапул` | `memory_anaphora-119.md:1224` vs `:1121`; hop `:1873-1874` `differs ["case_class"]` |
| T19 | structured `street` field restored as the bare lower-case seed value, dropping the sender's Title + generic | written field `Курск`, `переулок Вишнёвая` | restored field `Курск`, `загородный` (lower) | `long_support-027.md:1524-1527` vs `:1534-1538` |

### 2.6 Quotations

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T20 | two occurrences of one marker in one string restored differently | written: unquoted `Курск, переулок Вишнёвая, 99, кв. 158` + quoted `«ул. Вишнёвая»` | restored: unquoted keeps `Вишнёвая` (only `99/158`→`16/142`), quoted becomes `«загородный»` | `long_support-027.md:1564` vs `:1569` |
| T21 | quoted address collapses to the same real value as its unquoted twin | written note: `ул. Кленовая, д. 5, кв. 140` vs `ул. Барбарисовая, д. 3, кв. 228` | restored note: both render `ул. Барбарисовая, д. 7, кв. 31` | `tool_chain-017.md:1307` vs `:1312` |
| T22 | quoted negative stays untouched | `«2 гектаров»` in agent prose | same `«2 гектаров»` in the restored prose | `tool_chain-017.md:1307`, `:1312`; declared negative `:332`, `:336` |
| T23 | quoted address in the user-facing reply | restored reply quotes `«курск, загородный, 16»` | — | `long_support-027.md:2751` |

### 2.7 Bare house/flat

| # | operation | literal A | literal B | location |
|---|---|---|---|---|
| T24 | bare digits live in their own fields | agent `"house": "99", "flat": "158"` | restored `"house": "16", "flat": "142"` | `long_support-027.md:1525-1526` vs `:1536-1537`; hop `:3455-3461` (`same: true`) |
| T25 | bare digits inside prose get markers | user `… 16 кв 142` | agent `… 99, кв. 158` | `long_support-027.md:39` vs `:1564` |
| T26 | bare digits survive a span but not the marker | masked card `house 3`, `flat 228` | restored order `д. 7, кв. 31` | `tool_chain-017.md:1495` vs `:1215` |

## 3. Generated substitute marker vs user correction vs impossible guessing

### 3.1 Marker inventory (engine-generated, not written by any party)

| real value (declared) | marker(s) emitted | location |
|---|---|---|
| `зацепская` / `7` / `31` (`tool_chain-017` i7-i9) | `барбарисовая` (card), `грушевая` + `д 1` (directory), `кленовая` + `5/140` (order echo) | `tool_chain-017.md:1461`, `:1597`, `:1943` |
| `загородный` / `16` / `142` (`long_support-027` i7/i14/i17) | `вишнёвая` / `99` / `158`; full-span `курск переулок вишнёвая 99 кв 158` | `long_support-027.md:1809`, `:1770`, `:1860` |
| `комиссарова` / `64` / `183` (`prompt_rule-026` i7/i10) | `мятная`; full-span `Кинешма, улица Мятная 34, кв. 186`; echo `улица Кедровая, д. 62, кв. 130` | `prompt_rule-026.md:1098`, `:1321` |
| `новая` / `119` / `176` (`memory_anaphora-119` i11) | `ивовая`; full-span `сарапул улица ивовая 146 кв 68` | `memory_anaphora-119.md:1139`, `:1405` |

The generated marker is not a place and not an identity: `grouping/prefix/separators` differences on
phone hops and the `case_class/generic` differences on `long_support-027.md:3481-3482` are recorded
form failures, not identity failures. Identity checks on house/flat (`:3455-3461`) and on the phone
(`:3510-3516`) come back `same: true`.

### 3.2 No user correction of an address exists in these four cases

- `long_support-027.md:39` states the address once: `адрес был курск переулок загородный 16 кв 142`.
  There is no later user turn revising it (`:39` is message 2 of 6; the rest are `посмотрите…
  обращения`, `две карточки… уберите лишнюю`, `переключите на человека`).
- The only "correction" language in the I arm is agent-authored and refers to a marker:
  `Клиент уточнил адрес … (в карточке было «ул. Вишнёвая» — исправлено на переулок)`
  (`long_support-027.md:1564`), and it survives into the restored prose (`:1569`) and the escalation
  summary (`:1645`).
- `memory_anaphora-119` user turns are anaphora (`и мне на тот же телефон тоже`, `пусть курьер
  приедет к нему по тому адресу`), not corrections.
- `tool_chain-017` is an instruction to reuse the card (`:39`, `:40`), not an address statement.
- `prompt_rule-026` states the address once (`:39`).

The one literal *explicit correction* in the four cases is the agent correcting its own type word in
the control arm (`prompt_rule-026.controls.C.json:42` → `:108`), i.e. sender-side, not the user.

### 3.3 Impossible identity guessing

1. **Two markers reconciled as two real addresses.** The agent writes
   `в заказе … ул. Кленовая, 5–140, а в карточке — … ул. Барбарисовая, 3–228. Нужно решить, какой
   вариант верный` (`tool_chain-017.md:1485`) and repeats the "расхождение" in the restored turns
   (`:2361-2362`). No client answer can settle it: both strings are generated markers for
   `зацепская 7 31`. The controls have a single literal (`tool_chain-017.controls.C.json:118`,
   `:49`).
2. **A measure treated as an address.** Declared negative `2 гектаров`
   (`tool_chain-017.md:332`, `:336`, family `measure`) is queried as an address
   (`:1003`, `:1022`, `:1041`) and as a surname (`:1098`, `:1120`); the C control fabricates a
   street form `2-я Гектаров` (`tool_chain-017.controls.C.json:87`). Same for
   `25 гектаров` (`long_support-027.md:514`, `:518`).
3. **A fabricated correction history.** `в карточке было «загородный» — исправлено на переулок`
   (`long_support-027.md:1569`) and `в карточке адрес исправлен на загородный`
   (`:1649`) assert an edit that never happened in the conversation, over a marker.
4. **A marker overwriting the type the user chose.** `prompt_rule-026`: user says `переулок`
   (`:39`), the substitute says `улица` (`:1098`), and the restored agent form then reads
   `улица Мятная, д. 64, кв. 183` (`:1026`) with residual `"to_location.address": ["мятная"]`
   (`:1076`). Neither the user's `переулок` nor the seed's `street_type: переулок` (`:226`) is
   recoverable from the string alone.

## 4. Counterexamples (form preserved, or no transformation)

| case | literal | record | location |
|---|---|---|---|
| `memory_anaphora-119` IN | real `сарапул улица новая 119 кв 176` → emitted `сарапул улица ивовая 146 кв 68` | `same: true`, `differs []` — city position, `улица`, `кв`, lower case all mirrored | `:39` vs `:1405`; hop `:1602-1603` |
| `memory_anaphora-119` memory hop | same pair resolved from `тот адрес` | `same: true`, `differs []` | hop `:1677-1678` |
| `long_support-027` IN | real `курск переулок загородный 16 кв 142` → `курск переулок вишнёвая 99 кв 158` | `same: true`, `differs []` — `переулок` kept | hop `:2847-2848` |
| `tool_chain-017` IN (directory) | real `г Казань, ул Зацепская, д 7` → `г Казань, ул Грушевая, д 1` | `same: true`, `differs []` — `г`, `ул`, `д` layout kept | `:2437-2438` |
| controls | the real value is written verbatim (no marker anywhere); `substitutes: {}`, `masked_spans: {}` | — | `tool_chain-017.controls.C.json:118`; `long_support-027.controls.C2.json:131`; `memory_anaphora-119.controls.C2.json:53` |
| both legs | `city` and `postal_code` are identical in `text_real` and `text_masked` | e.g. `"city": "курск"` in both | `long_support-027.md:1859-1860`; `tool_chain-017.md:1942-1943` |
| `long_support-027` house/flat | `99→16`, `158→142` | `same: true` | hop `:3455-3461` |

So the transformations above are not universal behaviour: the same engine mirrors the sender's
shape in `memory_anaphora-119` / `long_support-027` IN hops and re-renders it in
`prompt_rule-026` IN, `long_support-027` OUT `street`, and `memory_anaphora-119` OUT `answer`.

## 5. What generalizes (reading, not a policy decision)

The literal operations observed are parametric, not case-specific:

- which **generic word** is present (`улица` / `переулок` / `пер.` / `пр-д` / none),
- where it sits (in prose before the street; inside a structured `street` field; absent),
- which **markers** wrap house/flat (`д.` / `кв.` / `квартира` / bare / comma-separated),
- **order and punctuation** (city-first with comma vs bare city-first, no commas),
- **case class** of the whole address (lower / Title),
- **delimitation** (quoted or not; prose vs JSON field),
- **decomposition** (single line vs `city/street/house/flat`), and
- whether the value is a **full span** or a **bare house/flat**.

Every one of these is chosen by the sender of that hop and is visible in the literal strings. The
identity (`зацепская 7 31`, `загородный 16 142`, `комиссарова 64 183`, `новая 119 176`) is
recoverable only through the vault link, never from the marker text — see §3.3.1–3.3.4. The traces
therefore support deriving the rule from the sender's literal form for any (generic, markers, order,
case, delimiter, decomposition) tuple rather than enumerating a fixed list of street types or case
ids.

## 6. Unresolved semantics (explicit; no decision taken here)

1. **Which type word is authoritative when the sender's conflicts with the seed.** `long_support-027`:
   sender `переулок Вишнёвая` (`:1527`), seed `street_type: переулок` (`:269`) — agree;
   `prompt_rule-026`: sender (agent, from the substitute) `улица Мятная` (`:1005`), user `переулок`
   (`:39`), seed `street_type: переулок` (`:226`) — disagree. Whether `restored` must reproduce the
   sender's word, the user's word, or the seed's field is not settled by the evidence.
2. **Field vs prose for the same identity.** The `street` field restore returned bare
   `загородный` (`:1538`), while quoted prose in the same turn returned `загородный` too (`:1569`)
   and unquoted prose kept `Вишнёвая`. Whether a structured field may drop the generic at all is
   open.
3. **Occurrence-level vs value-level restoration inside one string.** `long_support-027.md:1569`
   restores one occurrence of `Вишнёвая` and leaves the other; `tool_chain-017.md:1312` collapses two
   different markers to one value in one sentence. Which occurrence wins is not defined here.
4. **Whether one real address may hold more than one live marker in a conversation.**
   `memory_anaphora-119` uses one (`ивовая`) across IN/memory hops; `tool_chain-017` uses three
   (`барбарисовая`, `грушевая`, `кленовая`) in one turn. The consequence is visible as a fabricated
   discrepancy (`:1485`), but the intended cardinality is not stated in the evidence.
5. **What `reference` means on an OUT hop.** For `long_support-027` `street` it is the agent's written
   marker form `переулок Вишнёвая` (`:3482`); for house/flat and phone it is the written marker too
   (`:3456`, `:3511`). Whether the restore target is the agent's form or the canonical real value is
   therefore read from the observer, not defined.
6. **Quotes as a form signal.** `long_support-027.md:1569` and `tool_chain-017.md:1307` show quoted
   spans behaving differently from unquoted ones; whether quotes are load-bearing for restoration is
   unresolved.
7. **Negative measure vs address candidate.** `2 гектаров` / `25 гектаров` are declared negatives
   (`tool_chain-017.md:332`, `long_support-027.md:514`) but the agent queries them as addresses and
   as names (`tool_chain-017.md:1003`, `:1098`, C control `:87`). Whether the engine owes any guard
   on the OUT leg is open.
8. **`city` on both legs.** `city` is byte-identical in `text_real` and `text_masked`
   (`long_support-027.md:1859-1860`), yet the answer hop records `сарапул` vs `Сарапул` as
   `case_class` (`memory_anaphora-119.md:1873-1874`). Whether `city` is a PII part or a place
   reference is not resolved by these traces.
