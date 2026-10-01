# O-DATA — corrected acceptance manifest (`contracts-revision-2`)

Status: **proposal for the O-DATA checkpoint**, `status = OWNER_PENDING`. This supersedes the
*proposal* in [A1/ACCEPTANCE-PROPOSAL.json](<research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json>)
only where [CORRECTIONS.md](<research/quality-sprint-2026-09-30/work/contracts-revision-2/CORRECTIONS.md>)
§1 says so; the original artifact and its raw counts stay untouched and citable. Machine-readable
parts: [SLICES.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/SLICES.json>),
[BUDGET.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/BUDGET.json>),
[GATES.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/GATES.json>),
[DECISION-COVERAGE.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/DECISION-COVERAGE.json>),
questions [OWNER-QUESTIONS-6.md](<research/quality-sprint-2026-09-30/work/contracts-revision-2/OWNER-QUESTIONS-6.md).

No final gold is produced, no sample is chosen from detector predictions, no detector was run.

## 1. Registry scope (corrected)

| quantity | value | how re-derived |
|---|---|---|
| v6 registry records | **66** | `verify_facts.py` AST over `pii_types.py` + `pii_types_a/b/c.py` |
| item types among them | **65** | `item_type=True` |
| non-item record | **1** — `DATE`, `item_type=False` | same |
| v5 records | **11** = 10 item types + DATE | same |
| v6 records | **55** (`_a` 16, `_b` 15, `_c` 24) | same |
| `bare_typed=True` | **0** | same |
| checksum-carrying records | **11**, samples checksum-valid 11/11 | `checksum_v6` on the pinned samples |

Item types to claim per type: **10 native item types**, with `DATE` reported as its own separate
line (it is not an item). The temporary-secret family (CVC family, ISSUER_OTP and the Q4 subclass
scope) is **additional**; it is not in the 66 and must not be smuggled in as a v6 alias.

Out of scope here: lifecycle/storage/TTL/admin/API/HITL (deferred by owner), production payment
enablement, new provenance API fields.

## 2. Units (corrected)

- **Primary positive unit** = one gold **occurrence** of one PII value of one type in one case, with
  its slice and its identity-cluster key.
- **`whole_closed`** = that occurrence is closed: every **written identifying part** is inside the
  protected span (NAME: surname/given/patronymic/initials/possessive form, each only when written;
  address: the written personal components). A failure of any written part fails that **one**
  occurrence. There is no per-part fraction and no per-part denominator.
- **`part_coverage` / partial-leak count** = published **diagnostic** columns. They explain where
  coverage failed; they never move the primary denominator.
- **Generic markers** (street-type words, allowed generic toponyms, service words) are **not**
  required to be hidden: the check is (i) marker byte-identical, (ii) the identity retains the
  semantic role. "Street type included where written" is withdrawn as a coverage requirement.
- **PPV unit** = one detector-positive span from the blind split, adjudicated against source text
  only.
- **Specificity unit** = one pre-registered hard negative that must stay unmasked.

**Independence (protocol).** Four counts are always printed separately: N occurrences, N
`(type, identity)` clusters, N source documents/conversations, N template families. Repetitions,
template copies, a re-seeded copy and a hidden file from a known family are **not** independent
units. Where template provenance/shape is unknown the set is
**`INDEPENDENCE_NOT_MEASURED`** and cannot be counted toward 300. The earlier fallback
`(case id, type, identity)` is **withdrawn as an independence key**. Extra forms remain
intra-cluster robustness evidence (useful, not support).

## 3. Blinding

Two labelers, both see **raw source text only**; neither sees predicted spans. If a PPV estimate is
wanted, both label full source contexts **without highlighting any predicted span**, all gold spans
are collected, and the frozen PPV sample is matched **afterwards**. Showing a prediction to either
labeler is forbidden. The 15 known-diagnostic sets stay `known_diagnostic`; the blind acceptance
split is generated fresh at freeze and its labels are held by the named custodian (Q3). The 359-ID
tier may stay a secondary diagnostic tier with its `0/359` caveat printed; it is not blind.

## 4. PPV / specificity (corrected denominator)

- Frame: `PPV_frame` = detector positives inside the frozen blind split; hash recorded **before**
  sampling; stratified per `(type × register)` with a published seed.
- Labels per span: `TRUE_PII_TYPE_EXACT`, `TRUE_PII_TYPE_PARTIAL`, `WRONG_TYPE`, `NOT_PII`,
  `POLICY_NEGATIVE`, `UNRESOLVED`.
- **Three numbers never merged:** (i) type identity — does the span contain PII of the claimed type;
  (ii) coverage/whole-closed; (iii) boundary/overreach.
- **Denominator rule.** No `AMBIGUOUS_EXCLUDED` bucket: `UNRESOLVED` is printed as its own row with
  its N, next to (a) a strict lower bound counting every unresolved case as a miss and (b) a
  conditional figure with unresolved excluded. `POLICY_NEGATIVE` is governed by the detection rule
  (do not mask a single ambiguous form), not by a numerator convenience; its measurement population
  is Q2. Removing unresolved cases after predictions have been seen is forbidden.
- Specificity is the false-mask rate on the pre-registered negative frame, reported per negative
  family — **never** called PPV. Authored "one negative per case" is not an independent negative
  frame; the frame must be re-drawn from real prose when the over-masking corpus is regenerated
  (`ru_prose.jsonl` is 0 bytes on this host — an absence, not a PASS).

## 5. Slices and support

See [SLICES.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/SLICES.json>): the
axes are `pii_type × register × surface × hop_direction × transport × document_form`, with
`independence_status` attached to each slice row. A `(type, register)` row gets a headline
recall/whole/PPV claim only with ≥300 **independent** positive units; below that it is
`DESCRIPTIVE_INSUFFICIENT_SUPPORT` and stays visible. `22 case kinds` is a scenario proxy and does
**not** prove coverage of free prose / typed KV / nested JSON / document / RAG / tool-error
surfaces; those must be mapped explicitly before a slice is called covered.

## 6. CI and statuses

`x/n` + point estimate; headline requires point estimate ≥99% (owner Q1), CI published, lower CI
bound **not** required ≥99%. Wilson 95% for independent units plus a cluster bootstrap (10 000
resamples) over identity/document clusters, with design effect and effective n printed. TOST at
δ=3pp only for explicit "no effect" claims; McNemar only for a paired difference. Empty denominator
→ `NOT_MEASURED`. No averaging across heterogeneous types/registers.

Typed statuses are enumerated in [GATES.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/GATES.json>).

## 7. Budget

See [BUDGET.json](<research/quality-sprint-2026-09-30/work/contracts-revision-2/BUDGET.json>). The
staged arithmetic is reproduced exactly (6600 / 8320 / 16 640) and is labelled
`ESTIMATE_PRELIMINARY_STAGE`: it is **not** adequate for the 55 × 300 = 16 500 positive units the
per-type floor implies before registers, PPV, negatives and cluster de-duplication. Dispute rate
5–15% remains an **assumption**, not a measurement; dollars and human hours are `NOT_MEASURED` and
not invented. `2 × units` is two labeler passes and is not automatically a human action count.

## 8. Immutability and access

sha256 of every frozen artifact at freeze; append-only JSONL access log per read of a blind
artifact; labels / blind text / detector outputs in separate directories with separate owners. No
in-place edit of a blind split or its labels after any read.
