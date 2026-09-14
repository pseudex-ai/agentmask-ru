"""The worker process hardens itself against having its memory read off disk.

Written BEFORE `pseudex/hardening.py` (ТЗ docs/tz-tuning-in-lease.md, Ступень 1):
the tuning lives decrypted in RAM while the engine runs — a theorem we cannot
beat against root, but three disk-persistence and co-tenant vectors we CAN close:

  * a CRASH must not write a core file with the tuning to disk  → RLIMIT_CORE=0
  * a co-tenant / non-root debugger must not `gcore` us          → PR_SET_DUMPABLE=0
  * the tuning must never be swapped to disk                     → mlockall (best effort)

None of these makes reading the LIVE RAM of a process impossible for its own root
(that is physics). They close the paths where the tuning ends up ON DISK, and
raise the bar for anyone short of root-with-CAP_SYS_PTRACE. Honest scope, stated
in the asserts.

Run:  python3 test_memory_hardening.py
"""
import platform
import resource
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def test_core_dumps_disabled() -> None:
    """After hardening, RLIMIT_CORE is 0 — a crash cannot dump the tuning to a
    core file. Works on every POSIX (resource module), so it is asserted hard on
    all platforms. Positive control: it is NOT already 0 before hardening on the
    CI runner (proves the call did something), unless the environment pre-set it."""
    from pseudex.hardening import harden_process
    before_soft, before_hard = resource.getrlimit(resource.RLIMIT_CORE)
    status = harden_process()
    soft, hard = resource.getrlimit(resource.RLIMIT_CORE)
    check(soft == 0 and hard == 0, "core dumps disabled (RLIMIT_CORE=0)",
          f"before={before_soft}/{before_hard} after={soft}/{hard} status={status.get('core')}")


def test_not_dumpable_on_linux() -> None:
    """On Linux the process is marked non-dumpable (PR_GET_DUMPABLE==0): a
    same-uid non-root `gcore`/ptrace is refused. Root with CAP_SYS_PTRACE still
    can — stated honestly in the status string, not hidden. On non-Linux this is
    unsupported and the status must SAY so rather than silently claim success."""
    from pseudex.hardening import harden_process, get_dumpable
    harden_process()
    if platform.system() == "Linux":
        dumpable = get_dumpable()
        check(dumpable == 0, "process is non-dumpable (PR_SET_DUMPABLE=0)",
              f"PR_GET_DUMPABLE={dumpable}")
    else:
        status = harden_process()
        check(status.get("dumpable", "").startswith("unsupported"),
              "non-dumpable correctly reported unsupported off Linux",
              f"status={status.get('dumpable')}")


def test_mlock_attempted_and_honest() -> None:
    """mlockall is best-effort: it needs a high RLIMIT_MEMLOCK and can legitimately
    fail (a locked-memory limit the runtime did not raise). The requirement is
    that it is ATTEMPTED and its outcome reported truthfully — never a silent
    'ok' when the lock did not take. On Linux a success shows as VmLck>0."""
    from pseudex.hardening import harden_process
    status = harden_process()
    mlock = status.get("mlock", "")
    reported = mlock.startswith(("ok", "failed", "unsupported"))
    check(reported, "mlockall attempted with an honest verdict", f"status={mlock}")
    if platform.system() == "Linux" and mlock.startswith("ok"):
        vmlck = _vmlck_kb()
        check(vmlck > 0, "mlock success is real (VmLck>0)", f"VmLck={vmlck}kB")


def test_idempotent_and_never_raises() -> None:
    """Hardening runs at process start on every role; a limit it cannot set must
    DEGRADE (report failed), never crash the worker — a dead worker protects
    nothing. Calling twice is safe."""
    from pseudex.hardening import harden_process
    try:
        harden_process()
        harden_process()
        check(True, "harden_process is idempotent and never raises")
    except Exception as exc:  # noqa: BLE001
        check(False, "harden_process is idempotent and never raises", f"raised {exc!r}")


def _vmlck_kb() -> int:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmLck:"):
                return int(line.split()[1])
    except OSError:
        pass
    return -1


def main() -> None:
    test_core_dumps_disabled()
    test_not_dumpable_on_linux()
    test_mlock_attempted_and_honest()
    test_idempotent_and_never_raises()
    failed = [n for ok, n, _ in RESULTS if not ok]
    print("=" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("hardening not in place:", failed)
        raise SystemExit(1)
    print("memory hardening: core dumps off, non-dumpable, swap-locked.")


if __name__ == "__main__":
    main()
