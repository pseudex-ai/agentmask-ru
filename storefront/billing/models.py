"""Plans, subscriptions, keys and invoices.

The billing model is deliberately small — three flat plans and one overage
line — because that is what is actually sold. A usage-based billing engine was
considered and rejected in `docs/tz-site-stack.md`: it would have added a
service without removing the part that is genuinely hard here, which is Russian
invoicing.

WHAT LIVES HERE AND WHAT DOES NOT. The licensing server owns whether a key may
lease and how many requests were made. This module owns what the customer
bought and what they owe. `Subscription.state` is a MIRROR for rendering and is
never consulted to decide whether service continues.
"""

import hashlib
import secrets
from decimal import Decimal

from django.db import models
from django.utils import timezone

from accounts.models import Organization


class Plan(models.Model):
    """A tariff. Rows, not constants, so that changing a price does not need a
    deploy and an existing subscription can keep the terms it was sold on."""

    code = models.SlugField(primary_key=True, max_length=32)
    title = models.CharField(max_length=100)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)

    # ВКЛЮЧЁННЫЙ ОБЪЁМ, И ЕДИНИЦА — ЗАПРОС, а не защищённое значение. Поле
    # называлось `included_values`, и это пережиток решения, принятого до
    # `docs/billing-integrity.md`: счёт считается в запросах, потому что запрос
    # виден в логе шлюза САМОГО клиента и наш счёт можно с ним сверить, а число
    # защищённых значений рождается внутри его контура и проверить его нечем.
    # Полоса в кабинете и так считала запросы; расходилось только имя, и с
    # появлением строки по объёму это расхождение вышло бы к клиенту — «40%
    # полосы» рядом с начислением сверх лимита.
    included_requests = models.BigIntegerField(default=0)
    rpm_limit = models.PositiveIntegerField(default=60)

    # СТАВКА ЗА ТЫСЯЧУ ЗАПРОСОВ СВЕРХ ВКЛЮЧЁННОГО. Ноль — тариф не
    # тарифицируется по объёму вовсе.
    #
    # Строкой, а не константой, по той же причине, что и цена: ставка меняется
    # без выката, а подписка, проданная на старых условиях, их сохраняет.
    #
    # ЛЕСТНИЦА ОБЯЗАНА ОКУПАТЬ ПОДЪЁМ. Ставка — около 80% от собственной
    # «включённой» цены тарифа и УБЫВАЕТ по лестнице, поэтому перерасход всегда
    # дороже перехода на тариф выше: Рабочий на миллионе запросов стоит
    # 22 500 ₽ против 11 900 ₽ на Промышленном. Единая ставка для всех тарифов
    # уже была здесь однажды и давала обратное — объём через перерасход выходил
    # в десятки раз дешевле того же объёма внутри тарифа, никто никогда не
    # переходил, и выручка упиралась в цену входа.
    metered_per_1k = models.DecimalField(max_digits=8, decimal_places=2,
                                         default=Decimal("0"))

    # Selling copy, as data: who this tier is for. Here rather than in the
    # template because the tiers differ only in these strings, and a template
    # with three `{% if plan.code == ... %}` branches is a template nobody
    # updates when a fourth tier appears.
    audience = models.CharField(max_length=120, blank=True)

    # THE TIER. The only boundary decided on OUR side: the licensing server
    # knows which instance ids leased recently and refuses one beyond the plan.
    max_instances = models.PositiveIntegerField(default=1)
    max_keys = models.PositiveIntegerField(default=2)
    is_public = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return f"{self.title} ({self.code})"


class Subscription(models.Model):
    """What an organisation bought, and where it is in its lifecycle."""

    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    STATES = [
        (TRIAL, "пробный период"),
        (ACTIVE, "активна"),
        (PAST_DUE, "не оплачена"),
        (CANCELLED, "отменена"),
    ]

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE,
                                        related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    state = models.CharField(max_length=16, choices=STATES, default=TRIAL)
    trial_ends_at = models.DateTimeField()
    # Set when the customer turns off renewal. Service continues to the end of
    # the paid period: stopping at the moment of cancellation would be charging
    # for time and then not delivering it.
    cancel_at_period_end = models.BooleanField(default=False)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()

    class Meta:
        ordering = ["-current_period_start"]

    def __str__(self) -> str:
        return f"{self.organization_id}: {self.plan_id} ({self.state})"

    @property
    def is_serving(self) -> bool:
        """Whether the customer should be able to work right now.

        A rendering helper. The authority is the licensing server, and the two
        agreeing is a consequence of every state change going through
        `billing.services`, never of this property being consulted.
        """
        if self.state in (self.TRIAL, self.ACTIVE):
            return True
        return False


class LicenseKey(models.Model):
    """A key the customer can use, stored so it can be RECOGNISED but not read.

    Only a prefix and a hash are kept. The full key is shown once, at issue
    time, and never again — the same reason a password is not recoverable. It is
    a bearer credential for the customer's whole gateway, and a support screen
    that can display it turns every person with access to our admin into someone
    who can start a container as that customer.

    Losing it is recoverable by issuing a new one, which is cheap. Leaking it is
    not recoverable at all.
    """

    ENVIRONMENTS = [("live", "прод"), ("test", "стенд")]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name="keys")
    label = models.CharField(max_length=100, blank=True)
    environment = models.CharField(max_length=8, choices=ENVIRONMENTS, default="live")
    prefix = models.CharField(max_length=24)
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.prefix}… ({self.organization_id})"

    @staticmethod
    def fingerprint(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def record(cls, organization: Organization, key: str, label: str,
               environment: str) -> "LicenseKey":
        return cls.objects.create(
            organization=organization,
            label=label,
            environment=environment,
            prefix=key[:16],
            key_hash=cls.fingerprint(key),
        )


class Invoice(models.Model):
    """A счёт, and after payment the basis for an акт.

    Amounts are `Decimal`, never float: a rounding error in a figure a customer
    reconciles against their bank statement is not a cosmetic bug, it is a
    dispute.
    """

    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"
    STATES = [
        (DRAFT, "черновик"), (ISSUED, "выставлен"),
        (PAID, "оплачен"), (VOID, "аннулирован"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT,
                                     related_name="invoices")
    number = models.CharField(max_length=32, unique=True)
    state = models.CharField(max_length=16, choices=STATES, default=DRAFT)
    period_start = models.DateField()
    period_end = models.DateField()

    plan_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    # INFORMATION, never a charge: what the subscription protected this period.
    # It rides on the invoice because it is the answer to "what did I get for
    # the money", and because a figure far above the plan's guide is what
    # prompts an upgrade conversation. It is deliberately NOT a line item —
    # a table row priced at 0 ₽ reads to an accountant like a billing error.
    values_in_period = models.BigIntegerField(default=0)

    # ОТДЕЛЬНОЙ СТРОКОЙ, А НЕ СЛАГАЕМЫМ В ИТОГЕ. Бухгалтер клиента сверяет счёт
    # с актом и с банковской выпиской; сумма, в которой абонплата и объём
    # слиплись, превращает каждое расхождение в расследование. Количество лежит
    # рядом с деньгами, чтобы строку можно было пересчитать глазами по ставке из
    # тарифа.
    metered_requests = models.BigIntegerField(default=0)
    metered_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                         default=Decimal("0"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateField(null=True, blank=True)

    # КОГДА ОБСЛУЖИВАНИЕ БЫЛО ВОССТАНОВЛЕНО НА ЛИЦЕНЗИОННОМ СЕРВЕРЕ, а не когда
    # деньги записаны у нас. Два разных факта, и раньше они были одним.
    #
    # `mark_paid` держал сетевой вызов внутри `transaction.atomic()`, поэтому
    # его отказ откатывал и оплату: счёт возвращался в `draft`, а вебхук на
    # повторной доставке видел «не оплачен» и повторял ту же неудачу вечно.
    # Теперь деньги записываются первыми и не откатываются никогда, а вот это
    # поле остаётся пустым, пока возобновление не доехало.
    #
    # Без него повтор нечем было бы дочинить: ранний выход по `state == PAID`
    # съедал бы вторую попытку. С ним повторная доставка сама доводит дело до
    # конца, а сторож видит оплаченные счета с пустым полем как список того,
    # где мы должны клиенту работу.
    service_resumed_at = models.DateTimeField(null=True, blank=True)

    # Whatever the payment provider calls this. Nullable because a customer
    # paying by bank transfer against a счёт never gets one.
    #
    # UNIQUE when present: ЮKassa redelivers notifications, and two arriving at
    # once both passed the "already paid?" check and both ran mark_paid, which
    # unconditionally extends the period by 30 days. Two deliveries, two free
    # months. The database refuses the second now, whatever the application
    # threads do.
    payment_ref = models.CharField(max_length=128, blank=True, null=True,
                                   unique=True, default=None)

    # The licensing server reports CUMULATIVE requests since the installation's
    # first report — never a period. Billing subtracted nothing, so month two
    # charged overage on the lifetime total: steady 150k/month on a 100k plan
    # billed 50k, then 200k, then 350k. Month twelve was 34x the truth.
    #
    # Storing the reading this invoice was cut at makes the next one a
    # subtraction. It is on the invoice rather than on the subscription because
    # it must survive re-issuing and voiding — the previous ISSUED invoice is
    # the watermark, not the current state of anything.
    # ЁМКОСТЬ ЗА ПЕРИОД — ОСНОВАНИЕ БУДУЩЕГО НАЧИСЛЕНИЯ, записанное уже сейчас.
    #
    # Ставка за запрос — продуктовое решение, и оно ещё не принято; выдумывать
    # её здесь нельзя. Но число, на котором она будет считаться, уже верное и
    # уже проверяемое, и его надо ватермаркить С ЭТОГО МОМЕНТА: иначе первый же
    # счёт по объёму придётся считать от накопительного итога, а это ровно та
    # ошибка, из-за которой месяц двенадцатый выставлялся в тридцать четыре
    # раза больше правды.
    requests_billable_in_period = models.BigIntegerField(default=0)
    requests_billable_at_period_end = models.BigIntegerField(default=0)

    values_at_period_end = models.BigIntegerField(default=0)
    # Kept alongside, not billed on: the cabinet shows both, and the rate
    # guardrail is expressed in requests even though the meter is not.
    requests_at_period_end = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-period_start", "-number"]

    def __str__(self) -> str:
        return f"{self.number} — {self.organization_id} — {self.total} ₽"

    @staticmethod
    def next_number(when=None) -> str:
        """`PS-2026-08-4f3a`. Sequential-looking but not sequential.

        A strictly sequential invoice number tells every customer how many
        invoices we have issued, which for a young company is information we do
        not owe them. Uniqueness is enforced by the column, not by the format.
        """
        when = when or timezone.now()
        # Four hex digits is 65 536 values a month against a unique column: by
        # 250 invoices in one month a collision is more likely than not, and it
        # surfaces as an uncaught IntegrityError. Eight makes it negligible; the
        # caller still retries, because "negligible" is not "impossible".
        # PS, not VG: the prefix outlived the rename to pseudex, and it is the
        # one identifier a customer quotes back in a payment reference.
        return f"PS-{when:%Y-%m}-{secrets.token_hex(4)}"
