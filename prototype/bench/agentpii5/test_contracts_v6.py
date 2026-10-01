# test_contracts_v6.py — the v6 axis vocabulary and shapes are what the spec
# says, and `contracts` re-exports them from the one home (never a copy).
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_contracts_v6
#
# No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and
# returns the exit code.

from __future__ import annotations

import dataclasses

import bench.agentpii5.contracts as contracts
import bench.agentpii5.contracts_v6 as v6


def test_industries() -> list[str]:
    problems: list[str] = []
    expected = (
        "retail", "logistics", "banks_mfo_collectors", "medicine", "insurance",
        "auto", "telecom", "real_estate", "hospitality", "hr", "legal",
        "government_services", "education", "internal_bi", "marketing_cdp",
    )
    if v6.INDUSTRIES != expected:
        problems.append(f"INDUSTRIES differs from the spec: {v6.INDUSTRIES}")
    if len(set(v6.INDUSTRIES)) != 15:
        problems.append("INDUSTRIES has duplicate values")
    return problems


def test_axes_and_provenance() -> list[str]:
    problems: list[str] = []
    if v6.V6_AXES != ("industry", "provenance", "type_class"):
        problems.append(f"V6_AXES differs from the spec: {v6.V6_AXES}")
    if v6.V6_PROVENANCE_KINDS != ("live-register", "documented-procedure", "synthetic"):
        problems.append(f"V6_PROVENANCE_KINDS differs from the spec: {v6.V6_PROVENANCE_KINDS}")
    if v6.V6_DIR != "bench/agentpii5/v6":
        problems.append(f"V6_DIR differs from the spec: {v6.V6_DIR}")
    expected_negatives = (
        "BIK", "KPP", "INN_LEGAL", "OGRN_LEGAL", "GRN_RECORD",
        "CORR_ACCOUNT", "LEGAL_ACCOUNT", "TREASURY_ACCOUNT", "KBK", "OKTMO",
        "SWIFT_ISIN", "PASSPORT_DEPT_CODE", "CADASTRAL_QUARTER", "FIAS_GUID",
        "ORG_OID", "VIN_MASK", "COURT_INDEX", "LAW_ARTICLE", "DOC_NUMBER",
        "GOST_STANDARD", "ORDER_NUMBER", "TRACK_S10", "TRACK_RU14", "SKU_17",
        "GTIN", "CONTRACT_B2B", "ICCID_M2M", "METRICA_COUNTER",
    )
    if v6.V6_NEGATIVE_FAMILIES != expected_negatives:
        problems.append(f"V6_NEGATIVE_FAMILIES differs from the spec: {v6.V6_NEGATIVE_FAMILIES}")
    if len(set(v6.V6_NEGATIVE_FAMILIES)) != 28:
        problems.append("V6_NEGATIVE_FAMILIES has duplicate values")
    return problems


def test_contracts_re_exports_the_home() -> list[str]:
    problems: list[str] = []
    if contracts.INDUSTRIES is not v6.INDUSTRIES:
        problems.append("contracts.INDUSTRIES is not the contracts_v6 tuple")
    if contracts.V6_AXES is not v6.V6_AXES:
        problems.append("contracts.V6_AXES is not the contracts_v6 tuple")
    if contracts.V6_PROVENANCE_KINDS is not v6.V6_PROVENANCE_KINDS:
        problems.append("contracts.V6_PROVENANCE_KINDS is not the contracts_v6 tuple")
    if contracts.V6_NEGATIVE_FAMILIES is not v6.V6_NEGATIVE_FAMILIES:
        problems.append("contracts.V6_NEGATIVE_FAMILIES is not the contracts_v6 tuple")
    if contracts.CaseV6Meta is not v6.CaseV6Meta:
        problems.append("contracts.CaseV6Meta is not the contracts_v6 class")
    return problems


def test_case_v6_meta_shape() -> list[str]:
    problems: list[str] = []
    meta = v6.CaseV6Meta(industry="retail", provenance="synthetic",
                         skeleton_ref="", procedure_ref="")
    if dataclasses.fields(v6.CaseV6Meta) != dataclasses.fields(meta):
        problems.append("CaseV6Meta round-trips with different fields")
    proc = v6.ProcedureRecord(doc_ref="https://example", steps=("a", "b"))
    if proc.steps != ("a", "b") or proc.doc_ref != "https://example":
        problems.append("ProcedureRecord does not hold its fields")
    return problems


CHECKS = (test_industries, test_axes_and_provenance,
          test_contracts_re_exports_the_home, test_case_v6_meta_shape)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_contracts_v6: PASS" if not failures else f"test_contracts_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
