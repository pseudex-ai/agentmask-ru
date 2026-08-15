"""Search a running process's memory for a string. Used by gate L14.

`Assets.unload()` claims to DROP the gazetteers, not to hide them behind a flag.
The only way to check that claim is to look at the process's actual memory before
and after — a flag would leave the strings exactly where they were.

Runs in its own throwaway container that joins the sidecar's PID namespace with
SYS_PTRACE, rather than inside the sidecar itself: the release image is a
compiled binary with no Python, and a scanner that only works on the development
image would not be testing the thing that ships.

usage: python3 memscan.py <needle> [<process-name-substring>]
"""

import os
import re
import sys


def _pids(name_filter: str) -> list[int]:
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                cmdline = handle.read().decode("utf-8", "replace")
        except OSError:
            continue
        if name_filter in cmdline and "memscan" not in cmdline:
            found.append(pid)
    return found


def _needles(text: str) -> list[tuple[str, bytes]]:
    """The byte forms the marker can actually take in a live CPython process.

    UTF-8 alone finds NOTHING, and that is not a bug in the process being
    scanned: CPython stores strings per PEP 393 in the narrowest fixed width that
    fits, so an all-Cyrillic word is held as UCS-2 — two bytes per character,
    little-endian — not as UTF-8. Searching only for UTF-8 made the scanner
    report a clean process no matter what was in it, i.e. a gate that could
    never fail.

    UTF-8 is still searched, for the same word sitting in a bytes buffer
    (the compressed bundle, a socket read); UCS-4 for a string that got promoted
    by concatenation with an astral character."""
    return [
        ("ucs2", text.encode("utf-16-le")),
        ("utf8", text.encode("utf-8")),
        ("ucs4", text.encode("utf-32-le")),
    ]


def _scan(pid: int, needle: bytes) -> int:
    """Number of readable anonymous/heap regions containing the needle."""
    hits = 0
    try:
        maps = open(f"/proc/{pid}/maps", "r").read().splitlines()
        mem = open(f"/proc/{pid}/mem", "rb", 0)
    except OSError as error:
        print(f"  pid {pid}: cannot read memory ({error})", file=sys.stderr)
        return 0
    with mem:
        for line in maps:
            match = re.match(r"([0-9a-f]+)-([0-9a-f]+) (\S{4})", line)
            if match is None or "r" not in match.group(3):
                continue
            start, end = int(match.group(1), 16), int(match.group(2), 16)
            size = end - start
            # Skip absurd reservations; the heap regions we care about are small
            # enough to read, and a 1 TB mapping is not backed by anything.
            if size <= 0 or size > 512 * 1024 * 1024:
                continue
            try:
                mem.seek(start)
                chunk = mem.read(size)
            except (OSError, ValueError, OverflowError):
                continue
            if needle in chunk:
                hits += 1
    return hits


def _rss_kb(pid: int) -> int:
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    name_filter = sys.argv[2] if len(sys.argv) > 2 else "pseudex"
    pids = _pids(name_filter)
    if not pids:
        print("NO_TARGET_PROCESS")
        raise SystemExit(2)
    total = 0
    rss = 0
    for pid in pids:
        rss += _rss_kb(pid)
        for label, needle in _needles(sys.argv[1]):
            hits = _scan(pid, needle)
            total += hits
            print(f"  pid {pid} [{label}]: {hits} region(s) with the marker", file=sys.stderr)
    print(f"HITS {total} in {len(pids)} process(es)")
    print(f"RSS_KB {rss}")


if __name__ == "__main__":
    main()
