"""`correction` — the customer says a value, then corrects it; the SECOND is current.

«адрес ленина четырнадцать квартира пять ой нет не четырнадцать сорок один
квартира пять» → courier_book(address{street: ленина, building: 41, sflat: 5}).
Two items of one identity, the first marked `stale`. The ground truth points
at the second occurrence, which `text.find` can never return — this family is
the positive evidence that no offset in the corpus was searched for.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("courier_book", "crm_upsert_contact", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("correction", seed, 0, "chat").rng)
    return [_one(c.ctx_for("correction", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True, with_type=False)
    identity = f"p{ctx.index}"
    wrong = pools.Address(street=drawn.address.street, street_type="",
                          house=(drawn.address.house + 27) % 180 + 1, letter="",
                          entrance=0, flat=drawn.address.flat, korpus=0, city="")
    right = pools.Address(street=drawn.address.street, street_type="",
                          house=drawn.address.house, letter="", entrance=0,
                          flat=drawn.address.flat, korpus=0, city="")
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=("courier_book",),
        primary_identity=identity, cluster=f"LOC:{right.street} {right.house}",
        conversation_id=f"conv-corr-{ctx.index}" if ctx.index % 2 else "",
        note="второе упоминание адреса отменяет первое; эталон указывает на второе")

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("курьера на").say("адрес" if ctx.rng.random() < 0.5 else "")
    first.value("a_old", c.address(ctx, wrong))
    first.say(ctx.rng.choice(("ой нет", "стоп", "простите ошиблась", "нет не так")))
    first.say("правильно")
    first.value("a_new", c.address(ctx, right))
    # THE CITY IS SAID, because `courier_book` requires `locality` and the
    # first live pilot showed the model asking «в каком городе?» in EVERY arm of
    # every correction case — three arms spent to learn that the schema wants a
    # field the utterance never carried. The address VALUES stay city-less: a
    # correction restates the street, not the town.
    first.say("это в").say(city)
    first.say("это").value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"a_old": ("LOC", identity + ".addr", "required", True),
                         "a_new": ("LOC", identity + ".addr", "required", False),
                         "n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})
    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("завтра с десяти до двух", "в четверг после обеда",
                               "в любой день с девяти до шести")))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {})
    return builder.build()
