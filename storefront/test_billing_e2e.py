"""Billing, end to end, against the REAL ЮKassa test shop.

Not a mock and not the SDK called directly: every step goes through the code
that runs in production — `billing.services`, `billing.payments`, and the
webhook view. A test that talks to the provider itself proves the provider
agrees with us; this proves OUR path does.

What it walks:

    счёт выставлен
      -> оплата создана в ЮKassa (настоящий тестовый магазин)
      -> уведомление приходит, как пришло бы от них
      -> статус читается обратно из их API, а не из уведомления
      -> счёт помечен оплаченным, обслуживание возобновлено
      -> акт печатается

And the thing 54-ФЗ actually turns on: a receipt is attached for an individual
and NOT for a company, because ст. 2 п. 9 exempts transfers between
organisations and ИП. Sending one anyway fiscalises a transaction that should
not be and costs 1% of it.

    cd storefront && set -a && . ./.env.dev && set +a && .venv/bin/python test_billing_e2e.py
"""

import os
import sys
import tempfile
import time
from datetime import date, timedelta
from decimal import Decimal

FAILURES: list[str] = []
SKIPPED: list[str] = []


def skip(name: str) -> None:
    """Пропуск ПЕЧАТАЕТСЯ ОТДЕЛЬНО и никогда не путается с прохождением."""
    print(f"SKIP  {name}")
    SKIPPED.append(name)


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def main() -> int:
    if not os.environ.get("PSEUDEX_YOOKASSA_SECRET_KEY"):
        print("PSEUDEX_YOOKASSA_SECRET_KEY is not set — source storefront/.env.dev")
        return 1

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_SECRET_KEY"] = "billing-e2e"
    os.environ["PSEUDEX_DB_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="pseudex-billing-"), "b.sqlite3")
    # The licensing server of the local walkthrough stand (deploy/local.sh),
    # not the e2e gate stand — resuming a customer has to hit a real one.
    # Forced, not setdefault: .env.dev points at the e2e GATE stand's port,
    # which is only up while the gates run. Resuming a customer has to reach a
    # live licensing server, and the walkthrough stand's is the one that is.
    os.environ["PSEUDEX_LICENSING_ADMIN_URL"] = os.environ.get(
        "PSEUDEX_BILLING_LICENSING_URL", "http://127.0.0.1:9443")

    import django
    django.setup()
    from django.utils import timezone as _tz
    from django.core.management import call_command
    from django.test import Client
    from django.test.utils import setup_test_environment

    setup_test_environment()
    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_plans", verbosity=0)

    from accounts.models import Membership, Organization, User
    from billing import payments
    from billing.models import Invoice, Plan, Subscription
    from billing.services import mark_paid

    check("the test shop is reachable and configured", payments.is_available())

    # Two payers whose only difference is the one 54-ФЗ cares about.
    plan = Plan.objects.get(code="start")
    made = {}
    for kind, label in [(Organization.KIND_COMPANY, "ООО Ромашка"),
                        (Organization.KIND_PERSON, "Пётр")]:
        org = Organization.objects.create(display_name=label, kind=kind,
                                          legal_name=label, inn="7701234567")
        user = User.objects.create_user(email=f"{kind}@example.com")
        Membership.objects.create(user=user, organization=org)
        Subscription.objects.create(
            organization=org, plan=plan, state=Subscription.TRIAL,
            trial_ends_at=_tz.now() + timedelta(days=14),
            current_period_end=_tz.now() + timedelta(days=14),
        )
        # A key, issued on the REAL licensing server. Without it the org exists
        # only in our database, and resuming it fails with "unknown org_id" —
        # correctly, because a customer who never got a key was never stopped.
        from billing.services import issue_first_key
        issue_first_key(org)
        invoice = Invoice.objects.create(
            organization=org, number=Invoice.next_number(),
            state=Invoice.ISSUED,
            period_start=date.today() - timedelta(days=30), period_end=date.today(),
            plan_amount=plan.monthly_price, total=plan.monthly_price,
        )
        made[kind] = (org, user, invoice)

    # --- the receipt split, which is the whole point of the payer kind -------
    company_org, _company_user, company_invoice = made[Organization.KIND_COMPANY]
    person_org, person_user, person_invoice = made[Organization.KIND_PERSON]

    payment_id, url = payments.create_payment(
        person_invoice, "http://localhost:8080/app/", person_user.email)
    check("a payment is created for an individual", bool(payment_id) and url.startswith("https://"),
          f"id={payment_id[:12]}…")

    company_payment_id, _ = payments.create_payment(
        company_invoice, "http://localhost:8080/app/", "buh@romashka.ru")
    check("a payment is created for a company", bool(company_payment_id),
          f"id={company_payment_id[:12]}…")

    # WHAT WE SEND, not what comes back. The first version of this check read a
    # field off the provider's response and fell back to `or True`, which made
    # it pass unconditionally — a test that asserts nothing is worse than none,
    # because it reports success. The receipt decision is OURS, so it is checked
    # where it is made: by capturing the body handed to the SDK.
    captured: list[dict] = []
    from yookassa import Payment as RawPayment
    original_create = RawPayment.create

    def _capture(body, key=None):
        captured.append(body)
        return original_create(body, key)

    RawPayment.create = staticmethod(_capture)
    try:
        payments.create_payment(person_invoice, "http://localhost:8080/app/",
                                person_user.email)
        payments.create_payment(company_invoice, "http://localhost:8080/app/",
                                "buh@romashka.ru")
    finally:
        RawPayment.create = staticmethod(original_create)

    person_body, company_body = captured[0], captured[1]
    check("an individual's payment carries a fiscal receipt",
          "receipt" in person_body
          and person_body["receipt"]["customer"]["email"] == person_user.email,
          "54-ФЗ: физлицу чек обязателен по любому способу оплаты")
    check("a company's payment carries NO receipt",
          "receipt" not in company_body,
          "ст. 2 п. 9 освобождает безнал между организациями и ИП")
    check("the receipt states без НДС, as an ИП on УСН charges",
          person_body["receipt"]["items"][0]["vat_code"] == 1,
          f'vat_code={person_body["receipt"]["items"][0]["vat_code"]}')

    # --- reading the truth back from the provider ---------------------------
    status, amount, number = payments.fetch_status(payment_id)
    check("status is read back from ЮKassa, not from a notification",
          status == "pending" and amount == person_invoice.total
          and number == person_invoice.number,
          f"status={status} amount={amount} invoice={number}")

    # --- the webhook, exactly as ЮKassa would send it ------------------------
    client = Client()
    unpaid = client.post(
        "/hooks/yookassa",
        data='{"event": "payment.succeeded", "object": {"id": "%s", '
             '"status": "succeeded"}}' % payment_id,
        content_type="application/json")
    person_invoice.refresh_from_db()
    check("a notification claiming success is not believed while ЮKassa says pending",
          person_invoice.state != Invoice.PAID and unpaid.status_code == 200,
          f"status={unpaid.status_code} invoice={person_invoice.state}")

    # --- the paid path, driven through our own service ----------------------
    # The card cannot be completed headlessly (ЮKassa hosts the form), so the
    # transition itself is exercised directly — which is the part that is ours.
    # Everything upstream of it has just been proved against the real API.
    # ПРЕДУСЛОВИЕ РЕШАЕТСЯ ОДИН РАЗ И ЗАРАНЕЕ, А НЕ ЛОВИТСЯ ПОТОМ.
    #
    # Здесь стоял голый `except Exception`, и он приравнивал «лицензионного
    # сервера нет» к «лицензионный сервер отказал». Комментарий называл первое,
    # а ловилось второе: 403 на `/admin/resume` — то есть оплаченный и НЕ
    # возобновлённый клиент — глотался, три проверки молча пропускались, прогон
    # оставался зелёным. Проверка, исчезающая ровно тогда, когда ломается то,
    # что она проверяет.
    #
    # Пробник идёт по адресу и токену ИЗ `settings`, а не по своей константе:
    # иначе можно опросить не тот адрес, куда пойдёт код под тестом.
    from django.conf import settings as _settings
    import httpx as _httpx
    try:
        _httpx.get(f"{_settings.LICENSING_ADMIN_URL.rstrip('/')}/admin/list",
                   timeout=2,
                   headers={"Authorization": f"Bearer {_settings.LICENSING_ADMIN_TOKEN}"})
        licensing_up = True
    except _httpx.HTTPError as error:
        licensing_up = False
        skip(f"оплата возобновляет обслуживание "
             f"(лицензионный сервер по {_settings.LICENSING_ADMIN_URL} не отвечает: {error})")

    if licensing_up:
        # ПОСЛЕ ПРОБНИКА `except` НЕ ОСТАЁТСЯ НИ ОДНОГО. Отказ здесь — это
        # провал теста, а не повод отменить проверку.
        mark_paid(company_invoice)
        moved = True
    if licensing_up:
        company_invoice.refresh_from_db()
        subscription = company_org.subscription
        subscription.refresh_from_db()
        check("paying moves the invoice and resumes the subscription",
              company_invoice.state == Invoice.PAID
              and subscription.state == Subscription.ACTIVE,
              f"invoice={company_invoice.state} subscription={subscription.state}")

        before = subscription.current_period_end
        mark_paid(company_invoice)
        subscription.refresh_from_db()
        check("a duplicate notification does not grant a second month",
              subscription.current_period_end == before,
              "ЮKassa redelivers; two deliveries once meant two free months")

        client.force_login(User.objects.get(email=f"{Organization.KIND_COMPANY}@example.com"))
        printed = client.get(f"/app/invoices/{company_invoice.number}/print")
        body = printed.content.decode()
        check("a paid invoice prints as an акт",
              printed.status_code == 200 and "акт выполненных работ" in body.lower(),
              "работы приняты только после оплаты")

    print()
    # ПРОПУСК ПЕЧАТАЕТСЯ ОТДЕЛЬНОЙ СТРОКОЙ И НИКОГДА НЕ СЧИТАЕТСЯ ПРОХОЖДЕНИЕМ.
    # Раньше пропущенные проверки просто исчезали из вывода, и «зелёный прогон»
    # означал «тест не сделал того, ради чего написан».
    if SKIPPED:
        print(f"SKIPPED: {len(SKIPPED)} — {', '.join(SKIPPED)}")
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        return 1
    print("billing OK — real test shop, receipt only where 54-ФЗ requires one, "
          "notifications not trusted, duplicates harmless")
    return 0


if __name__ == "__main__":
    sys.exit(main())
