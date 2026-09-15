"""Спец-предложения (Offer): резолв адресных/публичных, срок/лимит, применение скидки.

Запуск:  cd storefront && .venv/bin/python test_offers.py
"""
import os
import sys
from decimal import Decimal


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "offers-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-offers-test.db"
    if os.path.exists("/tmp/pseudex-offers-test.db"):
        os.remove("/tmp/pseudex-offers-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)
    from django.utils import timezone
    from datetime import timedelta
    from accounts.models import Organization
    from billing.models import Offer, Plan
    from billing import services

    ok = True
    def check(cond, name):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok = ok and cond

    org = Organization.objects.create(id="offco", display_name="Offer Co")
    other = Organization.objects.create(id="other", display_name="Other Co")
    Offer.objects.create(title="VIP -30%", organization=org, discount_pct=30)
    Offer.objects.create(title="Промо -1000", code="P1000", discount_amount=Decimal("1000"),
                         applies_to=Offer.APPLIES_ANNUAL)
    Offer.objects.create(title="Истёкший -90%", organization=org, discount_pct=90,
                         valid_until=timezone.now() - timedelta(days=1))
    Offer.objects.create(title="Исчерпан -50%", organization=org, discount_pct=50,
                         max_uses=1, uses=1)

    a = services.resolve_offer(org)
    check(a is not None and a.discount_pct == 30, "адресный оффер резолвится (истёкший/исчерпанный отсеяны)")
    check(a.apply_to(Decimal("10000")) == Decimal("7000.00"), "скидка % применяется (10000 -30% = 7000)")
    check(services.resolve_offer(other) is None, "чужой org без офферов → None")

    code = services.resolve_offer(other, code="P1000", applies_to=Offer.APPLIES_ANNUAL)
    check(code is not None and code.discount_amount == Decimal("1000"),
          "публичный промокод резолвится по code")
    check(code.apply_to(Decimal("47000")) == Decimal("46000.00"), "фикс-скидка применяется (47000 -1000)")

    # промокод не подходит к типу 'first_month'
    check(services.resolve_offer(other, code="P1000", applies_to=Offer.APPLIES_FIRST_MONTH) is None,
          "оффер типа annual не резолвится для first_month")

    # лучший по СУММЕ: на 47000 VIP-30% (32900) выгоднее промо -1000 (46000)
    best = services.resolve_offer(org, code="P1000", applies_to=Offer.APPLIES_ANNUAL,
                                  amount=Decimal("47000"))
    check(best is not None and best.title == "VIP -30%",
          "при сумме выбирается выгоднейшее клиенту (VIP -30% на 47000)")

    # --- ВПЛЕТЕНИЕ В СЧЁТ: оффер больше НЕ инертен ---------------------
    from datetime import date
    from billing.models import Invoice, Subscription
    from billing.services import build_invoice

    start = Plan.objects.get(code="start")          # 990 ₽/мес
    now = timezone.now()
    buyer = Organization.objects.create(id="buyer", display_name="Buyer Co")
    Subscription.objects.create(
        organization=buyer, plan=start, state=Subscription.ACTIVE,
        trial_ends_at=now, current_period_start=now,
        current_period_end=now, terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    # Без перерасхода: usage замокан пустым.
    services.licensing.usage = lambda org_id: {"usage": {
        "values": 0, "requests": 0, "capacity_billable": 0}}

    Offer.objects.create(title="Адресный -20%", organization=buyer, discount_pct=20)
    inv1 = build_invoice(buyer, date.today(), date.today() + timedelta(days=30))
    check(inv1.discount_amount == Decimal("198.00")
          and inv1.total == Decimal("792.00")
          and inv1.discount_offer is not None,
          "адресный оффер применён к счёту: 990 -20% = 792, скидка отдельной строкой")
    applied = Offer.objects.get(title="Адресный -20%")
    check(applied.uses == 1, "счётчик использований оффера инкрементнут")

    # first_month действует только на первом счёте.
    firstie = Organization.objects.create(id="firstie", display_name="First Co")
    Subscription.objects.create(
        organization=firstie, plan=start, state=Subscription.ACTIVE,
        trial_ends_at=now, current_period_start=now, current_period_end=now,
        terms_monthly_price=start.monthly_price,
        terms_included_requests=start.included_requests,
        terms_metered_per_1k=start.metered_per_1k,
        terms_metered_floor=start.metered_floor, terms_taken_at=now)
    Offer.objects.create(title="Первый месяц -50%", organization=firstie,
                         discount_pct=50, applies_to=Offer.APPLIES_FIRST_MONTH)
    fm1 = build_invoice(firstie, date.today(), date.today() + timedelta(days=30))
    fm1.state = Invoice.ISSUED
    fm1.save(update_fields=["state"])
    check(fm1.discount_amount == Decimal("495.00"),
          "first_month применён на ПЕРВОМ счёте (990 -50% = 495)")
    fm2 = build_invoice(firstie, date.today() + timedelta(days=30),
                        date.today() + timedelta(days=60))
    check(fm2.discount_amount == Decimal("0"),
          "first_month НЕ применяется на втором счёте")

    print("=" * 60)
    if not ok:
        raise SystemExit("offers not correct")
    print("offers OK — резолв, срок/лимит, лучший-по-сумме, ВПЛЕТЕНИЕ В СЧЁТ + инкремент")
    return 0


if __name__ == "__main__":
    sys.exit(main())
