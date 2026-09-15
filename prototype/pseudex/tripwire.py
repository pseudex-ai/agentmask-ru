"""Memory-read tripwire: detect + attribute attempts to read the engine's RAM.

WHY THIS EXISTS, HONESTLY. A root user on the customer's own machine can read the
engine's memory (`/proc/<pid>/mem`, ptrace, process_vm_readv) and no code running
INSIDE the engine can see it — the read is a kernel operation that never enters our
process (a theorem; see research/2026-09-15-ram-extraction-hardening.md). This runs
OUTSIDE the engine, as a privileged watcher in the engine's PID namespace (or on the
host), and catches what a privileged observer CAN see: a process that ptrace-attached
to a worker, or that holds an open file descriptor onto a worker's `/proc/<pid>/mem`.
On a hit it records WHO (pid/uid/comm/exe/cmdline) and reports it to the licensing
server IN REAL TIME, so the evidence leaves the box before a root can scrub the local
log.

WHAT IT CATCHES: the common carve tooling — `gcore`/`gdb -p` (ptrace, shows as the
worker's TracerPid) and `dd if=/proc/<pid>/mem`/a held-open reader (an fd onto mem,
caught while the — necessarily slow, multi-MB — read is in flight).

WHAT IT DOES NOT (stated so it is never mis-sold): a single `process_vm_readv` leaves
no fd and no ptrace-attach (syscall-level only — use the shipped auditd/eBPF ruleset
`deploy/tripwire/audit-pseudex.rules` for that); a read via `/dev/mem`, a kernel
module, or cold-boot bypasses /proc entirely; and a root who disables THIS watcher
before the first read defeats it — but the watcher heartbeats, so a watcher that went
silent is itself a signal the vendor sees (like the metering-silence detector). This
is a TRIPWIRE + DETERRENT that raises the cost and forces the attacker to first
neutralise the auditor, not a guarantee against a prepared root.
"""
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable

_log = logging.getLogger("pseudex.tripwire")

_PROC = Path("/proc")
_ENGINE_MATCH = ("pseudex-serve", "serve_main", "pseudex")


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except (OSError, ValueError):
        return ""


def _cmdline(pid: str) -> str:
    raw = _read(_PROC / pid / "cmdline")
    return raw.replace("\x00", " ").strip()


def _uid(pid: str) -> int:
    for line in _read(_PROC / pid / "status").splitlines():
        if line.startswith("Uid:"):
            try:
                return int(line.split()[1])   # real uid
            except (IndexError, ValueError):
                return -1
    return -1


def _tracer_pid(pid: str) -> int:
    for line in _read(_PROC / pid / "status").splitlines():
        if line.startswith("TracerPid:"):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return 0
    return 0


def _comm(pid: str) -> str:
    return _read(_PROC / pid / "comm").strip()


def _exe(pid: str) -> str:
    try:
        return os.readlink(_PROC / pid / "exe")
    except OSError:
        return ""


def _pids() -> list[str]:
    return [p.name for p in _PROC.iterdir() if p.name.isdigit()] if _PROC.exists() else []


def engine_workers(pids: Iterable[str] | None = None) -> list[str]:
    """PIDs whose cmdline is an engine worker."""
    out: list[str] = []
    for pid in (pids if pids is not None else _pids()):
        cmd = _cmdline(pid) + " " + _comm(pid)
        if any(tag in cmd for tag in _ENGINE_MATCH):
            out.append(pid)
    return out


@dataclass(frozen=True)
class ReadEvent:
    """A detected attempt to read an engine worker's memory. Attribution of the
    READER — never the memory contents, which this tool does not touch."""
    method: str          # "ptrace" | "open_mem_fd"
    target_pid: int      # the engine worker being read
    reader_pid: int
    reader_uid: int
    reader_comm: str
    reader_exe: str
    reader_cmdline: str

    def as_record(self) -> dict:
        return asdict(self)


def _reader_event(method: str, target_pid: int, reader_pid: str) -> ReadEvent:
    return ReadEvent(
        method=method,
        target_pid=target_pid,
        reader_pid=int(reader_pid) if reader_pid.isdigit() else -1,
        reader_uid=_uid(reader_pid),
        reader_comm=_comm(reader_pid),
        reader_exe=_exe(reader_pid),
        reader_cmdline=_cmdline(reader_pid),
    )


def scan(worker_pids: Iterable[str] | None = None, self_pid: int | None = None) -> list[ReadEvent]:
    """One sweep for in-flight memory reads of the engine workers. Two signals a
    privileged observer can see: a worker's TracerPid (ptrace attach) and any process
    holding an open fd onto a worker's `/proc/<pid>/mem`. Excludes the watcher itself
    and the workers (they never read their own mem)."""
    workers = list(worker_pids) if worker_pids is not None else engine_workers()
    worker_set = set(workers)
    me = self_pid if self_pid is not None else os.getpid()
    events: list[ReadEvent] = []

    # 1) ptrace attach — the target names its tracer.
    for w in workers:
        tracer = _tracer_pid(w)
        if tracer and str(tracer) not in worker_set and tracer != me:
            events.append(_reader_event("ptrace", int(w), str(tracer)))

    # 2) an open fd onto a worker's mem/maps — a held-open reader (dd, a carver).
    targets = {f"/proc/{w}/mem" for w in workers} | {f"/proc/{w}/maps" for w in workers}
    for pid in _pids():
        if pid in worker_set or pid == str(me):
            continue
        fd_dir = _PROC / pid / "fd"
        try:
            fds = list(fd_dir.iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                dest = os.readlink(fd)
            except OSError:
                continue
            if dest in targets:
                target_pid = int(dest.split("/")[2])
                events.append(_reader_event("open_mem_fd", target_pid, pid))
                break
    return events


def _event_key(e: ReadEvent) -> tuple:
    return (e.method, e.reader_pid, e.reader_uid, e.reader_cmdline)


def watch(report: Callable[[ReadEvent], None], interval: float = 1.0,
          heartbeat: Callable[[], None] | None = None,
          heartbeat_every: float = 30.0, stop: Callable[[], bool] | None = None) -> None:
    """Poll for memory-read attempts and hand each NEW one to `report` exactly once
    (deduped by reader+cmdline). A short interval catches a slow multi-MB carve while
    its mem fd is open. `heartbeat` fires periodically so the vendor can tell a live
    watcher from one a root has killed — a silent watcher is itself a signal. The read
    CONTENTS are never touched; only the reader is attributed."""
    seen: set[tuple] = set()
    last_beat = 0.0
    while not (stop and stop()):
        try:
            for event in scan():
                key = _event_key(event)
                if key in seen:
                    continue
                seen.add(key)
                _log.critical("MEMORY-READ ATTEMPT on the engine: %s", json.dumps(event.as_record()))
                try:
                    report(event)
                except Exception as exc:                       # never let a report failure stop the watch
                    _log.error("tripwire report failed (kept watching): %r", exc)
            now = time.monotonic()
            if heartbeat and now - last_beat >= heartbeat_every:
                heartbeat()
                last_beat = now
        except Exception as exc:                               # a watcher that crashes is a blind spot
            _log.error("tripwire scan error (retrying): %r", exc)
        time.sleep(interval)


def _http_reporter(url: str, tenant_key: str, org_id: str, verify):
    """Report each event to the licensing server so the evidence leaves the box in
    real time — before a root can scrub the local log. Best-effort: a network block by
    the attacker just means the event stays only in the local encrypted record (and the
    vendor sees the watcher's heartbeats stop)."""
    import httpx
    client = httpx.Client(verify=verify, timeout=10.0)

    def report(event: ReadEvent) -> None:
        client.post(url.rstrip("/") + "/v1/tripwire",
                    json={"org_id": org_id, "key": tenant_key,
                          "event": event.as_record(), "at": time.time()})
    return report


def main() -> int:
    """PSEUDEX_ROLE=tripwire: watch this container's engine workers and report reads to
    the licensing server. Runs as a PRIVILEGED sidecar in the engine's PID namespace."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    url = os.environ.get("PSEUDEX_LICENSE_URL", "")
    org_id = os.environ.get("PSEUDEX_ORG", "") or "default"
    tenant_key = os.environ.get("PSEUDEX_KEY", "")
    ca = os.environ.get("PSEUDEX_LICENSE_CA", "")
    verify = ca if ca else True
    if not engine_workers():
        _log.warning("tripwire: no engine workers visible — run me with --pid=container "
                     "of the sidecar (or on the host). Watching anyway.")
    if url and tenant_key:
        report = _http_reporter(url, tenant_key, org_id, verify)
        _log.info("tripwire armed: reporting memory-read attempts to %s for org %s", url, org_id)
    else:
        def report(event: ReadEvent) -> None:
            pass  # local CRITICAL log only (already emitted in watch)
        _log.warning("tripwire armed LOCAL-ONLY (no PSEUDEX_LICENSE_URL/PSEUDEX_KEY) — "
                     "events log here but are not reported to the vendor.")
    watch(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
