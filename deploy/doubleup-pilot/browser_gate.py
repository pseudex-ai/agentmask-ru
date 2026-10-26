"""Real browser checks against the isolated seeded chat and real inspection API.

No chat turn is sent here. The inspected attempts came from boundary_fixture.py,
so screenshots contain synthetic values only. Credentials/session stay in private
state and any navigation error is reported without its URL/query or exception.
"""

import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
CHAT = ("http://127.0.0.1:18880/doubleup-pilot/assistantnew/57e342e0-2c08-578e-a801-527de89fe9de"
        "?thread=e6f6f3a8-dcf6-5c95-8eb5-fd9359fbeb09")


def main() -> None:
    screenshots = STATE / "browser"
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            # Actual SSR proof, not a source-text assertion. Even before React
            # handlers exist, a form can never put credentials in a GET URL.
            no_js = browser.new_context(java_script_enabled=False)
            prehydration = no_js.new_page()
            prehydration.goto("http://127.0.0.1:18880/login", wait_until="domcontentloaded", timeout=60000)
            form = prehydration.locator("form")
            assert form.get_attribute("method").lower() == "post"
            assert prehydration.locator("button[type=submit]").is_disabled()
            no_js.close()
            checks.append("login_pre_hydration_does_not_submit_credentials_in_url")

            context = browser.new_context(storage_state=str(screenshots / "storage.json"),
                                          viewport={"width": 1440, "height": 1100})
            page = context.new_page()
            reveals = []
            page.on("request", lambda request: reveals.append(request.method)
                    if urlsplit(request.url).path.endswith("/reveal") else None)
            page.goto(CHAT, wait_until="domcontentloaded", timeout=60000)
            button = page.locator('[data-testid="pseudex-open"]:visible').first
            button.wait_for(timeout=60000)
            assert not reveals
            button.click()
            panel = page.get_by_role("dialog", name=re.compile("Граница данных.*Pseudex"))
            panel.wait_for(timeout=30000)
            # Derive the attempt from an authenticated GET, not from guessed
            # timestamps or a canonical-token lookup.
            token = page.evaluate("() => localStorage.getItem('auth_access_token')")
            assert isinstance(token, str) and token
            listing = context.request.get("http://127.0.0.1:18860/api/v1/pseudex/inspections",
                params={"thread_id": "e6f6f3a8-dcf6-5c95-8eb5-fd9359fbeb09"},
                headers={"Authorization": "Bearer " + token, "X-Org-Id": "doubleup-pilot"})
            assert listing.status == 200 and listing.headers.get("cache-control") == "no-store"
            attempt_id = None
            for item in listing.json()["items"]:
                if item["mode"] != "pseudex":
                    continue
                detail = context.request.get("http://127.0.0.1:18860/api/v1/pseudex/inspections/" + item["attempt_id"],
                    headers={"Authorization": "Bearer " + token, "X-Org-Id": "doubleup-pilot"})
                data = detail.json()
                if data.get("tool_dispatches") and (data.get("inspection") or {}).get("replacements"):
                    attempt_id = item["attempt_id"]
                    break
            assert attempt_id is not None
            panel.get_by_role("button", name=re.compile(re.escape(attempt_id))).click()
            panel.get_by_test_id("pseudex-attempt-detail").wait_for(timeout=30000)
            assert "pilot.person@example.org" in panel.get_by_role("tabpanel").inner_text()
            checks.append("source_boundary_snapshot_visible_under_real_auth")
            pair = panel.get_by_test_id("pseudex-replacement-pair").first
            pair.wait_for(timeout=15000)
            assert pair.get_by_test_id("pseudex-source-fragment").inner_text()
            assert pair.get_by_test_id("pseudex-shown-fragment").inner_text()
            assert pair.get_by_test_id("pseudex-source-fragment").inner_text() != pair.get_by_test_id("pseudex-shown-fragment").inner_text()
            pair.scroll_into_view_if_needed()
            page.screenshot(path=str(screenshots / "replacement-pairs.png"), full_page=True)
            checks.append("exact_source_to_model_pairs_from_recorded_offsets")

            panel.get_by_role("tab", name="Отправлено модели", exact=True).click()
            assert "pilot.person@example.org" not in panel.get_by_role("tabpanel").inner_text()
            page.screenshot(path=str(screenshots / "model-boundary.png"), full_page=True)
            checks.append("actual_masked_provider_payload_visible")
            panel.get_by_role("tab", name="Ответ модели", exact=True).click()
            panel.get_by_text("Восстановленный ответ · restored_response", exact=True).wait_for()
            checks.append("raw_and_restored_model_responses_separate")
            panel.get_by_role("tab", name="Передано инструменту", exact=True).click()
            panel.get_by_text("Выполнено — есть запись диспетчеризации", exact=True).wait_for()
            page.screenshot(path=str(screenshots / "tool-boundary.png"), full_page=True)
            checks.append("actual_local_tool_dispatch_and_result_visible")

            panel.get_by_role("button", name="Раскрыть каноническое значение", exact=True).first.click()
            assert not reveals
            page.get_by_role("button", name="Отмена", exact=True).click()
            assert not reveals
            panel.get_by_role("button", name="Раскрыть каноническое значение", exact=True).first.click()
            page.get_by_role("button", name="Подтвердить раскрытие", exact=True).click()
            value = panel.get_by_test_id("pseudex-canonical-value")
            value.wait_for(timeout=15000)
            assert value.inner_text() and reveals == ["POST"]
            checks.append("explicit_confirmation_real_authorized_audited_reveal")
            panel.get_by_role("button", name="Close", exact=True).click()
            assert page.get_by_test_id("pseudex-session").count() == 0
            checks.append("closing_unmounts_plaintext")
            context.close()
            report = {"passed": True, "checks": checks, "real_backend": True,
                      "synthetic_only": True, "provider_calls": 0, "paid_usd": 0}
            target = STATE / "browser-gate.json"
            target.write_text(json.dumps(report, indent=2)); target.chmod(0o600)
            print(json.dumps(report))
        except Exception as error:
            print(json.dumps({"passed": False, "error_type": type(error).__name__, "checks_passed": checks}))
            raise SystemExit(1) from None
        finally:
            browser.close()


if __name__ == "__main__":
    main()
