"""The three tariffs from the landing, as rows.

A management command rather than a data migration: prices change, and a price
living in a migration means the history has to be edited to correct today's
number. Idempotent, so it is safe on every deploy.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from billing.models import Plan

PLANS = [
    ("start", "Старт", Decimal("19000"), 100_000, 1, 2, 0),
    ("prod", "Прод", Decimal("49000"), 1_000_000, 8, 6, 1),
    ("enterprise", "Enterprise", Decimal("0"), 10_000_000, 100, 50, 2),
]


class Command(BaseCommand):
    help = "Create or update the public plans"

    def handle(self, *args, **options) -> None:
        for code, title, price, included, instances, keys, order in PLANS:
            Plan.objects.update_or_create(code=code, defaults={
                "title": title,
                "monthly_price": price,
                "included_requests": included,
                "overage_per_1k": Decimal("0.40"),
                "max_instances": instances,
                "max_keys": keys,
                # Enterprise is quoted, not bought on the site: a price of zero
                # rendered next to a "начать пробу" button would sell it for
                # nothing.
                "is_public": code != "enterprise",
                "sort_order": order,
            })
        self.stdout.write(f"{len(PLANS)} plans seeded")
