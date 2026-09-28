# pii_types_b.py — the v6 Group B type-registry records (spec
# docs/tz-agentpii6-registry.md §1.3, cards B-01 … B-19). One frozen `TypeSpec`
# per admitted B-group candidate, in card order, EXCLUDING the four ДЕРЖИМ cards
# (B-13 EGRN_REG_NO, B-14 EGRN_REQUEST_NO, B-17 EPGU_APPLICATION_NO,
# B-19 PLEDGE_NOTICE_NO) that stay out of the corpus until the owner decides.
#
# This module is PURE and deterministic: it imports only the `TypeSpec` shape
# and the class/origin constants from `pii_types`, and nothing from `pseudex`,
# `licensing`, `contracts`, `gen_v6` or `checksum_v6`. Every field transcribes
# `prototype/bench/agentpii5/review/v6-typespec-mapping.md` (card → field) and
# `docs/tz-agentpii6.md` §5.2/§5.3/§5.5/§6.2/§9.2 (form/notation/mint/hunt).
#
# The class/checksum columns come from the mapping doc's FINAL table, which
# overrides the provisional [C?]/[K·КС] classes the card headers still show:
#   VIN → KC/iso3779 · EPTS_NUMBER → K/epts · UIN → K/uin ·
#   COURT_CASE_UID → K/mod97 · everything else → K/"".

from __future__ import annotations

from typing import Tuple

from bench.agentpii5.pii_types import (
    ORIGIN_V6,
    TYPE_CLASS_K,
    TYPE_CLASS_KC,
    TypeSpec,
)

# The fixed label lists of §5.2. `grouping` is the only per-type feature; the
# rest are one closed list shared by every type that carries the feature.
_SEP = ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")
_CASE = ("lower", "upper", "mixed", "none")
_SCRIPT = ("cyrillic", "latin", "mixed", "none")
_BY_FIELDS = ("fields", "string")
_PADDING = ("padded", "unpadded", "none")
_DIGIT_COUNT = ("as_grammar", "other")


GROUP_B: Tuple[TypeSpec, ...] = (
    # B-01 VIN · [KC] · vehicle identification number · tz-agentpii6-registry.md:473
    TypeSpec(
        id="VIN", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_KC,
        generated_checksum="iso3779", bare_typed=False,
        grammar=r"[0-9A-HJ-NPR-Z]{13}[0-9]{4}; варианты: строчные, кириллические двойники («ХТА…»), группы через пробел",
        length="17 (13+4); ГОСТ 33990-2016 Б.4", grammar_status="ГОТОВ",
        cues=("VIN", "ВИН", "вин-код", "VIN-код", "идентификационный номер", "номер кузова", "номер шасси", "кузов", "рама"),
        field_keys=("vin", "vin_code", "vehicle_vin", "vinNumber", "вин", "VIN"),
        industries=("auto", "insurance", "banks_mfo_collectors", "logistics", "government_services"),
        pd_context="indirect; owner is an individual (OD-22)",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("solid", "3-6-4-4", "other")),
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "glyph"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="XTAGFK330LY123456",
    ),
    # B-02 EPTS_NUMBER · [K] · electronic vehicle passport number · tz-agentpii6-registry.md:521
    TypeSpec(
        id="EPTS_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="epts", bare_typed=False,
        grammar=r"[123]\d{3}0[1-4]\d{9}",
        length="15; Решение ЕЭК № 122 п. 17", grammar_status="ГОТОВ",
        cues=("ЭПТС", "электронный ПТС", "электронный паспорт", "номер ЭП", "ЭПСМ"),
        field_keys=("epts", "epts_number", "eptsNumber", "номер_эптс"),
        industries=("auto", "banks_mfo_collectors", "insurance", "logistics"),
        pd_context="indirect; owner is an individual (OD-22)",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEP),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="164301000000016",
    ),
    # B-03 UIN · [K] · unique accrual identifier (GIS GMP) · tz-agentpii6-registry.md:551
    TypeSpec(
        id="UIN", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="uin", bare_typed=False,
        grammar=r"\d{20}|\d{25}",
        length="20|25; Приказ Минфина 107н", grammar_status="ГОТОВ",
        cues=("УИН", "уникальный идентификатор начисления", "номер постановления", "индекс документа", "код (поле 22)"),
        field_keys=("uin", "supplierBillID", "SupplierBillID", "уин", "payment_uin"),
        industries=("government_services", "auto", "banks_mfo_collectors", "internal_bi"),
        pd_context="indirect; payer is an individual (OD-22)",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEP),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="18810123456789012345",
    ),
    # B-04 COURT_CASE_UID · [K] · unique case id (courts of general jurisdiction) · tz-agentpii6-registry.md:587
    TypeSpec(
        id="COURT_CASE_UID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{2}[A-Z]{2}\d{4}-\d{2}-\d{4}-\d{6}-\d{2}",
        length="22; Инструкция СД № 36 п. 3.2.1", grammar_status="ГОТОВ",
        cues=("УИД", "уникальный идентификатор дела"),
        field_keys=("uid", "case_uid", "court_uid", "уид"),
        industries=("legal", "banks_mfo_collectors", "government_services", "hr"),
        pd_context="indirect; a party is an individual (OD-23)",
        form_features=("separators", "case_class", "script"),
        feature_labels=(
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="77OS0000-02-2026-000001-52",
    ),
    # B-05 ARBITRAZH_CASE_NO · [K] · arbitration court case number · tz-agentpii6-registry.md:620
    TypeSpec(
        id="ARBITRAZH_CASE_NO", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"А\d{2}-\d{1,7}/\d{4}; банкротство А\d{2}-\d{1,7}-\d{1,5}/\d{4}; апелляция \d{2}АП-\d{1,7}/\d{4}; кассация Ф\d{2}-\d{1,7}/\d{4}; СИП С01-\d{1,7}/\d{4}",
        length="переменная; Инструкция ВАС № 100", grammar_status="ГОТОВ",
        cues=("дело №", "по делу", "арбитражное дело", "дело о банкротстве", "обособленный спор"),
        field_keys=("case_number", "caseNumber", "номер_дела", "arbitr_case"),
        industries=("legal", "banks_mfo_collectors", "real_estate", "internal_bi"),
        pd_context="indirect; a party is an individual (OD-23)",
        form_features=("separators", "case_class", "script"),
        feature_labels=(
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="А31-2840/2013",
    ),
    # B-06 COURT_CASE_NO_SOU · [K] · general-jurisdiction court case number · tz-agentpii6-registry.md:642
    TypeSpec(
        id="COURT_CASE_NO_SOU", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"(?:\d{1,2}[а-я]?|М)-\d{1,6}/\d{4}",
        length="переменная; Инструкция СД № 36 п. 3.14", grammar_status="ГОТОВ",
        cues=("дело №", "гражданское дело", "по делу", "судебный приказ №", "производство №"),
        field_keys=("case_number", "court_case", "номер_дела"),
        industries=("legal", "banks_mfo_collectors", "government_services", "hr"),
        pd_context="indirect; a party is an individual (OD-23)",
        form_features=("separators", "case_class", "script"),
        feature_labels=(
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="2-13/2015",
    ),
    # B-07 FSSP_IP_NO · [K] · FSSP enforcement proceeding number · tz-agentpii6-registry.md:661
    TypeSpec(
        id="FSSP_IP_NO", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{1,7}/\d{2}/\d{5}-(?:ИП|СД)|\d{1,7}/\d{2}/\d{2}/\d{2}",
        length="переменная; fssp.gov.ru/iss/ip", grammar_status="ГОТОВ",
        cues=("ИП №", "исполнительное производство", "номер ИП", "сводное производство", "ФССП", "пристав"),
        field_keys=("ip_number", "enforcement_number", "fssp_ip", "номер_ип"),
        industries=("government_services", "banks_mfo_collectors", "hr"),
        pd_context="indirect; debtor is an individual (OD-23)",
        form_features=("separators", "case_class", "script"),
        feature_labels=(
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="1234567/25/77001-ИП",
    ),
    # B-08 EXEC_DOC_NO · [K] · writ of execution series + number · tz-agentpii6-registry.md:680
    TypeSpec(
        id="EXEC_DOC_NO", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"[А-Я]{2}\s?№?\s?\d{9}",
        length="2+9 (11); ПП № 579", grammar_status="ГРАММАТИКА?",
        cues=("исполнительный лист", "ИЛ", "серия ФС", "исполнительный документ"),
        field_keys=("exec_list_number", "writ_number", "исполнительный_лист"),
        industries=("government_services", "banks_mfo_collectors", "legal"),
        pd_context="indirect; debtor is an individual (OD-23)",
        form_features=("grouping", "separators", "case_class", "script", "by_fields"),
        feature_labels=(
            ("grouping", ("2-9", "solid", "other")),
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
            ("by_fields", _BY_FIELDS),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="ФС 012345678",
    ),
    # B-09 STS_NUMBER · [K] · vehicle registration certificate · tz-agentpii6-registry.md:696
    TypeSpec(
        id="STS_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{2}\s?\d{2}\s?\d{6}",
        length="2+2+6 (10); Приказ МВД № 399", grammar_status="ГОТОВ",
        cues=("СТС", "свидетельство о регистрации ТС", "свидетельство о регистрации транспортного средства", "техпаспорт (разг.)"),
        field_keys=("sts", "sts_number", "vehicle_registration_certificate", "номер_стс", "стс"),
        industries=("auto", "insurance", "banks_mfo_collectors", "government_services", "logistics"),
        pd_context="indirect; owner is an individual (OD-22)",
        form_features=("grouping", "separators", "by_fields"),
        feature_labels=(
            ("grouping", ("2-2-6", "4-6", "solid", "other")),
            ("separators", _SEP),
            ("by_fields", _BY_FIELDS),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=("VEHICLE_DOC",), mint="id_digits", hunt="by_shape", sample="77 12 345678",
    ),
    # B-10 PTS_NUMBER · [K] · vehicle passport (paper) · tz-agentpii6-registry.md:715
    TypeSpec(
        id="PTS_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{2}\s?[А-Я]{2}\s?\d{6}",
        length="2+2+6 (10); Приказ 496/192/134", grammar_status="ГОТОВ",
        cues=("ПТС", "паспорт транспортного средства", "паспорт ТС"),
        field_keys=("pts", "pts_number", "vehicle_passport", "номер_птс"),
        industries=("auto", "banks_mfo_collectors", "insurance"),
        pd_context="indirect; owner is an individual (OD-22)",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("2-2-6", "solid", "other")),
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=("VEHICLE_DOC",), mint="id_alnum", hunt="covered", sample="77 УК 123456",
    ),
    # B-11 DRIVER_LICENSE · [K] · driver's licence · tz-agentpii6-registry.md:735
    TypeSpec(
        id="DRIVER_LICENSE", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{2}\s?\d{2}\s?\d{6}",
        length="2+2+6 (10); Приказ МВД № 365", grammar_status="ГОТОВ",
        cues=("водительское удостоверение", "ВУ", "в/у", "права", "вод. удостоверение"),
        field_keys=("driver_license", "driverLicense", "dl_number", "license_number", "ву", "водительское_удостоверение"),
        industries=("auto", "insurance", "logistics", "hr", "retail"),
        pd_context="direct; an individual's document",
        form_features=("grouping", "separators", "by_fields"),
        feature_labels=(
            ("grouping", ("2-2-6", "4-6", "solid", "other")),
            ("separators", _SEP),
            ("by_fields", _BY_FIELDS),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="99 12 345678",
    ),
    # B-12 CADASTRAL_NUMBER · [K] · real-estate cadastral number · tz-agentpii6-registry.md:759
    TypeSpec(
        id="CADASTRAL_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{2}:\d{2}:\d{6,7}:\d{1,}",
        length="переменная (2:2:6-7:1+); Приказ П/0183 п. 3", grammar_status="ГОТОВ",
        cues=("кадастровый номер", "КН", "кад. номер", "кадастр"),
        field_keys=("cadastral_number", "cadastralNumber", "cad_num", "кадастровый_номер"),
        industries=("real_estate", "banks_mfo_collectors", "insurance", "government_services", "legal"),
        pd_context="indirect; owner is an individual (OD-22)",
        form_features=("separators", "case_class", "script"),
        feature_labels=(
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=("digits",),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="77:01:0001001:1234",
    ),
    # B-15 GIS_ZHKH_ELS · [K] · GIS Housing single personal account / housing utility id · tz-agentpii6-registry.md:808
    TypeSpec(
        id="GIS_ZHKH_ELS", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d{2}[А-Я]{2}\d{6} (10) | \d{2}[А-Я]{2}\d{6}-\d{2} (13) | \d{2}[А-Я]{2}\d{6}-\d{2}-\d{4} (18)",
        length="10|13|18; глоссарий ГИС ЖКХ", grammar_status="ГОТОВ",
        cues=("ЕЛС", "единый лицевой счёт", "идентификатор ЖКУ", "ИЖКУ", "идентификатор платёжного документа", "ИПД"),
        field_keys=("els", "unified_account", "gku_id", "payment_document_id", "елс"),
        industries=("government_services", "banks_mfo_collectors", "real_estate", "internal_bi"),
        pd_context="indirect; premises payer account",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("2-2-6", "2-2-6-2", "2-2-6-2-4", "solid", "other")),
            ("separators", _SEP),
            ("case_class", _CASE),
            ("script", _SCRIPT),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="60АА000593-01",
    ),
    # B-16 UTILITY_ACCOUNT · [K] · utility supplier personal account · tz-agentpii6-registry.md:832
    TypeSpec(
        id="UTILITY_ACCOUNT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="нет федеральной; обычно 6–12 цифр, иногда буквы/дефисы",
        length="6-12 (свободная форма)", grammar_status="ГОТОВ",
        cues=("лицевой счёт", "л/с", "ЛС", "номер лицевого счёта", "абонентский номер (ЖКХ)"),
        field_keys=("account", "personal_account", "ls", "лицевой_счет", "abonent_id"),
        industries=("government_services", "retail", "banks_mfo_collectors"),
        pd_context="indirect; premises payer account",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEP),
            ("case_class", _CASE),
            ("padding", _PADDING),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="by_shape", sample="1234567890",
    ),
    # B-18 ESIA_OID · [K] · ESIA account identifier · tz-agentpii6-registry.md:864
    TypeSpec(
        id="ESIA_OID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\d+; длина не установлена",
        length="не установлена; ЕСИА v2.5", grammar_status="ГОТОВ",
        cues=("oid", "ЕСИА", "идентификатор ЕСИА", "Госуслуги ID"),
        field_keys=("oid", "personOid", "prn_oid", "esia_oid", "sbj_id"),
        industries=("banks_mfo_collectors", "government_services", "education", "insurance"),
        pd_context="direct; an individual's account",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEP),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="1000123456",
    ),
)
