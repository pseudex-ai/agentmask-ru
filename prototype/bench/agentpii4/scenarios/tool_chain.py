"""`tool_chain` — выход первого инструмента вход второго, второго — третьего.

Клиент называет ОДИН телефон и больше ничего:

  crm_find_contact(телефон)      -> карточка с ФИО и адресом
  address_suggest(адрес карточки) -> строка справочника с индексом и fias_id
  delivery_create_order(получатель из карточки, индекс и адрес из справочника)
                                  -> uuid заказа
  order_status(uuid)              -> заказ целиком, с ФИО и адресом СНОВА

ЧЕМ ЭТО ОТЛИЧАЕТСЯ ОТ `result_feed` И `long_order`. `result_feed` — один
переход: значение пришло из результата и ушло в вызов. `long_order` — семь
ходов, но почти всё называет клиент. Здесь переходов ТРИ, и на каждом одни и те
же персональные данные проходят через шлюз заново: наружу подменой, внутрь
подменой, наружу подменой. Ошибка на любом шаге не исправляется на следующем —
она в него ВХОДИТ.

И ОДНО ЗНАЧЕНИЕ ЦЕПИ НЕ ЕСТЬ НИГДЕ, КРОМЕ ОТВЕТА. Номера заказа нет ни в
сообщении, ни в карточке, ни в справочнике: его выдал write. Вызов, который на
него ссылается, нельзя запланировать, не прочитав ответ, — и это единственная
проверка того, что «результат вернулся агенту» работает вообще.

ЧТО ЭТА СЕМЬЯ НАШЛА СРАЗУ, и это надо читать вместе с её числом. Справочник
отдаёт адрес в СВОЁМ формате — «Удмуртская Республика, г Ижевск, ул Грибоедова,
д 66», — модель копирует эту строку в заказ дословно, а обратно приходит
«ижевск, грибоедова, 66»: город, улица и дом на месте, регион и родовые слова
потеряны. Потеря происходит НЕ при восстановлении, а при чеканке: подмена не
отзеркалила форму оригинала и модель увидела короткий адрес. Класс называется
`same_person_variant` — то же место, другая запись, — и это не утечка и не
чужое значение; но L3 у семьи низкий именно из-за него, и читать его как
поломку значит искать несуществующую.

Клиент почти молчит НАМЕРЕННО. Чем меньше он сказал, тем больше цепь тянет из
систем заказчика — а это и есть та нога, на которой персональные данные приходят
не от человека, а из CRM.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "address_suggest", "delivery_create_order", "order_status",
         "courier_book", "notify_sms", "crm_add_note", "pickup_points_near")
_FIAS_BODY = "0123456789abcdef"


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("tool_chain", seed, 0, "chat").rng)
    return [_one(c.ctx_for("tool_chain", seed, index, registers[index])) for index in range(count)]


def _fias(ctx: c.Ctx) -> str:
    body = "".join(ctx.rng.choice(_FIAS_BODY) for _ in range(32))
    return f"{body[:8]}-{body[8:12]}-4{body[13:16]}-8{body[17:20]}-{body[20:32]}"


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True)
    identity = f"p{ctx.index}"
    reachable = ["crm_find_contact", "address_suggest", "delivery_create_order", "order_status"]
    reachable.append("notify_sms" if ctx.index % 2 else "crm_add_note")
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=tuple(reachable),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-chain3-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="три перехода: карточка -> справочник -> заказ -> статус; номер "
             "заказа существует только в ответе инструмента")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)

    # ONE directory row, and it is the card's own address: the chain must carry
    # the value through, not choose between candidates — `search_rank` asks the
    # choosing question and asking both at once would tell us which one failed
    # only by luck.
    zone = pools.CITIES[city][1]
    postal = f"{zone}{ctx.rng.randrange(100, 999):03d}"[:6]
    street = drawn.address.street
    house = f"{drawn.address.house}{drawn.address.letter}"
    value = f"{pools.CITIES[city][0]}, г {city.capitalize()}, ул {street.capitalize()}, д {house}"
    builder.seed("a-0", "addresses", {
        "value": value, "postal_code": postal, "region": pools.CITIES[city][0],
        "city": city, "street": street, "house": house, "flat": "", "fias_id": _fias(ctx)}, {
        "street": ("LOC", f"{identity}.dir", pools.Rendered(street, street, False, {"street": street})),
        "value": ("LOC", f"{identity}.dir",
                  pools.Rendered(value, value, False, {"city": city, "street": street, "house": house})),
    })

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx))
    first.say(ctx.rng.choice(("повторите прошлую доставку по номеру",
                              "оформите как в прошлый раз телефон",
                              "всё как обычно телефон")))
    first.value("ph1", c.phone(ctx, drawn.phone))
    builder.user(first, {"ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("адрес и получателя возьмите из карточки сверьте по справочнику",
                               "данные все в базе сверьте адрес в справочнике и оформляйте",
                               "ничего не диктую всё есть в карточке проверьте адрес и оформите")))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {})

    third = c.MessageDraft(ctx)
    third.say(ctx.rng.choice(("и скажите потом какой статус у заказа",
                              "потом проверьте что заказ прошёл",
                              "и статус заказа посмотрите")))
    if ctx.register == "clean":
        third.punct(".")
    builder.user(third, {})
    return builder.build()
