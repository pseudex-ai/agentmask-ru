# test_scenarios6_plan.py — the corpus plan and the full build under test.
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_scenarios6_plan
#
# No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and returns
# the exit code. The acceptance test is `test_plan_meets_full_floors` — it builds
# the whole 500-case corpus once and runs `validate_corpus_v6(cases, "full", 500)`.
# It is slow by design: a plan whose floors can only be checked by building it is
# the point of the file.

from __future__ import annotations

import pathlib
import subprocess
import sys
from collections.abc import Callable

from bench.agentpii5 import schema_v6
from bench.agentpii5.scenarios6 import build_full, plan_v6

_PROTOTYPE = str(pathlib.Path(__file__).resolve().parent.parent.parent)


def test_plan_meets_full_floors() -> list[str]:
    """THE acceptance test: `validate_corpus_v6(build_full(), "full", 500)` names
    no K6 problem. A plan whose floors the build cannot meet is a red line here,
    not a note in a report."""
    cases = build_full.build_full()
    problems = schema_v6.validate_corpus_v6(cases, "full", 500)
    if len(cases) != 500:
        problems.append(f"K6-01 build_full returns {len(cases)} cases, expected 500")
    return list(problems)


def test_no_pseudex() -> list[str]:
    """`scenarios6/plan_v6.py` and `build_full.py` import neither `pseudex` nor
    `licensing`, checked in a FRESH process so a leak left by this runner cannot
    both load them and pass."""
    code = (
        "import sys; import bench.agentpii5.scenarios6.plan_v6; "
        "import bench.agentpii5.scenarios6.build_full; "
        "print(','.join(sorted(m for m in sys.modules "
        "if m.split('.')[0] in ('pseudex', 'licensing'))))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=_PROTOTYPE)
    if proc.returncode != 0:
        return [f"fresh process failed: {proc.stderr.strip()}"]
    leaked = proc.stdout.strip()
    if leaked:
        return [f"the plan or the build loads engine modules: {leaked}"]
    return []


def _ids(cases) -> list[str]:
    return [case.base.id for case in cases]


def test_cases_deterministic() -> list[str]:
    """`build_full(seed=7)` is reproducible and differs from `seed=8` only where
    a seed genuinely changes minted values (the case ids are seed-independent)."""
    problems: list[str] = []
    first = build_full.build_full(7)
    again = build_full.build_full(7)
    other = build_full.build_full(8)
    if _ids(first) != _ids(again):
        problems.append("the same seed produced different case ids")
    if first != again:
        problems.append("build_full(7) is not equal to build_full(7)")
    if first == other:
        problems.append("build_full(7) equals build_full(8) — the seed changes nothing")
    if _ids(first) != _ids(other):
        problems.append("a different seed moved the case ids (ids must be seed-independent)")
    return problems


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_plan_meets_full_floors,
    test_no_pseudex,
    test_cases_deterministic,
)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_scenarios6_plan: PASS" if not failures else f"test_scenarios6_plan: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
