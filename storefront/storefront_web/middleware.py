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
from django.http import HttpResponsePermanentRedirect
from django.urls import is_valid_path
from django.utils import timezone
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

# ГРАНИЦА «КОМУ МОЖНО СЧИТАТЬ» СПРАШИВАЕТСЯ, А НЕ ПОВТОРЯЕТСЯ. Здесь стояла своя
# копия условия (`/app/` и админка), и она уже разошлась с шаблоном: в шаблоне
# исключены ещё `/accounts/`, `/activate` и `/welcome`. Расхождение молчаливое и
# в опасную сторону — страница с секретом в адресе получала бы разрешение в
# заголовке, даже когда счётчика на ней нет.
from pseudex_site.context import counters_allowed

def _policy_for(request) -> str:
    """CSP, РАЗНЫЙ ДЛЯ ПУБЛИЧНОЙ СТРАНИЦЫ И ДЛЯ КАБИНЕТА.

    Здесь стояла одна строка на весь сайт и комментарий, объясняющий, почему в
    ней нет третьих сторон: «маячок со страницы, на которую смотрит залогиненный
    клиент, — ровно та форма потока данных, которую продукт предотвращает».
    Довод верен и остаётся в силе — но он про КАБИНЕТ, а не про лендинг.

    Продуктовая аналитика живёт на НАШЕМ домене и нужна ровно там, где решается
    «почему не зарегистрировались»: на публичных страницах. В кабинете её нет и
    не будет: там на экране префиксы ключей и суммы счетов, и запись сессии
    сделала бы их копию, которую никто не заказывал. Что делают КЛИЕНТЫ, мы
    знаем из своих же серверных событий — каждое действие в кабинете это POST.

    ЯНДЕКС.МЕТРИКА — ЕДИНСТВЕННАЯ ТРЕТЬЯ СТОРОНА, КОТОРУЮ ЭТОТ ФАЙЛ ПУСКАЕТ, и
    пускает по тому же признаку: публичная страница. В кабинете её нет даже
    когда счётчик настроен, — и это не обещание, а заголовок, который браузер
    исполняет. Проверяется тестом с обеих сторон: тег не отдаётся на `/app/`, и
    CSP для `/app/` не содержит `mc.yandex.ru`.
    """
    analytics = settings.ANALYTICS
    if not counters_allowed(request.path):
        return _POLICY

    # ЧТО ИМЕННО РАЗРЕШЕНО ЭТОЙ СТРАНИЦЕ. Список СОБИРАЕТСЯ, а не выбирается:
    # Rybbit и Метрика включаются порознь, и публичная страница может нести оба
    # счётчика, один или ни одного. Прежняя развилка «режим off — не пускать
    # ничего» сломала бы ровно этот случай: Метрика при выключенном Rybbit не
    # получила бы разрешения и молча не грузилась, а страница при этом честно
    # говорила бы, что счётчик есть.
    origins: list[str] = []
    if analytics["mode"] != "off":
        origins.append(analytics["host"].rstrip("/"))
    if settings.METRIKA_ID:
        # `mc.yandex.ru` — и источник скрипта, и приёмник данных: тег грузится
        # оттуда и туда же шлёт визит. В `img-src` он нужен для пикселя в
        # `<noscript>`, который считается, когда скрипты выключены.
        #
        # `yastatic.net` — из общего списка адресов в справке о CSP: часть
        # ресурсов счётчика отдаётся оттуда, и без него они отваливаются так же
        # молча, как и blob-фрейм Вебвизора.
        origins.append("https://mc.yandex.ru")
        origins.append("https://yastatic.net")
    if not origins:
        return _POLICY

    allowed = " ".join(origins)
    metrika_img = " https://mc.yandex.ru" if settings.METRIKA_ID else ""
    policy = "; ".join(
        part + (f" {allowed}" if part.startswith(("script-src ", "connect-src "))
                else metrika_img if part.startswith("img-src ") else "")
        for part in _POLICY.split("; ")
    )
    # ВЕБВИЗОР НЕ ЗАРАБОТАЛ БЫ БЕЗ ЭТИХ ДВУХ ДИРЕКТИВ, И ЭТО НЕ ДОГАДКА:
    # справка Метрики «Установка счётчика на сайт с CSP» перечисляет их
    # отдельным пунктом — «для правильной работы Вебвизора, карт кликов, ссылок
    # и скроллинга». Вебвизор собирает запись в blob-iframe, а `default-src
    # 'self'` его не пускает: отказ при этом молчаливый — запись просто не
    # появляется, и искать причину будут в панели Метрики, а не в заголовке.
    #
    # `yastatic.net` — из того же списка адресов: часть ресурсов счётчика
    # отдаётся оттуда. Разрешение узкое — `blob:` и один хост, — и только на
    # публичных страницах со счётчиком.
    #
    # `frame-ancestors 'none'` ОСТАВЛЕН, хотя справка называет и его. Он
    # запрещает встраивать НАШУ страницу в чужой фрейм, и это защита от
    # кликджекинга формы регистрации. Справка перечисляет директивы общим
    # списком «для правильной работы»; если запись окажется неполной, начинать
    # надо отсюда — но ослаблять защиту до того, как она помешала, не за что.
    if settings.METRIKA_ID:
        policy += ("; child-src blob: https://mc.yandex.ru"
                   "; frame-src blob: https://mc.yandex.ru")
    return policy


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
    # РЕДИРЕКТ ПОСЛЕ ОТПРАВКИ ФОРМЫ — ТОЖЕ `form-action`, И ЭТО НЕ ОЧЕВИДНО.
    # Форма уходит на свой origin (можно), сервер отвечает 302 на страницу оплаты
    # провайдера, и браузер проверяет ЦЕЛЬ ПЕРЕНАПРАВЛЕНИЯ по тому же списку. С
    # одним `'self'` он её режет: POST уходит, 302 приходит, навигация
    # отменяется — человек видит «нажал, страница просто обновилась», а в
    # консоли «Sending form data to … violates form-action 'self'». Так была
    # недоступна оплата картой во всём кабинете.
    #
    # Домены провайдера, а не произвольные: это ровно те страницы, куда ЮKassa
    # уводит плательщика (checkout), и ничего больше.
    "form-action 'self' https://yoomoney.ru https://yookassa.ru",
    "frame-ancestors 'none'",
    "base-uri 'none'",
])


_log = logging.getLogger("storefront.analytics")


class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response.setdefault("Content-Security-Policy", _policy_for(request))
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


class TrailingSlashRedirectMiddleware(MiddlewareMixin):
    """`/detection/` → `/detection`: слэш на конце публичного адреса — это 404.

    ЗАЧЕМ. Публичные страницы объявлены БЕЗ слэша (`urls.py`: `path("detection",
    …)`), и таков же их канонический адрес и адрес в карте сайта. Джанго умеет
    слэш ДОБАВЛЯТЬ (`APPEND_SLASH`), но не убирать: `/detection/` не совпадает ни
    с одним маршрутом и отдаёт 404. Человек, скопировавший адрес из письма со
    слэшем, и внешняя ссылка со слэшем получают «страницы нет» — а на этом сайте
    каждый 404 ещё и кормит счётчик fail2ban, который банит по 404 на уровне
    пакетов (`deploy/fail2ban/`). То есть слэш стоил не только посетителя.

    ПОЧЕМУ MIDDLEWARE, А НЕ СПИСОК ПУТЕЙ. Список пришлось бы держать в согласии с
    `urls.py`, и он бы разошёлся молча. Общее правило «срезать слэш у всего» тоже
    не годится: на сайте есть `app/`, `accounts/login/` и админка, объявленные СО
    слэшем, и такое правило сломало бы их НАСМЕРТЬ — `/accounts/login/` →
    `/accounts/login` → `APPEND_SLASH` вернул бы слэш → бесконечный редирект.
    Здесь решение принимается по факту, а не по списку: срезаем только тогда,
    когда адрес без слэша ДЕЙСТВИТЕЛЬНО существует.

    ТРИ УСЛОВИЯ, И КАЖДОЕ ЗАКРЫВАЕТ СВОЮ ОШИБКУ:

      * ТОЛЬКО 404. Счастливый путь не платит даже за разрешение URL, а петля
        становится невозможной по построению: цель редиректа отвечает, а не
        отдаёт 404, поэтому второй раз сюда не придёт. `APPEND_SLASH` отправил бы
        нас в обратную сторону и столкнулся бы с этим же правилом — а ему на
        вход приходит адрес БЕЗ слэша, который сюда не заходит вовсе.
      * ЦЕЛЬ ОБЯЗАНА РАЗРЕШАТЬСЯ (`is_valid_path`). `/accounts/login/` и `/app/`
        разрешаются сами — их 404 не бывает, — а `/wp-admin/` не разрешается ни в
        каком виде и остаётся честным 404, как и было.
      * ТОЛЬКО GET/HEAD. 301 на POST браузеры и клиенты переигрывают как GET, и
        конфигуратор (`/demand`) потерял бы тело запроса. Метод решает, а не путь.

    КАКОЙ ЦЕНОЙ. Для ЧАСТНЫХ адресов вида `/app/invoices/<номер>/` с несуществующим
    номером получится 301 на адрес, который тоже отдаёт 404. Вреда нет — страница
    закрыта от индексации и ссылок на неё нет, — но назвать это надо, потому что
    «редирект в никуда» звучит как дефект, и следующий читатель имеет право знать,
    что он измерен и признан безобидным.
    """

    def process_response(self, request, response):
        if response.status_code != 404 or request.method not in ("GET", "HEAD"):
            return response
        path = request.path
        # Корень сайта слэш не «заканчивает» — он им является.
        if not path.endswith("/") or path == "/":
            return response
        target = path.rstrip("/")
        if not target or not is_valid_path(target):
            return response
        query = request.META.get("QUERY_STRING", "")
        return HttpResponsePermanentRedirect(f"{target}?{query}" if query else target)


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
            # ИДЕНТИФИКАТОР КЛИКА ПО ОБЪЯВЛЕНИЮ. Берётся из того же места, что и
            # метки, и по той же причине: он приходит на лендинг, а конверсия
            # случается страницей позже — на той, где счётчика нет и быть не
            # может. Без него офлайн-конверсию не к чему привязать.
            yclid=request.GET.get("yclid", "")[:64],
            device=device, browser=browser, os=system, is_bot=is_bot,
        )
        # Шаг воронки ставится ОДИН РАЗ за сутки на посетителя: человек,
        # трижды открывший лендинг, не три раза вошёл в воронку.
        if path == "/" and not is_bot:
            since = timezone.now() - timedelta(days=1)
            if not Funnel.objects.filter(step=Funnel.LANDING, visitor=visitor,
                                         at__gte=since).exists():
                Funnel.objects.create(step=Funnel.LANDING, visitor=visitor)