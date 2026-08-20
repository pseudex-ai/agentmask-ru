"""Tests for the high-load masking optimizations (perf/high-load-masking).

Covers, against the REAL production stack (real Detector + Vault + AuditLog +
the actual FastAPI app, on a temp PSEUDEX_DB_DIR — no mocks, no SQLite stand-in):

  - cache correctness: idempotency, no PII leak, audit de-dup (count once per
    unique (org, content), not once per resend)
  - no-pre-filter leak regression: Latin-keyed KV / single Latin names (no
    digit/Cyrillic/@/Latin-pair signal) are still masked, never passed raw
  - event-loop responsiveness: /health stays fast while a large /mask is in flight
  - unmask round-trip after masking (Vault token determinism end to end)

Run: PSEUDEX_DB_DIR=$(mktemp -d) python3 test_perf_masking.py
(the harness sets a temp dir itself, so just `python3 test_perf_masking.py`).
"""

import asyncio
import json
import os
import re
import tempfile
import time

# Each test process gets a fresh DB dir so audit/vault counts are deterministic.
os.environ.setdefault("PSEUDEX_DB_DIR", tempfile.mkdtemp(prefix="pseudex_perf_"))

import httpx  # noqa: E402

from testkit import load_dev_bundle, start_local_license  # noqa: E402

# BEFORE importing the app: it reads its licensing configuration at import time,
# and this file drives `service.app` through an ASGI transport, which never runs
# the lifespan that would otherwise acquire the lease.
start_local_license()  # noqa: E402

from pseudex.detect_all import Detector  # noqa: E402
from pseudex.maskcache import MaskCache, content_key  # noqa: E402
from pseudex import service  # noqa: E402

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

    key = content_key("orgA", "", "raw text")
    out1, hit1 = cache.get_or_compute(key, compute)
    out2, hit2 = cache.get_or_compute(key, compute)
    assert out1 == out2 == "MASKED"
    assert hit1 is False and hit2 is True
    assert calls["n"] == 1, "compute ran twice for an identical key (cache miss)"
    print("cache hit skips compute OK")


def test_cache_org_isolation() -> None:
    cache = MaskCache(capacity=10)
    ka = content_key("orgA", "", "same content")
    kb = content_key("orgB", "", "same content")
    assert ka != kb, "two orgs must not collide on identical content"
    out_a, _ = cache.get_or_compute(ka, lambda: "A_MASKED")
    out_b, hit_b = cache.get_or_compute(kb, lambda: "B_MASKED")
    assert out_a == "A_MASKED" and out_b == "B_MASKED" and hit_b is False
    print("cache org isolation OK")


def test_cache_lru_bound() -> None:
    cache = MaskCache(capacity=2)
    cache.get_or_compute(content_key("o", "", "1"), lambda: "1")
    cache.get_or_compute(content_key("o", "", "2"), lambda: "2")
    cache.get_or_compute(content_key("o", "", "3"), lambda: "3")  # evicts "1"
    assert len(cache) == 2, "cache exceeded its capacity"
    miss_called = {"n": 0}

    def recompute() -> str:
        miss_called["n"] += 1
        return "1"

    _, hit = cache.get_or_compute(content_key("o", "", "1"), recompute)
    assert hit is False and miss_called["n"] == 1, "evicted entry should be a miss"
    print("cache LRU bound OK")


# --------------------------------------------------------------------------- #
# HTTP integration against the real app
# --------------------------------------------------------------------------- #
def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=service.app)
    # The gateway surface is credentialed, and the credential is READ FROM THE
    # APP rather than restated here. `service` generates a per-process token when
    # the environment does not set one, so a copy in this file would be a second
    # value that has to stay equal to the first — and this test failing with 401
    # is exactly what a drifting copy looks like.
    return httpx.AsyncClient(transport=transport, base_url="http://pseudex",
                             headers={"Authorization": f"Bearer {service.GATEWAY_TOKEN}"})


async def _post(client: httpx.AsyncClient, path: str, payload: dict) -> dict:
    r = await client.post(path, json=payload)
    r.raise_for_status()
    return r.json()


async def _mask(client: httpx.AsyncClient, org: str, messages: list, skip_system: bool = False) -> list:
    body = await _post(client, "/mask", {"org_id": org, "agent_id": "ag", "messages": messages, "skip_system": skip_system})
    return body["messages"]


async def _async_tests() -> None:
    # The ASGI transport does not run the lifespan, so the two things the
    # lifespan does are done here explicitly against the real licensing server
    # started in main(): acquire a lease, then start renewing it.
    service.LICENSE.acquire()
    service.LICENSE.start()
    async with _client() as client:
        # warm models once by hitting health-then-mask
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
        # `/usage` is on the OPERATOR surface, not the gateway one — it discloses
        # what exists to disclose, so it takes the admin credential and not the
        # one every masking call carries. Sending the wrong one returns an error
        # body, and reading a missing key out of it is how that looked from here.
        usage = (await client.get("/usage", params={"org_id": org2},
                                  headers={"Authorization": f"Bearer {service.ADMIN_TOKEN}"})).json()
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
        usage4 = (await client.get("/usage", params={"org_id": org4},
                                   headers={"Authorization": f"Bearer {service.ADMIN_TOKEN}"})).json()
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

        # 6. TOOL SCHEMAS: a worked example in a tool description is PII that
        #    reaches the provider on EVERY call. It must be masked on the public
        #    leg and left alone when the caller flags it as the agent's template.
        org6 = "tools_org"
        tools = [{"type": "function", "function": {
            "name": "find_order",
            "description": "Найти заказ. Пример: телефон +7 999 123-45-67",
            "parameters": {"type": "object", "properties": {
                "phone": {"type": "string", "description": "Телефон, например +7 999 123-45-67"},
            }}}}]
        body = await _post(client, "/mask", {
            "org_id": org6, "agent_id": "ag",
            "messages": [{"role": "user", "content": "привет"}], "tools": tools})
        masked_fn = body["tools"][0]["function"]
        assert "+7 999 123-45-67" not in masked_fn["description"], "LEAK: PII in tool description"
        assert "+7 999 123-45-67" not in masked_fn["parameters"]["properties"]["phone"]["description"], \
            "LEAK: PII in parameter description"
        assert masked_fn["name"] == "find_order", "tool name must never be masked (breaks dispatch)"
        skipped = await _post(client, "/mask", {
            "org_id": org6, "agent_id": "ag", "skip_system": True,
            "messages": [{"role": "user", "content": "привет"}], "tools": tools})
        assert skipped["tools"] == tools, "engine leg must leave the agent's own template untouched"
        print(f"tool-schema masking OK — {masked_fn['description']!r}")

        # 7. STREAMING LEG: a token split across two SSE deltas must still be
        #    detokenized, and the carry must be caller-owned (stateless).
        org7 = "stream_org"
        masked7 = await _mask(client, org7, [{"role": "user", "content": "мой телефон +7 999 123-45-67"}])
        token = re.search(r"\+79\d{9}", masked7[0]["content"]).group()
        carry, out = "", ""
        for delta in ["Перезвоню на ", token[:5], token[5:], " завтра, всё в силе, до связи."]:
            chunk = await _post(client, "/unmask_chunk",
                                {"org_id": org7, "delta": delta, "carry": carry})
            out += chunk["text"]
            carry = chunk["carry"]
        tail = await _post(client, "/unmask_chunk",
                           {"org_id": org7, "delta": "", "carry": carry, "flush": True})
        out += tail["text"]
        assert tail["carry"] == "", "flush must drain the carry"
        assert "+7 999 123-45-67" in out, f"split token not detokenized in stream: {out!r}"
        assert token not in out, "fake token leaked to the user in the stream"
        print(f"/unmask_chunk OK — {out!r}")

        # 8. STREAMED TOOL CALL: the arguments go through /unmask_arguments and
        #    the result must still be JSON. This is the whole reason the endpoint
        #    exists, so the test pins BOTH halves — the streaming path breaking
        #    the object is asserted too, because the tempting simplification is
        #    to route arguments through /unmask_chunk like everything else.
        #
        #    The value carries quotes on purpose: on Russian business traffic
        #    every legal entity is written that way, so this is the common case
        #    and not an edge one.
        #    The value reaches the vault through form-KV typing, where the KEY
        #    types the whole VALUE — which is how a quoted string gets in there
        #    at all: no free-text recogniser produces a span with a quote in it.
        org8 = "stream_tool_org"
        real8 = 'ООО "Заря"'
        masked8 = await _mask(client, org8,
                              [{"role": "user", "content": f"получатель: {real8}"}])
        fake = masked8[0]["content"].split(": ", 1)[1]
        assert fake != real8, "the quoted value was not masked, so nothing is being tested"
        arguments = json.dumps({"company": fake}, ensure_ascii=False)

        restored = await _post(client, "/unmask_arguments",
                               {"org_id": org8, "arguments": [arguments]})
        assert len(restored["arguments"]) == 1, "one argument in, one out"
        try:
            parsed = json.loads(restored["arguments"][0])
        except json.JSONDecodeError as error:
            raise AssertionError(
                f"/unmask_arguments returned unparseable JSON: "
                f"{restored['arguments'][0]!r} ({error})") from error
        assert parsed["company"] == real8, f"tool argument not restored: {parsed!r}"

        # The same string through the TEXT path, which must not be used for this.
        flat = await _post(client, "/unmask_chunk",
                           {"org_id": org8, "delta": arguments, "carry": "", "flush": True})
        try:
            json.loads(flat["text"])
            raise AssertionError(
                "/unmask_chunk produced valid JSON for a quoted value — if that "
                "is now true, /unmask_arguments may be redundant and this test "
                "is the place to decide that deliberately")
        except json.JSONDecodeError:
            pass
        print(f"/unmask_arguments OK — {parsed!r}")


def test_generic_name_key_does_not_over_mask() -> None:
    """REGRESSION (found by the BFCL paired run, not by our own eval sets).

    The structured-KV layer types a value from its key, and `name` is the one
    genuinely ambiguous key: in English payloads it almost always means the name
    OF A THING. Agents pass `{"name": "ideas.txt"}` constantly, and typing that
    as NAME rewrote the agent's own file arguments into Russian personal names —
    corrupting tasks that had nothing to do with PII. A NAME-typed value must
    also LOOK like a person.

    Both directions matter: under-masking here is a leak, over-masking is task
    damage, and this layer exists precisely to catch names NER misses inside
    structure — so the person cases must keep working."""
    detector = Detector()
    # Filenames and paths only — the gate is narrow on purpose. Bare ambiguous
    # words (`test`, `config`) intentionally stay masked: over-masking is the
    # safe side of this trade, and widening the gate silently stopped masking
    # `{"name": "johnsecret"}` (see the leak regression below).
    must_not_mask = ['{"name": "ideas.txt"}', '{"name": "TeamNotes.txt"}',
                     '{"name": "log.txt"}', '{"name": "workspace/notes.md"}']
    must_mask = ['{"имя": "Анна Смирнова"}', '{"name": "John Smith"}',
                 '{"имя": "Смирнова"}', '{"фио": "Кузнецова М.И."}',
                 '{"name": "johnsecret"}']
    for text in must_not_mask:
        spans = [s for s in detector.detect(text) if s.entity_type == "NAME"]
        assert not spans, f"over-masked an identifier: {text} -> {[s.value for s in spans]}"
    for text in must_mask:
        spans = [s for s in detector.detect(text) if s.entity_type == "NAME"]
        assert spans, f"LEAK: person name not masked in {text}"
    print(f"generic-name-key OK — {len(must_not_mask)} identifiers left alone, "
          f"{len(must_mask)} person names still caught")


def main() -> None:
    load_dev_bundle()
    test_generic_name_key_does_not_over_mask()
    test_cache_hit_skips_compute()
    test_cache_org_isolation()
    test_cache_lru_bound()
    asyncio.run(_async_tests())
    print("\nALL PERF-MASKING TESTS PASSED")


if __name__ == "__main__":
    main()
