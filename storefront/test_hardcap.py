"""Жёсткий потолок объёма: остановка по объёму — ФЛАГ поверх состояния, не
состояние. Чисто на Django, лицензионный сервер замокан — стенд не нужен.

Доказывает разбор ревью:
  * HIGH: капнутый по объёму клиент ВСЁ РАВНО выставляется на своём переходе
    (state остаётся ACTIVE), новый период сдвигает ватермарку и он выходит из
    стопа — не «остановлен навсегда».
  * MED: возобновление НЕ теряет состояние (ACTIVE, не «оживший без оплаты»);
    отказ рубильника не роняет весь цикл; потолок, выведенный из включённого,
    не пускает в мгновенный стоп при правке включённого.

Запуск:  cd storefront && .venv/bin/python test_hardcap.py
"""
import os
import sys
from unittest.mock import Mock


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "hardcap-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-hardcap-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-hardcap-test.db"):
        os.remove("/tmp/pseudex-hardcap-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from datetime import timedelta
    from django.utils import timezone
    from django.core.management import call_command as run
    from accounts.models import Organization
    from billing import licensing, services
    from billing.models import Invoice, Plan, Subscription

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    plan = Plan.objects.get(code="start")   # included 10k, потолок 30k, буфер 3k
    org = Organization.objects.create(id="capco", display_name="Cap Co")
    now = timezone.now()
    sub = Subscription.objects.create(
        organization=org, plan=plan, state=Subscription.ACTIVE,
        trial_ends_at=now - timedelta(days=1),
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=30))

    # Лицензионный сервер замокан: usage задаём, рубильник считаем.
    status_calls = []
    def set_status(org_id, status):
        status_calls.append((org_id, status))
    licensing.set_status = set_status
    licensing.fleet = lambda ids: {}
    licensing.instances = lambda org_id: {"instances": []}
    def usage_of(billable):
        licensing.usage = lambda org_id: {"usage": {
            "values": billable, "requests": billable, "capacity_billable": billable}}

    # --- MED#8: потолок выводится из включённого, страховка classify_zone ---
    cap, buffer = services.derive_cap_and_buffer(10_000)
    check(cap == 30_000 and buffer == 3_000, "derive_cap_and_buffer(10k) = (30k, 3k)",
          f"{cap}/{buffer}")
    stale = Plan(included_requests=50_000, overage_cap_requests=30_000,
                 buffer_requests=3_000)   # потолок ОТСТАЛ от включённого
    z = services.classify_zone(20_000, stale)
    check(z["zone"] == "included",
          "включённое выше устаревшего потолка НЕ даёт мгновенный стоп",
          f"zone={z['zone']}")

    # --- потолок: за буфером — стоп по объёму (флаг), состояние ЖИВО ---
    usage_of(40_000)                        # > потолок(30k)+буфер(3k)
    run("run_billing_cycle", verbosity=0)
    sub.refresh_from_db()
    check(sub.volume_capped and sub.state == Subscription.ACTIVE,
          "за буфером: volume_capped=True, состояние ACTIVE не потеряно",
          f"capped={sub.volume_capped} state={sub.state}")
    check(("capco", "suspended") in status_calls, "рубильник дёрнут в suspended")

    # --- HIGH: капнутый клиент ВСЁ РАВНО выставляется на переходе периода ---
    before = Invoice.objects.filter(organization=org).count()
    Subscription.objects.filter(pk=sub.pk).update(
        current_period_end=now - timedelta(seconds=1))
    run("run_billing_cycle", verbosity=0)
    after = Invoice.objects.filter(organization=org).exclude(state=Invoice.VOID).count()
    check(after == before + 1,
          "капнутому выставлен счёт за период (перерасход не потерян)",
          f"было {before}, стало {after}")

    # --- HIGH: новый период сдвинул ватермарку → выход из стопа, БЕЗ оплаты ---
    # Счёт выше записал requests_billable_at_period_end = 40k. Следующий проход
    # видит расход периода = 40k - 40k = 0 → под потолком → снятие стопа.
    status_calls.clear()
    run("run_billing_cycle", verbosity=0)
    sub.refresh_from_db()
    check(not sub.volume_capped and sub.state == Subscription.ACTIVE,
          "новый период вернул из стопа сам (не «навсегда»), состояние цело",
          f"capped={sub.volume_capped} state={sub.state}")
    check(("capco", "active") in status_calls, "рубильник вернул active")

    # --- MED#3: отказ рубильника НЕ роняет цикл и НЕ пишет ложное зеркало ---
    Invoice.objects.filter(organization=org).update(state=Invoice.VOID)  # ватермарка 0
    Subscription.objects.filter(pk=sub.pk).update(
        volume_capped=False, current_period_end=now + timedelta(days=30))
    licensing.set_status = Mock(side_effect=licensing.LicensingError("boom"))
    usage_of(40_000)
    crashed = False
    try:
        run("run_billing_cycle", verbosity=0)
    except Exception:  # noqa: BLE001 — именно это не должно случаться
        crashed = True
    sub.refresh_from_db()
    check(not crashed, "отказ лицензионного сервера НЕ роняет часовой цикл")
    check(not sub.volume_capped,
          "при отказе рубильника локальное зеркало НЕ ставится (не врём кабинету)",
          f"capped={sub.volume_capped}")

    print("=" * 60)
    if not ok:
        raise SystemExit("hard-cap cycle not correct")
    print("hard-cap OK — флаг поверх состояния, счёт на переходе, авто-выход, "
          "устойчивый рубильник, вывод потолка")
    return 0


if __name__ == "__main__":
    sys.exit(main())
