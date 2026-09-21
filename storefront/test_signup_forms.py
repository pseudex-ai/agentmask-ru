"""КАЖДЫЙ ПУТЬ К РЕГИСТРАЦИИ НА ЛЕНДИНГЕ ОБЯЗАН ДОВОДИТЬ ДО КЛЮЧА.

ЧТО ЭТО ЛОВИТ. Форм регистрации на лендинге было ЧЕТЫРЕ — «Быстрый старт» и по
одной в каждой карточке тарифа. Карточная собирала одну галочку `consent`, а
сервер требует ещё и `terms`, то есть она НЕ МОГЛА сработать никогда: каждый,
кто регистрировался с прайса, упирался в «нужно принять оферту» и уходил. Тест
писался по живому отчёту владельца: галочка поставлена, кнопка нажата, ключа нет.

И ЭТО НЕ ТОЛЬКО ПОЛОМКА, НО И НАРУШЕНИЕ. С 01.09.2025 (156-ФЗ) согласие на
обработку ПД «оформляется отдельно от иных информации и (или) документов»: одна
галочка «согласие + политика + оферта» — совмещённое согласие, которое РКН
называет нарушением прямо, а штраф по ч. 2 ст. 13.11 КоАП считается за каждое
такое согласие.

ПОЧЕМУ ПРОВЕРКА БОЛЬШЕ НЕ СЧИТАЕТ ФОРМЫ. Стояло «форм не меньше двух», и это
описывало ПРЕЖНЮЮ РАСКЛАДКУ, а не требование. Требование другое: ни одна кнопка,
обещающая пробу, не должна вести в никуда. В новом дизайне форма одна, а кнопки
в карточках тарифов ведут к ней и подставляют выбранный тариф — тот класс ошибки
исчезает как таковой, и счётчик форм начал бы краснеть на верном продукте.
Поэтому считается ИСХОД: каждая форма действительно выпускает ключ, и каждая
кнопка пробы указывает на существующий якорь и на существующий публичный тариф.

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
    check(len(forms) >= 1, f"форма регистрации на лендинге есть: {len(forms)}",
          "без неё зарегистрироваться нельзя вовсе")

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
        # `value="1"` — сервер сверяет именно эту строку, а не факт наличия
        # поля. Галочка без значения ушла бы как "on" и молча не сработала.
        for field in ("consent", "terms"):
            check(f'name="{field}" value="1"' in form,
                  f"форма #{i}: у «{field}» значение 1",
                  "сервер сверяет строку «1»; без неё согласие не засчитается")

    # --- исход: каждая форма реально выпускает ключ -------------------------
    for i, form in enumerate(forms, 1):
        # Тариф — ПЕРВЫЙ пункт выпадашки, как отправил бы браузер без единого
        # клика. Сервер умолчания больше не подставляет: форма без тарифа это
        # сломанная форма, а не «Старт».
        select = re.search(r'<select[^>]*name="plan"[^>]*>(.*?)</select>', form, re.S)
        plan = re.search(r'<option[^>]*value="([^"]+)"', select.group(1)) if select else None
        data = {"email": f"form{i}@example.com"}
        if plan:
            data["plan"] = plan.group(1)
        for field in ("consent", "terms"):
            if f'name="{field}"' in form:
                data[field] = "1"
        # СБРОС АНТИ-АБУЗ ЛИМИТА МЕЖДУ ФОРМАМИ. На регистрацию стоит лимит
        # попыток с адреса — правильное поведение продукта, но тест, гоняющий
        # несколько форм подряд, упирается в него сам и краснеет на последней
        # «как будто форма сломана». Проверять надо форму, а не лимит.
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

    # --- кнопки в прайсе: ни одна не ведёт в никуда --------------------------
    # Бесплатный тариф — своя карточка и своя кнопка: он не публичный (не
    # товар), но выбрать его можно, и `signup_plans()` — тот же список, по
    # которому сервер принимает код. Кнопка и проверка читают один источник.
    from billing import services
    sellable = {plan.code for plan in services.signup_plans()}
    buttons = re.findall(r'<a[^>]*data-plan="([^"]+)"[^>]*>', page)
    check(len(buttons) == len(sellable),
          f"кнопок столько же, сколько тарифов в форме: {len(buttons)} и {len(sellable)}",
          "тариф без кнопки не продать, кнопка без тарифа — отказ сервера")
    check(set(buttons) == sellable,
          "каждая кнопка несёт тариф, который сервер примет",
          f"на странице {sorted(set(buttons))}, в форме {sorted(sellable)}")
    check("free" in buttons and buttons.index("free") == 0,
          "бесплатный тариф — первая карточка прайса",
          "иначе платные карточки снова читаются как «начать пробу»")
    check("НАЧАТЬ ПРОБУ" not in page,
          "платные карточки не обещают пробу — проба одна, на бесплатном")
    # Якорь, на который они ведут, обязан существовать — иначе нажатие ничего
    # не делает и человек просто остаётся стоять на прайсе.
    anchors = re.findall(r'<a[^>]*data-plan="[^"]+"[^>]*href="([^"]+)"', page) \
        or re.findall(r'<a[^>]*href="([^"]+)"[^>]*data-plan="[^"]+"', page)
    check(bool(anchors) and all(a == "#start" for a in anchors),
          "каждая кнопка ведёт к форме (#start)", str(sorted(set(anchors))))
    check('id="start"' in page, "и такой якорь на странице есть")

    print("=" * 60)
    if not ok:
        raise SystemExit("signup forms are not correct")
    print("signup-forms OK — форма собирает два согласия раздельно и заводит "
          "аккаунт, а каждая кнопка прайса ведёт к ней с тарифом, который сервер примет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
