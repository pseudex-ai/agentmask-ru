# M04 digest repair — independent adversarial recheck

- Task: `hop-report-population-recheck-20260927`
- Root: `/Users/igor/Projects/Obscura-hop-audit` (`pwd` run first, matched exactly; no abort)
- Scope: read-only. No source or test file was touched, no child agents, no network, no live
  model call. Scratch probes were written under `/tmp/m04recheck/` only.
- Candidate reviewed: `prototype/bench/agentpii5/frozen_oracle.py` (untracked, current tree,
  `FROZEN_ORACLE_VERSION = "m04-frozen-3"`), `prototype/bench/agentpii5/test_frozen_oracle.py`,
  the public scored-hop path in `prototype/bench/agentpii5/report.py`
  (`frozen_score_and_observations`, `read_parts`, `assemble`, `axis_cells`), against the original
  finding `research/hop-format-audit/evidence/reviews/m04-report-population-20260927.md`.
- I did not adopt the author's desired verdict. Everything below was re-derived from the running
  code; the verdict follows the measurements.

## Verdict

**PASS — the F1 false-address defect is closed for every file-reachable population, and the
`m04-frozen-3` digest may be cited as the address of the scored population.**

I reproduced the original counterexample class exactly: same-ID corpus edits that move printed
totals and axis cells now move the digest, while the old id-only formula sat still on the same
edits. No counterexample was found in which two *file-reachable* artifacts share one digest while
scoring different populations. Four residual issues remain and none blocks the claim (three LOW,
one INFO); they are stated with their reproductions in §4.

What would flip this to REJECT: a digest that stays byte-identical while a printed line or axis
cell moves on artifacts read from a run directory. I looked for it in the corpus half, the hop
half, the rows half, the witness half, subsets, duplicates, reorder and three hash seeds, and did
not find one.

## 1. Commands run

```
$ pwd
/Users/igor/Projects/Obscura-hop-audit

$ cd prototype && PYTHONPATH=. .venv/bin/python3 /tmp/m04recheck/probe.py     # same-ID edits, axes, hole
$ cd prototype && PYTHONPATH=. .venv/bin/python3 /tmp/m04recheck/probe2.py    # round-trip, seeds, types
$ cd prototype && PYTHONPATH=. .venv/bin/python3 /tmp/m04recheck/probe3.py    # old-vs-new address, engine-free
$ cd prototype && for t in test_frozen_oracle test_report_frozen test_report_gate test_reportjson test_report; \
    do PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5.$t; done
  test_frozen_oracle: PASS (14 проверок, версия m04-frozen-3)
  test_report_frozen: PASS (6 проверок)
  report --selftest: PASS / report gate: PASS (мутантов отказано: 6 из 6)
  reportjson: PASS
  report: PASS
```

The instrument used throughout is the real saved run
`prototype/bench/runs/2026-09-23/v5-live-nano` (30 cases, 30 arm rows, 533 hop rows), read
through the public `report.frozen_score_and_observations` unless a probe says otherwise.

## 2. The F1 repair, independently reproduced

### 2.1 Same-ID corpus edits move the digest, the printed totals and the axis cells

Each row is a copy of the real run with exactly one `chain-044` field edited in
`corpus.v5.json`, all ids byte-identical (verified in the probe). "cells moved" counts differing
`(metric, axis, bucket)` cells over the 1323 printable cells that `report.axis_cells` publishes.

```
base                       digest 9d597ffc2a2d
negatives += first         digest 57af5c1aa9e3  overmask 30/30->31/31   4 cells moved
pii[0].value/canonical +X  digest e281b379df53  totals unchanged        0 cells moved
register -> clean          digest 2239830f684d  totals unchanged       47 cells moved
messages[1].content + "!"  digest bbc819b85e03  totals unchanged        0 cells moved
behaviour -> single        digest 343d1bb0d57a  totals unchanged       36 cells moved
provenance.selection flip  digest b79e5fdbd492  totals unchanged       36 cells moved
returns[0].ids + entry     digest 524f897cb5d7  totals unchanged        0 cells moved
```

Every one of the seven is an address change; the three that move no number simply show the
address is finer than the claim needs, which is safe. The first, third, fifth and sixth are the
original F1 hazard exactly: a printed total or axis cells move under unchanged ids.

### 2.2 The old address was blind to those same edits (the hazard was real, and is gone)

Re-implementing the pre-fix formula (`"cases": sorted(case.base.id ...)` plus rows/hops/witnesses,
identical canonicalisation) on the same three mutations:

```
OLD id-only digest db18892aec2b   NEW 9d597ffc2a2d
  negatives: old moved=False  new moved=True
  register:  old moved=False  new moved=True
  behaviour: old moved=False  new moved=True
```

`db18892aec2b` is the value the original review reported for `m04-frozen-2`; the new digest differs
only because the corpus-content half and the version string changed, not because a line moved
(§3.1). `corpus_content` (`frozen_oracle.py:354-370`) routes every case through
`schema.case_v5_to_json`, and `CaseV5`/`Case` serialise **all** their fields (`schema.py:891-911`;
v4 `Case.to_json = asdict(self)`, `bench/agentpii4/schema.py:199-200`), so `negatives`, `pii`,
`register`, `messages`, `behaviour`, `returns` and `provenance.selection` — the fields
`overmask`, `consistency`/`stability`, and `metrics.by_axis` read — are all in the address.

### 2.3 Determinism and completeness

```
reorder corpus (reversed)          digest stable, lines stable
PYTHONHASHSEED in {0, 1, 12345}    one digest for the real run (3/3 identical)
score_artifacts vs report path     digest equal, lines equal (complete run)
533 saved hops, to_json/from_json  0 not equal after round trip
```

The sort in `corpus_content` is by each case's serialised bytes (not by id), so a duplicated id
cannot tie; `_jsonable` (`:336-351`) turns `set`/`frozenset` into a sorted list before
`_canonical_json` (`:328-333`), which is what makes the three hash seeds agree.

### 2.4 Complete saved run: counts unchanged, digest re-anchored

Frozen lines on the real run vs the values the previous review measured under `m04-frozen-2` and
the values in the run's own `*.report.txt` (`bench/runs/2026-09-23/v5-live-nano`):

```
end_to_end 37/108   overmask 30/30   consistency 16/17   stability 16/17
form_hIN 52/106     form_hOUT 177/277   residual 301/310   30 rows
report.txt agrees:  end_to_end 37/108 · overmask 30/30 · residual 301/310
```

Only the digest moved (`db18892aec2b…` → `9d597ffc2a2d…`), which is the intended re-anchoring of a
versioned address to a strictly larger population; no published number changed.

### 2.5 Missing-hop population coherence

Removing `chain-044`'s 28 saved hop rows from a copy of the real run:

```
dropped 28 hop rows -> hopless ('chain-044|0',), digest moved, 134 axis cells moved
reconciliation failures: 0  (sum(bucket.total) == line.total over all 1323 cells)
line moves: end_to_end 37/108->36/107, leak 106/106->103/103, coverage 105/106->102/103,
            form_hOUT 177/277->161/259, residual 301/310->283/291, overmask 30/30->29/29, ...
```

The hole is named (`half.hopless`), `assemble` folds it into `incomplete` via `excluded`, and the
lines, the cells and the digest all move together — the population a reader sees, the slices, and
the address are the same population. `test_report_frozen` (6 checks) passes and holds the
`assemble`-level version of this.

### 2.6 Repair table, subsets

```
69 LOC pairs: digest moved when the frozen table replaced the empty one, lines stable,
              measured 69 / unmeasured 0
subset of observations (29 of 30): digest moved
engine-free: report.frozen_score_and_observations inside forbid_engine()+assert_engine_free()
             returns the same digest and residual 301/310
```

`bench/agentpii5` still imports `pseudex` only in `harness.py` (the run-production capture,
`harness.py:93-99`, `:1580-1581`); scoring files import none. `frozen_oracle.main` on the real run
runs under the firewall, and `test_frozen_oracle` proves the firewall can go red (14/14 checks,
version `m04-frozen-3`).

## 3. Test coverage of the fixed hole

- `test_digest_moves_when_corpus_content_moves_under_the_same_ids` (`test_frozen_oracle.py:285-323`)
  now exists, drives four id-preserving edits, and additionally demands that at least one of them
  move a printed line — so the check cannot pass vacuously. This is the hole the original review
  found untested (the two pre-existing digest checks, `test_frozen_oracle.py:199-213` and
  `:216-252`, only mutate a row and drop an observation — neither touches corpus content).
- `test_artifact_digest_demands_an_explicit_population` (`:371-398`) closes F2: `artifact_digest(cases, rows)`
  is now a `TypeError`, and an explicitly hop-free population gets a different address.
- F3 from the original review is unchanged and still honest: the real nano run has no
  `repairs.json`, so `repairs_measured=0, repairs_unmeasured=69`, printed as «не измерено».

## 4. Residual findings (none blocks the claim; no REJECT)

**L1 — `score_observations` can hash a corpus the lines were not scored over. LOW (API misuse).**
`score_observations(observations, cases, rows, repairs)` computes the lines from
`metrics(observations)` — each observation carries its own `case` — but hashes the separate `cases`
argument (`frozen_oracle.py:443-453`). Repro:

```
obs = real run's observations; cases' = corpus with chain-044.negatives += 1
score_observations(obs, cases', rows, RepairTable())
  -> digest moved (base 9d597ffc -> ...), overmask stayed 30/30
```

A caller that passes a corpus inconsistent with its observations mints an address that names a
population it did not score. Not reachable through the public path: `frozen_score_and_observations`
builds both from the same `v5_corpus(dir)` (`report.py:680-722`), and `score_artifacts` derives the
observations from `cases` itself. Cheap hardening: assert the observation corpus and the `cases`
argument agree, or hash the cases off the observations.

**L2 — the address is over-strict where the scorer is order/duplicate-insensitive. LOW/INFO.**
Two artifacts that score identically can still carry two addresses:
* repair witnesses reordered — `RepairTable.by_key` is a dict, so verdicts and counts are identical,
  yet `digest_stable=False` in my run. `repairs.json` is written in pair order and read as-is, so a
  hand-sorted table re-addresses the same scoring semantics.
* duplicate / conflicting corpus ids — appending a byte-identical copy of `chain-044` moved the
  digest while lines and all 1323 cells stayed identical; appending a copy with one extra negative
  moved the digest and silently selected the LAST duplicate for scoring (`overmask 31/31`,
  `cases=31`, observations 30). `schema.validate` rejects duplicates as K01 and the report prints
  them in the waste table, so this is malformed-corpus territory, not a false-address hazard (the
  digest is a superset of what was scored, never a subset).
This direction is the mirror of F2 — one population under two addresses — and is harmless for
integrity (it cannot make two populations share one address); worth a doc line, not a fix.

**L3 — `default=str` and the set→sorted-list normalisation are not injective. INFO (unreachable from
run files).** `_canonical_json(..., default=str)` and `_jsonable` map some distinct in-memory values
to one blob, and `str()` of a plain object embeds its address:

```
row[0]["probe_extra"] = object(); new object; new object ->
    two calls in one process -> different digests (address in str)   # nondeterministic address
row[0]["probe_extra"] = {"a","b",...} vs sorted(list) -> SAME digest
unsorted list vs set -> different digest
```

Every artifact that actually reaches the scorer is JSON (corpus file, arms/hops JSONL, witness
JSON), and all 533 saved hops round-trip `to_json`/`from_json` exactly, so no file-reachable
counterexample exists. It is the documented footgun class of F2, now confined to hand-built
arguments.

**L4 — no false-address in the repairs half or the hop half.** A table with a dead witness for a
pair the run never produced moves the digest without moving any verdict (over-strict, same class as
L2); conversely the witness content is in the blob, so a flipped verdict cannot hide. The hop half
is injective on the 533 saved hops (round-trip verified), so the population half of the digest is
faithful.

## 5. Severity summary

| item | verdict | severity |
|---|---|---|
| F1 corpus content not in the address | **closed**, independently reproduced with the old formula as control | — |
| F2 defaults minting a second address | **closed** (`artifact_digest` population required, `TypeError` pinned) | — |
| L1 cases/observations mismatch in the raw API | open, not reachable via `report`/`score_artifacts` | LOW |
| L2 order/duplicate over-strictness (two addresses, one population) | open, mirror of F2 | LOW/INFO |
| L3 `default=str` / set normalisation | open, unreachable from files | INFO |
| F3 real run measures 0/69 repairs | unchanged, printed honestly | INFO |

No privacy, engine-safety or published-number impact in any of the above.

## Files referenced

- `prototype/bench/agentpii5/frozen_oracle.py:67`, `:328-351`, `:354-370`, `:373-406`, `:425-455`
- `prototype/bench/agentpii5/report.py:680-722`, `:765-778`, `:781-849`
- `prototype/bench/agentpii5/schema.py:891-911`; `prototype/bench/agentpii4/schema.py:181-200`
- `prototype/bench/agentpii5/test_frozen_oracle.py:285-323`, `:326-368`, `:371-398`
- `prototype/bench/agentpii5/metrics.py` (`by_axis`), `bench/agentpii5/harness.py:93-99`, `:1580-1581`
- Real run: `prototype/bench/runs/2026-09-23/v5-live-nano/` (no `repairs.json`)
- Scratch probes: `/tmp/m04recheck/probe.py`, `probe2.py`, `probe3.py`

No source or test file was changed by this review. The only file written inside the repository is
this review.
