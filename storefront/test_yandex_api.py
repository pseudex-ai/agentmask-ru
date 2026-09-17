"""ЯНДЕКС API: то, что ломается молча и снаружи.

ЗАЧЕМ ПРОВЕРКА. Интеграция с чужим сервисом отказывает не там, где её пишут.
Она отказывает в четырёх местах, и каждое из них выглядит как «ничего не
происходит», а не как ошибка:

  * ТОКЕН НЕ ОБНОВЛЯЕТСЯ. Access-токен живёт час-год, refresh — до отзыва.
    Модуль, который обменивает refresh на каждом запросе, работает и тихо
    упирается в лимит обращений; модуль, который не обновляет его вовсе,
    работает ровно до истечения и потом перестаёт.
  * СХЕМА АВТОРИЗАЦИИ ПЕРЕПУТАНА. Метрика принимает `OAuth`, Директ `Bearer`.
    Ошибка даёт 403 «недостаточно прав», то есть посылает проверять скоупы —
    и скоупы действительно выглядят подозрительно, потому что их выдавали
    давно и не помнишь какие.
  * ОШИБКА ПРИЕХАЛА С HTTP 200. Директ кладёт отказ в тело при успешном
    статусе. Проверка «статус 200» пропускает её наверх, и отчёт получается
    пустым вместо сломанным — а пустой отчёт читается как «реклама не
    работает».
  * ДВЕРЬ ОТКРЫТА, КОГДА ТОКЕН НЕ ЗАДАН. Сравнение с пустой строкой проходит
    у запроса без заголовка, и ненастроенный стенд публикует эндпоинт всем.

СЕТЬ ЗДЕСЬ НЕ УЧАСТВУЕТ НИ РАЗУ. `_request` подменяется целиком: тест, который
ходит в Яндекс, однажды упадёт от чужого 429 и будет починен ослаблением
проверки.

Запуск:  cd storefront && .venv/bin/python test_yandex_api.py
"""

import os
import stat
import sys
import tempfile
from decimal import Decimal


class _Fake:
    """Ответ без сети. Несёт ровно то, что читает модуль: статус и тело."""

    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def main() -> int:  # noqa: C901 — линейный сценарий из проверок
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "yandex-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-yandex-test.db"
    os.environ["SITE_URL"] = "https://pseudex.test"
    os.environ["PSEUDEX_SITE_URL"] = "https://pseudex.test"
    if os.path.exists("/tmp/pseudex-yandex-test.db"):
        os.remove("/tmp/pseudex-yandex-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)

    from django.conf import settings
    from django.test import Client, override_settings

    from ops import yandex_api
    from ops.management.commands import yandex_auth

    ok = True

    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # ── подмена сети ───────────────────────────────────────────────────────
    calls: list[tuple] = []
    scripted: list = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if not scripted:
            raise AssertionError(f"неожиданный запрос {method} {url}")
        item = scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    yandex_api._request = fake_request

    def reset_token_cache():
        yandex_api._access_token = ""
        yandex_api._access_expires_at = 0.0

    def token_payload(expires_in=3600, token="tok-1"):
        return {"access_token": token, "expires_in": expires_in,
                "refresh_token": "ref-1", "token_type": "bearer"}

    creds = dict(YANDEX_OAUTH_CLIENT_ID="cid", YANDEX_OAUTH_CLIENT_SECRET="sec",
                 YANDEX_OAUTH_REFRESH_TOKEN="ref")

    # ── 1. токен: обмен, кэш, обновление ───────────────────────────────────
    reset_token_cache()
    with override_settings(**creds):
        scripted.append(_Fake(200, token_payload()))
        first = yandex_api.access_token()
        second = yandex_api.access_token()
    check(first == "tok-1" and second == "tok-1" and len(calls) == 1,
          "второе обращение берёт токен из кэша, а не обменивает снова",
          f"вызовов сети: {len(calls)}")

    reset_token_cache()
    calls.clear()
    creds_no_refresh = dict(creds, YANDEX_OAUTH_REFRESH_TOKEN="")
    with override_settings(**creds_no_refresh):
        check(not yandex_api.configured(),
              "без refresh-токена интеграция считается выключенной")
        try:
            yandex_api.access_token()
            check(False, "обращение без refresh-токена обязано упасть")
        except yandex_api.YandexError as error:
            check("не настроен" in str(error),
                  "и падает внятно, а не пустым ключом в заголовке", str(error))
    check(not calls, "выключенная интеграция не ходит в сеть вообще",
          f"запросов: {calls}")

    # обмен вернул 401 — это отзыв, а не «истёк»
    reset_token_cache()
    scripted.append(_Fake(401, {"error": "invalid_grant"}))
    error = None
    with override_settings(**creds):
        try:
            yandex_api.access_token()
            check(False, "401 на обмене обязан быть ошибкой")
        except yandex_api.YandexError as caught:
            error = caught
            check(error.status == 401 and "invalid_grant" in str(error),
                  "401 на обмене называет код ошибки и статус", str(error))
    check(error is not None and "sec" not in str(error),
          "и не тащит client_secret в текст ошибки")

    # ── 2. схемы авторизации ───────────────────────────────────────────────
    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"data": [], "totals": [1, 2, 3]}))
    with override_settings(**creds):
        yandex_api.metrika_get("/stat/v1/data", {"ids": "1"})
    metrika_headers = calls[-1][2].get("headers", {})
    check(metrika_headers.get("Authorization") == "OAuth tok-1",
          "Метрика получает схему OAuth, а не Bearer", str(metrika_headers))

    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"result": {"Campaigns": []}}))
    with override_settings(**creds):
        yandex_api.direct("campaigns", "get", {})
    direct_headers = calls[-1][2].get("headers", {})
    check(direct_headers.get("Authorization") == "Bearer tok-1",
          "Директ получает схему Bearer, а не OAuth", str(direct_headers))
    check(calls[-1][2].get("json", {}).get("method") == "get",
          "тело Директа — method+params, а не REST-путь", str(calls[-1][2]))

    # ── 3. отказ внутри HTTP 200 ───────────────────────────────────────────
    reset_token_cache()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"error": {
        "error_code": 58, "error_string": "Incomplete registration",
        "error_detail": "заявка не одобрена"}}))
    with override_settings(**creds):
        try:
            yandex_api.direct_campaigns()
            check(False, "ошибка в теле при HTTP 200 обязана подниматься")
        except yandex_api.YandexError as error:
            check("Incomplete registration" in str(error),
                  "ошибка в теле при HTTP 200 поднимается как ошибка",
                  str(error))

    # ── 4. машинный доступ ─────────────────────────────────────────────────
    ops_base = f"/{settings.ADMIN_PATH}/ops"
    client = Client()
    with override_settings(OPS_API_TOKEN=""):
        response = client.get(f"{ops_base}/yandex/status")
        check(response.status_code == 401,
              "пустой OPS_API_TOKEN закрывает дверь, а не открывает",
              f"status={response.status_code}")
        response = client.get(f"{ops_base}/yandex/status",
                              headers={"Authorization": "Bearer "})
        check(response.status_code == 401,
              "и запрос с пустым Bearer её не открывает",
              f"status={response.status_code}")

    with override_settings(OPS_API_TOKEN="ops-secret", METRIKA_ID="112743085",
                           **creds):
        wrong = client.get(f"{ops_base}/yandex/status",
                           headers={"Authorization": "Bearer nope"})
        check(wrong.status_code == 401, "чужой токен получает 401",
              f"status={wrong.status_code}")
        response = client.get(f"{ops_base}/yandex/status",
                              headers={"Authorization": "Bearer ops-secret"})
        check(response.status_code == 200, "свой токен получает 200",
              f"status={response.status_code}")
        body = response.json()
        check(body["counter_set"] and body["refresh_token_set"],
              "/status видит настроенный стенд", str(body))

        # СТАТУС ОБЯЗАН ОТВЕЧАТЬ ПРИ МЁРТВОЙ СЕТИ: его дёргают, когда всё
        # сломалось. Любой сетевой вызов здесь — это отказ диагностики ровно в
        # тот момент, ради которого она существует.
        calls.clear()
        response = client.get(f"{ops_base}/yandex/status",
                              headers={"Authorization": "Bearer ops-secret"})
        check(response.status_code == 200 and not calls,
              "/status не ходит в сеть", f"запросов: {len(calls)}")

    # ── 5. сводка без счётчика — это 409, а не пустой отчёт ────────────────
    reset_token_cache()
    with override_settings(OPS_API_TOKEN="ops-secret", METRIKA_ID="",
                           **creds):
        response = client.get(f"{ops_base}/yandex/metrika/summary",
                              headers={"Authorization": "Bearer ops-secret"})
        check(response.status_code == 409,
              "без номера счётчика сводка честно говорит 409, "
              "а не отдаёт нули", f"status={response.status_code}")
        check(response.json().get("error") == "no_counter",
              "и называет причину", str(response.json()))

    # ── 6. заявка Директа ещё не одобрена — 409, а не 500 ─────────────────
    reset_token_cache()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"error": {"error_code": 58,
                                          "error_string": "Incomplete registration"}}))
    with override_settings(OPS_API_TOKEN="ops-secret", **creds):
        response = client.get(f"{ops_base}/yandex/direct/campaigns",
                              headers={"Authorization": "Bearer ops-secret"})
        check(response.status_code == 409,
              "неодобренная заявка Директа — 409, чтобы бот не кричал "
              "каждое утро", f"status={response.status_code}")
        check(response.json().get("error") == "not_approved",
              "и это отличимо от настоящей поломки", str(response.json()))

    # ── 7. команда: адрес авторизации ──────────────────────────────────────
    os.environ["YANDEX_OAUTH_CLIENT_ID"] = "cid"
    os.environ["YANDEX_OAUTH_CLIENT_SECRET"] = "sec"
    out = _capture(call_command, "yandex_auth", "--url")
    check("oauth.yandex.ru/authorize" in out and "client_id=cid" in out,
          "команда печатает адрес авторизации", out.strip()[:120])

    # ── 8. команда: обмен кода и правка .env ───────────────────────────────
    reset_token_cache()
    with tempfile.TemporaryDirectory() as tmp:
        env_path = os.path.join(tmp, ".env")
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("PSEUDEX_ENV_NAME=prod\n"
                         "YANDEX_OAUTH_REFRESH_TOKEN=old-value\n"
                         "PSEUDEX_METRIKA_ID=112743085\n")
        os.chmod(env_path, 0o644)
        scripted.append(_Fake(200, token_payload()))
        with override_settings(**creds):
            out = _capture(call_command, "yandex_auth", "the-code",
                           "--env-file", env_path)
        text = open(env_path, encoding="utf-8").read()
        backups = [n for n in os.listdir(tmp) if n.startswith(".env.bak-")]
        mode = stat.S_IMODE(os.stat(env_path).st_mode)
        check(text.count("YANDEX_OAUTH_REFRESH_TOKEN=") == 1
              and "YANDEX_OAUTH_REFRESH_TOKEN=ref-1" in text,
              "строка заменена, а не дописана второй",
              text)
        check("old-value" not in text, "старое значение не осталось в файле")
        check("PSEUDEX_ENV_NAME=prod" in text
              and "PSEUDEX_METRIKA_ID=112743085" in text,
              "соседние строки не тронуты", text)
        check(len(backups) == 1, "бэкап сделан и он один", str(backups))
        check(mode == 0o600, "права на .env — 600", oct(mode))
        check("ref-1" in out, "команда напечатала refresh-токен оператору")
        check("YANDEX_OAUTH_CLIENT_SECRET" not in out
              and "sec" not in out.replace("secret", ""),
              "и не напечатала client secret", out)

    # ── 9. команда: обмен без refresh-токена в ответе ──────────────────────
    scripted.append(_Fake(200, {"access_token": "tok", "expires_in": 3600}))
    from django.core.management.base import CommandError
    try:
        _capture(call_command, "yandex_auth", "some-code")
        check(False, "ответ без refresh-токена обязан быть ошибкой")
    except CommandError as error:
        check("refresh" in str(error),
              "ответ без refresh-токена назван ошибкой, а не принят",
              str(error))

    # ── 10. офлайн-конверсия: формат CSV и отсев строк без yclid ───────────
    import datetime as _dt

    from django.utils import timezone as _tz

    from accounts.models import Organization
    from ops.analytics_models import ConversionSent, Funnel

    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"uploading": {"id": 77, "status": "UPLOADED"}}))
    when = _tz.now() - _dt.timedelta(hours=2)
    with override_settings(METRIKA_ID="112743085", **creds):
        outcome = yandex_api.upload_conversions([
            {"target": "signup", "at": when, "yclid": "123"},
            {"target": "paid", "at": when, "yclid": "456",
             "price": Decimal("3900.00"), "currency": "RUB"},
            {"target": "signup", "at": when, "yclid": ""},
        ], comment="pseudex")
    csv_text = calls[-1][2]["files"]["file"][1]
    lines = csv_text.splitlines()
    check(outcome["sent"] == 2 and outcome["skipped"] == 1,
          "строка без yclid отсеяна ДО запроса, а не отвергнута Метрикой",
          str(outcome))
    check(lines[0] == "Target,DateTime,Yclid,Price,Currency",
          "заголовок CSV назван так, как требует документация", lines[0])
    check(len(lines) == 3, "в файле две строки: без yclid третьей нет",
          str(lines))
    check(str(int(when.timestamp())) in csv_text,
          "дата — UNIX-время события, а не момент отправки")
    check("3900.00" in csv_text and "3900,00" not in csv_text,
          "цена с точкой: «3900,00» не разберётся и утащит строку за собой")
    check(calls[-1][1].endswith(
              "/management/v1/counter/112743085/offline_conversions/upload"),
          "загрузка идёт на эндпоинт конверсий с номером счётчика",
          calls[-1][1])
    check(calls[-1][2].get("headers", {}).get("Authorization") == "OAuth tok-1",
          "конверсия грузится схемой OAuth, а не Bearer")
    check(calls[-1][2].get("params", {}).get("comment") == "pseudex",
          "комментарий загрузки назван, чтобы её нашли в панели")

    reset_token_cache()
    calls.clear()
    with override_settings(METRIKA_ID="112743085", **creds):
        outcome = yandex_api.upload_conversions([{"target": "signup", "at": when,
                                                  "yclid": ""}])
    check(outcome.get("sent", 0) == 0 and not calls,
          "файл без единой привязки не отправляется вовсе", str(outcome))

    # ── 11. цель заводится с условием «совпадает» ──────────────────────────
    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"goal": {"id": 1}}))
    with override_settings(METRIKA_ID="112743085", **creds):
        yandex_api.create_goal("pseudex: регистрация", "signup")
    body = calls[-1][2].get("json", {})
    condition = (body.get("goal", {}).get("conditions") or [{}])[0]
    check(body.get("goal", {}).get("type") == "action",
          "цель заводится типом «JavaScript-событие»", str(body))
    check(condition.get("type") == "exact" and condition.get("value") == "signup",
          "и условием «совпадает» — этого требует офлайн-конверсия", str(body))

    # ── 12. команда: отправка ровно один раз ───────────────────────────────
    clicked = Organization.objects.create(display_name="ООО Клик",
                                          legal_name="ООО «Клик»", inn="7712345670")
    clicked.source_yclid = "999888777"
    clicked.save(update_fields=["source_yclid"])
    direct = Organization.objects.create(display_name="ООО Прямой",
                                         legal_name="ООО «Прямой»",
                                         inn="7712345671")
    stamp = _tz.now() - _dt.timedelta(hours=3)
    Funnel.objects.create(step=Funnel.SIGNUP_SUBMITTED,
                          organization_id=clicked.id, at=stamp)
    Funnel.objects.create(step=Funnel.SIGNUP_SUBMITTED,
                          organization_id=direct.id, at=stamp)
    Funnel.objects.create(step=Funnel.PAID, organization_id=clicked.id,
                          at=stamp, detail="3900.00")
    # Второе событие той же цели: повтор учил бы Директ на завышенной цифре.
    Funnel.objects.create(step=Funnel.PAID, organization_id=clicked.id,
                          at=stamp + _dt.timedelta(minutes=5), detail="100.00")

    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"uploading": {"id": 5, "status": "PREPARED"}}))
    scripted.append(_Fake(200, {"uploading": {"id": 6, "status": "PREPARED"}}))
    with override_settings(METRIKA_ID="112743085", **creds):
        out = _capture(call_command, "yandex_conversions")
    rows = [r for r in calls if "offline_conversions" in r[1]]
    check(len(rows) == 2, "загрузка одна на цель, а не на организацию",
          f"загрузок: {len(rows)}")
    check(rows[0][2]["files"]["file"][1].count("\n") == 2,
          "в файле «регистрация» ровно одна строка — прямой заход не считается",
          rows[0][2]["files"]["file"][1])
    saved = set(ConversionSent.objects.values_list("organization_id", "target"))
    check((clicked.id, "signup") in saved and (clicked.id, "paid") in saved,
          "отметка поставлена по обеим целям", str(saved))
    check(all(org != direct.id for org, _ in saved),
          "организация без yclid не отмечена отправленной — её не отправляли",
          str(saved))
    check("3900.00" in rows[1][2]["files"]["file"][1]
          and "100.00" not in rows[1][2]["files"]["file"][1],
          "ценность взята у ПЕРВОЙ оплаты, а не у последней",
          rows[1][2]["files"]["file"][1])
    check("отправлено" in out, "команда сказала, что отправила", out)

    # повторный запуск: ни одного обращения в сеть
    reset_token_cache()
    calls.clear()
    with override_settings(METRIKA_ID="112743085", **creds):
        _capture(call_command, "yandex_conversions")
    check(not calls, "повторный запуск не отправляет ничего второй раз",
          f"запросов: {len(calls)}")

    # dry-run не ходит в сеть и не ставит отметок
    ConversionSent.objects.all().delete()
    reset_token_cache()
    calls.clear()
    with override_settings(METRIKA_ID="112743085", **creds):
        out = _capture(call_command, "yandex_conversions", "--dry-run")
    check(not calls and not ConversionSent.objects.exists(),
          "dry-run не отправляет и не отмечает", f"запросов: {len(calls)}")
    check("dry-run" in out, "и говорит об этом", out)

    # ── 13. yclid доезжает от рекламной ссылки до организации ──────────────
    from ops.analytics_models import Visit

    call_command("seed_plans", verbosity=0)
    landing = client.get("/?yclid=987654321&utm_source=yandex&utm_medium=cpc")
    check(landing.status_code == 200, "лендинг отрисовался",
          f"status={landing.status_code}")
    visited = Visit.objects.order_by("-at").first()
    check(visited is not None and visited.yclid == "987654321",
          "yclid сохранён вместе с визитом лендинга",
          visited.yclid if visited else "визита нет")
    from ops import collect as _collect
    touch = _collect.first_touch(visited.visitor, 24)
    check(touch.get("source_yclid") == "987654321",
          "первое касание отдаёт yclid так же, как метки", str(touch))
    check(touch.get("source_utm_source") == "yandex",
          "и метки при этом не потерялись", str(touch))
    # ЗАМЕТКА ДЛЯ ПРАВЯЩЕГО ШАБЛОН НЕ ДОЕЗЖАЕТ ДО ПОСЕТИТЕЛЯ. HTML-комментарий
    # в исходнике страницы читает первым тот, кто как раз выбирает, куда лезть;
    # в публичном шаблоне поэтому `{% comment %}`, а не `<!-- -->`.
    body = landing.content.decode()
    at = body.find("<!--")
    check(at < 0, "в исходнике публичной страницы нет HTML-комментариев",
          body[at:at + 90] if at >= 0 else "")

    # ── 14. недельный блок в сводке бота ──────────────────────────────────
    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"totals": [12, 9, 40], "data": []}))
    scripted.append(_Fake(200, {"data": [
        {"dimensions": [{"name": "organic"}], "metrics": [7]},
        {"dimensions": [{"name": "ad"}], "metrics": [5]}]}))
    scripted.append(_Fake(200, {"result": {"Campaigns": [{"Id": 1}]}}))
    with override_settings(METRIKA_ID="112743085", **creds):
        out = _capture(call_command, "daily_digest", "--weekly", "--dry-run")
    check("Метрика за 7 дн." in out and "визитов 12" in out,
          "недельная сводка называет визиты Метрики", out)
    check("organic 7" in out and "ad 5" in out,
          "и разрез по источникам", out)
    check("Директ: кампаний 1" in out, "и кампании Директа", out)

    reset_token_cache()
    calls.clear()
    scripted.append(_Fake(200, token_payload()))
    scripted.append(_Fake(200, {"totals": [1, 1, 1], "data": []}))
    scripted.append(_Fake(200, {"result": {"Campaigns": []}}))
    with override_settings(METRIKA_ID="112743085", **creds):
        out = _capture(call_command, "daily_digest", "--dry-run")
    check("Метрика" not in out and "Директ" not in out,
          "без --weekly блока Яндекса в сводке нет", out)

    out = _capture(call_command, "daily_digest", "--weekly", "--dry-run")
    check("Метрика" not in out and "Директ" not in out
          and not calls,
          "ненастроенная интеграция молчит, а не пишет «не работает» каждую "
          "неделю", out)

    print("=" * 60)
    if not ok:
        raise SystemExit("yandex api is not correct")
    print("yandex api OK — токен обновляется и кэшируется, схемы не "
          "перепутаны, отказ в теле не проходит за успех, дверь закрыта "
          "по умолчанию")
    return 0


def _capture(func, *args, **kwargs) -> str:
    """Вывод management-команды строкой: проверяем то, что видит оператор."""
    import io
    from django.core.management.base import OutputWrapper
    buffer = io.StringIO()
    old_out = sys.stdout
    sys.stdout = buffer
    try:
        func(*args, stdout=OutputWrapper(buffer), stderr=OutputWrapper(buffer),
             **kwargs)
    finally:
        sys.stdout = old_out
    return buffer.getvalue()


if __name__ == "__main__":
    sys.exit(main())
