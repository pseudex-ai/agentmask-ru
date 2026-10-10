"""Read-only daily Direct measurements; no strategy or goal writes.

Contract freshly checked against https://yandex.ru/dev/direct/doc/ru/ pages:
spec, headers, reports, fields-list, compatibility, restrictions, report-format,
codes (2026-10-10). Account configuration is caller evidence, not verified here.

Public API: build_report_plan(), parse_report_tsv(), request_report_page(),
collect_reports(). Plans and continuation state belong on the server, not in an
untrusted browser. Serialize Decimal as strings, never floats. A complete report
means the requested rows were fetched, NOT that consent, goal linkage, delayed
conversions, or billing reconciliation are complete. No ROI/CAC is inferred.

Example (catalog is supplied by the operator's configuration):
    plan = build_report_plan('2026-10-04', '2026-10-05', goals=catalog,
                             campaign_ids=['715028805'], counter_id='112743085')
    result = collect_reports(plan)
    # On pending, schedule after result['retry_in']; do not sleep in a view.
    result = collect_reports(plan, state=result['state'])

One account-wide scheduler should serialize callers and enforce <=20 requests
per 10 seconds across workers. This adapter never fans out queued reports, never
sleeps or retries automatically. Offline reports expire after five hours: discard
old continuation state and rebuild the plan for a new coherent observation.
"""
from copy import deepcopy
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import re
from uuid import uuid4

import httpx

from . import yandex_api

__all__ = ['build_report_plan', 'parse_report_tsv', 'request_report_page',
           'collect_reports']

_DIMENSIONS = {
    'campaign': ['Date', 'CampaignId'],
    'adgroup': ['Date', 'CampaignId', 'AdGroupId'],
    'ad': ['Date', 'CampaignId', 'AdGroupId', 'AdId'],
}
_BASE = ['Impressions', 'Clicks', 'Cost']
_UNKNOWN = {'', '--', '-', '—', 'N/A', 'null'}
_HEADERS = {'Accept-Language': 'en', 'processingMode': 'auto',
            'returnMoneyInMicros': 'false', 'skipReportHeader': 'true',
            'skipColumnHeader': 'false', 'skipReportSummary': 'true'}


def _id(value):
    # Reject floats even when apparently integral: precision may already be lost.
    if type(value) not in (str, int) or not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError('IDs must be positive decimal strings or exact integers')
    return str(value)


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label} must be an integer in [{low}, {high}]')
    return value


def build_report_plan(date_from, date_to, *, goals, campaign_ids,
                      counter_id=None, level='ad', attribution='LC',
                      page_limit=1000, currency=None, timezone=None):
    """Build a <=31-day plan, splitting arbitrary goal catalogs into tens.

    goals: iterable of metadata dicts with an 'id'; other keys (name, kind,
    semantics) are copied, never used to infer business outcomes. Currency and
    timezone are optional caller-verified account metadata, not guessed RUB/UTC.
    Counter ID is provenance only: Direct selects goals, not a counter parameter.
    """
    start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    if not 0 <= (end - start).days <= 30:
        raise ValueError('Use an inclusive daily window of 1 to 31 days')
    if level not in _DIMENSIONS or attribution not in {'LC', 'FCCD', 'LSCCD', 'AUTO'}:
        raise ValueError('Unsupported level or attribution')
    _integer(page_limit, 1, 100000, 'page_limit')
    catalog = [dict(goal, id=_id(goal['id'])) for goal in goals]
    ids = [goal['id'] for goal in catalog]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Supply a nonempty goal catalog with unique IDs')
    campaigns = [_id(value) for value in campaign_ids]
    if not campaigns or len(campaigns) > 10000 or len(set(campaigns)) != len(campaigns):
        raise ValueError('Supply 1..10000 unique campaign IDs')
    dimensions = _DIMENSIONS[level][:]
    nonce = uuid4().hex
    bodies = []
    for index in range(0, len(ids), 10):
        params = {
            'SelectionCriteria': {'DateFrom': start.isoformat(), 'DateTo': end.isoformat(),
                                  'Filter': [{'Field': 'CampaignId', 'Operator': 'IN',
                                              'Values': campaigns}]},
            'Goals': ids[index:index + 10], 'AttributionModels': [attribution],
            'FieldNames': dimensions + _BASE + ['Conversions'],
            'Page': {'Limit': page_limit, 'Offset': 0},
            'OrderBy': [{'Field': field, 'SortOrder': 'ASCENDING'} for field in dimensions],
            'ReportName': f'acquisition-{nonce}-{index // 10}-0',
            'ReportType': 'CUSTOM_REPORT', 'DateRangeType': 'CUSTOM_DATE',
            'Format': 'TSV', 'IncludeVAT': 'YES',
        }
        bodies.append({'params': params})
    return {'bodies': bodies, 'dimensions': dimensions, 'goals': deepcopy(catalog),
            'metadata': {'counter_id': _id(counter_id) if counter_id is not None else None,
                         'campaign_ids': campaigns, 'date_from': start.isoformat(),
                         'date_to': end.isoformat(), 'level': level,
                         'attribution': attribution, 'currency': currency,
                         'timezone': timezone, 'vat': 'gross', 'money_unit': 'currency',
                         'conversion_unit': 'target_visits_not_organizations',
                         'data_availability': 'not_verified',
                         'lag': 'Metrika matching may lag by several hours',
                         'roi_supported': False}}


def _columns(body):
    params = body['params']
    return [column for field in params['FieldNames']
            for column in ([f'Conversions_{goal}_{model}' for goal in params['Goals']
                            for model in params['AttributionModels']]
                           if field == 'Conversions' else [field])]


def _number(raw):
    if raw in _UNKNOWN:
        return None
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', raw):
        raise ValueError('Malformed numeric report value')
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError('Malformed numeric report value') from None
    if not value.is_finite():
        raise ValueError('Non-finite report value')
    return value


def parse_report_tsv(text, body):
    """Parse the exact header-bearing TSV requested by this adapter.

    Unknown cells remain None; actual zero remains Decimal('0'). Header-only is
    a valid empty page. Missing columns, malformed numbers and non-TSV fail.
    Duplicate keys are retained for the collector to mark incomplete, not summed.
    """
    expected = _columns(body)
    reader = csv.reader(io.StringIO(text.lstrip('\ufeff')), delimiter='\t', strict=True)
    try:
        header = next(reader, None)
        if header is None or len(header) != len(set(header)) or set(header) != set(expected):
            raise ValueError('Missing or unexpected TSV columns')
        rows = []
        for cells in reader:
            if len(cells) != len(header):
                raise ValueError('Malformed TSV row width')
            row = {}
            for field, raw in zip(header, cells):
                if field == 'Date':
                    parsed = date.fromisoformat(raw)
                    criteria = body['params']['SelectionCriteria']
                    if raw != parsed.isoformat() or not criteria['DateFrom'] <= raw <= criteria['DateTo']:
                        raise ValueError('Report date outside requested window')
                    row[field] = raw
                elif field.endswith('Id'):
                    row[field] = None if raw in _UNKNOWN else _id(raw)
                    if field == 'CampaignId':
                        filters = body['params']['SelectionCriteria']['Filter']
                        campaigns = next(f['Values'] for f in filters if f['Field'] == field)
                        if row[field] is not None and row[field] not in campaigns:
                            raise ValueError('Report campaign outside requested scope')
                else:
                    row[field] = _number(raw)
            rows.append(row)
    except csv.Error:
        raise ValueError('Malformed TSV encoding') from None
    if len(rows) > body['params']['Page']['Limit']:
        raise ValueError('Report exceeds requested page limit')
    return rows


def _header_int(headers, name):
    raw = headers.get(name)
    return int(raw) if raw is not None and re.fullmatch(r'[0-9]{1,9}', raw) else None


def request_report_page(body):
    """One Reports POST using server-held auth; no refresh/poll retry loop.

    Returns complete/pending/failed, safe status metadata and original request
    body/name (not credentials). An error body is never mistaken for zero rows.
    """
    result = {'body': deepcopy(body), 'report_name': body['params']['ReportName'],
              'rows': [], 'retry_in': None, 'reports_in_queue': None}
    try:
        response = yandex_api._request(
            'POST', f'{yandex_api.DIRECT_API}/reports', json=deepcopy(body),
            headers=dict(_HEADERS, Authorization=f'Bearer {yandex_api.access_token()}'))
    except (yandex_api.YandexError, httpx.HTTPError) as exc:
        return dict(result, status='failed', error='authentication_or_transport',
                    http_status=getattr(exc, 'status', None))
    result.update(http_status=response.status_code,
                  request_id=response.headers.get('RequestId'),
                  retry_in=_header_int(response.headers, 'retryIn'),
                  reports_in_queue=_header_int(response.headers, 'reportsInQueue'))
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and ('error' in payload or 'errors' in payload):
        # Do not echo server error strings: they may contain request credentials.
        error = payload.get('error')
        code = error.get('error_code') if isinstance(error, dict) else None
        return dict(result, status='failed', error='api_error', error_code=code)
    if response.status_code in (201, 202):
        return dict(result, status='pending')
    if response.status_code != 200:
        return dict(result, status='failed', error='http_error')
    content_type = response.headers.get('Content-Type', '').lower()
    if 'json' in content_type or 'html' in content_type or 'xml' in content_type:
        return dict(result, status='failed', error='not_tsv')
    try:
        rows = parse_report_tsv(response.content.decode('utf-8'), body)
    except (ValueError, UnicodeError):
        return dict(result, status='failed', error='invalid_tsv')
    return dict(result, status='complete', rows=rows)


def _fingerprint(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _merge(plan, batches):
    indexed, problems = [], []
    for batch in batches:
        index = {}
        for row in batch:
            key = tuple(row[field] for field in plan['dimensions'])
            if None in key:
                problems.append('unknown_dimension')
            if key in index:
                problems.append('duplicate_row_key')
            else:
                index[key] = row
        indexed.append(index)
    keys = set(indexed[0])
    if any(set(index) != keys for index in indexed[1:]):
        problems.append('batch_key_mismatch')
    joined = []
    for key in indexed[0]:
        row = deepcopy(indexed[0][key])
        for index in indexed[1:]:
            other = index.get(key)
            if other is None:
                continue
            if any(row[field] != other[field] for field in _BASE):
                problems.append('batch_base_mismatch')
            row.update({field: value for field, value in other.items()
                        if field.startswith('Conversions_')})
        joined.append(row)
    # Fail closed: inconsistent pages/batches are evidence, not publishable totals.
    return ([] if problems else joined), sorted(set(problems))


def collect_reports(plan, *, state=None, max_requests=5):
    """Fetch sequential pages/batches with a bounded request budget (1..5).

    Resume with the returned state after pending or request_budget. State includes
    exact pending body/name and all accumulated rows (Decimal); persist server-side.
    Stop on the FIRST queued report: at most one outstanding report per collection.
    This cannot police unrelated clients' queue/rate usage; use one scheduler.
    Full pages require another page, including a final header-only page when exact.
    Rows are published only after all pages and batches join consistently.
    """
    _integer(max_requests, 1, 5, 'max_requests')
    fingerprint = _fingerprint(plan)
    if state is None:
        state = {'fingerprint': fingerprint, 'batch': 0,
                 'body': deepcopy(plan['bodies'][0]),
                 'batches': [[] for _ in plan['bodies']], 'pages': []}
    else:
        state = deepcopy(state)
        if state.get('fingerprint') != fingerprint:
            raise ValueError('Continuation does not belong to this report plan')
    metadata = deepcopy(plan['metadata'])
    def finish(status, reason=None, page=None):
        rows, problems = ([], [])
        if status == 'complete':
            rows, problems = _merge(plan, state['batches'])
            if problems:
                status, reason = 'incomplete', 'inconsistent_join'
        return {'status': status, 'reason': reason, 'rows': rows,
                'issues': problems, 'metadata': metadata, 'goals': deepcopy(plan['goals']),
                'fullness': {'complete': status == 'complete', 'pages': deepcopy(state['pages']),
                             'batches_complete': state['batch'],
                             'batches_total': len(plan['bodies'])},
                'retry_in': (page or {}).get('retry_in'), 'page': page,
                'state': state if status in ('pending', 'incomplete') and not problems else None}
    if state['batch'] >= len(plan['bodies']):
        return finish('complete')
    for _ in range(max_requests):
        page = request_report_page(state['body'])
        if page['status'] != 'complete':
            return finish(page['status'], page.get('error'), page)
        rows = page['rows']
        params = state['body']['params']
        state['pages'].append({'report_name': params['ReportName'],
                               'offset': params['Page']['Offset'],
                               'limit': params['Page']['Limit'], 'rows': len(rows),
                               'request_id': page.get('request_id')})
        state['batches'][state['batch']].extend(rows)
        if len(rows) == params['Page']['Limit']:
            params['Page']['Offset'] += len(rows)
            base_name = plan['bodies'][state['batch']]['params']['ReportName'].rsplit('-', 1)[0]
            params['ReportName'] = f"{base_name}-{params['Page']['Offset']}"
        else:
            state['batch'] += 1
            if state['batch'] == len(plan['bodies']):
                return finish('complete')
            state['body'] = deepcopy(plan['bodies'][state['batch']])
    return finish('incomplete', 'request_budget')
