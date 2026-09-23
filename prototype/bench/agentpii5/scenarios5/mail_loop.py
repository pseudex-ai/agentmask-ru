"""`mail_loop` — прочитать письмо, переписать, положить в инструмент.

THE LOOP THE WHOLE CHANGE IS FOR, AND THE CORPUS MEASURED IT ZERO TIMES. The
1 736 cases carry 708 `IN/tool → OUT/tool_arg` transitions and **not one of them
comes out of a `free_text` result**: 596 out of a `list`, 66 out of `nested`, 24
out of `single`, 12 out of a ledger, 10 out of retrieval chunks. Values do reach
an argument out of free text — 413 of them — but only ever out of a DOCUMENT
(`file_read` 219, `form_parse` 150, `doc_retrieve` 44). A letter is not among the
sources, and a letter is where the customer's assistants spend their day.

WHY THAT GAP IS THE EXPENSIVE ONE. A typed result is a gateway's easy case: it
knows `contacts[].phone` is a phone before it looks. Prose is the hard one — the
model reads a name, a number and a street out of a sentence somebody's customer
wrote, RE-WRITES them in its own words, and the rewritten value has to arrive at
the next tool as the real thing. A placeholder masker scores zero here and full
marks on every list-shaped family in the corpus, which is exactly why the number
we could quote today would not be the number the customer buys.

THREE SINKS, BECAUSE «ПОЛОЖИТЬ» IS THREE DIFFERENT FIELDS:
  `_to_card`  — a CRM card and a deal in ONE nested call (`crm_upsert_card`):
                typed leaves plus a free-text note the agent writes itself;
  `_to_reply` — an answer sent back by mail (`mail_send`): a LIST of recipients
                in one argument, and subject and body as TEMPLATE leaves a human
                will read;
  `_to_issue` — a tracker task (`tracker_issue_create`): an assignee named by
                NAME rather than by id, and a description carrying the letter's
                values.

TWO LETTER SHAPES UNDER EACH SINK, and they are two different problems. `full`
hands the envelope back typed (`from.name`, `from.email`) with the body apart;
`raw` hands headers and body over as ONE untyped string. A gateway can do the
first and fail the second, and a family that offered only one of them would
report an average of a question it never asked.

THE SENDER IS NOT THE OPERATOR. The letter carries one person; the operator
asking for the work gives their own address wherever the register can carry one,
and it crosses as an `IN/user` EMAIL — the hop the corpus has 14 of against 1 196
EMAIL items. Two people, never one: the mock indexes a seeded value by the value
itself and drops any string two items share, so an operator who was also the
sender would leave both untagged and every hop on them would read as a gateway
miss no gateway could avoid.

«WHEREVER THE REGISTER CAN CARRY ONE» IS v4's GATE AND NOT A LIBERTY. Its
validator refuses a digit or sentence punctuation in `voice_raw` and punctuation
in `voice_itn`, measured on 53 324 utterances, and an address carries both; the
corpus agrees by itself, with 14 EMAIL items in a user message and none of them
dictated. So a spoken case carries the letter's values and nothing of the
operator's own, and the reply it sends still goes to a real person — only the
copy is missing.

THE LETTER'S ID IS NOWHERE IN THE DIALOGUE. `mock.call_arguments` reads it off
the row the case SEEDED, the way it reads a file path, and «msg-12» carries a
dash and a digit run no caller dictates. The inbox a customer's gateway points
at is configuration, so the system prompt is where it is named.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ReturnExpectation
from bench.agentpii5.scenarios5 import client_tools as t
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import answer_hop, arg_hop, told, tool_hop, user_hop

BEHAVIOUR: str = "sequential_chain"
TOOLS: tuple[str, ...] = (
    t.MAIL_READ, t.MAIL_SEND, t.CRM_UPSERT_CARD, t.TRACKER_ISSUE_CREATE)
_CARD_TOOLS: tuple[str, ...] = (t.MAIL_READ, t.CRM_UPSERT_CARD)
_REPLY_TOOLS: tuple[str, ...] = (t.MAIL_READ, t.MAIL_SEND)
_ISSUE_TOOLS: tuple[str, ...] = (t.MAIL_READ, t.TRACKER_ISSUE_CREATE)

MAIL_CLAUSE: str = ("Данные бери из письма: сначала прочитай его инструментом, потом "
                    "заполняй поля значениями оттуда, ничего не придумывая и ничего "
                    "не сокращая.")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(f"{BEHAVIOUR}:mail", seed, index, registers[index]))
            for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Three sinks by index modulo three and two letter shapes by index modulo
    two, never by a draw. The sink decides which OUT owner the family contributes
    (`tool_arg`, `template`, `summary`) and the shape decides which return form
    it reads; both would become properties of the seed if they were drawn, and
    K-level shares must be properties of the plan."""
    shapes = (_to_card, _to_reply, _to_issue)
    return shapes[ctx.index % len(shapes)](ctx)


def _open(ctx: c.Ctx, tools: tuple[str, ...],
          note: str) -> tuple[c.CaseBuilderV5, c.Drawn, str, str, dict[str, str]]:
    """The letter, the operator, and a prompt that names the inbox.

    Returns `(builder, the sender, the OPERATOR's identity, the letter's shape,
    the letter's {column: item id} map)`. The sender's identity is `p<index>` and
    is not returned: every item of the letter already carries it, and a second
    name for it in the caller would be a second chance to spell it differently.
    """
    identity = f"p{ctx.index}"
    operator = f"o{ctx.index}"
    sender = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    shape = t.LETTER_FORMATS[ctx.index % len(t.LETTER_FORMATS)]
    builder = c.new_builder(ctx, "crm", tools, tools, identity,
                            f"PHONE:{sender.phone}", note,
                            (MAIL_CLAUSE, "Новое письмо лежит в рабочем ящике."))
    builder.v4.conversation_id = t.conversation_id("mail_loop", ctx.index)
    _key, letter = t.letter_seed(builder, ctx.index, sender, ctx, identity,
                                 t.LETTER_BODIES[ctx.index % len(t.LETTER_BODIES)], shape)
    return builder, sender, operator, shape, letter


def _ask(builder: c.CaseBuilderV5, ctx: c.Ctx, operator: str,
         request: str) -> tuple[int, dict[str, str]]:
    """The operator's one message: what to do, their own address where the
    register can carry one, and the machine identifier the work is filed under.

    BOTH OMISSIONS ARE THE REGISTER GATE, NOT A CHOICE. v4's validator refuses a
    digit or sentence punctuation in `voice_raw` and punctuation in `voice_itn`,
    measured on 53 324 utterances; an address carries both and «CRM-412» has no
    spoken form a tracker would take back. So a spoken case carries the letter's
    values and nothing of the operator's own, and `said` comes back without the
    `op` key — which is why every caller checks for it rather than assuming it.
    """
    draft = builder.draft()
    draft.say(c.opener(ctx)).say(request)
    typed: dict[str, tuple[str, str, str, bool]] = {}
    if t.can_say_address(ctx):
        local, domain = t.operator_email(ctx, ctx.index)
        draft.say("ответственный я")
        draft.value("op", c.email(ctx, local, domain))
        typed["op"] = ("EMAIL", operator, "required", False)
    t.say_machine_id(draft, ctx, "по", t.issue_key(ctx.index), t.RECORD_KEY_FAMILY,
                     t.RECORD_KEY_WHY)
    draft.punct(".")
    return told(builder, draft, typed)


def _read_the_letter(builder: c.CaseBuilderV5, letter: dict[str, str], shape: str,
                     turn: int) -> tuple[dict[str, int], int]:
    """The five IN hops one `mail_read` produces, and the next free hop index.

    WHICH LEAF EACH COLUMN ARRIVES AT IS THE LETTER'S BUSINESS, not this
    family's: `client_tools.letter_leaves` answers it for both shapes, so three
    sinks cannot disagree about what a `raw` letter looks like.
    """
    index = builder.next_hop_index()
    read: dict[str, int] = {}
    for column, path in t.letter_leaves(shape):
        builder.declare_hop(tool_hop(letter[column], index, turn, t.MAIL_READ, 0, path))
        read[column] = index
        index += 1
    builder.expect_return(ReturnExpectation(
        t.MAIL_READ, 0, t.letter_form(shape),
        tuple(letter[column] for column, _path in t.letter_leaves(shape))))
    return read, index


def _operator_hop(builder: c.CaseBuilderV5, said: dict[str, str], turn: int) -> int:
    """The operator's own address entering the turn, where the register let them
    say it. Returns the next free hop index either way, so a caller never has to
    know which half of the family it is in."""
    if "op" not in said:
        return builder.next_hop_index()
    builder.declare_hop(user_hop(said["op"], builder.next_hop_index(), turn))
    return builder.next_hop_index()


def _to_card(ctx: c.Ctx) -> Case:
    """Письмо → карточка и сделка одним вызовом.

    THE FORM THE CORPUS HAS NOWHERE. `crm_upsert_contact` writes ONE object;
    this writes a contact and a deal in one call, and the deal's note is free
    text the agent composes out of what it just read. A value that arrives
    correctly in `contact.phone` and as a substitute in `deal.note` is a leak the
    typed leaves alone would call a pass.

    THE BIRTH DATE GOES INTO THE NOTE BECAUSE THE CARD HAS NO FIELD FOR IT, and
    that is the honest placement rather than a convenience: `crm_upsert_card`
    mirrors amoCRM's complex endpoint, which has no birth-date leaf, and a
    benchmark that widened a tool so its own declaration came true would be
    measuring itself.
    """
    builder, sender, operator, shape, letter = _open(
        ctx, _CARD_TOOLS, "письмо → карточка и сделка одним вызовом: ПД из свободного "
        "текста уходят в типизированные поля и в заметку сделки")
    turn, said = _ask(builder, ctx, operator,
                      "прочитайте новое письмо и заведите клиента и сделку")
    builder.v4.must_contain = (sender.person.surname[0],)

    index = _operator_hop(builder, said, turn)
    read, index = _read_the_letter(builder, letter, shape, turn)
    # THE NAME GOES INTO THE DEAL AND NOT INTO `contact.last_name`, and the
    # instrument decided that rather than taste. A letter's envelope carries ONE
    # string, «Букин Сергей Иванович»; the card's own leaves take a surname and a
    # given name apart, and `mock.call_arguments` writes the item's canonical
    # into whatever leaf a hop names — so the whole name landed in `last_name`,
    # the parser refused it with `name_cyrillic`, and every hop of the case died
    # with the call. `render_problems` said so by name (V01/V05). The split is a
    # real form and it is measured where the corpus has a SPLIT source — the CSV
    # of `office`, the card of `crm_upsert_contact` — not here.
    leaves: tuple[tuple[str, str], ...] = (
        ("from_name", t.CARD_DEAL_NAME), ("from_email", t.CARD_EMAIL),
        ("phone", t.CARD_PHONE), ("street", t.CARD_STREET))
    for column, leaf in leaves:
        builder.declare_hop(arg_hop(letter[column], index, turn, t.CRM_UPSERT_CARD, 0, leaf,
                                    read[column], ""))
        index += 1
    # The leaf the agent WRITES rather than copies: a note about the deal, in its
    # own words, carrying the one datum the card has no column for.
    builder.declare_hop(arg_hop(letter["dob"], index, turn, t.CRM_UPSERT_CARD, 0,
                                t.CARD_DEAL_NOTE, read["dob"], ""))
    index += 1
    # WHAT THE CRM SAYS IT STORED. A card written with a substitute in it is a
    # card that looks written: nothing downstream fails, and the agent reports
    # success. The echo is the only place the corpus can see the difference, and
    # it is read for every leaf the card echoes. The ADDRESS is among them and is
    # the most interesting of the four: the agent wrote a street into
    # `contact.address.street` and the card prints «г Ижевск, ул Калашникова, д
    # 41» back, one canon line — the same value in two shapes, which is what the
    # LOC form comparison exists for.
    back: tuple[tuple[str, str], ...] = (
        ("from_name", t.CARD_BACK_DEAL_NAME), ("from_email", t.CARD_BACK_EMAIL),
        ("phone", t.CARD_BACK_PHONE), ("street", t.CARD_BACK_ADDRESS))
    for column, leaf in back:
        builder.declare_hop(tool_hop(letter[column], index, turn, t.CRM_UPSERT_CARD, 0, leaf))
        index += 1
    builder.expect_return(ReturnExpectation(
        t.CRM_UPSERT_CARD, 0, "nested", tuple(letter[column] for column, _leaf in back)))
    builder.declare_hop(answer_hop(letter["from_name"], index, turn, read["from_name"], False))
    return builder.build(BEHAVIOUR)


def _to_reply(ctx: c.Ctx) -> Case:
    """Письмо → ответ на него, получателей ДВА в одном аргументе.

    THE LIST IS THE POINT. `email_send.to` is one address and
    `crm_segment_report.members[].name` is the corpus's only «several people in
    one argument»; a recipient list is the form the customer's own assistants use
    every hour. The reply goes to the sender and copies the operator who asked
    for it, which is also what makes the OUT hop on the operator's own address a
    real crossing rather than a decoration.
    """
    builder, sender, operator, shape, letter = _open(
        ctx, _REPLY_TOOLS, "письмо → ответ: получатель и копия в одном вызове, тема и "
        "тело — шаблонные поля, которые прочитает человек")
    turn, said = _ask(builder, ctx, operator,
                      "прочитайте новое письмо и ответьте отправителю копию мне")
    builder.v4.must_contain = (sender.person.surname[0],)

    _operator_hop(builder, said, turn)
    read, index = _read_the_letter(builder, letter, shape, turn)
    builder.declare_hop(arg_hop(letter["from_email"], index, turn, t.MAIL_SEND, 0,
                                t.at(t.MAIL_SEND_TO, index=0), read["from_email"], ""))
    index += 1
    if "op" in said:
        # The copy exists only where the operator could say their address; the
        # reply itself never depends on it, so the spoken half of the family
        # still sends a real letter to a real person.
        builder.declare_hop(arg_hop(said["op"], index, turn, t.MAIL_SEND, 0,
                                    t.at(t.MAIL_SEND_CC, index=0), 0, ""))
        index += 1
    # The subject and the body are TEMPLATE leaves: a human reads them, so the
    # form the real value must take on the way out is the agent's own, not a
    # canonical one.
    builder.declare_hop(arg_hop(letter["from_name"], index, turn, t.MAIL_SEND, 0,
                                t.MAIL_SEND_SUBJECT, read["from_name"], ""))
    index += 1
    for column in ("phone", "street"):
        builder.declare_hop(arg_hop(letter[column], index, turn, t.MAIL_SEND, 0,
                                    t.MAIL_SEND_BODY, read[column], ""))
        index += 1
    # THE TRANSFER AGENT ECHOES THE ADDRESS IT ACCEPTED, lower-cased — the
    # messaging vertical's own notation, which no caller register produces.
    builder.declare_hop(tool_hop(letter["from_email"], index, turn, t.MAIL_SEND, 0,
                                 t.at(t.MAIL_ACCEPTED, index=0)))
    index += 1
    builder.expect_return(ReturnExpectation(
        t.MAIL_SEND, 0, "single", (letter["from_email"],)))
    builder.declare_hop(answer_hop(letter["from_email"], index, turn, read["from_email"], False))
    return builder.build(BEHAVIOUR)


def _to_issue(ctx: c.Ctx) -> Case:
    """Письмо → задача в трекере: описание несёт ПД из чужой прозы.

    THE ASSIGNEE IS NOT DECLARED HERE. `mock._tracker_issue_create` matches the
    argument against a seeded `tracker_users` row and refuses what it does not
    know, so a case that names an assignee it never seeded would provoke a
    refusal it did not declare — the failure `document.py` already documents for
    a file extension. The assignee leaf is measured in the `tracker` family,
    which seeds the directory; here the letter's values go into the summary and
    the description, which is what a letter turned into a task actually carries.
    """
    builder, sender, operator, shape, letter = _open(
        ctx, _ISSUE_TOOLS, "письмо → задача: тема и описание из свободного текста "
        "письма, оба — поля, которые агент пишет сам")
    turn, said = _ask(builder, ctx, operator,
                      "прочитайте новое письмо и заведите по нему задачу")
    builder.v4.must_contain = (sender.person.surname[0],)

    _operator_hop(builder, said, turn)
    read, index = _read_the_letter(builder, letter, shape, turn)
    builder.declare_hop(arg_hop(letter["from_name"], index, turn, t.TRACKER_ISSUE_CREATE, 0,
                                t.TRACKER_ISSUE_SUMMARY, read["from_name"], ""))
    index += 1
    for column in ("phone", "street", "dob"):
        builder.declare_hop(arg_hop(letter[column], index, turn, t.TRACKER_ISSUE_CREATE, 0,
                                    t.TRACKER_ISSUE_DESCRIPTION, read[column], ""))
        index += 1
    builder.declare_hop(answer_hop(letter["from_name"], index, turn, read["from_name"], False))
    return builder.build(BEHAVIOUR)


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.mail_loop` — build and report."""
    cases = build(4, 24)
    sinks = sorted({hop.tool_name for case in cases for hop in case.hops
                    if hop.kind == "OUT" and hop.tool_name and hop.tool_name != t.MAIL_READ})
    forms = sorted({one.return_form for case in cases for one in case.returns})
    print(f"mail_loop: {len(cases)} cases, sinks {sinks}, letter forms {forms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
