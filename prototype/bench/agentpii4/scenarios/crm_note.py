"""`crm_note` — модель ПИШЕТ персональные данные своими словами в поле CRM.

Во всех девяти прежних семьях значение проходит через модель НЕТРОНУТЫМ: она
копирует его, разбирает по полям, переформатирует. Здесь она сочиняет фразу — и
единственные слова, которыми она располагает, это подмены. Так работает каждый
задокументированный колл-центр: Yandex AI Speech обещает «саммари с сохранением
результатов в CRM», МТС Exolve — «сотрудник получает причину обращения и историю
диалога», amoCRM принимает это как `params.text` заметки типа `call_in`
(research/2026-09-05-agent-scenario-coverage.md, §3).

ЧТО ЭТА СЕМЬЯ СПРАШИВАЕТ, чего не спрашивает никакая другая:

  * восстановление в СВОБОДНОМ тексте аргумента, а не в поле схемы: подмена
    стоит внутри фразы, в падеже, который выбрала модель, рядом со словами,
    которых не было ни в реплике клиента, ни в справочнике;
  * что попадает в CRM НАВСЕГДА: заметка переживёт диалог, и подмена, дошедшая
    до неё, останется в системе клиента как настоящее имя;
  * `entity_id` — plain: заметка обязана лечь в ту карточку, о которой речь.

Поле `text` объявлено `free`: сравнивать его дословно нельзя (модель вправе
написать что угодно), но каждая подмена внутри него — утечка, и её видит и
`residual`, и судья.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "crm_add_note", "crm_upsert_contact", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("crm_note", seed, 0, "chat").rng)
    return [_one(c.ctx_for("crm_note", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    if ctx.index % 2 == 0:
        return _call_summary(ctx)
    return _complaint(ctx)


def _call_summary(ctx: c.Ctx) -> Case:
    """Итог звонка в заметку: кто звонил, о чём и куда везти."""
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="callcenter", tools=TOOLS,
        reachable=("crm_find_contact", "crm_add_note"),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-note-{ctx.index}" if ctx.index % 4 == 0 else "",
        note="итог разговора своими словами в заметку карточки; ПД внутри свободного поля")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("это")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    first.say("запишите в карточку что я просил перенести доставку на")
    first.plain_value("t1", c.time_of_day(ctx), "time_of_day", "время — не ПД, обязано уцелеть")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say("и допишите что новый адрес")
    second.value("a1", c.address(ctx, pools.draw_address(ctx.rng, "", True, False, True)))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {"a1": ("LOC", identity + ".new", "required", False)})
    return builder.build()


def _complaint(ctx: c.Ctx) -> Case:
    """Жалоба на ДРУГОГО человека: в заметке двое, и подмены не должны слиться."""
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True)
    courier = c.draw(c.ctx_for("crm_note", ctx.seed, ctx.index * 100 + 1, ctx.register), foreign=True)
    identity = f"p{ctx.index}"
    other = f"p{ctx.index}.courier"
    builder = c.CaseBuilder(
        ctx=ctx, role="callcenter", tools=TOOLS,
        reachable=("crm_find_contact", "crm_add_note"),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-note-{ctx.index}" if ctx.index % 4 == 1 else "",
        note="в заметке двое: клиент и курьер; каждому своя подмена")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("это")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    first.say("курьер")
    first.value("n2", c.name(ctx, courier.person, ("surname", "given")))
    first.say("не позвонил перед приездом запишите это в мою карточку")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False),
                         "n2": ("NAME", other, "required", False)})
    return builder.build()
