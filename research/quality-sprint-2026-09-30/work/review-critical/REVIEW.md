# Independent critical-wave review — M1b / S1

## Verdict

| Package | Evidence accepted | Package/design verdict | Promotion consequence |
|---|---|---|---|
| **M1b** | **PASS, bounded:** valid-large canary refusal; stored capture population; visible replay-prefix agreement and **0/4** reproduced failures | **REVISE** replay-completeness/causality claims and reader design before acceptance | **G2 NOT_MEASURED/FAIL remains.** No four-divergence closure, no reader-contract freeze, no clean privacy claim |
| **S1** | **PASS, bounded:** independently repeated synthetic A2/B/C/D1 violations, P/C2/E1 controls; E2 demonstrates no-flush behavior | **REVISE** historical boundary/missing-state claims, failure assertions and owner-fork mapping | **Full G3 is not PASS.** Useful RED fixtures may be retained, but K1 still needs accepted design and M1c; D2/historical E1 remain unreproduced |

This review is **not** a product patch, a recall/precision measurement, a gate for release, or a new explanation of the paid run. Requested inherited reviewer target: `gpt-6-astra`; self-identification is not routing proof. No provider/payment/production calls, installs, Git changes, or writes to authors' directories occurred.

Only this report and [EVIDENCE.json](<research/quality-sprint-2026-09-30/work/review-critical/EVIDENCE.json>) were written. The stale `debug-leak` stash recipe was **not used**: the current task forbids modifying the shared worktree.

## 1. Review performed

Read both packages' INPUTS/SPEC/DELTA/GATE and owner questions (M1b embeds them in SPEC/GATE), probe sources and logs; [Lead intake](<research/quality-sprint-2026-09-30/work/WAVE-1-INTAKE.md>); binding owner decisions and relevant goal/plan/wiki clauses. Inspected actual envelope/gateway/capture/streaming paths, not just the researchers' summaries.

Executed one bounded independent Python check, exit **0**:

- Stream-read the original canary JSONL, count physical rows/payloads, validate the two oversized records with the unchanged `capture_from_json`, and call unchanged `check_run`.
- Extract original saved operands for `prompt_rule-005`, `long_clinic-001`, `long_clinic-006`, `fanout_pick-017` directly from archived corpus/arms. Exact content and original physical rows are preserved in review evidence.
- Load S1 definitions via `runpy.run_path(..., run_name='review_import_only')`, **not main or its writing shell script**. Invoke only the in-memory P/A2/B/C/C2/D1/E1/E2 functions, capture their stdout in memory. Their return values reproduce the recorded verdicts.
- Compare **223 source/raw-run/author-artifact hashes before and after that bounded command**: zero changes. A later final check found two **out-of-package M1a** module/test changes; see preservation qualification below. All M1b/S1 review inputs and critical engine/raw files remain unchanged.

A second read-only command inspected the extracted operands and confirmed the raw→restored strings below; exit **0**. No author replay script was rerun into its output directory. M1b parity replay was reviewed statically against its saved output; its own state-mutating monkeypatch was not installed in this reviewer process.

## 2. M1b: what the canary evidence really proves

Independent result:

| Fact | Verified value |
|---|---:|
| Original JSONL rows | **810** |
| Delivered payload records | **20,201** |
| Oversized physical rows | **806, 810** |
| Physical bytes, newline included | **5,531,229 / 5,470,734** |
| Schema validity | **Both accepted**, version 1 |
| Payload count in each oversized row | **380 / 380** |
| Largest individual UTF-8 payload text | **36,574 / 35,851 bytes** |
| Largest individual UTF-8 real-text payload | **36,592 / 35,852 bytes** |
| Current reader | **NOT_MEASURED**, fails at row 806 over **4,194,304** bytes |
| Current coverage metadata on this failure | captured0 / intervention0 / coverage_known=False |

This establishes a **writer/reader admissibility gap on the benchmark's own valid captures**, not that resource limits are inherently wrong or should be removed. The rows grew by many deliveries, not by a single multi-megabyte value. Keeping a hard memory/run ceiling is correct.

**Minor measurement correction:** [probe_canary_reader:103–105,169–175](<research/quality-sprint-2026-09-30/work/M1b/probe_canary_reader.py#L103-L105>) names `len(str)` fields `*_bytes`. Those are character counts, not UTF-8 byte counts. Physical `len(raw)` line/file counts are correct. Use the byte-accurate independent values above for any new resource limit.

**Denominator description:** the journal count is reached on normal success as well as the no-capture path, not only in the latter. The actual defect is the **early read-error return** before journal coverage is populated: [check_run:923–971](<prototype/bench/agentpii5/payload_canaries.py#L923-L971>). Correct the explanation, retain the demonstrated failure.

### M1b-R1 — reader proposal does not yet satisfy its own legacy acceptance

[Proposed design:152–187](<research/quality-sprint-2026-09-30/work/M1b/SPEC.md#L152-L187>) adds version-2 declared sizes, while saying version-1 rows remain under the version-1 rule. But the immutable problematic run is **version1**. If the old4MiB rule remains unchanged, a v2 writer cannot make these existing two rows readable. The acceptance claim “saved run measurable810/810” therefore needs an explicit **versioned evaluator/legacy reader path**, not a rewrite of the old JSONL or merely a future writer change.

Also, a declared size block is untrusted metadata. A reader cannot assume it occurs before large text in an arbitrary JSON object or allocate based solely on the declaration. Specify and test actual incremental byte accounting, nesting/schema checks, per-payload/count bounds, total-run bound and hard row ceiling. M1b has a proposal, not an implemented bounded parser.

**Acceptable next design:** preserve original files and original historical report; build a new evaluator/report version that reads these schema-valid legacy bytes within explicit measured resource limits. Keep expected/captured/read/measured/unmeasured populations distinct. Malformed/unsupported/over-hard-bound rows remain named failures or unmeasured coverage, never successes.

A partial diagnostic may be useful, but **do not change the existing global MEASURED/quality-gate semantics merely to make the run appear complete**. If a new partial status is desired, it must be explicit and cannot pass the full-coverage gate. The current owner decisions already require visible uncertainty and preserved denominators; implementation can retain global NOT_MEASURED plus partial diagnostics without reopening that principle.

## 3. M1b: replay-prefix agreement is not replayed state

### M1b-R2 — reject “full prior state” and the inferred failing-mint cause

The boolean [full_prior_state_replayed:209](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L181-L216>) is computed as:

```python
len(payloads) == len(have) + 1
```

The adjacent `state_byte_identical` check compares visible capture names/text/real_text for the replayed prefix. These facts prove **visible-prefix agreement**, not equivalence of:

- token rows and canonical forms;
- token-use/alias/shown-form records;
- provenance/cache/history snapshots;
- backend state;
- random choices/RNG state;
- the exact unrecorded failing tool result and the mints it provoked.

[Mint priming:141–153](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L141-L155>) directly returns inferred saved surfaces for selected pairs. It bypasses the normal `_unique_token` choice and does not reconstruct all the state above. For `derive-008`, **4 visible payloads plus the saved argument match**, and the recorded restored arguments match. That is useful. It is not “the entire original vault and machine state replayed”.

Therefore [SPEC:106–111](<research/quality-sprint-2026-09-30/work/M1b/SPEC.md#L106-L111>) must **not** conclude “the trigger lives in the failing push's own mint, not in the prior transcript/state.” Failure to reproduce from an incompletely reconstructed state cannot exclude that state as a cause. Correct conclusion: **0/4 reproduced; trigger and relevant missing state unknown**. SPEC194 also says “two of four” states, contradicting its own1/4 count; remove both the numerical typo and the unjustified exclusion claim.

### M1b-R3 — replay harness needs isolation and stronger verdict checks

1. **Cross-case monkeypatch chain.** `primed_vault_class` captures the current `Vault._unique_token`; the main loop installs a new patch for each case and never restores the original ([141–153](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L141-L155>), [254–262](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L254-L262>)). Later fallbacks can consult earlier cases' saved maps. Preserve the unmodified function once, restore it in `finally` per case/attempt, and prove order independence. This is a local-process probe defect, not a persisted engine edit.
2. **Mapping recovery assumptions are not certified.** `prime_from_captures` assigns message indexes by capture order and uses first matching literal anchors/fallback deltas ([111–137](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L111-L138>)). Empty/repeated anchors, non-user messages and overlapping/partial item masks require validation. Byte-identical visible output does not prove a unique underlying mapping. Its docstring claims four converging sweeps, but the implementation is one pass; fix the description and expose ambiguity.
3. **A HarnessError is not necessarily the target divergence.** `verdict=REPRODUCED` accepts any `HarnessError`; matching saved prefix is recorded only later and is not part of the success predicate ([219–227](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L219-L227>), [267–290](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py#L267-L290>)). Other exceptions get the misleading `NO_DIVERGENCE_THIS_TOOL` label. Keep expected divergence, unrelated harness failure, setup failure and true no-divergence separate.
4. **Candidate tool loop is not original call reconstruction.** The replay tries every declared tool with saved arguments. It does not establish which tool was the original failing call. Keep this as bounded search and identify actual call/result provenance before claiming exact replay.
5. **Eight controls are stateful sequence checks, not an exhaustive sweep.** [compare](<research/quality-sprint-2026-09-30/work/M1b/probe_parity_mechanism.py#L52-L67>) can mint into one shared gateway while controls run sequentially. Use fresh equivalent state for independent contrasts, and validate the “echo” surface actually belongs to the saved mapping. No statement “all parity passed” follows from eight equal controls.

These corrections do not invalidate the current **0/4 reproduced** report. They prevent a future unrelated failure or order-dependent artifact from being counted as the sought mechanism.

## 4. S1: accepted REDs and required corrections

The independent bounded invocation reproduced:

| Probe | Result | Accepted interpretation |
|---|---|---|
| P | HOLDS | Exact round trip and fixed-point behavior for this fixture |
| A2 | VIOLATED | Constructed same-conversation tool-result collision yields clear surname and/or wrong-person restoration |
| B | VIOLATED | This concrete lower-case two-part name gets LOC surname and leaves given name unprotected |
| C | VIOLATED | Under the constructed prior row, later whole/part outputs in c2 have different surnames |
| C2 | HOLDS | Clean-state counter-control for C |
| D1 | VIOLATED | Agent-written changed prefix survives while real subscriber digits are substituted and no residual is reported |
| E1 | HOLDS | These5 surfaces ×26 chunkings =130 comparisons match whole restoration |
| E2 | CONTRACT_GAP in author harness | Omitting required final flush withholds the tail; pure behavior reproduced, not a historical mismatch explanation |

Author records three repeated runs with the same violated set. That is repeated empirical evidence, **not a proof of deterministic behavior for every future random mint**. D2 was not rerun here: the author’s0/375 is kept as a bounded non-reproduction, not a clean class verdict.

### S1-R1 — historical raw input/response is present; correct missing-state inventory

The package repeatedly says original raw N2/P4/D2 is unavailable. Direct archived records contradict this:

- `prompt_rule-005` has source user message1 in archived corpus: `привет оформите доставку на битюкова зинаида телефон 8 926 123 45 67 да и 6 кабинет`. S1 uses a **different phone** in its reconstructed phrase. Its B RED is valid for its own input, not an exact replay. The source-name span and original model-visible payload were already verified in [all15 follow-up](<research/quality-sprint-2026-09-30/followup/name15-verified/FINDINGS.md>).
- [long_clinic-001, arms row49](<prototype/bench/runs/2026-09-30/v5-sprint-v2-813/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.arms.v5.jsonl#L49>): `/v5/model_trace/responses/6`, `/7`, `/12` retain raw `+7 929 542-23-19` and restored `+3 929 542-23-19`.
- [fanout_pick-017, row607](<prototype/bench/runs/2026-09-30/v5-sprint-v2-813/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.arms.v5.jsonl#L607>): response13 retains raw `23.10.1965` and `c-3`, restored `127.10.1965` and `c-8`.
- [long_clinic-006, row60](<prototype/bench/runs/2026-09-30/v5-sprint-v2-813/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.arms.v5.jsonl#L60>) retains `reply_raw`, delivered `reply`, `reply_whole`, and `stream_mismatch=true`.

Missing full historical vault/provenance/mint order can still prevent exact replay. **Missing state is not missing raw text.** Correct [SPEC:76–84,96–105,149–174](<research/quality-sprint-2026-09-30/work/S1/SPEC.md#L76-L105>) and its copied source/log annotations accordingly, preserving the original evidence revision.

### S1-R2 — D1 is a different input-side mutation, not the historical P4 cause

Author D1 explicitly constructs **`+3 <fake digits>` before restoration**, then observes **`+3 <real digits>`** with residual empty ([source:350–384](<research/quality-sprint-2026-09-30/work/S1/s1_probes.py#L350-L384>)). Historical P4 instead has **`+7 <fake digits>` → `+3 <same recorded fake-looking digits>`** at the restoration boundary. Different preconditions and byte transitions: the synthetic RED cannot explain or close P4.

Retain D1 as a separate numbered property: a mutated numeric identity must not silently expose real subscriber digits under an unrelated country code. Do not describe every non-RU prefix as intrinsically invalid—real international prefixes exist. The relevant issue is mismatch to the known phone identity and approved re-notation rules.

Its current disjunction “restores to canonical **or** visibly refuses” is too loose as a final acceptance test: canonical replacement can pass this check while violating the owner’s prohibition on silent repair of explicitly written values. Add separate checks for approved `7↔8`/bare notation and truly changed country identity; keep raw mutation, value, form and residual/refusal independent.

### S1-R3 — historical streaming path is known and flushes

The run is in-process. [harness:512–536](<prototype/bench/agentpii5/harness.py#L512-L536>) fixes `STREAM_CHUNK=17`, feeds a single `StreamDetokenizer`, **calls flush**, and compares with `unmask_text(raw,vault)`. [answer_leg:560–580](<prototype/bench/agentpii5/harness.py#L560-L580>) uses this directly for a streaming case.

Thus proxy-versus-sidecar uncertainty, provider SSE framing and unknown host flush sequence are **not missing inputs to the recorded benchmark mismatch**. The exact historical vault state still is. Replay should start from the saved raw answer, the known17-character chunk sequence and flush, then identify the missing state—not require another paid provider run.

E2’s pure omission of flush demonstrates the documented carry contract. It is not itself a valid engine RED requiring the buffer to emit without flush. Static [proxy:488–536](<prototype/pseudex/proxy.py#L488-L536>) does suggest a separate abrupt-EOF-without-`[DONE]` concern. That must be tested with an **offline fake upstream/ASGI harness**, not asserted as the cause of this in-process benchmark failure and not blocked on paid network permission.

### S1-R4 — strengthen causality, controls and G3 wording

- A2 establishes a constructed unsafe boundary. The static fact that `recorded` is handed to tool messages ([envelope:1605–1653](<prototype/pseudex/envelope.py#L1605-L1653>)) is not a complete proof that **all available inputs are incapable of distinguishing** an external new-real document from an echo. That information audit is explicitly required by the owner before new API proposals. Do not assert indistinguishability without paired input-equivalence proof.
- A2 reuses one context/vault across its three variants. Isolate or explicitly order the variants; distinguish “clear surname+wrong restoration” from “merged given name”. The bare variant does **not** overwrite a given name, despite the summary wording implying all three do.
- A1/A3 test foreign-conversation paths, not all backward/forward collision orders in one conversation. A1 reverses the original `fsur`, not necessarily the newly emitted second-person fake; add a true second-person round trip before counting this as two-sided safety acceptance.
- B’s final detector output does **not** establish that `зинаида` was “never born as a candidate”. It may have been absent or removed by suppression/resolution. Instrument recognizer→suppress→resolve separately before naming that internal cause.
- C is a useful state-dependent construction; strengthen its truth predicate beyond substring `Битюкова` in both restored strings, and avoid vacuous success when `_find_fake` fails or a fragment is empty. Bind explicit fixture identity and assert required nonempty setup. A source-order/cross-conversation variant is still needed before claiming the whole identity class covered.
- `GATE.json` currently says scoped G3PASS while disputed choices and independent review are pending. [G3](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L147>) includes accepted disputed design and reproducibility with justified causes. Record **evidence accepted for specific probes**, not full package G3PASS. Nonreproduced D2/historical E1 remain `NOT_MEASURED` for reproduction; their current fixture checks were measured, so do not confuse this with “never executed”.

## 5. Decision deduplication: what to ask and what is already binding

| Proposed question | Existing decision coverage | Review disposition |
|---|---|---|
| O-CORE-S1-1: refuse / use existing provenance / remask / status quo | [Remaining:14–15](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L14-L15>), [Owner:40](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L40>) | **Do not re-ask as a free policy choice.** First use/prove existing provenance; if unresolved, refuse the whole affected operation. Status quo is already rejected; blind re-mask that breaks echoes is not approved. Only a demonstrated information insufficiency or new protocol need creates a new owner fork |
| O-CORE-S1-2: always link / uniquely link / new fake | [Owner:37](<research/quality-sprint-2026-09-30/OWNER-DECISIONS.md#L37>), [wiki:851–864,883–900](<wiki/INVARIANTS.md#L851-L900>) | **Already constrained:** same-person whole/parts consistency, same conversation and unique proven owner; shared-name ambiguity cannot collapse people. Always-link and known split identity are not equal valid alternatives. A genuine counterexample to these joint rules may require a new question |
| O-CORE-S1-3: changed phone prefix | [Remaining:16–17](<research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md#L16-L17>), [wiki:603–619](<wiki/INVARIANTS.md#L603-L619>) | **Principles already constrain it:** preserve legitimate notation, do not silently repair a changed numeric identity, name unresolved near-miss and refuse unsafe delivery. Separate exact country-code equivalence from formatting; only an explicit proposed new equivalence/exception requires owner choice. Do not ask again whether known wrong-person/value output is allowed |
| O-M1B-1: partial rows counted as MEASURED | G2/G10 preserve denominators, exclusions and uncertainty | **New status semantics require approval only if actually proposed.** Safe default: whole run unmeasured/incomplete with explicitly named measured-subset diagnostics. Never partial=fullqualityPASS. Current task can design reading of both valid legacy rows without this detour |
| O-M1B-2: record failing mint state | Private benchmark already stores synthetic real/fake data; original artifacts immutable; no production logging permission | **Split the question.** Minimal private synthetic-run diagnostic metadata preserving CSPRNG behavior is an engineering proposal for review, not necessarily a new privacy policy. New persistent real-customer mappings, replay seeds affecting production randomness, or API/storage changes do require separate approval. Show exact fields, retention/visibility and reproduction sufficiency; do not ask blanket permission to “persist real values” |
| O-M1B-3: continue arm after parity disagreement | [Plan G2/G10](<research/quality-sprint-2026-09-30/SPRINT-PLAN.md#L146-L154>) and existing hard-fail baseline | **A real change of experimental semantics if desired.** Keep fail/excluded behavior by default and improve failure diagnostics. Continuing the arm cannot be smuggled into a reader fix or used to reduce exclusions; ask a narrow owner question only if a separate diagnostic-run mode is needed |

These mappings do not invent new owner answers. They identify `covered_by_decision_ids` constraints for the parent’s gate record. Unchosen algorithms still need technical evidence and independent review; existing policy does not make every proposed patch correct.

## 6. Safe next implementation sequence

1. **Correct these packages’ evidence descriptions and freeze revised inputs.** Preserve original reports; create explicit corrections rather than erasing the initial unsupported claims.
2. **M1b reader:** write the legacy-valid-large/invalid/over-hard-limit/missing-row/duplicate/version/metadata-mismatch tests first. Specify actual resource accounting and journal coverage on every failure path. A new report version can expose partial diagnostics, but global/fullquality acceptance stays blocked when coverage is incomplete.
3. **M1b parity diagnostics:** retain fail-closed comparison; capture exact differing boundary and enough state in a private synthetic benchmark artifact to distinguish visible-prefix reproduction from full state. Restore monkeypatches per case. Re-run the four saved surfaces offline only with an honest reconstruction manifest. If the failure still does not reproduce, leave it open.
4. **S1 core fixtures:** isolate A2 variants and prove the intended source/identity; strengthen C nonempty/identity assertions; separate synthetic prefix mutation from archived boundary corruption; use original raw inputs that already exist. No new provenance host API unless existing information is demonstrably insufficient.
5. **S1 streaming/non-PII:** use original raw response plus known harness chunk17+flush; state reconstruction remains explicit. Test proxy abrupt EOF separately with an offline upstream fixture. Expand non-PII collisions deliberately, not merely hope 25 random vaults hit the archived pattern.
6. **Independent re-review** on frozen corrected sources/tests/spec before package acceptance; then M1c and K1 only when their other prerequisites/owner checkpoints are actually satisfied. No engine/scorer change was made by this reviewer.

## 7. Preservation and confidence

Independent evidence shows eight bounded S1 function outcomes and original archived operands, not a full replay of all historical failures or a broad production evaluation. All **223** hashes matched before and after the bounded probe command. The later final recheck initially exited1 because two files outside these reviewed packages had changed: `prototype/bench/agentpii5/answer_restoration.py` and `prototype/bench/agentpii5/test_answer_restoration.py`. They were included only because the baseline manifest covers the wider sprint; neither is read or executed by these M1b/S1 probes. The remaining **221** hashes—including all M1b/S1 author artifacts, critical engine dependencies and original paid-run files—still match. The parent was notified; no original was rewritten by this reviewer and the discrepancy is preserved in the evidence JSON. This is not a claim that the entire workspace stayed frozen while the Lead worked independently on M1a.

The evidence JSON retains exact observed synthetic values and minimal archived fields with original row numbers; it is private benchmark evidence, not a public dataset.

**Bottom line:** keep the useful canary RED and four synthetic failure properties. Reject the unproved “full prior state / failing-mint cause”, correct missing-raw and streaming-transport claims, and avoid reopening already settled policies. Both packages need revision before full design-gate promotion; the engine has not become better merely because these measurements were produced.
