# E07 chains/repeats/corrections/memory/two-entities — independent re-check

Date: 2026-09-28 · Reviewer: independent (did not author the implementation)
Scope: `test_chain_repeat_correction_memory_two_entities` added to
`prototype/bench/agentpii5/test_harness_stream.py`. Read-only on code; one evidence
file (this one) written. Engine and `harness.py` were NOT touched by this change.

## Verdict

**ACCEPTED_FIX** — the test pins E07 through the real gateway path and asserts the
RESTORED value (not the minted substitute); the non-vacuity flip turns it red. Two
non-blocking gaps are recorded at the bottom (missing `load_dev_bundle()` in the
check itself; the `correction` sub-check is a necessary condition, not a unique pin).

## 1. Commands and exit codes (from `prototype/`)

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_harness_stream
#   chain_repeat_correction_memory_two_entities: PASS
#   harness_stream: PASS
#   exit 0

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_harness
#   only_harness_imports_pseudex: PASS   (the harness-only-imports-pseudex guard)
#   ... all checks PASS ...
#   harness: PASS
#   exit 0
```

## 2. Independent reproduction — the five properties are REAL

I dumped the case, the 8 actual calls, and every `actual_events` leaf with the
bundle loaded. The script drives `GatewayV5` → `GatewayHooks` → `seed_backend_v5`
through the production mask→restore→mock→record path (`hooks.tool` calls
`gateway.restore_arguments(written)` then `backend.call(name, restored)`), echoes
the gateway-minted substitutes, and asserts `restored` (the real value), not the mint.

Declared hops (idx : kind/owner/item tool path source_hop):

```
0 IN/user p_msg1 · 1 IN/user p_msg2
2 OUT/tool_arg p_msg1 crm_find_contact query.phone src=0
3 IN/tool p1s crm_find_contact contacts[].phone src=-1        ← find_in
4 OUT/tool_arg p1s notify_sms number src=3                    ← THE CHAIN HOP
5 OUT/tool_arg p_msg2 crm_find_contact query.phone src=1
6 IN/tool p2s crm_find_contact contacts[].phone src=-1
7 OUT/tool_arg p2s notify_sms number src=6
```

Actual calls (seq : tool → restored.number, residual.number, turn) — `written.number`
is the substitute, `restored.number` is what the backend received:

```
1 crm_find_contact  (—)                          turn1
2 notify_sms  +79566147640 → +79164021187  res=None  turn1   ← p1s (first chain)
3 crm_find_contact  (—)                          turn1
4 notify_sms  +79422418972 → +79261234567  res=None  turn1   ← p2s
5 notify_sms  +79566147640 → +79164021187  res=None  turn1   ← repeat
6 notify_sms  +79422418972 → +79261234567  res=None  turn1   ← wrong correction
7 notify_sms  +79566147640 → +79164021187  res=None  turn1   ← right correction
8 notify_sms  +79566147640 → +79164021187  res=None  turn2   ← memory
```

`actual_events` notify_sms.number events (seq/turn/item/identity/restored):

```
2 t1 p1s i1 → +79164021187 (matched, value_ok, form_ok)
4 t1 p2s i2 → +79261234567 (matched)
5 t1 p1s i1 → +79164021187 (matched)
6 t1 p2s i2 → +79261234567 (matched)
7 t1 p1s i1 → +79164021187 (matched)
8 t2 p1s i1 → +79164021187 (matched)
```

Property-by-property:

- **(i) chain link `source_hop==3` names the IN/tool `crm_find_contact.p1s` hop.**
  CONFIRMED: `chain_hop` is hop idx 4 (OUT/tool_arg notify_sms.number, `call_ordinal==0`,
  item p1s); `case.hops[4].source_hop == 3` → `case.hops[3]` is IN/tool
  `crm_find_contact`, item `p1s`, path `contacts[].phone`. The link is correct.
- **(ii) first actual notify crossing attributed to p1s, restores +79164021187.**
  CONFIRMED: `min(numbers, key=call_seq)` = seq 2, item p1s, identity i1,
  restored `+79164021187`, `value_ok` and `form_ok` both True.
- **(iii) repeat: one `number` event per call, distinct call_seq.** CONFIRMED:
  6 notify_sms calls (seq 2,4,5,6,7,8) → 6 `number` events with 6 distinct call_seq.
  The repeat (seq 5, same written number as seq 2) is a second event, never merged.
- **(iv) correction: right crossing later than wrong.** CONFIRMED as written:
  wrong = p2s/turn1 = {seq 4, 6} (max 6); right = p1s/turn1 restored ONE = {seq 2,5,7}
  (max 7); 7 > 6. (See gap B below — the condition is necessary, not unique.)
- **(v) memory: turn-2 crossing is p1s and restores the turn-1 value.** CONFIRMED:
  seq 8, turn 2, item p1s, restored `+79164021187`.
- **(vi) i1/i2 never swap; no fake reaches the tool.** CONFIRMED: i1 events all
  restore `+79164021187`, i2 events all restore `+79261234567`; every
  `call.restored.number` ∈ {ONE, TWO} and every `call.residual.number` is None.

The assertion rests on `restored`, not on `written`: the script echoes the minted
substitutes (`+79566147640`, `+79422418972`) and the checks demand the RESTORED
value equals the real phone — so the gateway's restoration leg, not the mint, is
what is measured. This is exactly the "without substituting the agent's action
choice for the gateway eval" requirement.

## 3. Non-vacuity (in a /tmp copy, repo untouched)

Flipped `source_hop` of hop idx 4 from 3 → 6 in a `/tmp` copy of the file:

```
FLIPPED E07 VERDICT: FAIL
  - source_hop 6 ведёт не на IN/tool crm_find_contact.p1s, а на Hop(...
        item_id='p2s' ... path='contacts[].phone' ...)
exit 1
```

The check goes RED with the correct cause (chain link now points at p2s, the other
entity). `actual_events` is documented to not read `case.hops`, so the flip tests
exactly the declared-link assertion (a) — which is the intended break point.

## 4. Change attribution — engine and `harness.py` untouched by THIS change

`git diff -- prototype/bench/agentpii5/test_harness_stream.py` shows the E07 block
(263 insertions) plus its import additions. Grepping `harness.py` and
`prototype/pseudex/` diffs for any E07 marker
(`_chain_case`, `test_chain_repeat`, `CHAIN_PHONE`, `notify_sms`, `crm_find_contact`,
`source_hop`) returns **nothing**. The E07 change is confined to
`test_harness_stream.py`.

Caveat about the worktree: `git status` shows `harness.py` and many `prototype/pseudex/`
files as `M` relative to HEAD — but that is the whole sprint's uncommitted work in
this scratch worktree, not this E07 change (none of those diffs contain E07 content).

## 5. Gaps found (non-blocking, recorded for the record)

- **Gap A — the check does not self-load the bundle.** Every sibling check in this
  file calls `load_dev_bundle()`; `test_chain_repeat_correction_memory_two_entities`
  (and `_scripted_chain_run`) does not. Running the check in a fresh process alone
  raises `pseudex.assets.BundleNotLeased` from deep in the engine, not a test result:

  ```
  python -c "from bench.agentpii5.test_harness_stream import \
             test_chain_repeat_correction_memory_two_entities; \
             test_chain_repeat_correction_memory_two_entities()"
  → BundleNotLeased: detection assets are not leased
  ```

  It passes only because earlier checks in `main()` load the bundle first. The
  documented full-suite invocation passes; the check is order-dependent.

- **Gap B — `correction` is a necessary condition, not a unique pin.** Check (c)
  asserts `max(p1s turn-1 call_seq) > max(p2s turn-1 call_seq)`, but that ordering is
  also produced by the repeat (i1 at seq 5) following the second entity (i2 at seq 4).
  Empirically: deleting ONLY the correction block (the wrong seq-6 + right seq-7 pair)
  from a /tmp copy leaves the test still PASSING. The correction is exercised by the
  script and the "right-after-wrong" ordering is asserted, but a reader who removes
  just the correction sees no red. (The same shape applies to `repeat`: (b) asserts
  events==calls, which holds whether or not a repeat exists.)

Neither gap makes the assertions tautological — they read `actual_events` from the
restored `ArmRunV5`, and the flip non-vacuity is red — but both are worth tightening
if E07 is meant to stand alone and to uniquely pin "repeats" and "corrections".
