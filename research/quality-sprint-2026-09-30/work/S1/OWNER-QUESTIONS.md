# S1 — owner forks (all `OWNER_PENDING`; no fork may be closed by an agent)

Three executed REDs raise choices that the approved decisions do not settle
mechanically. Each is stated as a concrete fork with the episodes, the binding
decision it touches, the options and their price. Until the owner answers, no
dependent implementation (`K1`) may start. Questions are asked here, not
inferred from silence ([REMAINING-DECISIONS.md](<REMAINING-DECISIONS.md>) §"Полнота решений").

## O-CORE-S1-1 — a tool result carries a value equal to an issued substitute

- **Episode (executed, `A2`):** person A `Битюкова Алла Сергеевна` is masked in
  one conversation; her substitute surname is `<F>`. A `file_read` tool result
  then carries a **different** person whose real surname is exactly `<F>`.
  Result: the surname is left in the clear, the given name is overwritten with
  A's substitute given name, and `unmask_arguments` returns **A's** real surname
  for that row.
- **Why it is a fork.** The owner already decided (§Опрос 2, Forward collision):
  distinguish by proven source/context/identity, never by message role; if
  indistinguishable → refuse the ambiguous operation; existing substitutes keep
  their continuity. But the owner also decided that **no new provenance API
  fields** may be assumed (REMAINING-DECISIONS Блок 2) — so the disambiguating
  signal must be one the engine already has.
- **Options.**
  1. Refuse the affected tool result/call occurrence (refusal unit is the whole
     affected call/answer).
  2. Disambiguate from existing inputs only: the call/result binding, the
     conversation view, `token_uses` occurrence history.
  3. Re-mask the collision occurrence as a new real value (never a silent pick).
  4. Keep status quo (rejected by the current decision).
- **Price.** (1) a legitimate echo inside a tool result would be refused unless
  refusal is per-occurrence; (2) needs a signal that is provably discriminating
  and must be measured on the existing corpus; (3) breaks substitute continuity
  for legitimate echoes.
- **Acceptance for the chosen option:** `A2` green, `A1`/`A3`/`C2`/`P` still
  green, no new API field, occurrence source proven from available state.

## O-CORE-S1-2 — lone surname / given name of a person already known in the conversation

- **Episode (executed, `C`):** with a reordered prior row for the same person in
  an earlier conversation, the canonical full name in `c2` gets one substitute
  and a later lone surname in `c2` gets a **different** one; both resolve to the
  same real person.
- **Why it is a fork.** "One person gets one consistent substitute for whole and
  parts" is decided, but the engine's conversation scope deliberately lets a
  foreign-conversation part be re-minted; a fix must not collapse two different
  people who share a surname in one document.
- **Options.** (a) always link the part to the conversation's full-name row;
  (b) link only when the part has exactly one owner in that conversation;
  (c) status quo.
- **Price.** (a)/(b) risk over-linking a shared surname; (c) keeps split identity.
- **Acceptance:** `C` green, `C2` green, two-people-one-dialogue positive
  controls unchanged.

## O-CORE-S1-3 — the model invents a country prefix on a substitute phone

- **Episode (executed, `D1`):** the model writes `«+3 <fake 10 digits>»`; the
  restore leg returns `«+3 962 056-61-63»` — the real subscriber digits under the
  invented prefix, `surviving_substitutes` empty. Recorded shape P4:
  `+3 929 542-23-19`.
- **Why it is a fork.** The engine deliberately keeps "what stands before the
  last ten digits" as the agent's convention (so `8 …`, `+7 …` and bare ten
  digits keep their form). Only `+8`/`++` are guarded. Whether an *invented*
  prefix must be preserved, refused or replaced is a fidelity-vs-usability
  choice the owner has not made.
- **Options.** (a) keep the agent's prefix but emit a residual/refusal when it
  differs from the real canonical's; (b) replace with the real canonical's
  prefix; (c) status quo.
- **Price.** (a) adds a residual to a legitimate foreign-prefix client; (b)
  overrides an explicitly written agent form, which the owner said outranks
  schema notation; (c) leaves a wrong real number silently delivered.
- **Acceptance:** `D1` green; legitimate notations (`8 …`, `+7 …`, ten digits)
  still keep their form; the guard must not swallow `+8`/`++` behaviour already
  pinned by existing tests.

## Ask, verbatim-ish

1. For `O-CORE-S1-1`: which of options 1–3, or a named existing decision that
   already covers it?
2. For `O-CORE-S1-2`: link always / link on unique owner / keep status quo?
3. For `O-CORE-S1-3`: preserve-with-residual / replace / keep status quo?

Until an answer arrives, `K1` stays blocked on these three forks; independent
read-only research may continue.
