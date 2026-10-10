"""Per-person acquisition permission, separate from legal and browser consent.

Exporters must lock the selected row with select_for_update(), then call
 grant_eligible immediately before dispatch, inside that same transaction.
No legacy source_yclid/first_touch value is authority or an identity here.
"""
from datetime import timedelta
import re
import uuid

from django.conf import settings
from django.core import signing
from django.db import models, transaction
from django.utils import timezone

PURPOSE_REVISION = "acquisition-v1"
MANAGEMENT_COOKIE = "ps_analytics_grant"
COOKIE_SALT = "acquisition.management.v1"
RAW_TTL = timedelta(days=21)
EXPORT_WINDOW = timedelta(days=20)


def default_expiry():
    return timezone.now() + RAW_TTL


class AnalyticsGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE, related_name="analytics_grants")
    organization = models.ForeignKey("accounts.Organization", null=True, blank=True,
                                     on_delete=models.CASCADE, related_name="analytics_grants")
    purpose_revision = models.CharField(max_length=32, default=PURPOSE_REVISION)
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_expiry, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    client_id = models.CharField(max_length=32, blank=True, default="")
    yclid = models.CharField(max_length=64, blank=True, default="")
    reference_at = models.DateTimeField(default=timezone.now)


def enabled():
    return bool(getattr(settings, "ACQUISITION_LINK_ENABLED", False))


def valid_client_id(value):
    # Do not coerce numeric JSON: precision may already have been lost upstream.
    return isinstance(value, str) and re.fullmatch(r"[0-9]{1,32}", value) is not None


def receipt_id(request):
    value = request.COOKIES.get(MANAGEMENT_COOKIE, "")
    if not value or len(value) > 256:
        return None
    try:
        return uuid.UUID(signing.loads(value, salt=COOKIE_SALT,
                                       max_age=int(RAW_TTL.total_seconds())))
    except (signing.BadSignature, ValueError, TypeError):
        return None


def set_receipt(response, grant):
    response.set_cookie(MANAGEMENT_COOKIE,
                        signing.dumps(str(grant.pk), salt=COOKIE_SALT),
                        max_age=max(0, int((grant.expires_at - timezone.now()).total_seconds())),
                        secure=True, httponly=True, samesite="Lax", path="/")


def active(grant, now):
    return (grant.purpose_revision == PURPOSE_REVISION and grant.revoked_at is None
            and grant.granted_at <= now < min(grant.expires_at, grant.granted_at + RAW_TTL)
            and valid_client_id(grant.client_id))


def bind_signup(request, organization, user=None):
    """Only call for a newly-created signup, never an existing-email branch.

    Server object arguments, not posted IDs. Creation timestamps additionally
    refuse attaching an older account to an anonymous permission.
    """
    if not enabled():
        return None
    from accounts.models import Membership
    if user is None:
        membership = Membership.objects.filter(organization=organization,
                                                role=Membership.ROLE_OWNER).first()
        user = membership.user if membership else None
    if user is None:
        return None
    with transaction.atomic():
        grant = AnalyticsGrant.objects.select_for_update().filter(pk=receipt_id(request)).first()
        now = timezone.now()
        if (not grant or not active(grant, now) or grant.user_id or grant.organization_id
                or user.date_joined < grant.granted_at
                or organization.created_at < grant.granted_at
                or not Membership.objects.filter(user=user, organization=organization,
                                                  role=Membership.ROLE_OWNER).exists()):
            return None
        grant.user, grant.organization = user, organization
        grant.save(update_fields=["user", "organization"])
        return grant


def confirmation_available(request, organization, user):
    """Mailbox ownership alone cannot endorse another browser's anonymous grant."""
    if not enabled() or user is None:
        return False
    grant = AnalyticsGrant.objects.filter(pk=receipt_id(request),
                                          organization=organization, user=user).first()
    return bool(grant and active(grant, timezone.now()) and grant.verified_at is None)


def confirm_grant(organization, user=None, *, request=None):
    """Require mailbox proof AND a separate affirmative purpose in its browser.

    Someone else can preregister a fresh email using THEIR browser receipt.
    A routine mailbox confirmation must not endorse that person's ClientID.
    Cross-device activation stays unattributed instead of guessing identity;
    signup, key issuance and payment remain available without this permission.
    """
    if (not enabled() or user is None or request is None or request.method != "POST"
            or request.POST.get("acquisition_confirmation") != PURPOSE_REVISION):
        return 0
    from accounts.models import Membership
    if not Membership.objects.filter(user=user, organization=organization).exists():
        return 0
    with transaction.atomic():
        grant = AnalyticsGrant.objects.select_for_update().filter(
            pk=receipt_id(request), organization=organization, user=user).first()
        now = timezone.now()
        if not grant or not active(grant, now) or grant.verified_at is not None:
            return 0
        grant.verified_at = now
        grant.save(update_fields=["verified_at"])
        return 1


def grant_eligible(grant, event_at, now=None):
    now = now or timezone.now()
    return bool(enabled() and grant and event_at and active(grant, now)
                and grant.user_id and grant.organization_id
                and grant.verified_at is not None and grant.verified_at <= now
                and grant.granted_at <= event_at <= now
                and grant.granted_at <= grant.reference_at <= event_at
                and now - grant.reference_at <= EXPORT_WINDOW
                and now - event_at <= EXPORT_WINDOW
                and event_at < grant.expires_at)


def eligible_grant(org, event_at, now=None):
    now = now or timezone.now()
    if not enabled():
        return None
    for grant in AnalyticsGrant.objects.filter(organization=org, revoked_at__isnull=True,
                                               expires_at__gt=now).order_by("granted_at", "pk"):
        if grant_eligible(grant, event_at, now):
            return grant
    return None


def revoke_grants(queryset, now=None):
    # UPDATE takes row locks too: serialize against the exporter's dispatch lock.
    # Clear identifiers even if an earlier revocation already marked the row.
    now = now or timezone.now()
    with transaction.atomic():
        ids = list(queryset.select_for_update().values_list("pk", flat=True))
        rows = AnalyticsGrant.objects.filter(pk__in=ids)
        rows.filter(revoked_at__isnull=True).update(revoked_at=now)
        return rows.update(client_id="", yclid="")


def purge_expired(now=None):
    """Run from the scheduled export/retention command, including disabled mode."""
    return revoke_grants(AnalyticsGrant.objects.filter(expires_at__lte=now or timezone.now()), now)
