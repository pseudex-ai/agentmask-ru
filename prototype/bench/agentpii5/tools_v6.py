"""The v6 tool registry: every grounded §2.3 tool + the unschemed names.

THE CORRECTION. The first author marked 44 §2.3 tools unschemed because their
exact field PATHS are only «summary» evidence. That is too conservative.
`docs/tz-agentpii6-registry.md` §2.4 point 6 explicitly allows the tool author
to «оставить evidence=summary, и тогда отчёт печатает срез provenance»: a §2.3
`doc-proc` tool is a REAL documented procedure with named registry TYPES, not a
synthetic API, so it MUST be implemented with `evidence="summary"` where the
exact path is unverified. D-069 forbids only a FABRICATED schema whose type card
has no procedure behind it. Every field path below is therefore derived from
the type card's `field_keys` / «Поверхности» (e.g. `bank_accounts_list` →
result leaf `items[].account` from A-07 `account`/`account_number`/`RQ_ACC_NUM`;
`oms_policy_find` → arg leaf `enp` from A-13 field_keys), and every pii_type is
a registry id.

THE RESULT OF A WRITE ECHOES THE STORED RECORD, exactly as v5's office suite
does (R-41): a write whose result carried nothing would be a pure-OUT tool
(V04/OD-46), and the v5 convention is the grounded way to give it a result —
not a fabrication, the same pattern `crm_import_csv` / `notify_sms` /
`crm_upsert_card` already wear. That is how `fiscal_receipt_create` (АТОЛ,
whose response carries no PII, §2.4 point 4) and `audience_segment_upload`
still declare a result.

`result_set` (V6T-07) is replaced by `list` until OD-45 decides the
column-path observer, and `free_text` where a BI export is one document.

NOTHING HERE IMPORTS `pseudex`. `checksum_v6` is the pure arithmetic home the
L2 rule pins (component 1), and every checksum-gated parser below reads it
rather than writing a second copy of one algorithm.
"""
import re
from dataclasses import dataclass

from bench.agentpii4.tools import (FieldSpec, Refusal, ToolSpec, _first, _obj,
                                   _required, _schema, parse_digits, parse_e164,
                                   parse_inn, parse_int, parse_iso_date,
                                   parse_name_word, parse_snils, parse_text)
from bench.agentpii5 import checksum_v6
from bench.agentpii5.contracts import (NEW_TOOL_NAMES, NO_SUITE, RETURN_FORMS,
                                       V4_TOOL_NAMES, VERTICALS, ReturnForm,
                                       ToolSpecV5)

Parsed = dict[str, object]

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
# ЮKassa's customer phone is NUMERIC — «79000000000», no «+» — which is the
# notation the IN/tool hop of `receipt_create` exists to test (the user register
# writes «+7 916 …», the fiscal API reads eleven bare digits).
NUMERIC_PHONE_RE = re.compile(r"7\d{10}")
# The batch import and the Exolve SMS share the same cap shape as the sources
# cite (≤500 contacts, ≤1000 chars of message body).
IMPORT_MAX_CONTACTS: int = 500
SMS_TEXT_LIMIT: int = 1000


@dataclass(frozen=True)
class V6ToolMeta:
    """The v6 provenance a `ToolSpecV5` has no field for (V6T-01). `ToolSpecV5`
    carries `source` (the URL), `vertical` and `suite`; the evidence class, the
    API status and the industry live here, one row per tool, so the report can
    print them and the test can assert every pii_type resolves against them.
    `api_status` is `official` (public, documented, live) | `closed` (documented
    but the endpoint is gone, OD-47) | `synthetic` (invented — never in
    `TOOLS_V6`)."""

    evidence: str          # primary | secondary | summary
    api_status: str        # official | closed | synthetic
    industry: str          # contracts_v6.INDUSTRIES


def _form(form: str, example: str, paths: tuple[str, ...]) -> ReturnForm:
    if form not in RETURN_FORMS:
        raise ValueError(f"{form!r} is not a return form of contracts.RETURN_FORMS")
    return ReturnForm(form=form, example=example, pii_paths=paths)


def _parse_ogrnip(raw: object, tool: str, path: str) -> str | Refusal:
    """OGRNIP: 15 digits, mod-13 check (Минфин 165н п. 7). The arithmetic is
    `checksum_v6.validate_ogrnip` — one algorithm, one home — and the format is
    the grammar the registry card owns."""
    if not isinstance(raw, str) or not raw.strip().isdigit() or len(raw.strip()) != 15:
        return Refusal(tool, path, "ogrnip_format", str(raw))
    if not checksum_v6.validate_ogrnip(raw.strip()):
        return Refusal(tool, path, "ogrnip_checksum", str(raw))
    return raw.strip()


def _parse_numeric_phone(raw: object, tool: str, path: str) -> str | Refusal:
    """ЮKassa `customer.phone`: eleven bare digits beginning with 7. A «+7…»
    form is refused — the fiscal API takes the numeric form, and repairing the
    argument here would hide the notation the IN/tool hop exists to measure."""
    if not isinstance(raw, str) or not NUMERIC_PHONE_RE.fullmatch(raw.strip()):
        return Refusal(tool, path, "phone_numeric_format", str(raw))
    return raw.strip()


# --- the §2.3 checksum-gated parsers (one algorithm home: checksum_v6) ----------
# Each §2.3 tool that carries a checksum-typed identifier refuses a bad value
# with the type's OWN rule name and reads the arithmetic from `checksum_v6`
# rather than re-typing it. The format rule is the card's grammar; the checksum
# rule is the published algorithm. A free-form type has no shape rule beyond
# non-empty and a length cap — that IS its documented grammar.

def _checksummed(raw: object, tool: str, path: str, type_id: str,
                 width: int, fmt_rule: str, ck_rule: str) -> str | Refusal:
    """Fixed-width digit string, checksum-gated by `checksum_v6.validate`."""
    digits = parse_digits(raw, tool, path, width, fmt_rule)
    if isinstance(digits, Refusal):
        return digits
    if not checksum_v6.validate(type_id, digits):
        return Refusal(tool, path, ck_rule, str(raw))
    return digits


def _parse_oms_enp(raw: object, tool: str, path: str) -> str | Refusal:
    return _checksummed(raw, tool, path, "OMS_ENP", 16, "enp_format", "enp_checksum")


def _parse_iccid(raw: object, tool: str, path: str) -> str | Refusal:
    return _checksummed(raw, tool, path, "ICCID", 19, "iccid_format", "iccid_checksum")


def _parse_imei(raw: object, tool: str, path: str) -> str | Refusal:
    return _checksummed(raw, tool, path, "IMEI", 15, "imei_format", "imei_checksum")


def _parse_vin(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9A-HJ-NPR-Z]{17}",
                                                    raw.strip().upper()):
        return Refusal(tool, path, "vin_format", str(raw))
    up = raw.strip().upper()
    if not checksum_v6.validate_vin(up):
        return Refusal(tool, path, "vin_checksum", str(raw))
    return up


def _parse_epts(raw: object, tool: str, path: str) -> str | Refusal:
    digits = parse_digits(raw, tool, path, 15, "epts_format")
    if isinstance(digits, Refusal):
        return digits
    if not checksum_v6.validate_epts_number(digits):
        return Refusal(tool, path, "epts_checksum", str(raw))
    return digits


def _parse_uin(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{20}|\d{25}", raw.strip()):
        return Refusal(tool, path, "uin_format", str(raw))
    if not checksum_v6.validate_uin(raw.strip()):
        return Refusal(tool, path, "uin_checksum", str(raw))
    return raw.strip()


def _parse_loan_uid(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9a-fA-F\-]{33,}", raw.strip()):
        return Refusal(tool, path, "loan_uid_format", str(raw))
    if not checksum_v6.validate_loan_uid(raw.strip()):
        return Refusal(tool, path, "loan_uid_checksum", str(raw))
    return raw.strip()


def _parse_loyalty(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{13,18}", raw.strip()):
        return Refusal(tool, path, "loyalty_card_format", str(raw))
    if not checksum_v6.validate_loyalty_card_number(raw.strip()):
        return Refusal(tool, path, "loyalty_card_checksum", str(raw))
    return raw.strip()


def _digits_spaceless(raw: object, tool: str, path: str, width: int,
                      rule: str) -> str | Refusal:
    """A fixed-width identifier whose printed form may group digits with spaces
    («77 12 345678», «75 1234567», «107724 0001234») — the spaces are notation,
    not grammar, and the parser folds them rather than refusing the customer's
    own spelling."""
    if not isinstance(raw, str):
        return Refusal(tool, path, rule, str(raw))
    value = re.sub(r"\s", "", raw)
    if not re.fullmatch(rf"\d{{{width}}}", value):
        return Refusal(tool, path, rule, str(raw))
    return value


def _shaped(raw: object, tool: str, path: str, pattern: str,
            rule: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(pattern, raw.strip()):
        return Refusal(tool, path, rule, str(raw))
    return raw.strip()


def _free_id(raw: object, tool: str, path: str, limit: int,
             rule: str) -> str | Refusal:
    """A free-form identifier (no national grammar — the card says so): the only
    documented rule is non-empty and within the field's length."""
    if not isinstance(raw, str) or not raw.strip():
        return Refusal(tool, path, rule, str(raw))
    if len(raw.strip()) > limit:
        return Refusal(tool, path, rule, str(raw))
    return raw.strip()


def _parse_osago(raw: object, tool: str, path: str) -> str | Refusal:
    # «ХХХ 0123456789» / «XXX 0123456789»: 3 letters + 10 digits, spaces and «№»
    # are notation. The card's alphabet is «12 "номерных" letters» but the
    # checked shape is 3 letters + 10 digits (A-15 grammar is secondary).
    if not isinstance(raw, str):
        return Refusal(tool, path, "osago_format", str(raw))
    value = re.sub(r"[№\s]", "", raw.strip().upper())
    if not re.fullmatch(r"[А-ЯЁA-Z]{3}\d{10}", value):
        return Refusal(tool, path, "osago_format", str(raw))
    return value


def _parse_cadastral(raw: object, tool: str, path: str) -> str | Refusal:
    return _shaped(raw, tool, path, r"\d{2}:\d{2}:\d{6,7}:\d+", "cadastral_format")


def _parse_els(raw: object, tool: str, path: str) -> str | Refusal:
    # ЕЛС «60АА000593», ИЖКУ «60АА000593-01», ИПД «60АА000593-01-7111» (B-15).
    return _shaped(raw, tool, path, r"\d{2}[А-ЯЁ]{2}\d{6}(?:-\d{2})?(?:-\d{4})?",
                   "els_format")


def _parse_arbitrazh(raw: object, tool: str, path: str) -> str | Refusal:
    # «А31-2840/2013» — Cyrillic «А» (B-05); a Latin «A» is accepted (printed
    # traffic, «не мерено»), folded to upper.
    if not isinstance(raw, str):
        return Refusal(tool, path, "case_format", str(raw))
    value = raw.strip().upper()
    if not re.fullmatch(r"[АA]\d{2}-\d{1,7}/\d{4}", value):
        return Refusal(tool, path, "case_format", str(raw))
    return value


# --- 1. Bitrix24 crm.requisite: the seller-requisites family (OGRNIP) ------------
#
# The §2.4 gap «реквизиты продавца маркетплейса с ОГРНИП» is closed by Bitrix24
# `crm.requisite` — the single richest native PII surface in either CRM's docs
# (research 2026-09-05 §A, grade A field list): `RQ_OGRNIP`, `RQ_INN`,
# `RQ_IDENT_DOC_SER`/`RQ_IDENT_DOC_NUM`/`RQ_IDENT_DOC_DATE`/`RQ_IDENT_DOC_ISSUED_BY`.

def _crm_requisite_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_requisite_get"
    present = [key for key in ("inn", "ogrnip") if args.get(key) not in (None, "")]
    if len(present) != 1:
        # THE SEARCH IS BY ONE KEY, like the bank's and the clinic's: a service
        # that took both would decide for itself which one the agent trusted.
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "inn":
        inn = parse_inn(args["inn"], tool, "inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        return {"inn": inn}
    ogrnip = _parse_ogrnip(args["ogrnip"], tool, "ogrnip")
    if isinstance(ogrnip, Refusal):
        return ogrnip
    return {"ogrnip": ogrnip}


CRM_REQUISITE_GET = ToolSpec(
    name="crm_requisite_get",
    source="Bitrix24 REST crm.requisite.get/list — RQ_OGRNIP, RQ_INN, "
           "RQ_IDENT_DOC_SER/RQ_IDENT_DOC_NUM/RQ_IDENT_DOC_DATE/RQ_IDENT_DOC_ISSUED_BY "
           "(https://apidocs.bitrix24.ru/api-reference/crm/requisites/universal/crm-requisite-fields.html)",
    schema=_schema(
        "crm_requisite_get",
        "Получить реквизиты продавца или физлица по ИНН или ОГРНИП. Возвращает ИНН, "
        "ОГРНИП и паспорт по серии и номеру.",
        {"inn": {"type": "string", "description": "ИНН, 10 или 12 цифр"},
         "ogrnip": {"type": "string", "description": "ОГРНИП, 15 цифр"}},
        ()),
    fields=(FieldSpec("inn", "identity", "INN", "digits"),
            FieldSpec("ogrnip", "identity", "OGRNIP", "digits")),
    parse=_crm_requisite_get_parse, mutating=False,
    result_pii=("requisite.rq_inn", "requisite.rq_ogrnip",
                "requisite.rq_ident_doc_ser", "requisite.rq_ident_doc_num"))


def _crm_requisite_set_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_requisite_set"
    miss = _required(args, tool, "", ("inn",))
    if miss:
        return miss
    inn = parse_inn(args["inn"], tool, "inn", (10, 12))
    if isinstance(inn, Refusal):
        return inn
    out: Parsed = {"inn": inn}
    if args.get("ogrnip") not in (None, ""):
        ogrnip = _parse_ogrnip(args["ogrnip"], tool, "ogrnip")
        if isinstance(ogrnip, Refusal):
            return ogrnip
        out["ogrnip"] = ogrnip
    if args.get("ident_doc"):
        doc = _obj(args["ident_doc"], tool, "ident_doc")
        if isinstance(doc, Refusal):
            return doc
        miss = _required(doc, tool, "ident_doc", ("ser", "num"))
        if miss:
            return miss
        # THE PASSPORT BY FIELDS: series and number are SEPARATE fields, which
        # is the notation the v5 registry has no single-string form for.
        ser = parse_digits(doc["ser"], tool, "ident_doc.ser", 4, "passport_series_format")
        num = parse_digits(doc["num"], tool, "ident_doc.num", 6, "passport_number_format")
        bad = _first(ser, num)
        if bad:
            return bad
        block: Parsed = {"ser": ser, "num": num}
        if doc.get("date") not in (None, ""):
            date = parse_iso_date(doc["date"], tool, "ident_doc.date")
            if isinstance(date, Refusal):
                return date
            block["date"] = date
        if doc.get("issued_by") not in (None, ""):
            issuer = parse_text(doc["issued_by"], tool, "ident_doc.issued_by", 200)
            if isinstance(issuer, Refusal):
                return issuer
            block["issued_by"] = issuer
        out["ident_doc"] = block
    return out


CRM_REQUISITE_SET = ToolSpec(
    name="crm_requisite_set",
    source="Bitrix24 REST crm.requisite.add/update — RQ_INN, RQ_OGRNIP, "
           "RQ_IDENT_DOC_SER/RQ_IDENT_DOC_NUM/RQ_IDENT_DOC_DATE/RQ_IDENT_DOC_ISSUED_BY; "
           "the saved requisite is echoed back (v5 R-41 write-echo) "
           "(https://apidocs.bitrix24.ru/api-reference/crm/requisites/universal/crm-requisite-fields.html)",
    schema=_schema(
        "crm_requisite_set",
        "Завести или обновить реквизиты продавца. Паспорт передаётся по серии и номеру.",
        {"inn": {"type": "string", "description": "ИНН, 10 или 12 цифр"},
         "ogrnip": {"type": "string", "description": "ОГРНИП, 15 цифр"},
         "ident_doc": {"type": "object",
                       "properties": {"ser": {"type": "string", "description": "Серия паспорта, 4 цифры"},
                                      "num": {"type": "string", "description": "Номер паспорта, 6 цифр"},
                                      "date": {"type": "string", "description": "Дата выдачи, ГГГГ-ММ-ДД"},
                                      "issued_by": {"type": "string", "description": "Кем выдан"}},
                       "required": ["ser", "num"]}},
        ("inn",)),
    fields=(FieldSpec("inn", "identity", "INN", "digits", required=True),
            FieldSpec("ogrnip", "identity", "OGRNIP", "digits"),
            FieldSpec("ident_doc.ser", "identity", "PASSPORT", "series"),
            FieldSpec("ident_doc.num", "identity", "PASSPORT", "number"),
            FieldSpec("ident_doc.date", "plain"),
            FieldSpec("ident_doc.issued_by", "plain")),
    parse=_crm_requisite_set_parse, mutating=True,
    result_pii=("requisite.rq_inn", "requisite.rq_ogrnip",
                "requisite.rq_ident_doc_ser", "requisite.rq_ident_doc_num",
                "error.subject"))


# --- 2. amoCRM /api/v4/contacts: the value under a nameless key -------------------
#
# `custom_fields_values[{field_id, values[{value, enum_code}]}]` is the D5/D6
# shape the OSS audit flagged: the phone and e-mail live under a bare `value`
# key whose TYPE is carried by the numeric `field_id`, not by the key. The
# `value` leaf therefore declares NO pii_type — claiming PHONE would lie half
# the time — and is a `free` leaf the gateway must type from the sibling field.

def _crm_contact_upsert_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_contact_upsert"
    miss = _required(args, tool, "", ("first_name", "last_name"))
    if miss:
        return miss
    first = parse_name_word(args["first_name"], tool, "first_name")
    last = parse_name_word(args["last_name"], tool, "last_name")
    bad = _first(first, last)
    if bad:
        return bad
    out: Parsed = {"first_name": first, "last_name": last}
    if args.get("custom_fields_values"):
        fields_raw = args["custom_fields_values"]
        if not isinstance(fields_raw, list) or not fields_raw:
            return Refusal(tool, "custom_fields_values", "array_required", str(fields_raw))
        parsed_fields: list[dict[str, object]] = []
        for index, entry in enumerate(fields_raw):
            block = _obj(entry, tool, f"custom_fields_values[{index}]")
            if isinstance(block, Refusal):
                return block
            field_id = parse_int(block.get("field_id"), tool,
                                 f"custom_fields_values[{index}].field_id", 1, 10**9)
            if isinstance(field_id, Refusal):
                return field_id
            values_raw = block.get("values")
            if not isinstance(values_raw, list) or not values_raw:
                return Refusal(tool, f"custom_fields_values[{index}].values",
                               "array_required", str(values_raw))
            parsed_values: list[dict[str, object]] = []
            for vindex, one in enumerate(values_raw):
                value_block = _obj(one, tool, f"custom_fields_values[{index}].values[{vindex}]")
                if isinstance(value_block, Refusal):
                    return value_block
                miss = _required(value_block, tool,
                                 f"custom_fields_values[{index}].values[{vindex}]", ("value",))
                if miss:
                    return miss
                value = parse_text(value_block["value"], tool,
                                   f"custom_fields_values[{index}].values[{vindex}].value", 120)
                if isinstance(value, Refusal):
                    return value
                parsed_values.append({"value": value,
                                      "enum_code": str(value_block.get("enum_code", "")).strip()})
            parsed_fields.append({"field_id": field_id, "values": parsed_values})
        out["custom_fields_values"] = parsed_fields
    return out


CRM_CONTACT_UPSERT = ToolSpec(
    name="crm_contact_upsert",
    source="amoCRM POST/PATCH /api/v4/contacts — first_name, last_name, "
           "custom_fields_values[{field_id, values[{value, enum_code}]}] "
           "(https://www.amocrm.ru/developers/content/crm_platform/contacts-api)",
    schema=_schema(
        "crm_contact_upsert",
        "Завести или обновить контакт в CRM. Телефон и почта передаются внутри "
        "custom_fields_values: числовой field_id и значение под ключом value.",
        {"first_name": {"type": "string", "description": "Имя"},
         "last_name": {"type": "string", "description": "Фамилия"},
         "custom_fields_values": {"type": "array", "description": "Дополнительные поля",
                                  "items": {"type": "object",
                                            "properties": {"field_id": {"type": "integer"},
                                                           "values": {"type": "array",
                                                                      "items": {"type": "object",
                                                                                "properties": {
                                                                                    "value": {"type": "string"},
                                                                                    "enum_code": {"type": "string"}},
                                                                                "required": ["value"]}}},
                                            "required": ["field_id", "values"]}}},
        ("first_name", "last_name")),
    fields=(FieldSpec("first_name", "identity", "NAME", "given", required=True),
            FieldSpec("last_name", "identity", "NAME", "surname", required=True),
            FieldSpec("custom_fields_values[].field_id", "plain"),
            # THE VALUE UNDER A NAMELESS KEY. No pii_type: the type is the numeric
            # field_id's, and the gateway must read it off the sibling key.
            FieldSpec("custom_fields_values[].values[].value", "free"),
            FieldSpec("custom_fields_values[].values[].enum_code", "plain")),
    parse=_crm_contact_upsert_parse, mutating=True,
    result_pii=("contact.first_name", "contact.last_name",
                "contact.custom_fields_values[].values[].value", "error.subject"))


# --- 3. Unisender importContacts: the batch import (mass OUT) ----------------------

def _email_contacts_import_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "email_contacts_import"
    miss = _required(args, tool, "", ("data",))
    if miss:
        return miss
    data_raw = args["data"]
    if not isinstance(data_raw, list) or not data_raw:
        return Refusal(tool, "data", "no_contacts", str(data_raw))
    if len(data_raw) > IMPORT_MAX_CONTACTS:
        return Refusal(tool, "data", "too_many_contacts", str(len(data_raw)))
    rows: list[dict[str, object]] = []
    for index, entry in enumerate(data_raw):
        block = _obj(entry, tool, f"data[{index}]")
        if isinstance(block, Refusal):
            return block
        miss = _required(block, tool, f"data[{index}]", ("email", "phone", "name"))
        if miss:
            return miss
        email = str(block["email"]).strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return Refusal(tool, f"data[{index}].email", "email_format", str(block["email"]))
        phone = parse_e164(block["phone"], tool, f"data[{index}].phone")
        if isinstance(phone, Refusal):
            return phone
        name = parse_text(block["name"], tool, f"data[{index}].name", 120)
        if isinstance(name, Refusal):
            return name
        rows.append({"email": email, "phone": phone, "name": name.strip()})
    return {"data": rows}


EMAIL_CONTACTS_IMPORT = ToolSpec(
    name="email_contacts_import",
    source="Unisender importContacts — fields/data map name/phone/email into "
           "Unisender fields, ≤500 contacts/call; the imported rows are echoed back "
           "(v5 crm_import_csv write-echo) "
           "(https://www.unisender.com/ru/support/api/contacts/createlist/)",
    schema=_schema(
        "email_contacts_import",
        "Импортировать список контактов. Один вызов несёт до 500 человек.",
        {"data": {"type": "array", "description": "Контакты, до 500",
                  "items": {"type": "object",
                            "properties": {"email": {"type": "string"},
                                           "phone": {"type": "string", "description": "E.164"},
                                           "name": {"type": "string"}},
                            "required": ["email", "phone", "name"]}}},
        ("data",)),
    fields=(FieldSpec("data[].email", "identity", "EMAIL", "", required=True),
            FieldSpec("data[].phone", "identity", "PHONE", "digits", required=True),
            FieldSpec("data[].name", "identity", "NAME", "", required=True)),
    parse=_email_contacts_import_parse, mutating=True,
    result_pii=("rows[].email", "rows[].phone", "rows[].name", "error.subject"))


# --- 4. DaData clean/phone: the normalisation preprocessor -------------------------

def _phone_clean_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "phone_clean"
    miss = _required(args, tool, "", ("source",))
    if miss:
        return miss
    source = args["source"]
    if not isinstance(source, str) or not source.strip():
        return Refusal(tool, "source", "empty_source", str(source))
    if len(source) > 60:
        return Refusal(tool, "source", "too_long", source)
    return {"source": source.strip()}


PHONE_CLEAN = ToolSpec(
    name="phone_clean",
    source="DaData POST /api/v1/clean/phone — source (raw phone) in, phone/number/"
           "provider/qc out (https://dadata.ru/api/clean/phone/)",
    schema=_schema(
        "phone_clean",
        "Нормализовать телефон: вернуть каноническую форму, провайдера и признак качества.",
        {"source": {"type": "string", "description": "Телефон в произвольной записи, до 60 символов"}},
        ("source",)),
    fields=(FieldSpec("source", "identity", "PHONE", "", required=True),),
    parse=_phone_clean_parse, mutating=False,
    result_pii=("items[].phone",))


# --- 5. ЮKassa / T-Bank receipts: the 54-ФЗ customer block -------------------------

def _receipt_create_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "receipt_create"
    miss = _required(args, tool, "", ("customer",))
    if miss:
        return miss
    customer = _obj(args["customer"], tool, "customer")
    if isinstance(customer, Refusal):
        return customer
    miss = _required(customer, tool, "customer", ("full_name",))
    if miss:
        return miss
    full_name = parse_text(customer["full_name"], tool, "customer.full_name", 200)
    if isinstance(full_name, Refusal):
        return full_name
    has_email = customer.get("email") not in (None, "")
    has_phone = customer.get("phone") not in (None, "")
    if not has_email and not has_phone:
        # 54-ФЗ: the fiscal receipt carries exactly one contact channel (ЮKassa)
        # or one of Email/Phone (T-Bank) — a customer block with neither is refused.
        return Refusal(tool, "customer", "contact_required", "")
    out_customer: Parsed = {"full_name": full_name.strip()}
    if has_email:
        email = str(customer["email"]).strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return Refusal(tool, "customer.email", "email_format", str(customer["email"]))
        out_customer["email"] = email
    if has_phone:
        phone = _parse_numeric_phone(customer["phone"], tool, "customer.phone")
        if isinstance(phone, Refusal):
            return phone
        out_customer["phone"] = phone
    if customer.get("inn") not in (None, ""):
        inn = parse_inn(customer["inn"], tool, "customer.inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        out_customer["inn"] = inn
    return {"customer": out_customer}


RECEIPT_CREATE = ToolSpec(
    name="receipt_create",
    source="ЮKassa POST /api.yookassa.ru/v3/receipts — customer.{full_name, email, "
           "phone, inn} (phone numeric «79000000000»); T-Bank eACQ Receipt.{Email, Phone} "
           "(https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/payments)",
    schema=_schema(
        "receipt_create",
        "Создать фискальный чек 54-ФЗ. Укажите покупателя: ФИО и ровно один канал — "
        "почту или телефон.",
        {"customer": {"type": "object",
                      "properties": {"full_name": {"type": "string"},
                                     "email": {"type": "string"},
                                     "phone": {"type": "string", "description": "Цифрами, 7…"},
                                     "inn": {"type": "string", "description": "10 или 12 цифр"}},
                      "required": ["full_name"]}},
        ("customer",)),
    fields=(FieldSpec("customer.full_name", "identity", "NAME", "", required=True),
            FieldSpec("customer.email", "identity", "EMAIL", ""),
            FieldSpec("customer.phone", "identity", "PHONE", "digits"),
            FieldSpec("customer.inn", "identity", "INN", "digits")),
    parse=_receipt_create_parse, mutating=True,
    result_pii=("receipt.customer.full_name", "receipt.customer.email",
                "receipt.customer.phone", "receipt.customer.inn", "error.subject"))


# --- 6. МТС Exolve SendSMS: the transactional SMS ----------------------------------

def _sms_send_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "sms_send"
    miss = _required(args, tool, "", ("destination", "text"))
    if miss:
        return miss
    destination = parse_e164(args["destination"], tool, "destination")
    if isinstance(destination, Refusal):
        return destination
    text = parse_text(args["text"], tool, "text", SMS_TEXT_LIMIT)
    if isinstance(text, Refusal):
        return text
    if not text.strip():
        return Refusal(tool, "text", "empty_text", str(text))
    out: Parsed = {"destination": destination, "text": text.strip()}
    if args.get("number") not in (None, ""):
        number = parse_text(args["number"], tool, "number", 11)
        if isinstance(number, Refusal):
            return number
        out["number"] = number.strip()
    return out


SMS_SEND = ToolSpec(
    name="sms_send",
    source="МТС Exolve POST https://api.exolve.ru/messaging/v1/SendSMS — number "
           "(sender), destination (recipient E.164), text (free, supports named "
           "variables); the queued confirmation echoes the destination (v5 notify_sms) "
           "(https://docs.exolve.ru/docs/ru/api-reference/sms-api/)",
    schema=_schema(
        "sms_send",
        "Отправить СМС на номер. Текст напиши своими словами.",
        {"destination": {"type": "string", "description": "Номер получателя в E.164, например +79161234567"},
         "text": {"type": "string", "description": "Текст сообщения, до 1000 символов"},
         "number": {"type": "string", "description": "Имя отправителя, до 11 символов"}},
        ("destination", "text")),
    fields=(FieldSpec("destination", "identity", "PHONE", "digits", required=True),
            FieldSpec("text", "free", required=True),
            FieldSpec("number", "plain")),
    parse=_sms_send_parse, mutating=True,
    result_pii=("destination", "error.subject"))


# --- 7. bank: the account and credit families (summary) ----------------------------

def _bank_accounts_list_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "bank_accounts_list"
    miss = _required(args, tool, "", ("client_id",))
    if miss:
        return miss
    client_id = str(args["client_id"]).strip()
    if not re.fullmatch(r"bc-\d{1,6}", client_id):
        return Refusal(tool, "client_id", "id_format", client_id)
    return {"client_id": client_id}


BANK_ACCOUNTS_LIST = ToolSpec(
    name="bank_accounts_list",
    source="ЦБ 809-П Прил. 1 «Схема обозначения лицевых счетов» — счёт физлица по "
           "полю `account`/`account_number`/`RQ_ACC_NUM` (A-07) (https://cbr.ru/)",
    schema=_schema(
        "bank_accounts_list",
        "Список счетов клиента банка по идентификатору клиента. Каждый счёт — 20 цифр.",
        {"client_id": {"type": "string", "description": "Идентификатор клиента банка, например bc-1"}},
        ("client_id",)),
    fields=(FieldSpec("client_id", "plain", required=True),),
    parse=_bank_accounts_list_parse, mutating=False,
    result_pii=("items[].account",))


def _ruble_transfer_create_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "ruble_transfer_create"
    miss = _required(args, tool, "", ("account", "bik"))
    if miss:
        return miss
    account = parse_digits(args["account"], tool, "account", 20, "account_format")
    bik = parse_digits(args["bik"], tool, "bik", 9, "bik_format")
    bad = _first(account, bik)
    if bad:
        return bad
    # The account key is a (account, BIK) pair check (ЦБ 515) — a transfer to an
    # account whose key does not match its БИК is refused by the bank.
    if not checksum_v6.validate_account(str(account), str(bik)):
        return Refusal(tool, "account", "account_key_mismatch", str(account))
    return {"account": account, "bik": bik}


RUBLE_TRANSFER_CREATE = ToolSpec(
    name="ruble_transfer_create",
    source="ЦБ 809-П Прил. 1 + ЦБ 515 ключ счёта по паре (счёт, БИК) — поле "
           "`account`/`RQ_ACC_NUM` (A-07) (https://cbr.ru/)",
    schema=_schema(
        "ruble_transfer_create",
        "Создать перевод по рублёвому счёту. Счёт и БИК получателя обязательны, ключ счёта проверяется.",
        {"account": {"type": "string", "description": "Счёт получателя, 20 цифр"},
         "bik": {"type": "string", "description": "БИК банка получателя, 9 цифр"}},
        ("account", "bik")),
    fields=(FieldSpec("account", "identity", "BANK_ACCOUNT", "digits", required=True),
            FieldSpec("bik", "plain", required=True)),
    parse=_ruble_transfer_create_parse, mutating=True,
    result_pii=("transfer.account", "error.subject"))


def _credit_report_request_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "credit_report_request"
    present = [key for key in ("snils", "client_id") if args.get(key) not in (None, "")]
    if len(present) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "snils":
        snils = parse_snils(args["snils"], tool, "snils")
        if isinstance(snils, Refusal):
            return snils
        return {"snils": snils}
    client_id = str(args["client_id"]).strip()
    if not re.fullmatch(r"bc-\d{1,6}", client_id):
        return Refusal(tool, "client_id", "id_format", client_id)
    return {"client_id": client_id}


CREDIT_REPORT_REQUEST = ToolSpec(
    name="credit_report_request",
    source="кредитный отчёт БКИ — УИд сделки `uid`/`deal_uid` (A-10, ЦБ 758-П "
           "Прил. 2 пп. 4–5) (https://www.nbki.ru/)",
    schema=_schema(
        "credit_report_request",
        "Запросить кредитный отчёт. По СНИЛС или по идентификатору клиента.",
        {"snils": {"type": "string", "description": "СНИЛС в формате XXX-XXX-XXX YY"},
         "client_id": {"type": "string", "description": "Идентификатор клиента, например bc-1"}},
        ()),
    fields=(FieldSpec("snils", "identity", "SNILS", "digits"),
            FieldSpec("client_id", "plain")),
    parse=_credit_report_request_parse, mutating=False,
    result_pii=("report.loans[].loan_uid",))


def _debtor_card_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "debtor_card_get"
    miss = _required(args, tool, "", ("contract_number",))
    if miss:
        return miss
    contract = _free_id(args["contract_number"], tool, "contract_number", 40,
                        "contract_number_format")
    if isinstance(contract, Refusal):
        return contract
    return {"contract_number": contract}


DEBTOR_CARD_GET = ToolSpec(
    name="debtor_card_get",
    source="досье должника (230-ФЗ) — `contract_number`/`loanNumber` (A-09) и УИд "
           "`uid`/`deal_uid` (A-10) (https://cbr.ru/)",
    schema=_schema(
        "debtor_card_get",
        "Карточка должника по номеру договора. Возвращает номер договора, УИд сделки и ФИО.",
        {"contract_number": {"type": "string", "description": "Номер кредитного договора"}},
        ("contract_number",)),
    fields=(FieldSpec("contract_number", "identity", "LOAN_CONTRACT_NUMBER", "", required=True),),
    parse=_debtor_card_get_parse, mutating=False,
    result_pii=("debtor.contract_number", "debtor.loan_uid", "debtor.name", "error.subject"))


# --- 8. medicine: ЕНП, ЭЛН, рецепт, РЭМД ------------------------------------------

def _eln_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "eln_get"
    miss = _required(args, tool, "", ("ln_code",))
    if miss:
        return miss
    ln_code = _free_id(args["ln_code"], tool, "ln_code", 12, "ln_code_format")
    if isinstance(ln_code, Refusal):
        return ln_code
    return {"ln_code": ln_code}


ELN_GET = ToolSpec(
    name="eln_get",
    source="СФР «Спецификация ЭЛН МО v2.3» — `lnCode`/`LN_CODE` (C-09) "
           "(https://sfr.gov.ru/)",
    schema=_schema(
        "eln_get",
        "Получить электронный листок нетрудоспособности по его номеру.",
        {"ln_code": {"type": "string", "description": "Номер ЭЛН, до 12 символов"}},
        ("ln_code",)),
    fields=(FieldSpec("ln_code", "identity", "ELN_NUMBER", "digits", required=True),),
    parse=_eln_get_parse, mutating=False,
    result_pii=("eln.ln_code", "eln.patient.name"))


def _remd_documents_search_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "remd_documents_search"
    miss = _required(args, tool, "", ("snils",))
    if miss:
        return miss
    snils = parse_snils(args["snils"], tool, "snils")
    if isinstance(snils, Refusal):
        return snils
    return {"snils": snils}


REMD_DOCUMENTS_SEARCH = ToolSpec(
    name="remd_documents_search",
    source="РЭМД/ЕГИСЗ поиск электронных медицинских документов — номер документа "
           "«К-2026-00412» (метка MED_CARD_NUMBER неверна, §2.4 п. 3) + ФИО пациента "
           "(https://portal.egisz.rosminzdrav.ru/)",
    schema=_schema(
        "remd_documents_search",
        "Найти медицинские документы пациента по СНИЛС. Номер документа — это номер ЭМД, не медкарты.",
        {"snils": {"type": "string", "description": "СНИЛС в формате XXX-XXX-XXX YY"}},
        ("snils",)),
    fields=(FieldSpec("snils", "identity", "SNILS", "digits", required=True),),
    parse=_remd_documents_search_parse, mutating=False,
    result_pii=("documents[].patient_name",))


def _oms_policy_find_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "oms_policy_find"
    miss = _required(args, tool, "", ("enp",))
    if miss:
        return miss
    enp = _parse_oms_enp(args["enp"], tool, "enp")
    if isinstance(enp, Refusal):
        return enp
    return {"enp": enp}


OMS_POLICY_FIND = ToolSpec(
    name="oms_policy_find",
    source="ТФОМС «Структура ЕНП» / ФФОМС 79 — `enp`/`oms_policy`/`policy_number` "
           "(A-13) (https://www.ffoms.gov.ru/)",
    schema=_schema(
        "oms_policy_find",
        "Найти полис ОМС по единому номеру полиса (ЕНП, 16 цифр).",
        {"enp": {"type": "string", "description": "ЕНП, 16 цифр"}},
        ("enp",)),
    fields=(FieldSpec("enp", "identity", "OMS_ENP", "digits", required=True),),
    parse=_oms_policy_find_parse, mutating=False,
    result_pii=("policy.enp",))


def _e_prescription_create_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "e_prescription_create"
    miss = _required(args, tool, "", ("enp", "patient_name"))
    if miss:
        return miss
    enp = _parse_oms_enp(args["enp"], tool, "enp")
    patient = parse_text(args["patient_name"], tool, "patient_name", 120)
    bad = _first(enp, patient)
    if bad:
        return bad
    return {"enp": enp, "patient_name": str(patient).strip()}


E_PRESCRIPTION_CREATE = ToolSpec(
    name="e_prescription_create",
    source="Приказ Минздрава 1094н — `enp` (A-13) + `recipe_number`/`rx_number` "
           "(C-10) (https://www.rosminzdrav.gov.ru/)",
    schema=_schema(
        "e_prescription_create",
        "Создать электронный рецепт по полису ОМС. Возвращает номер рецепта.",
        {"enp": {"type": "string", "description": "ЕНП, 16 цифр"},
         "patient_name": {"type": "string", "description": "ФИО пациента"}},
        ("enp", "patient_name")),
    fields=(FieldSpec("enp", "identity", "OMS_ENP", "digits", required=True),
            FieldSpec("patient_name", "identity", "NAME", "", required=True)),
    parse=_e_prescription_create_parse, mutating=True,
    result_pii=("prescription.enp", "prescription.number", "error.subject"))


# --- 9. retail: marketplace, loyalty, fiscal --------------------------------------

def _marketplace_order_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "marketplace_order_get"
    miss = _required(args, tool, "", ("order_id",))
    if miss:
        return miss
    order_id = str(args["order_id"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{4,30}", order_id):
        return Refusal(tool, "order_id", "id_format", order_id)
    return {"order_id": order_id}


MARKETPLACE_ORDER_GET = ToolSpec(
    name="marketplace_order_get",
    source="маркетплейс GET /order — покупатель ФИО/телефон/адрес (v4-типы) "
           "(https://www.ozon.ru/)",
    schema=_schema(
        "marketplace_order_get",
        "Заказ маркетплейса по его номеру. Возвращает покупателя и адрес доставки.",
        {"order_id": {"type": "string", "description": "Номер заказа"}},
        ("order_id",)),
    fields=(FieldSpec("order_id", "plain", required=True),),
    parse=_marketplace_order_get_parse, mutating=False,
    result_pii=("order.customer.name", "order.customer.phone", "order.delivery.address"))


def _loyalty_customer_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "loyalty_customer_get"
    miss = _required(args, tool, "", ("card_number",))
    if miss:
        return miss
    card = _parse_loyalty(args["card_number"], tool, "card_number")
    if isinstance(card, Refusal):
        return card
    return {"card_number": card}


LOYALTY_CUSTOMER_GET = ToolSpec(
    name="loyalty_customer_get",
    source="карта лояльности — `loyalty_card`/`bonus_card`/`card_number` (C-22, GS1) "
           "(https://www.mindbox.ru/)",
    schema=_schema(
        "loyalty_customer_get",
        "Найти клиента по номеру карты лояльности.",
        {"card_number": {"type": "string", "description": "Номер карты, 13–18 цифр"}},
        ("card_number",)),
    fields=(FieldSpec("card_number", "identity", "LOYALTY_CARD_NUMBER", "digits", required=True),),
    parse=_loyalty_customer_get_parse, mutating=False,
    result_pii=("customer.card_number",))


def _loyalty_card_bind_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "loyalty_card_bind"
    miss = _required(args, tool, "", ("card_number", "customer_name"))
    if miss:
        return miss
    card = _parse_loyalty(args["card_number"], tool, "card_number")
    name = parse_text(args["customer_name"], tool, "customer_name", 120)
    bad = _first(card, name)
    if bad:
        return bad
    return {"card_number": card, "customer_name": str(name).strip()}


LOYALTY_CARD_BIND = ToolSpec(
    name="loyalty_card_bind",
    source="привязка карты лояльности — `loyalty_card`/`bonus_card` (C-22, GS1) "
           "(https://www.mindbox.ru/)",
    schema=_schema(
        "loyalty_card_bind",
        "Привязать карту лояльности к клиенту.",
        {"card_number": {"type": "string", "description": "Номер карты, 13–18 цифр"},
         "customer_name": {"type": "string", "description": "ФИО клиента"}},
        ("card_number", "customer_name")),
    fields=(FieldSpec("card_number", "identity", "LOYALTY_CARD_NUMBER", "digits", required=True),
            FieldSpec("customer_name", "identity", "NAME", "", required=True)),
    parse=_loyalty_card_bind_parse, mutating=True,
    result_pii=("card.card_number", "error.subject"))


def _fiscal_receipt_create_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "fiscal_receipt_create"
    miss = _required(args, tool, "", ("customer",))
    if miss:
        return miss
    customer = _obj(args["customer"], tool, "customer")
    if isinstance(customer, Refusal):
        return customer
    miss = _required(customer, tool, "customer", ("full_name",))
    if miss:
        return miss
    full_name = parse_text(customer["full_name"], tool, "customer.full_name", 200)
    if isinstance(full_name, Refusal):
        return full_name
    has_email = customer.get("email") not in (None, "")
    has_phone = customer.get("phone") not in (None, "")
    if not has_email and not has_phone:
        return Refusal(tool, "customer", "contact_required", "")
    out_customer: Parsed = {"full_name": full_name.strip()}
    if has_email:
        email = str(customer["email"]).strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return Refusal(tool, "customer.email", "email_format", str(customer["email"]))
        out_customer["email"] = email
    if has_phone:
        phone = _parse_numeric_phone(customer["phone"], tool, "customer.phone")
        if isinstance(phone, Refusal):
            return phone
        out_customer["phone"] = phone
    if customer.get("inn") not in (None, ""):
        inn = parse_inn(customer["inn"], tool, "customer.inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        out_customer["inn"] = inn
    return {"customer": out_customer}


FISCAL_RECEIPT_CREATE = ToolSpec(
    name="fiscal_receipt_create",
    source="АТОЛ 54-ФЗ фискализация чека — customer.{full_name, email, phone, inn}; "
           "сохранённый чек эхом отдаёт покупателя (R-41, §2.4 п. 4: ответ АТОЛ без ПД) "
           "(https://www.atol.ru/)",
    schema=_schema(
        "fiscal_receipt_create",
        "Пробить фискальный чек 54-ФЗ через АТОЛ. Покупатель: ФИО и ровно один канал.",
        {"customer": {"type": "object",
                      "properties": {"full_name": {"type": "string"},
                                     "email": {"type": "string"},
                                     "phone": {"type": "string", "description": "Цифрами, 7…"},
                                     "inn": {"type": "string", "description": "10 или 12 цифр"}},
                      "required": ["full_name"]}},
        ("customer",)),
    fields=(FieldSpec("customer.full_name", "identity", "NAME", "", required=True),
            FieldSpec("customer.email", "identity", "EMAIL", ""),
            FieldSpec("customer.phone", "identity", "PHONE", "digits"),
            FieldSpec("customer.inn", "identity", "INN", "digits")),
    parse=_fiscal_receipt_create_parse, mutating=True,
    result_pii=("receipt.customer.full_name", "receipt.customer.email",
                "receipt.customer.phone", "receipt.customer.inn", "error.subject"))


# --- 10. logistics: CDEK order info -------------------------------------------------

def _cdek_order_info_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "cdek_order_info"
    miss = _required(args, tool, "", ("order_id",))
    if miss:
        return miss
    order_id = str(args["order_id"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{4,30}", order_id):
        return Refusal(tool, "order_id", "id_format", order_id)
    return {"order_id": order_id}


CDEK_ORDER_INFO = ToolSpec(
    name="cdek_order_info",
    source="CDEK API order info — получатель: паспорт по полям (серия/номер) + ИНН "
           "(§2.5 «паспорт ПО ПОЛЯМ») (https://www.cdek.ru/)",
    schema=_schema(
        "cdek_order_info",
        "Заказ CDEK по номеру. Возвращает получателя: паспорт серией и номером, ИНН.",
        {"order_id": {"type": "string", "description": "Номер заказа"}},
        ("order_id",)),
    fields=(FieldSpec("order_id", "plain", required=True),),
    parse=_cdek_order_info_parse, mutating=False,
    result_pii=("order.recipient.name", "order.recipient.passport.series",
                "order.recipient.passport.number", "order.recipient.inn", "error.subject"))


# --- 11. insurance: ОСАГО, убыток --------------------------------------------------

def _osago_policy_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "osago_policy_check"
    present = [key for key in ("policy_number", "vin") if args.get(key) not in (None, "")]
    if len(present) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "policy_number":
        policy = _parse_osago(args["policy_number"], tool, "policy_number")
        if isinstance(policy, Refusal):
            return policy
        return {"policy_number": policy}
    vin = _parse_vin(args["vin"], tool, "vin")
    if isinstance(vin, Refusal):
        return vin
    return {"vin": vin}


OSAGO_POLICY_CHECK = ToolSpec(
    name="osago_policy_check",
    source="РСА проверка полиса ОСАГО — `osago_number`/`policySerial` (A-15) + "
           "`vin` (B-01) (https://autoins.ru/)",
    schema=_schema(
        "osago_policy_check",
        "Проверить полис ОСАГО по номеру полиса или по VIN. Ровно один ключ.",
        {"policy_number": {"type": "string", "description": "Серия и номер полиса, например ХХХ 0123456789"},
         "vin": {"type": "string", "description": "VIN, 17 символов"}},
        ()),
    fields=(FieldSpec("policy_number", "identity", "OSAGO_POLICY", ""),
            FieldSpec("vin", "identity", "VIN", "")),
    parse=_osago_policy_check_parse, mutating=False,
    result_pii=("policy.number", "policy.vin"))


def _insurance_claim_create_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "insurance_claim_create"
    miss = _required(args, tool, "", ("policy_number",))
    if miss:
        return miss
    policy = _parse_osago(args["policy_number"], tool, "policy_number")
    if isinstance(policy, Refusal):
        return policy
    out: Parsed = {"policy_number": policy}
    if args.get("vin") not in (None, ""):
        vin = _parse_vin(args["vin"], tool, "vin")
        if isinstance(vin, Refusal):
            return vin
        out["vin"] = vin
    if args.get("sts_number") not in (None, ""):
        sts = _digits_spaceless(args["sts_number"], tool, "sts_number", 10, "sts_format")
        if isinstance(sts, Refusal):
            return sts
        out["sts_number"] = sts
    if args.get("account") not in (None, ""):
        account = parse_digits(args["account"], tool, "account", 20, "account_format")
        if isinstance(account, Refusal):
            return account
        out["account"] = account
    return out


INSURANCE_CLAIM_CREATE = ToolSpec(
    name="insurance_claim_create",
    source="урегулирование убытка — `policy_number` (A-15), `claimId`/`loss_number` "
           "(A-17) + VIN/СТС/счёт (B-01/B-09/A-07) (https://autoins.ru/)",
    schema=_schema(
        "insurance_claim_create",
        "Завести страховой убыток по полису ОСАГО. Возвращает номер дела.",
        {"policy_number": {"type": "string", "description": "Серия и номер полиса ОСАГО"},
         "vin": {"type": "string", "description": "VIN, 17 символов"},
         "sts_number": {"type": "string", "description": "СТС, 10 цифр"},
         "account": {"type": "string", "description": "Счёт для выплаты, 20 цифр"}},
        ("policy_number",)),
    fields=(FieldSpec("policy_number", "identity", "OSAGO_POLICY", "", required=True),
            FieldSpec("vin", "identity", "VIN", ""),
            FieldSpec("sts_number", "identity", "STS_NUMBER", "digits"),
            FieldSpec("account", "identity", "BANK_ACCOUNT", "digits")),
    parse=_insurance_claim_create_parse, mutating=True,
    result_pii=("claim.policy_number", "claim.claim_number", "error.subject"))


# --- 12. auto: штрафы, ЭПТС, ВУ ----------------------------------------------------

def _traffic_fines_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "traffic_fines_check"
    miss = _required(args, tool, "", ("sts_number",))
    if miss:
        return miss
    sts = _digits_spaceless(args["sts_number"], tool, "sts_number", 10, "sts_format")
    if isinstance(sts, Refusal):
        return sts
    return {"sts_number": sts}


TRAFFIC_FINES_CHECK = ToolSpec(
    name="traffic_fines_check",
    source="ГИБДД штрафы — `sts_number`/`стс` (B-09) → `uin` (B-03, Минфин 107н) "
           "(https://гибдд.рф/)",
    schema=_schema(
        "traffic_fines_check",
        "Проверить штрафы ГИБДД по СТС. Возвращает начисления с УИН.",
        {"sts_number": {"type": "string", "description": "СТС, 10 цифр, например 77 12 345678"}},
        ("sts_number",)),
    fields=(FieldSpec("sts_number", "identity", "STS_NUMBER", "digits", required=True),),
    parse=_traffic_fines_check_parse, mutating=False,
    result_pii=("fines[].uin",))


def _epts_status_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "epts_status_get"
    present = [key for key in ("epts_number", "vin") if args.get(key) not in (None, "")]
    if len(present) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "epts_number":
        epts = _parse_epts(args["epts_number"], tool, "epts_number")
        if isinstance(epts, Refusal):
            return epts
        return {"epts_number": epts}
    vin = _parse_vin(args["vin"], tool, "vin")
    if isinstance(vin, Refusal):
        return vin
    return {"vin": vin}


EPTS_STATUS_GET = ToolSpec(
    name="epts_status_get",
    source="ЭПТС — `epts_number`/`eptsNumber` (B-02, ЕЭК № 122) + `vin` (B-01) "
           "(https://elpts.ru/)",
    schema=_schema(
        "epts_status_get",
        "Статус электронного ПТС по номеру ЭПТС или по VIN. Ровно один ключ.",
        {"epts_number": {"type": "string", "description": "Номер ЭПТС, 15 цифр"},
         "vin": {"type": "string", "description": "VIN, 17 символов"}},
        ()),
    fields=(FieldSpec("epts_number", "identity", "EPTS_NUMBER", "digits"),
            FieldSpec("vin", "identity", "VIN", "")),
    parse=_epts_status_get_parse, mutating=False,
    result_pii=("passport.epts_number", "passport.vin"))


def _driver_license_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "driver_license_check"
    miss = _required(args, tool, "", ("license_number",))
    if miss:
        return miss
    lic = _digits_spaceless(args["license_number"], tool, "license_number", 10,
                            "driver_license_format")
    if isinstance(lic, Refusal):
        return lic
    return {"license_number": lic}


DRIVER_LICENSE_CHECK = ToolSpec(
    name="driver_license_check",
    source="ГИБДД проверка водительского удостоверения — `driver_license`/`dl_number` "
           "(B-11, Приказ МВД № 365) (https://гибдд.рф/)",
    schema=_schema(
        "driver_license_check",
        "Проверить водительское удостоверение по серии и номеру.",
        {"license_number": {"type": "string", "description": "Серия и номер ВУ, 10 цифр, например 99 12 345678"}},
        ("license_number",)),
    fields=(FieldSpec("license_number", "identity", "DRIVER_LICENSE", "digits", required=True),),
    parse=_driver_license_check_parse, mutating=False,
    result_pii=("license.number", "error.subject"))


# --- 13. telecom: абонент, SIM -----------------------------------------------------

def _subscriber_profile_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "subscriber_profile_get"
    present = [key for key in ("phone", "account") if args.get(key) not in (None, "")]
    if len(present) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "phone":
        phone = parse_e164(args["phone"], tool, "phone")
        if isinstance(phone, Refusal):
            return phone
        return {"phone": phone}
    account = _shaped(args["account"], tool, "account", r"\d{8,12}",
                      "subscriber_account_format")
    if isinstance(account, Refusal):
        return account
    return {"account": account}


SUBSCRIBER_PROFILE_GET = ToolSpec(
    name="subscriber_profile_get",
    source="профиль абонента — `personal_account`/`account_number` (C-06) + "
           "`iccid`/`sim_iccid` (C-02), `imsi` (C-03), `imei` (C-01) "
           "(https://moskva.mts.ru/)",
    schema=_schema(
        "subscriber_profile_get",
        "Профиль абонента связи по телефону или лицевому счёту.",
        {"phone": {"type": "string", "description": "Телефон E.164"},
         "account": {"type": "string", "description": "Лицевой счёт, 8–12 цифр"}},
        ()),
    fields=(FieldSpec("phone", "identity", "PHONE", "digits"),
            FieldSpec("account", "identity", "SUBSCRIBER_ACCOUNT", "digits")),
    parse=_subscriber_profile_get_parse, mutating=False,
    result_pii=("subscriber.account", "subscriber.sim.iccid",
                "subscriber.sim.imsi", "subscriber.device.imei"))


def _sim_replace_request_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "sim_replace_request"
    miss = _required(args, tool, "", ("iccid",))
    if miss:
        return miss
    iccid = _parse_iccid(args["iccid"], tool, "iccid")
    if isinstance(iccid, Refusal):
        return iccid
    return {"iccid": iccid}


SIM_REPLACE_REQUEST = ToolSpec(
    name="sim_replace_request",
    source="замена SIM — `iccid`/`sim_iccid` (C-02, Лун, ITU-T E.118 §6) "
           "(https://moskva.mts.ru/)",
    schema=_schema(
        "sim_replace_request",
        "Заявка на замену SIM-карты по ICCID.",
        {"iccid": {"type": "string", "description": "ICCID, 19 цифр"}},
        ("iccid",)),
    fields=(FieldSpec("iccid", "identity", "ICCID", "digits", required=True),),
    parse=_sim_replace_request_parse, mutating=True,
    result_pii=("request.iccid", "error.subject"))


# --- 14. real estate: ЕГРН, ГИС ЖКХ ------------------------------------------------

def _egrn_extract_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "egrn_extract_get"
    miss = _required(args, tool, "", ("cadastral_number",))
    if miss:
        return miss
    cad = _parse_cadastral(args["cadastral_number"], tool, "cadastral_number")
    if isinstance(cad, Refusal):
        return cad
    return {"cadastral_number": cad}


EGRN_EXTRACT_GET = ToolSpec(
    name="egrn_extract_get",
    source="Росреестр выписка ЕГРН — `cadastral_number`/`cadastralNumber` (B-12, "
           "Приказ П/0183 п. 3) (https://rosreestr.gov.ru/)",
    schema=_schema(
        "egrn_extract_get",
        "Выписка из ЕГРН по кадастровому номеру.",
        {"cadastral_number": {"type": "string", "description": "Кадастровый номер, например 77:01:0001001:1234"}},
        ("cadastral_number",)),
    fields=(FieldSpec("cadastral_number", "identity", "CADASTRAL_NUMBER", "digits", required=True),),
    parse=_egrn_extract_get_parse, mutating=False,
    result_pii=("extract.cadastral_number", "extract.owner.name"))


def _gis_gkh_account_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "gis_gkh_account_get"
    miss = _required(args, tool, "", ("els",))
    if miss:
        return miss
    els = _parse_els(args["els"], tool, "els")
    if isinstance(els, Refusal):
        return els
    return {"els": els}


GIS_GKH_ACCOUNT_GET = ToolSpec(
    name="gis_gkh_account_get",
    source="ГИС ЖКХ — `els`/`unified_account` (B-15) + `personal_account` (B-16) "
           "(https://dom.gosuslugi.ru/)",
    schema=_schema(
        "gis_gkh_account_get",
        "Счёт ЖКУ по ЕЛС или идентификатору платёжного документа.",
        {"els": {"type": "string", "description": "ЕЛС/ИЖКУ/ИПД, например 60АА000593-01"}},
        ("els",)),
    fields=(FieldSpec("els", "identity", "GIS_ZHKH_ELS", "", required=True),),
    parse=_gis_gkh_account_get_parse, mutating=False,
    result_pii=("account.els", "account.personal_account"))


# --- 15. hospitality: PMS, миграционный учёт, бронь --------------------------------

def _pms_booking_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "pms_booking_get"
    miss = _required(args, tool, "", ("booking_id",))
    if miss:
        return miss
    booking_id = str(args["booking_id"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{4,30}", booking_id):
        return Refusal(tool, "booking_id", "id_format", booking_id)
    return {"booking_id": booking_id}


PMS_BOOKING_GET = ToolSpec(
    name="pms_booking_get",
    source="PMS бронь — гость ФИО/телефон (v4-типы); BOOKING_ID вне реестра (plain) "
           "(https://www.travelline.ru/)",
    schema=_schema(
        "pms_booking_get",
        "Бронь в гостинице по номеру бронирования.",
        {"booking_id": {"type": "string", "description": "Номер бронирования"}},
        ("booking_id",)),
    fields=(FieldSpec("booking_id", "plain", required=True),),
    parse=_pms_booking_get_parse, mutating=False,
    result_pii=("booking.guest.name", "booking.guest.phone"))


def _guest_arrival_notify_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "guest_arrival_notify"
    miss = _required(args, tool, "", ("full_name", "document_number"))
    if miss:
        return miss
    name = parse_text(args["full_name"], tool, "full_name", 120)
    doc = _digits_spaceless(args["document_number"], tool, "document_number", 9,
                            "intl_passport_format")
    bad = _first(name, doc)
    if bad:
        return bad
    out: Parsed = {"full_name": str(name).strip(), "document_number": doc}
    if args.get("migration_card") not in (None, ""):
        out["migration_card"] = str(args["migration_card"]).strip()
    return out


GUEST_ARRIVAL_NOTIFY = ToolSpec(
    name="guest_arrival_notify",
    source="миграционный учёт гостя — ФИО + загранпаспорт `docNumber` (A-01, 9 цифр); "
           "миграционная карта — вне реестра (C-21 ДЕРЖИМ, plain) (https://мвд.рф/)",
    schema=_schema(
        "guest_arrival_notify",
        "Уведомить о прибытии иностранного гостя. Паспорт — заграничный, 9 цифр.",
        {"full_name": {"type": "string", "description": "ФИО гостя"},
         "document_number": {"type": "string", "description": "Загранпаспорт, 9 цифр, например 75 1234567"},
         "migration_card": {"type": "string", "description": "Номер миграционной карты"}},
        ("full_name", "document_number")),
    fields=(FieldSpec("full_name", "identity", "NAME", "", required=True),
            FieldSpec("document_number", "identity", "INTL_PASSPORT", "digits", required=True),
            FieldSpec("migration_card", "plain")),
    parse=_guest_arrival_notify_parse, mutating=True,
    result_pii=("guest.full_name", "guest.document_number", "error.subject"))


def _flight_order_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "flight_order_get"
    miss = _required(args, tool, "", ("pnr",))
    if miss:
        return miss
    pnr = _shaped(args["pnr"], tool, "pnr", r"[A-Z0-9]{5,6}", "pnr_format")
    if isinstance(pnr, Refusal):
        return pnr
    return {"pnr": pnr}


FLIGHT_ORDER_GET = ToolSpec(
    name="flight_order_get",
    source="бронь авиабилета (GDS) — `pnr`/`booking_reference` (C-19) + загранпаспорт "
           "`passport_number` (A-01) (https://www.amadeus.com/)",
    schema=_schema(
        "flight_order_get",
        "Бронь авиабилета по PNR. Возвращает пассажира и загранпаспорт.",
        {"pnr": {"type": "string", "description": "Код бронирования, 5–6 символов"}},
        ("pnr",)),
    fields=(FieldSpec("pnr", "identity", "PNR", "", required=True),),
    parse=_flight_order_get_parse, mutating=False,
    result_pii=("order.pnr", "order.passenger.name",
                "order.passenger.passport_number", "error.subject"))


# --- 16. HR: сотрудник, резюме, зарплатный реестр ----------------------------------

def _hr_employee_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "hr_employee_get"
    miss = _required(args, tool, "", ("tab_number",))
    if miss:
        return miss
    tab = _shaped(args["tab_number"], tool, "tab_number", r"\d{6,10}", "tab_number_format")
    if isinstance(tab, Refusal):
        return tab
    return {"tab_number": tab}


HR_EMPLOYEE_GET = ToolSpec(
    name="hr_employee_get",
    source="HRIS (1С ЗУП) — `tab_number`/`personnel_number`/`ТабельныйНомер` (C-16) "
           "(https://www.1c.ru/)",
    schema=_schema(
        "hr_employee_get",
        "Карточка сотрудника по табельному номеру.",
        {"tab_number": {"type": "string", "description": "Табельный номер, 6–10 цифр"}},
        ("tab_number",)),
    fields=(FieldSpec("tab_number", "identity", "EMPLOYEE_TAB_NUMBER", "digits", required=True),),
    parse=_hr_employee_get_parse, mutating=False,
    result_pii=("employee.tab_number", "employee.name"))


def _resume_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "resume_get"
    miss = _required(args, tool, "", ("resume_id",))
    if miss:
        return miss
    resume_id = str(args["resume_id"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{4,30}", resume_id):
        return Refusal(tool, "resume_id", "id_format", resume_id)
    return {"resume_id": resume_id}


RESUME_GET = ToolSpec(
    name="resume_get",
    source="hh.ru резюме — ФИО/телефон/почта (v4-типы) (https://hh.ru/)",
    schema=_schema(
        "resume_get",
        "Резюме по его идентификатору.",
        {"resume_id": {"type": "string", "description": "Идентификатор резюме"}},
        ("resume_id",)),
    fields=(FieldSpec("resume_id", "plain", required=True),),
    parse=_resume_get_parse, mutating=False,
    result_pii=("resume.name", "resume.phone", "resume.email"))


def _payroll_card_registry_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "payroll_card_registry"
    miss = _required(args, tool, "", ("employees",))
    if miss:
        return miss
    raw = args["employees"]
    if not isinstance(raw, list) or not raw:
        return Refusal(tool, "employees", "array_required", str(raw))
    rows: list[dict[str, object]] = []
    for index, entry in enumerate(raw):
        block = _obj(entry, tool, f"employees[{index}]")
        if isinstance(block, Refusal):
            return block
        miss = _required(block, tool, f"employees[{index}]", ("tab_number", "account"))
        if miss:
            return miss
        tab = _shaped(block["tab_number"], tool, f"employees[{index}].tab_number",
                      r"\d{6,10}", "tab_number_format")
        account = parse_digits(block["account"], tool, f"employees[{index}].account",
                               20, "account_format")
        bad = _first(tab, account)
        if bad:
            return bad
        rows.append({"tab_number": tab, "account": account})
    return {"employees": rows}


PAYROLL_CARD_REGISTRY = ToolSpec(
    name="payroll_card_registry",
    source="зарплатный реестр — `tab_number`/`ТабельныйНомер` (C-16) + `account`/"
           "`RQ_ACC_NUM` (A-07) (https://www.1c.ru/)",
    schema=_schema(
        "payroll_card_registry",
        "Реестр зарплатных карт: по сотруднику табельный номер и счёт.",
        {"employees": {"type": "array", "description": "Сотрудники",
                       "items": {"type": "object",
                                 "properties": {"tab_number": {"type": "string", "description": "6–10 цифр"},
                                                "account": {"type": "string", "description": "Счёт, 20 цифр"}},
                                 "required": ["tab_number", "account"]}}},
        ("employees",)),
    fields=(FieldSpec("employees[].tab_number", "identity", "EMPLOYEE_TAB_NUMBER", "digits", required=True),
            FieldSpec("employees[].account", "identity", "BANK_ACCOUNT", "digits", required=True)),
    parse=_payroll_card_registry_parse, mutating=True,
    result_pii=("rows[].tab_number", "rows[].account", "error.subject"))


# --- 17. legal: арбитраж, наследство -----------------------------------------------

def _arbitration_case_search_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "arbitration_case_search"
    miss = _required(args, tool, "", ("case_number",))
    if miss:
        return miss
    case = _parse_arbitrazh(args["case_number"], tool, "case_number")
    if isinstance(case, Refusal):
        return case
    return {"case_number": case}


ARBITRATION_CASE_SEARCH = ToolSpec(
    name="arbitration_case_search",
    source="kad.arbitr.ru — `case_number`/`caseNumber` (B-05, Инструкция ВАС № 100) + "
           "`ogrnip` (A-11) (https://kad.arbitr.ru/)",
    schema=_schema(
        "arbitration_case_search",
        "Найти арбитражное дело по номеру.",
        {"case_number": {"type": "string", "description": "Номер дела, например А31-2840/2013"}},
        ("case_number",)),
    fields=(FieldSpec("case_number", "identity", "ARBITRAZH_CASE_NO", "", required=True),),
    parse=_arbitration_case_search_parse, mutating=False,
    result_pii=("cases[].case_number", "cases[].party_ogrnip"))


def _probate_case_search_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "probate_case_search"
    miss = _required(args, tool, "", ("deceased_name",))
    if miss:
        return miss
    name = parse_text(args["deceased_name"], tool, "deceased_name", 120)
    if isinstance(name, Refusal):
        return name
    if not name.strip():
        return Refusal(tool, "deceased_name", "name_format", str(name))
    return {"deceased_name": name.strip()}


PROBATE_CASE_SEARCH = ToolSpec(
    name="probate_case_search",
    source="нотариальный реестр наследственных дел — ФИО умершего (v4 NAME); "
           "PROBATE_CASE_NUMBER вне реестра (plain) (https://notariat.ru/)",
    schema=_schema(
        "probate_case_search",
        "Найти наследственное дело по ФИО умершего.",
        {"deceased_name": {"type": "string", "description": "ФИО умершего"}},
        ("deceased_name",)),
    fields=(FieldSpec("deceased_name", "identity", "NAME", "", required=True),),
    parse=_probate_case_search_parse, mutating=False,
    result_pii=("cases[].deceased_name",))


# --- 18. government: ФНС, ГИС ГМП, диплом, ЕГЭ -------------------------------------

def _fns_inn_lookup_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "fns_inn_lookup"
    miss = _required(args, tool, "", ("full_name", "birth_date"))
    if miss:
        return miss
    name = parse_text(args["full_name"], tool, "full_name", 120)
    birth = parse_iso_date(args["birth_date"], tool, "birth_date")
    bad = _first(name, birth)
    if bad:
        return bad
    return {"full_name": str(name).strip(), "birth_date": birth}


FNS_INN_LOOKUP = ToolSpec(
    name="fns_inn_lookup",
    source="ФНС поиск ИНН по ФИО и дате рождения (https://www.nalog.gov.ru/)",
    schema=_schema(
        "fns_inn_lookup",
        "Найти ИНН физлица по ФИО и дате рождения.",
        {"full_name": {"type": "string", "description": "ФИО"},
         "birth_date": {"type": "string", "description": "ГГГГ-ММ-ДД"}},
        ("full_name", "birth_date")),
    fields=(FieldSpec("full_name", "identity", "NAME", "", required=True),
            FieldSpec("birth_date", "identity", "DOB", "iso", required=True)),
    parse=_fns_inn_lookup_parse, mutating=False,
    result_pii=("person.full_name", "person.inn"))


def _npd_status_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "npd_status_check"
    miss = _required(args, tool, "", ("inn",))
    if miss:
        return miss
    inn = parse_inn(args["inn"], tool, "inn", (12,))
    if isinstance(inn, Refusal):
        return inn
    return {"inn": inn}


NPD_STATUS_CHECK = ToolSpec(
    name="npd_status_check",
    source="ФНС статус самозанятого (НПД) — ИНН физлица (v4 INN) "
           "(https://www.nalog.gov.ru/)",
    schema=_schema(
        "npd_status_check",
        "Проверить статус самозанятого по ИНН.",
        {"inn": {"type": "string", "description": "ИНН физлица, 12 цифр"}},
        ("inn",)),
    fields=(FieldSpec("inn", "identity", "INN", "digits", required=True),),
    parse=_npd_status_check_parse, mutating=False,
    result_pii=("person.inn", "error.subject"))


def _budget_charges_find_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "budget_charges_find"
    miss = _required(args, tool, "", ("inn",))
    if miss:
        return miss
    inn = parse_inn(args["inn"], tool, "inn", (12,))
    if isinstance(inn, Refusal):
        return inn
    return {"inn": inn}


BUDGET_CHARGES_FIND = ToolSpec(
    name="budget_charges_find",
    source="ГИС ГМП начисления — `uin` (B-03, Минфин 107н); паспорт внутри "
           "идентификатора плательщика (V6T-05, plain) (https://www.nalog.gov.ru/)",
    schema=_schema(
        "budget_charges_find",
        "Найти начисления по ИНН плательщика. Возвращает УИН.",
        {"inn": {"type": "string", "description": "ИНН физлица, 12 цифр"}},
        ("inn",)),
    fields=(FieldSpec("inn", "identity", "INN", "digits", required=True),),
    parse=_budget_charges_find_parse, mutating=False,
    result_pii=("charges[].uin",))


def _diploma_registry_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "diploma_registry_check"
    miss = _required(args, tool, "", ("diploma_number",))
    if miss:
        return miss
    num = _digits_spaceless(args["diploma_number"], tool, "diploma_number", 13,
                            "diploma_format")
    if isinstance(num, Refusal):
        return num
    return {"diploma_number": num}


DIPLOMA_REGISTRY_CHECK = ToolSpec(
    name="diploma_registry_check",
    source="ФРДО — `diploma_series`/`diploma_number` (C-12, Приказ Минобрнауки № 645) "
           "(https://frdo.obrnadzor.gov.ru/)",
    schema=_schema(
        "diploma_registry_check",
        "Проверить диплом в реестре ФРДО по серии и номеру.",
        {"diploma_number": {"type": "string", "description": "Серия и номер диплома, 13 цифр, например 107724 0001234"}},
        ("diploma_number",)),
    fields=(FieldSpec("diploma_number", "identity", "DIPLOMA_NUMBER", "digits", required=True),),
    parse=_diploma_registry_check_parse, mutating=False,
    result_pii=("diploma.number",))


def _exam_results_check_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "exam_results_check"
    miss = _required(args, tool, "", ("reg_code",))
    if miss:
        return miss
    reg_code = _free_id(args["reg_code"], tool, "reg_code", 30, "reg_code_format")
    if isinstance(reg_code, Refusal):
        return reg_code
    return {"reg_code": reg_code}


EXAM_RESULTS_CHECK = ToolSpec(
    name="exam_results_check",
    source="ЕГЭ результаты — ФИО выпускника (v4 NAME); EXAM_REG_CODE вне реестра "
           "(plain) (https://checkege.rustest.ru/)",
    schema=_schema(
        "exam_results_check",
        "Результаты экзаменов по коду регистрации.",
        {"reg_code": {"type": "string", "description": "Код регистрации экзамена"}},
        ("reg_code",)),
    fields=(FieldSpec("reg_code", "plain", required=True),),
    parse=_exam_results_check_parse, mutating=False,
    result_pii=("results[].full_name",))


# --- 19. education: LMS ------------------------------------------------------------

def _lms_user_get_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "lms_user_get"
    miss = _required(args, tool, "", ("query",))
    if miss:
        return miss
    query = parse_text(args["query"], tool, "query", 100)
    if isinstance(query, Refusal):
        return query
    if not query.strip():
        return Refusal(tool, "query", "empty_query", str(query))
    return {"query": query.strip()}


LMS_USER_GET = ToolSpec(
    name="lms_user_get",
    source="LMS — `student_id`/`idnumber` (C-14) + `login`/`username` (C-27) "
           "(https://edu.ru/)",
    schema=_schema(
        "lms_user_get",
        "Найти пользователя LMS по имени или логину.",
        {"query": {"type": "string", "description": "Имя или логин, до 100 символов"}},
        ("query",)),
    fields=(FieldSpec("query", "free", required=True),),
    parse=_lms_user_get_parse, mutating=False,
    result_pii=("users[].student_id", "users[].login", "users[].name"))


# --- 20. BI: SQL, выгрузка ---------------------------------------------------------

def _dwh_sql_query_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "dwh_sql_query"
    miss = _required(args, tool, "", ("sql",))
    if miss:
        return miss
    sql = parse_text(args["sql"], tool, "sql", 20000)
    if isinstance(sql, Refusal):
        return sql
    if not sql.strip():
        return Refusal(tool, "sql", "empty_query", str(sql))
    return {"sql": sql.strip()}


DWH_SQL_QUERY = ToolSpec(
    name="dwh_sql_query",
    source="ClickHouse SQL — ФИО/телефон/ИНН по столбцам результата (v4-типы); "
           "литерал ПД в SQL — свободный лист (§2.5) (https://clickhouse.com/)",
    schema=_schema(
        "dwh_sql_query",
        "Выполнить SQL-запрос к хранилищу. Результат — строки с колонками ФИО, телефон, ИНН.",
        {"sql": {"type": "string", "description": "Текст SQL, до 20000 символов"}},
        ("sql",)),
    fields=(FieldSpec("sql", "free", required=True),),
    parse=_dwh_sql_query_parse, mutating=False,
    result_pii=("rows[].full_name", "rows[].phone", "rows[].inn", "error.subject"))


def _bi_chart_export_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "bi_chart_export"
    miss = _required(args, tool, "", ("chart_id",))
    if miss:
        return miss
    chart_id = str(args["chart_id"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{4,30}", chart_id):
        return Refusal(tool, "chart_id", "id_format", chart_id)
    return {"chart_id": chart_id}


BI_CHART_EXPORT = ToolSpec(
    name="bi_chart_export",
    source="BI выгрузка графика — ФИО/телефон по столбцам (v4-типы) "
           "(https://clickhouse.com/)",
    schema=_schema(
        "bi_chart_export",
        "Выгрузить данные графика BI. Возвращает строки с ФИО и телефоном.",
        {"chart_id": {"type": "string", "description": "Идентификатор графика"}},
        ("chart_id",)),
    fields=(FieldSpec("chart_id", "plain", required=True),),
    parse=_bi_chart_export_parse, mutating=False,
    result_pii=("rows[].name", "rows[].phone"))


# --- 21. marketing: CDP, Метрика ---------------------------------------------------

def _audience_segment_upload_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "audience_segment_upload"
    miss = _required(args, tool, "", ("customers",))
    if miss:
        return miss
    raw = args["customers"]
    if not isinstance(raw, list) or not raw:
        return Refusal(tool, "customers", "array_required", str(raw))
    rows: list[dict[str, object]] = []
    for index, entry in enumerate(raw):
        block = _obj(entry, tool, f"customers[{index}]")
        if isinstance(block, Refusal):
            return block
        miss = _required(block, tool, f"customers[{index}]", ("customer_id",))
        if miss:
            return miss
        cid = _free_id(block["customer_id"], tool, f"customers[{index}].customer_id",
                       40, "customer_id_format")
        if isinstance(cid, Refusal):
            return cid
        rows.append({"customer_id": cid})
    return {"customers": rows, "hashed": bool(args.get("hashed"))}


AUDIENCE_SEGMENT_UPLOAD = ToolSpec(
    name="audience_segment_upload",
    source="CDP загрузка сегмента — `customer_id`/`client_id`/`external_id` (C-26); "
           "загруженные id эхом отдаются (R-41; hashed=true — OD-49) "
           "(https://www.mindbox.ru/)",
    schema=_schema(
        "audience_segment_upload",
        "Загрузить сегмент аудитории по ID клиентов.",
        {"customers": {"type": "array", "description": "Клиенты",
                       "items": {"type": "object",
                                 "properties": {"customer_id": {"type": "string"}},
                                 "required": ["customer_id"]}},
         "hashed": {"type": "boolean", "description": "Хэшировать id перед загрузкой"}},
        ("customers",)),
    fields=(FieldSpec("customers[].customer_id", "identity", "CDP_CUSTOMER_ID", "", required=True),),
    parse=_audience_segment_upload_parse, mutating=True,
    result_pii=("uploaded[].customer_id", "error.subject"))


def _web_visits_export_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "web_visits_export"
    miss = _required(args, tool, "", ("date_from", "date_to"))
    if miss:
        return miss
    start = parse_iso_date(args["date_from"], tool, "date_from")
    end = parse_iso_date(args["date_to"], tool, "date_to")
    bad = _first(start, end)
    if bad:
        return bad
    return {"date_from": start, "date_to": end}


WEB_VISITS_EXPORT = ToolSpec(
    name="web_visits_export",
    source="Яндекс Метрика выгрузка визитов — `ClientId`/`_ym_uid` (C-25) + "
           "`ip_address`/`client_ip` (C-05) (https://yandex.ru/dev/metrika/)",
    schema=_schema(
        "web_visits_export",
        "Выгрузить визиты сайта за период. Возвращает ClientID и IP посетителей.",
        {"date_from": {"type": "string", "description": "Начало периода, ГГГГ-ММ-ДД"},
         "date_to": {"type": "string", "description": "Конец периода, ГГГГ-ММ-ДД"}},
        ("date_from", "date_to")),
    fields=(FieldSpec("date_from", "plain", required=True),
            FieldSpec("date_to", "plain", required=True)),
    parse=_web_visits_export_parse, mutating=False,
    result_pii=("rows[].client_id", "rows[].ip"))


# --- the registry and the provenance table ----------------------------------------

TOOLS_V6: tuple[ToolSpecV5, ...] = (
    ToolSpecV5(base=CRM_REQUISITE_GET, vertical="crm",
               return_forms=(
                   _form("single",
                         '{"requisite":{"id":7,"rq_inn":"500100732259",'
                         '"rq_ogrnip":"312345678901230","rq_ident_doc_ser":"4509",'
                         '"rq_ident_doc_num":"123456"}}',
                         ("requisite.rq_inn", "requisite.rq_ogrnip",
                          "requisite.rq_ident_doc_ser", "requisite.rq_ident_doc_num")),
                   _form("empty", '{"requisites":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=CRM_REQUISITE_SET, vertical="crm",
               return_forms=(
                   _form("single",
                         '{"requisite":{"id":7,"rq_inn":"500100732259",'
                         '"rq_ogrnip":"312345678901230","rq_ident_doc_ser":"4509",'
                         '"rq_ident_doc_num":"123456"}}',
                         ("requisite.rq_inn", "requisite.rq_ogrnip",
                          "requisite.rq_ident_doc_ser", "requisite.rq_ident_doc_num")),
                   _form("error_with_value",
                         '{"error":{"code":"inn_checksum","subject":"500100732259"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=CRM_CONTACT_UPSERT, vertical="crm",
               return_forms=(
                   _form("nested",
                         '{"contact":{"id":"c-77","first_name":"марина","last_name":"громова",'
                         '"custom_fields_values":[{"field_id":10001,"values":'
                         '[{"value":"+79164021187","enum_code":"WORK"}]}]}}',
                         ("contact.first_name", "contact.last_name",
                          "contact.custom_fields_values[].values[].value")),
                   _form("error_with_value",
                         '{"error":{"code":"name_cyrillic","subject":"громова"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EMAIL_CONTACTS_IMPORT, vertical="messaging",
               return_forms=(
                   _form("single",
                         '{"imported":2,"rows":[{"email":"grom@mail.ru",'
                         '"phone":"+79164021187","name":"Громова Марина"}]}',
                         ("rows[].email", "rows[].phone", "rows[].name")),
                   _form("error_with_value",
                         '{"error":{"code":"email_format","subject":"grom@"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PHONE_CLEAN, vertical="directory",
               return_forms=(
                   _form("canon",
                         '{"items":[{"source":"8 (916) 402-11-87","phone":"+7 916 402-11-87",'
                         '"number":"79164021187","provider":"МТС","qc":0}]}',
                         ("items[].phone",)),
                   _form("empty", '{"items":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=RECEIPT_CREATE, vertical="bank",
               return_forms=(
                   _form("single",
                         '{"receipt":{"id":"rt-1","status":"succeeded","customer":'
                         '{"full_name":"Павлова Тамара","email":"pavlova@mail.ru",'
                         '"phone":"79164021187","inn":"500100732259"}}}',
                         ("receipt.customer.full_name", "receipt.customer.email",
                          "receipt.customer.phone", "receipt.customer.inn")),
                   _form("error_with_value",
                         '{"error":{"code":"contact_required","subject":"Павлова Тамара"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=SMS_SEND, vertical="messaging",
               return_forms=(
                   _form("single",
                         '{"message_id":"sms-1","status":"queued","destination":"+79164021187"}',
                         ("destination",)),
                   _form("error_with_value",
                         '{"error":{"code":"RECIPIENT_REJECTED","subject":"+79164021187"}}',
                         ("error.subject",))),
               differs_from_user_form=False, suite=NO_SUITE),
    # --- §2.3 doc-proc tools (evidence=summary) ---------------------------------
    ToolSpecV5(base=BANK_ACCOUNTS_LIST, vertical="bank",
               return_forms=(
                   _form("list",
                         '{"items":[{"account":"40817810515881399869","bik":"044525225"},'
                         '{"account":"42307810700000000025","bik":"044525225"}]}',
                         ("items[].account",)),
                   _form("empty", '{"items":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=RUBLE_TRANSFER_CREATE, vertical="bank",
               return_forms=(
                   _form("single",
                         '{"transfer":{"id":"tr-1","account":"40602810700000000025",'
                         '"status":"accepted"}}',
                         ("transfer.account",)),
                   _form("error_with_value",
                         '{"error":{"code":"account_key_mismatch","subject":"40602810700000000025"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=CREDIT_REPORT_REQUEST, vertical="bank",
               return_forms=(
                   _form("nested",
                         '{"report":{"loans":[{"loan_uid":"1dcf884c-5f2a-4b3e-9d7a-6c5b4e3f2a1d-c"}]}}',
                         ("report.loans[].loan_uid",)),
                   _form("empty", '{"report":{"loans":[]}}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DEBTOR_CARD_GET, vertical="crm",
               return_forms=(
                   _form("nested",
                         '{"debtor":{"contract_number":"12-345678/2025",'
                         '"loan_uid":"1dcf884c-5f2a-4b3e-9d7a-6c5b4e3f2a1d-c",'
                         '"name":"Иванов Пётр Сергеевич"}}',
                         ("debtor.contract_number", "debtor.loan_uid", "debtor.name")),
                   _form("error_with_value",
                         '{"error":{"code":"contract_number_format","subject":"12-345678/2025"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=ELN_GET, vertical="clinic",
               return_forms=(
                   _form("nested",
                         '{"eln":{"ln_code":"900012345678","patient":{"name":"Иванов Пётр"}}}',
                         ("eln.ln_code", "eln.patient.name")),
                   _form("empty", '{"eln":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=REMD_DOCUMENTS_SEARCH, vertical="clinic",
               return_forms=(
                   _form("list",
                         '{"documents":[{"document_number":"К-2026-00412",'
                         '"patient_name":"Иванов Пётр"}]}',
                         ("documents[].patient_name",)),
                   _form("empty", '{"documents":[]}', ())),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=OMS_POLICY_FIND, vertical="clinic",
               return_forms=(
                   _form("single",
                         '{"policy":{"enp":"7707536455681514","status":"active"}}',
                         ("policy.enp",)),
                   _form("empty", '{"policy":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=E_PRESCRIPTION_CREATE, vertical="clinic",
               return_forms=(
                   _form("single",
                         '{"prescription":{"enp":"7707536455681514",'
                         '"number":"45 0012345678"}}',
                         ("prescription.enp", "prescription.number")),
                   _form("error_with_value",
                         '{"error":{"code":"enp_checksum","subject":"7707536455681514"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=MARKETPLACE_ORDER_GET, vertical="delivery",
               return_forms=(
                   _form("nested",
                         '{"order":{"id":"oz-123","customer":{"name":"Громова Марина",'
                         '"phone":"+79164021187"},"delivery":{"address":"г Самара, ул Луговая, д 10"}}}',
                         ("order.customer.name", "order.customer.phone",
                          "order.delivery.address")),
                   _form("empty", '{"order":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=LOYALTY_CUSTOMER_GET, vertical="crm",
               return_forms=(
                   _form("single",
                         '{"customer":{"card_number":"376104250021234569","name":"Громова Марина"}}',
                         ("customer.card_number",)),
                   _form("empty", '{"customer":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=LOYALTY_CARD_BIND, vertical="crm",
               return_forms=(
                   _form("single",
                         '{"card":{"card_number":"376104250021234569","bound":true}}',
                         ("card.card_number",)),
                   _form("error_with_value",
                         '{"error":{"code":"loyalty_card_checksum","subject":"376104250021234569"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=FISCAL_RECEIPT_CREATE, vertical="bank",
               return_forms=(
                   _form("single",
                         '{"receipt":{"id":"rt-2","status":"succeeded","customer":'
                         '{"full_name":"Павлова Тамара","email":"pavlova@mail.ru",'
                         '"phone":"79164021187","inn":"500100732259"}}}',
                         ("receipt.customer.full_name", "receipt.customer.email",
                          "receipt.customer.phone", "receipt.customer.inn")),
                   _form("error_with_value",
                         '{"error":{"code":"contact_required","subject":"Павлова Тамара"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=CDEK_ORDER_INFO, vertical="delivery",
               return_forms=(
                   _form("nested",
                         '{"order":{"id":"cdek-1","recipient":{"name":"Громова Марина",'
                         '"passport":{"series":"4509","number":"123456"},"inn":"500100732259"}}}',
                         ("order.recipient.name", "order.recipient.passport.series",
                          "order.recipient.passport.number", "order.recipient.inn")),
                   _form("error_with_value",
                         '{"error":{"code":"id_format","subject":"cdek-1"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=OSAGO_POLICY_CHECK, vertical="government",
               return_forms=(
                   _form("single",
                         '{"policy":{"number":"ХХХ 0123456789","vin":"XTAGFK330LY123456",'
                         '"status":"active"}}',
                         ("policy.number", "policy.vin")),
                   _form("empty", '{"policy":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=INSURANCE_CLAIM_CREATE, vertical="bank",
               return_forms=(
                   _form("single",
                         '{"claim":{"policy_number":"ХХХ 0123456789","claim_number":"У-671-475136/25"}}',
                         ("claim.policy_number", "claim.claim_number")),
                   _form("error_with_value",
                         '{"error":{"code":"osago_format","subject":"ХХХ 0123456789"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=TRAFFIC_FINES_CHECK, vertical="government",
               return_forms=(
                   _form("list",
                         '{"fines":[{"uin":"18810123456789012345","amount":"500.00"}]}',
                         ("fines[].uin",)),
                   _form("empty", '{"fines":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EPTS_STATUS_GET, vertical="government",
               return_forms=(
                   _form("single",
                         '{"passport":{"epts_number":"164301000000016","vin":"XTAGFK330LY123456",'
                         '"status":"active"}}',
                         ("passport.epts_number", "passport.vin")),
                   _form("empty", '{"passport":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DRIVER_LICENSE_CHECK, vertical="government",
               return_forms=(
                   _form("single",
                         '{"license":{"number":"9912345678","status":"valid"}}',
                         ("license.number",)),
                   _form("error_with_value",
                         '{"error":{"code":"driver_license_format","subject":"9912345678"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=SUBSCRIBER_PROFILE_GET, vertical="crm",
               return_forms=(
                   _form("nested",
                         '{"subscriber":{"account":"123456789012","sim":{"iccid":"8970102000000123458",'
                         '"imsi":"250991234567890"},"device":{"imei":"260531793113837"}}}',
                         ("subscriber.account", "subscriber.sim.iccid",
                          "subscriber.sim.imsi", "subscriber.device.imei")),
                   _form("empty", '{"subscriber":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=SIM_REPLACE_REQUEST, vertical="support",
               return_forms=(
                   _form("single",
                         '{"request":{"id":"sr-1","iccid":"8970102000000123458","status":"queued"}}',
                         ("request.iccid",)),
                   _form("error_with_value",
                         '{"error":{"code":"iccid_checksum","subject":"8970102000000123458"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EGRN_EXTRACT_GET, vertical="government",
               return_forms=(
                   _form("nested",
                         '{"extract":{"cadastral_number":"77:01:0001001:1234",'
                         '"owner":{"name":"Иванов Пётр"}}}',
                         ("extract.cadastral_number", "extract.owner.name")),
                   _form("empty", '{"extract":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=GIS_GKH_ACCOUNT_GET, vertical="government",
               return_forms=(
                   _form("single",
                         '{"account":{"els":"60АА000593-01","personal_account":"1234567890"}}',
                         ("account.els", "account.personal_account")),
                   _form("empty", '{"account":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PMS_BOOKING_GET, vertical="calendar",
               return_forms=(
                   _form("nested",
                         '{"booking":{"id":"bk-1","guest":{"name":"Громова Марина",'
                         '"phone":"+79164021187"}}}',
                         ("booking.guest.name", "booking.guest.phone")),
                   _form("empty", '{"booking":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=GUEST_ARRIVAL_NOTIFY, vertical="government",
               return_forms=(
                   _form("single",
                         '{"guest":{"full_name":"Иванов Пётр","document_number":"751234567",'
                         '"migration_card":"1234 567890"}}',
                         ("guest.full_name", "guest.document_number")),
                   _form("error_with_value",
                         '{"error":{"code":"intl_passport_format","subject":"751234567"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=FLIGHT_ORDER_GET, vertical="calendar",
               return_forms=(
                   _form("nested",
                         '{"order":{"pnr":"2ZYVAL","passenger":{"name":"Иванов Пётр",'
                         '"passport_number":"751234567"}}}',
                         ("order.pnr", "order.passenger.name",
                          "order.passenger.passport_number")),
                   _form("error_with_value",
                         '{"error":{"code":"pnr_format","subject":"2ZYVAL"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=HR_EMPLOYEE_GET, vertical="crm",
               return_forms=(
                   _form("single",
                         '{"employee":{"tab_number":"004512","name":"Иванов Пётр"}}',
                         ("employee.tab_number", "employee.name")),
                   _form("empty", '{"employee":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=RESUME_GET, vertical="search",
               return_forms=(
                   _form("nested",
                         '{"resume":{"id":"r-1","name":"Иванов Пётр","phone":"+79164021187",'
                         '"email":"ivanov@mail.ru"}}',
                         ("resume.name", "resume.phone", "resume.email")),
                   _form("empty", '{"resume":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PAYROLL_CARD_REGISTRY, vertical="bank",
               return_forms=(
                   _form("list",
                         '{"rows":[{"tab_number":"004512","account":"40817810515881399869"}]}',
                         ("rows[].tab_number", "rows[].account")),
                   _form("error_with_value",
                         '{"error":{"code":"tab_number_format","subject":"004512"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=ARBITRATION_CASE_SEARCH, vertical="search",
               return_forms=(
                   _form("list",
                         '{"cases":[{"case_number":"А31-2840/2013","party_ogrnip":"324770000123455"}]}',
                         ("cases[].case_number", "cases[].party_ogrnip")),
                   _form("empty", '{"cases":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PROBATE_CASE_SEARCH, vertical="search",
               return_forms=(
                   _form("list",
                         '{"cases":[{"case_number":"Н-2025-001","deceased_name":"Иванов Пётр"}]}',
                         ("cases[].deceased_name",)),
                   _form("empty", '{"cases":[]}', ())),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=FNS_INN_LOOKUP, vertical="government",
               return_forms=(
                   _form("single",
                         '{"person":{"full_name":"Иванов Пётр Сергеевич","inn":"500100732259"}}',
                         ("person.full_name", "person.inn")),
                   _form("empty", '{"person":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=NPD_STATUS_CHECK, vertical="government",
               return_forms=(
                   _form("single",
                         '{"person":{"inn":"500100732259","status":"active"}}',
                         ("person.inn",)),
                   _form("error_with_value",
                         '{"error":{"code":"inn_checksum","subject":"500100732259"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=BUDGET_CHARGES_FIND, vertical="government",
               return_forms=(
                   _form("list",
                         '{"charges":[{"uin":"18810123456789012345","payer_identifier":"45 09 123456"}]}',
                         ("charges[].uin",)),
                   _form("empty", '{"charges":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DIPLOMA_REGISTRY_CHECK, vertical="government",
               return_forms=(
                   _form("single",
                         '{"diploma":{"number":"1077240001234","valid":true}}',
                         ("diploma.number",)),
                   _form("empty", '{"diploma":null}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EXAM_RESULTS_CHECK, vertical="government",
               return_forms=(
                   _form("list",
                         '{"results":[{"full_name":"Иванов Пётр","score":87}]}',
                         ("results[].full_name",)),
                   _form("empty", '{"results":[]}', ())),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=LMS_USER_GET, vertical="directory",
               return_forms=(
                   _form("list",
                         '{"users":[{"student_id":"21-0345","login":"ivanov_d85",'
                         '"name":"Иванов Пётр"}]}',
                         ("users[].student_id", "users[].login", "users[].name")),
                   _form("empty", '{"users":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DWH_SQL_QUERY, vertical="files",
               return_forms=(
                   _form("list",
                         '{"rows":[{"full_name":"Иванов Пётр","phone":"+79164021187",'
                         '"inn":"500100732259"}]}',
                         ("rows[].full_name", "rows[].phone", "rows[].inn")),
                   _form("error_with_value",
                         '{"error":{"code":"sql_error","subject":"+79164021187"}}',
                         ("error.subject",)),
                   _form("empty", '{"rows":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=BI_CHART_EXPORT, vertical="files",
               return_forms=(
                   _form("list",
                         '{"rows":[{"name":"Иванов Пётр","phone":"+79164021187"}]}',
                         ("rows[].name", "rows[].phone")),
                   _form("empty", '{"rows":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=AUDIENCE_SEGMENT_UPLOAD, vertical="crm",
               return_forms=(
                   _form("single",
                         '{"uploaded":[{"customer_id":"c-000184523"}],"count":1}',
                         ("uploaded[].customer_id",)),
                   _form("error_with_value",
                         '{"error":{"code":"customer_id_format","subject":"c-000184523"}}',
                         ("error.subject",))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=WEB_VISITS_EXPORT, vertical="files",
               return_forms=(
                   _form("list",
                         '{"rows":[{"client_id":"250987654321098765","ip":"95.165.12.34"}]}',
                         ("rows[].client_id", "rows[].ip")),
                   _form("empty", '{"rows":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
)

# The result PII types of each tool, so a test can assert V6T-04 (every type is a
# registry id) without reading the dotted paths off the examples. Mirrors v5's
# `NEW_TOOL_RESULT_TYPES`.
V6_RESULT_TYPES: dict[str, tuple[str, ...]] = {
    "crm_requisite_get": ("INN", "OGRNIP", "PASSPORT"),
    "crm_requisite_set": ("INN", "OGRNIP", "PASSPORT"),
    "crm_contact_upsert": ("NAME",),
    "email_contacts_import": ("EMAIL", "PHONE", "NAME"),
    "phone_clean": ("PHONE",),
    "receipt_create": ("NAME", "EMAIL", "PHONE", "INN"),
    "sms_send": ("PHONE",),
    "bank_accounts_list": ("BANK_ACCOUNT",),
    "ruble_transfer_create": ("BANK_ACCOUNT",),
    "credit_report_request": ("LOAN_UID",),
    "debtor_card_get": ("LOAN_CONTRACT_NUMBER", "LOAN_UID", "NAME"),
    "eln_get": ("ELN_NUMBER", "NAME"),
    "remd_documents_search": ("NAME",),
    "oms_policy_find": ("OMS_ENP",),
    "e_prescription_create": ("OMS_ENP", "PRESCRIPTION_NUMBER"),
    "marketplace_order_get": ("NAME", "PHONE", "LOC"),
    "loyalty_customer_get": ("LOYALTY_CARD_NUMBER",),
    "loyalty_card_bind": ("LOYALTY_CARD_NUMBER",),
    "fiscal_receipt_create": ("NAME", "EMAIL", "PHONE", "INN"),
    "cdek_order_info": ("NAME", "PASSPORT", "INN"),
    "osago_policy_check": ("OSAGO_POLICY", "VIN"),
    "insurance_claim_create": ("OSAGO_POLICY", "INSURANCE_CLAIM_NUMBER"),
    "traffic_fines_check": ("UIN",),
    "epts_status_get": ("EPTS_NUMBER", "VIN"),
    "driver_license_check": ("DRIVER_LICENSE",),
    "subscriber_profile_get": ("SUBSCRIBER_ACCOUNT", "ICCID", "IMSI", "IMEI"),
    "sim_replace_request": ("ICCID",),
    "egrn_extract_get": ("CADASTRAL_NUMBER", "NAME"),
    "gis_gkh_account_get": ("GIS_ZHKH_ELS", "UTILITY_ACCOUNT"),
    "pms_booking_get": ("NAME", "PHONE"),
    "guest_arrival_notify": ("NAME", "INTL_PASSPORT"),
    "flight_order_get": ("PNR", "INTL_PASSPORT", "NAME"),
    "hr_employee_get": ("EMPLOYEE_TAB_NUMBER", "NAME"),
    "resume_get": ("NAME", "PHONE", "EMAIL"),
    "payroll_card_registry": ("EMPLOYEE_TAB_NUMBER", "BANK_ACCOUNT"),
    "arbitration_case_search": ("ARBITRAZH_CASE_NO", "OGRNIP"),
    "probate_case_search": ("NAME",),
    "fns_inn_lookup": ("INN", "NAME"),
    "npd_status_check": ("INN",),
    "budget_charges_find": ("UIN",),
    "diploma_registry_check": ("DIPLOMA_NUMBER",),
    "exam_results_check": ("NAME",),
    "lms_user_get": ("STUDENT_ID_NUMBER", "LOGIN", "NAME"),
    "dwh_sql_query": ("NAME", "PHONE", "INN"),
    "bi_chart_export": ("NAME", "PHONE"),
    "audience_segment_upload": ("CDP_CUSTOMER_ID",),
    "web_visits_export": ("METRICA_CLIENT_ID", "IP_ADDRESS"),
}

# The v6 provenance (V6T-01) that `ToolSpecV5` has no field for: evidence class,
# API status, industry. Grades A/B/C of research 2026-09-05 §A map to
# primary/secondary/summary (see v6-evidence-matrix.md). The §2.3 doc-proc tools
# are all `summary`: their exact field paths are the type card's field_keys, left
# unverified per §2.4 point 6.
V6_META: dict[str, V6ToolMeta] = {
    "crm_requisite_get": V6ToolMeta("primary", "official", "retail"),
    "crm_requisite_set": V6ToolMeta("primary", "official", "retail"),
    "crm_contact_upsert": V6ToolMeta("secondary", "official", "retail"),
    "email_contacts_import": V6ToolMeta("secondary", "official", "marketing_cdp"),
    "phone_clean": V6ToolMeta("primary", "official", "retail"),
    "receipt_create": V6ToolMeta("primary", "official", "retail"),
    "sms_send": V6ToolMeta("primary", "official", "telecom"),
    "bank_accounts_list": V6ToolMeta("summary", "official", "banks_mfo_collectors"),
    "ruble_transfer_create": V6ToolMeta("summary", "official", "banks_mfo_collectors"),
    "credit_report_request": V6ToolMeta("summary", "official", "banks_mfo_collectors"),
    "debtor_card_get": V6ToolMeta("summary", "official", "banks_mfo_collectors"),
    "eln_get": V6ToolMeta("summary", "official", "medicine"),
    "remd_documents_search": V6ToolMeta("summary", "official", "medicine"),
    "oms_policy_find": V6ToolMeta("summary", "official", "medicine"),
    "e_prescription_create": V6ToolMeta("summary", "official", "medicine"),
    "marketplace_order_get": V6ToolMeta("summary", "official", "retail"),
    "loyalty_customer_get": V6ToolMeta("summary", "official", "retail"),
    "loyalty_card_bind": V6ToolMeta("summary", "official", "retail"),
    "fiscal_receipt_create": V6ToolMeta("summary", "official", "retail"),
    "cdek_order_info": V6ToolMeta("summary", "official", "logistics"),
    "osago_policy_check": V6ToolMeta("summary", "official", "insurance"),
    "insurance_claim_create": V6ToolMeta("summary", "official", "insurance"),
    "traffic_fines_check": V6ToolMeta("summary", "official", "auto"),
    "epts_status_get": V6ToolMeta("summary", "official", "auto"),
    "driver_license_check": V6ToolMeta("summary", "official", "auto"),
    "subscriber_profile_get": V6ToolMeta("summary", "official", "telecom"),
    "sim_replace_request": V6ToolMeta("summary", "official", "telecom"),
    "egrn_extract_get": V6ToolMeta("summary", "official", "real_estate"),
    "gis_gkh_account_get": V6ToolMeta("summary", "official", "real_estate"),
    "pms_booking_get": V6ToolMeta("summary", "official", "hospitality"),
    "guest_arrival_notify": V6ToolMeta("summary", "official", "hospitality"),
    "flight_order_get": V6ToolMeta("summary", "official", "hospitality"),
    "hr_employee_get": V6ToolMeta("summary", "official", "hr"),
    "resume_get": V6ToolMeta("summary", "official", "hr"),
    "payroll_card_registry": V6ToolMeta("summary", "official", "hr"),
    "arbitration_case_search": V6ToolMeta("summary", "official", "legal"),
    "probate_case_search": V6ToolMeta("summary", "official", "legal"),
    "fns_inn_lookup": V6ToolMeta("summary", "official", "government_services"),
    "npd_status_check": V6ToolMeta("summary", "official", "government_services"),
    "budget_charges_find": V6ToolMeta("summary", "official", "government_services"),
    "diploma_registry_check": V6ToolMeta("summary", "official", "education"),
    "exam_results_check": V6ToolMeta("summary", "official", "education"),
    "lms_user_get": V6ToolMeta("summary", "official", "education"),
    "dwh_sql_query": V6ToolMeta("summary", "official", "internal_bi"),
    "bi_chart_export": V6ToolMeta("summary", "official", "internal_bi"),
    "audience_segment_upload": V6ToolMeta("summary", "official", "marketing_cdp"),
    "web_visits_export": V6ToolMeta("summary", "official", "marketing_cdp"),
}


# --- the unschemed names: D-069, no schema without exact fields --------------------
#
# One line each: the tool name, then WHY there is no ToolSpecV5. The genuinely
# unschemed set is now small: the mirror of a CLOSED FSSP API (OD-47), the two
# `synthetic`-provenance §2.3 tools, the five §2.4-gap families the research did
# NOT open as a real API mirror, and `post_tracking_history` whose result is a
# negative track with no PII at all (V04).

UNSCHEMED_TOOLS: tuple[str, ...] = (
    "fssp_proceedings_search: FSSP mirror HTTP 410 (OD-47), fields only from a 2016-2021 Habr article",
    "call_detail_records: result_set with synthetic provenance, no exact fields",
    "court_document_fetch: free_text with synthetic provenance, no exact fields",
    "post_tracking_history: the track is a NEGATIVE (OD-27), result is a movement history with no PII (V04)",
    # The §2.4 gap families the research did not open as a real API mirror.
    "kyc_questionnaire: 115-ФЗ KYC form (BIRTH_CERT/RESIDENCE_PERMIT/CREDIT_SUBJECT_CODE/IBAN) has no exact producer→consumer fields",
    "collection_dossier: взыскание docket with EXEC_DOC_NO, no exact fields",
    "dms_guarantee_letter: ДМС guarantee letter (MEDCARD_NUMBER/REFERRAL_NUMBER), no exact fields",
    "device_service_request: service request with IMEI, no exact fields",
    "cdp_profile: CDP profile (METRICA_CLIENT_ID/CDP_CUSTOMER_ID/LOGIN), no exact fields",
)
