# E05 declension — independent re-check of the repair (2026-09-28)

Re-check of the E05 **REJECT** from
`e04-e06-loc-independent-20260928.md` (declension was dropped for adjectival street names
absent from pymorphy's dictionary — «Зацепская» came back `на улице Зацепская` instead of
`…Зацепской`). The repair changed `prototype/pseudex/morph_places.py`:

- **(a)** `_is_genitive` (line 161) now requires the top parse to be `is_known` before freezing a
  word as a frozen genitive — pymorphy's spurious `Geox` genitive **GUESS** no longer freezes
  «Зацепская».
- **(b)** `_inflect_word` / `_inflect_parses` (lines 249–307) now declines a guessed `ADJF`
  (full adjective) parse when the dictionary has no known full-form reading; the `ADJS`
  short-form trap («ленна») is explicitly excluded. The already-in-target-case check moved into
  `_inflect_parses` over the filtered parses.
- Added `_declension()` to `prototype/test_location_hop_form.py` (2 new checks, 14→16).

Read-only on code; only this report written.

## 1. Read the changed functions

- `_is_genitive` (morph_places.py:161–179): `best = max(parses, key=score)` then
  `best.is_known and best.tag.case == "gent" and "ADJF" not in best.tag.grammemes`. The
  `is_known` gate is the change (a): a guessed genitive no longer freezes the word.
- `_inflect_word` (249–270): returns the word when **no** known full-form parse
  (`is_known and POS in {ADJF, NOUN, PRTF, NUMR}`) exists — UNLESS a guessed `ADJF` parse
  exists, in which case it filters `parses` down to the guessed `ADJF` (b). `ADJS` (short form)
  is excluded by construction.
- `_inflect_parses` (273–307): the already-in-target-case check
  (`any(parse.tag.case == case ...)`) now runs over the filtered parses, BEFORE the geographic
  (`Geox`) and gender filters — those filters can discard the very parse that proves no
  inflection is needed.
- `_declension()` (test_location_hop_form.py:176–194): mints with
  `patch("pseudex.vault._fake_place", return_value="г Казань, улица Кедровая, д 2, кв 5")`,
  then asserts `_prose("Живу на улице Кедровой, д 2")` == `"Живу на улице Зацепской, д 7"` and
  `_tool("на улице Кедровой, д 2")` == `"на улице Зацепской, д 7"`.

## 2. Test suites

Run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python` (Python 3.12.12).

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_location_hop_form.py` | `location_hop_form: 16/16 contract checks passed` | **0** |
| `.venv/bin/python test_location_form_adversarial.py` | `location_form_adversarial: 76/76 contract checks passed` | **0** |
| `.venv/bin/python test_derived_forms.py` | 17/17 PASS · `производные подмены возвращаются производными настоящего значения в конвенции модели` | **0** |

`test_location_hop_form.py` went 14/14 → 16/16, i.e. the two new `_declension` checks both pass.

## 3. Exact counterexample reproduced (independent probe)

Real `г Казань, улица Зацепская, д 7, кв 31`, fake patched to
`г Казань, улица Кедровая, д 2, кв 5`, then `Vault(":memory:", …).for_conversation(…)` +
`mask_text`. Public mask/restore path, real dev bundle, no LLM / no network.

```
MASKED: 'адрес: г Казань, улица Кедровая, д 2, кв 5'
unmask_text("Живу на улице Кедровой, д 2")          -> 'Живу на улице Зацепской, д 7'   PASS
unmask_arguments('{"address": "на улице Кедровой, д 2"}')
      -> {"address": "на улице Зацепской, д 7"}                                     PASS
```

Both legs now agree with the declined generic. This is the exact RED the prior review reported
(`…Зацепская…`), now `…Зацепской…`.

## 4. Guards still hold (independent probe)

| probe | result | want | verdict |
|---|---|---|---|
| `inflect_place("Ленина","loct")` | `Ленина` | `Ленина` | PASS (frozen genitive) |
| `inflect_place("Комиссарова","loct")` | `Комиссарова` | `Комиссарова` | PASS (frozen genitive) |
| `inflect_place("Победы","loct")` | `Победы` | `Победы` | PASS (frozen genitive) |
| `inflect_place("Солнечная","loct")` | `Солнечной` | `Солнечной` | PASS (known adjective declines) |
| `inflect_place("Зацепск","loct")` | `Зацепск` | `Зацепск` | PASS (unknown non-adjective stays) |

The `is_known` gate on `_is_genitive` does not unfreeze the dictionary-known genitives
(`Ленина`, `Комиссарова`, `Победы`), known adjectives still decline, and an unknown
non-adjective noun-like word is still left unchanged (the anti-typo guard is intact).

## 5. Terminal verdict

**E05 — ACCEPTED_FIX.** The exact `tool_chain-017` counterexample now restores
`на улице Зацепской, д 7` on both the prose and tool-argument legs, all three suites pass
(16/16, 76/76, 17/17), and the frozen-genitive / known-adjective / unknown-noun guards from the
pre-repair behaviour are preserved. Smallest counterexample was reproduced and is fixed.
