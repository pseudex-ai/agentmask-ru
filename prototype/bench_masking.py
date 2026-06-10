"""Micro-benchmark for the high-load masking optimizations.

Compares, on the SAME real Detector + Vault:
  BEFORE: mask every message every call (the O(n^2) growing-transcript path).
  AFTER : content-keyed cache (re-mask of seen content is O(1)).

Simulates a multi-step agent turn: each LLM call re-sends the whole transcript so
far, and the transcript grows by one message per call. We sum the masking cost
across all calls of the turn -> the real per-conversation CPU.

Run: python3 bench_masking.py
"""

import hashlib
import time

from obscura.detect_all import Detector
from obscura.maskcache import MaskCache, content_key
from obscura.redact import mask_text
from obscura.vault import Vault

_PII_MSG = "Здравствуйте, меня зовут Иван Петров, телефон +7 999 123-45-67, доставьте на улицу Ленина 5, кв 12."
_PLAIN_MSG = "thanks, that works for me, please proceed with the plan as discussed above"


def _mask_no_cache(text: str, det: Detector, vault: Vault) -> str:
    spans = det.detect(text)
    return mask_text(text, vault, spans)


def _mask_cached(text: str, det: Detector, vault: Vault, cache: MaskCache, org: str) -> str:
    def compute() -> str:
        spans = det.detect(text)
        return mask_text(text, vault, spans)

    out, _ = cache.get_or_compute(content_key(org, text), compute)
    return out


def _turn_cost_no_cache(turns: int, det: Detector) -> float:
    """Total ms to mask a whole multi-step turn WITHOUT cache (re-mask every msg
    every call). transcript grows by one msg per call -> sum is O(n^2)."""
    vault = Vault(":memory:", "nc")
    transcript: list[str] = []
    t0 = time.perf_counter()
    for i in range(turns):
        transcript.append(f"{_PII_MSG} шаг {i}")
        for msg in transcript:
            _mask_no_cache(msg, det, vault)
    return (time.perf_counter() - t0) * 1000


def _turn_cost_cached(turns: int, det: Detector) -> float:
    vault = Vault(":memory:", "c")
    cache = MaskCache(capacity=100000)
    transcript: list[str] = []
    t0 = time.perf_counter()
    for i in range(turns):
        transcript.append(f"{_PII_MSG} шаг {i}")
        for msg in transcript:
            _mask_cached(msg, det, vault, cache, "c")
    return (time.perf_counter() - t0) * 1000


def main() -> None:
    det = Detector()
    det.detect("warm")  # warm the dictionaries

    print("=== O(n^2) growing-transcript turn cost (sum over all LLM calls) ===")
    print(f"{'turns':>6}{'BEFORE ms':>12}{'AFTER ms':>12}{'speedup':>10}")
    for turns in (5, 10, 20, 40):
        before = _turn_cost_no_cache(turns, det)
        after = _turn_cost_cached(turns, det)
        speedup = before / after if after else float("inf")
        print(f"{turns:>6}{before:>12.1f}{after:>12.1f}{speedup:>9.1f}x")

    print("\n=== single-message latency: SHORT vs LONG (warm) ===")
    vault = Vault(":memory:", "single")
    cache = MaskCache(capacity=100000)
    short = _PII_MSG
    long = (_PII_MSG + " ") * 40  # ~one big concatenated message
    for label, text in [("SHORT (1 sentence)", short), ("LONG (~40x)", long)]:
        # cold (miss) then warm (hit)
        c = MaskCache(capacity=100000)
        v = Vault(":memory:", "x")
        t = time.perf_counter(); _mask_cached(text, det, v, c, "x"); cold = (time.perf_counter() - t) * 1000
        t = time.perf_counter(); _mask_cached(text, det, v, c, "x"); warm = (time.perf_counter() - t) * 1000
        print(f"  {label:<22} miss(detect)={cold:7.2f} ms   hit(cache)={warm:7.4f} ms")

    print("\n=== pre-filter win: masking a no-PII message ===")
    v = Vault(":memory:", "pf")
    c = MaskCache(capacity=100000)
    n = 1000
    t = time.perf_counter()
    for _ in range(n):
        _mask_no_cache(_PLAIN_MSG, det, v)
    no_pf = (time.perf_counter() - t) * 1000 / n
    t = time.perf_counter()
    for _ in range(n):
        _mask_cached(_PLAIN_MSG, det, v, c, "pf")  # prefilter sees no Cyrillic -> skip... but it HAS cyrillic? no, latin
    pf = (time.perf_counter() - t) * 1000 / n
    print(f"  no-PII Latin message: detect-always={no_pf:.3f} ms/msg   prefilter-skip={pf:.4f} ms/msg")


if __name__ == "__main__":
    main()
