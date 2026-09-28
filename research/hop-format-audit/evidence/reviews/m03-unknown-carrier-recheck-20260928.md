# M03 unknown-carrier recheck — independent READ-ONLY acceptance review

- Task: `hop-m03-unknown-carrier-review-20260928`
- Root: `/Users/igor/Projects/Obscura-hop-audit` (`pwd`/`date` first commands; no other root used)
- Reviewer is **not** the author. Scope: **read-only**. No source, test, corpus, saved run or historical
  report was created, modified or deleted. No child agents/sessions, no network, no provider call,
  no paid 450. Scratch was heredoc-only; no files written anywhere. The **only** file created is this one.
  Concurrent work on `prototype/pseudex/envelope.py` (another DeepSeek writer) was neither touched nor
  attributed to M03.

## Verdict

| Row | Verdict | One line |
|---|---|---|
| **M03** (`m03-causal-hops-v2`) | **PASS** (candidate; formal acceptance is Codex's) | The module contract rule 3 is now executed first; independently reproduced exactly **208 `attributed` + 98 `ambiguous` → `not_identifiable`** on the real saved 450, with no optimistic branch left open; the answer leg stays honestly `0/450` measured. Four non-blocking caveats below. |

## 1. What was run

```
$ cd prototype
$ for t in test_causal_hops test_actual_hops test_response_trace test_hop_report test_records; do
    PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5.$t; done
causal_hops: PASS (estimator=m03-causal-hops-v2)
actual_hops: PASS   response_trace: PASS   hop_report: PASS   records: PASS   (exit 0 each)
$ PYTHONDONTWRITEBYTECODE=1 python3 wiki/check.py     # 2 findings, both pre-existing/envelope, none M03
```

No review check reused an author test: every fixture below was built from the fixture *builders*
(`fixtures.py`) by this review, and the 450 numbers were recomputed with a re-implemented **v1** branch
order to measure the movement independently.

## 2. The fix, read in the code

`causal_hops.py` branch order is now rule 3 first (`:322-329` **unknown → `not_identifiable`**, before
`len(available)>1 → ambiguous` `:330-334`, `available and user → ambiguous` `:335-338`, and
`available → attributed` `:339-349`). The evidence line names the unprovable carrier *and* any proved
one (`:323-329`) and the v1 false phrase «no other carrier is available» is gone. `ESTIMATOR_VERSION`
is bumped to `m03-causal-hops-v2` (`:114`) with the denominator movement recorded in the comment.

## 3. Independent counterexample matrix (not the author's checks)

| # | Case | Expected | Measured |
|---|---|---|---|
| A | 1 proved carrier + 1 unprovable same-turn carrier, archived | `not_identifiable` | `not_identifiable`, cand `(0,1)`, source `-1` |
| B | 2 proved carriers + 1 unprovable | `not_identifiable` (v1 was `ambiguous`) | `not_identifiable`, cand `(0,1,2)` |
| C | user copy + 1 unprovable carrier | `not_identifiable` | `not_identifiable` |
| D | all carriers proved **later** | `unattributed` | `unattributed` |
| E | future result (belongs to a later call) | `False` / `unattributed` | `result_available=False`, `unattributed` |
| F | two calls of ONE response, with trace | `False` / `unattributed` | `False`, `unattributed` |
| G | two proved carriers for one item | `ambiguous` | `ambiguous` |
| G2 | one proved carrier on the run's first result | `attributed`/`first_result` | `attributed`, seq 0, `first_result` |
| H1 | reply answer **with** a real trace | `attributed` | `attributed`, seq 0 |
| H2 | the SAME reply **without** a trace | `not_identifiable` | `not_identifiable` |
| I | user copy + 1 proved + 1 unprovable | `not_identifiable` | `not_identifiable`, cand `(0,1)` |
| J | user-only datum, no result | `user_provided` | `user_provided`, `source_kind=user` |
| K | no carrier at all, not user | `unattributed` | `unattributed` |

Note on C: a result produced by the consumer's **own** call is proved `False`
(`result_index >= call_index`, `:232-235`), so a same-call "carrier" is unavailable, never unknown — the
unknown case needs an earlier call of the *same turn*. The matrix was corrected for this and re-run.

**Mutation probes** (recomputing events after the patch, not before):
unknown→available on a 40-run sample moved `attributed 148→254`, `ambiguous 54→151`,
`not_identifiable 203→0`; the v1 branch order reproduced the full-450 table in §4 exactly. The estimator
responds to the mutation it is claimed to guard.

## 4. The saved 450, recomputed in memory (nothing written)

`compose_cohort` over the four saved dirs; fingerprint **`6c2a6d6978f9ec061e85c739b6bb3bb5b666c15118a6931096ef0866f8cf622c`**
(same population as `m01-m03-actual-event-20260927.md`), **450 triples**, **7878 events**,
**runs with `model_trace`: 0 / 450** — the archive claim is exact.

My re-implementation of the pre-fix v1 order reproduces the original REJECT table to the row
(`tool_arg` 571/246/274/280/1136, `summary` 84/101/77/2/258, `template` 4/12/3/0/24,
`chain` 659/359/354/282/1418, `answer` 0/845/1/888), which makes the measured v1→v2 delta trustworthy:

```
transitions v1 -> v2 (every non-zero transition, full 450):
   attributed -> not_identifiable : 208     ambiguous -> not_identifiable : 98
   (no other transition; user_provided, unattributed and the whole answer line unchanged)
```

v2 surface table (all counts; `not_id` = `not_identifiable`):

| surface | cand | tool_causal | attr | first | later | amb | unattr | not_id | user |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| answer | 1734 | 846 | **0** | 0 | 0 | 0 | 1 | 845 | 888 |
| tool_arg | 2507 | 1371 | 495 | 228 | 267 | 213 | 280 | 383 | 1136 |
| summary | 522 | 264 | 58 | 22 | 36 | 85 | 2 | 119 | 258 |
| template | 43 | 19 | 2 | 1 | 1 | 12 | 0 | 5 | 24 |
| chain | 3072 | 1654 | 555 | 251 | 304 | 310 | 282 | 507 | 1418 |

The 208 is the prior review's per-surface impact (tool_arg 76 + summary 26 + template 2 + chain 104 =
104 owner rows and their 104 `chain` twins). **Aggregate denominators validated:** on every line
`sum(statuses)==candidates`, `tool_causal==sum(TOOL_CAUSAL_STATUSES)`, and
`value/form/form_unmeasured/residual/joint ≤ attributed` — zero violations.

## 5. Evidence wording and `candidate_seqs` audit (450)

- v2 `not_identifiable` events whose evidence still says «no other carrier is available»: **0**.
- v2 `attributed` events whose evidence lacks «no unprovable carrier»: **0**.
- `not_identifiable` `candidate_seqs == available ∪ unknown`: **0 mismatches** (all 1859).
- The answer line prints `0` attributed and `845` `not_identifiable` and **no percentage**; the saved
  `<run>.report.txt` / `<run>.public.json` contain **zero** `causal`/`not_identifiable` lines (archive
  mtimes Sep 26, untouched), and `causal_hops` is imported only by `hop_report.py` (the separate
  `hop-report` command) — **no answer rate is claimed on the old archive and none reaches a public
  report.** `hop_report.py:103-111` labels the causal section as recorded-chronology, and
  `:144-154` lists the honesty limitations, including same-turn unidentifiability.
- Forward path: `test_response_trace.forward_answer_leg` runs the **real `GatewayV5` + real
  `GatewayHooks` + real `records` round-trip** (provider mocked only at `responses.create`), and shows
  `attributed/1` for the seeded answer item and `not_identifiable` for the same run with the trace
  removed. That is the "local real forward trace" — a mechanism proof, not a live rate; the test's own
  docstring says so, and §4 confirms 0/450 real traces.

## 6. Non-blocking caveats (named, not waived)

1. **`candidate_seqs` docstring overstates** (`causal_hops.py:410-411`: "every recorded carrier the
   binding looked at"). For `not_identifiable` it omits carriers proved *later* (**690** of 1859 events
   on the 450), and for `unattributed` it is `()` even when later carriers exist. The `evidence` string
   still names them, so no decision is unauditable — a wording/consistency nit, not optimism.
2. **`by_owner` is not a partition.** `_acting_events` emits the owner event *and* its `chain` twin with
   the same owner (`:512-515`), so `by_owner.tool_arg`=5014 = 2507 surface + 2507 chain. No effect on
   statuses or on any published rate; a reader could misread the column as disjoint.
3. **`_answer_response` last-resort fallback** (`:198-201`) picks the LAST response and is explicitly
   optimistic; it is documented as such (`:186-189`) and **no real run exercises it** (0/450 traces).
   Reachable only if no response `raw` carries the substitute and none equals the reply.
4. **Archive `attributed` never uses a response boundary.** Without a trace, availability is inferred
   from turn order (earlier turn `True`, same turn `None`, later turn `False`, `:242-252`). That is sound
   and conservative and is the module's declared model, but it means the 495/58/2/555 attributed rows
   rest on turn order, not on a recorded chronology.

## 7. Reproducibility

Commands are in §1 and §4; the population is the four saved dirs
`/private/tmp/v5-quarter-deepseek-{nojudge-clean,missing-20260926-r2,remaining,final3}-20260926`
(fingerprint above). `wiki/check.py` is RED with **2** findings about `prototype/pseudex/envelope.py` ↔
`detect` (`wiki/MAP.md:80,270`) — the concurrent envelope writer's surface, **not** M03; `causal_hops`
is not a wiki-mapped module and no M03 wiki row was expected or changed. `git status --porcelain` is
unchanged by this review (63 pre-existing entries; this review file was the only new path).

No source or test file was changed. Formal acceptance is Codex's call.
