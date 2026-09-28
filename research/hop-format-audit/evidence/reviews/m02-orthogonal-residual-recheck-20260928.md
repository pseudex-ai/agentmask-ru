# M02 v10 orthogonal-residual repair — independent read-only acceptance attack

Reviewer: DSH main agent (DeepSeek Flash), session
`hop-m02-orthogonal-residual-review-20260928`. **NOT the author.** Read-only on
source, tests, wiki and the saved corpus; this file is the only artefact written.
Date: 2026-09-28. No network, no provider, no paid generation, no child sessions,
no workflow/ralph, no merge. Candidate: `prototype/bench/agentpii5/actual_hops.py`,
estimator `m0-actual-out-v10` (working tree, uncommitted).

## Verdict

| Row | Verdict | One line |
|---|---|---|
| **M02** | **REJECT** | The orthogonality claim is genuinely delivered — `tool_chain-009 c15` and all 31 v8→v9 hidden rows now carry `residual=True` with `item_id=''`, and the 563 newly flagged unresolved rows sample as true standing fakes — but the `residual` flag has a large confirmed **false-positive class**: a role-typed leaf whose substitute part equals the customer's own real part is charged `residual` even though the restored text is exactly the real value. 140 of the 205 `residual`-status rows (68.3%) are this class, reproduced by the independent city-role fixture below and by the frozen cohort (`chain-003 c3`, `long_order-001 c4…`). |

The exact counterexample, from the code path named in the task
(`_substitute_stands` returns at `actual_hops.py:418-420` before either exemption
set is read):

```
independent fixture (my own builders, /private/tmp/m02v10attack/city_role.py)
  item c1  LOC, real city 'Орёл', parts {city: орёл}
  substitute c1 = 'Орёл'  (mention available, msg 0)
  call turn 2  path 'contact.address.city'  written='Орёл'  restored='Орёл'
  v10 -> status='residual'  item_id='c1'  residual=True  attributed=True
  expected: residual=False (the leaf carries the customer's own real city;
            no minted fake is standing)
```

## 1. Hashes and run identity (verified)

| artefact | claimed | actual sha256 |
|---|---|---|
| `prototype/bench/agentpii5/actual_hops.py` | `dcc3a918…` | `dcc3a91823b0c8af5f58ab4872ff481a8d454e53c0d7de1b8601ccf971405835` ✅ |
| `prototype/bench/agentpii5/test_actual_hops.py` | `e147ec3b…` | `e147ec3b5575a9ad3e14fac2127e539a31e6c636c0a31b5d35354abbf3b838da` ✅ |

`/private/tmp/hop-m02-v10-20260928/report.json` pins `estimator=m0-actual-out-v10`
and `scorer_sha256["actual_hops.py"] = dcc3a918…`, i.e. the saved offline run is
the current candidate. Cohort fingerprint
`6c2a6d6978f9ec061e85c739b6bb3bb5b666c15118a6931096ef0866f8cf622c`, 450 complete
triples, 11565 actual leaves — identical keys on v8, v9 and v10. Diff against the
v9 tree (`/private/tmp/actual_hops_v9_reconstructed.py`,
`sha256=53af8349…`) confirms v10 changed the residual side only: the identity
reader is `_written_has_substitute` unchanged, the residual reader is the new
`_minted_substitute_stands`/`_leaf_leak`, and `_unresolved()` now carries a
`residual` argument instead of forcing `False`.

## 2. What was run (all local, offline, reproducible)

```
cd prototype && source .venv/bin/activate
python3 -m bench.agentpii5.test_actual_hops                        # 42/42 PASS, exit 0
python3 /private/tmp/m02v10attack/city_role.py                     # reviewer fixture
python3 /private/tmp/m02v10attack/dump_city.py                     # corpus re-derivation
PYTHONPATH=. python3 /private/tmp/m02v10attack/verify_generic.py   # exemption-set probe
```

The frozen v10 run (`/private/tmp/hop-m02-v10-20260928/events.jsonl`) was
re-derived in memory and matches its own `report.json` row for row; v8
(`/private/tmp/hop-m02-v8-ind-20260928`) and v9
(`/private/tmp/hop-m02-v9-ind-20260928`) are the frozen reviewers' runs. The
corpus cases were loaded from the four saved source directories through
`hop_report.compose_cohort` — no provider, no engine replay.

## 3. Author claims that hold (independently reproduced)

* **`tool_chain-009 repeat 0 call_seq 15 path 'query'` is repaired.**

  | | status | item | residual | written | restored | candidates |
  |---|---|---|---|---|---|---|
  | v8 | residual | `i7` | True | `Орёл Пихтовая 168к54` | `Орёл Пихтовая 168к54` | `('i7',)` |
  | v9 | ambiguous | `''` | **False** | same | same | `('i7','i8')` |
  | v10 | ambiguous | `''` | **True** | same | same | `('i7','i8')` |

  The byte-identical standing fake is now reported without naming an entity.
* **All 31 v8→v9 hidden residual rows are recovered.** v8 `residual` → v9
  `ambiguous` 20 + `not_identifiable` 11. In v10 every one of the 31 has
  `residual=True`, `item_id=''`, `attributed=False` — **0 violations**, no forced
  or wrong owner.
* **The 563 unresolved rows really carry the flag.** `residual=True` decomposes as
  205 `residual` status + 563 unresolved (528 `ambiguous`, 20 `not_identifiable`,
  15 `unattributed`); `768 = 205 + 563` exactly.
* **The 8 `residual → value_wrong` rows are true fake disappearance, not a city
  heuristic.** In 7 of them the written fake street is absent from `restored` and
  replaced by a *different* fake street (`tool_chain-005 c12` `Барбарисовая`→
  `Осиновая`; `tool_chain-010 c11` `Буковая`→`Грушевая`; `tool_chain-018 c12`
  `Луговая`→`Абрикосовая`; `tool_chain-020 c8` `Лавандовая`→`Жасминовая`;
  `tool_chain-032 c13/c14` `Барбарисовая`→`Черёмуховая`; `tool_chain-034 c9`
  `Черёмуховая`→`Полевая`). `residual=False` is correct for the item; the
  replacement is a `value_wrong`. The 8th, `tool_chain-036 c4`, is
  `written == restored == 'Челябинск 19 километров'` and the only match is the
  generic city of `i8`'s whole-address substitute `г Челябинск, ул Пихтовая, д 83`
  — no street fake stands, so `residual=False` is defensible; note only that the
  identity charge to `i8` rests on the generic city alone (identity-side, see §6).
* **Denominator consistency v9 → v10 holds.** `candidates 6465`, `attributed 3855`,
  `value_ok 3515`, `joint_ok 3174`, `matched 3515`, `ambiguous 1209`,
  `unattributed 685`, `not_identifiable 716` are all unchanged. Only the residual
  side moved: `residual status 213 → 205`, `value_wrong 119 → 127`,
  `form_ok 3251 → 3259`, `form_unmeasured 2831 → 2823`, residual flag total 768.
* **F1/F2 and the neighbouring controls still hold.** `test_actual_hops` is 42/42
  PASS (exit 0), including `roleless_collision_asks_this_calls_evidence` (msg 0 vs
  msg 1 identical, collider never charged), `future_mention_is_not_borrowed_as_prior_evidence`,
  `same_surname_and_old_new_versions_never_charge_the_collider`,
  `short_numbers_do_not_attribute_without_a_role`,
  `standing_fake_is_residual_without_naming_an_entity`,
  `generic_city_alone_is_not_a_minted_part`,
  `future_mention_is_not_borrowed_for_residual`. The v9 recheck independently
  reproduced F1/F2, and the v9↔v10 diff shows the identity reading untouched.
* **The 563-row sample is not padded with generic-city noise.** 0 of the 563 have
  `restored == expected`. Deterministic sample (sorted by `(case_id, call_seq, path)`,
  every ⌈n/10⌉-th per status; 30 rows read): **29/30 confirmed** a minted
  street/surname substitute still standing (`tool_chain-004 c4` `Луговая`,
  `tool_chain-038 c5` `Мятная`, `long_order-008 c51` `Луговая`, …),
  **1/30 uncertain** (`chain-022 c2`, Latin `contact.name_latin` `Kukushkin Valeriy`
  — the fake pool membership could not be confirmed offline). Untyped
  (`pii_type=''`) rows dominate by count (239) because the note names items while
  the leaf has no single type; they still show standing fakes.

## 4. The blocking finding: a role leaf charges the customer's own real part

`_substitute_stands` (`actual_hops.py:418-420`) is:

```python
if spec is not None and spec.role:
    return any(_renders_part(item.type, text, part)
               for part in _role_parts(item, spec.role, surfaces))
```

This early return is reached by **both** readers, so `_minted_substitute_stands` —
whose whole docstring claim is that a token the customer's own values carry in a
generic role "cannot prove a minted part" — never consults `case_own`, `item_own`
or `generic` on a role-typed leaf. For a role leaf the only surviving test is
"does the restored text exactly render the substitute's part". The engine's mint
**preserves the city** in an address substitute, so the substitute's city part and
the real city are the same string and the test fires on the real value.

Frozen-cohort confirmation:

```
chain-003 repeat 0 call_seq 3 path 'contact.address.city'
  item i10  real parts {city: кинешма, street: подлесная, house: 15, flat: 5}
  substitute i10 = 'Кинешма, улица Грушевая 20, кв. 104', parts {city: кинешма, ...}
  written = 'Кинешма'   restored = 'Кинешма'   expected = 'кинешма'
  v10 -> status='residual'  item_id='i10'  residual=True  attributed=True
  generic_stems_of(case) = {'gmai', 'кине', 'прос'}   # 'кине' IS the real city stem
```

The exemption that would have cancelled `кине` exists and is passed into
`_minted_substitute_stands`; the role branch never reads it. The same mechanism
reproduces on `to_location.city` and `address.locality`.

Population effect on the saved 450 (all read from the frozen events):

| quantity | value |
|---|---|
| residual-flag rows | 768 |
| residual-**status** rows | 205 |
| rows with `residual=True` **and** `restored.casefold() == expected.casefold()` | **140** |
| … by path | `to_location.city` 113, `contact.address.city` 18, `address.locality` 9 |
| share of the `residual` status class | **140/205 = 68.3%** |
| their v10 status | `residual` 140/140, `attributed=True`, `value_ok=False`, `form_measured=False` |
| same rows in v8 / v9 | `residual` 131/131 checked in both — **pre-existing**, not introduced by v10 |

For every one of these 140 the tool received exactly the value the estimator's own
`expected` column says it should receive, and the leaf is printed as the critical
defect. `observe.own_stems` states the rule this violates: without the exemption
"`residual`, the critical-defect line, would fire on the product working" — it
fires here on the product working. The 140 are also dropped from the value/form
denominators (`_restoration` short-circuits `value_ok=False`, `form_measured=False`)
although the restoration succeeded, so the false positive costs the report on both
sides.

## 5. Required repairs (for the author; nothing was modified by this review)

1. Make the ROLE branch of `_substitute_stands` consult the same exemption sets:
   for the residual question a role part that `part_matches` the item's own real
   part, or whose stem is in `generic_stems_of(case)`, is the customer's word and
   not a minted fake. (Keep the identity question's reading as v9 pinned it.)
2. Pin the counterexample: a `city`/`locality` role leaf whose substitute part
   equals the real part and whose `restored == expected` must assert
   `residual=False`. No current test covers the role branch's exemption bypass;
   `generic_city_alone_is_not_a_minted_part` exercises only the role-less leaf.
3. Re-read the 563 unresolved rows after the fix: none of them are role-FPs today
   (0 have `restored == expected`), so the orthogonal repair itself survives; the
   flag total should fall from 768 to ≈628 and the status class from 205 to ≈65.

## 6. Secondary observation (not the rejection basis)

`tool_chain-036 c4` (`written == restored == 'Челябинск 19 километров'`, path
`query`) is attributed to `i8` and scored `value_wrong`, but the only needle that
matches is the generic city in `i8`'s whole-address substitute. The residual
reader correctly refuses that token; the identity reader does not. That is the
pre-existing generic-city tension on the identity side, disclosed here so the
v10 repair is not read as having closed it.

## 7. Cost / accounting

Zero provider calls, zero network, zero paid generations, no child sessions, no
workflow. Every command is local and replayable from the frozen `/private/tmp`
run directories plus the in-repo builders; reviewer helpers live in
`/private/tmp/m02v10attack/`. Reviewer spend is not separately metered; this
session made no paid model call other than its own turns. Stop rule: the review
stopped at the confirmed counterexample and its cohort population, which is
sufficient for a REJECT. Codex decides formally.
