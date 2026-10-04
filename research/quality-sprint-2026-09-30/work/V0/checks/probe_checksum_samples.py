#!/usr/bin/env python3
"""V0 exploratory probe: does the v6 registry's `sample` actually PASS its own
published checksum, and what does the v6 `fake_checksum_invalid` rule score for
(a) a substitute that INHERITS source validity (owner Q2) and (b) the M8 mutant
("mints substitutes that PASS their checksum", tz-agentpii6.md §M8)?

Pure stdlib, no engine, no provider. Reads only frozen snapshot sources.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True
FROZEN = Path("/Users/igor/Projects/Obscura-hop-audit/research/quality-sprint-2026-09-30/work/V0/evidence/frozen")
V6 = FROZEN / "v6"
PY = FROZEN / "pypath"
BIK = "049805746"


def load(name: str):
    """Import a snapshot module from the frozen pypath (no engine, no installs)."""
    sys.path.insert(0, str(PY))
    module = __import__(f"bench.agentpii5.{name}", fromlist=[name])
    sys.path.pop(0)
    return module


def main() -> int:
    pt = load("pii_types")
    cs = load("checksum_v6")
    rows = []
    for t in pt.TYPE_REGISTRY:
        if not t.generated_checksum:
            continue
        sample = t.sample
        try:
            ok = cs.validate_account(sample, BIK) if t.id == "BANK_ACCOUNT" else cs.validate(t.id, sample)
        except Exception as err:  # noqa: BLE001
            ok = f"ERR {err!r}"
        rows.append((t.id, t.generated_checksum, t.value_notation, t.mint, sample, ok))
    print(f"{'type':26s} {'algo':18s} {'notation':11s} {'mint':10s} sample_valid")
    for r in rows:
        print(f"{r[0]:26s} {r[1]:18s} {r[2]:11s} {r[3]:10s} {r[5]}")
    print(f"generated_checksum types = {len(rows)}; sample valid = "
          f"{sum(1 for r in rows if r[5] is True)}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
