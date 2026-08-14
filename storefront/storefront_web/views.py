"""The pages.

The site is three things and nothing else: a landing, a way to sign up, and a
cabinet with keys, usage and invoices. There is deliberately no screen here that
shows a dialogue, a token or a value — see `veilgate/localui/` for those. That
absence is the product's legal position, not a missing feature, so a view added
later must be checked against it rather than against convenience.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Membership, Organization
from billing import licensing, services
from billing.models import Invoice, LicenseKey, Plan


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

    try:
        organization, key = services.register(email, name, plan_code)
    except Plan.DoesNotExist:
        messages.error(request, "Такого тарифа нет.")
        return redirect("landing")
    except licensing.LicensingError as error:
        # Deliberately not a generic apology: the customer's next action depends
        # on whether this is ours to fix, and it always is.
        messages.error(request, "Не удалось выпустить ключ — это на нашей стороне. "
                                "Напишите нам, и мы выпустим его вручную.")
        raise
    return _handoff(redirect("welcome"), key, organization.id)


# Why a signed COOKIE and not the session. Django's default session backend
# writes session data to OUR database, so `session["fresh_key"] = key` would
# persist the full key in a table we control — defeating the entire point of
# storing only a prefix and a hash, and putting a customer's bearer credential
# somewhere a backup and a support query can reach.
#
# A signed cookie never touches our storage. It is short-lived, HttpOnly, and
# deleted the moment the page that shows it renders.
_HANDOFF_COOKIE = "vg_handoff"
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
    # Read once. A refresh must not re-render a bearer credential: the page
    # would otherwise sit in the browser's back-forward cache holding a key
    # that opens the customer's whole gateway.
    response.delete_cookie(_HANDOFF_COOKIE)
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
    # There is no per-key revoke on the licensing server yet: statuses are
    # per-organisation. Revoking the last key would therefore stop the whole
    # organisation, which is not what this button says it does.
    if organization.keys.filter(revoked_at__isnull=True).count() <= 1:
        messages.error(request, "Это последний действующий ключ. Выпустите новый, "
                                "прежде чем отзывать этот — иначе сервис остановится.")
        return redirect("cabinet")
    with transaction.atomic():
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
    messages.success(request, f"Ключ {key.prefix}… отозван.")
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
    })


def healthz(request) -> HttpResponse:
    """Liveness for the orchestrator. Deliberately does not touch the licensing
    server: this answers "is the web process alive", and folding a dependency
    into it would make an outage there restart a healthy container."""
    return HttpResponse("ok", content_type="text/plain")
