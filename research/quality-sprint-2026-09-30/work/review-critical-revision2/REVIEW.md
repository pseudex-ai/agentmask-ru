# Independent re-review of first-wave corrections — M1b/S1 revision-2

## Verdict

| Package | Verdict | Consequence |
|---|---|---|
| **M1b revision-2** | **PASS_CORRECTIONS** | The three R-findings (full-state claim, replay isolation/verdict, legacy reader) are actually fixed, not relabelled. `G2` stays `NOT_MEASURED`/`FAIL`; no promotion. |
| **S1 revision-2** | **PASS_CORRECTIONS** | R1–R4 are actually fixed; the accepted synthetic REDs (A2/B/C/D1) reproduce on the pinned unchanged engine. Full `G3` stays blocked; no promotion. |

Requested reviewer target `gpt-6-astra` (inherited); self-identity is not routing proof. No provider/payment/production calls, no installs, no Git mutation, no writes to author directories. Only this report was written. The stale `debug-leak` stash recipe was not used.

## 1. Review performed

- Read [REVIEW.md](../review-critical/REVIEW.md) + [EVIDENCE.json](../review-critical/EVIDENCE.json) (the REVISE findings), both revision-2 packages (SPEC/DELTA/GATE/INPUTS/probe source/logs), and binding GOAL-BRIEF/OWNER-DECISIONS/REMAINING-DECISIONS.
- Read the archived raw run directly (arms.v5.jsonl) to re-derive the cited operands, not trusting either side's indices.
- Independently reran the S1 revision-2 probe in-memory (exit **4**, violated set `{A2,B,C,D1}`) and the M1b parity verdict self-test pure function (7/7 controls, unrelated `HarnessError` → `UNRELATED_HARNESS_ERROR`).
- Did **not** rerun `probe_canary_reader_v2.py` into its output directory (it rewrites its own synthetic-control `tmp/`); verified its saved JSON instead.
- Confirmed `git diff 0bfda236 -- prototype/pseudex prototype/licensing` is empty and no product/scorer/raw-run file is modified.

## 2. M1b revision-2 — each finding actually fixed

| Finding | Fix | Independently verified |
|---|---|---|
| full prior state claimed (`len(payloads)==len(have)+1`) | WITHDRAWN → `replayed_payload_count_matches_remaining`, a COUNT; `state_equivalence_claimed:false`, `trigger:UNKNOWN` | probe source L328, L425-426; SPEC §0, §3 |
| cross-case monkeypatch chain | `ORIGINAL_UNIQUE_TOKEN` captured once at import, restored in `finally` per case; exit asserts it back | probe source L71, L382, L394-396, L432 |
| any `HarnessError` = `REPRODUCED` | `REPRODUCED_EXACT_BOUNDARY` requires divergence signature + both saved 60-char prefixes verbatim + recomputed first-diff ≥ 60 | `classify_attempt` L199-225; self-test 7/7 `all_ok` (independently rerun); unrelated error → `UNRELATED_HARNESS_ERROR` |
| `len(str)` mislabelled `*_bytes` | `chars` and `utf8_bytes` reported separately | saved JSON: max payload 36592 B vs 35718 chars (distinct) |
| denominator "no-captures branch doesn't consult journal" | corrected: journal IS consulted; defect is the earlier `read_captures` early-return discarding the 810/810 denominator | SPEC §1; engine `NOT_MEASURED capture_rows=0 coverage_known=False` preserved |
| v2 declared-size as the legacy fix | a bounded **LEGACY v1** path (payload-level bounds, skip-never-abort, named/counted) is specified and measured | saved JSON: legacy diagnostic 810 measured / 0 skipped / 0 refused / 20,201 payloads; big-payload row skipped-by-name; hostile row skipped; lying v2 row `REFUSED` |
| "two of four prior states" / minted-push cause | WITHDRAWN; **0/4 reproduced**, trigger UNKNOWN, no cause inference | SPEC §3; GATE `parity_reproduced_exact_boundary:0/4` |

The legacy reader remains a **design + diagnostic**, explicitly `DIAGNOSTIC ONLY`, and the global verdict stays `NOT_MEASURED`. This is honest: no partial=full-PASS.

## 3. S1 revision-2 — each finding actually fixed

| Finding | Fix | Independently verified |
|---|---|---|
| "original raw unavailable" | `ARCHIVED_RAW` pointers; raw IS present | Re-read arms.v5.jsonl: `long_clinic-001` L49 raw `+7 929 542-23-19` and restored `+3 929 542-23-19` at requests 7/8/13; `fanout_pick-017` L607 raw `23.10.1965`/`c-3`/`c-8` and restored `127.10.1965` at request 14; `long_clinic-006` L60 `reply_raw`(fake `08.04.1964`)/`reply_whole`(real `04.04.1964`)/`stream_mismatch:true` |
| streaming needs HTTP/SSE inputs | in-process `STREAM_CHUNK=17` + one `StreamDetokenizer` + `flush`; SSE/leg are not inputs | probe E1 L516-557, `historical_path_is_in_process:true` |
| E2 = engine RED | `CONTRACT_EXPECTED`; separate proxy-abrupt-EOF concern not asserted as the cause | probe E2 L560-593, `counts_as_engine_red:false` |
| D1 explains archived P4 | synthetic input-side `+3 <fake>` kept separate; `d1_explains_archived_p4:false` | probe D1 L434-486 |
| D2 / historical E1 | both stay `NOT_MEASURED` for reproduction | probe D2 L489-510, E1 L554; GATE `not_measured_for_reproduction` |
| A2 reused one vault; C vacuous; B "never born"; A1 one-sided | A2 fresh vault per variant + separate harms; C `INVALID_FIXTURE` on empty/partial identity; B instruments recognizer→suppress→resolve; A1 true second-person round trip | probe A2 L208-260, C L377-427, B L279-371, A1 L164-205 |
| three forks re-asked | mapped `covered_by_decision_ids` (0 owner questions) | SPEC §4; GATE `decision_coverage` |

Independently rerun probe: exit **4**, `violated_probes=[A2,B,C,D1]`, holds `{P,A1,A3,C2,E1}`, `D2=NOT_MEASURED`, `E2=CONTRACT_EXPECTED`, `fixture_spec_sha256=6178608f…` — matches GATE exactly.

## 4. Gate-position honesty

- **M1b**: `G2` status `NOT_MEASURED`; full-state withdrawn; trigger UNKNOWN; reader is design+diagnostic, not accepted. No over-claim.
- **S1**: `G3` status `REVISED_NOT_PASS`, `full_g3_pass:false`. The four reproduced REDs are valid on the pinned unchanged engine; the disputed choices are *mapped*, not *approved*; D2 and the historical E1 episode remain unreproduced. No over-claim.

Both packages explicitly block product/scorer patches, merge/release and paid GO. No product source was written (revision-2 scopes only).

## 5. Two minor documentation-precision notes (not blockers)

1. **Pointer index convention.** `ARCHIVED_RAW` uses request ordinals (`responses[7,13]`, `response 14`) while the review-critical used 0-based list indices (`6/7/12`, `13`). They name the same responses (request 7/8/13 and request 14 = list index 6/7/12 and 13). The substance is verified; the notation is ambiguous and should say "request ordinal" to avoid a future off-by-one misread.
2. **`long_clinic-006` field name.** The field list names `reply`, but the top-level v5 keys are `reply_raw`/`reply_whole`/`stream_mismatch` (the delivered per-response text lives in `model_trace.responses`, not a top-level `reply`). The raw/whole/mismatch facts are correct; only the field label is loose.

Neither changes a verdict nor reopens a finding. They should be corrected in the next touch of these SPECs.

## 6. Bottom line

Both revision-2 packages genuinely fix the REVISE findings rather than relabel them. The useful canary RED and the four synthetic failure properties stand; the over-claims (full state, minted-push cause, missing raw, transport explanation) are withdrawn or corrected. Full G2/G3 remain blocked by the honest unresolved items, and the engine has not become better merely because these measurements were produced.
