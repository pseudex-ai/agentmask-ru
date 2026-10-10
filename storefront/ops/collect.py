"""Сбор визита: суточная соль, фильтр ботов, разбор источника.

ЗДЕСЬ ЖИВЁТ ЕДИНСТВЕННОЕ МЕСТО, КОТОРОЕ ВИДИТ IP-АДРЕС, и оно его не
возвращает. Адрес входит в хеш и выходит из области видимости той же строкой.
"""

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from django.conf import settings

# СОЛЬ СУТОК: ОДНА НА ВСЕ ВОРКЕРЫ, И НЕ В БАЗЕ.
#
# ЧТО БЫЛО СЛОМАНО. Соль генерировалась в памяти КАЖДОГО процесса заново.
# Витрина поднимает gunicorn с `--workers 2` (`storefront/Dockerfile`), поэтому
# лендинг и отправка формы обслуживались разными процессами, и один и тот же
# человек получал ДВА РАЗНЫХ отпечатка. `first_touch` ищет визиты по
# отпечатку — значит в половине случаев не находил ни одного, и регистрация
# записывалась как «прямой заход»: без меток, без реферера и без `yclid`.
#
# Цена была названа неверно. В комментарии здесь стояло «уникальные посетители
# считаются сверху, шум порядка числа воркеров». Настоящая цена другая и хуже:
# теряется не точность счёта, а СВЯЗЬ МЕЖДУ ВИЗИТОМ И РЕГИСТРАЦИЕЙ. Без неё
# нет ответа «какая кампания привела клиента», а офлайн-конверсия в Метрику не
# привязывается вовсе — она живёт ровно на `yclid`, который терялся вместе с
# метками.
#
# ПОЧЕМУ ФАЙЛ, А НЕ БАЗА И НЕ ВЫВОД ИЗ СЕКРЕТА. База пережила бы сутки в
# бэкапе, и обещание «назавтра связать нельзя» держалось бы на нашей
# аккуратности при восстановлении, а не на устройстве. Вывод из `SECRET_KEY`
# (HMAC от номера суток) сделал бы отпечаток воспроизводимым НАВСЕГДА для того,
# у кого этот ключ есть, — то есть отменил бы обещание задним числом. Файл
# лежит на эфемерной файловой системе контейнера: воркеры видят один и тот же,
# в базу и бэкапы он не попадает, и умирает вместе с контейнером.
#
# ЧТО ЭТО СТОИТ. При пересоздании контейнера — а это каждая выкатка — соль
# меняется, и в этот день человек может дать два отпечатка. Это N по числу
# выкаток за сутки, а не по числу воркеров, и N здесь обычно ноль или один.
_SALT_FILE = os.environ.get("PSEUDEX_ANALYTICS_SALT_FILE",
                            "/tmp/pseudex-analytics-salt")

_salt_lock = threading.Lock()
_salt_value = ""
_salt_day = -1


def _derived_salt(day: int) -> str:
    """Запасной путь: соль из `SECRET_KEY`. Слабее файла, но не ломается.

    НУЖЕН РОВНО НА СЛУЧАЙ, КОГДА ФАЙЛ ЗАПИСАТЬ НЕЛЬЗЯ (том только для чтения,
    чужая песочница). Молча вернуться к соли на процесс здесь нельзя: это ровно
    тот отказ, который мы чиним, — тихий и воспроизводящийся в половине
    случаев. Поэтому запасной путь ДЕТЕРМИНИРОВАН и о своём включении
    предупреждает в лог.
    """
    key = settings.SECRET_KEY.encode("utf-8", "replace")
    return hmac.new(key, f"pseudex-analytics-salt:{day}".encode(),
                    hashlib.sha256).hexdigest()


def _load_or_create(day: int) -> str:
    path = f"{_SALT_FILE}.{day}"
    try:
        # `x` — это O_CREAT|O_EXCL: гонку выигрывает ОДИН воркер, остальные
        # читают его соль. Без этого два процесса записали бы две разные соли
        # подряд, и вернулась бы та же рассинхронизация, только реже.
        with open(path, "x", encoding="ascii") as handle:
            handle.write(secrets.token_hex(32))
        # 600, А НЕ УМОЛЧАНИЕ. Соль — секрет: с ней отпечатки за сутки
        # разворачиваются обратно в адреса. Внутри контейнера наши процессы и
        # так свои, но файл, доступный на чтение всем, — это ровно тот
        # «аккуратность вместо устройства», от которого здесь уходят.
        os.chmod(path, 0o600)
        # Вчерашний файл больше не нужен: он не соли следующего дня, а мусор,
        # за которым однажды придут с вопросом «а что это тут лежит».
        for stale in _stale_salts(path):
            try:
                os.unlink(stale)
            except OSError:
                pass
    except FileExistsError:
        pass
    except OSError as error:
        _log_salt_fallback(error)
        return _derived_salt(day)
    try:
        with open(path, encoding="ascii") as handle:
            value = handle.read().strip()
        if value:
            return value
    except OSError as error:
        _log_salt_fallback(error)
    return _derived_salt(day)


def _stale_salts(current: str) -> list[str]:
    import glob
    return [name for name in glob.glob(f"{_SALT_FILE}.*") if name != current]


def _log_salt_fallback(error: OSError) -> None:
    import logging
    logging.getLogger("ops").warning(
        "соль аналитики берётся из SECRET_KEY, а не из файла (%s). Отпечатки "
        "согласованы между воркерами, но воспроизводимы для того, у кого есть "
        "ключ, — то есть обещание «назавтра связать нельзя» слабее обычного.",
        error)


def _daily_salt() -> str:
    global _salt_value, _salt_day
    day = int(time.time() // 86400)
    with _salt_lock:
        if day != _salt_day or not _salt_value:
            _salt_value = _load_or_create(day)
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
    """Keep the presentation shape without diagnosing wiring from totals.

    A paid signup pays BEFORE it can get a key or mask anything. Window totals
    also mix different organisations and maturities. A zero followed by a
    nonzero is not evidence of a missing emitter: checking actual emitters and
    per-organisation paths is required. Preserve the field for older callers,
    but never label a legitimate paid-first branch as broken instrumentation.
    """
    return [dict(step, unwired=False) for step in steps]


def acquisition_cohort(since, *, until=None) -> dict:
    """Observed outcomes of the SAME signup cohort, not adjacent step ratios.

    Paid-first and free-first paths are both valid. Outcomes are independently
    measured against signup organisations; no strict lease/mask/payment ordering
    is assumed. A click or signup isn't a qualified lead, first_mask isn't a
    successful tool loop, and a recent cohort is not mature retention evidence.
    """
    from django.utils import timezone
    from accounts.models import Organization
    from ops.analytics_models import Funnel

    until = until or timezone.now()
    starts = {}
    entries = (Funnel.objects.filter(step=Funnel.SIGNUP_SUBMITTED,
                                    at__gte=since, at__lte=until)
               .exclude(organization_id="").order_by("at")
               .values_list("organization_id", "at"))
    for organisation, at in entries:
        starts.setdefault(organisation, at)
    # Our explicit QA source is excluded, never guess that organic/direct
    # visitors are employees or that every low-volume source is a test.
    organisations = Organization.objects.filter(id__in=starts)
    qa_ids = set(organisations.filter(source_utm_source="qa_r01")
                 .values_list("id", flat=True))
    real_ids = set(organisations.exclude(id__in=qa_ids).values_list("id", flat=True))
    outcomes = [(code, title) for code, title in Funnel.STEPS
                if code not in {Funnel.LANDING, Funnel.SIGNUP_SUBMITTED,
                                Funnel.SIGNUP_REFUSED}]
    seen = {code: set() for code, _ in outcomes}
    rows = (Funnel.objects.filter(organization_id__in=real_ids, at__lte=until)
            .values_list("organization_id", "step", "at"))
    for organisation, code, at in rows:
        if code in seen and at >= starts[organisation]:
            seen[code].add(organisation)
    size = len(real_ids)
    return {
        "size": size, "excluded_qa": len(qa_ids),
        "orphan_signup_events": len(set(starts) - real_ids - qa_ids),
        "since": since, "until": until,
        "outcomes": [{"code": code, "title": title, "count": len(seen[code]),
                      "rate": round(len(seen[code]) / size * 100, 1) if size else None}
                     for code, title in outcomes],
    }
