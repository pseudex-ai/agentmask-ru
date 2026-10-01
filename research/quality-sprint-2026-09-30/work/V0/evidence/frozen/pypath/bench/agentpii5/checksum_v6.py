# checksum_v6.py — the VALIDATOR home of the L7 checksum arithmetic.
#
# Rule L2 of docs/tz-agentpii6-registry.md §1.8: every row's arithmetic is
# written TWICE, by different authors — here (the validator, which must ACCEPT
# the "необнаружимые классы", R6-09) and in `gen_v6.py` (the generator, which
# mints valid values). The two homes import NEITHER each other NOR
# `pseudex.ru_pii` / `licensing` (R6-07); agreeing on the corpus and on the
# cited examples is what proves they did not share one bug. This module is
# therefore PURE and deterministic: only the standard library, no module state,
# no I/O.
#
# Scope discipline: this module owns the ARITHMETIC only. Length and alphabet
# are the registry type cards' grammar (docs/tz-agentpii6-registry.md
# §1.2–1.4, `pii_types.py`), so a checksum helper does not re-decide a length
# the card owns. Two exceptions, where the length IS the algorithm: the
# BANK_ACCOUNT ЦБ 515 key runs over a fixed 23-digit (BIK-conditional + 20
# digit account) sequence, and the UIN key runs over a 19/24-digit body.

from __future__ import annotations

__all__ = [
    "validate",
    "luhn_check_digit",
    "validate_luhn",
    "validate_imei",
    "validate_oms_enp",
    "validate_iccid",
    "cbr515_account_key",
    "validate_account",
    "iban_check_digit",
    "validate_iban",
    "loan_uid_check_digit",
    "validate_loan_uid",
    "ogrnip_check_digit",
    "validate_ogrnip",
    "epts_check_digit",
    "validate_epts_number",
    "uin_check_digit",
    "validate_uin",
    "vin_check_digit",
    "validate_vin",
    "gs1_check_digit",
    "validate_loyalty_card_number",
    "icao731_check_digit",
    "validate_intl_passport",
    "upu_check_digit",
    "validate_s10_track",
]


def _ascii_digits(value: str) -> bool:
    # `str.isdigit` accepts non-ASCII digits, which would silently widen the
    # grammar; every checksum here is defined over 0-9 only.
    return len(value) > 0 and all("0" <= ch <= "9" for ch in value)


# --- Luhn, and its three registry consumers -------------------------------------
# IMEI (C-01), OMS_ENP (A-13, HL7 Mod10 ≡ Luhn) and ICCID (C-02) are one
# algorithm. A-13 proves HL7 "Mod10" == Luhn: the digit-sum of a doubled digit
# is sum(2d) − 9·[d≥5], order-independent, 0 disagreements over 200k bodies.
# Writing a second copy under a second name would create a third place for the
# two homes to disagree, so there is exactly one Luhn.

def luhn_check_digit(body: str) -> str:
    """Luhn check digit (ISO/IEC 7812-1 Annex B) for a digit-only body.

    Doubles every second digit counting from the RIGHT of the body — the body's
    rightmost digit IS the first doubled one — and subtracts 9 from any product
    over 9 (the digit-sum of the product). CD = (10 − sum mod 10) mod 10. This
    is the same convention as the TS 23.003 B.3 example «2 6 0 5 … = 53 → 7»."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:  # positions 1, 3, 5, … from the right
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def validate_luhn(value: str) -> bool:
    """True iff the last digit equals the Luhn check digit of the rest."""
    if len(value) < 2 or not _ascii_digits(value):
        return False
    return luhn_check_digit(value[:-1]) == value[-1]


def validate_imei(value: str) -> bool:
    """IMEI (C-01): 15 digits, Luhn over the first 14 (TS 23.003 cl. 6.2.1 B)."""
    return validate_luhn(value)


def validate_oms_enp(value: str) -> bool:
    """OMS_ENP (A-13): 16 digits, HL7 Mod10 ≡ Luhn (ФФОМС 79 → ISO/HL7 27931)."""
    return validate_luhn(value)


def validate_iccid(value: str) -> bool:
    """ICCID (C-02): 19 digits, Luhn over the first 18 (ITU-T E.118 §6)."""
    return validate_luhn(value)


# --- BANK_ACCOUNT (A-07): CBR 515 key, a PAIR check ------------------------------
# The key is a property of the (account, BIK) pair, never of the account alone:
# step 1 derives a 3-digit conditional number from the BIK, so a bare 20-digit
# account is uncheckable (each random value passes with some of the 1000 BIK
# suffixes — A-07 «Необнаружимо» 2000/2000). Hence `validate_account(account,
# bik)`, not a single-string `validate("BANK_ACCOUNT", v)`.

_CBR_WEIGHTS: tuple[int, ...] = (7, 1, 3) * 8  # cyclic 7,1,3; 24 slots, 23 used


def _cbr515_conditional(bik: str) -> str:
    # Step 1 (A-07): credit organisation → BIK digits 7–9; РКЦ/correspondent →
    # «0» + BIK digits 5–6. The only observable discriminator inside the pair is
    # that a РКЦ BIK ends in "000" (040305000, 049805000) while a credit
    # organisation's does not (049805746); the card's three examples split
    # exactly on that signal, so it is the whole rule, not a shortcut.
    if bik[6:9] == "000":
        return "0" + bik[4:6]
    return bik[6:9]


def cbr515_account_key(account_20: str, bik: str) -> int:
    """The 9th account digit, per CBR 08.09.1997 № 515.

    Append the 20-digit account with its key (9th) forced to 0 to the 3-digit
    conditional number → 23 digits; weights 7,1,3; sum the LOW digits of the
    products; key = low digit of (that sum × 3)."""
    if len(account_20) != 20 or not _ascii_digits(account_20):
        raise ValueError("account_20 must be 20 digits")
    if len(bik) != 9 or not _ascii_digits(bik):
        raise ValueError("bik must be 9 digits")
    zeroed = account_20[:8] + "0" + account_20[9:]
    total = 0
    for i, ch in enumerate(_cbr515_conditional(bik) + zeroed):
        total += (int(ch) * _CBR_WEIGHTS[i]) % 10
    return (total * 3) % 10


def validate_account(account_20: str, bik: str) -> bool:
    """True iff the account's 9th digit equals the ЦБ 515 key for (account, bik)."""
    if len(account_20) != 20 or not _ascii_digits(account_20):
        return False
    if len(bik) != 9 or not _ascii_digits(bik):
        return False
    return cbr515_account_key(account_20, bik) == int(account_20[8])


# --- IBAN (A-08): ISO 7064 MOD 97-10 --------------------------------------------

def iban_check_digit(country: str, bban: str) -> str:
    """Two-digit MOD 97-10 key for a country code + BBAN (BIK + account).

    key = 00, move country+key to the end, letters A=10…Z=35, remainder mod 97,
    key = 98 − remainder. The CBR letter's «carry the key (2 digits − 00)» is a
    typo: carrying the ACTUAL key is what yields remainder 1 on the example."""
    base = (country + "00" + bban).upper()
    rearranged = base[4:] + base[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return f"{98 - int(digits) % 97:02d}"


def validate_iban(value: str) -> bool:
    """MOD 97-10: the rearranged number mod 97 == 1. Spaces ignored, case folded."""
    v = value.replace(" ", "").upper()
    if len(v) < 5 or not v.isalnum() or not v[:2].isalpha():
        return False
    rearranged = v[4:] + v[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return int(digits) % 97 == 1


# --- LOAN_UID (A-10): Σ(hex × 1..10) mod 16 -------------------------------------

def loan_uid_check_digit(body: str) -> str:
    """Control symbol for a 32-hex body (ЦБ 758-П Прил. 2 пп. 4–5).

    Each hex digit, left to right, gets the cyclic ordinal 1…10; Σ(value ×
    ordinal) mod 16; the remainder (10…15 → a…f) is the 38th character."""
    total = 0
    for i, ch in enumerate(body):
        total += int(ch, 16) * (i % 10 + 1)
    return format(total % 16, "x")


def validate_loan_uid(value: str) -> bool:
    """38-char `NNNNNNNN-NNNN-NNNN-NNNN-NNNNNNNNNNNN-C`; dashes stripped, the
    trailing control symbol compared against the 32-hex body's check digit."""
    flat = value.replace("-", "").lower()
    if len(flat) != 33:  # 32 hex + 1 control symbol
        return False
    if not all(ch in "0123456789abcdef" for ch in flat):
        return False
    return loan_uid_check_digit(flat[:32]) == flat[32]


# --- OGRNIP (A-11): first 14 digits mod 13 → low digit ---------------------------

def ogrnip_check_digit(body14: str) -> str:
    """OGRNIP check digit (Минфин 165н п. 7): the LOW digit of body14 mod 13
    (remainder 10, 11, 12 → 0, 1, 2)."""
    return str(int(body14) % 13 % 10)


def validate_ogrnip(value: str) -> bool:
    if len(value) != 15 or not _ascii_digits(value):
        return False
    return ogrnip_check_digit(value[:14]) == value[14]


# --- EPTS_NUMBER (B-02): 14 digits mod 11, remainder 10 → 0 ---------------------

def epts_check_digit(body14: str) -> str:
    """ЭПТС check digit (ЕЭК № 122 п. 17): body14 mod 11, remainder 10 folds to 0."""
    r = int(body14) % 11
    return "0" if r == 10 else str(r)


def validate_epts_number(value: str) -> bool:
    if len(value) != 15 or not _ascii_digits(value):
        return False
    return epts_check_digit(value[:14]) == value[14]


# --- UIN (B-03): weights 1..10 mod 11 with a shifted second pass -----------------

def uin_check_digit(body: str) -> str:
    """UIN check digit (Минфин 107н). Weights 1…10 cyclic from the MOST
    significant digit over the 19/24-digit body; sum mod 11. Remainder ≤ 9 is
    the digit; remainder 10 re-runs with the sequence shifted two places left
    (3,4,5,6,7,8,9,10,1,2); a second 10 folds to 0."""
    first = sum(int(ch) * (i % 10 + 1) for i, ch in enumerate(body)) % 11
    if first <= 9:
        return str(first)
    second = sum(int(ch) * ((i + 2) % 10 + 1) for i, ch in enumerate(body)) % 11
    return "0" if second == 10 else str(second)


def validate_uin(value: str) -> bool:
    if not _ascii_digits(value):
        return False
    if len(value) == 20:
        body, cd = value[:19], value[19]
    elif len(value) == 25:
        body, cd = value[:24], value[24]
    else:
        return False
    return uin_check_digit(body) == cd


# --- VIN (B-01): ISO 3779 mod 11, check at position 9 ----------------------------

_VIN_VALUE: dict[str, int] = {}
for _d, _c in enumerate("0123456789"):
    _VIN_VALUE[_c] = _d
_VIN_VALUE.update(dict(zip("ABCDEFGH", (1, 2, 3, 4, 5, 6, 7, 8))))
_VIN_VALUE.update(dict(zip("JKLMN", (1, 2, 3, 4, 5))))
_VIN_VALUE["P"] = 7
_VIN_VALUE.update(dict(zip("RSTUVWXYZ", (9, 2, 3, 4, 5, 6, 7, 8, 9))))
# Position 9 carries weight 0 (the check digit itself is excluded from the sum);
# the equal weights (1↔11 … 7↔17) and equal letter values (1/A/J, 2/B/K/S, …)
# are exactly the mutations this checksum cannot see. I, O, Q are not in the
# VIN alphabet and are absent from the map, so they are rejected, not guessed.
_VIN_WEIGHTS: tuple[int, ...] = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


def vin_check_digit(body: str) -> str:
    total = 0
    for i, ch in enumerate(body):
        w = _VIN_WEIGHTS[i]
        if w == 0:
            continue
        total += _VIN_VALUE[ch] * w
    r = total % 11
    return "X" if r == 10 else str(r)


def validate_vin(value: str) -> bool:
    if len(value) != 17:
        return False
    up = value.upper()
    if any(c not in _VIN_VALUE for c in up):
        return False
    return vin_check_digit(up) == up[8]


# --- LOYALTY_CARD_NUMBER (C-22): GS1 mod 10 -------------------------------------

def gs1_check_digit(body: str) -> str:
    """GS1 check digit: weights 3,1 from the RIGHT, up to the next multiple of 10."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return str((10 - total % 10) % 10)


def validate_loyalty_card_number(value: str) -> bool:
    if len(value) < 2 or not _ascii_digits(value):
        return False
    return gs1_check_digit(value[:-1]) == value[-1]


# --- INTL_PASSPORT (A-01): ICAO 7-3-1 mod 10, MRZ only ---------------------------

def _icao_char_value(ch: str) -> int:
    if "0" <= ch <= "9":
        return ord(ch) - 48
    if "A" <= ch <= "Z":
        return ord(ch) - 55  # A → 10 … Z → 35
    if ch == "<":
        return 0  # the MRZ filler counts as zero, not as a letter
    raise ValueError(f"invalid MRZ character {ch!r}")


def icao731_check_digit(body: str) -> str:
    """ICAO 9303 part 3 check digit: weights 7,3,1 cyclic left to right; digits
    keep their value, `<` is 0, letters A=10…Z=35; the digit is sum mod 10 (no
    10-complement, unlike Luhn/GS1)."""
    total = 0
    for i, ch in enumerate(body.upper()):
        total += _icao_char_value(ch) * (7, 3, 1)[i % 3]
    return str(total % 10)


def validate_intl_passport(value: str) -> bool:
    # `value` is a body plus a trailing MRZ check digit (0-9). The printed
    # 9-digit passport number has NO checksum (A-01: «на печатном номере НЕТ»);
    # only the MRZ does, so this validates the MRZ form, not the bare number.
    if len(value) < 2:
        return False
    check = value[-1]
    if not ("0" <= check <= "9"):
        return False
    return check == icao731_check_digit(value[:-1])


# --- S10 track (negative): UPU mod 11 -------------------------------------------
# Not a PII type — a checksum-valid NEGATIVE the validator still reproduces so a
# track number is never given a checksum gate it does not deserve.

_UPU_WEIGHTS: tuple[int, ...] = (8, 6, 4, 2, 3, 5, 9, 7)


def upu_check_digit(body8: str) -> str:
    """UPU S10 check digit over 8 digits: weights 8 6 4 2 3 5 9 7 left to right,
    mod 11; remainder 0 → 5, remainder 1 → 0, else 11 − remainder."""
    r = sum(int(ch) * w for ch, w in zip(body8, _UPU_WEIGHTS)) % 11
    if r == 0:
        return "5"
    if r == 1:
        return "0"
    return str(11 - r)


def validate_s10_track(value: str) -> bool:
    if len(value) != 9 or not _ascii_digits(value):
        return False
    return upu_check_digit(value[:8]) == value[8]


# --- dispatch --------------------------------------------------------------------

_VALIDATORS: dict[str, object] = {
    "IMEI": validate_imei,
    "OMS_ENP": validate_oms_enp,
    "ICCID": validate_iccid,
    "IBAN": validate_iban,
    "LOAN_UID": validate_loan_uid,
    "OGRNIP": validate_ogrnip,
    "EPTS_NUMBER": validate_epts_number,
    "UIN": validate_uin,
    "VIN": validate_vin,
    "LOYALTY_CARD_NUMBER": validate_loyalty_card_number,
    "INTL_PASSPORT": validate_intl_passport,
    "S10": validate_s10_track,
    "S10_TRACK": validate_s10_track,
}


def validate(type_id: str, value: str) -> bool:
    """Validate the published checksum of `value` for `type_id`.

    Deterministic and pure. BANK_ACCOUNT is deliberately absent from the map:
    its key is a (account, BIK) pair check, so call `validate_account(account_20,
    bik)` instead."""
    tid = type_id.strip().upper()
    if tid == "BANK_ACCOUNT":
        raise ValueError(
            "BANK_ACCOUNT key is a (account, BIK) pair check; "
            "call validate_account(account_20, bik)"
        )
    fn = _VALIDATORS.get(tid)
    if fn is None:
        raise KeyError(f"checksum_v6: unknown type id {type_id!r}")
    return fn(value)  # type: ignore[operator]
