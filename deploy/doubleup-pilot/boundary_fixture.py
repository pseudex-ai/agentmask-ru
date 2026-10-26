"""Real DoubleUp transport, Redis/Mongo, licensed sidecar and tool execution.

The provider is the local scripted copier, NOT a live model. This experiment
isolates connector round-trip correctness; it cannot measure agent quality.
Only synthetic input is used and stdout contains booleans/counts, never values.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from chat_graph.llm_utils import http_post_with_retry
from chat_graph.security.engine import mask_before_provider
from chat_graph.security.levels import SecurityLevel
from chat_graph.stages.execution_stage import ExecutionStage
from observability.request_context import RequestContext, reset_context, set_context
from repository.pseudex_pilot_inspections import get_inspection_store

ORG = "doubleup-pilot"
USER = "pilot-owner"
GRAPH = "57e342e0-2c08-578e-a801-527de89fe9de"
THREAD = "e6f6f3a8-dcf6-5c95-8eb5-fd9359fbeb09"
SOURCE = 'Контакт Иванов Пётр: pilot.person@example.org, +7 916 123-45-67. Заметка: ООО "Заря".'


def main() -> None:
    if os.getenv("PSEUDEX_PILOT") != "1" or os.getenv("MONGO_DB_NAME") != "doubleup_pilot":
        raise SystemExit("isolated pilot required")
    logging.getLogger("pay_agent").setLevel(logging.WARNING)
    reports = []
    for mode in ("none", "builtin", "pseudex"):
        os.environ["PII_BACKEND"] = mode
        context_token = set_context(RequestContext(uuid.uuid4().hex[:12], user_id=USER, org_id=ORG,
                                                   graph_id=GRAPH, thread_id=THREAD))
        observed = []
        def echo(text: str) -> dict:
            """Store text only in this disposable local test handler."""
            observed.append(text)
            return {"stored": True, "record_id": "fixture-record", "text_equal_to_source": text == SOURCE}
        tool = StructuredTool.from_function(echo, name="pilot_echo", description="Local-only deterministic fixture echo.")
        try:
            prepared = mask_before_provider([HumanMessage(content=SOURCE)], model_name="deepseek-v4-flash",
                graph_id=GRAPH, thread_id=THREAD, org_id=ORG, level=SecurityLevel.HIGH)
            body = {"model": "deepseek-v4-flash", "temperature": 0, "max_tokens": 512,
                    "messages": [{"role": "user", "content": prepared[0].content}],
                    "tools": [convert_to_openai_tool(tool)],
                    "tool_choice": {"type": "function", "function": {"name": "pilot_echo"}}}
            headers = {"Authorization": "Bearer pilot-fixture-no-remote-access",
                "x-litellm-spend-logs-metadata": json.dumps({"billing_tenant_id": ORG,
                    "billing_user_id": USER, "billing_assistant_id": GRAPH, "billing_dialog_id": THREAD})}
            response = http_post_with_retry("http://gateway:4000/v1/chat/completions", headers=headers,
                json_data=body, timeout=60, max_retries=0, retry_delay=0)
            response.raise_for_status()
            completion = response.json()
            call = completion["choices"][0]["message"]["tool_calls"][0]
            arguments = json.loads(call["function"]["arguments"])
            attempt = response.extensions["pseudex_attempt_id"]
            stage = ExecutionStage()
            stage._pilot_attempt_id = attempt
            result = json.loads(stage._execute_single_tool(call["function"]["name"], arguments, [tool]))
            if len(observed) != 1 or result.get("stored") is not True:
                raise RuntimeError("fixture tool did not execute exactly once")
            get_inspection_store().append_tool_dispatch(attempt, {
                "stage": "executed", "tool_call_id": call["id"], "name": call["function"]["name"],
                "arguments": arguments, "result": result,
                "created_at": datetime.now(timezone.utc).isoformat()})
            history = [*body["messages"], completion["choices"][0]["message"],
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)}]
            followup = {**body, "messages": history}
            followup.pop("tool_choice")
            second = http_post_with_retry("http://gateway:4000/v1/chat/completions", headers=headers,
                json_data=followup, timeout=60, max_retries=0, retry_delay=0)
            second.raise_for_status()
            stored = get_inspection_store().get_attempt(ORG, attempt)
            receipt = stored.get("inspection")
            reports.append({"mode": mode, "tool_executed": True,
                "tool_argument_equal": observed[0] == SOURCE, "second_turn_ok": True,
                "inspection_recorded": isinstance(receipt, dict),
                "inspection_complete": receipt.get("complete") if isinstance(receipt, dict) else None,
                "replacements": len(receipt.get("replacements", [])) if isinstance(receipt, dict) else None,
                "attempt_id": attempt})
        finally:
            reset_context(context_token)
    if not reports[0]["tool_argument_equal"] or not reports[2]["tool_argument_equal"]:
        raise RuntimeError("control or Pseudex connector round-trip failed")
    print(json.dumps({"fixture_only": True, "provider_calls_external": 0, "paid_usd": 0,
                      "arms": reports, "agent_quality_measured": False}))


if __name__ == "__main__":
    main()
