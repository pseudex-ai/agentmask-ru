# C0 — O-SECRET owner questions (OWNER_PENDING)

**Decision point:** `O-SECRET` — per [EXECUTION.json](<research/quality-sprint-2026-09-30/EXECUTION.json>) it requires "precise temporary-secret quality scope, no current lifecycle implementation" and **blocks `C1` only**. `C1` additionally requires "precise temporary-secret type registry before implementation; no real CVC production enablement".
**Nothing below is decided by this task.** Every item is `OWNER_PENDING`; independent read-only work continues while they are open. Settled items are *not* re-opened — [РЕМАINING-DECISIONS §Блок 3](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L19-L27>) already answered destinations, scope and deferral.

Format per [OWNER-DECISIONS](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L45-L53>): episodes/provenance · applicable principles · the unknown · mass-mechanism options · price · proposed RED and acceptance gate · status.

---

## O-SECRET-1 — registry allocation for the temporary-secret family
**Kind:** registry/scope. **Blocks:** C1 (with O-SECRET-2).
**Episode/provenance.** The v6 registry enumerates 63 type codes and contains no CVC/CVV/OTP/3DS/SMS/PIN type ([checks.log C8](<research/quality-sprint-2026-09-30/work/C0/checks.log>); `tz-agentpii6.md` sha256 `b0cba571…`). The owner has already required "precise temporary-secret type registry before implementation" (EXECUTION.json, C1).
**Applicable principles.** P18 (gates are not decorative); G8 (all types visible, no alias turned into a fake pass); GOAL-BRIEF §2.3 ("native product support is proved per type/family").
**Unknown.** Whether the family becomes new registry item types (`CARD_VERIFICATION_CODE`, `ISSUER_OTP`, …), a separate secret family with its own lifecycle, or is excluded from the v6 registry entirely and tracked only by the quality gate.
**Options.** (a) new item types in the unified registry — visible in every matrix, heaviest; (b) a separate `secret_family` namespace with its own priority and storage policy — keeps the 55 v6 types untouched; (c) documented-only, no registry entry — cheapest and would make the type invisible, which G8 forbids for a claimed class.
**Price.** Registry visibility vs schema/priority churn vs the risk of an invisible claimed class.
**Proposed acceptance.** A registry diff where each proposed type appears exactly once with its grammar/priority/renderer declared; a mutation that removes one entry must be RED.
**Status: OWNER_PENDING.**

## O-SECRET-2 — accepted detection-evidence boundary per class
**Kind:** detection boundary (carries forward Q-A1).
**Episode.** Of the only external population, **77** annotated CVC values: 48 carry a `cvc|cvv|цвс|цсв` token within ±25 chars, **29 carry neither that token nor a nearby card**, and **0/77** sit near an annotated card ([FINDINGS §3](<research/quality-sprint-2026-09-30/followup/cvc-context-contract/FINDINGS.md>)). Positives/negatives: [FIXTURES.json](<research/quality-sprint-2026-09-30/work/C0/FIXTURES.json>) `POS-CVC-001..008`, `NEG-*`.
**Applicable principles.** P09 (one ambiguous form is not evidence); P05/Q3 (look-alike numbers are not personal documents); P01 (mass mechanism, not a witness list).
**Unknown.** Whether the cue-less 29 are card codes, OTPs or order codes — the annotation does not resolve it. Choosing proximity adds risk with **zero** external support.
**Options.** (a) field-name only (highest precision, misses prose traffic); (b) field-name OR bounded card-code cue, with `код` explicitly excluded (the measured separation is clean: RED-1..RED-4 show 0 protection today, and the 9/9 negatives stay open); (c) field-name OR cue OR PAN proximity (unsupported: 0/77).
**Price.** Prose recall vs over-masking business numbers vs a rule that matches half the language.
**Proposed RED / gate.** Same-run positive + same-glyph negative set; the cue window (≤20 non-digit chars) and shape set pinned; **any negative that starts matching is a RED**; G4/G7.
**Status: OWNER_PENDING.**

## O-SECRET-3 — length policy for `ISSUER_OTP`
**Kind:** grammar.
**Episode.** The 3DS OTP length was deliberately not established (CONTEXT-MATRIX `known_coverage_gaps`); positives `POS-OTP-001..004` are 6 digits only as fixtures, not as a grammar claim.
**Applicable principles.** P18 (no denominator invented for success); specification honesty.
**Unknown.** The real length distribution (4–10?) and whether it is issuer-defined at all.
**Options.** (a) declared bounded set from provider documentation; (b) context-only typing with no length constraint (recall up, precision down, needs a measured negative suite); (c) unasserted/NOT_MEASURED in the acceptance matrix until a source exists.
**Price.** Recall vs false-mask rate vs an unmeasured grammar.
**Proposed RED / gate.** A negative suite of same-length business numbers; a length change re-measures the negatives; G4.
**Status: OWNER_PENDING.**

## O-SECRET-4 — which adjacent classes enter the quality denominator
**Kind:** scope/denominator.
**Episode.** `CAND-TOTP-001` (2FA), `CAND-REC-001` (recovery code) exist as fixtures with no RED; `TRANSACTION_AUTH_CODE` has none; `CARD_PIN` is persistent, not temporary.
**Applicable principles.** Owner: "исследовать всё семейство временных секретов"; G7 (types must not disappear from the table); P18 (no denominator rewriting).
**Unknown.** Which of TOTP / recovery codes / transaction authorisation codes / PIN count as "personal data or agreed temporary secrets" for this sprint's claim.
**Options.** (a) full family — widest claim, largest denominator; (b) card- and issuer-authentication only (CVC + ISSUER_OTP), the others documented as NOT_MEASURED; (c) full family but reported descriptively until support ≥300 independent positives per class.
**Price.** Claim breadth vs measurement cost vs invisibility risk.
**Proposed acceptance.** Every candidate appears in the final matrix as measured **or** NOT_MEASURED — never absent; G7/Z1.
**Status: OWNER_PENDING.**

## O-SECRET-5 — malformed value under an authoritative secret field (carries Q-A4)
**Kind:** fail-closed behaviour.
**Episode.** `MAL-CVC-001` (`{"cvc":"31"}`) and `MAL-CVC-002` (`{"cvc":"31B"}`) are open today (RED-5). The engine precedent is demote-to-OPAQUE, never drop ([structured.py:371-372](<prototype/pseudex/structured.py#L371-L372>)).
**Applicable principles.** Fail-closed; P05 (protect what is written); P04 (do not repair the source).
**Unknown.** Whether masking a value that cannot be restored is better than passing it, given the gateway's promise that tool calls execute on real values.
**Options.** (a) mask-not-drop (OPAQUE) — safe, the tool cannot receive it; (b) pass unmasked — leaks a value the schema declares sensitive; (c) mask and mark the call as failed rather than partially restored (P08 refusal unit).
**Price.** Availability of the tool call vs the fail-closed principle.
**Proposed RED / gate.** Positive control: a malformed value under the field is not present in the model's input; G5/G6.
**Status: OWNER_PENDING.**

## O-SECRET-6 — legal/product framing of the class (carries Q-B3)
**Kind:** scope/claims.
**Episode.** The owner already ruled random three digits are not PII; the PCI SSC primary source makes this class a payment secret whose rule is about **retention**, not identifiability ([PRIMARY-SOURCES S1](<research/quality-sprint-2026-09-30/followup/cvc-context-contract/PRIMARY-SOURCES.md>)).
**Applicable principles.** P15/P18 (no claim without proof); customer-facing claims require owner GO.
**Unknown.** Whether customer traffic legitimately contains card verification codes at all, and which of 152-ФЗ vs the payment standard is the product's stated justification.
**Options.** (a) 152-ФЗ framing; (b) payment-retention framing; (c) both, with explicit disclosure that quality support ≠ retention permission.
**Price.** Product positioning and disclosure obligations.
**Proposed acceptance.** The chosen framing appears in the C1 report's claims section; no payment-ready sentence without the deferred lifecycle/security acceptance.
**Status: OWNER_PENDING.**

## O-SECRET-7 — per-object pairing as a required property (carries Q-A5)
**Kind:** identity/role scope.
**Episode.** `POS-CVC-008` (two card objects), `AMB-002` (card code vs order code with the same digits `000`); grouping primitive `structured._by_object` exists but nothing binds a code to a number.
**Applicable principles.** P06 (one persona/entity, consistent substitute); P08 (refuse rather than choose a wrong identity); G5.
**Unknown.** Whether an indistinguishable pair must fail the whole call or only the ambiguous object.
**Options.** (a) required pairing with fail-closed on ambiguity; (b) value-only binding (forbidden by the tiny-domain argument); (c) per-object pairing required plus an explicit refusal message.
**Price.** Multi-card payload availability vs wrong-card restoration risk.
**Proposed RED / gate.** Two-card payload where card A's code would restore into card B is a RED; an indistinguishable pair must refuse, not guess; G5.
**Status: OWNER_PENDING.**

## O-SECRET-8 — tiny-domain collision and refusal policy
**Kind:** identity/collision.
**Episode.** 3-digit space = 1000 values. The credentials renderer's safety argument — "collision not possible in practice: well over a hundred bits" ([vault.py:1765-1782](<prototype/pseudex/vault.py#L1765-L1782>)) — **does not transfer** here. Prior fix RED-9 shows a 3-digit value already receiving a 16-digit substitute.
**Applicable principles.** P07 (new real ≠ automatically old fake); P08 (known collision → explicit refusal of the affected unit); P06.
**Unknown.** The minimum context that makes a forward collision distinguishable for a 1000-value domain.
**Options.** (a) key the mapping by (binding unit, value) plus a per-unit no-reuse rule; (b) refuse the ambiguous operation; (c) unbounded retries until a fresh substitute exists — impossible once the unit exhausts the domain.
**Price.** Refusal/availability vs the guarantee of continuous identity.
**Proposed RED / gate.** A new real equal to a previously issued fake within the same binding unit must NOT be silently restored; refusal is the expected outcome; G5.
**Status: OWNER_PENDING.**

## O-SECRET-9 — which hops the C1 acceptance matrix asserts
**Kind:** hop scope.
**Episode.** Owner: CVC is valid "в любой ответ той же операции" (any answer of the same operation); the sprint's hop inventory is IN/user, IN/tool, IN/document, IN/memory, OUT/tool_arg, OUT/answer, OUT/summary, OUT/template, streaming and non-streaming ([GOAL-BRIEF §2.2](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md#L52-L58>)).
**Applicable principles.** P13 (delivered stream is the real OUT boundary); P14 (no payment-argument-only restriction).
**Unknown.** Which hops have "the same operation" for a temporary secret — `IN/document` and `IN/memory` have no payment operation to bind to.
**Options.** (a) all applicable hops (owner's literal phrase); (b) operation-bearing hops only (user/tool IN, tool_arg/answer OUT) with document/memory reported as NOT_MEASURED; (c) all hops, with document/memory exempt from same-operation binding and documented.
**Price.** Claim coverage vs an unbindable-hop false-success risk.
**Proposed acceptance.** For each declared hop, a positive and a same-glyph negative; a hop without a witness is NOT_MEASURED, never assumed; G5/G6.
**Status: OWNER_PENDING.**

## O-SECRET-10 — may C1 quality acceptance use an isolated non-persistent synthetic path?
**Kind:** scope boundary / acceptance mechanics.
**Episode.** Every existing mint persists the real value durably (`vault.py:3226`), and there is no non-persistent path ([FINDINGS E9](<research/quality-sprint-2026-09-30/followup/cvc-context-contract/FINDINGS.md>)). The owner selected the temporary reversible path as a **future design intent**, not a current obligation ([REMAINING-DECISIONS Блок 3](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L25-L27>)).
**Applicable principles.** P14/P15 (test-scope support ≠ production retention); G10 (freeze before live); the claims boundary.
**Unknown.** Whether a green C1 quality result may be produced by an isolated test-only mapping that is explicitly **not** the production vault path, and how that must be labelled so it can never read as payment readiness.
**Options.** (a) isolated test-only mapping, explicitly labelled, with A9 (no durable retention implied) as an acceptance property; (b) require the future non-persistent design first (re-introduces deferred scope); (c) block C1 until lifecycle is designed (contradicts the owner's explicit deferral).
**Price.** Progress on quality vs the risk of a score that implies a production capability that does not exist.
**Proposed acceptance.** The C1 report states the path used, proves no real value reaches any store, and carries no payment-ready claim; G5/G11 boundary.
**Status: OWNER_PENDING.**

---

## Carried-forward dispositions (no re-asking)

| Old id | Disposition |
|---|---|
| Q-A1 detection boundary | → **O-SECRET-2** |
| Q-A2 compound-key precedence (`card_cvc` → CARD) | **Mechanism, not secret-specific**: reproduced here as RED-9 and owned by the core design path (S1/K1). Not an O-SECRET fork; it stays open as G3 evidence for that path. |
| Q-A3 3DS OTP in scope | **Answered by the owner**: "исследовать всё семейство временных секретов". Its *length* is now O-SECRET-3; its *classification* (SAD or not) remains an explicit UNKNOWN and no rule depends on it. |
| Q-A4 malformed under field | → **O-SECRET-5** |
| Q-A5 per-object pairing | → **O-SECRET-7** |
| Q-B1 storage/reversibility | **Deferred by the owner** to the next feature-sprint; no longer blocking this sprint. Its quality-side consequence is **O-SECRET-10**. |
| Q-B2 per-class lifetime | **Deferred by the owner**; recorded in [SPEC §8](<research/quality-sprint-2026-09-30/work/C0/SPEC.md>) as a future constraint, not implemented. |
| Q-B3 legal framing | → **O-SECRET-6** |

**Not claimed by this task:** no owner decision, no implementation permission, no engine change, no C1 acceptance, no PCI compliance, no release.
