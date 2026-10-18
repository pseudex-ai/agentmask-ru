"""Public aggregate snapshots, never a browser bridge to the licensing admin API.

The demo and a future approved DB reader implement the SAME complete-snapshot
contract. No request increments a stored total. The real reader is opt-in and
must aggregate eligible installations correctly; exposing the existing private
fleet metric unchanged would inherit its reset/replay/self-check ambiguities.
"""
from datetime import datetime, timezone
import hashlib
import logging
import time
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.urls import reverse
from django.utils.module_loading import import_string
from django.views.decorators.http import require_GET

_log = logging.getLogger(__name__)
POLL_MS = 5000
DEMO_SEED = 9984
DEMO_PACKETS = (32, 74, 19, 108, 46, 63, 27, 91)
MAX_TOTAL = 2**53 - 1  # JavaScript must represent the received integer exactly.


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def _unavailable():
    return {'total': None, 'updated_at': None, 'revision': None,
            'mode': 'unavailable', 'poll_after_ms': 15000}


def _demo_snapshot(query, now):
    # A shared epoch in the URL makes the demo deterministic across processes.
    # Bounded, read-only arithmetic; no sessions, DB writes, or customer data.
    try:
        started = int(query.get('started', int(now)))
        advance = int(query.get('advance', '0'))
    except (KeyError, TypeError, ValueError):
        raise ValueError('invalid_demo_parameters') from None
    if not now - 3600 <= started <= now + 2 or not 0 <= advance <= 10000:
        raise ValueError('invalid_demo_parameters')
    ticks = max(0, int(now - started)) // (POLL_MS // 1000) + advance
    cycles, tail = divmod(ticks, len(DEMO_PACKETS))
    total = DEMO_SEED + cycles * sum(DEMO_PACKETS) + sum(DEMO_PACKETS[:tail])
    return {'total': total, 'updated_at': _iso(now),
            'revision': f'demo:{started}:{ticks}', 'mode': 'demo', 'poll_after_ms': POLL_MS,
            'demo_started_at': started}


def _reported_snapshot():
    """Read an approved DB aggregate through one server-side selector.

    Configure PSEUDEX_PUBLIC_COUNTER_LOADER to a zero-argument dotted callable.
    Return total, updated_at (aware datetime), and a stable snapshot revision.
    Extra fields are discarded. This module deliberately imports no private
    licensing client and does not infer a values total from billed requests.
    """
    configured = getattr(settings, 'PUBLIC_PROTECTION_COUNTER_LOADER', '')
    if not configured:
        return _unavailable()
    identity = configured if isinstance(configured, str) else repr(configured)
    key = 'public:protection-counter:v1:' + hashlib.sha256(identity.encode()).hexdigest()[:20]
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
        loader = import_string(configured) if isinstance(configured, str) else configured
        record = loader()
        if record is None:
            missing = _unavailable()
            cache.set(key, missing, timeout=POLL_MS // 1000)
            return missing
        total, updated, revision = record['total'], record['updated_at'], record['revision']
        if type(total) is not int or not 0 <= total <= MAX_TOTAL:
            raise ValueError('invalid total')
        if not isinstance(updated, datetime) or updated.utcoffset() is None:
            raise ValueError('updated_at must be timezone-aware')
        if not isinstance(revision, str) or not 1 <= len(revision) <= 80:
            raise ValueError('invalid revision')
        snapshot = {'total': total, 'updated_at': updated.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'revision': revision, 'mode': 'reported', 'poll_after_ms': POLL_MS}
    except Exception:
        _log.warning('Public protection counter snapshot unavailable', exc_info=True)
        missing = _unavailable()
        try:
            cache.set(key, missing, timeout=POLL_MS // 1000)
        except Exception:
            pass  # A cache outage must not turn the marketing page into a 500.
        return missing
    # One small sanitized aggregate, not a cache key for each browser/tenant.
    try:
        cache.set(key, snapshot, timeout=POLL_MS // 1000)
    except Exception:
        _log.warning('Public protection counter cache unavailable', exc_info=True)
    return snapshot


@require_GET
def snapshot(request):
    if request.GET.get('demo') == '1':
        try:
            data = _demo_snapshot(request.GET, time.time())
        except ValueError:
            response = JsonResponse({'error': 'invalid_demo_parameters'}, status=400)
        else:
            response = JsonResponse(data)
    else:
        data = _reported_snapshot()
        response = JsonResponse(data, status=503 if data['total'] is None else 200)
    # Browsers ask for the current snapshot; server-side caching caps DB load.
    response['Cache-Control'] = 'no-store'
    response['X-Robots-Tag'] = 'noindex'
    return response


def page_context(request):
    """Owner preview only until an approved real source is configured.

    The homepage block is intentionally off while the customer base is small:
    no markup, CSS, JS or polling is sent to visitors. It appears automatically
    once PSEUDEX_PUBLIC_COUNTER_LOADER is set to a real aggregate, or on the
    explicit ?counter-demo=1 preview page.
    """
    preview = request.GET.get('counter-demo') == '1'
    configured = bool(getattr(settings, 'PUBLIC_PROTECTION_COUNTER_LOADER', ''))
    if not preview and not configured:
        return {}
    demo = preview and not configured
    endpoint = reverse('public_protection_counter')
    if demo:
        started = int(time.time())
        endpoint += '?' + urlencode({'demo': '1', 'started': started})
        initial = DEMO_SEED
    else:
        initial = _reported_snapshot()['total']
    return {'protection_counter': {'demo': demo, 'preview': preview, 'endpoint': endpoint,
                                   'initial': initial,
                                   'initial_display': f'{initial:,}'.replace(',', ' ') if initial is not None else '—'}}
