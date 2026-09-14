"""Process-level hardening against having the worker's memory read off disk.

The tuning and the vault plaintext live decrypted in this process's RAM while it
serves — and no software can stop the machine's own root from reading a running
process's memory (a theorem, on any hardware without a TEE). What software CAN do
is close the paths where that memory ends up ON DISK, where it would persist past
the process and outside any lease, and raise the bar for anyone short of
root-with-CAP_SYS_PTRACE:

  * `RLIMIT_CORE = 0`      — a crash writes no core file (no tuning dump on disk).
  * `PR_SET_DUMPABLE = 0`  — a same-uid, non-root `gcore`/ptrace is refused; the
                             customer must actively grant CAP_SYS_PTRACE to dump.
  * `mlockall(...)`        — the pages are never swapped to disk (best effort:
                             needs a raised RLIMIT_MEMLOCK, may legitimately fail).

Every measure is BEST EFFORT and reports its outcome truthfully. A limit the
runtime will not grant DEGRADES (status 'failed: …') — it never raises, because a
worker that refuses to start protects nothing. The status dict is logged at
startup and asserted by `test_memory_hardening.py`.

NOT a claim that a memory dump is impossible for root — see the module docstring
of `pseudex/assets.py::unload` and docs/tz-tuning-in-lease.md for the honest
scope.
"""
import ctypes
import ctypes.util
import platform
import resource

# prctl options (linux/prctl.h) and mman flags (bits/mman-linux.h). Numeric
# because they are ABI-stable on Linux and we must not depend on a header.
_PR_SET_DUMPABLE = 4
_PR_GET_DUMPABLE = 3
_MCL_CURRENT = 1
_MCL_FUTURE = 2


def _libc() -> "ctypes.CDLL | None":
    if platform.system() != "Linux":
        return None
    try:
        return ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
    except OSError:
        return None


def _disable_core_dumps() -> str:
    """No core file on a crash — the one disk-persistence vector that is trivial
    and universal (works on every POSIX via the resource module, macOS included)."""
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        return "ok"
    except (ValueError, OSError) as error:
        return f"failed: {error}"


def _set_non_dumpable(libc: "ctypes.CDLL | None") -> str:
    if libc is None:
        return "unsupported (non-linux)"
    if libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        return f"failed: prctl errno {ctypes.get_errno()}"
    return "ok"


def _lock_memory(libc: "ctypes.CDLL | None") -> str:
    """Lock current and future pages so nothing is swapped to disk. Needs
    RLIMIT_MEMLOCK high enough to cover the resident set (~350 MB per worker) —
    the container must raise it (`ulimits: memlock: -1`). A low limit fails with
    ENOMEM/EPERM, which is reported, not hidden: a false 'ok' would be worse than
    a truthful failure."""
    if libc is None:
        return "unsupported (non-linux)"
    if libc.mlockall(_MCL_CURRENT | _MCL_FUTURE) != 0:
        errno = ctypes.get_errno()
        return f"failed: mlockall errno {errno} (raise RLIMIT_MEMLOCK)"
    return "ok"


def get_dumpable() -> int:
    """PR_GET_DUMPABLE, for the test to confirm the flag actually took. -1 off
    Linux or on error."""
    libc = _libc()
    if libc is None:
        return -1
    return libc.prctl(_PR_GET_DUMPABLE, 0, 0, 0, 0)


def harden_process() -> dict[str, str]:
    """Apply every hardening measure best-effort; return {measure: verdict}.

    Idempotent and non-raising by contract: called once per worker at the top of
    `serve_main.main`, before any role touches the tuning or the vault."""
    libc = _libc()
    return {
        "core": _disable_core_dumps(),
        "dumpable": _set_non_dumpable(libc),
        "mlock": _lock_memory(libc),
    }
