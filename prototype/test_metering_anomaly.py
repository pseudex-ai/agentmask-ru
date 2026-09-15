"""WS-6/M2: the fleet-wide metering-anomaly report surfaces a silent (root-patched)
or key-sharing engine for operator review.

The per-org signals (`unacked_quanta`, `ack_regressions`) already exist and are billed
for; this pins that `metering_anomalies` aggregates them across the fleet and flags the
right orgs — the operator surface the residual (bounded, per docs/metering-integrity)
never had.

Run:  python3 test_metering_anomaly.py
"""
import pathlib
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from licensing.store import LicenseStore  # noqa: E402


def main() -> None:
    s = LicenseStore(tempfile.mktemp(suffix=".db"))
    now = time.time()

    def meter(org: str, pubkey: str, unacked: int, regressions: int,
              granted: int, acked: int, updated: float) -> None:
        s._conn.execute(
            "INSERT INTO meter (org_id, pubkey, first_seen, updated_at, granted, acked, "
            "unacked_quanta, ack_regressions) VALUES (?,?,?,?,?,?,?,?)",
            (org, pubkey, now, updated, granted, acked, unacked, regressions))
        s._conn.commit()

    meter("honest", "k1", 0, 0, 10000, 9800, now)          # reports honestly
    meter("silent", "k1", 30, 0, 10000, 200, now)          # served, stopped reporting
    meter("silent", "k2", 25, 0, 10000, 150, now)          # 2nd process, same silence
    meter("shared", "k1", 0, 4, 5000, 4800, now)           # usage went backwards: one key, two engines
    meter("stale", "k1", 99, 0, 10000, 0, now - 7200)      # silent but INACTIVE (2h ago) → not fleet-current

    report = s.metering_anomalies(min_unacked=10, min_regressions=1, active_within_seconds=3600)
    flagged = {a["org_id"] for a in report}
    ok_set = flagged == {"silent", "shared"}

    silent = next((a for a in report if a["org_id"] == "silent"), {})
    ok_agg = silent.get("unacked_quanta") == 55 and silent.get("processes") == 2
    ok_sorted = bool(report) and report[0]["org_id"] == "silent"      # most-silent first
    ok_reasons = bool(silent.get("reasons"))

    passed = ok_set and ok_agg and ok_sorted and ok_reasons
    print(f"  flagged={sorted(flagged)}  silent={silent.get('unacked_quanta')}/{silent.get('processes')}proc")
    print(f"  {'PASS' if ok_set else 'FAIL'}  only silent+shared flagged (honest + stale-inactive clean)")
    print(f"  {'PASS' if ok_agg else 'FAIL'}  per-org aggregation across processes (55 over 2)")
    print(f"  {'PASS' if ok_sorted else 'FAIL'}  sorted most-severe first")
    print("=" * 60)
    if not passed:
        raise SystemExit("metering anomaly report not correct")
    print("WS-6/M2: silent (root-patched) and key-sharing engines surface for review.")


if __name__ == "__main__":
    main()
