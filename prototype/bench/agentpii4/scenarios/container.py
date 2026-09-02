"""`container` — PII inside a URL or a CSV string argument.

«отправь смс со ссылкой на отслеживание заказа 4471823 в ссылке должен быть
мой телефон 89161234567» → notify_sms(text="…https://track…?order=4471823&
phone=79161234567") — the phone is embedded in a query string inside a free
text field, and the order number beside it is PLAIN and must survive.
«занеси обоих одной строкой» → crm_import_csv with two people in one CSV
string. `unmask_arguments` walks JSON leaves; what it does INSIDE a leaf that
is itself a container is what this family measures.
"""
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("notify_sms", "crm_import_csv", "crm_find_contact")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("container", seed, 0, "chat").rng)
    return [_one(c.ctx_for("container", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    if ctx.index % 2 == 0:
        return _url(ctx)
    return _csv(ctx)


def _url(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="callcenter", tools=TOOLS, reachable=("notify_sms",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-url-{ctx.index}" if ctx.index % 4 == 0 else "",
        note="телефон внутри URL в текстовом поле смс; номер заказа рядом — plain")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("отправьте мне смс со ссылкой на отслеживание заказа")
    first.plain_value("o1", c.order_number(ctx), "order_number", "номер заказа — не ПД, обязан уцелеть")
    first.say("в ссылке должен быть мой телефон")
    first.value("ph1", c.phone(ctx, drawn.phone))
    first.say("и слать на него же")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"ph1": ("PHONE", identity, "required", False)})
    return builder.build()


def _csv(ctx: c.Ctx) -> Case:
    first_person = c.draw(ctx)
    # The second person is drawn from the foreign pool: it can never coincide
    # with a shared cluster person, and a redraw loop against a fixed shared
    # slot would never terminate.
    second_person = c.draw(ctx, foreign=True)
    identity_a = f"p{ctx.index}a"
    identity_b = f"p{ctx.index}b"
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS, reachable=("crm_import_csv",),
        primary_identity=identity_a, cluster=f"PHONE:{first_person.phone}",
        conversation_id=f"conv-csv-{ctx.index}" if ctx.index % 4 == 1 else "",
        note="два контакта одной CSV-строкой; фамилия и имя по колонкам")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("занесите двоих в базу одной выгрузкой")
    first.value("n1", c.name(ctx, first_person.person, ("surname", "given")))
    first.say("телефон").value("ph1", c.phone(ctx, first_person.phone))
    first.say("и").value("n2", c.name(ctx, second_person.person, ("surname", "given")))
    first.say("телефон").value("ph2", c.phone(ctx, second_person.phone))
    first.say("дата рождения второго").value("d2", c.dob(ctx, second_person.dob))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity_a, "required", False),
                         "ph1": ("PHONE", identity_a, "required", False),
                         "n2": ("NAME", identity_b, "required", False),
                         "ph2": ("PHONE", identity_b, "required", False),
                         "d2": ("DOB", identity_b, "required", False)})
    return builder.build()
