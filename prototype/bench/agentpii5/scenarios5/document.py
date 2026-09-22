"""`document` — the personal data arrives inside a FILE the agent opened.

WHY A FILE IS NOT JUST ANOTHER TOOL RESULT. A JSON result is typed: the gateway
knows `contacts[].phone` is a phone before it looks at it. A payload is not. A
CSV row is five columns of text, a filled application form is a nested blob a
parser guessed at, and a scan is the same text with an OCR's damage on it —
«Пeтpов» with two Latin letters inside a Cyrillic surname. Detection has to work
on the CONTENT, the way it does on a customer's own message, except that nobody
dictated this and nothing about it is in the register the conversation is in.

FOUR FORMATS, TWENTY-FIVE CASES EACH, AND THEY ARE FOUR DIFFERENT QUESTIONS:
  `csv`       — several people in one payload, the gateway must keep them apart
                when the agent imports one of them;
  `form`      — one person, deep structure, the identifiers a form carries and a
                chat never does (passport in two halves, СНИЛС with separators);
  `free_text` — prose the customer's own system wrote, values in ITS notation;
  `scan`      — the same prose with OCR damage, which is the register no corpus
                of typed or dictated text contains.

A CSV IS ONE LINE OR A TABLE, NEVER A FILE WITH NEWLINES. v4's writer refuses a
control character inside a slot, because an escaped value no longer equals the
span laid down for it (ruling R-21). So `file_read` on a CSV answers its `list`
form, row by row, and a document read as TEXT is one line joined with « | ».
The instrument's constraint is stated here rather than worked around.

THE CALLER IS NEVER THE PERSON IN THE FILE. The caller has a CRM card and gives
their own phone; the file carries somebody else. The mock drops a by-value tag
that two items share, so a name in both would be tagged in neither and every hop
on the document would read as a gateway miss no gateway could avoid.

THE INN AND THE PLATE LIVE HERE. v4 carried neither (`V4_TYPE_ITEM_COUNTS` has
both at zero), and K05 asks for sixty cases of each. The free-text protocol
carries an ИНН and extracts it into `bank_client_find`; the scan carries a plate
and extracts it into `vehicle_check` — twenty-five cases each, this half's share
of the floor.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.schema import Case
from bench.agentpii5.contracts import DocumentSpec, ReturnExpectation
from bench.agentpii5.scenarios5 import common as c
from bench.agentpii5.scenarios5.plan_b import (answer_hop, arg_hop, caller_card, city_for,
                                               conversation_id, document_hop, extra_people,
                                               find_the_caller, stored_name, stored_phone,
                                               stored_street, told, user_hop)
from bench.agentpii5.tools import FILE_EXTENSIONS

BEHAVIOUR: str = "document"
TOOLS: tuple[str, ...] = (
    "file_read", "form_parse", "doc_retrieve", "crm_find_contact", "crm_upsert_contact",
    "passport_verify", "bank_client_find", "vehicle_check")
_CSV_TOOLS: tuple[str, ...] = ("file_read", "crm_find_contact", "crm_upsert_contact")
_FORM_TOOLS: tuple[str, ...] = ("form_parse", "crm_find_contact", "passport_verify")
_TEXT_TOOLS: tuple[str, ...] = ("file_read", "doc_retrieve", "crm_find_contact",
                                "bank_client_find")
_SCAN_TOOLS: tuple[str, ...] = ("file_read", "crm_find_contact", "vehicle_check")

# The prose the customer's own systems wrote. `{slot}` names a column of the same
# row; `mock._template_pieces` reads it there, renders it in that field's prose
# notation and tags the piece with the item bound to the column.
PROTOCOL_TEXT: str = ("Акт сверки. Контрагент {who}, ИНН {inn}, контактный телефон {tel}, "
                      "адрес {street}. Расхождений не выявлено.")
SCAN_TEXT: str = ("Заявление на пропуск. Заявитель {who}, телефон {tel}, "
                  "транспортное средство {plate}, адрес {street}.")
# How many people a CSV carries. Two is the floor R18 puts on the format; three
# is what makes «keep them apart» a question rather than a coin toss, so the
# rows alternate by index instead of being drawn.
CSV_SIZES: tuple[int, int] = (2, 3)
# Twenty-five cases per format: the format is decided by the index, never by a
# draw, because K14 counts formats and a draw would make the count a property of
# the seed.
PER_FORMAT: int = 25
# The extensions `tools.file_read` accepts, IMPORTED rather than restated
# (ruling R-29). The restated copy needed a test to pin the two equal, and a
# test that keeps two literals equal is a definition written twice with a
# reminder attached.


def build(seed: int, count: int) -> list[Case]:
    registers = c.registers_for(count, c.ctx_for(BEHAVIOUR, seed, 0, "chat").rng)
    return [_one(c.ctx_for(BEHAVIOUR, seed, index, registers[index])) for index in range(count)]


def _one(ctx: c.Ctx) -> Case:
    shapes = (_csv_shape, _form_shape, _text_shape, _scan_shape)
    return shapes[min(ctx.index // PER_FORMAT, len(shapes) - 1)](ctx)


def _path(ctx: c.Ctx, stem: str, extension: str) -> str:
    """Where the payload sits. It carries the case index so two cases of one run
    cannot collide in the mock's `documents` table.

    THE EXTENSION IS ONE `tools.FILE_EXTENSIONS` ACCEPTS, and the tuple is the
    tools component's own. `file_read` refuses
    anything else with a documented `path_extension` refusal, which the mock
    records as `error_with_value` — so a scan called `.pdf` produced a case
    whose every declared IN/document hop could never happen. A corpus that
    provokes a refusal it did not declare measures the refusal.
    """
    if f".{extension}" not in FILE_EXTENSIONS:
        raise pools.BuildError(f"{extension!r} is not one of {FILE_EXTENSIONS}")
    return f"/upload/{stem}-{ctx.index}.{extension}"


def _open(ctx: c.Ctx, tools: tuple[str, ...], reachable: tuple[str, ...], note: str,
          path: str) -> tuple[c.CaseBuilderV5, c.Drawn, str, str, dict[str, str]]:
    """The caller, their seeded card, and a prompt that names the file.

    THE PATH IS IN THE SYSTEM PROMPT AND NOT IN THE CUSTOMER'S MESSAGE, and that
    is v4's register gate rather than a preference: «/upload/clients-12.csv»
    carries digits and a full stop, and a spoken message may carry neither —
    zero of 53 324 measured utterances do. A caller who dictates a file path is
    not a caller anybody has, and the attachment a customer's own gateway passes
    in arrives as configuration, which is exactly where this puts it.
    """
    identity = f"p{ctx.index}"
    city = city_for(ctx)
    drawn = c.draw(ctx, city=city)
    builder = c.new_builder(ctx, "crm", tools, reachable, identity, f"PHONE:{drawn.phone}",
                            note, (c.DOCUMENT_CLAUSE, f"Приложенный файл: {path}."))
    builder.v4.conversation_id = conversation_id(BEHAVIOUR, ctx.index)
    card = caller_card(builder, ctx, drawn, city, identity)
    return builder, drawn, identity, city, card


def _ask(builder: c.CaseBuilderV5, ctx: c.Ctx, drawn: c.Drawn, identity: str,
         request: str) -> tuple[int, dict[str, str]]:
    draft = builder.draft()
    draft.say(c.opener(ctx)).say("это")
    draft.value("name", c.name(ctx, drawn.person, ("surname", "given")))
    draft.say("телефон")
    draft.value("ph", c.phone(ctx, drawn.phone))
    draft.say(request)
    draft.punct(".")
    return told(builder, draft, {"name": ("NAME", identity, "required", False),
                                 "ph": ("PHONE", identity, "required", False)})


def _csv_shape(ctx: c.Ctx) -> Case:
    """A client list the caller uploaded: two or three people, one imported."""
    path = _path(ctx, "clients", "csv")
    builder, drawn, identity, city, card = _open(
        ctx, _CSV_TOOLS, ("file_read", "crm_find_contact", "crm_upsert_contact"),
        "csv на несколько человек: агент читает файл и заводит одного из них", path)
    size = CSV_SIZES[ctx.index % len(CSV_SIZES)]
    people = extra_people(ctx, city, drawn, size)
    fields: dict[str, object] = {"rows": [c.csv_row_fields(person) for person in people]}
    typed: dict[str, tuple[str, str, pools.Rendered]] = {}
    for position, person in enumerate(people):
        typed.update(c.csv_row_typed(position, person, f"{identity}f{position}"))
    rows = c.document_seed("doc-csv", path, "csv", "Выгрузка клиентов", fields, typed, builder)

    turn, said = _ask(builder, ctx, drawn, identity,
                      "я прислал файл со списком загрузите оттуда первого клиента")
    builder.v4.must_contain = (str(drawn.person.surname[0]),)
    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    surname_hop, index = find_the_caller(builder, card, said["ph"], turn, 1)
    # Only the FIRST row is imported; the other rows are what the gateway has to
    # not mix into the call, and a case that imported them all would have no
    # wrong answer available.
    imported = ("last_name", "first_name", "phone", "email", "birth_date")
    leaves = {"last_name": "contact.last_name", "first_name": "contact.first_name",
              "phone": "contact.phone", "email": "contact.email",
              "birth_date": "contact.birth_date"}
    read_hops: dict[str, int] = {}
    for column in imported:
        builder.declare_hop(document_hop(rows[f"rows[0].{column}"], index, turn, "file_read",
                                         0, f"rows[0].{column}"))
        read_hops[column] = index
        index += 1
    for column in imported:
        builder.declare_hop(arg_hop(rows[f"rows[0].{column}"], index, turn,
                                    "crm_upsert_contact", 0, leaves[column],
                                    read_hops[column], ""))
        index += 1
    builder.declare_hop(answer_hop(card["last_name"], index, turn, surname_hop, False))
    builder.expect_return(ReturnExpectation(
        "file_read", 0, "list",
        tuple(rows[f"rows[{position}].{column}"]
              for position in range(size) for column in imported)))
    # ONE `documents` row holding `size` people: `record_count` counts the
    # people, `record_ids` the row (ruling R-30).
    builder.set_document(DocumentSpec(
        "doc-csv", "file_read", "csv", size, ("doc-csv",), "crm_upsert_contact",
        tuple(rows[f"rows[0].{column}"] for column in imported)))
    return builder.build(BEHAVIOUR)


def _form_shape(ctx: c.Ctx) -> Case:
    """A filled application form: one person, ФИО, ДР, паспорт, СНИЛС, адрес —
    and the identifiers go straight into the state check that needs them."""
    path = _path(ctx, "anketa", "docx")
    builder, drawn, identity, city, card = _open(
        ctx, _FORM_TOOLS, ("form_parse", "crm_find_contact", "passport_verify"),
        "анкета: паспорт и СНИЛС из разобранной формы уходят в проверку", path)
    applicant = extra_people(ctx, city, drawn, 1)[0]
    applicant_identity = f"{identity}f0"
    series, number = pools.passport_digits(ctx.rng)
    snils_digits = pools.snils_digits(ctx.rng)
    fields = c.form_document_fields(applicant, city, series, number, snils_digits)
    typed = c.form_document_typed(applicant, ctx, series, number, snils_digits,
                                  applicant_identity)
    form = c.document_seed("doc-form", path, "form", "Анкета заявителя", fields, typed, builder)

    turn, said = _ask(builder, ctx, drawn, identity,
                      "разберите приложенную анкету и проверьте документы заявителя")
    builder.v4.must_contain = (str(drawn.person.surname[0]),)
    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    surname_hop, index = find_the_caller(builder, card, said["ph"], turn, 1)
    parsed = (("last_name", "fields.person.last_name", "person.last_name"),
              ("first_name", "fields.person.first_name", "person.first_name"),
              ("birth_date", "fields.birth_date", "person.birth_date"),
              ("passport_series", "fields.passport.series", "passport.series"),
              ("passport_number", "fields.passport.number", "passport.number"),
              ("snils", "fields.snils", "snils"))
    read_hops: dict[str, int] = {}
    for column, result_path, _argument in parsed:
        builder.declare_hop(document_hop(form[column], index, turn, "form_parse", 0,
                                         result_path))
        read_hops[column] = index
        index += 1
    for column, _result_path, argument in parsed:
        builder.declare_hop(arg_hop(form[column], index, turn, "passport_verify", 0, argument,
                                    read_hops[column], ""))
        index += 1
    builder.declare_hop(answer_hop(card["last_name"], index, turn, surname_hop, False))
    builder.expect_return(ReturnExpectation(
        "form_parse", 0, "nested", tuple(form[column] for column, _p, _a in parsed)))
    builder.set_document(DocumentSpec(
        "doc-form", "form_parse", "form", 1, ("doc-form",), "passport_verify",
        tuple(form[column] for column, _p, _a in parsed)))
    return builder.build(BEHAVIOUR)


def _text_shape(ctx: c.Ctx) -> Case:
    """A reconciliation act in prose, carrying an ИНН the agent must look up."""
    path = _path(ctx, "akt", "txt")
    builder, drawn, identity, city, card = _open(
        ctx, _TEXT_TOOLS, ("file_read", "crm_find_contact", "bank_client_find"),
        "акт сверки в свободном тексте: ИНН контрагента уходит в поиск клиента банка",
        path)
    counterparty = extra_people(ctx, city, drawn, 1)[0]
    counterparty_identity = f"{identity}f0"
    inn_digits = pools.inn12_digits(ctx.rng)
    act = c.document_seed(
        "doc-text", path, "free_text", "Акт сверки",
        {"template": PROTOCOL_TEXT, "who": stored_name(counterparty, ctx).surface,
         "inn": inn_digits, "tel": f"+7{counterparty.phone}",
         "street": counterparty.address.street},
        {"who": ("NAME", counterparty_identity, stored_name(counterparty, ctx)),
         "inn": ("INN", counterparty_identity, pools.Rendered(
             inn_digits, inn_digits, False, {"digits": inn_digits})),
         "tel": ("PHONE", counterparty_identity, stored_phone(counterparty)),
         "street": ("LOC", f"{counterparty_identity}.home", stored_street(counterparty))},
        builder)

    turn, said = _ask(builder, ctx, drawn, identity,
                      "прочитайте приложенный акт и найдите контрагента по его инн")
    builder.v4.must_contain = (str(drawn.person.surname[0]),)
    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    surname_hop, index = find_the_caller(builder, card, said["ph"], turn, 1)
    for column in ("who", "inn", "tel"):
        builder.declare_hop(document_hop(act[column], index, turn, "file_read", 0, "text"))
        index += 1
    builder.declare_hop(arg_hop(act["inn"], index, turn, "bank_client_find", 0, "inn",
                                index - 2, ""))
    builder.declare_hop(answer_hop(card["last_name"], index + 1, turn, surname_hop, False))
    builder.expect_return(ReturnExpectation(
        "file_read", 0, "free_text",
        (act["who"], act["inn"], act["tel"], act["street"])))
    builder.set_document(DocumentSpec(
        "doc-text", "file_read", "free_text", 1, ("doc-text",), "bank_client_find",
        (act["inn"], act["who"])))
    return builder.build(BEHAVIOUR)


def _scan_shape(ctx: c.Ctx) -> Case:
    """A scanned pass application: the same prose with OCR damage, and a plate.

    THE DAMAGE IS THE MOCK'S AND IS SEEDED BY THE DOCUMENT ID, so every arm of
    the same case reads the same page. A noise the SCENARIO applied would be a
    noise the control arm and the gateway arm could disagree about, and the two
    arms would stop being comparable.
    """
    path = _path(ctx, "skan", "docx")
    builder, drawn, identity, city, card = _open(
        ctx, _SCAN_TOOLS, ("file_read", "crm_find_contact", "vehicle_check"),
        "скан заявления: по распознанному номеру агент проверяет транспорт", path)
    applicant = extra_people(ctx, city, drawn, 1)[0]
    applicant_identity = f"{identity}f0"
    plate_text = c.plate_text(ctx.rng)
    scan = c.document_seed(
        "doc-scan", path, "scan", "Скан заявления",
        {"template": SCAN_TEXT, "who": stored_name(applicant, ctx).surface,
         "tel": f"+7{applicant.phone}", "plate": plate_text,
         "street": applicant.address.street},
        {"who": ("NAME", applicant_identity, stored_name(applicant, ctx)),
         "tel": ("PHONE", applicant_identity, stored_phone(applicant)),
         "plate": ("PLATE", applicant_identity, c.plate(_clean_ctx(ctx), plate_text)),
         "street": ("LOC", f"{applicant_identity}.home", stored_street(applicant))},
        builder)

    turn, said = _ask(builder, ctx, drawn, identity,
                      "тут скан заявления пробейте машину заявителя по номеру")
    builder.v4.must_contain = (str(drawn.person.surname[0]),)
    builder.declare_hop(user_hop(said["name"], 0, turn))
    builder.declare_hop(user_hop(said["ph"], 1, turn))
    surname_hop, index = find_the_caller(builder, card, said["ph"], turn, 1)
    for column in ("who", "plate", "street"):
        builder.declare_hop(document_hop(scan[column], index, turn, "file_read", 0, "text"))
        index += 1
    builder.declare_hop(arg_hop(scan["plate"], index, turn, "vehicle_check", 0, "plate",
                                index - 2, ""))
    builder.declare_hop(answer_hop(card["last_name"], index + 1, turn, surname_hop, False))
    builder.expect_return(ReturnExpectation(
        "file_read", 0, "free_text",
        (scan["who"], scan["tel"], scan["plate"], scan["street"])))
    builder.set_document(DocumentSpec(
        "doc-scan", "file_read", "scan", 1, ("doc-scan",), "vehicle_check",
        (scan["plate"], scan["who"])))
    return builder.build(BEHAVIOUR)


def _clean_ctx(ctx: c.Ctx) -> c.Ctx:
    """The same draw stream in the `clean` register — what a BACKEND column is
    written in. `common.plate` renders by register, and a scanned form does not
    carry «а сто двадцать три вэ эс» because the caller happened to phone in."""
    return c.Ctx(kind=ctx.kind, index=ctx.index, register="clean", rng=ctx.rng, seed=ctx.seed)


def main() -> int:
    """`python3 -m bench.agentpii5.scenarios5.document` — build and report."""
    cases = build(4, 100)
    formats = {case.document.format for case in cases if case.document is not None}
    print(f"{BEHAVIOUR}: {len(cases)} cases, formats {sorted(formats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
