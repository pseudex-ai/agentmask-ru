# M04 candidate — adversarial review: report population and frozen oracle

- Task: `hop-report-population-review-20260927`
- Root: `/Users/igor/Projects/Obscura-hop-audit` (`pwd` first command, confirmed)
- Scope: read-only. No source/test file was modified. Scratch fixtures were written under `/tmp`.
- Reviewed: `docs/plan-hop-form-before-450.md` M04 (line 43), `prototype/bench/agentpii5/report.py`
  `frozen_score_and_observations`/`assemble`, `prototype/bench/agentpii5/frozen_oracle.py`
  `artifact_digest`/`score_observations`/`score_artifacts`, and the new tests
  `test_report_frozen.py`, `test_frozen_oracle.py`, `test_report_gate.py`.

## Verdict

**ACCEPT the M04 scoring mechanism; REJECT the versioned-digest sub-claim as stated.**

The engine-independence half of M04 holds: the published v5 lines, their axis buckets and the
digest are all produced from the saved hops without reaching `pseudex`, and a COMPLETE run scores
identically through both paths. That part may land.

The new OBS claim — that `artifact_digest` "names the population the lines were computed over"
(`frozen_oracle.py:320-339`, `FROZEN_ORACLE_VERSION = "m04-frozen-2"`) — is **false for the
corpus**. The digest folds the corpus down to its IDs (`frozen_oracle.py:342`), so a corpus whose
content changed under the same IDs moves printed totals and axis buckets while the digest stays
byte-identical. Demonstrated below with a concrete counterexample, not by prose.
Severity **HIGH for report/evidence integrity** (two different measurements share one versioned
address), **no privacy or engine-safety impact**. One blocking fix before the digest is cited as
the population address: hash the corpus content, or narrow the claim to "corpus ids + rows + hops +
witnesses".

## What was run

```
$ pwd
/Users/igor/Projects/Obscura-hop-audit

$ cd prototype && for t in test_report_frozen test_frozen_oracle test_report_gate test_reportjson test_report; do
    PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5.$t; done
test_report_frozen: PASS (6 проверок)
test_frozen_oracle: PASS (11 проверок, версия m04-frozen-2)
report --selftest: PASS / report gate: PASS  (29/29 сломанных, 6/6 мутантов)
reportjson: PASS
report: PASS (24 проверки)
```

Real saved nano (`prototype/bench/runs/2026-09-23/v5-live-nano`, 30 cases / 30 arm rows / 533 hops):

```
$ PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5.frozen_oracle bench/runs/2026-09-23/v5-live-nano
  end_to_end  37/108   overmask 30/30   consistency 16/17   stability 16/17
  form_hIN 52/106   form_hOUT 177/277   residual 301/310   ...
frozen_oracle m04-frozen-2: 30 rows, digest db18892aec2b
```

Focused answers (each reproduced, not read off prose):

1. **Printed totals and axis buckets share the saved-hop population — YES.**
   `assemble` slices `parts.half.observations` (`report.py:789`, `815`), the same tuple the frozen
   lines were scored over (`report.py:720-721`). On the real nano run: 0 reconciliation failures
   (`sum(bucket.total) == line.total` over every printable cell). On the synthetic hole fixture
   (`test_report_frozen.py:277-337`) the same holds and `side.incomplete` is set. A zero-hop
   observation was constructed (case `chain-044`, hops emptied in the corpus and its hop rows
   dropped): still 0 reconciliation failures, because observation-denominator lines are not printed
   on hop axes (`metrics.prints_on_axis`, `metrics.py:1328`; `prints_on_axis("overmask","pii_type")
   == False`).

2. **Missing/altered hops are in the digest — YES.**
   Altered one saved hop's `produced` → digest moved (`...aec2b` → different), totals unchanged.
   Dropped one hop row → digest moved and `form_hOUT 177/277→177/276`, `residual 301/310→300/309`.
   Append an *orphan* hop row (case id with no arm record) → digest and totals both unchanged; the
   row is not scored either, so this is informational, not a defect.

3. **A changed corpus with the same IDs can change the score without changing the digest — YES.**
   This is the blocking finding; see F1.

4. **Engine dependency in the frozen path — NO; one deliberate capture remains, by design.**
   Poison test passes, and `frozen_oracle.main` runs the real nano under `forbid_engine()` +
   `assert_engine_free()` and prints the lines. `bench/agentpii5` imports `pseudex` only in
   `harness.py`. The one engine touch is the run-production write
   `harness.capture_run_repairs` (`harness.py:1558-1588`, called from `finish_run`, `harness.py:1613`),
   which asks `register_spelling` once and persists witnesses as data. The v4 half
   (`report.v4_half`) still reaches the engine lazily, but it is explicitly the baseline and not
   part of the frozen claim (`report.py:725-733`).

5. **Complete-run numbers remain identical across paths — YES.**
   On the real nano run, `score_observations` (saved hops) and `score_artifacts` (re-derived via
   `observe.observe`) gave **0 line mismatches and the same digest** `db18892aec2beee5`.

## F1 — the corpus is not in the digest (HIGH, blocking the OBS claim)

`artifact_digest` (`frozen_oracle.py:320-348`) hashes four things:

```
342:  "cases": sorted(case.base.id for case in cases),     # only ids — no item, message, negative, register
343:  "rows":  [dict(row) for row in rows],
344:  "hops":  [records.hop_observation_to_json(hop) ...],
346:  "repairs": [witness.to_json() ...],
```

The lines are scored against the case objects, not against their IDs: `overmask` counts
`case.base.negatives` (`metrics.py:432-448`), `consistency`/`stability` enumerate `case.base.pii`
(`metrics.py:469-511`), the axes read `case.base.register`, `case.behaviour`,
`case.base.provenance.selection`, `case.returns`, `case.base.messages` (`metrics.py:1390-1419`).
All of that lives in `corpus.v5.json` and none of it reaches the digest beyond the id list.

Reproduction: copy the real nano run, mutate one corpus case in place (same ids), rescore
`report.frozen_score_and_observations`, compare `frozen.digest`. Exact output:

```
--- add one negative to chain-044
    digest identical: True; totals moved: 1
      overmask: (30, 30) -> (31, 31)
--- remove pii item i1 from chain-044
    digest identical: True; totals moved: 2
      consistency: (16, 17) -> (15, 16)
      stability:   (16, 17) -> (15, 16)
--- mutate case chain-044 register (same ids)
    digest same as base: True (db18892aec2b vs db18892aec2b)
    axis cells moved: 47; digest moved: False
--- mutate case chain-044 messages[1]
    digest same as base: True; axis cells moved: 12; digest moved: False
```

So: printed `overmask`, `consistency` and `stability` totals, plus 47 printed axis cells, move
against an address that `FROZEN_ORACLE_VERSION = "m04-frozen-2"` declares to name the scored
population. `test_digest_is_content_addressed` (`test_frozen_oracle.py:191-205`) mutates a **row**,
and `test_digest_covers_the_scored_hops_and_the_witness` (`:208-236`) **removes an observation**;
neither touches corpus content, so the hole is untested.

Fix (one line of substance): include the corpus content — e.g. the canonical `case_v5_to_json(case)`
per case, or the SHA-256 of `corpus.v5.json` — in the blob, or restate the docstring and version
string to say the digest covers ids + rows + hops + witnesses, not the corpus. Either closes the
false-address gap; the second only narrows the claim.

## F2 — two addresses under one oracle version (LOW)

`artifact_digest(cases, rows)` with its documented defaults (`observations=()`, `repairs=None`,
`frozen_oracle.py:320-334`) yields a different digest for the same run than the scored path:

```
default-args digest : 1fee344b3986ccce
score_artifacts     : db18892aec2beee5
same: False
```

Both carry `FROZEN_ORACLE_VERSION = m04-frozen-2`, so an artifact digest quoted out of context cannot
be told from the population-scored one. The report itself always prints the scored digest
(`report.py:911-915`), so this is a footgun for external callers, not a report defect.

## F3 — the real saved run keeps 69 LOC pairs UNMEASURED (informational)

`frozen_score_and_observations` on `v5-live-nano` returns
`repairs_measured=0, repairs_unmeasured=69`: the run predates `harness.capture_run_repairs` and has
no `repairs.json`. The report prints this honestly (`report.py:914-915`) and never converts `None`
into `False` (`frozen_oracle.repair_verdict`, `:194-202`). M04's own evidence therefore still leans
on the fixture for repair measurement; a fresh live run is needed to show the capture path in a real
run. Not a defect — a gap to name in the M04 evidence line.

## Files referenced

- `prototype/bench/agentpii5/report.py:680-722` (`frozen_score_and_observations`), `:789-849` (`assemble`)
- `prototype/bench/agentpii5/frozen_oracle.py:59`, `:194-202`, `:320-348`, `:367-417`
- `prototype/bench/agentpii5/metrics.py:1328` (`prints_on_axis`), `:1390-1419` (`by_axis`)
- `prototype/bench/agentpii5/test_report_frozen.py:277-337`, `test_frozen_oracle.py:191-236`
- `prototype/bench/agentpii5/harness.py:1558-1588`, `:1613`
- Real run: `prototype/bench/runs/2026-09-23/v5-live-nano/`

No source or test file was changed by this review.
