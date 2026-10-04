# Hop-format audit — numbers, dates, JSON tool arguments (revision 2)

Author: bounded DeepSeek Flash investigator. Source: `/Users/igor/Projects/Obscura-v5-codex/prototype` (read-only).
Evidence: six exported cases under `/private/tmp/hop-audit-evidence/cases/`.
Method: human reading of the exported literal fields, plus `rg`/`sed` navigation of `redact.py`, `vault.py`,
`date_form.py`, `structured.py`, `agent_form.py`, `wiki/INVARIANTS.md`, and in revision 2
`bench/agentpii5/form.py` and `bench/agentpii5/observe.py`. No parsing script, no metric label taken as
evidence, no run executed, no reproducer claimed. `→` marks "written by the agent (substitute)" → "restored
(sent to tool / answer)".

## Revision 2 — corrections recorded (explicit)

**C1. §1 misattributed a verdict to the wrong hop; retracted.** In the original
`tool_chain-043.md`, `hop_index 0` (IN/user, item `i10`) prints `produced "8 935 335 03 98"`,
`reference "8 952 705 44 51"`, `verdict {"same": true, "differs": []}` (lines 2288-2293). The verdict
`{"same": false, "differs": ["grouping","prefix","separators"]}` belongs to **`hop_index 5`** (IN/tool,
`crm_find_contact.contacts[].phone`). Revision 1 quoted hop 5's verdict and attributed it to hop 0 and then
built a "contradiction" on the mix. Withdrawn in full.

**C2. The OUT comparison is intentional and correct; "swapped sides"/"inverted" is retracted.**
`form.py:1003 form_match` states it: *"IN hop — produced = the substitute the model read, reference = the
source's surface. OUT hop — produced = the real value the consumer received, reference = the substitute
exactly as the agent wrote it."* `observe.py:1155 _out_call` implements it:
`produced, reference = own_pair(item.type, restored, (item.canonical, item.value), written,
substitute_surfaces(...))`. FORM is compared, never the digits. So `tool_chain-043` `hop_index 19`
(`produced "+79527054451"`, `reference "8 935 335 03 98"`) is a **true and useful** statement: the restored
real did not take the notation the agent wrote.

**C3. IN/tool follows the TOOL result, not the older user notation; no observer defect.** `observe.py _in_tool`
sets `reference = record.text_real[span[0]:span[1]]` — the tool result's real surface. `_in_user` sets
`reference = item.value` — the source's surface. The two hops I had compared therefore answer **different
questions by design**; the "same relation, opposite verdicts" claim is retracted. `hop_index 5`'s
`differs [grouping, prefix, separators]` is a genuine defect: a substitute minted from the customer's message
notation was used to mask a tool result written in another notation.

**C4. The whole cross-cutting section "the observer cannot be used as root-cause evidence" is withdrawn.**
The comparator is type-specific, narrows each side to its own value (`observe.py own_pair`), refuses to score
an empty side as agreement, and reads 0/None-vs-value asymmetries deliberately. Nothing I read in
`form.py`/`observe.py` supports the revision-1 claims.

**C5. "Non-determinism" is downgraded to "state-dependent path".** The same written substitute appearing at
seq 1 and seq 6 sits across **changed vault state** (`shown_forms`, `_call_view`/`Vault.with_written_digits`,
caches), so it does **not** prove nondeterminism under identical state. What is trace-proven is the first
call's argument content. A same-state replay is required before any determinism claim; the central replay can
settle it. Revision 1's "one literal input, two outputs" is retained only as a description of what the export
shows, with that limit stated.

**C6. Schema coercion is withdrawn.** Revision 1 recommended rebuilding tool values into a schema-valid
(E.164) form. The owner's requirement is the opposite: the architecture must follow the **agent's** written
form — case, grouping, separators, and its errors preserved — and must never silently normalize to what a
schema wants. Every "should be E.164" in revision 1 is replaced by "the real digits in the form the agent
wrote". The mock's `phone_not_e164` refusal is evidence that words reached the tool, not a licence to coerce.

**Retained, well supported:** spoken-written identifiers reaching tools as words; free-text address restore
attaching a real house to a fake street; prefix/grouping form defects (mint from the wrong surface, restore
from the wrong surface). **Not inspected in either revision:** `contracts.FORM_FEATURES` and the individual
feature extractors, `form_tables.py`, and the hop-scoring pipeline's own tests.

## 1. tool_chain-043 — the fake mirrors the user, not the tool result; the restore drops the agent's grouping

Case `tool_chain-043`, arm I, turn 1. Customer wrote `телефон 8 952 705 44 51`; spec holds canonical
`"+79527054451"`, `parts.digits "9527054451"`.

Working example: `crm_find_contact.query.phone` `+79353350398 → +79527054451`; the declared=false OUT hop
prints `produced "+79527054451"`, `reference "+79353350398"`, `same:true` — form preserved, restore correct.

Observer:
- `hop_index 0` IN/user: `produced "8 935 335 03 98"`, `reference "8 952 705 44 51"`, `same:true`,
  `differs []`. **Independent verdict: correct.** The customer wrote spaced/`8`-prefixed; the fake preserves
  that exact shape. (Revision 1 was wrong here — see C1.)
- `hop_index 5` IN/tool `contacts[].phone`: `produced "8 935 335 03 98"`, `reference "+79527054451"`,
  `same:false`, `differs ["grouping","prefix","separators"]`. **Independent verdict: correct, and the defect
  is real.** Both strings are 11 digits, but one is E.164 and the other is spaced with an `8` prefix, so the
  axes are accurate. Cause: the substitute was minted once from the *message* notation and reused to mask the
  tool result, whose own notation was E.164 (the tool's `text_real` for this field is `"+79527054451"`).
  Class = **engine**, form source chosen from the wrong surface. Certainty: **confirmed by trace.**
- `hop_index 19` OUT/answer: `produced "+79527054451"`, `reference "8 935 335 03 98"`, `same:false`,
  `differs ["grouping","prefix","separators"]`. The agent's reply text (`reply_raw`) wrote
  `Телефон: 8 935 335 03 98`; the restored reply writes `Телефон: +79527054451`. **Independent verdict:
  correct verdict, real defect** — on the OUT leg the agent's notation must be kept, and it was not.
  Same class and certainty as above.

Metric judgement, corrected: the observer is right on all three hops; revision 1's "wrong pair" reading is
withdrawn (C2-C4).

## 2. long_order-014 — a phone dictated in words reaches the tool as words

Customer: `телефон восемь девятьсот пятьдесят ноль шесть сорок ноль один семь`. Spec `i9`
`value "восемь девятьсот…"`, `canonical "+79500640017"`, `digits "9500640017"`.

Call seq 1 `crm_find_contact`:
`written {"query":{"phone":"+79785192099"}}` →
`restored {"query":{"phone":"восемь девятьсот пятьдесят ноль шесть сорок ноль один семь"}}`,
`refusal_path "query.phone"`, `refusal_rule "phone_not_e164"`, `parsed null`.

Intended: the tool receives the **real digits in the form the agent wrote** — the agent wrote E.164, so
`+79500640017`. Independent verdict: **engine defect — the customer's spoken spelling was handed to the tool
and the call died.** This is trace-proven: the literal restored leaf is the word string and the mock's own
refusal is recorded.

Cause (**code hypothesis, not trace-proven**): `redact.py:673 _unmask` runs
`_restore_verbatim_spans(text, literals.forms)` first and closes those ranges to later passes ("A restored
range is closed to every later pass"); `redact.py:915 _restore_verbatim_spans` returns the customer's literal
slice for any form the dialogue was shown, and for a spoken-written phone that slice is words. The pass built
for this — `redact.py:1201 _digits_in_form_of`, whose docstring records "54 of 54 phone arguments refused by
the mock for `phone_not_e164`" — never runs, because verbatim already owns the span. It would have produced
the agent's form (`plus` true, counts differ, 10-12 digits both sides → `_same_shape` with the last ten real
digits). I did not run this, so the branch winner is an inference from the code and the exported string.

State across time (**C5**): `notify_sms` (seq 6) carries the **same** written `+79785192099` and restores to
`+79500640017`, accepted. The two calls do not share a vault state (`_call_view` at `redact.py:604` installs
`Vault.with_written_digits`, `vault.py:2551`), so this shows a **state-dependent path**, not nondeterminism
under identical state. The observer records the refused OUT argument hop as `status: "absent"`; on the
corrected reading that is the declared-hop bookkeeping, and the miss it represents — a tool argument that
never carried the value — is a real coverage question for the replay, not a verdict error.

## 3. prompt_rule-007 — same written phone, words then digits, in one case

Customer (spoken) `восем девятьсот двадцать два шестьсот восемьдесят шесть шестьсот одиннадцать четыре`.
- seq 1 `crm_find_contact`: `+79842990029` → the word string, `refusal_rule "phone_not_e164"`.
- seq 6 `crm_find_contact`, same `+79842990029` → `+79226866114`, accepted.
- seq 9 `notify_sms`, same `+79842990029` → `+79226866114`, accepted; the address in the same text restores
  (`Черёмуховый проспект, 104` → `Добролюбова, 134`), so the call was not wholly refused.

Independent verdict: **the same trace-proven defect as §2 on the first call**; the later calls show the path
depends on accumulated state (**C5** — no determinism claim). Class = **engine**; certainty: **confirmed by
trace** for the content of seq 1, **code hypothesis** for the branch.

## 4. long_order-057 — the fake street survives, the real house is restored under it

Customer: `везите на краснодар переулок дзержинского 177кв235`; real street `дзержинского`, substitute street
`Луговая`.

`delivery_create_order` seq 3:
`written to_location {"address":"переулок Луговая, д. 116, кв. 93", …}` →
`restored {"address":"переулок Луговая, д. 177, кв. 235", …}`, `residual {"to_location.address": ["луговая"]}`.

Independent verdict: **engine defect on the tool leg.** House and flat restored (116→177, 93→235) while the
street name did not, so the tool is asked about a street that exists nowhere, on the real customer's house.
Positive counterexample in the same case: `courier_book` seq 5 restores the split-role address correctly —
`street "Луговая" → "Дзержинского"`, `building 116 → 177`, `sflat 93 → 235` — so the failure is specific to
the single free-text `address` string, where street and house are resolved as independent tokens and the
phrase key never binds. Same shape in `tool_chain-041`
(`"улица Осиновая, 165, кв. 119" → "улица Осиновая, 177, кв. 49"`, residual `["осиновая"]`, again in
`crm_add_note` seq 9) and `tool_chain-043` (`"Брянск, ул. Речная, д. 21" → "Брянск, ул. Речная, д. 41"`,
residual `["речная"]`), while the street-only form in 043 (`"Брянск, улица Речная"`) restores the real street
(`"Брянск, добролюбова"`) and drops the generic word.

Class = **engine** (the open half recorded in `INVARIANTS.md#swap`); root-cause seam is
`morph_places.split_roles`/`in_form_of` plus per-token restore in `redact.py`'s `_restore_*_spans` passes — the
phrase is linked by conversation through `place_parts` yet is not resolved as one unit before the house token
restores on its own. Certainty: **confirmed by trace** for the mixed output, **code hypothesis** for the
binding step.

## 5. memory_anaphora-066 — the agent's grouping is discarded on the way back

Customer wrote `8-987-449-33-99`. Agent's substitute in the same grouped notation:
`escalate_to_human.summary` contains `тел. 8-964-201-16-65`; `restored.summary` contains
`тел. +79874493399`. `crm_find_contact` seq 1 agrees (`8-964-201-16-65` written as `+79642011665` →
`+79874493399`).

Intended, per `INVARIANTS.md#swap` ("on the way back the real value takes the form the AGENT wrote") and per
the owner's rule (**C6**): `8-987-449-33-99`. Independent verdict: **engine defect — the agent's form is not
kept**; the same rule the `tool_chain-043` answer hop breaks (§1, hop 19), here without a refusal.
**Counterexample to revision 1's leading theory** ("the tool leg returns the customer's literal, so a spoken
identifier leaks words"): here both the customer's literal and the agent's notation are discarded and the
canonical is returned instead. So the OUT phone form has no single rule today: §2-§3 return the customer's
words, §5 returns the canonical, §1's working example returns E.164. That inconsistency is the finding; which
of the two wrong sides wins is state-dependent and needs the replay (**C5**).
Class = **engine**; certainty: **confirmed by trace.**

## 6. tool_chain-041 — the same address split, and a working phone

Customer phone written `8-962-009-14-09`; fake `8-962-365-05-98`. `crm_find_contact` seq 1
`+79623650598 → +79620091409` accepted — **positive**. IN/user hop `same:true` (fake mirrors the customer);
IN/tool `contacts[].phone` `produced "8-962-365-05-98"`, `reference "+79620091409"`, `same:false` — the same
real defect as §1, correctly flagged. Address follows §4:
`"улица Осиновая, 165, кв. 119" → "улица Осиновая, 177, кв. 49"`, residual `["осиновая"]`; street-only
`"Осиновая" → "Загородный"` (real, no generic) — again split behaviour.
Class = **engine** (address) and **engine** (mint notation source); certainty: confirmed by trace.

## Dates: a deliberate negative result

Across all six cases every `DOB` is ISO-in/ISO-out: 1972-08-10→1972-04-21 (043), 1991-06-04→1991-06-09 (057),
1976-04-23→1976-03-16 (066), 1985-02-22→1985-09-16 (041); each observer hop `same:true`. Future intervals
(`2026-09-10T09:00:00+03:00`, `2026-09-02T11:00:00+03:00`) reach the tools **untouched** — correct: a bare
date is not PII and becomes personal only by association (`INVARIANTS.md#dates`). `date_form.render_like`
(`date_form.py:72`) has no case here where a non-ISO customer notation met a tool argument. **The date seam is
not implicated by this sample** — a counterexample to "numbers are broken everywhere".

## Findings, ranked (revision 2)

1. **Spoken-written identifiers reach tools as words, not in the agent's form.** 014 seq 1, 007 seq 1;
   `phone_not_e164`. Trace-proven; branch is a code hypothesis.
2. **The restore and the mint each pick the wrong surface for phone notation.** Mint from the message
   notation vs tool result (§1 hop 5, §6); restore discarding the agent's grouping (§1 hop 19, §5). Form
   comparison is followed correctly; the engine is what breaks it, in both directions.
3. **Free-text addresses restore the real house under the fake street** (057, 041, 043), while the split-role
   path restores them correctly — a missing phrase key, not a missing value.

Withdrawn from the ranking: revision 1's #2 "the tool leg is not deterministic" (state-dependence only,
**C5**) and its observer-defect claims (**C1-C4**).

## Minimal regression proofs to add (not run)

- **R1** `test_argument_form.py`: on a **fresh conversation, first call**, `unmask_arguments` of a leaf holding
  the substitute for the 014 spoken phone must contain the real digits **in the agent's own notation**
  (`+79500640017` for an agent that wrote `+79785192099`); today it contains the customer's words. Same shape
  for 007. This pins the trace-proven defect without asserting anything about later calls.
- **R2** state replay (**C5**): run the same leaf at call 1 and at call 6 and **record the vault state between
  them** (`shown_forms` rows, written digit runs), asserting only what the state justifies — the test that
  settles path-dependence versus nondeterminism, which the export cannot.
- **R3** address: `unmask_arguments` of a free-text `address` holding a fake street must leave no token of the
  fake street (`surviving_substitutes` empty) and must not attach a real house to it.
- **R4** form authority: for the 066 case, an agent that wrote `8-964-201-16-65` must receive the real digits
  in that grouped notation (`8-987-449-33-99`), and an agent that wrote a wrongly-cased or mistyped leaf must
  get that same shape back — never a normalized one (**C6**).

## Architectural seams (proposals only, no patch)

- **S1 — one form-authority rule: the AGENT's written surface owns the form on the way back, for every type.**
  Today the OUT leg can return the customer's literal (words), the vault canonical, or the agent's form,
  depending on the path. The seam is a single resolver consulted before spans are closed, whose answer is
  "the real content laid into the agent's written shape" — never a schema shape, and never the customer's
  literal for a leaf the agent chose a notation for. The customer's literal stays correct for prose, typos and
  look-alike repair; it must not outrank an identifier leaf the agent wrote.
- **S2 — two named restore views instead of one `for_tool` flag**: `restore_for_display` (customer literal,
  prose agreement) and `restore_for_tool` (real digits in the agent's form), sharing one vault read. The two
  promises currently ride one boolean through five passes, which is how both wrong surfaces stay reachable.
- **S3 — resolve the maximal address phrase on the tool leg as one key, then components.** The detector
  already merges maximal address spans on the way in; the way back should reuse that unit so a house can never
  be restored under a street that failed to bind.
- **S4 — instrument observability, not a defect claim:** record per argument hop what the tool leg actually
  received (pre-restore leaf, post-restore leaf) alongside the tool's own acceptance, so the class of §2/§3 —
  a value that never reached the tool — is visible in the stored verdicts rather than only in a mock's refusal
  rule. Kept separate from any verdict logic.

## Disclosed as not inspected

Twenty of the twenty-six evidence files were not opened; the six named above were read in the regions quoted
(calls, answers, observer hops, relevant spec fields), not in full. In revision 2 I read
`bench/agentpii5/form.py::form_match` (with its feature-extractor tables) and
`bench/agentpii5/observe.py::_observed/_in_user/_in_tool/_out_call/_out_status/own_pair`; I did **not** read
`contracts.FORM_FEATURES`, the individual extractors, `form_tables.py`, or the observer's tests, so the exact
feature axes per type are quoted from the exports, not from the contract. `vault._fake_phone`
(`vault.py:796`) and the masking leg's span decisions were not read, so how the mint chooses its grouping is
unverified. No test, eval or reproducer was executed; the only file written is this report.
