# gen_v6.py — the GENERATOR home of the v6 checksum arithmetic (TZ §12.2
# component 2; the L2 "second home").
#
# Rule L2 (docs/tz-agentpii6-registry.md §1.8): every checksum row is written
# TWICE, by different authors — here (mints checksum-VALID values) and in
# `checksum_v6.py` (validates them). The two homes import NEITHER each other NOR
# `pseudex` / `licensing` (R6-07). `pii_types` IS imported: it is the PURE,
# engine-free registry that names the 55 v6 types and their `value_notation`,
# and `test_pii_types.test_no_engine` already pins it loads nothing forbidden.
# So this module's own checksum code — Luhn, GS1 mod 10, ISO 3779 VIN, OGRNIP
# mod 13, ЭПТС mod 11, УИН two-pass, IBAN MOD 97-10, УИд hex-Σ mod 16, and the
# ЦБ 515 account key — is a deliberate, independent re-derivation of the SAME
# published arithmetic. Agreement with the cited examples (§1.8 L7 table) is the
# proof the two homes did not share one bug.
#
# Purity contract: deterministic, no module state, no I/O at import, no global
# mutable state. `generate` seeds a LOCAL `random.Random(seed)`, so the same
# (type_id, seed) yields the same (value, canonical) across processes.

from __future__ import annotations

import ipaddress
import random

from bench.agentpii5 import pii_types as _pt


__all__ = ["generate", "vin_is_russian_wmi", "BANK_ACCOUNT_BIK"]


# --- the canonical rule, per §5.3 form class -----------------------------------
#
# `canonical` is the normalised form the VAULT would key on: presentation
# stripped, identity kept. The right normalisation is exactly what the
# registry's `value_notation` already declares for the COMPARISON layer (§5.5),
# so the generator reuses that same five-way rule instead of inventing a sixth:
#
#   value_notation   canonical
#   "digits"         the ASCII digit run (all non-digits dropped)
#   "squeezed"       internal separators (space, "-", "/", ":", "№") removed,
#                    letters uppercased; the ALPHABET is kept (a genuine Cyrillic
#                    series «АК» stays Cyrillic — it is not a Latin twin)
#   "glyph_fold"     "squeezed" PLUS the Cyrillic double of each Latin letter of
#                    the VIN alphabet folded to Latin (А→A … Х→X)
#   "ip_strict"      the `ipaddress`-normalised address (IPv4 without leading
#                    zeros, IPv6 compressed) — the identity of an address IS the
#                    address, not its digit run
#   "" (free form)   the value verbatim — a free-form handle's identity is the
#                    literal string, and the generator already emits it clean
#
# This is why BIRTH_CERT «IV-МЮ № 123456» keys as «IVМЮ123456» (squeezed, the
# roman «IV» and Cyrillic «МЮ» are both real, not twins), while a VIN written in
# Cyrillic keys with its Latin twin (glyph_fold).

_SEP = " -/:№"                      # the R6-35 internal span separators
_GLYPH_FOLD = str.maketrans(
    "АВЕКМНОРСТУХ",                 # Cyrillic doubles of the VIN/Latin alphabet
    "ABEKMHOPCTYX",
)


def _squeeze(value: str) -> str:
    return "".join(ch for ch in value if ch not in _SEP).upper()


def _canonical(value: str, notation: str) -> str:
    if notation == "digits":
        return "".join(ch for ch in value if "0" <= ch <= "9")
    if notation == "squeezed":
        return _squeeze(value)
    if notation == "glyph_fold":
        return _squeeze(value).translate(_GLYPH_FOLD)
    if notation == "ip_strict":
        return str(ipaddress.ip_address(value))
    return value  # free form: the generator emits it clean, keep it verbatim


# --- the checksum arithmetic (independent of checksum_v6) -----------------------
# Every function mirrors the published algorithm, not the other home's code.

_DIGITS = "0123456789"
_HEX = "0123456789abcdef"


def _digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(_DIGITS) for _ in range(n))


def _luhn(body: str) -> str:
    """Luhn check digit (ISO/IEC 7812-1 Annex B): double every second digit from
    the RIGHT of the body, subtract 9 from products over 9 (the digit-sum of 2d),
    CD = (10 - sum mod 10) mod 10. One algorithm serves IMEI (15), OMS_ENP (16)
    and ICCID (19) — writing three copies would create a third place to disagree."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def _gs1(body: str) -> str:
    """GS1 mod 10: weights 3,1 from the RIGHT, up to the next multiple of 10."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return str((10 - total % 10) % 10)


_VIN_VALUES: dict[str, int] = {}
for _i, _c in enumerate("0123456789"):
    _VIN_VALUES[_c] = _i
_VIN_VALUES.update(dict(zip("ABCDEFGH", range(1, 9))))
_VIN_VALUES.update(dict(zip("JKLMN", range(1, 6))))
_VIN_VALUES["P"] = 7
_VIN_VALUES.update(dict(zip("RSTUVWXYZ", (9, 2, 3, 4, 5, 6, 7, 8, 9))))
# Position 9 carries weight 0 — the check digit itself is excluded from the sum.
_VIN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
_VIN_ALPHABET = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"   # no I, O, Q


def _vin_check(body17: str) -> str:
    """ISO 3779 mod 11: transliterate, weight by position, Σ mod 11, 10 → «X»."""
    total = 0
    for i, ch in enumerate(body17):
        w = _VIN_WEIGHTS[i]
        if w == 0:
            continue
        total += _VIN_VALUES[ch] * w
    r = total % 11
    return "X" if r == 10 else str(r)


def _ogrnip_check(body14: str) -> str:
    """OGRNIP: the LOW digit of body14 mod 13 (remainder 10/11/12 → 0/1/2)."""
    return str(int(body14) % 13 % 10)


def _epts_check(body14: str) -> str:
    """ЭПТС: body14 mod 11, remainder 10 folds to 0 (ЕЭК № 122 п. 17)."""
    r = int(body14) % 11
    return "0" if r == 10 else str(r)


def _uin_check(body: str) -> str:
    """УИН: weights 1..10 cyclic from the MOST significant digit, sum mod 11.
    Remainder ≤ 9 is the digit; remainder 10 re-runs with the sequence shifted
    two places left (3,4,…,10,1,2); a second 10 folds to 0."""
    first = sum(int(ch) * (i % 10 + 1) for i, ch in enumerate(body)) % 11
    if first <= 9:
        return str(first)
    second = sum(int(ch) * ((i + 2) % 10 + 1) for i, ch in enumerate(body)) % 11
    return "0" if second == 10 else str(second)


def _iban_key(country: str, bban: str) -> str:
    """ISO 7064 MOD 97-10: move country+«00» to the end, A=10…Z=35, key = 98 −
    (remainder mod 97), zero-padded to two digits. The CBR letter's «carry the
    key (2 digits − 00)» is a typo — carrying the ACTUAL key is what yields
    remainder 1 (A-08)."""
    base = (country + "00" + bban).upper()
    rearranged = base[4:] + base[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return f"{98 - int(digits) % 97:02d}"


def _loan_uid_check(hex32: str) -> str:
    """УИд (ЦБ 758-П Прил. 2): each hex digit gets the cyclic ordinal 1..10;
    Σ(value × ordinal) mod 16; the remainder (10..15 → a..f) is the 38th char."""
    total = 0
    for i, ch in enumerate(hex32):
        total += int(ch, 16) * (i % 10 + 1)
    return format(total % 16, "x")


# --- BANK_ACCOUNT: the ЦБ 515 key is a (account, BIK) PAIR ----------------------
# A bare 20-digit account is uncheckable (each random value passes for some of
# the 1000 BIK suffixes — A-07 «Необнаружимо» 2000/2000). So the generator mints
# the account FOR a fixed, announced BIK, and `validate_account(value, BIK)` is
# the pair check the tests run. The BIK is a negative/`plain` value, never PII,
# so fixing it keeps `generate` a single-value function (TZ §12.2).

BANK_ACCOUNT_BIK = "049805746"   # the A-07 primary example BIK (credit organisation)

_CBR_WEIGHTS = (7, 1, 3) * 8     # cyclic 7,1,3; 24 slots, 23 used


def _cbr515_conditional(bik: str) -> str:
    # Step 1: credit organisation → BIK digits 7–9; РКЦ → «0» + digits 5–6. The
    # observable discriminator is that a РКЦ BIK ends in «000» (040305000) while
    # a credit organisation's does not (049805746); the card's examples split on
    # exactly that signal, so it is the whole rule.
    if bik[6:9] == "000":
        return "0" + bik[4:6]
    return bik[6:9]


def _cbr515_key(account_20: str, bik: str) -> int:
    """The 9th account digit: zero the key, append to the conditional number, sum
    the LOW digits of the weighted products (weights 7,1,3), key = low digit of
    (that sum × 3)."""
    zeroed = account_20[:8] + "0" + account_20[9:]
    total = 0
    for i, ch in enumerate(_cbr515_conditional(bik) + zeroed):
        total += (int(ch) * _CBR_WEIGHTS[i]) % 10
    return (total * 3) % 10


# --- per-type generators --------------------------------------------------------
# Each returns the VALUE in its natural written form (identifier + internal
# separators, never a cue word, never an «от <дата>» tail — R6-35). `canonical`
# is then derived uniformly by `value_notation` above, so a generator never
# re-decides the normalisation.

_CYR = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЫЭЮЯ"
_LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")

# Russian manufacturer WMIs (first character «X» is the overwhelming marker of a
# RU/EАЭС WMI: АвтоВАЗ XTA, УАЗ XTT, ГАЗ XTH, Камаз XTC, …). The RU half fills
# position 9 «as manufacturer» (a random alphabet char, never the ISO check), so
# it is deliberately NON-ISO-3779 — OD-62, «wrong in ≈91%» (the card's measured
# 9.1% accidental-pass rate for random-digit VINs).
_RU_WMIS = ("XTA", "XUF", "XTH", "XTT", "X96", "X7L")
_WORLD_WMIS = ("1G4", "WDB", "JHM", "JT2", "VF3", "SAL", "WVW", "KNA", "1HG", "ZFA")


def vin_is_russian_wmi(value: str) -> bool:
    """True when `value` is a Russian-WMI VIN whose position 9 is the RU «as
    manufacturer» form — the half that is deliberately NOT ISO-3779-checked, and
    that `test_values_validate` therefore skips."""
    return value[:3] in _RU_WMIS


def _gen_intl_passport(rng):
    return _digits(rng, 9)                       # series 2 + number 7


def _gen_birth_cert(rng):
    return f"{rng.choice(_ROMAN)}-{''.join(rng.choice(_CYR) for _ in range(2))} № {_digits(rng, 6)}"


def _gen_civil_act_cert(rng):
    return f"{rng.choice(_ROMAN)}-{''.join(rng.choice(_CYR) for _ in range(2))} № {_digits(rng, 6)}"


def _gen_residence_permit(rng):
    return f"{rng.choice(('82', '83'))} {_digits(rng, 7)}"


def _gen_military_id(rng):
    return f"{''.join(rng.choice(_CYR) for _ in range(2))} № {_digits(rng, 7)}"


def _gen_bank_account(rng):
    # Balance account 40817 (resident individual, A-07), currency 810 (rouble),
    # key computed, branch 4, serial 7 → 20 digits.
    zeroed = "40817" + "810" + "0" + _digits(rng, 4) + _digits(rng, 7)
    key = _cbr515_key(zeroed, BANK_ACCOUNT_BIK)
    return zeroed[:8] + str(key) + zeroed[9:]


def _gen_iban(rng):
    # RU + key + BIK(9) + account(20) = 33. The nested account's own ЦБ 515 key
    # is NOT checked by MOD 97-10 (A-08 «необнаружимо»), so a random account body
    # is fine — only the MOD 97-10 key must be valid.
    bban = _digits(rng, 9) + _digits(rng, 20)
    return "RU" + _iban_key("RU", bban) + bban


def _gen_loan_contract_number(rng):
    return f"{_digits(rng, 2)}-{_digits(rng, 6)}/{_digits(rng, 4)}"


def _gen_loan_uid(rng):
    hex32 = "".join(rng.choice(_HEX) for _ in range(32))
    check = _loan_uid_check(hex32)
    return f"{hex32[:8]}-{hex32[8:12]}-{hex32[12:16]}-{hex32[16:20]}-{hex32[20:32]}-{check}"


def _gen_ogrnip(rng):
    body = "3" + _digits(rng, 13)               # С = 3 for ОГРНИП (A-11)
    return body + _ogrnip_check(body)


def _gen_credit_subject_code(rng):
    n = rng.randint(4, 15)
    alphabet = _LATIN + _DIGITS if rng.random() < 0.5 else _CYR + _DIGITS
    return "".join(rng.choice(alphabet) for _ in range(n))


def _gen_oms_enp(rng):
    body = _digits(rng, 15)
    return body + _luhn(body)


def _gen_dms_policy(rng):
    return f"{_digits(rng, 3)}{''.join(rng.choice(_LATIN) for _ in range(2))}{_digits(rng, 8)}"


def _gen_osago_policy(rng):
    return f"{''.join(rng.choice(_CYR) for _ in range(3))} {_digits(rng, 10)}"


def _gen_kasko_policy(rng):
    return f"{''.join(rng.choice(_LATIN) for _ in range(2))}{_digits(rng, 9)}"


def _gen_insurance_claim_number(rng):
    return f"{rng.choice('УКВ')}-{_digits(rng, 3)}-{_digits(rng, 6)}/{_digits(rng, 2)}"


def _gen_vin(rng):
    # 50% Russian WMI (OD-62) with position 9 «as manufacturer», 50% world WMI
    # with a valid ISO 3779 check. The split is the FIRST rng draw, so it is a
    # fixed, deterministic function of the seed.
    if rng.random() < 0.5:
        wmi = rng.choice(_RU_WMIS)
        mid = "".join(rng.choice(_VIN_ALPHABET) for _ in range(10))   # positions 4–13
        tail = _digits(rng, 4)
        return wmi + mid + tail
    wmi = rng.choice(_WORLD_WMIS)
    p48 = "".join(rng.choice(_VIN_ALPHABET) for _ in range(5))
    p1013 = "".join(rng.choice(_VIN_ALPHABET) for _ in range(4))
    tail = _digits(rng, 4)
    check = _vin_check(wmi + p48 + "0" + p1013 + tail)
    return wmi + p48 + check + p1013 + tail


def _gen_epts_number(rng):
    # `[123]\d{3}0[1-4]\d{9}`: the trailing `\d{9}` spans positions 7–15, so the
    # check digit IS the 15th char and the body is positions 1–14 (…\d{8}).
    body = rng.choice("123") + _digits(rng, 3) + "0" + rng.choice("1234") + _digits(rng, 8)
    return body + _epts_check(body)


def _gen_uin(rng):
    n = rng.choice((20, 25))
    body = _digits(rng, n - 1)
    return body + _uin_check(body)


def _gen_court_case_uid(rng):
    # `\d{2}[A-Z]{2}\d{4}-\d{2}-\d{4}-\d{6}-\d{2}`; вид ∈ {RS, OS}, middle ∈ {01, 02}
    # (B-04). No generated checksum — the MOD 97-10 was DERIVED, not published.
    return (f"{_digits(rng, 2)}{rng.choice(('RS', 'OS'))}{_digits(rng, 4)}"
            f"-{rng.choice(('01', '02'))}-{_digits(rng, 4)}-{_digits(rng, 6)}-{_digits(rng, 2)}")


def _gen_arbitrazh_case_no(rng):
    return f"А{_digits(rng, 2)}-{_digits(rng, rng.randint(1, 7))}/{_digits(rng, 4)}"


def _gen_court_case_no_sou(rng):
    return f"{_digits(rng, rng.randint(1, 2))}-{_digits(rng, rng.randint(1, 6))}/{_digits(rng, 4)}"


def _gen_fssp_ip_no(rng):
    return f"{_digits(rng, rng.randint(1, 7))}/{_digits(rng, 2)}/{_digits(rng, 5)}-{rng.choice(('ИП', 'СД'))}"


def _gen_exec_doc_no(rng):
    return f"{''.join(rng.choice(_CYR) for _ in range(2))} {_digits(rng, 9)}"


def _gen_sts_number(rng):
    return f"{_digits(rng, 2)} {_digits(rng, 2)} {_digits(rng, 6)}"


def _gen_pts_number(rng):
    return f"{_digits(rng, 2)} {''.join(rng.choice(_CYR) for _ in range(2))} {_digits(rng, 6)}"


def _gen_driver_license(rng):
    return f"{_digits(rng, 2)} {_digits(rng, 2)} {_digits(rng, 6)}"


def _gen_cadastral_number(rng):
    return f"{_digits(rng, 2)}:{_digits(rng, 2)}:{_digits(rng, rng.choice((6, 7)))}:{_digits(rng, rng.randint(1, 5))}"


def _gen_gis_zhkh_els(rng):
    base = _digits(rng, 2) + "".join(rng.choice(_CYR) for _ in range(2)) + _digits(rng, 6)
    variant = rng.choice((10, 13, 18))
    if variant == 10:
        return base
    if variant == 13:
        return base + "-" + _digits(rng, 2)
    return base + "-" + _digits(rng, 2) + "-" + _digits(rng, 4)


def _gen_utility_account(rng):
    return _digits(rng, rng.randint(6, 12))


def _gen_esia_oid(rng):
    return _digits(rng, 10)


def _gen_imei(rng):
    body = _digits(rng, 14)
    return body + _luhn(body)


def _gen_iccid(rng):
    # 19 digits only (E.118); the 20-digit legacy form is deliberately NOT
    # generated because its Luhn claim is unconfirmed (C-02, OD-16). MII «89», РФ «897…».
    body = "89" + _digits(rng, 16)
    return body + _luhn(body)


def _gen_imsi(rng):
    return "250" + _digits(rng, 12)              # MCC 250 (РФ), ≤15 digits total


def _gen_mac(rng):
    return ":".join(rng.choice(_HEX) + rng.choice(_HEX) for _ in range(6))


def _gen_ip_address(rng):
    return ".".join(str(rng.randint(0, 255)) for _ in range(4))


def _gen_subscriber_account(rng):
    return _digits(rng, rng.randint(8, 12))


def _gen_medcard_number(rng):
    return f"{_digits(rng, 5)}/{_digits(rng, 4)}"


def _gen_eln_number(rng):
    return "9000" + _digits(rng, 8)              # СФР examples all «9000…», 12 digits


def _gen_prescription_number(rng):
    return f"{_digits(rng, 2)} {_digits(rng, 10)}"


def _gen_referral_number(rng):
    return f"{rng.choice(('057', '088'))}-{_digits(rng, 4)}-{_digits(rng, 6)}"


def _gen_diploma_number(rng):
    return f"1{rng.choice('01234')}{_digits(rng, 4)} {_digits(rng, 7)}"


def _gen_school_cert_number(rng):
    return _digits(rng, 14)


def _gen_student_id_number(rng):
    return f"{_digits(rng, 2)}-{_digits(rng, 4)}"


def _gen_employee_tab_number(rng):
    return _digits(rng, rng.randint(6, 10))


def _gen_employment_contract_number(rng):
    return f"{_digits(rng, 3)}-ТД"


def _gen_access_pass_number(rng):
    if rng.random() < 0.5:
        return _digits(rng, rng.randint(4, 10))
    return "".join(rng.choice(_HEX) for _ in range(rng.choice((8, 14))))


def _gen_pnr(rng):
    return "".join(rng.choice(_VIN_ALPHABET) for _ in range(rng.choice((5, 6))))


def _gen_e_ticket_number(rng):
    return _digits(rng, 13)


def _gen_loyalty_card_number(rng):
    body = _digits(rng, 17)                      # GSRN-18 body (17) + GS1 check
    return body + _gs1(body)


def _gen_mobile_ad_id(rng):
    hexes = "".join(rng.choice(_HEX) for _ in range(32)).upper()
    return f"{hexes[:8]}-{hexes[8:12]}-{hexes[12:16]}-{hexes[16:20]}-{hexes[20:32]}"


def _gen_app_device_id(rng):
    if rng.random() < 0.5:
        return _digits(rng, 18)                  # appmetrica_device_id numeric form
    hexes = "".join(rng.choice(_HEX) for _ in range(32)).upper()
    return f"{hexes[:8]}-{hexes[8:12]}-{hexes[12:16]}-{hexes[16:20]}-{hexes[20:32]}"


def _gen_metrica_client_id(rng):
    return _digits(rng, 18)


def _gen_cdp_customer_id(rng):
    return f"c-{_digits(rng, 9)}"


def _gen_login(rng):
    return f"{''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rng.randint(4, 8)))}_d{_digits(rng, 2)}"


# --- dispatch -------------------------------------------------------------------
# One generator per v6 type id, in the registry's order. `generate` looks the id
# up here; the module-level guard below proves the dict covers exactly the 55
# v6 records of `pii_types.TYPE_REGISTRY` (no type silently missing).

_GENERATORS: dict[str, object] = {
    "INTL_PASSPORT": _gen_intl_passport,
    "BIRTH_CERT": _gen_birth_cert,
    "CIVIL_ACT_CERT": _gen_civil_act_cert,
    "RESIDENCE_PERMIT": _gen_residence_permit,
    "MILITARY_ID": _gen_military_id,
    "BANK_ACCOUNT": _gen_bank_account,
    "IBAN": _gen_iban,
    "LOAN_CONTRACT_NUMBER": _gen_loan_contract_number,
    "LOAN_UID": _gen_loan_uid,
    "OGRNIP": _gen_ogrnip,
    "CREDIT_SUBJECT_CODE": _gen_credit_subject_code,
    "OMS_ENP": _gen_oms_enp,
    "DMS_POLICY": _gen_dms_policy,
    "OSAGO_POLICY": _gen_osago_policy,
    "KASKO_POLICY": _gen_kasko_policy,
    "INSURANCE_CLAIM_NUMBER": _gen_insurance_claim_number,
    "VIN": _gen_vin,
    "EPTS_NUMBER": _gen_epts_number,
    "UIN": _gen_uin,
    "COURT_CASE_UID": _gen_court_case_uid,
    "ARBITRAZH_CASE_NO": _gen_arbitrazh_case_no,
    "COURT_CASE_NO_SOU": _gen_court_case_no_sou,
    "FSSP_IP_NO": _gen_fssp_ip_no,
    "EXEC_DOC_NO": _gen_exec_doc_no,
    "STS_NUMBER": _gen_sts_number,
    "PTS_NUMBER": _gen_pts_number,
    "DRIVER_LICENSE": _gen_driver_license,
    "CADASTRAL_NUMBER": _gen_cadastral_number,
    "GIS_ZHKH_ELS": _gen_gis_zhkh_els,
    "UTILITY_ACCOUNT": _gen_utility_account,
    "ESIA_OID": _gen_esia_oid,
    "IMEI": _gen_imei,
    "ICCID": _gen_iccid,
    "IMSI": _gen_imsi,
    "MAC": _gen_mac,
    "IP_ADDRESS": _gen_ip_address,
    "SUBSCRIBER_ACCOUNT": _gen_subscriber_account,
    "MEDCARD_NUMBER": _gen_medcard_number,
    "ELN_NUMBER": _gen_eln_number,
    "PRESCRIPTION_NUMBER": _gen_prescription_number,
    "REFERRAL_NUMBER": _gen_referral_number,
    "DIPLOMA_NUMBER": _gen_diploma_number,
    "SCHOOL_CERT_NUMBER": _gen_school_cert_number,
    "STUDENT_ID_NUMBER": _gen_student_id_number,
    "EMPLOYEE_TAB_NUMBER": _gen_employee_tab_number,
    "EMPLOYMENT_CONTRACT_NUMBER": _gen_employment_contract_number,
    "ACCESS_PASS_NUMBER": _gen_access_pass_number,
    "PNR": _gen_pnr,
    "E_TICKET_NUMBER": _gen_e_ticket_number,
    "LOYALTY_CARD_NUMBER": _gen_loyalty_card_number,
    "MOBILE_AD_ID": _gen_mobile_ad_id,
    "APP_DEVICE_ID": _gen_app_device_id,
    "METRICA_CLIENT_ID": _gen_metrica_client_id,
    "CDP_CUSTOMER_ID": _gen_cdp_customer_id,
    "LOGIN": _gen_login,
}

# Registry-derived facts, read once at import (pure, no I/O): the closed set of
# v6 ids and each type's `value_notation` (the canonical rule above).
_V6 = {t.id: t for t in _pt.TYPE_REGISTRY if t.origin == _pt.ORIGIN_V6}

if set(_GENERATORS) != set(_V6):
    _missing = sorted(set(_V6) - set(_GENERATORS))
    _extra = sorted(set(_GENERATORS) - set(_V6))
    raise RuntimeError(
        f"gen_v6 generator table does not match the v6 registry: "
        f"missing={_missing}, extra={_extra}"
    )


def generate(type_id: str, seed: int) -> tuple[str, str]:
    """Mint a deterministic `(value, canonical)` for a v6 type.

    `type_id` must be one of the 55 v6 ids in `pii_types.TYPE_REGISTRY`; anything
    else raises. `seed` drives a LOCAL `random.Random(seed)`, so the result is
    identical across processes and calls (no module state). `value` matches the
    type's grammar and, when `generated_checksum` is non-empty, is checksum-VALID
    for that algorithm — except VIN's 50% Russian-WMI half (OD-62, deliberately
    non-ISO-3779 position 9) and the never-generated 20-digit ICCID. `canonical`
    is the vault key per `value_notation` (see the module comment).
    """
    if type_id not in _V6:
        raise ValueError(f"gen_v6: unknown v6 type id {type_id!r}")
    rng = random.Random(seed)
    value = _GENERATORS[type_id](rng)  # type: ignore[operator]
    canonical = _canonical(value, _V6[type_id].value_notation)
    return value, canonical
