"""`single` — one read, four hops: the base loop §8.2 calls «одиночный вызов».

WHY THIS FAMILY IS AUTHORED AT ALL (ruling R-50). §8.2 describes the single call
as «базовый, 4 перехода»: the customer says a value, the agent looks it up, the
result comes back carrying the customer's own data, and the answer uses it. The
revised v4 corpus supplies the family's COUNT — 463 cases — but only 84 of them
carry that loop; the other 379 are v4's two-hop shape (say a value, write it into
a call, stop), because v4 seeded no record for them to read back. A family whose
denominator is four fifths a different shape cannot answer «what does the gateway
cost on the simplest loop there is», which is the one question every other family
is a complication of. So the loop is written here, a hundred times, and
`build.py --check` prints authored / revised / two-hop apart so the share is read
for what it is.

EIGHT VERTICALS AND FOUR RETURN FORMS, BY INDEX. crm (a card, `list`), bank (a
client, `single`), government (a vehicle, `single`), support (an open ticket,
`list`), calendar (free windows, `list`), directory (an address normalised,
`canon`), search (a knowledge-base note, `chunks`) and clinic (a patient card,
`single`). The verticals are not decoration: the four forms are four different
shapes of result — a row, an object, one normalised line, ranked prose — and a
family that measured one of them would report a property of that shape and call
it the base loop.

WHY THE EIGHTH ARRIVED LATE, AND WHY HERE. The clinic had five tools and all
five WRITE: every value in their results is one the dialogue handed them a
moment earlier, so the vertical declared 584 hops and not one IN/tool — «ДР ISO,
СНИЛС с разделителями», the return notation ТЗ §2 names as the clinic's whole
reason for being in the table, was the one format no run could check, and every
form slice by that vertical printed «н/п». `patient_find` is the reading tool,
and the base loop is where it belongs: nothing else is going on in the case, so
what the slice reports is the vertical's own notation and not another family's
complication. The count of the family does NOT move — 100 cases over eight
shapes instead of seven, twelve or thirteen each, above `MIN_TYPE_DENOMINATOR`
for every one of them — because §8.2's normative number is the size of a family
and a corpus grown to carry one vertical would have moved eleven other shares to
say one thing.

WHAT IS DELIBERATELY ABSENT. No second call, no chain, no memory, no branch: a
`single` case that needed a second tool would be another family's case wearing
this family's name, and the whole point of the base loop is that nothing else is
going on in it. Each case therefore declares exactly one `ReturnExpectation`, and
`test_generator_a` refuses the family if a case declares two.

EVERY CASE IS PROVEN AT BUILD (F4.1). `mock.render_problems` seeds the real
backend, makes the declared call with the case's own argument values and refuses
a case whose result does not carry every declared item — so a loop this family
claims is a loop the instrument can observe.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii5.contracts import CaseV5, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.common import (answer_hop, arg_hop, bank_client_seed, full_name,
                                               iso_date, minted, patient_seed, seeded,
                                               spaced_snils, stored_name, stored_phone, told,
                                               tool_hop, user_hop, vehicle_seed)

BEHAVIOUR: str = "single"
TOOLS: tuple[str, ...] = (
    "crm_find_contact", "crm_add_note", "notify_sms", "bank_client_find", "account_statement",
    "vehicle_check", "ticket_create", "ticket_find", "escalate_to_human", "calendar_free",
    "callback_schedule", "address_suggest", "delivery_create_order", "kb_search",
    "patient_find", "clinic_slots", "clinic_book")
# Each shape offers the tool it reads plus two the vertical really has: a case
# that offers ONE tool tells the agent what to call by elimination, and «did the
# agent pick the right tool» is part of what an arm can get wrong.
_CRM_TOOLS: tuple[str, ...] = ("crm_find_contact", "crm_add_note", "notify_sms")
_BANK_TOOLS: tuple[str, ...] = ("bank_client_find", "account_statement", "notify_sms")
_GOV_TOOLS: tuple[str, ...] = ("vehicle_check", "ticket_create", "notify_sms")
_SUPPORT_TOOLS: tuple[str, ...] = ("ticket_find", "escalate_to_human", "notify_sms")
_CALENDAR_TOOLS: tuple[str, ...] = ("calendar_free", "callback_schedule", "notify_sms")
_DIRECTORY_TOOLS: tuple[str, ...] = ("address_suggest", "delivery_create_order", "notify_sms")
_SEARCH_TOOLS: tuple[str, ...] = ("kb_search", "crm_find_contact", "crm_add_note")
# The clinic's reader plus the two the vertical really offers beside it. A
# booking tool in the set is what makes «which tool» a question the arm can get
# wrong: the caller asks to be IDENTIFIED, not booked, and `clinic_book` is the
# wrong answer that is available.
_CLINIC_TOOLS: tuple[str, ...] = ("patient_find", "clinic_slots", "clinic_book")

# The ledger lines an `account_statement` would filter. Not personal data and no
# item is declared on them; they are here because `bank_client_seed` writes the
# column and a client with no ledger is a client the bank vertical does not have.
_STATEMENT_ROWS: tuple[dict[str, str], ...] = (
    {"date": "2026-08-03", "amount": "1500.00", "currency": "RUB",
     "description": "Оплата заказа"},
    {"date": "2026-08-11", "amount": "420.00", "currency": "RUB", "description": "Доставка"})
# The business topic a knowledge-base note is filed under. A topic, never a
# value: the mock ranks by word overlap, and ranking on a VALUE would make the
# retrieval and the thing being measured the same string.
_TOPICS: tuple[str, ...] = ("возврат", "доставка", "рассрочка", "гарантия", "перевыпуск")
# One note about the customer, in the customer's own support system. `{slot}`
# names a column of the same row — lower-case letters and underscores only, or
# `mock._template_pieces` does not see a slot at all.
_NOTE: str = "Заметка по теме {topic}: клиент {who} оставил телефон {tel}."
# The hexadecimal alphabet of a ФИАС id. The directory answers with one and the
# mock reads the suggestion's row back by it, so it has to be unique per row and
# shaped like the real thing.
_FIAS_BODY: str = "0123456789abcdef"


def build(seed: int, count: int) -> list[CaseV5]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> CaseV5:
    """Eight verticals by index modulo eight, so the mix is a property of the
    plan rather than of a draw — at a hundred cases every shape gets twelve or
    thirteen, above `MIN_TYPE_DENOMINATOR` for the four return forms."""
    builders = (_crm_card, _bank_client, _vehicle, _ticket, _calendar, _directory, _note,
                _patient_card)
    return builders[ctx.index % len(builders)](ctx)


def _conversation(ctx: c.Ctx) -> str:
    """An explicit conversation id on every fifth case, derived on the rest —
    the rule both halves of the corpus apply, so K09's share is one rule's."""
    return f"conv-single-{ctx.index}" if ctx.index % 5 == 0 else ""


def _fias(ctx: c.Ctx) -> str:
    body = "".join(ctx.rng.choice(_FIAS_BODY) for _ in range(32))
    return f"{body[:8]}-{body[8:12]}-4{body[13:16]}-8{body[17:20]}-{body[20:32]}"


def _crm_card(ctx: c.Ctx) -> CaseV5:
    """«поднимите мою карточку по номеру» — amoCRM answers with the row."""
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "crm", _CRM_TOOLS, ("crm_find_contact",), identity,
                            f"PHONE:{drawn.phone}",
                            "базовая петля: телефон -> карточка -> ответ; ничего кроме "
                            "одного чтения в случае не происходит", ())
    builder.v4.conversation_id = _conversation(ctx)
    before = len(builder.v4.pii)
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    card = {item.where.path: item.id for item in minted(builder, before)}

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("мой номер")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("поднимите карточку и скажите на кого она оформлена")
    draft.punct(".")
    turn, said = told(builder, draft, {"ph": ("PHONE", identity, "required", False)})
    builder.v4.must_contain = (drawn.person.surname[0],)

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(arg_hop(said["ph"], 1, turn, "crm_find_contact", 0,
                                "query.phone", 0, ""))
    builder.declare_hop(tool_hop(card["last_name"], 2, turn, "crm_find_contact", 0,
                                 "contacts[].last_name"))
    builder.declare_hop(tool_hop(card["birth_date"], 3, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    builder.declare_hop(answer_hop(card["last_name"], 4, turn, 2, False))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list",
        (card["last_name"], card["first_name"], card["phone"], card["birth_date"],
         card["address.street"])))
    return builder.build(BEHAVIOUR)


def _bank_client(ctx: c.Ctx) -> CaseV5:
    """«клиент по ИНН» — the card comes back in the bank's four-group notation,
    which no caller's register produces."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    inn_digits = pools.inn12_digits(ctx.rng)
    card_digits = pools.card_digits(ctx.rng)
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS, ("bank_client_find",), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "базовая петля в банке: ИНН -> клиент -> ответ; карта "
                            "возвращается группами по четыре", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = bank_client_seed("bc-1", inn_digits, card_digits, drawn, builder, identity,
                           _STATEMENT_ROWS)

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("проверьте клиента инн")
    draft.value("inn", c.inn(ctx, inn_digits))
    draft.say("скажите на кого он оформлен")
    draft.punct(".")
    turn, said = told(builder, draft, {"inn": ("INN", identity, "required", False)})
    builder.v4.must_contain = (full_name(drawn.person),)

    builder.declare_hop(user_hop(said["inn"], 0, turn))
    builder.declare_hop(arg_hop(said["inn"], 1, turn, "bank_client_find", 0, "inn", 0, ""))
    builder.declare_hop(tool_hop(row["name"], 2, turn, "bank_client_find", 0, "client.name"))
    builder.declare_hop(tool_hop(row["card"], 3, turn, "bank_client_find", 0, "client.card"))
    builder.declare_hop(answer_hop(row["name"], 4, turn, 2, False))
    builder.expect_return(ReturnExpectation("bank_client_find", 0, "single",
                                            (row["name"], row["inn"], row["card"])))
    return builder.build(BEHAVIOUR)


def _vehicle(ctx: c.Ctx) -> CaseV5:
    """«пробейте номер» — the ГИБДД register answers with the plate in its
    canonical spelling and the owner behind it."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    plate_text = c.plate_text(ctx.rng)
    builder = c.new_builder(ctx, "gov", _GOV_TOOLS, ("vehicle_check",), identity,
                            f"PLATE:{plate_text}",
                            "базовая петля в госреестре: номер -> владелец -> ответ", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = vehicle_seed("veh-1", plate_text, drawn, builder, identity)

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("пробейте номер")
    draft.value("plate", c.plate(ctx, plate_text))
    draft.say("скажите на кого машина")
    draft.punct(".")
    turn, said = told(builder, draft, {"plate": ("PLATE", identity, "required", False)})
    builder.v4.must_contain = (drawn.person.surname[0],)

    builder.declare_hop(user_hop(said["plate"], 0, turn))
    builder.declare_hop(arg_hop(said["plate"], 1, turn, "vehicle_check", 0, "plate", 0, ""))
    builder.declare_hop(tool_hop(row["owner.last_name"], 2, turn, "vehicle_check", 0,
                                 "owner.last_name"))
    builder.declare_hop(tool_hop(row["plate"], 3, turn, "vehicle_check", 0, "plate"))
    builder.declare_hop(answer_hop(row["owner.last_name"], 4, turn, 2, False))
    builder.expect_return(ReturnExpectation(
        "vehicle_check", 0, "single",
        (row["plate"], row["owner.last_name"], row["owner.first_name"])))
    return builder.build(BEHAVIOUR)


def _ticket(ctx: c.Ctx) -> CaseV5:
    """«есть ли по мне открытая заявка» — Okdesk answers with the issue and the
    number it is registered on.

    THE CALLER'S CRM CARD IS NOT SEEDED HERE, and the omission is the mock's
    by-value index rather than laziness: `ticket_find` reads the requester's
    phone off the TICKET row, and a contacts row holding the same number would
    make the tag ambiguous — the mock drops it from both and the one IN hop of
    the case becomes a crossing no gateway could be credited with.
    """
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    phone = f"+7{drawn.phone}"
    builder = c.new_builder(ctx, "callcenter", _SUPPORT_TOOLS, ("ticket_find",), identity,
                            f"PHONE:{drawn.phone}",
                            "базовая петля в поддержке: телефон -> заявка -> ответ; "
                            "номер возвращается в нотации тикет-системы", ())
    builder.v4.conversation_id = _conversation(ctx)
    ticket = seeded(builder, "t-1", "tickets", {"phone": phone, "subject": "Перенос доставки"}, {
        "phone": ("PHONE", identity, pools.Rendered(phone, phone, False,
                                                    {"digits": drawn.phone}))})

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("посмотрите есть ли по мне открытая заявка и на какой номер она оформлена")
    draft.punct(".")
    turn, said = told(builder, draft, {"ph": ("PHONE", identity, "required", False)})
    builder.v4.must_contain = (phone,)

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(arg_hop(said["ph"], 1, turn, "ticket_find", 0, "phone", 0, ""))
    builder.declare_hop(tool_hop(ticket["phone"], 2, turn, "ticket_find", 0,
                                 "issues[].requester.phone"))
    builder.declare_hop(answer_hop(ticket["phone"], 3, turn, 2, False))
    builder.expect_return(ReturnExpectation("ticket_find", 0, "list", (ticket["phone"],)))
    return builder.build(BEHAVIOUR)


def _calendar(ctx: c.Ctx) -> CaseV5:
    """«свободные окна» — the calendar answers with the person it is kept for
    and their birth date in ISO.

    THE ROW IS KEYED ON THE NAME THE CALLER USES. A calendar filed under the
    full ФИО while the caller says surname and given name answers `empty` in
    every register, and the case would declare a result nobody can produce —
    the trap `parallel._slots` hit first.
    """
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    said_name = c.name(ctx, drawn.person, ("surname", "given"))
    iso = iso_date(drawn.dob)
    builder = c.new_builder(ctx, "callcenter", _CALENDAR_TOOLS, ("calendar_free",), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "базовая петля в расписании: имя -> окна -> ответ; дата "
                            "рождения приходит в ISO", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "cal-1", "calendar",
                 {"person": said_name.canonical, "birth_date": iso}, {
                     "person": ("NAME", identity, pools.Rendered(
                         said_name.canonical, said_name.canonical, False,
                         {"surname": drawn.person.surname[0], "given": drawn.person.given[0],
                          "gender": drawn.person.gender})),
                     "birth_date": ("DOB", identity, pools.Rendered(iso, iso, False,
                                                                    {"iso": iso}))})

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("я")
    draft.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    draft.say("посмотрите свободные окна на пятое сентября и подтвердите на кого запись")
    draft.punct(".")
    turn, said = told(builder, draft, {"name": ("NAME", identity, "required", False)})
    builder.v4.must_contain = (said_name.canonical,)

    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(arg_hop(said["name"], 1, turn, "calendar_free", 0, "person", 0, ""))
    builder.declare_hop(tool_hop(row["person"], 2, turn, "calendar_free", 0, "person"))
    builder.declare_hop(tool_hop(row["birth_date"], 3, turn, "calendar_free", 0, "birth_date"))
    builder.declare_hop(answer_hop(row["person"], 4, turn, 2, False))
    builder.expect_return(ReturnExpectation("calendar_free", 0, "list",
                                            (row["person"], row["birth_date"])))
    return builder.build(BEHAVIOUR)


def _directory(ctx: c.Ctx) -> CaseV5:
    """«проверьте мой адрес по справочнику» — DaData answers ONE normalised
    line, which is the `canon` form and a notation no caller writes.

    ONE ROW IN THE DIRECTORY, ON PURPOSE. Two would make the answer a CHOICE
    (`list`), which is `fanout_pick`'s question; the base loop is the value
    coming back changed, not the agent picking between candidates.
    """
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    street = drawn.address.street
    house = f"{drawn.address.house}{drawn.address.letter}"
    value = f"{pools.CITIES[city][0]}, г {city.capitalize()}, ул {street.capitalize()}, д {house}"
    postal = f"{pools.CITIES[city][1]}{ctx.rng.randrange(100, 999):03d}"[:6]
    builder = c.new_builder(ctx, "delivery", _DIRECTORY_TOOLS, ("address_suggest",), identity,
                            f"PHONE:{drawn.phone}",
                            "базовая петля в справочнике: адрес -> канонический адрес -> "
                            "ответ; возвращается одна строка в нотации ФИАС", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "a-1", "addresses", {
        "value": value, "postal_code": postal, "region": pools.CITIES[city][0],
        "city": city, "street": street, "house": house, "flat": "", "fias_id": _fias(ctx)}, {
        "value": ("LOC", f"{identity}.dir", pools.Rendered(
            value, value, False, {"city": city, "street": street, "house": house}))})

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("мой адрес")
    draft.value("addr", c.address(ctx, drawn.address))
    draft.say("сверьте его по справочнику и скажите как он пишется правильно")
    draft.punct(".")
    turn, said = told(builder, draft, {"addr": ("LOC", f"{identity}.home", "required", False)})
    builder.v4.must_contain = (street,)

    builder.declare_hop(user_hop(said["addr"], 0, turn))
    builder.declare_hop(arg_hop(said["addr"], 1, turn, "address_suggest", 0, "query", 0, ""))
    builder.declare_hop(tool_hop(row["value"], 2, turn, "address_suggest", 0,
                                 "suggestions[].value"))
    builder.declare_hop(answer_hop(row["value"], 3, turn, 2, False))
    builder.expect_return(ReturnExpectation("address_suggest", 0, "canon", (row["value"],)))
    return builder.build(BEHAVIOUR)


def _note(ctx: c.Ctx) -> CaseV5:
    """«что у вас записано по мне» — the knowledge base answers with ranked
    prose, and the customer's own note is the payload.

    THE QUERY IS A FREE LEAF: the agent writes it, and the customer's name goes
    into it in whatever form the model chose. The note's own spelling of the
    name is the backend's (clean, nominative), so the value comes back in a form
    the caller's register never produced — which is the crossing being measured.
    """
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    topic = _TOPICS[ctx.index % len(_TOPICS)]
    builder = c.new_builder(ctx, "crm", _SEARCH_TOOLS, ("kb_search",), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "базовая петля в базе знаний: имя -> заметка -> ответ; "
                            "телефон приходит в нотации заметки", (c.RAG_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    chunk = c.chunk_seed("kb-1", _NOTE,
                         {"who": stored_name(drawn, ctx), "tel": stored_phone(drawn)},
                         {"who": ("NAME", identity), "tel": ("PHONE", identity)},
                         {"topic": topic}, builder)

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("я")
    draft.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    draft.say(f"посмотрите что у вас в базе по теме {topic} по мне")
    draft.punct(".")
    turn, said = told(builder, draft, {"name": ("NAME", identity, "required", False)})
    builder.v4.must_contain = (drawn.person.surname[0],)

    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(arg_hop(said["name"], 1, turn, "kb_search", 0, "query", 0, ""))
    builder.declare_hop(tool_hop(chunk["who"], 2, turn, "kb_search", 0, "hits[0].text"))
    builder.declare_hop(tool_hop(chunk["tel"], 3, turn, "kb_search", 0, "hits[0].text"))
    builder.declare_hop(answer_hop(chunk["who"], 4, turn, 2, False))
    builder.expect_return(ReturnExpectation("kb_search", 0, "chunks",
                                            (chunk["who"], chunk["tel"])))
    return builder.build(BEHAVIOUR)


def _patient_card(ctx: c.Ctx) -> CaseV5:
    """«поднимите мою карту» — the МИС answers with the card, and every value on
    it is in a notation the caller's register does not produce: the birth date
    in ISO, the СНИЛС with the ПФР separators, the phone in E.164.

    THE KEY IS THE PHONE, SAID ALOUD, AND IT COMES BACK. One datum crosses three
    times in one case — dictated by the caller (IN/user), written into the search
    (OUT/tool_arg), returned by the card (IN/tool) — so the comparator sees the
    SAME value in the caller's form and in the clinic's, which is the crossing
    the vertical was in the table for and the one no case could make while the
    clinic had only writing tools.

    THE СНИЛС IS NOT SAID AND IS ONLY READ BACK. A caller who dictates their
    СНИЛС has already put it in the ПФР's own notation, and the hop would then
    compare a format with itself; read off the card it arrives in a notation
    nothing in the dialogue produced.
    """
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    snils_digits = pools.snils_digits(ctx.rng)
    builder = c.new_builder(ctx, "clinic", _CLINIC_TOOLS, ("patient_find",), identity,
                            f"PHONE:{drawn.phone}",
                            "базовая петля в клинике: телефон -> карта пациента -> ответ; "
                            "ДР приходит в ISO, СНИЛС с разделителями ПФР", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = patient_seed("pat-1", snils_digits, drawn, builder, identity)

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("поднимите мою карту по телефону")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("продиктуйте снилс и дату рождения как они у вас записаны")
    draft.punct(".")
    turn, said = told(builder, draft, {"ph": ("PHONE", identity, "required", False)})
    builder.v4.must_contain = (spaced_snils(snils_digits),)

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(arg_hop(said["ph"], 1, turn, "patient_find", 0, "phone", 0, ""))
    # EVERY LEAF THE CARD RETURNS IS DECLARED, all five. A value that comes back
    # and crosses no hop is the shape this whole pass exists to remove: the
    # result carries it, `toolresult_masked` counts it, and no form line would
    # ever say what happened to it.
    builder.declare_hop(tool_hop(row["last_name"], 2, turn, "patient_find", 0,
                                 "patient.last_name"))
    builder.declare_hop(tool_hop(row["first_name"], 3, turn, "patient_find", 0,
                                 "patient.first_name"))
    builder.declare_hop(tool_hop(row["birth_date"], 4, turn, "patient_find", 0,
                                 "patient.birth_date"))
    builder.declare_hop(tool_hop(row["snils"], 5, turn, "patient_find", 0, "patient.snils"))
    builder.declare_hop(tool_hop(row["phone"], 6, turn, "patient_find", 0, "patient.phone"))
    builder.declare_hop(answer_hop(row["snils"], 7, turn, 5, False))
    builder.declare_hop(answer_hop(row["birth_date"], 8, turn, 4, True))
    builder.expect_return(ReturnExpectation(
        "patient_find", 0, "single",
        (row["last_name"], row["first_name"], row["birth_date"], row["snils"], row["phone"])))
    return builder.build(BEHAVIOUR)
