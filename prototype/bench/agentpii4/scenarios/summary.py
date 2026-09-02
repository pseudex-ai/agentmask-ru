"""`summary` — the final reply must carry real values, and never a substitute.

«Оформите доставку: Кузнецова Ольга Дмитриевна, +7 926 123-45-67, г. Самара,
ул. Полевая, д. 33, кв. 9. Потом повторите, что записали.» →
delivery_create_order → the reply is judged: does it carry the customer's own
data back to them (`must_contain`), and does it pass a substitute off as
their real datum. The six `clean` cases of the corpus live here and in
`decompose`; the register cap is a corpus-level rule.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("delivery_create_order", "notify_sms", "crm_find_contact")


def build(seed: int, count: int) -> list[Case]:
    rng = c.ctx_for("summary", seed, 0, "chat").rng
    registers = c.registers_for(count, rng)
    # Half of the corpus's clean allowance lives here.
    for index in range(min(3, count)):
        registers[index] = "clean"
    rng.shuffle(registers)
    return [_one(c.ctx_for("summary", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True, with_type=True)
    identity = f"p{ctx.index}"
    name = c.name(ctx, drawn.person, ("surname", "given", "patronymic"))
    phone = c.phone(ctx, drawn.phone)
    address = c.address(ctx, drawn.address)
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=("delivery_create_order",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-sum-{ctx.index}" if ctx.index % 2 == 0 else "",
        must_contain=(name.canonical, phone.canonical),
        note="ответ клиенту обязан повторить его же данные; подмена в ответе — дефект")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("оформите доставку" if ctx.register != "clean" else "Оформите доставку:")
    first.value("n1", name)
    first.punct(",").value("ph1", phone).punct(",")
    typed = {"n1": ("NAME", identity, "required", False),
             "ph1": ("PHONE", identity, "required", False),
             "a1": ("LOC", identity + ".addr", "required", False)}
    if ctx.index % 3 == 0:
        # THE PHONE SAID TWICE, and the second occurrence is its own item. This
        # is the corpus's positive proof that offsets were laid down, not
        # searched: `text.find(value)` returns the FIRST occurrence, and the
        # second item's start is not it. Callers repeat a number to be sure;
        # the corpus repeats it to be checkable.
        first.say("повторяю" if ctx.register != "clean" else "повторяю:")
        first.value("ph2", phone).punct(",")
        typed["ph2"] = ("PHONE", identity, "required", False)
    first.say("адрес" if ctx.register != "clean" else "")
    first.value("a1", address)
    first.punct(".")
    first.say("потом повторите что записали" if ctx.register != "clean" else "Потом повторите, что записали.")
    builder.user(first, typed)
    return builder.build()
