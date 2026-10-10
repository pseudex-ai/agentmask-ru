"""Standalone offline contract checks: python -B test_acquisition_reports.py.

Only the transport is replaced; real access_token refresh and parser paths run.
No project settings, database, environment credentials or network are needed.
"""
import os
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
import socket
from unittest.mock import patch


def main():
    # Sanitize before Django initialization; do not load project settings/.env.
    clean = {key: value for key, value in os.environ.items()
             if not key.startswith(('PSEUDEX', 'YANDEX', 'DJANGO'))}
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, clean, clear=True))
        stack.enter_context(patch.object(socket.socket, 'connect', side_effect=AssertionError('network denied')))
        stack.enter_context(patch.object(socket, 'create_connection', side_effect=AssertionError('network denied')))
        import httpx
        stack.enter_context(patch.object(httpx, 'request', side_effect=AssertionError('HTTP denied')))
        from django.conf import settings
        if settings.configured:
            raise RuntimeError('Run this standalone before project Django settings are loaded')
        settings.configure(YANDEX_OAUTH_CLIENT_ID='synthetic-client',
                           YANDEX_OAUTH_CLIENT_SECRET='synthetic-secret',
                           YANDEX_OAUTH_REFRESH_TOKEN='synthetic-refresh',
                           INSTALLED_APPS=[])
        import django
        django.setup()
        from ops import acquisition_reports as reports
        from ops import yandex_api

        business = [('signup', '631841626'), ('activated', '631841723'),
                    ('key_issued', '671479127'), ('first_lease', '671479128'),
                    ('first_mask', '671479129'), ('paid', '631841775')]
        behavior = ['671474555', '671474557', '671474558', '671474591',
                    '671474592', '671474593', '671474595', '671474596']
        catalog = [{'id': goal, 'name': name, 'kind': 'business'} for name, goal in business]
        catalog += [{'id': goal, 'name': 'behavior-' + goal, 'kind': 'behavior'} for goal in behavior]
        def plan(n=14, **kwargs):
            return reports.build_report_plan('2026-10-04', '2026-10-05',
                goals=catalog[:n], campaign_ids=['715028805'], counter_id='112743085', **kwargs)

        def tsv(body, *, cost='122.00', ad='1921618436814334060', conversion='1', count=1):
            fields = []
            for field in body['params']['FieldNames']:
                fields.extend([f'Conversions_{g}_LC' for g in body['params']['Goals']]
                              if field == 'Conversions' else [field])
            values = {'Date': '2026-10-04', 'CampaignId': '715028805',
                      'AdGroupId': '42', 'AdId': ad, 'Cost': cost,
                      'Clicks': '7', 'Impressions': '100'}
            row = '\t'.join(values.get(field, conversion) for field in fields)
            return '\t'.join(fields) + '\n' + (row + '\n') * count

        calls = []
        handler = lambda body: httpx.Response(200, text=tsv(body))
        def transport(method, url, **kwargs):
            assert method == 'POST'
            if url == yandex_api.TOKEN_URL:
                assert kwargs['data']['refresh_token'] == 'synthetic-refresh'
                return httpx.Response(200, json={'access_token': 'synthetic-access', 'expires_in': 3600})
            assert url == 'https://api.direct.yandex.com/json/v501/reports'
            body, headers = kwargs['json'], kwargs['headers']
            calls.append(deepcopy(body))
            assert 'method' not in body
            assert headers['Authorization'] == 'Bearer synthetic-access'
            assert headers['returnMoneyInMicros'] == 'false'
            assert headers['skipColumnHeader'] == 'false'
            assert body['params']['IncludeVAT'] == 'YES'
            assert body['params']['AttributionModels'] == ['LC']
            assert len(body['params']['Goals']) <= 10
            assert not {'PriorityGoals', 'CostPerConversion', 'Revenue'} & set(body['params']['FieldNames'])
            return handler(body)
        stack.enter_context(patch.object(yandex_api, '_request', side_effect=transport))

        for n, sizes in [(11, [10, 1]), (14, [10, 4])]:
            p = plan(n)
            assert [len(b['params']['Goals']) for b in p['bodies']] == sizes
            result = reports.collect_reports(p)
            assert result['status'] == 'complete' and len(result['rows']) == 1
            row = result['rows'][0]
            assert row['AdId'] == '1921618436814334060'
            assert row['Cost'] == Decimal('122.00') and row['Clicks'] == Decimal(7)
            assert len([key for key in row if key.startswith('Conversions_')]) == n
            assert result['metadata']['conversion_unit'] == 'target_visits_not_organizations'
            assert result['metadata']['data_availability'] == 'not_verified'
        future = reports.build_report_plan('2026-10-04', '2026-10-04',
            goals=[{'id': str(i)} for i in range(1, 62)], campaign_ids=['99'])
        assert len(future['bodies']) == 7
        for level in ('campaign', 'adgroup', 'ad'):
            p = plan(1, level=level)
            assert reports.collect_reports(p)['status'] == 'complete'

        # Queued requests stop immediately and retain byte-equivalent JSON bodies.
        for status in (201, 202):
            p = plan()
            before = len(calls)
            handler = lambda body: httpx.Response(status, headers={'retryIn': '13', 'reportsInQueue': '5'})
            pending = reports.collect_reports(p)
            assert len(calls) == before + 1
            assert pending['status'] == 'pending' and pending['retry_in'] == 13
            assert pending['page']['report_name'] == p['bodies'][0]['params']['ReportName']
            handler = lambda body: httpx.Response(200, text=tsv(body))
            result = reports.collect_reports(p, state=pending['state'])
            assert result['status'] == 'complete'
            assert calls[before] == calls[before + 1]

        # Unknown != numeric zero; fractional attribution remains Decimal.
        for raw, expected in [('--', None), ('', None), ('0', Decimal(0)), ('0.25', Decimal('0.25'))]:
            handler = lambda body: httpx.Response(200, text=tsv(body, conversion=raw, cost=raw))
            result = reports.collect_reports(plan(1))
            assert result['status'] == 'complete'
            assert result['rows'][0]['Conversions_631841626_LC'] == expected
            assert result['rows'][0]['Cost'] == expected

        # Header only means fetched zero rows, not a failed API.
        handler = lambda body: httpx.Response(200, text=tsv(body, count=0))
        result = reports.collect_reports(plan())
        assert result['status'] == 'complete' and result['rows'] == []

        # Error handling must not look like a complete empty report.
        bad = [httpx.Response(200, json={'error': {'error_code': 58}}),
               httpx.Response(400, json={'error': {'error_code': 500}}),
               httpx.Response(429, text='rate limited'),
               httpx.Response(500, text='server error'),
               httpx.Response(200, text='<html>proxy</html>'),
               httpx.Response(200, text=''),
               httpx.Response(200, text='{}', headers={'Content-Type': 'application/json'})]
        for response in bad:
            handler = lambda body: response
            result = reports.collect_reports(plan(1))
            assert result['status'] == 'failed' and not result['fullness']['complete']
        for bad_value in ('NaN', 'Infinity', 'abc', '-1', '1,25'):
            handler = lambda body: httpx.Response(200, text=tsv(body, cost=bad_value))
            assert reports.collect_reports(plan(1))['status'] == 'failed'
        handler = lambda body: httpx.Response(200, content=b'\xff')
        assert reports.collect_reports(plan(1))['status'] == 'failed'
        def timeout(body):
            raise httpx.ReadTimeout('synthetic timeout')
        handler = timeout
        assert reports.collect_reports(plan(1))['status'] == 'failed'

        handler = lambda body: httpx.Response(200, text=tsv(body, count=2))
        result = reports.collect_reports(plan(1))
        assert result['status'] == 'incomplete' and result['rows'] == []
        assert 'duplicate_row_key' in result['issues']
        for kind in ('base', 'keys'):
            handler = lambda body: httpx.Response(200, text=tsv(body,
                cost='123.00' if len(body['params']['Goals']) == 4 and kind == 'base' else '122.00',
                ad='99' if len(body['params']['Goals']) == 4 and kind == 'keys' else '1921618436814334060'))
            result = reports.collect_reports(plan())
            assert result['status'] == 'incomplete' and result['rows'] == []
            assert 'batch_' + ('base_mismatch' if kind == 'base' else 'key_mismatch') in result['issues']

        handler = lambda body: httpx.Response(200, text=tsv(body, ad='--'))
        assert reports.collect_reports(plan(1))['issues'] == ['unknown_dimension']
        for transform in (lambda text: text.replace('Cost', 'WrongColumn'),
                          lambda text: text + 'bad\\trow\\n',
                          lambda text: text.replace('715028805', '99'),
                          lambda text: text.replace('2026-10-04', '2026-09-01')):
            handler = lambda body: httpx.Response(200, text=transform(tsv(body)))
            assert reports.collect_reports(plan(1))['status'] == 'failed'

        # Exact limit is not evidence of completeness; resume at the next offset.
        p = plan(1, page_limit=1)
        handler = lambda body: httpx.Response(200, text=tsv(body,
            count=1 if body['params']['Page']['Offset'] == 0 else 0))
        first = reports.collect_reports(p, max_requests=1)
        assert first['status'] == 'incomplete' and first['reason'] == 'request_budget'
        assert first['state']['body']['params']['Page']['Offset'] == 1
        assert first['state']['body']['params']['ReportName'] != p['bodies'][0]['params']['ReportName']
        result = reports.collect_reports(p, state=first['state'])
        assert result['status'] == 'complete' and len(result['fullness']['pages']) == 2
        assert result['rows'][0]['Cost'] == Decimal('122.00')
        # A duplicate across pages is also invalid, not a second spend row.
        handler = lambda body: httpx.Response(200, text=tsv(body,
            count=1 if body['params']['Page']['Offset'] < 2 else 0))
        assert reports.collect_reports(p)['issues'] == ['duplicate_row_key']

        def rejected(fn):
            try:
                fn()
            except ValueError:
                return
            raise AssertionError('invalid input accepted')
        rejected(lambda: reports.collect_reports(p, max_requests=6))
        rejected(lambda: reports.collect_reports(plan(1), state=first['state']))
        rejected(lambda: plan(1, page_limit=0))
        rejected(lambda: reports.build_report_plan('2026-10-01', '2026-12-01',
            goals=catalog, campaign_ids=['1']))
        rejected(lambda: reports.build_report_plan('2026-10-01', '2026-10-01',
            goals=[{'id': 631841626.0}], campaign_ids=['1']))
        rejected(lambda: reports.build_report_plan('2026-10-01', '2026-10-01',
            goals=[catalog[0], catalog[0]], campaign_ids=['1']))
        assert 'PSEUDEX_METRIKA_ID' not in os.environ
        print('acquisition_reports: all offline contract checks passed')


if __name__ == '__main__':
    main()
