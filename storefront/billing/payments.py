"""ЮKassa: cards, СБП and the invoice link a legal entity pays against.

WHY NOT AN ABSTRACTION OVER PAYMENT PROVIDERS. Stripe does not operate in this
market, so a gateway interface would be an interface over a set of one — and the
part that actually varies between Russian providers is the fiscal receipt, which
no abstraction hides. If a second provider is ever added, the interface can be
extracted then, from two real implementations rather than from one imagined one.

THE NOTIFICATION IS NOT TRUSTED. ЮKassa POSTs a payment object to us, and that
endpoint is on the public internet: anyone can post the same shape. So the
notification is treated as a HINT — it carries an id, and the status is read back
from the ЮKassa API over an authenticated connection. Source-IP allowlisting is
offered by the provider and is not used as the primary control, because it fails
open the day they add a range.
"""

import logging
from decimal import Decimal

from django.conf import settings

_log = logging.getLogger("billing.payments")


class PaymentError(RuntimeError):
    """The provider refused or could not be reached. Raised, never swallowed:
    the customer is watching a page that says their service is about to
    resume."""


class PaymentNotKnown(PaymentError):
    """Провайдер не знает такого платежа — ответ 404.

    ЭТО ОТВЕТ, А НЕ АВАРИЯ, И РАЗНИЦА НЕСУЩАЯ. Уведомление приходит на
    публичный адрес, и ЮKassa шлёт на него проверочные и чужие события; 502
    «не смогли выяснить» на платеже, которого нет, — это ложь в сторону
    «переспроси», а кабинет ЮKassa считает такой ответ поломкой адреса и
    настройку не сохраняет. Отдельный класс здесь существует ровно затем, чтобы
    вебхук отвечал 200 на «такого платежа нет» и 502 — на «не дозвонились».
    """


def _configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


def is_available() -> bool:
    """Whether card payment can be offered at all.

    The button is hidden rather than shown-and-broken when no credentials are
    set: an invoice can always be paid by transfer, so a dead card button would
    be the only broken thing on a page that otherwise works.

    И ГАСИТСЯ ЯВНЫМ РУБИЛЬНИКОМ, пока эквайринг не одобрен: даже с настроенными
    ключами карта не предлагается, если `PSEUDEX_ACQUIRING_ENABLED` не выставлен
    в 1. Так прод не показывает карту до одобрения, ничего не ломая — счёт по
    реквизитам остаётся.
    """
    return _configured() and settings.ACQUIRING_ENABLED


def _client():
    """Imported and configured lazily.

    The SDK configures itself through module-level globals, so importing it at
    module scope would apply whatever credentials happened to be in the
    environment at import time — including none, during a management command
    that has no business touching payments.
    """
    if not _configured():
        raise PaymentError(
            "ЮKassa is not configured: set PSEUDEX_YOOKASSA_SHOP_ID and "
            "PSEUDEX_YOOKASSA_SECRET_KEY"
        )
    from yookassa import Configuration, Payment  # noqa: PLC0415 (lazy on purpose)

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return Payment


def _receipt(invoice, email: str) -> dict[str, object]:
    """The фискальный чек that rides with EVERY card payment.

    It used to ride only with an individual's, on the strength of 54-ФЗ ст. 2
    п. 9: cashless settlements between organisations and/or ИП need no ККТ. That
    exemption is real and it is the wrong test here, for two reasons that were
    both measured rather than argued:

    * The exemption is about WHO PAYS, and a card payment is made by whoever
      holds the card. A company's accountant paying with a personal card is a
      settlement with an individual, receipt obligatory, and nothing in the
      provider's answer tells the two cards apart. The payer kind we store is
      the company's — it says nothing about the card.
    * ЮKassa's own receipt scheme sends the receipt data in the payment request
      «при проведении каждого платежа». A payment sent without it under that
      scheme is not a payment without a receipt, it is a payment the provider
      may refuse — and a refused first payment is how a paying customer leaves.

    The paper счёт path never comes here, so an organisation that pays by
    transfer still gets no receipt — that is where п. 9 actually applies.

    `vat_code: 1` is "без НДС", which is what an ИП on УСН charges. A company on
    ОСНО would need a different code, and guessing it wrong misstates tax on a
    document the buyer files.
    """
    return {
        "customer": {"email": email},
        "items": [{
            "description": f"Подписка pseudex, {invoice.period_start:%d.%m.%Y}"
                           f"—{invoice.period_end:%d.%m.%Y}"[:128],
            "quantity": "1.00",
            "amount": {"value": f"{invoice.total:.2f}", "currency": "RUB"},
            "vat_code": 1,
            "payment_mode": "full_payment",
            "payment_subject": "service",
        }],
    }


def confirmation_url(payment) -> str:
    """Ссылка, на которую отправляют клиента. Пустая строка — если её нет.

    У ЗАВЕРШЁННОГО И У ОТМЕНЁННОГО ПЛАТЕЖА ПОДТВЕРЖДЕНИЯ НЕТ ВООБЩЕ:
    `payment.confirmation` у них `None`, а не объект с пустым `url`. Код,
    читавший `payment.confirmation.confirmation_url` без проверки, падал на
    AttributeError — пятисоткой на кнопке «оплатить картой», ровно тогда, когда
    этой кнопкой платить уже нечего. Проверено на живом магазине 28.09.2026:
    четыре из пяти наших платежей отменены провайдером по истечении страницы
    (`expired_on_confirmation`), и у каждого `confirmation is None`.
    """
    confirmation = getattr(payment, "confirmation", None)
    return getattr(confirmation, "confirmation_url", "") or ""


# СКОЛЬКО СТУПЕНЕЙ ЦЕПОЧКИ ПРОБУЕМ ЗА ОДИН КЛИК. Больше четырёх не бывает
# даже у счёта, который клиент пытается оплатить месяцами: каждая ступень — это
# уже созданный платёж, чей идентификатор уточняет ключ идемпотентности.
_MAX_PAYMENT_ATTEMPTS = 4


def create_payment(invoice, return_url: str, email: str) -> tuple[str, str]:
    """Start a payment for an invoice. Returns (payment_id, confirmation_url).

    The idempotence key is the INVOICE NUMBER, not a fresh uuid. A customer who
    double-clicks, or a retry after a timeout we never saw the answer to, must
    not produce two payments for one invoice — and the provider can only prevent
    that if we give it the same key both times.

    НО КЛЮЧ НЕ МОЖЕТ БЫТЬ ОДНИМ И ТЕМ ЖЕ НАВСЕГДА, И ЭТО ПРОДОЛЖАЕТ ПРАВИЛО
    ВЫШЕ, А НЕ ОТМЕНЯЕТ ЕГО. У провайдера ключ разрешается в результат ПЕРВОГО
    запроса, и «не создавать второй платёж» превращается в «вернуть мёртвый»,
    как только первая попытка истекла: клиент нажимает кнопку, получает
    отменённый платёж, и ссылки на оплату в нём нет ни у нас, ни у него. Кнопка
    после этого не работает НИКАК, сколько по ней ни жми.
    """
    Payment = _client()
    body: dict[str, object] = {
        "amount": {"value": f"{invoice.total:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": f"pseudex {invoice.number}, "
                       f"{invoice.period_start:%d.%m.%Y}—{invoice.period_end:%d.%m.%Y}",
        # Read back on notification to find the invoice again. Only our own
        # identifiers: this object goes to a third party, so it carries an
        # invoice number and an org id and nothing that describes a person.
        "metadata": {"invoice": invoice.number, "org": invoice.organization_id},
    }
    body["receipt"] = _receipt(invoice, email)

    # ЦЕПОЧКА КЛЮЧЕЙ, А НЕ ОДИН КЛЮЧ НАВСЕГДА. Первая ступень — прежний ключ по
    # номеру счёта: он и защищает от двойного платежа. Если провайдер вернул по
    # нему запись, которой больше нельзя заплатить, следующая ступень строится
    # на ЕЁ идентификаторе — `pseudex-<номер>-<id прошлого платежа>`. Цепочка
    # детерминирована: тот же счёт в том же состоянии даёт тот же ключ, поэтому
    # второе нажатие повторяет путь первого и второго платежа не чеканит.
    key = f"pseudex-{invoice.number}"
    seen: set[str] = set()
    for _ in range(_MAX_PAYMENT_ATTEMPTS):
        try:
            payment = Payment.create(body, key)
        except Exception as error:  # the SDK raises provider-specific types
            raise PaymentError(
                f"ЮKassa refused the payment for {invoice.number}: {error}") from error
        url = confirmation_url(payment)
        if url:
            return payment.id, url
        # Ссылки нет. Завершённый платёж — деньги уже взяты, просить их второй
        # раз нельзя ничем; идущий — ссылки не дал сам провайдер, и выдумать её
        # нечем. Обе двери закрыты честной ошибкой, а не новой попыткой списать.
        status = str(getattr(payment, "status", ""))
        if status in ("pending", "waiting_for_capture", "succeeded"):
            raise PaymentError(
                f"payment {payment.id} for {invoice.number} is {status} and the "
                f"provider returned no confirmation url")
        payment_id = str(getattr(payment, "id", ""))
        if not payment_id or payment_id in seen:
            break
        seen.add(payment_id)
        key = f"pseudex-{invoice.number}-{payment_id}"
    raise PaymentError(
        f"ЮKassa returned no payable page for {invoice.number} after "
        f"{_MAX_PAYMENT_ATTEMPTS} attempts")


def fetch_status(payment_id: str) -> tuple[str, Decimal, str]:
    """Read a payment back from the provider. (status, amount, invoice_number).

    This is the ONLY thing that decides whether an invoice is paid. The webhook
    body is caller-controlled — this call is authenticated and goes to ЮKassa
    directly, so a forged notification about someone else's invoice resolves to
    whatever ЮKassa actually says, which is "no such payment".
    """
    Payment = _client()
    # Импорт рядом с вызовом, как и `_client()`: SDK настраивает себя
    # module-level глобалами, и тянуть его в команду, которой платить нечем,
    # незачем.
    from yookassa.domain.exceptions.not_found_error import NotFoundError
    try:
        payment = Payment.find_one(payment_id)
    except NotFoundError as error:
        raise PaymentNotKnown(f"provider has no payment {payment_id}") from error
    except Exception as error:
        raise PaymentError(f"could not read payment {payment_id}: {error}") from error
    return (
        payment.status,
        Decimal(str(payment.amount.value)),
        str((payment.metadata or {}).get("invoice", "")),
    )
