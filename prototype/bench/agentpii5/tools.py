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
import re
from dataclasses import replace

from bench.agentpii4 import tools as v4tools
from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import (CSV_HEADER, REGISTRY as V4_REGISTRY, FieldSpec, Refusal,
                                   ToolSpec, parse_e164, parse_inn, parse_int, parse_iso_date,
                                   parse_name_word, parse_snils)
from bench.agentpii5.contracts import (NEW_TOOL_NAMES, NEW_TOOL_RESULT_TYPES,
                                       NEW_TOOL_RETURN_FORMS, RETURN_FORMS, TOOL_VERTICAL,
                                       V4_TOOL_NAMES, VERTICALS, ReturnForm, ToolSpecV5)

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
                "clients[].name", "clients[].inn", "clients[].card", "error.subject"))


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
                "error.subject"))


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
                "error.subject"))


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
    result_pii=("person", "birth_date"))


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


NEW_SPECS: tuple[ToolSpec, ...] = (
    KB_SEARCH, DOC_RETRIEVE, FILE_READ, FORM_PARSE, BANK_CLIENT_FIND, ACCOUNT_STATEMENT,
    VEHICLE_CHECK, SNILS_VERIFY, CALENDAR_FREE, EMAIL_SEND, TICKET_HISTORY, COURIER_STATUS)
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
    "bank_client_find", "account_statement", "calendar_free", "ticket_history",
    "kb_search", "file_read", "form_parse", "crm_find_contact", "crm_import_csv",
    "email_send"})


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
        _form("nested",
              '{"claim_id":"clm-1","status":"delivering","recipient":{"name":"Громова Марина",'
              '"phone":"+79164021187"},"address":"г. Ижевск, ул. Пушкина, д. 41, кв. 7"}',
              ("address",)),
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
        _form("error_with_value",
              '{"error":{"code":"CLIENT_BLOCKED","subject":"165711234576"}}', ("error.subject",))),
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
        _form("empty", '{"person":"Громова Марина","date":"2026-09-10","slots":[]}', ())),
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
              '{"error":{"code":"VEHICLE_NOT_FOUND","subject":"Х501УН36"}}', ("error.subject",))),
    "snils_verify": (
        _form("single",
              '{"snils":"112-233-445 95","status":"valid","person":{"last_name":"Громова",'
              '"first_name":"Марина","birth_date":"1987-03-14"}}',
              ("snils", "person.last_name", "person.first_name", "person.birth_date")),
        _form("empty", '{"snils":"112-233-445 95","found":false}', ()),
        _form("error_with_value",
              '{"error":{"code":"SNILS_REVOKED","subject":"112-233-445 95"}}', ("error.subject",))),
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
        _form("single",
              '{"id":"c-77","updated_fields":["address"],"contact":{"last_name":"громова",'
              '"first_name":"марина","phone":"+79164021187"}}',
              ()),),
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
    "crm_import_csv": (
        _form("list",
              '{"imported":2,"rejected":[],"rows":[{"id":"c-1","last_name":"Громова",'
              '"first_name":"Марина","phone":"+79164021187","email":"grom@mail.ru",'
              '"birth_date":"1987-03-14"}]}',
              ("rows[].last_name", "rows[].first_name", "rows[].phone", "rows[].email",
               "rows[].birth_date")),),
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
                      differs_from_user_form=name in DIFFERS_FROM_USER_FORM)


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
    """Every violation of V01–V05 (`contracts.VERTICAL_RULES`), never the first
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
        promised = set(NEW_TOOL_RETURN_FORMS.get(name, ()))
        # The tools component MAY add a form, never remove one contracts named.
        dropped = sorted(promised - {form.form for form in spec.return_forms})
        if dropped:
            problems.append(f"V04 {name}: contracts declares {dropped}, which this registry "
                            f"does not")
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
