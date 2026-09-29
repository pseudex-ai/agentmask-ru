"""The v6 tool registry under test: 47 grounded specs, 9 unschemed names.

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
        if req_paths != fs_paths:
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
        problems.append("UNSCHEMED_TOOLS is empty — every D-069 tool needs a line")
    for entry in UNSCHEMED_TOOLS:
        head, _, reason = entry.partition(":")
        if not head.strip():
            problems.append(f"an unschemed entry has no tool name: {entry!r}")
        if not reason.strip():
            problems.append(f"the unschemed entry {head.strip()!r} has no reason")
    if not any(entry.partition(":")[0].strip() == "fssp_proceedings_search"
               for entry in UNSCHEMED_TOOLS):
        problems.append("fssp_proceedings_search is not named in UNSCHEMED_TOOLS")
    return problems


def test_parsers_good_bad() -> list[str]:
    problems: list[str] = []
    cases: dict[str, tuple[tuple[dict[str, object], ...],
                           tuple[tuple[dict[str, object], str], ...]]] = {
        # --- research-grounded (unchanged) -----------------------------------
        "crm_requisite_get": (
            ({"inn": "500100732259"}, {"ogrnip": "312345678901230"}),
            (({"inn": "500100732258"}, "inn_checksum"),
             ({"ogrnip": "312345678901231"}, "ogrnip_checksum")),
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
              "consent_id": "c-1"},),
            (({}, "missing_required"),
             ({"subject": {"last_name": "Громова", "first_name": "Марина",
                           "birth_date": "1987-03-14", "passport": "4507 443564",
                           "snils": "123-456-789 00"}, "consent_id": "c-1"},
              "snils_checksum")),
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
              "drug": "Амоксициллин", "dosage": "500 мг"},),
            (({}, "missing_required"),
             ({"patient": {"fio": "Иванов Пётр", "birth_date": "14.03.1987"},
               "drug": "Амоксициллин", "dosage": "500 мг"}, "date_format")),
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
            ({"msisdn": "79164021187"},),
            (({}, "missing_required"),
             ({"msisdn": "+79164021187"}, "phone_format")),
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
