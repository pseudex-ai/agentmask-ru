"""`calibration.py` v6 pinned: the calibration records WHICH new types it saw.

    cd prototype && source .venv/bin/activate
    && python3 -m bench.agentpii5.test_calibration_v6

Offline: no model, no sheet, no money. Two facts from §9.4: `answer_types` reads
the v6 ids off the answer hops (the same `hop.pii_type` every calibration row
carries), and `new_types_seen` names the NEW types a drawn sample recorded —
the list the report header prints (§6.5: «какие новые типы видела калибровка»).
"""
import sys
from collections.abc import Callable

from bench.agentpii5 import calibration, contracts
from bench.agentpii5.contracts import CalibrationRecord
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


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def _v6_answer_observation(case_id: str) -> object:
    """One observation whose OUT/answer hop carries a NEW type (OMS_ENP)."""
    enp = "7707536455681514"
    item = _item("e1", "OMS_ENP", enp, enp, "i1", _in_message(0, 0, len(enp)))
    answer = _hop("OUT", "answer", "e1", 0, 0, "", -1, -1, "")
    case = _case(case_id, "single", (enp,), (item,), (answer,))
    return _obs(case, _run(case_id), (_seen(case, answer, "OMS_ENP", enp, enp),))


def test_answer_types_records_new_types() -> list[str]:
    """§9.4: the stratum axis `answer_types` carries the v6 id off the answer hop,
    so a calibration row's `pii_types` records which NEW types it drew."""
    problems: list[str] = []
    obs = _v6_answer_observation("cal6-a")
    types = calibration.answer_types(obs)
    if "OMS_ENP" not in types:
        problems.append(f"the v6 answer type is not recorded: {types}")
    if "NAME" in types:
        problems.append("a type with no answer hop leaked into the answer types")
    return problems


def test_new_types_seen() -> list[str]:
    """§6.5 / §9.4: `new_types_seen` names exactly the NEW types a sample drew,
    and only them — a v5 type in the same rows is not reported as new."""
    problems: list[str] = []
    rows = (
        CalibrationRecord(sample_id="a|0", case_id="a", pii_types=("OMS_ENP", "VIN"),
                          family="single", register="chat", holdout=False, human_label="верно",
                          judge_label="верно", judge_reason="", repeat_index=0,
                          judge_model="m", prompt_sha256="p"),
        CalibrationRecord(sample_id="b|0", case_id="b", pii_types=("NAME", "PHONE"),
                          family="single", register="chat", holdout=False, human_label="верно",
                          judge_label="верно", judge_reason="", repeat_index=0,
                          judge_model="m", prompt_sha256="p"),
    )
    seen = calibration.new_types_seen(rows)
    if seen != ("OMS_ENP", "VIN"):
        problems.append(f"new_types_seen returned {seen}, expected ('OMS_ENP', 'VIN')")
    if calibration.new_types_seen(()) != ():
        problems.append("an empty sample must report no new types")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("answer_types_records_new_types", test_answer_types_records_new_types),
        ("new_types_seen", test_new_types_seen),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("calibration_v6: PASS" if not failures
          else "calibration_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
