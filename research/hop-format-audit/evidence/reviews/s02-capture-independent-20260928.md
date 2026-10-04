# S02 capture/readback — independent adversarial review (2026-09-28)

**Verdict: REJECT.** The S02 capture redesign is real and its focused greens all
pass, but one clause of the acceptance row is still unmet: **the report does not
show the denominator for old archives**. An old saved run (triples journal
present, no `.canary.jsonl` capture) correctly reads `NOT_MEASURED`, but the
denominator is dropped — `coverage_known=False`, `capture/intervention/selected =
0/0/0` — so the acceptance sentence **“Old saved 450 remain 0/450 measured”** is
not produced. It should be `0/450` (0 captures against the 450 executed
intervention arms the triples journal names), and the machine to compute that
denominator already exists and is simply bypassed.

Read-only on code: no `.py` was edited. One throwaway probe script per finding,
run from `/tmp`. Only file written: this one.

---

## 1. Commands run (all green) — `PYTHONDONTWRITEBYTECODE=1`, from `prototype/`

| Command | Exit code | Result |
|---|---|---|
| `.venv/bin/python -m bench.agentpii5.test_payload_canary_integration` | 0 | PASS (6/6 checks) |
| `.venv/bin/python -m bench.agentpii5.test_reportjson` | 0 | PASS (15/15 checks) |
| `.venv/bin/python -m bench.agentpii5.test_harness` | 0 | PASS (full battery) |

(Also run, for context: `.venv/bin/python -m bench.agentpii5.test_payload_canaries`
→ PASS 19/19.)

---

## 2. What the code inspection confirms is CORRECT

1. **Construction manifest from case-declared literals + raw bytes (not injected).**
   `GatewayV5.__init__` (`harness.py:248-253`) sets `_auto_manifest=True` when
   `capture=True` and no `manifest=` is passed; `run_triple_v5`
   (`harness.py:1262`) builds the gateway with `capture=True` and **no** manifest,
   so the real runner does not inject a manifest. `_capture_payload`
   (`harness.py:262-268`) calls `_manifest_at_delivery(case, manifest, name,
   real_text)` — placement is keyed on the **raw pre-mask** `real_text`, never the
   masked `text`. `_manifest_at_delivery` (`harness.py:154-201`) plants
   `case.base.pii` surfaces (full literals `item.value`, `item.canonical`, and the
   message slice) plus `case.base.plain`/`case.base.negatives` as **neighbours**,
   only where `surface_in(original, value)` holds against the raw payload. ✅

2. **`model_request` fixed at the production mask call.** `GatewayV5._on_masked_request`
   (`harness.py:290-292`) captures `json.dumps(masked)` / `json.dumps(self._transcript)`;
   it is invoked from `RealGateway._push` (`bench/agentpii4/gateway.py:149-165`)
   inside the same call that runs `mask_messages`, before any later `note` mutates
   the transcript. Pinned by `test_model_request_is_snapshotted_before_later_notes`
   (PASS). ✅

3. **Per-row / per-run limits.** `read_captures` (`payload_canaries.py:459-514`)
   reads each line with `readline(CAPTURE_MAX_ROW_BYTES + 1)` (per-row 4 MiB) and
   accumulates `total` against `CAPTURE_MAX_RUN_BYTES` (per-run 256 MiB). ✅

4. **Duplicate refusal and missing-I reconciliation** — see §3.

---

## 3. Adversarial probes (throwaway scripts in `/tmp`)

### 3a. Duplicate case/repeat — REFUSED ✅

Called `payload_canaries.append_capture(rd, "dup", run)` twice with the same
`(case_id, repeat)` then `read_captures(rd)`.

```
DUPLICATE: refused -> dup.canary.jsonl:2: duplicate capture for ('same', 0); first row at dup.canary.jsonl:1
```

### 3b. Missing I-arm capture vs triple journal — FLAGGED ✅

Two complete I-arm triples, only the first captured; `payload_canaries.check_run`.

```
MISSING-I: status=NOT_MEASURED coverage_known=True capture=1 inter=2 sel=2
MISSING-I reason: capture coverage 1/2 I arms; missing [('second', 0)]; unexpected []
```

### 3c. Neighbour adjacent to a protected value — NOT DAMAGED ✅

`payload_canaries.scan(make_canary_fixture().manifest, fixture.delivered)` →
`neighbour_damage = []`; replacing a neighbour with `***` reds only the neighbour
(`model_input: 'подтвердить заказ 4838'`), no invented leak.

### 3d. Old archive with NO manifest → NOT_MEASURED (status correct) ⚠️

Empty dir (no manifest, no capture): `check_run` → `NOT_MEASURED`, `ok=False`,
reason names the missing artifact. Correct on status and “never clean”.

### 3e. Old saved 450 — denominator dropped ❌ (the defect)

A run directory with a **450-row `*.triples.jsonl`** (all `complete` with an `I`
arm) and **no `.canary.jsonl` capture**:

```
check_run: coverage_known=False capture=0 inter=0 sel=0
```

while the denominator IS derivable from the same journal:

```
expected I-keys: 450  selected triples: 450
```

So the report prints `СТАТУС: NOT_MEASURED` but the `ЗАХВАТЫ: 0/450 …` line is
omitted (`report.py:955` gates it on `coverage_known`), and the machine report's
`canary_capture` is `{"known": false, "captured": 0, "intervention": 0, "selected": 0}`
instead of `0/450`. The acceptance sentence “Old saved 450 remain 0/450 measured”
is not produced; an operator sees an unmeasured run with **no** denominator, i.e.
it cannot be told from an empty/unselectable run.

---

## 4. Smallest reproducible counterexample

```python
# from prototype/, .venv/bin/python
import json, pathlib, tempfile
from bench.agentpii5 import payload_canaries as pc
with tempfile.TemporaryDirectory() as tmp:
    rd = pathlib.Path(tmp)
    # an old saved run: triples journal present, capture artifact absent
    (rd / "old.triples.jsonl").write_text("".join(
        json.dumps({"case_id": f"c{i:03d}", "repeat": 0, "status": "complete",
                    "arms": {"I": {}}}) + "\n" for i in range(450)),
        encoding="utf-8")
    r = pc.check_run(rd)
    print(r.status, r.coverage_known, r.capture_rows,
          r.intervention_rows, r.selected_rows)
    # observed:   NOT_MEASURED  False  0  0  0
    # expected:   NOT_MEASURED  True   0  450  450   ("0/450 measured")
```

A single complete I-arm triple (no capture) reproduces the same defect
(`selected_rows == 0` instead of `1`); 450 is only the scale named by the clause.

## 5. Code location

`prototype/bench/agentpii5/payload_canaries.py`, `check_run`, lines 932–934:

```python
    empty = _capture_problem(captures)
    if empty:
        return not_measured(empty)          # early return: denominator never computed
```

`_expected_capture_keys(run_dir)` (line 936, which reads the triples journal and
yields `(expected_I_arms, selected_triples)`) is only reached when `_capture_problem`
returns `""` — i.e. never for a zero-capture archive. The fix is to run
`_expected_capture_keys` before the `_capture_problem` early-return (or to fold
its result into the empty-capture `NOT_MEASURED`), so the old-archive report
carries `coverage_known=True, capture_rows=0, intervention_rows=450,
selected_rows=450`.

---

## 6. Compliance

- No provider, no network, no paid run, no model. All probes are offline and run
  under `PYTHONDONTWRITEBYTECODE=1` with `.venv/bin/python`.
- No source/test/wiki/corpus file edited; probes written to `/tmp` only; one
  markdown evidence file written.
- Focused greens do NOT override the gap: the three named suites pass, but none of
  them asserts a **0/450 denominator for a zero-capture archive** (the existing
  coverage test `test_capture_rows_cover_every_executed_intervention` only covers
  the *partial*-capture case; `test_unmeasured_canaries_are_never_printed_as_zero_leaks`
  asserts status+reason and explicitly does not assert the denominator).
