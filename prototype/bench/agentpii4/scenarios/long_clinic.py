"""`long_clinic` — запись, перенос и отмена: шесть ходов, десять инструментов.

«запишите к неврологу это соколова анна телефон … родилась двадцать первого
сентября восьмидесятого» → crm_find_contact → clinic_slots(невролог, дата) →
clinic_book(пациент из карточки, возраст и пол ВЫЧИСЛЕНЫ) → «а перенесите на
восьмое» → appointment_reschedule(id из ответа) → referral_create.

ЧТО ЗДЕСЬ ЕСТЬ, ЧЕГО НЕТ У `derive` И `result_feed`. `derive` спрашивает, что
агент вычислит из подменённой даты рождения; `result_feed` — дойдёт ли значение
из карточки до одного вызова. Здесь ОДИН пациент проходит через пять вызовов
подряд, и на четвёртом агент ссылается на запись по идентификатору, которого не
было ни в одном сообщении. Дата рождения при этом используется ДВАЖДЫ и
по-разному: как возраст (производная) и как поле направления (значение).

`clinic_slots` не несёт персональных данных вовсе, и это нужно: без такого шага
в разговоре нет места, где шлюз не при чём, а значит нет и способа увидеть, что
расхождение пришло именно от него.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "clinic_slots", "clinic_book", "appointment_reschedule",
         "appointment_cancel", "referral_create", "crm_upsert_contact", "notify_sms",
         "callback_schedule", "crm_add_note")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("long_clinic", seed, 0, "chat").rng)
    return [_one(c.ctx_for("long_clinic", seed, index, registers[index])) for index in range(count)]


def _reachable(index: int) -> tuple[str, ...]:
    names = ["crm_find_contact", "clinic_slots", "clinic_book"]
    names.append("appointment_cancel" if index % 3 == 2 else "appointment_reschedule")
    if index % 2 == 0:
        names.append("referral_create")
    if index % 4 == 1:
        names.append("notify_sms")
    if index % 5 == 0:
        names.append("crm_add_note")
    return tuple(names)


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="clinic", tools=TOOLS, reachable=_reachable(ctx.index),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-clinic-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="шесть ходов: карточка, свободные окна, запись, перенос или отмена "
             "по идентификатору из ответа, направление")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("запишите к неврологу это")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say("дата рождения").value("d1", c.dob(ctx, drawn.dob))
    builder.user(second, {"d1": ("DOB", identity, "required", False)})

    third = c.MessageDraft(ctx)
    third.say(ctx.rng.choice(("какие окна есть", "покажите свободное время",
                              "когда можно прийти")))
    builder.user(third, {})

    fourth = c.MessageDraft(ctx)
    fourth.say(ctx.rng.choice(("давайте на утро записывайте", "утреннее подойдёт записывайте",
                               "берём первое свободное")))
    builder.user(fourth, {})

    fifth = c.MessageDraft(ctx)
    if "appointment_cancel" in builder.reachable:
        fifth.say(ctx.rng.choice(("ой отмените запись не смогу", "нет отменяйте я не приду",
                                  "передумала отменяйте")))
    else:
        fifth.say(ctx.rng.choice(("а перенесите на восьмое", "лучше восьмого числа",
                                  "давайте перенесём на восьмое сентября")))
    builder.user(fifth, {})

    sixth = c.MessageDraft(ctx)
    sixth.say(ctx.rng.choice(("и направление выпишите", "нужно ещё направление",
                              "и подтверждение пришлите")))
    builder.user(sixth, {})
    return builder.build()
