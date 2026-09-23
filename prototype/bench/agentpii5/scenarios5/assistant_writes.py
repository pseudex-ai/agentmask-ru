"""`assistant_writes` — три записи, которые ассистент делает ОТ СЕБЯ.

THREE SINKS THE CORPUS HAS NOTHING LIKE, all of them writes and all of them out
of one lookup:

  `memory_save`     — a fact about a person put into a PERSISTENT store. The
                      corpus's 574 `IN/memory` hops are the CONVERSATION's
                      memory: «значение из транскрипта», which the model
                      re-reads and nobody else ever sees. Writing a person into
                      a store that outlives the dialogue is a different act with
                      a different failure: a substitute saved there is wrong for
                      every later conversation, not for this one.
  `reminder_set`    — a text that will be DELIVERED to a human later. Its
                      nearest relatives are `notify_sms.text` (379 cases) and
                      `send_template.variables.*` (34), and neither is deferred:
                      `callback_schedule` schedules a call and carries no text at
                      all, so «отложенное действие, несущее ПД» is measured by
                      nothing.
  `calendar_invite` — SEVERAL people in ONE argument. `calendar_free` asks about
                      one person, `callback_schedule` about one number, and the
                      corpus's only «many people in one argument» is
                      `crm_segment_report.members[].name` in eighteen cases. An
                      attendee list is what a working calendar takes.

ONE LOOKUP FEEDS ALL THREE, and that is what makes it a chain rather than three
`single` cases glued together: the same card's surname reaches a memory store, a
reminder and an invitation, so a form lost at the lookup is lost three times over
and the report can say which of the three sinks kept it.

THE SECOND ATTENDEE IS THE OPERATOR, and it is why the list is a real list: their
address enters as `IN/user` — the hop the corpus has 14 of against 1 196 EMAIL
items — and leaves through the same leaf as the client's, so a gateway that
resolves the first element and drops the second is visible. IT EXISTS ONLY IN THE
WRITTEN REGISTERS: v4's gate refuses a dot or a digit in dictated text, measured
on 53 324 utterances, and the corpus agrees by itself — of its 1 196 EMAIL items
the 14 said out loud are 10 `chat` and 4 `sloppy`. A spoken case invites the
client alone, which is one element short of the form and honest about why.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ReturnExpectation
from bench.agentpii5.scenarios5 import client_tools as t
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, minted, told, tool_hop,
                                               user_hop)

BEHAVIOUR: str = "sequential_chain"
TOOLS: tuple[str, ...] = ("crm_find_contact", t.MEMORY_SAVE, t.REMINDER_SET, t.CALENDAR_INVITE)
ASSISTANT_CLAUSE: str = ("Найдя карточку, запомни о клиенте то, что попросили, поставь "
                         "напоминание и позови на встречу и клиента, и постановщика.")
# The card columns this family reads back, and the result leaf each arrives at.
CARD_LEAVES: tuple[tuple[str, str], ...] = (
    ("last_name", "contacts[].last_name"), ("phone", "contacts[].phone"),
    ("email", "contacts[].email"), ("birth_date", "contacts[].birth_date"),
    ("address.street", "contacts[].address.street"))
# Every item of the card the lookup's result carries — K15's «several records of
# ONE person in one result» is counted on this, so it names the whole row rather
# than the four leaves the hops read.
CARD_RETURNED: tuple[str, ...] = (
    "last_name", "first_name", "phone", "email", "birth_date", "address.street")
MEETINGS: tuple[str, ...] = ("во вторник в одиннадцать", "в четверг в десять",
                             "в понедельник в пятнадцать")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(f"{BEHAVIOUR}:assistant", seed, index, registers[index]))
            for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    identity = f"p{ctx.index}"
    operator = f"o{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "crm", TOOLS, TOOLS, identity, f"PHONE:{drawn.phone}",
                            "одна карточка кормит три записи: постоянная память, отложенное "
                            "напоминание и приглашение", (ASSISTANT_CLAUSE,))
    builder.v4.conversation_id = t.conversation_id("assistant", ctx.index)
    card = _card(builder, ctx, city, drawn, identity)

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("клиент по телефону")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say("запомните его адрес поставьте напоминание и позовите на встречу")
    draft.plain_value("when", MEETINGS[ctx.index % len(MEETINGS)], "time_of_day",
                      "время встречи — не персональные данные, обязано уцелеть")
    typed: dict[str, tuple[str, str, str, bool]] = {
        "ph": ("PHONE", identity, "required", False)}
    if t.can_say_address(ctx):
        local, domain = t.operator_email(ctx, ctx.index)
        draft.say("и меня")
        draft.value("op", c.email(ctx, local, domain))
        typed["op"] = ("EMAIL", operator, "required", False)
    t.say_machine_id(draft, ctx, "по", t.issue_key(ctx.index), t.RECORD_KEY_FAMILY,
                     t.RECORD_KEY_WHY)
    draft.punct(".")
    turn, said = told(builder, draft, typed)
    builder.v4.must_contain = (drawn.person.surname[0],)

    said_hop = _hop_of(said)
    for key, item_id in said.items():
        builder.declare_hop(user_hop(item_id, said_hop[key], turn))
    index = len(said)
    phone_hop = said_hop["ph"]
    builder.declare_hop(arg_hop(said["ph"], index, turn, "crm_find_contact", 0, "query.phone",
                                phone_hop, ""))
    index += 1
    found: dict[str, int] = {}
    for column, path in CARD_LEAVES:
        builder.declare_hop(tool_hop(card[column], index, turn, "crm_find_contact", 0, path))
        found[column] = index
        index += 1
    builder.expect_return(ReturnExpectation(
        "crm_find_contact", 0, "list", tuple(card[column] for column in CARD_RETURNED)))
    index = _remember(builder, card, found, turn, index)
    index = _remind(builder, card, found, turn, index)
    index = _invite(builder, card, found, turn, index,
                    said.get("op", ""), said_hop.get("op", -1))
    builder.declare_hop(answer_hop(card["last_name"], index, turn, found["last_name"], False))
    return builder.build(BEHAVIOUR)


def _hop_of(said: dict[str, str]) -> dict[str, int]:
    """{draft key: hop index} for the values of one message.

    BY ENUMERATION AND NEVER BY `.index`. `told` hands back an insertion-ordered
    dict and v4's search proof traces `.index` as a scan — correctly, since it is
    the same move as asking a finished string where a value sits.
    """
    return {key: position for position, key in enumerate(said)}


def _card(builder: c.CaseBuilderV5, ctx: c.Ctx, city: str, drawn: c.Drawn,
          identity: str) -> dict[str, str]:
    """The client's own CRM row, seeded so the lookup has something to return."""
    before = len(builder.v4.pii)
    c.contact_seed("c-1", drawn, city, ctx, builder, identity)
    return {item.where.path: item.id for item in minted(builder, before)}


def _remember(builder: c.CaseBuilderV5, card: dict[str, str], found: dict[str, int],
              turn: int, index: int) -> int:
    """The fact about the person that outlives the conversation.

    `subject` IS A PLAIN ARGUMENT AND `fact` IS A SUMMARY LEAF, and the split is
    the measurement: the subject is a key the store indexes by — a substitute
    there files the fact under a person who does not exist and returns 200 —
    while the fact is prose the agent writes, where the form the real value must
    take is the agent's own.
    """
    builder.declare_hop(arg_hop(card["last_name"], index, turn, t.MEMORY_SAVE, 0,
                                t.MEMORY_SUBJECT, found["last_name"], ""))
    builder.declare_hop(arg_hop(card["address.street"], index + 1, turn, t.MEMORY_SAVE, 0,
                                t.MEMORY_FACT, found["address.street"], ""))
    builder.declare_hop(arg_hop(card["birth_date"], index + 2, turn, t.MEMORY_SAVE, 0,
                                t.MEMORY_FACT, found["birth_date"], ""))
    # WHOM THE STORE SAYS IT FILED THE FACT UNDER. A memory written against a
    # substitute is a memory about a person who does not exist, and it is wrong
    # for every LATER conversation rather than for this one — so the echo is the
    # only moment the corpus can catch it.
    builder.declare_hop(tool_hop(card["last_name"], index + 3, turn, t.MEMORY_SAVE, 0,
                                 t.MEMORY_BACK_SUBJECT))
    builder.expect_return(ReturnExpectation(t.MEMORY_SAVE, 0, "single", (card["last_name"],)))
    return index + 4


def _remind(builder: c.CaseBuilderV5, card: dict[str, str], found: dict[str, int],
            turn: int, index: int) -> int:
    """The text a human will read later, and the number it will reach them on.

    `recipient.phone` IS THE ONE REQUIRED IDENTITY LEAF OF THIS TOOL, and a case
    that declared no hop on it would be driven with an empty string and refused —
    `mock.call_arguments` says so out loud rather than inventing a number.

    IT COMES OFF THE CARD AND NOT OFF THE MESSAGE, and the difference is what can
    be measured. The two strings are the same number; the mock indexes a
    by-value tag off SEEDED rows only, so a reminder addressed with the message's
    item echoes a number nothing can tag and the whole write-back goes unread.
    Sourced from the lookup, the same datum crosses as `IN/user`, as an argument
    and back again — which is the loop this family is here to close.

    `text` IS A TEMPLATE LEAF: the value has to arrive in the shape a person
    reads, not in a canonical one, and it arrives after the conversation that
    produced it has ended.
    """
    builder.declare_hop(arg_hop(card["phone"], index, turn, t.REMINDER_SET, 0,
                                t.REMINDER_PHONE, found["phone"], ""))
    builder.declare_hop(arg_hop(card["last_name"], index + 1, turn, t.REMINDER_SET, 0,
                                t.REMINDER_NAME, found["last_name"], ""))
    builder.declare_hop(arg_hop(card["address.street"], index + 2, turn, t.REMINDER_SET, 0,
                                t.REMINDER_TEXT, found["address.street"], ""))
    # WHOM THE REMINDER IS ADDRESSED TO AND ON WHICH NUMBER, as the scheduler now
    # holds them.
    builder.declare_hop(tool_hop(card["last_name"], index + 3, turn, t.REMINDER_SET, 0,
                                 t.REMINDER_BACK_NAME))
    builder.declare_hop(tool_hop(card["phone"], index + 4, turn, t.REMINDER_SET, 0,
                                 t.REMINDER_BACK_PHONE))
    builder.expect_return(ReturnExpectation(
        t.REMINDER_SET, 0, "single", (card["last_name"], card["phone"])))
    return index + 5


def _invite(builder: c.CaseBuilderV5, card: dict[str, str], found: dict[str, int],
            turn: int, index: int, operator_item: str, operator_hop: int) -> int:
    """The attendees in ONE argument, and the agenda under them.

    The client's address comes off the card and the operator's out of the
    message, and both cross `attendees[].email` — so a gateway that carries the
    first element and loses the second sends an invitation that looks sent. The
    second element exists only where the register could carry an address; the
    first is always there, because it comes off a backend row and no register
    gates a tool result.
    """
    builder.declare_hop(arg_hop(card["email"], index, turn, t.CALENDAR_INVITE, 0,
                                t.at(t.INVITE_ATTENDEE_EMAIL, index=0), found["email"], ""))
    builder.declare_hop(arg_hop(card["last_name"], index + 1, turn, t.CALENDAR_INVITE, 0,
                                t.at(t.INVITE_ATTENDEE_NAME, index=0), found["last_name"], ""))
    builder.declare_hop(arg_hop(card["address.street"], index + 2, turn, t.CALENDAR_INVITE, 0,
                                t.INVITE_DESCRIPTION, found["address.street"], ""))
    index += 3
    builder.declare_hop(tool_hop(card["email"], index, turn, t.CALENDAR_INVITE, 0,
                                 t.at(t.INVITE_BACK_EMAIL, index=0)))
    builder.declare_hop(tool_hop(card["last_name"], index + 1, turn, t.CALENDAR_INVITE, 0,
                                 t.at(t.INVITE_BACK_NAME, index=0)))
    builder.expect_return(ReturnExpectation(
        t.CALENDAR_INVITE, 0, "single", (card["email"], card["last_name"])))
    index += 2
    if operator_item:
        builder.declare_hop(arg_hop(operator_item, index, turn, t.CALENDAR_INVITE, 0,
                                    t.at(t.INVITE_ATTENDEE_EMAIL, index=1), operator_hop, ""))
        index += 1
    return index


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.assistant_writes` — build and report."""
    cases = build(4, 6)
    owners = sorted({hop.owner for case in cases for hop in case.hops if hop.kind == "OUT"})
    print(f"assistant_writes: {len(cases)} cases, OUT owners {owners}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
