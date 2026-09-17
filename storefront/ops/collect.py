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


def first_touch(visitor: str, since_hours: int) -> dict[str, str]:
    """Чем этот посетитель пришёл — по его же визитам за последние сутки.

    ПОЧЕМУ ЗДЕСЬ, А НЕ В КУКЕ. Метки кампании приходят на ЛЕНДИНГ, а форму
    человек отправляет через несколько минут и уже с другой страницы, на
    которой никаких меток нет. Обычное решение — положить первое касание в
    сессию, то есть поставить куку; лендинг обещает, что куки не ставит, и
    обещание это стоит дороже точности атрибуции.

    Суточный отпечаток даёт ровно то, что нужно, и ровно на тот срок, на
    который нужно: визиты одного человека за сегодня связываются между собой,
    а завтра — уже нет. Путь от лендинга до ключа занимает минуты.

    МЕТКА ПРЕДПОЧТИТЕЛЬНЕЕ РЕФЕРЕРА, И БЕРЁТСЯ САМАЯ РАННЯЯ. Человек мог
    прийти по объявлению, уйти читать документацию и вернуться — последний
    визит назвал бы источником нас самих. Платит за приход первое касание.
    """
    from ops.analytics_models import Visit
    from django.utils import timezone
    import datetime

    if not visitor:
        return {}
    since = timezone.now() - datetime.timedelta(hours=since_hours)
    mine = Visit.objects.filter(visitor=visitor, at__gte=since).order_by("at")

    tagged = mine.exclude(utm_source="").first()
    first = mine.first()
    if first is None:
        return {}
    # YCLID ИЩЕТСЯ ОТДЕЛЬНО ОТ МЕТОК. Обычно они приходят вместе (Директ
    # дописывает и `utm_*`, и `yclid`), но полагаться на это нельзя: метка
    # переживает правку объявления, а идентификатор клика — нет, и переход по
    # ссылке, где yclid уже потеряли, оставил бы организацию без единственного
    # ключа, по которому конверсию можно привязать.
    clicked = mine.exclude(yclid="").first()
    return {
        "source_utm_source": (tagged.utm_source if tagged else ""),
        "source_utm_medium": (tagged.utm_medium if tagged else ""),
        "source_utm_campaign": (tagged.utm_campaign if tagged else ""),
        "source_yclid": (clicked.yclid if clicked else ""),
        # Реферер берётся у ПЕРВОГО визита, а не у помеченного: если метки нет
        # вовсе, источником был переход, и он стоит именно там.
        "source_referrer": first.referrer_host,
        "source_landing": first.path,
    }


def flag_unwired(steps: list[dict]) -> list[dict]:
    """Отметить шаги воронки, которые не записываются, а не отваливаются.

    ШАГ С НУЛЁМ, ЗА КОТОРЫМ СТОИТ НЕНУЛЕВОЙ, НЕВОЗМОЖЕН ПО СМЫСЛУ. Воронка
    упорядочена физически, а не оформительски: заплатить, не замаскировав ни
    одного запроса, нельзя, как нельзя замаскировать, не подняв контейнера.
    Поэтому такой ноль — не отвал клиентов, а отсутствующая запись.

    ЭТО ЕДИНСТВЕННЫЙ СПОСОБ УВИДЕТЬ ДЫРУ С ЭКРАНА, и она уже была: `first_mask`
    объявлен в модели и не записывался ничем, а выглядел провалом конверсии —
    то есть посылал чинить продукт вместо аналитики. Функция чистая и вынесена
    из вью именно затем, чтобы её можно было сломать в тесте.
    """
    return [dict(step, unwired=(step["count"] == 0
                                and any(later["count"] > 0
                                        for later in steps[i + 1:])))
            for i, step in enumerate(steps)]
