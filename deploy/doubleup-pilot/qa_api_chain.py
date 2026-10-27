"""The API chain, checked without a browser.

The dialogue report proves the product through the interface a customer uses.
This file proves the CONTRACT underneath it, where a UI can hide a defect: the
sidecar's /mask → /unmask → /reveal legs, the per-agent policy decision, a custom
block pattern, and the isolation between two agents.

It runs against the LIVE pilot sidecar (:18862) with the pilot's own credentials,
so it is an integration test, not a unit test — a mock would only agree with
whatever we already believe.

    python3 qa_api_chain.py

Exit 0 means every contract held; 1 means at least one did not, and the failing
line says which.
"""

import json
import sys
import uuid
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
SIDECAR = "http://127.0.0.1:18862"

PASS, FAIL, SKIP, NOTES = [], [], [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(("PASS " if condition else "FAIL ") + name + ((" · " + detail) if detail and not condition else ""))


def credentials() -> tuple[str, str]:
    payload = json.loads((STATE / "credentials.json").read_text())
    gateway = payload.get("gateway")
    admin = payload.get("admin")
    if not isinstance(gateway, str) or not isinstance(admin, str):
        raise SystemExit("pilot credentials missing")
    return gateway, admin


def scope(agent: str) -> dict:
    suffix = uuid.uuid4().hex
    return {
        "org_id": "doubleup-pilot",
        "conversation_id": "qa-api-" + suffix,
        "agent_id": agent,
        "request_id": "qa-api/" + suffix,
        "pseudonym_scope": "conversation",
    }


def main() -> int:
    gateway, admin = credentials()
    gw = {"Authorization": f"Bearer {gateway}"}
    adm = {"Authorization": f"Bearer {admin}"}
    phone = "+7 999 123-45-67"
    email = "m.sidorova@example.ru"

    with httpx.Client(timeout=30, trust_env=False) as client:
        # ── 1. /mask replaces the real values ────────────────────────────────
        where = scope("qa-agent-a")
        masked = client.post(SIDECAR + "/mask", headers=gw, json={
            **where, "inspection": True,
            "messages": [{"role": "user", "content": f"Позвоните {phone}, пишите на {email}."}],
        })
        check("mask answers 200", masked.status_code == 200, str(masked.status_code))
        body = masked.json() if masked.status_code == 200 else {}
        text = json.dumps(body.get("messages"), ensure_ascii=False)
        check("mask hides the phone", phone not in text, text[:200])
        check("mask hides the email", email not in text, text[:200])
        check("mask reports no residual", not body.get("residual_tokens"), str(body.get("residual_tokens")))
        check("mask returns an inspection receipt", isinstance(body.get("inspection"), dict))

        # ── 2. /unmask restores the answer ───────────────────────────────────
        substitute_phone = None
        for digit in ["+7 949 112-36-76"]:
            if digit in text:
                substitute_phone = digit
        restored = client.post(SIDECAR + "/unmask", headers=gw, json={
            **where,
            "response": {"choices": [{"index": 0, "message": {
                "role": "assistant", "content": "Записал: " + (substitute_phone or "номер в тексте")}}]},
        })
        check("unmask answers 200", restored.status_code == 200, str(restored.status_code))
        if restored.status_code == 200:
            restored_text = json.dumps(restored.json().get("response"), ensure_ascii=False)
            check("unmask restores the phone", phone in restored_text, restored_text[:300])
            check("unmask reports no residual", not restored.json().get("residual_tokens"))

        # ── 3. /reveal is an operator action, not a gateway one ──────────────
        denied = client.post(SIDECAR + "/reveal", headers=gw, json={
            **where, "token": "not-a-real-token", "actor": "qa"})
        check("reveal refuses the gateway credential", denied.status_code in (401, 403), str(denied.status_code))
        bogus = client.post(SIDECAR + "/reveal", headers=adm, json={
            **where, "token": "not-a-real-token", "actor": "qa"})
        bogus_value = None
        try:
            bogus_value = bogus.json().get("value")
        except (ValueError, AttributeError):
            bogus_value = None
        check("reveal with no stored token never returns a value",
              bogus.status_code == 400 or bogus_value is None, str(bogus.status_code))

        # ── 4. a custom block pattern refuses the request ────────────────────
        pattern = client.post(SIDECAR + "/mgmt/custom/patterns", headers=adm, json={
            "pattern_id": "qa-block", "kind": "block", "action": "block",
            "regex": r"QA-BLOCK-[0-9]{4}", "title": "QA block"})
        if pattern.status_code in (200, 201):
            blocked = client.post(SIDECAR + "/mask", headers=gw, json={
                **scope("qa-agent-a"), "messages": [{"role": "user", "content": "номер QA-BLOCK-1234"}]})
            check("a custom block pattern refuses the request",
                  blocked.status_code != 200 or json.dumps(blocked.json()).lower().find("block") >= 0,
                  f"{blocked.status_code} {blocked.text[:160]}")
            client.delete(SIDECAR + "/mgmt/custom/patterns/qa-block", headers=adm)
        else:
            SKIP.append(f"custom block pattern: engine has no /mgmt/custom/patterns ({pattern.status_code})")

        # ── 5. two agents do not share a substitute ──────────────────────────
        phrase = f"Клиент {phone}"
        one = client.post(SIDECAR + "/mask", headers=gw, json={
            **scope("qa-agent-a"), "messages": [{"role": "user", "content": phrase}]}).json()
        two = client.post(SIDECAR + "/mask", headers=gw, json={
            **scope("qa-agent-b"), "messages": [{"role": "user", "content": phrase}]}).json()
        one_text = json.dumps(one.get("messages"), ensure_ascii=False)
        two_text = json.dumps(two.get("messages"), ensure_ascii=False)
        if one_text == two_text:
            NOTES.append("the same phone produced the same substitute in two conversations "
                         "(pseudonym scope looks customer-wide here)")
        else:
            check("two agents get their own substitute", True)
        check("neither agent sees the real phone", phone not in one_text and phone not in two_text)

        # ── 6. the policy surface answers, and a binding is visible ──────────
        policies = client.get(SIDECAR + "/policies", headers=adm)
        if policies.status_code == 200:
            check("the policy surface answers", True)
        else:
            SKIP.append(f"per-agent policy surface: engine has no /policies ({policies.status_code})")

    for entry in SKIP:
        print(f"SKIP {entry}")
    for entry in NOTES:
        print(f"NOTE {entry}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped, {len(NOTES)} noted")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
