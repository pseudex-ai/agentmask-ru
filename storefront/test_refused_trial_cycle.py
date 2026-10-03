"""ОДИН РЯД, КОТОРОГО НЕТ НА ЛИЦЕНЗИОННОМ СЕРВЕРЕ, НЕ ОСТАНАВЛИВАЕТ ДЕНЬГИ.

ЧТО СЛУЧИЛОСЬ НА ПРОДЕ 03.10.2026. Часовой `run_billing_cycle` падал каждый час
на одной организации: `licensing.set_status(org, "unpaid")` получал
`404 {"error":"unknown org_id"}`, `_post` поднимал `LicensingError`, и
исключение обрывало ВЕСЬ проход. Ни счёт не выставлялся, ни проба не
останавливалась — ни у кого. Наружу это выглядело как `billing (unhealthy)`,
потому что отметка успеха в `/data/last-ok` не обновлялась.

ОТКУДА БЕРЁТСЯ ТАКОЙ РЯД, И ПОЧЕМУ ОН НЕ ОШИБКА. Лицензионный сервер узнаёт об
организации, когда выдан ПЕРВЫЙ ключ. Аккаунт, которому проба не досталась
(`services.create_account`: та же почта или тот же адрес), рождается с уже
кончившейся пробой и без ключей — и цикл штатно пытается его остановить.
Двигать нечего: изменено НОЛЬ ключей, а не «не удалось».

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ, И ПОЧЕМУ ЭТО НЕ ТАВТОЛОГИЯ. `set_status` вызывается
НАСТОЯЩИЙ — замокан только `httpx`, то есть проверяется реальный разбор ответа,
а не подменённая функция. Вторая половина важнее первой: прогон цикла целиком
доказывает, что после отказа по одному ряду ОСТАЛЬНЫЕ всё равно обработаны.
Тест, который смотрит только на возвращённый ноль, зелёный и на коде, где цикл
по-прежнему обрывается.

ОБРАТНАЯ СТОРОНА: чужая ошибка обязана остаться ошибкой. 404 на переименованной
ручке и 500 это НЕ «организации нет», и молча принять их значило бы спрятать
целый неработающий переход статуса. Ровно этот класс уже случался: `revoked` и
`suspended` уходили на несуществующие `/admin/revoked` и `/admin/suspended`.

Запуск:  cd storefront && .venv/bin/python test_refused_trial_cycle.py
"""
import json
import os
import sys
from datetime import timedelta


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "refused-trial-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-refused-trial.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-refused-trial.db"):
        os.remove("/tmp/pseudex-refused-trial.db")
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", "--no-licensing", verbosity=0)

    from django.utils import timezone
    from billing import licensing, services
    from billing.models import Subscription
    from billing.management.commands.run_billing_cycle import Command

    ok = True

    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # ── httpx замокан; `set_status` — настоящий ────────────────────────────
    UNKNOWN = "org_never_seen"
    KNOWN = "org_known"
    ROUTES: dict[str, object] = {}

    class _Fake:
        def __init__(self, status, body):
            self.status_code = status
            self.text = json.dumps(body, ensure_ascii=False)

        def json(self):
            return json.loads(self.text)

    def fake_post(url, **kwargs):
        path = url.rsplit("/json", 1)[-1]
        payload = kwargs.get("json") or {}
        org = str(payload.get("org_id", ""))
        if url.endswith("/admin/issue"):
            return _Fake(200, {"key": "sk-ps-refused-trial-test"})
        if url.endswith("/admin/unpaid") and org in ROUTES:
            return ROUTES[org]
        if url.endswith("/admin/unpaid"):
            return _Fake(200, {"keys_changed": 1})
        return _Fake(200, {"keys_changed": 0})

    licensing.httpx.post = fake_post
    licensing.set_ceiling = lambda org_id, ceiling: None
    licensing.fleet = lambda ids: {}
    licensing.instances = lambda org_id: {"instances": []}
    licensing.usage = lambda org_id: {"usage": {}}

    # ── 1. чужой организации нет — это ноль ключей, а не ошибка ────────────
    ROUTES[UNKNOWN] = _Fake(404, {"error": "unknown org_id", "org_id": UNKNOWN})
    try:
        changed = licensing.set_status(UNKNOWN, "unpaid")
        check(changed == 0,
              "организация без ключей: остановка возвращает ноль ключей",
              f"вернулось {changed!r}")
        check(True, "и не поднимает исключение")
    except licensing.LicensingError as error:
        check(False, "организация без ключей: остановка возвращает ноль ключей",
              f"поднялось {error}")

    # ── 2. чужая ошибка остаётся ошибкой ───────────────────────────────────
    ROUTES[KNOWN] = _Fake(404, {"error": "no such endpoint"})
    try:
        licensing.set_status(KNOWN, "unpaid")
        check(False, "404 на другом теле — по-прежнему ошибка, а не ноль")
    except licensing.LicensingError as error:
        check(getattr(error, "status", None) == 404,
              "404 на другом теле — по-прежнему ошибка, а не ноль",
              "это спрятало бы переименованную ручку целиком")

    ROUTES[KNOWN] = _Fake(500, {"error": "boom"})
    try:
        licensing.set_status(KNOWN, "unpaid")
        check(False, "500 не принимается за «организации нет»")
    except licensing.LicensingError as error:
        check(getattr(error, "status", None) == 500,
              "500 не принимается за «организации нет»", str(error))

    # ── 3. аккаунт без пробы рождается с кончившейся пробой ────────────────
    first = services.create_account("trial-first@acme-corp.ru", "Акме",
                                    "free", "203.0.113.9")
    second = services.create_account("trial-second@acme-corp.ru", "Акме-2",
                                     "free", "203.0.113.9")
    first_sub = Subscription.objects.get(organization=first)
    second_sub = Subscription.objects.get(organization=second)
    check(second.trial_granted is False,
          "повторная регистрация с того же адреса: проба не выдана")
    check(second_sub.state == Subscription.TRIAL
          and second_sub.trial_ends_at <= timezone.now(),
          "и проба у неё кончилась в момент рождения — её и берёт цикл",
          f"state={second_sub.state} ends={second_sub.trial_ends_at}")

    # Первый аккаунт — настоящая кончившаяся проба: она ОБЯЗАНА быть остановлена
    # в том же проходе, иначе тест доказывал бы только «плохой ряд пропущен».
    first_sub.trial_ends_at = timezone.now() - timedelta(hours=1)
    first_sub.save(update_fields=["trial_ends_at"])

    # ── 4. проход целиком: плохой ряд не обрывает остальные ────────────────
    ROUTES[second.id] = _Fake(404, {"error": "unknown org_id",
                                    "org_id": second.id})
    ROUTES[first.id] = _Fake(200, {"keys_changed": 1})
    blocked: list[str] = []
    notified: list[str] = []
    original = Command._notify_trial_over
    Command._notify_trial_over = lambda self, subscription: notified.append(
        subscription.organization_id)
    try:
        call_command("run_billing_cycle", verbosity=0)
    except Exception as error:                      # noqa: BLE001 — это и есть предмет
        # Провал ЗАПИСЫВАЕТСЯ, а не гасится: это и есть проверка.
        blocked.append(f"{type(error).__name__}: {error}")
    finally:
        Command._notify_trial_over = original

    check(not blocked, "проход цикла завершается, а не обрывается на одном ряду",
          "; ".join(blocked))
    first_sub.refresh_from_db()
    second_sub.refresh_from_db()
    check(first_sub.state == Subscription.PAST_DUE,
          "настоящая кончившаяся проба в том же проходе ОСТАНОВЛЕНА",
          f"state={first_sub.state}")
    check(second_sub.state == Subscription.PAST_DUE,
          "аккаунт без пробы тоже переведён в «ждём оплату»",
          f"state={second_sub.state}")
    check(notified == [first.id],
          "письмо «проба кончилась» уходит только тому, у кого проба БЫЛА",
          f"письма: {notified}")

    print()
    print("=" * 60)
    if not ok:
        raise SystemExit("refused trial stops the money path")
    print("refused trial OK — организации без ключей это ноль ключей, "
          "остальные ряды обработаны, чужая ошибка осталась ошибкой")
    return 0


if __name__ == "__main__":
    sys.exit(main())
