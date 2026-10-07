"""Team pages must remain readable in a real browser, not merely return 200.

The missing mobile breakpoint left the portrait visible while the name, role
and actions collapsed into a zero-width column outside the viewport. Checking
scrollWidth alone missed it because the shared frame clipped overflow.

Run with Playwright + Chromium installed. An existing local preview can be
checked with --url; otherwise a disposable Django server and database are used.
No production credentials or customer data are needed.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
WIDTHS = (320, 375, 390, 430, 700, 768, 900, 901, 1024, 1440)
PAGES = ("/i/", "/i/igor", "/i/gosha", "/i/slava")


def start_site(directory):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, PSEUDEX_DEBUG="1", PSEUDEX_SECRET_KEY="render-test-only",
               PSEUDEX_ALLOWED_HOSTS="127.0.0.1,localhost",
               PSEUDEX_DB_PATH=str(Path(directory) / "store.sqlite3"))
    for command in ("migrate", "seed_plans"):
        subprocess.run([sys.executable, "manage.py", command, "--noinput"]
                       if command == "migrate" else
                       [sys.executable, "manage.py", command],
                       cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}",
         "--noreload", "--insecure"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if server.poll() is not None:
            raise RuntimeError("preview server exited before it became ready")
        try:
            with urllib.request.urlopen(url + "/i/", timeout=1) as response:
                if response.status == 200:
                    return server, url
        except (OSError, urllib.error.URLError):
            time.sleep(.1)
    server.terminate()
    server.wait(timeout=10)
    raise RuntimeError("preview server did not become ready")


# The viewport must contain every critical element individually. An overflow
# hidden/clip ancestor can make document.scrollWidth pass with the text missing.
GEOMETRY = """(selectors) => selectors.flatMap(selector => {
  const elements = [...document.querySelectorAll(selector)];
  if (!elements.length) return [selector + ': missing'];
  return elements.flatMap(e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    const errors = [];
    if (r.width < 80 || r.height < 10 || s.visibility === 'hidden' || s.display === 'none')
      errors.push(selector + ': collapsed/invisible');
    if (r.left < -1 || r.right > innerWidth + 1)
      errors.push(selector + ': outside viewport');
    return errors;
  });
})"""


def verify(browser, url, screenshots):
    page = browser.new_page(viewport={"width": 390, "height": 844},
                            locale="ru-RU", reduced_motion="reduce")
    issues = []
    page.on("pageerror", lambda error: issues.append(str(error)))
    page.on("response", lambda response: issues.append(
        f"HTTP {response.status}: {response.url}") if response.status >= 400 else None)
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 844})
        for path in PAGES:
            response = page.goto(url + path, wait_until="networkidle")
            assert response.status == 200, (path, response.status)
            page.evaluate("() => document.fonts.ready")
            selectors = [".team-name", ".eyebrow", ".team-lede"]
            selectors += ([".person"] if path == "/i/" else
                          [".team-photo", ".team-actions .btn", ".contact"])
            errors = page.evaluate(GEOMETRY, selectors)
            assert not errors, (width, path, errors)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (width, path)
            assert page.locator(".frame").evaluate("e => getComputedStyle(e).backgroundImage") == "none", path
            assert page.locator("img").evaluate_all(
                "images => images.every(i => i.complete && i.naturalWidth > 0)"), path
            if path != "/i/":
                assert page.locator(".contact .v").evaluate_all(
                    "items => items.every(e => e.scrollWidth <= e.clientWidth + 1)"), (width, path, "clipped contact")
                assert page.locator(".team-actions .btn").evaluate_all(
                    "items => items.every(e => e.getBoundingClientRect().height >= 44)"), path
                if width <= 900:
                    photo = page.locator(".team-photo").bounding_box()
                    text = page.locator(".team-hero > div").bounding_box()
                    assert 16 <= text["y"] - (photo["y"] + photo["height"]) <= 40, (width, path, "hero gap")
                else:
                    assert page.locator(".team-hero > div").bounding_box()["x"] > page.locator(".team-photo").bounding_box()["x"], path
            if screenshots and width in (390, 1440):
                name = path.rstrip("/").split("/")[-1]
                page.screenshot(path=str(screenshots / f"{name}-{width}.png"), full_page=True)
        print(f"PASS {width}px: index + three people, visible text/actions, no clipping/grid")

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(url + "/i/", wait_until="networkidle")
    page.locator('a.person[href="/i/igor"]').click()
    page.wait_for_url("**/i/igor")
    assert page.locator("h1").inner_text() == "Игорь"
    assert page.locator('a[href^="tel:"]').count() >= 1
    assert page.locator('a[href^="mailto:"]').count() >= 1
    with page.expect_download() as pending:
        page.locator('a[download]').click()
    download = pending.value
    assert download.suggested_filename == "igor.vcf"
    assert "i.afonin@pseudex.ru" in Path(download.path()).read_text()
    page.locator('.head-cta a').click()
    page.wait_for_url("**/i/")
    page.locator('.head-cta a').click()
    page.wait_for_url(url + "/")
    page.locator('footer a[href="/i/"]').click()
    page.wait_for_url("**/i/")
    print("PASS navigation: landing footer → team → person → vCard → team → landing")

    # The frame is shared by the whole site, not only QR pages. Check both
    # palettes and a separate public document/account screen at phone and PC sizes.
    for width in (390, 1440):
        page.set_viewport_size({"width": width, "height": 844})
        for path in ("/", "/architecture", "/policy", "/accounts/login/"):
            response = page.goto(url + path, wait_until="networkidle")
            assert response.status == 200, (path, response.status)
            for theme in ("dark", "light"):
                page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                assert page.locator(".frame").evaluate("e => getComputedStyle(e).backgroundImage") == "none", (width, path, theme)
    assert not issues, issues
    page.close()
    print("PASS no decorative grid on landing, documents and login in both themes")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="existing local development server")
    parser.add_argument("--browser", choices=("chromium", "webkit"), default="chromium")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pseudex-team-renders-") as directory:
        server = None
        try:
            url = args.url
            if not url:
                server, url = start_site(directory)
            with sync_playwright() as pw:
                browser = getattr(pw, args.browser).launch()
                try:
                    verify(browser, url.rstrip("/"), args.screenshots)
                finally:
                    browser.close()
        finally:
            if server:
                server.terminate()
                server.wait(timeout=10)
    print(f"Team layout OK ({args.browser})")


if __name__ == "__main__":
    main()
