"""Profile the middleware's latency cost.

Part 1 (deterministic, no network): per-message cost of detect + mask + unmask
over the hold-out set — the reproducible "what Obscura adds".
Part 2 (real A/B, needs OBSCURA_UPSTREAM_KEY): the same LLM call WITHOUT the
middleware vs WITH it (mask before + unmask after), so you see real wall-clock
"с ним и без него". The HTTP hop to a local proxy is sub-ms and omitted.
"""

import json
import os
import statistics
import time

from obscura.detect_all import Detector
from obscura.redact import mask_text, unmask_text
from obscura.vault import Vault


def _pct(values: list[float], p: float) -> float:
    return sorted(values)[min(len(values) - 1, int(len(values) * p))]


def part1() -> None:
    with open("holdout.json", encoding="utf-8") as handle:
        cases = [c["text"] for c in json.load(handle)]

    t0 = time.perf_counter()
    detector = Detector()
    load_ms = (time.perf_counter() - t0) * 1000
    detector.detect("разогрев модели")  # warm

    vault = Vault(":memory:", "perf")
    detect_ms: list[float] = []
    mask_ms: list[float] = []
    unmask_ms: list[float] = []
    for text in cases:
        s = time.perf_counter(); spans = detector.detect(text); detect_ms.append((time.perf_counter() - s) * 1000)
        s = time.perf_counter(); masked = mask_text(text, vault, spans); mask_ms.append((time.perf_counter() - s) * 1000)
        s = time.perf_counter(); unmask_text(masked, vault); unmask_ms.append((time.perf_counter() - s) * 1000)

    total = [d + m + u for d, m, u in zip(detect_ms, mask_ms, unmask_ms)]
    print(f"model load (once): {load_ms:.0f} ms")
    print(f"{'stage':<14}{'mean':>8}{'p50':>8}{'p95':>8}  (ms/message)")
    for name, xs in [("detect(NER+regex)", detect_ms), ("mask", mask_ms),
                     ("unmask", unmask_ms), ("TOTAL middleware", total)]:
        print(f"{name:<14}{statistics.mean(xs):>8.1f}{_pct(xs,0.5):>8.1f}{_pct(xs,0.95):>8.1f}")


def part2() -> None:
    key = os.environ.get("OBSCURA_UPSTREAM_KEY")
    if key is None:
        print("\n[part 2 skipped: set OBSCURA_UPSTREAM_KEY for the real A/B]")
        return
    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    detector = Detector()
    vault = Vault(":memory:", "perf2")
    msg = "Не пришёл заказ, мой телефон +7 999 123-45-67, проверьте статус и повторите номер."
    model = "openai/gpt-4.1-mini"

    def call_direct() -> float:
        s = time.perf_counter()
        client.chat.completions.create(model=model, messages=[{"role": "user", "content": msg}])
        return (time.perf_counter() - s) * 1000

    def call_with_obscura() -> float:
        s = time.perf_counter()
        masked = mask_text(msg, vault, detector.detect(msg))
        r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": masked}])
        unmask_text(r.choices[0].message.content or "", vault)
        return (time.perf_counter() - s) * 1000

    n = 6
    without = [call_direct() for _ in range(n)]
    with_mw = [call_with_obscura() for _ in range(n)]
    print(f"\nreal A/B over {n} live calls (gpt-4.1-mini via OpenRouter):")
    print(f"  WITHOUT Obscura: mean {statistics.mean(without):>7.0f} ms")
    print(f"  WITH Obscura   : mean {statistics.mean(with_mw):>7.0f} ms")
    print(f"  overhead       : {statistics.mean(with_mw) - statistics.mean(without):>7.0f} ms")


if __name__ == "__main__":
    part1()
    part2()
