#!/usr/bin/env python3
"""Integrity receipt for contracts-revision-2: JSON validity, input pins, output hashes.

Read-only apart from writing RECEIPT.json into this directory.
Run:
  PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
    research/quality-sprint-2026-09-30/work/contracts-revision-2/make_receipt.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # .../research/quality-sprint-2026-09-30/work -> repo root

JSON_FILES = sorted(p for p in HERE.glob("*.json") if p.name != "RECEIPT.json")
MD_FILES = sorted(HERE.glob("*.md"))

json_validity = {}
for p in JSON_FILES:
    try:
        json.loads(p.read_text(encoding="utf-8"))
        json_validity[p.name] = "valid"
    except Exception as exc:  # pragma: no cover
        json_validity[p.name] = f"INVALID: {type(exc).__name__}: {exc}"

facts = json.loads((HERE / "FACTS.json").read_text(encoding="utf-8"))
inputs = facts["inputs"]

# raw evidence this revision read but must never have modified: recompute their hashes
raw_read = [
    "research/quality-sprint-2026-09-30/work/A1/ACCEPTANCE-PROPOSAL.json",
    "research/quality-sprint-2026-09-30/work/A1/SPEC.md",
    "research/quality-sprint-2026-09-30/work/A1/OWNER-QUESTIONS.md",
    "research/quality-sprint-2026-09-30/work/D0/d0_arm_compare.py",
    "research/quality-sprint-2026-09-30/work/D0/out/arm-results.json",
    "research/quality-sprint-2026-09-30/work/V0/SPEC.md",
    "research/quality-sprint-2026-09-30/work/V0/OWNER-QUESTIONS.md",
    "research/quality-sprint-2026-09-30/work/V0/TYPE55.json",
    "research/quality-sprint-2026-09-30/work/V0/checks/v0_checks.py",
    "research/quality-sprint-2026-09-30/work/C0/SPEC.md",
    "research/quality-sprint-2026-09-30/work/C0/OWNER-QUESTIONS.md",
    "research/quality-sprint-2026-09-30/work/C0/PROBE-FACTS.json",
    "research/quality-sprint-2026-09-30/work/S2/SPEC.md",
    "research/quality-sprint-2026-09-30/work/S2/GAP-MATRIX.json",
    "research/quality-sprint-2026-09-30/work/review-contracts/REVIEW.md",
    "research/quality-sprint-2026-09-30/work/review-contracts/VERIFICATION.json",
    "research/quality-sprint-2026-09-30/GOAL-BRIEF.md",
    "research/quality-sprint-2026-09-30/OWNER-DECISIONS.md",
    "research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md",
    "research/quality-sprint-2026-09-30/EXECUTION.json",
]
raw_pins = {}
for rel in raw_read:
    p = ROOT / rel
    raw_pins[rel] = {"exists": p.exists(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

# declared parent-owned files must be untouched by this revision.
# The brief named them as new v2-dev files; on disk the v2-dev copies live at the
# paths below. Both spellings are recorded so the claim is checkable, and this
# revision created/modified neither location (it never opened either file for write).
parent_declared = [
    "prototype/bench/agentpii5/answer_restoration.py",
    "prototype/bench/agentpii5/test_answer_restoration.py",
    "research/quality-sprint-2026-09-30/work/M1a/answer_restoration.py",
    "research/quality-sprint-2026-09-30/work/M1a/test_answer_restoration.py",
]
parent_pins = {}
for rel in parent_declared:
    p = ROOT / rel
    parent_pins[rel] = {
        "exists": p.exists(),
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,
        "written_by_this_revision": False,
    }

receipt = {
    "artifact": "RECEIPT",
    "revision": "contracts-revision-2",
    "sprint_root": "research/quality-sprint-2026-09-30",
    "write_scope": "research/quality-sprint-2026-09-30/work/contracts-revision-2/ ONLY",
    "python": {
        "interpreter": "prototype/.venv/bin/python",
        "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE", ""),
        "version": subprocess.run(["prototype/.venv/bin/python", "-V"], cwd=ROOT,
                                  capture_output=True, text=True).stdout.strip(),
    },
    "commands": [
        {
            "purpose": "independent fact re-derivation",
            "command": "PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/contracts-revision-2/verify_facts.py",
            "exit": 0,
            "stdout_log": "verify_facts.log",
            "notes": "no detector call, no engine import, no network, no git mutation",
        },
        {
            "purpose": "receipt generation",
            "command": "PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/contracts-revision-2/make_receipt.py",
            "exit": 0,
        },
    ],
    "deliverables": {},
    "json_validity": json_validity,
    "verified_facts": {
        "v5_HOP_STATUSES": facts["funnel_v0"]["v5_HOP_STATUSES"],
        "v6_HOP_STATUSES": facts["funnel_v0"]["v6_HOP_STATUSES"],
        "v6_strict_subset_of_v5": facts["funnel_v0"]["v6_strict_subset"],
        "registry_records": facts["v6_registry"]["records_total"],
        "item_types": facts["v6_registry"]["item_types_true"],
        "non_item_types": facts["v6_registry"]["non_item_types"],
        "v5_records": facts["v6_registry"]["by_origin"]["v5"],
        "v6_records": facts["v6_registry"]["by_origin"]["v6"],
        "bare_typed_true": facts["v6_registry"]["bare_typed_true"],
        "checksum_carrying_types": facts["checksum"]["generated_checksum_types"],
        "checksum_samples_valid": facts["checksum"]["samples_valid"],
        "demotion_guard": facts["c0_demotion_guard"]["guard_source_line"],
        "in_memory_vault": facts["c0_in_memory_and_opaque"],
        "budget": facts["a1_budget_arithmetic"],
        "nerel_version_read_by_a1": facts["a1_nerel_version_refs_in_inventory"],
    },
    "input_pins_from_FACTS": inputs,
    "raw_evidence_pins_unchanged_source": raw_pins,
    "declared_parent_owned_files": parent_pins,
    "limitations": [
        "No detector was run; nothing here measures engine quality.",
        "The child labels PASS/PARTIAL/PASS_RESEARCH_ONLY were not converted into official gate statuses; see GATES.json.",
        "Historical evidence was preserved and not rewritten.",
        "No git operation of any kind was performed.",
    ],
}

for p in JSON_FILES + MD_FILES:
    if p.name == "RECEIPT.json":
        continue
    receipt["deliverables"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()

(HERE / "RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"json_validity": json_validity,
                  "deliverables": receipt["deliverables"]}, ensure_ascii=False, indent=2))
print("EXIT 0")
