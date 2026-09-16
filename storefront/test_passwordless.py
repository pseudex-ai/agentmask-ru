"""Вход клиента — БЕЗ ПАРОЛЯ: почта → 6-значный код из письма → кабинет.

ЗАЧЕМ. Регистрация («Быстрый старт») пароль не задаёт никогда, а страница входа
показывала поле пароля — дефолт allauth, который никто не убрал. Клиент видел
форму, заполнить которую не мог: пароля у него нет. Теперь вход ровно один и он
совпадает с тем, как аккаунт заводится: доказательство владения почтой.

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ, И ПОЧЕМУ ИМЕННО ЭТО:
  * страница пароля недостижима — и GET, и POST: редирект, а не «спрятали
    поле». Спрятанное поле остаётся рабочей ручкой для того, кто знает URL;
  * пароль нельзя ЗАВЕСТИ — сброс пароля тоже уведён, иначе passwordless
    держался бы на том, что клиент не найдёт ссылку;
  * полный круг живьём: письмо с кодом → ввод кода → кабинет открылся;
  * АДМИНКА НЕ ЗАТРОНУТА. Это отдельная авторизация (Django admin + TOTP), и
    если passwordless заденет её, оператор останется без входа в биллинг. Гейт
    ровно на это: у админки поле пароля обязано остаться.

Запуск:  cd storefront && .venv/bin/python test_passwordless.py
"""
import os
import re
import sys


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "passwordless-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-passwordless-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-passwordless-test.db"):
        os.remove("/tmp/pseudex-passwordless-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    # ПОЧТА В ПАМЯТЬ — иначе код уходит в консоль и прочитать его нечем, а
    # проверка «письмо с кодом пришло» превратилась бы в проверку «не упало».
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from datetime import timedelta
    from django.conf import settings
    from django.core import mail
    from django.test import Client
    from django.utils import timezone
    from accounts.models import Membership, Organization, User
    from billing.models import Plan, Subscription

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # Клиент с организацией и подпиской — иначе кабинет не отрисуется и «вошёл»
    # нельзя отличить от «вошёл, но экран пустой».
    email = "client@example.com"
    user = User.objects.create_user(email=email)
    org = Organization.objects.create(id="pwless", display_name="Pwless Co")
    Membership.objects.create(user=user, organization=org)
    now = timezone.now()
    Subscription.objects.create(
        organization=org, plan=Plan.objects.get(code="start"),
        state=Subscription.TRIAL, trial_ends_at=now + timedelta(days=14),
        current_period_start=now, current_period_end=now + timedelta(days=14))

    # --- 1. страница пароля недостижима ------------------------------------
    c = Client()
    r = c.get("/accounts/login/")
    check(r.status_code == 302 and "/accounts/login/code/" in r.headers.get("Location", ""),
          "GET /accounts/login/ уводит на вход по коду",
          f"code={r.status_code} loc={r.headers.get('Location')}")

    # `?next=` НЕ ТЕРЯЕТСЯ: иначе клиента, пришедшего за счётом, после входа
    # выбрасывает на главную, и он идёт искать счёт заново.
    r_next = c.get("/accounts/login/?next=/app/invoices/PS-1")
    check("next=" in r_next.headers.get("Location", ""),
          "редирект сохраняет ?next", r_next.headers.get("Location", ""))

    # POST С ПАРОЛЕМ НЕ АУТЕНТИФИЦИРУЕТ. Проверяем именно POST, а не только
    # отсутствие поля в разметке: спрятать поле — не значит закрыть ручку.
    user.set_password("real-password-123")
    user.save()
    posted = c.post("/accounts/login/", {"login": email, "password": "real-password-123"})
    still_out = c.get("/app/")
    check(posted.status_code == 302 and still_out.status_code == 302,
          "POST пароля на старый URL не пускает в кабинет",
          f"post={posted.status_code} app={still_out.status_code}")

    # --- 2. страница входа по коду ------------------------------------------
    # СВЕЖИЙ КЛИЕНТ НА КАЖДУЮ СЕКЦИЮ. Вьюха запроса кода уводит уже вошедшего
    # (RedirectAuthenticatedUserMixin), поэтому сессия, оставшаяся от проверки
    # выше, давала бы 302 и секция падала бы по ложной причине — не потому, что
    # вход по коду сломан.
    c = Client()
    page = c.get("/accounts/login/code/")
    body = page.content.decode()
    check(page.status_code == 200, "страница входа по коду открывается", f"code={page.status_code}")
    check('name="email"' in body, "на ней есть поле почты")
    check('type="password"' not in body, "и НЕТ поля пароля")

    # --- 3. полный круг: письмо с кодом → вход -------------------------------
    mail.outbox.clear()
    asked = c.post("/accounts/login/code/", {"email": email})
    check(asked.status_code == 302 and len(mail.outbox) == 1,
          "запрос кода отправляет ровно одно письмо",
          f"code={asked.status_code} писем={len(mail.outbox)}")
    letter = (mail.outbox[0].body if mail.outbox else "")
    subject = (mail.outbox[0].subject if mail.outbox else "")
    # Код у allauth — шесть БУКВЕННО-ЦИФРОВЫХ символов (G6NHVG), не шесть цифр:
    # формат сверен с живым письмом, а не предположен.
    found = re.search(r"\b([A-Z0-9]{6})\b", letter)
    check(found is not None, "в письме есть код (6 буквенно-цифровых)", letter[:120])
    # ПИСЬМО БРЕНДОВОЕ. По умолчанию allauth подставляет имя объекта Site, а он
    # в базе дефолтный django — клиент получил бы «[example.com] Код для входа»
    # и текст про example.com. Это единственное письмо на пути входа, и оно не
    # может выглядеть чужим.
    check("example.com" not in letter and "example.com" not in subject,
          "в письме и теме нет example.com", f"тема={subject!r}")
    check("pseudex" in letter.lower(), "письмо подписано pseudex")

    # Экран ввода кода — второй шаг единственного входа, и он тоже должен быть
    # брендовым. Отдельно в test_auth_style его не проверить: без начатого
    # флоу страница недоступна, поэтому смотрим здесь, пока код запрошен.
    step2 = c.get("/accounts/login/code/confirm/").content.decode()
    check("auth-card" in step2 and "site.css" in step2,
          "экран ввода кода в брендовой карточке")
    check("Menu:" not in step2 and "<strong>Меню" not in step2,
          "и без дефолтного allauth-меню")

    # ПОВТОР — ОДНИМ КЛИКОМ. Раньше «не пришло письмо» вело на пустую форму, и
    # адрес приходилось вводить заново ровно тогда, когда у клиента уже что-то
    # пошло не так. Проверяем И то, что почта лежит на странице скрытым полем,
    # И то, что отправка действительно порождает НОВОЕ письмо: первое без
    # второго — просто разметка.
    check(email in step2, "на экране кода видно, на какой адрес ушёл код")

    # «НАЧАТЬ ЗАНОВО» ОБЯЗАН РАБОТАТЬ, А НЕ БЫТЬ НАДПИСЬЮ. Пока код в процессе,
    # allauth запирает клиента на этом экране: запрос нового кода редиректит
    # обратно, письма не отправив (проверено — и поэтому кнопки «отправить ещё
    # раз» здесь нет, она молчала бы). Сбрасывает ожидание только logout.
    # Проверяем ИСХОД: после сброса форма почты открывается и новый код уходит.
    restart = Client()
    restart.post("/accounts/login/code/", {"email": email})
    stuck = restart.get("/accounts/login/code/")
    check(stuck.status_code == 302,
          "пока код в процессе, форма почты действительно заперта (так у allauth)",
          f"code={stuck.status_code}")
    restart.post("/accounts/logout/", {"next": "/accounts/login/code/"})
    freed = restart.get("/accounts/login/code/")
    before = len(mail.outbox)
    restart.post("/accounts/login/code/", {"email": email})
    check(freed.status_code == 200 and len(mail.outbox) == before + 1,
          "«начать заново» разблокирует форму и присылает новый код",
          f"form={freed.status_code} писем {before}->{len(mail.outbox)}")
    # Вход идёт по коду ИМЕННО ЭТОЙ сессии (первое письмо): проверка «начать
    # заново» выше работала в отдельном клиенте и положила в общий outbox свои
    # письма — взять оттуда последнее значило бы войти чужим кодом.
    if found:
        entered = c.post("/accounts/login/code/confirm/", {"code": found.group(1)})
        cabinet = c.get("/app/")
        check(cabinet.status_code == 200,
              "по коду из письма клиент попадает в кабинет",
              f"confirm={entered.status_code} app={cabinet.status_code}")
        check(org.display_name in cabinet.content.decode(),
              "и это ЕГО кабинет (видит свою организацию)")

    # --- 3b. кнопка «ВОЙТИ» в шапке ведёт на живой вход ----------------------
    # Ссылка в шапке раньше вела на парольную страницу. После редиректа она не
    # сломалась бы молча — она бы просто ходила лишний хоп; но если однажды её
    # направят «ко входу» на сам себя, получится петля. Проверяем ИСХОД, а не
    # адрес: по ссылке из шапки клиент попадает на работающую форму.
    fresh = Client()
    landing = fresh.get("/")
    link = re.search(r'href="([^"]*)"[^>]*>\s*ВОЙТИ', landing.content.decode())
    check(link is not None, "в шапке есть кнопка входа")
    if link:
        landed = fresh.get(link.group(1), follow=True)
        text = landed.content.decode()
        check(landed.status_code == 200 and 'name="email"' in text
              and 'type="password"' not in text,
              "по кнопке из шапки открывается вход по коду (без пароля)",
              f"code={landed.status_code} url={link.group(1)}")

    # --- 4. пароль нельзя завести -------------------------------------------
    reset = Client().get("/accounts/password/reset/")
    check(reset.status_code == 302,
          "сброс пароля уведён — завести пароль нельзя", f"code={reset.status_code}")

    # --- 5. АДМИНКА НЕ ЗАТРОНУТА -------------------------------------------
    admin_login = Client().get(f"/{settings.ADMIN_PATH}/login/")
    admin_body = admin_login.content.decode()
    check(admin_login.status_code == 200 and 'type="password"' in admin_body,
          "у админки поле пароля ОСТАЛОСЬ (её вход отдельный)",
          f"code={admin_login.status_code}")
    check("otp_token" in admin_body,
          "и второй фактор админки на месте")

    print("=" * 60)
    if not ok:
        raise SystemExit("passwordless login not correct")
    print("passwordless OK — пароля у клиента нет нигде, вход по коду из письма, "
          "админка со своим паролем и 2FA цела")
    return 0


if __name__ == "__main__":
    sys.exit(main())
