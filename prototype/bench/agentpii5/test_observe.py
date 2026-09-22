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
from bench.agentpii5.contracts import Hop
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
    answer_spans,
    carried_substitute,
    carries_any,
    observe,
    turn_request,
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
    if got.status != "unmasked" or got.verdict is not None:
        problems.append(f"a leaf with no substitute in it must be `unmasked`, got {got.status}")
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


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("in_orientation", test_in_orientation),
        ("out_orientation", test_out_orientation),
        ("template_owner", test_template_owner),
        ("answer_alignment", test_answer_alignment),
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
