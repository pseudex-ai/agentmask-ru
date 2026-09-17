"""Аналитика: то, что ломается молча и замечается через месяц.

Три утверждения, и каждое из них — обещание, данное на экране и в политике.
Экран говорит «без куки, IP не хранится, боты отфильтрованы»; без проверки все
три держатся на одном присваивании.

    cd storefront && .venv/bin/python test_analytics.py
"""

import datetime
import io
import os
import subprocess
import sys
import tempfile

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_SECRET_KEY"] = "analytics-test"
    _tmpdir = tempfile.mkdtemp(prefix="pseudex-analytics-")
    os.environ["PSEUDEX_DB_PATH"] = os.path.join(_tmpdir, "a.sqlite3")
    # СОЛЬ — В СВОЙ ФАЙЛ, А НЕ В ОБЩИЙ /tmp. Иначе проверки одного запуска
    # удаляют соль другого (смена суток ниже стирает вчерашний файл), и тест
    # начинает зависеть от порядка и от того, что успело полежать в /tmp.
    os.environ["PSEUDEX_ANALYTICS_SALT_FILE"] = os.path.join(_tmpdir, "salt")

    import django
    django.setup()
    from django.core.management import call_command
    from django.utils import timezone

    from ops import collect
    from ops.analytics_models import Funnel, Visit, VisitDay

    call_command("migrate", verbosity=0, interactive=False)

    # --- отпечаток --------------------------------------------------------
    a = collect.fingerprint("pseudex.ru", "203.0.113.7", "Mozilla/5.0 Chrome")
    again = collect.fingerprint("pseudex.ru", "203.0.113.7", "Mozilla/5.0 Chrome")
    other = collect.fingerprint("pseudex.ru", "203.0.113.8", "Mozilla/5.0 Chrome")
    check("один и тот же посетитель в одних сутках — один отпечаток", a == again)
    check("разные адреса — разные отпечатки", a != other)
    check("в отпечатке нет ни адреса, ни user-agent",
          "203.0.113" not in a and "Chrome" not in a and len(a) == 16, a)

    # ОДИН ОТПЕЧАТОК НА ВСЕ ВОРКЕРЫ. Витрина поднимает gunicorn с
    # `--workers 2`, и соль, сгенерированная в каждом процессе заново, теряла
    # связь между визитом и регистрацией примерно в половине случаев — вместе с
    # метками, реферером и `yclid`, на котором держатся офлайн-конверсии.
    # ПРОВЕРЯЕМ ДРУГИМ ПРОЦЕССОМ, А НЕ ВТОРЫМ ВЫЗОВОМ: внутри одного процесса
    # одинаковый ответ получается и у сломанной версии, поэтому такой тест не
    # мог бы провалиться по той причине, ради которой стоит.
    # ИДЁТ ДО СМЕНЫ СУТОК: та стирает вчерашний файл соли, а вместе с ним и
    # предмет этой проверки.
    probe = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r);"
         "import django; django.setup();"
         "from ops import collect;"
         "print(collect.fingerprint('pseudex.ru', '203.0.113.7',"
         " 'Mozilla/5.0 Chrome'))" % os.getcwd()],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "pseudex_site.settings"})
    from_worker = probe.stdout.strip()
    check("второй воркер считает тот же отпечаток, что и первый",
          from_worker == a,
          f"первый {a!r}, второй {from_worker!r} — {probe.stderr.strip()[-160:]}")

    # ЗАВТРА СВЯЗАТЬ НЕЛЬЗЯ. Это обещание политики, и держится оно не на
    # аккуратности, а на том, что соль уничтожена вместе со сменой суток.
    # СУТКИ СДВИГАЮТСЯ ЧАСАМИ, А НЕ СБРОСОМ КЭША: соль теперь одна на контейнер
    # и лежит файлом, поэтому «забыть её» внутри тех же суток — это прочитать
    # ту же соль, а не проверить следующую.
    real_time = collect.time.time
    try:
        collect.time.time = lambda: real_time() + 86400
        collect._salt_day = -1
        tomorrow = collect.fingerprint("pseudex.ru", "203.0.113.7",
                                       "Mozilla/5.0 Chrome")
    finally:
        collect.time.time = real_time
        collect._salt_day = -1
    check("после смены суток тот же человек неузнаваем", a != tomorrow,
          "соль суток не воспроизводится на следующий день")

    # --- боты -------------------------------------------------------------
    html = "text/html,application/xhtml+xml"
    cases = [
        ("Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36", html, False),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148 Safari/604.1", html, False),
        ("Mozilla/5.0 (compatible; YandexBot/3.0)", html, True),
        ("Mozilla/5.0 (compatible; GPTBot/1.0)", html, True),
        ("curl/8.4.0", "*/*", True),
        ("python-requests/2.31.0", "*/*", True),
        # БЕЗ СПИСКА: браузер всегда просит html, скрипт — нет. Этот сигнал не
        # устаревает, в отличие от списка имён.
        ("Mozilla/5.0 (Windows NT 10.0) Gecko/20100101 Firefox/121.0", "*/*", True),
        ("", html, True),
    ]
    wrong = [ua[:34] for ua, accept, expected in cases
             if collect.looks_like_bot(ua, accept) != expected]
    check("бот отличается от человека по двум сигналам", not wrong, str(wrong))

    # ЯНДЕКС-БРАУЗЕР — НЕ ЯНДЕКС-БОТ. Шаблон `yandex` без оговорки выбросил бы
    # живых людей, а в России их много.
    check("Яндекс.Браузер не принят за бота",
          not collect.looks_like_bot(
              "Mozilla/5.0 (Windows NT 10.0) Chrome/120 YaBrowser/24.1 Safari/537.36", html))

    # --- источник ---------------------------------------------------------
    own = {"pseudex.ru"}
    check("собственный переход не считается источником",
          collect.referrer_host_of("https://pseudex.ru/detection", own) == "")
    check("www отбрасывается, чтобы один канал не считался двумя",
          collect.referrer_host_of("https://www.habr.com/ru/x", own) == "habr.com")
    check("из реферера берётся только хост, без запроса",
          collect.referrer_host_of("https://ya.ru/search?text=секрет", own) == "ya.ru",
          "поисковый запрос опознаёт человека, хост — нет")

    # --- свёртка ----------------------------------------------------------
    day = timezone.localdate() - datetime.timedelta(days=2)
    when = timezone.make_aware(datetime.datetime.combine(day, datetime.time(12, 0)))
    for i in range(10):
        Visit.objects.create(at=when, visitor=f"p{i % 4:015d}", path="/",
                             referrer_host="habr.com" if i < 6 else "ya.ru",
                             device="десктоп", browser="Chrome", os="macOS")
    Visit.objects.create(at=when, visitor="botbotbotbotbot", path="/", is_bot=True)

    call_command("rollup_analytics", days=3, verbosity=0)
    total = VisitDay.objects.get(day=day, dimension="total")
    check("свёртка считает просмотры и посетителей",
          total.visits == 10 and total.visitors == 4,
          f"{total.visits} просмотров, {total.visitors} посетителей")
    check("бот в свёртку не попал", total.visits == 10, "посеяно 10 живых + 1 бот")
    habr = VisitDay.objects.get(day=day, dimension="referrer", value="habr.com")
    check("разрез по источнику свёрнут", habr.visits == 6, str(habr.visits))

    # ИДЕМПОТЕНТНОСТЬ. Команда пойдёт по расписанию, повторится после падения и
    # будет запущена руками. Дописывание удвоило бы числа на первом же повторе.
    call_command("rollup_analytics", days=3, verbosity=0)
    call_command("rollup_analytics", days=3, verbosity=0)
    # ПО КЛЮЧУ, А НЕ ПО ОБЪЕКТУ: свёртка пересчитывает сутки ЦЕЛИКОМ, удаляя и
    # создавая строки заново, поэтому `refresh_from_db` на старом объекте
    # обязан не найти его. Это и есть доказательство, что пересчёт настоящий, а
    # не дописывание.
    total = VisitDay.objects.get(day=day, dimension="total")
    check("повторная свёртка не удваивает", total.visits == 10, str(total.visits))
    check("и не плодит строк",
          VisitDay.objects.filter(day=day, dimension="referrer").count() == 2,
          str(VisitDay.objects.filter(day=day, dimension="referrer").count()))

    # СНАЧАЛА СВЕРНУТЬ, ПОТОМ УДАЛИТЬ. Обратный порядок однажды удалил бы сутки,
    # которые ещё не свёрнуты, и дыру в ряду восстановить было бы неоткуда.
    call_command("rollup_analytics", days=3, keep_days=1, verbosity=0)
    check("сырьё старше срока удалено", not Visit.objects.filter(at__date=day).exists())
    check("а свёртка этих же суток осталась",
          VisitDay.objects.filter(day=day).exists(),
          "свёртка живёт вечно, сырьё — нет")

    # --- воронка: шаг, который не записывается ----------------------------
    #
    # ИМЕННО ЭТОТ ПРИБОР НАШЁЛ БЫ `first_mask` САМ. Шаг был объявлен в модели и
    # не записан ничем, воронка обрывалась на «поднял контейнер», а следующий
    # её шаг стоял ненулевым — то есть на экране это читалось как провал
    # конверсии и посылало чинить продукт вместо аналитики.
    ladder = [{"count": 10}, {"count": 6}, {"count": 0}, {"count": 3}]
    flagged = collect.flag_unwired(ladder)
    check("ноль, за которым стоит ненулевой шаг, назван не отвалом",
          flagged[2]["unwired"] is True,
          "заплатить, не замаскировав ни одного запроса, нельзя")
    check("а честный отвал в хвосте не оболган",
          [f["unwired"] for f in flagged] == [False, False, True, False],
          "последний ноль — это просто никто не дошёл")
    check("функция чистая — исходный список не тронут",
          "unwired" not in ladder[2], str(ladder[2]))

    # --- первое касание: атрибуция без куки -------------------------------
    #
    # МЕТКИ ПРИХОДЯТ НА ЛЕНДИНГ, А ФОРМА ОТПРАВЛЯЕТСЯ С ДРУГОЙ СТРАНИЦЫ. Обычное
    # решение — положить первое касание в сессию, то есть поставить куку;
    # лендинг обещает, что куки не ставит. Здесь связь берётся из визитов того
    # же суточного отпечатка, и это работает ровно сутки — честная цена.
    me = "attributed00001"
    base = timezone.now() - datetime.timedelta(minutes=30)
    Visit.objects.create(at=base, visitor=me, path="/",
                         referrer_host="yandex.ru", utm_source="yandex",
                         utm_medium="cpc", utm_campaign="pseudex-brand")
    Visit.objects.create(at=base + datetime.timedelta(minutes=5), visitor=me,
                         path="/detection", referrer_host="")
    touch = collect.first_touch(me, since_hours=24)
    check("источник взят из помеченного визита",
          touch["source_utm_campaign"] == "pseudex-brand"
          and touch["source_utm_source"] == "yandex", str(touch))
    check("посадочная страница — та, с которой начали, а не последняя",
          touch["source_landing"] == "/", touch["source_landing"])

    # ВОЗВРАТ ЧЕРЕЗ ДОКУМЕНТАЦИЮ НЕ ДОЛЖЕН ПЕРЕПИСЫВАТЬ ИСТОЧНИК. Человек ушёл
    # читать и вернулся — последний визит назвал бы источником нас самих, и
    # кампания, которая за него заплатила, не получила бы ни одной регистрации.
    Visit.objects.create(at=base + datetime.timedelta(minutes=20), visitor=me,
                         path="/", referrer_host="habr.com")
    again = collect.first_touch(me, since_hours=24)
    check("поздний переход не перебивает первое касание",
          again["source_utm_campaign"] == "pseudex-brand"
          and again["source_referrer"] == "yandex.ru", str(again))

    # ЧУЖОЙ ОТПЕЧАТОК — ЧУЖОЙ ИСТОЧНИК, и пустой ответ здесь правильный:
    # человек, пришедший по прямой ссылке, не должен унаследовать чужую метку.
    check("незнакомому посетителю источник не приписывается",
          collect.first_touch("neverseen00001", since_hours=24) == {},
          "иначе первая же кампания собрала бы все прямые заходы")

    # --- утренняя сводка: телеграм — ЧУЖОЙ сервис -------------------------
    #
    # «ПЕРСОНАЛЬНЫХ ДАННЫХ ЗДЕСЬ НЕТ» СТОЯЛО В ДОКСТРИНГЕ И НЕ ПРОВЕРЯЛОСЬ
    # НИЧЕМ. Обещание несёт юридический вес: уведомление в РКН утверждает, что
    # трансграничной передачи персональных данных нет, а телеграм —
    # единственный иностранный канал, куда продукт вообще что-либо отправляет.
    # Утверждение такого веса не может держаться на аккуратности автора.
    #
    # ДАННЫЕ ОБЯЗАНЫ ЛЕЖАТЬ В БАЗЕ, ИНАЧЕ ПРОВЕРКА ПУСТАЯ. Отсутствие почты в
    # сводке не значит ничего, если почты нет и в базе, — поэтому клиент здесь
    # настоящий, со всеми полями, до которых сводка теоретически могла бы
    # дотянуться, и каждая строка, способная их вынести, обязана напечататься.
    from accounts.models import Membership, Organization, User
    from billing.models import Invoice, Plan, Subscription

    call_command("seed_plans", verbosity=0)
    plan = Plan.objects.get(code="industrial")

    PROBE_EMAIL = "probe-utechka@example.org"
    PROBE_ORG = "Ромашка-Проба"
    PROBE_LEGAL = f"ООО «{PROBE_ORG}»"
    PROBE_INN = "7712345678"
    PROBE_ADDRESS = "ул. Пробная, д. 1"

    org = Organization.objects.create(
        display_name=PROBE_ORG, legal_name=PROBE_LEGAL, inn=PROBE_INN,
        legal_address=f"г. Москва, {PROBE_ADDRESS}")
    Membership.objects.create(
        user=User.objects.create_user(email=PROBE_EMAIL), organization=org)

    now = timezone.now()
    today = timezone.localdate()
    Subscription.objects.create(
        organization=org, plan=plan, state=Subscription.TRIAL,
        trial_ends_at=now + datetime.timedelta(days=2),
        current_period_end=now + datetime.timedelta(days=30))

    def probe_invoice(number: str, **fields) -> Invoice:
        return Invoice.objects.create(
            organization=org, number=number,
            period_start=today - datetime.timedelta(days=30), period_end=today,
            plan_amount=plan.monthly_price, total=plan.monthly_price, **fields)

    probe_invoice("PS-PROBE-PAID", state=Invoice.PAID, paid_at=now)
    probe_invoice("PS-PROBE-OVERDUE", state=Invoice.ISSUED,
                  due_at=today - datetime.timedelta(days=1))
    probe_invoice("PS-PROBE-STUCK", state=Invoice.PAID, paid_at=now,
                  service_resumed_at=None)

    for i in range(3):
        Visit.objects.create(at=now - datetime.timedelta(hours=1),
                             visitor=f"d{i:015d}", path="/",
                             referrer_host="habr.com")
    Funnel.objects.create(step=Funnel.LANDING, at=now, organization_id=org.id)
    Funnel.objects.create(step=Funnel.SIGNUP_SUBMITTED, at=now,
                          detail="industrial", organization_id=org.id)
    Funnel.objects.create(step=Funnel.SIGNUP_REFUSED, at=now,
                          detail="одноразовая почта")

    digest = io.StringIO()
    call_command("daily_digest", dry_run=True, stdout=digest)
    text = digest.getvalue()

    # СНАЧАЛА ПОЛОЖИТЕЛЬНАЯ ПОЛОВИНА, И ПО ТОМУ ЖЕ ТЕКСТУ. Пустая сводка не
    # содержит ни одной почты и прошла бы отрицательную проверку не заметив
    # этого; красной она станет только тогда, когда есть что выносить.
    rendered = [mark for mark in
                ("Посетителей:", "Воронка:", "Оплачено:", "Просрочено счетов:",
                 "обслуживание НЕ возобновлено", "Форма отказала:",
                 "Пробный период кончается")
                if mark in text]
    check("сводка напечатала все строки, способные вынести ПД",
          len(rendered) == 7, f"{len(rendered)} из 7: {', '.join(rendered)}")

    leaked = [name for name, value in (
        ("почта", PROBE_EMAIL), ("название", PROBE_ORG),
        ("юр. название", PROBE_LEGAL), ("ИНН", PROBE_INN),
        ("адрес", PROBE_ADDRESS)) if value in text]
    check("и ни одного персонального поля в ней нет", not leaked,
          f"утекло: {', '.join(leaked)}" if leaked else
          "почта, название, ИНН и адрес лежат в базе и в канал не попали")

    # --- деньги и отток: два числа, которые легко посчитать неправильно ----
    #
    # ЧИТАЕТСЯ КОНТЕКСТ ВЬЮ, А НЕ РАЗМЕТКА, и ради этого включается тестовая
    # инструментовка шаблонов: без неё `response.context` — None, потому что
    # сигнал отрисовки никто не подменял. Проверять арифметику по тексту
    # страницы нельзя вовсе: Django локализует числа, и «3900» превращается в
    # «3 900» с неразрывным пробелом — тест краснел бы от настройки языка.
    from django.test.utils import setup_test_environment
    setup_test_environment()

    from django.test import Client as _Client

    from accounts.models import Membership as _M, Organization as _O, User as _U
    from billing.models import Invoice as _I, Plan as _P, Subscription as _S
    from ops.analytics_models import UsageDay

    call_command("seed_plans", verbosity=0)
    staff = _U.objects.create_superuser(email="ops@pseudex.local", password="ops-pass-1")
    console = _Client()
    # СО ВТОРЫМ ФАКТОРОМ: консоль закрыта `otp_required`, и один `force_login`
    # её больше не открывает — страница отвечает редиректом, а `.context` в
    # тесте становится None. Ровно на этом проверка и падала.
    from testkit_otp import login_staff
    login_staff(console, staff)

    work = _P.objects.get(code="work")
    now2 = timezone.now()

    # КЛИЕНТ, КУПИВШИЙ ПО СТАРОЙ ЦЕНЕ. Снимок условий — 3900; тариф после
    # правки конструктора стоит вдвое дороже, но этот клиент платит старое до
    # продления. MRR по прайсу показал бы выручку, которой нет.
    old_terms = _O.objects.create(display_name="Старые условия")
    _S.objects.create(organization=old_terms, plan=work, state=_S.ACTIVE,
                      terms_monthly_price=work.monthly_price,
                      trial_ends_at=now2 - datetime.timedelta(days=1),
                      current_period_end=now2 + datetime.timedelta(days=20))
    was_price = work.monthly_price
    work.monthly_price = was_price * 2
    work.save(update_fields=["monthly_price"])

    # ЧИТАЕТСЯ КОНТЕКСТ, А НЕ РАЗМЕТКА. Первая версия искала «3900» в теле
    # страницы и краснела на ровном месте: Django локализует числа и печатает
    # «3 900» неразрывным пробелом. Тест, ломающийся от настройки языка,
    # проверяет верстальщика, а не арифметику.
    money = console.get("/admin/ops/analytics/?days=30").context["money"]
    check("MRR считается по снимку условий, а не по цене тарифа",
          money["mrr"] == was_price,
          f"MRR {money['mrr']} ₽ при снимке {was_price} ₽ и тарифе {was_price * 2} ₽")
    work.monthly_price = was_price
    work.save(update_fields=["monthly_price"])

    # ЗАМОЛЧАВШИЙ. Накопленное не двигалось неделю — на экране флота он
    # неотличим от работающего, потому что счётчик монотонен.
    silent = _O.objects.create(display_name="Замолчавший")
    _S.objects.create(organization=silent, plan=work, state=_S.ACTIVE,
                      terms_monthly_price=work.monthly_price,
                      trial_ends_at=now2 - datetime.timedelta(days=30),
                      current_period_end=now2 + datetime.timedelta(days=10))
    busy = _O.objects.create(display_name="Работающий")
    _S.objects.create(organization=busy, plan=work, state=_S.ACTIVE,
                      terms_monthly_price=work.monthly_price,
                      trial_ends_at=now2 - datetime.timedelta(days=30),
                      current_period_end=now2 + datetime.timedelta(days=10))
    today2 = timezone.localdate()
    for back in range(10):
        day = today2 - datetime.timedelta(days=back)
        UsageDay.objects.create(organization_id=silent.id, day=day, requests=50_000)
        UsageDay.objects.create(organization_id=busy.id, day=day,
                                requests=50_000 - back * 700)

    quiet = console.get("/admin/ops/analytics/?days=30").context["quiet"]
    named = {row["org_id"]: row["days"] for row in quiet}
    check("замолчавший клиент назван, хотя счётчик у него большой",
          named.get(silent.id) == 9,
          f"молчит {named.get(silent.id)} дн. — монотонный итог делает его "
          f"неотличимым от живого")
    check("а работающий в список оттока не попал",
          busy.id not in named, "у него расход растёт каждые сутки")

    # --- аналитика: текст на странице выведен из настройки ------------------
    #
    # НА ЛЕНДИНГЕ СТОЯЛО СИЛЬНОЕ ОБЕЩАНИЕ — «аналитики и счётчиков на сайте нет
    # вообще… поэтому нет и баннера», — и охраняло его ничто. Включение
    # счётчика сделало бы фразу ложной, а заметил бы это первый внимательный
    # читатель: то есть ровно тот клиент, ради которого продукт и покупают.
    # Теперь абзац выводится из `PSEUDEX_ANALYTICS_MODE`, и проверка ниже
    # краснеет, если вывод перестанет следовать за режимом.
    from django.test import override_settings

    def page(mode: str, path: str, client=None, metrika: str = "", follow: bool = True):
        settings_analytics = {
            "mode": mode, "host": "https://a.pseudex.ru", "key": "phc_probe",
            "stores_id": mode == "full", "records_sessions": mode == "full"}
        with override_settings(ANALYTICS=settings_analytics, METRIKA_ID=metrika):
            answer = (client or _Client()).get(path, follow=follow)
        return answer

    claims = {
        "off": "Аналитики и счётчиков на сайте нет вообще",
        "full": "спрашиваем согласия баннером",
    }
    wrong = []
    for mode, phrase in claims.items():
        html = page(mode, "/").content.decode()
        loaded = "analytics.js" in html
        if (mode == "off") == loaded:
            wrong.append(f"{mode}: скрипт={loaded}")
        if phrase not in html:
            wrong.append(f"{mode}: нет фразы «{phrase}»")
        # И НАОБОРОТ: текст ДРУГОГО режима не должен стоять на странице.
        for other, alien in claims.items():
            if other != mode and alien in html:
                wrong.append(f"{mode}: на странице фраза режима {other}")
    check("текст про куки следует за режимом аналитики, в обе стороны",
          not wrong, "; ".join(wrong) or "off / full — каждый свой абзац")

    # ЗАКРЫТЫЕ СТРАНИЦЫ НЕ ПОЛУЧАЮТ НИ СКРИПТА, НИ РАЗРЕШЕНИЯ В CSP. На экране
    # кабинета префиксы ключей и суммы счетов; запись сессии сделала бы их
    # копию, которую никто не заказывал. Свойство держится ДВУМЯ механизмами —
    # шаблоном и заголовком, — и проверяются оба: одного без другого мало.
    cabinet_user = _U.objects.create_user(email="analytics-probe@example.org")
    cabinet_org = _O.objects.create(display_name="Кабинет пробы")
    _M.objects.create(user=cabinet_user, organization=cabinet_org)
    signed = _Client()
    signed.force_login(cabinet_user)

    public = page("full", "/")
    private = page("full", "/app/", signed)
    csp_of = lambda answer: next(
        (part for part in answer.get("Content-Security-Policy", "").split("; ")
         if part.startswith("script-src ")), "")
    check("на публичной странице скрипт есть и CSP его пускает",
          "analytics.js" in public.content.decode()
          and "a.pseudex.ru" in csp_of(public), csp_of(public))
    check("в кабинете нет ни скрипта, ни разрешения в CSP",
          "analytics.js" not in private.content.decode()
          and "a.pseudex.ru" not in csp_of(private),
          f"код={private.status_code} csp={csp_of(private)}")

    # ── ЯНДЕКС.МЕТРИКА: ТРЕТЬЯ СТОРОНА, ТЕ ЖЕ ДВА ПРАВИЛА ─────────────────
    #
    # ТЕКСТ ОБЕЩАЕТ ОТСУТСТВИЕ СЧЁТЧИКА ПО ИМЕНИ — «ни Метрики, ни Google
    # Analytics». Включённый счётчик обязан менять текст, иначе сайт, продающий
    # минимизацию данных, публикует неправду о себе ровно там, где её ищут:
    # этот ответ читает служба безопасности клиента.
    #
    # ПОЭТОМУ ПРОВЕРЯЮТСЯ ОБЕ ПОЛОВИНЫ: что при включённом счётчике текст его
    # называет — И что при выключенном обещание на месте. Одной половины мало:
    # первая без второй пропустила бы «текст всегда говорит про Метрику».
    KEY = "98765432"
    off_no = page("off", "/").content.decode()
    full_no = page("full", "/").content.decode()
    on_off = page("off", "/", metrika=KEY).content.decode()
    on_full = page("full", "/", metrika=KEY).content.decode()

    metrika_wrong = []
    if "Яндекс.Метрика" not in on_off:
        metrika_wrong.append("off+счётчик: текст не назвал Метрику")
    if "Аналитики и счётчиков на сайте нет вообще" in on_off:
        metrika_wrong.append("off+счётчик: осталось обещание «счётчиков нет вообще»")
    if KEY not in on_full:
        metrika_wrong.append("full+счётчик: номер не доехал до загрузчика")
    if f'data-metrika-id="{KEY}"' not in on_full:
        metrika_wrong.append("full+счётчик: номер не в том атрибуте")
    # И НАОБОРОТ: без настройки ни номера, ни упоминания.
    if KEY in full_no or KEY in off_no:
        metrika_wrong.append("без настройки: номер всё равно на странице")
    if "Яндекс.Метрика" in full_no:
        metrika_wrong.append("без настройки: текст обещает Метрику, которой нет")
    check("текст и разметка следуют за настройкой Метрики, в обе стороны",
          not metrika_wrong, "; ".join(metrika_wrong) or "вкл/выкл — каждое своё")

    # ПРАВИЛО ЗАКРЫТЫХ СТРАНИЦ ДЕРЖИТСЯ CSP, А НЕ ШАБЛОНОМ. Шаблон можно
    # поправить и забыть про заголовок; заголовок исполняет браузер, поэтому
    # проверяем именно его — и обязательно с ВКЛЮЧЁННЫМ счётчиком, иначе
    # проверка ничего не говорит о том случае, ради которого стоит.
    check("CSP публичной страницы пускает mc.yandex.ru при счётчике",
          "https://mc.yandex.ru" in csp_of(page("off", "/", metrika=KEY)),
          csp_of(page("off", "/", metrika=KEY)))
    check("а без счётчика CSP его не разрешает",
          "mc.yandex.ru" not in csp_of(page("off", "/"))
          and "mc.yandex.ru" not in csp_of(page("full", "/")),
          "разрешение не должно появляться само")
    check("в кабинете счётчика нет даже включённого",
          KEY not in page("off", "/app/", signed, metrika=KEY).content.decode()
          and "mc.yandex.ru" not in csp_of(page("off", "/app/", signed, metrika=KEY)),
          "на экране кабинета префиксы ключей и суммы счетов")

    # ── И ПОЛИТИКА ОБРАБОТКИ: ЭТО ДОКУМЕНТ, А НЕ ТЕКСТ ЛЕНДИНГА ──────────
    # Раздел 9bis утверждает «счётчики третьих сторон не используются», а
    # раздел 6 — что данные третьим лицам не передаются. С включённой Метрикой
    # оба утверждения становятся неправдой, и читает их служба безопасности
    # клиента, то есть человек, который придёт с этим вопросом.
    policy_on = page("off", "/policy", metrika=KEY).content.decode()
    policy_off = page("off", "/policy").content.decode()
    check("политика называет Метрику, когда счётчик включён",
          "Яндекс.Метрики" in policy_on and "Вебвизор" in policy_on,
          "раздел 9bis обязан следовать за настройкой, как и лендинг")
    check("и обещает отсутствие счётчиков, когда он выключен",
          "Счётчики третьих сторон на сайте не используются" in policy_off
          and "Яндекс.Метрики" not in policy_off,
          "выключенный счётчик не должен упоминаться как работающий")
    check("политика открывается в обеих настройках",
          "9bis" in policy_on and "9bis" in policy_off)

    # ── СТРАНИЦЫ С СЕКРЕТОМ: НИ ОДНОГО СЧЁТЧИКА, НИ НАШЕГО, НИ ЧУЖОГО ─────
    #
    # `/activate?t=…` несёт подписанный токен, названный в `views.activate`
    # «работающий логин на 24 часа». Счётчик отправляет `location.href` — то
    # есть токен ушёл бы третьей стороне ДАЖЕ С ВЫКЛЮЧЕННЫМ Вебвизором.
    # `/welcome` показывает клиенту лицензионный ключ прямо в разметке.
    #
    # ДЫРА БЫЛА И ДО МЕТРИКИ: своя аналитика шлёт тот же `location.href`, просто
    # на наш сервер. Поэтому проверяются ОБА счётчика, а не только новый.
    from django.conf import settings
    from pseudex_site.context import counters_allowed

    boundary = {"/activate": False, "/welcome": False, "/": True, "/detection": True,
                "/app/": False, "/accounts/login/": False,
                f"/{settings.ADMIN_PATH}/": False}
    wrong_boundary = [f"{p}={counters_allowed(p)}" for p, want in boundary.items()
                      if counters_allowed(p) != want]
    check("граница счётчиков исключает закрытое и страницы с секретом",
          not wrong_boundary, "; ".join(wrong_boundary) or "список совпал")

    for path in ("/activate", "/welcome"):
        # Без `follow`: иначе редирект уводит на главную, где счётчик есть, и
        # проверка «счётчика нет» проходила бы на СОВСЕМ ДРУГОЙ странице.
        answer = page("full", path, metrika=KEY, follow=False)
        csp = csp_of(answer)
        check(f"{path}: CSP не разрешает ни Метрику, ни нашу аналитику",
              "mc.yandex.ru" not in csp and "a.pseudex.ru" not in csp, csp)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    print("аналитика OK — отпечаток суточный, IP не хранится, боты отделены, "
          "свёртка идемпотентна, в телеграм не уходит ни одного ПД, MRR по снимку "
          "условий, замолчавшие названы")
    return 0


if __name__ == "__main__":
    sys.exit(main())
