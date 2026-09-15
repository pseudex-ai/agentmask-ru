"""Годовая предоплата (вариант A): база оплачена вперёд, перерасход остаётся
помесячным. Чисто на Django, платёжка и лицензионный сервер замоканы.

Доказывает:
  * annual_price = 12×абонплата − ЛУЧШАЯ из скидок (тарифная годовая vs
    annual-оффер), настраиваемая;
  * build_annual_invoice помечает is_annual, идемпотентен;
  * mark_paid по годовому ставит base_paid_through (не делает период годовым);
  * в годовом окне месячный счёт несёт базу=0; нулевой — гасится сам, период
    двигается; перерасход всё равно приходит помесячно;
  * годовой счёт НЕ участвует в месячной ватермарке и НЕ останавливает за
    неоплату (обязателен месячный цикл).

Запуск:  cd storefront && .venv/bin/python test_annual.py
"""
import os
import sys
from decimal import Decimal


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "annual-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-annual-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-annual-test.db"):
        os.remove("/tmp/pseudex-annual-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from datetime import timedelta
    from django.utils import timezone
    from accounts.models import Organization
    from billing import licensing, services
    from billing.models import Invoice, Offer, Plan, Subscription

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    licensing.set_status = lambda org_id, status: None
    licensing.fleet = lambda ids: {}
    licensing.instances = lambda org_id: {"instances": []}
    def usage_of(billable):
        licensing.usage = lambda org_id: {"usage": {
            "values": billable, "requests": billable, "capacity_billable": billable}}
    usage_of(0)

    start = Plan.objects.get(code="start")   # 990/мес, годовая скидка 15%
    now = timezone.now()
    org = Organization.objects.create(id="annco", display_name="Ann Co")
    sub = Subscription.objects.create(
        organization=org, plan=start, state=Subscription.TRIAL,
        trial_ends_at=now + timedelta(days=5),
        current_period_start=now, current_period_end=now + timedelta(days=5),
        terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)

    # --- цена: 990×12 = 11880, −15% = 10098 -----------------------------
    priced = services.annual_price(org, start)
    check(priced["gross"] == Decimal("11880.00")
          and priced["total"] == Decimal("10098.00")
          and priced["discount"] == Decimal("1782.00")
          and priced["offer"] is None,
          "годовая цена = 12×абонплата −15% (10098 ₽)",
          f"{priced}")

    # --- annual-оффер перебивает тарифную скидку, если выгоднее ----------
    Offer.objects.create(title="Год -30%", organization=org, discount_pct=30,
                         applies_to=Offer.APPLIES_ANNUAL)
    priced2 = services.annual_price(org, start)
    check(priced2["total"] == Decimal("8316.00") and priced2["offer"] is not None,
          "annual-оффер -30% перебивает тарифные -15% (8316 < 10098)",
          f"{priced2['total']}")

    # --- счёт: is_annual, идемпотентность -------------------------------
    inv = services.build_annual_invoice(org)
    span = (inv.period_end - inv.period_start).days
    check(inv.is_annual and inv.total == Decimal("8316.00")
          and 360 <= span <= 366,
          "годовой счёт помечен, период ≈365 дней, total со скидкой",
          f"is_annual={inv.is_annual} total={inv.total} span={span}")
    check(services.build_annual_invoice(org).pk == inv.pk,
          "повторный вызов не плодит второй годовой счёт")
    check(Offer.objects.get(title="Год -30%").uses == 1,
          "использование annual-оффера засчитано")

    # --- оплата годового: base_paid_through, период НЕ годовой -----------
    services.mark_paid(inv)
    sub.refresh_from_db()
    check(sub.base_paid_through is not None
          and (sub.base_paid_through - now).days >= 360
          and sub.state == Subscription.ACTIVE,
          "оплата года ставит base_paid_through ~365, state ACTIVE")
    check((sub.current_period_end - now).days <= 31,
          "период остался МЕСЯЧНЫМ (не годовым)",
          f"период до {sub.current_period_end}")

    # --- месячный счёт в годовом окне: база = 0 -------------------------
    from datetime import date
    usage_of(15_000)   # включено 10k → перерасход 5k
    over = services.build_invoice(org, date.today(), date.today() + timedelta(days=30))
    expected_metered = Decimal(5000) / 1000 * start.metered_per_1k
    check(over.plan_amount == 0
          and over.metered_amount == expected_metered.quantize(Decimal("0.01"))
          and over.total == over.metered_amount,
          "в годовом окне месячный счёт: база=0, только перерасход",
          f"база={over.plan_amount} объём={over.metered_amount} итог={over.total}")
    over.state = Invoice.VOID
    over.save(update_fields=["state"])

    # --- нулевой месячный счёт гасится сам, период двигается -------------
    usage_of(5_000)    # под включённым → перерасхода нет, база=0 → 0 ₽
    Subscription.objects.filter(pk=sub.pk).update(
        current_period_end=now - timedelta(seconds=1))
    before = Invoice.objects.filter(organization=org, is_annual=False).count()
    call_command("run_billing_cycle", verbosity=0)
    zero = (Invoice.objects.filter(organization=org, is_annual=False)
            .order_by("-id").first())
    sub.refresh_from_db()
    check(zero is not None and zero.total == 0 and zero.state == Invoice.PAID,
          "нулевой месячный счёт выставлен и погашен автоматически",
          f"total={getattr(zero,'total',None)} state={getattr(zero,'state',None)}")
    check((sub.current_period_end - timezone.now()).days >= 29,
          "месячный период сдвинулся вперёд после нулевого счёта")

    # --- годовой счёт НЕ останавливает за неоплату -----------------------
    Invoice.objects.filter(organization=org).update(state=Invoice.VOID)
    Subscription.objects.filter(pk=sub.pk).update(
        state=Subscription.ACTIVE, base_paid_through=None,
        current_period_end=now + timedelta(days=30))
    stale = services.build_annual_invoice(org)
    Invoice.objects.filter(pk=stale.pk).update(
        state=Invoice.ISSUED, due_at=(now - timedelta(days=30)).date())
    call_command("run_billing_cycle", verbosity=0)
    sub.refresh_from_db()
    check(sub.state != Subscription.PAST_DUE,
          "просроченная попытка годовой оплаты НЕ останавливает клиента",
          f"state={sub.state}")

    # ====== РЕГРЕССИИ ИЗ КОД-РЕВЬЮ ======================================
    from datetime import date

    # #5: годовой платёж НЕ перезапускает ЖИВОЙ месячный период ------------
    o5 = Organization.objects.create(id="ann5", display_name="Ann5")
    live_end = now + timedelta(days=20)
    s5 = Subscription.objects.create(
        organization=o5, plan=start, state=Subscription.ACTIVE,
        trial_ends_at=now - timedelta(days=1),
        current_period_start=now - timedelta(days=10), current_period_end=live_end,
        terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    services.mark_paid(services.build_annual_invoice(o5))
    s5.refresh_from_db()
    check(abs((s5.current_period_end - live_end).total_seconds()) < 2
          and s5.base_paid_through is not None,
          "#5 годовой платёж не сдвигает живой месячный период",
          f"period_end {s5.current_period_end} vs {live_end}")

    # #2: в годовом окне (база=0) лимитный оффер НЕ сжигает use --------------
    o2 = Organization.objects.create(id="ann2", display_name="Ann2")
    Subscription.objects.create(
        organization=o2, plan=start, state=Subscription.ACTIVE,
        trial_ends_at=now, current_period_start=now,
        current_period_end=now + timedelta(days=30),
        base_paid_through=now + timedelta(days=300),
        terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    lim = Offer.objects.create(title="Лимит1 -20%", organization=o2,
                               discount_pct=20, max_uses=1)
    usage_of(0)
    z = services.build_invoice(o2, date.today(), date.today() + timedelta(days=30))
    lim.refresh_from_db()
    check(z.total == 0 and z.discount_amount == 0 and lim.uses == 0,
          "#2 нулевой месяц не сжигает use лимитного оффера",
          f"total={z.total} uses={lim.uses}")

    # #3: annual_available видит адресный annual-оффер на тарифе без скидки --
    ent = Plan.objects.get(code="enterprise")   # annual_discount_pct = 0
    o3 = Organization.objects.create(id="ann3", display_name="Ann3")
    Subscription.objects.create(
        organization=o3, plan=ent, state=Subscription.ACTIVE, trial_ends_at=now,
        current_period_start=now, current_period_end=now + timedelta(days=30))
    check(not services.annual_available(o3, ent),
          "#3 без оффера годовая на enterprise не предлагается")
    Offer.objects.create(title="Год адресно -25%", organization=o3,
                         discount_pct=25, applies_to=Offer.APPLIES_ANNUAL)
    check(services.annual_available(o3, ent),
          "#3 адресный annual-оффер включает годовую даже при annual_discount_pct=0")

    # #7: годовой счёт в истории НЕ делает первый месячный «первым месяцем» --
    o7 = Organization.objects.create(id="ann7", display_name="Ann7")
    Subscription.objects.create(
        organization=o7, plan=start, state=Subscription.ACTIVE, trial_ends_at=now,
        current_period_start=now, current_period_end=now + timedelta(days=30),
        terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    a7 = services.build_annual_invoice(o7)   # годовой счёт в истории (ISSUED)
    Offer.objects.create(title="Первый -50%", organization=o7, discount_pct=50,
                         applies_to=Offer.APPLIES_FIRST_MONTH)
    usage_of(0)
    m7 = services.build_invoice(o7, date.today(), date.today() + timedelta(days=30))
    check(a7.is_annual and m7.discount_amount == 0,
          "#7 first_month не применяется, если у клиента уже есть годовой счёт",
          f"скидка {m7.discount_amount}")

    # #1: нулевой счёт ДОВОДИТ правку тарифа (adopt_current_terms) -----------
    o1 = Organization.objects.create(id="ann1", display_name="Ann1")
    s1 = Subscription.objects.create(
        organization=o1, plan=start, state=Subscription.ACTIVE,
        trial_ends_at=now - timedelta(days=1),
        current_period_start=now - timedelta(days=40),
        current_period_end=now - timedelta(seconds=1),
        base_paid_through=now + timedelta(days=300),
        terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    start.monthly_price = Decimal("1234")     # правка тарифа
    start.save(update_fields=["monthly_price"])
    usage_of(0)
    call_command("run_billing_cycle", verbosity=0)
    s1.refresh_from_db()
    check(s1.terms_monthly_price == Decimal("1234"),
          "#1 нулевой счёт продлевает и доводит новую цену тарифа до снимка",
          f"снимок {s1.terms_monthly_price}")
    start.monthly_price = Decimal("990")      # вернуть
    start.save(update_fields=["monthly_price"])

    # #6: зона кабинета считается на ВКЛЮЧЁННОМ ИЗ СНИМКА, не с живого тарифа --
    o6 = Organization.objects.create(id="ann6", display_name="Ann6")
    Subscription.objects.create(
        organization=o6, plan=start, state=Subscription.ACTIVE, trial_ends_at=now,
        current_period_start=now, current_period_end=now + timedelta(days=30),
        terms_monthly_price=start.monthly_price,
        terms_included_requests=10_000,        # снимок = 10k
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    start.included_requests = 50_000           # живой тариф подняли до 50k
    start.save(update_fields=["included_requests"])
    usage_of(20_000)
    pr = services.period_pricing(o6, start,
                                 {"capacity_billable": 20_000})
    check(pr["included"] == 10_000 and pr["zone"] == "metered",
          "#6 зона на снимке (10k) → metered, а не на живом (50k) → included",
          f"included={pr['included']} zone={pr['zone']}")
    start.included_requests = 10_000           # вернуть
    start.save(update_fields=["included_requests"])

    print("=" * 60)
    if not ok:
        raise SystemExit("annual flow not correct")
    print("annual OK — цена+оффер, is_annual, base_paid_through, база=0 в окне, "
          "нулевой самогашение, годовой не стопает, + 5 регрессий из ревью")
    return 0


if __name__ == "__main__":
    sys.exit(main())
