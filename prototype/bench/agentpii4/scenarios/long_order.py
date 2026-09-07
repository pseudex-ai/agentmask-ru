"""`long_order` — оформление заказа целиком: семь ходов, двенадцать инструментов.

«это семёнов игорь телефон 8 916 402 11 87» → crm_find_contact → «везите на
пушкина сорок один квартира семь, коробка два килограмма» → delivery_quote →
«оформляйте» → delivery_create_order → «получать будет жена, зайцева ольга,
её телефон 8 903 …» → order_status(uuid из ответа) → order_reschedule →
notify_sms.

ЧЕГО НЕ СПРАШИВАЕТ НИ ОДНА ДРУГАЯ СЕМЬЯ. Все девять семей оси значений и пять
семей оси потока укладываются в один-три хода и один-два вызова. Здесь три
вещи сразу, и каждая из них ломается по-своему:

* ОДНА ЛИЧНОСТЬ ЧЕРЕЗ СЕМЬ ХОДОВ. Подмена, выданная на первом ходу, должна
  дожить до седьмого — и до этого никто не проверял, доживает ли.
* ВТОРОЙ ЧЕЛОВЕК ПОЯВЛЯЕТСЯ ПОЗДНО. Получатель называется на пятом ходу, когда
  заказ уже собран. Он не должен слиться с заказчиком в одну подмену, а
  заказчик — не должен перестать быть собой.
* НОМЕР ЗАКАЗА ЖИВЁТ ТОЛЬКО В ОТВЕТЕ ИНСТРУМЕНТА. Его нет ни в одном сообщении
  и ни в одной карточке: его выдал write, и вызов, который на него ссылается,
  можно построить только ПРОЧИТАВ ответ. Это единственная семья, где ось
  «результат инструмента — вход следующего» проходит через значение, которого
  в корпусе нет вовсе.

Инструменты предлагаются все двенадцать, достижимы — часть: агент, у которого
в наборе есть отмена и перенос, а нужен перенос, делает выбор, и выбор — это
то, чего скриптовый агент за 0$ не покрывает и живая модель покрывает.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "delivery_quote", "delivery_create_order", "pickup_points_near",
         "order_status", "order_reschedule", "order_cancel", "courier_book",
         "notify_sms", "callback_schedule", "crm_add_note", "crm_upsert_contact")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("long_order", seed, 0, "chat").rng)
    return [_one(c.ctx_for("long_order", seed, index, registers[index])) for index in range(count)]


def _reachable(index: int) -> tuple[str, ...]:
    """Every new tool in at least five cases, and never отмена вместе с переносом.

    `validate_corpus` refuses a registry tool reachable in fewer than five
    cases, so the rotation is a requirement rather than a flourish. Cancel and
    reschedule are mutually exclusive because a cancelled order cannot be
    moved — the mock says so (`ORDER_CANCELLED`), and a case whose two
    reachable tools contradict each other measures the agent's luck."""
    names = ["crm_find_contact", "delivery_quote", "delivery_create_order",
             "order_status", "notify_sms"]
    names.append(("order_reschedule", "order_cancel", "pickup_points_near")[index % 3])
    if index % 4 == 0:
        names.append("callback_schedule")
    if index % 4 == 1:
        names.append("crm_add_note")
    if index % 5 == 0:
        names.append("courier_book")
    return tuple(names)


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    buyer = c.draw(ctx, city=city, with_flat=True)
    # THE RECIPIENT IS DRAWN FROM `FOREIGN` FOR THE SAME REASON `container`
    # DOES IT: the shared-people pool recurs across the corpus by design, and
    # two shared people meeting inside one case would put two cases in one
    # cluster for a reason that is not the person.
    recipient = c.draw(ctx, city=city, with_flat=False, foreign=True)
    buyer_id = f"p{ctx.index}"
    recipient_id = f"p{ctx.index}r"
    reachable = _reachable(ctx.index)
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=reachable,
        primary_identity=buyer_id, cluster=f"PHONE:{buyer.phone}",
        conversation_id=f"conv-long-order-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="семь ходов: поиск, расчёт, оформление, поздний получатель, "
             "номер заказа из ответа инструмента, перенос или отмена, смс")
    c.contact_seed("c-1", buyer, city, ctx, builder, buyer_id)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("это")
    first.value("n1", c.name(ctx, buyer.person, ("surname", "given")))
    first.say("хочу отправить посылку телефон")
    first.value("ph1", c.phone(ctx, buyer.phone))
    builder.user(first, {"n1": ("NAME", buyer_id, "required", False),
                         "ph1": ("PHONE", buyer_id, "required", False)})

    kilos = ctx.rng.randrange(1, 6)
    second = c.MessageDraft(ctx)
    second.say("везите на")
    second.value("a1", c.address(ctx, buyer.address))
    second.say("коробка")
    second.plain_value("w1", pools.spell_cardinal(kilos) if ctx.spoken else str(kilos),
                       "weight", "вес посылки — не персональные данные, обязан дойти как назван")
    second.say("килограмма")
    builder.user(second, {"a1": ("LOC", buyer_id + ".home", "required", False)})

    third = c.MessageDraft(ctx)
    third.say(ctx.rng.choice(("сколько это будет стоить", "почём выйдет",
                              "посчитайте сколько это стоит")))
    builder.user(third, {})

    fourth = c.MessageDraft(ctx)
    fourth.say(ctx.rng.choice(("оформляйте", "хорошо оформляйте", "да давайте оформим")))
    builder.user(fourth, {})

    fifth = c.MessageDraft(ctx)
    fifth.say(ctx.rng.choice(("ой получать будет", "забыл сказать получать будет",
                              "получит не я а")))
    fifth.value("n2", c.name(ctx, recipient.person, ("surname", "given")))
    # THE PRONOUN AGREES WITH THE PERSON DRAWN, and the person is drawn from
    # `FOREIGN`, which holds both. «ким виктор … её телефон» is a sentence no
    # customer says, and a corpus that says it is teaching the detector a
    # gender signal that contradicts the name.
    fifth.say("его телефон" if recipient.person.gender == "m" else "её телефон")
    fifth.value("ph2", c.phone(ctx, recipient.phone))
    builder.user(fifth, {"n2": ("NAME", recipient_id, "required", False),
                         "ph2": ("PHONE", recipient_id, "required", False)})

    sixth = c.MessageDraft(ctx)
    if "order_cancel" in reachable:
        sixth.say(ctx.rng.choice(("а знаете отмените заказ", "нет отменяйте всё",
                                  "передумал отменяйте")))
    elif "pickup_points_near" in reachable:
        sixth.say(ctx.rng.choice(("а пункты выдачи рядом есть", "какие пвз рядом со мной",
                                  "посмотрите пункты выдачи поближе")))
    else:
        sixth.say(ctx.rng.choice(("и перенесите на десятое сентября",
                                  "давайте перенесём на десятое",
                                  "лучше десятого сентября")))
    builder.user(sixth, {})

    seventh = c.MessageDraft(ctx)
    # WHOSE NUMBER, SAID OUT LOUD. «смс пришлите на этот номер» after two
    # phones have been named is ambiguous, and the arms read it differently —
    # one texted the buyer, the other the recipient, and the comparator called
    # a correct restoration `other_person` three times on the 06.09 max run. A
    # case that asks the model to guess measures the guess.
    seventh.say(ctx.rng.choice(("и смс пришлите мне на мой номер",
                                "смс отправьте мне пожалуйста на мой телефон",
                                "и подтверждение смс мне на мой номер")))
    builder.user(seventh, {})
    return builder.build()
