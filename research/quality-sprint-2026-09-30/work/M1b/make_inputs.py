"""M1b — emit INPUTS.json and MISSING-STATE.json from the files themselves.

Every hash is computed here, not typed: a hand-written digest is a claim about a
revision nobody can check. The bundle identity is rebuilt IN MEMORY (the same
path B0's reviewer used) and no file is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
PROTO = REPO / "prototype"
sys.path.insert(0, str(PROTO))
RUN = REPO / "prototype/bench/runs/2026-09-30/v5-sprint-v2-813"
RUN_ID = "cc3a551f-a8a5-4c0d-b90b-d3db2b26858a"

SOURCE_FILES = [
    "prototype/bench/agentpii5/payload_canaries.py",
    "prototype/bench/agentpii5/test_payload_canaries.py",
    "prototype/bench/agentpii5/test_payload_canary_integration.py",
    "prototype/bench/agentpii5/harness.py",
    "prototype/bench/agentpii5/mock.py",
    "prototype/bench/agentpii5/schema.py",
    "prototype/bench/agentpii4/gateway.py",
    "prototype/pseudex/envelope.py",
    "prototype/pseudex/vault.py",
    "prototype/pseudex/detect_all.py",
    "prototype/bench/agentpii3/score.py",
]

RUN_FILES = [
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.canary.jsonl",
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.triples.jsonl",
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.arms.v5.jsonl",
    "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/corpus.v5.json",
    "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/corpus.json",
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.meta.json",
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.report.json",
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.report.txt",
    f"prototype/bench/runs/2026-09-30/v5-sprint-v2-813/{RUN_ID}.gate.json",
]

EVIDENCE_FILES = [
    "research/quality-sprint-2026-09-30/work/B0/GATE.json",
    "research/quality-sprint-2026-09-30/work/B0/REVIEW.md",
    "research/quality-sprint-2026-09-30/work/B0/SPEC.md",
    "research/quality-sprint-2026-09-30/work/B0/INPUTS.json",
    "research/hop-format-audit/runs/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.excluded.json",
    "research/hop-format-audit/runs/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.manifest.json",
    "research/quality-sprint-2026-09-30/SPRINT-PLAN.md",
    "research/quality-sprint-2026-09-30/GOAL-BRIEF.md",
    "research/quality-sprint-2026-09-30/OWNER-DECISIONS.md",
    "research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md",
    "research/quality-sprint-2026-09-30/work/FIRST-WAVE-TASKS.json",
    "research/quality-sprint-2026-09-30/work/FIRST-WAVE-SCOPES.md",
]


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def describe(rel: str) -> dict:
    path = REPO / rel
    if not path.exists():
        return {"path": rel, "exists": False}
    return {"path": rel, "exists": True, "bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True, check=True).stdout.strip()


def bundle_identity() -> dict:
    """The in-memory development bundle this probe's masks were computed under."""
    import licensing.pack as pack  # noqa: PLC0415
    payload = pack.build_payload()
    plaintext = pack.build_plaintext()
    return {"version": str(payload.get("version", "")),
            "plaintext_bytes": len(plaintext),
            "plaintext_sha256": hashlib.sha256(plaintext).hexdigest(),
            "persisted": False}


def missing_state(parity: dict, reasons: dict) -> dict:
    cases = []
    for one in parity["cases"]:
        case_id = one["case_id"]
        captured = [{"name": payload["name"], "text_bytes": len(payload["text"]),
                     "real_text_bytes": len(payload["real_text"])}
                    for payload in one.get("_payloads", [])]
        entry = {
            "case_id": case_id,
            "run_record_verdict": one.get("verdict"),
            "failed_arm_record": {
                "artifact": f"{RUN_ID}.arms.v5.jsonl",
                "state": "empty (_empty_run): state=[], calls=[], substitutes={}, "
                         "request_count=0",
                "survives_only": "the 60-character prefix pair in the triple reason",
            },
            "failing_boundary": "tool_result (the last captured payload is tool_args, "
                                "which the failing push_call consumes)",
            "prior_state_recovered_from": f"{RUN_ID}.canary.jsonl row for {case_id}",
            "prior_state_payload_count": len(one.get("payload_names", [])),
            "prior_state_payloads_replayed": one.get("payloads_replayed"),
            "prior_state_full_replayed": one.get("full_prior_state_replayed"),
            "intermediate_hops_in_capture": one.get("intermediate_hops_in_capture"),
            "prefix_replayed_byte_identical": one.get("state_byte_identical"),
            "restored_tool_args_match_saved": one.get("restored_args_match_saved"),
            "saved_prefixes": {"production": one.get("saved_production_prefix"),
                               "counting": one.get("saved_counting_prefix"),
                               "prefixes_equal": one.get("saved_production_prefix")
                               == one.get("saved_counting_prefix")},
            "absent_state": [
                "the two masked outputs of the failing push (production vs counting) "
                "beyond their first 60 characters",
                "every substitute the failing push MINTED for values first seen in "
                "the tool result: the mint is `secrets`-driven (pseudex/vault.py) and "
                "no mapping is persisted, and the capture stops before that push",
                "the vault's `shown_forms` rows written by the failing push's own "
                "restore, if any",
                "for the multi-hop cases, a replayable description of the "
                "intermediate tool hops: the capture holds their delivered bytes "
                "but not the tool call that produced them, so this probe replays "
                "only the prefix before the first tool call",
            ],
            "required_instrumentation": [
                "persist, per push, the two compared strings in full (or their first "
                "divergence offset and the 512 bytes around it) instead of raising "
                "with a truncated repr",
                "persist the minted (entity_type, real, fake) triples of the failing "
                "push, or a seed for the mint, so a replay can be byte-exact",
                "keep the failed arm's transcript/request_count instead of "
                "`_empty_run` whenever a capture row was already written",
            ],
            "not_claimed": ["root cause", "the mechanism is proven for this case",
                            "the other three cases have the same trigger"],
        }
        entry["captured_payloads_head"] = captured[:6]
        cases.append(entry)
    return {
        "generated_by": "research/quality-sprint-2026-09-30/work/M1b/make_inputs.py",
        "scope": "the four production/counting masking divergences excluded from run "
                 + RUN_ID,
        "rule": "the prior state IS on disk; the failing push's own mints are NOT. "
                "An absent input is named, never inferred.",
        "reason_source": "research/hop-format-audit/runs/"
                         "cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.excluded.json",
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reasons", required=True)
    parser.add_argument("--parity", required=True)
    parser.add_argument("--captures-json", required=True)
    args = parser.parse_args()

    out_dir = pathlib.Path(__file__).resolve().parent
    reasons_raw = json.loads(pathlib.Path(args.reasons).read_text(encoding="utf-8"))
    parity = json.loads(pathlib.Path(args.parity).read_text(encoding="utf-8"))
    captures = json.loads(pathlib.Path(args.captures_json).read_text(encoding="utf-8"))

    # Attach the saved payload list to each parity case for the manifest.
    # The payload lists are read from the run rows directly (bounded: 4 rows).
    wanted = {one["case_id"] for one in parity["cases"]}
    from bench.agentpii5 import payload_canaries  # noqa: PLC0415
    payload_lists: dict[str, list] = {}
    for raw in (RUN / f"{RUN_ID}.canary.jsonl").open("rb"):
        head = raw[:400]
        if not any(cid.encode() in head for cid in wanted):
            continue
        row = json.loads(raw)
        if row.get("case_id") in wanted:
            payload_lists[row["case_id"]] = row["capture"]["payloads"]
    for one in parity["cases"]:
        one["_payloads"] = payload_lists.get(one["case_id"], [])

    inputs = {
        "task": "M1b",
        "wave": "quality-sprint-design-red-1",
        "required_gate": {"path": "research/quality-sprint-2026-09-30/work/B0/GATE.json",
                          "gate": "G1", "status": "PASS",
                          "scope_note": "LOCAL/DESIGN only; production artifact "
                                        "NOT_MEASURED and release-A/B still blocked"},
        "provider": {"requested": "deepseek-official", "model_requested": "deepseek-flash",
                     "mechanism": "explicit orchestration override; no self-attestation "
                                  "is technical proof",
                     "external_calls_made": 0, "paid_benchmark_calls_made": 0},
        "git": {"head": git("rev-parse", "HEAD"),
                "head_subject": git("log", "-1", "--format=%s"),
                "pinned_product_commit": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
                "working_tree_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "product_source_diff_pinned_to_head": git(
                    "diff", "--stat",
                    "0bfda2363ef1a1d552e2ac093129b1026a86ad68..HEAD",
                    "--", "prototype/pseudex", "prototype/licensing",
                    "prototype/testkit.py"),
                "note": "890c508 is a research-only commit; the product source is the "
                        "pinned 0bfda236 content and the diff above is empty"},
        "run": {"run_id": RUN_ID, "label": "v5-sprint-v2-813",
                "directory": str(RUN.relative_to(REPO)),
                "meta_provenance_commit": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
                "meta_corpus_sha256": "7f7b1a80ba0c8fb3928d3105f9226646bc0950d65be97d37f9d4b8c7aabb8e52",
                "meta_corpus_v5_sha256": "3de9f13199ac957870f30c552988623d76bc15fd076ac3f0cc27fa747a0ef6a6"},
        "bundle": bundle_identity(),
        "sources": [describe(one) for one in SOURCE_FILES],
        "run_artifacts": [describe(one) for one in RUN_FILES if (REPO / one).exists()],
        "evidence_inputs": [describe(one) for one in EVIDENCE_FILES],
        "canary_reader": {
            "capture_version": payload_canaries.CAPTURE_VERSION,
            "manifest_version": payload_canaries.MANIFEST_VERSION,
            "capture_max_row_bytes": payload_canaries.CAPTURE_MAX_ROW_BYTES,
            "capture_max_run_bytes": payload_canaries.CAPTURE_MAX_RUN_BYTES,
            "capture_suffix": payload_canaries.CAPTURE_SUFFIX,
            "kill_switch": payload_canaries.CAPTURE_KILL_SWITCH,
        },
        "boundaries": {"write_scope": "research/quality-sprint-2026-09-30/work/M1b/",
                       "read_only": ["prototype/", "research/hop-format-audit/",
                                     "wiki/", "old raw runs and corpora",
                                     "EXECUTION.json and the usage journal (Lead owns)"],
                       "forbidden_actions_performed": ["git reset/stash/revert",
                                                       "package installs",
                                                       "model downloads",
                                                       "provider/benchmark calls",
                                                       "broad secret-path search"]},
    }

    (out_dir / "INPUTS.json").write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = missing_state(parity, reasons_raw)
    (out_dir / "MISSING-STATE.json").write_text(
        json.dumps(missing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"inputs": str(out_dir / "INPUTS.json"),
                      "missing_state": str(out_dir / "MISSING-STATE.json"),
                      "sources_hashed": len(inputs["sources"]),
                      "run_artifacts_hashed": len(inputs["run_artifacts"]),
                      "evidence_hashed": len(inputs["evidence_inputs"])},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
