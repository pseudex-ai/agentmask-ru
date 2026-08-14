"""Stage-level profiler for the masking hot path.

WHY THIS EXISTS: masking is the only CPU-heavy thing Obscura does, and "it feels
slow" is not actionable. This records where the time actually goes, per stage,
under REAL load — so optimization targets come from measurement instead of guesses.

Three levels, escalating (see docs/spec.md §4.1):
  1. THIS MODULE — always available, `OBSCURA_PROFILE=1`, near-zero cost when off.
     Answers "which stage". `GET /profile` on the sidecar.
  2. `profile_deep.py --mode=function` — yappi, answers "which function".
     yappi rather than cProfile because detection runs in a threadpool and
     cProfile only sees the thread it was started on.
  3. `profile_deep.py --mode=line` — line_profiler on whatever step 2 found.

Cost when disabled: `stage()` returns a shared no-op context manager, so the call
site pays one attribute lookup and one bool test. Safe to leave in the hot path.

Percentiles come from a bounded ring buffer per stage: memory stays capped in a
long-lived process, and the numbers describe RECENT traffic, which is what you
want when watching a benchmark run.
"""

import os
import threading
import time
from collections import deque
from contextlib import AbstractContextManager, nullcontext

ENABLED = os.environ.get("OBSCURA_PROFILE", "") == "1"

# Samples retained per stage for percentile estimation.
_CAPACITY = int(os.environ.get("OBSCURA_PROFILE_SAMPLES", "4096"))


class StageStats:
    """Thread-safe accumulator. Detection runs across worker threads, so every
    mutation is locked; the lock is held only for an append, never across the
    measured work itself."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("profiler capacity must be >= 1")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._samples: dict[str, deque[float]] = {}
        self._counts: dict[str, int] = {}
        self._totals: dict[str, float] = {}

    def record(self, name: str, seconds: float) -> None:
        with self._lock:
            samples = self._samples.get(name)
            if samples is None:
                samples = deque(maxlen=self._capacity)
                self._samples[name] = samples
                self._counts[name] = 0
                self._totals[name] = 0.0
            samples.append(seconds)
            self._counts[name] += 1
            self._totals[name] += seconds

    def snapshot(self) -> dict[str, dict[str, float]]:
        """Per-stage stats, sorted by total time spent — the top row is the thing
        worth optimizing. `count`/`total_ms` cover the whole process lifetime;
        percentiles cover the retained window."""
        with self._lock:
            frozen = {name: (sorted(samples), self._counts[name], self._totals[name])
                      for name, samples in self._samples.items()}
        out: dict[str, dict[str, float]] = {}
        for name, (samples, count, total) in frozen.items():
            if not samples:
                continue
            out[name] = {
                "count": count,
                "total_ms": round(total * 1000, 3),
                "mean_ms": round(total / count * 1000, 4),
                "p50_ms": round(_percentile(samples, 0.50) * 1000, 4),
                "p95_ms": round(_percentile(samples, 0.95) * 1000, 4),
                "p99_ms": round(_percentile(samples, 0.99) * 1000, 4),
                "max_ms": round(samples[-1] * 1000, 4),
                "window": len(samples),
            }
        return dict(sorted(out.items(), key=lambda item: item[1]["total_ms"], reverse=True))

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._counts.clear()
            self._totals.clear()


def _percentile(ordered: list[float], fraction: float) -> float:
    """Nearest-rank percentile over an already-sorted list."""
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return ordered[index]


STAGES = StageStats(_CAPACITY)
_NULL = nullcontext()


class _Timer:
    """Deliberately not a @contextmanager generator: this wraps stages that run
    per detected span, and the generator machinery would show up in its own
    measurement."""

    __slots__ = ("_name", "_start")

    def __init__(self, name: str) -> None:
        self._name = name
        self._start = 0.0

    def __enter__(self) -> "_Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        STAGES.record(self._name, time.perf_counter() - self._start)


def stage(name: str) -> AbstractContextManager[None]:
    """Time a block as `name`. No-op unless OBSCURA_PROFILE=1."""
    return _Timer(name) if ENABLED else _NULL


def snapshot() -> dict[str, object]:
    return {"enabled": ENABLED, "stages": STAGES.snapshot()}
