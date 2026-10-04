# S1 revision-2 SPEC — critical RED mechanisms (corrected)

Task `S1` of the approved plan. This is a **design/RED** deliverable: executed
counters on the pinned, unchanged build. It is not a product patch, not an
acceptance score, and not a claim that the recorded production traces are
explained. Revision-2 answers the independent critical review of
[REVIEW.md](../review-critical/REVIEW.md); revision-1 (`../SPEC.md`,
`../s1_probes.py`, `../GATE.json`, `../RED.log`) is preserved read-only and
authoritative for what it measured.

Pinned build: product source `0bfda2363ef1a1d552e2ac093129b1026a86ad68`, now at
evidence HEAD `8a808ca70a13b3b19b28d60c6746c443bec01ea0`. Executed evidence
[revision.log](revision.log): exit **4** = intentional RED for **4** violated
properties (`A2`, `B`, `C`, `D1`); the same violated set as revision-1, on
corrected predicates.

## 0. Corrections against revision-1

| revision-1 claim | disposition | corrected statement |
|---|---|---|
| original raw input/response of N2/P4/D1/D2 "unavailable" | **CORRECTED** | The raw **is** archived (`ARCHIVED_RAW` in `s1_probes_v2.py`): `prompt_rule-005` user message 1, `long_clinic-001` L49 responses 7/13, `long_clinic-006` L60 `reply_raw`/`reply`/`reply_whole`, `fanout_pick-017` L607 response 14. What is missing is the historical **vault/provenance/mint order**, not the raw text. |
| B reconstructs "the original raw input" | **CORRECTED** | Revision-1's phone `8 974 239 86 41` differs from the archived `8 926 123 45 67`. B remains a valid RED for its own input; it is **not** an exact replay. |
| given name "never born as a candidate" | **CORRECTED (and reversed)** | A NAME candidate **is** produced by `gazetteer_names` (`«битюкова зинаида»`) and survives `suppress`; it is dropped at `_resolve` because the `ADDR` span outranks it. The full replication matches the public detector output. |
| D1 explains the archived P4 `+3 …` | **CORRECTED** | D1 is a **synthetic input-side mutation** (`+3 <fake>` before restoration). Archived P4 is a **different boundary** (`+7 <fake>` → `+3 <same recorded digits>`). D1 is a separate numbered property; it neither explains nor closes P4. |
| historical streaming failure needs host `/unmask_chunk` sequence, provider SSE framing, proxy-vs-sidecar leg | **CORRECTED** | The historical path is **in-process**: `harness.stream_verdict` fixes `STREAM_CHUNK=17`, feeds one `StreamDetokenizer`, calls `flush()`, compares against `unmask_text`. SSE framing and leg choice are not missing inputs; the **vault state** is. |
| E2 is a `CONTRACT_GAP` / engine black point | **CORRECTED** | Withholding the tail until `flush()` is the **documented carry contract** of the pure API — expected behaviour, recorded `CONTRACT_EXPECTED`, not counted as engine RED. |
| the model-visible tool message "cannot distinguish" an external new-real value from an echo | **SOFTENED** | The static handoff of `recorded` to tool messages is not an input-equivalence proof. `indistinguishability_claimed: false`. |
| A2 reuses one context/vault across three variants | **FIXED** | Each variant gets a fresh vault and its own setup; the three harms are reported separately (`surname_left_in_clear`, `reverse_wrong_person`, `given_name_merged`). The bare variant does not overwrite a given name. |
| C passes vacuously when `_find_fake` fails | **FIXED** | The predicate requires a **nonempty, exactly identified** substitute for both the full name and the lone surname; otherwise `INVALID_FIXTURE`. |
| A1 tested only the original fake surname | **FIXED** | A true second-person round trip is added: every substitute minted for the second person's value must restore to that person. |

## 1. Property results (executed; exact counts in [revision.log](revision.log))

| Probe | Status | Corrected one-line evidence |
|---|---|---|
| `P` | `HOLDS` | clean round trip exact; substitute stable in its own conversation |
| `A1` | `HOLDS` | 0/3 variants leak on the plain-message foreign-conversation path; **second-person round trip ok** |
| `A3` | `HOLDS` | namesake of a substitute in a foreign conversation stays masked |
| `A2` | **`VIOLATED`** | 3/3 isolated variants: surname left in the clear **and** the reverse leg returns the first person's real surname; the two row variants also overwrite the given name (`merged`), the bare variant does not |
| `B` | **`VIOLATED`** | `gazetteer_names` produces NAME `«битюкова зинаида»`, it survives `suppress`, and `_resolve` drops it (ADDR outranks NAME); final spans `[LOC «битюкова», PHONE]`; given name `зинаида` reaches the model raw |
| `C` | **`VIOLATED`** | nonempty exact identity: full name → `«Боброва Василиса Алексеевна»`, lone surname → `«Ткачук»`; both resolve to the same real person; surnames differ |
| `C2` | `HOLDS` | clean-state whole/parts consistency, same nonempty predicate |
| `D1` | **`VIOLATED`** | approved notations (`+7…`, `8…`, bare 10) keep their form and the exact copy restores; an invented `+3`/`+9` silently delivers the real subscriber digits with `residual=[]` |
| `D2` | `NOT_MEASURED` | 375 checks, 0 mutations; the recorded `c-3→c-8`, `127.10.1965` rewrite is **not** reproduced from this fixture (pointer in `ARCHIVED_RAW`) |
| `E1` | `HOLDS` | 130 comparisons over 5 surfaces × 26 chunkings, 0 mismatches; the historical mismatch is **in-process** and its vault state is unreconstructed |
| `E2` | `CONTRACT_EXPECTED` | 64 chars withheld without `flush`; documented carry contract, **not** an engine RED |

## 2. Mechanism per RED

### `A2` — one byte string, two people, in a tool result
`envelope.mask_messages` hands every `role:"tool"` message the dialogue's
`recorded` values as the conservative leg (`envelope.py:1605-1653`). When a tool
result carries another person's real surname byte-identical to an issued
substitute's surname, the leg keeps it and the reverse leg resolves it to the
first person. **Causal boundary:** the collision precondition is **constructed**
from the observed substitute; it is not a replay of the original vault and it
does not prove which internal guard produced the recorded `document:office-005`
symptom. Whether **all available inputs** are incapable of distinguishing a
genuine echo from an external new-real value is **not proven here** — that
information audit is required before any new API proposal.

### `B` — the NAME candidate is born and then outranked
Instrumented stages on the phrase:
`recognizers` → `NAME «битюкова зинаида»` (plus `ADDR «битюкова»`);
`suppress` → both survive; `_resolve` → NAME dropped, final
`[LOC «битюкова», PHONE]`. The replication is checked against
`Detector.detect` output (`replication_matches_public_detect: true`). So the
correct statement is "the candidate is outranked at resolution", not "never
born". `mask_one` then ships the given name raw.

### `C` — whole/parts split across a reordered prior row
Precondition (deterministic): the same person appears in `c1` in the reordered
form `«Зинаида Битюкова»`; in `c2` the canonical full name and later only the
surname. `c2` gets two different surnames for one real person; the clean `C2`
control holds, so a fix must not simply freeze parts globally. A source-order and
cross-conversation variant is still needed before the whole identity class is
claimed covered.

### `D1` — the restore leg keeps an invented country prefix
`redact._digits_in_form_of` deliberately keeps what stands before the last ten
digits as the agent's, and only `+8`/`++` are guarded
(`redact.py:1642-1654,1728-1745`). An invented `+3`/`+9` therefore receives the
**real** last ten digits under the invented prefix with
`surviving_substitutes(...) == []` — neither the real value nor visibly refused.
**Separate from archived P4:** archived `long_clinic-001` is
`+7 929 542-23-19` → `+3 929 542-23-19` (same ten digits, prefix changed by the
engine), which this probe does not reproduce or explain.

## 3. Streaming and non-PII — precise gaps, not "passed"

1. **Non-PII rewrite (D2).** Not reproduced: 375/375 held on a fresh fixture.
   Missing is the `fanout_pick-017` vault/provenance and the raw-before-restore
   bytes; the archived `raw`/`restored` pair is a pointer, not a reconstruction.
   The recorded rewrite is **not** evidence the class is absent.
2. **Stream vs whole, historical episode.** `long_clinic-006` L60 keeps
   `reply_raw` (fake DOB `08.04.1964`), delivered `reply` (fake kept),
   `reply_whole` (real `04.04.1964`) and `stream_mismatch=true`. The producing
   contract is in-process `STREAM_CHUNK=17` + `flush`. The episode stays
   **NOT_MEASURED for reproduction** because its vault state is not reconstructed
   — not because the transport is unknown.
3. **Original causality of N2/N3/P4.** Not claimed; the mechanisms are
   deterministic REDs in their own right.

## 4. Decision coverage — no new owner policy is opened

revision-1's `OWNER-QUESTIONS.md` asked three policy questions. On independent
review each is already bounded by approved decisions, so revision-2 records
`covered_by_decision_ids` instead of re-asking (GOAL-BRIEF §9: an absent fork is
recorded, not invented). Full mapping in
[DECISION-COVERAGE.md](DECISION-COVERAGE.md).

- `O-CORE-S1-1` **covered_by** `REMAINING-DECISIONS §Блок 2` (use existing
  provenance/history first; new API fields not authorized), `OWNER-DECISIONS
  §Опрос 2 Forward collision` (distinguish by proven source/context/identity,
  never by role; if indistinguishable → refuse the affected operation; issued
  substitutes keep continuity), `SPRINT-PLAN §7`. **The concrete algorithm still
  needs technical evidence and independent review; existing policy does not make
  every proposed patch correct.**
- `O-CORE-S1-2` **covered_by** `OWNER-DECISIONS §Опрос 2` (one person → one
  consistent substitute for whole and parts) and the wiki invariants on
  conversation scope / shared-name ambiguity. Always-link and known split
  identity are not equal valid alternatives; only a genuine counterexample to
  these joint rules would open a question.
- `O-CORE-S1-3` **covered_by** `REMAINING-DECISIONS §Блок 2` (explicit agent form
  outranks schema; do not silently repair a changed identity; name unresolved
  near-miss and refuse unsafe delivery) and the wiki phone-notation invariants.
  Only an explicitly proposed **new equivalence/exception** (e.g. extending the
  approved `7↔8`/bare-notation set) would need an owner choice.

**Only a genuinely new policy question would be asked** — for example, persisting
new provenance fields, or adding a new country-code equivalence rule. No such
question is opened here.

## 5. Limits

- No product, scorer, corpus, wiki or licensing file was written or patched.
- Substitutes are minted with `secrets`, so concrete strings differ per run; the
  fixture spec is hashed (`6178608f…`, revision-2) and the original revision-1
  fixture hash (`438f3186…`) is preserved. **Property verdicts are invariant;
  concrete values are not.**
- Three revision-1 repeat runs showed the same violated set. That is repeated
  empirical evidence, **not** a proof of determinism for every future random mint.
- No claim about recall/precision/PPV, the whole quality sprint, or production.

## 6. Gate position

`G3` is **not PASS**. Accepted evidence is scoped to the specific probes and
predicates above; the disputed choices are mapped, not approved, and full-package
`G3` requires accepted disputed design and an independent re-review of these
frozen revision-2 artifacts. `D2` and the historical `E1` episode remain
`NOT_MEASURED` for reproduction (their fixture checks **were** executed, which is
a different statement from "never executed").
