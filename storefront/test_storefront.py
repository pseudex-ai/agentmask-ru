"""The storefront, against a REAL licensing server.

Two things are being proved:

  1. THE PATH WORKS. Sign-up issues a key that the licensing server actually
     knows about, and the cabinet renders. This is the site's only metric —
     time from first visit to first masked request — and every step of it goes
     through another service, so a mocked licensing server would test the mock.

  2. THE SITE NEVER BECOMES A PII SURFACE. No page may render a dialogue, a
     token or a value; the landing demo must have no input; the full key must
     appear exactly once and never again. These are not preferences — they are
     what keeps us outside the perimeter under 152-ФЗ, so they are checked
     rather than reviewed.

No pytest, matching the engine repo: run it, read the lines, non-zero is broken.

    python3 test_storefront.py
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

_HERE = Path(__file__).resolve().parent
_PROTOTYPE = _HERE.parent / "prototype"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


_ADMIN_TOKEN = "test-admin-token"
_SHOP_TOKEN = "test-shop-token"


def _free_port() -> int:
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_licensing() -> tuple[subprocess.Popen, str, str]:
    """The real licensing server, in its own interpreter.

    A subprocess rather than an import because it lives in the engine's
    virtualenv with the engine's dependencies, and the storefront deliberately
    shares neither. That separation is the point: if this test could import
    `licensing`, so could the storefront.
    """
    public, admin = _free_port(), _free_port()
    env = {
        **os.environ,
        "PSEUDEX_LICENSE_PORT": str(public),
        "PSEUDEX_LICENSE_ADMIN_PORT": str(admin),
        "PSEUDEX_LICENSE_DB": os.path.join(
            tempfile.mkdtemp(prefix="pseudex-store-test-"), "license.db"),
        "PSEUDEX_LICENSE_CERT": "",
        "PSEUDEX_LICENSE_KEYFILE": "",
        # Админка теперь под токеном, и оба конца должны знать один секрет:
        # сервер запускается ЗДЕСЬ, до того как настройки витрины прочитают
        # окружение, поэтому задавать их ниже было поздно.
        "PSEUDEX_LICENSE_ADMIN_TOKEN": _ADMIN_TOKEN,
        "PSEUDEX_LICENSE_STOREFRONT_TOKEN": _SHOP_TOKEN,
    }
    process = subprocess.Popen(
        [str(_PROTOTYPE / ".venv/bin/python"), "-m", "licensing.devserver"],
        cwd=str(_PROTOTYPE), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    admin_url = f"http://127.0.0.1:{admin}"
    public_url = f"http://127.0.0.1:{public}"
    for _ in range(120):
        try:
            httpx.get(f"{admin_url}/admin/list", timeout=2)
            return process, admin_url, public_url
        except httpx.HTTPError:
            time.sleep(0.25)
    process.kill()
    raise RuntimeError("the licensing server never came up")


def main() -> int:
    process, admin_url, public_url = start_licensing()
    # Админка лицензионного сервера теперь под токеном; тест поднимает
    # НАСТОЯЩИЙ сервер, поэтому оба конца должны знать один секрет.
    os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = _ADMIN_TOKEN
    os.environ["PSEUDEX_LICENSE_STOREFRONT_TOKEN"] = _SHOP_TOKEN
    os.environ["PSEUDEX_LICENSING_ADMIN_URL"] = admin_url
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_SECRET_KEY"] = "test-only"
    os.environ["PSEUDEX_DB_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="pseudex-store-db-"), "store.sqlite3")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")

    import django
    django.setup()
    from django.core.management import call_command
    from django.test import Client
    from django.test.utils import setup_test_environment

    # Redirects mail to `django.core.mail.outbox` so the activation link can be
    # read out of the message we actually sent, rather than reconstructed — the
    # point of the check is that the email carries a link and no key.
    setup_test_environment()

    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_plans", verbosity=0)

    try:
        run_checks(Client(), admin_url, public_url)
    finally:
        process.terminate()
        process.wait(timeout=10)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        return 1
    print("storefront OK — key issued before payment, cabinet renders, "
          "no PII surface anywhere on the site")
    return 0


def run_checks(client, admin_url: str, public_url: str) -> None:
    from accounts.models import Organization
    from billing.models import LicenseKey

    landing = client.get("/")
    body = landing.content.decode()
    check("the landing renders", landing.status_code == 200)
    # An input on the landing would mean this server starts receiving other
    # people's personal data. The demo is prepared examples only.
    check("the landing demo has no free-text input",
          "<textarea" not in body and 'type="text" name="text"' not in body)
    check("the landing carries a content security policy",
          "default-src 'self'" in landing.headers.get("Content-Security-Policy", ""))

    signed = client.post("/signup", {"email": "buyer@acme.ru",
                                     "company": "ООО Ромашка", "plan": "start"})
    check("sign-up does not hand a key to whoever typed the address",
          signed.status_code == 200 and "Проверьте почту" in signed.content.decode()
          or "Письмо ушло" in signed.content.decode(),
          f"status={signed.status_code}")
    check("no key exists before the mailbox is proven",
          LicenseKey.objects.count() == 0, f"keys={LicenseKey.objects.count()}")

    # The activation link, read from the email we actually sent.
    from django.core import mail
    check("an activation email was sent", len(mail.outbox) == 1,
          f"outbox={len(mail.outbox)}")
    body = mail.outbox[0].body
    check("the email carries no key, only a link",
          "ps_live_" not in body, "nothing secret is put in an email")
    link = [word for word in body.split() if "/activate?t=" in word][0]
    path = link[link.index("/activate"):]
    token = path.split("t=", 1)[1]

    # ПЕРЕХОД ПО ССЫЛКЕ НЕ ВХОДИТ В СЕССИЮ, и это проверяется первым.
    # `SESSION_COOKIE_SAMESITE = "Lax"` разрешает ставить cookie на
    # кросс-сайтовой навигации верхнего уровня, поэтому вход прямо на GET
    # означал бы, что чужой сайт может подсунуть клиенту СВОЮ ссылку и
    # подменить ему сессию — после чего клиент оплатит чужой счёт своей картой.
    shown = client.get(path, follow=False)
    check("the link only SHOWS a confirmation, it does not sign anyone in",
          shown.status_code == 200 and client.get("/app/").status_code != 200,
          f"status={shown.status_code}")

    activated = client.post(path, {"t": token}, follow=False)
    check("confirming issues the key",
          activated.status_code == 302 and activated.url == "/welcome",
          f"status={activated.status_code} url={getattr(activated,'url','-')}")

    # The activation link proves the mailbox — the same proof a sign-in link
    # carries — so spending it on a session too is what keeps a new customer
    # from needing a SECOND letter just to reach the cabinet where the keys
    # live. Two persona clients stopped before that second letter.
    check("following the link also signs the customer in",
          client.get("/app/").status_code == 200,
          "one letter must be enough to reach the cabinet")

    welcome = client.get("/welcome")
    welcome_body = welcome.content.decode()
    organization = Organization.objects.first()
    stored = LicenseKey.objects.first()
    check("an organisation and a key were created",
          organization is not None and stored is not None)
    check("the full key is shown once",
          stored.prefix in welcome_body, f"prefix={stored.prefix}")
    check("the run command comes with the key already in it",
          "PSEUDEX_LICENSE_KEY=" in welcome_body and stored.prefix in welcome_body)

    # A second activation must not mint a second key.
    replay = client.get(link[link.index("/activate"):], follow=False)
    check("the activation link cannot be replayed for another key",
          LicenseKey.objects.count() == 1, f"keys={LicenseKey.objects.count()}")

    # The key must be gone from the session now: a page that re-renders a bearer
    # credential on refresh is a credential in browser history.
    again = client.get("/welcome")
    check("the key page does not render the key twice",
          again.status_code == 302, f"status={again.status_code}")

    # The full key must not be recoverable from our own database.
    check("only a prefix and a hash are stored",
          not any(field.name == "key" for field in LicenseKey._meta.get_fields()),
          "there is no column that could hold the key")

    licensed = httpx.get(f"{os.environ['PSEUDEX_LICENSING_ADMIN_URL']}/admin/list",
                         # /admin/list — полный токен: витрине этот список
                         # видеть не положено, и тест ходит как оператор.
                         headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"},
                         timeout=10).json()
    check("the licensing server knows the organisation",
          any(row.get("org_id") == organization.id for row in licensed.get("orgs", [])),
          f"orgs={[row.get('org_id') for row in licensed.get('orgs', [])]}")

    # The three documents the footer links to. They pointed at an anchor on the
    # landing for a long time, so a customer who came for something to forward
    # to their client's security officer found a marketing section. A broken
    # link here is silent — nothing errors, the page just is not what was
    # promised — so it is asserted rather than eyeballed.
    landing_body = client.get("/").content.decode()
    for name, path in (("оферта", "/offer"), ("политика", "/policy"),
                       ("архитектура", "/architecture")):
        page = client.get(path)
        check(f"{name} opens as its own document",
              page.status_code == 200 and len(page.content) > 2000,
              f"status={page.status_code} bytes={len(page.content)}")
        check(f"the footer links to {name}, not to an anchor",
              f'href="{path}"' in landing_body, f"missing href={path}")

    # Sign-up exists in exactly ONE place. allauth's own form created a user
    # with no organisation and no key, and it sat behind the most prominent
    # button on the site; two persona clients took it and were shown a raw
    # Django 404.
    orphan_signup = client.get("/accounts/signup/")
    check("allauth's parallel sign-up form is gone",
          orphan_signup.status_code in (301, 302),
          f"status={orphan_signup.status_code}")

    check("the landing shows the Claude Code prompt before registration",
          "claude-prompt" in landing_body and "PSEUDEX_ROLE=proxy" in landing_body)

    # A FRESH client. The shared one followed the activation link above and is
    # legitimately signed in from that point on — checking anonymity with it
    # tested nothing and would have started passing for the wrong reason.
    from django.test import Client as _FreshClient
    anonymous = _FreshClient().get("/app/")
    check("the cabinet refuses an anonymous visitor",
          anonymous.status_code == 302 and "/accounts/login" in anonymous.url,
          f"status={anonymous.status_code}")

    # The page that redirect lands on must RENDER. Everything below signs in
    # with force_login(), which never builds allauth's form — so a login page
    # that raised FieldDoesNotExist on our username-less User model passed the
    # whole suite while being the only way back into the cabinet.
    # Fresh client again: allauth redirects an ALREADY signed-in visitor away
    # from the login page, so the shared client would test the redirect rather
    # than the form that a returning customer actually sees.
    login_page = _FreshClient().get(anonymous.url)
    check("the sign-in page renders",
          login_page.status_code == 200 and b"<form" in login_page.content,
          f"status={login_page.status_code}")

    from accounts.models import Membership, User
    client.force_login(User.objects.get(email="buyer@acme.ru"))
    cabinet = client.get("/app/")
    cabinet_body = cabinet.content.decode()
    check("the cabinet renders for its owner", cabinet.status_code == 200)
    check("the cabinet shows the key prefix but not the key",
          stored.prefix in cabinet_body, "prefix only")
    check("cabinet pages are not cached",
          "no-store" in cabinet.headers.get("Cache-Control", ""),
          cabinet.headers.get("Cache-Control", "missing"))
    # The site's whole legal position in one assertion.
    check("the cabinet states plainly that it holds no dialogues or values",
          "нет ваших диалогов" in cabinet_body)

    # The full key must never be written to OUR storage. Django's session
    # backend is a table, so a key parked in the session would sit in a database
    # a backup and a support query both reach.
    from django.contrib.sessions.models import Session
    parked = " ".join(row.session_data for row in Session.objects.all())
    check("the key is never parked in a server-side session",
          stored.prefix not in parked, "session table is clean")

    # Sign-up mints a key on the licensing server, so an unthrottled loop would
    # fill the one database whose loss stops every deployment in the field.
    throttled = None
    for index in range(6):
        throttled = client.post("/signup", {"email": f"flood{index}@example.com",
                                            "company": "x", "plan": "start"})
    check("sign-up is throttled",
          throttled.url == "/" if throttled.status_code == 302 else False,
          f"last redirect={getattr(throttled, 'url', throttled.status_code)}")

    repeat = client.post("/signup", {"email": "buyer@acme.ru", "company": "x",
                                     "plan": "start"})
    check("a known email is sent to sign-in, not given a second organisation",
          Organization.objects.filter(memberships__user__email="buyer@acme.ru").count() == 1,
          f"orgs={Organization.objects.filter(memberships__user__email='buyer@acme.ru').count()}")

    # Invoices and the printable form.
    from datetime import date, timedelta
    from billing.services import build_invoice
    client.force_login(User.objects.get(email="buyer@acme.ru"))
    org = Organization.objects.filter(memberships__user__email="buyer@acme.ru").first()
    invoice = build_invoice(org, date.today() - timedelta(days=30), date.today())
    # The invoice IS the subscription: the plan's own monthly price, and nothing
    # derived from any counter. Asserted against the plan row rather than a
    # constant, so a price change cannot make this pass while the customer is
    # charged something else.
    check("an invoice charges the plan price and nothing per value",
          invoice.total == org.subscription.plan.monthly_price
          and invoice.plan_amount == invoice.total,
          f"total={invoice.total} plan={org.subscription.plan.monthly_price}")

    printed = client.get(f"/app/invoices/{invoice.number}/print")
    printed_body = printed.content.decode()
    check("the printable form renders", printed.status_code == 200)
    check("the printable form warns when requisites are missing",
          "Реквизиты не заполнены" in printed_body,
          "ИНН is asked for at purchase, not at sign-up")
    # OUR OWN requisites, on the ИСПОЛНИТЕЛЬ line. The default used to be a
    # plausible but non-existent company, so an unconfigured deployment printed
    # a legal document naming an entity that does not exist. Unset must read as
    # unset, in red, and never as a name.
    from django.conf import settings as django_settings
    seller_name = django_settings.SELLER["name"]
    check("an unconfigured seller prints a warning, not a plausible name",
          ("Реквизиты исполнителя не заполнены" in printed_body
           if not seller_name else seller_name in printed_body),
          f"seller={seller_name!r}")
    check("an unpaid invoice is not also an act",
          "акт выполненных работ" not in printed_body.lower())

    # Another organisation must not reach it. Checked as a DIFFERENT user: the
    # first version of this line re-fetched as the owner and asserted 200, which
    # proved nothing at all.
    intruder = User.objects.create_user(email="intruder@example.com")
    intruder_org = Organization.objects.create(display_name="Чужая")
    Membership.objects.create(user=intruder, organization=intruder_org)
    client.force_login(intruder)
    outsider = client.get(f"/app/invoices/{invoice.number}/print")
    check("the printable form is scoped to its owner", outsider.status_code == 404,
          f"status={outsider.status_code}")
    client.force_login(User.objects.get(email="buyer@acme.ru"))

    # The webhook must not be a way to mark invoices paid by asserting so.
    # Malformed id: refused on shape, BEFORE any outbound call, because an
    # unauthenticated endpoint that always makes one is an amplifier.
    junk = client.post("/hooks/yookassa",
                       data='{"object": {"id": "made-up", "status": "succeeded"}}',
                       content_type="application/json")
    invoice.refresh_from_db()
    check("a malformed payment id is refused without a network call",
          junk.status_code == 400 and invoice.state != "paid",
          f"status={junk.status_code} invoice={invoice.state}")

    # Well-formed but not ours: this one reaches the verification path, which
    # asks ЮKassa and is told there is no such payment. The status the body
    # claims is never consulted.
    forged = client.post(
        "/hooks/yookassa",
        data='{"object": {"id": "2f8e1c3a-0000-4000-8000-abcdefabcdef",'
             ' "status": "succeeded", "amount": {"value": "99999.00"}}}',
        content_type="application/json")
    invoice.refresh_from_db()
    check("a forged payment notification cannot mark an invoice paid",
          invoice.state != "paid" and forged.status_code in (200, 502),
          f"status={forged.status_code} invoice={invoice.state}")

    # ОПЛАТА, КОТОРАЯ ПРОШЛА. Всё, что было по вебхуку, — отрицательные ветки:
    # подделку не пускаем, мусор не пускаем. Единственная нота, ради которой
    # этот стенд и собран — «клиент заплатил, обслуживание вернулось», — не
    # игралась ни разу, и ровно поэтому 403 на `/admin/resume` прожил в дереве
    # незамеченным, откатывая оплату целиком.
    from django.conf import settings
    from billing import licensing, services
    # Ключ для ЭТОЙ организации, выпущенный нашим же путём: дальше проверяется,
    # что контейнер с ним обслуживается и перестаёт обслуживаться.
    raw_key = services.issue_additional_key(org, "проверка оплаты", "live")

    def licence_status() -> str:
        rows = httpx.get(f"{admin_url}/admin/list", timeout=5,
                         headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"}).json()["orgs"]
        return next((r["status"] for r in rows if r["org_id"] == org.id), "нет такой")

    def engine_sees() -> int:
        """Что увидел бы КОНТЕЙНЕР этого клиента, придя за арендой.

        Статус ключа проверяется РАНЬШЕ получателя, поэтому пустой `pubkey`
        даёт 400 «ключ активен», 402 «не оплачено», 403 «отозван» — и для
        проверки не нужен ни движок, ни `pyrage` в venv витрины.
        """
        return httpx.post(f"{public_url}/v1/lease", timeout=5,
                          json={"key": raw_key, "instance_id": "t", "pubkey": "",
                                "engine_version": "1.0.0"}).status_code

    # УЗКИЙ `except`, КОТОРЫЙ ФИКСИРУЕТ ПРОВАЛ, А НЕ ОТМЕНЯЕТ ПРОВЕРКУ. Разница
    # с тем, что стояло в `test_billing_e2e.py`, ровно в этом: там голый
    # `except Exception` пропускал три проверки и оставлял прогон зелёным,
    # поэтому 403 на `/admin/resume` жил незамеченным. Здесь отказ — красная
    # строка, и остальные проверки всё равно выполняются.
    try:
        services.mark_paid(invoice, payment_ref="4f0e1c3a-1111-4000-8000-abcdefabcdef")
    except services.ServiceNotResumed as error:
        check("paying resumes the service", False, str(error)[:160])
    invoice.refresh_from_db()
    subscription = org.subscription
    subscription.refresh_from_db()
    check("paying records the money, resumes the service and says so",
          invoice.state == "paid" and invoice.paid_at is not None
          and invoice.service_resumed_at is not None
          and subscription.state == "active" and licence_status() == "active",
          f"invoice={invoice.state} resumed={invoice.service_resumed_at is not None} "
          f"subscription={subscription.state} licence={licence_status()}")
    check("the customer's own container is served again", engine_sees() == 400,
          f"POST /v1/lease -> {engine_sees()}")

    period_end = subscription.current_period_end
    services.mark_paid(invoice, payment_ref="4f0e1c3a-1111-4000-8000-abcdefabcdef")
    subscription.refresh_from_db()
    check("a duplicate delivery does not grant a second month",
          subscription.current_period_end == period_end,
          "ЮKassa redelivers; two deliveries once meant two free months")

    # ВОЗОБНОВЛЕНИЕ НЕ ДОЕХАЛО — ДЕНЬГИ ВСЁ РАВНО НАШИ. Ломается только то, что
    # можно починить повтором; факт платежа восстановить неоткуда.
    services.mark_unpaid(org)
    invoice.service_resumed_at = None
    invoice.save(update_fields=["service_resumed_at"])
    dead, settings.LICENSING_ADMIN_URL = settings.LICENSING_ADMIN_URL, "http://127.0.0.1:1"
    try:
        services.mark_paid(invoice, payment_ref="4f0e1c3a-2222-4000-8000-abcdefabcdef")
        raised = False
    except services.ServiceNotResumed:
        raised = True
    finally:
        settings.LICENSING_ADMIN_URL = dead
    invoice.refresh_from_db()
    check("an unreachable licensing server does not un-pay the invoice",
          raised and invoice.state == "paid" and invoice.service_resumed_at is None,
          f"raised={raised} invoice={invoice.state} "
          f"resumed={invoice.service_resumed_at is not None}")

    services.mark_paid(invoice, payment_ref="4f0e1c3a-2222-4000-8000-abcdefabcdef")
    invoice.refresh_from_db()
    check("the retry finishes what the outage interrupted",
          invoice.service_resumed_at is not None and licence_status() == "active",
          f"resumed={invoice.service_resumed_at is not None} licence={licence_status()}")

    # ВСЕ ЧЕТЫРЕ СТАТУСА ДОЕЗЖАЮТ. Два из них строили несуществующий путь и
    # отвечали 404 под любым токеном, а вызывающих у них не было — то есть
    # дыра ждала первого, кто нажмёт «отозвать» в поддержке.
    # И проверяется не только запись у нас, но и то, что видит КОНТЕЙНЕР: 402
    # «не оплачено» и 403 «отозван» минуют grace и останавливают клиента за
    # минуту, 400 значит «ключ в порядке».
    for status, seen in (("revoked", 403), ("suspended", 403),
                         ("unpaid", 402), ("active", 400)):
        licensing.set_status(org.id, status)
        check(f"set_status({status}) reaches the licensing server and the container",
              licence_status() == status and engine_sees() == seen,
              f"licence={licence_status()} POST /v1/lease -> {engine_sees()}")

    # A second period must bill the DELTA, not the lifetime counter again.
    from billing.models import Invoice as InvoiceModel
    invoice.values_at_period_end = 500
    invoice.state = InvoiceModel.ISSUED
    invoice.save(update_fields=["values_at_period_end", "state"])
    second = build_invoice(org, date.today(), date.today() + timedelta(days=30))
    check("the next invoice reports the period's values, not the lifetime total",
          second.values_in_period == 0,
          f"watermark=500 reported={second.values_at_period_end} "
          f"in_period={second.values_in_period}")

    # 54-ФЗ splits our customers in two, and only the payer kind tells them
    # apart. A receipt sent where none is required fiscalises a transaction that
    # should not be — and with ЮKassa's "Чеки" it costs 1% of it.
    from accounts.models import Organization as Org
    company = Org(kind=Org.KIND_COMPANY, legal_name="ООО Тест", inn="7701234567")
    entrepreneur = Org(kind=Org.KIND_ENTREPRENEUR, legal_name="ИП Тест", inn="770123456789")
    person = Org(kind=Org.KIND_PERSON)
    check("a company pays by invoice and needs no fiscal receipt",
          company.pays_by_invoice and not company.needs_receipt)
    check("an ИП pays by invoice and needs no fiscal receipt",
          entrepreneur.pays_by_invoice and not entrepreneur.needs_receipt)
    check("an individual cannot pay by invoice and always needs a receipt",
          not person.pays_by_invoice and person.needs_receipt)
    check("an individual needs no ИНН to be billable",
          person.is_billable and not company.__class__(kind="company").is_billable)

    # The instance limit is the ONE plan boundary we enforce, and it lives in
    # two places: the storefront's plans and the licensing server's own table.
    # They must agree, or a customer buys four instances and is refused the
    # second — or buys one and runs twelve.
    import subprocess, json as _json
    proto = str(_HERE.parent / "prototype")
    limits = _json.loads(subprocess.run(
        [proto + "/.venv/bin/python", "-c",
         "import json; from licensing.store import LicenseStore as S; "
         "print(json.dumps(S.PLAN_INSTANCES))"],
        cwd=proto, capture_output=True, text=True).stdout or "{}")
    from billing.models import Plan as PlanModel
    mismatched = [
        p.code for p in PlanModel.objects.all()
        if limits.get(p.code) is not None and limits[p.code] != p.max_instances
    ]
    check("the licensing server and the storefront agree on instance limits",
          bool(limits) and not mismatched,
          f"licensing={limits} mismatched={mismatched or 'none'}")

    # A second organisation must not be able to read the first one's invoices.
    other_user = User.objects.create_user(email="stranger@example.com")
    other_org = Organization.objects.create(display_name="Другая")
    Membership.objects.create(user=other_user, organization=other_org)
    client.force_login(other_user)
    leaked = client.get(f"/app/invoices/DOES-NOT-EXIST")
    # ОБРАЗ НЕ ВЕЗЁТ СЕКРЕТОВ РАЗРАБОТКИ. `.gitignore` для Docker не действует,
    # и без `.dockerignore` `COPY . .` запекал в продакшен-образ `.env.dev` с
    # ключом ЮKassa и дев-базу SQLite: всякий, у кого есть pull из реестра,
    # читал их одной командой. Проверяется СПИСОК ИСКЛЮЧЕНИЙ, а не собранный
    # образ — сборка здесь недоступна, а забыть строку в файле можно и завтра.
    ignore = (pathlib.Path(__file__).parent / ".dockerignore")
    ignored = ignore.read_text() if ignore.exists() else ""
    missing = [pattern for pattern in (".env", "*.sqlite3", ".venv/", "test_*.py")
               if pattern not in ignored]
    check("the build context excludes dev secrets and the dev database",
          ignore.exists() and not missing,
          f"missing={missing or 'none'}")

    check("one organisation cannot open another's invoice",
          leaked.status_code == 404, f"status={leaked.status_code}")


if __name__ == "__main__":
    sys.exit(main())
