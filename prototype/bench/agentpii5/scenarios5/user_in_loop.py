"""`user_in_loop` — find, SHOW what was found, wait for «да, это я», then act.

THE FAMILY WHERE THE CONFIRMATION IS THE MEASUREMENT. Everywhere else the agent
reads a value and uses it inside one turn; here the value crosses back to the
CUSTOMER first («нашёл: Петров Пётр, 14.03.1987 — верно?») and then has to
survive a turn of dialogue that does not repeat it before it becomes a tool
argument. Three things can break that no single-turn family can see: the shown
value can come back in a form the customer cannot recognise as their own, the
confirmation can be answered about the wrong record, and the act can be built
out of the substitute the agent still has in its context instead of the value
it was confirmed on.

THE CONFIRMING TURN CARRIES NO VALUE, AND THAT IS RULE R15 RATHER THAN A STYLE.
«да, это я, Петров» would let an agent that lost the record rebuild it from the
message, and the case would score a memory it never tested. The phrase is drawn
from a closed list of confirmations and the validator refuses any case whose
`confirm_phrase` contains an item value.

THE ACT HAPPENS IN THE TURN THE CONFIRMATION OPENED, not in a later one. A hop's
`turn` is the user message that OPENS the turn it happens in, so `confirm_turn`
IS the turn of the act — R15 reads «at or after», and demanding a third user
message would mean writing one that says nothing.

FOUR VERTICALS, AND EACH ONE PUTS THE CONFIRMED VALUE INTO A DIFFERENT KIND OF
CONSUMER: a clinic booking (plain tool arguments), an SMS (a TEMPLATE slot a
human reads), a delivery notification template, and a handover summary. The
owner decides which `form_hOUT` line the hop counts in, so one family covering
four owners is what gives the rarer owners a denominator in a second behaviour
(K13).

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import LoopSpec
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_b import (answer_hop, arg_hop, caller_card, city_for,
                                               conversation_id, find_the_caller, memory_hop,
                                               told, tool_hop, user_hop)

BEHAVIOUR: str = "user_in_loop"
TOOLS: tuple[str, ...] = (
    "crm_find_contact", "clinic_book", "notify_sms", "send_template", "escalate_to_human",
    "appointment_reschedule", "calendar_free")
_CLINIC_TOOLS: tuple[str, ...] = ("crm_find_contact", "clinic_book", "calendar_free",
                                  "appointment_reschedule")
_SMS_TOOLS: tuple[str, ...] = ("crm_find_contact", "notify_sms")
_TEMPLATE_TOOLS: tuple[str, ...] = ("crm_find_contact", "send_template")
_HANDOVER_TOOLS: tuple[str, ...] = ("crm_find_contact", "escalate_to_human",
                                    "ticket_create")

# What the customer says at the confirming turn. Every one of them is a plain
# agreement with NO value in it (R15), and they are literals rather than a
# draw over words because the phrase is also `LoopSpec.confirm_phrase`, which
# the validator compares against every item value of the case.
#
# NOT A COMMA IN ANY OF THEM. v4's register gate refuses sentence punctuation in
# a spoken message — zero of 53 324 measured utterances carry it — and these
# phrases are said in every register, so «да, это я» would make the confirming
# turn illegal in the two registers this family most needs it in.
CONFIRM_PHRASES: tuple[str, ...] = (
    "да это я", "верно действуйте", "всё правильно оформляйте",
    "да всё так продолжайте", "ага это моя карточка")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Four shapes by index modulo four, so the split is a property of the plan
    and not of a draw: ten of each over forty cases, every time."""
    builders = (_clinic, _sms, _template, _handover)
    return builders[ctx.index % 4](ctx)


def _open(ctx: c.Ctx, role: str, tools: tuple[str, ...], reachable: tuple[str, ...],
          note: str) -> tuple[c.CaseBuilderV5, c.Drawn, str, str, dict[str, str]]:
    """The three moves every shape of this family opens with: a builder whose
    prompt carries the confirmation clause, the caller's seeded card, and the
    identity the whole case is about."""
    identity = f"p{ctx.index}"
    city = city_for(ctx)
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, role, tools, reachable, identity, f"PHONE:{drawn.phone}",
                            note, (c.CONFIRM_CLAUSE,))
    builder.v4.conversation_id = conversation_id(BEHAVIOUR, ctx.index)
    card = caller_card(builder, ctx, drawn, city, identity)
    return builder, drawn, identity, city, card


def _ask(builder: c.CaseBuilderV5, ctx: c.Ctx, drawn: c.Drawn, identity: str,
         request: str) -> tuple[int, dict[str, str]]:
    """Turn one: the customer names themselves by phone and asks for something."""
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это")
    draft.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    draft.say("телефон")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say(request)
    draft.punct(".")
    return told(builder, draft, {"name": ("NAME", identity, "required", False),
                                 "ph": ("PHONE", identity, "required", False)})


def _confirm(builder: c.CaseBuilderV5) -> tuple[int, str]:
    """Turn two: the agreement, with nothing in it the agent could re-read."""
    phrase = CONFIRM_PHRASES[builder.ctx.index % len(CONFIRM_PHRASES)]
    draft = builder.draft()
    draft.say(phrase)
    draft.punct(".")
    turn, _said = told(builder, draft, {})
    return turn, phrase


def _clinic(ctx: c.Ctx) -> Case:
    """A booking: the card is read back, confirmed, and becomes the patient of
    `clinic_book` — five plain argument leaves fed by one result."""
    builder, drawn, identity, _city, card = _open(
        ctx, "clinic", _CLINIC_TOOLS, ("crm_find_contact", "clinic_book"),
        "найти карточку, показать её, дождаться подтверждения и записать "
        "подтверждённого пациента")
    ask_turn, said = _ask(builder, ctx, drawn, identity, "запишите меня к врачу")
    builder.declare_hop(user_hop(said["name"], 0, ask_turn))
    builder.declare_hop(user_hop(said["ph"], 1, ask_turn))
    surname_hop, _next = find_the_caller(builder, card, said["ph"], ask_turn, 1)
    birth_hop = surname_hop + 1
    shown = builder.next_hop_index()
    builder.declare_hop(answer_hop(card["last_name"], shown, ask_turn, surname_hop, False))
    builder.declare_hop(answer_hop(card["birth_date"], shown + 1, ask_turn, birth_hop, False))
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    confirm_turn, phrase = _confirm(builder)
    # The value crosses the confirming turn inside the model's context, not
    # inside a message: two IN/memory hops, one per leaf it is about to use.
    remembered = shown + 2
    builder.declare_hop(memory_hop(card["last_name"], remembered, confirm_turn, surname_hop))
    builder.declare_hop(memory_hop(card["birth_date"], remembered + 1, confirm_turn, birth_hop))
    builder.declare_hop(arg_hop(card["last_name"], remembered + 2, confirm_turn, "clinic_book",
                                0, "patient.last_name", remembered, ""))
    builder.declare_hop(arg_hop(card["first_name"], remembered + 3, confirm_turn, "clinic_book",
                                0, "patient.first_name", surname_hop, ""))
    builder.declare_hop(arg_hop(card["birth_date"], remembered + 4, confirm_turn, "clinic_book",
                                0, "patient.birth_date", remembered + 1, ""))
    builder.declare_hop(arg_hop(said["ph"], remembered + 5, confirm_turn, "clinic_book",
                                0, "phone", 1, ""))
    builder.set_loop(LoopSpec("crm_find_contact", ask_turn, confirm_turn, phrase, "clinic_book"))
    return builder.build(BEHAVIOUR)


def _sms(ctx: c.Ctx) -> Case:
    """The confirmed value goes into an SMS the customer will read — a TEMPLATE
    hop, where the agent's own wording decides the form of the value."""
    builder, drawn, identity, _city, card = _open(
        ctx, "delivery", _SMS_TOOLS, ("crm_find_contact", "notify_sms"),
        "показать найденную карточку, дождаться подтверждения и отправить "
        "подтверждённому адресату смс с его же данными")
    ask_turn, said = _ask(builder, ctx, drawn, identity, "пришлите мне смс с подтверждением")
    builder.declare_hop(user_hop(said["name"], 0, ask_turn))
    builder.declare_hop(user_hop(said["ph"], 1, ask_turn))
    surname_hop, _next = find_the_caller(builder, card, said["ph"], ask_turn, 1)
    shown = builder.next_hop_index()
    builder.declare_hop(answer_hop(card["last_name"], shown, ask_turn, surname_hop, False))
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    confirm_turn, phrase = _confirm(builder)
    builder.declare_hop(memory_hop(card["last_name"], shown + 1, confirm_turn, surname_hop))
    builder.declare_hop(arg_hop(said["ph"], shown + 2, confirm_turn, "notify_sms", 0,
                                "number", 1, ""))
    builder.declare_hop(arg_hop(card["last_name"], shown + 3, confirm_turn, "notify_sms", 0,
                                "text", shown + 1, ""))
    builder.set_loop(LoopSpec("crm_find_contact", ask_turn, confirm_turn, phrase, "notify_sms"))
    return builder.build(BEHAVIOUR)


def _template(ctx: c.Ctx) -> Case:
    """A delivery template: three variables of one person, filled after the
    confirmation, in the notation the agent chose for the slot."""
    builder, drawn, identity, _city, card = _open(
        ctx, "delivery", _TEMPLATE_TOOLS, ("crm_find_contact", "send_template"),
        "показать карточку, дождаться подтверждения и заполнить шаблон "
        "уведомления подтверждёнными значениями")
    ask_turn, said = _ask(builder, ctx, drawn, identity,
                          "подтвердите доставку по моей карточке")
    builder.declare_hop(user_hop(said["name"], 0, ask_turn))
    builder.declare_hop(user_hop(said["ph"], 1, ask_turn))
    surname_hop, _next = find_the_caller(builder, card, said["ph"], ask_turn, 1)
    street_hop = builder.next_hop_index()
    builder.declare_hop(tool_hop(card["address.street"], street_hop, ask_turn,
                                 "crm_find_contact", 0, "contacts[].address.street"))
    shown = street_hop + 1
    builder.declare_hop(answer_hop(card["last_name"], shown, ask_turn, surname_hop, False))
    builder.declare_hop(answer_hop(card["address.street"], shown + 1, ask_turn, street_hop,
                                   True))
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    confirm_turn, phrase = _confirm(builder)
    builder.declare_hop(memory_hop(card["address.street"], shown + 2, confirm_turn, street_hop))
    builder.declare_hop(arg_hop(said["ph"], shown + 3, confirm_turn, "send_template", 0,
                                "number", 1, ""))
    builder.declare_hop(arg_hop(card["last_name"], shown + 4, confirm_turn, "send_template", 0,
                                "variables.name", surname_hop, ""))
    builder.declare_hop(arg_hop(card["address.street"], shown + 5, confirm_turn,
                                "send_template", 0, "variables.address", shown + 2, ""))
    builder.set_loop(LoopSpec("crm_find_contact", ask_turn, confirm_turn, phrase,
                              "send_template"))
    return builder.build(BEHAVIOUR)


def _handover(ctx: c.Ctx) -> Case:
    """The confirmed card is retold to a human colleague — SUMMARY hops, where
    the agent writes the value into prose of its own.

    THE TICKET IS HERE BECAUSE A SUMMARY IS NOT AN ARGUMENT. R15 asks for an
    OUT/tool_arg hop at or after the confirming turn, and every leaf of
    `escalate_to_human` that carries a value is a SUMMARY leaf by the closed
    owner table — so a handover built out of that tool alone declares the act
    the rule is looking for and the rule cannot see it. The ticket carries the
    same confirmation in a typed `phone` field beside its free text, which is
    what a real handover does anyway: a queue entry and a record to call back.
    """
    builder, drawn, identity, _city, card = _open(
        ctx, "callcenter", _HANDOVER_TOOLS,
        ("crm_find_contact", "escalate_to_human", "ticket_create"),
        "показать карточку, дождаться подтверждения и передать подтверждённые "
        "данные живому оператору сводкой и заявкой")
    ask_turn, said = _ask(builder, ctx, drawn, identity, "переключите меня на оператора")
    builder.declare_hop(user_hop(said["name"], 0, ask_turn))
    builder.declare_hop(user_hop(said["ph"], 1, ask_turn))
    surname_hop, _next = find_the_caller(builder, card, said["ph"], ask_turn, 1)
    birth_hop = surname_hop + 1
    shown = builder.next_hop_index()
    builder.declare_hop(answer_hop(card["last_name"], shown, ask_turn, surname_hop, False))
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    confirm_turn, phrase = _confirm(builder)
    builder.declare_hop(memory_hop(card["last_name"], shown + 1, confirm_turn, surname_hop))
    builder.declare_hop(memory_hop(card["birth_date"], shown + 2, confirm_turn, birth_hop))
    builder.declare_hop(arg_hop(card["last_name"], shown + 3, confirm_turn,
                                "escalate_to_human", 0, "summary", shown + 1, ""))
    builder.declare_hop(arg_hop(card["birth_date"], shown + 4, confirm_turn,
                                "escalate_to_human", 0, "summary", shown + 2, ""))
    builder.declare_hop(arg_hop(said["ph"], shown + 5, confirm_turn, "ticket_create", 0,
                                "phone", 1, ""))
    builder.declare_hop(arg_hop(card["last_name"], shown + 6, confirm_turn, "ticket_create", 0,
                                "subject", shown + 1, ""))
    builder.set_loop(LoopSpec("crm_find_contact", ask_turn, confirm_turn, phrase,
                              "ticket_create"))
    return builder.build(BEHAVIOUR)


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.user_in_loop` — build and report."""
    cases = build(4, 40)
    print(f"{BEHAVIOUR}: {len(cases)} cases, "
          f"{sum(1 for case in cases if case.has_result)} with a result")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
