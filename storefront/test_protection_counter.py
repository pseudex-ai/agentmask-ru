"""Isolated API/DB contract + loopback browser acceptance for the counter demo.
No production source, licensing server, customer usage, writes outside temp DB,
providers or non-GET browser traffic. python test_protection_counter.py.
"""
import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit


def api_checks(directory):
    keep={k:os.environ[k] for k in ('PATH','HOME') if k in os.environ}
    os.environ.clear();os.environ.update(keep)
    os.environ.update({'DJANGO_SETTINGS_MODULE':'pseudex_site.settings','PSEUDEX_SECRET_KEY':'counter-test-only',
        'PSEUDEX_DEBUG':'1','PSEUDEX_DB_HOST':'','PSEUDEX_DB_PATH':str(Path(directory)/'counter.sqlite3'),
        'PSEUDEX_ANALYTICS_SALT_FILE':str(Path(directory)/'salt'),'PSEUDEX_ALLOWED_HOSTS':'testserver,localhost','SITE_URL':'http://testserver'})
    import django
    django.setup()
    from django.core.cache import cache
    from django.core.management import call_command
    from django.db import connection
    from django.test import Client, override_settings
    from storefront_web import protection_counter as counter
    call_command('migrate',verbosity=0)
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE counter_test_snapshot (total INTEGER, revision TEXT)')
        cursor.execute('INSERT INTO counter_test_snapshot VALUES (158000, %s)',['r1'])
    def db_reader():
        with connection.cursor() as cursor:
            cursor.execute('SELECT total, revision FROM counter_test_snapshot')
            total,revision=cursor.fetchone()
        return {'total':total,'revision':revision,'updated_at':datetime(2026,10,18,tzinfo=timezone.utc),
                'customer_names':['MUST NOT LEAK'],'admin_token':'MUST NOT LEAK'}
    module=types.ModuleType('counter_test_reader');module.read=db_reader
    sys.modules[module.__name__]=module
    old_logging=logging.root.manager.disable;logging.disable(logging.CRITICAL)
    class Contract(unittest.TestCase):
        def setUp(self):
            cache.clear();self.client=Client(enforce_csrf_checks=True)
            self.network=[patch.object(target,name,side_effect=AssertionError('external network forbidden')).start()
                for target,name in ((socket.socket,'connect'),(socket.socket,'connect_ex'),(socket,'getaddrinfo'))]
            self.addCleanup(patch.stopall)
        def tearDown(self):
            self.assertEqual(sum(m.call_count for m in self.network),0)
        def test_unknown_is_not_fake_zero(self):
            with override_settings(PUBLIC_PROTECTION_COUNTER_LOADER=''):
                response=self.client.get('/api/public/protection-counter')
            self.assertEqual(response.status_code,503);self.assertIsNone(response.json()['total'])
            self.assertEqual(response.json()['mode'],'unavailable')
            self.assertEqual(self.client.post('/api/public/protection-counter').status_code,403)  # CSRF middleware rejects first.
            self.assertEqual(Client().post('/api/public/protection-counter').status_code,405)  # View still rejects writes.
        def test_demo_is_complete_deterministic_snapshot(self):
            now=1900000000
            with patch.object(counter.time,'time',return_value=now):
                first=self.client.get('/api/public/protection-counter',{'demo':'1','started':now}).json()
                self.assertEqual(first['total'],9984)
                second=self.client.get('/api/public/protection-counter',{'demo':'1','started':now-5}).json()
                self.assertEqual(second['total'],10016)
                repeat=self.client.get('/api/public/protection-counter',{'demo':'1','started':now-5}).json()
                self.assertEqual(second,repeat)
                extra=self.client.get('/api/public/protection-counter',{'demo':'1','started':now,'advance':2}).json()
                self.assertEqual(extra['total'],10090)
                reset=self.client.get('/api/public/protection-counter',{'demo':'1'}).json()
                self.assertEqual(reset['total'],9984);self.assertEqual(reset['demo_started_at'],now)
                for params in ({'started':'nan'},{'started':now+5},{'started':now-3601},{'started':now,'advance':-1},{'started':now,'advance':10001}):
                    response=self.client.get('/api/public/protection-counter',{'demo':'1',**params})
                    self.assertEqual(response.status_code,400)
        def test_real_database_adapter_and_sanitized_cache(self):
            with override_settings(PUBLIC_PROTECTION_COUNTER_LOADER='counter_test_reader.read'):
                response=self.client.get('/api/public/protection-counter')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['total'],158000)
                self.assertEqual(set(response.json()),{'total','revision','updated_at','mode','poll_after_ms'})
                self.assertNotIn('MUST NOT LEAK',response.content.decode())
                with connection.cursor() as cursor:
                    cursor.execute('UPDATE counter_test_snapshot SET total=158020, revision=%s',['r2'])
                self.assertEqual(self.client.get('/api/public/protection-counter').json()['total'],158000)
                cache.clear()
                newer=self.client.get('/api/public/protection-counter').json()
                self.assertEqual(newer['total'],158020);self.assertEqual(newer['revision'],'r2')
                self.assertEqual(response['Cache-Control'],'no-store')
        def test_invalid_provider_data_is_unavailable(self):
            for total in (True,-1,2**53,1.5,'100'):
                with override_settings(PUBLIC_PROTECTION_COUNTER_LOADER=lambda:{'total':total,'revision':'bad','updated_at':datetime.now(timezone.utc)}):
                    self.assertEqual(self.client.get('/api/public/protection-counter').status_code,503)
                cache.clear()
        def test_counter_hidden_until_real_source_or_preview(self):
            with override_settings(PUBLIC_PROTECTION_COUNTER_LOADER=''):
                default=self.client.get('/').content.decode()
                self.assertNotIn('data-protection-counter',default)
                self.assertNotIn('protection-counter.js',default)
                self.assertNotIn('protection-counter.css',default)
                self.assertNotIn('ДЕМОНСТРАЦИЯ',default)
                self.assertNotIn('content="noindex,follow"',default)
                demo=self.client.get('/?counter-demo=1').content.decode()
                self.assertIn('data-protection-counter',demo)
                self.assertIn('data-mode="demo"',demo)
                self.assertIn('. Демонстрация',demo)
                self.assertIn('content="noindex,follow"',demo)
            with override_settings(PUBLIC_PROTECTION_COUNTER_LOADER='counter_test_reader.read'):
                real=self.client.get('/').content.decode()
                self.assertIn('data-protection-counter',real)
                self.assertIn('data-mode="reported"',real)
                self.assertNotIn('ДЕМОНСТРАЦИЯ',real)
                self.assertNotIn('ПО ОТЧЁТАМ УСТАНОВОК',real)
                self.assertNotIn('content="noindex,follow"',real)
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contract))
        with override_settings(PUBLIC_PROTECTION_COUNTER_LOADER='counter_test_reader.read'):
            browser_checks.reported_markup=Client().get('/').content.decode()
        return result.wasSuccessful()
    finally:logging.disable(old_logging)


def browser_checks(base):
    from playwright.sync_api import sync_playwright
    origin=urlsplit(base);failures=[];errors=[];outside=[]
    def check(value,message):
        if not value:raise AssertionError(message)
    def opened(browser,**opts):
        opts.setdefault('viewport',{'width':1440,'height':1000})
        ctx=browser.new_context(**opts)
        def route(handler):
            request=handler.request;url=urlsplit(request.url)
            if (url.scheme,url.netloc)!=(origin.scheme,origin.netloc) or request.method!='GET':outside.append(request.url);handler.abort()
            else:handler.continue_()
        ctx.route('**/*',route)
        page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda msg:errors.append(msg.text) if 'Content Security Policy' in msg.text else None)
        page.goto(base+'?counter-demo=1#protection-counter',wait_until='networkidle')
        page.locator('[data-protection-counter]').scroll_into_view_if_needed()
        page.wait_for_function('()=>document.querySelector("[data-protection-counter]").dataset.state==="ready"')
        return ctx,page
    def value(page):return int(page.locator('[data-protection-counter]').get_attribute('data-value'))
    def ready(page):page.wait_for_function('()=>document.querySelector("[data-protection-counter]").dataset.state==="ready"')
    def next_snapshot(page, timeout=12000):
        with page.expect_response(lambda r:'/api/public/protection-counter' in r.url,timeout=timeout) as response:
            pass
        return response.value
    def automatic_snapshots_and_offscreen(browser):
        ctx,page=opened(browser)
        count=[];page.on('request',lambda r:count.append(r.url) if '/api/public/protection-counter' in r.url else None)
        first=value(page)
        page.wait_for_function('(first)=>Number(document.querySelector("[data-protection-counter]").dataset.value)>first',arg=first,timeout=9000)
        ready(page)
        text=page.locator('.pc-section').inner_text()
        check('ДЕМОНСТРАЦИЯ' not in text and 'Синтетические' not in text,'final presentation still shows demo labels')
        check(page.locator('.pc-controls,[data-pc-toggle],[data-pc-refresh],[data-pc-reset],[data-pc-status]').count()==0,'service controls remain in final presentation')
        check('Демонстрация' in page.locator('[data-pc-number]').get_attribute('aria-label'),'accessible label lost the demo disclosure')
        check('рубеж' not in text.lower(),'removed milestone returns after an update')
        response=next_snapshot(page);ready(page)
        check(value(page)==response.json()['total'],'browser added a full snapshot as a delta')
        requests=len(count);page.evaluate('scrollTo(0,document.body.scrollHeight)');page.wait_for_timeout(250)
        page.wait_for_timeout(5500)
        check(len(count)==requests,'offscreen counter kept polling')
        check(page.locator('.pc-section').evaluate('e=>e.getAnimations({subtree:true}).length')==0,'offscreen animation kept running')
        ctx.close()
    def static_and_responsive(browser):
        for width in (320,390,768,1024,1440,2658):
            requests=[]
            ctx,page=opened(browser,viewport={'width':width,'height':1050},reduced_motion='reduce')
            page.on('request',lambda r:requests.append(r.url) if '/api/public/protection-counter' in r.url else None)
            for theme in ('dark','light'):
                if (page.locator('html').get_attribute('data-theme') or 'dark')!=theme:page.locator('[data-theme-toggle]').click()
                check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),str(width)+' overflow')
                check(page.locator('[data-pc-milestone]').count()==0,'milestone label remains in markup')
                if width>=1440:check(page.locator('[data-pc-number]').evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')<=140.1,'counter figure oversized again')
                check(page.locator('.pc-section').evaluate('e=>e.getAnimations({subtree:true}).length')==0,'reduced-motion animates')
                check(page.locator('.pc-section').get_attribute('data-auto')=='false','reduced-motion autoplays')
            held=value(page);count=len(requests);page.wait_for_timeout(5500)
            check(value(page)==held and len(requests)==count,'reduced-motion kept polling')
            ctx.close()
        ctx=browser.new_context(java_script_enabled=False)
        page=ctx.new_page();page.goto(base+'?counter-demo=1',wait_until='networkidle')
        check('9 984' in page.locator('[data-pc-number]').inner_text(),'no-JS number missing')
        check(page.locator('.pc-controls').count()==0,'no-JS dead controls visible');ctx.close()
    def unavailable_and_large_snapshot(browser):
        ctx,page=opened(browser,viewport={'width':390,'height':1050},reduced_motion='reduce')
        previous=value(page)
        ctx.close()
        # A visitor has no manual retry: the automatic loop must recover alone.
        ctx=browser.new_context(viewport={'width':390,'height':1050})
        state={'abort':True,'data':None}
        def router(handler):
            request=handler.request;url=urlsplit(request.url)
            if (url.scheme,url.netloc)!=(origin.scheme,origin.netloc) or request.method!='GET':outside.append(request.url);handler.abort()
            elif '/api/public/protection-counter' in request.url:
                handler.abort() if state['abort'] else handler.fulfill(status=200,content_type='application/json',body=json.dumps(state['data']))
            else:handler.continue_()
        ctx.route('**/*',router)
        page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base+'?counter-demo=1',wait_until='domcontentloaded')
        page.locator('.pc-section').scroll_into_view_if_needed()
        page.wait_for_function('()=>document.querySelector(".pc-section").classList.contains("is-error")',timeout=20000)
        check(previous>0,'initial server-rendered value lost before the failure')
        state['abort']=False
        total=8888888888888888
        state['data']={'total':total,'mode':'demo','revision':'test-large','updated_at':datetime.now(timezone.utc).isoformat(),'poll_after_ms':3000}
        page.wait_for_function('(total)=>document.querySelector("[data-protection-counter]").dataset.value===String(total)',arg=total,timeout=25000)
        check(value(page)==total,'large full total not represented exactly')
        check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'large total overflows mobile')
        # A newer correction is a new absolute snapshot, not a max()/local offset.
        state['data']['total']=12000;state['data']['revision']='test-correction';state['data']['updated_at']=datetime.now(timezone.utc).isoformat()
        page.wait_for_function('()=>document.querySelector("[data-protection-counter]").dataset.value==="12000"',timeout=15000)
        ctx.close()
    def reported_mode_uses_same_ui(browser):
        # Real-mode HTML comes from the DB-loader integration test, not a hand-
        # edited clone. API responses here are controlled test snapshots only.
        ctx=browser.new_context(viewport={'width':1440,'height':1000})
        data={'total':158020,'mode':'reported','revision':'fixture-r1',
              'updated_at':datetime(2026,1,1,tzinfo=timezone.utc).isoformat(),'poll_after_ms':5000}
        def route(handler):
            request=handler.request;url=urlsplit(request.url)
            if (url.scheme,url.netloc)!=(origin.scheme,origin.netloc) or request.method!='GET':outside.append(request.url);handler.abort()
            elif '/api/public/protection-counter' in request.url:handler.fulfill(status=200,content_type='application/json',body=json.dumps(data))
            elif url.path=='/':handler.fulfill(status=200,content_type='text/html',body=browser_checks.reported_markup)
            else:handler.continue_()
        ctx.route('**/*',route)
        page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base+'#protection-counter',wait_until='networkidle');page.locator('.pc-section').scroll_into_view_if_needed();ready(page)
        check(value(page)==158020 and page.locator('.pc-section').get_attribute('data-mode')=='reported','DB configuration did not reuse the real-mode UI')
        check(page.locator('.pc-controls,[data-pc-toggle],[data-pc-refresh],[data-pc-reset],[data-pc-status]').count()==0,'real source gained demo/service controls')
        check(page.locator('.pc-section').get_attribute('data-stale')=='true','old reported snapshot advertised as fresh')
        data['total']=158099;data['revision']='fixture-r2';data['updated_at']=datetime.now(timezone.utc).isoformat()
        page.wait_for_function('()=>document.querySelector("[data-protection-counter]").dataset.value==="158099"',timeout=15000)
        check(value(page)==158099,'real snapshot was added as a delta')
        check(page.locator('.pc-section').get_attribute('data-stale')=='false','fresh reported snapshot stayed stale')
        data['total']=1;data['revision']='old-response';data['updated_at']=datetime(2026,1,1,tzinfo=timezone.utc).isoformat()
        next_snapshot(page);ready(page)
        check(value(page)==158099,'older response overwrote the latest DB total')
        ctx.close()
    with sync_playwright() as p:
        browser=p.chromium.launch()
        for task in (automatic_snapshots_and_offscreen,static_and_responsive,unavailable_and_large_snapshot,reported_mode_uses_same_ui):
            try:task(browser);print('PASS',task.__name__,flush=True)
            except Exception as error:failures.append(task.__name__);print('FAIL',task.__name__,str(error),flush=True)
        browser.close()
    if errors or outside:failures.append('hygiene');print('FAIL browser hygiene',errors,outside)
    else:print('PASS local-only CSP/console/network hygiene',flush=True)
    return not failures


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:18765');parser.add_argument('--api-only',action='store_true')
    args=parser.parse_args();base=args.base_url.rstrip('/')+'/'
    if urlsplit(base).hostname not in ('localhost','127.0.0.1','::1'):return 2
    with tempfile.TemporaryDirectory(prefix='pseudex-counter-') as directory:
        api_ok=api_checks(directory)
        browser_ok=True if args.api_only else browser_checks(base)
    return int(not(api_ok and browser_ok))


if __name__=='__main__':raise SystemExit(main())
