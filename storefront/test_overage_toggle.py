"""ПЕРЕКЛЮЧАТЕЛЬ ОВЕРЕДЖА (docs/tz-license-volume-quota.md §B, приёмка §4).

Написано ПО КОНТРАКТУ, а не под реализацию, и каждая проверка умеет покраснеть.
Django целиком; платёжка и лицензионный сервер замоканы (как в `test_annual.py`).

Контракт §B/§4:

  * овередж ВЫКЛ (дефолт) — эффективный потолок = ВКЛЮЧЁННОЕ, буфер пуст:
    пробитие включённого = зона `stopped`; счёт БЕЗ строки овереджа;
  * овередж ВКЛ — служит сверх включённого (зона `metered`), копит по ставке,
    за `cap+buffer` — `stopped`; счёт СО строкой овереджа по ставке;
  * переключение вкл/выкл МЕНЯЕТ зону (эффект со следующей меры);
  * уже НАЧИСЛЕННЫЙ период задним числом НЕ пересчитывается.

    cd storefront && .venv/bin/python test_overage_toggle.py
"""
import os
import sys
from datetime import date, timedelta
from decimal import Decimal


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "overage-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-overage-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-overage-test.db"):
        os.remove("/tmp/pseudex-overage-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", "--no-licensing", verbosity=0)

    from django.utils import timezone
    from accounts.models import Organization
    from billing import licensing, services
    from billing.models import Invoice, Plan, Subscription

    ok = True

    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}"
              + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    # --- лицензионный сервер и платёжка замоканы -------------------------
    USAGE: dict[str, int] = {}
    licensing.set_status = lambda org_id, status: None
    licensing.set_ceiling = lambda org_id, ceiling: None
    licensing.fleet = lambda ids: {}
    licensing.instances = lambda org_id: {"instances": []}
    licensing.usage = lambda org_id: {"usage": {
        "values": USAGE.get(org_id, 0),
        "requests": USAGE.get(org_id, 0),
        "capacity_billable": USAGE.get(org_id, 0)}}

    start = Plan.objects.get(code="start")   # 990/мес, включено 10k, 79 ₽/1000
    # Потолок/буфер живого тарифа (для зоны при ВКЛ овередже).
    cap_on, buffer_on = services.effective_cap_buffer(
        Subscription(plan=start, overage_enabled=True), start)
    now = timezone.now()

    def make_sub(org_id, overage_enabled, included=10_000):
        org = Organization.objects.create(id=org_id, display_name=org_id)
        return Subscription.objects.create(
            organization=org, plan=start, state=Subscription.ACTIVE,
            overage_enabled=overage_enabled,
            trial_ends_at=now - timedelta(days=1),
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=30),   # период НЕ истёк
            terms_monthly_price=start.monthly_price,
            terms_included_requests=included,
            terms_metered_per_1k=start.metered_per_1k,
            terms_metered_floor=start.metered_floor, terms_taken_at=now)

    # ================================================================
    # A. ЗОНА: границы с учётом переключателя
    # ================================================================
    print("A. ЗОНА")
    sub_off = make_sub("zoff", overage_enabled=False)
    cap_off, buf_off = services.effective_cap_buffer(sub_off, start)
    check(cap_off == 10_000 and buf_off == 0,
          "ВЫКЛ: эффективный потолок = включённое, буфер пуст",
          f"cap={cap_off} buffer={buf_off}")
    check(services.classify_zone(10_000, 10_000, cap_off, buf_off)["zone"] == "included",
          "ВЫКЛ: ровно на включённом — ещё included")
    check(services.classify_zone(10_001, 10_000, cap_off, buf_off)["zone"] == "stopped",
          "ВЫКЛ: пробитие включённого = stopped")

    sub_on = make_sub("zon", overage_enabled=True)
    cap_e, buf_e = services.effective_cap_buffer(sub_on, start)
    check(cap_e == cap_on and buf_e == buffer_on and cap_e > 10_000,
          "ВКЛ: потолок/буфер живого тарифа (докуп сверх включённого)",
          f"cap={cap_e} buffer={buf_e}")
    check(services.classify_zone(20_000, 10_000, cap_e, buf_e)["zone"] == "metered",
          "ВКЛ: сверх включённого до потолка — metered (служит и копит)")
    check(services.classify_zone(cap_e + 1, 10_000, cap_e, buf_e)["zone"] == "buffer",
          "ВКЛ: за потолком в буфере — ещё служит")
    check(services.classify_zone(cap_e + buf_e + 1, 10_000, cap_e, buf_e)["zone"] == "stopped",
          "ВКЛ: за cap+buffer — stopped")

    # ================================================================
    # B. СЧЁТ: строка овереджа есть только при ВКЛ
    # ================================================================
    print("B. СЧЁТ")
    b_off = make_sub("boff", overage_enabled=False)
    USAGE["boff"] = 15_000                       # сверх включённых 10k
    inv_off = services.build_invoice(b_off.organization,
                                     date.today(), date.today() + timedelta(days=30))
    check(inv_off.metered_amount == Decimal("0.00") and inv_off.metered_requests == 0,
          "ВЫКЛ: пробитие включённого — счёт БЕЗ строки овереджа",
          f"объём={inv_off.metered_requests} сумма={inv_off.metered_amount}")
    check(inv_off.total == Decimal("990.00"),
          "ВЫКЛ: итог = только абонплата", f"итог={inv_off.total}")

    b_on = make_sub("bon", overage_enabled=True)
    USAGE["bon"] = 15_000
    inv_on = services.build_invoice(b_on.organization,
                                    date.today(), date.today() + timedelta(days=30))
    # (15000 − 10000 включённых − 0 порог) / 1000 × 79 ₽ = 395 ₽
    check(inv_on.metered_requests == 5_000
          and inv_on.metered_amount == Decimal("395.00"),
          "ВКЛ: счёт СО строкой овереджа по ставке (5000 → 395 ₽)",
          f"объём={inv_on.metered_requests} сумма={inv_on.metered_amount}")
    check(inv_on.total == Decimal("1385.00"),
          "ВКЛ: итог = абонплата + овередж", f"итог={inv_on.total}")

    # ================================================================
    # C. ПРИНУЖДЕНИЕ: часовой цикл останавливает по зоне переключателя
    # ================================================================
    print("C. ПРИНУЖДЕНИЕ (run_billing_cycle)")
    c_off = make_sub("coff", overage_enabled=False)
    USAGE["coff"] = 15_000                        # > включённого → stopped при ВЫКЛ
    c_met = make_sub("cmet", overage_enabled=True)
    USAGE["cmet"] = 15_000                        # metered при ВКЛ (< потолка) → служит
    c_stop = make_sub("cstop", overage_enabled=True)
    USAGE["cstop"] = cap_on + buffer_on + 5_000   # > cap+buffer → stopped даже при ВКЛ

    call_command("run_billing_cycle", verbosity=0)
    for s in (c_off, c_met, c_stop):
        s.refresh_from_db()
    check(c_off.volume_capped,
          "ВЫКЛ: пробитие включённого останавливает (volume_capped)")
    check(not c_met.volume_capped,
          "ВКЛ: сверх включённого до потолка НЕ останавливает — служит и копит")
    check(c_stop.volume_capped,
          "ВКЛ: за cap+buffer всё равно останавливает")

    # ================================================================
    # D. ПЕРЕКЛЮЧЕНИЕ МЕНЯЕТ ЗОНУ
    # ================================================================
    print("D. ПЕРЕКЛЮЧЕНИЕ")
    d = make_sub("dtog", overage_enabled=True)
    reported = {"capacity_billable": 20_000}      # между включённым и потолком
    pr_on = services.period_pricing(d.organization, start, reported)
    check(pr_on["zone"] == "metered",
          "ВКЛ: 20k → зона metered")
    d.overage_enabled = False
    d.save(update_fields=["overage_enabled"])
    d.organization.refresh_from_db()
    pr_off = services.period_pricing(d.organization, start, reported)
    check(pr_off["zone"] == "stopped",
          "тот же расход после ВЫКЛ → зона stopped (переключение меняет зону)",
          f"zone={pr_off['zone']}")
    check(pr_off["overage_amount"] == Decimal("0.00"),
          "ВЫКЛ: начисление в кабинете обнуляется")

    # ================================================================
    # E. УЖЕ НАЧИСЛЕННЫЙ ПЕРИОД НЕ ПЕРЕСЧИТЫВАЕТСЯ ЗАДНИМ ЧИСЛОМ
    # ================================================================
    print("E. НЕ ПЕРЕСЧИТЫВАТЬ ЗАДНИМ ЧИСЛОМ")
    e = make_sub("efreeze", overage_enabled=True)
    USAGE["efreeze"] = 15_000
    inv1 = services.build_invoice(e.organization,
                                  date.today(), date.today() + timedelta(days=30))
    charged = inv1.metered_amount
    check(charged == Decimal("395.00"),
          "период начислен при ВКЛ (овередж 395 ₽)", f"сумма={charged}")
    # Клиент выключает овередж ПОСЛЕ того, как период уже начислен.
    e.overage_enabled = False
    e.save(update_fields=["overage_enabled"])
    inv1.refresh_from_db()
    check(inv1.metered_amount == charged,
          "выключение задним числом НЕ трогает уже начисленный счёт",
          f"стало={inv1.metered_amount}")
    # А следующий период под ВЫКЛ уже без овереджа (эффект со следующей меры).
    USAGE["efreeze"] = 30_000                      # ватермарка 15k → сверх ещё 5k
    inv2 = services.build_invoice(e.organization,
                                  date.today() + timedelta(days=31),
                                  date.today() + timedelta(days=61))
    check(inv2.metered_amount == Decimal("0.00") and inv2.metered_requests == 0,
          "следующий период под ВЫКЛ — без начисления, хотя расход сверх включённого есть",
          f"объём={inv2.metered_requests} сумма={inv2.metered_amount}")

    print("=" * 60)
    if not ok:
        raise SystemExit("overage toggle not correct")
    print("overage toggle OK — зона, счёт, принуждение, переключение, "
          "заморозка начисленного")
    return 0


if __name__ == "__main__":
    sys.exit(main())
