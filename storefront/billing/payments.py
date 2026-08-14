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


def _configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


def _client():
    """Imported and configured lazily.

    The SDK configures itself through module-level globals, so importing it at
    module scope would apply whatever credentials happened to be in the
    environment at import time — including none, during a management command
    that has no business touching payments.
    """
    if not _configured():
        raise PaymentError(
            "ЮKassa is not configured: set VEILGATE_YOOKASSA_SHOP_ID and "
            "VEILGATE_YOOKASSA_SECRET_KEY"
        )
    from yookassa import Configuration, Payment  # noqa: PLC0415 (lazy on purpose)

    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return Payment


def create_payment(invoice, return_url: str) -> tuple[str, str]:
    """Start a payment for an invoice. Returns (payment_id, confirmation_url).

    The idempotence key is the INVOICE NUMBER, not a fresh uuid. A customer who
    double-clicks, or a retry after a timeout we never saw the answer to, must
    not produce two payments for one invoice — and the provider can only prevent
    that if we give it the same key both times.
    """
    Payment = _client()
    try:
        payment = Payment.create({
            "amount": {"value": f"{invoice.total:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": f"veilgate {invoice.number}, "
                           f"{invoice.period_start:%d.%m.%Y}—{invoice.period_end:%d.%m.%Y}",
            # Read back on notification to find the invoice again. Only our own
            # identifiers: this object goes to a third party, so it carries an
            # invoice number and an org id and nothing that describes a person.
            "metadata": {"invoice": invoice.number, "org": invoice.organization_id},
        }, f"veilgate-{invoice.number}")
    except Exception as error:  # the SDK raises provider-specific types
        raise PaymentError(f"ЮKassa refused the payment for {invoice.number}: {error}") from error
    return payment.id, payment.confirmation.confirmation_url


def fetch_status(payment_id: str) -> tuple[str, Decimal, str]:
    """Read a payment back from the provider. (status, amount, invoice_number).

    This is the ONLY thing that decides whether an invoice is paid. The webhook
    body is caller-controlled — this call is authenticated and goes to ЮKassa
    directly, so a forged notification about someone else's invoice resolves to
    whatever ЮKassa actually says, which is "no such payment".
    """
    Payment = _client()
    try:
        payment = Payment.find_one(payment_id)
    except Exception as error:
        raise PaymentError(f"could not read payment {payment_id}: {error}") from error
    return (
        payment.status,
        Decimal(str(payment.amount.value)),
        str((payment.metadata or {}).get("invoice", "")),
    )
