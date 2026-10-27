"""Collect the full transcripts of every hop of the five manual runs.

The report files the harness writes are truncated (4000 chars per leg) and carry
only the COUNT of replacements. Forensics needs the replacements themselves —
path, type, the real slice and the substitute the model was shown — because the
defects the owner sees are relations BETWEEN hops: one value replaced two ways,
two values replaced by one string, a substitute that never resolved.

Writes `.state/qa/forensics/tester-<n>.json`: attempts in order, each with
source_request, model_request, model_response, restored_response,
tool_dispatches and the full replacement table.

    python3 collect_forensics.py [--testers 1,2,3,4,5]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
OUT = STATE / "qa" / "forensics"
BASE = "http://127.0.0.1:18880"
API = "http://127.0.0.1:18860"


def password() -> str:
    return json.loads((STATE / "runtime" / "browser.json").read_text())["password"]


def newest_thread(user_id: str) -> str | None:
    script = (
        "const t = db.threads.find({user_id: '" + user_id + "'}).sort({created_at:-1}).limit(1).toArray();"
        "print(t.length ? t[0].thread_id : '')")
    result = subprocess.run(
        ["docker", "exec", "obscura-doubleup-pilot-mongodb-1", "mongosh", "doubleup_pilot",
         "--quiet", "--eval", script],
        capture_output=True, text=True, timeout=30, check=False)
    lines = (result.stdout or "").strip().splitlines()
    return lines[-1].strip() if lines and lines[-1].strip() else None


def walk(payload, path: str):
    """Resolve `/messages/1/content` (and list indices) inside the JSON body."""
    node = payload
    for chunk in [part for part in path.split("/") if part]:
        if isinstance(node, list):
            node = node[int(chunk)]
        else:
            node = node[chunk]
    return node


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testers", default="")
    args = parser.parse_args()
    wanted = [int(part) for part in args.testers.split(",") if part.strip()] or [1, 2, 3, 4, 5]
    OUT.mkdir(parents=True, exist_ok=True)
    secret = password()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for index in wanted:
            user_id = f"pilot-tester-{index}"
            context = browser.new_context(viewport={"width": 1440, "height": 1300}, locale="ru-RU")
            page = context.new_page()
            page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90_000)
            page.fill('input[name="user_id"]', user_id)
            page.fill('input[name="password"]', secret)
            page.click('button:has-text("Войти")')
            page.wait_for_url(lambda url: "/login" not in url, timeout=60_000)
            page.wait_for_timeout(2_500)
            token = page.evaluate("localStorage.getItem('auth_access_token')")
            org = page.evaluate("JSON.parse(localStorage.getItem('user_info')).org_id")
            headers = {"Authorization": f"Bearer {token}", "X-Org-Id": org}
            thread = newest_thread(user_id)
            attempts: list[dict] = []
            if thread:
                listing = context.request.get(
                    f"{API}/api/v1/pseudex/inspections?thread_id={thread}", headers=headers)
                items = listing.json().get("items", []) if listing.ok else []
                for item in items:
                    detail = context.request.get(
                        f"{API}/api/v1/pseudex/inspections/{item['attempt_id']}", headers=headers)
                    if not detail.ok:
                        continue
                    payload = detail.json()
                    source = payload.get("source_request") or {}
                    replacements = []
                    for row in (payload.get("inspection") or {}).get("replacements") or []:
                        real = None
                        try:
                            text = walk(source, row.get("path", ""))
                            if isinstance(text, str):
                                real = text[row["source_start"]:row["source_end"]]
                        except Exception:
                            real = None
                        replacements.append({
                            "path": row.get("path"), "type": row.get("type"),
                            "real": real, "shown": row.get("shown"),
                            "base_token": row.get("base_token"),
                            "source_start": row.get("source_start"),
                            "source_end": row.get("source_end"),
                        })
                    attempts.append({
                        "attempt_id": item["attempt_id"],
                        "status": item.get("status"),
                        "created_at": item.get("created_at"),
                        "source_request": source,
                        "model_request": payload.get("model_request"),
                        "model_response": payload.get("model_response"),
                        "restored_response": payload.get("restored_response"),
                        "tool_dispatches": payload.get("tool_dispatches"),
                        "replacements": replacements,
                    })
            document = {"tester": user_id, "org": org, "thread": thread, "attempts": attempts}
            (OUT / f"tester-{index}.json").write_text(json.dumps(document, ensure_ascii=False, indent=1))
            print(f"[{user_id}] thread {thread} attempts {len(attempts)} replacements "
                  f"{sum(len(a['replacements']) for a in attempts)}", flush=True)
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
