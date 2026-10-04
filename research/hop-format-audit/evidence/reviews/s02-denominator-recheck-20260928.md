# S02 denominator recheck — 2026-09-28

Independent reviewer re-check of the S02 repair in
`prototype/bench/agentpii5/payload_canaries.py` (worktree branch
`research/hop-format-audit`). I did not write the repair; I read the diff's
targets and reproduced the prior reviewer's counterexample from a throwaway
script.

## What the repair claims to do

When a saved run carries NO capture artifact (`.canary.jsonl`), `check_run`
still derives the denominator from the triples journal (`*.triples.jsonl`) and
folds `coverage_known=True, capture_rows=0, intervention_rows=len(expected),
selected_rows=selected` into the NOT_MEASURED report — instead of dropping the
denominator (`coverage_known=False`, 0/0/0).

## Code read

- `check_run` (`payload_canaries.py:902-973`): the `empty = _capture_problem(...)`
  branch now, on `not captures`, calls `_expected_capture_keys(run_dir)` and, when
  it returns a non-None coverage, returns
  `replace(not_measured(empty), coverage_known=True, capture_rows=0,
  intervention_rows=len(expected), selected_rows=selected)`.
- `_expected_capture_keys` (`payload_canaries.py:863-899`): reads the single
  `*.triples.jsonl`, validates each row, adds `(case_id, repeat)` to `expected`
  iff `"I" in arms`, returns `(frozenset(expected), len(seen))`. `selected` is the
  total journal row count; `intervention_rows` is the I-arm count.
- `_capture_problem` (`payload_canaries.py:843-860`): unchanged — returns the
  "no `.canary.jsonl` artifact" sentence for `not captures`.
- `not_measured` (`payload_canaries.py:337-347`): unchanged — default
  `coverage_known=False, capture_rows=0, intervention_rows=0, selected_rows=0`.
- New test `test_zero_capture_archive_keeps_its_denominator`
  (`test_payload_canaries.py:509-532`): asserts `coverage_known`, `capture_rows==0`,
  `intervention_rows==2`, `selected_rows==2` for a 2-row journal with no capture.

## Test runs (from `prototype/`, `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python`)

| command | exit code | result |
|---|---|---|
| `python -m bench.agentpii5.test_payload_canaries` | 0 | `payload_canaries: PASS (5 границ, 5 классов)` — 20/20 checks incl. `zero_capture_archive_keeps_its_denominator` and `capture_rows_cover_every_executed_intervention` |
| `python -m bench.agentpii5.test_payload_canary_integration` | 0 | `payload_canary_integration: PASS` |
| `python -m bench.agentpii5.test_reportjson` | 0 | `reportjson: PASS` |
| `python -m bench.agentpii5.test_harness` | 0 | `harness: PASS` |

## Counterexample reproduction (throwaway `/tmp/repro_s02.py`)

### CASE1 — exact prior counterexample (450-row journal, NO `.canary.jsonl`)

Run dir with `old.triples.jsonl`, 450 rows each
`{"case_id": f"c{i:03d}", "repeat": 0, "status": "complete", "arms": {"I": {}}}`,
and no capture artifact. `pc.check_run(rd)`:

```
status='NOT_MEASURED'
coverage_known=True
capture_rows=0
intervention_rows=450
selected_rows=450
VERDICT: PASS
```

All five required assertions hold.

### CASE2 — partial capture still flags missing keys

Journal with `first`/`second` (both `complete`, I arm); only `first` capture
written. `pc.check_run(rd)`:

```
status='NOT_MEASURED' coverage_known=True capture_rows=1 intervention_rows=2
reason="capture coverage 1/2 I arms; missing [('second', 0)]; unexpected []"
VERDICT: PASS
```

The `missing`/`unexpected` path is unchanged: a single missing capture still
produces NOT_MEASURED naming the missing key.

### CASE3 — empty dir still has no denominator

Empty run dir (no journal, no capture):

```
status='NOT_MEASURED' coverage_known=False capture_rows=0 intervention_rows=0 selected_rows=0
VERDICT: PASS
```

`coverage_known=False` is correct: with no journal there is no denominator to
report, and 0/0/0 is the honest reading of an empty run.

## Verdict

**ACCEPTED_FIX** — the repair closes the prior gap exactly: the 450-row
no-capture archive now reports NOT_MEASURED with `coverage_known=True,
capture_rows=0, intervention_rows=450, selected_rows=450`, the partial-capture
path still flags missing keys, and the empty-dir case correctly retains
`coverage_known=False`. All four test modules pass with exit code 0.
