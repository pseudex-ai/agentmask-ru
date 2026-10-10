"""Internal lifecycle evidence, NOT provider verification or a payment API.

Staff attest an existing qualification/acceptance/document; a click is not proof.
This bookkeeping never charges, refunds, cancels, changes licensing or exports.
No customer text/contact is accepted. New external use needs explicit consent
purpose/version and a separate review; these kinds are not export TARGETS.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Min, Sum
from django.utils import timezone
from django.utils.crypto import salted_hmac


STAFF_ATTESTED = "staff_attested"
KINDS = ("qualified_lead", "successful_agent_loop", "renewal_paid",
         "refund_confirmed", "subscription_cancelled")
FINANCIAL = {"renewal_paid", "refund_confirmed"}
EXTERNAL_EXPORT_DEFAULT = False


class _ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("outcome_immutable")

    def delete(self):
        raise ValidationError("outcome_immutable")

    def bulk_create(self, *args, **kwargs):
        raise ValidationError("use_record_outcome")

    def bulk_update(self, *args, **kwargs):
        raise ValidationError("outcome_immutable")


class AcquisitionOutcome(models.Model):
    """Immutable manual evidence. Actor PROTECT preserves the audit identity."""
    organization = models.ForeignKey("accounts.Organization", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32, choices=[(k, k) for k in KINDS])
    event_at = models.DateTimeField(db_index=True)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    source = models.CharField(max_length=24, default=STAFF_ATTESTED, editable=False)
    invoice = models.ForeignKey("billing.Invoice", null=True, blank=True, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="")
    reference_digest = models.CharField(max_length=64, unique=True, editable=False)
    objects = _ImmutableQuerySet.as_manager()

    class Meta:
        app_label = "ops"
        ordering = ("event_at", "pk")
        constraints = [models.UniqueConstraint(fields=("invoice", "kind"),
            condition=models.Q(kind="renewal_paid"), name="acq_renewal_invoice_once")]

    def save(self, *args, _attested_write=False, **kwargs):
        if not self._state.adding or not _attested_write:
            raise ValidationError("use_record_outcome" if self._state.adding else "outcome_immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("outcome_immutable")


def _money(value):
    try:
        amount = Decimal(str(value))
        if (not amount.is_finite() or not 0 < amount <= Decimal("9999999999.99")
                or amount != amount.quantize(Decimal("0.01"))):
            raise ValueError
        return amount
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("positive_finite_cent_amount_required") from None


def _aware(value):
    return isinstance(value, datetime) and timezone.is_aware(value)


@transaction.atomic
def record_outcome(actor, organization, kind, event_at, invoice=None, amount=None, reference=None):
    """Attest evidence; return the existing row for an exact idempotent retry.

    Caller UI MUST enforce real session OTP + CSRF, never set is_verified itself.
    Missing OTP context fails closed. qualified_lead means a concrete suitable
    agent project and agreed next step; successful_agent_loop means accepted
    correct tool action on the customer's scenario (not first_mask/HTTP 200).
    reference: opaque doc:<id> / provider:<id>, never a contact, URL or content.
    Financial kinds require a reference and amount; renewal is staff-classified,
    not inferred from a timer or from every subsequent payment. Cancellation
    corroborates current CANCELLED DB state, but its historical time is attested.
    """
    from accounts.models import Organization
    from billing.models import Invoice, Subscription

    verified = getattr(actor, "is_verified", None)
    if not (getattr(actor, "pk", None) and getattr(actor, "is_active", False)
            and getattr(actor, "is_staff", False) and callable(verified) and verified()):
        raise PermissionDenied("active_staff_otp_required")
    # Re-read permissions: a stale request object must not resurrect revoked staff.
    user = get_user_model().objects.select_for_update().filter(
        pk=actor.pk, is_active=True, is_staff=True).first()
    if user is None:
        raise PermissionDenied("active_staff_otp_required")
    if kind not in KINDS:
        raise ValidationError("unsupported_outcome_kind")
    now = timezone.now()
    if not _aware(event_at) or event_at >= now:
        raise ValidationError("past_aware_event_time_required")
    org = Organization.objects.select_for_update().get(pk=organization.pk)
    if event_at < org.created_at:
        raise ValidationError("event_before_organization")
    if reference is not None and (not isinstance(reference, str) or not re.fullmatch(
            r"(?:doc|provider):[A-Za-z0-9_-]{1,112}", reference)):
        raise ValidationError("opaque_document_reference_required")
    financial = kind in FINANCIAL
    if financial and (invoice is None or reference is None or amount is None):
        raise ValidationError("invoice_amount_reference_required")
    if not financial and (invoice is not None or amount is not None):
        raise ValidationError("nonfinancial_outcome_has_no_money")
    amount = _money(amount) if financial else None
    inv = None
    if financial:
        inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if inv.organization_id != org.pk:
            raise ValidationError("invoice_organization_mismatch")
        if (inv.state != Invoice.PAID or not _aware(inv.paid_at)
                or inv.paid_at > event_at or inv.paid_at >= now):
            raise ValidationError("genuine_paid_invoice_required")
        total = _money(inv.total)
        if amount > total:
            raise ValidationError("amount_exceeds_invoice")
    # Explicit reference identity is GLOBAL, so reuse across org/invoice/kind
    # cannot manufacture a second amount. Only a keyed digest reaches storage.
    # Preserve SECRET_KEY while this ledger is retained; rotation needs an
    # explicit digest/idempotency migration, not a blind key replacement.
    identity = reference or f"event:{org.pk}:{kind}:{event_at.astimezone(dt_timezone.utc).isoformat()}"
    digest = salted_hmac("acquisition-outcome-v1", identity, algorithm="sha256").hexdigest()
    existing = AcquisitionOutcome.objects.filter(reference_digest=digest).first()
    if existing:
        if (existing.organization_id, existing.kind, existing.event_at, existing.invoice_id,
                existing.amount) != (org.pk, kind, event_at, inv.pk if inv else None, amount):
            raise ValidationError("reference_conflict")
        return existing
    if kind == "renewal_paid":
        if amount != total:
            raise ValidationError("renewal_amount_must_equal_invoice")
        # A tied timestamp does not establish ordering. Invalid earlier paid
        # evidence blocks classification rather than guessing the first payment.
        paid = Invoice.objects.filter(organization=org, state=Invoice.PAID)
        if (paid.filter(paid_at__isnull=True).exists() or not paid.filter(
                paid_at__lt=inv.paid_at, total__gt=0).exists()):
            raise ValidationError("renewal_requires_prior_paid_invoice")
        if AcquisitionOutcome.objects.filter(invoice=inv, kind=kind).exists():
            raise ValidationError("renewal_already_attested")
    if kind == "refund_confirmed":
        refunded = AcquisitionOutcome.objects.filter(invoice=inv, kind=kind).aggregate(
            total=Sum("amount"))["total"] or Decimal("0")
        if refunded + amount > total:
            raise ValidationError("cumulative_refund_exceeds_invoice")
    if kind == "subscription_cancelled" and not Subscription.objects.select_for_update().filter(
            organization=org, state=Subscription.CANCELLED).exists():
        raise ValidationError("cancelled_subscription_required")
    row = AcquisitionOutcome(organization=org, actor=user, kind=kind, event_at=event_at,
        invoice=inv, amount=amount, currency="RUB" if financial else "", reference_digest=digest)
    try:
        with transaction.atomic():
            row.save(force_insert=True, _attested_write=True)
    except IntegrityError:
        # Different organizations may race over a globally reused reference.
        # Same-org exact retries are serialized by the organization lock above.
        if AcquisitionOutcome.objects.filter(reference_digest=digest).exists():
            raise ValidationError("reference_conflict") from None
        raise
    return row


def cohort_retention(since, now=None, windows=(7, 14, 30)):
    """Read-only first-signup cohort; UTC completed daily cumulative observations.

    Eligibility is first actual signup in [since, now), NOT a later duplicate.
    Active needs >=2 readings within [age-7, age] and a positive monotone delta.
    Inactive requires full daily coverage of that interval; sparse flat readings
    remain unknown. Any negative/reset in-window is unknown, even with a later
    increase. Today's mutable reading is excluded (no historical as-of illusion).
    Rates use evaluable only; coverage=evaluable/mature, never hide unknowns.
    No customer/contact/source strings or per-org contents leave this function.
    """
    from accounts.models import Organization
    from ops.analytics_models import Funnel, UsageDay

    now = now or timezone.now()
    if not _aware(since) or not _aware(now) or since >= now:
        raise ValidationError("valid_aware_cohort_bounds_required")
    windows = tuple(windows)
    if not windows or any(type(w) is not int or not 1 <= w <= 365 for w in windows):
        raise ValidationError("retention_windows_must_be_days_1_to_365")
    now = now.astimezone(dt_timezone.utc)
    first = Funnel.objects.filter(step=Funnel.SIGNUP_SUBMITTED, at__lt=now).exclude(
        organization_id="").values("organization_id").annotate(signup_at=Min("at"))
    first = {r["organization_id"]: r["signup_at"].astimezone(dt_timezone.utc)
             for r in first if since <= r["signup_at"] < now}
    ids = set(Organization.objects.filter(pk__in=first).exclude(
        source_utm_source="qa_r01").values_list("pk", flat=True))
    cohorts = {key: first[key] for key in ids}
    observations = defaultdict(list)
    for org_id, day, requests in UsageDay.objects.filter(organization_id__in=ids,
            day__gte=since.astimezone(dt_timezone.utc).date(), day__lt=now.date()).order_by(
                "day").values_list("organization_id", "day", "requests"):
        observations[org_id].append((day, requests))
    rows = []
    for age in windows:
        row = dict(age_days=age, eligible=len(cohorts), mature=0, immature=0,
                   evaluable=0, active=0, inactive=0, unknown=0)
        for org_id, signup in cohorts.items():
            if signup + timedelta(days=age) > now:
                row["immature"] += 1
                continue
            row["mature"] += 1
            start = signup.date() + timedelta(days=max(0, age - 7))
            end = signup.date() + timedelta(days=age)
            readings = [(d, n) for d, n in observations[org_id] if start <= d <= end]
            values = [n for _, n in readings]
            invalid = (len(values) < 2 or any(n < 0 for n in values)
                       or any(b < a for a, b in zip(values, values[1:])))
            if invalid or end >= now.date():
                row["unknown"] += 1
            elif values[-1] > values[0]:
                row["active"] += 1
            elif len(readings) == (end - start).days + 1:
                row["inactive"] += 1
            else:
                row["unknown"] += 1
        row["evaluable"] = row["active"] + row["inactive"]
        row["rate"] = row["active"] / row["evaluable"] if row["evaluable"] else None
        row["coverage"] = row["evaluable"] / row["mature"] if row["mature"] else None
        rows.append(row)
    return {"cohort": "first_signup_submitted", "since": since, "now": now,
            "eligible": len(cohorts), "windows": rows}
