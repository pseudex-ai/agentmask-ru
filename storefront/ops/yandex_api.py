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

import logging
import threading
import time

import httpx
from django.conf import settings

_log = logging.getLogger("ops.yandex")

TOKEN_URL = "https://oauth.yandex.ru/token"
METRIKA_API = "https://api-metrika.yandex.net"
DIRECT_API = "https://api.direct.yandex.com/json/v5"

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
    """POST к API Директа v5. Один сервис — один путь.

    Формат Директа — не REST: и чтение, и запись идут POST'ом на
    `/json/v5/<сервис>` с телом `{"method": ..., "params": ...}`. Поэтому
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
