#!/usr/bin/env python3
"""Read-only local regression: persistent click-operated stack and continuous depth.
Run: python test_landing_deck.py --base-url http://127.0.0.1:18765
No forms, signup, providers, engine calls or paid operations. Chromium only.
"""
import argparse
import time
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

FRONT = '.hero-stack-card.is-front'
PANEL = '#hero-panel'
REAL = ('волков дмитрий', 'мончгорская 12 кв 84', '89178347030')
FAKE = ('шилов виктор', 'чистопольская 41 кв 57', '89035571942')
ANIM = """(()=>{const fn=Element.prototype.animate;window.__turns=0;
Element.prototype.animate=function(...args){if(this.classList.contains('hero-stack-card'))window.__turns++;return fn.apply(this,args);};})()"""


def require(value, message):
    assert value, message


def idle(page):
    page.wait_for_function("()=>!document.querySelector('#hero-dialog').classList.contains('is-dealing')", timeout=6000)


def phase(page):
    return int(page.locator(PANEL).get_attribute('data-hero-current-phase'))


def go(page, target):
    for _ in range(6):
        if phase(page) == target:
            return
        page.locator(FRONT).click()
        idle(page)
    raise AssertionError('could not reach the requested phase by clicking cards')


def opened(browser, url, net, **options):
    ctx = browser.new_context(**options)
    origin = urlsplit(url)
    def route(handler):
        req = handler.request
        url = urlsplit(req.url)
        if (url.scheme, url.netloc) != (origin.scheme, origin.netloc) or req.method != 'GET':
            net['forbidden'].append((req.method, req.url)); handler.abort()
        else:
            handler.continue_()
    ctx.route('**/*', route)
    ctx.add_init_script(ANIM)
    page = ctx.new_page()
    page.on('pageerror', lambda e: net['errors'].append(str(e)))
    page.on('console', lambda m: net['errors'].append(m.text) if 'Content Security Policy' in m.text else None)
    response = page.goto(url, wait_until='networkidle')
    require(response and response.status == 200, 'page did not load: '+url)
    return ctx, page


def persistent(browser, base, net):
    ctx, page = opened(browser, base, net, viewport={'width': 1440, 'height': 1100})
    require(page.locator('.hero-stack-card').count() == 18, 'orders must be built as 18 persistent populated sheets')
    require(page.locator('#hero-rail,#hero-phase,[data-hero-step],[data-hero-pause],.mx-plane').count() == 0, 'old toolbar or fake backing screens remain')
    page.evaluate("window.__cards=[...document.querySelectorAll('.hero-stack-card')];window.__texts=window.__cards.map(c=>c.textContent);window.__old=document.querySelector('.hero-stack-card.is-front')")
    page.locator(FRONT).click()
    page.evaluate("document.querySelector('.hero-stack-card.is-front').click()")
    require(phase(page) == 2, 'a second click started another deal before the first finished')
    page.evaluate("window.__old.getAnimations().forEach(a=>{a.pause();a.currentTime=240;})")
    state = page.evaluate("""()=>({y:new DOMMatrix(getComputedStyle(__old).transform).m42,opacity:getComputedStyle(__old).opacity,
        active:__cards.filter(c=>c.getAnimations().length).length,kept:__old.isConnected})""")
    require(state['y'] > 70 and state['opacity'] == '1' and state['active'] == 1 and state['kept'], 'only one opaque physical sheet must descend first: '+str(state))
    page.evaluate("window.__old.getAnimations().forEach(a=>a.play())")
    page.wait_for_function("()=>window.__old.getAnimations().some(a=>a.effect.getKeyframes().length===3)")
    page.evaluate("window.__back=window.__old.getAnimations()[0];window.__back.pause()")
    depths = []
    for at in (0, 140, 280, 500):
        depths.append(page.evaluate("""at=>{__back.currentTime=at;const s=getComputedStyle(__old);return {
            z:new DOMMatrix(s.transform).m43,layer:s.zIndex,opacity:s.opacity,visible:s.visibility};}""", at))
    require(all(b['z'] < a['z'] for a, b in zip(depths, depths[1:])), 'return does not continuously travel backward: '+str(depths))
    require(all(d['layer'] == 'auto' and d['opacity'] == '1' and d['visible'] == 'visible' for d in depths), 'return still cuts a layer or fades/disappears')
    require(page.locator('#hero-dialog').evaluate("e=>getComputedStyle(e).transformStyle==='preserve-3d'&&getComputedStyle(e).isolation==='auto'"), 'the depth scene is flattened')
    page.evaluate('__back.play()'); idle(page)
    require(page.evaluate("__cards.every((c,i)=>c.isConnected&&c===[...document.querySelectorAll('.hero-stack-card')][i]&&c.textContent===__texts[i])"), 'a turn recreated a sheet or replaced its contents')
    page.emulate_media(reduced_motion='reduce')
    go(page, 4)
    text = page.locator(FRONT+' pre').first.inner_text().lower()
    require(all(x in text for x in FAKE) and not any(x in text for x in REAL), 'model view lost its plausible substitutes')
    go(page, 5)
    require('Волков' in page.locator(FRONT).inner_text(), 'tool view lost the original identity')
    for at in range(1, 7):
        go(page, at)
        require(page.locator(FRONT).count() == 1, 'more than one active sheet')
    ctx.close()


def manual(browser, base, net):
    ctx, page = opened(browser, base, net, reduced_motion='reduce')
    turns = page.evaluate('window.__turns')
    page.locator(FRONT).focus(); page.keyboard.press('Enter')
    require(phase(page) == 1, 'Enter did not wrap the final sheet to the next order')
    page.keyboard.press(' '); require(phase(page) == 2, 'Space did not advance')
    page.keyboard.press('ArrowLeft'); require(phase(page) == 1, 'left arrow did not go back')
    require(page.evaluate('window.__turns') == turns, 'reduced motion still animates')
    page.clock.install(); page.clock.run_for(20000)
    require(phase(page) == 1, 'manual-only stack still has autoplay')
    require(page.locator(FRONT).get_attribute('role') == 'button', 'clickable sheet has no keyboard semantics')
    ctx.close()
    ctx, page = opened(browser, base, net, java_script_enabled=False)
    require(page.locator('#hero-dialog .hero-deck-sheet').is_visible(), 'no-JS fallback missing')
    require(page.locator('h1').count() == 1, 'no-JS content lost')
    ctx.close()


def layout(browser, base, net):
    for width in (320, 390, 768, 1440):
        ctx, page = opened(browser, base, net, viewport={'width': width, 'height': 1100}, reduced_motion='reduce')
        require(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), str(width)+' horizontal overflow')
        require(page.locator('.mx-dust,.mx-light,[data-depth-dust]').count() == 0, 'particles or ambient glow remain')
        require(page.locator('#top').evaluate("e=>getComputedStyle(e).userSelect==='none'"), 'hero text is still selectable')
        require(page.locator('#signup-form input[type=email]').evaluate("e=>getComputedStyle(e).userSelect!=='none'"), 'selection suppression leaked into forms')
        if width == 1440:
            h = page.locator('.hero-copy h1').bounding_box(); lead = page.locator('.hero-lead').bounding_box(); actions = page.locator('.hero-actions').bounding_box()
            require(lead['y'] > h['y']+h['height']+35 and actions['y'] > lead['y']+lead['height']+50, 'copy is still crowded at the top')
            require(page.locator('.mx-grid-floor').evaluate("e=>Math.abs(+getComputedStyle(e).opacity-.22)<.01&&getComputedStyle(e).display!=='none'"), 'floor did not return to the quiet original styling')
        page.locator('[data-theme-toggle]').click()
        require(page.locator('h1').is_visible(), 'theme change hid the heading')
        ctx.close()


def lift(browser, base, net):
    ctx, page = opened(browser, base, net, viewport={'width': 1440, 'height': 1100})
    for selector in ('#top .metric','#demo .cards>div','#coverage .cards>div','#pricing .cards>div','#how .cards>div'):
        card = page.locator(selector).first; card.scroll_into_view_if_needed()
        previous, stable = card.bounding_box(), 0
        for _ in range(30):
            page.wait_for_timeout(100); current = card.bounding_box(); stable = stable+1 if current == previous else 0; previous = current
            if stable >= 3: break
        card.hover()
        page.wait_for_function("s=>{const e=document.querySelector(s);return e.matches(':hover')&&new DOMMatrix(getComputedStyle(e).transform).m42< -2.8;}", arg=selector)
    ctx.close()



def tactile(browser, base, net):
    ctx, page = opened(browser, base, net, viewport={'width':1440,'height':1100})
    page.evaluate("window.__refs=[...document.querySelectorAll('.hero-stack-card')]")
    for dx,dy in ((155,0),(-155,0),(0,-145),(0,145)):
        old=phase(page); r=page.locator(FRONT).bounding_box(); x=r['x']+r['width']/2; y=r['y']+r['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+dx,y+dy,steps=10)
        require(page.locator('#hero-dialog').evaluate("e=>e.classList.contains('is-dragging')"), 'pointer did not actually grab the sheet')
        page.mouse.up();idle(page)
        require(phase(page)==old%6+1, 'free-direction throw skipped or failed')
    old=phase(page);r=page.locator(FRONT).bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+17,y+11,steps=6);page.mouse.up();idle(page)
    require(phase(page)==old,'small movement did not snap back')
    page.mouse.down();page.mouse.move(x+130,y-50,steps=8);page.keyboard.press('Escape');idle(page);page.mouse.up()
    require(phase(page)==old,'Escape followed by pointer release advanced the sheet')
    require(page.evaluate("__refs.every((e,i)=>e.isConnected&&e===[...document.querySelectorAll('.hero-stack-card')][i])"),'drag replaced persistent sheets')
    require(urlsplit(page.url).path=='/ai-service','throw accidentally activated a CTA underneath')
    ctx.close()


def directional(browser, base, net):
    ctx,page=opened(browser,base,net,viewport={'width':1440,'height':1100})
    card=page.locator('#coverage .cards>div').nth(2);card.scroll_into_view_if_needed();page.mouse.move(0,0);page.wait_for_timeout(750)
    for side in ('top','right','bottom','left'):
        r=card.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
        if side=='top':y=r['y']+8
        if side=='bottom':y=r['y']+r['height']-8
        if side=='left':x=r['x']+8
        if side=='right':x=r['x']+r['width']-8
        page.mouse.move(x,y)
        page.wait_for_function("s=>document.querySelectorAll('#coverage .cards>div')[2].querySelector('.directional-edge').dataset.edge===s",arg=side)
        require(card.locator('>.directional-edge').get_attribute('aria-hidden')=='true','edge entered accessibility content')
    buy=page.locator('#pricing a[data-plan=work]');buy.scroll_into_view_if_needed();page.mouse.move(0,0);page.wait_for_timeout(650)
    before=buy.get_attribute('href');buy.hover()
    page.wait_for_function("()=>getComputedStyle(document.querySelector('#pricing a[data-plan=work]')).backgroundSize==='100% 100%'")
    require(buy.locator('>.directional-edge.is-on').count()==1,'working plan CTA has no edge hover')
    require(buy.evaluate("e=>getComputedStyle(e).position==='static'"),'edge positioning broke the native stretched link')
    r=buy.locator('..').bounding_box()
    require(page.evaluate("p=>document.elementFromPoint(p.x,p.y).closest('a')?.dataset.plan",{'x':r['x']+r['width']/2,'y':r['y']+75})=='work','full-card link hit area changed')
    require(buy.get_attribute('href')==before=='#start','working CTA target changed')
    page.locator('#signup-form input[type=email]').focus()
    require(page.locator('#signup-form input[type=email]').evaluate('e=>document.activeElement===e'),'edge blocks a native field')
    ctx.close()


def touch_drag(browser, base, net):
    ctx,page=opened(browser,base,net,viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
    require(page.locator('.directional-edge').count()==0,'touch created sticky hover overlays')
    paper=page.locator(FRONT);paper.scroll_into_view_if_needed();page.wait_for_timeout(300)
    grip=paper.locator('[data-sheet-grip]');r=grip.bounding_box();x=r['x']+r['width']/2;y=r['y']+4
    old=phase(page);cdp=ctx.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for step in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+3,'y':y+step*17}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});idle(page)
    require(phase(page)==old%6+1,'vertical touch throw from the grip failed')
    paper=page.locator(FRONT);paper.scroll_into_view_if_needed();page.wait_for_timeout(300)
    r=paper.bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']*.65;old=phase(page);scroll=page.evaluate('scrollY')
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for step in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y-step*17}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});idle(page)
    require(phase(page)==old,'native touch page scroll threw a sheet')
    require(page.evaluate('scrollY')>scroll,'card body trapped native vertical scrolling')
    ctx.close()


def products(browser, base, net):
    """Три продукта — якорь главной: видны и ведут каждый на свою страницу."""
    ctx, page = opened(browser, base, net, viewport={'width': 1440, 'height': 1100})
    hrefs = page.locator('.product-suite-card').evaluate_all("es=>es.map(e=>e.getAttribute('href'))")
    require(hrefs == ['/ai-service', '/ai-security', '/ai-coding'], 'approved product links changed: '+str(hrefs))
    ctx.close()
    ctx, page = opened(browser, base, net, java_script_enabled=False)
    require(page.locator('.product-suite-card').count() == 3 and page.locator('h1').count() == 1, 'no-JS products lost')
    ctx.close()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--base-url', default='http://127.0.0.1:18765')
    base = parser.parse_args().base_url.rstrip('/')+'/'
    if urlsplit(base).hostname not in ('127.0.0.1','localhost','::1'): return 2
    gateway = base + 'ai-service'
    net = {'errors': [], 'forbidden': []}; failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, check, url in [
            ('persistent-3d-stack', persistent, gateway),
            ('manual-keyboard-nojs', manual, gateway),
            ('responsive-clean-layout', layout, gateway),
            ('three-product-links', products, base),
            ('restored-card-lift', lift, gateway),
            ('grab-throw-cancel', tactile, gateway),
            ('nearest-edge-working-cta', directional, gateway),
            ('touch-grip-native-scroll', touch_drag, gateway),
        ]:
            try: check(browser, url, net); print('PASS', name)
            except Exception as exc: failed.append(name); print('FAIL', name, str(exc))
        browser.close()
    if net['errors'] or net['forbidden']: failed.append('hygiene'); print('FAIL hygiene', net)
    else: print('PASS local-only-console-hygiene')
    print(str(8-len(failed))+'/8 groups passed')
    return int(bool(failed))

if __name__ == '__main__':
    raise SystemExit(main())
