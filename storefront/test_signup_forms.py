"""КАЖДАЯ форма регистрации на сайте обязана работать и собирать ДВА согласия.

ЧТО ЭТО ЛОВИТ, И ПОЧЕМУ ОДНОЙ ФОРМЫ ПРОВЕРИТЬ БЫЛО МАЛО. Форм регистрации на
лендинге НЕ ОДНА: есть «Быстрый старт» и по форме в каждой карточке тарифа
(«НАЧАТЬ ПРОБУ»). Карточная собирала одну галочку `consent`, а сервер требует
ещё и `terms` — то есть она НЕ МОГЛА сработать никогда: каждый, кто регистрировался
с прайса, упирался в «нужно принять оферту» и уходил. Тест писался по живому
отчёту владельца: галочка поставлена, кнопка нажата, ключа нет.

И ЭТО НЕ ТОЛЬКО ПОЛОМКА, НО И НАРУШЕНИЕ. С 01.09.2025 (156-ФЗ) согласие на
обработку ПД «оформляется отдельно от иных информации и (или) документов»: одна
галочка «согласие + политика + оферта» — совмещённое согласие, которое РКН
называет нарушением прямо, а штраф по ч. 2 ст. 13.11 КоАП считается за каждое
такое согласие. В главной форме это записано комментарием — и ровно это было
нарушено в соседней.

Проверяется ИСХОД, а не разметка: форма действительно отправляется и ключ
действительно выпускается. Форма, у которой «есть оба поля», но которая падает
на сервере, — это та же неработающая регистрация.

Запуск:  cd storefront && .venv/bin/python test_signup_forms.py
"""
import os
import re
import sys


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "signup-forms-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-signup-forms.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-signup-forms.db"):
        os.remove("/tmp/pseudex-signup-forms.db")
    import django
    django.setup()
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from django.test import Client

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    page = Client().get("/").content.decode()
    forms = re.findall(r"<form[^>]*action=\"/signup\"[^>]*>(.*?)</form>", page, re.S)
    check(len(forms) >= 2,
          f"на лендинге найдено форм регистрации: {len(forms)} (их больше одной)",
          "проверять только «Быстрый старт» — значит не проверять прайс")

    # --- разметка: две ОТДЕЛЬНЫЕ галочки в КАЖДОЙ форме ---------------------
    for i, form in enumerate(forms, 1):
        has_consent = 'name="consent"' in form
        has_terms = 'name="terms"' in form
        check(has_consent and has_terms,
              f"форма #{i}: собирает ОБА согласия (consent + terms)",
              f"consent={has_consent} terms={has_terms} — сервер требует оба, иначе форма мертва")
        # 156-ФЗ: согласие отдельно от договора. Одна галочка на всё — нарушение.
        boxes = len(re.findall(r'type="checkbox"', form))
        check(boxes >= 2,
              f"форма #{i}: согласие и оферта — РАЗНЫМИ галочками (156-ФЗ)",
              f"галочек {boxes}: одна на всё — совмещённое согласие")

    # --- исход: каждая форма реально выпускает ключ -------------------------
    # Разметка может быть верной, а регистрация всё равно падать. Отправляем
    # ровно те поля, что несёт форма, и смотрим, что ключ выпущен.
    for i, form in enumerate(forms, 1):
        plan = re.search(r'name="plan"[^>]*value="([^"]+)"', form)
        data = {"email": f"form{i}@example.com"}
        if plan:
            data["plan"] = plan.group(1)
        for field in ("consent", "terms"):
            if f'name="{field}"' in form:
                data[field] = "1"
        # СБРОС АНТИ-АБУЗ ЛИМИТА МЕЖДУ ФОРМАМИ. На регистрацию стоит лимит
        # попыток с адреса — правильное поведение продукта, но тест, гоняющий
        # четыре формы подряд, упирается в него сам и краснеет на последней «как
        # будто форма сломана». Проверять надо форму, а не лимит.
        from django.core.cache import cache
        cache.clear()
        client = Client()
        response = client.post("/signup", data, follow=True)
        body = response.content.decode()
        # Ищем КОНКРЕТНЫЕ отказы, а не подстроку «согласие на обработку» — она
        # есть на самом лендинге в подписи к галочке, и проверка ловила бы себя.
        failed = any(m in body for m in (
            "нужно принять оферту", "Без согласия на обработку",
            "Слишком много попыток", "Нужен рабочий email"))
        from accounts.models import Membership
        created = Membership.objects.filter(user__email=data["email"]).exists()
        check(created and not failed,
              f"форма #{i}: отправка ДЕЙСТВИТЕЛЬНО заводит аккаунт",
              f"аккаунт={created} ошибка_на_странице={failed}")

    print("=" * 60)
    if not ok:
        raise SystemExit("signup forms are not correct")
    print("signup-forms OK — все формы регистрации собирают два согласия "
          "раздельно и действительно выпускают ключ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
