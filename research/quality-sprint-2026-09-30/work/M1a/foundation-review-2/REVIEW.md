# M1a v2-dev foundation — independent re-review

**Verdict: PASS_FOUNDATION.** The four reported defects are each independently
closed with no new regression found beyond the declared-open work. This accepts
the incremental foundation layer only; it is **not G2 acceptance** and does not
promote M1c, the legacy capture adapter, derived-role/initials proof, or unique
alignment.

Frozen inputs at review:

| file | sha256 |
|---|---|
| `prototype/bench/agentpii5/answer_restoration.py` | `c9050ded16823f41ee430e09bbd97649eb7559438d5c008555c3acf40f403ae2` |
| `prototype/bench/agentpii5/test_answer_restoration.py` | `024e494e46a588815a303b2d3d922b1cdc2df5590e6713dd9e094ce690e6b087` |

Only these two files differ from the B0 source pins (196 other source/run pins
unchanged, including the 17 paid raw-run files). No engine/scorer/corpus change.

## Method

- Reran the frozen M04 evidence-control suite read-only:
  `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python -m bench.agentpii5.test_answer_restoration`
  → **55/55 pass, exit 0**.
- Wrote and ran an independent probe module
  `foundation-review-2/probe_fixes.py` (12 assertions, `ALL_PASS`, exit 0),
  deliberately constructing counterexamples distinct from the parent's own
  added checks.
- Confirmed legacy regression suites (`test_metrics`, `test_fixtures`,
  `test_form`, `test_observe`, `test_hop_report`, `test_live`) all exit 0.
- Confirmed `git diff 0bfda236 -- prototype/pseudex prototype/licensing` is
  empty.

## The four defects, independently verified

| # | Defect | Fix | Independent confirmation |
|---|---|---|---|
| 1 | Exact copy judged by first-available alias canonical; a silent homoglyph repair passed as value | `exact_copy = len(literal_choices)==1`, value vs that single literal | homoglyph source `8(916)4О2-11-87` delivered repaired `8(916)402-11-87` → `joint_ok==0`; exact literal delivery → `value_ok==1`; unrelated canonical alias cannot license a bare-fake renotation (`joint_ok==0`); unchanged fake still residual |
| 2 | `call_requests`/`available_results` accepted bool/float/missing ordinals | whole-int, strictly-monotone request ordinals; `call_requests` length==calls and each names an existing int request; `available_results` whole int 0..len(calls) | bool, float, and unknown-request cases all raise `ValueError`; a valid tool call with a real mapped request is accepted |
| 3 | Tool piece `engine_type` was ignored; `NOT_A_TYPE` accepted | piece type must equal `item.type` | `NOT_A_TYPE` piece on a PHONE item raises `ValueError` |
| 4 | A future disclosure erased an unknown legacy competitor on another identity | future proof yields an `unknown` mapping, not a dropped candidate | p1 proved at request1 + p2 same-fake only future proof → `joint_ok==0`, candidate retained, unresolved ≥1 |

## Not re-introduced / still open (correctly)

- Renotation (`+7 999 000-11-22` → `+7 916 402-11-87`) still earns joint via the
  value path, distinct from exact-copy; the exact-copy branch only activates when
  exactly one proved literal matches the raw fake.
- The foundation still requires, and does not claim: (a) a legacy capture adapter
  that derives `DisclosureProof` from actual linked captures (never
  `zip(push, response)`), (b) derived role/initials proof beyond the visible
  `unknown` candidate, (c) unique monotone alignment replacing the dev
  `SequenceMatcher` heuristic, (d) per-span form abstention coverage.
- `answer_real`, shared `values_equal`, engine, scorer, and raw runs are
  unchanged.

## Boundary

PASS_FOUNDATION is a review of an incremental, still-incomplete metric layer.
G2 remains FAIL. M1c wiring and publication of any answer-restoration quality
rate stay blocked until the declared-open items are finished and independently
accepted on a frozen revision.
