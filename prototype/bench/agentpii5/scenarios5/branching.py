"""`branching` — found → update, not found → create; the rule is in the prompt.

The family where the SUBSTITUTE decides what the agent does. Every other family
asks whether a value survived a crossing; this one asks whether the agent's
CONTROL FLOW on substituted data equals its control flow on the real thing. If
the gateway hands the model a fake phone that the customer's own CRM has never
seen, the probe comes back empty and the agent creates a second card for a client
who already exists — a failure with no wrong value anywhere in it, which is why
the v4 levels (calls, fields, state) are what score it and the hop model adds
nothing per crossing.

AN EMPTY PROBE IS NOT THE SAME THING AS A CASE WITHOUT A RESULT, and three of
the four shapes here are built so that it is not. `BranchSpec.seed_present` must
agree with whether the case carries seed records at all (R14), so a case whose
record is genuinely absent has no IN/tool hop and no result — an `empty` answer
carries nothing and a hop on an absent record would score the gateway on a
crossing that cannot happen. But the commonest real rule does not stop at the
first miss: «не нашёл по телефону — ищи по фамилии». `_crm_second_probe` is that
rule — the first probe comes back `empty` (the number the caller has just moved
to is in no card), the second finds the card, and the case both KEEPS the `empty`
form and reaches a result. `_bank_absent` is the shape where the client really is
not there, and it is what keeps the `else` branch measured.

TWO VERTICALS SO THE RULE IS NOT ONE PROMPT'S WORDING. CRM (find by phone or
surname → update or open a ticket) and bank (find by ИНН → statement or open a
ticket); the else branch is a ticket in both, whose subject and text are SUMMARY
hops carrying the customer's own values.

THE RULE TRAVELS IN THE PROMPT, NOT IN A FIELD NOBODY READS. Every rule here is
passed to `new_builder` as an `extras` clause, because that is what
`system_prompt_v5` writes into message 0 — the text the gateway masks and the
agent receives. v4's `CaseBuilder.rule` is consumed in `__post_init__`, so a
family assigning `builder.v4.rule` AFTERWARDS states a rule the agent is never
told, and a branch nobody was asked to take is not a branch the arms can differ
on.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import BranchSpec, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, full_name, grouped_card,
                                               minted, seeded, told, tool_hop, user_hop)

BEHAVIOUR: str = "branching"
TOOLS: tuple[str, ...] = (
    "crm_find_contact", "crm_upsert_contact", "bank_client_find", "account_statement",
    "ticket_create", "notify_sms")
_CRM_TOOLS: tuple[str, ...] = ("crm_find_contact", "crm_upsert_contact", "ticket_create",
                               "notify_sms")
_BANK_TOOLS: tuple[str, ...] = ("bank_client_find", "account_statement", "ticket_create",
                                "notify_sms")
# The rule the agent must apply, once per vertical, in the SYSTEM prompt — where
# a customer puts one, and where the masking can rewrite it.
_BANK_RULE: str = ("Сначала найди клиента банка по ИНН: если он есть — покажи выписку, "
                   "если нет — заведи заявку на подключение.")
# The two-step read: a card is looked up by the number the caller is calling
# from, and a miss is a reason to try the surname, not a reason to open a ticket.
# Written as its own clause rather than appended to `BRANCH_CLAUSE`, because it
# replaces the first step of that rule instead of adding to it.
_CRM_RETRY_RULE: str = ("Найди карточку клиента по телефону; если по телефону не нашлась — "
                        "поищи по фамилии. Нашёл — обнови карточку, не нашёл — заведи заявку.")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Four shapes by index modulo four: crm found, crm found on the SECOND
    probe, bank found, bank absent. Over fifty cases that is a quarter each
    exactly — the split has to be a property of the plan, not of a draw, or the
    family would measure a different question from seed to seed.

    THREE SHAPES OUT OF FOUR REACH A RESULT and one does not, which is the
    corpus-wide «≥75 % with a result» rule applied inside the family rather
    than paid for by another one. The `empty` form keeps two shapes out of four
    (`_crm_second_probe`'s first probe and `_bank_absent`'s only probe), so
    nothing about the empty answer is measured less than before.
    """
    builders = (_crm_found, _crm_second_probe, _bank_found, _bank_absent)
    return builders[ctx.index % 4](ctx)


def _conversation(ctx: c.Ctx) -> str:
    return f"conv-branch-{ctx.index}" if ctx.index % 5 == 0 else ""


def _fresh_number(ctx: c.Ctx, drawn: c.Drawn) -> str:
    """The number the caller has just moved to — one the card cannot hold.

    A SECOND DRAW FROM `ctx.rng` WOULD SHIFT EVERY LATER DRAW of the case, so the
    seeded person would change with the addition of this one value and the family
    would be a different corpus from the same seed; the stream is its own, as it
    is for v4's rare stratum and for `parallel`'s fan-out.

    DISTINCTNESS FROM THE CARD'S OWN NUMBER IS CHECKED, NOT ASSUMED. An equal
    pair would make the FIRST probe find the record, and the case would declare
    an `empty` result the backend never produces — a corpus defect that reads in
    the report as a gateway miss.
    """
    stream = c.ctx_for(f"{BEHAVIOUR}:number", ctx.seed, ctx.index, ctx.register).rng
    for _ in range(50):
        digits = pools.mobile_digits(stream)
        if digits != drawn.phone:
            return digits
    raise pools.BuildError(f"{ctx.index}: no mobile number unlike {drawn.phone} in 50 draws")


def _crm_found(ctx: c.Ctx) -> Case:
    """The card exists: probe, then update it with the address the caller gave."""
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "crm", _CRM_TOOLS,
                            ("crm_find_contact", "crm_upsert_contact"), identity,
                            f"PHONE:{drawn.phone}",
                            "карточка есть: проба находит её, действие — обновление, "
                            "а не заведение второй", (c.BRANCH_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    before = len(builder.v4.pii)
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    card = {item.where.path: item.id for item in minted(builder, before)}
    builder.set_branch(BranchSpec("crm_find_contact", True, "crm_upsert_contact",
                                  "ticket_create"))

    new_address = pools.draw_address(ctx.rng, city, True, False, True)
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это клиент телефон")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("новый адрес")
    draft.value("addr", c.address(ctx, new_address))
    draft.punct(".")
    turn, said = told(builder, draft, {
        "ph": ("PHONE", identity, "required", False),
        "addr": ("LOC", f"{identity}.new", "required", False)})
    builder.v4.must_contain = (new_address.street,)

    builder.declare_hop(user_hop(said["ph"], 0, turn))
    builder.declare_hop(user_hop(said["addr"], 1, turn))
    builder.declare_hop(arg_hop(said["ph"], 2, turn, "crm_find_contact", 0, "query.phone", 0, ""))
    builder.declare_hop(tool_hop(card["last_name"], 3, turn, "crm_find_contact", 0,
                                 "contacts[].last_name"))
    builder.declare_hop(tool_hop(card["birth_date"], 4, turn, "crm_find_contact", 0,
                                 "contacts[].birth_date"))
    builder.declare_hop(arg_hop(said["addr"], 5, turn, "crm_upsert_contact", 0,
                                "contact.address.street", 1, ""))
    builder.declare_hop(arg_hop(said["ph"], 6, turn, "crm_upsert_contact", 0,
                                "contact.phone", 0, ""))
    # THE UPDATE ANSWERS WITH THE CARD, AND UNTIL NOW NOTHING READ IT. amoCRM
    # returns the merged contact, `mock._enrich` renders it off the STORED row —
    # so these are the CRM's own notations coming back, the second IN/tool hop
    # of the branch and the only one on the acting leg. The three leaves were
    # declared in `result_pii` and promised by no return form, which is why
    # deleting them reddened nothing (V06); declaring the hops is what makes the
    # column a measurement. THE «FOUND» BRANCH IS THE ONLY PLACE THIS CAN LIVE:
    # on the «not found» leg the update opens a NEW card, whose leaves carry no
    # seeded item and would be a hop nobody can observe.
    builder.declare_hop(tool_hop(card["last_name"], 7, turn, "crm_upsert_contact", 0,
                                 "contact.last_name"))
    builder.declare_hop(tool_hop(card["first_name"], 8, turn, "crm_upsert_contact", 0,
                                 "contact.first_name"))
    builder.declare_hop(tool_hop(card["phone"], 9, turn, "crm_upsert_contact", 0,
                                 "contact.phone"))
    builder.declare_hop(answer_hop(card["last_name"], 10, turn, 3, True))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list",
        (card["last_name"], card["first_name"], card["phone"], card["birth_date"],
         card["address.street"])))
    builder.expect_return(ReturnExpectation(
        "crm_upsert_contact", 0, "single",
        (card["last_name"], card["first_name"], card["phone"])))
    return builder.build(BEHAVIOUR)


def _crm_second_probe(ctx: c.Ctx) -> Case:
    """The card is there, but not under the number the caller has just moved to:
    the first probe answers `empty`, the second finds it by surname.

    THE PROBE THAT FINDS NOTHING IS STILL THE PROBE THIS FAMILY IS ABOUT. The
    agent's control flow on substituted data is what is scored, and the flow here
    has one more decision in it than «found / not found»: a gateway that hands the
    model a fake number produces the same `empty` a genuinely new number does, so
    the first call separates nothing on its own and only the SECOND one does. A
    substituted surname misses that one too, and the agent opens a ticket for a
    client it already has — the failure with no wrong value anywhere in it, now
    reachable with a result to compare against.

    THE OLD NUMBER COMES BACK AND THE NEW ONE GOES OUT, both PHONE, both this
    person's. That pair is why the update is declared on `contact.phone`: an arm
    that writes the CARD's own number back into the card has done nothing, and
    only a case carrying both values can tell the two apart.

    THE CALLER NAMES A SURNAME AND NOTHING ELSE OF THE NAME, because
    `crm_find_contact` matches `query.last_name` against the card's `last_name`
    column: a «фамилия имя» item would carry a canonical no column holds, the
    second probe would answer `empty` too, and the case would declare a result
    the backend cannot produce.
    """
    identity = f"p{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "crm", _CRM_TOOLS,
                            ("crm_find_contact", "crm_upsert_contact"), identity,
                            f"PHONE:{drawn.phone}",
                            "по телефону не нашлось, по фамилии нашлось: пустая первая проба "
                            "не повод заводить вторую карточку", (_CRM_RETRY_RULE,))
    builder.v4.conversation_id = _conversation(ctx)
    before = len(builder.v4.pii)
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    card = {item.where.path: item.id for item in minted(builder, before)}
    builder.set_branch(BranchSpec("crm_find_contact", True, "crm_upsert_contact",
                                  "ticket_create"))

    new_phone = _fresh_number(ctx, drawn)
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это")
    draft.value("name", c.name(ctx, drawn.person, ("surname",)))
    draft.say("у меня новый номер")
    draft.value("ph", c.phone(ctx, new_phone))
    draft.say("поменяйте его в карточке")
    draft.punct(".")
    # THE NEW NUMBER IS ITS OWN IDENTITY, as the new address is in `_crm_found`.
    # The card already holds a PHONE of `identity`; filing the caller's new one
    # under the same identity would put two different strings behind one question
    # («did this person's phone survive»), and a metric cannot answer it twice.
    turn, said = told(builder, draft, {"name": ("NAME", identity, "required", False),
                                       "ph": ("PHONE", f"{identity}.new", "required", False)})

    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    builder.declare_hop(arg_hop(said["ph"], 2, turn, "crm_find_contact", 0, "query.phone", 1, ""))
    builder.declare_hop(arg_hop(said["name"], 3, turn, "crm_find_contact", 1, "query.last_name",
                                0, ""))
    builder.declare_hop(tool_hop(card["last_name"], 4, turn, "crm_find_contact", 1,
                                 "contacts[].last_name"))
    builder.declare_hop(tool_hop(card["phone"], 5, turn, "crm_find_contact", 1,
                                 "contacts[].phone"))
    builder.declare_hop(arg_hop(said["ph"], 6, turn, "crm_upsert_contact", 0, "contact.phone",
                                1, ""))
    builder.declare_hop(answer_hop(card["last_name"], 7, turn, 4, True))
    builder.expect_return(ReturnExpectation("crm_find_contact", 0, "empty", ()))
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 1, "list",
        (card["last_name"], card["first_name"], card["phone"], card["email"],
         card["birth_date"], card["address.street"])))
    return builder.build(BEHAVIOUR)


def _bank_row(builder: c.CaseBuilderV5, ctx: c.Ctx, drawn: c.Drawn, inn_digits: str,
              identity: str) -> dict[str, str]:
    card_digits = pools.card_digits(ctx.rng)
    card = grouped_card(card_digits)
    person = full_name(drawn.person)
    return seeded(builder, "bc-1", "bank_clients", {
        "name": person, "inn": inn_digits, "card": card, "phone": f"+7{drawn.phone}",
        "status": "active",
        "rows": [{"date": "2026-08-03", "amount": "1500.00", "currency": "RUB",
                  "description": "Оплата заказа"}]}, {
        "name": ("NAME", identity, pools.Rendered(person, person, False,
                                                  {"surname": drawn.person.surname[0],
                                                   "given": drawn.person.given[0],
                                                   "gender": drawn.person.gender})),
        "inn": ("INN", identity, pools.Rendered(inn_digits, inn_digits, False,
                                                {"digits": inn_digits})),
        "card": ("CARD", identity, pools.Rendered(card, card, False, {"digits": card_digits})),
    })


def _bank_found(ctx: c.Ctx) -> Case:
    """The client exists: the branch goes to the statement."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    inn_digits = pools.inn12_digits(ctx.rng)
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS,
                            ("bank_client_find", "account_statement"), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "клиент банка есть: ветка идёт в выписку", (_BANK_RULE,))
    builder.v4.conversation_id = _conversation(ctx)
    row = _bank_row(builder, ctx, drawn, inn_digits, identity)
    builder.set_branch(BranchSpec("bank_client_find", True, "account_statement",
                                  "ticket_create"))

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("инн")
    draft.value("inn", c.inn(ctx, inn_digits))
    draft.say("посмотрите что там по счёту")
    draft.punct(".")
    turn, said = told(builder, draft, {"inn": ("INN", identity, "required", False)})
    builder.v4.must_contain = (full_name(drawn.person),)

    builder.declare_hop(user_hop(said["inn"], 0, turn))
    builder.declare_hop(arg_hop(said["inn"], 1, turn, "bank_client_find", 0, "inn", 0, ""))
    builder.declare_hop(tool_hop(row["name"], 2, turn, "bank_client_find", 0, "client.name"))
    builder.declare_hop(tool_hop(row["card"], 3, turn, "account_statement", 0, "holder.card"))
    builder.declare_hop(answer_hop(row["name"], 4, turn, 2, False))
    builder.declare_hop(answer_hop(row["card"], 5, turn, 3, True))
    builder.expect_return(ReturnExpectation("bank_client_find", 0, "single",
                                            (row["name"], row["inn"], row["card"])))
    builder.expect_return(ReturnExpectation("account_statement", 0, "list",
                                            (row["name"], row["card"])))
    return builder.build(BEHAVIOUR)


def _bank_absent(ctx: c.Ctx) -> Case:
    """No client under that ИНН: the branch goes to a ticket, and the ИНН itself
    rides in its free text."""
    identity = f"p{ctx.index}"
    drawn = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    inn_digits = pools.inn12_digits(ctx.rng)
    builder = c.new_builder(ctx, "bank", _BANK_TOOLS,
                            ("bank_client_find", "ticket_create"), identity,
                            f"NAME:{full_name(drawn.person)}",
                            "клиента банка нет: ветка идёт в заявку, ИНН уходит в её "
                            "свободный текст", (_BANK_RULE,))
    builder.v4.conversation_id = _conversation(ctx)
    builder.set_branch(BranchSpec("bank_client_find", False, "account_statement",
                                  "ticket_create"))

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это")
    draft.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    draft.say("инн")
    draft.value("inn", c.inn(ctx, inn_digits))
    draft.say("хочу подключиться")
    draft.punct(".")
    turn, said = told(builder, draft, {"name": ("NAME", identity, "required", False),
                                       "inn": ("INN", identity, "required", False)})

    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["inn"], 1, turn))
    builder.declare_hop(arg_hop(said["inn"], 2, turn, "bank_client_find", 0, "inn", 1, ""))
    builder.declare_hop(arg_hop(said["name"], 3, turn, "ticket_create", 0, "subject", 0, ""))
    builder.declare_hop(arg_hop(said["inn"], 4, turn, "ticket_create", 0, "text", 1, ""))
    builder.declare_hop(answer_hop(said["name"], 5, turn, 0, True))
    builder.expect_return(ReturnExpectation("bank_client_find", 0, "empty", ()))
    return builder.build(BEHAVIOUR)
