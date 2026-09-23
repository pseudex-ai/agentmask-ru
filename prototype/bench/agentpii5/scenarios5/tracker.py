"""`tracker` — одно ПОЛИМОРФНОЕ поле поиска и исполнитель ПО ИМЕНИ.

TWO FORMS THE CORPUS HAS THE OPPOSITE OF. `crm_find_contact` splits its key
across THREE typed fields — `query.phone`, `query.email`, `query.last_name` — so
a gateway knows what it is holding before it looks. A tracker has ONE field, and
the customer's own people type a surname, a login or an address into it without
thinking about which. That is the form and the risk at once: a leaf whose value
MAY be personal data and may not, where masking by the field's name is wrong in
one direction and not masking by the field's name is wrong in the other.

AND THE ASSIGNEE. The corpus names a person in a RESULT
(`escalate_to_human.assignee.name`) and never in an ARGUMENT: every tool it hands
a person to takes a phone, an ИНН, a plate or a card. A tracker takes the
person's own name and matches it against its directory, so a substitute that
fails to resolve there is refused by name.

AND «РАЗРЕШИЛОСЬ В ДРУГОГО» THIS CORPUS CANNOT SEE — said here rather than left
to be read out of the first sentence. Each case seeds ONE directory row, so the
only outcomes are «the row» and «nobody»: a substitute that resolved to a
COLLEAGUE would assign the task to them and return 201, and there is no second
colleague for it to resolve to. Seeding one would not buy the outcome either —
the substitute would have to collide with that second row's own surname, which
is the engine's `test_collisions` question and not a property any corpus of this
size can carry. The instrument therefore separates found from empty and nothing
finer, and the handover names the gap rather than the docstring implying it away.

WHAT COMES BACK IS LATIN. `mock._tracker_issue_create` answers with the
directory's `display_name` — «Sokolov Andrey» for a task the operator opened on
«Соколова» — which is a notation no Russian speech register produces and
therefore an IN hop that can actually fail. The same is true of the search
result, and it is why this family reads BOTH back.

THE LOGIN IS IN THE RESULT AND IS MEASURED BY NOTHING. `tracker_find_user`
renders one deliberately untagged: a login is not personal data, so it cannot be
declared in `result_pii` (V04/V06 refuse it), and `Negative` has no locus outside
a message. The corpus therefore puts a machine identifier the operator DOES say
— the issue key — into the message as a `plain_value`, and the handover names the
contract change the login needs. Filing it under one of the ten closed speech
families to get a number would be worse than the silence.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.pools import Rendered
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import ReturnExpectation
from bench.agentpii5.scenarios5 import client_tools as t
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_a import (answer_hop, arg_hop, seeded, told, tool_hop,
                                               user_hop)

BEHAVIOUR: str = "sequential_chain"
TOOLS: tuple[str, ...] = (t.TRACKER_FIND_USER, t.TRACKER_ISSUE_CREATE, t.MAIL_SEND)
TRACKER_CLAUSE: str = ("Исполнителя ищи в справочнике инструментом, в задачу ставь того, "
                       "кого назвали, а найденному напиши письмом. Данные клиента "
                       "переноси в описание без сокращений.")
# The directory columns this family reads back, and the result leaf each arrives
# at. Named once: the hop, the expectation and the argument all read it.
DIRECTORY_LEAVES: tuple[tuple[str, str], ...] = (
    ("display_name", t.TRACKER_USER_NAME), ("email", t.TRACKER_USER_EMAIL))
# What a tracker's directory row holds. `name` is the person as the DIALOGUE says
# them and is what `mock._tracker_user_named` matches an assignee against;
# `display_name` is the Latin spelling the tracker prints back. The two are the
# whole point of the row, and `login` beside them is the pair this instrument
# cannot yet separate.
LOGIN_SUFFIXES: tuple[str, ...] = ("ops", "crm", "sup", "fin")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(f"{BEHAVIOUR}:tracker", seed, index, registers[index]))
            for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    """Which kind of value the one free field holds alternates by index — except
    that an ADDRESS cannot be dictated at all.

    v4's register gate refuses a digit or sentence punctuation in `voice_raw` and
    punctuation in `voice_itn`, measured on 53 324 utterances, and an address
    carries both; the corpus agrees all by itself, with 14 EMAIL items in a user
    message and none of them in a speech register. So the speech half of this
    family searches by SURNAME and the written half alternates. The two shares
    are still decided by the plan and never by a draw, which is what keeps «the
    gateway masked it when it held a name» a measurement rather than a property
    of the seed.
    """
    if not t.can_say_address(ctx):
        return _by_surname(ctx)
    return (_by_surname if ctx.index % 2 == 0 else _by_address)(ctx)


def _staff_seed(builder: c.CaseBuilderV5, ctx: c.Ctx, drawn: c.Drawn,
                identity: str) -> dict[str, str]:
    """One row of `tracker_users`, in the shape `mock._tracker_find_user` reads.

    `name` IS THE SURNAME AND NOT THE FULL NAME, and that is the mock's contract
    rather than a preference: `_tracker_user_named` folds the assignee argument
    and compares it with this column, and the operator dictating «исполнитель
    Соколов» hands the tracker exactly one word. A row whose `name` were the full
    name would refuse every task this family opens, and the case would measure a
    refusal it did not declare.

    `display_name` IS LATIN, and the mock answers with it; the item on it is what
    makes the IN hop a question about form rather than about identity.
    """
    latin = pools.mail_translit(drawn.person.surname[0]).capitalize()
    shown = f"{latin} {pools.mail_translit(drawn.person.given[0]).capitalize()}"
    address = f"{drawn.email_local}@{drawn.email_domain}".lower()
    fields: dict[str, object] = {
        "name": drawn.person.surname[0], "display_name": shown, "email": address,
        "login": f"{pools.mail_translit(drawn.person.surname[0])}."
                 f"{LOGIN_SUFFIXES[ctx.index % len(LOGIN_SUFFIXES)]}",
        "account_id": f"acc-{ctx.index}"}
    return seeded(builder, "usr-1", "tracker_users", fields, {
        "display_name": ("NAME", identity, Rendered(shown, shown, False,
                                                    {"surname": latin,
                                                     "gender": drawn.person.gender})),
        "email": ("EMAIL", identity, Rendered(address, address, False,
                                              {"local": drawn.email_local,
                                               "domain": drawn.email_domain})),
    })


def _world(ctx: c.Ctx, note: str) -> tuple[c.CaseBuilderV5, c.Drawn, c.Drawn,
                                           dict[str, str], str, str]:
    """The colleague in the directory, the client the task is about, and the two
    identities they carry.

    THE CLIENT IS NOT THE COLLEAGUE, and not for tidiness: the mock drops a
    by-value tag two seeded items share, so two people with one surname would
    leave the directory row untagged and every hop on it unobservable.
    """
    staff = f"s{ctx.index}"
    client = f"k{ctx.index}"
    city = ctx.rng.choice(list(pools.CORPUS_CITIES))
    colleague = c.draw(ctx, city=city)
    customer = c.extra_people(ctx, city, colleague, 1)[0]
    builder = c.new_builder(ctx, "crm", TOOLS, TOOLS, staff, f"PHONE:{colleague.phone}",
                            note, (TRACKER_CLAUSE,))
    builder.v4.conversation_id = t.conversation_id("tracker", ctx.index)
    row = _staff_seed(builder, ctx, colleague, staff)
    return builder, colleague, customer, row, staff, client


def _chain(builder: c.CaseBuilderV5, row: dict[str, str], turn: int, key_hop: int,
           key_item: str, who_hop: int, who_item: str, phone_hop: int,
           phone_item: str) -> None:
    """Search the directory, open the task, write to the person it landed on.

    THREE TRANSITIONS, NOT ONE. R12 asks for a single OUT hop fed by another
    tool's result; §3.1's row asks this family for three, because one transition
    is a lookup feeding a write and the revised v4 corpus supplies that in bulk.
    The letter's recipient comes off the search, its subject and its body off the
    task the tracker answered — three leaves of two results, and a gateway can
    lose any one of them while carrying the others.

    THE ASSIGNEE IS SOURCED FROM THE USER'S OWN WORD, NOT FROM THE SEARCH, AND
    IT IS A DIFFERENT VALUE FROM THE KEY. `mock._tracker_user_named` matches the
    argument against the directory's `name` column — the surname the operator
    said — so an address put there is refused with `ASSIGNEE_UNKNOWN` and the
    call answers `error_with_value`. That is exactly what the first version of
    this family did on every address-keyed case, and `mock.render_problems` named
    it: a corpus that declares a chain the mock cannot make would score every hop
    of it as a gateway miss. The operator therefore names the person AND, in the
    written registers, their address; the search runs on one and the assignment
    on the other, which is also what somebody with a directory in front of them
    actually does.
    """
    index = builder.next_hop_index()
    builder.declare_hop(arg_hop(key_item, index, turn, t.TRACKER_FIND_USER, 0, t.TRACKER_QUERY,
                                key_hop, ""))
    index += 1
    found: dict[str, int] = {}
    for column, path in DIRECTORY_LEAVES:
        builder.declare_hop(tool_hop(row[column], index, turn, t.TRACKER_FIND_USER, 0, path))
        found[column] = index
        index += 1
    builder.expect_return(ReturnExpectation(
        t.TRACKER_FIND_USER, 0, "list",
        tuple(row[column] for column, _path in DIRECTORY_LEAVES)))

    builder.declare_hop(arg_hop(who_item, index, turn, t.TRACKER_ISSUE_CREATE, 0,
                                t.TRACKER_ISSUE_ASSIGNEE, who_hop, ""))
    index += 1
    # THE TITLE NAMES THE PERSON THE DIRECTORY GAVE BACK, in the directory's own
    # Latin spelling — so the task's title and its assignee field carry the SAME
    # human in two notations, out of two different sources, and a gateway can
    # lose either one on its own.
    builder.declare_hop(arg_hop(row["display_name"], index, turn, t.TRACKER_ISSUE_CREATE, 0,
                                t.TRACKER_ISSUE_SUMMARY, found["display_name"], ""))
    index += 1
    # The client's own datum, into the free-text description the agent composes:
    # a SUMMARY leaf, so the form the real value must take on the way out is the
    # agent's own rather than a canonical one.
    builder.declare_hop(arg_hop(phone_item, index, turn, t.TRACKER_ISSUE_CREATE, 0,
                                t.TRACKER_ISSUE_DESCRIPTION, phone_hop, ""))
    index += 1
    assignee_back = index
    builder.declare_hop(tool_hop(row["display_name"], index, turn, t.TRACKER_ISSUE_CREATE, 0,
                                 t.TRACKER_ISSUE_ASSIGNEE_BACK))
    index += 1
    builder.expect_return(ReturnExpectation(
        t.TRACKER_ISSUE_CREATE, 0, "single", (row["display_name"],)))

    builder.declare_hop(arg_hop(row["email"], index, turn, t.MAIL_SEND, 0,
                                t.at(t.MAIL_SEND_TO, index=0), found["email"], ""))
    index += 1
    builder.declare_hop(arg_hop(row["display_name"], index, turn, t.MAIL_SEND, 0,
                                t.MAIL_SEND_SUBJECT, assignee_back, ""))
    index += 1
    builder.declare_hop(arg_hop(phone_item, index, turn, t.MAIL_SEND, 0, t.MAIL_SEND_BODY,
                                phone_hop, ""))
    index += 1
    builder.declare_hop(answer_hop(row["display_name"], index, turn, found["display_name"],
                                   False))


def _say(builder: c.CaseBuilderV5, ctx: c.Ctx, colleague: c.Drawn, staff: str,
         customer: c.Drawn, client: str, with_address: bool) -> tuple[int, dict[str, str]]:
    """The operator's one message.

    THE PERSON IS ALWAYS NAMED AND THE ADDRESS IS EXTRA. Both halves of the
    family assign the task by the surname, because that is the only string the
    tracker's directory matches; the address-keyed half says the address AS WELL
    and searches by it. So the two differ in one value and in nothing else, which
    is what makes «the gateway masked the free field when it held an address»
    comparable with «…when it held a name».
    """
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("заведите задачу исполнитель")
    draft.value("who", c.name(ctx, colleague.person, ("surname",)))
    typed: dict[str, tuple[str, str, str, bool]] = {
        "who": ("NAME", staff, "required", False)}
    if with_address:
        draft.say("его ящик")
        draft.value("key", c.email(ctx, colleague.email_local, colleague.email_domain))
        typed["key"] = ("EMAIL", staff, "required", False)
    draft.say("клиент оставил телефон")
    draft.value("ph", c.phone(ctx, customer.phone))
    typed["ph"] = ("PHONE", client, "required", False)
    t.say_machine_id(draft, ctx, "по", t.issue_key(ctx.index), t.RECORD_KEY_FAMILY,
                     t.RECORD_KEY_WHY)
    draft.punct(".")
    return told(builder, draft, typed)


def _open_hops(builder: c.CaseBuilderV5, said: dict[str, str],
               turn: int) -> dict[str, int]:
    """Every value of the message entering the turn, in the order it was said,
    and the {draft key: hop index} map the chain points `source_hop` at.

    THE MAP IS BUILT BY ENUMERATION, NEVER BY `.index`. `told` hands back an
    insertion-ordered dict and v4's own search proof traces `.index` as a scan —
    correctly, since it is the same move as asking a finished string where a
    value sits. Walking the keys once answers the same question without asking
    anything.
    """
    order = {key: position for position, key in enumerate(said)}
    for key, item_id in said.items():
        builder.declare_hop(user_hop(item_id, order[key], turn))
    return order


def _by_surname(ctx: c.Ctx) -> Case:
    """В свободном поле — ФАМИЛИЯ. Обязана дойти настоящей и обязана быть
    замаскирована по дороге к модели."""
    builder, colleague, customer, row, staff, client = _world(
        ctx, "поиск исполнителя по свободному полю, в котором фамилия: то же поле примет "
             "логин, поэтому маскировать по имени поля нельзя")
    turn, said = _say(builder, ctx, colleague, staff, customer, client, False)
    builder.v4.must_contain = (colleague.person.surname[0],)
    order = _open_hops(builder, said, turn)
    _chain(builder, row, turn, order["who"], said["who"], order["who"],
           said["who"], order["ph"], said["ph"])
    return builder.build(BEHAVIOUR)


def _by_address(ctx: c.Ctx) -> Case:
    """В том же свободном поле — АДРЕС почты. Другая типизация, один лист."""
    builder, colleague, customer, row, staff, client = _world(
        ctx, "поиск исполнителя по свободному полю, в котором почта: тот же лист, что "
             "и у фамилии, а задача всё равно ставится по имени")
    turn, said = _say(builder, ctx, colleague, staff, customer, client, True)
    builder.v4.must_contain = (colleague.person.surname[0],)
    order = _open_hops(builder, said, turn)
    _chain(builder, row, turn, order["key"], said["key"], order["who"],
           said["who"], order["ph"], said["ph"])
    return builder.build(BEHAVIOUR)


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.tracker` — build and report."""
    cases = build(4, 12)
    types: set[str] = set()
    for case in cases:
        items = {item.id: item for item in case.base.pii}
        types.update(items[hop.item_id].type for hop in case.hops
                     if hop.path == t.TRACKER_QUERY)
    print(f"tracker: {len(cases)} cases, the one query leaf holds {sorted(types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
