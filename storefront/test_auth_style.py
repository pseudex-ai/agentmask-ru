"""Страницы входа/регистрации (django-allauth) — в брендовом каркасе, не голый HTML.

Ловит регресс: если шаблоны account/* или allauth/layouts/* удалят, allauth
вернётся к своим дефолтам («Меню:», serif, голые инпуты) — тот самый косяк.

Запуск:  cd storefront && .venv/bin/python test_auth_style.py
"""
import os, sys

def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "auth-style"; os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-authstyle.db"
    if os.path.exists("/tmp/pseudex-authstyle.db"): os.remove("/tmp/pseudex-authstyle.db")
    import django; django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    from django.test import Client
    c = Client(); ok = True
    def check(cond, name, d=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {d}" if d and not cond else "")); ok = ok and cond
    pages = [("/accounts/login/","вход"), ("/accounts/password/reset/","сброс пароля"),
             ("/accounts/login/code/","вход по коду")]
    for url, label in pages:
        r = c.get(url); h = r.content.decode()
        check(r.status_code == 200, f"{label}: 200", str(r.status_code))
        check("site.css" in h and 'class="brand"' in h, f"{label}: брендовый base.html")
        check("auth-card" in h, f"{label}: в брендовой карточке")
        check("Menu:" not in h and "<strong>Меню" not in h, f"{label}: нет дефолтного allauth-меню")
    # signup ведёт на лендинг, а не на голую форму allauth
    r = c.get("/accounts/signup/")
    check(r.status_code in (301, 302), "signup → редирект на лендинг", str(r.status_code))
    print("=" * 60)
    if not ok: raise SystemExit("auth pages not branded")
    print("auth-style OK — страницы входа в брендовом каркасе, без голого allauth")
    return 0

if __name__ == "__main__":
    sys.exit(main())
