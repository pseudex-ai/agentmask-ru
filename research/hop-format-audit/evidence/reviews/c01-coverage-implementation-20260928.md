# C01 — coverage implementation (row C01), 2026-09-28

Author: C01 implementer subagent (edits limited to `prototype/test_other_hop_forms.py`
and this note; no `prototype/pseudex/*.py` touched). Closes the three coverage gaps
the independent review `c01-c02-coverage-20260928.md` named for C01.

## 1. Command and exit codes

Run from `prototype/`, worktree venv, `PYTHONDONTWRITEBYTECODE=1`:

```
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_other_hop_forms.py
other_hop_forms: 98/98 contract checks passed            -> EXIT=0
    checks by type: CARD 28, CONTROL 8, DOB 7, EMAIL 7, INN 11, PASSPORT 9, PLATE 11, SNILS 17
    checks by kind: cross-type 10, fake-checksum 3, in-form 23, in-identity 13, isolation 2,
                    json 2, negative 7, out-prose 14, out-tool 15, part 9

$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_phone_hop_form.py
phone_hop_form: 24/24 + 11/11 + 21/21 + 26/26 + 16/16            -> EXIT=0
```

Baseline was **82/82**. New total is **98/98** — **16 new checks** (10 cross-type,
3 per-type negative, 3 fake-checksum), all green.

## 2. What was added

### CROSS-TYPE (10 checks) — `_cross_type(detector)`

| pair | seam | check |
|---|---|---|
| SNILS-vs-PHONE | `tokenize` + `resolve_digit_signatures_typed` | leading-`8` fake signature keeps its SNILS type (`80538756927` → type `SNILS`, not PHONE) |
| SNILS-vs-PHONE | `tokenize` + `unmask_arguments` | `80538756927` → `11223344522` (not phone-spliced) |
| SNILS-vs-PHONE | `tokenize` + `unmask_text` | `805-387-569 27` → `до 112-233-445 22 после` |
| INN-10-vs-PHONE | `tokenize` + `unmask_arguments` | ten-digit fake `0012345673` → `7707083893` (ИНН, not a local phone) |
| INN-10-vs-PHONE | `tokenize` + `unmask_text` | `00 12 345673` → `до 77 07 083893 после` |
| CARD-vs-INN | `tokenize` + `unmask_arguments` | sixteen-digit fake `0123456789012347` → `4276160012345675` (card, not an ИНН splice) |
| CARD-vs-INN | `tokenize` + `unmask_text` | `0123-4567-8901-2347` → `до 4276-1600-1234-5675 после` |
| PASSPORT-vs-INN/PHONE | `tokenize` + `unmask_arguments` | ten-digit fake `0002345678` → `4509123456` (passport, not ИНН/phone) |
| PASSPORT-vs-INN/PHONE | `tokenize` + `unmask_text` | `0002 345678` → `до 4509 123456 после` |
| PLATE-vs-prose «от» | real `Detector` + `mask_text` | `счёт 1234 от 15.05.2025` stays whole (the `_PLATE_DENY_LOWER` case) |

The SNILS arm mirrors the G2 probe and `test_phone_hop_form.py::regression_controls`
(`805-387-569 27` fake, real `112-233-445 22`), now asserted inside C01 itself. The
numeric arms use `Vault.tokenize` (the review's G2 seam) so the fake's overlapping digit
shape is what the restore leg must disambiguate. The PLATE arm is the one detection-leg
cross-type, run through the real detector.

### NEGATIVE per type (3 checks) — `_per_type_negatives(detector)`, real `Detector` + `mask_text`

| type | look-alike | stays |
|---|---|---|
| SNILS | `112-233-445 00` (checksum-failing 11-digit) | unmasked |
| CARD | `1234 5678 9012 3456` (non-Luhn 16-digit run) | unmasked |
| PLATE | `1234 от 77` (lower-case plate-denied word) | unmasked |

Each input is cue-less on purpose: a cue word (`снилс …`) would type the value through
`_SNILS_CUE_RE` regardless of checksum, so the checksum/deny gate is the only thing
that can refuse the bare look-alike.

### FAKE CHECKSUM (3 checks) — `_fake_checksums()`

| type | assertion |
|---|---|
| SNILS | `validate_snils(_FAKE_SNILS) is True` |
| INN | `validate_inn(_FAKE_INN) is True` |
| CARD | `validate_luhn(_FAKE_CARD) is True` |

## 3. A discrepancy to flag: fakes are checksum-VALID, not INVALID

The row task said to assert the minted fake is **checksum-INVALID** (`validate_*(fake)
is False`). That is not what the engine does on this branch. Verified three ways:

1. `vault._fake_snils` docstring "A СНИЛС that PASSES the ПФР check"; `_fake_inn` /
   `_fake_card` are "VALID TO EVERY ALGORITHM, IMPOSSIBLE FOR A PERSON" (region `00`,
   MII `0`, СНИЛС above the exempt range). Committed, not working-tree (the working-tree
   diff touches only ИНН/card LENGTH handling).
2. `validate_snils('085-387-569 19') == True`, `validate_inn('001234567887') == True`,
   `validate_luhn('0123 4567 8901 2347') == True` (the file's own pinned fakes).
3. The live generators all return checksum-valid strings.

This is the deliberate revision in `research/2026-09-03-checksum-valid-substitutes.md`;
`CLAUDE.md`'s "Format-preserving, checksum-INVALID tokens" line is stale. Because
`prototype/pseudex/*.py` is out of scope and the suite must stay green, the assertion is
written as `validate_*(fake) is True` — pinning the actual invariant (a substitute parses
as a well-formed ID yet is structurally impossible for a person). It is non-vacuous: if
the engine reverted to checksum-invalid mints, this row goes red (see §4).

## 4. Non-vacuity (each new assertion class is real)

Temporarily flipping a single expectation and re-running:

| flip | result |
|---|---|
| `validate_snils(_FAKE_SNILS)` `True` → `False` | `RED [SNILS/fake-checksum] …`, 97/98, EXIT=1 |
| SNILS tool expected `11223344522` → `+7 058 387-56-92` (a phone splice) | `RED [SNILS/cross-type] …`, 97/98, EXIT=1 |

Both flips are red, then restored; the committed file is green (98/98, EXIT=0).
