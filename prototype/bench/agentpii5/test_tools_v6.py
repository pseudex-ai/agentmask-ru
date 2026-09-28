"""The v6 tool registry under test: 47 grounded specs, 9 unschemed names.

THE WELLFORMED CHECK IS PER-SPEC, NOT THE WHOLE `registry_problems`. v5's
`registry_problems` also enforces V01/V02/V03 — the VERTICAL-WIDE rules («a
vertical declares a list form», «a vertical has an error/empty», «a vertical has
a differing notation») — and the v6 registry holds tools for only some of the
eleven verticals. A v6 tool is therefore checked against the PER-SPEC half of the
ruleset (V04 result_pii + forms, V05 source + strict parse, V06 every result path
promised by a form), on its own single-entry dict, plus the v6 extras the task
adds: non-empty `source`, every pii_type a registry id, and the V6T-01 metadata.

THE PARSERS ARE EXERCISED, NOT INSPECTED: each tool gets one accepted and at
least one refused shape, and the refusal must name the documented rule.
"""
import json
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


def _leaves(value: object) -> frozenset[str]:
    """Every dotted leaf of an example, array indexes erased («rows[].phone»).

    THE SAME WALK AS `tools.generic_paths`, written here rather than imported so
    this test does not couple to the v5 registry object for one helper."""
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


def test_no_pseudex() -> list[str]:
    leaked = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    return [f"the v6 registry pulled in {leaked}"] if leaked else []


def test_specs_wellformed() -> list[str]:
    problems: list[str] = []
    by_name = {spec.base.name: spec for spec in TOOLS_V6}
    for name, spec in sorted(by_name.items()):
        base = spec.base
        # V04 — a result carrying no PII has no IN/tool hop to measure.
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
        # V06 — a result path promised by no form is measured by nothing.
        unpromised = sorted(declared - in_forms)
        if unpromised:
            problems.append(f"V06 {name}: result_pii {unpromised} named by no return form")
        # V05 — non-empty source and a strict parser.
        if not base.source:
            problems.append(f"V05 {name}: no source API cited")
        refused = base.parse({})
        if not isinstance(refused, Refusal) or not refused.rule:
            problems.append(f"V05 {name}: parse({{}}) did not refuse with a documented "
                            f"rule (got {refused!r})")
        if spec.vertical not in VERTICALS:
            problems.append(f"{name}: vertical {spec.vertical!r} is not in contracts.VERTICALS")
        # V6T-04 — every pii_type is a registry id, in the fields and in the result.
        for field in base.fields:
            if field.pii_type and field.pii_type not in TYPE_IDS:
                problems.append(f"{name}: field {field.path} carries pii_type "
                                f"{field.pii_type!r}, not a registry id")
        for pii_type in V6_RESULT_TYPES.get(name, ()):
            if pii_type not in TYPE_IDS:
                problems.append(f"{name}: result type {pii_type!r} is not a registry id")
        # V6T-01 — the provenance that has no ToolSpecV5 field.
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


def test_no_collision() -> list[str]:
    # R6-18: a v6 name sharing a v4/v5 name would replace the baseline's spec, and
    # a v4/v5 corpus case calling it would be scored against a different API.
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
    # Accepted and refused shapes, one per tool, with the exact documented rule.
    cases: dict[str, tuple[tuple[dict[str, object], ...],
                           tuple[tuple[dict[str, object], str], ...]]] = {
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
        "email_contacts_import": (
            ({"data": [{"email": "grom@mail.ru", "phone": "+79164021187",
                        "name": "Громова Марина"}]},),
            (({"data": []}, "no_contacts"),
             ({"data": [{"email": "bad", "phone": "+79164021187",
                         "name": "Громова Марина"}]}, "email_format")),
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
        # --- §2.3 doc-proc tools (evidence=summary) ----------------------------
        "bank_accounts_list": (
            ({"client_id": "bc-1"},),
            (({"client_id": "x"}, "id_format"),),
        ),
        "ruble_transfer_create": (
            ({"account": "40602810700000000025", "bik": "049805746"},),
            (({"account": "123", "bik": "049805746"}, "account_format"),
             ({"account": "40602810800000000025", "bik": "049805746"}, "account_key_mismatch")),
        ),
        "credit_report_request": (
            ({"snils": "112-233-445 95"}, {"client_id": "bc-1"}),
            (({"snils": "123-456-789 00"}, "snils_checksum"),
             ({}, "exactly_one_key")),
        ),
        "debtor_card_get": (
            ({"contract_number": "12-345678/2025"},),
            (({"contract_number": "x" * 41}, "contract_number_format"),),
        ),
        "eln_get": (
            ({"ln_code": "900012345678"},),
            (({"ln_code": "x" * 13}, "ln_code_format"),),
        ),
        "remd_documents_search": (
            ({"snils": "112-233-445 95"},),
            (({"snils": "123-456-789 00"}, "snils_checksum"),),
        ),
        "oms_policy_find": (
            ({"enp": "7707536455681514"},),
            (({"enp": "7707536455681515"}, "enp_checksum"),),
        ),
        "e_prescription_create": (
            ({"enp": "7707536455681514", "patient_name": "Иванов Пётр"},),
            (({"enp": "123", "patient_name": "Иванов Пётр"}, "enp_format"),),
        ),
        "marketplace_order_get": (
            ({"order_id": "oz-123456"},),
            (({"order_id": "!"}, "id_format"),),
        ),
        "loyalty_customer_get": (
            ({"card_number": "376104250021234569"},),
            (({"card_number": "376104250021234560"}, "loyalty_card_checksum"),),
        ),
        "loyalty_card_bind": (
            ({"card_number": "376104250021234569", "customer_name": "Иванов Пётр"},),
            (({"card_number": "123", "customer_name": "Иванов Пётр"}, "loyalty_card_format"),),
        ),
        "fiscal_receipt_create": (
            ({"customer": {"full_name": "Павлова Тамара", "email": "pavlova@mail.ru"}},),
            (({"customer": {"full_name": "Павлова Тамара"}}, "contact_required"),),
        ),
        "cdek_order_info": (
            ({"order_id": "cdek-12345"},),
            (({"order_id": "!"}, "id_format"),),
        ),
        "osago_policy_check": (
            ({"policy_number": "ХХХ 0123456789"}, {"vin": "XTAGFK330LY123456"}),
            (({"policy_number": "ХХХ 012345678"}, "osago_format"),
             ({}, "exactly_one_key")),
        ),
        "insurance_claim_create": (
            ({"policy_number": "ХХХ 0123456789"},),
            (({"policy_number": "123"}, "osago_format"),),
        ),
        "traffic_fines_check": (
            ({"sts_number": "77 12 345678"},),
            (({"sts_number": "771234567"}, "sts_format"),),
        ),
        "epts_status_get": (
            ({"epts_number": "164301000000016"}, {"vin": "XTAGFK330LY123456"}),
            (({"epts_number": "164301000000017"}, "epts_checksum"),
             ({}, "exactly_one_key")),
        ),
        "driver_license_check": (
            ({"license_number": "99 12 345678"},),
            (({"license_number": "991234567"}, "driver_license_format"),),
        ),
        "subscriber_profile_get": (
            ({"phone": "+79164021187"}, {"account": "123456789012"}),
            (({}, "exactly_one_key"),),
        ),
        "sim_replace_request": (
            ({"iccid": "8970102000000123458"},),
            (({"iccid": "8970102000000123457"}, "iccid_checksum"),),
        ),
        "egrn_extract_get": (
            ({"cadastral_number": "77:01:0001001:1234"},),
            (({"cadastral_number": "77:01:1001:1234"}, "cadastral_format"),),
        ),
        "gis_gkh_account_get": (
            ({"els": "60АА000593-01"},),
            (({"els": "60AA000593-01"}, "els_format"),),
        ),
        "pms_booking_get": (
            ({"booking_id": "bk-12345"},),
            (({"booking_id": "!"}, "id_format"),),
        ),
        "guest_arrival_notify": (
            ({"full_name": "Иванов Пётр", "document_number": "75 1234567"},),
            (({"full_name": "Иванов Пётр", "document_number": "75123456"},
              "intl_passport_format"),),
        ),
        "flight_order_get": (
            ({"pnr": "2ZYVAL"},),
            (({"pnr": "2ZYV"}, "pnr_format"),),
        ),
        "hr_employee_get": (
            ({"tab_number": "004512"},),
            (({"tab_number": "4512"}, "tab_number_format"),),
        ),
        "resume_get": (
            ({"resume_id": "r-12345"},),
            (({"resume_id": "!"}, "id_format"),),
        ),
        "payroll_card_registry": (
            ({"employees": [{"tab_number": "004512", "account": "40817810515881399869"}]},),
            (({"employees": []}, "array_required"),
             ({"employees": [{"tab_number": "45", "account": "40817810515881399869"}]},
              "tab_number_format")),
        ),
        "arbitration_case_search": (
            ({"case_number": "А31-2840/2013"},),
            (({"case_number": "31-2840/2013"}, "case_format"),),
        ),
        "probate_case_search": (
            ({"deceased_name": "Иванов Пётр"},),
            (({"deceased_name": "   "}, "name_format"),),
        ),
        "fns_inn_lookup": (
            ({"full_name": "Иванов Пётр Сергеевич", "birth_date": "1987-03-14"},),
            (({"full_name": "Иванов", "birth_date": "14.03.1987"}, "date_not_iso8601"),),
        ),
        "npd_status_check": (
            ({"inn": "500100732259"},),
            (({"inn": "500100732258"}, "inn_checksum"),),
        ),
        "budget_charges_find": (
            ({"inn": "500100732259"},),
            (({"inn": "500100732258"}, "inn_checksum"),),
        ),
        "diploma_registry_check": (
            ({"diploma_number": "107724 0001234"},),
            (({"diploma_number": "107724000123"}, "diploma_format"),),
        ),
        "exam_results_check": (
            ({"reg_code": "EG-2025-123"},),
            (({"reg_code": "x" * 31}, "reg_code_format"),),
        ),
        "lms_user_get": (
            ({"query": "Иванов"},),
            (({"query": "   "}, "empty_query"),),
        ),
        "dwh_sql_query": (
            ({"sql": "SELECT * FROM t WHERE phone = '+79164021187'"},),
            (({"sql": "   "}, "empty_query"),),
        ),
        "bi_chart_export": (
            ({"chart_id": "ch-12345"},),
            (({"chart_id": "!"}, "id_format"),),
        ),
        "audience_segment_upload": (
            ({"customers": [{"customer_id": "c-000184523"}]},),
            (({"customers": []}, "array_required"),
             ({"customers": [{"customer_id": "x" * 41}]}, "customer_id_format")),
        ),
        "web_visits_export": (
            ({"date_from": "2026-01-01", "date_to": "2026-01-31"},),
            (({"date_from": "01.01.2026", "date_to": "2026-01-31"}, "date_not_iso8601"),),
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


CHECKS = (test_no_pseudex, test_specs_wellformed, test_no_collision,
          test_unschemed_named, test_parsers_good_bad)


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
