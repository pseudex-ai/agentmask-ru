"""`report.py` v6 pinned: the V6_AXES, the per-type slice extras, and the gated
OD-54 rows — all only on a run with a v6 case.

    cd prototype && source .venv/bin/activate
    && python3 -m bench.agentpii5.test_report_v6

Offline: the report helpers run over hand-built observations, never a run
directory, so no corpus, no model, no engine. The gating is the whole point:
`contracts.AXES` stays the v5 ten, and the v6 block exists only behind
`has_v6_case`, so an old-corpus report keeps its exact bytes (F7).
"""
import sys
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii5 import contracts
from bench.agentpii5.contracts import CaseV6Meta
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    REAL_NAME,
    _case,
    _hop,
    _in_message,
    _item,
    _obs,
    _run,
    _seen,
)
from bench.agentpii5.report import (
    has_v6_case,
    v6_axis_rows,
    v6_new_row_lines,
    v6_type_slice_lines,
)


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def _vin_case(case_id: str) -> object:
    """One v6 case: a VIN item (glyph-folded, a checksum type for the КС split)
    and a declared IN/user hop, plus the industry/provenance meta."""
    vin = "XTAGFK330LY123456"
    item = _item("v1", "VIN", vin, vin, "i1", _in_message(0, 0, len(vin)))
    hop = _hop("IN", "user", "v1", 0, 0, "", -1, -1, "")
    case = _case(case_id, "single", (vin,), (item,), (hop,))
    case = replace(case, v6=CaseV6Meta(industry="auto", provenance="synthetic",
                                       skeleton_ref="", procedure_ref=""))
    return _obs(case, _run(case_id), (_seen(case, hop, "VIN", "EAHNMR007SF890123", vin),))


def test_no_v6_case_prints_no_v6_block() -> list[str]:
    """F7: the GATE that keeps the v6 block off an old-corpus report. `render`
    calls the v6 helpers only when `has_v6_case` is True, so a v5 run never
    gains a line — the helpers themselves are ungated workers."""
    name = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
    hop = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    case = _case("r6v-old", "single", (REAL_NAME,), (name,), (hop,))
    obs = _obs(case, _run("r6v-old"), (_seen(case, hop, "NAME", FAKE_NAME, REAL_NAME),))
    problems: list[str] = []
    if has_v6_case((obs,)):
        problems.append("a v5 case was read as a v6 case")
    if not has_v6_case((_vin_case("r6v-v6"),)):
        problems.append("a v6 case was not read as one")
    return problems


def test_v6_axes_print_only_on_v6_case() -> list[str]:
    """R6-28 / §6.5: `industry`/`provenance`/`type_class` print on a v6 run and
    are NOT part of `contracts.AXES`."""
    problems: list[str] = []
    for axis in ("industry", "provenance", "type_class"):
        if axis in contracts.AXES:
            problems.append(f"{axis} leaked into contracts.AXES")
    obs = (_vin_case("r6v-v6"),)
    lines = v6_axis_rows(obs)
    joined = "\n".join(lines)
    for axis in ("industry", "provenance", "type_class"):
        if f"/{axis}:" not in joined:
            problems.append(f"axis {axis} did not print on a v6 run")
    # `type_class` is a HOP axis: it must be a slice of the hop-sliceable lines.
    if not any(line.startswith("   leak/type_class:") for line in lines):
        problems.append("`leak/type_class` did not print — a v6 hop axis is missing")
    return problems


def test_pii_type_slice_extras() -> list[str]:
    """§6.5: beside each new type — grammar status, cases/elements/hops, the
    R-58 survival exclusion, and for VIN the «КС верна / неверна» split."""
    problems: list[str] = []
    lines = v6_type_slice_lines((_vin_case("r6v-slice"),))
    if not lines:
        problems.append("no v6 type slice line for a VIN case")
        return problems
    line = lines[0]
    if "VIN" not in line:
        problems.append(f"the slice line is not about VIN: {line!r}")
    for token in ("грамматика", "случаев", "элементов", "хопов", "не оценивается по выживанию"):
        if token not in line:
            problems.append(f"the slice line lacks {token!r}: {line!r}")
    if "КС верна" not in line or "неверна" not in line:
        problems.append(f"the VIN slice lacks the «КС верна/неверна» split: {line!r}")
    return problems


def test_new_rows_gated() -> list[str]:
    """§6.3: the three OD-54 rows print on a v6 run, each gated by its fixtures."""
    problems: list[str] = []
    lines = v6_new_row_lines((_vin_case("r6v-rows"),))
    joined = "\n".join(lines)
    for name in ("typed_user", "fake_checksum_invalid", "overmask_result"):
        if name not in joined:
            problems.append(f"the v6 row {name} did not print")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("no_v6_case_prints_no_v6_block", test_no_v6_case_prints_no_v6_block),
        ("v6_axes_print_only_on_v6_case", test_v6_axes_print_only_on_v6_case),
        ("pii_type_slice_extras", test_pii_type_slice_extras),
        ("new_rows_gated", test_new_rows_gated),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("report_v6: PASS" if not failures else "report_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
