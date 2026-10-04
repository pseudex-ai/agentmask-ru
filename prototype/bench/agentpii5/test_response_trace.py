"""The model's OWN chronology: `ModelResponse` / `ModelTrace` (contract 2026-09-27).

    cd prototype && source .venv/bin/activate && \
        PYTHONDONTWRITEBYTECODE=1 python3 -m bench.agentpii5.test_response_trace

WHAT IS PINNED, AND WHY EACH ONE IS A DEFECT AND NOT A STYLE.

`GatewayV5.request_index` counts PUSHES (messages and tool results), not model
requests. Two function calls in ONE DeepSeek response execute sequentially, but
the second did NOT see the first's result — a chronology keyed on pushes cannot
say that, and the final reply is the last NONEMPTY text rather than the end of
the dialogue. `ModelTrace` is additive: `request_count` keeps meaning exactly
what it always meant.

The provider is mocked ONLY at the external I/O boundary (`responses.create`);
the gateway, the hooks and the records are the real objects. No network, no
model, no money.

`forward_answer_leg` closes the loop M03 left open: the REAL `GatewayV5` + REAL
`GatewayHooks` chronology is serialized through the REAL `records` round-trip and
then read by the causal answer leg. It measures no live rate — the saved 450
still carry 0/450 traces — it proves the mechanism, and that the same run
WITHOUT a trace is `not_identifiable`.
"""
import asyncio
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openai.types.responses import (
    ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText)

from bench.agentpii3.schema import Source
from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.records import ArmMeta
from bench.agentpii4.schema import (
    Case, Expectation, Locus, Message, PiiItem, Provenance, SeedRecord)
from bench.agentpii5 import causal_hops
from bench.agentpii5 import harness as h
from bench.agentpii5 import records as r
from bench.agentpii5.connectors import Json, ToolSpec
from bench.agentpii5.contracts import (
    MODEL_TRACE_FORMAT, ArmRunV5, CaseV5, ModelResponse, ModelTrace)
from bench.agentpii5.deepseek_connector import DeepSeekConnector, DeepSeekSettings
from bench.agentpii5.mock import seed_backend_v5


# --- a gateway with only what `GatewayHooks` calls, and an observable restorer ----------

class _Gateway:
    """`restored` is marked so a stored restoration can be told from the raw
    text; `push_tool` is the non-`GatewayV5` branch `GatewayHooks.tool` takes."""

    def push_user(self, index: int) -> str:
        return f"user-{index}"

    def note(self, text: str) -> None: ...

    def note_tool_call(self, name: str, written: dict[str, object]) -> None: ...

    def restore_arguments(self, written: dict[str, object]) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]:
        return dict(written), {}

    def restore_text(self, text: str) -> str:
        return f"[{text}]"

    def push_tool(self, name: str, text: str) -> str:
        return f"served:{name}"


class _Log:
    def __init__(self, seq: int) -> None:
        self.seq = seq
        self.result_text = f"result-{seq}"
        self.refusal = None
        self.parsed: dict[str, object] = {"ok": True}


class _Backend:
    def call(self, name: str, restored: dict[str, object]) -> _Log:
        self.seen: list[str] = getattr(self, "seen", [])
        self.seen.append(name)
        return _Log(len(self.seen))


def _hooks() -> h.GatewayHooks:
    return h.GatewayHooks(None, _Gateway(), _Backend())  # type: ignore[arg-type]


# --- the FixtureRES of an ArmRunV5, copied minimally from test_records -----------------

def _case(licence: str) -> Case:
    source = None if licence == "" else Source(corpus="speech_calls", key="k1", line=1,
                                               sha256="0" * 64, licence=licence)
    return Case(
        id="c-0001", kind="chain", register="chat",
        provenance=Provenance(kind="authored", corpus="authored", key="", shape="",
                              selection="census", weight=1.0, licence=licence or "authored"),
        cluster="NAME:иванова елена", conversation_id="", now="2026-09-01",
        messages=(Message(role="system", content="ты оператор", source=None, name=""),
                  Message(role="user", content="Лена Иванова, Гоголя 12", source=source, name="")),
        tools=(), seed_records=(SeedRecord(id="s1", table="contacts", fields={"name": "Иванова Елена"},
                                           pii_ids=("p1",)),),
        pii=(PiiItem(id="p1", type="NAME", identity="i1", value="Лена Иванова",
                     canonical="Иванова Елена", parts={"given": "Елена", "surname": "Иванова"},
                     where=Locus(kind="message", msg=1, start=0, end=12, record="", path=""),
                     duty="required", spoken=False, stale=False),),
        plain=(), negatives=(),
        expects=Expectation(reachable_tools=("crm_find_contact",), primary_identity="i1",
                            must_contain=(), must_not_contain=(), validate_types=()),
        trace=(), note="фикстура хронологии модели")


def _arm(case_id: str) -> ArmRun:
    call = ObservedCall(name="crm_find_contact", written={"name": "Пахомова Ольга"},
                        restored={"name": "Иванова Елена"}, residual={"name": ()},
                        refusal_path="", refusal_rule="", parsed={"name": "Пахомова Ольга"}, seq=0)
    return ArmRun(case_id=case_id, arm="I", repeat=0, calls=(call,),
                  state=({"table": "contacts", "id": "s1"},), reply="Нашёл Елену Иванову.",
                  termination="done", cost_usd=0.0123,
                  substitutes={"p1": ("Пахомова Ольга", {"given": "Ольга", "surname": "Пахомова"})},
                  masked_spans={1: ((0, 12),)})


def _meta() -> ArmMeta:
    return ArmMeta(model="deepseek-flash", turns=2, duration_ms=100, session_id="sess",
                   subtype="success", is_error=False, api_error_status=None, errors=(),
                   reason="", cap_usd=0.5)


def _trace() -> ModelTrace:
    """Two responses; the one accepted call was emitted by the FIRST, and the
    second response (empty text) already saw its result."""
    return ModelTrace(responses=(ModelResponse(request=1, turn=1, available_results=0,
                                               raw="Сейчас посмотрю.", restored="Сейчас посмотрю."),
                                  ModelResponse(request=2, turn=1, available_results=1,
                                                raw="", restored="")),
                      call_requests=(1,))


def _arm_v5(case_id: str, trace: ModelTrace | None) -> ArmRunV5:
    base = _arm(case_id)
    return ArmRunV5(
        base=base, reply_raw="Нашёл Пахомову Ольгу.", control_reply="Нашёл Елену Иванову.",
        tool_results=(), mentions=(), turn_replies=("Сейчас посмотрю.",),
        call_turns=(1,), request_count=3, stream_mismatch=False,
        reply_whole="Нашёл Елену Иванову.", turn_residual=0, model_trace=trace)


def _refused(call: object) -> bool:
    try:
        call()  # type: ignore[operator]
    except r.RecordError:
        return True
    return False


# --- the chronology the hook records ---------------------------------------------------

def test_one_response_two_calls_then_the_next() -> list[str]:
    """THE DEFECT, pinned: two calls of ONE response map to the SAME request and
    both read `available_results == 0`; the NEXT response reads 2. The second
    call's result exists, and the first response did NOT see it."""
    failures: list[str] = []
    hooks = _hooks()
    hooks.user(3)
    hooks.response("Беру обе карточки.")
    hooks.tool("crm_find_contact", {"a": 1})
    hooks.tool("crm_find_contact", {"b": 2})
    hooks.response("")
    trace = hooks.model_trace()
    if trace is None:
        return ["a connector that reported every response got model_trace=None"]
    if [one.request for one in trace.responses] != [1, 2]:
        failures.append(f"requests are {[one.request for one in trace.responses]}, not [1, 2]")
    if trace.call_requests != (1, 1):
        failures.append(f"two calls of one response mapped to {trace.call_requests}, not (1, 1)")
    if [one.available_results for one in trace.responses] != [0, 2]:
        failures.append("available_results is "
                        f"{[one.available_results for one in trace.responses]}, not [0, 2]")
    if trace.responses[1].raw != "":
        failures.append(f"the empty response text was not captured: {trace.responses[1].raw!r}")
    if trace.responses[0].raw != "Беру обе карточки.":
        failures.append("the first response text was not captured")
    if trace.responses[0].restored != "[Беру обе карточки.]":
        failures.append(f"restoration did not go through the gateway: {trace.responses[0].restored!r}")
    if [one.turn for one in trace.responses] != [3, 3]:
        failures.append("both responses must carry the current user turn 3")
    if len(hooks.calls) != 2:
        failures.append("the two accepted calls were not both recorded")
    return failures


def test_earlier_text_and_later_calls_are_not_misdated() -> list[str]:
    """A later call maps to the LATER response, and an earlier response's text
    stays on the earlier turn — the failure mode a push counter produces."""
    failures: list[str] = []
    hooks = _hooks()
    hooks.user(1)
    hooks.response("Первый ответ")
    hooks.tool("t", {})
    hooks.user(2)
    hooks.response("Второй ответ")
    hooks.tool("t", {})
    trace = hooks.model_trace()
    if trace is None:
        return ["a fully reported arm got model_trace=None"]
    if [one.turn for one in trace.responses] != [1, 2]:
        failures.append(f"turns are {[one.turn for one in trace.responses]}, not [1, 2]")
    if [one.raw for one in trace.responses] != ["Первый ответ", "Второй ответ"]:
        failures.append("an earlier response's text was re-dated to a later turn")
    if [one.available_results for one in trace.responses] != [0, 1]:
        failures.append("the second response must see the first response's single result")
    if trace.call_requests != (1, 2):
        failures.append(f"call→response map is {trace.call_requests}, not (1, 2)")
    return failures


def test_a_connector_that_never_reported_has_no_trace() -> list[str]:
    """No `response` call EVER means None — never a manufactured per-call request."""
    hooks = _hooks()
    hooks.user(0)
    hooks.tool("t", {})
    if hooks.model_trace() is not None:
        return ["a connector that never called response still produced a trace"]
    return []


def test_any_response_then_an_unmapped_call_raises() -> list[str]:
    """THE MIXED CASE: a connector that speaks the hook and then makes a call
    with no reported response has BROKEN chronology. Returning None would erase
    the evidence, so the hook raises."""
    failures: list[str] = []
    hooks = _hooks()
    hooks.user(0)
    hooks.response("Первый ответ")
    hooks.tool("t", {})
    hooks.user(1)           # a new turn clears the pending response
    hooks.tool("t", {})     # ... and this call has none of its own
    try:
        hooks.model_trace()
        failures.append("an unmapped call after a reported response did not raise")
    except h.HarnessError:
        pass
    return failures


def test_a_missing_map_entry_raises() -> list[str]:
    """A mapped count that does not line up is broken chronology too, not silence."""
    failures: list[str] = []
    hooks = _hooks()
    hooks.user(0)
    hooks.response("Первый ответ")
    hooks.tool("t", {})
    hooks.call_requests.clear()    # the writer dropped a mapping
    try:
        hooks.model_trace()
        failures.append("a mapped/recorded call-count mismatch did not raise")
    except h.HarnessError:
        pass
    return failures


# --- the connector fires the hook at the right boundary --------------------------------

class _FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses

    async def create(self, **request: object) -> object:
        return self.responses.pop(0)


class _FakeOpenAI:
    def __init__(self, responses: _FakeResponses) -> None:
        self.responses = responses


class _TraceHooks:
    """Ordered events, so «BEFORE processing its function calls» is checkable."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def user(self, index: int) -> str:
        return f"user-{index}"

    def assistant(self, text: str) -> None:
        self.events.append(("assistant", text))

    def response(self, text: str) -> None:
        self.events.append(("response", text))

    def tool(self, name: str, arguments: dict[str, Json]) -> h.ToolResult:
        self.events.append(("tool", name))
        return h.ToolResult('{"ok":true}', True)


def test_deepseek_reports_one_response_per_provider_response() -> list[str]:
    """The real connector, mocked only at `responses.create`: the hook fires
    ONCE per completed provider response, BEFORE its function calls, and an
    empty-text tool-call turn is reported as `""`."""
    usage = SimpleNamespace(input_tokens=20, output_tokens=5,
                            input_tokens_details=SimpleNamespace(cached_tokens=0),
                            output_tokens_details=SimpleNamespace(reasoning_tokens=1))
    call = ResponseFunctionToolCall(type="function_call", call_id="c1", name="lookup",
                                    arguments='{"id":"x"}')
    answer = ResponseOutputMessage(
        id="m1", type="message", role="assistant", status="completed",
        content=[ResponseOutputText(type="output_text", text="done", annotations=[], logprobs=[])])
    responses = _FakeResponses([
        SimpleNamespace(status="completed", error=None, usage=usage, output=[call]),
        SimpleNamespace(status="completed", error=None, usage=usage, output=[answer]),
    ])
    settings = DeepSeekSettings("deepseek-flash", "low", 1000, 2, 100, None,
                                "https://api.deepseek.com")
    hooks = _TraceHooks()
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture"}, clear=False), \
         patch("bench.agentpii5.deepseek_connector.AsyncOpenAI",
               return_value=_FakeOpenAI(responses)):
        asyncio.run(DeepSeekConnector(settings).converse(
            "S", (ToolSpec("lookup", "lookup one",
                           {"type": "object", "properties": {"id": {"type": "string"}}}),),
            (0,), hooks, 5.0, 1))
    observed = [event for event in hooks.events if event[0] in ("response", "tool")]
    want = [("response", ""), ("tool", "lookup"), ("response", "done")]
    if observed != want:
        return [f"connector event order is {observed}, not {want}"]
    return []


# --- persistence: roundtrip, legacy absence, malformed, licensed scrub ------------------

def test_trace_round_trips_under_a_versioned_format() -> list[str]:
    failures: list[str] = []
    case = _case("")
    run = _arm_v5(case.id, _trace())
    record = r.arm_v5_record(run, _meta(), case)
    block = record[r.V5_KEY]
    if not isinstance(block, dict) or block.get("model_trace", {}).get("format") != MODEL_TRACE_FORMAT:
        failures.append(f"the trace was not written with format {MODEL_TRACE_FORMAT}: "
                        f"{block.get('model_trace') if isinstance(block, dict) else block}")
    back = r.arm_v5_from_record(record)
    if back != run:
        failures.append(f"ArmRunV5 with a trace did not round-trip:\n  was {run}\n  now {back}")
    return failures


def test_a_legacy_row_reads_none() -> list[str]:
    """An old JSON has no `model_trace` key; that reads None and ONLY None — no
    fabricated chronology, and no refusal of a row that is otherwise valid."""
    failures: list[str] = []
    case = _case("")
    record = r.arm_v5_record(_arm_v5(case.id, None), _meta(), case)
    block = record[r.V5_KEY]
    assert isinstance(block, dict)
    block.pop("model_trace")
    back = r.arm_v5_from_record(record)
    if back.model_trace is not None:
        failures.append("a legacy row without the key did not read None")
    if r.arm_v5_from_record(r.arm_v5_record(_arm_v5(case.id, None), _meta(), case)).model_trace is not None:
        failures.append("an explicit None did not round-trip as None")
    return failures


def test_a_malformed_trace_is_refused() -> list[str]:
    failures: list[str] = []
    good = r.model_trace_to_json(_trace())
    if good["format"] != MODEL_TRACE_FORMAT:
        failures.append("the writer did not stamp the format version")
    response: dict[str, object] = {"request": 1, "turn": 0, "available_results": 0,
                                   "raw": "x", "restored": "x"}

    def mutated(**changes: object) -> object:
        return {**good, **changes}

    # LITERAL ROWS, written by hand rather than mutated from the writer's own
    # output: a validator tested only against mutations of itself is tested
    # against one author's idea of what malformed means.
    literals = (
        ({"format": 1, "responses": [response], "call_requests": [0]}, 1,
         "a call mapped to request 0 (ids are positive)"),
        ({"format": 1, "responses": [{**response, "request": 0}], "call_requests": []}, 0,
         "a response with request 0"),
        ({"format": 1, "responses": [{**response, "turn": -1}], "call_requests": []}, 0,
         "a response with a negative turn"),
        ({"format": 1, "responses": [response, {**response, "request": 2, "turn": 1,
                                                "available_results": 9}],
          "call_requests": [1]}, 1,
         "a future available_results boundary"),
        ({"format": 1, "responses": [response, {**response, "request": 2, "turn": 1,
                                                "available_results": 1}],
          "call_requests": [2, 1]}, 2,
         "a call map that goes backwards (2, 1)"),
        ({"format": 1, "responses": [response], "call_requests": [1, 1]}, 1,
         "more mapped calls than recorded calls"),
    )
    for value, calls, label in literals:
        if not _refused(lambda value=value, calls=calls:
                        r.model_trace_from_json(value, calls)):
            failures.append(f"the reader accepted {label}")

    mutations = (
        (mutated(format=MODEL_TRACE_FORMAT + 1), "an unknown format version"),
        (mutated(call_requests=[9]), "a call mapped to a response that was never recorded"),
        (mutated(responses=[{**good["responses"][1]}, {**good["responses"][0]}]),  # type: ignore[index]
         "responses that are not in increasing request order"),
        (mutated(responses=[{**good["responses"][0], "raw": 1}]),  # type: ignore[index]
         "a response whose raw text is not text"),
        (mutated(responses=[]), "a present but empty trace"),
    )
    for value, label in mutations:
        if not _refused(lambda value=value: r.model_trace_from_json(value, 1)):
            failures.append(f"the reader accepted {label}")

    # THE CALL'S TURN AND ITS RESPONSE'S TURN ARE ONE FACT, recorded twice.
    case = _case("")
    record = r.arm_v5_record(_arm_v5(case.id, _trace()), _meta(), case)
    block = record[r.V5_KEY]
    assert isinstance(block, dict)
    if not _refused(lambda: r.arm_v5_from_record(
            {**record, r.V5_KEY: {**block, "call_turns": [0]}})):
        failures.append("the reader accepted a call turn that disagrees with its response turn")
    if not _refused(lambda: r.arm_v5_from_record(
            {**record, r.V5_KEY: {**block, "call_turns": [1, 1]}})):
        failures.append("the reader accepted more call turns than recorded calls")
    return failures


def test_a_licensed_trace_loses_its_text_and_keeps_its_chronology() -> list[str]:
    failures: list[str] = []
    case = _case("CC BY-NC 4.0")
    record = r.arm_v5_record(_arm_v5(case.id, _trace()), _meta(), case)
    block = record[r.V5_KEY]["model_trace"]
    if any(one["raw"] != r.SCRUB_MARKER or one["restored"] != r.SCRUB_MARKER
           for one in block["responses"]):
        failures.append(f"a licensed trace kept the provider's text: {block['responses']}")
    if block["call_requests"] != [1]:
        failures.append("a licensed trace lost its call→response map")
    back = r.arm_v5_from_record(record)
    if back.model_trace is None or back.model_trace.call_requests != (1,):
        failures.append("a scrubbed trace did not read back as a chronology")
    return failures


# --- the FORWARD answer leg: real gateway + real hooks + real records -> causal ---------

def _forward_case() -> CaseV5:
    """A real corpus case whose tool result CARRIES items the answer can name.

    `chain-000`: the customer gives their own name and phone, a find call
    returns the seeded card, and the reply repeats a name from that card. The
    item chosen below (`i1`) is SEEDED, so its answer emission is a tool-causal
    question and not `user_provided`."""
    cases, _digest = h._load_corpus(Path(__file__).with_name("corpus.v5.json"))
    return next(one for one in cases if one.base.id == "chain-000")


def _forward_run(case: CaseV5) -> ArmRunV5:
    """THE REAL LOCAL FORWARD PATH: `GatewayV5` with the real detector and
    vault, the real `GatewayHooks`, and the chronology the hooks record.

    No network and no model: the two provider responses are spoken by this
    test, which is exactly what a connector's `response` hook does. The tool
    QUERY is the customer's real surname because the mock must find the card;
    that leaf is not what this check measures (it is a leak question for
    `actual_hops`), and the ANSWER is written with the substitute the gateway
    minted for the result.
    """
    h.load_dev_bundle()
    gateway = h.GatewayV5(case, h.Detector(), h.Vault(":memory:", "trace-forward"),
                          h.AuditLog(":memory:"), h.MaskCache(256))
    hooks = h.GatewayHooks(case, gateway, seed_backend_v5(case))
    gateway.push_system(case.base.messages[0].content)
    gateway.tools()
    turn = next(index for index, message in enumerate(case.base.messages)
                if message.role == "user")
    hooks.user(turn)
    hooks.response("")                                     # response 1: asks for the tool
    hooks.tool("crm_find_contact", {"query": {"last_name": "букин"}})
    substitutes = h.substitutes_for(case.base, gateway.substitutes_seen())
    fake = substitutes["i1"][0]
    raw = f"Нашёл: {fake}, готово."                        # response 2: the answer
    hooks.response(raw)
    restored = gateway.restore_text(raw)
    base = ArmRun(case_id=case.base.id, arm="I", repeat=0, calls=tuple(hooks.calls), state=(),
                  reply=restored, termination="done", cost_usd=0.0, substitutes=substitutes,
                  masked_spans=gateway.masked_spans())
    return ArmRunV5(
        base=base, reply_raw=raw, control_reply="", tool_results=gateway.tool_records(),
        mentions=gateway.mentions(), turn_replies=(restored,), call_turns=tuple(hooks.turns),
        request_count=gateway.request_index, stream_mismatch=False, reply_whole=restored,
        turn_residual=0, model_trace=hooks.model_trace())


def _answer_event(case: CaseV5, run: ArmRunV5, item_id: str) -> causal_hops.CausalEvent:
    found = [one for one in causal_hops.causal_events(case, run).events
             if one.surface == "answer" and one.item_id == item_id]
    if len(found) != 1:
        raise AssertionError(f"expected one answer event for {item_id}, found {len(found)}")
    return found[0]


def test_the_forward_answer_trace_proves_the_answer_leg() -> list[str]:
    """M03-F2, validated LOCALLY and reported HONESTLY.

    The saved 450 carry no `model_trace` (0/450), so the answer leg is
    UNMEASURED there and this check does not invent a rate. What it proves is
    the mechanism: a run that reports its chronology lets `causal_hops`
    attribute the answer to the one tool result that preceded it, through the
    real `GatewayHooks` and the real `records` round-trip — and the SAME run
    with the chronology removed is `not_identifiable`, which is what the
    archive's answer line really is.
    """
    failures: list[str] = []
    case = _forward_case()
    run = _forward_run(case)
    trace = run.model_trace
    if trace is None:
        return ["the real forward path produced no chronology at all"]
    if [one.available_results for one in trace.responses] != [0, 1]:
        failures.append("the answering response did not see the tool result: "
                        f"{[one.available_results for one in trace.responses]}")
    if trace.call_requests != (1,):
        failures.append(f"the call map is {trace.call_requests}, not (1,)")

    record = r.arm_v5_record(run, _meta(), case.base)
    back = r.arm_v5_from_record(record)
    if back != run:
        failures.append("the forward run did not survive the records round-trip")

    answered = _answer_event(case, back, "i1")
    if (answered.status, answered.source_seq) != ("attributed", 1):
        failures.append(f"the seeded answer item is {answered.status}/{answered.source_seq}, "
                        f"not attributed/1: {answered.evidence}")
    if answered.attributed is not True:
        failures.append("an attributed answer event did not carry attributed=True")
    if _answer_event(case, back, "i8").status != "user_provided":
        failures.append("the customer's own name in the answer is not user_provided")

    # THE ARCHIVE, REPRODUCED LOCALLY: the very same run WITHOUT the provider
    # chronology is `not_identifiable` — so the 450's 0/846 answer-from-tool is
    # a missing-record fact, not an engine result.
    archived = replace(back, model_trace=None)
    unproved = _answer_event(case, archived, "i1")
    if unproved.status != "not_identifiable" or unproved.attributed:
        failures.append(f"a run with no chronology read {unproved.status}, not not_identifiable")
    return failures


def main() -> int:
    checks = (
        ("one_response_two_calls_then_next", test_one_response_two_calls_then_the_next),
        ("earlier_text_and_later_calls", test_earlier_text_and_later_calls_are_not_misdated),
        ("no_report_no_trace", test_a_connector_that_never_reported_has_no_trace),
        ("mixed_then_unmapped_raises", test_any_response_then_an_unmapped_call_raises),
        ("missing_map_entry_raises", test_a_missing_map_entry_raises),
        ("deepseek_reports_each_response", test_deepseek_reports_one_response_per_provider_response),
        ("versioned_roundtrip", test_trace_round_trips_under_a_versioned_format),
        ("legacy_reads_none", test_a_legacy_row_reads_none),
        ("malformed_is_refused", test_a_malformed_trace_is_refused),
        ("licensed_scrub", test_a_licensed_trace_loses_its_text_and_keeps_its_chronology),
        ("forward_answer_leg", test_the_forward_answer_trace_proves_the_answer_leg),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("response_trace: PASS" if not failures
          else "response_trace: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
