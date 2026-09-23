"""Пять семей под формы клиента: то, что `validate_v5` не спрашивает.

WHAT THIS FILE IS FOR AND WHAT IT IS NOT FOR. `validate_v5` asks whether a case
is WELL FORMED; `test_generator_a` and `test_generator_b` ask whether a family is
the BEHAVIOUR it claims. Neither asks the question this round was opened on:
does the corpus now MEASURE the four forms the customer actually runs — a letter
read and rewritten into a tool, personal data used as a search key, a person
named in an argument, and a value written into a two-dimensional cell or a long
free text. A family can be valid, be a chain, and still measure none of them.

EVERY CHECK BELOW IS A NUMBER THAT WAS ZERO. The corpus carried 708 transitions
from a tool result into an argument and not one of them came out of `free_text`;
14 EMAIL items in a user message against 1 196 items; no tool anywhere that took
a person's NAME as an argument; no two-dimensional argument and no writing tool
for a document. So each check is written as «this must be more than none» with
the measurement it replaces named beside it, and each one fails on a corpus
where the family was deleted.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_client_families

NOTHING HERE IMPORTS `pseudex`.
"""
import sys
from collections.abc import Sequence
from dataclasses import replace

from bench.agentpii4.schema import PiiItem
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema as s
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5 import mock
from bench.agentpii5.mock import (IDENTITY_STEM, IDENTITY_TAIL, BackendV5,
                                  render_problems, seed_backend_v5)
from bench.agentpii5.scenarios5 import (assistant_writes, client_tools, mail_find,
                                        mail_loop, office, tracker)
from bench.agentpii5.scenarios5.plan_a import PLAN_A
from bench.agentpii5.scenarios5.plan_b import PLAN_B
from bench.agentpii5.tools import REGISTRY_V5

SEED: int = 4
# The five families of this round, at the counts their plans order. Built ONCE:
# five families is a couple of seconds, and building them per check would make
# the file slow enough that somebody stops running it.
CLIENT_MODULES: tuple[object, ...] = (mail_loop, mail_find, tracker, assistant_writes, office)
PLANNED: dict[str, int] = {
    module.__name__.rsplit(".", 1)[-1]: count                    # type: ignore[attr-defined]
    for module, count in PLAN_A + PLAN_B}
BUILT: dict[str, list[CaseV5]] = {
    module.__name__.rsplit(".", 1)[-1]:                          # type: ignore[attr-defined]
        module.build(SEED, PLANNED[module.__name__.rsplit(".", 1)[-1]])   # type: ignore[attr-defined]
    for module in CLIENT_MODULES}
ALL_CASES: tuple[CaseV5, ...] = tuple(case for cases in BUILT.values() for case in cases)
# The OUT owners that are an ACT on a tool. Read off `contracts` rather than
# restated: a second copy is one drift away from this file and the metrics
# disagreeing about what a chain is.
ACTING: tuple[str, ...] = c.ACTING_OUT_OWNERS


def _items(case: CaseV5) -> dict[str, PiiItem]:
    return {item.id: item for item in case.base.pii}


def _return_form(case: CaseV5, tool: str, ordinal: int) -> str:
    """The form the case declares that call comes back in, or "" — read off the
    case's own `ReturnExpectation`s, which is what `render_problems` proves
    against the real mock."""
    for expectation in case.returns:
        if expectation.tool_name == tool and expectation.call_ordinal == ordinal:
            return expectation.return_form
    return ""


def _free_text_transitions(cases: Sequence[CaseV5]) -> list[tuple[str, str, str]]:
    """Every «a value came back inside PROSE and went out into a tool» crossing,
    as (case id, source tool, consuming tool).

    THE SOURCE MUST BE A TOOL AND NOT A DOCUMENT. `IN/document` prose already
    existed — 413 crossings out of a CSV, a form and a scan — and the gap this
    round closes is the OTHER one: prose arriving from a SERVICE, where nothing
    told the gateway a file was being parsed.
    """
    out: list[tuple[str, str, str]] = []
    for case in cases:
        for hop in case.hops:
            if hop.kind != "OUT" or hop.owner not in ACTING:
                continue
            if not 0 <= hop.source_hop < len(case.hops):
                continue
            source = case.hops[hop.source_hop]
            if source.kind != "IN" or source.owner != "tool":
                continue
            if source.tool_name == hop.tool_name:
                continue
            if _return_form(case, source.tool_name, source.call_ordinal) != "free_text":
                continue
            out.append((case.base.id, source.tool_name, hop.tool_name))
    return out


# --- the four forms ---------------------------------------------------------------

def test_the_head_loop_is_measured() -> list[str]:
    """ПРОЧИТАЛ ПИСЬМО → ПОЛОЖИЛ В ИНСТРУМЕНТ, and it must be plural.

    The corpus carried 708 `IN/tool → OUT/tool_arg` transitions and NOT ONE came
    out of a `free_text` result: 596 out of a list, 66 out of a nested object, 24
    out of a single record, 12 out of a ledger, 10 out of retrieval chunks. This
    is the line that was zero, so the check is «more than a handful, and into
    more than one kind of sink» — a single case would be an anecdote and one sink
    would measure that sink's schema.
    """
    problems: list[str] = []
    crossings = _free_text_transitions(ALL_CASES)
    from_mail = [one for one in crossings if one[1] == client_tools.MAIL_READ]
    if len(from_mail) < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"{len(from_mail)} transitions out of a letter's prose, "
                        f"below {c.MIN_TYPE_DENOMINATOR}; the corpus had none and one case "
                        f"would be an anecdote")
    sinks = {one[2] for one in from_mail}
    if len(sinks) < 3:
        problems.append(f"a letter's prose reaches {sorted(sinks)}; «положить» is a card, a "
                        f"reply and a task, and one sink measures that sink's schema")
    cases = {one[0] for one in from_mail}
    if len(cases) < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"the loop lives in {len(cases)} cases, below "
                        f"{c.MIN_TYPE_DENOMINATOR}")
    return problems


def test_both_letter_shapes_are_read() -> list[str]:
    """A letter comes back typed OR as one untyped string, and both are read.

    `mail_read` answers `nested` for a stored letter and `free_text` for
    `format=raw` — the envelope apart from the body, or headers and body in one
    string. A gateway can do the first and fail the second, so a corpus that read
    only one of them would report an average of a question it never asked.
    """
    problems: list[str] = []
    forms: dict[str, int] = {}
    for case in ALL_CASES:
        form = _return_form(case, client_tools.MAIL_READ, 0)
        if form:
            forms[form] = forms.get(form, 0) + 1
    for form in ("nested", "free_text"):
        if forms.get(form, 0) < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"mail_read answers {form!r} in {forms.get(form, 0)} cases, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")
    return problems


def test_personal_data_is_a_search_key() -> list[str]:
    """ПД КАК КЛЮЧ, and through a leaf that is not typed.

    A substitute in a search key breaks nothing visibly: the call parses, the API
    answers 200, and it answers NOTHING. `crm_find_contact` splits its key across
    three TYPED fields, which is the opposite form; the customer's mail and
    tracker each have ONE free field that may hold an address, a surname or a
    login. Both kinds of value must go through that one leaf, or the corpus
    cannot say whether a gateway decided by the field's name.
    """
    problems: list[str] = []
    for tool, leaf in ((client_tools.MAIL_SEARCH, client_tools.MAIL_SEARCH_QUERY),
                       (client_tools.TRACKER_FIND_USER, client_tools.TRACKER_QUERY)):
        types: dict[str, int] = {}
        for case in ALL_CASES:
            items = _items(case)
            for hop in case.hops:
                if hop.kind == "OUT" and hop.tool_name == tool and hop.path == leaf:
                    kind = items[hop.item_id].type
                    types[kind] = types.get(kind, 0) + 1
        if len(types) < 2:
            problems.append(f"{tool}.{leaf} carries {sorted(types)}; one kind of value through "
                            f"a polymorphic field cannot show what the gateway decided by")
        if sum(types.values()) < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"{tool}.{leaf} is crossed {sum(types.values())} times, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")
    return problems


def test_a_person_is_named_in_an_argument() -> list[str]:
    """ИСПОЛНИТЕЛЬ ПО ИМЕНИ — a NAME the tool matches on, not a phone.

    The corpus names a person in a RESULT (`escalate_to_human.assignee.name`) and
    never in an argument: every tool it hands a person to takes a phone, an ИНН,
    a plate or a card. `tracker_issue_create.assignee` and `memory_save.subject`
    are keys made of a person's own name, and a substitute that fails to resolve
    there files the work against nobody while the call returns 201.
    """
    problems: list[str] = []
    for tool, leaf in ((client_tools.TRACKER_ISSUE_CREATE, client_tools.TRACKER_ISSUE_ASSIGNEE),
                       (client_tools.MEMORY_SAVE, client_tools.MEMORY_SUBJECT)):
        seen = 0
        for case in ALL_CASES:
            items = _items(case)
            for hop in case.hops:
                if hop.kind != "OUT" or hop.tool_name != tool or hop.path != leaf:
                    continue
                if items[hop.item_id].type != "NAME":
                    problems.append(f"{case.base.id}: {tool}.{leaf} carries a "
                                    f"{items[hop.item_id].type}; the leaf is a person's name")
                seen += 1
        if seen < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"{tool}.{leaf} is crossed {seen} times, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")
    return problems[:8]


def test_two_dimensions_and_a_long_text() -> list[str]:
    """ЯЧЕЙКА ТАБЛИЦЫ и ДОПИСАННЫЙ ДОКУМЕНТ — the two write shapes the corpus had
    nothing of.

    Its nearest spreadsheet was `crm_import_csv(csv)`, ONE string container; its
    nearest «write a document» was nothing at all. A row is not one value, so
    every cell is its own hop at its own (row, column) — a gateway that resolves
    four cells of five leaves a row that looks complete and nothing downstream
    fails.
    """
    problems: list[str] = []
    cells: dict[str, set[str]] = {}
    for case in ALL_CASES:
        for hop in case.hops:
            if hop.kind == "OUT" and hop.tool_name == client_tools.SHEET_APPEND_ROW:
                cells.setdefault(case.base.id, set()).add(hop.path)
    if len(cells) < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"{len(cells)} cases write a spreadsheet row, "
                        f"below {c.MIN_TYPE_DENOMINATOR}")
    thin = [case_id for case_id, paths in cells.items() if len(paths) < 2]
    if thin:
        problems.append(f"{len(thin)} of them write ONE cell ({thin[:3]}); a row that is one "
                        f"value has the shape `crm_import_csv` already had")
    appended = {case.base.id for case in ALL_CASES for hop in case.hops
                if hop.kind == "OUT" and hop.tool_name == client_tools.DOC_APPEND}
    if len(appended) < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"{len(appended)} cases append to a document, "
                        f"below {c.MIN_TYPE_DENOMINATOR}")
    for case in ALL_CASES:
        for hop in case.hops:
            if hop.kind == "OUT" and hop.tool_name == client_tools.DOC_APPEND:
                owner = c.hop_owner_of_leaf(hop.tool_name, hop.path)
                if owner != "summary":
                    problems.append(f"{case.base.id}: doc_append.{hop.path} counts as "
                                    f"{owner!r}; a paragraph the agent writes is a summary")
    return problems[:8]


def test_several_people_in_one_argument() -> list[str]:
    """СПИСОК ПОЛУЧАТЕЛЕЙ и СПИСОК УЧАСТНИКОВ: two values through one list leaf.

    `email_send.to` is ONE address and the corpus's only «many people in one
    argument» was `crm_segment_report.members[].name` in eighteen cases. A
    gateway that resolves the first element of a list and drops the second sends
    a letter and an invitation that both look sent.
    """
    problems: list[str] = []
    listed = 0
    for case in ALL_CASES:
        for tool in (client_tools.MAIL_SEND, client_tools.CALENDAR_INVITE):
            paths = {hop.path for hop in case.hops
                     if hop.kind == "OUT" and hop.tool_name == tool and "[" in hop.path}
            recipients = {path for path in paths if "email" in path or path.startswith("to[")
                          or path.startswith("cc[")}
            if len(recipients) >= 2:
                listed += 1
    if listed < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"{listed} cases put two people into one call's recipient list, "
                        f"below {c.MIN_TYPE_DENOMINATOR}; the form is «адрес ИЛИ СПИСОК» and "
                        f"a list of one measures the singular half twice")
    return problems


# --- what must survive ------------------------------------------------------------

def test_machine_identifiers_stand_beside_real_values() -> list[str]:
    """Ключи записей и диапазоны ячеек — В ТЕХ ЖЕ сообщениях, что и настоящие ПД.

    OVER-MASKING IS ONLY MEASURED IN THE MESSAGE, and that is a property of the
    package rather than of this corpus: `metrics.overmask` reads
    `case.base.negatives` and a `Negative` carries `msg`, the index of a message.
    There is no locus for «this argument», so an identifier that appeared only
    inside a call would be measured by nothing at all — which is why these stand
    in the dialogue, beside the values the same call carries.

    THEY ARE `plain_value` AND NOT `negative`, because `NEGATIVE_FAMILIES` is a
    closed tuple of ten speech families and `v4.validate` refuses anything else.
    Filing a cell range under «order_number» to get it counted would put a
    machine address into a number read as speech precision. The line that counts
    them is a CONTRACT change, named in the handover; this check only holds the
    corpus side of it in place, so the day the line exists it has a population.

    THE TWO FAMILIES ARE HELD TO DIFFERENT FLOORS, AND THE ARITHMETIC IS WHY.
    A record key is said in four registers of five and by four families, so its
    count is large and a floor means something. A cell RANGE is said by six cases
    of one family and «Лист1!A3:E3» carries both a digit and a colon, so v4's
    gate refuses it in BOTH speech registers — the honest ceiling is the written
    share of six cases, which is three or four depending on the seed. A floor of
    five there would be a number that passed on seed 4 and failed on seed 2, so
    the claim made instead is the stronger one: the range is present in EVERY
    case that could say it and in none that could not.
    """
    problems: list[str] = []
    families: dict[str, int] = {}
    for case in ALL_CASES:
        for plain in case.base.plain:
            if plain.family in (client_tools.RECORD_KEY_FAMILY, client_tools.CELL_RANGE_FAMILY):
                families[plain.family] = families.get(plain.family, 0) + 1
                refusing = client_tools._REFUSING_REGISTERS(plain.value)   # noqa: SLF001
                if case.base.register in refusing:
                    problems.append(f"{case.base.id}: {plain.value!r} in "
                                    f"{case.base.register!r}, which v4's register gate "
                                    f"refuses it in")
    if families.get(client_tools.RECORD_KEY_FAMILY, 0) < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"{families.get(client_tools.RECORD_KEY_FAMILY, 0)} messages carry a "
                        f"record key, below {c.MIN_TYPE_DENOMINATOR}")
    problems.extend(_range_problems())
    return problems[:8]


def _range_problems() -> list[str]:
    """Каждый случай, который ПИШЕТ строку таблицы, называет диапазон — если его
    регистр может его выговорить."""
    problems: list[str] = []
    said = 0
    for case in ALL_CASES:
        writes = any(hop.kind == "OUT" and hop.tool_name == client_tools.SHEET_APPEND_ROW
                     for hop in case.hops)
        if not writes:
            continue
        ranges = [plain for plain in case.base.plain
                  if plain.family == client_tools.CELL_RANGE_FAMILY]
        said += len(ranges)
        speakable = case.base.register not in client_tools._REFUSING_REGISTERS(   # noqa: SLF001
            client_tools.sheet_range(0))
        if speakable and not ranges:
            problems.append(f"{case.base.id} writes a spreadsheet row in "
                            f"{case.base.register!r} and names no range; the register could "
                            f"carry one")
        if not speakable and ranges:
            problems.append(f"{case.base.id} names a range in {case.base.register!r}")
    if not said:
        problems.append("no message anywhere carries a cell range; over-masking of the one "
                        "machine address that sits beside a spreadsheet row is measured by "
                        "nothing")
    return problems


def test_every_case_still_carries_a_speech_negative() -> list[str]:
    """Один негатив из закрытых десяти — в КАЖДОМ случае.

    v4's builder adds it on the first user message unless the family declared
    one, and these families declare none: `overmask` is the only line that scores
    precision, and a family that silenced it would buy its recall with a rule
    that masks everything.

    AND IT IS TRUE BY CONSTRUCTION, WHICH IS WHY IT IS FALSIFIED BY A MUTATION
    RATHER THAN BY A MISSING FAMILY. `agentpii4.scenarios.common.user()` adds the
    negative itself when neither the family nor the draft declared one, so no
    corpus that BUILDS can fail this — removing a family leaves it green, and
    `test_the_checks_can_fail` was therefore not naming it. The negative it is
    paired with strips the negatives off one case, which is the only way the
    thing this claims can stop being true.
    """
    problems: list[str] = []
    for case in ALL_CASES:
        if not case.base.negatives:
            problems.append(f"{case.base.id} carries no negative; `overmask` would have "
                            f"nothing to count on it")
    return problems[:8]


# --- the retriever: what a key is, and what it is not -------------------------------

# A surname ending, cut to ONE letter past what an inflection may add. Tied to
# `IDENTITY_TAIL` rather than spelled out, so raising the bound moves the check
# with it instead of leaving it testing an easier case than the rule allows.
_STRANGER_TAIL: str = "цевский"


def _near_miss(word: str) -> str:
    """A different surname that shares this one's first four letters.

    THE SHAPE A GATEWAY CAN ACTUALLY MINT. Pseudex draws a substitute out of its
    own pools, and nothing stops it drawing one whose stem collides; the index
    cannot tell that from a declension by looking, so the question is only how
    far past the shared stem it is allowed to run. Built here rather than drawn,
    because a check that depended on a draw would be a check that sometimes
    tested nothing.
    """
    return word[:IDENTITY_STEM] + _STRANGER_TAIL[:IDENTITY_TAIL + 1]


def _searchers(cases: Sequence[CaseV5]) -> list[tuple[CaseV5, str, str]]:
    """Every case that searches a seeded index by a person, as
    (case, the table it searches, the tool it searches with)."""
    out: list[tuple[CaseV5, str, str]] = []
    for case in cases:
        tools = {hop.tool_name for hop in case.hops}
        if client_tools.MAIL_SEARCH in tools:
            out.append((case, "mailbox", client_tools.MAIL_SEARCH))
        if client_tools.TRACKER_FIND_USER in tools:
            out.append((case, "tracker_users", client_tools.TRACKER_FIND_USER))
    return out


def test_a_substituted_key_finds_nothing() -> list[str]:
    """Подменённый ключ поиска НЕ НАХОДИТ засеянную строку — ни сам по себе, ни
    вместе с тематическим словом письма.

    THE DECLARATION `mail_find` IS BUILT ON, and it was false. `mock._ranked`
    ranked by word overlap over the CONCATENATION of every column of the row —
    `subject` and the body `template` among them — and admitted on a hit, so
    «Громов заявку» (a substituted surname beside a topic word the gateway
    correctly leaves alone) came back `list total=1`. The stem rule then admitted
    «букицев» against a seeded «букин», because a four-letter stem only had to be
    a PREFIX. Both errors ran one way: a key that should have found nothing found
    the letter, the chain walked on, and `chain_value` never saw the miss.

    THE REAL KEY IS CHECKED IN THE SAME BREATH, and that is what makes this a
    measurement rather than a way of returning `empty` to everything: a fix that
    closed the index would pass the first half and fail the second.
    """
    problems: list[str] = []
    for case, table, tool in _searchers(ALL_CASES):
        backend = seed_backend_v5(case)
        rows = backend._tables[table]                       # noqa: SLF001 - the seeded world
        if len(rows) != 1:
            problems.append(f"{case.base.id}: {table} holds {len(rows)} rows; this check "
                            f"names the one the case seeded")
            continue
        record = next(iter(rows.values()))
        column = "from_name" if table == "mailbox" else "name"
        real = str(record.fields[column]).split()[0]
        # A word out of the row that is NOT an identity column — the letter's own
        # subject where there is one, the tracker's login where there is not.
        # It is what a gateway leaves alone, and the whole of the first defect
        # was that leaving it alone was enough to find the row.
        words = str(record.fields.get("subject", "")).split()
        topic = words[-1] if words else "задача"
        for query, wanted in ((real, True), (_near_miss(real), False),
                              (f"{_near_miss(real)} {topic}", False)):
            total = _total(backend, tool, query)
            if wanted and total != 1:
                problems.append(f"{case.base.id}: {tool}({query!r}) found {total}; the real "
                                f"key must find the row the case seeded")
            if not wanted and total:
                problems.append(f"{case.base.id}: {tool}({query!r}) found {total}; a key that "
                                f"names nobody must find nothing")
    return problems[:8]


def _total(backend: BackendV5, tool: str, query: str) -> int:
    log = backend.call(tool, {"query": query, "max_results": 5})
    result = log.result if isinstance(log.result, dict) else {}
    return int(result.get("total", 0))


def test_the_directory_answers_are_assignable() -> list[str]:
    """Каждая форма, которой справочник ОТВЕТИЛ агенту, годится в исполнители —
    и чужая фамилия по-прежнему отвергается со значением.

    THE REFUSAL THE CASE NEVER DECLARED. `_tracker_user_named` compared the
    argument with ONE column by exact equality, while `tracker_find_user` answers
    `displayName` («Bukin Sergey»), `login`, `accountId` and `emailAddress` — so
    an agent that assigned the task to what the directory had just handed it got
    `ASSIGNEE_UNKNOWN`, as did «букину» and «букин Андрей». That refusal lands on
    BOTH arms, so it separates nothing; it only deletes the assignee hop and the
    `mail_send` leg behind it.

    AND THE OTHER HALF IN THE SAME CHECK: a stranger is still refused, with the
    value in the body. A widening that swallowed everything would pass the first
    half of this and fail the second.
    """
    problems: list[str] = []
    for case in ALL_CASES:
        if client_tools.TRACKER_ISSUE_CREATE not in {hop.tool_name for hop in case.hops}:
            continue
        backend = seed_backend_v5(case)
        rows = backend._tables.get("tracker_users", {})     # noqa: SLF001 - the seeded world
        if not rows:
            continue
        record = next(iter(rows.values()))
        surname = str(record.fields["name"])
        answered = (surname, f"{surname}у", str(record.fields["display_name"]),
                    str(record.fields["login"]), str(record.fields["account_id"]),
                    str(record.fields["email"]))
        for assignee in answered:
            form = _assign(backend, assignee)
            if form != "single":
                problems.append(f"{case.base.id}: assignee {assignee!r} — a form the "
                                f"directory itself answered with — came back {form!r}")
        stranger = _near_miss(surname)
        if _assign(backend, stranger) != "error_with_value":
            problems.append(f"{case.base.id}: assignee {stranger!r} resolved; a name the "
                            f"directory does not hold must be refused with its value")
    return problems[:8]


def _assign(backend: BackendV5, assignee: str) -> str:
    log = backend.call(client_tools.TRACKER_ISSUE_CREATE,
                       {"project_key": "SUP", "summary": "тема", "description": "текст",
                        "assignee": assignee})
    return backend.form_of(log.seq)


# --- the floor ---------------------------------------------------------------------

def test_every_case_is_valid_and_renders() -> list[str]:
    """Каждый случай проходит `validate_v5` И рендерится РЕАЛЬНЫМ моком.

    The second half is what a declaration cannot promise itself: a hop on a leaf
    the backend never tags is a crossing that scores as a gateway miss for ever,
    and 42% of the revised half's IN/tool hops were exactly that before the
    corpus had to prove itself.
    """
    problems: list[str] = []
    for case in ALL_CASES:
        problems.extend(s.validate_v5(case))
        problems.extend(render_problems(case))
    return problems[:12]


def test_the_new_tools_are_reached_often_enough() -> list[str]:
    """Каждый из одиннадцати новых инструментов доступен в ≥ MIN_TYPE_DENOMINATOR
    случаях — K07's share of this round.

    «Объявить и не покрыть» is the defect class this round exists to close: a
    tool the registry carries and the corpus never puts in front of an agent is a
    declaration with no measurement behind it.

    COUNTED BY HOPS AND NOT BY WHAT WAS OFFERED, which is the rule §8.1bis
    already states for the suite slice: «случай принадлежит набору, если его ХОПЫ
    трогают инструмент набора, — не по `base.tools`: случай, которому инструмент
    лишь предложили и который туда не ходил, попал бы в срез, ничего о нём не
    измеряя». K07 counts `expects.reachable_tools`, so a family that listed a
    tool and never reached it passed both it and this check; today the two
    numbers agree for all eleven (34/34, 10/10, 26/26, 6/6, 12/12, 24/24, 8/8,
    6/6, 6/6, 6/6, 6/6), and an agreement is not a check. Counting the crossing
    makes the weaker reading impossible to hold by accident.
    """
    problems: list[str] = []
    reach: dict[str, int] = {}
    for case in ALL_CASES:
        for tool in {hop.tool_name for hop in case.hops}:
            reach[tool] = reach.get(tool, 0) + 1
    for tool in client_tools.CLIENT_TOOLS:
        if tool not in REGISTRY_V5:
            problems.append(f"{tool!r} is not in REGISTRY_V5; the corpus names a tool the "
                            f"registry does not carry")
            continue
        if reach.get(tool, 0) < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"{tool!r} is crossed by hops in {reach.get(tool, 0)} cases of "
                            f"these five families, below {c.MIN_TYPE_DENOMINATOR}")
        offered = sum(1 for case in ALL_CASES
                      if tool in case.base.expects.reachable_tools)
        if offered != reach.get(tool, 0):
            problems.append(f"{tool!r} is offered to {offered} cases and reached by hops in "
                            f"{reach.get(tool, 0)}: a tool put in front of an agent that no "
                            f"hop crosses is in the suite slice measuring nothing")
    return problems


def test_every_declared_leaf_is_one_the_registry_carries() -> list[str]:
    """Каждый лист из `client_tools` существует в `REGISTRY_V5`.

    `common.arg_hop` already refuses an unknown ARGUMENT leaf at build; a RESULT
    leaf has no such guard — `render_problems` catches it only when a case
    happens to cross it — so the table is checked whole rather than case by case.
    """
    problems: list[str] = []
    for case in ALL_CASES:
        for hop in case.hops:
            if hop.kind != "IN" or hop.owner != "tool":
                continue
            spec = REGISTRY_V5.get(hop.tool_name)
            leaf = s._ARRAY_INDEX.sub("[]", hop.path)          # noqa: SLF001 - one definition
            if spec is None or leaf not in spec.base.result_pii:
                problems.append(f"{case.base.id}: hop {hop.hop_index} reads "
                                f"{hop.tool_name}.{leaf}, which result_pii does not declare")
    return problems[:8]


def test_the_checks_can_fail() -> list[str]:
    """Каждая проверка выше ОБЯЗАНА краснеть на корпусе без своей семьи.

    AN INSTRUMENT THAT CANNOT FAIL IS NOT AN INSTRUMENT, and v4 could not fail in
    four places at once. Each check is re-run over the cases with its own family
    removed, and a check that stays silent there is a check that was measuring
    nothing.
    """
    problems: list[str] = []
    every = dict(BUILT)
    # A CHECK WHOSE CLAIM NO SUBSET CAN BREAK NEEDS A MUTATION, not a smaller
    # corpus. `test_every_case_still_carries_a_speech_negative` is the one: v4's
    # builder supplies the negative, so every corpus that assembles carries it.
    # The mutation is the minimum that makes the claim false — one case with its
    # negatives removed — and it is applied to a COPY, `dataclasses.replace`
    # leaving the built corpus alone.
    for check, mutate in ((test_every_case_still_carries_a_speech_negative, _without_negatives),):
        _swap(mutate(ALL_CASES))
        try:
            if not check():
                problems.append(f"{check.__name__}: said nothing on a corpus mutated to "
                                f"break exactly what it claims")
        finally:
            _swap(tuple(case for cases in every.values() for case in cases))
    # AND THE TWO THAT ARE CLAIMS ABOUT THE MOCK, whose negative is therefore the
    # MOCK'S OWN DIAL and not a smaller corpus. Removing the family leaves them
    # with nothing to look at, which is silence for the wrong reason — the shape
    # that let four v4 checks pass on an empty population. Each rule is loosened
    # back to the exact state the defect was found in: the stem that only had to
    # be a prefix, and the assignee matched against one column.
    problems.extend(_loosened(test_a_substituted_key_finds_nothing, "IDENTITY_TAIL",
                              len("цевский")))
    problems.extend(_loosened(test_a_substituted_key_finds_nothing, "IDENTITY_COLUMNS",
                              {"mailbox": ("from_name", "from_email", "subject", "template"),
                               "tracker_users": mock.BackendV5.IDENTITY_COLUMNS[
                                   "tracker_users"]},
                              on=mock.BackendV5))
    problems.extend(_loosened(test_the_directory_answers_are_assignable,
                              "_ASSIGNEE_COLUMNS", ("name",), on=mock.BackendV5))
    # WHAT HAS TO GO IS EVERY FAMILY THAT SUPPLIES THE LINE, not the one that
    # supplies most of it — and two of these were written wrong the first time
    # and said nothing. Both mail families read a letter in both shapes, and both
    # `mail_loop` and `assistant_writes` put two people into one list, so
    # removing one of each pair left the check with a population and a pass. A
    # negative that removes half the evidence proves half of nothing.
    for check, families in ((test_the_head_loop_is_measured, ("mail_loop",)),
                            (test_both_letter_shapes_are_read, ("mail_loop", "mail_find")),
                            (test_personal_data_is_a_search_key, ("mail_find",)),
                            (test_a_person_is_named_in_an_argument, ("tracker",)),
                            (test_two_dimensions_and_a_long_text, ("office",)),
                            (test_several_people_in_one_argument,
                             ("mail_loop", "assistant_writes")),
                            (test_machine_identifiers_stand_beside_real_values, ("office",)),
                            (test_the_new_tools_are_reached_often_enough, ("office",))):
        kept = {name: cases for name, cases in every.items() if name not in families}
        _swap(tuple(case for cases in kept.values() for case in cases))
        try:
            if not check():
                problems.append(f"{check.__name__}: said nothing with "
                                f"{', '.join(families)} removed")
        finally:
            _swap(tuple(case for cases in every.values() for case in cases))
    return problems


def _loosened(check: object, name: str, value: object,
              on: object = mock) -> list[str]:
    """Run one check with a single rule of the mock widened back, and demand red.

    THE DIAL AND NOT A REWRITE. Both defects were one constant too generous —
    `IDENTITY_TAIL` letting a query word run any distance past the stem it
    shares, and `_ASSIGNEE_COLUMNS` holding the one column exact equality was
    ever tried against. Restoring the constant restores the defect exactly, so a
    check that stays green under it was never watching the rule it names.
    """
    was = getattr(on, name)
    setattr(on, name, value)
    try:
        if not check():                                         # type: ignore[operator]
            return [f"{check.__name__}: said nothing with "     # type: ignore[attr-defined]
                    f"{name} widened back to the state the defect was found in"]
        return []
    finally:
        setattr(on, name, was)


def _without_negatives(cases: tuple[CaseV5, ...]) -> tuple[CaseV5, ...]:
    """The same corpus with the FIRST case's negatives removed — the smallest
    edit that makes «every case carries one» false."""
    head = cases[0]
    stripped = replace(head, base=replace(head.base, negatives=()))
    return (stripped,) + cases[1:]


def _swap(cases: tuple[CaseV5, ...]) -> None:
    """Point every check at another corpus for the length of one negative.

    THE MODULE GLOBAL AND NOT A PARAMETER, because the checks above are the
    functions the runner calls and a parameter they never receive in anger would
    be a second code path — exactly the shape that let v4 ship four checks which
    could not fail. It is restored in a `finally`.
    """
    global ALL_CASES                                            # noqa: PLW0603 - see above
    ALL_CASES = cases


CHECKS: tuple[object, ...] = (
    test_the_head_loop_is_measured, test_both_letter_shapes_are_read,
    test_personal_data_is_a_search_key, test_a_person_is_named_in_an_argument,
    test_two_dimensions_and_a_long_text, test_several_people_in_one_argument,
    test_machine_identifiers_stand_beside_real_values,
    test_a_substituted_key_finds_nothing, test_the_directory_answers_are_assignable,
    test_every_case_still_carries_a_speech_negative, test_every_case_is_valid_and_renders,
    test_the_new_tools_are_reached_often_enough,
    test_every_declared_leaf_is_one_the_registry_carries, test_the_checks_can_fail)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()                                      # type: ignore[operator]
        name = check.__name__                                   # type: ignore[attr-defined]
        if problems:
            failures += 1
            print(f"FAIL {name}")
            for problem in problems:
                print(f"     {problem}")
        else:
            print(f"ok   {name}")
    crossings = _free_text_transitions(ALL_CASES)
    letters = [one for one in crossings if one[1] == client_tools.MAIL_READ]
    print(f"случаев: {len(ALL_CASES)} · семей: {len(BUILT)} · проверок: {len(CHECKS)} · "
          f"провалов: {failures}")
    print(f"петля «письмо → инструмент»: {len(letters)} переходов из прозы письма "
          f"в {len({one[2] for one in letters})} разных стока; в корпусе до этого — 0")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
