"""Real Chromium acquisition/consent proof, with every HTTP request locally routed.

Run from storefront using the existing Playwright venv and pw-browsers directory:
    PLAYWRIGHT_BROWSERS_PATH=/path/to/.venv/pw-browsers /path/to/.venv/bin/python test_acquisition_browser.py

Reuses the existing render-only harness, not its exact-init expectations. Django
uses temporary SQLite, locmem mail and synthetic .invalid contacts; Python sockets
are denied during rendering. Provider SDKs are explicit local stubs. No live
provider, replay, delivery, production or lawfulness claim; failures exit nonzero.
"""

import json
import mimetypes
from pathlib import Path
import sys
import tempfile
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
from test_analytics_browser import (CONSENT, COUNTER, EMAIL, METRIKA_STUB,
                                    METRIKA_URL, ORIGIN, ROOT, RYBBIT_STUB,
                                    RYBBIT_URL, render_pages, require)

CLIPBOARD_STUB = """
window.__clipboardCalls = 0;
window.__clipboardMode = 'success';
Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
    writeText: async function () {
        window.__clipboardCalls++;
        if (window.__clipboardMode === 'failure') throw new Error('offline fixture refusal');
        if (window.__clipboardMode === 'pending') await new Promise(resolve => { window.__finishCopy = resolve; });
    }
}});
"""


def fixtures(directory):
    pages = render_pages(directory)
    from django.conf import settings
    from django.db import connections
    from django.test import Client, override_settings

    attempts = []

    def deny_network(*args, **kwargs):
        attempts.append('socket')
        raise AssertionError('No Python network in acquisition rendering')

    with patch('socket.socket.connect', deny_network), \
            patch('socket.socket.connect_ex', deny_network), \
            patch('socket.getaddrinfo', deny_network), \
            override_settings(
                SUPPORT_EMAIL='support@example.invalid', SUPPORT_BOT='offline_support_bot',
                STATIC_ROOT=directory / 'staticfiles',
                STORAGES={
                    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
                }):
        try:
            client = Client(HTTP_HOST='storefront.invalid')
            for name, path in [('landing', '/'), ('architecture', '/architecture')]:
                response = client.get(path, secure=True)
                require(response.status_code == 200, f'{path} must render, got {response.status_code}')
                pages[name] = (response.content.decode(), response.headers.get('Content-Security-Policy', ''))
            with override_settings(ANALYTICS={**settings.ANALYTICS, 'mode': 'full'}, METRIKA_ID=''):
                response = client.get('/', secure=True)
                pages['landing-rybbit'] = (response.content.decode(), response.headers.get('Content-Security-Policy', ''))
            with override_settings(SUPPORT_EMAIL='', SUPPORT_BOT='offline_support_bot'):
                response = client.get('/', secure=True)
                pages['enterprise-telegram'] = (response.content.decode(), response.headers.get('Content-Security-Policy', ''))
            with override_settings(SUPPORT_EMAIL='', SUPPORT_BOT=''):
                response = client.get('/', secure=True)
                pages['enterprise-requisites'] = (response.content.decode(), response.headers.get('Content-Security-Policy', ''))
        finally:
            connections.close_all()
    require(not attempts, 'Rendering attempted a socket, even if caught')
    pages['unknown-success'] = (pages['signup'][0].replace('data-goal="signup"', 'data-goal="arbitrary_goal"'), pages['signup'][1])
    return pages


@contextmanager
def document(browser, pages, name='landing', remembered=None):
    from playwright.sync_api import expect
    state = {'cookies': [], 'origins': []}
    if remembered is not None:
        state['origins'] = [{'origin': ORIGIN, 'localStorage': [{'name': CONSENT, 'value': remembered}]}]
    requests, unexpected, errors = [], [], []
    with browser.new_context(storage_state=state, service_workers='block',
                             viewport={'width': 1280, 'height': 800}, reduced_motion='reduce') as context:
        context.set_default_timeout(5000)
        context.add_init_script(CLIPBOARD_STUB)
        html, csp = pages[name]

        def route_request(route):
            request = route.request
            requests.append((request.url, request.method))
            if urlsplit(request.url).netloc == 'storefront.invalid' and urlsplit(request.url).path == '/fixture/' + name:
                route.fulfill(content_type='text/html', body=html,
                              headers={'Content-Security-Policy': csp} if csp else {})
            elif request.url == METRIKA_URL:
                route.fulfill(content_type='application/javascript', body=METRIKA_STUB)
            elif request.url == RYBBIT_URL:
                route.fulfill(content_type='application/javascript', body=RYBBIT_STUB)
            elif request.url.startswith(ORIGIN + '/static/') or request.url == ORIGIN + '/favicon.ico':
                path = urlsplit(request.url).path
                relative = path.removeprefix('/static/') if path.startswith('/static/') else 'favicon.ico'
                source = (ROOT / 'static' / relative).resolve()
                if source.is_relative_to(ROOT / 'static') and source.is_file():
                    route.fulfill(body=source.read_bytes(), content_type=mimetypes.guess_type(str(source))[0] or 'application/octet-stream')
                else:
                    unexpected.append(request.url)
                    route.abort()
            else:
                unexpected.append(request.url)
                route.abort()

        context.route('**/*', route_request)
        context.route_web_socket('**/*', lambda socket: (unexpected.append(socket.url), socket.close()))
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.goto(ORIGIN + '/fixture/' + name, wait_until='load')
        # Keep authentic authored hrefs/contact channels but prevent navigating to
        # external mail/Telegram or sending the fixture form. Validation stays real.
        page.evaluate("""() => {
            document.addEventListener('click', e => { if (e.target.closest('a')) e.preventDefault(); }, true);
            document.addEventListener('submit', e => e.preventDefault(), true);
        }""")
        yield page, requests
        require(not unexpected, f'{name}: unexpected requests blocked {unexpected}')
        require(not errors, f'{name}: browser errors {errors}')
        if name != 'both-disabled':
            expect(page.locator('[data-analytics-preferences]')).to_be_visible()


def goals(page, name=None):
    result = page.evaluate("(window.__ymCalls || []).filter(c => c[1] === 'reachGoal')")
    return [call for call in result if name is None or call[2] == name]


def providers(page, rybbit=1, metrika=1):
    page.wait_for_function('([r, m]) => (window.__rybbitLoads || 0) === r && (window.__metrikaLoads || 0) === m', arg=[rybbit, metrika])
    calls = page.evaluate('window.__ymCalls || []')
    init = [call for call in calls if call[1] == 'init']
    require(len(init) == metrika, f'Expected {metrika} init, got {init}')
    if metrika:
        require(init[0][0] == COUNTER and init[0][2]['webvisor'] is True, 'Wrong counter or Webvisor disabled')


def duplicate(page):
    page.evaluate("""() => {
        window.__duplicateLoaded = false;
        const original = document.querySelector('script[src$="/static/analytics.js"]');
        const duplicate = document.createElement('script');
        for (const attr of original.attributes) duplicate.setAttribute(attr.name, attr.value);
        duplicate.onload = () => { window.__duplicateLoaded = true; };
        document.body.appendChild(duplicate);
    }""")
    page.wait_for_function('() => window.__duplicateLoaded === true')


def click(page, selector):
    page.locator(selector).first.click()


def choose_plan(page, value):
    from playwright.sync_api import expect
    # The radio is visually covered by its styled label. Exercise the same
    # visible control a visitor clicks, not an artificial forced input click.
    page.locator('#signup-form .planpick summary').click()
    page.locator(f'#signup-form label:has(input[name="plan"][value="{value}"])').click()
    expect(page.locator(f'#signup-form input[name="plan"][value="{value}"]')).to_be_checked()


def fill_signup(page):
    page.locator('#signup-form input[name="email"]').fill('acquisition@example.invalid')
    page.locator('#signup-form input[name="company"]').fill('Synthetic private company')
    page.locator('#signup-form input[name="consent"]').check()
    page.locator('#signup-form input[name="terms"]').check()


def no_consent_cases(browser, pages):
    from playwright.sync_api import expect
    for remembered, answer in [(None, None), (None, 'no'), ('no', None)]:
        with document(browser, pages, remembered=remembered) as (page, requests):
            duplicate(page)
            expect(page.get_by_role('dialog', name='Аналитика')).to_have_count(0 if remembered else 1)
            if answer:
                click(page, '[data-consent="no"]')
            click(page, '[data-acquisition-placement="header"]')
            choose_plan(page, 'work')
            fill_signup(page)
            click(page, '#signup-form button[type="submit"]')
            click(page, '[data-copy-btn]')
            expect(page.locator('[data-copy-btn]').first).to_have_text('СКОПИРОВАНО')
            require(not goals(page), 'Prechoice/declined actions must not create goals')
            require(not [url for url, _ in requests if not url.startswith(ORIGIN)], 'Provider requested without consent')
            require(page.evaluate('typeof window.ym') == 'undefined', 'Prechoice/declined ym queue exists')
            if answer or remembered:
                page.reload(wait_until='load')
                providers(page, 0, 0)
                require(not goals(page), 'Decline persisted incorrectly across reload')
        print(f'PASS no-consent actions discarded: remembered={remembered}, answer={answer}')

    with document(browser, pages) as (page, requests):
        # A promise started before consent cannot become a retrospective goal.
        page.evaluate("window.__clipboardMode = 'pending'")
        click(page, '[data-copy-btn]')
        page.wait_for_function('() => typeof window.__finishCopy === "function"')
        click(page, '[data-consent="yes"]')
        providers(page)
        page.evaluate('window.__finishCopy()')
        expect(page.locator('[data-copy-btn]').first).to_have_text('СКОПИРОВАНО')
        require(not goals(page, 'integration_copy'), 'Pending pre-consent copy was queued')
        require(not goals(page, 'plan_selected') and not goals(page, 'signup_attempt'), 'Pre-consent actions replayed')
    print('PASS accept: pre-consent/pending clipboard actions never replayed')


def acquisition_case(browser, pages):
    from playwright.sync_api import expect
    with document(browser, pages, remembered='yes') as (page, requests):
        providers(page)
        require(not goals(page), 'Initial landing render is not an observed pricing view')
        duplicate(page)
        click(page, '[data-acquisition-placement="header"]')
        require(goals(page, 'start_cta_click') == [[COUNTER, 'reachGoal', 'start_cta_click', {'placement': 'header'}]], 'Duplicate click listeners')
        page.locator('[data-acquisition-pricing]').scroll_into_view_if_needed()
        page.wait_for_function("() => (window.__ymCalls || []).some(c => c[2] === 'pricing_view')")
        page.locator('#top').scroll_into_view_if_needed()
        page.locator('[data-acquisition-pricing]').scroll_into_view_if_needed()
        require(len(goals(page, 'pricing_view')) == 1, 'Pricing view must be once per document')
        enterprise = page.locator('[data-acquisition-goal="enterprise_contact_click"]')
        require('mailto:support@example.invalid?subject=Enterprise' == enterprise.get_attribute('href'), 'Not the actual enterprise mailto')
        enterprise.click()
        enterprise.click()
        require(goals(page, 'enterprise_contact_click') == [[COUNTER, 'reachGoal', 'enterprise_contact_click', {'placement': 'pricing', 'channel': 'email'}]] * 2, 'Natural enterprise repeat or distinct goal broken')
        require(not goals(page, 'support_contact_click'), 'Enterprise was misclassified as basic support')
        click(page, '#faq [data-acquisition-channel="email"]')
        require(goals(page, 'support_contact_click') == [[COUNTER, 'reachGoal', 'support_contact_click', {'placement': 'faq', 'channel': 'email'}]], 'Basic support classification broken')
        page.locator('.support').evaluate('(el) => { el.open = true; }')
        click(page, '.support [data-acquisition-channel="telegram"]')
        click(page, '.support [data-acquisition-channel="feedback"]')
        click(page, 'footer [data-acquisition-channel="email"]')
        choose_plan(page, 'work')
        require(goals(page, 'plan_selected')[-1] == [COUNTER, 'reachGoal', 'plan_selected', {'placement': 'signup', 'plan': 'work'}], 'Actual radio plan not tracked')
        click(page, '#pricing [data-plan="free"]')
        require(goals(page, 'plan_selected')[-1][3]['plan'] == 'free', 'Non-bubbling pricing radio change not tracked')
        # Invalid browser-native form is not a submission; a valid submit event is
        # an attempt only, regardless of subsequent server refusal or success.
        click(page, '#signup-form button[type="submit"]')
        require(not goals(page, 'signup_attempt'), 'Invalid form invented a submit attempt')
        fill_signup(page)
        click(page, '#signup-form button[type="submit"]')
        require(goals(page, 'signup_attempt') == [[COUNTER, 'reachGoal', 'signup_attempt', {'placement': 'signup', 'plan': 'free'}]], 'Submit attempt missing/duplicated')
        require(not goals(page, 'signup'), 'Submit attempts cannot convert')
        for doc in ['how', 'architecture', 'knowledge_base', 'knowledge_article']:
            click(page, f'[data-acquisition-doc="{doc}"]')
        require([call[3] for call in goals(page, 'docs_open')] == [{'doc': value} for value in ['how', 'architecture', 'knowledge_base', 'knowledge_article']], 'Docs must send only fixed enum')
        copy = page.locator('[data-copy-btn]').first
        page.evaluate("window.__clipboardMode = 'failure'")
        copy.click()
        expect(copy).to_have_text('НЕ СКОПИРОВАЛОСЬ')
        require(not goals(page, 'integration_copy'), 'Failed clipboard counted as success')
        expect(copy).to_be_enabled()
        page.evaluate("window.__clipboardMode = 'success'")
        copy.click()
        expect(copy).to_have_text('СКОПИРОВАНО')
        require(goals(page, 'integration_copy') == [[COUNTER, 'reachGoal', 'integration_copy', {'placement': 'onboarding', 'source': 'agent_prompt'}]], 'Clipboard success must emit one static goal')
        # Unknown names and non-click goals cannot use DOM as a transport. Each
        # unknown enum rejects the whole event, rather than passing arbitrary text.
        before = goals(page)
        page.evaluate("""() => {
            for (const attrs of [
                {'goal':'unknown', 'placement':'header'},
                {'goal':'signup', 'placement':'header'},
                {'goal':'signup_attempt', 'placement':'signup'},
                {'goal':'integration_copy', 'placement':'onboarding'},
                {'goal':'start_cta_click', 'placement':'acquisition@example.invalid'},
                {'goal':'support_contact_click', 'placement':'faq', 'channel':'private-phone'},
                {'goal':'enterprise_contact_click', 'placement':'pricing', 'channel':'https://private.invalid'},
                {'goal':'docs_open', 'doc':'/how?email=private@example.invalid'}]) {
                const a = document.createElement('a');
                a.href = '/?private=private@example.invalid';
                for (const [k,v] of Object.entries(attrs)) a.setAttribute('data-acquisition-' + k, v);
                document.body.appendChild(a); a.click(); a.remove();
            }
            const radio = document.querySelector('#signup-form input[name="plan"]:checked');
            const old = radio.value;
            radio.value = 'private@example.invalid'; radio.dispatchEvent(new Event('change', {bubbles:true}));
            document.querySelector('#signup-form').dispatchEvent(new Event('submit', {bubbles:true}));
            radio.value = old;
            document.dispatchEvent(new CustomEvent('pseudex:acquisition', {detail:{goal:'signup', email:'private@example.invalid'}}));
            const privateSource = document.createElement('span');
            privateSource.setAttribute('data-copy', 'ps_live_private_fixture');
            document.body.appendChild(privateSource);
            privateSource.dispatchEvent(new CustomEvent('pseudex:integration-copy', {bubbles:true,detail:{source:'agent_prompt'}}));
            privateSource.remove();
        }""")
        require(goals(page) == before, 'Unknown DOM event/value bypassed allowlist')
        # Enumerate the exact privacy boundary of every custom call, not just a
        # forbidden-string regex that could miss another contact or copied text.
        schemas = {
            'start_cta_click': {'placement': {'header', 'hero', 'pricing', 'bottom'}},
            'pricing_view': {'placement': {'pricing'}},
            'plan_selected': {'placement': {'signup'}, 'plan': {'free', 'start', 'work', 'scale', 'enterprise'}},
            'signup_attempt': {'placement': {'signup'}, 'plan': {'free', 'start', 'work', 'scale', 'enterprise'}},
            'docs_open': {'doc': {'docs', 'how', 'architecture', 'litellm', 'knowledge_base', 'knowledge_article'}},
            'support_contact_click': {'placement': {'faq', 'floating', 'footer'}, 'channel': {'email', 'telegram', 'feedback'}},
            'enterprise_contact_click': {'placement': {'pricing'}, 'channel': {'email', 'telegram', 'requisites'}},
            'integration_copy': {'placement': {'onboarding'}, 'source': {'agent_prompt'}},
        }
        require(set(call[2] for call in goals(page)) == set(schemas), 'All eight actual behavioral identifiers must execute')
        for call in goals(page):
            schema = schemas[call[2]]
            require(len(call) == 4 and call[0] == COUNTER and set(call[3]) == set(schema), f'Unexpected goal shape {call}')
            require(all(value in schema[key] for key, value in call[3].items()), f'Unsafe goal enum {call}')
        require(sum(url == METRIKA_URL for url, _ in requests) == 1 and sum(url == RYBBIT_URL for url, _ in requests) == 1, 'Duplicate loader requested provider again')
    print('PASS all eight goals: actual DOM, observed pricing, radio, contacts, docs, clipboard and allowlists')


def preferences_cases(browser, pages):
    from playwright.sync_api import expect
    with document(browser, pages, remembered='no') as (page, requests):
        click(page, '[data-analytics-preferences]')
        expect(page.get_by_role('dialog', name='Аналитика')).to_have_count(1)
        click(page, '[data-consent-close]')
        require(page.evaluate('localStorage.getItem("pseudex.analytics.consent")') == 'no', 'Opening/closing preferences changed consent')
        click(page, '[data-analytics-preferences]')
        click(page, '[data-consent="yes"]')
        providers(page)
    with document(browser, pages, remembered='yes') as (page, requests):
        providers(page)
        duplicate(page)
        click(page, '[data-analytics-preferences]')
        expect(page.get_by_role('dialog', name='Аналитика')).to_have_count(1)
        require('не удалит уже собранные данные' in page.locator('.consent-text').inner_text(), 'Withdrawal must not claim erasure')
        require(page.evaluate('localStorage.getItem("pseudex.analytics.consent")') == 'yes', 'Preferences silently revoked consent')
        with page.expect_navigation(wait_until='load'):
            click(page, '[data-consent="no"]')
        require(page.evaluate('localStorage.getItem("pseudex.analytics.consent")') == 'no', 'Revoke did not persist no before GET')
        providers(page, 0, 0)
        require(not goals(page), 'Revoked fresh document contains goals')
        expect(page.locator('#rybbit-script')).to_have_count(0)
        expect(page.locator(f'script[src="{METRIKA_URL}"]')).to_have_count(0)
        require(all(method == 'GET' for _, method in requests), 'Withdrawal reposted form')
        require(requests.count((ORIGIN + '/fixture/landing', 'GET')) == 2, 'Withdrawal must perform a fresh GET navigation')
        page.reload(wait_until='load')
        providers(page, 0, 0)
        require(sum(url == METRIKA_URL for url, _ in requests) == 1 and sum(url == RYBBIT_URL for url, _ in requests) == 1, 'Reload after revoke loaded provider')
    print('PASS public preferences: remembered no→yes, close unchanged, yes→no GET, reload removes both trackers')


def success_and_configuration_cases(browser, pages):
    from playwright.sync_api import expect
    for name, signup in [('signup', True), ('resend', False), ('unknown-success', False)]:
        with document(browser, pages, name=name, remembered='yes') as (page, requests):
            providers(page)
            duplicate(page)
            expected = [[COUNTER, 'reachGoal', 'signup']] if signup else []
            require(goals(page) == expected, f'{name}: success goal semantics/dedup wrong')
            expect(page.locator('h2 span.ym-hide-content[data-private]')).to_have_text(EMAIL)
            field = page.locator('input[name="email"]')
            if signup:
                require('ym-disable-keys' in field.get_attribute('class').split() and field.get_attribute('data-private') is not None, 'Resend form must mask both SDKs')
            page.reload(wait_until='load')
            providers(page)
            require(goals(page) == expected, 'Success must remain once per document on reload')
            mask = page.locator('#rybbit-script').get_attribute('data-replay-mask-text-selectors')
            require(json.loads(mask) == ['[data-private]'], 'Rybbit masking changed')
    with document(browser, pages, name='landing-rybbit', remembered='yes') as (page, requests):
        providers(page, 1, 0)
        click(page, '[data-acquisition-placement="header"]')
        choose_plan(page, 'work')
        fill_signup(page)
        click(page, '#signup-form button[type="submit"]')
        click(page, '[data-copy-btn]')
        expect(page.locator('[data-copy-btn]').first).to_have_text('СКОПИРОВАНО')
        require(not goals(page) and page.evaluate('typeof window.ym') == 'undefined', 'Metrika-disabled loader emitted goals')
    with document(browser, pages, name='architecture', remembered='yes') as (page, requests):
        providers(page)
        click(page, 'footer [data-acquisition-doc="litellm"]')
        require(goals(page, 'docs_open') == [[COUNTER, 'reachGoal', 'docs_open', {'doc': 'litellm'}]], 'Base footer docs annotation absent')
        click(page, '[data-copy-btn]')
        expect(page.locator('[data-copy-btn]').first).to_have_text('СКОПИРОВАНО')
        require(not goals(page, 'integration_copy'), 'Non-onboarding copy must not become integration intent')
    for name, channel in [('enterprise-telegram', 'telegram'), ('enterprise-requisites', 'requisites')]:
        with document(browser, pages, name=name, remembered='yes') as (page, requests):
            providers(page)
            click(page, '[data-acquisition-goal="enterprise_contact_click"]')
            require(goals(page, 'enterprise_contact_click') == [[COUNTER, 'reachGoal', 'enterprise_contact_click', {'placement': 'pricing', 'channel': channel}]], 'Dynamic enterprise fallback misclassified')
    print('PASS signup conversion/resend privacy, unknown server goal denied, provider off, non-onboarding copy and enterprise fallbacks')


def main():
    sys.stdout.reconfigure(line_buffering=True)
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='pseudex-acquisition-browser-') as directory:
        pages = fixtures(Path(directory))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=[
                '--disable-background-networking', '--disable-component-update',
                '--host-resolver-rules=MAP * ~NOTFOUND'])
            try:
                print(f'Chromium {browser.version}; all HTTP routed, provider SDKs stubbed')
                no_consent_cases(browser, pages)
                acquisition_case(browser, pages)
                preferences_cases(browser, pages)
                success_and_configuration_cases(browser, pages)
            finally:
                browser.close()
    print('PASS acquisition browser suite; no skips; no live delivery/replay claim')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
