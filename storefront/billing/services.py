"""The state changes, in one place.

Everything that alters what a customer may do goes through here, because each of
these has to happen on BOTH sides — the shop's record and the licensing server's
kill switch — and the two disagreeing is the failure mode with real consequences:
a paying customer stopped on a Friday, or a departed one still being served.

ORDER MATTERS AND IS DELIBERATE. The licensing server is called FIRST and the
local record is written only if it succeeded. The reverse order produces a shop
that believes it resumed a customer who is still blocked, and the customer is
looking at a screen that says "оплачено" while their agents return 503. If the
call fails, the exception propagates and the customer sees an honest error.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership, Organization, User
from billing import licensing
from billing.models import Invoice, LicenseKey, Plan, Subscription

TRIAL_DAYS = 14


@transaction.atomic
def register(email: str, display_name: str, plan_code: str) -> tuple[Organization, str]:
    """Create the account and hand back a WORKING key, before any payment.

    This is the whole product promise on the storefront side: the single metric
    is time from first visit to first masked request, and every step between
    those two points is a place to lose someone. Asking for a card, or for ИНН,
    or for a confirmation click before the key exists, each add minutes to that
    number and buy nothing — the key is worthless without our licensing server,
    which we can switch off at any time.
    """
    plan = Plan.objects.get(code=plan_code)
    user, _ = User.objects.get_or_create(email=email)
    organization = Organization.objects.create(display_name=display_name or email)
    Membership.objects.create(user=user, organization=organization,
                              role=Membership.ROLE_OWNER)

    now = timezone.now()
    trial_ends = now + timedelta(days=TRIAL_DAYS)
    Subscription.objects.create(
        organization=organization,
        plan=plan,
        state=Subscription.TRIAL,
        trial_ends_at=trial_ends,
        current_period_start=now,
        current_period_end=trial_ends,
    )
    # Outside the shop's own tables and therefore the step that can fail on its
    # own. It is last, so a failure leaves no half-account behind — the atomic
    # block rolls the rest back with it.
    key = licensing.issue_key(organization.id, plan.code)
    LicenseKey.record(organization, key, label="первый ключ", environment="live")
    return organization, key


@transaction.atomic
def issue_additional_key(organization: Organization, label: str,
                         environment: str) -> str:
    live = organization.keys.filter(revoked_at__isnull=True).count()
    allowed = organization.subscription.plan.max_keys
    if live >= allowed:
        raise ValueError(
            f"на тарифе {organization.subscription.plan.title} доступно "
            f"{allowed} ключ(а/ей); отзовите ненужный или смените тариф"
        )
    key = licensing.issue_key(organization.id, organization.subscription.plan.code)
    LicenseKey.record(organization, key, label=label, environment=environment)
    return key


def mark_paid(invoice: Invoice) -> None:
    """Money arrived. Restore service first, record it second.

    A customer whose agents are stopped is waiting on exactly one thing, and it
    is not our database row.
    """
    licensing.set_status(invoice.organization_id, "active")
    with transaction.atomic():
        invoice.state = Invoice.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["state", "paid_at"])
        subscription = invoice.organization.subscription
        subscription.state = Subscription.ACTIVE
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = timezone.now() + timedelta(days=30)
        subscription.save(update_fields=["state", "current_period_start",
                                         "current_period_end"])


def mark_unpaid(organization: Organization) -> None:
    """The invoice went past due.

    `unpaid`, not `revoked`. Both stop the customer within a minute, but only
    one of them is undone by paying — and a customer who pays a late invoice must
    come back without us touching anything.
    """
    licensing.set_status(organization.id, "unpaid")
    subscription = organization.subscription
    subscription.state = Subscription.PAST_DUE
    subscription.save(update_fields=["state"])


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_invoice(organization: Organization, period_start, period_end) -> Invoice:
    """Draft the счёт for a period from the counters the customer's own
    containers reported.

    The overage is computed from the licensing server's numbers and from
    nothing else. The storefront has no way to observe traffic and must not
    acquire one: an independent estimate would be a number the customer cannot
    check against their own gateway's log.
    """
    subscription = organization.subscription
    plan = subscription.plan
    reported = licensing.usage(organization.id).get("usage", {})
    requests = int(reported.get("requests", 0)) if isinstance(reported, dict) else 0

    over = max(0, requests - plan.included_requests)
    # Charged per started thousand: billing a fraction of a thousand requests
    # produces kopeck-level lines nobody can reconcile.
    thousands = (over + 999) // 1000
    overage_amount = _round(Decimal(thousands) * plan.overage_per_1k)

    return Invoice.objects.create(
        organization=organization,
        number=Invoice.next_number(),
        state=Invoice.DRAFT,
        period_start=period_start,
        period_end=period_end,
        plan_amount=plan.monthly_price,
        overage_requests=over,
        overage_amount=overage_amount,
        total=_round(plan.monthly_price + overage_amount),
        due_at=(timezone.now() + timedelta(days=7)).date(),
    )
