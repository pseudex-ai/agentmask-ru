"""`observe.py` pinned: orientation, ownership, alignment, and the five statuses.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_observe

EVERY CHECK HERE IS SHOWN TO FAIL AS WELL AS TO PASS. A test that only asserts
the happy path pins nothing: the orientation check compares `produced` against
the substitute AND asserts it is NOT the source value, the partial-cover check
builds a piece that covers most of the span and demands `leaked`, and the owner
check builds a case that lies about its own hop and demands a raise.

The builders come from `fixtures.py` — the same hand-built records the gate
runs on, so a change that breaks one breaks both and neither can drift into
agreeing with the other by accident.
"""
import sys
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii4.schema import Locus
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import ArmRunV5, CaseV5, Hop
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    OTHER_NAME,
    REAL_NAME,
    REAL_PHONE,
    _call,
    _case,
    _hop,
    _in_message,
    _item,
    _result,
    _run,
    _with_calls,
    _with_masked,
    _with_mentions,
    _with_replies,
    _with_results,
    _with_subs,
)
from bench.agentpii5.observe import (
    ObserveError,
    Needle,
    _needle_spans,
    answer_spans,
    carried_substitute,
    carries_any,
    item_needles,
    item_survives_in,
    leaf_holds,
    merged_opcodes,
    observe,
    own_pair,
    own_stems,
    own_stretch,
    stem_of,
    survives_in,
    turn_request,
    value_needles,
)

NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
PHONE = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 20, 32))


def _one(case, run):  # noqa: ANN001, ANN202 - a two-line reader, typed by its callers
    return observe(case, run, None, None)


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_in_orientation() -> list[str]:
    """C-010. IN: produced = the substitute the model read, reference = the
    source. The reverse orientation would make every `form_hIN` verdict a
    statement about the source's form instead of the substitute's."""
    hop = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    case = _case("obs-in", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_subs(_run("obs-in"), {"p1": FAKE_NAME})
    got = _one(case, run).hops[0]
    problems: list[str] = []
    if got.produced != FAKE_NAME:
        problems.append(f"IN produced is {got.produced!r}, must be the substitute {FAKE_NAME!r}")
    if got.reference != REAL_NAME:
        problems.append(f"IN reference is {got.reference!r}, must be the source {REAL_NAME!r}")
    if got.produced == got.reference:
        problems.append("the fixture cannot tell the two orientations apart")
    leaked = _one(case, _run("obs-in")).hops[0]
    if leaked.status != "leaked" or leaked.verdict is not None:
        problems.append(f"no substitute must be `leaked` with no verdict, got {leaked.status}")
    return problems


def test_out_orientation() -> list[str]:
    """C-011. OUT: produced = what the consumer received, reference = the
    substitute AS THE AGENT WROTE IT — never canonicalised first."""
    hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("obs-out", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_subs(_with_calls(_run("obs-out"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": "Пахомовой"}},
        {"contact": {"last_name": "Ивановой"}}, {}, "", 0),), (0,)), {"p1": FAKE_NAME})
    got = _one(case, run).hops[0]
    problems: list[str] = []
    if got.produced != "Ивановой":
        problems.append(f"OUT produced is {got.produced!r}, must be the restored leaf")
    if got.reference != "Пахомовой":
        problems.append(f"OUT reference is {got.reference!r}, must be the written substitute")
    if got.status != "observed" or got.verdict is None:
        problems.append("an accepted OUT leaf must be observed and carry a verdict")
    return problems


def test_template_owner() -> list[str]:
    """C-033. A `send_template.variables.*` leaf is a TEMPLATE hop, and a case
    that declares it as a plain argument is refused — the owner decides which
    `form_hOUT` line the hop counts in, and a case must not choose its own."""
    good = _hop("OUT", "template", "p1", 0, 0, "send_template", 0, -1, "variables.name")
    case = _case("obs-tpl", "single", (REAL_NAME,), (NAME,), (good,))
    run = _with_calls(_run("obs-tpl"), (_call(
        "send_template", {"variables": {"name": FAKE_NAME}}, {"variables": {"name": REAL_NAME}},
        {}, "", 0),), (0,))
    problems: list[str] = []
    if contracts.hop_owner_of_leaf("send_template", "variables.name") != "template":
        problems.append("contracts no longer files variables.* under `template`")
    if _one(case, run).hops[0].hop.owner != "template":
        problems.append("the template leaf did not survive as a template hop")
    liar = _case("obs-tpl-2", "single", (REAL_NAME,), (NAME,),
                 (_hop("OUT", "tool_arg", "p1", 0, 0, "send_template", 0, -1, "variables.name"),))
    try:
        _one(liar, run)
        problems.append("a hop that mis-declares its owner was accepted")
    except ObserveError as error:
        if "variables.name" not in str(error):
            problems.append(f"the refusal does not name the leaf: {error}")
    return problems


def test_answer_alignment() -> list[str]:
    """The answer leg has no engine-recorded spans; `difflib` supplies them.
    «позвоню Кудрявцевой Диане» → «позвоню Кузнецовой Дарье» is ONE crossing
    even though the raw alignment breaks it around the shared «вой Д»."""
    hop = _hop("OUT", "answer", "p1", 0, 0, "", -1, -1, "")
    case = _case("obs-ans", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_mentions(_with_subs(_with_replies(
        _run("obs-ans"), "позвоню Кудрявцевой Диане", "позвоню Кузнецовой Дарье", ""),
        {"p1": "Кудрявцева Диана"}),
        (contracts.MentionRecord("p1", 0, -1, "Кудрявцевой Диане", 0),))
    spans = answer_spans(case, run)
    got = _one(case, run).hops
    problems: list[str] = []
    if len(spans) != 1:
        problems.append(f"expected one answer span, got {len(spans)}: {spans}")
    if len(got) != 1 or got[0].status != "observed":
        problems.append(f"expected one observed answer hop, got {[one.status for one in got]}")
    elif got[0].produced != "Кузнецовой Дарье" or got[0].reference != "Кудрявцевой Диане":
        problems.append(f"the span does not hold the whole name: {got[0].produced!r} / "
                        f"{got[0].reference!r}")
    untouched = _with_replies(run, "позвоню Кудрявцевой Диане", "позвоню Кудрявцевой Диане", "")
    left = _one(case, untouched).hops
    if not left or left[0].status != "residual":
        problems.append("a substitute the restoration never touched must be `residual`, "
                        f"got {[one.status for one in left]}")
    return problems


def test_an_insertion_on_the_boundary_is_not_lost() -> list[str]:
    """THE RESTORED WINDOW IS READ OFF THE RESTORED SIDE'S OWN OPCODES.

    «+72360987654» → «+79037654321» aligns as replace «236098»→«903», equal
    «7654», then a PURE INSERTION «321» with nothing on the raw side to measure
    it by. The window used to be carried across by the raw deltas — the two
    lines replayed below — which stopped at the end of the `equal` run and
    handed the comparator «+79037654»: a real value the gateway restored whole,
    truncated by the observer, and then counted as a form miss. 46 of
    `form_hOUT`'s 65 corpus misses and its single `answer_real` miss were this.

    Three things are asserted, and the fixture is worthless without the third:
    that the alignment really does put a zero-raw-width opcode on the window's
    right boundary (otherwise this case has stopped being the case it was built
    for), that the OLD arithmetic truncates it, and that the observer does not.
    """
    raw = "Готово. Пункт 1: +72360987654 — записано."
    restored = "Готово. Пункт 1: +79037654321 — записано."
    item = _item("q1", "PHONE", "+79037654321", "+79037654321", "i1", _in_message(0, 0, 12))
    hop = _hop("OUT", "answer", "q1", 0, 0, "", -1, -1, "")
    case = _case("obs-insert", "single", ("телефон",), (item,), (hop,))
    run = _with_subs(_with_replies(_run("obs-insert"), raw, restored, "Готово."),
                     {"q1": "+72360987654"})
    problems: list[str] = []
    opcodes = merged_opcodes(raw, restored)
    spans = answer_spans(case, run)
    if len(spans) != 1:
        return [f"expected one answer span, got {len(spans)}: {spans}"]
    span = spans[0]
    insertions = [one for one in opcodes
                  if one[0] == "replace" and one[1] == one[2] and one[1] == span.raw_end]
    if not insertions:
        problems.append("the alignment no longer puts a pure insertion on the window's right "
                        f"boundary, so this fixture pins nothing: {opcodes}")
    # The rule that was wrong, replayed: the replace's restored ends moved by
    # the RAW widening. It is written out rather than named so the test fails
    # if it ever stops being wrong on this input.
    index = next(i for i, one in enumerate(opcodes) if one[0] == "replace" and one[1] < one[2])
    _tag, opcode_raw_start, opcode_raw_end, new_start, new_end = opcodes[index]
    by_raw_deltas = restored[new_start - (opcode_raw_start - span.raw_start):
                             new_end + (span.raw_end - opcode_raw_end)]
    if by_raw_deltas != "+79037654":
        problems.append(f"the old arithmetic no longer truncates this input ({by_raw_deltas!r}), "
                        "so the fixture has stopped exercising the defect")
    got = [one for one in _one(case, run).hops if one.hop.owner == "answer"]
    if len(got) != 1 or got[0].status != "observed":
        problems.append(f"expected one observed answer hop, got {[one.status for one in got]}")
    elif got[0].produced != "+79037654321" or got[0].reference != "+72360987654":
        problems.append(f"the restored value comes back truncated: {got[0].produced!r} / "
                        f"{got[0].reference!r}")
    elif got[0].verdict is None or not got[0].verdict.same:
        problems.append("a phone the gateway restored whole reads as a form miss: "
                        f"{got[0].verdict.differs if got[0].verdict else None}")
    return problems


def test_the_widening_still_reaches_the_whole_occurrence() -> list[str]:
    """AND THE OTHER HALF: the widening the fix must not take away.

    «Кудрявцевой Диане» → «Кузнецовой Дарье» aligns into two replaces that hold
    «дрявце» and «иан» — fragments of a name that the comparator can say
    nothing about. The window is widened on the RAW side to the substitute's
    whole occurrence, and the restored side must follow it across the `equal`
    run between the two replaces. A fix for the insertion that derived the
    restored window from the replace alone would pass the test above and hand
    this one a syllable.
    """
    raw = "позвоню Кудрявцевой Диане завтра"
    restored = "позвоню Кузнецовой Дарье завтра"
    item = _item("p1", "NAME", "Кузнецова Дарья", "Кузнецова Дарья", "i1", _in_message(0, 0, 15))
    hop = _hop("OUT", "answer", "p1", 0, 0, "", -1, -1, "")
    case = _case("obs-widen", "single", ("звонок",), (item,), (hop,))
    run = _with_mentions(_with_subs(_with_replies(_run("obs-widen"), raw, restored, ""),
                                    {"p1": "Кудрявцева Диана"}),
                         (contracts.MentionRecord("p1", 0, -1, "Кудрявцевой Диане", 0),))
    problems: list[str] = []
    bare = [(raw[one[1]:one[2]], restored[one[3]:one[4]]) for one in merged_opcodes(raw, restored)
            if one[0] == "replace"]
    if not bare or any(len(left) >= len("Кудрявцевой Диане") for left, _right in bare):
        problems.append(f"the alignment no longer breaks the name into fragments ({bare}), "
                        "so this fixture does not ask for the widening")
    got = [one for one in _one(case, run).hops if one.hop.owner == "answer"]
    if len(got) != 1 or got[0].status != "observed":
        problems.append(f"expected one observed answer hop, got {[one.status for one in got]}")
    elif got[0].produced != "Кузнецовой Дарье" or got[0].reference != "Кудрявцевой Диане":
        problems.append(f"the widening no longer reaches the whole name: {got[0].produced!r} / "
                        f"{got[0].reference!r}")
    elif got[0].verdict is None or not got[0].verdict.same:
        problems.append("a name the gateway restored in the agent's own case reads as a form "
                        f"miss: {got[0].verdict.differs if got[0].verdict else None}")
    return problems


def test_residual_out() -> list[str]:
    """A substitute still standing in a tool leaf is `residual` and carries NO
    verdict: there is no form question about a value that never became real.

    THE OBSERVER DECIDES, NOT THE ENGINE. `ObservedCall.residual` is the
    gateway's own `residual_tokens` report, and the third case below is the
    one that matters: the fake reached the tool and the engine reported
    NOTHING. Reading the flag made that a clean `observed` hop with
    `form_match` comparing the fake to itself — the product's worst defect
    scored as a success by asking the defendant."""
    hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("obs-res", "single", (REAL_NAME,), (NAME,), (hop,))

    def one(restored: str, reported: tuple[str, ...]) -> object:
        return _one(case, _with_subs(_with_calls(_run("obs-res"), (_call(
            "crm_upsert_contact", {"contact": {"last_name": FAKE_NAME}},
            {"contact": {"last_name": restored}}, {"contact.last_name": reported}, "", 0),), (0,)),
            {"p1": FAKE_NAME})).hops[0]

    problems: list[str] = []
    got = one(FAKE_NAME, (FAKE_NAME,))
    if got.status != "residual" or got.verdict is not None:
        problems.append(f"a surviving substitute must be residual without a verdict, got {got.status}")
    if one(REAL_NAME, ()).status != "observed":
        problems.append("a restored leaf is clean; the engine reported nothing and there is nothing")
    silent = one(FAKE_NAME, ())
    if silent.status != "residual":
        problems.append("the fake reached the tool and the ENGINE reported nothing: the observer "
                        f"must still say residual, got {silent.status}")
    return problems


def test_out_unmasked_has_nothing_to_compare() -> list[str]:
    """A leaf the gateway never masked is `unmasked`, never `observed`.

    The reviewer's passthrough probe: no substitute minted, the agent wrote the
    REAL value, `/unmask_arguments` left it alone, so `restored == written` and
    `form_match` said «same». `form_hOUT`, `chain_form`, `chain_value` and
    `multi_all_out` all printed 100% for a gateway that protected nothing."""
    hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("obs-pass", "single", (REAL_NAME,), (NAME,), (hop,))
    missed = _with_calls(_run("obs-pass"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": REAL_NAME}},
        {"contact": {"last_name": REAL_NAME}}, {}, "", 0),), (0,))
    worked = _with_subs(_with_calls(_run("obs-pass"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": FAKE_NAME}},
        {"contact": {"last_name": REAL_NAME}}, {}, "", 0),), (0,)), {"p1": FAKE_NAME})
    problems: list[str] = []
    got = _one(case, missed).hops[0]
    if got.status != "leaf_foreign" or got.verdict is not None:
        problems.append(f"a leaf with no substitute in it must be `leaf_foreign`, got {got.status}")
    if _one(case, worked).hops[0].status != "observed":
        problems.append("a leaf that DID carry a substitute must stay observed — the fixture "
                        "would otherwise separate on nothing")
    if "unmasked" not in contracts.HOP_STATUSES:
        problems.append("contracts.HOP_STATUSES does not carry the status the observer emits")
    return problems


def test_out_reformatted_substitute_is_not_unmasked() -> list[str]:
    """The agent re-notated the substitute before writing it — «8 999 000-11-22»
    for a minted «+79990001122». The leaf DOES carry the substitute, and a
    check that looked for the surface or a `pieces_of` piece found neither: on
    Russian traffic that is the common case, and calling it `unmasked` would
    turn the gateway's own promise (follow the agent's notation) into a miss."""
    hop = _hop("OUT", "tool_arg", "p2", 0, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    case = _case("obs-note", "single", ("…",), (PHONE,), (hop,))
    run = _with_subs(_with_calls(_run("obs-note"), (_call(
        "crm_upsert_contact", {"contact": {"phone": "8 999 000-11-22"}},
        {"contact": {"phone": REAL_PHONE}}, {}, "", 0),), (0,)), {"p2": "+79990001122"})
    got = _one(case, run).hops[0]
    return [] if got.status == "observed" else [
        f"a reformatted substitute is still a substitute, got {got.status}"]


def test_memory_hop_reads_what_the_harness_records() -> list[str]:
    """The memory hop, decided from mentions the harness actually writes.

    `GatewayV5._note_message_mentions` records a message's mentions ONCE, when
    the message is pushed; the transcript then carries it forward. The observer
    used to ask for a re-recording of the first message at «the request after
    the last mention», which never exists, so EVERY IN/memory hop on the
    production path came back `leaked` — the memory family's headline defect
    was an artefact of the instrument."""
    recall = _hop("IN", "memory", "p1", 1, 4, "", -1, -1, "")
    case = _case("obs-mem", "memory_anaphora", ("…", "…"), (NAME,), (recall,))
    pushed = {0: ((0, len(REAL_NAME)),), 4: ()}
    carried = _with_masked(_with_mentions(_run("obs-mem"), (
        contracts.MentionRecord("p1", 0, -1, FAKE_NAME, 1),)), pushed)
    never = _with_masked(_run("obs-mem"), pushed)
    unreached = _with_masked(_with_mentions(_run("obs-mem"), (
        contracts.MentionRecord("p1", 0, -1, FAKE_NAME, 1),)), {0: ((0, len(REAL_NAME)),)})
    problems: list[str] = []
    got = _one(case, carried).hops[0]
    if got.status != "observed" or got.produced != FAKE_NAME:
        problems.append(f"the substitute the transcript carries is what the model read: {got.status}"
                        f" / {got.produced!r}")
    if _one(case, never).hops[0].status != "leaked":
        problems.append("the message was masked and left no mention: the real value went into the "
                        "context, which is `leaked`")
    if _one(case, unreached).hops[0].status != "absent":
        problems.append("a recall turn the run never reached is `absent`, not a miss the gateway owns")
    return problems


def test_derived_forms_are_needles() -> list[str]:
    """A substitute the agent TRANSLITERATED or squeezed to INITIALS is still
    the substitute, and `residual` must say so.

    Before this, `needles_of` knew four shapes and none of them was Latin, so
    «Pakhomova Olga» and «П.О.» matched nothing, `_out_status` answered
    `unmasked`, and `residual` — the line whose whole job is «a fake reached
    the consumer» — printed the leaf CLEAN with the fake standing in the
    customer's CRM. The corpus keeps 54 `derive` cases and 14 of them ask the
    agent for exactly these two forms, so this is the ordinary case of a
    declared family, not a corner."""
    arg = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.name")
    case = _case("obs-derived", "derive", (REAL_NAME,), (NAME,), (arg,))
    problems: list[str] = []
    for label, written in (("cyrillic", FAKE_NAME), ("translit", "Pakhomova Olga"),
                           ("translit, other table", "Pahomova Olga"),
                           ("squeezed initials", "П.О."), ("latin initials", "P.O.")):
        survived = _with_masked(_with_subs(_with_calls(
            _with_replies(_run("obs-derived"), "ок", "ок", "ок"),
            (_call("crm_upsert_contact", {"contact": {"name": written}},
                   {"contact": {"name": written}}, {}, "", 0),), (0,)),
            {"p1": FAKE_NAME}), {0: ((0, len(REAL_NAME)),)})
        got = _one(case, survived).hops[0]
        if got.status != "residual":
            problems.append(f"{label}: a fake left in the tool argument read {got.status!r}, "
                            f"not `residual`")
        restored = _with_masked(_with_subs(_with_calls(
            _with_replies(_run("obs-derived"), "ок", "ок", "ок"),
            (_call("crm_upsert_contact", {"contact": {"name": written}},
                   {"contact": {"name": REAL_NAME}}, {}, "", 0),), (0,)),
            {"p1": FAKE_NAME}), {0: ((0, len(REAL_NAME)),)})
        if _one(case, restored).hops[0].status != "observed":
            problems.append(f"{label}: a CORRECT derived-form round trip read "
                            f"{_one(case, restored).hops[0].status!r}, not `observed`")
    # AND THE NEEDLE MUST NOT INVENT ONE. Bare «ПО» is a preposition and an
    # abbreviation; the customer's own name transliterated is the customer's,
    # not a surviving fake; and another person entirely matches nothing.
    for text in ("Отправлено ПО почте", "Записал Ivanova Elena в CRM", "Записал Сидорова Петра"):
        if carries_any("NAME", (FAKE_NAME,), text, frozenset({"иван", "elen", "ivan", "елен",
                                                              "ие", "ie"})):
            problems.append(f"the derived needles fired on {text!r}, where no fake stands")
    return problems


def test_memory_reads_only_what_the_model_had_seen() -> list[str]:
    """A tool result the model has not read yet cannot carry a substitute into
    an earlier turn.

    `carried_substitute` took every tool-result mention (`msg == -1`)
    unconditionally, so a substitute first shown at request 9 was «carried
    into turn 4» and `leak` counted as PROTECTION a value the model had not
    been shown. The bound is the request the recall turn itself rode in
    (`turn_request`), which is the same clock the harness writes."""
    recall = _hop("IN", "memory", "p1", 1, 4, "", -1, -1, "")
    case = _case("obs-mem2", "memory_anaphora", ("…", "…"), (NAME,), (recall,))
    pushed = {0: ((0, len(REAL_NAME)),), 4: ()}

    def run_with(result_turn: int, mention_request: int, turn_request_index: int):
        """The record a LIVE run writes: `harness.push_call` appends the
        mention and the `ToolResultRecord` together, so the result's own turn
        is on disk beside the substitute it showed."""
        mentions = (contracts.MentionRecord("p1", -1, 7, FAKE_NAME, mention_request),
                    contracts.MentionRecord("p2", 4, -1, "+79990001122", turn_request_index))
        served = _result("crm_find_contact", result_turn, 0, "object", REAL_NAME,
                         FAKE_NAME, {"p1": (0, len(REAL_NAME))},
                         ((0, len(REAL_NAME), FAKE_NAME, "NAME"),), False)
        return _with_results(
            _with_masked(_with_mentions(_run("obs-mem2"), mentions), pushed),
            (replace(served, seq=7),))

    problems: list[str] = []
    before = run_with(2, 3, 5)
    if carried_substitute(before, "p1", 4) != FAKE_NAME:
        problems.append("a result the model read BEFORE the recall turn must still carry")
    if _one(case, before).hops[0].status != "observed":
        problems.append("a substitute carried into the turn is `observed`")
    after = run_with(6, 9, 5)
    if carried_substitute(after, "p1", 4) != "":
        problems.append("a result shown AFTER the recall turn was carried backwards into it")
    if _one(case, after).hops[0].status == "observed":
        problems.append("`leak` counted as protection a substitute the model had not seen")
    # The bound is an UPPER bound at every step: an earlier message's request
    # is a floor, and using it would exclude a result the model really read.
    only_earlier = _with_masked(_with_mentions(_run("obs-mem2"), (
        contracts.MentionRecord("p2", 0, -1, "+79990001122", 1),
        contracts.MentionRecord("p1", -1, 0, FAKE_NAME, 4))), pushed)
    if turn_request(only_earlier, 4) < 4:
        problems.append("the turn's request was bounded by an EARLIER message — a floor read "
                        "as a ceiling")
    if carried_substitute(only_earlier, "p1", 4) != FAKE_NAME:
        problems.append("a result read before the recall turn was dropped for want of evidence")
    return problems


def test_answer_needles_survive_inflection() -> list[str]:
    """A correctly restored DECLINED name and a REFORMATTED phone are answer
    hops, not `absent`. The needles used to be whole surfaces and whole parts,
    so «Передал Пахомовой Ольге» → «Передал Ивановой Елене» — two of the four
    registers the corpus is written in — was invisible to the answer leg."""
    name_hop = _hop("OUT", "answer", "p1", 0, 0, "", -1, -1, "")
    name_case = _case("obs-decl", "single", (REAL_NAME,), (NAME,), (name_hop,))
    declined = _with_subs(_with_replies(
        _run("obs-decl"), "Передал Пахомовой Ольге, всё готово.",
        "Передал Ивановой Елене, всё готово.", ""), {"p1": FAKE_NAME})
    phone_hop = _hop("OUT", "answer", "p2", 0, 0, "", -1, -1, "")
    phone_case = _case("obs-note2", "single", ("…",), (PHONE,), (phone_hop,))
    renotated = _with_subs(_with_replies(
        _run("obs-note2"), "Звоните на +7 (999) 000-11-22.",
        "Звоните на +7 (916) 402-11-87.", ""), {"p2": "+79990001122"})
    problems: list[str] = []
    for label, case, run in (("declined", name_case, declined), ("renotated", phone_case, renotated)):
        hops = _one(case, run).hops
        if not hops or hops[0].status != "observed":
            problems.append(f"{label}: expected an observed answer hop, got "
                            f"{[one.status for one in hops]}")
    return problems


def test_residual_answer_reads_the_whole_reply() -> list[str]:
    """A substitute standing in the reply the customer reads is `residual`
    wherever it stands, in whatever form, declared or not.

    Three inputs the alignment-based scan could not see: a DECLINED substitute
    that survived, a REFORMATTED one, and one belonging to an item the case
    declared no answer hop for. And one it must NOT fire on: a restored reply
    whose real name shares a given name with the substitute."""
    from bench.agentpii5.observe import residual_answer_items
    problems: list[str] = []
    cases = (
        ("declined", NAME, {"p1": FAKE_NAME}, "Передал Пахомовой Ольге.", True),
        ("renotated", PHONE, {"p2": "+79990001122"}, "Звоните на +7 (999) 000-11-22.", True),
        ("restored", NAME, {"p1": FAKE_NAME}, "Передал Ивановой Елене.", False),
    )
    for label, item, subs, reply, expected in cases:
        case = _case(f"obs-res-{label}", "single", ("…",), (item,), ())
        run = _with_subs(_with_replies(_run(f"obs-res-{label}"), reply, reply, ""), subs)
        left = bool(residual_answer_items(case, run))
        if left != expected:
            problems.append(f"{label}: residual_answer_items said {left}, expected {expected}")
    # The engine may mint a substitute that SHARES a given name with the real
    # value; the restored reply is full of real values. Without the own-stem
    # filter the critical-defect line fires on the product working.
    shared = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
    case = _case("obs-res-shared", "single", ("…",), (shared,), ())
    reply = "Передал Ивановой Елене."
    run = _with_subs(_with_replies(_run("obs-res-shared"), reply, reply, ""),
                     {"p1": "Пахомова Елена"})
    if residual_answer_items(case, run):
        problems.append("a substitute sharing the customer's own given name is not evidence that "
                        "the substitute survived")
    return problems


def test_leaked_in_partial_cover() -> list[str]:
    """Coverage, not overlap. A piece that covers all but the last word of the
    slot leaves the surname in the model's context, and calling that `observed`
    is exactly the 69 partial leaks AgentPII v1 hid behind 97.6% recall."""
    hop = _hop("IN", "tool", "p1", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
    case = _case("obs-part", "single", ("…",), (NAME,), (hop,))
    span = (0, len(REAL_NAME))
    partial = _with_results(_run("obs-part"), (_result(
        "crm_find_contact", 0, 0, "single", REAL_NAME, "Пахомова Елена", {"p1": span},
        ((0, 8, "Пахомова", "NAME"),), False),))
    whole = _with_results(_run("obs-part"), (_result(
        "crm_find_contact", 0, 0, "single", REAL_NAME, FAKE_NAME, {"p1": span},
        ((span[0], span[1], FAKE_NAME, "NAME"),), False),))
    missing = _with_results(_run("obs-part"), (_result(
        "crm_find_contact", 0, 0, "single", REAL_NAME, REAL_NAME, {}, (), False),))
    problems: list[str] = []
    if _one(case, partial).hops[0].status != "leaked":
        problems.append("a partially covered slot must be `leaked`")
    if _one(case, whole).hops[0].status != "observed":
        problems.append("a fully covered slot must be `observed`")
    if _one(case, missing).hops[0].status != "absent":
        problems.append("a result with no slot for the item did not happen; it is `absent`, "
                        "never `leaked` — there was no real value in it to leak")
    return problems


def test_optional_absent_not_emitted() -> list[str]:
    """An optional hop the agent legitimately skipped is not emitted at all; a
    required one is `absent` and counts as a miss. Defaulting everything to
    optional would let an agent that calls nothing pass every form line."""
    required = Hop(kind="OUT", owner="tool_arg", item_id="p1", hop_index=0, turn=0,
                   tool_name="crm_upsert_contact", call_ordinal=1, parallel_group="",
                   source_hop=-1, path="contact.last_name", optional=False)
    optional = replace(required, optional=True)
    run = _run("obs-opt")
    problems: list[str] = []
    hard = _case("obs-opt", "retry_same_tool", ("…",), (NAME,), (required,))
    soft = _case("obs-opt-2", "retry_same_tool", ("…",), (NAME,), (optional,))
    if [one.status for one in _one(hard, run).hops] != ["absent"]:
        problems.append("a required hop that did not happen must be `absent`")
    if _one(soft, run).hops:
        problems.append("an optional hop that did not happen must not be emitted")
    return problems


def test_extra_hop_undeclared() -> list[str]:
    """A crossing the agent made that the case did not declare is observed (it
    is real data crossing) with `declared=False` and `hop_index=-1`, so it
    counts in the form lines and in NO denominator the case owns."""
    case = _case("obs-extra", "single", ("…",), (NAME, PHONE), ())
    run = _with_subs(_with_calls(_run("obs-extra"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": FAKE_NAME, "phone": "+79990001122"}},
        {"contact": {"last_name": REAL_NAME, "phone": REAL_PHONE}}, {}, "", 0),), (0,)),
        {"p1": FAKE_NAME, "p2": "+79990001122"})
    hops = _one(case, run).hops
    problems: list[str] = []
    if len(hops) != 2:
        problems.append(f"two identity leaves, two extra hops; got {len(hops)}")
    for hop in hops:
        if hop.declared or hop.hop.hop_index != -1:
            problems.append(f"an undeclared crossing must be declared=False/-1: {hop.hop}")
    if {hop.hop.item_id for hop in hops} != {"p1", "p2"}:
        problems.append(f"the items were not resolved by substitute: "
                        f"{[hop.hop.item_id for hop in hops]}")
    plain = _with_calls(_run("obs-extra"), (_call(
        "crm_upsert_contact", {"id": "A-1"}, {"id": "A-1"}, {}, "", 0),), (0,))
    if _one(case, plain).hops:
        problems.append("a `plain` leaf is not a crossing and must emit nothing")
    return problems


def test_parent_path_joins_the_leaves_in_field_order() -> list[str]:
    """One value carried by SEVERAL leaves is ONE hop.

    `leaf_text` joins the leaves under a parent path with `contracts.FIELD_SEP`
    in the TOOL's field order, and the comparator reads `by_fields` off that
    separator. Both halves were exercised by nothing: the order check is not
    decorative — sorting the keys alphabetically puts `address.building`
    before `address.locality`, so «Ижевск, Клубная, 85» would be compared as
    «85, Ижевск, Клубная» and every `house_marker` and `generic_position`
    feature would be read off the wrong word. A blank field is skipped rather
    than joined as an empty segment, or a flat the agent left out would look
    like a missing piece of the street."""
    address = _item("p4", "LOC", "Ижевск, улица Клубная, 85", "Ижевск, улица Клубная, 85", "i1",
                    _in_message(0, 0, 25))
    hop = _hop("OUT", "tool_arg", "p4", 0, 0, "courier_book", 0, -1, "address")
    case = _case("obs-parent", "single", ("…",), (address,), (hop,))
    run = _with_subs(_with_calls(_run("obs-parent"), (_call(
        "courier_book",
        {"address": {"locality": "Самара", "street": "Луговая", "building": "10", "sflat": ""}},
        {"address": {"locality": "Ижевск", "street": "Клубная", "building": "85", "sflat": ""}},
        {}, "", 0),), (0,)), {"p4": "Самара, улица Луговая, 10"})
    got = _one(case, run).hops[0]
    sep = contracts.FIELD_SEP
    problems: list[str] = []
    if got.produced != f"Ижевск{sep}Клубная{sep}85":
        problems.append(f"the leaves must join in the tool's field order, got {got.produced!r}")
    if got.reference != f"Самара{sep}Луговая{sep}10":
        problems.append(f"the written half joins the same way, got {got.reference!r}")
    if got.status != "observed" or got.verdict is None:
        problems.append(f"a by-fields leaf is an ordinary OUT hop, got {got.status}")
    elif "by_fields" in got.verdict.differs:
        problems.append("both halves came from the same leaves; `by_fields` cannot differ here")
    return problems


def test_seed_item_has_no_message_span() -> list[str]:
    """A seed item's locus carries no message offsets; the observer must not
    index the transcript with them. Pinned because the IN/user path and the
    IN/tool path share a reader and the seed locus is `msg = -1`."""
    seed = _item("p7", "NAME", OTHER_NAME, OTHER_NAME, "i2",
                 Locus(kind="seed", msg=-1, start=-1, end=-1, record="s1", path="name"))
    hop = _hop("IN", "tool", "p7", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
    case = _case("obs-seed", "single", ("…",), (seed,), (hop,))
    run = _with_results(_run("obs-seed"), (_result(
        "crm_find_contact", 0, 0, "single", OTHER_NAME, FAKE_NAME, {"p7": (0, len(OTHER_NAME))},
        ((0, len(OTHER_NAME), FAKE_NAME, "NAME"),), False),))
    got = _one(case, run).hops[0]
    return [] if got.status == "observed" and got.reference == OTHER_NAME else [
        f"a seed item read from a tool result must be observed against its own text: {got}"]


# --- contracts §4bis: the needle layer, rule by rule ------------------------------------

# One value per type, in the notation the corpus writes it in. The list is the
# closed `contracts.FORM_TYPES` minus nothing: a type left out of it would be a
# type whose leak check nobody ever ran.
_VALUES: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("NAME", "Иванова Елена Петровна",
     {"surname": "Иванова", "given": "Елена", "patronymic": "Петровна"}),
    ("LOC", "омск переулок барышникова 7кв111",
     {"city": "омск", "street": "барышникова", "house": "7", "flat": "111"}),
    ("PHONE", "+7 999 000-11-22", {"digits": "9990001122"}),
    ("CARD", "2200 2334 2029 7500", {"digits": "2200233420297500"}),
    ("SNILS", "168-408-927 05", {"digits": "16840892705"}),
    ("INN", "500 100 732 259", {"digits": "500100732259"}),
    ("PASSPORT", "6942 474016", {"series": "6942", "number": "474016"}),
    ("DOB", "05.06.1988", {"iso": "1988-06-05"}),
    ("DATE", "05.06.1988", {"iso": "1988-06-05"}),
    ("EMAIL", "voronina96@gmail.com", {"local": "voronina96", "domain": "gmail.com"}),
    ("PLATE", "А220ММ96",
     {"letter": "А", "digits": "220", "pair": "ММ", "region": "96"}),
)


def _typed_item(pii_type: str, surface: str, parts: dict[str, str]):  # noqa: ANN202
    """A fixture item with the roles the CORPUS would have built it from,
    rather than the ones `parts_of` reads back off the surface — which is the
    whole difference `item_needles` exists for (contracts §4bis, N3/N4)."""
    return replace(_item("n1", pii_type, surface, surface, "i1",
                         _in_message(0, 0, len(surface))), parts=parts)


def test_a_text_that_is_the_value_contains_it() -> list[str]:
    """N1, the layer's own tripwire. `metrics._surviving_piece` was a folded
    SUBSTRING test over parts `parts_of` had already NORMALISED, so it asked
    for a string that does not occur in the value itself: `pieces_of` returned
    () for every plate, the bare digit run for a spaced card, the ISO fold for
    a dotted date and an ALPHABETICALLY SORTED blob for a comma-less address.
    Over every written surface of the corpus it failed on 329 of 329 plates,
    156 of 176 СНИЛС and 29.5 % of addresses — the leak check under six
    lines, blind to a value standing in the open."""
    problems: list[str] = []
    for pii_type, surface, parts in _VALUES:
        if not item_survives_in(_typed_item(pii_type, surface, parts), surface, surface):
            problems.append(f"{pii_type}: the value does not survive in ITSELF ({surface!r})")
        if not survives_in(pii_type, surface, surface, frozenset()):
            problems.append(f"{pii_type}: the substitute does not survive in ITSELF")
    return problems


def test_a_value_inside_a_longer_text_is_found() -> list[str]:
    """N2, in the shapes a MODEL writes a value: verbatim inside prose,
    renotated, respaced, dictated. Each pair is (what the value is, what the
    text says), and the text is never the value."""
    pairs: tuple[tuple[str, str, str, dict[str, str]], ...] = (
        ("NAME", "Пахомова Ольга", "передал Пахомовой Ольге вчера", {}),
        ("PHONE", "+79990001122", "звоните 8 (999) 000-11-22 после двух", {}),
        ("PLATE", "А220ММ96", "номер А 22 0ММ 96 записан", {}),
        ("DOB", "05.06.1988", "родился 1988-06-05 в Омске", {}),
        ("CARD", "2200233420297500", "карта 2200 2334 2029 7500 списана", {}),
        ("PHONE", "восемь девятьсот девяносто девять ноль ноль ноль одиннадцать двадцать два",
         "записал +7 999 000-11-22 в CRM", {}),
    )
    problems: list[str] = []
    for pii_type, surface, text, parts in pairs:
        if not survives_in(pii_type, surface, text, frozenset()):
            problems.append(f"{pii_type}: {surface!r} not found in {text!r}")
        if surface in text:
            problems.append(f"the {pii_type} pair is verbatim, so it proves nothing")
    # AND IT MUST NOT INVENT ONE. Another person, another number, another day.
    for pii_type, surface, text in (
            ("NAME", "Пахомова Ольга", "передал Сидорову Петру"),
            ("PHONE", "+79990001122", "звоните 8 (999) 000-11-23"),
            ("PLATE", "А220ММ96", "номер А 22 1ММ 96"),
            ("DOB", "05.06.1988", "родился 1988-06-06")):
        if survives_in(pii_type, surface, text, frozenset()):
            problems.append(f"{pii_type}: {surface!r} invented in {text!r}")
    return problems


def test_a_generic_word_is_not_an_identifying_piece() -> list[str]:
    """N4. The settlement, the street's generic word, the markers and the month
    names belong to everybody. A leak check that counted one would demand the
    engine mask «улица» and would call a restored date a surviving value."""
    address = "Ижевск, улица Клубная, 85, кв 14"
    item = _typed_item("LOC", address, {"city": "ижевск", "street": "клубная",
                                        "house": "85", "flat": "14"})
    problems: list[str] = []
    if item_survives_in(item, address, "Ижевск, улица Луговая, 10, кв 3"):
        problems.append("a surviving city and generic word read as a surviving piece")
    if not item_survives_in(item, address, "Самара, улица Клубная, 10"):
        problems.append("the street is not an identifying piece")
    for word in ("улица", "дом", "марта"):
        if word in {needle.text for needle in item_needles(item, address)}:
            problems.append(f"{word!r} is a needle")
    # AND ON THE PARSED PATH, where it bites. `parts_of` lumps every word it
    # cannot type into the street blob, region words and «область» included,
    # and a street NAMED after a month («улица 8 Марта») puts a month word
    # there: a needle built from either would report a leak in every address
    # that names a region and in every restored date.
    blob = "Ростовская область, г Ростов-на-дону, ул Дзержинского, д 44"
    stems = {needle.text for needle in value_needles("LOC", blob) if needle.kind == "stem"}
    if "обла" in stems:
        problems.append(f"a region word is an identifying piece: {sorted(stems)}")
    if "дзер" not in stems:
        problems.append(f"the street lost its needle to the filter: {sorted(stems)}")
    month = {needle.text for needle in value_needles("LOC", "улица 8 Марта, 12")
             if needle.kind == "stem"}
    if month:
        problems.append(f"a month name is an identifying piece: {sorted(month)}")
    return problems


def test_the_street_gets_one_needle_per_word() -> list[str]:
    """N3. `parts_of` lumps every word of an address it cannot type into ONE
    alphabetically sorted `street` blob, so the single four-character prefix
    was «можг» — the CITY — and the street had none. 626 of the corpus's
    2 770 LOC items were in that state and 294 carried a needle with a SPACE in
    it, which no word token can ever match."""
    surface = "можга школьная дом 64 четвёртый подъезд квартира 35"
    stems = {needle.text for needle in value_needles("LOC", surface) if needle.kind == "stem"}
    problems: list[str] = []
    if "школ" not in stems:
        problems.append(f"the street has no stem needle: {sorted(stems)}")
    if any(" " in stem for stem in stems):
        problems.append(f"a needle with a space in it can never match a word: {sorted(stems)}")
    return problems


def test_one_exempt_path() -> list[str]:
    """N5. The customer's OWN renderings are cancelled through `exempt` and
    through nothing else: a stem the real value carries proves nothing, while a
    whole surface and a digit signature are never cancelled — a fake phone does
    not wear the real one's digits."""
    case = _case("obs-exempt", "single", (REAL_NAME,), (NAME, PHONE), ())
    own = own_stems(case)
    problems: list[str] = []
    if survives_in("NAME", "Пахомова Елена", "записал Елене", own):
        problems.append("a given name the CUSTOMER carries read as a surviving fake")
    if not survives_in("NAME", "Пахомова Елена", "записал Пахомовой", own):
        problems.append("the fake's own surname was cancelled by the exemption")
    if not survives_in("PHONE", "+79990001122", "8 999 000-11-22", own):
        problems.append("a digit signature was cancelled by the exemption")
    return problems


def test_a_four_letter_name_survives_declension() -> list[str]:
    """A Russian ending takes one character, so a four-character prefix of a
    four-letter word is the WHOLE word: «Анну» stopped matching «Анна» and a
    four-letter given name left in a tool argument in another case read
    `unmasked`, with `residual` blind to it for no reason but the length."""
    problems: list[str] = []
    if not survives_in("NAME", "Анна", "записал Анну", frozenset()):
        problems.append("a declined four-letter name is invisible")
    if stem_of("Пахомова") != "пахо":
        problems.append("a long word no longer takes the four-character stem")
    if survives_in("NAME", "Анна", "записал Ольгу", frozenset()):
        problems.append("the short stem invented a name that is not there")
    return problems


def test_a_decomposed_leaf_is_judged_by_its_own_role() -> list[str]:
    """N6, the blocker, and it is TWO-SIDED. `_out_status` asked `carries_any`
    of the needles of the WHOLE substitute, and no needle of a whole address
    can live in `address.house` = «79»: a house number is below `MIN_PIECE`,
    the settlement and the generic word are generic, and a digit-typed value's
    signature is the whole digit string. The SAME leaf therefore printed
    `unmasked` for a gateway that restored it and for one that left the fake
    standing — un-earnable and un-failable at once. Three gateways, three
    statuses, one leaf."""
    item = _typed_item("LOC", "Ижевск, улица Клубная, 46",
                       {"city": "ижевск", "street": "клубная", "house": "46"})
    hop = _hop("OUT", "tool_arg", "n1", 0, 0, "crm_upsert_contact", 0, -1,
               "contact.address.house")
    case = _case("obs-house", "single", ("адрес",), (item,), (hop,))

    def _status(written: str, restored: str) -> str:
        run = _with_subs(_with_calls(_run("obs-house"), (_call(
            "crm_upsert_contact", {"contact": {"address": {"house": written}}},
            {"contact": {"address": {"house": restored}}}, {}, "", 0),), (0,)),
            {"n1": "Самара, улица Луговая, 79"})
        return _one(case, run).hops[0].status

    problems: list[str] = []
    for label, written, restored, want in (
            ("restored", "79", "46", "observed"),
            ("fake left standing", "79", "79", "residual"),
            ("never masked", "46", "46", "not_masked")):
        got = _status(written, restored)
        if got != want:
            problems.append(f"house leaf, {label}: read {got!r}, must be {want!r}")
    if not leaf_holds("LOC", ("Самара, улица Луговая, 79",), {}, "46", "79"):
        problems.append("the fake house is not read as a piece of the fake address")
    if leaf_holds("LOC", ("Самара, улица Луговая, 79",), {}, "46", "46"):
        problems.append("the customer's own house number read as a piece of the fake")
    return problems


def test_a_spoken_substitute_is_found_written() -> list[str]:
    """45 % of the corpus is the voice register. A substitute the model READ as
    «восемь девятьсот…» and wrote into a tool as digits carried no needle
    of its spoken surface at all — `digits_of` is "" there — so the leaf read
    `unmasked` and the gateway's own restoration was invisible to `residual`,
    `round_trip` and `retry_form`."""
    spoken = "восемь девятьсот девяносто девять ноль ноль ноль одиннадцать двадцать два"
    problems: list[str] = []
    if not survives_in("PHONE", spoken, "+7 999 000-11-22", frozenset()):
        problems.append("a dictated substitute written back as digits is invisible")
    if survives_in("PHONE", spoken, "+7 999 000-11-23", frozenset()):
        problems.append("the spoken digits matched a DIFFERENT number")
    return problems


def test_an_unknown_needle_kind_raises() -> list[str]:
    """`NEEDLE_KINDS` is closed and every kind has a way of being looked for. A
    silent «no match» for a shape nobody implemented is how a needle comes to
    be declared and never searched — which is the whole story of `pieces_of`."""
    problems: list[str] = []
    try:
        _needle_spans(Needle(kind="rumour", role="", text="x"), "x")
        problems.append("an unknown needle kind returned instead of raising")
    except ObserveError:
        pass
    found = {needle.kind for _type, surface, parts in _VALUES
             for needle in value_needles(_type, surface)}
    missing = set(contracts.NEEDLE_KINDS) - found - {"initials"}
    if missing:
        problems.append(f"declared needle kinds nothing ever builds: {sorted(missing)}")
    return problems


def test_a_shared_answer_span_is_narrowed_to_one_item() -> list[str]:
    """A rewritten region holding TWO data gives the form comparator a string
    with an e-mail in it and asks whether a PHONE's grouping is the same — a
    verdict about nothing, and 254 of the form misses a perfect gateway
    printed. Each side is narrowed by its OWN occurrences."""
    phone = _item("q1", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 0, 12))
    mail = _item("q2", "EMAIL", "elena@mail.ru", "elena@mail.ru", "i1", _in_message(0, 13, 26))
    hop = _hop("OUT", "answer", "q1", 0, 0, "", -1, -1, "")
    other = _hop("OUT", "answer", "q2", 1, 0, "", -1, -1, "")
    case = _case("obs-shared", "single", ("контакты",), (phone, mail), (hop, other))
    run = _with_subs(_with_replies(_run("obs-shared"),
                                   "Готово. +72507599608. smumknko@example.ru.",
                                   f"Готово. {REAL_PHONE}. elena@mail.ru.",
                                   "Готово."),
                     {"q1": "+72507599608", "q2": "smumknko@example.ru"})
    got = {one.hop.item_id: one for one in _one(case, run).hops if one.hop.owner == "answer"}
    problems: list[str] = []
    for item_id, wrong in (("q1", "@"), ("q2", "+7")):
        one = got.get(item_id)
        if one is None:
            problems.append(f"{item_id}: no answer hop")
            continue
        if wrong in one.reference or wrong in one.produced:
            problems.append(f"{item_id}: the other datum is still in the pair "
                            f"({one.produced!r}, {one.reference!r})")
        if one.verdict is None or not one.verdict.same:
            problems.append(f"{item_id}: a correct answer read as a form miss "
                            f"({one.verdict.differs if one.verdict else None})")
    return problems


def _sms(written: str, restored: str) -> tuple[CaseV5, ArmRunV5]:
    """One PHONE crossing a FREE leaf — `notify_sms.text`, the SMS body a live
    agent writes prose into. The substitute is written grouped, so the two
    notations are distinguishable at all."""
    phone = _item("s1", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 0, 12))
    hop = _hop("OUT", "template", "s1", 0, 0, "notify_sms", 0, -1, "text")
    case = _case("obs-sms", "single", ("напишите клиенту",), (phone,), (hop,))
    run = _with_subs(_with_calls(_run("obs-sms"),
                                 (_call("notify_sms", {"to": "+7 999 000-11-22", "text": written},
                                        {"to": REAL_PHONE, "text": restored}, {}, "", 0),),
                                 (0,)),
                     {"s1": "+7 999 000-11-22"})
    return case, run


FREE_LEAF_CANON = "Курьер позвонит на +79164021187 в 10:00, заказ №48213."
FREE_LEAF_AGENT = "Курьер позвонит на +7 916 402-11-87 в 10:00, заказ №48213."
FREE_LEAF_WRITTEN = "Курьер позвонит на +7 999 000-11-22 в 10:00, заказ №48213."


def test_a_free_leaf_is_compared_by_the_value_not_the_sentence() -> list[str]:
    """THE SENTENCE IS NOT THE DATUM. Every extractor in `form.py` reads the
    whole string it is handed, so a second number in the same SMS — an order
    number, a time — made `prefix` and `grouping` read `other` on BOTH sides
    and `separators` read `mixed` on both, and a gateway that answered the
    canon while the agent wrote «+7 999 000-11-22» scored «same».

    BOTH DIRECTIONS, or this pins nothing: the canon in the agent's sentence
    must DIFFER, and the agent's own notation in the same sentence must MATCH.
    Measured on the corpus: 781 declared OUT hops sit on free leaves, and all
    54 summary/PHONE hops of the phone-canon mutant scored «same» before the
    narrowing and «differs» after it."""
    problems: list[str] = []
    canon = _one(*_sms(FREE_LEAF_WRITTEN, FREE_LEAF_CANON)).hops[0]
    if canon.status != "observed" or canon.verdict is None:
        return [f"the canon leaf must be an ordinary OUT hop, got {canon.status}"]
    if "заказ" in canon.produced or "заказ" in canon.reference:
        problems.append(f"the sentence reached the comparator: "
                        f"({canon.produced!r}, {canon.reference!r})")
    if canon.verdict.same:
        problems.append("a canon phone against a grouped one scored «same» — the leaf's "
                        "own prose is being compared, not the value")
    elif not {"prefix", "grouping"} & canon.verdict.differs:
        problems.append(f"the notation difference is named by {sorted(canon.verdict.differs)}, "
                        f"which does not include the prefix or the grouping")
    kept = _one(*_sms(FREE_LEAF_WRITTEN, FREE_LEAF_AGENT)).hops[0]
    if kept.verdict is None or not kept.verdict.same:
        problems.append(f"the SAME sentence with the agent's own notation must MATCH, got "
                        f"{None if kept.verdict is None else sorted(kept.verdict.differs)} "
                        f"on ({kept.produced!r}, {kept.reference!r})")
    return problems


def test_a_narrowing_never_truncates_the_value() -> list[str]:
    """THE OTHER HALF OF THE NARROWING, and the half a first version got wrong.

    A narrowing built from ROLE needles can hand the comparator a PART: a
    by-fields address written «Самара⟦SEP⟧Луговая⟦SEP⟧10» holds no whole
    reading of «Самара, улица Луговая, 10» — the separators are the tool's —
    so the only needle that lands is the street stem, and narrowing to it
    compares «Луговая» for a ten-feature LOC value. `own_stretch` therefore
    narrows by WHOLE readings alone and otherwise hands back the leaf.

    Pinned here as well as through `parent_path_joins_the_leaves_in_field_
    order` because that check reads the joined text and this one reads the
    rule: a stretch shorter than the value is a truncation, not a narrowing."""
    value = "Самара, улица Луговая, 10"
    by_fields = f"Самара{contracts.FIELD_SEP}Луговая{contracts.FIELD_SEP}10"
    problems: list[str] = []
    if own_stretch("LOC", by_fields, (value,)):
        problems.append(f"a by-fields leaf was narrowed to "
                        f"{own_stretch('LOC', by_fields, (value,))!r}, which is a part of "
                        f"{value!r}, not a place it stands whole")
    produced, reference = own_pair("LOC", by_fields, (value,), by_fields, (value,))
    if (produced, reference) != (by_fields, by_fields):
        problems.append(f"an unlocatable value must leave the leaf whole, got "
                        f"({produced!r}, {reference!r})")
    prose = f"Курьер приедет на {value} сегодня."
    if own_stretch("LOC", prose, (value,)) != value:
        problems.append(f"a value standing WHOLE in prose must still be narrowed to itself, "
                        f"got {own_stretch('LOC', prose, (value,))!r}")
    return problems


A_REAL, A_FAKE = "Васильев Иван Павлович", "Соколов Пётр Иванович"
B_REAL, B_FAKE = "Букин Сергей Иванович", "Ершов Иван Олегович"


def test_an_answer_hop_is_judged_on_its_own_region() -> list[str]:
    """TWO PEOPLE IN ONE REPLY, and each region names both.

    `answer_spans` attributes a region to every item whose needles reach into
    it, and the given-name stem «иван» of one substitute is the head of the
    other's patronymic «Иванович» — so the first region lists BOTH items.
    Taking the first such region judged «Букин Сергей Иванович» on the text
    that carries «Васильев Иван Павлович»; the old stem-wise narrowing then
    cut that text down to «иван» and the value check accepted it, so two
    wrong readings cancelled and the line printed a hit. On the corpus this
    was `same_tool_other_target-001` and -019, and it is why `answer_real`
    read 637/637 while two of its answers carried another person's name."""
    a = _item("a1", "NAME", A_REAL, A_REAL, "i1", _in_message(0, 0, len(A_REAL)))
    b = _item("b1", "NAME", B_REAL, B_REAL, "i2", _in_message(0, 30, 30 + len(B_REAL)))
    case = _case("obs-two", "single", ("двое",), (a, b),
                 (_hop("OUT", "answer", "a1", 0, 0, "", -1, -1, ""),
                  _hop("OUT", "answer", "b1", 1, 0, "", -1, -1, "")))
    run = _with_subs(_with_replies(
        _run("obs-two"),
        f"Готово. Пункт 1: {A_FAKE} — записано. Пункт 2: {B_FAKE} — записано.",
        f"Готово. Пункт 1: {A_REAL} — записано. Пункт 2: {B_REAL} — записано.",
        "Готово."), {"a1": A_FAKE, "b1": B_FAKE})
    problems: list[str] = []
    spans = answer_spans(case, run)
    if not any(len(span.item_ids) > 1 for span in spans):
        problems.append("the fixture no longer produces a region naming two items, so it "
                        "cannot tell the two attributions apart")
    got = {one.hop.item_id: one for one in _one(case, run).hops if one.hop.owner == "answer"}
    for item_id, real, fake in (("a1", A_REAL, A_FAKE), ("b1", B_REAL, B_FAKE)):
        one = got.get(item_id)
        if one is None:
            problems.append(f"{item_id}: no answer hop")
            continue
        if one.produced != real or one.reference != fake:
            problems.append(f"{item_id}: judged on another person's region — "
                            f"({one.produced!r}, {one.reference!r}), expected "
                            f"({real!r}, {fake!r})")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("in_orientation", test_in_orientation),
        ("out_orientation", test_out_orientation),
        ("template_owner", test_template_owner),
        ("answer_alignment", test_answer_alignment),
        ("an_insertion_on_the_boundary_is_not_lost",
         test_an_insertion_on_the_boundary_is_not_lost),
        ("the_widening_still_reaches_the_whole_occurrence",
         test_the_widening_still_reaches_the_whole_occurrence),
        ("residual_out", test_residual_out),
        ("out_unmasked_has_nothing_to_compare", test_out_unmasked_has_nothing_to_compare),
        ("out_reformatted_substitute_is_not_unmasked", test_out_reformatted_substitute_is_not_unmasked),
        ("memory_hop_reads_what_the_harness_records", test_memory_hop_reads_what_the_harness_records),
        ("derived_forms_are_needles", test_derived_forms_are_needles),
        ("memory_reads_only_what_the_model_had_seen", test_memory_reads_only_what_the_model_had_seen),
        ("answer_needles_survive_inflection", test_answer_needles_survive_inflection),
        ("residual_answer_reads_the_whole_reply", test_residual_answer_reads_the_whole_reply),
        ("leaked_in_partial_cover", test_leaked_in_partial_cover),
        ("optional_absent_not_emitted", test_optional_absent_not_emitted),
        ("extra_hop_undeclared", test_extra_hop_undeclared),
        ("parent_path_joins_the_leaves_in_field_order",
         test_parent_path_joins_the_leaves_in_field_order),
        ("seed_item_has_no_message_span", test_seed_item_has_no_message_span),
        ("a_text_that_is_the_value_contains_it", test_a_text_that_is_the_value_contains_it),
        ("a_value_inside_a_longer_text_is_found", test_a_value_inside_a_longer_text_is_found),
        ("a_generic_word_is_not_an_identifying_piece",
         test_a_generic_word_is_not_an_identifying_piece),
        ("the_street_gets_one_needle_per_word", test_the_street_gets_one_needle_per_word),
        ("one_exempt_path", test_one_exempt_path),
        ("a_four_letter_name_survives_declension", test_a_four_letter_name_survives_declension),
        ("a_decomposed_leaf_is_judged_by_its_own_role",
         test_a_decomposed_leaf_is_judged_by_its_own_role),
        ("a_spoken_substitute_is_found_written", test_a_spoken_substitute_is_found_written),
        ("an_unknown_needle_kind_raises", test_an_unknown_needle_kind_raises),
        ("a_shared_answer_span_is_narrowed_to_one_item",
         test_a_shared_answer_span_is_narrowed_to_one_item),
        ("a_free_leaf_is_compared_by_the_value_not_the_sentence",
         test_a_free_leaf_is_compared_by_the_value_not_the_sentence),
        ("a_narrowing_never_truncates_the_value",
         test_a_narrowing_never_truncates_the_value),
        ("an_answer_hop_is_judged_on_its_own_region",
         test_an_answer_hop_is_judged_on_its_own_region),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("observe: PASS" if not failures else "observe: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
