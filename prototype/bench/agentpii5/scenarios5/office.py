"""`office` — ПД в ДВУМЕРНОЙ структуре и в длинном свободном тексте на ЗАПИСЬ.

TWO FORMS THE CORPUS DOES NOT HAVE AT ALL. Its nearest thing to a spreadsheet is
`crm_import_csv(csv)` — ONE string-container argument, fifteen cases — and its
nearest thing to writing a document is nothing: `doc_retrieve` (21 expectations),
`file_read` (330 IN/document hops) and the whole `document` family READ, and not
one tool in the registry PUTS a long free text back. So «строка таблицы» and
«дописать документ» — two of the commonest things an assistant does all day —
are measured by zero hops.

THE TWO-DIMENSIONALITY IS MEASURED ON THE WRITE SIDE, AND THAT IS WHERE IT HURTS.
A spreadsheet row is `values[][]`: five cells of one person crossing ONE declared
leaf, in an order the range names. A gateway that resolves four of the five and
drops the fifth writes a row that looks complete and is not — and, unlike a typed
argument, nothing downstream fails. The range itself (`Лист1!A3:E3`) is a machine
address standing right beside the personal data, which is why it is written into
the message as a `plain_value`: a substitute there writes the row into another
part of the sheet and returns 200.

THE SOURCE IS A FILE, SO THE BEHAVIOUR IS `document`. The values are read out of
an attachment (`IN/document`) and written into the sheet or the document
(`OUT/tool_arg`, `OUT/summary`); `DocumentSpec.extract_to_tool` names the sink and
`doc_extracted` counts exactly the items with an OUT hop into it, which is the
denominator H4.1 spent a round fixing.

THE CALLER IS NEVER THE PERSON IN THE FILE, for the mock's reason rather than for
tidiness: it drops a by-value tag two seeded items share, so a name in both the
caller's card and the payload would be tagged in neither.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import DocumentSpec, ReturnExpectation
from bench.agentpii5.scenarios5 import client_tools as t
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_b import (answer_hop, arg_hop, caller_card, city_for,
                                               document_hop, extra_people, find_the_caller,
                                               stored_name, stored_phone, stored_street,
                                               told, tool_hop, user_hop)
from bench.agentpii5.tools import FILE_EXTENSIONS

BEHAVIOUR: str = "document"
TOOLS: tuple[str, ...] = ("file_read", "crm_find_contact", t.SHEET_APPEND_ROW, t.DOC_APPEND)
_SHEET_TOOLS: tuple[str, ...] = ("file_read", "crm_find_contact", t.SHEET_APPEND_ROW)
_DOC_TOOLS: tuple[str, ...] = ("file_read", "crm_find_contact", t.DOC_APPEND)
# Half the family to each sink, by index and never by a draw: `sheet_append_row`
# and `doc_append` each need `MIN_TYPE_DENOMINATOR` cases of their own (K07), and
# a drawn sink would make that a property of the seed.
PER_SINK: int = 6
# How many people the uploaded list carries. Two is R18's floor for a `csv`
# document; three is what makes «write the right one into the sheet» a question.
CSV_SIZES: tuple[int, int] = (2, 3)
# The columns of the CSV row that go into the sheet, in the order the range
# names them. ONE tuple: the hops, the arguments and `DocumentSpec` all read it,
# and a column named twice is a column that can be named differently twice.
SHEET_COLUMNS: tuple[str, ...] = ("last_name", "first_name", "phone", "email", "birth_date")
# WHICH SHEET AND WHICH DOCUMENT. `mock.call_arguments` reads both off the row
# the case SEEDED (`_seeded_id`), the way it reads a file path, so the ids are
# never dictated and never invented; a sheet the case did not seed answers
# `error_with_value` and a document it did not seed answers DOCUMENT_NOT_FOUND.
#
# THE SHAPE IS THE READER'S, NOT OURS. `tools.SHEET_ID_RE` accepts «sh-N» and
# `DOC_ID_RE` accepts «doc-N»; a row seeded as «sht-1» was refused with
# `id_format` on every case, which `mock.render_problems` named — the same trap
# `sequential_chain` hit with «tkt-1» against a reader that takes «t-N».
SHEET_ID: str = "sh-1"
SHEET_TITLE: str = "Лист1"
# The prose an internal protocol is written in. `{who}`, `{tel}` and `{street}`
# name columns of the same row; `mock._template_pieces` renders each in that
# column's prose notation and tags the piece with the item bound to it, so the
# offsets are laid as the text is composed.
PROTOCOL_TEXT: str = ("Протокол осмотра. Клиент {who}, контактный телефон {tel}, "
                      "объект по адресу {street}. Замечаний нет.")
OFFICE_CLAUSE: str = ("Данные бери из приложенного файла: сначала прочитай его инструментом, "
                      "потом переноси значения оттуда, ничего не придумывая.")


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(f"{BEHAVIOUR}:office", seed, index, registers[index]))
            for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    shapes = (_to_sheet, _to_doc)
    return shapes[min(ctx.index // PER_SINK, len(shapes) - 1)](ctx)


def _path(ctx: c.Ctx, stem: str, extension: str) -> str:
    """Where the attachment sits. It carries the case index so two cases of one
    run cannot collide in the mock's `documents` table, and the extension is one
    `tools.FILE_EXTENSIONS` accepts — `file_read` refuses anything else with a
    documented `path_extension` rule, and a case that provokes a refusal it did
    not declare measures the refusal."""
    if f".{extension}" not in FILE_EXTENSIONS:
        raise pools.BuildError(f"{extension!r} is not one of {FILE_EXTENSIONS}")
    return f"/upload/{stem}-{ctx.index}.{extension}"


def _open(ctx: c.Ctx, tools: tuple[str, ...], note: str,
          path: str) -> tuple[c.CaseBuilderV5, c.Drawn, str, str, dict[str, str]]:
    """The caller, their seeded card, and a prompt that names the attachment.

    THE PATH IS CONFIGURATION, NOT SPEECH. «/upload/spisok-3.csv» carries dots
    and a digit run, and zero of 53 324 measured utterances dictate one; the
    attachment a customer's own gateway passes in arrives as configuration, which
    is where this puts it.
    """
    identity = f"p{ctx.index}"
    city = city_for(ctx)
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "crm", tools, tools, identity, f"PHONE:{drawn.phone}",
                            note, (OFFICE_CLAUSE, f"Приложенный файл: {path}."))
    builder.v4.conversation_id = t.conversation_id("office", ctx.index)
    card = caller_card(builder, ctx, drawn, city, identity)
    return builder, drawn, identity, city, card


def _to_sheet(ctx: c.Ctx) -> Case:
    """Файл со списком → СТРОКА таблицы: пять ячеек, один вызов, один диапазон."""
    path = _path(ctx, "spisok", "csv")
    builder, drawn, identity, city, card = _open(
        ctx, _SHEET_TOOLS, "список из файла → строка таблицы: пять ячеек в одном "
        "двумерном аргументе, диапазон рядом с ними обязан уцелеть", path)
    size = CSV_SIZES[ctx.index % len(CSV_SIZES)]
    people = extra_people(ctx, city, drawn, size)
    fields: dict[str, object] = {
        "rows": {str(position): c.csv_row_fields(person)
                 for position, person in enumerate(people)}}
    typed: dict[str, tuple[str, str, pools.Rendered]] = {}
    for position, person in enumerate(people):
        typed.update(c.csv_row_typed(position, person, f"{identity}f{position}"))
    doc_id = t.document_key(ctx.index)
    rows = c.document_seed(doc_id, path, "csv", "Список на внесение", fields, typed, builder)
    # THE SHEET CARRIES NO PERSONAL DATUM OF ITS OWN, and that is why it is
    # seeded with no typed path: the row this case writes is the first one, so
    # everything in the table afterwards came out of the file. A seeded person in
    # it would be a second copy of somebody the CSV already holds, which the
    # mock's by-value index drops — both untagged, every hop unobservable.
    c.seeded(builder, SHEET_ID, "sheets", {"title": SHEET_TITLE, "rows": []}, {})

    cells = tuple(rows[c.csv_row_path(0, column)] for column in SHEET_COLUMNS)
    turn, said = _ask(builder, ctx, drawn, identity,
                      "внесите первого из списка в таблицу",
                      ("в", t.sheet_range(ctx.index), t.CELL_RANGE_FAMILY, t.CELL_RANGE_WHY))
    builder.v4.must_contain = (drawn.person.surname[0],)
    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    surname_hop, index = find_the_caller(builder, card, said["ph"], turn, 1)
    read: dict[str, int] = {}
    for column in SHEET_COLUMNS:
        builder.declare_hop(document_hop(rows[c.csv_row_path(0, column)], index, turn,
                                         "file_read", 0, c.csv_row_path(0, column)))
        read[column] = index
        index += 1
    # EVERY CELL IS ITS OWN HOP AT ITS OWN (row, column), and that is the form
    # rather than a flourish: a row is not one value, so a gateway that resolves
    # four of the five writes a row that looks complete and is not. Joining them
    # would give this argument the shape `crm_import_csv` already has.
    for column_index, column in enumerate(SHEET_COLUMNS):
        builder.declare_hop(arg_hop(
            rows[c.csv_row_path(0, column)], index, turn, t.SHEET_APPEND_ROW, 0,
            t.at(t.SHEET_VALUES, row=0, column=column_index), read[column], ""))
        index += 1
    # WHAT THE SHEET SAYS IT WROTE. A spreadsheet API answers an append with the
    # range it touched and the values it stored, and reading that back is the
    # only way the corpus can tell «the row went in» from «the row went in
    # wrong»: a gateway that resolved four cells of five leaves a row that looks
    # complete, and nothing downstream fails.
    for column in SHEET_COLUMNS:
        builder.declare_hop(tool_hop(rows[c.csv_row_path(0, column)], index, turn,
                                     t.SHEET_APPEND_ROW, 0, t.SHEET_ECHO))
        index += 1
    builder.declare_hop(answer_hop(card["last_name"], index, turn, surname_hop, False))
    builder.expect_return(ReturnExpectation(
        "file_read", 0, "list",
        tuple(rows[c.csv_row_path(position, column)]
              for position in range(size) for column in SHEET_COLUMNS)))
    builder.expect_return(ReturnExpectation(t.SHEET_APPEND_ROW, 0, "list", cells))
    # ONE `documents` row holding `size` people: `record_count` counts the
    # people, `record_ids` the row (ruling R-30).
    builder.set_document(DocumentSpec(
        doc_id, "file_read", "csv", size, (doc_id,), t.SHEET_APPEND_ROW, cells))
    return builder.build(BEHAVIOUR)


def _to_doc(ctx: c.Ctx) -> Case:
    """Протокол в свободном тексте → ДОПИСАТЬ в него абзац: ПД внутри длинного текста.

    THE SINK IS A SUMMARY LEAF. The agent is not copying a field into a field: it
    writes a paragraph in its own words carrying three values it has just read,
    so the form the real value must take on the way out is the AGENT's — which is
    exactly what `form_hOUT`'s summary line exists to score and what no writing
    tool in the corpus offered it.

    IT APPENDS TO THE DOCUMENT IT READ, and that is the mock's contract rather
    than a simplification: `mock.call_arguments` gives `doc_append` the id of the
    row the case seeded, and a second `documents` row would be a page the driver
    never opens. A working assistant does the same thing — the protocol it was
    handed is the protocol it writes the outcome into.
    """
    path = _path(ctx, "protokol", "txt")
    builder, drawn, identity, city, card = _open(
        ctx, _DOC_TOOLS, "протокол из файла → абзац в том же документе: длинный свободный "
        "текст, который агент пишет сам, с ПД внутри", path)
    client = extra_people(ctx, city, drawn, 1)[0]
    client_identity = f"{identity}f0"
    doc_id = t.document_key(ctx.index)
    protocol = c.document_seed(
        doc_id, path, "free_text", "Протокол осмотра",
        {"template": PROTOCOL_TEXT, "who": stored_name(client, ctx).surface,
         "tel": f"+7{client.phone}", "street": client.address.street},
        {"who": ("NAME", client_identity, stored_name(client, ctx)),
         "tel": ("PHONE", client_identity, stored_phone(client)),
         "street": ("LOC", f"{client_identity}.home", stored_street(client))},
        builder)

    turn, said = _ask(builder, ctx, drawn, identity,
                      "допишите в протокол итог осмотра",
                      ("в документ", doc_id, t.RECORD_KEY_FAMILY, t.RECORD_KEY_WHY))
    builder.v4.must_contain = (drawn.person.surname[0],)
    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    surname_hop, index = find_the_caller(builder, card, said["ph"], turn, 1)
    read: dict[str, int] = {}
    for column in ("who", "tel", "street"):
        builder.declare_hop(document_hop(protocol[column], index, turn, "file_read", 0, "text"))
        read[column] = index
        index += 1
    for column in ("who", "tel", "street"):
        builder.declare_hop(arg_hop(protocol[column], index, turn, t.DOC_APPEND, 0, t.DOC_TEXT,
                                    read[column], ""))
        index += 1
    # THE WHOLE PAGE COMES BACK, which is how a wiki answers a write, and the
    # seeded prose inside it is tagged while the agent's own paragraph is not.
    # So the same three values are read out of a DOCUMENT and then out of a TOOL
    # RESULT, which are two different notation problems for a gateway.
    for column in ("who", "tel", "street"):
        builder.declare_hop(tool_hop(protocol[column], index, turn, t.DOC_APPEND, 0,
                                     t.DOC_BODY))
        index += 1
    builder.declare_hop(answer_hop(card["last_name"], index, turn, surname_hop, False))
    builder.expect_return(ReturnExpectation(
        "file_read", 0, "free_text",
        (protocol["who"], protocol["tel"], protocol["street"])))
    builder.expect_return(ReturnExpectation(
        t.DOC_APPEND, 0, "single",
        (protocol["who"], protocol["tel"], protocol["street"])))
    builder.set_document(DocumentSpec(
        doc_id, "file_read", "free_text", 1, (doc_id,), t.DOC_APPEND,
        (protocol["who"], protocol["tel"], protocol["street"])))
    return builder.build(BEHAVIOUR)


def _ask(builder: c.CaseBuilderV5, ctx: c.Ctx, drawn: c.Drawn, identity: str, request: str,
         machine: tuple[str, str, str, str]) -> tuple[int, dict[str, str]]:
    """The caller's one message: who they are, what to do, and the machine
    address the call will also carry.

    `machine` is `(the words before it, the value, its family, why it must
    survive)`, and it goes through `client_tools.say_machine_id`, which skips
    `voice_raw` — v4's gate refuses a digit or sentence punctuation there and
    «Лист1!A3:E3» carries both. It is a `plain_value` rather than a `Negative`
    because
    `agentpii3.NEGATIVE_FAMILIES` is a CLOSED tuple of ten speech families and
    `v4.validate` refuses anything else — filing a cell range under
    «order_number» to get it counted would put a machine address into a number
    that is read as speech precision. The value stands beside the personal data
    where the customer's own traffic puts it; the line that counts it is named in
    the handover as the contract change it is.
    """
    words, value, family, why = machine
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это")
    draft.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    draft.say("телефон")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say(request)
    t.say_machine_id(draft, ctx, words, value, family, why)
    draft.punct(".")
    return told(builder, draft, {"name": ("NAME", identity, "required", False),
                                 "ph": ("PHONE", identity, "required", False)})


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.office` — build and report."""
    cases = build(4, 12)
    sinks = sorted({case.document.extract_to_tool for case in cases
                    if case.document is not None})
    print(f"office: {len(cases)} cases, sinks {sinks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
