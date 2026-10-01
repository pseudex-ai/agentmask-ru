"""AgentPII-RU v6 — build the full 500-case corpus from `plan_v6`.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.scenarios6.build_full

WHAT THIS FILE DOES. It instantiates every `plan_v6.PlanRow` into a `CaseV5`
through `new_builder_v6`/`CaseBuilderV6`. A conversational row (one type) is the
v5 base loop; a record/dossier row (up to six types, a light industry may repeat
one type) reads every type back through its own TOOLS_V6 tool in ONE turn — the
`parallel` behaviour. The value source is always `gen_v6.generate`, never a
search of a finished string.

ONE APPEARANCE IS TWO ELEMENTS. A case seeds the value (the mock's stored copy)
AND the user dictates it (the message copy), so one appearance mints two items —
34 appearances are ≥ 60 elements with no invented second person.

NOTHING HERE IMPORTS `pseudex` OR `licensing`, AND NOTHING HERE SEARCHES A
FINISHED STRING.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace

from bench.agentpii4 import pools
from bench.agentpii4.pools import Rendered
from bench.agentpii4.schema import Message, Negative, TraceRow
from bench.agentpii4.scenarios.common import ctx_for
from bench.agentpii5 import build_v6, contracts_v6, gen_v6, pii_types, schema_v6
from bench.agentpii5.contracts import (CaseV5, ForcedError, Hop, ReturnExpectation)
from bench.agentpii5.scenarios5 import common as v5
from bench.agentpii5.scenarios5.common import (answer_hop, arg_hop, opener, seeded, told,
                                               tool_hop, user_hop)
from bench.agentpii5.scenarios6 import plan_v6
from bench.agentpii5.scenarios6.common6 import (new_builder_v6, procedure_records,
                                                skeleton_ids)
from bench.agentpii5.tools_v6 import TOOLS_V6, V6_META

SEED: int = 6
PROVENANCE: str = "documented-procedure"


@dataclass(frozen=True)
class Recipe:
    """Everything a behaviour needs to cross one v6 type through the mock.

    `read_tool` is the tool whose result carries the type back (IN/tool); `lookup`
    is the argument leaf the agent fills to ask for it (OUT/tool_arg); `result`
    is the result leaf the value comes back on; `field` is the seed record field
    (an item at a non-field_keys seed is a bare [K] positive — K6-16)."""

    type_id: str
    role: str
    read_tool: str
    lookup: str
    result: str
    field: str
    return_form: str
    cues: tuple[str, ...]
    note: str


def _spec(type_id: str) -> pii_types.TypeSpec:
    for spec in pii_types.TYPE_REGISTRY:
        if spec.id == type_id:
            return spec
    raise ValueError(f"{type_id!r} is not a registered type")


# The 55 admitted types' recipes, read off tools_v6's FieldSpecs and mock_v6's
# stored field names. `field` is a registry `field_keys` entry the mock renders.
RECIPES: dict[str, Recipe] = {
    "OGRNIP": Recipe("OGRNIP", "crm", "crm_requisite_get", "ogrnip", "requisite.rq_ogrnip", "ogrnip", "single", ("ОГРНИП", "огрнип", "рег. номер ИП"), ""),
    "BANK_ACCOUNT": Recipe("BANK_ACCOUNT", "bank", "bank_accounts_list", "client_id", "Data.Account[].AccountDetails[].identification", "account", "list", ("счёт", "счет", "расчётный счёт"), ""),
    "CADASTRAL_NUMBER": Recipe("CADASTRAL_NUMBER", "gov", "egrn_extract_get", "cadastral_number", "object.cadastral_number", "cadastral_number", "nested", ("кадастровый номер", "КН", "кадастр"), ""),
    "DIPLOMA_NUMBER": Recipe("DIPLOMA_NUMBER", "gov", "diploma_registry_check", "blank_number", "document.number", "diploma_number", "single", ("диплом", "серия и номер диплома", "документ об образовании"), ""),
    "EMPLOYEE_TAB_NUMBER": Recipe("EMPLOYEE_TAB_NUMBER", "crm", "hr_employee_get", "tab_number", "value[].ТабельныйНомер", "tab_number", "single", ("табельный номер", "таб. №", "табельный"), ""),
    "EPTS_NUMBER": Recipe("EPTS_NUMBER", "gov", "epts_status_get", "epts_number", "epts", "epts", "single", ("ЭПТС", "электронный ПТС", "электронный паспорт"), ""),
    "GIS_ZHKH_ELS": Recipe("GIS_ZHKH_ELS", "gov", "gis_gkh_account_get", "els", "account.els", "els", "single", ("ЕЛС", "единый лицевой счёт", "ИЖКУ"), ""),
    "ICCID": Recipe("ICCID", "crm", "sim_replace_request", "new_iccid", "iccid", "iccid", "single", ("ICCID", "номер сим-карты", "номер SIM"), ""),
    "INTL_PASSPORT": Recipe("INTL_PASSPORT", "gov", "flight_order_get", "flight_order_id", "data.travelers[].documents[].number", "passport_number", "nested", ("загранпаспорт", "загран", "паспорт для выезда"), ""),
    "LOAN_CONTRACT_NUMBER": Recipe("LOAN_CONTRACT_NUMBER", "bank", "debtor_card_get", "contract_number", "loan.contract", "contract_number", "nested", ("кредитный договор", "договор займа", "номер договора"), ""),
    "LOYALTY_CARD_NUMBER": Recipe("LOYALTY_CARD_NUMBER", "crm", "loyalty_customer_get", "discount_card", "customer.discountCards[].ids.number", "card_number", "single", ("карта лояльности", "бонусная карта", "дисконтная карта"), ""),
    "OMS_ENP": Recipe("OMS_ENP", "clinic", "oms_policy_find", "enp", "person.enp", "enp", "single", ("полис", "полис ОМС", "ЕНП"), ""),
    "OSAGO_POLICY": Recipe("OSAGO_POLICY", "gov", "osago_policy_check", "policy", "policy.number", "osago_number", "single", ("ОСАГО", "полис ОСАГО", "автогражданка"), ""),
    "VIN": Recipe("VIN", "gov", "osago_policy_check", "vin", "vehicle.vin", "vin", "single", ("VIN", "ВИН", "вин-код"), ""),
    "IBAN": Recipe("IBAN", "crm", "crm_requisite_get", "iban", "requisite.rq_iban", "iban", "single", ("IBAN", "айбан", "международный номер счёта"), ""),
    "ESIA_OID": Recipe("ESIA_OID", "gov", "esia_roles_get", "prn_oid", "personOid", "oid", "single", ("ЕСИА", "идентификатор ЕСИА", "Госуслуги ID"), ""),
    "ACCESS_PASS_NUMBER": Recipe("ACCESS_PASS_NUMBER", "directory", "uhppote_card_get", "cardNumber", "cardNumber", "card_number", "single", ("пропуск", "номер пропуска", "карта доступа"), ""),
    "APP_DEVICE_ID": Recipe("APP_DEVICE_ID", "crm", "appmetrica_device_id_lookup", "appmetrica_device_id", "appmetrica_device_id", "appmetrica_device_id", "single", ("device id", "идентификатор устройства", "appmetrica_device_id"), ""),
    "ARBITRAZH_CASE_NO": Recipe("ARBITRAZH_CASE_NO", "search", "arbitration_case_search", "case_number", "cases[].number", "number", "list", ("дело №", "по делу", "арбитражное дело"), ""),
    "BIRTH_CERT": Recipe("BIRTH_CERT", "government", "birth_cert_fetch", "birth_cert_number", "record.birth_cert_number", "birth_cert_number", "single", ("свидетельство о рождении", "св-во о рождении", "СОР"), ""),
    "CDP_CUSTOMER_ID": Recipe("CDP_CUSTOMER_ID", "crm", "audience_segment_upload", "file.rows[].external_id", "segment.ids[].external_id", "external_id", "single", ("ID клиента", "клиентский ID", "customer id"), ""),
    "CIVIL_ACT_CERT": Recipe("CIVIL_ACT_CERT", "government", "civil_act_fetch", "certificate_number", "record.certificate_number", "certificate_number", "single", ("свидетельство о браке", "о смерти", "о расторжении брака"), ""),
    "COURT_CASE_NO_SOU": Recipe("COURT_CASE_NO_SOU", "files", "court_document_fetch", "case_number", "text", "case_number", "free_text", ("дело №", "гражданское дело", "судебный приказ №"), ""),
    "COURT_CASE_UID": Recipe("COURT_CASE_UID", "search", "court_case_fetch", "case_uid", "case.case_uid", "case_uid", "single", ("УИД", "уникальный идентификатор дела"), ""),
    "CREDIT_SUBJECT_CODE": Recipe("CREDIT_SUBJECT_CODE", "bank", "credit_subject_check", "subject_code", "record.subject_code", "subject_code", "single", ("код субъекта", "код субъекта кредитной истории", "код КИ"), ""),
    "DMS_POLICY": Recipe("DMS_POLICY", "clinic", "dms_policy_find", "dms_policy", "policy.dms_policy", "dms_policy", "single", ("ДМС", "полис ДМС", "добровольное медицинское"), ""),
    "DRIVER_LICENSE": Recipe("DRIVER_LICENSE", "government", "driver_license_check", "license_number", "license", "license", "single", ("водительское удостоверение", "ВУ", "права"), ""),
    "ELN_NUMBER": Recipe("ELN_NUMBER", "clinic", "eln_get", "ln_code", "data.row.lnCode", "ln_code", "nested", ("ЭЛН", "больничный", "листок нетрудоспособности"), ""),
    "EMPLOYMENT_CONTRACT_NUMBER": Recipe("EMPLOYMENT_CONTRACT_NUMBER", "crm", "employment_contract_get", "employment_contract_number", "contract.employment_contract_number", "employment_contract_number", "single", ("трудовой договор", "ТД №", "номер трудового договора"), ""),
    "EXEC_DOC_NO": Recipe("EXEC_DOC_NO", "government", "exec_doc_check", "writ_number", "writ.writ_number", "writ_number", "single", ("исполнительный лист", "ИЛ", "серия ФС"), ""),
    "E_TICKET_NUMBER": Recipe("E_TICKET_NUMBER", "calendar", "e_ticket_issue", "ticket_number", "ticket.ticket_number", "ticket_number", "single", ("электронный билет", "номер билета", "e-ticket"), ""),
    "FSSP_IP_NO": Recipe("FSSP_IP_NO", "government", "fssp_proceedings_search", "ip_number", "result[].exe_production", "ip_number", "list", ("ИП №", "исполнительное производство", "номер ИП"), ""),
    "IMEI": Recipe("IMEI", "directory", "device_provisioning_find", "deviceIdentifier", "devices[].deviceIdentifier", "imei", "list", ("вот номер", "проверьте номер"), ""),
    "IMSI": Recipe("IMSI", "crm", "omnihss_subscriber_get", "imsi", "sim.imsi", "imsi", "single", ("IMSI", "международный идентификатор абонента"), ""),
    "INSURANCE_CLAIM_NUMBER": Recipe("INSURANCE_CLAIM_NUMBER", "bank", "insurance_claim_status", "claim_number", "claim.claim_number", "claim_number", "single", ("номер убытка", "убыток №", "страховое дело"), ""),
    "IP_ADDRESS": Recipe("IP_ADDRESS", "search", "ip_api_lookup", "query", "query", "ip", "single", ("IP", "айпи", "ip-адрес"), ""),
    "KASKO_POLICY": Recipe("KASKO_POLICY", "bank", "kasko_policy_find", "kasko_policy", "policy.kasko_policy", "kasko_policy", "single", ("КАСКО", "полис КАСКО", "каско"), ""),
    "LOAN_UID": Recipe("LOAN_UID", "bank", "credit_report_request", "uid", "contracts[].uid", "loan_uid", "nested", ("УИд", "УИД", "уникальный идентификатор договора"), ""),
    "LOGIN": Recipe("LOGIN", "directory", "moodle_user_by_username", "values", "[].username", "username", "list", ("логин", "имя пользователя", "username"), ""),
    "MAC": Recipe("MAC", "search", "mikrotik_dhcp_lease_get", "mac-address", "mac-address", "mac", "single", ("MAC", "мак-адрес", "физический адрес"), ""),
    "MEDCARD_NUMBER": Recipe("MEDCARD_NUMBER", "clinic", "medcard_lookup", "med_card_number", "card.med_card_number", "med_card_number", "single", ("медкарта", "медицинская карта", "амбулаторная карта"), ""),
    "METRICA_CLIENT_ID": Recipe("METRICA_CLIENT_ID", "crm", "metrica_offline_conversion_upload", "ClientId", "ClientId", "ClientId", "single", ("ClientID", "client id", "_ym_uid"), ""),
    "MILITARY_ID": Recipe("MILITARY_ID", "crm", "military_id_register", "military_id", "record.military_id", "military_id", "single", ("военный билет", "военник", "в/б"), ""),
    "MOBILE_AD_ID": Recipe("MOBILE_AD_ID", "crm", "appmetrica_event_import", "google_aid", "google_aid", "google_aid", "single", ("GAID", "IDFA", "рекламный идентификатор"), ""),
    "PNR": Recipe("PNR", "calendar", "flight_order_manage_get", "flight_order_id", "data.associatedRecords[].reference", "pnr", "nested", ("PNR", "номер брони", "код бронирования"), ""),
    "PRESCRIPTION_NUMBER": Recipe("PRESCRIPTION_NUMBER", "clinic", "e_prescription_create", "prescription_id", "prescription.number", "prescription_id", "single", ("рецепт", "серия рецепта", "номер рецепта"), ""),
    "PTS_NUMBER": Recipe("PTS_NUMBER", "government", "pts_vehicle_get", "pts_number", "vehicle.pts_number", "pts_number", "single", ("ПТС", "паспорт транспортного средства", "паспорт ТС"), ""),
    "REFERRAL_NUMBER": Recipe("REFERRAL_NUMBER", "clinic", "referral_find", "referral_id", "referral.referral_id", "referral_id", "single", ("направление", "номер направления", "электронное направление"), ""),
    "RESIDENCE_PERMIT": Recipe("RESIDENCE_PERMIT", "government", "residence_permit_check", "residence_permit", "record.residence_permit", "residence_permit", "single", ("вид на жительство", "ВНЖ", "внж"), ""),
    "SCHOOL_CERT_NUMBER": Recipe("SCHOOL_CERT_NUMBER", "government", "school_cert_verify", "attestat_number", "document.attestat_number", "attestat_number", "single", ("аттестат", "номер аттестата", "аттестат о среднем общем образовании"), ""),
    "STS_NUMBER": Recipe("STS_NUMBER", "government", "traffic_fines_check", "sts", "fines[].sts", "sts", "list", ("СТС", "свидетельство о регистрации ТС", "техпаспорт"), ""),
    "STUDENT_ID_NUMBER": Recipe("STUDENT_ID_NUMBER", "directory", "lms_user_get", "values", "[].idnumber", "idnumber", "list", ("студенческий билет", "студбилет", "номер студенческого"), ""),
    "SUBSCRIBER_ACCOUNT": Recipe("SUBSCRIBER_ACCOUNT", "crm", "subscriber_profile_get", "personal_account", "contract.personalAccount", "personal_account", "nested", ("лицевой счёт", "л/с", "account id"), ""),
    "UIN": Recipe("UIN", "government", "gis_gmp_charge_find", "SupplierBillID", "fines[].uin", "uin", "list", ("УИН", "уникальный идентификатор начисления", "номер постановления"), ""),
    "UTILITY_ACCOUNT": Recipe("UTILITY_ACCOUNT", "government", "gis_gkh_utility_account_get", "AccountID", "account.personal_account", "personal_account", "single", ("лицевой счёт", "л/с", "номер лицевого счёта"), ""),
}

# The recipe's `role` is a tool vertical; the v4 system prompt needs one of its
# six personas. Normalise the aliases so `new_builder_v6` never sees an unknown
# role.
_ROLE_ALIAS: dict[str, str] = {
    "government": "gov", "directory": "crm", "search": "gov", "files": "bank",
    "calendar": "callcenter", "support": "callcenter", "messaging": "callcenter",
}
for _tid, _r in list(RECIPES.items()):
    if _r.role in _ROLE_ALIAS:
        RECIPES[_tid] = replace(_r, role=_ROLE_ALIAS[_r.role])
    if not _r.note:
        RECIPES[_tid] = replace(RECIPES[_tid], note=f"{_tid} -> {_r.read_tool}")


# The chain pairs: a READ tool whose ONE result returns two admitted types, so a
# `sequential_chain` row spends one case on two type-slots. `second_result` is
# the partner's leaf on the READER; `write_tool`/`write_path` is the DIFFERENT
# tool the partner value feeds (R12: an OUT hop sourced by another tool's IN).
CHAIN_SPECS: dict[tuple[str, str], dict[str, str]] = {
    ("OSAGO_POLICY", "VIN"): {"second_result": "vehicle.vin",
                              "write_tool": "insurance_claim_create", "write_path": "vehicle.vin"},
    ("EPTS_NUMBER", "VIN"): {"second_result": "vin",
                             "write_tool": "insurance_claim_create", "write_path": "vehicle.vin"},
    ("IBAN", "OGRNIP"): {"second_result": "requisite.rq_ogrnip",
                         "write_tool": "crm_requisite_set", "write_path": "ogrnip"},
}


def _chain_case(ctx, first: Recipe, second: Recipe, industry: str) -> CaseV5:
    identity = "p0"
    spec = CHAIN_SPECS[(first.type_id, second.type_id)]
    write_tool, write_path = spec["write_tool"], spec["write_path"]
    second_result = spec["second_result"]
    tools, reachable = _offer(industry, (first,))
    tools = tuple(sorted(set(tools) | {write_tool}))
    builder = new_builder_v6(ctx, first.role, tools, tools, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{first.type_id}:{ctx.index}",
                             note=f"цепочка {first.type_id}->{second.type_id}",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    a = _mint(builder, first.type_id)
    b = _mint(builder, second.type_id)
    fields = {first.field: a.surface, second.field: b.surface}
    typed = {first.field: (first.type_id, identity, a),
             second.field: (second.type_id, identity, b)}
    row = seeded(builder.v5, f"rec-{ctx.index}", "v6_record", fields, typed)

    draft = builder.draft()
    draft.say(opener(ctx)).say(first.cues[0].lower())
    draft.value("val", _dictated(a))
    draft.say("и").say(second.cues[0].lower())
    draft.value("b", _dictated(b))
    draft.punct(".")
    turn, said = told(builder.v5, draft,
                      {"val": (first.type_id, identity, "required", False),
                       "b": (second.type_id, identity, "required", False)})

    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, first.read_tool, 0, first.lookup, 0, ""))
    builder.declare_hop(tool_hop(row[first.field], 2, turn, first.read_tool, 0, first.result))
    builder.declare_hop(tool_hop(row[second.field], 3, turn, first.read_tool, 0, second_result))
    builder.declare_hop(arg_hop(row[second.field], 4, turn, write_tool, 0, write_path, 3, ""))
    builder.declare_hop(answer_hop(row[second.field], 5, turn, 3, False))
    builder.expect_return(ReturnExpectation(first.read_tool, 0, first.return_form,
                                            (row[first.field], row[second.field])))
    return builder.build("sequential_chain")


def _mint(builder, type_id: str) -> Rendered:
    """Mint a value and guarantee non-empty `parts` (a whole canonical keeps the
    ground truth complete without inventing a digit run the value lacks).

    The returned `surface` is the value in the TOOL'S OWN NOTATION — the formatted
    form the parser demands (UUID with dashes, cadastral with colons, IP with dots,
    «series number» with its space). The SEED stores this surface, so a format-
    validating parser sees what it genuinely requires; the DICTATED message surface
    is derived separately by `_dictated` (the canonical stripped of sentence
    punctuation), and both share the canonical identity."""
    rendered = builder.mint(type_id)
    if rendered.parts:
        return Rendered(rendered.surface, rendered.canonical, rendered.spoken,
                        dict(rendered.parts))
    return Rendered(rendered.surface, rendered.canonical, rendered.spoken,
                    {"whole": rendered.canonical})


def _dictated(rendered: Rendered) -> Rendered:
    """The DICTATED message surface: the canonical stripped of sentence punctuation
    `[.,;:!?]` — the `voice_itn` register forbids it (an IP «188.201.146.147» is
    dictated as «188201146147») — while the canonical keeps its identity and the
    mock still matches by digit signature. The seed keeps the tool's formatted
    notation; the message keeps this stripped form."""
    surface = re.sub(r"[.,;:!?]", "", rendered.canonical or rendered.surface)
    return Rendered(surface, rendered.canonical, rendered.spoken, dict(rendered.parts))


def _seeded_item(builder, record_id: str, recipe: Recipe, rendered: Rendered,
                 identity: str) -> str:
    fields = {recipe.field: rendered.surface}
    typed = {recipe.field: (recipe.type_id, identity, rendered)}
    row = seeded(builder.v5, record_id, "v6_record", fields, typed)
    return row[recipe.field]


def _industry_tools(industry: str) -> tuple[str, ...]:
    names = sorted({spec.base.name for spec in TOOLS_V6
                    if V6_META[spec.base.name].industry == industry})
    return tuple(names)


def _offer(industry: str, recipes) -> tuple[tuple[str, ...], tuple[str, ...]]:
    readers = sorted({r.read_tool for r in recipes})
    names = sorted(set(_industry_tools(industry)) | set(readers))
    return names, names


# --- the base loop (single behaviour) --------------------------------------------

def _base_case(ctx, recipe: Recipe, industry: str, behaviour: str) -> CaseV5:
    identity = "p0"
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note, procedure_ref="requisites-115fz",
                             procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)

    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", _dictated(rendered))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, identity, "required", False)})

    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    return builder.build(behaviour)


def _bare_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    """A bare [C] positive (IMEI): the value is dictated with no cue and stored
    at the tool's argument leaf (not a `field_keys` entry), so BOTH the message
    item and the seed item are bare — K6-16's ≥20% floor for a [C] type."""
    identity = "p0"
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — голое значение",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    fields = {recipe.lookup: rendered.surface}
    typed = {recipe.lookup: (recipe.type_id, identity, rendered)}
    row = seeded(builder.v5, f"rec-{ctx.index}", "v6_record", fields, typed)
    item = row[recipe.lookup]

    draft = builder.draft()
    draft.say(opener(ctx)).say("проверьте вот это")
    draft.value("val", _dictated(rendered))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, identity, "required", False)})

    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    return builder.build("single")


# --- the record/dossier case (parallel behaviour) --------------------------------

def _dossier_case(ctx, type_ids: tuple[str, ...], industry: str) -> CaseV5:
    """A record carrying up to six types, each read back through its own tool in
    ONE turn. A type may repeat (a telecom record listing three SIMs), so a light
    industry's two types fill a six-slot record without inventing people."""
    identity = "p0"
    recipes = [RECIPES[t] for t in type_ids]
    tools, reachable = _offer(industry, recipes)
    builder = new_builder_v6(ctx, "crm", tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"dossier:{ctx.index}",
                             note="запись/документ: несколько типов",
                             procedure_ref="requisites-115fz", procedures=procedure_records())

    # mint + seed one item per slot, in order.
    rendered: list[tuple[Recipe, Rendered]] = []
    seed_ids: list[str] = []
    for position, recipe in enumerate(recipes):
        r = _mint(builder, recipe.type_id)
        item = _seeded_item(builder, f"rec-{ctx.index}-{position}", recipe, r, identity)
        rendered.append((recipe, r))
        seed_ids.append(item)

    # the user dictates every value, each cued by its own type's words.
    draft = builder.draft()
    draft.say(opener(ctx))
    typed: dict[str, tuple[str, str, str, bool]] = {}
    for position, (recipe, r) in enumerate(rendered):
        draft.say(recipe.cues[0].lower())
        draft.value(f"v{position}", _dictated(r))
        typed[f"v{position}"] = (recipe.type_id, identity, "required", False)
    draft.punct(".")
    turn, said = told(builder.v5, draft, typed)

    # `call_ordinal` is the ordinal of that TOOL's calls inside the turn
    # (contracts.Hop), not the position in the fan-out. Several recipes share one
    # read tool (OSAGO_POLICY/VIN → osago_policy_check, IBAN/OGRNIP →
    # crm_requisite_get), so the global `position` disagreed with
    # `observe.call_for_hop`, which filters calls by tool and indexes by this
    # ordinal — 950 required OUT/tool_arg hops read `absent` for no reason but the
    # index. The per-tool ordinal is computed once and used identically in the
    # OUT hop, the IN/tool hop and the `ReturnExpectation`, so all three stay
    # keyed on the same value.
    ordinals: list[int] = []
    seen: dict[str, int] = {}
    for recipe, _ in rendered:
        ordinal = seen.get(recipe.read_tool, 0)
        seen[recipe.read_tool] = ordinal + 1
        ordinals.append(ordinal)

    hops: list[Hop] = []
    for position, (recipe, _) in enumerate(rendered):
        hops.append(user_hop(said[f"v{position}"], len(hops), turn))
    for position, (recipe, _) in enumerate(rendered):
        hops.append(arg_hop(said[f"v{position}"], len(hops), turn, recipe.read_tool,
                            ordinals[position], recipe.lookup, 0, "g"))
    for position, (recipe, _) in enumerate(rendered):
        hops.append(tool_hop(seed_ids[position], len(hops), turn, recipe.read_tool,
                             ordinals[position], recipe.result))
    first_in = len(rendered) * 2  # hop index of the first tool_hop
    hops.append(answer_hop(seed_ids[0], len(hops), turn, first_in, False))

    for hop in hops:
        builder.declare_hop(hop)
    for position, (recipe, _) in enumerate(rendered):
        builder.expect_return(ReturnExpectation(recipe.read_tool, ordinals[position],
                                                recipe.return_form, (seed_ids[position],)))
    return builder.build("parallel")


# --- the retry / memory / fan-out behaviours (single type) ------------------------

def _retry_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    identity = "p0"
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — отказ по форме, повтор",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", _dictated(rendered))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, identity, "required", False)})
    builder.force_error(ForcedError(recipe.read_tool, 0, "format", item,
                                    f"значение {{value}} не прошло проверку формата"))
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, "error.subject"))
    builder.declare_hop(arg_hop(said["val"], 3, turn, recipe.read_tool, 1, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 4, turn, recipe.read_tool, 1, recipe.result))
    builder.declare_hop(answer_hop(item, 5, turn, 4, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 1, recipe.return_form, (item,)))
    return builder.build("retry_same_tool")


def _memory_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    identity = "p0"
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, "synthetic",
                             primary_identity=identity, cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — анафора")
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, identity)
    d1 = builder.draft()
    d1.say(opener(ctx)).say("мой").say(recipe.cues[0].lower())
    d1.value("val", _dictated(rendered))
    d1.punct(".")
    turn1, said = told(builder.v5, d1, {"val": (recipe.type_id, identity, "required", False)})
    d2 = builder.draft()
    d2.say("проверьте по нему и скажите что получилось")
    d2.punct(".")
    turn2, _ = told(builder.v5, d2, {})
    builder.declare_hop(user_hop(said["val"], 0, turn1))
    builder.declare_hop(arg_hop(said["val"], 1, turn2, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn2, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn2, 2, False))
    from bench.agentpii5.scenarios5.common import MemorySpec
    builder.remember(MemorySpec(item_id=said["val"], first_turn=turn1, recall_turn=turn2,
                                anaphora="pronoun"))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    return builder.build("memory_anaphora")


def _same_tool_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — два лица, один инструмент",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    a = _mint(builder, recipe.type_id)
    b = _mint(builder, recipe.type_id)
    ra = _seeded_item(builder, f"rec-{ctx.index}-a", recipe, a, "p0")
    rb = _seeded_item(builder, f"rec-{ctx.index}-b", recipe, b, "p1")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("a", _dictated(a))
    draft.say("и ещё")
    draft.value("b", _dictated(b))
    draft.punct(".")
    turn, said = told(builder.v5, draft,
                      {"a": (recipe.type_id, "p0", "required", False),
                       "b": (recipe.type_id, "p1", "required", False)})
    builder.declare_hop(user_hop(said["a"], 0, turn))
    builder.declare_hop(user_hop(said["b"], 1, turn))
    builder.declare_hop(arg_hop(said["a"], 2, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(ra, 3, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(said["b"], 4, turn, recipe.read_tool, 1, recipe.lookup, 1, ""))
    builder.declare_hop(tool_hop(rb, 5, turn, recipe.read_tool, 1, recipe.result))
    builder.declare_hop(answer_hop(ra, 6, turn, 3, False))
    builder.declare_hop(answer_hop(rb, 7, turn, 5, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (ra,)))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 1, recipe.return_form, (rb,)))
    return builder.build("same_tool_other_target")


def _fanout_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    from bench.agentpii5.contracts import PickSpec
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — список, выбор по значению",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    a = _mint(builder, recipe.type_id)
    b = _mint(builder, recipe.type_id)
    ra = _seeded_item(builder, f"rec-{ctx.index}-a", recipe, a, "p0")
    rb = _seeded_item(builder, f"rec-{ctx.index}-b", recipe, b, "p1")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("a", _dictated(a))
    draft.say("найди и выбери первого")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"a": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["a"], 0, turn))
    builder.declare_hop(arg_hop(said["a"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(ra, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(ra, 3, turn, recipe.read_tool, 0, recipe.lookup, 2, ""))
    builder.declare_hop(answer_hop(ra, 4, turn, 2, False))
    # A v6 READ tool answers ONE record for a key lookup, not a ranked list — so
    # the result carries only the picked candidate `ra`; `rb` stays a PickSpec
    # candidate the model must NOT act on, but it is in no result leaf.
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (ra,)))
    builder.set_pick(PickSpec(list_tool=recipe.read_tool, candidate_identities=("p0", "p1"),
                              target_identity="p0", act_tool=recipe.read_tool))
    return builder.build("fanout_pick")


def _branch_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    from bench.agentpii5.contracts import BranchSpec
    tools, reachable = _offer(industry, (recipe,))
    else_tool = next((t for t in tools if t != recipe.read_tool), recipe.read_tool)
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — ветвление",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", _dictated(rendered))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.set_branch(BranchSpec(probe_tool=recipe.read_tool, seed_present=True,
                                  then_tool=recipe.read_tool, else_tool=else_tool))
    return builder.build("branching")


def _loop_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    from bench.agentpii5.contracts import LoopSpec
    tools, reachable = _offer(industry, (recipe,))
    builder = new_builder_v6(ctx, recipe.role, tools, reachable, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — человек в цикле",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    d1 = builder.draft()
    d1.say(opener(ctx)).say(recipe.cues[0].lower())
    d1.value("val", _dictated(rendered))
    d1.say("покажите что нашли")
    d1.punct(".")
    turn1, said = told(builder.v5, d1, {"val": (recipe.type_id, "p0", "required", False)})
    d2 = builder.draft()
    d2.say("да это оно действуйте")
    d2.punct(".")
    turn2, _ = told(builder.v5, d2, {})
    builder.declare_hop(user_hop(said["val"], 0, turn1))
    builder.declare_hop(arg_hop(said["val"], 1, turn1, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn1, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(answer_hop(item, 3, turn1, 2, False))
    builder.declare_hop(arg_hop(item, 4, turn2, recipe.read_tool, 0, recipe.lookup, 2, ""))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.set_loop(LoopSpec(find_tool=recipe.read_tool, show_turn=turn1, confirm_turn=turn2,
                              confirm_phrase="да это оно действуйте", act_tool=recipe.read_tool))
    return builder.build("user_in_loop")


def _rag_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    from bench.agentpii5.contracts import RagSpec
    tools, reachable = _offer(industry, (recipe,))
    tools = tuple(sorted(set(tools) | {"kb_search"}))
    builder = new_builder_v6(ctx, recipe.role, tools, tools, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — поиск по базе",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    foreign = _mint(builder, recipe.type_id)
    # The mock renders a chunk template on `{[a-z_]+}` slot names only, AND K6-16
    # keys a seed item by its field-key path — so the foreign value sits under the
    # first LOWERCASE field key (case_number, external_id, client_id, ln_code …),
    # never a capitalised one like ClientId/lnCode.
    slot = next((key for key in _spec(recipe.type_id).field_keys
                 if re.fullmatch(r"[a-z_]+", key)), "value")
    chunk = seeded(builder.v5, f"chunk-{ctx.index}", "kb_chunks",
                   {"template": f"Заметка по теме возврат: клиент {{who}} с идентификатором {{{slot}}}",
                    "who": "другой человек", slot: foreign.surface},
                   {slot: (recipe.type_id, "p1", foreign)})
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower())
    draft.value("val", _dictated(rendered))
    draft.say("найди в базе")
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(said["val"], 3, turn, "kb_search", 0, "query", 0, ""))
    builder.declare_hop(tool_hop(chunk[slot], 4, turn, "kb_search", 0, "hits[].text"))
    builder.declare_hop(answer_hop(item, 5, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.expect_return(ReturnExpectation("kb_search", 0, "chunks", (chunk[slot],)))
    builder.set_rag(RagSpec(tool_name="kb_search", k=1, chunk_ids=(f"chunk-{ctx.index}",),
                            foreign_identities=("p1",), query_item_ids=(said["val"],)))
    return builder.build("rag")


def _document_case(ctx, recipe: Recipe, industry: str) -> CaseV5:
    from bench.agentpii5.contracts import DocumentSpec
    tools, reachable = _offer(industry, (recipe,))
    tools = tuple(sorted(set(tools) | {"file_read"}))
    builder = new_builder_v6(ctx, recipe.role, tools, tools, industry, PROVENANCE,
                             primary_identity="p0", cluster=f"{recipe.type_id}:{ctx.index}",
                             note=recipe.note + " — документ",
                             procedure_ref="requisites-115fz", procedures=procedure_records())
    rendered = _mint(builder, recipe.type_id)
    item = _seeded_item(builder, f"rec-{ctx.index}", recipe, rendered, "p0")
    draft = builder.draft()
    draft.say(opener(ctx)).say(recipe.cues[0].lower()).say("прочитай файл и проверь")
    draft.value("val", _dictated(rendered))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"val": (recipe.type_id, "p0", "required", False)})
    builder.declare_hop(user_hop(said["val"], 0, turn))
    builder.declare_hop(arg_hop(said["val"], 1, turn, recipe.read_tool, 0, recipe.lookup, 0, ""))
    builder.declare_hop(tool_hop(item, 2, turn, recipe.read_tool, 0, recipe.result))
    builder.declare_hop(arg_hop(item, 3, turn, recipe.read_tool, 0, recipe.lookup, 2, ""))
    builder.declare_hop(answer_hop(item, 4, turn, 2, False))
    builder.expect_return(ReturnExpectation(recipe.read_tool, 0, recipe.return_form, (item,)))
    builder.set_document(DocumentSpec(doc_id=f"doc-{ctx.index}", read_tool="file_read",
                                      format="free_text", record_count=1,
                                      record_ids=(f"rec-{ctx.index}",),
                                      extract_to_tool=recipe.read_tool,
                                      extracted_item_ids=(item,)))
    return builder.build("document")


# --- the one reading vertical no v6 type crosses (K6-15 K16) --------------------


def _build_one(ctx, row: plan_v6.PlanRow) -> CaseV5:
    if row.behaviour == "parallel":
        return _dossier_case(ctx, row.types, row.industry)
    if row.behaviour == "sequential_chain":
        return _chain_case(ctx, RECIPES[row.types[0]], RECIPES[row.types[1]], row.industry)
    recipe = RECIPES[row.types[0]]
    if row.bare:
        return _bare_case(ctx, recipe, row.industry)
    if row.behaviour == "retry_same_tool":
        return _retry_case(ctx, recipe, row.industry)
    if row.behaviour == "memory_anaphora":
        return _memory_case(ctx, recipe, row.industry)
    if row.behaviour == "same_tool_other_target":
        return _same_tool_case(ctx, recipe, row.industry)
    if row.behaviour == "fanout_pick":
        return _fanout_case(ctx, recipe, row.industry)
    if row.behaviour == "branching":
        return _branch_case(ctx, recipe, row.industry)
    if row.behaviour == "user_in_loop":
        return _loop_case(ctx, recipe, row.industry)
    if row.behaviour == "rag":
        return _rag_case(ctx, recipe, row.industry)
    if row.behaviour == "document":
        return _document_case(ctx, recipe, row.industry)
    return _base_case(ctx, recipe, row.industry, row.behaviour)


# --- the one reading vertical no v6 type crosses (K6-15 K16) --------------------
# Every v6 read tool crosses crm/bank/gov/clinic/directory/search/files, but the
# delivery vertical (cdek_order_info) returns only v5 NAME/PHONE — so one case
# reads a v5 NAME back through it, the same IN/tool crossing any other vertical
# gets. The plan leaves one slot for it (sums to 499).

_VERTICAL_READ: dict[str, str] = {
    "tool": "cdek_order_info", "industry": "logistics", "role": "delivery",
    "lookup": "cdek_number", "result": "entity.recipient.name", "form": "nested",
    "value": "NAME", "field": "name", "key": "PHONE", "ask": "заказ",
}


def _vertical_case(ctx, vspec: dict[str, str]) -> CaseV5:
    tool = vspec["tool"]
    identity = "p0"
    builder = new_builder_v6(ctx, vspec["role"], (tool,), (tool,), vspec["industry"],
                             "synthetic", primary_identity=identity,
                             cluster=f"{vspec['value']}:{ctx.index}",
                             note=f"вертикаль {vspec['value']} через {tool}")
    drawn = v5.draw(ctx, city=ctx.rng.choice(list(pools.CORPUS_CITIES)))
    name_r = v5.stored_name(drawn, ctx)
    phone_r = v5.stored_phone(drawn)
    stored, value_type = name_r, "NAME"
    fields = {vspec["field"]: stored.surface, vspec["lookup"]: phone_r.surface}
    typed = {vspec["field"]: (value_type, identity, stored)}
    row = seeded(builder.v5, f"vc-{ctx.index}", "v6_record", fields, typed)
    item_id = row[vspec["field"]]

    draft = builder.draft()
    draft.say(opener(ctx)).say(vspec["ask"])
    draft.value("key", v5.phone(ctx, drawn.phone))
    draft.punct(".")
    turn, said = told(builder.v5, draft, {"key": (vspec["key"], identity, "required", False)})

    builder.declare_hop(user_hop(said["key"], 0, turn))
    builder.declare_hop(arg_hop(said["key"], 1, turn, tool, 0, vspec["lookup"], 0, ""))
    builder.declare_hop(tool_hop(item_id, 2, turn, tool, 0, vspec["result"]))
    builder.declare_hop(answer_hop(item_id, 3, turn, 2, False))
    builder.expect_return(ReturnExpectation(tool, 0, vspec["form"], (item_id,)))
    return builder.build("single")


# --- the v6 negative layer (§1.6, K6-05) -----------------------------------------
# 28 families × 20 occurrences = 560 negatives laid over 500 cases: the first 60
# cases carry a second negative, the rest one — «≈1.1 negatives per case», and
# every family appears exactly 20 times. The schedule is the family order repeated
# 20 times, so the assignment is a property of the POSITION (seed-independent ids,
# seed-dependent values), never of the type a case happened to draw.

_NEG_PER_FAMILY: int = 20
_NEG_SCHEDULE: tuple[str, ...] = tuple(
    family for family in contracts_v6.V6_NEGATIVE_FAMILIES for _ in range(_NEG_PER_FAMILY))
_NEG_SECOND_AT: int = len(_NEG_SCHEDULE) - 500     # 60 cases carry a second negative


def _negatives_for(position: int, seed: int) -> tuple[tuple[str, str], ...]:
    """The `(family, value)` negatives a case at `position` carries, or () past
    the schedule (never happens — the vertical reader is position 499)."""
    if position >= 500:
        return ()
    slots = [_NEG_SCHEDULE[position]]
    if position < _NEG_SECOND_AT:
        slots.append(_NEG_SCHEDULE[500 + position])
    return tuple(
        (family, contracts_v6.neg_value(family, seed * 10_000 + position * 10 + slot))
        for slot, family in enumerate(slots))


def _attach_v6_negatives(case: CaseV5, position: int, seed: int) -> CaseV5:
    """Append the case's v6 negatives to the FIRST user message, as declared
    `Negative`s with their offsets and trace rows — the same discipline the v4
    auto-negative keeps (built, never searched). The negative sits NEXT TO the
    positive the message already dictates, so `overmask` (message) and K6-05
    read it, and `perfect._tool_results` re-renders the same values into the
    result as `neg:`-tagged slots for `overmask_result`."""
    pairs = _negatives_for(position, seed)
    if not pairs:
        return case
    base = case.base
    msg_idx = 1                                    # first user message (0 is system)
    messages = list(base.messages)
    text = messages[msg_idx].content
    trace = list(base.trace)
    negatives = list(base.negatives)
    cursor = len(text)
    for family, value in pairs:
        lead = " кстати "
        start = cursor + len(lead)
        end = start + len(value)
        # NO trailing sentence punctuation: the voice_itn register forbids
        # «.,;:!?», and the message already ends with its own opener's form.
        segment = lead + value
        text += segment
        trace.append(TraceRow(msg=msg_idx, key="", start=cursor, end=cursor + len(segment),
                              origin="literal"))
        negatives.append(Negative(value=value, start=start, end=end, msg=msg_idx,
                                  family=family, why="бизнес-идентификатор (не ПД)"))
        cursor += len(segment)
    messages[msg_idx] = Message(role="user", content=text, source=None, name="")
    return replace(case, base=replace(base, messages=tuple(messages),
                                      trace=tuple(trace), negatives=tuple(negatives)))


def build_full(seed: int = SEED) -> list[CaseV5]:
    cases: list[CaseV5] = []
    registers = _registers(seed)
    position = 0
    for row in plan_v6.PLAN_V6:
        for _ in range(row.count):
            register = registers[position % len(registers)]
            ctx = ctx_for(row.types[0], seed, position, register)
            case = _build_one(ctx, row)
            if register == "voice_itn" and position % 5 == 0:
                case = replace(case, streaming=True)
            case = _attach_v6_negatives(case, position, seed)
            cases.append(case)
            position += 1
    register = registers[position % len(registers)]
    ctx = ctx_for(_VERTICAL_READ["tool"], seed, position, register)
    case = _attach_v6_negatives(_vertical_case(ctx, _VERTICAL_READ), position, seed)
    cases.append(case)
    return cases


def _registers(seed: int) -> list[str]:
    targets = {"chat": 0.40, "voice_itn": 0.30, "sloppy": 0.20, "clean": 0.10}
    delivered = {name: 0 for name in targets}
    out: list[str] = []
    for _ in range(500):
        name = min(targets, key=lambda n: (-targets[n] / (2 * delivered[n] + 1),
                                           delivered[n], n))
        delivered[name] += 1
        out.append(name)
    import random
    random.Random(f"v6-register:{seed}").shuffle(out)
    return out


def main() -> int:
    started = time.monotonic()
    cases = build_full()
    problems = schema_v6.validate_corpus_v6(cases, "full", 500)
    print(f"build_full: {len(cases)} случаев, {time.monotonic() - started:.1f}s")
    for line in schema_v6.type_floor_table(cases, "full"):
        print(line)
    for line in problems:
        print(f"RED {line}")
    if problems:
        print("build_full: FAIL")
        return 1
    digest = build_v6.write_corpus(cases, build_v6.V6_OUT)
    build_v6.write_ladder_v6(cases, build_v6.V6_OUT)
    print(f"build_full: PASS (corpus {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
