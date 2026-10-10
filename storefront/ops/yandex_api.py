"""Яндекс API: один access-токен на Метрику и Директ, обмен и обновление.

ЗАЧЕМ ЭТОТ МОДУЛЬ СУЩЕСТВУЕТ, ЕСЛИ СЧЁТЧИК УЖЕ СТОИТ. Счётчик Метрики —
браузерный: он считает то, что увидел браузер посетителя. Он не отвечает ни на
один вопрос, который стоит денег на нашем уровне: «сколько регистраций принёс
канал», «какой запрос дал оплату», «какие кампании крутятся и сколько
израсходовано». Это данные ВЛАДЕЛЬЦА, и API Яндекса отдаёт их только по
OAuth-токену, выданному владельцем на наше приложение.

ПОЧЕМУ ACCESS-ТОКЕН НЕ ХРАНИТСЯ. Он выводится из refresh-токена за одно
обращение и живёт в памяти процесса. Секрет, который можно переполучить,
переживший процесс, переживает и отзыв: лежащий на диске access-токен
продолжает работать после того, как владелец отозвал приложение, и узнать об
этом можно только по отказам в логах. Refresh-токен лежит в `.env` — он и есть
долгоживущий секрет, и его отзыв должен быть ОДНИМ действием владельца.

ЧЕГО ЗДЕСЬ НЕТ И ПОЧЕМУ. Ни одного метода, который пишет в Директ: этот модуль
пока только читает (`direct_report`, `metrika_*`). Причина не в осторожности
вообще, а в порядке работ — заявка на доступ к API Директа рассматривается до
семи дней, и до её одобрения любой управляющий вызов вернёт ошибку 58
«Incomplete registration». Написать их раньше, чем появится доступ, значило бы
написать код, который нельзя ни разу выполнить.
"""

import csv
import io
import logging
import threading
import time

import httpx
from django.conf import settings

_log = logging.getLogger("ops.yandex")

TOKEN_URL = "https://oauth.yandex.ru/token"
METRIKA_API = "https://api-metrika.yandex.net"
# v5 compatibility reports a Unified campaign as TEXT_CAMPAIGN; v501 keeps
# the real type, which the operator needs before interpreting its settings.
DIRECT_API = "https://api.direct.yandex.com/json/v501"

# ЗАПАС К ИСТЕЧЕНИЮ. Токен меняется на границе срока, а не в момент отказа:
# запрос, начатый за секунду до истечения, доедет уже с мёртвым токеном и
# вернёт 401 — который читается как «доступ отозван» и посылает искать
# проблему не там. Минуты хватает с избытком на любой запрос к отчётам.
_EXPIRY_MARGIN = 120.0

# Сеть у нас не мгновенная, а Директ Reports честно думает над тяжёлым
# отчётом. Таймаут разделён: соединение — секунды, чтение — минуты, потому что
# это два разных ожидания и общий таймаут делает коротким то, что коротким не
# должно быть.
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


class YandexError(RuntimeError):
    """Ошибка обращения к Яндексу, пригодная для показа оператору.

    Несёт HTTP-статус и тело ответа: у Яндекса ошибка лежит В ТЕЛЕ даже при
    400, и «HTTP 400» без тела не говорит ничего — а тело говорит, например,
    «Incomplete registration» про неодобренную заявку Директа.
    """

    def __init__(self, message: str, status: int = 0, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


# КЭШ ТОКЕНА — НА ПРОЦЕСС, ПОД ЗАМКОМ. gunicorn поднимает N воркеров, и без
# замка одновременные запросы в одном воркере устроили бы N обменов одного и
# того же refresh-токена. Яндекс это переживёт, но `invalid_grant` при
# параллельном обмене существует, и получить его на ровном месте — это отказ,
# который не воспроизводится и потому не чинится.
_token_lock = threading.Lock()
_access_token = ""
_access_expires_at = 0.0


def configured() -> bool:
    """Есть ли чем работать. Пустой ответ — интеграция выключена, не сломана."""
    return bool(
        settings.YANDEX_OAUTH_CLIENT_ID
        and settings.YANDEX_OAUTH_CLIENT_SECRET
        and settings.YANDEX_OAUTH_REFRESH_TOKEN
    )


def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """Единственное место, где модуль выходит в сеть.

    Вынесено отдельной функцией ради тестов: подменяется целиком, и проверки
    не зависят ни от сети, ни от боевого токена. Тест, который ходит в Яндекс,
    — это тест, который однажды упадёт от чужого 429.
    """
    return httpx.request(method, url, timeout=_TIMEOUT, **kwargs)


def _token_request(data: dict) -> dict:
    """Обмен кода или refresh-токена на access-токен. Общий путь у обоих."""
    response = _request("POST", TOKEN_URL, data=data)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200 or "access_token" not in payload:
        # ТЕЛО ОТВЕТА НЕ ЛОГИРУЕТСЯ: при неудачном обмене Яндекс возвращает в
        # поле `error_description` в том числе фрагменты запроса, а в запросе
        # лежит client_secret. Ошибка называется по коду, диагностика — по
        # статусу; секрет в лог не попадает.
        error = payload.get("error", "") if isinstance(payload, dict) else ""
        raise YandexError(
            f"Яндекс не выдал токен: {error or 'ответ без access_token'} "
            f"(HTTP {response.status_code})",
            status=response.status_code,
        )
    return payload


def exchange_code(code: str) -> dict:
    """Одноразовый обмен кода авторизации. Вызывается человеком, не cron'ом.

    Это единственный шаг, который требует участия владельца: он открывает
    страницу авторизации, копирует код и отдаёт его сюда. Дальше приложение
    работает по refresh-токену само — и это ровно то, ради чего шаг вынесен в
    отдельную команду, а не спрятан в поток запроса.
    """
    return _token_request({
        "grant_type": "authorization_code",
        "code": code.strip(),
        "client_id": settings.YANDEX_OAUTH_CLIENT_ID,
        "client_secret": settings.YANDEX_OAUTH_CLIENT_SECRET,
    })


def _refresh() -> dict:
    return _token_request({
        "grant_type": "refresh_token",
        "refresh_token": settings.YANDEX_OAUTH_REFRESH_TOKEN,
        "client_id": settings.YANDEX_OAUTH_CLIENT_ID,
        "client_secret": settings.YANDEX_OAUTH_CLIENT_SECRET,
    })


def access_token(force: bool = False) -> str:
    """Действующий access-токен, при необходимости — обновлённый.

    `force` нужен тому, кто получил 401 на живом токене: отзыв приложения
    выглядит именно так, и одна повторная попытка отличает «токен истёк» от
    «доступ закрыт».
    """
    global _access_token, _access_expires_at
    if not configured():
        raise YandexError(
            "Яндекс API не настроен: нет YANDEX_OAUTH_CLIENT_ID / "
            "YANDEX_OAUTH_CLIENT_SECRET / YANDEX_OAUTH_REFRESH_TOKEN."
        )
    now = time.monotonic()
    with _token_lock:
        if not force and _access_token and now < _access_expires_at:
            return _access_token
        payload = _refresh()
        _access_token = payload["access_token"]
        # `expires_in` у Яндекса — секунды; отсутствие поля читаем как короткий
        # срок, а не как бесконечный: неизвестный срок, принятый за вечный,
        # даёт отказ через год и расследование на пустом месте.
        lifetime = float(payload.get("expires_in") or 3600)
        _access_expires_at = time.monotonic() + max(0.0, lifetime - _EXPIRY_MARGIN)
        return _access_token


def _check(response: httpx.Response, what: str) -> dict:
    """Разбор ответа Яндекса: и HTTP-статус, и ошибку в теле.

    ДВЕ ПРОВЕРКИ, А НЕ ОДНА. Директ умеет отвечать HTTP 200 с `error` в теле —
    это не «всё хорошо», это отказ, и молча вернуть его наверх значит показать
    оператору пустой отчёт вместо причины.
    """
    try:
        payload = response.json()
    except ValueError:
        raise YandexError(
            f"{what}: ответ не разобрался как JSON (HTTP {response.status_code})",
            status=response.status_code,
        ) from None
    if response.status_code != 200:
        raise YandexError(
            f"{what}: HTTP {response.status_code}", status=response.status_code,
            payload=payload,
        )
    if isinstance(payload, dict):
        if payload.get("error"):
            error = payload["error"]
            detail = error.get("error_string") or error.get("message") or error
            raise YandexError(f"{what}: {detail}", payload=payload)
        if payload.get("errors"):
            raise YandexError(f"{what}: {payload['errors']}", payload=payload)
    return payload


def metrika_get(path: str, params: dict | None = None) -> dict:
    """GET к API Метрики. Авторизация — `OAuth`, а не `Bearer`.

    ЭТО НЕ ОПЕЧАТКА И НЕ РАЗНОБОЙ ВКУСОВ: так у Яндекса. Метрика принимает
    `Authorization: OAuth <токен>`, Директ — `Bearer`; перепутанная схема даёт
    403 с телом про недостаток прав, то есть посылает проверять скоупы вместо
    заголовка.
    """
    response = _request(
        "GET", f"{METRIKA_API}{path}",
        params=params or {},
        headers={"Authorization": f"OAuth {access_token()}"},
    )
    return _check(response, f"Метрика {path}")


def direct(service: str, method: str, params: dict) -> dict:
    """POST к API Директа v501. Один сервис — один путь.

    Формат Директа — не REST: и чтение, и запись идут POST'ом на
    `/json/v501/<сервис>` с телом `{"method": ..., "params": ...}`. Поэтому
    «получить список кампаний» и «создать кампанию» выглядят одинаково, и
    различает их только `method`.
    """
    response = _request(
        "POST", f"{DIRECT_API}/{service}",
        json={"method": method, "params": params},
        headers={
            "Authorization": f"Bearer {access_token()}",
            "Accept-Language": "ru",
        },
    )
    return _check(response, f"Директ {service}.{method}")


def counters() -> list[dict]:
    """Счётчики Метрики, доступные токену.

    Нужен не ради списка, а ради ПРОВЕРКИ: он отвечает «токен жив и видит
    аккаунт» одним дешёвым запросом. Это то, что печатает `yandex_auth
    --status`, и без этого диагноз «не работает» не отличает отозванный токен
    от пустого аккаунта.
    """
    payload = metrika_get("/management/v1/counters")
    return (payload.get("counters") or [])


def direct_campaigns() -> list[dict]:
    """Кампании Директа. Пустой ответ здесь — тоже ответ.

    При неодобренной заявке на доступ Директ отвечает ошибкой 58, и она
    приходит сюда как `YandexError` — этим и отличается «доступ ещё не дали» от
    «кампаний нет».
    """
    payload = direct("campaigns", "get", {
        "SelectionCriteria": {},
        "FieldNames": ["Id", "Name", "Status", "State", "Type",
                       "DailyBudget", "Funds", "Statistics"],
    })
    result = payload.get("result") or {}
    return result.get("Campaigns") or []


def goals() -> list[dict]:
    """Цели счётчика. По ним видно, заведена ли цель под нашу конверсию."""
    payload = metrika_get(f"/management/v1/counter/{settings.METRIKA_ID}/goals")
    return payload.get("goals") or []


def create_goal(name: str, identifier: str) -> dict:
    """Завести цель «JavaScript-событие» с идентификатором, который мы шлём.

    ПОЧЕМУ ЦЕЛЬ СОЗДАЁТ КОД, А НЕ ВЛАДЕЛЕЦ В ПАНЕЛИ. Офлайн-конверсия
    привязывается к цели ПО ИМЕНИ ИДЕНТИФИКАТОРА, и цель с опечаткой в нём
    принимает загрузку без ошибки: Метрика сопоставит ноль записей и отчитается
    статусом `LINKAGE_FAILURE` через три часа. Строка, созданная той же
    константой, что и отправка, разойтись с ней не может; строка, набранная
    руками в панели, — может и разойдётся.

    Условие обязательно «совпадает» (`exact`): этого требует документация
    офлайн-конверсий, и цель с условием «содержит» сопоставит больше событий,
    чем мы отправили.

    ИДЕНТИФИКАТОР ЛЕЖИТ В ПОЛЕ `url`, А НЕ `value` — так у Метрики, и это не
    опечатка: `url` здесь означает «строка условия», одинаково для адреса
    страницы, имени события и номера телефона. Первая версия отправляла
    `value`, и API отвечал `conditions[0].value must not be empty`: поле, о
    котором он говорит, в схеме есть, но заполняется из другого имени, и
    сообщение называет не тот ключ, который надо поправить.
    """
    response = _request(
        "POST", f"{METRIKA_API}/management/v1/counter/{settings.METRIKA_ID}/goals",
        json={"goal": {"name": name, "type": "action",
                       "conditions": [{"type": "exact", "url": identifier}]}},
        headers={"Authorization": f"OAuth {access_token()}"},
    )
    return _check(response, f"создание цели {identifier}")


def metrika_summary(days: int = 30) -> dict:
    """Итоги и разрез по источникам за окно — один вызов, одно окно.

    ОДНА РЕАЛИЗАЦИЯ НА ЭКРАН И НА СВОДКУ В БОТА. Два места, считающие одно и то
    же порознь, расходятся молча — и расходятся ровно тогда, когда кто-то
    правит запрос в одном из них. Здесь же оба запроса живут вместе ещё по
    одной причине: «пришло 400» без «откуда» не отвечает ни на один вопрос, а
    посчитанные в разных обращениях окна могут не совпасть на границе суток, и
    цифры в одном отчёте перестанут сходиться между собой.
    """
    import datetime
    from django.utils import timezone

    if not settings.METRIKA_ID:
        raise YandexError("PSEUDEX_METRIKA_ID не задан — статистики не будет.")
    days = max(1, min(365, days))
    # Production and its counter use Europe/Moscow, not the container's UTC.
    # Report the application timezone explicitly rather than silently shifting
    # the period around midnight. Reconcile if the counter timezone changes.
    today = timezone.localdate()
    counter = settings.METRIKA_ID
    date1 = (today - datetime.timedelta(days=days - 1)).isoformat()
    date2 = today.isoformat()

    totals = metrika_get("/stat/v1/data", {
        "ids": counter, "date1": date1, "date2": date2,
        "metrics": "ym:s:visits,ym:s:users,ym:s:pageviews", "accuracy": "full",
        "attribution": "last",
    })
    sources = metrika_get("/stat/v1/data", {
        "ids": counter, "date1": date1, "date2": date2,
        "dimensions": "ym:s:trafficSource",
        "metrics": "ym:s:visits", "sort": "-ym:s:visits", "limit": 10,
        "accuracy": "full", "attribution": "last",
    })
    def quality(reply):
        returned = len(reply.get("data") or [])
        total_rows = reply.get("total_rows")
        return {"sampled": reply.get("sampled"),
                "sample_share": reply.get("sample_share"),
                "data_lag": reply.get("data_lag"),
                "total_rows": total_rows, "returned_rows": returned,
                "truncated": total_rows > returned if isinstance(total_rows, int) else None}
    return {
        "counter": counter,
        "period": {"days": days, "date1": date1, "date2": date2,
                   "timezone": settings.TIME_ZONE},
        "attribution": "last",
        "quality": {"totals": quality(totals), "sources": quality(sources)},
        "totals": list(totals.get("totals") or []),
        "sources": [
            {"source": (row.get("dimensions") or [{}])[0].get("name", ""),
             "visits": (row.get("metrics") or [0])[0]}
            for row in (sources.get("data") or [])
        ],
    }


def upload_conversions(rows: list[dict], comment: str = "") -> dict:
    """Загрузить офлайн-конверсии. `rows` — по одной на событие.

    ФОРМАТ ЗАДАН ДОКУМЕНТАЦИЕЙ И ПЕРЕНОСИТ ОШИБКУ ВРЕМЕНИ, А НЕ ДАННЫХ.
    `DateTime` — UNIX-время СТРОГО В ПРОШЛОМ: запись с будущим временем
    отклоняет всю загрузку, а не одну строку. Поэтому отметка берётся у самого
    события из `Funnel`, а не у момента отправки.

    ИДЕНТИФИКАТОР РОВНО ОДИН. Метрика принимает `ClientId` (кука — у нас их
    нет), `UserId` (свой идентификатор — мы его не заводим) или `Yclid`.
    Строка без yclid не привяжется ни к какому визиту, поэтому такие строки
    отсеиваются ДО запроса: загрузка, которая заведомо даст `LINKAGE_FAILURE`,
    тратит квоту и прячет настоящую причину за статусом, а не за своим
    отсутствием.
    """
    usable = [row for row in rows if row.get("yclid")]
    if not usable:
        return {"skipped": len(rows), "uploading": None}

    # ЦЕНА И ВАЛЮТА — ТОЛЬКО ЕСЛИ ЦЕНА ЕСТЬ. Колонка, целиком состоящая из
    # пустых значений, выглядит безобидно и мешает чтению файла глазами, когда
    # загрузка не сошлась и её достают из Метрики.
    priced = any(row.get("price") is not None for row in usable)
    header = ["Target", "DateTime", "Yclid"]
    if priced:
        header += ["Price", "Currency"]

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in usable:
        line = [row["target"], int(row["at"].timestamp()), row["yclid"]]
        if priced:
            price = row.get("price")
            # ТОЧКА, А НЕ ЗАПЯТАЯ, и это не придирка: русская локаль печатает
            # «3900,00», и такая цена не разберётся — молча, вместе со всей
            # строкой. Ровно та же ошибка, что с ценой в разметке для робота.
            line += [f"{price:.2f}" if price is not None else "",
                     (row.get("currency") or "RUB") if price is not None else ""]
        writer.writerow(line)

    response = _request(
        "POST",
        f"{METRIKA_API}/management/v1/counter/{settings.METRIKA_ID}"
        "/offline_conversions/upload",
        params={"comment": comment[:255]} if comment else None,
        files={"file": ("conversions.csv", buffer.getvalue(), "text/csv")},
        headers={"Authorization": f"OAuth {access_token()}"},
    )
    payload = _check(response, "загрузка конверсий")
    uploading = payload.get("uploading") or {}
    return {"skipped": len(rows) - len(usable), "uploading": uploading,
            "sent": len(usable)}

