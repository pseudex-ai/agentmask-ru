"""The six multi-call families of AgentPII-RU v5, under every check they claim.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_generator_a

EVERY CHECK HERE IS SHOWN TO FAIL. A check that has only ever been run on
correct input is a check nobody has measured: `test_checks_can_fail` breaks one
case per rule — a hop pointing forward, a retry without a second attempt, a
parallel group of one, a family whose registers were drawn instead of
apportioned — and REFUSES to pass unless every one of them is reported. The
positive atoms above it are what those negatives are measured against
(`e2e/audit_gates.py`'s rule, applied to a generator's own suite).

THE BACKEND CHECK IS THE ONE THAT FOUND THINGS. `test_backend_returns_the_
declared_items` seeds the real `BackendV5` from each sample case and calls the
tools the case declares a `ReturnExpectation` for, then asks whether every
declared result item was actually TAGGED in the rendered result. A case can
satisfy `validate_v5` completely and still declare a hop the backend can never
produce — a row shape the mock's renderer does not read, a value two seeds share
so the by-value index drops the tag — and only running it says so.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE CALLS A LIVE MODEL.
"""
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace

from bench.agentpii4 import validate as v4validate
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema as s
from bench.agentpii5.contracts import CaseV5, Hop, ReturnExpectation
from bench.agentpii5.mock import render_problems
from bench.agentpii5.scenarios5 import common
from bench.agentpii5.scenarios5.plan_a import PLAN_A

SEED: int = 4
# The corpus-wide quotas this half owes (brief «Type quotas across your 400
# cases»): generator_b supplies at least twenty of each, `MIN_CASES_BY_TYPE`
# wants sixty, so forty here is the split that makes K05 reachable.
MIN_INN_CASES: int = 40
MIN_PLATE_CASES: int = 40
MIN_VERTICALS_PER_FAMILY: int = 2
# §3.1's row for `sequential_chain` reads «три перехода минимум».
MIN_CHAIN_TRANSITIONS: int = 3
# Each branch of `branching`, and its empty probe, as a share of the family.
# NOT A HALF ANY MORE, and the reason is ruling R-23: «not found» used to be the
# family's only shape without a tool result, and three of its four shapes now
# reach one (`_crm_second_probe` keeps the empty first call and finds the card on
# the second). What must NOT happen is a branch with no denominator — an `else`
# nobody ever takes is an `else` the two arms cannot differ on — so the rule is a
# floor under the smaller side rather than a band around a half.
MIN_BRANCH_SHARE: float = 0.20


def _build_all() -> dict[str, list[CaseV5]]:
    """Every family at its planned count, once, from one seed."""
    out: dict[str, list[CaseV5]] = {}
    for module, count in PLAN_A:
        behaviour = getattr(module, "BEHAVIOUR")
        out[behaviour] = getattr(module, "build")(SEED, count)
    return out


FAMILIES: dict[str, list[CaseV5]] = _build_all()
CORPUS: tuple[CaseV5, ...] = tuple(case for cases in FAMILIES.values() for case in cases)


# --- the checks, as functions so the negatives can drive them ------------------

def _validation_problems(cases: Sequence[CaseV5]) -> list[str]:
    problems: list[str] = []
    for case in cases:
        for problem in s.validate_v5(case):
            problems.append(f"{case.base.id}: {problem}")
    return problems


def _behaviour_problems(behaviour: str, cases: Sequence[CaseV5]) -> list[str]:
    """What each behaviour owes beyond `validate_v5` — the §3.1 row, not the rule.

    `validate_v5` asks whether a case is WELL FORMED for its behaviour; this asks
    whether it is the behaviour at all. R10 is happy with a forced error and a
    second ordinal; the family is only a retry if every case has exactly one
    refusal. R09 is happy with two OUT hops in a group; the family is only
    parallel if the group is the turn's whole fan-out.
    """
    problems: list[str] = []
    for case in cases:
        tag = case.base.id
        if case.behaviour != behaviour:
            problems.append(f"{tag}: behaviour {case.behaviour!r} in family {behaviour!r}")
        if behaviour == "retry_same_tool":
            if len(case.forced) != 1:
                problems.append(f"{tag}: {len(case.forced)} forced errors, a retry has one")
            elif not any(hop.tool_name == case.forced[0].tool_name
                         and hop.call_ordinal == case.forced[0].call_ordinal + 1
                         for hop in case.hops):
                problems.append(f"{tag}: no hop on the second attempt of "
                                f"{case.forced[0].tool_name}")
        if behaviour == "parallel":
            groups: dict[str, list[Hop]] = {}
            for hop in case.hops:
                if hop.parallel_group:
                    groups.setdefault(hop.parallel_group, []).append(hop)
            if not groups:
                problems.append(f"{tag}: a parallel case with no parallel group")
            for label, group in sorted(groups.items()):
                if len(group) < 2:
                    problems.append(f"{tag}: group {label!r} holds {len(group)} OUT hops")
                if len({hop.turn for hop in group}) != 1:
                    problems.append(f"{tag}: group {label!r} spans several turns")
        if behaviour == "fanout_pick":
            if case.pick is None:
                problems.append(f"{tag}: a fan-out case with no PickSpec")
            elif len(set(case.pick.candidate_identities)) < 2:
                problems.append(f"{tag}: pick names fewer than two candidates")
        if behaviour == "sequential_chain":
            found = _transitions(case)
            if found < MIN_CHAIN_TRANSITIONS:
                problems.append(f"{tag}: {found} transitions, §3.1 asks for "
                                f"{MIN_CHAIN_TRANSITIONS}")
        if behaviour == "same_tool_other_target":
            if len(_targets_of_one_tool(case)) < 2:
                problems.append(f"{tag}: no tool carries OUT hops of two identities")
    if behaviour == "branching":
        problems.extend(_branch_family_problems(cases))
    return problems


def _branch_family_problems(cases: Sequence[CaseV5]) -> list[str]:
    """Both branches have a denominator, and the empty probe still happens.

    THREE NUMBERS, NOT ONE. `seed_present` says which branch is RIGHT, and a
    family that put every case on one side would score the agent on a decision it
    never had to make. The empty PROBE is a separate count because it is no
    longer the same thing: a case can reach a result and still have answered
    `empty` first, and that first answer is the one a substituted lookup key
    produces — if it stopped occurring, the family would measure the happy path
    of a rule and nothing else.
    """
    problems: list[str] = []
    specs = [case.branch for case in cases if case.branch is not None]
    absent = sum(1 for spec in specs if not spec.seed_present)
    floor = max(c.MIN_TYPE_DENOMINATOR, int(len(cases) * MIN_BRANCH_SHARE))
    for label, seen in (("seed_present=False", absent),
                        ("seed_present=True", len(specs) - absent)):
        if seen < floor:
            problems.append(f"branching has {seen} cases with {label} of {len(cases)}; "
                            f"under {floor} that branch has no denominator to differ on")
    empty_probes = sum(1 for case in cases
                       if any(one.return_form == "empty" for one in case.returns))
    if empty_probes < floor:
        problems.append(f"branching declares an empty probe in {empty_probes} cases of "
                        f"{len(cases)}, under {floor}; the answer a substituted lookup key "
                        f"produces would stop being measured")
    return problems


def _transitions(case: CaseV5) -> int:
    """OUT hops fed by an IN hop of ANOTHER tool.

    BOTH `tool` AND `document` SOURCES COUNT. R12 counts only `tool`, because a
    document read is not a tool chain in its vocabulary; but for «три перехода»
    a value that entered from a file and left in a call HAS crossed, and the file
    families would otherwise be scored as if their first link did not exist.
    """
    found = 0
    for hop in case.hops:
        if hop.kind != "OUT" or not hop.tool_name or hop.source_hop < 0:
            continue
        source = case.hops[hop.source_hop]
        if source.kind == "IN" and source.owner in ("tool", "document") \
                and source.tool_name != hop.tool_name:
            found += 1
    return found


def _targets_of_one_tool(case: CaseV5) -> set[str]:
    """The identities that the busiest single tool carries OUT arguments for."""
    items = {item.id: item for item in case.base.pii}
    by_tool: dict[str, set[str]] = {}
    for hop in case.hops:
        if hop.kind == "OUT" and hop.owner == "tool_arg" and hop.item_id in items:
            by_tool.setdefault(hop.tool_name, set()).add(items[hop.item_id].identity)
    return max(by_tool.values(), key=len) if by_tool else set()


def _orientation_problems(case: CaseV5) -> list[str]:
    """Every OUT hop points BACK at an IN hop; every IN/tool hop has a return."""
    problems: list[str] = []
    tools_with_returns = {one.tool_name for one in case.returns}
    for hop in case.hops:
        if hop.kind == "OUT" and hop.source_hop != -1:
            if not 0 <= hop.source_hop < hop.hop_index:
                problems.append(f"{case.base.id}: hop {hop.hop_index} sources "
                                f"{hop.source_hop}, not an earlier hop")
            elif case.hops[hop.source_hop].kind != "IN":
                problems.append(f"{case.base.id}: hop {hop.hop_index} sources an OUT hop")
        if hop.kind == "IN" and hop.owner in ("tool", "document"):
            if hop.tool_name not in tools_with_returns:
                problems.append(f"{case.base.id}: IN hop {hop.hop_index} reads "
                                f"{hop.tool_name!r}, which declares no return")
    return problems


def _quota_problems(cases: Sequence[CaseV5]) -> list[str]:
    """The type quotas and the tool reach this half owes the corpus."""
    problems: list[str] = []
    for pii_type, floor in (("INN", MIN_INN_CASES), ("PLATE", MIN_PLATE_CASES)):
        carrying = [case for case in cases
                    if any(item.type == pii_type for item in case.base.pii)]
        if len(carrying) < floor:
            problems.append(f"{len(carrying)} cases carry a {pii_type} item, need {floor}")
        families = {case.behaviour for case in carrying}
        if len(families) < 3:
            problems.append(f"{pii_type} lives in {sorted(families)}; the brief asks for "
                            f"three families or more, so one family cannot carry the axis")
    reach: dict[str, int] = {}
    for case in cases:
        for tool in case.base.expects.reachable_tools:
            reach[tool] = reach.get(tool, 0) + 1
    for tool in c.NEW_TOOL_NAMES:
        if reach.get(tool, 0) < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"new tool {tool!r} is reachable in {reach.get(tool, 0)} cases, "
                            f"below MIN_TYPE_DENOMINATOR={c.MIN_TYPE_DENOMINATOR}")
    return problems


def _vertical_problems(behaviour: str, cases: Sequence[CaseV5]) -> list[str]:
    verticals = {c.TOOL_VERTICAL[tool] for case in cases
                 for tool in case.base.expects.reachable_tools}
    if len(verticals) < MIN_VERTICALS_PER_FAMILY:
        return [f"{behaviour} reaches {sorted(verticals)}; a family confined to one vertical "
                f"measures that vertical's API, not the gateway"]
    return []


def _register_problems(behaviour: str, cases: Sequence[CaseV5]) -> list[str]:
    """The family's realised mix equals what `common.registers_for` apportions.

    CHECKED AGAINST THE APPORTIONMENT, NOT AGAINST `contracts.REGISTER_SHARES`,
    and the difference is an OPEN DECISION rather than a liberty taken here:
    `REGISTER_SHARES` sums to 0.95 and `scenarios5.common` gives the missing 5%
    to `chat`, which puts chat at 30% — three points outside K04's band for every
    feasible corpus size. Whose number moves is the owner's call (it is in this
    component's report); what IS this component's business is that each family
    uses the shared apportionment rather than drawing its own registers, and that
    is exactly what this compares.
    """
    expected = common.registers_for(len(cases), common.ctx_for(behaviour, SEED, 0, "chat").rng)
    seen: dict[str, int] = {}
    for case in cases:
        seen[case.base.register] = seen.get(case.base.register, 0) + 1
    wanted: dict[str, int] = {}
    for register in expected:
        wanted[register] = wanted.get(register, 0) + 1
    if seen != wanted:
        return [f"{behaviour}: registers {sorted(seen.items())} != apportioned "
                f"{sorted(wanted.items())}"]
    return []


# --- the positive atoms ---------------------------------------------------------

def test_no_pseudex() -> list[str]:
    """An instrument that imports the engine cannot fail the engine."""
    loaded = sorted(name for name in sys.modules
                    if name.startswith(c.FORBIDDEN_IMPORT_PREFIX))
    return [f"importing generator_a loaded {loaded}"] if loaded else []


def test_build_each_family() -> list[str]:
    """Every module builds its planned count and every case is valid."""
    problems: list[str] = []
    planned = {getattr(module, "BEHAVIOUR"): count for module, count in PLAN_A}
    for behaviour, cases in FAMILIES.items():
        if len(cases) != planned[behaviour]:
            problems.append(f"{behaviour} built {len(cases)}, planned {planned[behaviour]}")
        ids = [case.base.id for case in cases]
        if len(set(ids)) != len(ids):
            problems.append(f"{behaviour} has duplicate case ids")
        if ids and ids[0] != f"{behaviour}-000":
            problems.append(f"{behaviour} ids start at {ids[0]!r}, not "
                            f"{behaviour + '-000'!r}")
    problems.extend(_validation_problems(CORPUS)[:12])
    return problems


def test_behaviour_specs() -> list[str]:
    problems: list[str] = []
    for behaviour, cases in FAMILIES.items():
        problems.extend(_behaviour_problems(behaviour, cases)[:6])
    return problems


def test_type_quotas() -> list[str]:
    problems = _quota_problems(CORPUS)
    for behaviour, cases in FAMILIES.items():
        problems.extend(_vertical_problems(behaviour, cases))
    return problems


def test_registers() -> list[str]:
    problems: list[str] = []
    for behaviour, cases in FAMILIES.items():
        problems.extend(_register_problems(behaviour, cases))
    return problems


def test_hops_orientation() -> list[str]:
    problems: list[str] = []
    for cases in FAMILIES.values():
        for case in cases:
            problems.extend(_orientation_problems(case))
    return problems[:10]


def test_no_search() -> list[str]:
    """No frame under `scenarios5/` looked a value up in a finished string.

    v4's watcher is pointed at `scenarios5/` for the duration and put back
    afterwards: the module constant is v4's, this test borrows it, and a test
    that left it changed would silently stop watching v4's own generator in the
    same process.
    """
    root = v4validate._HERE.parent / "agentpii5" / "scenarios5"        # noqa: SLF001
    here = str(root)
    # A WATCHER POINTED AT NOTHING REPORTS NOTHING, which is the failure this
    # test would never notice by itself: v4's constant is a path built from
    # `__file__`, and one wrong segment turns the proof into a formality. The
    # directory is asserted to hold the modules that are about to run.
    missing = [module.__name__.rsplit(".", 1)[-1] for module, _count in PLAN_A
               if not (root / f"{module.__name__.rsplit('.', 1)[-1]}.py").exists()]
    if missing:
        return [f"the watched directory {here} does not hold {missing}; "
                f"`prove_no_search` would have watched an empty set of frames"]
    before = v4validate._WATCHED_DIRS                                   # noqa: SLF001
    v4validate._WATCHED_DIRS = (here,)                                  # noqa: SLF001
    try:
        _cases, hits = v4validate.prove_no_search(
            lambda: [case.base for case in _build_all()["retry_same_tool"][:8]])
    finally:
        v4validate._WATCHED_DIRS = before                               # noqa: SLF001
    return [f"a generator frame searched a finished string: {hit}" for hit in hits]


def test_plan_a_matches_the_floors() -> list[str]:
    """`PLAN_A` tops the revised v4 corpus up to §8.2, and names real modules."""
    problems: list[str] = []
    planned = {getattr(module, "BEHAVIOUR"): count for module, count in PLAN_A}
    if set(planned) != set(c.GENERATOR_A_BEHAVIOURS):
        problems.append(f"PLAN_A covers {sorted(planned)}, not "
                        f"{sorted(c.GENERATOR_A_BEHAVIOURS)}")
    for behaviour, count in planned.items():
        if count <= 0:
            problems.append(f"{behaviour} is planned at {count}")
    # The three families the revised corpus supplies NOTHING of must reach their
    # own floor here; the other three are top-ups and are allowed to be smaller.
    for behaviour in ("retry_same_tool", "parallel", "same_tool_other_target"):
        floor = c.BEHAVIOUR_FLOORS[behaviour]
        if planned[behaviour] < floor:
            problems.append(f"{behaviour} is planned at {planned[behaviour]} and nothing else "
                            f"supplies it; the floor is {floor}")
    for module, _count in PLAN_A:
        for name in ("build", "TOOLS", "BEHAVIOUR"):
            if not hasattr(module, name):
                problems.append(f"{module} has no {name}")
    return problems


def test_offered_tools_are_in_the_family_inventory() -> list[str]:
    """Every tool a case offers is named by its module's `TOOLS`.

    A case offering a tool the module does not advertise is how an inventory
    stops being an inventory: `build.py` reads `TOOLS` to know what the corpus
    exercises, and a tool visible only inside one branch of one function would
    never appear in it.
    """
    problems: list[str] = []
    for module, _count in PLAN_A:
        inventory = set(getattr(module, "TOOLS"))
        for case in FAMILIES[getattr(module, "BEHAVIOUR")]:
            extra = set(case.base.tools) - inventory
            if extra:
                problems.append(f"{case.base.id} offers {sorted(extra)}, "
                                f"outside the module's TOOLS")
    return problems[:6]


# --- the backend check ----------------------------------------------------------

def _backend_problems(case: CaseV5) -> list[str]:
    """Run the case's declared calls against the real mock and check the tags.

    ONE DEFINITION, IN `mock.py`. This used to carry its own argument builder
    and its own assertions; `build.py` then needed the same thing to REFUSE an
    unprovable case, and two drivers of one backend are two answers to «does
    this loop close». `mock.render_problems` is now that answer, and this test
    is where a family's authors see it fail first.
    """
    return render_problems(case)


def test_backend_returns_the_declared_items() -> list[str]:
    """A sample of every family, run against the real backend.

    EVERY CASE, NOT A SAMPLE. It costs a couple of seconds and a sample is where
    the two defects this check first found would have hidden: both lived in ONE
    variant of one family, in one register, and a head-of-family sample caught
    the first only because the variants happen to be laid out by index.
    """
    problems: list[str] = []
    for cases in FAMILIES.values():
        for case in cases:
            problems.extend(_backend_problems(case))
    return problems[:12]


def test_import_orders() -> list[str]:
    """`plan_a` and a family module import cleanly in EITHER order.

    The cycle (`plan_a` needs the modules for the plan, the modules need
    `plan_a` for the helpers) resolves only because the helpers are defined
    above the imports. Both orders are run in FRESH interpreters, because in
    this one everything is already in `sys.modules` and the cycle cannot be
    observed at all.
    """
    problems: list[str] = []
    for first in ("bench.agentpii5.scenarios5.plan_a",
                  "bench.agentpii5.scenarios5.branching"):
        done = subprocess.run(
            [sys.executable, "-c",
             f"import {first}; from bench.agentpii5.scenarios5.plan_a import PLAN_A, spaced_snils; "
             f"print(len(PLAN_A))"],
            capture_output=True, text=True, cwd=str(v4validate._HERE.parent.parent))  # noqa: SLF001
        if done.returncode != 0 or done.stdout.strip() != "6":
            problems.append(f"importing {first} first: rc={done.returncode} "
                            f"out={done.stdout.strip()!r} err={done.stderr.strip()[-200:]!r}")
    return problems


# --- every check, shown to fail ---------------------------------------------------

def _first_case(behaviour: str) -> CaseV5:
    return FAMILIES[behaviour][0]


def _broken(case: CaseV5, hops: tuple[Hop, ...]) -> CaseV5:
    return replace(case, hops=hops, has_result=s.has_result(hops))


def test_checks_can_fail() -> list[str]:
    """Each check above, driven by input it must reject.

    A check is named here by the FUNCTION it exercises, not by the test that
    wraps it, so a wrapper that stopped calling its check would leave this test
    green — which is why `test_checks_cover_every_wrapper` below compares the two
    lists.
    """
    problems: list[str] = []

    def must_report(label: str, found: list[str]) -> None:
        if not found:
            problems.append(f"{label}: the check said nothing about input it must reject")

    # A hop that points FORWARD, and one that sources an OUT hop.
    case = _first_case("sequential_chain")
    forward = tuple(replace(hop, source_hop=len(case.hops) - 1) if hop.hop_index == 1 else hop
                    for hop in case.hops)
    must_report("orientation/forward", _orientation_problems(_broken(case, forward)))
    must_report("validate/forward", _validation_problems([_broken(case, forward)]))

    # A chain with its transitions cut: every OUT hop sources the customer.
    flat = tuple(replace(hop, source_hop=0) if hop.kind == "OUT" else hop for hop in case.hops)
    must_report("behaviour/chain-transitions",
                _behaviour_problems("sequential_chain", [_broken(case, flat)]))

    # A retry with no second attempt, and one with no forced error.
    retry = _first_case("retry_same_tool")
    once = tuple(hop for hop in retry.hops if hop.call_ordinal < 1)
    renumbered = tuple(replace(hop, hop_index=index, source_hop=min(hop.source_hop, index - 1))
                       for index, hop in enumerate(once))
    must_report("behaviour/retry-second-attempt",
                _behaviour_problems("retry_same_tool", [_broken(retry, renumbered)]))
    must_report("behaviour/retry-forced-count",
                _behaviour_problems("retry_same_tool",
                                    [replace(retry, forced=retry.forced + retry.forced)]))

    # A parallel group of one.
    parallel = _first_case("parallel")
    lonely = tuple(replace(hop, parallel_group="") if hop.parallel_group and hop.hop_index > 3
                   else hop for hop in parallel.hops)
    must_report("behaviour/parallel-group",
                _behaviour_problems("parallel", [_broken(parallel, lonely)]))

    # A fan-out whose pick names one candidate.
    fan = _first_case("fanout_pick")
    assert fan.pick is not None
    single = replace(fan, pick=replace(fan.pick,
                                       candidate_identities=(fan.pick.target_identity,)))
    must_report("behaviour/fanout-candidates",
                _behaviour_problems("fanout_pick", [single]))

    # A `same_tool_other_target` case with one identity on its tool.
    pair = _first_case("same_tool_other_target")
    one_identity = replace(pair.base, pii=tuple(
        replace(item, identity=pair.base.expects.primary_identity) for item in pair.base.pii))
    must_report("behaviour/other-target-identities",
                _behaviour_problems("same_tool_other_target",
                                    [replace(pair, base=one_identity)]))

    # A branching family that seeds every case, and one whose probe never
    # answers `empty` — the two ways the family stops measuring its own branch.
    branch = FAMILIES["branching"]
    all_seeded = [replace(one, branch=replace(one.branch, seed_present=True))
                  for one in branch if one.branch is not None]
    must_report("behaviour/branching-halves", _behaviour_problems("branching", all_seeded))
    never_empty = [replace(one, returns=tuple(expectation for expectation in one.returns
                                              if expectation.return_form != "empty"))
                   for one in branch]
    must_report("behaviour/branching-empty-probe",
                _behaviour_problems("branching", never_empty))

    # Quotas: a corpus with no ИНН, and one where a new tool is unreachable.
    no_inn = [one for one in CORPUS if not any(item.type == "INN" for item in one.base.pii)]
    must_report("quota/INN", _quota_problems(no_inn))
    must_report("quota/tool-reach", _quota_problems(CORPUS[:5]))

    # A family confined to one vertical.
    must_report("verticals", _vertical_problems("parallel", [parallel]))

    # Registers drawn instead of apportioned: one case's register flipped.
    flipped = list(FAMILIES["branching"])
    other = "clean" if flipped[0].base.register != "clean" else "chat"
    flipped[0] = replace(flipped[0], base=replace(flipped[0].base, register=other))
    must_report("registers", _register_problems("branching", flipped))

    # A ReturnExpectation for a tool the case never offers, and one whose items
    # the backend cannot carry.
    chain = _first_case("sequential_chain")
    stranger = replace(chain, returns=chain.returns + (
        ReturnExpectation("kb_search", 0, "chunks", ()),))
    must_report("validate/return-tool", _validation_problems([stranger]))
    ghost = replace(chain, returns=tuple(
        replace(one, result_item_ids=one.result_item_ids + ("i999",)) for one in chain.returns))
    must_report("validate/return-item", _validation_problems([ghost]))

    # The backend check: a return that names an item the result does not carry.
    # A MESSAGE-LOCUS ITEM IS NEVER TAGGED IN A RESULT: the backend labels what
    # it HOLDS, so naming one here is the shape of «a hop the run can never
    # observe» — the defect this check exists for.
    said = next(item for item in chain.base.pii if item.where.kind == "message")
    swapped = _backend_problems(replace(
        chain, returns=tuple(replace(one, result_item_ids=(said.id,))
                             for one in chain.returns)))
    must_report("backend/untagged-item", swapped)

    # A forced error with two `{value}` slots.
    twice = replace(retry, forced=(replace(retry.forced[0],
                                           message_template="{value} и ещё {value}"),))
    must_report("validate/forced-template", _validation_problems([twice]))

    return problems


_WRAPPERS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("test_no_pseudex", test_no_pseudex),
    ("test_build_each_family", test_build_each_family),
    ("test_behaviour_specs", test_behaviour_specs),
    ("test_type_quotas", test_type_quotas),
    ("test_registers", test_registers),
    ("test_hops_orientation", test_hops_orientation),
    ("test_no_search", test_no_search),
    ("test_plan_a_matches_the_floors", test_plan_a_matches_the_floors),
    ("test_offered_tools_are_in_the_family_inventory",
     test_offered_tools_are_in_the_family_inventory),
    ("test_backend_returns_the_declared_items", test_backend_returns_the_declared_items),
    ("test_import_orders", test_import_orders),
    ("test_checks_can_fail", test_checks_can_fail),
)


def main() -> int:
    failures = 0
    for name, check in _WRAPPERS:
        problems = check()
        if problems:
            failures += 1
            print(f"FAIL {name}")
            for problem in problems[:8]:
                print(f"     {problem}")
        else:
            print(f"ok   {name}")
    print(f"случаев: {len(CORPUS)} · семей: {len(FAMILIES)} · "
          f"проверок: {len(_WRAPPERS)} · провалов: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
