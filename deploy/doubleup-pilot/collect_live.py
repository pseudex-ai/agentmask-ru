"""Collect counts and comparisons only; original prompts/values stay encrypted.

No provider calls and no rerun. Responses are associated by immutable attempt and
exact tool-call IDs, never preview/timestamp similarity. An absent call remains
non-comparable rather than a vacuous success.
"""

from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from budget import Ledger, NANO
from stand import HERE, STATE, compose

COLLECT = r'''
import hashlib,json,uuid
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from repository.pseudex_pilot_inspections import get_inspection_store
run="original-live-smoke-v2"
key=Path("/run/pilot/live-cases-v2.key").read_bytes()
raw=(Path("/app/data")/run/"report.aesgcm").read_bytes()
report=json.loads(AESGCM(key).decrypt(raw[:12],raw[12:],(run+":report").encode()))
case_raw=Path("/run/pilot/live-cases-v2.aesgcm").read_bytes()
cases=json.loads(AESGCM(key).decrypt(case_raw[:12],case_raw[12:],b"doubleup-original-live-smoke-v2"))["cases"]
by_case={case["case_id"]:case for case in cases}
store=get_inspection_store();rows=[];comparisons={}
def calls(body):
    result={}
    for choice in (body or {}).get("choices",[]):
        for call in (choice.get("message",{}).get("tool_calls") or []):
            f=call.get("function") or {}
            try:args=json.loads(f.get("arguments",""))
            except (ValueError,TypeError):args=None
            result[(choice.get("index",0),call.get("id"))]={"name":f.get("name"),"args":args}
    return result
for summary in report["arms"]:
    case=by_case[summary["case_id"]]
    org="doubleup-smoke-"+case["case_id"][:12]
    row=store.get_attempt(org,summary["attempt_id"])
    if row is None:raise RuntimeError("stored_attempt_missing")
    receipt=row.get("inspection")
    before=calls(row.get("model_response"));after=calls(row.get("restored_response"))
    changed=sum(k in before and before[k]["args"]!=v["args"] for k,v in after.items())
    declared={t["function"]["name"] for t in case["body"]["tools"]}
    usage=summary.get("usage") or {}
    names=[v["name"] if v["name"] in declared else "<undeclared>" for v in after.values()]
    numeric_usage={k:usage.get(k) for k in ("prompt_tokens","completion_tokens","total_tokens")
                   if isinstance(usage.get(k),(int,float)) and not isinstance(usage.get(k),bool)}
    item={"case":case["case_id"][:12],"arm":summary["arm"],"mode":summary["mode"],
        "status":summary["status"],"tool_calls":len(after),"tool_names":names,
        "tool_call_comparable":bool(after),"schema_valid":summary.get("all_generated_calls_schema_valid"),
        "changed_argument_calls_during_restore":changed if after else None,
        "mask_replacements":len(receipt["replacements"]) if isinstance(receipt,dict) else None,
        "receipt_complete":receipt.get("complete") if isinstance(receipt,dict) else None,
        "message_payload_changed":row["model_request"]["messages"]!=case["body"]["messages"],
        "usage":numeric_usage,"finish_reasons":summary.get("finish_reasons"),
        "actual_tool_executions":len(row.get("tool_dispatches") or []),"attempt_id":summary["attempt_id"]}
    rows.append(item)
    comparisons.setdefault(item["case"],{})[item["arm"]]=list(after.values())
noise=[]
for case,arms in comparisons.items():
    control=arms.get("C",[]);repeat=arms.get("C2",[])
    noise.append({"case":case,"both_controls_called_tools":bool(control and repeat),
        "control_tool_names_equal":[c["name"] for c in control]==[c["name"] for c in repeat] if control and repeat else None,
        "control_arguments_exactly_equal":control==repeat if control and repeat else None,
        "interpretation":"exact_equality_only_not_semantic_task_quality"})
print(json.dumps({"run_id":run,"rows":rows,"control_repeat":noise,
    "model":report["model"],"source_model":report["source_model"],"thinking_mode":report["thinking_mode"],
    "source_messages_unmodified":report["source_messages_unmodified"],
    "source_tool_schemas_unmodified":report["source_tool_schemas_unmodified"],
    "one_generation_boundary_smoke":True,"tool_execution_tested":False,
    "diagnostic_only":True,"formal_comparative_metrics_eligible":False,
    "independent_pii_ground_truth_available":False,"full_agent_outcome_proven":False,
    "upstream_no_log_requested":report["upstream_no_log_requested"],
    "upstream_logging_enforcement_proven":False},sort_keys=True))
'''


def main():
    result = compose(["exec", "-T", "graph_server", "python", "-"], input=COLLECT,
                     text=True, capture_output=True)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    path = STATE / "ledger" / "spend.sqlite3"
    if not path.is_file():
        raise SystemExit("persistent_budget_ledger_missing")
    report["budget"] = Ledger(path).summary()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        known, reserved = connection.execute("SELECT COALESCE(SUM(charged_nano),0),"
            "COALESCE(SUM(CASE WHEN charged_nano IS NULL THEN reserved_nano ELSE 0 END),0) FROM calls").fetchone()
    report["budget"]["known_usage_cost_estimate_usd"] = str(Decimal(known) / NANO)
    report["budget"]["unknown_usage_reservation_usd"] = str(Decimal(reserved) / NANO)
    report["budget"]["provider_invoice_cost_proven"] = False
    target = STATE / "live-summary.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)); target.chmod(0o600)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
