# S1 SPEC — critical RED mechanisms on the unchanged engine

Task `S1` of the approved plan ([FIRST-WAVE-TASKS.json](<work/FIRST-WAVE-TASKS.json>)
id=S1, [FIRST-WAVE-SCOPES.md](<work/FIRST-WAVE-SCOPES.md>)). This is a
**design/RED** deliverable: executed counters on the pinned, unchanged build and
mechanism options for the owner. It is not a product patch, not an acceptance
score and not a claim that the recorded production traces are explained.

Pinned build: product source `0bfda2363ef1a1d552e2ac093129b1026a86ad68`, now at
evidence HEAD `890c50849a326f882eac336ba4e38c91171de473` (research-only commit;
`git diff 0bfda236..HEAD -- prototype licensing storefront deploy wiki` is empty).
Executed evidence: [RED.log](<work/S1/RED.log>), determinism repeats, exit **4** =
intentional RED for **4** violated properties (`A2`, `B`, `C`, `D1`).

## Binding owner decisions this SPEC must not re-open

| Source | Decision used here |
|---|---|
| [OWNER-DECISIONS.md](<OWNER-DECISIONS.md>) §Опрос 2 | **All parts of a name are protected**; one person gets a consistent substitute for whole and parts; carry may keep an already-issued substitute but may never let a real name out for the first time |
| [OWNER-DECISIONS.md](<OWNER-DECISIONS.md>) §Опрос 2 (Forward collision) | A new real value is **not automatically** an old substitute; distinguish by proven source/context/identity, never by message role alone; if indistinguishable → **explicit refusal** of the ambiguous operation, never a silent pick and never a silent passthrough; continuity of already-issued substitutes is mandatory |
| [REMAINING-DECISIONS.md](<REMAINING-DECISIONS.md>) Блок 2 | First use the **available** transformation history and occurrence source; **new provenance API fields are NOT authorized**; simple coincidence of new real with old fake does not prove echo |
| [REMAINING-DECISIONS.md](<REMAINING-DECISIONS.md>) Блок 2 | Explicit agent-written form outranks schema notation; do not silently repair |
| [OWNER-DECISIONS.md](<OWNER-DECISIONS.md>) Q1/Q2/Q3 | ≥99% + CI on samples is the *goal*, not a claim made here; checksum validity of a substitute inherits from the source; a technically invalid personal id is protected by proven typed context, not corrected |
| [SPRINT-PLAN.md](<SPRINT-PLAN.md>) §7 | `G3` requires a reproducible RED on the pinned build and a causal mechanism **only where input/state are restored**; `G5` treats any reproduced wrong-person/collision as open; `G6` requires literal/form fidelity and stream = whole where the contract is the same |
| [SPRINT-PLAN.md](<SPRINT-PLAN.md>) §11 | No guessed cause; no scorer/engine edits under this task; new owner fork before implementation |

## Property results (executed; see RED.log for the exact counts)

| Probe | Property | Status | One-line evidence |
|---|---|---|---|
| `P` | clean synthetic round trip returns the exact original; substitute stable in its own conversation | `HOLDS` | 1/1 exact, repeat-stable |
| `A1` | a new real value equal to an earlier substitute does not become the first person (plain message, foreign conversation) | `HOLDS` | 0/3 variants violated |
| `A3` | a namesake of a substitute in a foreign conversation stays masked | `HOLDS` | 0/1 leaked |
| `A2` | a surface equal to an earlier substitute, arriving as another person's real value in a **tool result**, is not resolved to the first person and does not merge the identities | **`VIOLATED`** | 3/3 variants: surname left in the clear, reverse leg returns the first person's real surname |
| `B` | both identifying parts of a name are covered (surname not typed as a bare `LOC`, given name not left real) | **`VIOLATED`** | detection: `[LOC «битюкова», PHONE]`, **no NAME span**; given name `зинаида` reaches the model raw |
| `C` | all substitutes of one real person inside one conversation are consistent in surname/given | **`VIOLATED`** | full name → `«Мещерякова Сабина Борисовна»`, lone surname → `«Савченко»`, both resolve to the same real person |
| `C2` | clean-state whole/parts consistency | `HOLDS` | defect is **state-dependent** (needs the reordered prior row) |
| `D1` | a substitute phone written with an invented country prefix either restores to the real phone or is visibly refused | **`VIOLATED`** | `«+3 <fake10>»` → `«+3 962 056-61-63»`, `residual=[]`; exact write restores correctly |
| `D2` | non-PII digits/ids survive the reverse leg byte-identical | `NOT_MEASURED` | 375 checks, **0 mutations**; the recorded rewrite is not reproduced from this fixture |
| `E1` | chunked detokenization equals whole-text detokenization for every chunking | `HOLDS` | 130 comparisons over 5 surfaces × 26 chunkings, 0 mismatches |
| `E2` | a stream that ends without an explicit flush is delivered complete | `CONTRACT_GAP` | 64 chars withheld without flush; proxy flushes only on `[DONE]`/error |

## Class verdicts (what S1 does and does not establish)

| S1 class | Verdict |
|---|---|
| forward/backward NAME collision | `PARTIALLY_REPRODUCED` — plain-message and foreign-namesake halves hold (`A1`, `A3`); the **tool-result** half is reproduced (`A2`) |
| partial NAME, given name left real | `REPRODUCED` (`B`, detection leg, reconstructed surface) |
| whole/parts consistency | `REPRODUCED` (`C`; the clean control `C2` holds) |
| numeric prose restore | `REPRODUCED` for the invented-prefix sub-class (`D1`) |
| non-PII id rewrite | `NOT_MEASURED` (`D2`) |
| streaming vs whole, original episode | `NOT_MEASURED`; in-process equality holds (`E1`), flush contract gap documented (`E2`) |

## Mechanism for each RED (what the executed path shows)

### `A2` — one byte string, two people: the tool-result echo set
`envelope.mask_messages` builds `recorded` from `_Provenance.recorded_values()`
and hands it to **every** `role:"tool"` message as the conservative leg
([envelope.py:1620–1621, 1650](<prototype/pseudex/envelope.py#L1620-L1650>)).
When the tool result carries another person's real surname that is
byte-identical to an already-issued substitute's surname, that value is
indistinguishable, *from the available inputs*, from the substitute coming
back. Executed result: the surname is left in the clear (both lower-case and
capitalized) and the given name is overwritten with the first person's
substitute given name — the second person's row is presented to the model under
the first person's substitute identity. On the reverse leg,
`unmask_arguments({"last_name": <that surname>})` returns the **first** person's
real surname. That is the `G5` wrong-person shape.

Causal boundary: the collision precondition is **constructed** from this run's
observed substitute (`<observed fake surname>` becomes the second person's real
surname). That is a controlled fixture precondition and is documented as such;
it is **not** a replay of the original vault, and it does **not** prove which
internal guard produced the recorded `document:office-005` symptom.

### `B` — partial name: surname after a preposition becomes `LOC`, given name never born
`Detector.detect("… на битюкова зинаида телефон …")` returns `[LOC «битюкова»,
PHONE]` — the surname is read as a bare lower-case place name after «на», and
`«зинаида»` is not a candidate at all. `mask_one` therefore replaces the surname
with a **city** substitute and ships the given name raw. This reproduces the
recorded N2 **shape** (masked `«… на светлогорск зинаида …»`). The original raw
input bytes of N2 are not preserved, so the phrase is a reconstruction; the
detection leg itself is stateless and deterministic, which is why this is a RED
and not a NOT_MEASURED.

### `C` — whole/parts split identity across a reordered prior row
Precondition: conversation `c1` masks the person in the **reordered** form
`«Зинаида Битюкова»`; conversation `c2` then masks the canonical
`«Битюкова Зинаида Сергеевна»` and later only `«Битюкова»`. Executed result in
`c2`: full name → one substitute, lone surname → a **different** substitute; both
reverse-map to the same real person. The model is shown two surnames for one
person inside one conversation. Presence of the reordered prior row is the
trigger; the clean `C2` control holds, so a fix must not simply freeze parts
globally.

### `D1` — the restore leg keeps the agent's invented country prefix
`redact._digits_in_form_of` deliberately keeps "what stands before the last ten
digits" as the agent's ([redact.py:1728–1745](<prototype/pseudex/redact.py#L1728-L1745>)),
and only `+8`/`++` are guarded as malformed
([`_malformed_phone_sign`](<prototype/pseudex/redact.py#L1642-L1654>)). A model
that invents `+3`/`+9` therefore receives the **real** last ten digits under the
invented prefix, with `surviving_substitutes(...) == []` — a number that is
neither the real value nor visibly refused. This is the same class as the
recorded P4 `+3 929 542-23-19`. (The exact trace's written prefix is not
recoverable, so the original trace is a shape match, not proven causation.)

## Mechanism options (for the owner; no implementation until `O-CORE`)

Each option lists the owner contract it must preserve, price, and the RED it
must turn green without losing the existing positives (`A1`, `A3`, `C2`, `P`,
`E1`).

**`O-CORE-S1-1` — tool-result collision (`A2`).** How may the echo leg treat a
tool-result value equal to an issued substitute when the occurrence source is
*not* proven to be that substitute?
1. *Status quo* — cheapest, but keeps the wrong-person restore. Rejected by the
   binding "indistinguishable → explicit refusal".
2. *Refuse the affected result/call* — aligns with the owner's refusal unit
   ("the whole affected call or answer"); cost: a legitimate echo inside a tool
   result would be refused, so refusal must be per-occurrence, not per-message.
3. *Disambiguate from available inputs only* (conversation, `token_uses`
   occurrence history, the call/result binding already present) — no new API
   fields; cost: needs a discriminating signal that is not "message role".
4. *Mask the collision occurrence as a new real value* — protects the second
   person, but re-masks a legitimate echo and breaks substitute continuity.
Owner must choose among 2/3/4, or record `covered_by` an existing decision.

**`O-CORE-S1-2` — lone surname / given-name fragment of a known person (`C`).**
Same real person, later mention of one part only. Options: (a) always link the
part to the conversation's existing full-name row; (b) link only when the
conversation has exactly one owner of that part; (c) mint a new substitute
(status quo). Contract: one person → one substitute; but a shared surname
between two people in one document must not collapse them.

**`O-CORE-S1-3` — phone prefix authority on the restore leg (`D1`).** Options:
(a) keep the agent's prefix (status quo: real digits under an invented prefix,
no residual); (b) keep the agent's prefix but emit a residual/refusal when the
prefix differs from the real canonical's; (c) replace the invented prefix with
the real canonical's. Contract to preserve: a model that writes a *legitimate*
notation (`8 …`, `+7 …`, ten bare digits) must keep its form; a model that
invents a non-RU prefix must not silently receive a wrong number.

Detection-side option for `B` (no new fork — the owner already decided "protect
all parts"): make a lower-case surname after a personal preposition a NAME
candidate, or require the given name to license the surname; either must be
tested against the business-prose negatives before any patch (`G7`). Any such
change is `K1`/`D1-N` territory, not this task.

## NOT_MEASURED — precise gaps, not "passed"

1. **Non-PII rewrite (`D2`, recorded `c-3`→`c-8`, `3.`→`8.`, `127.10.1965`).**
   Not reproduced. Missing state to attempt reconstruction: the original
   `fanout_pick-017` conversation's vault (all minted values and their order),
   the raw model response bytes before restoration, and the exact answer string.
   The recorded trace preserves only the response-restored output. The property
   held 375/375 on a fresh fixture; that is **not** evidence the class is absent
   in production.
2. **Stream vs whole (`E1`, recorded `long_clinic-006` fake DOB in the delivered
   stream).** Not reproduced in-process: 130/130 chunkings equal. Missing state:
   the host's actual `/unmask_chunk` call sequence (carry/`flush` per chunk), the
   provider's SSE line framing, and whether the delivered reply came from the
   proxy leg or the sidecar leg. What *is* established by reading and by `E2`:
   `StreamDetokenizer` withholds the last ≤64 chars until `flush()`; the
   in-process proxy flushes only on `[DONE]` or on an upstream `httpx` error
   ([proxy.py:505–536](<prototype/pseudex/proxy.py#L505-L536>)); `/unmask_chunk`
   is stateless and the carry is the **caller's**
   ([service.py:812–860](<prototype/pseudex/service.py#L812-L860>)). A stream
   that ends without `flush` is delivered truncated by up to 64 characters.
   End-to-end proxy behaviour was **not measured** (no provider call permitted).
3. **Original causality of N2/N3/P4.** The recorded traces give masked outputs
   and corpus identifiers, not reconstructible vaults. The mechanisms above are
   consistent with the recorded shapes and are deterministic REDs in their own
   right; attributing the original runs to them would be a guess (`G0` forbids
   inferred cause presented as fact).

## Limits of this SPEC

- No product, scorer, corpus, wiki or licensing file was written or patched.
- Substitutes are minted with `secrets`, so concrete strings differ per run. The
  **property verdicts are invariant** across three runs (`A2,B,C,D1` violated,
  exit 4 each; see `determinism-run2.log`, `determinism-run3.log`), and the
  fixture **spec** is hashed (`438f3186…`). The observed state for the logged
  run is captured in `RED.log`.
- No claim is made about recall/precision/PPV, about the whole quality sprint, or
  about production. This SPEC supports `G3` only, and `O-CORE` before `K1`.
