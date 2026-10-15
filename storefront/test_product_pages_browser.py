"""Browser acceptance for the local product preview; synthetic local leads only.

Run a migrated local storefront, then python test_product_pages_browser.py.
The URL is deliberately restricted to loopback. This is not a production test.

The coding session is an ILLUSTRATIVE fixture: every name, address, path and key
below is invented, and no command, file, API, MCP or model is ever executed. The
values are restated here on purpose, as the expected result of the mapping the
fixture applies — so a change to either side of the boundary goes red instead of
quietly keeping its old meaning.

The substitutes are PLAUSIBLE and FORMAT-PRESERVING — the same vendor prefix, the
same length and the same digit/upper/lower class at every body position — not
removal placeholders. None of them is a working credential, and none may ever be
used as one; `static/coding-session.js` is the authoritative fixture and these
pairs are copied from its `mappings` array verbatim.
"""
import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# The synthetic originals the tool returns and the substitutes the model must see
# instead, in the fixture's own order.
SESSION_MAPPINGS = (
    ('anna@customer.example', 'elena.volkova@contact.example'),
    ('billing.atlas.internal', 'billing.orion.internal'),
    ('/Users/marina/work/atlas', '/Users/elena/work/orion'),
    ('sk_test_51Pn8m4Q7v2K9r6T3x5B0c8D1e4F7g2H', 'sk_test_84Wu1t7X0c5R2y9A6e8I3j1K4l7M0n5O'),
    ('ghp_A7m9K2p4R8v1T6x3B5n0C9d2F4g7H1j6L8q5', 'ghp_H0t2R5w7Y1c4A9e6I8u3J2k5M7n0O4q9S1x8'),
    ('postgresql://billing:Q7m4Rv9K@db.atlas.internal/billing',
     'postgresql://finance:N4t8Lp2R@db.orion.internal/finance'),
    ('atlas-payments', 'orion-payments'),
)
EMAIL, HOST, PATH, KEY, TOKEN, DSN, TENANT = range(len(SESSION_MAPPINGS))
# Step 1 carries the client, the host and the tenant and no path at all, so a
# path assertion there would only ever pass vacuously.
STEP0_PAIRS = (EMAIL, HOST, TENANT)


def field_value(text, pattern):
    match = re.search(pattern, text, re.M)
    return match.group(1) if match else ''


def credential_body(value, prefix):
    """The body after a vendor prefix, or '' when the prefix is not there."""
    return value[len(prefix):] if value.startswith(prefix) else ''


def body_classes(body):
    return ''.join('d' if ch.isdigit() else 'u' if ch.isupper()
                   else 'l' if ch.islower() else ch for ch in body)


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
            check(panel.locator('.p-real-screen').evaluate('(e) => e.scrollTop') == 0,
                  'screen opens at the top, including text preview: '+name)
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
        check(page.locator('[data-session-stage] [data-session-panes]').count() == 1
              and page.locator('[data-session-stage] .p-session-verdict').count() == 1,
              'the stage wraps both panes and the verdict, which is the subtree the crossfade clones')
        # The first tool result carries the three boundary values at once; if an
        # edit drops one, the sweep below would pass vacuously. It carries no
        # path, so a path assertion here would be exactly that kind of vacuum.
        page.locator('[data-session-step="0"]').click()
        first_local = local_text()
        step0_model = model_text()
        for index in STEP0_PAIRS:
            raw, fake = SESSION_MAPPINGS[index]
            check(raw in first_local and fake in step0_model,
                  f'first tool result carries {raw!r}; the model sees {fake!r}')
        # Sweep every step in the default protected mode. Reduced motion is on
        # for this context, so none of this depends on the animation running —
        # and a ghost clone surviving under it would be that dependency.
        for step in range(7):
            page.locator(f'[data-session-step="{step}"]').click()
            check(pressed(f'[data-session-step="{step}"]') == 'true'
                  and page.locator('[data-session-step][aria-pressed="true"]').count() == 1,
                  f'coding step {step+1} selects exactly itself')
            check(page.locator('[data-session-counter]').inner_text().strip() == f'{step+1:02d} / 07',
                  f'coding step {step+1} counter follows')
            check(page.locator('.p-session-ghost').count() == 0,
                  f'coding step {step+1} switches with no ghost clone under reduced motion')
            local, model = local_text(), model_text()
            leaked = [raw for raw, _ in SESSION_MAPPINGS if raw in model]
            check(not leaked, f'coding step {step+1}: synthetic originals stay out of the model pane {leaked}')
            unswapped = [f'{raw!r}->{fake!r}' for raw, fake in SESSION_MAPPINGS if raw in local and fake not in model]
            check(not unswapped, f'coding step {step+1}: every returned value is replaced for the model {unswapped}')
        # Step 2 of 7: the returned code must survive as code, and exactly one
        # workspace path inside it is rewritten.
        page.locator('[data-session-step="1"]').click()
        local, model = local_text(), model_text()
        raw_path, fake_path = SESSION_MAPPINGS[PATH]
        check(raw_path in local and fake_path in model and '/Users/marina' not in model,
              'grep step: the true workspace is local, the pseudonym is what the model gets')
        check(model.count('/Users/') == 1
              and fake_path + '/src/app/api/webhooks/stripe/route.ts:27' in model,
              'grep step: exactly one workspace path is rewritten and it keeps its tail')
        check('const rawBody = await request.text();' in model
              and 'process.env.STRIPE_WEBHOOK_SECRET' in model
              and 'stripe.webhooks.constructEvent(' in model,
              'grep step: code, line references and the environment-variable name stay readable')
        check('return <CreditRows items={credits} />;' in model
              and 'src/components/BillingHistory.tsx:48' in model,
              'grep step: JSX and the second file reference are preserved, not summarized')
        raw_tenant, fake_tenant = SESSION_MAPPINGS[TENANT]
        check(f'const tenant = "{raw_tenant}";' in local and f'const tenant = "{fake_tenant}";' in model
              and raw_tenant not in model,
              'grep step: only the tenant string literal is exchanged, inside identical surrounding code')
        # Step 3 of 7: credentials keep their vendor prefix, their length and the
        # character class of every body position — plausible, never a placeholder.
        page.locator('[data-session-step="2"]').click()
        local, model = local_text(), model_text()
        step2_model = model
        raw_key, fake_key = SESSION_MAPPINGS[KEY]
        raw_token, fake_token = SESSION_MAPPINGS[TOKEN]
        raw_dsn, fake_dsn = SESSION_MAPPINGS[DSN]
        check(all(raw in local for raw in (raw_key, raw_token, raw_dsn)),
              'config step carries the three synthetic credentials in the local file')
        check(raw_key not in model and raw_token not in model and raw_dsn not in model,
              'config step: key, token and connection string never reach the model pane')
        check('[SECRET REMOVED]' not in model and '[CONNECTION SECRET REMOVED]' not in model,
              'config step: the substitutes are plausible values, not removal placeholders')
        model_key = field_value(model, r'^STRIPE_SECRET_KEY=(\S+)$')
        model_token = field_value(model, r'^GITHUB_TOKEN=(\S+)$')
        model_dsn = field_value(model, r'^DATABASE_URL=(\S+)$')
        check(model_key == fake_key and model_token == fake_token and model_dsn == fake_dsn,
              'config step: each value is replaced by exactly the fixture substitute')
        check(model_key.startswith('sk_test_') and model_token.startswith('ghp_')
              and len(model_key) == len(raw_key) and len(model_token) == len(raw_token),
              'config step: vendor prefixes and the original lengths are preserved')
        check(body_classes(credential_body(model_key, 'sk_test_'))
              == body_classes(credential_body(raw_key, 'sk_test_'))
              and body_classes(credential_body(model_token, 'ghp_'))
              == body_classes(credential_body(raw_token, 'ghp_')),
              'config step: every body position keeps its digit/upper/lower character class')
        raw_url, fake_url = urlparse(raw_dsn), urlparse(model_dsn)
        check(fake_url.scheme == raw_url.scheme == 'postgresql' and bool(fake_url.hostname)
              and fake_url.username != raw_url.username and fake_url.password != raw_url.password
              and fake_url.hostname != raw_url.hostname and fake_url.path != raw_url.path,
              'config step: the DSN stays a parseable URI with every role replaced')
        check('Q7m4Rv9K' not in model and 'db.atlas.internal' not in model,
              'config step: the database password and the internal host do not survive')
        check('STRIPE_SECRET_KEY' in model and 'GITHUB_TOKEN' in model and 'DATABASE_URL' in model
              and 'APP_ORIGIN=http://127.0.0.1:3000' in model,
              'config step: variable names and the non-secret origin remain so the model still understands the config')
        # Step 4 of 7: the output of a command is a fresh boundary — protected
        # again with the same substitutes, while the signed request is not
        # rewritten in place.
        page.locator('[data-session-step="3"]').click()
        local, model = local_text(), model_text()
        check(model.count('POST /api/webhooks/stripe → 200') == 2
              and '$BILLING_API_TOKEN' in (page.locator('[data-session-command]').text_content() or ''),
              'API step: the signed request line and its environment-variable credential are not rewritten')
        check(SESSION_MAPPINGS[EMAIL][1] in model and SESSION_MAPPINGS[TENANT][1] in model
              and SESSION_MAPPINGS[HOST][1] in model
              and SESSION_MAPPINGS[EMAIL][0] not in model and SESSION_MAPPINGS[TENANT][0] not in model,
              'API step: the returned JSON is protected again with the same substitutes')
        check('"event": "evt_demo_104"' in model and model.count('"amount": 4900') == 2,
              'API step: event id and both duplicate credit amounts stay useful')
        check(field_value(step0_model, r'^customer: (\S+)$')
              == field_value(model, r'^  "email": "([^"]+)"') == SESSION_MAPPINGS[EMAIL][1],
              'API step: the client keeps the same pseudonym from the MCP result to the API response')
        # Step 5 of 7: the patch applies to code whose exact literal differs
        # between the panes, and the file is relative — no workspace path is part
        # of this step at all.
        page.locator('[data-session-step="4"]').click()
        local, model = local_text(), model_text()
        check('оригинальные литералы' in page.locator('[data-session-local-label]').inner_text(),
              'patch step: the local pane is captioned as the original literals')
        check(f'const tenant = "{SESSION_MAPPINGS[TENANT][0]}";' in local
              and f'const tenant = "{SESSION_MAPPINGS[TENANT][1]}";' in model
              and SESSION_MAPPINGS[TENANT][0] not in model,
              'patch step: the exact-code-literal context differs between local and model')
        check('*** Update File: src/billing.ts' in model
              and 'await db.$transaction(async tx => {' in model
              and 'await tx.webhookEvent.create({' in model
              and 'data: { id: event.id } // UNIQUE' in model
              and 'await creditBalance(event.data.object, tenant, tx);' in model
              and '# duplicate-event обрабатывается отдельно' in model,
              'patch step: the diff keeps its transaction structure and its comments')
        check('/Users/' not in local and '/Users/' not in model,
              'patch step: the patch is a relative path; no workspace path is involved')
        # Step 6 of 7: a passing test still prints the fixture and the token — and
        # the token is the same plausible substitute the config step showed.
        page.locator('[data-session-step="5"]').click()
        local, model = local_text(), model_text()
        check(f'fixture={{"email":"{SESSION_MAPPINGS[EMAIL][0]}","tenant":"{SESSION_MAPPINGS[TENANT][0]}"}}' in local,
              'test step: the local dump still holds the fixture originals')
        check(f'fixture={{"email":"{SESSION_MAPPINGS[EMAIL][1]}","tenant":"{SESSION_MAPPINGS[TENANT][1]}"}}' in model,
              'test step: the fixture email and tenant are replaced for the model')
        check(field_value(model, r'^GITHUB_TOKEN=(\S+)$') == fake_token and raw_token not in model,
              'test step: the dumped token is the same substitute the config step used, never the original')
        check('sequential retry → one credit' in model and 'invalid signature → rejected' in model
              and 'billing UI → one row' in model,
              'test step: test names and assertions survive')
        check('test-results' not in model and 'artifact:' not in model,
              'test step: no artifact path is part of this fixture anymore')
        # Step 7 of 7: the replayed history must not undo the earlier steps, and
        # it carries no workspace path of its own.
        page.locator('[data-session-step="6"]').click()
        local, model = local_text(), model_text()
        check(page.locator('[data-session-local-label]').inner_text().strip() == 'Исходные данные в вашем контуре',
              'history step: the local pane is captioned as the originals in your perimeter')
        check(all(raw in local for raw in (SESSION_MAPPINGS[EMAIL][0], SESSION_MAPPINGS[HOST][0],
                                           SESSION_MAPPINGS[TENANT][0], raw_key, raw_token)),
              'history step: the local history still holds client, host, tenant, key and token')
        check(f'MCP customer: {SESSION_MAPPINGS[EMAIL][1]}' in model
              and f'API upstream: {SESSION_MAPPINGS[HOST][1]}' in model
              and f'code tenant: {SESSION_MAPPINGS[TENANT][1]}' in model
              and f'config key: {fake_key}' in model and f'test token: {fake_token}' in model,
              'history step: client, host, tenant, key and token stay substituted in the history')
        check(field_value(model, r'^config key: (\S+)$') == model_key
              and field_value(model, r'^test token: (\S+)$') == model_token,
              'history step: the history reuses the exact substitutes from the config step')
        check('История для следующего хода' in model and 'MCP → код → конфиг → API → patch → тесты' in model,
              'history step: the handoff outline is preserved for the next turn')
        check('/Users/' not in local and '/Users/' not in model,
              'history step: the replayed history carries no workspace path')
        check(SESSION_MAPPINGS[EMAIL][0] not in model and raw_key not in model and raw_token not in model,
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
        check(raw_key in model_text(),
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
              and raw_key not in model_text(),
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
              and SESSION_MAPPINGS[TENANT][0] not in model_text()
              and SESSION_MAPPINGS[TENANT][1] in model_text()
              and SESSION_MAPPINGS[EMAIL][1] in model_text(),
              'reset renders the protected first step again')
        page.locator('[data-session-step="0"]').click()
        check(page.locator('.p-brand-logo').count() == 2, 'official integration marks rendered')
        page.locator('#connectors').screenshot(path=str(out/'coding-connectors-logos.png'))
        page.screenshot(path=str(out/'ai-coding-desktop.png'),full_page=True)

        # The site's own navigation, through real links: home -> enterprise ->
        # coding, and back. The cross-browser paint-only veil must be loaded,
        # not merely present on disk; ordinary browser links remain native.
        page.goto(base + '/', wait_until='networkidle')
        nav_href = page.locator('link[rel="stylesheet"][href*="navigation.css"]').first.get_attribute('href')
        check(nav_href is not None, 'navigation.css is linked from the document head')
        check(bool(page.evaluate("[...document.styleSheets].some(s => (s.href || '').includes('navigation.css'))")),
              'navigation.css is loaded by the browser, not only referenced')
        nav_css = page.request.get(nav_href if nav_href.startswith('http') else base + nav_href).text()
        check('ps-page-enter' in nav_css and '280ms' in nav_css,
              'navigation.css declares only a soft cross-browser fade')
        check(page.locator('.ps-page-veil').count() == 0,
              'stylized navigation masks and bands are removed')
        check('prefers-reduced-motion' in nav_css and 'animation:none' in nav_css,
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

        # Normal-motion evidence: a stylesheet string is NOT proof an effect ran.
        # Exercise the soft page fade and simultaneous gallery crossfade.
        motion_context = browser.new_context(viewport={'width':1440,'height':1000}, reduced_motion='no-preference')
        motion_context.route('**/*', guard)
        motion_page = motion_context.new_page()
        motion_page.on('pageerror', lambda e: errors.append(str(e)))
        motion_page.goto(base+'/', wait_until='networkidle')
        with motion_page.expect_navigation(wait_until='domcontentloaded'):
            motion_page.locator('#products a[href="/ai-security"]').first.click()
        check(motion_page.evaluate('''() => document.documentElement.classList.contains('ps-nav-enter')
            && getComputedStyle(document.querySelector('.frame')).animationName === 'ps-page-enter'
            && getComputedStyle(document.querySelector('.frame')).animationDuration === '0.28s' '''),
              'normal-motion page navigation really runs the soft opacity fade')
        motion_page.locator('[data-real-tab="journal"]').click()
        check(motion_page.locator('.p-real-ghost[aria-hidden="true"]').count() == 1
              and motion_page.locator('[data-real-panel="journal"]').evaluate('(e) => e.getAnimations().some(a => a.effect.getTiming().duration === 360)'),
              'normal-motion gallery crossfades the old and new screen simultaneously')
        for name in ('access','policy','quality','journal'):
            motion_page.locator(f'[data-real-tab="{name}"]').click()
        motion_page.wait_for_function('() => !document.querySelector(".p-real-ghost")')
        check(motion_page.locator('[data-real-panel]:not([hidden])').count() == 1,
              'rapid gallery changes clean up old screens and leave one active panel')
        # The coding session crossfades the same way: the whole stage (panes plus
        # verdict) is cloned into an inert ghost, the live view animates in over
        # 320ms, and a burst of switches still leaves exactly one live view.
        motion_page.goto(base+'/ai-coding', wait_until='networkidle')
        motion_stage = motion_page.locator('[data-session-stage]')
        check(motion_stage.locator('[data-session-panes]').count() == 1
              and motion_stage.locator('.p-session-verdict').count() == 1,
              'normal-motion coding stage wraps the panes and the verdict')
        motion_page.locator('[data-session-step="2"]').click()
        check(motion_page.locator('[data-session-stage] > .p-session-ghost[aria-hidden="true"]').count() == 1,
              'normal-motion coding switch keeps an aria-hidden ghost of the previous view')
        check(motion_page.evaluate('''() => {
            const ghost = document.querySelector('[data-session-stage] > .p-session-ghost');
            if (!ghost) return false;
            const nodes = [ghost, ...ghost.querySelectorAll('*')];
            const hooks = nodes.flatMap(n => [...n.attributes].map(a => a.name))
                .filter(name => name.startsWith('data-session-'));
            return ghost.hasAttribute('inert') && ghost.getAttribute('aria-hidden') === 'true'
                && ghost.classList.contains('p-session-ghost') && hooks.length === 0;
        }'''), 'coding ghost is inert and every data-session hook is stripped from the clone')
        check(motion_page.locator('[data-session-view]').evaluate(
            '(e) => e.getAnimations().some(a => a.effect.getTiming().duration === 320)'),
            'normal-motion coding view really animates in over 320ms')
        for step in ('0','3','5','6'):
            motion_page.locator(f'[data-session-step="{step}"]').click()
        motion_page.wait_for_function('() => !document.querySelector(".p-session-ghost")')
        check(motion_page.locator('[data-session-stage] > .p-session-ghost').count() == 0
              and motion_page.locator('[data-session-view]').count() == 1,
              'rapid coding changes clean up the ghost and leave one live view')
        motion_context.close()

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
