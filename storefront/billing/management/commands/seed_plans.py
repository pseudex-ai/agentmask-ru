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
    # code, title, ₽/мес, ориентир по значениям, RPM, инстансов, ключей, порядок
    #
    # BILLED ON TIME, NOT ON VOLUME — and that is the whole design, not a
    # simplification. The lease is the one meter we own: the container must call
    # us every 24 hours or stop, and we count those calls on our side. Every
    # other number — values, requests, entities — is produced inside the
    # customer's container, on their hardware, under their root, and can be
    # made to say anything.
    #
    # So the money comes from the subscription, which cannot be forged, and the
    # value count becomes what it is genuinely good at: telling the customer and
    # us whether the plan they chose still fits. Under-declaring is pointless
    # when nothing is charged per unit, and a plan that no longer matches shows
    # up in the reported numbers as a conversation rather than a fight.
    #
    # `included_values` is therefore a SIZING GUIDE, not a hard limit. Crossing
    # it does not generate a charge; it puts an upgrade suggestion in the cabinet.
    ("start", "Старт", Decimal("990"), 10_000, 300, 1, 2, 0),
    ("work", "Рабочий", Decimal("4900"), 100_000, 1_500, 4, 4, 1),
    ("industrial", "Промышленный", Decimal("19900"), 1_000_000, 6_000, 12, 10, 2),
    ("enterprise", "Enterprise", Decimal("0"), 100_000_000, 20_000, 100, 50, 3),
]

class Command(BaseCommand):
    help = "Create or update the public plans"

    def handle(self, *args, **options) -> None:
        # Plans removed from PLANS are retired, not left behind. A permanent
        # "Бесплатный" row survived a previous seed and would have been offered
        # on the landing beside a 14-day trial — two contradictory free entries,
        # one of them unintended.
        keep = {code for code, *_ in PLANS}
        retired = Plan.objects.exclude(code__in=keep)
        # Only hidden, never deleted: a subscription points at its plan, and a
        # customer who bought last year's tariff keeps the terms they bought.
        retired.update(is_public=False)

        for code, title, price, included, rpm, instances, keys, order in PLANS:
            Plan.objects.update_or_create(code=code, defaults={
                "title": title,
                "monthly_price": price,
                "included_values": included,
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
