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


# ОДНОРАЗОВЫЕ ПОЧТЫ — ЕДИНСТВЕННЫЙ РЕАЛЬНЫЙ ПУТЬ ЗЛОУПОТРЕБЛЕНИЯ ПРОБНЫМ
# ПЕРИОДОМ, и важно понимать, почему именно он, а не образ.
#
# Образ бесполезен без ключа: без `PSEUDEX_LICENSE_KEY` контейнер не стартует,
# с неизвестным ключом не стартует, и при недоступном лицензионном сервере на
# холодном старте тоже не стартует (гейты L1, L2, L3). Скачать образ заново —
# это ноль. Ключ выпускается только при открытии ссылки из письма, то есть ящик
# уже проверен. Значит цена одной бесплатной пробы = один рабочий ящик.
#
# Список НЕ претендует на полноту — их тысячи, и новые заводятся быстрее, чем
# любой список обновляется. Он поднимает цену: массовая регистрация перестаёт
# быть делом одной минуты. Настоящий предел ставит другое: новая организация —
# это новый `customer_id`, то есть НОВЫЙ ВОЛТ. Псевдонимы сбрасываются, и
# человек, который так работает, каждые три недели теряет связность своих же
# данных. Пробой можно позлоупотреблять; работать на ней нельзя.
DISPOSABLE_DOMAINS = frozenset({
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "temp-mail.org",
    "tempmail.com", "throwawaymail.com", "yopmail.com", "trashmail.com",
    "getnada.com", "dispostable.com", "maildrop.cc", "fakeinbox.com",
    "sharklasers.com", "grr.la", "spam4.me", "mohmal.com", "tempr.email",
    "emailondeck.com", "moakt.com", "luxusmail.org", "1secmail.com",
    "temp-mail.io", "mail-temp.com", "minuteinbox.com", "burnermail.io",
    "tempmailo.com", "mailnesia.com", "inboxkitten.com", "vklfdz.com",
})


def is_disposable(email: str) -> bool:
    """Одноразовый ли это ящик. Только точный домен, без эвристик.

    Эвристика вида «в домене есть temp» отсекает настоящие компании — и это
    ошибка в ту сторону, где мы теряем клиента и не узнаём об этом.
    """
    return email.rsplit("@", 1)[-1].strip().lower() in DISPOSABLE_DOMAINS


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
        subscription = Subscription.objects.create(
            organization=organization,
            plan=plan,
            state=Subscription.TRIAL,
            trial_ends_at=trial_ends,
            current_period_start=now,
            current_period_end=trial_ends,
            # СНИМОК СНИМАЕТСЯ СРАЗУ, а не при первой оплате: цена, показанная
            # человеку на лендинге в момент нажатия кнопки, — это и есть цена,
            # по которой ему придёт первый счёт. Правка тарифа во время его
            # пробного периода не имеет права её изменить.
            terms_monthly_price=plan.monthly_price,
            terms_included_requests=plan.included_requests,
            terms_metered_per_1k=plan.metered_per_1k,
            terms_metered_floor=plan.metered_floor,
            terms_taken_at=now,
        )

    return organization


def issue_first_key(organization: Organization) -> str:
    """The key, issued once the mailbox is proven. Separate from account
    creation so that no credential exists until someone has demonstrated they
    can read the address it was requested for."""
    key = licensing.issue_key(organization.id, organization.subscription.plan.code)
    LicenseKey.record(organization, key, label="первый ключ", environment="live")
    _log.info("first key issued", extra={"org": organization.id,
                                         "plan": organization.subscription.plan.code,
                                         "key_prefix": key[:12]})
    return key


def issue_additional_key(organization: Organization, label: str,
                         environment: str) -> str:
    """Ещё один ключ для той же организации.

    СЕТЬ БОЛЬШЕ НЕ ЖИВЁТ В ТРАНЗАКЦИИ, и решение по бюджету принимается ПОД
    БЛОКИРОВКОЙ. Раньше здесь стоял `@transaction.atomic` вокруг вызова с
    таймаутом в пятнадцать секунд, а проверка `max_keys` была незалоченным
    read-then-write: два одновременных нажатия оба видели место и оба чеканили.
    Ровно то, что комментарий в `create_account` объясняет как недопустимое, —
    сиблинг просто не последовал собственному объяснению.

    Дешёвая проверка идёт первой, чтобы обычный путь не чеканил ключ ради того,
    чтобы тут же его отозвать. Настоящее решение — второе, под
    `select_for_update`, и если оно отрицательное, ТОЛЬКО ЧТО ВЫПУЩЕННЫЙ КЛЮЧ
    ОТЗЫВАЕТСЯ: иначе на лицензионном сервере остаётся активный ключ, не
    привязанный ни к какому кабинету и не видимый ни в одной сверке — та самая
    осиротевшая запись, ради недопущения которой разделён `create_account`.
    """
    allowed = organization.subscription.plan.max_keys
    if organization.keys.filter(revoked_at__isnull=True).count() >= allowed:
        raise ValueError(
            f"на тарифе {organization.subscription.plan.title} доступно "
            f"{allowed} ключ(а/ей); отзовите ненужный или смените тариф"
        )

    key = licensing.issue_key(organization.id, organization.subscription.plan.code)
    try:
        with transaction.atomic():
            locked = (Organization.objects.select_for_update()
                      .get(pk=organization.pk))
            if locked.keys.filter(revoked_at__isnull=True).count() >= allowed:
                raise ValueError(
                    f"на тарифе {organization.subscription.plan.title} доступно "
                    f"{allowed} ключ(а/ей); отзовите ненужный или смените тариф"
                )
            LicenseKey.record(locked, key, label=label, environment=environment)
    except Exception:
        try:
            licensing.revoke_key(LicenseKey.fingerprint(key))
        except licensing.LicensingError as error:
            _log.error("issued key for %s could not be recorded NOR revoked: %s — "
                       "an active key now exists in no cabinet", organization.id, error)
        raise
    return key


class ServiceNotResumed(RuntimeError):
    """Деньги записаны, обслуживание восстановить не удалось.

    Отдельный тип, потому что вызывающему нужны РАЗНЫЕ действия: платёж
    трогать нельзя (он уже наш факт), а возобновление надо повторить. Вебхук
    отвечает на него 502 — «мы не смогли, ретрайте», — ровно как уже отвечает
    на `payments.PaymentError`.
    """


def adopt_current_terms(subscription: Subscription) -> None:
    """Снять условия тарифа на подписку. Продажа и КАЖДОЕ продление.

    Это единственный момент, когда правка тарифа доходит до клиента. Между
    продлениями строка может меняться сколько угодно: счёт считается по снимку,
    поэтому оплаченный месяц нельзя переоценить задним числом.

    Идемпотентно и не требует знать, первая это продажа или сотое продление —
    условия просто становятся текущими.
    """
    plan = subscription.plan
    subscription.terms_monthly_price = plan.monthly_price
    subscription.terms_included_requests = plan.included_requests
    subscription.terms_metered_per_1k = plan.metered_per_1k
    subscription.terms_metered_floor = plan.metered_floor
    subscription.terms_taken_at = timezone.now()
    subscription.save(update_fields=[
        "terms_monthly_price", "terms_included_requests",
        "terms_metered_per_1k", "terms_metered_floor", "terms_taken_at"])


def funnel(step: str, organization_id: str, detail: str = "") -> None:
    """Шаг воронки из биллинга. Импорт внутри — `billing` не должен зависеть от
    `ops` на уровне модуля: это разные приложения, и цикл импорта при загрузке
    Django дороже одной строки здесь."""
    try:
        from ops.analytics_models import Funnel
        Funnel.objects.create(step=step, organization_id=organization_id,
                              detail=detail[:64])
    except Exception:  # noqa: BLE001 — аналитика не ломает деньги
        _log.warning("не удалось отметить шаг воронки %s", step, exc_info=True)


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
            _log.info("payment already handled", extra={"invoice": locked.number})
            return
        if not already_paid:
            _log.info("payment recorded", extra={
                "invoice": locked.number, "org": locked.organization_id,
                "amount": str(locked.total), "ref": payment_ref or ""})
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
            # ПРОДЛЕНИЕ — ЕДИНСТВЕННАЯ ТОЧКА, ГДЕ ПРАВКА ТАРИФА ДОХОДИТ ДО
            # КЛИЕНТА. Внутри той же транзакции, что и новый период: период и
            # условия, по которым он будет посчитан, — один факт.
            adopt_current_terms(subscription)
        organization_id = locked.organization_id
        invoice_pk = locked.pk

    try:
        licensing.set_status(organization_id, "active")
        _log.info("service resumed", extra={"org": organization_id, "invoice": invoice.number})
    except licensing.LicensingError as error:
        _log.error("payment recorded but service NOT resumed", extra={
            "org": organization_id, "invoice": invoice.number, "error": str(error)})
        raise ServiceNotResumed(str(error)) from error

    with transaction.atomic():
        Invoice.objects.filter(pk=invoice_pk).update(
            service_resumed_at=timezone.now())
    funnel("paid", organization_id, str(invoice.total))
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
    _log.warning("service stopped: past due", extra={"org": organization.id})
    with transaction.atomic():
        subscription = (Subscription.objects.select_for_update()
                        .get(organization=organization))
        subscription.state = Subscription.PAST_DUE
        subscription.save(update_fields=["state"])


def _int_or_zero(value: object) -> int:
    """Число из чужого ответа. Не `int(...)`: лицензионный сервер наш, но счёт
    не имеет права падать на его ответе, а `int("x")` — это 500 в кабинете."""
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ПОРОГ ТАРИФИКАЦИИ ЖИВЁТ НА ТАРИФЕ (`Plan.metered_floor`), А НЕ ЗДЕСЬ.
#
# Здесь стояла общая константа 300 000, и она была неверна по форме: худшая
# ошибка счёта равна кванту плюс РЕЗЕРВУ, а резерв у каждого тарифа свой —
# 20 000 у Старта против 400 000 у Промышленного. Одно число на всех делало
# младший тариф в пятнадцать раз щедрее его собственного худшего случая, и
# `included_requests` на нём переставал значить что-либо: 990 ₽ действовали до
# 310 000 запросов.
#
# Порог страхует ОБРЫВ ЦЕПИ ОТЧЁТОВ, а не общую неточность: при живой цепи
# ошибка нулевая (`acked` точен, измерено на трёх масштабах в
# `docs/billing-integrity.md`), и только когда отчёты не доходят, счёт идёт по
# выданной ёмкости с полосой шириной в резерв.
#
# Значение по умолчанию для тарифа, у которого порог не задан: ноль означал бы
# «тарифицировать с первого запроса сверх включённого», то есть выставлять счёт
# по числу, которого при обрыве связи мы не знаем.
DEFAULT_METERED_FLOOR = 100_000

# Срок оплаты счёта. Здесь, а не литералом в `build_invoice`: это число
# напечатано на лендинге и в письме, и три копии одного срока разъезжаются.
INVOICE_DUE_DAYS = 7

# Запас СВЕРХ срока оплаты, после которого обслуживание останавливается.
# Счёт, выставленный в пятницу вечером, физически не может быть оплачен
# банковским переводом до понедельника.
GRACE_DAYS = 3


def build_invoice(organization: Organization, period_start, period_end) -> Invoice:
    """Draft the счёт for a period from the counters the customer's own
    containers reported.

    The overage is computed from the licensing server's numbers and from
    nothing else. The storefront has no way to observe traffic and must not
    acquire one: an independent estimate would be a number the customer cannot
    check against their own gateway's log.
    """
    subscription = organization.subscription
    # УСЛОВИЯ — ИЗ СНИМКА НА ПОДПИСКЕ, а не из строки тарифа: строку правит
    # конструктор в консоли, и правка не имеет права переоценить уже
    # оплаченный период. `plan` остаётся нужен для имени в счёте.
    plan = subscription.plan
    terms = subscription.terms
    reported = licensing.usage(organization.id).get("usage", {})
    if not isinstance(reported, dict):
        reported = {}
    # The billed quantity comes from the licensing server's MONOTONIC
    # accumulator, not from the raw report and not from the entity counters.
    # Entities move with the mask cache; the raw report drops to zero when a
    # customer deletes their vault. `values` never decreases — see
    # docs/billing-integrity.md.
    # КЛАМПЫ, И ВАТЕРМАРКА МОНОТОННА ПО ПОСТРОЕНИЮ. Раньше она была монотонна
    # «потому что счётчик снизу растёт» — а он не растёт: один подписанный
    # отчёт с отрицательными числами под свежим `instance_id` уводил итоги в
    # минус, и минус записывался сюда как ПОСТОЯННАЯ ватермарка, после чего все
    # следующие периоды давали ноль. Вход теперь проверяется, но инвариант,
    # державшийся на чужом поведении, обязан держаться на своём.
    values = max(0, _int_or_zero(reported.get("values")))
    requests = max(0, _int_or_zero(reported.get("requests")))
    # То, на чём будет считаться объёмная часть, когда ставка будет назначена.
    # Накопительное, как и `values`, поэтому за период — разница с ватермаркой.
    billable = max(0, _int_or_zero(reported.get("capacity_billable")))

    # The counter is CUMULATIVE since the installation's first report. What this
    # period used is the difference from the previous invoice's watermark.
    previous = (Invoice.objects
                .filter(organization=organization)
                .exclude(state=Invoice.VOID)
                .order_by("-period_end", "-id")
                .first())
    # И сама ватермарка не может уехать вниз: отрицательная строка могла
    # быть записана до клампов выше и тогда обнуляла бы каждый следующий
    # период навсегда.
    watermark = max(0, previous.values_at_period_end if previous else 0)
    billable_watermark = max(
        0, previous.requests_billable_at_period_end if previous else 0)
    # A counter that went BACKWARDS means the customer started from an empty
    # data directory — a new volume, a restore, a fresh deployment. Billing the
    # negative as zero and re-basing is the only reading that cannot overcharge.
    used_this_period = max(0, values - watermark)

    # НАЧИСЛЕНИЕ ПО ОБЪЁМУ СЧИТАЕТСЯ ОТ ВЫДАННОЙ ЁМКОСТИ, А НЕ ОТ ОТЧЁТА, и это
    # то, что отличает наш счёт от «полиции счётчика». Движок не обслуживает без
    # ёмкости, ёмкость чеканим мы по своим часам, поэтому чтобы провести V
    # запросов непропатченный движок ОБЯЗАН довести `granted` до >= V.
    # Подтверждённый отчёт клиента работает в ОБРАТНУЮ сторону — он уменьшает
    # начисление до фактического расхода. Снять отчёт значит отказаться от
    # скидки за неиспользованное, а не занизить счёт.
    #
    # Ничего не начисляется на защищённые ЗНАЧЕНИЯ: это число рождается внутри
    # контейнера клиента и проверить его нечем. Оно остаётся на счёте справкой —
    # ответом на «что я получил за деньги».
    subscription_amount = terms["monthly_price"]
    metered_requests = max(0, billable - billable_watermark)
    # Порог применяется к ПРЕВЫШЕНИЮ, не к объёму: включённое клиент уже
    # оплатил абонплатой, и мерить надо ровно ту часть, за которую выставляется
    # отдельная строка.
    over = max(0, metered_requests - _int_or_zero(terms["included_requests"]))
    floor = _int_or_zero(terms["metered_floor"]) or DEFAULT_METERED_FLOOR
    if over >= floor and terms["metered_per_1k"] > 0:
        billed_over = over
    else:
        billed_over = 0
    metered_amount = _round(Decimal(billed_over) / Decimal(1000)
                            * terms["metered_per_1k"])

    invoice = Invoice.objects.create(
        organization=organization,
        number=Invoice.next_number(),
        state=Invoice.DRAFT,
        period_start=period_start,
        period_end=period_end,
        plan_amount=_round(subscription_amount),
        values_in_period=used_this_period,
        metered_requests=billed_over,
        metered_amount=metered_amount,
        total=_round(subscription_amount + metered_amount),
        due_at=(timezone.now() + timedelta(days=INVOICE_DUE_DAYS)).date(),
        requests_billable_in_period=max(0, billable - billable_watermark),
        requests_billable_at_period_end=max(billable_watermark, billable),
        values_at_period_end=max(watermark, values),
        requests_at_period_end=requests,
    )
    # КАЖДЫЙ СЧЁТ — СТРОКА С РАЗЛОЖЕНИЕМ. Спор «почему столько» начинается с
    # этой строки, и без неё ответ собирается из четырёх таблиц вручную.
    _log.info("invoice built", extra={
        "invoice": invoice.number, "org": organization.id,
        "period": f"{period_start}..{period_end}",
        "plan_amount": str(invoice.plan_amount),
        "metered_requests": billed_over, "metered_amount": str(metered_amount),
        "total": str(invoice.total)})
    return invoice
