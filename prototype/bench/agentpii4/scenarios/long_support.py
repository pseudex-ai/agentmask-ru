"""`long_support` — тикет, история, СВОДКА живому оператору: ПД уходят в ПРОЗЕ.

«не пришёл заказ это ерохина марина телефон …» → ticket_find(телефон) →
ticket_create(тема и текст СВОИМИ СЛОВАМИ) → crm_merge_contacts (клиент в базе
дважды) → escalate_to_human(сводка: кто клиент, что случилось, что сделано).

ЭТО ЕДИНСТВЕННАЯ СЕМЬЯ, ГДЕ ПЕРСОНАЛЬНЫЕ ДАННЫЕ ИДУТ К ЧЕЛОВЕКУ В ПРЕДЛОЖЕНИИ.
Везде ещё они лежат в типизированном поле, где восстановителю есть за что
зацепиться: имя поля, форма значения, соседние поля той же записи. В сводке нет
ничего — только фраза, которую написала модель словами, которые ей показали.
`crm_note` близко, но там текст остаётся в CRM; здесь его ЧИТАЕТ ОПЕРАТОР, и
восстановление обязано сработать до того, как он его увидит.

`crm_merge_contacts` — вторая поверхность 152-ФЗ, которой у нас не было:
склейка дублей. Клиент заведён в базе дважды, агент выбирает выжившую карточку,
и обе — настоящие люди с настоящими идентификаторами, которые обязаны дойти
дословно.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("ticket_find", "ticket_create", "escalate_to_human", "crm_find_contact",
         "crm_merge_contacts", "crm_upsert_contact", "crm_add_note", "notify_sms",
         "callback_schedule", "order_status")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("long_support", seed, 0, "chat").rng)
    return [_one(c.ctx_for("long_support", seed, index, registers[index])) for index in range(count)]


def _reachable(index: int) -> tuple[str, ...]:
    names = ["crm_find_contact", "ticket_find", "ticket_create", "escalate_to_human"]
    if index % 2 == 0:
        names.append("crm_merge_contacts")
    if index % 3 == 1:
        names.append("crm_add_note")
    if index % 4 == 2:
        names.append("callback_schedule")
    if index % 5 == 3:
        names.append("notify_sms")
    return tuple(names)


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="callcenter", tools=TOOLS, reachable=_reachable(ctx.index),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-support-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="обращение, история по телефону, склейка дублей, эскалация СО СВОДКОЙ — "
             "персональные данные в прозе, которую читает живой оператор")
    # THE SAME PERSON TWICE, which is what makes the merge a real question. The
    # second card holds the same phone: that is how a duplicate arises and how
    # the agent recognises one.
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    c.contact_seed("c-2", drawn, city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say(ctx.rng.choice(("не пришёл заказ", "заказ потерялся",
                                                 "у меня проблема с заказом")))
    first.say("это").value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say("адрес был").value("a1", c.address(ctx, drawn.address))
    builder.user(second, {"a1": ("LOC", identity + ".home", "required", False)})

    third = c.MessageDraft(ctx)
    third.say(ctx.rng.choice(("посмотрите были ли обращения раньше",
                              "я уже звонил проверьте историю",
                              "у вас должны быть мои обращения")))
    builder.user(third, {})

    fourth = c.MessageDraft(ctx)
    fourth.say(ctx.rng.choice(("и я у вас в базе дважды объедините карточки",
                               "кажется я заведён два раза склейте их",
                               "две карточки на меня уберите лишнюю")))
    builder.user(fourth, {})

    fifth = c.MessageDraft(ctx)
    fifth.say(ctx.rng.choice(("переключите на человека вы не решаете",
                              "позовите оператора живого",
                              "это не решается передайте специалисту")))
    builder.user(fifth, {})
    return builder.build()
