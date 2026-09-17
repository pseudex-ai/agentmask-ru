"""Accounts and organisations.

THE ONE RULE THIS MODULE EXISTS TO KEEP: nothing here may ever hold personal
data belonging to a CUSTOMER'S customers. The people in this table are the
buyers — a name and a work email on a contract — and that is the whole of what
the storefront is allowed to know. The moment a field here could hold a value
that came out of someone's traffic, we stop being outside the perimeter and
become an operator under 152-ФЗ, which is the exact thing this product sells.

The organisation id is the SAME `org_id` the licensing server issues keys
against. One identifier across both sides means "this key belongs to that
invoice" is a lookup rather than a reconciliation.
"""

import secrets

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


def _org_id() -> str:
    """A short, opaque organisation id.

    Not the company name and not a sequence: the id travels to the licensing
    server, lands in the counters a customer can read, and appears in their own
    container's logs. A sequence would tell every customer how many customers we
    have, and a name would put a company's identity into a field that is copied
    around far more freely than the account record.
    """
    return "org_" + secrets.token_hex(6)


class UserManager(BaseUserManager):
    """Email is the identifier. There are no usernames, because the sign-up form
    asks for one thing and inventing a second identifier would mean asking for
    two."""

    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra) -> "User":
        if not email:
            raise ValueError("an email address is required")
        user = self.model(email=self.normalize_email(email), **extra)
        # `set_password(None)` produces an unusable password hash, which is
        # exactly right for an account that signs in by email link only.
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra) -> "User":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email: str, password: str, **extra) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("a superuser must have is_staff and is_superuser")
        return self._create(email, password, **extra)


class User(AbstractUser):
    username = None
    first_name = None
    last_name = None
    email = models.EmailField("email", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email


class Organization(models.Model):
    """The billing entity, and the `org_id` the customer's container reports as.

    `legal_name` / `inn` / `kpp` are OPTIONAL and stay empty until an invoice is
    actually requested. Asking a company for its ИНН before it has decided to
    buy is the single most common way a "15 minutes to the first masked request"
    promise turns into fifteen minutes of a form.
    """

    id = models.CharField(primary_key=True, max_length=32, default=_org_id, editable=False)
    display_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(default=timezone.now)

    # ФАКТ СОГЛАСИЯ, А НЕ ГАЛОЧКА НА ФОРМЕ. Галочка живёт в браузере и исчезает
    # вместе с ним; ст. 9 152-ФЗ требует, чтобы оператор МОГ ДОКАЗАТЬ получение
    # согласия, а доказать можно только записью. Храним момент и РЕДАКЦИЮ
    # текста: согласие даётся на конкретную редакцию, и если текст изменился,
    # старая запись покрывает старый текст, а не новый.
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_revision = models.CharField(max_length=32, blank=True)

    # ПЕРВОЕ КАСАНИЕ, СНЯТОЕ ОДИН РАЗ И НАВСЕГДА. Без этих полей вопрос
    # «какая кампания привела ПЛАТЯЩЕГО клиента» не имеет ответа в принципе:
    # метки живут на визите, визит опознаётся СУТОЧНЫМ отпечатком, и назавтра
    # связь исчезает вместе с солью. Деньги же приходят через недели.
    #
    # ПОЧЕМУ НЕ КУКА И НЕ СЕССИЯ. Оба варианта работают и оба ломают обещание,
    # данное прямо на лендинге: «куки не ставим». Django заводит сессию только
    # для входа, а посетитель лендинга не вошёл, — то есть куку пришлось бы
    # создать специально ради аналитики. Вместо этого регистрация считает ТОТ
    # ЖЕ отпечаток и берёт самый ранний визит этого человека за сутки: путь от
    # лендинга до ключа занимает минуты, и внутри суток связь уже существует.
    # Ограничение названо честно — человек, вернувшийся через неделю по прямой
    # ссылке, припишется к «прямому заходу», и это цена отказа от куки.
    source_utm_source = models.CharField(max_length=60, blank=True)
    source_utm_medium = models.CharField(max_length=60, blank=True)
    source_utm_campaign = models.CharField(max_length=60, blank=True)
    source_referrer = models.CharField(max_length=120, blank=True)
    source_landing = models.CharField(max_length=200, blank=True)
    # ИДЕНТИФИКАТОР КЛИКА ПО ОБЪЯВЛЕНИЮ ДИРЕКТА — единственное, по чему
    # офлайн-конверсия привязывается к визиту без куки. Хранится НЕ ради
    # отчёта (там хватает меток), а потому что без него рассказать Метрике о
    # регистрации и оплате невозможно: страницы, где эти события случаются,
    # счётчика не несут и не могут — на них лежит ключ клиента.
    source_yclid = models.CharField(max_length=64, blank=True)

    # ПО ЧЕМУ УЗНАЁТСЯ ПОВТОРНАЯ РЕГИСТРАЦИЯ.
    #
    # Проба выдавалась каждой новой почте без единой проверки, поэтому её можно
    # было брать бесконечно: завёл ящик — получил ещё две недели. Отпечатка
    # машины у нас нет и быть не может (контейнер крутится у клиента, а
    # `PSEUDEX_INSTANCE_ID` заново случаен при каждом старте), поэтому сверяем
    # то, что видно нам: адрес, с которого пришли, и домен почты.
    #
    # IP НЕ ХРАНИТСЯ — только соль плюс хеш, как и в аналитике: сам адрес это
    # персональные данные, а для ответа «это уже было» достаточно совпадения.
    # Соль постоянная (в отличие от суточной в аналитике): сравнивать надо через
    # месяцы, а не внутри дня.
    signup_ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    # Домен почты. Бесплатные ящики по домену НЕ сравниваются — иначе первый
    # зарегистрировавшийся с gmail отрезал бы от пробы всех остальных.
    signup_email_domain = models.CharField(max_length=100, blank=True, db_index=True)
    # Дали ли бесплатные дни. Ложь — повтор: аккаунт есть и работает, но пробы
    # у него нет, платить надо сразу. Снимается одной кнопкой в админке, потому
    # что один офис за NAT это один IP, и живой второй клиент оттуда возможен.
    trial_granted = models.BooleanField(default=True)

    # WHO the customer is. It decides three things and none of them is the
    # fiscal receipt any more (every card payment carries one — see
    # `billing.payments._receipt`): whether a счёт and an акт can be issued at
    # all (an individual has no реквизиты to print), whether the party is a
    # consumer under ЗоЗПП (an individual is — ст. 32 gives them a pro-rata
    # refund the offer must honour), and what the closing document says.
    # The customer sets it in the cabinet; nobody else can know it.
    KIND_COMPANY = "company"
    KIND_ENTREPRENEUR = "entrepreneur"
    KIND_PERSON = "person"
    KINDS = [
        (KIND_COMPANY, "юридическое лицо"),
        (KIND_ENTREPRENEUR, "ИП"),
        (KIND_PERSON, "физическое лицо"),
    ]
    kind = models.CharField(max_length=16, choices=KINDS, default=KIND_COMPANY)

    legal_name = models.CharField(max_length=300, blank=True)
    inn = models.CharField("ИНН", max_length=12, blank=True)
    kpp = models.CharField("КПП", max_length=9, blank=True)
    legal_address = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.id})"

    @property
    def is_billable(self) -> bool:
        """Whether a счёт can be issued at all. Checked when the customer asks
        for one, not at sign-up.

        An individual needs no requisites — there is nothing to put on a счёт
        for them, because they do not pay by one.
        """
        if self.kind == self.KIND_PERSON:
            return True
        return bool(self.legal_name and self.inn)

    @property
    def pays_by_invoice(self) -> bool:
        """Companies and ИП pay by transfer against a счёт: no commission, no
        acquiring contract, and no ККТ under 54-ФЗ ст. 2 п. 9.

        Individuals cannot — a person has no расчётный счёт to send a payment
        order from — so for them the card is not a convenience but the only
        route, and it brings the fiscal receipt with it.
        """
        return self.kind in (self.KIND_COMPANY, self.KIND_ENTREPRENEUR)


class Membership(models.Model):
    """Who may act for an organisation.

    A table rather than a foreign key on the user, because the second person from
    the same company arriving is the normal case, and discovering that the model
    is one-user-per-org at that point means a migration under time pressure.
    """

    ROLE_OWNER = "owner"
    ROLE_MEMBER = "member"
    ROLES = [(ROLE_OWNER, "владелец"), (ROLE_MEMBER, "участник")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name="memberships")
    role = models.CharField(max_length=16, choices=ROLES, default=ROLE_OWNER)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "organization")]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.organization_id} ({self.role})"
