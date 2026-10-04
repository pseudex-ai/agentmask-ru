# O-V6 — owner forks found by V0

Format per fork: episodes/provenance · applicable invariant/owner decision · what is unknown (no
invented cause) · mechanism options and the contract each keeps · price · proposed RED and
acceptance gate · status **OWNER_PENDING**.

An open fork is not converted into "decided" by an agent. Nothing below authorises a product patch;
the independent read-only work continues.

---

## O-V6-1 — checksum policy on the benchmark's `fake_checksum_invalid` line

**Provenance.** v6 `docs/tz-agentpii6.md` §6.3 + `docs/tz-agentpii6-registry.md` OD-54/OD-78;
`prototype/bench/agentpii5/perfect.py::mint_v6` (R6-39); `metrics.py::fake_checksum_invalid`;
`fixtures.py::_fake_checksum_fixtures`; `integrate_v6.py` mutant **M8**. Reproduced by
`CHK checksum-policy`.

**The contradiction.** The line's boundary is **1.0** and it counts a HIT when the substitute FAILS
its own checksum, so the "correct" arm must re-mint until the fake is INVALID. Owner **Q2** is
«Наследовать валидность исходника»: a valid source yields a valid substitute. The product invariant
`INVARIANTS.md#structured-ids` goes further — a fake СНИЛС/ИНН/card is **deliberately checksum-VALID**
(impossible ranges) so a checksum-checking agent still calls the tool. Executed: 11/11 v6
checksum-carrying `sample`s are valid; under Q2 the correct arm scores **0/11** and the **M8 mutant
scores the same 0/11** — the line cannot separate the behaviour it exists to catch from the
behaviour the owner chose.

**Options.**
1. **Redefine the line to the source's own validity** — «the substitute is valid exactly when the
   source was». Keeps Q2 and #structured-ids; M8 (valid-from-valid) becomes a HIT and a mutant that
   *repairs* an invalid source becomes the miss. Price: the v6 §6.2 "perfect gateway" paragraph and
   the OD-78 fixture expectation must be rewritten, and a new invalid-source fixture family is
   needed.
2. **Keep 1.0 and revisit the product invariant** — valid sources would mint invalid fakes. Keeps
   v6's line; contradicts Q2 and breaks a checksum-checking tool call (the tool-call loop is the
   product). Price: high, and it is a product decision, not an instrument one.
3. **Split the axis** — keep 1.0 only for types whose SOURCE is itself invalid, and report the
   valid-source population separately. Keeps both contracts on disjoint populations. Price: two
   denominators to name and print; support may be thin until the v6 corpus has invalid sources.

**Proposed RED / acceptance.** Extend `V0/checks/v0_checks.py` (already executed here) to a v6-side
test: for every `generated_checksum` type, assert `line(valid_source / valid_substitute) ==
line(M8 mutant)` is **false**. Acceptance: the chosen option makes the correct arm and M8 differ by
at least one fixture.

**Blocked on the answer:** V1's checksum clauses; nothing else.

---

## O-V6-2 — which status funnel the integration keeps

**Provenance.** v5 `contracts.OUT_HOP_WRITTEN_STATUSES` (+`out_written`, `out_no_mint`,
`out_engine_kept`, `out_not_masked`, `out_leaf_foreign`, `end_to_end_written`, `chain_*_written`);
v6 `contracts.HOP_STATUSES` + `observe.stdout_status` `"unmasked"`. Reproduced by
`CHK status-funnel`.

**The contradiction.** The two vocabularies are not ordered by inclusion: v6 has `unmasked`, v5 has
`engine_kept`/`not_masked`/`leaf_foreign`. G8 requires «written funnel не откатились», but v6's
`form_hOUT` denominator is still «observed ∪ unmasked», i.e. the pre-v5 funnel.

**Options.** (a) v5 five-status funnel is the reader; v6 rows stay additive and `unmasked` is
re-mapped in the observer; (b) keep both keys with an explicit mapping table in the report;
(c) keep v6's funnel and re-derive the v5 diagnostics from it — not possible, the information is
destroyed at the status assignment.

**Proposed acceptance.** A frozen old-corpus replay must print the same `out_*` counts as today
(v5 side) **and** the v6 rows, on one run file; `test_observe`/`test_observe_v6` both green.

---

## O-V6-3 — D-068 / D-069 / D-070 carry two different decisions

**Provenance.** `wiki/STATE.md` on both refs (exact headings quoted in SPEC §4.6 and
`COMPATIBILITY24.json` row `wiki/STATE.md`). No instrument catches it (`wiki/check.py` does not
check id uniqueness).

**Unknown.** Which branch's numbering wins, and whether the v6 decisions should be renumbered or the
v5 ones. This is a documentation-identity decision; there is no technical evidence that settles it.

**Price.** If it is merged silently, one decision loses its record and later work cites an id that
means something else — the exact failure `wiki/STATE.md` exists to prevent.

**Proposed acceptance.** After renumbering, `grep -c '^### D-' wiki/STATE.md` equals the count of
distinct ids, and every cross-reference `D-NNN` in `wiki/` resolves to exactly one heading.

---

## O-V6-4 — the home of the tables, and what `derived_piece_types` must read

**Provenance.** `pii_types.py` (v6, the single home with a stated one-way edge
`contracts → pii_types`) vs `contracts.py` literals (v5). Reproduced by `CHK v5-tables-reproduced`.

**The fork.** The v6 direction (one registry, `contracts` derives) is the better shape and is what
the v6 spec argues for; but its NAME record predates the v5 `script`/`translit` split, and its
`derived_piece_types` predicate is «`"script" in form_features or "initials" in form_features» —
which after the split no longer means "rewritten in another alphabet" (that fact moved to
`translit`).

**Options.** (a) migrate the v5 records INTO `pii_types` (v5 literals become the v5 `TypeSpec`s,
`translit` added, predicate reads `script or translit or initials`); (b) keep `contracts` literals
authoritative for v5 and let `pii_types` own only v6 — two homes, contradicted by the v6 spec;
(c) registry owns v6 only and a frozen v5 table is imported — the drift risk that produced this
finding.

**Proposed acceptance.** `pii_types`-derived `FORM_FEATURES`/`FEATURE_LABELS`/`FORM_ABSTAIN` equal
the live v5 literals **computed from the live file**, not from a hand copy; and
`test_pii_types.test_v5_tables_reproduced` reads the live `contracts` table (or a frozen blob hash
pinned in the same commit) so it can fail.

---

## O-V6-5 — typed-invalid personal identifiers after v6

**Provenance.** Q3 («защищать при доказанном типовом контексте»); v6 `pii_types.registry_problems`
T6 requires a `[K]` type to have a cue, a field key, or `bare_typed=True` — and **0 of 66 records
set `bare_typed`**. 21 records carry a `pd_context` rule.

**Unknown.** Whether "proven typed context" is reachable for a technically INVALID personal
identifier when no type admits a bare value, or whether that admission is meant to come from the v5
typed-KV layer instead. Not inferable from the snapshot.

**Proposed acceptance.** A positive fixture (invalid-but-typed personal id) and a negative control
(a business number in the same shape) that the chosen mechanism separates; without one, the v6
registry must not claim Q3 coverage.

---

## Coverage note

Owner overrides **source validity inheritance** and **all NAME parts** are addressed (one conflict,
one compatible). **Explicit agent format priority**, **typed personal invalid protection** and
**raw conditional metric** are recorded as gaps with pointers, not as decisions. No new API field
is proposed (`REMAINING-DECISIONS.md` Block 2 forbids it without proven insufficiency).
