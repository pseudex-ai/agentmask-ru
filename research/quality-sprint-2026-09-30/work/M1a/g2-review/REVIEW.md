# M1a v2-dev — G2 readiness review

**Verdict: NOT_READY.** One hard measurement blocker (LOC false-negative from a
non-unique char-level alignment), not a publishable known-unknown. Inputs frozen
as instructed; I wrote only `work/M1a/g2-review/{REVIEW.md,probes.json}`.

## 0. Frozen inputs confirmed

- `answer_restoration.py` sha256 `48ecc8f772aaa60d7bdd8394f793533ed8bf97e361582fe0b5f92a1c9f33d5b4`
- `test_answer_restoration.py` sha256 `ed5adbfb4c94d48f25e7f2d6b854fd2ef18d811f4fb8f69952264b540f4c1f78`
- 58/58 controls exit 0; 6 legacy suites (test_metrics/fixtures/form/observe/hop_report/live) exit 0.
- Only the two M1a files differ from B0 pins (196 other pins incl 17 raw-run unchanged).
- `git diff 0bfda236 -- prototype/pseudex prototype/licensing prototype/bench/agentpii5/{metrics,observe,contracts}.py` empty ⇒ old `answer_real`/`observe`/`contracts`/engine untouched. Both M1a files are new (759 insertions).

## 1. The hard blocker — LOC false-negative (point 6 / acceptance sentence)

Adversarial probe: item `LOC` real `«улица Пушкина, дом 14»`, fake
`«улица Липовая, дом 21»`, raw writes the fake, delivered writes the real
verbatim. Correct restoration must be `matched`; the metric returns
**`value_wrong`** (`probes.json` → `loc-positive-correct`).

Root cause (verified on opcodes): char-level `SequenceMatcher` fragments the
shared-prefix value — `«улица »` equal, `Липовая→Пушкина` replace, then `21→14`
becomes `delete 2 + equal 1 + insert 4`. The final `4` lands as an **insert at
`x==b`** and the round-3 boundary rule `a < x < b` drops it, so the mapped window
is `delivered[0:20] = «улица Пушкина, дом 1»`, which fails the value equality.
`_equal('LOC', delivered, real)` is itself `True` — the value comparator is fine;
the **alignment** truncates the value.

This is exactly the acceptance-sentence trap: *“an all-FALSE LOC comparator must
fail positive address controls.”* There is no positive LOC control in the suite,
and the one I added fails. It is a FALSE NEGATIVE (a correctly restored value
scored wrong), not a conservative UNKNOWN, so it cannot be waved away as
known-unknown publication.

The same char-level non-uniqueness also still mislabels the round-3
`insertion-around-token` case as `value_wrong` (should be `value_ok` + gap-change),
per `ALIGNMENT-NOTE.md`. Both directions fail; the boundary rule is a band-aid that
regressed LOC while not fixing its original target.

## 2. Ten M04-READINESS points

| # | point | verdict | evidence |
|---|---|---|---|
| 1 | provenance clocks | **MET** | push vs provider separated; legacy/mentions→unknown; future proof→unknown; tests L55-75 |
| 2 | substitute really written | **MET** | immutable occurrences; mutated digit→0 candidates; unchanged fake→residual; L132-144 |
| 3 | ground-truth literal | **PARTIAL** | exact-copy literal MET (L181-184); changed-form (Latin/translit) OPEN |
| 4 | family completeness | **OPEN** | dotted initials MET; Latin/partial-roles/LOC-components/numeric-notation/spoken/stream-boundaries not proven; unsupported spellings not surfaced |
| 5 | identity from RAW+source | **MET** | swapped-person→value_wrong; identity from item, not delivered; L146-150 |
| 6 | mapping local & unique | **NOT MET (blocker)** | char-level SequenceMatcher; LOC false-negative + boundary-insertion false value_wrong |
| 7 | non-PII simultaneously | **PARTIAL** | c-3→c-8 caught (L168-172); gap-vs-value attribution broken for boundary insertions |
| 8 | actually delivered | **MET** | base.reply; stream defeats whole (L165-167) |
| 9 | history immutable | **MET** | add-only module, versioned, old files unchanged; recompute-new-dir is operational (not yet exercised on a run) |
| 10 | independent review | **THIS** | suite lacks positive LOC control + swapped-person pin (both required) |

## 3. Adversarial false-pass hunt (beyond declared limits)

- `swapped-person` (identity chooser consulting delivered) → `value_wrong` ✓ correct.
- `whole-plus-initials` → 2 candidates / 2 matched ✓ no double-count, no nested-identity confusion.
- `unknown-competitor-not-promoted` — covered by existing L146-150; availability is per-(item,fake), an unrelated alias cannot promote it.
- `latin-spelling` → **0 candidates** (silently dropped from the denominator). Not a false *pass*, but a silent denominator shrink — point 4 violation (unsupported spellings must not disappear).
- `surname-only` → `provenance_unavailable` (conservative) ✓, but there is no mechanism to publish that this class is unsupported.

No false *value/form/joint pass* found beyond the declared limitations. The
failures are false NEGATIVES and silent denominator drops, not false positives —
they understate, never overstate, quality.

## 4. Is a valid G2 declaration possible now?

**No.** The LOC false-negative is a measurement error on a supported type, not an
unsupported-spelling gap. Publishing “known-unknown” covers Latin/partial-roles;
it does not license scoring a correct address restore as wrong. Point 6 (unique
alignment) is therefore a **hard blocker** that must be implemented, not published
away.

## 5. Minimal work list to reach G2

REQUIRED (hard):
1. **Replace char-level `_mapped_window` with a token-anchor monotone alignment**
   that maps by literal anchors/token boundaries, not char diff, and returns
   `alignment_unresolved` for non-unique assignments. Acceptance: positive LOC
   control (`улица Пушкина, дом 14` verbatim restore → `matched`) AND
   `insertion-around-token` → `value_ok` + `text_status=changed`.
2. **Positive LOC control test** (correct street-type restore → matched; wrong
   street type → value_wrong) pinned in the suite.

REQUIRED (must not disappear silently, may be published as unknown):
3. **Known-unknown surfacing**: an explicit report of unsupported written
   spellings (Latin/translit, partial roles) so they are not silently dropped from
   the denominator. Acceptance: `latin-spelling` produces a visible unsupported
   count, not 0 candidates with no note.
4. **Swapped-person pin** (already correct, but must be a pinned test per point 10).

OPTIONAL (do not block G2 if surfaced):
5. Latin/translit value support, partial-role proof, spoken/stream-boundary
   completeness — implement or publish as known-unknown.

## 6. Can M1c wiring begin in parallel?

Plumbing only: M1c can bind the frozen `answer_events(case, run, *, evidence)`
signature, but with no legacy adapter it yields all-UNKNOWN on real runs, and with
the LOC blocker it would corrupt the score. **Recommendation: hold M1c score
publication until (a) the alignment/LOC blocker and (b) the legacy capture adapter
are done; the wiring harness may be drafted but must not emit a number.** The pure
API surface is stable enough to draft against now.

## 7. Non-claims

No engine/scorer/raw/corpus/provider/production/paid calls. I did not edit any
frozen input. This is a design/readiness review, not G2 acceptance.
