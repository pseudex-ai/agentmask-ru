# D0 — corrected metric table on the SAVED outputs (no re-run, no overwrite)

The pinned raw artifacts are untouched and stay citable:

- [d0_arm_compare.py](<research/quality-sprint-2026-09-30/work/D0/d0_arm_compare.py>)
- [out/arm-results.json](<research/quality-sprint-2026-09-30/work/D0/out/arm-results.json>)
- [out/arm-summary.tsv](<research/quality-sprint-2026-09-30/work/D0/out/arm-summary.tsv>)
- [smoke.log](<research/quality-sprint-2026-09-30/work/D0/smoke.log>)

This document is a **correction table plus the required corrections to the script's read path**.
Nothing here re-ran a detector; no file under `work/D0/` was modified.

## 1. Population relabelling of the same rows (no re-run needed)

| current bucket in the harness | what it actually contains | corrected bucket | may enter FP/PPV? |
|---|---|---|---|
| `fp_public` (25 rows) | predictions on old-policy "must-not" public names | `OLD_POLICY_DISAGREEMENT` — public names are now positive | **no** until re-adjudicated; then it splits into `FP_on_adjudicated_negative` / `TP_public_name` |
| `fp_other` (104 rows) | (i) overlap with a labelled `other` occurrence **and** (ii) overlap with **no** labelled occurrence | (i) `FP_on_adjudicated_negative`; (ii) `unlabelled_prediction` | only (i), and only after independent adjudication |
| `fp_place` (7 rows) | overlap with a `place` occurrence | `FP_on_adjudicated_negative` | after adjudication (bare toponyms are not automatically PII addresses) |
| `12 DATE→DOB` | a type disagreement on **old** gold | `SOURCE_TYPE_DISAGREEMENT_UNREVIEWED` | no |
| `69/292 neg masked` | masks on the hand-labelled negative population | `FALSE_MASK_ON_LABELLED_NEGATIVE` | diagnostic; not precision |

**Script correction (new file only).** `GATE_MUST_NOT` must drop `public` and become
`GATE_MUST_NOT = {adjudicated negatives}`; the evaluator must emit two counters
(`fp_on_adjudicated_negative`, `unlabelled_prediction`) instead of `fp_other`; the old line must be
kept as a separately labelled historical run, not deleted. Any such change is written as a **new**
file under `work/contracts-revision-2/` and never overwrites `work/D0/out/`.

## 2. Two `whole` definitions that must stay apart

| definition | statement | consequence |
|---|---|---|
| `whole_single_span` (harness today) | one same-type predicted span contains the entire gold item | strict; a correct value split across two spans counts as not-whole |
| `char_union_coverage` (harness today) | union of predicted characters over the gold item | optimistic; a correct union can hide a partial leak |

Both are printed, each with its own column name. They are never averaged into one column and never
called "coverage" without the qualifier. The A1 acceptance protocol uses **occurrence-level
`whole_closed`** (CORRECTIONS §1/A1-1); a D0 comparison against a char-union number is a different
measurement and must say so.

## 3. Arm descriptions, corrected

| arm | what it actually is | what it is NOT |
|---|---|---|
| `FULL` | product detector as shipped in-process | not the container image behaviour |
| `RULES_ONLY` | `FULL` subclass with **only `_ner_spans` disabled** | not "all models/dictionaries off"; not a product configuration |
| `HYBRID_UNION` | `FULL` plus raw-NER spans that do not overlap existing spans | not the literal union; not a mechanism |
| `RAW_NER` | bare Natasha NER | not a replacement candidate |
| `RAW_NER_REGEX` | bare NER plus the regex layer | not a replacement candidate |

No arm is an architecture candidate; a difference on this gold is not a causal explanation and does
not transfer to production traffic.

## 4. Timing / resource rows

`12.35` and `7.58` ms/text are **two single runs on a shared host** and are explicitly **not**
p50/p95, **not** RSS, **not** an admission budget. Every candidate's latency/RSS/image-size cell
stays `NOT_MEASURED` until the controlled runbook
([RUNBOOK-PERF.md](<research/quality-sprint-2026-09-30/work/D0/RUNBOOK-PERF.md>)) is executed. No
resource trade-off may be put to the owner from these two numbers.

## 5. Required before O-DETECT

1. Corrected populations and labels as a new instrument version (above), with real adjudication of
   the public/unlabelled rows.
2. The accepted O-DATA protocol ([O-DATA-PROPOSAL.md](<research/quality-sprint-2026-09-30/work/contracts-revision-2/O-DATA-PROPOSAL.md>)).
3. Real candidate mechanisms compared on identical gold — not raw NER alone.
4. A controlled p50/p95/RSS measurement.

Only then may the owner be asked to choose between measured options.
