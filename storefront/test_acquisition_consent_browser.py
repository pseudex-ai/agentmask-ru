"""Real Chromium purpose UX; local routes/stub SDK only, never live events."""
import json
import mimetypes
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit

from test_analytics_browser import render_pages, ROOT, ORIGIN, METRIKA_URL, RYBBIT_URL, CONSENT

CLIENT_ID = "999999999999999999999999"
SDK = """
window.__calls = [];
var queued = window.ym.a || [];
window.ym = function () {
  var a = Array.from(arguments); window.__calls.push(a.slice(0, 3));
  if (a[1] === 'getClientID') a[2]('999999999999999999999999');
};
queued.forEach(function(a) { window.ym.apply(null, a); });
"""


def fixtures(directory):
    pages = render_pages(directory)
    from django.test import Client, override_settings
    def deny(*args, **kwargs):
        raise AssertionError("No rendering network")
    with patch("socket.socket.connect", deny), patch("socket.getaddrinfo", deny), \
            override_settings(ACQUISITION_LINK_ENABLED=True,
                STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                          "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
        response = Client(HTTP_HOST="storefront.invalid").get("/", secure=True)
        assert response.status_code == 200
        pages["consent"] = (response.content.decode(), response.headers.get("Content-Security-Policy", ""))
    return pages


def main():
    from playwright.sync_api import sync_playwright, expect
    with tempfile.TemporaryDirectory() as directory:
        pages = fixtures(Path(directory))
        html, csp = pages["consent"]
        assert 'data-acquisition-enabled="true"' in html
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            for legacy, purpose, fail in [(None, False, False), ("yes", False, False),
                                           ("yes", True, False), ("yes", True, True)]:
                with browser.new_context(service_workers="block") as context:
                    context.set_default_timeout(5000)
                    if legacy:
                        context.add_init_script(f"if (localStorage.getItem({json.dumps(CONSENT)}) === null) localStorage.setItem({json.dumps(CONSENT)}, 'yes')")
                    requests, posts, unexpected = [], [], []
                    def route(r):
                        req = r.request
                        requests.append(req.url)
                        path = urlsplit(req.url).path
                        if req.url == ORIGIN + "/":
                            r.fulfill(content_type="text/html", body=html,
                                      headers={"Content-Security-Policy": csp})
                        elif req.url == METRIKA_URL:
                            r.fulfill(content_type="application/javascript", body=SDK)
                        elif req.url == RYBBIT_URL:
                            r.fulfill(content_type="application/javascript", body="window.__rybbitLoads=1;")
                        elif req.url.startswith(ORIGIN + "/analytics/"):
                            posts.append((path, req.method, json.loads(req.post_data or "{}")))
                            r.fulfill(status=503 if fail and path.endswith("revoke") else 200,
                                      content_type="application/json", body='{"status":"ok"}')
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
                    if legacy:
                        page.locator("[data-analytics-preferences]").click()
                    else:
                        assert METRIKA_URL not in requests and RYBBIT_URL not in requests
                    checkbox = page.locator("[data-acquisition-purpose]")
                    expect(checkbox).not_to_be_checked()
                    assert not posts, "Legacy yes must not silently grant"
                    if purpose:
                        checkbox.check()
                    page.locator('[data-consent="yes"]').click()
                    expect(page.locator('[data-acquisition-status]')).to_be_visible()
                    if purpose:
                        page.wait_for_function("document.querySelector('[data-acquisition-status]').textContent.includes('Разрешение связи сохранено')")
                        assert posts[0] == ("/analytics/prepare", "POST", {
                            "purpose_revision": "acquisition-v1", "affirmative": "1", "browser_consent": "yes"})
                        assert posts[1] == ("/analytics/grant", "POST", {
                            "purpose_revision": "acquisition-v1", "affirmative": "1",
                            "browser_consent": "yes", "client_id": CLIENT_ID})
                        assert "email" not in json.dumps(posts) and "organization" not in json.dumps(posts)
                    else:
                        assert all(p[0] != "/analytics/grant" for p in posts)
                    page.locator("[data-analytics-preferences]").click()
                    expect(page.locator("[data-acquisition-purpose]")).not_to_be_checked()
                    before = requests.count(METRIKA_URL)
                    page.locator('[data-consent="no"]').click()
                    page.wait_for_url(ORIGIN + "/")
                    expect(page.locator('[data-acquisition-status]')).to_be_visible()
                    page.wait_for_function("document.querySelector('[data-acquisition-status]').textContent.includes('Повторите отзыв')" if fail else
                                           "document.querySelector('[data-acquisition-status]').textContent.startsWith('Серверный отзыв подтверждён')")
                    status = page.locator("[data-acquisition-status]").inner_text()
                    assert requests.count(METRIKA_URL) == before, "Clean GET must not reload providers"
                    assert ("ещё не подтверждён" if fail else "подтверждён") in status
                    assert not unexpected
            browser.close()
    print("PASS Chromium: explicit purpose, opaque-only responses, legacy opt-out, truthful revoke failure")


if __name__ == "__main__":
    main()
