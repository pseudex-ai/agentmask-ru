"""The spend ceiling, held under one lock, with the reservation made BEFORE the
call and reconciled against what was actually billed.

WHY A RESERVATION AND NOT A PRE-CHECK. The obvious guard is
`spent + cap <= ceiling` evaluated just before launching a case. It is provable
only at concurrency one: two cases evaluate it at the same instant, both pass,
and together they breach the ceiling. Under one `asyncio.Lock` the admission test
becomes `spent + Σ(in flight) + this_cap <= ceiling` and the quantity
`spent + Σ(in flight)` is held at or below the ceiling at EVERY instant — so even
if every run in flight bills its full cap, the ceiling stands.

WHAT THE CEILING ACTUALLY GUARANTEES, stated honestly. `max_budget_usd` is the
SDK's per-run cap and the CLI checks it BETWEEN turns, so a run can overshoot by
at most the turn that was already in flight when the check fired. The ledger
records what was really billed, so the overshoot is visible and the next
admission sees it — but the bound this class proves is «ceiling plus at most one
turn of the runs in flight», not «ceiling». Claiming the tighter one would be a
number nobody could defend after reading the SDK.

A CASE THAT CANNOT RESERVE IS RECORDED INCOMPLETE, NEVER DROPPED. A run that
sheds what it cannot afford and prints the rest reports the cheap cases and calls
it a result — and the cheap cases are the short, clean ones, which is exactly the
population whose numbers are already good.

The ledger is a plain TSV appended under one lock: two columns, a label and the
dollars, plus a `cumulative_usd` line after every charge so a killed run leaves a
readable total behind rather than a file somebody has to sum by hand.
"""

import asyncio
from pathlib import Path


class Budget:
    """A ledger file plus the in-flight reservations against it.

    A class rather than functions because it owns external state — a file on
    disk and a lock — which is the repo's one sanctioned reason for one.
    """

    def __init__(self, ledger: Path, ceiling_usd: float) -> None:
        self._ledger = ledger
        self._ceiling = float(ceiling_usd)
        self._reserved = 0.0
        self._committed = 0.0
        self._lock = asyncio.Lock()
        self._ledger.parent.mkdir(parents=True, exist_ok=True)

    @property
    def ceiling(self) -> float:
        return self._ceiling

    @property
    def committed(self) -> float:
        return self._committed

    @property
    def reserved(self) -> float:
        return self._reserved

    def held(self) -> float:
        """The quantity the invariant is about: committed plus every reservation
        still outstanding. Asserted against the ceiling on every admission."""
        return self._committed + self._reserved

    async def reserve(self, cap_usd: float) -> bool:
        """Admit one case iff its hard cap still fits under the ceiling counting
        everything already spent AND everything in flight. True means the caller
        owns the reservation and MUST later call `settle`."""
        cap = max(0.0, float(cap_usd))
        async with self._lock:
            if self._committed + self._reserved + cap > self._ceiling:
                return False
            self._reserved += cap
            return True

    async def settle(self, label: str, cap_usd: float, actual_usd: float) -> float:
        """Record what was really billed and drop the reservation, atomically.

        `actual_usd` is the measured `ResultMessage.total_cost_usd`, never an
        estimate: an estimated ledger is a ledger that disagrees with the invoice,
        and the whole point of the ceiling is that it does not.
        """
        cap = max(0.0, float(cap_usd))
        spent = max(0.0, float(actual_usd))
        async with self._lock:
            self._committed += spent
            self._reserved = max(0.0, self._reserved - cap)
            with self._ledger.open("a", encoding="utf-8") as handle:
                handle.write(f"{label}\t{spent:.6f}\n")
                handle.write(f"cumulative_usd\t{self._committed:.6f}\n")
            return self._committed
