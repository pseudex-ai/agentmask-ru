"""`send_template` — шаблон с плейсхолдерами, и подстановка в него персональных данных.

Именованная подстановка — не приём приложения, а штатная функция отправителей:
МТС Exolve описывает её прямо («можно обращаться к клиентам по имени»), Unisender
называет «подстановками», SMS Aero принимает готовый текст с ними
(research/2026-09-05-agent-scenario-coverage.md, §3). Агент выбирает шаблон и
заполняет ПЕРЕМЕННЫЕ — то есть кладёт ПД не в поле схемы и не в прозу, а в
третье место: в значение переменной, которое отправитель сам вставит в текст.

ЧТО ЭТА СЕМЬЯ СПРАШИВАЕТ, чего не спрашивает никакая другая:

  * `{{name}}` — НЕ значение и обязан дойти до отправителя нетронутым; подмена,
    попавшая в сам шаблон вместо переменной, рассылается всем сразу;
  * значение переменной — обычные ПД, и восстановление обязано вернуть их в той
    форме, в которой шаблон их ждёт (имя в именительном, телефон в E.164);
  * отрендеренный текст возвращается инструментом и снова проходит через шлюз —
    это тот же круг, что у `result_feed`, но по строке, которую собрал НЕ агент
    и НЕ клиент, а отправитель.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "send_template", "notify_sms", "callback_schedule")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("send_template", seed, 0, "chat").rng)
    return [_one(c.ctx_for("send_template", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    if ctx.index % 2 == 0:
        return _delivery_eta(ctx)
    return _callback(ctx)


def _delivery_eta(ctx: c.Ctx) -> Case:
    """Шаблон с именем И адресом: две переменные, два типа ПД."""
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS,
        reachable=("send_template",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-tpl-{ctx.index}" if ctx.index % 4 == 0 else "",
        note="шаблон delivery_eta: имя и адрес переменными, плейсхолдеры обязаны уцелеть")

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("пришлите смс о доставке по шаблону это")
    first.value("n1", c.name(ctx, drawn.person, ("given",)))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    first.say("адрес").value("a1", c.address(ctx, drawn.address))
    first.say("привезите")
    first.plain_value("t1", c.time_of_day(ctx), "time_of_day", "время — не ПД, обязано уцелеть")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False),
                         "a1": ("LOC", identity + ".home", "required", False)})
    return builder.build()


def _callback(ctx: c.Ctx) -> Case:
    """Шаблон, где ТЕЛЕФОН стоит и адресатом, и переменной внутри текста."""
    drawn = c.draw(ctx, with_flat=False)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="callcenter", tools=TOOLS,
        reachable=("send_template",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-tpl-{ctx.index}" if ctx.index % 4 == 1 else "",
        note="шаблон callback: один и тот же телефон адресатом и переменной")

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("подтвердите шаблоном что перезвоните меня зовут")
    first.value("n1", c.name(ctx, drawn.person, ("given",)))
    first.say("номер").value("ph1", c.phone(ctx, drawn.phone))
    first.say("перезвоните")
    first.plain_value("t1", c.time_of_day(ctx), "time_of_day", "время — не ПД, обязано уцелеть")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})
    return builder.build()
