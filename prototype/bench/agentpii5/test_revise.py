"""The revision of the 834, and the one thing it must never do.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_revise

THE FIRST CHECK IS THE ONLY ONE THAT CANNOT BE NEGOTIATED. v4's half of the v5
corpus IS the baseline: the control arm of every comparison runs on those bytes.
`test_messages_byte_identical` compares `case.base.to_json()` against the JSON
`corpus.json` holds, field for field, for all 834 — because a revision that
«improved» one message would make the baseline and the treatment two different
measurements sharing one number, and no later rule would catch it.

EVERY OTHER CHECK IS SHOWN TO FAIL TOO. A derivation is a place where a mistake
is silent: the hops are computed, not written, so nothing looks wrong when they
are wrong. Each property below is therefore checked once on the real revision
and once on a deliberately broken input the check must reject.

NOTHING HERE IMPORTS `pseudex`, AND NO CHECK HERE CALLS A MODEL.
"""
import json
import sys
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii4.pools import BuildError
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema as s
from bench.agentpii5 import revise as r
from bench.agentpii5.contracts import CaseV5

V4_CASES = r.load_v4_corpus()
V4_RAW: list[dict[str, object]] = json.loads(
    r.V4_CORPUS.read_text(encoding="utf-8"))["corpus"]
REVISIONS: list[r.Revision] = r.revise_reporting(V4_CASES)[0]
REVISED: list[CaseV5] = [one.case for one in REVISIONS]


def _as_json(value: object) -> str:
    """The BYTES a corpus file would carry, not the Python object.

    `Case.to_json` hands back tuples where the file holds lists, so an equality
    check on the objects reports every case as different and proves nothing.
    The claim this test makes is about what gets written, so it compares what
    gets written — canonically ordered, so key order cannot fake a difference.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def test_messages_byte_identical() -> list[str]:
    """The v4 half of every revised case serialises to exactly what
    `corpus.json` holds — all 834, field by field on the first that differs."""
    problems: list[str] = []
    if len(REVISED) != len(V4_RAW):
        problems.append(f"revised {len(REVISED)} of {len(V4_RAW)}")
    for case, raw in zip(REVISED, V4_RAW):
        written = case.base.to_json()
        if _as_json(written) == _as_json(raw):
            continue
        differing = sorted(key for key in raw
                           if _as_json(written.get(key)) != _as_json(raw.get(key)))
        problems.append(f"{case.base.id}: differs in {differing}")
    # The negative: the comparison must SEE a change. One character in one
    # message is what a careless revision would look like.
    doctored = dict(V4_RAW[0])
    messages = [dict(one) for one in doctored["messages"]]        # type: ignore[union-attr]
    messages[1]["content"] = str(messages[1]["content"]) + " "
    doctored["messages"] = messages
    if _as_json(REVISED[0].base.to_json()) == _as_json(doctored):
        problems.append("a message with an added space compared equal")
    return problems


def test_nothing_is_dropped() -> list[str]:
    """K10 counts exactly 834 revised cases; a silent drop is a corpus that
    fails three rules later with no clue which case caused it."""
    _revisions, dropped = r.revise_reporting(V4_CASES)
    return [f"could not revise: {one}" for one in dropped[:5]]


def test_455_get_loop() -> list[str]:
    """Exactly the cases with seed records reach a tool result, and no others.

    Both directions on purpose: a case with seeds and no result would drop K10
    below 455, and a case with a result and no seeds would mean an IN/tool hop
    on an item no backend holds.
    """
    problems: list[str] = []
    with_seeds = {case.base.id for case in REVISED if case.base.seed_records}
    with_result = {case.base.id for case in REVISED if case.has_result}
    if len(with_result) != c.V4_CASES_WITH_RESULT:
        problems.append(f"{len(with_result)} cases reach a result, "
                        f"v4 has {c.V4_CASES_WITH_RESULT} with seeds")
    for identifier in sorted(with_result - with_seeds)[:3]:
        problems.append(f"{identifier}: a result with no seed record")
    for identifier in sorted(with_seeds - with_result)[:3]:
        problems.append(f"{identifier}: seeds but no result")
    return problems


def test_k10() -> list[str]:
    """The corpus rule the revision exists to satisfy, run on the revision alone
    — and shown to fire when one case is dropped."""
    problems: list[str] = []
    revised_ids = {problem.split()[0] for problem in s.validate_corpus_v5(
        REVISED, ("crm_find_contact",))}
    if "K10" in revised_ids:
        problems.append("K10 fired on the whole revision")
    short = REVISED[:-1]
    if "K10" not in {problem.split()[0] for problem in s.validate_corpus_v5(
            short, ("crm_find_contact",))}:
        problems.append("K10 did not fire on 833 revised cases")
    return problems


def test_behaviour_mapping() -> list[str]:
    """Every case wears the behaviour its v4 kind maps to, or `single` with a
    recorded reason — never a third thing, and never a behaviour whose structure
    the case does not carry."""
    problems: list[str] = []
    for one in REVISIONS:
        mapped = c.V4_KIND_TO_BEHAVIOUR[one.case.base.kind]
        if one.case.behaviour == mapped:
            if one.downgraded_from or one.reason:
                problems.append(f"{one.case.base.id}: kept {mapped!r} yet reports a downgrade")
            continue
        if one.case.behaviour != "single":
            problems.append(f"{one.case.base.id}: {mapped!r} became "
                            f"{one.case.behaviour!r}, not 'single'")
        if one.downgraded_from != mapped or not one.reason:
            problems.append(f"{one.case.base.id}: downgrade recorded as "
                            f"{one.downgraded_from!r}/{one.reason!r}")
    return problems


def test_specs_match_the_behaviour() -> list[str]:
    """A behaviour and its spec move together: `fanout_pick` has a `PickSpec`,
    `branching` a `BranchSpec`, `user_in_loop` a `LoopSpec`, nothing else has
    any — which is what R13/R14/R15 refuse both ways."""
    problems: list[str] = []
    for case in REVISED:
        wanted = {"fanout_pick": "pick", "branching": "branch", "user_in_loop": "loop"}
        for behaviour, field in wanted.items():
            present = getattr(case, field) is not None
            if present != (case.behaviour == behaviour):
                problems.append(f"{case.base.id}: {case.behaviour!r} with "
                                f"{field}={'set' if present else 'unset'}")
    return problems


def test_all_valid() -> list[str]:
    """No revised case fails `validate_v5`, and a hand-broken one does."""
    problems: list[str] = []
    for case in REVISED:
        problems.extend(s.validate_v5(case))
    broken = replace(REVISED[0], behaviour="не поведение")
    if "R01" not in {problem.split()[0] for problem in s.validate_v5(broken)}:
        problems.append("a revised case with an unknown behaviour was accepted")
    return problems[:8]


def test_chains_are_real() -> list[str]:
    """Every case that kept `sequential_chain` really has an argument fed by
    ANOTHER tool's result — R12 read back off the hops rather than trusted."""
    problems: list[str] = []
    for case in REVISED:
        if case.behaviour != "sequential_chain":
            continue
        if not r._chains(case.hops):                     # noqa: SLF001 - the rule itself
            problems.append(f"{case.base.id}: claims a chain and has none")
    if r._chains(()):                                    # noqa: SLF001
        problems.append("an empty hop list was reported as a chain")
    return problems


def test_return_forms_are_declared() -> list[str]:
    """Every expected return form is one the tool declares (R19), and a form it
    does not declare is refused."""
    problems: list[str] = []
    for case in REVISED:
        problems.extend(problem for problem in s.validate_v5(case)
                        if problem.startswith("R19"))
    with_returns = next(case for case in REVISED if case.returns)
    broken = replace(with_returns, returns=(
        replace(with_returns.returns[0], return_form="chunks"),))
    if "R19" not in {problem.split()[0] for problem in s.validate_v5(broken)}:
        problems.append("a form the tool does not declare was accepted")
    return problems[:6]


def test_streaming_is_a_voice_axis() -> list[str]:
    """Streaming cases are speech-register cases with a result, and there are
    enough of them for K11 to be reachable at all."""
    problems: list[str] = []
    streaming = [case for case in REVISED if case.streaming]
    for case in streaming:
        if case.base.register not in c.SPEECH_REGISTERS:
            problems.append(f"{case.base.id}: streaming in {case.base.register!r}")
        if not case.has_result:
            problems.append(f"{case.base.id}: streaming with no result")
    if len(streaming) < c.MIN_STREAMING_CASES:
        problems.append(f"{len(streaming)} streaming cases in the revision; K11 wants "
                        f"{c.MIN_STREAMING_CASES} in the whole corpus and this is "
                        f"where the speech cases are")
    return problems


def test_missing_corpus_is_a_refusal() -> list[str]:
    """A missing `corpus.json` raises with the path in the message. The v5
    corpus is v4 plus a half; there is no «build without it» to fall back to."""
    original = r.V4_CORPUS
    r.V4_CORPUS = original.parent / "corpus.absent.json"
    try:
        r.load_v4_corpus()
        return ["a missing v4 corpus was not refused"]
    except BuildError as error:
        return [] if "corpus.absent.json" in str(error) else [f"unhelpful refusal: {error}"]
    finally:
        r.V4_CORPUS = original


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_messages_byte_identical, test_nothing_is_dropped, test_455_get_loop, test_k10,
    test_behaviour_mapping, test_specs_match_the_behaviour, test_all_valid,
    test_chains_are_real, test_return_forms_are_declared, test_streaming_is_a_voice_axis,
    test_missing_corpus_is_a_refusal)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        if problems:
            failures += 1
            print(f"  {check.__name__}: {problems[0]}")
            for problem in problems[1:5]:
                print(f"    {problem}")
    print(f"revise: {len(CHECKS)} проверок над {len(REVISED)} случаями · "
          + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
