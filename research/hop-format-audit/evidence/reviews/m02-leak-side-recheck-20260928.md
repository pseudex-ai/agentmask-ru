# M02 v8 leak-side repair — independent read-only recheck

Reviewer: DSH main agent (DeepSeek Flash), persisting session
`hop-m02-leak-side-review-20260928`. **NOT the author.** Read-only on source,
tests, wiki and the saved corpus; this file is the only artefact written.
Date: 2026-09-28. No network, no provider, no paid 450, no child sessions.

Candidate: `prototype/bench/agentpii5/actual_hops.py`, estimator
`m0-actual-out-v8` (working tree, uncommitted). Baseline for the saved-450 delta:
the accepted v7 artifact `/private/tmp/hop-sprint-m03-v7-20260927` (estimator
`m0-actual-out-v7`) — the same 450 saved triples, identical cohort fingerprint.

## Verdict

| Row | Verdict | One line |
|---|---|---|
| **M02** | **REJECT** | The two named v8 guards are real and the saved-450 move set is exactly 6 leaves, but the leak side still charges the **wrong person** on a role-less leaf whenever the colliding other entity's substitute was disclosed after message 0, and on an **unrestored** leaf it replaces the critical `residual` with `unmasked_known`. A second, independent defect makes the new fallback in `_written_has_substitute` unreachable. |

The row's acceptance clause («целое и его часть могут сопоставиться **при
доказанной связи**»; «два человека с одинаковой фамилией … остаются различимы»)
is met only on the role-specific path. The role-less path — free text,
`contact.name_latin`, a joined address — is where §4's counterexample lives, and
it still does.

## 1. What was run

```
cd prototype && source .venv/bin/activate
python3 -m bench.agentpii5.test_actual_hops          # 35/35 PASS (author suite)
python3 -m bench.agentpii5.test_hop_report           # PASS (offline, manifest, events, causal, immutable output)
python3 -m py_compile bench/agentpii5/actual_hops.py bench/agentpii5/test_actual_hops.py bench/agentpii5/hop_report.py   # OK
python3 -m bench.agentpii5.hop_report --source A=… B=… C=… D=… --out /private/tmp/hop-m02-v8-ind-20260928
# -> 450 complete triples; 11565 actual leaves; estimator=m0-actual-out-v8
```

Every fixture below is built by this review through the fixtures' own builders
(`_item`/`_case`/`_call`/`_run`/`_with_*`) and `actual_events`; no author test
is reused and no expression is copied from the candidate's test file. The
`saved-450` comparison uses the frozen `events.jsonl` of v7, keyed by
`(case_id, repeat, call_seq, path)`.

## 2. M02-F1 (blocking): hardcoded `(0, 0)` in `_owned_by_substitute` charges the wrong person

`actual_hops.py:796`:

```python
for surface in _available_surfaces(run, other.id, 0, 0):
```

The two readers of availability disagree. `_decide` asks for the **current**
call (`_available_surfaces(run, item.id, turn, call.seq)`, line 564); the leak
side asks every *rival* at turn 0 / seq 0. `_mention_available` with
`(0, 0)`, on an archived run (no `model_trace`), accepts only
`mention.msg <= 0`, so a substitute the agent had already read at message 1 or
later is invisible to the collision guard. The docstring justifies `0` with
«a substitute minted by a LATER tool result», but the bound it implements is
message 0, not the current call — a mention at `msg=1` is in the agent's hands
at a turn-3 call by the module's own availability rule.

Independent fixture — A's fake surname «Пахомова» is B's real surname (B is a
different person), role-less leaf `contact.name_latin`, call at **turn 3**,
A's fake disclosed at message 0 vs message 1 (both ≤ 3, so both available):

```
call turn=3, A's fake mention available at msg 0 and msg 1 (both <= 3):
  contact.name_latin   mention_msg=0 restoreA -> ('unattributed', '', (), False)
  contact.name_latin   mention_msg=0 NORESTORE -> ('not_applicable', '', (), False)
  contact.name_latin   mention_msg=1 restoreA -> ('unmasked_known', 'pb', ('pb',), False)
  contact.name_latin   mention_msg=1 NORESTORE -> ('unmasked_known', 'pb', ('pb',), False)
  contact.last_name    mention_msg=0 restoreA -> ('mixed', 'p1', ('p1', 'pb'), False)
  contact.last_name    mention_msg=1 restoreA -> ('mixed', 'p1', ('p1', 'pb'), False)
```

Reading:

* **Wrong-person unmasked_known.** `mention_msg=1`, gateway **restored A
  correctly** → the event is `unmasked_known` charged to **pb**. The written
  token is A's minted substitute and B's real surname; the entity charged is the
  collision, not the crossing. This is §4 verbatim, one message index away from
  the author's own fixture (which pins `msg=0`).
* **Silent residual.** `mention_msg=1`, gateway **did not restore** (written ==
  restored == A's fake, a genuine residual leak) → still `unmasked_known pb`,
  `residual=False`. §4's «the critical line under-counted» consequence is
  reproduced: a standing fake is not counted as residual.
* **Availability invariance is violated.** The same records, same call, two
  mentions both available at that call, produce different verdicts
  (`unattributed` vs `unmasked_known pb`). Availability at the current call is
  the only thing that may matter; `msg=0` vs `msg=1` may not.
* A **future** mention (`msg=4` > turn 3) also yields `unmasked_known pb` — so
  the wrong charge is reachable both for a late-but-real and for a genuinely
  future disclosure.
* The **role-specific** leaf (`contact.last_name`) is safe in every variant
  (`mixed p1`), because the role branch (`_role_parts`/`_renders_part`) is
  independent of `exempt`. The defect is confined to role-less leaves, which is
  exactly the scope §4 named.

Mutation that restores the OLD false attribution (proves the new guard is
load-bearing, not that it is sufficient):

```
stock                         msg0: [('unattributed', '')]
mutated (_fragment_owned_by_another -> False) msg0: [('unmasked_known', 'pb')]   # §4 verbatim
mutated (_own_value_refuses -> False)         msg0: [('value_wrong', 'p1')]
stock                         msg1: [('unmasked_known', 'pb')]
mutated (_own_value_refuses -> False)         msg1: [('mixed', 'p1')]
```

Removing `_fragment_owned_by_another` returns the module to the original §4
defect on the author's own `msg=0` fixture. The guard narrows the collateral but
does not reach the late-mention case. Fixing only the inversion (below) turns
`msg=1` into `mixed p1` — the rival is still charged because the `(0, 0)` bound
is still blind — so both defects must be repaired together.

## 3. M02-F2 (blocking): the fallback in `_written_has_substitute` is unreachable

`actual_hops.py:356-372`:

```python
if carries_any(item.type, surfaces, text, own):          # case-wide exempt
    return True
if _own_value_refuses(case, item, surfaces, text):       # own-only exempt
    return False
if _owned_by_substitute(case, run, text, own=…, exclude=item.id):
    return False
return carries_any(item.type, surfaces, text, own_stems_of(case, item))   # DEAD
```

`_own_value_refuses` (line 383) is **byte-for-byte the same expression** as the
final `return`:

```python
return carries_any(item.type, surfaces, text, own_stems_of(case, item))
```

So whenever the final `return` would be `True`, `_own_value_refuses` has already
returned `True` and the function returned `False` three lines earlier. The last
line can only be reached with `carries_any(...) == False`, i.e. it always returns
`False`. The fallback is dead code.

It is also **logically inverted**. `own` is the `exempt` set: `observe.carries_any`
→ `survives_in(..., own)`, where an exempt stem cancels an occurrence
(`observe.py:556-573`). `carries_any(type, surfaces, text, own_stems_of(case,item))`
therefore asks: «does this item's **substitute** render `text` once this item's
own real values are excluded?» — `True` means *the text is this item's
substitute*. The code treats `True` as «the refusal stands» and returns `False`.
The docstrings of both functions describe «the item's OWN value explains the
text», which is the *complement* of what the call computes.

Effect (instrumented, `_written_has_substitute(A)` on the §4 fixture):
`carries_any` case-wide `False`, `carries_any` own-only `True`,
`_own_value_refuses(A) True`, and the final answer `False`. The fake's owner is
never credited on a role-less leaf under a collision: the honest outcomes
(`matched` / `value_wrong` for A, which the author's own test docstring says the
leaf owes the reader) are unreachable — the leaf is `unattributed` at best, and
`unmasked_known pb` at worst. The author's `test_leak_side_separates_a_part_from_a_whole`
passes because its assertions are one-sided (`item_id != "pb"`,
`status not in ("unmasked_known","mixed")`); `unattributed` satisfies them, so the
test pins «not the wrong person» but not «the right one».

Hidden denominator effect: with `_own_value_refuses` flipped to `False`, the
`msg=0` fixture becomes `value_wrong p1` (candidate credited, `value`/`joint`
denominators gain an event) and `msg=1` becomes `mixed p1`.

## 4. Saved-450 delta — independently reproduced, exactly 6 leaves

`/private/tmp/hop-m02-v8-ind-20260928` vs the accepted v7 artifact
`/private/tmp/hop-sprint-m03-v7-20260927`; `cohort_fingerprint` equal, 11565
leaf events both sides:

```
MOVED v7->v8: 6
   chain-022            c2  contact.middle_name  : mixed        i8  -> matched  i8
   chain-033            c3  contact.initials     : unmasked_known i8 -> unattributed
   memory_anaphora-028  c2  contact.name         : mixed        i10 -> matched  i10
   prompt_rule-016      c6  query.last_name      : unmasked_known i3 -> unattributed
   tool_chain-034       c9  text                 : unmasked_known i1 -> unattributed
   tool_chain-034       c10 text                 : mixed        i10 -> value_wrong i10
```

«6 moved leaves» is confirmed; two of the three named are exact. The third is
`chain-022 c2 contact.middle_name` (mixed→matched), not `contact.name_latin` —
`contact.name_latin` remains `ambiguous` with three entities (`i1|i2|i8`).
Minor bookkeeping, not a defect; the raw rows:

```
memory_anaphora-028 c2 contact.name  W «Лебедев Артур» R «Ерохин Пётр» exp «Ерохин Пётр» -> matched
tool_chain-034     c10 text          W «…тел. +7 922 331 03 22…» R «…тел. +7 922 331 03 58…» -> value_wrong
```

No hidden real value and no residual was lost by the three:
`tool_chain-034 c9` (the §4 patronymic charge) and `chain-033 c3` moved off the
wrong entity to `unattributed`, and `residual` is 235 on both sides. The
mixed→value_wrong move is a strict improvement (a free-text leaf holding several
values is not a clean match).

Recomputed totals (memory, from the two `events.jsonl`; agree with both
`report.json`):

| quantity | v7 | v8 |
|---|---:|---:|
| candidates | 6462 | 6462 |
| attributed | 3895 | 3895 |
| value_ok | 3519 | 3521 |
| joint_ok | 3176 | 3178 |
| residual | 235 | 235 |
| mixed | 3 | 0 |
| unmasked_known | 11 | 8 |
| unattributed | 712 | 715 |
| ambiguous / not_identifiable | 1184 / 668 | 1184 / 668 |

All 8 v8 `unmasked_known` rows have `written == restored` (a real value written
with no restoration) — none is the wrong-person charge. **F1 is latent on the
saved 450**, not printed there: the move set happens to be the `msg=0`-shaped
slice. Latent on the archive is still a defect of the estimator, and the
synthetic counterexample is built from the archive's own shape.

`git status` confirms this review modified nothing: `actual_hops.py` and
`test_actual_hops.py` are untracked working-tree files, the other modified paths
belong to the concurrent E01/form writer and were not touched or attributed here.

## 5. Controls that do hold (independent)

* The exact-overlap ambiguity never produces a false attribution: the
  colliding token yields `ambiguous`/`unattributed`/`mixed`/`value_wrong`, never
  `matched` on the wrong entity.
* A true fake of A beside B's independently real value in distinct spans stays
  `mixed` (author pin `m02-pin`, re-run by me); it is not turned into a pass.
* Two people sharing a surname stay `ambiguous`; old/new value versions stay
  distinct; ordinary short numbers stay `not_applicable`; role-less `unattributed`
  and `not_applicable` remain distinguishable.
* `residual` remains inside the joint denominator on both baselines.
* The `mixed -> matched` moves are legitimate: the alternate candidate was a
  collision with the *substitute*, not a hidden real value.

## 6. Style / conventions (AGENTS bar)

* `_surface_renders_token(surface, token, own=None)` accepts `own` and **never
  reads it** (grep of lines 801-817: `own` occurs once, in the signature).
  `_owned_by_substitute`'s docstring calls `own` «THE EXEMPTION THE QUESTION IS
  ASKED WITH» — a load-bearing claim in a repo whose comments are the design
  record, and it is false.
* `_owned_by_substitute(case, run: ArmRunV5 | None, …)` is typed optional but
  dereferences `run.mentions`/`run.model_trace` with no guard; `run=None` is a
  live crash, not a supported state.
* New default arguments (`own=None`, `exclude=""`) are accepted but
  `exclude` is mandatory in both real call sites; the unused defaults hide the
  fact that the function has exactly two meaningful modes.

## 7. Acceptable limitations (not the reason for REJECT)

* `form_unmeasured` 2810/6462 on the saved 450 (form not measurable for the
  unpaired remainder).
* Non-PHONE value predicates retain legacy notation sensitivity; only whole
  PHONE has the independent numeral fold.
* The archive has 0/450 `model_trace`, so same-turn carrier availability stays
  `not_identifiable` — M01/M03 scope, disclosed in the report's limitations.
* One review did not re-run the full 15-suite v5 battery; the focused
  `test_actual_hops` (35/35), `test_hop_report` and `hop_report` on the frozen
  450 were run.

## 8. Required repairs (for the author, not done here)

1. Pass the **current call's** `turn`/`call.seq` into the leak-side
   `_owned_by_substitute` call (line 796), not `(0, 0)`; or hoist one
   availability map computed once per `(call, item)` and share it between
   `_decide` and the leak side.
2. Fix the inverted guard / remove the dead final `return` in
   `_written_has_substitute` (lines 356-372) so a role-less leaf credits its
   **substitute's owner**; rename `_own_value_refuses` to what it computes.
3. Add the review's counterexample as a pinned test with the call at turn 3 and
   the mention at `msg=1`, asserting `residual` for the unrestored variant and
   `matched`/`value_wrong` for the restored one — the current author test pins
   only `msg=0` and never requires the right entity.

## 9. Cost / accounting

Zero provider calls, zero network, zero paid generations; no child sessions.
All commands are local and reproducible from the frozen `/private/tmp` run
directories and the in-repo fixture builders. Reviewer DSH spend is not
separately metered here; this session made no paid model call other than its own
turn budget. Stop rule: the review stopped at the counterexample (F1/F2 plus the
6-leaf delta), which is sufficient for a REJECT; the remaining matrix rows were
not re-derived because the row already fails.
