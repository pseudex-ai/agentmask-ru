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
from pathlib import Path

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

from pseudex import license as license_module  # noqa: E402
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
                         # /metrics says how many people this customer protected
                         # today and in which categories — a description of their
                         # business, and at a small enough scale of their traffic.
                         # Every other product leaves /metrics open because «it is
                         # just numbers»; this one has no claim to the exception.
                         ("get", "/metrics"),
                         ("post", "/selfcheck")]:
        response = (client.post(path, json={}) if method == "post" else client.get(path))
        if response.status_code != 401:
            closed.append(f"{path}={response.status_code}")
    check("operator endpoints refuse an anonymous caller", not closed,
          f"unprotected={closed or 'none'}")

    wrong = client.get("/status", headers={"Authorization": "Bearer nope"})
    check("a wrong operator token is refused", wrong.status_code == 401)

    # THE VERSION THE OPERATOR SEES IS THE VERSION THE BUILD IS (D-053). It used
    # to be a constant that said "1.0.0" on every image ever shipped; the one
    # source is version.txt, and /status must read from it, not from memory.
    file_version = (Path(__file__).resolve().parent / "version.txt").read_text(encoding="utf-8").strip()
    status = client.get("/status", headers=AUTH).json()
    check("/status names the version from version.txt",
          status["engine"]["version"] == file_version,
          f"status={status['engine'].get('version')!r} file={file_version!r}")
    # THE VERDICT TRAVELS WITH THE VERSION (D-055). The local licensing server
    # here has no registry, so every field the server did not say is None —
    # and None must reach the screen as «неизвестно», never as «новейшая».
    release = status["engine"].get("release") or {}
    check("/status carries engine.release with the version and the server's verdict fields",
          release.get("version") == file_version
          and set(release) >= {"running_latest", "latest", "latest_in_cycle", "min_supported",
                               "deprecated_at", "sunset_at", "notice", "upgrade"}
          and release["running_latest"] is None and release["latest"] is None,
          f"release={release!r}")
    subscription = client.get("/subscription", headers=AUTH).json()
    check("/subscription mirrors the same release verdict",
          subscription.get("release") == release, f"{subscription.get('release')!r}")
    # BOTH SIDES OF THE SCHEMA CONTRACT (D-060): what the image understands and
    # what this process found the volume at. The audit log is opened at import,
    # so its volume number is known; the vault is per org and may not be yet.
    from pseudex import schema  # noqa: PLC0415
    schema_block = status["engine"].get("schema") or {}
    check("/status carries engine.schema with the image's maxima and the volume's numbers",
          schema_block.get("binary") == schema.versions()
          and schema_block.get("volume", {}).get("audit") == schema.versions()["audit"],
          f"schema={schema_block!r}")

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


def test_license_alarm_is_silent_while_healthy(client: TestClient) -> None:
    """`/license` is the ALARM, and an alarm stuck ON is an alarm nobody keeps.

    The docstring on `service.py::license_status` tells customers to point
    monitoring here precisely because `/health` must stay 200 through the grace
    window — an orchestrator that restarts a degraded container needs a fresh
    lease, which is the thing that is unavailable, so a failing healthcheck turns
    a survivable outage into an unrecoverable one.

    That endpoint compared `status.state != "leased"` while the wire value of
    `STATE_LEASED` is `"active"`, so it answered 503 on a perfectly healthy
    container — for its whole life, on the leg the documentation points at. The
    proxy leg had the mirror defect: 200 unconditionally, an alarm that could not
    fire at all.

    Checked HERE, and not only in gate L4, because the gates cost a container and
    fifteen minutes and run nightly; this file runs on every push. A one-line
    comparison is exactly the kind of thing that regresses between releases.
    """
    healthy = client.get("/license")
    check("the licence alarm is silent while leased",
          healthy.status_code == 200,
          f"{healthy.status_code} state={healthy.json().get('state')}")
    check("the licence alarm reports the leased state by its own constant",
          healthy.json().get("state") == license_module.STATE_LEASED,
          f"state={healthy.json().get('state')!r} "
          f"STATE_LEASED={license_module.STATE_LEASED!r}")
    # /health stays 200 for the reason above, and the two must not be confused.
    check("liveness answers 200 while serving",
          client.get("/health").status_code == 200)


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


def test_metrics_carry_counts_and_never_values(client: TestClient) -> None:
    """The scrape must be a READ, must parse, and must hold no personal value.

    The last one is not a formality: this endpoint is polled every fifteen
    seconds for ever and its output lands in a time-series database that lives
    outside the container. A value that leaked here would be copied for ever, by
    design, into the one place the vault exists to keep it out of.
    """
    headers = AUTH
    body = {"org_id": "metrics-org", "messages": [{
        "role": "user",
        "content": "Иванов Пётр Сергеевич, +7 916 214-88-03, ул. Ленина 14 кв 3",
    }]}
    masked = client.post("/mask", json=body,
                         headers=GATEWAY)
    check("traffic to measure went through", masked.status_code == 200,
          f"status={masked.status_code}")

    scrape = client.get("/metrics", params={"org_id": "metrics-org"}, headers=headers)
    text = scrape.text
    check("the scrape answers and is Prometheus text",
          scrape.status_code == 200 and "text/plain" in scrape.headers.get("content-type", ""),
          scrape.headers.get("content-type", ""))

    names = [line.split()[2] for line in text.splitlines() if line.startswith("# TYPE ")]
    check("no metric name is declared twice", len(names) == len(set(names)),
          str([n for n in names if names.count(n) > 1]))
    # Prometheus fails a scrape WHOLE, so one unparseable line takes down every
    # metric in the response rather than its own.
    malformed = [line for line in text.splitlines()
                 if line and not line.startswith("#") and len(line.rsplit(" ", 1)) != 2]
    check("every sample line parses", not malformed, str(malformed[:3]))

    leaked = [value for value in ("Иванов", "Пётр", "214-88-03", "Ленина")
              if value in text]
    check("no personal value reaches the scrape", not leaked, str(leaked))
    check("the ladder is four series and not an enum",
          'pseudex_license_state{state="active"}' in text
          and 'pseudex_license_state{state="expired"}' in text)
    check("what was protected is there, by TYPE — a closed set of nine",
          "pseudex_values_today{" in text and "pseudex_requests_today" in text)

    # A SCRAPE MAY NOT MINT OR BILL. It runs for ever on a timer; a diagnostic
    # that moves the number it reports is not one — the same rule `/spans` and
    # `peek_token` already live by.
    before = client.get("/metrics", params={"org_id": "metrics-org"},
                        headers=headers).text
    for _ in range(3):
        client.get("/metrics", params={"org_id": "metrics-org"}, headers=headers)
    after = client.get("/metrics", params={"org_id": "metrics-org"},
                       headers=headers).text

    def requests_line(text: str) -> str:
        return next((line for line in text.splitlines()
                     if line.startswith("pseudex_requests_today")), "")
    check("scraping does not bill the customer for being scraped",
          requests_line(before) == requests_line(after),
          f"{requests_line(before)!r} -> {requests_line(after)!r}")


def test_agent_prompt_is_quoted_not_paraphrased() -> None:
    """Экран «Интеграция» обязан ЦИТИРОВАТЬ инструкцию агенту, а не пересказывать.

    Она живёт в `docs/integration.md` и подпёрта живым замером v4
    (`docs/tz-agentpii4.md` §7). На экране стоял пересказ той же мысли другими
    словами — то есть клиент получал ДВЕ РЕДАКЦИИ одной инструкции и должен был
    сам решать, какая правильная. Расхождение вернётся при первой же правке
    формулировки, если его ничто не держит; вот оно и держит.

    Сверяются СЛОВА, а не форматирование: в документации строка обёрнута под
    ширину markdown, на экране — под ширину блока кода, и требовать совпадения
    переносов значило бы ломать проверку на каждой правке вёрстки.
    """
    root = Path(__file__).resolve().parent.parent
    doc = (root / "docs" / "integration.md").read_text(encoding="utf-8")
    app = (root / "prototype" / "pseudex" / "localui" / "static" / "app.js").read_text(
        encoding="utf-8")

    # ПЕРЕИМЕНОВАННЫЙ ЗАГОЛОВОК ИЛИ КОНСТАНТА — ЭТО ПРОВАЛ, А НЕ ОБРЫВ ПРОГОНА.
    # `.index()` бросал ValueError, а эта проверка идёт не последней: падение
    # здесь молча уносило с собой две следующие, про сессию интерфейса и про
    # подделку actor. Тот же класс, что уже чинился в наборе предполёта.
    try:
        section = doc[doc.index("## Инструкция агенту"):]
        # ДО СЛЕДУЮЩЕГО ЗАГОЛОВКА, А НЕ ДО КОНЦА ФАЙЛА: любая цитата, добавленная
        # ниже по документу, иначе приклеилась бы к ожидаемой строке и покраснела
        # бы при полностью синхронном промпте.
        cut = section.find("\n## ", 1)
        if cut != -1:
            section = section[:cut]
        quoted = " ".join(" ".join(line[2:].split()) for line in section.splitlines()
                          if line.startswith("> "))
        start = app.index("const AGENT_PROMPT = `") + len("const AGENT_PROMPT = `")
        screen = " ".join(app[start:app.index("`;", start)].split())
    except ValueError as error:
        check("инструкция агенту на экране — цитата, а не пересказ", False,
              f"не нашёл, откуда сверять: {error}")
        return

    check("инструкция агенту на экране — цитата, а не пересказ",
          quoted == screen,
          f"документация: {quoted[:60]!r}… экран: {screen[:60]!r}…")


def main() -> int:
    client = _client()
    test_operator_surface_is_closed(client)
    test_license_alarm_is_silent_while_healthy(client)
    test_reveal_requires_an_actor(client)
    test_requests_are_counted_apart_from_entities(client)
    test_selfcheck_is_not_billable(client)
    test_metrics_carry_counts_and_never_values(client)
    test_agent_prompt_is_quoted_not_paraphrased()
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
