# S02 capture/readback — independent READ-ONLY recheck (2026-09-28)

**Verdict: REJECT — candidate still incomplete.** The capture/readback redesign is
real and its own focused greens pass, but the S02 acceptance row is still not met:
the **real runner constructs no construction-time manifest**, so every capture it
writes carries an **empty** manifest and reads back `NOT_MEASURED`; and the
**per-row size bound is applied to the whole multi-row artifact**, so a real 450
run's `.canary.jsonl` (~7.3 MB projected) is refused wholesale. `test_reportjson`
stays **RED 3/16**, all three from fixtures that predate the capture requirement.
No provider, no network, no paid 450, no child session, no merge/deploy, no edit to
`actual_hops.py` / `test_actual_hops.py` or any source/test/wiki/corpus file. The
only file written is this one.

Scope read from source: `payload_canaries.py`, `harness.py` (capture/manifest
seam, `run_triple_v5`, `drive_v5` writer), `bench/agentpii4/gateway.py`
(`RealGateway._push` / `note` / `note_tool_call`), `records.py` /
`contracts.RUN_FILES`, `reportjson.py` / `report.py`, and the three test files.
This recheck does **not** repeat the earlier rejected `spans_real` allegation.

---

## 1. Focused tests reproduced (no provider, `PYTHONDONTWRITEBYTECODE=1`)

| Command | Result |
|---|---|
| `python3 -m bench.agentpii5.test_payload_canaries` | **PASS 16/16** |
| `python3 -m bench.agentpii5.test_payload_canary_integration` | **PASS 5/5** |
| `python3 -m bench.agentpii5.test_reportjson` | **FAIL 3/16** |

`test_reportjson` RED (exact sentences):

- `incomplete_is_explained: a healthy run was marked incomplete: ["канарейки пейлоада не измерены: no .canary.jsonl artifact in the run…"]`
- `unmeasured_canaries_are_never_printed_as_zero_leaks: the fixture holds no delivered bytes — the measured half is vacuous`
- `measured_canaries_keep_their_counts_and_stay_complete: the fixture holds no delivered bytes — the measured half is vacuous`

The two canary tests are greens because both build the manifest **inside the
test** (`test_payload_canary_integration.py:170` `gateway._manifest = _manifest_for(...)`,
`:274`). Nothing proves the real runner does.

---

## 2. The two requested risks — verified

### 2a. `model_request` is recomposed after the run, not captured at delivery — **CONFIRMED (method)**, divergence path real but not reproduced

Evidence chain, all read:

- Delivery composes per message only: `GatewayV5._push` → `super()._push` →
  `RealGateway._push` (`bench/agentpii4/gateway.py:149-151`) calls
  `mask_messages([...self._transcript...], self._context, False)`. `GatewayV5`
  captures only the per-message string there (`harness.py:311-316`,
  `model_input`), **not** the composed request.
- The composed boundary is produced later, on first read, by
  `GatewayV5.captured_payloads()` (`harness.py:244-246`):
  `composed = mask_messages([dict(one) for one in self._transcript], self._context, False)`.
  This is a **fresh re-run of the layer under test** against `self._context`,
  whose `vault=self._view` is live state, over the transcript as it stands at
  capture time.
- The transcript keeps being mutated **without** a composition:
  `RealGateway.note()` appends `{"role":"assistant", …}` (`gateway.py:177-178`)
  and `note_tool_call()` appends the assistant tool-call turn
  (`gateway.py:180-186`). `note()` is called from the live connector at
  `harness.py:862` (and `agentpii4/harness.py:249`) after the last push may have
  happened. So whenever a dialogue ends on a noted assistant turn, the
  recomposed `model_request` carries a turn **no request ever sent**.
- Offline probe over the scripted double (no provider): the recomposed payload
  has roles `['system','user','assistant','tool',…,'assistant','tool']` and ends
  on `tool`, i.e. in **this** run the message set coincided with the last pushed
  request. The divergence path exists but the scripted double did not exercise it.

Consequence: the docstrings that state this boundary is "the model's real input
and not a reconstruction of it" (`payload_canaries.py:355-358`) and "not a
reconstruction" (`harness.py:234-240`) are **overclaims**. No test pins
`recomposed == delivered`; the integration test only re-runs the same
recomposition.

### 2b. `CAPTURE_MAX_ROW_BYTES` is checked against the whole multi-row file — **CONFIRMED (blocker)**

`read_captures` (`payload_canaries.py:463-495`) sizes the **file**
(`path.stat().st_size`) and compares it to `CAPTURE_MAX_ROW_BYTES` (4 MiB), while
`append_capture` (`:436-445`) appends one row per (case, repeat) to that one
`.canary.jsonl`. The constant's own comment says "Per row is the bound that
decides a triple is broken" (`:89-95`) — the code does not implement that.

Probes (offline, constructed rows):

```
1764 valid small rows -> file 4,195,446 bytes
read_captures REFUSED:  r.canary.jsonl: 4195446 bytes is over the 4194304 byte bound for one capture artifact
check_run status:      NOT_MEASURED (reason = the delivered bytes could not be read: …)
```

Real row size, measured from the harness capture of one corpus case:

```
one real capture row            = 16,268 bytes
projected 450 rows             = 7,320,600 bytes  >  4,194,304 (ROW bound)
bound trips at                 = row 258
RUN bound (256 MiB) is never   the one that applies
```

So a real 450-triple run is refused by arithmetic and reports `NOT_MEASURED`, not
because anything leaked. `CAPTURE_MAX_RUN_BYTES` (256 MiB) is the right bound for
the archive and is unreachable while the row bound guards the file.

### 2c. Duplicate `CaptureError` class — **CONFIRMED (low)**

Identical class defined twice in `payload_canaries.py`:

- `:346-348` (before `RunCapture`)
- `:497-499` (after `read_captures`, immediately before `merge_reports`)

The second shadows the first; behaviour is unaffected because both are the same
`ValueError` subclass with the same docstring, but it is a dead/duplicated
definition and should be collapsed to one.

---

## 3. Other requested inspections

### Real runner supplies no manifest — **BLOCKER (unchanged from the inventory)**

`run_triple_v5` builds `GatewayV5(case, detector, Vault(":memory:", _ORG),
AuditLog(":memory:"), MaskCache(256), capture=True)` (`harness.py:1218-1219`) —
`capture=True` but **no `manifest=`**. `GatewayV5.capture()` then packages
`manifest=self._manifest or CanaryManifest(canaries=())` (`harness.py:290-293`),
so the persisted row carries zero canaries; `_capture_problem` returns "…carries no
manifest with canaries" (`payload_canaries.py:838-841`) and `check_run` is
`NOT_MEASURED`.

Worse, there is **no production manifest builder at all**. Grep over
`bench/agentpii5/*.py`: `CanaryManifest(...)` is constructed only at
`harness.py:291` (empty fallback), `test_payload_canary_integration.py:128`,
and the two `test_reportjson.py` sites. The construction-time ground truth the
module's whole premise depends on (`payload_canaries.py:1-33`) exists **only in
tests**. A paid 450 rerun today would be unmeasured by construction.

### Real model-bound path declares 0 neighbours — **[high]**

`_manifest_for` returns `pc.CanaryManifest(canaries=tuple(specs),
source="case-construction")` (`test_payload_canary_integration.py:128`) with
`neighbours=()` default. Only the synthetic unit fixture has neighbours
(`payload_canaries.py:757-763`). S02's over-masking half is unmeasured on the
model-bound path.

### Readback no longer reconstructs from `mentions` — **PASS**

`check_run` (`payload_canaries.py:845-878`) now calls `read_captures` +
`scan_captures`; `grep -n mentions payload_canaries.py` finds none in the read
path. `_delivered_from_run` (`:928-945`) reads captures too — but it has **no
production caller**; only `test_reportjson.py:498,655` call it. It is test-only
residue of the old design and a decision is needed: keep it explicitly as a
test helper or delete it.

### Manifest without capture → `NOT_MEASURED` — **PASS**

`_capture_problem` (`:833-841`) returns the "no `.canary.jsonl` artifact" sentence
before any scan; the integration test's negation asserts both this and the
unknown-version manifest (`test_payload_canary_integration.py:311-326`). The
sentence names the artifact suffix.

### Duplicate / missing capture rows, resume & append — **FAIL (medium)**

- **No dedup.** Probes: appending the same `(case_id, repeat)` twice yields
  `read_captures → 2` and `check_run → MEASURED` with `hidden =
  ('model_input:h','model_input:h')`. `merge_reports` (`:502-534`) sums every
  row; nothing keys on `(case_id, repeat)`. A resumed/appended run therefore
  double-counts hidden canaries and leaks.
- **No reconciliation of captures vs triple rows.** Excluded / budget-refused
  triples write no capture by design (`harness.py:1504-1508`) and the writer
  never records how many triples were skipped. A reader cannot tell "450 triples,
  N unmeasured/excluded" from a complete battery; the denominator silently
  shrinks.

### Size bounds — **FAIL** (see §2b). No per-line bound exists; the archive bound
is never the one that fires.

### Real PII in artifact vs public/meta — **PASS for the named surfaces, boundary to hold**

The capture artifact deliberately stores pre-mask `real_text` (measured 3,699
bytes of real corpus text per row; ~1.66 MB over 450 rows). It is **not** a
`RUN_FILES` entry and `records.run_file` refuses unknown names
(`records.py:616-620`), and the sink is a bare run-dir path
(`harness.py:1449-1455`). `test_unmeasured_canaries_make_the_public_file_incomplete`
asserts the public file carries no `REAL_NAME/REAL_PHONE/FAKE_NAME` (PASS), and
`public_is_an_allowlist` PASSes. **Residual:** the artifact lives **inside the run
directory**; any future copy/sync/publish that globs the run dir rather than
iterating `RUN_FILES` would carry raw PII. Worth an explicit test pinning that the
run-dir publisher excludes `*.canary.jsonl`.

### Report surfaces — **PASS (the old §6 defect is fixed)**

`report.py:954-969` prints `СТАТУС`/`ПРИЧИНА` and suppresses rows when not
MEASURED; `.oracle.json` carries `canary_status`/`canary_reason`
(`report.py:1128-1133`); `reportjson` carries `canary_status`, `canary_reason`,
`canary_by_boundary`, `canary_neighbour_damage`, `canary_unreached`, and feeds
`incomplete`/`incomplete_reasons` (`reportjson.py:164-270`). The empty-§1bis,
`{}`-oracle and no-canary-field defects of the inventory are closed.

---

## 4. Exact repair surface (bounded, minimal)

1. **[blocker] Build a construction-time manifest on the real path and pass it.**
   Add a production manifest builder that, at case start, records each case's
   declared PII literals with the boundary they were written to and the
   non-PII neighbours the case itself wrote; then
   `GatewayV5(..., capture=True, manifest=<that>)` at `harness.py:1218`. Without
   this, `check_run` is `NOT_MEASURED` forever. This is the largest missing piece.
2. **[blocker] Fix the size bound.** Check each JSONL **line** against
   `CAPTURE_MAX_ROW_BYTES` and the file/archive total against
   `CAPTURE_MAX_RUN_BYTES`; do not compare file size to the row bound
   (`payload_canaries.py:463-474`).
3. **[blocker] Repair the three `test_reportjson` fixtures** (below) — they must
   write a capture artifact, not a manifest alone.
4. **[high] Snapshot `model_request` at delivery.** Capture the composed request
   in the last `_push` (or each push, keeping the last) instead of recomposing in
   `captured_payloads()`; then the boundary is delivered bytes and
   `recomposed == delivered` becomes a pinned fact.
5. **[high] Give the real manifest neighbours** and assert
   `len(neighbours) > 0` and `neighbour_damage == ()`.
6. **[medium] Dedup by `(case_id, repeat)`** on read (last row wins, or refuse a
   duplicate), so resume/append cannot double-count.
7. **[medium] Record and report the denominator**: captures written vs triples
   run, with excluded/partial triples named, so the measured N cannot shrink
   silently.
8. **[low] Collapse the duplicate `CaptureError`** to one definition and resolve
   `_delivered_from_run`'s test-only status.

## 5. Concrete fixtures the repair must add

1. **Real-runner manifest fixture:** one case → `run_triple_v5` → `drive_v5` →
   `check_run` returns `MEASURED` with per-boundary hidden counts, **without any
   test assigning `gateway._manifest`**. (The existing integration test cannot
   catch the blocker because it assigns the manifest itself.)
2. **Row-bound fixture:** a run with valid rows summing over 4 MiB but under
   256 MiB must read back and measure; a single row over 4 MiB must be refused
   with the row's line named.
3. **450-row arithmetic fixture:** 450 × one measured row size passes `check_run`
   (the exact case that fails today).
4. **Duplicate/resume fixture:** the same `(case_id, repeat)` appended twice must
   not double-count `hidden`/`leaks`.
5. **Reportjson measured fixture:** write `canary_manifest.json` **and** a
   `.canary.jsonl` capture with the delivered bytes; then
   `unmeasured_canaries_are_never_printed_as_zero_leaks`,
   `measured_canaries_keep_their_counts_and_stay_complete` and
   `incomplete_is_explained` assert both halves.
6. **Divergence fixture:** a dialogue ending on a noted assistant turn must have
   `model_request` equal to the last request actually pushed — red under the
   current recomposition.

## 6. What this recheck does NOT claim

- No full S02 acceptance: manifest/neighbours on the real path remain absent and
  the saved 450 is still **0/450 measurable**.
- The `model_request` divergence was **not reproduced** byte-for-byte; the
  recomposition mechanism and the untested divergence path are confirmed, the
  single scripted probe ended on a `tool` push.
- No saved privacy miss is assigned to `detector`, `span`, `kv`, `result-payload`
  or `oracle`.
- No paid 450, no provider, no network, no children, no source/test/wiki/corpus
  write.

## 7. Compliance

Focused local tests: `test_payload_canaries` PASS 16/16,
`test_payload_canary_integration` PASS 5/5, `test_reportjson` FAIL 3/16; plus two
offline constructed probes and one offline harness probe (scripted connector
double, no provider). All run with `PYTHONDONTWRITEBYTECODE=1`. Total local
runtime well under the 12-minute / $0.12 cap. Only file written:
`research/hop-format-audit/evidence/reviews/s02-capture-readback-recheck-20260928.md`.
