"""`lookup_list` — поиск возвращает ЧУЖИЕ карточки, и одну из них надо выбрать.

Каждая существующая семья показывает модели данные ОДНОГО человека. Настоящий
оператор CRM живёт иначе: он ищет по фамилии, получает список однофамильцев или
дублей, и только потом решает, чья это карточка. Документация это описывает
прямо — `crm.duplicate.findbycomm` в Bitrix24 существует ровно для шага «сначала
проверь, нет ли уже такого», а поиск amoCRM по `?query=` возвращает всё, что
совпало (research/2026-09-05-agent-scenario-coverage.md, §3).

ЧТО ЭТА СЕМЬЯ СПРАШИВАЕТ, чего не спрашивает никакая другая:

  * несколько РАЗНЫХ людей приходят в одном результате инструмента — каждый
    обязан получить СВОЮ подмену, иначе модель выбирает между одинаковыми
    строками и всякий выбор одинаково случаен;
  * один и тот же человек в ДВУХ карточках (дубль) обязан получить ОДНУ
    подмену в обеих, иначе слияние дублей превращается в создание третьего;
  * различает карточки не имя, а телефон, дата рождения и `id` — и `id` обязан
    дойти до инструмента дословно, иначе обновится чужая запись.

Клиент НЕ называет телефон: назвал бы — искали бы по нему и список из одной
строки не появился бы. Он называет фамилию и один различающий признак, как это
и происходит на линии.
"""
from bench.agentpii4 import pools
from bench.agentpii4.scenarios import common as c
from bench.agentpii4.schema import Case

TOOLS = ("crm_find_contact", "crm_upsert_contact", "notify_sms", "callback_schedule")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for("lookup_list", seed, 0, "chat").rng)
    return [_one(c.ctx_for("lookup_list", seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    if ctx.index % 2 == 0:
        return _namesakes(ctx)
    return _duplicates(ctx)


def _namesakes(ctx: c.Ctx) -> Case:
    """Три разных человека с одной фамилией; различает дата рождения."""
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    target = c.draw(ctx, city=city, with_flat=True)
    # THE NAMESAKES MUST DIFFER FROM THE TARGET AND FROM EACH OTHER. Two cards
    # holding the same full name are one value to the vault and get ONE
    # substitute — correct behaviour, but it would make this family measure the
    # duplicate shape below instead of the choice it exists for.
    others: list[c.Drawn] = []
    step = 1
    while len(others) < 2:
        candidate = c.draw(c.ctx_for("lookup_list", ctx.seed, ctx.index * 100 + step, ctx.register), city=city)
        taken = {target.person.given[0], *(one.person.given[0] for one in others)}
        if candidate.person.given[0] not in taken:
            others.append(candidate)
        step += 1
    identity = f"p{ctx.index}"
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS,
        reachable=("crm_find_contact", "crm_upsert_contact"),
        primary_identity=identity, cluster=f"NAME:{c.full_name_canonical(target.person)}",
        conversation_id=f"conv-list-{ctx.index}" if ctx.index % 4 == 0 else "",
        must_not_contain=tuple(other.person.given[0] for other in others),
        note="поиск по фамилии возвращает трёх однофамильцев; выбирают по дате рождения")

    # THE SURNAME IS SHARED, everything else is not: that is what makes the
    # three cards a real choice rather than three copies. THE TARGET IS NOT
    # ALWAYS FIRST — a card chosen by position would pass this family without
    # reading anything, which is the one thing it must not allow.
    surname = target.person.surname
    place = ctx.index % 3
    slot = 0
    for other in others:
        if slot == place:
            slot += 1
        c.contact_seed(f"c-{slot + 1}", _with_surname(other, surname), city, ctx, builder,
                       f"{identity}.other{slot + 1}")
        slot += 1
    c.contact_seed(f"c-{place + 1}", target, city, ctx, builder, identity)

    # THE SURNAME IS SAID IN THE NOMINATIVE, and that is not a convenience.
    # «найдите карточку букина» is genitive-after-a-noun, which for an -ов/-ин
    # surname is spelled exactly like the feminine nominative («Букина»); the
    # engine refuses to convert without evidence of a case, and rightly — the
    # conversion breaks real women. This family exists to measure the CHOICE
    # between cards, so it must not hinge on that ambiguity. The ambiguity
    # itself is recorded in docs/known-issues.md and belongs to a corpus we did
    # not write, not to one we author around it.
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("найдите карточку фамилия")
    first.value("n1", c.name(ctx, target.person, ("surname",)))
    first.say("у неё день рождения" if target.person.gender == "f" else "у него день рождения")
    first.value("d1", c.dob(ctx, target.dob))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "d1": ("DOB", identity, "required", False)})

    second = c.MessageDraft(ctx)
    second.say(ctx.rng.choice(("запишите новый адрес", "поменяйте адрес доставки", "адрес теперь")))
    # The city is named for the same reason `chain` and `correction` name it:
    # `crm_upsert_contact` requires it with an address, and this family never
    # mentions a town anywhere else in the dialogue.
    second.value("a1", c.address(ctx, pools.draw_address(ctx.rng, city, True, False, True)))
    if ctx.register == "clean":
        second.punct(".")
    builder.user(second, {"a1": ("LOC", identity + ".new", "required", False)})
    return builder.build()


def _duplicates(ctx: c.Ctx) -> Case:
    """ОДИН человек в двух карточках: разные телефоны, одно ФИО."""
    city = ctx.rng.choice(list(pools.CITIES)[:10])
    drawn = c.draw(ctx, city=city, with_flat=True)
    # The same person, entered twice with different contact details — the shape
    # `crm.duplicate.findbycomm` exists for. One identity, so the benchmark
    # demands ONE substitute across both cards.
    twin = c.Drawn(person=drawn.person, phone=pools.mobile_digits(ctx.rng),
                   address=drawn.address, dob=drawn.dob,
                   email_local=drawn.email_local + "2", email_domain=drawn.email_domain)
    identity = f"p{ctx.index}"
    # THE CITY IS SAID, because `crm_upsert_contact` requires it whenever an
    # address is written (`tools._upsert_parse`), and an address the customer
    # dictates without one leaves the agent to lift it out of a masked lookup
    # result or invent it — two arms invent differently. The same patch
    # `correction` already carries.
    new_address = pools.draw_address(ctx.rng, city, True, False, True)
    builder = c.CaseBuilder(
        ctx=ctx, role="crm", tools=TOOLS,
        reachable=("crm_find_contact", "crm_upsert_contact"),
        primary_identity=identity, cluster=f"NAME:{c.full_name_canonical(drawn.person)}",
        conversation_id=f"conv-dup-{ctx.index}" if ctx.index % 4 == 1 else "",
        note="один человек двумя карточками; одна подмена на обе, id различает")
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    c.contact_seed("c-2", twin, city, ctx, builder, identity)

    # NOMINATIVE AFTER «это», never after a preposition. «посмотрите на
    # тарасова алла» is ungrammatical: «на» governs the accusative, the engine
    # reads the name in that case — correctly — and a woman is minted as a man.
    # A generator that writes broken Russian measures its own mistake.
    # THE TARGET CARD IS NAMED, AND THAT IS NOT A KINDNESS TO THE AGENT. The
    # utterance used to be «кажется я в базе дважды оставьте актуальным
    # телефон N», which admits three readings — update the first card's phone
    # to N, update the card that already has N, or merge — and there is no
    # merge tool. The mock merges into the EXISTING record, so the two
    # readings store a different `email`, and two arms that read the sentence
    # differently diverge on a coin the case itself tossed. The family's
    # question is «does ONE person in TWO cards get ONE substitute», not «which
    # card do you pick»; naming the card keeps the question and drops the coin.
    first = c.MessageDraft(ctx)
    first.say(c.opener(ctx)).say("это")
    first.value("n1", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("кажется я в базе дважды обновите ту карточку где телефон")
    first.value("ph1", c.phone(ctx, twin.phone))
    first.say("новый адрес")
    first.value("a1", c.address(ctx, new_address))
    if ctx.register == "clean":
        first.punct(".")
    builder.user(first, {"n1": ("NAME", identity, "required", False),
                         "ph1": ("PHONE", identity, "required", False),
                         "a1": ("LOC", identity + ".new", "required", False)})
    return builder.build()


def _with_surname(drawn: c.Drawn, surname: tuple[str, str, str]) -> c.Drawn:
    """The same person under another surname — a namesake, not a copy."""
    person = pools.Person(surname=surname, given=drawn.person.given,
                          patronymic=drawn.person.patronymic,
                          short_patronymic=drawn.person.short_patronymic,
                          gender=drawn.person.gender)
    return c.Drawn(person=person, phone=drawn.phone, address=drawn.address, dob=drawn.dob,
                   email_local=drawn.email_local, email_domain=drawn.email_domain)
