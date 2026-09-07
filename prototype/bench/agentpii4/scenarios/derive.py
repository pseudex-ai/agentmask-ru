"""`derive` — age, gender, initials, transliteration, postcode, timezone.

«запишите к кардиологу павлову тамару владимировну она четырнадцатого марта
восемьдесят седьмого года рождения телефон восемь девятьсот шестнадцать…» →
clinic_book(patient{…, birth_date: "1987-03-14", age: 39, gender: "F"}) with
`now` fixed by the system prompt. The agent COMPUTES age and gender from what
it read; if it read a substitute, the derived value belongs to nobody, and no
restoration reaches it. This family is where the `derived` class is counted.
Four sub-shapes rotate: clinic (age, gender), CRM (initials, translit),
delivery (postcode), callback (timezone).
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("clinic_book", "crm_upsert_contact", "delivery_create_order", "callback_schedule",
         "payment_create")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("derive", seed, 0, "chat").rng)
    return [_one(c.ctx_for("derive", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    shape = ctx.index % 4
    if shape == 0:
        return _clinic(ctx)
    if shape == 1:
        return _crm(ctx)
    if shape == 2:
        return _delivery(ctx)
    return _callback(ctx)


def _clinic(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx)
    identity = f"p{ctx.index}"
    speciality = ctx.rng.choice(("кардиологу", "терапевту", "неврологу", "офтальмологу"))
    builder = c.CaseBuilder(
        ctx=ctx, role="clinic", tools=TOOLS, reachable=("clinic_book",),
        primary_identity=identity, cluster=f"DOB:{drawn.dob}",
        conversation_id=f"conv-der-{ctx.index}" if ctx.index % 2 else "",
        note="возраст из даты рождения и пол из имени — производные, из подмены невосстановимы")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say(f"запишите к {speciality}")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given", "patronymic"), "acc"))
    first.say(ctx.rng.choice(("дата рождения", "родилась" if drawn.person.gender == "f" else "родился", "он" if drawn.person.gender == "m" else "она")))
    first.value("d1", c.dob(ctx, drawn.dob))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    first.say(ctx.rng.choice(("на завтра на десять утра", "на пятницу к девяти", "в среду после трёх")))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "d1": ("DOB", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False)})
    return builder.build()


def _crm(ctx: c.Ctx) -> Case:
    drawn = c.draw(ctx)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS, reachable=("crm_upsert_contact",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-der-{ctx.index}" if ctx.index % 2 else "",
        note="инициалы и латинское имя — производные от ФИО")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("заведите карточку")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given", "patronymic")))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    typed = {"n1": ("NAME", identity, "required", False),
             "ph1": ("PHONE", identity, "required", False)}
    if not ctx.speech:
        # An e-mail carries a dot and digits; the speech registers forbid both
        # and a spelled-out mailbox is the `spoken_id` family's business.
        first.say("почта").value("e1", c.email(ctx, drawn.email_local, drawn.email_domain))
        typed["e1"] = ("EMAIL", identity, "required", False)
    first.say("инициалы и латиницей заполните сами")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, typed)
    return builder.build()


def _delivery(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=True, with_type=True)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="delivery", tools=TOOLS, reachable=("delivery_create_order",),
        primary_identity=identity, cluster=f"LOC:{city} {drawn.address.street}",
        conversation_id=f"conv-der-{ctx.index}" if ctx.index % 2 else "",
        note="индекс — производная от города; подмена города даёт чужой индекс")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("оформите доставку на")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given"), "acc"))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    first.say("адрес").value("a1", c.address(ctx, drawn.address))
    first.say("посылка два килограмма индекс подберите сами")
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False),
                         "a1": ("LOC", identity + ".addr", "required", False)})
    return builder.build()


def _callback(ctx: c.Ctx) -> Case:
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city, with_flat=False, with_type=True)
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="callcenter", tools=TOOLS, reachable=("callback_schedule",),
        primary_identity=identity, cluster=f"PHONE:{drawn.phone}",
        conversation_id=f"conv-der-{ctx.index}" if ctx.index % 2 else "",
        note="часовой пояс — производная от города клиента")
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("перезвоните мне завтра")
    first.say(c.time_of_day(ctx)).say("по моему времени я в")
    first.value("a1", c.address(ctx, drawn.address))
    first.say("телефон").value("ph1", c.phone(ctx, drawn.phone))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"a1": ("LOC", identity + ".addr", "required", False),
                         "ph1": ("PHONE", identity, "required", False)})
    return builder.build()
