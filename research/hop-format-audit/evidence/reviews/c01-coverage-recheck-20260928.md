# C01 — coverage re-check (independent), 2026-09-28

Role: independent reviewer re-checking the C01 coverage implementation added by a
different subagent. I did not write `test_other_hop_forms.py`; I read the new
helpers, ran the suite, re-derived every new assertion from the engine myself, and
mutation-tested non-vacuity in a `/tmp` copy. Verdict: **ACCEPTED_FIX**.

## 1. Commands and exit codes

Run from `prototype/`, worktree venv, `PYTHONDONTWRITEBYTECODE=1`:

```
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_other_hop_forms.py
checks by type: CARD 28, CONTROL 8, DOB 7, EMAIL 7, INN 11, PASSPORT 9, PLATE 11, SNILS 17
checks by kind: cross-type 10, fake-checksum 3, in-form 23, in-identity 13, isolation 2,
                json 2, negative 7, out-prose 14, out-tool 15, part 9
other_hop_forms: 98/98 contract checks passed                 -> EXIT=0

$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_phone_hop_form.py
phone_hop_form: 24/24 value+form checks passed; ordinary-quantity controls passed
phone_hop_form: 11/11 additional regression controls passed
phone_hop_form: 21/21 extended-token controls passed
phone_hop_form: 26/26 shared-envelope current-form hops passed
phone_hop_form: 16/16 warm two-request notation hops passed   -> EXIT=0
```

Baseline 82/82 → 98/98. The delta is exactly the 16 new checks: 10 `cross-type`,
3 `negative` (per-type), 3 `fake-checksum`.

## 2. Independent reproduction of the new assertions

I did not rely on the test's own `_expect` machinery; each claim below was re-derived
with a separate probe script against the real engine.

### (a) SNILS leading-8 is NOT phone-spliced; digit-signature type stays SNILS

`805-387-569 27` is a checksum-valid СНИЛС (mod-101 control = 27). Its 11-digit
signature `80538756927` also matches the RU-phone shape `8 XXX XXX XX XX`, so the
restore leg could have read it as a phone. Independent probe:

```
tokenize('112-233-445 22','SNILS') under _fake_snils='805-387-569 27'
resolve_digit_signatures_typed({'80538756927'}, True) -> type='SNILS', value='112-233-445 22'
unmask_arguments('80538756927')  -> '11223344522'   (bare SNILS digits, no phone splice)
unmask_text('805-387-569 27')    -> 'до 112-233-445 22 после'
```

The full-signature (`digits`) index resolves first and returns the minted type; the
phone last-ten alias (`digits10`) does not win. Same for the INN-10 arm: signature
`0012345673` resolves to type `INN`, value `7707083893`. Confirmed.

### (b) Per-type negatives stay unmasked through the REAL `Detector` + `mask_text`

```
detect+mask('112-233-445 00')        -> unmasked   (validate_snils = False)
detect+mask('1234 5678 9012 3456')   -> unmasked   (validate_luhn  = False)
detect+mask('1234 от 77')            -> unmasked   (_PLATE_DENY_LOWER)
detect+mask('счёт 1234 от 15.05.2025')-> unmasked   (plate «от» deny; no DATE span fires)
```

Each is a real gate, not a "no regex matched" accident. Breaking the gate makes the
same text get masked (mutation, §4), so the assertions are load-bearing:

```
patch validate_snils -> True : '112-233-445 00'    -> spans=[SNILS]  -> masked '467-779-737 78'
patch validate_luhn  -> True : '1234 5678 9012 3456'-> spans=[CARD]   -> masked '0990 7522 5877 4874'
_PLATE_DENY_LOWER=frozenset() : '1234 от 77'        -> spans=[PLATE]  -> masked 'С267СН303'
_PLATE_DENY_LOWER=frozenset() : invoice            -> spans=[PLATE '1234 от 15']
```

### (c) The minted fake is checksum-VALID — `is True` is the correct invariant

```
validate_snils('085-387-569 19')  -> True
validate_inn  ('001234567887')    -> True
validate_luhn ('0123 4567 8901 2347') -> True
```

`vault._fake_snils` / `_fake_inn` / `_fake_card` are documented and committed to mint
checksum-VALID strings that are structurally impossible for a person (СНИЛС above the
exempt range; ИНН region `00`; card MII `0`) — the deliberate revision in
`research/2026-09-03-checksum-valid-substitutes.md`. The row task's "assert
`validate_*(fake) is False`" premise is therefore wrong for this branch, and the
implementer was right to assert `is True`. The `is True` form is non-vacuous: it pins
that the form-adaptation path did not corrupt the checksum, and a revert to
checksum-invalid mints goes red (§4).

**Stale doc flagged (not a C01 blocker):** `CLAUDE.md:473-474` and
`wiki/INVARIANTS.md:595` still say substitutes are "checksum-INVALID". That is stale
against the committed engine; it should be corrected in a docs change, but it does not
affect this coverage verdict.

## 3. Mutation test (non-vacuity), in `/tmp`, not the repo

Copied the test to `/tmp/test_other_hop_forms_flip*.py` (run with
`PYTHONPATH=prototype`, repo file untouched):

| flip | result |
|---|---|
| cross-type: SNILS tool expected `"11223344522"` → `"WRONG-CROSS-TYPE"` | `RED`, 97/98, EXIT=1 |
| checksum: `validate_snils(_FAKE_SNILS), True` → `False` | `RED [SNILS/fake-checksum]`, 97/98, EXIT=1 |

Both red, then restored; the committed file is green (98/98, EXIT=0). Both the
cross-type and the fake-checksum assertion classes are non-vacuous; the negative class
was additionally proven non-vacuous by gate-mutation in §4(b) above.

## 4. Verdict

**ACCEPTED_FIX.** The 16 added checks are real, cross-type and per-type, run through
the real `Detector`/`mask_text` or the real vault signature index (not mock-only), and
each new assertion class goes red under a targeted mutation. The checksum assertion
correctly pins checksum-VALID (`is True`), matching committed engine behaviour. The
only residual item is the stale "checksum-INVALID" wording in `CLAUDE.md` /
`wiki/INVARIANTS.md`, which is a documentation defect outside the scope of this
coverage fix and does not block acceptance.
