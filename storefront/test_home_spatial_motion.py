#!/usr/bin/env python3
"""Playwright smoke proof of the homepage spatial-motion layer (read-only).

Contract: static/spatial-motion.{css,js} + templates/products/home-depth.html as
loaded from templates/landing.html.

    python test_home_spatial_motion.py --base-url http://127.0.0.1:18765

GETs one loopback origin: no forms, no leads, no provider calls, no writes; every
request that leaves loopback is aborted and reported. NOT proven here: real touch
hardware, paint quality, production configuration, or landing.js hero timing.
"""
import argparse
import sys
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

sys.dont_write_bytecode = True

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
CARDS = ["/#start", "/ai-security", "/ai-coding"]
SCENE, GRID = "[data-depth-scene]", ".product-suite-grid"
WIDE = {"width": 1440, "height": 950}
MOTION = "document.body.classList.contains('motion-ready')"
SCROLL = "document.querySelector('[data-depth-scene]').style.getPropertyValue('--mx-scroll')"
PROP = "([s, n]) => parseFloat(document.querySelector(s).style.getPropertyValue(n) || 0)"
LIFTS = "[...document.querySelectorAll('.product-suite-card')].map(c => parseFloat(c.style.getPropertyValue('--mx-lift') || 0))"

# Counts spatial-motion's OWN frame callback: landing.js runs its own timers and
# counters, so a total rAF count would score the whole app, not the engine.
REF = """(() => {
  const native = window.requestAnimationFrame.bind(window);
  window.__mxRaf = {count: 0};
  window.requestAnimationFrame = function (cb) {
    if (typeof cb === 'function' && cb.name === 'paintDepth') window.__mxRaf.count++;
    return native(cb); }; })()"""

CARD = """(() => { const c = document.querySelectorAll('.product-suite-card')[1], r = c.getBoundingClientRect();
  const cs = getComputedStyle(c), e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height * .3);
  const hit = e && e.closest('.product-suite-card');
  return {href: c.getAttribute('href'), box: {x: r.left + r.width * .2, y: r.top + r.height * .3},
          w: Math.round(r.width), h: Math.round(r.height), op: cs.opacity, vis: cs.visibility,
          hit: hit === c ? 'self' : (hit ? 'other' : null)}; })()"""


def require(cond, msg): assert cond, msg


def poll(page, expr, want, arg=None, timeout=5000, interval=100):
    """Bounded wait; returns the last observed value, satisfying or not."""
    end, value = time.monotonic() + timeout / 1000, None
    while time.monotonic() < end and not want(value):
        value = page.evaluate(expr, arg)
        page.wait_for_timeout(interval)
    return value


def settle(page, timeout=8000, stable=3, interval=120):
    """Idle means paintDepth stopped being REGISTERED, not merely that time passed."""
    last, same, end = -1, 0, time.monotonic() + timeout / 1000
    while time.monotonic() < end:
        count = page.evaluate("window.__mxRaf.count")
        same, last = (same + 1, count) if count == last else (0, count)
        if same >= stable: return last
        page.wait_for_timeout(interval)
    raise AssertionError("paintDepth never went idle, so the engine is still looping")


def show(locator, label):
    """A trial click is the proof a control is neither hidden nor covered."""
    try:
        locator.click(trial=True, timeout=5000)
    except Exception as exc:
        raise AssertionError(f"{label} is hidden or covered ({type(exc).__name__})") from exc


def edge(page):  # bottom of the product grid, in document coordinates
    return page.evaluate(f"document.querySelector('{GRID}').getBoundingClientRect().bottom + scrollY")


def scroll_to(page, y): page.evaluate("y => scrollTo(0, y)", y); page.wait_for_timeout(350)


def open_page(browser, base, net, **kw):
    """One context + page: loopback route guard, rAF counter, error/CSP/asset collectors."""
    kw.setdefault("viewport", dict(WIDE))
    ctx = browser.new_context(**kw)

    def route(handler, request):
        if (urlsplit(request.url).scheme, urlsplit(request.url).netloc) == (urlsplit(base).scheme, urlsplit(base).netloc): handler.continue_()
        else:
            net["outside"].append(request.url)
            handler.abort()

    ctx.route("**/*", route)
    ctx.add_init_script(REF)
    page = ctx.new_page()
    page.on("pageerror", lambda e: net["errors"].append(str(e)))
    page.on("console", lambda m: net["csp"].append(m.text) if "Content Security Policy" in m.text else None)
    page.on("response", lambda r: net["assets"].__setitem__(urlsplit(r.url).path.rsplit("/", 1)[-1], r.status)
            if "spatial-motion" in r.url else None)
    response = page.goto(base, wait_until="load")
    require(response is not None and response.status == 200,
            f"homepage did not return 200 (got {response and response.status})")
    return ctx, page


def check_wide(browser, base, net):
    """Approved card motion remains; the owner removed hero particles and glow."""
    ctx, page = open_page(browser, base, net)
    require(page.evaluate(MOTION), "a wide fine-pointer homepage never got body.motion-ready")
    require(page.locator('[data-depth-dust],.mx-dust,.mx-light').count() == 0,
            "removed hero particles or ambient glow returned")
    at = page.evaluate("(() => { const r = document.querySelector('[data-depth-scene]').getBoundingClientRect();"
                       " return {x: r.left + r.width * .22, y: r.top + r.height * .5}; })()")
    before = page.locator("#hero-panel").bounding_box()
    page.mouse.move(at["x"], at["y"])
    page.wait_for_timeout(400)
    require(page.locator("#hero-panel").bounding_box() == before,
            "entering the hero moved the reading surface before a grab")
    top = float(page.evaluate(SCROLL) or 0)
    scroll_to(page, 420)
    down = poll(page, PROP, lambda v: v is not None and abs(v - top) > .05, [SCENE, "--mx-scroll"])
    require(abs(down - top) > .05, f"hero --mx-scroll did not react to the scroll ({top} -> {down})")
    require(page.evaluate("getComputedStyle(document.querySelector('#hero-panel')).transform") == "none",
            "the draggable hero still has an automatic transform")
    lifts, bottom = [], edge(page)
    for offset in (-1400, -700, -300):  # grid below the fold, entering it, deep inside it
        scroll_to(page, max(0, bottom - 600 + offset))
        lifts += page.evaluate(LIFTS)
    require(max(lifts, key=abs) > 1, f"cards never lifted from the scrolling parent grid: {lifts}")
    require(len({round(v) for v in lifts}) >= 2, f"cards ignored the scroll with a constant --mx-lift: {lifts}")
    found = page.evaluate("[...document.querySelectorAll('.product-suite-card')].map(c => c.getAttribute('href'))")
    require(found == CARDS, f"product card link targets changed: {found}")
    scroll_to(page, max(0, bottom - 1000))
    card = page.evaluate(CARD)
    require(card["hit"] == "self" and card["op"] == "1" and card["vis"] == "visible"
            and card["w"] > 100 and card["h"] > 100, f"card is not visible/clickable in place: {card}")
    page.mouse.move(card["box"]["x"] - 160, card["box"]["y"])
    page.wait_for_timeout(80)
    page.mouse.move(card["box"]["x"], card["box"]["y"])
    cxs = poll(page, "[...document.querySelectorAll('.product-suite-card')]"
                     ".map(c => parseFloat(c.style.getPropertyValue('--mx-cx') || 0))",
               lambda v: v and abs(v[1]) > .05)
    require(cxs and abs(cxs[1]) > .05, f"card --mx-cx did not react to the pointer: {cxs}")
    page.mouse.click(card["box"]["x"], card["box"]["y"])
    page.wait_for_url("**/ai-security", timeout=8000)
    require(urlsplit(page.url).path == "/ai-security", f"the platform card led to {page.url}")
    ctx.close()


def check_responsive(browser, base, net):
    """3: no horizontal overflow, no motion-ready under 900px, no hidden controls."""
    for width in (320, 390, 768, 1440):
        ctx, page = open_page(browser, base, net, viewport={"width": width, "height": 800})
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        require(over <= 1 and page.evaluate("document.body.scrollWidth") <= width + 1,
                f"{width}px: horizontal overflow of {over}px")
        ready = page.evaluate(MOTION)
        require(ready == (width >= 900), f"{width}px: motion-ready={ready}, expected {width >= 900}")
        require(len(page.locator("h1").first.inner_text().strip()) > 10, f"{width}px: h1 has no readable text")
        show(page.locator('a[href="#start"]').first, f"{width}px hero CTA")
        links = page.locator(".product-suite-card")
        require(links.count() == 3, f"{width}px: rendered {links.count()} product cards")
        for i in range(3):
            links.nth(i).scroll_into_view_if_needed()
            show(links.nth(i), f"{width}px product card {i}")
        ctx.close()
    ctx, page = open_page(browser, base, net, viewport={"width": 390, "height": 844},
                          is_mobile=True, has_touch=True, device_scale_factor=3)
    require(not page.evaluate(MOTION), "a coarse touch viewport got motion-ready")
    require(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 1,
            "a coarse touch viewport overflows horizontally")
    ctx.close()


def check_reduced(browser, base, net):
    """4: reduced motion clears motion-ready, resets the vars, starts and keeps no engine."""
    ctx, page = open_page(browser, base, net, reduced_motion="reduce")
    require(not page.evaluate(MOTION), "prefers-reduced-motion:reduce still got body.motion-ready")
    for y in (0, max(0, edge(page) - 1000), edge(page) + 200):
        scroll_to(page, y)
    require(page.evaluate("window.__mxRaf.count") == 0, "reduced motion still scheduled paintDepth")
    require(page.evaluate("document.querySelector('[data-depth-scene]').style.getPropertyValue('--mx-scroll')") == ""
            and page.evaluate("[...document.querySelectorAll('.product-suite-card')]"
                              ".every(c => c.style.getPropertyValue('--mx-lift') === '')"),
            "reduced motion wrote spatial scroll vars anyway")
    ctx.close()
    ctx, page = open_page(browser, base, net)
    require(page.evaluate(MOTION), "the dynamic-toggle arm has no motion to turn off")
    page.emulate_media(reduced_motion="reduce")
    require(poll(page, MOTION, lambda v: v is False, None, 4000) is False,
            "switching to prefers-reduced-motion did not clear body.motion-ready")
    require(page.evaluate(SCROLL) == "", "the toggle left --mx-scroll behind instead of resetting it")
    idle = settle(page)
    scroll_to(page, edge(page) + 200)
    page.wait_for_timeout(900)
    require(page.evaluate("window.__mxRaf.count") == idle, "paintDepth ran on after the reduced-motion toggle")
    page.emulate_media(reduced_motion="no-preference")
    require(poll(page, MOTION, lambda v: v is True, None, 4000) is True,
            "restoring motion preferences did not bring body.motion-ready back")
    ctx.close()


def check_no_js(browser, base, net):
    """5: with scripting disabled the h1 and every product link stay usable."""
    ctx, page = open_page(browser, base, net, java_script_enabled=False)
    heading, links = page.locator("h1").first, page.locator(".product-suite-card")
    require(heading.is_visible() and len(heading.inner_text().strip()) > 10,
            "the no-JS homepage h1 is not visible text")
    require(links.count() == 3 and [links.nth(i).get_attribute("href") for i in range(3)] == CARDS,
            "the no-JS homepage lost product cards or their link targets")
    for i in range(3):
        links.nth(i).scroll_into_view_if_needed()
        show(links.nth(i), f"no-JS product link {i}")
    show(page.locator('a[href="#start"]').first, "no-JS hero CTA")
    ctx.close()


def check_idle(browser, base, net):
    """7: the loop is demand-driven — it stops when idle and stays stopped offscreen."""
    ctx, page = open_page(browser, base, net)
    settle(page)
    offscreen = max(edge(page), page.evaluate("document.querySelector('[data-depth-scene]')"
                                              ".getBoundingClientRect().bottom + scrollY")) + 200
    scroll_to(page, offscreen)
    idle = settle(page)
    scroll_to(page, offscreen + 60)
    page.wait_for_timeout(900)
    require(page.evaluate("window.__mxRaf.count") == idle,
            "an offscreen scroll restarted paintDepth, so the engine is not viewport-gated")
    page.evaluate("scrollTo(0, 0)")
    grew = poll(page, "window.__mxRaf.count", lambda v: v is not None and v > idle, None, 5000)
    require(grew and grew > idle, "paintDepth never restarted when the hero scrolled back into view")
    settle(page)
    ctx.close()


CHECKS = (("wide-homepage-motion", check_wide), ("responsive-layout", check_responsive),
          ("reduced-motion", check_reduced), ("no-js-content", check_no_js),
          ("engine-idle-offscreen", check_idle))


def main():
    ap = argparse.ArgumentParser(description="Homepage spatial-motion smoke test")
    ap.add_argument("--base-url", default="http://127.0.0.1:18765")
    base = ap.parse_args().base_url.rstrip("/") + "/"
    if urlsplit(base).hostname not in LOOPBACK:
        print(f"FAIL base-url: must be loopback, got {base}")
        return 2
    net, failures = {"outside": [], "errors": [], "csp": [], "assets": {}}, []
    play = sync_playwright().start()
    try:
        browser = play.chromium.launch()
    except Exception:
        play.stop()
        raise  # Missing Chromium is fatal, not an aggregated/skippable check.
    try:
        for name, check in CHECKS:
            try:
                check(browser, base, net); print(f"PASS {name}")
            except Exception as exc:
                failures.append(name); print(f"FAIL {name}: {exc}")
        try:
            require(not net["outside"], f"requests left loopback: {net['outside'][:3]}")
            require(not net["errors"], f"page errors: {net['errors'][:5]}")
            require(not net["csp"], f"CSP violations: {net['csp'][:3]}")
            require(net["assets"].get("spatial-motion.js") == 200 and net["assets"].get("spatial-motion.css") == 200,
                    f"spatial-motion assets were not served 200: {net['assets']}")
        except AssertionError as exc:
            failures.append("network-console-hygiene"); print(f"FAIL network-console-hygiene: {exc}")
        else:
            print("PASS network-console-hygiene")
    finally:
        browser.close(); play.stop()
    total = len(CHECKS) + 1
    print(f"\n{total - len(failures)}/{total} checks passed against {base}"
          + ("" if not failures else f" — failed: {', '.join(failures)}"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
