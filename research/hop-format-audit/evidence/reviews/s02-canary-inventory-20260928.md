# S02 — independent payload-canary inventory (2026-09-28)

**Verdict: REJECT.** S02 is not acceptable. The canary instrument itself is
sound and its local fixtures pass, but **0 of the 450 saved triples is
measurable**, nothing in the run pipeline writes a manifest, the report renders
`NOT_MEASURED` as an **empty section**, and the real model-bound path declares
**no neighbour literals**. No paid rerun, no provider, no network, no child
session, no main-tree write, no merge/deploy. Read-only on source/tests/corpus;
the only file written is this one.

Scope of this inventory: `prototype/bench/agentpii5/payload_canaries.py`,
`prototype/bench/agentpii5/test_payload_canaries.py`,
`prototype/bench/agentpii5/test_payload_canary_integration.py`,
`harness.py` (capture/manifest seam), `report.py` / `reportjson.py` (where the
result is printed), `records.py` (what a saved run actually persists), the
`docs/plan-hop-form-before-450.md` S02 row, `PROGRESS.md` current checkpoint,
`wiki/MAP.md`, and the stored evidence under `evidence/`.

The earlier allegation that `ToolResultRecord.spans_real` is detector-derived
stays rejected and is **not repeated** here. Source confirms it:
`harness.push_call` builds `spans_real` from `log.result_spans` (mock item tags)
and stores detector-derived `pieces` separately (`harness.py:345-352`).

---

## 1. What is being audited, and what it is worth

`payload_canaries` is an **independent** instrument: ground truth is a
`CanaryManifest` whose surfaces are literals the fixture wrote, and a leak
exists **iff** a declared surface stands in the delivered bytes
(`payload_canaries.py:321-363`). Detector/span/KV/result evidence may only
**label** a leak the manifest already found (`classify`, `:413-423`); it can
never create or drop one. A run with no versioned `canary_manifest.json` is
`NOT_MEASURED`, never clean (`check_run`, `:632-651`). That design is correct
and is the right shape for the S02 acceptance row
(`docs/plan-hop-form-before-450.md:45`: «детектор-span не используется как
собственная истина»).

Measured locally (no provider; scripted connector double):

| Command | Result |
|---|---|
| `python3 -m bench.agentpii5.test_payload_canaries` | **PASS 12/12** — `payload_canaries: PASS (5 границ, 5 классов)` |
| `python3 -m bench.agentpii5.test_payload_canary_integration` | **PASS 3/3** |

What those greens do and do **not** prove:

- They prove the **scanner** can fail: undeclared prefix stays negative, a
  longer digit run stays negative, neighbour damage reds, an undelivered
  `tool_error` is `unreached` not clean, evidence cannot invent a leak, and the
  scanner source names no fixture literal (`test_payload_canaries.py:71-249`).
- They prove the **live seam** can be driven and unmeasured: each per-boundary
  mutant reds only its own boundary, and `capture=False` unmeasures every
  boundary (`test_payload_canary_integration.py:193-233`).
- They do **not** measure any saved run. Every green above is a fixture.

---

## 2. Are the manifests truly constructed at payload creation?

Per artifact, read from source:

| artifact | ground truth | constructed at payload creation? | detector used? |
|---|---|---|---|
| `make_canary_fixture` (`:463-528`) | one function builds the real text, the swap list and the specs together; `delivered` is derived by applying the swaps (`:512-517`) | **YES** | no — the "gateway" here is a hand `.replace()`, so it tests the scanner, not the engine |
| `make_number_fixture` (`:531-551`) | same, for one number boundary | **YES** | no |
| integration `_manifest_for` (`test_payload_canary_integration.py:97-121`) | case declarations: `item.value`, `item.canonical`, and the exact `[start,end)` slice of the case message (`:80-94`); placement read from the harness's **pre-mask** bytes (`payload.real_text`) | **construction-DERIVED, assembled AFTER the run** (`:163` attaches it to the gateway) | no detector span is read — case declarations only |
| saved-run reader `_delivered_from_run` (`:587-629`) | would read the saved bytes | n/a — unreachable, no manifest exists | **partly yes — see §4** |

So the prohibition that matters — *never synthesise a manifest from detector
spans* — is **honoured**. The integration manifest is retrodicted from
construction data, not from spans. Two real weaknesses remain:

1. **Silent drop.** Placement is filtered by the scanner's own matcher:
   `if pc.surface_in(payload.real_text, one)` (`test_payload_canary_integration.py:113`).
   A literal the case declares but that `surface_in` cannot see in the pre-mask
   bytes is **not planted and not reported** — no row, no warning. A silent drop
   is the failure class S02 exists to remove.
2. **No neighbours on the real path.** `_manifest_for` returns
   `CanaryManifest(canaries=..., source="case-construction")` with
   `neighbours=()` (`:121`). Only the synthetic unit fixture has neighbours
   (`payload_canaries.py:518-524`). The S02 over-masking half — «соседние
   неперсональные слова/числа не затронуты» — is therefore **unmeasured** on
   the model-bound path.

Concrete local measurement of the integration case (`chain-000`, 10 case items,
scripted double, no provider):

```
canaries: 41 | neighbours: 0
by boundary: {'final_answer': {'hidden': 4, 'leaked': 0},
              'model_input': {'hidden': 6, 'leaked': 0},
              'model_request': {'hidden': 6, 'leaked': 0},
              'tool_args': {'hidden': 12, 'leaked': 0},
              'tool_error': {'hidden': 1, 'leaked': 0},
              'tool_result': {'hidden': 12, 'leaked': 0}}
status: MEASURED | leaks: 0 | unreached: () | neighbour_damage: ()
```

Clean and per-boundary — but `neighbour_damage == ()` because **zero neighbours
were declared**, not because none were damaged.

---

## 3. Is the model-bound payload scanned independently of the detector?

**Live path: YES.** The composed `model_request` is the real
`mask_messages(...)` output the provider would receive
(`harness.py:225-246`); the scan reads manifest + delivered bytes only, and the
`ORACLE`/`DETECTOR` labels come from `evidence()` as decoration
(`:248-268`). `test_evidence_classifies_but_never_decides` PASS and
`test_removing_the_capture_hook_unmeasures_every_boundary` PASS demonstrate
both directions.

**Saved path: NO.** `_delivered_from_run` (`:587-629`) does not read the
delivered message bytes — it **reconstructs** `model_input` by re-applying
substitutes taken from `run.mentions` (detector-derived mention records) onto
the corpus message contents (`:608-622`), and it never builds the composed
`model_request` boundary at all. `records.py` persists no per-message delivered
bytes: only `reply_raw`, `tool_results` (`text_real`/`text_masked`/spans/pieces)
and `mentions` (`records.py:339-341`, reader `:388-429`). So if a manifest were
ever added to a saved run, the `model_input` boundary would be scored against a
reconstruction of the masking under test, and the composed model-bound request —
the thing S02 singles out — would be absent. This is latent today only because
no manifest exists.

---

## 4. Which saved 450 runs have manifests? — none

The 450-triple cohort is four saved archives (`evidence/m0/manifest.json`
`sources`): A `/private/tmp/v5-quarter-deepseek-nojudge-clean-20260926` (314),
B `/private/tmp/v5-quarter-deepseek-missing-20260926-r2` (9),
C `/private/tmp/v5-quarter-deepseek-remaining-20260926` (124),
D `/private/tmp/v5-quarter-deepseek-final3-20260926` (3).

- Whole-workspace `find . -name canary_manifest.json` → **0 files**.
- The 45 `manifest.json` files under `prototype/bench/runs/` are run-registry
  metadata (`date`, `git_head`, `inputs`), not canary manifests.
- `payload_canaries.check_run` on all four archives plus the repo's own saved
  nano run:

```
A  exists=True manifest=False status=NOT_MEASURED  reason=no versioned canary_manifest.json in the run: …
B  exists=True manifest=False status=NOT_MEASURED  …
C  exists=True manifest=False status=NOT_MEASURED  …
D  exists=True manifest=False status=NOT_MEASURED  …
nano (prototype/bench/runs/2026-09-23/v5-live-nano) status=NOT_MEASURED  …
```

- Nothing in the pipeline writes the artifact. The **only** writer of
  `canary_manifest.json` in the workspace is a test
  (`test_payload_canaries.py:201`). The real runner constructs
  `GatewayV5(case, detector, Vault, AuditLog, MaskCache(256))`
  (`harness.py:1187`) — `capture` defaults `False` and `manifest` defaults
  `None` (`:161-163`, `:194-195`). **Even a future paid run would be
  unmeasured.**

### n/N by boundary (450 saved triples)

`0/450` triples measurable ⇒ **0/0** per boundary. `0/0` is *not* “0 leaks out
of everything”; it is “no denominator exists”.

| boundary | canaries declared | hidden | leaks | measured N |
|---|---:|---:|---:|---:|
| `model_input` | 0 | 0 | 0 | 0 |
| `tool_args` | 0 | 0 | 0 | 0 |
| `tool_result` | 0 | 0 | 0 | 0 |
| `tool_error` | 0 | 0 | 0 | 0 |
| `final_answer` | 0 | 0 | 0 | 0 |
| `model_request` | 0 | 0 | 0 | 0 |

### n/N by miss class (450 saved triples)

| class | n | N | why |
|---|---:|---:|---|
| `detector` | 0 | 0 | no manifest → `NOT_MEASURED`, not “no detector misses” |
| `span` | 0 | 0 | same |
| `kv` | 0 | 0 | same |
| `result-payload` | 0 | 0 | same |
| `oracle` | 0 | 0 | same |
| `unclassified` | 0 | 0 | same |

**Unmeasured vs unknown, kept apart:**

- **Unmeasured (the whole saved population):** 450/450 triples and 4/4 archives
  return `NOT_MEASURED` with the reason “no versioned `canary_manifest.json` in
  the run”. There is no partial reading to report.
- **Unknown (not S02-classifiable):** the older estimator’s saved privacy
  misses are detector/span-derived and **may not be relabelled** as S02
  findings. From `evidence/m0/summary.md` (same 450, old instrument):
  historical `leak 3750/3751` (one miss), `coverage 3691/3751`, status counts
  `unmasked_known 10`, `residual 288`, `value_wrong 151`, `mixed 2`,
  `ambiguous 2162`, `unattributed 712`. Which layer those belong to is exactly
  what S02 is supposed to answer and, absent construction manifests, cannot.
  The historical `end_to_end 301/1736` and `chain_*` lines are additionally
  schedule-dependent and remain explicitly unmeasured.

No confirmed saved privacy miss exists under the S02 instrument, because no
saved run can be scanned. Reporting any of the numbers above as S02 results
would be the synthesis the module was redesigned to forbid.

---

## 5. Concrete canary + unaffected-neighbour negatives (verified locally)

From `test_payload_canaries.py` (all PASS) and an explicit probe:

| negative | declaration | delivered | result |
|---|---|---|---|
| full value hidden | full phone | masked phone | no leak, `ok=True` |
| planted cut reds | full + declared fragment | truncated by 1 | leak, `surface_kind=fragment` |
| undeclared prefix | full only | prefix | **no leak** (correct: not planted) |
| longer number | full + fragment | full digits + `000` | **no leak** (correct: another number) |
| neighbour damaged | `подтвердить заказ N` etc. | neighbour replaced by `***` | `neighbour_damage` reds, **no invented leak** |
| boundary never delivered | `tool_error` declared | payload absent | `unreached` reds, `ok=False` |
| capture hook removed | any | `capture=False` | every core boundary reports nothing hidden |

Probe output for the truncation seam (the honest limit): with **only the full
literal declared**, a one-character truncation is **not** reported
(`declared=full only -> leaks: [] ok= True`); declaring the exact fragment makes
it a `fragment` leak (`ok= False`). Truncation detection is therefore
**fixture-enumerated, not automatic** — the instrument cannot claim to catch
“a span that stopped one character short” unless the fixture declared that
exact cut.

---

## 6. Report surface: `NOT_MEASURED` currently reads as a clean run

This is the most dangerous defect found, because it defeats the module's own
stated rule that «a missing row would read as a clean one».

- `CanaryReport(status=NOT_MEASURED)` has `boundaries=()`, so
  `by_boundary()` returns **`{}`** (probe: `status NOT_MEASURED`,
  `by_boundary {}`, `reason 'no manifest'`).
- `report.py` §1bis iterates only `parts.canaries.by_boundary()` and
  `parts.canaries.leaks` and prints **only `unclassified`** otherwise
  (`report.py:946-953`). It never prints `status` or `reason`. On every saved
  run today §1bis renders as a **heading with no rows**, indistinguishable from
  “measured and empty”.
- `<run>.oracle.json` writes `"canaries": by_boundary()` → **`{}`**
  (`report.py:1106-1107`), with no status field.
- The versioned machine report carries canaries **not at all**:
  `grep -ic canar prototype/bench/agentpii5/reportjson.py` → **0**.

So a reader of the finished report cannot tell a run that measured nothing from
a run that leaked nothing. That must be fixed before any run is accepted.

---

## 7. Findings (severity)

1. **[blocker]** 0/450 measurable — no saved run carries `canary_manifest.json`;
   no code path writes one (`§4`).
2. **[blocker]** The real runner never enables `capture` or passes a `manifest`
   (`harness.py:1187`) — future runs, including a 450 rerun, would be
   `NOT_MEASURED` by construction (`§4`).
3. **[blocker]** `NOT_MEASURED` renders as an empty §1bis section; `.oracle.json`
   writes `{}`; `reportjson` has no canary field. Absence reads as clean (`§6`).
4. **[high]** The live model-bound manifest declares **0 neighbours**
   (`test_payload_canary_integration.py:121`), so S02's over-masking acceptance
   half is unmeasured on the real path (`§2`).
5. **[high]** The saved-run reader reconstructs `model_input` from
   detector-derived `run.mentions` and never builds `model_request`; saved-path
   measurement is therefore not detector-independent (`§3`).
6. **[medium]** The integration manifest's placement filter can **silently
   drop** a case-declared literal (`:113`), producing no row (`§2`).
7. **[medium]** Numeric truncation is caught only when the fixture declares the
   exact fragment; a one-char cut of a declared full value is invisible (`§5`).
8. **[low]** `wiki/MAP.md` does not list `payload_canaries.py` or its two tests
   (`grep -c payload_canar wiki/MAP.md` → 0), against the repo rule that a new
   module/test gets its row in the same change.

Positive, for the record: the manifest is construction-derived and never
span-synthesised; the scan decision is detector-independent on the live path;
evidence classification cannot invent or drop a leak; the `capture=False`
mutation proves the counts come from the harness hook; the scanner source names
no fixture literal.

---

## 8. Smallest local fixture/integration needed before S02 can be accepted

No 450 rerun is required to close the instrument. The minimum, all local:

1. **Move manifest construction into the harness.** Build the
   `CanaryManifest` in the delivered code path (not in the test) from case
   construction data at case start, with `capture=True`, so ground truth exists
   without a test's help. Keep the integration test as the assertion, not the
   builder.
2. **Give the real manifest neighbours.** For every case, declare the non-PII
   literals the case itself wrote (order ids, quantities, status words) on each
   boundary whose pre-mask bytes carry them, and assert
   `len(neighbours) > 0` plus `neighbour_damage == ()` on a right run. This is
   the missing half of the S02 acceptance row.
3. **Persist the delivered bytes, and read them back.** Write
   `canary_manifest.json` (`manifest_to_json`) and a `{name, text}`-only
   delivered-bytes artifact at capture time, then have `check_run` read those
   bytes instead of reconstructing `model_input`; build and scan
   `model_request` on the saved path too. No detector data in either artifact.
4. **Fail the run, not just print.** A run without manifest/capture must be an
   informative run-level refusal (or an explicit `incomplete` reason), never a
   silent pass.
5. **Make the report say it.** §1bis must print `status` and `reason` whenever
   the report is not `MEASURED`, and `reportjson` must carry
   `canary_status` / `canary_reason` / `canary_by_boundary`; an empty §1bis
   section must be impossible for an unmeasured run.
6. **One saved-run round trip as the acceptance fixture:** build manifest +
   payloads for one case, write them, run `check_run` → MEASURED with per-boundary
   counts; delete the manifest → `NOT_MEASURED`; restore one boundary's real
   bytes → only that boundary reds; damage one neighbour → `neighbour_damage`
   reds and no leak is invented; truncate a declared value by one character
   without declaring the fragment → not a leak (documented limit), with the
   fragment declared → a `fragment` leak.

Until 1–6 exist, the honest S02 statement is **0/450 measurable**, and no
saved privacy miss may be assigned to `detector`, `span`, `kv`,
`result-payload` or `oracle`.

---

## 9. Compliance

No provider call, no network, no paid 450 rerun, no main-tree write, no merge or
deploy, no child sessions, no edit to `envelope.py` or to any phone/error test
owned by the other writer. Only local test scripts were run
(`PYTHONDONTWRITEBYTECODE=1`), two of them (~14 s total); the only file written
is this report. Local test time well under the 15-minute cap.
