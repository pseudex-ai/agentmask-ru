# M1a v2-dev — G2 re-review after parent fixes

**Verdict: NOT_READY.** Three of the four REQUIRED items are closed and I confirm
them independently; the alignment fix resolves the LOC false-negative but leaves a
**false-pass on the fidelity axis** (point 7): a glued boundary insertion and a
duplicated real value are silently absorbed, so the answer is reported
`answer_restore_clean=1` / `text_status=preserved` while the text actually changed.

## 0. Frozen inputs confirmed

- `answer_restoration.py` sha256 `3c7c73367729208449ceb42b99627782b9819dcffee510dc473b01d5159c476e`
- `test_answer_restoration.py` sha256 `ca56536ef56bfadc348d1935ca9d6de926f135d830b803469b1b55cbff5b58d0`
- Suite **60/60 exit 0**; 6 legacy suites (test_metrics/fixtures/form/observe/hop_report/live) exit 0.
- Engine/scorer/licensing diff vs `0bfda236` = **0 lines** (old `answer_real`/`observe`/`contracts` untouched).
- Only the two M1a files differ from B0 pins among authored sources; `live.py`/`runs.json`/`wiki/INDEX.md` are pre-existing unrelated WIP.

## 1. Required item closure (independent probes, not the parent's suite)

| # | REQUIRED item | Verdict | My probe |
|---|---|---|---|
| 1 | token-anchor alignment (LOC + insertion) | **PARTIAL** | `loc-positive-verbatim` → matched ✓; `loc-wrong-street-type` → value_wrong ✓; `insertion-around-token` (whitespace `X ` / ` Y`) → value_ok + text_status=changed ✓. **But glued boundary insertion fails, see §2.** |
| 2 | positive LOC control pinned | **MET** | suite L200-204 (verbatim→matched) + L198-199 (wrong type→value_wrong) |
| 3 | known-unknown surfacing | **MET** | `latin-unsupported-surfaced` → `unsupported_spellings=1`; render prints the count |
| 4 | swapped-person pin | **NOT PINNED** | behavior is correct (`swapped-person-value-wrong` → value_wrong, identity from source); but the strong pin (p2 carries the delivered real) is not in the suite — only the weak `wrong-real-elsewhere` (L141-142) and `unknown-competitor` (L146-150) are. |

## 2. The remaining hard blocker — false-pass on fidelity (point 7)

Two independent counterexamples (in `probes.json`), both produce
`value_ok=1, joint_ok=1, text_status=preserved, unmapped=0`:

- **`boundary-insertion-gap-flagged`**: raw `+79990001122`, delivered
  `X+79164021187` (an `X` glued to the value with no separator). The exact-copy
  narrowing `text.find(literal)` correctly extracts the value, so `value_ok=1`;
  but the `X` insertion at `x==a` is attributed to the span by the inclusive
  `a<=x<=b` in the `text_status` pass, so `text_status=preserved`. The answer is
  reported **clean** while its text was changed.
- **`two-identical-real-literals`**: raw `+79990001122`, delivered
  `+79164021187 +79164021187` (the real twice). `joint_ok=1`, `text_status=
  preserved` — the duplicated real is not flagged as an outside change.

Root cause: the `text_status`/`answer_restore_clean` pass uses inclusive span
attribution `a<=x<=b` for insertions (`x==y`), so an insertion exactly at the span
edge (`x==a` or `x==b`) is treated as inside the value and never counted as a gap
change — inconsistent with the exact-copy narrowing that already treats those
bytes as outside the value. This **overstates** quality (false
`answer_restore_clean`), which the prior review's own rule says is not acceptable
(§4: false NEGATIVES may be waved as known-unknown, false PASSES may not).

Required fix (narrow): in the `text_status` pass, an insertion at `x==a` or `x==b`
must be classified as an outside/gap change (not attributed to the span),
consistent with `_mapped_window`'s round-3 `a<x<b` rule. Acceptance: the two
counterexamples above must yield `text_status=changed` (and `answer_restore_clean=0`).

## 3. Remaining REQUIRED vs OPTIONAL

- REQUIRED: (a) fix the boundary-insertion/duplication gap-flag (§2); (b) pin the
  strong swapped-person test (p2 declares the delivered real; expect value_wrong).
- OPTIONAL (do not block G2 if surfaced): Latin/translit value support,
  partial-role proof, spoken/stream-boundary completeness, legacy capture adapter
  (M1c wiring).

## 4. Non-claims

No engine/scorer/raw/corpus/provider/production/paid calls. I wrote only
`work/M1a/g2-review-2/{REVIEW.md,probes.json,probe_fixes.py}`. This is a
readiness re-review, not G2 acceptance.
