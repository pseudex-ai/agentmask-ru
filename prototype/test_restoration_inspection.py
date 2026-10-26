"""Opt-in OUT provenance: real core/ASGI, synthetic data, no sockets or model.

Run with the project venv. Only license transport/provider are replaced; real
assets, vault, morphology and endpoint auth run. Receipt oracles slice the wire
snapshots, never assume json.dumps preserved the input's lexical alignment.
"""
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch

_ROOT = Path(__file__).resolve().parent
_TEMP = tempfile.TemporaryDirectory(prefix=".restoration-test-", dir=_ROOT)
os.environ["PSEUDEX_DB_DIR"] = _TEMP.name
os.environ["PSEUDEX_VAULT_ENCRYPTION"] = "off"

import httpx
import testkit

testkit.load_dev_bundle()

from pseudex import proxy, redact, service
from pseudex.audit import AuditLog
from pseudex.detect import Span
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, mask_one
from pseudex.json_fields import scalar_map
from pseudex.maskcache import MaskCache
from pseudex.restoration import RestorationInspection
from pseudex.tenants import Tenant
from pseudex.vault import Vault

DETECTOR = Detector()


def vault(org):
    return Vault(":memory:", org).for_conversation("c")


def context(v):
    return MaskContext(DETECTOR, v, AuditLog(":memory:"), MaskCache(20),
                       v._customer, "test", "c")


def field(node, path):
    for part in path.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def validate(before, after, receipt, semantic=True):
    assert receipt["version"] == 2 and receipt["operation"] == "restore"
    assert receipt["coverage"] == "semantic_transformations"
    assert receipt["offset_unit"] == "unicode_codepoint"
    assert receipt["semantic_complete"] is semantic, receipt
    ids = set()
    for one in receipt["replacements"]:
        assert one["occurrence_id"] not in ids
        ids.add(one["occurrence_id"])
        assert not ({"shown", "raw", "value", "base_token"} & one.keys()), one
        assert one["type"] == "RESTORATION" and one["kind"] == "restoration"
        a, b = one["source_start"], one["source_end"]
        x, y = one["output_start"], one["output_end"]
        source, output = field(before, one["path"]), field(after, one["path"])
        assert 0 <= a < b <= len(source) and 0 <= x <= y <= len(output), one
        if one["granularity"] == "json_leaf":
            assert json.loads(source[a:b]) != json.loads(output[x:y]), one
        else:
            assert one["granularity"] == "span" and source[a:b] != output[x:y]
    if receipt["lexical_complete"]:
        for path in {one["path"] for one in receipt["replacements"]}:
            rebuilt = field(before, path)
            operations = [one for one in receipt["replacements"] if one["path"] == path]
            for one in sorted(operations, key=lambda op: op["source_start"], reverse=True):
                output = field(after, path)
                rebuilt = (rebuilt[:one["source_start"]]
                           + output[one["output_start"]:one["output_end"]]
                           + rebuilt[one["source_end"]:])
            assert rebuilt == field(after, path)
    return receipt["replacements"]


def arguments(raw, v):
    inspection = RestorationInspection("arguments")
    plain = redact.unmask_arguments(raw, v)
    out = redact.unmask_arguments(raw, v, restoration=inspection.field("/arguments/0"))
    assert out == plain, "inspection changed restoration output"
    receipt = inspection.payload("c", "conversation")
    return out, receipt


def test_prose_and_seam():
    v = vault("prose")
    fake = mask_one("ivan@example.com", context(v))
    raw = "😀 prefix " + fake + "; again " + fake + "."
    inspection = RestorationInspection("prose")
    plain = redact.unmask_text(raw, v)
    out = redact.unmask_text(raw, v, restoration=inspection.field("/text"))
    assert out == plain == "😀 prefix ivan@example.com; again ivan@example.com."
    receipt = inspection.payload("c", "conversation")
    entries = validate({"text": raw}, {"text": out}, receipt)
    assert len(entries) == 2 and entries[0]["source_start"] == 9
    assert "ivan@example.com" not in repr(inspection.__dict__)
    assert "ivan@example.com" not in repr(receipt)

    # Exercise the real FINAL splice boundary with candidate passes replaced:
    # rendering changes the accepted value; unchanged and conflict-veto ranges
    # reserve precedence but must NOT become receipt entries.
    raw = "😀 fake noop veto"
    record = RestorationInspection("seam")
    f = record.field("/text")
    with ExitStack() as stack:
        for name in ("_restore_inflected_candidates", "_restore_verbatim_spans",
                     "_conflicting_place_spans", "_restore_reformatted_spans",
                     "_restore_spoken_identifier_spans", "_restore_cued_numbers_spans"):
            stack.enter_context(patch.object(redact, name, return_value=[]))
        stack.enter_context(patch.object(redact.cvc, "restore_spans", return_value=[]))
        stack.enter_context(patch.object(redact.cvc, "drop_uncontexted", side_effect=lambda t, s, *a: s))
        stack.enter_context(patch.object(redact, "_restore_tokens_spans", return_value=[
            (2, 6, "real"), (7, 11, "noop"), (12, 16, "WRONG")]))
        stack.enter_context(patch.object(redact, "_conflicts_with", side_effect=lambda t, c: t == "veto"))
        stack.enter_context(patch.object(redact, "_as_written", side_effect=lambda t, s: "rendered" if t == "real" else t))
        out = redact._unmask(raw, v, redact._Literals([], (), {}), True, False, restoration=f)
    assert out == "😀 rendered noop veto"
    assert len(validate({"text": raw}, {"text": out}, record.payload("c", "conversation"))) == 1
    for raw in ("REDACTED_NAME_1", "Template text: no known substitutes."):
        record = RestorationInspection("template")
        assert redact.unmask_text(raw, v, restoration=record.field("/text")) == raw
        assert not record.payload("c", "conversation")["replacements"]
    print("PASS prose accepted/rendered splice, Unicode offsets, repeated values, veto/noop/template")


def test_json_lexemes():
    v = vault("json")
    # Real literal restoration can contain arbitrary escaped JSON characters.
    literal = 'ООО "Заря" \\ отдел 😀'
    v.remember_shown("Сергей Петров", literal, "NAME")
    raw = (' { "a/b~c" : "Сергей Петров", "items" : [ '
           '"prefix \\\"q\\\" \\\\ 😀 Сергей Петров", {"a/b~c":"Сергей Петров"} ], '
           '"unchanged":"\\ud83d\\ude00", "literal_key":"unchanged" } ')
    out, receipt = arguments(raw, v)
    parsed = json.loads(out)
    assert parsed["a/b~c"] == literal
    assert parsed["items"][0].endswith(literal)
    entries = validate({"arguments": [raw]}, {"arguments": [out]}, receipt)
    assert {one["leaf_path"] for one in entries} == {"/a~1b~0c", "/items/0", "/items/1/a~1b~0c"}
    assert all(one["granularity"] == "json_leaf" for one in entries)
    assert not receipt["lexical_complete"]
    assert literal not in repr(receipt)
    for one in entries:
        assert raw[one["source_start"]] == '"' and out[one["output_start"]] == '"'
    # Escaped source spellings, not a decoded string search in serialized text.
    escaped = json.dumps({"x": "Сергей Петров"}, ensure_ascii=True)
    out, receipt = arguments(escaped, v)
    entries = validate({"arguments": [escaped]}, {"arguments": [out]}, receipt)
    assert len(entries) == 1 and json.loads(out)["x"] == literal
    root = json.dumps("Сергей Петров", ensure_ascii=True)
    out, receipt = arguments(root, v)
    assert json.loads(out) == literal
    assert validate({"arguments": [root]}, {"arguments": [out]}, receipt)[0]["leaf_path"] == ""
    formatted = ' { "x" : "\\ud83d\\ude00", "n":1e2, "b":true, "z":null } '
    out, receipt = arguments(formatted, v)
    assert json.loads(out) == json.loads(formatted)
    assert not receipt["replacements"] and receipt["semantic_complete"]
    assert not receipt["lexical_complete"]
    assert receipt["limitations"] == [{"path": "/arguments/0", "reason": "json_serialization_normalized"}]
    clean = json.dumps({"x": "unchanged"})
    _, receipt = arguments(clean, v)
    assert receipt["lexical_complete"] and not receipt["replacements"]
    print("PASS escaped quotes/backslashes/Unicode, root scalar, repeated paths, semantic vs lexical coverage")


def test_numeric_and_joins():
    v = vault("numeric")
    raw = mask_one('{"cvc":314}', context(v))
    assert json.loads(raw)["cvc"] != 314
    out, receipt = arguments(raw, v)
    assert json.loads(out)["cvc"] == 314
    entries = validate({"arguments": [raw]}, {"arguments": [out]}, receipt)
    assert len(entries) == 1 and entries[0]["leaf_path"] == "/cvc"
    assert raw[entries[0]["source_start"]:entries[0]["source_end"]].isdigit()

    v = vault("joins")
    # Force deterministic address content; run real role ownership/join logic.
    real = "г Торжок, Светлый переулок, д 7, кв 112"
    fake = "г Торжок, Барбарисовый бульвар 3, кв 12"
    with patch("pseudex.vault._fake_place", return_value=fake):
        redact.mask_text(real, v, [Span(0, len(real), "LOC", real)])
    raw = json.dumps({"nested": [{"street": "Барбарисовый бульвар", "house": "3", "flat": "12"}]},
                     ensure_ascii=False)
    out, receipt = arguments(raw, v)
    entries = validate({"arguments": [raw]}, {"arguments": [out]}, receipt)
    assert json.loads(out)["nested"][0]["house"] == "7"
    assert any(one["leaf_path"] == "/nested/0/house" for one in entries), entries
    assert any(one["leaf_path"] == "/nested/0/flat" for one in entries), entries

    document = v.tokenize("4509 123456", "PASSPORT")
    digits = "".join(c for c in document if c.isdigit())
    raw = json.dumps({"doc": {"series": digits[:4], "number": digits[4:]}})
    out, receipt = arguments(raw, v)
    assert json.loads(out)["doc"] == {"series": "4509", "number": "123456"}, out
    entries = validate({"arguments": [raw]}, {"arguments": [out]}, receipt)
    assert {one["leaf_path"] for one in entries} == {"/doc/series", "/doc/number"}

    v.remember_shown("Сергей", "Иван", "NAME")
    raw = json.dumps({"person": {"first_name": "Сергей", "initials": "С."}}, ensure_ascii=False)
    out, receipt = arguments(raw, v)
    assert json.loads(out)["person"]["initials"] == "И."
    entries = validate({"arguments": [raw]}, {"arguments": [out]}, receipt)
    assert {one["leaf_path"] for one in entries} == {"/person/first_name", "/person/initials"}
    print("PASS numeric secret write, nested address/document/initial assignment provenance")


def test_ambiguity_and_content_json():
    v = vault("ambiguity")
    v.remember_shown("Сергей", "Иван", "NAME")
    for raw in ('{"x":"Сергей","x":"Сергей"}',
                '{"x":{"a":"Сергей"},"x":{"b":"Сергей"}}',
                '{"x":"Сергей","\\u0078":"Сергей"}'):
        out, receipt = arguments(raw, v)
        validate({"arguments": [raw]}, {"arguments": [out]}, receipt, semantic=False)
        assert not receipt["replacements"] and not receipt["lexical_complete"]
        assert any(one["reason"] == "duplicate_json_keys" for one in receipt["limitations"])
    assert scalar_map('{"a":1,"a":2}')[1] == "duplicate_json_keys"
    # An unsupported branch changing a leaf without a write hook must not be
    # relabelled as harmless serialization or inferred into a replacement.
    record = RestorationInspection("unsupported")
    f = record.field("/arguments/0")
    f.json('{"x":"before"}', '{"x": "after"}')
    receipt = record.payload("c", "conversation")
    assert not receipt["semantic_complete"] and not receipt["replacements"]
    assert any(one["reason"] == "untracked_json_leaf_change" for one in receipt["limitations"])
    raw = '{broken Сергей'
    out, receipt = arguments(raw, v)
    assert out == '{broken Иван'
    assert validate({"arguments": [raw]}, {"arguments": [out]}, receipt)[0]["granularity"] == "span"

    real = "г Торжок, Светлый переулок, д 7, кв 112"
    fake = "г Торжок, Барбарисовый бульвар 3, кв 12"
    with patch("pseudex.vault._fake_place", return_value=fake):
        redact.mask_text(real, v, [Span(0, len(real), "LOC", real)])
    raw = '{ "street":"Барбарисовый бульвар", "house":"3", "flat":"12", "name":"Сергей" }'
    record = RestorationInspection("content-json")
    out = redact.unmask_text(raw, v, restoration=record.field("/text"))
    assert out == redact.unmask_text(raw, v)
    assert json.loads(out)["house"] == "7" and json.loads(out)["name"] == "Иван"
    entries = validate({"text": raw}, {"text": out}, record.payload("c", "conversation"))
    assert all(one["granularity"] == "json_leaf" for one in entries)
    assert {one["leaf_path"] for one in entries} >= {"/house", "/flat", "/name"}
    print("PASS duplicate/escaped duplicate/container keys incomplete, invalid fallback, JSON-shaped assistant join")


class LicenseTransport:
    def __init__(self):
        self.consumed = 0
    def is_serving(self):
        return True
    def consume(self):
        self.consumed += 1


async def test_http():
    for module in (service, proxy):
        org = "http-" + module.__name__
        v = (module._vault(org) if module is service else module._get_vault(org)).for_conversation("effective")
        v.remember_shown("Сергей", "Иван", "NAME")
        response = {"id": "x", "choices": [{"message": {"role": "assistant", "content": "😀 Сергей",
            "tool_calls": [{"function": {"name": "find", "arguments": '{"who":"Сергей"}'}}]}}]}
        license_transport = LicenseTransport()
        with patch.object(module, "LICENSE", license_transport):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app),
                    base_url="http://asgi", headers={"Authorization": f"Bearer {module.GATEWAY_TOKEN}"}) as client:
                for endpoint, data, key in (("/unmask", {"response": response}, "response"),
                                           ("/unmask_arguments", {"arguments": ['{"who":"Сергей"}']}, "arguments")):
                    body = {"org_id": org, "conversation_id": "effective", "pseudonym_scope": "customer", **data}
                    plain = await client.post(endpoint, json=body)
                    assert plain.status_code == 200, plain.text
                    assert set(plain.json()) == {key}, plain.text
                    # Inspection must not mint, redetect, or introduce billing.
                    with patch.object(Vault, "tokenize", side_effect=AssertionError("restoration minted")), \
                         patch.object(Detector, "detect", side_effect=AssertionError("restoration detected")):
                        inspected = await client.post(endpoint, json={**body, "inspection": True, "request_id": "out-http"})
                    assert inspected.status_code == 200, inspected.text
                    out = inspected.json()
                    assert out[key] == plain.json()[key]
                    receipt = out["inspection"]
                    validate(body, out, receipt)
                    assert receipt["conversation_id"] == "effective" and receipt["pseudonym_scope"] == "customer"
                    assert receipt["request_id"] == "out-http" and receipt["replacements"]
                    assert license_transport.consumed == 0
                    for extra in ({"inspection": "true"}, {"inspection": 1},
                                  {"inspection": True, "request_id": 12},
                                  {"inspection": True, "request_id": " "},
                                  {"inspection": True, "request_id": "x" * 257}):
                        bad = await client.post(endpoint, json={**body, **extra})
                        assert bad.status_code == 400, bad.text
                    legacy = await client.post(endpoint, json={**body, "request_id": 12})
                    assert legacy.json() == plain.json()
                    disabled = await client.post(endpoint, json={**body, "inspection": False})
                    assert disabled.json() == plain.json()
                    wrong = await client.post(endpoint, json=body, headers={"Authorization": "Bearer wrong"})
                    assert wrong.status_code == 401
                    other = await client.post(endpoint, json={**body, "org_id": org + "-other", "inspection": True})
                    assert other.status_code == 200 and not other.json()["inspection"]["replacements"]
                    default = await client.post(endpoint, json={**data, "org_id": org, "inspection": True})
                    assert default.status_code == 200 and default.json()["inspection"]["conversation_id"] == ""
                if module is service:
                    # Streaming is intentionally not advertised/supported here.
                    chunk = await client.post("/unmask_chunk", json={"org_id": org, "delta": "", "carry": "", "flush": True,
                                                                    "inspection": True})
                    assert chunk.status_code == 200 and "inspection" not in chunk.json()
    print("PASS both manual HTTP surfaces: strict opt-in, legacy shape, auth, effective scope, no mint/billing")


async def test_openai_unchanged():
    license_transport = LicenseTransport()
    answer = {"id": "completion", "object": "chat.completion", "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "unchanged"}, "finish_reason": "stop"}]}
    with patch.object(proxy, "LICENSE", license_transport), \
         patch.object(proxy, "_tenant", return_value=Tenant("openai", "https://unused.invalid", "unused")), \
         patch.object(proxy, "_forward", new=AsyncMock(return_value=answer)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy.app), base_url="http://asgi") as client:
            response = await client.post("/v1/chat/completions", json={"model": "synthetic", "messages": [
                {"role": "user", "content": "hello"}], "inspection": True})
            assert response.status_code == 200 and response.json() == answer, response.text
    print("PASS provider /v1/chat/completions JSON unchanged; no provider streaming receipt claim")


def main():
    for test in (test_prose_and_seam, test_json_lexemes, test_numeric_and_joins, test_ambiguity_and_content_json):
        test()
    asyncio.run(test_http())
    asyncio.run(test_openai_unchanged())
    print("6 restoration inspection suites passed (synthetic, no sockets/provider)")


if __name__ == "__main__":
    try:
        main()
    finally:
        _TEMP.cleanup()
