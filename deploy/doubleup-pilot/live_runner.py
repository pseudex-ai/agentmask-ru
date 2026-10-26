"""One-generation smoke on original trace inputs through the actual host adapter.

This does NOT execute customer tools or claim full agent-task success. The separate
boundary fixture exercises tool execution; original-trace tool doubles require a
separate causal state model. Each arm writes an exclusive start marker BEFORE the
socket; an interrupted arm is never automatically paid for twice.
"""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx
from jsonschema import Draft202012Validator
from langchain_core.messages import ChatMessage
from pymongo import MongoClient

from chat_graph.llm_utils import http_post_with_retry
from chat_graph.security.engine import mask_before_provider
from chat_graph.security.levels import SecurityLevel
from observability.request_context import RequestContext, reset_context, set_context
from repository.pseudex_pilot_inspections import get_inspection_store

AAD = b"doubleup-original-live-smoke-v1"
USER = "pilot-owner"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def private_write(path, data):
    if not path.resolve().is_relative_to(Path("/app/data").resolve()) or path.is_symlink():
        raise RuntimeError("pilot_result_path_invalid")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def seal(path, value, key, context):
    nonce = os.urandom(12)
    private_write(path, nonce + AESGCM(key).encrypt(nonce, canonical(value), context))


def load(path, key, context):
    raw = path.read_bytes()
    return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], context))


def scope_for(case_id):
    short = case_id[:12]
    org = "doubleup-smoke-" + short
    graph = str(uuid.uuid5(uuid.NAMESPACE_URL, org + "/graph"))
    thread = str(uuid.uuid5(uuid.NAMESPACE_URL, org + "/thread"))
    return {"tenant_id": org, "thread_id": thread, "owner_id": USER, "agent_id": graph}


def seed_scope(db, scope, case_id):
    now = datetime.now(timezone.utc)
    org, graph, thread = (scope[key] for key in ("tenant_id", "agent_id", "thread_id"))
    db.organizations.update_one({"org_id": org}, {"$setOnInsert": {"org_id": org, "slug": org,
        "name": "Оригинальный трейс · " + case_id[:8], "owner_id": USER, "status": "active", "created_at": now}}, upsert=True)
    db.organization_members.update_one({"org_id": org, "user_id": USER}, {"$setOnInsert": {"org_id": org,
        "user_id": USER, "role": "owner", "status": "active", "created_at": now}}, upsert=True)
    db.graphs.update_one({"graph_id": graph}, {"$setOnInsert": {"graph_id": graph, "builtin_id": "simple_chat",
        "type": "builtin", "enabled": True, "user_id": USER, "org_id": org, "public": False,
        "name": "Трейс · " + case_id[:8], "tools": [], "default_tools": [], "security_level": 3,
        "created_at": now, "retrieval": {"enabled": False}, "kb_tools": False}}, upsert=True)
    db.threads.update_one({"thread_id": thread}, {"$setOnInsert": {"thread_id": thread, "org_id": org,
        "graph_id": graph, "user_id": USER, "title": "Оригинальный трейс · " + case_id[:8], "status": "active",
        "created_at": now, "last_activity": now, "message_count": 0}}, upsert=True)


def legacy_prepare(body, scope):
    prepared = copy.deepcopy(body)
    original = [ChatMessage(role=message["role"], content=message["content"]
        if isinstance(message.get("content"), (str, list)) else "") for message in body["messages"]]
    masked = mask_before_provider(original, model_name=body["model"], graph_id=scope["agent_id"],
        thread_id=scope["thread_id"], org_id=scope["tenant_id"], level=SecurityLevel.HIGH)
    for source, transformed in zip(prepared["messages"], masked):
        if isinstance(source.get("content"), str):
            source["content"] = transformed.content
    return prepared


def call_summary(response, request):
    declared = {tool["function"]["name"]: tool["function"]["parameters"] for tool in request.get("tools", [])
                if isinstance(tool, dict) and isinstance(tool.get("function"), dict)}
    calls = []
    for choice in response.get("choices", []):
        for call in (choice.get("message", {}).get("tool_calls") or []):
            function = call.get("function") or {}
            name = function.get("name")
            try:
                arguments = json.loads(function.get("arguments", ""))
                valid = name in declared and isinstance(arguments, dict) and not list(Draft202012Validator(declared[name]).iter_errors(arguments))
            except (ValueError, TypeError):
                valid = False
            calls.append({"name": name, "schema_valid": valid})
    return calls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--revision", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    if os.getenv("PSEUDEX_PILOT") != "1" or os.getenv("MONGO_DB_NAME") != "doubleup_pilot":
        raise SystemExit("isolated_pilot_required")
    runtime = Path("/run/pilot")
    prefix = "live-cases-v2" if args.revision == "v2" else "live-cases"
    aad = b"doubleup-original-live-smoke-v2" if args.revision == "v2" else AAD
    key = (runtime / (prefix + ".key")).read_bytes()
    encrypted = (runtime / (prefix + ".aesgcm")).read_bytes()
    payload = json.loads(AESGCM(key).decrypt(encrypted[:12], encrypted[12:], aad))
    if payload.get("model") != "deepseek-v4-flash" or payload.get("paid_limit_usd") != 10:
        raise SystemExit("owner_approved_model_and_budget_required")
    with httpx.Client(timeout=5, trust_env=False) as client:
        health = client.get("http://gateway:4000/health").json()
    expected = "fixture" if args.dry_run else "live"
    if health.get("mode") != expected:
        raise SystemExit("gateway_mode_does_not_match_smoke_kind")
    access = json.loads((runtime / "model-access.json").read_text()) if not args.dry_run else {"request_key": "pilot-fixture-no-remote-access"}
    run_id = payload["run_id"] + ("-dry" if args.dry_run else "")
    folder = Path("/app/data") / run_id
    folder.mkdir(mode=0o700, exist_ok=True)
    summaries = []
    halt = False
    with MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=5000) as client:
        db = client.get_database()
        for case in payload["cases"]:
            if halt:
                break
            identifier = case["case_id"]
            if not re.fullmatch(r"[0-9a-f]{64}", identifier) or case["body"]["model"] != payload["model"]:
                raise SystemExit("invalid_case_identity_or_model")
            if hashlib.sha256(canonical(case["body"]["messages"])).hexdigest() != case["original_messages_sha256"]:
                raise SystemExit("source_messages_changed")
            scope = scope_for(identifier)
            seed_scope(db, scope, identifier)
            for arm, mode in (("C", "none"), ("C2", "none"), ("B", "builtin"), ("P", "pseudex")):
                name = identifier + "-" + arm
                marker, done = folder / (name + ".started"), folder / (name + ".aesgcm")
                context = (run_id + ":" + name).encode("ascii")
                if done.exists():
                    summaries.append(load(done, key, context)["summary"])
                    continue
                if marker.exists():
                    summaries.append({"case_id": identifier, "arm": arm, "status": "interrupted_delivery_unknown_not_retried"})
                    continue
                os.environ["PII_BACKEND"] = mode
                token = set_context(RequestContext(uuid.uuid4().hex[:12], user_id=USER, org_id=scope["tenant_id"],
                    graph_id=scope["agent_id"], thread_id=scope["thread_id"]))
                summary = {"case_id": identifier, "arm": arm, "mode": mode, "dry_run": args.dry_run,
                    "diagnostic_only": True, "tool_execution_tested": False, "full_agent_outcome_proven": False}
                private_write(marker, canonical({"case_id": identifier, "arm": arm, "started_at": datetime.now(timezone.utc).isoformat()}))
                try:
                    request = legacy_prepare(case["body"], scope)
                    headers = {"Authorization": "Bearer " + access["request_key"],
                        "x-litellm-spend-logs-metadata": json.dumps({"billing_tenant_id": scope["tenant_id"],
                            "billing_user_id": USER, "billing_assistant_id": scope["agent_id"], "billing_dialog_id": scope["thread_id"]})}
                    response = http_post_with_retry("http://gateway:4000/v1/chat/completions", headers=headers,
                        json_data=request, timeout=150, max_retries=0, retry_delay=0)
                    response.raise_for_status()
                    result = response.json()
                    attempt = response.extensions["pseudex_attempt_id"]
                    record = get_inspection_store().get_attempt(scope["tenant_id"], attempt)
                    inspection = record.get("inspection")
                    generated = call_summary(result, case["body"])
                    raw_calls = call_summary(record["model_response"], case["body"])
                    summary.update({"status": "response_received", "attempt_id": attempt,
                        "generated_tool_calls": generated, "generated_tool_call_count": len(generated),
                        "all_generated_calls_schema_valid": all(call["schema_valid"] for call in generated) if generated else None,
                        "tool_call_comparable": bool(generated), "usage": result.get("usage"),
                        "mask_replacements": len(inspection.get("replacements", [])) if isinstance(inspection, dict) else None,
                        "inspection_complete": inspection.get("complete") if isinstance(inspection, dict) else None,
                        "transport_routing_preserved": [call["name"] for call in generated] == [call["name"] for call in raw_calls],
                        "finish_reasons": [choice.get("finish_reason") for choice in result.get("choices", [])]})
                except Exception as error:
                    # A privacy failure/transport error is recorded, not printed
                    # with the response/request body and not automatically retried.
                    summary.update({"status": "failed", "error_type": type(error).__name__})
                    if isinstance(error, httpx.HTTPStatusError):
                        summary["provider_http_status"] = error.response.status_code
                    halt = not args.dry_run
                finally:
                    reset_context(token)
                seal(done, {"summary": summary, "source_case_id": identifier}, key, context)
                summaries.append(summary)
                print(json.dumps({"case_id": identifier[:12], "arm": arm, "status": summary["status"], "dry_run": args.dry_run}), flush=True)
                if halt:
                    break
    report = {"run_id": run_id, "arms": summaries, "model_override_approved": True, "halted_after_failure": halt,
              "diagnostic_only": True, "formal_comparative_metrics_eligible": False,
              "one_generation_boundary_smoke": True, "tool_execution_tested": False,
              "source_messages_unmodified": True, "source_tool_schemas_unmodified": True,
              "source_model": "Qwen3.8", "model": "deepseek-v4-flash", "buffered_transport": True,
              "thinking_mode": payload.get("thinking_mode", "provider_default"),
              "upstream_no_log_requested": not args.dry_run, "upstream_logging_enforcement_proven": False}
    complete = len(summaries) == len(payload["cases"]) * 4 and all(row["status"] in ("response_received", "failed") for row in summaries)
    final = folder / ("report.aesgcm" if complete else "report-partial-" + uuid.uuid4().hex + ".aesgcm")
    if not final.exists():
        seal(final, report, key, (run_id + ":report").encode())
    print(json.dumps({"run_id": run_id, "completed_arms": len(summaries),
        "response_received": sum(row["status"] == "response_received" for row in summaries),
        "failed": sum(row["status"] == "failed" for row in summaries),
        "dry_run": args.dry_run, "diagnostic_only": True}), flush=True)
    if halt or not complete or any(row["status"] != "response_received" for row in summaries):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
