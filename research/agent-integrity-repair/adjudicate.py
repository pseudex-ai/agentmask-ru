"""Lead adjudication: separate OBJECTIVE gateway harm from reviewer-only harm.

The 40 review agents labelled cases `harmful_persistent` / `harmful_recovered` /
`execution_error` by reading the run. That is a BUSINESS verdict: it says the
outcome was wrong, not WHO was wrong. This script cross-references every such
case against the deterministic judge (`artifact_parity`) — the objective signal
that a substitute reached a tool or that the I arm did extra work — and splits
the reviewers' labels into three causes:

  gateway_residual_leak    a PII-shaped substitute survived in a durable write
                           (NAME/PHONE/SUBSTITUTE residual). The engine minted
                           a fake and failed to restore it: OUR defect.
  gateway_behavior_change  the I arm performed MORE of an action than BOTH
                           controls. The masking made the agent do extra work:
                           OUR defect (or model confusion to attribute later).
  reviewer_only            the reviewer saw harm but neither objective signal
                           fired. Model behaviour or a mechanism the judge does
                           not capture; NOT counted as proven gateway harm.

DATE residuals are DROPPED as false positives: an ISO slot the arm wrote and
restored unchanged is an operational time the engine never masked, and the
residual detector merely flagged a date fragment that matched a birth-date fake.
Read-only; writes nothing into the run.
"""
import argparse
import json
import sys
from pathlib import Path

# Residual types the deterministic judge reports. DATE is a known false positive
# (operational slot), the rest are PII-shaped and count as a real leak.
REAL_LEAK_TYPES = frozenset({"NAME", "PHONE", "SUBSTITUTE"})


def load_rollup(path: Path) -> dict:
    return json.loads(path.read_text())


def load_parity(path: Path) -> dict:
    return json.loads(path.read_text())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rollup", help="COMPLETE-REVIEW-PROVISIONAL-ROLLUP.json")
    ap.add_argument("parity", help="artifact_parity --json output over the same run")
    ap.add_argument("--out", default="-", help="write JSON here (default stdout)")
    args = ap.parse_args(argv)

    rollup = load_rollup(Path(args.rollup))
    parity = load_parity(Path(args.parity))

    # Index objective signals per case.
    residual_cases: set[str] = set()
    for row in parity["artifact_purity"]["durable_violations"]:
        if row["leak_type"] in REAL_LEAK_TYPES:
            residual_cases.add(row["case_id"])
    for row in parity["artifact_purity"]["readonly_violations"]:
        if row["leak_type"] in REAL_LEAK_TYPES:
            residual_cases.add(row["case_id"])
    behaviour_cases: set[str] = {row["case_id"] for row in parity["behavioural_parity"]}

    wanted_verdicts = frozenset({"harmful_persistent", "harmful_recovered", "execution_error", "unresolved"})
    rows = []
    for case in rollup.get("cases", []):
        verdict = case.get("verdict") or case.get("reviewer_verdict") or case.get("label")
        if verdict not in wanted_verdicts:
            continue
        cid = case.get("case_id")
        causes = []
        if cid in residual_cases:
            causes.append("gateway_residual_leak")
        if cid in behaviour_cases:
            causes.append("gateway_behavior_change")
        if not causes:
            causes.append("reviewer_only")
        rows.append({"case_id": cid, "reviewer_verdict": verdict, "causes": causes})

    counts: dict[str, int] = {}
    for row in rows:
        for cause in row["causes"]:
            counts[cause] = counts.get(cause, 0) + 1

    result = {
        "purpose": "Separate objective gateway harm from reviewer-only harm; do not overwrite reviewer evidence",
        "source": {"rollup": str(args.rollup), "parity": str(args.parity)},
        "counts": counts,
        "cases": rows,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
