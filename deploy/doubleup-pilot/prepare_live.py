"""Prepare original, unredacted trace requests for the owner-approved live smoke.

Only model and buffering transport are overridden, explicitly in the manifest.
Unattributed source cases are DIAGNOSTIC ONLY: they cannot become independent
holdout observations or customer-specific performance claims.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from budget import BudgetRefused, load_pricing, quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "prototype"))
from bench.doubleup.langfuse import attribution, metadata_nodes
from bench.doubleup.storage import RunStore

AAD = b"doubleup-original-live-smoke-v1"
MODEL = "deepseek-v4-flash"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def params_of(observation):
    for node, _ in metadata_nodes({"metadata": observation.get("metadata")}):
        value = node.get("llm.invocation_parameters")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                continue
        if isinstance(value, dict):
            return copy.deepcopy(value), "metadata.llm.invocation_parameters"
    params = copy.deepcopy(observation.get("modelParameters") or {})
    if not isinstance(params, dict):
        raise ValueError("model_parameters_unavailable")
    for key in ("tools", "tool_choice", "response_format"):
        if isinstance(params.get(key), str):
            try:
                params[key] = json.loads(params[key])
            except ValueError:
                pass
    return params, "modelParameters_decoded_structured_fields"


def main() -> None:
    runtime = HERE / ".state" / "runtime"
    manifest_path = HERE / ".state" / "live-selection.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        print(json.dumps({"prepared_existing": True, "cases": existing["cases"], "approved_model": MODEL}))
        return
    pricing = load_pricing(HERE / ".state" / "pricing.json")
    source = RunStore("export-local-pilot", False)
    manifest = source.verify()
    candidates = []
    skipped = {}
    for artifact in manifest["artifacts"]:
        if not artifact["file"].startswith("source-"):
            continue
        raw = source.read_encrypted(artifact["file"])
        for trace in raw["trace_details"]:
            attr = attribution(trace)
            for observation in trace.get("pilot_observations_list", []):
                if str(observation.get("type", "")).upper() != "GENERATION":
                    continue
                try:
                    params, origin = params_of(observation)
                    tools = params.get("tools")
                    if not isinstance(tools, list) or not tools:
                        continue
                    messages = observation.get("input")
                    if not isinstance(messages, list) or not messages or not all(isinstance(m, dict) and "role" in m for m in messages):
                        raise ValueError("original_message_envelope_unavailable")
                    original_params = copy.deepcopy(params)
                    params["stream"] = False
                    params.pop("stream_options", None)
                    body = {**params, "model": MODEL, "messages": copy.deepcopy(messages)}
                    estimate = quote(body, pricing)
                    names = sorted({(tool.get("function") or tool)["name"] for tool in tools if isinstance(tool, dict)})
                    case_id = hashlib.sha256(canonical([trace["id"], observation["id"]])).hexdigest()
                    candidates.append({"case_id": case_id, "source_run": source.run_id,
                        "source_artifact": artifact["file"], "trace_id": trace["id"], "observation_id": observation["id"],
                        "source_model": observation.get("model"), "parameter_provenance": origin,
                        "original_parameters": original_params, "body": body,
                        "original_messages_sha256": hashlib.sha256(canonical(messages)).hexdigest(),
                        "messages_unchanged": body["messages"] == messages, "source_tenant_status": attr["tenant_status"],
                        "diagnostic_only": True, "formal_comparative_metrics_eligible": False,
                        "tool_names": names, "quote": estimate})
                except (ValueError, KeyError, TypeError, BudgetRefused) as error:
                    reason = str(error) if isinstance(error, (ValueError, BudgetRefused)) and str(error).isidentifier() else type(error).__name__
                    skipped[reason] = skipped.get(reason, 0) + 1
    # Tool-set stratification and stable hashes, never gateway success or recall.
    chosen = []
    covered = set()
    for candidate in sorted(candidates, key=lambda case: (-len(case["tool_names"]), case["case_id"])):
        key = tuple(candidate["tool_names"])
        if key not in covered:
            chosen.append(candidate)
            covered.add(key)
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        selected = {case["case_id"] for case in chosen}
        chosen.extend(case for case in sorted(candidates, key=lambda case: case["case_id"]) if case["case_id"] not in selected)
        chosen = chosen[:3]
    if not chosen:
        raise SystemExit("no_original_tool_cases_with_bounded_cost")
    upper = sum(case["quote"]["reserved_nano"] * 4 for case in chosen)
    if upper > 10_000_000_000:
        raise SystemExit("complete_four_arm_smoke_would_exceed_budget")
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    payload = canonical({"run_id": "original-live-smoke-v1", "cases": chosen, "model": MODEL,
                         "paid_limit_usd": 10, "one_generation_boundary_smoke": True})
    write_private(runtime / "live-cases.key", key)
    write_private(runtime / "live-cases.aesgcm", nonce + AESGCM(key).encrypt(nonce, payload, AAD))
    summary = {"run_id": "original-live-smoke-v1", "cases": len(chosen), "eligible_candidates": len(candidates),
        "case_ids": [case["case_id"] for case in chosen], "approved_model": MODEL,
        "source_models": sorted({case["source_model"] for case in chosen}),
        "model_override_approved_by_owner": True, "buffered_transport_override": True,
        "source_messages_unmodified": True, "source_tools_unmodified": True,
        "diagnostic_only": True, "formal_comparative_metrics_eligible": False,
        "one_generation_boundary_smoke": True, "tool_execution_tested": False,
        "quotes_four_arms_upper_usd": upper / 1_000_000_000,
        "tool_names": sorted({name for case in chosen for name in case["tool_names"]}),
        "encrypted_payload_sha256": hashlib.sha256(payload).hexdigest(), "skipped": skipped}
    write_private(manifest_path, json.dumps(summary, indent=2).encode())
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
