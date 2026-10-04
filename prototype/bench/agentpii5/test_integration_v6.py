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


# The v5 READ vocabulary as it was BEFORE this integration, written out so the
# projection cannot be "fixed" by editing the vocabulary it projects from.
V5_READ_STATUSES: tuple[str, ...] = ("observed", "leaked", "residual", "unmasked",
                                     "absent", "engine_kept", "not_masked",
                                     "leaf_foreign")
V5_OUT_WRITTEN: frozenset[str] = frozenset({"observed", "residual", "engine_kept",
                                            "not_masked", "leaf_foreign"})


def test_the_v6_funnel_is_a_named_projection() -> list[str]:
    """SPEC §4 (`COV-INTEGRATION-KEEP-V5`): the eight-entry READ vocabulary is
    untouched, the five-entry v6 funnel is a SEPARATE, NAMED projection, total
    over the read vocabulary, with its OWN declared denominator — and the v5
    line is not what it is computed from."""
    problems: list[str] = []
    if tuple(contracts.HOP_STATUSES) != V5_READ_STATUSES:
        problems.append(f"HOP_STATUSES moved: {contracts.HOP_STATUSES}")
    if contracts.OUT_HOP_WRITTEN_STATUSES != V5_OUT_WRITTEN:
        problems.append("the v5 form_hOUT denominator moved: "
                        f"{sorted(contracts.OUT_HOP_WRITTEN_STATUSES)}")
    funnel = tuple(contracts.V6_FUNNEL_STATUSES)
    if funnel != ("observed", "leaked", "residual", "unmasked", "absent"):
        problems.append(f"V6_FUNNEL_STATUSES is {funnel}")
    if not set(funnel) < set(contracts.HOP_STATUSES):
        problems.append("the v6 funnel is not a strict subset of the read vocabulary")
    if set(contracts.V6_FUNNEL_READ_TO_FUNNEL) != set(contracts.HOP_STATUSES):
        problems.append("the projection is not total over HOP_STATUSES")
    if set(contracts.V6_FUNNEL_READ_TO_FUNNEL.values()) != set(funnel):
        problems.append("the projection's image is not the v6 funnel")
    if not contracts.V6_FUNNEL_DENOMINATOR <= set(funnel):
        problems.append("the v6 denominator is not a subset of the v6 funnel")
    if contracts.V6_FUNNEL_DENOMINATOR == contracts.OUT_HOP_WRITTEN_STATUSES:
        problems.append("the v6 denominator was borrowed from the v5 line")
    if contracts.V6_FUNNEL_DENOMINATOR != frozenset({"observed", "unmasked"}):
        problems.append(f"the v6 denominator is {sorted(contracts.V6_FUNNEL_DENOMINATOR)}")
    # Each of the three v5-only OUT statuses folds to the ONE v6 name, and the
    # read vocabulary keeps them: nothing is re-labelled back into three.
    for read_status in ("engine_kept", "not_masked", "leaf_foreign"):
        if contracts.v6_funnel_status(read_status) != "unmasked":
            problems.append(f"{read_status} does not fold to unmasked")
    split = contracts.v6_funnel_split({"observed": 2, "leaf_foreign": 3, "absent": 1})
    if split != {"observed": 2, "leaked": 0, "residual": 0, "unmasked": 3, "absent": 1}:
        problems.append(f"v6_funnel_split gave {split}")
    # THE NEGATIVE: a status outside the read vocabulary raises rather than
    # being bucketed into a sixth funnel name.
    try:
        contracts.v6_funnel_status("healthy")
        problems.append("an undeclared status was projected instead of refused")
    except ValueError:
        pass
    return problems


def test_l9_rows_are_keyed_by_the_v6_id() -> list[str]:
    """The alias guard at the report level: an l9 row is keyed by the v6 type's
    OWN id, its status histogram is the named projection (never the eight-entry
    read vocabulary), and the v5 split rides beside it."""
    problems: list[str] = []
    section = integrate_v6.l9_section((), "full", None)
    rows = {str(row["type"]): row for row in section["types"]}
    if set(rows) != set(pii_types.NEW_ITEM_TYPES):
        problems.append("the l9 rows are not exactly the registered v6 item types")
    v5 = {spec.id for spec in pii_types.TYPE_REGISTRY
          if spec.origin == pii_types.ORIGIN_V5}
    for type_id, row in rows.items():
        if type_id in v5:
            problems.append(f"{type_id}: a v5 id carries an l9 row")
        if set(row["statuses"]) != set(contracts.V6_FUNNEL_STATUSES):
            problems.append(f"{type_id}: statuses {sorted(row['statuses'])} are not "
                            f"the v6 funnel")
        if row.get("funnel_denominator") != sorted(contracts.V6_FUNNEL_DENOMINATOR):
            problems.append(f"{type_id}: no declared v6 denominator")
        if "read_split" not in row:
            problems.append(f"{type_id}: the v5 read split is absent")
        if sum(row["statuses"].values()) != row["hops"]:
            problems.append(f"{type_id}: the funnel does not sum to its hops")
    # THE POSITIVE CONTROL: a read status the v5 funnel emits and the v6 funnel
    # does not name (`leaf_foreign`) is counted — through the one door — and the
    # v5 cause stays legible beside it. Without this, the guard above would pass
    # on a corpus that never produced the status the bug was about.
    from types import SimpleNamespace

    target = next(iter(pii_types.NEW_ITEM_TYPES))
    hop = SimpleNamespace(pii_type=target, case_id="synthetic", status="leaf_foreign",
                          hop=SimpleNamespace(kind="OUT", owner="tool"))
    real = integrate_v6.observations
    try:
        integrate_v6.observations = lambda cases, simulate: (SimpleNamespace(hops=(hop,)),)
        probe = {str(row["type"]): row
                 for row in integrate_v6.l9_section((), "full", None)["types"]}
    finally:
        integrate_v6.observations = real
    row = probe[target]
    if row["statuses"]["unmasked"] != 1:
        problems.append(f"{target}: a leaf_foreign hop was not projected to unmasked "
                        f"({row['statuses']})")
    if row.get("read_split") != {"leaf_foreign": 1}:
        problems.append(f"{target}: the v5 cause was lost: read_split={row.get('read_split')}")
    return problems


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
        ("the_v6_funnel_is_a_named_projection", test_the_v6_funnel_is_a_named_projection),
        ("l9_rows_are_keyed_by_the_v6_id", test_l9_rows_are_keyed_by_the_v6_id),
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
