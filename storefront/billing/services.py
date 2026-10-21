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

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from accounts.models import Membership, Organization, User
from billing import licensing, payments
from billing.models import Invoice, LicenseKey, Offer, Plan, Subscription

_log = logging.getLogger("billing.services")

# ДЛИТЕЛЬНОСТЬ ПРОБЫ ЖИВЁТ В СТРОКЕ ТАРИФА, А НЕ ЗДЕСЬ.
#
# Это число осталось ровно одним: значением по умолчанию, которым `seed_plans`
# создаёт пробный тариф в первый раз. Дальше его правят в админке, и правка
# доходит до следующей регистрации без выката. Читать его в коде вместо
# `trial_plan().trial_days` значит вернуть ту самую константу, ради снятия
# которой всё и делалось.
TRIAL_DAYS_SEED = 14


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


def trial_plan() -> Plan | None:
    """Строка тарифа, на которой живёт проба. Пусто — пробы в продукте нет.

    Отсутствие строки это РАБОЧЕЕ состояние, а не сбой: владелец имеет право
    выключить бесплатный период вовсе, сняв отметку в админке, и тогда новый
    аккаунт заводится сразу платным. Поэтому здесь `None`, а не исключение.
    """
    return Plan.objects.filter(is_trial=True).first()


def signup_plans() -> list[Plan]:
    """Что можно выбрать в форме регистрации: бесплатный тариф первым, затем
    публичные платные.

    ОДИН СПИСОК НА ЭКРАН И НА ПРОВЕРКУ. Лендинг рисует из него выпадашку, а
    `signup` по нему же решает, существует ли присланный код: два списка
    разошлись бы на первом же непубличном тарифе. Бесплатный тариф в него
    входит, хотя он `is_public=False`: непубличность значит «нет в карточках
    цен как товар», а не «нельзя выбрать» — это единственный вход без денег.
    """
    trial = trial_plan()
    paid = list(Plan.objects.filter(is_public=True))
    return ([trial] if trial is not None else []) + paid


def trial_days() -> int:
    """Сколько дней бесплатно. Ноль — бесплатного периода нет.

    Печатается на лендинге и в юридических страницах, поэтому читается отсюда, а
    не из константы: обещание на сайте и правило, по которому заводится аккаунт,
    обязаны быть одним числом. Раньше это была `TRIAL_DAYS = 14` в коде, и
    поменять срок пробы значило выкатить релиз.
    """
    plan = trial_plan()
    return plan.trial_days if plan is not None else 0


def signup_ip_hash(client_ip: str) -> str:
    """Необратимая метка адреса, с которого пришла регистрация.

    Сам адрес не хранится нигде: для ответа «с этого адреса уже заводили
    аккаунт» достаточно совпадения хешей, а хранение IP это хранение
    персональных данных ради анти-абуза — цена, которую платить незачем.

    Соль постоянная, в отличие от суточной в аналитике, и это осознанно: там
    задача противоположная — не дать связать визиты между днями, здесь связать
    регистрации через месяцы и есть смысл.
    """
    if not client_ip:
        return ""
    salt = getattr(settings, "SECRET_KEY", "")
    return hashlib.sha256(f"signup|{salt}|{client_ip}".encode()).hexdigest()


# Домены, по которым организации НЕ сопоставляются. Общий ящик не говорит о
# компании ничего: сравнивать по нему значит выдать пробу первому пришедшему с
# gmail и отказать всем остальным в стране.
PUBLIC_MAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yandex.ru", "ya.ru", "yandex.com",
    "mail.ru", "inbox.ru", "list.ru", "bk.ru", "internet.ru",
    "rambler.ru", "lenta.ru", "autorambler.ru",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "pm.me", "tutanota.com", "tuta.io",
    "zoho.com", "aol.com", "gmx.com", "fastmail.com", "qq.com",
})


def email_domain(email: str) -> str:
    _, _, domain = email.partition("@")
    return domain.strip().lower()


def trial_allowed(ip_hash: str, domain: str) -> bool:
    """Первая ли это проба для этого адреса и этой компании.

    ЧЕГО ЭТА ПРОВЕРКА НЕ УМЕЕТ, СКАЗАНО ПРЯМО. Отпечатка машины у нас нет:
    контейнер работает на железе клиента, `PSEUDEX_INSTANCE_ID` заново случаен
    при каждом старте, а запасной `installation_id` лежит в томе и исчезает
    вместе с ним. Софт на чужой машине не может дать метку, переживающую
    `docker rm -v`, и обещать обратное было бы враньём. Поэтому сверяется то,
    что видно НАМ, а настоящая защита от фарма — не этот список, а узость
    самого бесплатного тарифа: брать его пачками незачем.

    Промах в обе стороны возможен и признан: один офис за NAT это один адрес, и
    второй живой клиент оттуда пробы не получит (снимается кнопкой в админке), а
    смена провайдера плюс новый домен её вернут. Это фильтр, а не забор.
    """
    from accounts.models import Organization as _Organization
    if ip_hash and _Organization.objects.filter(signup_ip_hash=ip_hash).exists():
        return False
    if domain and domain not in PUBLIC_MAIL_DOMAINS and \
            _Organization.objects.filter(signup_email_domain=domain).exists():
        return False
    return True


def create_account(email: str, display_name: str, plan_code: str,
                   client_ip: str) -> Organization:
    """Create the account. On the free plan the key follows before any payment;
    on a paid plan the key follows the payment.

    The free path is the whole product promise on the storefront side: the
    single metric is time from first visit to first masked request, and every
    step between those two points is a place to lose someone. Asking for a
    card, or for ИНН, or for a confirmation click before the key exists, each
    add minutes to that number and buy nothing — the key is worthless without
    our licensing server, which we can switch off at any time.

    ПЛАТНЫЙ ТАРИФ С ЛЕНДИНГА — ЭТО ПОКУПКА, А НЕ ПРОБА С НАМЕРЕНИЕМ. Раньше
    любой выбор в форме давал те же четырнадцать бесплатных дней, и слово
    «Старт — 990 ₽/мес» рядом с «ключ работает сразу и бесплатно» читалось как
    «Старт бесплатно две недели». Теперь бесплатных входов ровно один — тариф
    `free`, — а выбравший платный получает подписку в состоянии `pending`:
    без пробы, без ключа, с кнопкой оплаты в кабинете. Ключ выпускается после
    денег (`may_issue_keys`), и за оплату без пробы ему положены подарочные
    дни (`bonus_days_for`).
    """
    intended = Plan.objects.get(code=plan_code)
    trial = trial_plan()
    if trial is None or intended.code != trial.code:
        return _create_pending_account(email, display_name, intended, client_ip)
    ip_hash = signup_ip_hash(client_ip)
    domain = email_domain(email)

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
        # ПРОБА ИДЁТ НА СВОЁМ ТАРИФЕ, А НЕ НА ВЫБРАННОМ.
        #
        # Раньше выбор из формы становился тарифом подписки, и две недели на
        # «Промышленном» означали миллион запросов бесплатно — с каждой новой
        # почты заново. Теперь выбор это НАМЕРЕНИЕ (`intended_plan`), а
        # обслуживание идёт на пробном тарифе с его собственными лимитами.
        #
        # Повторная регистрация аккаунт получает, но без бесплатных дней: проба
        # кончается в момент создания, и чтобы начать работать, надо заплатить.
        granted = trial_allowed(ip_hash, domain)
        plan = trial
        trial_ends = now + timedelta(days=trial.trial_days) if granted else now
        organization.signup_ip_hash = ip_hash
        organization.signup_email_domain = domain
        organization.trial_granted = granted
        organization.save(update_fields=["signup_ip_hash", "signup_email_domain",
                                         "trial_granted"])
        subscription = Subscription.objects.create(
            organization=organization,
            plan=plan,
            intended_plan=intended,
            state=Subscription.TRIAL,
            trial_ends_at=trial_ends,
            current_period_start=now,
            current_period_end=trial_ends,
            # СНИМОК СНИМАЕТСЯ СРАЗУ, а не при первой оплате, и снимается он
            # с тарифа ОБСЛУЖИВАНИЯ — на пробе это пробный тариф. Условия
            # выбранного платного снимутся в момент, когда за него заплатят
            # (`mark_paid` -> `adopt_current_terms`): обещать сегодняшнюю цену
            # тому, кто ещё не заплатил, мы не можем, а вот не менять её посреди
            # уже оплаченного периода — обязаны.
            terms_monthly_price=plan.monthly_price,
            terms_included_requests=plan.included_requests,
            terms_metered_per_1k=plan.metered_per_1k,
            terms_metered_floor=plan.metered_floor,
            terms_taken_at=now,
        )

    return organization


def _create_pending_account(email: str, display_name: str, plan: Plan,
                            client_ip: str) -> Organization:
    """An account that has chosen a paid plan and not paid yet.

    Same split as the free path — the account commits on its own, the
    licensing server is not involved at all: it learns about the organisation
    when the first key is issued, and that happens after `mark_paid`. The
    trial is NOT granted and not refused either — it was never asked for —
    and `trial_ends_at` sits in the past so no code path can read a free window
    into it. The terms snapshot is taken from the plan being bought: that is
    the price the invoice will carry, and `mark_paid` → `adopt_current_terms`
    re-takes it on the day the money arrives.
    """
    ip_hash = signup_ip_hash(client_ip)
    domain = email_domain(email)
    with transaction.atomic():
        user, _ = User.objects.get_or_create(email=email)
        organization = Organization.objects.create(display_name=display_name or email)
        Membership.objects.create(user=user, organization=organization,
                                  role=Membership.ROLE_OWNER)
        now = timezone.now()
        organization.signup_ip_hash = ip_hash
        organization.signup_email_domain = domain
        organization.trial_granted = False
        organization.save(update_fields=["signup_ip_hash", "signup_email_domain",
                                         "trial_granted"])
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            intended_plan=plan,
            state=Subscription.PENDING,
            trial_ends_at=now,
            current_period_start=now,
            current_period_end=now,
            terms_monthly_price=plan.monthly_price,
            terms_included_requests=plan.included_requests,
            terms_metered_per_1k=plan.metered_per_1k,
            terms_metered_floor=plan.metered_floor,
            terms_taken_at=now,
        )
    _log.info("pending account created", extra={"org": organization.id,
                                                "plan": plan.code})
    return organization


class KeyNotAvailable(ValueError):
    """A key was asked for while the subscription pays for nothing.

    A `ValueError` so the cabinet's existing handling shows the text; its own
    class so a caller can tell «pay first» from «too many keys»."""


def may_issue_keys(subscription: Subscription | None) -> bool:
    """Is there a paid-for or free-for-now service for a key to open.

    THE KEY IS WHAT THE MONEY BUYS, AND A LIVE TRIAL IS THE ONE EXCEPTION.
    Before this gate the cabinet minted keys for any organisation in any state:
    a paid signup could take a key before paying, and a refused-trial repeat
    got one that leased for up to an hour until the billing cycle stopped it.
    Both were the same hole — a credential handed out with nothing behind it.
    `past_due` and `cancelled` are refused for the same reason: the licensing
    server would not honour the key, and a key that does not work is a support
    ticket, not a feature.
    """
    if subscription is None:
        return False
    if subscription.state == Subscription.ACTIVE:
        return True
    return (subscription.state == Subscription.TRIAL
            and subscription.trial_ends_at > timezone.now())


def issue_first_key(organization: Organization) -> str:
    """The key, issued once the mailbox is proven. Separate from account
    creation so that no credential exists until someone has demonstrated they
    can read the address it was requested for."""
    if not may_issue_keys(getattr(organization, "subscription", None)):
        raise KeyNotAvailable("ключ выпускается после оплаты тарифа")
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
    if not may_issue_keys(organization.subscription):
        raise KeyNotAvailable("ключ выпускается после оплаты тарифа")
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
            now = timezone.now()
            # Был ли месячный период живым ДО оплаты — до того, как трогаем state.
            period_live = (subscription.state != Subscription.TRIAL
                           and subscription.current_period_end is not None
                           and subscription.current_period_end > now)
            subscription.state = Subscription.ACTIVE
            # Новый период = свежий включённый объём: остановка по объёму снята
            # ПРЯМО ЗДЕСЬ, а не только на следующем тике цикла, чтобы оплативший
            # клиент не видел «лимит исчерпан» ещё час.
            subscription.volume_capped = False
            fields_sub = ["state", "volume_capped"]
            if locked.is_annual:
                # ГОДОВОЙ ПЛАТЁЖ НЕ ДЕЛАЕТ ПЕРИОД ГОДОВЫМ (вариант A): оплачивает
                # БАЗУ на 12 мес вперёд, месячный цикл идёт своим чередом. И НЕ
                # перезапускает ЖИВОЙ месячный период — иначе сдвигает каденс и
                # дарит лишний частичный месяц. Месячный период стартуем только
                # если его нет (триал или истёкший).
                subscription.base_paid_through = now + timedelta(
                    days=ANNUAL_PERIOD_DAYS)
                fields_sub.append("base_paid_through")
                if not period_live:
                    subscription.current_period_start = now
                    subscription.current_period_end = now + timedelta(days=30)
                    fields_sub += ["current_period_start", "current_period_end"]
            else:
                # Месячное продление всегда открывает новый 30-дневный период.
                # ПОДАРОЧНЫЕ ДНИ ПРИБАВЛЯЮТСЯ К ПЕРИОДУ, а не к счёту: человек
                # платит за месяц и получает месяц плюс подарок обслуживания.
                # Число берётся СО СЧЁТА, а не из тарифа: обещание дано при
                # выставлении, и правка тарифа между выставлением и платежом не
                # имеет права его уменьшить.
                subscription.current_period_start = now
                subscription.current_period_end = now + timedelta(
                    days=30 + locked.bonus_days)
                fields_sub += ["current_period_start", "current_period_end"]
            # СЧЁТ, КОТОРЫЙ ПЕРЕВОДИТ НА ТАРИФ, ПЕРЕВОДИТ ЕГО ЗДЕСЬ.
            #
            # До `adopt_current_terms` — иначе условия снялись бы со старого
            # тарифа, и первый же счёт пришёл бы по цене, которую человек уже не
            # покупал. Проба на этом заканчивается совсем: `trial_ends_at`
            # уводится в прошлое, чтобы месячный цикл не пытался выставить ей
            # закрывающий счёт вторым платежом.
            if locked.target_plan_id and subscription.plan_id != locked.target_plan_id:
                _log.info("plan switched by payment", extra={
                    "org": locked.organization_id, "invoice": locked.number,
                    "was": subscription.plan_id, "now": locked.target_plan_id})
                subscription.plan = locked.target_plan
                fields_sub.append("plan")
            if locked.target_plan_id and subscription.trial_ends_at > now:
                subscription.trial_ends_at = now
                fields_sub.append("trial_ends_at")
            subscription.save(update_fields=fields_sub)
            # ПРОДЛЕНИЕ — ЕДИНСТВЕННАЯ ТОЧКА, ГДЕ ПРАВКА ТАРИФА ДОХОДИТ ДО
            # КЛИЕНТА. Внутри той же транзакции, что и новый период: период и
            # условия, по которым он будет посчитан, — один факт.
            adopt_current_terms(subscription)
        organization_id = locked.organization_id
        invoice_pk = locked.pk
        switched_to = locked.target_plan_id

    # ЛИМИТЫ ИСПОЛНЯЕТ ЛИЦЕНЗИОННЫЙ СЕРВЕР, И ЕМУ НАДО СКАЗАТЬ.
    #
    # Тариф записан на КЛЮЧЕ, который он выдал; наша строка решает только счёт.
    # Без этого вызова оплата «Промышленного» меняла бы цифру в кабинете, а
    # контейнеров как было по потолку младшего тарифа, так и осталось бы. Вне
    # транзакции и до `set_status` по тому же правилу, что и всё здесь: сеть не
    # держит транзакцию, а деньги уже записаны.
    if switched_to and LicenseKey.objects.filter(
            organization_id=organization_id, revoked_at__isnull=True).exists():
        try:
            licensing.set_org_plan(organization_id, switched_to)
        except licensing.LicensingError as error:
            _log.error("payment recorded but plan NOT applied on licensing", extra={
                "org": organization_id, "invoice": invoice.number,
                "plan": switched_to, "error": str(error)})
            raise ServiceNotResumed(str(error)) from error

    # ОПЛАТА РАНЬШЕ КЛЮЧА — ТЕПЕРЬ ВОЗМОЖНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ, А НЕ СБОЙ.
    #
    # Пока заплатить можно было только по счёту, ключ существовал всегда: счёт
    # выставлялся тому, кто уже работал. С кнопкой «оплатить сейчас» человек
    # может заплатить в первый же день, ещё не пройдя по ссылке из письма, — и
    # тогда возобновлять на лицензионном сервере НЕЧЕГО: организации он не
    # знает и честно отвечает 404. Раньше это была бы `ServiceNotResumed`,
    # вебхук вернул бы ошибку, ЮKassa начала бы повторять доставку, и каждая
    # попытка падала бы так же — при том что деньги записаны и всё в порядке.
    #
    # Спрашиваем СВОЮ базу, а не ловим текст чужой ошибки: ключей нет — значит
    # и обслуживания нет, и включать нечего. Тариф на будущий ключ возьмётся из
    # подписки в момент выпуска.
    has_keys = LicenseKey.objects.filter(organization_id=organization_id,
                                         revoked_at__isnull=True).exists()
    if not has_keys:
        _log.info("payment recorded; no key yet, nothing to resume", extra={
            "org": organization_id, "invoice": invoice.number})
        with transaction.atomic():
            Invoice.objects.filter(pk=invoice_pk).update(
                service_resumed_at=timezone.now())
        funnel("paid", organization_id, str(invoice.total))
        invoice.refresh_from_db()
        return

    try:
        licensing.set_status(organization_id, "active")
        _log.info("service resumed", extra={"org": organization_id, "invoice": invoice.number})
    except licensing.LicensingError as error:
        _log.error("payment recorded but service NOT resumed", extra={
            "org": organization_id, "invoice": invoice.number, "error": str(error)})
        raise ServiceNotResumed(str(error)) from error

    # НОВЫЙ ПЕРИОД — НОВАЯ ВАТЕРМАРКА — НОВЫЙ АБСОЛЮТНЫЙ ПОТОЛОК. Оплата двигает
    # период, значит и потолок объёма на лиц-сервере надо обновить, иначе клиент
    # остался бы с потолком прошлого периода. Не роняет оплату при отказе.
    push_ceiling(invoice.organization)

    with transaction.atomic():
        Invoice.objects.filter(pk=invoice_pk).update(
            service_resumed_at=timezone.now())
    funnel("paid", organization_id, str(invoice.total))
    invoice.refresh_from_db()


# ЧТО ПРОВАЙДЕР СКАЗАЛ О ПЛАТЕЖЕ, СЛОВАМИ, А НЕ КОДОМ HTTP.
#
# `settle_payment` зовут ДВЕ ДВЕРИ, и у них разные ответы наружу: уведомление
# отвечает кодами (200 принято / 502 переспроси), а вернувшийся с оплаты клиент
# — страницей. Общий разбор поэтому возвращает вердикт, а не статус, и каждая
# дверь переводит его в своё.
PAID = "paid"                    # деньги пришли и записаны
UNRESUMED = "unresumed"          # деньги записаны, обслуживание не поднялось
PENDING = "pending"              # платёж ещё идёт
DECLINED = "declined"            # провайдер закрыл платёж без денег
UNDERPAID = "underpaid"          # денег меньше счёта
UNREADABLE = "unreadable"        # спросить провайдера не удалось
UNKNOWN_PAYMENT = "unknown_payment"  # провайдер такого платежа не знает
UNKNOWN_INVOICE = "unknown_invoice"
NOTHING = "nothing"              # у счёта нет ни одной попытки оплаты

_OWED = (PAID, UNRESUMED)


@dataclass(frozen=True)
class Settlement:
    """Вердикт по одному платежу: что с ним стало и почему."""

    verdict: str
    payment_id: str = ""
    detail: str = ""

    @property
    def paid(self) -> bool:
        return self.verdict in _OWED


def settle_payment(invoice: Invoice | None = None, payment_id: str = "") -> Settlement:
    """Прочитать платёж у провайдера и, если он прошёл, записать оплату.

    ЗАЧЕМ ВТОРАЯ ДВЕРЬ. Уведомление — то, что ДОЛЖНО приходить, и до
    28.09.2026 оно не приходило НИ РАЗУ: у магазина в кабинете ЮKassa не
    настроен URL уведомлений (это настройка чужого кабинета, и её нельзя
    выставить нашим ключом — ручка `/v3/webhooks` требует OAuth и отвечает 401
    на Basic). За это время пять наших платежей из пяти дошли до `succeeded` у
    провайдера и остались неоплаченными у нас: счёт `issued`, подписка
    `pending`, ключ не выпущен, а клиент только что отдал деньги и смотрит на
    «ЖДЁТ ОПЛАТЫ».

    Дверь, зависящая от настройки в чужом кабинете, не может быть единственной.
    Поэтому тем же правилом, что и уведомление — «тело не доверяем, статус
    читаем обратно по authenticated-соединению», — пользуется и возврат клиента
    с оплаты, и часовой обход биллинга. Правило одно, дверей три.

    ИДЕМПОТЕНТНО: `mark_paid` сам перечитывает строку под блокировкой и
    возвращается сразу, если деньги уже записаны и обслуживание поднято.
    """
    payment_id = payment_id or (invoice.payment_ref if invoice is not None else "")
    if not payment_id:
        return Settlement(NOTHING)
    try:
        status, amount, number = payments.fetch_status(payment_id)
    except payments.PaymentNotKnown as error:
        # 404 у провайдера — это ответ, а не авария: такого платежа нет.
        return Settlement(UNKNOWN_PAYMENT, payment_id, str(error))
    except payments.PaymentError as error:
        return Settlement(UNREADABLE, payment_id, str(error))

    if invoice is None:
        invoice = Invoice.objects.filter(number=number).first()
        if invoice is None:
            return Settlement(UNKNOWN_INVOICE, payment_id, number)

    if status != "succeeded":
        # Идущий платёж и закрытый — разные ответы: первого ждут, второго нет.
        going = status in ("pending", "waiting_for_capture")
        return Settlement(PENDING if going else DECLINED, payment_id, status)

    if invoice.state == Invoice.PAID and invoice.service_resumed_at is not None:
        return Settlement(PAID, payment_id)

    # НЕДОПЛАТА НЕ ВОЗОБНОВЛЯЕТ ОБСЛУЖИВАНИЕ. Сравнение точное: с обеих сторон
    # Decimal, а не float, — расхождение в копейку здесь стоило бы клиенту
    # месяца, за который он заплатил меньше.
    if amount < invoice.total:
        return Settlement(UNDERPAID, payment_id, f"{amount} < {invoice.total}")

    try:
        mark_paid(invoice, payment_ref=payment_id)
    except ServiceNotResumed as error:
        # Деньги записаны и не откатятся; не доехало только возобновление, и
        # повторный вызов — единственное, что его дочинит.
        return Settlement(UNRESUMED, payment_id, str(error))
    return Settlement(PAID, payment_id)


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
# РЕШЕНИЕ ВЛАДЕЛЬЦА: порог тарификации = 0 на всех тарифах. Считаем ПРОСТО и ЯВНО —
# «включено N, каждая 1000 сверх N по ставке», с ПЕРВОГО запроса сверх включённого.
# Без «полосы бесплатных запросов» поверх включённого: она путала (клиент видел
# «купил 10k, а биллится с 30k?!») и раздавала объём даром.
#
# Что порог страховал: ОБРЫВ ЦЕПИ ОТЧЁТОВ, не общую неточность. При ЖИВЫХ отчётах
# `acked` точен, ошибка НОЛЬ (измерено на трёх масштабах, docs/billing-integrity.md) —
# и floor=0 биллит ровно, честно. Только если отчёты не доходят, счёт идёт по ВЫДАННОЙ
# ёмкости и может завысить на ширину резерва — редкий край, в нашу пользу, и он
# само-корректируется следующим отчётом (`acked` кумулятивен). Владелец это принял.
# Поле `metered_floor` оставлено настраиваемым: не 0 на тарифе → вернётся полоса.
DEFAULT_METERED_FLOOR = 0


def resolve_offer(organization, code: str = "", applies_to: str = "any", plan=None,
                  amount=None):
    """Лучшее применимое предложение для этой оплаты, или None. Ищет среди АДРЕСНЫХ
    (offer.organization == organization) и ПУБЛИЧНЫХ по промокоду (offer.code == code,
    если код введён). Фильтрует по сроку/лимиту (`is_available`), по типу (`applies_to`:
    'any' подходит всегда) и по тарифу (`target_plan`). Выбирает ВЫГОДНЕЙШЕЕ клиенту:
    при заданной `amount` — по наименьшей итоговой цене (честно для смеси % и ₽), иначе
    по величине скидки. Оператор не думает о порядке. Применение — у вызывающего."""

    who = Q(organization=organization)
    if code:
        who |= Q(code=code, organization__isnull=True)
    candidates = Offer.objects.filter(who).select_related("target_plan", "organization")
    plan_code = getattr(plan, "code", None) or getattr(plan, "pk", None)
    applicable = []
    for offer in candidates:
        if not offer.is_available():
            continue
        if offer.applies_to != Offer.APPLIES_ANY and offer.applies_to != applies_to:
            continue
        if offer.target_plan_id and plan_code and offer.target_plan_id != plan_code:
            continue
        applicable.append(offer)
    if not applicable:
        return None
    if amount is not None:
        from decimal import Decimal
        amount = Decimal(amount)
        return min(applicable, key=lambda o: o.apply_to(amount))
    return max(applicable, key=lambda o: (o.discount_pct, o.discount_amount))


# ГЛОБАЛЬНЫЙ ПОТОЛОК ВЫВОДИТСЯ ИЗ ВКЛЮЧЁННОГО ОБЪЁМА, В ОДНОМ МЕСТЕ.
#
# `overage_cap_requests` — не независимое абсолютное число: оно ОТНОСИТЕЛЬНО
# включённого (докуп до 3× включённого, буфер 10% потолка). Хранить его
# абсолютом и править `included_requests` в конструкторе, не тронув потолок, —
# это молчаливый рассинхрон: подняли включённое выше старого потолка, и клиент,
# пересёкший включённое, попадал СРАЗУ в «stopped» без единого предупреждения.
# Поэтому потолок/буфер выводятся здесь и пере-выводятся везде, где меняется
# включённое (`seed_plans`, конструктор).
CAP_MULTIPLIER = 3
BUFFER_FRACTION = 10          # буфер = потолок // 10 (10%)
UPGRADE_DISCOUNT_PCT = 50     # скидка на первый месяц старшего тарифа при апгрейде
ANNUAL_DISCOUNT_PCT = 15      # годовая предоплата: ≈2 месяца в подарок (сид-дефолт)


def derive_cap_and_buffer(included: int) -> tuple[int, int]:
    """Потолок и буфер из включённого объёма. Возврат (cap, buffer)."""
    cap = max(0, int(included)) * CAP_MULTIPLIER
    return cap, cap // BUFFER_FRACTION


def effective_cap_buffer(subscription: Subscription, plan: Plan) -> tuple[int, int]:
    """Границы зоны С УЧЁТОМ переключателя овереджа — для `classify_zone`.

    Овередж ВКЛ — потолок и буфер живого тарифа (enforcement, как и раньше).
    Овередж ВЫКЛ — потолок равен ВКЛЮЧЁННОМУ из снимка, буфер пуст: пробитие
    включённого сразу означает стоп, зоны `metered`/`buffer` пусты, начисления
    нет. Одна точка правды для цикла, кабинета и потолка на лиц-сервере.
    """
    if subscription.overage_enabled:
        return int(plan.overage_cap_requests or 0), int(plan.buffer_requests or 0)
    included = _int_or_zero(subscription.terms["included_requests"])
    return included, 0


def absolute_ceiling(organization: Organization) -> int:
    """Абсолютный потолок запросов периода для лиц-сервера, или 0 = без потолка.

    То же число, по которому ВИТРИНА сама останавливает клиента (`classify_zone`),
    только в терминах монотонного счётчика сервера: ватермарка последнего
    месячного счёта плюс граница зоны периода. `0` — потолка нет (Enterprise/по
    договору: овередж ВКЛ и `overage_cap_requests == 0`).
    """
    subscription = organization.subscription
    included = _int_or_zero(subscription.terms["included_requests"])
    if not subscription.overage_enabled:
        boundary = included
    else:
        cap = int(subscription.plan.overage_cap_requests or 0)
        if cap <= 0:
            return 0
        # Потолок не ниже включённого — как страховка в `classify_zone`.
        boundary = max(cap, included) + int(subscription.plan.buffer_requests or 0)
    previous = _last_metered_invoice(organization)
    watermark = max(0, previous.requests_billable_at_period_end if previous else 0)
    return watermark + boundary


def push_ceiling(organization: Organization) -> bool:
    """Отправить абсолютный потолок периода на лиц-сервер. Возврат True при успехе.

    Отказ НЕ роняет вызывающего и не поднимается наружу: потолок — это УСКОРЕНИЕ
    стопа (движок упирается в него за минуты), а не единственный механизм —
    часовой стоп цикла остаётся. Поэтому недоступность сервера здесь логируется
    и проглатывается, в отличие от рубильника оплаты, где она обязана всплыть.
    """
    try:
        licensing.set_ceiling(organization.id, absolute_ceiling(organization))
        return True
    except licensing.LicensingError as error:
        _log.warning("не удалось передать потолок объёма на лиц-сервер",
                     extra={"org": organization.id, "error": str(error)})
        return False


MONTHS_IN_YEAR = 12
ANNUAL_PERIOD_DAYS = 365


def _last_metered_invoice(organization: Organization):
    """Последний МЕСЯЧНЫЙ невоидный счёт — носитель ватермарки перерасхода.

    Годовой счёт (`is_annual`) исключён: это предоплата БАЗЫ, к объёму
    отношения не имеет, а его период на год вперёд иначе всегда выигрывал бы
    сортировку по `period_end` и подменял месячную ватермарку своей.
    """
    return (Invoice.objects.filter(organization=organization, is_annual=False)
            .exclude(state=Invoice.VOID)
            .order_by("-period_end", "-id").first())


def period_billable(organization: Organization, reported: dict) -> int:
    """Сколько запросов к начислению стоит ТЕКУЩИЙ период, а не вся жизнь.

    Счётчик сервера накопительный, поэтому за период — разница с ватермаркой
    последнего невоидного МЕСЯЧНОГО счёта. ОДНА арифметика для цикла
    (порог/письма/стоп) и кабинета (зона/цена): два ответа на «сколько за
    период» разошлись бы — полоса показывала бы одно, счёт приходил бы на другое.
    """
    previous = _last_metered_invoice(organization)
    watermark = max(0, previous.requests_billable_at_period_end if previous else 0)
    confirmed = max(0, _int_or_zero(reported.get("capacity_billable")) - watermark)
    # РЕАЛЬНЫЙ РАСХОД ИЗ ОТЧЁТОВ КОНТЕЙНЕРОВ — И ОН ЖЕ ВЕРХНЯЯ ГРАНИЦА ПОКАЗА.
    #
    # Полоса считалась ТОЛЬКО по подтверждённой ёмкости. Подтверждение приходит
    # вместе с покупкой следующего кванта, и пока контейнер работает внутри
    # первого, в кабинете стоит ноль: человек видит «израсходовано 0 из 10 000»
    # при семистах обслуженных запросах и справедливо считает, что учёта нет.
    # Расход при этом УЖЕ на нашей стороне — контейнер отчитывается отдельно и
    # подписанно, `usage.requests`, — и он обновляется в реальном времени.
    #
    # Берём БОЛЬШЕЕ из двух: показать меньше фактического нельзя (это ложь в
    # пользу продавца), а показать меньше подтверждённого — расхождение с счётом.
    # Ватермарка у каждого счётчика своя: у ёмкости и у расхода они разные.
    reported_requests = max(0, _int_or_zero(reported.get("requests"))
                            - max(0, previous.requests_at_period_end if previous else 0))
    return max(confirmed, reported_requests)


def annual_price(organization: Organization, plan) -> dict:
    """Цена годовой предоплаты базы: 12×абонплата минус ЛУЧШАЯ из двух скидок —
    стандартной годовой (`plan.annual_discount_pct`) или адресного/промо
    annual-оффера, если он выгоднее клиенту. НЕ складывает: берёт минимум цены.

    Возврат: gross, discount, total, offer (если победил оффер), label."""
    terms = organization.subscription.terms
    monthly = Decimal(terms["monthly_price"] or 0)
    gross = _round(monthly * MONTHS_IN_YEAR)
    # Базовая годовая скидка тарифа.
    plan_pct = int(plan.annual_discount_pct or 0)
    plan_total = _round(gross * (Decimal(100 - plan_pct) / Decimal(100)))
    plan_label = f"Годовая скидка {plan_pct}%" if plan_pct else "Годовая оплата"
    best_total, offer, label = plan_total, None, plan_label
    # Annual-оффер: перебивает базовую скидку, только если дешевле клиенту.
    annual_offer = resolve_offer(organization, applies_to=Offer.APPLIES_ANNUAL,
                                 plan=plan, amount=gross)
    if annual_offer is not None:
        offer_total = annual_offer.apply_to(gross)
        if offer_total < best_total:
            best_total, offer, label = offer_total, annual_offer, annual_offer.title
    return {"gross": gross, "total": best_total,
            "discount": _round(gross - best_total),
            "offer": offer, "label": label, "monthly": monthly}


def annual_available(organization: Organization, plan) -> bool:
    """Предлагать ли годовую оплату: тариф даёт годовую скидку ИЛИ есть
    доступный адресный/промо annual-оффер. Иначе адресный annual-оффер на
    тарифе с нулевой годовой скидкой был бы инертен — тот же баг «оффер создан,
    но до денег не доходит», что этот эпик и чинит для месячных."""
    if plan.annual_discount_pct:
        return True
    return resolve_offer(organization, applies_to=Offer.APPLIES_ANNUAL,
                         plan=plan) is not None


def build_annual_invoice(organization: Organization) -> Invoice:
    """Счёт на 12 месяцев базы вперёд, со скидкой. Идемпотентно: если уже есть
    невоидный НЕоплаченный годовой счёт — вернуть его, а не плодить второй."""
    existing = (Invoice.objects.filter(organization=organization, is_annual=True)
                .exclude(state__in=(Invoice.VOID, Invoice.PAID))
                .order_by("-id").first())
    if existing is not None:
        return existing
    plan = organization.subscription.plan
    priced = annual_price(organization, plan)
    now = timezone.now()
    period_start = now.date()
    period_end = (now + timedelta(days=ANNUAL_PERIOD_DAYS)).date()
    invoice = Invoice.objects.create(
        organization=organization,
        number=Invoice.next_number(),
        state=Invoice.ISSUED,
        is_annual=True,
        period_start=period_start,
        period_end=period_end,
        plan_amount=priced["gross"],
        discount_amount=priced["discount"],
        discount_offer=priced["offer"],
        metered_requests=0,
        metered_amount=Decimal("0"),
        total=priced["total"],
        issued_at=now,
        due_at=(now + timedelta(days=INVOICE_DUE_DAYS)).date(),
    )
    if priced["offer"] is not None:
        Offer.objects.filter(pk=priced["offer"].pk).update(uses=F("uses") + 1)
    _log.info("annual invoice built", extra={
        "invoice": invoice.number, "org": organization.id,
        "gross": str(priced["gross"]), "total": str(priced["total"])})
    return invoice


def has_ever_paid(organization: Organization) -> bool:
    """Платила ли организация хоть раз. Определяет право на подарочные дни."""
    return Invoice.objects.filter(organization=organization,
                                  state=Invoice.PAID).exists()


def trial_has_been_used(reported: dict) -> bool:
    """Прошёл ли через движок хоть один запрос — «проба начата».

    Счётчик `requests` приходит из `/admin/usage`, а самопроверка в него не
    входит, поэтому ненулевое значение — это реальная работа агента, а не наш
    служебный трафик.
    """
    return _int_or_zero(reported.get("requests")) > 0


def bonus_days_for(organization: Organization, plan: Plan,
                   trial_used: bool) -> int:
    """Сколько дней в подарок даёт оплата ЭТОГО тарифа без пробы.

    Два условия, и оба обязательны. Первое: платёж действительно первый —
    подарок платит за доверие, за решение купить, не глядя, и на втором месяце
    он был бы просто скидкой, которую никто не просил. Второе: проба НЕ
    НАЧАТА — ни одного запроса через движок. Кто уже прогнал свои сценарии,
    получил ровно то, ради чего проба была; ему положена другая половина —
    `post_trial_discount_for`, — и никогда обе сразу.

    Выдавалась ли проба, здесь БОЛЬШЕ НЕ СПРАШИВАЕТСЯ. Условие стояло против
    фарма подарков, но подарок требует ДЕНЕГ, и брать продукт бесплатно им
    нельзя. А главный его получатель теперь — тот, кто выбрал платный тариф на
    лендинге: пробы у него нет по собственному выбору, и именно ему обещан
    месяц за то, что он не стал её брать.
    """
    if has_ever_paid(organization) or trial_used:
        return 0
    return plan.first_payment_bonus_days


def post_trial_discount_for(organization: Organization, plan: Plan,
                            trial_used: bool) -> int:
    """Процент скидки на первый оплаченный месяц тому, кто ПРОШЁЛ пробу.

    Зеркало `bonus_days_for` с теми же двумя условиями наоборот: платёж
    первый, проба начата. Удержание в момент, когда человек всё увидел и
    решает, платить ли; число — с тарифа, который он покупает.
    """
    if has_ever_paid(organization) or not trial_used:
        return 0
    return plan.post_trial_discount_pct


def build_switch_invoice(organization: Organization, plan: Plan) -> Invoice:
    """Счёт на месяц ТАРИФА, выставленный по требованию.

    ЗАЧЕМ ОН ЕСТЬ. `pay_invoice` умеет оплатить только уже существующий счёт, а
    счета выставлял месячный цикл — по окончании пробы или периода. Значит во
    время пробы счёта не существовало, и человек, готовый заплатить сегодня, не
    мог сделать этого ничем, кроме годовой предоплаты: единственная живая кнопка
    на весь кабинет. Этот счёт закрывает дыру и он же служит сменой тарифа для
    того, кто уже платит, — оба случая это «переведи меня на тариф X с оплатой».

    ИДЕМПОТЕНТНО, И ПЕРЕДУМАТЬ РАЗРЕШЕНО. Повторный вызов на тот же тариф отдаёт
    тот же счёт, а не плодит второй: иначе две вкладки дали бы два платежа.
    Выбор другого тарифа АННУЛИРУЕТ прежний неоплаченный счёт — оставить его
    живым значило бы, что человек, передумавший в пользу старшего тарифа, может
    случайно оплатить младший и получить не то, что выбрал.
    """
    pending = (Invoice.objects.filter(organization=organization,
                                      target_plan__isnull=False)
               .exclude(state__in=(Invoice.VOID, Invoice.PAID))
               .order_by("-id").first())
    if pending is not None:
        if pending.target_plan_id == plan.code:
            return pending
        pending.state = Invoice.VOID
        pending.save(update_fields=["state"])
        _log.info("switch invoice voided in favour of another plan", extra={
            "invoice": pending.number, "org": organization.id,
            "was": pending.target_plan_id, "now": plan.code})

    now = timezone.now()
    # Подарочные дни просит немедленная оплата НЕ НАЧАТОЙ пробы; счётчик берём
    # у licensing, а его недоступность не должна лишать платящего подарка —
    # тогда падаем в прежнее поведение (проба считается неначатой).
    try:
        reported = licensing.usage(organization.id).get("usage", {})
    except licensing.LicensingError:
        reported = {}
    if not isinstance(reported, dict):
        reported = {}
    trial_used = trial_has_been_used(reported)
    bonus = bonus_days_for(organization, plan, trial_used)
    # СКИДКА ЗА ПРОЙДЕННУЮ ПРОБУ — ЗДЕСЬ, ПОТОМУ ЧТО ЭТОТ СЧЁТ И ЕСТЬ ПЕРВЫЙ
    # ПЛАТЁЖ: месячный цикл после пробы счёта не выставляет вовсе (проба
    # останавливает обслуживание), значит первый месяц покупается только этой
    # кнопкой. Адресное предложение на первый месяц (`Offer`) с ней не
    # складывается — берётся лучшее для клиента, как у годовой оплаты.
    discount = Decimal("0")
    offer = None
    if not has_ever_paid(organization):
        discount_pct = post_trial_discount_for(organization, plan, trial_used)
        discount = _round(plan.monthly_price * Decimal(discount_pct) / Decimal(100))
        offer = resolve_offer(organization, applies_to=Offer.APPLIES_FIRST_MONTH,
                              plan=plan, amount=plan.monthly_price)
        offer_discount = (_round(plan.monthly_price - offer.apply_to(plan.monthly_price))
                          if offer is not None else Decimal("0"))
        if offer_discount > discount:
            discount = offer_discount
        else:
            offer = None
    invoice = Invoice.objects.create(
        organization=organization,
        number=Invoice.next_number(),
        state=Invoice.ISSUED,
        target_plan=plan,
        bonus_days=bonus,
        period_start=now.date(),
        period_end=(now + timedelta(days=30 + bonus)).date(),
        plan_amount=plan.monthly_price,
        metered_requests=0,
        metered_amount=Decimal("0"),
        discount_amount=discount,
        discount_offer=offer,
        total=_round(plan.monthly_price - discount),
        issued_at=now,
        due_at=(now + timedelta(days=INVOICE_DUE_DAYS)).date(),
    )
    if offer is not None:
        Offer.objects.filter(pk=offer.pk).update(uses=F("uses") + 1)
    _log.info("switch invoice built", extra={
        "invoice": invoice.number, "org": organization.id, "plan": plan.code,
        "total": str(invoice.total), "bonus_days": bonus,
        "discount": str(discount)})
    return invoice


def settle_zero_invoice(invoice: Invoice) -> None:
    """Погасить НУЛЕВОЙ месячный счёт без похода в платёжку и лицензионный
    сервер: клиент уже активен (база оплачена вперёд или тариф нулевой), платить
    нечего, но период обязан сдвинуться — иначе следующий проход упрётся в
    идемпотентность и месячный период встанет навсегда."""
    now = timezone.now()
    with transaction.atomic():
        locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if locked.state == Invoice.PAID:
            return
        locked.state = Invoice.PAID
        locked.paid_at = now
        locked.service_resumed_at = now
        locked.save(update_fields=["state", "paid_at", "service_resumed_at"])
        subscription = locked.organization.subscription
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)
        subscription.save(update_fields=["current_period_start",
                                         "current_period_end"])
        # ПРОДЛЕНИЕ ДОВОДИТ ПРАВКУ ТАРИФА ДО КЛИЕНТА — и нулевой счёт это тоже
        # продление. Без этого клиент на годовой предоплате (или на нулевом
        # тарифе) НИКОГДА не получал бы новую цену/включённое: adopt был только
        # в `mark_paid`, а сюда путь шёл мимо него.
        adopt_current_terms(subscription)
    # Нулевой счёт — тоже продление: период сдвинулся, значит и абсолютный потолок
    # на лиц-сервере пере-выставляется от новой ватермарки. Вне транзакции (сеть).
    push_ceiling(invoice.organization)
    _log.info("zero invoice settled", extra={
        "invoice": invoice.number, "org": invoice.organization_id})


def period_pricing(organization: Organization, plan, reported: dict) -> dict:
    """Всё, что кабинет показывает про объём и цену за период, В ОДНОМ месте.

    Зона (включено/докуп/буфер/стоп), % до потолка, ставка, НАЧИСЛЕНО СВЕРХ на
    сейчас, и — в буфере — адресный оффер апгрейда. Чистая функция от отчёта и
    условий подписки (снимок), чтобы цифры кабинета совпадали со счётом.
    """
    used = period_billable(organization, reported)
    terms = organization.subscription.terms
    rate = terms["metered_per_1k"] or Decimal("0")
    included = _int_or_zero(terms["included_requests"])
    floor = _int_or_zero(terms["metered_floor"]) if terms.get("metered_floor") is not None else DEFAULT_METERED_FLOOR
    # Зона — на ВКЛЮЧЁННОМ ИЗ СНИМКА (тот же, что биллит счёт), потолок/буфер —
    # с живого тарифа (это enforcement, меняется сразу для всех, как RPM/лимит
    # инстансов). Так число «включено», зона и начисление в кабинете сходятся.
    # Границы — С УЧЁТОМ ПЕРЕКЛЮЧАТЕЛЯ: при выключенном овередже потолок = included,
    # буфер пуст, начисления нет; пробитие включённого сразу даёт `stopped`.
    subscription = organization.subscription
    cap, buffer = effective_cap_buffer(subscription, plan)
    zone = classify_zone(used, included, cap, buffer)
    if subscription.overage_enabled:
        over = max(0, used - included)
        billed_over = max(0, over - floor) if rate > 0 else 0
    else:
        billed_over = 0
    overage_amount = _round(Decimal(billed_over) / Decimal(1000) * Decimal(rate))
    # Оффер апгрейда показываем только когда он к месту — в буфере за потолком.
    upgrade_offer = None
    if zone["in_buffer"]:
        upgrade_offer = resolve_offer(organization, applies_to=Offer.APPLIES_ANY,
                                      plan=plan)
    return {
        "zone": zone["zone"],
        "used": used,
        "included": included,
        "cap": zone["cap"],
        "buffer_end": zone["buffer_end"],
        "pct_of_cap": zone["pct_of_cap"],
        "rate": rate,
        "floor": floor,
        "overage_requests": billed_over,
        "overage_amount": overage_amount,
        "monthly_price": terms["monthly_price"],
        "upgrade_discount_pct": plan.upgrade_first_month_discount_pct,
        "upgrade_offer": upgrade_offer,
    }


def classify_zone(used: int, included: int, cap: int, buffer: int) -> dict:
    """Which VOLUME ZONE the org is in — for the cabinet display AND enforcement.
    Pure function of the period's request count and explicit boundaries. Four zones:

      included  0..included_requests            — covered by the subscription
      metered   included..overage_cap           — top-up (overage) at the tier rate
      buffer    overage_cap..overage_cap+buffer  — still served, cabinet offers the
                                                   upgrade (favourable first month)
      stopped   beyond the buffer                — hard stop, like an unpaid licence

    `cap == 0` means NO ceiling (Enterprise/по договору): only included vs metered.

    ГРАНИЦЫ ПЕРЕДАЮТСЯ ЯВНО, А НЕ ЧИТАЮТСЯ С ЖИВОГО ТАРИФА. `included` обязан
    прийти ИЗ СНИМКА подписки — тогда зона (и стоп-решение) считается на том же
    числе, что и счёт (`build_invoice` по снимку). Раньше функция брала
    `plan.included_requests` (живой), и после правки тарифа зона в кабинете
    расходилась с включённым, показанным рядом, и с тем, за что реально биллят."""
    included = max(0, int(included))
    cap = int(cap or 0)
    buffer = int(buffer or 0)
    used = max(0, int(used))
    # ПОТОЛОК НИКОГДА НЕ НИЖЕ ВКЛЮЧЁННОГО. Иначе пересечение включённого падает
    # мимо зоны «metered» прямо в «stopped» — мгновенная остановка без докупа.
    # Конструктор пере-выводит потолок при правке включённого, но эта страховка
    # стоит ноль и закрывает ещё и старые/руками правленые строки.
    if 0 < cap < included:
        cap = included
    if cap <= 0:
        zone = "included" if used <= included else "metered"
        return {"zone": zone, "used": used, "included": included, "cap": 0,
                "buffer_end": 0, "capped": False, "in_buffer": False,
                "pct_of_cap": 0}
    buffer_end = cap + buffer
    if used <= included:
        zone = "included"
    elif used <= cap:
        zone = "metered"
    elif used <= buffer_end:
        zone = "buffer"
    else:
        zone = "stopped"
    return {"zone": zone, "used": used, "included": included, "cap": cap,
            "buffer_end": buffer_end, "capped": zone == "stopped",
            "in_buffer": zone == "buffer",
            "pct_of_cap": min(100, round(used / cap * 100)) if cap else 0}

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
    # period used is the difference from the previous MONTHLY invoice's
    # watermark (годовой счёт исключён — это база, не объём).
    previous = _last_metered_invoice(organization)
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
    #
    # БАЗА = 0, ПОКА ОПЛАЧЕНА ВПЕРЁД ГОДОВЫМ ПЛАТЕЖОМ (вариант A): месячный счёт
    # в годовом окне несёт только строку перерасхода. Часто перерасхода нет —
    # тогда счёт нулевой и гасится сам (`settle_zero_invoice` в цикле).
    base_prepaid = (subscription.base_paid_through is not None
                    and timezone.now() < subscription.base_paid_through)
    subscription_amount = Decimal("0") if base_prepaid else terms["monthly_price"]
    # ОДНА АРИФМЕТИКА С ЗОНОЙ И С КАБИНЕТОМ. `period_billable` берёт БОЛЬШЕЕ из
    # двух подписанных счётчиков — подтверждённую ёмкость и аудит запросов, —
    # каждый со своей ватермаркой. Счёт читал только ёмкость, и у клиента, чей
    # движок подтверждает ноль (`acked = 0`: лиза без блока `capacity`), счёт
    # выходил 0 ₽ при растущем `requests`. Комментарий выше объясняет, почему
    # счёт строится на ёмкости; он остаётся верным для движка, который ёмкость
    # покупает, и перестаёт быть верным для того, кто её не покупает вовсе —
    # там единственное подписанное свидетельство расхода и есть `requests`.
    metered_requests = period_billable(organization, reported)
    # Порог применяется к ПРЕВЫШЕНИЮ, не к объёму: включённое клиент уже
    # оплатил абонплатой, и мерить надо ровно ту часть, за которую выставляется
    # отдельная строка.
    over = max(0, metered_requests - _int_or_zero(terms["included_requests"]))
    # Respect an EXPLICIT 0 (the policy: no free band, bill from the first over-request).
    # `or` would rewrite 0 back to the default — 0 is a valid floor, not "unset".
    floor = _int_or_zero(terms.get("metered_floor")) if terms.get("metered_floor") is not None else DEFAULT_METERED_FLOOR
    # ПЕРЕРАСХОД НАЧИСЛЯЕТСЯ, ТОЛЬКО КОГДА КЛИЕНТ ЕГО ВКЛЮЧИЛ. Флаг читается на
    # момент выставления (задним числом уже начисленный период не трогаем): при
    # выключенном овередже пробитие включённого — это остановка, а не строка в
    # счёте, поэтому здесь начисление ровно ноль.
    #
    # Bill only the part ABOVE the floor, never the floor itself. The floor is the
    # measurement-noise band — a fixed count of requests (the quantum granularity)
    # we cannot bill accurately — so it stays ALWAYS free, and the charge ramps from
    # zero at the threshold instead of jumping to the whole excess. The old
    # `billed_over = over` created a CLIFF: crossing the floor by one request billed
    # the entire excess at once (e.g. Старт 29 999→30 000 req = 0→+1 580 ₽), a
    # billing shock and a dispute magnet.
    if subscription.overage_enabled and terms["metered_per_1k"] > 0:
        billed_over = max(0, over - floor)
    else:
        billed_over = 0
    metered_amount = _round(Decimal(billed_over) / Decimal(1000)
                            * terms["metered_per_1k"])

    # СПЕЦ-ПРЕДЛОЖЕНИЕ ПРИМЕНЯЕТСЯ ЗДЕСЬ — иначе Offer можно создать в админке,
    # но он НИКОГДА не доходит до денег (инертен). Только АДРЕСНЫЕ (на эту org):
    # промокод вводится клиентом при оплате, а не сервером при выставлении.
    # Тип 'first_month' действует лишь на ПЕРВОМ счёте клиента; 'any' — всегда.
    # Скидка бьёт по абонплате (повторяющийся платёж), не по объёму. Лучший для
    # клиента выбирает `resolve_offer` по итоговой цене.
    # ПЕРВЫЙ СЧЁТ — ПО ЛЮБОМУ невоидному счёту, ВКЛЮЧАЯ годовой и нулевой
    # погашенный. `previous` (ватермарка) исключает годовой, поэтому по нему
    # `is_first` был бы True у клиента, у которого ЕСТЬ годовой счёт, — и скидку
    # «первый месяц» он получил бы на первом ненулевом месяце ПОСЛЕ годового
    # окна, спустя год после регистрации. Здесь вопрос другой: выставлялся ли
    # клиент вообще хоть раз.
    is_first = not Invoice.objects.filter(organization=organization).exclude(
        state=Invoice.VOID).exists()
    applies = Offer.APPLIES_FIRST_MONTH if is_first else Offer.APPLIES_ANY
    offer = resolve_offer(organization, applies_to=applies, plan=plan,
                          amount=subscription_amount)
    discount = Decimal("0")
    if offer is not None:
        discount = _round(Decimal(subscription_amount) - offer.apply_to(subscription_amount))
    total = _round(subscription_amount - discount + metered_amount)

    invoice = Invoice.objects.create(
        organization=organization,
        number=Invoice.next_number(),
        state=Invoice.DRAFT,
        period_start=period_start,
        period_end=period_end,
        plan_amount=_round(subscription_amount),
        discount_amount=discount,
        discount_offer=offer,
        values_in_period=used_this_period,
        metered_requests=billed_over,
        metered_amount=metered_amount,
        total=total,
        due_at=(timezone.now() + timedelta(days=INVOICE_DUE_DAYS)).date(),
        requests_billable_in_period=metered_requests,
        requests_billable_at_period_end=max(billable_watermark, billable),
        values_at_period_end=max(watermark, values),
        requests_at_period_end=requests,
    )
    # СЧЁТЧИК ИСПОЛЬЗОВАНИЙ — ТОЛЬКО КОГДА СКИДКА РЕАЛЬНО ПРИМЕНИЛАСЬ (discount
    # > 0), после создания счёта и атомарно (F). Иначе в годовом окне, где база
    # = 0, оффер резолвился каждый месяц со скидкой 0 и СЖИГАЛ `max_uses` даром —
    # лимитный оффер исчерпывался до того, как хоть раз дал реальную скидку.
    if offer is not None and discount > 0:
        Offer.objects.filter(pk=offer.pk).update(uses=F("uses") + 1)
    # КАЖДЫЙ СЧЁТ — СТРОКА С РАЗЛОЖЕНИЕМ. Спор «почему столько» начинается с
    # этой строки, и без неё ответ собирается из четырёх таблиц вручную.
    _log.info("invoice built", extra={
        "invoice": invoice.number, "org": organization.id,
        "period": f"{period_start}..{period_end}",
        "plan_amount": str(invoice.plan_amount),
        "metered_requests": billed_over, "metered_amount": str(metered_amount),
        "total": str(invoice.total)})
    return invoice
