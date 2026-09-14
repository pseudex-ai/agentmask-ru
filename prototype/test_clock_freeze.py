"""Clock-freeze liveness (pentest W2-PATCH): a root customer LD_PRELOAD-froze
CLOCK_MONOTONIC to serve past revocation. `state()` now cross-checks the wall
clock as an upper bound — monotonic stays primary (anti-rollback), the wall
catches a freeze (which leaves the wall moving). Fail closed when the wall says
the lease is past ttl+grace while monotonic pretends it is fresh.

Run:  python3 test_clock_freeze.py
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pseudex.license import LicenseClient, STATE_LEASED, STATE_STALE, STATE_EXPIRED


def _mk(ttl, grace, mono_ago, wall_ago, terminal=None):
    c = LicenseClient.__new__(LicenseClient)
    c._lock = threading.Lock()
    c._terminal_code = terminal
    c._ttl_seconds = ttl
    c._grace_seconds = grace
    c._last_ok_monotonic = time.monotonic() - mono_ago
    c._last_ok_wall = time.time() - wall_ago
    return c


def main() -> None:
    cases = [
        (_mk(60, 120, 5, 5).state() == STATE_LEASED, "both fresh -> LEASED"),
        (_mk(60, 120, 90, 90).state() == STATE_STALE, "both in grace -> STALE"),
        (_mk(60, 120, 5, 10000).state() == STATE_EXPIRED,
         "frozen monotonic (wall past ttl+grace) -> EXPIRED"),
        (_mk(60, 120, 5, 20).state() == STATE_LEASED,
         "small wall skew (NTP) -> still LEASED"),
        (_mk(60, 120, 5, 5, terminal="403").state() == STATE_EXPIRED,
         "terminal revoke -> EXPIRED"),
        # Backward compat: no wall anchor (old object) -> wall check skipped.
        (_no_wall().state() == STATE_LEASED, "no wall anchor -> monotonic only (compat)"),
    ]
    for ok, name in cases:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(ok for ok, _ in cases)
    print("=" * 50)
    print(f"{passed}/{len(cases)} passed")
    if passed != len(cases):
        raise SystemExit(1)
    print("clock-freeze: wall-clock ceiling catches a frozen monotonic timer.")


def _no_wall():
    c = LicenseClient.__new__(LicenseClient)
    c._lock = threading.Lock()
    c._terminal_code = None
    c._ttl_seconds = 60
    c._grace_seconds = 120
    c._last_ok_monotonic = time.monotonic() - 5
    c._last_ok_wall = None
    return c


if __name__ == "__main__":
    main()
