"""`decompose` — series/number, last/first/middle, street/house/flat, card parts.

«паспрот 4509 123456 выдан оуфмс москвы 12.05.2010 код 770-045 снилс
112-233-445 95 иванов пётр сергеевич» → passport_verify(passport{series,
number, issued_by, issue_date, department_code}, snils, person{last, first,
middle}). One dictated value becomes five fields; `issued_by` and
`department_code` are PLAIN and must survive byte-identical.
Three sub-shapes rotate: passport, courier (address by parts), payment (card
by parts + cardholder).
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("passport_verify", "courier_book", "payment_create", "crm_upsert_contact")


def build(seed: int, count: int) -> list[Case]:
    rng = c.ctx_for("decompose", seed, 0, "chat").rng
    registers = c.registers_for(count, rng)
    for index in range(min(3, count)):
        registers[index] = "clean"
    rng.shuffle(registers)
    return [_one(c.ctx_for("decompose", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    shape = ctx.index % 3
    if shape == 0:
        return _passport(ctx)
    if shape == 1:
        return _courier(ctx)
    return _payment(ctx)


def _passport(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx)
    identity = f"p{ctx.index}"
    series, number = pools.passport_digits(ctx.rng)
    snils_digits = pools.snils_digits(ctx.rng)
    code = f"{ctx.rng.randrange(100, 999)}-{ctx.rng.randrange(100, 999):03d}"
    issued = ctx.rng.choice(("отделом уфмс россии по городу москве", "оуфмс по удмуртской республике в ленинском районе",
                             "гу мвд россии по краснодарскому краю"))
    builder = c.CaseBuilder(
        ctx=ctx, role="gov", tools=TOOLS, reachable=("passport_verify",),
        primary_identity=identity, cluster=f"PASSPORT:{series}{number}",
        conversation_id=f"conv-dec-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="серия и номер отдельными полями; кем выдан и код подразделения — plain")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("сверьте паспорт" if ctx.register != "sloppy" else "сверьте паспрот")
    first.value("pp1", c.passport(ctx, series, number))
    first.say("выдан").plain_value("iss", issued, "room_number", "кем выдан — орган, не ПД")
    if ctx.register == "voice_raw":
        first.say("код подразделения").plain_value(
            "code", " ".join(pools.spell_groups(code.replace("-", ""), (3, 3))),
            "order_number", "код подразделения — не ПД, обязан уцелеть")
    else:
        first.say("код подразделения").plain_value("code", code, "order_number",
                                                   "код подразделения — не ПД, обязан уцелеть")
    first.say("снилс").value("s1", c.snils(ctx, snils_digits))
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given", "patronymic")))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"pp1": ("PASSPORT", identity, "required", False),
                         "s1": ("SNILS", identity, "required", False),
                         "n1": ("NAME", identity, "required", False)})
    return builder.build()


def _courier(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True, with_entrance=True, with_type=ctx.rng.random() < 0.4)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=("courier_book",),
        primary_identity=identity, cluster=f"LOC:{drawn.address.street} {drawn.address.house}",
        conversation_id=f"conv-dec-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="адрес одной фразой уходит в locality/street/building/porch/sflat")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("курьера на")
    first.value("a1", c.address(ctx, drawn.address))
    first.say("это в").say(city)
    first.say("получатель").value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    first.say(ctx.rng.choice(("завтра с десяти до двух", "в четверг с двух до шести")))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"a1": ("LOC", identity + ".addr", "required", False),
                         "n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})
    return builder.build()


def _payment(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx)
    identity = f"p{ctx.index}"
    card_digits = pools.card_digits(ctx.rng)
    month = f"{ctx.rng.randrange(1, 13):02d}"
    year = str(ctx.rng.randrange(2027, 2031))
    amount = ctx.rng.choice((780, 990, 450, 620))
    builder = c.CaseBuilder(
        ctx=ctx, role="bank", tools=TOOLS, reachable=("payment_create",),
        primary_identity=identity, cluster=f"CARD:{card_digits}",
        conversation_id=f"conv-dec-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="карта по частям: номер, месяц, год, держатель латиницей — производная от имени")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("проведите оплату")
    first.plain_value("amt", (" ".join(pools.spell_groups(str(amount), (len(str(amount)),)))
                              if ctx.spoken else str(amount)) + " рублей",
                      "quantity", "сумма — не ПД")
    first.say("карта").value("cd1", c.card(ctx, card_digits))
    if ctx.spoken:
        first.say("срок").plain_value("exp", f"{pools.spell_cardinal(int(month))} {pools.spell_year(int(year))}",
                                      "time_of_day", "срок действия — не ПД")
    else:
        first.say("срок").plain_value("exp", f"{month}/{year[2:]}", "time_of_day", "срок действия — не ПД")
    first.say("держатель").value("n1", c.name(ctx, drawn.person, ("given", "surname")))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"cd1": ("CARD", identity, "required", False),
                         "n1": ("NAME", identity, "required", False)})
    return builder.build()
