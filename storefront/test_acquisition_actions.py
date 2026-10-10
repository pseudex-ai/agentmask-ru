"""Offline Chromium contract tests; no Django, providers, server or external I/O.

Run with a Playwright-enabled Python and installed Chromium. Set
PLAYWRIGHT_BROWSERS_PATH if the browsers live outside the default cache.
Media tests use ffmpeg only to generate a tiny anonymous in-memory MP4.
"""
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = (Path(__file__).parent / "static/acquisition-actions.js").read_text()
ORIGIN = "https://public.test"
KEY = "pseudex.analytics.consent"
BODY = """<h1>PRIVATE TEXT never transmitted</h1>
<a id="doc" href="/how?email=secret@example.test#private">Private link text</a>
<a id="annotated" href="/how" data-acquisition-goal="docs_open">Annotated</a>
<section id="faq"><details id="question"><summary>Private question</summary>Answer</details></section>
<div class="faq-grid"><details id="faqpage" open><summary>Question</summary>Answer</details></div>
<details id="support"><summary>Support</summary>Not FAQ</details>
<section id="configurator"><div id="cfg"><input id="selection" type="checkbox" data-group="PRIVATE"></div></section>
<input id="other" type="checkbox" value="PRIVATE">
<video id="video" controls preload="auto" width="240" src="/static/media/setup.mp4"></video>
<div style="height:3000px"></div>"""


def main():
    media = subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=20",
        "-t", "1.5", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "frag_keyframe+empty_moov", "-f", "mp4", "pipe:1",
    ], check=True, capture_output=True).stdout
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(service_workers="block")
        requests, errors = [], []
        context.route_web_socket("**/*", lambda ws: ws.close())

        def route(request):
            requests.append(request.request.url)
            if request.request.url == ORIGIN + "/static/media/setup.mp4":
                request.fulfill(body=media, content_type="video/mp4")
            elif request.request.is_navigation_request() and request.request.url.startswith(ORIGIN + "/"):
                request.fulfill(body="<!doctype html><html><body>" + BODY + "</body></html>", content_type="text/html")
            else:
                request.abort()
        context.route("**/*", route)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.clock.install()
        page.clock.pause_at("2030-01-01T00:00:00Z")

        def load(path="/", consent="yes", config=True, duplicate=False):
            page.goto(ORIGIN + path)
            page.evaluate("""({key, consent, config}) => {
                localStorage.clear();
                if (consent !== null) localStorage.setItem(key, consent);
                if (config) { const s = document.createElement('script'); s.dataset.metrikaId='123'; document.head.append(s); }
                window.events=[];
                document.addEventListener('pseudex:public-action', e => {
                    if (e.target !== document) throw Error('Wrong dispatch target');
                    events.push(e.detail);
                });
                document.addEventListener('click', e => { if(e.target.closest('a')) e.preventDefault(); });
            }""", {"key": KEY, "consent": consent, "config": config})
            page.add_script_tag(content=JS)
            if duplicate:
                page.add_script_tag(content=JS)
            assert page.evaluate("document.hasFocus()")

        def events(name=None):
            result = page.evaluate("events")
            return [e for e in result if name is None or e["name"] == name]

        def choose(value):
            page.evaluate("""({key,value}) => {
                localStorage.setItem(key,value);
                document.dispatchEvent(new CustomEvent('pseudex:analytics-consent'));
            }""", {"key": KEY, "value": value})

        for value in (None, "no"):
            load(consent=value)
            page.locator("#doc").click()
            page.locator("#question summary").click()
            page.clock.run_for(30000)
            assert events() == [], (value, events())
            choose("yes")
            page.clock.run_for(19000)
            assert events() == []
            page.clock.run_for(1500)
            assert len(events("content_engaged")) == 1

        load(duplicate=True)
        page.locator("#doc").click()
        assert events() == [{"name": "docs_open", "params": {"doc": "how"}}]
        page.locator("#annotated").click()
        assert len(events()) == 1
        for href, expected in [
            ("architecture", "architecture"), (ORIGIN + "/litellm", "litellm"),
            ("/baza-znaniy", "knowledge_base"),
            ("/baza-znaniy/kak-vybrat-sistemu", "knowledge_article"),
            ("/docs", "docs"), ("https://elsewhere.test/how", None),
            ("/how-private", None), ("/baza-znaniy/secret", None),
            ("/baza-znaniy/kak-vybrat-sistemu/secret", None),
            ("mailto:secret@example.test", None), ("//elsewhere.test/how", None),
        ]:
            before = len(events())
            page.locator("#doc").evaluate("(a, href) => a.setAttribute('href', href)", href)
            page.locator("#doc").click()
            assert len(events()) == before + (expected is not None), href
            if expected:
                assert events()[-1]["params"] == {"doc": expected}
        assert "secret" not in json.dumps(events()) and "PRIVATE" not in json.dumps(events())
        assert page.url == ORIGIN + "/"

        load("/how?token=private")
        page.clock.run_for(10000)
        choose("no")
        page.clock.run_for(30000)
        choose("yes")
        page.clock.run_for(11000)
        assert events() == []
        # Deterministic visibility boundary, real browser layout and clock.
        page.evaluate("Object.defineProperty(document, 'visibilityState', {configurable:true, value:'hidden'}); document.dispatchEvent(new Event('visibilitychange'))")
        page.clock.run_for(30000)
        assert events() == []
        page.evaluate("Object.defineProperty(document, 'visibilityState', {configurable:true, value:'visible'}); document.dispatchEvent(new Event('visibilitychange'))")
        page.evaluate("scrollTo(0, 1500)")
        page.clock.run_for(10000)
        assert events() == [{"name": "content_engaged", "params": {"section": "how", "threshold": "20s_visible"}}]
        page.clock.run_for(30000)
        assert len(events()) == 1

        load('/architecture')
        page.evaluate("document.querySelector('h1').style.display='none'")
        choose('no')
        choose('yes')
        page.clock.run_for(30000)
        assert events() == []
        page.evaluate("document.querySelector('h1').style.display='block'")
        page.clock.run_for(10000)
        page.evaluate("document.hasFocus=() => false; window.dispatchEvent(new Event('blur'))")
        page.clock.run_for(30000)
        assert events() == []
        page.evaluate("document.hasFocus=() => true; window.dispatchEvent(new Event('focus'))")
        page.clock.run_for(11000)
        assert events()[0]['params']['section'] == 'architecture'

        load()
        page.evaluate("() => { Storage.prototype.getItem=() => {throw Error('denied')}; }")
        page.locator('#doc').click()
        page.clock.run_for(30000)
        assert events() == []

        for path in ("/unknown", "/app/", "/baza-znaniy/private"):
            load(path)
            page.locator("#doc").click()
            page.clock.run_for(30000)
            assert events() == []
        load(config=False)
        page.locator("#doc").click()
        page.clock.run_for(30000)
        assert events() == []

        for path, selector, section in [("/", "#question", "home"), ("/faq", "#faqpage", "faq")]:
            load(path)
            page.locator("#support summary").click()
            assert events() == []
            if path == "/faq":
                page.locator(selector + " summary").click()
                page.clock.run_for(1)
                assert events() == []
            page.locator(selector + " summary").click()
            page.clock.run_for(1)
            page.wait_for_function("events.some(e => e.name === 'faq_open')")
            assert events() == [{"name": "faq_open", "params": {"section": section}}], (path, events())
            page.locator(selector + " summary").click()
            page.locator(selector + " summary").click()
            page.clock.run_for(1)
            assert len(events()) == 1

        load("/detection")
        page.locator("#other").check()
        page.locator("#selection").check()
        page.locator("#selection").uncheck()
        page.locator("#selection").check()
        assert events() == [{"name": "configurator_used", "params": {"placement": "configurator"}}]

        # Native media events and played time, not synthetic play/ended events.
        page.clock.resume()
        for case in ("autoplay", "seek", "normal", "preconsent", "revoke"):
            load(consent=None if case == "preconsent" else "yes")
            page.wait_for_function("document.querySelector('video').readyState >= 2")
            page.evaluate("""() => {
                const v=document.querySelector('video');
                window.ended=new Promise(resolve => v.addEventListener('ended', resolve, {once:true}));
                v.muted=true;
            }""")
            if case == "autoplay":
                page.evaluate("document.querySelector('video').play()")
            else:
                # Trusted pointerdown on the actual video plus a real play call
                # models a custom/native control without fragile shadow-DOM coords.
                page.locator("video").click(position={"x": 120, "y": 10})
                page.evaluate("document.querySelector('video').play()")
            if case == "seek":
                page.evaluate("document.querySelector('video').currentTime=1.35")
            if case == "preconsent":
                choose("yes")
            if case == "revoke":
                choose("no")
                choose("yes")
            page.evaluate("ended.then(() => true)")
            names = [e["name"] for e in events()]
            if case == "normal":
                assert names == ["setup_video_started", "setup_video_completed"], (case, events())
            elif case in ("seek", "revoke"):
                assert names == ["setup_video_started"], (case, events())
            else:
                assert names == [], (case, events())
        assert not errors, errors
        assert all(url.startswith(ORIGIN + "/") for url in requests), requests
        context.close()
        browser.close()
    print("PASS: public actions consent, timing, enums, docs, FAQ, configurator and native video (offline Chromium)")


if __name__ == "__main__":
    main()
