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


def create_account(email: str, display_name: str, plan_code: str) -> Organization:
    """Create the account and hand back a WORKING key, before any payment.

    This is the whole product promise on the storefront side: the single metric
    is time from first visit to first masked request, and every step between
    those two points is a place to lose someone. Asking for a card, or for ИНН,
    or for a confirmation click before the key exists, each add minutes to that
    number and buy nothing — the key is worthless without our licensing server,
    which we can switch off at any time.
    """
    plan = Plan.objects.get(code=plan_code)

    # The account commits FIRST, on its own. The licensing call that follows is
    # a 15 s network round trip, and it used to run inside this transaction —
    # holding a write transaction open across the network, and worse: if the
    # call succeeded and the commit then failed, the key stayed ACTIVE on the
    # licensing server bound to an org that no longer existed. It would lease
    # forever, appear in no cabinet, no invoice and no reconciliation.
    #
    # Splitting them leaves only the harmless failure direction: an org with no
    # key yet, visible in the cabinet, fixed by one button.
    with transaction.atomic():
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

    return organization


def issue_first_key(organization: Organization) -> str:
    """The key, issued once the mailbox is proven. Separate from account
    creation so that no credential exists until someone has demonstrated they
    can read the address it was requested for."""
    key = licensing.issue_key(organization.id, organization.subscription.plan.code)
    LicenseKey.record(organization, key, label="первый ключ", environment="live")
    return key


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

    IDEMPOTENT UNDER CONCURRENT DELIVERY. ЮKassa redelivers notifications, and
    two arriving at once both passed the caller's "already paid?" check before
    either wrote — then both ran this, and the unconditional
    `current_period_end = now + 30 days` granted two free months. The row is
    locked and re-read here, so the second delivery finds it already PAID and
    returns without touching the period.
    """
    with transaction.atomic():
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if locked.state == Invoice.PAID:
            return
        licensing.set_status(locked.organization_id, "active")
        invoice = locked
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
    if not isinstance(reported, dict):
        reported = {}
    # The billed quantity comes from the licensing server's MONOTONIC
    # accumulator, not from the raw report and not from the entity counters.
    # Entities move with the mask cache; the raw report drops to zero when a
    # customer deletes their vault. `values` never decreases — see
    # docs/billing-integrity.md.
    values = int(reported.get("values", 0))
    requests = int(reported.get("requests", 0))

    # The counter is CUMULATIVE since the installation's first report. What this
    # period used is the difference from the previous invoice's watermark.
    previous = (Invoice.objects
                .filter(organization=organization)
                .exclude(state=Invoice.VOID)
                .order_by("-period_end", "-id")
                .first())
    watermark = previous.values_at_period_end if previous else 0
    # A counter that went BACKWARDS means the customer started from an empty
    # data directory — a new volume, a restore, a fresh deployment. Billing the
    # negative as zero and re-basing is the only reading that cannot overcharge.
    used_this_period = max(0, values - watermark)

    # THE INVOICE IS THE SUBSCRIPTION. Nothing is charged per value: the value
    # count is produced inside the customer's container and cannot be verified
    # by us, while the subscription period is counted on our side and cannot be
    # forged by them. Billing on the number we do not control would mean
    # policing a counter instead of running a business.
    #
    # The period's values are still recorded on the invoice, as INFORMATION —
    # the customer sees what they got for the money, and a figure far above the
    # plan's guide is what prompts an upgrade.
    subscription_amount = plan.monthly_price

    return Invoice.objects.create(
        organization=organization,
        number=Invoice.next_number(),
        state=Invoice.DRAFT,
        period_start=period_start,
        period_end=period_end,
        plan_amount=_round(subscription_amount),
        overage_values=used_this_period,
        overage_amount=Decimal("0"),
        total=_round(subscription_amount),
        due_at=(timezone.now() + timedelta(days=7)).date(),
        values_at_period_end=values,
        requests_at_period_end=requests,
    )
