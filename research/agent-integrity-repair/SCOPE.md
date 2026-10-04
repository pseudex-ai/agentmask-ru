# Agent-hop integrity repair — open scope and acceptance

Owner authorized fixing the entire confirmed problem family and new confirmed findings from completing the stopped run. The latest mandate explicitly requires and authorizes a NEW LIVE LLM comparison on the SAME recorded cases after repairs (deepseek-flash, C/C′/I, comparable settings). Offline checks are PRECONDITIONS, not final validation. No deployment, release, main-branch changes, mutation of old run, or mixed-version resume is authorized.

## Isolation / evidence

Repair branch: `fix/agent-hop-integrity`, separate worktree `/Users/igor/Projects/Obscura-agent-integrity`, basea810bf85fbb7f6fe5e12c73323ff42a0d8cc38bf.
Original integration checkout and stopped run remain read-only. Existing dirty research/marketing/wiki work in other checkouts is preserved.

Initial17-script baseline exits all0: [results](<baseline/RESULTS.json>). This does not constitute acceptance: new cross-hop checks fail7classes on the same baseline: [red log](<RED.log>). Test/check schemas must never be weakened to erase these failures.

## Rules to preserve together

1. Detection always runs, fail closed on errors; no raw-PII fallback or prompt exemptions.
2. Entity identity, role projection and presentation are separate. Shared fragments cannot choose a different owner or add omitted fields.
3. A short low-entropy component is meaningful only under its role, not a global string rewrite. Unrelated IDs, counts, list indices, phone country code and dates remain untouched.
4. Compatible alias forms in one conversation share the corresponding core and parts. Different cities/owners/types/apartments remain distinct and reversible.
5. Historical own substitutes have a stable representation without weakening detection of genuinely new PII.
6. Plain operational dates are not DOB merely because another JSON field contains a person. Genuine birth cues remain detected.
7. Restoration selects an unambiguous owner with evidence; never last-row-wins for incompatible meanings.
8. All executed/attempted operations and partial failures remain in evidence and denominators; provider envelopes are labelled by what actually crosses that boundary.
9. Correct final state does not erase corrupted durable notes/SMS or unrequested destructive retries.
10. Arbitrary computation on fictitious values is NOT automatically reversible; supported semantic operations need an explicit, verified contract, not a false universal promise.

## Work ledger

| class | state | required proof |
|---|---|---|
| Numeric LOC literals corrupt IDs/counts/phones | first implementation + new positives/negatives green;17-suite regression green | positive role restoration + unrelated scalar negatives + complete phone priority |
| Broad address-family prefix aliases city to full address | exact type-slot lookup implemented;new and17-suite regression green;legacy incompatible-row defense still pending | exact generic-slot change only; city/full owner doesn't collapse |
| Compositional missing-city projection/W8 | scope-local core projection implemented with full-head part namespace;12new checks and17-suite regression green;broader replay pending | scope-safe owner reuse; same flat same fake, changed flat distinct; multi-city ambiguity refused |
| Inconsistent address parsing/composed collision | confirmed isolated repro, pending | same-type notation variants accepted; genuine foreign collisions still refused |
| Operational dates typedDOB | structural JSON value/path context implemented;birth-key arrays/notes and schedule negatives green;prose semantics and broad replay pending | structured field boundaries, positive birth cues, ordinary schedule with nearby names/phones |
| Weight/quantity swallowed in address | leased full-unit vocabulary corrected;kg/gram/milligram/liter controls green;full corpus measurement pending | unit semantics + fuzzy candidate boundaries; positive spoken-address controls |
| Markdown captures own-name markup | field label/value delimiter separated;issued-token and real-name controls green;broader markup variants pending | markup boundary preserves source offsets and own-name identity; new real names still detected |
| NAME roles/initials/transliteration/declension | candidate-type provenance, coherent derived-full-name priority, full Latin windows and ordinary-word initials collisions repaired;20cross-hop/17legacy green;mint/other morphology cases still pending | role-correct derivation, no ordinary-word collisions, ambiguous owner refusal |
| CARD/PHONE spoken/partial fake remnants | masked-card head/tail restored; last-4-only remains ambiguous (fail-closed residual); spoken Luhn-invalid case proven model transcription, mint Luhn-valid | checksum-valid mint+notation, no fake fragments in executed data, no invented originals |
| Streaming vs whole restoration divergence | measured (stream_mismatch) and reproduced; correct fix requires non-window-dependent chunk restoration — not yet implemented, documented as open | all split positions, all turns, identical final content without unsafe incremental release |
| Derived DOB age / prefix-driven decisions | semantic contract pending | trusted reference/derived values; no unapproved masking weakening or heuristic patch to output age |
| Partial failure trace/state reset | ConnectedArms (deepseek path) now preserves calls/state/results/mentions/chronology via `_partial_run_v5`; pinned in test_harness_stream | incremental state retained on every error; unknown not empty |
| Provider history/capture mismatch | confirmed no-network witness, pending | actual transmitted payloads separately recorded; both integration modes tested |
| Missing negative labels/ambiguous scorer leaves | instrument design pending | all-unit accounting, mention/component granularity, bounded unknowns, no relaxed comparator |
| Newly confirmed cases | Flash follow-up in progress | add general-class regression before implementation; not case-ID allowlists |

## Concurrent audit

164cases lacked full coverage after first40-agent workflow. Continuation manifest in separate research checkout: FLASH-FINISH-BATCHES.json,82batches of2cases. Workflows45/46/47 (40+40+2 Flash readers) are complete and collected. Ledger now records419/419 primary AND capture components covered, zero parse errors. This certifies recorded reading coverage, NOT agreement/quality of all reviewer verdicts; lead reconciliation remains. Audit readers wrote only their own reviews, never repair source. Generated verdict totals are aggregation only.

## Acceptance, not just green tests

- Every confirmed class has red-before/green-after positive AND negative tests, including combined transformations and repeated hops.
- Old17-suite baseline and expanded identity/detection/restoration/streaming suites do not regress.
- Generated corpora regenerated consistently; detection/negative volume and external corpora measured with before/after witnesses. Missing corpus is a named gap, not pass.
- Frozen419-case traces are replayed offline through repaired code without overwriting source or claiming counterfactual model behavior. The owner-authorized fresh LIVE run on the same cases is REQUIRED to prove changed agent decisions; final acceptance must include paired before/after business outcomes, not only offline metrics.
- Case-reading completion and disputed verdicts reconciled; no unknown labelled success.
- Actual client version/image/bundle/integration shape checked before any production exposure statement or deployment.

No claim of 'never any future defect' or unconditional production-readiness is an acceptance criterion that software tests can establish.
