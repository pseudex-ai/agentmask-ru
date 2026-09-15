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

    # ПОРОГ ТАРИФИКАЦИИ — СОБСТВЕННЫЙ РЕЗЕРВ ТАРИФА, А НЕ ОБЩАЯ КОНСТАНТА.
    #
    # Превышение ниже этого числа не начисляется. Обоснование метрологическое:
    # при ПОРВАННОЙ цепи отчётов счёт идёт по выданной ёмкости, и худшая ошибка
    # равна кванту плюс резерву — то есть ровно резерву этого тарифа. При живой
    # цепи ошибка НУЛЕВАЯ (`acked` точен, измерено на трёх масштабах), так что
    # порог страхует обрыв связи, а не общую неточность.
    #
    # Стояло 300 000 одним числом на все тарифы, и это было неверно дважды:
    # резерв у Старта 20 000, у Промышленного 400 000 — одна константа для
    # первого в пятнадцать раз щедрее его собственного худшего случая, а для
    # второго строже. И следствие било по продукту: Старт платил 990 ₽ до
    # 310 000 запросов, то есть `included_requests` младших тарифов не значил
    # почти ничего.
    #
    # Сверяется с `reserve_max` лицензионного сервера так же, как потолок
    # инстансов: расхождение видно на экране тарифов операторской консоли.
    metered_floor = models.BigIntegerField(default=0)

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

    # ГЛОБАЛЬНЫЙ ПОТОЛОК ОБЪЁМА — докупать (перерасход) можно ТОЛЬКО ДО ЭТОГО ЧИСЛА,
    # дальше буфер и остановка. Овердрафт не уходит вверх бесконечно: клиент не
    # получает сюрприз-счёт, а мы подталкиваем к переходу на старший тариф.
    #   зоны: [0..included] абонплата · (included..overage_cap] докуп по ставке ·
    #         (overage_cap..overage_cap+buffer] буфер с оффером апгрейда ·
    #         дальше — жёсткая остановка (как неоплата).
    # 0 = потолка нет (Enterprise / по договору).
    overage_cap_requests = models.BigIntegerField(default=0)
    # Небольшой запас сверх потолка: сервис ещё работает, но кабинет показывает
    # оффер «перейди на старший тариф, первый месяц выгодно — ты уже пользуешься».
    buffer_requests = models.BigIntegerField(default=0)
    # Скидка на ПЕРВЫЙ месяц старшего тарифа, когда предлагаем апгрейд на потолке
    # (в процентах). 0 = без скидки.
    upgrade_first_month_discount_pct = models.PositiveSmallIntegerField(default=0)

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

    # ПОТОЛОК ОБЪЁМА — ОРТОГОНАЛЬНЫЙ ФАКТ, А НЕ СОСТОЯНИЕ ЖИЗНЕННОГО ЦИКЛА.
    #
    # Было отдельным состоянием `capped`, и это ломалось трижды: оно СТИРАЛО
    # `trial`/`active`, поэтому (1) выставление счетов, отбирающее TRIAL/ACTIVE,
    # никогда не касалось остановленного по объёму — новый период не наступал,
    # ватермарка не двигалась, перерасход не выставлялся, клиент стоял ВЕЧНО;
    # (2) возобновление не знало, куда вернуть — жёстко ставило ACTIVE, и триал,
    # упёршийся в потолок, «оживал» оплаченным без оплаты; (3) кабинет и консоль
    # рисовали его как «ОТМЕНЕНА», а MRR его терял. Всё это исчезает, когда
    # остановка по объёму — булев флаг ПОВЕРХ настоящего состояния: капнутый
    # клиент остаётся TRIAL/ACTIVE (счёт выставится сам на своём переходе), а
    # `is_serving` и рендер отдельно учитывают флаг. Ставится/снимается в
    # `run_billing_cycle` вместе с рубильником на лицензионном сервере.
    volume_capped = models.BooleanField(default=False)

    trial_ends_at = models.DateTimeField()
    # Set when the customer turns off renewal. Service continues to the end of
    # the paid period: stopping at the moment of cancellation would be charging
    # for time and then not delivering it.
    cancel_at_period_end = models.BooleanField(default=False)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()

    # УСЛОВИЯ, НА КОТОРЫХ ПРОДАНО, СНИМКОМ — А НЕ ССЫЛКОЙ НА ИЗМЕНЯЕМУЮ СТРОКУ.
    #
    # `plan` — это указатель, и правка тарифа меняла условия ВСЕМ немедленно, в
    # том числе посреди оплаченного периода: клиент платил за месяц по одной
    # цене и получал счёт по другой. Так работать нельзя, и починить это ссылкой
    # нельзя тоже — строка одна на всех по построению.
    #
    # Поэтому цена и всё, из чего считается счёт, СНИМАЮТСЯ при продаже и
    # обновляются РОВНО в момент продления (`services.adopt_current_terms`,
    # вызывается из `mark_paid`). Между продлениями строка тарифа может меняться
    # сколько угодно — счёт этого клиента она не тронет.
    #
    # Чего снимок НЕ покрывает и почему: потолок инстансов и RPM исполняет
    # лицензионный сервер, и он знает тарифы по КОДУ, а не по версии условий.
    # Эти два числа меняются сразу для всех, и конструктор в консоли говорит об
    # этом прямо, вместо того чтобы обещать несуществующую изоляцию.
    terms_monthly_price = models.DecimalField(max_digits=10, decimal_places=2,
                                              null=True, blank=True)
    terms_included_requests = models.BigIntegerField(null=True, blank=True)
    terms_metered_per_1k = models.DecimalField(max_digits=8, decimal_places=2,
                                               null=True, blank=True)
    terms_metered_floor = models.BigIntegerField(null=True, blank=True)
    terms_taken_at = models.DateTimeField(null=True, blank=True)

    # ДО КАКОЙ ОТМЕТКИ КЛИЕНТ УЖЕ ПРЕДУПРЕЖДЁН О РАСХОДЕ В ЭТОМ ПЕРИОДЕ.
    #
    # Превышение — это счёт, а не рубильник, и в этом вся идея: остановить
    # шлюз значит остановить бизнес клиента из-за наших денег. Но у «не
    # останавливаем» есть обратная сторона, и до сих пор она была открыта:
    # клиент узнавал о перерасходе ИЗ ПИСЬМА СО СЧЁТОМ, когда платить уже
    # поздно и обсуждать нечего.
    #
    # Ступени: `included` — «включённый объём выбран», `floor` — «дальше
    # начинает капать». Хранится ПРОЙДЕННАЯ ступень, а не флаг: письмо уходит
    # один раз на ступень и обнуляется при продлении, поэтому цикл может
    # запускаться хоть каждую минуту.
    NOTIFIED_NONE = ""
    NOTIFIED_INCLUDED = "included"
    NOTIFIED_METERED = "metered"
    NOTIFIED_BUFFER = "buffer"      # вошёл в буфер за потолком — послан оффер апгрейда
    volume_notified = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        ordering = ["-current_period_start"]

    def __str__(self) -> str:
        return f"{self.organization_id}: {self.plan_id} ({self.state})"

    @property
    def terms(self) -> dict[str, object]:
        """Условия, по которым считается счёт ЭТОГО клиента.

        Снимок, если он есть; иначе текущая строка тарифа — так подписки,
        заведённые до появления снимка, продолжают считаться, а не падают.
        Возврат к строке безопасен именно потому, что снимок ставится при
        первой же продаже и при каждом продлении.
        """
        if self.terms_taken_at is None:
            return {"monthly_price": self.plan.monthly_price,
                    "included_requests": self.plan.included_requests,
                    "metered_per_1k": self.plan.metered_per_1k,
                    "metered_floor": self.plan.metered_floor,
                    "source": "тариф"}
        return {"monthly_price": self.terms_monthly_price,
                "included_requests": self.terms_included_requests,
                "metered_per_1k": self.terms_metered_per_1k,
                "metered_floor": self.terms_metered_floor,
                "source": "снимок"}

    @property
    def on_old_terms(self) -> bool:
        """Отличаются ли условия клиента от текущих. Для экрана конструктора:
        правка тарифа обязана быть видна как «столько-то клиентов доработают
        период на прежних условиях»."""
        if self.terms_taken_at is None:
            return False
        terms = self.terms
        return (terms["monthly_price"] != self.plan.monthly_price
                or terms["included_requests"] != self.plan.included_requests
                or terms["metered_per_1k"] != self.plan.metered_per_1k
                or terms["metered_floor"] != self.plan.metered_floor)

    @property
    def is_serving(self) -> bool:
        """Whether the customer should be able to work right now.

        A rendering helper. The authority is the licensing server, and the two
        agreeing is a consequence of every state change going through
        `billing.services`, never of this property being consulted.

        `volume_capped` gates it separately: a customer who hit the volume
        ceiling is stopped on the licensing server while their lifecycle state
        stays TRIAL/ACTIVE, so serving is state AND not capped.
        """
        if self.state in (self.TRIAL, self.ACTIVE):
            return not self.volume_capped
        return False


class PlanChange(models.Model):
    """Кто, когда и что поменял в тарифе.

    ЖУРНАЛ, А НЕ ИСТОЧНИК ИСТИНЫ. Счёт считается по снимку на подписке; здесь
    лежит история, чтобы через полгода можно было ответить «а сколько стоил
    Рабочий в июле» и «кто поставил эту цену». Без такого журнала правка через
    экран неотличима от посева, и первый же спор о цене упирается в память.
    """

    plan = models.ForeignKey("Plan", on_delete=models.CASCADE, related_name="changes")
    field = models.CharField(max_length=32)
    was = models.CharField(max_length=64, blank=True)
    became = models.CharField(max_length=64, blank=True)
    actor = models.CharField(max_length=200)
    at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self) -> str:
        return f"{self.plan_id}.{self.field}: {self.was} -> {self.became}"


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

    # СКИДКА ПО СПЕЦ-ПРЕДЛОЖЕНИЮ, ОТДЕЛЬНОЙ СТРОКОЙ. Оффер (адресный или по
    # промокоду) применяется при построении счёта: `discount_amount` — сколько
    # ₽ снято, `discount_offer` — какой (для акта и разбора «почему столько»).
    # Отдельной строкой по той же причине, что и объём: бухгалтер сверяет
    # разложение, а скидка, растворённая в итоге, превращает расхождение в
    # расследование. SET_NULL — счёт переживает удаление оффера.
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                          default=Decimal("0"))
    discount_offer = models.ForeignKey("Offer", null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name="invoices")
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

    @property
    def metered_per_1k(self) -> Decimal:
        """The overage rate THIS invoice was cut at, back-derived from its own
        figures. Not read off the plan: a plan changes, an issued document
        does not, and a rate printed from the live plan would misstate a
        line the customer already reconciled."""
        if not self.metered_requests:
            return Decimal("0")
        return (self.metered_amount * 1000 / self.metered_requests).quantize(Decimal("0.01"))

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


class Offer(models.Model):
    """Спец-предложение оператора: скидка, настраиваемая в админке. АДРЕСНАЯ
    (конкретной организации) или ПУБЛИЧНАЯ (по промокоду). Применяется при оплате.

    Три оси: КОМУ (organization или code-промокод), СКОЛЬКО (% или ₽), НА ЧТО
    (любой счёт / первый месяц / переход на тариф / годовая оплата)."""

    APPLIES_ANY = "any"
    APPLIES_FIRST_MONTH = "first_month"
    APPLIES_PLAN = "plan"
    APPLIES_ANNUAL = "annual"
    APPLIES = [
        (APPLIES_ANY, "любой счёт"),
        (APPLIES_FIRST_MONTH, "первый месяц"),
        (APPLIES_PLAN, "переход на тариф"),
        (APPLIES_ANNUAL, "годовая оплата"),
    ]

    title = models.CharField(max_length=120)
    # Промокод для ПУБЛИЧНЫХ (клиент вводит в кабинете). Пусто — адресное.
    code = models.SlugField(max_length=40, blank=True, db_index=True)
    # Адресное: только этой организации. Null — по промокоду / всем.
    organization = models.ForeignKey(Organization, null=True, blank=True,
                                     on_delete=models.CASCADE, related_name="offers")
    # Скидка: процент И/ИЛИ фикс. Процент применяется первым, затем фикс.
    discount_pct = models.PositiveSmallIntegerField(default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal("0"))
    applies_to = models.CharField(max_length=16, choices=APPLIES, default=APPLIES_ANY)
    # На какой тариф (для applies_to plan/annual). Null — любой.
    target_plan = models.ForeignKey(Plan, null=True, blank=True,
                                    on_delete=models.CASCADE, related_name="offers")
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(default=0)      # 0 = без лимита
    uses = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        who = self.organization_id or (self.code or "публичное")
        return f"{self.title} ({who})"

    def is_available(self, now=None) -> bool:
        """Действует ли сейчас: активно, в сроке, не исчерпан лимит."""
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses and self.uses >= self.max_uses:
            return False
        return True

    def apply_to(self, amount: Decimal) -> Decimal:
        """Цена после скидки (процент, затем фикс), не ниже нуля."""
        amount = Decimal(amount)
        if self.discount_pct:
            amount = amount * (Decimal(100 - int(self.discount_pct)) / Decimal(100))
        amount = amount - (self.discount_amount or Decimal("0"))
        return max(Decimal("0"), amount.quantize(Decimal("0.01")))
