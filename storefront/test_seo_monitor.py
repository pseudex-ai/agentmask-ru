"""Замер поиска: сбор, идемпотентность, честность отказа, движение.

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ И ПОЧЕМУ ИМЕННО ЭТО. Замер — инструмент, а инструмент,
который не может провалиться, ничего не измеряет. Четыре вещи ломаются тихо, и
каждая из них уже стоила кому-то времени:

  СЕТЬ В ТЕСТЕ. Ни одного настоящего запроса: и Вебмастер, и Search API
    подменяются. Иначе тест падал бы от чужого сбоя и проходил бы от чужого
    успеха, то есть не проверял бы наш код вовсе.
  МОЛЧАНИЕ ИСТОЧНИКА, СТАВШЕЕ НУЛЁМ. `None` и `0` в поле индекса — разные
    новости: «нас нет в поиске» и «мы не смогли спросить». Если сбой источника
    записывать нулём, мы испугаемся на пустом месте, а настоящий обвал
    пропустим. Здесь это проверяется на отказе Вебмастера.
  ВТОРАЯ СТРОКА ЗА ТЕ ЖЕ СУТКИ. Сводка может перезапуститься; смысл таблицы —
    движение по дням. Вторая запись за сутки сделала бы «вчера» сегодняшним и
    убила бы сравнение.
  ДВИЖЕНИЕ, КОТОРОЕ НЕ ПОКАЗАНО. Снимок ценен только разницей с предыдущим,
    поэтому строка сводки обязана называть, СКОЛЬКО БЫЛО.

    python3 test_seo_monitor.py
"""

import datetime
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
os.environ["PSEUDEX_SECRET_KEY"] = "seo-monitor-test"
os.environ["PSEUDEX_DEBUG"] = "1"
os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-seo-monitor.db"
os.environ["SITE_URL"] = "https://pseudex.ru"
os.environ["PSEUDEX_SITE_URL"] = "https://pseudex.ru"
os.environ.setdefault("PSEUDEX_OPS_API_TOKEN", "ops-token-for-test")

if os.path.exists("/tmp/pseudex-seo-monitor.db"):
    os.remove("/tmp/pseudex-seo-monitor.db")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

setup_test_environment()
call_command("migrate", verbosity=0, run_syncdb=True)
call_command("seed_plans", verbosity=0)

from ops import seo, seo_api  # noqa: E402
from ops.models import SeoDay  # noqa: E402


def main() -> int:
    ok = True

    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # ── подмена источников: тест не ходит в сеть ───────────────────────────
    calls = {"summary": 0, "positions": 0}
    state = {"fail_summary": False}

    def summary():
        calls["summary"] += 1
        if state["fail_summary"]:
            raise seo_api.SeoError("HTTP 403: скоуп webmaster:hostinfo не выдан")
        return {"pages_in_search": 9, "sqi": 40, "raw": {}}

    def positions(queries):
        calls["positions"] += 1
        return [{"query": q, "position": (3 if i == 0 else None), "documents": 1000 + i}
                for i, q in enumerate(queries)]

    seo_api.webmaster_configured = lambda: True
    seo_api.search_configured = lambda: True
    seo_api.webmaster_summary = summary
    seo_api.webmaster_popular = lambda limit=20: [{"query": "обезличивание персональных данных"}]
    seo_api.search_index_count = lambda: 11
    seo_api.search_positions = positions

    # ── 0. СВЯЗКА С ВЕБМАСТЕРОМ: ТО, ЧТО НЕ РАБОТАЛО МЕСЯЦАМИ ──────────────
    # Два дефекта жили в `seo_api` и не были видны: снимок писал «источник
    # недоступен», а это считалось нормальным ответом. Оба стоят здесь.
    from ops import yandex_api as _ya
    real_request, real_post, real_token = (seo_api._webmaster_request, seo_api.httpx.post,
                                           _ya.access_token)
    _ya.access_token = lambda: "test-token"   # токен здесь не проверяем, сеть не трогаем
    try:
        # Хост Вебмастер отдаёт СО СХЕМОЙ: https://pseudex.ru/. Сравнение с
        # SITE_URL без схемы не совпадало никогда.
        seo_api._webmaster_request = lambda path, params=None: (
            {"user_id": 2435923507} if path == "/user/"
            else {"hosts": [{"ascii_host_url": "https://pseudex.ru/",
                             "host_url": "https://pseudex.ru/",
                             "verified": True, "host_id": "https:pseudex.ru:443"}]})
        try:
            user, host = seo_api._webmaster_ids()
        except Exception as error:  # noqa: BLE001 — отказ и есть результат проверки
            # ПРОВАЛ ЗАПИСЫВАЕТСЯ ЗДЕСЬ ЖЕ, а не превращается в строку. Линтер
            # тестов (`e2e/lint_tests.py`) считает `except Exception`, который
            # ничего не записывает, проглоченным провалом — и прав: сначала я
            # складывал ошибку в переменную и проверял её ниже, из-за чего
            # красная проверка выглядела как обычное сравнение строк.
            check("хост Вебмастера находится по домену", False,
                  f"{type(error).__name__}: {error}")
        else:
            check("хост Вебмастера находится по домену",
                  host == "https:pseudex.ru:443", f"получили {host}")

        # Переобход: API принимает ОДИН адрес на запрос. Тело со списком он
        # отвергает, и прежняя версия функции не отправляла ничего.
        sent = []

        class _Reply:
            status_code = 202
            text = ""

            def json(self):
                return {"task_id": "t", "quota_remainder": 148}

        def fake_post(url, json=None, headers=None, timeout=None):
            sent.append(json)
            return _Reply()

        seo_api.httpx.post = fake_post
        result = seo_api.webmaster_recrawl(["https://pseudex.ru/a", "https://pseudex.ru/b"])
        check(sent == [{"url": "https://pseudex.ru/a"}, {"url": "https://pseudex.ru/b"}],
              "переобход шлёт по одному адресу на запрос", str(sent))
        check(result["submitted"] == 2 and result["quota_remainder"] == 148,
              "принятые адреса и остаток квоты записаны", str(result))
    finally:
        (seo_api._webmaster_request, seo_api.httpx.post, _ya.access_token) = (real_request, real_post, real_token)

    today = datetime.date(2026, 9, 30)
    yesterday = today - datetime.timedelta(days=1)

    # ── 1. сбор ────────────────────────────────────────────────────────────
    snapshot = seo.collect(today)
    check(snapshot.pages_in_index == 9, "индекс владельца записан", str(snapshot.pages_in_index))
    check(snapshot.pages_in_index_estimate == 11, "оценка site: записана отдельно",
          str(snapshot.pages_in_index_estimate))
    check(len(snapshot.positions) == len(seo_api.TARGET_QUERIES),
          f"позиции собраны по всему целевому списку ({len(snapshot.positions)})")
    check(seo.in_top10(snapshot) == 1, "в топ-10 посчитан один запрос", str(seo.in_top10(snapshot)))

    # ── 2. идемпотентность ─────────────────────────────────────────────────
    seo.collect(today)
    check(SeoDay.objects.filter(day=today).count() == 1,
          "повторный сбор за те же сутки не плодит строк",
          str(SeoDay.objects.filter(day=today).count()))

    # ── 3. честность отказа: None, а не ноль ───────────────────────────────
    state["fail_summary"] = True
    broken = seo.collect(today)
    check(broken.pages_in_index is None,
          "отказ источника — это None, а не ноль страниц в индексе",
          repr(broken.pages_in_index))
    check("скоуп" in (broken.sources.get("webmaster") or ""),
          "причина отказа названа словами", str(broken.sources.get("webmaster")))
    line = seo.digest_lines(broken)[0]
    check("нет данных" in line and "не ответил" not in line,
          "строка сводки говорит «нет данных», а не «нас нет в поиске»", line)

    # ── 4. движение относительно прошлых суток ─────────────────────────────
    state["fail_summary"] = False
    seo.collect(yesterday)
    SeoDay.objects.filter(day=yesterday).update(pages_in_index=2)
    older = SeoDay.objects.get(day=yesterday)
    fresh = SeoDay.objects.get(day=today)
    fresh.pages_in_index = 9
    fresh.save(update_fields=["pages_in_index"])
    lines = seo.digest_lines(fresh, older)
    check(any("было 2" in l for l in lines), "движение показано числом: было 2", str(lines))
    check(any("топ-10" in l for l in lines), "и позиции названы отдельной строкой", str(lines))

    # ── 5. ручка: закрыта без токена и не считает заново ───────────────────
    from django.test import Client

    before_calls = dict(calls)
    client = Client()
    # Адрес консоли зависит от ADMIN_PATH, а он на проде свой (`ops-…`).
    # Складывать его руками значило бы проверять адрес, которого в тесте нет.
    from django.conf import settings

    ops_seo = f"/{settings.ADMIN_PATH}/ops/yandex/seo"
    closed = client.get(ops_seo)
    check(closed.status_code == 401, "ручка без токена закрыта", str(closed.status_code))
    opened = client.get(ops_seo,
                        headers={"Authorization": f"Bearer {os.environ['PSEUDEX_OPS_API_TOKEN']}"})
    check(opened.status_code == 200, "с токеном открывается", str(opened.status_code))
    payload = opened.json()
    check(payload.get("days"), "и отдаёт снимки", str(payload)[:80])
    check(calls == before_calls,
          "ручка берёт готовые снимки и не ходит в сеть на каждом запросе", str(calls))

    print()
    print("замер поиска OK — индекс от источника, позиции по списку, отказ назван, движение видно"
          if ok else "замер поиска: есть провалы")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
