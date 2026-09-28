# S02 — bounded status repair (C1/C2), second independent READ-ONLY recheck (2026-09-28)

**Verdict: PASS for the bounded status package as specified (C1 + C2).**
**Full S02 stays REJECT / open** — the row's `0/450` and the disabled capture are
untouched by this package and I re-measured them as still true (§7).

I did not author any of this code. Read-only on source, tests, wiki and corpus:
the only file written is this one. No provider, no network, no paid run, no
`450` rerun, no child session, no main-tree write, no merge/deploy. Focused
suites only, all offline, ~4 min total.

**Ruling asked for in the brief — the `report.txt` title vs the public
`incomplete` flag: NOT a blocker for the bounded package.** Full reasoning and
the exact counterexample + lines in §5; it is finding 1 at **[medium]**, not a
package stopper, because the same human file says `NOT_MEASURED` in words two
lines into §1bis and no surface publishes a *clean* reading of an unmeasured
half.

---

## 1. What I ran (focused, offline, no engine, no provider)

`PYTHONDONTWRITEBYTECODE=1`, cwd `prototype/`, `.venv/bin/python`, fixtures from
`test_report.build_run` (the real writers: `report.report_lines`,
`reportjson.write`) in `tempfile` directories.

| command | result |
|---|---|
| `python3 -m bench.agentpii5.test_payload_canaries` | **PASS 13/13** — `payload_canaries: PASS (5 границ, 5 классов)` |
| `python3 -m bench.agentpii5.test_payload_canary_integration` | **PASS 3/3** |
| `python3 -m bench.agentpii5.test_reportjson` | **PASS 15/15**, incl. `unmeasured_canaries_make_the_public_file_incomplete`, `an_empty_manifest_cannot_render_clean`, `measured_canaries_keep_their_counts_and_stay_complete` |
| `python3 -m bench.agentpii5.test_report` | **PASS 29/29** |
| **total** | **60/60** |

**Revision frozen once.** The reviewed files carry mtimes 01:07–01:16 (the S02
author's last edits before going idle); the only writer still active in this tree
owns `actual_hops.py` / `test_actual_hops.py` (`dcc3a918…`) and none of the files
below. Every number here was taken against these exact bytes and the focused
suites were re-run on them — same 60/60. Hashes re-read at 01:22:32, unchanged:

```
0dac5c19ee8e487d7ec6ff2505c04a70ff04b1aafd335c0c0980c36ce6d4b995  payload_canaries.py
ceeaa01287fcede2fe30cdb06ab7e15467d10f58d8ab42d1541de0d37342b6e0  report.py
5bf9cffc524ec15b77f2fdc6f093265d755cdd4f6f07f0ce2efcac46b6a3cba0  reportjson.py
be0f4ae122479f9c956d32e3067f8217ca817ef3af7a12603c1c688c92eaaf1a  test_reportjson.py
45159910a05922a541557e43c7dd184df2247a748c964b3d04de5ccb52f04ee7  test_payload_canaries.py
0a381b7b84f4cad2d040d8b628d2acebb8253ebb0cea2d9a6e58f7f5d8e89219  test_payload_canary_integration.py
080d7fad39511a28e0bbacadc86bcb3a1e558ccc5a96e714eaa77d603a10d4fe  harness.py
84b40f36e2c6fe8aa614d6e2d81271d8a30109aa3ff5b4bb4cc5346261a76393  wiki/MAP.md
```

All `file:line` citations below were re-verified against these hashes.

Plus my own independent probe (`/tmp/s02v2_probe.py`, `/tmp/s02v2_probe2.py`):
six saved-run constructions, read back from all four produced surfaces
(`.report.txt`, `.report.json`, `.public.json`, `.oracle.json`).

Independent probe outcomes, one row per construction (n/N = 6/6 constructions
reproduced as claimed):

| # | construction | `check_run` | public.json | report.json | .report.txt §1bis | oracle |
|---|---|---|---|---|---|---|
| C1 | no manifest | `NOT_MEASURED ok=False` + reason | `incomplete True`, reason, `canary_status NOT_MEASURED`, `canary_reason` | same + `canary_by_boundary {}` | `СТАТУС: NOT_MEASURED` + «НЕ ИЗМЕРЕНО…» + `ПРИЧИНА:` | `canary_status NOT_MEASURED` |
| C2a | `canary_manifest.json` = `{not json at all` | `NOT_MEASURED` reason = `JSONDecodeError: Expecting property name…`, **no crash** | incomplete True | incomplete True | status + reason | status |
| C2b | `{"version": 99, …}` | `NOT_MEASURED` reason names version 99 vs reader's 1 | incomplete True | incomplete True | status + reason | status |
| C2c | `{"version":1,"manifest":{"canaries":[],"neighbours":[]}}` | `NOT_MEASURED ok=False` (0 canaries) | incomplete True | incomplete True | `NOT_MEASURED` + reason, **no `скрыто` rows** | status |
| M1 | v1 manifest, 1 hidden canary | `MEASURED ok=True` | `incomplete False`, `canary_status MEASURED` | counts `{model_input:{hidden:1,leaked:0}}` | `СТАТУС: MEASURED` + `скрыто 1 утечек 0` | same counts |
| M2 | v1 manifest: 1 hidden + 1 leaked + damaged neighbour + unreached | `MEASURED ok=False`, leak/damage/unreached all set | `incomplete False`, `canary_status MEASURED`, **no counts, no damage, no unreached** | counts + `canary_neighbour_damage` + `canary_unreached` | `скрыто 1 утечек 1`, leak line, `БЕЗ КЛАССА`, `СОСЕДИ ЗАТРОНУТЫ`, `ГРАНИЦЫ НЕ ДОСТИГНУТЫ` | same counts |

---

## 2. C1 reproduced exactly as claimed — no manifest, healthy run

Reproduced verbatim (paths redacted to `<tmp>`):

```
check_run   : status=NOT_MEASURED ok=False
              reason='no versioned canary_manifest.json in the run: a saved run without
                      a construction-time manifest is not measurable'
public.json : incomplete=True
              incomplete_reasons=['канарейки пейлоада не измерены: no versioned
                                   canary_manifest.json in the run: …']
              canary_status='NOT_MEASURED'  canary_reason=<same string as check_run>
              keys=['benchmark','canary_reason','canary_status','cases','corpus_digest',
                    'generated_at','incomplete','incomplete_reasons','lines',
                    'lines_withheld','repeats','schema','tier']
report.json : incomplete=True, canary_status='NOT_MEASURED',
              canary_reason=<same>, canary_by_boundary={},
              canary_neighbour_damage=[], canary_unreached=[]
§1bis       : '1bis. КАНАРЕЙКИ ПЕЙЛОАДА …'
              '   СТАТУС: NOT_MEASURED'
              '   НЕ ИЗМЕРЕНО — это НЕ означает «утечек нет»: знаменателя нет, в прогоне
               нет construction-time манифеста канареек'
              '   ПРИЧИНА: no versioned canary_manifest.json in the run: …'
oracle.json : canary_status='NOT_MEASURED', canaries={}
```

- **Explicit canary reason/status on the public surface: yes** —
  `reportjson.py:79-87` (`PUBLIC_TOP_LEVEL` now ends `"canary_status",
  "canary_reason"`) and `reportjson.py:254` (`"incomplete": side.incomplete or
  canary_incomplete(parts)`), with `canary_incomplete` at `reportjson.py:164-170`
  and the reason text at `reportjson.py:197-199`.
- **No private values: yes.** I grep the produced `.public.json` bytes for the
  fixture's real name, real phone and fake name and for both case ids:
  `fixture values present=[]  case ids present=[]`. The reason strings are
  provenance text only.
- **`report.json` and `report.txt` §1bis agree** with the public flag: the same
  `NOT_MEASURED` plus the *same* reason string (`parts.canaries.reason`, written
  once, read by both — `report.py:954-959` and `reportjson.py:265-266`).

## 3. C2 reproduced exactly as claimed — empty v1 manifest, bad JSON, bad version

- **Empty v1 manifest** → `check_run` returns
  `NOT_MEASURED ok=False` with
  `canary_manifest.json declares 0 canaries (source 'artifact'): a manifest with
  no denominator is not measurable, and «measured, clean» on zero evidence is the
  reading this refuses` (`payload_canaries.py:686-690`, plus the same guard inside
  `scan`, `payload_canaries.py:336-339` — I called `scan` on an empty manifest
  directly: `NOT_MEASURED`). Consequences: §1bis prints `NOT_MEASURED` + the
  reason and **no `скрыто` rows**; `.report.json` and `.public.json` both say
  `incomplete: True` with the canary reason; oracle says `NOT_MEASURED`. So
  **human, public and machine all refuse a clean reading** — C2 is closed.
- **Malformed JSON** → `NOT_MEASURED`, reason names `JSONDecodeError`; report and
  JSON writers complete without an exception.
- **Unknown version** → `NOT_MEASURED`, reason names *the version it saw* and the
  one the reader knows (`payload_canaries.py:611-615`). This closes the earlier
  inventory's diagnosability nit: absent, unreadable, unknown-version and
  malformed-body are now four distinct sentences (`load_manifest`,
  `payload_canaries.py:587-620`).

## 4. Measured, non-empty manifest — correct on the private/human surfaces

- **M1 (hidden only):** `MEASURED ok=True`, `incomplete False`, and §1bis prints
  `скрыто 1 утечек 0`. The C1 term does not drag an honest run into «НЕПОЛНЫЙ».
- **M2 (leak + damaged neighbour + unreached):** `MEASURED ok=False`; the leak,
  `СОСЕДИ ЗАТРОНУТЫ` and `ГРАНИЦЫ НЕ ДОСТИГНУТЫ` are printed in §1bis and carried
  in `report.json` and `oracle.json`. `CanaryReport.ok` is the clean verdict and
  is `False` here (`payload_canaries.py:279-283`).

**One semantic to state plainly, because the brief's phrasing («complete true
only when no leak/damage/unreached») reads it the other way.** The
`incomplete` flag is a *measurability* flag, not a cleanliness flag: M2 keeps
`incomplete: false` while `ok=False`, deliberately
(`test_reportjson.py:645-714` asserts exactly that). Measured + leaking is a
finding, not an incomplete report — the finding is the leak rows, which travel on
§1bis/report.json/oracle. That is defensible, but see finding 2 for what it costs
on the **public** surface.

## 5. Ruling: `report.txt` title vs public `incomplete` — **not a blocker**

**Counterexample (reproduced, C1 construction):**

```
<title of <tmp>/fixture0001.report.txt, line 1>:
AgentPII-RU v5 — …/fixture0001 против …/baseline01          ← no «НЕПОЛНЫЙ»
<same run>.public.json : "incomplete": true                 ← and a canary reason
```

**Where it comes from:** the human title's mark is `report.py:891`
(`mark = f"  {contracts.INCOMPLETE_REPORT_MARK}" if side.incomplete else ""`),
and `side.incomplete` is set at `report.py:849` from refused metrics, the judge
and the holes **only**. The JSON documents use a wider condition,
`reportjson.py:254` (`side.incomplete or canary_incomplete(parts)`). The
divergence is explicit and acknowledged in the writer's own comment,
`reportjson.py:247-253`. I confirmed the direction both ways: with no manifest
`side.incomplete=False` while `reportjson incomplete=True`; with a deliberately
refused metric (`toolresult_masked` replaced by a broken `Line`) `side.incomplete=True`
and the title **does** print «НЕПОЛНЫЙ».

**Why it is not a blocker:** the unmeasured half is not silent anywhere. The
human report prints, in the same file and in §1bis at `report.py:953-959`,
`СТАТУС: NOT_MEASURED` + «НЕ ИЗМЕРЕНО — это НЕ означает „утечек нет“» + the
`ПРИЧИНА` (reproduced verbatim in §2). The earlier blocker was that the public
file made an *affirmative* completeness claim whose counterevidence its readers
could not reach; here the counterevidence is two lines below the title in the
very artifact that carries it, and the title omits a mark rather than asserting
one. So the C1 promise — «a reader of the finished report cannot take an
unmeasured half for a measured one» — still holds on the human surface, and the
public surface now says `incomplete: true`.

**Still a real defect, and it belongs to this package's owner:** one run now
carries two definitions of one flag, which is the exact pattern the repo's own
comments call «one drift away from a report contradicting itself». Smallest
honest fix: compute the human mark from the same composed condition
(`side.incomplete or reportjson.canary_incomplete(parts)`), or carry the canary
term on `SideBySide.incomplete` at `report.py:849`. The stated reason it was left
alone — three `test_report` pins on the manifest-less fixture's title — is a test
that would need updating, not a licence for divergent definitions.

## 6. `wiki/MAP.md` — the canary instrument is still invisible (integration risk)

```
grep -c payload_canar wiki/MAP.md   → 0
```

`wiki/MAP.md` §4.1 (lines 638-648) *was* updated for this workstream: it names
`bench/agentpii5/cohort.py`, `actual_hops.py`, `hop_report.py` and pins
`test_cohort.py`, `test_actual_hops.py`, `test_hop_report.py`,
`test_response_trace.py`. It names **neither** `payload_canaries.py` nor
`test_payload_canaries.py` nor `test_payload_canary_integration.py`, and the
only `canary` hits in the map are the unrelated licensing canary
(`licensing/canary.py`, `test_canary.py`) and `bench/eval_canaries.py`.

**Why this is an integration risk rather than bookkeeping:** `wiki/check.py`
verifies that every path the wiki *names* exists and that the map matches the
import graph — it cannot see a module the map never names (`python3 wiki/check.py`
is green today, so the gate cannot be the evidence that the map is complete). The
repo rule in `CLAUDE.md` is that a new module/test gets its row in the same
change. The result is asymmetric: an agent reading the map learns the hop modules
exist and learns nothing about the S02 payload canary instrument, which is the
one that decides the S02 acceptance row. **Owner of the next edit to
`payload_canaries.py` or its tests should add the three rows in the same change.**

## 7. Open, and unchanged by this package (full S02 remains REJECT)

- **`0/450` measurable today.** `find . -name canary_manifest.json` → **0**
  files (excluding the venv). The four cohort archives named by
  `research/hop-format-audit/evidence/m0/manifest.json` all still return
  `NOT_MEASURED` with the missing-manifest reason — re-measured just now:
  `A NOT_MEASURED`, `B NOT_MEASURED`, `C NOT_MEASURED`, `D NOT_MEASURED`.
  Per boundary and per class the honest reading remains `0/0` (no denominator),
  not `0` leaks.
- **A future paid run would still be unmeasured by construction.** The only
  `GatewayV5(...)` in the real runner is `harness.py:1187`, without
  `capture=True` and without a `manifest=`;
  `GatewayV5.__init__` defaults `capture: bool = False` (`harness.py:162`) and
  the only writer of `canary_manifest.json` in the tree is a test. So the
  package fixes how an unmeasured run is *reported*, not whether one is
  *measurable*.

## 8. Findings (severity)

1. **[medium]** The human report title and the public/private `incomplete` flag
   derive from two different conditions, so a run whose only incompleteness cause
   is the canary half has `incomplete: true` in JSON and no «НЕПОЛНЫЙ» in the
   `.report.txt` title (`report.py:891` + `:849` vs `reportjson.py:254`).
   **Ruled not a blocker** (§5); reproduced; fix is one condition.
2. **[medium, outside the C1/C2 scope as specified]** On a **measured leaking**
   run (`ok=False`) the public file is indistinguishable from a measured clean
   one: `canary_status: "MEASURED"`, `canary_reason: ""`, `incomplete: false`,
   and none of `canary_by_boundary` / `canary_neighbour_damage` /
   `canary_unreached` is in `PUBLIC_TOP_LEVEL` (`reportjson.py:79-87`). The
   counts/verdict remain on §1bis, `.report.json` and `.oracle.json`, and the
   public file does publish its own `leak`/`coverage` lines — so this is not the
   old «absence reads as clean», but the outer promise is only fully kept on the
   private surfaces. Worth an explicit owner decision (publish the canary counts,
   or state that the public file carries no canary findings).
3. **[low]** `canary_reason` reaches `.public.json` with text interpolated from
   the manifest artifact itself: `manifest.source` (`payload_canaries.py:686-690`)
   and the unsupported-version value `raw.get("version")!r`
   (`payload_canaries.py:611-615`). I reproduced the hole: a v1 manifest whose
   `source` was `"builder saw Иванова Елена +79164021187"` published both the real
   name and the real phone inside `.public.json`. Reachable only from a manifest
   the pipeline itself wrote, so it is not a live leak — but it is a path by which
   "the public file carries no corpus value" can be defeated, and the fix is to
   keep `source` out of the public reason.
4. **[integration risk, medium-low]** `wiki/MAP.md` names neither
   `payload_canaries.py` nor its two tests while naming the sibling hop modules
   from the same workstream; `wiki/check.py` is green and cannot catch it (§6).
5. **[open, unchanged]** `0/450` manifests and `capture=False` in the only real
   runner (§7) — the blockers that keep **full S02** rejected.

## 9. Verdict and n/N

| item | n/N | evidence |
|---|---|---|
| C1 no manifest → public incomplete true + status + reason, no private values | **1/1** | §2; `check_run` NOT_MEASURED, `public.json incomplete=True`, reason present, fixture values/case ids absent |
| C1 report.json / report.txt §1bis agree | **1/1** | §2; same reason string on both |
| C2 v1 empty manifest → NOT_MEASURED, ok=False, no clean reading on human/public/machine | **1/1** | §3; §1bis + both JSONs, no `скрыто` rows |
| C2 bad JSON / unsupported version → distinct reason, no crash | **2/2** | §3 |
| Measured healthy → `ok=True`, `incomplete=False`, counts present | **1/1** | §4 M1 |
| Measured leaky/damaged/unreached → `ok=False`, all three facts visible, `incomplete` per its measurability semantics | **1/1** | §4 M2; §8 finding 2 for the public-surface limit |
| Focused suites | **60/60** | §1 |
| Title/public-flag mismatch ruling | **ruled NOT a blocker** | §5 |
| Full S02 (`0/450`, capture disabled) | **still open / REJECT** | §7 |

**PASS for the bounded status repair package C1/C2.**
**REJECT (unchanged) for the S02 acceptance row as a whole** — the package makes
an unmeasured run honest to report; it does not make any run measurable, and
`0/450` with capture disabled stands.

## 10. Compliance

Read-only: the only file written is this one. No source, test, wiki or corpus
file was edited; no `actual_hops`/`m02`-owned file was touched. No provider call,
no network, no paid `450` rerun, no merge, no deploy, no child session. All
probes ran offline against `test_report.build_run` fixtures in `tempfile`
directories with `PYTHONDONTWRITEBYTECODE=1`; the focused suites are four local
scripts (~6 min including the full re-run on the pinned revision). One report
produced inside the 12-minute timebox.
