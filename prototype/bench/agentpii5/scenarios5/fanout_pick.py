"""`fanout_pick` — a list of several people comes back and ONE of them is right.

THE FAMILY A PLACEHOLDER MASKER CANNOT PASS, and the only one in this half whose
failure mode is a wrong action rather than a wrong form. The list holds two or
three candidates whose values are of the SAME type as the customer's cue, so the
schema tells them apart by nothing: the agent must match BY VALUE. Replace every
name with «[NAME]» and the three rows become one row printed three times, and
every choice is equally arbitrary — which is what «где плейсхолдер слепнет» in
§3.1 means, stated as a test.

`must_not_contain` IS REAL HERE AND ONLY HERE. The non-target candidates are
other people whose values have no business in the answer at all, so their
absence is mechanically checkable — unlike `same_tool_other_target`, where both
identities are legitimately reported.

WHAT THE SEEDS MUST NOT DO. Two candidates may not share a value that a hop
names: the mock's by-value index tags a value that two items hold as AMBIGUOUS
and drops the tag, and a hop nobody can observe is a hop that always scores as a
miss. Hence the namesake variants match on the given name and the birth date —
the columns that differ — and never on the shared surname.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import PickSpec, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, full_name, grouped_card,
                                               minted, seeded, told, tool_hop, user_hop)

BEHAVIOUR: str = "fanout_pick"
TOOLS: tuple[str, ...] = (
    "bank_client_find", "account_statement", "crm_find_contact", "crm_upsert_contact",
    "kb_search", "notify_sms", "courier_book")
_BANK_TOOLS: tuple[str, ...] = ("bank_client_find", "account_statement", "notify_sms")
_CRM_TOOLS: tuple[str, ...] = ("crm_find_contact", "crm_upsert_contact", "notify_sms")
_KB_TOOLS: tuple[str, ...] = ("kb_search", "notify_sms")
_COURIER_TOOLS: tuple[str, ...] = ("crm_find_contact", "courier_book", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    builders = (_clients, _namesakes, _chunks, _courier)
    return builders[ctx.index % 4](ctx)


def _others(ctx: c.Ctx, how_many: int, avoid: str) -> tuple[c.Drawn, ...]:
    """The other candidates, from streams of their own, none of them `avoid`."""
    out: list[c.Drawn] = []
    step = 0
    while len(out) < how_many:
        stream = c.ctx_for(f"{BEHAVIOUR}:other", ctx.seed, ctx.index * 100 + step, ctx.register)
        candidate = c.draw(stream, city=stream.rng.choice(list(pools.CORPUS_CITIES)))
        # EVERY COLUMN A HOP NAMES MUST DIFFER, not only the given name: a value
        # two seeds share is ambiguous to the mock's by-value index and tagged on
        # neither, which turns a corpus collision into a gateway miss.
        clash = candidate.person.given[0] == avoid or any(
            one.person.given[0] == candidate.person.given[0]
            or one.phone == candidate.phone
            or one.address.street == candidate.address.street
            or one.dob == candidate.dob for one in out)
        if not clash:
            out.append(candidate)
        step += 1
        if step > 60:
            raise pools.BuildError(f"{ctx.index}: could not draw {how_many} distinct candidates")
    return tuple(out)


def _with_surname(drawn: c.Drawn, surname: tuple[str, str, str]) -> c.Drawn:
    """The same person under another surname — a namesake, never a copy. v4's
    `lookup_list` needed this and so does this family: the surname is what makes
    the list a real choice, the rest is what resolves it."""
    person = pools.Person(surname=surname, given=drawn.person.given,
                          patronymic=drawn.person.patronymic,
                          short_patronymic=drawn.person.short_patronymic,
                          gender=drawn.person.gender)
    return c.Drawn(person=person, phone=drawn.phone, address=drawn.address, dob=drawn.dob,
                   email_local=drawn.email_local, email_domain=drawn.email_domain)


def _conversation(ctx: c.Ctx) -> str:
    return f"conv-fan-{ctx.index}" if ctx.index % 4 == 0 else ""


def _clients(ctx: c.Ctx) -> Case:
    """Two bank clients on ONE phone — a family number, the shape a bank's search
    by phone actually returns. The name decides which one."""
    target = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    other = _others(ctx, 1, target.person.given[0])[0]
    one, two = f"p{ctx.index}a", f"p{ctx.index}b"
    phone = f"+7{target.phone}"
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS,
                            ("bank_client_find", "account_statement"), one,
                            f"PHONE:{target.phone}",
                            "один телефон — два клиента; выбирает имя, а не порядок строк",
                            ())
    builder.v4.conversation_id = _conversation(ctx)
    builder.v4.must_not_contain = (full_name(other.person),)
    rows = []
    for slot, (drawn, identity) in enumerate(((target, one), (other, two))):
        card_digits = pools.card_digits(ctx.rng)
        card = grouped_card(card_digits)
        inn_digits = pools.inn12_digits(ctx.rng)
        person = full_name(drawn.person)
        # THE PHONE COLUMN IS ON BOTH ROWS AND TYPED ON NEITHER: it is what the
        # search matches, and two seed items holding one string are ambiguous to
        # the mock's by-value index — the tags of the rows would go with it.
        rows.append(seeded(builder, f"bc-{slot + 1}", "bank_clients", {
            "name": person, "inn": inn_digits, "card": card, "phone": phone,
            "status": "active",
            "rows": [{"date": "2026-08-03", "amount": "1500.00", "currency": "RUB",
                      "description": "Оплата заказа"}]}, {
            "name": ("NAME", identity, pools.Rendered(person, person, False,
                                                      {"surname": drawn.person.surname[0],
                                                       "given": drawn.person.given[0],
                                                       "gender": drawn.person.gender})),
            "inn": ("INN", identity, pools.Rendered(inn_digits, inn_digits, False,
                                                    {"digits": inn_digits})),
            "card": ("CARD", identity, pools.Rendered(card, card, False,
                                                      {"digits": card_digits})),
        }))

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("по номеру")
    draft.value("ph", c.phone(ctx, target.phone))
    draft.say("там двое это")
    draft.value("name", c.name(ctx, target.person, ("surname", "given")))
    draft.say("покажите движение по его карте")
    draft.punct(".")
    turn, said = told(builder, draft, {"ph": ("PHONE", one, "required", False),
                                       "name": ("NAME", one, "required", False)})
    builder.set_pick(PickSpec("bank_client_find", (one, two), one, "account_statement"))

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(user_hop(said["name"], 1, turn))
    builder.declare_hop(arg_hop(said["ph"], 2, turn, "bank_client_find", 0, "phone", 0, ""))
    builder.declare_hop(tool_hop(rows[0]["name"], 3, turn, "bank_client_find", 0,
                                 "clients[].name"))
    builder.declare_hop(tool_hop(rows[1]["name"], 4, turn, "bank_client_find", 0,
                                 "clients[].name"))
    builder.declare_hop(tool_hop(rows[0]["card"], 5, turn, "account_statement", 0,
                                 "holder.card"))
    builder.declare_hop(answer_hop(rows[0]["card"], 6, turn, 5, False))
    builder.declare_hop(answer_hop(rows[0]["name"], 7, turn, 3, True))
    builder.expect_return(ReturnExpectation(
        "bank_client_find", 0, "list",
        (rows[0]["name"], rows[0]["inn"], rows[0]["card"],
         rows[1]["name"], rows[1]["inn"], rows[1]["card"])))
    builder.expect_return(ReturnExpectation("account_statement", 0, "list",
                                            (rows[0]["name"], rows[0]["card"])))
    return builder.build(BEHAVIOUR)


def _namesakes(ctx: c.Ctx) -> Case:
    """Three cards under one surname; the birth date resolves them, and the act
    is an update of the RIGHT card."""
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    target = c.draw(ctx, city=city)
    others = tuple(_with_surname(one, target.person.surname)
                   for one in _others(ctx, 2, target.person.given[0]))
    identity = f"p{ctx.index}"
    labels = (identity, f"{identity}.o1", f"{identity}.o2")
    builder = c.new_builder(ctx, "crm", _CRM_TOOLS,
                            ("crm_find_contact", "crm_upsert_contact"), identity,
                            f"NAME:{full_name(target.person)}",
                            "три однофамильца: различает дата рождения, обновить надо ту "
                            "карточку, про которую спросили", ())
    builder.v4.conversation_id = _conversation(ctx)
    builder.v4.must_not_contain = tuple(one.person.given[0] for one in others)
    # THE TARGET IS NOT ALWAYS FIRST. A card chosen by position would pass this
    # family without reading anything, which is the one thing it must not allow.
    place = ctx.index % 3
    rows_in_order: list[tuple[c.Drawn, str]] = [(others[0], labels[1]), (others[1], labels[2])]
    rows_in_order.insert(place, (target, labels[0]))
    cards: dict[str, dict[str, str]] = {}
    for slot, (drawn, label) in enumerate(rows_in_order):
        before = len(builder.v4.pii)
        c.contact_seed(f"c-{slot + 1}", drawn, city, ctx, builder, label)
        cards[label] = {item.where.path: item.id for item in minted(builder, before)}

    new_address = pools.draw_address(ctx.rng, city, True, False, True)
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("найдите карточку фамилия")
    draft.value("surname", c.name(ctx, target.person, ("surname",)))
    draft.say("день рождения")
    draft.value("dob", c.dob(ctx, target.dob))
    draft.say("новый адрес")
    draft.value("addr", c.address(ctx, new_address))
    draft.punct(".")
    turn, said = told(builder, draft, {
        "surname": ("NAME", identity, "required", False),
        "dob": ("DOB", identity, "required", False),
        "addr": ("LOC", f"{identity}.new", "required", False)})
    builder.set_pick(PickSpec("crm_find_contact", labels, identity, "crm_upsert_contact"))

    builder.declare_hop(user_hop(said["surname"], 0, turn))
    builder.declare_hop(user_hop(said["dob"], 1, turn))
    builder.declare_hop(user_hop(said["addr"], 2, turn))
    builder.declare_hop(arg_hop(said["surname"], 3, turn, "crm_find_contact", 0,
                                "query.last_name", 0, ""))
    builder.declare_hop(tool_hop(cards[labels[0]]["birth_date"], 4, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    builder.declare_hop(tool_hop(cards[labels[1]]["birth_date"], 5, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    builder.declare_hop(tool_hop(cards[labels[2]]["birth_date"], 6, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    # THE GIVEN NAME COMES BACK FROM THE LIST, NOT FROM THE WRITE-BACK. The
    # upsert composes its echo out of the ARGUMENTS it was handed, and this call
    # hands it an address and an id — nothing would be there to label, and a hop
    # on it would be a permanent miss charged to the gateway.
    builder.declare_hop(tool_hop(cards[labels[0]]["first_name"], 7, turn, "crm_find_contact", 0,
                                 "contacts[].first_name"))
    builder.declare_hop(arg_hop(said["addr"], 8, turn, "crm_upsert_contact", 0,
                                "contact.address.street", 2, ""))
    builder.declare_hop(answer_hop(cards[labels[0]]["first_name"], 9, turn, 7, True))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list",
        tuple(cards[label][path] for label in labels
              for path in ("first_name", "birth_date", "phone"))))
    return builder.build(BEHAVIOUR)


def _chunks(ctx: c.Ctx) -> Case:
    """Three knowledge-base notes about three people; one of them is the caller's
    and the phone to text is inside its prose."""
    target = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    # THE THREE NOTES ARE ABOUT NAMESAKES, and that is what makes the list a
    # list. `kb_search` ranks by word overlap: a note about a person whose name
    # shares no word with the query scores zero and is not returned at all, so
    # three unrelated people would come back as one hit and the family would
    # measure nothing. A shared surname puts all three in the result; the given
    # name and the phone are what tell them apart.
    others = tuple(_with_surname(one, target.person.surname)
                   for one in _others(ctx, 2, target.person.given[0]))
    identity = f"p{ctx.index}"
    labels = (identity, f"{identity}.o1", f"{identity}.o2")
    builder = c.new_builder(ctx, "crm", _KB_TOOLS, ("kb_search", "notify_sms"), identity,
                            f"NAME:{full_name(target.person)}",
                            "три заметки базы знаний про трёх людей: чужие значения в ответ "
                            "переносить нельзя, телефон берётся из СВОЕЙ заметки",
                            (c.RAG_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    builder.v4.must_not_contain = tuple(full_name(one.person) for one in others)
    chunks: dict[str, dict[str, str]] = {}
    for slot, (drawn, label) in enumerate(zip((target, *others), labels)):
        person = full_name(drawn.person)
        phone = f"+7{drawn.phone}"
        chunks[label] = seeded(builder, f"kb-{slot + 1}", "kb_chunks", {
            "identity": label, "name": person, "phone": phone,
            "template": "Клиент {name}, телефон {phone}, просил перезвонить по заявке."}, {
            "name": ("NAME", label, pools.Rendered(person, person, False,
                                                   {"surname": drawn.person.surname[0],
                                                    "given": drawn.person.given[0],
                                                    "gender": drawn.person.gender})),
            "phone": ("PHONE", label, pools.Rendered(phone, phone, False,
                                                     {"digits": drawn.phone})),
        })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("посмотрите в базе знаний что там по клиенту")
    draft.value("name", c.name(ctx, target.person, ("surname", "given")))
    draft.say("и отправьте ему смс")
    draft.punct(".")
    turn, said = told(builder, draft, {"name": ("NAME", identity, "required", False)})
    builder.set_pick(PickSpec("kb_search", labels, identity, "notify_sms"))

    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(arg_hop(said["name"], 1, turn, "kb_search", 0, "query", 0, ""))
    builder.declare_hop(tool_hop(chunks[labels[0]]["name"], 2, turn, "kb_search", 0,
                                 "hits[].text"))
    builder.declare_hop(tool_hop(chunks[labels[0]]["phone"], 3, turn, "kb_search", 0,
                                 "hits[].text"))
    builder.declare_hop(tool_hop(chunks[labels[1]]["name"], 4, turn, "kb_search", 0,
                                 "hits[].text"))
    builder.declare_hop(tool_hop(chunks[labels[2]]["name"], 5, turn, "kb_search", 0,
                                 "hits[].text"))
    builder.declare_hop(arg_hop(chunks[labels[0]]["phone"], 6, turn, "notify_sms", 0,
                                "number", 3, ""))
    builder.declare_hop(arg_hop(chunks[labels[0]]["name"], 7, turn, "notify_sms", 0,
                                "text", 2, ""))
    builder.declare_hop(answer_hop(chunks[labels[0]]["name"], 8, turn, 2, True))
    builder.expect_return(ReturnExpectation(
        "kb_search", 0, "chunks",
        (chunks[labels[0]]["name"], chunks[labels[0]]["phone"],
         chunks[labels[1]]["name"], chunks[labels[2]]["name"])))
    return builder.build(BEHAVIOUR)


def _courier(ctx: c.Ctx) -> Case:
    """Same list, different act: the chosen card's address goes to a courier —
    a wrong pick here sends a real parcel to a real stranger."""
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    target = c.draw(ctx, city=city)
    others = tuple(_with_surname(one, target.person.surname)
                   for one in _others(ctx, 1, target.person.given[0]))
    identity = f"p{ctx.index}"
    labels = (identity, f"{identity}.o1")
    builder = c.new_builder(ctx, "delivery", _COURIER_TOOLS,
                            ("crm_find_contact", "courier_book"), identity,
                            f"NAME:{full_name(target.person)}",
                            "два однофамильца, курьер едет к одному: ошибка выбора — это "
                            "посылка чужому человеку", ())
    builder.v4.conversation_id = _conversation(ctx)
    builder.v4.must_not_contain = tuple(one.person.given[0] for one in others)
    # THE TARGET IS NOT ALWAYS THE FIRST ROW here either, for the same reason.
    rows_in_order: list[tuple[c.Drawn, str]] = [(others[0], labels[1])]
    rows_in_order.insert(ctx.index % 2, (target, labels[0]))
    cards: dict[str, dict[str, str]] = {}
    for slot, (drawn, label) in enumerate(rows_in_order):
        before = len(builder.v4.pii)
        c.contact_seed(f"c-{slot + 1}", drawn, city, ctx, builder, label)
        cards[label] = {item.where.path: item.id for item in minted(builder, before)}

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("вызовите курьера клиенту фамилия")
    draft.value("surname", c.name(ctx, target.person, ("surname",)))
    draft.say("день рождения")
    draft.value("dob", c.dob(ctx, target.dob))
    draft.say("адрес в карточке")
    draft.punct(".")
    turn, said = told(builder, draft, {"surname": ("NAME", identity, "required", False),
                                       "dob": ("DOB", identity, "required", False)})
    builder.v4.must_contain = (target.address.street,)
    builder.set_pick(PickSpec("crm_find_contact", labels, identity, "courier_book"))

    builder.declare_hop(user_hop(said["surname"], 0, turn))
    builder.declare_hop(user_hop(said["dob"], 1, turn))
    builder.declare_hop(arg_hop(said["surname"], 2, turn, "crm_find_contact", 0,
                                "query.last_name", 0, ""))
    builder.declare_hop(tool_hop(cards[labels[0]]["birth_date"], 3, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    builder.declare_hop(tool_hop(cards[labels[1]]["birth_date"], 4, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    builder.declare_hop(tool_hop(cards[labels[0]]["address.street"], 5, turn,
                                 "crm_find_contact", 0, "contacts[].address.street"))
    builder.declare_hop(tool_hop(cards[labels[0]]["phone"], 6, turn, "crm_find_contact", 0,
                                 "contacts[].phone"))
    # THE GIVEN NAME, NOT THE SURNAME: both candidates are namesakes, their
    # `last_name` items hold ONE string, and a value two seed items share is
    # ambiguous to the by-value index and tagged on neither.
    builder.declare_hop(tool_hop(cards[labels[0]]["first_name"], 7, turn, "crm_find_contact", 0,
                                 "contacts[].first_name"))
    builder.declare_hop(arg_hop(cards[labels[0]]["address.street"], 8, turn, "courier_book", 0,
                                "address.street", 5, ""))
    builder.declare_hop(arg_hop(cards[labels[0]]["phone"], 9, turn, "courier_book", 0,
                                "contact.phone", 6, ""))
    # THE RECIPIENT'S NAME IS REQUIRED BY THE COURIER API, so the pick has to
    # carry it too: a booking that named only a phone would be refused, and a
    # case whose call cannot be made measures nothing.
    builder.declare_hop(arg_hop(cards[labels[0]]["first_name"], 10, turn, "courier_book", 0,
                                "contact.name", 7, ""))
    builder.declare_hop(answer_hop(cards[labels[0]]["address.street"], 11, turn, 5, False))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list",
        tuple(cards[label][path] for label in labels
              for path in ("first_name", "birth_date", "phone", "address.street"))))
    builder.expect_return(ReturnExpectation(
        "courier_book", 0, "nested",
        (cards[labels[0]]["phone"], cards[labels[0]]["address.street"])))
    return builder.build(BEHAVIOUR)
