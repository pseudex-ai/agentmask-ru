# Brief — component `tools` (owner code **T**)

You build the v5 tool registry and the v5 mock backend: 31 v4 tools revised +
12 new tools across 11 verticals, each with a declared return form, and a mock
that renders the REAL value strictly in each API's own format (that is what
the IN/tool hop measures). You do not build metrics, the comparator, scenarios
or the harness.

## Read first, in this order

1. `docs/tz-agentpii5.md` §2 and §8.1 (the tables are your requirements).
2. `bench/agentpii5/contracts.py` §3 (`RETURN_FORMS`, `VERTICALS`,
   `TOOL_VERTICAL`, `NEW_TOOL_NAMES`, `NEW_TOOL_RETURN_FORMS`,
   `NEW_TOOL_RESULT_TYPES`, `VERTICAL_RULES`, `ReturnForm`, `ToolSpecV5`,
   `ResultRenderer`, `ForcedError`, `ECHO_TAG_PREFIX`).
3. `bench/agentpii5/CHECKLIST.md` — the items marked **T** are yours.
4. `bench/agentpii4/tools.py` in full: `Refusal`, `FieldSpec`, `ToolSpec`, the
   primitive parsers (`parse_e164`, `parse_iso_date`, `parse_digits`,
   `parse_card`, `parse_snils`, `parse_inn`, `parse_name_word`…), `_schema`,
   how every `*_parse` refuses with a documented rule name, `REGISTRY`,
   `spec_for`, `flatten`, and `main()` (the good/bad shape test pattern you
   will copy).
5. `bench/agentpii4/mock.py` in full: `Backend`, `CallLog`, `_apply`,
   `_domain_error`, `_store`, `snapshot`; `bench/agentpii4/writer.py`: `Slot`,
   `serialise` (a result is a Slot tree; `serialise` returns text + spans).
6. `bench/agentpii4/fake_agent.py::seed_backend` (how v4 seeds a backend from
   a case) — you write the v5 equivalent.

## Rules

- Comments in English, dense «why not the alternative» style. Docstrings are
  the design record. No default parameter values. Strict typing, no `Any`.
- **Never import `pseudex`** (test: `test_tools.test_no_pseudex`,
  `test_mock.test_no_pseudex`). The mock is the customer's system; if it
  shared the engine's validators the instrument would be part of the detector.
- **Do not edit** `bench/agentpii4/`, `pseudex/`, `public/`. To fill a v4
  tool's empty `result_pii`, use `dataclasses.replace(v4_spec, result_pii=…)`
  on the imported object — never edit `agentpii4/tools.py`.
- Every parser is taken from the documentation of a real Russian API and the
  `source` string cites it. A parser accepts exactly what the API accepts,
  refuses with the documented rule's name, never repairs.
- Do not commit. Run tests from `prototype/` with the venv:
  `python3 -m bench.agentpii5.test_tools && python3 -m bench.agentpii5.test_mock`.

## Files to create

| file | what |
|---|---|
| `bench/agentpii5/tools.py` | `REGISTRY_V5: dict[str, ToolSpecV5]` (43 entries), the 12 new `ToolSpec`s with their parsers, `registry_problems() -> list[str]` (rules V01–V05), `spec_v5_for(tool, path)` |
| `bench/agentpii5/mock.py` | `BackendV5(Backend)`: new tables, seeds, `_apply` for the 12 new tools, return-form rendering with item-id slot tags, forced errors, `form_of(seq)`; `seed_backend_v5(case: CaseV5) -> BackendV5` |
| `bench/agentpii5/test_tools.py` | see «Acceptance tests» |
| `bench/agentpii5/test_mock.py` | see «Acceptance tests» |

## Step by step

### 1. `tools.py` — the 31 v4 tools revised

For every name in `contracts.V4_TOOL_NAMES` build a `ToolSpecV5`:

- `base`: the v4 `ToolSpec` from `bench.agentpii4.tools.REGISTRY`. Where its
  `result_pii` is empty (22 of 31 are), `dataclasses.replace` it with the
  dotted result paths that carry PII — read `mock._apply` for that tool to
  see what the result actually contains (e.g. `delivery_create_order` returns
  `recipient.name`, `recipient.phone`, `to_location.city`,
  `to_location.address`). A tool whose v4 result truly carries no PII
  (`crm_merge_contacts`, `order_cancel`, `delivery_quote`…) MUST be given a
  result that does in `BackendV5._apply` (e.g. `order_cancel` returns the
  cancelled order's recipient as CDEK does) — rule V04 says every tool has an
  IN/tool hop to measure.
- `vertical`: `contracts.TOOL_VERTICAL[name]`.
- `return_forms`: at least one `ReturnForm(form, example, pii_paths)`;
  `example` is a serialised JSON string the mock's rendering matches in
  SHAPE (same keys, nesting, separators); `pii_paths` are the paths carrying
  PII in THAT form.
- `differs_from_user_form`: True iff some form renders a type in a notation a
  user register never writes (`canon`, ISO dates, `+7 (916) 123-45-67`,
  `XXX-XXX-XXX YY`).

### 2. `tools.py` — the 12 new tools

One `ToolSpec` each (v4 shape: `name`, `source`, `schema` via v4's `_schema`,
`fields`, `parse`, `mutating`, `result_pii`), wrapped in `ToolSpecV5` with the
forms in `contracts.NEW_TOOL_RETURN_FORMS[name]` (you may ADD forms, never
remove) and result types `contracts.NEW_TOOL_RESULT_TYPES[name]`. Parsers,
explicit:

| tool | arguments and refusal rules |
|---|---|
| `kb_search` | `query` string 1–200 chars (`not_a_string` / `too_long` / `empty_query`); `k` int 1–10 (`out_of_range`). `mutating=False`. Fields: `query` kind `free` (PII may be inside), `k` plain. |
| `doc_retrieve` | `doc_id` matches `doc-\d+` (`id_format`). read. |
| `file_read` | `path` string ending `.txt`/`.csv`/`.docx` (`path_extension`), no `..` (`path_traversal`). read. |
| `form_parse` | `text` string ≤ 4000 (`too_long`), non-empty (`empty_text`). read. Field `text` kind `free`. |
| `bank_client_find` | exactly one of `inn` (10 or 12 digits, `inn_format`, checksum via v4 `parse_inn` → `inn_checksum`) or `phone` (E.164 via v4 `parse_e164`) — `exactly_one_key`. Fields: `inn` identity `INN`, `phone` identity `PHONE` role `digits`. read. |
| `account_statement` | `client_id` matches `bc-\d+` (`id_format`); optional `from`, `to` ISO dates (v4 `parse_iso_date`), `from <= to` (`range_order`). read. |
| `vehicle_check` | `plate` matches `^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$` — Cyrillic upper case, no spaces (`plate_format`; a Latin look-alike letter is `plate_format` too — the real service takes Cyrillic). Field `plate` identity `PLATE`. read. |
| `snils_verify` | `snils` via v4 `parse_snils` (`snils_format`, `snils_checksum`). Field identity `SNILS`. read. |
| `calendar_free` | `person` 1–3 name words (v4 `parse_name_word` per word, `name_format`); `date` ISO (`date_not_iso8601`). Fields: `person` identity `NAME`. read. |
| `email_send` | `to` matches `[^@\s]+@[^@\s]+\.[a-z]{2,}` (`email_format`); `subject` ≤ 200; `body` ≤ 4000 (`too_long`). Fields: `to` identity `EMAIL`; `subject`, `body` kind `free`. `mutating=True`. |
| `ticket_history` | `issue_id` matches `t-\d+` (`id_format`). read. |
| `courier_status` | `claim_id` with the prefix v4's `Backend` allocates for the `claims` table (read `mock._apply` for `courier_book`) (`id_format`). read. |

For every new tool, `schema` descriptions are in Russian like v4's.

### 3. `tools.py` — the registry and the rules

`REGISTRY_V5 = {spec.base.name: spec for spec in (...)}` with exactly 43
entries. `registry_problems()` returns every violation of V01–V05
(`contracts.VERTICAL_RULES`) as one string each, never the first only. Also
export `spec_v5_for(tool: str, path: str) -> FieldSpec | None` delegating to
v4's `spec_for` for v4 tools and to your own for the new ones.

### 4. `mock.py` — `BackendV5`

Subclass v4 `Backend`. Constructor
`BackendV5(now_iso: str, forced: tuple[ForcedError, ...], echo_values: dict[str, str])`
— `echo_values` maps `ForcedError.echo_item_id` → the real value to echo.

- New tables: `kb_chunks`, `documents`, `bank_clients`, `vehicles`,
  `snils_records`, `calendar`, `ticket_events`, `emails`. Seeds:
  `seed_chunk(id, fields)`, `seed_document(id, fields)`,
  `seed_bank_client(id, fields)`, `seed_vehicle(id, fields)`,
  `seed_snils(id, fields)`, `seed_calendar(id, fields)`,
  `seed_ticket_event(id, fields)`. Seeds have `seq == 0` (not effects), like v4.
- `call(tool, arguments)`: if `(tool, ordinal-of-this-tool-so-far)` matches a
  `ForcedError`, return a `CallLog` with `refusal=None`, `parsed=None`, a
  result body `{"error": {"code": forced.code, "message": <template with
  {value} filled>}}` rendered with a `Slot(value, ECHO_TAG_PREFIX + item_id)`,
  and record form `error_with_value`. Otherwise delegate to `super().call`.
  Keep a `forms: list[str]` parallel to `self.calls` and expose
  `form_of(seq: int) -> str`.
- `_apply` for the 12 new tools, returning `(data, slot_tree)` like v4. The
  Slot TAG of every value that came from a SEED item is that item's id (the
  seed field → item id map is built in `seed_backend_v5` from
  `SeedRecord.pii_ids` and `PiiItem.where.path`). Choose the form from state:
  found → `single`/`list`/`nested`/`free_text`/`chunks`; nothing found →
  `empty` (`{"items": []}` or `{"found": false}` per API); a domain error →
  `error_with_value` via `_domain_error` with the offending value in a Slot.
- Rendering rules per form (these ARE the API formats the IN/tool hop tests):
  - `canon` (`address_suggest`, `normalize_contact`): DaData shape —
    `«г Самара, ул Луговая, д 10»` (no dots after generic abbreviations,
    comma-separated, `д` before the house), phone `+7 (916) 123-45-67`.
  - `courier_status` nested: `{"recipient": {"name": …, "phone": "+7916…"},
    "address": "г. Ижевск, ул. Пушкина, д. 41, кв. 7"}` (dots, `д.`/`кв.`
    with a space).
  - clinic/`snils_verify`: `birth_date` `YYYY-MM-DD`; `snils` `XXX-XXX-XXX YY`.
  - `bank_client_find` / `account_statement`: `card` as `XXXX XXXX XXXX XXXX`,
    `inn` as bare digits; ≥ 2 statement rows of the same person.
  - `kb_search` chunks: `{"hits": [{"id": …, "score": 0.91, "text": "…"}, …]}`,
    `k` hits, each `text` a sentence with ≥ 1 PII slot, ranked; chunks of
    OTHER identities seeded as `kb_chunks` are included.
  - `file_read` / `doc_retrieve`: `free_text` — the document body as one
    string with slots; for `csv` documents also a `list` form with one row
    per line (`last_name;first_name;phone;email;birth_date` like v4
    `CSV_HEADER`); for `scan` documents apply a SEEDED noise (`random.Random(
    f"scan:{doc_id}")`): Latin look-alikes for `о/а/е/с` in 5% of letters,
    a doubled space in 3% of gaps — deterministic for a given doc id.
  - `calendar_free`: `{"person": …, "slots": ["2026-09-10T09:30:00+03:00",
    "10.09.2026 11:00", …]}` — ≥ 2 notations across the list, chosen by a
    seeded draw.
  - `ticket_history`: prose paragraphs `«12.09 клиент Иванов Пётр (+7916…)
    просил перенести…»` with ≥ 2 PII slots.
- `seed_backend_v5(case: CaseV5) -> BackendV5`: calls v4
  `fake_agent.seed_backend`'s logic for `contacts`/`addresses` (copy the
  loop — v4's function returns a v4 `Backend`, and you need a `BackendV5`)
  and seeds the new tables from `SeedRecord.table`; builds `echo_values`
  from `case.forced`.

### 5. Examples and shape check

For every `ReturnForm.example`, `test_tools` parses it as JSON and asserts
every `pii_paths` entry resolves in it (arrays as `[]`). `test_mock` renders
each tool in each declared form and asserts the rendered JSON has the same
key set and nesting as the example (values differ).

## Acceptance tests you must ship

`bench/agentpii5/test_tools.py` (`main()` returns 1 on any failure):

- `test_no_pseudex` — import `bench.agentpii5.tools`; no `sys.modules` key
  starts with `pseudex`.
- `test_counts` — `len(REGISTRY_V5) == 43`; `set(REGISTRY_V5) ==
  set(V4_TOOL_NAMES) | set(NEW_TOOL_NAMES)`; every `vertical` in `VERTICALS`
  and equal to `TOOL_VERTICAL[name]`.
- `test_v4_kept` — every v4 name present; `spec.base.schema` equals v4's
  schema object for that name (`is` or `==`).
- `test_v4_tools_revised` — every v4 tool has ≥ 1 `ReturnForm` and
  non-empty `base.result_pii`.
- `test_vertical_rules` — `registry_problems() == []`; then break the
  registry in memory (drop every `list` form of one vertical) and assert a
  V01 problem appears — the rule must be able to fail.
- `test_every_tool_has_form` — V04 on every tool.
- `test_parsers_good_bad` — for each of the 12 new tools ≥ 1 accepted shape
  and ≥ 1 refused shape with the exact rule name from the table above (the
  v4 `main()` pattern).
- `test_examples_resolve` — every example parses and its `pii_paths` resolve.
- `test_directory_canon`, `test_clinic_iso_snils`, `test_bank_forms`,
  `test_ticket_history_free_text`, `test_calendar_notations`,
  `test_government_forms`, `test_kb_search_chunks`, `test_file_forms`,
  `test_courier_status_forms`, `test_nested_address`, `test_file_read_scan_noise`
  — each renders through `BackendV5` and asserts the exact notation named in
  CHECKLIST C-027…C-036, C-050, C-117.

`bench/agentpii5/test_mock.py`:

- `test_no_pseudex`.
- `test_forced_error` — a `ForcedError` on ordinal 0 yields
  `error_with_value` with the echoed real value at
  `spans_real[ECHO_TAG_PREFIX + item_id]`; ordinal 1 of the same tool parses
  normally; `form_of` reports both.
- `test_error_echoes_value` — the echoed text equals `echo_values[item_id]`
  byte for byte.
- `test_slot_tags_are_item_ids` — after `seed_backend_v5` on a hand-built
  `CaseV5`, a lookup's `result_spans` keys are exactly the seed item ids of
  the returned record.
- `test_ids_by_writes_only`, `test_snapshot_typed` — v4 invariants hold on
  the subclass (an extra read does not shift ids; `snapshot()` excludes seeds).
- `test_each_form_renders` — every declared form of every tool is producible
  from some state and serialises (`writer.serialise` round-trips).

## What you must NOT touch

`bench/agentpii4/**`, `pseudex/**`, `public/**`, and every other
`bench/agentpii5/` file (contracts, form, metrics, observe, fixtures, report,
schema, scenarios5, harness, judge, calibration, records). If a contract
seems wrong, write it in your final message under «contract questions»; do
not change `contracts.py`.

## Checklist items you own

C-006, C-027, C-028, C-029, C-030, C-031, C-032, C-033 (tool half), C-034,
C-035, C-036, C-039, C-040, C-042 (mock half), C-049, C-050, C-051, C-053,
C-054, C-055 (renderer half), C-060 (renderer half), C-062 (renderer half),
C-106, C-113–C-130.

## Definition of done

Both tests PASS; `registry_problems() == []`; `git --no-pager diff --stat --
bench/agentpii4 pseudex public` is empty; your final message lists the files,
the test commands and their output, and any contract questions.
