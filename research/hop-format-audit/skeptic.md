# Skeptic — independent metric/observer prosecution of six v5 cases (rev. 2)

> Codex reviewer note: the blanket `source A` below is incorrect; each retained case dossier identifies its source, including C for `prompt_rule-026`. Supplied aggregate counts were computed by the coordinating reviewer, not independently by this investigator. The 301/388 conditional statistic does not fully answer engine quality because it still depends on old alignment. See [adjudication](README.md).

Scope: `samples.skeptic` = memory_anaphora-119, memory_anaphora-028, tool_chain-004,
prompt_rule-026, long_order-058, long_support-027, all arm `I`, `source A`, `repeat 0`.
Evidence read: the six `.md` exports; **same-case controls** `memory_anaphora-119.controls.C/C2`,
`tool_chain-004.controls.C`, `long_order-058.controls.C`; `audit.json`/`extract.log`; read-only
`bench/agentpii5/{metrics,observe,form,report}.py`, `contracts.py`.
Run A provenance: `b4296aa2-…`, 321 raw, 314 completed, 7 excluded (`memory_anaphora-033/045/
062/081/087/105`, `tool_chain-015`) — none of mine.

**Not exhaustive.** Per the owner this export is a sample investigation of **24 of 450** stored
observations; my six are a subset. Counts the owner supplied (744, 415, 1348/342/37/9,
301/1736/388, 5305, 5720) are used only for arithmetic and are **not independently
re-derived or verified by me**. I ran no reproducer and wrote no parsing script.

## Corrections to my first draft

1. **RETRACTED: the `prompt_rule-026` "shared street" counterexample.** Exact spec: i7/i10
   parts are `street "комиссарова", street_type "переулок", house "64", flat "183"`; the masked
   result renders `street "мятная", house "34", flat "186"`. The fake street is **not** shared
   with the real. The `residual {"to_location.address": ["мятная"]}` is therefore a **genuine
   surviving fake**, not a false positive — a stronger engine finding, not a counterexample.
2. **Same identity in two source notations is REQUIRED product scope, not a corpus artifact.**
   In `long_order-058`, i4 `+79889990949` and i9 `8 988 999 09 49` are one identity `p58`; the
   user format and the tool format must each be mirrored. The IN/tool phone miss is **engine**.
3. **744 is "same tool called elsewhere in the run", not proof of 744 aligned actions.** I do not
   treat it as a causal class. The code fact is only that matching is turn-scoped
   (`observe.py:732-735`).
4. My earlier control citation (`chain-009.controls.C.json`) was the wrong file; controls must be
   the same case, C/C2 vs I (read for 119, 004, 058 below).
5. All counts given by the owner are marked owner-stated, not verified.

## Cross-cutting: what the code does, and what the controls show

**Same-case controls are the behavioural instrument.** `memory_anaphora-119`: arm C (`written ==
restored`, no substitute in the path) made two calls (`crm_find_contact` phone, then `last_name
"морозов"`); C2 made three (`"Лебедева"`, `"Морозов"`, …); arm I made **one**. `tool_chain-004`
C: `address_suggest.query == "псков смольный 52"` (the real address); I: `"Псков, улица Луговая,
дом 89"` (the fake). `long_order-058` C: phone `+79889990949` (real) and recipient
`Васильев Иван Павлович` — i.e. the controls never saw a substitute. So the behavioural effect
of the gateway is read **C/C2 vs I on the same case**, which is the axis the owner names — not
the declared turn.

**The declared `turn` is not an obligation on a free agent.** `call_for_hop`
(`observe.py:732-735`) matches `(turn, tool_name, call_ordinal)`; `_out_call`
(`observe.py:1163-1165`) turns "no call in that turn" into `absent`. Since the agent must not act
at a fixed turn, an `absent` under a declared turn is not by itself evidence that a causal action
was skipped. **Rebinding must be causal — the same data/action identity (the hop's causal
lineage), never merely any-turn ordinal, because an ordinal can attach a later correction/retry
call to an earlier hop.** I withdraw my draft's "bind by `(tool, call_ordinal)`" seam.

**Denominators (owner-stated numbers, code confirmed).**
- `form_hOUT` (`metrics.py:588-590`) takes only `observed|unmasked`; a `residual` hop has
  `verdict=None` (`observe.py:1175`) and is in neither the 5305-denominator nor the `out_absent`
  caption (`metrics.py:593-599`, `report.py:121`, printed adjacently at `report.py:826-844`).
  5305+415=5720 is arithmetic consistency, not my verification. Excluding residual is defensible
  per-hop; the missing caption is not.
- `end_to_end` (`metrics.py:423-430`) counts every declared OUT/tool_arg and a hit only at
  `observed`; 1348+342+37+9=1736 with only 388 written gives 301/388 conditional (owner-stated).
  The consequence is interpretive and mine: the headline mixes "agent acted" with "gateway
  restored", and only the conditional rate answers the gateway question.
- 744 off-turn `absent` hops are owner-stated; the mechanism is confirmed, alignment is not.

## Per-case findings

### memory_anaphora-119 — one call; answer-leg LOC form loss
Declared: `IN/user i8/i9` t1 (fake "мухина инна"/"8 950 483 72 32" vs real "лебедева ирина"/
"8 950 630 21 17"); `OUT/tool_arg i9 t1 crm_find_contact.query.phone` written `+79504837232` →
restored `+79506302117`, `residual {}`; t3 `notify_sms.number`, t4 `courier_book.address.street`/
`contact.name`, t5 `ticket_create.subject/text/phone` all `absent`; memory hops i9 t3, i11/i10
t4, i8 t5 `observed`.
Answer: raw `…к Юдину Геннадию по адресу Сарапул, ул. Ивовая, д. 146, кв. 68?` → restored
`…к Морозову Леониду по адресу сарапул улица новая 119 кв 176?`. Positive: the dative name
`Морозову Леониду` is restored in the agent's case. Negative: extra answer hops `"сарапул"` vs
`"Сарапул"` → `[case_class]`; `" улица новая"` vs `", ул. Ивовая"` → `[case_class, commas,
generic]`.
Class: the `absent` hops are **agent-behaviour** (C/C2 made more calls than I); the answer LOC
misses are **engine**. Root cause: `observe.py:1395-1399` → `form.py:1033-1052`. Regression to
add (not run): raw `Сарапул, ул. Ивовая, д. 146` / restored `сарапул улица новая 119` expecting
`differs == {case_class, commas, generic}`. Certainty: **confirmed by trace**.

### memory_anaphora-028 — observer false `unmasked`; cross-item collision
Real i1 `лебедев`, i10 `Ерохин Пётр`, i11 `Воткинск, бульвар Лермонтова, 23 кв. 196`; fakes i8
`Устинов Назар`, i10 `Лебедев Артур`, i11 `Ивовый бульвар, 71 кв. 144`. `courier_book` written
`"Ивовый бульвар", 71, 144, "Лебедев Артур"` → restored `"Лермонтова", 23, 196, "Ерохин Пётр"`.
Declared optional `OUT/answer i1` (hop 7) returns `status="unmasked"`, `produced=""`,
`reference=""`. The agent never wrote `лебедев`; `reply_raw` holds `Лебедев Артур` — the
substitute for i10, whose surname equals i1's real value. `if occurrences_of(item.type,
item.value, run.reply_raw)` (`observe.py:1321`) reads the real surface inside another item's fake
and reports "the gateway never minted a substitute".
Class: **harness-observer** (confirmed). Root cause: `observe.py:1321`, interacting with the
engine minting a substitute containing another item's real surname in one case.
**This is my counterexample to my own leading theory** ("a metric miss is a gateway failure"):
here the metric miss is an instrument error. Regression to add: a fixture where item X's real
surname appears only inside item Y's substitute in `reply_raw`, asserting X is not emitted as
`unmasked`. The engine collision is a **code hypothesis** (needs collision-side evidence).
Honest engine misses in the same case: answer hop i4/i9 `+79252387434` vs `+7 918 724-94-67`
(answer loses phone grouping); `courier_book.address.street` `Лермонтова` vs `Ивовый бульвар`.

### tool_chain-004 — a real residual leak; declared-turn semantics
Real Миллер Валерий Леонидович, `+79512725489`, Псков/Смольный/52/2; fakes Котов Матвей
Евгеньевич, `+79822248300`, Луговая/89/27. Actual calls at **turn 2**: `address_suggest` written
`"Псков, улица Луговая, дом 89"` → restored `"Псков, улица Луговая, дом 52"`, `residual
{"query": ["луговая"]}`; a second call written `"Псков Луговая 89"` → `"Псков Луговая 52"`, same
residual; a third written `"Псков улица Луговая"` → `"Псков улица Смольный"` (clean). Control C
queried the real `"псков смольный 52"`, so the fake is gateway-caused, not agent-caused.
Class: **engine**, critical — a fake street reached the tool; the engine's own `residual_tokens`
agrees, but the observer's `carries_any` (`observe.py:1150-1152`) is the verdict. Trigger looks
like the house number in the same free-text argument (restores without it, not with it) —
**code hypothesis** over three literal pairs. Declared hops 10-14 sit at turn 3 while the agent
(duly) acted at turn 2; with the owner's clarification that is **not** a corpus defect to fix by
ordinal rebinding — it is a binding-by-causality question — but it does mean `chain_value`/
`chain_form` (`metrics.py:806` requires `hop.declared`) saw `absent` and the real crossings went
unscored. Class **harness-observer (declared-turn semantics) / ambiguous**. Regression to add:
one argument holding `<fake street> <fake house>` with no shared street stem, asserting the
restored leaf carries no needle of the substitute. Residual: **confirmed by trace**.

### prompt_rule-026 — genuine residual; Б27 in the OUT direction
Real i9 dictated `восемь девятьсот пейсят два пятьсот семь сорок шесть пятьдесят четыре`
(canonical `+79525074654`); i7/i10 real address `комиссарова / переулок / 64 / 183`; fakes
`Панов Лев Константинович`, `+79729706081`, `улица Мятная, д. 34, кв. 186`. The agent wrote the
written fake `+79729706081`; the engine restored the **spoken** real and the mock refused
`phone_not_e164` — the known **Б27** asymmetry (`metrics.py:562-570` documents the IN leg; here
it recurs OUT). `delivery_create_order.to_location.address` written `"улица Мятная, д. 34, кв.
186"` → restored `"улица Мятная, д. 64, кв. 183"`, `residual {"to_location.address": ["мятная"]}`:
the house and flat restore to the real 64/183 but the **fake street stays**. This is the same
partial-address-restore defect as 004 and is **engine**, confirmed by trace (real street
`комиссарова` per the spec parts; the flagged piece is the fake). Declared hop 10
(`crm_find_contact.query.phone`, turn 3) is `absent` because the call is turn 1 — the free-agent
case again, not to be rebound by ordinal.

### long_order-058 — dual-notation phone is engine scope
Real `+79889990949`, written by the customer as i4 `+79889990949` and i9 `8 988 999 09 49` (one
identity `p58`); fake `8 990 807 27 70`. IN/tool hop 8 `contacts[].phone` produced
`8 990 807 27 70` vs reference `+79889990949` → `differs` (prefix `eight` vs `plus7`, grouping
`3-3-2-2` vs `solid`). Given the owner's scope ruling, the engine must mirror **each source
occurrence's** notation; rendering the tool result's `+7` form with the user occurrence's
`8 …` notation is an **engine** miss, not a corpus artifact. Positive: the answer preserved the
notation (`reply_raw 8 990 807 27 70` → `reply 8 988 999 09 49`). Declared OUT hops 12-18 at
turn 7 versus earlier actual calls: declared-turn semantics, free-agent case.

### long_support-027 — answer/tool form loss; metalinguistic corruption
Real Миллер Валерия Леонидовна, `8 977 122 70 49`, `Курск, переулок Загородный, 16 кв. 142`.
Declared answer hops 24/30 produced `+79771227049` vs reference `8 947 028 21 09` → `differs`
(answer leg emits canonical while the tool-arg leg follows the agent). Extra
`crm_upsert_contact.contact.address.street` produced `загородный` vs reference `переулок
Вишнёвая` → the marker `переулок` is dropped. Both **engine**. The note restore is a semantic
corruption: written `…в карточке было «ул. Вишнёвая» — исправлено на переулок` → restored
`…в карточке было «загородный» — исправлено на переулок` — the engine replaced a **quoted**
mention of the fake and inverted the note. Class **engine/ambiguous** (stateless substitution
cannot know the agent quotes the fake as a string). Undeclared `contact.address.city`
`Курск`/`Курск`, `item_id ""`, `status="unmasked"` is counted in `form_hOUT` although nothing
was masked — class **harness-observer** (see below).

## `form_hOUT` denominator, judged

`unmasked` merges (a) a leaf the agent wrote with nothing restorable — real values it typed
itself, place references (`Курск`, `Псков`, `Миллер`), emitted with `item_id ""` by
`_extra_call_hops` (`observe.py:1370-1383`) — with (b) a genuine gateway failure. Every one is a
miss (`metrics.py:588-590`). The 68.98 % headline therefore mixes real form misses (119, 027,
028, 058), the `item_id ""` class, and the excluded residual class (415, owner-stated) shown
nowhere. This is the largest interpretive risk in the run. **I did not test whether the
`item_id ""` class dominates**; that needs the count I was told not to compute.

## Seams (proposals only)

1. **Causal hop binding.** Bind a declared hop to an action by its data/action lineage, never by
   any-turn ordinal, and never across a correction/retry. Report an `off_turn`/unbound cohort
   instead of silently booking `absent`.
2. **Same-case behavioural controls as the gate.** Publish C/C2-vs-I deltas per case beside the
   absolute lines; the `absent`/`unmasked` classes are behavioural and the controls are what
   measure them.
3. **Denominator ledger per line.** Generalize `BESIDE` (`report.py:121`) into a computed table
   of excluded statuses; `form_hOUT` currently drops `residual` with no caption.
4. **Split "did the agent act" from "did the gateway restore".** Publish the conditional rate
   beside the unconditional floor.
5. **Address-restore completeness.** 004 and 026 are the same defect: house/flat restore while
   the street fake survives in a free-text/by-field address. A residual must be a component the
   gateway was *obliged* to change, and the engine must change all of them.
6. **One answer-form policy, and a cross-item collision guard** (`028`): decide whether answers
   follow the agent's notation (names already do) or canonical, and forbid a substitute that
   contains another item's real surface in the same case.

## Disclosures

Sample investigation, not exhaustive (owner: 24 of 450). No reproducer, no eval, no analytics
script, no git. I did not inspect the other exported cases, per-case metric rows,
`judge.py`/`build.py`/`harness.py` in depth, arms B/D, or controls beyond 119/004/058. Owner
counts were not re-derived. The engine-side collision (028), the 004/026 address trigger, and the
answer-LOC marker policy are code hypotheses, not verified engine results.
