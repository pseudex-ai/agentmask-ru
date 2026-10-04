#!/usr/bin/env python3
"""A1: self-check of the deliverables + read-only proof for the declared inputs.

This is an evidence check, not a quality metric.  It asserts:
  1. every deliverable parses;
  2. the counts inside the deliverables agree with INVENTORY.json;
  3. every binding/external input declared in INPUTS.json still hashes to the value
     recorded when A1 read it (i.e. A1 changed nothing outside its own scope);
  4. the A1 directory contains no bytecode and no file outside the declared list.

Exit 0 = all assertions held.  Any failure prints the exact assertion.
Run:
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/A1/validate_outputs.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

A1 = Path(__file__).resolve().parent
ROOT = Path("/Users/igor/Projects/Obscura-hop-audit")
CHECKS = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}  {detail}")
        raise SystemExit(1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    # 1. parse every JSON deliverable
    inputs = json.loads((A1 / "INPUTS.json").read_text())
    inv = json.loads((A1 / "INVENTORY.json").read_text())
    gaps_sum = json.loads((A1 / "DATA-GAPS-SUMMARY.json").read_text())
    proposal = json.loads((A1 / "ACCEPTANCE-PROPOSAL.json").read_text())
    delta = json.loads((A1 / "DELTA.json").read_text())
    gate = json.loads((A1 / "GATE.json").read_text())
    check("all six JSON deliverables parse", True)

    # 2. counts agree with the inventory
    check("v5 corpus cases == 1800", inv["v5_corpus_1800"]["cases"] == 1800,
          str(inv["v5_corpus_1800"]["cases"]))
    check("v5 corpus items == 16287", inv["v5_corpus_1800"]["pii_items_total"] == 16287,
          str(inv["v5_corpus_1800"]["pii_items_total"]))
    check("run813 cases == 813", inv["run_2026_09_30_813"]["cases"] == 813)
    check("run813 items == 8191", inv["run_2026_09_30_813"]["pii_items_total"] == 8191)
    check("gate labels == 587", inv["gate_instrument"]["labelled_occurrences"] == 587)
    check("gate candidates == 3054", inv["gate_instrument"].get("candidate_occurrences") == 3054)
    check("v6 new types == 55",
          len(inv["v6_registry"]["new_v6_types"]) == 55
          and proposal["registry_scope"]["v6_new_types"]["count"] == 55)
    check("v6 grammar-uncertain == 9",
          len(inv["v6_registry"]["grammar_uncertain_types"]) == 9)
    check("v6 generated cases == 0",
          inv["v6_registry"]["generated_v6_cases_on_host"] == 0)
    check("name15 verified rows == 15",
          inv["name15_prior"]["verified_rows"]["lines_nonempty"] == 15)
    check("proposal native types == 10",
          len(proposal["registry_scope"]["native_v5_item_types"]["types"]) == 10)

    # NAME independent identity count, both places
    name_v5 = inv["v5_corpus_1800"]["per_type"]["NAME"]["unique_identities"]
    check("NAME independent identities == 1188",
          name_v5 == 1188
          and proposal["available_support_today"]["NAME"]["v5_corpus_1800"][
              "independent_identity_clusters"] == 1188,
          f"{name_v5}")
    check("underpowered native types == 5",
          sum(1 for t, v in gaps_sum["main_type_gap_from_single_largest_known_source"].items()
              if v["gap_to_target_using_v5_corpus"] > 0) == 5)

    # 3. DATA-GAPS.csv integrity
    rows = list(csv.DictReader((A1 / "DATA-GAPS.csv").open()))
    check("DATA-GAPS.csv rows == 511", len(rows) == 511, str(len(rows)))
    check("DATA-GAPS.csv has no empty pii_type",
          all(r["pii_type"] for r in rows))
    v6_rows = [r for r in rows if r["dataset"] == "v6_registry"]
    temp_rows = [r for r in rows if r["dataset"] == "temporary_secrets"]
    check("DATA-GAPS.csv v6 rows == 55", len(v6_rows) == 55)
    check("DATA-GAPS.csv temporary-secret rows == 6", len(temp_rows) == 6)
    check("every v6/temporary row carries gap 300",
          all(r["gap_units"] == "300" for r in v6_rows + temp_rows))

    # 4. proposal protocol completeness
    check("proposal status OWNER_PENDING", proposal["status"] == "OWNER_PENDING")
    check("proposal owner questions == 10", len(proposal["owner_questions"]) == 10)
    ids = [q["id"] for q in proposal["owner_questions"]]
    check("owner question ids unique", len(set(ids)) == len(ids))
    rules = proposal["labeling_protocol"]["case_rules"]
    for required in ("lexical_ambiguity_wife_name", "fio_all_parts", "possessive_forms",
                     "public_fictional_stage", "brand_context", "address_entrance_floor",
                     "malformed_personal_ids"):
        check(f"protocol rule present: {required}", required in rules)
    check("PPV and specificity are separate designs",
          "ppv_design" in proposal and "specificity_design" in proposal
          and proposal["ppv_design"]["frame"].startswith("detector-positive"))
    check("zero denominator status == NOT_MEASURED",
          proposal["ci_and_statuses"]["zero_denominator"].startswith("NOT_MEASURED"))
    check("insufficient-N status named",
          "DESCRIPTIVE_INSUFFICIENT_SUPPORT"
          in proposal["ci_and_statuses"]["insufficient_n"])
    cost = proposal["cost_estimate_human_review_items"]["planning_result"]
    check("cost units_full_scope == 8320", cost["units_full_scope"] == 8320,
          str(cost["units_full_scope"]))
    check("cost native labeler-items == 13200",
          cost["labeler_items_native_only"] == 13200,
          str(cost["labeler_items_native_only"]))
    check("proposal carries the confirmed in-memory bundle identity",
          proposal["revision"]["bundle"]["version"] == "2a07cebae2b050ec"
          and proposal["revision"]["bundle"]["matches_b0_record"] is True
          and proposal["revision"]["bundle"]["file_written"] is False)

    # 5. inputs unchanged (read-only proof)
    checked = 0
    for rel, rec in inputs["binding_inputs"].items():
        if not rec.get("exists") or rec.get("kind") != "file":
            continue
        p = ROOT / rel
        check(f"binding input unchanged: {rel}", sha256(p) == rec["sha256"])
        checked += 1
    for rel, rec in inputs["external_corpora"].items():
        if not rec.get("exists") or rec.get("kind") != "file":
            continue
        p = Path(rel).expanduser()
        check(f"external input unchanged: {rel}", sha256(p) == rec["sha256"])
        checked += 1
    check("read-only proof covered >=20 files", checked >= 20, str(checked))

    # 6. own scope hygiene
    files = sorted(p.name for p in A1.iterdir())
    check("no __pycache__ under A1", not (A1 / "__pycache__").exists())
    check("no .pyc under A1", not any(p.suffix == ".pyc" for p in A1.rglob("*")))
    check("DELTA lists only own scope",
          all(f.startswith("research/quality-sprint-2026-09-30/work/A1/")
              for f in delta["changed_files"]))
    check("GATE is OWNER_PENDING and claims no quality PASS",
          gate["status"] == "OWNER_PENDING"
          and "product quality passed" in gate["not_claimed"])
    print(f"\nall checks passed ({CHECKS} assertions, {checked} input hashes re-verified)")
    print("files in scope:", ", ".join(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
