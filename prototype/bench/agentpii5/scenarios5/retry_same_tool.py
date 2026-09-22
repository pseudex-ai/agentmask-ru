"""`retry_same_tool` — the service refuses the FORM, and the agent writes it again.

A real API answers a badly shaped field by quoting it back: ЮKassa returns
`invalid_request` with the offending parameter in the message, the ГИБДД service
names the plate it could not read, the ПФР names the СНИЛС whose checksum did
not close, an SMTP relay names the address it rejected. That reply is a tool
RESULT carrying a real personal value in free text — the IN hop the engine is
weakest at — and the agent's answer to it is a SECOND call of the same tool with
the same datum written another way. Three things are measured here and nowhere
else: the form of the substitute on EVERY OUT argument (not just the first), the
form of the value inside an error body on the way IN, and whether the two
attempts carried the SAME substitute.

THE REFUSAL IS SCRIPTED, AND THAT IS THE WHOLE POINT. A retry that depends on a
live agent making a mistake has an unmeasured denominator: the cases where it
did not err are silently dropped and the family measures whatever the model's
luck was that night. `ForcedError` makes the first call of the named tool fail
whatever the arguments were, so every case of this family provokes exactly one
retry and the denominator is 120.

WHY THE ECHO HOP NAMES THE SEEDED ITEM AND NOT THE CUSTOMER'S. The value in the
error body is the one the customer dictated, and it is also the one the
customer's own system holds — the same string, two items. Rule R05 requires an
IN/tool hop to name an item with a SEED locus, because a tool returns what a
backend holds; so the hop (and the `ForcedError`) name the seeded item, whose
canonical is byte-identical. Naming the message item would describe a result
that came out of a message, which no API does.

WHY THESE FOUR VERTICALS AND NOT THE OBVIOUS ONES. This family needs a READ
whose result is a BACKEND ROW: `courier_book` and `clinic_book` are writes, their
result echoes the arguments, and the only items it could carry are the customer's
own message items — which R05 refuses for an IN/tool hop. Messaging is excluded
for a second reason: an e-mail address cannot be written in either speech
register (`voice_raw` forbids the digits of its local part, `voice_itn` forbids
the dot of its domain — both are measured properties of real speech, not style),
so a mail family would have to drop the 45% of the corpus that is voice and the
register mix would stop being a measurement. Bank, government twice (plate and
СНИЛС) and calendar give four verticals that every register can carry; delivery
rides in `sequential_chain` and `fanout_pick`, messaging in `parallel` and
`sequential_chain`, where the value never has to be dictated.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ForcedError, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, full_name, grouped_card,
                                               iso_date, seeded, spaced_snils, told,
                                               tool_hop, user_hop)

BEHAVIOUR: str = "retry_same_tool"
# The union of what the four verticals offer; each case offers its own slice,
# because a gov case holding an SMTP tool would tell the model something about
# the corpus rather than about the customer.
TOOLS: tuple[str, ...] = (
    "bank_client_find", "account_statement", "vehicle_check", "snils_verify",
    "calendar_free", "callback_schedule", "ticket_create", "notify_sms")
_BANK_TOOLS: tuple[str, ...] = ("bank_client_find", "account_statement", "notify_sms")
_PLATE_TOOLS: tuple[str, ...] = ("vehicle_check", "ticket_create", "notify_sms")
_SNILS_TOOLS: tuple[str, ...] = ("snils_verify", "ticket_create", "notify_sms")
_SLOT_TOOLS: tuple[str, ...] = ("calendar_free", "callback_schedule", "notify_sms")
# The wording of each refusal mirrors the real service's own, because the
# message is what the model reads and a house style would teach it a pattern
# that no customer's API produces.
_BANK_MESSAGE: str = ("invalid_request: параметр inn «{value}» не прошёл проверку, "
                      "ожидается 10 или 12 цифр без пробелов")
_PLATE_MESSAGE: str = ("номер {value} не найден в формате ГОСТ Р 50577, "
                       "передайте серию и регион кириллицей без пробелов")
_SNILS_MESSAGE: str = ("СНИЛС {value} не прошёл проверку контрольной суммы ПФР, "
                       "передайте одиннадцать цифр")
_SLOT_MESSAGE: str = ("сотрудник {value} не найден в расписании, "
                      "передайте фамилию и имя как в карточке")
# The date of the requested slot, per register. NO DOTTED FORM ANYWHERE: a dot is
# sentence punctuation, which `voice_raw` and `voice_itn` both refuse, and a
# family whose filler decides its register is a family that cannot be built.
_SLOT_DAY: tuple[tuple[str, str], ...] = (
    ("voice_raw", "пятого сентября"), ("voice_itn", "5 сентября"), ("chat", "5 сентября"),
    ("sloppy", "5 сентября"), ("clean", "5 сентября"))


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Four verticals, one per index modulo four, so every register mix reaches
    every vertical instead of the split being drawn and drifting."""
    if ctx.index % 4 == 0:
        return _bank(ctx)
    if ctx.index % 4 == 1:
        return _plate(ctx)
    if ctx.index % 4 == 2:
        return _snils(ctx)
    return _slots(ctx)


def _conversation(ctx: c.Ctx) -> str:
    """An explicit id on a third of the cases: the corpus needs both explicit
    and derived conversation identities (K09), and a family that gave every case
    one would leave the derived path unmeasured."""
    return f"conv-retry-{ctx.index}" if ctx.index % 3 == 0 else ""


def _bank(ctx: c.Ctx) -> Case:
    """ЮKassa-shaped: the ИНН is refused for its shape, then accepted."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    inn_digits = pools.inn12_digits(ctx.rng)
    card_digits = pools.card_digits(ctx.rng)
    card = grouped_card(card_digits)
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS, ("bank_client_find",), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "инн отказан по форме, повторный вызов принят; карта приходит "
                            "группами — нотация, которой не даёт ни один регистр речи",
                            (c.RETRY_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "bc-1", "bank_clients", {
        "name": full_name(drawn.person), "inn": inn_digits, "card": card,
        "phone": f"+7{drawn.phone}", "status": "active",
        "rows": [{"date": "2026-08-03", "amount": "1500.00", "currency": "RUB",
                  "description": "Оплата заказа"}]}, {
        "name": ("NAME", identity, pools.Rendered(
            full_name(drawn.person), full_name(drawn.person), False,
            {"surname": drawn.person.surname[0], "given": drawn.person.given[0],
             "gender": drawn.person.gender})),
        "inn": ("INN", identity, pools.Rendered(inn_digits, inn_digits, False,
                                                {"digits": inn_digits})),
        "card": ("CARD", identity, pools.Rendered(card, card, False,
                                                  {"digits": card_digits})),
        "phone": ("PHONE", identity, pools.Rendered(f"+7{drawn.phone}", f"+7{drawn.phone}",
                                                    False, {"digits": drawn.phone})),
    })

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("проверьте клиента по инн")
    draft.value("inn", c.inn(ctx, inn_digits))
    draft.say("и скажите какая карта у него привязана")
    draft.punct(".")
    turn, said = told(builder, draft, {"inn": ("INN", identity, "required", False)})
    builder.v4.must_contain = (card,)
    builder.force_error(ForcedError("bank_client_find", 0, "invalid_request",
                                    row["inn"], _BANK_MESSAGE))

    builder.declare_hop(user_hop(said["inn"], 0, turn))
    builder.declare_hop(arg_hop(said["inn"], 1, turn, "bank_client_find", 0, "inn", 0, ""))
    builder.declare_hop(tool_hop(row["inn"], 2, turn, "bank_client_find", 0, "error.message"))
    # THE SECOND ATTEMPT SOURCES THE CUSTOMER, NOT THE ECHO. What the agent
    # rewrites is the value it was given; sourcing the echo would say the form
    # to mirror is the error body's, and then a service that quotes a value back
    # in ITS notation would be scored as the owner of the retry's form.
    builder.declare_hop(arg_hop(said["inn"], 3, turn, "bank_client_find", 1, "inn", 0, ""))
    builder.declare_hop(tool_hop(row["card"], 4, turn, "bank_client_find", 1, "client.card"))
    builder.declare_hop(tool_hop(row["name"], 5, turn, "bank_client_find", 1, "client.name"))
    builder.declare_hop(answer_hop(row["card"], 6, turn, 4, False))
    builder.declare_hop(answer_hop(row["name"], 7, turn, 5, True))
    builder.expect_return(ReturnExpectation("bank_client_find", 1, "single",
                                            (row["name"], row["inn"], row["card"])))
    return builder.build(BEHAVIOUR)


def _plate(ctx: c.Ctx) -> Case:
    """ГИБДД-shaped: the plate is refused for its format, then accepted."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    canonical = c.plate_text(ctx.rng)
    builder = c.new_builder(ctx, "gov", _PLATE_TOOLS, ("vehicle_check",), identity,
                            f"PLATE:{canonical}",
                            "госномер отказан по формату, повторный вызов принят; "
                            "владелец приходит из реестра",
                            (c.RETRY_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "veh-1", "vehicles", {
        "plate": canonical, "model": ctx.rng.choice(("Kia Rio", "Lada Vesta", "Hyundai Solaris")),
        "year": ctx.rng.choice(("2016", "2019", "2021")),
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
    draft.say(c.opener(ctx)).say("пробейте машину номер")
    draft.value("plate", c.plate(ctx, canonical))
    draft.say("скажите кто сейчас владелец")
    draft.punct(".")
    turn, said = told(builder, draft, {"plate": ("PLATE", identity, "required", False)})
    builder.v4.must_contain = (drawn.person.surname[0],)
    builder.force_error(ForcedError("vehicle_check", 0, "plate_format",
                                    row["plate"], _PLATE_MESSAGE))

    builder.declare_hop(user_hop(said["plate"], 0, turn))
    builder.declare_hop(arg_hop(said["plate"], 1, turn, "vehicle_check", 0, "plate", 0, ""))
    builder.declare_hop(tool_hop(row["plate"], 2, turn, "vehicle_check", 0, "error.message"))
    builder.declare_hop(arg_hop(said["plate"], 3, turn, "vehicle_check", 1, "plate", 0, ""))
    builder.declare_hop(tool_hop(row["owner.last_name"], 4, turn, "vehicle_check", 1,
                                 "owner.last_name"))
    builder.declare_hop(tool_hop(row["plate"], 5, turn, "vehicle_check", 1, "plate"))
    builder.declare_hop(answer_hop(row["owner.last_name"], 6, turn, 4, False))
    builder.declare_hop(answer_hop(row["plate"], 7, turn, 5, True))
    builder.expect_return(ReturnExpectation(
        "vehicle_check", 1, "single",
        (row["plate"], row["owner.last_name"], row["owner.first_name"])))
    return builder.build(BEHAVIOUR)


def _snils(ctx: c.Ctx) -> Case:
    """ПФР-shaped: the checksum is refused, then the record comes back with the
    separators and an ISO birth date — two notations no caller dictates."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    digits = pools.snils_digits(ctx.rng)
    spaced = spaced_snils(digits)
    iso = iso_date(drawn.dob)
    builder = c.new_builder(ctx, "gov", _SNILS_TOOLS, ("snils_verify",), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "снилс отказан по контрольной сумме, повторный вызов принят; "
                            "запись возвращает разделители ПФР и дату в ISO",
                            (c.RETRY_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "sn-1", "snils_records", {
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

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("сверьте снилс")
    draft.value("snils", c.snils(ctx, digits))
    draft.say("чья это запись")
    draft.punct(".")
    turn, said = told(builder, draft, {"snils": ("SNILS", identity, "required", False)})
    builder.v4.must_contain = (drawn.person.surname[0],)
    builder.force_error(ForcedError("snils_verify", 0, "snils_checksum",
                                    row["snils"], _SNILS_MESSAGE))

    builder.declare_hop(user_hop(said["snils"], 0, turn))
    builder.declare_hop(arg_hop(said["snils"], 1, turn, "snils_verify", 0, "snils", 0, ""))
    builder.declare_hop(tool_hop(row["snils"], 2, turn, "snils_verify", 0, "error.message"))
    builder.declare_hop(arg_hop(said["snils"], 3, turn, "snils_verify", 1, "snils", 0, ""))
    builder.declare_hop(tool_hop(row["last_name"], 4, turn, "snils_verify", 1,
                                 "person.last_name"))
    builder.declare_hop(tool_hop(row["birth_date"], 5, turn, "snils_verify", 1,
                                 "person.birth_date"))
    builder.declare_hop(answer_hop(row["last_name"], 6, turn, 4, False))
    builder.declare_hop(answer_hop(row["birth_date"], 7, turn, 5, True))
    builder.expect_return(ReturnExpectation(
        "snils_verify", 1, "single",
        (row["snils"], row["last_name"], row["first_name"], row["birth_date"])))
    return builder.build(BEHAVIOUR)


def _slots(ctx: c.Ctx) -> Case:
    """Calendar-shaped: the scheduler does not know the employee under the name
    the caller used, then the same name is accepted and the record comes back
    with an ISO birth date — a notation no caller dictates.

    THE DAY IS A PLAIN VALUE, not an item: a slot date is a fact about a
    schedule and identifies nobody (`contracts.NEW_TOOL_RESULT_TYPES` files this
    tool's personal data as NAME and DOB for the same reason). It is also the one
    digit-bearing chunk of the message, which is what `voice_itn` is defined by
    carrying.
    """
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    # THE SCHEDULER STORES THE NAME THE CALLER USES, and the row is built from
    # the very `Rendered` the message will carry. A row keyed on the full ФИО
    # while the caller says surname and given name is a lookup that answers
    # `empty` in every register — the case would declare a result nobody can
    # produce, which `validate_v5` cannot see and the backend check does.
    said_name = c.name(ctx, drawn.person, ("surname", "given"))
    person = said_name.canonical
    iso = iso_date(drawn.dob)
    day = dict(_SLOT_DAY)[ctx.register]
    builder = c.new_builder(ctx, "callcenter", _SLOT_TOOLS, ("calendar_free",), identity,
                            f"NAME:{person}",
                            "расписание не узнало сотрудника по имени, повторный вызов принят; "
                            "дата рождения приходит в ISO",
                            (c.RETRY_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    row = seeded(builder, "cal-1", "calendar", {"person": person, "birth_date": iso}, {
        "person": ("NAME", identity, pools.Rendered(person, person, False,
                                                    {"surname": drawn.person.surname[0],
                                                     "given": drawn.person.given[0],
                                                     "gender": drawn.person.gender})),
        "birth_date": ("DOB", identity, pools.Rendered(iso, iso, False, {"iso": iso})),
    })

    draft = builder.draft()
    # NOMINATIVE AFTER A BARE ROLE NOUN («врач Иванов Пётр»), never after «у»:
    # «у» governs the genitive, v4's renderer offers nom/dat/acc only, and a
    # generator that writes broken Russian measures its own mistake.
    draft.say(c.opener(ctx)).say("посмотрите свободные окна врач")
    draft.value("name", said_name)
    draft.say("на")
    draft.plain_value("day", day, "time_of_day",
                      "день приёма — не персональные данные, обязан уцелеть")
    draft.punct(".")
    turn, said = told(builder, draft, {"name": ("NAME", identity, "required", False)})
    builder.force_error(ForcedError("calendar_free", 0, "employee_unknown",
                                    row["person"], _SLOT_MESSAGE))

    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(arg_hop(said["name"], 1, turn, "calendar_free", 0, "person", 0, ""))
    builder.declare_hop(tool_hop(row["person"], 2, turn, "calendar_free", 0, "error.message"))
    builder.declare_hop(arg_hop(said["name"], 3, turn, "calendar_free", 1, "person", 0, ""))
    builder.declare_hop(tool_hop(row["person"], 4, turn, "calendar_free", 1, "person"))
    builder.declare_hop(tool_hop(row["birth_date"], 5, turn, "calendar_free", 1, "birth_date"))
    builder.declare_hop(answer_hop(row["person"], 6, turn, 4, True))
    builder.declare_hop(answer_hop(row["birth_date"], 7, turn, 5, True))
    builder.expect_return(ReturnExpectation("calendar_free", 1, "list",
                                            (row["person"], row["birth_date"])))
    return builder.build(BEHAVIOUR)
