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

import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership, Organization, User
from billing import licensing
from billing.models import Invoice, LicenseKey, Plan, Subscription

_log = logging.getLogger("billing.services")

TRIAL_DAYS = 14


def pending_organization(email: str):
    """The organisation of an account whose activation link has not been used.

    Returns None for an unknown address AND for one that is already activated,
    so the resend view can answer identically in both cases — a view that
    answered honestly would tell an attacker which addresses are customers.
    """
    membership = (Membership.objects
                  .filter(user__email=email, role=Membership.ROLE_OWNER)
                  .select_related("organization")
                  .order_by("-id")
                  .first())
    if membership is None:
        return None
    organization = membership.organization
    if organization.keys.filter(revoked_at__isnull=True).exists():
        return None
    return organization


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


class ServiceNotResumed(RuntimeError):
    """Деньги записаны, обслуживание восстановить не удалось.

    Отдельный тип, потому что вызывающему нужны РАЗНЫЕ действия: платёж
    трогать нельзя (он уже наш факт), а возобновление надо повторить. Вебхук
    отвечает на него 502 — «мы не смогли, ретрайте», — ровно как уже отвечает
    на `payments.PaymentError`.
    """


def mark_paid(invoice: Invoice, payment_ref: str = "") -> None:
    """Money arrived. RECORD IT FIRST, restore service second.

    ПОРЯДОК ПЕРЕВЁРНУТ, И ЭТО НЕ ВКУСОВЩИНА. Раньше здесь стояло «сначала
    восстановить, потом записать», и сетевой вызов жил ВНУТРИ
    `transaction.atomic()`. Его отказ откатывал `state=PAID`, `paid_at` и
    продление периода целиком:

        POST /admin/resume "HTTP/1.1 403 Forbidden"
        состояние счёта ПОСЛЕ оплаты: draft   paid_at= None

    Ломаются оба порядка, но по-разному, и невосстановимо только одно.
    «Лицензии первыми» теряет САМ ФАКТ ПЛАТЕЖА: у ЮKassa конечное окно
    ретраев, а у банковского перевода их нет вовсе, и восстановить событие
    неоткуда. «Деньги первыми» оставляет шлюз клиента стоять несколько минут —
    плохо, но это видно в `service_resumed_at`, алармится сторожем и чинится
    нами сколько угодно раз.

    Три шага, и сеть не держит ни одной транзакции:

      1. короткая транзакция без сети: платёж, состояние, период;
      2. вне транзакции: возобновление на лицензионном сервере;
      3. короткая транзакция: отметка, что обслуживание действительно вернулось.

    ИДЕМПОТЕНТНО ПОД ПАРАЛЛЕЛЬНОЙ ДОСТАВКОЙ. ЮKassa повторяет уведомления, и
    два пришедших разом оба проходили проверку «уже оплачен?» до того, как
    любое из них писало, — а дальше безусловное `+30 дней` дарило два месяца.
    Строка блокируется и перечитывается здесь. Но ранний выход теперь смотрит
    НЕ ТОЛЬКО на `PAID`: счёт, оплаченный и не возобновлённый, обязан пройти
    шаги 2 и 3 ещё раз, иначе повтор доставки — единственное, что могло бы его
    дочинить, — съедал бы сам себя.
    """
    with transaction.atomic():
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        already_paid = locked.state == Invoice.PAID
        if already_paid and locked.service_resumed_at is not None:
            return
        if not already_paid:
            locked.state = Invoice.PAID
            locked.paid_at = timezone.now()
            fields = ["state", "paid_at"]
            # Записывается ТЕМ ЖЕ коммитом, что и оплата. Раньше вебхук писал
            # его отдельно и ДО `mark_paid`, поэтому откат оставлял счёт с
            # проставленным `payment_ref` и состоянием `draft` — самое
            # неприятное состояние для сверки с выпиской провайдера.
            if payment_ref and not locked.payment_ref:
                locked.payment_ref = payment_ref
                fields.append("payment_ref")
            locked.save(update_fields=fields)
            subscription = locked.organization.subscription
            subscription.state = Subscription.ACTIVE
            subscription.current_period_start = timezone.now()
            subscription.current_period_end = timezone.now() + timedelta(days=30)
            subscription.save(update_fields=["state", "current_period_start",
                                             "current_period_end"])
        organization_id = locked.organization_id
        invoice_pk = locked.pk

    try:
        licensing.set_status(organization_id, "active")
    except licensing.LicensingError as error:
        _log.error("payment recorded for %s but service was not resumed: %s",
                   organization_id, error)
        raise ServiceNotResumed(str(error)) from error

    with transaction.atomic():
        Invoice.objects.filter(pk=invoice_pk).update(
            service_resumed_at=timezone.now())
    invoice.refresh_from_db()


def mark_unpaid(organization: Organization) -> None:
    """The invoice went past due.

    `unpaid`, not `revoked`. Both stop the customer within a minute, but only
    one of them is undone by paying — and a customer who pays a late invoice must
    come back without us touching anything.

    ПОРЯДОК ЗДЕСЬ ОБРАТНЫЙ К `mark_paid`, И ПО ТОЙ ЖЕ ПРИЧИНЕ. Рубильник и есть
    смысл операции: локальная запись «остановлен» без реальной остановки — ложь
    в опасную сторону, потому что по ней мы перестанем напоминать клиенту, а он
    продолжит работать. Поэтому сначала лицензионный сервер, и его отказ
    поднимается наружу, а не прячется за уже изменённым зеркалом.
    """
    licensing.set_status(organization.id, "unpaid")
    with transaction.atomic():
        subscription = (Subscription.objects.select_for_update()
                        .get(organization=organization))
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
        values_in_period=used_this_period,
        total=_round(subscription_amount),
        due_at=(timezone.now() + timedelta(days=7)).date(),
        values_at_period_end=values,
        requests_at_period_end=requests,
    )
