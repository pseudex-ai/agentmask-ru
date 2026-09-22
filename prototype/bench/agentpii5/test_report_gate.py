"""The refusal, watched from both sides: a broken metric is refused, a real one is not.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_report_gate

C-090 and C-091. The gate is the one part of v5 that decides whether numbers
are printed at all, so it is the part that most needs to have been SEEN going
red. Here a deliberately constant metric is registered under a real name and
the report must (a) leave it out of `v5_lines`, (b) name it in `v5_refused`
with a reason, and (c) carry `НЕПОЛНЫЙ` in its header — and the same run with
the real registry must do none of those things, or the three assertions above
would pass on a report that is always incomplete.
"""
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import Line, Metric
from bench.agentpii5.fixtures import FIXTURES
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.report import (
    gate,
    gate_all,
    report_lines,
    run_id_of,
    selftest,
    side_by_side,
)
from bench.agentpii5.test_report import RUN_ID, build_run

# A non-diagnostic metric, so its refusal must also make the whole report
# incomplete; a diagnostic one is refused without that consequence.
BROKEN = "toolresult_masked"


def _always_one(_observations: object) -> Line:
    return Line(BROKEN, 1, 1)


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_broken_metric_is_refused() -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        v5_dir = build_run(root, RUN_ID, True)
        v4_dir = build_run(root, "baseline01", False)
        broken: dict[str, Metric] = {**METRIC_FUNCTIONS, BROKEN: _always_one}
        side = side_by_side(v5_dir, v4_dir, broken)
        healthy = side_by_side(v5_dir, v4_dir, METRIC_FUNCTIONS)
        lines = report_lines(v5_dir, v4_dir, broken)
        problems: list[str] = []
        if BROKEN in side.v5_lines:
            problems.append(f"{BROKEN} was printed although its fixtures refuse it")
        if BROKEN not in side.v5_refused:
            problems.append(f"{BROKEN} is not named in v5_refused")
        elif "fx_toolresult_masked" not in side.v5_refused[BROKEN]:
            problems.append(f"the reason does not name the failing fixture: "
                            f"{side.v5_refused[BROKEN]!r}")
        if not side.incomplete or contracts.INCOMPLETE_REPORT_MARK not in lines[0]:
            problems.append(f"a refused non-diagnostic metric must mark the report: {lines[0]!r}")
        if any(line.strip().startswith(BROKEN + " ") for line in lines):
            problems.append(f"{BROKEN} still has a printed line")
        # The other side of the same assertion: with the real registry nothing
        # is refused and the header is clean. Without this, «is it incomplete»
        # would pass on a report that can never be complete.
        if healthy.v5_refused:
            problems.append(f"the real registry was refused: {healthy.v5_refused}")
        if healthy.incomplete:
            problems.append("a healthy run with a calibrated judge was marked incomplete")
        gate_path = records.run_file(v5_dir, run_id_of(v5_dir), "<run>.gate.json")
        written = json.loads(gate_path.read_text(encoding="utf-8"))
        if written.get(BROKEN, {}).get("printable") is not False:
            problems.append("<run>.gate.json does not record the refusal")
        return problems


def test_gate_never_raises() -> list[str]:
    """A metric that throws is a FINDING, not a crash: a gate that died on it
    would take the whole report with it and the one line that mattered would
    never be printed."""
    def explodes(_observations: object) -> Line:
        raise RuntimeError("метрика сломана")

    verdict = gate(explodes, FIXTURES[BROKEN])
    problems: list[str] = []
    if verdict.printable:
        problems.append("a metric that raises was declared printable")
    if "метрика упала" not in verdict.why:
        problems.append(f"the reason does not say the metric raised: {verdict.why!r}")
    return problems


def test_missing_fixtures_are_a_refusal() -> list[str]:
    """A metric nobody wrote fixtures for is refused with that reason. «No
    fixtures» must never read as «passed»."""
    extra: dict[str, Metric] = {**METRIC_FUNCTIONS,
                                "новая_метрика": lambda _obs: Line("новая_метрика", 1, 1)}
    verdicts = gate_all(extra)
    problems: list[str] = []
    verdict = verdicts.get("новая_метрика")
    if verdict is None or verdict.printable:
        problems.append("a metric with no fixtures was allowed to print")
    elif "нет фикстур" not in verdict.why:
        problems.append(f"the reason does not say the fixtures are missing: {verdict.why!r}")
    return problems


def test_selftest_passes() -> list[str]:
    """C-091. Every metric, replaced by a constant, must be refused; every real
    one must be printable. The `e2e/audit_gates.py --selftest` shape."""
    return [] if selftest() == 0 else ["report --selftest did not exit 0"]


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("broken_metric_is_refused", test_broken_metric_is_refused),
        ("gate_never_raises", test_gate_never_raises),
        ("missing_fixtures_are_a_refusal", test_missing_fixtures_are_a_refusal),
        ("selftest_passes", test_selftest_passes),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("report gate: PASS" if not failures else "report gate: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
