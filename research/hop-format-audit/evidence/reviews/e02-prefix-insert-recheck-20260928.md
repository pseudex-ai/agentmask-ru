# E02 PHONE-OUT — re-check of the PREFIX/INSERT repair (2026-09-28)

Independent read-only re-check of the repair to the E02 REJECT (`e02-phone-out-full-20260928.md`).
The prior rejection: a known fake phone with one **PREFIX** or **INSERTED** digit produced a
real/fake hybrid on BOTH out paths and was not flagged residual. The repair touched
`prototype/pseudex/redact.py` in two places and extended the pinned test.

## Verdict: **ACCEPTED_FIX**

## 1. Code read

- `_restore_reformatted_spans` (`prototype/pseudex/redact.py:1193-1260`). The phone last-10 fallback
  is now gated at line 1231:
  `if hit is None and 10 <= len(digits) <= 11:` → `hit = resolved.get(digits[-10:])`.
  A 12-digit run is never a phone, so it no longer resolves through the `digits10` alias; it is left
  for the fragment path only (which does not apply to a 12-digit whole-run). The prior defect at the
  old `redact.py:1225` (`len(digits) >= 10`) is closed.
- `_extended_phone_runs` (`prototype/pseudex/redact.py:2767-2795`). For any 12-digit numeric run it
  deletes **each** position once (`for i in range(len(digits)): window = digits[:i] + digits[i+1:]`)
  and adds BOTH the 11-digit remainder and its 10-digit tail (`signatures.add(window)` +
  `signatures.add(window[-10:])`), then flags the run residual iff any signature resolves to a minted
  **PHONE** (`owners[signature][0] == "PHONE"`). This replaces the old suffix-only probe
  `digits[1:11]` (old `redact.py:2760-2772`) and covers suffix, prefix, and interior insertion, in
  both the `+7` and domestic `8` forms (the `window[-10:]` tail is what catches `8 (979) 555-33-221`).
- Test `prototype/test_phone_hop_form.py:289-322` (`extended_phone_is_not_partially_restored`) now
  iterates `altered = ("+797955533221", "8 (979) 555-33-221", "979795553322", "879795553322",
  "8 797 955 533 22", "+797955533292")` — suffix, prefix, and inserted shapes — asserting both legs
  return the input unchanged and `residual_tokens` is non-empty; plus an ordinary 12-digit control.

## 2. Recomputed suites

Run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python` (Python 3.12.12).

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_phone_hop_form.py` | 24/24 value+form · 11/11 regression · **21/21 extended-token** · 26/26 shared-envelope · 16/16 warm | **0** |
| `.venv/bin/python test_argument_form.py` | all PASS | **0** |

Note the extended-token count rose 9/9 → 21/21 (6 altered shapes × (2 legs + 1 residual) + 3
ordinary-control checks), reflecting the widened coverage.

## 3. Independent counterexample probe (`/tmp/e02_recheck.py`)

Fresh mint via `patch("pseudex.vault._fake_phone", return_value="+79795553322")` over
`Vault(":memory:","x").for_conversation("one").tokenize("+79162148803","PHONE")` — the real restore
path. For each of the six shapes, `unmask_arguments('{"phone": w}')` and `unmask_text(w)` must return
`w` unchanged, and `residual_tokens(w)` must be non-empty.

```
[PASS] '979795553322'        arg=unchanged text=unchanged residual=['979795553322']
[PASS] '879795553322'        arg=unchanged text=unchanged residual=['879795553322']
[PASS] '8 797 955 533 22'    arg=unchanged text=unchanged residual=['8 797 955 533 22']
[PASS] '+797955533292'       arg=unchanged text=unchanged residual=['+797955533292']
[PASS] '+797955533221'       arg=unchanged text=unchanged residual=['+797955533221']
[PASS] '8 (979) 555-33-221'  arg=unchanged text=unchanged residual=['8 (979) 555-33-221']
counterexamples: 6/6 passed
```

No hybrid on either leg; every one is flagged residual.

Four-notation matrix (international/domestic/local/grouped × 3 real sources × tool+answer):

```
matrix: 24/24 passed
```

Ordinary unknown phones pass through unchanged and are NOT flagged residual:

```
[PASS] ordinary '+791234567890'   arg=unchanged text=unchanged residual=[]
[PASS] ordinary '+79123456789'    arg=unchanged text=unchanged residual=[]
[PASS] ordinary '8 (900) 000-00-00' arg=unchanged text=unchanged residual=[]
ordinary: 3/3 passed
```

`TOTAL_FAILS 0`; script exit **0**.

## 4. Root-cause closure

The two prior failure locations are both fixed and now consistent:

- Restore (`_restore_reformatted_spans:1231`): the last-10 fallback fires only for 10/11-digit runs,
  so a 12-digit extended fake is no longer spliced with the real digits.
- Residual (`_extended_phone_runs:2783-2795`): all 12 single-deletion remainders (and their 10-digit
  tails) are probed against the minted PHONE signatures, so suffix/prefix/interior extensions are all
  reported — matching what the restore leg leaves unchanged. The old slice mismatch (`digits[-10:]` vs
  `digits[1:11]`) is gone.

## 5. Terminal verdict

**ACCEPTED_FIX.** The six prefix/insert/suffix counterexamples from the prior REJECT all return their
input unchanged on both `unmask_arguments` and `unmask_text`, and are each flagged non-empty by
`residual_tokens`; the four-notation matrix still restores the real digits 24/24; ordinary unknown
phones (`+791234567890`, `+79123456789`, `8 (900) 000-00-00`) pass through unchanged and are not
flagged. Both suites exit 0.

Artifacts: `redact.py` sha256 `6b82d121029657a5cda8a20c4611a564708162d51eb72f6409ba3f300df86f63`,
`test_phone_hop_form.py` `0065b2352b3ea34539d0fa004da8162cfdc3228d1428f04db87f265727401215`
(both untracked/new in the worktree), `git rev-parse HEAD` = `9c5acbb`.

No source, test, wiki, corpus or saved run was modified; only this report was written. No network, no
provider, no child sessions.
