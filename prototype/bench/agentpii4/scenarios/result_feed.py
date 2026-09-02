"""`result_feed` — PII from a tool RESULT feeds a later call, and is derived from.

«запишите меня к терапевту я в базе тел 89261234567» → crm_find_contact →
the row carries birth_date 1987-03-14 and the name → clinic_book(patient{…,
birth_date ← result, age ← result, gender ← result name}, phone, speciality,
slot). The date the agent computes the age from was never said aloud: it
arrived from the customer's own system, masked on the way in.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "clinic_book", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("result_feed", seed, 0, "chat").rng)
    return [_one(c.ctx_for("result_feed", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city)
    identity = f"p{ctx.index}"
    speciality = ctx.rng.choice(("терапевту", "кардиологу", "неврологу", "стоматологу", "офтальмологу"))
    builder = c.CaseBuilder(
        ctx=ctx, role="clinic", tools=TOOLS,
        reachable=("crm_find_contact", "clinic_book"),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-feed-{ctx.index}" if ctx.index % 3 == 0 else "",
        note="дата рождения приходит из карточки; возраст и пол выводятся из результата")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say(f"запишите меня к {speciality} я у вас в базе")
    first.say("телефон" if ctx.rng.random() < 0.6 else "тел")
    first.value("ph1", c.phone(ctx, drawn.phone))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("на завтра на десять утра", "давайте в четверг к девяти",
                               "на пятницу после обеда")))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {})
    return builder.build()
