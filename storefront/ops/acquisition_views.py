"""First-party permission endpoints. No provider SDK and no contact payloads."""
import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods

from ops import acquisition_consent as consent


def _payload(request):
    if request.content_type == "application/json":
        if len(request.body) > 1024:
            return {}
        try:
            value = json.loads(request.body)
            return value if isinstance(value, dict) else {}
        except (ValueError, UnicodeError):
            return {}
    return request.POST


def _live_unbound(row, now):
    # Blank ClientID is a prepared MANAGEMENT capability, never export consent.
    return bool(row and not row.user_id and not row.organization_id
                and row.verified_at is None and row.revoked_at is None
                and row.purpose_revision == consent.PURPOSE_REVISION
                and row.granted_at <= now < min(row.expires_at, row.granted_at + consent.RAW_TTL))


@never_cache
@csrf_protect
@require_POST
def prepare(request):
    if not consent.enabled():
        return JsonResponse({"status": "disabled"}, status=403)
    data = _payload(request)
    if (data.get("purpose_revision") != consent.PURPOSE_REVISION
            or data.get("affirmative") != "1" or data.get("browser_consent") != "yes"):
        return JsonResponse({"status": "consent_required"}, status=400)
    if getattr(request.user, "is_authenticated", False):
        return JsonResponse({"status": "new_signup_only"}, status=409)
    from storefront_web.views import _too_many
    if _too_many(request, "analytics_prepare", 20, 600):
        return JsonResponse({"status": "retry_later"}, status=429)
    with transaction.atomic():
        row = consent.AnalyticsGrant.objects.select_for_update().filter(pk=consent.receipt_id(request)).first()
        now = timezone.now()
        # Only this explicit-purpose endpoint may mint a new capability. Reusing
        # a live unbound one does not extend either its prepared or granted life.
        if not _live_unbound(row, now):
            row = consent.AnalyticsGrant.objects.create(client_id="", granted_at=now,
                reference_at=now, expires_at=now + consent.RAW_TTL)
    response = JsonResponse({"status": "prepared", "purpose_revision": consent.PURPOSE_REVISION})
    consent.set_receipt(response, row)
    return response


@never_cache
@csrf_protect
@require_POST
def grant(request):
    if not consent.enabled():
        return JsonResponse({"status": "disabled"}, status=403)
    data = _payload(request)
    if (data.get("purpose_revision") != consent.PURPOSE_REVISION
            or data.get("affirmative") != "1" or data.get("browser_consent") != "yes"):
        return JsonResponse({"status": "consent_required"}, status=400)
    client_id = data.get("client_id", "")
    cookie_id = request.COOKIES.get("_ym_uid", "")
    # A callback is not a cryptographic attestation. Cross-check the same-browser
    # cookie and fail closed without affecting signup when blockers remove it.
    if not consent.valid_client_id(client_id) or client_id != cookie_id:
        return JsonResponse({"status": "identifier_unavailable"}, status=400)
    if getattr(request.user, "is_authenticated", False):
        return JsonResponse({"status": "new_signup_only"}, status=409)
    from storefront_web.views import _too_many
    if _too_many(request, "analytics_grant", 20, 600):
        return JsonResponse({"status": "retry_later"}, status=429)
    with transaction.atomic():
        row = consent.AnalyticsGrant.objects.select_for_update().filter(pk=consent.receipt_id(request)).first()
        now = timezone.now()
        # The browser acknowledged this cookie BEFORE starting grant. Revoke
        # locks the same row, so either ordering ends revoked; never resurrect or
        # mint a replacement when a delayed POST carries no/old capability.
        if not _live_unbound(row, now):
            return JsonResponse({"status": "prepare_required"}, status=409)
        if row.client_id:
            if row.client_id != client_id:
                return JsonResponse({"status": "identifier_conflict"}, status=409)
            return JsonResponse({"status": "granted", "purpose_revision": consent.PURPOSE_REVISION})
        row.client_id = client_id
        row.granted_at = row.reference_at = now
        row.expires_at = now + consent.RAW_TTL
        row.save(update_fields=["client_id", "granted_at", "reference_at", "expires_at"])
    response = JsonResponse({"status": "granted", "purpose_revision": consent.PURPOSE_REVISION})
    consent.set_receipt(response, row)
    return response


def _revoke(request):
    # Authenticated preferences revoke this PERSON across devices, not their org.
    if request.user.is_authenticated:
        from django.db.models import Q
        rows = consent.AnalyticsGrant.objects.filter(
            Q(user=request.user) | Q(pk=consent.receipt_id(request), user__isnull=True))
    else:
        receipt = consent.receipt_id(request)
        if request.COOKIES.get(consent.MANAGEMENT_COOKIE) and receipt is None:
            return False
        rows = consent.AnalyticsGrant.objects.filter(pk=receipt)
    consent.revoke_grants(rows)
    return True


@never_cache
@csrf_protect
@require_POST
def revoke(request):
    if not _revoke(request):
        return JsonResponse({"status": "receipt_invalid"}, status=400)
    response = JsonResponse({"status": "revoked"})
    response.delete_cookie(consent.MANAGEMENT_COOKIE, path="/", samesite="Lax")
    return response


@never_cache
@ensure_csrf_cookie
@csrf_protect
@require_http_methods(["GET", "POST"])
def preferences(request):
    done = False
    if request.method == "POST":
        done = _revoke(request)
    response = render(request, "analytics_preferences.html", {
        "revoked": done, "failed": request.method == "POST" and not done,
        "analytics_here": False, "metrika_id": "", "indexable": False,
    })
    if done:
        response.delete_cookie(consent.MANAGEMENT_COOKIE, path="/", samesite="Lax")
    return response
