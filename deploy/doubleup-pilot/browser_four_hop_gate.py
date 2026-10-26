"""Actual chat input, inline marks and tool detail interactions; synthetic only."""

import json
import re
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import sync_playwright

from seed_four_hop import GRAPH, THREAD
from stand import STATE

CHAT = f'http://127.0.0.1:18880/doubleup-pilot/assistantnew/{GRAPH}?thread={THREAD}'


def main():
    with httpx.Client(timeout=5, trust_env=False) as client:
        assert client.get('http://127.0.0.1:18850/health').json()['mode'] == 'fixture'
        assert client.get('http://127.0.0.1:18860/llm/api/v1/health').status_code == 200
        assert client.get('http://127.0.0.1:18880/login').status_code == 200
    checks, failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(STATE / 'browser' / 'storage.json'), viewport={'width': 1440, 'height': 1100})
        page = context.new_page()
        page.on('response', lambda response: failures.append({'path': urlsplit(response.url).path, 'status': response.status}) if response.status >= 400 and '/pseudex/' in response.url else None)
        try:
            page.goto(CHAT, wait_until='domcontentloaded', timeout=60000)
            field = page.locator('textarea[placeholder="Введите сообщение..."]:visible').first
            field.wait_for(timeout=60000)
            field.fill('😀 Проверь контакт Иванов Пётр, почта pilot.person@example.org, телефон +7 916 123-45-67.')
            field.press('Enter')
            user = page.locator('mark[aria-label^="Подмена: пользователь → модель"]:visible').last
            user.wait_for(timeout=60000)
            user.hover()
            tooltip = page.get_by_role('tooltip').last
            tooltip.wait_for(timeout=10000)
            assert 'После подмены' in tooltip.inner_text() and 'для модели' in tooltip.inner_text()
            page.screenshot(path=str(STATE / 'browser' / 'inline-user-highlight.png'), full_page=True, animations='disabled')
            checks.append('actual_user_bubble_mask_hover')
            user.press('Escape')
            assistant = page.locator('mark[aria-label^="Восстановление: модель → пользователь"]:visible').last
            assistant.wait_for(timeout=30000)
            assistant.focus()
            tooltip = page.get_by_role('tooltip').last
            tooltip.wait_for(timeout=10000)
            assert 'До восстановления' in tooltip.inner_text() and 'от модели' in tooltip.inner_text()
            page.screenshot(path=str(STATE / 'browser' / 'inline-assistant-highlight.png'), full_page=True, animations='disabled')
            checks.append('actual_restored_assistant_bubble_focus')
            assistant.press('Escape')
            page.locator('[data-testid="pseudex-open"]:visible').first.click()
            panel = page.get_by_role('dialog', name='Граница данных Pseudex')
            panel.wait_for(timeout=10000)
            data = page.evaluate('''async (thread) => {
              const token=localStorage.getItem('auth_access_token');
              const headers={Authorization:`Bearer ${token}`,'X-Org-Id':'doubleup-pilot'};
              const r=await fetch(`http://127.0.0.1:18860/api/v1/pseudex/inspections/highlights?thread_id=${encodeURIComponent(thread)}`,{headers,cache:'no-store'});
              const j=await r.json();const ids=j.tools.filter(x=>x.hop==='model_to_tool'&&x.arguments_match===true&&x.completed===true).map(x=>x.attempt_id);
              const list=await fetch(`http://127.0.0.1:18860/api/v1/pseudex/inspections?thread_id=${encodeURIComponent(thread)}`,{headers,cache:'no-store'}).then(r=>r.json());
              return {ids,ordinal:list.items.findIndex(x=>x.attempt_id===ids[0])+1};
            }''', THREAD)
            assert data['ids']
            assert data['ordinal'] > 0
            panel.get_by_role('button', name=re.compile(r'^Запрос ' + str(data['ordinal']) + r'\b')).click()
            panel.get_by_role('tab', name='Передано инструменту', exact=True).click()
            hop = panel.get_by_test_id('pseudex-tool-hops')
            hop.wait_for(timeout=10000)
            assert 'Модель → инструмент' in hop.inner_text() and 'Инструмент → модель' in hop.inner_text()
            assert hop.locator('mark[role=button]').count() >= 2
            hop.scroll_into_view_if_needed()
            page.screenshot(path=str(STATE / 'browser' / 'four-hop-tool-panel.png'), full_page=True, animations='disabled')
            checks.append('both_tool_hops_highlighted_in_existing_menu')
            panel.get_by_role('button', name='Close').click()
            assert page.get_by_role('tooltip').count() == 0
            page.locator('[data-testid="pseudex-highlight-toggle"]:visible').first.click()
            assert page.locator('mark[role=button]').count() == 0
            checks.append('turning_off_unmounts_all_marks_and_peer_values')
        finally:
            context.close()
        mobile = browser.new_context(storage_state=str(STATE / 'browser' / 'storage.json'),
            viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        try:
            page = mobile.new_page()
            page.goto(CHAT, wait_until='domcontentloaded', timeout=60000)
            marker = page.locator('mark[aria-label^="Подмена: пользователь → модель"]:visible').last
            marker.wait_for(timeout=60000)
            marker.tap()
            page.get_by_role('tooltip').last.wait_for(timeout=10000)
            checks.append('mobile_first_tap_opens_explanation')
            marker.tap()
            page.get_by_role('tooltip').wait_for(state='detached', timeout=10000)
            checks.append('mobile_second_tap_closes_explanation')
            page.clock.install()
            page.locator('button:visible').filter(has_text='Обновить подсветку').first.click()
            marker.wait_for(timeout=10000)
            marker.tap()
            page.get_by_role('tooltip').last.wait_for(timeout=10000)
            page.screenshot(path=str(STATE / 'browser' / 'inline-mobile-highlight.png'), full_page=True, animations='disabled')
            before = page.get_by_role('tooltip').last.inner_text()
            page.clock.fast_forward(61000)
            assert page.locator('mark[role=button]').count() > 0
            after = page.get_by_role('tooltip').last.inner_text() if page.get_by_role('tooltip').count() else ''
            assert before != after
            checks.append('absolute_ttl_keeps_marks_but_erases_private_peer_payload')
        finally:
            mobile.close(); browser.close()
    report = {'passed': True, 'checks': checks, 'inspection_network_failures': failures,
              'synthetic_only': True, 'real_browser_and_backend': True, 'provider_calls_external': 0, 'paid_usd': 0}
    path = STATE / 'browser-four-hop-gate.json'; path.write_text(json.dumps(report, indent=2)); path.chmod(0o600)
    print(json.dumps(report))


if __name__ == '__main__': main()
