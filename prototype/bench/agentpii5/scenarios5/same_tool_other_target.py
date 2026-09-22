"""`same_tool_other_target` — find(A), find(B): two people, one tool, one turn.

The smallest shape in which a gateway can contaminate one person with another.
Both calls go to the SAME tool with the SAME argument leaf, so nothing about the
schema tells the two apart: only the values do. A vault that minted one
substitute for two people, a cache keyed on content but not on the conversation,
a canonicalisation that folded «Иванова» and «Иванов» into one key — each of
those shows up here and nowhere in a single-identity family, because a single
identity cannot be confused with anybody.

WHY THE ANSWER DECLARES BOTH PEOPLE AND `must_not_contain` IS EMPTY. The obvious
check — «A's values must not appear in B's sentence» — is not checkable: the
reply is one text, and which sentence a value belongs to is exactly the judgement
the judge is calibrated for and the hop model is not. What IS mechanical is that
the reply owes BOTH identities their own value, so the case declares an
OUT/answer hop per identity and lets the comparator score each. `must_not_contain`
stays for the families where a value genuinely must not appear at all
(`fanout_pick`).

THREE VERTICALS, ONE PER INDEX MODULO THREE: crm (two cards by phone), bank (two
clients by ИНН — the type v4 carried zero of), government (two СНИЛС). All three
are READS whose result is a backend row, because an IN/tool hop must name an item
the backend holds (R05).
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, full_name, grouped_card,
                                               iso_date, minted, seeded, spaced_snils, told,
                                               tool_hop, user_hop)

BEHAVIOUR: str = "same_tool_other_target"
TOOLS: tuple[str, ...] = (
    "crm_find_contact", "crm_upsert_contact", "bank_client_find", "account_statement",
    "snils_verify", "notify_sms")
_CRM_TOOLS: tuple[str, ...] = ("crm_find_contact", "crm_upsert_contact", "notify_sms")
_BANK_TOOLS: tuple[str, ...] = ("bank_client_find", "account_statement", "notify_sms")
_GOV_TOOLS: tuple[str, ...] = ("snils_verify", "crm_upsert_contact", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    if ctx.index % 3 == 0:
        return _cards(ctx)
    if ctx.index % 3 == 1:
        return _clients(ctx)
    return _records(ctx)


def _second(ctx: c.Ctx, first: c.Drawn) -> c.Drawn:
    """The other person, drawn from a stream of their own.

    NOT FROM `ctx.rng`: taking a second person from the shared stream would shift
    every later draw of the case, so adding the axis would rebuild the corpus
    instead of extending it — the rule v4 wrote into `_add_negative` and the rare
    stratum, applied to the second identity.
    """
    # THE INDEX IS SHIFTED, not reused. v4's `draw` puts one of eight SHARED
    # people at every fifth index and a rare-stratum person at every seventh; two
    # streams asked at the SAME index answer with the same person, and two
    # identical identities make this family's question — «did they stay apart» —
    # unanswerable, because one substitute for both would be correct.
    step = 0
    while step < 20:
        other = c.ctx_for(f"{BEHAVIOUR}:other", ctx.seed, ctx.index * 100 + 7 + step,
                          ctx.register)
        drawn = c.draw(other, city=other.rng.choice(list(pools.CORPUS_CITIES)))
        # EVERY COLUMN BOTH CARDS DECLARE A HOP ON MUST DIFFER. A value the two
        # seeds share is ambiguous to the mock's by-value index and tagged on
        # neither, so a corpus collision would read as the gateway losing a hop.
        if (drawn.phone != first.phone
                and drawn.person.surname != first.person.surname
                and drawn.person.given != first.person.given
                and drawn.dob != first.dob
                and drawn.address.street != first.address.street
                and (drawn.email_local, drawn.email_domain)
                != (first.email_local, first.email_domain)):
            return drawn
        step += 1
    raise pools.BuildError(f"{ctx.index}: could not draw a second identity")


def _conversation(ctx: c.Ctx) -> str:
    return f"conv-pair-{ctx.index}" if ctx.index % 4 == 0 else ""


def _cards(ctx: c.Ctx) -> Case:
    """Two CRM cards by two phones: the commonest pair on a real line."""
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    first = c.draw(ctx, city=city)
    second = _second(ctx, first)
    one, two = f"p{ctx.index}a", f"p{ctx.index}b"
    builder = c.new_builder(ctx, "crm", _CRM_TOOLS, ("crm_find_contact",), one,
                            f"PHONE:{first.phone}",
                            "две карточки в одном ходе: один инструмент, две личности, "
                            "перекрёстного заражения быть не должно", ())
    builder.v4.conversation_id = _conversation(ctx)
    before = len(builder.v4.pii)
    c.contact_seed("c-1", first, city, ctx, builder, one)
    card_one = {item.where.path: item.id for item in minted(builder, before)}
    before = len(builder.v4.pii)
    c.contact_seed("c-2", second, city, ctx, builder, two)
    card_two = {item.where.path: item.id for item in minted(builder, before)}

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("найдите две карточки по телефонам")
    draft.value("ph1", c.phone(ctx, first.phone))
    draft.say("и")
    draft.value("ph2", c.phone(ctx, second.phone))
    draft.punct(".")
    turn, said = told(builder, draft, {"ph1": ("PHONE", one, "required", False),
                                       "ph2": ("PHONE", two, "required", False)})
    builder.v4.must_contain = (first.person.surname[0], second.person.surname[0])

    builder.declare_hop(user_hop(said["ph1"], 0, turn))
    builder.declare_hop(user_hop(said["ph2"], 1, turn))
    builder.declare_hop(arg_hop(said["ph1"], 2, turn, "crm_find_contact", 0, "query.phone", 0, ""))
    builder.declare_hop(tool_hop(card_one["last_name"], 3, turn, "crm_find_contact", 0,
                                 "contacts[].last_name"))
    builder.declare_hop(arg_hop(said["ph2"], 4, turn, "crm_find_contact", 1, "query.phone", 1, ""))
    builder.declare_hop(tool_hop(card_two["last_name"], 5, turn, "crm_find_contact", 1,
                                 "contacts[].last_name"))
    builder.declare_hop(answer_hop(card_one["last_name"], 6, turn, 3, False))
    builder.declare_hop(answer_hop(card_two["last_name"], 7, turn, 5, False))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list",
        (card_one["last_name"], card_one["first_name"], card_one["phone"],
         card_one["email"], card_one["birth_date"])))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 1, "list",
        (card_two["last_name"], card_two["first_name"], card_two["phone"],
         card_two["email"], card_two["birth_date"])))
    return builder.build(BEHAVIOUR)


def _bank_row(builder: c.CaseBuilderV5, record_id: str, drawn: c.Drawn,
              identity: str, rng_digits: tuple[str, str]) -> dict[str, str]:
    """One `bank_clients` row in the shape `mock._bank_row` reads: the name in
    ONE column (a bank CRM's shape, not the three-column CRM's) and the card in
    four groups (the screen's notation, which no caller's register produces)."""
    inn_digits, card_digits = rng_digits
    card = grouped_card(card_digits)
    person = full_name(drawn.person)
    return seeded(builder, record_id, "bank_clients", {
        "name": person, "inn": inn_digits, "card": card,
        "phone": f"+7{drawn.phone}", "status": "active"}, {
        "name": ("NAME", identity, pools.Rendered(person, person, False,
                                                  {"surname": drawn.person.surname[0],
                                                   "given": drawn.person.given[0],
                                                   "gender": drawn.person.gender})),
        "inn": ("INN", identity, pools.Rendered(inn_digits, inn_digits, False,
                                                {"digits": inn_digits})),
        "card": ("CARD", identity, pools.Rendered(card, card, False, {"digits": card_digits})),
    })


def _clients(ctx: c.Ctx) -> Case:
    """Two bank clients by two ИНН — the type the v4 corpus carried zero of."""
    first = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    second = _second(ctx, first)
    one, two = f"p{ctx.index}a", f"p{ctx.index}b"
    inn_one, inn_two = pools.inn12_digits(ctx.rng), pools.inn12_digits(ctx.rng)
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS, ("bank_client_find",), one,
                            f"NAME:{full_name(first.person)}",
                            "два клиента банка по двум ИНН в одном ходе; карты приходят "
                            "группами и не должны перепутаться", ())
    builder.v4.conversation_id = _conversation(ctx)
    row_one = _bank_row(builder, "bc-1", first, one, (inn_one, pools.card_digits(ctx.rng)))
    row_two = _bank_row(builder, "bc-2", second, two, (inn_two, pools.card_digits(ctx.rng)))

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("проверьте двух клиентов инн")
    draft.value("inn1", c.inn(ctx, inn_one))
    draft.say("и инн")
    draft.value("inn2", c.inn(ctx, inn_two))
    draft.say("скажите чьи это карты")
    draft.punct(".")
    turn, said = told(builder, draft, {"inn1": ("INN", one, "required", False),
                                       "inn2": ("INN", two, "required", False)})
    builder.v4.must_contain = (full_name(first.person), full_name(second.person))

    builder.declare_hop(user_hop(said["inn1"], 0, turn))
    builder.declare_hop(user_hop(said["inn2"], 1, turn))
    builder.declare_hop(arg_hop(said["inn1"], 2, turn, "bank_client_find", 0, "inn", 0, ""))
    builder.declare_hop(tool_hop(row_one["name"], 3, turn, "bank_client_find", 0, "client.name"))
    builder.declare_hop(tool_hop(row_one["card"], 4, turn, "bank_client_find", 0, "client.card"))
    builder.declare_hop(arg_hop(said["inn2"], 5, turn, "bank_client_find", 1, "inn", 1, ""))
    builder.declare_hop(tool_hop(row_two["name"], 6, turn, "bank_client_find", 1, "client.name"))
    builder.declare_hop(tool_hop(row_two["card"], 7, turn, "bank_client_find", 1, "client.card"))
    builder.declare_hop(answer_hop(row_one["name"], 8, turn, 3, False))
    builder.declare_hop(answer_hop(row_two["name"], 9, turn, 6, False))
    builder.declare_hop(answer_hop(row_one["card"], 10, turn, 4, True))
    builder.declare_hop(answer_hop(row_two["card"], 11, turn, 7, True))
    builder.expect_return(ReturnExpectation("bank_client_find", 0, "single",
                                            (row_one["name"], row_one["inn"], row_one["card"])))
    builder.expect_return(ReturnExpectation("bank_client_find", 1, "single",
                                            (row_two["name"], row_two["inn"], row_two["card"])))
    return builder.build(BEHAVIOUR)


def _snils_row(builder: c.CaseBuilderV5, record_id: str, drawn: c.Drawn,
               digits: str, identity: str) -> dict[str, str]:
    spaced = spaced_snils(digits)
    iso = iso_date(drawn.dob)
    return seeded(builder, record_id, "snils_records", {
        "snils": spaced, "last_name": drawn.person.surname[0],
        "first_name": drawn.person.given[0], "birth_date": iso, "status": "valid"}, {
        "snils": ("SNILS", identity, pools.Rendered(spaced, spaced, False, {"digits": digits})),
        "last_name": ("NAME", identity, pools.Rendered(
            drawn.person.surname[0], drawn.person.surname[0], False,
            {"surname": drawn.person.surname[0], "gender": drawn.person.gender})),
        "first_name": ("NAME", identity, pools.Rendered(
            drawn.person.given[0], drawn.person.given[0], False,
            {"given": drawn.person.given[0], "gender": drawn.person.gender})),
        "birth_date": ("DOB", identity, pools.Rendered(iso, iso, False, {"iso": iso})),
    })


def _records(ctx: c.Ctx) -> Case:
    """Two СНИЛС records: the separators and the ISO dates come back together
    and each has to land on its own person."""
    first = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    second = _second(ctx, first)
    one, two = f"p{ctx.index}a", f"p{ctx.index}b"
    digits_one, digits_two = pools.snils_digits(ctx.rng), pools.snils_digits(ctx.rng)
    builder = c.new_builder(ctx, "gov", _GOV_TOOLS, ("snils_verify",), one,
                            f"NAME:{full_name(first.person)}",
                            "два СНИЛС в одном ходе: две записи ПФР, две даты рождения "
                            "в ISO, ни одной перекрёстной", ())
    builder.v4.conversation_id = _conversation(ctx)
    row_one = _snils_row(builder, "sn-1", first, digits_one, one)
    row_two = _snils_row(builder, "sn-2", second, digits_two, two)

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("сверьте два снилса")
    draft.value("sn1", c.snils(ctx, digits_one))
    draft.say("и")
    draft.value("sn2", c.snils(ctx, digits_two))
    draft.punct(".")
    turn, said = told(builder, draft, {"sn1": ("SNILS", one, "required", False),
                                       "sn2": ("SNILS", two, "required", False)})
    builder.v4.must_contain = (first.person.surname[0], second.person.surname[0])

    builder.declare_hop(user_hop(said["sn1"], 0, turn))
    builder.declare_hop(user_hop(said["sn2"], 1, turn))
    builder.declare_hop(arg_hop(said["sn1"], 2, turn, "snils_verify", 0, "snils", 0, ""))
    builder.declare_hop(tool_hop(row_one["last_name"], 3, turn, "snils_verify", 0,
                                 "person.last_name"))
    builder.declare_hop(tool_hop(row_one["birth_date"], 4, turn, "snils_verify", 0,
                                 "person.birth_date"))
    builder.declare_hop(arg_hop(said["sn2"], 5, turn, "snils_verify", 1, "snils", 1, ""))
    builder.declare_hop(tool_hop(row_two["last_name"], 6, turn, "snils_verify", 1,
                                 "person.last_name"))
    builder.declare_hop(tool_hop(row_two["birth_date"], 7, turn, "snils_verify", 1,
                                 "person.birth_date"))
    builder.declare_hop(answer_hop(row_one["last_name"], 8, turn, 3, False))
    builder.declare_hop(answer_hop(row_two["last_name"], 9, turn, 6, False))
    builder.expect_return(ReturnExpectation(
        "snils_verify", 0, "single",
        (row_one["snils"], row_one["last_name"], row_one["first_name"], row_one["birth_date"])))
    builder.expect_return(ReturnExpectation(
        "snils_verify", 1, "single",
        (row_two["snils"], row_two["last_name"], row_two["first_name"], row_two["birth_date"])))
    return builder.build(BEHAVIOUR)
