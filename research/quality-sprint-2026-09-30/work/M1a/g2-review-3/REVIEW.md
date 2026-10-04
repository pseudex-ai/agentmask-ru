# M1a v2-dev — G2 readiness re-review #3

**Verdict: PASS_G2_READY** (with OPTIONAL items deferred to M1c as known-unknown). Inputs frozen as instructed; I wrote only `work/M1a/g2-review-3/{REVIEW.md,probe_fixes_copy.py,adversarial.py,probes.json}`.

## 0. Frozen inputs confirmed

- `answer_restoration.py` sha256 `b6472f455cd603a6475d9cbc1be53cb8acb915f97317725871a6a78693866e7b`
- `test_answer_restoration.py` sha256 `be574f298f9a30817ad1075bc2656e9e5ee48e82aef39d87f7b965c72e0bcae4`
- 63/63 controls exit 0; 6 legacy suites (metrics/fixtures/form/observe/hop_report/live) exit 0.
- Only three source files differ from B0 pins: the two M1a files + `live.py` (declared owner-requested CPU fix, OUT of scope). `git diff 0bfda236 -- prototype/pseudex prototype/licensing prototype/bench/agentpii5/{metrics,observe,contracts}.py` is **empty** (0 lines).

## 1. Prior two REQUIRED blockers — genuinely closed

| blocker | verdict | evidence |
|---|---|---|
| boundary-insertion/duplication gap-flag | **CLOSED** | `X+79164021187` → text_status=changed, clean=0; `+79164021187 +79164021187` → text_status=changed, clean=0. Root cause (inclusive `a<=x<=b` span attribution) replaced by a literal-gaps fidelity pass that compares raw literal gaps to delivered literal gaps using the narrowed value windows. |
| strong swapped-person pin | **CLOSED + PINNED** | p1 fake restored with p2 declared real `+79261234567` → value_wrong, joint=0. Pinned in the suite (identity from source, not delivered). |

The reviewer probe script `g2-review-2/probe_fixes.py` was copied to my scope and re-run: **7/7 PASS** (loc-positive-verbatim, loc-wrong-street-type, insertion-around-token, latin-unsupported-surfaced, swapped-person-value-wrong, boundary-insertion-gap-flagged, two-identical-real-literals). No frozen file overwritten.

## 2. Regression checks (no over-correction)

| case | result | correct |
|---|---|---|
| clean restore | text_status=preserved, clean=1 | ✓ |
| wrong-real-elsewhere | value_wrong + text preserved | ✓ |
| shared surrounding literals | preserved, clean=1 | ✓ |

## 3. Independent adversarial false-pass hunt (6/6 no false-pass)

- glued leading AND trailing insertion (`X+79164021187Y`) → changed, clean=0 ✓
- duplicated real with changed prefix → changed, clean=0 ✓
- value glued duplicate inner (`+79164021187+79164021187`) → changed, clean=0 ✓
- clean restore → preserved, clean=1 ✓ (no regression)
- wrong-real-elsewhere → value_wrong, preserved ✓
- shared surrounding literals → preserved, clean=1 ✓

No false `value/form/joint/clean` pass found beyond the declared optional limitations. All remaining failures are false-negatives/UNKNOWN (understate, never overstate).

## 4. M04-READINESS ten points (post-fix)

MET: #1 provenance clocks, #2 substitute-written, #5 identity-from-source, #6 unique alignment (LOC positive control + boundary gap-flag now pass), #7 non-PII fidelity (gap-vs-value attribution correct), #8 delivered boundary, #9 history immutable, #10 independent review (three rounds: 76fef59f, 6034ec57, this). PARTIAL/#3: exact-copy literal MET, Latin/translit OPEN. OPEN/#4: family completeness — dotted initials MET; Latin/partial-roles/numeric/spoken/stream not proven but now SURFACED via `unsupported_spellings` (not silently dropped).

## 5. OPTIONAL items (may publish as known-unknown, defer to M1c)

Latin/translit value support · partial-role proof · spoken/stream-boundary completeness · legacy capture adapter (M1c wiring: tool_result disclosures provable, message disclosures stay UNKNOWN until harness carries provider ordinals).

## 6. Non-claims

No engine/scorer/raw/corpus/provider/production/paid calls. No frozen input edited. This is a G2-readiness verdict, not a measurement of detection quality.

**Recommendation:** M1a G2 is met for its instrument purpose. M1c may begin wiring `answer_events(case, run, *, evidence)` and the bounded legacy-v1 canary reader; the wiring harness must not emit a published score until the legacy capture adapter is done (else all-UNKNOWN), per the prior review's guidance.
