"""ОПЛАЧЕНО У ПРОВАЙДЕРА — ЗНАЧИТ ОПЛАЧЕНО У НАС.

ЧТО ЭТО ЛОВИТ, И ПОЧЕМУ ЭТО НЕ ЛОВИЛ НИКТО. 28.09.2026 клиент заплатил 990 ₽:
у ЮKassa платёж `succeeded`, у нас счёт `PS-2026-09-6300da97` остался `issued`,
подписка `pending`, ключей у организации ноль. Деньги ушли, обслуживания нет, и
человек смотрит на «ЖДЁТ ОПЛАТЫ» на странице, которую только что покинул ради
оплаты.

Причина оказалась не в коде оплаты, а в ЕДИНСТВЕННОЙ ДВЕРИ. Уведомление
ЮKassa — настройка в чужом кабинете, и она не сделана: за всё время ни одного
`POST /hooks/yookassa` в логах, при пяти платежах из пяти, дошедших до
`succeeded`. А страница, куда провайдер возвращает клиента (`return_url`), была
ВИТРИНОЙ: она рисовала счёт и ни разу не спросила провайдера, чем кончилось
дело. Проверять это было нечем: `test_billing_lifecycle.py` сам присылает
уведомление, `test_billing_e2e.py` ходит против настоящего магазина и требует
его ключей и человека с картой.

ЗДЕСЬ СЕТЬ ПОДМЕНЕНА В ОДНОМ МЕСТЕ — в ответе провайдера о деньгах, — и
проверяются ТРИ двери, которыми этот ответ теперь спрашивается: возврат клиента,
уведомление и часовой обход биллинга. Подделка моделирует и правило
идемпотентности ЮKassa (ключ разрешается в результат ПЕРВОГО запроса) — потому
что второй дефект, найденный рядом, живёт ровно в нём: отменённая попытка
навсегда запирала кнопку «оплатить картой», а её ответ без `confirmation`
ронял страницу пятисоткой.

Запуск:  cd storefront && .venv/bin/python test_payment_return.py
"""

import os
import sys
from datetime import date, timedelta

from decimal import Decimal


class Confirmation:
    def __init__(self, url: str) -> None:
        self.confirmation_url = url


class Amount:
    def __init__(self, value: str) -> None:
        self.value = value


class Payment:
    """Объект платежа ровно в той форме, в какой его читает наш код."""

    def __init__(self, pid: str, status: str, url: str = "",
                 amount: str = "0.00", invoice: str = "") -> None:
        self.id = pid
        self.status = status
        # У ОТМЕНЁННОГО И ЗАВЕРШЁННОГО ПОДТВЕРЖДЕНИЯ НЕТ — `None`, а не пустой
        # объект. Проверено на живом магазине: `Payment.find_one` отменённого
        # платежа отдаёт `confirmation is None`.
        self.confirmation = Confirmation(url) if url else None
        self.amount = Amount(amount)
        self.metadata = {"invoice": invoice}


class Provider:
    """Подделка ЮKassa: правило идемпотентности и создание новых платежей.

    Ключ разрешается в результат ПЕРВОГО запроса — так это работает у
    провайдера, и именно это превращало «не создавать второй платёж» в «вернуть
    мёртвый». Каждый запрос записывается: ключи проверяются как данные, а не
    как «примерно то».
    """

    def __init__(self) -> None:
        self.by_key: dict[str, Payment] = {}
        self.by_id: dict[str, Payment] = {}
        self.keys: list[str] = []
        self.bodies: list[dict] = []
        self.counter = 0

    def seed(self, key: str, payment: Payment) -> Payment:
        self.by_key[key] = payment
        self.by_id[payment.id] = payment
        return payment

    def create(self, body: dict, key: str) -> Payment:
        self.keys.append(key)
        self.bodies.append(body)
        if key in self.by_key:
            return self.by_key[key]
        self.counter += 1
        payment = Payment(f"srv-{self.counter}", "pending",
                          url=f"https://pay.test/{self.counter}",
                          amount=str(body["amount"]["value"]),
                          invoice=str(body.get("metadata", {}).get("invoice", "")))
        self.seed(key, payment)
        return payment

    def find_one(self, pid: str) -> Payment:
        return self.by_id[pid]


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "payment-return-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-payment-return.db"
    os.environ["SITE_URL"] = "http://localhost"
    # Эквайринг «включён»: предмет проверки — путь денег, а не рубильник.
    os.environ["PSEUDEX_YOOKASSA_SHOP_ID"] = "test-shop"
    os.environ["PSEUDEX_YOOKASSA_SECRET_KEY"] = "test-secret"
    os.environ["PSEUDEX_ACQUIRING_ENABLED"] = "1"
    if os.path.exists("/tmp/pseudex-payment-return.db"):
        os.remove("/tmp/pseudex-payment-return.db")

    import django
    django.setup()
    from django.core.management import call_command
    from django.test import Client
    from django.test.utils import setup_test_environment
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from billing import licensing, payments, services
    from accounts.models import Membership
    from billing.models import Invoice, LicenseKey, Subscription

    ok = True

    def check(cond: bool, name: str, detail: str = "") -> None:
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # СЕТЬ — ЗАГЛУШКОЙ, И ВЫЗОВЫ ЗАПИСЫВАЮТСЯ. Лицензионный сервер здесь не
    # предмет проверки; важно, что выпуск ключа доезжает до него ровно тогда,
    # когда должен.
    issued: list[tuple[str, str]] = []
    statuses: list[tuple[str, str]] = []
    licensing.issue_key = lambda org_id, plan: (
        issued.append((org_id, plan)) or f"ps_live_{len(issued):08d}")
    licensing.set_status = lambda org_id, status: statuses.append((org_id, status)) or 1
    licensing.set_org_plan = lambda org_id, plan: 1
    licensing.set_ceiling = lambda org_id, ceiling: None
    licensing.usage = lambda org_id: {"usage": {}}
    licensing.fleet = lambda org_ids: {}

    provider = Provider()
    payments._client = lambda: provider

    def as_provider(payment_id: str, amount: Decimal, number: str) -> None:
        """Ответ провайдера про конкретный платёж: деньги пришли."""
        provider.seed(payment_id, Payment(payment_id, "succeeded",
                                          amount=f"{amount:.2f}", invoice=number))

    # ── 1. кнопка «оплатить картой» не запирается мёртвой попыткой ────────
    #
    # Провайдер держит ключ 24 часа и разрешает его в результат ПЕРВОГО запроса.
    # Если первая попытка истекла (`expired_on_confirmation`), по тому же ключу
    # возвращается отменённый платёж, в котором нет ни одной ссылки. Прежний код
    # читал `payment.confirmation.confirmation_url` без проверки и падал
    # AttributeError — то есть пятисоткой по кнопке.
    dead = services.create_account("dead@acme-corp.ru", "Деад", "start", "203.0.113.1")
    from billing.models import Plan
    dead_invoice = services.build_switch_invoice(dead, Plan.objects.get(code="start"))
    provider.seed(f"pseudex-{dead_invoice.number}",
                  Payment("dead-1", "canceled", url=""))
    try:
        payment_id, url = payments.create_payment(
            dead_invoice, "http://localhost/app/", "dead@acme-corp.ru")
        check(url.startswith("https://pay.test/"),
              "отменённая попытка не запирает кнопку: выдан РАБОЧИЙ платёж", url)
        check(payment_id != "dead-1",
              "и это не тот же самый мёртвый платёж", payment_id)
        check(provider.keys[-2:] == [f"pseudex-{dead_invoice.number}",
                                     f"pseudex-{dead_invoice.number}-dead-1"],
              "ключ уточнён идентификатором мёртвой попытки — цепочка",
              str(provider.keys[-2:]))
    except payments.PaymentError as error:
        check(False, "отменённая попытка не запирает кнопку", str(error))

    # Двойное нажатие по-прежнему не чеканит второй платёж: цепочка ключей
    # детерминирована, поэтому оба клика приходят в одну и ту же запись.
    try:
        again_id, again_url = payments.create_payment(
            dead_invoice, "http://localhost/app/", "dead@acme-corp.ru")
        check(again_id == payment_id and again_url == url,
              "второе нажатие — тот же платёж, а не второй", f"{again_id} / {payment_id}")
    except payments.PaymentError as error:
        check(False, "второе нажатие — тот же платёж, а не второй", str(error))

    # А вот ПРОШЕДШИЙ платёж второй раз не просят никогда: деньги уже взяты, и
    # единственный правильный ответ — не создавать новую попытку, а сказать, что
    # платить нечего.
    provider.seed(f"pseudex-{dead_invoice.number}-dead-1",
                  Payment("done-1", "succeeded", url="", amount="990.00",
                          invoice=dead_invoice.number))
    try:
        payments.create_payment(dead_invoice, "http://localhost/app/", "dead@acme-corp.ru")
        check(False, "по прошедшему платежу новую попытку не создаём",
              "create_payment вернул платёж вместо ошибки")
    except payments.PaymentError:
        check(True, "по прошедшему платежу новую попытку не создаём")

    # ── 2. ГЛАВНОЕ: возврат с оплаты закрывает счёт ───────────────────────
    org = services.create_account("paid@acme-corp.ru", "Пейд", "start", "203.0.113.2")
    subscription = org.subscription
    check(subscription.state == Subscription.PENDING and not org.keys.exists(),
          "платный тариф с лендинга: подписка ждёт оплаты, ключа нет",
          f"{subscription.state}")
    check(not services.may_issue_keys(subscription),
          "и ключ до денег не выпускается")

    invoice = services.build_switch_invoice(org, subscription.plan)
    payment_id = "324c7507-000f-5001-9000-1549ed87f11c"
    invoice.payment_ref = payment_id
    invoice.save(update_fields=["payment_ref"])
    as_provider(payment_id, invoice.total, invoice.number)

    member = Membership.objects.get(organization=org).user
    client = Client()
    client.force_login(member)

    answer = client.get(f"/app/invoices/{invoice.number}")
    invoice.refresh_from_db()
    subscription.refresh_from_db()
    check(answer.status_code == 302 and answer["Location"] == "/app/",
          "возврат с оплаты уводит в кабинет, а не оставляет на счёте",
          f"{answer.status_code} -> {answer.get('Location')}")
    check(invoice.state == Invoice.PAID,
          "СЧЁТ ЗАКРЫТ по возврату клиента, хотя уведомление не приходило",
          invoice.state)
    check(invoice.service_resumed_at is not None,
          "и обслуживание отмечено восстановленным", str(invoice.service_resumed_at))
    check(subscription.state == Subscription.ACTIVE,
          "подписка стала активной — статус платежа больше не висит",
          subscription.state)
    check(services.may_issue_keys(subscription),
          "ключ теперь выпускается", str(services.may_issue_keys(subscription)))

    # ── 3. и ключ действительно выпускается тем же путём, что у пробы ─────
    answer = client.post("/app/keys/new", {"label": "прод", "environment": "live"})
    check(answer.status_code == 302 and answer["Location"] == "/welcome",
          "кнопка «выпустить ключ» ведёт на страницу одноразового показа",
          f"{answer.status_code} -> {answer.get('Location')}")
    keys = list(LicenseKey.objects.filter(organization=org, revoked_at__isnull=True))
    check(len(keys) == 1 and issued and issued[-1][1] == "start",
          "ключ выпущен на оплаченном тарифе",
          f"ключей={len(keys)} issued={issued}")

    # ── 4. повторный возврат не дарит второй месяц ───────────────────────
    period_end = subscription.current_period_end
    client.get(f"/app/invoices/{invoice.number}")
    subscription.refresh_from_db()
    check(subscription.current_period_end == period_end,
          "повторный заход на страницу счёта не продлевает период",
          f"{period_end:%d.%m} -> {subscription.current_period_end:%d.%m}")

    # ── 5. недоплата возвратом не закрывается ────────────────────────────
    short_org = services.create_account("short@acme-corp.ru", "Шорт", "start", "203.0.113.3")
    short_invoice = services.build_switch_invoice(short_org, short_org.subscription.plan)
    short_id = "2f8e1c3a-3333-4000-8000-cccccccccccc"
    short_invoice.payment_ref = short_id
    short_invoice.save(update_fields=["payment_ref"])
    as_provider(short_id, short_invoice.total - Decimal("1"), short_invoice.number)
    short_client = Client()
    short_client.force_login(Membership.objects.get(organization=short_org).user)
    short_client.get(f"/app/invoices/{short_invoice.number}")
    short_invoice.refresh_from_db()
    check(short_invoice.state != Invoice.PAID,
          "недоплата не закрывает счёт и не возобновляет обслуживание",
          short_invoice.state)

    # ── 6. кнопка оплаты не берёт деньги второй раз ──────────────────────
    #
    # Счёт оплачен, но не отмечен (уведомления нет) — ровно состояние, в
    # котором кнопка «оплатить картой» раньше вела ко второму списанию: в базе
    # `issued`, значит проверка «уже оплачен?» пропускала, а провайдера никто
    # не спрашивал.
    double_org = services.create_account("double@acme-corp.ru", "Дабл", "start", "203.0.113.4")
    double_invoice = services.build_switch_invoice(double_org, double_org.subscription.plan)
    double_id = "2f8e1c3a-4444-4000-8000-dddddddddddd"
    double_invoice.payment_ref = double_id
    double_invoice.save(update_fields=["payment_ref"])
    as_provider(double_id, double_invoice.total, double_invoice.number)
    double_client = Client()
    double_client.force_login(Membership.objects.get(organization=double_org).user)
    before = len(provider.keys)
    answer = double_client.post(f"/app/invoices/{double_invoice.number}/pay")
    double_invoice.refresh_from_db()
    check(answer.status_code == 302 and double_invoice.state == Invoice.PAID,
          "нажатие «оплатить картой» по уже оплаченному счёту закрывает его",
          f"{answer.status_code} {double_invoice.state}")
    check(len(provider.keys) == before,
          "и НЕ создаёт новую попытку списания", f"{len(provider.keys)} vs {before}")

    # ── 7. уведомление по-прежнему работает и остаётся идемпотентным ─────
    hook_org = services.create_account("hook@acme-corp.ru", "Хук", "start", "203.0.113.5")
    hook_invoice = services.build_switch_invoice(hook_org, hook_org.subscription.plan)
    hook_id = "2f8e1c3a-5555-4000-8000-eeeeeeeeeeee"
    as_provider(hook_id, hook_invoice.total, hook_invoice.number)
    hook_client = Client()
    import json as _json
    first = hook_client.post("/hooks/yookassa",
                             data=_json.dumps({"object": {"id": hook_id}}),
                             content_type="application/json")
    hook_invoice.refresh_from_db()
    hook_org.subscription.refresh_from_db()
    period_end = hook_org.subscription.current_period_end
    second = hook_client.post("/hooks/yookassa",
                              data=_json.dumps({"object": {"id": hook_id}}),
                              content_type="application/json")
    hook_org.subscription.refresh_from_db()
    check(first.status_code == 200 and hook_invoice.state == Invoice.PAID,
          "уведомление закрывает счёт, как и раньше",
          f"{first.status_code} {hook_invoice.state}")
    check(second.status_code == 200
          and hook_org.subscription.current_period_end == period_end,
          "повторная доставка не дарит второй месяц",
          f"{second.status_code} {period_end:%d.%m} -> "
          f"{hook_org.subscription.current_period_end:%d.%m}")

    # ── 8. часовой обход дочиняет того, кто не вернулся ──────────────────
    #
    # Клиент, заплативший и закрывший вкладку, на страницу возврата не придёт.
    # Без этого шага он остаётся неоплаченным навсегда — и это не теория: именно
    # так выглядели все пять наших платежей.
    away_org = services.create_account("away@acme-corp.ru", "Авэй", "start", "203.0.113.6")
    away_invoice = services.build_switch_invoice(away_org, away_org.subscription.plan)
    away_id = "2f8e1c3a-6666-4000-8000-ffffffffffff"
    away_invoice.payment_ref = away_id
    away_invoice.save(update_fields=["payment_ref"])
    as_provider(away_id, away_invoice.total, away_invoice.number)
    call_command("run_billing_cycle", verbosity=0)
    away_invoice.refresh_from_db()
    away_org.subscription.refresh_from_db()
    check(away_invoice.state == Invoice.PAID,
          "часовой обход подтверждает оплату у провайдера сам", away_invoice.state)
    check(away_org.subscription.state == Subscription.ACTIVE,
          "и поднимает подписку без единого действия клиента",
          away_org.subscription.state)

    # ── 9. обход не трогает счёт без платежа ─────────────────────────────
    quiet_org = services.create_account("quiet@acme-corp.ru", "Квайт", "start", "203.0.113.7")
    quiet_invoice = services.build_switch_invoice(quiet_org, quiet_org.subscription.plan)
    before = len(provider.keys)
    call_command("run_billing_cycle", verbosity=0)
    quiet_invoice.refresh_from_db()
    check(quiet_invoice.state == Invoice.ISSUED
          and quiet_org.subscription.state == Subscription.PENDING,
          "счёт без попытки оплаты обход не трогает и провайдера не спрашивает",
          f"{quiet_invoice.state} {quiet_org.subscription.state}")
    check(len(provider.keys) == before,
          "и ни одного лишнего запроса к провайдеру", f"{len(provider.keys)}")

    # ── 10. уведомление о платеже, которого провайдер не знает, — это 200 ─
    #
    # На адрес уведомлений шлют проверочные и чужие события. Прежний код отвечал
    # на них 502 «не смогли выяснить», а 502 на публичном адресе читается как
    # поломка адреса: кабинет ЮKassa такую настройку не сохраняет. То есть
    # единственную дверь, которая у нас была, нельзя было даже включить.
    from yookassa.domain.exceptions.not_found_error import NotFoundError

    class _UnknownProvider:
        def find_one(self, pid):
            raise NotFoundError({"type": "error", "code": "not_found",
                                 "description": "такого платежа нет"})

    original_client = payments._client
    payments._client = lambda: _UnknownProvider()
    try:
        try:
            payments.fetch_status("2f8e1c3a-9999-4000-8000-000000000000")
            check(False, "404 провайдера отличается от «не дозвонились»",
                  "исключения не было вовсе")
        except payments.PaymentNotKnown:
            check(True, "404 провайдера отличается от «не дозвонились»")
        except payments.PaymentError as error:
            check(False, "404 провайдера отличается от «не дозвонились»", repr(error))
    finally:
        payments._client = original_client

    original_fetch = payments.fetch_status
    try:
        def _not_known(_pid):
            raise payments.PaymentNotKnown("такого платежа нет")

        payments.fetch_status = _not_known
        answer = hook_client.post(
            "/hooks/yookassa",
            data=_json.dumps({"object": {
                "id": "2f8e1c3a-7777-4000-8000-000000000000"}}),
            content_type="application/json")
        check(answer.status_code == 200,
              "чужой или проверочный платёж получает 200, а не 502",
              str(answer.status_code))

        def _unreachable(_pid):
            raise payments.PaymentError("нет связи с провайдером")

        payments.fetch_status = _unreachable
        answer = hook_client.post(
            "/hooks/yookassa",
            data=_json.dumps({"object": {
                "id": "2f8e1c3a-8888-4000-8000-000000000000"}}),
            content_type="application/json")
        check(answer.status_code == 502,
              "а недоступный провайдер — по-прежнему 502, повторить нужно",
              str(answer.status_code))
    finally:
        payments.fetch_status = original_fetch

    # ── 11. у КЛИЕНТА С КЛЮЧОМ оплата доезжает до лицензионного сервера ───
    #
    # РАЗНИЦА МЕЖДУ ПЕРВОЙ ПОКУПКОЙ И ПРОДЛЕНИЕМ, и она не косметическая.
    # Клиенту БЕЗ ключей лицензионный сервер не нужен вовсе: организации он ещё
    # не знает, и `mark_paid` намеренно молчит — он узнает её при выпуске
    # первого ключа. А у клиента С ключом лимиты живут на сервере, и без звонка
    # оплата поднимет цифру в кабинете, оставив контейнеры под прежним потолком.
    #
    # ЭТО ЖЕ И ЕСТЬ ПЛЕЧО, КОТОРОЕ ДО СИХ ПОР НЕ ДОСТИГАЛОСЬ: пока платёж не
    # закрывался, `mark_paid` не вызывался вообще, и до лицензионного сервера не
    # доезжало ничего. Проверка держит обе половины: звонок делается, когда он
    # нужен, и не делается, когда ключей нет.
    from billing.models import LicenseKey

    def org_with_a_key(email: str, ip: str):
        """Клиент, который уже работает: ключ есть, обслуживание остановлено."""
        client_org = services.create_account(email, "Ключевой", "work", ip)
        # Хеш ключа уникален на всю таблицу: два клиента с одним ключом — не наш
        # случай, а нарушение инварианта самой модели.
        LicenseKey.record(client_org, f"ps_live_{email.split('@')[0]}0000000001",
                          "прод", "live")
        subscription = client_org.subscription
        subscription.state = Subscription.PAST_DUE
        subscription.save(update_fields=["state"])
        return client_org

    renewing = org_with_a_key("renew@acme-corp.ru", "203.0.113.8")
    renew_invoice = services.build_invoice(renewing, date.today(),
                                           date.today() + timedelta(days=30))
    renew_invoice.state = Invoice.ISSUED
    renew_id = "2f8e1c3a-9999-4000-8000-111111111111"
    renew_invoice.payment_ref = renew_id
    renew_invoice.save(update_fields=["state", "payment_ref"])
    as_provider(renew_id, renew_invoice.total, renew_invoice.number)
    statuses.clear()
    services.settle_payment(invoice=renew_invoice)
    renewing.subscription.refresh_from_db()
    check((renewing.id, "active") in statuses,
          "оплата клиента С КЛЮЧОМ доезжает до лицензионного сервера",
          str(statuses))
    check(renewing.subscription.state == Subscription.ACTIVE,
          "и подписка становится активной", renewing.subscription.state)

    # Смена тарифа — ВТОРОЙ звонок, и он несёт САМ тариф: потолок на сервере
    # берётся из него. Без этого оплата «Промышленного» осталась бы цифрой в
    # кабинете.
    switched: list[tuple[str, str]] = []
    licensing.set_org_plan = lambda org_id, plan: switched.append((org_id, plan)) or 1
    mover = org_with_a_key("move@acme-corp.ru", "203.0.113.9")
    move_invoice = services.build_switch_invoice(mover, Plan.objects.get(code="industrial"))
    move_id = "2f8e1c3a-aaaa-4000-8000-222222222222"
    move_invoice.payment_ref = move_id
    move_invoice.save(update_fields=["payment_ref"])
    as_provider(move_id, move_invoice.total, move_invoice.number)
    services.settle_payment(invoice=move_invoice)
    mover.subscription.refresh_from_db()
    check(switched and switched[-1] == (mover.id, "industrial"),
          "смена тарифа уходит на лицензионный сервер вместе с оплатой",
          str(switched))
    check(mover.subscription.plan_id == "industrial",
          "и тариф подписки переставлен по факту денег", mover.subscription.plan_id)

    print()
    if ok:
        print("все проверки прошли")
        return 0
    print(f"ПРОВАЛЕНО: {sys.stderr}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
