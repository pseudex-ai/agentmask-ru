# M1b revision-2 SPEC — canary readback and masking parity (corrected)

Status: **design/RED corrected; no product or benchmark source patched; `G2` NOT
passed.** This revision answers the independent critical review of
[REVIEW.md](../review-critical/REVIEW.md) and leaves the revision-1 package
(`../SPEC.md`, `../GATE.json`, `../probe_*.py`, `../RED.log`) untouched and
authoritative for what it measured.

- Wave: `quality-sprint-design-red-1`, task `M1b`, write scope
  `work/M1b/revision-2/` only.
- Revision-2 evidence: [revision.log](revision.log),
  [probe_canary_reader_v2.json](probe_canary_reader_v2.json),
  [probe_parity_replay_v2.json](probe_parity_replay_v2.json),
  [legacy_reader_limits.json](legacy_reader_limits.json).
- Commands, exits and output hashes: [revision.log](revision.log). Both probes exit
  **0**; the red reader verdict is asserted inside the probe, not hidden by it.
- Pinned build unchanged: product source `0bfda2363ef1a1d552e2ac093129b1026a86ad68`,
  run `cc3a551f-a8a5-4c0d-b90b-d3db2b26858a` / `v5-sprint-v2-813`,
  capture artifact sha256 `3c42892960088ad08a8cded1b5dc987563cfe4af810d7b8ae283b501e2ceabb7`.
- The two `prototype/bench/agentpii5/answer_restoration*.py` changes observed by
  the reviewer are the **declared parent M1a v2-dev work**, not third-party drift
  and not this task's; revision-2 neither attributes them elsewhere nor writes to
  them.

## 0. Corrections against revision-1 (what was withdrawn, what replaced it)

| revision-1 claim | disposition | corrected statement |
|---|---|---|
| `full_prior_state_replayed` (`len(payloads)==len(have)+1`) as "the entire vault and machine state replayed" | **WITHDRAWN** | It is a **count** comparison, reported as `replayed_payload_count_matches_remaining`. Visible-prefix agreement is not equivalence of token rows/canonical forms, token-use/alias/shown-form records, provenance/cache/history, backend state or RNG state. |
| "the trigger lives in the failing push's own mint, not in the prior transcript/state" | **WITHDRAWN** | **0/4 reproduced; trigger and relevant missing state UNKNOWN.** Failing to reproduce from an incompletely reconstructed state cannot exclude that state as a cause. |
| "two of four prior states were reproduced byte-identically" | **WITHDRAWN (typo + wrong count)** | One case (`derive-008`) had its visible prefix replayed with a matching count; the rest are partial. No state-equivalence claim. |
| `verdict = REPRODUCED if any HarnessError` | **FIXED** | `REPRODUCED_EXACT_BOUNDARY` requires the divergence signature, both saved 60-char prefixes verbatim in the raise, and a recomputed first difference ≥ 60. Seven-control mutation self-test in `probe_parity_replay_v2.json`. |
| `_unique_token` patched per case, never restored | **FIXED** | Original captured once at import, restored in `finally` per case; the probe's exit code asserts it is back in place. |
| recovery docstring "four sweeps converge" | **FIXED** | One greedy pass; empty anchors, non-positive intervals and recovered==raw are exposed as `ambiguous_recovery`; no recovered pair ⇒ `MISSING_PRIMED_STATE`. |
| `payload_*_bytes` from `len(str)` | **FIXED** | `chars` and `utf8_bytes` reported as separate numbers; the proposed limits are byte limits. |
| `0/0` denominator explained as the no-captures branch not consulting the journal | **FIXED** | The journal IS consulted on normal success and on the empty-captures branch. The defect is the earlier read-error return. |
| D1 adds a v2 declared-size block while v1 rows stay under the v1 rule | **FIXED** | The immutable problematic run is **version 1**; a separate bounded **LEGACY v1** path is specified and measured, not a future-writer change. |

## 1. Finding R-A — the canary reader refuses a valid run (unchanged red, corrected numbers)

Measured by `probe_canary_reader_v2.py` (all numbers in
[probe_canary_reader_v2.json](probe_canary_reader_v2.json)):

- **810** physical rows, **95,241,454 B** / **81,514,019** decoded chars;
  **808** rows at or under the engine's `CAPTURE_MAX_ROW_BYTES = 4,194,304`;
  rows **806** (5,531,229 B incl. newline) and **810** (5,470,734 B) are over it.
- Both oversized rows are **schema-valid version-1 captures** (`capture_from_json`
  ACCEPTED), **380** payloads each. Their maxima in BYTES, not characters:
  `text` **36,574 / 35,851 B**, `real_text` **36,592 / 35,852 B**; totals
  ≈2.27 MB per row. The rows are large by **delivery count**, not by one huge
  value, so the row-byte limit refuses the chatty case, not the hostile one.
- The engine reader still answers **`NOT_MEASURED`**, reason
  `...canary.jsonl:806: capture row is over the 4194304 byte bound`, with
  `capture_rows=0`, `intervention_rows=0`, `coverage_known=False` — the `0/0`
  the report published.

**Corrected denominator sentence.** `_expected_capture_keys` (the triple journal)
is read on the normal success path (`payload_canaries.py:955-971`) and on the
empty-captures branch (`:942-952`). The defect is **earlier**: `check_run` calls
`read_captures` first and returns `not_measured(...)` on its `CaptureError`
(`:926-931`) before any denominator code runs, so `not_measured`'s zeros
(`:337-347`) are what the published report carries. The journal names **810
expected I arms**, the artifact holds **810** covered (1.0) and no duplicates —
that denominator exists and is discarded by the early return.

**Lost record vs unreadable archive, separated.** No raw record is lost and no
delivered byte is missing (810/810 parse, 20,201 payloads intact). What is lost
is (a) the *reading* of 808 otherwise-readable rows and (b) the *denominator* in
the published report.

## 2. Design D1 — a bounded, chunk-safe, versioned canary reader (corrected)

Design constraints, in order: do not remove limits; do not rewrite the saved run;
do not degrade a measurement into a clean verdict; **the legacy version-1 rows
must become readable on their own rule**, because the immutable run is v1.

1. **A legacy v1 path, not a future writer.** Version-1 rows carry no declared
   size block. They are read with bounded incremental byte accounting:
   `readline(row_ceiling+1)`, strict UTF-8 decode, JSON parse,
   `capture_from_json`, then per-payload and per-count checks. **The v2 declared
   block is untrusted metadata** and may not be allocated on; a v2 row whose
   declaration disagrees with its bytes is refused (demonstrated on a synthetic
   lying v2 row: verdict `REFUSED`).
2. **Bound the payload, not the row.** Payload `text`/`real_text` and the payload
   count are bounded; the row-byte bound becomes *derived*. Measured maxima in
   [legacy_reader_limits.json](legacy_reader_limits.json): max payload
   **36,592 UTF-8 B**, max payload count **380**, max valid row **5,531,229 B**,
   run **95,241,454 B** of the unchanged **256 MiB** budget. Proposed:
   `max_payload_utf8_bytes = 1 MiB`, `max_payloads = 4096`,
   `max_row_utf8_bytes = 8 MiB`, run budget unchanged at 256 MiB, 1 MiB read
   windows.
3. **Skip, never abort.** A row over a hard bound is skipped with a **named,
   counted** record and the remaining rows are still measured (controls: a
   2,950,000-byte payload row is skipped by name while its two neighbours are
   measured; a >9 MiB hostile row is skipped by the row ceiling).
4. **The denominator survives on every path**, including refusal.
5. **No status softening.** The global verdict stays `NOT_MEASURED`, the parity
   hard fail stays fail-closed, and no partial read may be reported as
   full-coverage quality.

**Diagnostic result (design path, not an accepted reader).** Under the proposed
legacy limits the saved run reads **810/810 rows, 0 skipped, 0 refused, 20,201
payloads** — reported in a **separate namespace** beside the unchanged engine
verdict. It is `DIAGNOSTIC ONLY`: M1c must accept and implement the reader
contract before this can feed any gate, and global full-coverage acceptance
stays blocked while coverage is incomplete.

## 3. Finding R-B — the four divergences, corrected verdicts

The run's 11 exclusions contain **4** production/counting masking divergences
(`tool_chain-037`, `tool_chain-040`, `derive-008`,
`sequential_chain:assistant-002`). Their arm-I records are `_empty_run`
(`state=[]`, `calls=[]`, `substitutes={}`, `request_count=0`); the captures
end at the `tool_args` payload before the failing push.

**Replay result (corrected rule, `probe_parity_replay_v2.json`).**
**0/4 reproduced.** For all four, the visible prefix the replay produced agrees
byte-for-byte with the saved capture prefix; only `derive-008`'s payload count
matches the "one more than replayed" heuristic, which is **not** state
equivalence. The recovered `(real, fake)` pairs (derive-008: 3; the other three:
1–2; no ambiguous recovery) and the saved `tool_args` restore are on disk, but
the token rows, provenance/shown-forms, cache, backend and RNG state of the
failing push are not. **Trigger and relevant missing state remain UNKNOWN**, and
the «one trigger vs four» question stays open.

**Replay harness corrections (all output-local).** Per-case `finally` restore of
`_unique_token`; ambiguity-exposing recovery; the boundary+signature verdict with
its seven-control mutation self-test (an unrelated `HarnessError` such as
`mask_messages вернул не строку` classifies as `UNRELATED_HARNESS_ERROR`, never
`REPRODUCED_EXACT_BOUNDARY`); the candidate loop declared a **bounded search**
with `original_call_identified: false`; the four saved 60-char prefixes within a
case are equal, so the recorded divergence begins at or after character 60 and no
exact original offset is recoverable from the saved artifacts alone.

**Class controls (revision-1, not re-run).** The eight controls are **stateful
sequence checks** run against one shared gateway; they are not an exhaustive
sweep and no "all parity passed" statement follows from them. They must be
re-run with fresh equivalent state per contrast in M1c.

**Missing, exactly** (machine-readable in [../MISSING-STATE.json](../MISSING-STATE.json),
unchanged): the two full compared strings past the 60-char repr; the substitutes
the failing push minted for values first seen in the tool result; its
`shown_forms` rows; the failed arm's transcript/request_count; and for the
multi-hop cases a replayable description of the intermediate hops.

## 4. Instrumentation the next iteration needs (unchanged, benchmark-side)

Persist both compared strings in full (or the first divergence offset plus a
bounded window); persist the minted triples or a per-case mint seed **only if the
narrow boundary in §5 is approved**; keep the failed arm's transcript and request
count whenever a capture row exists; run the same comparison on the other three
cases once their prior mints are recoverable.

## 5. Owner forks — decision coverage, not new policy

No new owner question is opened by this revision. Each fork is mapped to the
decisions that already bound it; only a genuinely new policy would ask.

- **O-M1B-1 (partial rows counted as MEASURED).** *covered_by*: `G2` (nonempty
  denominators, old results immutable, versioned new scope), `G10` (exclusions and
  uncertainty preserved), SPRINT-PLAN §7. Safe default and what this revision
  proposes: whole run `NOT_MEASURED`/incomplete, with an explicitly named
  measured-subset diagnostic — never partial = full-quality PASS. No question.
- **O-M1B-2 (persisting the mint).** *Split, not a blanket request.* A minimal
  private synthetic-run diagnostic that preserves CSPRNG behaviour is an
  engineering proposal for review; persisting real-customer mappings, changing
  production randomness, or any API/storage change is **new policy** and would
  need a separate owner question. This revision proposes nothing that crosses
  that line and opens no question.
- **O-M1B-3 (fail vs record on disagreement).** *covered_by*: `G2`/`G10` and the
  existing hard-fail baseline. Default stays fail-closed with better diagnostics;
  a separate diagnostic-run mode would be a new experimental semantics and only
  then a narrow question. No question now.

## 6. Not claimed

- Not `G2`, not a quality PASS, not a paid GO, not a release; production digest
  `NOT_VERIFIED`.
- The four divergences are not diagnosed; the trigger is `UNKNOWN`.
- The legacy reader is a **design + bounded diagnostic**, not an accepted or
  implemented reader contract; global semantics are unchanged.
- No engine, scorer, benchmark, corpus or run file was changed by revision-2.

## 7. Next step

M1b feeds `M1c` (one benchmark writer) with: the legacy-v1 bounded reader design
and its measured limits, the corrected denominator explanation, the corrected
parity verdict rule and instrumentation list. **No G3/full-package PASS may be
recorded before independent re-review** of these frozen revision-2 artifacts.
