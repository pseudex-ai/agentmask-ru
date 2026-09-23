"""The v5 tool registry: the 31 v4 tools revised + 12 new ones, 11 verticals.

WHY A REGISTRY OF RETURN FORMS AND NOT ONLY OF PARSERS. v4 asked one question
of a tool — did the agent call it with the right arguments — so a `ToolSpec`
needed a schema and a strict parser and nothing more, and 22 of its 31 tools
returned no personal data at all (`result_pii` empty). v5 measures the OTHER
direction too: what the tool RETURNS reaches the model in that API's own
notation («+7 (916) 402-11-87» from DaData, «1987-03-14» from a clinic,
«XXX-XXX-XXX YY» from the ПФР, a card in four groups from a bank), and the
substitute the gateway puts in its place has to wear that notation. A tool
whose result carries nothing has no IN/tool hop to measure, which is why V04
refuses it and why `BackendV5` gives every tool a result that carries a real
value the way the API it mirrors does.

THE v4 SPECS ARE NOT EDITED. A `ToolSpecV5` COMPOSES the imported v4 object
(`base`), and where v4 left `result_pii` empty the v5 value is put on a COPY
made with `dataclasses.replace` — `bench/agentpii4/` is the baseline the
mandatory v4-vs-v5 comparison runs against, and a baseline that moved with the
treatment measures nothing. `base.schema` stays the SAME OBJECT, so a v4 corpus
run keeps offering the model byte-identical tool definitions.

A BARE CITY IS NOT IN `result_pii`, ANYWHERE. «Ижевск» identifies nobody
(152-ФЗ ст. 3 п. 1, and the engine refuses bare cities on purpose — MASSIVE
`place_name` 0.1% is the CORRECT number, `CLAUDE.md` «Eval discipline»).
Declaring `to_location.city` as a PII path would create an IN hop on a value
the engine will never mask, and every form metric sliced by LOC would carry a
permanent, undeserved miss. The city is rendered — it is part of the API's
address notation — and it is not counted.

NOTHING HERE IMPORTS `pseudex`, and the parsers of the twelve new tools are
taken from the documentation of the API each one mirrors: they accept exactly
what it accepts, refuse with the documented rule's name and never repair.
"""
import datetime as dt
import re
from dataclasses import replace

from bench.agentpii4 import tools as v4tools
from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import (CSV_HEADER, REGISTRY as V4_REGISTRY, FieldSpec, Refusal,
                                   ToolSpec, parse_e164, parse_inn, parse_int, parse_iso_date,
                                   parse_name_word, parse_snils)
from bench.agentpii5.contracts import (NEW_TOOL_NAMES, NEW_TOOL_RESULT_TYPES,
                                       NEW_TOOL_RETURN_FORMS, NO_SUITE, RETURN_FORMS, SUITES,
                                       TOOL_SUITE, TOOL_VERTICAL, V4_TOOL_NAMES, VERTICALS,
                                       ReturnForm, ToolSpecV5)

Parsed = dict[str, object]

# The traffic plate of a Russian civil vehicle: the twelve Cyrillic letters that
# have a Latin look-alike in the ГОСТ, three digits, two letters, a 2- or
# 3-digit region. A Latin «X» is refused (`plate_format`) and NOT folded to the
# Cyrillic «Х» — the ГИБДД service takes the Cyrillic form, and repairing the
# argument here would hide the very confusion the PLATE cases are built to
# provoke.
PLATE_RE = re.compile(r"[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}")
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
FILE_EXTENSIONS: tuple[str, ...] = (".txt", ".csv", ".docx")


def field_at(fields: dict[str, object], path: str) -> object:
    """A seed field by its dotted path, arrays by index («rows[1].phone»).

    THE ONE WALKER OF A SEED PATH IN v5. The mock read tags with it while the
    builder let v4's `_seed_field` (dots only, no index, and no way to say «I
    could not») write the item's surface; the two disagreed on every CSV cell
    and the disagreement shipped as the string «None». It raises where v4
    returns None, which is the whole difference.
    """
    value: object = fields
    for step in path.split("."):
        name, indexes = step, []
        while name.endswith("]"):
            head, _, raw = name[:-1].rpartition("[")
            indexes.insert(0, int(raw))
            name = head
        if not isinstance(value, dict) or name not in value:
            raise KeyError(f"seed path {path!r} does not exist: no {name!r} in {value!r}")
        value = value[name]
        for index in indexes:
            if not isinstance(value, list) or index >= len(value):
                raise KeyError(f"seed path {path!r} does not exist: no index {index}")
            value = value[index]
    return value


def csv_row_path(row_key: str, column: str) -> str:
    """Where a CSV cell lives inside its `documents` seed row: `rows.<i>.<col>`.

    IT LIVES BESIDE `CSV_HEADER` BECAUSE IT IS THE SAME KIND OF FACT — the
    layout `file_read` answers a CSV in — and because it is the one string the
    builder (`scenarios5.common.csv_row_typed`), the renderer (`mock`) and the
    item's own `Locus.path` must spell identically; a tag spelled apart is a
    tag nothing matches.

    THE ROWS ARE A MAPPING KEYED BY THE ORDINAL, NOT A LIST, and that is v4's
    constraint rather than a taste: `agentpii4.schema._seed_field` walks «.»
    alone, so a path through a LIST resolved to None while v4's `validate`
    demanded that the item's written surface EQUAL that None. The 310 CSV items
    therefore shipped with the surface «None» — not merely odd-looking, but a
    NEEDLE: the stem «none» entered every document case's own-stem exemption
    and matched the literal word in any reply.
    """
    return f"rows.{row_key}.{column}"
# The id prefix `Backend._store` allocates for each table, so a reader tool
# refuses an id no writer could ever have minted. `clm` is `courier_book`'s.
CLAIM_ID_RE = re.compile(r"clm-\d{1,6}")
DOC_ID_RE = re.compile(r"doc-\d{1,6}")
BANK_CLIENT_ID_RE = re.compile(r"bc-\d{1,6}")
ISSUE_ID_RE = re.compile(r"t-\d{1,6}")
KB_MAX_HITS: int = 10
KB_QUERY_LIMIT: int = 200
FORM_TEXT_LIMIT: int = 4000
EMAIL_BODY_LIMIT: int = 4000
EMAIL_SUBJECT_LIMIT: int = 200


# --- the twelve new tools -----------------------------------------------------
#
# `v4tools._schema`, `_required`, `_obj` and `_first` are used through the
# module rather than re-implemented: two definitions of «what a JSON function
# schema looks like» would be one definition and a drift waiting to happen, and
# the model must see the new tools described exactly like the old ones.

def _kb_search_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "kb_search"
    for key in ("query", "k"):
        if key not in args:
            return Refusal(tool, key, "missing_required", "")
    raw = args["query"]
    if not isinstance(raw, str):
        return Refusal(tool, "query", "not_a_string", str(raw))
    if not raw.strip():
        # NOT `missing_required`: Elasticsearch answers a present-but-blank
        # `query.match` with its own error, and the retry family needs the two
        # failures to be distinguishable in the model's context.
        return Refusal(tool, "query", "empty_query", raw)
    if len(raw) > KB_QUERY_LIMIT:
        return Refusal(tool, "query", "too_long", raw)
    count = parse_int(args["k"], tool, "k", 1, KB_MAX_HITS)
    if isinstance(count, Refusal):
        return count
    return {"query": raw.strip(), "k": count}


KB_SEARCH = ToolSpec(
    name="kb_search",
    source="Elasticsearch 8 POST /_search (query.match + size) / Qdrant points/search (limit); top-k over a knowledge base of customer notes",
    schema=v4tools._schema(
        "kb_search",
        "Найти в базе знаний записи по запросу. Возвращает k наиболее подходящих фрагментов.",
        {"query": {"type": "string", "description": "Строка поиска, до 200 символов"},
         "k": {"type": "integer", "description": "Сколько фрагментов вернуть, 1-10"}},
        ("query", "k")),
    # THE QUERY IS `free`, NOT `identity`: the agent decides what to search for
    # and a search string carrying a name is prose, never compared for equality
    # — but it IS an OUT hop, and the form of the value inside it is scored.
    fields=(FieldSpec("query", "free", required=True),
            FieldSpec("k", "plain", required=True)),
    parse=_kb_search_parse, mutating=False,
    result_pii=("hits[].text", "records[].name", "records[].phone", "records[].address"))


def _doc_retrieve_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "doc_retrieve"
    miss = v4tools._required(args, tool, "", ("doc_id",))
    if miss:
        return miss
    raw = str(args["doc_id"]).strip()
    if not DOC_ID_RE.fullmatch(raw):
        return Refusal(tool, "doc_id", "id_format", raw)
    return {"doc_id": raw}


DOC_RETRIEVE = ToolSpec(
    name="doc_retrieve",
    source="document store GET /documents/{id} (opaque id «doc-N», body as text)",
    schema=v4tools._schema(
        "doc_retrieve",
        "Получить документ из хранилища по идентификатору вида doc-1.",
        {"doc_id": {"type": "string", "description": "Идентификатор документа, например doc-12"}},
        ("doc_id",)),
    fields=(FieldSpec("doc_id", "plain", required=True),),
    parse=_doc_retrieve_parse, mutating=False,
    result_pii=("body",))


def _file_read_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "file_read"
    miss = v4tools._required(args, tool, "", ("path",))
    if miss:
        return miss
    raw = args["path"]
    if not isinstance(raw, str):
        return Refusal(tool, "path", "not_a_string", str(raw))
    path = raw.strip()
    # TRAVERSAL FIRST: «../secrets/passwords.txt» carries a legal extension, and
    # a storage service checks the path before it checks what is at the end of
    # it. Order matters only for a path that breaks both rules, and this is the
    # order the service applies.
    if ".." in path:
        return Refusal(tool, "path", "path_traversal", path)
    if not path.lower().endswith(FILE_EXTENSIONS):
        return Refusal(tool, "path", "path_extension", path)
    return {"path": path}


FILE_READ = ToolSpec(
    name="file_read",
    source="attachment storage GET /files?path= (txt / csv / docx extracted as text); traversal refused before the extension is looked at",
    schema=v4tools._schema(
        "file_read",
        "Прочитать вложение клиента. Допустимы .txt, .csv и .docx.",
        {"path": {"type": "string", "description": "Путь к файлу, например /mnt/in/clients.csv"}},
        ("path",)),
    fields=(FieldSpec("path", "plain", required=True),),
    parse=_file_read_parse, mutating=False,
    result_pii=("text", "rows[].last_name", "rows[].first_name", "rows[].phone",
                "rows[].email", "rows[].birth_date"))


def _form_parse_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "form_parse"
    if "text" not in args:
        return Refusal(tool, "text", "missing_required", "")
    raw = args["text"]
    if not isinstance(raw, str):
        return Refusal(tool, "text", "not_a_string", str(raw))
    if not raw.strip():
        return Refusal(tool, "text", "empty_text", raw)
    if len(raw) > FORM_TEXT_LIMIT:
        return Refusal(tool, "text", "too_long", raw)
    return {"text": raw}


FORM_PARSE = ToolSpec(
    name="form_parse",
    source="анкета-parser POST /forms/parse (free text in, typed fields out; unrecognised text is answered with the offending fragment)",
    schema=v4tools._schema(
        "form_parse",
        "Разобрать текст анкеты на поля: ФИО, дата рождения, паспорт, СНИЛС, адрес.",
        {"text": {"type": "string", "description": "Текст анкеты целиком, до 4000 символов"}},
        ("text",)),
    fields=(FieldSpec("text", "free", required=True),),
    parse=_form_parse_parse, mutating=False,
    result_pii=("fields.person.last_name", "fields.person.first_name", "fields.person.middle_name",
                "fields.birth_date", "fields.passport.series", "fields.passport.number",
                "fields.snils", "fields.address.street", "fields.address.house",
                "fields.address.flat", "error.subject"))


def _bank_client_find_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "bank_client_find"
    present = [key for key in ("inn", "phone") if args.get(key) not in (None, "")]
    if len(present) != 1:
        # THE BANK'S SEARCH IS BY ONE KEY. Two keys in one request would let the
        # service pick, and a service that picks hides which key the agent
        # actually trusted — the whole point of an INN case.
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "inn":
        inn = parse_inn(args["inn"], tool, "inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        return {"inn": inn}
    phone = parse_e164(args["phone"], tool, "phone")
    if isinstance(phone, Refusal):
        return phone
    return {"phone": phone}


BANK_CLIENT_FIND = ToolSpec(
    name="bank_client_find",
    source="банковская CRM GET /clients?inn=|phone= (ИНН физлица 12 / ИП 12 / юрлица 10 знаков with the ФНС checksum, phone E.164)",
    schema=v4tools._schema(
        "bank_client_find",
        "Найти клиента банка по ИНН или по телефону. Ровно один из двух параметров.",
        {"inn": {"type": "string", "description": "ИНН, 10 или 12 цифр"},
         "phone": {"type": "string", "description": "Телефон в формате E.164, например +79161234567"}},
        ()),
    fields=(FieldSpec("inn", "identity", "INN", ""),
            FieldSpec("phone", "identity", "PHONE", "digits")),
    parse=_bank_client_find_parse, mutating=False,
    result_pii=("client.name", "client.inn", "client.card",
                "clients[].name", "clients[].inn", "clients[].card", "error.subject",
                "error.message"))


def _account_statement_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "account_statement"
    miss = v4tools._required(args, tool, "", ("client_id",))
    if miss:
        return miss
    client_id = str(args["client_id"]).strip()
    if not BANK_CLIENT_ID_RE.fullmatch(client_id):
        return Refusal(tool, "client_id", "id_format", client_id)
    out: Parsed = {"client_id": client_id}
    for key in ("from", "to"):
        if args.get(key) in (None, ""):
            continue
        value = parse_iso_date(args[key], tool, key)
        if isinstance(value, Refusal):
            return value
        out[key] = value
    if "from" in out and "to" in out and str(out["from"]) > str(out["to"]):
        return Refusal(tool, "to", "range_order", f"{out['from']}..{out['to']}")
    return out


ACCOUNT_STATEMENT = ToolSpec(
    name="account_statement",
    source="банковская выписка GET /clients/{id}/statement?from=&to= (ISO dates, rows of one account holder)",
    schema=v4tools._schema(
        "account_statement",
        "Выписка по счёту клиента за период. Даты в формате ГГГГ-ММ-ДД.",
        {"client_id": {"type": "string", "description": "Идентификатор клиента банка, например bc-1"},
         "from": {"type": "string", "description": "Начало периода, ГГГГ-ММ-ДД"},
         "to": {"type": "string", "description": "Конец периода, ГГГГ-ММ-ДД"}},
        ("client_id",)),
    fields=(FieldSpec("client_id", "plain", required=True),
            FieldSpec("from", "plain"),
            FieldSpec("to", "plain")),
    parse=_account_statement_parse, mutating=False,
    result_pii=("holder.name", "holder.card", "rows[].holder", "rows[].card"))


def _vehicle_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "vehicle_check"
    miss = v4tools._required(args, tool, "", ("plate",))
    if miss:
        return miss
    raw = str(args["plate"]).strip().upper().replace(" ", "")
    if not PLATE_RE.fullmatch(raw):
        return Refusal(tool, "plate", "plate_format", str(args["plate"]))
    return {"plate": raw}


VEHICLE_CHECK = ToolSpec(
    name="vehicle_check",
    source="ГИБДД-подобная проверка GET /vehicles?plate= (кириллический ГОСТ-номер без пробелов, регион 2-3 цифры)",
    schema=v4tools._schema(
        "vehicle_check",
        "Проверить автомобиль по госномеру. Номер кириллицей, без пробелов, например Х501УН36.",
        {"plate": {"type": "string", "description": "Госномер, например Х501УН36"}},
        ("plate",)),
    fields=(FieldSpec("plate", "identity", "PLATE", "", required=True),),
    parse=_vehicle_check_parse, mutating=False,
    result_pii=("plate", "owner.last_name", "owner.first_name",
                "registrations[].owner.last_name", "registrations[].owner.first_name",
                "error.subject", "error.message"))


def _snils_verify_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "snils_verify"
    miss = v4tools._required(args, tool, "", ("snils",))
    if miss:
        return miss
    digits = parse_snils(args["snils"], tool, "snils")
    if isinstance(digits, Refusal):
        return digits
    return {"snils": digits}


SNILS_VERIFY = ToolSpec(
    name="snils_verify",
    source="ПФР-подобная проверка POST /snils/verify (формат XXX-XXX-XXX YY, контрольная сумма mod-101)",
    schema=v4tools._schema(
        "snils_verify",
        "Проверить СНИЛС и получить данные застрахованного. Формат 112-233-445 95.",
        {"snils": {"type": "string", "description": "СНИЛС в формате XXX-XXX-XXX YY"}},
        ("snils",)),
    fields=(FieldSpec("snils", "identity", "SNILS", "", required=True),),
    parse=_snils_verify_parse, mutating=False,
    result_pii=("snils", "person.last_name", "person.first_name", "person.birth_date",
                "error.subject", "error.message"))


def _calendar_free_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "calendar_free"
    miss = v4tools._required(args, tool, "", ("person", "date"))
    if miss:
        return miss
    raw = args["person"]
    if not isinstance(raw, str):
        return Refusal(tool, "person", "name_format", str(raw))
    words = raw.split()
    if not 1 <= len(words) <= 3:
        return Refusal(tool, "person", "name_format", raw)
    parts: list[str] = []
    for index, word in enumerate(words):
        value = parse_name_word(word, tool, f"person[{index}]")
        if isinstance(value, Refusal):
            return value
        parts.append(str(value))
    date = parse_iso_date(args["date"], tool, "date")
    if isinstance(date, Refusal):
        return date
    return {"person": " ".join(parts), "date": date}


CALENDAR_FREE = ToolSpec(
    name="calendar_free",
    source="календарь GET /calendars/free?person=&date= (свободные окна человека; каждое окно в нотации своего источника)",
    schema=v4tools._schema(
        "calendar_free",
        "Показать свободные окна человека на дату. Имя — от одного до трёх слов.",
        {"person": {"type": "string", "description": "ФИО или имя, например Громова Марина"},
         "date": {"type": "string", "description": "Дата, ГГГГ-ММ-ДД"}},
        ("person", "date")),
    fields=(FieldSpec("person", "identity", "NAME", "", required=True),
            FieldSpec("date", "plain", required=True)),
    parse=_calendar_free_parse, mutating=False,
    result_pii=("person", "birth_date", "error.message"))


def _email_send_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "email_send"
    miss = v4tools._required(args, tool, "", ("to", "subject", "body"))
    if miss:
        return miss
    to = args["to"]
    if not isinstance(to, str) or not EMAIL_RE.fullmatch(to.strip()):
        return Refusal(tool, "to", "email_format", str(to))
    subject = v4tools.parse_text(args["subject"], tool, "subject", EMAIL_SUBJECT_LIMIT)
    body = v4tools.parse_text(args["body"], tool, "body", EMAIL_BODY_LIMIT)
    bad = v4tools._first(subject, body)
    if bad:
        return bad
    return {"to": to.strip(), "subject": subject, "body": body}


EMAIL_SEND = ToolSpec(
    name="email_send",
    source="SMTP submission / Mailgun POST /messages (адрес принимается как есть, хранится в нижнем регистре; тело — свободный текст)",
    schema=v4tools._schema(
        "email_send",
        "Отправить письмо клиенту. Тему и текст напиши своими словами.",
        {"to": {"type": "string", "description": "Адрес получателя, например client@mail.ru"},
         "subject": {"type": "string", "description": "Тема, до 200 символов"},
         "body": {"type": "string", "description": "Текст письма, до 4000 символов"}},
        ("to", "subject", "body")),
    # `subject` AND `body` ARE TEMPLATE HOPS (`contracts.TEMPLATE_FIELDS`): a
    # person reads what the model wrote, so the value inside the sentence is
    # judged for form and for leaks, never compared for equality.
    fields=(FieldSpec("to", "identity", "EMAIL", "", required=True),
            FieldSpec("subject", "free", required=True),
            FieldSpec("body", "free", required=True)),
    parse=_email_send_parse, mutating=True,
    result_pii=("accepted", "error.subject"))


def _ticket_history_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "ticket_history"
    miss = v4tools._required(args, tool, "", ("issue_id",))
    if miss:
        return miss
    raw = str(args["issue_id"]).strip()
    if not ISSUE_ID_RE.fullmatch(raw):
        return Refusal(tool, "issue_id", "id_format", raw)
    return {"issue_id": raw}


TICKET_HISTORY = ToolSpec(
    name="ticket_history",
    source="Okdesk GET /issues/{id}/comments (история обращения сплошным текстом, как её читает оператор)",
    schema=v4tools._schema(
        "ticket_history",
        "Показать историю обращения по идентификатору вида t-1.",
        {"issue_id": {"type": "string", "description": "Идентификатор обращения, например t-12"}},
        ("issue_id",)),
    fields=(FieldSpec("issue_id", "plain", required=True),),
    parse=_ticket_history_parse, mutating=False,
    result_pii=("history",))


def _courier_status_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "courier_status"
    miss = v4tools._required(args, tool, "", ("claim_id",))
    if miss:
        return miss
    raw = str(args["claim_id"]).strip()
    if not CLAIM_ID_RE.fullmatch(raw):
        return Refusal(tool, "claim_id", "id_format", raw)
    return {"claim_id": raw}


COURIER_STATUS = ToolSpec(
    name="courier_status",
    source="CDEK GET /v2/orders/{uuid} / Boxberry ParcelInfo (получатель и адрес в нормализации курьерки: «г. Ижевск, ул. Пушкина, д. 41, кв. 7»)",
    schema=v4tools._schema(
        "courier_status",
        "Узнать статус заявки курьеру по её идентификатору вида clm-1.",
        {"claim_id": {"type": "string", "description": "Идентификатор заявки, например clm-3"}},
        ("claim_id",)),
    fields=(FieldSpec("claim_id", "plain", required=True),),
    parse=_courier_status_parse, mutating=False,
    # `recipient.*` IS declared (ruling R-41, reversing R-27): when the claim
    # was SEEDED the mock renders the stored recipient — a value arriving from
    # the courier's system in its notation, a real IN hop — and when the claim
    # was booked by `courier_book` in the same dialogue no IN hop can be
    # declared on it anyway, because R05 requires a seed locus. The address is
    # re-rendered in the courier's dotted notation («г. Ижевск, ул. Пушкина,
    # д. 41, кв. 7»), and `error.subject` is that same address inside a failure.
    result_pii=("recipient.name", "recipient.phone", "address", "error.subject"))


def _patient_find_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "patient_find"
    present = [key for key in ("phone", "snils") if args.get(key) not in (None, "")]
    if len(present) != 1:
        # ONE KEY, LIKE THE BANK'S SEARCH AND FOR THE SAME REASON: a МИС that
        # took both would decide for itself which one it trusted, and the case
        # measures exactly which identifier the agent carried through.
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "snils":
        digits = parse_snils(args["snils"], tool, "snils")
        if isinstance(digits, Refusal):
            return digits
        return {"snils": digits}
    phone = parse_e164(args["phone"], tool, "phone")
    if isinstance(phone, Refusal):
        return phone
    return {"phone": phone}


PATIENT_FIND = ToolSpec(
    name="patient_find",
    source="МИС (Медеск/Инфоклиника) GET /patients?phone=|snils= (карта пациента: ДР в ISO, СНИЛС в написании ПФР «XXX-XXX-XXX YY», телефон E.164)",
    schema=v4tools._schema(
        "patient_find",
        "Найти карту пациента по телефону или по СНИЛС. Ровно один из двух параметров.",
        {"phone": {"type": "string", "description": "Телефон в формате E.164, например +79161234567"},
         "snils": {"type": "string", "description": "СНИЛС в формате XXX-XXX-XXX YY"}},
        ()),
    fields=(FieldSpec("phone", "identity", "PHONE", "digits"),
            FieldSpec("snils", "identity", "SNILS", "")),
    parse=_patient_find_parse, mutating=False,
    # THE WHOLE CARD, AND NOTHING THAT IS NOT ON IT. The clinic's five other
    # tools all WRITE, so every value in their results is one the dialogue just
    # handed them; here the values come off a stored record, which is what makes
    # them an IN/tool hop at all (R05 asks for a seed locus).
    result_pii=("patient.last_name", "patient.first_name", "patient.birth_date",
                "patient.snils", "patient.phone"))




# --- the office suite: eleven shapes an enterprise assistant actually has ------
#
# WHY THESE ELEVEN AND NOT A PRODUCT'S API. The names are generalised on purpose
# (`mail_send`, not a vendor's endpoint): the corpus outlives any one deal and is
# read again for the next customer, and a registry full of brand names would have
# to be rewritten every time. Each `source` still cites the PUBLIC documentation
# of the real APIs these mirror, because a parser invented rather than read would
# refuse what the market accepts and accept what it refuses.
#
# WHAT THE MEASUREMENT SAID WAS MISSING, before any of this was written:
#   · 708 IN/tool → OUT/tool_arg transitions in the corpus, NOT ONE from a
#     `free_text` result. Prose reaches an argument only out of a DOCUMENT (413
#     hops). «Read the letter → write the card» — the loop where a placeholder
#     gateway scores zero — was not measured at all.
#   · `messaging` had no reading tool and was EXEMPT from K16 for it.
#   · EMAIL crosses as an IN/user hop 14 times in 1 736 cases, against 1 196
#     declared EMAIL items: the type is declared everywhere and travels nowhere.
#   · No argument anywhere takes a LIST of people, no argument takes TWO objects
#     at once, and nothing at all is two-dimensional.
#
# THE LEAVES ARE DECLARED TIGHT. `build.result_pii_residue` refuses a
# `result_pii` leaf no IN/tool hop crosses unless it is named in the frozen
# `UNCROSSED_RESULT_PII`, so every leaf below is one the office families are
# built to cross — a generous declaration here would be a new decorative claim
# of exactly the kind that check exists to catch.

MAIL_ID_RE = re.compile(r"msg-\d{1,6}")
SHEET_ID_RE = re.compile(r"sh-\d{1,6}")
MEMORY_ID_RE = re.compile(r"mem-\d{1,6}")
# Jira's project key: a capital letter, then letters and digits, 2–10 in all
# (Atlassian «What is an issue key»). The ISSUE key it mints — «ABC-123» — is the
# customer's commonest NON-personal identifier and must survive the gateway
# untouched.
#
# WHERE THAT CAN BE SAID, AND WHERE IT CANNOT — measured, not assumed. The
# DECLARATION exists: v4's `schema.PlainValue` is exactly «not personal data,
# must reach the tool byte-identical», it takes a message or a SEED locus, and
# `Case.plain` holds it. What is missing is the SCORER: v4's report printed a
# plain-value line, and no module of v5 reads `case.base.plain` at all — not
# `metrics`, not `observe`, not `harness`, not `report`. So a corpus may declare
# «ABC-123» today and nothing will tell anyone when the gateway substitutes it.
# The `result_plain` column the 23.09 review named is the OTHER half, for a leaf
# that appears only in a RESULT and has no locus to hang a `PlainValue` on.
PROJECT_KEY_RE = re.compile(r"[A-Z][A-Z0-9]{1,9}")
# A1 notation, optionally prefixed by a sheet name: «A1», «A1:C10», «Лист1!A1:C10»
# (Sheets API «A1 notation»). Also a non-personal identifier that has to survive.
SHEET_RANGE_RE = re.compile(r"(?:[^!]{1,40}!)?[A-Z]{1,3}\d{1,7}(?::[A-Z]{1,3}\d{1,7})?")
PRICE_RE = re.compile(r"\d{1,9}(?:[.,]\d{1,2})?")
DEAL_STAGES: tuple[str, ...] = ("new", "in_progress", "won", "lost")
MEMORY_SCOPES: tuple[str, ...] = ("user", "org")
MAIL_QUERY_LIMIT: int = 200
MAIL_MAX_RESULTS: int = 50
MAIL_MAX_RECIPIENTS: int = 20
TRACKER_QUERY_LIMIT: int = 100
TRACKER_MAX_RESULTS: int = 50
TRACKER_DEFAULT_RESULTS: int = 10
ISSUE_SUMMARY_LIMIT: int = 255
ISSUE_TEXT_LIMIT: int = 20000
CALENDAR_MAX_ATTENDEES: int = 25
SHEET_MAX_ROWS: int = 50
DOC_APPEND_LIMIT: int = 20000
MEMORY_SUBJECT_LIMIT: int = 120
MEMORY_FACT_LIMIT: int = 1000
REMINDER_TEXT_LIMIT: int = 1000


def _address_list(raw: object, tool: str, path: str) -> list[str] | Refusal:
    """A recipient LIST, refused the way a submission agent refuses one.

    THE FIRST ARGUMENT IN THE CORPUS THAT HOLDS SEVERAL PEOPLE AT ONCE.
    `email_send.to` takes exactly one address; the only other «many people in one
    argument» anywhere is `crm_segment_report.members[].name`. A list is what
    makes the question «does the gateway keep a DIFFERENT substitute for each
    person inside one array» askable at all.

    NOTHING IS REPAIRED HERE. The address is stripped and handed on in the case
    the agent wrote it; the transfer agent lower-cases what it stored, and that
    lower-casing belongs to the RESULT — it is one of the notations the IN hop
    is there to measure, and doing it in the parser would erase it.
    """
    if not isinstance(raw, list):
        return Refusal(tool, path, "recipient_format", str(raw))
    if not raw:
        return Refusal(tool, path, "no_recipients", str(raw))
    if len(raw) > MAIL_MAX_RECIPIENTS:
        return Refusal(tool, path, "too_many_recipients", str(len(raw)))
    out: list[str] = []
    for index, one in enumerate(raw):
        if not isinstance(one, str) or not EMAIL_RE.fullmatch(one.strip()):
            return Refusal(tool, f"{path}[{index}]", "recipient_format", str(one))
        out.append(one.strip())
    return out


def _mail_read_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "mail_read"
    miss = v4tools._required(args, tool, "", ("message_id",))
    if miss:
        return miss
    raw = str(args["message_id"]).strip()
    if not MAIL_ID_RE.fullmatch(raw):
        return Refusal(tool, "message_id", "id_format", raw)
    return {"message_id": raw}


MAIL_READ = ToolSpec(
    name="mail_read",
    source="Gmail API users.messages.get (format=full — payload.headers From/To/Subject, тело в parts[].body; format=raw — весь RFC 5322 одной строкой) / Microsoft Graph GET /me/messages/{id} (from.emailAddress{name,address}, body.content)",
    schema=v4tools._schema(
        "mail_read",
        "Прочитать письмо по его идентификатору вида msg-1.",
        {"message_id": {"type": "string", "description": "Идентификатор письма, например msg-3"}},
        ("message_id",)),
    fields=(FieldSpec("message_id", "plain", required=True),),
    parse=_mail_read_parse, mutating=False,
    # THE BODY IS THE POINT. `subject` and `body` are free prose written by a
    # HUMAN and carrying their own personal data, which is the source form the
    # corpus had nowhere: 413 of its prose-to-argument hops come out of a
    # document and none out of a letter. `raw` is the same letter as one string,
    # the way `format=raw` answers it, and the headers are its nested half.
    result_pii=("from.name", "from.email", "subject", "body", "raw"))


def _mail_search_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "mail_search"
    miss = v4tools._required(args, tool, "", ("query", "max_results"))
    if miss:
        return miss
    raw = args["query"]
    if not isinstance(raw, str):
        return Refusal(tool, "query", "not_a_string", str(raw))
    query = raw.strip()
    if not query:
        return Refusal(tool, "query", "empty_query", str(raw))
    if len(query) > MAIL_QUERY_LIMIT:
        return Refusal(tool, "query", "too_long", query)
    count = parse_int(args["max_results"], tool, "max_results", 1, MAIL_MAX_RESULTS)
    if isinstance(count, Refusal):
        return count
    return {"query": query, "max_results": count}


MAIL_SEARCH = ToolSpec(
    name="mail_search",
    source="Gmail API users.messages.list?q= (операторы поиска Gmail: from:, to:, subject:) / Microsoft Graph GET /me/messages?$search",
    schema=v4tools._schema(
        "mail_search",
        "Найти письма запросом почтового поиска, например «from:client@mail.ru».",
        {"query": {"type": "string",
                   "description": "Запрос, до 200 символов, например from:grom@mail.ru"},
         "max_results": {"type": "integer", "description": "Сколько писем вернуть, 1–50"}},
        ("query", "max_results")),
    # `query` IS `free`, NOT `identity`, and that is the shape the client asks
    # for: the agent decides what to put in it — an address, a surname, a subject
    # — and the gateway has to decide for itself whether what it sees is personal
    # data. An `identity` leaf would tell it the answer in advance.
    fields=(FieldSpec("query", "free", required=True),
            FieldSpec("max_results", "plain", required=True)),
    parse=_mail_search_parse, mutating=False,
    # `error.subject` IS NOT DECLARED: the body of an unsupported-operator error
    # echoes the QUERY, and a query is the agent's own string — the mock cannot
    # tag a value inside it without searching for it. The form is still declared
    # and still rendered; it simply promises no personal datum.
    result_pii=("messages[].from.name", "messages[].from.email", "messages[].snippet"))


def _mail_send_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "mail_send"
    miss = v4tools._required(args, tool, "", ("to", "subject", "body"))
    if miss:
        return miss
    to = _address_list(args["to"], tool, "to")
    if isinstance(to, Refusal):
        return to
    copies: list[str] = []
    if args.get("cc") not in (None, "", []):
        cc = _address_list(args["cc"], tool, "cc")
        if isinstance(cc, Refusal):
            return cc
        copies = cc
    subject = v4tools.parse_text(args["subject"], tool, "subject", EMAIL_SUBJECT_LIMIT)
    body = v4tools.parse_text(args["body"], tool, "body", EMAIL_BODY_LIMIT)
    bad = v4tools._first(subject, body)
    if bad:
        return bad
    return {"to": to, "cc": copies, "subject": subject, "body": body}


MAIL_SEND = ToolSpec(
    name="mail_send",
    source="Gmail API users.messages.send (RFC 5322: заголовок To: — список адресов через запятую, Cc: — копии) / SMTP submission RFC 6409",
    schema=v4tools._schema(
        "mail_send",
        "Отправить письмо одному или нескольким получателям. Тему и текст напиши своими словами.",
        {"to": {"type": "array", "items": {"type": "string"},
                "description": "Адреса получателей, до 20"},
         "cc": {"type": "array", "items": {"type": "string"}, "description": "Копии"},
         "subject": {"type": "string", "description": "Тема, до 200 символов"},
         "body": {"type": "string", "description": "Текст письма, до 4000 символов"}},
        ("to", "subject", "body")),
    # `subject` and `body` are TEMPLATE hops (`contracts.TEMPLATE_FIELDS`): a
    # person reads them, so they are judged for form and for leaks, never for
    # equality. `to[]` and `cc[]` are identity leaves — one hop per address, so
    # two people in one array are two hops and a gateway that gives them one
    # substitute is visible.
    fields=(FieldSpec("to[]", "identity", "EMAIL", "", required=True),
            FieldSpec("cc[]", "identity", "EMAIL", ""),
            FieldSpec("subject", "free", required=True),
            FieldSpec("body", "free", required=True)),
    parse=_mail_send_parse, mutating=True,
    result_pii=("accepted[]", "error.subject"))


def _calendar_invite_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "calendar_invite"
    miss = v4tools._required(args, tool, "", ("summary", "attendees", "start", "end"))
    if miss:
        return miss
    people = args["attendees"]
    if not isinstance(people, list):
        return Refusal(tool, "attendees", "attendee_format", str(people))
    if not people:
        return Refusal(tool, "attendees", "no_attendees", str(people))
    if len(people) > CALENDAR_MAX_ATTENDEES:
        return Refusal(tool, "attendees", "too_many_attendees", str(len(people)))
    guests: list[dict[str, object]] = []
    for index, one in enumerate(people):
        block = v4tools._obj(one, tool, f"attendees[{index}]")
        if isinstance(block, Refusal):
            return block
        address = block.get("email")
        if not isinstance(address, str) or not EMAIL_RE.fullmatch(address.strip()):
            return Refusal(tool, f"attendees[{index}].email", "attendee_format", str(address))
        guest: dict[str, object] = {"email": address.strip()}
        if block.get("name"):
            shown = v4tools.parse_text(block["name"], tool, f"attendees[{index}].name", 120)
            if isinstance(shown, Refusal):
                return shown
            guest["name"] = shown
        guests.append(guest)
    start = v4tools.parse_iso_datetime(args["start"], tool, "start")
    end = v4tools.parse_iso_datetime(args["end"], tool, "end")
    bad = v4tools._first(start, end)
    if bad:
        return bad
    # COMPARED AS INSTANTS, NOT AS STRINGS. «10:00+03:00» sorts after
    # «09:00+00:00» lexically and is an hour EARLIER; a string comparison would
    # accept a backwards interval whenever the two offsets differ, which is what
    # a calendar in two time zones looks like.
    if dt.datetime.fromisoformat(str(start)) >= dt.datetime.fromisoformat(str(end)):
        return Refusal(tool, "end", "interval_order", f"{start}..{end}")
    summary = v4tools.parse_text(args["summary"], tool, "summary", 255)
    if isinstance(summary, Refusal):
        return summary
    out: Parsed = {"summary": summary, "attendees": guests, "start": start, "end": end}
    if args.get("description"):
        text = v4tools.parse_text(args["description"], tool, "description", 4000)
        if isinstance(text, Refusal):
            return text
        out["description"] = text
    return out


CALENDAR_INVITE = ToolSpec(
    name="calendar_invite",
    source="Google Calendar API events.insert (attendees[]{email,displayName}, start/end как {dateTime: RFC 3339, timeZone: IANA}) / Microsoft Graph POST /me/events",
    schema=v4tools._schema(
        "calendar_invite",
        "Создать встречу и позвать участников. Повестку напиши своими словами.",
        {"summary": {"type": "string", "description": "Название встречи"},
         "attendees": {"type": "array", "description": "Участники, до 25",
                       "items": {"type": "object",
                                 "properties": {"email": {"type": "string"},
                                                "name": {"type": "string"}}}},
         "start": {"type": "string", "description": "Начало, ISO 8601 со смещением"},
         "end": {"type": "string", "description": "Конец, ISO 8601 со смещением"},
         "description": {"type": "string", "description": "Повестка"}},
        ("summary", "attendees", "start", "end")),
    fields=(FieldSpec("attendees[].email", "identity", "EMAIL", "", required=True),
            FieldSpec("attendees[].name", "identity", "NAME", ""),
            FieldSpec("summary", "free", required=True),
            FieldSpec("description", "free")),
    parse=_calendar_invite_parse, mutating=True,
    result_pii=("event.attendees[].email", "event.attendees[].displayName",
                "error.subject"))


def _tracker_find_user_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "tracker_find_user"
    miss = v4tools._required(args, tool, "", ("query",))
    if miss:
        return miss
    raw = args["query"]
    if not isinstance(raw, str):
        return Refusal(tool, "query", "not_a_string", str(raw))
    query = raw.strip()
    if not query:
        return Refusal(tool, "query", "empty_query", str(raw))
    if len(query) > TRACKER_QUERY_LIMIT:
        return Refusal(tool, "query", "too_long", query)
    count = parse_int(args.get("max_results", TRACKER_DEFAULT_RESULTS), tool,
                      "max_results", 1, TRACKER_MAX_RESULTS)
    if isinstance(count, Refusal):
        return count
    return {"query": query, "max_results": count}


TRACKER_FIND_USER = ToolSpec(
    name="tracker_find_user",
    source="Jira Cloud REST v3 GET /rest/api/3/user/search?query= (ОДНО поле, сопоставляется и с displayName, и с emailAddress) / YouTrack GET /api/users?query=",
    schema=v4tools._schema(
        "tracker_find_user",
        "Найти сотрудника в трекере: имя, логин или почта — одним запросом.",
        {"query": {"type": "string",
                   "description": "Имя, логин или почта, до 100 символов"},
         "max_results": {"type": "integer", "description": "Сколько вернуть, 1–50"}},
        ("query",)),
    # THE OPPOSITE OF `crm_find_contact`, WHICH IS WHY IT IS HERE. That tool
    # splits the key into three TYPED fields (`query.phone` / `query.email` /
    # `query.last_name`) and hands the gateway the answer; Jira takes one free
    # field whose value may be a name, may be an e-mail, and may be a LOGIN —
    # which is not personal data and is spelled like a surname. This is the one
    # place in the corpus that tests the leak and the over-masking of one leaf
    # at the same time.
    fields=(FieldSpec("query", "free", required=True),
            FieldSpec("max_results", "plain")),
    parse=_tracker_find_user_parse, mutating=False,
    # `users[].accountId` and `users[].login` are rendered and NOT in `result_pii`:
    # they are not personal data, so V04/V06 would refuse them here. A login can
    # still be DECLARED — `PlainValue` with the seed locus of this row — and it
    # is scored by nothing: no v5 module reads `case.base.plain`. Until one does,
    # a gateway that substitutes a login is invisible to this instrument.
    result_pii=("users[].displayName", "users[].emailAddress"))


def _tracker_issue_create_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "tracker_issue_create"
    miss = v4tools._required(args, tool, "", ("project_key", "summary"))
    if miss:
        return miss
    key = str(args["project_key"]).strip()
    if not PROJECT_KEY_RE.fullmatch(key):
        return Refusal(tool, "project_key", "project_key", key)
    summary = args["summary"]
    if not isinstance(summary, str):
        return Refusal(tool, "summary", "not_a_string", str(summary))
    if len(summary.strip()) > ISSUE_SUMMARY_LIMIT:
        return Refusal(tool, "summary", "summary_too_long", summary)
    out: Parsed = {"project_key": key, "summary": summary.strip()}
    if args.get("description"):
        text = v4tools.parse_text(args["description"], tool, "description", ISSUE_TEXT_LIMIT)
        if isinstance(text, Refusal):
            return text
        out["description"] = text
    if args.get("assignee"):
        who = v4tools.parse_text(args["assignee"], tool, "assignee", 120)
        if isinstance(who, Refusal):
            return who
        out["assignee"] = who
    return out


TRACKER_ISSUE_CREATE = ToolSpec(
    name="tracker_issue_create",
    source="Jira Cloud REST v3 POST /rest/api/3/issue (fields.project.key, fields.summary ≤ 255, fields.description, fields.assignee; ответ — {id, key, self})",
    schema=v4tools._schema(
        "tracker_issue_create",
        "Завести задачу в трекере. Исполнителя укажи по имени, описание напиши своими словами.",
        {"project_key": {"type": "string", "description": "Ключ проекта, например SUP"},
         "summary": {"type": "string", "description": "Заголовок, до 255 символов"},
         "description": {"type": "string", "description": "Описание"},
         "assignee": {"type": "string", "description": "Исполнитель по имени"}},
        ("project_key", "summary")),
    # THE ASSIGNEE IS AN ARGUMENT, and that is the gap: `ticket_create` carries
    # free text but names nobody, and the only assignee anywhere in the corpus
    # arrives in a RESULT (`escalate_to_human.assignee.name`). `summary` and
    # `description` are SUMMARY leaves — the agent retells the dialogue for
    # another worker to read.
    fields=(FieldSpec("assignee", "identity", "NAME", ""),
            FieldSpec("summary", "free", required=True),
            FieldSpec("description", "free"),
            FieldSpec("project_key", "plain", required=True)),
    parse=_tracker_issue_create_parse, mutating=True,
    # `issue.key` («SUP-14») is deliberately absent from `result_pii`: it is the
    # customer's own record key, not personal data, and what it needs is the
    # plain-value scorer v5 does not have (see PROJECT_KEY_RE above).
    result_pii=("issue.fields.assignee.displayName", "error.subject"))


def _crm_upsert_card_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_upsert_card"
    contact_raw, deal_raw = args.get("contact"), args.get("deal")
    if not contact_raw and not deal_raw:
        return Refusal(tool, "", "empty_card", "")
    out: Parsed = {}
    if args.get("id"):
        out["id"] = str(args["id"]).strip()
    if contact_raw:
        contact = v4tools._obj(contact_raw, tool, "contact")
        if isinstance(contact, Refusal):
            return contact
        person: dict[str, object] = {}
        for key in ("last_name", "first_name", "middle_name"):
            if contact.get(key):
                value = parse_name_word(contact[key], tool, f"contact.{key}")
                if isinstance(value, Refusal):
                    return value
                person[key] = value
        if contact.get("phone"):
            phone = parse_e164(contact["phone"], tool, "contact.phone")
            if isinstance(phone, Refusal):
                return phone
            person["phone"] = phone
        if contact.get("email"):
            address = str(contact["email"]).strip().lower()
            if not EMAIL_RE.fullmatch(address):
                return Refusal(tool, "contact.email", "email_format", address)
            person["email"] = address
        if contact.get("address"):
            block = v4tools._obj(contact["address"], tool, "contact.address")
            if isinstance(block, Refusal):
                return block
            miss = v4tools._required(block, tool, "contact.address", ("city", "street", "house"))
            if miss:
                return miss
            house = v4tools.parse_house(block["house"], tool, "contact.address.house")
            if isinstance(house, Refusal):
                return house
            flat: object = ""
            if block.get("flat") not in ("", None):
                flat = parse_int(block["flat"], tool, "contact.address.flat", 1, 2000)
                if isinstance(flat, Refusal):
                    return flat
            person["address"] = {"city": str(block["city"]).strip().lower(),
                                 "street": str(block["street"]).strip().lower(),
                                 "house": house, "flat": str(flat) if flat != "" else ""}
        if not person:
            return Refusal(tool, "contact", "nothing_to_update", "")
        out["contact"] = person
    if deal_raw:
        deal = v4tools._obj(deal_raw, tool, "deal")
        if isinstance(deal, Refusal):
            return deal
        trade: dict[str, object] = {}
        if deal.get("title"):
            title = v4tools.parse_text(deal["title"], tool, "deal.title", 255)
            if isinstance(title, Refusal):
                return title
            trade["title"] = title
        if deal.get("price") not in (None, ""):
            price = str(deal["price"]).strip()
            if not PRICE_RE.fullmatch(price):
                return Refusal(tool, "deal.price", "price_format", price)
            trade["price"] = price
        if deal.get("stage"):
            stage = str(deal["stage"]).strip().lower()
            if stage not in DEAL_STAGES:
                return Refusal(tool, "deal.stage", "stage_unknown", stage)
            trade["stage"] = stage
        if deal.get("contact_name"):
            shown = v4tools.parse_text(deal["contact_name"], tool, "deal.contact_name", 120)
            if isinstance(shown, Refusal):
                return shown
            trade["contact_name"] = shown
        if deal.get("note"):
            note = v4tools.parse_text(deal["note"], tool, "deal.note", 4000)
            if isinstance(note, Refusal):
                return note
            trade["note"] = note
        if not trade:
            return Refusal(tool, "deal", "nothing_to_update", "")
        out["deal"] = trade
    return out


CRM_UPSERT_CARD = ToolSpec(
    name="crm_upsert_card",
    source="amoCRM POST /api/v4/leads/complex (сделка и _embedded.contacts[] ОДНИМ запросом) / Bitrix24 crm.deal.add с вложенным CONTACT",
    schema=v4tools._schema(
        "crm_upsert_card",
        "Завести или обновить карточку: контакт и сделку одним вызовом. Комментарий напиши своими словами.",
        {"id": {"type": "string", "description": "id карточки, если она уже есть"},
         "contact": {"type": "object",
                     "properties": {"last_name": {"type": "string"},
                                    "first_name": {"type": "string"},
                                    "middle_name": {"type": "string"},
                                    "phone": {"type": "string", "description": "E.164"},
                                    "email": {"type": "string"},
                                    "address": {"type": "object",
                                                "properties": {"city": {"type": "string"},
                                                               "street": {"type": "string"},
                                                               "house": {"type": "string"},
                                                               "flat": {"type": "string"}},
                                                "required": ["city", "street", "house"]}}},
         "deal": {"type": "object",
                  "properties": {"title": {"type": "string"},
                                 "price": {"type": "string"},
                                 "stage": {"type": "string",
                                           "enum": ["new", "in_progress", "won", "lost"]},
                                 "contact_name": {"type": "string"},
                                 "note": {"type": "string"}}}},
        ()),
    # TWO OBJECTS IN ONE CALL, which nothing in the corpus had.
    # `crm_upsert_contact` nests one level (`contact.address.*`); here a person
    # and a deal travel together, and the same person is named TWICE — as
    # `contact.last_name`/`first_name` and as `deal.contact_name` — so a gateway
    # that mints two substitutes for one identity inside one argument is
    # visible. It is also the second consumer of the mail loop: what the letter
    # said goes here.
    fields=(FieldSpec("id", "plain"),
            FieldSpec("contact.last_name", "identity", "NAME", "surname"),
            FieldSpec("contact.first_name", "identity", "NAME", "given"),
            FieldSpec("contact.middle_name", "identity", "NAME", "patronymic"),
            FieldSpec("contact.phone", "identity", "PHONE", "digits"),
            FieldSpec("contact.email", "identity", "EMAIL", ""),
            FieldSpec("contact.address.city", "identity", "LOC", "city"),
            FieldSpec("contact.address.street", "identity", "LOC", "street"),
            FieldSpec("contact.address.house", "identity", "LOC", "house"),
            FieldSpec("contact.address.flat", "identity", "LOC", "flat"),
            FieldSpec("deal.title", "free"),
            FieldSpec("deal.price", "plain"),
            FieldSpec("deal.stage", "enum"),
            FieldSpec("deal.contact_name", "identity", "NAME", ""),
            FieldSpec("deal.note", "free")),
    parse=_crm_upsert_card_parse, mutating=True,
    result_pii=("card.contact.last_name", "card.contact.first_name", "card.contact.phone",
                "card.contact.email", "card.contact.address", "card.deal.contact_name",
                "error.subject"))


def _sheet_append_row_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "sheet_append_row"
    miss = v4tools._required(args, tool, "", ("spreadsheet_id", "range", "values"))
    if miss:
        return miss
    sheet = str(args["spreadsheet_id"]).strip()
    if not SHEET_ID_RE.fullmatch(sheet):
        return Refusal(tool, "spreadsheet_id", "id_format", sheet)
    cells = str(args["range"]).strip()
    if not SHEET_RANGE_RE.fullmatch(cells):
        return Refusal(tool, "range", "range_format", cells)
    rows = args["values"]
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        return Refusal(tool, "values", "not_a_matrix", str(rows))
    if not rows:
        return Refusal(tool, "values", "no_rows", str(rows))
    if len(rows) > SHEET_MAX_ROWS:
        return Refusal(tool, "values", "too_many_rows", str(len(rows)))
    table: list[list[str]] = []
    for row_index, row in enumerate(rows):
        line: list[str] = []
        for cell_index, cell in enumerate(row):
            if not isinstance(cell, str):
                return Refusal(tool, f"values[{row_index}][{cell_index}]",
                               "cell_not_a_string", str(cell))
            line.append(cell)
        table.append(line)
    return {"spreadsheet_id": sheet, "range": cells, "values": table}


SHEET_APPEND_ROW = ToolSpec(
    name="sheet_append_row",
    source="Google Sheets API spreadsheets.values.append (range в A1-нотации, valueInputOption=USER_ENTERED, values[][]; ответ — updates{updatedRange, updatedRows})",
    schema=v4tools._schema(
        "sheet_append_row",
        "Дописать строки в таблицу. Одна ячейка — одно целое значение.",
        {"spreadsheet_id": {"type": "string", "description": "Идентификатор таблицы, например sh-1"},
         "range": {"type": "string", "description": "Диапазон в A1-нотации, например Лист1!A1:E1"},
         "values": {"type": "array", "description": "Строки таблицы, до 50",
                    "items": {"type": "array", "items": {"type": "string"}}}},
        ("spreadsheet_id", "range", "values")),
    # THE ONE TWO-DIMENSIONAL ARGUMENT IN THE CORPUS. `crm_import_csv` passes a
    # whole CSV as ONE container string; a path to a CELL exists only on the
    # READING side (`csv_row_path`). Here the argument itself is a matrix.
    #
    # ONE CELL CARRIES A WHOLE VALUE, and the leaf therefore declares NO role:
    # `spec_v5_for` erases every index, so `values[0][2]` and `values[3][0]`
    # resolve to the SAME `FieldSpec`, and a role on it would claim that every
    # cell of every column holds a surname. A spreadsheet row is written whole
    # values anyway — «Громова Марина», «+7 916 402-11-87», «Ижевск, Клубная 85»
    # — which is why the shape costs nothing to state honestly.
    fields=(FieldSpec("spreadsheet_id", "plain", required=True),
            FieldSpec("range", "plain", required=True),
            FieldSpec("values[][]", "identity", "", "", required=True)),
    parse=_sheet_append_row_parse, mutating=True,
    # `updated.updatedRange` («Лист1!A4:E4») is NOT in `result_pii`: a range is
    # not personal data and must survive the gateway untouched — the same class
    # as an issue key, and the same missing scorer.
    result_pii=("updated.values[][]", "error.subject"))


def _doc_append_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "doc_append"
    miss = v4tools._required(args, tool, "", ("document_id", "text"))
    if miss:
        return miss
    document = str(args["document_id"]).strip()
    if not DOC_ID_RE.fullmatch(document):
        return Refusal(tool, "document_id", "id_format", document)
    text = args["text"]
    if not isinstance(text, str):
        return Refusal(tool, "text", "not_a_string", str(text))
    if not text.strip():
        return Refusal(tool, "text", "empty_text", str(text))
    if len(text) > DOC_APPEND_LIMIT:
        return Refusal(tool, "text", "too_long", text)
    return {"document_id": document, "text": text.strip()}


DOC_APPEND = ToolSpec(
    name="doc_append",
    source="Google Docs API documents.batchUpdate с InsertTextRequest{location.index, text} / Confluence PUT /rest/api/content/{id} (тело страницы целиком)",
    schema=v4tools._schema(
        "doc_append",
        "Дописать абзац в документ вида doc-1. Текст напиши своими словами.",
        {"document_id": {"type": "string", "description": "Идентификатор документа, например doc-1"},
         "text": {"type": "string", "description": "Что дописать, до 20000 символов"}},
        ("document_id", "text")),
    # LONG FREE TEXT ON THE WAY IN TO STORAGE. Reading documents is covered
    # densely (524 IN/document hops, the `document` family, `doc_retrieve`);
    # WRITING prose into one was covered by nothing. It writes into the same
    # `documents` store `doc_retrieve` and `file_read` read, so «дописал →
    # перечитал» is a chain the corpus gets for free — and «создание документа»
    # is an append into a seeded empty one, which is why there is no `doc_create`.
    fields=(FieldSpec("document_id", "plain", required=True),
            FieldSpec("text", "free", required=True)),
    parse=_doc_append_parse, mutating=True,
    # THE WHOLE PAGE COMES BACK, which is Confluence's answer to a PUT and the
    # only shape that gives this tool a measurable result: the SEEDED prose in
    # the document is tagged as it is rendered, the agent's appended paragraph is
    # not, and the leaf declares what can actually be observed.
    result_pii=("document.body",))


def _memory_save_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "memory_save"
    miss = v4tools._required(args, tool, "", ("subject", "fact"))
    if miss:
        return miss
    subject = args["subject"]
    if not isinstance(subject, str) or not subject.strip():
        return Refusal(tool, "subject", "empty_subject", str(subject))
    if len(subject.strip()) > MEMORY_SUBJECT_LIMIT:
        return Refusal(tool, "subject", "too_long", subject)
    fact = args["fact"]
    if not isinstance(fact, str) or not fact.strip():
        return Refusal(tool, "fact", "empty_fact", str(fact))
    if len(fact) > MEMORY_FACT_LIMIT:
        return Refusal(tool, "fact", "too_long", fact)
    scope = str(args.get("scope", "user")).strip().lower()
    if scope not in MEMORY_SCOPES:
        return Refusal(tool, "scope", "scope_unknown", scope)
    return {"subject": subject.strip(), "fact": fact.strip(), "scope": scope}


MEMORY_SAVE = ToolSpec(
    name="memory_save",
    source="Letta (MemGPT) POST /v1/agents/{id}/archival-memory {text} / OpenAI Assistants persistent store (факт кладётся строкой и живёт дольше разговора)",
    schema=v4tools._schema(
        "memory_save",
        "Запомнить факт о человеке надолго — он переживёт этот разговор.",
        {"subject": {"type": "string", "description": "О ком факт, например Громова Марина"},
         "fact": {"type": "string", "description": "Сам факт, до 1000 символов"},
         "scope": {"type": "string", "enum": ["user", "org"]}},
        ("subject", "fact")),
    # AGENT MEMORY AS A TOOL, which is a different axis from the `memory`
    # family. That family measures the memory of the CONVERSATION — IN/memory is
    # by definition «a value from the transcript» — and the risk here is the
    # other one: a substitute written into an EXTERNAL store outlives the
    # conversation that could have resolved it. Filed under `crm` because a fact
    # about a person put into a long-lived store is a card by another name; the
    # list of eleven verticals is closed and needs no twelfth for it.
    fields=(FieldSpec("subject", "identity", "NAME", "", required=True),
            FieldSpec("fact", "free", required=True),
            FieldSpec("scope", "enum")),
    parse=_memory_save_parse, mutating=True,
    result_pii=("memory.subject", "error.subject"))


def _reminder_set_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "reminder_set"
    miss = v4tools._required(args, tool, "", ("remind_at", "text", "recipient"))
    if miss:
        return miss
    when = v4tools.parse_iso_datetime(args["remind_at"], tool, "remind_at")
    if isinstance(when, Refusal):
        return when
    text = args["text"]
    if not isinstance(text, str) or not text.strip():
        return Refusal(tool, "text", "empty_text", str(text))
    if len(text) > REMINDER_TEXT_LIMIT:
        return Refusal(tool, "text", "too_long", text)
    who = v4tools._obj(args["recipient"], tool, "recipient")
    if isinstance(who, Refusal):
        return who
    miss = v4tools._required(who, tool, "recipient", ("phone",))
    if miss:
        return miss
    phone = parse_e164(who["phone"], tool, "recipient.phone")
    if isinstance(phone, Refusal):
        return phone
    block: dict[str, object] = {"phone": phone}
    if who.get("name"):
        shown = v4tools.parse_text(who["name"], tool, "recipient.name", 120)
        if isinstance(shown, Refusal):
            return shown
        block["name"] = shown
    return {"remind_at": when, "text": text.strip(), "recipient": block}


REMINDER_SET = ToolSpec(
    name="reminder_set",
    source="Google Tasks API tasks.insert (due в RFC 3339) / Todoist REST v2 POST /tasks с due_datetime — отложенное действие со своим номером",
    schema=v4tools._schema(
        "reminder_set",
        "Поставить напоминание человеку на срок. Текст напиши своими словами — он придёт ему.",
        {"remind_at": {"type": "string", "description": "Когда, ISO 8601 со смещением"},
         "text": {"type": "string", "description": "Текст напоминания, до 1000 символов"},
         "recipient": {"type": "object",
                       "properties": {"name": {"type": "string"},
                                      "phone": {"type": "string", "description": "E.164"}},
                       "required": ["phone"]}},
        ("remind_at", "text", "recipient")),
    # `text` IS A TEMPLATE HOP: a human reads it. `notify_sms` and
    # `send_template` already carry 303 OUT/template hops, but neither is a
    # DEFERRED action with an identifier of its own — `callback_schedule` books a
    # call and carries no text at all. Filed under `calendar` beside it rather
    # than under messaging, which already gains three tools from this suite.
    fields=(FieldSpec("recipient.phone", "identity", "PHONE", "digits", required=True),
            FieldSpec("recipient.name", "identity", "NAME", ""),
            FieldSpec("text", "free", required=True),
            FieldSpec("remind_at", "plain", required=True)),
    parse=_reminder_set_parse, mutating=True,
    result_pii=("reminder.recipient.name", "reminder.recipient.phone", "error.subject"))


# WHY NO FREE-TEXT ECHO IS DECLARED BELOW, and it is the same rule for all six.
# A tool that echoes the PROSE THE AGENT WROTE — an issue description, a card's
# note, an appended paragraph, a remembered fact, a reminder's text, a meeting's
# agenda — returns a string whose personal values the mock cannot TAG: a span is
# laid down as a string is BUILT (`Writer`/`Slot`), and the agent's sentence is
# built by the agent. Finding the value inside it afterwards is the one thing
# this package forbids (`prove_no_search_v5`), and declaring a leaf the mock can
# never tag is exactly the defect R-27/R-41 chased out of `courier_status`: a
# permanent miss charged to the gateway, held up by an assertion no measurement
# could contradict.
#
# THOSE FIELDS ARE STILL MEASURED — on the OUT side, where they belong. Every one
# of them is a `template` or `summary` hop (`contracts.TEMPLATE_FIELDS` /
# `SUMMARY_FIELDS`), judged for form and scanned for leaks as the agent writes
# it. What is not measured is the echo coming back, and that is a limit of the
# instrument, stated here rather than papered over with a declaration.

OFFICE_SPECS: tuple[ToolSpec, ...] = (
    MAIL_READ, MAIL_SEARCH, MAIL_SEND, CALENDAR_INVITE, TRACKER_FIND_USER,
    TRACKER_ISSUE_CREATE, CRM_UPSERT_CARD, SHEET_APPEND_ROW, DOC_APPEND,
    MEMORY_SAVE, REMINDER_SET)


NEW_SPECS: tuple[ToolSpec, ...] = (
    KB_SEARCH, DOC_RETRIEVE, FILE_READ, FORM_PARSE, BANK_CLIENT_FIND, ACCOUNT_STATEMENT,
    VEHICLE_CHECK, SNILS_VERIFY, CALENDAR_FREE, EMAIL_SEND, TICKET_HISTORY, COURIER_STATUS,
    PATIENT_FIND, *OFFICE_SPECS)
NEW_REGISTRY: dict[str, ToolSpec] = {spec.name: spec for spec in NEW_SPECS}


# --- the v4 revision: what each old result carries once the mock fills it ------
#
# Read `BackendV5._enrich` beside this table: every path here is a path that
# backend renders. v4's own non-empty declarations are NOT repeated — the nine
# tools it already described keep exactly what it said, except where v5 adds a
# block (`order_status.to_location.city` stays out for the bare-city rule).

RESULT_PII_V5: dict[str, tuple[str, ...]] = {
    "delivery_create_order": ("recipient.name", "recipient.phone", "to_location.address"),
    "courier_book": ("contact.name", "contact.phone", "address"),
    "payment_create": ("receipt.customer.full_name", "receipt.customer.phone"),
    "passport_verify": ("person.last_name", "person.first_name", "passport.series",
                        "passport.number", "snils"),
    "clinic_book": ("patient.last_name", "patient.first_name", "patient.birth_date", "phone"),
    "notify_sms": ("number",),
    "callback_schedule": ("phone",),
    "crm_import_csv": ("rows[].last_name", "rows[].first_name", "rows[].phone",
                       "rows[].email", "rows[].birth_date"),
    "crm_add_note": ("entity.last_name", "entity.first_name", "entity.phone"),
    "send_template": ("text", "parameters[].text"),
    "crm_segment_report": ("buckets[].sample.last_name", "buckets[].sample.first_name",
                           "buckets[].sample.phone"),
    "order_cancel": ("recipient.name", "recipient.phone"),
    "order_reschedule": ("recipient.name", "recipient.phone", "to_location.address"),
    "delivery_quote": ("pickup_point.address",),
    "normalize_contact": ("name.surname", "name.given", "name.patronymic", "phone.e164",
                          "phone.formatted", "address.street", "address.house", "address.value"),
    "clinic_slots": ("doctor.name",),
    "appointment_cancel": ("patient.last_name", "patient.first_name"),
    "appointment_reschedule": ("patient.last_name", "patient.first_name"),
    "referral_create": ("patient.last_name", "patient.first_name", "patient.birth_date"),
    "payment_refund": ("receipt.customer.full_name", "receipt.customer.phone"),
    "ticket_create": ("requester.name", "requester.phone"),
    "ticket_find": ("issues[].subject", "issues[].requester.name", "issues[].requester.phone"),
    "escalate_to_human": ("assignee.name", "assignee.phone"),
    "crm_merge_contacts": ("contact.last_name", "contact.first_name", "contact.phone"),
    # v4's own declaration, kept (ruling R-41, reversing R-27). amoCRM answers a
    # PATCH with the merged card: on a SEEDED contact the mock renders the
    # STORED card — the CRM's notation coming back, a real IN hop — and on a
    # card the call itself created no IN hop can be declared, because R05
    # requires a seed locus. R-27 assumed «a leaf that can never be tagged»;
    # the mock tags it whenever the row was seeded, so there was no permanent
    # miss to prevent and no reason for an exemption to rule V04.
    "crm_upsert_contact": ("contact.last_name", "contact.first_name", "contact.phone"),
}
# The tools whose result renders a type in a notation no user register writes —
# a canon, an ISO date, «+7 (916) 402-11-87», «XXX-XXX-XXX YY», a card in four
# groups, a plate in upper case. These are the tools whose IN/tool hop actually
# tests adaptation; V03 asks every vertical for at least one.
DIFFERS_FROM_USER_FORM: frozenset[str] = frozenset({
    "address_suggest", "normalize_contact", "courier_book", "courier_status",
    "clinic_book", "referral_create", "passport_verify", "snils_verify", "vehicle_check",
    "patient_find",
    "bank_client_find", "account_statement", "calendar_free", "ticket_history",
    "kb_search", "file_read", "form_parse", "crm_find_contact", "crm_import_csv",
    "email_send",
    # The office suite's four. A mailbox lower-cases the address and writes the
    # date in RFC 2822; Jira answers a Cyrillic query with a Latin `displayName`
    # and a lower-case `emailAddress`; a spreadsheet gives every value back as a
    # bare cell, stripped of the separators and the cases the speech had. None of
    # these is a notation a user register produces, which is what V03 asks for
    # and what makes the IN/tool hop of these four able to FAIL.
    "mail_read", "mail_search", "tracker_find_user", "sheet_append_row"})


def _form(form: str, example: str, paths: tuple[str, ...]) -> ReturnForm:
    if form not in RETURN_FORMS:
        raise ValueError(f"{form!r} is not a return form of contracts.RETURN_FORMS")
    return ReturnForm(form=form, example=example, pii_paths=paths)


_NAME_PII = ("recipient.name", "recipient.phone")
RETURN_FORMS_BY_TOOL: dict[str, tuple[ReturnForm, ...]] = {
    "delivery_create_order": (
        _form("single",
              '{"uuid":"ord-1","status":"ACCEPTED","recipient":{"name":"Громова Марина",'
              '"phone":"+79164021187"},"to_location":{"postal_code":"426034","city":"ижевск",'
              '"address":"ул. Клубная, 85, кв. 12"}}',
              ("recipient.name", "recipient.phone", "to_location.address")),),
    "courier_book": (
        _form("nested",
              '{"claim_id":"clm-1","status":"estimating","contact":{"name":"Громова Марина",'
              '"phone":"+79164021187"},"address":"г. Ижевск, ул. Пушкина, д. 41, кв. 7"}',
              ("contact.name", "contact.phone", "address")),),
    "courier_status": (
        # The recipient block is rendered AND declared (R-41): on a seeded claim
        # it is the stored recipient in the courier's notation.
        #
        # AND THE FORM NOW NAMES IT, which is the whole of the 23.09 repair. The
        # union said `recipient.name`/`recipient.phone` carried personal data and
        # this form said the result carried only the address, so the two leaves
        # were declared where nothing reads a declaration and named where every
        # reader looks — the column «ПД в результате» held by an assertion no
        # measurement could contradict. `single._courier_claim` now SEEDS the
        # claim, which is the only way the mock can tag the block (a claim the
        # dialogue itself booked is not a seed locus, R05), and the corpus
        # crosses both leaves.
        _form("nested",
              '{"claim_id":"clm-1","status":"delivering","recipient":{"name":"Громова Марина",'
              '"phone":"+79164021187"},"address":"г. Ижевск, ул. Пушкина, д. 41, кв. 7"}',
              ("recipient.name", "recipient.phone", "address")),
        _form("error_with_value",
              '{"error":{"code":"CLAIM_ADDRESS_UNKNOWN","subject":"г. Ижевск, ул. Пушкина, д. 41, кв. 7"}}',
              ("error.subject",))),
    "order_status": (
        _form("single",
              '{"uuid":"ord-1","status":"ACCEPTED","date":"2026-09-05","recipient":'
              '{"name":"Громова Марина","phone":"+79164021187"},"to_location":{"city":"ижевск",'
              '"address":"ул. Клубная, 85, кв. 12"}}',
              ("recipient.name", "recipient.phone", "to_location.address")),
        _form("error_with_value", '{"error":{"code":"ORDER_NOT_FOUND","subject":"ord-9"}}', ())),
    "order_cancel": (
        _form("single",
              '{"uuid":"ord-1","status":"CANCELLED","recipient":{"name":"Громова Марина",'
              '"phone":"+79164021187"}}', _NAME_PII),),
    "order_reschedule": (
        _form("single",
              '{"uuid":"ord-1","status":"RESCHEDULED","date":"2026-09-07","recipient":'
              '{"name":"Громова Марина","phone":"+79164021187"},"to_location":'
              '{"address":"ул. Клубная, 85, кв. 12"}}',
              ("recipient.name", "recipient.phone", "to_location.address")),),
    "delivery_quote": (
        _form("single",
              '{"city":"ижевск","weight":"1200","price":"384.00","currency":"RUB","days":"2",'
              '"pickup_point":{"address":"г Ижевск, ул Пушкина, д 41"}}',
              ("pickup_point.address",)),),
    "pickup_points_near": (
        _form("list",
              '{"points":[{"code":"PVZ001","address":"г Ижевск, ул Пушкина, д 41","distance_m":"300"}]}',
              ("points[].address",)),
        _form("empty", '{"points":[]}', ())),
    "address_suggest": (
        _form("canon",
              '{"suggestions":[{"value":"г Ижевск, ул Пушкина, д 41, кв 7","confidence":"1.00",'
              '"data":{"postal_code":"426034","region":"Удмуртская Респ","city":"Ижевск",'
              '"street":"Пушкина","house":"41","flat":"7","fias_id":"a1"}}]}',
              ("suggestions[].value", "suggestions[].data.street", "suggestions[].data.house")),
        # ONE ANSWER IS A NORMALISATION, SEVERAL ARE A CHOICE. DaData returns the
        # same body either way, and the difference the agent has to act on is
        # the COUNT — so the form is decided by it, not by a second endpoint.
        _form("list",
              '{"suggestions":[{"value":"г Ижевск, ул Пушкина, д 41, кв 7","confidence":"1.00",'
              '"data":{"postal_code":"426034","region":"Удмуртская Респ","city":"Ижевск",'
              '"street":"Пушкина","house":"41","flat":"7","fias_id":"a1"}},'
              '{"value":"г Ижевск, ул Пушкина, д 41","confidence":"0.50",'
              '"data":{"postal_code":"426034","region":"Удмуртская Респ","city":"Ижевск",'
              '"street":"Пушкина","house":"41","flat":"","fias_id":"a2"}}]}',
              ("suggestions[].value", "suggestions[].data.street", "suggestions[].data.house")),
        _form("empty", '{"suggestions":[]}', ())),
    "normalize_contact": (
        _form("canon",
              '{"name":{"surname":"Громова","given":"Марина","patronymic":"Борисовна","quality":"0"},'
              '"phone":{"e164":"+79164021187","formatted":"+7 (916) 402-11-87","quality":"0"},'
              '"address":{"street":"пушкина","house":"41","value":"ул Пушкина, д 41","quality":"0"}}',
              ("name.surname", "name.given", "name.patronymic", "phone.e164", "phone.formatted",
               "address.street", "address.house", "address.value")),),
    "clinic_book": (
        _form("single",
              '{"appointment_id":"apt-1","slot":"2026-09-05T09:30:00+04:00","status":"booked",'
              '"patient":{"last_name":"павлова","first_name":"тамара","birth_date":"1987-03-14"},'
              '"phone":"+79164021187"}',
              ("patient.last_name", "patient.first_name", "patient.birth_date", "phone")),),
    "clinic_slots": (
        _form("list",
              '{"speciality":"кардиолог","date":"2026-09-05","doctor":{"name":"Соколов Андрей"},'
              '"slots":[{"id":"slot-1","at":"2026-09-05T09:00:00+04:00"}]}',
              ("doctor.name",)),),
    "appointment_cancel": (
        _form("single",
              '{"appointment_id":"apt-1","status":"CANCELLED","patient":{"last_name":"павлова",'
              '"first_name":"тамара"}}', ("patient.last_name", "patient.first_name")),
        _form("error_with_value",
              '{"error":{"code":"APPOINTMENT_NOT_FOUND","subject":"apt-9"}}', ())),
    "appointment_reschedule": (
        _form("single",
              '{"appointment_id":"apt-1","status":"MOVED","slot":"2026-09-06T11:00:00+04:00",'
              '"patient":{"last_name":"павлова","first_name":"тамара"}}',
              ("patient.last_name", "patient.first_name")),),
    "referral_create": (
        _form("single",
              '{"referral_id":"ref-1","speciality":"невролог","status":"issued",'
              '"patient":{"last_name":"павлова","first_name":"тамара","birth_date":"1987-03-14"}}',
              ("patient.last_name", "patient.first_name", "patient.birth_date")),),
    "payment_create": (
        _form("single",
              '{"id":"pay-1","status":"pending","receipt":{"customer":'
              '{"full_name":"Павлова Тамара","phone":"+79164021187"}}}',
              ("receipt.customer.full_name", "receipt.customer.phone")),),
    "payment_status": (
        _form("single",
              '{"id":"pay-1","status":"pending","amount":{"value":"1500.00","currency":"RUB"},'
              '"receipt":{"customer":{"full_name":"Павлова Тамара","phone":"+79164021187"}}}',
              ("receipt.customer.full_name", "receipt.customer.phone")),
        _form("error_with_value", '{"error":{"code":"PAYMENT_NOT_FOUND","subject":"pay-9"}}', ())),
    "payment_refund": (
        _form("single",
              '{"payment_id":"pay-1","status":"refunded","amount":{"value":"1500.00",'
              '"currency":"RUB"},"receipt":{"customer":{"full_name":"Павлова Тамара",'
              '"phone":"+79164021187"}}}',
              ("receipt.customer.full_name", "receipt.customer.phone")),),
    "receipt_fetch": (
        _form("single",
              '{"payment_id":"pay-1","fiscal_document":"fd-y-1","customer":'
              '{"full_name":"Павлова Тамара","phone":"+79164021187","email":"pavlova@mail.ru"}}',
              ("customer.full_name", "customer.phone", "customer.email")),),
    "bank_client_find": (
        _form("single",
              '{"client":{"id":"bc-1","name":"Громова Марина Борисовна","inn":"165711234576",'
              '"card":"4276 1600 1234 5678","status":"active"}}',
              ("client.name", "client.inn", "client.card")),
        _form("list",
              '{"clients":[{"id":"bc-1","name":"Громова Марина Борисовна","inn":"165711234576",'
              '"card":"4276 1600 1234 5678","status":"active"}]}',
              ("clients[].name", "clients[].inn", "clients[].card")),
        _form("empty", '{"clients":[]}', ()),
        # TWO ERROR BODIES, AND ONLY ONE OF THEM WAS NAMED. `_error` writes the
        # domain refusal («not found», «blocked») with the value under
        # `error.subject`; the SCRIPTED refusal of `retry_same_tool`
        # (`mock._forced_call`) writes it under `error.message`, and 126 hops of
        # the corpus cross that leaf. Naming it here is what lets K17 hold every
        # crossed leaf to a declaration.
        # TWO ERROR BODIES, TWO FORMS, AND ONLY ONE OF THEM WAS DECLARED. `_error`
        # writes the domain refusal («not found», «blocked») with the value under
        # `error.subject`; the SCRIPTED refusal of `retry_same_tool`
        # (`mock._forced_call`, `Refusal.as_error`) writes it under
        # `error.message`, and 126 hops of the corpus cross that leaf. They are
        # separate `ReturnForm`s rather than one with both paths because an
        # example must RESOLVE every path it names, and no single body carries
        # both — one example naming two shapes is a declaration nothing can check.
        _form("error_with_value",
              '{"error":{"code":"CLIENT_BLOCKED","subject":"165711234576"}}', ("error.subject",)),
        _form("error_with_value",
              '{"error":{"code":"invalid_request","message":"invalid_request: параметр inn «165711234576» не прошёл проверку."}}',
              ("error.message",))),
    "account_statement": (
        _form("list",
              '{"client_id":"bc-1","holder":{"name":"Громова Марина Борисовна",'
              '"card":"4276 1600 1234 5678"},"rows":[{"date":"2026-08-03","amount":"1500.00",'
              '"currency":"RUB","card":"4276 1600 1234 5678","holder":"Громова Марина Борисовна",'
              '"description":"Оплата заказа"}]}',
              ("holder.name", "holder.card", "rows[].card", "rows[].holder")),
        _form("empty", '{"client_id":"bc-1","rows":[]}', ())),
    "ticket_create": (
        _form("single",
              '{"ticket_id":"tkt-1","status":"open","requester":{"name":"Громова Марина",'
              '"phone":"+79164021187"}}', ("requester.name", "requester.phone")),),
    "ticket_find": (
        _form("list",
              '{"issues":[{"ticket_id":"tkt-1","subject":"Перенос доставки","status":"open",'
              '"requester":{"name":"Громова Марина","phone":"+79164021187"}}]}',
              ("issues[].subject", "issues[].requester.name", "issues[].requester.phone")),
        _form("empty", '{"issues":[]}', ())),
    "ticket_history": (
        _form("free_text",
              '{"issue_id":"t-1","events":2,"history":"12.09 клиент Громова Марина '
              '(+7 (916) 402-11-87) просила перенести доставку на пятницу."}', ("history",)),
        _form("empty", '{"issue_id":"t-9","found":false}', ())),
    "escalate_to_human": (
        _form("single",
              '{"escalation_id":"esc-1","queue":"general","status":"queued",'
              '"assignee":{"name":"Соколов Андрей","phone":"+79261234567"}}',
              ("assignee.name", "assignee.phone")),),
    "callback_schedule": (
        _form("single",
              '{"id":"cb-1","status":"scheduled","phone":"+79164021187",'
              '"at":"2026-09-03T18:00:00+04:00"}', ("phone",)),),
    "calendar_free": (
        _form("list",
              '{"person":"Громова Марина","birth_date":"1987-03-14","date":"2026-09-10",'
              '"slots":["2026-09-10T09:30:00+03:00","10.09.2026 11:00"]}',
              ("person", "birth_date")),
        _form("empty", '{"person":"Громова Марина","date":"2026-09-10","slots":[]}', ()),
        # THE CALENDAR HAD NO ERROR FORM AND THE CORPUS FORCED ONE ON IT 31
        # TIMES. `retry_same_tool` scripts the refusal, the mock answers it and
        # `_form_of_log` records `error_with_value`; a tool that can be refused
        # and declares no refusal form is a tool whose commonest failure shape is
        # unslicable. Adding a form is allowed (contracts may not be contradicted,
        # only extended — V04's `dropped` check).
        _form("error_with_value",
              '{"error":{"code":"employee_unknown","message":"сотрудник Громова Марина не найден в расписании."}}',
              ("error.message",))),
    "notify_sms": (
        _form("single", '{"id":"sms-1","status":"queued","number":"+79164021187"}', ("number",)),),
    "send_template": (
        _form("list",
              '{"id":"tpl-1","status":"queued","text":"Марина, перезвоним вам на +79164021187 завтра.",'
              '"parameters":[{"key":"name","text":"Марина"},{"key":"phone","text":"+79164021187"},'
              '{"key":"when","text":"завтра"}]}',
              ("text", "parameters[].text")),),
    "email_send": (
        _form("single",
              '{"message_id":"<em-1@mail.example.ru>","accepted":"grom@mail.ru","status":"queued"}',
              ("accepted",)),
        _form("error_with_value",
              '{"error":{"code":"RECIPIENT_REJECTED","subject":"grom@mail.ru"}}',
              ("error.subject",))),
    "passport_verify": (
        _form("single",
              '{"id":"ver-1","valid":true,"checked_at":"2026-09-02","person":{"last_name":"иванов",'
              '"first_name":"пётр"},"passport":{"series":"4509","number":"123456"},'
              '"snils":"112-233-445 95"}',
              ("person.last_name", "person.first_name", "passport.series", "passport.number",
               "snils")),),
    "vehicle_check": (
        _form("single",
              '{"plate":"Х501УН36","owner":{"last_name":"Громова","first_name":"Марина"},'
              '"model":"Lada Vesta","year":"2019"}',
              ("plate", "owner.last_name", "owner.first_name")),
        # THE HISTORY OF REGISTRATIONS IS A LIST OF OWNERS, and it is what the
        # ГИБДД service answers for a car that changed hands — the one place in
        # the government vertical where the agent must MATCH a person in a list.
        _form("list",
              '{"plate":"Х501УН36","registrations":[{"from":"2019-04-01","to":"2023-02-15",'
              '"owner":{"last_name":"Громова","first_name":"Марина"}},'
              '{"from":"2023-02-16","to":"","owner":{"last_name":"Букин","first_name":"Сергей"}}]}',
              ("plate", "registrations[].owner.last_name", "registrations[].owner.first_name")),
        _form("error_with_value",
              '{"error":{"code":"VEHICLE_NOT_FOUND","subject":"Х501УН36"}}', ("error.subject",)),
        _form("error_with_value",
              '{"error":{"code":"plate_format","message":"номер Х501УН36 не найден в формате ГОСТ Р 50577."}}',
              ("error.message",))),
    "snils_verify": (
        _form("single",
              '{"snils":"112-233-445 95","status":"valid","person":{"last_name":"Громова",'
              '"first_name":"Марина","birth_date":"1987-03-14"}}',
              ("snils", "person.last_name", "person.first_name", "person.birth_date")),
        _form("empty", '{"snils":"112-233-445 95","found":false}', ()),
        _form("error_with_value",
              '{"error":{"code":"SNILS_REVOKED","subject":"112-233-445 95"}}', ("error.subject",)),
        _form("error_with_value",
              '{"error":{"code":"snils_checksum","message":"СНИЛС 112-233-445 95 не прошёл проверку контрольной суммы ПФР."}}',
              ("error.message",))),
    "kb_search": (
        _form("chunks",
              '{"query":"Громова Марина","total":2,"hits":[{"id":"kb-1","score":"0.91",'
              '"text":"Клиент Громова Марина, телефон +7 (916) 402-11-87, просила перезвонить."}]}',
              ("hits[].text",)),
        # THE SAME INDEX HOLDS TYPED CARDS, and Elasticsearch returns whatever
        # `_source` it stored: a note as text, a card as fields. The form follows
        # what matched — a fan-out over cards is a list to match a person in,
        # not prose to read.
        _form("list",
              '{"query":"Громова Марина","total":1,"records":[{"id":"kb-2",'
              '"name":"Букин Сергей","phone":"+7 (926) 123-45-67",'
              '"address":"г Самара, ул Луговая, д 10"}]}',
              ("records[].name", "records[].phone", "records[].address")),
        _form("empty", '{"query":"Громова Марина","total":0,"hits":[]}', ())),
    "doc_retrieve": (
        _form("free_text",
              '{"doc_id":"doc-1","title":"Анкета клиента","format":"free_text",'
              '"body":"Заявитель Громова Марина Борисовна, телефон +79164021187."}', ("body",)),
        _form("empty", '{"doc_id":"doc-9","found":false}', ())),
    "file_read": (
        _form("free_text",
              '{"path":"/mnt/in/anketa.txt","format":"txt","text":"Заявитель Громова Марина '
              'Борисовна, телефон +79164021187."}', ("text",)),
        _form("list",
              '{"path":"/mnt/in/clients.csv","format":"csv","header":"' + CSV_HEADER + '",'
              '"rows":[{"last_name":"Громова","first_name":"Марина","phone":"+79164021187",'
              '"email":"grom@mail.ru","birth_date":"1987-03-14"}]}',
              ("rows[].last_name", "rows[].first_name", "rows[].phone", "rows[].email",
               "rows[].birth_date")),
        _form("empty", '{"path":"/mnt/in/clients.csv","found":false}', ())),
    "form_parse": (
        _form("nested",
              '{"format":"form","confidence":"0.87","fields":{"person":{"last_name":"Громова",'
              '"first_name":"Марина","middle_name":"Борисовна"},"birth_date":"1987-03-14",'
              '"passport":{"series":"4509","number":"123456"},"snils":"112-233-445 95",'
              '"address":{"city":"Ижевск","street":"Пушкина","house":"41","flat":"7"}}}',
              ("fields.person.last_name", "fields.person.first_name", "fields.person.middle_name",
               "fields.birth_date", "fields.passport.series", "fields.passport.number",
               "fields.snils", "fields.address.street", "fields.address.house",
               "fields.address.flat")),
        _form("error_with_value",
              '{"error":{"code":"FORM_UNPARSED","subject":"Громова Марина Борисовна"}}',
              ("error.subject",))),
    "crm_find_contact": (
        _form("list",
              '{"contacts":[{"id":"c-77","last_name":"громова","first_name":"марина",'
              '"middle_name":"борисовна","phone":"+79164021187","email":"grom@mail.ru",'
              '"birth_date":"1987-03-14","address":{"city":"ижевск","street":"клубная",'
              '"house":"85","flat":"12"}}]}',
              ("contacts[].last_name", "contacts[].first_name", "contacts[].middle_name",
               "contacts[].phone", "contacts[].email", "contacts[].birth_date",
               "contacts[].address.street", "contacts[].address.house")),
        _form("empty", '{"contacts":[]}', ())),
    "crm_upsert_contact": (
        # The card comes back — that is what amoCRM answers with, and the shape
        # the model reads must be the API's. Its leaves are declared (R-41): on a
        # seeded contact they are the STORED card, the CRM's notation coming back.
        #
        # THE FORM SAID `()` AND `result_pii` SAID THREE LEAVES, and the identical
        # tool one entry below (`crm_merge_contacts`, same block, same renderer)
        # named all three — so this was an omission, not a position. Naming them
        # here is what makes `branching._crm_update` able to declare the IN hops
        # on the stored card it updates; R19 checks a case's form against this
        # table, and a declaration nothing can be checked against is the defect.
        _form("single",
              '{"id":"c-77","updated_fields":["address"],"contact":{"last_name":"громова",'
              '"first_name":"марина","phone":"+79164021187"}}',
              ("contact.last_name", "contact.first_name", "contact.phone")),),
    "crm_add_note": (
        _form("single",
              '{"id":"note-1","entity_id":"c-77","length":64,"entity":{"last_name":"громова",'
              '"first_name":"марина","phone":"+79164021187"}}',
              ("entity.last_name", "entity.first_name", "entity.phone")),),
    "crm_segment_report": (
        _form("list",
              '{"group_by":"city","buckets":[{"bucket":"Ижевск","count":1,"sample":'
              '{"last_name":"громова","first_name":"марина","phone":"+79164021187"}}]}',
              ("buckets[].sample.last_name", "buckets[].sample.first_name",
               "buckets[].sample.phone")),),
    "crm_merge_contacts": (
        _form("single",
              '{"primary_id":"c-77","merged":"c-78","contact":{"last_name":"громова",'
              '"first_name":"марина","phone":"+79164021187"}}',
              ("contact.last_name", "contact.first_name", "contact.phone")),
        _form("error_with_value",
              '{"error":{"code":"CONTACT_NOT_FOUND","subject":"c-77/c-99"}}', ())),
    "patient_find": (
        _form("single",
              '{"found":true,"patient":{"last_name":"Громова","first_name":"Марина",'
              '"birth_date":"1987-03-14","snils":"112-233-445 95","phone":"+79164021187"}}',
              ("patient.last_name", "patient.first_name", "patient.birth_date",
               "patient.snils", "patient.phone")),
        _form("empty", '{"found":false}', ())),
    "crm_import_csv": (
        _form("list",
              '{"imported":2,"rejected":[],"rows":[{"id":"c-1","last_name":"Громова",'
              '"first_name":"Марина","phone":"+79164021187","email":"grom@mail.ru",'
              '"birth_date":"1987-03-14"}]}',
              ("rows[].last_name", "rows[].first_name", "rows[].phone", "rows[].email",
               "rows[].birth_date")),),
    # --- the office suite ----------------------------------------------------
    # EVERY `error_with_value` BELOW ECHOES PERSONAL DATA, not an identifier.
    # An error body whose subject is a document id or a cell range would leave
    # `error.subject` declared in `result_pii` and crossed by nothing — the
    # decorative declaration `build.result_pii_residue` exists to refuse. Where
    # the real service names only the id, the mock names what it could not file
    # instead, the way `form_parse` already names the fragment it could not read.
    "mail_read": (
        _form("nested",
              '{"id":"msg-1","threadId":"thr-1","date":"Fri, 12 Sep 2026 10:14:02 +0300",'
              '"from":{"name":"Громова Марина","email":"grom@mail.ru"},'
              '"to":["office@example.ru"],"subject":"Доставка на Клубную",'
              '"body":"Здравствуйте! Прошу перенести доставку на пятницу.",'
              '"attachments":[{"name":"anketa.txt","path":"/mnt/in/anketa.txt"}]}',
              ("from.name", "from.email", "subject", "body")),
        # `format=raw` HANDS BACK THE WHOLE LETTER AS ONE STRING, headers and
        # all — the shape the corpus had nowhere: prose carrying a person's own
        # words, from a source that is not a document.
        _form("free_text",
              '{"id":"msg-2","format":"raw","raw":"From: Громова Марина <grom@mail.ru> '
              'Subject: Доставка на Клубную Здравствуйте! Прошу перенести доставку."}',
              ("raw",)),
        _form("empty", '{"message_id":"msg-9","found":false}', ())),
    "mail_search": (
        _form("list",
              '{"query":"from:grom@mail.ru","total":1,"messages":[{"id":"msg-1",'
              '"threadId":"thr-1","date":"Fri, 12 Sep 2026 10:14:02 +0300",'
              '"from":{"name":"Громова Марина","email":"grom@mail.ru"},'
              '"snippet":"Здравствуйте! Прошу перенести доставку"}]}',
              ("messages[].from.name", "messages[].from.email", "messages[].snippet")),
        _form("empty", '{"query":"from:nobody@mail.ru","total":0,"messages":[]}', ()),
        _form("error_with_value",
              '{"error":{"code":"INVALID_QUERY","subject":"from:grom@mail.ru"}}', ())),
    "mail_send": (
        _form("single",
              '{"message_id":"<em-1@mail.example.ru>","thread_id":"thr-1","status":"queued",'
              '"accepted":["grom@mail.ru","bukin@mail.ru"]}',
              ("accepted[]",)),
        _form("error_with_value",
              '{"error":{"code":"RECIPIENT_REJECTED","subject":"blocked@mail.ru"}}',
              ("error.subject",))),
    "calendar_invite": (
        _form("single",
              '{"event":{"id":"evt-1","iCalUID":"evt-1@example.ru",'
              '"start":{"dateTime":"2026-09-05T09:30:00+04:00","timeZone":"Europe/Moscow"},'
              '"end":{"dateTime":"2026-09-05T10:00:00+04:00","timeZone":"Europe/Moscow"},'
              '"organizer":{"email":"office@example.ru"},"summary":"Встреча по заказу",'
              '"attendees":[{"email":"grom@mail.ru","displayName":"Громова Марина",'
              '"responseStatus":"needsAction"}],"description":"Обсудить перенос доставки"}}',
              ("event.attendees[].email", "event.attendees[].displayName")),
        _form("error_with_value",
              '{"error":{"code":"ATTENDEE_UNKNOWN","subject":"grom@mail.ru"}}',
              ("error.subject",))),
    "tracker_find_user": (
        # `login` AND `accountId` ARE RENDERED AND OUTSIDE `result_pii`: neither
        # is personal data, and both must reach the next call untouched. They can
        # be declared as `PlainValue` off this seed row; no v5 metric reads that
        # field, so `test_tools` pins only that they are PRESENT in the result.
        _form("list",
              '{"query":"Громова","total":1,"users":[{"accountId":"5b10a2","login":"m.gromova",'
              '"displayName":"Gromova Marina","emailAddress":"grom@mail.ru","active":"true"}]}',
              ("users[].displayName", "users[].emailAddress")),
        _form("empty", '{"query":"никто","total":0,"users":[]}', ())),
    "tracker_issue_create": (
        _form("single",
              '{"issue":{"id":"10001","key":"SUP-14","fields":{"project":{"key":"SUP"},'
              '"summary":"Перенести доставку Громовой Марине","description":"Клиент просит '
              'пятницу.","assignee":{"displayName":"Sokolov Andrey"}}}}',
              ("issue.fields.assignee.displayName",)),
        _form("error_with_value",
              '{"error":{"code":"ASSIGNEE_UNKNOWN","subject":"Соколов Андрей"}}',
              ("error.subject",))),
    "crm_upsert_card": (
        _form("nested",
              '{"card":{"contact":{"id":"c-77","last_name":"громова","first_name":"марина",'
              '"middle_name":"борисовна","phone":"+79164021187","email":"grom@mail.ru",'
              '"address":"г Ижевск, ул Клубная, д 85, кв 12"},"deal":{"id":"d-1",'
              '"title":"Доставка","price":"1500.00","stage":"new",'
              '"contact_name":"Громова Марина","note":"Просила перенести на пятницу"}}}',
              ("card.contact.last_name", "card.contact.first_name", "card.contact.phone",
               "card.contact.email", "card.contact.address", "card.deal.contact_name")),
        _form("error_with_value",
              '{"error":{"code":"DUPLICATE_CARD","subject":"+79164021187"}}',
              ("error.subject",))),
    "sheet_append_row": (
        _form("list",
              '{"spreadsheet_id":"sh-1","updated":{"updatedRange":"Лист1!A4:E4",'
              '"updatedRows":"1","values":[["Громова Марина","+7 916 402-11-87",'
              '"grom@mail.ru","г Ижевск, ул Клубная, д 85","1987-03-14"]]}}',
              ("updated.values[][]",)),
        _form("error_with_value",
              '{"error":{"code":"DUPLICATE_ROW","subject":"Громова Марина"}}',
              ("error.subject",))),
    "doc_append": (
        _form("single",
              '{"document_id":"doc-1","revision_id":"rev-2","document":'
              '{"title":"Анкета клиента","body":"Заявитель Громова Марина, телефон '
              '+7 (916) 402-11-87. 12.09 просила перенести доставку на пятницу.",'
              '"length":"420"}}',
              ("document.body",)),
        _form("error_with_value",
              '{"error":{"code":"DOCUMENT_NOT_FOUND","subject":"doc-9"}}', ())),
    "memory_save": (
        _form("single",
              '{"memory":{"id":"mem-1","scope":"user","subject":"Громова Марина",'
              '"fact":"Просила звонить после 18:00 на +7 916 402-11-87"}}',
              ("memory.subject",)),
        _form("error_with_value",
              '{"error":{"code":"MEMORY_CONFLICT","subject":"Громова Марина"}}',
              ("error.subject",))),
    "reminder_set": (
        _form("single",
              '{"reminder":{"id":"rem-1","remind_at":"2026-09-05T09:00:00+03:00",'
              '"status":"scheduled","text":"Позвонить Громовой Марине про пятницу",'
              '"recipient":{"name":"Громова Марина","phone":"+79164021187"}}}',
              ("reminder.recipient.name", "reminder.recipient.phone")),
        _form("error_with_value",
              '{"error":{"code":"RECIPIENT_UNKNOWN","subject":"+79164021187"}}',
              ("error.subject",))),
}


def _spec_v5(name: str) -> ToolSpecV5:
    """One registry entry: the v4 spec (its `result_pii` filled where v4 left it
    empty) or the new spec, plus the vertical and the declared forms.

    THE TEST IS «is it one of the twelve», not «is it in v4's registry»: the
    widening below puts the twelve INTO v4's registry, and a membership test on
    the other side of it would read the wrong base once it had run."""
    if name not in NEW_REGISTRY:
        base = V4_REGISTRY[name]
        if name in RESULT_PII_V5:
            # A COPY, NEVER AN EDIT. `replace` keeps `schema`, `fields` and
            # `parse` as the SAME objects, so a v4 run offers the model exactly
            # the tool definition it always offered.
            base = replace(base, result_pii=RESULT_PII_V5[name])
    else:
        base = NEW_REGISTRY[name]
    return ToolSpecV5(base=base, vertical=TOOL_VERTICAL[name],
                      return_forms=RETURN_FORMS_BY_TOOL[name],
                      differs_from_user_form=name in DIFFERS_FROM_USER_FORM,
                      # READ FROM `contracts`, NEVER RESTATED HERE. `--slice
                      # suite=office` and this registry must name the same set,
                      # and a second table would be one drift away from a slice
                      # that measures a tool the registry files elsewhere.
                      suite=TOOL_SUITE.get(name, NO_SUITE))


REGISTRY_V5: dict[str, ToolSpecV5] = {
    name: _spec_v5(name) for name in (*V4_TOOL_NAMES, *NEW_TOOL_NAMES)}

# --- ONE DOCUMENTED SIDE EFFECT ON v4's MODULE OBJECT (ruling R-24) -----------
#
# THE GAP IT CLOSES. Rule R02 runs v4's own `validate` on `CaseV5.base`, and
# that validator refuses any `case.tools` name outside v4's 31-tool `REGISTRY`.
# The twelve new tools live here, so without this line no v5 case could offer
# `bank_client_find`, `kb_search` or `file_read` at all — while K07 requires
# every tool of `REGISTRY_V5` to be reachable in at least MIN_TYPE_DENOMINATOR
# cases. The two rules cannot both hold, and the corpus cannot be built.
#
# WHY A RUNTIME WIDENING AND NOT AN EDIT OF `bench/agentpii4/tools.py`. That
# package is the baseline the mandatory v4-vs-v5 comparison runs against, and a
# baseline that moved with the treatment measures nothing. This ADDS names v4
# never had and replaces none of the 31; the v4 corpus names none of the twelve,
# so a v4 run offers the model exactly the tools it always did. The alternative
# — filtering the tool check out of R02 in `schema.py` — was rejected: it would
# also stop catching a genuinely mistyped tool name.
#
# THE COLLISION IS REFUSED, NOT ASSERTED. A new tool sharing a v4 name would
# REPLACE the baseline's spec, and every v4 case calling it would be scored
# against a different API than it was written for. `assert` is stripped under
# `-O`, and this is a fact the import must not be allowed to proceed without.
# The rule is a function so a test can be shown it failing: once the widening
# has run, every new name IS in v4's registry, and the import-time answer
# survives only in `_COLLIDING_TOOL_NAMES`.


def colliding_tool_names(new: dict[str, ToolSpec], existing: dict[str, ToolSpec]) -> tuple[str, ...]:
    """The names `new` would overwrite in `existing` — sorted, all of them."""
    return tuple(sorted(set(new) & set(existing)))


_COLLIDING_TOOL_NAMES: tuple[str, ...] = colliding_tool_names(NEW_REGISTRY, V4_REGISTRY)
if _COLLIDING_TOOL_NAMES:
    raise RuntimeError(
        f"the v5 tools {list(_COLLIDING_TOOL_NAMES)} already exist in v4's registry; widening it "
        f"would replace the baseline's spec for them. Rename the v5 tool or drop it.")
V4_REGISTRY.update(NEW_REGISTRY)


# --- paths, rules, lookups ----------------------------------------------------

def generic_paths(value: object) -> frozenset[str]:
    """Every dotted leaf of a result, array indexes erased («rows[].phone»).

    NOT v4's `flatten`: it drops an empty container, and an `empty` return form
    IS an empty container — «{"contacts": []}» would flatten to nothing and a
    shape check between two different empty results would pass on air. Here an
    empty list is the path «contacts[]» and an empty object is its own path."""
    out: set[str] = set()
    _walk(value, "", out)
    return frozenset(out)


def _walk(value: object, prefix: str, out: set[str]) -> None:
    if isinstance(value, dict):
        if not value:
            out.add(prefix)
            return
        for key, inner in value.items():
            _walk(inner, f"{prefix}.{key}" if prefix else str(key), out)
        return
    if isinstance(value, list):
        if not value:
            out.add(f"{prefix}[]")
            return
        for inner in value:
            _walk(inner, f"{prefix}[]", out)
        return
    out.add(prefix)


def registry_problems(registry: dict[str, ToolSpecV5]) -> list[str]:
    """Every violation of V01–V07 (`contracts.VERTICAL_RULES`), never the first
    one only — a reviewer needs the whole list to decide, and a checker that
    stops at the first problem makes a second one invisible until the first is
    fixed.

    THE REGISTRY IS A PARAMETER, and that is a deviation from the brief's
    `registry_problems()`. A rule that cannot be shown to fail is not a rule:
    `test_tools.test_vertical_rules` breaks a COPY of the registry and demands
    a red, which a function reading the module global could only be given by
    monkey-patching it."""
    problems: list[str] = []
    by_vertical: dict[str, list[ToolSpecV5]] = {vertical: [] for vertical in VERTICALS}
    for name, spec in sorted(registry.items()):
        if spec.vertical not in by_vertical:
            problems.append(f"V04 {name}: vertical {spec.vertical!r} is not in contracts.VERTICALS")
            continue
        by_vertical[spec.vertical].append(spec)
    for vertical, specs in by_vertical.items():
        forms = {form.form for spec in specs for form in spec.return_forms}
        if "list" not in forms:
            problems.append(f"V01 vertical {vertical!r} declares no tool with return form 'list'")
        if not forms & {"error_with_value", "empty"}:
            problems.append(f"V02 vertical {vertical!r} declares no tool with "
                            f"'error_with_value' or 'empty'")
        if not any(spec.differs_from_user_form for spec in specs):
            problems.append(f"V03 vertical {vertical!r} has no tool whose result form differs "
                            f"from the user's")
    for name, spec in sorted(registry.items()):
        if not spec.return_forms:
            problems.append(f"V04 {name}: no return form declared")
        if not spec.base.result_pii:
            problems.append(f"V04 {name}: result_pii is empty — no IN/tool hop to measure")
        declared = set(spec.base.result_pii)
        for form in spec.return_forms:
            if form.form not in RETURN_FORMS:
                problems.append(f"V04 {name}: {form.form!r} is not a contracts return form")
            unknown = sorted(set(form.pii_paths) - declared)
            if unknown:
                problems.append(f"V04 {name}/{form.form}: pii_paths {unknown} are not in "
                                f"result_pii")
        # V06 IS V04's CONTAINMENT READ BACKWARDS, and it had to be written
        # separately because the one-way check let a declaration live where
        # nothing could reach it: `result_pii` is the union a hop's `path` is
        # read against, `ReturnForm.pii_paths` is what a case's declared form
        # promises, and a leaf in the union and in no form is promised by no
        # form a case can declare. Five of the 142 were exactly that, and
        # deleting them reddened nothing — which is how they lived.
        in_forms = {path for form in spec.return_forms for path in form.pii_paths}
        unpromised = sorted(declared - in_forms)
        if unpromised:
            problems.append(f"V06 {name}: result_pii {unpromised} named by no return form — "
                            f"declared where nothing measures it")
        promised = set(NEW_TOOL_RETURN_FORMS.get(name, ()))
        # The tools component MAY add a form, never remove one contracts named.
        dropped = sorted(promised - {form.form for form in spec.return_forms})
        if dropped:
            problems.append(f"V04 {name}: contracts declares {dropped}, which this registry "
                            f"does not")
        if spec.suite != NO_SUITE and spec.suite not in SUITES:
            problems.append(f"V07 {name}: suite {spec.suite!r} is not in contracts.SUITES")
        if spec.suite != TOOL_SUITE.get(name, NO_SUITE):
            problems.append(f"V07 {name}: filed under suite {spec.suite!r}, contracts says "
                            f"{TOOL_SUITE.get(name, NO_SUITE)!r}")
        if not spec.base.source:
            problems.append(f"V05 {name}: no source API cited")
        # THE PARSER IS EXERCISED, NOT INSPECTED. Every tool has at least one
        # required argument, so an empty call must come back as a Refusal with
        # a documented rule name; a rule that only читает the registry could
        # not tell a strict parser from a `lambda args: args`.
        refused = spec.base.parse({})
        if not isinstance(refused, Refusal) or not refused.rule:
            problems.append(f"V05 {name}: parse({{}}) did not refuse with a documented rule "
                            f"(got {refused!r})")
    return problems


def spec_v5_for(tool: str, path: str) -> FieldSpec | None:
    """The `FieldSpec` a dotted argument path falls under, for any of the 43.

    The twelve are matched FIRST: since the widening above they are also in
    v4's registry, and v4's `spec_for` would answer for them out of a dict this
    module filled — one lookup routed through two owners."""
    if tool not in NEW_REGISTRY:
        return v4tools.spec_for(tool, path)
    generic = re.sub(r"\[\d+\]", "[]", path)
    for spec in NEW_REGISTRY[tool].fields:
        if spec.path == generic:
            return spec
    return None


def expected_leaf_value(item: PiiItem, spec: FieldSpec) -> str:
    """The value a tool argument leaf CARRIES of this datum: the item's part for
    the leaf's role, or the whole canonical for a leaf that names no role.
    "" when the item has no such part, and then the leaf cannot carry it at all.

    THE LEAF IS NOT THE DATUM. `contact.last_name` takes a surname and
    `contact.address.city` takes a city; a v4 `PiiItem` is one part of a name
    («букин», parts {surname}) or a whole address (parts {city, street, house,
    flat}). Matching by PII TYPE alone put the surname item on `first_name`,
    `middle_name` and `last_name` alike and the street item on `.city`, `.house`
    and `.flat` — 1 627 of 8 399 OUT hops whose declared item can never be the
    value of the declared leaf, and 1 012 of them inside `chain_value`'s
    denominator, where they read as a hand-over the gateway broke.

    THE VOCABULARY IS ALREADY SHARED: `FieldSpec.role` and `PiiItem.parts` use
    the same words — surname / given / patronymic / city / street / house /
    flat / iso / digits — so nothing is invented here, only read.
    """
    if not spec.role:
        return item.canonical or item.value
    return item.parts.get(spec.role, "")


def result_types(tool: str) -> tuple[str, ...]:
    """The PII types a tool's result can carry. Declared by contracts for the
    twelve new tools; derived from the v4 `FieldSpec`s for the rest, because a
    v4 result carries back what its arguments and its seed put there."""
    if tool in NEW_TOOL_RESULT_TYPES:
        return NEW_TOOL_RESULT_TYPES[tool]
    types: list[str] = []
    for field in REGISTRY_V5[tool].base.fields:
        if field.pii_type and field.pii_type not in types:
            types.append(field.pii_type)
    return tuple(types)
