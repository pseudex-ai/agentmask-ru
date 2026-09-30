"""Машинный доступ к данным Яндекса: JSON под отдельным токеном.

ПОЧЕМУ ОТДЕЛЬНЫЙ ТОКЕН, А НЕ СЕССИЯ ОПЕРАТОРА. Экраны консоли закрыты
`staff` + подтверждённым TOTP — это верно для человека и неприменимо к боту: у
бота нет ни пароля, ни второго фактора, а завести ему staff-аккаунт значило бы
выдать весь биллинг и все персональные данные клиентов ради одной сводки.
`PSEUDEX_OPS_API_TOKEN` открывает РОВНО то, что перечислено в `urls.py` под
`_ops_api_gate`, — четыре читающих эндпоинта о рекламе и статистике.

ЧТО ЗДЕСЬ ЧИТАЮЩЕЕ И ЧТО ЭТО ЗНАЧИТ. Ни одного метода, меняющего состояние ни у
нас, ни в Яндексе. Токен, попавший не в те руки, показывает цифры посещаемости
и список кампаний — это неприятно и это не «выключили продукт клиенту».
Управляющие вызовы Директа появятся отдельно и потребуют отдельного решения.

ПЕРСОНАЛЬНЫХ ДАННЫХ ЗДЕСЬ НЕТ ПО УСТРОЙСТВУ. Метрика отдаёт агрегаты, а не
посетителей: `ym:s:visits` — число, `ym:s:lastSignTrafficSource` — название
канала. Ни IP, ни client_id, ни `ym:s:userID` в ответы не попадают, потому что
ни один из них не запрашивается. Это не фильтр поверх ответа — это отсутствие
запроса, и разница между ними в том, что первое можно забыть обновить.
"""

import hmac
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ops import yandex_api


def _ops_api_gate(view):
    """Bearer-токен, сравнение постоянного времени, отказ по умолчанию.

    ПУСТОЙ `OPS_API_TOKEN` ЗАКРЫВАЕТ ДВЕРЬ, А НЕ ОТКРЫВАЕТ ЕЁ. Сравнение с
    пустой строкой прошло бы у запроса без заголовка, и незаданная настройка
    превратилась бы в открытый эндпоинт — то есть «не настроено» стало бы
    «доступно всем». Отсюда явная проверка на пустоту до сравнения.
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        expected = settings.OPS_API_TOKEN
        supplied = ""
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            supplied = header[len("Bearer "):].strip()
        if not expected or not hmac.compare_digest(supplied, expected):
            return JsonResponse(
                {"error": "unauthorized",
                 "hint": "Authorization: Bearer <PSEUDEX_OPS_API_TOKEN>"},
                status=401,
            )
        return view(request, *args, **kwargs)
    return wrapper


def _days(request, default: int = 30) -> int:
    """Окно отчёта, ограниченное сверху. Год — предел, а не вкус.

    Метрика считает по дням и на большом окне отвечает заметно дольше; запрос
    «за всё время» от бота, который ошибся в параметре, — это запрос, из-за
    которого бот ждёт минуту и падает по таймауту.
    """
    try:
        value = int(request.GET.get("days", default))
    except (TypeError, ValueError):
        value = default
    return max(1, min(365, value))


@_ops_api_gate
@require_GET
def metrika_counters(request):
    """Список счётчиков. Дешёвая проверка «токен жив» для бота и для меня.

    `site` у Метрики — СТРОКА С ДОМЕНОМ, а не объект. Первая версия читала
    `site.domain`; на настоящем ответе это падало, и поймано было только живым
    обращением — выдуманный ответ выглядел правдоподобно.
    """
    return JsonResponse({"counters": [
        {"id": str(c.get("id", "")), "name": c.get("name", ""),
         "site": c.get("site", ""),
         "status": c.get("status", "")}
        for c in yandex_api.counters()
    ]})


@_ops_api_gate
@require_GET
def metrika_summary(request):
    """Итоги за окно плюс разрез по источникам.

    ИСТОЧНИКИ ИДУТ ВМЕСТЕ С ИТОГАМИ, А НЕ ОТДЕЛЬНЫМ ЭНДПОИНТОМ. «Пришло 400»
    без «откуда» не отвечает ни на один вопрос, ради которого сюда заходят; а
    два запроса вместо одного — это два окна, которые могут не совпасть на
    границе суток, и тогда цифры в отчёте не сходятся между собой.

    СЧИТАЕТ НЕ ЭТОТ ФАЙЛ, А `yandex_api.metrika_summary`, И ЭТО НЕ ЛЕНЬ. Ту же
    сводку печатает недельный отчёт в бота; вторая реализация тех же двух
    запросов разошлась бы с первой молча — и разошлась бы ровно тогда, когда
    кто-то поправит запрос в одном из двух мест.
    """
    days = _days(request)
    if not settings.METRIKA_ID:
        return JsonResponse(
            {"error": "no_counter",
             "hint": "PSEUDEX_METRIKA_ID не задан — статистики не будет "
                     "даже с рабочим токеном."},
            status=409,
        )
    return JsonResponse(yandex_api.metrika_summary(days))


@_ops_api_gate
@require_GET
def direct_campaigns(request):
    """Кампании Директа: состояние и расход.

    ОШИБКА 58 ОТДАЁТСЯ КАК 409, А НЕ КАК 500. «Заявку на доступ ещё не
    одобрили» — это не поломка, а ожидаемое состояние первые семь дней, и
    бот, который на 500 кричит «всё сломалось», кричит это каждое утро неделю.
    Отдельный код даёт ему возможность промолчать.
    """
    try:
        campaigns = yandex_api.direct_campaigns()
    except yandex_api.YandexError as error:
        not_approved = "58" in str(error) or "Incomplete registration" in str(error)
        return JsonResponse(
            {"error": "not_approved" if not_approved else "direct_error",
             "detail": str(error)},
            status=409 if not_approved else 502,
        )
    return JsonResponse({"campaigns": campaigns, "count": len(campaigns)})


@_ops_api_gate
@require_GET
def status(request):
    """Состояние интеграции одним ответом. Ничего не запрашивает у Яндекса.

    БЕЗ ОБРАЩЕНИЯ В СЕТЬ НАРОЧНО. Этот эндпоинт дёргают, когда «ничего не
    работает», и он обязан отвечать даже при недоступном Яндексе — иначе
    диагностика отказывает ровно в тот момент, ради которого существует.
    """
    return JsonResponse({
        "configured": yandex_api.configured(),
        "client_id_set": bool(settings.YANDEX_OAUTH_CLIENT_ID),
        "client_secret_set": bool(settings.YANDEX_OAUTH_CLIENT_SECRET),
        "refresh_token_set": bool(settings.YANDEX_OAUTH_REFRESH_TOKEN),
        "counter": settings.METRIKA_ID,
        "counter_set": bool(settings.METRIKA_ID),
    })


@require_GET
@_ops_api_gate
def seo(request):
    """Снимки поиска машинным видом: индекс, позиции, движение.

    РУЧКА НУЖНА ДАЙДЖЕСТУ И ЛЮБОМУ ВНЕШНЕМУ ЧИТАТЕЛЮ. Сводка ходит в `ops.seo`
    напрямую, потому что живёт в том же процессе; ручка существует для того, кто
    в процессе не живёт, — утреннего отчёта на другом хосте, выгрузки в таблицу.
    Считать заново она НЕ умеет: это дорого и требует секретов, поэтому отдаёт
    то, что уже собрано, и честно говорит, если за сутки снимка нет.
    """
    from datetime import date

    from ops.models import SeoDay
    from ops import seo as seo_module

    days = min(max(int(request.GET.get("days", 14)), 1), 365)
    rows = list(SeoDay.objects.all()[:days])
    today = date.today().isoformat()
    payload = {
        "today_collected": any(row.day.isoformat() == today for row in rows),
        "days": [
            {
                "day": row.day.isoformat(),
                "pages_in_index": row.pages_in_index,
                "pages_in_index_estimate": row.pages_in_index_estimate,
                "sqi": row.sqi,
                "in_top10": seo_module.in_top10(row),
                "queries_measured": len(row.positions),
                "popular_queries": [q.get("query") for q in row.popular_queries[:5]],
                "positions": row.positions,
                "sources": row.sources,
            }
            for row in rows
        ],
    }
    return JsonResponse(payload)
