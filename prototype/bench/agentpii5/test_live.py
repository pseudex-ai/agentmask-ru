"""`live.py` snapshot agrees with the offline `hop-report` on the same files,
and degrades to `starting`/`missing` on a half-written or absent run.

One fixture (test_cohort._write_source) written with the live writers, so the
snapshot reads the SAME bytes `compose_cohort` reads and the numbers must
match — a live face that disagreed with the offline report at the end would be
a second estimator, which this module is not.
"""

import tempfile
from pathlib import Path

from bench.agentpii5 import live
from bench.agentpii5.cohort import compose_cohort
from bench.agentpii5.hop_report import historical_counts, source_spec
from bench.agentpii5.test_cohort import CASES_A, PROVIDER_12000, SOURCE_A, _cases, _write_source


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        run_dir = _write_source(root, SOURCE_A, _cases(CASES_A), PROVIDER_12000, 3.0)

        snapshot = live.live_snapshot(run_dir)
        if snapshot["state"] != "live":
            failures.append(f"state={snapshot['state']}, wanted live")
        if snapshot["done"] != len(CASES_A):
            failures.append(f"done={snapshot['done']}, wanted {len(CASES_A)}")

        # The live historical counts must equal the offline cohort's counts.
        cohort = compose_cohort((source_spec(f"src={run_dir}"),))
        for name, line in historical_counts(cohort).items():
            got = snapshot["historical"][name]
            if got["hits"] != line["hits"] or got["total"] != line["total"]:
                failures.append(f"historical {name}: live {got} != offline "
                                f"{line['hits']}/{line['total']}")

        # The hop-owner breakdown is present and carries the buckets THIS corpus
        # actually crosses (`IN/tool` only appears when a tool result carries a
        # PII item back — the nano fixtures have none).
        owners = snapshot["owners"]
        if not owners or "IN/user" not in owners:
            failures.append(f"owners empty or missing IN/user: {sorted(owners)}")

        text = live.render(snapshot)
        for needle in ("Historical", "Переходы", "Actual OUT", "Actual causal"):
            if needle not in text:
                failures.append(f"render missing {needle!r}")

        # A directory that is not yet a run degrades, never raises.
        empty = root / "empty"
        empty.mkdir()
        early = live.live_snapshot(empty)
        if early["state"] not in ("missing", "no_corpus"):
            failures.append(f"empty dir state={early['state']}, wanted missing/no_corpus")

        missing = live.live_snapshot(root / "does-not-exist")
        if missing["state"] != "missing":
            failures.append(f"absent dir state={missing['state']}, wanted missing")

    if failures:
        for failure in failures:
            print("FAIL", failure)
        return 1
    print("live: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
