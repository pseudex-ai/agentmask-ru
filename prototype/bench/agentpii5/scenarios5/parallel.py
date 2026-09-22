"""`parallel` — N independent calls the agent should issue in ONE assistant turn.

Every other family gives the gateway one thing to do at a time. Here three
people's values leave the container inside one assistant message and three
results come back together, and the questions are different in kind: does EVERY
one of the N arguments get out (v4's D3 defect — «did the arm act at all» — in
its multi-call form), does each person keep their OWN substitute when the three
are minted in the same breath, and does the answer integrate all three instead of
reporting the first.

THE PROMPT ASKS FOR IT AND THE HOPS DECLARE IT. `common.PARALLEL_CLAUSE` tells
the agent to issue independent calls together; the OUT hops of the turn share one
`parallel_group`, which R09 requires to be ≥ 2 OUT hops of ONE turn and permits
in NO other behaviour. A live agent may still serialise them — that is a finding,
not a corpus error, and `metrics.multi_all_out` counts it against the arm rather
than dropping the case.

THE SMS VARIANT IS A FAN-OUT OF TWO ROUNDS, AND THE SECOND ROUND IS WHY.
`notify_sms` returns the number it was given, so its own result carries no item
the BACKEND holds and R05 allows no IN/tool hop on it. Sending three messages and
reading nothing would make this the one shape of the family with no result at
all — and an agent that texts three people looks them up first, because the text
it owes them is their own delivery address. So the turn is two fan-outs: three
`crm_find_contact` calls in one group, then three `notify_sms` calls in another,
each template carrying the name the CALLER said and the street the CARD returned.
That second pair is the crossing no other family has — a value that came back
from a tool leaving again inside a human-read template — and it is what makes
`template` the owner of a tool-sourced hop rather than only of a user-sourced one.

TWO GROUPS IN ONE TURN, NOT ONE. R09 asks a `parallel_group` to be ≥ 2 OUT hops
of ONE turn; it does not ask a turn to hold one group, and merging these two
would claim the notifications could be issued before the lookups they quote. The
lookups are `GROUP`, the notifications `NOTIFY_GROUP`, and the dependency between
the rounds is declared by `source_hop`, not by a label.
"""
from collections.abc import Sequence

from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, full_name, iso_date,
                                               minted, seeded, told, tool_hop, user_hop)

BEHAVIOUR: str = "parallel"
# The label of a fan-out issued in ONE assistant move. Three of the four variants
# have a single round and only need `GROUP`; `_messages` reads before it writes,
# and its second round is `NOTIFY_GROUP` — a group is «these calls go together»,
# not «this turn», and one label over both rounds would claim the notifications
# could be issued before the lookups they quote.
GROUP: str = "g1"
NOTIFY_GROUP: str = "g2"
TOOLS: tuple[str, ...] = (
    "vehicle_check", "notify_sms", "calendar_free", "crm_find_contact", "ticket_create",
    "crm_upsert_contact", "callback_schedule")
_PLATE_TOOLS: tuple[str, ...] = ("vehicle_check", "ticket_create", "notify_sms")
_SMS_TOOLS: tuple[str, ...] = ("crm_find_contact", "notify_sms", "callback_schedule")
_SLOT_TOOLS: tuple[str, ...] = ("calendar_free", "callback_schedule", "notify_sms")
_CRM_TOOLS: tuple[str, ...] = ("crm_find_contact", "crm_upsert_contact", "notify_sms")
# The requested day, per register. No dotted form anywhere: a dot is sentence
# punctuation and both speech registers refuse it.
_DAY: tuple[tuple[str, str], ...] = (
    ("voice_raw", "пятого сентября"), ("voice_itn", "5 сентября"), ("chat", "5 сентября"),
    ("sloppy", "5 сентября"), ("clean", "5 сентября"))


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    builders = (_plates, _messages, _slots, _cards)
    return builders[ctx.index % 4](ctx)


def _people(ctx: c.Ctx, how_many: int) -> tuple[c.Drawn, ...]:
    """`how_many` DIFFERENT people, each from a stream of its own.

    A second draw from `ctx.rng` would shift every later draw of the case, so a
    family that fans out to three would be a different corpus from the same seed
    than one that fans out to two. Distinctness is checked on the surname rather
    than assumed: two identical people in one fan-out make the consistency
    question unanswerable, because one substitute for both is CORRECT.
    """
    out: list[c.Drawn] = []
    step = 0
    while len(out) < how_many:
        stream = c.ctx_for(f"{BEHAVIOUR}:fan", ctx.seed, ctx.index * 100 + step, ctx.register)
        candidate = c.draw(stream, city=stream.rng.choice(list(pools.CORPUS_CITIES)))
        if _distinct(candidate, out):
            out.append(candidate)
        step += 1
        if step > 50:
            raise pools.BuildError(f"{ctx.index}: could not draw {how_many} distinct people")
    return tuple(out)


def _distinct(candidate: c.Drawn, taken: Sequence[c.Drawn]) -> bool:
    """No FIELD may repeat, not just no person.

    EVERY column the fan-out declares a hop on has to differ. Two people sharing
    a given name or a street produce two seed items holding ONE string, the
    mock's by-value index calls that ambiguous and tags NEITHER, and the hop
    becomes a miss charged to the gateway for a collision the corpus caused. The
    surname alone is not enough: the failure this rule closes was two «Марина»s
    in one three-card lookup.
    """
    for one in taken:
        if (one.person.surname[0] == candidate.person.surname[0]
                or one.person.given[0] == candidate.person.given[0]
                or one.phone == candidate.phone
                or one.address.street == candidate.address.street
                or one.dob == candidate.dob
                or (one.email_local, one.email_domain) == (candidate.email_local,
                                                           candidate.email_domain)):
            return False
    return True


def _conversation(ctx: c.Ctx) -> str:
    return f"conv-par-{ctx.index}" if ctx.index % 3 == 0 else ""


def _plates(ctx: c.Ctx) -> Case:
    """«пробейте эти три номера» — three ГИБДД lookups in one move."""
    people = _people(ctx, 3)
    plates = tuple(c.plate_text(ctx.rng) for _ in people)
    identities = tuple(f"p{ctx.index}n{slot}" for slot in range(3))
    builder = c.new_builder(ctx, "gov", _PLATE_TOOLS, ("vehicle_check",), identities[0],
                            f"PLATE:{plates[0]}",
                            "три номера одним ходом: три OUT сразу, три результата вместе, "
                            "ответ обязан свести все три",
                            (c.PARALLEL_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    rows = tuple(
        seeded(builder, f"veh-{slot + 1}", "vehicles", {
            "plate": plates[slot], "model": "Lada Vesta", "year": "2019",
            "owner": {"last_name": people[slot].person.surname[0],
                      "first_name": people[slot].person.given[0]}}, {
            "plate": ("PLATE", identities[slot],
                      c.plate(c.ctx_for("plate", ctx.seed, ctx.index * 10 + slot, "clean"),
                              plates[slot])),
            "owner.last_name": ("NAME", identities[slot], pools.Rendered(
                people[slot].person.surname[0], people[slot].person.surname[0], False,
                {"surname": people[slot].person.surname[0],
                 "gender": people[slot].person.gender})),
        })
        for slot in range(3))

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("пробейте три номера")
    for slot in range(3):
        if slot:
            draft.say("и")
        draft.value(f"plate{slot}", c.plate(ctx, plates[slot]))
    draft.say("скажите чьи они")
    draft.punct(".")
    turn, said = told(builder, draft, {
        f"plate{slot}": ("PLATE", identities[slot], "required", False) for slot in range(3)})
    builder.v4.must_contain = tuple(one.person.surname[0] for one in people)

    index = 0
    for slot in range(3):
        builder.declare_hop(user_hop(said[f"plate{slot}"], index, turn))
        index += 1
    for slot in range(3):
        builder.declare_hop(arg_hop(said[f"plate{slot}"], index, turn, "vehicle_check", slot,
                                    "plate", slot, GROUP))
        index += 1
    owners: list[int] = []
    for slot in range(3):
        owners.append(index)
        builder.declare_hop(tool_hop(rows[slot]["owner.last_name"], index, turn,
                                     "vehicle_check", slot, "owner.last_name"))
        index += 1
    for slot in range(3):
        builder.declare_hop(answer_hop(rows[slot]["owner.last_name"], index, turn,
                                       owners[slot], False))
        index += 1
    for slot in range(3):
        builder.expect_return(ReturnExpectation(
            "vehicle_check", slot, "single",
            (rows[slot]["plate"], rows[slot]["owner.last_name"])))
    return builder.build(BEHAVIOUR)


def _messages(ctx: c.Ctx) -> Case:
    """«отправьте смс Иванову, Петрову и Сидоровой» — three cards, then three
    templates, all in one assistant move.

    THE LOOKUP IS NOT SCAFFOLDING. The message the three people are owed names
    the address the courier will come to, and the caller does not dictate three
    addresses — they are in the cards. So the round that reads is as much part of
    the task as the round that writes, and an arm that skips it cannot write a
    correct text at all.

    EACH TEMPLATE CARRIES TWO VALUES FROM TWO SOURCES: the name the caller said
    (IN/user) and the street the card returned (IN/tool). One slot per person
    would make «did each person keep their own substitute» answerable by
    position; two, from two directions, make it answerable only by value — which
    is the question this family exists to ask.
    """
    people = _people(ctx, 3)
    identities = tuple(f"p{ctx.index}s{slot}" for slot in range(3))
    builder = c.new_builder(ctx, "callcenter", _SMS_TOOLS,
                            ("crm_find_contact", "notify_sms"), identities[0],
                            f"PHONE:{people[0].phone}",
                            "три карточки и три смс одним ходом: имя и улица каждого уходят "
                            "в СВОЙ шаблон, и перепутать их нечем, кроме значения",
                            (c.PARALLEL_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    cards: list[dict[str, str]] = []
    for slot in range(3):
        before = len(builder.v4.pii)
        c.contact_seed(f"c-{slot + 1}", people[slot], people[slot].address.city, ctx, builder,
                       identities[slot])
        cards.append({item.where.path: item.id for item in minted(builder, before)})

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("разошлите троим смс")
    draft.say("что курьер приедет по адресу из их карточки")
    typed: dict[str, tuple[str, str, str, bool]] = {}
    for slot in range(3):
        if slot:
            draft.say("потом")
        draft.value(f"name{slot}", c.name(ctx, people[slot].person, ("surname", "given")))
        draft.say("на номер")
        draft.value(f"ph{slot}", c.phone(ctx, people[slot].phone))
        typed[f"name{slot}"] = ("NAME", identities[slot], "required", False)
        typed[f"ph{slot}"] = ("PHONE", identities[slot], "required", False)
    draft.punct(".")
    turn, said = told(builder, draft, typed)

    index = 0
    names: list[int] = []
    phones: list[int] = []
    for slot in range(3):
        names.append(index)
        builder.declare_hop(user_hop(said[f"name{slot}"], index, turn))
        index += 1
        phones.append(index)
        builder.declare_hop(user_hop(said[f"ph{slot}"], index, turn))
        index += 1
    for slot in range(3):
        builder.declare_hop(arg_hop(said[f"ph{slot}"], index, turn, "crm_find_contact", slot,
                                    "query.phone", phones[slot], GROUP))
        index += 1
    streets: list[int] = []
    for slot in range(3):
        streets.append(index)
        builder.declare_hop(tool_hop(cards[slot]["address.street"], index, turn,
                                     "crm_find_contact", slot, "contacts[].address.street"))
        index += 1
    for slot in range(3):
        builder.declare_hop(arg_hop(said[f"ph{slot}"], index, turn, "notify_sms", slot,
                                    "number", phones[slot], NOTIFY_GROUP))
        index += 1
        builder.declare_hop(arg_hop(said[f"name{slot}"], index, turn, "notify_sms", slot,
                                    "text", names[slot], NOTIFY_GROUP))
        index += 1
        builder.declare_hop(arg_hop(cards[slot]["address.street"], index, turn, "notify_sms",
                                    slot, "text", streets[slot], NOTIFY_GROUP))
        index += 1
    for slot in range(3):
        builder.declare_hop(answer_hop(said[f"name{slot}"], index, turn, names[slot], True))
        index += 1
    for slot in range(3):
        builder.expect_return(ReturnExpectation(
            "crm_find_contact", slot, "list",
            (cards[slot]["last_name"], cards[slot]["first_name"], cards[slot]["phone"],
             cards[slot]["address.street"])))
    return builder.build(BEHAVIOUR)


def _slots(ctx: c.Ctx) -> Case:
    """«свободные окна у двоих» — two calendars in one move, two ISO birth dates
    back, and neither may be read onto the other person."""
    people = _people(ctx, 2)
    identities = tuple(f"p{ctx.index}c{slot}" for slot in range(2))
    day = dict(_DAY)[ctx.register]
    # THE ROW IS KEYED ON THE NAME THE CALLER USES, built from the very
    # `Rendered` the message will carry: a calendar keyed on the full ФИО while
    # the caller says surname and given name answers `empty` in every register,
    # and the case would declare a result nobody can produce.
    said_names = tuple(c.name(ctx, one.person, ("surname", "given")) for one in people)
    builder = c.new_builder(ctx, "callcenter", _SLOT_TOOLS, ("calendar_free",), identities[0],
                            f"NAME:{full_name(people[0].person)}",
                            "два расписания одним ходом: даты рождения приходят в ISO "
                            "и не должны поменяться людьми",
                            (c.PARALLEL_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    rows = tuple(
        seeded(builder, f"cal-{slot + 1}", "calendar", {
            "person": said_names[slot].canonical,
            "birth_date": iso_date(people[slot].dob)}, {
            "person": ("NAME", identities[slot], pools.Rendered(
                said_names[slot].canonical, said_names[slot].canonical, False,
                {"surname": people[slot].person.surname[0],
                 "given": people[slot].person.given[0],
                 "gender": people[slot].person.gender})),
            "birth_date": ("DOB", identities[slot], pools.Rendered(
                iso_date(people[slot].dob), iso_date(people[slot].dob), False,
                {"iso": iso_date(people[slot].dob)})),
        })
        for slot in range(2))

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("посмотрите свободные окна врач")
    draft.value("name0", said_names[0])
    draft.say("и врач")
    draft.value("name1", said_names[1])
    draft.say("на")
    draft.plain_value("day", day, "time_of_day",
                      "день приёма — не персональные данные, обязан уцелеть")
    draft.punct(".")
    turn, said = told(builder, draft, {
        "name0": ("NAME", identities[0], "required", False),
        "name1": ("NAME", identities[1], "required", False)})

    index = 0
    for slot in range(2):
        builder.declare_hop(user_hop(said[f"name{slot}"], index, turn))
        index += 1
    for slot in range(2):
        builder.declare_hop(arg_hop(said[f"name{slot}"], index, turn, "calendar_free", slot,
                                    "person", slot, GROUP))
        index += 1
    births: list[int] = []
    for slot in range(2):
        builder.declare_hop(tool_hop(rows[slot]["person"], index, turn, "calendar_free", slot,
                                     "person"))
        index += 1
        births.append(index)
        builder.declare_hop(tool_hop(rows[slot]["birth_date"], index, turn, "calendar_free",
                                     slot, "birth_date"))
        index += 1
    for slot in range(2):
        builder.declare_hop(answer_hop(rows[slot]["birth_date"], index, turn, births[slot], True))
        index += 1
    for slot in range(2):
        builder.expect_return(ReturnExpectation(
            "calendar_free", slot, "list",
            (rows[slot]["person"], rows[slot]["birth_date"])))
    return builder.build(BEHAVIOUR)


def _cards(ctx: c.Ctx) -> Case:
    """«поднимите три карточки» — three CRM lookups at once, three addresses
    back, and the answer owes each person their own street."""
    people = _people(ctx, 3)
    identities = tuple(f"p{ctx.index}k{slot}" for slot in range(3))
    builder = c.new_builder(ctx, "crm", _CRM_TOOLS, ("crm_find_contact",), identities[0],
                            f"PHONE:{people[0].phone}",
                            "три карточки одним ходом: три адреса назад, ни один не должен "
                            "оказаться в чужой строке",
                            (c.PARALLEL_CLAUSE,))
    builder.v4.conversation_id = _conversation(ctx)
    cards: list[dict[str, str]] = []
    for slot in range(3):
        before = len(builder.v4.pii)
        c.contact_seed(f"c-{slot + 1}", people[slot], people[slot].address.city, ctx, builder,
                       identities[slot])
        cards.append({item.where.path: item.id for item in minted(builder, before)})

    draft = builder.draft()
    draft.say(c.opener(ctx)).say("поднимите три карточки по телефонам")
    for slot in range(3):
        if slot:
            draft.say("и")
        draft.value(f"ph{slot}", c.phone(ctx, people[slot].phone))
    draft.say("скажите адреса")
    draft.punct(".")
    turn, said = told(builder, draft, {
        f"ph{slot}": ("PHONE", identities[slot], "required", False) for slot in range(3)})
    builder.v4.must_contain = tuple(one.address.street for one in people)

    index = 0
    for slot in range(3):
        builder.declare_hop(user_hop(said[f"ph{slot}"], index, turn))
        index += 1
    for slot in range(3):
        builder.declare_hop(arg_hop(said[f"ph{slot}"], index, turn, "crm_find_contact", slot,
                                    "query.phone", slot, GROUP))
        index += 1
    streets: list[int] = []
    for slot in range(3):
        streets.append(index)
        builder.declare_hop(tool_hop(cards[slot]["address.street"], index, turn,
                                     "crm_find_contact", slot, "contacts[].address.street"))
        index += 1
    for slot in range(3):
        builder.declare_hop(answer_hop(cards[slot]["address.street"], index, turn,
                                       streets[slot], False))
        index += 1
    for slot in range(3):
        builder.expect_return(ReturnExpectation(
            "crm_find_contact", slot, "list",
            (cards[slot]["last_name"], cards[slot]["first_name"], cards[slot]["phone"],
             cards[slot]["address.street"])))
    return builder.build(BEHAVIOUR)
