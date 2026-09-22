# Brief — component `metrics` (owner code **M**)

You build the PURE measuring half of v5: `observe.py` (records → hop
observations), `metrics.py` (every metric as a function returning one
`Line`), `fixtures.py` (three can-fail fixtures per metric), `report.py` (the
refuse-to-report gate, the axes, the differs histogram, and the v4-vs-v5
side-by-side). Nothing you write imports `pseudex`, runs a model, or reads
the network. You consume `form_match` from the comparator component and
records the judge/harness component writes; you do not build either.

## Read first, in this order

1. `docs/tz-agentpii5.md` §1, §4, §8.3 (the metric table IS your spec).
2. `bench/agentpii5/contracts.py` §1 (hops), §5 (Line, MetricSpec, METRICS,
   AXES, FIXTURE_KINDS, Fixture, GateVerdict, Metric, MetricGate,
   MentionRecord, ToolResultRecord, AnswerSpan, ArmRunV5, HopObservation,
   HOP_STATUSES, RunObservation, Observer, ECHO_TAG_PREFIX, FIELD_SEP,
   hop_owner_of_leaf), §7 (LevelRow, SideBySide), §8 (RUN_FILES).
3. `bench/agentpii5/CHECKLIST.md` — items marked **M**.
4. `public/agentmask-ru/src/agentmask_ru/score.py` (read-only): the shape
   `score()` → `Scores(lines)` and `by_axis`; your `Line` is that `Line`.
5. `e2e/audit_gates.py` header (the discipline of the gate: a check that
   cannot go red is decorative; `--selftest` proves the checker can tell).
6. `bench/agentpii4/compare.py` (`ArmRun`, `ObservedCall`, `PairVerdict`),
   `bench/agentpii4/report.py` (`LEVELS`, `render`, `score_triples`,
   `comparable_triples`, `case_effects`), `bench/agentpii4/stats.py`
   (`clopper_pearson`, `zero_failure_floor`, `mde_paired`),
   `bench/agentpii4/autopsy.py::_load_run`, `bench/agentpii4/records.py`,
   `bench/agentpii4/tools.py::flatten`, `bench/agentpii4/parts.py::parts_of`.

## Rules

- English comments, dense «why not the alternative»; docstrings are the
  design record; no default parameter values; strict typing; no `Any`.
- **No `pseudex` import in any of your files** (`test_*.test_no_pseudex`).
- Every metric is a pure function `Sequence[RunObservation] -> Line`, named
  exactly as `contracts.METRIC_NAMES`, registered in
  `metrics.METRIC_FUNCTIONS: dict[str, Metric]`. Counters, never rates.
- A metric with NO applicable observations returns `Line(name, 0, 0)`; the
  report prints «н/п» for it, never 0%.
- Do not commit. Tests from `prototype/` with the venv:
  `python3 -m bench.agentpii5.test_observe`, `test_metrics`, `test_fixtures`,
  `test_report`, `test_report_gate`.

## Files to create

| file | what |
|---|---|
| `bench/agentpii5/observe.py` | `observe(case, run, ic, cc) -> RunObservation` (satisfies `contracts.Observer`); the alignment rules below |
| `bench/agentpii5/metrics.py` | one function per metric; `METRIC_FUNCTIONS`; `by_axis(observations, axis) -> dict[str, list[RunObservation]]` |
| `bench/agentpii5/fixtures.py` | `FIXTURES: dict[str, tuple[Fixture, Fixture, Fixture]]` for every non-level metric; hand-built `RunObservation`s via small builders |
| `bench/agentpii5/report.py` | `gate(metric, fixtures) -> GateVerdict`, `gate_all()`, `render_line`, `differs_histogram`, `render_side_by_side(v5_run_dir, v4_run_dir) -> list[str]`, `--selftest` |
| `bench/agentpii5/test_observe.py`, `test_metrics.py`, `test_fixtures.py`, `test_report.py`, `test_report_gate.py` | see «Acceptance tests» |

## Step 1 — `observe.py`: from records to `HopObservation`s

Input: `CaseV5`, the I arm's `ArmRunV5`, and the v4 `PairVerdict`s (`ic`,
`cc`, may be None). Output: one `HopObservation` per declared hop (plus extra
ones). Use `bench.agentpii5.form.form_match` for the verdict. `pii_type` =
the item's `type`.

Per owner, EXACTLY:

- **IN/user** — `substitute = run.base.substitutes.get(item_id)`; present →
  `produced = substitute surface (element 0)`, `reference = item.value`,
  status `observed`; absent → status `leaked` (`produced = ""`, `reference =
  item.value`, verdict None).
- **IN/tool** and **IN/document** — find the `ToolResultRecord` with
  `tool_name == hop.tool_name`, `call_ordinal == hop.call_ordinal`, `turn ==
  hop.turn`; none → `absent`. Span = `spans_real[item_id]` (for a forced
  error, `spans_real[ECHO_TAG_PREFIX + item_id]`); a piece in `pieces` that
  COVERS the span entirely → `produced = piece.substitute`, `reference =
  text_real[span]`, `observed`; no piece or partial cover → `leaked`
  (coverage rule: a surviving piece is a leak).
- **IN/memory** — the recall turn `t = hop.turn`; the request index of that
  turn = the smallest `request_index` among `MentionRecord`s with `msg ==
  the user message index of turn t` (or, when anaphora leaves no mention at
  that turn, the request that follows the last mention before `t`); find the
  `MentionRecord` for `item_id` with that `request_index` and `msg` == the
  FIRST mention's `msg`; present → `produced = substitute`, `reference =
  item.value`; absent → `leaked`.
- **OUT/tool_arg, template, summary** — the call: the `hop.call_ordinal`-th
  call named `hop.tool_name` among `run.base.calls` whose `run.call_turns`
  entry equals `hop.turn`; none → `absent` (unless `hop.optional`, in which
  case the hop is NOT emitted). Leaf: `flatten(call.written)[path]` and
  `flatten(call.restored)[path]`; if `path` resolves to a sub-object, join its
  string leaves in the tool's `FieldSpec` order with `FIELD_SEP` (both
  sides). `call.residual` has the path (or any sub-path) → status `residual`
  with `produced = restored leaf`, `reference = written leaf`, verdict None.
  Else `observed`: `produced = restored leaf`, `reference = written leaf`,
  `verdict = form_match(type, produced, reference)`. Owner sanity: the
  hop's owner must equal `contracts.hop_owner_of_leaf(tool, path)`; a
  mismatch is a case bug — raise `ValueError` naming the hop.
- **OUT/answer** — align `run.reply_raw` (substitutes in) with
  `run.base.reply` (restored) using `difflib.SequenceMatcher(None,
  reply_raw, reply, autojunk=False).get_opcodes()`; every `replace` opcode is
  an `AnswerSpan`. Attribute a span to the item whose substitute (any
  `MentionRecord.substitute` for that item, or a piece of it ≥ 4 chars from
  `parts_of`) occurs inside the raw span; `produced = reply[restored span]`,
  `reference = reply_raw[raw span]`, `observed`. An item whose substitute
  occurs in `reply_raw` inside an `equal` opcode → `residual`. A declared
  OUT/answer hop with no span and no residual → `absent` (or not emitted if
  optional).
- **Extra hops** — every call leaf of an `identity` field not covered by a
  declared hop, and every answer span not attributed to a declared hop, is
  emitted with `declared=False`, a synthesised `Hop(hop_index=-1, …)`,
  and the item resolved by substitute match (or `item_id=""` when none).

## Step 2 — `metrics.py`: each metric, exactly

Notation: H = all `HopObservation`s over all observations; declared unless
said otherwise.

| metric | hits / total |
|---|---|
| `leak` | hits: IN hops (any owner, declared or not) with status ≠ `leaked` / total: all IN hops |
| `coverage` | over IN hops with status `observed` or `leaked`: a hop is covered iff status `observed` AND no piece of `reference` (from `parts_of(type, reference)`, excluding roles `city`, generic words, markers) occurs verbatim in `run.base.reply_raw`'s masked view of that message — i.e. in `ToolResultRecord.text_masked` (IN/tool) or in the masked user message (IN/user: the harness stores it as `MentionRecord` context; use `run.base.masked_spans` — an item span not fully inside a masked span is uncovered) / total: same population |
| `typed` | hits: IN/tool hops whose covering piece's `engine_type` equals the item type (`DOB`≡`DATE` allowed) / total: IN/tool hops with a covering piece; `Line(…,0,0)` when none |
| `round_trip` | over IN/user items that are `observed` (altered) AND have a declared OUT/tool_arg hop: hits iff that OUT hop's `produced` equals `item.canonical` (or, for LOC, `parts_of` agree on street+house+flat) / total: those items |
| `round_trip_repaired` | same population; hit also when `produced` equals a REPAIRED form: canonical date notation, nominative of the name (compare `parts_of` roles), digits-only equality for PHONE |
| `end_to_end` | hits: OUT/tool_arg hops with status `observed` and value equal to canonical (as round_trip) / total: ALL declared OUT/tool_arg hops (absent counts as miss) |
| `overmask` | hits: negatives not covered by any span in `run.base.masked_spans[msg]` / total: `case.base.negatives` |
| `consistency` | per item with ≥ 2 `MentionRecord`s in DIFFERENT messages: hit iff all substitutes equal / total: such items |
| `stability` | per item with mentions in ≥ 2 `request_index` values: hit iff the substitute is the same across requests / total: such items |
| `rewrite_ratio` | diagnostic: hits: observations where `difflib.SequenceMatcher(None, C reply, I reply).ratio() < 0.7` / total: observations with `ic` present and both replies non-empty (C reply from the v4 record the harness stores in `ic`-side file; if unavailable, `Line(…,0,0)`) |
| `shared_block` | diagnostic: hits: OUT/answer spans attributed to > 1 item / total: OUT/answer spans |
| `form_hIN` | hits: IN hops `observed` with `verdict.same` / total: IN hops `observed` |
| `form_hOUT` | hits: OUT hops `observed` with `verdict.same` / total: OUT hops `observed` |
| `toolresult_masked` | per `ToolResultRecord` with ≥ 1 `spans_real` entry: hit iff every span is fully covered by a piece / total: such results |
| `answer_real` | per observation whose case declares ≥ 1 OUT/answer hop: hit iff every OUT/answer hop (declared, non-optional) is `observed` with `verdict.same` and no OUT/answer hop is `residual` / total: such observations |
| `chain_value` | per declared OUT hop with `source_hop != -1` pointing at an IN/tool hop of ANOTHER tool: hit iff status `observed` and `produced` equals that IN hop's `reference` (the real value the tool returned; for LOC by `parts_of`), AND the item identity matches / total: such transitions |
| `chain_form` | same population: hit iff `observed` and `verdict.same` |
| `multi_all_out` | per (observation, turn) with ≥ 2 declared non-optional OUT/tool_arg hops: hit iff every one is `observed`, `verdict.same`, and value-correct (as chain_value against the item's canonical); ORDER IS NOT A CONDITION / total: such turns |
| `multi_consistency` | per (observation, turn) with ≥ 2 calls: for every item read in that turn, the set of substitutes written across the turn's calls (from `written` leaves matching mentions) has size 1 / total: such turns |
| `retry_form` | per (observation, tool) with ≥ 2 calls in one turn where a `ForcedError` or a refusal preceded the last: hit iff every attempt's OUT hops are `observed` and `verdict.same` / total: such retries |
| `memory_consistency` | per `MemorySpec`: hit iff all `MentionRecord`s of the item across both turns have one substitute (an anaphoric recall with no mention counts the first turn's mentions only) / total: MemorySpecs |
| `memory_stability` | per item with mentions in ≥ 2 requests within ONE conversation: hit iff unchanged / total: such items; a new conversation is a new observation, never a miss |
| `rag_masked` | per chunk (a `ToolResultRecord` of `kb_search`/`doc_retrieve` split by `spans_real` into the chunks the case's `RagSpec.chunk_ids` name): hit iff every span in the chunk is covered / total: chunks with ≥ 1 span |
| `rag_identity_kept` | per `RagSpec.foreign_identities` entry: hit iff no real value of that identity appears in any OUT hop `produced` of the CUSTOMER's items and no substitute shown for the customer appears where the foreign value stood in `text_masked` / total: foreign identities |
| `doc_masked` | per `DocumentSpec`: hit iff every `spans_real` span of the document's `ToolResultRecord` is covered / total: documents |
| `doc_extracted` | per `DocumentSpec.extracted_item_ids` item: hit iff its declared OUT hop into `extract_to_tool` is `observed` and value-correct (canonical) / total: extracted items |
| `residual` | per OUT hop (declared or not) and per answer: hit iff status ≠ `residual` / total: all OUT hops + all answers |

`by_axis(observations, axis)` for every `contracts.AXES` entry: `register`,
`family` (= `case.base.kind`), `behaviour`, `vertical` (= `TOOL_VERTICAL` of
the hop's tool; hop-level axes split the HOPS, not the observations —
build a filtered `RunObservation` copy holding only the hops of the bucket,
like public `by_axis` does for `tier`/`cue`), `hop_owner`, `pii_type`,
`return_form`, `name_tier` (from `case.base.provenance.selection`: `rare` vs
`authored`), `cue` (item's message text has a cue word within 60 chars —
reuse v4's notion: `bench.agentpii3.schema` exposes none you may import
cheaply; implement a 12-word cue list `тел|телефон|адрес|улица|дом|кв|снилс|
инн|паспорт|карта|почта|родил`).

## Step 3 — `fixtures.py`

For EVERY non-level name in `contracts.METRIC_NAMES` (i.e. all but
`action/tools/keys/state/values/verbatim`) build three `Fixture`s named
`fx_<metric>_zero`, `fx_<metric>_one`, `fx_<metric>_adversarial`, each a
hand-assembled `RunObservation` tuple (tiny `CaseV5` + `ArmRunV5` + hops)
following the scenarios in CHECKLIST C-153…C-167 and C-069…C-079 to the
letter. The adversarial fixture's docstring says what a WRONG metric would
print. Never build a fixture by running an agent or the engine. Provide
small builders (`_case(...)`, `_run(...)`, `_hop(...)`) so a fixture is ≤ 25
lines.

## Step 4 — `report.py`

- `gate(metric, fixtures) -> GateVerdict`: all three kinds present; each
  fixture's `metric(input)` equals `(expected_hits, expected_total)`; zero
  fixture rate 0.0 and one fixture rate 1.0 (`FIXTURE_MIN_SEPARATION`). Any
  failure → `printable=False`, `why` names the fixture and the fraction
  seen. Never raises on a wrong metric.
- `gate_all() -> dict[str, GateVerdict]` over `METRIC_FUNCTIONS` ×
  `FIXTURES`; a metric missing from `FIXTURES` is refused («no fixtures»).
- `render_line(line) -> str`: `«name x/n (p%) [low, high]»` and, when
  `certified` is set, `«сертифицирует ≥ f%»` instead of 100%; `«н/п»` for
  `total == 0`.
- `differs_histogram(observations, type) -> dict[str, int]`: per feature,
  the count of `observed` hops whose `verdict.differs` contains it.
- `render_side_by_side(v5_run_dir, v4_run_dir) -> list[str]`:
  1. Load both runs' v4 blocks with `bench.agentpii4.autopsy._load_run` +
     `bench.agentpii4.report.score_triples` + `bench.agentpii4.report.render`
     — the v4 block text is v4's own, byte for byte; parse its level lines
     into `LevelRow`s for the summary table.
  2. Load `<run>.hops.jsonl` + `<run>.arms.v5.jsonl` + `corpus.v5.json` of
     the v5 run (deserialisers come from the judge component's
     `records.py`; import `bench.agentpii5.records`) and rebuild
     `RunObservation`s.
  3. `gate_all()`; refused non-diagnostic metrics → `incomplete=True`;
     header line 1 = run ids + models + `INCOMPLETE_REPORT_MARK` when
     incomplete; read `CalibrationStamp` from the v5 run's judge file
     header and mark incomplete when `calibrated` is False.
  4. Sections, in this order: 0 header · 1 the v4 block (both runs side by
     side: each `LevelRow` of v5 beside v4) · 2 v5 Lines (every printable
     metric, diagnostics under «диагностика») · 3 form: `form_hIN`/`form_hOUT`
     by `pii_type`, `hop_owner`, `vertical`, `behaviour` + the differs
     histogram per type · 4 by-behaviour MDE line (`stats.mde_paired(n,
     0.10, 2.1)` per behaviour with its n) · 5 judge label counts · 6 refused
     metrics with reasons · 7 examples (≤ dump) of `residual`, `leaked`, and
     `differs` hops.
  5. Write `<run>.report.txt` and `<run>.gate.json`.
- `--selftest`: replace every metric with `lambda obs: Line(name, 1, 1)` and
  assert every one is refused; then with the real functions assert every one
  is printable. Exit 1 otherwise. (The `audit_gates --selftest` shape.)

## Acceptance tests you must ship

- `test_observe.py`: `test_no_pseudex`; `test_in_orientation` (an IN hop's
  `produced` is the substitute, `reference` the source); `test_out_orientation`;
  `test_template_owner` (a `send_template.variables.name` leaf yields owner
  `template`; a mismatch with the declared owner raises); `test_answer_alignment`
  (raw «позвоню Кудрявцевой Диане» / restored «позвоню Кузнецовой Дарье»
  yields one OUT/answer hop with the two spans); `test_residual_out`;
  `test_leaked_in_partial_cover`; `test_optional_absent_not_emitted`;
  `test_extra_hop_undeclared`.
- `test_metrics.py`: `test_no_pseudex`; `test_every_metric_registered`
  (`set(METRIC_FUNCTIONS) == set(METRIC_NAMES) - set(V4_LEVEL_NAMES)`);
  `test_form_lines_ignore_controls` (C-017); `test_chain_transitions`;
  `test_rag_identity_kept`; `test_public_denominators` (C-168);
  `test_empty_is_na` (`Line(…,0,0)` on no observations).
- `test_fixtures.py`: `test_three_kinds_each`; `test_fixture_expectations`
  (every fixture yields its expected fraction under the real metric — this
  is the gate run as a test); `test_no_pseudex`.
- `test_report.py`: `test_no_pseudex`; `test_line_rendering`;
  `test_v4_block_byte_equal` (render the same fixture run dir through v4's
  `report.render` and through `render_side_by_side`; the v4 block lines are
  identical); `test_every_axis_prints`; `test_differs_histogram`;
  `test_leak_and_coverage_both_present`; `test_no_effect_claims_outside_v4_block`
  («эквивалентно» only inside the v4 block); `test_side_by_side_sections`.
- `test_report_gate.py`: `test_broken_metric_is_refused` (a constant metric
  registered under a real name is absent from `v5_lines`, present in
  `v5_refused`, header carries `INCOMPLETE_REPORT_MARK`); `test_selftest_passes`
  (invokes the `--selftest` path).

For `test_report` you need a fixture run directory: build one under
`bench/agentpii5/testdata/run-fixture/` by WRITING records with
`bench.agentpii5.records` from hand-built objects (v4 `arm_record` for the
three arms, your `ArmRunV5`/hops for I). The judge component owns
`records.py`; until it lands, write the JSON by hand following the v4
record shape and `contracts.RUN_FILES`, and swap to `records` when it exists.

## What you must NOT touch

`bench/agentpii4/**`, `pseudex/**`, `public/**`, `contracts.py`, `form.py`,
`tools.py`, `mock.py`, `schema.py`, `scenarios5/`, `harness.py`, `judge.py`,
`calibration.py`, `records.py`.

## Checklist items you own

C-002, C-007, C-008, C-010, C-011, C-015–C-017, C-033 (observer half), C-042
(metric half), C-043–C-045 (metric half), C-047 (v4-by-behaviour), C-059
(metric half), C-061, C-066 (render half), C-067–C-095, C-101, C-103, C-108,
C-151, C-152–C-169, C-181 (histogram), C-184 (incomplete mark), C-190.

## Definition of done

All five tests PASS; `python3 -m bench.agentpii5.report --selftest` exits 0;
no `pseudex` import; final message lists files, commands, output, questions.
