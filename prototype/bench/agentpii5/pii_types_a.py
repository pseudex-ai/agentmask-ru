# pii_types_a.py — GROUP_A: the sixteen A-group v6 type-registry records
# (docs/tz-agentpii6-registry.md §1.2, cards A-01…A-17 minus the ДЕРЖИМ
# TEMP_RESIDENCE_PERMIT). One frozen `TypeSpec` per card, in card order.
#
# Every field transcribes the card through the mapping in
# `bench/agentpii5/review/v6-typespec-mapping.md`. This module is PURE data and
# imports nothing but the `TypeSpec` shape and the class/origin constants from
# `pii_types` — no `pseudex`, no `licensing`, no `contracts`, no `gen_v6`, no
# `checksum_v6`. It is consumed by the lead's `v6-records-review.py` and later
# by the phase-1 owner who folds GROUP_A/B/C into `TYPE_REGISTRY`.
#
# Load-bearing notes:
# - `needle_kinds` carries `glyph` (a CQ-8 needle kind) exactly as the cards'
#   «Иглы» lines do; `pii_types.NEEDLE_KINDS` is extended by the phase-1 owner
#   in the same change that admits these records, so the closed-list T2 rule
#   holds after that extension, not before it.
# - `hunt` and `mint` follow §9.2 / §6.2: digit types hunt `by_shape` and mint
#   `id_digits`; alphanumeric types hunt `covered` and mint `id_alnum`; hex mints
#   `hex`; free-form-cue types mint `""`.
# - The `sample` of a checksum-carrying type is checksum-VALID (see the inline
#   comments for the arithmetic); samples reuse the card's §1.8 / grammar
#   examples where one exists, else are built from the card's checksum rule.

from __future__ import annotations

from bench.agentpii5.pii_types import (
    ORIGIN_V6,
    TYPE_CLASS_K,
    TYPE_CLASS_KC,
    TypeSpec,
)


# The sixteen A-group records, in card order (A-05 TEMP_RESIDENCE_PERMIT is
# ДЕРЖИМ and deliberately absent).
GROUP_A: tuple[TypeSpec, ...] = (
    # A-01 INTL_PASSPORT · [K] · grammar at registry:30 · Иглы whole,digits(9)
    TypeSpec(
        id="INTL_PASSPORT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="NN NNNNNNN — серия 2 цифры + номер 7 цифр; варианты «751234567», «75 № 1234567», "
                "«серия 75 номер 1234567», в MRZ — номер + контрольная ICAO (ПП 687 стр. 227–228)",
        length="9 цифр (2 серия + 7 номер)", grammar_status="ГОТОВ",
        cues=("загранпаспорт", "загран", "загранник", "заграничный паспорт", "биометрический паспорт",
              "passport", "паспорт для выезда"),
        field_keys=("intl_passport", "foreign_passport", "passport_number", "docNumber", "RQ_IDENT_DOC_NUM"),
        industries=("banks_mfo_collectors", "insurance", "hospitality", "hr"), pd_context="",
        form_features=("grouping", "separators", "by_fields"),
        feature_labels=(
            ("grouping", ("2-7", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("by_fields", ("fields", "string")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape",
        # The printed 9-digit number has NO checksum (the ICAO 7-3-1 digit lives
        # only in the MRZ), so any 9-digit series is checksum-vacuously valid.
        sample="751234567",
    ),
    # A-02 BIRTH_CERT · [K] · grammar at registry:51 · Иглы whole,glyph,digits(6)
    TypeSpec(
        id="BIRTH_CERT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="<римские>-<2 заглавные кириллические> № NNNNNN («IV-МЮ № 123456»); варианты: без «№», "
                "слитно, арабская цифра вместо римской, кириллические/украинские І/Х, «серия IV-МЮ номер 123456»",
        length="серия <римские>-<2 кириллические> + номер 6 цифр (Приказ Минюста 167 — состав серии не получен)",
        grammar_status="ГРАММАТИКА?",
        cues=("свидетельство о рождении", "св-во о рождении", "свид-во о рожд", "свидетельство ребенка", "СОР"),
        field_keys=("birth_certificate", "birth_cert_series", "birth_cert_number", "doc_type"),
        industries=("banks_mfo_collectors", "insurance", "medicine", "education", "government_services"),
        pd_context="",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("2-2-6", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("script", ("cyrillic", "latin", "mixed", "none")),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="IV-МЮ № 123456",
    ),
    # A-03 CIVIL_ACT_CERT · [K] · grammar at registry:72 · Иглы whole,glyph,digits(6)
    TypeSpec(
        id="CIVIL_ACT_CERT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="как BIRTH_CERT: <римские>-<2 заглавные кириллические> № NNNNNN",
        length="как BIRTH_CERT: серия + номер 6 цифр", grammar_status="ГРАММАТИКА?",
        cues=("свидетельство о браке", "о заключении брака", "о расторжении брака", "о смерти",
              "о перемене имени", "об установлении отцовства", "об усыновлении"),
        field_keys=("marriage_certificate", "death_certificate", "name_change_certificate"),
        industries=("banks_mfo_collectors", "insurance", "legal"), pd_context="",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("2-2-6", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("script", ("cyrillic", "latin", "mixed", "none")),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="I-АГ № 672731",
    ),
    # A-04 RESIDENCE_PERMIT · [K] · grammar at registry:90 · Иглы whole,digits(9)
    TypeSpec(
        id="RESIDENCE_PERMIT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="серия «82»/«83» + номер 7 цифр; варианты «821234567», «серия 82 № 1234567», «ВНЖ 82 1234567»",
        length="9 цифр (2 серия + 7 номер)", grammar_status="ГРАММАТИКА?",
        cues=("вид на жительство", "ВНЖ", "внж", "вид на жит.", "residence permit"),
        field_keys=("residence_permit", "vnzh", "RQ_IDENT_DOC_NUM"),
        industries=("banks_mfo_collectors", "insurance", "hr", "hospitality"), pd_context="",
        form_features=("grouping", "separators", "by_fields"),
        feature_labels=(
            ("grouping", ("2-7", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("by_fields", ("fields", "string")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=(), mint="id_digits", hunt="by_shape", sample="82 1234567",
    ),
    # A-06 MILITARY_ID · [K] · grammar at registry:127 · Иглы whole,glyph,digits(7)
    TypeSpec(
        id="MILITARY_ID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="две заглавные кириллические + «№» + 7 цифр: «АК 1234567», «АК №1234567», «АК1234567», "
                "«серия АК номер 1234567», латиница «AK 1234567»",
        length="2 кириллические + 7 цифр (Приказ МО РФ № 700 Прил. 4)", grammar_status="ГОТОВ",
        cues=("военный билет", "военник", "в/б"),
        field_keys=("military_id", "military_ticket", "voenniy_bilet", "voennyi_bilet"),
        industries=("banks_mfo_collectors", "hr", "insurance", "government_services"), pd_context="",
        form_features=("grouping", "separators", "case_class", "script", "by_fields"),
        feature_labels=(
            ("grouping", ("2-7", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("script", ("cyrillic", "latin", "mixed", "none")),
            ("by_fields", ("fields", "string")),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="АК № 1234567",
    ),
    # A-07 BANK_ACCOUNT · [K·КС] · grammar at registry:146 · Иглы whole,digits(20)
    TypeSpec(
        id="BANK_ACCOUNT", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_KC,
        generated_checksum="cbr515", bare_typed=False,
        grammar="20 цифр: 1–5 балансовый счёт 2-го порядка, 6–8 валюта (810/840/978), 9 защитный ключ, "
                "10–13 филиал, 14–20 порядковый; варианты слитно, 4×5, «40817.810.0.9991.0004312»",
        length="20 цифр (Положение ЦБ 809-П Прил. 1)", grammar_status="ГОТОВ",
        cues=("счёт", "счет", "р/с", "расчётный счёт", "лицевой счёт", "л/с", "номер счёта", "текущий счёт",
              "счёт вклада", "реквизиты", "зачислить на", "перевести на счёт"),
        field_keys=("account", "account_number", "accountNumber", "acc_num", "RQ_ACC_NUM", "НомерСчета",
                    "bank_account", "ls"),
        industries=("banks_mfo_collectors", "retail", "hr", "insurance", "internal_bi"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("4-4-4-4-4", "5-3-1-4-7", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("digit_count", ("as_grammar", "other")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=("ACCOUNT",), mint="id_digits", hunt="by_shape",
        # ЦБ 515 working example (БИК 049805746): body …0…25 → key 7.
        sample="40602810700000000025",
    ),
    # A-08 IBAN · [K] · grammar at registry:198 · Иглы whole,squeezed,digits(31)
    TypeSpec(
        id="IBAN", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="mod97", bare_typed=False,
        grammar="RU + 2 контрольные + БИК (9) + номер счёта (20) = 33 знака; печатный формат — группы по 4; "
                "иностранные (KZ, BY, GE, TR, AE, CY) ≤34",
        length="33 знака RU (ЦБ ИН-04-45/146); иностранные ≤34 по реестру SWIFT", grammar_status="ГОТОВ",
        cues=("IBAN", "айбан", "международный номер счёта"),
        field_keys=("iban", "IBAN", "RQ_IBAN", "beneficiary_iban"),
        industries=("banks_mfo_collectors", "retail", "hr", "insurance"), pd_context="",
        form_features=("grouping", "separators", "case_class", "script"),
        feature_labels=(
            ("grouping", ("4-4-4-4-4-4-4-4-1", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("script", ("cyrillic", "latin", "mixed", "none")),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_alnum", hunt="covered",
        # MOD 97-10, key «03» (фактчек mirror); remainder is 1.
        sample="RU0304452522540817810538091310419",
    ),
    # A-09 LOAN_CONTRACT_NUMBER · [K] · grammar at registry:240 · Иглы whole,squeezed,glyph,digits
    TypeSpec(
        id="LOAN_CONTRACT_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="национальной НЕТ (353-ФЗ не задаёт формат); цифры 8–20, с «/»/«-» и годом, буквенные префиксы; "
                "формы «12-345678/2025», «МФО-2025-0012345», «0045-Р-123456789», «625/1234-0001234»",
        length="8–20 цифр (свободная форма)", grammar_status="ГОТОВ",
        cues=("кредитный договор", "договор займа", "договор №", "КД №", "договор потребительского кредита",
              "номер договора", "займ №"),
        field_keys=("contract_number", "loan_id", "loanNumber", "credit_agreement_no", "НомерДоговора", "dogovor"),
        industries=("banks_mfo_collectors", "retail", "internal_bi"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("padding", ("padded", "unpadded", "none")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="covered", sample="12-345678/2025",
    ),
    # A-10 LOAN_UID · [K] · grammar at registry:262 · Иглы whole,squeezed
    TypeSpec(
        id="LOAN_UID", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="uid", bare_typed=False,
        grammar="NNNNNNNN-NNNN-NNNN-NNNN-NNNNNNNNNNNN-C — UUID (строчные a–f) + «-» + контрольный символ hex; "
                "варианты: ЗАГЛАВНЫЕ, без дефисов 33 hex",
        length="38 знаков (32 hex + 4 дефиса + контрольный символ; ЦБ 758-П Прил. 2 пп. 4–5)", grammar_status="ГОТОВ",
        cues=("УИд", "УИД", "уникальный идентификатор договора", "идентификатор сделки", "UID договора"),
        field_keys=("uid", "UID", "deal_uid", "contract_uid", "uid_deal"),
        industries=("banks_mfo_collectors", "internal_bi"), pd_context="",
        form_features=("grouping", "separators", "case_class"),
        feature_labels=(
            ("grouping", ("8-4-4-4-12", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="hex", hunt="covered",
        # Σ(hex × 1..10 cyclic) mod 16 over the 32-hex body = 12 → check char «c».
        sample="1dcf884c-5f2a-4b3e-9d7a-6c5b4e3f2a1d-c",
    ),
    # A-11 OGRNIP · [K] · grammar at registry:298 · Иглы whole,digits(15)
    TypeSpec(
        id="OGRNIP", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="ogrnip", bare_typed=False,
        grammar="15 цифр «С ГГ КК XXXXXXXXX Ч», С = 3 для ОГРНИП; вариант «ОГРНИП: 324 77 000012345 5»",
        length="15 цифр (Приказ Минфина 165н п. 7)", grammar_status="ГОТОВ",
        cues=("ОГРНИП", "ОГРН ИП", "рег. номер ИП"),
        field_keys=("ogrnip", "OGRNIP", "RQ_OGRNIP"),
        industries=("retail", "banks_mfo_collectors", "logistics", "internal_bi", "legal"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("1-2-2-9-1", "3-2-9-1", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("digit_count", ("as_grammar", "other")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=("OGRN",), mint="id_digits", hunt="by_shape",
        # First 14 digits mod 13 → 5 (младший разряд остатка) — the card's own
        # «324 77 000012345 5» shape is checksum-valid.
        sample="324770000123455",
    ),
    # A-12 CREDIT_SUBJECT_CODE · [K] · grammar at registry:325 · Иглы whole
    TypeSpec(
        id="CREDIT_SUBJECT_CODE", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="4–15 знаков: цифры + буквы ОДНОГО алфавита (русского ИЛИ латинского), регистр не учитывается",
        length="4–15 знаков (Указание ЦБ 6474-У п. 1.3)", grammar_status="ГОТОВ",
        cues=("код субъекта", "код субъекта кредитной истории", "код КИ", "дополнительный код", "код для ЦККИ"),
        field_keys=("credit_history_code", "subject_code", "kod_subekta"),
        industries=("banks_mfo_collectors",), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("padding", ("padded", "unpadded", "none")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole",), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="covered", sample="Qw7rT2",
    ),
    # A-13 OMS_ENP · [K·КС] · grammar at registry:344 · Иглы whole,digits(16)
    TypeSpec(
        id="OMS_ENP", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_KC,
        generated_checksum="luhn", bare_typed=False,
        grammar="16 цифр, 16-я — контрольный разряд; варианты слитно, 4×4",
        length="16 цифр (ТФОМС Ростовской обл. «Структура ЕНП»)", grammar_status="ГОТОВ",
        cues=("полис", "полис ОМС", "ОМС", "медполис", "мед. полис", "ЕНП", "номер полиса", "единый номер полиса"),
        field_keys=("enp", "ENP", "oms", "oms_policy", "polis", "polis_number", "policy_number",
                    "NPOLIS", "SPOLIS", "VPOLIS"),
        industries=("medicine", "insurance", "hr", "government_services"), pd_context="",
        form_features=("grouping", "separators", "digit_count"),
        feature_labels=(
            ("grouping", ("4-4-4-4", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("digit_count", ("as_grammar", "other")),
        ),
        abstain=(),
        identifying_roles=("digits",),
        needle_kinds=("whole", "digits"), squeeze_separators="", signature_tail=0, value_notation="digits",
        engine_labels=("OMS",), mint="id_digits", hunt="by_shape",
        # HL7 Mod10 ≡ Luhn over the 16 digits — the card's own example is valid.
        sample="7707536455681514",
    ),
    # A-14 DMS_POLICY · [K] · grammar at registry:392 · Иглы whole,squeezed,glyph
    TypeSpec(
        id="DMS_POLICY", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="национальной НЕТ (ГК гл. 48, 4015-1); формы страховщиков «001SB12345678», «ДМС-1234567/25», "
                "«12345678901234», карта ДМС — 16 цифр",
        length="свободная форма", grammar_status="ГОТОВ",
        cues=("ДМС", "полис ДМС", "добровольное медицинское", "карта ДМС", "страховка", "номер полиса"),
        field_keys=("dms_policy", "policy_number", "policyNumber", "insurance_policy", "polis"),
        industries=("medicine", "insurance", "hr"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("padding", ("padded", "unpadded", "none")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="covered", sample="001SB12345678",
    ),
    # A-15 OSAGO_POLICY · [K] · grammar at registry:412 · Иглы whole,glyph,digits(10)
    TypeSpec(
        id="OSAGO_POLICY", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="серия — 3 заглавные кириллические (электронный «ХХХ»; бумажные ТТТ, ААН, ААВ, ААС, ЕЕЕ, МММ…) "
                "+ номер 10 цифр: «ХХХ 0123456789», «ХХХ№0123456789», «XXX 0123456789»",
        length="3 кириллические + 10 цифр (справочные страницы страховщиков, вторично)", grammar_status="ГРАММАТИКА?",
        cues=("ОСАГО", "полис ОСАГО", "автогражданка", "е-ОСАГО", "страховка на машину"),
        field_keys=("osago_series", "osago_number", "policySerial", "policyNumber", "policy_series"),
        industries=("insurance", "auto", "banks_mfo_collectors"), pd_context="OD-22",
        form_features=("grouping", "separators", "case_class", "script", "by_fields"),
        feature_labels=(
            ("grouping", ("3-10", "solid", "other")),
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("script", ("cyrillic", "latin", "mixed", "none")),
            ("by_fields", ("fields", "string")),
        ),
        abstain=(("case_class", "none"), ("script", "none")),
        identifying_roles=(),
        needle_kinds=("whole", "glyph", "digits"), squeeze_separators="", signature_tail=0, value_notation="squeezed",
        engine_labels=(), mint="id_alnum", hunt="covered", sample="ХХХ 0123456789",
    ),
    # A-16 KASKO_POLICY · [K] · grammar at registry:434 · Иглы whole,squeezed,glyph
    TypeSpec(
        id="KASKO_POLICY", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="национальной НЕТ (ГК гл. 48, 4015-1); формы «AI123456789», «7100-12345678», «КАСКО-001-2025-0001234»",
        length="свободная форма", grammar_status="ГОТОВ",
        cues=("КАСКО", "полис КАСКО", "каско", "добровольное автострахование"),
        field_keys=("kasko_policy", "policy_number", "policyNumber"),
        industries=("insurance", "auto", "banks_mfo_collectors"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("padding", ("padded", "unpadded", "none")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="covered", sample="AI123456789",
    ),
    # A-17 INSURANCE_CLAIM_NUMBER · [K] · grammar at registry:448 · Иглы whole,squeezed,glyph
    TypeSpec(
        id="INSURANCE_CLAIM_NUMBER", origin=ORIGIN_V6, item_type=True, type_class=TYPE_CLASS_K,
        generated_checksum="", bare_typed=False,
        grammar="своя у страховщика; формы «У-671-475136/25», «0012345678-001», «ОСАГО-25-123456»",
        length="свободная форма", grammar_status="ГОТОВ",
        cues=("номер убытка", "убыток №", "страховое дело", "номер дела", "номер выплатного дела"),
        field_keys=("claim_number", "claimId", "loss_number", "ubytok"),
        industries=("insurance", "auto", "medicine"), pd_context="",
        form_features=("separators", "case_class", "padding"),
        feature_labels=(
            ("separators", ("none", "space", "hyphen", "dot", "slash", "colon", "numsign", "mixed")),
            ("case_class", ("lower", "upper", "mixed", "none")),
            ("padding", ("padded", "unpadded", "none")),
        ),
        abstain=(("case_class", "none"),),
        identifying_roles=(),
        needle_kinds=("whole", "squeezed", "glyph"), squeeze_separators="", signature_tail=0, value_notation="",
        engine_labels=(), mint="", hunt="covered", sample="У-671-475136/25",
    ),
)
