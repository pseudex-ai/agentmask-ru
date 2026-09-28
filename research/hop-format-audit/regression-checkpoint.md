# Hop-format regression checkpoint — quick-test battery

- **Task:** `hop-sprint-regression-snapshot-20260927`
- **Role:** read-only regression operator. No agents, no network, no live LLM, no code changes.
- **Date:** 2026-09-27, 14:35:36 → 14:36:34 (+05:00). Total wall time ≈ 58 s.
- **Workspace:** `/Users/igor/Projects/Obscura-hop-audit` (worktree; no main/git/credential writes made).
- **Raw evidence:** `/private/tmp/hop-sprint-checkpoint-tests/` — one `<script>.log` per test,
  `summary.jsonl`, `summary.json`, plus the runner `run_all.py`.
- **Verdict in one line:** **19/19 scripts exited 0**, but this is **not a clean single-revision
  certification** — `pseudex/morph_places.py` changed *during* the battery and again immediately
  after it, so the run is pinned to two revisions and `test_product.py` straddles the change.

## Method

- Interpreter: `/private/tmp/agentpii5-connectors-venv/bin/python` (python3.12).
- Command shape per test, run **one at a time**, sequentially, from `prototype/`:
  `PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python <script>`
- Exit code captured **directly** from the child process (`subprocess.run(...).returncode`); output
  redirected to a per-test file. **No `tee`, no pipe** — nothing could shadow the child's exit code.
- Per-test timeout 900 s (none hit). One run per script; no retries.
- **Bundle:** real only. 18/19 scripts call `testkit.load_dev_bundle()` →
  `ASSETS.load(build_plaintext())` from `licensing/pack.py` (real authored tuning + real bulk, in
  process); `vault_test.py` is vault-only and needs no detector. `test_localui.py` and
  `test_perf_masking.py` additionally start the **real** licensing server on a loopback port and
  acquire a real lease (`bundle=5e113b9c1ba1c0d7`). No mocks, no stubs, no external network, no
  live LLM (`test_loop.py` runs the loop deterministically).
- No datasets generated; no broad external corpora run.

## Engine revision snapshot (four watched files)

| file | at battery start (14:35:36) | mid-battery (test 8, 14:35:44→14:35:56) | end of battery (14:36:34) | after battery (14:37:22) |
|---|---|---|---|---|
| `pseudex/redact.py` | `ea9c47f8…c58a` | unchanged | `ea9c47f8…c58a` | `ea9c47f8…c58a` |
| `pseudex/morph_places.py` | `0cfbd081…f9cc` **(A)** | → `cd6c069f…93d7` **(B)** | `cd6c069f…93d7` (B) | → `b01a820c…ea1d` **(C)** |
| `pseudex/vault.py` | `048a4f1c…1646` | unchanged | `048a4f1c…1646` | `048a4f1c…1646` |
| `pseudex/spoken.py` | `8a0093bc…97e1` | unchanged | `8a0093bc…97e1` | `8a0093bc…97e1` |

Full digests:

- `redact.py` `ea9c47f8dfc677670112e6651e15f23383c68d159196a0fa8c46fd79fd52c58a`
- `morph_places.py` A `0cfbd08199981869b174c472fdde8418f9392c7c91c4e5b94105dfbf6be1f9cc`
- `morph_places.py` B `cd6c069f0eba0b4248fb982d38a0fd88509077bde256da5b0ced6d8ae07593d7`
- `morph_places.py` C (live after the run, mtime 14:37:22) `b01a820cd48872e8689228ccf73cfc08ecc54b959fc838c7afe08e0501cfea1d`
- `vault.py` `048a4f1c941d9b474cdfda6d0bfde4087e5f3e69567636c4f5d2b57683931646`
- `spoken.py` `8a0093bc9f05a154c51e7f4249c0a643348dd3a87434773d2ea44a078a7977e1`

### Drift-attribution consequence

| rows | tests | revision of `morph_places.py` | status |
|---|---|---|---|
| 1–7 | phone, other-hop, atomic, name-subject, name-case, spoken-date, loop | **A** `0cfbd081` | green, but green **on A only** |
| 8 | `test_product.py` | **A → B during the run** | **DRIFTED — not attributable to either revision** |
| 9–19 | vault, persona, overmasking, localui, hard-cases, names-morphology, credentials, 152fz, perf, argument-form, derived-forms | **B** `cd6c069f` | green, but green **on B only** |
| — | (no test) | **C** `b01a820c` is what is on disk now | **nothing was run against C** |

A green here is evidence about the revision named, not a standing pass. `morph_places.py` is
load-bearing for address/LOC and agent-form behaviour, so the address-heavy rows
(`test_hard_cases`, `test_other_hop_forms`, `test_product`) are the ones most exposed to the
A/B/C movement.

## Results (exit codes, one run each)

| # | script | exit | time | engine | terminal line (actual tail) |
|---|---|---:|---:|---|---|
| 1 | `test_phone_hop_form.py` | 0 | 1.41 s | A | `phone_hop_form: 11/11 additional regression controls passed` (plus 24/24 value+form) |
| 2 | `test_other_hop_forms.py` | 0 | 1.02 s | A | `other_hop_forms: 66/66 contract checks passed` — + **2 open questions** (below) |
| 3 | `test_atomic_form_adversarial.py` | 0 | 0.99 s | A | `atomic_form_adversarial: 24/24 literal checks passed` |
| 4 | `test_name_subject_form.py` | 0 | 1.35 s | A | `name_subject_form: 18/18 checks passed` |
| 5 | `test_name_case_regression.py` | 0 | 1.39 s | A | `name case regression OK — …the gender-blind observer is the side that was wrong` |
| 6 | `test_spoken_date_form.py` | 0 | 0.97 s | A | `spoken_date_form: 7/7` |
| 7 | `test_loop.py` | 0 | 0.93 s | A | `PASS — model saw only tokens; tool received real values.` |
| 8 | `test_product.py` | 0 | 12.03 s | **A→B** | `tool schemas OK — описания на любой глубине, три формы, enum и имена целы` — **DRIFTED** |
| 9 | `vault_test.py` | 0 | 0.17 s | B | `survives restart (detok still works): +7 999 111 22 33` |
| 10 | `test_persona_defects.py` | 0 | 4.68 s | B | `все 10 дефекта прогона персон закрыты` |
| 11 | `test_overmasking.py` | 0 | 5.04 s | B | certifies ≥98.9%; **6 false masks remain** (see caveats) |
| 12 | `test_localui.py` | 0 | 5.13 s | B | `local UI surface OK — closed to anonymous callers, reveals audited, requests billed apart from entities` |
| 13 | `test_hard_cases.py` | 0 | 9.35 s | B | `hard cases OK — detected, restored, and nothing over-masked` |
| 14 | `test_names_morphology.py` | 0 | 1.87 s | B | `names OK — gender and case agree, and a re-inflected token still resolves to the real person` |
| 15 | `test_credentials.py` | 0 | 1.25 s | B | `ВСЁ ЧИСТО` |
| 16 | `test_coverage_152fz.py` | 0 | 1.24 s | B | `152-ФЗ coverage OK — 22 types caught and typed correctly, 8 look-alikes left untouched` |
| 17 | `test_perf_masking.py` | 0 | 3.22 s | B | `ALL PERF-MASKING TESTS PASSED` |
| 18 | `test_argument_form.py` | 0 | 3.27 s | B | `форма аргумента принадлежит агенту, содержимое — волту` |
| 19 | `test_derived_forms.py` | 0 | 2.73 s | B | `производные подмены возвращаются производными настоящего значения в конвенции модели` |

## Error-tail inspection — what is *not* a clean pass

Read from the actual logs, not from the exit codes alone.

1. **`test_overmasking.py` (row 11) is a bounded pass, not 100 %.** It exits 0 because it certifies
   "не ниже 98.9 %"; observed 99.5 % (6/1134). The six real false masks are printed and are
   assistant/loanword-shaped: `алиса` ×2, `алекса` ×2, `латиной`, `монти` (the last from "Монти
   Пайтона"). Hand-written business phrases: 42/42 untouched (contract zero). The residual is a
   real over-masking cost on conversational/assistant text and must not be reported as "clean".
2. **`test_other_hop_forms.py` (row 2) carries two unresolved domain questions** — explicitly
   "neither pass nor fail": (a) `'05.06.2025'` is read day-first with no dd.mm/mm.dd rule when both
   fields ≤ 12; (b) a 2-digit plate region (`А123ВС77`) mints a 3-digit one, and "region width" is
   not yet part of the current-sender form contract. 66/66 is a score over the pinned contract, not
   a resolution of these.
3. **Environment warnings, correctly *not* failures.** `test_perf_masking.py`,
   `test_persona_defects.py`, `test_localui.py` log `PSEUDEX_ADMIN_TOKEN was not set — generated a
   per-process one`; that is the harness not exporting the container's token, expected for a
   single-process test. `test_localui.py` also shows one lease 429 (`too_fast: one grant per
   second`) that the client's own 3-attempt retry absorbs — normal, not a defect.
4. **No traceback, assertion error, or non-zero exit appears anywhere in the 19 logs.** Grep for
   `Traceback|Error|FAIL|Exception` returns only the expected warnings/questions above and
   PASS-named checks.

## Scope limits of this checkpoint

- One run per script by instruction; **no re-run against the live revision C** (`b01a820c`), so
  nothing here certifies the current on-disk engine.
- `test_product.py` is the one **drifted** result and should be treated as unverified until re-run
  against a frozen revision.
- Not exercised: eval/quality datasets (`make_*`/`eval_*`), external corpora (NEREL, PII-Bench),
  the e2e container gates, and the browser render test (`test_localui_renders.py`, needs
  playwright/chromium). Those were out of scope and remain open.
- `redact.py`, `vault.py`, `spoken.py` were byte-stable across the whole window; no drift to mark
  for them.

## Reproduction

```bash
cd /Users/igor/Projects/Obscura-hop-audit/prototype
PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_phone_hop_form.py
# … one at a time, in the order of the table above; raw logs:
ls -l /private/tmp/hop-sprint-checkpoint-tests/
```

Budget: local-only execution (no paid calls, no network); one run per test, no retries.
