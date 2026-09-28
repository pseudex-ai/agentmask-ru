# S02 — independent report-surface recheck (2026-09-28)

**Verdict: REJECT of this bounded status package.** The three surfaces the author
named are genuinely fixed — `NOT_MEASURED` and its reason do travel to the human
markdown §1bis, `<run>.oracle.json` and `<run>.report.json`, and a measured run
keeps its per-boundary counts, neighbour damage and unreached list. **But the
promise the fix exists to keep — «a run cannot look clean» — is still broken in
two places, each reproduced below with an exact counterexample:** the public
surface publishes an unmeasured run as `incomplete: false` with no canary field
at all, and a valid manifest that declares **zero** canaries is accepted as
`MEASURED` / `ok=True` with no denominator and no rows.

This is a review of the **bounded status package**, not acceptance of the S02 row
(`docs/plan-hop-form-before-450.md:45`); the row's `0/450 measurable` and
`0/450` per-class result from
[`s02-canary-inventory-20260928.md`](s02-canary-inventory-20260928.md) is
untouched and unchallenged by the report-surface change. Read-only: the only file
written is this one. No provider, no network, no paid 450, no main-tree write, no
merge/deploy, no child session, no edit to source/tests/wiki/corpus.

Note on the brief: **`AGENTS.md` does not exist anywhere in the tree**
(`find . -iname AGENTS.md` → 0). The workspace instructions that apply are the
embedded `CLAUDE.md` block and the wiki; I read those, the S02 row, the
independence inventory, and the five named source files instead.

---

## 1. The author's three claims — verified true

Read from source, then reproduced by building a saved run with the real writers
(`test_report.build_run(...)`, `report.report_lines`, `reportjson.write`), no
provider, scripted fixture only.

| claim | where it is now true | probe result |
|---|---|---|
| §1bis prints status and reason | `report.py:953-959` — status is appended before any row; `NOT_MEASURED` adds the «НЕ ИЗМЕРЕНО — это НЕ означает „утечек нет“» line and `ПРИЧИНА:` | `СТАТУС: NOT_MEASURED` + the reason, first two lines of the section |
| oracle JSON carries it | `report.py:1128-1131` — `canary_status`, `canary_reason`, `canary_neighbour_damage`, `canary_unreached` | present, exact strings |
| machine JSON carries it | `reportjson.py:226-238` — `canary_status`, `canary_reason`, `canary_by_boundary`, `canary_neighbour_damage`, `canary_unreached` | present, exact strings |
| measured counts / neighbour damage / unreached preserved | `report.py:960-969`; `reportjson.py:235-238` | §1bis printed `model_input скрыто 0 утечек 1`, the leak line, `СОСЕДИ ЗАТРОНУТЫ`, `ГРАНИЦЫ НЕ ДОСТИГНУТЫ`; both JSONs carried the same three facts |

The redesign premise is intact: the leak is decided by
`payload_canaries.scan` against the manifest's declared surfaces only
(`payload_canaries.py:321-363`); classification can only label it (`:413-423`);
`CanaryReport.ok` is `status == MEASURED and not leaks and not damage and not
unclassified and not unreached` (`:279-283`); no manifest ⇒ `not_measured`
(`:632-651`). `test_reportjson`'s new check
(`test_reportjson.py:403-524`) is not vacuous — it demands the source be
`NOT_MEASURED` with a reason *and* reads all three produced surfaces back, then
plants a manifest and demands `MEASURED` with the counts and the leak.

---

## 2. Attack: no manifest — three surfaces pass, the fourth fails

Run built by the real writers, no `canary_manifest.json`:

```
§1bis
1bis. КАНАРЕЙКИ ПЕЙЛОАДА — байты этого прогона, по границам (S02)
   СТАТУС: NOT_MEASURED
   НЕ ИЗМЕРЕНО — это НЕ означает «утечек нет»: знаменателя нет, в прогоне нет
   construction-time манифеста канареек
   ПРИЧИНА: no versioned canary_manifest.json in the run: a saved run without a
   construction-time manifest is not measurable

oracle.json : canary_status=NOT_MEASURED, canary_reason=<same>, canaries={}
report.json : canary_status=NOT_MEASURED, canary_reason=<same>, canary_by_boundary={}
```

**`<run>.public.json` carries none of it** — reproduced keys:

```
['benchmark','cases','corpus_digest','generated_at','incomplete',
 'incomplete_reasons','lines','lines_withheld','repeats','schema','tier']
incomplete: False        incomplete_reasons: []
"canary..." in keys: False
```

This is not merely silence. The public file **affirmatively publishes
`incomplete: false`** for a run whose S02 half was never measured. The mechanism
to say otherwise already exists and is public: `incomplete` / `incomplete_reasons`
are in `PUBLIC_TOP_LEVEL` (`reportjson.py:79-81`), but `incomplete_reasons`
(`reportjson.py:158-175`) has no canary term and `assemble` computes
`incomplete = bool(blocked) or bool(parts.judge.problems) or bool(_holes(...))`
(`report.py:849`) — canary status is not an input anywhere. So on the surface
`reportjson.py:22-28` and `contracts.py:1964` call «то, что можно показать
наружу», an unmeasured run reads as **complete and clean**.

### Ruling on the public omission: **BLOCKER**

Acceptable would be a public file that simply makes no canary claim; this one
makes the opposite claim (`incomplete: false`) while omitting the fact that
invalidates it. S02's promise is stated over «a reader of the finished report»
(`payload_canaries.py:293-300`, «a missing row would read as a clean one»), and
the public file is a finished report — the one whose readers by construction
cannot consult `§1bis`. The whole point of the allowlist is that a new field is
private by default; the point was never that a *negative completeness claim* may
be published without its counterevidence. Smallest honest fix (no corpus value,
no case id is added): either add `canary_status` / `canary_reason` to
`PUBLIC_TOP_LEVEL`, or — better, because it corrects the flag rather than adding
a field beside a wrong one — add a canary term to `incomplete_reasons` so
`status != MEASURED` forces `incomplete: true`. Both are cheap; the second also
fixes the human header, which today prints «НЕПОЛНЫЙ» for other causes but never
for an unmeasured S02 half.

---

## 3. Attack: measured leak, neighbour damage, unreached — all preserved

Same saved run, manifest planted with one genuine literal present in
`model_input`, one canary on a boundary that is never delivered, and one
neighbour that no delivered byte contains:

```
check_run : MEASURED ok=False leaks=[('model_input','leak1')]
            neighbour_damage=("model_input: 'NEIGHBOUR-TEXT-NOT-PRESENT'",)
            unreached=('never_delivered',)

§1bis
   СТАТУС: MEASURED
   model_input    скрыто    0  утечек    1
   never_delivered скрыто    0  утечек    0
      model_input: leak1 [unclassified] the manifest found the declared surface;
      no evidence was supplied to classify it
   БЕЗ КЛАССА: ['leak1']
   СОСЕДИ ЗАТРОНУТЫ: ["model_input: 'NEIGHBOUR-TEXT-NOT-PRESENT'"]
   ГРАНИЦЫ НЕ ДОСТИГНУТЫ: ['never_delivered']
```

`report.json` carried `canary_by_boundary={model_input:{hidden:0,leaked:1},
never_delivered:{hidden:0,leaked:0}}`, `canary_neighbour_damage`,
`canary_unreached`; `oracle.json` the same under `canaries`. So a leak, a damaged
neighbour and an unreached boundary cannot be read as clean on any of the three.
The one asymmetry worth naming is cosmetic: the machine report spells the counts
`canary_by_boundary`, the oracle sidecar spells the same object `canaries`.

Still open and not introduced here: the real path's manifest declares
**0 neighbours** (`test_payload_canary_integration.py:97-121` builds
`pc.CanaryManifest(canaries=..., source=...)` and leaves `neighbours` at its
`()` default), so `neighbour_damage == ()`
on a live run means «nothing was declared», not «nothing was damaged» — inventory
finding #4, untouched by this package.

---

## 4. Attack: absent vs unsupported version vs zero canaries

| manifest on disk | `check_run` | §1bis | machine JSON | verdict |
|---|---|---|---|---|
| absent | `NOT_MEASURED` | status + reason + «НЕ ИЗМЕРЕНО» | status + reason | **correct** |
| `{"version":99,…}` | `NOT_MEASURED` | status + reason | status + reason | fail-safe, but see below |
| `{"version":1,"manifest":{"canaries":[],"neighbours":[]}}` | **`MEASURED`, `ok=True`, `by_boundary()={}`** | `СТАТУС: MEASURED` and **nothing else** | `canary_status: MEASURED`, `canary_by_boundary: {}` | **COUNTEREXAMPLE** |

- **Unsupported version** is refused, which is the safe direction
  (`manifest_from_json:162-187`, `read_manifest:573-584`), but `read_manifest`
  collapses «absent» and «version I do not know» into the same `None`, so the
  reason an operator reads is «no versioned canary_manifest.json in the run» even
  though the file is there with version 99. A future-format manifest and a
  missing one are the same sentence. Diagnosability nit, not a correctness bug;
  it cost one probe to tell them apart and the text should too.
- **Zero canaries is a blocker-level counterexample to the promise.** A
  syntactically valid, correctly-versioned manifest that declares no canaries is
  accepted as `MEASURED` with `ok=True`, `by_boundary()` `{}` and a §1bis that
  prints only its status line — the exact «heading with no rows» the redesign
  removed for the `NOT_MEASURED` case, restored one layer up. Nothing prints the
  declared canary count or the manifest `source`, so a reader cannot tell
  «measured 0 of 0» from a full measurement, and `ok` (the green verdict) is
  `True` on zero evidence. This is reachable without malice: the integration
  builder silently drops every declared literal its own `surface_in` filter
  cannot place (`test_payload_canary_integration.py:112`, inventory finding #6),
  and if all placements drop, `canaries=()` — a run that planted nothing then
  reports `MEASURED` / clean. The fix is to make emptiness unmeasurable, not
  green: refuse an empty manifest in `check_run`, or require at least one hidden
  canary for `ok`, and print the declared total in §1bis.

---

## 5. Exact counterexamples (n/N)

| # | construction | observed | expected by the promise |
|---|---|---|---|
| C1 | saved run, no manifest → `<run>.public.json` | `incomplete: false`, `incomplete_reasons: []`, no canary key | must not read as complete/clean |
| C2 | manifest `{"version":1,"manifest":{"canaries":[]}}` | `MEASURED ok=True by_boundary={}`, §1bis = status line only | no denominator ⇒ not measurable/not green |

Positive side, same instrument: **3/3** author-named surfaces carry
`NOT_MEASURED` + reason (markdown §1bis, oracle JSON, machine JSON); **3/3**
measured facts (leak count, neighbour damage, unreached) survive to all three.

---

## 6. Findings (severity)

1. **[blocker]** `<run>.public.json` omits every canary field and publishes
   `incomplete: false` for an unmeasured run, because canary status feeds neither
   `PUBLIC_TOP_LEVEL` nor `incomplete_reasons` (`reportjson.py:79-81,158-175`;
   `report.py:849`). «Absence reads as clean» survives on the outward surface.
2. **[blocker]** An empty (or fully silently-dropped) manifest yields
   `MEASURED` / `ok=True` with `by_boundary()={}` and a status-only §1bis —
   `payload_canaries.check_run`/`scan`/`ok` (`:279-283,321-363,632-651`) have no
   emptiness guard and the report prints no declared total.
3. **[medium]** `read_manifest` reports an unsupported manifest version with the
   same reason as an absent artifact, so the operator cannot tell a missing file
   from a future format (`:573-584`).
4. **[low]** `wiki/MAP.md` still lists neither `payload_canaries.py` nor its two
   tests (`grep -c payload_canar wiki/MAP.md` → 0), against the repo rule that a
   new module/test gets its row in the same change. `wiki/check.py` cannot see
   this because it verifies named paths, not coverage.
5. **[low, inherited]** The machine report's `canary_by_boundary` and the
   oracle's `canaries` are the same object under two names.

---

## 7. Recomputed locally (no provider)

| command | result |
|---|---|
| `python3 -m bench.agentpii5.test_reportjson` | **PASS 12/12**, including `unmeasured_canaries_are_never_printed_as_zero_leaks` |
| `python3 -m bench.agentpii5.test_payload_canaries` | **PASS 12/12** — `PASS (5 границ, 5 классов)` |
| `python3 -m bench.agentpii5.test_payload_canary_integration` | **PASS 3/3** |
| `python3 -m bench.agentpii5.test_report` | **PASS** |
| `python3 wiki/check.py` | `map, flows, claude, index, state, invariants — 0 finding(s)` |

The greens are consistent with the two blockers: no current test asserts the
public file's canary completeness, and none feeds `check_run` an empty manifest.
Both are one fixture each, and the second is why the package cannot be accepted
as-is.

---

## 8. Compliance

No provider call, no network, no paid 450 rerun, no main-tree write, no merge or
deploy, no child sessions. No source, test, wiki or corpus file was edited; the
only file written is this report. All probes ran offline against
`test_report.build_run` fixtures in a `tempfile` directory with
`PYTHONDONTWRITEBYTECODE=1`. Total local runtime well inside the 12-minute
timebox; one report produced.
