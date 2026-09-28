# LOC hop form — E04/E05 RED reproducers (independent)

Scope: `prototype/test_location_hop_form.py` and this file only. Engine untouched,
no children, no network, no paid generation, `main` untouched. Public
`mask_text` / `unmask_text` / `unmask_arguments`, a real ephemeral `Vault`, the
real dev bundle through `testkit.load_dev_bundle()`. Run from `prototype/`:

    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_location_hop_form.py

Verdict: **10/14 — two contract classes are RED, both reproduced without an LLM.**

Evidence read literally (the four named case files, not the aggregate CSV):
`tool_chain-017.md`, `prompt_rule-026.md`, `memory_anaphora-119.md`,
`long_support-027.md`. Current LOC code read only where the seam is:
`redact.py` `mask_text` / `_token_for_text` / `_place_fragment` / `_unmask`,
`morph_places.split_roles` / `in_form_of` / `street_case`, `vault._pick_value` /
`place_key` / `_fake_place`.

## 1. E04 — hybrid «подставная улица + реальный дом» (§4.2)

**Reproducer (exact, no pin needed — the fake is read at the mint boundary).**
The card `{"contacts":[{"address":{"city":"казань","street":"зацепская",
"house":"7","flat":"31"}}]}` is masked through the real `Detector`; the model is
shown three separate leaves of ONE address (e.g. `абрикосовая` / `9` / `146`).
The agent reassembles them into one field — `ул. Абрикосовая, д. 9, кв. 146` —
and the tool receives:

    got   'ул. Берёзовая, д. 7, кв. 31'      (this run's fake street)
    want  'ул. Зацепская, д. 7, кв. 31'      (§4.2, §1)

The two numeric leaves resolve to the REAL house and flat; the alphabetic street
does not, and `surviving_substitutes(..., for_tool=True)` reports it:
`['Берёзовая']`. Both consumers produce the same hybrid. This is the exact class
of `tool_chain-017` (`delivery_create_order` → `to_location.address`, written
`ул. Барбарисовая, д. 3, кв. 228`, restored `ул. Барбарисовая, д. 7, кв. 31`,
residual `барбарисовая`). `prompt_rule-026` (fake `мятная` against real
`комиссарова 64 кв 183`) and `long_support-027` (`crm_add_note`, `переулок
Вишнёвая` kept while `16, кв. 142` restore) show the same split.

## 2. E05 — marker/prose discrepancy against §1

**Reproducer.** Real `г Казань, проезд Зацепская, д 7, кв 31`, masked and then
rewritten by the agent in its own sentence with its own generic (`проезд` →
`улица`). The SAME written string reaches both consumers:

    unmask_arguments -> 'г Казань, улица Зацепская, д 7, кв 31'   (passes)
    unmask_text      -> 'г г Казань, проезд Зацепская, д 7, кв 31' (RED)
    want (both legs)    'г Казань, улица Зацепская, д 7, кв 31'

On the prose leg the agent's generic is replaced by the STORED one (`проезд`)
and the agent's settlement marker is duplicated (`г г`). §1 puts the form in the
current sender and §4 makes the core shared by argument and text, so the two
legs must agree; the tool leg already implements the contract and is the
reference here.

## 3. Root seam (why, not what to build)

**IN has one entity, OUT has many surfaces.** `Vault.tokenize` mints ONE LOC row
from the whole address; `redact._token_for_text` shows its parts through
`PartSpan` (`morph_places.split_roles` / `_street_like`), so the card's street,
house and flat are three views of the same row.

**OUT resolves the written surface as a whole key, with an independent numeric
rescue.** `unmask_arguments` → `_unmask(inflect=False)` reaches the real value
only if `vault.place_owner` / `_place_fragment` match the whole surface by
`morph_places.match_signature`. When that key misses, the numeric leaves are
still recovered through the digit-signature path (`redact._digit_signatures` /
`_digits_in_form_of`), while the alphabetic street has no such second chance.
The result is a partial owner: real digits over a fake word — the hybrid §4.2
names. `_mirror_leaks_nothing` and the single-owner rule guard the IN mirror and
the reverse lookup, but not the recombination of leaves on the way out.

**The prose branch never re-forms.** In `_unmask(inflect=True)` the LOC branch
is `case = morph_places.street_case(surface); if case is None or case == "nomn":
return value` — the whole stored real value, unlike the tool branch's
`morph_places.in_form_of(value, surface)`. So the prose marker and composition
come from whichever representation first entered the vault, which §1 forbids,
and the window that matched can begin after the agent's own settlement marker,
leaving it doubled in front of the returned whole.

The seam is the same one in both failures: content is owned by the mint, form by
the consumer, and no single resolution decides the pair before the splice.

## 4. Controls (green)

- Copied fake verbatim → both `unmask_arguments` and `unmask_text` return the
  real `г Казань, ул Зацепская, д 7, кв 31`.
- Two addresses in one text sharing a street but not a house resolve to their
  own houses; the street alone names no house (§4.2 independence).
- A measured quantity (`2 гектаров`) and numbers in a sentence are untouched.
- The agent's generic on the TOOL leg is preserved (the E05 asymmetry).

## 5. Not reproduced / open

- E04 could not be reproduced by rewriting a whole-address LOC span: the
  whole-surface key held in every variant tried (marker swap, city swap,
  dropped city, reordered), so the split is specific to the many-leaves mint.
  The whole-span rewrite did surface a separate defect — the real address
  appended after the agent's text — not claimed here.
- `memory_anaphora-119` carries a fake street with its own fake house/flat
  (`ивовая 146 кв 68` against `новая 119 кв 176`); no real house sitting under a
  fake street was observed in the saved transcript, so it is corroboration of
  the mint shape, not a second reproducer.
- Whether the generic word (`улица` / `проезд`) is FORM or CONTENT is not
  settled by the text of §1; the test takes the form reading because the tool
  leg already does and the two legs must not disagree. Reported needed.
- No engine change, no new abstraction, no benchmark sweep is proposed here.
