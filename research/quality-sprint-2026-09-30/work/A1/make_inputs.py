#!/usr/bin/env python3
"""A1: build INPUTS.json — exact revision, source pointers, hashes, gates, model routing.

Read-only.  The bundle is rebuilt IN MEMORY only (no file written) to confirm the B0
identity independently of the B0 record; the production digest is NOT touched and stays
NOT_VERIFIED for RG, exactly as B0/REVIEW.md states.

Run:
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/A1/make_inputs.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

A1 = Path(__file__).resolve().parent
ROOT = Path("/Users/igor/Projects/Obscura-hop-audit")

BINDING = [
    "research/quality-sprint-2026-09-30/work/B0/GATE.json",
    "research/quality-sprint-2026-09-30/work/B0/REVIEW.md",
    "research/quality-sprint-2026-09-30/work/B0/SPEC.md",
    "research/quality-sprint-2026-09-30/work/B0/INPUTS.json",
    "research/quality-sprint-2026-09-30/GOAL-BRIEF.md",
    "research/quality-sprint-2026-09-30/OWNER-DECISIONS.md",
    "research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md",
    "research/quality-sprint-2026-09-30/SPRINT-PLAN.md",
    "research/quality-sprint-2026-09-30/EXECUTION.json",
    "research/quality-sprint-2026-09-30/work/FIRST-WAVE-TASKS.json",
    "research/quality-sprint-2026-09-30/work/FIRST-WAVE-SCOPES.md",
    "research/quality-sprint-2026-09-30/followup/name-labels-blind-proposal/proposal-counts.json",
    "research/quality-sprint-2026-09-30/followup/cvc-context-contract/CONTEXT-MATRIX.json",
    "research/quality-sprint-2026-09-30/followup/cvc-context-contract/PRIMARY-SOURCES.md",
    "research/hop-format-audit/next-sprint-review/v6-snapshot/registry-inventory.json",
    "research/hop-format-audit/next-sprint-review/v6-snapshot/tz-agentpii6.md",
    "prototype/bench/agentpii5/corpus.v5.json",
    "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/corpus.json",
    "prototype/bench/gate/labels.json",
    "prototype/bench/gate/README.md",
    "wiki/INVARIANTS.md",
]

EXTERNAL = [
    ("~/.cache/pseudex-bench/nerel/NEREL-v1.1", "dir"),
    ("~/.cache/pseudex-bench/pii-bench/data/domain-00000-of-00001.parquet", "file"),
    ("~/.cache/pseudex-bench/pii-bench/data/entity-00000-of-00001.parquet", "file"),
    ("~/.cache/pseudex-bench/massive_ru_train.parquet", "file"),
    ("~/.cache/pseudex-bench/massive_ru_validation.parquet", "file"),
    ("~/.cache/pseudex-bench/massive_ru_test.parquet", "file"),
    ("~/.cache/pseudex-bench/voice_addresses.json", "file"),
    ("~/.cache/pseudex-bench/rudevices_addresses.json", "file"),
    ("~/.cache/pseudex-bench/speech_calls.jsonl", "file"),
    ("~/.cache/pseudex-bench/speech_rudevices.jsonl", "file"),
    ("~/.cache/pseudex-bench/gate_candidates.json", "file"),
    ("~/.cache/pseudex-bench/ru_prose.jsonl", "file"),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(args: list[str]) -> str:
    p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return p.stdout.strip()


def record(rel_or_abs: str) -> dict:
    p = Path(rel_or_abs).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return {"path": rel_or_abs, "exists": False}
    if p.is_dir():
        n = sum(1 for _ in p.rglob("*") if _.is_file())
        return {"path": rel_or_abs, "exists": True, "kind": "dir", "files": n}
    return {"path": rel_or_abs, "exists": True, "kind": "file",
            "bytes": p.stat().st_size, "sha256": sha256(p)}


def bundle_identity() -> dict:
    sys.path.insert(0, str(ROOT / "prototype"))
    try:
        from licensing.pack import build_payload, build_plaintext  # type: ignore

        payload = build_payload()
        plain = build_plaintext("", "")
        return {
            "recomputed_in_memory": True,
            "version": payload["version"],
            "plaintext_bytes": len(plain),
            "sha256": hashlib.sha256(plain).hexdigest(),
            "matches_b0_record": (
                payload["version"] == "2a07cebae2b050ec"
                and hashlib.sha256(plain).hexdigest()
                == "01c19f4689450b54694b7aaa4070cbaf695efc3e98f0b59471486392a0348206"
            ),
            "file_written": False,
        }
    except Exception as exc:  # pragma: no cover - reported, never hidden
        return {"recomputed_in_memory": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    b0 = json.loads((ROOT / "research/quality-sprint-2026-09-30/work/B0/GATE.json").read_text())
    inv = json.loads((A1 / "INVENTORY.json").read_text())
    out = {
        "task": "A1",
        "wave": "quality-sprint-design-red-1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "write_scope": "research/quality-sprint-2026-09-30/work/A1/",
        "requested_routing": {
            "provider": "deepseek-official",
            "model": "deepseek-flash",
            "mechanism": "explicit provider/model override requested by the Lead",
            "effective_routing_metadata": (
                "NOT AVAILABLE to this subagent from inside its own run; claimed model "
                "identity is not technical evidence (REVIEW.md:9 precedent). "
                "Authoritative record belongs to the Lead's SUBAGENT-USAGE journal, "
                "which A1 must not edit."
            ),
            "self_identity_attested": False,
        },
        "revision": {
            "git_head_current": git(["rev-parse", "HEAD"]),
            "git_branch_current": git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "product_source_pin": b0["source_head"],
            "product_source_pin_note": (
                "0bfda2363ef1a1d552e2ac093129b1026a86ad68 is the pinned product source; "
                "current HEAD 890c508 is research-only evidence per the task and B0."
            ),
            "porcelain_lines": len(git(["status", "--porcelain"]).splitlines()),
            "no_git_mutation_performed": True,
        },
        "gates_inherited": {
            "B0_G1_local_design": {"status": b0["gate"], "record": "work/B0/GATE.json",
                                   "scope": b0["scope"], "checks": b0["checks"]},
            "B0_review": {"path": "work/B0/REVIEW.md",
                          "verdict": "PASS for local/design G1 only; production NOT_VERIFIED"},
            "production_artifact_gate": b0["production_artifact_gate"],
            "paid_runs_authorized": b0["paid_runs_authorized"],
        },
        "bundle": bundle_identity(),
        "bundle_b0_record": b0["bundle"],
        "environment": inv["environment"],
        "binding_inputs": {r: record(r) for r in BINDING},
        "external_corpora": {r: record(r) for r, _kind in EXTERNAL},
        "executed_commands": [
            {"cmd": "PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python "
                    "work/A1/inventory_sources.py", "exit": 0,
             "log": "work/A1/INVENTORY.log", "out": "work/A1/INVENTORY.json"},
            {"cmd": "PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python "
                    "work/A1/derive_gaps.py", "exit": 0,
             "log": "work/A1/DERIVE.log", "out": "work/A1/DATA-GAPS.csv"},
        ],
        "scope_forbidden": [
            "no engine/licensing/scorer/benchmark/corpus/git writes",
            "no detector prediction, eval, score, hop or judge artifact read",
            "no downloads, installs, model training, provider/benchmark calls",
            "no EXECUTION.json or SUBAGENT-USAGE journal edit",
            "no final gold produced by this task",
        ],
        "not_claimed": [
            "no O-DATA acceptance",
            "no product quality result",
            "no production verification",
            "no G7/G11 implication",
            "prior name-label proposal is not accepted gold",
        ],
    }
    (A1 / "INPUTS.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("revision", "bundle", "gates_inherited")},
                     ensure_ascii=False, indent=2))
    print(f"wrote {A1 / 'INPUTS.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
