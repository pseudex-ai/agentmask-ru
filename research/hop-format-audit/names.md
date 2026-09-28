# Hop-format audit — names, role projection, case, transliteration, partial first names

> Codex reviewer note: this is retained investigator testimony, not the final verdict. The introduction's PHONE pair is misquoted and cannot justify its form claim. Case 6's claim of a fake name remaining in the reply is rejected: the quoted restored name is the real Владислав Юрьевич. See [adjudication](README.md). Other root-cause claims remain hypotheses unless independently reproduced there.

Task `hop-audit-20260927-names`. **Revision 2 — corrected.** Engine read at
`/Users/igor/Projects/Obscura-v5-codex/prototype` (read-only, commit `9c5acbb`); instrument read at
`prototype/bench/agentpii5/`. Evidence: the six `cases/*.md` files named in the task.

## Corrections to revision 1 (required reading before the body)

Three conclusions in revision 1 were unsupported. They are withdrawn:

1. **RETRACTED — «the observer's `produced`/`reference` are swapped».**
   `bench/agentpii5/form.py:1003` `form_match(type, produced, reference)` is a **FORM** comparator,
   not a value comparator: its docstring fixes the orientation — «IN hop — produced = the substitute
   the model read, reference = the source's surface. OUT hop — produced = the real value the
   consumer received, reference = the substitute exactly as the agent wrote it» — and it returns
   `FormVerdict(same=…)` over `contracts.FORM_FEATURES[type]` only. `observe.py:962` `_verdict`
   delegates straight to it, and `metrics.form_hIN`/`form_hOUT` (`metrics.py:558`, `:575`) count
   `verdict.same` over `observed` IN hops and `observed ∪ unmasked` OUT hops respectively. So
   `produced="+79607464897"', reference="8 942 925 28 02", same=true` in `chain-009` is the correct
   reading — the two strings agree as *phone forms* — and is not a swapped pair. There is no
   harness-observer defect here, and my «inconsistent orientation within one file» finding is void.
   `observe._out_call` (`observe.py:1155`) does build OUT observations as
   `produced, reference = own_pair(...), written` — real value vs written substitute, exactly as the
   comparator documents.

2. **RETRACTED — «the verdict should compare IN hops against the restored string».** `form_match`
   answers «did the substitute wear the source's form», a form question with a declared answer. On
   the IN side the substitute and the source legitimately differ in VALUE while agreeing in form
   (that is the product working), so `same=true` there is not a certification of anything about
   identity, and it is not a bug that it does not read `restored`. The metric is answering a
   different question than the one I wanted; it is not answering its own question wrongly.

3. **RETRACTED — «`resolve_digit_signatures` reached another row through `deletion_keys`».**
   `vault.py:4379` `resolve_digit_signatures` calls `self._lookup("digits10", …)` then
   `self._lookup("digits", …)`; `_lookup` is a point query
   `SELECT <column>, … FROM tokens WHERE customer=? AND <column> IN (…)`. No `fuzzy`/`deletion_keys`
   call is on that path, and nothing in the traces proves a *different person's* value was returned:
   in `long_order-011` the words returned resolve to `+79884009578`, which is the `i4` row of the
   **same case and the same identity** (`substitutes.i4 = "+79454200672"`, the very fake the agent
   wrote). Mapping a fake to its own real is correct behaviour. What remains is the format defect
   below, not a collision and not a wrong identity.

   I also withdraw the corollary I drew about vault state: the calls in these files run at different
   points of one dialogue, so a later call seeing a later mint is expected; I have no evidence of
   nondeterminism for identical state. My conclusion-3 claim that minted inconsistencies were
   «corpus» defects was likewise overreach — see finding C.

## What survives, and how each is established

The verdict fields are quoted only as they are recorded; every judgement below is mine against the
recorded `restored`/`written`/`tool_results` text, and each is labelled by what the evidence proves.

---

## Case 1 — `memory_anaphora-045` · hop 14 (i10 → `courier_book.contact.name`), turn 4

- **Real input:** msg 2 `«посылку примет громова марина адрес казань улица нижняя 10 квартира 151»`;
  spec `i10 value="громова марина"`, `canonical="громова марина"`, `parts.surname="громова"`,
  `parts.given="марина"`.
- **Minted fake** (`substitutes.i10`, and `mentions` for msg 2): `"мухина степана"` with
  `{"surname":"мухина","given":"степана"}`.
- **Agent-written** (`calls[2].written.contact.name`): `"Мухин Степан"`.
- **Restored** (`calls[2].restored.contact.name`): **`"Громов Марин"`**. The same wrong string is
  recorded in three payloads: `calls[2].restored.contact.name`, `calls[3].restored.text`
  (`«Получатель: Громов Марин»`), `calls[4].restored.summary` (`«получатель Громов Марин»`), and in
  `state[]` for `clm-2` and `esc-1`.
- **Intended:** `Громова Марина`.
- **Recorded observer hops:** 5 and 12 (`i10`, IN) — `produced="мухина степана"`,
  `reference="громова марина"`, `status="observed"`, `verdict.same=true`; hop 14 is `absent`. With
  correction 2 in hand, `same=true` says only that the fake's *form* matched the source's form —
  nothing about the restore. So the instrument neither caught nor claimed to catch this.
- **My verdict:** fail — the restored text is a different person's form (masculine surname, given
  name left in the oblique). Class = **engine**.
- **Root cause (code hypothesis — the string is recorded, the attributing line is not proven):**
  `name_key` (`vault.py:536`) is `morph_names.to_nominative(token).lower()`, and `to_nominative`
  (`morph_names.py:748`) resolves gender/case through `read_person(..., lone_rule=False)`
  (`morph_names.py:658`). `_part_to_nominative` (`morph_names.py:847`) returns a part untouched only
  when *the part's own chosen parse is already `nomn`*; it has no guard for a part whose **lemma** is
  the other gender. I did not run pymorphy3 (venv not used for engine code), so which of
  `read_person`'s candidate sets produced `громов`/`марин` is unproven.
- **Minimal regression proof:** in `test_derived_forms.py`, mint `"громова марина"` (gender f),
  restore `{"contact":{"name":"Мухин Степан"}}` through `unmask_arguments`, assert
  `"Громова Марина"`; plus `assert name_key("громова") != name_key("громов")`.
- **Certainty:** defect confirmed by trace (three payloads); root-cause line = code hypothesis.

**Counterexample to my leading theory.** In the same case, hop 7 (i1) restores `"Осипова"` →
`"Битюкова"` correctly — also a lone feminine surname. `search_rank-000` i12 restores a one-word
given name `"Захара"` → `"Сергей"` correctly. So «feminine surnames break» is false; the trigger is
narrower and unresolved.

---

## Case 2 — `memory_anaphora-003` · hop 2 (i9 → `crm_find_contact.query.phone`), turn 1

- **Real input:** msg 1 `«…это волынов савелий мой телефон восемь девятьсот двадцать пяять ноль
  семьдесят шесть семнадцать семьдесят один…»`; spec `i4`/`i9` `canonical="+79250761771"`.
- **Minted fake:** `"+79211236895"` (recorded `mentions`, msg 1).
- **Agent-written** (`calls[0].written.query.phone`): `"+79211236895"` — a faithful copy.
- **Restored** (`calls[0].restored.query.phone`): **`"восемь девятьсот двадцать пяять ноль
  семьдесят шесть семнадцать семьдесят один"`**, with `refusal_path`/`refusal_rule` set to
  `"phone_not_e164"`. The call did not execute: hop 3 (`contacts[].last_name`) is `absent`.
- **Intended:** the dialable `+79250761771` in a tool argument.
- **Observer:** hop 2 `status="observed"`, `produced="восемь девятьсот…"`,
  `reference="+79211236895"`, `verdict.same=false` — again a **form** verdict, and it is honest:
  the value delivered to the tool does not wear the form the substitute had.
- **My verdict:** fail — a word-run was handed to a schema field that demands E.164; the engine's own
  guard then refused the call. Class = **engine** (fail-closed behaviour working as designed).
- **Root cause (code hypothesis):** `_pick_value` (`vault.py:505`) is written for exactly this case —
  `for_tool and entity_type in _CANONICAL_IS_THE_VALUE and looks_dictated(original, canonical)` →
  return `canonical`; PHONE is in `_NUMERIC_TYPES` (`vault.py:381`) and
  `_CANONICAL_IS_THE_VALUE` (`vault.py:477`), and the tool leg does pass `for_tool=True`
  (`redact.py:2064` `_unmask(..., False, True)`). Either `looks_dictated` (`vault.py:480`) returned
  False on this row, or the value came from the verbatim pass `_restore_verbatim_spans`
  (`redact.py:692`) rather than the token lookup. Distinguishing them needs the vault row, which the
  export does not carry. The same shape recurs in `long_order-011` hop 1 (`"+79454200672"` →
  `"восемсь девятьсот восемьдесят восемсь четыреста девятьсот пятьдесят семь восемь"`) and hop 4.
- **Minimal regression proof:** mint `"восемь девятьсот двадцать пять ноль семьдесят шесть семнадцать
  семьдесят один"` / `"+79250761771"` as a dictated PHONE; unmask its substitute for a tool and
  assert the leaf is E.164. Also assert `looks_dictated(original, canonical)` is recorded per row so
  the branch cannot be missed.
- **Certainty:** defect confirmed by trace; attributing branch = code hypothesis.

---

## Case 3 — `long_order-011` · hop 14 (i11 → `delivery_create_order.recipient.name`), turn 1

- **Real input:** msg 1 `«везите на екатеринбург проезд коммунаров сто семьдесят девять б квартира
  двести одиннадцать коробкаа один килограмма»`; spec `value="тагиев рустам"`.
- **Minted fake** (`substitutes.i11`): `"вениамин игнат"` — written **surname-last**, where the rest
  of the corpus is surname-first.
- **Agent-written:** `{"recipient":{"name":"Вениамин Игнат"}}`.
- **Restored:** `"Тагиев Рустам"` — correct content, role and case.
- **My verdict:** pass on the name axis. Because the substitute itself carried the mention's word
  order, no permutation (`redact._parts_in_order_of`, `redact.py:337`) was exercised. Class = **none
  (works)**; the word-order question remains untested by this case.
- **Address, same case (engine hypothesis, not corpus):** `i7`/`i10` fake
  `"г. Екатеринбург, ул. Рябиновая, д. 104, кв. 206"`, while `courier_book` in the agent arm shows
  `written.address = {street: "Липовая", building: "22", sflat: "21"}` and `restored.address =
  {street: "Нижняя", building: "10", sflat: "151"}` — the recorded `tool_results` are the engine's
  own masked/unmasked output, so a contradiction between them is an engine hypothesis until the
  original raw seed strings are shown to disagree. I withdraw the «corpus» label I put on this.

---

## Case 4 — `tool_chain-038` · the `address_suggest` chain and `address.building`, turns 1–2

- **Real input:** msg 2 `«ничеего не дикктую всё есть в каточке проверьте адреес и оформите»`; card
  `c-1` address `{city: курск, street: маросейка, house: 1, flat: 24}`; seed `a-0 value="Курская
  область, г Курск, ул Маросейка, д 1"`; spec `i7 value="маросейка"` (card street),
  `i9 value="Курская область, г Курск, ул Маросейка, д 1"`.
- **Minted fakes:** `i7` (card street) → `"мятная"`; `i9` (the whole `a-0` address) →
  `"г Курск, ул Липовая, д 4"`. The masked `address_suggest` result records both projections:
  `value: "г Курск, ул Липовая, д 4"` and `data.street: "липовая"` — consistent, one fake for the
  one seed. (Revision 1 claimed the corpus minted several fakes for one seed here; that was wrong —
  `i7` and `i9` are *different* seeds, the card street and the suggestion address.)
- **Agent-written / restored, the recorded calls:**
  `"Курск, улица Мятная, 5"` → `"Курск, улица Мятная, 1"` (residual `["5"]`), and three similar;
  then `"Курск, ул Мятная, д 5, кв 43"` → **`"Курск, ул Мятная, д 1, кв 24"`** (residual
  `["5","43"]`); the `delivery_create_order` leaf records
  `"ул. Мятная, д. 1, кв. 24"` with `status="residual"`.
- **My verdict: fail, and my revision-1 note that this one «is right» was wrong.** The agent's leaf
  held a fake street (`Мятная`) and numbers it invented. The restored leaf keeps the **fake street**
  and fills in the **real house and flat** (`1`, `24` from card `c-1`). A tool now receives a mixed
  address — a street that belongs to no real place with the customer's true house number — which is
  worse than either the fake whole or the real whole. Class = **engine** (partial restoration of one
  value; the container is the vault's, and this leaf restored the container's parts from two
  different owners).
- **Observer:** these hops are `status="residual"` — the honest label, and it agrees with me that a
  substitute survived.
- **Certainty:** defect confirmed by trace (the recorded `restored` leaf and the recorded `written`
  leaf are both quoted); the code path that mixes them (fragment fallback `_place_fragment` /
  `in_form_of`) is a hypothesis, not traced.

---

## Case 5 — `search_rank-000` · hop 1 (i12 → `courier_book.contact.name`), turn 1

- **Real input:** msg 1 `«здрасте курьера на солнечная 7 это в чернь на сергея телефон 89164021187
  а также к 10 часам»`; `i12 value="сергея"`, `canonical="сергей"`, `parts={"given":"сергей"}` — a
  **given name only**, no surname.
- **Minted fake:** `"захара"` for the user mention (genitive, matching «на сергея») and `"Захар"` in
  the masked CRM payload.
- **Agent-written / restored:** `"Захар"` → `"Сергей"` — correct, right role, right case.
- **My verdict:** pass. This is the positive example for a partial first-name-only answer: the
  one-word given name mints a one-word substitute, and the restore returns the customer's nominative
  given name. Class = **none (works)**.
- **Address, same case (engine hypothesis):** the masked `address_suggest` result for seed `a-0`
  records `value: "г Чернь, ул Озёрная, д 3"` with `data: {street: "берёзовая", house: "8"}` — two
  different fakes inside one seed's own payload. My revision-1 «corpus» label is withdrawn: these are
  engine outputs, so the disagreement is an engine hypothesis until a raw seed is shown to carry
  contradictory originals. The agent wrote `"Чернь Озёрная 3"` and the recorded restore is
  `"Чернь Солнечная 7"`; the agent's later prose asserts «совпадение 100 %».

---

## Case 6 — `chain-009` · `crm_upsert_contact` (turn 2) and the reply

- **Real input:** msg 1 `«здрасте это захаров владислав юрьевич хочу поменять адрес доставки телефон
  8 960 746 48 97…»`; msg 2 `«теперь казань вишнёвая 8 кв 176»`; spec `i1..i3 =
  захаров/владислав/юрьевич`, `i4 = +79607464897`, `i10 = "казань вишнёвая 8 кв 176"`.
- **Minted fakes:** `"рыбаков"`, `"ярослав"`, `"геннадьевич"`, `"8 942 925 28 02"`,
  `"казань грушевая 5 кв 40"`.
- **Agent-written → restored (all correct):** `last_name "Рыбаков"→"Захаров"`,
  `first_name "Ярослав"→"Владислав"`, `middle_name "Геннадьевич"→"Юрьевич"`,
  `phone "+79429252802"→"+79607464897"`, `address.street "Грушевая"→"Вишнёвая"`,
  `house "5"→"8"`, `flat "40"→"176"`.
- **My verdict:** pass — the cleanest case in the set and the positive control that name, role, case
  and address restoration can all work in one call. Class = **none (works)**.
- **Agent-behaviour note:** the customer-facing reply keeps the fake in prose —
  `reply: "…на номер +79607464897: «Владислав Юрьевич, адрес доставки обновлён: казань вишнёвая 8
  кв 176»."` while `reply_raw`/`control_reply` in the same file carry `«Ярослав Геннадьевич»`. The
  restored *fields* are right; the sentence's name is stale. Class = **agent-behaviour**.

---

## Findings that stand (with class and certainty)

- **A. A person's restored name came back in the wrong gender/case** (`Громов Марин` for
  `громова марина`, in three restored payloads). Class: engine. Certainty: defect by trace,
  root-cause line by code hypothesis. Highest-value single defect in this set.
- **B. A dictated identifier reached a tool argument as a word-run** (`phone_not_e164`, and the same
  in `long_order-011`). Class: engine, fail-closed. Certainty: defect by trace, branch by hypothesis.
- **C. One value restored as a mixture of fake and real parts** (`"Курск, ул Мятная, д 1, кв 24"`:
  fake street, real house and flat from the card). My revision-1 reading of this as «correct» was
  wrong. Class: engine. Certainty: defect by trace, path by hypothesis.
- **D. Within one masked payload the same seed appears in two projections with different fakes**
  (`search_rank-000` a-0: `value` fake `Озёрная 3` vs `data.street` fake `берёзовая`; and
  `tool_chain-038`'s earlier suggestion leaves). Class: **engine hypothesis** — the recorded
  `tool_results` are engine output; I did not inspect the raw corpus seeds, so I cannot call this
  corpus. Certainty: unresolved.
- **E. Positive examples worth pinning as controls:** `chain-009` (seven fields, one call),
  `search_rank-000` i12 (partial first name), `memory_anaphora-045` i1 (`Осипова`→`Битюкова`),
  `tool_chain-038` `crm_find_contact.query.phone` (`+79312015731`→`+79527226345`),
  `long_order-011` i11 (`Вениамин Игнат`→`Тагиев Рустам`).

## Architectural seams (proposal only — no patch)

1. **One container, one owner, on the way back.** A restored leaf must be all-real or all-fake:
   resolve a value's parts as a unit and refuse a partial splice (finding C). A house number taken
   from one address and a street from another is a new place, which is worse than either.
2. **Record the branch, not just the outcome.** Persist on every token row whether the original was
   dictated (`looks_dictated`) and what the canonical is, so the tool leg is `if row.dictated: return
   row.canonical` and finding B becomes testable at the row instead of at the argument.
3. **A value-level hop oracle beside the form oracle.** `form_match` answers the form question
   correctly (correction 1); nothing in the instrument answers «is this the same identity». Add a
   separate `value_ok(restored, canonical)` field to `HopObservation` for OUT hops and
   `identity_ok` for IN hops, so finding A is machine-detectable without weakening `form_hIN`/`hOUT`.
4. **One mint per identity per conversation, enforced at mint time** (`is_minted_token` before
   insert) — this is the seam that would make finding D decidable and eliminate it if it is real.
5. **A same-seed/many-projections fixture** asserting every projection of one seed maps back to that
   seed's canonical, which is what the ranking families need before they can score anything.

## Not inspected

- The other 20 evidence files were not read.
- Engine code was not executed; all morphology and vault claims are read, not reproduced.
- The raw corpus seeds for these cases were not opened, which is why findings C and D are labelled
  engine hypotheses rather than corpus defects.
- The harness code that *writes* `verdict` was read only through `observe._observed`/`_out_call`,
  `metrics.form_hIN`/`form_hOUT` and `form.form_match`; the rest of `observe.py` was not audited.
