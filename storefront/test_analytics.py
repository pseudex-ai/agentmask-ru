"""Аналитика: то, что ломается молча и замечается через месяц.

Три утверждения, и каждое из них — обещание, данное на экране и в политике.
Экран говорит «без куки, IP не хранится, боты отфильтрованы»; без проверки все
три держатся на одном присваивании.

    cd storefront && .venv/bin/python test_analytics.py
"""

import datetime
import os
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
    os.environ["PSEUDEX_DB_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="pseudex-analytics-"), "a.sqlite3")

    import django
    django.setup()
    from django.core.management import call_command
    from django.utils import timezone

    from ops import collect
    from ops.analytics_models import Visit, VisitDay

    call_command("migrate", verbosity=0, interactive=False)

    # --- отпечаток --------------------------------------------------------
    a = collect.fingerprint("pseudex.ru", "203.0.113.7", "Mozilla/5.0 Chrome")
    again = collect.fingerprint("pseudex.ru", "203.0.113.7", "Mozilla/5.0 Chrome")
    other = collect.fingerprint("pseudex.ru", "203.0.113.8", "Mozilla/5.0 Chrome")
    check("один и тот же посетитель в одних сутках — один отпечаток", a == again)
    check("разные адреса — разные отпечатки", a != other)
    check("в отпечатке нет ни адреса, ни user-agent",
          "203.0.113" not in a and "Chrome" not in a and len(a) == 16, a)

    # ЗАВТРА СВЯЗАТЬ НЕЛЬЗЯ. Это обещание политики, и держится оно не на
    # аккуратности, а на том, что соль уничтожена вместе со сменой суток.
    collect._salt_day = -1
    tomorrow = collect.fingerprint("pseudex.ru", "203.0.113.7", "Mozilla/5.0 Chrome")
    check("после смены соли тот же человек неузнаваем", a != tomorrow,
          "соль живёт в памяти процесса и уничтожается сменой суток")

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

    print()
    if FAILURES:
        print(f"{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    print("аналитика OK — отпечаток суточный, IP не хранится, боты отделены, "
          "свёртка идемпотентна")
    return 0


if __name__ == "__main__":
    sys.exit(main())
