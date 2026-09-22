# RULINGS — the architect's decisions on the builders' contract questions

Applies to everything under `bench/agentpii5/`. Every builder that starts after
2026-09-22 15:30 reads this file BEFORE its brief; where a ruling and a brief
disagree, the ruling wins. Each ruling names WHO applies it:

| tag | who |
|---|---|
| `done` | already applied — in `contracts.py` or in the landed file |
| `GB2` | generator_b, second half (families, revise, build; owns `schema.py`, `scenarios5/common.py`) |
| `J2` | judge, second half (`judge.py`, `calibration.py`, `harness.py`) |
| `M` | metrics (`observe.py`, `metrics.py`, `fixtures.py`, `report.py`) |
| `INT` | the Phase 3 integrator, after every builder has landed |

`python3 -m bench.agentpii5.test_contracts` is PASS after these changes.
`contracts.py` CHANGED after the four leaf components landed — a top-level
builder must re-read it, not trust its dependency's notes about it.

## From judge/records

- **R-01** `case_v5_to_json(case) -> dict` and `case_v5_from_json(row) -> CaseV5`
  live in `schema.py`: `base` through v4's `Case` to/from json, the v5 block
  beside it; a `corpus.v5.json` row (`contracts.RUN_FILES`) is exactly that
  dict. — `GB2`
- **R-02** `JudgeRow(case_id, repeat, input_sha256, verdict)` is normative in
  `contracts.py` §6; `records.py` imports it (its local copy is gone). — `done`
- **R-03** `judged_by == "none"` ⇔ `label == ""`. No other combination; a
  reader refuses it. Codified in the `JudgeVerdict` docstring. `J2` writes
  verdicts that way. — `done` / `J2`
- **R-04** `AnswerSpan` is NOT persisted in the arms file; the observer
  derives it on every read. records' to/from-json helpers stay (harmless). — `done`

## From comparator

- **R-05** The ABSTAIN rule is normative: `contracts.FORM_ABSTAIN`. `form_match`
  adds a feature to `differs` iff `a != b` and neither side carries the
  feature's abstain label. A string with no letters yields `none` for
  `case_class` (NAME/LOC/EMAIL/PLATE) and `NAME.script`, and the feature
  abstains. `form.py` must import `FORM_ABSTAIN` and drop its local
  `ABSTAIN_LABELS`; its extractors must emit `none` on letterless input. — `INT`
- **R-06** `LOC.city_present` cannot be isolated from `city_position` (an
  absent city is also a position): the per-feature isolation check accepts
  `{city_present, city_position}` for either. `CHECKLIST` C-173 says so. — `done`
- **R-07** `PHONE.prefix` and `CARD.separator` gained the label `other`: an
  extractor returns it when no named shape matches, never falls through to the
  last branch. `INT` verifies with a negative fixture per feature. — `INT`
- **R-08** The brief's LOC stem list carried `переулк` and `переулок` as two
  stems; folding them (`form_tables.GENERIC_STEM_CANON`) is right, the brief was
  wrong. — `done`
- Accepted as written: hyphen halves as separate words for `case_class`; the
  Latin surname-suffix table for `order`; `city_present` requiring a street
  left after the city; uniform `date_separator`; `MONTH_OTHER`; the
  keep-going test runner.

## From generator_b/foundations

- **R-09** **K04 is a claim about the v5-AUTHORED cases** (`revised_from_v4 ==
  False`). The 834 revised cases keep the registers v4 measured (voice_raw 276,
  voice_itn 183, chat 250, sloppy 119, clean 6) and no mix of new cases can
  move that block. `REGISTER_SHARES` now sums to 1.00 (`chat` 0.30 — the
  former 5 % remainder). `validate_corpus_v5` computes K04 on the authored
  subset; the report prints the corpus-wide register table beside it.
  **`test_schema.py` is RED on K04 right now because of this change** — `GB2`
  reworks the check and the synthetic corpus of the test. — `GB2`
- **R-10** `V4_KIND_FOR_BEHAVIOUR` is normative in `contracts.py`;
  `scenarios5/common.py` imports it and drops its copy. — `GB2`
- **R-11** `DocumentSpec.record_ids` (the seed records the document renders,
  `len == record_count`) and the tightened R18 («`extracted_item_ids` are items
  of THOSE records», `len(record_ids) == record_count`, every id a seed
  record) are added by `INT` after every builder has landed — adding a
  dataclass field under a running builder broke `fixtures.py`. `GB2`'s document
  family builds `extracted_item_ids` only from the records it renders and
  keeps those record ids where one line can thread them into the field. — `INT` (+ `GB2` prepares)
- **R-12** A RAG chunk seed is `{"text": <chunk>, "slots": {<key>: <surface>}}`;
  the item's `Locus.path` is `slots.<key>`, `start/end` index into `text`.
  Normative comment beside `RagSpec`. — `done`
- **R-13** R15 reads «an OUT/tool_arg hop at or after `confirm_turn`». — `done`
- **R-14** K12 is enforced by `build.py` / `test_build.test_holdout_frozen`;
  `validate_corpus_v5`'s docstring says so. — `done`
- **R-15** K01 includes «every case id unique». `GB2` keeps the check under K01. — `done` / `GB2`
- **R-16** `registers_for` keeps the mix voice_raw .28 · voice_itn .17 · chat .30
  · sloppy .15 · clean .10 — it now sums to 1.00, no remainder. — `GB2`
- Accepted as written: R21 checked both ways; R13/R15/R17/R18 checking that the
  spec's tools are offered; the `plate` renderer with the vault key as
  canonical; `new_builder`'s eight parameters; the seed helpers' shapes.

## From tools

- **R-17** R19: a tool declares EVERY form it can return (a state-decided one —
  `address_suggest` canon/list, `kb_search` chunks/list, `bank_client_find`
  single/list — is declared as all of them); the case's `return_form` names
  the one THIS seeded state yields. The observer records the ACTUAL form
  (`BackendV5.form_of`) on every tool result; the metric that slices results
  by form uses the actual form, and `expected != actual` is a CORPUS defect
  printed by `build --check` and the report, never a gateway miss. — `done` / `M` / `J2`
- **R-18** A documented parse refusal whose message names the offending
  argument is recorded as `error_with_value`. — `done`
- **R-19** `ForcedError` echoes `PiiItem.canonical` (what the tool's parser
  accepted), never the spoken surface; `retry_form` compares against it. — `done`
- **R-20** One slot tag per item per result — the FIRST rendering. Leak checks
  (`toolresult_masked`) read the whole text; no metric counts occurrences. — `done`
- **R-21** v4's writer refuses control characters inside a slot, so a free-text
  document carries no newline: a CSV read as TEXT joins rows with « | », a CSV
  read as a TABLE is `file_read`'s `list` form. `GB2`'s document family uses
  exactly those two renderings; changing v4's writer is out of scope. — `GB2`
- Accepted as written: three extra `list` forms (`address_suggest`,
  `vehicle_check`, the third the brief names); no bare CITY path in any
  `result_pii` (a city identifies nobody and the engine refuses bare cities on
  purpose); `registry_problems(registry)` takes the registry; the generic
  `seed_record`; v4's private tags dropped.

## Standing rules for every builder still to run

- Re-read `contracts.py`; the notes a dependency left about it may predate a
  ruling above.
- Anything still unsettled goes into `contract_questions` with the exact
  proposed change — never a silent choice.

---

# Phase 3 rulings (2026-09-22, after all eight builders landed)

Tags: `INT-A` (data model & report integrator), `INT-B` (tools / form / plan
integrator), `FIX-C` (generator_a's K03 fix), `done`.

## The two reds

- **R-23 K03 (73.1 % < 75 %) is closed by CONVERSION, not by moving the bar and
  not by growing the corpus.** Exactly the authored no-result cases become
  cases that reach a result while keeping what they were built to test:
  branching «not found» → «not found by X, then found by Y» (the `empty`
  first call stays, so the `empty` form keeps its coverage; the else branch is a
  second READ that returns the seeded record — «если по телефону не найден,
  ищи по email» is what a real rule says); parallel `notify_sms ×3` → a lookup
  that returns the recipients' records first, then the three notifications (an
  agent notifying three people looks them up). At least 31 must convert;
  `build --check` and `test_build` go green, the `empty` form and the
  `template` owner keep ≥ MIN_TYPE_DENOMINATOR, no family drops below its
  floor. — `FIX-C`
- **R-24 The registry gap closes in `tools.py`, once, right after
  `REGISTRY_V5` is assembled:** v4's in-memory `REGISTRY` is widened with the
  twelve new specs, with an assertion that no new name collides with a v4 one
  (a collision would silently replace the baseline's tool). It is an explicit,
  documented side effect on v4's module object, never a file edit;
  `plan_a.py`'s stopgap goes; `test_generator_a.test_v4_registry_gap` goes
  with it (FIX-C removes the check, INT-B the stopgap). — `INT-B` / `FIX-C`

## From generator_a

- **R-25** The four hop constructors and the three bookkeeping helpers move
  from `scenarios5/plan_a.py` to `scenarios5/common.py`; `plan_a.py` and
  `plan_b.py` import them from there and KEEP re-exporting the same names for
  one release (FIX-C imports them while INT-B moves them). With the helpers
  gone, `plan_a.py` imports its family modules at the TOP like every other
  file — the bottom-of-file exception disappears. — `INT-B`
- **R-26** `ticket_history` refuses the ids `ticket_find` mints (`t-` vs
  `tkt-`): the mock's `tickets` prefix becomes `t`, so `ISSUE_ID_RE` stays the
  documented one. — `INT-B`
- **R-27** `courier_status.recipient.*` and `crm_upsert_contact.contact.*`
  (and any other leaf composed from the call's own ARGUMENTS) leave
  `result_pii`: a leaf that can never be tagged is a permanent miss charged
  to the gateway — the v4 disease inverted. The comment beside each says why. — `INT-B`
- Accepted as written: the retry family's four verticals; no
  `ReturnExpectation` on a forced ordinal; the echo hop naming the seeded
  item; six chain verticals; `TOOLS` as the module union with per-case slices.

## From generator_b

- **R-28** R-12 is SUPERSEDED by the landed mock: a prose seed is a `template`
  column plus one flat column per `{slot}`, tagged by field name; a slot name
  is `[a-z_]+` (a digit in it makes it literal text, and every hop on it a
  crossing that never happened). `INT-A` rewrites the comment beside `RagSpec`
  to describe THAT shape and where `Locus.path` points; `INT-B` puts the
  slot-name rule in `mock._template_pieces`'s docstring and adds a negative
  test (`{who2}` refused or flagged, never silently literal). — `INT-A` / `INT-B`
- **R-29** `tools.FILE_EXTENSIONS` is the normative tuple; `document.py`
  imports it instead of restating it, and the restating test goes. — `INT-A`
- **R-30** R-11 revised for CSV: `DocumentSpec.record_ids` = the SEED RECORDS
  the document renders (a CSV is ONE `documents` row holding N people, so
  `len(record_ids)` may be < `record_count`); `record_count` stays the number
  of PEOPLE. R18 checks `record_count ≥ 1 (≥ 2 for csv)`, every id in
  `record_ids` a seed record, `extracted_item_ids ⊆ items of THOSE records`;
  the `len(record_ids) == record_count` equality is dropped. `INT-A` adds the
  field to contracts, threads it through `schema.py` (R18 +
  `case_v5_to/from_json`), `scenarios5/document.py`, `fixtures.py`
  (`_doc_case`), and `test_schema.py`, in ONE change so no test is red
  between commits. — `INT-A`
- **R-31** R15 now reads «an OUT hop with owner in ('tool_arg', 'template',
  'summary') at or after `confirm_turn`» — a handover acts through summary
  leaves. `schema.py` follows the new text. — `done` (contracts) / `INT-A` (schema)
- **R-32** `common.draw` cannot be asked twice in one case (v4's index
  overrides return the same person): the note lives in v5's
  `scenarios5/common.py` beside `extra_people` — v4's docstring is not ours to
  edit. — `INT-B`
- Accepted as written: `prove_no_search_v5` widening v4's `_WATCHED_DIRS` for
  the build and restoring it (pinned); `revise.py` downgrading a case to
  `single` with the reason rather than claiming a behaviour it lacks;
  `_pick_spec` choosing the first SEEDED identity; `STREAMING_EVERY = 3`; the
  file path in the system prompt; `document_seed` with the format as a column.

## From metrics

- **R-33** `rewrite_ratio`'s denominator is «both `control_reply` and
  `base.reply` non-empty», `ic` ignored — the brief's rule would have been
  0/0 on every fixture and refused for ever. — `done` (code) — brief note `INT-A`
- **R-34** `gate_all(functions)`, `side_by_side(v5_dir, v4_dir, functions)`,
  `report_lines(…, functions)` take the metric registry explicitly;
  `render_side_by_side(v5_dir, v4_dir)` stays the entry point. C-190's
  acceptance reads «`report.render(side: SideBySide, …) -> list[str]`, reached
  through `render_side_by_side(v5_run_dir, v4_run_dir)`». — `done` / CHECKLIST `INT-A`
- **R-35** `SideBySide.v4_extra` and `V4_EXTRA_LINES` are DROPPED from
  contracts: v4 computes `v4_leak` / `v4_seed_coverage` / `v4_overmask` inside
  `bench/agentpii4/report.py::render` (no function exposes them), the report
  embeds v4's block byte for byte, and any other source of those three numbers
  would be a re-derivation. `records.py` / `report.py` drop the field. — `INT-A`
- **R-36** `HopObservation` stays without offsets / engine type; `observe`
  re-derives them from the arm records (one definition). — `done`
- Accepted as written: the temp-dir run fixture; `answer_spans`' widening
  rules; «exists but no slot → absent»; memory recall not locatable → absent;
  `coverage` on IN/memory; `value_matches` casefold + ё→е; `fixtures.NOTES`;
  the masculine name pair in the form fixtures (pymorphy3 reads a feminine
  surname as `gent` either way).

## From judge

- **R-37** `JUDGE_MODEL = "claude-sonnet-5"` STAYS — Claude 5 ids carry no
  date; the comment now says so. `AGENT_MODEL` stays dated. — `done`
- **R-38** `judge_answer(config, request, substitutes_minted)` +
  `judge_with(config, substitutes_minted)` as the protocol adapter;
  `draw_sample(observations, thresholds, seed, holdout_ids)`;
  `drive_v5(…, run_one)`; `stamp()` requiring `n ≥ sample_size` and treating a
  missing stability sub-sample as `repeat_disagreement = 1.0`; v3's judge
  helpers restated (v3's module imports pseudex); the two-halves import test.
  All accepted. CHECKLIST C-191's evidence names both halves. — `done` / CHECKLIST `INT-A`
- **R-39** `<run>.judge.jsonl` row 0 is the CalibrationStamp — codified in
  `RUN_FILES`. — `done`
- **R-40 The judge SEES the agent's intermediate turns.** `ArmRunV5` gains
  `turn_replies: tuple[str, ...]` (the agent's reply at the end of every turn,
  in turn order; the harness already holds them); `records.py` writes/reads
  it; `judge.dialogue_context` emits `role="assistant"` turns from it, so
  question 4 («учёл ли контекст») on `memory_anaphora` / `user_in_loop` is
  judged WITH the agent's own earlier words; `calibration export` shows the
  labeller the same. `fixtures` and `test_report.build_run` populate it. — `INT-A`

## Definition of done for Phase 3

Every `python3 -m bench.agentpii5.test_*` PASS; `report --selftest` exit 0;
`build --check` prints no problem and `build` WRITES `corpus.v5.json` +
`ladder.json`; only `harness.py` (and `test_harness_stream.py`) import
pseudex; `bench/agentpii4/`, `pseudex/`, `public/` untouched; `wiki/MAP.md`
row for `bench/agentpii5/` updated from `design` to `live` with the real file
list and `python3 wiki/check.py --sync` green.

---

# Phase 3 outcome (2026-09-22 evening)

All of R-23…R-40 applied; the suite is 19/19 green, `report --selftest` 27/27,
`build --check` 1203/1594 = 75.5 % with result, wiki 0 findings. Rulings made
on the integrators' questions:

- **R-41 reverses R-27.** INT-B showed R-27's premise false: the mock TAGS
  `courier_status.recipient.*` and `crm_upsert_contact.contact.*` whenever
  the row was SEEDED (the stored card in the system's notation — a real IN
  hop), and on a row the call itself created R05 already forbids the hop. So
  there was no permanent miss to prevent: v4's declarations are restored, the
  `ARGUMENT_ECHO_TOOLS` exemption to V04 is gone, `NEW_TOOL_RESULT_TYPES`
  and `result_pii` agree again. — `done`
- **R-42** `ACTING_OUT_OWNERS` for R15 stays `('tool_arg', 'template',
  'summary')` — `answer` excluded, as INT-A argued: a loop whose act is a
  second sentence showing the value tests nothing beyond `show_turn`. — `done`
- **R-43** The K03 tripwire in `test_build.py` retired; K03 is enforced with
  the other fourteen rules. — `done`
- **R-44** `plan_b.py` keeps its bottom-of-file family imports (helpers with
  exactly one consumer each); `extra_people` now lives in `common.py` with
  the draw-twice note. — `done`
- **R-45** `document.py` importing `tools` makes R-24's registry widening a
  load-order side effect of a scenario module. Accepted and named: the
  widening stays at `tools` import time; a builder that needs v4's validator
  to know the twelve tools imports `bench.agentpii5.tools` first. — `done`
- **R-46** On a streaming case `turn_replies[-1]` (whole-text restoration)
  may differ from `stream_verdict`'s chunked restoration exactly when
  `stream_mismatch` is True; `dialogue_context` drops that last turn, so the
  judge never sees the difference. Known; `stream_mismatch` is the metric that
  carries it. — `done`
- `e2e/lint_tests.py` flags `test_form.py`'s keep-going runner («except
  глотает провал»): the exception is recorded and printed as a red check, not
  swallowed. Left for the Phase 4 reviewers to judge with the lint's own rule.

---

# After fix round 1 (2026-09-22 evening)

- **R-47 supersedes R-46.** A streaming case is SCORED on the chunked
  restoration — the text the streaming customer reads (F3.1); the whole-text
  restoration is kept beside it (`ArmRunV5.reply_whole`, round 2) and
  `stream_fidelity` is the line where the two disagreeing shows.
- **R-48 retires the adapter half of R-38.** `judge_with` / `pregate_with`
  are gone; the harness calls `judge_answer(config, request,
  substitutes_minted)` directly and the docstrings say so.
- **R-49 chain truth on a MUTATING tool.** When the customer states a NEW
  value and the agent writes it into an update call, the source of that
  argument is the customer's message, not the earlier result that held the
  OLD value: such a hop is IN/user → OUT/tool_arg, never a chain transition.
  `revise._arguments` lets `said` win over `chained` for mutating tools; the
  cases that lose their only transition leave `sequential_chain` honestly,
  and generator_a tops the family up above its floor with PROVABLE chains.
- **R-50 the `single` family is AUTHORED.** §8.2 calls the single call «the
  base, 4 hops»; 84 revised cases carry that loop, 379 are v4's two-hop shape.
  generator_a gains a `single` family of 100 provable cases across ≥ 6
  verticals and all registers.
- **R-51 `CORPUS_SIZE_BAND_V5` widens to (1200, 1800).** The spec's «≈1200–
  1500» was an estimate made before the 834 revised cases were kept whole;
  K01 is a sanity bound on the corpus, not a target to trim families to.
- **R-52 the ladder may move ONCE more.** «Frozen before any debug run» — no
  live run has happened; round 2 regenerates the ladder once (the new and
  topped-up families reshuffle v4's per-family draw), then its
  `corpus_sha256` is the frozen one and `_holdout_moved` refuses every later
  move. The digest is recorded in FIXES.md at the end of round 2.
- **R-53 one definition of «the value a leaf expects»:**
  `tools.expected_leaf_value(item, spec)`; `metrics` imports it, its local
  `leaf_value_ok` becomes a thin caller.
- **R-54 `turn_residual` and `reply_whole` live on `ArmRunV5`** (records
  round-trips them); the triple row carries `judge_cost_usd` (= the sum of
  that triple's `judge.cost_usd`) and `turn_residual` as well, validated by
  records' triple reader. `residual` counts `turn_residual > 0` as a miss of
  the observation.
- **R-55 `FIXTURE_MIN_SEPARATION` is deleted** (report.gate's comparison is
  unreachable — the fixtures pin both rates exactly); no decoration.
- **R-56 `JudgeConfig.temperature: float`** is explicit (no SDK default) and
  the K repeats run at the same value the run uses.

---

# R-57 (2026-09-23) — a stamp refresh is not a redraw

FIX-4's CSV fix (310 items carrying the literal surface «None», because a seed
path walked through a LIST) changes `case.base`, so the v4 corpus digest moves
and `write_ladder` refuses the kept ladder — while the MEMBERSHIP of every tier
is provably unchanged (holdout 347 → 347, moved 0; every tier moved 0).

**The freeze protects membership, not a hash.** Its promise is «the holdout has
not seen the debugging»; a corpus whose tiers hold exactly the same case ids
keeps that promise literally, and refusing it would mean either shipping a
corpus with 310 poisoned surfaces or hand-editing a stamp — both worse.

So: **`build` refreshes `corpus_sha256` in place when it PROVES every tier's
membership identical by case id, and prints the proof** («холдаут не сдвинулся:
0 из 347», per tier). `--regenerate-ladder --unfrozen-before-first-run` stays
for an actual REDRAW and keeps its meaning (no live run has happened yet); a
refresh that would move even one id is refused and becomes a contract question.
A run's report records the ladder's `corpus_sha256` and the id-set hash, so a
reader can tell a refresh from a redraw after the fact.

Defence in depth, separately: the needle layer must refuse a PLACEHOLDER
surface («None», «», «null») as an identifying piece whatever the corpus says —
FIX-1's contract, so that a corpus defect of this class can never again make a
leak check silently exempt a value.

---

# R-58 (2026-09-23) — a needle must be IDENTIFYING, whole value or piece

FIX-4's reproduction: `doc_masked` prints 92/100 for the PERFECT gateway, and
all eight misses are a LOC house item whose whole value is one or two digits
(«19», «6», «13»). The value never reached the model — `form_parse` renders the
person columns and no address — but the `whole` needle is a bare substring
test with no floor, so «19» is «found» inside «i11: 1977-01-07».

**The rule.** `PIECE_MIN_CHARS` guards a piece because a two-character
fragment identifies nobody; the same is true of a two-character VALUE. So the
floor belongs to the needle, not to the piece: a value below the identifying
floor (digits-only values below the digit floor) carries NO needle, and
`survives_in` answers False for it — everywhere, not only in `doc_masked`. The
engine takes the same position on a bare house number and a bare city.

**And the half that matters more:** an item that carries no needle must be
EXCLUDED from every survival-based denominator, never credited as clean. A
value we cannot look for is not a value we protected. The report prints the
count («не оценивается по выживанию: n»), so the exclusion is visible rather
than flattering.

**Where a span exists, the span decides.** The needle path is the UNTAGGED
fallback; a short value the mock tagged is still scored by its span, so this
ruling costs no coverage — it removes evidence we never had.

Corpus note (no change ordered): a bare house number as a standalone item is
only scorable through its tag, which is why the tagged path stays the primary
one. If a family ever declares a short item with no tag, `build` should refuse
it — FIX-4's call after H4.2.
