"""Browser acceptance for the local product preview; synthetic local leads only.

Run a migrated local storefront, then python test_product_pages_browser.py.
The URL is deliberately restricted to loopback. This is not a production test.

The coding session is an ILLUSTRATIVE fixture: every name, address, path and key
below is invented, and no command, file, API, MCP or model is ever executed. The
values are restated here on purpose, as the expected result of the mapping the
fixture applies — so a change to either side of the boundary goes red instead of
quietly keeping its old meaning.
"""
import argparse
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# The synthetic originals the tool returns and the substitutes the model must
# see instead; the first three are also what makes the first tool result real.
SESSION_MAPPINGS = (
    ('anna@customer.example', 'user-17@example.invalid'),
    ('billing.atlas.internal', 'service-01.internal.invalid'),
    ('/Users/marina/work/atlas', '/workspace/project-01'),
    ('sk_test_DEMO_NOT_A_KEY', '[SECRET REMOVED]'),
    ('whsec_DEMO_NOT_A_SECRET', '[SECRET REMOVED]'),
    ('postgresql://demo:demo@db.atlas.internal/billing', '[CONNECTION SECRET REMOVED]'),
)


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

        def model_text():
            return page.locator('[data-session-model]').text_content() or ''

        def local_text():
            return page.locator('[data-session-local]').text_content() or ''

        def pressed(selector):
            return page.locator(selector).get_attribute('aria-pressed')

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
            page.wait_for_function('selector => { const img=document.querySelector(selector); return img.complete && img.naturalWidth===3200; }', arg=f'[data-real-panel="{name}"] img')
            check(urlparse(panel.locator('img').get_attribute('src')).path.endswith(name+'.webp'), 'actual local screenshot loaded: '+name)
            check(panel.locator('a[target="_blank"]').count() == 1, 'full-size real screen available: '+name)
        page.locator('[data-real-tab="policy"]').focus()
        page.keyboard.press('ArrowRight')
        check(page.locator('[data-real-tab="agents"]').get_attribute('aria-selected') == 'true', 'real screen tabs support keyboard navigation')
        page.locator('[data-real-tab="policy"]').click()
        page.screenshot(path=str(out/'ai-security-desktop.png'),full_page=True)

        # --- coding session: seven steps, two modes, one synthetic boundary ---
        page.goto(base+'/ai-coding',wait_until='networkidle')
        session = page.locator('[data-coding-session]')
        check(session.count() == 1, 'coding session fixture is present')
        check(page.locator('[data-hop], [data-code-left], [data-coding-mode], [data-edge-case]').count() == 0,
              'superseded coding hooks are gone from the page')
        check(page.locator('[data-session-step]').count() == 7, 'coding session offers exactly seven steps')
        check(pressed('[data-session-step="0"]') == 'true'
              and page.locator('[data-session-step][aria-pressed="true"]').count() == 1,
              'coding session starts on step 1 of 7')
        check(pressed('[data-session-mode="protected"]') == 'true' and pressed('[data-session-mode="raw"]') == 'false',
              'coding session starts in the protected mode')
        check(page.locator('[data-session-counter]').inner_text().strip() == '01 / 07', 'counter names step 1 of 7')
        check(page.locator('[data-session-local]').count() == 1 and page.locator('[data-session-model]').count() == 1,
              'local and model panes are separate elements')
        # The first tool result carries the three boundary values at once; if an
        # edit drops one, the sweep below would pass vacuously.
        page.locator('[data-session-step="0"]').click()
        first_local = local_text()
        for raw, fake in SESSION_MAPPINGS[:3]:
            check(raw in first_local and fake in model_text(),
                  f'first tool result carries {raw!r}; the model sees {fake!r}')
        # Sweep every step in the default protected mode. Reduced motion is on
        # for this context, so none of this depends on the animation running.
        for step in range(7):
            page.locator(f'[data-session-step="{step}"]').click()
            check(pressed(f'[data-session-step="{step}"]') == 'true'
                  and page.locator('[data-session-step][aria-pressed="true"]').count() == 1,
                  f'coding step {step+1} selects exactly itself')
            check(page.locator('[data-session-counter]').inner_text().strip() == f'{step+1:02d} / 07',
                  f'coding step {step+1} counter follows')
            local, model = local_text(), model_text()
            leaked = [raw for raw, _ in SESSION_MAPPINGS if raw in model]
            check(not leaked, f'coding step {step+1}: synthetic originals stay out of the model pane {leaked}')
            unswapped = [f'{raw!r}->{fake!r}' for raw, fake in SESSION_MAPPINGS if raw in local and fake not in model]
            check(not unswapped, f'coding step {step+1}: every returned value is replaced for the model {unswapped}')
        # Step 2 of 7: the returned code must survive as code.
        page.locator('[data-session-step="1"]').click()
        local, model = local_text(), model_text()
        check('/Users/marina/work/atlas' in local and '/workspace/project-01' in model and '/Users/marina' not in model,
              'grep step: the true workspace is local, the pseudonym is what the model gets')
        check('const rawBody = await request.text();' in model
              and 'process.env.STRIPE_WEBHOOK_SECRET' in model
              and 'stripe.webhooks.constructEvent(' in model,
              'grep step: code, line references and the environment-variable name stay readable')
        # Step 3 of 7: secrets leave the transcript, names of variables stay.
        page.locator('[data-session-step="2"]').click()
        local, model = local_text(), model_text()
        check(all(raw in local for raw, _ in SESSION_MAPPINGS[3:]),
              'config step carries the three synthetic secrets in the local file')
        check('sk_test_DEMO_NOT_A_KEY' not in model and 'whsec_DEMO_NOT_A_SECRET' not in model,
              'config step: key and signing secret never reach the model pane')
        check(model.count('[SECRET REMOVED]') >= 2 and '[CONNECTION SECRET REMOVED]' in model,
              'config step: key, signing secret and connection string are removed')
        check('demo:demo@' not in model, 'config step: the database password does not survive')
        check('STRIPE_SECRET_KEY' in model and 'STRIPE_WEBHOOK_SECRET' in model and 'DATABASE_URL' in model,
              'config step: variable names remain so the model still understands the config')
        # Step 4 of 7: output of a command is a fresh boundary.
        page.locator('[data-session-step="3"]').click()
        model = model_text()
        check('user-17@example.invalid' in model and 'service-01.internal.invalid' in model,
              'API step: the tool result is protected again before the model')
        check('evt_demo_104' in model and '"credits"' in model and '4900' in model,
              'API step: event id, duplicate credits and amounts stay useful')
        # Step 5 of 7: the allowed patch needs the real path locally only.
        page.locator('[data-session-step="4"]').click()
        local, model = local_text(), model_text()
        check('/Users/marina/work/atlas/src/billing.ts' in local
              and '/workspace/project-01/src/billing.ts' in model,
              'patch step: the allowed patch keeps its true local path, the model sees the pseudonym')
        check('/Users/marina' not in model, 'patch step: the owner name inside the path does not reach the model')
        check('настоящий путь' in page.locator('[data-session-local-label]').inner_text(),
              'patch step: the local pane is labelled as the real path')
        # Step 6 of 7: a passing test still prints the fixture.
        page.locator('[data-session-step="5"]').click()
        local, model = local_text(), model_text()
        check('fixture: anna@customer.example' in local and 'fixture: user-17@example.invalid' in model,
              'test step: the fixture email is replaced for the model')
        check('artifact: /workspace/project-01/test-results/billing.png' in model and '/Users/marina' not in model,
              'test step: the artifact path is replaced too')
        check('sequential retry → one credit' in model, 'test step: test names and assertions survive')
        # Step 7 of 7: the replayed history must not undo the earlier steps.
        page.locator('[data-session-step="6"]').click()
        local, model = local_text(), model_text()
        check('Исходный код + .env.local' in local and 'sk_test_DEMO_NOT_A_KEY' in local,
              'history step: the local project still holds the secret')
        check('История для следующего хода' in model and 'config → [SECRET REMOVED]' in model,
              'history step: the history handed to the model is protected')
        check('user-17@example.invalid' in model and '/workspace/project-01/src/billing.ts' in model,
              'history step: email, host and path stay pseudonymous in the history')
        check('/Users/marina' not in model and 'anna@customer.example' not in model
              and 'sk_test_DEMO_NOT_A_KEY' not in model,
              'history step: no original returns with the history')
        # Next walks and wraps; the label says which of the two it will do.
        page.locator('[data-session-step="6"]').click()
        check(page.locator('[data-session-next]').text_content().strip() == 'Повторить сессию ↺',
              'next button announces the wrap on the last step')
        page.locator('[data-session-next]').click()
        check(pressed('[data-session-step="0"]') == 'true'
              and page.locator('[data-session-counter]').inner_text().strip() == '01 / 07',
              'next after the last step restarts the session')
        page.locator('[data-session-next]').click()
        check(pressed('[data-session-step="1"]') == 'true', 'next advances exactly one step')
        # The edge case: a secret is not something to restore into any command.
        page.locator('[data-session-step="2"]').click()
        page.locator('[data-session-edge]').click()
        edge = page.locator('[data-session-edge-result]').text_content() or ''
        check('не восстанавливается' in edge and 'Bash' in edge and 'остановлена' in edge,
              'edge case: the secret is not restored into an arbitrary Bash command and the operation stops')
        # Raw mode exists to show the contrast and to warn, not to be the default.
        page.locator('[data-session-mode="raw"]').click()
        check(pressed('[data-session-mode="raw"]') == 'true' and pressed('[data-session-mode="protected"]') == 'false',
              'raw mode selects itself')
        check('sk_test_DEMO_NOT_A_KEY' in model_text(),
              'raw mode exposes the synthetic original, which is what the warning is about')
        check('Без защиты' in (page.locator('[data-session-title]').text_content() or ''),
              'raw mode warns in the verdict title')
        check('пароль БД' in (page.locator('[data-session-description]').text_content() or ''),
              'raw mode explains the consequence instead of the protection copy')
        check(page.locator('[data-session-model-label]').inner_text().strip() == 'Контекст модели · без проверки',
              'raw mode relabels the model pane')
        check('p-session-raw' in (session.get_attribute('class') or ''),
              'raw mode is marked on the fixture root for styling')
        page.locator('[data-session-mode="protected"]').click()
        check('p-session-raw' not in (session.get_attribute('class') or '')
              and 'sk_test_DEMO_NOT_A_KEY' not in model_text(),
              'switching back to protected hides the original again')
        # Reset is the only escape hatch and it returns to step 1, protected.
        page.locator('[data-session-step="4"]').click()
        page.locator('[data-session-mode="raw"]').click()
        page.locator('[data-session-reset]').click()
        check(pressed('[data-session-step="0"]') == 'true'
              and page.locator('[data-session-step][aria-pressed="true"]').count() == 1,
              'reset returns to step 1 of 7')
        check(pressed('[data-session-mode="protected"]') == 'true' and pressed('[data-session-mode="raw"]') == 'false',
              'reset returns to the protected mode')
        check(page.locator('[data-session-counter]').inner_text().strip() == '01 / 07'
              and '/Users/marina' not in model_text() and 'user-17@example.invalid' in model_text(),
              'reset renders the protected first step again')
        page.locator('[data-session-step="0"]').click()
        check(page.locator('.p-brand-logo').count() == 2, 'official integration marks rendered')
        page.locator('#connectors').screenshot(path=str(out/'coding-connectors-logos.png'))
        page.screenshot(path=str(out/'ai-coding-desktop.png'),full_page=True)

        # The site's own navigation, through real links: home -> enterprise ->
        # coding, and back. navigation.css is the native cross-document
        # transition, so it must be loaded — not merely present on disk.
        page.goto(base + '/', wait_until='networkidle')
        nav_href = page.locator('link[rel="stylesheet"][href*="navigation.css"]').first.get_attribute('href')
        check(nav_href is not None, 'navigation.css is linked from the document head')
        check(bool(page.evaluate("[...document.styleSheets].some(s => (s.href || '').includes('navigation.css'))")),
              'navigation.css is loaded by the browser, not only referenced')
        nav_css = page.request.get(nav_href if nav_href.startswith('http') else base + nav_href).text()
        check('@view-transition' in nav_css and 'navigation: auto' in nav_css,
              'navigation.css declares native same-origin view transitions')
        check('prefers-reduced-motion' in nav_css and 'animation: none' in nav_css,
              'navigation.css turns the transition off under reduced motion')
        with page.expect_navigation(wait_until='networkidle'):
            page.locator('#products a[href="/ai-security"]').first.click()
        check(urlparse(page.url).path == '/ai-security', 'home product card opens the enterprise page')
        with page.expect_navigation(wait_until='networkidle'):
            page.locator('nav a[href="/ai-coding"]').first.click()
        check(urlparse(page.url).path == '/ai-coding', 'enterprise nav link opens the coding page')
        with page.expect_navigation(wait_until='networkidle'):
            page.locator('nav a[href="/#products"]').first.click()
        check(urlparse(page.url).path == '/' and urlparse(page.url).fragment == 'products',
              'coding nav link returns to the product choice on home')
        page.go_back(wait_until='networkidle')
        check(urlparse(page.url).path == '/ai-coding', 'browser back returns to the coding page')

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
