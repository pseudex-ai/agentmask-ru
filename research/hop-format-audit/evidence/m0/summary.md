# Completed cohort: historical and actual-hop estimators

Report: `hop-cohort-report-1`; actual OUT: `m0-actual-out-v4`.
Complete triples: 450; configuration groups: 4.

These are the SAME saved generations, NOT an engine improvement or a new live run.
Actual OUT is a conservative diagnostic of tool leaves, not a replacement for behaviour, IN, answer or chain metrics.
Unattributed/ambiguous events are measurement uncertainty, not established gateway failures.
Full PHONE value is notation-independent. Other types retain legacy value predicates; whole/part aliasing can overcount ambiguity.

## Historical estimator (completed-only composition)

| Metric | Hits/total |
|---|---:|
| leak | 3750/3751 (99.97%) |
| coverage | 3691/3751 (98.40%) |
| residual | 7549/8349 (90.42%) |
| end_to_end | 301/1736 (17.34%) |
| form_hIN | 3184/3750 (84.91%) |
| form_hOUT | 5153/7470 (68.98%) |
| chain_value | 9/197 (4.57%) |
| chain_form | 11/197 (5.58%) |
| consistency | 1267/1295 (97.84%) |
| memory_consistency | 549/549 (100.00%) |
| multi_all_out | 0/330 (0.00%) |
| overmask | 450/450 (100.00%) |
| out_absent | 1498/2692 (55.65%) |

The historical end_to_end/chain/multi lines still depend on scheduled hops.
Do not interpret those rates as engine-only restoration quality.

## Actual OUT crossings

All leaf events: 11565; not_applicable: 5103.
Each denominator below is the candidate leaf population, including uncertainty.
Form is independent of identity; joint requires correct value, form and no residual.

| Type | Candidates | Attributed | Value | Form | Form unmeasured | Residual present | Joint |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | 6462 | 3586/6462 (55.49%) | 3137/6462 (48.55%) | 2890/6462 (44.72%) | 3174/6462 (49.12%) | 288/6462 (4.46%) | 2782/6462 (43.05%) |
| untyped | 1210 | 0/1210 (0.00%) | 0/1210 (0.00%) | 0/1210 (0.00%) | 1210/1210 (100.00%) | 0/1210 (0.00%) | 0/1210 (0.00%) |
| CARD | 43 | 43/43 (100.00%) | 43/43 (100.00%) | 43/43 (100.00%) | 0/43 (0.00%) | 0/43 (0.00%) | 43/43 (100.00%) |
| DOB | 306 | 65/306 (21.24%) | 65/306 (21.24%) | 65/306 (21.24%) | 241/306 (78.76%) | 0/306 (0.00%) | 65/306 (21.24%) |
| EMAIL | 77 | 77/77 (100.00%) | 77/77 (100.00%) | 77/77 (100.00%) | 0/77 (0.00%) | 0/77 (0.00%) | 77/77 (100.00%) |
| LOC | 911 | 592/911 (64.98%) | 246/911 (27.00%) | 297/911 (32.60%) | 602/911 (66.08%) | 283/911 (31.06%) | 241/911 (26.45%) |
| NAME | 1987 | 881/1987 (44.34%) | 790/1987 (39.76%) | 838/1987 (42.17%) | 1112/1987 (55.96%) | 3/1987 (0.15%) | 788/1987 (39.66%) |
| PHONE | 1928 | 1928/1928 (100.00%) | 1916/1928 (99.38%) | 1570/1928 (81.43%) | 9/1928 (0.47%) | 2/1928 (0.10%) | 1568/1928 (81.33%) |

### Overall status counts

- matched: 3137
- mixed: 2
- residual: 288
- value_wrong: 151
- unmasked_known: 10
- ambiguous: 2162
- unattributed: 712

## Provenance and spend

`manifest.json` pins sources, recorded configurations, exclusions and ledger reconciliation.
Recorded ledger cost is not a provider invoice; missing/unreconciled amounts remain visible.
`events.jsonl` exposes each decision and its evidence for independent review.
`report.json` pins scorer hashes. Retain all files together.
