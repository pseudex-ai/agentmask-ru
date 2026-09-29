"""The v6 tool registry, upgraded from the W1 discovery data (apis.json).

EXACT PATHS. Every ToolSpecV5 below is built from `/apis.json` (the W1 real-API
mirror): `result_pii` is the union of `returns[].pii_paths` VERBATIM, every
`ReturnForm` is one `returns[]` entry (its `form`, its `example`, its
`pii_paths`), and every `FieldSpec` is one `request[]` entry (path -> pii_type /
required / role). A request `pii_type` is a `pii_types.TYPE_REGISTRY` id, or ""
(plain) where the discovery labels a type the registry does not hold (TRACK_NUMBER,
BOOKING_ID, MIGRATION_CARD, VISA_NUMBER, EXAM_REG_CODE, DEATH_DATE, PROBATE_CASE_
NUMBER). `source` is the first `evidence[]` url; `evidence` is the strongest grade
present (summary stays summary — never upgraded to a fake primary); `api_status` is
official for every documented-procedure tool; `vertical` = `v5_vertical`; `industry`
from the field.

KNOWN 1:1 APPROXIMATIONS (see report):
  * `result_set` (not a v5 RETURN_FORM) is renamed `list`, except the two pure-OUT
    tools and the columnar/TSV exporters.
  * `fiscal_receipt_create` and `email_contacts_import` are verified pure-OUT tools
    (their `returns[].pii_paths` union is EMPTY); V04 forbids an empty result_pii, so
    they carry the v5 R-41 write-echo (the stored record) instead of nothing.
  * `payroll_card_registry` columnar `rows[][N]` -> named `rows[].<col>`;
    `bi_chart_export` `$csv` and `web_visits_export` `$tsv[..]` -> a `free_text`
    `text` leaf (the columnar observer rule is unsolved in apis.json itself).

The six research-grounded specs (Bitrix24 crm_requisite_get/_set, amoCRM
crm_contact_upsert, DaData phone_clean, ЮKassa/T-Bank receipt_create, Exolve
sms_send) are kept unchanged — no apis.json tool shares their name. Unisender
`email_contacts_import` IS superseded by the apis.json tool of the same name.

NOTHING HERE IMPORTS `pseudex`.
"""
import datetime as dt
import re
from dataclasses import dataclass

from bench.agentpii4.tools import (FieldSpec, Refusal, ToolSpec, _first, _obj,
                                   _required, _schema, parse_digits, parse_e164,
                                   parse_inn, parse_int, parse_iso_date,
                                   parse_name_word, parse_snils, parse_text,
                                   snils_ok)
from bench.agentpii5 import checksum_v6
from bench.agentpii5.contracts import (NEW_TOOL_NAMES, NO_SUITE, RETURN_FORMS,
                                       V4_TOOL_NAMES, VERTICALS, ReturnForm,
                                       ToolSpecV5)

Parsed = dict[str, object]

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
NUMERIC_PHONE_RE = re.compile(r"7\d{10}")
IMPORT_MAX_CONTACTS: int = 500
SMS_TEXT_LIMIT: int = 1000
ID_RE = re.compile(r"[A-Za-z0-9_./-]{1,60}")
PLATE_RE = re.compile(r"[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}")


@dataclass(frozen=True)
class V6ToolMeta:
    """The v6 provenance a `ToolSpecV5` has no field for (V6T-01): evidence class,
    API status, industry."""

    evidence: str          # primary | secondary | summary
    api_status: str        # official | closed | synthetic
    industry: str          # contracts_v6.INDUSTRIES


def _form(form: str, example: str, paths: tuple[str, ...]) -> ReturnForm:
    if form not in RETURN_FORMS:
        raise ValueError(f"{form!r} is not a return form of contracts.RETURN_FORMS")
    return ReturnForm(form=form, example=example, pii_paths=paths)


def _parse_opaque_id(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not ID_RE.fullmatch(raw.strip()):
        return Refusal(tool, path, "id_format", str(raw))
    return raw.strip()


def _parse_snils_bare(raw: object, tool: str, path: str) -> str | Refusal:
    """СНИЛС as 11 bare digits (the СФР/РЭМД/ТФОМС form), mod-101 gate."""
    if not isinstance(raw, str) or not re.fullmatch(r"\d{11}", raw.strip()):
        return Refusal(tool, path, "snils_format", str(raw))
    digits = raw.strip()
    if not snils_ok(digits):
        return Refusal(tool, path, "snils_checksum", str(raw))
    return digits


def _parse_phone_digits(raw: object, tool: str, path: str) -> str | Refusal:
    """The numeric MSISDN «79164021187» the telecom/CDP APIs store (no plus)."""
    if not isinstance(raw, str) or not NUMERIC_PHONE_RE.fullmatch(raw.strip()):
        return Refusal(tool, path, "phone_format", str(raw))
    return raw.strip()


def _parse_plate(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str):
        return Refusal(tool, path, "plate_format", str(raw))
    value = re.sub(r"\s", "", raw.strip().upper())
    if not PLATE_RE.fullmatch(value):
        return Refusal(tool, path, "plate_format", str(raw))
    return value


def _parse_intl_passport(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str):
        return Refusal(tool, path, "document_format", str(raw))
    value = re.sub(r"\s", "", raw.strip())
    if not re.fullmatch(r"[0-9A-Za-z]{9}", value):
        return Refusal(tool, path, "document_format", str(raw))
    return value


def _parse_dmy(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw.strip()):
        return Refusal(tool, path, "date_format", str(raw))
    return raw.strip()


def _parse_date_iso(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw.strip()):
        return Refusal(tool, path, "date_format", str(raw))
    try:
        dt.date.fromisoformat(raw.strip())
    except ValueError:
        return Refusal(tool, path, "date_format", str(raw))
    return raw.strip()


def _parse_ogrnip(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not raw.strip().isdigit() or len(raw.strip()) != 15:
        return Refusal(tool, path, "ogrnip_format", str(raw))
    if not checksum_v6.validate_ogrnip(raw.strip()):
        return Refusal(tool, path, "ogrnip_checksum", str(raw))
    return raw.strip()


def _parse_numeric_phone(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not NUMERIC_PHONE_RE.fullmatch(raw.strip()):
        return Refusal(tool, path, "phone_numeric_format", str(raw))
    return raw.strip()


def _checksummed(raw, tool, path, type_id, width, fmt_rule, ck_rule):
    digits = parse_digits(raw, tool, path, width, fmt_rule)
    if isinstance(digits, Refusal):
        return digits
    if not checksum_v6.validate(type_id, digits):
        return Refusal(tool, path, ck_rule, str(raw))
    return digits


def _parse_oms_enp(raw, tool, path):
    return _checksummed(raw, tool, path, "OMS_ENP", 16, "enp_format", "enp_checksum")


def _parse_iccid(raw, tool, path):
    return _checksummed(raw, tool, path, "ICCID", 19, "iccid_format", "iccid_checksum")


def _parse_imei(raw, tool, path):
    return _checksummed(raw, tool, path, "IMEI", 15, "imei_format", "imei_checksum")


def _parse_vin(raw, tool, path):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9A-HJ-NPR-Z]{17}", raw.strip().upper()):
        return Refusal(tool, path, "vin_format", str(raw))
    up = raw.strip().upper()
    if not checksum_v6.validate_vin(up):
        return Refusal(tool, path, "vin_checksum", str(raw))
    return up


def _parse_epts(raw, tool, path):
    digits = parse_digits(raw, tool, path, 15, "epts_format")
    if isinstance(digits, Refusal):
        return digits
    if not checksum_v6.validate_epts_number(digits):
        return Refusal(tool, path, "epts_checksum", str(raw))
    return digits


def _parse_uin(raw, tool, path):
    if not isinstance(raw, str) or not re.fullmatch(r"\d{20}|\d{25}", raw.strip()):
        return Refusal(tool, path, "uin_format", str(raw))
    if not checksum_v6.validate_uin(raw.strip()):
        return Refusal(tool, path, "uin_checksum", str(raw))
    return raw.strip()


def _parse_loan_uid(raw, tool, path):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9a-fA-F\-]{33,}", raw.strip()):
        return Refusal(tool, path, "loan_uid_format", str(raw))
    if not checksum_v6.validate_loan_uid(raw.strip()):
        return Refusal(tool, path, "loan_uid_checksum", str(raw))
    return raw.strip()


def _parse_loyalty(raw, tool, path):
    # The card is issuer-specific (Mindbox's own example is 12 digits, not EAN-13),
    # so the card grammar is «8-20 digits», no universal checksum.
    if not isinstance(raw, str) or not re.fullmatch(r"\d{8,20}", raw.strip()):
        return Refusal(tool, path, "card_format", str(raw))
    return raw.strip()


def _digits_spaceless(raw, tool, path, width, rule):
    if not isinstance(raw, str):
        return Refusal(tool, path, rule, str(raw))
    value = re.sub(r"\s", "", raw)
    if not re.fullmatch(rf"\d{{{width}}}", value):
        return Refusal(tool, path, rule, str(raw))
    return value


def _shaped(raw, tool, path, pattern, rule):
    if not isinstance(raw, str) or not re.fullmatch(pattern, raw.strip()):
        return Refusal(tool, path, rule, str(raw))
    return raw.strip()


def _free_id(raw, tool, path, limit, rule):
    if not isinstance(raw, str) or not raw.strip():
        return Refusal(tool, path, rule, str(raw))
    if len(raw.strip()) > limit:
        return Refusal(tool, path, rule, str(raw))
    return raw.strip()


def _parse_osago(raw, tool, path):
    if not isinstance(raw, str):
        return Refusal(tool, path, "policy_format", str(raw))
    value = re.sub(r"[№\s]", "", raw.strip().upper())
    if not re.fullmatch(r"[А-ЯЁA-Z]{3}\d{10}", value):
        return Refusal(tool, path, "policy_format", str(raw))
    return value


def _parse_cadastral(raw, tool, path):
    return _shaped(raw, tool, path, r"\d{2}:\d{2}:\d{6,7}:\d+", "cadastral_format")


def _parse_els(raw, tool, path):
    return _shaped(raw, tool, path, r"\d{2}[А-ЯЁ]{2}\d{6}(?:-\d{2})?(?:-\d{4})?",
                   "els_format")


def _parse_arbitrazh(raw, tool, path):
    if not isinstance(raw, str):
        return Refusal(tool, path, "case_number_format", str(raw))
    value = raw.strip().upper()
    if not re.fullmatch(r"[АA]\d{2}-\d{1,7}/\d{4}", value):
        return Refusal(tool, path, "case_number_format", str(raw))
    return value


def _parse_court_case_sou(raw, tool, path):
    if not isinstance(raw, str):
        return Refusal(tool, path, "case_number_format", str(raw))
    value = raw.strip()
    if not re.fullmatch(r"(?:\d{1,2}[а-я]?|М)-\d{1,6}/\d{4}", value):
        return Refusal(tool, path, "case_number_format", str(raw))
    return value


def _parse_iban(raw, tool, path):
    if not isinstance(raw, str):
        return Refusal(tool, path, "iban_format", str(raw))
    value = re.sub(r"\s", "", raw.strip().upper())
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", value):
        return Refusal(tool, path, "iban_format", str(raw))
    if not checksum_v6.validate_iban(value):
        return Refusal(tool, path, "iban_checksum", str(raw))
    return value


def _parse_esia_oid(raw, tool, path):
    if not isinstance(raw, str) or not raw.strip().isdigit():
        return Refusal(tool, path, "oid_format", str(raw))
    return raw.strip()


# --- research-grounded (kept: no apis.json tool shares their name) ---------------

def _crm_requisite_get_parse(args):
    tool = "crm_requisite_get"
    present = [key for key in ("inn", "ogrnip", "iban") if args.get(key) not in (None, "")]
    if len(present) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(present))
    if present[0] == "inn":
        inn = parse_inn(args["inn"], tool, "inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        return {"inn": inn}
    if present[0] == "iban":
        iban = _parse_iban(args["iban"], tool, "iban")
        if isinstance(iban, Refusal):
            return iban
        return {"iban": iban}
    ogrnip = _parse_ogrnip(args["ogrnip"], tool, "ogrnip")
    if isinstance(ogrnip, Refusal):
        return ogrnip
    return {"ogrnip": ogrnip}


CRM_REQUISITE_GET = ToolSpec(
    name="crm_requisite_get",
    source="Bitrix24 REST crm.requisite.get/list — RQ_OGRNIP, RQ_INN, RQ_IBAN, "
           "RQ_IDENT_DOC_SER/RQ_IDENT_DOC_NUM/RQ_IDENT_DOC_DATE/RQ_IDENT_DOC_ISSUED_BY "
           "(https://apidocs.bitrix24.ru/api-reference/crm/requisites/universal/crm-requisite-fields.html)",
    schema=_schema(
        "crm_requisite_get",
        "Получить реквизиты продавца или физлица по ИНН, ОГРНИП или IBAN. Возвращает ИНН, "
        "ОГРНИП, IBAN и паспорт по серии и номеру.",
        {"inn": {"type": "string", "description": "ИНН, 10 или 12 цифр"},
         "ogrnip": {"type": "string", "description": "ОГРНИП, 15 цифр"},
         "iban": {"type": "string", "description": "IBAN, RU + 2 ключа + БИК 9 + счёт 20"}},
        ()),
    fields=(FieldSpec("inn", "identity", "INN", "digits"),
            FieldSpec("ogrnip", "identity", "OGRNIP", "digits"),
            FieldSpec("iban", "identity", "IBAN", "")),
    parse=_crm_requisite_get_parse, mutating=False,
    result_pii=("requisite.rq_inn", "requisite.rq_ogrnip", "requisite.rq_iban",
                "requisite.rq_ident_doc_ser", "requisite.rq_ident_doc_num"))


def _crm_requisite_set_parse(args):
    tool = "crm_requisite_set"
    miss = _required(args, tool, "", ("inn",))
    if miss:
        return miss
    inn = parse_inn(args["inn"], tool, "inn", (10, 12))
    if isinstance(inn, Refusal):
        return inn
    out = {"inn": inn}
    if args.get("iban") not in (None, ""):
        iban = _parse_iban(args["iban"], tool, "iban")
        if isinstance(iban, Refusal):
            return iban
        out["iban"] = iban
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
        ser = parse_digits(doc["ser"], tool, "ident_doc.ser", 4, "passport_series_format")
        num = parse_digits(doc["num"], tool, "ident_doc.num", 6, "passport_number_format")
        bad = _first(ser, num)
        if bad:
            return bad
        block = {"ser": ser, "num": num}
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
    source="Bitrix24 REST crm.requisite.add/update — RQ_INN, RQ_OGRNIP, RQ_IBAN, "
           "RQ_IDENT_DOC_SER/RQ_IDENT_DOC_NUM/RQ_IDENT_DOC_DATE/RQ_IDENT_DOC_ISSUED_BY; "
           "the saved requisite is echoed back (v5 R-41 write-echo) "
           "(https://apidocs.bitrix24.ru/api-reference/crm/requisites/universal/crm-requisite-fields.html)",
    schema=_schema(
        "crm_requisite_set",
        "Завести или обновить реквизиты продавца. Паспорт передаётся по серии и номеру.",
        {"inn": {"type": "string", "description": "ИНН, 10 или 12 цифр"},
         "ogrnip": {"type": "string", "description": "ОГРНИП, 15 цифр"},
         "iban": {"type": "string", "description": "IBAN, RU + 2 ключа + БИК 9 + счёт 20"},
         "ident_doc": {"type": "object",
                       "properties": {"ser": {"type": "string", "description": "Серия паспорта, 4 цифры"},
                                      "num": {"type": "string", "description": "Номер паспорта, 6 цифр"},
                                      "date": {"type": "string", "description": "Дата выдачи, ГГГГ-ММ-ДД"},
                                      "issued_by": {"type": "string", "description": "Кем выдан"}},
                       "required": ["ser", "num"]}},
        ("inn",)),
    fields=(FieldSpec("inn", "identity", "INN", "digits", required=True),
            FieldSpec("ogrnip", "identity", "OGRNIP", "digits"),
            FieldSpec("iban", "identity", "IBAN", ""),
            FieldSpec("ident_doc.ser", "identity", "PASSPORT", "series"),
            FieldSpec("ident_doc.num", "identity", "PASSPORT", "number"),
            FieldSpec("ident_doc.date", "plain"),
            FieldSpec("ident_doc.issued_by", "plain")),
    parse=_crm_requisite_set_parse, mutating=True,
    result_pii=("requisite.rq_inn", "requisite.rq_ogrnip", "requisite.rq_iban",
                "requisite.rq_ident_doc_ser", "requisite.rq_ident_doc_num",
                "error.subject"))


def _crm_contact_upsert_parse(args):
    tool = "crm_contact_upsert"
    miss = _required(args, tool, "", ("first_name", "last_name"))
    if miss:
        return miss
    first = parse_name_word(args["first_name"], tool, "first_name")
    last = parse_name_word(args["last_name"], tool, "last_name")
    bad = _first(first, last)
    if bad:
        return bad
    out = {"first_name": first, "last_name": last}
    if args.get("custom_fields_values"):
        fields_raw = args["custom_fields_values"]
        if not isinstance(fields_raw, list) or not fields_raw:
            return Refusal(tool, "custom_fields_values", "array_required", str(fields_raw))
        parsed_fields = []
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
            parsed_values = []
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
            FieldSpec("custom_fields_values[].values[].value", "free"),
            FieldSpec("custom_fields_values[].values[].enum_code", "plain")),
    parse=_crm_contact_upsert_parse, mutating=True,
    result_pii=("contact.first_name", "contact.last_name",
                "contact.custom_fields_values[].values[].value", "error.subject"))


def _phone_clean_parse(args):
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


def _receipt_create_parse(args):
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
        return Refusal(tool, "customer", "contact_required", "")
    out_customer = {"full_name": full_name.strip()}
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


def _sms_send_parse(args):
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
    out = {"destination": destination, "text": text.strip()}
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



# --- bank_accounts_list (bank, banks_mfo_collectors, evidence=primary, mutating=False) ---
def _bank_accounts_list_parse(args):
    tool = "bank_accounts_list"
    miss = _required(args, tool, "", ("client_id",))
    if miss:
        return miss
    client_id = _parse_opaque_id(args["client_id"], tool, "client_id")
    if isinstance(client_id, Refusal):
        return client_id
    out = {"client_id": client_id}
    if args.get("status") not in (None, ""):
        out["status"] = str(args["status"]).strip()
    return out

BANK_ACCOUNTS_LIST = ToolSpec(
    name='bank_accounts_list',
    source='https://cbr.ru/Content/Document/File/185563/20251219_od_2890.pdf',
    schema=_schema('bank_accounts_list', 'Открытые API Банка России / Ассоциации ФинТех — «Получение информации о банковских счетах Пользователя» (СТО, v2.0.0, введение 2026-10-01); АБС банка (ЦФТ, Diasoft) за ним',
        {'client_id': {'type': 'string', 'description': 'строка'}, 'status': {'type': 'string', 'description': 'значение из закрытого списка'}},
        ('client_id',)),
    fields=(
            FieldSpec('client_id', 'plain', required=True),
            FieldSpec('status', 'enum', required=False),
    ),
    parse=_bank_accounts_list_parse, mutating=False,
    result_pii=('Data.Account[].AccountDetails[].identification', 'Data.Account[].AccountDetails[].name'))


# --- ruble_transfer_create (bank, banks_mfo_collectors, evidence=summary, mutating=True) ---
def _ruble_transfer_create_parse(args):
    tool = "ruble_transfer_create"
    miss = _required(args, tool, "", ("payment_id", "recipient", "amount", "purpose"))
    if miss:
        return miss
    payment_id = _parse_opaque_id(args["payment_id"], tool, "payment_id")
    recipient = _obj(args["recipient"], tool, "recipient")
    if isinstance(recipient, Refusal):
        return recipient
    miss = _required(recipient, tool, "recipient", ("name", "account", "bik"))
    if miss:
        return miss
    name = parse_text(recipient["name"], tool, "recipient.name", 200)
    account = parse_digits(recipient["account"], tool, "recipient.account", 20, "account_format")
    bik = parse_digits(recipient["bik"], tool, "recipient.bik", 9, "bik_format")
    bad = _first(payment_id, name, account, bik)
    if bad:
        return bad
    if not checksum_v6.validate_account(str(account), str(bik)):
        return Refusal(tool, "recipient.account", "account_key_mismatch", str(account))
    amount = str(args["amount"]).strip()
    purpose = parse_text(args["purpose"], tool, "purpose", 210)
    if isinstance(purpose, Refusal):
        return purpose
    if not purpose.strip():
        return Refusal(tool, "purpose", "purpose_too_long", str(purpose))
    out = {"payment_id": payment_id, "recipient": {"name": str(name).strip(),
            "account": account, "bik": bik}, "amount": amount, "purpose": purpose.strip()}
    if recipient.get("inn") not in (None, ""):
        inn = parse_inn(recipient["inn"], tool, "recipient.inn", (12,))
        if isinstance(inn, Refusal):
            return inn
        out["recipient"]["inn"] = inn
    if recipient.get("corr_account") not in (None, ""):
        corr = parse_digits(recipient["corr_account"], tool, "recipient.corr_account",
                            20, "account_format")
        if isinstance(corr, Refusal):
            return corr
        out["recipient"]["corr_account"] = corr
    return out

RUBLE_TRANSFER_CREATE = ToolSpec(
    name='ruble_transfer_create',
    source='https://developer.tbank.ru/docs/api/payments-core-pay',
    schema=_schema('ruble_transfer_create', 'Т-Бизнес T-API «Выполнить платёж» (перевод со счёта компании на счёт физлица/юрлица в банке РФ) / платёжное поручение по Положению Банка России 762-П',
        {'payment_id': {'type': 'string', 'description': 'строка'}, 'recipient.name': {'type': 'string', 'description': 'NAME'}, 'recipient.inn': {'type': 'string', 'description': 'INN — 12 digits for a person'}, 'recipient.account': {'type': 'string', 'description': 'ACCOUNT — 20 digits'}, 'recipient.bik': {'type': 'string', 'description': '9 digits'}, 'recipient.corr_account': {'type': 'string', 'description': '20 digits'}, 'amount': {'type': 'string', 'description': 'строка'}, 'purpose': {'type': 'string', 'description': 'свободный текст'}},
        ('payment_id', 'recipient.name', 'recipient.account', 'recipient.bik', 'amount', 'purpose')),
    fields=(
            FieldSpec('payment_id', 'plain', required=True),
            FieldSpec('recipient.name', "identity", 'NAME', '', required=True),
            FieldSpec('recipient.inn', "identity", 'INN', '', required=False),
            FieldSpec('recipient.account', "identity", 'BANK_ACCOUNT', '', required=True),
            FieldSpec('recipient.bik', 'plain', required=True),
            FieldSpec('recipient.corr_account', 'plain', required=False),
            FieldSpec('amount', 'plain', required=True),
            FieldSpec('purpose', 'free', required=True),
    ),
    parse=_ruble_transfer_create_parse, mutating=True,
    result_pii=('recipient.name', 'recipient.account', 'errorMessage'))


# --- credit_report_request (bank, banks_mfo_collectors, evidence=secondary, mutating=False) ---
def _credit_report_request_parse(args):
    tool = "credit_report_request"
    miss = _required(args, tool, "", ("subject", "consent_id"))
    if miss:
        return miss
    subject = _obj(args["subject"], tool, "subject")
    if isinstance(subject, Refusal):
        return subject
    miss = _required(subject, tool, "subject", ("last_name", "first_name", "birth_date", "passport"))
    if miss:
        return miss
    last = parse_name_word(subject["last_name"], tool, "subject.last_name")
    first = parse_name_word(subject["first_name"], tool, "subject.first_name")
    birth = _parse_date_iso(subject["birth_date"], tool, "subject.birth_date")
    passport = _digits_spaceless(subject["passport"], tool, "subject.passport", 10, "passport_format")
    bad = _first(last, first, birth, passport)
    if bad:
        return bad
    consent = _parse_opaque_id(args["consent_id"], tool, "consent_id")
    if isinstance(consent, Refusal):
        return consent
    out = {"subject": {"last_name": last, "first_name": first, "birth_date": birth,
                       "passport": passport}, "consent_id": consent}
    if subject.get("middle_name") not in (None, ""):
        mid = parse_name_word(subject["middle_name"], tool, "subject.middle_name")
        if isinstance(mid, Refusal):
            return mid
        out["subject"]["middle_name"] = mid
    if subject.get("snils") not in (None, ""):
        snils = parse_snils(subject["snils"], tool, "subject.snils")
        if isinstance(snils, Refusal):
            return snils
        out["subject"]["snils"] = snils
    if subject.get("inn") not in (None, ""):
        inn = parse_inn(subject["inn"], tool, "subject.inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        out["subject"]["inn"] = inn
    return out

CREDIT_REPORT_REQUEST = ToolSpec(
    name='credit_report_request',
    source='https://github.com/diev/Api5704',
    schema=_schema('credit_report_request', 'НБКИ / ОКБ / Скоринг Бюро — кредитный отчёт субъекта и сведения о среднемесячных платежах (ССП) и самозапрете по Указанию Банка России 6775-У (ранее 5704-У)',
        {'subject.last_name': {'type': 'string', 'description': 'NAME (surname)'}, 'subject.first_name': {'type': 'string', 'description': 'NAME (given)'}, 'subject.middle_name': {'type': 'string', 'description': 'NAME (patronymic)'}, 'subject.birth_date': {'type': 'string', 'description': 'DOB — ISO'}, 'subject.passport': {'type': 'string', 'description': 'PASSPORT'}, 'subject.snils': {'type': 'string', 'description': 'SNILS — XXX-XXX-XXX YY'}, 'subject.inn': {'type': 'string', 'description': 'INN'}, 'consent_id': {'type': 'string', 'description': 'строка'}},
        ('subject.last_name', 'subject.first_name', 'subject.birth_date', 'subject.passport', 'consent_id')),
    fields=(
            FieldSpec('subject.last_name', "identity", 'NAME', 'surname', required=True),
            FieldSpec('subject.first_name', "identity", 'NAME', 'given', required=True),
            FieldSpec('subject.middle_name', "identity", 'NAME', 'patronymic', required=False),
            FieldSpec('subject.birth_date', "identity", 'DOB', '', required=True),
            FieldSpec('subject.passport', "identity", 'PASSPORT', '', required=True),
            FieldSpec('subject.snils', "identity", 'SNILS', '', required=False),
            FieldSpec('subject.inn', "identity", 'INN', '', required=False),
            FieldSpec('consent_id', 'plain', required=True),
    ),
    parse=_credit_report_request_parse, mutating=False,
    result_pii=('subject.name', 'subject.birth_date', 'subject.passport', 'contracts[].uid'))


# --- debtor_card_get (crm, banks_mfo_collectors, evidence=summary, mutating=False) ---
def _debtor_card_get_parse(args):
    tool = "debtor_card_get"
    miss = _required(args, tool, "", ("contract_number",))
    if miss:
        return miss
    contract = _free_id(args["contract_number"], tool, "contract_number", 40, "contract_format")
    if isinstance(contract, Refusal):
        return contract
    return {"contract_number": contract}

DEBTOR_CARD_GET = ToolSpec(
    name='debtor_card_get',
    source='https://base.garant.ru/71433918/1b93c134b90c6071b4dc3f495464b753/',
    schema=_schema('debtor_card_get', 'CRM коллекторского агентства / МФО (портфель уступленных долгов); поля — по 230-ФЗ (взаимодействие с должником и третьими лицами)',
        {'contract_number': {'type': 'string', 'description': 'CONTRACT_NUMBER'}},
        ('contract_number',)),
    fields=(
            FieldSpec('contract_number', "identity", 'LOAN_CONTRACT_NUMBER', '', required=True),
    ),
    parse=_debtor_card_get_parse, mutating=False,
    result_pii=('debtor.fio', 'debtor.birth_date', 'debtor.phones[]', 'debtor.reg_address', 'loan.contract', 'loan.uid', 'third_parties[].fio', 'third_parties[].phone', 'message'))


# --- eln_get (clinic, medicine, evidence=primary, mutating=False) ---
def _eln_get_parse(args):
    tool = "eln_get"
    miss = _required(args, tool, "", ("ogrn", "ln_code", "snils"))
    if miss:
        return miss
    ogrn = _shaped(args["ogrn"], tool, "ogrn", r"\d{13}|\d{15}", "ogrn_pattern")
    ln_code = _digits_spaceless(args["ln_code"], tool, "ln_code", 12, "ln_code_format")
    snils = _parse_snils_bare(args["snils"], tool, "snils")
    bad = _first(ogrn, ln_code, snils)
    if bad:
        return bad
    return {"ogrn": ogrn, "ln_code": ln_code, "snils": snils}

ELN_GET = ToolSpec(
    name='eln_get',
    source='https://lk.sfr.gov.ru/eln/Спецификация_ЭЛН_МО_v_2.1.docx',
    schema=_schema('eln_get', 'СФР, Система учёта ЭЛН — веб-сервис FileOperationsLnService, метод getLNData (спецификация ЭЛН для МО)',
        {'ogrn': {'type': 'string', 'description': '13 or 15 digits'}, 'ln_code': {'type': 'string', 'description': 'ELN_CODE — 12 digits'}, 'snils': {'type': 'string', 'description': 'SNILS — 11 digits, no separators'}},
        ('ogrn', 'ln_code', 'snils')),
    fields=(
            FieldSpec('ogrn', 'plain', required=True),
            FieldSpec('ln_code', "identity", 'ELN_NUMBER', '', required=True),
            FieldSpec('snils', "identity", 'SNILS', '', required=True),
    ),
    parse=_eln_get_parse, mutating=False,
    result_pii=('data.row.snils', 'data.row.surname', 'data.row.name', 'data.row.patronymic', 'data.row.lnCode', 'data.row.birthday', 'data.row.servFullData.surname', 'data.row.servFullData.name', 'data.row.servFullData.birthday'))


# --- remd_documents_search (clinic, medicine, evidence=secondary, mutating=False) ---
def _remd_documents_search_parse(args):
    tool = "remd_documents_search"
    miss = _required(args, tool, "", ("patient_snils",))
    if miss:
        return miss
    snils = _parse_snils_bare(args["patient_snils"], tool, "patient_snils")
    if isinstance(snils, Refusal):
        return snils
    out = {"patient_snils": snils}
    if args.get("kind") not in (None, ""):
        out["kind"] = str(args["kind"]).strip()
    for key in ("creation_date_begin", "creation_date_end"):
        if args.get(key) not in (None, ""):
            value = _parse_date_iso(args[key], tool, key)
            if isinstance(value, Refusal):
                return value
            out[key] = value
    return out

REMD_DOCUMENTS_SEARCH = ToolSpec(
    name='remd_documents_search',
    source='https://help.medflex.me/searchRegistryItem/',
    schema=_schema('remd_documents_search', 'ЕГИСЗ, подсистема РЭМД — searchRegistryItem (поиск записей реестра ЭМД по пациенту); через шлюзы (N3.Health, МедФлекс)',
        {'patient_snils': {'type': 'string', 'description': 'SNILS — 11 digits, no separators'}, 'kind': {'type': 'string', 'description': 'значение из закрытого списка'}, 'creation_date_begin': {'type': 'string', 'description': 'строка'}, 'creation_date_end': {'type': 'string', 'description': 'строка'}},
        ('patient_snils',)),
    fields=(
            FieldSpec('patient_snils', "identity", 'SNILS', '', required=True),
            FieldSpec('kind', 'enum', required=False),
            FieldSpec('creation_date_begin', 'plain', required=False),
            FieldSpec('creation_date_end', 'plain', required=False),
    ),
    parse=_remd_documents_search_parse, mutating=False,
    result_pii=('items[].patient.snils', 'items[].patient.fio', 'items[].patient.birth_date', 'items[].document_number'))


# --- oms_policy_find (clinic, medicine, evidence=primary, mutating=False) ---
def _oms_policy_find_parse(args):
    tool = "oms_policy_find"
    keys = [k for k in ("enp", "snils", "last_name") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "enp":
        enp = _parse_oms_enp(args["enp"], tool, "enp")
        if isinstance(enp, Refusal):
            return enp
        return {"enp": enp}
    if keys[0] == "snils":
        snils = _parse_snils_bare(args["snils"], tool, "snils")
        if isinstance(snils, Refusal):
            return snils
        return {"snils": snils}
    name = parse_name_word(args["last_name"], tool, "last_name")
    if isinstance(name, Refusal):
        return name
    out = {"last_name": name}
    if args.get("birth_date") not in (None, ""):
        birth = _parse_date_iso(args["birth_date"], tool, "birth_date")
        if isinstance(birth, Refusal):
            return birth
        out["birth_date"] = birth
    return out

OMS_POLICY_FIND = ToolSpec(
    name='oms_policy_find',
    source='https://rostov-tfoms.ru/services/zasedaniya-rabochih-grupp/erp/enp-struct',
    schema=_schema('oms_policy_find', 'ТФОМС / ФОМС — единый регистр застрахованных лиц (ЕРЗ): идентификация застрахованного по ЕНП / СНИЛС / документу',
        {'enp': {'type': 'string', 'description': 'OMS_POLICY — 16 digits'}, 'snils': {'type': 'string', 'description': 'SNILS'}, 'last_name': {'type': 'string', 'description': 'NAME (surname)'}, 'birth_date': {'type': 'string', 'description': 'DOB'}},
        ()),
    fields=(
            FieldSpec('enp', "identity", 'OMS_ENP', '', required=False),
            FieldSpec('snils', "identity", 'SNILS', '', required=False),
            FieldSpec('last_name', "identity", 'NAME', 'surname', required=False),
            FieldSpec('birth_date', "identity", 'DOB', '', required=False),
    ),
    parse=_oms_policy_find_parse, mutating=False,
    result_pii=('person.fam', 'person.im', 'person.ot', 'person.dr', 'person.enp', 'person.snils'))


# --- e_prescription_create (clinic, medicine, evidence=summary, mutating=True) ---
def _e_prescription_create_parse(args):
    tool = "e_prescription_create"
    miss = _required(args, tool, "", ("patient", "drug", "dosage"))
    if miss:
        return miss
    patient = _obj(args["patient"], tool, "patient")
    if isinstance(patient, Refusal):
        return patient
    miss = _required(patient, tool, "patient", ("fio", "birth_date"))
    if miss:
        return miss
    fio = parse_text(patient["fio"], tool, "patient.fio", 120)
    birth = _parse_date_iso(patient["birth_date"], tool, "patient.birth_date")
    drug = parse_text(args["drug"], tool, "drug", 200)
    dosage = parse_text(args["dosage"], tool, "dosage", 100)
    bad = _first(fio, birth, drug, dosage)
    if bad:
        return bad
    out = {"patient": {"fio": str(fio).strip(), "birth_date": birth},
           "drug": str(drug).strip(), "dosage": str(dosage).strip()}
    if patient.get("snils") not in (None, ""):
        snils = parse_snils(patient["snils"], tool, "patient.snils")
        if isinstance(snils, Refusal):
            return snils
        out["patient"]["snils"] = snils
    if patient.get("oms_policy") not in (None, ""):
        enp = _parse_oms_enp(patient["oms_policy"], tool, "patient.oms_policy")
        if isinstance(enp, Refusal):
            return enp
        out["patient"]["oms_policy"] = enp
    return out

E_PRESCRIPTION_CREATE = ToolSpec(
    name='e_prescription_create',
    source='https://www.consultant.ru/document/cons_doc_LAW_401865/af42dc5917c97680f33eaf2d8c74214b0e285cb6/',
    schema=_schema('e_prescription_create', 'МИС → ЕГИСЗ: СЭМД «Рецепт на лекарственный препарат» (электронный аналог формы 107-1/у / 148-1/у-88)',
        {'patient.fio': {'type': 'string', 'description': 'NAME'}, 'patient.birth_date': {'type': 'string', 'description': 'DOB'}, 'patient.snils': {'type': 'string', 'description': 'SNILS'}, 'patient.oms_policy': {'type': 'string', 'description': 'OMS_POLICY'}, 'drug': {'type': 'string', 'description': 'свободный текст'}, 'dosage': {'type': 'string', 'description': 'свободный текст'}},
        ('patient.fio', 'patient.birth_date', 'drug', 'dosage')),
    fields=(
            FieldSpec('patient.fio', "identity", 'NAME', '', required=True),
            FieldSpec('patient.birth_date', "identity", 'DOB', '', required=True),
            FieldSpec('patient.snils', "identity", 'SNILS', '', required=False),
            FieldSpec('patient.oms_policy', "identity", 'OMS_ENP', '', required=False),
            FieldSpec('drug', 'free', required=True),
            FieldSpec('dosage', 'free', required=True),
    ),
    parse=_e_prescription_create_parse, mutating=True,
    result_pii=('prescription.number', 'prescription.patient.fio', 'prescription.patient.birth_date', 'prescription.patient.oms_policy', 'message'))


# --- marketplace_order_get (delivery, retail, evidence=secondary, mutating=False) ---
def _marketplace_order_get_parse(args):
    tool = "marketplace_order_get"
    miss = _required(args, tool, "", ("posting_number",))
    if miss:
        return miss
    posting = _shaped(args["posting_number"], tool, "posting_number",
                      r"[0-9A-Za-z-]{4,30}", "posting_number_format")
    if isinstance(posting, Refusal):
        return posting
    return {"posting_number": posting}

MARKETPLACE_ORDER_GET = ToolSpec(
    name='marketplace_order_get',
    source='https://github.com/diphantxm/ozon-api-client/blob/master/ozon/fbs.go',
    schema=_schema('marketplace_order_get', 'Ozon Seller API POST /v3/posting/fbs/get (rFBS) / Wildberries Orders DBS POST /api/v3/dbs/orders/client',
        {'posting_number': {'type': 'string', 'description': 'строка'}},
        ('posting_number',)),
    fields=(
            FieldSpec('posting_number', 'plain', required=True),
    ),
    parse=_marketplace_order_get_parse, mutating=False,
    result_pii=('result.customer.name', 'result.customer.address.address_tail', 'result.addressee.name', 'orders[].firstName', 'orders[].fullName', 'orders[].phone'))


# --- loyalty_customer_get (crm, retail, evidence=summary, mutating=False) ---
def _loyalty_customer_get_parse(args):
    tool = "loyalty_customer_get"
    keys = [k for k in ("mobile_phone", "email", "discount_card") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "mobile_phone":
        phone = _parse_phone_digits(args["mobile_phone"], tool, "mobile_phone")
        if isinstance(phone, Refusal):
            return phone
        return {"mobile_phone": phone}
    if keys[0] == "email":
        email = str(args["email"]).strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return Refusal(tool, "email", "email_format", str(args["email"]))
        return {"email": email}
    card = str(args["discount_card"]).strip()
    return {"discount_card": card}

LOYALTY_CUSTOMER_GET = ToolSpec(
    name='loyalty_customer_get',
    source='https://developers.mindbox.ru/',
    schema=_schema('loyalty_customer_get', 'Mindbox API v3 operations (sync) — получение данных клиента; Manzana Loyalty — Contact/Card',
        {'mobile_phone': {'type': 'string', 'description': 'PHONE (digits)'}, 'email': {'type': 'string', 'description': 'EMAIL'}, 'discount_card': {'type': 'string', 'description': 'LOYALTY_CARD'}},
        ()),
    fields=(
            FieldSpec('mobile_phone', "identity", 'PHONE', 'digits', required=False),
            FieldSpec('email', "identity", 'EMAIL', '', required=False),
            FieldSpec('discount_card', "identity", 'LOYALTY_CARD_NUMBER', '', required=False),
    ),
    parse=_loyalty_customer_get_parse, mutating=False,
    result_pii=('customer.lastName', 'customer.firstName', 'customer.middleName', 'customer.birthDate', 'customer.mobilePhone', 'customer.email', 'customer.discountCards[].ids.number'))


# --- loyalty_card_bind (crm, retail, evidence=primary, mutating=True) ---
def _loyalty_card_bind_parse(args):
    tool = "loyalty_card_bind"
    miss = _required(args, tool, "", ("customer", "card_number"))
    if miss:
        return miss
    customer = _obj(args["customer"], tool, "customer")
    if isinstance(customer, Refusal):
        return customer
    miss = _required(customer, tool, "customer", ("mobile_phone",))
    if miss:
        return miss
    phone = _parse_phone_digits(customer["mobile_phone"], tool, "customer.mobile_phone")
    card = _parse_loyalty(args["card_number"], tool, "card_number")
    bad = _first(phone, card)
    if bad:
        return bad
    return {"customer": {"mobile_phone": phone}, "card_number": card}

LOYALTY_CARD_BIND = ToolSpec(
    name='loyalty_card_bind',
    source='https://developers.mindbox.ru/docs/customer-card-activation',
    schema=_schema('loyalty_card_bind', 'Mindbox «Выдача дисконтной карты клиенту» (операция RegCard) / Manzana Card/Bind',
        {'customer.mobile_phone': {'type': 'string', 'description': 'PHONE (digits)'}, 'card_number': {'type': 'string', 'description': 'LOYALTY_CARD'}},
        ('customer.mobile_phone', 'card_number')),
    fields=(
            FieldSpec('customer.mobile_phone', "identity", 'PHONE', 'digits', required=True),
            FieldSpec('card_number', "identity", 'LOYALTY_CARD_NUMBER', '', required=True),
    ),
    parse=_loyalty_card_bind_parse, mutating=True,
    result_pii=('discountCard.ids.number', 'discountCard.ids.number'))


# --- fiscal_receipt_create (bank, retail, evidence=primary, mutating=True) ---
def _fiscal_receipt_create_parse(args):
    tool = "fiscal_receipt_create"
    miss = _required(args, tool, "", ("external_id", "receipt"))
    if miss:
        return miss
    external_id = _parse_opaque_id(args["external_id"], tool, "external_id")
    receipt = _obj(args["receipt"], tool, "receipt")
    if isinstance(receipt, Refusal):
        return receipt
    miss = _required(receipt, tool, "receipt", ("items",))
    if miss:
        return miss
    client = _obj(receipt.get("client", {}), tool, "receipt.client")
    if isinstance(client, Refusal):
        return client
    has_email = client.get("email") not in (None, "")
    has_phone = client.get("phone") not in (None, "")
    if not has_email and not has_phone:
        return Refusal(tool, "receipt.client", "email_or_phone_required", "")
    out = {"external_id": external_id, "receipt": {"items": receipt["items"],
           "client": {}}}
    if has_email:
        email = str(client["email"]).strip().lower()
        if not EMAIL_RE.fullmatch(email):
            return Refusal(tool, "receipt.client.email", "email_format", str(client["email"]))
        out["receipt"]["client"]["email"] = email
    if has_phone:
        phone = _parse_numeric_phone(client["phone"], tool, "receipt.client.phone")
        if isinstance(phone, Refusal):
            return phone
        out["receipt"]["client"]["phone"] = phone
    for key in ("name", "inn", "birthdate", "document_data", "address"):
        if client.get(key) not in (None, ""):
            out["receipt"]["client"][key] = str(client[key]).strip()
    if client.get("inn") not in (None, ""):
        inn = parse_inn(client["inn"], tool, "receipt.client.inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        out["receipt"]["client"]["inn"] = inn
    if client.get("birthdate") not in (None, ""):
        birth = _parse_dmy(client["birthdate"], tool, "receipt.client.birthdate")
        if isinstance(birth, Refusal):
            return birth
        out["receipt"]["client"]["birthdate"] = birth
    return out

FISCAL_RECEIPT_CREATE = ToolSpec(
    name='fiscal_receipt_create',
    source='https://atol.online/files/API_atol_online_v5.pdf',
    schema=_schema('fiscal_receipt_create', 'АТОЛ Онлайн API v5 (ФФД 1.2) — sell / sell_correction, объект receipt.client',
        {'external_id': {'type': 'string', 'description': 'строка'}, 'receipt.client.email': {'type': 'string', 'description': 'EMAIL'}, 'receipt.client.phone': {'type': 'string', 'description': 'PHONE — +digits, no spaces'}, 'receipt.client.name': {'type': 'string', 'description': 'NAME'}, 'receipt.client.inn': {'type': 'string', 'description': 'INN'}, 'receipt.client.birthdate': {'type': 'string', 'description': 'DOB — DD.MM.YYYY'}, 'receipt.client.document_data': {'type': 'string', 'description': 'PASSPORT'}, 'receipt.client.address': {'type': 'string', 'description': 'LOC'}, 'receipt.items': {'type': 'string', 'description': 'строка'}},
        ('external_id', 'receipt.items')),
    fields=(
            FieldSpec('external_id', 'plain', required=True),
            FieldSpec('receipt.client.email', "identity", 'EMAIL', '', required=False),
            FieldSpec('receipt.client.phone', "identity", 'PHONE', '', required=False),
            FieldSpec('receipt.client.name', "identity", 'NAME', '', required=False),
            FieldSpec('receipt.client.inn', "identity", 'INN', '', required=False),
            FieldSpec('receipt.client.birthdate', "identity", 'DOB', '', required=False),
            FieldSpec('receipt.client.document_data', "identity", 'PASSPORT', '', required=False),
            FieldSpec('receipt.client.address', "identity", 'LOC', '', required=False),
            FieldSpec('receipt.items', 'plain', required=True),
    ),
    parse=_fiscal_receipt_create_parse, mutating=True,
    result_pii=('receipt.client.name', 'receipt.client.email', 'receipt.client.phone', 'receipt.client.inn', 'receipt.client.birthdate', 'receipt.client.document_data', 'receipt.client.address'))


# --- cdek_order_info (delivery, logistics, evidence=secondary, mutating=False) ---
def _cdek_order_info_parse(args):
    tool = "cdek_order_info"
    miss = _required(args, tool, "", ("cdek_number",))
    if miss:
        return miss
    number = _shaped(args["cdek_number"], tool, "cdek_number",
                     r"[0-9A-Za-z-]{4,30}", "cdek_number_format")
    if isinstance(number, Refusal):
        return number
    return {"cdek_number": number}

CDEK_ORDER_INFO = ToolSpec(
    name='cdek_order_info',
    source='https://pkg.go.dev/github.com/ifedor/cdek/v2',
    schema=_schema('cdek_order_info', 'СДЭК API v2 GET /v2/orders?cdek_number= (получатель с паспортными данными и ИНН)',
        {'cdek_number': {'type': 'string', 'description': 'строка'}},
        ('cdek_number',)),
    fields=(
            FieldSpec('cdek_number', 'plain', required=True),
    ),
    parse=_cdek_order_info_parse, mutating=False,
    result_pii=('entity.recipient.name', 'entity.recipient.passport_series', 'entity.recipient.passport_number', 'entity.recipient.passport_date_of_birth', 'entity.recipient.tin', 'entity.recipient.phones[].number', 'entity.to_location.address', 'requests[].errors[].message'))


# --- osago_policy_check (government, insurance, evidence=summary, mutating=False) ---
def _osago_policy_check_parse(args):
    tool = "osago_policy_check"
    keys = [k for k in ("plate", "vin", "policy") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "plate":
        plate = _parse_plate(args["plate"], tool, "plate")
        if isinstance(plate, Refusal):
            return plate
        return {"plate": plate}
    if keys[0] == "vin":
        vin = _parse_vin(args["vin"], tool, "vin")
        if isinstance(vin, Refusal):
            return vin
        return {"vin": vin}
    policy = _parse_osago(args["policy"], tool, "policy")
    if isinstance(policy, Refusal):
        return policy
    out = {"policy": policy}
    if args.get("date") not in (None, ""):
        out["date"] = str(args["date"]).strip()
    return out

OSAGO_POLICY_CHECK = ToolSpec(
    name='osago_policy_check',
    source='https://dkbm-web.autoins.ru/dkbm-web-1.0/policyInfo.htm',
    schema=_schema('osago_policy_check', 'РСА (АИС ОСАГО) — проверка полиса ОСАГО по госномеру / VIN / кузову / серии-номеру полиса',
        {'plate': {'type': 'string', 'description': 'PLATE'}, 'vin': {'type': 'string', 'description': 'VIN'}, 'policy': {'type': 'string', 'description': 'OSAGO_POLICY'}, 'date': {'type': 'string', 'description': 'строка'}},
        ()),
    fields=(
            FieldSpec('plate', "identity", 'PLATE', '', required=False),
            FieldSpec('vin', "identity", 'VIN', '', required=False),
            FieldSpec('policy', "identity", 'OSAGO_POLICY', '', required=False),
            FieldSpec('date', 'plain', required=False),
    ),
    parse=_osago_policy_check_parse, mutating=False,
    result_pii=('policy.series', 'policy.number', 'vehicle.plate', 'vehicle.vin'))


# --- insurance_claim_create (bank, insurance, evidence=summary, mutating=True) ---
def _insurance_claim_create_parse(args):
    tool = "insurance_claim_create"
    miss = _required(args, tool, "", ("applicant", "policy"))
    if miss:
        return miss
    applicant = _obj(args["applicant"], tool, "applicant")
    if isinstance(applicant, Refusal):
        return applicant
    miss = _required(applicant, tool, "applicant", ("fio", "birth_date", "passport"))
    if miss:
        return miss
    fio = parse_text(applicant["fio"], tool, "applicant.fio", 200)
    birth = _parse_date_iso(applicant["birth_date"], tool, "applicant.birth_date")
    passport = _digits_spaceless(applicant["passport"], tool, "applicant.passport",
                                 10, "passport_format")
    policy = _parse_osago(args["policy"], tool, "policy")
    bad = _first(fio, birth, passport, policy)
    if bad:
        return bad
    out = {"applicant": {"fio": str(fio).strip(), "birth_date": birth,
                         "passport": passport}, "policy": policy}
    if applicant.get("inn") not in (None, ""):
        inn = parse_inn(applicant["inn"], tool, "applicant.inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        out["applicant"]["inn"] = inn
    for key in ("phone", "email", "address"):
        if applicant.get(key) not in (None, ""):
            out["applicant"][key] = str(applicant[key]).strip()
    vehicle = args.get("vehicle")
    if vehicle:
        vehicle = _obj(vehicle, tool, "vehicle")
        if isinstance(vehicle, Refusal):
            return vehicle
        v = {}
        if vehicle.get("vin") not in (None, ""):
            vin = _parse_vin(vehicle["vin"], tool, "vehicle.vin")
            if isinstance(vin, Refusal):
                return vin
            v["vin"] = vin
        if vehicle.get("plate") not in (None, ""):
            plate = _parse_plate(vehicle["plate"], tool, "vehicle.plate")
            if isinstance(plate, Refusal):
                return plate
            v["plate"] = plate
        if vehicle.get("sts") not in (None, ""):
            sts = _digits_spaceless(vehicle["sts"], tool, "vehicle.sts", 10, "sts_format")
            if isinstance(sts, Refusal):
                return sts
            v["sts"] = sts
        out["vehicle"] = v
    payout = args.get("payout")
    if payout:
        payout = _obj(payout, tool, "payout")
        if isinstance(payout, Refusal):
            return payout
        p = {}
        if payout.get("account") not in (None, ""):
            account = parse_digits(payout["account"], tool, "payout.account", 20, "account_format")
            if isinstance(account, Refusal):
                return account
            p["account"] = account
        if payout.get("bik") not in (None, ""):
            bik = parse_digits(payout["bik"], tool, "payout.bik", 9, "bik_format")
            if isinstance(bik, Refusal):
                return bik
            p["bik"] = bik
            if "account" in p and not checksum_v6.validate_account(str(p["account"]), str(bik)):
                return Refusal(tool, "payout.account", "account_key_mismatch", str(p["account"]))
        out["payout"] = p
    return out

INSURANCE_CLAIM_CREATE = ToolSpec(
    name='insurance_claim_create',
    source='https://base.garant.ru/409568139/cae826fe4c9a66b3489670e2f0677320/',
    schema=_schema('insurance_claim_create', 'Заявление о страховом возмещении / прямом возмещении убытков по ОСАГО (Положение Банка России 837-П, Приложение 5; ранее 431-П, Приложение 6) — личный кабинет/API страховщика',
        {'applicant.fio': {'type': 'string', 'description': 'NAME'}, 'applicant.birth_date': {'type': 'string', 'description': 'DOB'}, 'applicant.passport': {'type': 'string', 'description': 'PASSPORT'}, 'applicant.inn': {'type': 'string', 'description': 'INN'}, 'applicant.phone': {'type': 'string', 'description': 'PHONE'}, 'applicant.email': {'type': 'string', 'description': 'EMAIL'}, 'applicant.address': {'type': 'string', 'description': 'LOC'}, 'policy': {'type': 'string', 'description': 'OSAGO_POLICY'}, 'vehicle.vin': {'type': 'string', 'description': 'VIN'}, 'vehicle.plate': {'type': 'string', 'description': 'PLATE'}, 'vehicle.sts': {'type': 'string', 'description': 'STS'}, 'payout.account': {'type': 'string', 'description': 'ACCOUNT'}, 'payout.bik': {'type': 'string', 'description': 'строка'}},
        ('applicant.fio', 'applicant.birth_date', 'applicant.passport', 'policy')),
    fields=(
            FieldSpec('applicant.fio', "identity", 'NAME', '', required=True),
            FieldSpec('applicant.birth_date', "identity", 'DOB', '', required=True),
            FieldSpec('applicant.passport', "identity", 'PASSPORT', '', required=True),
            FieldSpec('applicant.inn', "identity", 'INN', '', required=False),
            FieldSpec('applicant.phone', "identity", 'PHONE', '', required=False),
            FieldSpec('applicant.email', "identity", 'EMAIL', '', required=False),
            FieldSpec('applicant.address', "identity", 'LOC', '', required=False),
            FieldSpec('policy', "identity", 'OSAGO_POLICY', '', required=True),
            FieldSpec('vehicle.vin', "identity", 'VIN', '', required=False),
            FieldSpec('vehicle.plate', "identity", 'PLATE', '', required=False),
            FieldSpec('vehicle.sts', "identity", 'STS_NUMBER', '', required=False),
            FieldSpec('payout.account', "identity", 'BANK_ACCOUNT', '', required=False),
            FieldSpec('payout.bik', 'plain', required=False),
    ),
    parse=_insurance_claim_create_parse, mutating=True,
    result_pii=('applicant.fio', 'policy', 'message'))


# --- traffic_fines_check (government, auto, evidence=summary, mutating=False) ---
def _traffic_fines_check_parse(args):
    tool = "traffic_fines_check"
    miss = _required(args, tool, "", ("plate", "sts"))
    if miss:
        return miss
    plate = _parse_plate(args["plate"], tool, "plate")
    sts = _digits_spaceless(args["sts"], tool, "sts", 10, "sts_format")
    bad = _first(plate, sts)
    if bad:
        return bad
    return {"plate": plate, "sts": sts}

TRAFFIC_FINES_CHECK = ToolSpec(
    name='traffic_fines_check',
    source='https://roskazna.gov.ru/gis/…/pro-oplatu-shtrafov/',
    schema=_schema('traffic_fines_check', 'Госавтоинспекция «Проверка штрафов» (гибдд.рф/check/fines) / ГИС ГМП начисления',
        {'plate': {'type': 'string', 'description': 'PLATE'}, 'sts': {'type': 'string', 'description': 'STS'}},
        ('plate', 'sts')),
    fields=(
            FieldSpec('plate', "identity", 'PLATE', '', required=True),
            FieldSpec('sts', "identity", 'STS_NUMBER', '', required=True),
    ),
    parse=_traffic_fines_check_parse, mutating=False,
    result_pii=('fines[].uin', 'fines[].vehicle'))


# --- epts_status_get (government, auto, evidence=summary, mutating=False) ---
def _epts_status_get_parse(args):
    tool = "epts_status_get"
    keys = [k for k in ("epts_number", "vin") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "epts_number":
        epts = _parse_epts(args["epts_number"], tool, "epts_number")
        if isinstance(epts, Refusal):
            return epts
        return {"epts_number": epts}
    vin = _parse_vin(args["vin"], tool, "vin")
    if isinstance(vin, Refusal):
        return vin
    return {"vin": vin}

EPTS_STATUS_GET = ToolSpec(
    name='epts_status_get',
    source='https://xn--k1aigd6c.xn--p1ai/check',
    schema=_schema('epts_status_get', 'АО «Электронный паспорт» (СЭП) — проверка статуса ЭПТС по номеру или VIN',
        {'epts_number': {'type': 'string', 'description': 'EPTS'}, 'vin': {'type': 'string', 'description': 'VIN'}},
        ()),
    fields=(
            FieldSpec('epts_number', "identity", 'EPTS_NUMBER', '', required=False),
            FieldSpec('vin', "identity", 'VIN', '', required=False),
    ),
    parse=_epts_status_get_parse, mutating=False,
    result_pii=('epts', 'vin'))


# --- driver_license_check (government, auto, evidence=summary, mutating=False) ---
def _driver_license_check_parse(args):
    tool = "driver_license_check"
    miss = _required(args, tool, "", ("license_number", "issue_date"))
    if miss:
        return miss
    lic = _digits_spaceless(args["license_number"], tool, "license_number", 10, "license_format")
    issued = _parse_date_iso(args["issue_date"], tool, "issue_date")
    bad = _first(lic, issued)
    if bad:
        return bad
    return {"license_number": lic, "issue_date": issued}

DRIVER_LICENSE_CHECK = ToolSpec(
    name='driver_license_check',
    source='https://www.gosuslugi.ru/600445/1/form',
    schema=_schema('driver_license_check', 'Госавтоинспекция «Проверка водителя» / Госуслуги «Проверка водительского удостоверения»',
        {'license_number': {'type': 'string', 'description': 'DRIVER_LICENSE — «99 12 345678»'}, 'issue_date': {'type': 'string', 'description': 'строка'}},
        ('license_number', 'issue_date')),
    fields=(
            FieldSpec('license_number', "identity", 'DRIVER_LICENSE', '', required=True),
            FieldSpec('issue_date', 'plain', required=True),
    ),
    parse=_driver_license_check_parse, mutating=False,
    result_pii=('license', 'message'))


# --- subscriber_profile_get (crm, telecom, evidence=secondary, mutating=False) ---
def _subscriber_profile_get_parse(args):
    tool = "subscriber_profile_get"
    miss = _required(args, tool, "", ("msisdn",))
    if miss:
        return miss
    msisdn = _parse_phone_digits(args["msisdn"], tool, "msisdn")
    if isinstance(msisdn, Refusal):
        return msisdn
    return {"msisdn": msisdn}

SUBSCRIBER_PROFILE_GET = ToolSpec(
    name='subscriber_profile_get',
    source='https://github.com/poing/tmf632-server/blob/master/docs/Model/Individual.md',
    schema=_schema('subscriber_profile_get', 'BSS оператора связи — TM Forum Open API TMF632 Party Management (Individual) / TMF637 Product Inventory; в РФ — АСР «Гидра», Nexign BSS',
        {'msisdn': {'type': 'string', 'description': 'PHONE (digits)'}},
        ('msisdn',)),
    fields=(
            FieldSpec('msisdn', "identity", 'PHONE', 'digits', required=True),
    ),
    parse=_subscriber_profile_get_parse, mutating=False,
    result_pii=('individual.familyName', 'individual.givenName', 'individual.middleName', 'individual.birthDate', 'individual.individualIdentification[].identificationId', 'contract.number', 'contract.personalAccount', 'sim.msisdn', 'sim.iccid', 'sim.imsi', 'device.imei'))


# --- sim_replace_request (support, telecom, evidence=summary, mutating=True) ---
def _sim_replace_request_parse(args):
    tool = "sim_replace_request"
    miss = _required(args, tool, "", ("msisdn", "fio", "passport", "new_iccid"))
    if miss:
        return miss
    msisdn = _parse_phone_digits(args["msisdn"], tool, "msisdn")
    fio = parse_text(args["fio"], tool, "fio", 200)
    passport = _digits_spaceless(args["passport"], tool, "passport", 10, "passport_format")
    iccid = _parse_iccid(args["new_iccid"], tool, "new_iccid")
    bad = _first(msisdn, fio, passport, iccid)
    if bad:
        return bad
    out = {"msisdn": msisdn, "fio": str(fio).strip(), "passport": passport,
           "new_iccid": iccid}
    if args.get("contract_number") not in (None, ""):
        out["contract_number"] = str(args["contract_number"]).strip()
    return out

SIM_REPLACE_REQUEST = ToolSpec(
    name='sim_replace_request',
    source='https://www.garant.ru/news/536002/',
    schema=_schema('sim_replace_request', 'Замена SIM / перенос номера (MNP, 253-ФЗ): заявление абонента с документом, удостоверяющим личность; ЦНИС',
        {'msisdn': {'type': 'string', 'description': 'PHONE'}, 'fio': {'type': 'string', 'description': 'NAME'}, 'passport': {'type': 'string', 'description': 'PASSPORT'}, 'new_iccid': {'type': 'string', 'description': 'ICCID'}, 'contract_number': {'type': 'string', 'description': 'CONTRACT_NUMBER'}},
        ('msisdn', 'fio', 'passport', 'new_iccid')),
    fields=(
            FieldSpec('msisdn', "identity", 'PHONE', '', required=True),
            FieldSpec('fio', "identity", 'NAME', '', required=True),
            FieldSpec('passport', "identity", 'PASSPORT', '', required=True),
            FieldSpec('new_iccid', "identity", 'ICCID', '', required=True),
            FieldSpec('contract_number', "plain", required=False),
    ),
    parse=_sim_replace_request_parse, mutating=True,
    result_pii=('msisdn', 'iccid', 'message'))


# --- egrn_extract_get (government, real_estate, evidence=summary, mutating=False) ---
def _egrn_extract_get_parse(args):
    tool = "egrn_extract_get"
    miss = _required(args, tool, "", ("cadastral_number",))
    if miss:
        return miss
    cad = _parse_cadastral(args["cadastral_number"], tool, "cadastral_number")
    if isinstance(cad, Refusal):
        return cad
    return {"cadastral_number": cad}

EGRN_EXTRACT_GET = ToolSpec(
    name='egrn_extract_get',
    source='https://www.garant.ru/news/1610451/',
    schema=_schema('egrn_extract_get', 'Росреестр, ФГИС ЕГРН — выписка об объекте недвижимости (веб-сервисы Росреестра для профессиональных пользователей)',
        {'cadastral_number': {'type': 'string', 'description': 'CADASTRAL_NUMBER — AA:BB:CCCCCCC:KK'}},
        ('cadastral_number',)),
    fields=(
            FieldSpec('cadastral_number', "identity", 'CADASTRAL_NUMBER', '', required=True),
    ),
    parse=_egrn_extract_get_parse, mutating=False,
    result_pii=('object.cadastral_number', 'object.address', 'rights[].holder', 'rights[].birth_date', 'rights[].reg_number'))


# --- gis_gkh_account_get (government, real_estate, evidence=summary, mutating=False) ---
def _gis_gkh_account_get_parse(args):
    tool = "gis_gkh_account_get"
    keys = [k for k in ("els", "address") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "els":
        els = _parse_els(args["els"], tool, "els")
        if isinstance(els, Refusal):
            return els
        return {"els": els}
    address = parse_text(args["address"], tool, "address", 200)
    if isinstance(address, Refusal):
        return address
    out = {"address": str(address).strip()}
    if args.get("flat") not in (None, ""):
        out["flat"] = str(args["flat"]).strip()
    return out

GIS_GKH_ACCOUNT_GET = ToolSpec(
    name='gis_gkh_account_get',
    source='https://ukavenue.ru/faq/oplata/v-kvitancii-poyavilis-kakie-to-novye-bukvy-i-cifry-els-gis-zhkh-80ao337193/',
    schema=_schema('gis_gkh_account_get', 'ГИС ЖКХ (dom.gosuslugi.ru) — лицевые счета: ЕЛС, идентификатор ЖКУ, адрес помещения, плательщик (сервис управления домами, export данных ЛС)',
        {'els': {'type': 'string', 'description': 'ELS_GKH'}, 'address': {'type': 'string', 'description': 'LOC'}, 'flat': {'type': 'string', 'description': 'строка'}},
        ()),
    fields=(
            FieldSpec('els', "identity", 'GIS_ZHKH_ELS', '', required=False),
            FieldSpec('address', "identity", 'LOC', '', required=False),
            FieldSpec('flat', 'plain', required=False),
    ),
    parse=_gis_gkh_account_get_parse, mutating=False,
    result_pii=('account.els', 'account.zhku_id', 'account.personal_account', 'account.address', 'account.payer.fio', 'account.payer.snils'))


# --- pms_booking_get (calendar, hospitality, evidence=summary, mutating=False) ---
def _pms_booking_get_parse(args):
    tool = "pms_booking_get"
    if args.get("booking_id") in (None, ""):
        return Refusal(tool, "booking_id", "missing_required", "")
    booking_id = _parse_opaque_id(args["booking_id"], tool, "booking_id")
    if isinstance(booking_id, Refusal):
        return booking_id
    out = {"booking_id": booking_id}
    for key in ("date_from", "date_to"):
        if args.get(key) not in (None, ""):
            value = _parse_date_iso(args[key], tool, key)
            if isinstance(value, Refusal):
                return value
            out[key] = value
    return out

PMS_BOOKING_GET = ToolSpec(
    name='pms_booking_get',
    source='https://help.bnovo.ru/knowledgebase/открытое-api-bnovo-pms/',
    schema=_schema('pms_booking_get', 'Bnovo PMS API v1 GET /bookings, /bookings/{id} / TravelLine WebPMS',
        {'booking_id': {'type': 'string', 'description': 'BOOKING_ID'}, 'date_from': {'type': 'string', 'description': 'строка'}, 'date_to': {'type': 'string', 'description': 'строка'}},
        ()),
    fields=(
            FieldSpec('booking_id', "plain", required=False),
            FieldSpec('date_from', 'plain', required=False),
            FieldSpec('date_to', 'plain', required=False),
    ),
    parse=_pms_booking_get_parse, mutating=False,
    result_pii=('booking.customer.name', 'booking.customer.surname', 'booking.customer.phone', 'booking.customer.email', 'booking.guests[].surname', 'booking.guests[].name', 'booking.guests[].birthdate', 'booking.guests[].document.series', 'booking.guests[].document.number', 'bookings[].customer.surname', 'bookings[].customer.phone'))


# --- guest_arrival_notify (government, hospitality, evidence=primary, mutating=True) ---
def _guest_arrival_notify_parse(args):
    tool = "guest_arrival_notify"
    miss = _required(args, tool, "", ("guest", "stay"))
    if miss:
        return miss
    guest = _obj(args["guest"], tool, "guest")
    if isinstance(guest, Refusal):
        return guest
    miss = _required(guest, tool, "guest",
                     ("last_name", "first_name", "citizenship", "birth_date", "document"))
    if miss:
        return miss
    last = parse_name_word(guest["last_name"], tool, "guest.last_name")
    first = parse_name_word(guest["first_name"], tool, "guest.first_name")
    citizenship = str(guest["citizenship"]).strip().upper()
    if not citizenship:
        return Refusal(tool, "guest.citizenship", "citizenship_code", citizenship)
    birth = _parse_date_iso(guest["birth_date"], tool, "guest.birth_date")
    document = _obj(guest["document"], tool, "guest.document")
    if isinstance(document, Refusal):
        return document
    miss = _required(document, tool, "guest.document", ("number",))
    if miss:
        return miss
    doc_number = _parse_intl_passport(document["number"], tool, "guest.document.number")
    bad = _first(last, first, birth, doc_number)
    if bad:
        return bad
    stay = _obj(args["stay"], tool, "stay")
    if isinstance(stay, Refusal):
        return stay
    miss = _required(stay, tool, "stay", ("address", "until"))
    if miss:
        return miss
    address = parse_text(stay["address"], tool, "stay.address", 200)
    until = parse_text(stay["until"], tool, "stay.until", 20)
    bad = _first(address, until)
    if bad:
        return bad
    out = {"guest": {"last_name": last, "first_name": first,
                     "citizenship": citizenship, "birth_date": birth,
                     "document": {"number": doc_number}},
           "stay": {"address": str(address).strip(), "until": str(until).strip()}}
    if guest.get("migration_card") not in (None, ""):
        out["guest"]["migration_card"] = str(guest["migration_card"]).strip()
    if guest.get("visa") not in (None, ""):
        out["guest"]["visa"] = str(guest["visa"]).strip()
    return out

GUEST_ARRIVAL_NOTIFY = ToolSpec(
    name='guest_arrival_notify',
    source='https://www.consultant.ru/document/cons_doc_LAW_376871/3f409dc0f75268f237dfd37b0cffbbec6137e1a7/',
    schema=_schema('guest_arrival_notify', 'Миграционный учёт: уведомление о прибытии иностранного гражданина в место пребывания (форма — Приказ МВД 856 от 10.12.2020, новая форма Приказ МВД 628 от 22.10.2024); подача гостиницей через Контур.От…',
        {'guest.last_name': {'type': 'string', 'description': 'NAME (surname) — Latin as in the passport'}, 'guest.first_name': {'type': 'string', 'description': 'NAME (given)'}, 'guest.citizenship': {'type': 'string', 'description': 'значение из закрытого списка'}, 'guest.birth_date': {'type': 'string', 'description': 'DOB'}, 'guest.document.number': {'type': 'string', 'description': 'FOREIGN_PASSPORT'}, 'guest.migration_card': {'type': 'string', 'description': 'MIGRATION_CARD'}, 'guest.visa': {'type': 'string', 'description': 'VISA_NUMBER'}, 'stay.address': {'type': 'string', 'description': 'LOC'}, 'stay.until': {'type': 'string', 'description': 'строка'}},
        ('guest.last_name', 'guest.first_name', 'guest.citizenship', 'guest.birth_date', 'guest.document.number', 'stay.address', 'stay.until')),
    fields=(
            FieldSpec('guest.last_name', "identity", 'NAME', 'surname', required=True),
            FieldSpec('guest.first_name', "identity", 'NAME', 'given', required=True),
            FieldSpec('guest.citizenship', 'enum', required=True),
            FieldSpec('guest.birth_date', "identity", 'DOB', '', required=True),
            FieldSpec('guest.document.number', "identity", 'INTL_PASSPORT', '', required=True),
            FieldSpec('guest.migration_card', "plain", required=False),
            FieldSpec('guest.visa', "plain", required=False),
            FieldSpec('stay.address', "identity", 'LOC', '', required=True),
            FieldSpec('stay.until', 'plain', required=True),
    ),
    parse=_guest_arrival_notify_parse, mutating=True,
    result_pii=('guest.fio', 'guest.document', 'reason'))


# --- flight_order_get (calendar, hospitality, evidence=primary, mutating=False) ---
def _flight_order_get_parse(args):
    tool = "flight_order_get"
    miss = _required(args, tool, "", ("flight_order_id",))
    if miss:
        return miss
    order_id = _parse_opaque_id(args["flight_order_id"], tool, "flight_order_id")
    if isinstance(order_id, Refusal):
        return order_id
    return {"flight_order_id": order_id}

FLIGHT_ORDER_GET = ToolSpec(
    name='flight_order_get',
    source='https://raw.githubusercontent.com/amadeus4dev/amadeus-open-api-specification/main/spec/json/FlightOrderManagement_v1_swagger_specification.json',
    schema=_schema('flight_order_get', 'GDS PNR: Amadeus Self-Service Flight Order Management GET /v1/booking/flight-orders/{id}; в РФ — Сирена-Трэвел (PNR 6 знаков)',
        {'flight_order_id': {'type': 'string', 'description': 'строка'}},
        ('flight_order_id',)),
    fields=(
            FieldSpec('flight_order_id', 'plain', required=True),
    ),
    parse=_flight_order_get_parse, mutating=False,
    result_pii=('data.associatedRecords[].reference', 'data.travelers[].dateOfBirth', 'data.travelers[].name.firstName', 'data.travelers[].name.lastName', 'data.travelers[].documents[].number', 'data.travelers[].contact.emailAddress', 'data.travelers[].contact.phones[].number', 'errors[].detail'))


# --- hr_employee_get (crm, hr, evidence=summary, mutating=False) ---
def _hr_employee_get_parse(args):
    tool = "hr_employee_get"
    keys = [k for k in ("tab_number", "fio") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "tab_number":
        tab = _shaped(args["tab_number"], tool, "tab_number", r"\d{6,10}", "tab_number_format")
        if isinstance(tab, Refusal):
            return tab
        return {"tab_number": tab}
    fio = parse_text(args["fio"], tool, "fio", 120)
    if isinstance(fio, Refusal):
        return fio
    return {"fio": str(fio).strip()}

HR_EMPLOYEE_GET = ToolSpec(
    name='hr_employee_get',
    source='https://1cfresh.com/articles/data_odata',
    schema=_schema('hr_employee_get', '1С:Зарплата и управление персоналом 3 — стандартный интерфейс OData (Catalog_Сотрудники, Catalog_ФизическиеЛица)',
        {'tab_number': {'type': 'string', 'description': 'TAB_NUMBER'}, 'fio': {'type': 'string', 'description': 'NAME'}},
        ()),
    fields=(
            FieldSpec('tab_number', "identity", 'EMPLOYEE_TAB_NUMBER', '', required=False),
            FieldSpec('fio', "identity", 'NAME', '', required=False),
    ),
    parse=_hr_employee_get_parse, mutating=False,
    result_pii=('value[].Description', 'value[].ТабельныйНомер', 'value[].ФизическоеЛицо.ДатаРождения', 'value[].ФизическоеЛицо.ИНН', 'value[].ФизическоеЛицо.СтраховойНомерПФР', 'error.subject'))


# --- resume_get (search, hr, evidence=summary, mutating=False) ---
def _resume_get_parse(args):
    tool = "resume_get"
    miss = _required(args, tool, "", ("resume_id",))
    if miss:
        return miss
    resume_id = _parse_opaque_id(args["resume_id"], tool, "resume_id")
    if isinstance(resume_id, Refusal):
        return resume_id
    return {"resume_id": resume_id}

RESUME_GET = ToolSpec(
    name='resume_get',
    source='https://github.com/hhru/api/blob/master/docs/employer_resumes.md',
    schema=_schema('resume_get', 'hh.ru API GET /resumes/{resume_id} (работодатель)',
        {'resume_id': {'type': 'string', 'description': 'строка'}},
        ('resume_id',)),
    fields=(
            FieldSpec('resume_id', 'plain', required=True),
    ),
    parse=_resume_get_parse, mutating=False,
    result_pii=('last_name', 'first_name', 'middle_name', 'birth_date', 'contact[].value.formatted', 'contact[].value'))


# --- payroll_card_registry (bank, hr, evidence=summary, mutating=True) ---
def _payroll_card_registry_parse(args):
    tool = "payroll_card_registry"
    miss = _required(args, tool, "", ("employees",))
    if miss:
        return miss
    raw = args["employees"]
    if not isinstance(raw, list) or not raw:
        return Refusal(tool, "employees", "missing_required", str(raw))
    if len(raw) > 1000:
        return Refusal(tool, "employees", "too_many_rows", str(len(raw)))
    rows = []
    for index, entry in enumerate(raw):
        block = _obj(entry, tool, f"employees[{index}]")
        if isinstance(block, Refusal):
            return block
        miss = _required(block, tool, f"employees[{index}]", ("fio", "birth_date", "passport"))
        if miss:
            return miss
        fio = parse_text(block["fio"], tool, f"employees[{index}].fio", 200)
        birth = _parse_date_iso(block["birth_date"], tool, f"employees[{index}].birth_date")
        passport = _digits_spaceless(block["passport"], tool,
                                     f"employees[{index}].passport", 10, "passport_format")
        bad = _first(fio, birth, passport)
        if bad:
            return bad
        row = {"fio": str(fio).strip(), "birth_date": birth, "passport": passport}
        if block.get("tab_number") not in (None, ""):
            tab = _shaped(block["tab_number"], tool, f"employees[{index}].tab_number",
                          r"\d{6,10}", "tab_number_format")
            if isinstance(tab, Refusal):
                return tab
            row["tab_number"] = tab
        for key in ("phone", "address"):
            if block.get(key) not in (None, ""):
                row[key] = str(block[key]).strip()
        rows.append(row)
    return {"employees": rows}

PAYROLL_CARD_REGISTRY = ToolSpec(
    name='payroll_card_registry',
    source='https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/standart-obmena-dannymi-po-zarplatnym-proektam/',
    schema=_schema('payroll_card_registry', 'Стандарт обмена данными по зарплатным проектам (1С и банки; DirectBank): реестр на открытие лицевых счетов / зачисление',
        {'employees[].fio': {'type': 'string', 'description': 'NAME'}, 'employees[].birth_date': {'type': 'string', 'description': 'DOB'}, 'employees[].passport': {'type': 'string', 'description': 'PASSPORT'}, 'employees[].tab_number': {'type': 'string', 'description': 'TAB_NUMBER'}, 'employees[].phone': {'type': 'string', 'description': 'PHONE'}, 'employees[].address': {'type': 'string', 'description': 'LOC'}},
        ('employees[].fio', 'employees[].birth_date', 'employees[].passport')),
    fields=(
            FieldSpec('employees[].fio', "identity", 'NAME', '', required=True),
            FieldSpec('employees[].birth_date', "identity", 'DOB', '', required=True),
            FieldSpec('employees[].passport', "identity", 'PASSPORT', '', required=True),
            FieldSpec('employees[].tab_number', "identity", 'EMPLOYEE_TAB_NUMBER', '', required=False),
            FieldSpec('employees[].phone', "identity", 'PHONE', '', required=False),
            FieldSpec('employees[].address', "identity", 'LOC', '', required=False),
    ),
    parse=_payroll_card_registry_parse, mutating=True,
    result_pii=('rows[].tab_number', 'rows[].fio', 'rows[].account', 'rows[].status'))


# --- arbitration_case_search (search, legal, evidence=summary, mutating=False) ---
def _arbitration_case_search_parse(args):
    tool = "arbitration_case_search"
    keys = [k for k in ("participant", "inn", "case_number") if args.get(k) not in (None, "")]
    if not keys:
        return Refusal(tool, "", "at_least_one_key", "")
    out = {}
    if args.get("participant") not in (None, ""):
        name = parse_text(args["participant"], tool, "participant", 200)
        if isinstance(name, Refusal):
            return name
        out["participant"] = str(name).strip()
    if args.get("inn") not in (None, ""):
        inn = parse_inn(args["inn"], tool, "inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        out["inn"] = inn
    if args.get("case_number") not in (None, ""):
        case = _parse_arbitrazh(args["case_number"], tool, "case_number")
        if isinstance(case, Refusal):
            return case
        out["case_number"] = case
    return out

ARBITRATION_CASE_SEARCH = ToolSpec(
    name='arbitration_case_search',
    source='https://kad.arbitr.ru/',
    schema=_schema('arbitration_case_search', 'Картотека арбитражных дел kad.arbitr.ru — поиск по участнику (наименование/ИНН) и номеру дела',
        {'participant': {'type': 'string', 'description': 'NAME'}, 'inn': {'type': 'string', 'description': 'INN'}, 'case_number': {'type': 'string', 'description': 'COURT_CASE_NUMBER'}},
        ()),
    fields=(
            FieldSpec('participant', "identity", 'NAME', '', required=False),
            FieldSpec('inn', "identity", 'INN', '', required=False),
            FieldSpec('case_number', "identity", 'ARBITRAZH_CASE_NO', '', required=False),
    ),
    parse=_arbitration_case_search_parse, mutating=False,
    result_pii=('cases[].number', 'cases[].respondent.name', 'cases[].respondent.inn', 'cases[].respondent.ogrnip', 'cases[].respondent.address'))


# --- probate_case_search (search, legal, evidence=summary, mutating=False) ---
def _probate_case_search_parse(args):
    tool = "probate_case_search"
    miss = _required(args, tool, "", ("fio",))
    if miss:
        return miss
    fio = parse_text(args["fio"], tool, "fio", 120)
    if isinstance(fio, Refusal):
        return fio
    if not fio.strip():
        return Refusal(tool, "fio", "name_format", str(fio))
    out = {"fio": fio.strip()}
    for key in ("birth_date", "death_date"):
        if args.get(key) not in (None, ""):
            value = _parse_date_iso(args[key], tool, key)
            if isinstance(value, Refusal):
                return value
            out[key] = value
    return out

PROBATE_CASE_SEARCH = ToolSpec(
    name='probate_case_search',
    source='https://xn--80aaxsfnme.xn--p1ai/ru-ru/help/probate-cases/',
    schema=_schema('probate_case_search', 'Федеральная нотариальная палата — Реестр наследственных дел (notariat.ru/ru-ru/help/probate-cases/)',
        {'fio': {'type': 'string', 'description': 'NAME'}, 'birth_date': {'type': 'string', 'description': 'DOB'}, 'death_date': {'type': 'string', 'description': 'DEATH_DATE'}},
        ('fio',)),
    fields=(
            FieldSpec('fio', "identity", 'NAME', '', required=True),
            FieldSpec('birth_date', "identity", 'DOB', '', required=False),
            FieldSpec('death_date', "plain", required=False),
    ),
    parse=_probate_case_search_parse, mutating=False,
    result_pii=('cases[].deceased', 'cases[].birth_date', 'cases[].death_date', 'cases[].case_number'))


# --- fns_inn_lookup (government, government_services, evidence=summary, mutating=False) ---
def _fns_inn_lookup_parse(args):
    tool = "fns_inn_lookup"
    miss = _required(args, tool, "", ("fam", "nam", "bdate", "doctype", "docno"))
    if miss:
        return miss
    fam = parse_name_word(args["fam"], tool, "fam")
    nam = parse_name_word(args["nam"], tool, "nam")
    bdate = _parse_dmy(args["bdate"], tool, "bdate")
    doctype = str(args["doctype"]).strip()
    if not doctype:
        return Refusal(tool, "doctype", "missing_required", doctype)
    docno = _digits_spaceless(args["docno"], tool, "docno", 10, "passport_format")
    bad = _first(fam, nam, bdate, docno)
    if bad:
        return bad
    out = {"fam": fam, "nam": nam, "bdate": bdate, "doctype": doctype, "docno": docno}
    if args.get("otch") not in (None, ""):
        otch = parse_name_word(args["otch"], tool, "otch")
        if isinstance(otch, Refusal):
            return otch
        out["otch"] = otch
    if args.get("docdt") not in (None, ""):
        docdt = _parse_dmy(args["docdt"], tool, "docdt")
        if isinstance(docdt, Refusal):
            return docdt
        out["docdt"] = docdt
    return out

FNS_INN_LOOKUP = ToolSpec(
    name='fns_inn_lookup',
    source='https://gist.github.com/nalgeon/547e95d4f6b7a8b06bcdc9de3c87856a',
    schema=_schema('fns_inn_lookup', 'ФНС «Узнать ИНН» (service.nalog.ru/inn.do → inn-proc.do)',
        {'fam': {'type': 'string', 'description': 'NAME (surname)'}, 'nam': {'type': 'string', 'description': 'NAME (given)'}, 'otch': {'type': 'string', 'description': 'NAME (patronymic)'}, 'bdate': {'type': 'string', 'description': 'DOB — DD.MM.YYYY'}, 'doctype': {'type': 'string', 'description': 'значение из закрытого списка'}, 'docno': {'type': 'string', 'description': 'PASSPORT — «45 01 123456»'}, 'docdt': {'type': 'string', 'description': 'строка'}},
        ('fam', 'nam', 'bdate', 'doctype', 'docno')),
    fields=(
            FieldSpec('fam', "identity", 'NAME', 'surname', required=True),
            FieldSpec('nam', "identity", 'NAME', 'given', required=True),
            FieldSpec('otch', "identity", 'NAME', 'patronymic', required=False),
            FieldSpec('bdate', "identity", 'DOB', '', required=True),
            FieldSpec('doctype', 'enum', required=True),
            FieldSpec('docno', "identity", 'PASSPORT', '', required=True),
            FieldSpec('docdt', 'plain', required=False),
    ),
    parse=_fns_inn_lookup_parse, mutating=False,
    result_pii=('inn',))


# --- npd_status_check (government, government_services, evidence=primary, mutating=False) ---
def _npd_status_check_parse(args):
    tool = "npd_status_check"
    miss = _required(args, tool, "", ("inn", "requestDate"))
    if miss:
        return miss
    inn = parse_inn(args["inn"], tool, "inn", (12,))
    req = _parse_date_iso(args["requestDate"], tool, "requestDate")
    bad = _first(inn, req)
    if bad:
        return bad
    return {"inn": inn, "requestDate": req}

NPD_STATUS_CHECK = ToolSpec(
    name='npd_status_check',
    source='https://npd.nalog.ru/html/sites/www.npd.nalog.ru/api_statusnpd_nalog_ru.pdf',
    schema=_schema('npd_status_check', 'ФНС «Проверка статуса налогоплательщика налога на профессиональный доход» POST /api/v1/tracker/taxpayer_status',
        {'inn': {'type': 'string', 'description': 'INN — 12 digits'}, 'requestDate': {'type': 'string', 'description': 'YYYY-MM-DD'}},
        ('inn', 'requestDate')),
    fields=(
            FieldSpec('inn', "identity", 'INN', '', required=True),
            FieldSpec('requestDate', 'plain', required=True),
    ),
    parse=_npd_status_check_parse, mutating=False,
    result_pii=('message',))


# --- budget_charges_find (government, government_services, evidence=summary, mutating=False) ---
def _budget_charges_find_parse(args):
    tool = "budget_charges_find"
    keys = [k for k in ("payer_snils", "payer_inn", "payer_passport")
            if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    if keys[0] == "payer_snils":
        snils = _parse_snils_bare(args["payer_snils"], tool, "payer_snils")
        if isinstance(snils, Refusal):
            return snils
        return {"payer_snils": snils}
    if keys[0] == "payer_inn":
        inn = parse_inn(args["payer_inn"], tool, "payer_inn", (10, 12))
        if isinstance(inn, Refusal):
            return inn
        return {"payer_inn": inn}
    passport = _digits_spaceless(args["payer_passport"], tool, "payer_passport",
                                 10, "passport_format")
    if isinstance(passport, Refusal):
        return passport
    return {"payer_passport": passport}

BUDGET_CHARGES_FIND = ToolSpec(
    name='budget_charges_find',
    source='https://roskazna.gov.ru/gis/…/pro-oplatu-shtrafov/',
    schema=_schema('budget_charges_find', 'ГИС ГМП — начисления по идентификатору плательщика (СНИЛС / ИНН / документ), через банк-участник или Госуслуги',
        {'payer_snils': {'type': 'string', 'description': 'SNILS'}, 'payer_inn': {'type': 'string', 'description': 'INN'}, 'payer_passport': {'type': 'string', 'description': 'PASSPORT'}},
        ()),
    fields=(
            FieldSpec('payer_snils', "identity", 'SNILS', '', required=False),
            FieldSpec('payer_inn', "identity", 'INN', '', required=False),
            FieldSpec('payer_passport', "identity", 'PASSPORT', '', required=False),
    ),
    parse=_budget_charges_find_parse, mutating=False,
    result_pii=('charges[].uin', 'charges[].payer_name', 'charges[].payer_identifier'))


# --- diploma_registry_check (government, education, evidence=summary, mutating=False) ---
def _diploma_registry_check_parse(args):
    tool = "diploma_registry_check"
    miss = _required(args, tool, "", ("last_name", "blank_series", "blank_number"))
    if miss:
        return miss
    last = parse_name_word(args["last_name"], tool, "last_name")
    series = _digits_spaceless(args["blank_series"], tool, "blank_series", 6, "series_format")
    number = _digits_spaceless(args["blank_number"], tool, "blank_number", 7, "number_format")
    bad = _first(last, series, number)
    if bad:
        return bad
    out = {"last_name": last, "blank_series": series, "blank_number": number}
    if args.get("issue_date") not in (None, ""):
        issued = _parse_date_iso(args["issue_date"], tool, "issue_date")
        if isinstance(issued, Refusal):
            return issued
        out["issue_date"] = issued
    return out

DIPLOMA_REGISTRY_CHECK = ToolSpec(
    name='diploma_registry_check',
    source='https://obrnadzor.gov.ru/…/formirovanie-i-vedenie-federalnogo-reestra…/',
    schema=_schema('diploma_registry_check', 'Рособрнадзор, ФИС ФРДО — сервис поиска сведений о документах об образовании (frdocheck.obrnadzor.gov.ru)',
        {'last_name': {'type': 'string', 'description': 'NAME (surname)'}, 'blank_series': {'type': 'string', 'description': 'DIPLOMA_NUMBER (series)'}, 'blank_number': {'type': 'string', 'description': 'DIPLOMA_NUMBER (number)'}, 'issue_date': {'type': 'string', 'description': 'строка'}},
        ('last_name', 'blank_series', 'blank_number')),
    fields=(
            FieldSpec('last_name', "identity", 'NAME', 'surname', required=True),
            FieldSpec('blank_series', "identity", 'DIPLOMA_NUMBER', 'series', required=True),
            FieldSpec('blank_number', "identity", 'DIPLOMA_NUMBER', 'number', required=True),
            FieldSpec('issue_date', 'plain', required=False),
    ),
    parse=_diploma_registry_check_parse, mutating=False,
    result_pii=('document.series', 'document.number', 'document.reg_number', 'document.holder', 'error.subject'))


# --- exam_results_check (government, education, evidence=summary, mutating=False) ---
def _exam_results_check_parse(args):
    tool = "exam_results_check"
    miss = _required(args, tool, "", ("fio", "region"))
    if miss:
        return miss
    fio = parse_text(args["fio"], tool, "fio", 200)
    region = str(args["region"]).strip()
    if not region:
        return Refusal(tool, "region", "missing_required", region)
    keys = [k for k in ("document_number", "reg_code") if args.get(k) not in (None, "")]
    if len(keys) != 1:
        return Refusal(tool, "", "exactly_one_key", ", ".join(keys))
    out = {"fio": str(fio).strip(), "region": region}
    if keys[0] == "document_number":
        docno = _digits_spaceless(args["document_number"], tool, "document_number",
                                  6, "passport_number_format")
        if isinstance(docno, Refusal):
            return docno
        out["document_number"] = docno
    else:
        out["reg_code"] = str(args["reg_code"]).strip()
    return out

EXAM_RESULTS_CHECK = ToolSpec(
    name='exam_results_check',
    source='https://checkege.rustest.ru/',
    schema=_schema('exam_results_check', 'ФИС ГИА и приёма — официальный сервис ознакомления с результатами ЕГЭ (checkege.rustest.ru)',
        {'fio': {'type': 'string', 'description': 'NAME'}, 'region': {'type': 'string', 'description': 'строка'}, 'document_number': {'type': 'string', 'description': 'PASSPORT (number)'}, 'reg_code': {'type': 'string', 'description': 'EXAM_REG_CODE'}},
        ('fio', 'region')),
    fields=(
            FieldSpec('fio', "identity", 'NAME', '', required=True),
            FieldSpec('region', 'plain', required=True),
            FieldSpec('document_number', "identity", 'PASSPORT', 'number', required=False),
            FieldSpec('reg_code', "plain", required=False),
    ),
    parse=_exam_results_check_parse, mutating=False,
    result_pii=('participant',))


# --- lms_user_get (directory, education, evidence=primary, mutating=False) ---
def _lms_user_get_parse(args):
    tool = "lms_user_get"
    miss = _required(args, tool, "", ("field", "values"))
    if miss:
        return miss
    field = str(args["field"]).strip().lower()
    if field not in ("email", "idnumber", "username", "id"):
        return Refusal(tool, "field", "field_enum", field)
    values = args["values"]
    if not isinstance(values, list) or not values:
        return Refusal(tool, "values", "missing_required", str(values))
    out_values = []
    for index, one in enumerate(values):
        value = str(one).strip()
        if not value:
            return Refusal(tool, f"values[{index}]", "missing_required", str(one))
        out_values.append(value)
    return {"field": field, "values": out_values}

LMS_USER_GET = ToolSpec(
    name='lms_user_get',
    source='https://docs.moodle.org/dev/Web_service_API_functions',
    schema=_schema('lms_user_get', 'Moodle Web Services core_user_get_users_by_field (вузы и колледжи РФ)',
        {'field': {'type': 'string', 'description': 'значение из закрытого списка'}, 'values': {'type': 'string', 'description': 'STUDENT_ID'}},
        ('field', 'values')),
    fields=(
            FieldSpec('field', 'enum', required=True),
            FieldSpec('values', "identity", 'STUDENT_ID_NUMBER', '', required=True),
    ),
    parse=_lms_user_get_parse, mutating=False,
    result_pii=('[].firstname', '[].lastname', '[].email', '[].idnumber', '[].phone1', '[].username'))


# --- dwh_sql_query (files, internal_bi, evidence=summary, mutating=False) ---
def _dwh_sql_query_parse(args):
    tool = "dwh_sql_query"
    miss = _required(args, tool, "", ("sql",))
    if miss:
        return miss
    sql = parse_text(args["sql"], tool, "sql", 20000)
    if isinstance(sql, Refusal):
        return sql
    if not sql.strip():
        return Refusal(tool, "sql", "sql_not_select", str(sql))
    out = {"sql": sql.strip()}
    if args.get("limit") not in (None, ""):
        limit = parse_int(args["limit"], tool, "limit", 1, 100000)
        if isinstance(limit, Refusal):
            return limit
        out["limit"] = limit
    return out

DWH_SQL_QUERY = ToolSpec(
    name='dwh_sql_query',
    source='https://clickhouse.com/docs/interfaces/formats/JSON',
    schema=_schema('dwh_sql_query', 'ClickHouse HTTP interface, FORMAT JSON (meta / data / rows / statistics); то же — Postgres/Greenplum через BI-шлюз',
        {'sql': {'type': 'string', 'description': 'свободный текст'}, 'limit': {'type': 'string', 'description': 'строка'}},
        ('sql',)),
    fields=(
            FieldSpec('sql', 'free', required=True),
            FieldSpec('limit', 'plain', required=False),
    ),
    parse=_dwh_sql_query_parse, mutating=False,
    result_pii=('data[].client_fio', 'data[].phone', 'data[].inn', 'exception'))


# --- bi_chart_export (files, internal_bi, evidence=summary, mutating=False) ---
def _bi_chart_export_parse(args):
    tool = "bi_chart_export"
    miss = _required(args, tool, "", ("chart_id", "result_format"))
    if miss:
        return miss
    chart_id = _parse_opaque_id(args["chart_id"], tool, "chart_id")
    result_format = str(args["result_format"]).strip().lower()
    if result_format not in ("csv", "json", "xlsx"):
        return Refusal(tool, "result_format", "format_enum", result_format)
    out = {"chart_id": chart_id, "result_format": result_format}
    filters = args.get("filters")
    if filters is not None and filters != []:
        if not isinstance(filters, list):
            return Refusal(tool, "filters", "object_required", str(filters))
        out["filters"] = filters
    return out

BI_CHART_EXPORT = ToolSpec(
    name='bi_chart_export',
    source='https://github.com/apache/superset/discussions/33574',
    schema=_schema('bi_chart_export', 'Apache Superset REST API POST /api/v1/chart/data (result_format csv|json) / Yandex DataLens export',
        {'chart_id': {'type': 'string', 'description': 'строка'}, 'filters[].val': {'type': 'string', 'description': 'свободный текст'}, 'result_format': {'type': 'string', 'description': 'значение из закрытого списка'}},
        ('chart_id', 'result_format')),
    fields=(
            FieldSpec('chart_id', 'plain', required=True),
            FieldSpec('filters[].val', 'free', required=False),
            FieldSpec('result_format', 'enum', required=True),
    ),
    parse=_bi_chart_export_parse, mutating=False,
    result_pii=('result[].data[].manager', 'result[].data[].client', 'result[].data[].phone', 'text'))


# --- audience_segment_upload (crm, marketing_cdp, evidence=summary, mutating=True) ---
def _audience_segment_upload_parse(args):
    tool = "audience_segment_upload"
    miss = _required(args, tool, "", ("segment_name", "file", "hashed"))
    if miss:
        return miss
    segment_name = parse_text(args["segment_name"], tool, "segment_name", 200)
    hashed = str(args["hashed"]).strip().lower()
    if hashed not in ("true", "false"):
        return Refusal(tool, "hashed", "hash_length", hashed)
    file = _obj(args["file"], tool, "file")
    if isinstance(file, Refusal):
        return file
    rows = file.get("rows")
    if not isinstance(rows, list) or len(rows) < 100:
        return Refusal(tool, "file.rows", "too_few_rows", str(len(rows) if isinstance(rows, list) else 0))
    out_rows = []
    for index, entry in enumerate(rows):
        block = _obj(entry, tool, f"file.rows[{index}]")
        if isinstance(block, Refusal):
            return block
        row = {}
        if block.get("phone") not in (None, ""):
            phone = _parse_phone_digits(block["phone"], tool, f"file.rows[{index}].phone")
            if isinstance(phone, Refusal):
                return phone
            row["phone"] = phone
        if block.get("email") not in (None, ""):
            email = str(block["email"]).strip().lower()
            if not EMAIL_RE.fullmatch(email):
                return Refusal(tool, f"file.rows[{index}].email", "email_lowercase", str(block["email"]))
            row["email"] = email
        if block.get("external_id") not in (None, ""):
            row["external_id"] = str(block["external_id"]).strip()
        out_rows.append(row)
    return {"segment_name": str(segment_name).strip(),
            "file": {"rows": out_rows}, "hashed": hashed == "true"}

AUDIENCE_SEGMENT_UPLOAD = ToolSpec(
    name='audience_segment_upload',
    source='https://yandex.ru/support2/audience/ru/segments/create-from-file',
    schema=_schema('audience_segment_upload', 'Яндекс Аудитории API — segments/upload_csv_file (phone, email, external_id; хеш SHA-256)',
        {'segment_name': {'type': 'string', 'description': 'строка'}, 'file.rows[].phone': {'type': 'string', 'description': 'PHONE (digits)'}, 'file.rows[].email': {'type': 'string', 'description': 'EMAIL'}, 'file.rows[].external_id': {'type': 'string', 'description': 'CLIENT_ID'}, 'hashed': {'type': 'string', 'description': 'значение из закрытого списка'}},
        ('segment_name', 'hashed')),
    fields=(
            FieldSpec('segment_name', 'plain', required=True),
            FieldSpec('file.rows[].phone', "identity", 'PHONE', 'digits', required=False),
            FieldSpec('file.rows[].email', "identity", 'EMAIL', '', required=False),
            FieldSpec('file.rows[].external_id', "identity", 'CDP_CUSTOMER_ID', '', required=False),
            FieldSpec('hashed', 'enum', required=True),
    ),
    parse=_audience_segment_upload_parse, mutating=True,
    result_pii=('errors[].message',))


# --- email_contacts_import (messaging, marketing_cdp, evidence=primary, mutating=True) ---
def _email_contacts_import_parse(args):
    tool = "email_contacts_import"
    miss = _required(args, tool, "", ("field_names", "data"))
    if miss:
        return miss
    field_names = args["field_names"]
    if not isinstance(field_names, list) or not field_names:
        return Refusal(tool, "field_names", "field_names_mismatch", str(field_names))
    if "email" not in [str(f).lower() for f in field_names]:
        return Refusal(tool, "field_names", "field_names_mismatch", str(field_names))
    data = args["data"]
    if not isinstance(data, list) or not data:
        return Refusal(tool, "data", "missing_required", str(data))
    if len(data) > IMPORT_MAX_CONTACTS:
        return Refusal(tool, "data", "too_many_rows", str(len(data)))
    rows = []
    for index, row in enumerate(data):
        if not isinstance(row, list) or not row:
            return Refusal(tool, f"data[{index}]", "missing_required", str(row))
        email = row[0] if len(row) > 0 else ""
        if not isinstance(email, str) or not EMAIL_RE.fullmatch(email.strip().lower()):
            return Refusal(tool, f"data[{index}][0]", "email_format", str(email))
        phone = row[1] if len(row) > 1 else ""
        name = row[2] if len(row) > 2 else ""
        rows.append({"email": email.strip().lower(),
                     "phone": str(phone).strip(), "name": str(name).strip()})
    return {"field_names": field_names, "data": rows}

EMAIL_CONTACTS_IMPORT = ToolSpec(
    name='email_contacts_import',
    source='https://www.unisender.com/ru/support/api/contacts/importcontacts/',
    schema=_schema('email_contacts_import', 'Unisender API importContacts (field_names[], data[][])',
        {'field_names': {'type': 'string', 'description': 'строка'}, 'data[][0]': {'type': 'string', 'description': 'EMAIL'}, 'data[][1]': {'type': 'string', 'description': 'PHONE'}, 'data[][2]': {'type': 'string', 'description': 'NAME'}},
        ('field_names', 'data[][0]')),
    fields=(
            FieldSpec('field_names', 'plain', required=True),
            FieldSpec('data[][0]', "identity", 'EMAIL', '', required=True),
            FieldSpec('data[][1]', "identity", 'PHONE', '', required=False),
            FieldSpec('data[][2]', "identity", 'NAME', '', required=False),
    ),
    parse=_email_contacts_import_parse, mutating=True,
    result_pii=('rows[].email', 'rows[].phone', 'rows[].name'))


# --- web_visits_export (files, marketing_cdp, evidence=primary, mutating=False) ---
def _web_visits_export_parse(args):
    tool = "web_visits_export"
    miss = _required(args, tool, "", ("counter_id", "date1", "date2", "fields"))
    if miss:
        return miss
    counter_id = str(args["counter_id"]).strip()
    if not counter_id.isdigit():
        return Refusal(tool, "counter_id", "fields_unknown", counter_id)
    date1 = _parse_date_iso(args["date1"], tool, "date1")
    date2 = _parse_date_iso(args["date2"], tool, "date2")
    fields = str(args["fields"]).strip()
    if not fields:
        return Refusal(tool, "fields", "fields_unknown", fields)
    bad = _first(date1, date2)
    if bad:
        return bad
    return {"counter_id": counter_id, "date1": date1, "date2": date2, "fields": fields}

WEB_VISITS_EXPORT = ToolSpec(
    name='web_visits_export',
    source='https://yandex.ru/support/metrica/ru/pro/visits',
    schema=_schema('web_visits_export', 'Яндекс Метрика Logs API — выгрузка визитов (ClientID, ClientIP, UserIDHash, ParsedParams)',
        {'counter_id': {'type': 'string', 'description': 'строка'}, 'date1': {'type': 'string', 'description': 'строка'}, 'date2': {'type': 'string', 'description': 'строка'}, 'fields': {'type': 'string', 'description': 'строка'}},
        ('counter_id', 'date1', 'date2', 'fields')),
    fields=(
            FieldSpec('counter_id', 'plain', required=True),
            FieldSpec('date1', 'plain', required=True),
            FieldSpec('date2', 'plain', required=True),
            FieldSpec('fields', 'plain', required=True),
    ),
    parse=_web_visits_export_parse, mutating=False,
    result_pii=('text',))


# --- fssp_proceedings_search (banks_mfo_collectors, evidence=secondary, api closed) ---
def _fssp_proceedings_search_parse(args):
    tool = "fssp_proceedings_search"
    miss = _required(args, tool, "", ("region", "last_name", "first_name"))
    if miss:
        return miss
    region = str(args["region"]).strip()
    if not region:
        return Refusal(tool, "region", "missing_required", region)
    last = parse_name_word(args["last_name"], tool, "last_name")
    first = parse_name_word(args["first_name"], tool, "first_name")
    bad = _first(last, first)
    if bad:
        return bad
    out = {"region": region, "last_name": last, "first_name": first}
    if args.get("middle_name") not in (None, ""):
        mid = parse_name_word(args["middle_name"], tool, "middle_name")
        if isinstance(mid, Refusal):
            return mid
        out["middle_name"] = mid
    if args.get("birth_date") not in (None, ""):
        birth = _parse_dmy(args["birth_date"], tool, "birth_date")
        if isinstance(birth, Refusal):
            return birth
        out["birth_date"] = birth
    return out

FSSP_PROCEEDINGS_SEARCH = ToolSpec(
    name='fssp_proceedings_search',
    source='https://habr.com/ru/articles/648321/ (api-ip.fssp.gov.ru/about — HTTP 410 Gone 2026-09-24)',
    schema=_schema('fssp_proceedings_search', 'ФССП «Банк данных исполнительных производств» — search/physical (api-ip.fssp.gov.ru, ЗАКРЫТ); живые пути: веб-форма fssp.gov.ru/iss/ip и межведомственный обмен ФССП↔банки',
        {'region': {'type': 'string', 'description': 'строка'}, 'last_name': {'type': 'string', 'description': 'NAME (surname)'}, 'first_name': {'type': 'string', 'description': 'NAME (given)'}, 'middle_name': {'type': 'string', 'description': 'NAME (patronymic)'}, 'birth_date': {'type': 'string', 'description': 'DOB — DD.MM.YYYY'}},
        ('region', 'last_name', 'first_name')),
    fields=(
            FieldSpec('region', 'plain', required=True),
            FieldSpec('last_name', "identity", 'NAME', 'surname', required=True),
            FieldSpec('first_name', "identity", 'NAME', 'given', required=True),
            FieldSpec('middle_name', "identity", 'NAME', 'patronymic', required=False),
            FieldSpec('birth_date', "identity", 'DOB', '', required=False),
    ),
    parse=_fssp_proceedings_search_parse, mutating=False,
    result_pii=('result[].name', 'result[].exe_production', 'result[].details'))


# --- court_document_fetch (legal, evidence=summary, synthetic) ---
def _court_document_fetch_parse(args):
    tool = "court_document_fetch"
    miss = _required(args, tool, "", ("court", "case_number"))
    if miss:
        return miss
    court = str(args["court"]).strip()
    if not court:
        return Refusal(tool, "court", "missing_required", court)
    case = _parse_court_case_sou(args["case_number"], tool, "case_number")
    if isinstance(case, Refusal):
        return case
    return {"court": court, "case_number": case}

COURT_DOCUMENT_FETCH = ToolSpec(
    name='court_document_fetch',
    source='https://sudrf.ru/',
    schema=_schema('court_document_fetch', 'ГАС «Правосудие» / sudrf.ru — текст судебного акта (обезличенный при публикации) и карточка дела',
        {'court': {'type': 'string', 'description': 'строка'}, 'case_number': {'type': 'string', 'description': 'COURT_CASE_NO_SOU'}},
        ('court', 'case_number')),
    fields=(
            FieldSpec('court', 'plain', required=True),
            FieldSpec('case_number', "identity", 'COURT_CASE_NO_SOU', '', required=True),
    ),
    parse=_court_document_fetch_parse, mutating=False,
    result_pii=('text',))


# --- esia_roles_get (government_services, evidence=primary) ---
def _esia_roles_get_parse(args):
    tool = "esia_roles_get"
    miss = _required(args, tool, "", ("prn_oid",))
    if miss:
        return miss
    oid = _parse_esia_oid(args["prn_oid"], tool, "prn_oid")
    if isinstance(oid, Refusal):
        return oid
    return {"prn_oid": oid}

ESIA_ROLES_GET = ToolSpec(
    name='esia_roles_get',
    source='ЕСИА, Методические рекомендации v2.5 (rulaws.ru) — REST rs/prns/{prn_oid}/roles; '
           '"personOid" — идентификатор зарегистрированной учётной записи',
    schema=_schema('esia_roles_get', 'ЕСИА REST API — роли учётной записи по prn_oid; возвращает personOid',
        {'prn_oid': {'type': 'string', 'description': 'ESIA_OID — цифры'}},
        ('prn_oid',)),
    fields=(FieldSpec('prn_oid', "identity", 'ESIA_OID', '', required=True),),
    parse=_esia_roles_get_parse, mutating=False,
    result_pii=('personOid',))


TOOLS_V6: tuple[ToolSpecV5, ...] = (
    ToolSpecV5(base=CRM_REQUISITE_GET, vertical='crm',
               return_forms=(
                   _form('single', '{"requisite":{"id":7,"rq_inn":"500100732259","rq_ogrnip":"312345678901230","rq_iban":"RU0304452522540817810538091310419","rq_ident_doc_ser":"4509","rq_ident_doc_num":"123456"}}', ('requisite.rq_inn', 'requisite.rq_ogrnip', 'requisite.rq_iban', 'requisite.rq_ident_doc_ser', 'requisite.rq_ident_doc_num')),
                   _form('empty', '{"requisites":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=CRM_REQUISITE_SET, vertical='crm',
               return_forms=(
                   _form('single', '{"requisite":{"id":7,"rq_inn":"500100732259","rq_ogrnip":"312345678901230","rq_iban":"RU0304452522540817810538091310419","rq_ident_doc_ser":"4509","rq_ident_doc_num":"123456"}}', ('requisite.rq_inn', 'requisite.rq_ogrnip', 'requisite.rq_iban', 'requisite.rq_ident_doc_ser', 'requisite.rq_ident_doc_num')),
                   _form('error_with_value', '{"error":{"code":"inn_checksum","subject":"500100732259"}}', ('error.subject',))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=CRM_CONTACT_UPSERT, vertical='crm',
               return_forms=(
                   _form('nested', '{"contact":{"id":"c-77","first_name":"марина","last_name":"громова","custom_fields_values":[{"field_id":10001,"values":[{"value":"+79164021187","enum_code":"WORK"}]}]}}', ('contact.first_name', 'contact.last_name', 'contact.custom_fields_values[].values[].value')),
                   _form('error_with_value', '{"error":{"code":"name_cyrillic","subject":"громова"}}', ('error.subject',))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PHONE_CLEAN, vertical='directory',
               return_forms=(
                   _form('canon', '{"items":[{"source":"8 (916) 402-11-87","phone":"+7 916 402-11-87","number":"79164021187","provider":"МТС","qc":0}]}', ('items[].phone',)),
                   _form('empty', '{"items":[]}', ())),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=RECEIPT_CREATE, vertical='bank',
               return_forms=(
                   _form('single', '{"receipt":{"id":"rt-1","status":"succeeded","customer":{"full_name":"Павлова Тамара","email":"pavlova@mail.ru","phone":"79164021187","inn":"500100732259"}}}', ('receipt.customer.full_name', 'receipt.customer.email', 'receipt.customer.phone', 'receipt.customer.inn')),
                   _form('error_with_value', '{"error":{"code":"contact_required","subject":"Павлова Тамара"}}', ('error.subject',))),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=SMS_SEND, vertical='messaging',
               return_forms=(
                   _form('single', '{"message_id":"sms-1","status":"queued","destination":"+79164021187"}', ('destination',)),
                   _form('error_with_value', '{"error":{"code":"RECIPIENT_REJECTED","subject":"+79164021187"}}', ('error.subject',))),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=BANK_ACCOUNTS_LIST, vertical='bank',
               return_forms=(
                   _form('list',
                         '{"Data":{"Account":[{"accountId":"acc-1","currency":"RUB","accountType":"Personal","AccountDetails":[{"schemeName":"RU.CBR.BBAN","identification":"40817810099910004312","name":"ГРОМОВА МАРИНА БОРИСОВНА"}],"Servicer":{"schemeName":"RU.CBR.BIC","identification":"044525225"}}]}}',
                         ('Data.Account[].AccountDetails[].identification', 'Data.Account[].AccountDetails[].name')),
                   _form('empty',
                         '{"Data":{"Account":[]}}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=RUBLE_TRANSFER_CREATE, vertical='bank',
               return_forms=(
                   _form('single',
                         '{"paymentId":"p-1","status":"IN_PROGRESS","recipient":{"name":"Громова Марина Борисовна","account":"40817810099910004312"}}',
                         ('recipient.name', 'recipient.account')),
                   _form('error_with_value',
                         '{"errorCode":"ACCOUNT_KEY_MISMATCH","errorMessage":"Счёт 40817810099910004313 не соответствует БИК 044525225"}',
                         ('errorMessage',)),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=CREDIT_REPORT_REQUEST, vertical='bank',
               return_forms=(
                   _form('nested',
                         '{"subject":{"name":"ГРОМОВА МАРИНА БОРИСОВНА","birth_date":"1987-03-14","passport":"4507 443564"},"contracts":[{"uid":"3f2b6c1e-0d4a-4b7e-9a51-2c8f0e7d1a93-7","creditor":"МФК «Пример»","opened":"2025-11-02","overdue_days":"47"}],"self_ban":false}',
                         ('subject.name', 'subject.birth_date', 'subject.passport', 'contracts[].uid')),
                   _form('empty',
                         '{"subject":null,"contracts":[]}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DEBTOR_CARD_GET, vertical='crm',
               return_forms=(
                   _form('nested',
                         '{"debtor":{"fio":"Громова Марина Борисовна","birth_date":"14.03.1987","phones":["+7 916 402-11-87"],"reg_address":"Удмуртская Респ, г Ижевск, ул Клубная, д 85, кв 12"},"loan":{"contract":"МЗ-2025/118804","uid":"3f2b6c1e-0d4a-4b7e-9a51-2c8f0e7d1a93-7"},"third_parties":[{"fio":"Громов Олег Петрович","relation":"супруг","phone":"+7 912 555-40-10","consent":true}]}',
                         ('debtor.fio', 'debtor.birth_date', 'debtor.phones[]', 'debtor.reg_address', 'loan.contract', 'loan.uid', 'third_parties[].fio', 'third_parties[].phone')),
                   _form('error_with_value',
                         '{"error":"CONTRACT_NOT_FOUND","message":"Договор МЗ-2025/118805 не найден в портфеле"}',
                         ('message',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=ELN_GET, vertical='clinic',
               return_forms=(
                   _form('nested',
                         '{"status":"1","data":{"row":{"snils":"12345678964","surname":"ГРОМОВА","name":"МАРИНА","patronymic":"БОРИСОВНА","lnCode":"900000161887","lnDate":"2026-09-01","birthday":"1987-03-14","servFullData":{"surname":"ГРОМОВ","name":"ИЛЬЯ","birthday":"2019-05-20"},"treatDoctor":"СОКОЛОВ АА"}}}',
                         ('data.row.snils', 'data.row.surname', 'data.row.name', 'data.row.patronymic', 'data.row.lnCode', 'data.row.birthday', 'data.row.servFullData.surname', 'data.row.servFullData.name', 'data.row.servFullData.birthday')),
                   _form('empty',
                         '{"status":"1","data":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=REMD_DOCUMENTS_SEARCH, vertical='clinic',
               return_forms=(
                   _form('list',
                         '{"items":[{"emdr_id":"1.2.643.5.1.13.13.12.2.18.12345.100.1.1.51","kind":"Протокол консультации","document_number":"К-2026-00412","patient":{"snils":"12345678964","fio":"Громова Марина Борисовна","birth_date":"1987-03-14"},"creation_date_time":"2026-09-01T10:12:00+04:00"}],"has_next":false}',
                         ('items[].patient.snils', 'items[].patient.fio', 'items[].patient.birth_date', 'items[].document_number')),
                   _form('empty',
                         '{"items":[],"has_next":false}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=OMS_POLICY_FIND, vertical='clinic',
               return_forms=(
                   _form('single',
                         '{"person":{"fam":"ГРОМОВА","im":"МАРИНА","ot":"БОРИСОВНА","dr":"1987-03-14","enp":"1850000812345678","snils":"123-456-789 64"},"policy":{"smo":"АО «СК «Пример-Мед»","date_begin":"2021-02-01","status":"действующий"}}',
                         ('person.fam', 'person.im', 'person.ot', 'person.dr', 'person.enp', 'person.snils')),
                   _form('empty',
                         '{"person":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=E_PRESCRIPTION_CREATE, vertical='clinic',
               return_forms=(
                   _form('single',
                         '{"prescription":{"series":"18-26","number":"000412","issued":"2026-09-01","patient":{"fio":"Громова М. Б.","birth_date":"14.03.1987","oms_policy":"1850000812345678"}},"remd_status":"registered"}',
                         ('prescription.number', 'prescription.patient.fio', 'prescription.patient.birth_date', 'prescription.patient.oms_policy')),
                   _form('error_with_value',
                         '{"error":"PATIENT_POLICY_INVALID","message":"Полис 1850000812345679 не прошёл проверку контрольного разряда"}',
                         ('message',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=MARKETPLACE_ORDER_GET, vertical='delivery',
               return_forms=(
                   _form('nested',
                         '{"result":{"posting_number":"0123456789-0001-1","customer":{"name":"Марина Громова","phone":"","address":{"address_tail":"г. Ижевск, ул. Клубная, д. 85, кв. 12","city":"Ижевск","zip_code":"426034"}},"addressee":{"name":"Громова Марина","phone":""}}}',
                         ('result.customer.name', 'result.customer.address.address_tail', 'result.addressee.name')),
                   _form('single',
                         '{"orders":[{"orderID":1234567,"firstName":"Марина","fullName":"Громова Марина Борисовна","phone":"+79164021187","phoneCode":"1234"}]}',
                         ('orders[].firstName', 'orders[].fullName', 'orders[].phone')),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=LOYALTY_CUSTOMER_GET, vertical='crm',
               return_forms=(
                   _form('single',
                         '{"status":"Success","customer":{"processingStatus":"Found","lastName":"Громова","firstName":"Марина","middleName":"Борисовна","birthDate":"1987-03-14","mobilePhone":"79164021187","email":"m.gromova@example.ru","discountCards":[{"ids":{"number":"231534554262"}}]}}',
                         ('customer.lastName', 'customer.firstName', 'customer.middleName', 'customer.birthDate', 'customer.mobilePhone', 'customer.email', 'customer.discountCards[].ids.number')),
                   _form('empty',
                         '{"status":"Success","customer":{"processingStatus":"NotFound"}}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=LOYALTY_CARD_BIND, vertical='crm',
               return_forms=(
                   _form('single',
                         '{"status":"Success","customer":{"processingStatus":"Found"},"discountCard":{"processingStatus":"Bound","ids":{"number":"231534554262"}}}',
                         ('discountCard.ids.number',)),
                   _form('error_with_value',
                         '{"status":"Success","discountCard":{"processingStatus":"BoundToAnotherCustomer","ids":{"number":"231534554262"}}}',
                         ('discountCard.ids.number',)),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=FISCAL_RECEIPT_CREATE, vertical='bank',
               return_forms=(
                   _form('single',
                         '{"receipt":{"uuid":"4475d6d8-844d-4d05-aa8b-e3dbdf3defd5","client":{"name":"Громова Марина Борисовна","email":"m.gromova@example.ru","phone":"+79164021187","inn":"183101234567","birthdate":"14.03.1987","document_data":"4507 443564","address":"г. Ижевск, ул. Клубная, д. 85, кв. 12"}}}',
                         ('receipt.client.name', 'receipt.client.email', 'receipt.client.phone', 'receipt.client.inn', 'receipt.client.birthdate', 'receipt.client.document_data', 'receipt.client.address')),
                   _form('error_with_value',
                         '{"uuid":null,"status":"fail","error":{"error_id":"475d6d8d-844d-4d05-aa8b-e3dbdf4defd6","code":13,"text":"Ошибка валидации входящего запроса. Ошибочные поля : receipt.client.birthdate","type":"system"}}',
                         ()),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=CDEK_ORDER_INFO, vertical='delivery',
               return_forms=(
                   _form('nested',
                         '{"entity":{"uuid":"72753031-…","cdek_number":"1234567890","recipient":{"name":"Громова Марина Борисовна","passport_series":"9404","passport_number":"123456","passport_date_of_birth":"1987-03-14","tin":"183101234567","phones":[{"number":"+79164021187"}]},"to_location":{"city":"Ижевск","address":"ул. Клубная, 85, кв. 12"}}}',
                         ('entity.recipient.name', 'entity.recipient.passport_series', 'entity.recipient.passport_number', 'entity.recipient.passport_date_of_birth', 'entity.recipient.tin', 'entity.recipient.phones[].number', 'entity.to_location.address')),
                   _form('error_with_value',
                         '{"requests":[{"state":"INVALID","errors":[{"code":"v2_entity_not_found_im_number","message":"Заказ с номером 1234567891 не найден"}]}]}',
                         ('requests[].errors[].message',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=OSAGO_POLICY_CHECK, vertical='government',
               return_forms=(
                   _form('single',
                         '{"policy":{"series":"ХХХ","number":"0123456789","insurer":"СПАО «Пример»","status":"Действует","valid_from":"2026-02-01","valid_to":"2027-01-31"},"vehicle":{"plate":"Р777ТТ18","vin":"XTA210990Y2765432","model":"LADA 2109"}}',
                         ('policy.series', 'policy.number', 'vehicle.plate', 'vehicle.vin')),
                   _form('empty',
                         '{"policy":null,"message":"Сведения о договоре ОСАГО не найдены"}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=INSURANCE_CLAIM_CREATE, vertical='bank',
               return_forms=(
                   _form('single',
                         '{"claim_id":"У-2026-004512","status":"registered","applicant":{"fio":"Громова Марина Борисовна"},"policy":"ХХХ 0123456789"}',
                         ('applicant.fio', 'policy')),
                   _form('error_with_value',
                         '{"error":"POLICY_NOT_ACTIVE","message":"Договор ХХХ 0123456789 не действовал на дату ДТП"}',
                         ('message',)),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=TRAFFIC_FINES_CHECK, vertical='government',
               return_forms=(
                   _form('list',
                         '{"fines":[{"uin":"18810018260000123456","decision_date":"2026-08-14","amount":"500","koap":"12.9 ч.2","vehicle":"Р777ТТ18"}]}',
                         ('fines[].uin', 'fines[].vehicle')),
                   _form('empty',
                         '{"fines":[]}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EPTS_STATUS_GET, vertical='government',
               return_forms=(
                   _form('single',
                         '{"epts":"164301012345678","status":"действующий","vin":"XTA210990Y2765432","owner_type":"физическое лицо","restrictions":[]}',
                         ('epts', 'vin')),
                   _form('empty',
                         '{"epts":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DRIVER_LICENSE_CHECK, vertical='government',
               return_forms=(
                   _form('single',
                         '{"license":"9912345678","issued":"2019-06-11","valid_to":"2029-06-11","categories":"B, B1, M","deprivation":[]}',
                         ('license',)),
                   _form('error_with_value',
                         '{"code":"100","message":"Водительское удостоверение 9912345679 от 11.06.2019 не найдено"}',
                         ('message',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=SUBSCRIBER_PROFILE_GET, vertical='crm',
               return_forms=(
                   _form('nested',
                         '{"individual":{"familyName":"Громова","givenName":"Марина","middleName":"Борисовна","birthDate":"1987-03-14","individualIdentification":[{"identificationType":"passport","identificationId":"9404 123456"}]},"contract":{"number":"18-0412345","personalAccount":"418000123456"},"sim":{"msisdn":"79164021187","iccid":"8970101234567890123","imsi":"250011234567890"},"device":{"imei":"356938035643809"}}',
                         ('individual.familyName', 'individual.givenName', 'individual.middleName', 'individual.birthDate', 'individual.individualIdentification[].identificationId', 'contract.number', 'contract.personalAccount', 'sim.msisdn', 'sim.iccid', 'sim.imsi', 'device.imei')),
                   _form('empty',
                         '{"individual":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=SIM_REPLACE_REQUEST, vertical='support',
               return_forms=(
                   _form('single',
                         '{"request_id":"SR-2026-0912","status":"accepted","msisdn":"79164021187","iccid":"8970101234567890123"}',
                         ('msisdn', 'iccid')),
                   _form('error_with_value',
                         '{"error":"ICCID_INVALID","message":"ICCID 8970101234567890124 не прошёл проверку"}',
                         ('message',)),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=EGRN_EXTRACT_GET, vertical='government',
               return_forms=(
                   _form('nested',
                         '{"object":{"cadastral_number":"18:26:010203:1234","address":"Удмуртская Республика, г. Ижевск, ул. Клубная, д. 85, кв. 12","area":"54.3"},"rights":[{"holder":"Громова Марина Борисовна","birth_date":"14.03.1987","share":"1/2","reg_number":"18:26:010203:1234-18/051/2021-3"},{"holder":"Физическое лицо","share":"1/2","reg_number":"18:26:010203:1234-18/051/2021-4"}]}',
                         ('object.cadastral_number', 'object.address', 'rights[].holder', 'rights[].birth_date', 'rights[].reg_number')),
                   _form('empty',
                         '{"object":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=GIS_GKH_ACCOUNT_GET, vertical='government',
               return_forms=(
                   _form('single',
                         '{"account":{"els":"80АО337193","zhku_id":"80АО337193-01","personal_account":"1204567","address":"г. Ижевск, ул. Клубная, д. 85, кв. 12","payer":{"fio":"Громова М. Б.","snils":"123-456-789 64"}}}',
                         ('account.els', 'account.zhku_id', 'account.personal_account', 'account.address', 'account.payer.fio', 'account.payer.snils')),
                   _form('empty',
                         '{"account":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PMS_BOOKING_GET, vertical='calendar',
               return_forms=(
                   _form('nested',
                         '{"booking":{"id":"b-123456","arrival":"2026-09-20","departure":"2026-09-23","customer":{"name":"Марина","surname":"Громова","phone":"89164021187","email":"m.gromova@example.ru"},"guests":[{"surname":"Громов","name":"Олег","birthdate":"1985-07-02","document":{"type":"passport","series":"9404","number":"654321"}}]}}',
                         ('booking.customer.name', 'booking.customer.surname', 'booking.customer.phone', 'booking.customer.email', 'booking.guests[].surname', 'booking.guests[].name', 'booking.guests[].birthdate', 'booking.guests[].document.series', 'booking.guests[].document.number')),
                   _form('list',
                         '{"bookings":[{"id":"b-123456","customer":{"surname":"Громова","phone":"89164021187"}},{"id":"b-123457","customer":{"surname":"Громова","phone":"89123330011"}}]}',
                         ('bookings[].customer.surname', 'bookings[].customer.phone')),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=GUEST_ARRIVAL_NOTIFY, vertical='government',
               return_forms=(
                   _form('single',
                         '{"notification_id":"N-2026-18-004512","status":"sent","guest":{"fio":"IVANOVA ANNA","document":"FA1234567"}}',
                         ('guest.fio', 'guest.document')),
                   _form('error_with_value',
                         '{"status":"rejected","reason":"Срок пребывания по миграционной карте 4612 1234567 истёк"}',
                         ('reason',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=FLIGHT_ORDER_GET, vertical='calendar',
               return_forms=(
                   _form('nested',
                         '{"data":{"id":"eJzTd9f3NjIJdgYADN4CVg%3D%3D","associatedRecords":[{"reference":"2ZYVAL","originSystemCode":"1A"}],"travelers":[{"id":"1","dateOfBirth":"1987-03-14","name":{"firstName":"MARINA","lastName":"GROMOVA"},"documents":[{"documentType":"PASSPORT","number":"751234567","expiryDate":"2031-05-01","nationality":"RU"}],"contact":{"emailAddress":"m.gromova@example.ru","phones":[{"countryCallingCode":"7","number":"9164021187"}]}}]}}',
                         ('data.associatedRecords[].reference', 'data.travelers[].dateOfBirth', 'data.travelers[].name.firstName', 'data.travelers[].name.lastName', 'data.travelers[].documents[].number', 'data.travelers[].contact.emailAddress', 'data.travelers[].contact.phones[].number')),
                   _form('error_with_value',
                         '{"errors":[{"status":404,"code":1797,"title":"NOT FOUND","detail":"order with id 2ZYVAX not found"}]}',
                         ('errors[].detail',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=HR_EMPLOYEE_GET, vertical='crm',
               return_forms=(
                   _form('single',
                         '{"value":[{"Ref_Key":"5f1c…","Code":"0000-00412","Description":"Громова Марина Борисовна","ТабельныйНомер":"0000-00412","ФизическоеЛицо":{"ДатаРождения":"1987-03-14T00:00:00","ИНН":"183101234567","СтраховойНомерПФР":"123-456-789 64"}}]}',
                         ('value[].Description', 'value[].ТабельныйНомер', 'value[].ФизическоеЛицо.ДатаРождения', 'value[].ФизическоеЛицо.ИНН', 'value[].ФизическоеЛицо.СтраховойНомерПФР')),
                   _form('empty',
                         '{"value":[]}',
                         ()),
                   _form('error_with_value',
                         '{"error":{"code":"TAB_NOT_FOUND","subject":"Громова Марина Борисовна"}}',
                         ('error.subject',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=RESUME_GET, vertical='search',
               return_forms=(
                   _form('nested',
                         '{"id":"0123abcd","last_name":"Громова","first_name":"Марина","middle_name":"Борисовна","birth_date":"1987-03-14","area":{"name":"Ижевск"},"contact":[{"type":{"id":"cell"},"value":{"country":"7","city":"916","number":"4021187","formatted":"+7 (916) 402-11-87"}},{"type":{"id":"email"},"value":"m.gromova@example.ru"}]}',
                         ('last_name', 'first_name', 'middle_name', 'birth_date', 'contact[].value.formatted', 'contact[].value')),
                   _form('single',
                         '{"id":"0123abcd","last_name":null,"first_name":null,"birth_date":null,"contact":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PAYROLL_CARD_REGISTRY, vertical='bank',
               return_forms=(
                   _form('list',
                         '{"rows":[{"tab_number":"0000-00412","fio":"Громова Марина Борисовна","account":"40817810099910004312","status":"Открыт"}]}',
                         ('rows[].tab_number', 'rows[].fio', 'rows[].account', 'rows[].status')),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=ARBITRATION_CASE_SEARCH, vertical='search',
               return_forms=(
                   _form('list',
                         '{"cases":[{"number":"А71-12345/2025","court":"АС Удмуртской Республики","date":"2025-06-02","plaintiff":"ООО «Пример»","respondent":{"name":"ИП Громова Марина Борисовна","inn":"183101234567","ogrnip":"318183200012345","address":"г. Ижевск, ул. Клубная, д. 85, кв. 12"}}]}',
                         ('cases[].number', 'cases[].respondent.name', 'cases[].respondent.inn', 'cases[].respondent.ogrnip', 'cases[].respondent.address')),
                   _form('empty',
                         '{"cases":[]}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=PROBATE_CASE_SEARCH, vertical='search',
               return_forms=(
                   _form('list',
                         '{"cases":[{"deceased":"Громов Пётр Иванович","birth_date":"12.01.1941","death_date":"03.05.2026","case_number":"45/2026","notary":"Соколова Анна Викторовна","chamber":"Нотариальная палата Удмуртской Республики"}]}',
                         ('cases[].deceased', 'cases[].birth_date', 'cases[].death_date', 'cases[].case_number')),
                   _form('empty',
                         '{"cases":[]}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=FNS_INN_LOOKUP, vertical='government',
               return_forms=(
                   _form('single',
                         '{"code":1,"inn":"183101234567","captchaRequired":false}',
                         ('inn',)),
                   _form('empty',
                         '{"code":0,"captchaRequired":false}',
                         ()),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=NPD_STATUS_CHECK, vertical='government',
               return_forms=(
                   _form('single',
                         '{"status":true,"message":"183101234567 является плательщиком налога на профессиональный доход"}',
                         ('message',)),
                   _form('error_with_value',
                         '{"code":"validation.failed","message":"Указан некорректный ИНН"}',
                         ()),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=BUDGET_CHARGES_FIND, vertical='government',
               return_forms=(
                   _form('list',
                         '{"charges":[{"uin":"18209965264301234567","payee":"УФК по Удмуртской Республике (УФНС)","purpose":"Налог на имущество физических лиц","amount":"1840.00","payer_name":"ГРОМОВА МАРИНА БОРИСОВНА","payer_identifier":"1010000000094041234567"}]}',
                         ('charges[].uin', 'charges[].payer_name', 'charges[].payer_identifier')),
                   _form('empty',
                         '{"charges":[]}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DIPLOMA_REGISTRY_CHECK, vertical='government',
               return_forms=(
                   _form('single',
                         '{"found":true,"document":{"type":"Диплом бакалавра","series":"101805","number":"0123456","reg_number":"18-Б-0412","issued":"2009-06-30","holder":"Громова Марина Борисовна","organization":"ФГБОУ ВО «УдГУ»"}}',
                         ('document.series', 'document.number', 'document.reg_number', 'document.holder')),
                   _form('empty',
                         '{"found":false}',
                         ()),
                   _form('error_with_value',
                         '{"error":{"code":"DIPLOMA_NOT_FOUND","subject":"Громова Марина Борисовна"}}',
                         ('error.subject',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EXAM_RESULTS_CHECK, vertical='government',
               return_forms=(
                   _form('list',
                         '{"participant":"Громов Илья Олегович","results":[{"subject":"Математика профильная","score":"78","status":"Результат утверждён"}]}',
                         ('participant',)),
                   _form('empty',
                         '{"participant":null,"results":[]}',
                         ()),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=LMS_USER_GET, vertical='directory',
               return_forms=(
                   _form('list',
                         '[{"id":412,"username":"gromova.m","firstname":"Марина","lastname":"Громова","email":"m.gromova@example.ru","idnumber":"20-БИ-0412","phone1":"8 (3412) 45-67-89","city":"Ижевск"}]',
                         ('[].firstname', '[].lastname', '[].email', '[].idnumber', '[].phone1', '[].username')),
                   _form('empty',
                         '[]',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=DWH_SQL_QUERY, vertical='files',
               return_forms=(
                   _form('list',
                         '{"meta":[{"name":"client_fio","type":"String"},{"name":"phone","type":"String"},{"name":"inn","type":"String"},{"name":"ltv","type":"Float64"}],"data":[{"client_fio":"Громова Марина Борисовна","phone":"79164021187","inn":"183101234567","ltv":48210.5},{"client_fio":"Зайцев Олег Петрович","phone":"79125554010","inn":"183107654321","ltv":1200}],"rows":2,"statistics":{"elapsed":0.012,"rows_read":81234,"bytes_read":5242880}}',
                         ('data[].client_fio', 'data[].phone', 'data[].inn')),
                   _form('error_with_value',
                         '{"exception":"Code: 62. DB::Exception: Syntax error: failed at position 43 (\'Громова\') … (SYNTAX_ERROR)"}',
                         ('exception',)),
                   _form('empty',
                         '{"meta":[],"data":[],"rows":0}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=BI_CHART_EXPORT, vertical='files',
               return_forms=(
                   _form('list',
                         '{"result":[{"colnames":["manager","client","phone","deal_sum"],"data":[{"manager":"Соколова А.","client":"Громова М. Б.","phone":"+7 916 402-11-87","deal_sum":48210}],"rowcount":1}]}',
                         ('result[].data[].manager', 'result[].data[].client', 'result[].data[].phone')),
                   _form('free_text',
                         '{"text":"manager,client,phone,deal_sum\\nСоколова А.,Громова М. Б.,+7 916 402-11-87,48210"}',
                         ('text',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=AUDIENCE_SEGMENT_UPLOAD, vertical='crm',
               return_forms=(
                   _form('single',
                         '{"segment":{"id":12345,"name":"Отток сентябрь","type":"uploading","status":"uploaded","hashed":false}}',
                         ()),
                   _form('error_with_value',
                         '{"errors":[{"error_type":"invalid_parameter","message":"Invalid phone in line 3: +7 (916) 402-11-87"}]}',
                         ('errors[].message',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=EMAIL_CONTACTS_IMPORT, vertical='messaging',
               return_forms=(
                   _form('single',
                         '{"imported":1,"rows":[{"email":"m.gromova@example.ru","phone":"+79164021187","name":"Громова Марина"}]}',
                         ('rows[].email', 'rows[].phone', 'rows[].name')),
               ),
               differs_from_user_form=False, suite=NO_SUITE),
    ToolSpecV5(base=WEB_VISITS_EXPORT, vertical='files',
               return_forms=(
                   _form('free_text',
                         '{"text":"ym:s:visitID\\tym:s:clientID\\tym:s:ipAddress\\tym:s:parsedParamsKey2\\n7300000000000001\\t1693400000123456789\\t95.31.12.40\\tm.gromova@example.ru"}',
                         ('text',)),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=FSSP_PROCEEDINGS_SEARCH, vertical='government',
               return_forms=(
                   _form('list',
                         '{"result":[{"name":"ГРОМОВА МАРИНА БОРИСОВНА 14.03.1987 Г. ИЖЕВСК","exe_production":"123456/24/18017-ИП от 02.04.2024","details":"Судебный приказ от 11.01.2024 № 2-45/2024","subject":"Задолженность по кредитным платежам: 48210.50 руб.","department":"Октябрьский РОСП г. Ижевска","bailiff":"СОКОЛОВА А. В."}]}',
                         ('result[].name', 'result[].exe_production', 'result[].details')),
                   _form('empty',
                         '{"result":[]}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=COURT_DOCUMENT_FETCH, vertical='files',
               return_forms=(
                   _form('free_text',
                         '{"case_number":"2-1234/2026","text":"… Истец Громова М.Б. обратилась в суд с иском к <ФИО1> о взыскании … проживающей по адресу: г. Ижевск, ул. Клубная, д. 85, кв. 12 …"}',
                         ('text',)),
                   _form('empty',
                         '{"text":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
    ToolSpecV5(base=ESIA_ROLES_GET, vertical='government',
               return_forms=(
                   _form('single',
                         '{"personOid":"1000123456","roles":["citizen"],"status":"active"}',
                         ('personOid',)),
                   _form('empty',
                         '{"personOid":null}',
                         ()),
               ),
               differs_from_user_form=True, suite=NO_SUITE),
)


V6_RESULT_TYPES: dict[str, tuple[str, ...]] = {
    'crm_requisite_get': ('INN', 'OGRNIP', 'IBAN', 'PASSPORT'),
    'crm_requisite_set': ('INN', 'OGRNIP', 'IBAN', 'PASSPORT'),
    'crm_contact_upsert': ('NAME',),
    'phone_clean': ('PHONE',),
    'receipt_create': ('NAME', 'EMAIL', 'PHONE', 'INN'),
    'sms_send': ('PHONE',),
    'bank_accounts_list': ('BANK_ACCOUNT', 'NAME'),
    'ruble_transfer_create': ('NAME', 'BANK_ACCOUNT'),
    'credit_report_request': ('NAME', 'DOB', 'PASSPORT', 'LOAN_UID'),
    'debtor_card_get': ('NAME', 'DOB', 'PHONE', 'LOC', 'LOAN_CONTRACT_NUMBER', 'LOAN_UID'),
    'eln_get': ('SNILS', 'NAME', 'DOB', 'ELN_NUMBER'),
    'remd_documents_search': ('SNILS', 'NAME', 'DOB', 'MEDCARD_NUMBER'),
    'oms_policy_find': ('NAME', 'DOB', 'OMS_ENP', 'SNILS'),
    'e_prescription_create': ('NAME', 'DOB', 'OMS_ENP', 'PRESCRIPTION_NUMBER'),
    'marketplace_order_get': ('NAME', 'LOC', 'PHONE'),
    'loyalty_customer_get': ('NAME', 'DOB', 'PHONE', 'EMAIL', 'LOYALTY_CARD_NUMBER'),
    'loyalty_card_bind': ('LOYALTY_CARD_NUMBER',),
    'fiscal_receipt_create': ('NAME', 'EMAIL', 'PHONE', 'INN', 'DOB', 'PASSPORT', 'LOC'),
    'cdek_order_info': ('NAME', 'PASSPORT', 'DOB', 'INN', 'PHONE', 'LOC'),
    'osago_policy_check': ('OSAGO_POLICY', 'PLATE', 'VIN'),
    'insurance_claim_create': ('NAME', 'OSAGO_POLICY'),
    'traffic_fines_check': ('UIN', 'PLATE'),
    'epts_status_get': ('EPTS_NUMBER', 'VIN'),
    'driver_license_check': ('DRIVER_LICENSE',),
    'subscriber_profile_get': ('NAME', 'DOB', 'PASSPORT', 'LOAN_CONTRACT_NUMBER', 'SUBSCRIBER_ACCOUNT', 'PHONE', 'ICCID', 'IMSI', 'IMEI'),
    'sim_replace_request': ('PHONE', 'ICCID'),
    'egrn_extract_get': ('CADASTRAL_NUMBER', 'LOC', 'NAME', 'DOB'),
    'gis_gkh_account_get': ('GIS_ZHKH_ELS', 'UTILITY_ACCOUNT', 'LOC', 'NAME', 'SNILS'),
    'pms_booking_get': ('NAME', 'PHONE', 'EMAIL', 'DOB', 'PASSPORT'),
    'guest_arrival_notify': ('NAME', 'INTL_PASSPORT'),
    'flight_order_get': ('PNR', 'DOB', 'NAME', 'INTL_PASSPORT', 'EMAIL', 'PHONE'),
    'hr_employee_get': ('NAME', 'EMPLOYEE_TAB_NUMBER', 'DOB', 'INN', 'SNILS'),
    'resume_get': ('NAME', 'DOB', 'PHONE', 'EMAIL'),
    'payroll_card_registry': ('EMPLOYEE_TAB_NUMBER', 'NAME', 'BANK_ACCOUNT', 'PASSPORT'),
    'arbitration_case_search': ('ARBITRAZH_CASE_NO', 'NAME', 'INN', 'OGRNIP', 'LOC'),
    'probate_case_search': ('NAME', 'DOB'),
    'fns_inn_lookup': ('INN',),
    'npd_status_check': ('INN',),
    'budget_charges_find': ('UIN', 'NAME', 'PASSPORT'),
    'diploma_registry_check': ('DIPLOMA_NUMBER', 'NAME'),
    'exam_results_check': ('NAME',),
    'lms_user_get': ('NAME', 'EMAIL', 'STUDENT_ID_NUMBER', 'PHONE', 'LOGIN'),
    'dwh_sql_query': ('NAME', 'PHONE', 'INN'),
    'bi_chart_export': ('NAME', 'PHONE'),
    'audience_segment_upload': (),
    'email_contacts_import': ('EMAIL', 'PHONE', 'NAME'),
    'web_visits_export': ('METRICA_CLIENT_ID', 'IP_ADDRESS', 'EMAIL'),
    'fssp_proceedings_search': ('NAME', 'DOB', 'FSSP_IP_NO', 'COURT_CASE_NO_SOU'),
    'court_document_fetch': ('NAME', 'LOC', 'COURT_CASE_NO_SOU'),
    'esia_roles_get': ('ESIA_OID',),
}


V6_META: dict[str, V6ToolMeta] = {
    'crm_requisite_get': V6ToolMeta('primary', 'official', 'retail'),
    'crm_requisite_set': V6ToolMeta('primary', 'official', 'retail'),
    'crm_contact_upsert': V6ToolMeta('secondary', 'official', 'retail'),
    'phone_clean': V6ToolMeta('primary', 'official', 'retail'),
    'receipt_create': V6ToolMeta('primary', 'official', 'retail'),
    'sms_send': V6ToolMeta('primary', 'official', 'telecom'),
    'bank_accounts_list': V6ToolMeta('primary', 'official', 'banks_mfo_collectors'),
    'ruble_transfer_create': V6ToolMeta('summary', 'official', 'banks_mfo_collectors'),
    'credit_report_request': V6ToolMeta('secondary', 'official', 'banks_mfo_collectors'),
    'debtor_card_get': V6ToolMeta('summary', 'official', 'banks_mfo_collectors'),
    'eln_get': V6ToolMeta('primary', 'official', 'medicine'),
    'remd_documents_search': V6ToolMeta('secondary', 'official', 'medicine'),
    'oms_policy_find': V6ToolMeta('primary', 'official', 'medicine'),
    'e_prescription_create': V6ToolMeta('summary', 'official', 'medicine'),
    'marketplace_order_get': V6ToolMeta('secondary', 'official', 'retail'),
    'loyalty_customer_get': V6ToolMeta('summary', 'official', 'retail'),
    'loyalty_card_bind': V6ToolMeta('primary', 'official', 'retail'),
    'fiscal_receipt_create': V6ToolMeta('primary', 'official', 'retail'),
    'cdek_order_info': V6ToolMeta('secondary', 'official', 'logistics'),
    'osago_policy_check': V6ToolMeta('summary', 'official', 'insurance'),
    'insurance_claim_create': V6ToolMeta('summary', 'official', 'insurance'),
    'traffic_fines_check': V6ToolMeta('summary', 'official', 'auto'),
    'epts_status_get': V6ToolMeta('summary', 'official', 'auto'),
    'driver_license_check': V6ToolMeta('summary', 'official', 'auto'),
    'subscriber_profile_get': V6ToolMeta('secondary', 'official', 'telecom'),
    'sim_replace_request': V6ToolMeta('summary', 'official', 'telecom'),
    'egrn_extract_get': V6ToolMeta('summary', 'official', 'real_estate'),
    'gis_gkh_account_get': V6ToolMeta('summary', 'official', 'real_estate'),
    'pms_booking_get': V6ToolMeta('summary', 'official', 'hospitality'),
    'guest_arrival_notify': V6ToolMeta('primary', 'official', 'hospitality'),
    'flight_order_get': V6ToolMeta('primary', 'official', 'hospitality'),
    'hr_employee_get': V6ToolMeta('summary', 'official', 'hr'),
    'resume_get': V6ToolMeta('summary', 'official', 'hr'),
    'payroll_card_registry': V6ToolMeta('summary', 'official', 'hr'),
    'arbitration_case_search': V6ToolMeta('summary', 'official', 'legal'),
    'probate_case_search': V6ToolMeta('summary', 'official', 'legal'),
    'fns_inn_lookup': V6ToolMeta('summary', 'official', 'government_services'),
    'npd_status_check': V6ToolMeta('primary', 'official', 'government_services'),
    'budget_charges_find': V6ToolMeta('summary', 'official', 'government_services'),
    'diploma_registry_check': V6ToolMeta('summary', 'official', 'education'),
    'exam_results_check': V6ToolMeta('summary', 'official', 'education'),
    'lms_user_get': V6ToolMeta('primary', 'official', 'education'),
    'dwh_sql_query': V6ToolMeta('summary', 'official', 'internal_bi'),
    'bi_chart_export': V6ToolMeta('summary', 'official', 'internal_bi'),
    'audience_segment_upload': V6ToolMeta('summary', 'official', 'marketing_cdp'),
    'email_contacts_import': V6ToolMeta('primary', 'official', 'marketing_cdp'),
    'web_visits_export': V6ToolMeta('primary', 'official', 'marketing_cdp'),
    'fssp_proceedings_search': V6ToolMeta('secondary', 'closed', 'banks_mfo_collectors'),
    'court_document_fetch': V6ToolMeta('summary', 'synthetic', 'legal'),
    'esia_roles_get': V6ToolMeta('primary', 'official', 'government_services'),
}


UNSCHEMED_TOOLS: tuple[str, ...] = (
    "call_detail_records: result_set with synthetic provenance, no exact fields",
    "post_tracking_history: the track is a NEGATIVE (OD-27), result is a movement history with no PII (V04)",
    # The §2.4 gap families the research did not open as a real API mirror.
    "kyc_questionnaire: 115-ФЗ KYC form (BIRTH_CERT/RESIDENCE_PERMIT/CREDIT_SUBJECT_CODE) has no exact producer→consumer fields",
    "collection_dossier: взыскание docket with EXEC_DOC_NO, no exact fields",
    "dms_guarantee_letter: ДМС guarantee letter (MEDCARD_NUMBER/REFERRAL_NUMBER), no exact fields",
    "device_service_request: service request with IMEI, no exact fields",
    "cdp_profile: CDP profile (METRICA_CLIENT_ID/CDP_CUSTOMER_ID/LOGIN), no exact fields",
)
