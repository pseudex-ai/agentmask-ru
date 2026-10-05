"""Два разных взгляда на поиск: что знает Яндекс и где мы в выдаче.

ЗАЧЕМ ДВА ИСТОЧНИКА, А НЕ ОДИН. Это не дублирование, у них разные оси, и
подменять один другим нельзя:

  Яндекс Вебмастер API — ДАННЫЕ ВЛАДЕЛЬЦА. Сколько страниц в поиске (точно, а
    не оценка), по каким запросам сайт показывался, ИКС, и — что важнее всего
    практически — постановка адресов в очередь переобхода. Требует OAuth
    владельца: тот же refresh-токен, что у Метрики и Директа, плюс скоуп
    `webmaster:hostinfo`.
  Search API — ЖИВАЯ ВЫДАЧА. Позиция по нашему списку целевых запросов и
    `site:` как оценка индекса. Требует ключ сервисного аккаунта Yandex Cloud.

ПОЧЕМУ БЕЗ ВТОРОГО НЕ ОБОЙТИСЬ НА СТАРТЕ. Вебмастер говорит о том, что уже
произошло: показов нет — и в отчёте по запросам пусто, хотя страница может
стоять на 40-м месте. Пока сайт молодой, движение видно ТОЛЬКО через живую
выдачу. И наоборот: когда показы появятся, авторитетным становится Вебмастер, а
`site:` остаётся оценкой. Поэтому в снимке лежат оба, и подписываются они
по-разному, чтобы никто не принял оценку за факт.

ПОЧЕМУ ЗДЕСЬ НЕТ ПИШУЩИХ ВЫЗОВОВ, КРОМЕ ПЕРЕОБХОДА. Переобход — единственное
изменение, которое мы делаем в чужой системе, и оно безобидно по устройству:
это не «поставь нас выше», а «посмотри страницу». Всё остальное только читает,
и это осознанно: управляющие вызовы Директа в соседнем модуле ждут одобрения
приложения, и писать код, который нельзя выполнить, там уже отказались.
"""

import json
import logging
import re
from typing import Any

import httpx
from django.conf import settings

_log = logging.getLogger("ops.seo")

WEBMASTER_API = "https://api.webmaster.yandex.net/v4"
SEARCH_API = "https://searchapi.api.cloud.yandex.net/v2"

# ТАЙМАУТ КОРОТКИЙ И ОН ЖЕ ОГРАНИЧИВАЕТ ВЕСЬ СНИМОК. Сбор идёт по расписанию и
# не должен держать воркер: если Яндекс не ответил за десять секунд, снимок за
# эти сутки будет неполным — и это правильный исход, потому что «нет данных» мы
# умеем показать честно, а повисший воркер не умеет ничего.
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class SeoError(RuntimeError):
    """Источник недоступен или ответил отказом. Наружу идёт как «неизвестно»."""


# ── Вебмастер API (OAuth владельца) ──────────────────────────────────────────

def webmaster_configured() -> bool:
    """Есть ли чем ходить в Вебмастер.

    Отдельно от `configured()` Search API: у них разные секреты и разные отказы.
    """
    return bool(
        getattr(settings, "YANDEX_OAUTH_REFRESH_TOKEN", "")
        and getattr(settings, "YANDEX_OAUTH_CLIENT_ID", "")
        and getattr(settings, "YANDEX_OAUTH_CLIENT_SECRET", "")
    )


def _webmaster_request(path: str, params: dict | None = None) -> Any:
    from ops import yandex_api  # ленивый импорт: токен берётся из того же места

    token = yandex_api.access_token()
    response = httpx.get(
        f"{WEBMASTER_API}{path}",
        params=params or {},
        headers={"Authorization": f"OAuth {token}"},
        timeout=_TIMEOUT,
    )
    return _check(response, f"Вебмастер {path}")


def _check(response: httpx.Response, what: str) -> Any:
    if response.status_code >= 400:
        raise SeoError(f"{what}: HTTP {response.status_code} {response.text[:200]}")
    try:
        return response.json()
    except json.JSONDecodeError as error:
        raise SeoError(f"{what}: ответ не JSON ({error})") from error


def _host_name(url: str) -> str:
    """Имя хоста без схемы и завершающей косой черты.

    СХЕМУ СНИМАЕМ С ОБЕИХ СТОРОН, И ЭТО НЕ ПРИДИРКА. Вебмастер отдаёт
    `ascii_host_url` как `https://pseudex.ru/`, а `SITE_URL` у нас без схемы.
    Сравнение «как есть» не совпадало НИКОГДА: источник молчал месяцами, снимок
    писал «сайта pseudex.ru нет среди хостов», хотя хост подтверждён и API
    отвечал 200. Отказ выглядел как «Вебмастер недоступен», а не как наша
    ошибка, — поэтому и не был замечен."""
    return url.replace("https://", "").replace("http://", "").strip("/").lower()


def _webmaster_ids() -> tuple[int, str]:
    """Идентификатор пользователя и ПОДТВЕРЖДЁННОГО хоста.

    Хост ищется, а не задаётся константой: `host_id` — внутренний номер Яндекса,
    он не совпадает с доменом, и вписанный руками он молча разошёлся бы с
    реальностью после переподтверждения прав.
    """
    user = _webmaster_request("/user/")["user_id"]
    hosts = _webmaster_request(f"/user/{user}/hosts/")["hosts"]
    site = _host_name(str(getattr(settings, "SITE_URL", "")))
    for host in hosts:
        names = {_host_name(str(host.get("ascii_host_url", ""))),
                 _host_name(str(host.get("host_url", "")))}
        if site in names:
            if not host.get("verified"):
                raise SeoError(f"хост {site} не подтверждён — Вебмастер данных не отдаёт")
            return int(user), str(host["host_id"])
    raise SeoError(f"сайта {site} нет среди хостов Вебмастера: {[h.get('ascii_host_url') for h in hosts]}")


def webmaster_summary() -> dict[str, Any]:
    """Сколько страниц в поиске и ИКС. Точные данные владельца."""
    user, host = _webmaster_ids()
    data = _webmaster_request(f"/user/{user}/hosts/{host}/summary/")
    return {
        "sqi": data.get("sqi"),
        "pages_in_search": data.get("searchable_urls_count"),
        "excluded": data.get("excluded_urls_count"),
        "raw": data,
    }


def webmaster_popular(limit: int = 20) -> list[dict[str, Any]]:
    """Запросы, по которым сайт ПОКАЗЫВАЛСЯ. Пусто — значит показов ещё нет."""
    user, host = _webmaster_ids()
    data = _webmaster_request(
        f"/user/{user}/hosts/{host}/search-queries/popular/",
        {"order_by": "TOTAL_SHOWS", "limit": limit},
    )
    return [
        {"query": q.get("query_text", ""), "query_id": q.get("query_id", "")}
        for q in data.get("queries", [])
    ]


def webmaster_recrawl(urls: list[str]) -> dict[str, Any]:
    """Поставить адреса в очередь переобхода.

    ПО ОДНОМУ АДРЕСУ НА ЗАПРОС, и это выяснилось только на живом API. Тело
    `{"urls": ["…", "…"]}` он отвергает `ENTITY_VALIDATION_ERROR` «Cannot parse
    request entity»; принимает `{"url": "…"}` и отвечает `202` с `task_id` и
    остатком квоты. То есть первая версия этой функции не отправляла НИЧЕГО, а в
    снимок за сутки писала ошибку — и выглядела исправной, потому что «источник
    недоступен» уже считалось нормальным ответом.

    Отказ по одному адресу не отменяет остальные: исчерпанная квота — не ошибка
    сбора, и снимок обязан остаться валидным. Поэтому отказы собираются списком,
    а не бросаются исключением."""
    if not urls:
        return {"submitted": 0, "quota_remainder": None}
    user, host = _webmaster_ids()
    from ops import yandex_api

    token = yandex_api.access_token()
    limit = urls[: settings.YANDEX_RECRAWL_LIMIT]
    submitted, tasks, refused, quota = 0, [], [], None
    for one in limit:
        response = httpx.post(
            f"{WEBMASTER_API}/user/{user}/hosts/{host}/recrawl/queue",
            json={"url": one},
            headers={"Authorization": f"OAuth {token}"},
            timeout=_TIMEOUT,
        )
        if response.status_code == 202:
            data = response.json()
            submitted += 1
            quota = data.get("quota_remainder")
            tasks.append(data.get("task_id"))
        else:
            refused.append({"url": one, "status": response.status_code,
                            "body": response.text[:120]})
    return {
        "submitted": submitted,
        "quota_remainder": quota,
        "tasks": tasks,
        "refused": refused,
        "requested": len(limit),
    }

def search_configured() -> bool:
    return bool(getattr(settings, "SEARCH_API_KEY", ""))


def _search_request(path: str, body: dict) -> Any:
    response = httpx.post(
        f"{SEARCH_API}{path}",
        json=body,
        headers={
            "Authorization": f"Api-Key {settings.SEARCH_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=_TIMEOUT,
    )
    data = _check(response, f"Search API {path}")
    # ОТВЕТ ПРИХОДИТ В base64-ЗАВЁРНУТОМ XML. Разворачиваем здесь, а не в
    # потребителе: иначе каждый, кто хочет одно число, обязан знать про base64.
    import base64

    raw = data.get("rawData")
    if not raw:
        raise SeoError(f"Search API {path}: в ответе нет rawData")
    return base64.b64decode(raw).decode("utf-8", "replace")


def _search_docs(xml: str) -> tuple[int, list[str]]:
    found = re.search(r"<found[^>]*>(\d+)</found>", xml)
    urls = [re.sub(r"<[^>]+>", "", m) for m in re.findall(r"<url>(.*?)</url>", xml, re.S)]
    return (int(found.group(1)) if found else 0), urls


def search_index_count() -> int:
    """`site:` — ОЦЕНКА индекса, а не факт. Настоящее число даёт Вебмастер."""
    xml = _search_request("/web/search", {"query": {
        "queryText": f"site:{_site_host()}", "searchType": "SEARCH_TYPE_RU",
        "familyMode": "FAMILY_MODE_NONE", "page": "0"}})
    return _search_docs(xml)[0]


def search_positions(queries: list[str]) -> list[dict[str, Any]]:
    """Позиция в живой выдаче по нашему списку. Единственное, что видно без показов."""
    host = _site_host()
    rows = []
    for query in queries:
        xml = _search_request("/web/search", {"query": {
            "queryText": query, "searchType": "SEARCH_TYPE_RU",
            "familyMode": "FAMILY_MODE_NONE", "page": "0"}})
        found, urls = _search_docs(xml)
        position = next(
            (i + 1 for i, url in enumerate(urls) if host in url), None
        )
        rows.append({"query": query, "position": position, "documents": found})
    return rows


def _site_host() -> str:
    return str(getattr(settings, "SITE_URL", "")).split("//")[-1].strip("/")


# ЦЕЛЕВОЙ СПИСОК — ЭТО НАШ ВЫБОР, А НЕ ВЫГРУЗКА СПРОСА. Позиции меряются по
# нему, поэтому он лежит в коде и меняется осознанно: добавили материал под новый
# кластер — добавили строку. Wordstat (сколько людей ищут) — отдельный вопрос, и
# он в снимок не входит: спрос не меняется от того, вышли мы в выдачу или нет, и
# мешать его с позициями в одной таблице значило бы показывать движение там, где
# его нет.
TARGET_QUERIES = (
    "обезличивание персональных данных",
    "как обезличить персональные данные",
    "можно ли отправлять персональные данные в chatgpt",
    "обезличивание данных для ии",
    "блокирование уничтожение обезличивание персональных данных",
    "приказ роскомнадзора 140 обезличивание",
    "персональные данные искусственный интеллект",
    "как выбрать систему обезличивания",
    "документы для обезличивания персональных данных",
    "штраф за трансграничную передачу персональных данных",
)
