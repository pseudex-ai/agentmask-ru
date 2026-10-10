"""Операторская консоль в НАСТОЯЩЕМ браузере, на всех шести экранах.

ПОЧЕМУ ЭТОГО НЕ ЗАМЕНЯЕТ `test_storefront.py`. Тот проверяет коды ответа и
наличие подстрок в HTML — и оба утверждения остались бы верными, если бы
страница исполнялась с ошибкой, рисовала пустую таблицу или показывала не то.
Консоль — это место, где мы ведём бизнес: флот, разрывы цепи отчётов, правка
тарифа без выката, сверка счёта с логом клиента. Экран, который «отдаёт 200» и
ничего не рисует, выглядит для HTTP так же, как рабочий; в этом репозитории уже
было ровно так с интерфейсом контейнера.

И ОДНА ПРОВЕРКА ЗДЕСЬ НЕ ПРО ОТРИСОВКУ. Консоль показывает данные клиентов, и
персональных данных на ней быть не может ни при каких условиях — они физически
не покидают контур заказчика, но проверять это надо там, где рисуется, а не там,
где обещано.

ПРОПУСК — ПРОВАЛ, А НЕ «НЕ СМОГЛИ»: отсутствие playwright печатает команду
установки и выходит ненулём.

    cd storefront && .venv/bin/python test_ops_renders.py
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_PORT = int(os.environ.get("PSEUDEX_OPS_PORT", "8413"))
_DB = os.path.join(tempfile.mkdtemp(prefix="pseudex-ops-db-"), "store.sqlite3")
_STAFF_EMAIL = "ops-render@pseudex.local"
_STAFF_PASSWORD = "ops-render-password-not-a-secret"
# Шестнадцатеричный ключ TOTP, из которого считается код. Не секрет:
# он живёт ровно столько, сколько идёт этот тест, и в стенде, который
# поднимается на локальном порту и гасится в `finally`.
_STAFF_TOTP_KEY = "3132333435363738393031323334353637383930"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _launch(pw):
    """Штатный chromium, а если номер сборки не тот — лежащий рядом.

    Тот же приём, что в `test_configurator_renders.py`: проверка, падающая на
    несовпадении номеров playwright и браузера, перестаёт бежать — а падать она
    должна на консоли.
    """
    try:
        return pw.chromium.launch()
    except Exception as error:  # noqa: BLE001 — любая
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        found = sorted(Path(root).glob("chromium-*/chrome-linux/chrome")) if root else []
        if not found:
            raise RuntimeError(
                f"chromium не запускается ({error}); поставьте его "
                f"`python -m playwright install chromium`") from error
        return pw.chromium.launch(executable_path=str(found[-1]))


_SEED = '''
import os
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Membership, Organization
from billing.models import Invoice, LicenseKey, Plan, Subscription

User = get_user_model()
staff = User.objects.create_user(email=os.environ["STAFF_EMAIL"],
                                 password=os.environ["STAFF_PASSWORD"])
staff.is_staff = staff.is_superuser = True
staff.save()

# ВТОРОЙ ФАКТОР — ЧАСТЬ ВХОДА В КОНСОЛЬ, А НЕ ДЕТАЛЬ. Консоль закрыта
# `otp_required`, поэтому без подтверждённого устройства сюда не войти вообще:
# проверка отрисовки экранов сперва обязана пройти тем же входом, что и человек.
# Ключ задан константой, чтобы тест мог посчитать код той же арифметикой.
from django_otp.plugins.otp_totp.models import TOTPDevice
TOTPDevice.objects.create(user=staff, name="ops-render", confirmed=True,
                          key=os.environ["STAFF_TOTP_KEY"])

# Клиент с полной историей: подписка, ключ, оплаченный счёт и счёт по объёму.
# Пустая консоль отрисуется у кого угодно — экран обязан быть проверен на
# данных, иначе «страница открылась» ничего не значит.
customer_user = User.objects.create_user(email="client@example.test",
                                         password="x" * 20)
org = Organization.objects.create(display_name="ООО Ромашка", legal_name="ООО «Ромашка»",
                                  inn="7707083893")
Membership.objects.create(user=customer_user, organization=org)
plan = Plan.objects.get(code="industrial")
Subscription.objects.create(organization=org, plan=plan,
                            trial_ends_at=timezone.now() + timedelta(days=14),
                            current_period_end=timezone.now() + timedelta(days=30))
LicenseKey.record(org, "ps_live_rendercheck0000000000", "прод", "live")
Invoice.objects.create(organization=org, number="PS-2026-09-render01",
                       state=Invoice.PAID, period_start="2026-08-01",
                       period_end="2026-08-31", plan_amount=Decimal("11900"),
                       metered_requests=500000, metered_amount=Decimal("4750"),
                       total=Decimal("16650"), requests_at_period_end=1500000,
                       values_at_period_end=900000)
# ВИЗИТЫ И ВОРОНКА: пустой экран отрисуется у кого угодно, и проверка на нём
# ничего не значит. Сеем оба конца воронки — начало на лендинге и хвост по
# организации — плюс одного бота, чтобы фильтр было видно.
from ops.analytics_models import Funnel, Visit
for i in range(25):
    Visit.objects.create(visitor=f"v{i % 7:014d}", path="/" if i % 3 else "/detection",
                         referrer_host="ya.ru" if i % 4 == 0 else "",
                         utm_source="habr" if i % 5 == 0 else "",
                         device="десктоп", browser="Chrome", os="macOS")
Visit.objects.create(visitor="botbotbotbotbo", path="/", is_bot=True)
for i in range(7):
    Funnel.objects.create(step=Funnel.LANDING, visitor=f"v{i:014d}")
Funnel.objects.create(step=Funnel.SIGNUP_SUBMITTED, visitor="v0000000000000",
                      organization_id=org.id, detail="industrial")
Funnel.objects.create(step=Funnel.SIGNUP_REFUSED, detail="уже зарегистрирован")
Funnel.objects.create(step=Funnel.ACTIVATED, organization_id=org.id)
# Paid-first is a legitimate SaaS path, not missing first_mask wiring.
Funnel.objects.create(step=Funnel.PAID, organization_id=org.id, detail="16650")
Funnel.objects.create(step=Funnel.KEY_ISSUED, organization_id=org.id)

print(org.id)
'''


def _start_site() -> tuple[subprocess.Popen, str]:
    env = dict(os.environ)
    env.update({
        "DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
        "PSEUDEX_DEBUG": "1",
        "PSEUDEX_SECRET_KEY": "ops-render-test",
        "PSEUDEX_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "PSEUDEX_DB_PATH": _DB,
        "STAFF_EMAIL": _STAFF_EMAIL,
        "STAFF_PASSWORD": _STAFF_PASSWORD,
        "STAFF_TOTP_KEY": _STAFF_TOTP_KEY,
        # Лицензионного сервера здесь нет НАМЕРЕННО: консоль обязана открываться
        # и говорить, что цифр сейчас нет, а не падать пятисоткой. Этот случай
        # уже проверяется по HTTP, и в браузере он же — самый вероятный на
        # проде.
        # ЛИЦЕНЗИОННЫЙ СЕРВЕР ЛЕЖИТ ПО УМОЛЧАНИЮ, И ЭТО ГЛАВНЫЙ СЛУЧАЙ.
        # Консоль обязана открываться и говорить, что цифр сейчас нет, а не
        # падать пятисоткой: на проде это самое частое её состояние — наш
        # сервис перезапускается, сеть моргает, а оператор в этот момент как
        # раз и смотрит, что происходит.
        #
        # Прогон с ЖИВЫМ сервером — второй, и он включается переменной, потому
        # что требует поднятого стенда. Экран тарифов строит форму по ответу
        # `/admin/plans`, поэтому без сервера формы там нет ЗАКОННО.
        "PSEUDEX_LICENSING_ADMIN_URL": os.environ.get(
            "PSEUDEX_OPS_LICENSING_URL", "http://127.0.0.1:9"),
    })
    for command in (["migrate", "--noinput", "-v", "0"], ["seed_plans", "-v", "0"]):
        subprocess.run([sys.executable, "manage.py", *command], cwd=str(_ROOT),
                       env=env, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    seeded = subprocess.run([sys.executable, "manage.py", "shell", "-c", _SEED],
                            cwd=str(_ROOT), env=env, check=True,
                            capture_output=True, text=True)
    org_id = seeded.stdout.strip().splitlines()[-1]

    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{_PORT}",
         "--noreload", "--insecure"],
        cwd=str(_ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{_PORT}/", timeout=2)
            return server, org_id
        except urllib.error.HTTPError:
            return server, org_id
        except OSError:
            time.sleep(0.5)
    server.terminate()
    raise RuntimeError("витрина не поднялась")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright не установлен, а без него эта проверка ничего не "
              "проверяет:\n  pip install playwright && "
              "python -m playwright install chromium")
        return 1

    live_licensing = bool(os.environ.get("PSEUDEX_OPS_LICENSING_URL"))
    print(f"лицензионный сервер: {'живой' if live_licensing else 'намеренно лежит'}")
    server, org_id = _start_site()
    base = f"http://127.0.0.1:{_PORT}"
    admin_path = os.environ.get("PSEUDEX_ADMIN_PATH", "admin")
    ops = f"{base}/{admin_path}/ops"
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                    if m.type == "error" else None)

            # --- аноним не входит ---------------------------------------
            page.goto(f"{ops}/", wait_until="networkidle")
            check("аноним на консоль не попадает",
                  "/login" in page.url or "войти" in page.content().lower(),
                  page.url.replace(base, ""))

            # --- вход сотрудника ----------------------------------------
            #
            # ЧЕРЕЗ АДМИНКУ И С КОДОМ. Здесь стояла клиентская форма
            # `/accounts/login/` с полями login+password, и она умерла дважды:
            # вход клиента стал беспарольным (поля `password` там больше нет), а
            # консоль закрылась вторым фактором. Тест падал на `input[name=login]`
            # по таймауту — сообщение, по которому ни одной из двух причин не видно.
            # ВХОД В ДВА ШАГА, КАК У ЧЕЛОВЕКА. `OTPAuthenticationForm` сперва
            # проверяет пароль и только потом показывает выбор устройства: код
            # без `otp_device` она отвергает словами «Please select a device», и
            # одностраничная попытка возвращалась на форму входа молча.
            from django_otp.oath import totp as _totp
            page.goto(f"{base}/{admin_path}/login/?next=/{admin_path}/ops/",
                      wait_until="networkidle")
            page.fill("input[name=username]", _STAFF_EMAIL)
            page.fill("input[name=password]", _STAFF_PASSWORD)
            page.click("input[type=submit], button[type=submit]")
            page.wait_for_load_state("networkidle")
            # Код считается ЗДЕСЬ, после первого шага: он живёт 30 секунд, и
            # посчитанный до перехода мог бы протухнуть на медленной странице.
            page.select_option("select[name=otp_device]", index=0)
            page.fill("input[name=otp_token]", "%06d" % _totp(bytes.fromhex(_STAFF_TOTP_KEY)))
            page.click("input[type=submit], button[type=submit]")
            page.wait_for_load_state("networkidle")
            check("сотрудник вошёл паролем и кодом",
                  "/login" not in page.url, page.url.replace(base, ""))

            screens = [
                ("флот", f"{ops}/", ["ООО Ромашка"]),
                ("разрывы цепи", f"{ops}/chains/", []),
                ("тарифы", f"{ops}/plans/", ["Промышленный"]),
                ("конструктор", f"{ops}/tariffs/",
                 ["Промышленный", "прежних условиях", "Новый тариф"]),
                ("спрос", f"{ops}/demand/", []),
                ("аналитика", f"{ops}/analytics/",
                 ["События за период", "Когорта новых регистраций", "зашёл на лендинг", "поднял контейнер", "Трафик"]),
                # ЭКРАН ЯНДЕКСА ПРОВЕРЯЕТСЯ ПРИ ВЫКЛЮЧЕННОЙ ИНТЕГРАЦИИ, и это
                # главный случай: он обязан открываться, когда чужой сервис не
                # настроен или лежит, — иначе диагностика отказывает ровно в ту
                # минуту, ради которой существует.
                ("яндекс", f"{ops}/yandex/",
                 ["Яндекс", "Метрика за", "Директ", "СЧЁТЧИК"]),
                ("карточка клиента", f"{ops}/{org_id}/", ["ООО Ромашка", "PS-2026-09-render01"]),
                ("сверка", f"{ops}/{org_id}/reconcile/", []),
            ]
            for name, url, must_contain in screens:
                errors.clear()
                page.goto(url, wait_until="networkidle")
                body = page.inner_text("body")
                # НЕ ПУСТАЯ И НЕ ТРАССИРОВКА. Django с DEBUG=1 рисует стектрейс
                # с кодом 500, и «страница отрисовалась» на нём тоже верно.
                healthy = (len(body) > 200 and "Traceback" not in body
                           and "Server Error" not in body)
                missing = [needle for needle in must_contain if needle not in body]
                check(f"экран «{name}» отрисован", healthy and not missing,
                      f"{len(body)} симв."
                      + (f", НЕТ: {missing}" if missing else "")
                      + (f", ошибки: {errors[:2]}" if errors else ""))

            # --- правка тарифа доезжает до базы -------------------------
            # Форма живёт на СПИСКЕ и постит в `ops_edit_plan`; сам
            # `/plans/<code>/` — это POST-ручка, а не страница. Первая версия
            # проверки ходила туда и падала «формы нет» — на продукте, у
            # которого форма есть.
            page.goto(f"{ops}/plans/", wait_until="networkidle")
            form = page.query_selector("form[action*='plans/industrial']")
            body = page.inner_text("body")
            if live_licensing:
                check("тариф правится с экрана, а не через выкат", form is not None,
                      "формы на странице списка нет" if form is None else "форма есть")
            else:
                # БЕЗ СЕРВЕРА ФОРМЫ НЕТ ЗАКОННО — но экран обязан СКАЗАТЬ об
                # этом, а не показать пустую таблицу, из которой оператор
                # сделает вывод «тарифов нет».
                said = any(word in body.lower() for word in
                           ("недоступ", "не отвеча", "нет связи", "сейчас нет"))
                check("без лицензионного сервера экран тарифов честно молчит",
                      form is None and said,
                      f"форма={form is not None} объяснение={said}")

            # --- аналитика: боты не попадают в число посетителей --------
            page.goto(f"{ops}/analytics/", wait_until="networkidle")
            body = page.inner_text("body")
            import re as _re
            shown = _re.search(r"(\d+)\s+посетителей", body)
            check("аналитика считает посетителей без ботов",
                  shown is not None and int(shown.group(1)) == 7,
                  f"на экране {shown.group(1) if shown else '?'}, посеяно 7 живых + 1 бот")
            # НЕ РАВЕНСТВО, А НАЛИЧИЕ: сам playwright опознаётся фильтром как
            # бот (в его user-agent есть `HeadlessChrome`), поэтому ботов
            # больше посеянного одного — и это доказательство, что фильтр
            # работает, а не повод ослабить проверку. Считаем ровно то, что
            # утверждаем: их отдельная строка есть и число в ней не ноль.
            counted = _re.search(r"ботов отфильтровано (\d+)", body)
            check("бот посчитан отдельно и назван",
                  counted is not None and int(counted.group(1)) >= 1,
                  f"{counted.group(1) if counted else 'строки нет'} — "
                  f"выброшенное нельзя пересчитать, помеченное можно")
            check("агрегаты не названы последовательными потерями людей",
                  "ПОТЕРЯНО" not in body and "из предыдущего" not in body.lower()
                   and "не последовательная конверсия" in body,
                  "paid-first не обязан сначала маскировать запрос")
            cohort_table = page.locator("table").filter(
                has=page.get_by_text("ОТ КОГОРТЫ", exact=True))
            paid = cohort_table.locator("tr").filter(
                has=page.get_by_text("заплатил", exact=True)).locator("td").all_text_contents()
            masked = cohort_table.locator("tr").filter(
                has=page.get_by_text("первый замаскированный запрос", exact=True)).locator("td").all_text_contents()
            check("когорта paid-first: одна оплата из одного аккаунта",
                  len(paid) == 3 and paid[1].strip() == "1"
                  and _re.fullmatch(r"100(?:[.,]0)?%", paid[2].strip()) is not None,
                  str(paid))
            check("paid-first без first_mask не назван сломанной воронкой",
                  len(masked) == 3 and masked[1].strip() == "0"
                  and "НЕ ЗАПИСЫВАЕТСЯ" not in body, str(masked))

            # --- конструктор правит цену и говорит, кого это коснётся ----
            page.goto(f"{ops}/tariffs/", wait_until="networkidle")
            form = page.query_selector("form:has(input[name='code'][value='industrial'])")
            edited = False
            if form is not None:
                form.query_selector("input[name=monthly_price]").fill("13500")
                # НАСТРАИВАЕМЫЕ ВЛАДЕЛЬЦЕМ КОММЕРЧЕСКИЕ РУЧКИ: годовая скидка
                # правится тем же экраном, а не только сидом/кодом.
                form.query_selector("input[name=annual_discount_pct]").fill("20")
                form.query_selector("input[name=note]").fill("проверка экрана")
                form.query_selector("button[type=submit]").click()
                page.wait_for_load_state("networkidle")
                edited = True
            body = page.inner_text("body")
            check("конструктор применяет правку и называет её последствие",
                  edited and "13500" in body.replace(" ", "")
                  and "прежних условиях" in body,
                  f"{'правка ушла' if edited else 'формы нет'}")
            # ПРОВЕРЯЕМ ЧЕРЕЗ DOM, А НЕ ORM: тест-процесс правит сервер браузером
            # и своего Django не поднимает. После правки экран перерисован, и
            # плейсхолдер годовой скидки у «Промышленного» показывает новое 20.
            after = page.query_selector(
                "form:has(input[name='code'][value='industrial']) "
                "input[name=annual_discount_pct]")
            check("годовая скидка правится из конструктора (настраивается)",
                  after is not None and after.get_attribute("placeholder") == "20",
                  after.get_attribute("placeholder") if after else "поля нет")
            # ЖУРНАЛ — ЧАСТЬ ОБЕЩАНИЯ. Правка без записи о том, кто и зачем,
            # неотличима от посева, и первый спор о цене упирается в память.
            page.click("details summary")
            check("правка попала в журнал с автором",
                  _STAFF_EMAIL in page.inner_text("body"), _STAFF_EMAIL)

            # --- сверка принимает число и выносит вердикт ---------------
            page.goto(f"{ops}/{org_id}/reconcile/", wait_until="networkidle")
            # ПРИЦЕЛ ВНУТРЬ НУЖНОЙ ФОРМЫ. Первая версия брала первую кнопку
            # отправки НА СТРАНИЦЕ, попадала в чужую, уезжала на лендинг — и
            # проверяла всё дальнейшее против него. Проверка «на консоли нет
            # персональных значений» краснела на вымышленном телефоне из
            # демонстрации на главной: неверный вывод из верного наблюдения,
            # сделанного не на той странице.
            form = page.query_selector("form:has(input[name=theirs]:not([type=hidden]))")
            submitted = False
            if form is not None:
                form.query_selector("input[name=theirs]").fill("1500000")
                form.query_selector("button[type=submit]").click()
                page.wait_for_load_state("networkidle")
                submitted = True
            verdict = page.inner_text("body")
            check("сверка отвечает на названное число, а не молчит",
                  submitted and f"/{org_id}/reconcile" in page.url
                  and len(verdict) > 200 and "Traceback" not in verdict,
                  f"{page.url.replace(base, '')} — {len(verdict)} симв.")

            # --- и ни одного персонального значения ---------------------
            # Их здесь физически нет: витрина не видит трафик. Проверяется
            # там, где рисуется, потому что обещание проверяется механизмом.
            # Читается ТОЛЬКО экран консоли: `page.url` выше уже удостоверил,
            # что мы всё ещё на нём.
            leaked = [needle for needle in ("+7 9", "@example.test", "СНИЛС ", "паспорт ")
                      if needle in verdict]
            check("на консоли нет персональных значений", not leaked, str(leaked))

            shot = os.path.join(tempfile.gettempdir(), "pseudex-ops.png")
            page.screenshot(path=shot, full_page=True)
            print(f"  снимок: {shot}")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    # ЧИСЛО ЭКРАНОВ НЕ ПИШЕТСЯ СЛОВАМИ. Оно уже разошлось — «шесть» при
    # девяти, — и разошлось ровно потому, что его никто не пересчитывал при
    # добавлении седьмого. Считаем здесь, а не помним.
    print(f"операторская консоль OK — {len(screens)} экранов рисуются на "
          f"настоящих данных")
    return 0


if __name__ == "__main__":
    sys.exit(main())
