"""`long_bank` — платёж, статус, чек и возврат: пять ходов, девять инструментов.

«оплатите с карты … на имя … телефон для чека …» → payment_create →
«прошёл платёж?» → payment_status(id из ответа) → «чек пришлите» →
receipt_fetch → «верните деньги» → payment_refund.

ЧЕТЫРЕ СТРОГИХ ФОРМАТА ПОДРЯД, и каждый следующий вызов ссылается на предыдущий.
`validate` спрашивает, откажется ли агент от подмены с неверной контрольной
суммой; `receipt` — обязателен ли контакт для продажи. Здесь другое: платёж уже
прошёл, и всё, что дальше, — ЧТЕНИЕ его обратно. Чек по 54-ФЗ несёт контакт
плательщика, поэтому персональные данные приходят ВНУТРЬ из платёжной системы,
а не от клиента, и приходят они уже канонизированными эквайрингом.

Возврат — единственное место в корпусе, где сумма денег обязана дойти дословно:
это `plain`, и ошибка в ней стоит ровно столько, сколько в ней написано.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("payment_create", "payment_status", "receipt_fetch", "payment_refund",
         "crm_find_contact", "crm_upsert_contact", "notify_sms", "crm_add_note",
         "callback_schedule")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("long_bank", seed, 0, "chat").rng)
    return [_one(c.ctx_for("long_bank", seed, index, registers[index])) for index in range(count)]


def _reachable(index: int) -> tuple[str, ...]:
    names = ["payment_create", "payment_status"]
    names.append("receipt_fetch" if index % 2 == 0 else "payment_refund")
    if index % 3 == 0:
        names.append("notify_sms")
    if index % 4 == 1:
        names.append("crm_add_note")
    if index % 5 == 2:
        # NOT `callback_schedule`: it derives the timezone from a LOC and this
        # family carries no address, which `validate` refuses — a derived field
        # whose source the case does not have measures the agent's invention.
        names.append("crm_find_contact")
    return tuple(names)


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=False)
    card = pools.card_digits(ctx.rng)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="bank", tools=TOOLS, reachable=_reachable(ctx.index),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-bank-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="платёж, затем чтение его обратно по идентификатору из ответа: "
             "статус, чек 54-ФЗ с контактом плательщика, возврат")

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("оплатите заказ картой")
    first.value("c1", c.card(ctx, card))
    builder.user(first, {"c1": ("CARD", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say("держатель").value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    second.say("телефон для чека").value("ph1", c.phone(ctx, drawn.phone))
    builder.user(second, {"n1": ("NAME", identity, "required", False),
                          "ph1": ("PHONE", identity, "required", False)})

    third = c.MessageDraft(ctx)
    third.say(ctx.rng.choice(("платёж прошёл", "проверьте прошло ли",
                              "скажите статус платежа")))
    builder.user(third, {})

    fourth = c.MessageDraft(ctx)
    if "receipt_fetch" in builder.reachable:
        fourth.say(ctx.rng.choice(("чек пришлите", "нужен фискальный чек",
                                   "и чек отправьте")))
    else:
        fourth.say(ctx.rng.choice(("верните деньги заказ отменяю", "оформите возврат",
                                   "деньги верните полностью")))
    builder.user(fourth, {})

    fifth = c.MessageDraft(ctx)
    fifth.say(ctx.rng.choice(("и запишите в карточку что обращался",
                              "отметьте у себя что я звонил",
                              "зафиксируйте обращение")))
    builder.user(fifth, {})
    return builder.build()
