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
# ЕДИНИЦА — ЗАПРОС (docs/billing-integrity.md): он виден в логе шлюза САМОГО
# клиента, поэтому наш счёт сверяем с его независимой записью. Число защищённых
# значений остаётся справкой — оно рождается внутри его контура.
#
# СТАВКА СВЕРХ ВКЛЮЧЁННОГО — около 80% от собственной «включённой» цены тарифа,
# и она УБЫВАЕТ по лестнице. Это не щедрость, а единственная форма, при которой
# подъём окупается: единая ставка уже стояла здесь и делала объём через
# перерасход в десятки раз дешевле того же объёма внутри тарифа — Старт на 3 млн
# запросов платил бы 4 088 ₽ вместо 29 900 ₽ на Масштабе, никто никогда не
# переходил, и выручка упиралась в цену входа. Так же устроен всякий счётный
# российский продукт (Диадок: 11.80 -> 7.02 ₽/документ по лестнице).
#
# ПОРОГ ТАРИФИКАЦИИ У КАЖДОГО ТАРИФА СВОЙ И РАВЕН ЕГО РЕЗЕРВУ на лицензионном
# сервере (`licensing/store.py::RESERVE_MAX`). Это худшая ошибка счёта при
# порванной цепи отчётов — при живой она нулевая. Общая константа 300 000 на все
# тарифы делала Старт бесплатным до 310 000 запросов, то есть его включённый
# объём не значил ничего.
#
# Точки перехода при этих числах: ~67k запросов Старт -> Рабочий, ~458k
# Рабочий -> Промышленный. Выше них тариф выше ДЕШЕВЛЕ перерасхода, всегда.
PLANS = [
    # code, title, ₽/мес, включено запросов, ₽/1000 сверх, порог тарификации,
    # RPM, инстансов, ключей, порядок, для кого
    #
    # THE TIER IS THE INSTANCE COUNT, and it is the only boundary decided on OUR
    # side: the licensing server counts which instance ids leased recently and
    # refuses a new one beyond the plan. Nothing the container reports about
    # itself can be a boundary, because it runs on the customer's hardware.
    #
    # Known and accepted: a customer can put one container behind their own
    # proxy and route everything through it. That is not fixable in software
    # running inside someone else's perimeter — no on-prem product solves it,
    # and the ones that pretend to are enforcing by contract. With volume
    # metered the INCENTIVE disappears anyway: volume is volume, and how many
    # containers pushed it through stops mattering.
    ("start", "Старт", Decimal("990"), 10_000, Decimal("79.00"), 0,
     300, 1, 2, 0, "один бот или сервис в проде"),
    ("work", "Рабочий", Decimal("3900"), 100_000, Decimal("31.00"), 0,
     1_500, 4, 4, 1, "прод, стенд и запас — или несколько команд"),
    ("industrial", "Промышленный", Decimal("11900"), 1_000_000, Decimal("9.50"),
     0, 6_000, 12, 10, 2, "несколько продуктов и отказоустойчивость"),
    ("enterprise", "Enterprise", Decimal("0"), 100_000_000, Decimal("7.00"),
     0, 20_000, 100, 50, 3, "по договору"),
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

        for (code, title, price, included, metered, floor, rpm, instances, keys,
             order, audience) in PLANS:
            # Глобальный потолок объёма: докупать можно до 3× включённого, затем
            # буфер 10% с оффером апгрейда, дальше жёсткая остановка. Enterprise
            # (по договору) — без потолка. Множители здесь, чтобы правились в одном
            # месте; поля тарифа остаются настраиваемыми поштучно при желании.
            if code == "enterprise":
                cap = buffer = discount = 0
            else:
                cap = included * 3
                buffer = cap // 10
                discount = 50
            Plan.objects.update_or_create(code=code, defaults={
                "title": title,
                "monthly_price": price,
                "included_requests": included,
                "metered_per_1k": metered,
                "metered_floor": floor,
                "rpm_limit": rpm,
                "max_instances": instances,
                "max_keys": keys,
                # Enterprise is quoted, not bought on the site: a price of zero
                # rendered next to a "начать пробу" button would sell it for
                # nothing.
                "is_public": code != "enterprise",
                "sort_order": order,
                "audience": audience,
                "overage_cap_requests": cap,
                "buffer_requests": buffer,
                "upgrade_first_month_discount_pct": discount,
            })
        self.stdout.write(f"{len(PLANS)} plans seeded")
