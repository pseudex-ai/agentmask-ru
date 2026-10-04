# Hop-format audit — Addresses and multi-tool chains (revision 2)

> Codex reviewer note: section 6 mixes two prefix pairs and is not accepted as standalone evidence. The phone refusals are downstream mock-tool refusals, not proof of gateway fail-closed protection. The exposed error echo is a real phone fragment, not proof of the whole phone being disclosed. See [adjudication](README.md). References to owner-supplied checks below mean checks supplied by the coordinating Codex reviewer.

Revised after owner fact-check. **Agent form is the standard at every hop, including answers:**
`+7` stays `+7`, case stays case, a tool name's given/surname order stays the order the tool uses.
The canonical form is **not** a competing authority. Form verdicts and content verdicts are
**separate instruments**: `same:true` on a form axis never says the value is correct, and it is
never evidence about content either way. The owner reports the central replay-10384 run stored
**zero** form mismatches; that is owner-supplied and not re-verified here.

**Retractions from revision 1 (explicit).**
- *Retracted:* "metric/product conflict" for the answer and OUT form misses in `long_order-002`,
  `long_support-014`, `long_order-015`. There is no product rule that licences returning the
  canonical form against the agent's `+7`/`8`/case. Those verdicts are correct; the restore is the
  defect. My earlier citation of "detokenization returns the canonical form" as an alibi is
  withdrawn.
- *Retracted:* "metric leniency" for `long_order-015`. A form match is a form match; content is
  another metric's job. I no longer infer anything about content from `same:true`.
- *Retracted:* "declared-absent = corpus turn-declaration defect" and the "declare a chain, not a
  turn / resolve over any turn" proposal. There is **no fixed-turn expectation**; the comparison
  standard is the **C0/C1 control arms vs I and the causal actions**, not turn pinning. **The
  exports contain only arm I**, so the non-observed hops below are **unresolved**, not corpus
  defects.
- *Retracted:* the `tool_chain-035` triple ("kept the fake house `145а`, real `136`") — I had
  `written`/`restored` reversed. Corrected in §4 from the raw call records.
- *Retracted:* the "digit run with a trailing letter" mechanism and the post-restore
  well-formedness ("schema normalization") proposal.
- *Narrowed:* the `long_support-013` leak claim — re-verified against the literal
  `text_real`/`text_masked` values, and it **survives** (below), now with the exact snippet.

## 1. `tool_chain-017` — turn-3 "absent" hops: unresolved; the real defect is the address

Real input (msg 1): `повторите прошлую доставку по номеру 8-982-385-93-29 а также 2 гектаров`.
Fake read by the model: `8-952-190-62-13`. Written seq 1
`crm_find_contact.query.phone = "+79521906213"` → restored `"+79823859329"` — **a working chain
leg**: the masked return fed the next call and the tool received the real phone. Array-index
erasure (`contracts.py:1930 _erase_indexes`, used by `:1920 hop_owner_of_leaf`) correctly treats
declared `recipient.phones[].number` and actual `recipient.phones[0].number` as one path.

Six hops read `absent` at `turn 3 ord 0`; `call_turns = [1×8, 2×7, 3×3]` and the three turn-3
calls are `order_status` (`ord-1`→`ord-7`; `1`→`7` with `refusal_path order_id_format`; `ord-1`→
`ord-7`). The order chain ran at turn 2 (seq 11) and its values appear as `declared:false`
observed hops (`recipient.name` = `Бударин Ефим Ефимович`, `phones[0].number` = `+79823859329`).
Per the owner's standard I do **not** call this a declaration defect: without C0/C1 I cannot say
whether I acted causally or late. Class = **ambiguous/unresolved**. **[trace]** for the turn/call
tables; **[open]** for the judgement.

Verified defect, raw call seq 11: `written.to_location.address =
"ул. Барбарисовая, д. 3, кв. 228"` → `restored = "ул. Барбарисовая, д. 7, кв. 31"` with
`residual = {"to_location.address": ["барбарисовая"]}`. The seed's real address is
`казань / зацепская / 7 / 31`, so the **fake street survived while house and flat were restored**;
the CRM received a mixed address. The same fake street restored correctly in the same turn in the
free-text leaf `address_suggest.query` (`"казань барбарисовая 3"` → `"казань зацепская 7"`,
seq 10). Class = **engine**. Candidate seam `redact.py:2184 _join_addresses_deep` /
`:2324 _join_one_address` (the composed-field path), **[code]**; the residual is **[trace]**.
Counterexample to the scope theory: same turn, same conversation, same street resolves in the
free-text leaf, so `vault.py:2403 for_conversation` identity is not the cause.

## 2. `long_support-013` — dictated phone breaks the call, and its echo carries the real value

Raw call seq 3/4: `written.phone = "+79042711995"` → `restored.phone =
"восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три восемсь"`.
The tool refused both (`phone_not_e164`, `refusal_path phone`). The agent wrote digits; the
restore returned the customer's **dictated notation**. Under the owner's rule this is a straight
**agent-form failure** (class = engine): a digits-form argument must come back digits-form, and
`redact.py:2030 unmask_arguments` has no notation-mirroring step for phones on the arguments leg.
Regression proof: a phone fake written in digits must be restored in digits (E.164) or the gateway
must refuse the call itself.

**Leak claim re-verified, not dropped.** Four records in `long_support-013` have
`text_real` and `text_masked` as the *identical* value (mechanical check on the two literal
fields — my revision-1 check compared whole lines including their keys and was wrong; the values
are equal). Exact snippet, seq 1 `ticket_find` (error echo):

```
"text_real":   "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три \"\n  }\n}"
"text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три \"\n  }\n}"
```

The same pair is byte-equal for `crm_find_contact` seq 1 (`field query.phone`) and for the two
turn-1 repeats. The decisive cross-check that the echoed words are the **real** value, not a fake:
in the later successful record the engine's own masking maps the contact to
`"phone": "+79042711995"` in `text_masked` against `"phone": "+79265478238"` in `text_real`.
The minted fake is the **digits** `+79042711995` (the string the agent wrote); the error echo is
the dictated words of `+79265478238`, i.e. the real number, unmasked. So the model read a real
value it had never been shown. Class = **engine** (detection of the truncated dictated run —
the echo drops the trailing `восемсь`), mechanism **[code]**, exact text **[trace]**.
The fourteen declared IN hops on `crm_find_contact turn 1 ord 0` are `absent` because that result
is an error with `spans_real = {}` (found at exactly `turn 1, call_ordinal 0`; `observe.py:738
result_for_hop` matches it, `observe.py:989–996` then reports no slot). **Not** an ordinal bug —
that hypothesis is refuted: `harness.py:429/508` computes the ordinal per tool per turn exactly
as `observe.py:732 call_for_hop` reads it, and `contracts.py:143` states the contract.

## 3. `long_order-002` — real form failures, plus unresolved turn-2/7 hops

Declared `absent`: `delivery_create_order turn 7 ord 0` (`recipient.name i8`,
`recipient.phones[].number i9`, `to_location.city i10`, `to_location.address i10`) and
`pickup_points_near turn 7 ord 0 address i7`. The arm ordered at turn 5 (written `Гущин Степан`
→ restored `Мкртчян Ашот`, `same:true`). Per the owner's standard: **unresolved**, needs C0/C1;
class = ambiguous, not corpus.

Form failures that stand as **engine** defects under agent form: the answer hop
`i9 PHONE` produced `89821406572` against the written fake `+7 968 206-30-83`
(`differs ['grouping','prefix','separators']`). The value is the real one; the **form is not the
agent's**, and that is a defect, not a metric convention. Positive example: the reply restored the
recipient correctly (`Мкртчян Ашот` ← `Гущин Степан`, `same:true`). The address answer hop
`ица солнечная 104 квартира 203` vs `. Абрикосовая, д. 167, кв. 25`
(`differs ['case_class','commas','flat_marker','house_marker']`) is likewise a form failure.
Whether those same restored values are *content*-correct is a separate metric's question and is
not answered by anything in this file.

## 4. `tool_chain-035` — corrected triples; the surviving fake part is the street

Raw `address_suggest` seq 6: `written.query = "Брянск, Еловая 162"` → `restored.query =
"Брянск, Еловая 145а"` with `residual = {"query": ["еловая"]}`. The seed's real address is
`брянск / пушкина / 145а / 44`, and pii `i7`/`i8` both carry `canonical "пушкина"`. So the fake
house `162` **was** restored to the real `145а`, and the **street stem `еловая` survived** — the
opposite of what revision 1 said. The same holds for `delivery_create_order.to_location.address`:
written `"ул Пихтовая, д. 136, кв. 167"` → restored `"ул Пихтовая, д. 145а, кв. 44"` with the fake
street `Пихтовая` (real `Пушкина`) left in place. This confirms §1's single mechanism and refutes
the trailing-letter hypothesis (the real house `145а` restored correctly *with* its letter).
Class = **engine**, same join seam. The four turn-1 `crm_find_contact` calls repeat §2:
`refusal_path query.phone`, `phone_not_e164`, `parsed: null`, and the observed hop carries the
dictated real (`восемь девятьсот семьдесят семь …`) against the fake `+79316427327`.

## 5. `long_order-015` — truncated fake restored to a truncated real (content question)

Seed real phone `+79129876543`. Raw call, written `+7986337807` → restored `+7912987654`;
and written `+798633780730` → restored `+791298765430`. The fake full form is `+79863378073` (seen in a
later call as written `+79863378073` → restored `+79129876543`). So the agent
wrote a fake **one digit short**, and the restore produced the real **one digit short** — the
form axis correctly reports `same:true` because the agent's form was preserved. Whether the tool
receiving a 10-digit number instead of the 11-digit real is a *content* failure is for the content
metric, not the form metric, and I no longer call the form verdict lenient. Class = **agent
behaviour** (the truncation is the model's) with an engine-side reindex consequence; **[trace]**
for the strings. Working legs in the same case: `+7 985 282 11 96` → `+7 952 732 13 88`,
`Джонсон Майкл` → `Аркадий Юрий` (`observed`, `same:true`).

## 6. `long_support-014` — form failure, and two unresolved hops

`ticket_find turn 3 ord 2` and the answer hop: fake `+7 912 764 73 27`/`8 912 764 73 27` →
restored `+7 925 987 69 22`/`8 925 987 69 22`, `differs ['prefix']`. Under agent form this is a
real **engine** form failure (the `+7` written must stay `+7`), not a conflict with the metric.
Two `absent` OUT hops at `turn 5` (`ticket_find.phone i4`, `callback_schedule.phone i16`):
**unresolved** without the C0/C1 arms; the run's `turn_residual` is 2. Clean legs:
`+79259876922` → `89127647327` (`same:true`).

## Cross-case conclusions (revised)

1. **One confirmed engine defect, seen in three cases**: a fake VALUE inside a *composed address
   field* loses only its STREET to restoration while house/flat restore — `tool_chain-017`
   (`барбарисовая` left in `to_location.address`) and `tool_chain-035` (`еловая`/`Пихтовая` left)
   — while the same street restores in a free-text leaf. Wrong real data is written to the
   customer's system with a 200.
2. **Agent-form violations are real failures, at two legs**: the arguments leg for phones
   (digits in → dictated words out: `long_support-013`, `tool_chain-035` ×4 refusals) and the
   answer leg (`+7`→`8`/canonical in `long_order-002`, `long_support-014`).
3. **The one demonstrable leak**: a refused call echoes the restored real value, and for the
   dictated phone the echo is not masked at all (`long_support-013`, exact fields above).
4. **Non-observed hops are unresolved, not corpus defects.** The exports carry arm I only; the
   owner's standard is C0/C1 vs I on causal actions, and no fixed-turn expectation exists. My
   earlier "turn drift = corpus defect" and every "any-turn resolution" proposal are withdrawn.
5. Absence has at least two mechanically different origins in this sample (a result with no item
   slot because the tool refused; a call that a turn did not contain). That distinction is
   diagnosable from the records (`spans_real`, `call_turns`) and would be worth recording on the
   observation itself — as a **diagnostic**, not as a scoring shortcut.

## Not inspected / limits

- Arm I only; no C0/C1 records exist in this export, so no causal comparison was made.
- The replay-10384 zero-mismatch result is owner-supplied; I did not read that run.
- `long_order-015` (98 calls) and `tool_chain-035` (26 calls) were read at hop level plus the
  raw call records quoted above; their other calls were not read line by line.
- `long_support-014`'s turn-5 calls were not read.
- No engine, harness, corpus or git state was modified; nothing was executed. Every engine claim
  is labelled **[trace]** (what the serialized fields show) or **[code]** (what the source
  implies), never "reproduced".

## Remaining seams (owner-corrected list)

- **Restore must honour the agent's form everywhere** (`redact.py:2030` arguments,
  answer leg): digits stay digits, `+7` stays `+7`, case stays case. This alone covers findings
  2 and 3 of the conclusions and is the same seam `date_form.render_like` already occupies for
  dates.
- **Street resolution inside a composed address field** (`redact.py:2184 _join_addresses_deep`):
  the value the leaf already carries must be resolvable there, not only in a free-text leaf.
- **Record the absence reason as a diagnostic** (no-item-slot vs no-call), computed where the
  observation is made, so a reader never has to guess which one `absent` meant.
