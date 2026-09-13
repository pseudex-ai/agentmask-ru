"""Response headers the framework does not set for us.

Django's SecurityMiddleware covers nosniff, HSTS and the referrer policy. It has
no content security policy, and this site has two properties that make one worth
having beyond the usual: it is where a customer's credentials for a production
gateway are managed, and it must be demonstrably free of third-party beacons.
`default-src 'self'` with no reporting endpoint is that demonstration — there is
no origin the page could talk to even if something were injected into it.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    # The landing draws its diagrams inline; attributes only, never a <style>
    # block, for the same reason as the local interface.
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    # Deliberately no third party. An analytics tag here would beacon from a
    # page a logged-in customer is looking at, which is exactly the shape of
    # data flow this product exists to prevent.
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
])


_log = logging.getLogger("storefront.analytics")


class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response.setdefault("Content-Security-Policy", _POLICY)
        # Pages behind the login show a key prefix and billing detail. A shared
        # proxy holding a rendered copy is a copy nobody accounted for.
        #
        # ПУТЬ АДМИНКИ БЕРЁТСЯ ИЗ НАСТРОЙКИ, А НЕ ЛИТЕРАЛОМ. Здесь стояло
        # `/admin/`, тогда как путь вынесен в `PSEUDEX_ADMIN_PATH` намеренно —
        # «фиксированный `/admin/` первым пробует любой сканер, и перенести его
        # ничего не стоит». Стоило: перенесённая админка переставала получать
        # `no-store`, то есть ровно та настройка, которую включают ради
        # безопасности, тихо снимала заголовок со всего бэк-офиса. Операторская
        # консоль живёт там же и получает заголовок по той же строке.
        guarded = ("/app/", f"/{settings.ADMIN_PATH}/")
        if any(request.path.startswith(prefix) for prefix in guarded):
            response["Cache-Control"] = "no-store"
        return response


class AnalyticsMiddleware(MiddlewareMixin):
    """Считает визит на сервере: без куки, без JS, без чужого кода.

    ПОЧЕМУ НА СЕРВЕРЕ, А НЕ МАЯЧКОМ СО СТРАНИЦЫ. Маячок можно заблокировать
    расширением, он требует JS и он ставит куку или обращается к третьей
    стороне — то есть ровно то, чего мы обещаем не делать. Серверный счёт видит
    каждый отданный ответ и не добавляет на страницу ничего.

    ЧТО ОН НЕ УМЕЕТ, СКАЗАНО ЧЕСТНО: время на странице, глубину прокрутки и
    клики. Для лендинга B2B это не потеря — там решают визиты, источник и
    воронка до регистрации, а всё это видно из запроса.

    СЧИТАЕМ ТОЛЬКО СТРАНИЦЫ. Статика, служебные адреса и ручки API — не визиты,
    и без этого фильтра одна страница с четырьмя картинками даёт пять «визитов».

    ЗАПИСЬ НИКОГДА НЕ ЛОМАЕТ ОТВЕТ. Аналитика — не то, ради чего клиент пришёл;
    упавшая запись должна стоить нам строки в логе, а не пятисотки на лендинге.
    """

    # Пути, которые визитом не являются. Проверяется префикс — ровно потому,
    # что вложенность у статики произвольная.
    _SKIP = ("/static/", "/media/", "/healthz", "/hooks/", "/favicon",
             "/robots.txt", "/api/", "/demand")

    def process_response(self, request, response):
        try:
            self._record(request, response)
        except Exception:  # noqa: BLE001 — любая; см. докстроку
            _log.warning("не удалось записать визит", exc_info=True)
        return response

    def _record(self, request, response) -> None:
        if request.method != "GET" or response.status_code != 200:
            return
        path = request.path
        if any(path.startswith(prefix) for prefix in self._SKIP):
            return
        # Путь админки не считаем НИКОГДА: это наши собственные заходы, и они
        # завысили бы всё, что мы по этим числам решаем.
        if path.startswith(f"/{settings.ADMIN_PATH}"):
            return

        from ops import collect
        from ops.analytics_models import Funnel, Visit

        meta = request.META
        agent = meta.get("HTTP_USER_AGENT", "")
        visitor = collect.fingerprint(
            request.get_host(), collect.client_ip(meta), agent)
        is_bot = collect.looks_like_bot(agent, meta.get("HTTP_ACCEPT", ""))
        device, browser, system = collect.classify(agent)
        own = {request.get_host().split(":")[0].lower()}

        Visit.objects.create(
            visitor=visitor,
            path=path[:200],
            referrer_host=collect.referrer_host_of(meta.get("HTTP_REFERER", ""), own),
            utm_source=request.GET.get("utm_source", "")[:60],
            utm_medium=request.GET.get("utm_medium", "")[:60],
            utm_campaign=request.GET.get("utm_campaign", "")[:60],
            device=device, browser=browser, os=system, is_bot=is_bot,
        )
        # Шаг воронки ставится ОДИН РАЗ за сутки на посетителя: человек,
        # трижды открывший лендинг, не три раза вошёл в воронку.
        if path == "/" and not is_bot:
            since = timezone.now() - timedelta(days=1)
            if not Funnel.objects.filter(step=Funnel.LANDING, visitor=visitor,
                                         at__gte=since).exists():
                Funnel.objects.create(step=Funnel.LANDING, visitor=visitor)