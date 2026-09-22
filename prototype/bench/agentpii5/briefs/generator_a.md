# Brief — component `generator_a` (owner code **GA**)

> **Read `bench/agentpii5/RULINGS.md` before this brief** — the architect's rulings on the questions the first builders raised; where a ruling and this brief disagree, the ruling wins.

You write six NEW case families of the v5 corpus, one per behaviour of
`contracts.GENERATOR_A_BEHAVIOURS`: `retry_same_tool`,
`same_tool_other_target`, `sequential_chain`, `parallel`, `fanout_pick`,
`branching`. Every case is BUILT (never searched), declares its hops, its
return expectations and its behaviour spec, and validates under
`schema.validate_v5`. You do not write the schema, the builder, the
revision of the 834, or the build script — generator_b does; you code
against the contract and import their concrete builder.

## Read first, in this order

1. `docs/tz-agentpii5.md` §1, §3.1, §3.2, §8.2 (rows for your six families).
2. `bench/agentpii5/contracts.py` §1 (Hop, MINIMAL_LOOP, TEMPLATE_FIELDS,
   SUMMARY_FIELDS, hop_owner_of_leaf), §2 (BEHAVIOURS, BEHAVIOUR_FLOORS,
   ReturnExpectation, ForcedError, PickSpec, BranchSpec, CaseV5,
   V5_CASE_RULES R01–R21, CaseKit), §3 (RETURN_FORMS, TOOL_VERTICAL,
   NEW_TOOL_NAMES, NEW_TOOL_RESULT_TYPES).
3. `bench/agentpii5/CHECKLIST.md` — items marked **GA**.
4. v4's generator, in this order: `bench/agentpii4/scenarios/common.py`
   (`Ctx`, `ctx_for`, `registers_for`, `MessageDraft`, `CaseBuilder`,
   `draw`, `name/phone/address/dob/snils/inn/card/passport/email`,
   `contact_seed`, `address_seed_fields`), `bench/agentpii4/pools.py`
   (`Rendered`, `Person`, `Address`, the render functions, `CORPUS_CITIES`),
   `bench/agentpii4/writer.py` (why nothing searches a finished string),
   `bench/agentpii4/validate.py` (`prove_no_search` watches your frames),
   three v4 scenario modules to copy the shape from:
   `scenarios/result_feed.py` (the 4-hop base), `scenarios/tool_chain.py`
   (chain), `scenarios/lookup_list.py` (a list comes back).
5. `bench/agentpii5/briefs/generator_b.md` §«The builder» — the concrete
   `CaseBuilderV5` API you import from
   `bench.agentpii5.scenarios5.common` (it wraps v4's `CaseBuilder` and
   implements `contracts.CaseKit`). Until it exists, write your modules
   against `contracts.CaseKit` and the v4 `CaseBuilder` methods
   (`user`, `seed`) it re-exposes; do NOT write your own builder.

## Rules

- English comments; docstrings are the design record; no default parameter
  values; strict typing; no `Any`.
- **No `pseudex` import**; **no `str.find`/`index`/`re.search` on a finished
  message** — offsets come from `MessageDraft`/`Writer` (`prove_no_search`
  runs over `scenarios5/` in `build.py --check` and refuses the corpus).
- Ground truth = the canonical of WHAT WAS WRITTEN, from the parts you built
  (`Rendered.parts`), never recovered from the surface.
- Every family module exposes `build(seed: int, count: int) -> list[CaseV5]`
  and a module constant `TOOLS: tuple[str, ...]` (offered tools), like v4.
  Case ids `f"{behaviour}-{index:03d}"`.
- Register mix per family: use `common.registers_for` from
  `scenarios5/common.py` (v5 shares: voice 45 / chat 25 / sloppy 15 /
  clean 10).
- Do not commit. Tests: `python3 -m bench.agentpii5.test_generator_a`.

## Files to create

| file | what |
|---|---|
| `bench/agentpii5/scenarios5/retry_same_tool.py` | 120 cases |
| `bench/agentpii5/scenarios5/same_tool_other_target.py` | 50 cases |
| `bench/agentpii5/scenarios5/sequential_chain.py` | 40 cases (new verticals: bank, support, files, government) |
| `bench/agentpii5/scenarios5/parallel.py` | 100 cases |
| `bench/agentpii5/scenarios5/fanout_pick.py` | 40 cases |
| `bench/agentpii5/scenarios5/branching.py` | 50 cases |
| `bench/agentpii5/scenarios5/plan_a.py` | `PLAN_A: tuple[tuple[object, int], ...]` = the six (module, count) pairs above, imported by generator_b's `build.py` |
| `bench/agentpii5/test_generator_a.py` | see «Acceptance tests» |

Counts are the §8.2 floors minus what the revised v4 corpus already
supplies (see `contracts.V4_KIND_TO_BEHAVIOUR`): the revised corpus gives
`sequential_chain` 319, `fanout_pick` 117, `branching` 35, so your 40/40/50
top them up; `retry`, `other_target`, `parallel` come only from you.

Type quotas across your 400 cases (K05: INN ≥ 60 and PLATE ≥ 60 cases
corpus-wide; generator_b supplies ≥ 20 each): **≥ 40 cases carrying an INN
item and ≥ 40 carrying a PLATE item**, spread over ≥ 3 of your families.
INN rendering: `scenarios5/common.py` exports `inn(ctx, digits)` (v4's, with
checksum) and `plate(ctx, text)` (new, generator_b writes it — Cyrillic
plate «А123ВС 77», spoken form «а сто двадцать три вэ эс семьдесят семь»
for `voice_raw`).

## Hop declaration — the exact recipe (every family)

After the v4 moves (`builder.user(...)`, `builder.seed(...)` /
`contact_seed`), declare:

1. **IN/user** for every message-locus item: `Hop("IN", "user", item_id,
   idx, turn=msg index, "", -1, "", -1, "", False)`.
2. **OUT/tool_arg** for every identity leaf of every call you expect, with
   `path` = the `FieldSpec.path` (arrays as `[]`), `tool_name`,
   `call_ordinal`, `turn`, `source_hop` = the IN hop index the value comes
   from (user or tool), `optional` = `not FieldSpec.required`; owner via
   `contracts.hop_owner_of_leaf(tool, path)` (so a `notify_sms.text` leaf is
   a `template` hop).
3. **IN/tool** for every seed item a call returns: `Hop("IN", "tool",
   item_id, idx, turn, tool_name, call_ordinal, "", -1, path=<result path
   from ToolSpec.result_pii / ReturnForm.pii_paths>, False)` + one
   `ReturnExpectation(tool, ordinal, form, result_item_ids)` per call.
4. **OUT/answer** for every item of the primary identity the final reply
   should carry: `optional=True` unless the user asked for it explicitly
   (then `False` and also put the canonical into `must_contain`).
5. Hop indexes 0..n-1 in the order the crossings happen.

`builder.build(behaviour)` validates R01–R21 and raises on any problem —
fix the case, never the validator.

## Family by family

### `retry_same_tool` (120) — §3.1 row 2
Verticals: bank (`bank_client_find` by INN, `payment_create`), government
(`vehicle_check`, `snils_verify`), delivery (`courier_book`), clinic
(`clinic_book`). The user gives one identifier (INN / plate / SNILS / phone)
and asks for an action. `ForcedError(tool, call_ordinal=0, code, echo_item_id,
"…{value}…")` makes the mock answer `error_with_value` on the first call —
message templates mirror the real API's own wording (e.g. ЮKassa
`invalid_request: поле phone «{value}» должно быть в формате E.164`; ГИБДД
«номер {value} не найден в формате…»). Hops: IN/user → OUT/tool_arg
(ordinal 0) → IN/tool (ordinal 0, the echo, `path="error.message"`) →
OUT/tool_arg (ordinal 1, `source_hop` = the IN/user hop, not the echo) →
IN/tool (ordinal 1, the record) → OUT/answer. R10.

### `same_tool_other_target` (50) — §3.1 row 3
Two identities in one dialogue («найдите Иванова и Петрову»): two calls of
the SAME tool (`crm_find_contact` / `bank_client_find` / `snils_verify`),
ordinals 0 and 1 in ONE turn (parallel_group "" — they may be sequential),
two seeds, `must_not_contain` = each person's values in the OTHER's answer
sentence is not checkable, so instead declare OUT/answer hops for both
identities and set `expects.primary_identity` to the first. R11.

### `sequential_chain` (40) — §3.1 row 4
Three transitions minimum, in verticals v4 lacks: bank (`bank_client_find` →
`account_statement` → `payment_refund` → answer), support (`ticket_find` →
`ticket_history` → `escalate_to_human` with a SUMMARY leaf → answer), files
(`file_read` → `crm_upsert_contact` → `notify_sms`), government
(`vehicle_check` → `ticket_create`). Each OUT hop of tool B carries
`source_hop` → the IN/tool hop of A (R12). The answer covers every value
returned (OUT/answer hops, `optional=False` for the one the user asked).

### `parallel` (100) — §3.1 row 5
N ∈ {2, 3, 4} independent calls the agent should issue in ONE assistant
turn: «отправьте смс Иванову, Петрову и Сидоровой» (`notify_sms` ×3),
«проверьте эти три номера в ГИБДД» (`vehicle_check` ×3), «забронируйте слоты
для двоих» (`calendar_free` ×2). All OUT hops of the turn share
`parallel_group="g1"` (R09). The system prompt (a v5 role prompt in
`scenarios5/common.py`) says calls that do not depend on each other are to
be issued together. IN/tool for every result, OUT/answer integrating all.

### `fanout_pick` (40) — §3.1 row 6
`list_tool` returns ≥ 2 candidates of different identities with the same
TYPE of value as the customer's cue (`bank_client_find` by phone returning
two clients; `kb_search` returning three people; `crm_find_contact` by
surname returning namesakes). `PickSpec(list_tool, candidate_identities,
target_identity, act_tool)`; the user's message carries the discriminating
value (a DOB, a street) so the pick is BY VALUE. Seeds for every candidate,
`must_not_contain` = the non-target candidates' values. R13.

### `branching` (50) — §3.1 row 7
`BranchSpec(probe_tool, seed_present, then_tool, else_tool)`: half the
cases seed the record (found → `then_tool`, e.g. `crm_upsert_contact`), half
do not (`empty` result → `else_tool`, e.g. `crm_upsert_contact` with a new
id, or `ticket_create`). The prompt states the rule («если клиент найден —
обновите карточку, иначе заведите новую»). Hops: IN/user → OUT/tool_arg
(probe) → IN/tool (found: the record; absent: no IN hop — an `empty` result
carries nothing) → OUT/tool_arg (then/else, `source_hop` accordingly) →
OUT/answer. R14.

## Acceptance tests you must ship — `bench/agentpii5/test_generator_a.py`

- `test_no_pseudex`.
- `test_build_each_family` — every module builds its count with seed 4;
  every case passes `schema.validate_v5` (empty list) — import from
  `bench.agentpii5.schema`.
- `test_behaviour_specs` — retry cases have exactly one `ForcedError` and an
  ordinal-1 hop; parallel cases have a `parallel_group` of ≥ 2 OUT hops in
  one turn; fanout cases have `pick` with ≥ 2 candidates; branching cases
  split ~half/half on `seed_present`; chain cases have ≥ 3 transitions with
  `source_hop` across tools; other_target cases have 2 identities on one tool.
- `test_type_quotas` — ≥ 40 INN cases and ≥ 40 PLATE cases across your
  families; each family touches ≥ 2 verticals; the six families together
  reach every one of the 12 new tools in ≥ `MIN_TYPE_DENOMINATOR` cases.
- `test_registers` — the register mix of each family is within
  `SHARE_TOLERANCE` of `REGISTER_SHARES` (voice = voice_raw + voice_itn).
- `test_no_search` — `bench.agentpii4.validate.prove_no_search` over your
  `build` calls (adapt the watched dirs to `scenarios5/`) reports nothing.
- `test_hops_orientation` — for a sample case per family, every OUT hop with
  `source_hop != -1` points at an earlier IN hop; every IN/tool hop has a
  `ReturnExpectation` naming it.

## What you must NOT touch

`bench/agentpii4/**`, `pseudex/**`, `public/**`, `contracts.py`, `schema.py`,
`scenarios5/common.py`, `scenarios5/plan_b.py`, `revise.py`, `build.py`,
`tools.py`, `mock.py`, `form.py`, metrics/report/harness/judge files. If the
builder lacks something you need (a new renderer, a role prompt), ask
generator_b in your final message; do not add it to `common.py` yourself.

## Checklist items you own

C-015 (declaration half), C-016 (declaration half), C-042 (case half), C-043,
C-044, C-045, C-046, C-047 (case half), C-093 (your frames under
`prove_no_search`), C-138, C-139 (new chains), C-140, C-141, C-142, C-147,
C-149 (your INN/PLATE quota).

## Definition of done

`test_generator_a` PASS; `python3 -m bench.agentpii5.build --check` (once
generator_b lands it) reports no problem from your families; final message
lists files, counts per family, INN/PLATE counts, commands, output, questions.
