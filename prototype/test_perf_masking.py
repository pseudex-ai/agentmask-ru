"""Tests for the high-load masking optimizations (perf/high-load-masking).

Covers, against the REAL production stack (real Detector + Vault + AuditLog +
the actual FastAPI app, on a temp OBSCURA_DB_DIR — no mocks, no SQLite stand-in):

  - cache correctness: idempotency, no PII leak, audit de-dup (count once per
    unique (org, content), not once per resend)
  - no-pre-filter leak regression: Latin-keyed KV / single Latin names (no
    digit/Cyrillic/@/Latin-pair signal) are still masked, never passed raw
  - event-loop responsiveness: /health stays fast while a large /mask is in flight
  - unmask round-trip after masking (Vault token determinism end to end)

Run: OBSCURA_DB_DIR=$(mktemp -d) python3 test_perf_masking.py
(the harness sets a temp dir itself, so just `python3 test_perf_masking.py`).
"""

import asyncio
import json
import os
import tempfile
import time

# Each test process gets a fresh DB dir so audit/vault counts are deterministic.
os.environ.setdefault("OBSCURA_DB_DIR", tempfile.mkdtemp(prefix="obscura_perf_"))

import httpx  # noqa: E402

from obscura.detect_all import Detector  # noqa: E402
from obscura.maskcache import MaskCache, content_key  # noqa: E402
from obscura import service  # noqa: E402

_PII_MSG = "Здравствуйте, меня зовут Иван Петров, телефон +7 999 123-45-67, доставьте на улицу Ленина 5."


# --------------------------------------------------------------------------- #
# Unit: MaskCache + pre-filter (no HTTP)
# --------------------------------------------------------------------------- #
def test_cache_hit_skips_compute() -> None:
    cache = MaskCache(capacity=10)
    calls = {"n": 0}

    def compute() -> str:
        calls["n"] += 1
        return "MASKED"

    key = content_key("orgA", "raw text")
    out1, hit1 = cache.get_or_compute(key, compute)
    out2, hit2 = cache.get_or_compute(key, compute)
    assert out1 == out2 == "MASKED"
    assert hit1 is False and hit2 is True
    assert calls["n"] == 1, "compute ran twice for an identical key (cache miss)"
    print("cache hit skips compute OK")


def test_cache_org_isolation() -> None:
    cache = MaskCache(capacity=10)
    ka = content_key("orgA", "same content")
    kb = content_key("orgB", "same content")
    assert ka != kb, "two orgs must not collide on identical content"
    out_a, _ = cache.get_or_compute(ka, lambda: "A_MASKED")
    out_b, hit_b = cache.get_or_compute(kb, lambda: "B_MASKED")
    assert out_a == "A_MASKED" and out_b == "B_MASKED" and hit_b is False
    print("cache org isolation OK")


def test_cache_lru_bound() -> None:
    cache = MaskCache(capacity=2)
    cache.get_or_compute(content_key("o", "1"), lambda: "1")
    cache.get_or_compute(content_key("o", "2"), lambda: "2")
    cache.get_or_compute(content_key("o", "3"), lambda: "3")  # evicts "1"
    assert len(cache) == 2, "cache exceeded its capacity"
    miss_called = {"n": 0}

    def recompute() -> str:
        miss_called["n"] += 1
        return "1"

    _, hit = cache.get_or_compute(content_key("o", "1"), recompute)
    assert hit is False and miss_called["n"] == 1, "evicted entry should be a miss"
    print("cache LRU bound OK")


# --------------------------------------------------------------------------- #
# HTTP integration against the real app
# --------------------------------------------------------------------------- #
def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=service.app)
    return httpx.AsyncClient(transport=transport, base_url="http://obscura")


async def _post(client: httpx.AsyncClient, path: str, payload: dict) -> dict:
    r = await client.post(path, json=payload)
    r.raise_for_status()
    return r.json()


async def _mask(client: httpx.AsyncClient, org: str, messages: list, skip_system: bool = False) -> list:
    body = await _post(client, "/mask", {"org_id": org, "agent_id": "ag", "messages": messages, "skip_system": skip_system})
    return body["messages"]


async def _async_tests() -> None:
    async with _client() as client:
        # warm models once (lifespan startup) by hitting health-then-mask
        await client.get("/health")

        # 1. NO LEAK + idempotency: masking the same message twice yields the
        #    identical masked output, and no raw PII survives.
        org = "leak_org"
        m1 = await _mask(client, org, [{"role": "user", "content": _PII_MSG}])
        m2 = await _mask(client, org, [{"role": "user", "content": _PII_MSG}])
        masked1 = m1[0]["content"]
        masked2 = m2[0]["content"]
        assert masked1 == masked2, "re-masking identical content gave different output (non-idempotent)"
        assert "Иван Петров" not in masked1, "LEAK: name survived masking"
        assert "+7 999 123-45-67" not in masked1 and "9991234567" not in masked1.replace(" ", "").replace("-", ""), "LEAK: phone survived"
        assert "Ленина" not in masked1, "LEAK: street survived"
        print("no-leak + idempotency OK")

        # 1b. PRE-FILTER LEAK REGRESSION: these inputs carry NO digit / Cyrillic /
        #     '@' / capital-Latin-PAIR signal, so the removed pre-filter would have
        #     skipped detection and passed them RAW to the model. Detection (KV by
        #     Latin key; single Latin gazetteer name) masks them, so the secret
        #     must NOT survive. Guards against re-introducing a non-superset gate.
        # secrets are distinctive (won't collide with a random token) and carry
        # NO pre-filter signal: no digit, no Cyrillic, no '@', no capital-Latin pair.
        leak_org = "latin_leak_org"
        leak_cases = [
            ('{"name":"johnsecret"}', "johnsecret"),
            ("name: johndoexyz", "johndoexyz"),
            ('{"email":"bobsecretvalue"}', "bobsecretvalue"),
            ('{"phone":"johndoeqq"}', "johndoeqq"),
            ('{"inn":"abcdefgh"}', "abcdefgh"),
            ("Ivan", "Ivan"),
        ]
        for text, secret in leak_cases:
            out = await _mask(client, leak_org, [{"role": "user", "content": text}])
            got = out[0]["content"]
            assert secret not in got, f"PRE-FILTER LEAK: {secret!r} survived masking of {text!r} -> {got!r}"
        print(f"latin pre-filter leak regression OK ({len(leak_cases)} cases masked)")

        # 2. AUDIT de-dup: 5 resends of the same message count the PII ONCE per
        #    unique (org, content), not 5x. (The growing-transcript inflation fix.)
        org2 = "audit_org"
        for _ in range(5):
            await _mask(client, org2, [{"role": "user", "content": _PII_MSG}])
        usage = (await client.get("/usage", params={"org_id": org2})).json()
        counts = usage["protected_counts"]
        # The message has exactly one NAME, one PHONE, one LOC(addr).
        assert counts.get("NAME", 0) == 1, f"NAME audited {counts.get('NAME')} times, expected 1 (dedup)"
        assert counts.get("PHONE", 0) == 1, f"PHONE audited {counts.get('PHONE')} times, expected 1 (dedup)"
        assert counts.get("LOC", 0) == 1, f"LOC audited {counts.get('LOC')} times, expected 1 (dedup)"
        print(f"audit de-dup OK — 5 resends -> counts {counts}")

        # 3. UNMASK ROUND-TRIP: mask, then build a fake model response echoing the
        #    tokens, unmask it, assert real values come back.
        org3 = "roundtrip_org"
        masked = await _mask(client, org3, [{"role": "user", "content": "Телефон +7 999 123-45-67, почта ivan@mail.ru"}])
        masked_text = masked[0]["content"]
        # The model echoes the masked tokens back in its reply:
        response = {"choices": [{"message": {"role": "assistant", "content": f"Подтверждаю: {masked_text}"}}]}
        out = await _post(client, "/unmask", {"org_id": org3, "response": response})
        restored = out["response"]["choices"][0]["message"]["content"]
        assert "9991234567" in restored.replace(" ", "").replace("-", "").replace("+7", "7"), f"phone not restored: {restored}"
        assert "ivan@mail.ru" in restored, f"email not restored: {restored}"
        print("unmask round-trip OK")

        # 4. NO-PII passthrough via the API: a message with no detectable PII is
        #    returned byte-identical (detection finds nothing -> no audit entry).
        org4 = "passthru_org"
        plain = "hello world this is fine"
        out = await _mask(client, org4, [{"role": "user", "content": plain}])
        assert out[0]["content"] == plain, "no-PII passthrough altered a clean message"
        usage4 = (await client.get("/usage", params={"org_id": org4})).json()
        assert usage4["protected_counts"] == {}, "no-PII message produced audit entries"
        print("no-PII passthrough OK")

        # 5. EVENT-LOOP RESPONSIVENESS: fire a large /mask (long transcript) and,
        #    concurrently, a burst of /health. /health must stay fast (the mask
        #    runs in a thread, not on the loop). Before the fix this would block.
        org5 = "loop_org"
        long_transcript = [{"role": "user", "content": f"{_PII_MSG} вариант {i}"} for i in range(60)]

        async def big_mask() -> float:
            t = time.perf_counter()
            await _mask(client, org5, long_transcript)
            return (time.perf_counter() - t) * 1000

        async def health_pings() -> list[float]:
            latencies = []
            # ping health repeatedly while the big mask is in flight
            for _ in range(20):
                t = time.perf_counter()
                r = await client.get("/health")
                assert r.status_code == 200
                latencies.append((time.perf_counter() - t) * 1000)
                await asyncio.sleep(0.005)
            return latencies

        mask_task = asyncio.create_task(big_mask())
        health_task = asyncio.create_task(health_pings())
        mask_ms, health_lat = await asyncio.gather(mask_task, health_task)
        p99_health = sorted(health_lat)[int(len(health_lat) * 0.99) - 1]
        max_health = max(health_lat)
        print(f"event-loop responsiveness: big /mask {mask_ms:.0f} ms; /health p99 {p99_health:.1f} ms, max {max_health:.1f} ms (n={len(health_lat)})")
        # /health must not be starved by the in-flight mask. Generous bound to
        # avoid CI flakiness, but far below the ~hundreds-of-ms the blocking
        # version would show when the mask monopolizes the single loop.
        assert max_health < 200, f"/health starved during /mask (max {max_health:.0f} ms) — event loop blocked"
        print("event-loop responsiveness OK")


def main() -> None:
    test_cache_hit_skips_compute()
    test_cache_org_isolation()
    test_cache_lru_bound()
    asyncio.run(_async_tests())
    print("\nALL PERF-MASKING TESTS PASSED")


if __name__ == "__main__":
    main()
