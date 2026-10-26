"""Actual platform schema catalog through the licensed container; no tool calls.

Descriptions/titles may be masked, but executable names, types, required fields,
enum/default/const and all other structural schema data must stay identical.
This does not certify the external Jira/mail/CRM integrations themselves.
"""

import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx
from pymongo import MongoClient

from repository.tools_repository import COLLECTION, is_tool_hidden


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def schema_structure(value):
    if isinstance(value, list):
        return [schema_structure(item) for item in value]
    if not isinstance(value, dict):
        return value
    out = {key: item for key, item in value.items() if key not in ("description", "title")}
    # Map KEYS are argument names, not schema metadata. A field called 'title'
    # must survive, as must literal objects inside enum/default/const.
    for key in ("properties", "$defs", "definitions", "patternProperties", "dependentSchemas"):
        if isinstance(out.get(key), dict):
            out[key] = {name: schema_structure(item) for name, item in out[key].items()}
    for key in ("items", "additionalProperties", "unevaluatedProperties", "propertyNames", "contains", "not", "if", "then", "else"):
        if isinstance(out.get(key), (dict, list)):
            out[key] = schema_structure(out[key])
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        if isinstance(out.get(key), list):
            out[key] = [schema_structure(item) for item in out[key]]
    return out


def structural(value):
    if isinstance(value, list):
        return [structural(item) for item in value]
    if not isinstance(value, dict):
        return value
    out = dict(value)
    if isinstance(out.get("function"), dict):
        out["function"] = structural(out["function"])
        return out
    out.pop("description", None)
    for key in ("parameters", "inputSchema", "input_schema"):
        if isinstance(out.get(key), dict):
            out[key] = schema_structure(out[key])
    return out


def main():
    if os.getenv("PSEUDEX_PILOT") != "1" or os.getenv("MONGO_DB_NAME") != "doubleup_pilot":
        raise SystemExit("isolated_pilot_required")
    with MongoClient(os.environ["MONGO_URI"]) as client:
        all_rows = list(client.get_database()[COLLECTION].find({}, {"_id": 0, "name": 1,
            "description": 1, "schema": 1, "module": 1}))
    rows = sorted((row for row in all_rows if not is_tool_hidden(row)), key=lambda row: row["name"])
    if len(rows) < 30 or any(not isinstance(row.get("schema"), dict) for row in rows):
        raise RuntimeError("platform_catalog_incomplete")
    tools = [{"type": "function", "function": {"name": row["name"],
        "description": row.get("description") or "", "parameters": row["schema"]}} for row in rows]
    source = {"org_id": "doubleup-pilot", "conversation_id": "catalog-" + uuid.uuid4().hex,
              "messages": [{"role": "user", "content": "Контрактная проверка схем инструментов."}],
              "tools": tools, "inspection": True}
    with httpx.Client(timeout=90, trust_env=False) as client:
        response = client.post("http://sidecar:8000/mask", json=source,
            headers={"Authorization": "Bearer " + os.environ["PSEUDEX_GATEWAY_TOKEN"]})
    response.raise_for_status()
    masked = response.json()
    assert structural(masked["tools"]) == structural(tools)
    assert [tool["function"]["name"] for tool in masked["tools"]] == [tool["function"]["name"] for tool in tools]
    snapshot = {"source": tools, "masked": masked["tools"], "inspection": masked["inspection"]}
    key = Path(os.environ["PSEUDEX_INSPECTION_KEY_FILE"]).read_bytes()
    nonce = os.urandom(12)
    encrypted = nonce + AESGCM(key).encrypt(nonce, canonical(snapshot), b"doubleup-platform-catalog-v1")
    # Driver captures binary stdout to a PRIVATE file, not the chat or a raw dump.
    sys.stdout.buffer.write(encrypted)
    report = {"passed": True, "platform_catalog_tools": len(rows),
        "hidden_test_or_retired_tools_excluded": len(all_rows) - len(rows),
        "structural_contracts_unchanged": True, "function_names_unchanged": True,
        "source_catalog_sha256": hashlib.sha256(canonical(tools)).hexdigest(),
        "mask_replacements": len(masked["inspection"]["replacements"]),
        "scope": "schema_contract_only_not_tool_execution", "provider_calls": 0, "paid_usd": 0}
    print(json.dumps(report), file=sys.stderr)


if __name__ == "__main__":
    main()
