# FIXES — round 1 orders after the Phase 4 review (2026-09-22)

The review (`review/2026-09-22-phase4-digest.txt`; full JSON beside it) walked
all 191 checklist items (175 hold, 14 do not, 2 rows stale), ran three
adversarial skeptics and a completeness critic, and had every serious finding
re-verified by an independent agent. **All sixteen verified findings were
CONFIRMED** (one narrowed to minor). Eleven more serious findings were not
verified for lack of slots (`T1…T11` below) — the fixer verifies each FIRST
and fixes only what reproduces.

The reviewers' reproduction scripts still exist under
`/Users/igor/.claude/jobs/4e5fce9b/tmp/{metrics-lens,verify-*,corpus-*,harness-*,…}/`
— read them; **turn each reproduction into the negative test that pins the fix.**

Numbering: `#n` = verified finding n in the digest; `Tn` = unverified tail
item n; `C-nnn` = checklist item; `Gn` = spec gap. Every order names its
owner; owners' file sets are disjoint. Rulings R-01…R-46 in `RULINGS.md`
still stand unless an order below says otherwise.

---

## FIX-1 — the observer and the metric definitions
Owns: `contracts.py`, `observe.py`, `metrics.py`, `fixtures.py`, `records.py`,
`test_contracts.py`, `test_observe.py`, `test_metrics.py`, `test_fixtures.py`,
`test_records.py`, `CHECKLIST.md` rows it changes.

- **F1.1 (#2, blocker)** `value_matches` compares a per-LEAF hop against the
  WHOLE canonical; a perfect gateway tops out at 76.8 % on `round_trip`,
  `end_to_end`, `multi_all_out`, `doc_extracted`, `chain_value`. Compare the
  leaf against the item's PART for the leaf's role (`spec_v5_for(tool,
  path).role` → `item.parts[role]`), digits-to-digits for PHONE/CARD/SNILS/INN,
  ISO-to-ISO for DOB, the whole canonical only for a leaf whose FieldSpec has
  no role. A hop where NO string can satisfy both the tool and the metric is
  a corpus defect the fixture must expose, never a silent miss.
- **F1.2 (#1, blocker)** Every IN/memory hop is `leaked` on the production
  path: `_recall_request` expects a per-request re-recording of mentions the
  harness never does. Decide the memory hop from what the harness records:
  the item was masked when its message was pushed and its substitute was not
  re-minted → `observed`, produced = the substitute carried forward,
  reference = the first surface; re-minted → the form verdict on the new
  substitute; the message never masked → `leaked`. Pin with the harness's
  real record shape (`fixtures` must build mentions the way `harness._push`
  does — read it).
- **F1.3 (#3, major)** A passthrough gateway scores 100 % on `form_hOUT`,
  `chain_form`, `chain_value`, `multi_all_out`: `_out_call` and
  `_extra_call_hops` observe hops with nothing to compare. An OUT hop is
  `observed` only when the written leaf carries a spelling (or a ≥ MIN_PIECE
  piece) of the item's substitute from `substitute_surfaces`; otherwise the
  new status **`unmasked`** (add to `contracts.HOP_STATUSES`; records
  round-trips it; every metric that reads OUT hops treats `unmasked` as a
  MISS in the denominator, never a hit, never dropped).
- **F1.4 (#4, major)** `residual` counts `absent` hops as clean and sees only
  whole surfaces in `equal` regions. `absent` OUT hops are in neither
  numerator nor denominator; the answer residual scan reads the WHOLE
  restored reply for every surface AND every ≥ MIN_PIECE word-bounded piece
  of every minted substitute (declined, reformatted, undeclared item alike).
- **F1.5 (#8, major)** `answer_spans` needles are whole surfaces/parts, so a
  correctly restored declined («Пахомовой Ольге») or reformatted («+7 (999)
  000-11-22») substitute reads `absent`. Add needles that survive inflection
  and notation: for NAME the first MIN_PIECE+ letters of each part as a
  word-prefix match; for PHONE/CARD/SNILS/INN the digit signature of the raw
  region; for DOB the date-form fold (`pseudex` is NOT importable here —
  write the folds in the package, they are string rules).
- **F1.6 (#9 + #15 half 2, blocker)** `leak` counts `absent` IN hops as
  protected. Denominator = «shown to the model» = observed ∪ leaked (what
  `coverage` already does); `absent` excluded. Fix the adversarial fixture
  (`1/1`, note «absent is not shown»). `C-069`: an item never shown is not
  «altered» and not in `total`. `C-074`: `form_hOUT`'s docstring promise
  («over ALL declared tool arguments, including the ones the agent never
  wrote») — make the line say what it measures: `absent` OUT hops are a
  separate printed count beside the line («не написано: n»), never a hit,
  and the docstring matches.
- **F1.7 (#16, major)** `toolresult_masked` (and `rag_masked`, `doc_masked`)
  denominator is «results the mock happened to tag». Derive it from the
  case's declared `returns[].result_item_ids`; a declared value the result
  renders untagged is a MISS; a declared result the agent never obtained is
  `absent` and outside the denominator.
- **F1.8 (#11, major)** The three `*_masked` lines read tagged spans only.
  After the span check require that no `pieces_of(item.type, text_real[span])`
  piece (minus GRAMMAR_WORDS) survives anywhere in `text_masked` — the
  `_surviving_piece` rule `coverage` already uses. Fixture: a repeated
  untagged rendering.
- **F1.9 (#12, major)** `_transitions` accepts answer hops as «tool B». Restrict
  to OUT owners in `contracts.ACTING_OUT_OWNERS` (move that tuple from
  `schema.py` into `contracts.py`; schema imports it — coordinate: FIX-4 owns
  schema.py, so FIX-1 adds the constant to contracts and FIX-4 switches the
  import; until then schema keeps its own copy). Fixture: an answer hop with
  `source_hop` expected OUTSIDE the chain denominator.
- **F1.10 (#13, major)** `multi_consistency` counts inflections of ONE
  substitute as two. Count distinct substitutes by their MINT (nominative fold
  / ≥ MIN_PIECE stems against the minted surface); only a spelling sharing no
  stem with any minted substitute is a second substitute.
- **F1.11 (#14, major)** `stability` and `memory_stability` are one function
  under two names. Give `memory_stability` its own population — items named
  by `case.memory` specs, mentions across requests of that conversation — with
  fixtures that DIFFER from `stability`'s; if after reading the spec you
  conclude the two ARE one quantity, drop `memory_stability` from
  `V5_NEW_METRIC_NAMES` and say so in contract_questions — never two lines
  for one number.
- **F1.12 (C-044, C-083, major)** `answer_real` is vacuous for 713 cases: it
  can only fail by `residual`. Hit iff every declared OUT/answer hop of the
  observation is `observed` with the value right by F1.1's rule (and not
  `unmasked`, not `absent`); a case that declares no OUT/answer hop is
  outside the denominator; an answer naming no personal datum while the case
  declared one is a MISS.
- **F1.13 (#10, minor)** Add the clause fixtures the gate lacks: observed-but-
  wrong-value for `end_to_end`; right-value-wrong-form for `multi_all_out`;
  first-attempt-wrong for `retry_form`; a piece covering all but one char for
  the three `*_masked` lines. Fold into `adversarial` or add a fourth kind
  `clause` in `contracts.FIXTURE_KINDS` (then `report.gate` must demand it —
  tell FIX-2 in contract_questions).
- **F1.14 (G-stream)** `stream_mismatch` is written and read by nothing. Add
  the metric **`stream_fidelity`** to `V5_NEW_METRIC_NAMES` + METRICS +
  METRIC_FUNCTIONS + fixtures: over streaming cases, hit iff the chunked
  restoration equals the whole-text one (`not stream_mismatch`); FIX-3 makes
  the streaming case's scored reply the CHUNKED one (F3.1), so this line is
  where the two restorations disagreeing becomes visible.
- **F1.15 (G-public)** `rewrite_ratio` and `shared_block` carry public names
  with different definitions (threshold; masked message vs restored answer).
  Either make each identical to `public/agentmask-ru/src/agentmask_ru/score.py`
  (read it) or RENAME the v5 line (`rewrite_ratio_v5`, `shared_block_answer`)
  and say in its MetricSpec that it is not the public quantity. Do the same
  audit for every other name in `PUBLIC_METRIC_NAMES`: a MetricSpec whose
  wording describes the public unit while the code measures another is a
  finding; fix the wording to the code.
- **F1.16 (minor)** `by_axis` on a hop axis repeats every per-observation term
  in every bucket — per-observation metrics must be bucketed by the
  observation's own axis value, or excluded from hop axes with a printed note.
  The `gate` separation check is unreachable (equality already demanded) —
  either make `FIXTURE_MIN_SEPARATION` do real work (a fourth fixture whose
  expected rate is not 0 or 1) or delete it and its constant. `leaf_text`'s
  FIELD_SEP join and `LOC.by_fields` are exercised by nothing: add an
  observer test with a parent-path hop.
- **F1.17 (C-164)** `rag_identity_kept`: add a fixture where one PiiItem
  value is shared by two identities and the answer names the foreign person.
- **F1.18 (`unverified`, observe.py:436)** OUT/tool_arg `residual` is read
  from the engine's own `call.residual`. Decide it in the observer from the
  written leaf vs the minted substitutes (the same scan as F1.4); the engine's
  flag may be printed beside it, never be the verdict.

## FIX-2 — the report
Owns: `report.py`, `test_report.py`, `test_report_gate.py`.

- **F2.1 (#6, C-066, G-missing, major)** `_LEVEL_LINE` parses only the single
  word «эквивалентно»; «НЕ эквивалентно» and «нет данных» (v4's
  `stats.py:108-127`) are dropped, so the side-by-side level table is biased
  toward agreement. Match all three verdicts; test with a v4 block that
  carries each.
- **F2.2 (#5, major)** A missing or truncated `<run>.hops.jsonl` silently
  empties every hop and `residual` certifies cleanliness. Raise `ReportError`
  when the file is absent; a (case, repeat) whose arm record exists but has
  no hop rows while the case declares hops is EXCLUDED and the report marked
  НЕПОЛНЫЙ with the count.
- **F2.3 (#7, major)** The calibration stamp is trusted from the file.
  Recompute `calibrated` from the stamp's numbers against
  `contracts.CalibrationThresholds` (n ≥ sample_size, raw ≥ 0.85, κ ≥ 0.70
  whole and per type, repeat_disagreement ≤ max) and require
  `stamp.judge_model == contracts.JUDGE_MODEL` and `stamp.prompt_sha256 ==`
  the run's judge prompt hash; a stamp that lies makes the report НЕПОЛНЫЙ
  and prints why.
- **F2.4 (G-cost)** `--report` replay prints no price. Render v4's cost lines
  («0. ЦЕНА», budget, per-triple median, ceiling) from `<run>.triples.jsonl`
  and `<run>.spend.tsv` through v4's own `_cost_lines` if it is a callable;
  if it is inline in v4's `render`, print the same numbers from the same
  files with a comment naming v4's function as the definition — and the
  judge's spend (FIX-3 adds it to the triple) on its own line.
- **F2.5 (C-043, C-046, C-047, G-share)** v4 levels and the taxonomy are
  never scored per behaviour. Run v4's `score_triples`/`render` over the
  behaviour subsets (a filter on `corpus.json` by `case.id` → behaviour from
  `corpus.v5.json`) and print one v4 block per behaviour after the corpus-wide
  one; `answer_real` by behaviour is printed; `same_tool_other_target`'s
  `other_person` count appears in its block.
- **F2.6 (C-080)** `test_every_axis_prints` never checks the rendered report;
  assert the printed report carries every axis section for every carried
  line.
- **F2.7 (T11)** `judged_by == "residual_gate"` verdicts are counted in the
  judge histogram and inside the κ the report certifies. Print them as their
  own row («отказано до судьи: n») and exclude them from the κ line; the κ
  itself is FIX-3's (`calibration.kappa`) — FIX-2 reads whatever it returns
  and prints the pre-gate count beside it.
- **F2.8 (F1.13)** If FIX-1 adds a fourth fixture kind, `gate` demands it.

## FIX-3 — the harness, the judge, the calibration
Owns: `harness.py`, `judge.py`, `calibration.py`, `test_harness.py`,
`test_harness_stream.py`, `test_judge.py`, `test_calibration.py`,
`briefs/judge.md` (notes).

- **F3.1 (T7, blocker — verify first)** The streaming leg is measured on every
  streaming case and read by nothing; the 84 streaming cases are scored on the
  WHOLE restoration, text the streaming customer never sees. For a streaming
  case the scored `reply` (and `turn_replies[-1]`) is the CHUNKED restoration
  (the sidecar's per-field contract: `delta.content` through the chunk path,
  tool arguments never); the whole-text restoration is kept in the record for
  the diff and `stream_mismatch` stays true iff they differ (F1.14 prints it).
- **F3.2 (T8, major — verify first)** A residual substitute in any non-final
  turn raises `OracleLeak` and kills the whole live run. The judge must never
  see a substitute AND the run must not die: an intermediate turn carrying a
  minted substitute (whole or ≥ MIN_PIECE piece — the same scan as F1.4) is
  passed to the judge with the substitute replaced by the marker
  «[нераскрытая подмена]», the turn is flagged, `residual` counts it, and
  `assert_blind` then holds by construction. Pin with a run whose turn 1
  reply keeps a substitute.
- **F3.3 (T9, major — verify first)** The calibration sheet shows the human
  labeller the judge's label and reason. The exported sheet carries NO judge
  output; labels are joined on import by (case_id, repeat, answer hash).
- **F3.4 (T10, major — verify first)** `repeat_disagreement` is structurally
  0.0: the K stability rows carry one judge label. Repeats are K INDEPENDENT
  judge calls (`calibration export` with `--repeats K` performs them through
  `judge_answer`, spending from the ledger, `temperature` as the judge config
  says); `repeat_check` then compares K real verdicts. Offline test with a
  scripted judge that answers differently per call.
- **F3.5 (T11 + G-calibration)** `judged_by == "residual_gate"` verdicts are
  excluded from `agreement`/`kappa` (they are not the model's); and there IS
  a path from a filled sheet to a run: `calibration import --sheet … --run
  <run dir>` writes the recomputed stamp as row 0 of that run's
  `<run>.judge.jsonl` (records' writer), so a report is never «НЕ
  ОТКАЛИБРОВАН» because nobody could tell it otherwise. Document the
  procedure in `briefs/judge.md` (§calibration) and in the CLI help.
- **F3.6 (minor)** The judge's spend goes into the triple's cost
  (`cost_usd` + a `judge_cost_usd` field on the triple record — FIX-1 owns
  records.py: ask in contract_questions and write the field only when it
  exists; until then print it in the run header) and counts against the
  ceiling of a resumed run. The rubric guard: replace the four-stem substring
  test with a word list that includes the rubric's own synonyms (склонение,
  написание, орфография, регистр букв, нотация, запись…) and does not fire on
  «информация». Delete the unreachable adapters or wire the harness through
  them — one of the two; the docstring must be true.

## FIX-4 — the corpus, the builder, the families
Owns: `schema.py`, `build.py`, `revise.py`, `scenarios5/*.py`, `tools.py`,
`mock.py`, `test_schema.py`, `test_build.py`, `test_revise.py`,
`test_generator_a.py`, `test_generator_b.py`, `test_tools.py`, `test_mock.py`,
`corpus.v5.json`, `corpus.json`, `ladder.json` (rebuilt by `build`).

- **F4.1 (#15 half 1, T1, T5, blocker)** 42 % of the revised half's declared
  IN/tool hops are crossings the mock never renders; K03's 75.5 % counts
  them; `return_form` is declared and never compared. **Make the declaration
  provable at build time:** `build` seeds `mock.seed_backend_v5(case)` and
  drives every `ReturnExpectation` (the expected call with the case's own
  argument values), and REFUSES a case whose `result_item_ids` the backend
  does not render, whose rendered form ≠ `return_form`, or whose declared
  IN/tool hops have no rendered span. `has_result` is then true only for
  provable loops. `revise.py` must SEED what it declares (a v4 case whose
  result the mock cannot render gets its seeds written into the case, the way
  generator_b's families do) rather than lose the loop — K03 stays ≥ 75 % by
  making the 132 + others provable, not by dropping them; if the share still
  falls below 0.75 after everything provable is seeded, STOP and report the
  exact arithmetic in contract_questions (do not move the bar).
- **F4.2 (T2, blocker — verify first)** `chain_value`'s ground truth is
  contradicted by the control arm: 520 of 5 441 revised transitions are
  attainable. A transition (`source_hop` IN/tool → OUT) is declared only
  when the argument value the OUT hop expects is a value the source result
  actually renders (F4.1's proof gives that); `revise._arguments` /
  `_argument_item` declare nothing else.
- **F4.3 (T3, major)** `build` keeps a stale `ladder.json` with no check
  against its own `corpus_sha256`. Compare on every build; a mismatch without
  `--regenerate-ladder` is a refusal that prints both digests; with the flag,
  the holdout of the new ladder must equal the old one for every case id that
  still exists (frozen), new cases distributed by the same seed.
- **F4.4 (T4, major)** `prove_no_search_v5` does not watch `revise.py` and
  cannot see the `in` operator or a hand-rolled scan. Watch `revise.py`,
  `build.py` and `scenarios5/`; extend the v5 prover (never v4's) to flag
  `x in <finished string>`, `.find`, `.index`, `re.search/match/finditer`
  and `startswith/endswith` on any variable bound from `case.messages`,
  `rendered`, `text` — then fix what it finds in `revise.py` (`_loo…` reads
  a finished message) by deriving from what was BUILT.
- **F4.5 (T6, major)** `rag`'s declared chunk hops exist only if the live
  agent puts the topic word in its query (257 of 350 vanish). The mock's
  `kb_search` must return the case's chunks for any query that carries the
  customer's `query_item_ids` values (name/phone), matching by seeded
  identity, not by a topic word; the declared hops are then attainable by
  the agent that does what the case asks.
- **F4.6 (minor)** `rag`: `extra_people` drawn twice yields the same person
  (70 of 100 cases give one value two identities; 2 give a «foreign» the
  customer's own name) — draw from one stream with a used-set. `revise._argument_item`
  treats `p0.other2` and `p0` as one identity — split on the full identity.
  Contract docstrings promising guards that do not exist (`ReturnExpectation`
  rendering assertion, `ForcedError` retry comparison) become true through
  F4.1 (tell FIX-1 in contract_questions which docstring wording to keep).
- **F4.7 (C-004, C-048, C-041/C-137)** `test_r07_min_hops` negative (a
  has_result case with 2–3 hops → exactly {R07}). `user_in_loop` declares a
  `MemorySpec` for the value shown at `show_turn` and recalled at
  `confirm_turn` so `memory_consistency` has a population there. The single
  family: over the seeded singles assert the four MINIMAL_LOOP (kind, owner)
  pairs; print in `build --check` how many singles are v4 two-hop shapes
  (downgraded by R-23's conversion) so the §8.2 share is read honestly.
- **F4.8 (T-form)** `return_form` expected ≠ actual is a CORPUS defect
  printed by `build --check` (F4.1 provides the actual) — and the observer's
  actual-form record (FIX-1) is what the report prints.

---

## Definition of done for round 1

Every `python3 -m bench.agentpii5.test_*` PASS; `report --selftest` exit 0;
`build --check` clean AND `build` rewrites `corpus.v5.json`/`corpus.json`
(the ladder's holdout unchanged for surviving ids — F4.3 proves it); only
`harness.py`/`test_harness_stream.py` import pseudex; v4/pseudex/public
untouched; every fix pinned by a negative test built from the reviewer's
own reproduction; `python3 wiki/check.py` 0 findings. Round 2 = the three
skeptics re-run against THIS list to confirm closure.

---

# Round 2 orders (2026-09-22, after round 1 — rulings R-47…R-56)

Two waves: **wave 1** = FIX-1 + FIX-4 (the contract and the corpus land
first); **wave 2** = FIX-2 + FIX-3 (their users). Then the skeptics re-run.
Owners' file sets as in round 1, plus: FIX-1 also owns `test_form.py` and
`form.py` this round; FIX-3 owns the CHECKLIST rows it changes.

## FIX-1 (wave 1)
- **F1.19 (first thing)** `CORPUS_SIZE_BAND_V5 = (1200, 1800)` (R-51) — one
  line, so FIX-4's build can go green while you work.
- **F1.20 (R-54)** `ArmRunV5.reply_whole: str` (the whole-text restoration on
  a streaming case; "" otherwise) and `ArmRunV5.turn_residual: int` (how many
  EARLIER turns still carried a minted substitute when the judge prompt was
  built); `records.py` round-trips both with a negative each; the triple row
  gains a validating reader/writer in `records.py` for `judge_cost_usd` and
  `turn_residual` (a missing or non-numeric field is refused). `residual`'s
  per-observation term counts `turn_residual > 0` as a miss; fixture.
- **F1.21 (R-53)** `metrics` imports `tools.expected_leaf_value`; `leaf_value_ok`
  becomes a caller of it; a test asserts the two never disagree over every
  (tool, path) of `REGISTRY_V5` on a sample item per type.
- **F1.22** `contracts.RUN_FILES` gains `"<run>.meta.json"` (run_id, benchmark,
  model, judge_model, tier, repeats, digest, ceiling_usd, spent_usd,
  prompt_sha256, finished — written by `harness.main`); `contracts.SideBySide`
  gains `judge_pregate: int` and `excluded_observations: tuple[str, ...]`
  (FIX-2 fills them in wave 2; until then `report.py`'s local copies stand).
- **F1.23** `test_form.py`'s keep-going runner: make `e2e/lint_tests.py`
  green on it (read the lint's rule; record the failure the way it
  recognises) without losing the keep-going property.
- **F1.24** Do NOT delete `FIXTURE_MIN_SEPARATION` yet (report.gate imports
  it); FIX-2 removes the comparison in wave 2 and the architect deletes the
  constant after.

## FIX-4 (wave 1)
- **F4.9 (R-49)** `revise._arguments`: `said` wins over `chained` on a
  MUTATING tool; the cases that lose their only transition leave
  `sequential_chain` (they keep `has_result`). Print the count in
  `build --check`.
- **F4.10 (R-49 top-up)** generator_a's `sequential_chain` family grows by
  as many PROVABLE chains as keep the family ≥ its floor with ≥ 20 % margin,
  across the six verticals; every transition proven by the mock at build.
- **F4.11 (R-50)** A new authored family `scenarios5/single.py` — 100 cases,
  ONE read tool whose result carries the customer's data, the answer uses it
  (the 4-hop MINIMAL_LOOP), ≥ 6 verticals, all registers, ≥ 4 return forms,
  every case provable; added to `PLAN_A`; `BEHAVIOUR_FLOORS["single"]` and
  the share row read honestly (`build --check` prints authored / revised /
  two-hop counts).
- **F4.12 (R-52)** Regenerate the ladder ONCE with an explicit flag that
  says why (`--regenerate-ladder --unfrozen-before-first-run` or the name you
  choose); after it, `_holdout_moved` refuses as before; write the new
  `corpus_sha256` into your final message.
- **F4.13** `schema.py`: import `contracts.ACTING_OUT_OWNERS`, delete the
  local copy.
- **F4.14** `contracts` docstrings (F4.6): wording per your own proposal —
  «`build` proves it (mock.render_problems) and `toolresult_masked` scores
  it» — send FIX-1 the exact text in contract_questions (FIX-1 owns the file).

## FIX-2 (wave 2)
- **F2.9** Use `SideBySide.judge_pregate` / `excluded_observations` (drop the
  report-local copies); read `<run>.meta.json` through `records` if FIX-1
  gave it a reader, else through `json` with the RUN_FILES key.
- **F2.10** `out_absent` printed directly beneath `form_hOUT`; the per-axis
  loop uses `metrics.prints_on_axis(name, axis)` and prints
  `metrics.AXIS_NOTE` for the rest.
- **F2.11 (R-55)** Delete the unreachable separation comparison in
  `report.gate` (and its test if any); tell the architect when done.
- **F2.12** `judge_cost_usd` read from the triple through records' reader
  (F1.20), never `row.get`.

## FIX-3 (wave 2)
- **F3.7 (R-54)** Populate `reply_whole` and `turn_residual` on the I arm's
  `ArmRunV5`; keep `judge_cost_usd` on the triple equal to the sum of
  `judge.cost_usd` by construction (one place computes it).
- **F3.8 (R-56)** `JudgeConfig.temperature: float`, set explicitly where the
  config is built; the K repeats use it.
- **F3.9** CHECKLIST rows C-182 and C-037 per your own proposal; `briefs/judge.md`
  notes R-47/R-48.

## Definition of done for round 2
As for round 1, plus: `build --check` prints the authored `single` count and
the chain top-up; the ladder digest recorded; every `python3 -m
bench.agentpii5.test_*` PASS; `e2e/lint_tests.py bench/agentpii5` clean.
