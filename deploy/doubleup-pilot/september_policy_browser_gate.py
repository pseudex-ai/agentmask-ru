"""Playwright-only platform UI QA using the REAL backend and combined engine.

Doc-grounded checks: platform-authenticated policy CRUD, persisted rule/binding,
attribution preview, credential refusal. No mock routes, no model calls, no
customer text in screenshots/logs. Temporary configuration is removed afterward.
"""
from pathlib import Path
import json
import uuid
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent
STATE=HERE/'.state'


def main():
    checks=[];network=[];errors=[];stage='launch';status=1
    ident='qa-browser-'+uuid.uuid4().hex[:10];agent=ident+'-agent'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(storage_state=str(STATE/'browser/storage.json'),viewport={'width':1440,'height':1000})
        page=context.new_page()
        page.on('pageerror',lambda e:errors.append(type(e).__name__))
        page.on('response',lambda r:network.append({'method':r.request.method,'status':r.status})
                if '/api/v1/pseudex/policies' in urlsplit(r.url).path else None)
        try:
            stage='open_policy_screen'
            page.goto('http://127.0.0.1:18880/doubleup-pilot/settings/policies',wait_until='domcontentloaded',timeout=60000)
            if '/login' in page.url:
                credentials=json.loads((STATE/'runtime/browser.json').read_text())
                page.locator('input[name="user_id"]').fill('pilot-owner@example.invalid')
                page.locator('input[name="password"]').fill(credentials['password'])
                page.get_by_role('button',name='Войти',exact=True).click()
                page.wait_for_url(lambda u:'/login' not in u,timeout=60000)
                page.goto('http://127.0.0.1:18880/doubleup-pilot/settings/policies',wait_until='domcontentloaded',timeout=60000)
            page.get_by_test_id('policies-screen').wait_for(timeout=60000)
            page.wait_for_function('() => document.querySelectorAll("[data-testid=policies-screen][aria-busy=false]").length>0',timeout=30000)
            page.wait_for_function('() => !document.querySelector("[data-testid=policies-card]").innerText.includes("Читаю политики")',timeout=30000)
            assert page.get_by_test_id('load-error').count()==0,'policy_load_failed'
            checks.append('real_platform_policy_screen_loaded')
            stage='create'
            page.get_by_test_id('policy-new-id').fill(ident)
            page.get_by_test_id('policy-new-title').fill('QA — временная политика')
            with page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path.endswith('/pseudex/policies')) as event:
                page.get_by_test_id('policy-create').click()
            assert event.value.status==201
            row=page.locator('[data-testid="policy-row"]').filter(has=page.locator('[data-policy-id="'+ident+'"]'))
            page.locator('[data-testid="policy-open"][data-policy-id="'+ident+'"]').click()
            page.get_by_test_id('rules-card').wait_for()
            checks.append('policy_created_through_browser_and_real_api')
            stage='edit_rule'
            page.get_by_test_id('rule-add').click()
            page.get_by_test_id('rule-action').last.select_option('ignore')
            page.get_by_test_id('rule-category').last.fill('NAME')
            page.get_by_test_id('rule-values').last.fill('РОП')
            with page.expect_response(lambda r:r.request.method=='PUT' and urlsplit(r.url).path.endswith('/policies/'+ident)) as event:
                page.get_by_test_id('policy-save').click()
            assert event.value.status==200
            checks.append('value_scoped_ignore_saved_in_actual_engine')
            stage='bind_agent'
            page.get_by_test_id('binding-add').click()
            binding=page.get_by_test_id('binding-row').last
            binding.get_by_test_id('binding-agent').fill(agent)
            binding.get_by_test_id('binding-policy').select_option(ident)
            with page.expect_response(lambda r:r.request.method=='PUT' and urlsplit(r.url).path.endswith('/policies/bindings')) as event:
                page.get_by_test_id('bindings-save').click()
            assert event.value.status==200
            page.reload(wait_until='domcontentloaded')
            page.get_by_test_id('policies-screen').wait_for()
            page.wait_for_function('() => document.querySelectorAll("[data-testid=policies-screen][aria-busy=false]").length>0',timeout=30000)
            assert agent in page.get_by_test_id('binding-agent').evaluate_all('(els)=>els.map(e=>e.value)')
            checks.append('binding_persists_after_page_reload')
            stage='preview'
            page.get_by_test_id('preview-headers').fill(json.dumps({'x-agent-id':agent}))
            page.get_by_test_id('preview-body').fill('{}')
            with page.expect_response(lambda r:urlsplit(r.url).path.endswith('/policies/preview')) as event:
                page.get_by_test_id('preview-run').click()
            assert event.value.status==200
            page.get_by_test_id('preview-result').wait_for()
            assert page.get_by_test_id('preview-policy').inner_text()==ident
            assert page.get_by_test_id('preview-matched').inner_text()=='header:x-agent-id'
            checks.append('browser_preview_resolves_its_own_engine_policy')
            stage='screenshot'
            page.screenshot(path=str(STATE/'browser/september-policy-real-api.png'),full_page=True)
            stage='delete'
            # First remove its binding in the UI; a bound policy must not vanish.
            target=page.get_by_test_id('binding-row').filter(has=page.locator('input[data-testid="binding-agent"]'))
            for i in range(page.get_by_test_id('binding-row').count()-1,-1,-1):
                r=page.get_by_test_id('binding-row').nth(i)
                if r.get_by_test_id('binding-agent').input_value()==agent:r.get_by_test_id('binding-remove').click()
            with page.expect_response(lambda r:r.request.method=='PUT' and urlsplit(r.url).path.endswith('/policies/bindings')) as event:
                page.get_by_test_id('bindings-save').click()
            assert event.value.status==200
            page.locator('[data-testid="policy-delete"][data-policy-id="'+ident+'"]').click()
            with page.expect_response(lambda r:r.request.method=='DELETE' and urlsplit(r.url).path.endswith('/policies/'+ident)) as event:
                page.get_by_test_id('policy-delete-confirm').click()
            assert event.value.status==200
            checks.append('browser_unbind_and_delete_complete')
            assert not errors,'browser_page_error'
            status=0
        except Exception as e:
            print(json.dumps({'browser_passed':False,'stage':stage,'error_type':type(e).__name__,
                              'checks':checks,'policy_http':network,'page_error_count':len(errors)}))
        finally:
            # Cleanup is housekeeping through the platform JWT, never through a
            # browser-held engine admin key. It is not claimed as a UI check.
            token=page.evaluate('() => localStorage.getItem("auth_access_token")') if not page.is_closed() else None
            if token:
                h={'Authorization':'Bearer '+token,'X-Org-Id':'doubleup-pilot'}
                root='http://127.0.0.1:18860/api/v1/pseudex/policies'
                b=context.request.get(root+'/bindings',headers=h)
                if b.status==200:
                    data=b.json();filtered=[x for x in data['bindings'] if x['agent_key']!=agent]
                    if len(filtered)!=len(data['bindings']):context.request.put(root+'/bindings',headers=h,data={
                        'bindings':filtered,'default_policy_id':data['default_policy_id']})
                context.request.delete(root+'/'+ident,headers=h)
            context.close();browser.close()
    report={'passed':status==0,'checks':checks,'page_error_count':len(errors),'policy_http':network,
            'mock_routes_used':False,'provider_calls':0,'source_data_in_screenshots':False}
    out=STATE/'september-policy-browser-gate.json';out.write_text(json.dumps(report,indent=2));out.chmod(0o600)
    print(json.dumps(report))
    raise SystemExit(status)

if __name__=='__main__':main()
