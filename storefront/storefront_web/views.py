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
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Membership, Organization
from billing import onboarding, licensing, payments, services
from accounts.models import User
from billing.models import Invoice, LicenseKey, Plan
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
        # Группы конфигуратора — из того же реестра, что и страница /detection.
        "groups": detection_types.groups_for_page(),
        # ЧИСЛО ТИПОВ СЧИТАЕТСЯ, А НЕ ПИШЕТСЯ. «18» стояло литералом в трёх
        # местах, пока список был разметкой; теперь список — данные, и
        # следующий добавленный тип сделал бы страницу противоречащей
        # собственной таблице.
        "found_count": len(detection_types.FOUND),
        "trial_days": services.TRIAL_DAYS,
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
        "trial_days": services.TRIAL_DAYS,
        "due_days": services.INVOICE_DUE_DAYS,
        "grace_days": services.GRACE_DAYS,
        "updated": datetime.date.fromtimestamp(max(stamps)).strftime("%d.%m.%Y"),
    }


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
    })


def requisites(request):
    """Сведения о владельце сайта — ст. 10 ч. 2 ФЗ «Об информации».

    Владелец сайта обязан разместить наименование, место нахождения и адрес
    электронной почты. Для дистанционной продажи то же требует ст. 26.1 ЗоЗПП:
    покупатель должен видеть, КОМУ он платит, до того как заплатит.
    """
    return render(request, "legal/requisites.html", {"seller": settings.SELLER})


def offer(request):
    return render(request, "legal/offer.html", _legal_context())


def policy(request):
    return render(request, "legal/policy.html", _legal_context())


def architecture(request):
    return render(request, "legal/architecture.html", _legal_context())


def detection(request):
    """What the engine finds, and what it does not.

    Split out of the landing because three of five persona-clients independently
    asked for the list behind the number, and because the architecture page
    promised published defects with nothing to click. A count with no list reads
    as a marketing counter; a promise of transparency with no page is worse than
    saying nothing."""
    # СПИСКИ ПРИЕЗЖАЮТ ИЗ РЕЕСТРА, а не лежат разметкой: те же факты нужны
    # конфигуратору на лендинге, и два экземпляра одного утверждения расходятся.
    return render(request, "legal/detection.html", _legal_context() | {
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
    organization = services.create_account(email, name, plan_code)
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
    return render(request, "check_email.html", {"email": email})


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
        "trial_days": services.TRIAL_DAYS,
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
    included = subscription.plan.included_requests if subscription else 0
    # ЁМКОСТЬ: НА ЧЁМ СТРОИТСЯ СЧЁТ И ЧЕМ ОНО ЗАЖАТО. Клиент должен видеть обе
    # границы, потому что расстояние между ними — это ровно та скидка, которую
    # он получает за подтверждённые отчёты. Без этого фраза «отчёт — ваша
    # защита» остаётся обещанием.
    billable = int(reported.get("capacity_billable", 0) or 0)
    ceiling = int(reported.get("capacity_granted", 0) or 0)
    acknowledged = int(reported.get("capacity_acked", 0) or 0)
    unacked = int(reported.get("capacity_unacked_quanta", 0) or 0)
    return render(request, "app/cabinet.html", {
        "instances": slots,
        "organization": organization,
        "subscription": subscription,
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
    messages.success(request, f"Ключ {key.prefix}… отозван и больше не продлит аренду.")
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
