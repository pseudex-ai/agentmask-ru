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
from bench.agentpii5.mock import render_problems
from bench.agentpii5.tools import expected_leaf_value, spec_v5_for

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


def test_every_declared_crossing_is_rendered() -> list[str]:
    """THE PROOF, over all 834: the backend really produces every IN/tool hop
    and every `result_item_ids` the revision declares.

    THE REPRODUCTION THIS PINS (corpus-lens, T1): driving the revised half
    against the real mock, 132 of the 455 cases claiming `has_result` had not
    one observable tool crossing, and 42% of the declared IN/tool hops were
    crossings the mock never renders — every one of them a permanent gateway
    miss and a free hit on `leak`.
    """
    problems: list[str] = []
    for case in REVISED:
        problems.extend(render_problems(case))
    return problems[:8]


def test_a_declared_transition_is_attainable() -> list[str]:
    """R12's link is declared only when the source result PRINTED the value the
    argument leaf will hold.

    THE REPRODUCTION THIS PINS (corpus-lens/chain.py + roles.py): of 5 441
    transitions in the revised half only 520 were attainable with the gateway
    removed entirely and 1 240 were actively contradicted — the street item's
    IN span reads «толстого» while `contact.address.city` holds «омск», the
    surname item's reads «букин» while `contact.first_name` holds «сергей».
    """
    problems: list[str] = []
    contradicted = 0
    for case in REVISED:
        items = {item.id: item for item in case.base.pii}
        for hop in case.hops:
            if hop.kind != "OUT" or hop.source_hop == -1 or not hop.path:
                continue
            source = case.hops[hop.source_hop]
            if source.kind != "IN" or source.owner != "tool":
                continue
            spec = spec_v5_for(hop.tool_name, hop.path)
            if spec is None or not expected_leaf_value(items[hop.item_id], spec):
                contradicted += 1
    if contradicted:
        problems.append(f"{contradicted} declared transitions carry a leaf the item "
                        f"has no part for")
    # THE NEGATIVE: the rule itself, shown refusing. A surname item cannot be
    # the value of `contact.first_name`, whatever its type says.
    surname = next((item for case in REVISED for item in case.base.pii
                    if item.type == "NAME" and set(item.parts) <= {"surname", "gender"}), None)
    if surname is None:
        problems.append("no surname-only item in the revision to test the rule with")
    else:
        given = spec_v5_for("crm_upsert_contact", "contact.first_name")
        if given is None:
            problems.append("crm_upsert_contact has no contact.first_name leaf")
        elif expected_leaf_value(surname, given):
            problems.append(f"a surname item was accepted for a given-name leaf: "
                            f"{expected_leaf_value(surname, given)!r}")
    return problems


def test_a_write_takes_the_value_the_customer_stated() -> list[str]:
    """R-49: the argument of a MUTATING call is what the customer just said, not
    what the earlier lookup returned.

    THE REPRODUCTION THIS PINS. «запишите новый телефон …» puts the value of the
    MESSAGE into `crm_upsert_contact.contact.phone`, while the lookup that found
    the card returned the OLD one; declaring the update as fed by that result
    claims a hand-over the dialogue contradicts, and no arm can satisfy both — an
    agent that does what the customer asked misses `chain_value` on every such
    hop, and one that satisfies it has written the stale value back into the
    customer's record. 85 revised cases lost their only transition this way and
    left `sequential_chain` honestly.
    """
    problems: list[str] = []
    for case in REVISED:
        items = {item.id: item for item in case.base.pii}
        for hop in case.hops:
            if hop.kind != "OUT" or not hop.tool_name or not r._is_mutating(hop.tool_name):
                continue                                 # noqa: SLF001 - the rule itself
            item = items[hop.item_id]
            if item.where.kind == "message":
                continue
            spec = spec_v5_for(hop.tool_name, hop.path)
            if spec is None:
                continue
            said = [one for one in case.base.pii if one.where.kind == "message"
                    and one.type == item.type and one.identity == item.identity
                    and expected_leaf_value(one, spec)]
            if said:
                problems.append(f"{case.base.id}: hop {hop.hop_index} writes a result into "
                                f"{hop.tool_name}.{hop.path} while the customer stated "
                                f"{said[0].id} for it")
    # THE NEGATIVE: the same candidates and the same leaf type, once for a tool
    # that WRITES and once for one that READS. The rule is the only thing that
    # can make the two answers differ — without it both are the chained item,
    # which is exactly the state this check exists to refuse.
    probe = _both_ways("crm_upsert_contact", "contact.phone", "bank_client_find", "phone")
    if probe is None:
        problems.append("no revised case offers a phone both said and read back; the "
                        "negative for R-49 was not exercised")
    else:
        write_item, read_item = probe
        if write_item.where.kind != "message":
            problems.append(f"a MUTATING leaf took {write_item.where.kind!r}, not what "
                            f"the customer said")
        if read_item.where.kind != "seed":
            problems.append(f"a READ leaf took {read_item.where.kind!r}; the chain "
                            f"preference is gone from the read path too")
    return problems[:6]


def _both_ways(write_tool: str, write_leaf: str, read_tool: str,
               read_leaf: str) -> tuple[object, object] | None:
    """The item a write leaf and a read leaf take on the FIRST v4 case that
    offers both a said and a read-back value for them."""
    for case in V4_CASES:
        reads = r._readers(case)                         # noqa: SLF001 - the rule itself
        read_by = {item.id: tool for tool, pairs in reads.items() for item, _leaf in pairs}
        hopped = r._hopped_ids(case, reads)              # noqa: SLF001
        write_spec = spec_v5_for(write_tool, write_leaf)
        read_spec = spec_v5_for(read_tool, read_leaf)
        if write_spec is None or read_spec is None:
            return None
        candidates = r._candidates(case, write_spec, hopped,       # noqa: SLF001
                                   case.expects.primary_identity)
        if not (r._chained_of(candidates, read_by, write_tool)     # noqa: SLF001
                and r._said_of(candidates)):                       # noqa: SLF001
            continue
        chosen_write = r._argument_item(case, write_spec, hopped, read_by,   # noqa: SLF001
                                        write_tool)
        chosen_read = r._argument_item(case, read_spec, hopped, read_by,     # noqa: SLF001
                                       read_tool)
        if chosen_write is None or chosen_read is None:
            continue
        return chosen_write, chosen_read
    return None


def test_the_loop_family_declares_its_memory() -> list[str]:
    """`user_in_loop` shows a value and the customer confirms it without saying
    it again — a recall by anaphora, and the family declared none (C-048), so
    `memory_consistency` had an empty population in the one family whose whole
    shape is a value held across two turns."""
    problems: list[str] = []
    loops = [case for case in REVISED if case.behaviour == "user_in_loop"]
    if not loops:
        return ["the revision has no user_in_loop case"]
    without = [case.base.id for case in loops if not case.memory]
    if without:
        problems.append(f"{len(without)} loop cases declare no MemorySpec: {without[:3]}")
    for case in loops[:20]:
        assert case.loop is not None
        for spec in case.memory:
            if spec.first_turn != case.loop.show_turn:
                problems.append(f"{case.base.id}: recall starts at {spec.first_turn}, "
                                f"the value is shown at {case.loop.show_turn}")
            if spec.recall_turn != case.loop.confirm_turn:
                problems.append(f"{case.base.id}: recall at {spec.recall_turn}, the "
                                f"confirmation is at {case.loop.confirm_turn}")
            if spec.anaphora == "none":
                problems.append(f"{case.base.id}: a confirmation that repeats the value "
                                f"is not the loop this family measures")
    # THE NEGATIVE: no other revised family invents one.
    stray = [case.base.id for case in REVISED
             if case.memory and case.behaviour != "user_in_loop"]
    if stray:
        problems.append(f"memory declared outside the loop family: {stray[:3]}")
    return problems[:6]


def test_singles_that_reach_a_result_carry_the_minimal_loop() -> list[str]:
    """§8.2's «одиночный вызов: базовый, 4 перехода» (C-041, C-137), over the
    singles that actually reach one — and the count of the two-hop v4 shapes
    beside it, because 418 in one number read as 418 of the base shape."""
    problems: list[str] = []
    singles = [case for case in REVISED if case.behaviour == "single"]
    looped = [case for case in singles if case.has_result]
    if not looped:
        return ["no single case reaches a tool result"]
    for case in looped:
        pairs = {(hop.kind, hop.owner) for hop in case.hops}
        missing = [pair for pair in c.MINIMAL_LOOP if pair not in pairs]
        if missing:
            problems.append(f"{case.base.id}: reaches a result without {missing}")
    # THE NEGATIVE: the check sees a loop with a leg cut out.
    stripped = replace(looped[0], hops=tuple(
        hop for hop in looped[0].hops if not (hop.kind == "OUT" and hop.owner == "answer")))
    if all(pair in {(hop.kind, hop.owner) for hop in stripped.hops}
           for pair in c.MINIMAL_LOOP):
        problems.append("a loop with no answer hop still read as minimal")
    return problems[:6]


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_every_declared_crossing_is_rendered, test_a_declared_transition_is_attainable,
    test_a_write_takes_the_value_the_customer_stated,
    test_the_loop_family_declares_its_memory,
    test_singles_that_reach_a_result_carry_the_minimal_loop,
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
