# Response-trace implementation — the model's own chronology

Task `hop-sprint-response-trace-20260927`. Scope `bench/agentpii5/` only; no
architecture/engine/metric change, no model calls.

## Defect

`GatewayV5.request_index` counts PUSHES (messages + results), not model
requests. Two tool calls in ONE DeepSeek response run sequentially but the
second did NOT see the first's result — a push counter cannot say this.
`request_count` therefore never meant «model requests» and is NOT
reinterpreted: the change is additive. And the final reply is the last NONEMPTY
text, not the end of the dialogue, so «which response carried this text» is not
recoverable from the reply list.

## Contract (`contracts.py`)

- `MODEL_TRACE_FORMAT = 1`.
- frozen `ModelResponse(request, turn, available_results, raw, restored)`.
- frozen `ModelTrace(responses, call_requests)`.
- `ArmRunV5.model_trace: ModelTrace | None` — no default, every constructor
  states it.
- `request` = 1-based model-request ordinal, one per completed provider
  response; `turn` = current user turn; `available_results` = accepted calls
  BEFORE this response's own calls run; `raw` = provider text ("" allowed);
  `restored` = `gateway.restore_text(raw)` then; `call_requests[i]` = request
  that emitted accepted call i.
- `None` = «connector never called `response`» (Claude, legacy, perfect), never
  «no model was asked»; no per-call request is manufactured.

## Hook (`connectors.py`, `harness.py`, `deepseek_connector.py`)

- `DialogueHooks.response(text)` added.
- `DeepSeekConnector` calls `hooks.response(...)` once per completed provider
  response, BEFORE its function calls, including empty text (pure tool-call
  turn → `("response", "")`).
- `GatewayHooks.response()` records turn, request ordinal, `len(calls)`, raw,
  and the restored text through the gateway's current state, then sets the
  current response for the calls that follow.
- `GatewayHooks.user()` clears the pending response: a call before THIS turn's
  first response is unmapped, not silently the previous turn's ordinal.
- `GatewayHooks.tool()` maps each accepted call to the current response ordinal;
  two calls of one response share one id.
- `model_trace()` returns None ONLY when no response was ever reported (legacy,
  even if it made calls). If ANY response was reported, an unmapped call or a
  mapped/recorded mismatch RAISES `HarnessError` — the connector speaks the
  hook, so `None` would erase evidence.
- `ConnectedArms._run` passes `hooks.model_trace()`; Claude `run_arm_v5`,
  `_empty_run`, `perfect.simulate`, `fixtures._run` pass None.

## Persistence (`records.py`)

Under `v5.model_trace`: `{"format": 1, "responses": [...], "call_requests": [...]}`.

- Missing key on old JSON reads None, and only that; explicit null too.
- Present trace validated: known format; nonempty; POSITIVE request ids;
  increasing requests; nonnegative non-decreasing turns; nonnegative
  available_results; call_requests integers, NONDECREASING (a `(2, 1)` map says
  a later call ran before an earlier one), length `len(base.calls)`, every id
  naming a recorded response; nonfuture boundary (`available_results` ≤ calls
  from strictly earlier responses). Violations raise `RecordError` by field.
- `arm_v5_from_record` requires `len(call_turns) == len(base.calls)` and each
  call's turn == the `turn` of the ModelResponse its `call_requests` names.
- Licensed scrub blanks raw/restored per response, keeps the chronology.

## Tests (`test_response_trace.py`, offline; mocked only at `responses.create`)

1. two calls in one response share request 1 and read available_results 0; the
   next response reads 2; empty response captured.
2. earlier text and later calls are not misdated.
3. never reported → None; reported once then unmapped, or count mismatch, →
   HarnessError (mixed legacy/trace).
4. real connector fires response before its calls: [resp "", tool, resp "done"].
5. full arm round-trip and format stamp; legacy row reads None; explicit None
   round-trips.
6. hand-written literal malformed rows (request 0, turn -1, call_requests [0],
   future boundary, backwards map (2, 1), count mismatch) plus record-level
   call-turn/response-turn disagreement and a wrong-length call_turns.
7. licensed scrub removes texts, keeps chronology.

## Verification

Four owned suites this round: test_response_trace 10/10, test_records 9/9,
test_connectors 11/11, test_harness 16/16 — all PASS. test_cli needs no entry
(it enumerates only non-`test_` stems).

`test_harness_stream` failure, reported exactly: test function
`test_restoration_runs_on_the_conversation_view` (`test_harness_stream.py:229`),
assertion line 276 `f"{case.base.id}: сообщение не восстановилось тем же видом:\n   было  {…!r}\n   стало {…!r}"`,
on result_feed-002/-006/-009/-011 — the two views disagree on the spoken phone
(one restores `+79128167121`, the other leaves the dictated words). No test
expectation or engine file touched.

No observer or metric reads `model_trace` yet; Codex owns that integration.
