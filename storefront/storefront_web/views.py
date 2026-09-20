"""The pages.

The site is three things and nothing else: a landing, a way to sign up, and a
cabinet with keys, usage and invoices. There is deliberately no screen here that
shows a dialogue, a token or a value — see `pseudex/localui/` for those. That
absence is the product's legal position, not a missing feature, so a view added
later must be checked against it rather than against convenience.
"""

import json
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts import payer
from accounts.models import Membership, Organization
from billing import onboarding, licensing, payments, services
from accounts.models import User
from billing.models import Invoice, LicenseKey, Plan, Subscription
from ops.analytics_models import Funnel
from ops.models import DemandDay
from storefront_web import detection_types

_log = logging.getLogger("storefront")


def _organization(request) -> Organization:
    # Oldest membership, not an arbitrary row. `.first()` on an unordered
    # queryset returns whatever the database feels like, so a user who belongs
    # to two organisations would see them alternate between requests.
    membership = (Membership.objects
                  .filter(user=request.user)
                  .select_related("organization")
                  .order_by("created_at")
                  .first())
    if membership is None:
        # A signed-in user with no organisation is not an error, it is someone
        # who came in through allauth's own sign-up form instead of ours. Both
        # larger persona clients did exactly that — it is the most prominent
        # button on the page — and were shown a raw Django 404 with the whole
        # URLconf on it. Send them where the account is actually created.
        raise NoOrganization
    return membership.organization


class NoOrganization(Exception):
    """Signed in, but never completed sign-up. Handled, not an error page."""


# Sign-ups per client address per window. Kept in the cache rather than the
# database: this is throttling, and a throttle that writes a row per attempt is
# itself the amplification it exists to prevent.
_SIGNUP_LIMIT = 3
_SIGNUP_WINDOW_SECONDS = 600


def _client_ip(request) -> str:
    # Behind our own Caddy, which sets X-Real-IP. Only the FIRST hop is trusted;
    # X-Forwarded-For is caller-controlled and taking the last entry lets anyone
    # pick their own throttle bucket.
    return (request.META.get("HTTP_X_REAL_IP")
            or request.META.get("REMOTE_ADDR", "unknown"))


def _too_many(request, kind: str, limit: int, window: int) -> bool:
    """Счётчик на IP в окне. ОДНА реализация на все анонимные записи.

    Их было две с одинаковыми восемью строками (регистрация и вебхук), и третья
    копия ради конфигуратора была бы третьим местом, где живёт одна и та же
    тонкость: `add` перед `incr`, чтобы окно начиналось с ПЕРВОЙ попытки и не
    продлевалось следующими — иначе ровный ручеёк держит ключ живым вечно и
    вызывающий заперт навсегда.
    """
    bucket = f"{kind}:{_client_ip(request)}"
    if cache.get(bucket, 0) >= limit:
        return True
    cache.add(bucket, 0, window)
    try:
        cache.incr(bucket)
    except ValueError:
        cache.set(bucket, 1, window)
    return False


def _funnel(step: str, detail: str = "", request=None, organization=None) -> None:
    """Отметить шаг воронки. НИКОГДА не ломает путь клиента.

    Аналитика — не то, ради чего человек пришёл. Упавшая запись обязана стоить
    строки в логе, а не отказа в регистрации.
    """
    try:
        visitor = ""
        if request is not None:
            from ops import collect
            visitor = collect.fingerprint(
                request.get_host(), collect.client_ip(request.META),
                request.META.get("HTTP_USER_AGENT", ""))
        Funnel.objects.create(
            step=step, detail=detail[:64], visitor=visitor,
            organization_id=(organization.id if organization is not None else ""))
        # ОДНА СТРОКА ЗДЕСЬ — И КАЖДЫЙ ШАГ ПУТИ КЛИЕНТА В ЛОГЕ. Регистрация,
        # отказ формы с причиной, активация, выпуск ключа проходят через эту
        # функцию; логировать их по месту значило бы семь мест, из которых одно
        # забудут. Почты здесь нет намеренно — только организация и шаг.
        _log.info("funnel step", extra={
            "step": step, "detail": detail[:64],
            "org": organization.id if organization is not None else ""})
    except Exception:  # noqa: BLE001 — см. докстроку
        _log.warning("не удалось отметить шаг воронки %s", step, exc_info=True)


def _too_many_signups(request) -> bool:
    return _too_many(request, "signup", _SIGNUP_LIMIT, _SIGNUP_WINDOW_SECONDS)


# ЮKassa payment ids are UUIDs. Anything else cannot be one of ours, so it is
# refused before it can cost us a network call.
_PAYMENT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_WEBHOOK_LIMIT = 60
_WEBHOOK_WINDOW_SECONDS = 60


def _too_many_webhooks(request) -> bool:
    return _too_many(request, "webhook", _WEBHOOK_LIMIT, _WEBHOOK_WINDOW_SECONDS)


# ── СПРОС НА ТИПЫ, КОТОРЫХ МЫ НЕ НАХОДИМ ────────────────────────────────────
#
# Лимиты щедрее регистрационных: здесь ничего не выпускается и ничего не стоит,
# а строка в базе одна на сутки и группу независимо от числа обращений.
_DEMAND_LIMIT = 30
_DEMAND_WINDOW_SECONDS = 300
# ПОДПИСАННАЯ КУКА, А НЕ СЕССИЯ, И ЭТО НЕ МЕЛОЧЬ. Первая версия писала флаг в
# `request.session`, а сессия у анонима — это СТРОКА В БАЗЕ: каждый посетитель,
# нажавший кнопку, оставлял запись в `django_session`, никакой `clearsessions`
# её не убирал, и главное — соседний докстринг в `ops/models.py` обещает «ни
# адреса, ни отпечатка, ни идентификатора сессии». Обещание было неправдой на
# соседней строке.
#
# Подписанная кука хранит то же самое У ПОСЕТИТЕЛЯ: сервер не запоминает о нём
# ничего, подделать её нельзя (подпись ключом сайта), а испорченную мы просто
# игнорируем — худшее, что даёт подделка, это лишняя единица в счётчике, ради
# которой проще нажать кнопку в новом окне.
_DEMAND_COOKIE = "demand_marked"


@require_POST
def demand(request):
    """Отметки конфигуратора — счётчиком, без строки о посетителе.

    ПОЧЕМУ ЭТО ВООБЩЕ ПИШЕТСЯ НА СЕРВЕР, если вердикт считается в браузере.
    Вердикт — да, а вот ЧТО ЛЮДИ СПРАШИВАЮТ, в браузере не остаётся. Страница
    /detection дважды обещала «напишите — это меняет очередь работ», и писать
    было некуда: адреса для связи на сайте нет. Отметка и есть то письмо.

    НИ ТЕКСТА, НИ ПОЧТЫ. Текста — потому что это приём чужих персональных данных
    на наш сервер, ровно то, что мы продаём не делать (`landing` докстринг, ТЗ
    вертикалей §4.4). Почты — потому что цель сайта «15 минут от лендинга до
    первого замаскированного запроса» (`docs/tz-site.md` §0), и вторая форма,
    конкурирующая с регистрацией, эти минуты удлиняет.

    НЕИЗВЕСТНЫЙ КОД ОТВЕРГАЕТСЯ, А НЕ ЗАПИСЫВАЕТСЯ. Иначе таблица, по которой
    строится очередь работ, наполняется тем, что придумал вызывающий.
    """
    if _too_many(request, "demand", _DEMAND_LIMIT, _DEMAND_WINDOW_SECONDS):
        return HttpResponse(status=429)

    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponse(status=400)
    # `[]`, `5`, `"x"` и `null` — ВАЛИДНЫЙ JSON, и у них нет `.get`. Без этой
    # строки любой из них давал 500 вместо 400: анонимная ручка, роняющая
    # обработчик телом из одного символа.
    if not isinstance(payload, dict):
        return HttpResponse(status=400)
    asked = payload.get("groups")
    if not isinstance(asked, list):
        return HttpResponse(status=400)
    # Длина ограничена ДО разбора: список из миллиона строк не должен доходить
    # до множества, даже если каждая из них будет отвергнута.
    if len(asked) > len(detection_types.CODES):
        return HttpResponse(status=400)
    codes = {code for code in asked if isinstance(code, str)}
    if not codes or not codes <= detection_types.CODES:
        return HttpResponse(status=400)

    today = timezone.localdate()
    stamp = today.isoformat()
    try:
        marked = request.get_signed_cookie(_DEMAND_COOKIE, default="")
    except Exception:                               # noqa: BLE001 — подпись не сошлась
        marked = ""
    # Формат «дата:код,код». Дата внутри самой куки: со сменой суток прежние
    # отметки перестают учитываться, и один человек может сказать то же самое
    # завтра — спрос это поток, а не разовая перепись.
    day, _, listed = marked.partition(":")
    already = set(listed.split(",")) if day == stamp and listed else set()
    fresh = sorted(codes - already)

    response = HttpResponse(status=204)
    if not fresh:
        return response
    for code in fresh:
        row, _created = DemandDay.objects.get_or_create(day=today, group=code)
        DemandDay.objects.filter(pk=row.pk).update(count=F("count") + 1)
    response.set_signed_cookie(
        _DEMAND_COOKIE, f"{stamp}:{','.join(sorted(already | set(fresh)))}",
        max_age=86400, samesite="Lax", secure=not settings.DEBUG, httponly=True)
    return response


def landing(request):
    """The public page. The demo on it runs on PREPARED examples and has no
    free-text input: an input field here would mean accepting other people's
    personal data onto our servers, which is precisely what we sell not doing."""
    return render(request, "landing.html", {
        "plans": Plan.objects.filter(is_public=True),
        # Enterprise намеренно НЕ публичный (его нельзя купить самообслуживанием,
        # см. seed_plans), поэтому он не в `plans` — иначе попал бы и в выпадашку
        # регистрации. Отдаётся отдельно ради одной карточки «по договору».
        "enterprise": Plan.objects.filter(code="enterprise").first(),
        # Группы конфигуратора — из того же реестра, что и страница /detection.
        "groups": detection_types.groups_for_page(),
        # ЧИСЛО ТИПОВ СЧИТАЕТСЯ, А НЕ ПИШЕТСЯ. «18» стояло литералом в трёх
        # местах, пока список был разметкой; теперь список — данные, и
        # следующий добавленный тип сделал бы страницу противоречащей
        # собственной таблице.
        "found_count": len(detection_types.FOUND),
        **_meta("landing"),
        "trial_days": services.trial_days(),
        "due_days": services.INVOICE_DUE_DAYS,
        "grace_days": services.GRACE_DAYS,
        "image": settings.DOCKER_IMAGE,
        "license_url_env": (f"-e PSEUDEX_LICENSE_URL={settings.LICENSE_URL} "
                            if settings.LICENSE_URL else ""),
        # The same prompt the welcome page hands out, with the key as a
        # placeholder. It belongs HERE too: "paste this and it connects itself"
        # is the strongest thing we can say about setup, and saying it only
        # after registration means the people deciding whether to register
        # never hear it.
        "claude_prompt": onboarding.claude_prompt(
            "ps_live_…  (подставится после регистрации)",
            settings.DOCKER_IMAGE, "8081", settings.LICENSE_URL),
    })


# ЗАГОЛОВКИ И ОПИСАНИЯ ПУБЛИЧНЫХ СТРАНИЦ — ЗДЕСЬ, ОДНОЙ ТАБЛИЦЕЙ.
#
# Они нужны в трёх местах сразу: в `<title>`, в `og:title` и в карточке для
# мессенджеров, — а блоком шаблона значение подставляется ровно в одно. Три
# блока означали бы три копии одного текста, и разъехались бы они молча: в
# выдаче это видно, а на экране нет.
#
# ЧТО В НИХ НАПИСАНО, ТОЖЕ НЕ СЛУЧАЙНО. Запрос нашей аудитории звучит не
# «токенизация ПД», а «152-ФЗ и нейросети», «персональные данные в ChatGPT»,
# «обезличивание персональных данных» — словами закона и задачи, а не названием
# технологии. Описание — это то, что человек прочитает в выдаче ВМЕСТО страницы,
# поэтому в нём стоит суть и цена, а не обещание «узнать больше».
_META = {
    "landing": (
        "Pseudex — маскирование персональных данных для LLM-агентов по 152-ФЗ",
        "Шлюз обезличивания персональных данных перед языковой моделью: модель "
        "видит подмену, а ваши инструменты получают настоящие значения. "
        "Контейнер работает в вашем контуре, наружу уходят только счётчики. "
        "СНИЛС и ИНН — по контрольной сумме. От 990 ₽ в месяц."),
    "detection": (
        "Какие персональные данные находит Pseudex — и чего не находит",
        "ФИО в падежах, телефон, email, адрес, дата рождения, СНИЛС, ИНН, "
        "паспорт, ОМС, банковская карта и счёт, госномер, IP — с контрольными "
        "суммами и русской морфологией. И честный список того, что пока не "
        "находим."),
    "architecture": (
        "Архитектура Pseudex для службы безопасности: почему мы не обработчик ПД",
        "Где проходит граница обработки персональных данных, что уходит за "
        "периметр (только агрегатные счётчики), как устроены волт, аренда "
        "словарей детекции и режим fail-closed. Документ для ИБ и комплаенса."),
    "offer": (
        "Публичная оферта Pseudex — лицензионный договор",
        "Условия, на которых предоставляется право использования программы: "
        "предмет, цена, порядок оплаты, ответственность и порядок работы "
        "лицензии."),
    "policy": (
        "Политика обработки персональных данных — Pseudex",
        "Какие персональные данные мы обрабатываем как оператор, зачем, сколько "
        "храним и как их отозвать. Данные ваших клиентов к нам не поступают."),
    "consent": (
        "Согласие на обработку персональных данных — Pseudex",
        "Текст согласия по ст. 9 152-ФЗ отдельным документом: перечень данных, "
        "цели обработки, срок и порядок отзыва."),
    "requisites": (
        "Реквизиты Pseudex",
        "Наименование, место нахождения, ИНН и адрес электронной почты "
        "владельца сайта — ст. 10 ч. 2 ФЗ «Об информации» и ст. 26.1 ЗоЗПП."),
}


def _meta(page: str) -> dict[str, str]:
    title, description = _META[page]
    return {"page_title": title, "page_description": description}


# ПУБЛИЧНЫЕ АДРЕСА — ОДНИМ СПИСКОМ, и карта сайта строится из него.
#
# Карта, написанная руками, устаревает в тот день, когда появляется страница:
# новый адрес про неё не знает, а робот не знает про адрес. Здесь же живёт
# ответ на «что вообще индексируется», и он совпадает с `indexable` в контексте
# шаблона по построению — закрытых страниц в списке просто нет.
_PUBLIC_PAGES = (
    ("landing", 1.0, "weekly"),
    ("detection", 0.8, "monthly"),
    ("architecture", 0.7, "monthly"),
    ("offer", 0.4, "yearly"),
    ("policy", 0.4, "yearly"),
    ("consent", 0.4, "yearly"),
    ("requisites", 0.3, "yearly"),
)


def robots(request):
    """`robots.txt`: что можно обходить, и где лежит карта.

    ЗАПРЕЩАЕТСЯ РОВНО ЗАКРЫТОЕ. Кабинет, админка и экраны входа не должны
    попадать в выдачу — там ключи, суммы счетов и чужие названия, — но запрет
    здесь это ПРОСЬБА, а не защита: `noindex` в шапке страницы и настоящая
    авторизация делают работу, а `robots.txt` лишь бережёт краулинговый бюджет.
    Считать его защитой — классическая ошибка: файл публичный и сам называет
    адреса, которые просит не смотреть.
    """
    admin_path = settings.ADMIN_PATH
    lines = [
        "User-agent: *",
        "Disallow: /app/",
        f"Disallow: /{admin_path}/",
        "Disallow: /accounts/",
        "Disallow: /signup",
        "Disallow: /activate",
        "Disallow: /welcome",
        "Disallow: /demand",
        "Allow: /",
        "",
        # Яндекс читает Clean-param и склеивает адреса с этими параметрами в
        # один. Без него наша же реклама плодит дубли главной: каждая ссылка из
        # кампании это отдельный адрес с тем же содержимым.
        "Clean-param: utm_source&utm_medium&utm_campaign&utm_term&utm_content&yclid&gclid",
        "",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap(request):
    """Карта сайта. Строится из `_PUBLIC_PAGES`, а не пишется руками."""
    from django.urls import reverse
    from django.utils.html import escape
    rows = []
    for name, priority, freq in _PUBLIC_PAGES:
        rows.append(
            f"  <url>\n"
            f"    <loc>{escape(settings.SITE_URL + reverse(name))}</loc>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>")
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")
    return HttpResponse(body, content_type="application/xml; charset=utf-8")


def _legal_context() -> dict[str, object]:
    """Shared by all three legal pages.

    The date is the file's own last change, not `today`: a policy that claims to
    have been revised this morning every morning tells the reader nothing, and a
    regulator reads the revision date as a fact.
    """
    import datetime
    import pathlib as _pathlib
    here = _pathlib.Path(__file__).resolve().parent.parent / "templates" / "legal"
    stamps = [f.stat().st_mtime for f in here.glob("*.html")] or [0]
    return {
        "seller": settings.SELLER,
        "trial_days": services.trial_days(),
        "due_days": services.INVOICE_DUE_DAYS,
        "grace_days": services.GRACE_DAYS,
        "updated": datetime.date.fromtimestamp(max(stamps)).strftime("%d.%m.%Y"),
    }


def favicon(request):
    """Отдать `/favicon.ico` НАСТОЯЩИМ файлом, кодом 200.

    ЗДЕСЬ БЫЛ 301 НА `/static/favicon.svg`, И ЭТО РОВНО ТА ОШИБКА, КОТОРУЮ
    НАЗЫВАЕТ ВЕБМАСТЕР. В его таблице причин у иконки есть отдельная строка —
    «файл перенаправляет на другой адрес», — и проверка 17.09.2026 ответила:
    «Добавьте файл favicon в формате SVG или размером 120 × 120 пикселей».

    Раньше редирект был осмысленным: он уводил запрос робота от 404, а 404 на
    этом сайте кормит счётчик fail2ban, который банит на уровне пакетов. Но 404
    и 301 — не одно и то же: 404 робот просто отмечает, а 301 считает ошибкой и
    иконку не берёт. Файл теперь отдаётся, а не переадресуется.

    ИКОНКА ЛЕЖИТ В `static/`, ХОТЯ АДРЕС КОРНЕВОЙ. Справка требует файл с
    именем `favicon` в корне сайта, но рядом же разрешает ссылку из `<head>` на
    любой адрес. Здесь и то и другое: `/favicon.ico` отвечает 200 и остаётся
    одним файлом с остальными иконками, а не второй копией.

    ВЕКТОРНАЯ ИКОНКА ОСТАЁТСЯ ГЛАВНОЙ — она в разметке первой, и браузеры
    берут её. Этот файл нужен тем, кто просит корневой `.ico` сам: старым
    браузерам, закладкам и роботу YandexFavicons.
    """
    import pathlib as _pathlib
    path = (_pathlib.Path(__file__).resolve().parent.parent
            / "static" / "favicon.ico")
    response = FileResponse(path.open("rb"), content_type="image/x-icon")
    # Сутки: иконка меняется раз в год, а запрашивает её каждый новый посетитель.
    response["Cache-Control"] = "public, max-age=86400"
    return response


def favicon_svg(request):
    """Отдать `/favicon.svg` из корня — вторая дверь к той же иконке.

    Вебмастер называет SVG РЕКОМЕНДУЕМЫМ форматом, а справка просит положить
    файл с именем `favicon` в корень сайта. Корневой `.ico` у нас есть и
    отвечает 200; векторный лежит в `static/` и объявлен ссылкой в `<head>`, а
    это справка тоже разрешает. Адрес в корне стоит трёх строк и снимает
    вопрос «а какой именно файл искал робот» — при том что оба формата
    нарисованы из одного исходника и не могут разойтись.
    """
    import pathlib as _pathlib
    path = (_pathlib.Path(__file__).resolve().parent.parent
            / "static" / "favicon.svg")
    response = FileResponse(path.open("rb"), content_type="image/svg+xml")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def consent(request):
    """Текст согласия на обработку ПД — отдельным документом.

    ОТДЕЛЬНЫМ, А НЕ АБЗАЦЕМ В ОФЕРТЕ: ст. 9 152-ФЗ требует, чтобы согласие было
    конкретным и информированным, а РКН последовательно читает это как «не
    смешанное с другими документами». Согласие, спрятанное в п. 7.3 договора,
    признаётся не полученным.
    """
    return render(request, "legal/consent.html", {
        "seller": settings.SELLER,
        "revision": settings.SELLER.get("consent_revision", ""),
        **_meta("consent"),
    })


def requisites(request):
    """Сведения о владельце сайта — ст. 10 ч. 2 ФЗ «Об информации».

    Владелец сайта обязан разместить наименование, место нахождения и адрес
    электронной почты. Для дистанционной продажи то же требует ст. 26.1 ЗоЗПП:
    покупатель должен видеть, КОМУ он платит, до того как заплатит.
    """
    return render(request, "legal/requisites.html",
                  {"seller": settings.SELLER, **_meta("requisites")})


def offer(request):
    return render(request, "legal/offer.html", _legal_context() | _meta("offer"))


def policy(request):
    return render(request, "legal/policy.html", _legal_context() | _meta("policy"))


def architecture(request):
    return render(request, "legal/architecture.html",
                  _legal_context() | _meta("architecture"))


def detection(request):
    """What the engine finds, and what it does not.

    Split out of the landing because three of five persona-clients independently
    asked for the list behind the number, and because the architecture page
    promised published defects with nothing to click. A count with no list reads
    as a marketing counter; a promise of transparency with no page is worse than
    saying nothing."""
    # СПИСКИ ПРИЕЗЖАЮТ ИЗ РЕЕСТРА, а не лежат разметкой: те же факты нужны
    # конфигуратору на лендинге, и два экземпляра одного утверждения расходятся.
    return render(request, "legal/detection.html", _legal_context() | _meta("detection") | {
        "found": detection_types.found_rows(),
        "missing": detection_types.missing_numbered(),
    })


def resend_activation(request):
    """Send the activation link again.

    The persona run stopped dead here: the letter is the ONLY way forward, there
    was no way to ask for another one, and the support channel is email — the
    same channel that had just failed. A single point of failure with no retry is
    not a small gap in a funnel whose first step it is.

    Deliberately says the same thing whether or not the address has an account.
    Answering honestly would turn this into a way to ask the site which of a list
    of addresses is a customer.
    """
    if request.method != "POST":
        return redirect("landing")
    email = (request.POST.get("email") or "").strip().lower()
    organization = services.pending_organization(email)
    if organization is not None:
        link = request.build_absolute_uri(
            "/activate?t=" + signing.dumps({"org": organization.id, "email": email})
        )
        send_mail(
            subject="pseudex — ваш ключ готов к выпуску",
            message=(
                f"Здравствуйте!\n\n"
                f"Вы попросили прислать ссылку ещё раз. Ключ будет выпущен и "
                f"показан один раз, когда вы её откроете:\n\n{link}\n\n"
                f"Ссылка действует {_ACTIVATION_HOURS} часа."
            ),
            from_email=None,
            recipient_list=[email],
            fail_silently=False,
        )
    return render(request, "check_email.html", {"email": email, "resent": True})


def signup(request):
    """Email, company name, plan. Three fields, and the key exists at the end of
    the post — before payment, before any confirmation click."""
    if request.method != "POST":
        return redirect("landing")
    email = (request.POST.get("email") or "").strip().lower()
    name = (request.POST.get("company") or "").strip()
    plan_code = request.POST.get("plan") or "start"
    if not email or "@" not in email:
        messages.error(request, "Нужен рабочий email.")
        return redirect("landing")

    # Sign-up is the DEAREST unauthenticated write on the site — `demand` below
    # is the other one — and every call MINTS A KEY on the licensing server.
    # Unthrottled, a loop would fill that database — the one whose loss stops
    # every customer in the field — with junk, for free, from anywhere.
    #
    # («the only unauthenticated write» стояло здесь до конфигуратора. Вторая
    # появилась, и утверждение поправлено вместе с ней: комментарий, ставший
    # неправдой, опаснее отсутствующего — по нему принимают решения.)
    if _too_many_signups(request):
        _funnel(Funnel.SIGNUP_REFUSED, "троттлинг", request)
        messages.error(request, "Слишком много попыток. Подождите минуту.")
        return redirect("landing")

    # Отказ НАЗЫВАЕТ причину и что делать: человек с одноразовым ящиком чаще
    # всего просто осторожен, а не злоупотребляет, и «попробуйте ещё раз» без
    # объяснения выгнало бы его насовсем.
    # СОГЛАСИЕ ПРОВЕРЯЕТСЯ НА СЕРВЕРЕ, А НЕ ТОЛЬКО АТРИБУТОМ `required`.
    # `required` живёт в браузере и снимается через инструменты разработчика за
    # две секунды; ст. 9 152-ФЗ требует, чтобы оператор МОГ ДОКАЗАТЬ получение
    # согласия, а доказать можно только тем, что без него запись не создаётся.
    if request.POST.get("consent") != "1":
        _funnel(Funnel.SIGNUP_REFUSED, "без согласия", request)
        messages.error(request, "Без согласия на обработку персональных данных "
                                "аккаунт создать нельзя — это требование "
                                "152-ФЗ, а не формальность с нашей стороны.")
        return redirect("landing")
    # ДОГОВОР — ВТОРАЯ ГАЛОЧКА, И ОНА НЕ СОГЛАСИЕ. С 01.09.2025 согласие на
    # обработку ПД оформляется отдельно от любого другого документа (ч. 1 ст. 9
    # 152-ФЗ в ред. 156-ФЗ), поэтому «даю согласие и принимаю оферту» одной
    # галочкой — совмещённое согласие, то есть отсутствие согласия. Акцепт
    # оферты проверяется тем же способом и по той же причине: доказывать его
    # придётся нам.
    if request.POST.get("terms") != "1":
        _funnel(Funnel.SIGNUP_REFUSED, "без акцепта оферты", request)
        messages.error(request, "Чтобы выпустить ключ, нужно принять оферту — "
                                "это договор, по которому вы получаете право "
                                "использовать программу.")
        return redirect("landing")

    if services.is_disposable(email):
        _funnel(Funnel.SIGNUP_REFUSED, "одноразовая почта", request)
        messages.error(request, "На одноразовые почтовые ящики ключ не "
                                "выпускается — ссылка на активацию до вас не "
                                "дойдёт. Укажите рабочий адрес: пробный период "
                                "всё равно бесплатный и карта не нужна.")
        return redirect("landing")

    # An email that already has an organisation goes to sign-in instead of
    # getting a second one. Two reasons, and the second is what matters: a
    # person who signs up twice would end up with two orgs and see only one of
    # them, and anyone could otherwise attach organisations to a stranger's
    # address by typing it into this form.
    if Membership.objects.filter(user__email=email).exists():
        _funnel(Funnel.SIGNUP_REFUSED, "уже зарегистрирован", request)
        messages.info(request, "Такой email уже зарегистрирован — войдите по ссылке "
                               "на почту, ключи в кабинете.")
        return redirect("account_login")

    if not Plan.objects.filter(code=plan_code, is_public=True).exists():
        messages.error(request, "Такого тарифа нет.")
        return redirect("landing")

    # The account is created now; the KEY is not. A live licence key opens the
    # customer's whole gateway, and handing one to whoever typed an address let
    # anyone claim a stranger's email, take the key, and leave the stranger to
    # sign in later into the attacker's organisation with the attacker's key
    # still active inside it.
    #
    # The link below is the proof of the mailbox, and it carries NO key — only a
    # signed reference to the account. Nothing secret is ever put in an email.
    organization = services.create_account(email, name, plan_code,
                                           _client_ip(request))
    # Факт, а не галочка: момент и РЕДАКЦИЯ текста, на которую согласились.
    _funnel(Funnel.SIGNUP_SUBMITTED, plan_code, request, organization)
    organization.consent_at = timezone.now()
    organization.consent_revision = settings.SELLER.get("consent_revision", "")
    fields = ["consent_at", "consent_revision"]

    # ПЕРВОЕ КАСАНИЕ ПЕРЕЕЗЖАЕТ НА ОРГАНИЗАЦИЮ ИМЕННО ЗДЕСЬ И БОЛЬШЕ НИКОГДА.
    # Это единственный момент, когда обе половины существуют одновременно:
    # суточный отпечаток посетителя ещё жив, а организация уже создана. Через
    # сутки соль уничтожена, и вопрос «какая кампания привела этого клиента»
    # ответа не имеет — поэтому запись не может быть отложена на потом.
    try:
        from ops import collect
        touch = collect.first_touch(
            collect.fingerprint(request.get_host(),
                                collect.client_ip(request.META),
                                request.META.get("HTTP_USER_AGENT", "")),
            since_hours=24)
        for field, value in touch.items():
            setattr(organization, field, value)
            fields.append(field)
    except Exception:  # noqa: BLE001 — аналитика не ломает регистрацию
        _log.warning("не удалось определить источник регистрации", exc_info=True)

    organization.save(update_fields=fields)
    link = request.build_absolute_uri(
        "/activate?t=" + signing.dumps({"org": organization.id, "email": email})
    )
    send_mail(
        subject="pseudex — ваш ключ готов к выпуску",
        message=(
            f"Здравствуйте!\n\n"
            f"Аккаунт создан. Ключ будет выпущен и показан один раз, когда вы "
            f"откроете ссылку:\n\n{link}\n\n"
            f"Ссылка действует {_ACTIVATION_HOURS} часа. Если это были не вы — "
            f"просто не открывайте её, ничего не произошло."
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )
    # ЦЕЛЬ «РЕГИСТРАЦИЯ» СЧИТАЕТСЯ ЗДЕСЬ, А НЕ НА ПОВТОРНОЙ ОТПРАВКЕ ПИСЬМА.
    # Экран тот же самый, и `resent` отличает один случай от другого: человек,
    # попросивший письмо второй раз, уже зарегистрирован, и засчитанная ему
    # цель удвоила бы регистрацию в отчёте. Цель уходит из браузера, то есть
    # только при согласии на счётчик — так же, как обещает раздел 9bis политики.
    return render(request, "check_email.html",
                  {"email": email, "metrika_goal": "signup"})


_ACTIVATION_HOURS = 24


def activate(request):
    """Issue the key, once, to whoever proved they hold the mailbox."""
    try:
        token = request.POST.get("t") or request.GET.get("t", "")
        payload = signing.loads(token,
                                max_age=_ACTIVATION_HOURS * 3600)
    except (signing.BadSignature, signing.SignatureExpired):
        messages.error(request, "Ссылка недействительна или устарела. "
                                "Зарегистрируйтесь заново — это займёт минуту.")
        return redirect("landing")

    organization = Organization.objects.filter(id=payload["org"]).first()
    if organization is None:
        return redirect("landing")

    # ВХОД ПО ССЫЛКЕ — ЭТО GET, А GET ПОДДЕЛЫВАЕТСЯ ЧУЖИМ САЙТОМ. Ссылка
    # активации — работающий логин на 24 часа, и раньше она входила в сессию
    # прямо на переходе. `SESSION_COOKIE_SAMESITE = "Lax"` НАМЕРЕННО разрешает
    # ставить cookie на кросс-сайтовой навигации верхнего уровня, поэтому
    # злоумышленник, зарегистрировавшись сам, мог подсунуть свою ссылку клиенту:
    # сессия жертвы затиралась, и дальше жертва платила его счёт своей картой.
    #
    # Поэтому GET только ПОКАЗЫВАЕТ форму, а вход делает POST с CSRF-токеном.
    # Одна лишняя кнопка на регистрации против смены личности по ссылке.
    if request.method != "POST":
        return render(request, "activate.html",
                      {"token": request.GET.get("t", ""),
                       "email": payload["email"]})
    # И личность не подменяется молча: если в браузере уже кто-то другой, мы
    # об этом говорим, а не переключаем под ним стул.
    current = getattr(request, "user", None)
    if (current is not None and current.is_authenticated
            and current.email.lower() != str(payload["email"]).lower()):
        messages.error(request, "В этом браузере уже открыт другой аккаунт. "
                                "Выйдите из него и откройте ссылку снова.")
        return redirect("cabinet")
    # Following the link twice must not mint a second key: the first one was
    # shown once and the customer may already be running it.
    if organization.keys.filter(revoked_at__isnull=True).exists():
        # Sending them back for ANOTHER letter was absurd: they arrived by
        # clicking a link in the mailbox we were asking them to check again.
        _sign_in(request, payload["email"])
        messages.info(request, "Ключ уже был выпущен и показан один раз. "
                               "Здесь виден его префикс и расход; если ключ "
                               "потерян — выпустите новый.")
        return redirect("cabinet")
    try:
        _funnel(Funnel.ACTIVATED, "", request, organization)
        key = services.issue_first_key(organization)
        _funnel(Funnel.KEY_ISSUED, "", request, organization)
    except licensing.LicensingError as error:
        _log.error("issuing a key for %s failed: %s", organization.id, error)
        messages.error(request, "Не удалось выпустить ключ — это на нашей стороне. "
                                "Напишите нам, и мы выпустим его вручную.")
        return redirect("landing")
    # The link already proved the mailbox — the same proof a passwordless
    # sign-in link carries. Not spending it on a session meant a new customer
    # needed TWO letters to reach the cabinet: one to get the key, another to
    # log in and see it listed. Both personas stopped before the second.
    _sign_in(request, payload["email"])
    return _handoff(redirect("welcome"), key, organization.id)


def _sign_in(request, email: str) -> None:
    """Authenticate the session for a mailbox we have just verified.

    The backend is named explicitly because allauth's is not the only one
    configured, and `login()` refuses to guess when there is more than one.
    """
    user = User.objects.filter(email=email).first()
    if user is None:
        return
    auth_login(request, user,
               backend="allauth.account.auth_backends.AuthenticationBackend")


# Why a signed COOKIE and not the session. Django's default session backend
# writes session data to OUR database, so `session["fresh_key"] = key` would
# persist the full key in a table we control — defeating the entire point of
# storing only a prefix and a hash, and putting a customer's bearer credential
# somewhere a backup and a support query can reach.
#
# A signed cookie never touches our storage. It is short-lived, HttpOnly, and
# deleted the moment the page that shows it renders.
_HANDOFF_COOKIE = "ps_handoff"
_HANDOFF_MAX_AGE = 600


def _handoff(response, key: str, org_id: str):
    response.set_cookie(
        _HANDOFF_COOKIE,
        signing.dumps({"key": key, "org": org_id}),
        max_age=_HANDOFF_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
    )
    return response


def welcome(request):
    raw = request.COOKIES.get(_HANDOFF_COOKIE, "")
    try:
        payload = signing.loads(raw, max_age=_HANDOFF_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return redirect("landing")
    response = render(request, "welcome.html", {
        "key": payload["key"],
        "org_id": payload["org"],
        "image": settings.DOCKER_IMAGE,
        "license_url_env": (f"-e PSEUDEX_LICENSE_URL={settings.LICENSE_URL} "
                            if settings.LICENSE_URL else ""),
        "trial_days": services.trial_days(),
        "due_days": services.INVOICE_DUE_DAYS,
        "grace_days": services.GRACE_DAYS,
        # The key is injected into the prompt here, on the one page that is
        # allowed to show it in full. The cabinet cannot offer this: it only
        # keeps a prefix and a hash, by design.
        "claude_prompt": onboarding.claude_prompt(
            payload["key"], settings.DOCKER_IMAGE, "8081", settings.LICENSE_URL),
    })
    # Read once, and not cached. Deleting the cookie alone does NOT keep the key
    # out of the back-forward cache — only `no-store` disables it, so Back
    # re-displayed a live gateway credential. The middleware covers /app/ and
    # /admin/; this page is neither.
    response.delete_cookie(_HANDOFF_COOKIE)
    response["Cache-Control"] = "no-store"
    return response


@login_required
def cabinet(request):
    try:
        organization = _organization(request)
    except NoOrganization:
        messages.info(request, "Аккаунт создан, но организации ещё нет — "
                               "завершите регистрацию, и ключ выдастся сразу.")
        return redirect("/#start")
    subscription = getattr(organization, "subscription", None)
    try:
        reported = licensing.usage(organization.id).get("usage", {})
        unreachable = False
    except licensing.LicensingError:
        # The cabinet still renders. Counters are the one thing here that comes
        # from another service, and a page that 500s because a sidebar number is
        # unavailable is worse than a page that says the number is unavailable.
        reported, unreachable = {}, True
    if not isinstance(reported, dict):
        reported = {}
    # WHICH CONTAINERS HOLD A SLOT. The plan is sold in containers and the limit
    # is enforced on them, and until now the cabinet showed only the allowance.
    # A customer refused a lease was told to stop a container they had already
    # deleted; now they can see what the licensing server thinks is running.
    try:
        slots = licensing.instances(organization.id).get("instances", [])
    except licensing.LicensingError:
        slots = []
    if not isinstance(slots, list):
        slots = []
    # What is billed: protected values, from the monotonic accumulator. Requests
    # are shown beside it because the operator recognises them, but the bar
    # tracks the meter.
    used = int(reported.get("values", 0))
    requests = int(reported.get("requests", 0))
    # НА ПРОБЕ ПОКАЗЫВАЕМ ПРОБНЫЙ ТАРИФ, А НЕ ТОТ, ЧТО ПРИВЯЗАН.
    #
    # Регистрация привязывает к пробной подписке именно пробный тариф
    # (`services.start_trial` берёт `trial_plan()`), и для новых организаций эти
    # два совпадают. Но у аккаунтов, созданных ДО появления тарифа `free`, в
    # строке подписки остался платный `start` — и кабинет сообщал человеку, что
    # он на «Старте» за 990 ₽/мес, тогда как он не платит ничего.
    #
    # Чиним ПОКАЗ, а не данные: строка подписки хранит ещё и намерение клиента
    # (`intended_plan`), и переписывать её ради вида значило бы потерять то, что
    # он выбрал. Состояние подписки (`state == trial`) и есть признак, по
    # которому видно правду, и оно не зависит от того, какая строка тарифа
    # привязана.
    display_plan = subscription.plan if subscription else None
    if subscription is not None and subscription.state == Subscription.TRIAL:
        trial_plan = services.trial_plan()
        if trial_plan is not None:
            display_plan = trial_plan

    included = display_plan.included_requests if display_plan else 0
    # ЁМКОСТЬ: НА ЧЁМ СТРОИТСЯ СЧЁТ И ЧЕМ ОНО ЗАЖАТО. Клиент должен видеть обе
    # границы, потому что расстояние между ними — это ровно та скидка, которую
    # он получает за подтверждённые отчёты. Без этого фраза «отчёт — ваша
    # защита» остаётся обещанием.
    billable = int(reported.get("capacity_billable", 0) or 0)
    ceiling = int(reported.get("capacity_granted", 0) or 0)
    acknowledged = int(reported.get("capacity_acked", 0) or 0)
    unacked = int(reported.get("capacity_unacked_quanta", 0) or 0)
    # ЗОНА И ЦЕНА ЗА ПЕРИОД: «вот сколько включено, вот цена сверх, вот докуда
    # можно, вот что за буфером». Считается той же арифметикой, что и счёт
    # (`services.period_pricing`), чтобы полоса не расходилась с начислением.
    # Недоступный сервер — нет отчёта — нет зоны: показываем честное молчание,
    # а не ноль, который выглядит как «всё включено».
    pricing = None
    if subscription and not unreachable:
        pricing = services.period_pricing(organization, display_plan, reported)
    # ГОДОВАЯ ПРЕДОПЛАТА: цена и «что получишь». Показываем, если тариф её даёт
    # ИЛИ есть адресный annual-оффер, и пока база НЕ оплачена вперёд. Срок
    # сверяется С СЕЙЧАС, а не по правдивости даты: истёкшая дата иначе вечно
    # показывала бы «оплачено вперёд» и прятала кнопку продления.
    annual = None
    annual_prepaid_until = None
    if subscription:
        if (subscription.base_paid_through
                and timezone.now() < subscription.base_paid_through):
            annual_prepaid_until = subscription.base_paid_through
        elif services.annual_available(organization, subscription.plan):
            annual = services.annual_price(organization, subscription.plan)
    return render(request, "app/cabinet.html", {
        "instances": slots,
        "organization": organization,
        "subscription": subscription,
        # Тариф, который кабинет ПОКАЗЫВАЕТ: на пробе — пробный.
        "plan": display_plan,
        "keys": organization.keys.filter(revoked_at__isnull=True),
        "invoices": organization.invoices.all()[:12],
        "used": used,
        "requests": requests,
        "billable": billable,
        "ceiling": ceiling,
        "acknowledged": acknowledged,
        "unacked_quanta": unacked,
        # Сколько клиент НЕ платит благодаря тому, что его контейнеры
        # отчитываются. Ноль здесь значит, что отчёты не доходят.
        "capacity_discount": max(0, ceiling - billable),
        "included": included,
        "percent": min(100, round(billable / included * 100)) if included else 0,
        "pricing": pricing,
        "annual": annual,
        "annual_prepaid_until": annual_prepaid_until,
        "card_available": payments.is_available(),
        # ЧТО МОЖНО КУПИТЬ И ЧТО ПРЕДЛОЖИТЬ ПО УМОЛЧАНИЮ.
        #
        # `suggested_plan` — тариф, выбранный человеком ещё на лендинге
        # (`intended_plan`). Он сохранён ровно ради этой строки: подставить
        # выбранное вместо того, чтобы заставлять выбирать второй раз, и не
        # потерять намерение того, кто так и не заплатил.
        "paid_plans": Plan.objects.filter(is_public=True),
        "suggested_plan": (subscription.intended_plan_id
                           if subscription and subscription.plan.is_trial
                           else (subscription.plan_id if subscription else None)),
        "trial_over": bool(subscription and subscription.plan.is_trial
                           and subscription.trial_ends_at <= timezone.now()),
        "bonus_days": (services.bonus_days_for(
                           organization,
                           subscription.intended_plan or subscription.plan,
                           services.trial_has_been_used(reported))
                       if subscription else 0),
        "unreachable": unreachable,
        "image": settings.DOCKER_IMAGE,
        "license_url_env": (f"-e PSEUDEX_LICENSE_URL={settings.LICENSE_URL} "
                            if settings.LICENSE_URL else ""),
    })


@login_required
@require_POST
def new_key(request):
    organization = _organization(request)
    try:
        key = services.issue_additional_key(
            organization,
            label=(request.POST.get("label") or "").strip()[:100],
            environment=("test" if request.POST.get("environment") == "test" else "live"),
        )
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("cabinet")
    return _handoff(redirect("welcome"), key, organization.id)


@login_required
@require_POST
def revoke_key(request, key_id: int):
    organization = _organization(request)
    key = organization.keys.filter(id=key_id, revoked_at__isnull=True).first()
    if key is None:
        raise Http404("ключ не найден")
    if organization.keys.filter(revoked_at__isnull=True).count() <= 1:
        messages.error(request, "Это последний действующий ключ. Выпустите новый, "
                                "прежде чем отзывать этот — иначе сервис остановится.")
        return redirect("cabinet")
    # The licensing server FIRST. This used to set a local flag and report
    # success while the key kept leasing indefinitely — so an engineer who left
    # with a copy still held a working credential for the whole gateway, and the
    # screen said it was revoked. If the call fails the customer is told the
    # truth instead of a comforting message.
    try:
        licensing.revoke_key(key.key_hash)
    except licensing.LicensingError as error:
        _log.error("revoking %s failed: %s", key.prefix, error)
        messages.error(request, "Не удалось отозвать ключ на лицензионном сервере — "
                                "он всё ещё действует. Это на нашей стороне, напишите нам.")
        return redirect("cabinet")
    with transaction.atomic():
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
    # ОТЗЫВ — СОБЫТИЕ БЕЗОПАСНОСТИ, И ОНО ЛОГИРУЕТСЯ ПРИ УСПЕХЕ, НЕ ТОЛЬКО ПРИ
    # ПРОВАЛЕ: «кто и когда отозвал ключ» спрашивают, когда контейнер у
    # клиента встал, а никто не помнит, что нажимал.
    _log.warning("key revoked", extra={"org": organization.id, "key_prefix": key.prefix,
                                       "by": request.user.email})
    messages.success(request, f"Ключ {key.prefix}… отозван и больше не продлит аренду.")
    return redirect("cabinet")


@login_required
@require_POST
def update_payer(request):
    """The customer states who pays: юрлицо, ИП or физлицо, with реквизиты.

    Asked HERE and never at sign-up — the fifteen-minute promise on the landing
    dies the moment a form asks a company for its ИНН before it has decided to
    buy. But it must be askable somewhere the customer can reach: the счёт page
    used to say «напишите нам, и мы добавим», which made every invoice a
    support ticket and left every account a «юрлицо» by default.
    """
    organization = _organization(request)
    try:
        fields = payer.payer_fields(
            kind=request.POST.get("kind", ""),
            legal_name=request.POST.get("legal_name", ""),
            inn=request.POST.get("inn", ""),
            kpp=request.POST.get("kpp", ""),
            legal_address=request.POST.get("legal_address", ""),
        )
    except payer.PayerError as error:
        messages.error(request, str(error))
        return redirect("cabinet")
    for name, value in fields.items():
        setattr(organization, name, value)
    organization.save(update_fields=list(fields))
    messages.success(request, "Реквизиты плательщика сохранены.")
    return redirect("cabinet")


@login_required
def invoice_detail(request, number: str):
    organization = _organization(request)
    invoice = organization.invoices.filter(number=number).first()
    if invoice is None:
        raise Http404("счёт не найден")
    return render(request, "app/invoice.html", {
        "invoice": invoice,
        "organization": organization,
        # Card payment is offered only when it is actually wired up. For a
        # company or an ИП it is also the expensive route — the same money
        # arrives by transfer with no commission and no ККТ.
        "card_available": payments.is_available(),
    })


@login_required
@require_POST
def pay_invoice(request, number: str):
    """Send the customer to ЮKassa for this invoice."""
    organization = _organization(request)
    invoice = organization.invoices.filter(number=number).first()
    if invoice is None:
        raise Http404("счёт не найден")
    if invoice.state == Invoice.PAID:
        messages.info(request, "Этот счёт уже оплачен.")
        return redirect("invoice_detail", number=number)
    try:
        payment_id, confirmation = payments.create_payment(
            invoice,
            request.build_absolute_uri(f"/app/invoices/{number}"),
            request.user.email,
        )
    except payments.PaymentError as error:
        _log.error("payment for %s failed: %s", number, error)
        messages.error(request, "Не удалось начать оплату картой. Счёт можно "
                                "оплатить по реквизитам — форма ниже.")
        return redirect("invoice_detail", number=number)
    invoice.payment_ref = payment_id
    invoice.save(update_fields=["payment_ref"])
    return redirect(confirmation)


@login_required
@require_POST
def subscribe(request):
    """Оплатить тариф СЕЙЧАС — первый платёж или переход на другой тариф.

    ЧТО ЭТО ЧИНИТ. Заплатить было нельзя вовсе: `pay_invoice` оплачивает только
    существующий счёт, а счета выставляет месячный цикл — по окончании пробы или
    периода. Во время пробы счёта не существует, поэтому у человека, готового
    отдать деньги сегодня, не было ни одной кнопки, кроме годовой предоплаты.
    Смены тарифа не было тоже — ни вьюхи, ни адреса.

    Обе задачи здесь одна: «переведи меня на тариф X и возьми за него деньги».
    Счёт несёт тариф, а подписку переставляет `mark_paid` — по факту денег, а не
    по факту нажатия. Пока не заплачено, ничего не меняется: иначе кнопка
    «перейти на Промышленный» выдавала бы его лимиты всем желающим.

    Карта — не единственный путь. Когда эквайринг выключен или ЮKassa отказала,
    счёт всё равно ВЫСТАВЛЕН и его видно по реквизитам: юрлица в России платят
    по безналу чаще, чем картой, и терять их из-за отказа провайдера незачем.
    """
    organization = _organization(request)
    plan = Plan.objects.filter(code=request.POST.get("plan", ""),
                               is_public=True).first()
    if plan is None:
        messages.error(request, "Такого тарифа нет.")
        return redirect("cabinet")
    subscription = getattr(organization, "subscription", None)
    if subscription is not None and subscription.plan_id == plan.code \
            and subscription.state == Subscription.ACTIVE:
        messages.info(request, f"Вы уже на тарифе «{plan.title}».")
        return redirect("cabinet")

    invoice = services.build_switch_invoice(organization, plan)
    if not payments.is_available():
        messages.info(request, f"Счёт {invoice.number} выставлен — оплатите по "
                               "реквизитам, форма ниже. Картой сейчас нельзя.")
        return redirect("invoice_detail", number=invoice.number)
    try:
        payment_id, confirmation = payments.create_payment(
            invoice,
            request.build_absolute_uri(f"/app/invoices/{invoice.number}"),
            request.user.email,
        )
    except payments.PaymentError as error:
        _log.error("subscribe payment for %s failed: %s", organization.id, error)
        messages.error(request, f"Не удалось начать оплату картой. Счёт "
                                f"{invoice.number} выставлен — его можно "
                                "оплатить по реквизитам.")
        return redirect("invoice_detail", number=invoice.number)
    invoice.payment_ref = payment_id
    invoice.save(update_fields=["payment_ref"])
    return redirect(confirmation)


@login_required
@require_POST
def pay_annual(request):
    """Годовая предоплата базы: собрать годовой счёт и увести в ЮKassa.

    Идемпотентно на уровне `build_annual_invoice` (не плодит второй незакрытый
    годовой счёт). Оплата обрабатывается тем же вебхуком и `mark_paid`, что и
    месячная — `mark_paid` ветвится по `is_annual`.
    """
    organization = _organization(request)
    subscription = getattr(organization, "subscription", None)
    if subscription is None or not services.annual_available(
            organization, subscription.plan):
        messages.info(request, "Для этого тарифа годовая оплата не предлагается.")
        return redirect("cabinet")
    if not payments.is_available():
        messages.info(request, "Оплата картой сейчас недоступна — напишите нам, "
                               "выставим годовой счёт по реквизитам.")
        return redirect("cabinet")
    invoice = services.build_annual_invoice(organization)
    try:
        payment_id, confirmation = payments.create_payment(
            invoice,
            request.build_absolute_uri(f"/app/invoices/{invoice.number}"),
            request.user.email,
        )
    except payments.PaymentError as error:
        _log.error("annual payment for %s failed: %s", organization.id, error)
        messages.error(request, "Не удалось начать оплату картой. Годовой счёт "
                                f"{invoice.number} можно оплатить по реквизитам.")
        return redirect("invoice_detail", number=invoice.number)
    invoice.payment_ref = payment_id
    invoice.save(update_fields=["payment_ref"])
    return redirect(confirmation)


@csrf_exempt
@require_POST
def yookassa_webhook(request):
    """Payment notification.

    Machine-to-machine, so CSRF does not apply — there is no session and no
    browser. The body is NOT trusted: it supplies an id, and the status is read
    back from ЮKassa over an authenticated connection. Anyone can post this
    shape at us; nobody can make ЮKassa agree.

    Always answers 200 once the notification is understood. A provider that gets
    a 500 retries, and retrying a notification we have already acted on is how a
    customer's service gets resumed twice and an invoice marked paid twice.
    """
    try:
        body = json.loads(request.body or b"{}")
        payment_id = str(body.get("object", {}).get("id", ""))
    except (ValueError, AttributeError):
        return HttpResponse("bad body", status=400)
    # Shape-checked BEFORE the outbound call. Every POST here costs one
    # authenticated round trip to ЮKassa, so an unauthenticated endpoint that
    # always makes one is an amplifier: ~8 concurrent requests fill every
    # gunicorn slot and the storefront stops answering, and sustained traffic
    # burns the API quota until real customers cannot pay.
    if not _PAYMENT_ID.fullmatch(payment_id):
        return HttpResponse("not a payment id", status=400)
    if _too_many_webhooks(request):
        return HttpResponse("slow down", status=429)

    try:
        status, amount, number = payments.fetch_status(payment_id)
    except payments.PaymentError as error:
        # 502 rather than 200: we could not establish the truth, so the provider
        # SHOULD retry. This is the one case where a retry is what we want.
        _log.error("could not verify payment %s: %s", payment_id, error)
        return HttpResponse("could not verify", status=502)

    if status != "succeeded":
        return HttpResponse("ignored", status=200)

    invoice = Invoice.objects.filter(number=number).first()
    if invoice is None:
        _log.error("payment %s references unknown invoice %r", payment_id, number)
        return HttpResponse("unknown invoice", status=200)
    if invoice.state == Invoice.PAID and invoice.service_resumed_at is not None:
        return HttpResponse("already paid", status=200)
    # Underpayment must not resume service. Amounts come back as Decimal from
    # both sides, so this is an exact comparison and not a float near-miss.
    if amount < invoice.total:
        _log.error("payment %s underpays %s: %s < %s",
                   payment_id, number, amount, invoice.total)
        return HttpResponse("amount mismatch", status=200)

    # `payment_ref` едет ВНУТРЬ `mark_paid` и пишется тем же коммитом, что и
    # оплата. Раньше он записывался здесь, до вызова, и откат внутри `mark_paid`
    # оставлял счёт с проставленным `payment_ref` в состоянии `draft` — при
    # уникальном поле это ещё и упирало повторную доставку в конфликт.
    try:
        services.mark_paid(invoice, payment_ref=payment_id)
    except services.ServiceNotResumed as error:
        # 502, а не 500 из необработанного исключения: деньги записаны и не
        # откатятся, не доехало только возобновление, и провайдер ДОЛЖЕН
        # повторить — повтор его и дочинит. Та же дверь, что у
        # `payments.PaymentError` выше, и по той же причине.
        _log.error("invoice %s paid but service not resumed: %s", number, error)
        return HttpResponse("paid, service not resumed", status=502)
    _log.info("invoice %s paid via %s", number, payment_id)
    return HttpResponse("ok", status=200)


@login_required
def invoice_print(request, number: str):
    """Печатная форма счёта — the page an accountant prints or saves as PDF.

    HTML with a print stylesheet rather than a generated PDF. WeasyPrint and
    friends need pango/cairo, which do not import on a developer machine at all,
    so the one artefact a customer's accountant looks at would have first run in
    production. A page can be opened by a test with an HTTP GET.
    """
    organization = _organization(request)
    invoice = organization.invoices.filter(number=number).first()
    if invoice is None:
        raise Http404("счёт не найден")
    return render(request, "app/print_invoice.html", {
        "invoice": invoice,
        "organization": organization,
        "seller": settings.SELLER,
        # An акт only exists once the work is paid for; before that this is a
        # счёт and nothing else.
        "act": invoice.state == Invoice.PAID,
    })


def healthz(request) -> HttpResponse:
    """Liveness for the orchestrator. Deliberately does not touch the licensing
    server: this answers "is the web process alive", and folding a dependency
    into it would make an outage there restart a healthy container."""
    return HttpResponse("ok", content_type="text/plain")
