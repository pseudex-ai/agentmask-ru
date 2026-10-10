"""Deterministic prepare/SDK/grant withdrawal races; no external network."""
import json
from concurrent.futures import ThreadPoolExecutor
import mimetypes
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from test_acquisition_consent_browser import fixtures, SDK, CLIENT_ID
from test_analytics_browser import ROOT, ORIGIN, METRIKA_URL, RYBBIT_URL, CONSENT

PAYLOAD = {"purpose_revision": "acquisition-v1", "affirmative": "1", "browser_consent": "yes"}


def deny(*args, **kwargs):
    raise AssertionError("External network prohibited")


def server_tests():
    from django.core.cache import cache
    from django.test import Client
    from django.utils import timezone
    from accounts.models import User
    from ops import acquisition_consent as c

    client = Client(enforce_csrf_checks=True)
    page = client.get("/analytics/preferences", secure=True)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]
    client.cookies["_ym_uid"] = CLIENT_ID

    def post(path, data=PAYLOAD):
        return client.post("/analytics/" + path, data, secure=True,
                           HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver")

    grant = {**PAYLOAD, "client_id": CLIENT_ID}
    assert post("grant", grant).status_code == 409, "No standalone grant"
    assert client.post("/analytics/prepare", PAYLOAD, secure=True).status_code == 403
    for invalid in ({"browser_consent": "no"}, {"affirmative": "0"}, {"purpose_revision": "old"}):
        assert post("prepare", {**PAYLOAD, **invalid}).status_code == 400
    before = c.AnalyticsGrant.objects.count()
    response = post("prepare")
    assert response.status_code == 200
    cookie = response.cookies[c.MANAGEMENT_COOKIE]
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Lax"
    row = c.AnalyticsGrant.objects.latest("granted_at")
    assert c.AnalyticsGrant.objects.count() == before + 1
    assert not row.client_id and not row.user_id and not row.organization_id
    assert row.expires_at - row.granted_at == timedelta(days=21)
    assert not c.active(row, timezone.now()) and not c.grant_eligible(row, timezone.now())
    original = (row.granted_at, row.reference_at, row.expires_at)
    assert post("prepare").status_code == 200
    row.refresh_from_db()
    assert (row.granted_at, row.reference_at, row.expires_at) == original
    receipt = client.cookies[c.MANAGEMENT_COOKIE].value
    assert post("revoke", {}).status_code == 200
    # The already-started request carries the acknowledged, now revoked cookie.
    client.cookies[c.MANAGEMENT_COOKIE] = receipt
    assert post("grant", grant).status_code == 409
    row.refresh_from_db()
    assert row.revoked_at and not row.client_id
    assert c.AnalyticsGrant.objects.count() == before + 1
    assert post("prepare").status_code == 200, "A NEW explicit choice may prepare"
    new = c.AnalyticsGrant.objects.latest("granted_at")
    assert new.pk != row.pk and not new.client_id
    prepared_at = new.granted_at
    assert post("grant", grant).status_code == 200
    new.refresh_from_db()
    assert new.granted_at > prepared_at and new.reference_at == new.granted_at
    assert new.expires_at - new.granted_at == timedelta(days=21)
    original = (new.granted_at, new.reference_at, new.expires_at)
    with patch("ops.acquisition_views.timezone.now", return_value=new.granted_at + timedelta(hours=1)):
        assert post("grant", grant).status_code == 200
        assert post("prepare").status_code == 200
    new.refresh_from_db()
    assert (new.granted_at, new.reference_at, new.expires_at) == original
    receipt = client.cookies[c.MANAGEMENT_COOKIE].value
    assert post("revoke", {}).status_code == 200, "Grant-first ordering also ends revoked"
    client.cookies[c.MANAGEMENT_COOKIE] = receipt
    assert post("grant", grant).status_code == 409
    assert post("prepare").status_code == 200
    latest = c.AnalyticsGrant.objects.latest("granted_at")
    c.AnalyticsGrant.objects.filter(pk=latest.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert post("grant", grant).status_code == 409
    cache.clear()
    assert post("prepare").status_code == 200
    latest = c.AnalyticsGrant.objects.latest("granted_at")
    user = User.objects.create_user(email="race-bound@example.invalid")
    c.AnalyticsGrant.objects.filter(pk=latest.pk).update(user=user)
    assert post("grant", grant).status_code == 409
    assert post("prepare").status_code == 200
    assert c.AnalyticsGrant.objects.latest("granted_at").pk != latest.pk
    client.force_login(user)
    assert post("prepare").status_code == 409
    cache.clear()
    with patch("storefront_web.views._too_many", return_value=True):
        client.logout()
        page = client.get("/analytics/preferences", secure=True)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]
        assert post("prepare").status_code == 429
    cache.clear()
    assert post("prepare", {**PAYLOAD, "browser_consent": "no"}).status_code == 400
    response = client.post("/signup", {"email": "race-no-consent@example.invalid",
        "company": "Synthetic", "plan": "start", "consent": "1", "terms": "1"},
        secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver")
    assert response.status_code == 200, "Declined analytics must not block signup"
    new_user = User.objects.get(email="race-no-consent@example.invalid")
    assert not c.AnalyticsGrant.objects.filter(user=new_user).exists()


def browser_tests(html, csp):
    from django.core.cache import cache
    from django.test import Client
    from ops import acquisition_consent as c
    from playwright.sync_api import sync_playwright

    delayed_sdk = SDK.replace("a[2]('999999999999999999999999');", "window.__clientCallbacks.push(a[2]);")
    delayed_sdk = "window.__clientCallbacks = [];\n" + delayed_sdk
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for stage in ("sdk", "prepare", "grant"):
            cache.clear()
            with browser.new_context(service_workers="block") as context:
                context.set_default_timeout(5000)
                context.add_cookies([{"name": "_ym_uid", "value": CLIENT_ID, "url": ORIGIN}])
                held, posts, responses, unexpected = [], [], [], []

                def api(route):
                    req = route.request
                    # Exercise actual DB endpoints; CSRF is tested independently
                    # above because the rendered fixture does not carry its cookie jar.
                    path, body, cookies = urlsplit(req.url).path, req.post_data, req.all_headers().get("cookie", "")
                    def request():
                        from django.db import connections
                        try:
                            with patch("socket.socket.connect", deny), patch("socket.getaddrinfo", deny):
                                return Client().post(path, body, content_type="application/json", secure=True,
                                                     HTTP_COOKIE=cookies)
                        finally:
                            connections.close_all()
                    # Playwright handlers run on its event loop. Keep Django's
                    # synchronous ORM on a worker, not an async-unsafe override.
                    with ThreadPoolExecutor(max_workers=1) as worker:
                        result = worker.submit(request).result()
                    headers = {"Content-Type": "application/json"}
                    if result.cookies:
                        headers["Set-Cookie"] = next(iter(result.cookies.values())).OutputString()
                    responses.append((urlsplit(req.url).path, result.status_code))
                    route.fulfill(status=result.status_code, headers=headers, body=result.content)

                def route(r):
                    req = r.request
                    path = urlsplit(req.url).path
                    if req.url == ORIGIN + "/":
                        r.fulfill(content_type="text/html", body=html, headers={"Content-Security-Policy": csp})
                    elif req.url == METRIKA_URL:
                        r.fulfill(content_type="application/javascript", body=delayed_sdk if stage == "sdk" else SDK)
                    elif req.url == RYBBIT_URL:
                        r.fulfill(content_type="application/javascript", body="window.__rybbitLoads=1;")
                    elif req.url.startswith(ORIGIN + "/analytics/"):
                        posts.append((path, req.all_headers().get("cookie", "")))
                        if path == "/analytics/" + stage:
                            held.append(r)
                        else:
                            api(r)
                    elif req.url.startswith(ORIGIN + "/static/") or path == "/favicon.ico":
                        relative = path.removeprefix("/static/") if path.startswith("/static/") else "favicon.ico"
                        source = (ROOT / "static" / relative).resolve()
                        if source.is_relative_to(ROOT / "static") and source.is_file():
                            r.fulfill(body=source.read_bytes(), content_type=mimetypes.guess_type(str(source))[0] or "application/octet-stream")
                        else:
                            unexpected.append(req.url); r.abort()
                    else:
                        unexpected.append(req.url); r.abort()

                context.route("**/*", route)
                context.route_web_socket("**/*", lambda socket: socket.close())
                page = context.new_page()
                page.goto(ORIGIN + "/")
                page.locator("[data-acquisition-purpose]").check()
                if stage == "sdk":
                    page.locator('[data-consent="yes"]').click()
                    page.wait_for_function("() => window.__clientCallbacks && window.__clientCallbacks.length === 1")
                else:
                    with page.expect_request(ORIGIN + "/analytics/" + stage):
                        page.locator('[data-consent="yes"]').click()
                # YES with unchecked purpose must invalidate old work even though
                # browser consent remains yes. Release the exact old callback/POST.
                page.locator("[data-analytics-preferences]").click()
                with page.expect_response(ORIGIN + "/analytics/revoke"):
                    page.locator('[data-consent="yes"]').click()
                assert page.evaluate(f"localStorage.getItem({json.dumps(CONSENT)})") == "yes"
                if stage == "sdk":
                    page.evaluate("window.__clientCallbacks.shift()('999999999999999999999999')")
                else:
                    assert len(held) == 1
                    with page.expect_response(ORIGIN + "/analytics/" + stage):
                        api(held.pop())
                # A browser task turn flushes promise callbacks, without sleeps.
                page.evaluate("() => new Promise(resolve => setTimeout(resolve, 0))")
                if stage == "grant":
                    assert ("/analytics/grant", 409) in responses
                    for path, cookies in posts:
                        if path in ("/analytics/grant", "/analytics/revoke"):
                            assert c.MANAGEMENT_COOKIE + "=" in cookies, "Cookie ACK precedes grant and revoke"
                else:
                    assert all(path != "/analytics/grant" for path, _ in posts)
                def latest_row():
                    from django.db import connections
                    try:
                        return c.AnalyticsGrant.objects.latest("granted_at")
                    finally:
                        connections.close_all()
                with ThreadPoolExecutor(max_workers=1) as worker:
                    row = worker.submit(latest_row).result()
                if stage == "prepare":
                    assert not page.evaluate("window.__calls.some(a => a[1] === 'getClientID')")
                    assert not row.client_id and not c.active(row, row.granted_at)
                else:
                    assert row.revoked_at
                assert not unexpected
        browser.close()


def main():
    with tempfile.TemporaryDirectory() as directory:
        html, csp = fixtures(Path(directory))["consent"]
        from django.test import override_settings
        with override_settings(ACQUISITION_LINK_ENABLED=True,
                               EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                               STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                         "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            with patch("socket.socket.connect", deny), patch("socket.socket.connect_ex", deny), patch("socket.getaddrinfo", deny):
                server_tests()
            from ops.acquisition_consent import AnalyticsGrant
            AnalyticsGrant.objects.all().delete()
            browser_tests(html, csp)
    print("PASS prepared receipt: guards, CSRF, TTL, lock orderings; Chromium SDK/prepare/grant withdrawal races")


if __name__ == "__main__":
    main()
