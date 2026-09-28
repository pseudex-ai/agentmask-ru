"""`causal_hops.py` pinned: WHO an emission came from, proved by the chronology.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_causal_hops

Every check fails on the optimistic reading it replaces:

  * a user datum the answer repeats AFTER an unrelated tool ran is
    `user_provided` — the tool and its result explain nothing;
  * an answer built from the FIRST result and an answer built from the SECOND
    are attributed to different results (`first_result` / `later_result`);
  * two calls of ONE model response are not a sequence: the first result was NOT
    available to the call that the same response also asked for, so nothing is
    attributed to it — and a mutant that reads execution order instead of the
    response boundary attributes it, which is the red this file pins;
  * a summary and a template emission are their own lines, with their own
    denominators, and the true result-A -> call-B edge is attributed to A;
  * an ARCHIVED run with no response boundary is `not_identifiable`, never
    `attributed` and never a silent pass — the second mutation guard converts
    `not_identifiable` into a pass and demands the optimistic verdict instead;
  * a result that arrived LATER is evidence against, so the emission stays
    `user_provided`;
  * ONE PROVED CARRIER BESIDE ONE UNPROVABLE SAME-TURN CARRIER is
    `not_identifiable`: a proved cause is not a UNIQUE cause (M03-F1), and the
    evidence names the unprovable carrier instead of claiming none exists;
  * the branch-order neighbours around it: a single proved carrier stays
    `attributed`, two proved carriers and a user copy beside one are
    `ambiguous`, a lone unprovable carrier is `not_identifiable`, a user copy
    beside an unprovable carrier is `not_identifiable`, and a later-only
    carrier is `unattributed`;
  * `case.hops` is never read: a crossing the corpus did not schedule is
    measured all the same.
"""
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii4.compare import ObservedCall
from bench.agentpii4.schema import PiiItem
from bench.agentpii5 import causal_hops
from bench.agentpii5.causal_hops import (
    CAUSAL_SURFACES,
    CAUSAL_STATUSES,
    ESTIMATOR_VERSION,
    TOOL_CAUSAL_STATUSES,
    CausalEvent,
    aggregate,
    call_consumer,
    causal_events,
    render,
    result_available,
)
from bench.agentpii5.contracts import ArmRunV5, CaseV5, ModelResponse, ModelTrace, ToolResultRecord
from bench.agentpii5.fixtures import (
    _call,
    _case,
    _hop,
    _in_message,
    _in_seed,
    _item,
    _result,
    _run,
    _with_calls,
    _with_mentions,
    _with_replies,
    _with_results,
    _with_subs,
)

# --- the small world every check is built in --------------------------------------------

USER_ITEM: PiiItem = _item("p1", "NAME", "Иванова Елена", "Иванова Елена", "i1",
                           _in_message(0, 0, 13))
USER_FAKE = "Пахомова Ольга"
# Two seed items, reached ONLY through tool results: one per result, so «first»
# and «second» are two different data and not two spellings of one.
SEED_ONE: PiiItem = _item("p9", "NAME", "Смирнова Анна", "Смирнова Анна", "i2",
                          _in_seed("s2", "name"))
SEED_TWO: PiiItem = _item("p8", "NAME", "Кузнецова Дарья", "Кузнецова Дарья", "i3",
                          _in_seed("s3", "name"))
FAKE_ONE = "Сидорова Вера"
FAKE_TWO = "Орлова Мария"
FIND = "crm_find_contact"
SMS = "notify_sms"
NOTE = "crm_add_note"

IN_USER = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
IN_TOOL_ONE = _hop("IN", "tool", "p9", 1, 0, FIND, 0, -1, "contacts[].name")
OUT_ANSWER = _hop("OUT", "answer", "p9", 2, 1, "", -1, -1, "")


def _case_world(case_id: str, items: tuple[PiiItem, ...]) -> CaseV5:
    """A case with NO declared hop tying the results to anything: every verdict
    below has to come from the chronology, never from a timetable."""
    return _case(case_id, "sequential_chain", ("найди клиента", "запиши"), items,
                 (IN_USER, IN_TOOL_ONE, OUT_ANSWER))


def _mention(item_id: str, msg: int, result_seq: int, substitute: str, request: int = 1):
    from bench.agentpii5.contracts import MentionRecord
    return MentionRecord(item_id=item_id, msg=msg, result_seq=result_seq,
                         substitute=substitute, request_index=request)


def _response(request: int, turn: int, available: int, raw: str = "", restored: str = "") -> ModelResponse:
    return ModelResponse(request=request, turn=turn, available_results=available,
                         raw=raw, restored=restored)


def _trace(responses: tuple[ModelResponse, ...], call_requests: tuple[int, ...]) -> ModelTrace:
    return ModelTrace(responses=responses, call_requests=call_requests)


def _result_carrying(seq: int, turn: int, item_id: str, real: str, fake: str) -> ToolResultRecord:
    """One tool result whose TYPED tag names the item, as the mock records it."""
    return _result(FIND, turn, seq, "list", real, fake,
                   {item_id: (0, len(real))}, (), False)


def _by_surface(events: tuple[CausalEvent, ...], surface: str) -> tuple[CausalEvent, ...]:
    return tuple(one for one in events if one.surface == surface)


def _one(events: tuple[CausalEvent, ...], surface: str, item_id: str) -> CausalEvent:
    found = tuple(one for one in _by_surface(events, surface) if one.item_id == item_id)
    if len(found) != 1:
        raise AssertionError(f"expected one {surface} event for {item_id}, found {len(found)}")
    return found[0]


# --- check 1: a user datum after an unrelated tool ----------------------------------------

def check_user_datum_after_unrelated_tool() -> None:
    case = _case_world("cx-user", (USER_ITEM, SEED_ONE))
    run = _with_calls(
        _run("cx-user"),
        (_call(FIND, {"query": "заказ 42"}, {"query": "заказ 42"}, {}, "", 0),), (0,))
    run = _with_results(run, (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),))
    run = _with_mentions(run, (_mention("p1", 0, -1, USER_FAKE),
                               _mention("p9", -1, 0, FAKE_ONE)))
    run = _with_subs(run, {"p1": USER_FAKE, "p9": FAKE_ONE})
    run = _with_replies(run, f"Клиент {USER_FAKE} подтвердил заказ.",
                        "Клиент Иванова Елена подтвердил заказ.", "")
    run = replace(run, model_trace=_trace(
        (_response(1, 0, 0, f"Клиент {USER_FAKE} подтвердил заказ.",
                   "Клиент Иванова Елена подтвердил заказ."),), (1,)))
    observed = causal_events(case, run)
    event = _one(observed.events, "answer", "p1")
    assert event.status == "user_provided", event.evidence
    assert event.source_seq == -1 and event.source_kind == "user"
    assert event.attributed is False
    # The unrelated result carried p9 and was never in the answer: it produced
    # neither an answer event nor an edge, and it explains nothing about p1.
    assert not _by_surface(observed.events, "answer") or \
        all(one.item_id != "p9" for one in _by_surface(observed.events, "answer"))
    assert _by_surface(observed.events, "chain") == ()
    # THE GENERAL MENTION DENOMINATOR KEEPS IT, THE CAUSAL ONE DOES NOT.
    line = aggregate((observed,)).by_surface[0]
    assert line.key == "answer" and line.candidates == 1 and line.user_provided == 1
    assert line.tool_causal == 0 and line.attributed == 0
    print("causal_hops: user datum after an unrelated tool -> user_provided (mention kept, "
          "causal denominator empty)")


# --- check 2: the FIRST result and the SECOND result are different sources ----------------

def check_first_and_second_result() -> None:
    case = _case_world("cx-two-results", (SEED_ONE, SEED_TWO))
    calls = (_call(FIND, {"query": "первый"}, {"query": "первый"}, {}, "", 0),
             _call(FIND, {"query": "второй"}, {"query": "второй"}, {}, "", 1))
    run = _with_calls(_run("cx-two-results"), calls, (0, 1))
    run = _with_results(run, (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),
                              _result_carrying(1, 1, "p8", "Кузнецова Дарья", FAKE_TWO)))
    run = _with_mentions(run, (_mention("p9", -1, 0, FAKE_ONE),
                               _mention("p8", -1, 1, FAKE_TWO)))
    raw = f"Найдены {FAKE_ONE} и {FAKE_TWO}."
    restored = "Найдены Смирнова Анна и Кузнецова Дарья."
    run = _with_subs(run, {"p9": FAKE_ONE, "p8": FAKE_TWO})
    run = _with_replies(run, raw, restored, "")
    run = replace(run, model_trace=_trace(
        (_response(1, 0, 0), _response(2, 1, 1), _response(3, 2, 2, raw, restored)),
        (1, 2)))
    events = causal_events(case, run).events
    first = _one(events, "answer", "p9")
    second = _one(events, "answer", "p8")
    assert (first.status, first.source_seq, first.source_kind) == ("attributed", 0, "first_result")
    assert (second.status, second.source_seq, second.source_kind) == ("attributed", 1, "later_result")
    assert first.value_ok is True and second.value_ok is True
    line = next(one for one in aggregate((causal_events(case, run),)).by_surface
                if one.key == "answer")
    assert line.attributed == 2 and line.first_result == 1 and line.later_result == 1
    assert line.joint_ok <= line.attributed
    print("causal_hops: answer from the first result vs the second -> attributed (seq 0 / seq 1)")


# --- check 3: two calls of ONE response are not a sequence (mutation guard 1) -------------

def _same_response_run(with_trace: bool) -> tuple[CaseV5, ArmRunV5]:
    case = _case_world("cx-same-response", (SEED_ONE,))
    calls = (_call(FIND, {"query": "первый"}, {"query": "первый"}, {}, "", 0),
             _call(FIND, {"query": FAKE_ONE}, {"query": "Смирнова Анна"}, {}, "", 1))
    run = _with_calls(_run("cx-same-response"), calls, (1, 1))
    run = _with_results(run, (_result_carrying(0, 1, "p9", "Смирнова Анна", FAKE_ONE),))
    run = _with_mentions(run, (_mention("p9", -1, 0, FAKE_ONE),))
    run = _with_subs(run, {"p9": FAKE_ONE})
    if with_trace:
        # ONE response emitted BOTH calls: `available_results` is 0 for it, so
        # the first result was NOT in the model's hands when it asked for both.
        run = replace(run, model_trace=_trace(
            (_response(1, 1, 0), _response(2, 2, 2)), (1, 1)))
    return case, run


def check_two_calls_of_one_response() -> None:
    case, run = _same_response_run(True)
    assert result_available(run, 0, call_consumer(1, 1)) is False, \
        "a result produced by the SAME response is not available to the other call it asked for"
    event = _one(causal_events(case, run).events, "tool_arg", "p9")
    assert event.status == "unattributed", event.evidence
    assert event.attributed is False
    # MUTATION GUARD 1 — «execution order is enough». A mutant that drops the
    # response boundary finds the result available and attributes the call, so
    # the assertion above is what makes that mutation red.
    original: Callable[..., bool | None] = causal_hops.result_available

    def execution_order(run_: ArmRunV5, result_seq: int, consumer: causal_hops.Consumer,
                        item_id: str = "") -> bool | None:
        if consumer.kind == "answer":
            return original(run_, result_seq, consumer, item_id)
        result_index = next(index for index, call in enumerate(run_.base.calls)
                            if call.seq == result_seq)
        call_index = next(index for index, call in enumerate(run_.base.calls)
                          if call.seq == consumer.seq)
        return result_index < call_index

    causal_hops.result_available = execution_order
    try:
        mutant = _one(causal_events(case, run).events, "tool_arg", "p9")
    finally:
        causal_hops.result_available = original
    assert mutant.status == "attributed", "the mutation guard no longer detects the optimistic rule"
    print("causal_hops: two calls of one response -> unattributed "
          "(mutation 'execution order only' -> attributed, red)")


# --- check 4: a summary and a template are their own lines, and the edge is real ----------

def check_summary_template_and_chain_edge() -> None:
    case = _case_world("cx-emit", (SEED_ONE,))
    calls = (_call(FIND, {"query": "клиент"}, {"query": "клиент"}, {}, "", 0),
             _call(SMS, {"text": f"{FAKE_ONE}, заказ принят"},
                   {"text": "Смирнова Анна, заказ принят"}, {}, "", 1),
             _call(NOTE, {"text": f"клиент {FAKE_ONE} подтвердил"},
                   {"text": "клиент Смирнова Анна подтвердил"}, {}, "", 2))
    run = _with_calls(_run("cx-emit"), calls, (0, 1, 2))
    run = _with_results(run, (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),))
    run = _with_mentions(run, (_mention("p9", -1, 0, FAKE_ONE),))
    run = _with_subs(run, {"p9": FAKE_ONE})
    run = replace(run, model_trace=_trace(
        (_response(1, 0, 0), _response(2, 1, 1), _response(3, 2, 1), _response(4, 3, 1)),
        (1, 2, 3)))
    observed = causal_events(case, run)
    template = _one(observed.events, "template", "p9")
    summary = _one(observed.events, "summary", "p9")
    assert (template.status, template.source_seq) == ("attributed", 0)
    assert (summary.status, summary.source_seq) == ("attributed", 0)
    assert template.tool_name == SMS and summary.tool_name == NOTE
    # THE ACTUAL EDGE result A -> later call B: both acting calls re-emitted the
    # datum of result 0, and each is its own edge.
    edges = {one.call_seq: one for one in _by_surface(observed.events, "chain")}
    assert set(edges) == {1, 2}, edges
    assert all(one.status == "attributed" and one.source_seq == 0 for one in edges.values())
    assert all(one.source_kind == "first_result" for one in edges.values())
    result = aggregate((observed,))
    assert {one.key for one in result.by_surface} == {"chain", "summary", "template"}
    assert {one.key for one in result.by_owner} == {"summary", "template"}
    assert result.estimator == ESTIMATOR_VERSION
    assert set(CAUSAL_SURFACES) >= {"answer", "tool_arg", "summary", "template", "chain"}
    assert set(TOOL_CAUSAL_STATUSES) <= set(CAUSAL_STATUSES)
    assert any("Not identifiable" in row for row in render(result))
    print("causal_hops: summary and template lines separate; true result-0 -> call-1/2 edges "
          "attributed")


# --- check 5: an archived trace has no boundary (mutation guard 2) ------------------------

def check_archived_trace_is_not_identifiable() -> None:
    case, run = _same_response_run(False)
    assert run.model_trace is None
    assert result_available(run, 0, call_consumer(1, 1)) is None, \
        "one turn, no recorded response boundary: availability is unprovable"
    event = _one(causal_events(case, run).events, "tool_arg", "p9")
    assert event.status == "not_identifiable", event.evidence
    assert event.attributed is False
    # MUTATION GUARD 2 — «not_identifiable is close enough to a pass». A mutant
    # that reads an unknown boundary as available attributes the call, so the
    # `not_identifiable` assertion above is what makes that mutation red.
    original: Callable[..., bool | None] = causal_hops.result_available

    def optimistic(run_: ArmRunV5, result_seq: int, consumer: causal_hops.Consumer,
                   item_id: str = "") -> bool | None:
        proved = original(run_, result_seq, consumer, item_id)
        return True if proved is None else proved

    causal_hops.result_available = optimistic
    try:
        mutant = _one(causal_events(case, run).events, "tool_arg", "p9")
    finally:
        causal_hops.result_available = original
    assert mutant.status == "attributed", \
        "the mutation guard no longer converts not_identifiable into a pass"
    print("causal_hops: archived trace, same turn -> not_identifiable "
          "(mutation 'unknown = available' -> attributed, red)")


# --- check 6: a FUTURE result is evidence against, not for --------------------------------

def check_future_result_is_unavailable() -> None:
    case = _case_world("cx-future", (USER_ITEM, SEED_ONE))
    calls = (_call(FIND, {"query": USER_FAKE}, {"query": "Иванова Елена"}, {}, "", 0),
             _call(FIND, {"query": "позже"}, {"query": "позже"}, {}, "", 1),
             _call(FIND, {"query": FAKE_ONE}, {"query": "Смирнова Анна"}, {}, "", 2))
    run = _with_calls(_run("cx-future"), calls, (0, 1, 3))
    # The result that CARRIES both data belongs to a LATER call and a LATER
    # turn. Call 0 cannot have read it.
    carrying = _result(FIND, 2, 1, "list", "Смирнова Анна Иванова Елена", "",
                       {"p9": (0, 12), "p1": (13, 25)}, (), False)
    run = _with_results(run, (carrying,))
    run = _with_mentions(run, (_mention("p1", 0, -1, USER_FAKE),
                               _mention("p1", -1, 1, USER_FAKE),
                               _mention("p9", -1, 1, FAKE_ONE)))
    run = _with_subs(run, {"p1": USER_FAKE, "p9": FAKE_ONE})
    run = replace(run, model_trace=_trace(
        (_response(1, 0, 0), _response(2, 1, 0), _response(3, 3, 2)), (1, 2, 3)))
    assert result_available(run, 1, call_consumer(0, 0)) is False, \
        "a result of a later call/turn is not available to call 0"
    event = _one(causal_events(case, run).events, "tool_arg", "p1")
    assert event.status == "user_provided", event.evidence
    assert event.attributed is False and event.source_seq == -1
    # ...while the LATER call may use it: the same result, one turn on, is not a
    # future result any more.
    later = _one(causal_events(case, run).events, "chain", "p9")
    assert later.call_seq == 2 and later.status == "attributed" and later.source_seq == 1
    print("causal_hops: future result unavailable -> call 0 user_provided, call 2 attributed")


# --- check 7: ONE PROVED CARRIER BESIDE ONE UNPROVABLE ONE (M03-F1, RED first) -----------

def _available_plus_unknown_run() -> tuple[CaseV5, ArmRunV5]:
    """ONE proved carrier and ONE unprovable same-turn carrier, no user copy —
    the case contract rule 3 exists for.

    The run is ARCHIVED (`model_trace is None`), which is what every one of the
    saved 450 is: result 0 landed on an EARLIER turn and is proved available,
    while result 1 shares the consuming call's turn and has no recorded response
    boundary. Two calls of one turn can belong to one response, so result 1's
    availability is unprovable — and an unprovable carrier means uniqueness is
    not established, whatever the proved one says."""
    case = _case_world("cx-unknown-outranks", (SEED_ONE,))
    calls = (_call(FIND, {"query": "первый"}, {"query": "первый"}, {}, "", 0),
             _call(SMS, {"text": "промежуточно"}, {"text": "промежуточно"}, {}, "", 1),
             _call(FIND, {"query": FAKE_ONE}, {"query": "Смирнова Анна"}, {}, "", 2))
    run = _with_calls(_run("cx-unknown-outranks"), calls, (0, 2, 2))
    run = _with_results(run, (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),
                              _result_carrying(1, 2, "p9", "Смирнова Анна", FAKE_ONE)))
    run = _with_mentions(run, (_mention("p9", -1, 0, FAKE_ONE),))
    return case, _with_subs(run, {"p9": FAKE_ONE})


def check_unknown_carrier_outranks_a_proved_one() -> None:
    case, run = _available_plus_unknown_run()
    assert run.model_trace is None, "this check is the archived-run case; a trace would prove it"
    assert result_available(run, 0, call_consumer(2, 2)) is True, \
        "result seq 0 is on an earlier turn and must be PROVED available"
    assert result_available(run, 1, call_consumer(2, 2)) is None, \
        "result seq 1 shares the consumer's turn with no boundary and must be UNPROVABLE"
    event = _one(causal_events(case, run).events, "tool_arg", "p9")
    # THE OPTIMISTIC READING IS THE RED: one proved carrier alone returned
    # `attributed` and wrote an evidence line saying no other carrier existed —
    # while carrier seq 1 was there, merely unprovable.
    assert event.status == "not_identifiable", event.evidence
    assert event.attributed is False, event.evidence
    assert event.source_seq == -1 and event.source_kind == ""
    assert set(event.candidate_seqs) == {0, 1}, event.candidate_seqs
    assert "no other carrier is available" not in event.evidence, event.evidence
    assert "seq 1" in event.evidence, event.evidence
    line = next(one for one in aggregate((causal_events(case, run),)).by_surface
                if one.key == "tool_arg")
    assert line.attributed == 0 and line.not_identifiable == 1, line
    print("causal_hops: proved carrier + unprovable same-turn carrier -> not_identifiable "
          "(the evidence names both, never 'no other carrier')")


# --- check 8: the branch-order controls around the RED ------------------------------------

# One consumer (call seq 2, turn 1) and three recorded calls, so a result of an
# earlier call/turn is PROVED, a result of the consumer's own turn is UNPROVABLE
# and a result of a later turn is evidence AGAINST. Every control below differs
# only in which result carries the item.
_CONTROL_CALLS = (
    _call(FIND, {"query": "первый"}, {"query": "первый"}, {}, "", 0),
    _call(FIND, {"query": "второй"}, {"query": "второй"}, {}, "", 1),
    _call(FIND, {"query": FAKE_ONE}, {"query": "Смирнова Анна"}, {}, "", 2),
)
_CONTROL_TURNS = (0, 0, 1)
_CONTROL_CONSUMER = call_consumer(2, 1)


def _control_world(case_id: str, results: tuple[ToolResultRecord, ...],
                   with_user: bool = False) -> tuple[CaseV5, ArmRunV5]:
    """The carriers are the typed `spans_real` tags of the results, which is the
    slot evidence the mock writes; no mention is needed to name them."""
    case = _case_world(case_id, (USER_ITEM, SEED_ONE) if with_user else (SEED_ONE,))
    run = _with_calls(_run(case_id), _CONTROL_CALLS, _CONTROL_TURNS)
    return case, _with_results(run, results)


def _binding(case: CaseV5, run: ArmRunV5, item_id: str) -> causal_hops._Binding:
    return causal_hops._bind(case, run, item_id, _CONTROL_CONSUMER)


def check_binding_branch_order_controls() -> None:
    """The verdict each neighbour MUST keep, so the fix cannot overshoot.

    A fix that dropped the `attributed` branch entirely, or that read an unknown
    carrier as sufficient for `ambiguous` (or as absent for `user_provided`), is
    red on one of these rows."""
    rows: list[tuple[str, str, str]] = []

    case, run = _control_world("cx-ctl-one",
                               (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),))
    rows.append(("one proved carrier", "attributed", _binding(case, run, "p9").status))

    case, run = _control_world("cx-ctl-two",
                               (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),
                                _result_carrying(1, 0, "p9", "Смирнова Анна", FAKE_ONE)))
    rows.append(("two proved carriers", "ambiguous", _binding(case, run, "p9").status))

    case, run = _control_world("cx-ctl-unknown",
                               (_result_carrying(0, 1, "p9", "Смирнова Анна", FAKE_ONE),))
    rows.append(("one unprovable carrier", "not_identifiable", _binding(case, run, "p9").status))

    case, run = _control_world("cx-ctl-mixed",
                               (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),
                                _result_carrying(1, 1, "p9", "Смирнова Анна", FAKE_ONE)))
    rows.append(("proved + unprovable", "not_identifiable", _binding(case, run, "p9").status))

    case, run = _control_world("cx-ctl-later",
                               (_result_carrying(0, 2, "p9", "Смирнова Анна", FAKE_ONE),))
    rows.append(("later-only carrier", "unattributed", _binding(case, run, "p9").status))

    case, run = _control_world("cx-ctl-user-avail",
                               (_result_carrying(0, 0, "p1", "Иванова Елена", USER_FAKE),),
                               with_user=True)
    rows.append(("user copy + proved carrier", "ambiguous", _binding(case, run, "p1").status))

    case, run = _control_world("cx-ctl-user-unknown",
                               (_result_carrying(0, 1, "p1", "Иванова Елена", USER_FAKE),),
                               with_user=True)
    rows.append(("user copy + unprovable carrier", "not_identifiable",
                 _binding(case, run, "p1").status))

    wrong = [f"{label}: {got}, want {want}" for label, want, got in rows if got != want]
    assert not wrong, "; ".join(wrong)
    print("causal_hops: branch-order controls -> " + ", ".join(
        f"{label}={got}" for label, _want, got in rows))


# --- check 9: value, form, residual and joint where measurable ----------------------------

def check_residual_is_measured_apart() -> None:
    case = _case_world("cx-residual", (SEED_ONE,))
    calls = (_call(FIND, {"query": "клиент"}, {"query": "клиент"}, {}, "", 0),
             _call(SMS, {"text": f"{FAKE_ONE}, заказ принят"},
                   {"text": f"{FAKE_ONE}, заказ принят"}, {}, "", 1))
    run = _with_calls(_run("cx-residual"), calls, (0, 1))
    run = _with_results(run, (_result_carrying(0, 0, "p9", "Смирнова Анна", FAKE_ONE),))
    run = _with_mentions(run, (_mention("p9", -1, 0, FAKE_ONE),))
    run = _with_subs(run, {"p9": FAKE_ONE})
    run = replace(run, model_trace=_trace(
        (_response(1, 0, 0), _response(2, 1, 1)), (1, 2)))
    event = _one(causal_events(case, run).events, "template", "p9")
    assert event.attributed is True and event.residual is True
    assert event.value_ok is False, "a fake the customer received is not a value pass"
    line = next(one for one in aggregate((causal_events(case, run),)).by_surface
                if one.key == "template")
    assert line.attributed == 1 and line.residual == 1 and line.joint_ok == 0
    # `value_ok`/`form_ok`/`residual` are not gated by the status: the aggregate
    # divides them by ATTRIBUTED emissions, and the event keeps the reading.
    print("causal_hops: residual measured apart from the value; joint is not bought back")


def check_no_events_without_evidence() -> None:
    """A call that carried nothing, and a reply with no substitute, produce no
    event at all — an empty denominator is not a measured zero."""
    case = _case_world("cx-empty", (USER_ITEM,))
    run = _with_calls(_run("cx-empty"),
                      (_call(FIND, {"query": "заказ 42"}, {"query": "заказ 42"}, {}, "", 0),), (0,))
    run = _with_replies(run, "Готово.", "Готово.", "")
    run = replace(run, model_trace=_trace((_response(1, 0, 0),), (1,)))
    observed = causal_events(case, run)
    assert observed.events == ()
    result = aggregate((observed,))
    assert result.events_total == 0 and result.by_surface == ()
    assert result.overall.candidates == 0 and result.overall.attributed == 0
    print("causal_hops: no evidence -> no event, and no surface line at 0/0")


def main() -> int:
    check_user_datum_after_unrelated_tool()
    check_first_and_second_result()
    check_two_calls_of_one_response()
    check_summary_template_and_chain_edge()
    check_archived_trace_is_not_identifiable()
    check_future_result_is_unavailable()
    check_unknown_carrier_outranks_a_proved_one()
    check_binding_branch_order_controls()
    check_residual_is_measured_apart()
    check_no_events_without_evidence()
    print(f"causal_hops: PASS (estimator={ESTIMATOR_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
