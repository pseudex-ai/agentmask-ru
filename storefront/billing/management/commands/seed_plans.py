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
# code, title, ₽/мес, включено, ₽/1000 сверх, инстансов, ключей, порядок
#
# THE OVERAGE RATE IS PER-TIER, and that is the fix for a real arithmetic bug.
# It was a single 0.40 ₽ inherited from the mock while the tier prices moved
# under it, which made buying volume through overage 50–242× cheaper than
# buying the same volume inside a tier: a Старт customer at 3M requests paid
# 4 088 ₽ instead of 29 900 ₽ on Масштаб. Nobody would ever upgrade and revenue
# capped near the entry price.
#
# Each rate is ~80% of that tier's own included rate, so overage is a mild
# discount for going over — never a cheaper route than the tier above. And it
# DECLINES with volume, which is what every metered Russian product does
# (Диадок: 11.80 -> 7.02 ₽/документ across its ladder): the customer who grows
# gets a better unit price, and the ladder still pays to climb.
PLANS = [
    ("start", "Старт", Decimal("2900"), 30_000, Decimal("77"), 1, 2, 0),
    ("prod", "Прод", Decimal("9900"), 300_000, Decimal("26"), 4, 4, 1),
    ("scale", "Масштаб", Decimal("29900"), 1_500_000, Decimal("16"), 12, 10, 2),
    ("enterprise", "Enterprise", Decimal("0"), 10_000_000, Decimal("10"), 100, 50, 3),
]


class Command(BaseCommand):
    help = "Create or update the public plans"

    def handle(self, *args, **options) -> None:
        for code, title, price, included, overage, instances, keys, order in PLANS:
            Plan.objects.update_or_create(code=code, defaults={
                "title": title,
                "monthly_price": price,
                "included_requests": included,
                "overage_per_1k": overage,
                "max_instances": instances,
                "max_keys": keys,
                # Enterprise is quoted, not bought on the site: a price of zero
                # rendered next to a "начать пробу" button would sell it for
                # nothing.
                "is_public": code != "enterprise",
                "sort_order": order,
            })
        self.stdout.write(f"{len(PLANS)} plans seeded")
