# test_overlap_review.py — the S7/G8 instrument over `overlap_review.py`.
#
#     cd prototype && source .venv/bin/activate
#     python3 -m bench.agentpii5.test_overlap_review
#
# The RED clause this pins (SPEC §6, S7): «the 24 overlap review records exist,
# one per path», and «no old corpus was regenerated over the frozen evidence».
# Each rule has a negative half; the ones driven by an injected record set live
# in `overlap_review.record_problems()`, and this module asserts they fire.
#
# NO ENGINE, NO MODEL, NO NETWORK: file hashes and the transcribed decision
# table only.
from __future__ import annotations

import sys
from collections.abc import Callable

from bench.agentpii5 import overlap_review as orv

# SPEC §2 «Decision distribution», transcribed from the plan.
DECLARED_DISTRIBUTION: dict[str, int] = {
    "HAND_MERGE_ADDITIVE": 11,
    "HAND_MERGE_KEEP_V5_SEMANTICS": 7,
    "ADOPT_V6": 4,
    "GATED_ADOPT_V6": 1,
    "KEEP_V5": 1,
}


def test_the_24_records_exist_one_per_path() -> list[str]:
    problems: list[str] = []
    records = orv.RECORDS
    if len(records) != 24:
        problems.append(f"{len(records)} records, the plan declares 24 overlap paths")
    if len({record.id for record in records}) != len(records):
        problems.append("duplicate record ids")
    paths = [record.path for record in records]
    if len(set(paths)) != len(paths):
        problems.append("two records for one path")
    root = orv.repo_root()
    for record in records:
        if not (root / record.path).is_file():
            problems.append(f"{record.id} {record.path}: no such path in the tree")
        if not record.keep_v5:
            problems.append(f"{record.id}: nothing recorded as kept")
        if not record.owner_covered:
            problems.append(f"{record.id}: no owner decision recorded")
    # THE NEGATIVE: the clause is not satisfied by having any 24 objects — an
    # injected duplicate path is caught.
    mutated = orv.RECORDS + (orv.RECORDS[0],)
    if not any("two records for one path" in problem
               for problem in orv._problems_for(mutated, orv.RESOLVED_IN)):
        problems.append("a duplicated path was not caught")
    return problems


def test_the_decisions_are_the_declared_ones() -> list[str]:
    problems: list[str] = []
    live = {name: sum(1 for record in orv.RECORDS if record.decision == name)
            for name in orv.DECISIONS}
    if live != DECLARED_DISTRIBUTION:
        problems.append(f"decision distribution {live} != SPEC §2 {DECLARED_DISTRIBUTION}")
    for record in orv.RECORDS:
        if record.decision not in orv.DECISIONS:
            problems.append(f"{record.id}: decision {record.decision!r} is not declared")
    # THE NEGATIVE: a sixth mechanism is not silently accepted.
    mutated = (orv.RECORDS[0].__class__(
        id=orv.RECORDS[0].id, path=orv.RECORDS[0].path, decision="OURS",
        keep_v5=orv.RECORDS[0].keep_v5, adopt_v6=orv.RECORDS[0].adopt_v6,
        owner_covered=orv.RECORDS[0].owner_covered,
        red_acceptance=orv.RECORDS[0].red_acceptance),) + orv.RECORDS[1:]
    if not any("is not declared" in problem
               for problem in orv._problems_for(mutated, orv.RESOLVED_IN)):
        problems.append("an undeclared merge mechanism was not caught")
    return problems


def test_the_two_rows_s7_owes_are_recorded() -> list[str]:
    """The plan declared C17 (`test_form.py`) and C21 (`test_spec_form.py`); S2
    and S3 wrote no row for either, so S7 records them — with the evidence it
    has, not with an invented S3 hunk ledger."""
    problems: list[str] = []
    for rid, path, module in (
            ("C17", "prototype/bench/agentpii5/test_form.py", "bench.agentpii5.test_form"),
            ("C21", "prototype/bench/agentpii5/test_spec_form.py", "bench.agentpii5.test_spec_form")):
        record = next((r for r in orv.RECORDS if r.id == rid), None)
        if record is None:
            problems.append(f"{rid}: no record")
            continue
        if record.path != path:
            problems.append(f"{rid}: path is {record.path!r}, not {path!r}")
        if record.decision != "HAND_MERGE_KEEP_V5_SEMANTICS":
            problems.append(f"{rid}: decision is {record.decision!r}")
        if orv.RESOLVED_IN.get(rid) != "S7":
            problems.append(f"{rid}: not recorded as resolved by S7")
        if module not in orv.command_targets(record):
            problems.append(f"{rid}: no re-check naming {module}")
        if not (orv.repo_root() / path).is_file():
            problems.append(f"{rid}: {path} does not exist")
    if orv.RESOLVED_IN.get("C17") != "S7" or orv.RESOLVED_IN.get("C21") != "S7":
        problems.append("the S7-resolved rows are not both attributed to S7")
    return problems


def test_every_re_check_target_resolves() -> list[str]:
    """A re-check that names a module the package does not hold is a record of
    a check nobody can run — unless the gap is NAMED, which is what
    `KNOWN_ABSENT_TARGETS` is for (and there is exactly one)."""
    problems: list[str] = []
    missing: list[str] = []
    for record in orv.RECORDS:
        for target in orv.command_targets(record):
            if orv.target_exists(target):
                continue
            if target in orv.KNOWN_ABSENT_TARGETS:
                if not orv.KNOWN_ABSENT_TARGETS[target].strip():
                    problems.append(f"{record.id}: {target} absent with no reason")
                continue
            missing.append(f"{record.id}:{target}")
    if missing:
        problems.append(f"re-checks naming modules that do not exist: {missing}")
    if "bench.agentpii5.test_scenarios5" not in orv.KNOWN_ABSENT_TARGETS:
        problems.append("the one known absent target is no longer named")
    if not any(target.startswith("bench.agentpii5.")
               for record in orv.RECORDS for target in orv.command_targets(record)):
        problems.append("no record names a package module to re-run")
    return problems


def test_the_frozen_evidence_is_unchanged() -> list[str]:
    """«No old corpus was regenerated over the frozen evidence» — the three v5
    files against pins recorded outside this branch, the two v6 files against
    the v6 report's own record."""
    problems: list[str] = []
    problems += orv.frozen_problems()
    if not orv.FROZEN_V5:
        problems.append("no v5 input is pinned")
    for rel in orv.FROZEN_V5:
        pin, source = orv.FROZEN_INPUTS[rel]
        if len(pin) != 64 or any(ch not in "0123456789abcdef" for ch in pin):
            problems.append(f"{rel}: pin {pin!r} is not a sha256")
        if not source:
            problems.append(f"{rel}: pinned by nobody")
    live = orv.report()["frozen_inputs"]
    if set(live) != set(orv.FROZEN_INPUTS):
        problems.append("the report's frozen inputs are not the declared set")
    # THE NEGATIVE: a wrong pin is caught, so the check can fail.
    saved = dict(orv.FROZEN_INPUTS)
    try:
        orv.FROZEN_INPUTS["prototype/bench/agentpii5/ladder.json"] = (
            "0" * 64, "negative control")
        if not any("ladder.json" in problem for problem in orv.frozen_problems()):
            problems.append("a wrong ladder pin was not caught")
    finally:
        orv.FROZEN_INPUTS.clear()
        orv.FROZEN_INPUTS.update(saved)
    return problems


def test_the_report_is_deterministic_and_complete() -> list[str]:
    problems: list[str] = []
    first = orv.report()
    second = orv.report()
    if first != second:
        problems.append("two builds of the report differ")
    if first["overlap_paths"] != 24:
        problems.append(f"the report declares {first['overlap_paths']} paths")
    if len(first["records"]) != len(orv.RECORDS):
        problems.append("the report does not carry every record")
    if first["decisions"] != DECLARED_DISTRIBUTION:
        problems.append("the report's distribution is not the declared one")
    for row in first["records"]:
        if not row["sha256"] or len(str(row["sha256"])) != 64:
            problems.append(f"{row['id']}: no live sha256")
        if not row["resolved_in"]:
            problems.append(f"{row['id']}: no resolving stage")
    return problems


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("the_24_records_exist_one_per_path", test_the_24_records_exist_one_per_path),
    ("the_decisions_are_the_declared_ones", test_the_decisions_are_the_declared_ones),
    ("the_two_rows_s7_owes_are_recorded", test_the_two_rows_s7_owes_are_recorded),
    ("every_re_check_target_resolves", test_every_re_check_target_resolves),
    ("the_frozen_evidence_is_unchanged", test_the_frozen_evidence_is_unchanged),
    ("the_report_is_deterministic_and_complete", test_the_report_is_deterministic_and_complete),
)


def main() -> int:
    failures: list[str] = []
    for name, check in CHECKS:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 - the exception IS the failure
            problems = [f"raised {error!r}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    broken = {one.split(":")[0] for one in failures}
    print(f"overlap_review: {'PASS' if not failures else 'FAIL'} "
          f"({len(CHECKS) - len(broken)}/{len(CHECKS)} passed)")
    if failures:
        print("\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
