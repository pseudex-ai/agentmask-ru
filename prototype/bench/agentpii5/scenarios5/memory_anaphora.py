"""`memory_anaphora` — «ему», «на тот адрес», «тот же телефон», five turns later.

THE FAMILY THAT MEASURES WHAT THE SUBSTITUTE IS FOR. A tokenizing gateway hands
the model a fake and takes the real value back on the way out; that works turn by
turn without any memory at all. It stops working the moment the customer stops
SAYING the value: at turn five «отправьте ему смс» carries nothing for the
detector to find, and the argument the agent builds is whatever substitute it
still has in its context — so the gateway must resolve a token the current
message never mentions, minted four turns ago, against the right one of the two
people in the dialogue. Every defect of a per-message masker lives here.

THE VALUE IS WRITTEN ONCE AND NEVER AGAIN (R16). A recall turn that repeated the
phone would let a stateless gateway pass by re-detecting it, and the case would
report a memory it never tested — the validator compares by VALUE, not by item
id, because a second writing of one value is a different `PiiItem`.

TWO PEOPLE, NOT ONE, AND THEY ARE DISTINCT IN EVERY INDEXED FIELD. The question
is not «did a value survive» but «did the RIGHT value survive»: a gateway that
resolves «ему» to the other person in the conversation fails in a way that
carries no wrong-looking string anywhere. The mock drops a by-value tag that two
items share, so a shared surname would make the hop unobservable and the defect
invisible — `plan_b.other_person` refuses that draw field by field.

ALL FOUR ANAPHORA KINDS IN EVERY CASE. `pronoun` (ему / ей), `same_phone` (тот
же телефон), `same_address` (на тот адрес) and `same_person` (первому клиенту)
each name a different thing the resolution can key on, and a corpus that carried
them in separate cases would report a family average where four different
mechanisms hide.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import MemorySpec
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_b import (answer_hop, arg_hop, caller_card, city_for,
                                               conversation_id, extra_people, find_the_caller,
                                               memory_hop, told, user_hop)

BEHAVIOUR: str = "memory_anaphora"
TOOLS: tuple[str, ...] = (
    "crm_find_contact", "notify_sms", "courier_book", "escalate_to_human", "crm_add_note",
    "ticket_create", "callback_schedule")
_SMS_TOOLS: tuple[str, ...] = ("crm_find_contact", "notify_sms", "courier_book",
                               "escalate_to_human")
_NOTE_TOOLS: tuple[str, ...] = ("crm_find_contact", "callback_schedule", "courier_book",
                                "crm_add_note")
_TICKET_TOOLS: tuple[str, ...] = ("crm_find_contact", "notify_sms", "courier_book",
                                  "ticket_create")

# How each recall is phrased, by anaphora kind. The phrases carry NO value —
# that is the whole construction — and they live here rather than in the three
# shapes because a phrase written three times is three phrases that drift.
PHONE_RECALL: tuple[str, ...] = (
    "продублируйте мне на тот же телефон", "пришлите на тот же номер",
    "и мне на тот же телефон тоже")
# The address recall carries a PRONOUN for the recipient as well: the courier
# booking needs both the street and the person, and a phrase that named only the
# address would leave `pronoun` filed on a turn that refers to nobody.
ADDRESS_RECALL: tuple[str, ...] = (
    "курьера к нему отправьте на тот адрес", "заберите у неё по тому же адресу",
    "пусть курьер приедет к нему по тому адресу")
PERSON_RECALL: tuple[str, ...] = (
    "и передайте оператору всё по первому клиенту", "по первому получателю передайте оператору",
    "оператору отдайте карточку первого")
# No comma in any of them: v4's register gate refuses sentence punctuation in a
# spoken message, and every phrase above is said in all five registers.


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Three shapes by index modulo three — forty of each over 120 cases. They
    differ only in the CONSUMER of the last recall (an SMS template, a CRM note,
    a support ticket), because that is the axis the owner table reads."""
    shapes = (_sms_shape, _note_shape, _ticket_shape)
    return shapes[ctx.index % 3](ctx)


def _second_leg(ctx: c.Ctx, tools: tuple[str, ...], reachable: tuple[str, ...],
                note: str) -> tuple[c.CaseBuilderV5, c.Drawn, dict[str, str],
                                    dict[str, str], dict[str, str], int, int]:
    """The five turns every shape of this family shares, and the ids they mint.

    Returns the builder, the caller, the caller's seeded card and the
    `{key: item id}` maps of the first two turns, plus the two turn indexes.
    The second person is not returned: every later turn refers to them through
    the item ids of turn two, which is the point of the family.
    """
    identity = f"p{ctx.index}"
    other_identity = f"p{ctx.index}b"
    city = city_for(ctx)
    drawn = c.draw(ctx, city=city)
    second = extra_people(ctx, city, drawn, 1)[0]
    builder = c.new_builder(ctx, "delivery", tools, reachable, identity,
                            f"PHONE:{drawn.phone}", note, (c.MEMORY_CLAUSE,))
    builder.v4.conversation_id = conversation_id(BEHAVIOUR, ctx.index)
    card = caller_card(builder, ctx, drawn, city, identity)

    first = builder.draft()
    first.say(c.opener(ctx)).say("это")
    first.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    first.say("мой телефон")
    first.value("ph", c.phone(ctx, drawn.phone))
    first.punct(".")
    turn_one, said_one = told(builder, first, {
        "name": ("NAME", identity, "required", False),
        "ph": ("PHONE", identity, "required", False)})

    second_draft = builder.draft()
    second_draft.say("посылку примет")
    second_draft.value("name2", c.name(ctx, second.person, ("surname", "given")))
    second_draft.say("адрес")
    second_draft.value("addr2", c.address(ctx, second.address))
    second_draft.punct(".")
    turn_two, said_two = told(builder, second_draft, {
        "name2": ("NAME", other_identity, "required", False),
        "addr2": ("LOC", f"{other_identity}.home", "required", False)})
    return builder, drawn, card, said_one, said_two, turn_one, turn_two


def _recall(builder: c.CaseBuilderV5, phrases: tuple[str, ...]) -> int:
    """One recall turn: a phrase that refers to a value without saying it."""
    draft = builder.draft()
    draft.say(phrases[builder.ctx.index % len(phrases)])
    draft.punct(".")
    turn, _said = told(builder, draft, {})
    return turn


def _declare_memory(builder: c.CaseBuilderV5, said_one: dict[str, str],
                    said_two: dict[str, str], turns: tuple[int, int, int, int, int]) -> None:
    """The four `MemorySpec`s every case of this family carries, one per kind.

    `pronoun` is filed on the SECOND person's name because «ему» in these
    dialogues refers to the recipient, not to the caller — the spec must name
    the item the phrase actually points at, or `memory_consistency` would count
    the wrong substitute.
    """
    turn_one, turn_two, recall_phone, recall_address, recall_person = turns
    builder.remember(MemorySpec(said_one["ph"], turn_one, recall_phone, "same_phone"))
    builder.remember(MemorySpec(said_two["addr2"], turn_two, recall_address, "same_address"))
    builder.remember(MemorySpec(said_two["name2"], turn_two, recall_address, "pronoun"))
    builder.remember(MemorySpec(said_one["name"], turn_one, recall_person, "same_person"))


def _common_hops(builder: c.CaseBuilderV5, card: dict[str, str], said_one: dict[str, str],
                 said_two: dict[str, str], turn_one: int, turn_two: int) -> dict[str, int]:
    """The hops of the first two turns: what the customer said, what the CRM
    answered, and what the agent read back. Returns the hop indexes the recall
    turns chain onto."""
    builder.declare_hop(user_hop(said_one["name"], 0, turn_one))
    builder.declare_hop(user_hop(said_one["ph"], 1, turn_one))
    surname_hop, after_find = find_the_caller(builder, card, said_one["ph"], turn_one, 1)
    builder.declare_hop(user_hop(said_two["name2"], after_find, turn_two))
    builder.declare_hop(user_hop(said_two["addr2"], after_find + 1, turn_two))
    builder.declare_hop(answer_hop(card["last_name"], after_find + 2, turn_one, surname_hop,
                                   True))
    return {"surname": surname_hop, "name2": after_find, "addr2": after_find + 1}


def _courier_leg(builder: c.CaseBuilderV5, said_two: dict[str, str], anchors: dict[str, int],
                 turn: int) -> None:
    """The recalled address and recipient become a courier booking — the value
    the current message never mentions, in four argument leaves."""
    index = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_two["addr2"], index, turn, anchors["addr2"]))
    builder.declare_hop(memory_hop(said_two["name2"], index + 1, turn, anchors["name2"]))
    builder.declare_hop(arg_hop(said_two["addr2"], index + 2, turn, "courier_book", 0,
                                "address.street", index, ""))
    builder.declare_hop(arg_hop(said_two["name2"], index + 3, turn, "courier_book", 0,
                                "contact.name", index + 1, ""))


def _sms_shape(ctx: c.Ctx) -> Case:
    """The last recall goes into an SMS: a TEMPLATE slot the customer reads."""
    builder, drawn, card, said_one, said_two, turn_one, turn_two = _second_leg(
        ctx, _SMS_TOOLS, ("crm_find_contact", "notify_sms", "courier_book"),
        "пять реплик, два человека, четыре отсылки без значения: телефон в смс, "
        "адрес и получатель в курьера, первый клиент — в сводку")
    anchors = _common_hops(builder, card, said_one, said_two, turn_one, turn_two)
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    recall_phone = _recall(builder, PHONE_RECALL)
    index = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_one["ph"], index, recall_phone, 1))
    builder.declare_hop(arg_hop(said_one["ph"], index + 1, recall_phone, "notify_sms", 0,
                                "number", index, ""))
    builder.declare_hop(arg_hop(card["last_name"], index + 2, recall_phone, "notify_sms", 0,
                                "text", anchors["surname"], ""))

    recall_address = _recall(builder, ADDRESS_RECALL)
    _courier_leg(builder, said_two, anchors, recall_address)

    recall_person = _recall(builder, PERSON_RECALL)
    last = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_one["name"], last, recall_person, 0))
    builder.declare_hop(arg_hop(said_one["name"], last + 1, recall_person,
                                "escalate_to_human", 0, "summary", last, ""))
    builder.declare_hop(arg_hop(said_one["ph"], last + 2, recall_person,
                                "escalate_to_human", 0, "summary", 1, ""))
    _declare_memory(builder, said_one, said_two,
                    (turn_one, turn_two, recall_phone, recall_address, recall_person))
    return builder.build(BEHAVIOUR)


def _note_shape(ctx: c.Ctx) -> Case:
    """The last recall goes into a CRM note: a SUMMARY the next operator reads,
    and the phone recall books a callback instead of an SMS."""
    builder, drawn, card, said_one, said_two, turn_one, turn_two = _second_leg(
        ctx, _NOTE_TOOLS, ("crm_find_contact", "callback_schedule", "courier_book"),
        "пять реплик: обратный звонок по «тому же телефону», курьер «по тому "
        "адресу», заметка в карточке по «первому клиенту»")
    anchors = _common_hops(builder, card, said_one, said_two, turn_one, turn_two)
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    recall_phone = _recall(builder, PHONE_RECALL)
    index = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_one["ph"], index, recall_phone, 1))
    builder.declare_hop(arg_hop(said_one["ph"], index + 1, recall_phone, "callback_schedule",
                                0, "phone", index, ""))

    recall_address = _recall(builder, ADDRESS_RECALL)
    _courier_leg(builder, said_two, anchors, recall_address)

    recall_person = _recall(builder, PERSON_RECALL)
    last = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_one["name"], last, recall_person, 0))
    builder.declare_hop(arg_hop(said_one["name"], last + 1, recall_person, "crm_add_note", 0,
                                "text", last, ""))
    builder.declare_hop(arg_hop(said_two["name2"], last + 2, recall_person, "crm_add_note", 0,
                                "text", anchors["name2"], ""))
    _declare_memory(builder, said_one, said_two,
                    (turn_one, turn_two, recall_phone, recall_address, recall_person))
    return builder.build(BEHAVIOUR)


def _ticket_shape(ctx: c.Ctx) -> Case:
    """The last recall opens a support ticket whose subject and text are both
    SUMMARY leaves — two people retold in one free-text field."""
    builder, drawn, card, said_one, said_two, turn_one, turn_two = _second_leg(
        ctx, _TICKET_TOOLS, ("crm_find_contact", "notify_sms", "courier_book"),
        "пять реплик: смс «на тот же телефон», курьер «по тому адресу», "
        "обращение по «первому клиенту» с обоими людьми в тексте")
    anchors = _common_hops(builder, card, said_one, said_two, turn_one, turn_two)
    builder.v4.must_contain = (str(drawn.person.surname[0]),)

    recall_phone = _recall(builder, PHONE_RECALL)
    index = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_one["ph"], index, recall_phone, 1))
    builder.declare_hop(arg_hop(said_one["ph"], index + 1, recall_phone, "notify_sms", 0,
                                "number", index, ""))

    recall_address = _recall(builder, ADDRESS_RECALL)
    _courier_leg(builder, said_two, anchors, recall_address)

    recall_person = _recall(builder, PERSON_RECALL)
    last = builder.next_hop_index()
    builder.declare_hop(memory_hop(said_one["name"], last, recall_person, 0))
    builder.declare_hop(arg_hop(said_one["name"], last + 1, recall_person, "ticket_create", 0,
                                "subject", last, ""))
    builder.declare_hop(arg_hop(said_two["name2"], last + 2, recall_person, "ticket_create", 0,
                                "text", anchors["name2"], ""))
    builder.declare_hop(arg_hop(said_one["ph"], last + 3, recall_person, "ticket_create", 0,
                                "phone", 1, ""))
    _declare_memory(builder, said_one, said_two,
                    (turn_one, turn_two, recall_phone, recall_address, recall_person))
    return builder.build(BEHAVIOUR)


MEMORY_SELFTEST: int = 12


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.memory_anaphora` — build and report."""
    cases = build(4, MEMORY_SELFTEST)
    print(f"{BEHAVIOUR}: {len(cases)} cases, "
          f"{sum(len(case.memory) for case in cases)} memory specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
