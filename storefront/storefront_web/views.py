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
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Membership, Organization
from billing import licensing, payments, services
from billing.models import Invoice, LicenseKey, Plan

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
        raise Http404("у пользователя нет организации")
    return membership.organization


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


def _too_many_signups(request) -> bool:
    bucket = f"signup:{_client_ip(request)}"
    seen = cache.get(bucket, 0)
    if seen >= _SIGNUP_LIMIT:
        return True
    # `add` then `incr` so the window starts at the first attempt and is not
    # extended by later ones — otherwise a steady trickle keeps the key alive
    # forever and the caller is locked out permanently.
    cache.add(bucket, 0, _SIGNUP_WINDOW_SECONDS)
    try:
        cache.incr(bucket)
    except ValueError:
        cache.set(bucket, 1, _SIGNUP_WINDOW_SECONDS)
    return False


# ЮKassa payment ids are UUIDs. Anything else cannot be one of ours, so it is
# refused before it can cost us a network call.
_PAYMENT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_WEBHOOK_LIMIT = 60
_WEBHOOK_WINDOW_SECONDS = 60


def _too_many_webhooks(request) -> bool:
    bucket = f"webhook:{_client_ip(request)}"
    if cache.get(bucket, 0) >= _WEBHOOK_LIMIT:
        return True
    cache.add(bucket, 0, _WEBHOOK_WINDOW_SECONDS)
    try:
        cache.incr(bucket)
    except ValueError:
        cache.set(bucket, 1, _WEBHOOK_WINDOW_SECONDS)
    return False


def landing(request):
    """The public page. The demo on it runs on PREPARED examples and has no
    free-text input: an input field here would mean accepting other people's
    personal data onto our servers, which is precisely what we sell not doing."""
    return render(request, "landing.html", {
        "plans": Plan.objects.filter(is_public=True),
        "trial_days": services.TRIAL_DAYS,
        "image": settings.DOCKER_IMAGE,
    })


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

    # Sign-up is the only unauthenticated write on the site, and every call
    # MINTS A KEY on the licensing server. Unthrottled, a loop would fill that
    # database — the one whose loss stops every customer in the field — with
    # junk, for free, from anywhere.
    if _too_many_signups(request):
        messages.error(request, "Слишком много попыток. Подождите минуту.")
        return redirect("landing")

    # An email that already has an organisation goes to sign-in instead of
    # getting a second one. Two reasons, and the second is what matters: a
    # person who signs up twice would end up with two orgs and see only one of
    # them, and anyone could otherwise attach organisations to a stranger's
    # address by typing it into this form.
    if Membership.objects.filter(user__email=email).exists():
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
        payload = signing.loads(request.GET.get("t", ""),
                                max_age=_ACTIVATION_HOURS * 3600)
    except (signing.BadSignature, signing.SignatureExpired):
        messages.error(request, "Ссылка недействительна или устарела. "
                                "Зарегистрируйтесь заново — это займёт минуту.")
        return redirect("landing")

    organization = Organization.objects.filter(id=payload["org"]).first()
    if organization is None:
        return redirect("landing")
    # Following the link twice must not mint a second key: the first one was
    # shown once and the customer may already be running it.
    if organization.keys.filter(revoked_at__isnull=True).exists():
        messages.info(request, "Ключ уже выпущен. Войдите по ссылке на почту — "
                               "в кабинете видно его префикс и расход.")
        return redirect("account_login")
    try:
        key = services.issue_first_key(organization)
    except licensing.LicensingError as error:
        _log.error("issuing a key for %s failed: %s", organization.id, error)
        messages.error(request, "Не удалось выпустить ключ — это на нашей стороне. "
                                "Напишите нам, и мы выпустим его вручную.")
        return redirect("landing")
    return _handoff(redirect("welcome"), key, organization.id)


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
        "trial_days": services.TRIAL_DAYS,
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
    organization = _organization(request)
    subscription = getattr(organization, "subscription", None)
    try:
        reported = licensing.usage(organization.id).get("usage", {})
        unreachable = False
    except licensing.LicensingError:
        # The cabinet still renders. Counters are the one thing here that comes
        # from another service, and a page that 500s because a sidebar number is
        # unavailable is worse than a page that says the number is unavailable.
        reported, unreachable = {}, True
    used = int(reported.get("requests", 0)) if isinstance(reported, dict) else 0
    included = subscription.plan.included_requests if subscription else 0
    return render(request, "app/cabinet.html", {
        "organization": organization,
        "subscription": subscription,
        "keys": organization.keys.filter(revoked_at__isnull=True),
        "invoices": organization.invoices.all()[:12],
        "used": used,
        "included": included,
        "percent": min(100, round(used / included * 100)) if included else 0,
        "unreachable": unreachable,
        "image": settings.DOCKER_IMAGE,
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
    if invoice.state == Invoice.PAID:
        return HttpResponse("already paid", status=200)
    # Underpayment must not resume service. Amounts come back as Decimal from
    # both sides, so this is an exact comparison and not a float near-miss.
    if amount < invoice.total:
        _log.error("payment %s underpays %s: %s < %s",
                   payment_id, number, amount, invoice.total)
        return HttpResponse("amount mismatch", status=200)

    invoice.payment_ref = payment_id
    invoice.save(update_fields=["payment_ref"])
    services.mark_paid(invoice)
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
