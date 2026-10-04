"""Verify every count recorded in S2/GATE.json against the real artifacts.

Exit 0 only when each recorded number recomputes from the probe JSON, the
fixture, the matrix and the B0 pin. Writes logs/OUTPUT-HASHES.txt.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = "/Users/igor/Projects/Obscura-hop-audit"
S2 = os.path.join(ROOT, "research/quality-sprint-2026-09-30/work/S2")
B0_INPUTS = os.path.join(ROOT, "research/quality-sprint-2026-09-30/work/B0/INPUTS.json")

PINNED = [
    "prototype/pseudex/quasi.py", "prototype/pseudex/context.py",
    "prototype/pseudex/detect_all.py", "prototype/pseudex/vault.py",
    "prototype/pseudex/redact.py", "prototype/licensing/assets_source.py",
    "prototype/licensing/pack.py",
]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    failures: list[str] = []
    gate = json.load(open(os.path.join(S2, "GATE.json"), encoding="utf-8"))
    probe = json.load(open(os.path.join(S2, "probes/semantic_probe.json"), encoding="utf-8"))
    matrix = json.load(open(os.path.join(S2, "GAP-MATRIX.json"), encoding="utf-8"))
    episodes = [json.loads(l) for l in open(os.path.join(S2, "EPISODES.jsonl"),
                                            encoding="utf-8") if l.strip()]
    b0 = json.load(open(B0_INPUTS, encoding="utf-8"))
    pins = {s["path"]: s["sha256"] for s in b0["sources"]}

    checks: list[tuple[str, object, object]] = []
    checks.append(("episodes_total", len(episodes), gate["checks"]["episodes_total"]))
    checks.append(("probe_episodes", probe["counts"]["episodes"], len(episodes)))
    checks.append(("any_span", probe["counts"]["any_span"], gate["checks"]["episodes_with_any_span"]))
    checks.append(("masked_changed", probe["counts"]["masked_changed"], gate["checks"]["episodes_masked_changed"]))
    checks.append(("roundtrip", f'{probe["counts"]["roundtrip_identical"]}/{probe["counts"]["episodes"]}',
                   gate["checks"]["roundtrip_identical"]))
    sem_pos = [e for e in episodes if e["pair_role"] == "positive" and e["dimension"] != "control"]
    sem_neg = [e for e in episodes if e["pair_role"] == "negative"]
    ctl = [e for e in episodes if e["dimension"] == "control"]
    checks.append(("semantic_positive", len(sem_pos), gate["checks"]["episodes_semantic_positive"]))
    checks.append(("negative", len(sem_neg), gate["checks"]["episodes_negative"]))
    checks.append(("controls", len(ctl), gate["checks"]["episodes_existing_capability_control"]))

    rows = {r["id"]: r for r in matrix["measured_episodes"]}
    closed = sum(1 for e in sem_pos if rows[e["id"]]["relation_state_measured"] == "relation_closed")
    disclosed = sum(1 for e in sem_pos if rows[e["id"]]["relation_state_measured"] == "relation_disclosed_by_attribute")
    not_detected = sum(1 for e in sem_pos if rows[e["id"]]["relation_state_measured"] == "subject_not_detected")
    checks.append(("semantic_closed", closed, gate["checks"]["semantic_positive_relation_closed"]))
    checks.append(("semantic_disclosed", disclosed, gate["checks"]["semantic_positive_relation_disclosed_by_leftover_attribute"]))
    checks.append(("semantic_subject_not_detected", not_detected, gate["checks"]["semantic_positive_subject_not_detected"]))
    checks.append(("closed+disclosed+not_detected", closed + disclosed + not_detected, len(sem_pos)))

    over = [e["id"] for e in sem_neg if rows[e["id"]]["engine_types"]]
    checks.append(("negative_over_masked", len(over), gate["checks"]["negative_over_masked"]))
    checks.append(("negative_untouched", len(sem_neg) - len(over), gate["checks"]["negative_correctly_untouched"]))

    pin_matches = sum(1 for rel in PINNED if pins.get(rel) == sha256(os.path.join(ROOT, rel)))
    checks.append(("engine_pins", f"{pin_matches}/7", gate["source_pin"]["engine_files_verified_against_b0"]))

    checks.append(("owner_forks", len(gate["owner_forks"]), 1))
    checks.append(("owner_questions", len(gate["owner_forks"][0]["questions"]), gate["checks"]["owner_forks"]))
    checks.append(("read_facts", len(matrix["read_inventory"]), gate["checks"]["read_inventory_facts"]))
    checks.append(("implementation_allowed", gate["owner_forks"][0]["implementation_allowed"], False))

    for name, got, want in checks:
        ok = got == want
        print(f'{"ok  " if ok else "FAIL"} {name}: got={got!r} want={want!r}')
        if not ok:
            failures.append(name)

    files = ["INPUTS.json", "SPEC.md", "GAP-MATRIX.json", "EPISODES.jsonl",
             "OWNER-DISPOSITION.md", "DELTA.json", "GATE.json",
             "probes/semantic_probe.py", "probes/semantic_probe.json",
             "probes/build_inputs.py",
             "probes/build_matrix.py", "probes/verify_outputs.py",
             "logs/semantic_probe.log", "logs/build_inputs.log", "logs/build_matrix.log",
             # verify_outputs.log is intentionally excluded: it is the file this
             # process is currently writing, so hashing it would record 0 bytes.
             "logs/COMMANDS.md"]
    lines = ["# S2 output hashes (sha256, size) — written by probes/verify_outputs.py"]
    for rel in files:
        full = os.path.join(S2, rel)
        if not os.path.exists(full):
            print(f"FAIL missing artifact {rel}")
            failures.append(rel)
            continue
        lines.append(f"{sha256(full)}  {os.path.getsize(full):>8}  {rel}")
    with open(os.path.join(S2, "logs/OUTPUT-HASHES.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"CHECKS {len(checks)} FAILURES {len(failures)} {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
