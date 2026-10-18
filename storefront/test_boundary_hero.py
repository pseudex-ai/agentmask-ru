#!/usr/bin/env python3
"""Local read-only acceptance for the current typographic Pseudonym hero.

Runner name retained from the previous boundary experiment. That experiment is
no longer the homepage contract. Only loopback GETs; fixed fixtures, no engine,
providers or tool execution. Run with --base-url http://127.0.0.1:18765.
"""
import argparse
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = '[data-poster-demo]'
FRAME_COUNTER = """(()=>{const native=requestAnimationFrame;window.__posterFrames=0;
window.requestAnimationFrame=function(fn){if(fn.name==='paintPseudonym')window.__posterFrames++;return native.call(window,fn);};})()"""


def require(value, message):
    assert value, message


def opened(browser, base, net, **options):
    options.setdefault('viewport', {'width':1440,'height':1100})
    ctx=browser.new_context(**options)
    origin=urlsplit(base)
    def route(handler):
        req=handler.request;url=urlsplit(req.url)
        if (url.scheme,url.netloc)!=(origin.scheme,origin.netloc) or req.method!='GET':
            net['outside'].append((req.method,req.url));handler.abort()
        else:handler.continue_()
    ctx.route('**/*',route);ctx.add_init_script(FRAME_COUNTER)
    page=ctx.new_page()
    page.on('pageerror',lambda error:net['errors'].append(str(error)))
    page.on('console',lambda msg:net['errors'].append(msg.text) if 'Content Security Policy' in msg.text else None)
    response=page.goto(base,wait_until='networkidle')
    require(response and response.status==200,'landing failed to load')
    return ctx,page


def state(page, expected):
    page.wait_for_function('(expected)=>document.querySelector("[data-poster-demo]").dataset.state===expected',arg=expected,timeout=8000)


def values(page):
    return page.locator('.pp-value').all_text_contents()


def boxes(page):
    return page.locator('.pp-row,.pp-private,.pp-window').evaluate_all("es=>es.map(e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]})")


def scenarios_and_return(browser,base,net):
    ctx,page=opened(browser,base,net,reduced_motion='reduce')
    fixtures=[
        ('platform',['морозову сергею','+7 916 238-47-50'],['крылову андрею','+7 930 482-71-56'],'чтение CRM','+79162384750'),
        ('service',['катя морозова','ул садовая д24 кв8','8-916-238-47-50'],['марина тихонова','ул кедровая д57 кв3','8-930-482-71-56'],'create_order','+79162384750'),
        ('coding',['"ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5"'],['"ghp_H0t2R5w7Y1c4A9e6I8u3J2k5M7n0O4q9S1x8"'],'вашем контуре','process.env.GITHUB_TOKEN'),
    ]
    for name,original,substitute,tool,local_argument in fixtures:
        page.locator(f'[data-pp-track="{name}"]').click();state(page,'model')
        require(values(page)==substitute,'wrong model view: '+str(values(page)))
        require(page.locator('[data-pp-track][aria-pressed="true"]').count()==1,'multiple selected products')
        require(page.locator('.pp-value').count()==len(original),'stale material left behind')
        require(not page.locator('[data-pp-receipt]').is_visible(),'tool result shown before explicit return')
        before=boxes(page)
        page.locator('[data-pp-action]').click();state(page,'tool')
        require(values(page)==original,'tool view did not restore originals')
        require(page.locator('[data-pp-receipt]').is_visible(),'return example missing')
        require(tool in page.locator('[data-pp-tool-name]').inner_text(),'wrong illustrative tool')
        result=page.locator('[data-pp-tool-code]').inner_text()
        require(local_argument in result,'local execution/argument example missing')
        if name=='coding':
            require(original[0].strip('"') not in result and substitute[0].strip('"') not in result,'credential interpolated into tool code')
        if name=='service':
            require(original[1] in result and 'create_order' in result and 'quantity: 2' in result and '1 кг' in result,'new order content/address lost in return')
            require('4471' not in result and 'order:' not in result,'new request still depends on an existing order')
        after=boxes(page)
        require(len(before)==len(after) and all(abs(a-b)<.2 for ra,rb in zip(before,after) for a,b in zip(ra,rb)), 'word length changed the poster layout')
        page.locator('[data-pp-action]').click();state(page,'model')
        require(values(page)==substitute,'repeat did not return to model view')
    require('BETA' in page.locator('[data-pp-track="platform"]').inner_text(),'corporate beta label lost')
    require('BETA' in page.locator('[data-pp-track="coding"]').inner_text(),'coding beta label lost')
    require('вымышленные' in page.locator('.pp-footer').inner_text().lower(),'synthetic demo disclosure absent')
    require(page.locator('.lb-stage,.lp-demo,.lp-marquee').count()==0,'rejected diagram/widget decoration returned')
    code=page.locator('[data-pp-material]').inner_text()
    require('new Octokit({' in code and 'auth:' in code and 'github.rest.issues.get(issue)' in code,'credential is not shown inside useful code')
    require('tenant' not in code,'old variable-masking demonstration returned')
    ctx.close()


def drag_keyboard_and_cancel(browser,base,net):
    ctx,page=opened(browser,base,net)
    state(page,'model')
    word=page.locator('.pp-private').first
    box=word.bounding_box();x=box['x']+box['width']*.7;y=box['y']+box['height']*.5
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-220,y,steps=12);page.mouse.up()
    state(page,'tool')
    require(values(page)[0]=='морозову сергею','drag did not restore the original')
    require(not page.locator(ROOT).evaluate("e=>e.classList.contains('is-dragging')"),'capture stuck')
    word.focus();page.keyboard.press('End');state(page,'model')
    page.keyboard.press('Home');state(page,'tool')
    page.keyboard.press('Enter');state(page,'model')
    # Escape must undo a partially moved strip and must not leave half-hidden text.
    box=word.bounding_box();x=box['x']+box['width']*.5;y=box['y']+box['height']*.5
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-45,y,steps=5)
    page.keyboard.press('Escape');page.mouse.up();state(page,'model')
    require(values(page)[0]=='крылову андрею','cancel changed identity unexpectedly')
    require(urlsplit(page.url).path=='/','drag activated another link')
    ctx.close()


def finite_motion_and_cover(browser,base,net):
    ctx,page=opened(browser,base,net)
    state(page,'model')
    count=page.evaluate('window.__posterFrames');page.wait_for_timeout(300)
    require(page.evaluate('window.__posterFrames')==count,'intro runs perpetually')
    require(page.locator(ROOT).get_attribute('data-scene')=='platform','automatic scenario carousel')
    page.locator('[data-pp-track="service"]').click()
    # A private word has exactly one visible value node. The two measurements
    # are hidden, never composited originals/fakes at half opacity.
    require(page.locator('.pp-private .pp-value').count()==3,'duplicate or missing service value layers')
    require(page.locator('.pp-measure').evaluate_all("es=>es.every(e=>getComputedStyle(e).visibility==='hidden')"),'measurement text visible')
    state(page,'model')
    page.locator('[data-pp-action]').click()
    page.wait_for_timeout(320)
    require(page.locator(ROOT).get_attribute('data-state')=='restoring','reverse episode did not animate')
    state(page,'tool')
    require(page.evaluate('window.__posterFrames')>count,'finite animation did not render')
    page.locator('[data-pp-track="coding"]').click()
    page.evaluate('scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(350)
    count=page.evaluate('window.__posterFrames');page.wait_for_timeout(350)
    require(page.evaluate('window.__posterFrames')==count,'offscreen episode kept rendering')
    page.emulate_media(reduced_motion='reduce');page.evaluate('scrollTo(0,0)')
    state(page,'model')
    count=page.evaluate('window.__posterFrames');page.wait_for_timeout(250)
    require(page.evaluate('window.__posterFrames')==count,'dynamic reduced-motion did not stop animation')
    # Very rapid changes must leave only the final material and one active scene.
    for name in ['coding','platform','service','coding','service']:
        page.locator(f'[data-pp-track="{name}"]').click()
    require(values(page)==['марина тихонова','ул кедровая д57 кв3','8-930-482-71-56'],'stale animation changed the final scene')
    require(page.locator('[data-pp-material]').count()==1,'scenario ghosts accumulated')
    ctx.close()


def responsive_and_nojs(browser,base,net):
    for width in (320,390,768,1024,1440,2729):
        ctx,page=opened(browser,base,net,viewport={'width':width,'height':1100},reduced_motion='reduce')
        for name in ('platform','coding','service'):
            page.locator(f'[data-pp-track="{name}"]').click();state(page,'model')
            require(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),str(width)+' horizontal overflow: '+name)
            # Every word fits the poster; don't hide overflow to pretend it fits.
            fits=page.locator('.pp-private').evaluate_all("es=>es.every(e=>{const r=e.getBoundingClientRect();return r.x>=-1&&r.right<=innerWidth+1})")
            require(fits,str(width)+' private text runs off screen: '+name)
        require(page.locator('h1').is_visible(),str(width)+' no visible title')
        require(page.locator('.product-suite-card').count()==3,'product chooser removed')
        require(page.evaluate('window.__posterFrames')==0,'reduced-motion scheduled a frame')
        page.locator('.pp-footer>a').click()
        require(urlsplit(page.url).fragment=='products','native products anchor failed')
        ctx.close()
    ctx,page=opened(browser,base,net,java_script_enabled=False)
    require('морозову сергею' in page.locator('.pp-value').first.inner_text(),'no-JS specimen empty')
    require(page.locator('.pp-private').first.is_disabled(),'no-JS word looks actionable')
    require(page.locator('[data-pp-track="coding"]').is_disabled(),'no-JS selector looks actionable')
    require(not page.locator('.pp-direction').is_visible(),'no-JS dead controls visible')
    ctx.close()


def touch_native_scroll(browser,base,net):
    ctx,page=opened(browser,base,net,viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='reduce')
    page.locator('[data-pp-track="service"]').click();state(page,'model')
    word=page.locator('.pp-private').first;word.scroll_into_view_if_needed()
    box=word.bounding_box();x=box['x']+box['width']*.8;y=box['y']+box['height']*.5
    cdp=ctx.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for n in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x-n*14,'y':y}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    state(page,'tool')
    require(values(page)[0]=='катя морозова','touch drag did not restore original')
    before=page.evaluate('scrollY');x,y=80,430
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for n in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y-n*15}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    page.wait_for_timeout(250)
    require(page.evaluate('scrollY')>before,'poster swallowed native page scroll')
    ctx.close()


def brand_themes_and_preserved_format(browser,base,net):
    ctx,page=opened(browser,base,net,reduced_motion='reduce')
    expected={
        'dark':('rgb(23, 23, 26)','rgb(232, 231, 236)','rgb(179, 160, 234)'),
        'light':('rgb(247, 247, 249)','rgb(22, 22, 26)','rgb(111, 100, 134)'),
    }
    def shape(text):
        return ''.join('D' if c.isdigit() else 'U' if c.isupper() else 'L' if c.islower() else c for c in text)
    for theme,palette in expected.items():
        current=page.locator('html').get_attribute('data-theme') or 'dark'
        if current!=theme:page.locator('[data-theme-toggle]').click()
        actual=page.locator('.pp-hero').evaluate('e=>[getComputedStyle(e).backgroundColor,getComputedStyle(e).color,getComputedStyle(e.querySelector(".pp-tape")).backgroundColor]')
        require(tuple(actual)==palette,'hero/tape diverge from brand '+theme+': '+str(actual))
        require(page.locator('.pp-hero').get_attribute('data-theme') is None,'poster still forces a separate theme')
        page.locator('[data-pp-track="coding"]').click()
        data=page.locator('[data-pp-key="api-key"]').evaluate('e=>({raw:e.dataset.ppOriginal,fake:e.dataset.ppSubstitute,value:e.querySelector(".pp-value").textContent,prefix:e.querySelector(".pp-value .pp-affix").textContent})')
        require(len(data['raw'])==len(data['fake'])==40,'credential truncated or length changed')
        require(data['raw'].startswith('ghp_') and data['fake'].startswith('ghp_') and data['prefix']=='ghp_','vendor prefix not preserved')
        require(shape(data['raw'])==shape(data['fake']),'positional digit/case classes changed')
        require(data['value'].strip('"')==data['fake'] and '…' not in data['value'],'full credential body is not displayed')
        require(page.locator('.pp-format,.pp-note').count()==0,'redundant explanatory paragraphs returned')
        require(not page.locator('[data-pp-next-format]').is_visible(),'unsupported credential variation shown')
        for scene in ('platform','service'):
            page.locator(f'[data-pp-track="{scene}"]').click()
            phone=page.locator('[data-pp-key="phone"]').evaluate('e=>[e.dataset.ppOriginal,e.dataset.ppSubstitute]')
            require(shape(phone[0])==shape(phone[1]),'phone grouping/punctuation changed: '+scene)
            require(len([c for c in phone[0] if c.isdigit()])==11,'illustrative phone lost digits')
            require(all('(' not in value and ')' not in value for value in phone),'phone parentheses returned')
            text=page.locator('[data-pp-material]').inner_text()
            if scene=='platform':
                require('CRM' in text and 'просрочку' in text and 'черновик' in text and 'не отправляй' in text,'corporate example is not an actual employee prompt')
                require('для сверки' not in text,'redundant phone label returned')
            else:
                require(all(x in text for x in ('2 пачки кофе','1 кг','завтра','доставка','наберите')),'new customer order scenario incomplete')
                require('4471' not in text,'customer is assumed to already have an order')
                address=page.locator('[data-pp-key="address"]').evaluate('e=>[e.dataset.ppOriginal,e.dataset.ppSubstitute]')
                require(all(token in value for value in address for token in ('ул','д','кв')),'address structure replaced with a placeholder')
    ctx.close()


def register_variants_and_highlighted_invariants(browser,base,net):
    # These are authored examples in observed registers, not benchmark scores.
    for width in (390,1440):
        ctx,page=opened(browser,base,net,viewport={'width':width,'height':1100},reduced_motion='reduce')
        for theme in ('dark','light'):
            current=page.locator('html').get_attribute('data-theme') or 'dark'
            if current!=theme:page.locator('[data-theme-toggle]').click()
            expected_accent='rgb(179, 160, 234)' if theme=='dark' else 'rgb(111, 100, 134)'
            for scene in ('platform','service'):
                page.locator(f'[data-pp-track="{scene}"]').click()
                for variant in (0,1):
                    if variant:page.locator('[data-pp-next-format]').click()
                    require(page.locator(ROOT).get_attribute('data-format')==str(variant),'manual format selection failed')
                    state(page,'model')
                    model_marks=page.locator('.pp-value .pp-affix').all_text_contents()
                    require(model_marks,'non-coding values have no visual format proof')
                    colors=page.locator('.pp-value .pp-affix').evaluate_all('es=>es.map(e=>getComputedStyle(e).color)')
                    require(all(c==expected_accent for c in colors),'preserved tokens are not brand purple')
                    parts=page.locator('.pp-private').evaluate_all('es=>es.map(e=>({raw:e.dataset.ppOriginal,fake:e.dataset.ppSubstitute,visible:e.querySelector(".pp-value").textContent}))')
                    require(all(p['fake']==p['visible'] for p in parts),'formatted markup modified a value')
                    before=boxes(page)
                    page.locator('[data-pp-action]').click();state(page,'tool')
                    raw_marks=page.locator('.pp-value .pp-affix').all_text_contents()
                    require(raw_marks==model_marks,'purple tokens claim to preserve changing personal content')
                    after=boxes(page)
                    require(len(before)==len(after) and all(abs(a-b)<.2 for ra,rb in zip(before,after) for a,b in zip(ra,rb)),str(width)+' highlighting/format introduced layout drift')
                    raw=page.locator('.pp-private').evaluate_all('es=>es.map(e=>e.querySelector(".pp-value").textContent)')
                    require(raw==[p['raw'] for p in parts],'selected register was normalized on return')
                    if variant:
                        name_marks=page.locator('[data-pp-key="name"] .pp-value .pp-affix').all_text_contents()
                        require(any('.' in mark for mark in name_marks),'initial dots not highlighted')
                        require(not any(any(c.isupper() for c in mark) for mark in name_marks),'changing initial letters colored as invariant')
                    else:
                        require(parts[0]['raw']==parts[0]['raw'].lower(),'chat name tidied into title case')
                        if scene=='service':
                            require('д24' in parts[1]['raw'] and 'кв8' in parts[1]['raw'],'compact chat address replaced by formal prose')
                    require(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'variant horizontal overflow')
                # Product changes explicitly reset the example, not a ghost state.
                page.locator('[data-pp-track="coding"]').click()
                require(page.locator(ROOT).get_attribute('data-format')=='0','register did not reset on product selection')
                require(not page.locator('[data-pp-next-format]').is_visible(),'extra format action left on coding')
        require(page.evaluate('window.__posterFrames')==0,'register controls forced animation under reduced-motion')
        ctx.close()


def whole_hero_drag_and_controls(browser,base,net):
    ctx,page=opened(browser,base,net)
    state(page,'model')
    title=page.locator('.pp-heading h1').bounding_box()
    x=title['x']+title['width']*.75;y=title['y']+title['height']*.5
    count=page.evaluate('window.__posterFrames')
    page.mouse.click(x,y);page.wait_for_timeout(120)
    require(page.locator(ROOT).get_attribute('data-state')=='model','plain heading click toggled demo')
    require(page.evaluate('window.__posterFrames')==count,'plain click restarted motion')
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-120,y)
    require(page.locator(ROOT).get_attribute('data-state')=='dragging','heading is not a gesture surface')
    tape=page.locator(ROOT).evaluate('e=>parseFloat(e.style.getPropertyValue("--pp-tape"))')
    distance=page.locator('.pp-hero').evaluate('e=>Math.max(140,Math.min(360,e.clientWidth*.28))')
    target=(1-120/distance)*208-104
    require(tape>target+.5 and tape<=104,'drag jumps directly instead of smoothly following the pointer')
    page.wait_for_timeout(700)
    count=page.evaluate('window.__posterFrames');page.wait_for_timeout(130)
    require(page.evaluate('window.__posterFrames')==count,'stationary held drag renders forever')
    page.mouse.move(x-240,y);page.mouse.up();state(page,'tool')
    require(values(page)[0]=='морозову сергею','heading drag did not restore values')
    require(not page.locator('.pp-hero').evaluate('e=>e.hasPointerCapture(1)||e.classList.contains("is-dragging")'),'hero capture stuck')
    # Tool arguments remain selectable; their text must not start a hero drag.
    code=page.locator('[data-pp-tool-code]');code.scroll_into_view_if_needed();r=code.bounding_box()
    page.mouse.move(r['x']+5,r['y']+8);page.mouse.down();page.mouse.move(r['x']+150,r['y']+8,steps=8);page.mouse.up()
    require(page.locator(ROOT).get_attribute('data-state')=='tool','copying tool code triggered masking')
    require(page.evaluate('getSelection().toString().length')>0,'tool code no longer copyable')
    page.evaluate('getSelection().removeAllRanges()')
    # Restore from padding, then drag ordinary non-private sentence text.
    page.evaluate('scrollTo(0,0)')
    material=page.locator('[data-pp-material]').bounding_box()
    x=material['x']+15;y=material['y']+8
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+240,y,steps=12);page.mouse.up();state(page,'model')
    sentence=page.locator('.pp-request-continuation>span').bounding_box()
    x=sentence['x']+sentence['width']*.6;y=sentence['y']+sentence['height']*.5
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-160,y,steps=8)
    page.keyboard.press('Escape');page.mouse.up();state(page,'model')
    require(values(page)[0]=='крылову андрею','background Escape did not undo partial gesture')
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-240,y,steps=12);page.mouse.up();state(page,'tool')
    # Native controls work immediately after a broad drag, including keyboard.
    page.locator('[data-pp-action]').focus();page.keyboard.press('Enter');state(page,'model')
    page.locator('[data-pp-next-format]').click();state(page,'model')
    require(page.locator(ROOT).get_attribute('data-format')=='1','format button swallowed by hero')
    page.locator('[data-pp-track="coding"]').click();state(page,'model')
    require(page.locator(ROOT).get_attribute('data-scene')=='coding','product button swallowed by hero')
    page.locator('.pp-intro a').click()
    require(urlsplit(page.url).fragment=='products','native hero link swallowed by drag handler')
    ctx.close()


def whole_hero_touch_surface(browser,base,net):
    ctx,page=opened(browser,base,net,viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='reduce')
    state(page,'model')
    r=page.locator('.pp-heading h1').bounding_box();x=r['x']+r['width']*.8;y=r['y']+r['height']*.5
    cdp=ctx.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for n in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x-n*15,'y':y}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    state(page,'tool')
    require(values(page)[0]=='морозову сергею','touch gesture on heading failed')
    require(page.evaluate('window.__posterFrames')==0,'reduced-motion gesture scheduled animation')
    before=page.evaluate('scrollY')
    cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for n in range(1,9):cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y-n*15}]})
    cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    page.wait_for_timeout(200)
    require(page.evaluate('scrollY')>before,'vertical scroll from heading hijacked by hero')
    require(page.locator(ROOT).get_attribute('data-state')=='tool','vertical gesture changed identity')
    require('pinch-zoom' in page.locator('.pp-hero').evaluate('e=>getComputedStyle(e).touchAction'),'hero forbids native pinch zoom')
    require(not page.locator('.pp-hero').evaluate('e=>e.classList.contains("is-dragging")'),'touch capture remained stuck')
    ctx.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:18765')
    base=parser.parse_args().base_url.rstrip('/')+'/'
    if urlsplit(base).hostname not in ('localhost','127.0.0.1','::1'):return 2
    net={'outside':[],'errors':[]};failed=[]
    checks=[scenarios_and_return,drag_keyboard_and_cancel,finite_motion_and_cover,responsive_and_nojs,touch_native_scroll,brand_themes_and_preserved_format,register_variants_and_highlighted_invariants,whole_hero_drag_and_controls,whole_hero_touch_surface]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for check in checks:
            try:check(browser,base,net);print('PASS',check.__name__,flush=True)
            except Exception as error:failed.append(check.__name__);print('FAIL',check.__name__,str(error),flush=True)
        browser.close()
    if net['outside'] or net['errors']:failed.append('hygiene');print('FAIL hygiene',net)
    else:print('PASS local-only-console-hygiene')
    print(f'{len(checks)+1-len(failed)}/{len(checks)+1} groups passed')
    return int(bool(failed))


if __name__=='__main__':
    raise SystemExit(main())
