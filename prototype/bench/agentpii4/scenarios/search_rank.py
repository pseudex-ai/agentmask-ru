"""`search_rank` — справочник возвращает top-k с уверенностью, агент выбирает.

«курьера на пушкна сорок три» → address_suggest(query, count=5) возвращает пять
настоящих записей справочника, каждая со своей уверенностью, и агент берёт ту, в
которой уверенности больше → courier_book со street/house ВЫБРАННОЙ записи и её
fias_id.

ПОЧЕМУ ЭТО ОТДЕЛЬНАЯ СЕМЬЯ, А НЕ `compare`. `compare` даёт три записи и
спрашивает, ту ли выбрал агент. Здесь записей пять, они РАНЖИРОВАНЫ, и подмена
меняет две вещи сразу: какие записи вообще найдутся (поиск идёт по словам
запроса, а в запросе теперь наша улица) и в каком порядке. Агент, выбирающий по
уверенности, может выбрать ДРУГУЮ запись — не потому что ошибся, а потому что
ему показали другой список. Это прямой запрос владельца: «надо добавить кейс где
у агента есть инструмент find/search_adress который на input возвращает top k
адресов с confidense интересно как мы в этом случае сработаем».

ЗАПРОС НАМЕРЕННО НЕТОЧЕН. Клиент называет улицу с опечаткой или без родового
слова, поэтому уверенность у кандидатов РАЗНАЯ — на точном запросе все пятеро
совпали бы одинаково и выбирать было бы не из чего.

Пять записей строятся вокруг настоящего адреса клиента: он сам, тот же дом с
литерой, тот же дом в другом городе, соседний дом и однокоренная улица. Все
пятеро — настоящие записи справочника, все маскируются на входе.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("address_suggest", "courier_book", "delivery_create_order", "crm_find_contact",
         "notify_sms", "pickup_points_near")


def _fias(ctx: c.Ctx, index: int) -> str:
    """A UUID per row. `compare` holds three literals and cannot go past k=3;
    a generator can, and the value is `plain` — it must reach the tool byte for
    byte, so it is drawn from the case's own stream and never re-drawn."""
    stream = ctx.rng
    body = "".join(stream.choice("0123456789abcdef") for _ in range(32))
    return f"{body[:8]}-{body[8:12]}-4{body[13:16]}-8{body[17:20]}-{body[20:32]}"


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("search_rank", seed, 0, "chat").rng)
    return [_one(c.ctx_for("search_rank", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    cities = list(pools.CITIES)[:10]
    city = ctx.rng.choice(cities)
    other_city = ctx.rng.choice([one for one in cities if one != city])
    drawn = c.draw(ctx, city="", with_flat=False, with_type=False)
    target = drawn.address
    identity = f"p{ctx.index}"
    reachable = ("address_suggest", "courier_book") if ctx.index % 3 else \
                ("address_suggest", "courier_book", "notify_sms")
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=reachable,
        primary_identity=identity, cluster=f"LOC:{target.street} {target.house}",
        conversation_id=f"conv-rank-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="пять записей справочника с уверенностью; агент выбирает по ней и "
             "передаёт выбранную дальше — подмена меняет и список, и порядок")
    house = f"{target.house}{target.letter}"
    neighbour = str(target.house + 2)
    rows = (
        (city, target.street, house),
        (city, target.street, f"{target.house}а" if not target.letter else str(target.house)),
        (other_city, target.street, house),
        (city, target.street, neighbour),
        (city, f"{target.street}ский" if not target.street.endswith("ский") else target.street[:-4],
         neighbour),
    )
    for index, (row_city, street, row_house) in enumerate(rows):
        zone = pools.CITIES[row_city][1]
        postal = f"{zone}{ctx.rng.randrange(100, 999):03d}"[:6]
        value = f"{pools.CITIES[row_city][0]}, г {row_city.capitalize()}, ул {street.capitalize()}, д {row_house}"
        fields: dict[str, object] = {"value": value, "postal_code": postal,
                                     "region": pools.CITIES[row_city][0], "city": row_city,
                                     "street": street, "house": row_house, "flat": "",
                                     "fias_id": _fias(ctx, index)}
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
                      pools.Rendered(value, value, False,
                                     {"city": row_city, "street": street, "house": row_house})),
        })

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("курьера на")
    # THE QUERY IS DELIBERATELY IMPRECISE — a damaged name in the noisy
    # registers, no type word anywhere. On an exact query all five rows match
    # equally and the confidence the family exists to read is flat.
    first.value("a1", c.address(ctx, target))
    first.say("это в").say(city)
    first.say("на").value("n1", c.name(ctx, drawn.person, ("given",), "acc"))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"a1": ("LOC", identity + ".addr", "required", False),
                         "n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("найдите в справочнике самый похожий и по нему оформляйте",
                               "поищите адрес в базе выберите самый точный вариант",
                               "сверьтесь со справочником и берите вариант поувереннее")))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {})
    return builder.build()
