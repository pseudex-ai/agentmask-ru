# E04/E05/E06 LOC hop-form — independent read-only adversarial review (2026-09-28)

Rows **E04, E05, E06** of the 19-row hop-format sprint, one LOC surface. Candidate changes
`prototype/pseudex/morph_places.py` (+20/−), `prototype/pseudex/redact.py` (+469/−), and
`prototype/pseudex/vault.py` (+152/−) so that (1) a composite LOC never becomes a fake street + real
house, (2) the LOC's case/declension/markers/parts follow the current sender on every hop, and (3)
projections of one object stay one object with no history rewrite. Pinned tests:
`prototype/test_location_hop_form.py` (E04/E05), `prototype/test_location_form_adversarial.py`
(E04/E05/R0 controls), `prototype/test_derived_forms.py` (adjacent, E06-adjacent conversation scope).

## Acceptance clauses

- **E04** — a composite LOC must not become a fake street with a real house; two identical streets
  must not mix the two addresses; an apartment the agent omitted must not be added back.
- **E05** — LOC in prose, tool arguments, summary and template keeps its case, declension, markers
  (ул./переулок) and the parts the agent chose.
- **E06** — different projections of one object are actually one object; a NEW value version does not
  overwrite the OLD; tenant and conversation are isolated. `ACCEPTED_NO_CHANGE` is a valid outcome.

## Verdicts

| row | verdict |
|---|---|
| E04 | **ACCEPTED_FIX** |
| E05 | **REJECT** — declension is dropped for street names absent from pymorphy's dictionary (`Зацепская`) |
| E06 | **ACCEPTED_NO_CHANGE** |

## 1. Recomputations of the accepted suites

Run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python` (Python 3.12.12).

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_location_hop_form.py` | `location_hop_form: 14/14 contract checks passed` | **0** |
| `.venv/bin/python test_location_form_adversarial.py` | `location_form_adversarial: 76/76 contract checks passed` | **0** |
| `.venv/bin/python test_derived_forms.py` | all PASS · `производные подмены возвращаются производными настоящего значения в конвенции модели` | **0** |

All three suites pass. Neither LOC suite asserts **declension**: `test_location_hop_form.py` covers the
marker (`проезд`→`улица`) and the hybrid; `test_location_form_adversarial.py` covers marker spelling
(`ул.`/`улица`) and letter-case (R2/R3), and its header states the *kind* of street (`улица` vs
`проезд`) is deliberately left unasserted — but **declension is a different axis and is not pinned
anywhere**, which is why the E05 gap below is invisible to them.

Candidate hashes (recomputed here): `morph_places.py`
`b01a820cd48872e8689228ccf73cfc08ecc54b959fc838c7afe08e0501cfea1d`, `vault.py`
`800b302e75199269892fa443b1214eae78b49013b5ddb5169b6a3832487891d2`, `redact.py`
`6b82d121029657a5cda8a20c4611a564708162d51eb72f6409ba3f300df86f63`. `git rev-parse HEAD` = `9c5acbb`.

## 2. Independent probe

Probes in `/tmp/e04e05e06_probe.py`, `/tmp/e05_decl_probe.py`, `/tmp/e06_city_probe.py`, mirroring the
test files' own helpers (`mask_text` / `unmask_text` / `unmask_arguments` / `surviving_substitutes`,
fresh `Vault(":memory:", customer).for_conversation(convo)`, real dev bundle). No LLM, no network.

**E04** (all pass):
```
E04a tool/prose: omitted flat not added back       "г Казань, улица Зацепская, д 7"   PASS
E04b tool: cross-mix (street+house of A, flat of B) stays unresolved, no hybrid, no B-leak  PASS
E04b A -> own house, B -> own house, A still own house after B minted  PASS
E04c structured card (tool_chain-017 leaves) -> "ул. Зацепская, д. 7, кв. 31" (real street)  PASS
E04c no fake-street residual (surviving_substitutes == [])  PASS
```

**E06** (all pass):
```
E06a short mention "Ленина 14" links to the full "г. Москва, ул. Ленина, д. 14" — one object  PASS
     short prose/tool restore as written (no ул. added)  PASS
E06b new value (same street, д 9) is a distinct entity; д 7 still restores to д 7  PASS
E06b same street+house, different FLAT (кв 31 vs кв 32) — two entities, each its own flat  PASS
E06c tenant isolation: fragment of customer A stays fake for customer B (tool + prose)  PASS
E06d conversation isolation: fragment of convA stays fake for convB (tool + prose)  PASS
E06c same street+house in TWO cities (Чернь vs Красноярск, search_rank-000) = distinct objects  PASS
```

**E05** (markers/case/parts pass; **declension fails**):
```
E05a prose / tool street-leaf / summary all keep case+marker+parts  PASS
E05b marker spelling ул./улица kept on BOTH legs (current sender)  PASS
E05c marker «переулок» kept on BOTH legs  PASS
E05d declension: "Живу на улице Кедровой, д 2" (fake declined to loct)
     -> prose  "Живу на улице Зацепская, д 7"   (want "…Зацепской…")   FAIL
     -> tool   "на улице Зацепская, д 7"        (want "…Зацепской…")   FAIL
     -> tool street leaf "улице Кедровой" -> "улице Зацепская"         FAIL
```

The declension survives for street names pymorphy knows — `Солнечная→Солнечной`,
`Мятная→Мятной`, `Барбарисовая→Барбарисовой`, `Маросейка→Маросейке` — and correctly refuses frozen
genitives (`Ленина`, `Комиссарова`). It fails exactly for an adjectival street name absent from the
dictionary: `Зацепская` (the `tool_chain-017` street).

## 3. Smallest reproducible counterexample (E05)

1. Mint the row: real `г Казань, улица Зацепская, д 7, кв 31` (the `tool_chain-017` address).
   The fake is e.g. `г Казань, улица Кедровая, д 2, кв N`.
2. The agent writes the **fake street declined to the locative** (correct Russian): `Живу на улице
   Кедровой, д 2`.
3. `unmask_text("Живу на улице Кедровой, д 2", vault)` → `Живу на улице Зацепская, д 7`
   — the generic `улица` declined to `улице`, but the real street name stayed **nominative**.
4. `unmask_arguments('{"address": "на улице Кедровой, д 2"}')` → `на улице Зацепская, д 7`
   — same break on the tool leg; the street leaf `улице Кедровой` → `улице Зацепская`.

`на улице Зацепская` is broken Russian; the form no longer belongs to the current sender, and the real
value reaches the tool/answer in a grammatically corrupted shape — the exact `§1`/E05 obligation
("форма — от текущего отправителя").

## 4. Root cause (code location)

- `prototype/pseudex/morph_places.py:1622-1623` — `_street_like` (added this sprint) detects the
  sender's case via `street_case(model)` and inflects the real street with `inflect_place(street,
  case)`. For `model = "улице Кедровой"` this is `street_case → "loct"`, so the path is entered
  correctly.
- `prototype/pseudex/morph_places.py:260-261` — `_inflect_word` returns the word **unchanged** when no
  `is_known` full-form parse exists in the pymorphy3 dictionary. `зацепский` is not in the dictionary
  (the ADJF parse is `is_known=False`), so `inflect_place("Зацепская", "loct")` → `"Зацепская"`. The
  generic word (`улица`→`улице`) IS inflected, producing the mismatch `на улице Зацепская`.

The conservative "only inflect dictionary-known full forms" gate is a deliberate anti-typo guard (see
the comment at `morph_places.py:254-259`), but its cost is that **adjectival street names absent from
pymorphy's general dictionary lose their declension**, while the fake (drawn from the leased street
vocabulary) declines fine — so the model saw correct Russian and the tool/answer receives broken
Russian. The leased ГАР street vocabulary is not consulted for inflection. **Not fixed here** (REJECT —
read-only review).

## 5. Terminal verdicts

- **E04 — ACCEPTED_FIX.** The hybrid (`ул. Барбарисовая, д. 7, кв. 31`) is gone: the reassembled
  card restores the real street, a cross-mixed mention stays unresolved without leaking the other
  address, two same-street addresses keep their own houses, and an omitted flat is not added back.
  Independent probes and both LOC suites agree.
- **E05 — REJECT.** Markers (`ул.`/`улица`/`переулок`), letter-case and chosen parts are preserved on
  prose, tool-argument and summary legs, but **declension is dropped for street names absent from
  pymorphy's dictionary** (`Зацепская` from `tool_chain-017`), yielding `на улице Зацепская` on both
  legs instead of `на улице Зацепской`.
- **E06 — ACCEPTED_NO_CHANGE.** Full vs shortened projections resolve to one object; a new value
  version (different house or different flat) is a distinct entity and does not rewrite the old;
  tenant and conversation scopes are isolated; same street+house in different cities are distinct
  objects.

No source, test, wiki, corpus or saved run was modified; only this report was written. No network, no
provider, no child sessions.
