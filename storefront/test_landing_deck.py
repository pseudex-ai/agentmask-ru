#!/usr/bin/env python3
"""Read-only Playwright regression for the landing hero deck and the #how route cue.

Contract: templates/landing.html, static/hero-deck.{js,css}, static/landing-route.{js,css},
static/landing-interactions.css, and the HERO_CASES/heroToken/heroRecord fixtures landing.js
exposes to hero-deck.js. The deck is SIX PHASES OF ONE EXISTING CUSTOMER ORDER, not a carousel.
Phase 3 hides .hero-token-real at opacity:0 while its textContent stays in the DOM — that is the
synthetic before/after scene, so the assertion is computed opacity, never hidden-text presence.

    python test_landing_deck.py --base-url http://127.0.0.1:18765

One loopback origin; no form submit, lead, account, model or provider call; any request leaving
loopback is aborted and reported. NOT proven: paint quality, touch hardware, production settings.
"""
import argparse
import sys
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

sys.dont_write_bytecode = True
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
CARDS = ["/#start", "/ai-security", "/ai-coding"]
RAIL, DIALOG, PANEL = "#hero-rail button[data-hero-phase]", "#hero-dialog", "#hero-panel"
REAL = ("волков дмитрий", "мончгорская 12 кв 84", "89178347030")
FAKE = ("шилов виктор", "чистопольская 41 кв 57", "89035571942")
PH = "document.querySelector('#hero-panel').dataset.heroCurrentPhase"
GHOSTS = "document.querySelectorAll('.hero-window-ghost').length"
PAUSE_OFF = "document.querySelector('[data-hero-pause]').disabled"
FAQ_OPEN = "document.querySelector('#faq details').hasAttribute('open')"
PROG = "parseFloat(document.querySelector('[data-route-grid]').style.getPropertyValue('--route-progress')||-1)"
SHADOW = """getComputedStyle(document.querySelector('#signup-form input[type="email"]')).boxShadow"""
TURN = """document.querySelector('#hero-rail button[data-hero-phase="2"]').click()"""
# Instrument the deck's and the cue's OWN callbacks: landing.js and spatial-motion.js register
# their own rAF/animate, so a raw total would score the whole page instead of the contract.
ANIM = ("(() => { const a = Element.prototype.animate, s = {n: 0, frames: []}; Element.prototype.animate ="
        " function (f, o) { s.n++; s.frames.push(f); return a.call(this, f, o); }; window.__anim = s; })()")
RAF = ("(() => { const a = window.requestAnimationFrame.bind(window); window.__routeRaf = {count: 0};"
       " window.requestAnimationFrame = function (cb) { if (typeof cb === 'function' && cb.name === 'paintRoute')"
       " window.__routeRaf.count++; return a(cb); }; })()")
SWAP = ("(() => { const r = document.querySelector('.hero-token-real'), f = document.querySelector('.hero-token-fake');"
        " return {real: getComputedStyle(r).opacity, fake: getComputedStyle(f).opacity, realText: r.textContent.trim(),"
        " fakeText: f.textContent.trim()}; })()")
GHOST = ("(() => { document.querySelector('[data-hero-step=\"1\"]').click(); const g = document.querySelector('.hero-window-ghost');"
         " return g && {count: document.querySelectorAll('.hero-window-ghost').length, ids: g.querySelectorAll('[id]').length,"
         " ownId: g.hasAttribute('id'), data: [...g.attributes].filter(x => x.name.startsWith('data-')).length,"
         " aria: g.getAttribute('aria-hidden'), inert: g.hasAttribute('inert'),"
         " phase: document.querySelector('#hero-panel').dataset.heroCurrentPhase}; })()")
RAPID = ("(() => { const b = document.querySelector('[data-hero-step=\"1\"]'); for (let i = 0; i < 4; i++) b.click();"
         " return document.querySelectorAll('.hero-window-ghost').length; })()")
LEGS = ("(() => { const k = [...document.querySelector('[data-route-grid]').children];"
        " return {cur: k.findIndex(x => x.classList.contains('is-route-current')), done: k.map((x, i) =>"
        " x.classList.contains('is-route-done') ? i : -1).filter(i => i >= 0)}; })()")
BURST = ("(() => { const n = window.__routeRaf.count; for (let i = 0; i < 5; i++) dispatchEvent(new Event('scroll'));"
         " return window.__routeRaf.count - n; })()")
HIDDEN = ("(on) => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => on});"
          " document.dispatchEvent(new Event('visibilitychange')); if (on) document.activeElement.blur(); }")
# Form-relative, so a settling reveal transform or the browser's own focus scroll cannot fake a shift.
STAMP = ("(() => { const f = document.querySelector('#signup-form'), r = f.getBoundingClientRect();"
         " return [f.querySelector('button[type=\"submit\"]'), f.querySelector('.pp-p')].flatMap(e =>"
         " [e.getBoundingClientRect().x - r.x, e.getBoundingClientRect().y - r.y])"
         ".concat([r.width, r.height]).map(v => Math.round(v * 10) / 10); })()")


def require(cond, msg):
    assert cond, msg


def poll(page, expr, want, arg=None, timeout=5000):
    """Bounded wait; returns the last observed value, satisfying or not."""
    end, value = time.monotonic() + timeout / 1000, None
    while time.monotonic() < end and not want(value):
        value = page.evaluate(expr, arg)
        page.wait_for_timeout(100)
    return value


def settle(page, expr, stable=3):
    """Idle means the counter stopped changing, not that time passed."""
    last, same = -1, 0
    for _ in range(80):
        count = page.evaluate(expr)
        same, last = (same + 1, count) if count == last else (0, count)
        if same >= stable:
            return last
        page.wait_for_timeout(120)
    raise AssertionError("the frame callback never went idle, so it is still looping")


def page_of(browser, base, net, scripts=(), clock=False, **kw):
    """One context + page: loopback route guard, instruments, error/CSP/asset collectors."""
    kw.setdefault("viewport", {"width": 1440, "height": 950})
    ctx, origin = browser.new_context(**kw), (urlsplit(base).scheme, urlsplit(base).netloc)

    def guard(handler, request):
        url = urlsplit(request.url)
        if (url.scheme, url.netloc) == origin:
            handler.continue_()
        else:
            net["outside"].append(request.url)
            handler.abort()

    ctx.route("**/*", guard)
    for script in scripts:
        ctx.add_init_script(script)
    page = ctx.new_page()
    if clock:
        page.clock.install()
    page.on("pageerror", lambda e: net["errors"].append(str(e)))
    page.on("console", lambda m: net["csp"].append(m.text) if "Content Security Policy" in m.text else None)
    page.on("response", lambda r: net["assets"].__setitem__(urlsplit(r.url).path.rsplit("/", 1)[-1], r.status)
            if any(k in r.url for k in ("hero-deck", "landing-route", "landing-interactions")) else None)
    response = page.goto(base, wait_until="load")
    require(response is not None and response.status == 200, f"landing did not return 200 ({response and response.status})")
    return ctx, page


def phase(page):
    return page.evaluate(PH)


def goto_phase(page, n):
    page.locator(f'{RAIL}[data-hero-phase="{n}"]').click()
    require(poll(page, PH, lambda v: v == str(n)) == str(n), f"rail segment {n} did not select phase {n}")


def check_phases(browser, base, net):
    """The six sheets, the rail, both arrows, wrap-around, keyboard and the turn-time ghost."""
    ctx, page = page_of(browser, base, net, (ANIM,))
    page.wait_for_selector(RAIL)
    require(page.locator(RAIL).count() == 6, "the rail is not six segments")
    require(page.evaluate("[...document.querySelectorAll('#hero-rail button')].filter(b => b.getAttribute('aria-pressed') === 'true').length") == 1,
            "the rail does not mark exactly one segment pressed")
    require(phase(page) == "1", f"a wide load must open on the raw customer phase, got {phase(page)}")
    for n in range(1, 7):
        goto_phase(page, n)
        require(page.locator(f"{DIALOG} > [data-order-sheet]").count() == 1, f"phase {n} is not one order sheet")
    for n, want in ((1, REAL), (5, ("Волков", "Мончегорская"))):
        goto_phase(page, n)
        text = page.locator(DIALOG).inner_text()
        require(all(w in text for w in want), f"phase {n} is missing {[w for w in want if w not in text]}")
    goto_phase(page, 4)
    pre = page.locator(f"{DIALOG} pre").first.inner_text().lower()
    require(all(v in pre for v in FAKE) and not any(v in pre for v in REAL),
            f"phase 4 handed the model something other than fakes: {pre!r}")
    require("перенести доставку" in page.locator(DIALOG).inner_text().lower(), "phase 4 lost the decision")
    goto_phase(page, 3)
    swap = page.evaluate(SWAP)
    require(swap["fake"] == "1" and swap["real"] == "0" and swap["realText"] and swap["fakeText"],
            f"phase 3 is not the plausible swap (hidden text is the scene, not a leak): {swap}")
    goto_phase(page, 6)
    sides = page.locator(f"{DIALOG} .hero-sheet-compare .hero-sheet-side")
    require(sides.count() == 2 and any(v in sides.nth(0).inner_text().lower() for v in FAKE)
            and "Волков" in sides.nth(1).inner_text(), "phase 6 does not put the swaps beside the local originals")
    case = page.get_attribute(PANEL, "data-hero-case")
    page.locator('[data-hero-step="1"]').click()
    require(poll(page, PH, lambda v: v == "1") == "1" and page.get_attribute(PANEL, "data-hero-case") != case,
            "the forward arrow did not wrap into the next case")
    page.locator('[data-hero-step="-1"]').click()
    require(poll(page, PH, lambda v: v == "6") == "6" and page.get_attribute(PANEL, "data-hero-case") == case,
            "the reverse arrow did not wrap back to the previous case")
    goto_phase(page, 2)
    page.locator(f'{RAIL}[data-hero-phase="2"]').focus()
    page.keyboard.press("ArrowRight")
    require(poll(page, PH, lambda v: v == "3") == "3", "ArrowRight inside the deck controls did not advance")
    page.keyboard.press("ArrowLeft")
    require(poll(page, PH, lambda v: v == "2") == "2", "ArrowLeft inside the deck controls did not reverse")
    goto_phase(page, 1)
    ghost = page.evaluate(GHOST)
    require(ghost and ghost["count"] == 1 and ghost["ids"] == 0 and ghost["data"] == 0 and not ghost["ownId"]
            and ghost["aria"] == "true" and ghost["inert"] and ghost["phase"] == "2",
            f"the turning ghost is not an inert, id-stripped clone of the public screen body: {ghost}")
    require(page.evaluate("""() => document.querySelector('#hero-dialog').getAnimations().some(a => a.effect.getTiming().duration === 460)
        && document.querySelector('#hero-panel').getAnimations().length === 0
        && !document.querySelector('.hero-window-ghost').querySelector('form,input,textarea,.hero-ctl,.hero-rail')"""),
        "only the public screen body may turn; controls must stay put and forms must never be cloned")
    require(poll(page, GHOSTS, lambda v: v == 0, 2500) == 0, "the ghost outlived its 360ms leave")
    rapid = page.evaluate(RAPID)
    require(rapid <= 1, f"rapid turns stacked {rapid} ghosts instead of cancelling the old ones")
    require(poll(page, GHOSTS, lambda v: v == 0, 2500) == 0, "ghosts from rapid turns were never cleaned up")
    ctx.close()


def check_reduced_motion(browser, base, net):
    """Reduced motion: finished phase, dead autoplay, manual steps still work, live toggle."""
    ctx, page = page_of(browser, base, net, (ANIM,), reduced_motion="reduce")
    page.wait_for_selector(RAIL)
    require(phase(page) == "6", f"reduced motion must open on the finished phase, got {phase(page)}")
    require(page.locator("[data-hero-pause]").is_disabled(), "reduced motion left autoplay enabled")
    require(page.evaluate("window.__anim.n") == 0, "reduced motion still animated the first render")
    goto_phase(page, 1)
    page.locator('[data-hero-step="1"]').click()
    require(poll(page, PH, lambda v: v == "2") == "2" and page.evaluate("window.__anim.n") == 0 and page.evaluate(GHOSTS) == 0,
            "manual steps under reduced motion must work without WAAPI or a ghost")
    ctx.close()
    ctx, page = page_of(browser, base, net, (ANIM,))
    require(phase(page) == "1", "the dynamic-toggle arm has no motion to turn off")
    page.emulate_media(reduced_motion="reduce")
    require(poll(page, PAUSE_OFF, lambda v: v is True, 4000) is True, "reduced motion did not disable autoplay")
    turns = page.evaluate("window.__anim.n")
    goto_phase(page, 4)
    require(page.evaluate("window.__anim.n") == turns and page.evaluate(GHOSTS) == 0,
            "the dynamic reduced-motion toggle kept turning with WAAPI or a ghost")
    page.emulate_media(reduced_motion="no-preference")
    require(poll(page, PAUSE_OFF, lambda v: v is False, 4000) is False, "restoring motion did not re-enable autoplay")
    ctx.close()


def check_autoplay(browser, base, net):
    """Autoplay stops on explicit pause, hover, focus and document.hidden (fake clock) and,
    on the real clock, while the deck is scrolled out of view."""
    ctx, page = page_of(browser, base, net, clock=True)
    page.wait_for_selector(RAIL)
    page.clock.run_for(3000)
    require(phase(page) == "2", f"autoplay never advanced from phase 1 (phase {phase(page)})")
    page.locator("[data-hero-pause]").click()
    require(page.get_attribute("[data-hero-pause]", "aria-pressed") == "true", "pause did not flip aria-pressed")
    page.clock.run_for(15000)
    require(phase(page) == "2", "an explicit pause did not stop autoplay")
    page.locator("[data-hero-pause]").click()
    page.mouse.move(5, 5)  # the click itself hovers the deck, and hover is the next thing under test
    page.clock.run_for(3000)
    require(phase(page) != "2", "resuming did not restart autoplay")
    box = page.locator(PANEL).bounding_box()  # coordinates: decorative planes can obscure a locator.hover
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    held = phase(page)
    page.clock.run_for(15000)
    require(phase(page) == held, "hovering the deck did not pause autoplay")
    page.mouse.move(5, 5)
    page.locator(f'{RAIL}[data-hero-phase="1"]').focus()
    page.clock.run_for(15000)
    require(phase(page) == held, "focus inside the deck did not pause autoplay")
    page.evaluate(HIDDEN, True)
    page.clock.run_for(20000)
    require(phase(page) == held, "autoplay kept running while document.hidden")
    page.evaluate(HIDDEN, False)
    page.clock.run_for(4000)
    require(phase(page) != held, "autoplay never resumed after the document became visible again")
    ctx.close()
    ctx, page = page_of(browser, base, net)
    page.evaluate("scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1300)
    held = phase(page)
    page.wait_for_timeout(4300)  # longer than the longest dwell (phase 6: 3400ms)
    require(phase(page) == held, f"the deck kept turning offscreen ({held} -> {phase(page)})")
    ctx.close()


def check_route(browser, base, net):
    """#how publishes one bounded --route-progress per paint and three leg classes."""
    ctx, page = page_of(browser, base, net, (RAF,))
    require(page.locator("[data-route-grid] > div").count() == 3, "the route grid is not three legs")
    page.evaluate("document.querySelector('[data-route-grid]').scrollIntoView({block: 'center'})")
    progress = poll(page, PROG, lambda v: v is not None and v >= 0, timeout=5000)
    require(progress is not None and progress >= 0, f"native scroll never published --route-progress ({progress})")
    legs = page.evaluate(LEGS)
    require(legs["cur"] >= 0 and legs["done"] == list(range(legs["cur"])),
            f"the legs are not one current with exactly the ones before it done: {legs}")
    page.evaluate("scrollBy(0, 260)")
    moved = poll(page, PROG, lambda v: v is not None and v > progress, timeout=4000)
    require(moved > progress, f"--route-progress did not follow the scroll ({progress} -> {moved})")
    settle(page, "window.__routeRaf.count")
    delta = page.evaluate(BURST)
    require(delta == 1, f"five scroll events scheduled {delta} paints instead of coalescing into one")
    page.evaluate("scrollTo(0, 0)")
    page.wait_for_timeout(1300)
    idle = page.evaluate("window.__routeRaf.count")
    page.evaluate("scrollBy(0, 300)")
    page.wait_for_timeout(900)
    require(page.evaluate("window.__routeRaf.count") == idle, "the route cue kept looping after leaving the viewport")
    ctx.close()
    ctx, page = page_of(browser, base, net, (RAF,), reduced_motion="reduce")
    page.evaluate("document.querySelector('[data-route-grid]').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(700)
    require(page.evaluate(PROG) == -1 and page.evaluate("window.__routeRaf.count") == 0
            and page.evaluate("[...document.querySelectorAll('[data-route-grid] > div')].every(d =>"
                              " !d.classList.contains('is-route-current') && !d.classList.contains('is-route-done')"
                              " && d.getBoundingClientRect().height > 60)"),
            "reduced motion did not leave the whole route present and static")
    ctx.close()


def check_layout(browser, base, net):
    """Four widths in both themes with the alpha-only turn, then hover, focus, FAQ and no-JS."""
    for width, scheme in ((320, "light"), (390, "dark"), (768, "light"), (1440, "dark")):
        ctx, page = page_of(browser, base, net, (ANIM,), viewport={"width": width, "height": 900}, color_scheme=scheme)
        over = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        require(over <= 1, f"{width}px/{scheme}: {over}px of horizontal overflow")
        require(page.locator("header.top").is_visible() and len(page.locator("footer").first.inner_text().strip()) > 20,
                f"{width}px/{scheme}: the shared header or footer was lost")
        require(page.evaluate("document.body.classList.contains('motion-ready')") == (width >= 900),
                f"{width}px: the spatial-motion gate moved")
        require(page.evaluate("[...document.querySelectorAll('.product-suite-card')].map(c => c.getAttribute('href'))") == CARDS,
                f"{width}px/{scheme}: product card targets changed")
        page.wait_for_selector(RAIL)
        page.evaluate(TURN)
        flat = [f for frame in page.evaluate("window.__anim.frames")
                for f in (frame if isinstance(frame, list) else [frame]) if isinstance(f, dict)]
        require(any("transform" in f for f in flat) == (width >= 900),
                f"{width}px: the turn keyframes do not follow the 900px alpha-only breakpoint")
        if width < 900:
            require(page.evaluate(f"getComputedStyle(document.querySelector('{PANEL}')).transform") == "none",
                    f"{width}px: the resting hero panel is under a transform")
        ctx.close()
    ctx, page = page_of(browser, base, net, viewport={"width": 1440, "height": 950})
    lifts = []
    for selector in ("#demo .cards > *", "#coverage .cards > *", "#pricing .cards > *"):
        page.locator(selector).first.scroll_into_view_if_needed()
        page.locator(selector).first.hover()
        page.wait_for_timeout(800)
        lifts.append(page.evaluate(f"getComputedStyle(document.querySelector('{selector}')).transform"))
    require(all(t == "none" for t in lifts), f"a generic card lift survived the interactions sheet: {lifts}")
    page.locator("#start").scroll_into_view_if_needed()
    before = page.evaluate(STAMP)
    for _ in range(20):  # wait out the form's own reveal transition before stamping
        page.wait_for_timeout(150)
        if page.evaluate(STAMP) == before:
            break
        before = page.evaluate(STAMP)
    page.locator('#signup-form input[type="email"]').focus()
    page.wait_for_timeout(350)
    shadow = page.evaluate(SHADOW)
    require("inset" in shadow, f"the signup email focus is invisible ({shadow})")
    require(page.evaluate(STAMP) == before, "focusing the signup input moved the form, the price or the submit control")
    page.locator("#faq").scroll_into_view_if_needed()
    item = page.locator("#faq details").first
    require(item.get_attribute("open") is None, "a FAQ item was open before the click")
    item.locator("summary").click()
    require(poll(page, FAQ_OPEN, lambda v: v is True) is True and item.locator(".faq-a").first.is_visible(),
            "the FAQ item did not open")
    item.locator("summary").click()
    require(poll(page, FAQ_OPEN, lambda v: v is False) is False, "the FAQ item did not close")
    ctx.close()
    ctx, page = page_of(browser, base, net, java_script_enabled=False)
    sheet = page.locator(f"{DIALOG} .hero-deck-sheet")
    require(sheet.count() == 1 and sheet.is_visible() and len(sheet.inner_text().strip()) > 60,
            "the no-JS hero fallback is missing or empty")
    require(page.locator("#hero-rail button").count() == 0 and page.locator("h1").first.is_visible(),
            "the no-JS page kept a built rail or lost its heading")
    ctx.close()


CHECKS = (("hero-six-phase-order", check_phases), ("hero-reduced-motion", check_reduced_motion),
          ("hero-autoplay-pause", check_autoplay), ("route-progress-cue", check_route),
          ("responsive-interactions-nojs", check_layout))


def main():
    ap = argparse.ArgumentParser(description="Landing hero-deck and route-cue regression")
    ap.add_argument("--base-url", default="http://127.0.0.1:18765")
    base = ap.parse_args().base_url.rstrip("/") + "/"
    if urlsplit(base).hostname not in LOOPBACK:
        print(f"FAIL base-url: must be loopback, got {base}")
        return 2
    net, failures = {"outside": [], "errors": [], "csp": [], "assets": {}}, []
    try:
        play = sync_playwright().start()
        browser = play.chromium.launch()
    except Exception as exc:  # no browser is a failure, never a skip
        print(f"FAIL browser: Chromium is unavailable ({type(exc).__name__}: {str(exc).splitlines()[0][:160]})")
        return 2
    try:
        for name, check in CHECKS:
            try:
                check(browser, base, net)
                print(f"PASS {name}")
            except Exception as exc:
                failures.append(name)
                print(f"FAIL {name}: {exc}")
        for label, key in (("requests left loopback", "outside"), ("page errors", "errors"), ("CSP violations", "csp")):
            require(not net[key], f"{label}: {net[key][:3]}")
        wanted = ("hero-deck.css", "hero-deck.js", "landing-route.css", "landing-route.js", "landing-interactions.css")
        require(all(net["assets"].get(name) == 200 for name in wanted),
                f"the new stylesheets and scripts were not all served 200: {net['assets']}")
    except AssertionError as exc:
        failures.append("network-console-assets")
        print(f"FAIL network-console-assets: {exc}")
    else:
        print("PASS network-console-assets")
    finally:
        browser.close()
        play.stop()
    total = len(CHECKS) + 1
    print(f"\n{total - len(failures)}/{total} checks passed against {base}"
          + ("" if not failures else f" — failed: {', '.join(failures)}"))
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
