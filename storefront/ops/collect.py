"""Сбор визита: суточная соль, фильтр ботов, разбор источника.

ЗДЕСЬ ЖИВЁТ ЕДИНСТВЕННОЕ МЕСТО, КОТОРОЕ ВИДИТ IP-АДРЕС, и оно его не
возвращает. Адрес входит в хеш и выходит из области видимости той же строкой.
"""

import hashlib
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

# СОЛЬ СУТОК В ПАМЯТИ ПРОЦЕССА, А НЕ В БАЗЕ.
#
# В базе она пережила бы сутки в бэкапе, и тогда обещание «назавтра связать
# нельзя» держалось бы на нашей аккуратности при восстановлении, а не на
# устройстве. В памяти она исчезает с процессом — сильнее, чем любое `DELETE`.
#
# Цена названа: у N воркеров N разных солей, поэтому один человек в один день
# может дать до N разных отпечатков и уникальные посетители СЧИТАЮТСЯ СВЕРХУ.
# Для вопроса «какой канал работает» это шум порядка числа воркеров; для
# вопроса «сколько людей» — завышение, и так и написано на экране.
_salt_lock = threading.Lock()
_salt_value = ""
_salt_day = -1


def _daily_salt() -> str:
    global _salt_value, _salt_day
    day = int(time.time() // 86400)
    with _salt_lock:
        if day != _salt_day:
            _salt_value = secrets.token_hex(32)
            _salt_day = day
        return _salt_value


def fingerprint(host: str, ip: str, user_agent: str) -> str:
    """Суточный отпечаток. IP входит сюда и никуда больше."""
    raw = f"{_daily_salt()}|{host}|{ip}|{user_agent}".encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:16]


# ── боты ──────────────────────────────────────────────────────────────────
#
# ФИЛЬТР НУЖЕН НЕ ДЛЯ КРАСОТЫ ЦИФР, А ПОТОМУ ЧТО ПО НИМ ПРИНИМАЮТ РЕШЕНИЯ.
# Лендинг с десятью живыми посетителями и двумя сотнями обходов краулеров
# показывает 210 и врёт в двадцать раз — а по этому числу выбирается канал.
#
# Считаем ботов, но НЕ ВЫБРАСЫВАЕМ: строка помечается и по умолчанию не
# показывается. Выброшенное нельзя пересчитать, если фильтр ошибся, а
# помеченное можно.
_BOT_PATTERNS = re.compile(
    r"bot|crawl|spider|slurp|search|fetch|scrape|curl|wget|python-requests|"
    r"httpx|okhttp|java/|go-http|libwww|headless|phantom|selenium|playwright|"
    r"puppeteer|lighthouse|pingdom|uptime|monitor|preview|validator|"
    r"facebookexternalhit|whatsapp|telegram|slackbot|discord|vkshare|"
    r"yandex(?!browser)|google(?!chrome)|bing|baidu|duckduck|semrush|ahrefs|"
    r"mj12|dotbot|petal|bytespider|gptbot|claudebot|ccbot|perplexity|applebot",
    re.I,
)


def looks_like_bot(user_agent: str, accept: str) -> bool:
    """Бот ли это по тому, что он о себе сказал и что попросил.

    ДВА СИГНАЛА, И ВТОРОЙ ЛОВИТ ТО, ЧЕГО НЕ ЛОВИТ ПЕРВЫЙ. Список строк —
    это гонка, в которой мы всегда позади: новый краулер по определению не в
    списке. Но браузер, рисующий страницу человеку, ВСЕГДА просит `text/html`,
    а скрипт, дёргающий адрес, обычно не просит ничего или просит `*/*`. Второй
    сигнал не зависит от списка и потому не устаревает.
    """
    if not user_agent or len(user_agent) < 12:
        return True
    if _BOT_PATTERNS.search(user_agent):
        return True
    return "text/html" not in (accept or "").lower()


# ── источник ──────────────────────────────────────────────────────────────

# Хосты, которые приходят рефером на свои же страницы. Собственный переход не
# источник трафика, и без этой строки главным «каналом» становишься ты сам.
def referrer_host_of(referrer: str, own_hosts: set[str]) -> str:
    if not referrer:
        return ""
    try:
        host = urlsplit(referrer).netloc.lower()
    except ValueError:
        return ""
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return "" if host in own_hosts or not host else host[:120]


# ── устройство ────────────────────────────────────────────────────────────
#
# КАТЕГОРИЯ, А НЕ СТРОКА. Полный user-agent — это отпечаток: связка версий
# браузера, ОС и сборки опознаёт человека не хуже куки. Три коротких поля
# отвечают на вопросы «верстать ли под телефон» и «поддерживать ли этот
# браузер» и не опознают никого.
_BROWSERS = (
    ("YaBrowser", "Яндекс"), ("Edg/", "Edge"), ("OPR/", "Opera"),
    ("Firefox", "Firefox"), ("Chrome", "Chrome"), ("Safari", "Safari"),
)
_SYSTEMS = (
    ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iOS"),
    ("Windows", "Windows"), ("Mac OS", "macOS"), ("Linux", "Linux"),
)


def classify(user_agent: str) -> tuple[str, str, str]:
    """(устройство, браузер, ОС) — три категории и ничего больше."""
    mobile = any(word in user_agent for word in
                 ("Mobile", "Android", "iPhone", "iPod"))
    tablet = "iPad" in user_agent or ("Android" in user_agent and "Mobile" not in user_agent)
    device = "планшет" if tablet else ("телефон" if mobile else "десктоп")
    browser = next((name for token, name in _BROWSERS if token in user_agent), "")
    system = next((name for token, name in _SYSTEMS if token in user_agent), "")
    return device, browser, system


def client_ip(meta: dict) -> str:
    """Адрес из заголовка обратного прокси.

    ЛЕВЫЙ В ЦЕПОЧКЕ, А НЕ ПРАВЫЙ: `X-Forwarded-For` дописывается каждым
    прокси, и крайний правый — это адрес НАШЕГО же Caddy. Значение уходит в
    хеш и нигде не сохраняется.
    """
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return meta.get("REMOTE_ADDR", "")
