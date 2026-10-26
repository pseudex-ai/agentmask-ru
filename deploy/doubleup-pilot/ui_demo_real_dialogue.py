"""Open a COMPLETED protected dialogue in the real UI and capture the panel.

Read-only: no chat turn is sent, no model call, no reveal click. Screenshots of
the source tab are written to a private directory and NOT published; the tabs
that show substitutes are the evidence shown to the user.
"""
import base64, json, re, sys
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'prototype'))
from bench.doubleup.storage import RunStore
from dialogue_runner import scope_for, unseal
from prepare_dialogue_replay import AAD

STATE = HERE / '.state'
BUNDLE = 'release-rc-protected-v4'
REVISION = 'rc-protected-v4'
CASE = 99


def main():
    key = (STATE / 'runtime' / f'{BUNDLE}.key').read_bytes()
    raw = (STATE / 'runtime' / f'{BUNDLE}.aesgcm').read_bytes()
    packet = json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], AAD))
    case = next(c for c in packet['cases'] if c['source_index'] == CASE)
    scope = scope_for(case, 'pseudex', packet['run_id'] + '-live-' + REVISION)
    folder = STATE / (packet['run_id'] + '-live-' + REVISION)
    prefix = case['case_id'] + '-pseudex'
    summary = unseal(folder / (prefix + '.complete.aesgcm'), key, prefix + ':complete')
    url = summary['url']

    archive = RunStore('release-rc-ui-demo-v3', True)
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(STATE / 'browser/storage.json'),
                                      viewport={'width': 1440, 'height': 1400})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(type(e).__name__))
        page.goto(url, wait_until='domcontentloaded', timeout=90000)
        if '/login' in page.url:
            creds = json.loads((STATE / 'runtime/browser.json').read_text())
            page.locator('input[name="user_id"]').fill('pilot-owner@example.invalid')
            page.locator('input[name="password"]').fill(creds['password'])
            page.get_by_role('button', name='Войти', exact=True).click()
            page.wait_for_url(lambda u: '/login' not in u, timeout=90000)
            page.goto(url, wait_until='domcontentloaded', timeout=90000)
        page.get_by_test_id('pseudex-open').first.wait_for(timeout=90000)
        checks.append('completed_protected_chat_renders')

        token = page.evaluate("() => localStorage.getItem('auth_access_token')")
        headers = {'Authorization': 'Bearer ' + token, 'X-Org-Id': scope['tenant_id']}
        listing = context.request.get('http://127.0.0.1:18860/api/v1/pseudex/inspections',
                                      params={'thread_id': scope['thread_id']}, headers=headers)
        assert listing.status == 200, listing.status
        items = listing.json()['items']
        chosen, ordinal = None, None
        for index, item in enumerate(items):
            detail = context.request.get(
                'http://127.0.0.1:18860/api/v1/pseudex/inspections/' + item['attempt_id'], headers=headers)
            if detail.status != 200:
                continue
            data = detail.json()
            if data.get('tool_dispatches') and (data.get('restoration') or {}).get('replacements'):
                chosen, ordinal = item['attempt_id'], index + 1
                break
        assert chosen, 'attempt_with_tools_and_restore_missing'

        page.get_by_test_id('pseudex-open').first.click()
        panel = page.get_by_role('dialog', name=re.compile('Граница данных.*'))
        panel.wait_for(timeout=60000)
        by_ordinal = panel.get_by_role('button', name=re.compile(r'^Запрос ' + str(ordinal) + r'(?:\s|•)'))
        if by_ordinal.count():
            by_ordinal.first.click()
        else:
            panel.get_by_role('button', name=re.compile(re.escape(chosen))).first.click()
        panel.get_by_test_id('pseudex-attempt-detail').wait_for(timeout=60000)
        checks.append('real_attempt_selected')

        page.screenshot(path=str(STATE / 'browser/demo-chat-with-panel.png'), full_page=True)
        archive.encrypt('chat-with-panel.aesgcm', {
            'media_type': 'image/png',
            'base64': base64.b64encode((STATE / 'browser/demo-chat-with-panel.png').read_bytes()).decode()})

        panel.get_by_role('tab', name='Отправлено модели', exact=True).click()
        panel.get_by_role('tabpanel').wait_for()
        page.screenshot(path=str(STATE / 'browser/demo-model-view.png'), full_page=True)
        checks.append('model_boundary_tab')
        archive.encrypt('model-view.aesgcm', {
            'media_type': 'image/png',
            'base64': base64.b64encode((STATE / 'browser/demo-model-view.png').read_bytes()).decode()})

        panel.get_by_role('tab', name='Передано инструменту', exact=True).click()
        tabpanel = panel.get_by_role('tabpanel')
        tabpanel.wait_for(timeout=60000)
        # The four-hop projection is a private 60-second view and this dialogue
        # is older, so its rows may legitimately be gone. The DISPATCH RECORDS
        # are durable and are what the panel renders from `tool_dispatches`.
        hops = panel.get_by_test_id('pseudex-tool-hops')
        executed = 0
        matched = 0
        if hops.count():
            try:
                hops.wait_for(timeout=15000)
                executed = hops.get_by_text('исполнение записано', exact=False).count()
                matched = hops.get_by_text('Аргументы совпадают с переданными исполнителю.',
                                           exact=False).count()
            except Exception:  # noqa: BLE001 - expired projection is expected and stated
                pass
        dispatch_badges = tabpanel.get_by_text(re.compile(r'Запись диспетчеризации'),
                                                exact=False).count()
        assert dispatch_badges > 0 or executed > 0, 'no recorded tool dispatch shown'
        page.screenshot(path=str(STATE / 'browser/demo-tool-view.png'), full_page=True)
        checks.append('tool_boundary_tab')
        archive.encrypt('tool-view.aesgcm', {
            'media_type': 'image/png',
            'base64': base64.b64encode((STATE / 'browser/demo-tool-view.png').read_bytes()).decode()})

        panel.get_by_role('tab', name='Ответ модели', exact=True).click()
        panel.get_by_role('tabpanel').wait_for()
        page.screenshot(path=str(STATE / 'browser/demo-response-view.png'), full_page=True)
        checks.append('response_tab')

        report = {'passed': True, 'checks': checks, 'case': CASE, 'turns': summary['turns'],
                  'model_calls': summary['models'], 'tool_calls': summary['tools'],
                  'tool_errors': summary['tool_errors'],
                  'chat_url': url, 'attempt_ordinal': ordinal,
                  'tool_rows_claiming_execution': executed,
                  'tool_rows_claiming_matching_arguments': matched,
                  'page_errors': len(errors), 'provider_calls': 0,
                  'no_chat_turn_sent_by_this_check': True,
                  'source_tab_screenshot_published': False}
        target = STATE / 'release-rc-20261025/ui-demo.json'
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        target.chmod(0o600)
        archive.encrypt('report.aesgcm', report)
        archive.finish({'kind': 'completed_protected_dialogue_ui_demo', **{k: report[k] for k in
                       ('case', 'turns', 'tool_calls', 'attempt_ordinal')}})
        archive.verify()
        context.close()
        browser.close()
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
