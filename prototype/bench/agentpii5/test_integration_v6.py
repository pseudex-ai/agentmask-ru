"""The acceptance test over `review/v6-integration.json` (tz-agentpii6.md §7.2).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_integration_v6

Red when, for a REGISTERED new type of THIS phase: there is no `l9` row,
`exception != 0`, `absent_required != 0` or `cases < 1`; when `l8.unprovable` is
non-empty; when the leak table appears without a `ladder_stamp` (or is absent
with one); when the dry-run cost estimate is not numeric; or when `integrate_v6`
imports the engine.

No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and returns
the exit code.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import contracts, integrate_v6, pii_types

_HERE = Path(__file__).resolve().parent
_OUT = _HERE / "review" / "v6-integration.json"


def _report() -> dict[str, object]:
    return json.loads(_OUT.read_text(encoding="utf-8"))


def _l9_rows(report: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = report.get("l9", {}).get("types", [])
    return {str(row["type"]): row for row in rows}


def test_l9_covers_registered_types(report: dict[str, object]) -> list[str]:
    """Every registered new type has an l9 row, and each is healthy: ≥1 case,
    no exception, no absent required IN hop."""
    problems: list[str] = []
    rows = _l9_rows(report)
    for type_id in pii_types.NEW_ITEM_TYPES:
        row = rows.get(type_id)
        if row is None:
            problems.append(f"{type_id}: no l9 row")
            continue
        if int(row["cases"]) < 1:
            problems.append(f"{type_id}: cases {row['cases']} < 1")
        if int(row["exception"]) != 0:
            problems.append(f"{type_id}: exception {row['exception']} != 0")
        if int(row["absent_required"]) != 0:
            problems.append(f"{type_id}: absent_required {row['absent_required']} != 0")
    return problems


def test_l8_unprovable_empty(report: dict[str, object]) -> list[str]:
    unprovable = report.get("l8", {}).get("unprovable", [])
    if unprovable:
        return [f"l8.unprovable is not empty: {unprovable[:5]}"]
    return []


def test_leak_table_needs_stamp() -> list[str]:
    """R6-33: the per-type leak table exists only with a `ladder_stamp`."""
    problems: list[str] = []
    cases, ladder, ladder_path = integrate_v6.load_corpus_and_ladder("full")
    stamped = integrate_v6.l9_section(cases, "full", "a-stamp")
    unstamped = integrate_v6.l9_section(cases, "full", None)
    stamped_rows = {str(row["type"]): row for row in stamped["types"]}
    unstamped_rows = {str(row["type"]): row for row in unstamped["types"]}
    if any("leak" in row for row in unstamped_rows.values()):
        problems.append("a leak table is present but no `ladder_stamp` was set")
    if not any("leak" in row for row in stamped_rows.values()):
        problems.append("`ladder_stamp` is set but no l9 row carries a leak table")
    return problems


def test_dry_run_cost() -> list[str]:
    """A numeric nano/small/medium/max cost estimate, computed with no live call."""
    problems: list[str] = []
    cases, ladder, _path = integrate_v6.load_corpus_and_ladder("full")
    cost = integrate_v6.dry_run_cost(cases, ladder)
    for tier in ("nano", "small", "medium", "max"):
        row = cost.get(tier)
        if row is None:
            problems.append(f"{tier}: no dry-run row")
            continue
        for key in ("cases", "model_calls_low", "model_calls_high", "tool_calls_low",
                    "tool_calls_high", "prompt_tokens", "reserve_usd"):
            value = row.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"{tier}.{key}: not numeric ({value!r})")
    return problems


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules
           if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def main() -> int:
    # The report is a generated artifact (never committed). If it is absent —
    # a fresh checkout that ran the tests before the writer — build it first so
    # the test is self-contained. The writer refuses a report without
    # `generated_by`, which `build_report` always sets.
    if not _OUT.exists():
        code = integrate_v6.main(["--phase", "full"])
        if code != 0:
            return code
    report = _report()
    checks: tuple[tuple[str, Callable[..., list[str]]], ...] = (
        ("l9_covers_registered_types", lambda: test_l9_covers_registered_types(report)),
        ("l8_unprovable_empty", lambda: test_l8_unprovable_empty(report)),
        ("leak_table_needs_stamp", test_leak_table_needs_stamp),
        ("dry_run_cost", test_dry_run_cost),
        ("no_pseudex", test_no_pseudex),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("integration_v6: PASS" if not failures
          else "integration_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
