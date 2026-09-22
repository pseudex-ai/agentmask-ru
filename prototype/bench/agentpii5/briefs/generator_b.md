# Brief — component `generator_b` (owner code **GB**)

You own the corpus SPINE of v5 and four new families. Spine: `schema.py`
(`CaseV5` validation, corpus validation, JSON round trip, digest),
`scenarios5/common.py` (the concrete `CaseBuilderV5` implementing
`contracts.CaseKit`, the v5 register mix, INN/PLATE renderers, v5 role
prompts), `revise.py` (the 834 v4 cases → `CaseV5`, the 455 with results
getting hops 3–4), `build.py` (assemble v4-revised + plan_a + plan_b,
freeze the ladder with a holdout, `--check`). Families:
`user_in_loop` (40), `memory_anaphora` (120), `rag` (100), `document` (100).

generator_a builds against your `common.py` and `schema.py` — deliver those
two FIRST (step 1–2 below), then the rest.

## Read first, in this order

1. `docs/tz-agentpii5.md` §1, §3.3–§3.7, §8.2.
2. `bench/agentpii5/contracts.py` §1, §2 in full (every dataclass, R01–R21,
   K01–K15, `CaseKit`, `V4_KIND_TO_BEHAVIOUR`, `REGISTER_SHARES`,
   `BEHAVIOUR_FLOORS`, `CORPUS_SIZE_BAND_V5`, `MIN_CASES_BY_TYPE`,
   `V4_TYPE_ITEM_COUNTS`, `MIN_STREAMING_CASES`), §3 (tools, return forms),
   §8 (`RUN_FILES`: `corpus.json` is v4-shaped, `corpus.v5.json` is yours).
3. `bench/agentpii5/CHECKLIST.md` — items marked **GB**.
4. `bench/agentpii4/schema.py` in full (`Case`, `PiiItem`, `Locus`,
   `SeedRecord`, `validate`, `validate_corpus`, `case_from_json`,
   `corpus_digest`, `Ladder`, `sample`, `tier`, `TIER_SIZES`),
   `bench/agentpii4/scenarios/common.py` in full, `bench/agentpii4/pools.py`
   (renderers; note there is no plate renderer — you add one in v5),
   `bench/agentpii4/build.py` (`PLAN`, `build_ladder`, `--check`),
   `bench/agentpii4/validate.py` (`prove_no_search`, `find_distinct_share`),
   `bench/agentpii4/tools.py` (`REGISTRY`, `FieldSpec`, `result_pii`),
   `bench/agentpii4/corpus.json` (the 834 you revise — load with
   `case_from_json`), and two v4 scenarios: `long_clinic.py`,
   `long_support.py`.
5. `bench/agentpii5/briefs/generator_a.md` §«Hop declaration» — the recipe
   both generators follow; your `revise.py` applies the same recipe to v4
   cases mechanically.

## Rules

- English comments; docstrings are the design record; no default parameter
  values; strict typing; no `Any`.
- **No `pseudex` import** anywhere in your files.
- Nothing searches a finished message (`prove_no_search`).
- `validate_v5` reports EVERY problem, one string per rule, prefixed with
  the rule id (`R07 …`), never the first only; `validate_corpus_v5` likewise
  with `K..`. Do not call v4's `validate_corpus` (its band and clean cap are
  v4's); DO call v4's per-case `validate(case.base)` (R02).
- Do not commit. Tests: `python3 -m bench.agentpii5.test_schema`,
  `test_revise`, `test_build`, `test_generator_b`.

## Files to create

| file | what |
|---|---|
| `bench/agentpii5/schema.py` | `validate_v5(case) -> list[str]`, `validate_corpus_v5(cases, registry_v5) -> list[str]`, `case_v5_to_json`, `case_v5_from_json`, `corpus_digest_v5`, `has_result(hops) -> bool` |
| `bench/agentpii5/scenarios5/__init__.py` | empty docstring module |
| `bench/agentpii5/scenarios5/common.py` | `CaseBuilderV5` (implements `contracts.CaseKit`), `registers_for` (v5 mix), `ctx_for`, `plate(ctx, text) -> Rendered`, `inn(ctx, digits)` re-export, `system_prompt_v5(role, now, extras)` with the parallel-calls and branching clauses, `chunk_seed`, `document_seed`, `bank_client_seed`, `vehicle_seed`, `snils_seed`, `calendar_seed`, `ticket_event_seed` |
| `bench/agentpii5/scenarios5/user_in_loop.py`, `memory_anaphora.py`, `rag.py`, `document.py` | the four families |
| `bench/agentpii5/scenarios5/plan_b.py` | `PLAN_B: tuple[tuple[object, int], ...]` |
| `bench/agentpii5/revise.py` | `revise(v4_cases) -> list[CaseV5]` |
| `bench/agentpii5/build.py` | `build_corpus(seed)`, `build_ladder`, CLI `--check`, `--regenerate-ladder`; writes `corpus.v5.json`, `corpus.json` (v4 view), `ladder.json` |
| `bench/agentpii5/test_schema.py`, `test_revise.py`, `test_build.py`, `test_generator_b.py` | see «Acceptance tests» |

## Step 1 — `schema.py`

- `validate_v5(case: CaseV5) -> list[str]`: rules R01–R21 of
  `contracts.V5_CASE_RULES`, in that order, each producing a message that
  starts with its id. R19 needs the tool's declared forms: import
  `bench.agentpii5.tools.REGISTRY_V5` lazily inside the function (the tools
  component may land later; until then, R19 checks `form in RETURN_FORMS`
  only and says so in a comment with a TODO that `test_schema` removes when
  `REGISTRY_V5` imports).
- `validate_corpus_v5(cases, registry_names: tuple[str, ...]) -> list[str]`:
  K01–K15 of `contracts.V5_CORPUS_RULES`. K02 is a FLOOR (≥
  `BEHAVIOUR_FLOORS`, share ≥ `BEHAVIOUR_SHARES - SHARE_TOLERANCE`), no
  ceiling; print each family's MDE with
  `bench.agentpii4.stats.mde_paired(n, 0.10, 2.1)` in `build.py`.
- `case_v5_to_json(case) -> dict[str, object]`: `{"base": case.base.to_json(),
  "behaviour": …, "hops": [asdict(h)], "returns": …, "forced": …, "memory":
  …, "pick": … | None, "branch": …, "loop": …, "rag": …, "document": …,
  "has_result": …, "streaming": …, "revised_from_v4": …}`;
  `case_v5_from_json` inverts it using v4's `case_from_json` for `base`.
- `corpus_digest_v5(cases)`: sha256 over `case_v5_to_json` sorted-keys JSON,
  case by case, like v4.
- `has_result(hops)`: any IN/tool and any OUT/answer.

## Step 2 — `scenarios5/common.py`: the builder

`CaseBuilderV5` WRAPS a v4 `CaseBuilder` (composition: `self.v4 =
CaseBuilder(...)`) and re-exposes `user(draft, typed) -> int` and
`seed(record_id, table, fields, typed_paths)`; the v4 builder's
`contact_seed` works through it. It adds the `CaseKit` methods
(`declare_hop`, `expect_return`, `force_error`, `remember`, `set_pick`,
`set_branch`, `set_loop`, `set_rag`, `set_document`, `set_streaming`) that
append to lists, and `build(behaviour) -> CaseV5` which calls
`self.v4.build()`, computes `has_result`, assembles `CaseV5`, runs
`validate_v5` and raises `bench.agentpii4.schema.InvalidCase` with every
problem joined by newlines. `revised_from_v4=False`.

Also:
- `registers_for(count, rng)` with the v5 mix `voice_raw 0.28, voice_itn
  0.17, chat 0.25, sloppy 0.15, clean 0.10` (round-robin like v4, never
  `rng.sample` — clean must not round to zero in small families), then a
  5% remainder to `chat`.
- `plate(ctx, text)`: `Rendered(surface, canonical, spoken, parts)` with
  `parts = {"series": "А", "digits": "123", "letters": "ВС", "region": "77"}`
  — Cyrillic letters only from `АВЕКМНОРСТУХ`; canonical `А123ВС77`
  (no space); `chat`/`sloppy` surfaces `а123вс 77` / `А123ВС77`; `voice_raw`
  «а сто двадцать три вэ эс семьдесят семь» via v4's numeral speller
  (`pools.spell_number` or equivalent — read `pools.py` for its name);
  `voice_itn` «а 123 вс 77». Every spoken form must parse back to its
  digits (`pools.parse_numerals`), like every v4 spoken value.
- Seed helpers for the new tables, mirroring `contact_seed`: `typed_paths`
  register every PII field as a seed item with the right type
  (`bank_clients.inn` → INN, `vehicles.plate` → PLATE, `snils_records.snils`
  → SNILS, `kb_chunks.text` → the chunk's items by offset — a chunk is a
  free-text field with SEVERAL items, so its `Locus.path` is
  `text` and each item's `where.start/end` index into the chunk text; the
  mock renders the chunk from the seed text and tags slots by item id).
- `system_prompt_v5(role, now, extras: tuple[str, ...])`: v4's
  `system_prompt` plus the extra clauses a family needs (parallel calls,
  branching rule, «use the file», «the customer confirms before you act»).

## Step 3 — `revise.py`: the 834

For each v4 `Case` (loaded from `bench/agentpii4/corpus.json` with v4's
`case_from_json`; the messages, items, seeds, negatives, trace are kept
BYTE-IDENTICAL — `test_revise.test_messages_byte_identical`):

1. `behaviour = V4_KIND_TO_BEHAVIOUR[case.kind]`.
2. IN/user hops for every message-locus item (turn = `where.msg`).
3. OUT/tool_arg hops: for every `expects.reachable_tools` tool, for every
   `FieldSpec` with `kind == "identity"` whose `pii_type` equals an item type
   of the PRIMARY identity: one hop per such item, `call_ordinal 0`, `turn`
   = the LAST user message before the case ends (v4 cases do not say which
   turn a call happens in; the last turn is the one the harness's
   `call_turns` will match when the agent calls at the end — document this
   approximation in the module docstring), `optional = not spec.required`,
   owner via `hop_owner_of_leaf`, `source_hop` = the item's IN/user hop or,
   for seed items, the IN/tool hop.
4. For the 455 with `seed_records`: for every seed item, an IN/tool hop on
   the reachable tool whose `result_pii` covers the seed field (`contacts.*`
   → `crm_find_contact` `contacts[].<field>`; `addresses.*` →
   `address_suggest`), `call_ordinal 0`, `turn` = the first user turn; a
   `ReturnExpectation(tool, 0, "single" or "list" per the tool's declared
   forms, result_item_ids)`; and OUT/answer hops (`optional=True`) for the
   primary identity's seed items. For `summary` cases OUT/answer hops for
   `must_contain` values are `optional=False`.
5. `fanout_pick` kinds (`compare`, `lookup_list`, `search_rank`): build
   `PickSpec` from the seeds (candidates = identities of the seeds; target =
   `expects.primary_identity`; list_tool = the reachable lookup; act_tool =
   the reachable mutating tool). `branching` (`prompt_rule`): `BranchSpec`
   with `seed_present = bool(seed_records)`, then/else = the two reachable
   tools named in the prompt. `user_in_loop` (`long_clinic`): `LoopSpec`
   from the turns (show = the turn after the find, confirm = the next user
   turn, phrase = that message's text with no item inside — R15; if the v4
   message carries a value, mark the case `behaviour="sequential_chain"`
   instead and note it).
6. `streaming = True` for every 8th case with `register in SPEECH_REGISTERS`
   and a result (K11 needs ≥ 60).
7. `revised_from_v4 = True`; validate; a v4 case that cannot be made valid
   is a FINDING to print, not to silently drop — `revise()` raises with the
   list unless `--allow-drop` is passed to `build.py`, which then prints the
   dropped ids and keeps K10 red.

## Step 4 — the four families

### `user_in_loop` (40) — §3.1 row 8
Turn 1: the user gives a cue («я записан, фамилия Петров»); the agent finds
(`crm_find_contact` / `bank_client_find` / `ticket_find`) and SHOWS what it
found (OUT/answer hops, `optional=False` for the value the prompt tells it
to read back). Turn 2: `confirm_phrase` («да, это я», «верно, действуйте»)
with NO value (R15). Turn 3 (optional): the act (`appointment_reschedule`,
`payment_refund`, `order_reschedule`) with OUT/tool_arg hops whose
`source_hop` is the IN/tool hop of the find. `LoopSpec` set.

### `memory_anaphora` (120) — §3.3
5–8 user turns, 2–3 identities, ≥ 3 `MemorySpec`s per case in ≥ 5 cases
(K14), `anaphora` ≠ `none` in ≥ 50% of specs («ему», «на тот адрес», «тот
же телефон», «первому клиенту»). The value is WRITTEN at `first_turn` and
NOT written at `recall_turn` when anaphora ≠ none (R16); the tool called at
the recall turn needs it (OUT/tool_arg with `source_hop` = the IN/user hop
of the first turn). A summary at the end (`escalate_to_human` /
`crm_add_note`) carries several values (OUT summary hops).

### `rag` (100) — §3.4
`kb_search(query, k)` with `k ∈ {3, 5}`; seeds `kb_chunks` for `k` chunks:
1–2 about the customer, the rest about `foreign_identities` (≥ 1), one chunk
carrying TWO identities in ≥ 30 cases; `RagSpec` set; OUT/tool_arg on
`kb_search.query` (the query carries the customer's value — a `free` leaf,
declare the hop with `path="query"`); IN/tool hops for every chunk item
(`path="hits[i].text"`); then an act or an answer; `must_not_contain` = the
foreign identities' values. Ten cases use `doc_retrieve` instead.

### `document` (100) — §3.5
`DocumentSpec` with all four `DOCUMENT_FORMATS` (≥ 20 each): `csv` via
`file_read` (`list` form, `record_count ≥ 2`, `extract_to_tool =
crm_import_csv` or `crm_upsert_contact`), `form` via `form_parse` (`nested`:
ФИО, ДР, паспорт, СНИЛС, адрес — `extract_to_tool = passport_verify` /
`clinic_book`), `free_text` and `scan` via `file_read`/`doc_retrieve`
(`extract_to_tool = crm_upsert_contact` / `ticket_create`). IN/document hops
(owner `document`) for every item in the document (`path` = the document
field), OUT/tool_arg hops for `extracted_item_ids` with `source_hop` → the
IN/document hop, OUT/answer. ≥ 20 document cases carry INN and ≥ 20 carry
PLATE (K05, your share).

## Step 5 — `build.py`

`build_corpus(seed)` = `revise(v4 corpus)` + every `(module, count)` of
`plan_a.PLAN_A` and `plan_b.PLAN_B` (`module.build(seed, count)`).
`--check`: `validate_v5` on every case, `validate_corpus_v5` with
`tuple(REGISTRY_V5)` (or v4 `REGISTRY` + `NEW_TOOL_NAMES` until tools
lands), `prove_no_search` over `scenarios5/` AND v4's `scenarios/` (the
revised cases are re-validated, not re-generated), print shares per
behaviour / register / type, cases with result, INN/PLATE counts, streaming
count, and each family's MDE. Without `--check`: write `corpus.v5.json`
(`{"corpus": [...], "digest": corpus_digest_v5}`), `corpus.json` (v4 view:
`{"corpus": [case.base.to_json()], "digest": v4.corpus_digest}`), and
`ladder.json` via v4's `build_ladder` logic on the `.base` cases with
`holdout` = 20% drawn FIRST and never part of another tier; an existing
`ladder.json` is kept unless `--regenerate-ladder` (K12).

## Acceptance tests you must ship

- `test_schema.py`: `test_no_pseudex`; one test per rule `test_r01` …
  `test_r21` — build a valid hand case, break exactly that rule, assert the
  message with that id appears and nothing else new; `test_k02_floor_not_
  ceiling`, `test_k03`, `test_k04`, `test_k05`, `test_k10`, `test_k11`,
  `test_k13`, `test_k14`, `test_k15` on small synthetic corpora;
  `test_json_round_trip` (`case_v5_from_json(case_v5_to_json(c)) == c`).
- `test_revise.py`: `test_messages_byte_identical`; `test_455_get_loop`
  (exactly the cases with seeds have `has_result`); `test_k10`;
  `test_behaviour_mapping`; `test_all_valid` (no revised case fails
  `validate_v5`).
- `test_build.py`: `test_holdout_frozen` (second build without the flag
  keeps `ladder.json` byte-identical); `test_v4_view_loads` (v4's
  `case_from_json` reads every entry of `corpus.json`); `test_check_prints_
  shares`.
- `test_generator_b.py`: `test_no_pseudex`; `test_build_each_family`;
  `test_loop_confirm_has_no_value`; `test_anaphora_not_written`;
  `test_rag_foreign_identities`; `test_document_formats`;
  `test_type_quotas` (≥ 20 INN, ≥ 20 PLATE); `test_plate_spoken_parses`;
  `test_registers`; `test_no_search`.

## What you must NOT touch

`bench/agentpii4/**` (read `corpus.json`, never write it), `pseudex/**`,
`public/**`, `contracts.py`, generator_a's six modules and `plan_a.py`,
`tools.py`, `mock.py`, `form.py`, metrics/report/harness/judge files.

## Checklist items you own

C-004, C-005, C-012, C-013, C-014, C-037 (K11), C-041, C-046 (schema half),
C-048, C-052, C-055 (K15), C-056–C-060 (case half), C-062–C-065 (case half),
C-093 (your frames), C-102, C-104, C-105 (K11), C-107, C-132–C-137, C-139
(revised chains), C-143–C-146, C-148, C-149 (K05/K06), C-150.

## Definition of done

All four tests PASS; `python3 -m bench.agentpii5.build --check` prints no
problem (with generator_a's families present) and the shares/MDE table;
final message lists files, the printed shares, dropped v4 ids if any,
commands, output, questions.
