"""The three tariffs from the landing, as rows.

A management command rather than a data migration: prices change, and a price
living in a migration means the history has to be edited to correct today's
number. Idempotent, so it is safe on every deploy.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from billing.models import Plan

# Lowered from the mock's 19 000 / 49 000. Those were placed before anyone had
# been asked to pay them, and the smallest real customer we modelled — a solo
# developer running a booking bot that earns him 40 000 ₽/month — would not
# have read past the price. A tariff nobody at the bottom of the market can
# afford does not select for serious customers, it just removes the bottom of
# the funnel, and the bottom is where the word of mouth starts.
#
# The overage rate is unchanged: it is the number that scales with real cost,
# and it was not the thing making the entry unaffordable.
PLANS = [
    ("start", "Старт", Decimal("2900"), 30_000, 1, 2, 0),
    ("prod", "Прод", Decimal("9900"), 300_000, 4, 4, 1),
    ("scale", "Масштаб", Decimal("29900"), 1_500_000, 12, 10, 2),
    ("enterprise", "Enterprise", Decimal("0"), 10_000_000, 100, 50, 3),
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
