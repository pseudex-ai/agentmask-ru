# LOC form — independent adversarial review of the current candidate

Scope: `prototype/test_location_form_adversarial.py` and this file only. The
engine was **not** edited; no children, no network, no paid generation, no
`main`/credentials writes. Public `mask_text` / `unmask_text` /
`unmask_arguments` through a real ephemeral `Vault` (`:memory:`) and the real
development bundle (`testkit.load_dev_bundle()`).

    cd prototype
    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python \
        test_location_form_adversarial.py

Evidence read literally: `evidence/cases/tool_chain-017.md`,
`prompt_rule-026.md`, `memory_anaphora-119.md`, `long_support-027.md`, and
`location-hop-review.md`. Current code read at the seam only: `redact.py`
`_unmask` (696–731), `_in_case_of` (1981–2026), `_place_fragment` (1824–1874),
`_restore_inflected_spans` (1582–1740); `morph_places.py` `_street_like`
(1602–1629), `in_form_of` (1631–1676), `role_spans` (1234+); `vault.py`
`place_owner` (3074–3116), `resolve_digit_signatures_typed` (4384+).

## Verdict

**47/64 checks pass; 17 are RED.** One of them is a **new regression** caused by
this candidate — it is the `test_product.py:442` failure Codex reported. The
other 16 are pre-existing contract failures on the same seam (the candidate
neither introduced nor closed them), and 7 pre-existing REDs *were* closed by
the candidate.

Measured against the HEAD snapshot, same file, same venv, run from
`/private/tmp/hop-sprint-baseline.86Dxvl/prototype` with the test copied in
(`sys.path[0]` is the script directory, so a plain `cd` does **not** change the
imports — the file has to sit in the snapshot):

| snapshot | result | note |
|---|---|---|
| HEAD `9c5acbb` baseline | **44/64**, 20 RED | `test_location_hop_form.py` red |
| current candidate | **47/64**, 17 RED | existing LOC suite green (`14/14`) |

The candidate closes 7 prose checks (marker duplication `г г …`, and the prose
expansion of a copied street fragment into the whole address) and opens 4
(the short-address link). Net −3 RED.

## F1 — NEW regression: the current sender's marker is injected into the customer's value

**This is `test_product.py::test_short_address_resolves_to_the_full_one`, line
442. Log `/private/tmp/hop-sprint-date-product.log`.** Reproduced in isolation
and pinned in the test file (`R0/link`, 4 checks).

    full  = talk.tokenize("г. Москва, ул. Ленина, д. 14", "LOC")   # e.g. 'Москва, ул. Каштановая 44'
    short = talk.tokenize("Ленина 14", "LOC")                      # e.g. 'ул. Каштановая 44'
    unmask_text(f"адрес {short}", talk)

    got   'адрес ул. Ленина 14'
    want  'адрес Ленина 14'          (HEAD baseline: got == want)
    tool  'ул. Ленина 14'            want 'Ленина 14'

The short mention's real value is `Ленина 14` — it names no street type. The
**mint** gave the linked fake a marker (`ул. Каштановая 44`), the agent copied
the fake, and the restorer re-added `ул.` before `Ленина`: a word the customer
never wrote in that mention. §1 («форма — от текущего отправителя») and the
shipped test's own property 2 («It gets back exactly what it wrote: no city and
no flat if it named neither») both forbid it.

### Root cause: `_street_like`, not the `_unmask` priority reorder

`morph_places._street_like` (1602–1629) in this candidate removed the branch
that used to keep a type-less real value type-less:

```python
# HEAD (still described by the docstring above the function):
if len(named) == len(words):
    result = real_name                      # клиент типа не написал -> типа нет
else:
    agent_marker = _leading_generic(model)
    result = f"{agent_marker} {real_name}" if agent_marker else real_name

# candidate:
agent_marker = _leading_generic(model)
result = f"{agent_marker} {real_name}" if agent_marker else real_name
```

The marker is now taken from the model surface **unconditionally**. But the
surface carries `ул.` because the MINT wrote it into the fake, not because the
current sender chose it. Direct proof, no mocks:

    morph_places.in_form_of("Ленина 14", "ул. Каштановая 44")  == 'ул. Ленина 14'
    morph_places.in_form_of("Ленина 14", "Каштановая 44")      == 'Ленина 14'
    _restore_inflected_spans('ул. Ольховая 35', talk, True, False)
        -> [(0, 16, 'ул. Ольховая 35', 'ул. Ленина 14')]

The value is already wrong **before** `_unmask` chooses a span, so the newly
reordered whole-address priority is not the cause here. The retained docstring
above `_street_like` still documents the removed rule («Клиент написал улицу БЕЗ
типа … типа в аргументе не будет»), so code and comment now disagree; the
comment cites 25 measured addresses that this change re-injects.

Reproduced through the public mask path as well: `R0/link` runs both a
`mask_text`-minted full address and a `tokenize`-minted one; both RED, both
fixed by returning the type-less real value unmarked.

## F2 — RED (pre-existing): a dropped marker makes the prose leg a §4.2 hybrid

`R1/priority`, 2 of 4 checks RED (the tool leg is correct).

    written  'г Казань, Сиреневая, д 5, кв 107'     (agent dropped «улица»)
    tool     'г Казань, Зацепская, д 7, кв 31'      OK
    prose    'г Казань, Сиреневая, д 5, кв 31'      RED — fake street + fake house, REAL flat
    want     'г Казань, Зацепская, д 7, кв 31'

`_restore_inflected_spans` resolves the whole composite span correctly
(`(2, 30, 'Казань, Сиреневая, д 5, кв 107') -> 'Казань, Зацепская, д 7, кв 31'`
— verified by direct call). `_unmask` then discards it: the reorder only
pre-takes a composite when `vault.place_owner(surface, "") is not None` (line
704), and for this surface `place_owner` returns `None`, so the composite is
**not** pre-taken. The
prose-only `_restore_cued_numbers_spans` runs first in `passes` (714–716),
splices the REAL flat, and the composite span is dropped as overlapping
(718–721). The tool leg has no cued-numbers pass, so it never steals the range
and the composite survives. Both consumers therefore disagree, and the prose
consumer gets a hybrid: the exact class §4.2 names.

The guard disagrees with the resolver: a span the resolver already proved does
not need a second, stricter `place_owner` vote. When it loses that vote, a
lower-priority numeric pass wins a sub-range of a resolved address.

## F3 — RED (pre-existing): the same seam reached by letter case alone

`R2/case`, 2 of 3 RED. Written lower-case, the whole span resolves
(`'казань, улица сосновая, д 4, кв 66' -> 'казань, улица зацепская, д 7, кв 31'`)
and is discarded by the same guard; the tool leg is correct, the prose leg gives
`'г казань, улица сосновая, д 4, кв 31'` — fake street + fake house, real flat.
Tools and prose disagree. This is F2 without the marker, which isolates the
cause to the priority/steal interaction rather than to the dropped word.

## F4 — RED (pre-existing): an all-caps mention loses the real city

`R3/case`, 2 of 2 RED.

    written  'г КАЗАНЬ, улица СОСНОВАЯ, д 4, кв 66'
    tool     'г ЗАЦЕПСКАЯ, д 7, кв 31'       RED
    prose    'г КАЗАНЬ, улица СОСНОВАЯ, д 4, кв 31'  RED
    want     'г КАЗАНЬ, улица ЗАЦЕПСКАЯ, д 7, кв 31'

Here the content itself is lost, not only the form: `role_spans` does not read
an all-caps settlement as a city, so the city slice is classified as part of the
street; `in_form_of` then writes the real STREET into the city span and never
places the real city (`_restore_inflected_spans` returns
`'ЗАЦЕПСКАЯ, д 7, кв 31'` for this surface). One role's content is placed into
another role's slot — §4.2 forbids exactly that — and the real town disappears
from the tool argument. Both legs fail, differently.

## F5 — RED (pre-existing): a street-less fragment expands to the whole address

`R4/fragment`, 5 of 6 RED.

| written (agent) | tool | prose | want |
|---|---|---|---|
| `кв <fake flat>` | whole real address | `кв 31` | `кв 31` |
| `д <fake house>, кв <fake flat>` | `д <fake>, г Казань, улица Зацепская, д 7, кв 31` | `д <fake>, кв 31` | `д 7, кв 31` |

`_place_fragment(..., for_tool=True)` returns the **whole** stored value
(1824–1874) and `in_form_of` returns it unchanged when the surface has no
`street` role (`if "street" not in theirs …: return value`, 1662–1663). So a
lone `кв` leaf is answered with a complete address the agent never selected —
the opposite of `in_form_of`'s own docstring («ЧАСТЬ, КОТОРОЙ НЕТ У МОДЕЛИ, НЕ
ДОПИСЫВАЕТСЯ») and of §4.2 («Если агент выбрал только имя, полный ФИО не
достраивается»). `_place_fragment`'s docstring says it was measured **prose
only**; the candidate now calls it on the argument leg too, and the guard that
was supposed to make that safe does not hold for a street-less surface.

## F6 — RED (pre-existing): a cross-mix leaks the other address whole

`F/two`, 2 of 8 RED. Two real addresses in one text share the street; the mint
gives them the same fake street (measured). A is street+house, B is a different
house:

    A = 'казань зацепская 7 кв 31'   B = 'казань зацепская 9 кв 32'
    cross = A's fake street + A's fake house + B's fake flat
    tool  contains B's WHOLE real value  -> RED
    prose leaves B's fake flat standing  -> RED

Each full fake restores to its own address (control, green), a bare shared
street names no house (control, green), but the cross-mixed surface both leaks
the other mention whole on the tool leg and leaves a fake part in prose. §4.2:
«Несколько адресов в одном тексте разрешаются независимо; неоднозначность
одного не даёт права взять дом из другого». Same seam as F5.

## Controls (GREEN, 47 checks)

Pinned so a fix cannot pay for the REDs above with them:

- **Verbatim copy** of the fake → the real address on both legs.
- **Conversation scope**: a bare-street and a street+house fragment stay fake in
  another conversation on both legs (whole-substitute lookup across the customer
  is the documented, intended exception and is not asserted either way).
- **Unknown street**: `Незнакомая` with a number that is not ours stays byte-for-
  byte on both legs; a measured quantity (`2 гектаров`) is untouched.
- **Literal original typos** (§4.3): a typo in the type word (`улца`), transposed
  street letters (`Зацепксая`), a Latin `c` inside the Cyrillic street and a
  Latin `l` inside the flat all return the ORIGINAL exactly, both legs.
- **Same-kind abbreviation** (the only marker policy this file encodes): the
  current sender's spelling wins — `улица`→`ул.` and `ул`/`ул.`→`улица` — both
  legs.
- **Copied fragments**: bare street, street+type, street+house, city+street each
  restore their own part, both legs.
- **Two-address independence**: A and B each restore their own house/house+flat;
  a bare shared street names no house.

The candidate **closed** the baseline's prose marker duplication (`г г Казань,
улица …`) and the baseline's prose expansion of copied fragments
(`bare street` / `street+type` / `street+house` / `city+street` used to return
the whole address on the prose leg). Those are now green; the existing
`test_location_hop_form.py` is `14/14`.

## Semantic policy left open (deliberately not asserted)

The focus note was respected: **`улица` vs `проезд` is not treated as
formatting.** The candidate renders whatever generic the agent wrote over the
real street name, so an agent that rewrites `проезд Зацепская` as `улица
Зацепская` receives `улица Зацепская` on both legs (measured: real `проезд
Зацепская` + agent `улица` → `г Казань, улица Зацепская, д 7, кв 31`). Whether
the KIND of a street is content or form is not settled by §1; this file encodes
neither reading and only asserts same-kind abbreviation (`ул.`/`улица`). The
same open question governs F1 in its other direction: when the customer wrote no
type but the mint showed one, the candidate treats the marker as the sender's
form and injects it; the shipped test and the retained `_street_like` docstring
treat it as content that is absent. **That contradiction needs an owner
decision**, not a test edit.

## What each RED would need (no engine change made here)

- **F1**: `_street_like` must take the type from the REAL value's shape, not
  from the model surface alone (restore the `named == len(words)` case, or gate
  the marker on the real value's own type). The mint already writes a marker
  into every fake, so the model's marker cannot be read as the sender's choice.
- **F2/F3**: the `place_owner` guard at `redact.py:704` must not veto a span
  `_restore_inflected_spans` already resolved as a full street+house; and the
  numeric/cued passes must yield to a resolved composite whose range they
  overlap.
- **F4**: `role_spans`/`in_form_of` must not classify an all-caps settlement as
  street, and must place the real city into the city role.
- **F5/F6**: a street-less fragment must be answered with the roles the surface
  named, never with the whole stored value; the same rule removes the
  cross-mention leak.

## Budget / discipline

No engine, `main`, `.env`, credential or source-run writes. The test uses only
`:memory:` vaults, so no `pseudex-vault.key` or dataset is produced. All work is
local and deterministic: three consecutive runs of the candidate give
`47/64`. The fake is read at the mint boundary and never pinned; the only
fixture not built from `mask_text` is the public `Vault.tokenize` link of the
shipped `test_product.py`, used because that is the failing path.

---

# Addendum — read-only review update (2026-09-27, after the conflict guard)

Task: `hop-sprint-loc-attack-20260927`, continuation. **No engine edits, no
test edits, no children, no model calls.** Only this addendum was written. The
shipped `test_location_form_adversarial.py` was *run*, not modified: it now
reads **66/66** (the 2 conflict checks below were added by its owner). No
450-case rerun; evidence is the 66-check suite plus targeted read-only probes.

## A. Adjudication of the F/two change — LEGITIMATE. My earlier expectation was wrong

The owner replaced `surviving_substitutes(cross, prose) == []` with: the whole
conflicting mention must come back **byte-identical on both legs**, plus the
existing residual diagnostic must be non-empty. I independently tried to break
that reading and could not; it is the correct outcome, and my old assertion was
the defect.

Evidence (fresh `:memory:` vault, A = `казань зацепская 7 кв 31`,
B = `казань зацепская 9 кв 32`; the mint links them to one fake street and
distinct fake house/flat; `cross` = shared fake street + A's fake house + B's
fake flat):

| probe | result |
|---|---|
| `vault.place_owner(cross, "")` | `None` |
| `vault.place_owner(<shared street + A house>, "")` | `None` |
| `vault.place_owner(<A fake house>, "house")` | token A |
| `vault.place_owner(<B fake flat>, "flat")` | token B — a DIFFERENT owner |
| `unmask_arguments` on `cross` | unchanged: `'г Казань, улицу Родниковую, д 3, кв 242'` |
| `unmask_text` on `cross` | unchanged, same string |
| `surviving_substitutes(cross, …, for_tool=True/False)` | non-empty (fake street + both fake numbers) |

Why refusal-to-resolve is right, on the product's own terms:

1. The surface provably names parts of **two owners**, so among the client's
   records there is no single true address for it. There is nothing to resolve
   *to*.
2. Any "resolved" string is a hybrid of **two real identities** — exactly §4.2's
   prohibition, and worse than a fake: each half is a real value, so a
   courier/tool can act on a real place the sender never named in that mention.
   A fake corresponds to no real place; leaving it fails safely at the tool.
3. `residual == []` can only be reached by **choosing an owner**, which §1 of
   `docs/tz-hop-form-adaptation.md` forbids («неоднозначный … исход
   ambiguous/unsupported, а не случайный человек»). My assertion demanded the
   engine guess; that is the weakened acceptance, not the owner's rule.
4. "Unchanged whole" is a refusal, not a hybrid, and the residual list is the
   `ambiguous` surface the current API actually has. **I do not ask the engine
   to pick an owner to clear the residual.**

Two conditions make the rule safe, and both are now asserted (so this is a
stronger acceptance, not a weaker one):

- the entire mention is byte-identical on **both** legs — no partial restoration
  of the unambiguous half (verified: tool and prose both return `cross`);
- the residual diagnostic is **non-empty** in exactly this case (verified).
- Caller-side caveat, for the record: a fake address is safe only if the gateway
  treats a non-empty `residual_tokens` as *do not execute*. The engine cannot
  make an ambiguous mention correct; it can only refuse and report.

Guard overreach check (the opposite failure — refusing a resolvable mix) is
clean; these are good literal negatives to keep:

| written | tool | prose |
|---|---|---|
| A consistent whole (fake street/house/flat of A) | real A `'…, улицу Зацепская, д 7, кв 31'` | same |
| B consistent whole | real B `'…, д 9, кв 32'` | same |
| A street + A house (no flat) | `'…, д 7'` | same |
| A house + B flat (conflict) | unchanged | unchanged |
| B house + A flat (conflict, other direction) | unchanged | unchanged |

## B. Public regression risk of the new cue handling

`_restore_cued_numbers_spans` is now in `passes` for **both** legs
(`redact.py:737`), `_HOUSE_CUES` includes bare `"д"`, and `_CUE_NUMBER` accepts
`д(?=\s)` (`redact.py:793`). Two concrete risks, both reproduced with a real
vault and the real bundle.

### B1 — bare `д` fires on a letter/label, not on «дом» (false positive, both legs)

Real `г Казань, улица Зацепская, д 7, кв 31`, fake house `<H>` (e.g. `4`):

| written | tool | prose |
|---|---|---|
| `Иванов Д <H>` | `Иванов Д 7` | `Иванов Д 7` |
| `класс д <H>` | `класс д 7` | `класс д 7` |
| `группа Д <H>` | `группа Д 7` | `группа Д 7` |

`Д`/`д` here is an initial / category label / abbreviation (деревня, доктор),
not a house marker, yet the following number is replaced with the real house.
The dotted `д.` and the word `дом` are address-specific; bare `д` is not. This
is the main public over-mask risk of the new short form. The old text (`д.` only)
did not fire on these.

### B2 — the street-less projection fills a role the number does not own (tool only)

Real as above; `<H>` the fake house, `<F>` the fake flat:

| written | cued pass | tool | prose |
|---|---|---|---|
| `кв <H>` (fake HOUSE under a flat cue) | `[]` (role isolation holds) | `кв 31` (the real FLAT) | `кв <H>` unchanged |
| `д <H>` | `['<7>']` (correct) | `д 7` | `д 7` |
| `кв <F>` | `['<31>']` | `кв 31` | `кв 31` |

Root: the cue pass correctly refuses (`place_owner(<H>, "flat")` has no owner),
but `_restore_inflected_candidates(..., for_tool=True)` still returns a candidate
for `кв <H>`, and `in_form_of`'s new street-less projection writes `ours["flat"]`
into the flat slot without asking whether the number is that role's part. The
tool leg therefore returns the real FLAT for a number that was the fake HOUSE,
while prose leaves it — a leg split and a role swap. Suggested rule: the
projection must use the same role-scoped evidence as the cue pass
(`_wears_parts_in_role` / `place_owner(number, role)`) before filling a numeric
role, or refuse.

### B3 — the tool-leg cue pass is bounded to one leaf (what holds)

`{"note": "дом <H>"}` → `{"note": "дом 7"}` and
`{"comment": "привезти к д <H>"}` → `"… к д 7"` — the cue now fires inside a
tool string, which is the intended new reach. But `{"дом": "<H>"}` is
**untouched**, because `unmask_arguments` restores the VALUE leaf and the key is
not part of that text, so the cue and the number are not adjacent. Good: the
new behavior is confined to free-text leaves containing both. That is also the
boundary of the B1/B2 risk — no schema key can trigger it.

### B4 — negatives that already hold (pin them)

`дом 3` (not ours), `д 3`, `д <F>` (fake flat under a house cue), `счёт 1234`,
`заказ 42`, `2 гектаров`, `п. <H>`, `house <H>` — all unchanged on both legs.
They are not in the current suite; they are cheap literal additions.

## C. Suggested literal negatives for the test owner

Add (each should stay byte-identical on both legs, with the real vault of
`_REAL`); none requires an engine decision about ownership:

1. `"Иванов Д <H>"`, `"класс д <H>"`, `"группа Д <H>"` — the B1 false positives.
2. `"дом 3"`, `"д 3"` — a number that is not any token's house.
3. `"д <F>"`, `"кв <H>"` — role isolation, both directions (B2).
4. `"счёт 1234"`, `"заказ 42"`, `"2 гектаров"` — ordinary business quantities.
5. `{"дом": "<H>"}` — the key/value boundary (B3), and positively
   `{"note": "дом <H>"}` if the tool-leg cue is intended.
6. Conflict guard, both directions, from the fresh vault (§A table): conflict is
   unchanged on both legs with a non-empty residual, while A-consistent,
   B-consistent and A-street+house all still resolve.

## D. Status

- F/two adjudication: **legitimate**; my previous residual-`== []` expectation
  is withdrawn. `66/66` including the 2 conflict checks.
- B1 is the one finding I would fix before a public benchmark: it changes an
  ordinary token (`Д` + number) in tool arguments and prose.
- B2 is a parity/role-swap residual of the street-less projection, tool-only.
- No engine or test edit made; this file is the only write.
