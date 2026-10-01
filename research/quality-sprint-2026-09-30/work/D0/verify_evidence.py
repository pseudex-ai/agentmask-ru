#!/usr/bin/env python3
"""D0 self-check: gate numbers vs the retained raw run, hashes vs files on disk.

This is a SELF-check, not the independent review (GATE.json:independent_review is
NOT_RUN). It exists so the Lead's reviewer starts from a machine-checked state:
every number GATE.json claims is re-derived here from out/arm-results.json and the
files themselves. Exit 0 = all assertions hold; 1 = at least one mismatch.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

D0 = pathlib.Path(__file__).resolve().parent
failures: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        failures.append(label)


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


res = json.loads((D0 / "out" / "arm-results.json").read_text(encoding="utf-8"))
gate = json.loads((D0 / "GATE.json").read_text(encoding="utf-8"))
inputs = json.loads((D0 / "INPUTS.json").read_text(encoding="utf-8"))
delta = json.loads((D0 / "DELTA.json").read_text(encoding="utf-8"))
inv = json.loads((D0 / "MODEL-INVENTORY.json").read_text(encoding="utf-8"))
sh = json.loads((D0 / "out" / "source-hashes.json").read_text(encoding="utf-8"))

print("== identity ==")
check(sha(D0 / "d0_arm_compare.py") == res["harness_sha256"],
      "harness sha256 matches the retained run")
check(gate["revision"]["harness_sha256"] == res["harness_sha256"],
      "GATE harness sha256 matches the retained run")
check(res["bundle"]["sha256"]
      == "01c19f4689450b54694b7aaa4070cbaf695efc3e98f0b59471486392a0348206",
      "bundle sha256 equals B0 RUNTIME identity")
check(res["bundle"]["vs_B0_RUNTIME"] == {"version_match": True, "sha256_match": True,
                                         "bytes_match": True}, "bundle cross-check vs B0")
pc = res["source_pin_check_vs_B0"]
check(pc["compared"] == 63 and pc["match"] == 63 and pc["drift"] == [],
      "63/63 module pins match B0 with no drift")

print("== gold population ==")
meta = {m["slice"]: m for m in res["gold_slices"]}
check(meta["golden"]["cases"] == 100 and meta["golden"]["unresolved_gold_values"] == 0,
      "golden: 100 cases, 0 unresolved gold values")
check(meta["dirty"]["cases"] == 150 and meta["dirty"]["unresolved_gold_values"] == 0,
      "dirty: 150 cases, 0 unresolved gold values")
check(meta["gatectx"]["labelled_used"] == 587
      and meta["gatectx"]["duplicate_rows_skipped"] == 47
      and meta["gatectx"]["unlabelled_skipped"] == 2420,
      "gatectx: 587 unique labelled rows (47 duplicates dropped, 2420 unlabelled)")
check(meta["gatectx"]["label_counts"] == {"person": 271, "address": 24, "other": 209,
                                          "place": 26, "public": 57},
      "gatectx label counts = 295 must-mask + 292 must-not")
check(res["holdout"]["used"] is False and res["holdout"]["file_present"] is False,
      "holdout not read and not present")

print("== controls ==")
ctl = res["results"]["instrument_controls"]
check(ctl["positive"]["pass"] and len(ctl["positive"]["spans"]) == 2,
      "positive control passed with 2 spans")
check(ctl["negative"]["pass"], "negative control passed")

print("== headline counters ==")
arms = res["results"]["arms"]


def t(arm: str, sl: str) -> dict:
    return arms[arm]["per_slice"][sl]["totals"]


check(t("FULL", "golden").get("gold") == 298 and t("FULL", "golden").get("miss", 0) == 0,
      "FULL golden: 298 gold, 0 miss")
check(t("FULL", "golden").get("exact") == 266 and t("FULL", "golden").get("whole_same_type") == 20,
      "FULL golden: 266 exact + 20 whole = 286/298")
check(t("FULL", "gatectx").get("gold") == 295 and t("FULL", "gatectx").get("negatives") == 292,
      "FULL gatectx: 295 gold / 292 labelled negatives")
check(t("RULES_ONLY", "golden").get("miss") == 18, "RULES_ONLY golden: 18 LOC misses")
check(t("RULES_ONLY", "gatectx") == t("FULL", "gatectx"),
      "RULES_ONLY gatectx totals identical to FULL (per-text spec)")
check(t("RAW_NER", "gatectx").get("miss") == 295, "RAW_NER gatectx: 295/295 miss")
check(arms["RAW_NER"]["is_ablation"] and arms["HYBRID_UNION"]["is_ablation"]
      and arms["RULES_ONLY"]["is_ablation"] and not arms["FULL"]["is_ablation"],
      "ablation flags correct (FULL is the only product arm)")
check(all(v["unique_texts"] == 791 for v in arms.values()),
      "791 unique texts per arm")

print("== gate/inputs/delta consistency ==")
check(gate["checks"]["gold_units"] == {"golden": 298, "dirty": 134, "gatectx": 295},
      "GATE gold units match the run")
check(gate["checks"]["arms_executed"] == len(arms)
      and gate["checks"]["unique_texts_per_arm"] == 791,
      "GATE arm/text counts match the run")
check(gate["owner_gate"]["status"] == "OWNER_PENDING"
      and gate["production_artifact_gate"]["status"] == "NOT_MEASURED",
      "O-DETECT OWNER_PENDING and production NOT_MEASURED")
check(delta["owner_gates"]["O-DETECT"] == "OWNER_PENDING", "DELTA owner gate consistent")
bad = [a for a, row in inputs["outputs"].items()
       if not (D0 / a).exists() or sha(D0 / a) != row["sha256"]]
check(not bad, f"INPUTS.json artifact hashes match files on disk ({bad})")
bad = []
for row in delta["changed_files"]:
    rel = pathlib.Path(row["path"]).relative_to(
        "research/quality-sprint-2026-09-30/work/D0")
    if not (D0 / rel).exists() or sha(D0 / rel) != row["sha256"]:
        bad.append(row["path"])
check(not bad, f"DELTA.json artifact hashes match files on disk ({bad})")
check(inv["engine_used_for_baseline"]["bundle_matches_B0_RUNTIME"] is True,
      "MODEL-INVENTORY bundle flag consistent")
check(all(not m["exists"] or len(m["sha256"]) == 64 for m in sh["models"]),
      "source-hashes.json model digests are full sha256")

print("== log ==")
log = (D0 / "smoke.log").read_text(encoding="utf-8")
check("EXIT=0" in log and "DRIFT" not in log, "smoke.log shows EXIT=0")

print()
if failures:
    print(f"SELF-CHECK FAILED: {len(failures)} assertion(s)")
    sys.exit(1)
print("SELF-CHECK PASSED: all assertions hold")
sys.exit(0)
