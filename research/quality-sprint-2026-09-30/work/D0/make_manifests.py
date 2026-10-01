#!/usr/bin/env python3
"""Write D0's INPUTS.json and DELTA.json with hashes computed at write time.

Run from anywhere; writes only inside work/D0/. Kept next to the harness so the
manifests are reproducible rather than hand-copied numbers.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time

D0 = pathlib.Path(__file__).resolve().parent
SPRINT = D0.parents[1]
ROOT = SPRINT.parents[1]

ARTIFACTS = ["d0_arm_compare.py", "SPEC.md", "OPTIONS.md", "RUNBOOK-PERF.md",
             "MODEL-INVENTORY.json", "GATE.json", "smoke.log",
             "verify_evidence.py", "make_manifests.py",
             "out/arm-results.json", "out/arm-summary.tsv", "out/source-hashes.json"]
# verify.log is deliberately NOT hash-listed: it is the output of verify_evidence.py,
# which checks the hash list, so hashing it would make the manifest self-referential
# (the log's content depends on whether the hashes match).


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(rel: str) -> dict:
    p = D0 / rel
    return {"path": f"research/quality-sprint-2026-09-30/work/D0/{rel}",
            "bytes": p.stat().st_size, "sha256": sha(p)}


def main() -> int:
    results = json.loads((D0 / "out" / "arm-results.json").read_text(encoding="utf-8"))
    arms = results["results"]["arms"]
    slices = {m["slice"]: m for m in results["gold_slices"]}

    def totals(arm: str, sl: str) -> dict:
        return arms[arm]["per_slice"][sl]["totals"]

    def whole(c: dict) -> str:
        return f"{c.get('exact', 0) + c.get('whole_same_type', 0)}/{c.get('gold', 0)}"

    inputs = {
        "task": "D0",
        "title": "Comparable detector-mechanism experiment (isolated research harness)",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root": str(ROOT),
        "parent_gates": {
            "B0_G1": "PASS — local source/WIP/run/runtime scope only",
            "B0_evidence": ["work/B0/GATE.json", "work/B0/REVIEW.md",
                            "work/B0/INPUTS.json", "work/B0/RUNTIME.json"],
            "B0_production_digest": "NOT_VERIFIED (unchanged by D0)",
        },
        "authorization": {
            "first_wave_task": "work/FIRST-WAVE-TASKS.json:id=D0",
            "plan_rows": ["SPRINT-PLAN.md §6 D0", "SPRINT-PLAN.md §7 G3",
                          "GOAL-BRIEF.md §9 O-DETECT", "GOAL-BRIEF.md P15, P17"],
            "owner_decisions": {"Q4": "compare variants allowed; the choice is the owner's",
                                "block4": "best proven quality; real resource cost shown before adoption"},
            "write_scope": "research/quality-sprint-2026-09-30/work/D0/",
            "forbidden_and_honoured": [
                "no model download / install", "no provider or production call",
                "no PII to external inference", "no engine/scorer/benchmark/licensing edit",
                "no git reset/stash/revert or checkout", "no holdout read",
                "no paid-run directory read", "no broad secret-path search"],
        },
        "model_routing": {
            "requested_provider": "deepseek-official",
            "requested_model": "deepseek-flash",
            "effective_model": "NOT_AVAILABLE_FROM_RUNTIME",
            "note": ("runtime routing metadata was not exposed to this agent; no "
                     "self-identity attestation is made and no other model name is claimed"),
        },
        "revision": {
            "head": "890c50849a326f882eac336ba4e38c91171de473",
            "head_note": "evidence-only commit; product source remains pinned",
            "product_source_pin": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
            "branch": "research/hop-format-audit",
            "v6_ref": "fad9c7466ea1221282214e6c747ca373ee7e6a55",
        },
        "runtime": {
            "python": results["environment"]["python"],
            "executable": results["environment"]["executable"],
            "platform": results["environment"]["platform"],
            "PYTHONDONTWRITEBYTECODE": results["environment"]["PYTHONDONTWRITEBYTECODE"],
            "libraries": results["environment"]["libraries"],
            "installed_ner_capable": results["environment"]["installed_ner_capable"],
            "dev_bundle": "testkit.load_dev_bundle() in process, nothing written to disk",
        },
        "bundle": results["bundle"],
        "identity_cross_checks": {
            "source_pin_check_vs_B0": results["source_pin_check_vs_B0"],
            "note": ("63 hashed prototype/pseudex/*.py + prototype/licensing/*.py modules "
                     "match work/B0/INPUTS.json pins; drift 0"),
            "dictionaries": results["dictionaries"],
        },
        "gold_inputs": {
            "slices": results["gold_slices"],
            "files_hashed": results["gold_files_hashed"],
            "holdout": results["holdout"],
            "corpus_text_retention": ("no corpus or holdout text is stored in D0 outputs; "
                                      "arm-results.json holds only counters and spans of "
                                      "this agent's own synthetic control strings"),
        },
        "commands": [
            {"cmd": "prototype/.venv/bin/python -m py_compile work/D0/d0_arm_compare.py",
             "exit": 1, "outcome": "SyntaxError in the first draft; fixed before any measurement"},
            {"cmd": "... d0_arm_compare.py --max-cases 5 --out work/D0/out_check",
             "exit": 0, "outcome": "bounded sanity; controls passed; out_check removed"},
            {"cmd": "... d0_arm_compare.py --out work/D0/out (pre-dedupe instrument)",
             "exit": 0, "outcome": "overwritten; its counting unit was wrong (see DELTA.json)"},
            {"cmd": "... d0_arm_compare.py --out work/D0/out (deduped instrument)",
             "exit": 0, "outcome": "overwritten by the final run after the pin-check widening"},
            {"cmd": "cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "
                    "../research/quality-sprint-2026-09-30/work/D0/d0_arm_compare.py "
                    "--out ../research/quality-sprint-2026-09-30/work/D0/out",
             "exit": 0, "log": "work/D0/smoke.log",
             "outcome": "final run retained; 791 unique texts x 5 arms; controls passed"},
        ],
        "outputs": {a: describe(a) for a in ARTIFACTS if (D0 / a).exists()},
        "outputs_note": ("verify.log is present but not hash-listed because it is the "
                         "output of the self-check that validates this hash list"),
        "scope_compliance": {
            "files_written_outside_work_D0": [],
            "git_status_product_paths": "empty (verified with git status --porcelain on prototype/pseudex, prototype/licensing, testkit.py, dataset.json, dirty.json, bench/gate, bench/_baseline_independent.py)",
            "engine_source_modified": False,
            "scorer_or_benchmark_modified": False,
        },
        "limits": results["limits"],
        "production_digest": "NOT_VERIFIED",
        "paid_runs_authorized": False,
        "owner_gates": {"O-DETECT": "OWNER_PENDING"},
    }
    (D0 / "INPUTS.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=1),
                                    encoding="utf-8")

    per_slice = {}
    for sl in ("golden", "dirty", "gatectx"):
        base = totals("FULL", sl)
        per_slice[sl] = {
            "unit": slices[sl].get("slice"),
            "gold_units": base.get("gold", 0),
            "population": {
                "golden": "100 generated cases -> 298 unique (span,type) gold values",
                "dirty": "150 generated cases -> 134 unique gold values + 6 declared hard negatives",
                "gatectx": "587 unique hand-labelled occurrences (295 must-mask, 292 must-not)",
            }[sl],
            "baseline_arm": "FULL (product path)",
            "baseline_whole_same_type": whole(base),
            "baseline_char_coverage": round(base.get("covered_chars", 0)
                                           / max(1, base.get("gold_chars", 1)), 4),
            "baseline_fp": {k: base.get(k, 0) for k in
                            ("fp_other", "fp_place", "fp_public", "fp_declared")},
            "arms": {},
            "unknowns": ("no CI, no independence/cluster analysis, no approved acceptance "
                         "protocol: these are diagnostic counts, not G7 acceptance"),
        }
        for arm in ("RULES_ONLY", "HYBRID_UNION", "RAW_NER", "RAW_NER_REGEX"):
            c = totals(arm, sl)
            per_slice[sl]["arms"][arm] = {
                "is_ablation": True,
                "whole_same_type": whole(c),
                "char_coverage": round(c.get("covered_chars", 0)
                                       / max(1, c.get("gold_chars", 1)), 4),
                "wrong_type": c.get("wrong_type", 0),
                "miss": c.get("miss", 0),
                "pred": c.get("pred", 0),
                "fp": {k: c.get(k, 0) for k in
                       ("fp_other", "fp_place", "fp_public", "fp_declared")},
            }

    delta = {
        "task": "D0",
        "created_utc": inputs["created_utc"],
        "changed_files": [describe(a) for a in ARTIFACTS if (D0 / a).exists()],
        "change_type": "new evidence only — no product, scorer, benchmark, licensing, wiki or corpus file changed",
        "instrument_corrections": [
            {"defect": "occurrence rows counted instead of unique labelled keys",
             "effect": "gate numerator/denominator inflated (320 gold, 634 rows)",
             "fix": "dedupe by the instrument's own key (bench/gate/sheet.py:101)",
             "evidence": "out/arm-results.json:gold_slices[gatectx].duplicate_rows_skipped"},
            {"defect": "a prediction re-counted once per sibling occurrence in the same text",
             "effect": "prediction-side FP counts inflated",
             "fix": "gold items counted once per (span,type); predictions once per unique text",
             "evidence": "harness docstring evaluate(); SPEC.md §4"},
        ],
        "per_slice": per_slice,
        "evidence_mechanism_vs_measurement": {
            "mechanism_evidence": ("arm definitions (FULL = product path; RULES_ONLY = "
                                   "_ner_spans disabled subclass; RAW_NER = bare NewsNERTagger; "
                                   "HYBRID_UNION = union; RAW_NER_REGEX = bare NER + the naive "
                                   "regexes of bench/_baseline_independent.py) and the "
                                   "identical-input comparison performed by one harness"),
            "measurement": ("counters in out/arm-results.json and out/arm-summary.tsv; timings "
                            "are exploratory single-run numbers, not a p50/p95 and not an "
                            "admission budget"),
            "causality": "NOT CLAIMED — an ablation difference on this gold is not a causal claim about production",
        },
        "population_and_exclusions": {
            "excluded": "no paid run, no holdout, no external corpus; 2420 unlabelled gate occurrences skipped; 47 duplicate labelled rows deduped",
            "unknown": ["real-traffic precision", "CI/support", "p50/p95/RSS", "licence of natasha's weights"],
            "membership_delta": "none — D0 adds no corpus and changes no population",
        },
        "not_claimed": [
            "architecture choice", "production quality", "causal effect of any component",
            "raw Natasha as a replacement", "p50/p95/RSS", "entire-sprint quality green",
            "paid or live GO", "production artifact verified",
        ],
        "owner_gates": {"O-DETECT": "OWNER_PENDING"},
    }
    (D0 / "DELTA.json").write_text(json.dumps(delta, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print("wrote INPUTS.json, DELTA.json")
    for a in ARTIFACTS:
        p = D0 / a
        if p.exists():
            print(f"  {a:<28} {p.stat().st_size:>8} B  {sha(p)[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
