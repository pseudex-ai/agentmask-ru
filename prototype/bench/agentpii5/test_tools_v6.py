"""The v6 tool registry under test: 78 grounded specs, 3 unschemed names.

THE WELLFORMED CHECK IS PER-SPEC, NOT THE WHOLE `registry_problems`. v5's
`registry_problems` also enforces V01/V02/V03 — the VERTICAL-WIDE rules — and the
v6 registry holds tools for only some of the eleven verticals. A v6 tool is
therefore checked against the PER-SPEC half of the ruleset (V04 result_pii +
forms, V05 source + strict parse, V06 every result path promised by a form), on
its own single-entry dict, plus the v6 extras: non-empty `source`, every pii_type
a registry id, and the V6T-01 metadata.

THE PARSERS ARE EXERCISED, NOT INSPECTED: each tool gets one accepted and at
least one refused shape, and the refusal must name the documented rule.

EXACT PATHS FROM DISCOVERY (`test_exact_paths_from_discovery`) reads the W1
`apis.json` and asserts, for every implemented apis.json tool, that its
`FieldSpec` paths equal the `request[].path` set and its `result_pii` equals the
`returns[].pii_paths` union VERBATIM. The five tools whose `returns[].pii_paths`
cannot be carried 1:1 by a v5 ToolSpecV5 are named in `RESULT_PII_APPROX` with
their approximation:
  * fiscal_receipt_create / email_contacts_import — verified pure-OUT tools
    (union is empty); V04 forbids an empty result_pii, so they carry the v5 R-41
    write-echo instead of nothing.
  * payroll_card_registry — `result_set` columnar `rows[][N]` -> named `rows[].<col>`.
  * bi_chart_export — `$csv` columnar path -> a `free_text` `text` leaf.
  * web_visits_export — `$tsv[col]` columnar path -> a `free_text` `text` leaf.
(The `result_set` return FORM itself is renamed `list` everywhere — `result_set`
is not a v5 `contracts.RETURN_FORMS` value — which changes no result_pii path.)
"""
import json
import os
import sys

from bench.agentpii4.tools import Refusal
from bench.agentpii5 import pii_types
from bench.agentpii5.contracts import (INDUSTRIES, NEW_TOOL_NAMES, RETURN_FORMS,
                                       V4_TOOL_NAMES, VERTICALS)
from bench.agentpii5.tools_v6 import (TOOLS_V6, UNSCHEMED_TOOLS, V6_META,
                                      V6_RESULT_TYPES)

TYPE_IDS = frozenset(t.id for t in pii_types.TYPE_REGISTRY)
EVIDENCE_KINDS = frozenset(("primary", "secondary", "summary"))
API_STATUSES = frozenset(("official", "closed", "synthetic"))
APIS_JSON = "/Users/igor/pseudex-private/v6-work/w1/apis.json"
# The tools whose result_pii is an approximation of the verbatim union (see the
# module docstring). Everything else must match apis.json exactly.
RESULT_PII_APPROX: dict[str, str] = {
    "fiscal_receipt_create": "pure-OUT (union empty): R-41 write-echo",
    "email_contacts_import": "pure-OUT (union empty): R-41 write-echo",
    "payroll_card_registry": "result_set rows[][N] -> named rows[].<col>",
    "bi_chart_export": "$csv -> free_text text leaf",
    "web_visits_export": "$tsv[col] -> free_text text leaf",
    "diploma_registry_check": "error.subject declared for retry_same_tool; apis.json has no error form",
    "hr_employee_get": "error.subject declared for retry_same_tool; apis.json has no error form",
    "traffic_fines_check": "STS_NUMBER result side added (fines[].sts) — apis.json has no result path for it",
    "audience_segment_upload": "CDP_CUSTOMER_ID result side added (segment.ids[].external_id) — apis.json has no result path for it",
}

# The four tools that gained their MISSING argument side in place (the 22 both-ways
# upgrade): apis.json carries no request path for these keys, so the exact
# `request[].path == FieldSpec.path` cross-check cannot hold verbatim for them.
FIELD_PATH_APPROX: dict[str, str] = {
    "credit_report_request": "LOAN_UID arg side added (uid) — apis.json has no request path for it",
    "fssp_proceedings_search": "FSSP_IP_NO arg side added (ip_number) — apis.json has no request path for it",
    "subscriber_profile_get": "SUBSCRIBER_ACCOUNT arg side added (personal_account) — apis.json has no request path for it",
    "e_prescription_create": "PRESCRIPTION_NUMBER arg side added (prescription_id) — apis.json has no request path for it",
}


def _leaves(value: object) -> frozenset[str]:
    """Every dotted leaf of an example, array indexes erased («rows[].phone»)."""
    out: set[str] = set()

    def walk(node: object, prefix: str) -> None:
        if isinstance(node, dict):
            if not node:
                out.add(prefix)
                return
            for key, inner in node.items():
                walk(inner, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(node, list):
            if not node:
                out.add(f"{prefix}[]")
                return
            for inner in node:
                walk(inner, f"{prefix}[]")
        else:
            out.add(prefix)

    walk(value, "")
    return frozenset(out)


def _audience_rows(n: int) -> list[dict[str, str]]:
    """`n` valid numeric-phone rows for the Яндекс Аудитории bulk upload."""
    return [{"phone": f"7999000{i:04d}"} for i in range(n)]


def test_no_pseudex() -> list[str]:
    leaked = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    return [f"the v6 registry pulled in {leaked}"] if leaked else []


def test_specs_wellformed() -> list[str]:
    problems: list[str] = []
    by_name = {spec.base.name: spec for spec in TOOLS_V6}
    for name, spec in sorted(by_name.items()):
        base = spec.base
        if not base.result_pii:
            problems.append(f"V04 {name}: result_pii is empty")
        if not spec.return_forms:
            problems.append(f"V04 {name}: no return form declared")
        declared = set(base.result_pii)
        in_forms: set[str] = set()
        for form in spec.return_forms:
            if form.form not in RETURN_FORMS:
                problems.append(f"V04 {name}: {form.form!r} is not a contracts return form")
            unknown = sorted(set(form.pii_paths) - declared)
            if unknown:
                problems.append(f"V04 {name}/{form.form}: pii_paths {unknown} "
                                f"are not in result_pii")
            in_forms |= set(form.pii_paths)
            try:
                obj = json.loads(form.example)
            except json.JSONDecodeError as exc:
                problems.append(f"{name}/{form.form}: example is not JSON: {exc}")
                continue
            leaves = _leaves(obj)
            missing = sorted(set(form.pii_paths) - leaves)
            if missing:
                problems.append(f"{name}/{form.form}: example does not resolve {missing}")
        unpromised = sorted(declared - in_forms)
        if unpromised:
            problems.append(f"V06 {name}: result_pii {unpromised} named by no return form")
        if not base.source:
            problems.append(f"V05 {name}: no source API cited")
        refused = base.parse({})
        if not isinstance(refused, Refusal) or not refused.rule:
            problems.append(f"V05 {name}: parse({{}}) did not refuse with a documented "
                            f"rule (got {refused!r})")
        if spec.vertical not in VERTICALS:
            problems.append(f"{name}: vertical {spec.vertical!r} is not in contracts.VERTICALS")
        for field in base.fields:
            if field.pii_type and field.pii_type not in TYPE_IDS:
                problems.append(f"{name}: field {field.path} carries pii_type "
                                f"{field.pii_type!r}, not a registry id")
        for pii_type in V6_RESULT_TYPES.get(name, ()):
            if pii_type not in TYPE_IDS:
                problems.append(f"{name}: result type {pii_type!r} is not a registry id")
        meta = V6_META.get(name)
        if meta is None:
            problems.append(f"{name}: no V6_META row (V6T-01)")
            continue
        if meta.evidence not in EVIDENCE_KINDS:
            problems.append(f"{name}: evidence {meta.evidence!r} is not "
                            f"primary/secondary/summary")
        if meta.api_status not in API_STATUSES:
            problems.append(f"{name}: api_status {meta.api_status!r} is not "
                            f"official/closed/synthetic")
        if meta.industry not in INDUSTRIES:
            problems.append(f"{name}: industry {meta.industry!r} is not in contracts_v6.INDUSTRIES")
    return problems


def test_exact_paths_from_discovery() -> list[str]:
    """result_pii == returns[].pii_paths union, FieldSpec paths == request[].path.

    Skipped (empty result) when the discovery file is absent, so the suite stays
    green in an environment without the W1 worktree; it is the cross-check the
    upgrade exists to satisfy when the file IS present."""
    if not os.path.exists(APIS_JSON):
        return []
    with open(APIS_JSON) as handle:
        data = json.load(handle)
    by_name = {spec.base.name: spec for spec in TOOLS_V6}
    problems: list[str] = []
    for tool in data["tools"]:
        name = tool["name"]
        if name not in by_name:
            continue  # unschemed: fssp, call_detail_records, court_document_fetch, post_tracking
        spec = by_name[name]
        req_paths = [r["path"] for r in tool["request"]]
        fs_paths = [f.path for f in spec.base.fields]
        if name in FIELD_PATH_APPROX:
            pass  # the missing argument side was added in place; exact equality cannot hold
        elif req_paths != fs_paths:
            problems.append(f"{name}: FieldSpec paths {fs_paths} != request paths {req_paths}")
        union = tuple(p for r in tool["returns"] for p in r["pii_paths"])
        if name in RESULT_PII_APPROX:
            if not spec.base.result_pii:
                problems.append(f"{name}: approximated ({RESULT_PII_APPROX[name]}) "
                                f"but result_pii is empty")
            continue
        if spec.base.result_pii != union:
            problems.append(f"{name}: result_pii {spec.base.result_pii} "
                            f"!= returns[].pii_paths union {union}")
    return problems


def test_no_collision() -> list[str]:
    v6_names = {spec.base.name for spec in TOOLS_V6}
    existing = set(V4_TOOL_NAMES) | set(NEW_TOOL_NAMES)
    collided = sorted(v6_names & existing)
    return [f"v6 tool {name!r} collides with a v4/v5 tool" for name in collided]


def test_unschemed_named() -> list[str]:
    problems: list[str] = []
    if not UNSCHEMED_TOOLS:
        problems.append("UNSCHEMED_TOOLS is empty — every D-078 tool needs a line")
    for entry in UNSCHEMED_TOOLS:
        head, _, reason = entry.partition(":")
        if not head.strip():
            problems.append(f"an unschemed entry has no tool name: {entry!r}")
        if not reason.strip():
            problems.append(f"the unschemed entry {head.strip()!r} has no reason")
    return problems


def test_parsers_good_bad() -> list[str]:
    problems: list[str] = []
    cases: dict[str, tuple[tuple[dict[str, object], ...],
                           tuple[tuple[dict[str, object], str], ...]]] = {
        # --- research-grounded (unchanged) -----------------------------------
        "crm_requisite_get": (
            ({"inn": "500100732259"}, {"ogrnip": "312345678901230"},
             {"iban": "RU0304452522540817810538091310419"}),
            (({"inn": "500100732258"}, "inn_checksum"),
             ({"ogrnip": "312345678901231"}, "ogrnip_checksum"),
             ({"iban": "RU0304452522540817810538091310418"}, "iban_checksum")),
        ),
        "crm_requisite_set": (
            ({"inn": "500100732259", "ogrnip": "312345678901230",
              "ident_doc": {"ser": "4509", "num": "123456", "date": "2018-04-10",
                            "issued_by": "ГУ МВД"}},),
            (({"inn": "123"}, "inn_format"),
             ({"inn": "500100732259", "ident_doc": {"ser": "45", "num": "123456"}},
              "passport_series_format")),
        ),
        "crm_contact_upsert": (
            ({"first_name": "Марина", "last_name": "Громова",
              "custom_fields_values": [{"field_id": 10001,
                                        "values": [{"value": "+79164021187", "enum_code": "WORK"}]}]},),
            (({"first_name": "Марина"}, "missing_required"),
             ({"first_name": "Марина", "last_name": "Громова",
               "custom_fields_values": [{"field_id": 10001, "values": []}]}, "array_required")),
        ),
        "phone_clean": (
            ({"source": "8 (916) 402-11-87"},),
            (({"source": "   "}, "empty_source"),
             ({"source": "x" * 61}, "too_long")),
        ),
        "receipt_create": (
            ({"customer": {"full_name": "Павлова Тамара", "email": "pavlova@mail.ru"}},
             {"customer": {"full_name": "Павлова Тамара", "phone": "79164021187",
                           "inn": "500100732259"}}),
            (({"customer": {"full_name": "Павлова Тамара"}}, "contact_required"),
             ({"customer": {"full_name": "Павлова Тамара", "phone": "+79164021187"}},
              "phone_numeric_format")),
        ),
        "sms_send": (
            ({"destination": "+79164021187", "text": "Перезвоним завтра."},),
            (({"destination": "89164021187", "text": "Перезвоним завтра."}, "phone_not_e164"),
             ({"destination": "+79164021187", "text": ""}, "missing_required")),
        ),
        # --- apis.json exact --------------------------------------------------
        "bank_accounts_list": (
            ({"client_id": "bc-1"},),
            (({"client_id": "bad id"}, "id_format"),),
        ),
        "ruble_transfer_create": (
            ({"payment_id": "p-1",
              "recipient": {"name": "Громова Марина Борисовна",
                            "account": "40602810700000000025", "bik": "049805746"},
              "amount": "1000.00", "purpose": "Перевод за товар"},),
            (({"payment_id": "p-1",
               "recipient": {"name": "Громова Марина Борисовна",
                             "account": "123", "bik": "049805746"},
               "amount": "1000", "purpose": "x"}, "account_format"),
             ({"payment_id": "p-1",
               "recipient": {"name": "Громова Марина Борисовна",
                             "account": "40602810800000000025", "bik": "049805746"},
               "amount": "1000", "purpose": "x"}, "account_key_mismatch")),
        ),
        "credit_report_request": (
            ({"subject": {"last_name": "Громова", "first_name": "Марина",
                          "birth_date": "1987-03-14", "passport": "4507 443564"},
              "consent_id": "c-1"},
             {"uid": "1dcf884c-5f2a-4b3e-9d7a-6c5b4e3f2a1d-c", "consent_id": "c-1"}),
            (({}, "missing_required"),
             ({"subject": {"last_name": "Громова", "first_name": "Марина",
                           "birth_date": "1987-03-14", "passport": "4507 443564",
                           "snils": "123-456-789 00"}, "consent_id": "c-1"},
              "snils_checksum"),
             ({"uid": "not-a-uid", "consent_id": "c-1"}, "loan_uid_format")),
        ),
        "debtor_card_get": (
            ({"contract_number": "12-345678/2025"},),
            (({"contract_number": "x" * 41}, "contract_format"),),
        ),
        "eln_get": (
            ({"ogrn": "1027700000000", "ln_code": "900012345678",
              "snils": "11223344595"},),
            (({"ogrn": "123", "ln_code": "900012345678", "snils": "11223344595"},
              "ogrn_pattern"),
             ({"ogrn": "1027700000000", "ln_code": "900012345678",
               "snils": "12345678900"}, "snils_checksum")),
        ),
        "remd_documents_search": (
            ({"patient_snils": "11223344595"},),
            (({"patient_snils": "12345678900"}, "snils_checksum"),),
        ),
        "oms_policy_find": (
            ({"enp": "7707536455681514"}, {"snils": "11223344595"}),
            (({}, "exactly_one_key"),
             ({"enp": "7707536455681515"}, "enp_checksum")),
        ),
        "e_prescription_create": (
            ({"patient": {"fio": "Иванов Пётр", "birth_date": "1987-03-14"},
              "drug": "Амоксициллин", "dosage": "500 мг"},
             {"patient": {"fio": "Иванов Пётр", "birth_date": "1987-03-14"},
              "drug": "Амоксициллин", "dosage": "500 мг",
              "prescription_id": "45 0012345678"}),
            (({}, "missing_required"),
             ({"patient": {"fio": "Иванов Пётр", "birth_date": "14.03.1987"},
               "drug": "Амоксициллин", "dosage": "500 мг"}, "date_format"),
             ({"patient": {"fio": "Иванов Пётр", "birth_date": "1987-03-14"},
               "drug": "Амоксициллин", "dosage": "500 мг",
               "prescription_id": "45"}, "prescription_format")),
        ),
        "marketplace_order_get": (
            ({"posting_number": "0123456789-0001-1"},),
            (({"posting_number": "!"}, "posting_number_format"),),
        ),
        "loyalty_customer_get": (
            ({"mobile_phone": "79164021187"}, {"email": "m.gromova@example.ru"},
             {"discount_card": "231534554262"}),
            (({}, "exactly_one_key"),
             ({"mobile_phone": "+79164021187"}, "phone_format"),
             ({"email": "bad"}, "email_format")),
        ),
        "loyalty_card_bind": (
            ({"customer": {"mobile_phone": "79164021187"}, "card_number": "231534554262"},),
            (({"customer": {"mobile_phone": "79164021187"}, "card_number": "123"},
              "card_format"),),
        ),
        "fiscal_receipt_create": (
            ({"external_id": "e-1", "receipt": {"items": [{"name": "Товар"}],
               "client": {"email": "pavlova@mail.ru"}}},),
            (({}, "missing_required"),
             ({"external_id": "e-1", "receipt": {"items": [{"name": "Товар"}],
               "client": {"name": "Павлова Тамара"}}}, "email_or_phone_required")),
        ),
        "cdek_order_info": (
            ({"cdek_number": "1234567890"},),
            (({"cdek_number": "!"}, "cdek_number_format"),),
        ),
        "osago_policy_check": (
            ({"policy": "ХХХ 0123456789"}, {"vin": "XTAGFK330LY123456"}),
            (({}, "exactly_one_key"),
             ({"policy": "ХХХ 012345678"}, "policy_format")),
        ),
        "insurance_claim_create": (
            ({"applicant": {"fio": "Громова Марина Борисовна", "birth_date": "1987-03-14",
                            "passport": "4507 443564"}, "policy": "ХХХ 0123456789"},),
            (({"applicant": {"fio": "Громова Марина Борисовна", "birth_date": "1987-03-14",
                             "passport": "4507 443564"}, "policy": "123"}, "policy_format"),),
        ),
        "traffic_fines_check": (
            ({"plate": "Р777ТТ18", "sts": "77 12 345678"},),
            (({"plate": "Р777ТТ18", "sts": "771234567"}, "sts_format"),),
        ),
        "epts_status_get": (
            ({"epts_number": "164301000000016"}, {"vin": "XTAGFK330LY123456"}),
            (({}, "exactly_one_key"),
             ({"epts_number": "164301000000017"}, "epts_checksum")),
        ),
        "driver_license_check": (
            ({"license_number": "99 12 345678", "issue_date": "2019-06-11"},),
            (({"license_number": "991234567", "issue_date": "2019-06-11"},
              "license_format"),),
        ),
        "subscriber_profile_get": (
            ({"msisdn": "79164021187"}, {"personal_account": "418000123456"}),
            (({}, "missing_required"),
             ({"msisdn": "+79164021187"}, "phone_format"),
             ({"personal_account": "123"}, "account_format")),
        ),
        "sim_replace_request": (
            ({"msisdn": "79164021187", "fio": "Иванов Пётр", "passport": "4507 443564",
              "new_iccid": "8970102000000123458"},),
            (({"msisdn": "79164021187", "fio": "Иванов Пётр", "passport": "4507 443564",
               "new_iccid": "8970102000000123457"}, "iccid_checksum"),),
        ),
        "egrn_extract_get": (
            ({"cadastral_number": "77:01:0001001:1234"},),
            (({"cadastral_number": "77:01:1001:1234"}, "cadastral_format"),),
        ),
        "gis_gkh_account_get": (
            ({"els": "60АА000593-01"},),
            (({}, "exactly_one_key"),
             ({"els": "60AA000593-01"}, "els_format")),
        ),
        "pms_booking_get": (
            ({"booking_id": "b-123456"},),
            (({}, "missing_required"),
             ({"booking_id": "bad id"}, "id_format")),
        ),
        "guest_arrival_notify": (
            ({"guest": {"last_name": "Иванов", "first_name": "Пётр", "citizenship": "RUS",
                        "birth_date": "1987-03-14", "document": {"number": "751234567"}},
              "stay": {"address": "г. Ижевск, ул. Клубная, д. 85", "until": "2026-12-01"}},),
            (({}, "missing_required"),
             ({"guest": {"last_name": "Иванов", "first_name": "Пётр", "citizenship": "RUS",
                         "birth_date": "1987-03-14", "document": {"number": "75123456"}},
               "stay": {"address": "г. Ижевск, ул. Клубная, д. 85", "until": "2026-12-01"}},
              "document_format")),
        ),
        "flight_order_get": (
            ({"flight_order_id": "2ZYVAL"},),
            (({}, "missing_required"),
             ({"flight_order_id": "2 ZYVAL"}, "id_format")),
        ),
        "hr_employee_get": (
            ({"tab_number": "004512"}, {"fio": "Иванов Пётр"}),
            (({}, "exactly_one_key"),
             ({"tab_number": "4512"}, "tab_number_format")),
        ),
        "resume_get": (
            ({"resume_id": "0123abcd"},),
            (({"resume_id": "bad id"}, "id_format"),),
        ),
        "payroll_card_registry": (
            ({"employees": [{"fio": "Громова Марина Борисовна", "birth_date": "1987-03-14",
                             "passport": "4507 443564"}]},),
            (({}, "missing_required"),
             ({"employees": [{"fio": "Громова Марина Борисовна",
                              "birth_date": "1987-03-14", "passport": "123"}]},
              "passport_format")),
        ),
        "arbitration_case_search": (
            ({"case_number": "А31-2840/2013"}, {"inn": "500100732259"}),
            (({}, "at_least_one_key"),
             ({"case_number": "31-2840/2013"}, "case_number_format")),
        ),
        "probate_case_search": (
            ({"fio": "Громов Пётр Иванович"},),
            (({"fio": "   "}, "name_format"),),
        ),
        "fns_inn_lookup": (
            ({"fam": "Громова", "nam": "Марина", "bdate": "14.03.1987",
              "doctype": "21", "docno": "45 01 123456"},),
            (({"fam": "Громова", "nam": "Марина", "bdate": "14.03.1987",
               "doctype": "21", "docno": "45 01 12345"}, "passport_format"),),
        ),
        "npd_status_check": (
            ({"inn": "500100732259", "requestDate": "2019-01-11"},),
            (({"inn": "500100732258", "requestDate": "2019-01-11"}, "inn_checksum"),),
        ),
        "budget_charges_find": (
            ({"payer_inn": "500100732259"}, {"payer_snils": "11223344595"}),
            (({}, "exactly_one_key"),
             ({"payer_inn": "500100732258"}, "inn_checksum")),
        ),
        "diploma_registry_check": (
            ({"last_name": "Громова", "blank_series": "101805", "blank_number": "0123456"},),
            (({"last_name": "Громова", "blank_series": "10180", "blank_number": "0123456"},
              "series_format"),),
        ),
        "exam_results_check": (
            ({"fio": "Громов Илья Олегович", "region": "18", "document_number": "123456"},),
            (({"fio": "Громов Илья Олегович", "region": "18"}, "exactly_one_key"),),
        ),
        "lms_user_get": (
            ({"field": "email", "values": ["m.gromova@example.ru"]},),
            (({"field": "phone", "values": ["x"]}, "field_enum"),),
        ),
        "dwh_sql_query": (
            ({"sql": "SELECT * FROM t WHERE phone = '+79164021187'"},),
            (({"sql": "   "}, "sql_not_select"),),
        ),
        "bi_chart_export": (
            ({"chart_id": "ch-12345", "result_format": "csv"},),
            (({"chart_id": "ch-12345", "result_format": "pdf"}, "format_enum"),),
        ),
        "audience_segment_upload": (
            ({"segment_name": "Отток", "hashed": "false",
              "file": {"rows": _audience_rows(100)}},),
            (({}, "missing_required"),
             ({"segment_name": "Отток", "hashed": "false",
               "file": {"rows": _audience_rows(5)}}, "too_few_rows")),
        ),
        "email_contacts_import": (
            ({"field_names": ["email"], "data": [["grom@mail.ru"]]},),
            (({"field_names": ["phone"], "data": [["grom@mail.ru"]]}, "field_names_mismatch"),
             ({"field_names": ["email"], "data": [["bad"]]}, "email_format")),
        ),
        "web_visits_export": (
            ({"counter_id": "12345", "date1": "2026-01-01", "date2": "2026-01-31",
              "fields": "ym:s:clientID"},),
            (({"counter_id": "12345", "date1": "01.01.2026", "date2": "2026-01-31",
               "fields": "ym:s:clientID"}, "date_format"),),
        ),
        "fssp_proceedings_search": (
            ({"region": "18", "last_name": "Фомина", "first_name": "Анна",
              "middle_name": "Петровна", "birth_date": "14.03.1987"},
             {"ip_number": "123456/24/18017-ИП"}),
            (({"region": "18", "last_name": "Фомина"}, "missing_required"),
             ({"region": "18", "last_name": "Фомина", "first_name": "Анна",
               "birth_date": "1987-03-14"}, "date_format"),
             ({"ip_number": "123"}, "ip_number_format")),
        ),
        "court_document_fetch": (
            ({"court": "Индустриальный районный суд", "case_number": "2-13/2015"},),
            (({"court": "Индустриальный районный суд"}, "missing_required"),
             ({"court": "Индустриальный районный суд", "case_number": "13/2015"},
              "case_number_format")),
        ),
        "esia_roles_get": (
            ({"prn_oid": "1000123456"},),
            (({}, "missing_required"),
             ({"prn_oid": "abc"}, "oid_format")),
        ),
        # --- the 12 WEB-STUDY both-ways tools ---------------------------------
        "gis_gmp_charge_find": (
            ({"SupplierBillID": "91417776317066907430"},),
            (({}, "missing_required"),
             ({"SupplierBillID": "9141777631706690743"}, "uin_format"),
             ({"SupplierBillID": "91417776317066907431"}, "uin_checksum")),
        ),
        "gis_gkh_utility_account_get": (
            ({"AccountID": "9141777"},),
            (({}, "missing_required"),
             ({"AccountID": "91417"}, "account_format")),
        ),
        "device_provisioning_find": (
            ({"deviceIdentifier": "291417776317061"},),
            (({}, "missing_required"),
             ({"deviceIdentifier": "29141777631706"}, "imei_format"),
             ({"deviceIdentifier": "291417776317062"}, "imei_checksum")),
        ),
        "omnihss_subscriber_get": (
            ({"imsi": "250291417776317"},),
            (({}, "missing_required"),
             ({"imsi": "2502914177763"}, "imsi_format")),
        ),
        "ip_api_lookup": (
            ({"query": "68.32.130.60"},),
            (({}, "missing_required"),
             ({"query": "999.32.130.60"}, "ip_format")),
        ),
        "flight_order_manage_get": (
            ({"flight_order_id": "4G7YV"},),
            (({}, "missing_required"),
             ({"flight_order_id": "4G7"}, "pnr_format")),
        ),
        "metrica_offline_conversion_upload": (
            ({"ClientId": "291417776317066907"},),
            (({}, "missing_required"),
             ({"ClientId": "29141777631706690"}, "client_id_format")),
        ),
        "moodle_user_by_username": (
            ({"field": "username", "values": ["szyci_d17"]},),
            (({"field": "email", "values": ["szyci_d17"]}, "field_enum"),
             ({"field": "username", "values": ["ab"]}, "login_format")),
        ),
        "appmetrica_event_import": (
            ({"google_aid": "4283FEFC-63F0-CD0E-873A-0000C6D07EF7"},
             {"ios_ifa": "4283FEFC-63F0-CD0E-873A-0000C6D07EF7"}),
            (({}, "exactly_one_key"),
             ({"google_aid": "4283FEFC-63F0-CD0E-873A-0000C6D07E"}, "uuid_format")),
        ),
        "appmetrica_device_id_lookup": (
            ({"appmetrica_device_id": "141777631706690743"},
             {"ios_ifv": "4283FEFC-63F0-CD0E-873A-0000C6D07EF7"}),
            (({}, "exactly_one_key"),
             ({"appmetrica_device_id": "14177763170669074"}, "device_id_format")),
        ),
        "mikrotik_dhcp_lease_get": (
            ({"mac-address": "42:83:fe:fc:63:f0"},),
            (({}, "missing_required"),
             ({"mac-address": "42:83:fe:fc:63"}, "mac_format")),
        ),
        "uhppote_card_get": (
            ({"cardNumber": "1417776317"},),
            (({}, "missing_required"),
             ({"cardNumber": "141"}, "card_format")),
        ),
        # --- the 16 final both-ways documented-procedure tools -----------------
        "birth_cert_fetch": (
            ({"birth_cert_number": "IV-МЮ 320819"},),
            (({}, "missing_required"),
             ({"birth_cert_number": "320819"}, "cert_format")),
        ),
        "civil_act_fetch": (
            ({"certificate_number": "I-АГ 672731"},),
            (({}, "missing_required"),
             ({"certificate_number": "672731"}, "cert_format")),
        ),
        "residence_permit_check": (
            ({"residence_permit": "82 1234567"},),
            (({}, "missing_required"),
             ({"residence_permit": "82 12345"}, "permit_format")),
        ),
        "military_id_register": (
            ({"military_id": "АК 1234567"},),
            (({}, "missing_required"),
             ({"military_id": "АК 123456"}, "military_id_format")),
        ),
        "credit_subject_check": (
            ({"subject_code": "Qw7rT2"},),
            (({}, "missing_required"),
             ({"subject_code": "abc"}, "subject_code_format")),
        ),
        "dms_policy_find": (
            ({"dms_policy": "001SB12345678"},),
            (({}, "missing_required"),
             ({"dms_policy": "!"}, "policy_format")),
        ),
        "kasko_policy_find": (
            ({"kasko_policy": "AI123456789"},),
            (({}, "missing_required"),
             ({"kasko_policy": "!"}, "policy_format")),
        ),
        "insurance_claim_status": (
            ({"claim_number": "У-671-475136/25"},),
            (({}, "missing_required"),
             ({"claim_number": "123"}, "claim_format")),
        ),
        "court_case_fetch": (
            ({"case_uid": "77RS0000-02-2026-000001-52"},),
            (({}, "missing_required"),
             ({"case_uid": "77RS0000"}, "uid_format")),
        ),
        "exec_doc_check": (
            ({"writ_number": "ФС 012345678"},),
            (({}, "missing_required"),
             ({"writ_number": "ФС 01234567"}, "exec_doc_format")),
        ),
        "pts_vehicle_get": (
            ({"pts_number": "77 УК 123456"},),
            (({}, "missing_required"),
             ({"pts_number": "77 123456"}, "pts_format")),
        ),
        "medcard_lookup": (
            ({"med_card_number": "12345/2024"},),
            (({}, "missing_required"),
             ({"med_card_number": "!"}, "medcard_format")),
        ),
        "referral_find": (
            ({"referral_id": "057-1234-123456"},),
            (({}, "missing_required"),
             ({"referral_id": "057"}, "referral_format")),
        ),
        "school_cert_verify": (
            ({"attestat_number": "07705000012345"},),
            (({}, "missing_required"),
             ({"attestat_number": "0770500001234"}, "cert_number_format")),
        ),
        "employment_contract_get": (
            ({"employment_contract_number": "145-ТД"},),
            (({}, "missing_required"),
             ({"employment_contract_number": "!"}, "contract_format")),
        ),
        "e_ticket_issue": (
            ({"ticket_number": "5552412345678"},),
            (({}, "missing_required"),
             ({"ticket_number": "555241234567"}, "ticket_format")),
        ),
    }
    by_name = {spec.base.name: spec for spec in TOOLS_V6}
    for name in sorted(by_name):
        spec = by_name[name]
        if name not in cases:
            problems.append(f"{name}: no good/bad shapes in the test table")
            continue
        accepted, refused = cases[name]
        for shape in accepted:
            result = spec.base.parse(dict(shape))
            if isinstance(result, Refusal):
                problems.append(f"{name}: refused its own accepted shape {shape!r}: "
                                f"{result.rule}")
        for shape, rule in refused:
            result = spec.base.parse(dict(shape))
            if not isinstance(result, Refusal):
                problems.append(f"{name}: accepted the refused shape {shape!r} "
                                f"(expected rule {rule!r})")
            elif result.rule != rule:
                problems.append(f"{name}: shape {shape!r} refused with {result.rule!r}, "
                                f"expected {rule!r}")
    return problems


CHECKS = (test_no_pseudex, test_specs_wellformed, test_exact_paths_from_discovery,
          test_no_collision, test_unschemed_named, test_parsers_good_bad)


def main() -> int:
    failures = 0
    for check in CHECKS:
        for problem in check():
            print(f"FAIL {check.__name__}: {problem}")
            failures += 1
    print("test_tools_v6: PASS" if not failures else f"test_tools_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
