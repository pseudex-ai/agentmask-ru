"""Browser acceptance for the local product preview; synthetic local leads only.

Run a migrated local storefront, then python test_product_pages_browser.py.
The URL is deliberately restricted to loopback. This is not a production test.
"""
import argparse
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:18765')
    parser.add_argument('--out', default='../.preview')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    parsed = urlparse(base)
    if parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.scheme != 'http':
        parser.error('Only a local HTTP preview is allowed; never submit QA leads to prod.')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    passed = 0

    def check(condition, label):
        nonlocal passed
        assert condition, label
        passed += 1
        print('PASS', label)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
        external, errors, csp_errors = [], [], []

        def guard(route):
            if urlparse(route.request.url).netloc != parsed.netloc:
                external.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        context.route('**/*', guard)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: csp_errors.append(m.text) if m.type == 'error' else None)
        for path in ('/', '/ai-security', '/ai-coding'):
            response = page.goto(base + path, wait_until='networkidle')
            check(response.status == 200, path + ' loads')
            check(page.locator('h1').count() == 1, path + ' has exactly one h1')
        page.goto(base + '/', wait_until='networkidle')
        check(page.locator('#products a[href="/ai-security"]').count() >= 1, 'home links corporate product')
        check(page.locator('#products a[href="/ai-coding"]').count() >= 1, 'home links coding product')
        check('Корпоративная платформа AI-безопасности' in page.locator('#products').inner_text(), 'cards name actual products')
        # Reproduce the reported HTML/new + stylesheet/old combination: remove
        # the icon-specific CSS rule. Intrinsic SVG dimensions must still hold.
        removed = page.evaluate('''() => {
            let removed = 0;
            for (const sheet of document.styleSheets) {
                for (let i = sheet.cssRules.length - 1; i >= 0; i--) {
                    if ((sheet.cssRules[i].selectorText || '').includes('suite-product-icon')) {
                        sheet.deleteRule(i); removed++;
                    }
                }
            }
            return removed;
        }''')
        check(removed > 0, 'stale-stylesheet simulation removed the icon size rule')
        check(page.locator('.suite-product-icon').evaluate_all('''icons => icons.length === 2 && icons.every(icon => {
            const box = icon.getBoundingClientRect();
            return box.width === 32 && box.height === 32;
        })'''), 'icons stay 32px even without their CSS rule')
        page.reload(wait_until='networkidle')
        # Hide only the sticky header for a tall element capture; CSS attributes
        # are allowed by the real CSP, injected <style> blocks are not.
        page.locator('header.top').evaluate("node => node.style.visibility = 'hidden'")
        page.locator('#products').screenshot(path=str(out/'products-choice-large.png'))
        page.locator('header.top').evaluate("node => node.style.visibility = ''")
        for width in (320,390,768,1440):
            page.set_viewport_size({'width':width,'height':900})
            for path in ('/', '/ai-security', '/ai-coding'):
                page.goto(base+path,wait_until='networkidle')
                check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{path} no horizontal overflow at {width}')
                if path == '/':
                    check(page.locator('.suite-product-icon').evaluate_all('''icons => icons.length === 2 && icons.every(icon => {
                        const box = icon.getBoundingClientRect();
                        const slot = icon.parentElement.getBoundingClientRect();
                        const heading = icon.closest('a').querySelector('h3').getBoundingClientRect();
                        return box.width === 32 && box.height === 32 && box.top >= slot.top
                            && box.bottom <= slot.bottom && box.bottom <= heading.top;
                    })'''), f'icons fit their slot and do not overlap text at {width}')
                if path != '/':
                    check(page.locator('[data-interest-form]').is_visible(), f'{path} usable form at {width}')
                    if width == 390:
                        page.screenshot(path=str(out/(path[1:]+'-mobile.png')), full_page=True)
        page.set_viewport_size({'width':1440,'height':1000})
        page.goto(base+'/ai-security',wait_until='networkidle')
        check(page.locator('[data-enterprise-demo]').count() == 0, 'simplified mock is removed')
        check(page.locator('.p-model-providers .p-brand-logo').count() == 3, 'Claude ChatGPT and Google marks identify model providers')
        for name in ('policy','agents','access','journal','integration','preview','quality'):
            tab = page.locator(f'[data-real-tab="{name}"]')
            tab.click()
            panel = page.locator(f'[data-real-panel="{name}"]')
            check(panel.is_visible() and tab.get_attribute('aria-selected') == 'true', 'real screen tab '+name)
            panel.locator('img').wait_for()
            page.wait_for_function('selector => { const img=document.querySelector(selector); return img.complete && img.naturalWidth===1600; }', arg=f'[data-real-panel="{name}"] img')
            check(panel.locator('img').get_attribute('src').endswith(name+'.webp'), 'actual local screenshot loaded: '+name)
            check(panel.locator('a[target="_blank"]').count() == 1, 'full-size real screen available: '+name)
        page.locator('[data-real-tab="policy"]').focus()
        page.keyboard.press('ArrowRight')
        check(page.locator('[data-real-tab="agents"]').get_attribute('aria-selected') == 'true', 'real screen tabs support keyboard navigation')
        page.locator('[data-real-tab="policy"]').click()
        page.screenshot(path=str(out/'ai-security-desktop.png'),full_page=True)
        page.goto(base+'/ai-coding',wait_until='networkidle')
        for step in range(4):
            page.locator(f'[data-hop="{step}"]').click()
            check(page.locator(f'[data-hop="{step}"]').get_attribute('aria-pressed') == 'true', f'coding step {step+1}')
        page.locator('[data-hop="2"]').click()
        check('anna@example.test' not in page.locator('[data-code-right]').inner_text(), 'original absent from returned model-view')
        check('1 запись' in page.locator('[data-code-left]').inner_text(), 'round-trip finds real record')
        page.locator('[data-coding-mode="mask-only"]').click()
        check('0 записей' in page.locator('[data-code-left]').inner_text(), 'mask-only loses the same real record')
        page.locator('[data-edge-case]').click()
        check('не выполняется' in page.locator('[data-edge-result]').inner_text(), 'unknown mapping does not guess')
        page.locator('[data-coding-mode="roundtrip"]').click()
        page.locator('[data-hop="0"]').click()
        check(page.locator('.p-brand-logo').count() == 2, 'official integration marks rendered')
        page.locator('#connectors').screenshot(path=str(out/'coding-connectors-logos.png'))
        page.screenshot(path=str(out/'ai-coding-desktop.png'),full_page=True)
        for product,path in (('enterprise','/ai-security'),('coding','/ai-coding')):
            page.goto(base+path,wait_until='networkidle')
            page.locator('[name=role]').select_option('developer')
            page.locator('[name=harness]').select_option('codex')
            page.locator('[name=use_case]').select_option('evaluation')
            page.locator('[name=email]').fill('preview-'+product+'@example.test')
            page.locator('[name=consent]').check()
            with page.expect_navigation(wait_until='networkidle') as navigation:
                page.locator('[data-interest-form] button[type=submit]').click()
            check(navigation.value.status == 200, product+' POST follows successful redirect: '+page.url)
            check('Заявка получена' in page.locator('.p-success').inner_text(), product+' actual form confirms receipt')
            page.reload(wait_until='networkidle')
            check(page.locator('.p-success').count() == 0, product+' receipt consumed; refresh does not count lead')
        for path in ('/ai-security','/ai-coding'):
            page.goto(base+path,wait_until='networkidle')
            page.locator('[data-theme-toggle]').click()
            check(page.evaluate('document.documentElement.dataset.theme') == 'light', 'light theme '+path)
            page.screenshot(path=str(out/(path[1:]+'-light.png')),full_page=True)
            page.locator('[data-theme-toggle]').click()
        check(not external, 'no third-party browser requests: '+str(external))
        check(not errors, 'no JS errors: '+str(errors))
        check(not csp_errors, 'no console/CSP errors: '+str(csp_errors))
        browser.close()
    print(f'{passed} browser checks passed; only local synthetic form submissions.')


if __name__ == '__main__':
    main()
