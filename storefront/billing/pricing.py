"""What a month of protected values costs.

A LADDER, NOT TIERS. The price per thousand falls as volume rises, and it falls
automatically — there is no plan to choose, outgrow, or be upsold into. Two
reasons, and the second is the one that matters:

  * A customer who doubles their traffic should not have to notice, negotiate or
    migrate. Every metered Russian product that works this way does it for that
    reason (Diadoc runs 11.80 -> 7.02 ₽/документ across its ladder).
  * Tiers create a moment where growing makes the customer worse off: the value
    just past the included volume costs more than the ones before it. That
    moment is where support tickets and churn come from. A ladder has no such
    moment.

THE UNIT IS A PROTECTED VALUE: one distinct real personal datum that did not
reach the model. A phone number appearing in fifty messages of one conversation
is ONE protected value, not fifty — the engine's audit already works that way,
and the customer sees the same number in their own local interface. That is the
property no other meter has: they can check our invoice against their own
screen, instead of taking a request count on faith.
"""

from decimal import ROUND_HALF_UP, Decimal

# (up to N values, ₽ per 1000 within this band)
#
# Rates benchmarked against Dadata's 20 коп./адрес — 200 ₽ per 1000 records
# enriched, the closest per-record meter in the Russian market. The lower bands
# sit above it because a protected value is worth more than an enriched one, and
# the top bands below it because at that volume the competition is the
# customer's own decision to build this themselves.
#
# Calibrated to the meter that counts PEOPLE, not messages. The first version of
# this ladder was built for a counter that logged a cache miss, which inflated
# every number by roughly the length of a conversation — so its bands were an
# order of magnitude too high for what a real customer actually protects.
#
# Modelled volumes, to be replaced by measurements from the persona runs and the
# first real customers rather than defended:
#   бот с 200 клиентами в месяц   ~200 значений   (укладывается в бесплатное)
#   CRM на 40 автосервисов        ~6 000
#   доставка еды, 300 сотрудников ~60 000
#
# A returning customer costs nothing: their data is already in the vault. That
# is what makes these numbers small and what makes the meter defensible — the
# customer is charged once per person, not once per conversation.
LADDER: list[tuple[int | None, Decimal]] = [
    (1_000, Decimal("0")),        # бесплатно, и не пробный период — навсегда
    (10_000, Decimal("400")),
    (100_000, Decimal("250")),
    (1_000_000, Decimal("120")),
    (None, Decimal("60")),
]

# Право использования: one instance. Small on purpose — starting must not be a
# budget decision, and everything that scales with usage lives in the ladder.
PLATFORM_FEE = Decimal("990")
EXTRA_INSTANCE_FEE = Decimal("490")


def price_values(count: int) -> tuple[Decimal, list[tuple[int, Decimal, Decimal]]]:
    """Cost of `count` protected values, and the per-band breakdown for the
    invoice.

    PROGRESSIVE, like income tax: each band prices only the values that fall
    inside it. A customer at 60 000 pays nothing for the first 5 000, 300 ₽/1000
    for the next 45 000, and 100 ₽/1000 for the last 10 000 — never 300 ₽/1000
    on the whole amount. Charging the whole volume at the band it lands in would
    mean one value over a boundary raises the price of every value below it,
    which is the cliff this ladder exists to avoid.
    """
    total = Decimal("0")
    breakdown: list[tuple[int, Decimal, Decimal]] = []
    remaining = count
    floor = 0
    for ceiling, rate in LADDER:
        if remaining <= 0:
            break
        span = remaining if ceiling is None else min(remaining, ceiling - floor)
        if span > 0:
            # Per started thousand: fractions produce kopeck lines nobody can
            # reconcile against their own counter.
            thousands = (span + 999) // 1000
            amount = (Decimal(thousands) * rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
            breakdown.append((span, rate, amount))
            total += amount
            remaining -= span
        if ceiling is not None:
            floor = ceiling
    return total.quantize(Decimal("0.01"), ROUND_HALF_UP), breakdown


def month_total(values: int, instances: int) -> Decimal:
    fee = PLATFORM_FEE + EXTRA_INSTANCE_FEE * max(0, instances - 1)
    return (fee + price_values(values)[0]).quantize(Decimal("0.01"), ROUND_HALF_UP)
