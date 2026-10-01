# V0 — v5/v6 semantic compatibility (DESIGN/RED, read-only)

**Task** `V0` of the approved Pseudex quality sprint, first design/RED wave.
**Scope of work** `research/quality-sprint-2026-09-30/work/V0/` only.
**Nothing here is a quality PASS, an integration approval, a release GO or a claim that the
RF/ПД registry is complete.**

## 1. What was compared, and from where

| side | ref | role |
|---|---|---|
| current v5 | `0bfda2363ef1a1d552e2ac093129b1026a86ad68` | the live audit branch; **product source** |
| evidence commit | `890c50849a326f882eac336ba4e38c91171de473` | research-only; `prototype/` diff vs the v5 ref is **0 files** (re-verified, `CHK` C3) |
| v6 | `fad9c7466ea1221282214e6c747ca373ee7e6a55` | the local `origin/bench/agentpii6` head |
| common base | `3be526a2bfb8a9b9e86a9b14b3e11758f723f3a8` | merge base used by `branch-comparison.json` |

The v6 snapshot files under `research/hop-format-audit/next-sprint-review/v6-snapshot/` were
verified **byte-identical** to the `fad9c746` blobs (blob + SHA256 in [INPUTS.json](INPUTS.json));
the read-only `git` refs were used for every diff. **No merge, checkout, worktree, stash, reset or
source patch was performed.** No engine, bundle, vault, provider or benchmark call was made.

Work was done per the B0 gate, which read `work/B0/GATE.json` and `work/B0/REVIEW.md` as
**local/design G1 PASS**; `production_digest` stays **NOT_VERIFIED** and RG stays blocked on it.
`EXECUTION.json` and the usage journal were not touched (Lead owns them).

## 2. Method

1. Recompute the overlap set from the refs (`v5 Δbase ∩ v6 Δbase`); it is **24 paths**, identical
   to the declared list — `overlap_count_declared = 24`, `reproduced_exactly = true`.
2. Extract, per path, the changed module-level symbols on each side by AST/diff, and write the
   semantic row (current must preserve / v6 addition / risk / test acceptance) in
   [COMPATIBILITY24.json](COMPATIBILITY24.json).
3. Freeze both sides into `evidence/frozen/` and run **9 pure executable checks**
   ([checks/v0_checks.py](checks/v0_checks.py)) that read only frozen data. 7 of them are
   **declared RED** — reproduced conflicts, printed as `CHECK <id> RED expected=RED` in
   [REDorchecks.log](REDorchecks.log) — and 2 are GREEN count reproductions. The script exits **0**
   because every check landed on its declared expectation; a RED that turned GREEN would exit 1.
4. Enumerate the 55 v6 types and the 9 grammar-uncertain ones from the registry record itself
   ([TYPE55.json](TYPE55.json)).

## 3. Counts (reproduced, not asserted)

| quantity | value | source |
|---|---|---|
| v5-changed paths vs base | **418** | `git diff --name-only` |
| v6-changed paths vs base | **77** | `branch-comparison.json` `v6_changed` |
| overlap paths | **24** (recomputed == declared) | CHK `overlap-24` |
| v6 new item types | **55** (`ORIGIN_V6`) | CHK `type-55`, `TYPE55.json` |
| grammar-uncertain (`ГРАММАТИКА?`) | **9** | CHK `type-55` |
| v5 item types | **11** (`CARD DATE DOB EMAIL INN LOC NAME PASSPORT PHONE PLATE SNILS`) | registry |
| checksum-carrying v6 types | **11**, all 11 registry `sample`s checksum-VALID | `probe_checksum_samples.py` |
| v6 modules the v6 branch adds that the v5 branch lacks | **51 files** (incl. `pii_types*`, `checksum_v6`, `scenarios6/`, `v6/corpus.json`) | `git ls-tree` set difference |

The declared counts are **not** massaged: 24 and 55/9 reproduce exactly. Where a v6 claim is weaker
than it sounds it is stated below rather than rounded up.

## 4. The reproduced conflicts (declared RED)

### 4.1 The registry rolls back the v5 `script` / `translit` split — `CHK v5-tables-reproduced`, `CHK script-translit`

The v5 branch split one NAME form feature into two: `script` = **alphabet**
(`cyrillic|latin|mixed|none`) and `translit` = **romanization**
(`latin:gost|latin:icao|latin:bgn|latin:unknown`, abstaining at `latin:unknown`). The v6
`pii_types.py` NAME record transcribes the **pre-split** table
(`("NAME","script"): ("cyrillic","latin:gost","latin:icao","latin:bgn","latin:unknown","mixed","none")`,
no `translit` row, no `("NAME","translit")` abstention), and the v6 `contracts.py` **derives**
`FORM_FEATURES`/`FEATURE_LABELS`/`FORM_ABSTAIN` from that registry instead of holding the literals.
Adopting the v6 direction of the edge therefore silently deletes the v5 decision, and the G8
condition «скопирована старая script/translit таблица» stops being hypothetical.

`FORM_FEATURES`, `FEATURE_LABELS` and `FORM_ABSTAIN` are the three diverging tables; the other six
(`IDENTIFYING_ROLES`, `NEEDLE_KINDS` prefix, `DIGIT_PIECE_TYPES`, `DATE_PIECE_TYPES`,
`DERIVED_PIECE_TYPES`, `SQUEEZED_TYPES`) still reproduce.

### 4.2 The instrument that was meant to catch it cannot — `CHK v6-test-literal-copy`

`test_pii_types.test_v5_tables_reproduced` compares the registry against **hand-copied** literals
(`_LITERAL_*`) that are the *base* tree's tables, not the live v5 tables. It is green on the stale
copy while `contracts` diverges. So G8's "old script/translit not rolled back" has, today, **no
instrument**: the v6 test proves the registry equals the base, not that it equals current v5.

### 4.3 The status funnel was rebuilt on the v5 side and is absent on the v6 side — `CHK status-funnel`

v5 replaced the single `unmasked` status with `engine_kept` / `not_masked` / `leaf_foreign`
(`OUT_HOP_WRITTEN_STATUSES`; plus `out_written`, `out_no_mint`, `end_to_end_written`,
`chain_*_written`, `multi_all_out_written`). v6's `HOP_STATUSES` is still
`("observed","leaked","residual","unmasked","absent")` and its `form_hOUT` denominator is
«observed ∪ unmasked». Neither side contains the other: v6 has `unmasked`, v5 has the three split
statuses. A merge must pick a reader and an observer, and no owner decision names one (O-V6-2).

### 4.4 Checksum policy: three contracts, one line — `CHK checksum-policy`

| contract | says |
|---|---|
| v6 §6.3 / R6-39 / OD-78, `perfect.mint_v6`, `metrics.fake_checksum_invalid`, `V6_FIXTURES` | the correct gateway **re-mints until the substitute FAILS** the published checksum; boundary **1.0** |
| owner **Q2** «Наследовать валидность исходника» | a **valid source → a valid substitute** |
| product invariant `INVARIANTS.md#structured-ids` (CLAUDE.md) | a fake СНИЛС/ИНН/card is **deliberately checksum-VALID** (from impossible ranges) so a checksum-checking agent still calls the tool |

Executed on the snapshot: all **11** `generated_checksum` types have a checksum-VALID `sample`.
Under owner Q2 the correct arm scores `fake_checksum_invalid` **0/11** (boundary 1.0 unmet), and the
**M8 mutant** («чеканит подмены, ПРОХОДЯЩИЕ свою КС», `integrate_v6.py`) also scores **0/11** — the
two are **indistinguishable on the line built to separate them**. The v6 fixtures state the same
thing in fixture form: `7707536455681514` is Luhn-**valid** and is the `"zero"` (0/1 = miss)
fixture; `7707536455681515` is Luhn-invalid and is the `"one"` fixture. This is a scoring-semantics
fork, **not** a product patch: V0 proposes nothing and changes nothing (O-V6-1).

### 4.5 v5's authorial-leaf and value-reading tables are not carried — `CHK v5-leaf-and-readings`, `CHK v5-corpus-rules`

`LEAF_EQUIVALENCE` / `LEAF_SEMANTICS` / `LEAF_CANONICAL` / `semantic_leaf` / `equivalence_problems`
(two tool schemas, one semantic leaf) and `VALUE_READINGS` / `VALUE_NORMALISERS` (the ONE reading of
"same value", replacing three drifted copies) exist only on the v5 side; none is present in the v6
snapshot. `V5_CASE_RULES` R22 (one semantic leaf per transition) and R23 (no required OUT hop on a
superseded item) are v5-only (23 v5 rules vs 21 v6 rules). The corpus/`scenarios5` builders depend
on both.

### 4.6 Documentation: decision ids collide — `wiki/STATE.md`

D-068, D-069 and D-070 are used by **both** branches with different dates and different decisions
(v5: «Лимит по ОБЪЁМУ», «v5 model connectors», «Current-hop PHONE form»; v6: «v6 implements pilot
types…», «Pilot tools require an evidence-backed schema», «v6 is built as the full corpus…»). A
merge either duplicates an id or silently keeps one meaning, and `wiki/check.py` does not validate id
uniqueness, so **no instrument catches it** (O-V6-3).

## 5. Owner overrides — compatibility, stated honestly

| owner override | state against the v6 snapshot |
|---|---|
| **source validity inheritance** (Q2) | **CONFLICT** — §4.4, executed |
| **explicit agent format priority** (Block 2) | **PARTIAL/UNKNOWN** — nothing in the v6 snapshot overrides it, but no v6 instrument states it either; the priority lives in the observer/judge and must be carried, not re-derived |
| **typed personal invalid protection** (Q3) | **GAP** — no type in the v6 registry is `bare_typed` (0/66), so every `[K]` type still needs a cue or a field key; the "proven typed context" admission Q3 chose has no declared path (O-V6-5) |
| **all NAME parts** | **COMPATIBLE at registry level** — the NAME record's `identifying_roles` is `("surname","given","patronymic")`; the defect is the feature split of §4.1, not the roles |
| **raw conditional metric** (M04 raw-first) | **GAP** — `fake_checksum_invalid` reads the mint record (`run.base.substitutes`), not the delivered raw stream; M04 is M1a's scope, so this is recorded, not resolved here |

## 6. Claim boundary

- The 55 types are **registry records**, not engine support. Nothing here claims any v6 type is
  detected, substituted or restored by the product; native support is proven per type after V1/N1.
- The 9 `ГРАММАТИКА?` types are **grammar-uncertain**; they are enumerated, not resolved.
- Red on a check means **a conflict was reproduced on frozen snapshot data**, with the exact source
  pointers in `INPUTS.json`/`REDorchecks.log`. It is not a product defect claim, not a suite failure
  and not a request for a patch.
- `production_digest` remains **NOT_VERIFIED**; RG is still blocked on that separate proof.
- No engine, licensing, scorer, benchmark, corpus, wiki or git state was modified.

## 7. Open questions (O-V6)

See [OWNER-QUESTIONS.md](OWNER-QUESTIONS.md). The forks are O-V6-1 (checksum policy on the
benchmark's `fake_checksum_invalid` line), O-V6-2 (status funnel), O-V6-3 (D-id collision), O-V6-4
(the `pii_types` vs `contracts` home and the `translit` predicate), O-V6-5 (typed-invalid admission).
Until the owner answers, V1 (integration) stays blocked on its checksum/funnel clauses; independent
read-only work continues.
