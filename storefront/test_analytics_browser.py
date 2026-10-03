"""Offline Chromium proof of the real analytics loader and check-email DOM.

Run from storefront (Django requirements, Playwright and Chromium required):
    env -i PATH="$PATH" HOME="$HOME" \
      PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/pw-browsers" \
      .venv/bin/python test_analytics_browser.py

Django renders actual signup/resend before the browser starts: temporary SQLite,
seed_plans --no-licensing, locmem mail, synthetic .invalid email, no sockets.
Every browser request is fulfilled locally or aborted; provider scripts are
explicit stubs, never downloaded. This proves loader calls/DOM privacy markers,
NOT provider replay implementation, delivery, production configuration or consent
lawfulness. The current loader emits signup to Metrika, not a Rybbit custom goal.
No pytest, optional tests, live credentials, mailbox, server or fixed sleeps.
"""

import io
import json
import mimetypes
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlsplit

# Imports must not leave bytecode behind in a single-file-scope test run.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
ORIGIN = "https://storefront.invalid"
RYBBIT_HOST = "https://analytics.invalid"
RYBBIT_URL = RYBBIT_HOST + "/api/script.js"
METRIKA_URL = "https://mc.yandex.ru/metrika/tag.js"
COUNTER = "123456"
EMAIL = "browser-consent@example.invalid"
CONSENT = "pseudex.analytics.consent"
LOADER = 'script[src$="/static/analytics.js"]'

# Drain the REAL loader's ym queue, then record later calls. Installing ym in
# add_init_script would conceal regressions in the loader's queue bootstrap.
METRIKA_STUB = """
window.__metrikaLoads = (window.__metrikaLoads || 0) + 1;
window.__ymCalls = window.__ymCalls || [];
for (const args of ((window.ym && window.ym.a) || [])) {
    window.__ymCalls.push(Array.from(args));
}
window.ym = function () { window.__ymCalls.push(Array.from(arguments)); };
"""
RYBBIT_STUB = "window.__rybbitLoads = (window.__rybbitLoads || 0) + 1;"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def render_pages(directory):
    """Exercise real views with outbound Python sockets prohibited throughout."""
    # Do not inherit DB/SMTP/OAuth settings even when someone omits env -i.
    allowed = {name: os.environ[name] for name in
               ("PATH", "HOME", "PLAYWRIGHT_BROWSERS_PATH", "SYSTEMROOT")
               if name in os.environ}
    os.environ.clear()
    os.environ.update(allowed)
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
        "PSEUDEX_DEBUG": "1",
        "PSEUDEX_SECRET_KEY": "offline-browser-test-not-a-secret",
        "PSEUDEX_ALLOWED_HOSTS": "storefront.invalid,testserver",
        "PSEUDEX_DB_PATH": str(directory / "test.sqlite3"),
        "PSEUDEX_ANALYTICS_SALT_FILE": str(directory / "salt"),
        "PSEUDEX_SITE_URL": ORIGIN,
        "PSEUDEX_ANALYTICS_MODE": "full",
        "PSEUDEX_ANALYTICS_HOST": RYBBIT_HOST,
        "PSEUDEX_ANALYTICS_KEY": "offline-site",
        "PSEUDEX_METRIKA_ID": COUNTER,
        "PSEUDEX_LOG_LEVEL": "ERROR",
    })
    attempts = []

    def deny_network(*args, **kwargs):
        attempts.append("Python network attempt")
        raise AssertionError("Django rendering must not open a network connection")

    with patch("socket.socket.connect", deny_network), \
            patch("socket.socket.connect_ex", deny_network), \
            patch("socket.getaddrinfo", deny_network):
        import django
        django.setup()
        from django.conf import settings
        from django.core import mail
        from django.core.management import call_command
        from django.db import connections
        from django.template.loader import render_to_string
        from django.test import Client, RequestFactory, override_settings
        from django.urls import reverse

        require(settings.DATABASES["default"]["ENGINE"] ==
                "django.db.backends.sqlite3", "test must use SQLite")
        require(settings.DATABASES["default"]["NAME"] ==
                str(directory / "test.sqlite3"), "test must use its temporary DB")
        pages = {}
        try:
            with override_settings(
                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                DEFAULT_FROM_EMAIL="test@example.invalid",
                STATIC_ROOT=directory / "staticfiles",
                STORAGES={
                    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
                },
            ):
                call_command("migrate", verbosity=0, interactive=False)
                call_command("seed_plans", "--no-licensing", verbosity=0,
                             stdout=io.StringIO())
                client = Client(HTTP_HOST="storefront.invalid")
                signup = client.post(reverse("signup"), {
                    "email": EMAIL, "company": "Offline browser fixture",
                    "plan": "free", "consent": "1", "terms": "1",
                }, secure=True)
                require(signup.status_code == 200,
                        f"signup render returned {signup.status_code}, expected 200")
                require(len(mail.outbox) == 1 and mail.outbox[0].to == [EMAIL],
                        "signup must send one synthetic message into locmem only")
                resend = client.post(reverse("resend"), {"email": EMAIL}, secure=True)
                require(resend.status_code == 200, "resend must render successfully")
                require(len(mail.outbox) == 2 and mail.outbox[1].to == [EMAIL],
                        "resend must send its synthetic message into locmem only")
                for name, response in (("signup", signup), ("resend", resend)):
                    pages[name] = (response.content.decode(),
                                   response.headers.get("Content-Security-Policy", ""))

                # Disabled-provider combinations use the real template/context,
                # not a copied script tag. The signup/resend above prove the view
                # supplies the goal; these fixtures isolate configuration knobs.
                request = RequestFactory().get("/signup", secure=True)
                for name, mode, counter in (
                    ("rybbit-only", "full", ""),
                    ("metrika-only", "off", COUNTER),
                    ("both-disabled", "off", ""),
                ):
                    config = {**settings.ANALYTICS, "mode": mode}
                    with override_settings(ANALYTICS=config, METRIKA_ID=counter):
                        html = render_to_string("check_email.html", {
                            "email": EMAIL, "metrika_goal": "signup",
                        }, request=request)
                    pages[name] = (html, "")
        finally:
            connections.close_all()
    require(not attempts, "a view attempted network access, even if it caught the error")
    print("PASS actual signup/resend renders; temporary DB, two locmem messages, no sockets")
    return pages


def browser_case(browser, pages, name, document="signup", remembered=None,
                 answer=None, rybbit=0, metrika=0, goal=0, reload=False,
                 double_load=False, privacy=False):
    from playwright.sync_api import expect

    requests = []
    unexpected = []
    errors = []
    html, csp = pages[document]
    with browser.new_context(service_workers="block") as context:
        context.set_default_timeout(5000)
        if remembered is not None:
            context.add_init_script(
                f"localStorage.setItem({json.dumps(CONSENT)}, {json.dumps(remembered)});"
            )

        def route_request(route):
            url = route.request.url
            requests.append(url)
            if url == ORIGIN + "/" + document:
                headers = {"Content-Security-Policy": csp} if csp else {}
                route.fulfill(status=200, content_type="text/html", body=html,
                              headers=headers)
            elif url == METRIKA_URL:
                route.fulfill(content_type="application/javascript", body=METRIKA_STUB)
            elif url == RYBBIT_URL:
                route.fulfill(content_type="application/javascript", body=RYBBIT_STUB)
            elif url.startswith(ORIGIN + "/static/") or url == ORIGIN + "/favicon.ico":
                path = urlsplit(url).path
                relative = path.removeprefix("/static/") if path.startswith("/static/") else "favicon.ico"
                source = (ROOT / "static" / relative).resolve()
                if source.is_relative_to(ROOT / "static") and source.is_file():
                    route.fulfill(body=source.read_bytes(), content_type=(
                        mimetypes.guess_type(str(source))[0] or "application/octet-stream"))
                else:
                    unexpected.append(url)
                    route.abort()
            else:
                unexpected.append(url)
                route.abort()

        context.route("**/*", route_request)

        def deny_websocket(websocket):
            unexpected.append(websocket.url)
            websocket.close()

        context.route_web_socket("**/*", deny_websocket)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text)
                if message.type == "error" else None)
        page.goto(ORIGIN + "/" + document, wait_until="load")

        def assert_counts(multiplier=1):
            # Positive completion waits on executed stub scripts, not mere tags.
            page.wait_for_function("""([r, m]) =>
                (window.__rybbitLoads || 0) === r &&
                (window.__metrikaLoads || 0) === m""", arg=[rybbit, metrika])
            calls = page.evaluate("window.__ymCalls || []")
            queued = page.evaluate("Array.from((window.ym && window.ym.a) || [], a => Array.from(a))")
            require(not queued, f"{name}: unexpected undrained Metrika calls {queued}")
            expected_calls = []
            if metrika:
                expected_calls.append([COUNTER, "init", {
                    "clickmap": True, "trackLinks": True,
                    "accurateTrackBounce": True, "webvisor": True,
                }])
            if goal:
                expected_calls.append([COUNTER, "reachGoal", "signup"])
            require(calls == expected_calls, f"{name}: unexpected calls {calls}")
            require(requests.count(RYBBIT_URL) == rybbit * multiplier,
                    f"{name}: wrong Rybbit request count")
            require(requests.count(METRIKA_URL) == metrika * multiplier,
                    f"{name}: wrong Metrika request count")
            expect(page.locator("#rybbit-script")).to_have_count(rybbit)
            expect(page.locator(f'script[src="{METRIKA_URL}"]')).to_have_count(metrika)
            require(not unexpected, f"{name}: unapproved requests blocked: {unexpected}")
            require(not errors, f"{name}: browser errors: {errors}")

        if remembered is None and document != "both-disabled":
            expect(page.get_by_role("dialog", name="Аналитика")).to_have_count(1)
            require(not [url for url in requests if not url.startswith(ORIGIN + "/")],
                    f"{name}: provider request before consent")
            require(page.evaluate("typeof window.ym") == "undefined",
                    f"{name}: goals/init exist before consent")
        else:
            expect(page.locator(".consent-bar")).to_have_count(0)
        if answer:
            page.locator(f'[data-consent="{answer}"]').click()
            expect(page.locator(".consent-bar")).to_have_count(0)
            require(page.evaluate("key => localStorage.getItem(key)", CONSENT) == answer,
                    f"{name}: answer was not persisted")
        assert_counts()
        if privacy:
            loader = page.locator(LOADER)
            expect(loader).to_have_count(1)
            expect(loader).to_have_attribute("data-goal", "signup" if document == "signup" else "")
            email = page.locator("h2 span")
            expect(email).to_have_text(EMAIL)
            expect(email).to_have_class("ym-hide-content")
            require(email.get_attribute("data-private") is not None,
                    "check_email visible email lacks Rybbit data-private")
            if document == "signup":
                field = page.locator('input[name="email"]')
                expect(field).to_have_value(EMAIL)
                require("ym-disable-keys" in field.get_attribute("class").split(),
                        "resend input lacks Metrika input masking")
                require(field.get_attribute("data-private") is not None,
                        "resend input lacks Rybbit data-private")
            else:
                expect(page.locator('input[name="email"]')).to_have_count(0)
            if rybbit:
                script = page.locator("#rybbit-script")
                expect(script).to_have_attribute("data-site-id", "offline-site")
                expect(script).to_have_attribute("data-replay-mask-all-inputs", "true")
                selectors = json.loads(script.get_attribute("data-replay-mask-text-selectors"))
                require(selectors == ["[data-private]"], "Rybbit mask selector drifted")
                require(email.evaluate("(el, selector) => el.matches(selector)", selectors[0]),
                        "rendered email does not match the configured replay selector")
        if double_load:
            # Copy attributes into a NEW script: cloneNode preserves the HTML
            # already-started flag and would never execute this second loader.
            # Avoid eval: document.currentScript must be a real script node.
            page.evaluate("""() => {
                const original = document.querySelector('script[src$="/static/analytics.js"]');
                const duplicate = document.createElement('script');
                for (const attr of original.attributes) {
                    duplicate.setAttribute(attr.name, attr.value);
                }
                duplicate.onload = () => { window.__duplicateLoaded = true; };
                document.body.appendChild(duplicate);
            }""")
            page.wait_for_function("() => window.__duplicateLoaded === true")
            expect(page.locator(LOADER)).to_have_count(2)
            require(requests.count(ORIGIN + "/static/analytics.js") == 2,
                    "duplicate loader must actually execute a second network load")
            assert_counts()
        if reload:
            # No init-script for click cases: this uses the answer the loader
            # itself stored, proving persistence across a fresh document.
            page.reload(wait_until="load")
            expect(page.locator(".consent-bar")).to_have_count(0)
            assert_counts(multiplier=2)
        if document == "both-disabled":
            expect(page.locator(LOADER)).to_have_count(0)
        print(f"PASS {name}")


def main():
    sys.stdout.reconfigure(line_buffering=True)
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix="pseudex-analytics-browser-") as directory:
        pages = render_pages(Path(directory))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=[
                "--disable-background-networking", "--disable-component-update",
                "--host-resolver-rules=MAP * ~NOTFOUND",
            ])
            try:
                print(f"Chromium {browser.version}; all requests locally routed")
                browser_case(browser, pages, "no choice: no providers or goals")
                browser_case(browser, pages, "decline + reload: no providers or goals",
                             answer="no", reload=True)
                browser_case(browser, pages, "accept + reload: each provider/signup once per document",
                             answer="yes", rybbit=1, metrika=1, goal=1, reload=True,
                             privacy=True)
                browser_case(browser, pages, "remembered no: no banner/providers/goals",
                             remembered="no")
                browser_case(browser, pages, "remembered yes + loader twice: no duplicate goals",
                             remembered="yes", rybbit=1, metrika=1, goal=1,
                             double_load=True, privacy=True)
                browser_case(browser, pages, "accept then loader twice: no duplicate goals",
                             answer="yes", rybbit=1, metrika=1, goal=1, double_load=True)
                browser_case(browser, pages, "Metrika disabled: only Rybbit, no signup goal",
                             document="rybbit-only", answer="yes", rybbit=1)
                browser_case(browser, pages, "Rybbit disabled: only Metrika/signup",
                             document="metrika-only", answer="yes", metrika=1, goal=1)
                browser_case(browser, pages, "both disabled: no loader/banner/providers/goals",
                             document="both-disabled", remembered="yes")
                browser_case(browser, pages, "actual resend: both providers, zero signup goals, masked email",
                             document="resend", remembered="yes", rybbit=1, metrika=1,
                             privacy=True, double_load=True)
            finally:
                browser.close()
    print("PASS all 10 browser cases; no skips; no production or provider-delivery claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
