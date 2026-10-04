# M01–M03 actual-event measurement candidate — independent read-only acceptance review

- Task: `hop-m01-m03-independent-review-20260927`
- Root: `/Users/igor/Projects/Obscura-hop-audit` (`pwd` first command, confirmed; no other root was used)
- Scope: **read-only**. No source, test, corpus or saved-run file was created, modified or deleted. No network,
  no provider call, no live/paid 450. Every check below was run in-process from a `python3` heredoc; scratch
  files were not written anywhere, including `/tmp`. `git status` after the review shows the same
  modified/untracked set as before it.
- Reviewed: `docs/plan-hop-form-before-450.md` rows M01/M02/M03 (lines 40–42) and
  `docs/plan-hop-form-execution.md` (current), `prototype/bench/agentpii5/{actual_hops,causal_hops,records,harness,hop_report}.py`,
  and `test_actual_hops.py`, `test_causal_hops.py`, `test_response_trace.py`, `test_hop_report.py`.
- Saved 450 population (read only, never written): `A=/private/tmp/v5-quarter-deepseek-nojudge-clean-20260926`,
  `B=/private/tmp/v5-quarter-deepseek-missing-20260926-r2`, `C=/private/tmp/v5-quarter-deepseek-remaining-20260926`,
  `D=/private/tmp/v5-quarter-deepseek-final3-20260926`; cohort fingerprint
  `6c2a6d6978f9ec061e85c739b6bb3bb5b666c15118a6931096ef0866f8cf622c`, 450 complete triples, 4 configuration groups.

## Verdicts

| Row | Verdict | One line |
|---|---|---|
| **M01** | **ACCEPT** (mechanism) | All three acceptance clauses reproduce PASS under independent mutants; `absent` does not exist in the estimator; the versioned v7 line is reproducible on the exact saved 450. Two non-blocking caveats named below. |
| **M02** | **REJECT** | Substitute-side whole/part, same-surname ambiguity, old/new value and short-number controls all pass — but the **leak side does not separate whole from part**: a stem collision charges the wrong entity. Reproduced synthetically and twice on the real saved 450. |
| **M03** | **REJECT** | `_bind` grants `attributed` while a second carrier's availability is **unprovable**, contradicting the module's own contract rule 3 and M03's "неоптимистичный pass" acceptance; 208 printed event rows on the real 450 are affected, and the recorded evidence string is factually false. Separately, 0 of 450 saved runs carry a provider chronology, so the answer leg is entirely unmeasured on real data. |

Codex decides. Nothing here was fixed; no source or test file was touched.

## 1. What was run, and the author's suites

```
$ pwd
/Users/igor/Projects/Obscura-hop-audit
$ cd prototype && for t in test_actual_hops test_causal_hops test_response_trace test_hop_report test_records; do
    PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5.$t; done
actual_hops: PASS
causal_hops: PASS (estimator=m03-causal-hops-v1)
response_trace: PASS
hop_report: PASS (offline, manifest, events, historical + causal lines, immutable output)
records: PASS
```

All five author suites are green on the current candidate (exit 0 each). **That is not acceptance** — every
green check was re-derived from an independent construction in §3, and two checks the author does not have
(§4, §5) are red.

The public report surface was checked without running it against a run:

```
$ PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5 report --help      # v4/v5 scheduled-hop report
$ PYTHONPATH=. .venv/bin/python3 -m bench.agentpii5 hop-report --help  # new offline actual + causal report
```

**Wiring fact.** `actual_hops`/`causal_hops` are reachable only through the separate `hop-report` command
(`hop_report.py`). The public `report` command and the saved `<run>.public.json` / `<run>.report.txt` of the
450 contain **no** actual-OUT or causal line (checked: the public JSON keys are
`benchmark, cases, corpus_digest, generated_at, incomplete, incomplete_reasons, lines, lines_withheld, repeats,
schema, tier`; the public report text still prints the scheduled `end_to_end 17.34%` / `out_absent 55.65%`
families). This matches the plan's "versioned offline report" intent, but the M01–M03 rows are therefore not
in any published headline and cannot be read as an engine result by a public-report reader.

## 2. The real 450, measured by this review

In-memory `compose_cohort` → `actual_events` / `causal_events` → `aggregate` (nothing written). The v7 claim in
PROGRESS (`450 / 6462 / 3895 / 1184 / 712 / 668`) is **reproduced exactly**:

```
runs 450 · events 11565 · not_applicable 5103
all   candidates 6462  attributed 3895  value 3519  form 3264  form_unmeasured 2813
      residual 235  joint 3176
      matched 3519 · mixed 3 · residual 235 · value_wrong 130 · unmasked_known 11
      ambiguous 1184 · unattributed 712 · not_identifiable 668
```

Causal (`m03-causal-hops-v1`, 7878 emissions):

| Surface | Emissions | Tool-causal | Attributed | First | Later | Ambiguous | Unattributed | Not identifiable | User-provided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| answer | 1734 | 846 | **0** | 0 | 0 | 0 | 1 | **845** | 888 |
| tool_arg | 2507 | 1371 | 571 | 275 | 296 | 246 | 280 | 274 | 1136 |
| summary | 522 | 264 | 84 | 41 | 43 | 101 | 2 | 77 | 258 |
| template | 43 | 19 | 4 | 3 | 1 | 12 | 0 | 3 | 24 |
| chain | 3072 | 1654 | 659 | 319 | 340 | 359 | 282 | 354 | 1418 |

Reproducibility: two fresh compositions of the same four directories give byte-identical `ActualAggregate` and
`CausalAggregate`; the rendered `hop_report.summary_text` hashes to `77bc4c48b4eb520ea513885b222cf1ea48cd46a2bff6c28c094c4c728518a641`
on both. `hop_report.write_report` refuses an existing output directory (`FileExistsError`), verified by passing
the repo root as `--out` (nothing was written).

**Chronology coverage (decisive for M03):** `runs with model_trace: 0 / 450`. The `model_trace` key is *absent*
from all 450 `arms.v5.jsonl` rows (the archive predates the key), so `result_available` always takes the legacy
turn branch and the answer leg cannot be proved at all. The answer line's 0 attributed / 845 not_identifiable is
this fact, not an engine result.

## 3. Independent counterexample matrix (author's tests not reused)

Every fixture below was built by this review from the fixture builders; none is a copy of an author test.

| # | Required counterexample | Independent result |
|---|---|---|
| 1 | action moved to another turn does not create `absent` | **PASS** — `"absent" not in ACTUAL_STATUSES`; event at turn 5 vs declared turn 7 is `matched`, and the historical observer prints `absent` on the same record (the additivity the row claims) |
| 2 | event identity/verdict invariant across turns 0/1/5/9 | **PASS** — one `event_id`, one status, always a candidate |
| 3 | harmless clarification changes nothing | **PASS** — 0, 1 and 2 added user messages keep `event_id`, status, value and form identical |
| 4 | repeated calls stay distinct | **PASS** — two calls of one tool, one leaf, one turn, distinct `call_seq` → two distinct events |
| 5 | future tool result not credited | **PASS** — a result of a later call does not resolve an earlier call; with a trace, call 0 is `unattributed` while the later call that legitimately saw it is `attributed` |
| 6 | two people with the same surname | **PASS** — `ambiguous`, both candidate ids visible |
| 7 | whole + declared part share a projection | **PASS** — `matched`, both evidence ids; the distinct-fake control resolves to exactly one version |
| 8 | changed value version stays distinct | **PASS** — two NAME versions whose fakes share a surname → `ambiguous`; two PHONE versions → `ambiguous` |
| 9 | unrelated short number is not a phone | **PASS** — `age=25`, `month=11`, `order_id=34`, `score=87` all `not_applicable` |
| 10 | a real value of another item coinciding with a fake | **PARTIAL** — full-string collision → `mixed` (pass); **partial/stem collision → FAIL, see §4** |
| 11 | answer from user vs first vs later result | **PASS** — `user_provided` / `attributed+first_result` / `attributed+later_result` in one run |
| 12 | missing response chronology is `not_identifiable` | **PASS for tool-sourced items** (845 on the archive); a user datum with no carrier is correctly `user_provided` |
| 13 | answer / tool_arg / summary / template / chain have separate denominators | **PASS** — five `by_surface` lines, each with its own `candidates` and `tool_causal` |
| 14 | a result of the *same* response is not credited | **PASS** — `unattributed`; the author's monkey-patched mutation guard is real and goes red |

Representative reproduction (one heredoc, no writes):

```python
# move an action; declared hop at turn 7, actual call at turn 5
case = _case("mv","sequential_chain",("Иванова Елена",),(NAME_WHOLE,),
             (_hop("OUT","tool_arg","p1",1,7,"crm_upsert_contact",0,-1,"contact.last_name"),))
run  = _with_calls(_run("mv"),(ups(3,"contact.last_name","Пахомова","Иванова"),),(5,))
run  = _with_mentions(run,(M("p1",0,-1,"Пахомова Ольга"),)); run=_with_subs(run,{"p1":"Пахомова Ольга"})
# -> actual: matched, event_id "3|contact.last_name|p1"; historical observe(): ["absent"]
```

## 4. M02-F1 — the leak side does not separate a part from a whole (REJECT)

`actual_hops._written_has_real` asks `item_survives_in(item, item.value, written)` for every item. That path
uses `observe.needles_of` **stem** needles with the case-wide `exempt` set built by `observe.own_stems`, so a
part of *another* item's real value can match what the agent actually wrote.

Counterexample (built from scratch, minimal):

```python
A = _item("pa","NAME","Иванова Елена","Иванова Елена","i1", _in_message(0,0,13))   # fake -> "Пахомова Ольга"
B = _item("pb","NAME","Пахомова Анна","Пахомова Анна","i2", _in_seed("s2","name"))  # same surname as A's fake
case = _case("x","single",("Иванова Елена",),(A,B),())
# ROLE-LESS free-text leaf: the agent wrote A's FAKE surname, the gateway restored A's REAL surname
run = _with_calls(_run("x"),(_call("crm_upsert_contact",
        {"contact":{"name_latin":"Пахомова"}},{"contact":{"name_latin":"Иванова"}},{},"",3),),(0,))
run = _with_mentions(run,(M("pa",0,-1,"Пахомова Ольга"),)); run=_with_subs(run,{"pa":"Пахомова Ольга"})
```

Observed verdict:

```
ROLE-LESS free-text, agent wrote A's fake 'Пахомова', gateway restored 'Иванова':
   status = unmasked_known   item = pb   value_ok = False   residual = False
   EXPECTED: matched A (the gateway did its job)
ROLE leaf contact.last_name, same values:
   status = mixed   item = pa   candidates = ('pa','pb')
```

So the role'd leaf resolves conservatively (`mixed`), while the role-less leaf (free text, `name_latin`, etc.)
attributes the leaf to the **wrong person** and calls a correct restoration a leak. The same mechanism, with the
gateway *not* restoring, reports `unmasked_known` instead of `residual` — the critical line under-counted.

**It is present in the real saved 450.** Of the 11 `unmasked_known` events, 2 have `written != restored`
(the engine demonstrably replaced something, yet the event is charged as a real leak). Both are literal
whole/part collisions:

```
chain-033      call3  path=contact.initials  charged=i8  type=NAME
   written  = 'В. И.'      restored = 'И. П.'      expected = 'васильев иван павлович'
   (the written initials are another entity's; item i8's real initials needle matched, so the
    correctly restored leaf is reported as i8's leak)

tool_chain-034 call9  path=text              charged=i1  type=NAME
   written  = '…Получатель: Бирюкова Снежана Фёдоровна. Адрес: г. Чернь, ул. Черёмуховая, д. 9…'
   restored = '…Получатель: Фёдорова Юлия Викторовна. Адрес: г. Чернь, ул. Полевая, д. 4…'
   expected = 'фёдорова'
   (item i1's real surname "фёдорова" matched the PATRONYMIC "Фёдоровна" of a different name)
```

Direction of the error is *safe* (no false pass: `real` can only produce `unmasked_known` or `mixed`, never
`matched`), but it (a) names the wrong entity, (b) deflates `value`/`joint`, (c) inflates `unmasked_known`, and
(d) can replace a critical `residual` with a non-residual status. This is exactly the M02 row's stated problem
class ("ошибки сопоставления целого/части и совпадения real другого item с fake") and it contradicts M02's
acceptance clause "целое и его часть могут сопоставиться **при доказанной связи**". The report discloses the
general limitation ("Non-PHONE value predicates and free-text needles retain historical limitations"), which
makes it a declared gap — but a declared gap is not an accepted row.

Also informational: `event_id` (`seq|path|item`) is identical across `repeat` values and across arms
(`actual_hops.py:562-566`, `causal_hops.py:416`). Nothing consumes it as a key today (grep: only tests), and
`events.jsonl` rows carry `repeat`, so this is a footgun for a consumer, not a metric defect.

## 5. M03-F1 — `attributed` while a carrier's availability is unprovable (REJECT, blocking)

The module states the governing contract in its own docstring (`causal_hops.py:39-60`):

> 2. ONE CARRIER, PROVED, AND NO USER COPY IS `attributed`. A second carrier … is `ambiguous` …
> 3. **AN UNKNOWN CARRIER OUTRANKS A KNOWN ONE**: while any carrier's availability is unprovable the emission
>    is `not_identifiable`, because uniqueness is not established.

The code does not implement rule 3 (`causal_hops.py:292-325`): the branch order is
`len(available)>1 → ambiguous`, `available and user → ambiguous`, **`available → attributed`**, `unknown →
not_identifiable`, `user → user_provided`, `unavailable → unattributed`. One proved carrier plus one *unknown*
carrier therefore returns `attributed`.

Counterexample (one available carrier, one unknown; no trace = an archived run):

```python
calls = (UPS seq0 turn0, FIND seq1 turn2, UPS seq2 turn2)   # result seq0 turn0 carries p9; result seq1 turn2 carries p9
run   = _with_calls(_run("cx"), calls, (0,2,2))
run   = _with_results(run, (res(FIND,0,0,"Смирнова Анна",F9,"p9"), res(FIND,2,1,"Смирнова Анна",F9,"p9")))
carriers          = (0, 1)
availability      = [True, None]           # result_available(seq0)=True, result_available(seq1)=None
_bind(...)        -> attributed / first_result
evidence string   -> "result seq 0 (first_result) carried item p9 and was available to call 2;
                       no other carrier is available and the datum is not user-provided"
```

The evidence line written into `events.jsonl` is **factually false** — carrier seq 1 *is* a carrier, it is
merely unprovable, which is the case rule 3 exists for. Note the contrast inside the same package:
`actual_hops._decide` checks `unclocked` **before** `substituted` (`actual_hops.py:519-522`), i.e. it *does*
implement "unknown outranks known"; the two estimators of one sprint disagree about the same rule.

**Impact on the real 450** (per-surface, recomputed carrier by carrier):

| Surface | `attributed` rows that are not unique | `attributed` total | share |
|---|---:|---:|---:|
| tool_arg | 76 | 571 | 13.3% |
| summary | 26 | 84 | 31.0% |
| template | 2 | 4 | 50.0% |
| chain | 104 | 659 | 15.8% |

208 printed event rows (104 owner rows and their 104 `chain` twins), from 103 distinct
`(case, call, item)` binding decisions. On the archive the unproved carriers are same-turn carriers, which is
precisely the case the module's own comment calls "the exact case that makes an archived run's chain
`not_identifiable`". The author's two mutation guards (`check_two_calls_of_one_response`,
`check_archived_trace_is_not_identifiable`) only exercise the *single-carrier* same-turn case, so they stay
green while this hole is open.

This is a direct violation of M03's acceptance: "отсутствие достаточных записей даёт `not_identifiable`, а не
оптимистичный pass". Either the code moves to `not_identifiable` (and the 208 rows and all downstream `chain`
rates move), or Codex consciously rewrites rule 2/3 and the `attributed` definition. Silent retention of the
current state is a REJECT.

## 6. M03-F2 — the answer leg has no real data at all (unmeasured, blocking for the row)

0 / 450 saved runs carry a provider chronology; the `model_trace` key is absent from every `arms.v5.jsonl` row.
Consequently the `answer` surface prints 1734 emissions, **0 attributed**, 845 `not_identifiable`, 1
`unattributed`, 888 `user_provided`. M03's deliverable is "отдельно измерять общий answer, answer-from-tool,
summary/template и реальные рёбра цепочки" — the answer-from-tool half is 0/846 on the only saved population.
The forward path exists and is tested (`harness.GatewayHooks.response`/`model_trace`, `records.model_trace_from_json`
with its non-future boundary validation, and `deepseek_connector.py:142` calls the hook), and
`test_response_trace` uses the real `GatewayHooks`; but no *real* run demonstrates it. This is a measurement gap,
not an engine defect — and it must be named on the M03 line rather than absorbed into a green test suite.

## 7. M03-F3 — the `CausalLine` docstring states the wrong denominator (minor)

`causal_hops.py:502-503` says "`candidates` is the ONE denominator of every status **and of
value/form/residual/joint**", while `_line` (`:557-562`) divides `value_ok/form_ok/residual/joint` by
`attributed` only, and `render` prints "Value, form, residual and joint divide by ATTRIBUTED emissions only."
The printed table is honest; the code docstring a reader would cite is not. One-line fix.

Related, smaller: `_answer_response`'s last-resort fallback (`:178-181`) picks the *last* response because it has
"the most generous window", and the docstring calls that "conservative". For a single-carrier item a larger
window converts `not_identifiable` into `attributed`, i.e. it is optimistic; for a multi-carrier item it
converts `attributed` into `ambiguous`. The label is wrong for the first case and the fallback is untested on
real data.

## 8. Unmeasured gaps (not waived)

1. **M03 answer causality on real data** — 0/450 has a chronology; needs a fresh run (paid GO required) or an
   explicit `not measurable on the archive` status on the row.
2. **M03 `chain` rate purity** — 104/659 chain edges are affected by §5; until fixed, the chain `attributed`,
   `first_result`/`later_result` and `joint` lines are optimistic by an unquantified-but-counted amount.
3. **M02 leak-side whole/part** — only the 11 `unmasked_known` events were read literally; the same stem
   collision can also suppress `residual` and `matched`, and the freeze set is 2 named instances, not a
   full census of the class.
4. **`not_applicable` with a known-but-unavailable fake** — for an *unchanged, non-identity-shaped* leaf
   (`_identity_shaped` false) that carries a substitute whose only mention is in the future, the crossing leaves
   the denominator as ordinary traffic (`actual_hops.py:549-559`). No instance was found on the 450; the path is
   untested.
5. **Performance/cost of the new estimators** — not measured; the review ran on 450 saved triples only.
6. **`event_id` uniqueness across repeats/arms** — documented footgun, no current consumer.

## 9. Cost

- **Paid benchmark spend by this review: $0.00.** No provider call, no live run, no network; all work was local
  read-only Python. This is a verified fact, not an estimate.
- **DSH session token cost: not reported — not observable.** `prototype/bench/agentpii5` accounting does not
  apply to a review session; the local session journal
  (`~/.dsh/sessions/…/baecc1ca-…session.v3.jsonl.zstd`, 421 records) carries no `input_tokens`/`output_tokens`/
  `cost`/`usage` field, and no other local usage record exists. Reporting a USD number here would be invented.
  `accountingComplete=false`; the sprint's earlier figure ($0.251535048 and the twelve-session $1.306017408)
  remains a lower bound and is not reduced or renamed by this review.

## Files referenced

- `docs/plan-hop-form-before-450.md:40-42` (M01/M02/M03) · `docs/plan-hop-form-execution.md` §5-§6
- `prototype/bench/agentpii5/actual_hops.py:209-233` (`_mention_available`), `:275-325` (`_renders_part`,
  `_written_has_substitute`, `_written_has_real`), `:328-366` (`_entity_of`, `_projection_owner`),
  `:498-559` (`_decide` branch order), `:562-566` (`_event_id`)
- `prototype/bench/agentpii5/causal_hops.py:39-60` (contract), `:184-232` (`result_available`),
  `:274-327` (`_bind`, the divergence), `:502-503`/`:557-562` (denominator docstring vs code)
- `prototype/bench/agentpii5/records.py:234-335` (trace round-trip + non-future validation)
- `prototype/bench/agentpii5/harness.py:311-366` (mentions/results), `:599-680` (`GatewayHooks`),
  `:740-750`, `:866-888` (the Claude leg's explicit `model_trace=None`)
- `prototype/bench/agentpii5/hop_report.py` (separate `hop-report` command; no public-report wiring)
- `prototype/bench/agentpii5/observe.py:322-391` (`needles_of`/`value_needles`), `:479-547` (`survival`, `own_stems`)
- Saved runs: `/private/tmp/v5-quarter-deepseek-{nojudge-clean,missing-20260926-r2,remaining,final3}-20260926`
- Evidence: `research/hop-format-audit/evidence/reviews/m04-report-population-20260927.md` (prior M04 review, same form)

No source or test file was changed by this review. The only file created is this one.
