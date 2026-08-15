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
    # code, title, ₽/мес, включено значений, ₽/1000 сверх, RPM, инстансов, ключей, порядок
    #
    # The cheap entry is FREE, not cheap. Every comparable Russian product has a
    # free tier, and a solo developer whose bot serves 200 clients a month uses
    # ~400 protected values — so the floor of the market runs at zero forever
    # and grows into a paid tier by rate and volume, not by a paywall.
    ("free", "Бесплатный", Decimal("0"), 5_000, Decimal("0"), 60, 1, 1, 0),

    # Effective ₽ per 1000 protected values: 396 / 116 / 53. Benchmarked against
    # Dadata's 20 коп./адрес (200 ₽/1000 records enriched) — the closest Russian
    # per-record meter found. Overage sits at ~80% of each tier's own rate and
    # declines with volume, following Diadoc's curve (11.80 -> 7.02 ₽/документ),
    # so the upgrade is a real decision: you move up because the next tier's
    # unit price is better and the rate ceiling is binding.
    ("start", "Старт", Decimal("9900"), 25_000, Decimal("320"), 300, 1, 2, 1),
    ("work", "Рабочий", Decimal("29000"), 250_000, Decimal("100"), 1_500, 4, 4, 2),
    ("industrial", "Промышленный", Decimal("79000"), 1_500_000, Decimal("45"), 6_000, 12, 10, 3),
    ("enterprise", "Enterprise", Decimal("0"), 10_000_000, Decimal("30"), 20_000, 100, 50, 4),
]


class Command(BaseCommand):
    help = "Create or update the public plans"

    def handle(self, *args, **options) -> None:
        for code, title, price, included, overage, rpm, instances, keys, order in PLANS:
            Plan.objects.update_or_create(code=code, defaults={
                "title": title,
                "monthly_price": price,
                "included_values": included,
                "overage_per_1k": overage,
                "rpm_limit": rpm,
                "max_instances": instances,
                "max_keys": keys,
                # Enterprise is quoted, not bought on the site: a price of zero
                # rendered next to a "начать пробу" button would sell it for
                # nothing.
                "is_public": code != "enterprise",
                "sort_order": order,
            })
        self.stdout.write(f"{len(PLANS)} plans seeded")
