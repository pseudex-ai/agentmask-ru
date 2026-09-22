"""`metrics.py` pinned: the registry, the denominators, and the controls it must ignore.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_metrics

The per-metric arithmetic is pinned by `fixtures.py` and run as a test by
`test_fixtures.py`; this file pins the promises that live BETWEEN metrics —
that every declared name has a function, that the public denominators are the
public ones, that a form line does not move when the v4 verdicts do, and that
an empty population prints «н/п» rather than 0%.
"""
import sys
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii3.schema import Negative
from bench.agentpii4.compare import LevelVerdict, PairVerdict
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import Hop, MentionRecord, RagSpec
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    OTHER_NAME,
    REAL_NAME,
    REAL_PHONE,
    _case,
    _hop,
    _in_message,
    _in_seed,
    _item,
    _obs,
    _result,
    _run,
    _seen,
    _with_masked,
    _with_mentions,
    _with_results,
    _with_subs,
)
from bench.agentpii5.metrics import METRIC_FUNCTIONS, by_axis

NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
PHONE = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 15, 27))


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_every_metric_registered() -> list[str]:
    """C-007. Every name the contracts declare, minus the six v4 paired levels
    (printed by v4's own report, not as a `Line`), has a function here."""
    want = set(contracts.METRIC_NAMES) - set(contracts.V4_LEVEL_NAMES)
    have = set(METRIC_FUNCTIONS)
    problems: list[str] = []
    if have - want:
        problems.append(f"metrics nobody declared: {sorted(have - want)}")
    if want - have:
        problems.append(f"declared metrics with no function: {sorted(want - have)}")
    for name in contracts.V4_LEVEL_NAMES:
        if name in have:
            problems.append(f"{name} is a v4 PAIRED level and must not be a v5 Line")
    return problems


def _form_case() -> tuple[object, object]:
    hop = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    case = _case("m-form", "single", (REAL_NAME,), (NAME,), (hop,))
    return case, hop


def test_form_lines_ignore_controls() -> list[str]:
    """C-017. The form check lives INSIDE arm I. v4 compared I with C and the
    comparison cancels form — two live models normalise a name the same way —
    so a form line that moved with `ic` would be v4's blind spot restored."""
    case, hop = _form_case()
    run = _run("m-form")
    blind = _obs(case, run, (_seen(case, hop, "NAME", "Орлову Ивану", "Орлов Иван"),))
    levels = LevelVerdict(tools=True, tools_sub="", keys=True, keys_sub="", state=True,
                          state_verbatim=True, state_diff=(), comparable=frozenset({"state"}))
    paired = replace(blind, ic=PairVerdict("IC", levels, (), ()),
                     cc=PairVerdict("CC", levels, (), ()))
    problems: list[str] = []
    for name in ("form_hIN", "form_hOUT", "chain_form", "answer_real"):
        left, right = METRIC_FUNCTIONS[name]((blind,)), METRIC_FUNCTIONS[name]((paired,))
        if (left.hits, left.total) != (right.hits, right.total):
            problems.append(f"{name} moved when the v4 verdicts were attached: "
                            f"{left.hits}/{left.total} vs {right.hits}/{right.total}")
    line = METRIC_FUNCTIONS["form_hIN"]((blind,))
    if (line.hits, line.total) != (0, 1):
        problems.append(f"the fixture cannot fail: form_hIN printed {line.hits}/{line.total}")
    return problems


def _chain(case_id: str, out_item: str, items: tuple[object, ...],
           produced: str) -> object:
    source = _hop("IN", "tool", "p1", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
    target = Hop(kind="OUT", owner="tool_arg", item_id=out_item, hop_index=1, turn=0,
                 tool_name="delivery_create_order", call_ordinal=0, parallel_group="",
                 source_hop=0, path="recipient.name", optional=False)
    case = _case(case_id, "sequential_chain", ("…",), items, (source, target))
    return _obs(case, _run(case_id), (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                                      _seen(case, target, "NAME", produced, FAKE_NAME)))


def test_chain_transitions() -> list[str]:
    """C-015. A transition is a declared OUT hop whose `source_hop` points at
    an IN/tool hop of ANOTHER tool. Same tool → no transition; no `source_hop`
    → no transition. The denominator is the case's declaration, so an agent
    that skipped the second call cannot shrink it."""
    other = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    kept = _chain("m-ch-1", "p1", (NAME,), REAL_NAME)
    problems: list[str] = []
    line = METRIC_FUNCTIONS["chain_value"]((kept,))
    if (line.hits, line.total) != (1, 1):
        problems.append(f"a kept value is 1/1, got {line.hits}/{line.total}")
    crossed = _chain("m-ch-2", "p9", (NAME, other), REAL_NAME)
    line = METRIC_FUNCTIONS["chain_value"]((crossed,))
    if (line.hits, line.total) != (0, 1):
        problems.append("a transition carrying another identity's hop must be a miss, "
                        f"got {line.hits}/{line.total}")
    same_tool = replace(kept.case, hops=(
        kept.case.hops[0], replace(kept.case.hops[1], tool_name="crm_find_contact")))
    folded = replace(kept, case=same_tool, hops=(
        kept.hops[0], replace(kept.hops[1], hop=replace(kept.hops[1].hop,
                                                        tool_name="crm_find_contact"))))
    line = METRIC_FUNCTIONS["chain_value"]((folded,))
    if line.total != 0:
        problems.append(f"a tool feeding its own result is not a chain, got total {line.total}")
    return problems


def test_rag_identity_kept() -> list[str]:
    """C-061. Two ways for a foreign identity to be mixed with the customer,
    and both must count: the stranger's real value in the customer's argument,
    and the customer's substitute standing where the stranger's value stood."""
    mine = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_seed("s1", "name"))
    theirs = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    out = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("m-rag", "rag", ("…",), (mine, theirs), (out,))
    case = replace(case, rag=RagSpec("kb_search", 2, ("s1", "s2"), ("i2",), ("p1",)))
    clean = _obs(case, _run("m-rag"), (_seen(case, out, "NAME", REAL_NAME, FAKE_NAME),))
    bled = _obs(case, _run("m-rag"), (_seen(case, out, "NAME", OTHER_NAME, FAKE_NAME),))
    text = f"Менеджер: {OTHER_NAME}."
    span = (10, 10 + len(OTHER_NAME))
    merged_run = _with_subs(_with_results(_run("m-rag"), (_result(
        "kb_search", 0, 0, "chunks", text, text, {"p9": span},
        ((span[0], span[1], FAKE_NAME, "NAME"),), False),)), {"p1": FAKE_NAME})
    merged = _obs(case, merged_run, (_seen(case, out, "NAME", REAL_NAME, FAKE_NAME),))
    problems: list[str] = []
    for label, one, want in (("clean", clean, 1), ("bled", bled, 0), ("merged", merged, 0)):
        line = METRIC_FUNCTIONS["rag_identity_kept"]((one,))
        if (line.hits, line.total) != (want, 1):
            problems.append(f"{label}: expected {want}/1, got {line.hits}/{line.total}")
    return problems


def test_public_denominators() -> list[str]:
    """C-168. One observation set, every public total asserted against the
    population `score.py` names — not against whatever the code happened to
    collect. A denominator nobody stated is a denominator that drifts."""
    in_user = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    in_tool = _hop("IN", "tool", "p2", 1, 0, "crm_find_contact", 0, -1, "contacts[].phone")
    out_name = _hop("OUT", "tool_arg", "p1", 2, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    out_phone = _hop("OUT", "tool_arg", "p2", 3, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    negative = Negative(value="TRK-1", start=40, end=45, msg=0, family="order_no", why="трек")
    case = _case("m-pub", "single", (f"{REAL_NAME}, {REAL_PHONE}, TRK-1",), (NAME, PHONE),
                 (in_user, in_tool, out_name, out_phone))
    case = replace(case, base=replace(case.base, negatives=(negative,)))
    span = (0, len(REAL_PHONE))
    run = _with_masked(_with_mentions(_with_results(_run("m-pub"), (_result(
        "crm_find_contact", 0, 0, "single", REAL_PHONE, "+79990001122", {"p2": span},
        ((span[0], span[1], "+79990001122", "PHONE"),), False),)),
        (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 2, -1, FAKE_NAME, 1))),
        {0: ((0, len(REAL_NAME)),)})
    one = _obs(case, run, (
        _seen(case, in_user, "NAME", FAKE_NAME, REAL_NAME),
        _seen(case, in_tool, "PHONE", "+79990001122", REAL_PHONE),
        _seen(case, out_name, "NAME", REAL_NAME, FAKE_NAME),
        _seen(case, out_phone, "PHONE", REAL_PHONE, "+79990001122")))
    want = {"leak": 2, "coverage": 2, "typed": 1, "round_trip": 1, "round_trip_repaired": 1,
            "end_to_end": 2, "overmask": 1, "consistency": 1, "stability": 1}
    problems: list[str] = []
    for name, total in want.items():
        got = METRIC_FUNCTIONS[name]((one,)).total
        if got != total:
            problems.append(f"{name}: denominator {got}, the public one is {total}")
    # `round_trip` is over items the gateway ALTERED and a tool consumes;
    # `end_to_end` over ALL of them. Folding the two is how a passthrough
    # scores 100% on a line meant to say the data was protected.
    if METRIC_FUNCTIONS["round_trip"]((one,)).total == METRIC_FUNCTIONS["end_to_end"]((one,)).total:
        problems.append("round_trip and end_to_end got the same denominator on a set built "
                        "so that exactly one item was altered")
    return problems


def test_empty_is_na() -> list[str]:
    """A metric with nothing to say prints `Line(name, 0, 0)` and the report
    prints «н/п». Returning 0/1 instead would say the gateway failed something
    it was never asked to do."""
    problems: list[str] = []
    for name, function in sorted(METRIC_FUNCTIONS.items()):
        line = function(())
        if (line.hits, line.total) != (0, 0):
            problems.append(f"{name} on no observations printed {line.hits}/{line.total}")
        if line.name != name:
            problems.append(f"{name} returned a Line named {line.name!r}")
        if line.rate != 0.0 or line.certified is not None:
            problems.append(f"{name}: an empty line must not certify anything")
    return problems


def test_axes_split_hops_not_observations() -> list[str]:
    """C-080. A hop-level axis splits the HOPS: `form_hOUT` by `pii_type` must
    count a NAME hop under NAME and nowhere else. Splitting the observations
    instead would put every hop of a mixed case into every bucket."""
    in_name = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    in_phone = _hop("IN", "user", "p2", 1, 0, "", -1, -1, "")
    case = _case("m-axis", "single", ("…",), (NAME, PHONE), (in_name, in_phone))
    one = _obs(case, _run("m-axis"), (_seen(case, in_name, "NAME", FAKE_NAME, REAL_NAME),
                                      _seen(case, in_phone, "PHONE", REAL_PHONE, REAL_PHONE)))
    buckets = by_axis((one,), "pii_type")
    problems: list[str] = []
    if sorted(buckets) != ["NAME", "PHONE"]:
        problems.append(f"pii_type buckets are {sorted(buckets)}")
    for bucket, rows in buckets.items():
        line = METRIC_FUNCTIONS["form_hIN"](rows)
        if line.total != 1:
            problems.append(f"{bucket}: {line.total} hops in a bucket that holds one")
    if sorted(by_axis((one,), "behaviour")) != ["single"]:
        problems.append("an observation-level axis must not split the hops")
    try:
        by_axis((one,), "не ось")
        problems.append("an unknown axis was accepted")
    except ValueError:
        pass
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("every_metric_registered", test_every_metric_registered),
        ("form_lines_ignore_controls", test_form_lines_ignore_controls),
        ("chain_transitions", test_chain_transitions),
        ("rag_identity_kept", test_rag_identity_kept),
        ("public_denominators", test_public_denominators),
        ("empty_is_na", test_empty_is_na),
        ("axes_split_hops_not_observations", test_axes_split_hops_not_observations),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("metrics: PASS" if not failures else "metrics: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
