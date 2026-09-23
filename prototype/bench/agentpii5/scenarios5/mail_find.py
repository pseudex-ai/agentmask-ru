"""`mail_find` — персональные данные как КЛЮЧ ПОИСКА, и молчание вместо ошибки.

THE WORST FAILURE CLASS THE GATEWAY HAS, AND THE ONE NOBODY SEES. Every other
family in this corpus breaks loudly: a substitute in a phone field fails a
checksum, a substitute in an id fails `tools.ISSUE_ID_RE`, and the call comes
back `error_with_value`. A substitute in a SEARCH KEY breaks nothing. The request
parses, the API answers 200, and it answers NOTHING — no letters from that
address, no user by that name. The agent then reports, truthfully, that it found
nothing, and every level of the instrument except this one records a tidy day.

THE CORPUS HAS NINE «ПД КАК КЛЮЧ» TOOLS AND NOT ONE OF THEM IS A MAILBOX
(`crm_find_contact` 881 cases, `address_suggest` 144, `bank_client_find` 133,
`kb_search` 112, `vehicle_check` 107, `ticket_find` 70, `calendar_free` 68,
`snils_verify` 47, `patient_find` 12). EMAIL as an `IN/user` hop occurs 14 times
against 1 196 EMAIL items — mail is a column this corpus READS and never a value
the agent searches by.

THE SEARCH FEEDS THE READ, AND THAT IS THE MEASUREMENT. A key that resolves
finds the letter; a key that does not finds nothing and the chain stops, so
`chain_value` over `mail_search → mail_read → mail_send` is the line this family
exists to move. `mock._found_by_identity` admits a row by the
identities the query NAMES — its `from_name` and `from_email`, never its subject
or its body — and lets word overlap only ORDER what the identity admitted. That
order is the finding this family was audited on: with the ranking ADMITTING, «a
substituted surname beside a topic word of the letter» came back `total=1` and
the declaration above was false. The identity itself still tolerates a
declension («от Ерохиной»), because retrieval must not become a property of the
model's phrasing.

AND THE OUTCOME SPACE IS TWO, said here as it is in `tracker`: one letter per
case, so «нашли не то» does not exist to be measured. A search that returns the
wrong correspondent would need a substitute colliding with a SECOND seeded
sender, which is the engine's own `test_collisions` question.

WHY NOT `fanout_pick`. A search whose key is the person returns THAT person's
letters and nothing else, so the candidates a pick needs would have to be several
correspondents matched by one query — and a query that matched all of them would
be a topic word, not personal data. Declaring letters the search cannot return
would put every hop on them into a denominator no gateway could earn, which is
the exact defect `mock.render_problems` was built to refuse. The family is a
chain, and the fan-out over a mailbox is named in the handover instead.

TWO KEYS THROUGH ONE LEAF. `mail_search` has a single free `query`, the `q` of
every mail API, where «from:» is a convention and not a column. Half the cases
put an ADDRESS through it and half a SURNAME — so a gateway that decides by the
field's NAME is wrong in one direction or the other, and only a corpus that runs
both through the same leaf can say which. The address half exists only in the
written registers: v4's own gate refuses a dot or a digit in dictated text.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ReturnExpectation
from bench.agentpii5.scenarios5 import client_tools as t
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import answer_hop, arg_hop, told, tool_hop, user_hop

BEHAVIOUR: str = "sequential_chain"
TOOLS: tuple[str, ...] = (t.MAIL_SEARCH, t.MAIL_READ, t.MAIL_SEND, t.TRACKER_ISSUE_CREATE)
_REPLY_TOOLS: tuple[str, ...] = (t.MAIL_SEARCH, t.MAIL_READ, t.MAIL_SEND)
_ISSUE_TOOLS: tuple[str, ...] = (t.MAIL_SEARCH, t.MAIL_READ, t.TRACKER_ISSUE_CREATE)
SEARCH_CLAUSE: str = ("Письмо найди поиском по почте, прочитай найденное инструментом и "
                      "только потом действуй. По памяти не отвечай.")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(f"{BEHAVIOUR}:mailfind", seed, index, registers[index]))
            for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """The key alternates by index, except that an ADDRESS cannot be dictated —
    see the module docstring and `client_tools.can_say_address`."""
    if not t.can_say_address(ctx):
        return _by_name(ctx)
    return (_by_address if ctx.index % 2 == 0 else _by_name)(ctx)


def _world(ctx: c.Ctx, note: str) -> tuple[c.CaseBuilderV5, c.Drawn, str, dict[str, str]]:
    """One letter in the mailbox, and the correspondent who sent it.

    Returns `(builder, the sender, the letter's shape, the letter's map)`. The
    shape alternates so both of `mail_read`'s answers — the typed envelope and
    the `raw` string — are reached through a search as well as through a
    configured inbox.

    THE SINK ALTERNATES TOO, and it is not decoration: a family whose every tool
    is `messaging` measures a mail API rather than a gateway, which is what
    `test_generator_a._vertical_problems` refuses. Half the cases answer the
    letter and half open a task on it, so the same value found by the same key
    leaves through a TEMPLATE leaf in one half and a SUMMARY leaf in the other.
    """
    identity = f"p{ctx.index}"
    sender = c.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    shape = t.LETTER_FORMATS[ctx.index % len(t.LETTER_FORMATS)]
    tools = _REPLY_TOOLS if _replies(ctx) else _ISSUE_TOOLS
    builder = c.new_builder(ctx, "crm", tools, tools, identity, f"PHONE:{sender.phone}",
                            note, (SEARCH_CLAUSE,))
    builder.v4.conversation_id = t.conversation_id("mail_find", ctx.index)
    _key, letter = t.letter_seed(builder, ctx.index, sender, ctx, identity,
                                 t.LETTER_BODIES[ctx.index % len(t.LETTER_BODIES)], shape)
    return builder, sender, shape, letter


def _replies(ctx: c.Ctx) -> bool:
    """Whether this case answers the letter or opens a task on it. By index and
    never by a draw: the two sinks are two OUT owners, and their shares must be
    a property of the plan."""
    return (ctx.index // 2) % 2 == 0


def _chain(builder: c.CaseBuilderV5, letter: dict[str, str], shape: str, turn: int,
           key_item: str, key_hop: int, replies: bool) -> None:
    """Search by the key, open what came back, answer it.

    THE ENVELOPE IS READ TWICE ON PURPOSE — once out of the search result and
    once out of the letter — and they are not the same crossing. A search hit is
    a row in a list the model scans; the letter is a document it opens. A gateway
    that carries the address through one and not the other is a gateway whose
    answer depends on which screen the value came off, and one leaf for both
    would average that away.
    """
    index = builder.next_hop_index()
    builder.declare_hop(arg_hop(key_item, index, turn, t.MAIL_SEARCH, 0, t.MAIL_SEARCH_QUERY,
                                key_hop, ""))
    index += 1
    hit: dict[str, int] = {}
    for column, path in (("from_name", t.MAIL_HIT_NAME), ("from_email", t.MAIL_HIT_EMAIL)):
        builder.declare_hop(tool_hop(letter[column], index, turn, t.MAIL_SEARCH, 0, path))
        hit[column] = index
        index += 1
    # THE SNIPPET IS PERSONAL DATA REACHING THE MODEL WITH NO LETTER OPENED. A
    # search result is a screen a person scans, and every line of it carries the
    # first sentence of somebody's mail; a gateway that masks the letter and not
    # the hit list has leaked before the agent decided anything.
    for column in t.LETTER_INSIDE:
        builder.declare_hop(tool_hop(letter[column], index, turn, t.MAIL_SEARCH, 0,
                                     t.MAIL_HIT_SNIPPET))
        index += 1
    builder.expect_return(ReturnExpectation(
        t.MAIL_SEARCH, 0, "list",
        tuple(letter[column] for column, _path in t.LETTER_ENVELOPE)
        + tuple(letter[column] for column in t.LETTER_INSIDE)))

    read: dict[str, int] = {}
    for column, path in t.letter_leaves(shape):
        builder.declare_hop(tool_hop(letter[column], index, turn, t.MAIL_READ, 0, path))
        read[column] = index
        index += 1
    builder.expect_return(ReturnExpectation(
        t.MAIL_READ, 0, t.letter_form(shape),
        tuple(letter[column] for column, _path in t.letter_leaves(shape))))

    if replies:
        builder.declare_hop(arg_hop(letter["from_email"], index, turn, t.MAIL_SEND, 0,
                                    t.at(t.MAIL_SEND_TO, index=0), hit["from_email"], ""))
        index += 1
        builder.declare_hop(arg_hop(letter["from_name"], index, turn, t.MAIL_SEND, 0,
                                    t.MAIL_SEND_SUBJECT, read["from_name"], ""))
        index += 1
        for column in ("phone", "street"):
            builder.declare_hop(arg_hop(letter[column], index, turn, t.MAIL_SEND, 0,
                                        t.MAIL_SEND_BODY, read[column], ""))
            index += 1
        builder.declare_hop(tool_hop(letter["from_email"], index, turn, t.MAIL_SEND, 0,
                                     t.at(t.MAIL_ACCEPTED, index=0)))
        index += 1
        builder.expect_return(ReturnExpectation(
            t.MAIL_SEND, 0, "single", (letter["from_email"],)))
    else:
        # NO ASSIGNEE. `mock._tracker_issue_create` matches one against a seeded
        # directory and refuses what it does not know; this case seeds no
        # directory, so the leaf is left out — it is optional in the schema, and
        # the family that measures it is `tracker`, which seeds one.
        builder.declare_hop(arg_hop(letter["from_name"], index, turn, t.TRACKER_ISSUE_CREATE,
                                    0, t.TRACKER_ISSUE_SUMMARY, read["from_name"], ""))
        index += 1
        for column in ("phone", "street"):
            builder.declare_hop(arg_hop(letter[column], index, turn, t.TRACKER_ISSUE_CREATE,
                                        0, t.TRACKER_ISSUE_DESCRIPTION, read[column], ""))
            index += 1
    builder.declare_hop(answer_hop(letter["from_name"], index, turn, read["from_name"], False))


def _request(ctx: c.Ctx) -> str:
    """What the operator asks for once the letter is found — the sink, in words."""
    return "и ответьте на него" if _replies(ctx) else "и заведите по нему задачу"


def _by_address(ctx: c.Ctx) -> Case:
    """Поиск ПО ОТПРАВИТЕЛЮ: адрес как ключ."""
    builder, sender, shape, letter = _world(
        ctx, "поиск письма по адресу отправителя: ПД как ключ, подмена не ломает вызов — "
             "она ничего не находит")
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("найдите письмо от")
    draft.value("key", c.email(ctx, sender.email_local, sender.email_domain))
    draft.say(_request(ctx))
    t.say_machine_id(draft, ctx, "по", t.issue_key(ctx.index), t.RECORD_KEY_FAMILY,
                     t.RECORD_KEY_WHY)
    draft.punct(".")
    turn, said = told(builder, draft, {"key": ("EMAIL", f"p{ctx.index}", "required", False)})
    builder.v4.must_contain = (sender.person.surname[0],)
    builder.declare_hop(user_hop(said["key"], 0, turn))
    _chain(builder, letter, shape, turn, said["key"], 0, _replies(ctx))
    return builder.build(BEHAVIOUR)


def _by_name(ctx: c.Ctx) -> Case:
    """Тот же свободный запрос, но в нём ФАМИЛИЯ.

    The half of the form that cannot be decided by the field's name: the same
    leaf would equally hold a topic word or a project code.
    """
    builder, sender, shape, letter = _world(
        ctx, "поиск письма по свободному запросу, в котором фамилия: тот же лист, что и "
             "у темы письма — маскировать по имени поля нельзя")
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("поищите в почте письмо от")
    draft.value("key", c.name(ctx, sender.person, ("surname",)))
    draft.say(_request(ctx))
    t.say_machine_id(draft, ctx, "по", t.issue_key(ctx.index), t.RECORD_KEY_FAMILY,
                     t.RECORD_KEY_WHY)
    draft.punct(".")
    turn, said = told(builder, draft, {"key": ("NAME", f"p{ctx.index}", "required", False)})
    builder.v4.must_contain = (sender.person.surname[0],)
    builder.declare_hop(user_hop(said["key"], 0, turn))
    _chain(builder, letter, shape, turn, said["key"], 0, _replies(ctx))
    return builder.build(BEHAVIOUR)


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.mail_find` — build and report."""
    cases = build(4, 10)
    types: set[str] = set()
    for case in cases:
        items = {item.id: item for item in case.base.pii}
        types.update(items[hop.item_id].type for hop in case.hops
                     if hop.path == t.MAIL_SEARCH_QUERY)
    print(f"mail_find: {len(cases)} cases, the one search leaf holds {sorted(types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
