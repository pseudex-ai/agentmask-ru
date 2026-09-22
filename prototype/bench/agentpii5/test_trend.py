"""The trend: one row per run, from the registry and the run's own report.json.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_trend

ТЗ `docs/tz-bench-harness.md` §5.2, item 16. Everything here runs on files:
two run directories written by `test_report.build_run`, their `report.json`
written by `reportjson.write`, and a `runs.json` written by this test in the
shape §1.2 describes.

Each check goes red on a revert:

  * a run with no report is a ROW, not a gap — drop it and
    `a_run_without_a_report_still_has_a_row` finds the missing line;
  * the registry has ONE reader and it is `runinfo`'s — parse `runs.json` here
    instead and `the_registry_is_read_through_runinfo` goes green on a registry
    of another version, which the real reader refuses;
  * a regression is between two runs of the SAME tier — compare across tiers and
    `regression_is_within_one_tier` fires on a `nano`-vs-`medium` pair that
    differs only in n.
"""
import io
import json
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path

from bench.agentpii5 import contracts
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.reportjson import write as write_report_json
from bench.agentpii5.test_report import RUN_ID, build_run
from bench.agentpii5.runinfo import RunInfoError, RunRecord, append_run, read_runs
from bench.agentpii5.trend import (
    NO_REPORT,
    TREND_LINES,
    ordered,
    regressions,
    render_json,
    render_markdown,
    trend_rows,
)
from bench.agentpii5.trend import main as trend_main

SECOND_RUN = "fixture0002"


def _record(run_id: str, date: str, tier: str, run_dir: Path, label: str) -> RunRecord:
    """One registry row, built with the REGISTRY's own dataclass.

    The fixture is written by `runinfo.append_run` — the writer the run itself
    uses — so this test proves the trend reads what a run WRITES. A row spelled
    by hand here would prove only that the trend agrees with this file."""
    return RunRecord(
        run_id=run_id, benchmark="agentpii5", started=date, finished=date,
        state="finished", tier=tier, cases=2, repeats=1, triples_done=2,
        transport_terminated=0, model=contracts.AGENT_MODEL,
        judge_model=contracts.JUDGE_MODEL, concurrency=2, corpus_digest="digest-v5",
        ladder_digest="ladder-1", label=label, note="", ceiling_usd=12.0,
        spent_usd=0.24, wall_s=61.0, verdict="полный", worktree="commit abcdef1",
        run_dir=str(run_dir))


def _registry(path: Path, rows: list[RunRecord]) -> Path:
    for row in rows:
        append_run(path, row)
    return path


def _two_runs(root: Path) -> tuple[Path, Path, Path]:
    """Two v5 runs with reports, one baseline, and the registry naming both."""
    baseline = build_run(root, "baseline01", False)
    first = build_run(root / "a", RUN_ID, True)
    second = build_run(root / "b", SECOND_RUN, True)
    write_report_json(first, baseline, METRIC_FUNCTIONS)
    write_report_json(second, baseline, METRIC_FUNCTIONS)
    # THE NEWER RUN IS APPENDED FIRST, on purpose. The registry is additive and
    # its order is the order rows were written, which is NOT the order the runs
    # began: a `--resume` writes its row after the run it resumed. A trend that
    # simply kept the file's order would pass every check on a fixture whose two
    # orders agree, and would print a regression backwards on the day they did
    # not.
    registry = _registry(root / "runs.json", [
        _record(SECOND_RUN, "2026-09-23T10:00:00+00:00", "nano", second, "после правки адресов"),
        _record(RUN_ID, "2026-09-20T10:00:00+00:00", "nano", first, "до правки адресов")])
    return first, second, registry


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_the_registry_is_read_through_runinfo() -> list[str]:
    """ONE reader of `runs.json`, and it is `runinfo`'s. A second parser here
    would be a second opinion about what a run was: the day a field is renamed,
    one of the two would print an empty column instead of going red.

    The check is that the trend's own CLI refuses a registry `runinfo` refuses
    (and names it), and that a registry `runinfo` accepts reads back whole."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        broken = root / "broken.json"
        broken.write_text(json.dumps({"version": 99, "runs": []}), encoding="utf-8")
        argv = sys.argv[:]
        sys.argv = ["trend", "--runs", str(broken)]
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = trend_main()
        finally:
            sys.argv = argv
        if code != 2:
            problems.append(f"a registry of another version was read anyway (exit {code})")
        sys.argv = ["trend", "--runs", str(root / "нет.json")]
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                missing = trend_main()
        finally:
            sys.argv = argv
        if missing != 2:
            problems.append(f"a missing registry was read as an empty one (exit {missing})")
        # The other side, or «it refuses» would pass on a reader that refuses
        # everything.
        good = read_runs(_registry(root / "good.json",
                                   [_record("x", "2026-09-23T10:00:00+00:00", "nano",
                                            root, "метка")]))
        if len(good) != 1 or good[0].label != "метка":
            problems.append(f"a well-formed registry did not read back: {good}")
        if not isinstance(RunInfoError("x"), ValueError):
            problems.append("the registry's own error type is not the one this module catches")
    return problems


def test_rows_join_the_registry_and_the_report() -> list[str]:
    """§5.2: «одна строка на прогон из runs.json + report.json». The lines come
    off the document, never off the text report — a trend that parsed the
    report's spacing broke the day the spacing moved."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        _first, _second, registry = _two_runs(Path(tmp))
        rows = trend_rows(read_runs(registry), TREND_LINES)
        if len(rows) != 2:
            problems.append(f"two runs produced {len(rows)} rows")
        if rows[0].record.started > rows[1].record.started:
            problems.append("the rows are not in date order")
        for row in rows:
            if row.problem:
                problems.append(f"{row.record.run_id}: {row.problem}")
            if not row.lines:
                problems.append(f"{row.record.run_id}: no line was read off the report")
            if row.incomplete is None:
                problems.append(f"{row.record.run_id}: the completeness verdict did not travel")
        if ordered(read_runs(registry))[0].run_id != rows[0].record.run_id:
            problems.append("the table's order is not the registry's, sorted by start time")
        table = render_markdown(rows, TREND_LINES)
        if len(table) != len(rows) + 2:
            problems.append(f"the table is not a header, a rule and one row per run: {table}")
        if "метка" not in table[0] or "ярус" not in table[0]:
            problems.append(f"the header names neither the label nor the tier: {table[0]}")
        if "после правки адресов" not in "\n".join(table):
            problems.append("the label is not in the table — §1.3 made it mandatory for a reason")
        as_json = render_json(rows, TREND_LINES)
        runs = as_json["runs"]
        if not isinstance(runs, list) or len(runs) != 2:
            problems.append(f"the JSON does not carry both runs: {as_json}")
        elif "corpus_digest" not in runs[0] or "lines" not in runs[0]:
            problems.append(f"a JSON row without its digest or its lines: {sorted(runs[0])}")
    return problems


def test_a_run_without_a_report_still_has_a_row() -> list[str]:
    """An interrupted run is exactly the run a reader looks for a month later.
    Dropping it would make the trend a list of the runs that went well."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline = build_run(root, "baseline01", False)
        done = build_run(root / "a", RUN_ID, True)
        write_report_json(done, baseline, METRIC_FUNCTIONS)
        stopped = build_run(root / "b", SECOND_RUN, True)      # no report.json written
        registry = _registry(root / "runs.json", [
            _record(RUN_ID, "2026-09-20T10:00:00+00:00", "nano", done, "целый"),
            replace(_record(SECOND_RUN, "2026-09-23T10:00:00+00:00", "nano", stopped,
                            "прерван"), state="interrupted", transport_terminated=3)])
        rows = trend_rows(read_runs(registry), TREND_LINES)
        if len(rows) != 2:
            problems.append(f"the run without a report was dropped: {len(rows)} rows")
            return problems
        if not rows[1].problem.startswith(NO_REPORT):
            problems.append(f"the missing report is not named: {rows[1].problem!r}")
        if rows[1].lines:
            problems.append("a run with no report produced lines anyway")
        if rows[1].incomplete is not None:
            problems.append("a run with no report was given a completeness verdict")
        table = "\n".join(render_markdown(rows, TREND_LINES))
        if NO_REPORT not in table or "прерван" not in table:
            problems.append("the table hides the interrupted run")
        # The CLI says so in its exit code: a CI step reading only stdout would
        # go green on a table full of «отчёта нет».
        argv = sys.argv[:]
        sys.argv = ["trend", "--runs", str(registry)]
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = trend_main()
        finally:
            sys.argv = argv
        if code != 1:
            problems.append(f"a trend that could not read a report exited {code}")
    return problems


def test_regression_is_within_one_tier() -> list[str]:
    """A `nano` run beside a `medium` one differ by three orders of magnitude in
    n; calling that a regression would make the trend fire on every smoke run.
    The pair must be consecutive AND of one tier."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _first, _second, registry = _two_runs(root)
        rows = list(trend_rows(read_runs(registry), TREND_LINES))
        # Two runs of one tier, the later one worse: the drop must be named,
        # with both dates and both run ids.
        rows[1] = replace(rows[1], lines={**rows[1].lines, "leak": (5, 10)})
        rows[0] = replace(rows[0], lines={**rows[0].lines, "leak": (10, 10)})
        better, worse = rows[0], rows[1]
        fallen = regressions(rows, ["leak"], 1.0)
        if not fallen or "leak" not in fallen[0]:
            problems.append(f"a 50pp fall on one tier was not reported: {fallen}")
        elif better.record.run_id[:8] not in fallen[0] or worse.record.run_id[:8] not in fallen[0]:
            problems.append(f"the pair is not named: {fallen[0]}")
        # The same pair on two tiers is NOT a regression.
        across = [replace(rows[0], record=replace(rows[0].record, tier="medium")), rows[1]]
        if regressions(across, ["leak"], 1.0):
            problems.append("a nano-vs-medium pair was called a regression")
        # A rise is not a regression either, or the line would fire on every
        # improvement.
        if regressions([rows[1], rows[0]], ["leak"], 1.0):
            problems.append("an improvement was reported as a regression")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("the_registry_is_read_through_runinfo", test_the_registry_is_read_through_runinfo),
        ("rows_join_the_registry_and_the_report", test_rows_join_the_registry_and_the_report),
        ("a_run_without_a_report_still_has_a_row", test_a_run_without_a_report_still_has_a_row),
        ("regression_is_within_one_tier", test_regression_is_within_one_tier),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("trend: PASS" if not failures else "trend: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
