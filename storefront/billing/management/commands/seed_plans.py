"""The three tariffs from the landing, as rows.

A management command rather than a data migration: prices change, and a price
living in a migration means the history has to be edited to correct today's
number. Idempotent, so it is safe on every deploy.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from billing import licensing, services
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
# ПОРОГ ТАРИФИКАЦИИ = 0 НА ВСЕХ ТАРИФАХ (решение владельца): биллим с первого
# запроса сверх включённого, без «бесплатной полосы» поверх. Раньше порог был
# привязан к резерву ёмкости сервера (`licensing/store.py::RESERVE_MAX`) — это
# худшая ошибка счёта при ПОРВАННОЙ цепи отчётов, при живой она нулевая. Полоса
# путала («купил 10k — биллится с 30k?!») и раздавала объём даром, поэтому её
# убрали; поле `metered_floor` осталось настраиваемым (не 0 → полоса вернётся),
# но с резервом больше НЕ сверяется. Редкий край при обрыве отчётов —
# завышение на ширину резерва — принят, он само-корректируется отчётом.
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


# БЕСПЛАТНЫЙ ТАРИФ — ЭТО САМА ПРОБА, А НЕ ВТОРАЯ БЕСПЛАТНАЯ ДВЕРЬ.
#
# Строка с этим именем здесь уже была однажды и была убрана правильно: она
# стояла НА ЛЕНДИНГЕ рядом с четырнадцатидневной пробой, и получалось два
# противоречащих друг другу бесплатных входа. Сейчас она возвращается в другой
# роли — на ней живёт сама проба, и на лендинге её нет (`is_public=False`),
# выбрать её нельзя, попадают на неё все и сразу.
#
# ЗАЧЕМ ВООБЩЕ. Проба шла на ВЫБРАННОМ тарифе: человек отмечал в форме
# «Промышленный» и получал миллион запросов бесплатно на две недели, и так с
# каждой новой почты. Теперь обслуживание на пробе идёт по этим лимитам —
# десятая часть «Старта»: хватает подключить, прогнать свои сценарии и увидеть,
# что агент не сломался, а работать на этом в проде нельзя.
#
# ВСЕ ЧИСЛА ЗДЕСЬ — ТОЛЬКО ПЕРВОНАЧАЛЬНЫЕ. Дальше они правятся в админке, и
# правка доходит до следующей регистрации без выката; `update_or_create` их не
# перетирает, потому что для этой строки мы задаём defaults только при создании.
FREE_PLAN = {
    "code": "free",
    "title": "Бесплатный",
    "monthly_price": Decimal("0"),
    "included_requests": 1_000,
    "metered_per_1k": Decimal("0"),   # сверх лимита — не счёт, а остановка
    "metered_floor": 0,
    "rpm_limit": 30,
    "max_instances": 1,
    "max_keys": 1,
    "is_public": False,               # на лендинге его нет: это проба, а не выбор
    "sort_order": 9,
    "audience": "познакомиться с продуктом",
    "overage_cap_requests": 0,
    "buffer_requests": 0,
    "upgrade_first_month_discount_pct": 0,
    "annual_discount_pct": 0,
    "is_trial": True,
    "trial_days": services.TRIAL_DAYS_SEED,
    "first_payment_bonus_days": 0,
}

# Лимиты той же строки НА ЛИЦЕНЗИОННОМ СЕРВЕРЕ. Он исполняет потолок инстансов и
# выдаёт ёмкость порциями, и знает тарифы по коду — незнакомый код он отклоняет
# при выпуске ключа, поэтому без этой отправки регистрация ломалась бы на первом
# же новом аккаунте. Кванты мелкие под стать объёму: выдавать пробе порцию
# размером с её месячный лимит значит отдать весь лимит одним запросом.
FREE_PLAN_LIMITS = {
    "max_instances": 1,
    "processes_per_instance": 2,
    "grant_size": 500,
    "quantum_min": 100,
    "quantum_max": 1_000,
    "reserve_max": 2_000,
}

# ДНЕЙ В ПОДАРОК ЗА НЕМЕДЛЕННУЮ ОПЛАТУ. Пока заплатить было нельзя вовсе, весь
# выбор человека был «досидеть пробу», и повода заплатить сегодня не возникало
# никогда. Число стартовое — дальше правится в админке по каждому тарифу.
FIRST_PAYMENT_BONUS_DAYS = 30


class Command(BaseCommand):
    help = "Create or update the public plans"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-licensing", action="store_true",
            help="не отправлять бесплатный тариф на лицензионный сервер "
                 "(локальный прогон без него)")

    def handle(self, *args, **options) -> None:
        # Plans removed from PLANS are retired, not left behind. A permanent
        # "Бесплатный" row survived a previous seed and would have been offered
        # on the landing beside a 14-day trial — two contradictory free entries,
        # one of them unintended.
        keep = {code for code, *_ in PLANS} | {FREE_PLAN["code"]}
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
                cap = buffer = discount = annual = 0
            else:
                cap, buffer = services.derive_cap_and_buffer(included)
                discount = services.UPGRADE_DISCOUNT_PCT
                annual = services.ANNUAL_DISCOUNT_PCT
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
                "annual_discount_pct": annual,
            })
            # ПОДАРОЧНЫЕ ДНИ ПРОСТАВЛЯЮТСЯ ТОЛЬКО ПРИ СОЗДАНИИ СТРОКИ.
            #
            # Остальные поля выше сид перетирает намеренно — цена и лимиты
            # живут в этом файле и правятся выкатом. Это поле живёт в админке
            # по прямому требованию: перетирать его на каждом деплое значило бы
            # молча отменять решение владельца через неделю после того, как он
            # его принял, и заметил бы он это по выручке, а не по экрану.
            if code != "enterprise":
                Plan.objects.filter(code=code, first_payment_bonus_days=0).update(
                    first_payment_bonus_days=FIRST_PAYMENT_BONUS_DAYS)

        # ── бесплатный тариф: создаём, но НЕ перетираем ─────────────────────
        free_code = FREE_PLAN["code"]
        free, created = Plan.objects.get_or_create(
            code=free_code, defaults={k: v for k, v in FREE_PLAN.items() if k != "code"})
        if not created and not free.is_trial:
            # Строка есть, но отметку сняли: это могло быть сделано руками ради
            # выключения пробы, и возвращать её молча нельзя — иначе админка
            # перестаёт что-либо решать. Говорим вслух и не трогаем.
            self.stdout.write(self.style.WARNING(
                f"тариф {free_code} есть, но не отмечен пробным — оставлен как есть"))

        self.stdout.write(f"{len(PLANS) + 1} plans seeded"
                          + (f", {free_code} created" if created else ""))

        # ── и он же на лицензионном сервере ─────────────────────────────────
        # БЕЗ ЭТОГО РЕГИСТРАЦИЯ ЛОМАЕТСЯ НА ПЕРВОМ ЖЕ АККАУНТЕ: выпуск ключа
        # отклоняет незнакомый код тарифа, а теперь на пробе стоит `free`.
        # Отказ здесь — это отказ команды, а не предупреждение: деплой, молча
        # оставивший сервер без этого тарифа, выкатит сломанную регистрацию.
        # НЕНАСТРОЕННЫЙ СЕРВЕР — ЭТО НЕ ОТКАЗ, А ДРУГОЕ ОКРУЖЕНИЕ.
        #
        # Тесты и локальный прогон поднимают витрину без лицензионного сервера
        # вовсе: падать там значило бы требовать его для каждого `migrate`. А на
        # проде токен задан всегда, и тогда отказ — это отказ.
        configured = bool(getattr(settings, "LICENSING_ADMIN_TOKEN", ""))
        if options.get("no_licensing") or not configured:
            why = "по флагу" if options.get("no_licensing") else "он не настроен"
            self.stdout.write(self.style.WARNING(
                f"лицензионный сервер пропущен ({why}) — тариф {free_code} там "
                "может отсутствовать, и тогда регистрация будет падать на "
                "выпуске ключа"))
            return
        try:
            licensing.set_plan(free_code, FREE_PLAN_LIMITS, actor="seed_plans")
        except licensing.LicensingError as error:
            raise CommandError(
                f"тариф {free_code} не отправлен на лицензионный сервер: {error}. "
                "Регистрация упадёт на выпуске ключа. Поднимите сервер и "
                "повторите, либо запустите с --no-licensing, если это локальный "
                "прогон без него.") from error
        self.stdout.write(f"{free_code} отправлен на лицензионный сервер")
