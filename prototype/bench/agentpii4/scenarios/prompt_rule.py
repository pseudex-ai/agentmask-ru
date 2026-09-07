"""`prompt_rule` — в промпте бизнес-правило, и подмена может его НАРУШИТЬ.

«Заказы с номером дома больше 100 не оформляем — это промзона.» Клиент живёт в
доме 34; подмена ставит дом 212, агент читает своё же правило и ОТКАЗЫВАЕТ —
инструмент не вызывается вовсе. Ни одного вызова, ни одной ошибки, 200 нигде, и
в журнале нет ничего, что бы это объяснило.

Прямая формулировка владельца: «у нас в промте явно написанно что мы не возим в
центр питера и так получилось что подмененное значение именно центр питера из
памяти модели хотя пользваоель назвал адре в другом районе, и тул бы обработал
нормально но моделька начнет возмущатся».

ГРАНИЦА ПО НОМЕРУ ДОМА, А НЕ СПИСОК УЛИЦ, И ЭТО ВАЖНО. Список улиц в промпте
пришлось бы подбирать под пул подмен движка, а это ровно то, что владелец
запретил: «не тюнить движок под собственный генератор» — здесь то же самое
наоборот. Номер дома движок чеканит случайным, поэтому столкновение возникает
по устройству данных, а не потому, что мы его подстроили; правило «до дома N»
— настоящая форма зоны доставки.

ТРИ ФОРМЫ, И ТРЕТЬЯ — КОНТРОЛЬНАЯ:
  * граница, которую настоящий адрес НЕ переходит, а подмена может;
  * граница, которую переходят ОБА — оба плеча обязаны отказать одинаково,
    иначе мы измеряем не шлюз, а собственную удачу;
  * правило про ГОРОД: движок сохраняет населённый пункт внутри подмены
    (`vault._settlement_of`), поэтому оно не должно срабатывать ни в одном
    плече. Семья, где правило ломается всегда, не отличает поломку от нормы.
"""
import dataclasses

from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("delivery_create_order", "courier_book", "crm_find_contact", "notify_sms",
         "delivery_quote", "crm_add_note")
_LIMIT = 100


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("prompt_rule", seed, 0, "chat").rng)
    return [_one(c.ctx_for("prompt_rule", seed, index, registers[index])) for index in range(count)]


def _rule(ctx: c.Ctx, city: str) -> str:
    if ctx.index % 3 == 2:
        # The control shape: a rule about the SETTLEMENT, which the engine keeps
        # real. It must fire identically in both arms — that is, never.
        return (f"Доставляем только по городу {city.capitalize()}; в другие города "
                f"заказы не оформляем.")
    return (f"Заказы с номером дома больше {_LIMIT} не оформляем — это промзона, "
            f"туда курьер не ездит.")


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True)
    # THE REAL HOUSE OBEYS THE RULE. `draw_address` numbers houses across the
    # whole range, so a case whose real address is already outside the boundary
    # measures the rule and not the gateway — both arms would refuse and agree.
    # One in three is built to break it in BOTH arms on purpose, and that is
    # the second shape named in the docstring.
    breaks_anyway = ctx.index % 3 == 1
    house = ctx.rng.randrange(_LIMIT + 12, _LIMIT + 90) if breaks_anyway else ctx.rng.randrange(1, _LIMIT - 10)
    address = dataclasses.replace(drawn.address, house=house, letter="")
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS,
        reachable=("crm_find_contact", "delivery_quote", "delivery_create_order", "notify_sms"),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-rule-{ctx.index}" if ctx.index % 2 == 0 else "",
        rule=_rule(ctx, city),
        note="правило доставки в системном промпте; подмена может его нарушить "
             "и агент откажет там, где отказывать не следовало")
    # THE CARD HOLDS THE SAME ADDRESS THE CUSTOMER SAYS. Seeded with
    # `drawn.address` it held the same STREET at a different house, so the two
    # arms had two real addresses of one person to choose between: one read the
    # message, the other read the card it had just looked up, and the
    # comparator scored a correct restoration as a changed house number. A case
    # that offers the model two right answers measures which one it picked.
    import dataclasses as _dc
    c.contact_seed("c-1", _dc.replace(drawn, address=address), city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("оформите доставку на")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say("адрес")
    second.value("a1", c.address(ctx, address))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {"a1": ("LOC", identity + ".home", "required", False)})

    third = c.MessageDraft(ctx)
    # NO PUNCTUATION INSIDE `say`: it glues to the word and the register gate
    # refuses voice_raw with a comma in it. Speech does not carry one.
    third.say(ctx.rng.choice(("оформляйте и смс пришлите", "давайте оформим и подтверждение смс",
                              "всё оформляйте и смс на этот номер")))
    builder.user(third, {})
    return builder.build()
