"""`fixtures.py` pinned: three kinds per metric, each printing what it declares.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_fixtures

THIS IS THE GATE RUN AS A TEST. `report.gate_all` refuses a metric whose
fixtures do not separate; here the same thing is asserted directly, so a broken
fixture is a red test at build time and not a silently missing line in a report
three weeks later.

It also asserts the property that makes the fixtures worth having: the `zero`
and the `one` input must be DIFFERENT (a pair that separates because the metric
is constant would separate on nothing), and every `adversarial` fixture must
name what a wrong metric would print instead — a trap nobody described is a
third ordinary case wearing the word «adversarial».
"""
import sys
from collections.abc import Callable

from bench.agentpii5 import contracts
from bench.agentpii5.fixtures import FIXTURES, NOTES
from bench.agentpii5.metrics import METRIC_FUNCTIONS

NON_LEVEL: tuple[str, ...] = tuple(
    name for name in contracts.METRIC_NAMES if name not in contracts.V4_LEVEL_NAMES)


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_three_kinds_each() -> list[str]:
    """C-008, C-089. Every non-level metric ships all three kinds, named as the
    brief names them, and nothing else is in the table."""
    problems: list[str] = []
    for name in NON_LEVEL:
        fixtures = FIXTURES.get(name)
        if fixtures is None:
            problems.append(f"{name}: no fixtures — the report will refuse it")
            continue
        kinds = [fixture.kind for fixture in fixtures]
        if sorted(kinds) != sorted(contracts.FIXTURE_KINDS):
            problems.append(f"{name}: kinds {kinds}, expected {list(contracts.FIXTURE_KINDS)}")
        for fixture in fixtures:
            if fixture.metric != name:
                problems.append(f"{fixture.name}: filed under {name}, declares {fixture.metric}")
            if fixture.name != f"fx_{name}_{fixture.kind}":
                problems.append(f"{fixture.name}: not named fx_<metric>_<kind>")
            if not fixture.input:
                problems.append(f"{fixture.name}: no observations at all")
    extra = set(FIXTURES) - set(NON_LEVEL)
    if extra:
        problems.append(f"fixtures for names that are not metrics: {sorted(extra)}")
    return problems


def test_fixture_expectations() -> list[str]:
    """The gate, run here. Each fixture's metric must print exactly the
    fraction the fixture declares, and `zero`/`one` must be 0.0 and 1.0."""
    problems: list[str] = []
    for name, fixtures in sorted(FIXTURES.items()):
        function = METRIC_FUNCTIONS.get(name)
        if function is None:
            problems.append(f"{name}: fixtures without a metric function")
            continue
        rates: dict[str, float] = {}
        for fixture in fixtures:
            line = function(fixture.input)
            if (line.hits, line.total) != (fixture.expected_hits, fixture.expected_total):
                problems.append(f"{fixture.name}: printed {line.hits}/{line.total}, "
                                f"declared {fixture.expected_hits}/{fixture.expected_total}")
            rates[fixture.kind] = line.rate
        if rates.get("zero", 1.0) != 0.0:
            problems.append(f"{name}: the zero fixture is not 0.0 ({rates.get('zero')})")
        if rates.get("one", 0.0) != 1.0:
            problems.append(f"{name}: the one fixture is not 1.0 ({rates.get('one')})")
        if rates.get("one", 0.0) - rates.get("zero", 1.0) < contracts.FIXTURE_MIN_SEPARATION:
            problems.append(f"{name}: zero and one do not separate")
    return problems


def test_kind_invariants() -> list[str]:
    """`zero` is 0 of n > 0; `one` is n of n > 0. A `zero` fixture with an empty
    population would «separate» against nothing and would let a metric that
    always returns `Line(0, 0)` through the gate."""
    problems: list[str] = []
    for name, fixtures in sorted(FIXTURES.items()):
        by_kind = {fixture.kind: fixture for fixture in fixtures}
        zero, one = by_kind.get("zero"), by_kind.get("one")
        if zero is None or one is None:
            continue
        if not (zero.expected_hits == 0 and zero.expected_total > 0):
            problems.append(f"{name}: zero declares {zero.expected_hits}/{zero.expected_total}")
        if not (one.expected_hits == one.expected_total > 0):
            problems.append(f"{name}: one declares {one.expected_hits}/{one.expected_total}")
        if zero.input == one.input:
            problems.append(f"{name}: zero and one are the SAME input — they separate on nothing")
    return problems


def test_adversarial_notes() -> list[str]:
    """Every trap says what a wrong metric would print. Four of v4's defects
    were found by asking that question of code that looked right."""
    problems: list[str] = []
    for name, fixtures in sorted(FIXTURES.items()):
        for fixture in fixtures:
            if fixture.kind != "adversarial":
                continue
            if not NOTES.get(fixture.name, "").strip():
                problems.append(f"{fixture.name}: no note saying what a wrong metric would print")
            if fixture.expected_total <= 0:
                problems.append(f"{fixture.name}: an empty adversarial population traps nothing")
    return problems


def test_fixtures_are_hand_built() -> list[str]:
    """No fixture may carry a cost, a session or a model: a record produced by
    running the thing under test agrees with it by construction. The gateway
    arm's `cost_usd` is the cheapest evidence that a live run wrote it."""
    problems: list[str] = []
    for name, fixtures in sorted(FIXTURES.items()):
        for fixture in fixtures:
            for one in fixture.input:
                if one.run.base.cost_usd != 0.0:
                    problems.append(f"{fixture.name} ({name}): a run record with a cost")
                if one.ic is not None or one.cc is not None:
                    problems.append(f"{fixture.name}: fixtures carry no v4 verdicts by contract")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("three_kinds_each", test_three_kinds_each),
        ("fixture_expectations", test_fixture_expectations),
        ("kind_invariants", test_kind_invariants),
        ("adversarial_notes", test_adversarial_notes),
        ("fixtures_are_hand_built", test_fixtures_are_hand_built),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print(f"fixtures: PASS ({len(FIXTURES)} метрик × 3)" if not failures
          else "fixtures: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
