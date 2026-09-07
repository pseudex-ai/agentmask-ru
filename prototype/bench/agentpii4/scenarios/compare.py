"""`compare` — three real records come back, and the agent must choose one.

«курьера на садовую 12 это в колпино» → address_suggest returns {Колпино,
Садовая, 12}, {Колпино, Садовая, 12А}, {Санкт-Петербург, Садовая, 12} — all
REAL rows from the seed table, all masked on the way in — and the agent
picks one and passes its fias_id (plain) and its postal code (derived) to
courier_book. Choosing between three substitutes that no longer resemble the
customer's words is the similarity-preservation question in its purest form.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("address_suggest", "courier_book", "delivery_create_order")
_FIAS = ("3f4e3d2c-1a1b-4c5d-8e9f-0a1b2c3d4e5f", "7a6b5c4d-3e2f-4a1b-9c8d-7e6f5a4b3c2d",
         "c1d2e3f4-5a6b-4c7d-8e9f-a0b1c2d3e4f5")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("compare", seed, 0, "chat").rng)
    return [_one(c.ctx_for("compare", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    cities = list(pools.CORPUS_CITIES)
    city = ctx.rng.choice(cities)
    other_city = ctx.rng.choice([one for one in cities if one != city])
    drawn = c.draw(ctx, city="", with_flat=False, with_type=False)
    identity = f"p{ctx.index}"
    target = drawn.address
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS,
        reachable=("address_suggest", "courier_book"),
        primary_identity=identity, cluster=f"LOC:{target.street} {target.house}",
        conversation_id=f"conv-cmp-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="три настоящих адреса из справочника, агент выбирает один; fias_id — plain")
    house = f"{target.house}{target.letter}"
    rows = (
        (city, target.street, house),
        (city, target.street, f"{target.house}а" if not target.letter else str(target.house)),
        (other_city, target.street, house),
    )
    for index, (row_city, street, row_house) in enumerate(rows):
        zone = pools.CITIES[row_city][1]
        postal = f"{zone}{ctx.rng.randrange(100, 999):03d}"[:6]
        value = f"{pools.CITIES[row_city][0]}, г {row_city.capitalize()}, ул {street.capitalize()}, д {row_house}"
        fields: dict[str, object] = {"value": value, "postal_code": postal,
                                     "region": pools.CITIES[row_city][0], "city": row_city,
                                     "street": street, "house": row_house, "flat": "",
                                     "fias_id": _FIAS[index]}
        # THE STREET IS REGISTERED SEPARATELY FROM THE DISPLAY STRING, because
        # the RESULT exposes it separately (`mock._apply` makes `data.street` a
        # Slot of its own) and an agent reads the structured field, not the
        # human one. Registering only `value` left `data.street` unmarked, so
        # the level-A fake never masked it and the scripted agent wrote the
        # customer's REAL street into the booking.
        builder.seed(f"a-{index}", "addresses", fields, {
            "street": ("LOC", f"{identity}.sugg{index}",
                       pools.Rendered(street, street, False, {"street": street})),
            "value": ("LOC", f"{identity}.sugg{index}",
                      pools.Rendered(value, value, False, {"city": row_city, "street": street, "house": row_house})),
        })
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("курьера на")
    first.value("a1", c.address(ctx, target))
    first.say("это в").say(city)
    first.say("на имя").value("n1", c.name(ctx, drawn.person, ("given",), "acc"))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"a1": ("LOC", identity + ".addr", "required", False),
                         "n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})
    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("сверьте по справочнику и оформляйте на завтра с десяти до четырёх",
                               "проверьте адрес в базе и вызывайте на завтра утром")))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {})
    return builder.build()
