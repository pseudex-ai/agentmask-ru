"""`sequential_chain` — the result of A becomes the argument of B (and of C).

The one shape where an error cannot be corrected downstream, because it ENTERS
the next call. The same datum crosses the gateway four times or more — out as a
substitute, back as a substitute, out again, back again — and a form lost at any
crossing is lost for the rest of the chain. v4 measured this on CRM only
(`chain`, `tool_chain`, `result_feed`); the four verticals here are the ones v4
never had a chain in, and they were chosen because each returns its values in a
notation of its own: a bank prints a card in four groups, a ticket system retells
the dialogue in prose, a courier service normalises the address, a form parser
hands back typed fields, a ГИБДД register answers in the plate's canonical form.

WHAT COUNTS AS A TRANSITION, AND WHY THIS FAMILY DECLARES AT LEAST THREE. A
transition is an OUT hop whose `source_hop` is an IN hop of ANOTHER tool. R12
asks for one; §3.1's row asks for three, and three is what makes the family
different from `single` — one transition is a lookup feeding a write, which the
revised v4 corpus already supplies in bulk.

READING A FILE IS AN `IN/document` HOP, NOT AN `IN/tool` HOP. The form the
substitute must mirror is the DOCUMENT's (a CSV cell, a form field, a scanned
line), not the reading tool's, and `contracts.IN_OWNERS` separates the two for
exactly that reason. R12 counts only `tool` sources, so the file families ALSO
declare the write-back result (`crm_upsert_contact` echoes what it stored) and
chain from there — which is what a real agent does anyway when it confirms.

WHY THE FILE PATH LIVES IN THE SYSTEM PROMPT. A path carries a dot, and a dot is
sentence punctuation that `voice_raw` and `voice_itn` both refuse; dictating one
would cost these families the 45% of the corpus that is voice. It is also where a
real integrator puts it — the inbox is configuration, not something the caller
says.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import Hop, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, full_name, grouped_card,
                                               iso_date, minted, seeded, spaced_snils, told,
                                               tool_hop, user_hop)

BEHAVIOUR: str = "sequential_chain"
TOOLS: tuple[str, ...] = (
    "bank_client_find", "account_statement", "payment_create", "ticket_find", "ticket_history",
    "escalate_to_human", "vehicle_check", "ticket_create", "crm_find_contact", "courier_book",
    "courier_status", "file_read", "crm_upsert_contact", "email_send", "notify_sms",
    "doc_retrieve", "form_parse")
_BANK_TOOLS: tuple[str, ...] = ("bank_client_find", "account_statement", "payment_create",
                                "notify_sms")
_SUPPORT_TOOLS: tuple[str, ...] = ("ticket_find", "ticket_history", "escalate_to_human",
                                   "notify_sms")
_GOV_TOOLS: tuple[str, ...] = ("vehicle_check", "ticket_create", "notify_sms")
_DELIVERY_TOOLS: tuple[str, ...] = ("crm_find_contact", "courier_book", "courier_status",
                                    "notify_sms")
_FILE_TOOLS: tuple[str, ...] = ("file_read", "form_parse", "crm_upsert_contact",
                                "email_send", "notify_sms")
_FORM_TOOLS: tuple[str, ...] = ("doc_retrieve", "form_parse", "crm_upsert_contact", "notify_sms")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Six verticals by index modulo six. At forty cases the two file families
    get six each and the rest seven — above `MIN_TYPE_DENOMINATOR` for every one
    of the six new tools they are the only home of."""
    builders = (_bank, _support, _plates, _delivery, _file, _form)
    return builders[ctx.index % 6](ctx)


def _conversation(ctx: c.Ctx) -> str:
    return f"conv-chain5-{ctx.index}" if ctx.index % 2 == 0 else ""


def _bank(ctx: c.Ctx) -> Case:
    """ИНН → клиент → выписка → платёж. Three transitions, and the card that
    ends up in the payment came back from the statement in the bank's own
    four-group notation, never in the caller's."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    inn_digits = pools.inn12_digits(ctx.rng)
    card_digits = pools.card_digits(ctx.rng)
    card = grouped_card(card_digits)
    person = full_name(drawn.person)
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS,
                            ("bank_client_find", "account_statement", "payment_create"), identity,
                            f"NAME:{person}",
                            "инн -> клиент -> выписка -> платёж: карта и ФИО входят в "
                            "следующий вызов в нотации банка", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "bc-1", "bank_clients", {
        "name": person, "inn": inn_digits, "card": card, "phone": f"+7{drawn.phone}",
        "status": "active",
        "rows": [{"date": "2026-08-03", "amount": "1500.00", "currency": "RUB",
                  "description": "Оплата заказа"},
                 {"date": "2026-08-11", "amount": "420.00", "currency": "RUB",
                  "description": "Доставка"}]}, {
        "name": ("NAME", identity, pools.Rendered(person, person, False,
                                                  {"surname": drawn.person.surname[0],
                                                   "given": drawn.person.given[0],
                                                   "gender": drawn.person.gender})),
        "inn": ("INN", identity, pools.Rendered(inn_digits, inn_digits, False,
                                                {"digits": inn_digits})),
        "card": ("CARD", identity, pools.Rendered(card, card, False, {"digits": card_digits})),
    })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("клиент инн")
    draft.value("inn", c.inn(ctx, inn_digits))
    draft.say("посмотрите выписку и проведите оплату с его карты")
    draft.punct(".")
    turn, said = told(builder, draft, {"inn": ("INN", identity, "required", False)})
    builder.v4.must_contain = (person,)

    builder.declare_hop(user_hop(said["inn"], 0, turn))
    builder.declare_hop(arg_hop(said["inn"], 1, turn, "bank_client_find", 0, "inn", 0, ""))
    builder.declare_hop(tool_hop(row["name"], 2, turn, "bank_client_find", 0, "client.name"))
    builder.declare_hop(tool_hop(row["inn"], 3, turn, "bank_client_find", 0, "client.inn"))
    builder.declare_hop(tool_hop(row["card"], 4, turn, "account_statement", 0, "holder.card"))
    builder.declare_hop(arg_hop(row["card"], 5, turn, "payment_create", 0,
                                "payment_method_data.card.number", 4, ""))
    builder.declare_hop(arg_hop(row["name"], 6, turn, "payment_create", 0,
                                "receipt.customer.full_name", 2, ""))
    builder.declare_hop(arg_hop(row["inn"], 7, turn, "payment_create", 0,
                                "payment_method_data.payer_bank_details.inn", 3, ""))
    builder.declare_hop(answer_hop(row["name"], 8, turn, 2, False))
    builder.declare_hop(answer_hop(row["card"], 9, turn, 4, True))
    builder.expect_return(ReturnExpectation("bank_client_find", 0, "single",
                                            (row["name"], row["inn"], row["card"])))
    builder.expect_return(ReturnExpectation("account_statement", 0, "list",
                                            (row["name"], row["card"])))
    return builder.build(BEHAVIOUR)


def _support(ctx: c.Ctx) -> Case:
    """Заявка → история в прозе → эскалация. The middle result is FREE TEXT with
    three people's worth of values in one sentence, and the summary the agent
    writes for a human is an OUT hop of its own owner."""
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    person = full_name(drawn.person)
    phone = f"+7{drawn.phone}"
    street = drawn.address.street
    builder = c.new_builder(ctx, "callcenter", _SUPPORT_TOOLS,
                            ("ticket_find", "ticket_history", "escalate_to_human"), identity,
                            f"PHONE:{drawn.phone}",
                            "заявка -> история в свободном тексте -> эскалация: пересказ "
                            "диалога человеку — хоп-summary", ())
    builder.v4.conversation_id = _conversation(ctx)
    # THE TICKET ROW CARRIES NO TYPED ITEM ON PURPOSE. Its phone column is the
    # same string as the history's, and two seed items holding one value are
    # AMBIGUOUS to the mock's by-value index — neither would be tagged, and the
    # IN hop on `issues[].requester.phone` would be unobservable.
    # THE TICKET'S ID IS «t-1», NOT «tkt-1». `ticket_history` refuses an issue id
    # outside `tools.ISSUE_ID_RE` (`t-\d{1,6}`), while `tkt-` is the prefix the
    # mock MINTS for a ticket it creates — so a chain seeded with a minted-shaped
    # id cannot take its second step. The id a pre-existing ticket carries is
    # ours to choose, and this is the one the reader accepts.
    seeded(builder, "t-1", "tickets", {"phone": phone, "subject": "Перенос доставки"}, {})
    event = seeded(builder, "ev-1", "ticket_events", {
        "issue_id": "t-1", "order": 1, "name": person, "phone": phone, "address": street,
        "template": "12.09 клиент {name} ({phone}) просил перенести доставку на {address}."}, {
        "name": ("NAME", identity, pools.Rendered(person, person, False,
                                                  {"surname": drawn.person.surname[0],
                                                   "given": drawn.person.given[0],
                                                   "gender": drawn.person.gender})),
        "phone": ("PHONE", identity, pools.Rendered(phone, phone, False,
                                                    {"digits": drawn.phone})),
        "address": ("LOC", f"{identity}.home", pools.Rendered(street, street, False,
                                                              {"street": street})),
    })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("по моей заявке телефон")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("поднимите историю и переключите на человека")
    draft.punct(".")
    turn, said = told(builder, draft, {"ph": ("PHONE", identity, "required", False)})
    builder.v4.must_contain = (street,)

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(arg_hop(said["ph"], 1, turn, "ticket_find", 0, "phone", 0, ""))
    builder.declare_hop(tool_hop(event["phone"], 2, turn, "ticket_find", 0,
                                 "issues[].requester.phone"))
    builder.declare_hop(tool_hop(event["name"], 3, turn, "ticket_history", 0, "history"))
    builder.declare_hop(tool_hop(event["phone"], 4, turn, "ticket_history", 0, "history"))
    builder.declare_hop(tool_hop(event["address"], 5, turn, "ticket_history", 0, "history"))
    builder.declare_hop(arg_hop(event["name"], 6, turn, "escalate_to_human", 0, "summary", 3, ""))
    builder.declare_hop(arg_hop(event["phone"], 7, turn, "escalate_to_human", 0, "summary", 4, ""))
    builder.declare_hop(arg_hop(event["address"], 8, turn, "escalate_to_human", 0,
                                "summary", 5, ""))
    builder.declare_hop(answer_hop(event["address"], 9, turn, 5, False))
    builder.declare_hop(answer_hop(event["name"], 10, turn, 3, True))
    builder.expect_return(ReturnExpectation("ticket_find", 0, "list", (event["phone"],)))
    builder.expect_return(ReturnExpectation("ticket_history", 0, "free_text",
                                            (event["name"], event["phone"], event["address"])))
    return builder.build(BEHAVIOUR)


def _plates(ctx: c.Ctx) -> Case:
    """Номер → владелец → заявка. The owner's name goes into the ticket's free
    text, which is a SUMMARY hop, and the plate into its subject."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    canonical = c.plate_text(ctx.rng)
    builder = c.new_builder(ctx, "gov", _GOV_TOOLS, ("vehicle_check", "ticket_create"), identity,
                            f"PLATE:{canonical}",
                            "номер -> владелец -> заявка: ФИО из реестра уходит в свободный "
                            "текст тикета", ())
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "veh-1", "vehicles", {
        "plate": canonical, "model": ctx.rng.choice(("Kia Rio", "Lada Vesta", "Skoda Rapid")),
        "year": ctx.rng.choice(("2015", "2018", "2022")),
        "owner": {"last_name": drawn.person.surname[0], "first_name": drawn.person.given[0]}}, {
        "plate": ("PLATE", identity, c.plate(c.ctx_for("plate", ctx.seed, ctx.index, "clean"),
                                             canonical)),
        "owner.last_name": ("NAME", identity, pools.Rendered(
            drawn.person.surname[0], drawn.person.surname[0], False,
            {"surname": drawn.person.surname[0], "gender": drawn.person.gender})),
        "owner.first_name": ("NAME", identity, pools.Rendered(
            drawn.person.given[0], drawn.person.given[0], False,
            {"given": drawn.person.given[0], "gender": drawn.person.gender})),
    })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("пробейте номер")
    draft.value("plate", c.plate(ctx, canonical))
    draft.say("и заведите заявку на владельца")
    draft.punct(".")
    turn, said = told(builder, draft, {"plate": ("PLATE", identity, "required", False)})
    builder.v4.must_contain = (drawn.person.surname[0],)

    builder.declare_hop(user_hop(said["plate"], 0, turn))
    builder.declare_hop(arg_hop(said["plate"], 1, turn, "vehicle_check", 0, "plate", 0, ""))
    builder.declare_hop(tool_hop(row["plate"], 2, turn, "vehicle_check", 0, "plate"))
    builder.declare_hop(tool_hop(row["owner.last_name"], 3, turn, "vehicle_check", 0,
                                 "owner.last_name"))
    builder.declare_hop(tool_hop(row["owner.first_name"], 4, turn, "vehicle_check", 0,
                                 "owner.first_name"))
    builder.declare_hop(arg_hop(row["plate"], 5, turn, "ticket_create", 0, "subject", 2, ""))
    builder.declare_hop(arg_hop(row["owner.last_name"], 6, turn, "ticket_create", 0, "text", 3, ""))
    builder.declare_hop(arg_hop(row["owner.first_name"], 7, turn, "ticket_create", 0,
                                "text", 4, ""))
    builder.declare_hop(answer_hop(row["owner.last_name"], 8, turn, 3, False))
    builder.declare_hop(answer_hop(row["plate"], 9, turn, 2, True))
    builder.expect_return(ReturnExpectation(
        "vehicle_check", 0, "single",
        (row["plate"], row["owner.last_name"], row["owner.first_name"])))
    return builder.build(BEHAVIOUR)


def _delivery(ctx: c.Ctx) -> Case:
    """Карточка → вызов курьера → статус. The courier service hands the address
    back in ITS normalisation («г. Ижевск, ул. Клубная, д. 85, кв. 12»), which is
    the crossing `same_person_variant` was found on in v4."""
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "delivery", _DELIVERY_TOOLS,
                            ("crm_find_contact", "courier_book", "courier_status"), identity,
                            f"PHONE:{drawn.phone}",
                            "карточка -> вызов курьера -> статус: адрес возвращается в "
                            "нормализации курьерки", ())
    builder.v4.conversation_id = _conversation(ctx)
    before = len(builder.v4.pii)
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    card = {item.where.path: item.id for item in minted(builder, before)}

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("повторите доставку по номеру")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("адрес и получателя возьмите из карточки потом скажите статус")
    draft.punct(".")
    turn, said = told(builder, draft, {"ph": ("PHONE", identity, "required", False)})
    builder.v4.must_contain = (drawn.address.street,)

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(arg_hop(said["ph"], 1, turn, "crm_find_contact", 0, "query.phone", 0, ""))
    builder.declare_hop(tool_hop(card["phone"], 2, turn, "crm_find_contact", 0,
                                 "contacts[].phone"))
    builder.declare_hop(tool_hop(card["last_name"], 3, turn, "crm_find_contact", 0,
                                 "contacts[].last_name"))
    builder.declare_hop(tool_hop(card["address.street"], 4, turn, "crm_find_contact", 0,
                                 "contacts[].address.street"))
    builder.declare_hop(arg_hop(card["phone"], 5, turn, "courier_book", 0, "contact.phone", 2, ""))
    builder.declare_hop(arg_hop(card["last_name"], 6, turn, "courier_book", 0,
                                "contact.name", 3, ""))
    builder.declare_hop(arg_hop(card["address.street"], 7, turn, "courier_book", 0,
                                "address.street", 4, ""))
    # THE WHOLE BLOCK COMES BACK TAGGED FROM THE COURIER — address, name and
    # phone. It used to be the address alone, on the reading that a claim the
    # booking minted is not a seeded row and so nothing could label its
    # `contact.*` columns; that was true of `mock._slot_of`, the EXACT map, and
    # not of the datum. The values in the claim are the CRM card's own (the
    # agent wrote them into `courier_book` three hops above), so the by-value
    # index identifies them exactly as it identifies the street — and the mock
    # now renders the recipient through it. These are real crossings: the
    # gateway unmasked them into the booking and has to mask them coming back.
    builder.declare_hop(tool_hop(card["address.street"], 8, turn, "courier_status", 0, "address"))
    builder.declare_hop(tool_hop(card["last_name"], 9, turn, "courier_status", 0,
                                 "recipient.name"))
    builder.declare_hop(tool_hop(card["phone"], 10, turn, "courier_status", 0,
                                 "recipient.phone"))
    builder.declare_hop(answer_hop(card["address.street"], 11, turn, 8, False))
    builder.declare_hop(answer_hop(card["phone"], 12, turn, 2, True))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list",
        (card["last_name"], card["first_name"], card["phone"], card["address.street"])))
    builder.expect_return(ReturnExpectation("courier_book", 0, "nested",
                                            (card["address.street"],)))
    builder.expect_return(ReturnExpectation(
        "courier_status", 0, "nested",
        (card["address.street"], card["last_name"], card["phone"])))
    return builder.build(BEHAVIOUR)


def _file(ctx: c.Ctx) -> Case:
    """Файл → разбор → карточка → письмо и смс.

    WHY THE PARSER SITS IN THE MIDDLE AND `crm_upsert_contact`'s ECHO DOES NOT.
    The write-back's result is composed from the ARGUMENTS it received, and the
    mock tags such a value only when some seeded row already held it — a contact
    this very call is creating held nothing, so the echo carries no tag and a hop
    declared on it could never be observed. `form_parse` answers out of the
    DOCUMENT row the values came from, so its result is tagged, and the chain's
    transitions (R12 counts `tool` sources only) hang off it.
    """
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    path = f"/mnt/in/anketa-{ctx.index}.txt"
    phone = f"+7{drawn.phone}"
    mail = f"{drawn.email_local}@{drawn.email_domain}"
    iso = iso_date(drawn.dob)
    builder = c.new_builder(ctx, "crm", _FILE_TOOLS,
                            ("file_read", "form_parse", "crm_upsert_contact", "email_send"),
                            identity, f"PHONE:{drawn.phone}",
                            "анкета из файла -> разбор -> карточка -> письмо: значения "
                            "входят документом, выходят шаблоном",
                            (c.DOCUMENT_CLAUSE, f"Анкета клиента лежит в файле {path}."))
    builder.v4.conversation_id = _conversation(ctx)
    document = seeded(builder, "doc-1", "documents", {
        "path": path, "format": "txt", "title": "Анкета клиента",
        "last_name": drawn.person.surname[0], "first_name": drawn.person.given[0],
        "birth_date": iso, "phone": phone, "email": mail,
        "template": ("Заявитель {last_name} {first_name}, {birth_date} года рождения, "
                     "телефон {phone}, почта {email}.")}, {
        "last_name": ("NAME", identity, pools.Rendered(
            drawn.person.surname[0], drawn.person.surname[0], False,
            {"surname": drawn.person.surname[0], "gender": drawn.person.gender})),
        "first_name": ("NAME", identity, pools.Rendered(
            drawn.person.given[0], drawn.person.given[0], False,
            {"given": drawn.person.given[0], "gender": drawn.person.gender})),
        "birth_date": ("DOB", identity, pools.Rendered(iso, iso, False, {"iso": iso})),
        "phone": ("PHONE", identity, pools.Rendered(phone, phone, False,
                                                    {"digits": drawn.phone})),
        "email": ("EMAIL", identity, pools.Rendered(mail, mail, False,
                                                    {"local": drawn.email_local,
                                                     "domain": drawn.email_domain})),
    })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("оформите клиента по анкете к заказу номер")
    draft.plain_value("order", c.order_number(ctx), "order_number",
                      "номер заказа — не персональные данные, обязан уцелеть")
    draft.say("и подтвердите ему письмом")
    draft.punct(".")
    turn, _ = told(builder, draft, {})
    builder.v4.must_contain = (drawn.person.surname[0],)

    builder.declare_hop(_document_hop(document["last_name"], 0, turn, "file_read", "text"))
    builder.declare_hop(_document_hop(document["first_name"], 1, turn, "file_read", "text"))
    builder.declare_hop(_document_hop(document["birth_date"], 2, turn, "file_read", "text"))
    builder.declare_hop(_document_hop(document["phone"], 3, turn, "file_read", "text"))
    builder.declare_hop(_document_hop(document["email"], 4, turn, "file_read", "text"))
    builder.declare_hop(arg_hop(document["last_name"], 5, turn, "form_parse", 0, "text", 0, ""))
    builder.declare_hop(arg_hop(document["birth_date"], 6, turn, "form_parse", 0, "text", 2, ""))
    builder.declare_hop(tool_hop(document["last_name"], 7, turn, "form_parse", 0,
                                 "fields.person.last_name"))
    builder.declare_hop(tool_hop(document["first_name"], 8, turn, "form_parse", 0,
                                 "fields.person.first_name"))
    builder.declare_hop(tool_hop(document["birth_date"], 9, turn, "form_parse", 0,
                                 "fields.birth_date"))
    builder.declare_hop(arg_hop(document["last_name"], 10, turn, "crm_upsert_contact", 0,
                                "contact.last_name", 7, ""))
    builder.declare_hop(arg_hop(document["first_name"], 11, turn, "crm_upsert_contact", 0,
                                "contact.first_name", 8, ""))
    builder.declare_hop(arg_hop(document["birth_date"], 12, turn, "crm_upsert_contact", 0,
                                "contact.birth_date", 9, ""))
    builder.declare_hop(arg_hop(document["phone"], 13, turn, "crm_upsert_contact", 0,
                                "contact.phone", 3, ""))
    builder.declare_hop(arg_hop(document["email"], 14, turn, "email_send", 0, "to", 4, ""))
    builder.declare_hop(arg_hop(document["last_name"], 15, turn, "email_send", 0, "body", 7, ""))
    builder.declare_hop(answer_hop(document["last_name"], 16, turn, 7, False))
    builder.declare_hop(answer_hop(document["phone"], 17, turn, 3, True))
    builder.expect_return(ReturnExpectation(
        "file_read", 0, "free_text",
        (document["last_name"], document["first_name"], document["birth_date"],
         document["phone"], document["email"])))
    builder.expect_return(ReturnExpectation(
        "form_parse", 0, "nested",
        (document["last_name"], document["first_name"], document["birth_date"])))
    return builder.build(BEHAVIOUR)


def _form(ctx: c.Ctx) -> Case:
    """Документ → разбор анкеты → карточка. The parser answers in TYPED fields —
    an ISO date, a СНИЛС with ПФР separators, an address split by role — none of
    which the document's own prose used."""
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    digits = pools.snils_digits(ctx.rng)
    series, number = pools.passport_digits(ctx.rng)
    spaced = spaced_snils(digits)
    iso = iso_date(drawn.dob)
    street = drawn.address.street
    builder = c.new_builder(ctx, "crm", _FORM_TOOLS,
                            ("doc_retrieve", "form_parse", "crm_upsert_contact"), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "документ -> разбор анкеты -> карточка: парсер отдаёт поля в "
                            "нотации, которой в самой анкете не было",
                            (c.DOCUMENT_CLAUSE, "Анкета лежит в документе doc-1."))
    builder.v4.conversation_id = _conversation(ctx)
    document = seeded(builder, "doc-1", "documents", {
        "path": f"/mnt/in/form-{ctx.index}.docx", "format": "form", "title": "Анкета",
        "last_name": drawn.person.surname[0], "first_name": drawn.person.given[0],
        "middle_name": drawn.person.patronymic[0], "birth_date": iso,
        "passport_series": series, "passport_number": number, "snils": spaced,
        "city": city.capitalize(), "street": street.capitalize(),
        "house": str(drawn.address.house), "flat": str(drawn.address.flat or ""),
        "template": ("Анкета. Фамилия {last_name}, имя {first_name}, отчество {middle_name}, "
                     "дата рождения {birth_date}, паспорт {passport_series} {passport_number}, "
                     "СНИЛС {snils}, адрес {city}, {street}, {house}.")}, {
        "last_name": ("NAME", identity, pools.Rendered(
            drawn.person.surname[0], drawn.person.surname[0], False,
            {"surname": drawn.person.surname[0], "gender": drawn.person.gender})),
        "first_name": ("NAME", identity, pools.Rendered(
            drawn.person.given[0], drawn.person.given[0], False,
            {"given": drawn.person.given[0], "gender": drawn.person.gender})),
        "birth_date": ("DOB", identity, pools.Rendered(iso, iso, False, {"iso": iso})),
        "snils": ("SNILS", identity, pools.Rendered(spaced, spaced, False, {"digits": digits})),
        "street": ("LOC", f"{identity}.home", pools.Rendered(
            street.capitalize(), street.capitalize(), False, {"street": street})),
    })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("разберите анкету и заведите карточку заказ номер")
    draft.plain_value("order", c.order_number(ctx), "order_number",
                      "номер заказа — не персональные данные, обязан уцелеть")
    draft.punct(".")
    turn, _ = told(builder, draft, {})
    builder.v4.must_contain = (drawn.person.surname[0],)

    builder.declare_hop(_document_hop(document["last_name"], 0, turn, "doc_retrieve", "body"))
    builder.declare_hop(_document_hop(document["birth_date"], 1, turn, "doc_retrieve", "body"))
    builder.declare_hop(_document_hop(document["snils"], 2, turn, "doc_retrieve", "body"))
    builder.declare_hop(_document_hop(document["street"], 3, turn, "doc_retrieve", "body"))
    builder.declare_hop(arg_hop(document["last_name"], 4, turn, "form_parse", 0, "text", 0, ""))
    builder.declare_hop(arg_hop(document["birth_date"], 5, turn, "form_parse", 0, "text", 1, ""))
    builder.declare_hop(arg_hop(document["snils"], 6, turn, "form_parse", 0, "text", 2, ""))
    builder.declare_hop(arg_hop(document["street"], 7, turn, "form_parse", 0, "text", 3, ""))
    builder.declare_hop(tool_hop(document["last_name"], 8, turn, "form_parse", 0,
                                 "fields.person.last_name"))
    builder.declare_hop(tool_hop(document["birth_date"], 9, turn, "form_parse", 0,
                                 "fields.birth_date"))
    builder.declare_hop(tool_hop(document["snils"], 10, turn, "form_parse", 0, "fields.snils"))
    builder.declare_hop(tool_hop(document["street"], 11, turn, "form_parse", 0,
                                 "fields.address.street"))
    builder.declare_hop(arg_hop(document["last_name"], 12, turn, "crm_upsert_contact", 0,
                                "contact.last_name", 8, ""))
    builder.declare_hop(arg_hop(document["birth_date"], 13, turn, "crm_upsert_contact", 0,
                                "contact.birth_date", 9, ""))
    builder.declare_hop(arg_hop(document["street"], 14, turn, "crm_upsert_contact", 0,
                                "contact.address.street", 11, ""))
    builder.declare_hop(answer_hop(document["last_name"], 15, turn, 8, False))
    builder.declare_hop(answer_hop(document["snils"], 16, turn, 10, True))
    builder.expect_return(ReturnExpectation(
        "doc_retrieve", 0, "free_text",
        (document["last_name"], document["first_name"], document["birth_date"],
         document["snils"], document["street"])))
    builder.expect_return(ReturnExpectation(
        "form_parse", 0, "nested",
        (document["last_name"], document["first_name"], document["birth_date"],
         document["snils"], document["street"])))
    return builder.build(BEHAVIOUR)


def _document_hop(item_id: str, index: int, turn: int, tool: str, path: str) -> Hop:
    """An IN hop whose owner is the DOCUMENT, not the tool that opened it.

    The form the substitute had to mirror belongs to the file — a CSV cell, a
    filled form line, a scanned page — and `contracts.IN_OWNERS` separates
    `document` from `tool` for that reason. Written here rather than in `plan_a`
    because these two families are the only ones of this half that read a file,
    and a helper used twice in one module is a helper that belongs to it.
    """
    return Hop(kind="IN", owner="document", item_id=item_id, hop_index=index, turn=turn,
               tool_name=tool, call_ordinal=0, parallel_group="", source_hop=-1,
               path=path, optional=False)
