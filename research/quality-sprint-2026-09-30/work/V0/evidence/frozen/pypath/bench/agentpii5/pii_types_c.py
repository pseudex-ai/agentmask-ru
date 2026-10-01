# pii_types_c.py — the 24 C-group v6 type-registry records (GROUP_C), written
# from `docs/tz-agentpii6-registry.md` §1.4 and the field mapping in
# `review/v6-typespec-mapping.md`.
#
# Like `pii_types.py`, this module is a PURE, deterministic description: it
# imports only `TypeSpec` and the class/origin constants from `pii_types`, and
# nothing from `pseudex`, `licensing`, `contracts`, `gen_v6` or `checksum_v6`.
# The records are the C-group candidates MINUS the ДЕРЖИМ ones (C-07 EID,
# C-15 RECORD_BOOK_NUMBER, C-21 MIGRATION_CARD_NUMBER), in card order.
#
# Field conventions (review/v6-typespec-mapping.md): `origin="v6"`,
# `item_type=True`, `bare_typed=False`, `squeeze_separators=""`,
# `signature_tail=0` for every record; `type_class`/`generated_checksum` from
# the class table; `cues` are the Russian cue words (before the `·`), the
# `field_keys` the English keys (after the `·`), both verbatim from the card;
# `industries` are the `contracts_v6.INDUSTRIES` keys; `pd_context` names the
# OD-22/23/24 rule when the card's ПД status hinges on one, else "".

from __future__ import annotations

from typing import Tuple

from bench.agentpii5.pii_types import (
    ORIGIN_V6,
    TYPE_CLASS_C,
    TYPE_CLASS_K,
    TYPE_CLASS_KC,
    TypeSpec,
)

# Shared closed label vocabularies (§5.2). `separators` and `case_class` /
# `script` / `by_fields` / `padding` / `digit_count` / `notation` are the fixed
# §5.2 lists; `grouping` is the per-type closed list (groupings from the card +
# `solid` + `other`).
_SEPARATORS: tuple[str, ...] = ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")
_CASE_CLASS: tuple[str, ...] = ("lower", "upper", "mixed", "none")
_SCRIPT: tuple[str, ...] = ("cyrillic", "latin", "mixed", "none")
_BY_FIELDS: tuple[str, ...] = ("fields", "string")
_PADDING: tuple[str, ...] = ("padded", "unpadded", "none")
_DIGIT_COUNT: tuple[str, ...] = ("as_grammar", "other")
_NOTATION_IP: tuple[str, ...] = ("v4_dotted", "v4_padded", "v6_full", "v6_compressed", "other")


GROUP_C: Tuple[TypeSpec, ...] = (
    # C-01 IMEI · [C] · mobile device identifier · docs/tz-agentpii6-registry.md:902
    TypeSpec(
        id="IMEI", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_C,
        generated_checksum="luhn", bare_typed=False,
        grammar="15 цифр: TAC (8) + SNR (6) + CD (1); печатается слитно или с разделителями "
                "«35-209900-176148-1»; dual-SIM — два IMEI; IMEISV — 16 цифр без CD (OD-39).",
        length="15 цифр (3GPP TS 23.003 cl. 6.2.1)", grammar_status="ГОТОВ",
        cues=("IMEI", "имей", "ИМЕЙ", "imei1", "imei2", "серийный номер телефона", "*#06#"),
        field_keys=("imei", "imei1", "imei2", "device_imei", "imeisv"),
        industries=("telecom", "retail", "insurance", "logistics"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("2-6-6-1", "solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="260531793113837",
    ),
    # C-02 ICCID · [K] · SIM card number · docs/tz-agentpii6-registry.md:936
    TypeSpec(
        id="ICCID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="luhn", bare_typed=False,
        grammar="19 цифр (ITU-T E.118 §6): MII «89» + CC (1–3) + IIN + CD (Лун); РФ — «897…»; "
                "20-значные на старых носителях — полевое наблюдение.",
        length="19 цифр (20-значные легаси; ITU-T E.118 §6 / ETSI TS 102 221 §13.2)", grammar_status="ГОТОВ",
        cues=("ICCID", "номер сим-карты", "номер SIM", "серийный номер сим", "ICC"),
        field_keys=("iccid", "sim_iccid", "icc_id", "sim_number"),
        industries=("telecom", "retail", "logistics"),
        pd_context="indirect; natural-person subscriber, M2M legal-entity SIM is a negative (OD-22)",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="8970102000000123458",
    ),
    # C-03 IMSI · [K] · international subscriber identity · docs/tz-agentpii6-registry.md:970
    TypeSpec(
        id="IMSI", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="≤15 цифр: MCC (3) + MNC (2–3) + MSIN; MCC РФ «250».",
        length="≤15 цифр (TS 23.003 cl. 2.2)", grammar_status="ГОТОВ",
        cues=("IMSI", "международный идентификатор абонента"),
        field_keys=("imsi", "subscriber_imsi"),
        industries=("telecom",), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="250991234567890",
    ),
    # C-04 MAC · [K] · device MAC address · docs/tz-agentpii6-registry.md:988
    TypeSpec(
        id="MAC", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="EUI-48: 6 октетов hex через «:» или «-»; Cisco «xxxx.xxxx.xxxx»; голый 12-hex.",
        length="12 hex (6 октетов; IEEE не прочитан)", grammar_status="ГОТОВ",
        cues=("MAC", "мак-адрес", "MAC-адрес", "физический адрес"),
        field_keys=("mac", "mac_address", "client_mac", "bssid"),
        industries=("telecom", "internal_bi", "hospitality"), pd_context="",
        form_features=("grouping", "separators", "case_class"),
        feature_labels=(
            ("grouping", ("2-2-2-2-2-2", "4-4-4", "solid", "other")),
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="hex", hunt="covered", sample="00:1A:2B:3C:4D:5E",
    ),
    # C-05 IP_ADDRESS · [K] · visitor/subscriber IP address · docs/tz-agentpii6-registry.md:1007
    TypeSpec(
        id="IP_ADDRESS", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="IPv4 — четыре октета 0–255 через точку; IPv6 — по RFC 5952 (не прочитан).",
        length="", grammar_status="ГОТОВ",
        cues=("IP", "айпи", "ip-адрес", "с адреса"),
        field_keys=("ip", "ip_address", "client_ip", "remote_addr", "x_forwarded_for"),
        industries=("telecom", "retail", "marketing_cdp", "internal_bi"),
        pd_context="indirect; PD only when linked to a client record (OD-24)",
        form_features=("notation", "padding"),
        feature_labels=(
            ("notation", _NOTATION_IP),
            ("padding", _PADDING),
        ),
        abstain=(),
        identifying_roles=(),
        needle_kinds=("whole", "octets", "ipv6"), squeeze_separators="", signature_tail=0, value_notation="ip_strict",
        engine_labels=("IP",), mint="", hunt="covered", sample="95.165.12.34",
    ),
    # C-06 SUBSCRIBER_ACCOUNT · [K] · telecom subscriber account · docs/tz-agentpii6-registry.md:1033
    TypeSpec(
        id="SUBSCRIBER_ACCOUNT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="операторский цифровой прогон, типично 8–12 цифр, иногда с префиксом оператора (НЕ из первоисточника).",
        length="типично 8–12 цифр (наблюдение, не первоисточник)", grammar_status="ГОТОВ",
        cues=("лицевой счёт", "л/с", "ЛС", "номер договора абонента", "account id"),
        field_keys=("personal_account", "ls", "account_number", "contract_number", "billing_account"),
        industries=("telecom",), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="by_shape", sample="123456789012",
    ),
    # C-08 MEDCARD_NUMBER · [K] · medical record number · docs/tz-agentpii6-registry.md:1065
    TypeSpec(
        id="MEDCARD_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="национальной НЕТ — цифры, часто «/год» или префикс отделения (Приказ Минздрава 1094н).",
        length="", grammar_status="ГОТОВ",
        cues=("медкарта", "медицинская карта", "амбулаторная карта", "история болезни", "ЭМК", "номер карты пациента"),
        field_keys=("medcard", "med_card_number", "patient_card", "emk_id", "history_number"),
        industries=("medicine",), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="covered", sample="12345/2024",
    ),
    # C-09 ELN_NUMBER · [K] · electronic sick-leave number · docs/tz-agentpii6-registry.md:1089
    TypeSpec(
        id="ELN_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="строка до 12 символов; примеры эмитента — 12 цифр на «9000…».",
        length="строка ≤12 (xs:string, «Макс.длинна: 12», СФР «Спецификация ЭЛН МО v2.3»)", grammar_status="ГОТОВ",
        cues=("ЭЛН", "больничный", "листок нетрудоспособности", "номер больничного", "электронный больничный"),
        field_keys=("lnCode", "LN_CODE", "prevLnCode", "nextLnCode", "eln", "eln_number", "sick_leave_number", "ln_code"),
        industries=("medicine", "hr"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="900012345678",
    ),
    # C-10 PRESCRIPTION_NUMBER · [K] · prescription number · docs/tz-agentpii6-registry.md:1114
    TypeSpec(
        id="PRESCRIPTION_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="единой НЕТ: бумажный 148-1/у-04(л) — серия (2 цифры ОКАТО) + номер; электронный — "
                "уникальный номер региональной ГИС (Приказ Минздрава 1094н).",
        length="", grammar_status="ГОТОВ",
        cues=("рецепт", "серия рецепта", "номер рецепта", "электронный рецепт", "льготный рецепт"),
        field_keys=("prescription_id", "recipe_number", "rx_number", "recipe_series"),
        industries=("medicine", "retail"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="covered", sample="45 0012345678",
    ),
    # C-11 REFERRAL_NUMBER · [K] · referral number · docs/tz-agentpii6-registry.md:1134
    TypeSpec(
        id="REFERRAL_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="форма 057/у-04 и электронные направления в МИС/РЕГИЗ; национальная грамматика НЕ установлена.",
        length="", grammar_status="ГРАММАТИКА?",
        cues=("направление", "номер направления", "электронное направление"),
        field_keys=("referral_id", "napravlenie_number"),
        industries=("medicine", "insurance"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="covered", sample="057-2024-001234",
    ),
    # C-12 DIPLOMA_NUMBER · [K] · higher-education diploma number · docs/tz-agentpii6-registry.md:1150
    TypeSpec(
        id="DIPLOMA_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\b1[0-4]\d{4}\s?\d{7}\b — серия 6 символов (тип организации 10–14 + код субъекта 2 + "
                r"лицензия изготовителя 2) + номер 7 цифр (Приказ Минобрнауки № 645); до 2014 — "
                r"буквенные серии («ВСГ», «ОР»).",
        length="13 цифр (серия 6 + номер 7)", grammar_status="ГОТОВ",
        cues=("диплом", "серия и номер диплома", "бланк диплома", "документ об образовании"),
        field_keys=("diploma_series", "diploma_number", "education_doc_number"),
        industries=("education", "hr"), pd_context="",
        form_features=("grouping", "separators", "by_fields"),
        feature_labels=(
            ("grouping", ("6-7", "solid", "other")),
            ("separators", _SEPARATORS),
            ("by_fields", _BY_FIELDS),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="107724 0001234",
    ),
    # C-13 SCHOOL_CERT_NUMBER · [K] · school certificate number · docs/tz-agentpii6-registry.md:1176
    TypeSpec(
        id="SCHOOL_CERT_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"\b\d{14}\b — 3 (код субъекта) + 2 (лицензия изготовителя) + 9 (порядковый) "
                r"(Приказ Минпросвещения № 545).",
        length="14 цифр", grammar_status="ГОТОВ",
        cues=("аттестат", "номер аттестата", "аттестат о среднем общем образовании"),
        field_keys=("attestat_number", "school_certificate_number"),
        industries=("education", "hr"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="07705000012345",
    ),
    # C-14 STUDENT_ID_NUMBER · [K] · student ID number · docs/tz-agentpii6-registry.md:1194
    TypeSpec(
        id="STUDENT_ID_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="организационная, часто «NN-NNNN» или цифры; форма студбилета не получена.",
        length="", grammar_status="ГРАММАТИКА?",
        cues=("студенческий билет", "студбилет", "номер студенческого"),
        field_keys=("student_id", "student_card_number", "idnumber"),
        industries=("education", "retail", "hospitality"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="covered", sample="21-0345",
    ),
    # C-16 EMPLOYEE_TAB_NUMBER · [K] · employee tab number · docs/tz-agentpii6-registry.md:1217
    TypeSpec(
        id="EMPLOYEE_TAB_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="работодательский цифровой прогон, часто с ведущими нулями (6–10 цифр); в 1С ЗУП — «0000-00412».",
        length="6–10 цифр (наблюдение)", grammar_status="ГОТОВ",
        cues=("табельный номер", "таб. №", "табельный", "таб номер"),
        field_keys=("tab_number", "personnel_number", "employee_number", "tabnum", "ТабельныйНомер"),
        industries=("hr", "internal_bi", "retail", "logistics"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="", hunt="by_shape", sample="004512",
    ),
    # C-17 EMPLOYMENT_CONTRACT_NUMBER · [K] · employment contract number · docs/tz-agentpii6-registry.md:1236
    TypeSpec(
        id="EMPLOYMENT_CONTRACT_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="свободная («145-ТД», «ТД-2024/017»).",
        length="", grammar_status="ГОТОВ",
        cues=("трудовой договор", "ТД №", "номер трудового договора"),
        field_keys=("employment_contract_number", "labor_contract_no"),
        industries=("hr", "legal"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="", hunt="covered", sample="145-ТД",
    ),
    # C-18 ACCESS_PASS_NUMBER · [K] · access pass / badge number · docs/tz-agentpii6-registry.md:1252
    TypeSpec(
        id="ACCESS_PASS_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="цифры печатного пропуска или RFID UID в hex (8 или 14 hex).",
        length="", grammar_status="ГОТОВ",
        cues=("пропуск", "номер пропуска", "карта доступа", "бейдж"),
        field_keys=("pass_number", "access_card_id", "badge_id", "card_uid", "card_number"),
        industries=("hr", "internal_bi", "hospitality", "real_estate"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="covered", sample="0034561",
    ),
    # C-19 PNR · [K] · booking record locator · docs/tz-agentpii6-registry.md:1268
    TypeSpec(
        id="PNR", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="5–6 алфавитно-цифровых (GDS); локаторы «Сирены» могут использовать кириллицу; "
                "пример Amadeus «2ZYVAL».",
        length="5–6 символов", grammar_status="ГРАММАТИКА?",
        cues=("PNR", "номер брони", "код бронирования", "номер бронирования", "бронь"),
        field_keys=("pnr", "record_locator", "booking_reference", "booking_code"),
        industries=("hospitality", "logistics"), pd_context="",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("script", _SCRIPT),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=(),
        needle_kinds=("whole", "glyph"), squeeze_separators="", signature_tail=0, value_notation="glyph_fold",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="2ZYVAL",
    ),
    # C-20 E_TICKET_NUMBER · [K] · electronic ticket number · docs/tz-agentpii6-registry.md:1284
    TypeSpec(
        id="E_TICKET_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="авиа — 13 цифр: 3 (расчётный код перевозчика) + 10 (серийный); ж/д — нумерация РЖД не установлена.",
        length="13 цифр (авиа)", grammar_status="ГРАММАТИКА?",
        cues=("электронный билет", "номер билета", "e-ticket", "маршрутная квитанция"),
        field_keys=("ticket_number", "eticket", "ticket_no"),
        industries=("hospitality", "logistics"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="5552412345678",
    ),
    # C-22 LOYALTY_CARD_NUMBER · [K·КС] · loyalty card number · docs/tz-agentpii6-registry.md:1309
    TypeSpec(
        id="LOYALTY_CARD_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_KC,
        generated_checksum="gs1", bare_typed=False,
        grammar="EAN-13 (префиксы 02, 20–29), GSRN-18 (AI 8018) или проприетарные 13–16 цифр (GS1 General "
                "Specifications).",
        length="13–18 цифр (EAN-13 / проприетарные 13–16 / GSRN-18)", grammar_status="ГОТОВ",
        cues=("карта лояльности", "бонусная карта", "дисконтная карта", "клубная карта", "номер карты покупателя"),
        field_keys=("loyalty_card", "bonus_card", "discount_card", "card_number"),
        industries=("retail", "hospitality", "marketing_cdp", "medicine"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "4-4-4-4", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="376104250021234569",
    ),
    # C-23 MOBILE_AD_ID · [K] · advertising ID (GAID / IDFA) · docs/tz-agentpii6-registry.md:1347
    TypeSpec(
        id="MOBILE_AD_ID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="UUID 8-4-4-4-12 (IDFA обычно заглавными, GAID строчными).",
        length="36 символов (UUID)", grammar_status="ГОТОВ",
        cues=("GAID", "IDFA", "рекламный идентификатор", "advertising id"),
        field_keys=("google_aid", "ios_ifa", "advertisingIdentifier", "gaid", "idfa", "adid"),
        industries=("marketing_cdp", "retail", "internal_bi"),
        pd_context="indirect; PD only when linked to a client record (OD-24)",
        form_features=("grouping", "separators", "case_class"),
        feature_labels=(
            ("grouping", ("8-4-4-4-12", "solid", "other")),
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="hex", hunt="covered", sample="6D92078A-8246-4BA4-AE5B-76104861E7DC",
    ),
    # C-24 APP_DEVICE_ID · [K] · in-app device identifier · docs/tz-agentpii6-registry.md:1367
    TypeSpec(
        id="APP_DEVICE_ID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="цифры (appmetrica_device_id, пример «123456789012345678» — 18 цифр) или UUID (IFV).",
        length="цифровая форма — 18 цифр (наблюдение); UUID", grammar_status="ГОТОВ",
        cues=("device id", "идентификатор устройства", "appmetrica_device_id"),
        field_keys=("appmetrica_device_id", "device_id", "idfv", "app_set_id"),
        industries=("marketing_cdp", "internal_bi", "retail"),
        pd_context="indirect; PD only when linked to a client record (OD-24)",
        form_features=("grouping", "separators", "case_class"),
        feature_labels=(
            ("grouping", ("8-4-4-4-12", "solid", "other")),
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "digits", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="hex", hunt="covered", sample="123456789012345678",
    ),
    # C-25 METRICA_CLIENT_ID · [K] · Yandex Metrica ClientID · docs/tz-agentpii6-registry.md:1384
    TypeSpec(
        id="METRICA_CLIENT_ID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="десятичные цифры; образец эмитента — 18 цифр.",
        length="18 цифр (наблюдение, не грамматика)", grammar_status="ГОТОВ",
        cues=("ClientID", "client id", "_ym_uid", "идентификатор посетителя"),
        field_keys=("ClientId", "_ym_uid", "client_id", "ym_client_id", "ym_uid"),
        industries=("marketing_cdp", "retail", "internal_bi"),
        pd_context="indirect; PD only when CRM links the ClientID to a lead (OD-24)",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("solid", "other")),
            ("separators", _SEPARATORS),
            ("digit_count", _DIGIT_COUNT),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="250987654321098765",
    ),
    # C-26 CDP_CUSTOMER_ID · [K] · CRM/CDP customer id · docs/tz-agentpii6-registry.md:1405
    TypeSpec(
        id="CDP_CUSTOMER_ID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="внешней НЕТ — цифры, коды «c-000184523», UUID.",
        length="", grammar_status="ГОТОВ",
        cues=("ID клиента", "клиентский ID", "customer id", "user id"),
        field_keys=("customer_id", "client_id", "user_id", "external_id", "crm_id"),
        industries=("marketing_cdp", "internal_bi", "retail", "logistics"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="", hunt="covered", sample="c-000184523",
    ),
    # C-27 LOGIN · [K] · login / username · docs/tz-agentpii6-registry.md:1419
    TypeSpec(
        id="LOGIN", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar=r"[A-Za-z0-9._-]{3,} — свободный handle.",
        length="≥3 символа", grammar_status="ГОТОВ",
        cues=("логин", "имя пользователя", "username", "учётная запись"),
        field_keys=("login", "username", "user_name", "account_login"),
        industries=("telecom", "retail", "internal_bi", "education", "marketing_cdp"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", _SEPARATORS),
            ("case_class", _CASE_CLASS),
            ("padding", _PADDING),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole",), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="covered", sample="ivanov_d85",
    ),
)
