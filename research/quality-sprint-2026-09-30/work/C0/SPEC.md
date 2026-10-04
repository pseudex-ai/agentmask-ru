# C0 — SPEC: temporary-secret QUALITY type contracts (CVC/CVV/CID · OTP/SMS/3DS · temporary secrets)

**Task:** C0 — `work/C0` (only write scope). **Wave:** first design/RED wave.
**Gate:** G3 (design/RED, quality-contract half) + **O-SECRET = OWNER_PENDING**.
**Precondition:** [B0 GATE](<research/quality-sprint-2026-09-30/work/B0/GATE.json>) `G1 LOCAL/DESIGN PASS`; production `NOT_MEASURED`.
**Status of this document:** a *contract proposal*, not an implementation brief and not an approved registry.

> This task changes **no engine source**. The product source is pinned at `0bfda236`; `890c508` is research-only evidence. Verified: `git diff 0bfda236 -- <8 engine files read>` is empty ([checks.log C1](<research/quality-sprint-2026-09-30/work/C0/checks.log>)).

---

## 1. What is asked, and what is not

**Asked (task C0):** turn the owner-approved temporary-secret direction into a *precise quality type contract*, on a **synthetic isolated** path: which types, which evidence types each value, which lengths/forms, how malformed values behave, how substitutes are constrained, what faithful restoration means per hop, and positive + hard-negative pairs. Produce the forks that only the owner can decide as `OWNER_PENDING`.

**Not asked, and not done:**
- no engine/recognizer/renderer/restore implementation (`C1` is blocked by O-SECRET and by K1/V1/N1);
- no storage, TTL, expiry, admin, API or HITL work — those are the **next** feature-sprint by direct owner decision;
- no real CVC/OTP value, no real payment instrument, no production/customer traffic, no provider or benchmark call;
- no PCI re-research (the primary sources are reused and cited, not re-fetched);
- **no claim** of engine quality, PCI compliance, payment readiness, or "entire quality green".

Governing decisions are listed in [TYPE-CONTRACTS.json](<research/quality-sprint-2026-09-30/work/C0/TYPE-CONTRACTS.json>) under `owner_decisions_already_settled_do_not_reopen`; the load-bearing quotes come from [REMAINING-DECISIONS §Блок 3](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L19-L27>) (CVC destinations «в любой ответ той же операции»; CVC not excluded; «Да, исследовать всё семейство временных секретов»; lifecycle/admin/API/HITL deferred) and [GOAL-BRIEF §2.3, P01–P18](<research/quality-sprint-2026-09-30/GOAL-BRIEF.md#L60-L68>).

---

## 2. The class model (full machine-readable form in `TYPE-CONTRACTS.json`)

| # | family | class | scope | discriminator | length |
|---|---|---|---|---|---|
| 1 | `CARD_VERIFICATION_CODE` | static printed card secret | **in** (owner: not excluded) | authoritative field name, then bounded card-code cue | **3 or 4** (brand-dependent: CVV2/CVC2/CSC 3, CID/4DBC 4) |
| 2 | `ISSUER_OTP` | dynamic issuer one-time value (3DS/SMS/email/push) | **in** (owner: whole family) | authoritative field name, then explicit one-time/channel wording | **explicitly unasserted** |
| 3 | `TOTP_2FA` | dynamic time-based one-time value | **candidate — OWNER_PENDING (O-SECRET-4)** | 2FA/TOTP context | 6 or 8, unasserted |
| 4 | `RECOVERY_CODE` | static single-use list secret | **candidate — OWNER_PENDING (O-SECRET-4)** | recovery/backup wording or field | vendor-defined, unasserted |
| 5 | `TRANSACTION_AUTH_CODE` | one-time operation authorisation code | **candidate — OWNER_PENDING (O-SECRET-4)** | operation-authorisation wording | unasserted |

**Explicitly excluded, with the reason recorded** (not omitted): `CARD_PIN` (persistent, not temporary), `PAN` (existing `CARD` + Luhn), `CARD_EXPIRY` (not SAD), cardholder name (already `NAME`), password/passphrase (already `SECRET`), API keys/tokens (already `SECRET`, published prefixes), **bare short digit runs**, business orders/requisites, and the v6 identifier types.

**Registry fact.** The v6 snapshot registry enumerates **63** type codes and contains **no** CVC/CVV/OTP/3DS/SMS/PIN type ([checks.log C8](<research/quality-sprint-2026-09-30/work/C0/checks.log>), [tz-agentpii6.md](<research/hop-format-audit/next-sprint-review/v6-snapshot/tz-agentpii6.md>)). The temporary-secret family is therefore **additional** and needs its own allocation decision — it may not be smuggled in as a v6 alias (O-SECRET-1).

---

## 3. Discriminator policy — "no generic digit regex" made operational

A short digit run has **no intrinsic evidence**. The contract therefore states, per family, which discriminator licenses the value, and what is **forbidden**:

- **primary:** an authoritative field name in a typed KV / schema field (`cvc`, `cvv2`, `cid`, `otp`, `sms_code`, `auth_code`, `3ds_code`).
- **secondary:** a *bounded* cue phrase in prose. The engine's existing mechanism is exactly `(?i:{cues})\D{0,20}?({shape})\b` (`pseudex/assets.py:432`); the cue window is therefore already pinned at **≤20 non-digit characters** and any widening is a measured change, not a free one.
- **forbidden by construction:** a bare digit run of any length; the generic cue `код` alone; card-PAN proximity (upstream population: **0/77** annotated codes adjacent to a card — [FINDINGS §3](<research/quality-sprint-2026-09-30/followup/cvc-context-contract/FINDINGS.md>)); entropy or "looks random" scoring (`pseudex/credentials.py:1-20` rejects entropy as a discriminator).

**Why a fixed `\d{3}` is not the class.** The class is **3 or 4** digits by the PCI SSC primary source. A fixed `\d{3}` silently leaves the 4-digit CID variant open; an unbounded `\d{3,4}` widens the false-positive surface of the 3-digit form. The contract requires a **declared bounded length set per alias**, re-measured against the negative suite on any change.

---

## 4. Engine facts at the pin (read-only; no writes)

Re-derived by [probe_engine.py](<research/quality-sprint-2026-09-30/work/C0/probe_engine.py>) → [PROBE-FACTS.json](<research/quality-sprint-2026-09-30/work/C0/PROBE-FACTS.json>); full detail in that file's `mechanism_facts`.

| Fact | Evidence |
|---|---|
| The leased key map knows **no** card-code spelling; `cvc`/`cvv`/`cid`/`otp` → `None` | `KEY_TYPE` has 82 entries ([assets_source.py:1334](<prototype/licensing/assets_source.py#L1334>)); probe `key_type_cvc`/`key_type_otp` are `null` |
| A compound authoritative key is **mis-typed, not merely unknown**: `card_cvc`/`cardcvc` → `CARD` (ordered prefix-stem fallback) | `_key_type` ([structured.py:74](<prototype/pseudex/structured.py#L74>)); probe `key_type_card_cvc = "CARD"` |
| The consequence is **executed**: `_card_length("314") == 16` and `_render_token("CARD", original="314")` returns a **16-digit Luhn-valid card number** — a 3-digit field receives a 16-digit substitute | probe `card_renderer_for_3_digits` (the sample is CSPRNG-random by design, so a re-run yields a different 16-digit string; the LENGTH is the fact) |
| The JSON KV regex is **string-values only**: `{"cvc": "314"}` matches, `{"cvc": 314}` matches **nothing** | `_JSON_KV` ([structured.py:56](<prototype/pseudex/structured.py#L56>)); probe `kv_regex_matches` |
| An entity type with **no renderer** falls through to `REDACTED<6 hex>`: `_render_token("CVC", original="314") == "REDACTEDf40bac"` — a 14-char marker inside a numeric field | `_render_token` ([vault.py:1838](<prototype/pseudex/vault.py#L1838>), fallback [1929](<prototype/pseudex/vault.py#L1929>)) |
| `SECRET` already holds the **top priority slot** (8) and is anchored to published prefixes; its collision argument is "well over a hundred bits" — which **does not transfer** to a 1000-value domain | `PRIORITY` ([assets_source.py:1485](<prototype/licensing/assets_source.py#L1485>)); `credentials.py:45`; [vault.py:1765](<prototype/pseudex/vault.py#L1765>) |
| The **typed-KV mechanism is live** for classes it knows: `{"password": "hunter2"}` → `SECRET` | probe `CTRL-1` (held) |
| A malformed value under a numeric key type is **demoted to OPAQUE, never dropped** | [structured.py:55](<prototype/pseudex/structured.py#L55>), [371-372](<prototype/pseudex/structured.py#L371-L372>) |
| Audit already hides a 3-digit value (`_preview` → all bullets for `len <= 3`) | [audit.py:39](<prototype/pseudex/audit.py#L39>) |

---

## 5. RED results on the pinned unchanged build — expected failing properties

[RED.log](<research/quality-sprint-2026-09-30/work/C0/RED.log>) / [PROBE-FACTS.json](<research/quality-sprint-2026-09-30/work/C0/PROBE-FACTS.json>): **9/9 intentional REDs `RED_CONFIRMED`**, **4/4 controls held**, **0/14** synthetic positives protected, **10/10** hard negatives open, exit 0. `suite_verdict = NOT_A_SUITE_PASS`.

| RED | property that does not hold today | observed |
|---|---|---|
| RED-1 | a value under an authoritative card-code field/alias is protected | 0/5 fielded CVC positives |
| RED-2 | prose/form label with a colon (`CVV: 314`) is protected | not protected |
| RED-3 | `_JSON_KV` matches the unquoted numeric form `{"cvc": 314}` | `[]` (quoted form does match) |
| RED-4 | a dynamic issuer one-time code is protected as its own class | 0/4 OTP positives |
| RED-5 | a malformed value under an authoritative field is masked, not passed | both malformed fixtures open |
| RED-6 | one card code and one OTP in one utterance receive **different** classes | no spans at all |
| RED-7 | two card objects keep their codes bound per object | only the PAN is typed |
| RED-8 | a card-code type renders card-code-shaped, never `REDACTED…` | `'REDACTEDf40bac'` |
| RED-9 | a compound key resolves to the most specific class; substitute length equals source length | `card_cvc → CARD`, 3 digits → 16 |

**These are capability gaps reproduced as RED, not regressions and not a suite PASS.** A RED here is the property the future patch (C1) must turn GREEN under G4, with the counterexample and mutation-red discipline.

**Controls that must keep holding** (and do): 9/9 business/status/order same-glyph negatives stay open; a bare `код` does not license a card code; keyed `SECRET` still types; the `CARD` class still types.

---

## 6. Fixtures and the local checker — and the limit of what they prove

[FIXTURES.json](<research/quality-sprint-2026-09-30/work/C0/FIXTURES.json>) is generated by [gen_fixtures.py](<research/quality-sprint-2026-09-30/work/C0/gen_fixtures.py): **32 fixtures** — 14 positives, 10 hard negatives, 2 malformed-under-field, 3 form-fidelity, 2 ambiguity, 1 structural gap, 2 owner-pending candidates — across **4** families, with **8** positive↔negative glyph-identical pairs.

**All values are synthetic**, constructed for this task from a documented synthetic block; none was collected, sampled, transacted, fetched or derived from real traffic or a real instrument. The published non-live test PAN `4111111111111111` appears only as a structural neighbour inside a JSON object.

**Hard negatives are HARD by construction:** each carries the *same digits* as its paired positive and differs only in context (`{"order_code":"314"}` vs `{"cvc":"314"}`; `заказ 314` vs `cvc 314`). **The self-check in `gen_fixtures.py` validates only its own syntax tables and the internal consistency of the fixture set. It is not a detector and never counts as engine quality** ([checks.log C3](<research/quality-sprint-2026-09-30/work/C0/checks.log>); the flag `never_counts_as_engine_quality` is written into the artifact).

---

## 7. Acceptance properties proposed for C1 (G4–G7 + G8 only)

A1 same-run recall on positives **and** open hard negatives · A2 declared length set per alias · A3 CVC and OTP in one utterance receive different classes/policies · A4 substitute length/shape equals the source, never `REDACTED…`, never a `CARD` shape · A5 exact-digit restoration in the same operation, agent's own written form preserved, a partial restore is a failure · A6 per-object binding, indistinguishable pair fails closed · A7 tiny-domain collision/refusal is explicit · A8 no real value in any run artifact (absence proven by reading stores, not by trusting the API) · A9 a green quality result implies **no** durable retention of real values.

Gate applicability is exactly the approved one: **C1 = G4–G7 synthetic isolated quality + G8 compatibility only**; G9 retention/expiry/multiworker lifecycle and G11 payment-ready are **out** ([SPRINT-PLAN §7](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L163-L168>), [EXECUTION.json](<research/quality-sprint-2026-09-30/EXECUTION.json>) `gate_applicability`).

---

## 8. Deferred constraints, documented separately and not blocking this scope

Recorded here so the future feature-sprint inherits them, **without** implementing anything now (owner: lifecycle/storage/admin/API/HITL deferred):

1. **Retention.** Every existing mint durably writes the real value into the SQLCipher vault; there is no non-persistent mint path (`vault.py:3226`, `vault.py:2151-2153`). PCI SSC states cryptography cannot satisfy the no-storage rule; the durable vault is therefore **not by itself** an answer for this class ([FINDINGS F3](<research/quality-sprint-2026-09-30/followup/cvc-context-contract/FINDINGS.md>)).
2. **Lifetime is per-table, not per-class**; the core `tokens` table has no expiry by design. A per-class lifetime is a numbered schema change under the pinned-minor contract.
3. **Observability.** `/reveal`, `/events`, `/spans`, UI and logs must not become a read-back path for a live secret; audit is already value-free for 3-digit values.
4. **Tiny domain.** A 3-digit substitute space is 1000 values; collision handling and refusal are mandatory, not an optimisation.
5. **Claims boundary.** Nothing here authorises production retention or a payment-ready claim; C1 acceptance is synthetic and isolated.

---

## 9. Open questions

All ten forks are in [OWNER-QUESTIONS.md](<research/quality-sprint-2026-09-30/work/C0/OWNER-QUESTIONS.md>) as **O-SECRET-1..10**, each with episodes, applicable principles, options, price, proposed RED/acceptance and `status = OWNER_PENDING`. O-SECRET blocks **C1 only**; independent read-only work continues.

## 10. Limits

No production traffic, no real secret, no PCI DSS v4.0.1 clause text, no EMVCo text, no YooKassa/CloudPayments field table was obtained; the OTP length is deliberately unasserted; it is not established whether a 3DS one-time value is SAD. The REDs are reproduced on a **pinned unchanged local build**, not on the deployed artifact, whose digest remains `NOT_VERIFIED` for RG.
