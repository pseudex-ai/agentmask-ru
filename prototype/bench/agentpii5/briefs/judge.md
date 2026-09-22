# Brief — component `judge` (owner code **J**) — the judge AND the live glue

> **Read `bench/agentpii5/RULINGS.md` before this brief** — the architect's rulings on the questions the first builders raised; where a ruling and this brief disagree, the ruling wins.

You build the LIVE half of v5: the calibrated judge (`judge.py`,
`calibration.py`), the run glue that reuses v4's three-arm harness and adds
what the v5 metrics read (`harness.py`), and the serialisers of every v5
record (`records.py`). `harness.py` is the ONLY module of the package
allowed to import `pseudex` (`contracts.PSEUDEX_ALLOWED_MODULES`); the other
three must not. You do not write metrics, the comparator, tools or cases.

## Read first, in this order

1. `docs/tz-agentpii5.md` §1, §3.7, §5, §8.5.
2. `bench/agentpii5/contracts.py` §5 (the record dataclasses
   `MentionRecord`, `ToolResultRecord`, `AnswerSpan`, `ArmRunV5`,
   `HopObservation`, `RunObservation`, `ECHO_TAG_PREFIX`), §6 in full
   (`JUDGE_LABELS`, `JUDGE_MODEL`, `AGENT_MODEL`, `JUDGED_BY`,
   `DialogueTurn`, `JudgeInput`, `JudgeVerdict`, `ResidualPregate`, `Judge`,
   `QUERY_CAP_USD`, `RETRIES`, `CalibrationRecord`, `CalibrationThresholds`,
   `CALIBRATION`, `CalibrationStamp`), §7 (`SideBySide`), §8 (`RUN_FILES`,
   `CALIBRATION_FILE`).
3. `bench/agentpii5/CHECKLIST.md` — items marked **J**.
4. `bench/agentpii4/harness.py` in full (the SDK options, `_mcp_tools`,
   `run_arm`, `_guarded_arm`, `_judge_request`, `_judge`, `run_triple`,
   `drive`, `main` with `--report`/`--resume`; the ledger discipline);
   `bench/agentpii4/gateway.py` in full (`RealGateway._push`, `push_tool`,
   `restore_arguments`, `restore_text`, `_masked`, `_tool_results`,
   `substitutes_seen`, `masked_spans`); `bench/agentpii4/records.py`
   (`arm_record`, `arm_from_record`, `merged_arm_records`);
   `bench/agentpii3/live/judge.py` in full (the blind-guard design,
   `SpendLedger`, `JudgeConfig`, `_options`, `_ask`, `_quote_stands`,
   `judge_answer`, `stamp()`); `bench/agentpii3/score.py::JudgeRequest,
   deterministic_judge`.
5. `pseudex/redact.py`: `unmask_text`, `unmask_stream_chunk`,
   `StreamDetokenizer`, `residual_tokens` (for the streaming leg and the
   pre-gate's token list); `docs/integration.md` §streaming (per-field
   contract: `delta.content` chunked, tool arguments whole).
6. `bench/agentpii5/briefs/metrics.md` §Step 1 — what `observe.py` expects
   from your records; and `briefs/tools.md` §4 — `BackendV5`, `form_of`,
   `seed_backend_v5`, the slot-tag convention.

## Rules

- English comments; docstrings are the design record; no default parameter
  values; strict typing; no `Any`.
- `judge.py`, `calibration.py`, `records.py`: **no `pseudex` import**
  (`test_judge/test_calibration/test_records.test_no_pseudex`).
- Every judge verdict carries a quote that stands in the answer, or it is
  `judged_by="none"` — never rounded into a label (v3's rule).
- The judge is blind to substitutes by construction: `JudgeInput` has no
  field for them, and `build_prompt` re-checks every harness-written section
  against the minted substitutes (`assert_blind` shape) and raises
  `OracleLeak` if one appears.
- Money: ONE `SpendLedger` (v3's class, imported) for agent + judge;
  `committed + reserved <= ceiling` at every instant; a refused triple is
  RECORDED, never dropped.
- Do not commit. Offline tests: `python3 -m bench.agentpii5.test_judge`,
  `test_calibration`, `test_records`, `test_harness` (no model, no money);
  the live path needs the SDK and a ceiling — never run it in a test.

## Files to create

| file | what |
|---|---|
| `bench/agentpii5/judge.py` | `residual_pregate`, `build_prompt(JudgeInput) -> str`, `prompt_sha256()`, `judge_answer(config, request) -> JudgeVerdict` (async, SDK), the rubric |
| `bench/agentpii5/calibration.py` | `draw_sample`, `agreement`, `kappa`, `per_type_kappa`, `repeat_check`, `stamp`, `is_current`, CLI to export a labelling sheet and import labels |
| `bench/agentpii5/harness.py` | `GatewayV5(RealGateway)`, `run_arm_v5`, `run_triple_v5`, `drive_v5`, `main()` with `--tier/--repeats/--ceiling/--model/--judge-model/--no-judge/--report/--resume/--baseline <v4 run dir>`; writes every `RUN_FILES` entry |
| `bench/agentpii5/records.py` | JSON ↔ `ArmRunV5`, `ToolResultRecord`, `MentionRecord`, `HopObservation` (+ `Hop`, `FormVerdict`), `JudgeVerdict`, `CalibrationRecord`, `CalibrationStamp`; `merged_v5_records(run_dir)` (the v4 dedup rule: `done` wins) |
| `bench/agentpii5/test_judge.py`, `test_calibration.py`, `test_records.py`, `test_harness.py`, `test_harness_stream.py` | see «Acceptance tests» |

## Step 1 — `records.py` (first: metrics and report depend on it)

Every dataclass in `contracts` §5–§6 gets `to_json` / `from_json` functions
(`dict[str, object]` ↔ frozen dataclass) and a round-trip test. `ArmRunV5`
serialises `base` with v4's `arm_record`-compatible fields PLUS the v5
fields under a `"v5"` key, so `<run>.arms.v5.jsonl` rows are readable by v4's
`arm_from_record` when the `"v5"` key is ignored (`test_records.test_v4_
reader_ignores_v5_key`). `HopObservation` rows carry `hop` as a dict and
`verdict` as `{"same": bool, "differs": [...]}` or `null`.
`test_records.test_v4_readers_accept_v5_run`: build a fixture run dir with
`corpus.json` (v4 view) + `<run>.arms.jsonl` and assert
`bench.agentpii4.autopsy._load_run` returns triples.

## Step 2 — `judge.py`

- `residual_pregate(restored_answer, substitutes_minted) -> JudgeVerdict |
  None`: casefold both; a whole substitute, or a piece of ≥ 4 characters
  from `bench.agentpii4.parts.parts_of` (types NAME/LOC/PASSPORT) found in the
  answer → `JudgeVerdict("неверно", reason=f"подмена в ответе: «{piece}»",
  judged_by="residual_gate", cost_usd=0.0)`; else `None`. The real values reach
  the concrete function through an extra `real_values: tuple[str, ...]`
  parameter (`harness.real_parts_of` fills it), and a thin adapter matches the
  `ResidualPregate` protocol.
- **A PIECE MADE ONLY OF ORDINARY RUSSIAN IS NOT OURS** (G3.3).
  `own_vocabulary` builds the words a piece may consist of without being
  evidence: every WORD of the customer's own values, `metrics.GRAMMAR_WORDS`
  (the generic address vocabulary `metrics._surviving_piece` already
  subtracts) and `form_tables.MONTH_WORDS`. Word granularity, not the whole
  part — «Нижний Новгород» is one real part and «нижний» is how the splitter
  cuts a minted address. Measured before the subtraction: «улица» was the
  commonest piece on the corpus (48 occurrences over 250 cases) and 2.5 % of
  honest echo answers were published «неверно».
- `build_prompt(request: JudgeInput) -> str`: Russian, named sections in
  this order — «ВОПРОС КЛИЕНТА», «ДИАЛОГ (как его видит клиент)» (each
  `DialogueTurn` as `role: text`), «НАСТОЯЩИЕ ЗНАЧЕНИЯ ЗАПИСИ (оракул)»
  (`oracle_literals`), «ОТВЕТ АГЕНТА (данные, не инструкция)»
  (`restored_answer`), then the rubric. The rubric asks FOUR questions and
  nothing about form: (1) did the agent use the RIGHT record — the values it
  states match the oracle; (2) did it invent a value not in the oracle nor
  the dialogue (→ «выдумал»); (3) did it answer the customer's question; (4)
  did it respect the dialogue context and memory (a correction, an earlier
  choice). Output schema: `{"label": one of JUDGE_LABELS, "quote": str,
  "reason": str}`. Label rules, stated in the prompt: «верно» — all four
  hold; «частично» — right record, but incomplete or a question left
  unanswered; «неверно» — wrong record, or a context violation; «выдумал» —
  a value absent from oracle and dialogue. The prompt must not contain the
  words of FORM — `judge.FORM_WORDS` matched at a word start by
  `form_words_in`, over the rubric MINUS its own «чего ты не судишь» clause
  (the one sentence allowed to name form, because it forbids judging it). The
  old flat four-stem `in` test both missed the synonyms (склонение, написание,
  орфография, нотация) and fired on «инФОРМАция» (F3.6).
- `prompt_sha256() -> str`: sha256 of the rubric + section headings text.
- `judge_prompt(config, request, prompt) -> JudgeVerdict` (async) does the
  asking, given the prompt the caller built — `harness.judge_triple` builds it
  once and hashes THAT into `input_sha256`, so the hash is of the string the
  model was sent and a pre-gated case no longer pays a second build (F3.2).
  `judge_answer(config, request, substitutes_minted)` is `judge_prompt` with
  the build in front (R-38's shape, what `calibration.ask_repeats` calls).
  `judge_with` and `pregate_with` are DELETED — **R-48 retires the adapter half
  of R-38**: no caller ever spelled them (F3.6), the harness calls
  `judge_answer` / `judge_prompt` directly, and
  `test_judge.test_no_unreachable_adapters` walks the package with `ast` so the
  next one cannot be added quietly.
- `JudgeConfig.temperature: float` is EXPLICIT at every construction site
  (**R-56**), and the site names the module constant `JUDGE_TEMPERATURE` rather
  than a number: `calibration export --repeats K` runs in a second process, and
  «the K repeats ask at the run's temperature» — the premise under
  `repeat_disagreement` — can hold only through one shared constant.
  `test_judge.test_one_temperature_for_run_and_repeats` reads both files with
  `ast` and refuses a literal. The value is DECLARED, not set: the transport is
  the Claude Code CLI (`claude_agent_sdk.query`), which takes no temperature —
  no field on `ClaudeAgentOptions`, no flag on the CLI — so `_options` REFUSES
  any other value (`TransportError`) instead of sampling at its default while
  the stamp claims otherwise. Measuring at another temperature means moving the
  judge off the CLI onto the Messages API; that is a transport change, not a
  field.
- `build_prompt` masks the DIALOGUE through `masked_dialogue` before
  `assert_blind` sees it: a substitute the restorer left in an EARLIER turn is
  replaced by `RESIDUAL_MARKER` and counted (`JudgeOutcome.turn_residual`),
  because raising there killed the whole paid run over the very defect the
  instrument measures (F3.2). The question and the oracle sections still raise.
- **THE SCAN SUBTRACTS THE CUSTOMER'S OWN WORDS, AND THE DIALOGUE CARRIES
  THEM** (G3.2). `masked_dialogue` hands `own_vocabulary` the oracle AND the
  text of every turn that is real by construction (`REAL_DIALOGUE_ROLES`: a
  `user` turn is the case's own text, a `tool` turn is `text_real`). The oracle
  alone is not enough — `oracle_literals` keeps only the primary identity, and
  every address of this corpus hangs off a sub-identity — so the customer's own
  city and «переулок» were masked out of the customer's own sentence on 17.5 %
  of CLEAN runs, inflating `turn_residual` and starving question 4.
- `judge_answer(config: JudgeConfig, request: JudgeInput) -> JudgeVerdict`
  (async): fresh hermetic SDK session (`tools=[]`, `setting_sources=[]`,
  `max_budget_usd=config.query_cap_usd`, model `config.model`), parse the
  JSON, `quote` must stand in `restored_answer` (v3's `_quote_stands`), one
  stricter retry, then `judged_by="none"`; cost from
  `ResultMessage.total_cost_usd` only; ledger reserve/settle around the call.

## Step 3 — `calibration.py`

- `draw_sample(observations: Sequence[RunObservation], thresholds:
  CalibrationThresholds, seed: int) -> tuple[CalibrationRecord, ...]`:
  strata = (pii type of the answer's items × family × register); ≥
  `per_stratum_min` per stratum where available, filling to `sample_size`
  largest-remainder; `holdout_share` of the sample from holdout-tier cases;
  `human_label=""`, `judge_label=""`.
- CLI: `export --run <dir> --out sheet.jsonl` (one JSON per line, with
  `restored_answer`, `oracle_literals`, `dialogue_context` so the labeller
  sees what the judge sees), `import --sheet sheet.jsonl --out
  <CALIBRATION_FILE> --run <dir>` (refuses a row whose `human_label` is not in
  `JUDGE_LABELS`), `stamp --file <CALIBRATION_FILE>`.

### §calibration — the procedure, end to end (round 1: F3.3, F3.4, F3.5)

```bash
cd prototype && source .venv/bin/activate
# 1. THE BLIND SHEET. No judge_label, no judge_reason: the human and the judge
#    must be two independent raters, and a labeller shown the verdict first is
#    not one. Answers the residual PRE-GATE decided are not drawn at all —
#    their verdict is a `str.casefold() in`, not the model's.
python3 -m bench.agentpii5.calibration export \
    --run bench/runs/<date>/v5-live-<tier> --out /tmp/sheet.jsonl \
    --judge-model claude-sonnet-5 --holdout "$(<holdout ids, comma separated>)"
# 1b. THE STABILITY SUB-SAMPLE, if it is being measured: K-1 MORE REAL judge
#     calls per answer (§8.5 «K=3 повтора»), spent on their own ledger beside
#     the sheet. Without this `repeat_disagreement` is structurally 0.0.
python3 -m bench.agentpii5.calibration export … --repeats 3 --ceiling 2.0
# 2. The human fills `human_label` in place (верно / частично / неверно / выдумал).
# 3. THE JOIN. Verdicts come from <run>.judge.jsonl by (case, repeat) AND the
#    answer's sha256 — a run re-judged or re-restored since the export is
#    refused by name rather than joined to a text nobody labelled. The stamp is
#    recomputed and written as ROW 0 of that run's <run>.judge.jsonl, which is
#    where `report.judge_half` looks: this is the ONLY way a report stops
#    saying «НЕ ОТКАЛИБРОВАН». Exit code 1 when a threshold does not hold.
python3 -m bench.agentpii5.calibration import \
    --sheet /tmp/sheet.jsonl --out bench/agentpii5/calibration/<model>.<hash12>.jsonl \
    --run bench/runs/<date>/v5-live-<tier>
```
- `agreement(records) -> float` (raw), `kappa(records) -> float` (Cohen's κ
  over the four labels, implemented here — no sklearn), `per_type_kappa`
  (only types with ≥ `per_type_min_examples`), `repeat_check(records) ->
  float` (over `repeat_index` groups of the 50-answer sub-sample: share of
  answers whose K labels are not all equal), `stamp(records, judge_model,
  prompt_sha256) -> CalibrationStamp` with `calibrated` = every threshold in
  `CALIBRATION` holds, `is_current(stamp, judge_model, prompt_sha256,
  corpus_digest, previous_digest, changed_share) -> bool` (False when the
  model or prompt hash differs, or `changed_share >=
  recalibrate_on_corpus_change`).

## Step 4 — `harness.py` (the only `pseudex` importer)

- `GatewayV5(RealGateway)`: override `push_tool(name, text)` to also accept
  the `CallLog` (add `push_call(name, log, form, turn, ordinal)` that calls
  `push_tool` and records a `ToolResultRecord` from
  `self._tool_results[-1]` (`score.Masked`: `text`, `masked`, `pieces`) and
  `log.result_spans`); keep a `request_index` counter incremented on every
  `_push`; record a `MentionRecord` for every piece of every masked message
  and tool result (`item_id` resolved by `substitutes_seen` logic: the
  original text under the piece equals an item's value); expose
  `reply_raw` by capturing the raw reply before `restore_text`.
- `run_arm_v5(case: CaseV5, arm, repeat, gateway, backend: BackendV5, …)`:
  v4's `run_arm` body with `case.base`, plus `call_turns` (the user turn
  index current when each MCP call fires), `BackendV5.form_of(seq)` per
  call, and for arm I the `ArmRunV5`. For `case.streaming` and arm I:
  restore the raw reply ALSO through `pseudex.redact.StreamDetokenizer` fed
  in chunks of 17 characters (a prime, so no boundary aligns with a token)
  and set `stream_mismatch = (chunked != whole)`. **THE CHUNKED RESULT IS THE
  `reply`** (F3.1; **R-47 supersedes R-46**): it is the text the streaming
  customer read, and `form_hOUT` / `answer_real` / `residual` / the judge all
  grade `base.reply`. `answer_leg` makes that choice in one named place,
  returns the whole-text restoration beside it as `AnswerLeg.reply_whole` —
  kept on the record as `ArmRunV5.reply_whole` (**R-54**), because
  `metrics.stream_fidelity` says THAT the two disagreed and a reader then has
  to see WHICH text the customer lost — and `with_streamed_answer` lays the
  scored text over `turn_replies[-1]`, so the record holds one ANSWER and one
  diagnostic beside it, never two answers.
- `ArmRunV5.turn_residual` (**R-54**) is laid onto the I record by
  `harness.with_turn_residual` inside `run_triple_v5`: the count is known only
  when the judge's prompt is built, three arms in, and while it lived on the
  triple row alone `residual` — a per-observation line that reads the arm
  record — could not reach it. The triple row carries it too, together with
  `judge_cost_usd` (= the sum of that triple's `judge.cost_usd`, computed in
  ONE place, `harness.triple_totals`), and both are written and read through
  `records.triple_totals_to_json` / `_from_json`, never `row.get(key) or 0`. A
  triple whose prompt build still refuses (a substitute in the QUESTION or the
  ORACLE — ours) carries the count out on the exception itself
  (`judge.LeakedPrompt`), because the dialogue has been read by then and a zero
  written there cannot be told from «ни один ход не нёс подмену».
- `run_triple_v5`: as v4's `run_triple` — C first, then I ∥ C′ — with
  `seed_backend_v5(case)` per arm and `RealGateway` replaced by
  `GatewayV5`; then `observe` (import `bench.agentpii5.observe`) on the I
  arm → `HopObservation`s; then the judge on the I reply: build
  `JudgeInput` (restored answer; `oracle_literals` = canonicals of the
  primary identity's items + every seed item a result returned;
  `dialogue_context` = user messages as written + tool results RESTORED
  (`text_real`) + the agent's own earlier turns, RESTORED, read off
  `ArmRunV5.turn_replies` (**ruling R-40**: question 4 asks whether the
  answer took the dialogue into account, and on `memory_anaphora` /
  `user_in_loop` it was the AGENT that established what «ему» points at —
  judging that against the user's messages alone asked about context the
  judge was never shown. RESTORED because the judge must never see a
  substitute, and the LAST non-empty turn is left out because it is the
  evidence and has its own section); `customer_question` = the last
  user message), run `residual_pregate` with the minted substitutes (from
  `gateway.substitutes()` minus real settlements, as v4's `_judge_request`
  does with `strip_leading_city`), then `judge_answer` unless `--no-judge`.
- `drive_v5` writes, per triple, the v4 `arms.jsonl` rows (all three arms,
  via v4's `arm_record` on `.base`), the `arms.v5.jsonl` row (I),
  `hops.jsonl` rows, `judge.jsonl` row, `triples.jsonl` — before the next
  triple starts (v4's rule). `main()` writes `corpus.json` (v4 view) and
  `corpus.v5.json` snapshots first, prints v4's cost lines, and at the end
  calls `bench.agentpii5.report.render_side_by_side(run_dir, baseline)`
  (baseline = `--baseline` v4 run dir, or the run's own v4 block when
  absent) into `<run>.report.txt`; header line prints agent model, judge
  model, calibration stamp (`calibrated` or `НЕ ОТКАЛИБРОВАН`).
- `--report <run dir>` rebuilds everything from files, no model, no money.

## Acceptance tests you must ship

- `test_records.py`: `test_no_pseudex`; `test_round_trips` (every
  dataclass); `test_v4_reader_ignores_v5_key`; `test_v4_readers_accept_v5_run`;
  `test_merged_done_wins`.
- `test_judge.py`: `test_no_pseudex`; `test_input_is_blind` (`JudgeInput`
  has no attribute named like `substitute*`; `build_prompt` on an input
  whose dialogue carries a minted substitute raises `OracleLeak`);
  `test_rubric_names_four_questions`; `test_rubric_has_no_form_rules`;
  `test_residual_pregate_short_circuits` (a substitute in the answer →
  `неверно`/`residual_gate`; a real value only → `None`; a piece that is
  also a real part → `None`); `test_quote_must_stand` (a verdict JSON whose
  quote is not in the answer is rejected by the parser); `test_prompt_sha_
  changes_with_rubric`.
- `test_calibration.py`: `test_no_pseudex`; `test_sample_strata`;
  `test_thresholds` (a records set at 0.84 agreement → `calibrated False`;
  0.90 and κ 0.72 everywhere → True; one type with ≥ 20 examples at κ 0.5 →
  False); `test_kappa_known_values` (κ on a textbook 2×2 table);
  `test_repeat_check`; `test_recalibration_triggers`; `test_import_refuses_
  bad_label`.
- `test_harness.py` (offline): `test_only_harness_imports_pseudex` (walk
  `bench/agentpii5/*.py`, parse imports with `ast`, assert only
  `harness.py` names `pseudex`); `test_ledger_shared` (agent and judge
  reservations go through one `SpendLedger` object — assert by constructing
  the config and inspecting); `test_run_files_written` (drive a
  hand-stubbed `run_triple_v5` — monkeypatch the arm runner to return
  canned `ArmOutcome`s — and assert every `RUN_FILES` name exists in the
  run dir); `test_baseline_flag_reads_v4_dir`.
- `test_harness_stream.py`: `test_chunked_answer` — with a dev bundle
  (`testkit.load_dev_bundle()`) and an in-memory vault, mint a substitute,
  restore a reply whole and in 17-char chunks; assert equality on a clean
  case and that a deliberately broken chunk feed sets `stream_mismatch` —
  the instrument must be able to fail. Plus
  `test_corpus_answer_is_what_the_client_read`, which runs the same leg over
  the CORPUS's own streaming cases: the hand-written sentence agrees with
  itself on every restoration, so only the corpus shows the ~4% of replies
  where the two disagree — the replies F3.1 is about.

## What you must NOT touch

`bench/agentpii4/**`, `pseudex/**`, `public/**`, `contracts.py`, `form.py`,
`metrics.py`, `observe.py`, `fixtures.py`, `report.py`, `tools.py`,
`mock.py`, `schema.py`, `scenarios5/`, `revise.py`, `build.py`. You import
`observe`, `report`, `records`-consumers and `BackendV5`; you do not edit
them — questions go in your final message.

## Checklist items you own

C-003 (live agent), C-009, C-037 (streaming leg), C-065 (harness half),
C-066 (v4 block from v4-shaped files), C-096–C-100, C-110, C-182–C-187,
C-189, C-191 (the `ast` walk test).

## Definition of done

Four offline tests + the stream test PASS; a `--report` on the fixture run
dir produces `<run>.report.txt` with the v4 block first; no `pseudex`
import outside `harness.py`; final message lists files, commands, output,
the calibration CLI usage, and questions (including: the exact model ids
for `JUDGE_MODEL`/`AGENT_MODEL` the SDK accepts today — confirm against
`bench/agentpii3/live/judge.py` and the owner).
