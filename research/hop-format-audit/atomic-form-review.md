# Atomic-form patch — independent skeptical review

Scope: `_atomic_in_form_of` / `_plate_in_form_of` / `_phone_in_form_of` and their
callsites, against `docs/tz-hop-form-adaptation.md` §1. Engine untouched; only
`prototype/test_atomic_form_adversarial.py` and this file were written. No
children, no network, no paid calls. Baseline `9c5acbb` compared in-process.

## 1. What checks out

Both suites the other agents wrote are green on this working tree:
`test_other_hop_forms.py` 66/66, `test_phone_hop_form.py` 24/24 + 11/11 controls.
Reproduced independently, with expectations taken from §1 and from the ГОСТ map,
never from the tested function:

- **IN (`_token_for_text`)** — the substitute takes the *mention's* form for
  PHONE/SNILS/INN/CARD/PASSPORT/DOB/DATE/EMAIL/PLATE; content still comes from
  the vault row. Reused entity: each later mention keeps its own notation while
  one row is reused (`test_phone_hop_form.reused`, `_in_identity`).
- **OUT tool (`unmask_arguments`) and OUT prose (`unmask_text`)** — both take the
  agent's form. A typed numeric row is never re-read as a phone or a date: the
  CARD checks (`0418 8633 8391 7819` → `4276 1600 1234 5675`;
  `0418863383917819` → `4276160012345675`; `0418-8633-8391-7819` →
  `4276-1600-1234-5675`) and the SNILS/phone ten-digit overlap row keep type.
  `date_form.same_notation` gating keeps `11.07.75` → `2.06.75` (no invented
  zero padding) and ISO reordering correct.
- **Plate alphabet/case** — Latin write `X456YK777` → `A123BC777`, lower →
  `a123bc777`; a real `2`/`3`-digit region mismatch returns the value unchanged
  rather than guessing (`_plate_in_form_of` refuses when letter counts differ).
- **Email case** — `ABCDEFGH@EXAMPLE.RU` → `IVAN.PETROV@MAIL.RU`; minted lower
  case returns lower. No identity change in any of the above.

## 2. Confirmed defect — a copied look-alike inside a phone run restores a HYBRID

`prototype/test_atomic_form_adversarial.py::_attack_homoglyph_inside_the_run`
(2 RED, 16/18 pass; the other 16 are the controls above). Reproducer, pinned
fake `+79795553322`, customer `8 916 214-88-03`:

| | literal |
|---|---|
| input (agent's field) | `8 (979) 555-33-О2`  (Cyrillic «О» at the last digit) |
| output, tool and prose | `8 (916) 214-88-О2` |
| expected per §1 | `8 (916) 214-88-О3` |

The output is **not** the customer's number and **not** the showable substitute:
the head `8 (916) 214-88` is real, the tail `О2` is the fake's. Mechanism: the
Cyrillic «О» is not in `_NUM_RUN`, so the run stops at index 14;
`_restore_reformatted_spans` gets `8 (979) 555-33-` only, and
`_atomic_in_form_of`'s `_same_shape` therefore never lays a real digit into the
final position. `normalize()` is applied in `_token_for_text` but not to the
written run before the signature is built.

**Preexisting or introduced?** Preexisting and *not* closed — and the patch
changes its shape for the worse. On the baseline (same probe, same vault):

| | baseline | patched |
|---|---|---|
| tool | `8 (979) 555-33-О2` (whole fake, consistent) | `8 (916) 214-88-О2` (hybrid) |
| prose | `8 (979) 555-33-О2` | `8 (916) 214-88-О2` |

Previously the agent's argument was a coherent (wrong) token that a schema
validator rejects; now it is a plausible-looking number that is half real. A
stricter E.164 check would still refuse it, but nothing about `-О2` says
"substitute", so the failure is quieter. This is the one item I would treat as a
pre-acceptance item, not a feature gap: §1 promises supported typos survive, and
the copied-homoglyph case is exactly the "literal fast path" §4 discusses.

Clean-run control (no homoglyph, same vault): `8 (979) 555-33-22` →
`8 (916) 214-88-03` — the defect needs the look-alike only.

## 3. Attacked and did NOT reproduce (so not claimed as solved either)

- Numeric-ID-vs-phone confusion via last-ten fallback: no reachable collision
  found. A 10-digit SNILS signature and an 11-digit phone signature are equal
  only by constructed coincidence, and `_lookup_typed` returns exact before
  tail, so the row keeps its own type.
- Numeric-ID-vs-date confusion: a 12-digit CARD written bare or with dots is
  spliced positionally, never re-read as a date (checked).
- Mixed plate script: an out-of-alphabet head (`A` at a Cyrillic position) is
  transliterated *by the mention's script*, which is consistent with the one
  map the engine owns; not counted as a defect, but it is a choice — a
  mixed-script mention cannot preserve both scripts, and the docstring's "each
  letter's alphabet" is only true per-position, not per-mention.
- Fresh vs reused entity: mint once, write many forms — each mention resolves to
  the same row with its own form (both suites).

## 4. Limits of this review

- PHONE fixtures are pinned through `_fake_phone`; SNILS/CARD/DOB likewise.
  Non-pinned rows were not fuzzed, so coverage is by representative form, not
  exhaustive.
- I did not exercise `service.py`/`proxy.py` end to end, streaming
  `unmask_chunk`, or the `shown_forms` expiry path; the verdicts are on
  `mask_text` / `unmask_arguments` / `unmask_text`.
- The DOB day-first ambiguity and 2-digit plate region remain open interpretation
  questions from `test_other_hop_forms.py`; I did not decide them.
- No claim is made that unsupported forms are solved; the reproducer asserts only
  the literals above and deliberately leaves the two open questions alone.
