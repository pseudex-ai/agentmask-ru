# M1b technical SPEC — canary readback and masking parity (design/RED)

Status: **RED delivered, design proposed, no product patch**. Gate `G2`-input only.
This document does not imply that the sprint's quality goal, the engine, the
release candidate or production is green.

- Wave: `quality-sprint-design-red-1`, task `M1b`, write scope
  `research/quality-sprint-2026-09-30/work/M1b/` only.
- Precondition: [B0 GATE](<../B0/GATE.json>) `G1` **PASS for local/design scope**,
  [B0 REVIEW](<../B0/REVIEW.md>) durable and independent. Production artifact
  remains `NOT_MEASURED`; `RG` release-A/B stays blocked on it.
- Source: product pinned at `0bfda2363ef1a1d552e2ac093129b1026a86ad68`; HEAD
  `890c508` is research-only and `git diff` of the product paths between the two
  is empty (hashes in [INPUTS.json](<INPUTS.json>)). Bundle identity
  `2a07cebae2b050ec` / `01c19f4689450b54694b7aaa4070cbaf695efc3e98f0b59471486392a0348206`,
  identical to B0's record.
- Evidence: [RED.log](<RED.log>), [probe_canary_reader.json](<probe_canary_reader.json>),
  [probe_parity_replay.json](<probe_parity_replay.json>),
  [probe_parity_mechanism.json](<probe_parity_mechanism.json>),
  [MISSING-STATE.json](<MISSING-STATE.json>).
- B0's boundary is inherited unchanged: evidence commit `890c508` preserves work; it
  does not certify production, quality or the container.

## 1. Owner decisions that bind this task

| decision | source | what it fixes here |
|---|---|---|
| Gate `G2` requires old counters preserved, new statuses and denominators **named**, deliberate corrections in a **new version**; «100 % from an empty denominator» is a failure | [SPRINT-PLAN §7](<../../SPRINT-PLAN.md>) | the reader's `NOT_MEASURED` on 810 present rows is a G2 failure; `0/0` must be replaced by a named denominator |
| M1b must show «reader of large valid canary records without losing them; full exclusion inventory; exact 4 divergence reproductions»; engine patch must not hide inside a reader change | [GOAL-BRIEF §5](<../../GOAL-BRIEF.md>) | two separate deliverables: the reader RED+design, and the parity RED+missing-state |
| Unproven root cause is `UNKNOWN`, never an invented cause | [FIRST-WAVE-SCOPES](<../FIRST-WAVE-SCOPES.md>) | C3's controls did not pin the trigger, so the trigger is recorded UNKNOWN |
| Old raw outputs are immutable; no blanket revert/reset/stash; corpora and runs are read-only | [SPRINT-PLAN §11](<../../SPRINT-PLAN.md>) | the old run is read; nothing is rewritten |
| New provenance API fields are **not** allowed without proven insufficiency plus a separate owner question | [REMAINING-DECISIONS §2](<../../REMAINING-DECISIONS.md>) | the parity recommendation is instrumentation inside the benchmark, not a gateway/API change |
| Owner forks that are still open stay `OWNER_PENDING` | [SPRINT-PLAN §7](<../../SPRINT-PLAN.md>) | §5 below |

## 2. Requirement

**R-A (readback).** A canary archive whose rows were written by the benchmark
itself is either measured or refused for a *named, arithmetic* reason; a single
row's size must not turn a whole run into «не измерено», and a refusal must not
erase the denominator the run's own journal names.

**R-B (parity).** The two masking implementations the gateway compares on every
push (`envelope.mask_messages` — production — and `score._mask_message` — the
counting instrument) must agree on every delivered message, or the disagreement
must be reproducible from persisted artifacts and diagnosed to a mechanism.

## 3. Finding R-A — the canary reader refuses a valid run

Measured on the run (all numbers in [RED.log C1](<RED.log>)):

- 810 rows, 95 241 454 B, 0 unparsable, 0 duplicate keys, **808 rows at or under
  the 4 194 304 B row bound**; rows 806 (5 531 229 B) and 810 (5 470 734 B) are
  over it, and both are **schema-valid version-1 captures** (`capture_from_json`
  ACCEPTED, 380 delivered payloads each, 20/19 manifest canaries).
- The rows are large by **delivery count**, not by one huge value: the biggest
  individual payload text stays small. `CAPTURE_MAX_ROW_BYTES` therefore refuses
  the *chatty* case, not the hostile one.
- `read_captures` raises on the first oversized row, so the whole pass dies:
  `check_run` → `NOT_MEASURED` with `capture_rows=0, intervention_rows=0`.
- The triples journal names **810 expected I arms**; the file holds all 810
  (`1.0` coverage, 0 missing, 0 unexpected). The `0/0` denominator printed by the
  report is a *second* defect: the refusal branch returns
  `not_measured(problem)` while the «no captures» branch fills the denominator
  from `_expected_capture_keys`.
- A synthetic control (one valid capture, one over-bound payload) refuses the same
  way, so the refusal is arithmetic and size-driven, not a property of this
  archive.

**Lost record vs truncated display, stated separately.** No raw record is lost and
no delivered byte is missing — 810/810 rows parse and 20 201 payloads are intact.
What is lost is (a) the *reading* of 808 readable rows because 2 are refused and
(b) the *denominator* in the published report. A truncation of the displayed
reason to 60 characters in the excluded-case log is a third, unrelated display
limit; it is why the parity evidence in §4 had to be recovered from a different
artifact.

## 4. Finding R-B — the four divergences, and the state that is missing

The run's 11 exclusions contain **4** production/counting masking divergences:
`tool_chain-037`, `tool_chain-040`, `derive-008`, `sequential_chain:assistant-002`.
`RealGateway._push` raises when production's `mask_messages(transcript)` and
`score._mask_message(text)` disagree on the message being pushed.

**Recovered (this is the new evidence).** The arm-I records in
`<run>.arms.v5.jsonl` are `_empty_run` — `state=[]`, `calls=[]`,
`substitutes={}`, `request_count=0` — so the transcript and the calls are gone and
only the 60-character prefix pair survives. But `GatewayV5(capture=True)` appended
every payload at delivery, and the triple appended that capture **even when the
arm failed** (`harness.py:1343`). Each of the four captures therefore ends at the
`tool_args` payload that the failing `push_call` consumes: the exact pre-failure
transcript, every user message reached, and the arguments the model wrote are on
disk. This is extracted into [MISSING-STATE.json](<MISSING-STATE.json>) and
replayed in [probe_parity_replay.json](<probe_parity_replay.json>).

**Replay result.** `derive-008` is the one case with no intermediate tool hop, and
there the prior state is replayed **in full and byte-identically** (4 replayed
payloads + the saved `tool_args` = all 5), including a restore of its tool
arguments to the saved real values; its three minted pairs (NAME, DOB, PHONE) are
recovered from the delivered bytes and primed into the vault.
`sequential_chain:assistant-002` and `tool_chain-037/040` replay their prefix
byte-identically (the system push and the user pushes before the first tool call)
but not in full: their captures hold 1/8/8 intermediate tool results whose
delivered bytes are on disk while the call that produced them is not, so this
probe does not rebuild those hops.

**The failure does not reproduce** — 0/4, with every declared tool of each case
tried. For `derive-008`, prior state is byte-identical and the failing push still
agrees under freshly minted substitutes. Therefore the trigger lives in the
failing push's own mint, not in the prior transcript, and it stays **UNKNOWN**.
The other three add nothing to that conclusion, because their prior state is only
partially replayed; that limitation is stated rather than smoothed over.

**What is missing, exactly** (machine-readable in `MISSING-STATE.json`):

1. the two masked outputs of the failing push past character 60 (the raise keeps
   only a 60-character repr);
2. the substitutes the failing push minted for values first seen in the tool
   result — `pseudex/vault.py` mints through `secrets`, no mapping is persisted,
   and the capture stops before that push;
3. any `shown_forms` row the failing push's own restore would write;
4. the failed arm's `transcript` / `request_count` (`_empty_run` discards them
   although a capture row for the same push already exists on disk);
5. for the multi-hop cases, a replayable description of the intermediate tool
   hops — the capture has their delivered bytes but not the call that produced
   them, which is why only `derive-008`'s prior state is replayed in full.

**Class controls** ([probe_parity_mechanism.json](<probe_parity_mechanism.json>)):
a new value, a no-PII negative, a repeat of a substitute, four fragment shapes and
the whole real name again — eight controls, none makes the two implementations
disagree on `derive-008`'s exact state. The two functions *are* different
(production snapshots its echo record at pass start and has a call-scoped
`_reserve_echoes` leg; the scorer has no call association, reads the vault live,
and derives its LOC cover set from the pieces it kept) — but that difference is
not by itself sufficient, and the probe does not pretend it is.

**Instrumentation the next iteration needs** (benchmark-side; not a gateway/API
change, so no owner fork on API is opened):

- persist, per push, both compared strings *in full* (or the first divergence
  offset plus a bounded window) instead of a 60-character repr;
- persist the minted `(entity_type, real, fake)` triples of a push that raises, or
  a per-case mint seed, so a replay can be byte-exact;
- keep the failed arm's transcript and request count whenever a capture row exists;
- run the same comparison on the *other* three cases once their prior mints are
  recoverable, to tell «one trigger» from «four triggers».

## 5. Design D1 — a bounded, chunk-safe, versioned canary reader (proposal)

Design constraints, in order: do not remove limits; do not rewrite the saved run;
do not silently degrade a measurement into a clean verdict.

1. **Bound the payload, not the row.** A row's size is the sum of its payloads.
   Bound each payload's `text`/`real_text` (`CAPTURE_MAX_PAYLOAD_BYTES`) and the
   payload count (`CAPTURE_MAX_PAYLOADS`); a row is admissible iff its declared
   payloads each fit and the count is sane. The row-byte bound becomes *derived*
   (`payload_count_bound × payload_bound × overhead`), never an independent
   constant that a legitimate chatty case trips first.
2. **Chunk-safe read.** Read a row in bounded chunks; before materialising it,
   decide from the **declared** size block (`payload_count`, `max_payload_bytes`,
   `total_text_bytes`, `row_bytes`) whether it fits. A row that does not fit is
   *skipped with a counted, named record* — never a whole-run abort.
3. **Version dispatch, no lenient read.** `CAPTURE_VERSION` 2 carries the declared
   size block plus a per-row digest of the payload texts. An unknown version is
   `NOT_MEASURED` (as today). A row whose declared sizes disagree with the bytes
   it holds is refused, not co-erced. Version-1 rows stay readable under the
   version-1 rule so the saved run is **not** rewritten.
4. **The denominator survives.** `CanaryReport` gains named counters
   `measured_rows`, `skipped_rows`, `captured_rows`, `intervention_rows`,
   `coverage_fraction`. Coverage comes from the triples journal on **every**
   path, including the refusal path (today only the empty-captures branch does
   it). «Measured 806 of 810, 4 skipped» is a different, legible fact from
   «NOT_MEASURED 0/0» and from «clean».
5. **Ceiling stays.** The run bound (256 MiB) and a hard per-row ceiling remain;
   the change is which limit is primary, not that limits exist.
6. **No engine work in this change.** The reader is a benchmark artifact; an engine
   patch must not ride inside it ([GOAL-BRIEF §5](<../../GOAL-BRIEF.md>)).

Acceptance for D1 (to be run in M1c, after this design is reviewed):

- the saved run becomes measurable with the journal's denominator, e.g.
  `MEASURED, captured 810/810, skipped 0`, or an explicit `MEASURED (partial)`
  with the skipped rows named;
- one over-bound *payload* in an otherwise valid row is refused by a reason that
  names the payload, and the other rows are still measured;
- a row whose declared sizes disagree with its bytes is refused;
- a mutation that removes the payload-count bound is red;
- unknown version and empty herd stay `NOT_MEASURED`.

## 6. Not claimed

- Not the entire quality goal, not a quality PASS, not a paid GO, not a release.
- Production digest remains `NOT_VERIFIED`; the release-A/B gate remains blocked.
- The four divergences are **not** diagnosed to a root cause; the trigger is
  `UNKNOWN` (two of four prior states were reproduced byte-identically, which is
  what makes «not the prior transcript» a fact rather than a guess).
- The reader design is a proposal; no product or benchmark source was changed in
  M1b.

## 7. Open owner forks (OWNER_PENDING)

- **O-M1B-1 (metric semantics).** When a row must be skipped, is the run
  `MEASURED` with a named partial denominator, or `NOT_MEASURED`? G2 forbids
  «100 % from an empty denominator» and the plan forbids «excluded turned into a
  success»; both readings are defensible, so the owner picks.
- **O-M1B-2 (persisting the mint).** May the benchmark persist the
  `(real, fake)` pairs (or a mint seed) that today exist only inside delivered
  bytes, so a parity failure is reproducible? This changes benchmark artifacts,
  not engine behaviour, but it is a new persisted record of real values.
- **O-M1B-3 (fail vs record).** Should a production/counting disagreement fail the
  arm (today) or be recorded as a measurement and let the arm continue? The
  current raise is what makes the four cases excluded instead of quantified.

Until these are answered, D1 is a design and M1c must not freeze a reader contract
that presumes one of the three.

## 8. Next step

M1b feeds `M1c` (one benchmark writer) with: the reader defect and its design, the
parity RED and the instrumentation list, and the owner forks above. No engine,
scorer, corpus or run file is touched by M1b.
