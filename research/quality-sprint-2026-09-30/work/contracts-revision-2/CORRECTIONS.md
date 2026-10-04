# CORRECTIONS — contracts revision 2 (A1 · D0 · V0 · C0 · S2)

Status: **independent review response, not a new owner decision.** Version `contracts-revision-2`.
Binding: [GOAL-BRIEF](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md>),
[OWNER-DECISIONS](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md>),
[REMAINING-DECISIONS](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md>),
[EXECUTION.json](<research/quality-sprint-2026-09-30/EXECUTION.json>) and
[REVIEW.md](<research/quality-sprint-2026-09-30/work/review-contracts/REVIEW.md>) (verdict `REVISE`).

No original child report is rewritten. Every correction is a *new* file under
`work/contracts-revision-2/` that points at the raw artifact it corrects. Raw historical evidence
(counts, hashes, logs) is preserved; no `PASS` is fabricated anywhere.

## 0. Evidence and reproducibility of this revision

| item | value |
|---|---|
| independent re-derivation | [verify_facts.py](<research/quality-sprint-2026-09-30/work/contracts-revision-2/verify_facts.py>) → [FACTS.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/FACTS.json>), stdout [verify_facts.log](<research/quality-sprint-2026-09-30/work/contracts-revision-2/verify_facts.log>) |
| command | `cd <repo> && PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/contracts-revision-2/verify_facts.py` |
| exit | `0` (one run; no detector call, no engine import, no network, no git mutation) |
| input pins | 14 files hashed into `FACTS.json.inputs` (each `path` + `sha256`) |
| output hashes | `FACTS.json` sha256 `f6731fae39819df040134f74482607dccc36f187ab8ab1a2b5142abff546c84e`; `verify_facts.log` ends with the same `OUTPUT_SHA256` |
| declared concurrent write | parent owns the new v2-dev `answer_restoration.py` / `test_answer_restoration.py` (on disk: [answer_restoration.py](<prototype/bench/agentpii5/answer_restoration.py>), [test_answer_restoration.py](<prototype/bench/agentpii5/test_answer_restoration.py>)). This revision wrote neither and read neither; pins in `RECEIPT.json.declared_parent_owned_files`. |
| model routing | task routing requested `deepseek-official` / `deepseek-flash`; recorded in [EXECUTION.json](<research/quality-sprint-2026-09-30/EXECUTION.json>) `research_completed`. A model's self-identification is **not** proof of routing, so it is recorded, not claimed. |

`FACTS.json` is machine-readable; the numbers quoted below are the ones it recomputes.

## 1. A1 — O-DATA acceptance manifest

### A1-1 (high) — occurrence-first `whole`, parts as diagnostics

Correction of `units.part_unit` / `whole_coverage_unit` in
[ACCEPTANCE-PROPOSAL.json](<research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json>).

**Now.** A NAME occurrence "expands into its identifying parts" and a masked surname with a live
given name "scores as a miss on the part unit, never as recall"; the naive-units list adds "a case
counted once per field of the same person".

**Corrected wording.**

- The **primary positive unit** is one gold *occurrence* of one PII value (one written span), with
  its identity-cluster key.
- **`whole_closed(occurrence)`** — the whole occurrence is closed: for NAME every written
  identifying part is inside the protected span; for an address the written personal components are
  inside it. Failure of any written part is a **failure of that one occurrence**. The occurrence is
  not split into fractional units and the denominator is not doubled ("whole measured per part" is
  withdrawn).
- **`part_coverage`** and partial-leak counts stay published as **diagnostic columns** beside the
  occurrence number — they explain *where* coverage failed, they never enter the primary
  denominator.

**Why it matters.** `1/2` for a half-open occurrence silently halves the defect and inflates the
headline; the same event must be one failure, and the diagnostic column must not be able to pay for
it.

### A1-2 (high) — type identity vs generic-marker coverage; current public NAME policy

- **`type_identity` axis** (new, separate): the span's type equals the gold type. A correct partial
  NAME span is a true positive **on this axis** and is *not* reported as "the" precision.
- **`coverage` axis**: `whole_closed(occurrence)` above.
- **`boundary/overreach` axis**: characters or tokens protected beyond the gold occurrence.
- **Generic markers are not required to be hidden.** "street type included where written" is
  withdrawn. Per [OWNER-DECISIONS:38](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L38>) a
  service word or an allowed generic toponym must **stay byte-identical, not be substituted**; the
  *semantic type* (street vs city vs house) is preserved in the identity key. The check is therefore
  two checks: marker unchanged, and identity retains the role. "All personal components are inside
  the span" is a separate, weaker requirement.
- **Public/fictional/stage names are positives** and stay in the headline denominator
  ([REMAINING-DECISIONS:9](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L9>)). A
  separately published `public` stratum is a **reporting view**, never an exclusion. The gate
  instrument's 57 `public` labels are a view, not a denominator change. This is settled; it is not
  asked again.

### A1-3 (high) — no ambiguous denominate-exclusion without approval

`ppv_design.estimator` removes `AMBIGUOUS_EXCLUDED` from numerator *and* denominator.

**Correction.** Split the label:

- **`POLICY_NEGATIVE`** — a lexically ambiguous form with no evidence of a name
  («напиши жене»): by the owner's rule it must not be masked, so masking it is a defect and the
  fix runs through the detection rule, not through the denominator. Policy status is fixed by
  [REMAINING-DECISIONS:8](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L8>); the
  *measurement* of that population is question **Q2**.
- **`UNLABELLED/UNRESOLVED`** — a gold case no adjudicator can settle. It is **reported in a third
  row with its own N**, plus a strict lower bound (all unresolved counted as miss) and a
  conditional figure (unresolved excluded), both printed. Silent removal after predictions are seen
  is forbidden.

**Why it matters.** Removing unresolved cases can reward the detector for exactly the mask the owner
forbade, and no owner decision authorises that exclusion.

### A1-4 (high) — independence counter and honest budget

- **Independence (protocol, decided here, no owner input needed).** Print four numbers separately:
  N occurrences, N `(type, identity)` clusters, N source documents/conversations, N template
  families. A template copy that reuses a shape does **not** create an independent unit even with a
  new identity, a new seed or a hidden file. The fallback `(case id, type, identity)` is withdrawn
  as an independence key: where template provenance/shape is unknown the independence status is
  **`INDEPENDENCE_NOT_MEASURED`** and that type/slice cannot be called `≥300 independent`. Extra
  forms stay as **intra-cluster robustness** checks (useful, never counted as support).
- **Budget.** The staged arithmetic is coherent (recomputed: `3000+3000+600 = 6600`,
  `6600+1360+360 = 8320`, `2×8320 = 16640`) — it is a **staged cost**, not the price of the claim.
  The claim actually implies `55 × 300 = 16500` positive units for v6 alone **before** registers,
  PPV, negatives and cluster de-duplication, versus `1360` staged v6 units and `360` fixture units.
  Therefore: 17.8–18.6k review items is an **`ESTIMATE_PRELIMINARY_STAGE`**; it is not
  `ADEQUATE_FOR_FULL_SCOPE`. Which gates it does **not** close is listed in
  [GATES.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/GATES.json>).
- **Labeler vs human.** `2 × units` is two *labeler* passes. Labelers may be independent model
  workers; owner adjudication is a separate count and is **not measured** here. Dollars remain
  unmeasured and uninvented ([ACCEPTANCE-PROPOSAL](<research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json>)).
- **PPV sampling must not break blinding.** Allowed: give both labelers full source contexts with no
  predicted span highlighted, collect all gold spans, then match the frozen PPV sample afterwards.
  Forbidden: showing the prediction to either blind labeller.

### A1-5 (medium) — NEREL version, not parser

Independently recomputed from the pinned annotations: **NEREL-v1.0 = 1907** PERSON annotation rows /
187 dev+test docs, **NEREL-v1.1 = 1908** / 187 docs, both with the same strict contiguous parser and
empty exclusion lists. `inventory_sources.py` reads **v1.1**; the earlier external measurement was
**v1.0**. This is a **source-version difference, not a parser difference and not an engine delta**;
both manifests are preserved separately. The `22 case kinds` axis is a scenario proxy and proves no
coverage of free prose / typed KV / document / RAG / tool-error surfaces.

### A1-6 — already settled, not re-asked

Public names protected; personal entrance/floor protected while generic markers stay unchanged;
small support ≠ full PASS; synthetic isolated CVC quality scope chosen; two blind labelers;
point estimate ≥99% with published CI (lower bound not required ≥99%); `≥300 independent` orient.
These are marked `covered_by_decision_ids` in
[DECISION-COVERAGE.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/DECISION-COVERAGE.json>).

## 2. D0 — mechanism comparison

### D0-1 (high) — no architecture ranking from the wrong gold

`public` sits in `GATE_MUST_NOT` in
[d0_arm_compare.py](<research/quality-sprint-2026-09-30/work/D0/d0_arm_compare.py>) — an **old**
policy. The 25 `fp_public` rows are therefore **not** 25 current defects: after
[REMAINING-DECISIONS:9](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L9>) real public
names are positives, and each row needs independent re-adjudication. The harness must stop calling
the old public policy "must-not".

### D0-2 (high) — explicit negative FP vs unlabelled unknown

The harness merges two different events into `fp_other`: a prediction overlapping a labelled negative
occurrence, and a prediction overlapping **no labelled occurrence at all**. Labelling is
occurrence-level, not whole-text, so `104 other` is **not 104 verified false masks** — an unlabelled
real person can be in that group.

**Correction.** Two separate buckets: `FP_on_adjudicated_negative` and `unlabelled_prediction`.
Only the first can enter an FP/PPV number; the second is what the independent PPV annotation must
resolve. A broad span covering a correct PII value **and** a negative word still needs a boundary
audit; overlap with a negative token alone does not classify it.

### D0-3 (medium) — precise arm descriptions, corrected metric set, no budget from timings

- `RULES_ONLY` disables **only `_ner_spans`** via a subclass. It is **not** "all model/dictionary
  components off"; the word "rules-only" must not be read as a product configuration.
- `HYBRID_UNION` adds only **non-overlapping raw-NER spans**; it is not the literal union and is not
  a mechanism. Neither arm is an architecture candidate.
- The two whole definitions must be labelled and never merged: `whole` = one same-type span contains
  the entire gold vs char-union coverage printed separately.
- `12 DATE→DOB` is a recorded type disagreement on **old** gold under the current owner scope, not a
  new-engine error, until re-adjudicated.
- `12.35` and `7.58` ms/text are two single runs on a shared host: **exploratory, not p50/p95, not
  RSS, not a resource budget** — this stays as written.
- **A corrected-table script or metric-correction script may be written only as new files under
  `work/contracts-revision-2/`**; the saved outputs under `work/D0/out/` are **not overwritten**.
  The corrected table is [D0-METRICS-CORRECTED.md](<research/quality-sprint-2026-09-30/work/contracts-revision-2/D0-METRICS-CORRECTED.md>).

**O-DETECT is not ready.** Ranking before the corrected populations/labels and a real controlled
resource measurement is forbidden; the owner is not asked to choose a family from these numbers.

## 3. V0 — v5/v6 compatibility

### V0-1 (high) — the status vocabularies are ordered by strict inclusion

Independently re-read from the pinned modules (hash in `FACTS.json`):

```text
v5 HOP_STATUSES (8) = observed, leaked, residual, unmasked, absent,
                      engine_kept, not_masked, leaf_foreign
v6 HOP_STATUSES (5) = observed, leaked, residual, unmasked, absent   ⊂ strict subset of v5
```

`unmasked` is **preserved as legacy** in v5; the three split statuses are additions. The child check
`CHK status-funnel` compared the v6 **read-vocabulary** against a v5 **write-population**
(`OUT_HOP_WRITTEN_STATUSES ∪ {absent, leaked}` = 7 values) and therefore lost `unmasked`; the
"neither side contains the other" sentence in [V0/SPEC.md](<research/quality-sprint-2026-09-30/work/V0/SPEC.md>)
is **false**. What is real: the observer funnel/denominators changed, and a historical legacy
`unmasked` row cannot be converted into the three new statuses from its label alone without
evidence. Keeping old readers and current semantics is already approved — **not** a new owner poll
(`covered_by: INTEGRATION-KEEP-V5`).

### V0-2 (high) — correct mutants, honest controls

Under inheritance-of-source-validity (OWNER-Q2), `valid → valid` is the **correct** behaviour.
Therefore old **M8 ("always mints checksum-valid") is not a mutant on a valid source** and
`valid→valid` cannot be the line that separates the correct arm from M8. The child check also
assigned both arms the same formula instead of two real executions. Corrected mutants:

| new mutant | breaks which decided rule | needs |
|---|---|---|
| `valid → invalid` | Q2 inheritance | a checksum-valid source; the substitute must be valid |
| `invalid → valid` | "do not repair the source" (OWNER-Q2/Q3) | an invalid-but-typed source; the substitute keeps the fault |
| wrong form / unsafe identity / collision | form + identity contracts | its own fixture family |
| real-provided positives (controls) | instrument-can-fail | ≥1 real-provided valid and ≥1 real-provided invalid source per checksum type |

Acceptance: the correct arm and each mutant differ on **at least one real execution**, with the
typed-invalid and typed-valid populations **split** (the two denominators named in the report).

### V0-3 (medium) — counts re-derived

`66` registry records = `65` item types + `1` non-item (`DATE`, `item_type=False`) = `11` v5 records
(10 item types + DATE) + `55` v6 records (`pii_types_a` 16, `_b` 15, `_c` 24). `bare_typed=True`:
**0/66**. Checksum-carrying records: **11**, samples checksum-**valid** 11/11 (recheck list in
`FACTS.json.checksum.rows`). "11 v5 item types" and "11 native items" are wrong; the proposed DATE
slice is therefore **`ITEM_TYPES = 10` + `DATE` reported separately**.
`bare_typed=False` is **not** proof that no typed-invalid path exists — cues/field keys are exactly
the signals Q3 admits. It is a **testable engineering gap** (typed-invalid positive + same-shape
business negative), not an open owner rule.
`script` still means alphabet; the claim that its alphabetic meaning moved to `translit` is wrong;
`DERIVED_PIECE_TYPES` equals today and must not change on a verbal argument.
`CHK v5-leaf-and-readings` triggers RED on the presence of `v5_extra` rather than on the absence of
`carried`; as a post-integration acceptance it can never go GREEN — instrument fix, not a fork.

### V0-4 — D-ID collisions are engineering

`D-068/069/070` (and D-070 current-hop PHONE) are used by both branches with different contents.
Assigning new numbers, keeping **both** records and contents, and adding an old→new reference map is
an **existing engineering obligation with its own test** (`covered_by: D-ID-RENUMBER`); it is **not**
a new owner poll. To the owner go only *contradicting contents*, if any.

## 4. C0 — temporary-secret quality contracts

### C0-1 (high) — OPAQUE is reversible; the false fork is removed

`OPAQUE` is **not** an irreversible marker. The renderer is a deterministic redaction derived from
the original (`REDACTED<sha256[:6]>`,
[vault.py:1920](<prototype/pseudex/vault.py#L1920>)), the vault stores the surface `original` in the
same `tokens` row that carries the token ("first writer wins"), and audit stores only
`token`/`preview` — `entities`/`events` never hold the value. O-SECRET-5's
"OPAQUE ⇒ the tool cannot get the value" versus passthrough is deleted; the requirement is the
already-chosen one: mask it, restore it, keep the written form, refuse rather than silently pass.

### C0-2 (high) — in-memory Vault exists; no impossible test-only requirement

`Vault(":memory:", org)` is the normal test path
([test_loop.py:24](<prototype/test_loop.py#L24>), [sqlite_setup.py:264](<prototype/pseudex/sqlite_setup.py#L264>)).
"Every mint is durable, there is no non-persistent path" is false in the test sense. The corrected
boundary: the synthetic isolated quality path uses the **real engine structures** (a real vault, the
real restore path), no real payment value exists anywhere, no retention/admin/TTL/API/HITL
implementation is a prerequisite (deferred by owner), and no production retention or payment-ready
claim follows.

### C0-3 (high) — numeric demotion is "no digits at all", not "malformed"

The guard is literally `if entity_type in _NUMERIC_KEY_TYPES and not any(c.isdigit() for c in value)`
([structured.py:371](<prototype/pseudex/structured.py#L371>)). A short `31`, a wrong-checksum
16-digit PAN and an `A31` form are **not** demoted by it. Length, wrong checksum and "no digits" are
three different predicates and must be three tests, not one sentence.

### C0-4 (high) — the existing regex/window is a hypothesis, not the norm

`(?i:{cues})\D{0,20}?({shape})` is an **engineering hypothesis at the pin**
([assets.py:432](<prototype/pseudex/assets.py#L432>)); the owner chose *proven* context/key
plus a general mechanism, not a 20-character window. A fixed window, a hard `PAN` ban, or trusting
`cid`/`auth_code` as an "authoritative schema" may not be fixed without proof: `cid`/`auth_code` can
be ordinary identifiers in a non-payment context, and a missing adjacent PAN in somebody's 77
examples does not make PAN proximity safe alone. Needed instead: same-spelling pairs with *different*
meanings (not just `cvc` vs `order_code`).
**Fake generation, a fixture profile or a self-check syntax test are never quality rates** — the
fixture self-check validates its own tables only. The 0/14 protected and 10/10 open numbers stay
capability gaps, explicitly not precision.
Length/grammar of an OTP is **not** an owner question: see Q5 — cite the source or mark the gap.

### C0-5 (medium) — count and deferred-lifecycle boundary

`63` is the initial candidate count in a ТЗ, not the implemented registry. The correct reference is
**66 records / 65 items / 55 new (v6) / 11 v5, DATE separate**; no temporary-secret code is in that
list, so the family needs its own allocation and cannot be smuggled in as a v6 alias.
A8's "no real value in any run artifact" means **no real secret**; the synthetic originals **must**
stay in private fixtures/evidence for round-trip checking. Absence of a string in one log proves no
production retention of nothing. Storage/TTL/admin/API/HITL stay out of C1.

## 5. S2 — semantic gap inventory

### S2-1 (high) — `relation_closed` is a proposed metric only

The 26 synthetic episodes, 13 changed texts, 26/26 identical round trip and the marker/untouched
counts are accepted as recorded observations. But "subject replaced **and** every attribute word
gone" is a **proposed** definition, not an approved product contract. Two different promises:
"the name is hidden, the diagnosis stays visible for the agent" vs "the diagnosis is replaced too".
So: `relation_closed` = `PROPOSED_METRIC`, `1/15` = a number under that metric, and
"proven leak of an established relation" is **not** claimed without an accepted threat model and
contextual re-identification analysis. Marker-vs-value may violate the desired form and raises an
agent-behaviour question; the probe **does not** prove how the agent behaved.

### S2-2 (high) — date association is not automatically a MEDICAL rule

[test_coverage_152fz.py:48](<prototype/test_coverage_152fz.py#L48>) **expects** MEDICAL for
«диагноз сахарный диабет» with no named person. Different type policies are not a logical
contradiction. `DX-04` is a recorded mask and a **candidate** scope error under a *new* rule, not a
violation of an already-accepted general association invariant. No MEDICAL change now.

### S2-3 (high) — pronouns are not missed NAME spans

"Subject not found" in a pronoun/role utterance («у него», «пациент») is not the same as a missed
**written** name: no NAME span exists there. Split 8/15 into *unnamed/indirect subject* and *really
missed named name*; never merge them into "detector recall failure".

### S2-4 (medium) — health, income and debt are not one policy

The legal text was read from a mirror and proves no compliance; record-field subject recovery, the
intersection with the 55 v6 types and the real dictionary completeness are `NOT_MEASURED`. Do not
merge health, conviction and income under a single policy. **DATE not MEDICAL policy** is the
correction to `SG-5`. Semantic implementation is **deferred**; the owner's decision is
research-now/implement-later.

## 6. What is deliberately *not* asked again

`≥99% point estimate + published CI` · `≥300 independent positive units` orient · two blind
labelers · lexical ambiguity («жене») not masked and not an automatic FP · possessive/public/
fictional names protected · all NAME parts protected · CVC destinations "any answer of the same
operation" · synthetic isolated CVC quality scope · unit of refusal = the whole affected call/answer
· no new provenance API fields · explicit agent form over schema · source validity inheritance ·
keep the current v5 semantics/readers · lifecycle/admin/API/HITL deferred · semantic implementation
deferred. Each carries the id of its decision in
[DECISION-COVERAGE.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/DECISION-COVERAGE.json>).

## 7. Unknowns that stay unknown

1. True independence of synthetic template families on this host — `INDEPENDENCE_NOT_MEASURED`.
2. OTP/3DS grammar and length — not established from the sources read here. **Research gap**, not an
   owner question (see Q5).
3. Real p50/p95/RSS for every D0 candidate — `NOT_MEASURED`.
4. Real human adjudication hours and dollars — `NOT_MEASURED`; no number invented.
5. Whether a 3DS one-time value is SAD, and production retention readiness — out of scope
   (`deferred`).
6. Production digest of the deployed artifact — `NOT_VERIFIED` (B0/RG).
