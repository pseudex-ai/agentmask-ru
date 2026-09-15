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

    print("=" * 60)
    if not ok:
        raise SystemExit("offers not correct")
    print("offers OK — адресные+промокод, срок/лимит, лучший-по-сумме, применение скидки")
    return 0


if __name__ == "__main__":
    sys.exit(main())
