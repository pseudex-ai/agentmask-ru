"""Offline CSP/XFO regression; add --browser for synthetic Chromium framing.

No SDK, visitor records, database, server or external requests are used. Browser
routes fulfill every request locally; unrecognized destinations are aborted.
"""
import argparse
import hashlib
import os
from pathlib import Path
import socket
from unittest.mock import patch
from urllib.parse import urlsplit

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
os.environ.setdefault("PSEUDEX_SECRET_KEY", "offline-framing-test-only")

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils.module_loading import import_string

from storefront_web.middleware import _POLICY, _policy_for

# Independent snapshot of the official frame-ancestors list, checked 2026-10-10.
# https://yandex.ru/support/metrica/ru/code/install-counter-csp
ANCESTORS = {"https://" + host for host in """
metrika.yandex.ru analytics.yandex.by analytics.yandex.com analytics.yandex.com.tr
analytics.yandex.kz analytics.yandex.ru metr.yandex.by metr.yandex.com
metr.yandex.com.tr metr.yandex.kz metr.yandex.ru metrica.ya.ru metrica.yandex
metrica.yandex.by metrica.yandex.com metrica.yandex.com.tr metrica.yandex.kz
metrica.yandex.ru metrika.ya.ru metrika.yandex metrika.yandex.by metrika.yandex.com
metrika.yandex.com.tr metrika.yandex.kz metrika.yandex.uz
""".split()}
CONNECT = {"wss://mc.yandex.ru", "https://mc.webvisor.com",
           "https://mc.webvisor.org", "wss://mc.webvisor.com", "wss://mc.webvisor.org"}
PUBLIC = ("/", "/signup", "/detection", "/kb/example")
CLOSED = ("/activate", "/activate/token", "/welcome", "/welcome/",
          "/app", "/app/", "/app/invoices/1", "/accounts", "/accounts/login/",
          "/secret-admin", "/secret-admin/", "/secret-admin/oidc/authenticate/")
XFO = "django.middleware.clickjacking.XFrameOptionsMiddleware"
SECURITY = "storefront_web.middleware.SecurityHeadersMiddleware"


def blocked(*args, **kwargs):
    raise AssertionError("Network access is forbidden in framing tests")


def directives(policy):
    return {bits[0]: set(bits[1:]) for item in policy.split(";")
            if (bits := item.split())}


def response_for(path, headers=None, exempt=False, order=None):
    def view(request):
        response = HttpResponse('<p id="framing-proof">Synthetic document</p>',
                                headers=headers)
        response.xframe_options_exempt = exempt
        return response
    # Use real classes and their order from real settings, not a copied order.
    chain = order or [name for name in settings.MIDDLEWARE if name in (XFO, SECURITY)]
    handler = view
    for name in reversed(chain):
        handler = import_string(name)(handler)
    return handler(RequestFactory().get(path, secure=True))


def test_headers():
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.MIDDLEWARE.index(XFO) < settings.MIDDLEWARE.index(SECURITY)
    count = 0
    for metrika in ("", "123456"):
        for mode in ("off", "replay"):
            with override_settings(METRIKA_ID=metrika, ADMIN_PATH="secret-admin",
                                   ANALYTICS={"mode": mode, "host": "https://analytics.example"}):
                for path in PUBLIC + CLOSED:
                    for existing in ({}, {"X-Frame-Options": "DENY"},
                                     {"X-Frame-Options": "SAMEORIGIN"}):
                        response = response_for(path, existing, exempt=True)
                        csp = directives(response["Content-Security-Policy"])
                        eligible = path in PUBLIC and bool(metrika)
                        assert csp["frame-ancestors"] == (ANCESTORS if eligible else {"'none'"}), path
                        assert (response.get("X-Frame-Options") is None) == eligible, path
                        if not eligible:
                            assert response["X-Frame-Options"] == "DENY"
                        assert "'unsafe-inline'" not in csp["script-src"]
                        assert "'unsafe-eval'" not in csp["script-src"]
                        assert not any("*" in value for values in csp.values() for value in values)
                        if eligible:
                            assert CONNECT <= csp["connect-src"]
                            assert not CONNECT & csp["script-src"]
                            assert csp["frame-src"] == {"blob:", "https://mc.yandex.ru"}
                        else:
                            assert not any("yandex" in v or "webvisor" in v or "yastatic" in v
                                           for values in csp.values() for v in values)
                        if path in CLOSED:
                            assert response["Content-Security-Policy"] == _POLICY
                        count += 1
                # A response-specific restrictive CSP must not be replaced with
                # the public allowance or lose XFO through an exemption flag.
                for custom in ("default-src 'self'; frame-ancestors 'none'",
                               "default-src 'self'; frame-ancestors https://untrusted.example"):
                    response = response_for("/", {"Content-Security-Policy": custom}, exempt=True)
                    assert response["Content-Security-Policy"] == custom + ", frame-ancestors 'none'"
                    assert response["X-Frame-Options"] == "DENY"
                # Private response headers may not smuggle a public CSP through
                # setdefault; the private resource policy wins even with exempt.
                public_policy = _policy_for(RequestFactory().get("/"))
                response = response_for("/app/", {"Content-Security-Policy": public_policy}, exempt=True)
                assert response["Content-Security-Policy"] == _POLICY
                assert response["X-Frame-Options"] == "DENY"
                # Removal also works if XFO has already run on the response.
                response = response_for("/", order=[SECURITY, XFO])
                assert (response.get("X-Frame-Options") is None) == bool(metrika)
    print(f"PASS: {count} header cases; custom headers and actual Django middleware order")


def test_full_stack():
    import django
    from django.core.handlers.base import BaseHandler

    django.setup()
    # Keep every real middleware from settings, substituting only the terminal
    # view and the database-backed visit writer. No URL or model fixture is
    # needed to prove that the surrounding middleware preserves these headers.
    with override_settings(METRIKA_ID="123456", ADMIN_PATH="secret-admin",
                           ALLOWED_HOSTS=["testserver"],
                           ANALYTICS={"mode": "off", "host": "https://analytics.example"}), \
            patch("storefront_web.middleware.AnalyticsMiddleware._record"):
        handler = BaseHandler()
        handler._get_response = lambda request: HttpResponse("Synthetic full-stack view")
        handler.load_middleware()
        for path in PUBLIC + CLOSED:
            response = handler.get_response(RequestFactory().get(path, secure=True))
            assert response.status_code == 200, (path, response.status_code)
            assert (response.get("X-Frame-Options") is None) == (path in PUBLIC), path
            assert directives(response["Content-Security-Policy"])["frame-ancestors"] == (
                ANCESTORS if path in PUBLIC else {"'none'"})
    print("PASS: all 16 paths through the complete actual settings middleware stack")


def test_caddy(required=False):
    path = Path(__file__).resolve().parents[1] / "deploy/Caddyfile"
    if not path.is_file():
        if required:
            raise AssertionError("Caddy configuration required for platform CI")
        print("NOT RUN: proxy configuration is not distributed in standalone storefront; use monorepo --require-proxy")
        return
    source = path.read_text()
    # Pin all other sites byte-for-byte: this scoped change must not weaken
    # licensing, analytics, SSO or board. Deliberate future changes update this
    # snapshot only after reviewing those sites' independent security contracts.
    tail = source[source.index("www.{$SITE_HOST} {"):]
    assert hashlib.sha256(tail.encode()).hexdigest() == (
        "4ac708e223f58142e07fe9d37bd401385a334e354165753b1ae21716b6e395d5")
    storefront = source[:source.index("www.{$SITE_HOST} {")]
    active = "\n".join(line for line in storefront.splitlines()
                       if not line.lstrip().startswith("#"))
    assert active.count("reverse_proxy storefront:8000 {") == 1
    assert "X-Frame-Options" not in active
    assert "Content-Security-Policy" not in active
    assert 'Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"' in active
    assert 'X-Content-Type-Options "nosniff"' in active
    assert 'Referrer-Policy "same-origin"' in active
    print("PASS: Caddy storefront delegates framing; all other site blocks unchanged")


def test_browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=[
            "--disable-background-networking", "--host-resolver-rules=MAP * ~NOTFOUND"])
        context = browser.new_context(service_workers="block")
        unexpected = []
        current = {}

        def route_request(route):
            url = urlsplit(route.request.url)
            origin = f"{url.scheme}://{url.netloc}"
            if origin == current["origin"] and url.path == "/parent":
                route.fulfill(content_type="text/html", body=(
                    '<iframe src="https://storefront.example' + current["path"] + '"></iframe>'))
            elif origin == "https://storefront.example" and url.path == current["path"]:
                response = current["response"]
                route.fulfill(status=200, headers=dict(response.items()), body=response.content)
            else:
                unexpected.append(route.request.url)
                route.abort()

        context.route("**/*", route_request)
        count = 0
        with override_settings(ADMIN_PATH="secret-admin",
                               ANALYTICS={"mode": "off", "host": "https://analytics.example"}):
            cases = [(origin, "/", "123456", True) for origin in sorted(ANCESTORS)]
            cases += [(origin, "/", "123456", False) for origin in (
                "https://untrusted.example", "https://metrika.yandex.ru.evil.example",
                "http://metrika.yandex.ru", "https://storefront.example")]
            cases += [("https://metrika.yandex.ru", path, "123456", False) for path in CLOSED]
            cases += [("https://metrika.yandex.ru", "/", "", False)]
            cases = [(*case, {}) for case in cases]
            cases += [(
                "https://metrika.yandex.ru", "/", "123456", False,
                {"Content-Security-Policy": "default-src 'self'; frame-ancestors https://metrika.yandex.ru"},
            ), (
                "https://metrika.yandex.ru", "/", "123456", True,
                {"X-Frame-Options": "DENY"},
            )]
            for origin, path, metrika, expected, headers in cases:
                with override_settings(METRIKA_ID=metrika):
                    current.update(origin=origin, path=path, response=response_for(path, headers))
                page = context.new_page()
                errors = []
                page.on("console", lambda message: errors.append(message.text))
                page.goto(origin + "/parent", wait_until="load")
                rendered = any(frame.locator("#framing-proof").count()
                               for frame in page.frames if frame != page.main_frame)
                assert rendered == expected, (origin, path, metrika, errors)
                if not expected:
                    assert any("frame-ancestors" in error for error in errors), errors
                page.close()
                count += 1
        assert not unexpected, unexpected
        context.close()
        browser.close()
    print(f"PASS: Chromium {count} synthetic framing cases; every request locally fulfilled")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true", help="Require installed Playwright Chromium")
    parser.add_argument("--require-proxy", action="store_true", help="Fail unless monorepo Caddy configuration is checked")
    args = parser.parse_args()
    with patch.object(socket.socket, "connect", blocked), \
            patch.object(socket.socket, "connect_ex", blocked), \
            patch.object(socket, "create_connection", blocked):
        test_headers()
        test_full_stack()
        test_caddy(required=args.require_proxy)
        if args.browser:
            test_browser()
        else:
            print("SKIP: Chromium framing (run with --browser to require it)")


if __name__ == "__main__":
    main()
