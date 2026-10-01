# S1 revision-2 — decision coverage (replaces revision-1 `OWNER-QUESTIONS.md`)

revision-1 collected three owner forks (`O-CORE-S1-1/2/3`). Independent review
([REVIEW.md](../review-critical/REVIEW.md) §5) showed each is already bounded by
an approved decision. GOAL-BRIEF §9 and SPRINT-PLAN §7 say that when no new fork
exists the reviewer records `covered_by_decision_ids` rather than manufacturing a
new owner answer. This file does exactly that. **No owner question is opened by
revision-2.**

A decision ID here names a *constraint on the solution*, not an approval of the
patch: the concrete algorithm still needs technical evidence, RED→GREEN,
mutation and an independent review. An open technical choice is not a policy
choice.

## O-CORE-S1-1 — a tool result carries a value equal to an issued substitute

- **Executed evidence:** `A2`, 3/3 isolated variants (revision-2, each with a
  fresh vault): surname in the clear + reverse leg returns the first person;
  the two row variants also overwrite the given name.
- **covered_by_decision_ids:**
  - `REMAINING-DECISIONS §Блок 2 — Происхождение`: first restore and use the
    **available** transformation history and occurrence source; **new provenance
    API fields are NOT authorized**; a simple coincidence of a new real value with
    an old fake does not prove echo.
  - `OWNER-DECISIONS §Опрос 2 — Forward collision`: a new real value is not
    automatically an old substitute; distinguish by proven source/context/
    identity, **never by message role alone**; if indistinguishable, **explicitly
    refuse the affected operation**, never a silent pick and never a silent
    passthrough; continuity of already-issued substitutes is mandatory.
  - `SPRINT-PLAN §7` (`G2`/`G10`): exclusions and uncertainty preserved, no
    silent success.
- **Consequence:** status quo (option 4 in revision-1) is **not** a valid answer;
  a blind re-mask that breaks legitimate echoes is **not** approved. The engineer
  must first attempt disambiguation from existing inputs and use refusal as the
  fallback — that is a technical problem, not a fork.
- **What would reopen a question:** a demonstrated input-equivalence proof that
  **no** available input can distinguish an external new-real value from an echo
  (that information audit is required before any new API proposal). Revision-2
  does **not** claim indistinguishability.

## O-CORE-S1-2 — lone surname / given-name fragment of a known person

- **Executed evidence:** `C` (nonempty, exact identity: full name and lone
  surname get different substitutes for one real person) with `C2` holding.
- **covered_by_decision_ids:**
  - `OWNER-DECISIONS §Опрос 2 — части имени`: all identifying parts are protected;
    **one person receives a consistent substitute for whole and parts**; carry may
    keep an already-issued substitute but may never let a real name out for the
    first time.
  - wiki `INVARIANTS.md` `#conversation-scope` / shared-name ambiguity: the
    conversation scope exists so a single-candidate rule means something, and
    two people who share a surname must not collapse into one.
- **Consequence:** "always link" vs "keep split identity" is not a free policy
  choice; the binding rules constrain the answer. A shared-surname
  counterexample inside one dialogue would be a genuine new fork — none was
  executed here, and the two-people-one-surname positive control is still
  required before `C` counts as class coverage.

## O-CORE-S1-3 — the model invents a country prefix on a substitute phone

- **Executed evidence:** `D1` (synthetic `+3 <fake>` → `+3 <real>`, residual
  empty). **Separate** from archived P4 (`+7 <fake>` → `+3 <same digits>`), which
  is not executed here.
- **covered_by_decision_ids:**
  - `REMAINING-DECISIONS §Блок 2 — Явная форма агента против схемы`: preserve the
    explicitly written agent form; do not silently repair an explicit format; a
    tool's format refusal is not a faithful-gateway miss.
  - `REMAINING-DECISIONS §Блок 2 — Непереносимая опечатка` (general refusal rule):
    when a safe substitute cannot be produced, refuse explicitly.
  - wiki `INVARIANTS.md` phone-notation rules (#swap): the approved notations
    (`8 …`, `+7 …`, ten bare digits) keep their form; a changed numeric identity
    must not be silently delivered.
- **Consequence:** "keep status quo" is not a valid answer; the question is the
  technical one of separating legitimate notation from a changed country
  identity. Only an explicitly proposed **new equivalence/exception** (extending
  the approved notation set) would need an owner choice.

## Rules observed

- No new API/storage/provenance field is proposed or assumed.
- No product/scorer patch is made by revision-2.
- The three forks stay visible in `GATE.json` as `covered_by_decision_ids`, not as
  `OWNER_PENDING`, and **not** as approved designs.
