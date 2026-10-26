"""Prove the shipped inline inspection contract over real container HTTP.

Only synthetic values are used. This is not a detection-quality benchmark or a
live agent test. No provider endpoint is called and no raw request is printed.
"""

import json
import os
from pathlib import Path
import uuid

import httpx

HERE = Path(__file__).resolve().parent


def field(document: dict, pointer: str) -> str:
    current = document
    for component in pointer.split("/")[1:]:
        name = component.replace("~1", "/").replace("~0", "~")
        current = current[int(name)] if isinstance(current, list) else current[name]
    assert isinstance(current, str)
    return current


def main() -> None:
    credentials = json.loads((HERE / ".state" / "credentials.json").read_text())
    gateway = {"Authorization": "Bearer " + credentials["gateway"]}
    admin = {"Authorization": "Bearer " + credentials["admin"]}
    conversation = "gate-" + uuid.uuid4().hex
    original = '😀 Напишите на pilot.person@example.org, телефон +7 916 123-45-67, заметка «ООО "Заря"». '
    scope = {"org_id": "doubleup-pilot", "conversation_id": conversation, "pseudonym_scope": "conversation"}
    request = {**scope, "request_id": "request-" + uuid.uuid4().hex, "inspection": True,
        "messages": [{"role": "user", "content": original}],
        "tools": [{"type": "function", "function": {"name": "pilot_echo",
            "description": "Отправка в локальную песочницу. Контакт pilot.operator@example.org",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}]}
    base = os.environ.get("PILOT_INSPECTION_URL", "http://127.0.0.1:18862")
    kind = os.environ.get("PILOT_ENGINE_KIND", "source")
    if base not in ("http://127.0.0.1:18862", "http://127.0.0.1:18863") or kind not in ("source", "compiled"):
        raise SystemExit("only the isolated pilot endpoints are allowed")
    with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
        response = client.post("/mask", headers=gateway, json=request)
        response.raise_for_status()
        masked = response.json()
        inspection = masked["inspection"]
        assert inspection["request_id"] == request["request_id"]
        assert inspection["conversation_id"] == conversation and inspection["complete"]
        assert inspection["offset_unit"] == "unicode_codepoint"
        replacements = inspection["replacements"]
        assert len(replacements) >= 3
        assert len({r["occurrence_id"] for r in replacements}) == len(replacements)
        for item in replacements:
            source = field(request, item["path"])
            output = field(masked, item["path"])
            assert output[item["output_start"]:item["output_end"]] == item["shown"]
            assert source[item["source_start"]:item["source_end"]] != item["shown"]
        assert "pilot.person@example.org" not in json.dumps(inspection)
        plain_request = {k: v for k, v in request.items() if k not in ("inspection", "request_id")}
        repeated = client.post("/mask", headers=gateway, json=plain_request)
        repeated.raise_for_status()
        assert repeated.json() == {key: masked[key] for key in ("messages", "tools")}
        text = masked["messages"][0]["content"]
        arguments = json.dumps({"text": text}, ensure_ascii=False)
        restored = client.post("/unmask_arguments", headers=gateway,
            json={**scope, "arguments": [arguments]})
        restored.raise_for_status()
        assert not restored.json().get("residual_tokens")
        assert json.loads(restored.json()["arguments"][0])["text"] == original
        # OUT/tool: actual JSON-aware restoration operations, not guessed diffs.
        restored_inspected = client.post("/unmask_arguments", headers=gateway,
            json={**scope, "request_id": "out-tool-" + uuid.uuid4().hex,
                  "inspection": True, "arguments": [arguments]})
        restored_inspected.raise_for_status()
        out_tool = restored_inspected.json()
        assert out_tool["arguments"] == restored.json()["arguments"]
        assert out_tool["inspection"]["version"] == 2 and out_tool["inspection"]["semantic_complete"]
        assert out_tool["inspection"]["replacements"]
        for item in out_tool["inspection"]["replacements"]:
            source = field({"arguments": [arguments]}, item["path"])
            output = field(out_tool, item["path"])
            assert source[item["source_start"]:item["source_end"]] != output[item["output_start"]:item["output_end"]]
            assert not any(key in item for key in ("shown", "value", "raw", "base_token"))
        # IN/tool: the tool-return content is masked before the next model call.
        tool_request = {**scope, "inspection": True, "messages": [
            {"role": "user", "content": "Проверьте локальный контакт."},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "gate-call", "type": "function",
                "function": {"name": "pilot_echo", "arguments": arguments}}]},
            {"role": "tool", "tool_call_id": "gate-call", "content": original}]}
        tool_mask = client.post("/mask", headers=gateway, json=tool_request)
        tool_mask.raise_for_status()
        assert any(item["path"] == "/messages/2/content" for item in tool_mask.json()["inspection"]["replacements"])
        # OUT/user: exact accepted text splices in the returned assistant answer.
        raw_answer = {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]}
        answer = client.post("/unmask", headers=gateway, json={**scope, "inspection": True, "response": raw_answer})
        answer.raise_for_status()
        answer_body = answer.json()
        assert answer_body["response"]["choices"][0]["message"]["content"] == original
        assert answer_body["inspection"]["semantic_complete"] and answer_body["inspection"]["replacements"]
        for item in answer_body["inspection"]["replacements"]:
            source, output = field({"response": raw_answer}, item["path"]), field(answer_body, item["path"])
            assert source[item["source_start"]:item["source_end"]] != output[item["output_start"]:item["output_end"]]
        email = next(item for item in replacements if item["type"] == "EMAIL")
        reveal = client.post("/reveal", headers=admin, json={"org_id": scope["org_id"],
            "token": email["base_token"], "actor": "pilot-http-container-gate"})
        reveal.raise_for_status()
        assert reveal.json()["value"] in ("pilot.person@example.org", "pilot.operator@example.org")
        forbidden = client.post("/reveal", headers=gateway, json={"org_id": scope["org_id"],
            "token": email["base_token"], "actor": "pilot-http-container-gate"})
        assert forbidden.status_code == 401
    report = {"kind": "real_" + kind + "_container_http_gate", "passed": True,
              "replacement_count": len(replacements), "exact_source_output_offsets": True,
              "noflag_shape_unchanged": True, "tool_json_roundtrip": True,
              "all_four_hops": True, "out_receipt_version": 2, "no_restored_literals_in_receipt": True,
              "audited_reveal": True, "auth_surfaces_separate": True,
              "synthetic_only": True, "provider_calls": 0, "paid_usd": 0}
    target = HERE / ".state" / ("http-inspection-gate-compiled.json" if kind == "compiled" else "http-inspection-gate.json")
    target.write_text(json.dumps(report, indent=2))
    target.chmod(0o600)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
