"""Inspect actual real-run chats via Playwright; screenshots stay encrypted."""
import base64
from pathlib import Path
import json
import re
import sys
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'prototype'))
from bench.doubleup.storage import RunStore
from dialogue_runner import scope_for
from prepare_dialogue_replay import AAD


def main():
    state=HERE/'.state';bundle='september-qualified-cases-v1'
    key=(state/'runtime'/f'{bundle}.key').read_bytes();r=(state/'runtime'/f'{bundle}.aesgcm').read_bytes()
    packet=json.loads(AESGCM(key).decrypt(r[:12],r[12:],AAD));case=next(c for c in packet['cases'] if c['source_index']==7)
    scope=scope_for(case,'pseudex',packet['run_id']+'-live-qualified-live-v1')
    url=f'http://127.0.0.1:18880/{scope["tenant_id"]}/assistantnew/{scope["agent_id"]}?thread={scope["thread_id"]}'
    archive=RunStore('september-chat-browser-evidence-v2',True)
    checks=[];errors=[];failures=[];stage='open_chat';status=1
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(storage_state=str(state/'browser/storage.json'),viewport={'width':1440,'height':1100})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(type(e).__name__))
        page.on('response',lambda r:failures.append(r.status) if r.status>=400 and '/pseudex/' in urlsplit(r.url).path else None)
        try:
            response=page.goto(url,wait_until='domcontentloaded',timeout=60000)
            assert response and response.status==200
            if '/login' in page.url:
                creds=json.loads((state/'runtime/browser.json').read_text())
                page.locator('input[name="user_id"]').fill('pilot-owner@example.invalid')
                page.locator('input[name="password"]').fill(creds['password'])
                page.get_by_role('button',name='Войти',exact=True).click()
                page.wait_for_url(lambda u:'/login' not in u,timeout=60000)
                page.goto(url,wait_until='domcontentloaded',timeout=60000)
            button=page.locator('[data-testid="pseudex-open"]:visible').first
            button.wait_for(timeout=60000)
            checks.append('actual_source_chat_renders_privacy_controls')
            token=page.evaluate('() => localStorage.getItem("auth_access_token")')
            h={'Authorization':'Bearer '+token,'X-Org-Id':scope['tenant_id']}
            listing=context.request.get('http://127.0.0.1:18860/api/v1/pseudex/inspections',
                params={'thread_id':scope['thread_id']},headers=h)
            assert listing.status==200
            selected=None
            for item in listing.json()['items']:
                d=context.request.get('http://127.0.0.1:18860/api/v1/pseudex/inspections/'+item['attempt_id'],headers=h)
                if d.status!=200:continue
                data=d.json()
                if data.get('tool_dispatches') and data.get('restoration',{}).get('replacements'):
                    selected=item['attempt_id'];break
            assert selected,'real_tool_restoration_attempt_missing'
            stage='open_boundary'
            button.click()
            panel=page.get_by_role('dialog',name=re.compile('Граница данных.*Pseudex'))
            panel.wait_for(timeout=30000)
            # The UI uses ordinal labels, not ids. Pick the button by DOM
            # attribute if present, otherwise match its list order from API.
            buttons=panel.get_by_role('button')
            target=panel.locator('[data-attempt-id="'+selected+'"]')
            if target.count():target.first.click()
            else:
                metadata=listing.json()['items']
                n=next(i for i,item in enumerate(metadata) if item['attempt_id']==selected)
                # Fall back only to a supplied attempt identifier in the label;
                # never guess a timestamp or canonical token.
                by_id=panel.get_by_role('button',name=re.compile(re.escape(selected)))
                if by_id.count():by_id.first.click()
                else:
                    # The production component labels attempts by their ordinal
                    # in THIS API listing, then groups them visually by mode.
                    by_ordinal=panel.get_by_role('button',name=re.compile(r'^Запрос '+str(n+1)+r'(?:\s|•)'))
                    assert by_ordinal.count()==1,'attempt_selector_unavailable'
                    by_ordinal.click()
            panel.get_by_test_id('pseudex-attempt-detail').wait_for(timeout=30000)
            checks.append('recorded_real_attempt_selected')
            stage='model_boundary'
            panel.get_by_role('tab',name='Отправлено модели',exact=True).click()
            panel.get_by_role('tabpanel').wait_for()
            checks.append('actual_masked_model_request_tab_visible')
            stage='tool_boundary'
            panel.get_by_role('tab',name='Передано инструменту',exact=True).click()
            panel.get_by_role('tabpanel').wait_for()
            hops=panel.get_by_test_id('pseudex-tool-hops')
            hops.wait_for(timeout=30000)
            assert hops.get_by_text('исполнение записано',exact=False).count()>0
            assert hops.get_by_text('Аргументы совпадают с переданными исполнителю.',exact=False).count()>0
            checks.append('real_tool_dispatch_and_matching_restored_arguments_visible')
            png=page.screenshot(full_page=True)
            archive.encrypt('tool-boundary-screenshot.aesgcm',{'media_type':'image/png','base64':base64.b64encode(png).decode()})
            assert not errors,'browser_page_errors'
            status=0
        except Exception as e:
            failures.append({'stage':stage,'error_type':type(e).__name__})
        finally:
            context.close();browser.close()
    report={'passed':status==0,'checks':checks,'page_error_count':len(errors),'failures':failures,
            'provider_calls':0,'screenshots_encrypted':True,'real_dialogue_not_fixture':True,
            'original_pseudex_run_status':'stopped_after_first_completed_turn'}
    archive.encrypt('report.aesgcm',report);archive.finish({'kind':'actual_source_chat_playwright_check',**report});archive.verify()
    path=state/'september-chat-browser-gate.json';path.write_text(json.dumps(report,indent=2));path.chmod(0o600)
    print(json.dumps(report));raise SystemExit(status)

if __name__=='__main__':main()
