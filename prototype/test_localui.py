"""The operator surface, exercised against the real apps.

Two things are being proved, and only one of them is "the screens have data":

  1. The OPERATOR SURFACE IS CLOSED. /reveal and the whole log/statistics
     surface must refuse an unauthenticated caller, and /reveal must refuse a
     caller who will not say who they are. These are the checks that keep a
     masking gateway from quietly becoming an unaudited disclosure channel.

  2. THE BILLED NUMBER IS THE RIGHT NUMBER. `requests` used to be
     sum(entities), so a plan sold as 100 000 requests was consumed several
     times faster than the customer was quoted. The test pins the two apart by
     sending traffic whose request count and entity count cannot coincide.

No pytest, per the repo: run it, read the lines, non-zero exit means broken.
"""

import os
import sys
import tempfile
import time

os.environ.setdefault("PSEUDEX_ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("PSEUDEX_GATEWAY_TOKEN", "test-gateway-token")
_TMP = tempfile.mkdtemp(prefix="pseudex-ui-test-")
os.environ["PSEUDEX_DB_DIR"] = _TMP
os.environ["PSEUDEX_UI_ORG"] = "acme"

from fastapi.testclient import TestClient  # noqa: E402

import testkit  # noqa: E402

# A REAL licensing server on a loopback port, not a stub and not a bypass. The
# licence gate is the thing that makes /mask answer 503, so switching it off to
# test the endpoints around it would leave the interesting interaction — an
# operator surface that must stay readable while masking is stopped — untested.
# Must run before `pseudex.service` is imported: it reads its configuration
# from the environment at import time.
os.environ["PSEUDEX_LICENSE_KEY"] = testkit.start_local_license()
testkit.load_dev_bundle()

from pseudex import service  # noqa: E402
from pseudex.localui import server as ui_server  # noqa: E402

service.LICENSE.acquire()

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _client() -> TestClient:
    """The real app, WITHOUT entering it as a context manager.

    Entering would run the lifespan, whose first act is to lease from a real
    licensing server — not this test's subject, and not reachable here.
    `load_dev_bundle` has already put the assets in memory, which is the only
    thing the lifespan arranges that the endpoints below actually need.
    """
    return TestClient(service.app)


AUTH = {"Authorization": f"Bearer {os.environ['PSEUDEX_ADMIN_TOKEN']}"}
GATEWAY = {"Authorization": f"Bearer {os.environ['PSEUDEX_GATEWAY_TOKEN']}"}


def test_operator_surface_is_closed(client: TestClient) -> None:
    closed = []
    for method, path in [("get", "/status"), ("get", "/events"), ("get", "/stats"),
                         ("get", "/reveals"), ("get", "/subscription"),
                         ("get", "/diagnostics"), ("post", "/reveal"),
                         # /usage returns the same tokens and previews as
                         # /events. It was the one endpoint the closing of the
                         # operator surface missed, and next to an open /unmask
                         # it made the whole reveal audit bypassable.
                         ("get", "/usage"),
                         ("post", "/selfcheck")]:
        response = (client.post(path, json={}) if method == "post" else client.get(path))
        if response.status_code != 401:
            closed.append(f"{path}={response.status_code}")
    check("operator endpoints refuse an anonymous caller", not closed,
          f"unprotected={closed or 'none'}")

    wrong = client.get("/status", headers={"Authorization": "Bearer nope"})
    check("a wrong operator token is refused", wrong.status_code == 401)

    # The masking surface has its own credential, held by the customer's gateway.
    anonymous_mask = client.post("/mask", json={"org_id": "acme",
                                 "messages": [{"role": "user", "content": "привет"}]})
    check("masking refuses a caller with no gateway token",
          anonymous_mask.status_code == 401, f"status={anonymous_mask.status_code}")

    # /unmask is a DETOKENIZATION ORACLE — token in, real personal value out.
    # Anonymous access to it made /reveal's access log decorative.
    oracle = client.post("/unmask", json={"org_id": "acme", "response": {}})
    check("detokenization refuses a caller with no gateway token",
          oracle.status_code == 401, f"status={oracle.status_code}")

    open_leg = client.post("/mask", headers=GATEWAY, json={"org_id": "acme",
                           "messages": [{"role": "user", "content": "привет"}]})
    check("the gateway token opens the masking path", open_leg.status_code == 200,
          f"status={open_leg.status_code}")

    # The two credentials must not be interchangeable.
    crossed = client.post("/mask", headers=AUTH, json={"org_id": "acme",
                          "messages": [{"role": "user", "content": "привет"}]})
    check("the operator token does not open the masking path",
          crossed.status_code == 401, f"status={crossed.status_code}")


def test_reveal_requires_an_actor(client: TestClient) -> None:
    masked = client.post("/mask", headers=GATEWAY, json={
        "org_id": "acme", "agent_id": "support-bot",
        "messages": [{"role": "user", "content": "Позвоните на +7 916 214-88-03"}],
    })
    token_text = masked.json()["messages"][0]["content"]

    events = client.get("/events", params={"org_id": "acme"}, headers=AUTH).json()
    phone = next((event for event in events["events"] if event["type"] == "PHONE"), None)
    check("the masked value reached the log", phone is not None)
    if phone is None:
        return
    check("the log shows the real token, not a placeholder",
          phone["token"] in token_text, f"token={phone['token']}")

    anonymous = client.post("/reveal", json={"org_id": "acme", "token": phone["token"]},
                            headers=AUTH)
    check("reveal without an actor is refused", anonymous.status_code == 400,
          f"status={anonymous.status_code}")

    named = client.post("/reveal", headers=AUTH, json={
        "org_id": "acme", "token": phone["token"], "actor": "ui:test-session",
    })
    check("reveal with an actor returns the real value",
          named.status_code == 200 and named.json()["value"] == "+7 916 214-88-03",
          f"value={named.json().get('value')!r}")

    log = client.get("/reveals", params={"org_id": "acme"}, headers=AUTH).json()
    recorded = log["reveals"][0] if log["reveals"] else {}
    check("the reveal was written to the access log",
          recorded.get("actor") == "ui:test-session" and recorded.get("found") is True,
          f"entry={recorded}")
    # The access log is not allowed to become the second copy of the data.
    check("the access log stores no value",
          "+7 916 214-88-03" not in str(log),
          "value found in the access log" if "+7 916" in str(log) else "")

    missing = client.post("/reveal", headers=AUTH, json={
        "org_id": "acme", "token": "vg_not_a_real_token", "actor": "ui:test-session",
    })
    after = client.get("/reveals", params={"org_id": "acme"}, headers=AUTH).json()
    check("a miss is recorded too",
          missing.json()["value"] is None and after["reveals"][0]["found"] is False,
          "a sweep of guessed tokens leaves no other trace")


def test_requests_are_counted_apart_from_entities(client: TestClient) -> None:
    """Three requests carrying six entities must bill as three, not nine."""
    from pseudex.audit import AuditLog

    fresh = AuditLog(os.path.join(_TMP, "billing.db"))
    for _ in range(3):
        fresh.record_request("acme", "agent")
        fresh.record_many("acme", "agent", [
            ("PHONE", "t1", "+7 916 214-88-03"),
            ("NAME", "t2", "Иванов Пётр"),
        ])
    totals = fresh.billing_totals()
    check("requests are counted, not entities",
          totals["requests"] == 3 and sum(totals["entities"].values()) == 6,
          f"requests={totals['requests']} entities={sum(totals['entities'].values())}")

    # A request that finds nothing is still a request — it cannot be derived
    # from the events table at any level of cleverness.
    fresh.record_request("acme", "agent")
    check("a request with no PII is still billable",
          fresh.billing_totals()["requests"] == 4,
          f"requests={fresh.billing_totals()['requests']}")


def test_selfcheck_is_not_billable(client: TestClient) -> None:
    before = service.AUDIT.billing_totals()["requests"]
    result = client.post("/selfcheck", headers=AUTH).json()
    after = service.AUDIT.billing_totals()["requests"]
    check("the self-check proves the round trip",
          result["ok"] and result["restored"] == result["original"]
          and result["masked"] != result["original"],
          f"ok={result['ok']} spans={len(result['spans'])}")
    check("the self-check is not billed", after == before,
          f"{before} -> {after}")
    check("the self-check reports the tokens the interface highlights",
          all(span.get("token") for span in result["spans"]),
          f"spans={[(s['type'], bool(s.get('token'))) for s in result['spans']]}")


def test_ui_refuses_without_a_session() -> None:
    # Entered as a context manager so every request shares ONE event loop. Without
    # it TestClient spins a fresh portal per call, and the module-level
    # httpx.AsyncClient the proxy uses keeps a pool bound to a loop that is
    # already closed. In production there is one long-lived loop, so this is a
    # property of the test harness rather than of the server.
    with TestClient(ui_server.app) as ui:
        check("the interface refuses an unauthenticated api call",
          ui.get("/api/engine/status").status_code == 401)

        bad = ui.post("/api/signin", json={"secret": "wrong"})
        check("a wrong sign-in secret is refused", bad.status_code == 401)

        good = ui.post("/api/signin", json={"secret": ui_server.SIGNIN_TOKEN})
        check("the startup token signs in", good.status_code == 200,
          f"status={good.status_code}")
        session = good.json().get("session", "")

        # The proxy must not be a way to reach anything the page does not use.
        blocked = ui.get("/api/engine/../../etc/passwd",
                     headers={"Authorization": f"Bearer {session}"})
        check("the engine proxy is an allowlist, not a prefix match",
          blocked.status_code == 404, f"status={blocked.status_code}")

        traversal = ui.get("/static/../server.py")
        check("static serving refuses path traversal",
          traversal.status_code == 404, f"status={traversal.status_code}")

        page = ui.get("/")
        policy = page.headers.get("content-security-policy", "")
        check("the page is served with a content security policy",
          "default-src 'self'" in policy and "script-src 'self'" in policy,
          policy[:40])
        # Without this the charts silently render with no widths: style ATTRIBUTES
        # fall back to style-src, and `style-src 'self'` blocks every one of them.
        check("inline style attributes are allowed, injected <style> is not",
          "style-src-attr 'unsafe-inline'" in policy and "style-src 'self'" in policy)
        check("the page is not cached",
          "no-store" in page.headers.get("cache-control", ""))
        check("the sign-in url is not echoed into the page",
          ui_server.SIGNIN_TOKEN not in page.text)

    # The page's inline import map must be permitted by the policy the page is
    # served with. It was not, and the result was a BLANK PAGE in every browser
    # while every header assertion passed. Recomputed here from the served HTML,
    # so editing index.html without the policy following it fails loudly.
    import base64 as _b64, hashlib as _hash, re as _re
    inline = [body for body in _re.findall(r"<script[^>]*>(.*?)</script>",
                                           page.text, _re.DOTALL) if body.strip()]
    missing = [
        body[:40] for body in inline
        if "'sha256-" + _b64.b64encode(_hash.sha256(body.encode()).digest()).decode() + "'"
        not in policy
    ]
    check("every inline script the page carries is allowed by its own CSP",
          not missing and bool(inline),
          f"inline={len(inline)} unallowed={len(missing)}")


def test_actor_cannot_be_forged_through_the_ui() -> None:
    """The whole chain: browser -> UI process -> engine -> access log.

    Run against a REAL engine on a loopback port rather than a stubbed forward,
    because the thing under test is what the proxy does to the body in flight —
    a stub would be asserting my own edit back at me.
    """
    import threading
    import uvicorn

    port = testkit._free_port()
    config = uvicorn.Config(service.app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    if not server.started:
        check("engine came up for the end-to-end check", False, "never started")
        return

    ui_server.ENGINE_URL = f"http://127.0.0.1:{port}"
    with TestClient(ui_server.app) as ui:
        _forgery_checks(ui, server, thread)


def _forgery_checks(ui: TestClient, server, thread) -> None:
        session = ui.post("/api/signin", json={"secret": ui_server.SIGNIN_TOKEN}).json()["session"]
        auth = {"Authorization": f"Bearer {session}"}

        masked = ui.post("/api/engine/mask", headers=auth, json={
            "org_id": "acme", "agent_id": "e2e",
            "messages": [{"role": "user", "content": "мой телефон +7 916 555-11-22"}],
        })
        check("the interface can mask through the proxy", masked.status_code == 200,
              f"status={masked.status_code}")

        events = ui.get("/api/engine/events", headers=auth, params={"org_id": "acme"}).json()
        phone = next((e for e in events["events"]
                      if e["type"] == "PHONE" and e["agent_id"] == "e2e"), None)
        if phone is None:
            check("the end-to-end masked value reached the log", False)
            server.should_exit = True
            return

        forged = ui.post("/api/engine/reveal", headers=auth, json={
            "org_id": "acme", "token": phone["token"], "actor": "директор Иванов",
        })
        log = ui.get("/api/engine/reveals", headers=auth, params={"org_id": "acme"}).json()
        recorded = log["reveals"][0]["actor"] if log["reveals"] else ""
        check("a forged actor is replaced by the session the server validated",
              forged.status_code == 200 and recorded != "директор Иванов"
              and recorded.startswith("ui:"),
              f"recorded={recorded!r}")
        check("the session label is not the session token itself",
              session not in recorded, f"recorded={recorded!r}")

        server.should_exit = True
        thread.join(timeout=10)


def main() -> int:
    client = _client()
    test_operator_surface_is_closed(client)
    test_reveal_requires_an_actor(client)
    test_requests_are_counted_apart_from_entities(client)
    test_selfcheck_is_not_billable(client)
    test_ui_refuses_without_a_session()
    test_actor_cannot_be_forged_through_the_ui()
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        return 1
    print("local UI surface OK — closed to anonymous callers, reveals audited, "
          "requests billed apart from entities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
