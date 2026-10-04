"""`actual_hops.py` pinned: ACTUAL OUT crossings, strict identity, independent form.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_actual_hops

Each check fails on the optimistic reading it replaces:

  * an action that happened at turn 5 is NOT `absent` because the case declared
    it at turn 7 (the old observer's `absent` is asserted beside it);
  * a harmless clarification, and reordering independent calls, move nothing;
  * a repeated call stays two events;
  * two people — and two people sharing a surname — are `ambiguous`; a
    4-character prefix («Иванов» vs «Иваненко») attributes nothing;
  * a mention the agent had not read yet (a later result, a later message) is
    not evidence, and neither is the run's future mint record;
  * two records of the SAME entity collapse; the same identity with a DIFFERENT
    value does not (no silent min-id pick);
  * a partial-role leaf needs its exact typed part; unresolved stays visible;
  * an unchanged identity leaf no mention explains is `unattributed`, while an
    enum, a quantity and a generic part are `not_applicable`;
  * the restored value never chooses the identity;
  * a gateway that masks nothing prints zero on value/form/joint;
  * FORM IS INDEPENDENT of the value: a wrong value can carry a form pass, and
    that pass is not a joint pass;
  * a real value of ANOTHER entity beside a clean fake is `mixed`, not matched;
  * `residual` is inside the joint denominator; the event id carries no turn;
  * a GENERIC-role word the customer's own values carry chooses no identity,
    while the MINTED part beside it still names its owner (v12);
  * `residual` is a property of the LEAF even after the identity RESOLVES:
    another item's standing fake is not hidden by the winner's clean restoration;
  * the VALUE column does not charge the tool's notation: the real address
    returned as a joined «Красноярск Энгельса 37» is a match, while a different
    or truncated street, a wrong house and another entity's address are not (v13).
"""
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii4.compare import ObservedCall
from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import FieldSpec
from bench.agentpii5.actual_hops import (
    ACTUAL_STATUSES,
    CANDIDATE_STATUSES,
    ESTIMATOR_VERSION,
    ActualEvent,
    ActualRunObservation,
    _minted_substitute_stands,
    actual_events,
    aggregate,
    own_stems_of,
    render,
)
from bench.agentpii5.contracts import ArmRunV5, CaseV5, Hop, MentionRecord, ModelResponse, ModelTrace, ToolResultRecord
from bench.agentpii5.fixtures import (
    REAL_NAME,
    _call,
    _case,
    _hop,
    _in_message,
    _in_seed,
    _item,
    _run,
    _with_calls,
    _with_mentions,
    _with_subs,
)
from bench.agentpii5.form import form_match
from bench.agentpii5.observe import observe

# --- the small world every check is built in ------------------------------------------

FAKE_ONE = "Пахомова Ольга"           # the substitute of p1
FAKE_TWO = "Пахомова Анна"            # another person whose fake shares the surname
FAKE_TWO_DISTINCT = "Сидорова Вера"   # ...and one that shares nothing
OTHER_REAL = "Смирнова Анна"
REAL_PHONE = "+79164021187"
REAL_PHONE_B = "+79261234567"
REAL_PHONE_C = "+79065943442"
FAKE_PHONE = "+79990001122"
FAKE_PHONE_B = "+79991112233"
UPSERT = "crm_upsert_contact"
SMS = "notify_sms"


def _one() -> PiiItem:
    """The customer of the dialogue, in a message: surname + given."""
    return _item("p1", "NAME", "Иванова Елена", "Иванова Елена", "i1", _in_message(0, 0, 13))


def _two() -> PiiItem:
    """The second person, reached through a seed record (a tool result)."""
    return _item("p9", "NAME", OTHER_REAL, OTHER_REAL, "i2", _in_seed("s2", "name"))


def _phone() -> PiiItem:
    return _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 20, 32))


def _declared_out(turn: int) -> Hop:
    """An OUT/tool_arg hop the corpus SCHEDULED at `turn`."""
    return _hop("OUT", "tool_arg", "p1", 1, turn, UPSERT, 0, -1, "contact.last_name")


def _mention(item_id: str, msg: int, result_seq: int, substitute: str) -> MentionRecord:
    return MentionRecord(item_id=item_id, msg=msg, result_seq=result_seq,
                         substitute=substitute, request_index=1)


def _run_with(case_id: str, subs: tuple[tuple[str, str], ...],
              mentions: tuple[MentionRecord, ...],
              calls: tuple[ObservedCall, ...], turns: tuple[int, ...]) -> ArmRunV5:
    run = _with_calls(_run(case_id), calls, turns)
    run = _with_mentions(run, mentions)
    return _with_subs(run, dict(subs))


def _upsert_call(seq: int, path: str, written: str, restored: str) -> ObservedCall:
    """One `crm_upsert_contact` call carrying ONE leaf, at `path`."""
    head, leaf = path.split(".", 1)
    return _call(UPSERT, {head: {leaf: written}}, {head: {leaf: restored}}, {}, "", seq)


def _sms_call(seq: int, written: str, restored: str) -> ObservedCall:
    return _call(SMS, {"number": FAKE_PHONE, "text": written, "sign": "SMS Aero"},
                 {"number": REAL_PHONE, "text": restored, "sign": "SMS Aero"}, {}, "", seq)


def _by_id(observation: ActualRunObservation) -> dict[str, ActualEvent]:
    return {event.event_id: event for event in observation.events}


def _events_at(observation: ActualRunObservation, path: str) -> tuple[ActualEvent, ...]:
    """Every actual event of one dotted leaf."""
    return tuple(event for event in observation.events if event.path == path)


def _candidates(observation: ActualRunObservation) -> tuple[ActualEvent, ...]:
    return tuple(event for event in observation.events if event.status in CANDIDATE_STATUSES)


def _one_event(case: CaseV5, run: ArmRunV5) -> ActualRunObservation:
    return actual_events(case, run)


def _statuses(observation: ActualRunObservation) -> tuple[tuple[str, str, bool, bool], ...]:
    return tuple(sorted((event.path, event.status, event.value_ok, event.form_ok)
                        for event in _candidates(observation)))


# --- 1. an action that happened at turn 5 is not `absent` at turn 7 --------------------

def test_actual_crossing_is_not_absent_at_another_turn() -> list[str]:
    case = _case("t1", "sequential_chain", (REAL_NAME,), (_one(),), (_declared_out(7),))
    run = _run_with("t1", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                    (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (5,))
    events = actual_events(case, run).events
    problems: list[str] = []
    if len(events) != 1:
        return [f"expected ONE actual crossing, found {len(events)}: {events}"]
    one = events[0]
    if one.call_turn != 5:
        problems.append(f"the event must carry the ACTUAL turn 5, not the declared 7: {one.call_turn}")
    if one.status != "matched" or one.item_id != "p1":
        problems.append(f"the crossing must be attributed to p1 and matched: {one.status}/{one.item_id}")
    if "absent" in ACTUAL_STATUSES:
        problems.append("the actual estimator has no `absent`")
    # THE OTHER HALF: the historical observer prints `absent` for the declared
    # turn-7 hop on the same records — the artefact this estimator is additive to.
    declared = [hop.status for hop in observe(case, run, None, None).hops
                if hop.declared and hop.hop.kind == "OUT" and hop.hop.tool_name == UPSERT]
    if declared != ["absent"]:
        problems.append(f"the historical observer should mark the declared turn-7 hop absent: {declared}")
    return problems


# --- 2. a harmless clarification moves nothing ----------------------------------------

def test_harmless_clarification_is_invariant() -> list[str]:
    plain = _case("t2a", "sequential_chain", (REAL_NAME,), (_one(),), ())
    run_a = _run_with("t2a", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                      (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    clarified = _case("t2b", "sequential_chain", (REAL_NAME, "И ещё: уточните адрес"),
                      (_one(),), ())
    run_b = _run_with("t2b", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                      (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (1,))
    left, right = _statuses(_one_event(plain, run_a)), _statuses(_one_event(clarified, run_b))
    problems: list[str] = []
    if left != right:
        problems.append(f"a clarification changed the measurement: {left} != {right}")
    # CAN-FAIL: a mention the agent had not read yet leaves the crossing unresolved.
    future = _run_with("t2c", (("p1", FAKE_ONE),), (_mention("p1", 5, -1, FAKE_ONE),),
                       (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (1,))
    unresolved = _statuses(_one_event(
        _case("t2c", "sequential_chain", (REAL_NAME, "x"), (_one(),), ()), future))
    if unresolved == right:
        problems.append("a mention at message 5 must NOT be usable by a call at turn 1")
    return problems


# --- 3. reordered independent calls move nothing ---------------------------------------

def test_reordered_independent_actions_are_invariant() -> list[str]:
    case = _case("t3", "parallel", (REAL_NAME,), (_one(), _two()), ())
    subs = (("p1", FAKE_ONE), ("p9", FAKE_TWO_DISTINCT))
    mentions = (_mention("p1", 0, -1, FAKE_ONE), _mention("p9", -1, 1, FAKE_TWO_DISTINCT))
    first = _upsert_call(3, "contact.last_name", "Пахомова", "Иванова")
    second = _upsert_call(4, "contact.name_latin", FAKE_TWO_DISTINCT, OTHER_REAL)
    left = {event.event_id: (event.status, event.item_id, event.value_ok, event.form_ok)
            for event in actual_events(case, _run_with("t3", subs, mentions, (first, second),
                                                       (4, 4))).events}
    right = {event.event_id: (event.status, event.item_id, event.value_ok, event.form_ok)
             for event in actual_events(case, _run_with("t3", subs, mentions, (second, first),
                                                        (4, 4))).events}
    if left != right:
        return [f"reordering independent calls changed the events: {left} != {right}"]
    return []


# --- 4. a repeated call is not silently merged -----------------------------------------

def test_repeated_call_is_not_merged() -> list[str]:
    case = _case("t4", "retry_same_tool", (REAL_NAME,), (_one(),), ())
    run = _run_with("t4", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                    (_upsert_call(5, "contact.last_name", "Пахомова", "Иванова"),
                     _upsert_call(20, "contact.last_name", "Пахомова", "Иванова")), (4, 9))
    events = _candidates(_one_event(case, run))
    problems: list[str] = []
    if len(events) != 2:
        problems.append(f"two actual calls are two events, found {len(events)}")
    if len({event.event_id for event in events}) != len(events):
        problems.append("the two events share an id: a repeat was merged away")
    if {event.call_seq for event in events} != {5, 20}:
        problems.append(f"each event carries its own call seq: {[e.call_seq for e in events]}")
    return problems


# --- 5. two people, and two people sharing a part, are ambiguous -----------------------

def test_two_people_are_ambiguous() -> list[str]:
    case = _case("t5", "parallel", (REAL_NAME,), (_one(), _two(), _phone()), ())
    written = f"{FAKE_ONE} или {FAKE_TWO_DISTINCT}"
    run = _run_with("t5", (("p1", FAKE_ONE), ("p9", FAKE_TWO_DISTINCT), ("p2", FAKE_PHONE)),
                    (_mention("p1", 0, -1, FAKE_ONE),
                     _mention("p9", 0, -1, FAKE_TWO_DISTINCT),
                     _mention("p2", 0, -1, FAKE_PHONE)),
                    (_sms_call(3, f"Клиент {written}", f"Клиент {FAKE_ONE} или {OTHER_REAL}"),), (0,))
    events = _events_at(_one_event(case, run), "text")
    if len(events) != 1 or events[0].status != "ambiguous":
        return [f"two identities in one leaf must be ambiguous: {[e.status for e in events]}"]
    if set(events[0].candidate_ids) != {"p1", "p9"}:
        return [f"both candidates must stay visible: {events[0].candidate_ids}"]
    return []


def test_two_people_sharing_a_part_are_ambiguous() -> list[str]:
    """The surname alone cannot choose between two people who wear it."""
    case = _case("t5b", "parallel", (REAL_NAME,), (_one(), _two()), ())
    run = _run_with("t5b", (("p1", FAKE_ONE), ("p9", FAKE_TWO)),
                    (_mention("p1", 0, -1, FAKE_ONE), _mention("p9", 0, -1, FAKE_TWO)),
                    (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    events = _candidates(_one_event(case, run))
    if len(events) != 1 or events[0].status != "ambiguous":
        return [f"a shared surname must be ambiguous: {[e.status for e in events]}"]
    return []


# --- 6. a mention the agent had not yet read is not evidence ---------------------------

def test_a_later_tool_result_is_not_usable_yet() -> list[str]:
    case = _case("t6", "sequential_chain", (REAL_NAME,), (_one(), _two()), ())
    problems: list[str] = []
    later = _run_with("t6", (("p9", FAKE_TWO_DISTINCT),),
                      (_mention("p9", -1, 9, FAKE_TWO_DISTINCT),),
                      (_upsert_call(9, "contact.name_latin", FAKE_TWO_DISTINCT, OTHER_REAL),), (0,))
    after = _run_with("t6", (("p9", FAKE_TWO_DISTINCT),),
                      (_mention("p9", -1, 9, FAKE_TWO_DISTINCT),),
                      (_upsert_call(10, "contact.name_latin", FAKE_TWO_DISTINCT, OTHER_REAL),), (1,))
    after = replace(after, tool_results=(ToolResultRecord(
        tool_name="crm_search", seq=9, call_ordinal=0, turn=0,
        return_form="single", text_real=OTHER_REAL, text_masked=FAKE_TWO_DISTINCT,
        spans_real={}, pieces=(), forced=False),))
    before_events = _candidates(_one_event(case, later))
    after_events = _candidates(_one_event(case, after))
    if not before_events or before_events[0].status == "matched":
        problems.append(f"a result at seq 9 cannot justify a call at seq 9: "
                        f"{[e.status for e in before_events]}")
    if not after_events or after_events[0].status != "matched":
        problems.append(f"the same result at seq 9 must justify a call at seq 10: "
                        f"{[e.status for e in after_events]}")
    return problems


def test_same_turn_result_is_not_proven_available() -> list[str]:
    """Sequential execution does not prove separate model response batches."""
    case = _case("batch", "sequential_chain", (REAL_NAME,), (_two(),), ())
    run = _run_with("batch", (("p9", FAKE_TWO_DISTINCT),),
                    (_mention("p9", -1, 9, FAKE_TWO_DISTINCT),),
                    (_upsert_call(10, "contact.name_latin", FAKE_TWO_DISTINCT, OTHER_REAL),), (0,))
    run = replace(run, tool_results=(ToolResultRecord(
        tool_name="crm_search", seq=9, call_ordinal=0, turn=0,
        return_form="single", text_real=OTHER_REAL, text_masked=FAKE_TWO_DISTINCT,
        spans_real={}, pieces=(), forced=False),))
    event = actual_events(case, run).events[0]
    if event.status != "not_identifiable" or event.attributed or event.value_ok:
        return [f"same-turn result credited without response-batch evidence: {event}"]
    missing = actual_events(case, replace(run, tool_results=())).events[0]
    if missing.status != "not_identifiable":
        return [f"missing result record silently proves availability: {missing}"]
    return []


def test_response_trace_proves_only_prior_response_results() -> list[str]:
    case = _case("traced", "sequential_chain", (REAL_NAME,), (_two(),), ())
    first = _call("crm_search", {}, {}, {}, "", 1)
    second = _upsert_call(2, "contact.name_latin", FAKE_TWO_DISTINCT, OTHER_REAL)
    run = _run_with("traced", (("p9", FAKE_TWO_DISTINCT),),
                    (_mention("p9", -1, 1, FAKE_TWO_DISTINCT),), (first, second), (0, 0))
    run = replace(run, tool_results=(ToolResultRecord(
        tool_name="crm_search", seq=1, call_ordinal=0, turn=0,
        return_form="single", text_real=OTHER_REAL, text_masked=FAKE_TWO_DISTINCT,
        spans_real={}, pieces=(), forced=False),))
    initial = ModelResponse(request=1, turn=0, available_results=0, raw="", restored="")
    later = ModelResponse(request=2, turn=0, available_results=1, raw="", restored="")
    sequential = replace(run, model_trace=ModelTrace(responses=(initial, later), call_requests=(1, 2)))
    batched = replace(run, model_trace=ModelTrace(responses=(initial,), call_requests=(1, 1)))
    good = _candidates(actual_events(case, sequential))
    uncertain = _candidates(actual_events(case, batched))
    problems: list[str] = []
    if len(good) != 1 or good[0].status != "matched":
        problems.append(f"a recorded later response must see result 1: {good}")
    if len(uncertain) != 1 or uncertain[0].status != "not_identifiable":
        problems.append(f"same response must not see its own result: {uncertain}")
    return problems


def test_future_minted_parts_are_not_evidence() -> list[str]:
    """The run's mint record is written from everything the arm ever saw.

    A leaf that carries a fake the agent had NOT yet read must not be explained
    by the run's final mint — that is the future used as evidence for the past.
    """
    case = _case("t6b", "sequential_chain", (REAL_NAME,), (_phone(),), ())
    future = _run_with("t6b", (("p2", FAKE_PHONE_B),), (_mention("p2", 0, -1, FAKE_PHONE),),
                       (_call(SMS, {"number": FAKE_PHONE_B}, {"number": FAKE_PHONE_B}, {}, "", 3),),
                       (0,))
    # The full-run record names the FUTURE fake, with its parts, as
    # `compare.substitutes_for` writes them.
    future = replace(future, base=replace(future.base, substitutes={
        "p2": (FAKE_PHONE_B, {"digits": "9991112233"})}))
    problems: list[str] = []
    events = _candidates(_one_event(case, future))
    if not events or events[0].status != "unattributed":
        problems.append(f"the run's future mint must not explain the leaf: "
                        f"{[e.status for e in events]}")
    read = _run_with("t6b", (("p2", FAKE_PHONE),), (_mention("p2", 0, -1, FAKE_PHONE),),
                     (_call(SMS, {"number": FAKE_PHONE}, {"number": REAL_PHONE}, {}, "", 3),), (0,))
    ok = _candidates(_one_event(case, read))
    if not ok or ok[0].status != "matched":
        problems.append(f"the fake the agent HAD read must still match: {[e.status for e in ok]}")
    return problems


# --- 7. entity = identity + type + value + parts ---------------------------------------

def test_semantic_duplicate_items_are_one_entity() -> list[str]:
    twin = _item("p1b", "NAME", "Иванова Елена", "Иванова Елена", "i1", _in_message(0, 0, 13))
    case = _case("t7", "single", (REAL_NAME,), (_one(), twin), ())
    run = _run_with("t7", (("p1", FAKE_ONE), ("p1b", FAKE_ONE)),
                    (_mention("p1", 0, -1, FAKE_ONE), _mention("p1b", 0, -1, FAKE_ONE)),
                    (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    events = _candidates(_one_event(case, run))
    problems: list[str] = []
    if len(events) != 1 or events[0].status != "matched":
        problems.append(f"two records of ONE entity must resolve: "
                        f"{[(e.status, e.candidate_ids) for e in events]}")
    elif events[0].item_id != "p1":
        problems.append(f"the representative is the lowest id, found {events[0].item_id!r}")
    # CAN-FAIL: a DIFFERENT person behind the same surname IS ambiguous.
    other = _item("p1b", "NAME", OTHER_REAL, OTHER_REAL, "i9", _in_message(0, 0, 13))
    case2 = _case("t7b", "single", (REAL_NAME,), (_one(), other), ())
    run2 = _run_with("t7b", (("p1", FAKE_ONE), ("p1b", FAKE_TWO)),
                     (_mention("p1", 0, -1, FAKE_ONE), _mention("p1b", 0, -1, FAKE_TWO)),
                     (_upsert_call(3, "contact.last_name", "Пахомова", "Ивановой"),), (0,))
    events2 = _candidates(_one_event(case2, run2))
    if len(events2) != 1 or events2[0].status != "ambiguous":
        problems.append(f"two entities behind one surname must be ambiguous: "
                        f"{[e.status for e in events2]}")
    return problems


def test_same_identity_different_value_is_ambiguous() -> list[str]:
    """One person, two phone values: the leaf carries both fakes.

    Keyed on `identity` alone the two records were one entity, the lowest id was
    chosen, and the leaf scored a clean match over a second value of the same
    person that was never measured. Type and value are part of the entity.
    """
    second = _item("p2b", "PHONE", REAL_PHONE_B, REAL_PHONE_B, "i1", _in_seed("s2", "phone"))
    case = _case("t7c", "single", (REAL_NAME,), (_phone(), second), ())
    written = f"звоните {FAKE_PHONE} или {FAKE_PHONE_B}"
    restored = f"звоните {REAL_PHONE} или {REAL_PHONE_B}"
    run = _run_with("t7c", (("p2", FAKE_PHONE), ("p2b", FAKE_PHONE_B)),
                    (_mention("p2", 0, -1, FAKE_PHONE), _mention("p2b", 0, -1, FAKE_PHONE_B)),
                    (_call(SMS, {"text": written}, {"text": restored}, {}, "", 3),), (0,))
    events = _candidates(_one_event(case, run))
    problems: list[str] = []
    if len(events) != 1 or events[0].status != "ambiguous":
        problems.append(f"two values of one identity must not pick the min id: "
                        f"{[(e.status, e.item_id) for e in events]}")
    elif events[0].item_id:
        problems.append(f"an ambiguous event names no single item, got {events[0].item_id!r}")
    elif set(events[0].candidate_ids) != {"p2", "p2b"}:
        problems.append(f"both values must stay visible: {events[0].candidate_ids}")
    return problems


# --- 8. a 4-character prefix is not identity ------------------------------------------

def test_a_four_letter_prefix_is_not_identity() -> list[str]:
    """«Иванов» must not attribute to «Иваненко».

    The real surname is a third string, so the leaf is neither the fake nor a
    leak: with a prefix rule it matched the fake by its first four letters.
    """
    owner = _item("p1", "NAME", "Смирнов Пётр", "Смирнов Пётр", "i1", _in_message(0, 0, 12))
    case = _case("t8b", "single", (REAL_NAME,), (owner,), ())
    problems: list[str] = []
    guessed = _run_with("t8b", (("p1", "Иваненко Пётр"),), (_mention("p1", 0, -1, "Иваненко Пётр"),),
                        (_upsert_call(3, "contact.last_name", "Иванов", "Иванов"),), (0,))
    events = _candidates(_one_event(case, guessed))
    if not events or events[0].status != "unattributed":
        problems.append(f"a four-letter prefix must not attribute: {[e.status for e in events]}")
    exact = _run_with("t8b", (("p1", "Иваненко Пётр"),), (_mention("p1", 0, -1, "Иваненко Пётр"),),
                      (_upsert_call(3, "contact.last_name", "Иваненко", "Смирнов"),), (0,))
    found = _candidates(_one_event(case, exact))
    if not found or found[0].status != "matched":
        problems.append(f"the exact part must still match: {[e.status for e in found]}")
    return problems


# --- 9. partial roles are exact; unresolved stays visible ------------------------------

def test_partial_role_needs_the_exact_part() -> list[str]:
    case = _case("t9", "single", (REAL_NAME,), (_one(),), ())
    problems: list[str] = []
    given = _run_with("t9", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                      (_upsert_call(3, "contact.last_name", "Ольга", "Елена"),), (0,))
    events = _candidates(_one_event(case, given))
    if not events or events[0].status != "unattributed":
        problems.append(f"the GIVEN name in a surname leaf must not match: "
                        f"{[e.status for e in events]}")
    surname = _run_with("t9", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                        (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    ok = _candidates(_one_event(case, surname))
    if not ok or ok[0].status != "matched":
        problems.append(f"the surname in a surname leaf must match: {[e.status for e in ok]}")
    return problems


def test_an_unattributed_crossing_stays_visible() -> list[str]:
    case = _case("t9b", "single", (REAL_NAME,), (_one(),), ())
    run = _run_with("t9b", (), (), (_upsert_call(3, "contact.name_latin", "Ромашка", "Заря"),), (0,))
    events = _candidates(_one_event(case, run))
    if len(events) != 1 or events[0].status != "unattributed" or events[0].candidate_ids:
        return [f"a changed leaf with no evidence is unattributed with no invented candidate: "
                f"{[(e.status, e.candidate_ids) for e in events]}"]
    return []


def test_unchanged_identity_leaf_without_evidence_is_unattributed() -> list[str]:
    """A future fake in an identity leaf is an unresolved crossing, not traffic."""
    case = _case("t9c", "single", (REAL_NAME,), (_one(),), ())
    future = _run_with("t9c", (("p1", FAKE_ONE),), (_mention("p1", 5, -1, FAKE_ONE),),
                       (_upsert_call(3, "contact.last_name", "Пахомова", "Пахомова"),), (0,))
    problems: list[str] = []
    events = _candidates(_one_event(case, future))
    if len(events) != 1 or events[0].status != "unattributed":
        problems.append(f"an unexplained identity leaf must stay a candidate: "
                        f"{[(e.path, e.status) for e in events]}")
    # ORDINARY CONTROLS: an enum and a plain leaf are not defects.
    ordinary = _run_with("t9c", (), (),
                         (_call(UPSERT, {"id": "c-1", "contact": {"gender": "F"}},
                                {"id": "c-1", "contact": {"gender": "F"}}, {}, "", 3),), (0,))
    for event in _one_event(case, ordinary).events:
        if event.status != "not_applicable":
            problems.append(f"{event.path} is ordinary traffic, got {event.status!r}")
    if _candidates(_one_event(case, ordinary)):
        problems.append("ordinary leaves must not enter a denominator")
    return problems


# --- 10. the restored value never chooses the identity ---------------------------------

def test_restored_value_does_not_choose_identity() -> list[str]:
    case = _case("t10", "single", (REAL_NAME,), (_one(), _two()), ())
    run = _run_with("t10", (("p1", FAKE_ONE), ("p9", FAKE_TWO_DISTINCT)),
                    (_mention("p1", 0, -1, FAKE_ONE),
                     _mention("p9", -1, 1, FAKE_TWO_DISTINCT)),
                    (_upsert_call(3, "contact.name_latin", FAKE_ONE, OTHER_REAL),), (0,))
    events = _candidates(_one_event(case, run))
    problems: list[str] = []
    if len(events) != 1:
        return [f"expected one event, found {len(events)}"]
    one = events[0]
    if one.item_id != "p1":
        problems.append(f"the WRITTEN side chooses the identity; the restored value is p9's. "
                        f"Got {one.item_id!r}")
    if one.status != "value_wrong" or one.value_ok:
        problems.append(f"p9's real value is not p1's expected value: {one.status!r}")
    return problems


def test_ordinary_leaf_is_not_a_defect() -> list[str]:
    case = _case("t11", "single", (REAL_NAME,), (_one(),), ())
    call = _call(UPSERT, {"id": "c-1", "contact": {"gender": "F"}},
                 {"id": "c-1", "contact": {"gender": "F"}}, {}, "", 3)
    run = _run_with("t11", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),), (call,), (0,))
    observation = _one_event(case, run)
    if any(event.status != "not_applicable" for event in observation.events):
        return [f"ordinary leaves must be not_applicable: "
                f"{[(e.path, e.status) for e in observation.events]}"]
    return []


# --- 11. a gateway that masks nothing cannot look perfect ------------------------------

def test_no_mask_gateway_is_not_perfect() -> list[str]:
    case = _case("t12", "single", (REAL_NAME,), (_one(), _phone()), ())
    call = _call(UPSERT, {"id": "c-1", "contact": {"last_name": "Иванова", "phone": REAL_PHONE}},
                 {"id": "c-1", "contact": {"last_name": "Иванова", "phone": REAL_PHONE}},
                 {}, "", 3)
    run = _run_with("t12", (), (), (call,), (0,))
    observation = _one_event(case, run)
    report = aggregate((observation,))
    problems: list[str] = []
    statuses = {event.path: event.status for event in observation.events}
    if statuses.get("contact.last_name") != "unmasked_known":
        problems.append(f"the real surname reached the tool: {statuses}")
    if statuses.get("contact.phone") != "unmasked_known":
        problems.append(f"the real phone reached the tool: {statuses}")
    if statuses.get("id") != "not_applicable":
        problems.append(f"an order id is no PII defect: {statuses}")
    if report.overall.candidates != 2 or report.not_applicable != 1:
        problems.append(f"only real PII leaves may be counted: candidates="
                        f"{report.overall.candidates} na={report.not_applicable}")
    if report.overall.value_ok or report.overall.form_ok or report.overall.joint_ok:
        problems.append(f"a no-mask gateway may not pass a line: {report.overall}")
    if report.overall.count("unmasked_known") != 2:
        problems.append(f"both real values must be visible: {report.overall.statuses}")
    return problems


# --- 12. form is independent of the value ---------------------------------------------

def test_form_pass_does_not_imply_identity_pass() -> list[str]:
    """A wrong real value CAN carry a form pass — and it is not a correctness pass.

    p9's real name arrives where p1's fake was written. The value is wrong. The
    notation is identical (two title-case nominative names), the form comparator
    says so, and the joint line must still be zero. A form pass that could be
    read as success is what M0 §6.4 forbids.
    """
    case = _case("t13", "single", (REAL_NAME,), (_one(), _two()), ())
    run = _run_with("t13", (("p1", FAKE_ONE), ("p9", FAKE_TWO_DISTINCT)),
                    (_mention("p1", 0, -1, FAKE_ONE),
                     _mention("p9", -1, 1, FAKE_TWO_DISTINCT)),
                    (_upsert_call(3, "contact.name_latin", FAKE_ONE, OTHER_REAL),), (0,))
    observation = _one_event(case, run)
    report = aggregate((observation,))
    problems: list[str] = []
    if report.overall.candidates != 1:
        return [f"expected one candidate, found {report.overall.candidates}"]
    one = observation.events[0]
    naive = form_match("NAME", OTHER_REAL, FAKE_ONE)
    if not naive.same:
        problems.append("fixture defect: the two notations were meant to be the same")
    if one.status != "value_wrong" or one.value_ok:
        problems.append(f"another person's value is a wrong value: {one.status!r}")
    if not one.form_measured or not one.form_ok:
        problems.append(f"the notation IS the same, so the form is measured and passes: "
                        f"form_ok={one.form_ok} measured={one.form_measured}")
    if report.overall.value_ok != 0 or report.overall.form_ok != 1 or report.overall.joint_ok != 0:
        problems.append(f"a form pass must not become a joint pass: value="
                        f"{report.overall.value_ok} form={report.overall.form_ok} "
                        f"joint={report.overall.joint_ok}")
    if report.overall.form_unmeasured != 0:
        problems.append("this form was measurable and must not be reported as unmeasured")
    # AND THE FORM COLUMN DISCRIMINATES: a different grammatical case is a miss.
    dative = _run_with("t13", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                       (_upsert_call(3, "contact.name_latin", FAKE_ONE, "Ивановой Елене"),), (0,))
    other = _one_event(case, dative).events[0]
    if not other.form_measured or other.form_ok:
        problems.append(f"a different case is a form miss: form_ok={other.form_ok} "
                        f"differs={other.form_differs}")
    return problems


def test_a_wrong_value_and_a_wrong_case_stay_separate() -> list[str]:
    """`joint` needs value AND form AND no residual — never one of them."""
    case = _case("t13b", "single", (REAL_NAME,), (_one(),), ())
    run = _run_with("t13b", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                    (_upsert_call(3, "contact.name_latin", FAKE_ONE, "Ивановой Елене"),), (0,))
    report = aggregate((_one_event(case, run),))
    problems: list[str] = []
    if report.overall.value_ok or report.overall.form_ok or report.overall.joint_ok:
        problems.append(f"neither a wrong value nor a wrong case may pass: value="
                        f"{report.overall.value_ok} form={report.overall.form_ok} "
                        f"joint={report.overall.joint_ok}")
    if report.overall.form_unmeasured != 0:
        problems.append("this form was measurable (own_pair narrowed both sides)")
    return problems


# --- 13. a hidden real value beside a clean fake is `mixed` ----------------------------

def test_mixed_real_value_beside_a_fake_is_not_a_pass() -> list[str]:
    other = _item("p2", "PHONE", REAL_PHONE_C, REAL_PHONE_C, "i2", _in_seed("s2", "phone"))
    case = _case("t14", "single", (REAL_NAME,), (_one(), other), ())
    subs = (("p1", FAKE_ONE), ("p2", FAKE_PHONE_B))
    mentions = (_mention("p1", 0, -1, FAKE_ONE), _mention("p2", -1, 1, FAKE_PHONE_B))
    mixed_text = f"Клиент {FAKE_ONE}, телефон {REAL_PHONE_C}"
    call = _call(SMS, {"text": mixed_text, "sign": "SMS Aero"},
                 {"text": mixed_text, "sign": "SMS Aero"}, {}, "", 3)
    observation = _one_event(case, _run_with("t14", subs, mentions, (call,), (0,)))
    report = aggregate((observation,))
    problems: list[str] = []
    events = _events_at(observation, "text")
    if len(events) != 1 or events[0].status != "mixed":
        problems.append(f"a clean fake beside another entity's REAL value is `mixed`: "
                        f"{[(e.status, e.written) for e in events]}")
    elif not {"p1", "p2"} <= set(events[0].candidate_ids):
        problems.append(f"both the fake's and the real's item must stay visible: "
                        f"{events[0].candidate_ids}")
    if events and (events[0].value_ok or events[0].form_ok):
        problems.append("a mixed leaf may not be a value or form pass")
    if report.overall.value_ok or report.overall.joint_ok:
        problems.append(f"a mixed leaf must not pass: {report.overall}")
    # POSITIVE CONTROL: the same shape without the unrelated real value resolves.
    clean = f"Клиент {FAKE_ONE}, телефон {FAKE_PHONE}"
    clean_call = _call(SMS, {"text": clean, "sign": "SMS Aero"},
                       {"text": f"Клиент Иванова Елена, телефон {REAL_PHONE}",
                        "sign": "SMS Aero"}, {}, "", 3)
    clean_events = _events_at(_one_event(case, _run_with("t14", subs, mentions, (clean_call,), (0,))),
                              "text")
    if not clean_events or clean_events[0].status != "matched":
        problems.append(f"the control must resolve cleanly: {[e.status for e in clean_events]}")
    return problems


# --- 14. residual, per-type, event id, generic parts, version --------------------------

def test_residual_is_in_the_joint_denominator() -> list[str]:
    case = _case("t15", "retry_same_tool", (REAL_NAME,), (_one(),), ())
    run = _run_with("t15", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                    (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),
                     _upsert_call(4, "contact.first_name", "Ольга", "Ольга")), (0, 0))
    report = aggregate((_one_event(case, run),))
    problems: list[str] = []
    if report.overall.candidates != 2:
        return [f"two leaves were crossed, found {report.overall.candidates}"]
    if report.overall.count("residual") != 1:
        problems.append(f"the fake that survived must be residual: {report.overall.statuses}")
    if report.overall.value_ok != 1 or report.overall.joint_ok != 1:
        problems.append(f"joint must be 1 of 2, not 1 of 1: value={report.overall.value_ok} "
                        f"joint={report.overall.joint_ok}")
    return problems


def test_per_type_aggregate_splits_by_type() -> list[str]:
    case = _case("t16", "single", (REAL_NAME,), (_one(), _phone()), ())
    call = _call(UPSERT, {"contact": {"last_name": "Пахомова", "phone": FAKE_PHONE}},
                 {"contact": {"last_name": "Иванова", "phone": REAL_PHONE}}, {}, "", 3)
    run = _run_with("t16", (("p1", FAKE_ONE), ("p2", FAKE_PHONE)),
                    (_mention("p1", 0, -1, FAKE_ONE), _mention("p2", 0, -1, FAKE_PHONE)),
                    (call,), (0,))
    report = aggregate((_one_event(case, run),))
    by_type = {one.pii_type: one for one in report.by_type}
    problems: list[str] = []
    if set(by_type) != {"NAME", "PHONE"}:
        problems.append(f"each type needs its own line: {sorted(by_type)}")
    for name in ("NAME", "PHONE"):
        if by_type.get(name) is None or by_type[name].value_ok != 1:
            problems.append(f"{name} must carry its own value count: {by_type.get(name)}")
    if not render(report):
        problems.append("the aggregate must render")
    return problems


def test_event_id_carries_no_turn() -> list[str]:
    case = _case("t17", "sequential_chain", (REAL_NAME,), (_one(),), ())
    early = _run_with("t17", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                      (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (5,))
    late = _run_with("t17", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                     (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (9,))
    left, right = _by_id(_one_event(case, early)), _by_id(_one_event(case, late))
    problems: list[str] = []
    if set(left) != set(right):
        problems.append(f"the same call in another turn keeps its id: {set(left)} != {set(right)}")
    one = next(iter(left.values()))
    for part in (str(one.call_seq), one.path, one.item_id):
        if part not in one.event_id:
            problems.append(f"the event id must name seq+field+item: {one.event_id!r} lacks {part!r}")
    return problems


def test_a_generic_part_is_not_an_unmasked_defect() -> list[str]:
    """A city a tool stores is not «the real value reached the consumer»."""
    loc = replace(_item("p7", "LOC", "торжок, проспект Энгельса, 48, кв. 169",
                        "торжок, проспект Энгельса, 48, кв. 169", "i1", _in_seed("s1", "address")),
                  parts={"city": "торжок", "street": "энгельса", "street_type": "проспект",
                         "house": "48", "flat": "169"})
    case = _case("t18", "single", (REAL_NAME,), (loc,), ())
    city_run = _run_with("t18", (("p7", "Сиреневая"),), (_mention("p7", 0, -1, "Сиреневая"),),
                         (_call(UPSERT, {"contact": {"address": {"city": "торжок"}}},
                                {"contact": {"address": {"city": "торжок"}}}, {}, "", 3),), (0,))
    problems: list[str] = []
    events = _events_at(_one_event(case, city_run), "contact.address.city")
    if len(events) != 1 or events[0].status != "not_applicable":
        problems.append(f"a settlement leaf is not a defect: {[(e.status, e.written) for e in events]}")
    # CAN-FAIL: the STREET of the same item, written real, is still a leak.
    street_run = _run_with("t18", (("p7", "Сиреневая"),), (_mention("p7", 0, -1, "Сиреневая"),),
                           (_call(UPSERT, {"contact": {"address": {"street": "Энгельса"}}},
                                  {"contact": {"address": {"street": "Энгельса"}}}, {}, "", 3),), (0,))
    found = _events_at(_one_event(case, street_run), "contact.address.street")
    if len(found) != 1 or found[0].status != "unmasked_known":
        problems.append(f"the real STREET must still be a leak: {[(e.status, e.written) for e in found]}")
    return problems


def test_version_is_declared_and_scope_is_out_calls() -> list[str]:
    problems: list[str] = []
    if not ESTIMATOR_VERSION or ESTIMATOR_VERSION == "m0":
        problems.append("the estimator must carry a version naming itself")
    if "not_applicable" not in ACTUAL_STATUSES or "not_applicable" in CANDIDATE_STATUSES:
        problems.append("not_applicable is a status and never a candidate")
    if "residual" not in CANDIDATE_STATUSES or "mixed" not in CANDIDATE_STATUSES:
        problems.append("residual and mixed are candidates and stay in the denominators")
    return problems


# --- the runner ------------------------------------------------------------------------

def test_short_numbers_do_not_attribute_without_a_role() -> list[str]:
    case = _case("short-numbers", "single", (REAL_NAME,), (_phone(),), ())
    fake = "+79992534112"
    values = {"patient": {"age": "25"}, "month": "11", "order_id": "34"}
    call = _call("clinic_book", values, values, {}, "", 3)
    run = _run_with("short-numbers", (("p2", fake),),
                    (_mention("p2", 0, -1, fake),), (call,), (0,))
    wrong = [event for event in actual_events(case, run).events
             if event.status != "not_applicable"]
    problems = [f"unrelated short number attributed: {event.path}/{event.status}"
                for event in wrong]
    # A full substitute in the wrong field remains observable, not exempt.
    full = _call("clinic_book", {"month": fake}, {"month": fake}, {}, "", 3)
    full_run = _run_with("short-numbers", (("p2", fake),),
                         (_mention("p2", 0, -1, fake),), (full,), (0,))
    if actual_events(case, full_run).events[0].status != "residual":
        problems.append("a full fake in an unexpected field disappeared")
    return problems


def test_phone_value_is_independent_of_notation() -> list[str]:
    case = _case("phone-notation", "single", (REAL_NAME,), (_phone(),), ())
    spoken = "восемь девятьсот шестнадцать сорок двадцать один восемнадцать семь"
    problems: list[str] = []
    for path in ("phone", "phones[0]"):
        for real in ("8 (916) 402-11-87", "9164021187", spoken):
            call = _upsert_call(3, "contact." + path, FAKE_PHONE, real)
            run = _run_with("phone-notation", (("p2", FAKE_PHONE),),
                            (_mention("p2", 0, -1, FAKE_PHONE),), (call,), (0,))
            event = actual_events(case, run).events[0]
            if not event.value_ok or event.form_ok:
                problems.append(f"same PHONE, different form must separate: {path}/{real}/{event.status}")
    return problems


def test_whole_and_declared_part_share_one_projection() -> list[str]:
    whole = _one()
    surname = replace(whole, id="p1-surname", value="Иванова", canonical="Иванова",
                      parts={"surname": "иванова"})
    case = _case("projection", "single", (REAL_NAME,), (whole, surname), ())
    run = _run_with("projection", (("p1", FAKE_ONE), (surname.id, "Пахомова")),
                    (_mention("p1", 0, -1, FAKE_ONE),
                     _mention(surname.id, 0, -1, "Пахомова")),
                    (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    event = actual_events(case, run).events[0]
    if event.status != "matched" or set(event.candidate_ids) != {"p1", surname.id}:
        return [f"whole and declared surname must share projection with both evidence ids: {event}"]
    return []


def test_conflicting_full_versions_do_not_collapse_on_shared_part() -> list[str]:
    changed = replace(_one(), id="p1-new", value="Иванова Анна", canonical="Иванова Анна",
                      parts={"surname": "иванова", "given": "анна"})
    case = _case("versioned-name", "single", (REAL_NAME,), (_one(), changed), ())
    run = _run_with("versioned-name", (("p1", FAKE_ONE), (changed.id, FAKE_TWO)),
                    (_mention("p1", 0, -1, FAKE_ONE), _mention(changed.id, 0, -1, FAKE_TWO)),
                    (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    event = actual_events(case, run).events[0]
    return [] if event.status == "ambiguous" else [f"conflicting versions collapsed: {event}"]


def test_role_does_not_reinterpret_another_type() -> list[str]:
    surname = replace(_one(), value="Иванова", canonical="Иванова", parts={"surname": "иванова"})
    case = _case("wrong-role", "single", (REAL_NAME,), (surname,), ())
    run = _run_with("wrong-role", (("p1", "Пахомова"),),
                    (_mention("p1", 0, -1, "Пахомова"),),
                    (_upsert_call(3, "contact.first_name", "Пахомова", "Иванова"),), (0,))
    event = actual_events(case, run).events[0]
    return [] if event.status == "unattributed" else [f"surname reinterpreted as given: {event}"]


# --- 15. M02-F1: the leak side separates a whole from a stem (review §4) ---------------

def _roleless_call(seq: int, written: str, restored: str) -> ObservedCall:
    """ONE role-less free-text leaf — `contact.name_latin` has no role, so the
    loose needle reading is the only one that can attribute this leaf."""
    return _call(UPSERT, {"contact": {"name_latin": written}},
                 {"contact": {"name_latin": restored}}, {}, "", seq)


def test_leak_side_separates_a_part_from_a_whole() -> list[str]:
    """THE REVIEW'S OWN COUNTEREXAMPLE, built from the fixture builders.

    A's substitute is `Пахомова Ольга`; B is another REAL person whose real
    surname happens to BE «Пахомова». In a role-less leaf the agent wrote A's
    FAKE surname and the gateway restored A's REAL one. The loose reading asked
    only «does a stem of B's real value stand in this text», charged B as
    `unmasked_known`, and named the wrong entity on a leaf the gateway handled
    correctly. The mechanism refuses that: a word two entities' values render at
    once is not a confident leak of the lower id, and B is never charged on the
    strength of a collision. What the leaf owes the reader is the truth about
    the WHOLE value — `matched` or `value_wrong` for A — so an ambiguity the
    collisions cannot resolve is `ambiguous`/`unattributed` and stays visible,
    never a silent pass and never the wrong person.
    """
    a = _one()
    b = _item("pb", "NAME", "Пахомова Анна", "Пахомова Анна", "i2", _in_seed("s2", "name"))
    case = _case("m02f1", "single", (REAL_NAME,), (a, b), ())
    subs = (("p1", FAKE_ONE), ("pb", FAKE_TWO_DISTINCT))
    mentions = (_mention("p1", 0, -1, FAKE_ONE), _mention("pb", -1, 1, FAKE_TWO_DISTINCT))
    problems: list[str] = []
    # GATEWAY RESTORES: the leaf is NOT a leak of pb, and it may not be a pass.
    restored = _events_at(_one_event(case, _run_with(
        "m02f1", subs, mentions, (_roleless_call(3, "Пахомова", "Иванова"),), (0,))), "contact.name_latin")
    if len(restored) != 1:
        return [f"expected one role-less event, found {[(e.path, e.status) for e in restored]}"]
    one = restored[0]
    if one.item_id == "pb":
        problems.append("pb is not the written side: it is the collision, not the crossing")
    if one.status in ("unmasked_known", "mixed"):
        problems.append(f"a correct restoration of a value cannot be {one.status!r}")
    if one.residual and one.item_id != "p1":
        problems.append(f"a residual may only be charged to the leaf's own substitute: {one.item_id!r}")
    # THE MECHANISM ITSELF, pinned where it is decided: «Пахомова» is a whole
    # rendering of p1's FAKE and of pb's real value at once, and NEITHER real
    # value may be charged on it. p1's real value is «Иванова Елена» and pb's is
    # the collision, so both readings must be False — the collision is not
    # evidence about either person's real datum.
    from bench.agentpii5.actual_hops import _written_has_real
    run = _run_with("m02f1", subs, mentions,
                    (_roleless_call(3, "Пахомова", "Иванова"),), (0,))
    for item in (a, b):
        if _written_has_real(item, None, case, run, "Пахомова", 3, 3):
            problems.append(f"{item.id}'s real value is not in «Пахомова»: the collision "
                            f"was charged as a leak")
    # GATEWAY DOES NOT RESTORE: the fake still stands, and pb is still not charged.
    kept = _events_at(_one_event(case, _run_with(
        "m02f1", subs, mentions, (_roleless_call(3, "Пахомова", "Пахомова"),), (0,))),
        "contact.name_latin")[0]
    if kept.item_id == "pb":
        problems.append("an unrestored collision is never charged to the other real person")
    if kept.status in ("unmasked_known",):
        problems.append(f"the fake standing is not a real-value leak: {kept.status!r}")
    return problems


def test_real_archive_whole_part_collisions_do_not_charge_the_wrong_entity() -> list[str]:
    """The two literal rows review §4 found on the saved 450, rebuilt compactly.

    FORBIDDEN MOVES ON THIS FIXTURE: reading `restored` to choose the entity,
    and turning the collision into a pass. The gateway restored BOTH leaves
    correctly; the point is only that the entity charged is the right one, and
    that the wrong one is not charged at all.
    """
    victim = _item("i8", "NAME", "васильев иван павлович", "васильев иван павлович", "p33",
                   _in_seed("s8", "name"))
    collider = _item("i2", "NAME", "иван", "иван", "p33", _in_seed("s2", "given"))
    initials_case = _case("m02-033", "single", (REAL_NAME,), (victim, collider), ())
    initials_run = _run_with(
        "m02-033",
        (("i8", "ершов вениамин ильич"), ("i2", "вениамин")),
        (_mention("i8", 0, -1, "ершов вениамин ильич"), _mention("i2", 0, -1, "вениамин")),
        (_call(UPSERT, {"contact": {"initials": "В. И."}},
               {"contact": {"initials": "И. П."}}, {}, "", 3),), (0,))

    surname = _item("i1", "NAME", "фёдорова", "фёдорова", "p34", _in_seed("s1", "name"))
    given = _item("i2", "NAME", "юлия", "юлия", "p34", _in_seed("s2", "given"))
    patronymic = _item("i3", "NAME", "викторовна", "викторовна", "p34", _in_seed("s3", "patronymic"))
    phone_fake = _item("i10", "PHONE", "8 909 813 55 15", "8 909 813 55 15", "p34",
                       _in_seed("s10", "phone"))
    patronymic_case = _case("m02-034", "single", (REAL_NAME,), (surname, given, patronymic, phone_fake), ())
    written = ("Получатель: Бирюкова Снежана Фёдоровна. Адрес: г. Чернь")
    restored = ("Получатель: Фёдорова Юлия Викторовна. Адрес: г. Чернь")
    patronymic_run = _run_with(
        "m02-034",
        (("i1", "бондаренко"), ("i2", "валентина"), ("i3", "дмитриевна"),
         ("i10", "8 922 331 03 22")),
        (_mention("i1", 0, -1, "бондаренко"), _mention("i2", 0, -1, "валентина"),
         _mention("i3", 0, -1, "дмитриевна"), _mention("i10", 0, -1, "8 922 331 03 22")),
        (_roleless_call(3, written, restored),), (0,))

    problems: list[str] = []
    for case, run, path, forbidden in (
            (initials_case, initials_run, "contact.initials", "i8"),
            (patronymic_case, patronymic_run, "contact.name_latin", "i1")):
        events = _events_at(_one_event(case, run), path)
        if not events:
            problems.append(f"{case.base.id}: the leaf vanished")
            continue
        one = events[0]
        if one.item_id == forbidden:
            problems.append(f"{case.base.id}: the wrong entity {forbidden} was charged ({one.status})")
        if one.status in ("unmasked_known", "mixed"):
            problems.append(f"{case.base.id}: a collision of a stem with REAL text became {one.status!r}")
        if one.status == "unmasked_known" and one.item_id:
            problems.append(f"{case.base.id}: a fabricate of one value was charged as a real leak "
                            f"of {one.item_id}")
    return problems


def test_true_mixed_case_stays_caught_and_prior_verdicts_hold() -> list[str]:
    """The MIXED pin, the negative control, and the conservative priors.

    A substitute of A and a REAL value of B standing in DIFFERENT spans of one
    leaf is a genuine mixed leaf and must stay caught. Refusing a stem is not a
    licence to stop catching a whole: the real value written `Иванова Елена`,
    the surname leaf, the two-people-same-surname ambiguity, the old/new value
    version and the unrelated short numbers keep their verdicts.
    """
    problems: list[str] = []
    mixed_other = _item("p2", "PHONE", REAL_PHONE_C, REAL_PHONE_C, "i2", _in_seed("s2", "phone"))
    case = _case("m02-pin", "single", (REAL_NAME,), (_one(), mixed_other), ())
    leaf = f"Клиент {FAKE_ONE}, телефон {REAL_PHONE_C}"
    call = _call(SMS, {"text": leaf, "sign": "SMS Aero"}, {"text": leaf, "sign": "SMS Aero"}, {}, "", 3)
    run = _run_with("m02-pin", (("p1", FAKE_ONE), ("p2", FAKE_PHONE_B)),
                    (_mention("p1", 0, -1, FAKE_ONE), _mention("p2", -1, 1, FAKE_PHONE_B)),
                    (call,), (0,))
    events = _events_at(_one_event(case, run), "text")
    if len(events) != 1 or events[0].status != "mixed":
        problems.append(f"a substitute beside another entity's REAL value is still mixed: "
                        f"{[(e.status, e.item_id) for e in events]}")
    elif not {"p1", "p2"} <= set(events[0].candidate_ids):
        problems.append(f"both entities stay visible on a mixed leaf: {events[0].candidate_ids}")
    # NEGATIVE CONTROL: the very same shape without the real value resolves.
    clean = _call(SMS, {"text": f"Клиент {FAKE_ONE}", "sign": "SMS Aero"},
                  {"text": "Клиент Иванова Елена", "sign": "SMS Aero"}, {}, "", 3)
    clean_events = _events_at(_one_event(case, _run_with(
        "m02-pin", (("p1", FAKE_ONE), ("p2", FAKE_PHONE_B)),
        (_mention("p1", 0, -1, FAKE_ONE), _mention("p2", -1, 1, FAKE_PHONE_B)), (clean,), (0,))), "text")
    if not clean_events or clean_events[0].status != "matched" or clean_events[0].item_id != "p1":
        problems.append(f"the control must still resolve to p1: "
                        f"{[(e.status, e.item_id) for e in clean_events]}")
    # THE REAL WHOLE WRITTEN IN THE CLEAR is still charged — a refused stem may
    # not become a refused whole.
    leak_case = _case("m02-leak", "single", (REAL_NAME,), (_one(),), ())
    leak_run = _run_with("m02-leak", (), (), (_roleless_call(3, "Иванова Елена", "Иванова Елена"),), (0,))
    leak = _events_at(_one_event(leak_case, leak_run), "contact.name_latin")[0]
    if leak.status != "unmasked_known" or leak.item_id != "p1":
        problems.append(f"a REAL whole written in the clear is still a leak: {leak.status}/{leak.item_id}")
    # CONSERVATIVE PRIORS, one leaf each.
    surname_leaf = _run_with("m02-role", (("p1", FAKE_ONE),), (_mention("p1", 0, -1, FAKE_ONE),),
                             (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    role = _events_at(_one_event(_case("m02-role", "single", (REAL_NAME,), (_one(),), ()),
                                 surname_leaf), "contact.last_name")[0]
    if role.status != "matched" or role.item_id != "p1":
        problems.append(f"the role-specific surname leaf still matches: {role.status}/{role.item_id}")
    whole = _one()
    part = replace(whole, id="p1-surname", value="Иванова", canonical="Иванова",
                   parts={"surname": "иванова"})
    projection = _case("m02-proj", "single", (REAL_NAME,), (whole, part), ())
    projection_run = _run_with("m02-proj", (("p1", FAKE_ONE), (part.id, "Пахомова")),
                               (_mention("p1", 0, -1, FAKE_ONE),
                                _mention(part.id, 0, -1, "Пахомова")),
                               (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (0,))
    event = _events_at(_one_event(projection, projection_run), "contact.last_name")[0]
    if event.status != "matched" or set(event.candidate_ids) != {"p1", part.id}:
        problems.append(f"whole plus declared part keep their projection: "
                        f"{event.status}/{event.candidate_ids}")
    return problems


# --- 16. M02-F1/F2: the role-less collision asks THIS call's evidence -------------------
#
# A's substitute SURNAME is B's REAL surname — the review's §4 fixture. The leaf
# is role-less (`contact.name_latin`), so the leak side has to decide whose the
# written word is by the evidence the agent HAD at the call. Two rules are
# pinned here and neither is borrowed from a reviewer's expression:
#
#   * the availability question is asked with the CURRENT call's turn and seq
#     (F1). A mention at message 0 and one at message 1 are both in the agent's
#     hands at a turn-3 call and must give the SAME verdict; message 4 is the
#     future and may not be borrowed.
#   * the fallback that credits a substitute whose word ALSO renders another
#     entity's real value is reachable (F2). Its guard used to be computed with
#     the item's own exemption and then read backwards, so the branch that names
#     the fake's owner could never run: a restored leaf read `unattributed` and
#     an unrestored one read `unmasked_known` on the collider.

def _collision_pair() -> tuple[PiiItem, PiiItem]:
    """A (fake «Пахомова Ольга») and B, a DIFFERENT real person whose real
    surname IS «Пахомова». B's substitute shares no word with A's."""
    a = _one()
    b = _item("pb", "NAME", "Пахомова Анна", "Пахомова Анна", "i2", _in_seed("s2", "name"))
    return a, b


def _collision_events(case_id: str, mention_msg: int | None, restored: str,
                      items: tuple[PiiItem, ...], subs: tuple[tuple[str, str], ...],
                      mentions: tuple[MentionRecord, ...]) -> tuple[ActualEvent, ...]:
    case = _case(case_id, "single", (REAL_NAME,), items, ())
    run = _run_with(case_id, subs, mentions, (_roleless_call(3, "Пахомова", restored),), (3,))
    return _events_at(_one_event(case, run), "contact.name_latin")


def test_roleless_collision_asks_this_calls_evidence() -> list[str]:
    """F1/F2: the same leaf at the same call, one message index apart, may not
    change who is charged.

    The call is at TURN 3, so A's fake at message 0 and at message 1 are both
    available. Restoring A correctly must name A and must not charge B with a
    leak (nor buy the leaf a pass); leaving A's fake standing must be `residual`
    on A. Both variants must be IDENTICAL across the two mentions.
    """
    a, b = _collision_pair()
    subs = (("p1", FAKE_ONE), ("pb", FAKE_TWO_DISTINCT))
    problems: list[str] = []
    verdicts: list[tuple[object, ...]] = []
    for msg in (0, 1):
        mentions = (_mention("p1", msg, -1, FAKE_ONE), _mention("pb", -1, 1, FAKE_TWO_DISTINCT))
        restored = _collision_events(f"m02-f1-{msg}", msg, "Иванова", (a, b), subs, mentions)
        if len(restored) != 1:
            problems.append(f"msg={msg}: expected one role-less event, got {len(restored)}")
            continue
        one = restored[0]
        if one.item_id != "p1":
            problems.append(f"msg={msg}: the fake's owner wrote this leaf, got "
                            f"{one.item_id!r} ({one.status})")
        if one.status not in ("matched", "value_wrong"):
            problems.append(f"msg={msg}: a restored A owes matched/value_wrong, "
                            f"got {one.status!r}")
        if one.residual:
            problems.append(f"msg={msg}: A's real value is not a surviving fake: {one.status!r}")
        kept = _collision_events(f"m02-f1-{msg}", msg, "Пахомова", (a, b), subs, mentions)
        if len(kept) != 1:
            problems.append(f"msg={msg}: expected one unrestored event, got {len(kept)}")
            continue
        stood = kept[0]
        if stood.item_id != "p1":
            problems.append(f"msg={msg}: a standing fake belongs to its owner, got "
                            f"{stood.item_id!r} ({stood.status})")
        if stood.status == "unmasked_known":
            problems.append(f"msg={msg}: a standing FAKE is not the collider's REAL value")
        if not stood.residual:
            problems.append(f"msg={msg}: the fake still standing must set residual, "
                            f"got {stood.status!r}")
        verdicts.append((one.item_id, one.status, one.residual,
                         stood.item_id, stood.status, stood.residual))
    if len(verdicts) == 2 and verdicts[0] != verdicts[1]:
        problems.append(f"msg=0 and msg=1 are both available at turn 3 and must agree: {verdicts}")
    return problems


def test_future_mention_is_not_borrowed_as_prior_evidence() -> list[str]:
    """A mention at message 4 is the future of a turn-3 call: it may not be
    borrowed as evidence, and a genuinely future fake may not choose the
    identity."""
    a, b = _collision_pair()
    subs = (("p1", FAKE_ONE), ("pb", FAKE_TWO_DISTINCT))
    problems: list[str] = []

    def verdict(msg: int | None) -> tuple[str, str, bool] | None:
        mentions = ((_mention("p1", msg, -1, FAKE_ONE),) if msg is not None else ()) + \
                   (_mention("pb", -1, 1, FAKE_TWO_DISTINCT),)
        events = _collision_events("m02-f1-future", msg, "Пахомова", (a, b), subs, mentions)
        return (events[0].item_id, events[0].status, events[0].residual) if len(events) == 1 else None

    future, never = verdict(4), verdict(None)
    if future != never:
        problems.append(f"a mention at message 4 must not be borrowed by a call at turn 3: "
                        f"{future} != {never}")
    if future is not None and future[0] == "p1":
        problems.append(f"the future fake must not choose the identity: {future}")
    return problems


def test_same_surname_and_old_new_versions_never_charge_the_collider() -> list[str]:
    """The collision pinned beside two people wearing one surname and a NEW
    version of A: the real collider is never the written side, and a pass may
    not hide a second entity. (The role-specific surname leaf, the two-people-
    one-surname ambiguity, the old/new value version and the ordinary short
    numbers keep their own pins in this same suite.)"""
    a, b = _collision_pair()
    newer = replace(a, id="p1-new", value="Иванова Анна", canonical="Иванова Анна",
                    parts={"surname": "Иванова", "given": "Анна"})
    subs = (("p1", FAKE_ONE), ("pb", FAKE_TWO_DISTINCT), ("p1-new", "Пахомова Вера"))
    mentions = (_mention("p1", 1, -1, FAKE_ONE),
                _mention("pb", -1, 1, FAKE_TWO_DISTINCT),
                _mention("p1-new", 1, -1, "Пахомова Вера"))
    events = _collision_events("m02-versions", 1, "Иванова", (a, b, newer), subs, mentions)
    if len(events) != 1:
        return [f"expected one role-less event, got {len(events)}"]
    one = events[0]
    problems: list[str] = []
    if one.item_id == "pb":
        problems.append("the real collider is never the written side")
    if one.status == "unmasked_known":
        problems.append(f"a collision of a fake with a real value is not a real-value leak: {one.status!r}")
    if one.item_id and one.item_id not in ("p1", "p1-new"):
        problems.append(f"only a fake's owner may be named here: {one.item_id!r}")
    if one.status == "matched" and set(one.candidate_ids) - {"p1", "p1-new"}:
        problems.append(f"a matched leaf may not hide another entity: {one.candidate_ids}")
    # THE ROLE BRANCH IS INDEPENDENT of the leak-side repair: the exact typed
    # part still names A (as `mixed`, because the collider's real surname is
    # also in the text) in BOTH mention variants.
    for msg in (0, 1):
        case = _case(f"m02-role-{msg}", "single", (REAL_NAME,), (a, b), ())
        run = _run_with(f"m02-role-{msg}", subs,
                        (_mention("p1", msg, -1, FAKE_ONE), _mention("pb", -1, 1, FAKE_TWO_DISTINCT)),
                        (_upsert_call(3, "contact.last_name", "Пахомова", "Иванова"),), (3,))
        role = _events_at(_one_event(case, run), "contact.last_name")[0]
        if role.item_id != "p1" or role.status not in ("mixed", "matched"):
            problems.append(f"msg={msg}: the role leaf keeps naming A: {role.status}/{role.item_id!r}")
    return problems


# --- 17. M02 v10: residual is a LEAF signal, never spent on an entity refusal ----------
#
# The second independent recheck (m02-leak-side-v9-recheck-20260928.md §3) rejected
# v9 because `residual` was computed inside `_restoration`, which runs only for a
# CHOSEN entity: when two same-identity records made `_one_entity` refuse, a standing
# fake was reclassified `ambiguous` with `residual=False` and the report read as a
# privacy improvement bought by an identity refusal. The counterexample is
# `tool_chain-009 repeat 0 call_seq 15 turn 2`: a byte-identical written/restored
# address whose established fake is i7's minted street substitute, while i8's
# whole-address substitute lights the SAME leaf through its generic settlement
# «Орёл» — `parts_of` folds the settlement into the street blob of an address it
# cannot type, so `i8` competed for a leaf that is unambiguously `i7`'s.
#
# v10 measures `residual` on the RESTORED text and the AVAILABLE substitute
# surfaces, BEFORE identity selection, and carries it through an unresolved status
# with `item_id=''`. A token the customer's own values carry in a GENERIC role (the
# settlement, the street type, the mail domain, the gender) is an ordinary token and
# cannot prove a MINTED part.

ADDRESS_TOOL = "address_suggest"
FAKE_STREET = "Пихтовая"                            # i7's changed street (real «лермонтова»)
FAKE_FULL_ADDRESS = "г Орёл, ул Ольховая, д 163"    # i8's whole address, generic «Орёл»
REAL_STREET = "лермонтова"
SHAPE_LEAF = "Орёл Пихтовая 168к54"                 # the raw tool_chain-009 seq-15 query


def _address_call(seq: int, written: str, restored: str) -> ObservedCall:
    """One role-less `address_suggest.query` leaf — the tool_chain-009 shape."""
    return _call(ADDRESS_TOOL, {"count": 10, "query": written},
                 {"count": 10, "query": restored}, {}, "", seq)


def _same_identity_addresses() -> tuple[PiiItem, PiiItem]:
    """i7 (whole record) and i8 (street-only projection) of ONE identity and ONE
    real street — the corpus's own pair, where `parts_of` folds i8's substitute
    settlement into its street blob."""
    whole = replace(_item("i7", "LOC", REAL_STREET, REAL_STREET, "a1", _in_seed("s2", "street")),
                    parts={"street": REAL_STREET, "street_type": "проезд",
                           "house": "120", "flat": "150", "city": "орёл"})
    part = replace(_item("i8", "LOC", REAL_STREET, REAL_STREET, "a1", _in_seed("s3", "street")),
                   parts={"street": REAL_STREET})
    return whole, part


def _shape_events(case_id: str, items: tuple[PiiItem, ...],
                  subs: tuple[tuple[str, str], ...], mentions: tuple[MentionRecord, ...],
                  written: str = SHAPE_LEAF, restored: str = SHAPE_LEAF,
                  turn: int = 2) -> tuple[ActualEvent, ...]:
    case = _case(case_id, "single", (REAL_NAME,), items, ())
    run = _run_with(case_id, subs, mentions, (_address_call(15, written, restored),), (turn,))
    return _events_at(_one_event(case, run), "query")


def test_standing_fake_is_residual_under_the_resolved_identity() -> list[str]:
    """The review's `tool_chain-009` shape: written == restored, i7's minted
    street still stands, and the leaf's residual flag survives whatever identity
    the branches pick. v11 read this leaf `ambiguous` with `item_id=''` because
    i8's whole-address substitute was CREDITED through the GENERIC settlement
    «Орёл»; v12 refuses that credit (a generic-role word the customer's own
    values carry proves no minted part), so the only remaining candidate is i7 —
    the entity whose minted STREET «Пихтовая» is in the leaf — and the row is a
    named `residual`. ATTRIBUTION MOVED TO THE EVIDENCED OWNER; THE PRIVACY
    READING DID NOT: the flag stays True and i8 is never charged."""
    whole, part = _same_identity_addresses()
    subs = (("i7", FAKE_STREET), ("i8", FAKE_FULL_ADDRESS))
    problems: list[str] = []
    events = _shape_events("m02-v10-shape", (whole, part), subs,
                           (_mention("i7", 0, -1, FAKE_STREET),
                            _mention("i8", 1, -1, FAKE_FULL_ADDRESS)))
    if len(events) != 1:
        return [f"expected one query event, got {[(e.status, e.item_id) for e in events]}"]
    one = events[0]
    if one.status != "residual":
        problems.append("i7's minted street substitute still stands: the critical-defect "
                        f"status is `residual`, got {one.status!r}")
    if not one.residual:
        problems.append("i7's minted street substitute still stands: residual must be True")
    if one.item_id != "i7":
        problems.append(f"the leaf's only identifying needle is i7's «{FAKE_STREET}»: {one.item_id!r}")
    if set(one.candidate_ids) != {"i7"}:
        problems.append(f"a generic settlement gives i8 no candidacy: {one.candidate_ids}")
    if not one.attributed:
        problems.append("the evidenced owner is named")
    # msg 0 and msg 1 are both available at a turn-2 call: the verdict may not move.
    second = _shape_events("m02-v10-shape-2", (whole, part), subs,
                           (_mention("i7", 1, -1, FAKE_STREET),
                            _mention("i8", 0, -1, FAKE_FULL_ADDRESS)))
    if len(second) != 1 or (second[0].status, second[0].item_id, second[0].residual) != \
            (one.status, one.item_id, one.residual):
        problems.append("an available mention one message earlier must not move the verdict")
    return problems


def test_generic_city_alone_is_not_a_minted_part() -> list[str]:
    """The negative control for the same shape: the leaf carries the generic
    settlement «Орёл» — matched by i8's whole-address substitute — and NOTHING of
    i7's minted street. «Орёл» is a word the customer's own values carry in a
    generic role, so it is an ordinary token and cannot prove a minted part: the
    leaf is NOT residual, and it stays a visible value/form verdict instead of a
    fabricated critical defect. (v9 read this leaf `residual` through i8's
    narrowed exemption, which is the `i8`-vs-`i7` refusal the review names.)"""
    whole, part = _same_identity_addresses()
    events = _shape_events("m02-v10-generic", (whole, part),
                           (("i7", FAKE_STREET), ("i8", FAKE_FULL_ADDRESS)),
                           (_mention("i7", 0, -1, FAKE_STREET),
                            _mention("i8", 1, -1, FAKE_FULL_ADDRESS)),
                           written="Орёл 168к54", restored="Орёл 168к54")
    if len(events) != 1:
        return [f"expected one query event, got {[(e.status, e.item_id) for e in events]}"]
    one = events[0]
    problems: list[str] = []
    if one.residual:
        problems.append("a generic settlement shared with the customer's own values is "
                        "not a minted part")
    if one.status == "residual":
        problems.append("the generic-city reading may not print the critical-defect status")
    return problems


def test_future_mention_is_not_borrowed_for_residual() -> list[str]:
    """A fake disclosed at message 4 is the future of a turn-2 call. The leaf-level
    residual signal uses AVAILABLE surfaces only: it may not be borrowed, and the
    future fake may not choose the identity."""
    whole, part = _same_identity_addresses()
    problems: list[str] = []
    future = _shape_events("m02-v10-future", (whole, part),
                           (("i7", FAKE_STREET), ("i8", FAKE_FULL_ADDRESS)),
                           (_mention("i7", 4, -1, FAKE_STREET),
                            _mention("i8", 1, -1, FAKE_FULL_ADDRESS)))
    if len(future) != 1:
        return [f"expected one query event, got {[(e.status, e.item_id) for e in future]}"]
    if future[0].item_id == "i7":
        problems.append("a fake disclosed after the call may not choose the identity")
    if future[0].residual:
        problems.append("no AVAILABLE minted surface proves a standing fake here")
    return problems


# --- 18. M02 v11: the ROLE branch's exemption is TYPED and PER-ITEM --------------------
#
# The third independent recheck (m02-orthogonal-residual-recheck-20260928.md §4)
# rejected v10 on 140 of its 205 `residual`-status rows: `_substitute_stands`
# returns at the ROLE branch before either exemption set is read, so a
# `contact.address.city` / `to_location.city` / `address.locality` leaf whose
# substitute part IS the customer's own city was charged `residual` although
# `restored == expected`. The engine PRESERVES the settlement in an address
# substitute, so the role test fired on the customer's own word.
#
# v11 repairs ONLY the residual reader. For a GENERIC role it declines a role
# part PROVEN to be this item's own real part (unchanged); otherwise it keeps the
# role reading exactly as v9 pinned it. A surname role is not generic and is
# untouched (F2), and a role part that DIFFERS from the customer's own is a
# minted part and still stands.

def _city_role_item(item_id: str = "i10") -> PiiItem:
    """The frozen chain-003 shape: a whole address whose substitute PRESERVES the
    settlement, so the city part of the substitute equals the customer's own."""
    return replace(_item(item_id, "LOC", "кинешма подлесная 15", "кинешма подлесная 15", "a1",
                         _in_seed("s2", "address")),
                   parts={"city": "кинешма", "street": "подлесная", "house": "15", "flat": "5"})


def _city_call(seq: int, city: str) -> ObservedCall:
    """One `crm_upsert_contact` call carrying the city ROLE leaf alone."""
    return _call(UPSERT, {"contact": {"address": {"city": city}}},
                 {"contact": {"address": {"city": city}}}, {}, "", seq)


def _city_event(case_id: str, substitute: str, leaf: str) -> ActualEvent | None:
    item = _city_role_item()
    case = _case(case_id, "single", (REAL_NAME,), (item,), ())
    run = _run_with(case_id, (("i10", substitute),), (_mention("i10", 0, -1, substitute),),
                    (_city_call(3, leaf),), (2,))
    events = _events_at(_one_event(case, run), "contact.address.city")
    return events[0] if len(events) == 1 else None


def test_unchanged_city_role_is_not_residual() -> list[str]:
    """The review's counterexample, as a role leaf: the substitute's city part IS
    the customer's own city, the tool received exactly what it asked for, and the
    leaf may not print the critical-defect status."""
    one = _city_event("m02-v11-city", "Кинешма, улица Грушевая 20, кв. 104", "Кинешма")
    if one is None:
        return ["expected one contact.address.city event"]
    problems: list[str] = []
    if one.residual:
        problems.append("the substitute's city part IS the customer's own unchanged city: "
                        "an ordinary word, not a minted part")
    if one.status == "residual":
        problems.append("the unchanged city may not print the critical-defect status")
    if one.item_id != "i10":
        problems.append(f"the unchanged city leaf still belongs to i10: {one.item_id!r}")
    if not one.value_ok:
        problems.append("restored == expected, so the value came back: value_ok must be True")
    if one.expected != "кинешма":
        problems.append(f"the leaf asked for the customer's own city: {one.expected!r}")
    return problems


def test_unchanged_street_type_role_is_not_residual() -> list[str]:
    """The generic role with no registry leaf of its own: asked directly of the
    residual READER. The substitute's street_type part equals the customer's own,
    so it proves no minted part — while a street_type the customer's own value
    does not carry is still a minted part and still stands."""
    spec = FieldSpec(path="address.street_type", kind="identity", pii_type="LOC",
                     role="street_type")
    item = replace(_item("s1", "LOC", "проезд", "проезд", "a1", _in_seed("s2", "street")),
                   parts={"street_type": "проезд"})
    case = _case("m02-v11-stype", "single", (REAL_NAME,), (item,), ())
    run = _run_with("m02-v11-stype", (("s1", "проезд"),),
                    (_mention("s1", 0, -1, "проезд"),), (), ())
    own = own_stems_of(case, item)
    problems: list[str] = []
    if _minted_substitute_stands(item, spec, ("проезд",), "проезд", own, case, run, 0, 0):
        problems.append("the substitute's street_type part IS the customer's own unchanged "
                        "generic: it cannot prove a minted part")
    if not _minted_substitute_stands(item, spec, ("шоссе",), "шоссе", own, case, run, 0, 0):
        problems.append("a street_type the customer's own value does not carry still stands")
    return problems


def test_a_minted_role_part_still_stands() -> list[str]:
    """CAN-FAIL for the city exemption: a settlement that DIFFERS from the
    customer's own is a minted part and the leaf stays `residual`."""
    one = _city_event("m02-v11-minted", "Рязань, улица Грушевая 20, кв. 104", "Рязань")
    if one is None:
        return ["expected one contact.address.city event"]
    problems: list[str] = []
    if not one.residual:
        problems.append("a minted settlement still standing must stay residual")
    if one.status != "residual":
        problems.append(f"a standing minted settlement is the critical-defect status: {one.status!r}")
    return problems


def test_colliding_surname_role_keeps_the_standing_fake() -> list[str]:
    """F2, role-typed: the exemption is GENERIC and PER-ITEM, so a surname leaf is
    untouched. A's fake «Пахомова» still stands for A even though it is B's REAL
    surname, and it is never read as B's standing fake."""
    a, b = _collision_pair()
    spec = FieldSpec(path="contact.last_name", kind="identity", pii_type="NAME", role="surname")
    case = _case("m02-v11-f2", "single", (REAL_NAME,), (a, b), ())
    run = _run_with("m02-v11-f2", (("p1", FAKE_ONE), ("pb", FAKE_TWO_DISTINCT)), (), (), ())
    problems: list[str] = []
    if not _minted_substitute_stands(a, spec, (FAKE_ONE,), "Пахомова",
                                     own_stems_of(case, a), case, run, 3, 3):
        problems.append("a surname role is not generic: A's standing fake must survive")
    if _minted_substitute_stands(b, spec, (FAKE_TWO_DISTINCT,), "Пахомова",
                                 own_stems_of(case, b), case, run, 3, 3):
        problems.append("B's real surname is not B's standing fake")
    return problems


def test_tool_chain_009_hidden_residual_survives_the_city_exemption() -> list[str]:
    """The ONE case that carries both shapes: the role-less `query` leaf whose
    minted street stands (the hidden residuals v8->v9 lost) keeps `residual=True`
    and names i7 — the entity whose minted STREET is in the leaf, once i8's
    generic-city credit is refused — while the city ROLE leaf beside it (the
    customer's own unchanged settlement) is cleared. The exemption is a proof
    about ONE item's role part, never a case-wide suppression."""
    whole, part = _same_identity_addresses()
    substitutes = (("i7", "Орёл, улица Пихтовая, д 120"), ("i8", FAKE_FULL_ADDRESS))
    case = _case("m02-v11-shape", "single", (REAL_NAME,), (whole, part), ())
    run = _run_with("m02-v11-shape", substitutes,
                    (_mention("i7", 0, -1, "Орёл, улица Пихтовая, д 120"),
                     _mention("i8", 1, -1, FAKE_FULL_ADDRESS)),
                    (_address_call(15, SHAPE_LEAF, SHAPE_LEAF), _city_call(16, "Орёл")), (2, 2))
    observation = _one_event(case, run)
    queries = _events_at(observation, "query")
    problems: list[str] = []
    if len(queries) != 1:
        return [f"expected one query event, got {[(e.status, e.item_id) for e in queries]}"]
    if not queries[0].residual:
        problems.append("i7's minted street still stands: residual must be True")
    if queries[0].item_id != "i7":
        problems.append("with i8's generic-city credit refused, the minted street names i7: "
                        f"item_id={queries[0].item_id!r}")
    cities = _events_at(observation, "contact.address.city")
    if len(cities) != 1:
        return problems + [f"expected one city event, got {[(e.status, e.item_id) for e in cities]}"]
    if cities[0].residual:
        problems.append("the unchanged generic city beside it is the customer's own word")
    if cities[0].item_id != "i7":
        problems.append(f"the city leaf is still i7's: {cities[0].item_id!r}")
    return problems


# --- 19. M02 v12: a GENERIC-role word chooses no identity, and the residual flag is a
# leaf property even after the identity RESOLVES -----------------------------------------
#
# The read-only E2E on the saved 450 kept ONE generic-city identity credit:
# `tool_chain-036 repeat 0 call_seq 4 path 'query'`, written == restored ==
# «Челябинск 19 километров», whose only matching needle was the settlement
# «Челябинск» that `parts_of` folds out of i8's whole-address substitute
# «г Челябинск, ул Пихтовая, д 83». The customer's OWN values carry that city as a
# generic part, so the word proves no minted part and may not choose i8: the
# identity reader had read the case-wide cancellation as «another entity's real
# value explains it». The gate is the one the residual reader already used (one
# mechanism, two readers). Resolving identity where v11 refused then exposed the
# other half: `_restoration` asked the leak question only of the winner, so a
# second item's standing fake could disappear (tool_chain-008 seq 7,
# tool_chain-030 seq 6, tool_chain-034 seq 10, long_order-018/023/045/048).

def _generic_city_case(case_id: str, fake_address: str, leaf: str,
                       restored: str = "") -> ActualEvent | None:
    """The `tool_chain-036` shape: a whole LOC whose OWN parts declare the
    settlement, and a street-only projection whose substitute is a whole address
    (so `parts_of` folds the settlement into its street blob). `restored` is the
    tool's answer; empty means the leaf came back as written."""
    whole = replace(_item("i7", "LOC", "смольный", "смольный", "a1", _in_seed("s2", "street")),
                    parts={"street": "смольный", "street_type": "бульвар", "house": "37б",
                           "flat": "187", "city": "челябинск"})
    part = replace(_item("i8", "LOC", "смольный", "смольный", "a1", _in_seed("s3", "street")),
                   parts={"street": "смольный"})
    case = _case(case_id, "single", (REAL_NAME,), (whole, part), ())
    run = _run_with(case_id, (("i7", "Берёзовая"), ("i8", fake_address)),
                    (_mention("i7", 0, -1, "Берёзовая"),
                     _mention("i8", 1, -1, fake_address)),
                    (_address_call(4, leaf, restored or leaf),), (2,))
    events = _events_at(_one_event(case, run), "query")
    return events[0] if len(events) == 1 else None


def test_generic_city_role_does_not_choose_an_identity() -> list[str]:
    """`tool_chain-036 c4`: the leaf carries ONLY the customer's own settlement.
    Before v12 the identity reader credited i8 and printed `value_wrong`; a
    generic-role word the customer's own values carry proves no minted part, so
    the leaf is `unattributed` — visible and unresolved, with i8 never charged."""
    one = _generic_city_case("m02-v12-city", "г Челябинск, ул Пихтовая, д 83",
                             "Челябинск 19 километров")
    if one is None:
        return ["expected one query event"]
    problems: list[str] = []
    if one.item_id or one.attributed:
        problems.append(f"a generic settlement chooses no entity: {one.item_id!r}/{one.attributed}")
    if one.status != "unattributed":
        problems.append(f"an unresolved leaf stays visible as `unattributed`: {one.status!r}")
    if one.residual:
        problems.append("no minted fake stands in the leaf")
    return problems


def test_generic_settlement_beside_another_standing_fake() -> list[str]:
    """THE REAL CORPUS SHAPE OF THE SAME REFUSAL (`tool_chain-005 c12`,
    `tool_chain-010 c11`, `tool_chain-018 c12`, `tool_chain-032 c13/c14`): the
    agent wrote only the customer's own settlement beside a street that is
    NOBODY's substitute, and the tool answered with ANOTHER item's standing fake.
    The written side is `unattributed` — the generic word chooses nobody, and i8
    is never charged — while the leak flag stays ORTHOGONAL and TRUE: i7's minted
    «Берёзовая» really does stand in the restored text, so no value credit may be
    bought with the identity refusal. PARITY CONTROL: the same written leaf with
    no standing fake in the answer keeps `residual=False` and no value pass
    (`test_generic_city_role_does_not_choose_an_identity`)."""
    one = _generic_city_case("m02-v12-corpus", "г Челябинск, ул Пихтовая, д 83",
                             "Челябинск Барбарисовая 13",
                             restored="Челябинск Берёзовая 37б")
    if one is None:
        return ["expected one query event"]
    problems: list[str] = []
    if one.item_id or one.attributed:
        problems.append(f"a generic settlement chooses no entity here either: "
                        f"{one.item_id!r}/{one.attributed}")
    if one.status != "unattributed":
        problems.append(f"the written side stays visible as `unattributed`: {one.status!r}")
    if not one.residual:
        problems.append("i7's minted street still stands in the restored text: residual must be True")
    if one.value_ok:
        problems.append("an unresolved identity earns no value credit")
    return problems


def test_minted_part_still_chooses_its_owner() -> list[str]:
    """CAN-FAIL doors for the generic gate, same shape: the leaf carrying the
    MINTED street of i8's whole-address substitute still credits i8, and so does
    a settlement the customer's own values do NOT carry (a minted part)."""
    problems: list[str] = []
    street = _generic_city_case("m02-v12-street", "г Челябинск, ул Пихтовая, д 83",
                                "Пихтовая 19 километров")
    if street is None or street.item_id != "i8" or not street.attributed:
        problems.append("the minted street still credits i8: "
                        f"{None if street is None else (street.status, street.item_id)}")
    minted = _generic_city_case("m02-v12-minted", "г Рязань, ул Пихтовая, д 83",
                                "Рязань 19 километров")
    if minted is None or minted.item_id != "i8" or not minted.attributed:
        problems.append("a settlement the customer's own values do not carry is a minted "
                        "part and still credits i8: "
                        f"{None if minted is None else (minted.status, minted.item_id)}")
    return problems


def test_leaf_residual_survives_a_resolved_identity() -> list[str]:
    """v12's leaf-orthogonal residual, the mirror of v10's refusal rule. The
    chosen entity is restored correctly, so the identity RESOLVES — but another
    item's minted street is still standing in the same restored text. Asking the
    leak question only of the winner printed `matched` and hid a real standing
    fake; the leaf-level reader keeps `residual`. NEGATIVE CONTROL: the same leaf
    with no standing fake in the restored text is `matched` with `residual=False`."""
    a = _one()
    b = _item("pb", "LOC", "лермонтова", "лермонтова", "i2", _in_seed("s2", "street"))
    case = _case("m02-v12-ortho", "single", (REAL_NAME,), (a, b), ())
    standing = _run_with(
        "m02-v12-ortho", (("p1", FAKE_ONE), ("pb", "Пихтовая")),
        (_mention("p1", 0, -1, FAKE_ONE), _mention("pb", 0, -1, "Пихтовая")),
        (_call(SMS, {"text": "Клиент Пахомова, адрес уточняется"},
               {"text": "Клиент Иванова Елена, адрес: Пихтовая"}, {}, "", 3),), (0,))
    events = _events_at(_one_event(case, standing), "text")
    problems: list[str] = []
    if len(events) != 1:
        return [f"expected one leaf, got {[(e.status, e.item_id) for e in events]}"]
    if events[0].item_id != "p1":
        problems.append(f"pb's fake is not in the written leaf: {events[0].item_id!r}")
    if not events[0].residual or events[0].status != "residual":
        problems.append("pb's minted street still stands in the restored text: "
                        f"residual={events[0].residual} status={events[0].status!r}")
    clean = _run_with(
        "m02-v12-ortho", (("p1", FAKE_ONE), ("pb", "Пихтовая")),
        (_mention("p1", 0, -1, FAKE_ONE), _mention("pb", 0, -1, "Пихтовая")),
        (_call(SMS, {"text": "Клиент Пахомова, адрес уточняется"},
               {"text": "Клиент Иванова Елена"}, {}, "", 3),), (0,))
    clean_events = _events_at(_one_event(case, clean), "text")
    if len(clean_events) != 1 or clean_events[0].status != "matched" or clean_events[0].residual:
        problems.append("with no standing fake the leaf is `matched` and not residual: "
                        f"{[(e.status, e.residual) for e in clean_events]}")
    return problems


# --- 20. M02 v13: the value column is independent of the tool's notation ----------------
#
# v12 refused the generic-settlement identity credit, so leaves v11 could not
# resolve now name their ONE evidenced owner — and 11 of those resolutions were
# printed `value_wrong` although the tool received the real street: the `query`
# leaf returns the settlement and the street JOINED («Красноярск Энгельса»), and
# the pre-existing LOC predicate compared that blob with the one-street
# canonical. The repair is a SECOND, NARROWER reading — `leaf_value_ok` first,
# then every role it compares (street/house/flat) asked of the produced tokens —
# never a weaker rule. These checks pin the repaired shape AND the four ways it
# must still fail.

def _notation_case(case_id: str, restored: str, house: str = "37") -> ActualEvent | None:
    """The `tool_chain-002 seq 7` shape: i7's fake street «Берёзовая» was written
    and the real «Энгельса» came back JOINED to the settlement «Красноярск». A
    declared `house` is a role the leaf must also render; with `house=""` the
    target is the street alone (`tool_chain-002`'s own part declaration)."""
    value = f"энгельса {house}".strip()
    parts = {"street": "энгельса", "street_type": "улица", "flat": "187",
             "city": "красноярск"}
    if house:
        parts["house"] = house
    whole = replace(_item("i7", "LOC", value, value, "a1", _in_seed("s2", "street")),
                    parts=parts)
    case = _case(case_id, "single", (REAL_NAME,), (whole,), ())
    run = _run_with(case_id, (("i7", "Берёзовая"),),
                    (_mention("i7", 0, -1, "Берёзовая"),),
                    (_address_call(7, "Красноярск Берёзовая", restored),), (2,))
    events = _events_at(_one_event(case, run), "query")
    return events[0] if len(events) == 1 else None


def _repeated_word_case(case_id: str, restored: str) -> ActualEvent | None:
    """`tool_chain-034 seq 5`: the settlement and the street are the SAME word,
    so the produced blob «Чернь Чернь, Ленина» has to answer the street alone."""
    whole = replace(_item("i7", "LOC", "ленина", "ленина", "a1", _in_seed("s2", "street")),
                    parts={"street": "ленина", "street_type": "улица",
                           "house": "4", "flat": "58", "city": "чернь"})
    case = _case(case_id, "single", (REAL_NAME,), (whole,), ())
    run = _run_with(case_id, (("i7", "Полевая"),),
                    (_mention("i7", 0, -1, "Полевая"),),
                    (_address_call(5, "Чернь Полевая", restored),), (2,))
    events = _events_at(_one_event(case, run), "query")
    return events[0] if len(events) == 1 else None


def test_joined_address_notation_is_not_a_wrong_value() -> list[str]:
    """The delivered real address in a separator-free composite is a `matched`
    leaf, with or without the house the item declares, and with the settlement
    carrying the STREET word too (`tool_chain-034 seq 5`, «Чернь Чернь, Ленина»).
    NEGATIVE CONTROLS: the tool returned the OTHER real street of the same
    customer (`value_wrong`), and another entity's address — which is a
    standing fake of that entity, so it is `residual` with no value credit."""
    problems: list[str] = []
    for case_id, restored, house in (("m02-v13-joined-house", "Красноярск Энгельса 37", "37"),
                                     ("m02-v13-joined-street", "Красноярск Энгельса", "")):
        one = _notation_case(case_id, restored, house)
        if one is None or one.status != "matched" or not one.value_ok:
            problems.append(f"the restored real address must be a MATCH: {restored!r} -> "
                            f"{None if one is None else (one.status, one.value_ok)}")
    repeated = _repeated_word_case("m02-v13-repeated", "Чернь Чернь, Ленина")
    if repeated is None or repeated.status != "matched" or not repeated.value_ok:
        problems.append("a settlement that repeats the street word is still the joined shape: "
                        f"{None if repeated is None else (repeated.status, repeated.value_ok)}")
    wrong = _notation_case("m02-v13-wrong-street", "Красноярск Барбарисовая")
    if wrong is None or wrong.value_ok or wrong.status not in ("value_wrong", "residual"):
        problems.append("another real street is NOT the expected value: "
                        f"{None if wrong is None else (wrong.status, wrong.value_ok)}")
    other = _repeated_word_case("m02-v13-other", "Чернь Чернь, Полевая")
    if other is None or not other.residual or other.value_ok:
        problems.append("another entity's standing fake is residual and earns no value pass: "
                        f"{None if other is None else (other.status, other.value_ok, other.residual)}")
    return problems


def test_notation_rescue_asks_every_declared_role() -> list[str]:
    """The second reading asks every role `value_matches` compares, so a WRONG
    house is not bought by the right street. The item declares `house=37`; the
    same leaf with 37 is `matched` — the parity check that keeps the control
    honest — while 99 and a missing house stay `value_wrong`."""
    problems: list[str] = []
    for case_id, restored, want in (("m02-v13-house-ok", "Красноярск Энгельса 37", True),
                                    ("m02-v13-house-bad", "Красноярск Энгельса 99", False),
                                    ("m02-v13-house-missing", "Красноярск Энгельса", False)):
        one = _notation_case(case_id, restored)
        if one is None:
            problems.append(f"expected one query leaf for {case_id}")
            continue
        if (one.status == "matched") != want:
            problems.append(f"{case_id}: expected matched={want}, got "
                            f"{one.status!r}/{one.value_ok}")
    return problems


def test_joined_address_refuses_competing_values() -> list[str]:
    """A mentioned correct address cannot excuse another value in the same leaf."""
    problems: list[str] = []
    for case_id, restored in (
        ("m02-v13-extra-street", "Красноярск Барбарисовая Энгельса 37"),
        ("m02-v13-two-addresses", "Красноярск Барбарисовая 99; Красноярск Энгельса 37"),
        ("m02-v13-old-address", "Красноярск Барбарисовая 99, прежняя улица Энгельса дом 37"),
        ("m02-v13-two-houses", "Красноярск Энгельса 99; дом 37"),
        ("m02-v14-wrong-type", "Красноярск бульвар Энгельса 37"),
    ):
        one = _notation_case(case_id, restored)
        if one is None or one.value_ok or one.status == "matched":
            problems.append(f"competing value must not match: {restored!r} -> "
                            f"{None if one is None else (one.status, one.value_ok)}")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("whole_and_declared_part_share_one_projection", test_whole_and_declared_part_share_one_projection),
        ("conflicting_full_versions_do_not_collapse_on_shared_part",
         test_conflicting_full_versions_do_not_collapse_on_shared_part),
        ("role_does_not_reinterpret_another_type", test_role_does_not_reinterpret_another_type),
        ("phone_value_is_independent_of_notation", test_phone_value_is_independent_of_notation),
        ("short_numbers_do_not_attribute_without_a_role",
         test_short_numbers_do_not_attribute_without_a_role),
        ("actual_crossing_is_not_absent_at_another_turn",
         test_actual_crossing_is_not_absent_at_another_turn),
        ("harmless_clarification_is_invariant", test_harmless_clarification_is_invariant),
        ("reordered_independent_actions_are_invariant",
         test_reordered_independent_actions_are_invariant),
        ("repeated_call_is_not_merged", test_repeated_call_is_not_merged),
        ("two_people_are_ambiguous", test_two_people_are_ambiguous),
        ("two_people_sharing_a_part_are_ambiguous", test_two_people_sharing_a_part_are_ambiguous),
        ("a_later_tool_result_is_not_usable_yet", test_a_later_tool_result_is_not_usable_yet),
        ("same_turn_result_is_not_proven_available", test_same_turn_result_is_not_proven_available),
        ("response_trace_proves_only_prior_response_results", test_response_trace_proves_only_prior_response_results),
        ("future_minted_parts_are_not_evidence", test_future_minted_parts_are_not_evidence),
        ("semantic_duplicate_items_are_one_entity",
         test_semantic_duplicate_items_are_one_entity),
        ("same_identity_different_value_is_ambiguous",
         test_same_identity_different_value_is_ambiguous),
        ("a_four_letter_prefix_is_not_identity", test_a_four_letter_prefix_is_not_identity),
        ("partial_role_needs_the_exact_part", test_partial_role_needs_the_exact_part),
        ("an_unattributed_crossing_stays_visible", test_an_unattributed_crossing_stays_visible),
        ("unchanged_identity_leaf_without_evidence_is_unattributed",
         test_unchanged_identity_leaf_without_evidence_is_unattributed),
        ("restored_value_does_not_choose_identity",
         test_restored_value_does_not_choose_identity),
        ("ordinary_leaf_is_not_a_defect", test_ordinary_leaf_is_not_a_defect),
        ("no_mask_gateway_is_not_perfect", test_no_mask_gateway_is_not_perfect),
        ("form_pass_does_not_imply_identity_pass", test_form_pass_does_not_imply_identity_pass),
        ("a_wrong_value_and_a_wrong_case_stay_separate",
         test_a_wrong_value_and_a_wrong_case_stay_separate),
        ("mixed_real_value_beside_a_fake_is_not_a_pass",
         test_mixed_real_value_beside_a_fake_is_not_a_pass),
        ("residual_is_in_the_joint_denominator", test_residual_is_in_the_joint_denominator),
        ("per_type_aggregate_splits_by_type", test_per_type_aggregate_splits_by_type),
        ("event_id_carries_no_turn", test_event_id_carries_no_turn),
        ("a_generic_part_is_not_an_unmasked_defect",
         test_a_generic_part_is_not_an_unmasked_defect),
        ("version_is_declared_and_scope_is_out_calls",
         test_version_is_declared_and_scope_is_out_calls),
        ("leak_side_separates_a_part_from_a_whole",
         test_leak_side_separates_a_part_from_a_whole),
        ("real_archive_whole_part_collisions_do_not_charge_the_wrong_entity",
         test_real_archive_whole_part_collisions_do_not_charge_the_wrong_entity),
        ("true_mixed_case_stays_caught_and_prior_verdicts_hold",
         test_true_mixed_case_stays_caught_and_prior_verdicts_hold),
        ("roleless_collision_asks_this_calls_evidence",
         test_roleless_collision_asks_this_calls_evidence),
        ("future_mention_is_not_borrowed_as_prior_evidence",
         test_future_mention_is_not_borrowed_as_prior_evidence),
        ("same_surname_and_old_new_versions_never_charge_the_collider",
         test_same_surname_and_old_new_versions_never_charge_the_collider),
        ("standing_fake_is_residual_under_the_resolved_identity",
         test_standing_fake_is_residual_under_the_resolved_identity),
        ("generic_city_alone_is_not_a_minted_part",
         test_generic_city_alone_is_not_a_minted_part),
        ("future_mention_is_not_borrowed_for_residual",
         test_future_mention_is_not_borrowed_for_residual),
        ("unchanged_city_role_is_not_residual",
         test_unchanged_city_role_is_not_residual),
        ("unchanged_street_type_role_is_not_residual",
         test_unchanged_street_type_role_is_not_residual),
        ("a_minted_role_part_still_stands",
         test_a_minted_role_part_still_stands),
        ("colliding_surname_role_keeps_the_standing_fake",
         test_colliding_surname_role_keeps_the_standing_fake),
        ("tool_chain_009_hidden_residual_survives_the_city_exemption",
         test_tool_chain_009_hidden_residual_survives_the_city_exemption),
        ("generic_city_role_does_not_choose_an_identity",
         test_generic_city_role_does_not_choose_an_identity),
        ("generic_settlement_beside_another_standing_fake",
         test_generic_settlement_beside_another_standing_fake),
        ("minted_part_still_chooses_its_owner",
         test_minted_part_still_chooses_its_owner),
        ("leaf_residual_survives_a_resolved_identity",
         test_leaf_residual_survives_a_resolved_identity),
        ("joined_address_notation_is_not_a_wrong_value",
         test_joined_address_notation_is_not_a_wrong_value),
        ("notation_rescue_asks_every_declared_role",
         test_notation_rescue_asks_every_declared_role),
        ("joined_address_refuses_competing_values",
         test_joined_address_refuses_competing_values),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("actual_hops: PASS" if not failures else "actual_hops: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
