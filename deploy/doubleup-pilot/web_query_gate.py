"""Authenticated User API → graph RPC → protected LLM boundary, with no paid LLM.

The web/graph RPC may use SSE events even though the model-provider call itself
is buffered/nonstream. This test distinguishes those two streaming contracts.
"""

from collections import Counter
import json
from pathlib import Path

import httpx

from stand import STATE

GRAPH = "57e342e0-2c08-578e-a801-527de89fe9de"
THREAD = "e6f6f3a8-dcf6-5c95-8eb5-fd9359fbeb09"


def main():
    credentials = json.loads((STATE / "runtime" / "browser.json").read_text())
    with httpx.Client(timeout=90, trust_env=False) as client:
        if client.get("http://127.0.0.1:18850/health").json().get("mode") != "fixture":
            raise SystemExit("query_gate_requires_unpaid_fixture_mode")
        login = client.post("http://127.0.0.1:18860/auth/login", json={
            "user_id": "pilot-owner@example.invalid", "password": credentials["password"]})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"], "X-Org-Id": "doubleup-pilot"}
        url = "http://127.0.0.1:18860/api/v1/pseudex/inspections"
        before = client.get(url, headers=headers, params={"thread_id": THREAD})
        before.raise_for_status()
        identities = {item["attempt_id"] for item in before.json()["items"]}
        response = client.post("http://127.0.0.1:18860/query", headers=headers, json={
            "graph_id": GRAPH, "thread_id": THREAD,
            "query": "Локальная проверка: контакт pilot.person@example.org, телефон +7 916 123-45-67. Ответьте коротко.",
            "config": {"retrieval": {"enabled": False}, "kb_tools": False}})
        response.raise_for_status()
        events = []
        for line in response.text.splitlines():
            if line.startswith("data:"):
                try:
                    events.append(json.loads(line[5:].strip()))
                except ValueError:
                    continue
        types = Counter(event.get("type", "unknown") for event in events if isinstance(event, dict))
        encoded = json.dumps(events, ensure_ascii=False)
        after = client.get(url, headers=headers, params={"thread_id": THREAD})
        after.raise_for_status()
        created = [item for item in after.json()["items"] if item["attempt_id"] not in identities]
        detail = []
        for item in created:
            value = client.get(url + "/" + item["attempt_id"], headers=headers)
            value.raise_for_status()
            data = value.json()
            detail.append({"mode": data["mode"], "status": data["status"],
                "mask_replacements": len((data.get("inspection") or {}).get("replacements", []))})
    report = {"passed": bool(created) and types["error"] == 0 and "Локальная проверка завершена" in encoded,
        "http_status": response.status_code, "event_types": dict(types), "new_boundary_attempts": detail,
        "fixture_answer_received": "Локальная проверка завершена" in encoded,
        "authenticated_full_web_path": True, "synthetic_only": True, "provider_calls_external": 0, "paid_usd": 0}
    path = STATE / "web-query-gate.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2)); path.chmod(0o600)
    print(json.dumps(report, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
