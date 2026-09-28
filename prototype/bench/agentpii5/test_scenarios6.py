# test_scenarios6.py — the v6 case builder under test: a valid case, the two
# behaviours that must build, the provenance refs that must resolve, and the
# purity of the value source.
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_scenarios6
#
# No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and returns
# the exit code.

from __future__ import annotations

import pathlib
import subprocess
import sys
from collections.abc import Callable

from bench.agentpii4.scenarios.common import ctx_for
from bench.agentpii5 import checksum_v6
from bench.agentpii5 import pii_types
from bench.agentpii5.schema import validate_v5
from bench.agentpii5.tools_v6 import TOOLS_V6
from bench.agentpii5.scenarios6.common6 import (load_skeletons, memory_anaphora_case,
                                                procedure_records, sequential_chain_case,
                                                single_case, skeleton_ids)

_PROTOTYPE = str(pathlib.Path(__file__).resolve().parent.parent.parent)

# The v6 tool names and v6 item types, read from their homes — never a copy.
_V6_TOOL_NAMES: frozenset[str] = frozenset(spec.base.name for spec in TOOLS_V6)
_V6_ITEM_TYPES: frozenset[str] = frozenset(
    t.id for t in pii_types.TYPE_REGISTRY if t.origin == pii_types.ORIGIN_V6 and t.item_type)


def _v6_items(case) -> list:
    """The case's items whose type is a v6 item type (origin == "v6")."""
    return [item for item in case.base.pii if item.type in _V6_ITEM_TYPES]


def _v6_hops(case) -> list:
    """The case's hops through a v6 tool."""
    return [hop for hop in case.hops if hop.tool_name in _V6_TOOL_NAMES]


def _checksum_problem(case) -> list[str]:
    """A minted v6 value must pass its declared checksum (R6-26's other half:
    the value is checksum-VALID, never a search of a finished string). BANK_ACCOUNT
    is a (account, BIK) pair check and is skipped — no example here mints it."""
    problems: list[str] = []
    for item in _v6_items(case):
        spec = next((t for t in pii_types.TYPE_REGISTRY if t.id == item.type), None)
        if spec is None or not spec.generated_checksum or spec.id == "BANK_ACCOUNT":
            continue
        try:
            ok = checksum_v6.validate(item.type, item.value)
        except (KeyError, ValueError) as error:
            problems.append(f"{case.base.id}: cannot validate {item.type}: {error}")
            continue
        if not ok:
            problems.append(f"{case.base.id}: {item.type} value {item.value!r} fails its "
                            f"{spec.generated_checksum} checksum")
    return problems


def _assert_valid(case) -> list[str]:
    """The one shape every build must satisfy: a valid v5 case with v6 meta set,
    at least one v6 item minted by gen_v6, and at least one hop through a v6 tool."""
    problems: list[str] = []
    for rule in validate_v5(case):
        problems.append(f"{case.base.id}: {rule}")
    if case.v6 is None:
        problems.append(f"{case.base.id}: v6 meta is None")
    elif not case.v6.industry or not case.v6.provenance:
        problems.append(f"{case.base.id}: v6.industry/provenance not set")
    if not _v6_items(case):
        problems.append(f"{case.base.id}: no v6 item minted by gen_v6")
    if not _v6_hops(case):
        problems.append(f"{case.base.id}: no hop through a v6 tool")
    problems.extend(_checksum_problem(case))
    return problems


def _build_one(ctx, builder) -> list[str]:
    try:
        return _assert_valid(builder(ctx))
    except Exception as error:  # noqa: BLE001 - a build crash is a failure to report
        return [f"{builder.__name__}: {type(error).__name__}: {error}"]


def test_builds_a_valid_v6_case() -> list[str]:
    """`new_builder_v6` assembles a valid v6 case, and at least `sequential_chain`
    and `memory_anaphora` build too — the two behaviours the foundation owes."""
    problems: list[str] = []
    ctx = ctx_for("single", 20260926, 0, "chat")
    problems.extend(_build_one(ctx, single_case))
    problems.extend(_build_one(ctx, sequential_chain_case))
    problems.extend(_build_one(ctx, memory_anaphora_case))
    return problems


def test_provenance_refs_resolve() -> list[str]:
    """R6-24: a live-register case names a skeleton in `v6/skeletons.json`; a
    documented-procedure case names a procedure in the `ProcedureRecord` registry."""
    problems: list[str] = []
    ctx = ctx_for("single", 20260926, 1, "chat")
    if not skeleton_ids():
        problems.append("v6/skeletons.json holds no skeletons")
    live = single_case(ctx, provenance="live-register",
                       skeleton_ref="retail-loyalty-receipt", procedure_ref="")
    if live.v6.skeleton_ref not in skeleton_ids():
        problems.append(f"live-register case names {live.v6.skeleton_ref!r}, "
                        f"which is not in {sorted(skeleton_ids())}")
    if not live.v6.skeleton_ref:
        problems.append("live-register case carries an empty skeleton_ref")
    documented = single_case(ctx, provenance="documented-procedure",
                             procedure_ref="requisites-115fz", skeleton_ref="")
    if documented.v6.procedure_ref not in procedure_records():
        problems.append(f"documented-procedure case names {documented.v6.procedure_ref!r}, "
                        f"which is not in {sorted(procedure_records())}")
    return problems


def test_gen_v6_not_pseudex() -> list[str]:
    """`scenarios6/common6.py` imports neither `pseudex` nor `licensing`. Checked
    in a FRESH process, so an import left behind by this runner cannot both load
    the module and pass the check."""
    code = (
        "import sys; import bench.agentpii5.scenarios6.common6; "
        "print(','.join(sorted(m for m in sys.modules "
        "if m.split('.')[0] in ('pseudex', 'licensing'))))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=_PROTOTYPE)
    leaked = proc.stdout.strip()
    if proc.returncode != 0:
        return [f"fresh process failed: {proc.stderr.strip()}"]
    if leaked:
        return [f"common6 loads engine modules: {leaked}"]
    return []


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_builds_a_valid_v6_case,
    test_provenance_refs_resolve,
    test_gen_v6_not_pseudex,
)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_scenarios6: PASS" if not failures else f"test_scenarios6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
