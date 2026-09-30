# M1a independent design/RED review — REVISE (bounded)

**Verdict: REVISE the fixture/evidence isolation before treating the eight checks as an implementation acceptance suite.** The five target properties are legitimate under the approved owner rules; their reproduced failures are not setup errors. Four REDs directly demonstrate the named prototype limitation. The provenance RED identifies a real absence-of-proof problem, but its current fixture also contains an inconsistent gateway counter and must not become a special-case `99 > 1` repair. The positive value/restoration controls need explicit disclosure evidence once provenance becomes conservative.

This is a design review, **not G2 PASS** and not permission to change the engine, historical scorer, host API, raw run, or old `answer_real`. Parent owns implementation. Only this review was written.

## 1. Evidence read and checks executed

Read [SPEC](<research/quality-sprint-2026-09-30/work/M1a/SPEC.md>), [RED source](<research/quality-sprint-2026-09-30/work/M1a/red_truth_conditions.py>), [RED log](<research/quality-sprint-2026-09-30/work/M1a/RED.log>), [RED results](<research/quality-sprint-2026-09-30/work/M1a/RED-RESULTS.json>), [GATE](<research/quality-sprint-2026-09-30/work/M1a/GATE.json>), the entire [preserved M04 prototype](<prototype/bench/agentpii5/answer_restoration.py>), [owner decisions](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L35-L43>), [later decisions](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L12-L17>), and targeted contracts/fixtures/harness/value-reader source.

Executed a pure read-only replay of all eight fixtures using `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python`, `runpy.run_path(..., run_name='review_definitions_only')`, the defined `fixture` function, and direct `answer_events`/`aggregate` calls. **Did not call `run_checks()`**, because that would rewrite the owner's saved RED results. Independently reconstructed the eight predicates, asserted agreement with every saved pass/fail, and checked six input hashes before/after. Command exit **0**. Result: **3 PASS / 5 RED exactly reproduced**. No engine/provider import, no payment/live call, no raw trace mutation.

Input SHA256s at review:

| Input | SHA256 |
|---|---|
| RED source | `9cf2a0856f2a89a9aec61beccb7753f852f966e55772520c2fbab2b87bd9f6a3` |
| SPEC | `ea02c2944b14b38be22e7f188214f2d8be23751032efa41fe5f4a966a6bf14ad` |
| RED log | `45e02e48b04e040a6f428eaee30df396b11f69b269f67bd2294876d2d5270cd9` |
| RED results | `4f10b6e10894af0d29cf8bffdb157fdf980afd30e1939b2757df919f591ca7d0` |
| GATE | `fa765c2f1977e8d0ef8b2bbc11fedf217a192918d116f129648f205bd392c847` |
| M04 prototype | `0fe7ec381e5d870ce2b2eacbf7fe09f7cebfdaf44f89012bc81c071484a51ff5` |

## 2. Are the five RED assertions legitimate?

| Check | Exact current result | Review |
|---|---|---|
| `exact_copy_does_not_silently_repair_source_typo` | source `игрь`, canonical `игорь`, disclosed fake/raw `егрь`, delivered `игорь`; prototype `matched`, value/form/joint all true | **Valid negative property.** A copied fake must not silently repair the source. `_mapping_rows` selects canonical and then `item.parts` built from canonical; it loses the literal source. `joint_ok==0` is required. It does not require the semantic identity submetric alone to be false if a future design separates identity from literal fidelity. |
| `correct_literal_source_can_earn_value` | same source/fake, delivered `игрь`; `value_wrong`, value0, form1, joint0 | **Valid positive target with an evidence precondition.** With a proved disclosure-to-source mapping, the correct literal must earn value/joint under the exact-copy branch. Current fixture lacks independently tied disclosure proof, just as other positive controls do; enrich it before requiring measurable success from a provenance-safe implementation. Do not turn a correct literal into a failure solely because canonical differs. |
| `unmapped_push_clock_is_not_provider_provenance` | mention push index99/provider response1 → `matched`, joint1 | **Valid conservative principle, fixture revision required.** `msg<=turn` alone is not an exact spelling/source exposure proof. But99 is not numerically later than1 on the same clock: the clocks differ. Moreover the fixture inherits gateway `request_count=1`, so its push index99 exceeds its own recorded push count. This inconsistent record must not be the only witness for missing provenance. |
| `known_initials_not_silent_zero_denominator` | known fake `Пахомова Ольга`, raw `П.О.`, delivered `И.Е.` → zero candidates, answer classified without substitutes | **Valid population assertion.** Owner includes initials/derived forms. At least one raw candidate must remain, possibly unresolved; the test does not require an unjustified identity or success. Add the unchanged `П.О.→П.О.` case and two-person shared initials. Discovery must not depend on restoration changing the text. |
| `street_type_is_value_identity_not_only_form` | expected `переулок Пушкина, дом 14`, delivered `улица Пушкина, дом 14` → value1, form0, `form_wrong` | **Valid value assertion.** Owner explicitly made street type identity. `_place_equal` reads street/house/flat but discards street type. A form failure does not repair this false value pass. Add a positive same-type variant and an unresolvable type-omission case so “all LOC values false” cannot pass. |

Sources: [RED predicates:40–60](<research/quality-sprint-2026-09-30/work/M1a/red_truth_conditions.py#L40-L60>), [canonical/parts selection:176–199](<prototype/bench/agentpii5/answer_restoration.py#L176-L199>), [LOC comparison:668–692](<prototype/bench/agentpii5/observe.py#L668-L692>).

The three positive controls are useful and reproduced exactly: two repeated fakes yield one matched + one residual; `c-3→c-8` yields changed text; delivered fake remains residual even when `reply_whole` is correct. They are not a complete alignment proof and must keep working with an explicit valid evidence fixture.

## 3. R1 — fix provenance test isolation, not the owner rule

### 3.1 Three distinct facts

1. [Harness `_push`:388–399](<prototype/bench/agentpii5/harness.py#L388-L399>) increments `_requests` for gateway pushes. [Mention recording:423–439](<prototype/bench/agentpii5/harness.py#L423-L439>) stores that value as `request_index`.
2. [Provider response hook:747–761](<prototype/bench/agentpii5/harness.py#L747-L761>) assigns `ModelResponse.request = len(responses)+1`. This is another clock.
3. [Fixture `_run`:130–138](<prototype/bench/agentpii5/fixtures.py#L130-L138>) sets the **gateway** `request_count=1`. The RED fixture changes mention index to99, but not that count. Thus99 versus provider1 is incomparable;99 versus gateway total1 is internally inconsistent metadata.

Do not repair this with `mention.request_index <= response.request`, a threshold for99, or a fabricated global push→provider conversion. The pure probe also set the total push count to99 and tried mention indices0/1/99; the preserved prototype returned joint1 for **all three** because [availability:153–166](<prototype/bench/agentpii5/answer_restoration.py#L153-L166>) uses only `mention.msg <= response.turn` on user mentions. This demonstrates the unqualified promotion; it does **not** prove which particular historical alias was unavailable.

### 3.2 Required fixture split

- **Invalid-record control:** a push index beyond the recorded push total is an explicit invalid-record diagnostic/refusal, not evidence of future provider knowledge.
- **Consistent missing-link control:** internally consistent independent clocks, candidate fake present, but no verified disclosure→consumer relation. Expect one unresolved candidate, zero joint. Change the numeric values without changing the verdict.
- **Proved-exposure positive control:** same clocks and same raw/delivered bytes, but a validated explicit disclosure relation exists. Expect measurable success. This proves the fix does not reject every legacy/synthetic row blindly.
- **Proved-future negative control:** an explicit relation proves disclosure occurred only after the consumer; do not call it merely missing proof. It must not earn restoration success for that consumer.
- **Competing source forms:** the same person/canonical/fake is disclosed from two different literal sources, only one demonstrably available. If the choice cannot be established, retain uncertainty rather than select the latest mention or an arbitrary list order.

Give **all value/form/alignment-positive fixtures** explicit admissible disclosure/source evidence. Otherwise a correct missing-provenance rule turns them all UNKNOWN, and implementers will be tempted to weaken provenance to satisfy unrelated positives. Test layer separation is essential.

## 4. Bounded additive evidence/API design (benchmark-only)

No new engine or host integration is needed to establish the pure API and truthful legacy behavior. Add M04-local immutable dataclasses and an optional keyword input, e.g. `answer_events(case, run, *, evidence: AnswerEvidence | None = None)`; exact names belong to parent. Preserve the existing output vocabulary or version it explicitly. Do not alter old `HopObservation`, `answer_real`, historical files or shared `values_equal` during M1a.

### 4.1 Separate identities and observations

**Mapping identity:** `(person_identity, pii_type, value_version, semantic_role)`. This identifies the datum, not how many places carried it.

**Disclosure record:** immutable record ID; item IDs/aliases; mapping key; exact real source text and minimal source span/role spans; exact fake surface and its payload span; source message/result ID; original artifact hash/JSON pointer; observed boundary; explicit `available_before_response` relation or unknown/false; verification status/reason.

**Consumer record:** exact provider response request/turn and raw interval in the final concatenated answer; final delivered answer pointer/hash. Multiple text responses in the final nonempty turn must map to their own regions. No “last response probably wrote this” fallback. `reply_whole` is a diagnostic only.

**Availability is tri-state**, not the current false that combines unknown with proved later. A verified evidence builder checks bounds, bytes, record IDs, call mappings, type/role consistency and hashes; callers do not earn a pass simply by supplying a convenient boolean. Synthetic unit fixtures may construct known facts explicitly. Legacy loaders only emit what the saved evidence proves.

### 4.2 What existing records may prove

- A validated original user `where` slice supplies a **source literal**. A `MentionRecord` alone supplies a claimed fake spelling and message number, not a provider request snapshot. Do not promote it because the model later wrote matching bytes.
- A typed tool-result `spans_real` slice plus replaced piece can supply source/fake correspondence only when the piece really covers the declared role/value, not mere overlap. [Harness:470–477](<prototype/bench/agentpii5/harness.py#L470-L477>) records the **first overlapping piece**, so one mention can describe only a part or include another slot. Audit the actual span geometry.
- `call_requests` and `available_results` can prove availability of a result to a consumer; they do not prove that a later alias/version of that result was already visible, or that a whole payload equals one narrow value.
- [Captured model requests:320–333](<prototype/bench/agentpii5/harness.py#L320-L333>) are captured at **gateway pushes**. Their presence does not itself assign a provider ordinal. Associate only if existing chronological/record correspondence proves it; never “zip snapshot number to response number.” Unknown legacy relations remain explicit unresolved mass.
- End-of-run mint data can nominate a candidate, never certify historical exposure. Do not derive benchmark identity from the delivered real value.

The pure evidence API can be implemented and tested now. A safe legacy adapter may initially leave many rows unresolved. That is an honest meter limitation, not proof the engine failed and not justification for demanding new host fields. Any future capture-wiring addition belongs to the separately owned integration stage, not this review.

## 5. Bounded evaluator sequence

### Step A — RAW population before outcomes

Find every occurrence independently of delivered text: whole recorded spellings; complete numeric/date/plate re-notations; strict known-role name morphology; explicitly supported initials/Latin readings. Initials are candidate generators, **not** unique identity proof. No bare short number as a phone/house token, no four-character prefix as person identity. Each repeated span remains its own event.

Deduplicate only identical interval + equivalent mapping/evidence. A whole occurrence can suppress its own redundant subpart hypotheses, but must not erase a conflicting nested owner or an overlapping unresolved value. The prototype's blanket maximal-interval filtering at [248–255](<prototype/bench/agentpii5/answer_restoration.py#L248-L255>) requires an adversarial conflict test. Raw ambiguity must not be resolved by whichever delivered value looks correct.

Count user and tool disclosures equally when they establish the same mapping. More than one causal origin is not automatically more than one identity. Different people/value versions/roles, unresolved competing availability or different exact-copy source obligations remain uncertainty.

### Step B — choose the expectation per disclosure/occurrence

- **Exact copied fake:** bind to the specific disclosed source literal. `егрь → игрь` can pass; `егрь → игорь` cannot earn joint success. Do not use canonical-derived `item.parts` as that literal. The canonical can still represent identity separately.
- **Changed form:** use a proved value/role identity and the supported form transformation actually written by the model. Do not silently accept a fuzzy typo correction. If the source form or transformation is not identifiable, label it unresolved/form-unmeasured rather than canonical success.
- **Partial role:** require only the real role corresponding to the copied role. Do not demand a patronymic the model omitted; do not repair role information by guessing from a broad sentence.
- **Address identity:** normalize abbreviations of the same street type; preserve its semantic class. Street vs lane is value-wrong, not only different presentation. Missing type with multiple possible identities remains unresolved. Implement this in the new versioned M04 reading; shared historical reader changes wait for M1c.

A useful output split is `identity_value_ok`, `literal_copy_ok`, `form_ok`, plus `joint_ok`; if retaining `value_ok`, define exactly how the exact-copy branch treats the source literal. Whatever names are chosen, the existing RED's positive literal outcome must be earnable **with valid evidence**, and a silent correction must not earn joint success.

### Step C — local delivered intervals and literal gaps

SequenceMatcher can propose alignments; it cannot certify a unique mapping merely because each diff stays inside a raw token.

A bounded conservative approach:

1. Partition raw into minimal candidate-token intervals and intervening literals **before** reading delivered.
2. Compute monotone correspondence using literal anchors, token boundaries and length changes; never choose a candidate identity or occurrence assignment because one matching makes value score green.
3. Require agreement on each delivered interval across admissible alignments. Repeated anchors, adjacent tokens or crossing edits with multiple assignments yield alignment-unresolved. Put a work cap on ambiguous alignment enumeration; cap exhaustion is UNKNOWN, not an optimistic arbitrary path.
4. Check prefix/infix/suffix literals exactly. A gap changed (`c-3→c-8`) is a separate fidelity failure even if every token restores. If the correspondence itself is unprovable, fidelity is unresolved, not preserved.
5. Test local delivered value/form/residual at the fixed interval. Real value elsewhere does not rescue this occurrence. Same fake repeated twice with one successful replacement has one pass and one failure, not item-level success.
6. Use actual `base.reply` for customer delivery; correct `reply_whole` never rescues a streamed residual.

Also pin an unchanged fake and a changed unrelated literal in a **no-token answer**. Be explicit that unrecognized new spellings are a discovery blind spot: “all candidates” is not “all possible personal data.” Do not label all unmatched changed regions proven non-PII damage if an unsupported legitimate substitution may explain them; expose unmapped/uncertain changes separately.

### Step D — aggregate without denominator laundering

Keep owner-approved `joint/all candidates` lower bound and `joint/measurable` beside it, with candidate counts and provenance/identity/alignment/form uncertainty. Zero written candidates is N/A restoration, not100%. A measurable value but unmeasured form cannot earn joint success; show it beside the conditional denominator rather than hiding it.

`answer_restore_clean` requires every raw candidate to pass and literal preservation to be proved. Unknown events remain in the headline but are **not attributed engine bugs**. Retain old `answer_real` unchanged and show that it answers a different, agent-dependent question.

## 6. Minimal sequenced implementation/acceptance plan for parent

1. Preserve these RED artifacts; add a new fixture/evidence layer and the consistent absent/present/future provenance controls. Do not overwrite RED history to make the count look better.
2. Add M04-local immutable evidence structures/validation and versioned API; fixtures with proofs can pass, missing legacy relations remain UNKNOWN. No new host/engine API required.
3. Fix exact-copy literal truth independently of identity canonicalization; add repeated disclosure with different literal forms and source typo/missing spaces/case controls.
4. Extend RAW candidate coverage for initials (unchanged and rewritten), known Latin and partial roles; collision tests, no short numeric/prefix guessing, whole/nested conflict preservation.
5. Add street-type-aware M04 value comparison and same-type positive tests. Keep old shared scorer semantics untouched in this package.
6. Replace heuristic alignment certification with occurrence-local proof/UNKNOWN and exact gap fidelity; adversarial repeated anchors/adjacent types/shared suffix/insertion/deletion/wrong-real-elsewhere tests.
7. Rerun the expanded pure tests plus unchanged historical `answer_real` counters on frozen rows; export events and uncertainties in **new output paths**, not original run files. Independent review again before G2/M1c promotion.

Acceptance is not merely the original five turning green: an all-UNKNOWN implementation must fail positive evidence controls; an all-FALSE LOC comparator must fail positive address controls; a candidate detector that discovers initials only after restoration must fail unchanged-initials; an identity chooser that consults restored values must fail swapped-person tests. Unknown legacy coverage must be printed even if it produces an inconveniently low headline.

## 7. Final disposition

- **Accept:** the five owner-aligned truth-condition requirements, exact-copy vs canonical distinction, raw-first initials population, street-type value identity, delivered-boundary and per-occurrence requirements.
- **Revise before implementation acceptance:** provenance fixture internal consistency and explicit evidence in positive controls; unique local alignment certification; whole/part candidate ambiguity; versioned new value reading without altering the old scorer.
- **Keep G2 FAIL / M1c promotion blocked** until the new version is implemented, positive and negative evidence controls pass, and a separate independent implementation review accepts it.

No model/provider/production/paid calls were made. No engine, scorer, raw run, RED artifact or owner decision file was edited. This review neither invents historical availability nor asks the parent to build a new host/engine integration.
