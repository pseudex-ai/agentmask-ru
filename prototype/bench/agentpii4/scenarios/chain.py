"""`chain` — lookup by PII, a result carrying PII, decomposition, free text.

«здравствуйте это громова марина борисовна хочу поменять адрес доставки
телефон 8 916 402 11 87» → crm_find_contact(phone) → the seed row comes back
with the address on file → «теперь пушкина сорок один квартира семь» →
crm_upsert_contact(id, address{street, house, flat}) → «и смс пришлите что
адрес поменяли» → notify_sms(number, text).

Three things this provokes at once: a lookup by a substituted key (the
gateway must detokenise the query or the CRM finds nobody), PII arriving
INBOUND in a tool result, and an address decomposed into fields.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "crm_upsert_contact", "notify_sms", "callback_schedule")


def build(seed: int, count: int) -> list[Case]:
    cases: list[Case] = []
    registers = c.registers_for(count, c.ctx_for("chain", seed, 0, "chat").rng)
    for index in range(count):
        ctx = c.ctx_for("chain", seed, index, registers[index])
        cases.append(_one(ctx))
    return cases


def _one(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True)
    # THE CITY IS IN THE NEW ADDRESS, because `crm_upsert_contact` refuses an
    # address without one (`tools._upsert_parse`) and the customer never said
    # it: the agent had to lift the town out of a masked lookup result or
    # invent it, and two arms of one case invented differently. The same patch
    # `correction` already carries for `courier_book.locality`.
    new_address = pools.draw_address(ctx.rng, city, True, False, ctx.rng.random() < 0.3)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS,
        reachable=("crm_find_contact", "crm_upsert_contact", "notify_sms"),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-chain-{ctx.index}" if ctx.index % 2 == 0 else "",
        note="поиск по телефону, адрес из карточки, новый адрес по полям, смс")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)

    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("это")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given", "patronymic")))
    first.say("хочу поменять адрес доставки" if ctx.register != "clean"
              else "хочу поменять адрес доставки.")
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("теперь", "новый адрес", "записывайте")))
    second.value("a1", c.address(ctx, new_address))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {"a1": ("LOC", identity + ".new", "required", False)})

    third = c.MessageDraft(ctx)
    third.say(ctx.rng.choice(("и смс пришлите что адрес поменяли",
                              "и пришлите смс с подтверждением",
                              "и отправьте мне смс что всё записали")))
    if ctx.register == "clean":
        third.punct(".")
    builder.user(third, {})
    return builder.build()
