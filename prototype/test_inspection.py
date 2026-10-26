"""Exact /mask receipts against the real core and ASGI apps, without networking.

Only the licensing transport is replaced: ASGI does not run lifespan and this
script deliberately must not acquire a lease or call a provider. Real leased
assets are loaded via testkit, and Detector/Vault/AuditLog/cache/splices are real.
Run: PYTHONDONTWRITEBYTECODE=1 python test_inspection.py
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

# Keep all test artifacts inside the assigned checkout, even with caller TMPDIR.
_ROOT = Path(__file__).resolve().parent
_TEMP = tempfile.TemporaryDirectory(prefix=".inspection-test-", dir=_ROOT)
assert Path(_TEMP.name).resolve().parent == _ROOT
os.environ["PSEUDEX_DB_DIR"] = _TEMP.name
os.environ["PSEUDEX_VAULT_ENCRYPTION"] = "off"

import httpx
import testkit

testkit.load_dev_bundle()

from pseudex import proxy, service
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, conversation_key, mask_messages, mask_one, mask_tools
from pseudex.inspection import Edit, Inspection, MaskedText, Trace, snapshot
from pseudex.maskcache import MaskCache
from pseudex.vault import Vault


DETECTOR = Detector()


class LicenseTransport:
    def __init__(self):
        self.consumed = 0

    def is_serving(self):
        return True

    def consume(self):
        self.consumed += 1


def context(org="receipt", conversation="c", cache=None, vault=None, audit=None):
    return MaskContext(DETECTOR,
                       (vault if vault is not None else Vault(":memory:", org))
                       .for_conversation(conversation),
                       audit if audit is not None else AuditLog(":memory:"),
                       cache if cache is not None else MaskCache(100), org, "agent", conversation)


def inspected(messages, ctx, tools=None, skip=False):
    receipt = Inspection("core-request")
    ctx = replace(ctx, inspection=receipt)
    out = {"messages": mask_messages(messages, ctx, skip)}
    if tools is not None:
        out["tools"] = mask_tools(tools, ctx, skip)
    out["inspection"] = receipt.payload(ctx.conversation_id, "conversation")
    return out


def field(node, path):
    for component in path.split("/")[1:]:
        component = component.replace("~1", "/").replace("~0", "~")
        node = node[int(component)] if isinstance(node, list) else node[component]
    return node


def validate(raw, out, complete=True):
    receipt = out["inspection"]
    assert receipt["complete"] is complete, receipt["limitations"]
    assert receipt["offset_unit"] == "unicode_codepoint"
    identities = set()
    by_path = {}
    for one in receipt["replacements"]:
        assert one["occurrence_id"] not in identities
        identities.add(one["occurrence_id"])
        source, final = field(raw, one["path"]), field(out, one["path"])
        assert isinstance(source, str) and isinstance(final, str)
        a, b = one["source_start"], one["source_end"]
        x, y = one["output_start"], one["output_end"]
        assert 0 <= a < b <= len(source), one
        assert 0 <= x <= y <= len(final), one
        assert final[x:y] == one["shown"], one
        assert source[a:b] != one["shown"], "an unchanged value was called replaced"
        if one["kind"] == "redaction":
            assert one["base_token"] is None
            assert one["shown"].startswith("REDACTED")
        else:
            assert one["kind"] == "pseudonym"
        by_path.setdefault(one["path"], []).append(one)
    # Rebuild from EXPLICIT receipt operations only, as an independent test
    # oracle. Production never diffs/re-detects/re-mints to obtain its receipt.
    for path, operations in by_path.items():
        rebuilt = field(raw, path)
        for one in sorted(operations, key=lambda item: item["source_start"], reverse=True):
            rebuilt = rebuilt[:one["source_start"]] + one["shown"] + rebuilt[one["source_end"]:]
        if complete:
            assert rebuilt == field(out, path), (path, operations)
    return receipt["replacements"]


def stable(replacements):
    return [{key: value for key, value in one.items() if key != "occurrence_id"}
            for one in replacements]


def test_trace():
    trace = Trace("😀 abcdef tail")
    trace.apply("😀 MARK tail", [Edit(2, 8, "MARK", "PHONE")])
    trace.apply("😀 long-substitute tail", [Edit(2, 6, "long-substitute", "PHONE")])
    got = trace.freeze()
    assert got.complete and len(got.replacements) == 1
    one = got.replacements[0]
    assert (one.source_start, one.source_end, one.output_start, one.output_end) == (2, 8, 2, 17)
    # Overwriting only part of an earlier non-linear replacement cannot claim
    # exact raw offsets. Explicit incomplete is safer than invented provenance.
    trace.apply("😀 lXng-substitute tail", [Edit(3, 4, "X", "NAME")])
    got = trace.freeze()
    assert not got.complete and not got.replacements
    incomplete = Inspection("partial")
    incomplete.record("/messages/0/content", got)
    result = incomplete.payload("dialogue", "conversation")
    assert not result["complete"] and result["limitations"] == [
        {"path": "/messages/0/content", "reason": "non_linear_overlap"}]
    try:
        one.shown = "mutated"
        raise AssertionError("replacement was mutable")
    except FrozenInstanceError:
        pass
    print("PASS trace composition, Unicode offsets, immutable snapshots, explicit incomplete")


def test_cache():
    ctx = context()
    text = "😀 ivan@example.com; ivan@example.com"
    # Warm WITHOUT inspection. Metadata must exist on the first miss, not be
    # reconstructed when a later caller asks to inspect this cached output.
    first = mask_one(text, ctx)
    raw = {"messages": [{"role": "user", "content": text}]}
    with patch.object(DETECTOR, "detect", side_effect=AssertionError("cache re-detected")), \
         patch.object(ctx.audit, "record_many", side_effect=AssertionError("cache re-audited")), \
         patch.object(ctx.vault, "tokenize", side_effect=AssertionError("cache re-minted")):
        out = inspected(raw["messages"], ctx)
    entries = validate(raw, out)
    assert out["messages"][0]["content"] == first
    assert len(entries) == 2 and entries[0]["source_start"] == 2
    assert entries[0]["shown"] == entries[1]["shown"]
    assert entries[0]["base_token"] == entries[1]["base_token"]
    assert entries[0]["base_token"] is not None
    again = inspected(raw["messages"], ctx)
    assert stable(entries) == stable(validate(raw, again))
    # Response JSON objects cannot mutate cached metadata.
    entries[0]["shown"] = "corrupt"
    assert validate(raw, inspected(raw["messages"], ctx))[0]["shown"] != "corrupt"
    for cached in ctx.cache._store.values():
        assert isinstance(cached, MaskedText)
        assert "ivan@example.com" not in repr(cached)
    print("PASS no-flag cache warm, no redetection/remint/audit, repeated occurrences, no raw metadata")


def test_fields_and_exemptions():
    ctx = context("fields")
    raw = {"messages": [
        {"role": "system", "content": "support@example.com"},
        {"role": "user", "content": [{"type": "text", "text": "😀 ivan@example.com"},
                                      {"type": "image_url", "image_url": {"url": "unchanged"}},
                                      {"type": "text", "text": "ivan@example.com"}]},
        {"role": "assistant", "tool_calls": [{"id": "x", "type": "function", "function": {
            "name": "find", "arguments": '{"email":"ivan@example.com","note":"😀"}'}}]},
    ], "tools": [{"type": "function", "function": {"name": "find", "description": "ivan@example.com",
        "parameters": {"type": "object", "properties": {"a/b~c": {"type": "string",
            "description": "ivan@example.com", "title": "support@example.com",
            "enum": ["ivan@example.com"], "default": "ivan@example.com"}}}}}]}
    out = inspected(raw["messages"], ctx, raw["tools"])
    entries = validate(raw, out)
    assert len(entries) == 7, entries
    assert any(one["path"].endswith("/properties/a~1b~0c/description") for one in entries)
    assert any(one["path"] == "/messages/2/tool_calls/0/function/arguments" for one in entries)
    assert "content" not in out["messages"][2]
    assert out["messages"][1]["content"][1] == raw["messages"][1]["content"][1]
    assert out["tools"][0]["function"]["parameters"]["properties"]["a/b~c"]["enum"] == ["ivan@example.com"]
    skipped = inspected(raw["messages"], ctx, raw["tools"], skip=True)
    skipped_entries = validate(raw, skipped)
    assert skipped["messages"][0] == raw["messages"][0] and skipped["tools"] == raw["tools"]
    assert all(not one["path"].startswith(("/tools/", "/messages/0/")) for one in skipped_entries)
    ownctx = context("own", cache=ctx.cache)
    # Same cache/conversation, changing own-values must not reuse old policy.
    ownraw = [{"role": "user", "content": "Здравствуйте, Татьяна"}]
    assert inspected(ownraw, ownctx)["inspection"]["replacements"]
    ownctx = replace(ownctx, vault=ownctx.vault.with_own_values(("Татьяна",)))
    ownout = inspected(ownraw, ownctx)
    assert ownout["messages"] == ownraw and not ownout["inspection"]["replacements"]
    print("PASS multipart/tool description/arguments/pointer escaping/template and own-value exemptions")


def test_echoes():
    ctx = context("echoes")
    real = "8 926 547-82-38"
    shown = mask_one("телефон " + real, ctx).removeprefix("телефон ")
    # Reserve + ordinary direct masking before/after it + neutral post-pass.
    # A second known phone supplies the unbound conservative leg in the SAME
    # field. The replacement lengths all differ, so stage-local offsets fail.
    other = "8 916 123-45-67"
    mask_one("телефон " + other, ctx)
    body = "😀 prefix@example.com; echo " + real[:9] + "; other " + other[:9] + "; tail@example.com"
    messages = [{"role": "assistant", "tool_calls": [{"id": "phone", "type": "function",
        "function": {"name": "find", "arguments": json.dumps({"phone": shown})}}]},
        {"role": "tool", "tool_call_id": "phone", "content": body}]
    raw = {"messages": messages}
    out = inspected(messages, ctx)
    entries = validate(raw, out)
    result_entries = [one for one in entries if one["path"] == "/messages/1/content"]
    assert len(result_entries) == 4, result_entries
    assert {one["kind"] for one in result_entries} == {"pseudonym", "redaction"}
    assert {body[one["source_start"]:one["source_end"]] for one in result_entries} == {
        "prefix@example.com", real[:9], other[:9], "tail@example.com"}
    assert not [one for one in entries if "/arguments" in one["path"]], "own call leaf was called replaced"
    with patch.object(ctx.audit, "record_many", side_effect=AssertionError("echo cache re-audited")), \
         patch.object(ctx.vault, "tokenize", side_effect=AssertionError("echo receipt reminted")):
        again = inspected(messages, ctx)
    assert out["messages"] == again["messages"]
    assert stable(entries) == stable(validate(raw, again))
    # Multipart echoes and unbound result use the exact same capture seam.
    multi = [{"role": "tool", "tool_call_id": "missing", "content": [
        {"type": "text", "text": "😀 " + real[:10]}, {"type": "text", "text": real[:10]}]}]
    unbound = inspected(multi, ctx)
    neutral = validate({"messages": multi}, unbound)
    assert len(neutral) == 2 and all(one["kind"] == "redaction" for one in neutral)
    # Another conversation sees no recorded evidence for these declined cuts.
    foreign = inspected(multi, replace(ctx, vault=ctx.vault.for_conversation("foreign"),
                                      conversation_id="foreign"))
    assert foreign["messages"] == multi and not foreign["inspection"]["replacements"]
    print("PASS reserve→direct→splice→neutral composition, echo cache, multipart, conversation isolation")


def test_redaction():
    ctx = context("opaque")
    raw = {"messages": [{"role": "user", "content": '{"phone":"not-a-phone-value"}'}]}
    out = inspected(raw["messages"], ctx)
    entries = validate(raw, out)
    assert len(entries) == 1 and entries[0]["kind"] == "redaction"
    assert entries[0]["base_token"] is None
    again = inspected(out["messages"], ctx)
    assert again["messages"] == out["messages"] and not again["inspection"]["replacements"]
    print("PASS direct opaque redaction kind/no-token and own-redaction fixed point")


def test_concurrency():
    vault = Vault(":memory:", "threads")
    audit = AuditLog(":memory:")
    cache = MaskCache(100)
    text = [{"role": "user", "content": "😀 ivan@example.com"}]
    def run(index):
        ctx = context("threads", f"conversation-{index}", cache, vault, audit)
        out = inspected(text, ctx)
        validate({"messages": text}, out)
        assert out["inspection"]["conversation_id"] == f"conversation-{index}"
        return out["inspection"]["receipt_id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(run, range(8)))
    assert len(set(ids)) == 8
    assert vault._conversation == "", "shared vault was mutated"
    print("PASS request-local collectors and shared-cache/vault thread isolation")


async def test_http():
    license_transport = LicenseTransport()
    with patch.object(service, "LICENSE", license_transport):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app),
            base_url="http://asgi", headers={"Authorization": f"Bearer {service.GATEWAY_TOKEN}"}) as client:
            raw = {"org_id": "http", "conversation_id": "explicit", "pseudonym_scope": "customer",
                   "messages": [{"role": "user", "content": "😀 ivan@example.com"}]}
            plain = await client.post("/mask", json=raw)
            assert plain.status_code == 200 and set(plain.json()) == {"messages"}
            before = license_transport.consumed
            response = await client.post("/mask", json={**raw, "inspection": True, "request_id": "http-id"})
            assert response.status_code == 200, response.text
            out = response.json()
            assert out["messages"] == plain.json()["messages"]
            assert license_transport.consumed == before + 1, "inspection introduced extra billing"
            entries = validate(raw, out)
            assert len(entries) == 1
            assert out["inspection"]["request_id"] == "http-id"
            assert out["inspection"]["conversation_id"] == "explicit"
            assert out["inspection"]["pseudonym_scope"] == "customer"
            default = await client.post("/mask", json={"messages": raw["messages"], "inspection": True})
            assert default.status_code == 200
            assert default.json()["inspection"]["conversation_id"] == conversation_key(raw["messages"])
            assert default.json()["inspection"]["request_id"]
            for extra in ({"inspection": "true"}, {"inspection": True, "request_id": 12},
                          {"inspection": True, "request_id": ""}):
                bad = await client.post("/mask", json={**raw, **extra})
                assert bad.status_code == 400, bad.text
            # Existing no-flag callers' unrelated request_id fields stay ignored.
            legacy = await client.post("/mask", json={**raw, "request_id": 12})
            assert legacy.status_code == 200 and "inspection" not in legacy.json()
            noauth = await client.post("/mask", json=raw, headers={"Authorization": "Bearer wrong"})
            assert noauth.status_code == 401
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy.app),
        base_url="http://asgi", headers={"Authorization": f"Bearer {proxy.GATEWAY_TOKEN}"}) as client:
        raw = {"org_id": "proxy-http", "messages": [{"role": "user", "content": "ivan@example.com"}]}
        plain = await client.post("/mask", json=raw)
        response = await client.post("/mask", json={**raw, "inspection": True})
        assert plain.status_code == response.status_code == 200
        out = response.json()
        assert out["messages"] == plain.json()["messages"]
        validate(raw, out)
        assert out["inspection"]["conversation_id"] == conversation_key(raw["messages"])
    print("PASS HTTP both /mask legs, exact no-flag shape/equivalence, effective IDs/scope, auth, one billing unit")


def main():
    for test in (test_trace, test_cache, test_fields_and_exemptions, test_echoes,
                 test_redaction, test_concurrency):
        test()
    asyncio.run(test_http())
    print("7 inspection suites passed (no sockets/provider calls)")


if __name__ == "__main__":
    try:
        main()
    finally:
        _TEMP.cleanup()
