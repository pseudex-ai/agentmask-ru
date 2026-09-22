"""`observe.py` pinned: orientation, ownership, alignment, and the four statuses.

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
    _with_mentions,
    _with_replies,
    _with_results,
    _with_subs,
)
from bench.agentpii5.observe import ObserveError, answer_spans, observe

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
    run = _with_calls(_run("obs-out"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": "Пахомовой"}},
        {"contact": {"last_name": "Ивановой"}}, {}, "", 0),), (0,))
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
    """A substitute the engine reported as surviving in a tool leaf is
    `residual` and carries NO verdict: there is no form question about a value
    that never became real."""
    hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("obs-res", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_calls(_run("obs-res"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": FAKE_NAME}},
        {"contact": {"last_name": FAKE_NAME}}, {"contact.last_name": (FAKE_NAME,)}, "", 0),), (0,))
    got = _one(case, run).hops[0]
    clean = _with_calls(_run("obs-res"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": FAKE_NAME}},
        {"contact": {"last_name": REAL_NAME}}, {"contact.last_name": ()}, "", 0),), (0,))
    problems: list[str] = []
    if got.status != "residual" or got.verdict is not None:
        problems.append(f"a surviving substitute must be residual without a verdict, got {got.status}")
    if _one(case, clean).hops[0].status != "observed":
        problems.append("an EMPTY residual tuple is not a residual; the leaf was clean")
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
        ("leaked_in_partial_cover", test_leaked_in_partial_cover),
        ("optional_absent_not_emitted", test_optional_absent_not_emitted),
        ("extra_hop_undeclared", test_extra_hop_undeclared),
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
