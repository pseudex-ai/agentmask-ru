# M02 v9 leak-side repair — second independent read-only recheck

Reviewer: DSH main agent (DeepSeek Flash), session
`hop-m02-leak-side-recheck-20260928`. **NOT the author.** Read-only on source,
tests, wiki and the saved corpus; this file is the only artefact written.
Date: 2026-09-28. No network, no provider, no paid 450, no child sessions, no
workflow/ralph. Candidate: `prototype/bench/agentpii5/actual_hops.py`,
estimator `m0-actual-out-v9` (working tree, uncommitted;
`sha256=53af8349e11cf8b66d23121a1b0ac68f2d9e863d2eca4840edd250ffd00e4671`,
pinned in the fresh run's `report.json`).
Baselines: `m0-actual-out-v8` (`/private/tmp/hop-m02-v8-ind-20260928`, the v8
review's run) and accepted `m0-actual-out-v7`
(`/private/tmp/hop-sprint-m03-v7-20260927`). Same cohort fingerprint
`6c2a6d69…fcf622c`, 450 complete triples, 11565 actual leaves on all three.

## Verdict

| Row | Verdict | One line |
|---|---|---|
| **M02** | **REJECT** | Both named v8 defects are genuinely fixed and the wrong-person `unmasked_known` is gone, but the repair moved a **confirmed restored-side fake out of the residual metric**: `residual 235 → 213` is exactly the 20 `residual → ambiguous` plus 11 `residual → not_identifiable` minus 9 `unattributed → residual`, and at least one of those leaves carries a byte-identical standing fake yet is now reported `ambiguous` with `residual=False`. The unresolved status is not an equivalent flag: `_unresolved()` is hard-wired to `residual=False`. |

The architectural contradiction, stated plainly: **`residual` is not measured on
the token, it is derived from a single chosen entity, and the entity chooser is
allowed to refuse.** When it refuses (`ambiguous`) the answer to "is a fake
still standing in the restored text" is discarded rather than reported. The
sprint bars trading residual privacy coverage for attribution ambiguity, and
v9 does exactly that trade.

## 1. What was run (all commands local, reproducible)

```
cd prototype && source .venv/bin/activate
python3 -m bench.agentpii5.test_actual_hops            # 38/38 PASS, exit 0
python3 -m bench.agentpii5.hop_report \
  --source A=/private/tmp/v5-quarter-deepseek-nojudge-clean-20260926 \
  --source B=/private/tmp/v5-quarter-deepseek-missing-20260926-r2 \
  --source C=/private/tmp/v5-quarter-deepseek-remaining-20260926 \
  --source D=/private/tmp/v5-quarter-deepseek-final3-20260926 \
  --out /private/tmp/hop-m02-v9-ind-20260928
# -> 450 complete triples; 11565 actual leaves; estimator=m0-actual-out-v9
python3 /private/tmp/m02_v9_indep_check.py             # reviewer fixtures
python3 /private/tmp/m02_v9_forensics.py               # per-moved-leaf re-derivation
python3 /private/tmp/m02_mutate.py {noturn|noguard} <out>   # mutation guards
```

The reviewer fixtures are built from the repository's own builders
(`_item`/`_case`/`_call`/`_run`/`_with_*`) and `actual_events`; no author test
expression was copied. The v8/v7 comparisons use their frozen `events.jsonl`
keyed by `(case_id, repeat, call_seq, path)`; the v9 side is the fresh run above.
`actual_hops.py` was never modified (the mutation harness rewrites and restores
it; `diff` against the backup is clean after every run and the hash in
`report.json` equals the current file).

## 2. Author claims that hold (independently reproduced)

* **F1 fixed.** `_owned_by_substitute` is asked with the current call's
  `call_turn`/`call_seq` (`actual_hops.py:809`), and `_fragment_owned_by_another`
  too (`:939`). My fixture, call turn 3, A's fake disclosed at message 0 vs 1:

  ```
  msg=0   restored:   p1  value_wrong   residual=False   cand=('p1',)
  msg=0   unrestored: p1  residual      residual=True
  msg=1   restored:   p1  value_wrong   residual=False
  msg=1   unrestored: p1  residual      residual=True
  _owned_by_substitute(turn=3,seq=3)=('p1',)   (turn=0,seq=0)=()
  ```

  Availability invariance holds; the wrong-person charge is gone; the role leaf
  (`contact.last_name`) keeps naming A (`mixed p1`) in both variants.
* **F2 fixed and reachable.** `_written_has_substitute` returns `True` through
  the narrowed-exemption branch (`carries_any` case-wide `True`, own-only
  `True` → answer `True`); the restored leaf is credited to A, not left
  `unattributed`.
* **Residual is `True` on the unrestored variant** on A, status `residual`, and
  no wrong-person `unmasked_known` anywhere in the msg 0/1 matrix.
* **A genuinely future mention is not borrowed**: msg=4 and no-mention give the
  same verdict, and neither charges A.
* **Two people, one fake surname** stay `ambiguous`; **old/new versions** stay
  distinct (`value_wrong p9`, never the new version on the old fake); ordinary
  short numbers keep their controls.
* **38/38 focused checks green** (`test_actual_hops`: PASS, exit 0).
* **Mutation guards are load-bearing, measured independently** (my mutations on
  the current tree, frozen 450):

  | tree | residual | matched | unmasked_known |
  |---|---:|---:|---:|
  | v9 as written | 213 | 3515 | 8 |
  | F2 guard reverted (`carries_any` read backwards) | 464 | 3209 | 8 |
  | F1 bound reverted to `(0, 0)` | 214 | 3515 | 8 |

  Reverting the F2 guard alone destroys 306 matches into `ambiguous` and adds
  251 spurious residuals; reverting F1 alone moves 6 `not_identifiable` back to
  `value_wrong` and 1 `ambiguous` to `residual`. Both guards carry weight. (A
  mutation reverting BOTH does **not** reproduce the v8 artifact — residual 158,
  `ambiguous` 5736 — so v9 is not the v8 tree plus these two guards; the
  docstring's "v9 vs v8" comment under-describes the diff. Bookkeeping, disclosed
  here so no reader infers a two-line change.)
* **No false pass**: of all 83 moved leaves, zero became `matched`/`value_wrong`
  out of `ambiguous`/`unattributed`/`not_identifiable`/`residual`-as-real, and no
  new `unmasked_known` (`v7 11 → v9 8`; all 8 are `written == restored`).
* **Event identities carry no turn** (`event_id = seq|field|item`) and the
  version bump is consistent (`ESTIMATOR_VERSION = "m0-actual-out-v9"`, printed
  in `summary.md` and `report.json`).

## 3. The blocking finding: `residual` is dropped when the entity choice refuses

Count arithmetic, recomputed in memory from the three frozen `events.jsonl`
(identical to their `report.json`):

| quantity | v7 | v8 | v9 |
|---|---:|---:|---:|
| candidates | 6462 | 6462 | 6465 |
| matched | 3519 | 3521 | 3515 |
| value_wrong | 130 | 131 | 119 |
| unmasked_known | 11 | 8 | 8 |
| **residual** | **235** | **235** | **213** |
| ambiguous | 1184 | 1184 | 1209 |
| not_identifiable | 668 | 668 | 716 |
| unattributed | 712 | 715 | 685 |
| residual/candidates | 3.637% | 3.637% | **3.295%** |

The 22-row drop is exactly the move set (raw rows, no reinterpretation):

```
residual -> ambiguous          20
residual -> not_identifiable   11
unattributed -> residual        9        => 235 - 31 + 9 = 213
```

For **every** one of those 31 leaves the engine wrote a substitute street and the
restored text still carries that same substitute street; 30 of them differ only
in the house/flat the other address version carries. Raw examples:

```
tool_chain-002 c9  query  W='Красноярск Берёзовая 31 квартира 147'
                          R='Красноярск Берёзовая 54 квартира 189'      resid T -> ambiguous
tool_chain-038 c4  query  W='Мятная улица 5 Курск'
                          R='Мятная улица 1 Курск'                     resid T -> not_identifiable
```

**The exact counterexample — a confirmed standing restored-side fake, reclassified:**

```
tool_chain-009  repeat 0  call_seq 15  turn 2  path 'query'
  v8: status=residual        item='i7' residual=True   candidates=('i7',)
      evidence: "the written leaf carries item i7's substitute (one entity)"
  v9: status=ambiguous       item=''   residual=False  candidates=('i7','i8')
      evidence: "2 entities (p9.dir|LOC|лермонтова|street=лермонтова,
                 p9.home|LOC|лермонтова|city=орел|flat=150|house=120|street=лермонтова|street_type=проезд)"
  written : 'Орёл Пихтовая 168к54'
  restored: 'Орёл Пихтовая 168к54'      <-- byte-identical: NOTHING was restored
  expected: 'лермонтова'
  available surfaces: i7 = ('пихтовая',)   i8 = ('г Орёл, ул Ольховая, д 163',)
```

The engine's substitute `Пихтовая` (real street `лермонтова`) survived into the
tool's restored input — a textbook residual leak — and the whole value was
returned unchanged. In v9 the leaf is `ambiguous` and **`residual=False`**.

Why: `_unresolved()` (`actual_hops.py:478-483`) hard-codes `residual=False` for
`ambiguous`, `not_identifiable` and `unattributed`. Here two candidate records of
one person render the written text (`i7` via its street substitute `Пихтовая`,
`i8` via the generic city token `Орёл` contained in its full-address surface), so
`_one_entity` refuses, `_decide` returns at `:603-604` **before `_restoration`
is ever reached**, and the standing fake is never tested. The leak question was
answerable; the identity question was not; v9 reports the identity answer and
discards the leak answer.

Denominator effect (the sprint's bar, measured):

* `residual` fell 235 → 213 (−9.4%) and `residual/candidates` fell 3.637% →
  3.295%, i.e. the report reads as a privacy improvement while the set of
  leaves holding a standing fake is unchanged.
* `attributed` fell 3895 → 3871 — 24 previously attributed leaves left the
  attributed denominator entirely, and `joint_ok` 3178 → 3174.
* Unresolved (`ambiguous` + `not_identifiable`) grew 1852 → 1925. On a
  conservative probe of that bucket, **652 leaves have at least one available
  substitute that renders BOTH the written and the restored text**, i.e. a
  standing fake the estimator does not flag as residual; **509 of them are
  refused by more than one candidate**, which is the mechanism above. (The probe
  is an upper bound — a whole-address surface can legitimately contain a city
  token — so 652 is a bound, not a confirmed count; the `tool_chain-009` row and
  the 31 raw rows are confirmed by hand.)
* The other side of the trade is real but smaller: the 9 `unattributed →
  residual` gains are genuine recovered failures (e.g. `tool_chain-005 c12`
  W `…Барбарисовая…` → R `…Осиновая…`, `residual i8`) and one v7
  `unmasked_known → residual` (`tool_chain-034 c9`) is the correct diagnosis.
  v9 is, row for row, more honest about *who*; it is less complete about
  *whether*. Those are different metrics and one may not be spent on the other.

## 4. Root cause and what a repair would need (not done here)

The residual decision is computed inside `_restoration`, which runs only for a
chosen entity. `residual` is a property of the token and the restored text — the
test in `_written_has_substitute(...restored...)` needs no identity at all —
while the entity is needed for the `item_id` charge and for the value/form
columns. Conflating them means every entity refusal silently deletes a leak
finding. The honest shape is "confirm the leak, then name its owner or leave the
owner empty" (`residual` with `item_id=''` and the candidate set), not
"owner unknown, so no leak". A secondary contributor is that
`_available_surfaces`/`_written_has_substitute` accept a full-address surface
whose generic tokens (the city) light up on any address, which manufactures the
multi-candidate refusal in the first place; that is why `i8` competes with `i7`
on a leaf that is unambiguously `i7`'s street substitute.

## 5. Controls that do hold, and acceptable limitations

* No wrong-person charge survives: `pb` is never charged on A's available fake
  (msg 0/1), and the role leaf stays on A.
* No `matched` is bought by the collision; no residual was lost on a leaf that
  carried a real value (forensics: `real_owners` empty for all residual-losing
  rows).
* `unmasked_known` is strictly down (11 → 8) and every remaining row is a true
  real-value pass-through; `mixed` is 0 on all three versions.
* The `_surface_renders_token(surface, token)` signature takes `own` and never
  reads it (`:814`) — a stale parameter, pre-existing, cosmetic.
* Non-PHONE value predicates keep legacy notation sensitivity; the archive has
  0/450 `model_trace`, so same-turn carrier availability stays
  `not_identifiable` (M01/M03 scope, disclosed).
* The mutation-BOTH result (158) shows the v9 docstring's two-line story is
  incomplete; the estimator moved more than its own comment says.

## 6. Required repairs (for the author; nothing was modified by this review)

1. Compute `residual` on the restored text **independently of the entity choice**
   and let an unresolved leaf carry `residual=True` with `item_id=''` when a
   substitute is still standing. `_unresolved()` must stop forcing
   `residual=False`.
2. Narrow the substitute-surface test so a generic whole-address surface cannot
   own a single-word street token from another item (the `i8` vs `i7` refusal),
   or resolve same-identity whole/part records before the leak question is asked.
3. Add a pinned test with `written == restored` for a role-less address leaf
   under a same-identity collision, asserting `residual=True` — the current
   suite pins the standing fake only where a single entity owns it.

## 7. Cost / accounting

Zero provider calls, zero network, zero paid generations, no child sessions, no
workflow. Every command is local and replayable from the frozen `/private/tmp`
run directories plus the in-repo fixture builders; the reviewer's helper scripts
live at `/private/tmp/m02_v9_indep_check.py`, `/private/tmp/m02_v9_forensics.py`
and `/private/tmp/m02_mutate.py`. Reviewer spend is not separately metered; this
session made no paid model call other than its own turns. Stop rule: the review
stopped at the confirmed counterexample and its denominator effect, which is
sufficient for a REJECT. Codex decides formally.
