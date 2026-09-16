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
    # ЖИВАЯ СТРАНИЦА ВХОДА ТЕПЕРЬ ОДНА. Парольная форма и сброс пароля уведены
    # редиректом (вход без пароля, см. test_passwordless), поэтому проверять их
    # «брендовость» больше нечего — их не существует. Проверяем то, что клиент
    # действительно видит.
    pages = [("/accounts/login/code/","вход по коду")]
    for url, label in pages:
        r = c.get(url); h = r.content.decode()
        check(r.status_code == 200, f"{label}: 200", str(r.status_code))
        check("site.css" in h and 'class="brand"' in h, f"{label}: брендовый base.html")
        check("auth-card" in h, f"{label}: в брендовой карточке")
        check("Menu:" not in h and "<strong>Меню" not in h, f"{label}: нет дефолтного allauth-меню")
    # signup ведёт на лендинг, а не на голую форму allauth
    r = c.get("/accounts/signup/")
    check(r.status_code in (301, 302), "signup → редирект на лендинг", str(r.status_code))
    # Убранные парольные страницы не должны отдавать 200 «в брендовом каркасе» —
    # их не должно быть вовсе.
    for url, label in (("/accounts/login/", "парольный вход"),
                       ("/accounts/password/reset/", "сброс пароля")):
        code = c.get(url).status_code
        check(code in (301, 302), f"{label} уведён, а не отрисован", str(code))
    # МНОГОСТРОЧНЫЙ `{# #}` РЕНДЕРИТСЯ ВИДИМЫМ ТЕКСТОМ. Django-комментарий
    # `{# #}` ОДНОСТРОЧНЫЙ: как только он переносится на вторую строку, его
    # содержимое перестаёт быть комментарием и печатается клиенту. Так на
    # странице активации (её видит каждый новый клиент после письма) и на двух
    # экранах консоли висел текст про CSRF и про счётчики. Проверка статическая,
    # по всем шаблонам: отрисовать в тесте каждую страницу нельзя, а ошибка
    # класса «комментарий стал текстом» одинаково смертельна на любой из них.
    import pathlib, re
    leaking = []
    for tpl in pathlib.Path("templates").rglob("*.html"):
        for m in re.finditer(r"\{#(.*?)#\}", tpl.read_text(encoding="utf-8"), re.S):
            if "\n" in m.group(0):
                leaking.append(str(tpl))
                break
    check(not leaking, "нигде нет многострочного {# #} (он печатается клиенту)",
          ", ".join(leaking))

    print("=" * 60)
    if not ok: raise SystemExit("auth pages not branded")
    print("auth-style OK — страницы входа в брендовом каркасе, без голого allauth")
    return 0

if __name__ == "__main__":
    sys.exit(main())
