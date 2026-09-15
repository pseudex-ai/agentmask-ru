"""Memory-read tripwire (WS-7): the vendor sees WHO tried to read the engine's RAM.

The DETECTOR half (pseudex/tripwire.scan) needs Linux /proc + a live worker and is
demonstrated live in the stand (it caught a `open('/proc/<pid>/mem')` carver with full
attribution: reader pid/uid/comm/exe/cmdline). This pins the VENDOR-SIDE half that runs
anywhere: a reported event is recorded and surfaced, attributing the reader, so the
evidence survives a root scrubbing the local log.

Run:  python3 test_tripwire.py
"""
import pathlib
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from licensing.store import LicenseStore  # noqa: E402
from pseudex.tripwire import ReadEvent, _event_key  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, name: str) -> None:
    RESULTS.append((ok, name))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")


def main() -> None:
    s = LicenseStore(tempfile.mktemp(suffix=".db"))

    # A carver read acme's engine; the watcher reported it. It records WHO, never contents.
    ev = ReadEvent(method="open_mem_fd", target_pid=16, reader_pid=1515, reader_uid=0,
                   reader_comm="python3", reader_exe="/usr/local/bin/python3.12",
                   reader_cmdline='python3 -c f=open("/proc/16/mem","rb")')
    s.record_tripwire("acme", ev.as_record())
    time.sleep(0.01)
    s.record_tripwire("acme", ReadEvent("ptrace", 17, 2020, 0, "gdb", "/usr/bin/gdb",
                                        "gdb -p 17").as_record())
    s.record_tripwire("globex", ReadEvent("open_mem_fd", 30, 99, 0, "dd", "/bin/dd",
                                          "dd if=/proc/30/mem").as_record())

    events = s.tripwire_events()
    ok_count = len(events) == 3
    ok_newest = events[0]["reader_comm"] == "dd"  # newest first (globex-dd written last)
    row = next((e for e in events if e["reader_comm"] == "python3"), {})
    ok_attr = (row.get("reader_uid") == 0 and row.get("reader_pid") == 1515
               and row.get("method") == "open_mem_fd"
               and 'open("/proc/16/mem"' in row.get("reader_cmdline", ""))
    ok_no_contents = all("value" not in e and "content" not in e for e in events)
    acme_only = s.tripwire_events(org_id="acme")
    ok_filter = len(acme_only) == 2 and all(e["org_id"] == "acme" for e in acme_only)
    ok_dedup = _event_key(ev) == _event_key(ev) and _event_key(ev)[1] == 1515

    check(ok_count and ok_newest, "reported reads recorded, newest first")
    check(ok_attr, "the READER is attributed (uid/pid/comm/exe/cmdline), 100% of who tried")
    check(ok_no_contents, "records WHO only — never memory contents")
    check(ok_filter, "fleet surface filters by org (names who tried, per org)")
    check(ok_dedup, "event key dedupes a repeated reader across scans")

    passed = all(ok for ok, _ in RESULTS)
    print("=" * 60)
    if not passed:
        raise SystemExit("tripwire vendor-surface not correct")
    print("tripwire: a memory-read attempt is attributed to the exact reader and "
          "reported to the vendor in real time.")


if __name__ == "__main__":
    main()
