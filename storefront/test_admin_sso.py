"""Единый вход сотрудников (OIDC) на админку и /ops/.

Доказывает три вещи, каждая из которых — отдельный способ ошибиться:

  * SSO-вход С ПОДТВЕРЖДЁННЫМ вторым фактором открывает админку без TOTP-кода
    (иначе кнопка «войти через SSO» ведёт на экран второго фактора и смысла не
    имеет);
  * SSO-вход БЕЗ подтверждения второго фактора админку НЕ открывает: нет claim
    `amr` — нет пропуска. Это и есть fail closed: недоказанное MFA считается
    отсутствующим, и человек вводит код из приложения;
  * подобрать аккаунт может только существующий staff по своему email —
    незнакомый адрес и не-staff не получают ничего, и новых учёток не заводится.

Запуск:  cd storefront && .venv/bin/python test_admin_sso.py
"""
import os
import sys


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "admin-sso-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-sso-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    os.environ["PSEUDEX_ADMIN_PATH"] = "backstage"
    # ЕДИНСТВЕННОЕ ОТЛИЧИЕ ОТ БОЕВОЙ КОНФИГУРАЦИИ — ЭТОТ ФЛАГ. Всё остальное
    # (бэкенд, маршруты, шаблон) включается им же, поэтому тест проверяет ту
    # самую ветку, которая поедет на прод после решения.
    os.environ["PSEUDEX_OIDC_ENABLED"] = "1"
    os.environ["PSEUDEX_OIDC_ISSUER"] = "https://auth.example.test"
    os.environ["PSEUDEX_OIDC_CLIENT_ID"] = "storefront"
    os.environ["PSEUDEX_OIDC_CLIENT_SECRET"] = "test-secret"
    if os.path.exists("/tmp/pseudex-sso-test.db"):
        os.remove("/tmp/pseudex-sso-test.db")

    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client

    from pseudex_site.oidc import SSO_MFA_SESSION_KEY, PseudexOIDCBackend

    call_command("migrate", verbosity=0, run_syncdb=True)

    User = get_user_model()
    staff = User.objects.create_user(
        email="igor@pseudex.ru", password="x", is_staff=True, is_active=True)
    outsider = User.objects.create_user(
        email="customer@example.com", password="x", is_staff=False, is_active=True)

    failures = []

    def check(name, condition, why=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name}  {why}")
            failures.append(name)

    admin_url = "/backstage/"
    ops_url = "/backstage/ops/"

    print("\n— подбор аккаунта по токену —")
    backend = PseudexOIDCBackend()
    check("staff находится по email",
          list(backend.filter_users_by_claims({"email": "IGOR@pseudex.ru"})) == [staff],
          "регистр не должен решать")
    check("не-staff не подбирается",
          list(backend.filter_users_by_claims({"email": "customer@example.com"})) == [])
    check("незнакомый адрес не подбирается",
          list(backend.filter_users_by_claims({"email": "someone@else.ru"})) == [])
    check("пустой email не подбирает никого",
          list(backend.filter_users_by_claims({"email": ""})) == [])
    check("создание аккаунта из OIDC выключено",
          getattr(__import__("django.conf", fromlist=["settings"]).settings,
                  "OIDC_CREATE_USER", None) is False,
          "OIDC_CREATE_USER обязан быть False")

    print("\n— MFA берётся из токена, а не из воздуха —")
    backend._claims = {"amr": ["pwd", "mfa"]}
    check("amr с вторым фактором → подтверждено", backend._mfa_confirmed())
    backend._claims = {"amr": ["pwd", "otp"]}
    check("amr с otp (TOTP у Authelia) → подтверждено", backend._mfa_confirmed())
    backend._claims = {"amr": ["pwd", "hwk"]}
    check("amr с hwk (ключ) → подтверждено", backend._mfa_confirmed())
    backend._claims = {"amr": ["pwd"]}
    check("только пароль → НЕ подтверждено", not backend._mfa_confirmed())
    backend._claims = {}
    check("нет claim amr → НЕ подтверждено", not backend._mfa_confirmed())
    backend._claims = {"amr": "mfa"}
    check("amr строкой тоже читается", backend._mfa_confirmed())
    # kba — знание, то есть ПЕРВЫЙ фактор под другим именем. Считать его
    # вторым значило бы пропускать TOTP за один пароль.
    backend._claims = {"amr": ["pwd", "kba"]}
    check("kba (знание) вторым фактором НЕ считается", not backend._mfa_confirmed())

    print("\n— доступ в админку —")

    def client_with_sso(flag: bool) -> Client:
        c = Client()
        c.force_login(staff)
        if flag:
            session = c.session
            session[SSO_MFA_SESSION_KEY] = True
            session.save()
        return c

    r = client_with_sso(True).get(admin_url)
    check("SSO с MFA: админка открывается", r.status_code == 200, f"код {r.status_code}")
    r = client_with_sso(True).get(ops_url)
    check("SSO с MFA: /ops/ открывается", r.status_code == 200, f"код {r.status_code}")

    r = client_with_sso(False).get(admin_url)
    check("SSO без MFA: админка закрыта",
          r.status_code == 302 and "/login" in r.headers.get("Location", ""),
          f"код {r.status_code}")
    r = client_with_sso(False).get(ops_url)
    check("SSO без MFA: /ops/ закрыт",
          r.status_code == 302 and "/login" in r.headers.get("Location", ""),
          f"код {r.status_code}")

    print("\n— аварийный вход жив —")
    c = Client()
    c.force_login(outsider)
    r = c.get(ops_url)
    check("не-staff не в /ops/ даже с сессией",
          r.status_code == 302, f"код {r.status_code}")

    print("\n" + "=" * 60)
    if failures:
        print("SSO FAIL:", ", ".join(failures))
        return 1
    print("админский SSO OK — вход по токену с MFA пускает, без MFA не пускает, "
          "новых учёток не заводит")
    return 0


if __name__ == "__main__":
    sys.exit(main())
