"""Жизненный цикл биллинга, от лендинга до контейнера, на mock-провайдере.

ЧТО ЗДЕСЬ НАСТОЯЩЕЕ, А ЧТО ПОДДЕЛАНО — ровно одна вещь поддельна, и это ответ
платёжного провайдера о деньгах. Настоящие: код витрины целиком, лицензионный
сервер, выпуск ключа, аренда, движок и маскирование. Мы подменяем
`payments.fetch_status`, потому что чужой боевой магазин — не наша половина
системы, и `test_billing_e2e.py` уже проверяет договорённость с ним отдельно.

ЗАЧЕМ ОТДЕЛЬНО ОТ `test_billing_e2e.py`. Тот идёт ОДИН путь — счёт, оплата, акт
— против настоящей ЮKassa, и потому не может пройти без ключей магазина и не
может ждать. Здесь проверяется другое: ПЕРЕХОДЫ, которых у продукта девять, и
каждый из них меняет то, что видит контейнер клиента. Ни один из них не
выполнялся никогда, потому что вызывать `build_invoice` и `mark_unpaid` было
некому — планировщика не существовало.

ОСТАНОВКА ДОКАЗЫВАЕТСЯ КОНТЕЙНЕРОМ, А НЕ ЗАПИСЬЮ В БАЗЕ. `Subscription.state`
— это зеркало для отрисовки; если считать его доказательством, то тест пройдёт
и на продукте, который берёт деньги и не выключает неплательщика. Поэтому
каждый переход, меняющий обслуживание, проверяется запросом `/mask` в живой
контейнер: замаскировал — обслуживание идёт, отказал — стоит.

ТРЕБУЕТ ПОДНЯТОГО СТЕНДА:

    bash deploy/local.sh
    cd storefront && .venv/bin/python test_billing_lifecycle.py

Аренда стенда по умолчанию живёт пять минут, и остановка видна только на
следующем продлении. Чтобы не ждать, поднимите стенд с коротким TTL — это
конфигурация, а не крючок:

    STAND_LEASE_TTL=25 STAND_GRACE=15 bash deploy/local.sh
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import httpx

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DEPLOY = _ROOT / "deploy"

LICENSE_ADMIN = "http://127.0.0.1:9443"
LICENSE_FOR_CONTAINER = "http://host.docker.internal:8443"
CONTAINER = "pseudex-billing-lifecycle"
# Образ СТЕНДА, а не гейтов: у них разные ключи проверки, и общий тег
# означал бы, что прогон гейтов ломает этот тест молча.
STAND_IMAGE = "pseudex:local"
GATEWAY_TOKEN = "lifecycle-gateway-token"
ADMIN_TOKEN_UI = "lifecycle-admin-token"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _stand_token() -> str:
    path = _DEPLOY / ".local-tokens"
    if not path.exists():
        print("стенд не поднят: нет deploy/.local-tokens — запустите deploy/local.sh")
        raise SystemExit(1)
    return path.read_text().splitlines()[0]


def stand_ttl(token: str) -> int:
    """Сколько живёт аренда У ЗАПУЩЕННОГО СЕРВЕРА, а не в переменной окружения.

    Тест брал TTL из `STAND_LEASE_TTL`, то есть из переменной ТЕКУЩЕГО шелла, а
    контейнер работает с тем значением, которое ему дали при создании. Стоит
    один раз поднять стенд без неё — и два числа расходятся молча: проверки,
    ждущие закрытия окна, падают не потому, что продукт сломан, а потому что
    ждали 33 секунды вместо пяти минут.

    Ложный красный дороже ложного зелёного: его начинают игнорировать вместе с
    настоящими. Поэтому спрашиваем сервер — он отдаёт своё окно в каждом ответе
    `/admin/fleet`.
    """
    try:
        answer = httpx.get(f"{LICENSE_ADMIN}/admin/fleet", timeout=10,
                           params={"org_ids": "probe"},
                           headers={"Authorization": f"Bearer {token}"})
        window = answer.json().get("window_seconds")
        if isinstance(window, int) and window > 0:
            return window
    except (httpx.HTTPError, ValueError):
        pass
    return 300


def _stand_alive(token: str) -> bool:
    try:
        answer = httpx.get(f"{LICENSE_ADMIN}/admin/list", timeout=5,
                           headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        return False
    return answer.status_code == 200


# --- контейнер -----------------------------------------------------------

def start_container(key: str) -> bool:
    """Настоящий движок на настоящем ключе. Возвращает, поднялся ли он."""
    subprocess.run(["docker", "rm", "-f", CONTAINER],
                   capture_output=True, text=True, timeout=60)
    subprocess.run([
        "docker", "run", "-d", "--name", CONTAINER,
        "-p", "18100:8000",
        "-e", f"PSEUDEX_LICENSE_KEY={key}",
        "-e", f"PSEUDEX_LICENSE_URL={LICENSE_FOR_CONTAINER}",
        "-e", f"PSEUDEX_GATEWAY_TOKEN={GATEWAY_TOKEN}",
        "-e", f"PSEUDEX_ADMIN_TOKEN={ADMIN_TOKEN_UI}",
        # Один воркер: тест смотрит на ОДИН процесс и его аренду, а несколько
        # за SO_REUSEPORT сделали бы «ответил или нет» вопросом о том, к какому
        # процессу попал запрос.
        "-e", "PSEUDEX_WORKERS=1",
        "-e", "PSEUDEX_UI", "-e", "PSEUDEX_VAULT_ENCRYPTION=off",
        os.environ.get("PSEUDEX_STAND_IMAGE", "pseudex:local"),
    ], capture_output=True, text=True, timeout=120)
    for _ in range(90):
        try:
            answer = httpx.get("http://127.0.0.1:18100/health", timeout=3)
            if answer.status_code == 200 and answer.json().get("license") == "active":
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def container_masks() -> tuple[bool, str]:
    """Обслуживает ли контейнер ПРЯМО СЕЙЧАС.

    Не `/health`: он отвечает и на остановленной лицензии, называя состояние.
    Вопрос теста — «выполняется ли работа, за которую заплачено», а это `/mask`.
    """
    try:
        answer = httpx.post("http://127.0.0.1:18100/mask", timeout=30,
                            headers={"Authorization": f"Bearer {GATEWAY_TOKEN}"},
                            json={"org_id": "acme", "messages": [
                                {"role": "user", "content": "позвоните Ивану +7 999 123-45-67"}]})
    except httpx.HTTPError as error:
        return False, f"нет ответа: {error}"
    if answer.status_code != 200:
        return False, f"HTTP {answer.status_code}"
    masked = answer.json()["messages"][0]["content"]
    return "+7 999 123-45-67" not in masked, masked[:60]


def wait_for_service(expected: bool, seconds: int) -> tuple[bool, str]:
    """Дождаться, пока контейнер придёт в ожидаемое состояние.

    Ожидание НЕ бесконечное и результат возвращается честно: тест, который
    крутится, пока не получит нужное, не может провалиться.
    """
    detail = ""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        serving, detail = container_masks()
        if serving == expected:
            return True, detail
        time.sleep(2)
    return False, detail


def main() -> int:
    token = _stand_token()
    if not _stand_alive(token):
        print("стенд не отвечает на", LICENSE_ADMIN, "— запустите deploy/local.sh")
        return 1

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_SECRET_KEY"] = "billing-lifecycle"
    os.environ["PSEUDEX_DB_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="pseudex-lifecycle-"), "b.sqlite3")
    os.environ["PSEUDEX_LICENSING_ADMIN_URL"] = LICENSE_ADMIN
    os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = token
    os.environ["PSEUDEX_LICENSE_STOREFRONT_TOKEN"] = token
    # Почта в память: письмо со счётом — часть перехода, и его отсутствие тоже
    # надо уметь увидеть.
    os.environ["PSEUDEX_SMTP_HOST"] = ""

    # ПОЧТА В ПАМЯТЬ. `mail.outbox` существует только у locmem-бэкенда, и без
    # него «письмо ушло» проверить нечем: консольный печатает в stdout и не
    # оставляет объекта, а SMTP в тесте не нужен вовсе.
    os.environ["PSEUDEX_EMAIL_BACKEND"] = "django.core.mail.backends.locmem.EmailBackend"

    import django
    django.setup()
    from django.conf import settings as django_settings
    django_settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail
    mail.outbox = []
    from django.core.management import call_command
    from django.test import Client
    from django.utils import timezone

    from billing import payments, services
    from billing.models import Invoice, Plan, Subscription
    from ops.analytics_models import Funnel

    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_plans", verbosity=0)

    # --- 0. лестница тарифов, арифметикой -------------------------------
    plans = {p.code: p for p in Plan.objects.all()}
    ladder_ok = True
    reasons = []
    for lower, upper in (("start", "work"), ("work", "industrial")):
        low, high = plans[lower], plans[upper]
        # ПРОВЕРЯТЬ НАДО ТАМ, ГДЕ НИЖНИЙ ТАРИФ ВООБЩЕ ТАРИФИЦИРУЕТСЯ. Первая
        # версия брала объём верхнего тарифа и падала на паре Старт->Рабочий:
        # Порог = 0, поэтому перерасход считается с первого запроса сверх включённого.
        # Настоящее свойство лестницы: перерасход обязан РАСТИ быстрее, чем стоит
        # переход на старший тариф. Берём точку заведомо выше включённого и требуем,
        # чтобы переход был выгоднее, чем остаться с перерасходом.
        volume = max(high.included_requests,
                     low.included_requests + low.metered_floor + 100_000)
        over = max(0, volume - low.included_requests - low.metered_floor)
        staying = low.monthly_price + Decimal(over) / 1000 * low.metered_per_1k
        if staying <= high.monthly_price:
            ladder_ok = False
            reasons.append(f"{lower}->{upper} на {volume}: остаться {staying} "
                           f"<= перейти {high.monthly_price}")
    floors = " · ".join(f"{c}:{plans[c].metered_floor}"
                        for c in ("start", "work", "industrial"))
    # ПОЛИТИКА: порог = 0 на всех тарифах — считаем с первого запроса сверх включённого,
    # без бесплатной полосы (решение владельца). Поле остаётся настраиваемым.
    check("порог тарификации = 0 на всех тарифах (биллим с первого сверх включённого)",
          all(plans[c].metered_floor == 0 for c in ("start", "work", "industrial")), floors)
    check("лестница окупает подъём на любом объёме", ladder_ok,
          "; ".join(reasons) or "переход всегда дешевле перерасхода")

    # --- 1. от лендинга до ключа ----------------------------------------
    client = Client()
    landing = client.get("/")
    check("лендинг открывается", landing.status_code == 200, f"код={landing.status_code}")

    email = f"lifecycle-{int(time.time())}@example.test"
    signup = client.post("/signup", {"email": email, "name": "ООО Тест",
                                     "consent": "1", "terms": "1",
                                     "plan": "industrial"})
    check("регистрация принята", signup.status_code == 200, f"код={signup.status_code}")

    organization = services.pending_organization(email)
    check("организация создана", organization is not None)
    if organization is None:
        return 1
    key = services.issue_first_key(organization)
    check("ключ выпущен и это настоящий ключ", key.startswith("ps_"), key[:12] + "…")

    # --- 2. контейнер клиента работает ----------------------------------
    up = start_container(key)
    check("контейнер поднялся на выпущенном ключе", up)
    if not up:
        print(subprocess.run(["docker", "logs", "--tail", "30", CONTAINER],
                             capture_output=True, text=True).stdout[-2000:])
        return 1
    serving, detail = container_masks()
    check("и маскирует настоящий телефон", serving, detail)

    # --- 2б. «ПОДНЯЛ КОНТЕЙНЕР» ЗАСЕКАЕТСЯ ПО АРЕНДЕ ЛИЦЕНЗИИ ------------
    # Это шаг воронки, невидимый из браузера: он случается на железе клиента и
    # доезжает к нам тем, что выданный ключ взял аренду. Проверяется настоящим
    # контейнером, потому что первая версия читала поля не того уровня
    # вложенности и не засекла бы его ни разу.
    call_command("run_billing_cycle", verbosity=0)
    raised = Funnel.objects.filter(step=Funnel.FIRST_LEASE,
                                   organization_id=organization.id).exists()
    check("ВОРОНКА ВИДИТ ПОДНЯТЫЙ КОНТЕЙНЕР", raised,
          "аренда выданного ключа — единственный след этого шага")
    # И не дублируется: цикл идёт каждый час, а поднял человек один раз.
    call_command("run_billing_cycle", verbosity=0)
    check("и не отмечает его второй раз",
          Funnel.objects.filter(step=Funnel.FIRST_LEASE,
                                organization_id=organization.id).count() == 1)

    # --- 3. триал кончился -> счёт --------------------------------------
    subscription = organization.subscription
    subscription.trial_ends_at = timezone.now() - timedelta(minutes=1)
    subscription.current_period_end = timezone.now() - timedelta(minutes=1)
    subscription.save(update_fields=["trial_ends_at", "current_period_end"])

    mail.outbox.clear()
    call_command("run_billing_cycle", verbosity=0)
    invoice = Invoice.objects.filter(organization=organization).first()
    check("цикл выставил счёт по концу триала", invoice is not None,
          invoice.number if invoice else "счёта нет")
    if invoice is None:
        return 1
    check("счёт выставлен, а не остался черновиком",
          invoice.state == Invoice.ISSUED, invoice.state)
    check("сумма — абонплата тарифа",
          invoice.total == plans["industrial"].monthly_price,
          f"{invoice.total} ₽")
    check("письмо со счётом ушло", len(mail.outbox) == 1,
          mail.outbox[0].subject if mail.outbox else "писем нет")

    # ПОВТОРНЫЙ ЗАПУСК НЕ ВЫСТАВЛЯЕТ ВТОРОЙ. Расписание запустит цикл ещё раз
    # через час, systemd повторит после падения, оператор нажмёт руками.
    call_command("run_billing_cycle", verbosity=0)
    check("повторный проход не выставил второй счёт",
          Invoice.objects.filter(organization=organization).count() == 1,
          f"{Invoice.objects.filter(organization=organization).count()} шт")

    # --- 4. НЕОПЛАТА: обслуживание встаёт -------------------------------
    invoice.due_at = date.today() - timedelta(days=10)
    invoice.save(update_fields=["due_at"])
    call_command("run_billing_cycle", verbosity=0)
    subscription.refresh_from_db()
    check("подписка помечена неоплаченной",
          subscription.state == Subscription.PAST_DUE, subscription.state)

    stopped, detail = wait_for_service(False, stand_ttl(token) + 40)
    check("КОНТЕЙНЕР ПЕРЕСТАЛ ОБСЛУЖИВАТЬ", stopped, detail)

    # --- 5. ОПЛАТА: обслуживание возвращается ---------------------------
    payment_ref = "2f8e1c3a-1111-4000-8000-aaaaaaaaaaaa"
    services.mark_paid(invoice, payment_ref=payment_ref)
    invoice.refresh_from_db()
    check("счёт оплачен", invoice.state == Invoice.PAID, invoice.state)
    check("и обслуживание отмечено восстановленным",
          invoice.service_resumed_at is not None)
    subscription.refresh_from_db()
    check("подписка снова активна",
          subscription.state == Subscription.ACTIVE, subscription.state)

    resumed, detail = wait_for_service(True, stand_ttl(token) + 40)
    check("КОНТЕЙНЕР СНОВА ОБСЛУЖИВАЕТ", resumed, detail)

    # --- 6. повторная доставка уведомления ------------------------------
    period_end_before = subscription.current_period_end
    services.mark_paid(invoice, payment_ref=payment_ref)
    subscription.refresh_from_db()
    check("повторная доставка не подарила второй месяц",
          subscription.current_period_end == period_end_before,
          f"{period_end_before:%d.%m} -> {subscription.current_period_end:%d.%m}")

    # --- 7. НЕДОПЛАТА обслуживание не возвращает ------------------------
    # Через настоящую вьюху вебхука, с подменённым ответом провайдера: это и
    # есть та единственная поддельная деталь.
    second = services.build_invoice(organization, date.today(),
                                    date.today() + timedelta(days=30))
    second.state = Invoice.ISSUED
    second.save(update_fields=["state"])
    original_fetch = payments.fetch_status
    payments.fetch_status = lambda pid: ("succeeded", second.total - Decimal("1"),
                                         second.number)
    try:
        answer = client.post("/hooks/yookassa",
                             data=json.dumps({"object": {
                                 "id": "2f8e1c3a-2222-4000-8000-bbbbbbbbbbbb"}}),
                             content_type="application/json")
        second.refresh_from_db()
        check("недоплата не отмечает счёт оплаченным",
              answer.status_code == 200 and second.state != Invoice.PAID,
              f"код={answer.status_code} состояние={second.state}")
        check("и обслуживание не возобновлено недоплатой",
              second.service_resumed_at is None,
              str(second.service_resumed_at))
    finally:
        payments.fetch_status = original_fetch

    # --- 8. ОБЪЁМ: вторая строка появляется по порогу --------------------
    # Ватермарка предыдущего счёта — это то, от чего считается период, поэтому
    # объём задаётся ЛИЦЕНЗИОННОМУ СЕРВЕРУ, а не полю счёта: иначе тест
    # проверял бы арифметику по числу, которое сам же и написал.
    plan = plans["industrial"]
    below = plan.included_requests + plan.metered_floor - 1
    above = plan.included_requests + plan.metered_floor + 200_000

    def invoice_for(capacity: int) -> Invoice:
        original_usage = services.licensing.usage
        services.licensing.usage = lambda org: {"usage": {
            "values": capacity, "requests": capacity,
            "capacity_billable": capacity}}
        try:
            return services.build_invoice(
                organization, date.today() + timedelta(days=30),
                date.today() + timedelta(days=60))
        finally:
            services.licensing.usage = original_usage

    Invoice.objects.filter(organization=organization).exclude(
        pk__in=[invoice.pk]).update(state=Invoice.VOID)
    under = invoice_for(below)
    check("под порогом объём не тарифицируется",
          under.metered_amount == 0 and under.total == plan.monthly_price,
          f"{under.metered_requests} запросов, {under.total} ₽")
    under.state = Invoice.VOID
    under.save(update_fields=["state"])

    over_invoice = invoice_for(above)
    # Bills the excess ABOVE the floor (the floor is the always-free measurement-noise
    # band), not the whole excess — no cliff at the threshold.
    expected_metered = (Decimal(above - plan.included_requests - plan.metered_floor) / 1000
                        * plan.metered_per_1k)
    check("над порогом появляется отдельная строка объёма",
          over_invoice.metered_amount > 0,
          f"{over_invoice.metered_requests} запросов = {over_invoice.metered_amount} ₽")
    check("и она считается по ставке тарифа, а не на глаз",
          over_invoice.metered_amount == expected_metered.quantize(Decimal("0.01")),
          f"{over_invoice.metered_amount} против ожидаемых {expected_metered}")
    check("итог — абонплата плюс объём, и это видно разложением",
          over_invoice.total == over_invoice.plan_amount + over_invoice.metered_amount,
          f"{over_invoice.plan_amount} + {over_invoice.metered_amount} = {over_invoice.total}")

    # --- 8а. ПРЕДУПРЕЖДЕНИЕ О РАСХОДЕ ПРИХОДИТ ДО СЧЁТА -----------------
    # «Превышение — это счёт, а не рубильник» верно и правильно, но без
    # предупреждения означало «узнаете из письма со счётом», когда обсуждать
    # уже нечего.
    subscription.refresh_from_db()
    subscription.state = Subscription.ACTIVE
    subscription.volume_notified = Subscription.NOTIFIED_NONE
    subscription.save(update_fields=["state", "volume_notified"])
    plan = plans["industrial"]
    # НОВЫЙ ПЕРИОД НАЧИНАЕТСЯ С ВАТЕРМАРКИ ПОСЛЕДНЕГО СЧЁТА, и шаг 8 оставил
    # её выше, чем задаваемая здесь ёмкость — расход вышел бы нулевым, и
    # проверка провалилась бы на арифметике теста, а не на продукте.
    Invoice.objects.filter(organization=organization).update(state=Invoice.VOID)

    original_usage = services.licensing.usage
    def usage_of(capacity):
        return lambda org: {"usage": {"values": capacity, "requests": capacity,
                                      "capacity_billable": capacity}}
    try:
        # ПРИ floor = 0 (наша политика) СТУПЕНИ «included» И «metered» СХЛОПНУТЫ
        # в одну точку: пересечение включённого сразу означает тарификацию,
        # отдельного «пока бесплатно» письма нет. Ступень NOTIFIED_INCLUDED
        # достижима только при floor > 0 — раньше тест ждал именно её и на
        # floor=0 краснел на стенде.
        services.licensing.usage = usage_of(plan.included_requests + 10)
        mail.outbox.clear()
        call_command("run_billing_cycle", verbosity=0)
        subscription.refresh_from_db()
        charged = mail.outbox and str(plan.metered_per_1k) in mail.outbox[0].body
        check("на пересечении включённого сразу приходит письмо о тарификации",
              len(mail.outbox) == 1
              and subscription.volume_notified == Subscription.NOTIFIED_METERED
              and charged,
              mail.outbox[0].subject if mail.outbox else "писем нет")

        # Повтор прохода второго письма не шлёт — цикл идёт каждый час.
        mail.outbox.clear()
        call_command("run_billing_cycle", verbosity=0)
        check("повторный проход письма не повторяет", not mail.outbox,
              f"{len(mail.outbox)} писем")

        check("и обслуживание при этом НЕ остановлено",
              container_masks()[0], "превышение — это счёт, а не рубильник")
    finally:
        services.licensing.usage = original_usage

    # --- 8б. ПРАВКА ТАРИФА НЕ ТРОГАЕТ ДЕЙСТВУЮЩЕГО ПОДПИСЧИКА ------------
    # Это обещание конструктора, и без проверки оно держится на одном
    # присваивании в `build_invoice`. Строку тарифа правим НАСТОЯЩИМ путём —
    # тем же, что и экран консоли, — и требуем, чтобы счёт клиента не сдвинулся.
    subscription.refresh_from_db()
    old_price = subscription.terms["monthly_price"]
    plan_row = Plan.objects.get(code="industrial")
    plan_row.monthly_price = old_price * 2
    plan_row.save(update_fields=["monthly_price"])

    Invoice.objects.filter(organization=organization).update(state=Invoice.VOID)
    mid_period = invoice_for(0)
    check("правка тарифа НЕ переоценивает действующую подписку",
          mid_period.plan_amount == old_price,
          f"было {old_price} ₽, тариф стал {plan_row.monthly_price} ₽, "
          f"в счёте {mid_period.plan_amount} ₽")
    check("и подписка видна как «на прежних условиях»",
          subscription.on_old_terms, str(subscription.terms["source"]))
    mid_period.state = Invoice.VOID
    mid_period.save(update_fields=["state"])

    # А ПРОДЛЕНИЕ — ЕДИНСТВЕННЫЙ МОМЕНТ, КОГДА НОВАЯ ЦЕНА ДОХОДИТ.
    renewal = services.build_invoice(organization, date.today() + timedelta(days=90),
                                     date.today() + timedelta(days=120))
    renewal.state = Invoice.ISSUED
    renewal.save(update_fields=["state"])
    services.mark_paid(renewal, payment_ref="2f8e1c3a-3333-4000-8000-cccccccccccc")
    subscription.refresh_from_db()
    check("после продления условия становятся текущими",
          subscription.terms["monthly_price"] == plan_row.monthly_price
          and not subscription.on_old_terms,
          f"снимок {subscription.terms['monthly_price']} ₽ против "
          f"тарифа {plan_row.monthly_price} ₽")
    plan_row.monthly_price = old_price
    plan_row.save(update_fields=["monthly_price"])

    # --- 9. отмена по концу периода -------------------------------------
    subscription.refresh_from_db()
    subscription.cancel_at_period_end = True
    subscription.current_period_end = timezone.now() - timedelta(minutes=1)
    subscription.state = Subscription.ACTIVE
    subscription.save(update_fields=["cancel_at_period_end", "current_period_end",
                                     "state"])
    before_count = Invoice.objects.filter(organization=organization).count()
    call_command("run_billing_cycle", verbosity=0)
    subscription.refresh_from_db()
    check("отменившему не выставляется следующий счёт",
          Invoice.objects.filter(organization=organization).count() == before_count,
          f"{before_count} шт")
    check("и подписка закрыта",
          subscription.state == Subscription.CANCELLED, subscription.state)

    # --- 10. ПОСЛЕДНИМ: ВОРОНКА ВИДИТ ОСТАНОВЛЕННЫЙ КОНТЕЙНЕР -----------
    # В КОНЦЕ ПРОГОНА, А НЕ В СЕРЕДИНЕ. Здесь останавливается контейнер, и
    # всякая проверка после неё зависела бы от того, успел ли он вернуться:
    # две проверки уже падали не потому, что продукт сломан, а потому что порт
    # ещё не слушал. Ложный красный хуже ложного зелёного тем, что его
    # начинают игнорировать вместе с настоящими.
    #
    # Различающий случай: `instances` считает аренды в текущем окне TTL и у
    # остановленного клиента равен нулю, а вопрос воронки — «поднимал ли
    # КОГДА-НИБУДЬ». У живого контейнера обе метрики дают одно и то же, и
    # разница между верным и неверным сигналом невидима.
    subprocess.run(["docker", "stop", CONTAINER], capture_output=True, timeout=60)
    Funnel.objects.filter(step=Funnel.FIRST_LEASE,
                          organization_id=organization.id).delete()
    time.sleep(stand_ttl(token) + 8)
    call_command("run_billing_cycle", verbosity=0)
    check("воронка видит поднятый контейнер и после его остановки",
          Funnel.objects.filter(step=Funnel.FIRST_LEASE,
                                organization_id=organization.id).exists(),
          "ёмкость выдана и назад не едет, а инстансов сейчас ноль")

    subprocess.run(["docker", "rm", "-f", CONTAINER],
                   capture_output=True, text=True, timeout=60)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    print("жизненный цикл биллинга проходит целиком — счёт, неоплата, остановка "
          "контейнера, оплата, возобновление, объём и отмена")
    return 0


if __name__ == "__main__":
    sys.exit(main())
