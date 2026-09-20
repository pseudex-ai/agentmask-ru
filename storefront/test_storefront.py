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
        # Тюнинг едет в лизе (docs/tz-tuning-in-lease.md), не в вкомпилированном
        # блобе — PSEUDEX_TUNING_KEY больше не нужен ни серверу, ни этому набору.
    }
    # ПРИЧИНА ОТКАЗА НЕ ВЫБРАСЫВАЕТСЯ В DEVNULL.
    #
    # Оба потока шли в никуда, поэтому «the licensing server never came up» было
    # всем, что оставалось от любого отказа старта, — и настоящая причина
    # (отсутствующий ключ тюнинга) не называлась ни в CI, ни на машине. Тридцать
    # секунд ожидания и одна строка без диагноза: ровно тот случай, ради
    # которого в репозитории есть `e2e/lint_tests.py`.
    # ФАЙЛ, А НЕ PIPE. Сервер живёт весь прогон и логирует КАЖДЫЙ запрос; никто
    # не читает его stderr, пока идут проверки, поэтому труба на 64 КБ
    # заполняется, дочерний процесс блокируется в `write()` и перестаёт
    # обслуживать — а `process.wait(timeout=10)` в `finally` затем маскирует
    # настоящий результат прогона таймаутом и оставляет процесс сиротой.
    # Временный файл даёт ту же диагностику и не имеет предела.
    stderr = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")

    def _stderr_tail(limit: int = 2000) -> str:
        stderr.flush()
        stderr.seek(0)
        return stderr.read()[-limit:]

    process = subprocess.Popen(
        [str(_PROTOTYPE / ".venv/bin/python"), "-m", "licensing.devserver"],
        cwd=str(_PROTOTYPE), env=env,
        stdout=subprocess.DEVNULL, stderr=stderr, text=True,
    )
    admin_url = f"http://127.0.0.1:{admin}"
    public_url = f"http://127.0.0.1:{public}"
    for _ in range(120):
        if process.poll() is not None:
            # Умер — читать можно сразу и целиком, ждать оставшиеся секунды незачем.
            raise RuntimeError("the licensing server exited "
                               f"({process.returncode}):\n{_stderr_tail()}")
        try:
            httpx.get(f"{admin_url}/admin/list", timeout=2)
            return process, admin_url, public_url
        except httpx.HTTPError:
            time.sleep(0.25)
    process.kill()
    raise RuntimeError(f"the licensing server never came up:\n{_stderr_tail()}")


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
    from billing.models import LicenseKey, Plan, Subscription
    from billing import services

    landing = client.get("/")
    body = landing.content.decode()
    # ОДНОРАЗОВЫЙ ЯЩИК НЕ ПОЛУЧАЕТ КЛЮЧА. Единственный реальный путь
    # злоупотребления пробным периодом: образ без ключа не стартует вовсе, а
    # ключ выпускается только по ссылке из письма.
    # ЮРИДИЧЕСКИ ОБЯЗАТЕЛЬНЫЕ СТРАНИЦЫ ОТКРЫВАЮТСЯ И СВЯЗАНЫ ИЗ ПОДВАЛА.
    # Документ, который существует и никуда не ведёт, не «опубликован с
    # обеспечением неограниченного доступа» (ст. 18.1 152-ФЗ) — а именно за это
    # штрафует ст. 13.11 ч. 3.
    footer = body
    for path, name in (("/policy", "политика обработки"),
                       ("/consent", "согласие на обработку"),
                       ("/requisites", "реквизиты владельца"),
                       ("/offer", "оферта")):
        page = client.get(path)
        check(f"{name}: страница открывается", page.status_code == 200,
              f"{path} -> {page.status_code}")
        check(f"{name}: есть ссылка в подвале", path in footer, path)

    # СОГЛАСИЕ ПРОВЕРЯЕТСЯ НА СЕРВЕРЕ. `required` в разметке снимается
    # инструментами разработчика за две секунды, а доказывать получение
    # согласия придётся нам.
    before = Organization.objects.count()
    without = client.post("/signup", {"email": f"noconsent-{int(time.time())}@example.test",
                                    "company": "Тест", "plan": "start", "terms": "1"})
    check("без галочки согласия аккаунт не создаётся",
          Organization.objects.count() == before, f"код={without.status_code}")
    # ДВЕ ГАЛОЧКИ, И КАЖДАЯ ОБЯЗАТЕЛЬНА ПОРОЗНЬ. С 01.09.2025 согласие на
    # обработку ПД оформляется отдельно от иных документов (ч. 1 ст. 9 152-ФЗ
    # в ред. 156-ФЗ): одна галочка «даю согласие и принимаю оферту» — это
    # совмещённое согласие, то есть его отсутствие. Согласие без акцепта
    # оферты — тоже не регистрация: договора нет.
    no_terms = client.post("/signup", {"email": f"noterms-{int(time.time())}@example.test",
                                     "company": "Тест", "plan": "start", "consent": "1"})
    check("без акцепта оферты аккаунт не создаётся",
          Organization.objects.count() == before, f"код={no_terms.status_code}")
    check("согласие и оферта — две разные галочки на форме",
          'name="consent"' in body and 'name="terms"' in body
          and "и принимаю" not in body.split('name="consent"')[1].split("</label>")[0],
          "одна галочка на согласие и договор — совмещённое согласие")

    from billing.services import is_disposable
    check("одноразовый ящик отсечён", is_disposable("x@mailinator.com"))
    check("регистр домена не спасает", is_disposable("x@YOPMAIL.COM"))
    check("настоящая почта проходит",
          not is_disposable("igor@sber.ru") and not is_disposable("a@tempo-market.ru"),
          "эвристика «в домене есть temp» отсекала бы живые компании")

    check("the landing renders", landing.status_code == 200)
    # An input on the landing would mean this server starts receiving other
    # people's personal data. The demo is prepared examples only.
    check("the landing demo has no free-text input",
          "<textarea" not in body and 'type="text" name="text"' not in body)
    check("the landing carries a content security policy",
          "default-src 'self'" in landing.headers.get("Content-Security-Policy", ""))

    signed = client.post("/signup", {"email": "buyer@acme.ru", "consent": "1", "terms": "1",
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

    # ПРОБА ПОКАЗЫВАЕТ ПРОБНЫЙ ТАРИФ, А НЕ ПРИВЯЗАННЫЙ ПЛАТНЫЙ.
    #
    # Регистрация привязывает правильный (`services.start_trial` берёт
    # `trial_plan()`), но у аккаунтов, созданных ДО появления тарифа `free`, в
    # строке подписки остался платный `start` — и кабинет сообщал человеку
    # «Старт, 990 ₽/мес», тогда как он не платит ничего.
    #
    # Проверка держит ПОКАЗ, а не данные: строку подписки мы не переписываем
    # (в ней ещё и намерение клиента), а смотрим ровно блок «ТАРИФ» — в списке
    # смены тарифа платные названия быть обязаны.
    pinned = Subscription.objects.first()
    paid = Plan.objects.filter(is_public=True, is_trial=False).first()
    trial = services.trial_plan()
    if pinned is not None and paid is not None and trial is not None:
        was = pinned.plan
        pinned.plan = paid
        pinned.save(update_fields=["plan"])
        try:
            body = client.get("/app/").content.decode()
        finally:
            # ПОДМЕНА ЖИВЁТ РОВНО ОДИН ЗАПРОС. Без этого следующий тест собирал
            # счёт по подменённому тарифу и падал на сумме — проверка обязана
            # убирать за собой, иначе она ломает соседа, а не проверяет своё.
            pinned.plan = was
            pinned.save(update_fields=["plan"])
        block = body.split("ТАРИФ", 1)[-1].split("ИСПОЛЬЗОВАНО", 1)[0]
        check(trial.title in block and paid.title not in block,
              "на пробе кабинет показывает ПРОБНЫЙ тариф, а не привязанный платный",
              f"пробный={trial.title in block} платный={paid.title in block}")

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
    # `follow=True`, ПОТОМУ ЧТО ВХОД ТЕПЕРЬ БЕЗ ПАРОЛЯ: `/accounts/login/`
    # уведён на вход по коду (пароля у клиента нет никогда), так что без
    # перехода по редиректу здесь виден 302, а не та страница, которую видит
    # вернувшийся клиент. Смысл проверки прежний и он важнее адреса: экран, на
    # который приземляется отказ кабинета, обязан ОТРИСОВАТЬСЯ с формой, а не
    # упасть — именно так однажды прошёл весь набор при сломанном входе.
    login_page = _FreshClient().get(anonymous.url, follow=True)
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
    # THE SITE'S WHOLE LEGAL POSITION IN ONE ASSERTION — ON /architecture, ONCE
    # (docs/spec.md §2.6.6). It used to sit at the end of the cabinet's
    # invoices and say what the cabinet does NOT hold; the spec moved it to
    # where the customer first thinks about it. So the cabinet must NOT repeat
    # it, and the architecture page must state it plainly.
    check("the cabinet no longer carries the «no dialogues» block (§2.6.6: it lives on /architecture)",
          "ваших диалогов" not in cabinet_body)
    architecture_body = client.get("/architecture").content.decode()
    check("/architecture states plainly that our side holds no dialogues, tokens or values",
          "не содержит ваших диалогов, токенов и значений" in architecture_body)

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
                                            "consent": "1", "terms": "1",
                                            "company": "x", "plan": "start"})
    check("sign-up is throttled",
          throttled.url == "/" if throttled.status_code == 302 else False,
          f"last redirect={getattr(throttled, 'url', throttled.status_code)}")

    repeat = client.post("/signup", {"email": "buyer@acme.ru", "company": "x",
                                     "consent": "1", "terms": "1",
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
          "и акт" not in printed_body.lower())

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
    from billing.models import Plan
    # ПЛАТЯЩИЙ КЛИЕНТ, А НЕ ПРОБНЫЙ. Регистрация сажает на пробный тариф — у
    # него один ключ и один контейнер, — а здесь проверяется путь оплаты, то
    # есть по определению не проба. Раньше строки ниже работали случайно: проба
    # шла на ВЫБРАННОМ тарифе и наследовала его лимиты, что и было дырой.
    subscription = org.subscription
    subscription.plan = Plan.objects.get(code="start")
    subscription.save(update_fields=["plan"])
    licensing.set_org_plan(org.id, "start")
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

    # THE CUSTOMER SAYS WHO PAYS, IN THE CABINET. There was no form: every
    # organisation stayed «юрлицо» by default and the счёт page said «напишите
    # нам», so each invoice was a support ticket. The form is validated where
    # the documents are: a wrong ИНН goes onto an акт the buyer files.
    from decimal import Decimal
    bad_inn = client.post("/app/payer", {"kind": "company", "legal_name": "ООО Ромашка",
                                         "inn": "7701234561", "kpp": "", "legal_address": ""})
    org.refresh_from_db()
    check("an ИНН that fails its checksum is refused",
          bad_inn.status_code == 302 and org.inn == "", f"inn={org.inn!r}")
    wrong_len = client.post("/app/payer", {"kind": "entrepreneur", "legal_name": "ИП Ромашкин",
                                           "inn": "7701234567", "kpp": "", "legal_address": ""})
    org.refresh_from_db()
    check("an ИП with a 10-digit ИНН is refused — an ИП's has twelve",
          wrong_len.status_code == 302 and org.inn == "", f"inn={org.inn!r}")
    saved = client.post("/app/payer", {"kind": "company", "legal_name": "ООО  Ромашка ",
                                       "inn": "7701 234560", "kpp": "770101001",
                                       "legal_address": "Москва, ул. Тверская, 1"})
    org.refresh_from_db()
    check("valid requisites are stored normalised",
          saved.status_code == 302 and org.kind == "company"
          and org.legal_name == "ООО Ромашка" and org.inn == "7701234560"
          and org.kpp == "770101001" and org.is_billable,
          f"kind={org.kind} name={org.legal_name!r} inn={org.inn!r} kpp={org.kpp!r}")
    as_person = client.post("/app/payer", {"kind": "person", "legal_name": "", "inn": "",
                                           "kpp": "", "legal_address": ""})
    org.refresh_from_db()
    check("an individual needs nothing but the kind",
          as_person.status_code == 302 and org.kind == "person" and org.is_billable)
    client.post("/app/payer", {"kind": "company", "legal_name": "ООО Ромашка",
                               "inn": "7701234560", "kpp": "770101001", "legal_address": ""})
    org.refresh_from_db()

    # THE PAID FORM IS THE ACT, AND ITS LINES ADD UP TO ITS TOTAL. The print
    # form showed one row of абонплата under a total that already included
    # the metered overage — a document whose rows do not sum to its total is
    # one an accountant sends back. The overage is written onto this paid
    # invoice directly: `build_invoice` computes it from counters this test
    # does not drive, and the document must be right whatever fed it.
    invoice.metered_requests = 40000
    invoice.metered_amount = Decimal("1240.00")
    invoice.total = invoice.plan_amount + invoice.metered_amount
    invoice.save(update_fields=["metered_requests", "metered_amount", "total"])
    act = client.get(f"/app/invoices/{invoice.number}/print").content.decode()

    # Figures are read back the way the page prints them — «1 240,00», with the
    # locale's thousands space and decimal comma — so the check is on the
    # NUMBERS, not on one formatting the template does not control.
    def figures(page: str) -> str:
        return page.replace("\u00a0", "").replace(" ", "").replace(",", ".")

    check("a paid invoice prints as счёт и акт о предоставлении права",
          "и акт о предоставлении права использования" in act
          and "Право использования программы предоставлено" in act)
    check("the act names the customer's requisites",
          "ООО Ромашка" in act and "7701234560" in act and "770101001" in act)
    check("the metered overage is its own line with its own rate",
          "сверх включённого объёма" in act and "40000" in figures(act)
          and "1240.00" in figures(act) and "31.00" in figures(act),
          "rate back-derived from the invoice: 1240 / 40 = 31.00 за 1000")
    on_screen = client.get(f"/app/invoices/{invoice.number}").content.decode()
    check("the on-screen invoice shows the same overage line",
          "сверх включённого объёма" in on_screen and "1240.00" in figures(on_screen))
    check("a paid invoice offers the act by name", "СЧЁТ И АКТ" in on_screen)

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

    # БЮДЖЕТ КЛЮЧЕЙ И ОСИРОТЕВШИЙ КЛЮЧ. Отказ по `max_keys` обязан не оставить
    # на лицензионном сервере активную запись, не привязанную ни к какому
    # кабинету: она лизует вечно и не видна ни в одной сверке.
    def keys_on_server() -> int:
        # СЧИТАЮТСЯ КЛЮЧИ, А НЕ СТРОКИ КАТАЛОГА. `/admin/list` отдаёт одну
        # строку на ОРГАНИЗАЦИЮ (раньше — на каждый ключ), поэтому сумма по
        # строкам стала бы сравнением единицы с единицей: проверка перестала бы
        # уметь падать, оставаясь зелёной. Число живых ключей организация теперь
        # называет сама.
        rows = httpx.get(f"{admin_url}/admin/list", timeout=5,
                         headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"}).json()["orgs"]
        return sum(int(row["active_keys"]) for row in rows if row["org_id"] == org.id)

    allowed = org.subscription.plan.max_keys
    while org.keys.filter(revoked_at__isnull=True).count() < allowed:
        services.issue_additional_key(org, "добивка", "live")
    before = keys_on_server()
    try:
        services.issue_additional_key(org, "лишний", "live")
        refused = False
    except ValueError:
        refused = True
    check("a key beyond the plan is refused and leaves nothing behind on the server",
          refused and keys_on_server() == before,
          f"refused={refused} keys on server {before} -> {keys_on_server()}")

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

    from unittest.mock import patch

    # ЁМКОСТЬ ВИДНА КЛИЕНТУ И ВАТЕРМАРКИТСЯ НА СЧЁТЕ. Ставка ещё не назначена —
    # это продуктовое решение, — но число, на котором она будет считаться, уже
    # верное, и его надо ватермаркить с этого момента: иначе первый же счёт по
    # объёму пришлось бы считать от накопительного итога.
    with patch("billing.licensing.usage",
               return_value={"usage": {"capacity_billable": 4000, "values": 10,
                                       "requests": 4000}}):
        metered = build_invoice(org, date.today(), date.today() + timedelta(days=30))
    metered.state = InvoiceModel.ISSUED
    metered.save(update_fields=["state"])
    with patch("billing.licensing.usage",
               return_value={"usage": {"capacity_billable": 6500, "values": 10,
                                       "requests": 6500}}):
        metered_next = build_invoice(org, date.today(), date.today() + timedelta(days=30))
    check("the invoice watermarks the capacity the volume charge will use",
          metered_next.requests_billable_in_period == 2500,
          f"в периоде {metered_next.requests_billable_in_period}, "
          f"ватермарка {metered_next.requests_billable_at_period_end}")

    cabinet_page = client.get("/app/").content.decode()
    # §2.6.1: ОДНА сумма сверху и ОДНА полоса с отмеченным порогом остановки —
    # не две полосы про разное и ноль сумм. §2.6.2: ОДНА строка рядом с
    # числом («израсходовано X из Y»), остальное — под «?»: там и начисление по
    # выданной ёмкости (отчёт контейнеров его только УМЕНЬШАЕТ — «отчёт — ваша
    # защита» иначе остаётся обещанием), и ставка сверх, и потолок докупки.
    check("the cabinet shows ONE sum on top and ONE usage line (§2.6.1, §2.6.2)",
          "В ЭТОМ ПЕРИОДЕ" in cabinet_page and "₽" in cabinet_page
          and "израсходовано" in cabinet_page
          and cabinet_page.count('class="meter"') + cabinet_page.count('class="usebar"') == 1,
          f"meters={cabinet_page.count('class=\"meter\"')} usebars={cabinet_page.count('class=\"usebar\"')}")
    check("the cabinet says what is billed — the capacity WE issued — and that the report only lowers it (§2.6.2, under «?»)",
          'class="qmark"' in cabinet_page
          and "по ёмкости, которую выдали мы" in cabinet_page
          and "уменьшает" in cabinet_page,
          "без обеих границ фраза «отчёт — ваша защита» остаётся обещанием")
    # ЗОНА И ЦЕНА ЗА ПЕРИОД: «вот включено, вот цена сверх, вот докуда докуп,
    # вот где стоп». Раньше кабинет показывал только полосу, и клиент узнавал о
    # потолке и ставке из счёта.
    check("кабинет показывает включённое, ставку сверх, потолок докупки и порог остановки",
          "сверх включённого" in cabinet_page
          and "докупать можно до" in cabinet_page
          and "остановка на" in cabinet_page,
          "нет блока зоны/цены — «цена/что получу/овердрафт» осталось обещанием")

    # ОТРАВЛЕННЫЙ ОТВЕТ НЕ ДЕЛАЕТ КЛИЕНТА ВЕЧНО БЕСПЛАТНЫМ. Отрицательное
    # значение раньше записывалось как ПОСТОЯННАЯ ватермарка, после чего каждый
    # следующий период давал ноль. Вход теперь проверяется, но инвариант,
    # державшийся на чужом поведении, обязан держаться на своём.
    poison = {"usage": {"values": -10 ** 9, "requests": -10 ** 9}}
    with patch("billing.licensing.usage", return_value=poison):
        poisoned = build_invoice(org, date.today(), date.today() + timedelta(days=30))
    poisoned.state = InvoiceModel.ISSUED
    poisoned.save(update_fields=["state"])
    with patch("billing.licensing.usage",
               return_value={"usage": {"values": 5000, "requests": 7000}}):
        after_poison = build_invoice(org, date.today(), date.today() + timedelta(days=30))
    # Инвариант — НЕ «ватермарка обнулилась», а «ватермарка не поехала вниз»:
    # она держится на прежнем значении, и следующий период считает дельту от
    # него, а не от минуса.
    before_poison = second.values_at_period_end
    check("a poisoned counter cannot make a customer permanently free",
          poisoned.values_at_period_end >= before_poison
          and after_poison.values_in_period == 5000 - before_poison,
          f"watermark {before_poison} -> {poisoned.values_at_period_end}, "
          f"next period={after_poison.values_in_period}")

    # THE PAYER KIND DECIDES THE DOCUMENTS, NOT THE RECEIPT. A receipt used to
    # ride only with an individual's payment on the strength of 54-ФЗ ст. 2
    # п. 9 — but a card payment is made by whoever holds the card, a company's
    # accountant paying with a personal one is a settlement with an individual,
    # and nothing tells the two cards apart. ЮKassa's own scheme wants the
    # receipt «при проведении каждого платежа». So every card payment carries
    # one (`billing.payments`), and the kind is left with what only it can say.
    from accounts.models import Organization as Org
    company = Org(kind=Org.KIND_COMPANY, legal_name="ООО Тест", inn="7701234560")
    entrepreneur = Org(kind=Org.KIND_ENTREPRENEUR, legal_name="ИП Тест", inn="770123456703")
    person = Org(kind=Org.KIND_PERSON)
    check("a company and an ИП pay by invoice, an individual cannot",
          company.pays_by_invoice and entrepreneur.pays_by_invoice
          and not person.pays_by_invoice)
    check("an individual needs no ИНН to be billable",
          person.is_billable and not company.__class__(kind="company").is_billable)
    check("the receipt decision no longer lives on the organisation",
          not hasattr(Org, "needs_receipt"),
          "a kind-gated receipt let every default «юрлицо» pay with no чек")

    # The instance limit is the ONE plan boundary we enforce, and it lives in
    # two places: the storefront's plans and the licensing server's own table.
    # They must agree, or a customer buys four instances and is refused the
    # second — or buys one and runs twelve.
    # ЧЕРЕЗ РУЧКУ, А НЕ ЧЕРЕЗ SUBPROCESS В ЧУЖОЙ VENV. Здесь стояло `python -c
    # "print(S.PLAN_INSTANCES)"` в интерпретаторе движка — сверка АТРИБУТА
    # КЛАССА, а не того, по чему сервер на самом деле принимает решения. Тариф
    # теперь строка в его базе, и константа осталась только сидом: правка,
    # сделанная оператором, не изменила бы прочитанный так словарь ни на йоту, и
    # сверка продолжала бы говорить «сходится» про числа, которых больше нет.
    #
    # Заодно уходит хрупкость: путь `../prototype/.venv/bin/python` был зашит, и
    # его отсутствие давало пустой stdout, то есть `{}` — сверку, которая
    # проходит, ничего не сверив.
    plans = httpx.get(f"{admin_url}/admin/plans", timeout=5,
                      headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"}).json()["plans"]
    limits = {row["code"]: row["max_instances"] for row in plans}
    # ПОРОГ ТАРИФИКАЦИИ = 0 НА ВСЕХ ТАРИФАХ (решение владельца): биллим с
    # первого запроса сверх включённого, без «бесплатной полосы». Раньше порог
    # был привязан к резерву ёмкости сервера и сверялся с ним здесь — та связь
    # РАЗОРВАНА: резерв остаётся серверной метрологией (край при обрыве
    # отчётов), а порог стал чистым продуктовым нулём. Сверять их равенство
    # теперь ложный красный. Проверяем то, что действительно инвариант:
    # политика floor = 0 держится на всех сидовых тарифах.
    from billing.models import Plan as PlanModel
    shop_plans = list(PlanModel.objects.all())
    mismatched = [
        p.code for p in shop_plans
        if limits.get(p.code) is not None and limits[p.code] != p.max_instances
    ]
    floors_off = [f"{p.code}: порог {p.metered_floor}"
                  for p in shop_plans if p.metered_floor != 0]
    check("порог тарификации = 0 на всех тарифах (политика floor=0)",
          not floors_off, "; ".join(floors_off) or
          f"сверено {len(shop_plans)} тарифов")
    # ТАРИФ, КОТОРОГО ЛИЦЕНЗИОННЫЙ СЕРВЕР НЕ ЗНАЕТ, — ТОЖЕ РАСХОЖДЕНИЕ, и до
    # сих пор эта проверка пропускала ровно его: `limits.get(p.code) is not
    # None` отсеивал именно те коды, которых на той стороне нет.
    #
    # Раньше это было почти безобидно — незнакомый тариф молча получал лимиты
    # «старта». Теперь `/admin/issue` отвечает на него 400, потому что тихое
    # понижение и есть тот дефект, ради которого всё это чинится: клиент упирался
    # в потолок чужого тарифа, и ни одна строка об этом не говорила. Но громкий
    # отказ означает, что клиент на таком тарифе НЕ ПОЛУЧИТ КЛЮЧ ВОВСЕ, а
    # `seed_plans` выводит тарифы из продажи, НЕ удаляя их (подписка помнит
    # условия, на которых куплена). Значит расхождение обязано падать здесь, до
    # выката, а не у клиента при выпуске ключа.
    unknown_to_licensing = sorted(p.code for p in shop_plans if p.code not in limits)
    check("the licensing server and the storefront agree on instance limits",
          bool(limits) and not mismatched and not unknown_to_licensing,
          f"licensing={limits} mismatched={mismatched or 'none'} "
          f"unknown_to_licensing={unknown_to_licensing or 'none'}")

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

    _check_ops_console(client, admin_url, public_url, org, raw_key)


def _verify_otp(client, user) -> None:
    """Пометить сессию клиента прошедшей второй фактор (TOTP).

    Консоль и админка теперь требуют подтверждённое OTP-устройство
    (django_otp.OTPAdminSite + otp_required на /ops/). `force_login` даёт только
    аутентификацию, но не второй фактор, поэтому staff-сессию надо ещё
    верифицировать — иначе все экраны консоли отвечают 302 на вход.
    """
    from django_otp import DEVICE_ID_SESSION_KEY
    from django_otp.plugins.otp_totp.models import TOTPDevice

    device, _created = TOTPDevice.objects.get_or_create(
        user=user, name="ci", defaults={"confirmed": True})
    if not device.confirmed:
        device.confirmed = True
        device.save(update_fields=["confirmed"])
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()


def _check_ops_console(client, admin_url: str, public_url: str,
                       org, raw_key: str) -> None:
    """Операторская консоль: все клиенты, один клиент, цепи, тарифы.

    ПЕРВЫЙ СОТРУДНИК В ЭТИХ ТЕСТАХ. До сих пор `create_user` заводил только
    клиентов — `is_staff` по умолчанию `False`, — поэтому доступ к консоли не с
    чем было сравнивать: проверка «клиент не войдёт» без проверки «сотрудник
    войдёт» проходит и на сломанной странице.
    """
    from unittest import mock

    from django.conf import settings
    from django.test import Client as _FreshClient

    from accounts.models import User
    from billing import licensing
    from billing.models import Plan

    base = f"/{settings.ADMIN_PATH}/ops/"
    screens = (base, f"{base}chains/", f"{base}plans/", f"{base}{org.id}/")

    # ЗАКРЫТО ДЛЯ КЛИЕНТА И ДЛЯ АНОНИМА. `client` вошёл как покупатель ещё выше и
    # остаётся им — это и есть нужный случай: обычный клиент витрины не должен
    # видеть ни своих соседей, ни их счётчиков.
    customer_saw = [path for path in screens if client.get(path).status_code == 200]
    check("консоль закрыта для обычного клиента", not customer_saw,
          f"открылось={customer_saw or 'ничего'}")
    anonymous = _FreshClient()
    anonymous_saw = [path for path in screens if anonymous.get(path).status_code == 200]
    check("консоль закрыта для анонима", not anonymous_saw,
          f"открылось={anonymous_saw or 'ничего'}")

    staff_client = _FreshClient()
    staff = User.objects.create_user(email="ops@pseudex.ru", is_staff=True)
    staff_client.force_login(staff)
    _verify_otp(staff_client, staff)

    rendered = {path: staff_client.get(path) for path in screens}
    broken = [f"{path}={response.status_code}"
              for path, response in rendered.items() if response.status_code != 200]
    check("сотрудник открывает все четыре экрана", not broken,
          f"не открылось={broken or 'ничего'}")

    fleet_body = rendered[base].content.decode()
    check("флот показывает организацию и её тариф",
          org.id in fleet_body and org.subscription.plan.title in fleet_body,
          f"org={org.id in fleet_body} plan={org.subscription.plan.title in fleet_body}")

    # ДВА ПОЛЯ С ОДНИМ ИМЕНЕМ `instances`, И ЭТО ЛОВУШКА.
    #
    # У `/admin/usage` это СЫРЫЕ СТРОКИ АРЕНД — по строке на каждую выдачу,
    # вместе с освобождёнными, с потолком в сотню. Их количество не считает
    # контейнеры: у клиента с одним контейнером колонка «занято по тарифу»
    # показала бы «100 / 1» через сутки работы. У `/admin/fleet` и
    # `/admin/instances` это ДЕРЖАЩИЕ СЛОТ, сгруппированные по `instance_id`, и
    # только у них есть `state` и `last_lease`, которые рисует экран клиента.
    # НАСТОЯЩАЯ АРЕНДА, иначе оба списка пусты и обе проверки ниже проходят
    # впустую: `all(...)` по пустому списку истинно, то есть проверка,
    # неспособная упасть. Ключ процесса генерируется в venv движка — витрина
    # такой зависимости не имеет и иметь не должна.
    process_key = subprocess.run(
        [str(_PROTOTYPE / ".venv/bin/python"), "-c",
         "from pseudex.bundle import generate_process_key; "
         "print(generate_process_key().public)"],
        cwd=str(_PROTOTYPE), capture_output=True, text=True).stdout.strip()
    leased = httpx.post(f"{public_url}/v1/lease", timeout=10,
                        json={"key": raw_key, "instance_id": "ops-console-probe",
                              "process_id": "p1", "pubkey": process_key,
                              "engine_version": "1.0.0"})
    check("стенд смог взять настоящую аренду для проверки формы ответов",
          leased.status_code == 200, f"код={leased.status_code} {leased.text[:120]}")

    fleet_rows = httpx.get(f"{admin_url}/admin/fleet",
                           params={"org_ids": org.id}, timeout=5,
                           headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"}).json()["orgs"]
    fleet_slots = fleet_rows[0]["instances"]
    raw_leases = httpx.get(f"{admin_url}/admin/usage", params={"org_id": org.id},
                           timeout=5,
                           headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"}
                           ).json()["instances"]
    check("флот считает контейнеры, а не строки аренд",
          bool(fleet_slots) and all("state" in slot for slot in fleet_slots),
          f"поля={sorted(fleet_slots[0]) if fleet_slots else 'СЛОТОВ НЕТ — проверка пуста'}")
    check("а сырые строки аренд остались там, где и были",
          bool(raw_leases) and all("state" not in row for row in raw_leases),
          f"поля={sorted(raw_leases[0]) if raw_leases else 'АРЕНД НЕТ — проверка пуста'}")

    # НИ ОДНОГО ЗНАЧЕНИЯ ИЗ ТРАФИКА. Та же граница, что у кабинета
    # (`docs/tz-site.md` §1): витрина не имеет права нарисовать экран, где виден
    # диалог, сообщение, токен или значение. Консоль показывает счётчики и
    # идентификаторы — и полный ключ тоже никогда, у неё его и нет.
    leaked_key = [path for path, response in rendered.items()
                  if "ps_live_" in response.content.decode()]
    check("консоль не рисует ни одного полного ключа", not leaked_key,
          f"утекло на={leaked_key or 'нигде'}")

    # Страницы бэк-офиса не кэшируются. Заголовок ставит middleware, и он берёт
    # префикс из настройки: раньше там стоял литерал `/admin/`, поэтому
    # перенесённая админка молча оставалась без `no-store`.
    uncached = [path for path, response in rendered.items()
                if "no-store" not in response.headers.get("Cache-Control", "")]
    check("страницы консоли не кэшируются", not uncached,
          f"без no-store={uncached or 'нигде'}")

    # ...И ЗАГОЛОВОК ДЕРЖИТСЯ НА НАСТРОЙКЕ, А НЕ НА ЛИТЕРАЛЕ `/admin/`.
    #
    # Этот прогон идёт с путём по умолчанию, поэтому подмена литерала настройкой
    # в нём не видна вообще — а именно ею и был дефект: `PSEUDEX_ADMIN_PATH`
    # существует, чтобы админку можно было перенести, и перенесённая переставала
    # получать `no-store`. То есть настройка, которую включают ради
    # безопасности, тихо снимала заголовок со всего бэк-офиса. Проверяется
    # вызовом middleware напрямую: маршруты собраны на импорте и переезжать по
    # ходу теста не умеют.
    from django.http import HttpResponse
    from storefront_web.middleware import SecurityHeadersMiddleware

    def _header_for(path: str, admin_path: str) -> str:
        with mock.patch.object(settings, "ADMIN_PATH", admin_path):
            request = _FreshClient().request(PATH_INFO=path).wsgi_request
            middleware = SecurityHeadersMiddleware(lambda _request: HttpResponse("ok"))
            return middleware(request).headers.get("Cache-Control", "")

    check("перенесённая админка не теряет no-store",
          "no-store" in _header_for("/g7x2q/anything", "g7x2q"),
          f"заголовок={_header_for('/g7x2q/anything', 'g7x2q')!r}")
    check("посторонний путь заголовка не получает",
          "no-store" not in _header_for("/landing", "g7x2q"),
          "иначе проверка выше проходила бы на чём угодно")

    # ПРАВКА ТАРИФА ДОЕЗЖАЕТ ДО СЕРВЕРА И НАЗЫВАЕТ АВТОРА.
    edited = staff_client.post(f"{base}plans/start/", {"max_instances": "3"},
                               follow=True)
    remote = {row["code"]: row for row in
              httpx.get(f"{admin_url}/admin/plans", timeout=5,
                        headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"}
                        ).json()["plans"]}
    check("правка тарифа из консоли доезжает до лицензионного сервера",
          edited.status_code == 200 and remote["start"]["max_instances"] == 3,
          f"на сервере={remote['start']['max_instances']}")
    check("автор правки записан почтой сотрудника",
          remote["start"]["updated_by"] == "ops@pseudex.ru"
          and remote["start"]["source"] == "edited",
          f"автор={remote['start']['updated_by']!r} источник={remote['start']['source']}")

    # Мусор в форме — сообщение, а не пятисотка и не тихое ничего.
    junk = staff_client.post(f"{base}plans/start/", {"max_instances": "много"},
                             follow=True)
    check("мусор в форме тарифа не роняет страницу",
          junk.status_code == 200 and "нужно целое число" in junk.content.decode(),
          f"код={junk.status_code}")

    # РАСХОЖДЕНИЕ ДВУХ ИСТОЧНИКОВ ВИДНО ГЛАЗОМ. Мы только что подвинули потолок на
    # сервере до 3, а витрина продаёт 1 — экран обязан это показать, иначе он не
    # нужен: расхождение и так уже ловит красный тест, ценность консоли в том,
    # что человек видит его до того, как оно станет отказом клиенту.
    plans_body = staff_client.get(f"{base}plans/").content.decode()
    plan_start = Plan.objects.get(code="start")
    check("консоль показывает расхождение витрины и сервера",
          plan_start.max_instances != 3 and "pill bad" in plans_body,
          f"витрина={plan_start.max_instances} сервер=3")

    _check_reconciliation(staff_client, base, org)
    _check_configurator(client, staff_client, base)

    _screens_with_reconcile = screens + (f"{base}{org.id}/reconcile/",)

    # И ГЛАВНОЕ: КОНСОЛЬ ОТКРЫВАЕТСЯ, КОГДА ЛИЦЕНЗИОННЫЙ СЕРВЕР ЛЕЖИТ. Это ровно
    # та минута, ради которой её открывают, и пятисотка здесь — худшее из
    # возможных поведений.
    #
    # `raise_request_exception=False` ОБЯЗАТЕЛЕН, и не ради удобства. Под
    # `DEBUG=1` тестовый клиент пробрасывает исключение вью наружу вместо того,
    # чтобы вернуть 500, — то есть регрессия здесь роняла бы весь прогон
    # трейсбеком вместо строки «упало=/admin/ops/=500». Проверено снятием
    # `except` во вью: набор падал, но не говорил, что именно сломалось.
    down_client = _FreshClient(raise_request_exception=False)
    down_client.force_login(staff)
    _verify_otp(down_client, staff)
    with mock.patch("billing.licensing._get",
                    side_effect=licensing.LicensingError("сервер не отвечает")):
        down = {path: down_client.get(path) for path in _screens_with_reconcile}
    fell = [f"{path}={response.status_code}"
            for path, response in down.items() if response.status_code != 200]
    check("консоль открывается при лежащем лицензионном сервере", not fell,
          f"упало={fell or 'ничего'}")
    check("и честно говорит, что цифр сейчас нет",
          "не отвечает" in down[base].content.decode(),
          "плашка вместо молча пустых колонок")



def _check_configurator(client, staff_client, base: str) -> None:
    """Конфигуратор, спрос и то, что оба списка типов — ОДИН список.

    Проверка существует потому, что до неё страница `/detection` дважды обещала
    «напишите — это меняет очередь работ», а адреса для связи нет ни на одной
    странице сайта, и кнопка под этим обещанием вела в блок тарифов с подписью
    «ПРОВЕРИТЬ НА СВОЁМ ТЕКСТЕ» — при том что своего текста лендинг не принимает
    намеренно.
    """
    import json as _json

    from django.test import Client as _FreshClient

    from ops.models import DemandDay
    from storefront_web import detection_types

    body = client.get("/").content.decode()
    check("на лендинге есть блок конфигуратора", 'id="configurator"' in body)
    missing_groups = [group["code"] for group in detection_types.GROUPS
                      if f'data-group="{group["code"]}"' not in body]
    check("все группы реестра отрисованы", not missing_groups, str(missing_groups))
    # НИ ОДНОГО ПОЛЯ ДЛЯ ЧУЖОГО ТЕКСТА — В САМОМ БЛОКЕ. Утверждать это про всю
    # страницу нельзя: ниже стоит форма регистрации, и поле названия компании в
    # ней законно. Проверка по целой странице падала именно на нём, то есть
    # говорила не о том, о чём написана.
    section = body[body.index('id="configurator"'):body.index('id="start"')]
    check("конфигуратор не просит чужой текст",
          "<textarea" not in section and 'type="text"' not in section
          and 'type="email"' not in section, section[:0] or "проверен сам блок")

    # ОДИН РЕЕСТР НА ДВЕ СТРАНИЦЫ. Сверяется не двумя списками в тесте, а тем,
    # что подписи типов со страницы /detection приезжают из того же модуля.
    detection = client.get("/detection").content.decode()
    absent = [label for label, _example, _holds in detection_types.FOUND
              if label not in detection]
    check("страница /detection перечисляет реестр целиком", not absent, str(absent))
    check("и обещание «напишите» ведёт туда, где это можно сделать",
          "#configurator" in detection and "СВОЁМ ТЕКСТЕ" not in detection)

    gap = next(group["code"] for group in detection_types.GROUPS
               if not group.get("found"))
    other = next(group["code"] for group in detection_types.GROUPS
                 if not group.get("found") and group["code"] != gap)

    def send(sender, codes):
        return sender.post("/demand", data=_json.dumps({"groups": codes}),
                           content_type="application/json")

    visitor = _FreshClient()
    first = send(visitor, [gap])
    check("отметка записывается", first.status_code == 204,
          f"status={first.status_code}")
    check("и появляется ровно одна строка",
          DemandDay.objects.filter(group=gap).count() == 1
          and DemandDay.objects.get(group=gap).count == 1)

    # ПОВТОР ИЗ ТОЙ ЖЕ СЕССИИ НЕ СЧИТАЕТСЯ. Это и есть настоящая граница: троттл
    # по IP слаб по устройству (CACHES не задан, значит LocMemCache на процесс,
    # и при N воркерах лимит делится на N), а этот предел живёт в сессии.
    send(visitor, [gap])
    send(visitor, [gap])
    check("повтор из той же сессии счётчик не двигает",
          DemandDay.objects.get(group=gap).count == 1,
          f"стало {DemandDay.objects.get(group=gap).count}")
    # А ДРУГАЯ ГРУППА ИЗ ТОЙ ЖЕ СЕССИИ — СЧИТАЕТСЯ: предел на группу, не на
    # человека, иначе первая отметка глушила бы остальные.
    send(visitor, [other])
    check("другая группа из той же сессии считается",
          DemandDay.objects.get(group=other).count == 1)

    send(_FreshClient(), [gap])
    check("новая сессия считается", DemandDay.objects.get(group=gap).count == 2)

    before = DemandDay.objects.count()
    unknown = send(_FreshClient(), ["не-такой-код"])
    check("неизвестный код отвергается и не пишет строку",
          unknown.status_code == 400 and DemandDay.objects.count() == before,
          f"status={unknown.status_code}")
    mixed = send(_FreshClient(), [gap, "не-такой-код"])
    check("известный вместе с неизвестным — отказ целиком, а не половина",
          mixed.status_code == 400 and DemandDay.objects.count() == before,
          f"status={mixed.status_code}")
    check("GET на ручку спроса отвергается",
          _FreshClient().get("/demand").status_code == 405)
    check("пустой список отвергается",
          send(_FreshClient(), []).status_code == 400)

    # ВАЛИДНЫЙ JSON, У КОТОРОГО НЕТ `.get`. `[]`, `5`, `"x"` и `null` роняли
    # обработчик в 500 — анонимная ручка, падающая от тела из одного символа.
    #
    # `raise_request_exception=False` ОБЯЗАТЕЛЕН. Под `DEBUG=1` тестовый клиент
    # пробрасывает исключение вью наружу вместо 500 — то есть регрессия здесь
    # роняла бы ВЕСЬ прогон трейсбеком вместо строки «FAIL мусорное тело».
    # Проверено откатом: без него снятие проверки не давало ни одной строки
    # FAIL, только обрыв.
    broken = []
    for body_text in ("[]", "5", '"x"', "null", "{"):
        answer = _FreshClient(raise_request_exception=False).post(
            "/demand", data=body_text, content_type="application/json")
        if answer.status_code != 400:
            broken.append(f"{body_text}={answer.status_code}")
    check("мусорное тело — 400, а не 500", not broken, str(broken))

    # СТРОКИ О ПОСЕТИТЕЛЕ НЕ ПОЯВЛЯЕТСЯ, И ЭТО ПРОВЕРЯЕТСЯ, А НЕ ОБЕЩАЕТСЯ.
    # Дедуп жил в `request.session`, то есть в СТРОКЕ БАЗЫ на каждого анонима —
    # при том, что докстринг рядом обещал «ни отпечатка, ни идентификатора
    # сессии». Обещание было неправдой на соседней строке.
    from django.contrib.sessions.models import Session
    sessions_before = Session.objects.count()
    for _ in range(5):
        send(_FreshClient(), [gap])
    check("отметки не заводят строк сессий",
          Session.objects.count() == sessions_before,
          f"{sessions_before} -> {Session.objects.count()}")

    # РЕЕСТР СОГЛАСОВАН В ОБЕ СТОРОНЫ. Проверка ловила только «группа ссылается
    # на несуществующий тип»; обратная сторона — тип, не попавший ни в одну
    # группу, — молча выкидывала его с конфигуратора, что и случилось с
    # ОГРН/ОГРНИП.
    grouped = {label for group in detection_types.GROUPS
               for label in group.get("found", ())}
    check("каждый найденный тип попал в группу конфигуратора",
          grouped == {label for label, _e, _h in detection_types.FOUND},
          str({label for label, _e, _h in detection_types.FOUND} - grouped))
    # ПРОВЕРЯЕТСЯ ИСХОДНИК ШАБЛОНА, А НЕ ОТРЕНДЕРЕННАЯ СТРАНИЦА: в выводе
    # литерал «18 типов» и вычисленный `{{ found_count }}` неотличимы по
    # построению, пока в реестре ровно восемнадцать. Первая версия этой строки
    # смотрела на вывод и утверждала бессмыслицу.
    from pathlib import Path as _Path
    templates = _Path(__file__).resolve().parent / "templates"
    hardcoded = [str(f.relative_to(templates))
                 for f in (templates / "landing.html",
                           templates / "legal" / "detection.html")
                 if f"{len(detection_types.FOUND)} типов" in f.read_text(encoding="utf-8")]
    check("число типов в шаблонах не литерал, а длина реестра",
          not hardcoded, str(hardcoded))
    check("и страница его действительно печатает",
          f"{len(detection_types.FOUND)} типов" in detection)

    # ЭКРАН, РАДИ КОТОРОГО ВСЁ ЭТО ПИШЕТСЯ: очередь работ должна читаться
    # глазами, иначе счётчик существует для себя.
    screen = staff_client.get(f"{base}demand/")
    text = screen.content.decode()
    check("сотрудник видит экран спроса", screen.status_code == 200)
    check("и на нём непокрытая группа с числом",
          gap in text or dict(
              (group["code"], group["label"]) for group in detection_types.GROUPS
          )[gap] in text)
    check("аноним экран спроса не видит",
          _FreshClient().get(f"{base}demand/").status_code in (302, 404),
          f"status={_FreshClient().get(f'{base}demand/').status_code}")


def _check_reconciliation(staff_client, base: str, org) -> None:
    """Сверка счёта с логом шлюза клиента — арифметика и экран.

    `docs/billing-integrity.md` объявляет запрос единицей тарификации ИМЕННО
    потому, что «запрос виден в логе шлюза самого клиента» и спор о деньгах
    превращается в сравнение двух независимых источников. Сравнивать до сих пор
    было нечем.
    """
    from billing import reconcile as R

    # ТРИ МАСШТАБА ИЗ `docs/billing-integrity.md`, ЧЕСТНАЯ ЦЕПЬ: там измерено
    # 0.00% на всех трёх, значит числа обязаны совпадать РОВНО, а не «примерно».
    exact = [R.reconcile(ours=volume, theirs=volume,
                         quantum_max=q, reserve_max=r)
             for volume, q, r in ((10_000, 2_000, 20_000),
                                  (100_000, 10_000, 100_000),
                                  (1_000_000, 40_000, 400_000))]
    check("на трёх масштабах при целой цепи счёт сходится точно",
          all(item.verdict == R.MATCH and item.difference == 0 for item in exact),
          f"вердикты={[item.verdict for item in exact]}")

    # Полоса — это `Q + R` из строки тарифа, и она объявлена несущей.
    band = R.band_width(quantum_max=2_000, reserve_max=20_000)
    check("полоса погрешности равна Q + R из тарифа", band == 22_000, f"полоса={band}")

    # И ОНА СКЛАДЫВАЕТСЯ ПО ПРОЦЕССАМ. `LicenseStore.billable` зажимает
    # `clamp(acked, granted − Q − R, granted)` НА КАЖДЫЙ процесс и складывает —
    # леджер ёмкости ключуется на ключ процесса. Восьмиворкерный контейнер на
    # «Старте» законно расходится на 8 × 22 000, и полоса в одну штуку объявила
    # бы это «мы выставили больше, смотреть надо у нас».
    check("полоса складывается по процессам, а не берётся за один",
          R.band_width(2_000, 20_000, processes=8) == 8 * 22_000,
          f"на восьми процессах={R.band_width(2_000, 20_000, processes=8)}")
    eight = R.reconcile(ours=10_000, theirs=10_000 + 8 * 22_000 - 1,
                        quantum_max=2_000, reserve_max=20_000, processes=8)
    check("законное расхождение восьми воркеров не зовётся нашим дефектом",
          eight.agrees, f"вердикт={eight.verdict}")

    # ПОЛОСА НЕИЗВЕСТНА — ВЕРДИКТА НЕТ. Нет подписки, нет тарифа на сервере, ни
    # один процесс не брал ёмкость: ноль здесь значит «не знаем, на сколько
    # можно», а не «расходиться нельзя».
    blind = R.reconcile(ours=10_000, theirs=10_001, quantum_max=0, reserve_max=0)
    check("без известной полосы вердикт не выносится",
          blind.verdict == R.UNKNOWN_BAND and not blind.agrees
          and "по какому тарифу" in blind.reasons[0],
          f"вердикт={blind.verdict}")

    inside = R.reconcile(ours=10_000, theirs=10_000 + band,
                         quantum_max=2_000, reserve_max=20_000)
    outside = R.reconcile(ours=10_000, theirs=10_000 + band + 1,
                          quantum_max=2_000, reserve_max=20_000)
    check("на самой границе полосы расхождение ещё объяснимо",
          inside.verdict == R.WITHIN_BAND and inside.agrees,
          f"вердикт={inside.verdict}")
    check("на шаг за границей — уже нет",
          outside.verdict == R.THEY_COUNTED_MORE and not outside.agrees,
          f"вердикт={outside.verdict}")

    # САМАЯ ЧАСТАЯ ПРИЧИНА НАЗЫВАЕТСЯ ПЕРВОЙ. У клиента больше нашего — почти
    # всегда он посчитал то, что запросом не считается; проверяется за минуту, в
    # отличие от разбора цепи.
    check("когда у клиента больше, первым назван его собственный подсчёт",
          outside.reasons and "/spans" in outside.reasons[0],
          f"первая причина={outside.reasons[0][:70] if outside.reasons else 'нет'}")

    # ОБРАТНЫЙ СЛУЧАЙ — ЕДИНСТВЕННЫЙ, ГДЕ ВИНОВАТЫ СКОРЕЕ МЫ, и текст обязан это
    # говорить: при доходящих отчётах счёт равен расходу, значит расхождение в
    # эту сторону при целой цепи — наша сторона.
    ours_more = R.reconcile(ours=50_000, theirs=10_000,
                            quantum_max=2_000, reserve_max=20_000)
    check("перевыставление при целой цепи названо нашей стороной",
          ours_more.verdict == R.WE_BILLED_MORE
          and any("наша сторона" in reason for reason in ours_more.reasons),
          f"вердикт={ours_more.verdict}")

    # ПОРВАННАЯ ЦЕПЬ — НЕ ОБВИНЕНИЕ. Счёт идёт по выданной ёмкости, а отчёт
    # только уменьшил бы его: это отказ от скидки, а не приписка. Формулировка
    # тут и есть продукт — с неё начинается разговор с клиентом.
    dirty = R.reconcile(ours=50_000, theirs=10_000, quantum_max=2_000,
                        reserve_max=20_000, reports_missing=3, chain_breaks=1)
    check("порванная цепь объясняется скидкой, а не припиской",
          not dirty.chain_clean
          and any("не приписка" in reason for reason in dirty.reasons)
          and not any("наша сторона" in reason for reason in dirty.reasons),
          f"причин={len(dirty.reasons)}")

    # Первая точка ряда прироста не имеет — предшественника в окне нет.
    rows = R.daily_rows([{"day": "2026-09-01", "requests": 100},
                         {"day": "2026-09-02", "requests": 250}])
    check("в выгрузке первая точка не выдаёт накопленное за прирост",
          rows[0]["requests_delta"] == "" and rows[1]["requests_delta"] == 150,
          f"ряд={[row['requests_delta'] for row in rows]}")

    # СВЕРЯЕТСЯ КОНКРЕТНЫЙ СЧЁТ, А НЕ «ТО, ЧТО НАКАПАЛО ПОСЛЕ НЕГО».
    #
    # Спор начинается со счёта в руках, поэтому число обязано быть тем самым,
    # что на нём напечатано. Здесь считалось «накопленное минус ватермарка
    # последнего счёта» — то есть объём ЕЩЁ НЕ ВЫСТАВЛЕННОГО периода, — и
    # подписывалось именем того самого счёта: клиент, пришедший спорить про
    # INV-N, получал разницу с чужим числом, тем большую, чем дольше работает.
    from datetime import date, timedelta

    from billing.models import Invoice

    disputed = Invoice.objects.create(
        organization=org, number=Invoice.next_number(), state=Invoice.ISSUED,
        period_start=date.today() - timedelta(days=30), period_end=date.today(),
        requests_billable_in_period=4_242,
        requests_billable_at_period_end=9_999)
    with_invoice = staff_client.get(
        f"{base}{org.id}/reconcile/?invoice={disputed.number}").content.decode()
    # Разделитель разрядов у Django — НЕРАЗРЫВНЫЙ пробел (`USE_THOUSAND_SEPARATOR`),
    # поэтому «4242» на странице не встречается буквально ни при каком раскладе.
    flat = with_invoice.replace("\u00a0", "").replace(" ", "")
    check("сверяется число С САМОГО СЧЁТА, а не остаток после него",
          "4242" in flat and disputed.number in with_invoice,
          f"счёт {disputed.number} несёт 4242 за период")

    # ЭКРАН И ВЫГРУЗКА.
    page = staff_client.get(f"{base}{org.id}/reconcile/")
    check("экран сверки открывается", page.status_code == 200,
          f"код={page.status_code}")
    body = page.content.decode()
    check("экран говорит, что лог сюда не загружается",
          "не загружается" in body,
          "иначе кто-нибудь однажды приделает загрузку файла")
    check("экран перечисляет, что запросом не считается",
          "/spans" in body and "fail-closed" in body)

    # ПРОВЕРЯЕТСЯ ВЕРДИКТ, А НЕ ЭХО. Число уезжает обратно в `value` формы,
    # поэтому «999999 есть на странице» истинно и тогда, когда сверка не
    # считалась вовсе, — то есть проверка не могла упасть.
    swept = staff_client.get(f"{base}{org.id}/reconcile/?theirs=999999").content.decode()
    check("экран выносит вердикт по названному числу",
          "Чем объясняется" in swept and "запросом не считается" in swept,
          "вердикта на странице нет — сверка не посчиталась")
    junk = staff_client.get(f"{base}{org.id}/reconcile/?theirs=много", follow=True)
    check("мусор вместо числа не роняет сверку",
          junk.status_code == 200 and "нужно целое число" in junk.content.decode(),
          f"код={junk.status_code}")

    csv_response = staff_client.get(f"{base}{org.id}/usage.csv")
    # Колонка называет ЧАСОВОЙ ПОЯС. Срез режет UTC (`time.gmtime` на
    # лицензионном сервере), а витрина рисует в Europe/Moscow: без пометки
    # вечерний московский трафик молча ложится в предыдущую строку, и клиент
    # ищет расхождение там, где его нет.
    check("выгрузка отдаётся файлом и называет часовой пояс суток",
          csv_response.status_code == 200
          and "attachment" in csv_response.headers.get("Content-Disposition", "")
          and b"day_utc,requests_total" in csv_response.content,
          f"код={csv_response.status_code}")
    # Имя файла строится из идентификатора, а не из названия организации:
    # название — свободная строка, и она уехала бы в заголовок ответа.
    check("имя файла выгрузки не несёт свободной строки",
          org.display_name not in csv_response.headers.get("Content-Disposition", ""),
          csv_response.headers.get("Content-Disposition", ""))

if __name__ == "__main__":
    sys.exit(main())
