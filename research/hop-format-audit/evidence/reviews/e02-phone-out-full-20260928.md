# E02 PHONE-OUT (full) — independent read-only adversarial review (2026-09-28)

Row **E02** of the 19-row hop-format sprint: the **PHONE OUT** path. Candidate changed
`prototype/pseudex/redact.py` and `prototype/pseudex/vault.py` so that (1) a phone token is no longer
recognised as a numeric prefix of a longer token and (2) the leftover of an extended known substitute
is reported through `residual_tokens` / `surviving_substitutes`. Pinned test:
`prototype/test_phone_hop_form.py` (`extended_phone_is_not_partially_restored` + the full form matrix
in `main()`).

**ACCEPTANCE CLAUSE for E02:** BOTH OUT paths (tool and answer) must return the correct PHONE in the
form the AGENT chose; an extra agent-added digit must not produce a real/fake hybrid;
`/unmask_arguments` must report a residual and the tool must not receive a corrupted phone.

## Verdict: **REJECT**

The SUFFIX extension is handled, but a **PREFIX** extension of the same known fake produces a
real/fake hybrid on BOTH out paths and is **not** flagged residual; an **inserted** digit is correctly
left unchanged but is also **not** flagged residual. Smallest reproducible counterexample below.

## 1. Recomputations of the accepted suites

Run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python` (Python 3.12.12).

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_phone_hop_form.py` | 24/24 value+form · 11/11 regression · 9/9 extended-token · 26/26 shared-envelope · 16/16 warm | **0** |
| `.venv/bin/python test_argument_form.py` | all PASS | **0** |

Both suites pass. The pinned `extended_phone_is_not_partially_restored` covers **only the SUFFIX
shape** — `("+797955533221", "8 (979) 555-33-221")` — which is why the PREFIX and INSERTED gaps below
are invisible to it.

Candidate hashes (recomputed here): `redact.py`
`1e1dec28975bcba921c71b90aab6b6fa69ee01ee3a4e117985777c1beff96833`, `vault.py`
`800b302e75199269892fa443b1214eae78b49013b5ddb5169b6a3832487891d2`. `git rev-parse HEAD` = `9c5acbb`.
`test_phone_hop_form.py` is untracked (new).

## 2. Independent probe

Probes in `/tmp/probe_e02.py` and `/tmp/probe_e02_focus.py`, mirroring the test file's own helpers
(`tool_value` → `unmask_arguments`, `answer_value` → `unmask_text`, `residual_tokens`,
`surviving_substitutes`, `canonicalize`). Fresh mint via `patch("pseudex.vault._fake_phone",
return_value="+79795553322")` over real `+79162148803` — the REAL restore path, not a re-import of the
suite's constants.

**Fixture:** real phone `+79162148803` (11 digits `79162148803`), fake minted `+79795553322`
(11 digits `79795553322`, last-10 `9795553322`).

```
=== one added digit, both legs ===
suffix +7        '+797955533221'   -> tool/answer unchanged, residual ['+797955533221']   OK
suffix 8         '8 (979) 555-33-221' -> unchanged, residual ['8 (979) 555-33-221']       OK
prefix 9         '979795553322'    -> tool/answer '979162148803'   (HYBRID), residual []   FAIL
prefix 8         '879795553322'    -> tool/answer '879162148803'   (HYBRID), residual []   FAIL
prefix 8 grouped '8 797 955 533 22' -> tool/answer '8 791 621 488 03' (HYBRID), residual [] FAIL
insert mid       '+797955533292'   -> unchanged (no corruption) but residual []            FAIL
```

The four-notation matrix (international/domestic/local/grouped × 3 real sources × tool+answer) passes
24/24 with the real digits in the agent's chosen form; ordinary unknown phones
(`+791234567890`, `+79123456789`, `8 (900) 000-00-00`) pass through unchanged and are **not** flagged;
`/unmask_arguments` with a SUFFIX-extended fake as the only content returns it unchanged and
`surviving_substitutes(..., for_tool=True)` flags it. 48/56 probe checks passed; the 8 failures are the
PREFIX/INSERT cases above.

## 3. Smallest reproducible counterexample

1. Mint the row: real `+79162148803`, `_fake_phone` → `+79795553322`.
2. The agent writes a **known fake with one PREFIX digit**: `979795553322`
   (12 digits = `9` + `79795553322`).
3. `unmask_arguments('{"phone": "979795553322"}')` → `{"phone": "979162148803"}`
   (tool receives a corrupted 12-digit hybrid — neither the fake nor the real).
4. `unmask_text("979795553322")` → `"979162148803"` (answer leg, same hybrid).
5. `residual_tokens("979795553322")` → `[]` and `surviving_substitutes(..., for_tool=True)` → `[]`
   (silent — the `/unmask_arguments` endpoint reports nothing, with a 200).

`979162148803` = agent's spurious `9` + the real `79162148803`. The `8`-prefix twin `879795553322` →
`879162148803`, and the grouped `8 797 955 533 22` → `8 791 621 488 03` — the same defect. This is
precisely the "real/fake hybrid" and "corrupted phone" the clause forbids, on BOTH legs, with no
residual.

## 4. Root cause (code location)

- `prototype/pseudex/redact.py:1225` — `_restore_reformatted_spans` resolves a **12-digit** run
  through the phone **last-10** fallback `resolved.get(digits[-10:])`. A 12-digit run whose trailing
  ten digits equal a minted phone's `digits10` therefore resolves even though the run is not a phone.
- `prototype/pseudex/redact.py:1479-1480` — `_digits_in_form_of` then keeps the two leading digits as
  a prefix and splices the real last ten: `_same_shape(written, written_digits[:-10] +
  real_digits[-10:])`. `written_digits[:-10]` is exactly the spurious prefix digit (plus the fake's
  `7`), so the real phone is laid under the agent's extra digit → hybrid.
- `prototype/pseudex/redact.py:2760-2772` — `_extended_phone_runs` probes the tail as `digits[1:11]`
  (drop the country code, keep the next ten), which only matches the **SUFFIX** shape. A prefix or an
  interior insertion shifts the tail, so `residual_tokens` / `surviving_substitutes` report nothing.
  The restore path and the residual detector use **different slices** (`digits[-10:]` vs
  `digits[1:11]`), which is the inconsistency that makes the corruption silent.

The last-10 fallback should fire only for phone-shaped runs of 10 or 11 digits (a phone is never 12
digits), and `_extended_phone_runs` should match every 11-digit window that resolves to a minted
PHONE, not only the suffix tail. **Not fixed here** (REJECT — read-only review).

## 5. Terminal verdict

**REJECT.** The SUFFIX path satisfies the clause, but a one-digit **PREFIX** extension of a known fake
(`979795553322` / `879795553322`) returns a real/fake hybrid (`979162148803` / `879162148803`) on both
tool and answer, and is not flagged residual — the tool silently receives a corrupted phone. An
interior **inserted** digit is left unchanged but also unreported.

No source, test, wiki, corpus or saved run was modified; only this report was written. No network, no
provider, no child sessions.
