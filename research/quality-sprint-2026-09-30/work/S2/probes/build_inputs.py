"""Build S2/INPUTS.json from measured file hashes — executed, not hand-copied.

Checks the product source against the B0 G1 pin before recording anything:
the seven engine files S2 reads must still match the SHA256 B0 stored.
Exit 0 = every pin matched; exit 1 = a pin drifted (S2 must not proceed).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys

ROOT = "/Users/igor/Projects/Obscura-hop-audit"
S2 = os.path.join(ROOT, "research/quality-sprint-2026-09-30/work/S2")
B0_INPUTS = os.path.join(ROOT, "research/quality-sprint-2026-09-30/work/B0/INPUTS.json")

PINNED = [
    "prototype/pseudex/quasi.py",
    "prototype/pseudex/context.py",
    "prototype/pseudex/detect_all.py",
    "prototype/pseudex/vault.py",
    "prototype/pseudex/redact.py",
    "prototype/licensing/assets_source.py",
    "prototype/licensing/pack.py",
]

INPUTS_READ = [
    ("research/quality-sprint-2026-09-30/work/B0/GATE.json", "G1 local/design PASS, production NOT_VERIFIED, allowed_next includes S2"),
    ("research/quality-sprint-2026-09-30/work/B0/REVIEW.md", "independent B0 review; limits and production gate"),
    ("research/quality-sprint-2026-09-30/GOAL-BRIEF.md", "semantic-PII clause L68; S2 deliverable L216; gate discipline L337"),
    ("research/quality-sprint-2026-09-30/OWNER-DECISIONS.md", "binding owner answers Q1-Q4, lexical ambiguity rule"),
    ("research/quality-sprint-2026-09-30/REMAINING-DECISIONS.md", "Block 5 semantic-PII scope; Block 1/2 name+identity rules"),
    ("research/quality-sprint-2026-09-30/SPRINT-PLAN.md", "S2 work package L124, G0/G3 gate text L144-L147, G7 L157"),
    ("research/quality-sprint-2026-09-30/work/FIRST-WAVE-SCOPES.md", "wave write scopes and synthetic-fixture limits"),
    ("research/quality-sprint-2026-09-30/work/FIRST-WAVE-TASKS.json", "exact task entry id=S2"),
    ("wiki/INVARIANTS.md", "Dates association rule L156; context rules; engine-wide fail-closed"),
    ("research/2026-08-16-vertical-pii-registry.md", "prior registry gap table (salary/conviction are values, not patterns) L346-L371"),
    ("research/2026-08-16-industry-pii-hr-insurance-legal.md", "HR/legal vertical inventory; vendor gap"),
    ("research/dd4-C-quasi-identifiers.md", "prior quasi-identifier design (diagnosis as sensitive attribute)"),
    ("prototype/test_coverage_152fz.py", "current must-catch list incl. isolated MEDICAL L48 and legal-person negative"),
    ("prototype/testkit.py", "load_dev_bundle development path contract"),
    ("prototype/pseudex/quasi.py", "DOB/AGE/MEDICAL recognizer implementation"),
    ("prototype/pseudex/detect_all.py", "single composition point; stage order; priority"),
    ("prototype/pseudex/context.py", "suppress(); _IDENTIFIES_A_PERSON includes AGE/MEDICAL"),
    ("prototype/pseudex/vault.py", "no-renderer fallback REDACTED<digest> L1920-L1929"),
    ("prototype/licensing/assets_source.py", "MEDICAL_PATTERN L1032-L1042; KEY_TYPE/CTX_TYPES contain no semantic keys"),
]

LEGAL = [
    {
        "url": "https://www.consultant.ru/document/cons_doc_LAW_61801/4f41fe599ce341751e4e34dc50a4b676674c1416/",
        "article": "152-ФЗ ст. 3 п. 1",
        "claim": "Personal data is any information relating to a directly or indirectly identified or identifiable natural person.",
        "used_for": "Why the SUBJECT->ATTRIBUTE relation, not the isolated word, is the unit of protection.",
        "limits": "Text fetched 2026-10-01 from a secondary legal mirror (ConsultantPlus), not from the official publication portal; wording of the current redaction (26.07.2026) is quoted, not the original 2006 text.",
    },
    {
        "url": "https://www.consultant.ru/document/cons_doc_LAW_61801/26edb2934b899bf9c74c3a8f7e574651c6565e6d/",
        "article": "152-ФЗ ст. 10 ч. 1",
        "claim": "Special categories requiring the ch. 2 conditions include 'state of health'; processing them is generally prohibited without a listed ground.",
        "used_for": "Diagnosis/health attribute belongs to the special-category class.",
        "limits": "Same mirror/redaction caveat; ch. 2 grounds are broad and this document makes no compliance determination for any operator.",
    },
    {
        "url": "https://www.consultant.ru/document/cons_doc_LAW_61801/26edb2934b899bf9c74c3a8f7e574651c6565e6d/",
        "article": "152-ФЗ ст. 10 ч. 3",
        "claim": "Conviction data is processed by state/municipal bodies within their powers, and by other persons in the cases and order determined by federal laws.",
        "used_for": "Conviction is NOT in the ch. 1 special-category list; it has its own narrower regime.",
        "limits": "Same mirror caveat; the parent document explicitly rejects re-classifying conviction as a health-like special category.",
    },
]


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    b0 = json.load(open(B0_INPUTS, encoding="utf-8"))
    pinned = {s["path"]: s["sha256"] for s in b0["sources"]}

    pinned_rows = []
    mismatches = []
    for rel in PINNED:
        now = sha256(os.path.join(ROOT, rel))
        want = pinned.get(rel)
        row = {"path": rel, "sha256_b0_pin": want, "sha256_now": now,
               "match": bool(want) and want == now}
        pinned_rows.append(row)
        if not row["match"]:
            mismatches.append(rel)

    read_rows = []
    for rel, purpose in INPUTS_READ:
        full = os.path.join(ROOT, rel)
        read_rows.append({
            "path": rel,
            "sha256": sha256(full),
            "bytes": os.path.getsize(full),
            "purpose": purpose,
        })

    fixture = os.path.join(S2, "EPISODES.jsonl")
    fixture_rows = sum(1 for line in open(fixture, encoding="utf-8") if line.strip())

    payload = {
        "task": "S2",
        "title": "Semantic PII gap inventory (subject -> attribute relations)",
        "stage": "ResearchOnly",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "root": ROOT,
        "write_scope": "research/quality-sprint-2026-09-30/work/S2/",
        "source_pins": {
            "git_head_evidence_commit": "890c50849a326f882eac336ba4e38c91171de473",
            "product_source_revision": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
            "product_source_note": "B0 pinned this revision; S2 ran read-only against the working tree, which B0 G1 verified as that source plus preserved WIP.",
            "engine_files_verified_against_b0": pinned_rows,
            "engine_pin_mismatches": mismatches,
        },
        "gate_source": {
            "path": "research/quality-sprint-2026-09-30/work/B0/GATE.json",
            "sha256": sha256(os.path.join(ROOT, "research/quality-sprint-2026-09-30/work/B0/GATE.json")),
            "gate": "G1",
            "status": "PASS",
            "scope": "local/design only",
            "production_artifact_gate": "NOT_MEASURED",
        },
        "task_contract": {
            "file": "research/quality-sprint-2026-09-30/work/FIRST-WAVE-TASKS.json",
            "entry_id": "S2",
            "deliverables": ["INPUTS.json", "SPEC.md", "GAP-MATRIX.json", "EPISODES.jsonl",
                             "OWNER-DISPOSITION.md", "GATE.json", "DELTA.json", "logs"],
        },
        "inputs_read": read_rows,
        "fixture": {
            "path": "research/quality-sprint-2026-09-30/work/S2/EPISODES.jsonl",
            "sha256": sha256(fixture),
            "episodes": fixture_rows,
            "synthetic": True,
            "source": "approved semantic scope: GOAL-BRIEF.md L68, SPRINT-PLAN.md L16, REMAINING-DECISIONS.md L38",
        },
        "legal_sources_fetched": LEGAL,
        "environment": {
            "python": sys.version.split()[0],
            "interpreter": sys.executable,
            "cwd_for_probe": "prototype",
            "PYTHONDONTWRITEBYTECODE": "1",
            "bundle": "load_dev_bundle() in-process; no bundle file written",
            "vault": "Vault(':memory:', 's2-synthetic'); no on-disk store",
            "network": "no provider, no production, no install, no model download",
        },
        "out_of_scope_confirmed": [
            "no engine/licensing/scorer/benchmark source changed",
            "no product implementation or semantic type added",
            "no git reset/stash/revert, no commit",
            "no EXECUTION.json or usage-journal write",
            "no paid/provider benchmark call",
            "no broad secret-path search",
        ],
    }
    out = os.path.join(S2, "INPUTS.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"pinned_sources={len(pinned_rows)} mismatches={mismatches}")
    print(f"inputs_read={len(read_rows)} episodes={fixture_rows}")
    print(f"WROTE {out}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
