"""v6 registry types the engine now supports natively — arithmetic, mints, anchors.

THIS FILE HOLDS FOUR FAMILIES, one per section, each APPENDED to the one before
without touching it (N1 is five grammar families written by five executors over
the same shared files):

  * §checksum — the eleven records with `generated_checksum != ""` (BANK_ACCOUNT
    cbr515, IBAN mod97, LOAN_UID uid, OGRNIP ogrnip, OMS_ENP luhn, VIN iso3779,
    EPTS_NUMBER epts, UIN uin, IMEI luhn, ICCID luhn, LOYALTY_CARD_NUMBER gs1);
  * §identity — the eight identity-document records with
    `generated_checksum == ""` (INTL_PASSPORT, BIRTH_CERT, CIVIL_ACT_CERT,
    RESIDENCE_PERMIT, MILITARY_ID, DRIVER_LICENSE, PTS_NUMBER, STS_NUMBER). Their
    mechanism is GRAMMAR + TYPED CONTEXT, not arithmetic: the registry marks three
    of them `ГРАММАТИКА?`, so their shape is a conservative cue/key-anchored rule
    and never an invented validator (`GRAMMAR_UNASSERTED`);
  * §legal — the six legal/court records (COURT_CASE_UID, ARBITRAZH_CASE_NO,
    COURT_CASE_NO_SOU, FSSP_IP_NO, EXEC_DOC_NO, CADASTRAL_NUMBER), the same
    mechanism with one `ГРАММАТИКА?` (`LEGAL_GRAMMAR_UNASSERTED`);
  * §finance — the ten finance/insurance/medical records of this executor's own
    family (LOAN_CONTRACT_NUMBER, CREDIT_SUBJECT_CODE, DMS_POLICY, OSAGO_POLICY,
    KASKO_POLICY, INSURANCE_CLAIM_NUMBER, MEDCARD_NUMBER, ELN_NUMBER,
    PRESCRIPTION_NUMBER, REFERRAL_NUMBER). NONE carries a checksum — the registry
    gives all ten `generated_checksum == ""` — and EIGHT of them are free-form
    («национальной НЕТ»), so this is the first family whose shape is a
    conservative SHAPE RULE for a number whose national format does not exist.
    Two records are `ГРАММАТИКА?` (`FINANCE_GRAMMAR_UNASSERTED`).

The registry (`bench/agentpii5/pii_types.py`, V1-integrated) names exactly
eleven records with a `generated_checksum`: BANK_ACCOUNT (cbr515), IBAN (mod97),
LOAN_UID (uid), OGRNIP (ogrnip), OMS_ENP (luhn), VIN (iso3779), EPTS_NUMBER
(epts), UIN (uin), IMEI (luhn), ICCID (luhn), LOYALTY_CARD_NUMBER (gs1). Eight
of them are new to the engine; OGRNIP, VIN and the Luhn family existed but were
neither format-preserving nor validity-inheriting.

TWO RULES DECIDE EVERY LINE HERE.

  1. COV-CHECKSUM-INHERIT (OWNER-DECISIONS.md:23). «Валидный исходник →
     валидная подмена; ошибочный исходник не исправлять подменой.» A valid
     source mints a VALID fake; a faulty source mints a FAULTY fake. The engine
     never re-mints until the checksum fails — the historical R6-39 rule the
     owner rejected (V1 SPEC §5, `mint_v6_remint_invalid` is the mutant the
     versioned metric separates, not the semantics).

  2. SAFE RANGES ARE PROVEN PER TYPE, not inherited from the v5 trick
     (OWNER-DECISIONS.md:23, last sentence). Where the format admits a value
     that cannot belong to anybody — an IMEI reporting-body id `00`, an ОМС
     region `000`, an ОГРНИП region `00`, a VIN region `0`, an unassigned bank
     code `000000000` — the fake uses it. Where it does not (a UUID, a
     proprietary loyalty number), TYPES.md records the collision argument
     instead, and this module does not pretend otherwise.

The arithmetic lives HERE, not in `pseudex/ru_pii.py`, because the two must be
able to disagree: the frozen v6 benchmark already cross-checks its validator
against an independent generator (checksum_v6.py header, R6-07), and the engine
validator is a third reading of the same published algorithms. The four
algorithms the engine already owned (Luhn, ОГРН, VIN's value table, СНИЛС) are
re-used rather than copied — one algorithm, one home.
"""

import re
import secrets

from pseudex.detect import Span

# Entity label -> registry type id. Three of the eleven keep their v5 engine
# name (`engine_labels` in the registry): ACCOUNT, OGRN, OMS. The other eight
# are new labels, so a v5 conversation keeps its vocabulary and its rows.
LABEL_TO_TYPE: dict[str, str] = {
    "ACCOUNT": "BANK_ACCOUNT",
    "OGRN": "OGRNIP",
    "OMS": "OMS_ENP",
    "IBAN": "IBAN",
    "LOAN_UID": "LOAN_UID",
    "EPTS": "EPTS_NUMBER",
    "UIN": "UIN",
    "IMEI": "IMEI",
    "ICCID": "ICCID",
    "LOYALTY": "LOYALTY_CARD_NUMBER",
    "VIN": "VIN",
}

V6_TYPES: tuple[str, ...] = (
    "BANK_ACCOUNT", "IBAN", "LOAN_UID", "OGRNIP", "OMS_ENP", "VIN",
    "EPTS_NUMBER", "UIN", "IMEI", "ICCID", "LOYALTY_CARD_NUMBER",
)

# The country codes the registry's IBAN card names for this market. A bare
# IBAN is anchored on this closed list — that is a SOURCE fact (the card's own
# grammar), not a bare-value guess, which is why it may stand without a cue
# while a bare 16-digit ОМС may not (`bare_typed=False` on all eleven).
IBAN_COUNTRIES: frozenset[str] = frozenset(
    ("RU", "KZ", "BY", "GE", "TR", "AE", "CY"))

# Balance-account prefixes of the v6 negative families CORR_ACCOUNT,
# LEGAL_ACCOUNT and TREASURY_ACCOUNT. They identify a legal entity, which 152-ФЗ
# ст. 3 п. 1 does not call a data subject; masking them broke the customer's own
# payment flow — the same line that removed 13-digit ОГРН.
_BUSINESS_ACCOUNT_PREFIXES: tuple[str, ...] = ("301", "407", "03100", "4010")

# Personal balance-account families the substitute is drawn from: текущие счета
# физлиц (408xx) and вклады физлиц (423-426). A fake from here can never be a
# legal entity's account, and the customer's own tool sees a shape its form
# accepts.
_PERSONAL_ACCOUNT_PREFIXES: tuple[str, ...] = (
    "40817", "40820", "40803", "40810", "40813", "40814", "40821", "40822",
    "40823", "40824", "423", "424", "425", "426")

# The BIK a BANK_ACCOUNT fake is minted against when the field context carries
# none. It is not a real bank: a BIK begins with «04» and encodes a credit
# organisation's registration, so «000000000» can never name one — and a
# (account, BIK) pair with an impossible BIK cannot be a real pair.
_SYNTHETIC_BIK: str = "000000000"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _ascii_digits(value: str) -> bool:
    return bool(value) and all("0" <= ch <= "9" for ch in value)


def _rand_digits(count: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(count))


def _rand_from(alphabet: str, count: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(count))


# =========================================================== arithmetic ======
#
# Each validator is total: any string, any length, no exception. The caller in
# `vault._render_token` asks «was the SOURCE valid?» on text the detector just
# found and on text it did not, so a raise here would be a 5xx on the masking
# path — the fail-closed direction is «False», never a traceback.

def luhn_check_digit(body: str) -> str:
    """Luhn/ISO 7812-1 Annex B check digit over a digit-only body.

    Doubles every second digit counting from the RIGHT of the body; the body's
    rightmost digit is the first doubled one. CD = (10 − sum mod 10) mod 10.
    One home for IMEI, ICCID and ОМС_ENP — the registry itself proves HL7
    «Mod10» ≡ Luhn (A-13), so a second copy under a second name would only
    create a place for the two to disagree."""
    total = 0
    for index, char in enumerate(reversed(body)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def validate_luhn(value: str) -> bool:
    return len(value) >= 2 and _ascii_digits(value) and \
        luhn_check_digit(value[:-1]) == value[-1]


def validate_imei(value: str) -> bool:
    """IMEI (C-01): 15 digits, Luhn over the first 14 (TS 23.003 cl. 6.2.1)."""
    return len(value) == 15 and validate_luhn(value)


def validate_oms_enp(value: str) -> bool:
    """ОМС ЕНП (A-13): 16 digits, HL7 Mod10 ≡ Luhn."""
    return len(value) == 16 and validate_luhn(value)


def validate_iccid(value: str) -> bool:
    """ICCID (C-02): 19 digits (20 on legacy carriers), Luhn (ITU-T E.118 §6)."""
    return len(value) in (19, 20) and validate_luhn(value)


def validate_ogrnip(value: str) -> bool:
    """ОГРНИП (A-11): 15 digits, low digit of the first 14 mod 13."""
    return len(value) == 15 and _ascii_digits(value) \
        and str(int(value[:14]) % 13 % 10) == value[14]


def validate_epts_number(value: str) -> bool:
    """ЭПТС (B-02): 15 digits, body14 mod 11 (remainder 10 folds to 0)."""
    if len(value) != 15 or not _ascii_digits(value):
        return False
    remainder = int(value[:14]) % 11
    return ("0" if remainder == 10 else str(remainder)) == value[14]


def uin_check_digit(body: str) -> str:
    """УИН check digit (Минфин 107н).

    Weights 1…10 cyclic from the most significant digit; sum mod 11. A
    remainder ≤ 9 is the digit; a remainder of 10 re-runs the sequence shifted
    two places left, and a second 10 folds to 0."""
    first = sum(int(ch) * (index % 10 + 1) for index, ch in enumerate(body)) % 11
    if first <= 9:
        return str(first)
    second = sum(int(ch) * ((index + 2) % 10 + 1)
                 for index, ch in enumerate(body)) % 11
    return "0" if second == 10 else str(second)


def validate_uin(value: str) -> bool:
    """УИН (B-03): 20 or 25 digits, the last one is the check digit."""
    if not _ascii_digits(value) or len(value) not in (20, 25):
        return False
    return uin_check_digit(value[:-1]) == value[-1]


# ISO 3779. I, O and Q are absent from the alphabet precisely so they cannot be
# confused with 1/0, and that exclusion is what makes the grammar checkable.
_VIN_VALUES: dict[str, int] = {str(d): d for d in range(10)}
_VIN_VALUES.update(dict(zip("ABCDEFGH", range(1, 9))))
_VIN_VALUES.update(dict(zip("JKLMN", (1, 2, 3, 4, 5))))
_VIN_VALUES["P"] = 7
_VIN_VALUES.update(dict(zip("RSTUVWXYZ", (9, 2, 3, 4, 5, 6, 7, 8, 9))))
_VIN_WEIGHTS: tuple[int, ...] = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)
VIN_ALPHABET: str = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"
# The registry grammar: thirteen alphanumerics, then FOUR DIGITS (ГОСТ
# 33990-2016 Б.4). Used to recognise the card's form; the VIN validator itself
# stays permissive about the last four, because ISO 3779 does not put digits
# there and a real VIN with letters in the VIS must not be refused.
VIN_GRAMMAR = re.compile(r"[0-9A-HJ-NPR-Z]{13}[0-9]{4}")


def vin_check_char(value: str) -> str:
    """The ISO 3779 check character at position 9."""
    total = 0
    for index, char in enumerate(value):
        weight = _VIN_WEIGHTS[index]
        if weight:
            total += _VIN_VALUES[char] * weight
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def validate_vin(value: str) -> bool:
    """VIN (B-01): 17 characters from the ISO alphabet, check at position 9."""
    upper = value.upper()
    if len(upper) != 17 or any(char not in _VIN_VALUES for char in upper):
        return False
    return vin_check_char(upper) == upper[8]


def iban_check_digits(country: str, bban: str) -> str:
    """ISO 7064 MOD 97-10 key for a country code + BBAN.

    key = 98 − (the whole IBAN with a 00 key, country+key moved to the end,
    letters read as A=10…Z=35) mod 97."""
    base = (country + "00" + bban).upper()
    rearranged = base[4:] + base[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return f"{98 - int(numeric) % 97:02d}"


def validate_iban(value: str) -> bool:
    """IBAN (A-08): the rearranged number mod 97 == 1, spaces ignored."""
    squeezed = value.replace(" ", "").upper()
    if len(squeezed) < 5 or not squeezed.isalnum() or not squeezed[:2].isalpha():
        return False
    if not _ascii_digits(squeezed[2:4]):
        return False
    rearranged = squeezed[4:] + squeezed[:4]
    try:
        numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    except ValueError:
        return False
    return int(numeric) % 97 == 1


def validate_loan_uid(value: str) -> bool:
    """УИД (A-10): 32 hex + one control character (ЦБ 758-П Прил. 2 пп. 4–5).

    38 characters with dashes, or the 33-character glued variant; the control
    character is Σ(hex × cyclic ordinal 1…10) mod 16."""
    flat = value.replace("-", "").lower()
    if len(flat) != 33 or not all(ch in "0123456789abcdef" for ch in flat):
        return False
    total = sum(int(ch, 16) * (index % 10 + 1) for index, ch in enumerate(flat[:32]))
    return format(total % 16, "x") == flat[32]


def _cbr515_conditional(bik: str) -> str:
    """Step 1 of ЦБ 515: the three-digit conditional number.

    A credit organisation contributes BIK digits 7–9; a РКЦ (a BIK ending in
    «000» — 040305000, 049805000) contributes «0» + digits 5–6. The only
    observable discriminator inside the pair is that ending, so it is the rule."""
    if bik[6:9] == "000":
        return "0" + bik[4:6]
    return bik[6:9]


_CBR_WEIGHTS: tuple[int, ...] = (7, 1, 3) * 8


def cbr515_account_key(account_20: str, bik: str) -> int:
    """The key digit (9th) of a 20-digit account for a 9-digit BIK.

    The account with its key forced to 0 is appended to the conditional number
    → 23 digits; weights 7,1,3; sum the LOW digits of the products; the key is
    the low digit of that sum × 3."""
    zeroed = account_20[:8] + "0" + account_20[9:]
    total = 0
    for index, char in enumerate(_cbr515_conditional(bik) + zeroed):
        total += (int(char) * _CBR_WEIGHTS[index]) % 10
    return (total * 3) % 10


def validate_account(account: str, bik: str) -> bool:
    """True iff the account's 9th digit is the ЦБ 515 key for (account, BIK).

    A bare 20-digit account is UNCHECKABLE — the key is a property of the pair,
    which is why the registry's own dispatch refuses a single-string call."""
    if len(account) != 20 or not _ascii_digits(account):
        return False
    if len(bik) != 9 or not _ascii_digits(bik):
        return False
    return cbr515_account_key(account, bik) == int(account[8])


def validate_bank_account_shape(value: str) -> bool:
    """The account's own shape: 20 digits, a PERSONAL balance family, and the
    key digit consistent with the engine's synthetic unassignable BIK. This is
    what can be checked without the customer's BIK, and it is exactly what the
    mint guarantees — see TYPES.md for the honest limit."""
    if len(value) != 20 or not _ascii_digits(value):
        return False
    if not value.startswith(_PERSONAL_ACCOUNT_PREFIXES):
        return False
    return cbr515_account_key(value, _SYNTHETIC_BIK) == int(value[8])


def gs1_check_digit(body: str) -> str:
    """GS1 check digit: weights 3,1 from the RIGHT, up to the next multiple of 10."""
    total = sum(int(ch) * (3 if index % 2 == 0 else 1)
                for index, ch in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def validate_loyalty_card_number(value: str) -> bool:
    """LOYALTY_CARD_NUMBER (C-22): 13–18 digits, GS1 mod 10 (EAN-13, GSRN-18 or
    a proprietary 13–16-digit number)."""
    return 13 <= len(value) <= 18 and _ascii_digits(value) \
        and gs1_check_digit(value[:-1]) == value[-1]


_VALIDATORS = {
    "IMEI": validate_imei,
    "OMS_ENP": validate_oms_enp,
    "ICCID": validate_iccid,
    "OGRNIP": validate_ogrnip,
    "EPTS_NUMBER": validate_epts_number,
    "UIN": validate_uin,
    "VIN": validate_vin,
    "IBAN": validate_iban,
    "LOAN_UID": validate_loan_uid,
    "LOYALTY_CARD_NUMBER": validate_loyalty_card_number,
}


def validate(type_id: str, value: str) -> bool:
    """Validate `value` for `type_id` (BANK_ACCOUNT excluded: pair check)."""
    if type_id == "BANK_ACCOUNT":
        raise ValueError("BANK_ACCOUNT is a (account, BIK) pair check; "
                         "call validate_account(account, bik)")
    return _VALIDATORS[type_id](value)


# ============================================================== anchors ======
#
# TWO ANCHORS, and the difference between them is the whole bare-vs-typed rule.
#
#   * A CUE or a FIELD KEY types the value: «полис ОМС …», {"iban": …}. The
#     evidence is the word, so a faulty checksum is protected too
#     (COV-TYPED-INVALID / P05) — the customer who mistypes a digit has still
#     typed their identifier. These anchors live in the LEASED tables
#     (`CTX_TYPES`, `KEY_TYPE`) and are therefore not repeated here.
#   * A BARE value stands alone only where the anchor is a closed SOURCE list
#     and not just a shape: an IBAN obeys the country registry, a УИД is a
#     32-hex UUID plus its control character. `bare_typed=False` on all eleven
#     records says a bare digit run is NOT typed — 15/16/20 digits are order
#     and tracking numbers, and the v5 bare paths that already existed for VIN
#     and ОГРНИП are preserved verbatim (`COV-INTEGRATION-KEEP-V5`).

# An IBAN is printed glued and in groups of four; both are the same value.
_IBAN_GLUED = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2}\d{2}[A-Z0-9]{11,30})(?![A-Za-z0-9])")
_IBAN_SPACED = re.compile(
    r"(?<![A-Za-z0-9])([A-Z]{2}\d{2}(?: [A-Z0-9]{4})*(?: [A-Z0-9]{1,4})?)(?![A-Za-z0-9])")
# УИД: the dashed UUID form and the glued 33-hex form, in either case.
_LOAN_UID_DASHED = re.compile(
    r"(?<![0-9A-Za-z])"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{12}-[0-9a-fA-F])(?![0-9A-Za-z])")
_LOAN_UID_GLUED = re.compile(r"(?<![0-9A-Za-z])([0-9a-fA-F]{33})(?![0-9A-Za-z])")


def detect_checksum_anchored(text: str) -> list[Span]:
    """Bare-valued positives whose anchor is a closed source list: IBAN and
    LOAN_UID. Everything else needs a cue or a field key (`bare_typed=False`)."""
    spans: list[Span] = []
    seen: set[tuple[int, int]] = set()
    for pattern, kind in ((_IBAN_GLUED, "IBAN"), (_IBAN_SPACED, "IBAN"),
                          (_LOAN_UID_DASHED, "LOAN_UID"),
                          (_LOAN_UID_GLUED, "LOAN_UID")):
        for match in pattern.finditer(text):
            value = match.group(1)
            if kind == "IBAN":
                squeezed = value.replace(" ", "").upper()
                if squeezed[:2] not in IBAN_COUNTRIES or not validate_iban(value):
                    continue
            elif not validate_loan_uid(value):
                continue
            if (match.start(1), match.end(1)) in seen:
                continue
            seen.add((match.start(1), match.end(1)))
            spans.append(Span(match.start(1), match.end(1), kind, value))
    return spans


def is_business_account(value: str) -> bool:
    """A 20-digit account of a legal entity, a correspondent or a treasury
    account — a v6 negative family, never a data subject's account."""
    digits = _digits(value)
    return len(digits) == 20 and digits.startswith(_BUSINESS_ACCOUNT_PREFIXES)


# ================================================================ mints ======
#
# Every mint takes the ORIGINAL and returns the substitute. The shape is
# preserved (length, alphabet, country, grouping class) and the verdict is
# inherited. `_corrupt_check` is the ONE place a fault is mirrored, and it
# breaks exactly the position the checksum lives in — never a random position,
# which would change the grammar rather than the verdict.

def _corrupt_check(type_id: str, token: str) -> str:
    """The same value with the CHECK position changed and nothing else."""
    def broken_digit(value: str) -> str:
        for index in range(len(value) - 1, -1, -1):
            if value[index].isdigit():
                return value[:index] + ("0" if value[index] != "0" else "1") + value[index + 1:]
        raise RuntimeError(f"{type_id}: no digit to break in {value!r}")

    if type_id in ("IMEI", "ICCID", "OMS_ENP", "OGRNIP", "EPTS_NUMBER",
                   "UIN", "LOYALTY_CARD_NUMBER"):
        return broken_digit(token)
    if type_id == "VIN":
        return token[:8] + ("0" if token[8] != "0" else "1") + token[9:]
    if type_id == "IBAN":
        check = token[2:4]
        return token[:2] + ("01" if check != "01" else "02") + token[4:]
    if type_id == "LOAN_UID":
        return token[:-1] + ("0" if token[-1] != "0" else "1")
    if type_id == "BANK_ACCOUNT":
        # The key digit is the 9th; a different digit there breaks the pair.
        return token[:8] + ("0" if token[8] != "0" else "1") + token[9:]
    raise RuntimeError(f"no check position known for {type_id}")


def _personal_body(length: int) -> str:
    """`length` digits from a personal balance family (408xx / 423-426)."""
    prefix = secrets.choice(_PERSONAL_ACCOUNT_PREFIXES)
    return (prefix + _rand_digits(length - len(prefix)))[:length]


def mint_imei() -> str:
    body = "00" + _rand_digits(12)          # RBI «00» is not assigned
    return body + luhn_check_digit(body)


def mint_iccid(length: int) -> str:
    body = "890" + _rand_digits(length - 3 - 1)   # country code 0 is unassigned
    return body + luhn_check_digit(body)


def mint_oms_enp() -> str:
    body = "000" + _rand_digits(12)         # region 000 is not a ТФОМС
    return body + luhn_check_digit(body)


def mint_ogrnip() -> str:
    body = "3" + f"{secrets.randbelow(100):02d}" + "00" + _rand_digits(9)
    return body + str(int(body) % 13 % 10)


def mint_epts_number() -> str:
    body = secrets.choice("123") + _rand_digits(3) + "0" \
        + secrets.choice("1234") + _rand_digits(8)
    remainder = int(body) % 11
    return body + ("0" if remainder == 10 else str(remainder))


def mint_uin(length: int) -> str:
    body = "000" + _rand_digits(length - 1 - 3)   # administrator 000 unassigned
    return body + uin_check_digit(body)


def mint_loyalty(length: int) -> str:
    body = _rand_digits(length - 1)
    return body + gs1_check_digit(body)


def mint_vin() -> str:
    """A VIN whose check digit PASSES and whose region digit cannot be real.

    The first ISO 3779 position is the geographic region; «0» is not an
    assigned region code, so no manufacturer issued it. The check digit is
    written at position 9 with a valid value — the v5 renderer deliberately
    corrupted it, which under COV-CHECKSUM-INHERIT turns a valid source into an
    invalid fake, i.e. the rejected mutant."""
    body = ["0"] + list(_rand_from(VIN_ALPHABET, 12)) + list(_rand_digits(4))
    candidate = "".join(body)
    check = vin_check_char(candidate)
    candidate = candidate[:8] + check + candidate[9:]
    return candidate


def mint_iban(country: str, length: int) -> str:
    """An IBAN whose bank code cannot be assigned.

    For the RU form (country + 2 + BIK 9 + account 20) the BBAN is built on
    «000000000», which fails the BIK's own first-two-digits rule, so the pair
    (bank, account) names no bank. A foreign form keeps its country and length
    and pads the BBAN the same way."""
    if country == "RU" and length == 33:
        bban = _SYNTHETIC_BIK + _personal_body(20)
    else:
        bban = "0" * (length - 4)
    return country + iban_check_digits(country, bban) + bban


def mint_loan_uid(case: str, grouped: bool) -> str:
    body = _rand_from("0123456789abcdef", 32)
    control = format(sum(int(ch, 16) * (i % 10 + 1)
                         for i, ch in enumerate(body)) % 16, "x")
    flat = body + control
    token = (f"{flat[:8]}-{flat[8:12]}-{flat[12:16]}-{flat[16:20]}-{flat[20:32]}-{flat[32]}"
             if grouped else flat)
    if case == "upper":
        return token.upper()
    if case == "lower":
        return token.lower()
    return token


def mint_bank_account(bik: str = "") -> str:
    """A 20-digit personal account whose key is ЦБ 515-consistent.

    With a BIK in the field context the key is the real pair's; without one the
    key is computed against the synthetic unassignable BIK, so the value is
    internally consistent and can name no real pair. The honest limit — the
    customer's own validator, if it checks against THEIR BIK, will not accept a
    value we could not compute against that BIK — is recorded in TYPES.md."""
    account = _personal_body(20)
    reference = bik if len(bik) == 9 and _ascii_digits(bik) else _SYNTHETIC_BIK
    key = cbr515_account_key(account, reference)
    return account[:8] + str(key) + account[9:]


def mint(type_id: str, original: str, bik: str = "") -> str:
    """The substitute for `original`: same shape, INHERITED verdict.

    A valid source mints a valid fake; a faulty source mints a faulty fake of
    the same shape (the fault is MIRRORED, never repaired). No re-mint loop
    exists — the loop is what makes a valid source into an invalid fake."""
    if type_id == "IMEI":
        token, valid = mint_imei(), validate_imei(original)
    elif type_id == "ICCID":
        length = len(_digits(original)) if len(_digits(original)) in (19, 20) else 19
        token, valid = mint_iccid(length), validate_iccid(original)
    elif type_id == "OMS_ENP":
        token, valid = mint_oms_enp(), validate_oms_enp(original)
    elif type_id == "OGRNIP":
        token, valid = mint_ogrnip(), validate_ogrnip(original)
    elif type_id == "EPTS_NUMBER":
        token, valid = mint_epts_number(), validate_epts_number(original)
    elif type_id == "UIN":
        length = 25 if len(_digits(original)) == 25 else 20
        token, valid = mint_uin(length), validate_uin(original)
    elif type_id == "LOYALTY_CARD_NUMBER":
        length = len(_digits(original)) if 13 <= len(_digits(original)) <= 18 else 13
        token, valid = mint_loyalty(length), validate_loyalty_card_number(original)
    elif type_id == "VIN":
        token, valid = mint_vin(), validate_vin(original)
    elif type_id == "IBAN":
        squeezed = original.replace(" ", "").upper()
        country = squeezed[:2] if squeezed[:2].isalpha() else "RU"
        length = len(squeezed) if len(squeezed) >= 15 else 33
        token, valid = mint_iban(country, length), validate_iban(original)
    elif type_id == "LOAN_UID":
        flat = original.replace("-", "")
        case = "upper" if flat.isupper() else "lower" if flat.islower() else "mixed"
        token, valid = (mint_loan_uid(case, "-" in original),
                        validate_loan_uid(original))
    elif type_id == "BANK_ACCOUNT":
        # THE ONE TYPE WHOSE CHECKSUM IS A PAIR PROPERTY, and therefore the one
        # place the inheritance is conditional. With a BIK the source's verdict
        # under that pair is inherited exactly; WITHOUT one the verdict is NOT
        # COMPUTABLE (each random account passes for some of the 1000 BIK
        # suffixes — A-07 «Необнаружимо» 2000/2000), so the engine does not
        # pretend to mirror it: it mints a shape-consistent PERSONAL account
        # whose key matches the synthetic unassignable BIK. Repaired or not is
        # an unknowable question here, not a silently answered one. See TYPES.md.
        if bik:
            token = mint_bank_account(bik)
            return token if validate_account(_digits(original), bik) \
                else _corrupt_check("BANK_ACCOUNT", token)
        return mint_bank_account()
    else:
        raise KeyError(f"not a v6 checksum type: {type_id!r}")
    return token if valid else _corrupt_check(type_id, token)


# ========================================================= token shapes ======
#
# On the OUT leg the vault finds candidates by SHAPE (`vault._token_re`), so a
# token shape that escapes the recognizer stops being reversible and a FAKE
# reaches the customer's tool. These are the shapes this module mints that the
# v5 alternation does not already cover.

TOKEN_PATTERNS: tuple[str, ...] = (
    r"(?i:[A-Z]{2}\d{2}[A-Z0-9]{29})",                    # IBAN, glued (RU)
    r"(?i:[A-Z]{2}\d{2}(?: [A-Z0-9]{4}){2,8})",           # IBAN, groups of four
    r"(?i:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}-[0-9a-f])",   # LOAN_UID
    r"(?i:[0-9a-f]{33})",                                 # LOAN_UID, glued
    r"(?i:\b[0-9A-HJ-NPR-Z]{17}\b)",                      # VIN
    r"\b\d{19}\b",                                        # ICCID (19)
    r"\b\d{25}\b",                                        # UIN (25)
    r"\b\d{14}\b|\b\d{17}\b|\b\d{18}\b",                  # LOYALTY (14/17/18)
)


def render_like_atomic(value: str, surface: str, for_tool: bool = False) -> str:
    """`value` laid into the SEPARATOR LAYOUT and letter case of `surface`.

    The form belongs to whoever wrote the mention, on both legs: on the IN leg
    the customer's grouping is mirrored onto the fake, and on the OUT leg the
    agent's regrouping is mirrored onto the real value. Applied only when the
    two carry the same number of alphanumeric characters — anything else is a
    different value and a splice would be a guess."""
    from pseudex import agent_form  # local: agent_form imports no v6 module

    ours = [ch for ch in value if ch.isalnum()]
    theirs = [ch for ch in surface if ch.isalnum()]
    if not ours or len(ours) != len(theirs):
        return value
    laid: list[str] = []
    index = 0
    for char in surface:
        if char.isalnum():
            laid.append(ours[index])
            index += 1
        else:
            laid.append(char)
    rendered = "".join(laid)
    return agent_form.cased_like(rendered, surface) if surface else rendered


# ==================================================================== identity ===
#
# THE SECOND FAMILY: the eight identity-document records of the v6 registry, all
# `generated_checksum == ""`. There is no arithmetic to inherit here — the
# mechanism is GRAMMAR (the registry's own `grammar` field) + TYPED CONTEXT (cue,
# field key, `pd_context`) and nothing else. Three of the eight carry
# `grammar_status == "ГРАММАТИКА?"` (BIRTH_CERT, CIVIL_ACT_CERT,
# RESIDENCE_PERMIT): their shape is recorded below as GRAMMAR_UNASSERTED — the
# conservative cue/key-anchored rule the registry's own sample satisfies, never a
# permissive regex invented to make a test green. The other five are `ГОТОВ`.
#
# WHERE EACH LABEL COMES FROM. Five of the eight already had an engine label
# (`engine_labels` in the registry), and a v5 conversation keeps its vocabulary
# and its rows:
#
#   INTL_PASSPORT  -> INTL_PASSPORT   (v5 label, priority 7, cue already leased)
#   BIRTH_CERT     -> BIRTH_CERT      (v5 label, priority 7, bare v5 recognizer)
#   DRIVER_LICENSE -> DRIVER_LICENSE  (v5 label, priority 7)
#   PTS_NUMBER     -> VEHICLE_DOC     (registry `engine_labels`)
#   STS_NUMBER     -> VEHICLE_DOC     (registry `engine_labels`)
#
# Two consequences are deliberate and recorded rather than hidden:
#
#   * CIVIL_ACT_CERT shares BIRTH_CERT. Its grammar is literally «как BIRTH_CERT»
#     (same series + six-digit number), and `ru_pii._BIRTH_CERT_RE` — the v5 bare
#     recognizer, outside this family's write scope — types that shape BIRTH_CERT
#     at PRIORITY 7 while a new label would default to 1 and LOSE to it. A v6
#     label split therefore needs the Lead's priority entry (handoff in
#     DELTA.json); until then sharing the label is the only outcome that protects
#     the value under the right family instead of under a v5 name chosen by luck.
#   * MILITARY_ID takes its own label, so the `№` form — the registry's own
#     sample «АК № 1234567» — types correctly. The registry's separator-free
#     variants («АК1234567») are ALSO a v5 plate shape (type 1А trailers) at
#     priority 5, so they stay typed PLATE until the Lead's priority entry. The
#     VALUE is masked either way; the label is what waits.
#
# NOTHING HERE IS A CHECKSUM. `mint_identity` never invents a check digit, never
# validates one, and never re-mints until something fails — the registry says
# `generated_checksum == ""`, and a fabricated validator would be a claim the
# registry does not make.

# Registry type id -> engine label. The label is what detection, the vault row,
# the audit trail and `_PRIORITY` speak; the type id is what the benchmark and
# the registry speak.
IDENTITY_LABEL: dict[str, str] = {
    "INTL_PASSPORT": "INTL_PASSPORT",
    "BIRTH_CERT": "BIRTH_CERT",
    "CIVIL_ACT_CERT": "BIRTH_CERT",
    "RESIDENCE_PERMIT": "RESIDENCE_PERMIT",
    "MILITARY_ID": "MILITARY_ID",
    "DRIVER_LICENSE": "DRIVER_LICENSE",
    "PTS_NUMBER": "VEHICLE_DOC",
    "STS_NUMBER": "VEHICLE_DOC",
}

IDENTITY_TYPES: tuple[str, ...] = (
    "INTL_PASSPORT", "BIRTH_CERT", "CIVIL_ACT_CERT", "RESIDENCE_PERMIT",
    "MILITARY_ID", "DRIVER_LICENSE", "PTS_NUMBER", "STS_NUMBER",
)

# A LABEL CAN COVER TWO REGISTRY TYPES (VEHICLE_DOC is СТС and ПТС; BIRTH_CERT is
# a birth certificate and a civil-act certificate), so the reverse map is
# one-to-many on purpose — the mint decides ПТС-vs-СТС from the SOURCE's shape
# (letters present => ПТС), not from the label.
LABEL_IDENTITY_TYPES: dict[str, tuple[str, ...]] = {
    label: tuple(type_id for type_id in IDENTITY_TYPES
                 if IDENTITY_LABEL[type_id] == label)
    for label in dict.fromkeys(IDENTITY_LABEL.values())
}

IDENTITY_LABELS: frozenset[str] = frozenset(IDENTITY_LABEL.values())

# `grammar_status == "ГРАММАТИКА?"` in the registry — the ORDER MINISTRY
# documents the composition of the series were not obtained (Приказ Минюста 167),
# so the shape below is only what the registry's own sample proves. Executors
# must not read this as a validator: it anchors recognition, it does not assert
# legality.
GRAMMAR_UNASSERTED: frozenset[str] = frozenset(
    ("BIRTH_CERT", "CIVIL_ACT_CERT", "RESIDENCE_PERMIT"))

# The one label whose registry `value_notation` is "glyph_fold": a ПТС series is
# Cyrillic on paper and Latin on a keyboard, and the two spellings are ONE
# document. BIRTH_CERT/MILITARY_ID keep their alphabet ("squeezed": a genuine
# Cyrillic «МЮ» is not a Latin twin), which is why the fold is per label and not
# global.
IDENTITY_FOLD_LABELS: frozenset[str] = frozenset(("VEHICLE_DOC",))
_VIN_GLYPH_FOLD = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")

# Roman numerals by CHARACTER COUNT. The series length is part of the format —
# the substitute keeps it, so `render_like_atomic` can lay the fake into the
# source's own separators and case without changing how many characters stand
# before the dash.
_ROMAN_BY_LENGTH: dict[int, tuple[str, ...]] = {
    1: ("I", "V", "X"),
    2: ("II", "IV", "VI", "IX", "XI", "XV"),
    3: ("III", "VII", "XII", "XVI"),
    4: ("VIII", "XIII", "XVII"),
}

# The Cyrillic capitals a series may be printed in. The registry's sample series
# «МЮ» and «АГ» are ordinary two-letter pairs; the alphabet is the Russian one,
# without the letters that do not begin a series pair in practice (Ъ, Ь, Ы).
_SERIES_LETTERS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ"

# Field separators of a document number. Presentation, never identity: the
# registry's `form_features` name none/space/hyphen/dot/slash/colon/numsign and
# "mixed", and «IV-МЮ № 123456», «IV-МЮ№123456» and «IVМЮ 123456» are one
# certificate.
_IDENTITY_SEPARATORS = re.compile(r"[\s\-./:№]+")

# RESIDENCE_PERMIT's series is a closed set in the registry's own grammar
# («серия «82»/«83»»), and that is the ONLY constraint on its content: what comes
# after it is seven free digits.
_RESIDENCE_SERIES: tuple[str, ...] = ("82", "83")

# One leading group that is a Roman numeral, for BIRTH_CERT/CIVIL_ACT_CERT.
_IDENTITY_ROMAN_HEAD = re.compile(r"^\s*([IVXІХ]+)")


def identity_signature(value: str, label: str) -> str:
    """The CONTENT identity of an identity document, typed by its label.

    AN IDENTITY DOCUMENT IS LETTERS **AND** DIGITS, and a digit-only signature
    would let two different documents answer for each other: «77 УК 123456» and
    «77 ХК 123456» are two ПТС, and `resolve_digit_signatures_typed` returns one
    row per signature. The registry's own `value_notation` says so per record —
    "digits" for the digit-only documents, "squeezed" for the certificate family,
    "glyph_fold" for ПТС — and this is that rule in one place.

    The label is part of the key on purpose (`label\\x1fcontent`): the same nine
    characters can be an INTL_PASSPORT or a RESIDENCE_PERMIT, and the two are not
    one document. `identity_label_of_shape` is the caller's half of the same
    contract."""
    squeezed = _IDENTITY_SEPARATORS.sub("", value).upper()
    if not squeezed:
        return ""
    if label in IDENTITY_FOLD_LABELS:
        squeezed = squeezed.translate(_VIN_GLYPH_FOLD)
    return f"{label}\x1f{squeezed}"


def identity_label_of_shape(value: str) -> str:
    """Which identity LABEL this spelling could be, for the signature lookup.

    Only the letter-bearing labels need a shape test (the digit-only ones are
    indexed by their digits, so they need no second reading). A wrong guess costs
    one indexed point query and returns nothing — the value must still be a row
    the vault minted, which is the same guarantee every other candidate has."""
    surface = value.strip()
    if _IDENTITY_ROMAN_HEAD.match(surface) and re.fullmatch(
            r"(?i:[IVXІХ]{1,4}[ \t.,\-/]{0,3}[А-ЯЁ]{2}"
            r"[ \t.,\-/]{0,3}№?[ \t.,\-/]{0,3}\d{6})", surface):
        return "BIRTH_CERT"
    if re.fullmatch(r"(?i:\d{2}[ \t.,\-/]{0,2}[А-ЯЁA-Z]{2}[ \t.,\-/]{0,2}\d{6})",
                    surface):
        return "VEHICLE_DOC"
    if re.fullmatch(r"(?i:[А-ЯЁA-Z]{2}[ \t.,\-/]{0,2}№?[ \t.,\-/]{0,2}\d{7})",
                    surface):
        return "MILITARY_ID"
    return ""


def _letters_like(sample: str) -> str:
    """One random letter in the SCRIPT, ALPHABET and CASE of `sample`.

    The script is carried, not guessed: a series typed in Latin («AK») stays
    Latin and a Cyrillic one («АК») stays Cyrillic, the same rule `notation`
    applies to a plate."""
    if sample.isascii():
        pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    else:
        pool = _SERIES_LETTERS
    letter = secrets.choice(pool)
    return letter.lower() if sample.islower() else letter


def _identity_content(label: str, surface: str) -> str:
    """The fake's CONTENT in the source's own character classes.

    One rule, three exceptions, and each exception is a fact the registry states:
    a certificate's leading group is a ROMAN numeral, a ВНЖ's series is 82/83,
    and a ПТС/ВНЖ number is digits. Everything else — how many, in what order, in
    which script and case — is read off the source, so the substitute cannot
    change the shape the customer's validator reads."""
    roman = _IDENTITY_ROMAN_HEAD.match(surface) if label in (
        "BIRTH_CERT", "CIVIL_ACT_CERT") else None
    out: list[str] = []
    if roman:
        # THE NUMERAL IS CHOSEN AS ONE VALUE, not drawn character by character:
        # three independent letters are «XVI» only by accident, and the series
        # must stay a numeral of the SAME LENGTH so the layout below is unchanged.
        length = roman.end(1)
        out.append(secrets.choice(_ROMAN_BY_LENGTH.get(length, (roman.group(1),))))
        rest = surface[length:]
    else:
        rest = surface
    for char in rest:
        if char.isdigit():
            out.append(secrets.choice("0123456789"))
        elif char.isalpha():
            out.append(_letters_like(char))
        else:
            out.append(char)
    rendered = "".join(out)
    if label == "RESIDENCE_PERMIT":
        # Серия «82»/«83» — the registry's grammar, and the only place in this
        # family where a value's first two digits are not free.
        digits = [i for i, ch in enumerate(rendered) if ch.isdigit()]
        series = secrets.choice(_RESIDENCE_SERIES)
        for slot, digit in zip(digits[:2], series):
            rendered = rendered[:slot] + digit + rendered[slot + 1:]
    return rendered


def mint_identity(label: str, original: str) -> str:
    """A format-preserving fake for an identity document.

    THE SHAPE IS THE CUSTOMER'S, THE CONTENT IS OURS — the same split the whole
    engine follows. `render_like_atomic` lays the fake into the source's
    separators and letter case, and `_identity_content` keeps its character
    classes, so the substitute satisfies every form check the real document does
    and names no document. There is no checksum to inherit (the registry gives
    none) and therefore no validity to preserve: what is preserved is FORMAT.

    An empty or content-free source falls back to the registry's own sample
    layout, so the mint is total — a renderer that raises is a 5xx on the masking
    path, which is the one failure this product does not accept."""
    surface = original.strip()
    if not surface or not any(ch.isalnum() for ch in surface):
        sample = {
            "INTL_PASSPORT": "75 1234567",
            "BIRTH_CERT": "IV-МЮ № 123456",
            "RESIDENCE_PERMIT": "82 1234567",
            "MILITARY_ID": "АК № 1234567",
            "DRIVER_LICENSE": "99 12 345678",
            "VEHICLE_DOC": "77 12 345678",
        }.get(label, "99 12 345678")
        surface = sample
    return render_like_atomic(_identity_content(label, surface), surface)


# Every shape `mint_identity` can be shown in — the source's separators and case
# mirrored. A token that escapes the restorer's shapes stops being reversible and
# a FAKE reaches the customer's tool, so these are matched from the same place
# that mints them (the rule `TOKEN_PATTERNS` above already states).
_ID_SEP = r"[ \t.,\-/]{0,2}"
IDENTITY_TOKEN_PATTERNS: tuple[str, ...] = (
    # The digit-only documents. `(?<!\d)`/`(?!\d)` are load-bearing: without them
    # a 20-digit account token would be read as a 9-digit passport standing in
    # its prefix, and the restorer would replace ten characters of a twenty.
    r"(?<!\d)\d{2}" + _ID_SEP + r"\d{7}(?!\d)",                    # INTL_PASSPORT
    r"(?<!\d)8[23]" + _ID_SEP + r"\d{7}(?!\d)",                    # RESIDENCE_PERMIT
    r"(?<!\d)\d{2}" + _ID_SEP + r"\d{2}" + _ID_SEP + r"\d{6}(?!\d)",   # licence/СТС
    # ПТС: series as digits, then two letters, then the number.
    r"(?<![0-9A-Za-zА-ЯЁа-яё])\d{2}" + _ID_SEP + r"[А-ЯЁA-Z]{2}"
    + _ID_SEP + r"\d{6}(?![0-9A-Za-zА-ЯЁа-яё])",
    # BIRTH_CERT / CIVIL_ACT_CERT, including the Cyrillic «І»/«Х» a Ukrainian
    # keyboard leaves in place of the Latin numeral characters, AND the fully
    # squeezed spelling an agent leaves when it strips our separators: the
    # detection shape keeps its hyphen because that is the grammar, but the
    # RESTORER must still recognise its own substitute (`identity_label_of_shape`
    # is the same reading) or the fake reaches the tool.
    r"(?i:[IVXІХ]{1,4}" + _ID_SEP + r"[А-ЯЁ]{2}"
    + _ID_SEP + r"№?" + _ID_SEP + r"\d{6})",
    # MILITARY_ID.
    r"(?<![0-9A-Za-zА-ЯЁа-яё])[А-ЯЁA-Z]{2}" + _ID_SEP + r"№?"
    + _ID_SEP + r"\d{7}(?!\d)",
)


# ==================================================================== legal =====
#
# THE THIRD FAMILY: the six legal/court records of the v6 registry, all
# `generated_checksum == ""` — COURT_CASE_UID, ARBITRAZH_CASE_NO,
# COURT_CASE_NO_SOU, FSSP_IP_NO, EXEC_DOC_NO, CADASTRAL_NUMBER. There is no
# arithmetic to inherit, so the mechanism is the same as §identity's: GRAMMAR
# (the registry's own `grammar` field) + TYPED CONTEXT (cue, field key,
# `pd_context`) and nothing else. ONE of the six carries
# `grammar_status == "ГРАММАТИКА?"` (EXEC_DOC_NO): its shape below is recorded as
# GRAMMAR_UNASSERTED — exactly the registry's grammar `[А-Я]{2}\s?№?\s?\d{9}`
# and nothing wider, never a permissive regex invented to make a test green.
#
# NOTHING HERE IS A CHECKSUM. `mint_legal` never invents a check digit, never
# validates one, and never re-mints until something fails: the registry says
# `generated_checksum == ""`, and a fabricated validator would be a claim the
# registry does not make. The one place the checksum family's rule would have
# applied — a "check position" to corrupt — does not exist here, and the mint
# says so by having no such branch.
#
# WHERE EACH LABEL COMES FROM. All six records carry `engine_labels == ()`, so
# every label below is NEW: the engine label is the registry's type id verbatim.
# That is deliberate and not cosmetic — the v6 metric separates types by name,
# and an alias would make two registry types indistinguishable in the metric, a
# fake pass (GOAL-BRIEF §N1: «unsupported alias не превращается в fake pass»).
#
# TWO ARBITRATION DECISIONS ARE MADE HERE, EACH FOR A STATED REASON.
#
#   1. THE COURT-CASE PAIR SHARES ONE IDENTITY KEY. ARBITRAZH_CASE_NO and
#      COURT_CASE_NO_SOU are two registry types with two labels, but the registry
#      gives them the SAME field keys (`case_number`, `номер_дела`) and the KEY
#      PATH TYPES THE WHOLE VALUE WITH NO SHAPE CHECK (P03, KEY_TYPE). One key
#      cannot name two types; the same case reached through a generic key and
#      through a cue would then mint TWO substitutes for ONE document. So
#      `legal_signature` keys both under the group "COURT_CASE", while the
#      DETECTED label stays distinct — the cue path is what names a type, and the
#      identity that must not fork is the content, not the label. The MINT is
#      family-aware for the same reason: it preserves the SOURCE's variant, not
#      the label's, so a case number typed through a generic key keeps its own
#      shape instead of being re-shaped into the other registry type.
#   2. `bare_typed=False` ON ALL SIX IS HONOURED. Every shape below is reached
#      through a cue or a field key; NOT ONE bare anchor is added. A bare
#      «77:01:0001001:1234» or a bare «А31-2840/2013» is NOT typed — the registry
#      says a bare value is not evidence, and a cadastral number's colon shape is
#      common enough in ordinary tables that claiming it bare would buy recall
#      with other people's data.

# Registry type id -> the engine label. Identity on purpose: see above.
LEGAL_LABEL: dict[str, str] = {
    "COURT_CASE_UID": "COURT_CASE_UID",
    "ARBITRAZH_CASE_NO": "ARBITRAZH_CASE_NO",
    "COURT_CASE_NO_SOU": "COURT_CASE_NO_SOU",
    "FSSP_IP_NO": "FSSP_IP_NO",
    "EXEC_DOC_NO": "EXEC_DOC_NO",
    "CADASTRAL_NUMBER": "CADASTRAL_NUMBER",
}

LEGAL_TYPES: tuple[str, ...] = tuple(LEGAL_LABEL)
LEGAL_LABELS: frozenset[str] = frozenset(LEGAL_LABEL.values())

# `grammar_status == "ГРАММАТИКА?"` in the registry. The federal law's appendix
# (ПП № 579) describes the blank, but the composition of the series was not
# asserted, so the shape is what the registry's own sample proves and it is named
# here rather than silently trusted. It anchors recognition; it does not assert
# legality.
LEGAL_GRAMMAR_UNASSERTED: frozenset[str] = frozenset(("EXEC_DOC_NO",))

# The registry's own `value_notation` per record. "squeezed" drops the
# separators; "glyph_fold" drops them AND folds the Cyrillic/Latin twins — the
# same two readings the identity family's certificates and ПТС already use, and
# the reason a УИД typed «77ОС0000-…» with Cyrillic О/С is ONE document with
# «77OS0000-…».
LEGAL_VALUE_NOTATION: dict[str, str] = {
    "COURT_CASE_UID": "glyph_fold",
    "ARBITRAZH_CASE_NO": "glyph_fold",
    "COURT_CASE_NO_SOU": "squeezed",
    "FSSP_IP_NO": "glyph_fold",
    "EXEC_DOC_NO": "glyph_fold",
    "CADASTRAL_NUMBER": "squeezed",
}
LEGAL_GLYPH_FOLD: frozenset[str] = frozenset(
    type_id for type_id, notation in LEGAL_VALUE_NOTATION.items()
    if notation == "glyph_fold")

# The registry's own `sample`, used as the fallback LAYOUT when the mint is
# handed a value that is not the label's shape at all (a KEY types the whole
# value, so that is reachable). The mint then answers with a well-shaped fake
# instead of echoing the source's characters.
LEGAL_SAMPLE: dict[str, str] = {
    "COURT_CASE_UID": "77OS0000-02-2026-000001-52",
    "ARBITRAZH_CASE_NO": "А31-2840/2013",
    "COURT_CASE_NO_SOU": "2-13/2015",
    "FSSP_IP_NO": "1234567/25/77001-ИП",
    "EXEC_DOC_NO": "ФС 012345678",
    "CADASTRAL_NUMBER": "77:01:0001001:1234",
}

# The Cyrillic capitals a court marker may be printed with, and their Latin
# twins. ARBITRAZH_CASE_NO's `form_features` name `script` and its `needle_kinds`
# name "glyph": the same case number typed through a Latin layout is the same
# case number, exactly as the ПТС series is. The twins are written out because
# the registry's own grammar writes the Cyrillic letter.
_A = r"[АA]"
_F = r"[ФF]"
_S = r"[СC]"
_P = r"[ПP]"

# THE GRAMMAR, ONE STRING PER TYPE, ALL OF IT FROM THE REGISTRY. The comment on
# each line says what was WIDENED and what was NOT:
#
#   * separators: the registry's `form_features` for these records name
#     `separators` over the closed list (none/space/hyphen/dot/slash/colon/…).
#     Where the separators are PRESENTATION the shape makes them optional or
#     takes the class; where they are STRUCTURE (FSSP's slashes, ARBITRAZH's
#     hyphen-slash, the SOU hyphen) they are kept exactly as the grammar writes
#     them. A shape that demands the glued form is the shape the customer copying
#     off their own document does not have.
#   * CADASTRAL_NUMBER's three separators are MANDATORY. The registry's grammar
#     writes colons and the record is `bare_typed=False`; a separator-free
#     spelling is an unanchored digit run, and no cue can make a bare run a
#     cadastral number safely.
#   * EXEC_DOC_NO is the registry's grammar verbatim (`\s?№?\s?` and all), per
#     `grammar_status == "ГРАММАТИКА?"`.
_LEGAL_SHAPE_TEXT: dict[str, str] = {
    "COURT_CASE_UID":
        r"\d{2}[A-ZА-ЯЁ]{2}\d{4}[ .\-]?\d{2}[ .\-]?\d{4}[ .\-]?\d{6}[ .\-]?\d{2}",
    "ARBITRAZH_CASE_NO":
        r"(?:" + _A + r"\d{2}-\d{1,7}-\d{1,5}/\d{4}"
        r"|" + _A + r"\d{2}-\d{1,7}/\d{4}"
        r"|\d{2}" + _A + _P + r"-\d{1,7}/\d{4}"
        r"|" + _F + r"\d{2}-\d{1,7}/\d{4}"
        r"|" + _S + r"01-\d{1,7}/\d{4})",
    "COURT_CASE_NO_SOU": r"(?:\d{1,2}[а-я]?|[МM])-\d{1,6}/\d{4}",
    "FSSP_IP_NO": r"\d{1,7}/\d{2}/\d{5}-(?:ИП|СД)|\d{1,7}/\d{2}/\d{2}/\d{2}",
    "EXEC_DOC_NO": r"[А-ЯЁA-Z]{2}\s?№?\s?\d{9}",
    "CADASTRAL_NUMBER": r"\d{2}[ .\-/:]\d{2}[ .\-/:]\d{6,7}[ .\-/:]\d{1,10}",
}

LEGAL_SHAPES: dict[str, "re.Pattern[str]"] = {
    label: re.compile(rf"(?i:{shape})") for label, shape in _LEGAL_SHAPE_TEXT.items()
}

# The labels whose letters are CONTENT rather than grammar, and therefore get
# refreshed like every digit does. ARBITRAZH's «А»/«Ф»/«С»/«АП», the SOU index
# letter and FSSP's «ИП»/«СД» are the TYPE — replacing them would mint a value
# that is not a case number at all. COURT_CASE_UID's two court-code letters and
# EXEC_DOC_NO's blank series are content: they are regenerated in the source's own
# script and case, so the substitute leaks neither the real court code nor the
# real blank series while keeping the shape the customer's form accepts.
_LEGAL_SERIES_IS_CONTENT: frozenset[str] = frozenset(
    ("COURT_CASE_UID", "EXEC_DOC_NO"))

# The two registry types ONE generic field key cannot separate (see decision 1
# above). Their identity key carries the GROUP, not the label.
_LEGAL_IDENTITY_GROUP: dict[str, str] = {
    "ARBITRAZH_CASE_NO": "COURT_CASE",
    "COURT_CASE_NO_SOU": "COURT_CASE",
}
_COURT_CASE_LABELS: tuple[str, ...] = ("ARBITRAZH_CASE_NO", "COURT_CASE_NO_SOU")

# THE FOLD IS A PROPERTY OF THE IDENTITY KEY, NOT OF THE CARD. The two
# court-case types share one key while their cards name DIFFERENT notations
# (ARBITRAZH «glyph_fold», COURT_CASE_NO_SOU «squeezed»), and folding by the CARD
# would give the same case two keys — the fork this group exists to prevent. So a
# key folds when ANY member of its group does: the stricter reading wins, and
# «2а-456/2026» and «2a-456/2026» are one case number typed on two layouts rather
# than two cases.
LEGAL_GLYPH_FOLD_GROUPS: frozenset[str] = frozenset(
    _LEGAL_IDENTITY_GROUP.get(type_id, type_id) for type_id in LEGAL_GLYPH_FOLD)


def legal_signature(value: str, label: str) -> str:
    """The CONTENT identity of a legal identifier, typed by its family.

    A legal number is letters AND digits («А31-2840/2013», «ФС 012345678»), and a
    digit-only signature would let two different blanks that share a digit run
    answer for each other. The separators go (the registry's `value_notation`),
    the case goes, the glyph twins go where the KEY's group says they do — and the
    key carries the FAMILY, so the same case number reached through a cue and
    through a generic field key is ONE row rather than two substitutes for one
    document. The label is deliberately NOT part of the key for the court-case
    pair; see the section comment."""
    squeezed = _IDENTITY_SEPARATORS.sub("", value).upper()
    if not squeezed:
        return ""
    group = _LEGAL_IDENTITY_GROUP.get(label, label)
    if group in LEGAL_GLYPH_FOLD_GROUPS:
        squeezed = squeezed.translate(_VIN_GLYPH_FOLD)
    return f"{group}\x1f{squeezed}"


# SQUEEZED READERS — the restorer's second line of defence, the same contract
# `identity_label_of_shape` states: the agent that strips our separators leaves a
# string that no longer matches the minted shape, and the FAKE then reaches the
# customer's tool with a 200. These patterns are used ONLY to guess which label a
# candidate could be; the guess is a point query against the vault and a wrong
# guess returns nothing.
#
# NOT EVERY SQUEEZE IS READABLE, AND THE UNREADABLE ONES ARE NAMED. A squeezed
# COURT_CASE_NO_SOU or CADASTRAL_NUMBER or FSSP alternative-2 is a bare digit run
# — a pattern for it would claim unrelated numbers and, on the restore leg, would
# swallow the real token standing after the false one. Those three squeezes are
# resolved by the DIGIT-SIGNATURE path instead (`vault._NUMERIC_TYPES` holds
# CADASTRAL_NUMBER; the SOU and FSSP rows are also indexed by their digits), and
# the token shapes keep their separators because that is how they are minted.
_LEGAL_SQUEEZED_TEXT: dict[str, str] = {
    "ARBITRAZH_CASE_NO":
        r"(?:" + _A + r"\d{2}\d{1,7}\d{1,5}\d{4}"
        r"|" + _A + r"\d{2}\d{1,7}\d{4}"
        r"|\d{2}" + _A + _P + r"\d{1,7}\d{4}"
        r"|" + _F + r"\d{2}\d{1,7}\d{4}"
        r"|" + _S + r"01\d{1,7}\d{4})",
    "FSSP_IP_NO": r"\d{1,7}\d{2}\d{5}(?:ИП|СД)",
}
_LEGAL_SQUEEZED: tuple[tuple[str, "re.Pattern[str]"], ...] = tuple(
    (label, re.compile(rf"(?i:{shape})"))
    for label, shape in _LEGAL_SQUEEZED_TEXT.items())


def legal_signatures(value: str) -> list[tuple[str, str]]:
    """Every (signature, label) this spelling could be — the restorer's question.

    MORE THAN ONE ANSWER IS POSSIBLE AND THAT IS THE POINT. Two of these records
    share a digit-run squeeze (a stripped SOU number and a stripped FSSP
    alternative-2 differ only in group lengths), so guessing ONE label and asking
    the vault once would lose whichever row the guess did not name. Each candidate
    is asked as its own indexed point query, and a hit is accepted only when its
    recorded label is the label the signature was proposed under — so a wrong
    reading can cost a query and can never restore another type's value."""
    surface = value.strip()
    if not surface:
        return []
    answers: list[tuple[str, str]] = []
    seen: set[str] = set()

    def propose(candidate: str, label: str) -> None:
        signature = legal_signature(candidate, label)
        if signature and signature not in seen:
            seen.add(signature)
            answers.append((signature, label))

    for label in LEGAL_TYPES:
        pattern = LEGAL_SHAPES.get(label)
        if pattern is not None and pattern.fullmatch(surface):
            propose(surface, label)
    squeezed = _IDENTITY_SEPARATORS.sub("", surface)
    for label, pattern in _LEGAL_SQUEEZED:
        if pattern.fullmatch(squeezed):
            propose(surface, label)
    return answers


def legal_label_of_shape(value: str) -> str:
    """The FIRST label this spelling could be, for callers that need one name.

    `legal_signatures` is what the restore seam uses (it can carry more than one
    reading); this convenience is for tests and for the single-guess callers, and
    it answers "" when nothing legal matches."""
    answers = legal_signatures(value)
    return answers[0][1] if answers else ""


def legal_label_for_source(original: str, label: str) -> str:
    """The LABEL whose variant the source itself is written in.

    THE SOURCE DECIDES THE SHAPE, NOT THE LABEL. A generic field key
    (`case_number`) types the whole value with no shape check, so an
    ARBITRAZH-shaped number can arrive labelled COURT_CASE_NO_SOU; re-shaping it
    into the other registry type's form would be a format change the customer's
    own validator reads. Within the court-case family the variant is read off the
    source; outside it the label stands."""
    if label in _COURT_CASE_LABELS:
        for candidate in _COURT_CASE_LABELS:
            pattern = LEGAL_SHAPES.get(candidate)
            if pattern is not None and pattern.fullmatch(original.strip()):
                return candidate
    return label


def _legal_pinned_positions(surface: str, label: str) -> set[int]:
    """Indices of DIGITS that are GRAMMAR and must survive the mint.

    ONE PLACE IN THIS FAMILY PINS A DIGIT, and the registry's own grammar pins
    it: the intellectual-rights court's number is written «С01-\\d{1,7}/\\d{4}» —
    the «01» is part of that court's designation, not a case counter. A generic
    digit refresh turned «С01-1234/2024» into «С61-4308/3572», which is not a СИП
    number at all and stopped matching its own shape (found by the round-trip
    test, not by a reader). Every other digit in the six grammars is free."""
    pinned: set[int] = set()
    if label == "ARBITRAZH_CASE_NO":
        sip = re.fullmatch(r"(?i:([СC])(01)(-\d{1,7}/\d{4}))", surface)
        if sip is not None:
            pinned.update((sip.start(2), sip.start(2) + 1))
    return pinned


def _legal_random_content(surface: str, label: str) -> str:
    """The same SURFACE with new content: every digit drawn, letters per type.

    A character-by-character rewrite is what keeps the shape EXACTLY — group
    lengths, separator layout, letter case and script are the source's by
    construction, which is the property the customer's form check reads. The
    digits the grammar itself pins stay (`_legal_pinned_positions`)."""
    pinned = _legal_pinned_positions(surface, label)
    out: list[str] = []
    for index, char in enumerate(surface):
        if index in pinned:
            out.append(char)
        elif char.isdigit():
            out.append(secrets.choice("0123456789"))
        elif char.isalpha():
            out.append(_letters_like(char) if label in _LEGAL_SERIES_IS_CONTENT
                       else char)
        else:
            out.append(char)
    return "".join(out)


def mint_legal(label: str, original: str) -> str:
    """A format-preserving fake for a legal identifier. No checksum, ever.

    The shape is the customer's; the content is ours. `render_like_atomic` lays
    the fake into the source's separators and letter case, and `_legal_random_content`
    keeps its character classes, so the substitute satisfies every form check the
    real number does and names no case, no proceeding and no plot.

    TWO FALLBACKS, BOTH FAIL-CLOSED. A source that does not match the label's
    shape (reachable only through a field key, which types the whole value with no
    shape check) is minted from the registry's own SAMPLE layout rather than
    echoed back — an echo would send the source's own characters to the model
    under a substitute's name. And the loop re-draws while the fake equals the
    source, so the mint cannot hand back the real value however improbable the
    draw; the mint is total, because a renderer that raises is a 5xx on the
    masking path."""
    resolved = legal_label_for_source(original, label)
    surface = original.strip()
    pattern = LEGAL_SHAPES.get(resolved)
    if not surface or pattern is None or not pattern.fullmatch(surface):
        resolved = legal_label_for_source(LEGAL_SAMPLE.get(label, ""), label)
        surface = LEGAL_SAMPLE.get(resolved, LEGAL_SAMPLE.get(label, ""))
    if not surface:
        return ""
    fake = render_like_atomic(_legal_random_content(surface, resolved), surface)
    for _ in range(8):
        if fake != surface:
            return fake
        fake = render_like_atomic(_legal_random_content(surface, resolved), surface)
    return fake


# Every shape `mint_legal` can be shown in. `unmask_text` finds candidates by
# SHAPE, so a token shape that escapes this tuple stops being reversible and a
# FAKE reaches the customer's tool — the invariant `TOKEN_PATTERNS` above
# already states, applied to this family. Two squeezes the AGENT may produce are
# included; the three that are indistinguishable from a bare digit run are
# deliberately NOT here (see `_LEGAL_SQUEEZED_TEXT`).
_LEGAL_TOKEN_START = r"(?<![0-9A-Za-zА-ЯЁа-яё])"
_LEGAL_TOKEN_END = r"(?![0-9A-Za-zА-ЯЁа-яё])"

LEGAL_TOKEN_PATTERNS: tuple[str, ...] = (
    # CADASTRAL_NUMBER: the three separators are mandatory — a separator-free
    # cadastral is a bare digit run, resolved by the digit-signature path.
    r"(?<!\d)\d{2}[ .\-/:]\d{2}[ .\-/:]\d{6,7}[ .\-/:]\d{1,10}(?!\d)",
    # COURT_CASE_UID: the two letters pin the type, so the separators may be
    # absent — that is the squeeze the agent may write.
    _LEGAL_TOKEN_START
    + r"(?i:\d{2}[A-ZА-ЯЁ]{2}\d{4}[ .\-]?\d{2}[ .\-]?\d{4}[ .\-]?\d{6}[ .\-]?\d{2})"
    + _LEGAL_TOKEN_END,
    # EXEC_DOC_NO: two letters and nine digits, «№» and spacing optional.
    _LEGAL_TOKEN_START + r"(?i:[А-ЯЁA-Z]{2}\s?№?\s?\d{9})(?!\d)" + _LEGAL_TOKEN_END,
    # ARBITRAZH_CASE_NO: the registry's separators, then the squeezes.
    _LEGAL_TOKEN_START + r"(?i:" + _A + r"\d{2}-\d{1,7}-\d{1,5}/\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _A + r"\d{2}-\d{1,7}/\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:\d{2}" + _A + _P + r"-\d{1,7}/\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _F + r"\d{2}-\d{1,7}/\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _S + r"01-\d{1,7}/\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _A + r"\d{2}\d{1,7}\d{1,5}\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _A + r"\d{2}\d{1,7}\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:\d{2}" + _A + _P + r"\d{1,7}\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _F + r"\d{2}\d{1,7}\d{4})" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:" + _S + r"01\d{1,7}\d{4})" + _LEGAL_TOKEN_END,
    # COURT_CASE_NO_SOU: the registry's separators only (a squeeze is a bare run).
    _LEGAL_TOKEN_START + r"(?i:(?:\d{1,2}[а-я]?|[МM])-\d{1,6}/\d{4})" + _LEGAL_TOKEN_END,
    # FSSP_IP_NO: alternative 1 with and without separators; alternative 2 only
    # as it is minted, because its squeeze is a bare digit run.
    _LEGAL_TOKEN_START + r"(?i:\d{1,7}/\d{2}/\d{5}-(?:ИП|СД))" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"(?i:\d{1,7}\d{2}\d{5}(?:ИП|СД))" + _LEGAL_TOKEN_END,
    _LEGAL_TOKEN_START + r"\d{1,7}/\d{2}/\d{2}/\d{2}" + _LEGAL_TOKEN_END,
)


# THE FAMILY'S OWN ALTERNATION, COMPILED ONCE. `vault._token_re` carries these
# shapes too, but its scan is leftmost-first and NON-OVERLAPPING, and a legal
# token can begin after a two-letter word and «№»: the masked FSSP proceeding
# «ИП № 4542450/74/44664-ИП» makes another family's identity shape
# (`[А-ЯЁ]{2} №? \d{7}`) match the CUE AND THE FIRST GROUP as one candidate, and
# `finditer` then resumes after it, so the real token is never seen. The restore
# asks this alternation separately (see `redact._restore_tokens_spans`) so the
# family's reversibility does not depend on who else matched nearby.
LEGAL_TOKEN_RE = re.compile("|".join(LEGAL_TOKEN_PATTERNS))


# ==================================================================== finance ===
#
# THE FOURTH FAMILY: the ten finance / insurance / medical records of the v6
# registry — LOAN_CONTRACT_NUMBER, CREDIT_SUBJECT_CODE, DMS_POLICY,
# OSAGO_POLICY, KASKO_POLICY, INSURANCE_CLAIM_NUMBER, MEDCARD_NUMBER,
# ELN_NUMBER, PRESCRIPTION_NUMBER, REFERRAL_NUMBER. NONE of them carries a
# checksum (`generated_checksum == ""` on all ten), so — exactly as in §identity
# and §legal — the mechanism is GRAMMAR + TYPED CONTEXT and NOTHING ELSE.
# `mint_finance` never invents a check digit, never validates one and never
# re-mints until something fails: the registry says there is no arithmetic, and a
# fabricated validator would be a claim the registry does not make.
#
# WHAT IS NEW HERE, AND WHY IT IS THE HARDEST OF THE FOUR FAMILIES. The other
# three families could lean on a FORMAT: a checksum, a fixed group layout, a
# closed series list. Eight of these ten records say «национальной НЕТ» — there is
# no national format to read — and the registry's own `grammar` field names the
# forms its authors saw («12-345678/2025», «001SB12345678», «У-671-475136/25»).
# So the shape below is a CONSERVATIVE SHAPE RULE, not a grammar copied from a
# standard, and two consequences are recorded rather than hidden:
#
#   1. `bare_typed=False` ON ALL TEN IS HONOURED LITERALLY. Every shape is
#      reached through a cue or a field key; NOT ONE bare anchor is added. A bare
#      «12345/2024» is a case number, a tariff or a fraction — the registry says a
#      bare value is not evidence, and the engine already has fourteen v5 shapes
#      that would fight over it.
#   2. THE SHAPE FORBIDS TWO THINGS A FREE-FORM NUMBER WOULD OTHERWISE SWALLOW.
#      A DATE is excluded by a lookahead (`(?!dd.mm.yyyy)` / `(?!yyyy-mm-dd)`),
#      because «история болезни 12.03.2020» must keep its date — a typed span
#      CONTAINS and therefore REPLACES the DATE span the v5 recognizer found, so
#      without the guard the customer's date would come back as a fake medcard
#      number. And a DIGIT SPACE DIGIT extension is bounded: the run may cross
#      «.», «-», «/» and a short letter group (an issuer prefix: «МФО-», «SB»,
#      «001SB»), but a SPACE may separate at most TWO groups — so an ordinary
#      sentence cannot glue a number onto the next one.
#
# WHERE EACH LABEL COMES FROM. All ten records carry `engine_labels == ()`, so
# every label is the registry's type id VERBATIM. An alias would make two registry
# types indistinguishable in the v6 metric — a fake pass, which GOAL-BRIEF §N1
# forbids by name («unsupported alias не превращается в fake pass»).
#
# TWO RECORDS ARE `ГРАММАТИКА?`, AND THEY ARE NAMED. OSAGO_POLICY's primary
# source was not obtained (РСА refused TLS, НСИС answered 403, and the series
# forms come from insurers' reference pages); REFERRAL_NUMBER's national grammar
# is «НЕ установлена (первоисточник не получен)». Their shapes are exactly what
# the registry's own grammar and sample prove and nothing wider, and the constant
# that says so is `FINANCE_GRAMMAR_UNASSERTED`.

# Registry type id -> the engine label. Identity on purpose: `engine_labels == ()`
# for all ten, so the label a conversation already had cannot move, and the metric
# can separate the types.
FINANCE_LABEL: dict[str, str] = {
    "LOAN_CONTRACT_NUMBER": "LOAN_CONTRACT_NUMBER",
    "CREDIT_SUBJECT_CODE": "CREDIT_SUBJECT_CODE",
    "DMS_POLICY": "DMS_POLICY",
    "OSAGO_POLICY": "OSAGO_POLICY",
    "KASKO_POLICY": "KASKO_POLICY",
    "INSURANCE_CLAIM_NUMBER": "INSURANCE_CLAIM_NUMBER",
    "MEDCARD_NUMBER": "MEDCARD_NUMBER",
    "ELN_NUMBER": "ELN_NUMBER",
    "PRESCRIPTION_NUMBER": "PRESCRIPTION_NUMBER",
    "REFERRAL_NUMBER": "REFERRAL_NUMBER",
}

FINANCE_TYPES: tuple[str, ...] = tuple(FINANCE_LABEL)
FINANCE_LABELS: frozenset[str] = frozenset(FINANCE_LABEL.values())

# `grammar_status == "ГРАММАТИКА?"` in the registry. OSAGO_POLICY: the primary
# source (РСА/НСИС/Положение 431-П) was not obtained, the series forms are
# second-hand, and the «12 letters that may stand in a series» restriction is
# explicitly «НЕ проверено» — so the series class below takes ANY three capitals
# and the shape asserts only the composition. REFERRAL_NUMBER: 057/у-04 and the
# electronic referrals in МИС/РЕГИЗ, national grammar NOT established. Both are
# conservative cue/key-anchored shapes; neither is a validator.
FINANCE_GRAMMAR_UNASSERTED: frozenset[str] = frozenset(
    ("OSAGO_POLICY", "REFERRAL_NUMBER"))

# The one record whose `pd_context` is set: OSAGO_POLICY is `OD-22` — «объектные
# номера: позитив при владельце-физлице, в контексте юрлица — негатив». THE RULE
# IS RECORDED AND NOT IMPLEMENTED, and that is honest rather than lazy: nothing in
# this pipeline carries an OWNER signal. The detected span is a policy number; who
# owns the car is decided by the customer's own data, which the gateway never
# sees. A recognizer cannot invent the discriminator, and pretending to would be
# the fabricated-evidence failure GOAL-BRIEF §7 forbids. See TYPES.md / DELTA.json.
FINANCE_PD_CONTEXT: dict[str, str] = {"OSAGO_POLICY": "OD-22"}

# The registry's own `needle_kinds` per record, copied so the two derived sets
# below are READ rather than asserted by hand.
FINANCE_NEEDLE_KINDS: dict[str, tuple[str, ...]] = {
    "LOAN_CONTRACT_NUMBER": ("whole", "squeezed", "glyph", "digits"),
    "CREDIT_SUBJECT_CODE": ("whole",),
    "DMS_POLICY": ("whole", "squeezed", "glyph"),
    "OSAGO_POLICY": ("whole", "glyph", "digits"),
    "KASKO_POLICY": ("whole", "squeezed", "glyph"),
    "INSURANCE_CLAIM_NUMBER": ("whole", "squeezed", "glyph"),
    "MEDCARD_NUMBER": ("whole", "squeezed", "digits"),
    "ELN_NUMBER": ("whole", "digits"),
    "PRESCRIPTION_NUMBER": ("whole", "squeezed", "digits"),
    "REFERRAL_NUMBER": ("whole", "squeezed"),
}

# `glyph` in `needle_kinds` means the record's letters may be typed on EITHER
# layout — OSAGO's «ХХХ» against a Latin «XXX» is one series, exactly as a VIN's
# Cyrillic look-alikes are — so the identity key folds the twins. CREDIT_SUBJECT_
# CODE is deliberately NOT here: the ЦБ rule says the code is letters of ONE
# alphabet, and folding would merge two codes written in two alphabets into one
# row (the law says those are different codes).
_FINANCE_GLYPH_FOLD: frozenset[str] = frozenset(
    type_id for type_id, kinds in FINANCE_NEEDLE_KINDS.items() if "glyph" in kinds)

# `digits` in `needle_kinds` means a DIGIT-ONLY reading of the value is an
# identity (the registry states it per record). Kept as the registry-derived fact
# it is; `vault._NUMERIC_TYPES` is the engine's own, wider list and explains why.
FINANCE_NUMERIC_LABELS: frozenset[str] = frozenset(
    type_id for type_id, kinds in FINANCE_NEEDLE_KINDS.items() if "digits" in kinds)

# The registry's own `value_notation` per record. "squeezed" drops the
# separators; "digits" is the digit-only reading; "" is the empty value the four
# free-form records carry, and for those the separators are PRESENTATION (every
# one of them lists `separators` in `form_features`), so the signature squeezes
# them exactly as the identity family does.
FINANCE_VALUE_NOTATION: dict[str, str] = {
    "LOAN_CONTRACT_NUMBER": "",
    "CREDIT_SUBJECT_CODE": "",
    "DMS_POLICY": "",
    "OSAGO_POLICY": "squeezed",
    "KASKO_POLICY": "",
    "INSURANCE_CLAIM_NUMBER": "",
    "MEDCARD_NUMBER": "squeezed",
    "ELN_NUMBER": "digits",
    "PRESCRIPTION_NUMBER": "squeezed",
    "REFERRAL_NUMBER": "squeezed",
}

# The registry's own `sample`, used as the fallback LAYOUT when the mint is handed
# something that is not the label's shape at all (a field key types the WHOLE
# value with no shape check, so that is reachable). The mint then answers with a
# well-shaped fake instead of echoing the source's own characters.
FINANCE_SAMPLE: dict[str, str] = {
    "LOAN_CONTRACT_NUMBER": "12-345678/2025",
    "CREDIT_SUBJECT_CODE": "Qw7rT2",
    "DMS_POLICY": "001SB12345678",
    "OSAGO_POLICY": "ХХХ 0123456789",
    "KASKO_POLICY": "AI123456789",
    "INSURANCE_CLAIM_NUMBER": "У-671-475136/25",
    "MEDCARD_NUMBER": "12345/2024",
    "ELN_NUMBER": "900012345678",
    "PRESCRIPTION_NUMBER": "45 0012345678",
    "REFERRAL_NUMBER": "057-2024-001234",
}

# ---------------------------------------------------------------- the shapes ---
#
# ONE SHAPE LANGUAGE, THREE FACTS ABOUT IT, AND EACH FACT IS WHY THE OTHER TWO
# CHOICES WERE REJECTED:
#
#   * A LETTER MAY STAND IN ITS OWN ALPHABET. These numbers are printed with
#     Cyrillic prefixes («МФО-», «ДМС-», «КАСКО-», «У-») and Latin ones
#     («AI123456789», «001SB12345678»), and a free-form number does not say which
#     — so `[A-Za-zА-Яа-яЁё]` accepts either, script preserved at the mint.
#   * THE GAP BETWEEN TWO DIGITS CARRIES SEPARATORS OR A SHORT LETTER GROUP, BUT
#     NEVER A SPACE AROUND THAT GROUP. «001SB12345678» and «12-345678/2025» must
#     hold together; «456 — 789» and «12 или 34» must not. A letter group may be
#     glued or joined by `.-/` (that is how issuer prefixes are printed); a SPACE
#     next to a letter group ends the token. This is the rule that keeps a
#     sentence from being read as one long number.
#   * A SPACE MAY JOIN EXACTLY TWO GROUPS, and that alternative is written out
#     separately so it is BOUNDED. The registry's own spaced sample is
#     «45 0012345678» (PRESCRIPTION_NUMBER); a repeating `(?: \d+)*` gap would let
#     a date on the next word be swallowed into the value, which is the over-mask
#     this family measured against (see `_FIN_NOT_A_DATE`).
_FIN_LETTER = r"[A-Za-zА-Яа-яЁё]"
_FIN_GAP = (r"(?:[.\-/]{0,2}|[.\-/]?" + _FIN_LETTER + r"{1,5}[.\-/]?)")
# A DATE IS NOT A DOCUMENT NUMBER, AND THE LOOKAHEAD IS THE ONLY PLACE THAT CAN
# SAY SO. `(shape)` is wrapped and the TYPED span then CONTAINS the DATE span the
# v5 recognizer already found, so the DATE is dropped and the customer's
# «12.03.2020» would arrive at the model as a fake medcard number — the date lost
# from the agent's view and a wrong value handed to a tool that asked for it.
_FIN_NOT_A_DATE = (r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))"
                   r"(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))")
# A PLUS BEFORE THE RUN MEANS A PHONE. The gap language would otherwise read the
# ten digits of «+7 999 123-45-67» as a document number behind any cue.
_FIN_NOT_PHONE = r"(?<!\+)"


def _free_number(lo: int, hi: int) -> str:
    """A free-form document number: `lo`..`hi` digits, presentation separators,
    an optional letter prefix, and ONE bounded space-joined alternative.

    The digit count is bounded by the REPETITION, `\\d(?:GAP\\d){lo-1,hi-1}` —
    exactly one digit per repetition, so a 25-digit run can never be advertised as
    a 20-digit number by backtracking: every shorter end is still followed by a
    digit and `\\b` refuses it."""
    glued = (_FIN_NOT_PHONE + r"(?:" + _FIN_LETTER + r"{1,5}[.\-/]?)?"
             + r"\d(?:" + _FIN_GAP + r"\d){"
             + str(lo - 1) + "," + str(hi - 1) + r"}")
    return _FIN_NOT_A_DATE + r"(?:" + glued + r"|\d{2,8} \d{2,12})"


# CREDIT_SUBJECT_CODE is the one record with a REAL grammar (Указание ЦБ 6474-У
# п. 1.3): 4–15 characters, digits plus letters of ONE alphabet, case-insensitive.
# The shape enforces all three facts, and the single-alphabet clause is enforced
# rather than assumed — a code that mixes Cyrillic and Latin is not a code the
# rule describes, and folding it into one key would merge two subjects.
_FIN_CODE = (r"(?:(?=[A-Za-z0-9]{4,15}(?![A-Za-z0-9]))(?=[A-Za-z]*\d)"
             r"(?=\d*[A-Za-z])[A-Za-z0-9]{4,15}"
             r"|(?=[А-Яа-яЁё0-9]{4,15}(?![А-Яа-яЁё0-9]))(?=[А-Яа-яЁё]*\d)"
             r"(?=\d*[А-Яа-яЁё])[А-Яа-яЁё0-9]{4,15})")

# OSAGO_POLICY: three capitals (Cyrillic «ХХХ»/«ТТТ» or the Latin «XXX» a form
# prints) and a ten-digit number, with the registry's own optional «№» and the
# word «номер»/«серия» that stands between series and number in the printed form
# «серия ТТТ номер 7012345678». `ГРАММАТИКА?` — the shape is the composition the
# registry states and does not restrict the twelve letters it could not verify.
_FIN_OSAGO = (r"(?:[А-ЯЁ]{3}|[A-Z]{3})[ .\-]?(?:№|N|номер)?[ .\-]?\d{10}(?!\d)")

# ELN_NUMBER: the СФР specification says «xs:string, Макс.длинна: 12» and every
# example the emitter prints is TWELVE DIGITS on «9000…». The digit form is what a
# customer copies and what 1С:ЗУП imports, and it is the form the shape claims —
# a shorter string is not claimed at all rather than guessed (see not-implemented).
_FIN_ELN = r"(?<!\d)\d{12}(?!\d)"

# THE REGISTRY'S OWN WIDEST FORM PER RECORD. The bounds are the digit counts the
# registry names or its samples show; where the registry gives no length («свободная
# форма») the bound is the sample family's own spread, never an unbounded `\d+`.
_FINANCE_SHAPE_TEXT: dict[str, str] = {
    # «цифры 8–20, с «/»/«-» и годом, буквенные префиксы».
    "LOAN_CONTRACT_NUMBER": _free_number(8, 20),
    "CREDIT_SUBJECT_CODE": _FIN_CODE,
    # «цифры, часто «/год» или префикс отделения»; 16-digit card form included.
    "DMS_POLICY": _free_number(6, 20),
    "OSAGO_POLICY": _FIN_OSAGO,
    # «AI123456789», «7100-12345678», «КАСКО-001-2025-0001234».
    "KASKO_POLICY": _free_number(6, 20),
    # «У-671-475136/25», «0012345678-001», «ОСАГО-25-123456».
    "INSURANCE_CLAIM_NUMBER": _free_number(5, 20),
    # «12345/2024» — the registry's `digits` needle names «если ≥4».
    "MEDCARD_NUMBER": _free_number(4, 20),
    "ELN_NUMBER": _FIN_ELN,
    # Бумажный 148-1/у-04(л): серия (2 цифры ОКАТО) + номер.
    "PRESCRIPTION_NUMBER": _free_number(4, 20),
    # «057-2024-001234»; `ГРАММАТИКА?`.
    "REFERRAL_NUMBER": _free_number(5, 20),
}

FINANCE_SHAPES: dict[str, "re.Pattern[str]"] = {
    label: re.compile(rf"(?i:{shape})")
    for label, shape in _FINANCE_SHAPE_TEXT.items()
}


def finance_signature(value: str, label: str) -> str:
    """The CONTENT identity of a finance identifier, typed by its own label.

    A finance number is letters AND digits («У-671-475136/25», «001SB12345678»)
    and a digit-only signature would let two identifiers that share a digit run
    answer for each other: `resolve_digit_signatures_typed` returns one row per
    signature, so «12-345678/2025» and «98-345678/2025» would be one contract.
    The separators go (presentation, per the registry's `form_features`), the case
    goes, the Cyrillic/Latin twins go where the record's own `glyph` needle says
    they do, and the LABEL is part of the key — so a DMS policy number and a
    KASKO policy number that happen to be written the same way are two documents,
    which is what the registry's ten separate records assert."""
    squeezed = _IDENTITY_SEPARATORS.sub("", value).upper()
    if not squeezed:
        return ""
    if label in _FINANCE_GLYPH_FOLD:
        squeezed = squeezed.translate(_VIN_GLYPH_FOLD)
    return f"{label}\x1f{squeezed}"


def finance_signatures(value: str) -> list[tuple[str, str]]:
    """Every (signature, label) this spelling could be — the restorer's question.

    MORE THAN ONE ANSWER IS POSSIBLE AND THAT IS THE POINT. The free-form shapes
    overlap by construction — «12345/2024» is a MEDCARD_NUMBER and, at another
    digit count, a PRESCRIPTION_NUMBER — so guessing ONE label would lose
    whichever row the guess did not name. Each reading is asked as its own indexed
    point query and a hit is kept only when the vault's recorded label is the
    label the signature was proposed under, exactly as `legal_signatures` does. A
    wrong reading costs one query and can never restore another type's value."""
    surface = value.strip()
    if not surface:
        return []
    answers: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, pattern in FINANCE_SHAPES.items():
        if not pattern.fullmatch(surface):
            continue
        signature = finance_signature(surface, label)
        if signature and signature not in seen:
            seen.add(signature)
            answers.append((signature, label))
    return answers


def finance_label_of_shape(value: str) -> str:
    """The FIRST label this spelling could be, for callers that need one name."""
    answers = finance_signatures(value)
    return answers[0][1] if answers else ""


def finance_label_for_source(original: str, label: str) -> str:
    """The label whose VARIANT the source itself is written in.

    The free-form labels share one shape language, so a generic field key can hand
    a value to a label whose own registry sample looks different. The mint must
    preserve the SOURCE's variant — re-shaping «001SB12345678» into a
    «12345/2024» medcard would hand the customer's validator a document that is
    not there. Only a label whose own shape does NOT accept the source is
    re-labelled, and only to another label that does."""
    pattern = FINANCE_SHAPES.get(label)
    if pattern is not None and pattern.fullmatch(original.strip()):
        return label
    for candidate, candidate_pattern in FINANCE_SHAPES.items():
        if candidate_pattern.fullmatch(original.strip()):
            return candidate
    return label


def _finance_content(surface: str) -> str:
    """The same SURFACE with every alphanumeric character drawn afresh.

    ONE RULE, AND IT IS THE ONE THE FROZEN BENCHMARK ALREADY STATES: the v6 mint
    rules `id_digits`/`id_alnum` (`bench/agentpii5/perfect.py §6.2`) change EVERY
    alphanumeric character in place and keep every separator, so the grammar holds
    and no position is shared with the source (T8). Digits are drawn from 0–9,
    letters from the source's OWN script and case (`_letters_like`) — so a
    Cyrillic «ДМС-» stays Cyrillic and does not silently become a Latin twin,
    which is the same rule the identity family applies to a series."""
    out: list[str] = []
    for char in surface:
        if char.isdigit():
            out.append(secrets.choice("0123456789"))
        elif char.isalpha():
            out.append(_letters_like(char))
        else:
            out.append(char)
    return "".join(out)


def mint_finance(label: str, original: str) -> str:
    """A format-preserving fake for a finance identifier. No checksum, ever.

    THE SHAPE IS THE CUSTOMER'S, THE CONTENT IS OURS. `render_like_atomic` lays
    the fake into the source's separators and letter case and `_finance_content`
    keeps its character classes, so the substitute satisfies every form check the
    real number does and names no contract, no policy and no patient.

    TWO FALLBACKS, BOTH FAIL-CLOSED, both reachable only through a field key,
    which types the WHOLE value with no shape check: a source that is not the
    label's shape is minted from the registry's own SAMPLE layout rather than
    echoed back (an echo would send the source's own characters to the model under
    a substitute's name), and the loop re-draws while the fake equals the source,
    so the mint cannot hand back the real value however improbable the draw. The
    mint is TOTAL — a renderer that raises is a 5xx on the masking path, the one
    failure this product does not accept."""
    resolved = finance_label_for_source(original, label)
    surface = original.strip()
    pattern = FINANCE_SHAPES.get(resolved)
    if not surface or pattern is None or not pattern.fullmatch(surface):
        surface = FINANCE_SAMPLE.get(label, "")
        resolved = finance_label_for_source(surface, label)
    if not surface:
        return ""
    fake = render_like_atomic(_finance_content(surface), surface)
    for _ in range(8):
        if fake != surface:
            return fake
        fake = render_like_atomic(_finance_content(surface), surface)
    return fake


# Every shape `mint_finance` can be shown in. `unmask_text` finds candidates by
# SHAPE, so a token shape that escapes this tuple stops being reversible and a
# FAKE reaches the customer's tool — the invariant `TOKEN_PATTERNS` states, applied
# to this family. Each pattern is the SHAPE ORIGINALLY WRITTEN, wrapped in the
# alphanumeric boundary; the tuple is appended to `vault._token_re` AFTER the bare
# digit runs (see the caller's comment) so no free-form shape can claim the head of
# another family's token.
_FIN_TOKEN_START = r"(?<![0-9A-Za-zА-Яа-яЁё])"
_FIN_TOKEN_END = r"(?![0-9A-Za-zА-Яа-яЁё])"

FINANCE_TOKEN_PATTERNS: tuple[str, ...] = tuple(
    _FIN_TOKEN_START + shape + _FIN_TOKEN_END
    for shape in _FINANCE_SHAPE_TEXT.values())

# THE FAMILY'S OWN ALTERNATION, COMPILED ONCE — the same second line of defence
# `LEGAL_TOKEN_RE` is. `vault._token_re` is a non-overlapping leftmost-first scan,
# so a token another family's shape matches AROUND is skipped in full; asking this
# alternation separately means the family's reversibility never depends on who else
# matched nearby. Dead candidates cost nothing: a signature that resolves to
# nothing is never spliced.
FINANCE_TOKEN_RE = re.compile("|".join(FINANCE_TOKEN_PATTERNS))


# ==================================================================== telecom ===
#
# THE FIFTH AND LAST FAMILY: the eight telecom / device records of the v6
# registry — IMSI, MAC, IP_ADDRESS, ESIA_OID, MOBILE_AD_ID, APP_DEVICE_ID,
# METRICA_CLIENT_ID, SUBSCRIBER_ACCOUNT. NONE of them carries a checksum
# (`generated_checksum == ""` on all eight), so — exactly as in §identity,
# §legal and §finance — the mechanism is GRAMMAR + TYPED CONTEXT and nothing
# else. `mint_telecom` never invents a check digit, never validates one and
# never re-mints until something fails.
#
# WHAT IS NEW HERE, AND WHAT IS NOT.
#
#   * NOT NEW: the mechanism. Four families already run on cue/key + shape.
#   * NEW, AND IT IS THE POINT OF THIS FAMILY: ONE REGISTRY RECORD MAPS TO AN
#     ENGINE LABEL THE v5 ENGINE ALREADY USES — `IP_ADDRESS -> IP` — and TWO of
#     the eight (`MAC`, `IP_ADDRESS`) ALREADY HAVE A BARE v5 RECOGNIZER AND A
#     PRIORITY SLOT. So this family is the first that must EXTEND a label rather
#     than introduce one, and the extension is written as a second USE of the
#     same label, never as a second label: two labels for one value would either
#     fight over the span (this family's labels other than MAC/IP default to
#     priority 1, `IP` and `MAC` are 5 — the v5 span would win and a second label
#     would be dead code) or split one value into two rows. `engine_labels` in
#     the registry says exactly this for IP_ADDRESS, and the same reasoning is
#     applied to MAC, whose v5 recognizer reads the 2-2-2-2-2-2 forms only.
#   * NEW: THREE of the eight are ALPHANUMERIC HEX — the first family whose
#     identity carries letters that are NOT a document series. A MAC, a GAID and
#     an IFV are one device under any of the notations the registry names, and
#     `telecom_signature` is where that identity lives.
#
# `bare_typed=False` ON ALL EIGHT, AND THE HONEST READING OF IT IS PER TYPE.
# For the six with no bare v5 anchor (IMSI, ESIA_OID, MOBILE_AD_ID,
# APP_DEVICE_ID, METRICA_CLIENT_ID, SUBSCRIBER_ACCOUNT) NOT ONE bare anchor is
# added: a bare 15-digit run is an ОГРНИП and a bare 18-digit run is a loyalty
# card, and claiming either bare would buy recall with other people's
# identifiers. MAC and IP_ADDRESS are DIFFERENT and the difference is recorded
# rather than smoothed over: `detect_vehicle_ids` and the v5 IPv4 regex ALREADY
# claim their shapes with no cue at all, on the engine's own v5 authority. This
# family does not remove that — `COV-INTEGRATION-KEEP-V5` — and it cannot
# pretend such a value is untyped. What it does is close the v5 shapes' gaps
# (glued/dotted MAC, IPv6, the field keys `mac_address`, `client_ip`,
# `x_forwarded_for`) under the SAME label, so a value claimed bare by v5 and a
# value claimed by this family's key are one row, not two.
#
# NO RECORD IN THIS FAMILY IS `ГРАММАТИКА?` — all eight carry
# `grammar_status == "ГОТОВ"` — and `TELECOM_GRAMMAR_UNASSERTED` says so
# POSITIVELY rather than leaving a reader to infer it from a missing name. The
# one place the registry itself names an unread source is IP_ADDRESS's IPv6
# clause: «IPv6 — по RFC 5952 (не прочитан)». That is recorded, and the IPv6
# shape below claims only the NOTATION (which the record's own `needle_kinds`
# already names `ipv6`), never a per-IPv6-rule reading the registry did not
# obtain. IP_ADDRESS's `length` field is empty and that is why: it is the one
# record of the eight whose length is not a fact.
#
# DISJOINT SHAPES, AND WHY THAT IS A REQUIREMENT RATHER THAN A PREFERENCE. Five
# of the eight are digit-only, so their shapes must not overlap: the restorer
# answers a value by SHAPE (`telecom_signatures`), and a spelling that satisfies
# two labels would offer one reading, lose the other, and hand the customer's
# tool a fake. The boundaries are therefore written out per label — an 18-digit
# run is Метрика, 8–12 is an operator account, 13–15 on MCC «250» is an IMSI —
# and each one is the registry's own sample family rather than an invented rule.
# The three exceptions the boundaries CANNOT separate (a 10-digit ЕСИА
# identifier and a 10-digit operator account are the same ten digits; a 16-digit
# app device id and a 16-digit Метрика id are the same sixteen) are recorded in
# NOT_IMPLEMENTED below and resolved by the FIELD KEY that typed them, which is
# the registry's own statement that these records are `hunt: by_shape`.

# Registry type id -> engine label. `IP_ADDRESS -> IP` is the registry's own
# `engine_labels`; `MAC -> MAC` is the same extension argument (the v5
# recognizer already emits MAC, and the label, the audit trail and `_PRIORITY`
# already speak it). The other six are the registry's type ids VERBATIM
# (`engine_labels == ()`): an alias would make two registry types
# indistinguishable in the v6 metric — a fake pass, which GOAL-BRIEF §N1
# forbids by name.
TELECOM_LABEL: dict[str, str] = {
    "IMSI": "IMSI",
    "MAC": "MAC",
    "IP_ADDRESS": "IP",
    "ESIA_OID": "ESIA_OID",
    "MOBILE_AD_ID": "MOBILE_AD_ID",
    "APP_DEVICE_ID": "APP_DEVICE_ID",
    "METRICA_CLIENT_ID": "METRICA_CLIENT_ID",
    "SUBSCRIBER_ACCOUNT": "SUBSCRIBER_ACCOUNT",
}

TELECOM_TYPES: tuple[str, ...] = tuple(TELECOM_LABEL)
TELECOM_LABELS: frozenset[str] = frozenset(TELECOM_LABEL.values())

# ENGINE LABEL -> REGISTRY TYPE ID. The vault stores and hands back the ENGINE
# label (`IP` for IP_ADDRESS), so `mint_telecom` must accept it and the restorer
# must compare it — the reverse mapping `LABEL_TO_TYPE` gives the checksum family,
# built here from `TELECOM_LABEL` so the two cannot drift.
LABEL_TO_TELECOM: dict[str, str] = {
    _engine_label: _type_id for _type_id, _engine_label in TELECOM_LABEL.items()}

# `grammar_status == "ГРАММАТИКА?"` in the registry — NONE, on all eight. The
# constant is written out anyway and asserted EMPTY by `test_pii_v6`, because
# each sibling family carries its unasserted types and a reader of this file
# must be able to SEE that this one has none rather than infer it from a missing
# name. If a future change makes one of them uncertain, it goes here and its
# shape shrinks to what the registry's own sample proves.
TELECOM_GRAMMAR_UNASSERTED: frozenset[str] = frozenset()

# The `pd_context` rules the registry states for this family, carried verbatim.
# THREE of the five say the same thing — «indirect; PD only when linked to a
# client record (OD-24)» — and ESIA_OID is the direct one; IMSI and
# SUBSCRIBER_ACCOUNT carry the empty string. THE RULES ARE RECORDED AND NOT
# IMPLEMENTED, for exactly the reason §finance records OSAGO's OD-22: nothing in
# this pipeline carries the LINK signal. An address, a GAID or a ClientID is
# personal data when the customer's own CRM links it to a person, and the
# gateway never sees that link. A recognizer cannot invent the discriminator; a
# fabricated one would be the evidence failure GOAL-BRIEF §7 forbids. What the
# engine CAN do — and does — is treat the value as protectable, because the
# traffic that carries it is the traffic where the link exists, and on this
# family a false negative is a leak while a false positive is one masked field.
# TYPES.md states that asymmetry rather than hiding it.
TELECOM_PD_CONTEXT: dict[str, str] = {
    "IP_ADDRESS": "indirect; PD only when linked to a client record (OD-24)",
    "MOBILE_AD_ID": "indirect; PD only when linked to a client record (OD-24)",
    "APP_DEVICE_ID": "indirect; PD only when linked to a client record (OD-24)",
    "METRICA_CLIENT_ID": "indirect; PD only when CRM links the ClientID to a lead (OD-24)",
    "ESIA_OID": "direct; an individual's account",
}

# The registry's own `needle_kinds` per record, copied so the derived set below
# is READ rather than asserted by hand.
TELECOM_NEEDLE_KINDS: dict[str, tuple[str, ...]] = {
    "IMSI": ("whole", "digits"),
    "MAC": ("whole", "squeezed"),
    "IP_ADDRESS": ("whole", "octets", "ipv6"),
    "ESIA_OID": ("whole", "digits"),
    "MOBILE_AD_ID": ("whole", "squeezed"),
    "APP_DEVICE_ID": ("whole", "digits", "squeezed"),
    "METRICA_CLIENT_ID": ("whole", "digits"),
    "SUBSCRIBER_ACCOUNT": ("whole", "digits"),
}

# `digits` in `needle_kinds` means a DIGIT-ONLY reading of the value is an
# identity (the registry states it per record). Read, not asserted: IMSI,
# ESIA_OID, METRICA_CLIENT_ID, SUBSCRIBER_ACCOUNT and APP_DEVICE_ID's numeric
# form. MAC, MOBILE_AD_ID and APP_DEVICE_ID's UUID form are NOT here — their
# identity includes hex letters, and a digit-only signature would let two
# devices that share a digit run answer for each other.
TELECOM_NUMERIC_TYPES: frozenset[str] = frozenset(
    type_id for type_id, kinds in TELECOM_NEEDLE_KINDS.items() if "digits" in kinds)

# The registry's own `value_notation` per record. "squeezed" drops the
# separators (a MAC's colons, a UUID's hyphens, an IMSI's spaces — all
# presentation, and every one of those records lists `separators` in its own
# `form_features`); "digits" is the digit-only reading; "ip_strict" is the
# address family, whose identity is its OCTETS and whose dotted/compressed
# notation belongs to whoever wrote it. APP_DEVICE_ID is the one record whose
# `needle_kinds` carry BOTH `digits` and `squeezed`: it has two forms, and
# `_telecom_content` decides the fake's form from the SOURCE's, not from this
# field — which is why the value here is "squeezed", the UUID half.
TELECOM_VALUE_NOTATION: dict[str, str] = {
    "IMSI": "digits",
    "MAC": "squeezed",
    "IP_ADDRESS": "ip_strict",
    "ESIA_OID": "digits",
    "MOBILE_AD_ID": "squeezed",
    "APP_DEVICE_ID": "squeezed",
    "METRICA_CLIENT_ID": "digits",
    "SUBSCRIBER_ACCOUNT": "digits",
}

# The registry's own `sample`, used as the fallback LAYOUT when the mint is
# handed something that is not the label's shape at all (a field key types the
# WHOLE value with no shape check, so that is reachable). The mint then answers
# with a well-shaped fake instead of echoing the source's own characters.
TELECOM_SAMPLE: dict[str, str] = {
    "IMSI": "250991234567890",
    "MAC": "00:1A:2B:3C:4D:5E",
    "IP_ADDRESS": "95.165.12.34",
    "ESIA_OID": "1000123456",
    "MOBILE_AD_ID": "6D92078A-8246-4BA4-AE5B-76104861E7DC",
    "APP_DEVICE_ID": "123456789012345678",
    "METRICA_CLIENT_ID": "250987654321098765",
    "SUBSCRIBER_ACCOUNT": "123456789012",
}

# ---------------------------------------------------------------- the shapes ---
#
# ONE SHAPE LANGUAGE, AND FOR THIS FAMILY IT IS MOSTLY *HEX*. Five facts decide
# every line below, and each is something the registry states about a record
# rather than a convenience:
#
#   * A NETWORK IDENTIFIER IS PRINTED IN MORE THAN ONE NOTATION, and the
#     customer's own form is the one that must survive: `00:1A:2B:3C:4D:5E`,
#     `00-1A-2B-3C-4D-5E`, `001A.2B3C.4D5E` (Cisco) and `001A2B3C4D5E` are ONE
#     device, so the shape accepts the separators and the SIGNATURE drops them.
#   * A HEX FIELD MAY BE TYPED IN CYRILLIC. `А`, `В`, `Е`, `С`, `М`, `Н`, `О`,
#     `Р`, `Т`, `У`, `Х` are the same glyphs as A, B, E, C, M, H, O, P, T, Y, X,
#     and a keyboard layout leaves them behind exactly as it leaves them in a VIN
#     series. The shape takes the Cyrillic twins and `telecom_signature` folds
#     them, because a hex field has no other reading — the one place in this
#     whole module where a glyph fold is provable rather than chosen.
#   * A RUN NEXT TO A DIGIT IS NOT THE VALUE. Every shape carries its own
#     lookaround: without it a 32-hex UUID would be read as a 12-hex MAC
#     standing in its prefix, and the restorer would replace twelve characters of
#     thirty-two — the failure `TOKEN_PATTERNS` documents for the checksum
#     family, and the one a fake-in-the-tool always is.
#   * AN OCTET IS 0–255, NOT `\d{1,3}`. The IPv4 class below is the octet
#     alternation the v5 recognizer already uses, so the two readings of an
#     address cannot disagree — and `999.1.1.1`, which is four groups of digits
#     and not an address, stays a version number.
#   * THE SHAPES ARE DISJOINT WHERE THE REGISTRY'S OWN SAMPLES ALLOW IT, because
#     `telecom_signatures` answers a value by shape and an ambiguous spelling
#     offers one reading and loses the other. The boundary per label is the
#     registry's sample family: 18 digits is Метрика's issuer sample, 8–12 is
#     the operator-account observation, 13–15 on MCC «250» is the IMSI sample.
#
# TWO SHAPES ARE DELIBERATELY NARROWER THAN THE REGISTRY'S PROSE, AND BOTH ARE
# NAMED BECAUSE THE DIFFERENCE IS A MEASURED RISK RATHER THAN AN OVERSIGHT:
#
#   * ESIA_OID. The registry's grammar is «\d+; длина не установлена». `\d+` is
#     not a recognizer — it is every digit run in the message — so the shape
#     takes the DIGIT FLOOR the registry's own sample establishes (10 digits,
#     sample «1000123456», and the fixture generator is `_digits(rng, 10)`) and
#     is bounded ABOVE at 15 so it cannot swallow a 20-digit account. The
#     genuine overlap with SUBSCRIBER_ACCOUNT's 8–12 is NOT hidden: it is
#     recorded in NOT_IMPLEMENTED and the account is asked first.
#   * SUBSCRIBER_ACCOUNT. The registry's own note is «типично 8–12 цифр (НЕ из
#     первоисточника)» — an OBSERVATION, not a standard — so the bound is that
#     observation and nothing wider. An operator account has no national format,
#     and a wider bound would claim order numbers behind «л/с».
# TWO SEPARATOR CLASSES, AND THE SPLIT IS THE REASON THE SHAPES STAY DISJOINT.
# A DIGIT-ONLY record may not be separated by a DOT or a COLON: an IPv4 address
# is exactly four digit groups joined by dots, and `123456789012` with dots is a
# version number — allowing `.`/`:` in an account run made «95.165.12.34» BOTH an
# address and an operator account, which is a fake-in-the-tool waiting to happen.
# The hex records DO take dots and colons: those are the notations MAC and a UUID
# are actually printed in (`001A.2B3C.4D5E`, `00:1A:…`).
_TC_SEP = r"[ \t\-/:№]{0,2}"
_TC_SEP_HEX = r"[ \t.\-/:№]{0,2}"
_TC_HEX = r"[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]"
# The same class as a NEGATIVE lookaround: one character that could be part of a
# hex run, in either alphabet.
_TC_HEX_B = r"[0-9A-Fa-fАВЕСКМНОРТУХ]"

# A UUID: 8-4-4-4-12, hyphenated, spaced or dotted, OR the 32-hex squeezed
# spelling an agent leaves when it strips the separators (the RESTORER must
# recognise its own substitute — `IDENTITY_TOKEN_PATTERNS` states the same rule
# for the certificate family). The GROUPED alternative stands first so the
# spelling that carries more evidence is the one a `fullmatch` answers with.
_TC_UUID_GROUPED = (r"(?<!" + _TC_HEX_B + r")"
                    + _TC_HEX + r"{8}" + _TC_SEP_HEX
                    + _TC_HEX + r"{4}" + _TC_SEP_HEX
                    + _TC_HEX + r"{4}" + _TC_SEP_HEX
                    + _TC_HEX + r"{4}" + _TC_SEP_HEX
                    + _TC_HEX + r"{12}(?!" + _TC_HEX_B + r")")
_TC_UUID_SQUEEZED = (r"(?<!" + _TC_HEX_B + r")"
                     + _TC_HEX + r"{32}(?!" + _TC_HEX_B + r")")
_TC_UUID = r"(?:" + _TC_UUID_GROUPED + r"|" + _TC_UUID_SQUEEZED + r")"

# MAC: EUI-48, six octets. The registry names three groupings — 2-2-2-2-2-2
# (with «:» or «-», which is what the v5 recognizer already reads), 4-4-4
# (Cisco, dotted) and solid — and all three are claimed; the SIGNATURE drops the
# separators so all three are one device.
# NOTE THE SEPARATORS: «:», «-», the Cisco «.» and nothing else. A
# SPACE-SEPARATED «00 1A 2B 3C 4D 5E» is how a person READS a MAC aloud, not a
# notation the registry prints, and admitting it made the shape match a spelling
# the notation mirror then reproduced — minting «58 30 C9 88 B4 2E», a token no
# recognizer can see and therefore a FAKE in the customer's tool. A key that types
# such a value now gets the canonical mint, which is matchable.
_TC_MAC_PAIRS = (r"(?<!" + _TC_HEX_B + r")"
                 # «:» AND «-» ARE BOTH THE REGISTRY'S NOTATIONS, and the class
                 # accepts EITHER at EACH separator rather than one separator
                 # carried by a backreference. A backreference is the stricter
                 # rule and is what this started as, but the family's patterns are
                 # EMBEDDED into larger alternations (`TELECOM_TOKEN_PATTERNS`,
                 # `_TELECOM_SHAPE_TEXT`), so a group number is not stable and
                 # `\1` referred to whichever group happened to precede it. A
                 # separator-class alternation costs the mixed spelling
                 # «00:1A-2B…», which no customer writes and which the SIGNATURE
                 # would fold to the same device as the consistent one anyway.
                 + r"(?:" + _TC_HEX + r"{2}(?:[:.\-]" + _TC_HEX + r"{2}){5}"
                 + r"|" + _TC_HEX + r"{4}[.\-]" + _TC_HEX + r"{4}[.\-]"
                 + _TC_HEX + r"{4})"
                 + r"(?!" + _TC_HEX_B + r")")
_TC_MAC_DOTTED = (r"(?<!" + _TC_HEX_B + r")"
                  + _TC_HEX + r"{4}\." + _TC_HEX + r"{4}\." + _TC_HEX + r"{4}"
                  + r"(?!" + _TC_HEX_B + r")")
# THE SOLID 12-HEX FORM IS DELIBERATELY NOT CLAIMED, and the registry itself is
# why: its grammar lists «голый 12-hex», and a bare 12-hex run is ALSO a 12-digit
# order number, an IMEI prefix and — worst of the three — a PREFIX of the 32-hex
# UUID that MOBILE_AD_ID's squeezed form already claims. The v5 recognizer never
# claimed it either; NOT_IMPLEMENTED records the cost.
_TC_MAC = r"(?:" + _TC_MAC_PAIRS + r"|" + _TC_MAC_DOTTED + r")"

# IPv4: four octets 0–255. The class is the octet alternation the v5 recognizer
# already uses, so the two readings of an address cannot disagree.
_TC_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_TC_IPV4_CORE = _TC_OCTET + r"(?:\." + _TC_OCTET + r"){3}"
_TC_IPV4 = r"(?<![\d.])" + _TC_IPV4_CORE + r"(?![\d.])"
# IPv6, the SYNTAX of RFC 5952's notation. The registry's own grammar line says
# the RFC was «не прочитан», so this claims the NOTATION (which the record's own
# `needle_kinds` already names `ipv6`) and asserts no IPv6 semantics — see
# NOT_IMPLEMENTED. THE ALTERNATIVES ARE ORDERED SO AN INVALID ADDRESS IS NOT AN
# ADDRESS: the IPv4-mapped/embedded families come first, so their dotted tail is
# read as four OCTETS and not as four hex groups («::ffff:999.1.1.1» must be
# refused); then the full eight-group form; then the compressed «::» form; then
# the trailing-«::» form. A single group («abc») is not an address at all.
_TC_H16 = r"[0-9A-Fa-f]{1,4}"
_TC_IPV6 = (r"(?<![0-9A-Fa-f:.])" + r"(?:"
            + r"(?:" + _TC_H16 + r":){1,6}:" + _TC_IPV4_CORE
            + r"|(?:" + _TC_H16 + r":){6}" + _TC_IPV4_CORE
            + r"|::(?:[0-9A-Fa-f]{1,4}:){0,5}" + _TC_IPV4_CORE
            + r"|" + _TC_H16 + r"(?::" + _TC_H16 + r"){7}"
            + r"|(?:" + _TC_H16 + r"(?::" + _TC_H16 + r"){0,6})?"
            + r"::(?:" + _TC_H16 + r"(?::" + _TC_H16 + r"){0,6})?"
            + r"|(?:" + _TC_H16 + r":){1,7}:"
            + r")" + r"(?![0-9A-Fa-f:.])")

# The digit-only shapes. ONE bounded digit-run language serves all five of them,
# and WHAT SEPARATES THEM IS THE DIGIT COUNT — which is the registry's own
# statement about each record («le», «типично 8–12», «образец эмитента — 18 цифр»)
# and not an invented rule. The run is bounded to SIX groups and to fifteen
# digits so it cannot swallow a twenty-digit account or a sentence of numbers;
# `_TELECOM_DIGIT_COUNTS` then says which readings a given digit count permits,
# and a spelling that permits more than one is resolved by asking the vault for
# ALL of them («recorded label is one the spelling permits») rather than by
# guessing — see `telecom_signatures`. A DOT AND A COLON ARE NOT SEPARATORS
# HERE: a digit-only record printed with dots is an IPv4 address or a version
# number, and claiming it as an operator account is a fake-in-the-tool waiting
# to happen.
_TC_DIGIT_RUN = (r"(?<!\d)\d{1,6}(?:" + _TC_SEP + r"\d{1,6}){0,5}(?!\d)")

# label -> the digit counts the record's own facts allow.
#   IMSI            ≤15 digits, MCC 3 + MNC 2–3 + MSIN → 13–15 on «250»
#   SUBSCRIBER_     the registry's own «типично 8–12 цифр» observation
#   ESIA_OID        «длина не установлена»: the sample floor (10) up to the
#                   fifteen a digit run may reach
#   METRICA         «образец эмитента — 18 цифр»
#   APP_DEVICE_ID   the numeric «пример — 18 цифр», and the same run
_TELECOM_DIGIT_COUNTS: dict[str, frozenset[int]] = {
    "SUBSCRIBER_ACCOUNT": frozenset(range(8, 13)),
    "IMSI": frozenset((13, 14, 15)),
    "ESIA_OID": frozenset(range(10, 16)),
    "METRICA_CLIENT_ID": frozenset((18,)),
    "APP_DEVICE_ID": frozenset(range(15, 19)),
}
_TC_IMSI_PREFIX = "250"

# The same table under the name the tests and TYPES.md read it by: the bounds are
# the registry's own facts about the five digit-only records, so they are PUBLIC
# to this family the way `FINANCE_NEEDLE_KINDS` is.
TELECOM_DIGIT_COUNTS: dict[str, frozenset[int]] = _TELECOM_DIGIT_COUNTS

# The registry's own widest form per record. THE ORDER IS LOAD-BEARING: it is the
# answer order of `telecom_signatures` and `telecom_label_of_shape`, and the
# record whose spelling is the more specific one must be asked first — the
# account before the ЕСИА identifier, the 18-digit issuer sample before the app
# form's other lengths. Every entry is bounded so no two readings of ONE
# spelling disagree about which label it is (see `_telecom_disjoint` in
# test_pii_v6, which measures the property over the shapes themselves).
_TELECOM_SHAPE_TEXT: dict[str, str] = {
    "MAC": _TC_MAC,
    "IP_ADDRESS": r"(?:" + _TC_IPV4 + r"|" + _TC_IPV6 + r")",
    "MOBILE_AD_ID": _TC_UUID,
    "APP_DEVICE_ID": r"(?:" + _TC_UUID + r"|" + _TC_DIGIT_RUN + r")",
    "METRICA_CLIENT_ID": _TC_DIGIT_RUN,
    "SUBSCRIBER_ACCOUNT": _TC_DIGIT_RUN,
    "ESIA_OID": _TC_DIGIT_RUN,
    "IMSI": _TC_DIGIT_RUN,
}

TELECOM_SHAPES: dict[str, "re.Pattern[str]"] = {
    label: re.compile(rf"(?i:{shape})") for label, shape in _TELECOM_SHAPE_TEXT.items()
}

# The Cyrillic capitals that are the same GLYPH as a Latin hex letter, mapped to
# the Latin twin so `АВЕ` and `ABE` are one device. APPLIED ONLY WHERE THE
# RECORD'S OWN GRAMMAR IS A HEX FIELD (MAC and the two UUID forms): «СО» and
# «SO» are not one series in any other family, which is why §identity keeps its
# alphabet and folds only the ПТС series, whose registry `value_notation` names
# `glyph_fold`.
_TELECOM_GLYPH_FOLD = str.maketrans("АВЕСКМНОРТУХ", "ABECKMHOPTYX")
_TELECOM_GLYPH_FOLD_TYPES: frozenset[str] = frozenset(
    ("MAC", "MOBILE_AD_ID", "APP_DEVICE_ID"))


# THE ENGINE LABEL THIS FAMILY MINTS A FULLY-FORMED VALUE FOR. Five of the
# eight are minted as a run of the source's own length, so the notation is the
# SEPARATORS and `render_like_atomic` is the whole rule. Three are not:
#
#   * IP_ADDRESS — the fake is a complete RFC 2544 address, minted valid with its
#     own dots; splicing it character-by-character into a source of a different
#     digit count produced `19.819.70.83`, which is not an address and matches no
#     token shape. The mint's own layout is the answer, and IPv6 is the exception
#     INSIDE the exception: an IPv6 fake carries one hex character per
#     alphanumeric slot of the source, so its colons ARE a splice.
#   * MAC and MOBILE_AD_ID — a bare 12- or 32-hex run, minted without separators
#     by construction, so the source's layout must be laid onto it.
_TELECOM_SELF_LAID: frozenset[str] = frozenset(("IP_ADDRESS",))


def telecom_own_layout(label: str, source: str) -> bool:
    """Whether `mint_telecom` answers with a COMPLETE value rather than a run.

    True means the fake carries its own notation and must NOT be mirrored onto the
    source's separators a second time; False means the fake is a run of the
    source's own length and IS mirrored. The IPv6 case is decided by the source:
    an IPv6 fake is one hex character per alphanumeric slot, so it is laid like a
    MAC, while an IPv4 fake is a whole address."""
    type_id = LABEL_TO_TELECOM.get(label, label)
    if type_id not in _TELECOM_SELF_LAID:
        return False
    stripped = source.strip()
    if _TC_IPV6_MAPPED.match(stripped):
        # the mapped form is a complete address too (prefix + reserved tail)
        return True
    return not bool(_TC_IPV6_SHAPE.fullmatch(stripped))


def telecom_shape(label: str) -> "re.Pattern[str] | None":
    """The compiled shape for an ENGINE label or a registry type id.

    `mint_telecom` and the token-shape guard are handed the ENGINE label the vault
    stores (`IP` for IP_ADDRESS), while `TELECOM_SHAPES` is keyed by the registry
    type id — so this is the one place the translation happens and the one place a
    caller can ask "is this value a shape this family claims?". A field key types
    the WHOLE value with no shape check, so the answer is what decides whether the
    source's separators may be mirrored onto the substitute or must be left
    alone."""
    return TELECOM_SHAPES.get(LABEL_TO_TELECOM.get(label, label))


def telecom_signature(value: str, label: str = "") -> str:
    """The CONTENT identity of a telecom / device identifier.

    SEPARATORS ARE PRESENTATION, THE CONTENT IS THE VALUE — the registry says so
    per record (`value_notation` "squeezed", whose own `form_features` list
    `separators`). So `00:1A:2B:3C:4D:5E`, `00-1A-2B-3C-4D-5E`,
    `001A.2B3C.4D5E` and `001A2B3C4D5E` are ONE MAC;
    `6D92078A-8246-4BA4-AE5B-76104861E7DC` and its squeezed 32-hex spelling are
    ONE GAID; `250 99 1234567890` and `250991234567890` are ONE IMSI.

    THE LABEL IS NOT PART OF THE KEY, AND THAT IS THE DIFFERENCE FROM THE THREE
    PRECEDING FAMILIES. There, one spelling could be two registry types (a ПТС
    and a СТС, a ДМС policy and a КАСКО policy) and the label had to be in the
    key or two documents would answer for each other. Here the shapes are
    DISJOINT BY CONSTRUCTION (see `_TELECOM_SHAPE_TEXT`), so a value has exactly
    one reading and a label in the key would add nothing but a way for the two
    readings to disagree. `test_pii_v6` measures the disjointness rather than
    trusting this comment.

    The `label` argument is accepted so the call site reads like every other
    family's and is used for ONE thing only: the glyph fold, which is applied
    where the record's own grammar is a hex field. Passing no label folds
    nothing, which is what a caller asking about an unknown spelling wants."""
    squeezed = _IDENTITY_SEPARATORS.sub("", value).upper()
    if not squeezed:
        return ""
    if label in _TELECOM_GLYPH_FOLD_TYPES:
        squeezed = squeezed.translate(_TELECOM_GLYPH_FOLD)
    return squeezed


def telecom_signatures(value: str) -> list[tuple[str, str]]:
    """Every (label, signature) this spelling could be — the restorer's question.

    MORE THAN ONE READING IS NORMAL HERE, and it is the family's own structure
    rather than an accident. The six records share five shapes:

      * a digit run is 8–12 (SUBSCRIBER_ACCOUNT), or a 10–15 ЕСИА identifier, or
        the two together — the digit bounds of the first four are a PARTITION and
        the fifth (ESIA_OID, «длина не установлена») is the catch-all;
      * an 18-digit run is Метрика's issuer sample OR an app device id, because
        both emit eighteen digits;
      * a 32-hex run is a GAID/IDFA OR an app device id in its UUID form — the
        same spelling, and the FIELD KEY is the only thing that tells them apart.

    So the answer is every label whose SHAPE the spelling satisfies (a label with
    a digit-count bound is filtered by it, a label with none is asked of every
    spelling its pattern matches), each with its own signature. The caller asks
    every signature as its own indexed point query and keeps a hit only when the
    vault's recorded label is among the readings — so a wrong reading costs one
    query, an ambiguous spelling still resolves, and no reading can restore
    another type's value. Mirrors `legal_signatures`/`finance_signatures`.

    THE DIGIT-BOUNDED READINGS COME FIRST, because they carry more information: the
    first entry is what `telecom_label_of_shape` answers with."""
    surface = value.strip()
    if not surface:
        return []
    digits = _digits(surface)
    answers: list[tuple[str, str]] = []
    for label, pattern in TELECOM_SHAPES.items():
        if not pattern.fullmatch(surface):
            continue
        allowed = _TELECOM_DIGIT_COUNTS.get(label)
        if allowed is not None and not _TC_UUID_GROUPED_PATTERN.fullmatch(surface) \
                and not v6_uuid_squeezed(surface):
            # THE DIGIT BOUNDS GOVERN THE DIGIT FORM ONLY. APP_DEVICE_ID has TWO
            # forms (a UUID and an 18-digit run) and records one bound; asked about
            # a UUID its digit count is meaningless, and applying the bound would
            # make the family blind to half of its own record.
            if len(digits) not in allowed:
                continue
            # IMSI is the one bounded label with a CONTENT prefix, and the prefix
            # is the registry's own («MCC РФ "250"»): a run of fifteen digits that
            # is not on 250 is a legal-entity ОГРНИП, not an IMSI.
            if label == "IMSI" and not digits.startswith(_TC_IMSI_PREFIX):
                continue
        answers.append((label, telecom_signature(surface, label)))
    answers.sort(key=lambda pair: _TELECOM_DIGIT_COUNTS.get(pair[0]) is None)
    return answers


def telecom_label_of_shape(value: str) -> str:
    """The FIRST label this spelling could be, for callers that need one name."""
    answers = telecom_signatures(value)
    return answers[0][0] if answers else ""


# The two readings `_telecom_content` asks before it draws: is the source a
# GROUPED UUID, and is it an IPv6 address? Both are `fullmatch` questions on the
# same patterns the recognizer uses, so the mint and the recognition cannot
# disagree about what a source is.
_TC_UUID_GROUPED_PATTERN = re.compile(rf"(?i:{_TC_UUID_GROUPED})")
_TC_UUID_SQUEEZED_PATTERN = re.compile(rf"(?i:{_TC_UUID_SQUEEZED})")
_TC_IPV6_SHAPE = re.compile(rf"(?i:{_TC_IPV6})")


def _rand_hex(count: int) -> str:
    return "".join(secrets.choice("0123456789abcdef") for _ in range(count))


def _alnum_count(value: str) -> int:
    return sum(1 for char in value if char.isalnum())


def v6_uuid_squeezed(value: str) -> bool:
    """Whether `value` is the 32-hex squeezed spelling of a UUID."""
    return bool(_TC_UUID_SQUEEZED_PATTERN.fullmatch(value.strip()))


# The IPv4-mapped / embedded IPv6 tail: a hex prefix up to the LAST colon that is
# followed by a dotted quad. This is the ONE IPv6 family whose fake cannot be a
# character-by-character splice, because its dotted tail must stay a real IPv4
# address — laid as hex it becomes `::4ced:ccc.b7a.0.0`, which is not an address
# and matches no token shape.
_TC_IPV6_MAPPED = re.compile(
    r"^(?P<prefix>.*:)(?P<v4>(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})$")


def _reserved_ipv4() -> str:
    """A fresh address from RFC 2544 (198.18.0.0/15): reserved, never on the
    public internet, so a token can never address a real host."""
    return (f"198.{secrets.choice((18, 19))}.{secrets.randbelow(256)}."
            f"{secrets.randbelow(254) + 1}")


def _documents(value: str) -> int:
    """How many ALPHANUMERIC characters a value carries (its identity length)."""
    return sum(1 for char in value if char.isalnum())


def _laid(content: str, surface: str) -> str:
    """`content` into the SEPARATOR LAYOUT and letter case of `surface`.

    The whole family's presentation rule, written once here instead of calling
    `render_like_atomic` from inside `_telecom_content`: an IPv6 or IPv4 fake is
    built as a VALID address and must be laid into the source's own colons or
    dots, while a MAC or a UUID fake is a bare run of hex characters that may be
    laid the same way."""
    return render_like_atomic(content, surface)


def _telecom_content(label: str, surface: str) -> str:
    """The fake's CONTENT in the source's own character classes and notation.

    ONE RULE, THREE FACTS, and each fact is why the alternative was rejected:

      * THE SOURCE'S FORM DECIDES THE FAKE'S FORM. APP_DEVICE_ID has two forms in
        the registry («цифры (appmetrica_device_id …) или UUID (IFV)»), so a UUID
        source must mint a UUID and a digit source must mint digits — the other
        would hand the customer's validator a shape its own field does not
        accept. `_TC_UUID_GROUPED_PATTERN` decides which the source is.
      * THE CHARACTER CLASS IS THE LABEL'S, NOT A GUESS. A MAC's fake is hex; a
        Метрика ClientID's fake is DECIMAL; an IMSI's is decimal on MCC «250», so
        the substitute is still an IMSI by its own grammar.
      * AN ADDRESS IS DRAWN FROM A RESERVED POOL. IPv4 comes from RFC 2544
        (198.18.0.0/15) — the same range the v5 renderer already uses: reserved,
        never on the public internet, so a token can never address a real host.
        An IPv6 fake keeps the source's GROUP COUNT, because the source's colons
        are the notation and `render_like_atomic` lays the fake into them.

    The case is inherited character by character by `render_like_atomic`, so a
    source written in Cyrillic twins keeps its script — the substitute must
    satisfy the same field the source did."""
    if label == "MAC":
        return _rand_hex(12)
    if label == "MOBILE_AD_ID":
        return _rand_hex(32)
    if label == "APP_DEVICE_ID":
        if _TC_UUID_GROUPED_PATTERN.fullmatch(surface.strip()):
            return _rand_hex(32)
        digits = len(_digits(surface))
        return _rand_digits(digits if digits else 18)
    if label == "IP_ADDRESS":
        mapped = _TC_IPV6_MAPPED.match(surface.strip())
        if mapped:
            # THE MAPPED FORM KEEPS ITS MAPPED PREFIX AND GETS A REAL IPv4 TAIL.
            # The prefix is notation (it says WHICH IPv4 mapping this is) and a
            # splice would turn the tail into hex; the tail is the address, so it
            # comes from the reserved pool. The prefix's own hex groups are left
            # as they are — they are the notation, not the address.
            return mapped.group("prefix") + _reserved_ipv4()
        if _TC_IPV6_SHAPE.fullmatch(surface.strip()):
            # One hex character per alphanumeric slot of the source: the group
            # count, the compression and the separators are the writer's, and the
            # content is ours.
            return _rand_hex(_alnum_count(surface))
        # RFC 2544 (198.18.0.0/15) for IPv4. The SECOND octet is the whole
        # reservation — 18 OR 19, never both and never anything else — and the
        # rest is free, which is why the v5 renderer wrote exactly this shape.
        return _reserved_ipv4()
    if label == "IMSI":
        # MCC «250» is the registry's own grammar for this record and the only
        # part of an IMSI that is not free: a fake that moved it would name
        # another country's subscriber. The rest is a 10–12 digit MSIN, so the
        # substitute is 13–15 digits whatever length the source was — an IMSI is
        # not required to keep the MSIN length its issuer happened to use, and
        # `render_like_atomic` would refuse a splice of a different length
        # anyway, which is why the content is drawn to fit the source's own
        # digit count when that count is one an IMSI may have.
        length = len(_digits(surface))
        if length not in _TELECOM_DIGIT_COUNTS["IMSI"]:
            length = 15
        return _TC_IMSI_PREFIX + _rand_digits(length - len(_TC_IMSI_PREFIX))
    # SUBSCRIBER_ACCOUNT and ESIA_OID: a digit run of the SOURCE's own length,
    # because the length is the record's own bound (8–12 and the sample's floor)
    # and a fake of another length is a value the customer's validator refuses.
    digits = len(_digits(surface))
    return _rand_digits(digits if digits else 12)


def mint_telecom(label: str, original: str) -> str:
    """A format-preserving fake for a telecom / device identifier. No checksum.

    THE SHAPE IS THE CUSTOMER'S, THE CONTENT IS OURS. `render_like_atomic` lays
    the fake into the source's separators and letter case, and `_telecom_content`
    keeps its character classes and its form (grouped UUID vs squeezed, digits vs
    hex, compressed IPv6 vs full), so the substitute satisfies every form check
    the real value does and names no device, no subscriber and no account. There
    is no checksum to inherit (the registry gives none) and therefore no validity
    to preserve: what is preserved is FORMAT.

    TWO FALLBACKS, BOTH FAIL-CLOSED, both reachable only through a field key, which
    types the WHOLE value with no shape check: a source that is not the label's
    shape is minted from the registry's own SAMPLE layout rather than echoed back
    (an echo would send the source's own characters to the model under a
    substitute's name), and the re-draw loop keeps the fake from ever equalling
    the source. The mint is TOTAL — a renderer that raises is a 5xx on the masking
    path, the one failure this product does not accept."""
    label = LABEL_TO_TELECOM.get(label, label)
    surface = original.strip()
    pattern = TELECOM_SHAPES.get(label)
    if not surface or pattern is None or not pattern.fullmatch(surface):
        surface = TELECOM_SAMPLE.get(label, "")
    if not surface:
        return ""
    return _mint_like(label, surface)


def _mint_like(label: str, surface: str) -> str:
    """Draw a fake for `surface` and lay it into the surface's own notation.

    An IPv4 ADDRESS IS THE ONE PLACE THE LAYOUT IS NOT A SPLICE. Everywhere else
    the fake carries exactly as many alphanumeric characters as the source, so
    `render_like_atomic` is exact; but an IPv4 fake is minted from the reserved
    RFC 2544 range, whose own octets have their own lengths, and a character-by-
    character splice across a different total length produced `19.819.87.98` — a
    string that is not an address at all and that no token shape matches, i.e. a
    fake the restorer can never find. So the digits of the reserved address are
    laid into the source's SEPARATOR positions and the source's own octet SHAPE is
    what decides the answer: when the source's octets are one to three digits —
    every dotted form a person writes — the address is rendered with its own
    dots; otherwise the source is already outside the shape and the shape check
    above sent us to the registry's SAMPLE.

    THE RE-DRAW LOOP keeps the fake from ever equalling the source, however
    improbable the draw, and it terminates because the candidate space of a
    reserved range is far larger than eight."""
    self_laid = telecom_own_layout(label, surface)
    for _ in range(8):
        content = _telecom_content(label, surface)
        fake = content if self_laid else render_like_atomic(content, surface)
        # FAIL CLOSED ON THE MIRROR. A field key types the WHOLE value with no
        # shape check, so a source can arrive in separators no telecom shape
        # admits («00 1A 2B 3C 4D 5E»). Mirroring THOSE onto the fake mints a
        # spelling outside every shape the restorer scans, and a substitute that
        # is not a candidate is a FAKE in the customer's tool with a 200 — the one
        # failure this module's token-shape invariant exists to prevent. The
        # fallback is the CANONICAL reading of the same source: the SAMPLE's
        # layout, which the family's own tuple is built to match.
        if fake != surface and TELECOM_TOKEN_RE.fullmatch(fake):
            return fake
        if not self_laid:
            canonical = TELECOM_SAMPLE.get(LABEL_TO_TELECOM.get(label, label), "")
            if canonical and canonical != surface:
                fallback = render_like_atomic(
                    _telecom_content(label, canonical), canonical)
                if TELECOM_TOKEN_RE.fullmatch(fallback):
                    return fallback
        if fake != surface and self_laid and telecom_shape(label) is not None:
            return fake
    return fake


# ------------------------------------------------------------ raw-text entry ---
#
# WHY THIS EXISTS AT ALL. `Detector.detect` runs every recognizer on the text
# AFTER `normalize()`, whose digit-look-alike fold is applied to any run of
# digits, look-alike glyphs and phone separators holding five or more REAL digits.
# A UUID is exactly such a run — `6D92078A-8246-4BA4-AE5B-76104861E7DC` holds ten
# digits — so its `B` is folded to `8` INSIDE the value: the masked substitute
# stands over `…AE58…`, and the customer's real `…AE5B…` can never come back from
# the string the model was shown. The vault still holds the real value, so the
# FILE is right and the ROUND TRIP is wrong, which is the worse of the two.
#
# `detect_vehicle_ids` (MAC, VIN) and `detect_plates` are run on the RAW text for
# the same reason and with the same justification: a value whose identity is HEX
# must not be read through a fold designed for digits, and the engine's own
# invariant makes it safe — `normalize()` is 1:1, so offsets taken on the raw
# string index identically into every layer downstream.
#
# THE CUES ARE THE LEASED ONES. `licensing/assets_source.CTX_TYPES` is the source
# of truth for WHICH words type this family and `pseudex/assets.py` builds the
# compiled patterns from it; this function re-uses those compiled patterns rather
# than restating a single cue word, so the two paths cannot drift. It is therefore
# inert without a bundle — `BundleNotLeased` is the engine's own answer, exactly
# as it is for every other recognizer.
def detect_telecom(raw_text: str) -> list[Span]:
    """The family's cue path, on the RAW text (see the note above)."""
    try:
        from pseudex.assets import ASSETS
        if not ASSETS.is_loaded:
            return []
        patterns = ASSETS.get().ru_pii.ctx_patterns
    except Exception:                                                # noqa: BLE001
        return []
    spans: list[Span] = []
    for entity_type, pattern in patterns:
        if entity_type not in TELECOM_LABELS:
            continue
        for match in pattern.finditer(raw_text):
            value = match.group(1)
            spans.append(Span(match.start(1), match.end(1), entity_type, value))
    return spans


# Every shape `mint_telecom` can be shown in. `unmask_text` finds candidates by
# SHAPE, so a token shape that escapes this tuple stops being reversible and a
# FAKE reaches the customer's tool — the invariant `TOKEN_PATTERNS` states, and
# the reason this tuple is built from the SAME `_TELECOM_SHAPE_TEXT` the
# recognizer uses rather than restated by hand.
#
# THE ORDER IS LOAD-BEARING IN TWO PLACES. The GROUPED UUID stands before the
# squeezed 32-hex form (a 32-hex token the agent stripped must still be seen, and
# the grouped spelling carries more evidence when both could match), and the MAC
# stands before the squeezed UUID because a 12-hex MAC is a PREFIX of a 32-hex
# UUID and the alternation would otherwise swallow twelve characters of one. The
# bare digit runs stand LAST: they are the family's least specific shapes.
_TC_TOKEN_START = r"(?<![0-9A-Za-zА-Яа-яЁё])"
_TC_TOKEN_END = r"(?![0-9A-Za-zА-Яа-яЁё])"

TELECOM_TOKEN_PATTERNS: tuple[str, ...] = (
    _TC_UUID_GROUPED,      # GAID / IFV / GAID-shaped app id, grouped
    _TC_MAC_PAIRS,         # MAC, 2-2-2-2-2-2
    _TC_MAC_DOTTED,        # MAC, Cisco 4-4-4
    _TC_UUID_SQUEEZED,     # the same UUID with its separators stripped
    _TC_IPV6,              # IPv6, colon notation (incl. the IPv4-mapped tail)
    _TC_IPV4,              # IPv4
    _TC_DIGIT_RUN,         # the five digit-only records, bounded
)

# THE FAMILY'S OWN ALTERNATION, COMPILED ONCE — the same second line of defence
# `LEGAL_TOKEN_RE` and `FINANCE_TOKEN_RE` are. `vault._token_re` is a
# non-overlapping leftmost-first scan, so a token another family's shape matches
# AROUND is skipped in full; asking this alternation separately means the
# family's reversibility never depends on who else matched nearby. A dead
# candidate costs one indexed point query and is never spliced.
TELECOM_TOKEN_RE = re.compile("|".join(
    _TC_TOKEN_START + pattern + _TC_TOKEN_END
    for pattern in TELECOM_TOKEN_PATTERNS))


# ================================== utility / account / education / travel ===
#
# THE SIXTH FAMILY: the twelve utility / account / education / travel records of
# the v6 registry — GIS_ZHKH_ELS, UTILITY_ACCOUNT, CDP_CUSTOMER_ID, LOGIN,
# DIPLOMA_NUMBER, SCHOOL_CERT_NUMBER, STUDENT_ID_NUMBER, ACCESS_PASS_NUMBER,
# EMPLOYEE_TAB_NUMBER, EMPLOYMENT_CONTRACT_NUMBER, PNR, E_TICKET_NUMBER. NONE
# carries a checksum (`generated_checksum == ""` on all twelve), so — exactly as
# in §identity, §legal, §finance and §telecom — the mechanism is GRAMMAR +
# TYPED CONTEXT and NOTHING ELSE. `mint_utility` never invents a check digit,
# never validates one and never re-mints until something fails.
#
# WHAT THIS FAMILY ADDS TO THE FIVE BEFORE IT, AND EACH FACT IS A DECISION:
#
#   1. THREE RECORDS ARE `ГРАММАТИКА?` — STUDENT_ID_NUMBER («форма студбилета не
#      получена»), PNR (GDS locators, «локаторы "Сирены" могут использовать
#      кириллицу») and E_TICKET_NUMBER («ж/д — нумерация РЖД не установлена»).
#      Their shapes are the registry's OWN samples and grammar notes and nothing
#      wider, and the constant that says so is `UTILITY_GRAMMAR_UNASSERTED`. No
#      permissive regex was invented for them.
#   2. TWO RECORDS CARRY A `pd_context` (GIS_ZHKH_ELS and UTILITY_ACCOUNT:
#      «indirect; premises payer account»). Both are RECORDED and NOT implemented,
#      for the reason the telecom family states: nothing in this pipeline carries
#      an owner/premises signal, and a fabricated discriminator is the
#      fabricated-evidence failure GOAL-BRIEF §7 forbids.
#   3. NINE OF THE TWELVE CARRY LETTERS as part of their identity (a ЕЛС's series,
#      a ПНР's locator, a CDP code or UUID, an RFID UID, a login, a contract
#      number), so their identity key is the CONTENT with the letters in it and
#      their notation is mirrored whole — the rule §identity, §legal and §telecom
#      already state. The FIVE whose grammar admits no letter (a diploma's 13
#      digits, an attestat's 14, an air ticket's 13, a tab number, a student id)
#      keep the digit signature every v5 identifier has.
#   4. ONE CUE COLLIDES WITH AN EARLIER FAMILY, AND THE COLLISION IS RECORDED
#      RATHER THAN WON. The registry gives BOTH `SUBSCRIBER_ACCOUNT` (telecom,
#      family 5) and `UTILITY_ACCOUNT` (this family) the cues «лицевой счёт»,
#      «л/с», «ЛС» and the same 6–12 digit space — two records that are one thing
#      in a ЖКХ ledger and another in a telecom billing system. `_resolve` breaks
#      the tie by (priority, length) and, at equality, by the order the spans were
#      appended: the telecom entry stands earlier in the leased `CTX_TYPES`, so
#      the shared cues answer `SUBSCRIBER_ACCOUNT`. This family therefore reaches
#      `UTILITY_ACCOUNT` through its OWN keys (`abonent_id`, `лицевой_счет`) and
#      through the LETTER-BEARING form the telecom shape cannot read
#      («л/с 12-34АБ»), and `test_utility_shared_cue_arbitration_is_recorded`
#      pins the arbitration so it cannot be mistaken for an accident. Making this
#      family win instead is a PRIORITY decision for the Lead's table, not a
#      silent edit here.
#   5. THE RAW-TEXT QUESTION IS SHARED WITH THE TELECOM FAMILY, and the module
#      BINDING `ru_pii.detect_structured` resolves is widened at the bottom of
#      this section rather than in that file, which is outside this family's write
#      scope. A ЕЛС series is Cyrillic («60АА000593-01»), and `normalize()` folds
#      digit look-alikes — «60ВВ000593-01» becomes «6088000593-01» INSIDE the
#      value. The shape below requires LETTERS in the series slots precisely so
#      the folded spelling cannot match on the normalized path, and the raw path
#      is then the only reading of it, which is what makes the round trip exact.

# Registry type id -> engine label. Identity on purpose: `engine_labels == ()` for
# all twelve, so the label a conversation already had cannot move and the v6
# metric can separate the types. An alias would make two registry types
# indistinguishable — the fake pass GOAL-BRIEF §N1 forbids by name.
UTILITY_LABEL: dict[str, str] = {
    "GIS_ZHKH_ELS": "GIS_ZHKH_ELS",
    "UTILITY_ACCOUNT": "UTILITY_ACCOUNT",
    "CDP_CUSTOMER_ID": "CDP_CUSTOMER_ID",
    "LOGIN": "LOGIN",
    "DIPLOMA_NUMBER": "DIPLOMA_NUMBER",
    "SCHOOL_CERT_NUMBER": "SCHOOL_CERT_NUMBER",
    "STUDENT_ID_NUMBER": "STUDENT_ID_NUMBER",
    "ACCESS_PASS_NUMBER": "ACCESS_PASS_NUMBER",
    "EMPLOYEE_TAB_NUMBER": "EMPLOYEE_TAB_NUMBER",
    "EMPLOYMENT_CONTRACT_NUMBER": "EMPLOYMENT_CONTRACT_NUMBER",
    "PNR": "PNR",
    "E_TICKET_NUMBER": "E_TICKET_NUMBER",
}

UTILITY_TYPES: tuple[str, ...] = tuple(UTILITY_LABEL)
UTILITY_LABELS: frozenset[str] = frozenset(UTILITY_LABEL.values())
LABEL_TO_UTILITY: dict[str, str] = {engine: type_id
                                   for type_id, engine in UTILITY_LABEL.items()}

# `grammar_status == "ГРАММАТИКА?"` in the registry, read per record rather than
# inferred from a missing name. STUDENT_ID_NUMBER: the form of a student card was
# not obtained, so the shape is the registry's own «NN-NNNN» sample family. PNR:
# five or six alphanumerics per GDS, and «локаторы "Сирены" могут использовать
# кириллицу» — a second script the registry does not pin down. E_TICKET_NUMBER:
# the AIR form is `3 + 10` digits, the RAIL form is «нумерация РЖД не
# установлена», so only the air form is claimed.
UTILITY_GRAMMAR_UNASSERTED: frozenset[str] = frozenset(
    ("STUDENT_ID_NUMBER", "PNR", "E_TICKET_NUMBER"))

# The two records whose `pd_context` is set. RECORDED, NOT IMPLEMENTED — the same
# rule and the same reason as FINANCE_PD_CONTEXT and TELECOM_PD_CONTEXT: the
# discriminator is who owns the premises, which the gateway never sees.
UTILITY_PD_CONTEXT: dict[str, str] = {
    "GIS_ZHKH_ELS": "indirect; premises payer account",
    "UTILITY_ACCOUNT": "indirect; premises payer account",
}

# The registry's own `needle_kinds` per record, copied so the derived sets below
# are READ rather than asserted by hand.
UTILITY_NEEDLE_KINDS: dict[str, tuple[str, ...]] = {
    "GIS_ZHKH_ELS": ("whole", "glyph", "digits"),
    "UTILITY_ACCOUNT": ("whole", "digits"),
    "CDP_CUSTOMER_ID": ("whole", "squeezed", "digits"),
    "LOGIN": ("whole",),
    "DIPLOMA_NUMBER": ("whole", "digits"),
    "SCHOOL_CERT_NUMBER": ("whole", "digits"),
    "STUDENT_ID_NUMBER": ("whole", "squeezed"),
    "ACCESS_PASS_NUMBER": ("whole", "squeezed", "digits"),
    "EMPLOYEE_TAB_NUMBER": ("whole", "digits"),
    "EMPLOYMENT_CONTRACT_NUMBER": ("whole", "squeezed", "glyph"),
    "PNR": ("whole", "glyph"),
    "E_TICKET_NUMBER": ("whole", "digits"),
}

# HOW A VALUE'S IDENTITY IS WRITTEN, per record, and why the two styles that the
# registry does not spell out are what they are:
#
#   * `digits` — the registry's own `value_notation` for five of the twelve, and
#     the plain digit key every v5 identifier has. The five grammars admit NO
#     letter (checked against `_UTILITY_SHAPE_TEXT` below by
#     `test_utility_registry_facts_are_recorded`), which is why the label is not
#     part of the key: two digit-only values with equal digits ARE equal values
#     modulo the separators the canonical drops, so the digit-signature index the
#     whole engine relies on keeps working untouched.
#   * `squeezed` — separators are presentation, the characters are the identity.
#     The registry's `value_notation` for GIS/CDP/STUDENT_ID/ACCESS_PASS, and for
#     UTILITY_ACCOUNT the same reading (`digits`) is used for the digit form while
#     the LETTER-bearing form keeps its letters — one function, two inputs.
#   * `glyph_fold` — separators go AND the Cyrillic/Latin twins fold, because the
#     record's own `needle_kinds` name `glyph`: a ЕЛС typed «60AA000593» on a
#     Latin layout is the same document as «60АА000593».
#   * `handle` — LOGIN's own: the registry's `needle_kinds` is `whole` ALONE (no
#     `squeezed`, no `digits`), because a login's dots and underscores ARE the
#     handle — «ivan.petrov» and «ivanpetrov» are two accounts. Only the CASE is
#     folded, and that is a decision rather than a fact: a login is compared
#     case-insensitively by every system that issues one, and a model that
#     re-cases the substitute must still resolve it. Two logins differing only in
#     case are therefore one row, and TYPES.md records the limit.
UTILITY_SIGNATURE_STYLE: dict[str, str] = {
    "GIS_ZHKH_ELS": "glyph_fold",
    "UTILITY_ACCOUNT": "squeezed",
    "CDP_CUSTOMER_ID": "squeezed",
    "LOGIN": "handle",
    "DIPLOMA_NUMBER": "digits",
    "SCHOOL_CERT_NUMBER": "digits",
    "STUDENT_ID_NUMBER": "digits",
    "ACCESS_PASS_NUMBER": "squeezed",
    "EMPLOYEE_TAB_NUMBER": "digits",
    "EMPLOYMENT_CONTRACT_NUMBER": "glyph_fold",
    "PNR": "glyph_fold",
    "E_TICKET_NUMBER": "digits",
}

# The registry's own `value_notation`, copied so a reader sees the record's fact
# beside the engine's choice above.
UTILITY_VALUE_NOTATION: dict[str, str] = {
    "GIS_ZHKH_ELS": "glyph_fold",
    "UTILITY_ACCOUNT": "digits",
    "CDP_CUSTOMER_ID": "squeezed",
    "LOGIN": "",
    "DIPLOMA_NUMBER": "digits",
    "SCHOOL_CERT_NUMBER": "digits",
    "STUDENT_ID_NUMBER": "squeezed",
    "ACCESS_PASS_NUMBER": "squeezed",
    "EMPLOYEE_TAB_NUMBER": "digits",
    "EMPLOYMENT_CONTRACT_NUMBER": "glyph_fold",
    "PNR": "glyph_fold",
    "E_TICKET_NUMBER": "digits",
}

# The registry's own `sample`, used as the fallback LAYOUT when a field key hands
# the mint something its label's shape does not accept (a key types the WHOLE
# value with no shape check, so that is reachable).
UTILITY_SAMPLE: dict[str, str] = {
    "GIS_ZHKH_ELS": "60АА000593-01",
    "UTILITY_ACCOUNT": "1234567890",
    "CDP_CUSTOMER_ID": "c-000184523",
    "LOGIN": "ivanov_d85",
    "DIPLOMA_NUMBER": "107724 0001234",
    "SCHOOL_CERT_NUMBER": "07705000012345",
    "STUDENT_ID_NUMBER": "21-0345",
    "ACCESS_PASS_NUMBER": "0034561",
    "EMPLOYEE_TAB_NUMBER": "004512",
    "EMPLOYMENT_CONTRACT_NUMBER": "145-ТД",
    "PNR": "2ZYVAL",
    "E_TICKET_NUMBER": "5552412345678",
}

# The registry-derived sets the engine reads. `UTILITY_DIGIT_LABELS` is the five
# whose canonical is plain digits; `UTILITY_ATOMIC_LABELS` is the seven whose
# token carries letters and therefore takes the TYPED content signature in
# `vault._digit_signatures` (the same rule §identity/§legal/§finance/§telecom
# state). `UTILITY_NUMERIC_LABELS` is what `vault._NUMERIC_TYPES` needs: every
# label whose value CAN be digit-only — the five, plus the three whose grammar
# admits a digit-only reading beside its letter-bearing ones, so a model that
# strips a substitute's separators still resolves it on the digit index.
UTILITY_DIGIT_LABELS: frozenset[str] = frozenset(
    type_id for type_id, style in UTILITY_SIGNATURE_STYLE.items()
    if style == "digits")
UTILITY_ATOMIC_LABELS: frozenset[str] = frozenset(
    UTILITY_LABELS - UTILITY_DIGIT_LABELS)
UTILITY_CANONICAL_IS_A_KEY: frozenset[str] = UTILITY_ATOMIC_LABELS
UTILITY_NUMERIC_LABELS: frozenset[str] = (
    UTILITY_DIGIT_LABELS
    | {"UTILITY_ACCOUNT", "CDP_CUSTOMER_ID", "ACCESS_PASS_NUMBER"})

# The digit bounds the registry states or its samples prove, read per record. The
# shape below is built FROM these so a reader sees the bound in one place; each
# floor/ceiling is the record's own sample family, never an unbounded `\d+`.
UTILITY_DIGIT_COUNTS: dict[str, frozenset[int]] = {
    "DIPLOMA_NUMBER": frozenset((13,)),
    "SCHOOL_CERT_NUMBER": frozenset((14,)),
    "E_TICKET_NUMBER": frozenset((13,)),
    "EMPLOYEE_TAB_NUMBER": frozenset(range(6, 11)),   # «6–10 цифр (наблюдение)»
    "STUDENT_ID_NUMBER": frozenset(range(5, 11)),     # sample «21-0345» + «цифры»
    "UTILITY_ACCOUNT": frozenset(range(6, 13)),       # «обычно 6–12 цифр»
    "ACCESS_PASS_NUMBER": frozenset((6, 7, 8, 9, 10, 11, 12, 14)),
    "CDP_CUSTOMER_ID": frozenset(range(9, 21)),       # the sample's own floor
}

# ---------------------------------------------------------------- the shapes ---
#
# ONE SHAPE LANGUAGE, AND ITS BOUNDS ARE THE REGISTRY'S OWN FACTS. Every shape is
# cue- or key-anchored (`bare_typed=False` on all twelve), so none of them has to
# stand on a bare number — which is what lets the free-form records be as wide as
# their own sample families without touching an order number.
#
# THE SEPARATOR CLASS IS `[ \t\-/]?` AND NEVER A DOT OR A COLON. A dot is what a
# date and an IPv4 address are written with, and «12.03.2020» after «трудовой
# договор» must stay a DATE; a colon is what a cadastral number and a MAC use, and
# the legal/telecom families already own those readings.
_UT_LETTER = r"[A-Za-zА-Яа-яЁё]"
_UT_DIGIT = r"\d"
_UT_SEP = r"[ \t\-/]"
_UT_SQUEEZE_SEP = r"[ \t\-/]?"

# GIS_ZHKH_ELS — the registry's grammar VERBATIM, all three lengths, with the
# script and case the record's own `form_features` name. THE LETTER SLOTS REQUIRE
# LETTERS: that is what keeps the normalized spelling of a Cyrillic look-alike
# series («60ВВ…» → «6088…») from matching here, so the folded value can never be
# read on the normalized path and the raw path below is the only reading of it.
_UT_GIS = (r"(?<!\d)\d{2}(?:[А-ЯЁа-яё]{2}|[A-Za-z]{2})\d{6}"
           r"(?:-\d{2}(?:-\d{4})?)?(?!\d)")

# UTILITY_ACCOUNT — «нет федеральной; обычно 6–12 цифр, иногда буквы/дефисы».
# Two readings, and the SECOND is the one that gives this label a cue of its own:
# the telecom shape is a digit run, so a letter-bearing account («л/с 12-34АБ»)
# is outside it and answers to this family. The mixed form keeps a letter ADJACENT
# to a digit — that is what makes it a letter-bearing account and not a word, and
# the bounds are the sample family's own.
_UT_ACCOUNT_DIGITS = (r"(?<!\d)\d(?:" + _UT_SQUEEZE_SEP + r"\d){5,11}(?!\d)")
# NO SPACE ANYWHERE IN THE MIXED FORM, and that is the over-mask guard rather than
# a taste: with a space allowed between two characters the shape matched «договор
# 875» — a WORD and a number, behind any of this label's cues — and, being
# leftmost-first, it then claimed the head of the token scan and hid the real
# substitute from the restorer. The registry says «иногда буквы/дефисы»: hyphens,
# and a glued spelling, never a break.
_UT_ACCOUNT_MIXED = (
    r"(?<![0-9A-Za-zА-Яа-яЁё\-/])"
    r"(?=[0-9А-ЯЁа-яёA-Za-z\-/]*\d)"
    r"(?=[\-/0-9]*[А-ЯЁA-Zа-яё])"
    r"[0-9А-ЯЁа-яёA-Za-z](?:[-/]?[0-9А-ЯЁа-яёA-Za-z]){4,11}"
    r"(?![0-9A-Za-zА-Яа-яЁё\-/])")
_UT_ACCOUNT = r"(?:" + _UT_ACCOUNT_DIGITS + r"|" + _UT_ACCOUNT_MIXED + r")"

# CDP_CUSTOMER_ID — «внешней НЕТ — цифры, коды "c-000184523", UUID». All three
# readings the registry names. The UUID shapes are the TELECOM family's own
# constants (`_TC_UUID_GROUPED`/`_TC_UUID_SQUEEZED`), reused rather than restated:
# one UUID shape in one module means the two readings of one device id cannot
# drift, and the Cyrillic hex twins come with them.
_UT_CDP_UUID = r"(?:" + _TC_UUID_GROUPED + r"|" + _TC_UUID_SQUEEZED + r")"
_UT_CDP_CODE = (r"(?<![0-9A-Za-zА-Яа-яЁё])[A-Za-zА-Яа-яЁё]{1,3}[-/]?\d{3,20}"
                r"(?![0-9A-Za-zА-Яа-яЁё])")
# The sample's own floor (nine digits) and the twenty a digit run may reach. A
# SHORTER CDP id is deliberately not claimed by the cue path — see TYPES.md; the
# field-key path still types the WHOLE value, which is P03's own rule.
_UT_CDP_DIGITS = r"(?<!\d)\d{9,20}(?!\d)"
_UT_CDP = r"(?:" + _UT_CDP_UUID + r"|" + _UT_CDP_CODE + r"|" + _UT_CDP_DIGITS + r")"

# LOGIN — `[A-Za-z0-9._-]{3,}` «свободный handle», bounded to a handle's length and
# requiring ONE LETTER. The letter is not in the registry's grammar; it is the
# over-mask guard: «логин 2024» is a year and no system issues an all-digit
# handle that a cue would reach here, while every sample in the registry's own
# industries carries a letter.
_UT_LOGIN = (r"(?<![0-9A-Za-z._\-])(?=[0-9._\-]*[A-Za-z])"
             r"[A-Za-z0-9][A-Za-z0-9._\-]{2,31}(?![0-9A-Za-z._\-])")

# DIPLOMA_NUMBER — the registry's grammar VERBATIM: 6 series characters whose
# first is the organisation type 10–14, then 7 number digits, an optional single
# space between them. THE LEADING «1» AND THE 0–4 ARE GRAMMAR, NOT CONTENT, and
# the mint keeps them (see `_utility_content`).
_UT_DIPLOMA = r"(?<!\d)1[0-4]\d{4}[ \t]?\d{7}(?!\d)"

# SCHOOL_CERT_NUMBER — `\b\d{14}\b`, the registry's own grammar, no separator.
_UT_SCHOOL = r"(?<!\d)\d{14}(?!\d)"

# STUDENT_ID_NUMBER — `ГРАММАТИКА?`. The shape is the registry's own sample family
# («NN-NNNN») plus the «или цифры» the card names, and NOT the permissive
# `[\w-]+` a "free" reading would suggest: a four-digit year after the cue must
# stay a year, which is why the digit-only reading starts at five.
_UT_STUDENT = r"(?<!\d)(?:\d{2}[ \t\-/]?\d{4}|\d{5,10})(?!\d)"

# ACCESS_PASS_NUMBER — «цифры печатного пропуска или RFID UID в hex (8 или 14
# hex)». Two readings, bounded by the record's own note: 6–12 digits (the sample
# «0034561»; a four-digit pass is deliberately not claimed — a year after «пропуск
# на …» is commoner than a four-digit badge) and the 8/14-hex UID.
_UT_PASS_DIGITS = r"(?<!\d)\d{6,12}(?!\d)"
_UT_PASS_HEX = (r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{14}|[0-9A-Fa-f]{8})"
                r"(?![0-9A-Fa-f])")

# EMPLOYEE_TAB_NUMBER — «работодательский цифровой прогон, часто с ведущими нулями
# (6–10 цифр); в 1С ЗУП — "0000-00412"». Both the run and the 1С grouping; the
# grouped form needs five digits after the separator so «2024-2025» — a date
# range in ordinary prose — is not an employee's tab number.
_UT_TAB = (r"(?<!\d)(?:\d{4}[ \t\-/]\d{5,6}|\d{6,10})(?!\d)")

# EMPLOYMENT_CONTRACT_NUMBER — «свободная ("145-ТД", "ТД-2024/017")». A free-form
# number is read as LETTERS AND DIGITS held together by `-` or `/`, with the
# letter group one to three characters: that is what the registry's two samples
# are, and it is narrow enough to refuse a sentence. A GLUED «ТД2024» is
# deliberately not claimed (no registry sample is glued) — TYPES.md records it.
_UT_CONTRACT = (
    r"(?<![0-9A-Za-zА-Яа-яЁё])"
    r"(?:\d{1,6}[-/][А-ЯЁA-Zа-яё]{1,3}(?:[-/]\d{1,6})*"
    r"|[А-ЯЁA-Zа-яё]{1,3}[-/]\d{1,6}(?:[-/]\d{1,6})*)"
    r"(?![0-9A-Za-zА-Яа-яЁё])")

# PNR — `ГРАММАТИКА?`: «5–6 алфавитно-цифровых (GDS); локаторы "Сирены" могут
# использовать кириллицу; пример Amadeus "2ZYVAL"». The length is the registry's;
# the requirement of BOTH a letter and a digit is this family's conservative
# reading of «алфавитно-цифровых» and the over-mask guard — «бронь отеля» is five
# Cyrillic letters and must not become a booking locator. TYPES.md records that an
# all-letter or all-digit locator is reached by the field key, not by the cue.
_UT_PNR = (r"(?<![0-9A-Za-zА-Яа-яЁё])"
           r"(?=[0-9А-ЯЁа-яёA-Za-z]{0,5}[А-ЯЁа-яёA-Za-z])"
           r"(?=[А-ЯЁа-яёA-Za-z]*\d)"
           r"[0-9А-ЯЁа-яёA-Za-z]{5,6}(?![0-9A-Za-zА-Яа-яЁё])")

# E_TICKET_NUMBER — `ГРАММАТИКА?`: the AIR form only («авиа — 13 цифр: 3 + 10»).
# The rail form is «не установлена», so nothing is claimed for it.
_UT_ETICKET = r"(?<!\d)\d{13}(?!\d)"

# THE REGISTRY'S OWN WIDEST FORM PER RECORD, keyed by the ENGINE label.
_UTILITY_SHAPE_TEXT: dict[str, str] = {
    "GIS_ZHKH_ELS": _UT_GIS,
    "UTILITY_ACCOUNT": _UT_ACCOUNT,
    "CDP_CUSTOMER_ID": _UT_CDP,
    "LOGIN": _UT_LOGIN,
    "DIPLOMA_NUMBER": _UT_DIPLOMA,
    "SCHOOL_CERT_NUMBER": _UT_SCHOOL,
    "STUDENT_ID_NUMBER": _UT_STUDENT,
    "ACCESS_PASS_NUMBER": r"(?:" + _UT_PASS_DIGITS + r"|" + _UT_PASS_HEX + r")",
    "EMPLOYEE_TAB_NUMBER": _UT_TAB,
    "EMPLOYMENT_CONTRACT_NUMBER": _UT_CONTRACT,
    "PNR": _UT_PNR,
    "E_TICKET_NUMBER": _UT_ETICKET,
}

UTILITY_SHAPES: dict[str, "re.Pattern[str]"] = {
    label: re.compile(rf"(?i:{shape})")
    for label, shape in _UTILITY_SHAPE_TEXT.items()
}


def utility_signature(value: str, label: str) -> str:
    """The CONTENT identity of a utility identifier, typed by its own label.

    FOUR STYLES, ONE PER KIND OF IDENTITY THE REGISTRY DESCRIBES (see
    `UTILITY_SIGNATURE_STYLE`): a digit-only record keys on its digits, a
    separator-bearing one squeezes the separators, a `glyph` one folds the
    Cyrillic/Latin twins, and a login keeps its own handle and folds only the
    case. For every style but `digits` the LABEL IS PART OF THE KEY, because the
    token's letters are content and two different registry records must not answer
    for each other; the `digits` styles keep the plain digit key so the engine's
    digit-signature index — the thing that resolves a model's regrouping — keeps
    working exactly as it does for a СНИЛС or an ИНН."""
    style = UTILITY_SIGNATURE_STYLE.get(label, "")
    if style == "digits":
        return _digits(value)
    if style == "handle":
        squeezed = value.strip().casefold()
    else:
        squeezed = _IDENTITY_SEPARATORS.sub("", value).upper()
        if style == "glyph_fold":
            squeezed = squeezed.translate(_VIN_GLYPH_FOLD)
    if not squeezed:
        return ""
    return f"{label}\x1f{squeezed}"


def utility_signatures(value: str) -> list[tuple[str, str]]:
    """Every (signature, label) this spelling could be — the restorer's question.

    MORE THAN ONE ANSWER IS POSSIBLE AND THAT IS THE POINT. A six-to-twelve digit
    run is a UTILITY_ACCOUNT and an ACCESS_PASS_NUMBER; «145-ТД» is an employment
    contract and, at the same length, a letter-bearing operator account; a
    thirteen-digit run on «1[0-4]» is an air ticket AND a diploma. Naming ONE
    label would lose whichever row the guess did not name, so every reading whose
    shape `fullmatch`es the spelling is proposed and each is asked as its own
    indexed point query. A hit is kept only when the vault's recorded label is the
    label the signature was proposed under, exactly as `legal_signatures` and
    `finance_signatures` do: a wrong reading costs one query and can never restore
    another type's value."""
    surface = value.strip()
    if not surface:
        return []
    answers: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label, pattern in UTILITY_SHAPES.items():
        if not pattern.fullmatch(surface):
            continue
        signature = utility_signature(surface, label)
        if signature and (signature, label) not in seen:
            seen.add((signature, label))
            answers.append((signature, label))
    return answers


def utility_label_of_shape(value: str) -> str:
    """The FIRST label this spelling could be, for callers that need one name."""
    answers = utility_signatures(value)
    return answers[0][1] if answers else ""


def utility_label_for_source(original: str, label: str) -> str:
    """The label whose VARIANT the source itself is written in.

    A field key types the WHOLE value with no shape check, so a generic key can
    hand a value to a label whose own shape does not accept it — «145-ТД» behind
    `external_id`, say. The mint must preserve the SOURCE's variant, because
    re-shaping it into the label's own sample would hand the customer's validator
    a document that is not there. Only a label whose shape refuses the source is
    re-labelled, and only to another label that accepts it."""
    pattern = UTILITY_SHAPES.get(label)
    if pattern is not None and pattern.fullmatch(original.strip()):
        return label
    for candidate, candidate_pattern in UTILITY_SHAPES.items():
        if candidate_pattern.fullmatch(original.strip()):
            return candidate
    return label


# THE TWO DIGITS THAT ARE GRAMMAR, NOT CONTENT: a diploma's series begins with the
# organisation type, «1» followed by 0–4. Re-drawing them would mint a string that
# is not a diploma number at all, which is why the mint pins them exactly as
# `_legal_pinned_positions` pins a case index.
_UTILITY_PINNED: dict[str, dict[int, str]] = {
    "DIPLOMA_NUMBER": {0: "1", 1: "01234"},
}

# THE TWO RECORDS WHOSE LETTERS ARE HEX, and the alphabet is not a detail: a UUID
# or an RFID UID drawn from A–Z stops being hex, stops matching the family's own
# shape, and — the failure this whole module is built to prevent — stops being a
# candidate for the restorer, so the FAKE reaches the customer's tool with a 200.
# The case is still the source's, character by character.
_UTILITY_HEX_LABELS: frozenset[str] = frozenset(
    ("CDP_CUSTOMER_ID", "ACCESS_PASS_NUMBER"))


def _utility_letter(char: str, label: str) -> str:
    """One random letter for `char`'s position: HEX where the record is hex.

    A hex record's letters come from A–F (in the source's case); every other
    record's come from the source's own script and case (`_letters_like`), so a
    Cyrillic ЕЛС series stays Cyrillic and a login stays a login."""
    if label in _UTILITY_HEX_LABELS:
        pick = secrets.choice("ABCDEF")
        return pick.lower() if char.islower() else pick
    return _letters_like(char)


def _utility_content(label: str, surface: str) -> str:
    """The fake's CONTENT in the source's own character classes and notation.

    ONE RULE, TWO EXCEPTIONS, and each exception is a fact the record states:

      * EVERY ALPHANUMERIC CHARACTER IS DRAWN AFRESH IN ITS OWN CLASS. A digit
        stays a digit, a letter stays a letter IN THE SOURCE'S SCRIPT AND CASE
        (`_letters_like`), and every separator is kept — so a ЕЛС keeps letters in
        its series slots, a UUID keeps hex, an RFID UID keeps eight or fourteen
        hex characters, a login keeps its dots, and the substitute satisfies every
        form check the real value does. This is the frozen benchmark's own
        `id_digits`/`id_alnum` rule (§6.2).
      * A GRAMMAR-PINNED POSITION KEEPS ITS VALUE (`_UTILITY_PINNED`): a diploma's
        leading «1» and its 0–4 organisation type are the format, not the number.
      * THE CONTENT NEVER EQUALS THE SOURCE: the caller re-draws, and the loop is
        bounded there — a renderer that raises is a 5xx on the masking path, the
        one failure this product does not accept."""
    pinned = _UTILITY_PINNED.get(label, {})
    out: list[str] = []
    index = 0
    for char in surface:
        if char.isdigit():
            if index in pinned:
                out.append(secrets.choice(pinned[index]))
            else:
                out.append(secrets.choice("0123456789"))
            index += 1
        elif char.isalpha():
            out.append(_utility_letter(char, label))
            index += 1
        else:
            out.append(char)
    return "".join(out)


def mint_utility(label: str, original: str) -> str:
    """A format-preserving fake for a utility/account/education/travel identifier.

    THE SHAPE IS THE CUSTOMER'S, THE CONTENT IS OURS. `render_like_atomic` lays
    the fake into the source's separators and letter case and `_utility_content`
    keeps its character classes, so the substitute satisfies every form check the
    real value does and names no account, no student and no booking. There is no
    checksum to inherit (the registry gives none) and therefore no validity to
    preserve: what is preserved is FORMAT.

    TWO FALLBACKS, BOTH FAIL-CLOSED, both reachable only through a field key,
    which types the WHOLE value with no shape check: a source that is not the
    label's shape is minted from the registry's own SAMPLE layout rather than
    echoed back (an echo would send the source's own characters to the model under
    a substitute's name), and the re-draw loop keeps the fake from ever equalling
    the source. A candidate that escaped every token shape would be a FAKE the
    restorer can never see, so the last check before returning is the family's own
    alternation — and the mint is TOTAL, because a renderer that raises is a 5xx
    on the masking path."""
    label = LABEL_TO_UTILITY.get(label, label)
    surface = original.strip()
    pattern = UTILITY_SHAPES.get(label)
    if not surface or pattern is None or not pattern.fullmatch(surface):
        surface = UTILITY_SAMPLE.get(label, "")
        if surface:
            label = utility_label_for_source(surface, label)
    if not surface:
        return ""
    fake = render_like_atomic(_utility_content(label, surface), surface)
    for _ in range(8):
        if fake != surface and UTILITY_TOKEN_RE.fullmatch(fake):
            return fake
        content = _utility_content(label, surface)
        fake = render_like_atomic(content, surface)
    return fake


# Every shape `mint_utility` can be shown in. `unmask_text` finds candidates by
# SHAPE, so a token shape that escapes this tuple stops being reversible and a
# FAKE reaches the customer's tool — the invariant `TOKEN_PATTERNS`,
# `LEGAL_TOKEN_PATTERNS`, `FINANCE_TOKEN_PATTERNS` and `TELECOM_TOKEN_PATTERNS`
# all state, applied to this family. The tuple is built from the SAME
# `_UTILITY_SHAPE_TEXT` the recognizer uses rather than restated by hand.
#
# THE ORDER IS LOAD-BEARING IN ONE PLACE: the broad LOGIN shape stands LAST,
# because it matches any Latin handle-shaped word and every more specific shape
# must be asked first. Within a family the lookup is by TOKEN STRING and by
# CONTENT signature, so an overlap between two of these patterns costs a
# candidate, never a wrong value.
_UT_TOKEN_START = r"(?<![0-9A-Za-zА-Яа-яЁё])"
_UT_TOKEN_END = r"(?![0-9A-Za-zА-Яа-яЁё])"

UTILITY_TOKEN_PATTERNS: tuple[str, ...] = (
    _UT_GIS,                                    # GIS_ZHKH_ELS
    _UT_CONTRACT,                               # EMPLOYMENT_CONTRACT_NUMBER
    _UT_CDP_UUID,                               # CDP_CUSTOMER_ID (UUID)
    _UT_CDP_CODE,                               # CDP_CUSTOMER_ID (code)
    _UT_PNR,                                    # PNR
    _UT_PASS_HEX,                               # ACCESS_PASS_NUMBER (hex UID)
    _UT_DIPLOMA,                                # DIPLOMA_NUMBER
    _UT_SCHOOL,                                 # SCHOOL_CERT_NUMBER
    _UT_ETICKET,                                # E_TICKET_NUMBER
    _UT_TAB,                                    # EMPLOYEE_TAB_NUMBER
    _UT_STUDENT,                                # STUDENT_ID_NUMBER
    _UT_ACCOUNT_MIXED,                          # UTILITY_ACCOUNT (letters)
    _UT_ACCOUNT_DIGITS,                         # UTILITY_ACCOUNT (digits)
    _UT_PASS_DIGITS,                            # ACCESS_PASS_NUMBER (digits)
    _UT_CDP_DIGITS,                             # CDP_CUSTOMER_ID (digits)
    # …AND THE BROAD ONE LAST: `LOGIN` matches any Latin word carrying a letter,
    # and a leftmost-first alternation must meet every specific shape first.
    _UT_LOGIN,                                  # LOGIN
)

# THE FAMILY'S OWN ALTERNATION, COMPILED ONCE — the same second line of defence
# `LEGAL_TOKEN_RE`, `FINANCE_TOKEN_RE` and `TELECOM_TOKEN_RE` are. `vault._token_re`
# is a non-overlapping leftmost-first scan, so a token another family's shape
# matches AROUND is skipped in full; asking this alternation separately means the
# family's reversibility never depends on who else matched nearby. A dead
# candidate costs one indexed point query and is never spliced.
UTILITY_TOKEN_RE = re.compile("|".join(
    _UT_TOKEN_START + pattern + _UT_TOKEN_END
    for pattern in UTILITY_TOKEN_PATTERNS))


# ------------------------------------------------------------ raw-text entry ---
#
# THE SAME QUESTION THE TELECOM FAMILY ASKED, AND FOR THE SAME REASON. A ЕЛС
# series is Cyrillic and `normalize()` folds digit look-alikes inside any run
# holding five or more real digits, so «60ВВ000593-01» arrives at the cue path as
# «6088000593-01» — a string with no letters in the series slots, which no shape
# of this family accepts (and must not: the value the customer wrote is the one
# that has to come back). The family's cue path therefore runs on the RAW text,
# exactly as the telecom one does, on the same invariant: `normalize()` is 1:1, so
# offsets taken on the raw string index identically into every layer downstream.
#
# The caller is `ru_pii.detect_structured(norm, raw)`, which asks ONE name for the
# raw-text reading — `ru_pii_v6.detect_telecom`. That file is outside this
# family's write scope, so the answer is APPENDED here rather than edited there:
# the telecom function keeps its body untouched (see `_raw_telecom_detect`), and
# the module binding the caller resolves is the two-family one below. One entry
# point, one question, two families — and no second caller seam invented.
_raw_telecom_detect = detect_telecom


def detect_utility_raw(raw_text: str) -> list[Span]:
    """This family's cue path, on the RAW text (see the note above)."""
    try:
        from pseudex.assets import ASSETS
        if not ASSETS.is_loaded:
            return []
        patterns = ASSETS.get().ru_pii.ctx_patterns
    except Exception:                                                # noqa: BLE001
        return []
    spans: list[Span] = []
    for entity_type, pattern in patterns:
        if entity_type not in UTILITY_LABELS:
            continue
        for match in pattern.finditer(raw_text):
            spans.append(Span(match.start(1), match.end(1), entity_type,
                              match.group(1)))
    return spans


def detect_telecom(raw_text: str) -> list[Span]:      # noqa: F811
    """The raw-text cue path of the TELECOM and UTILITY families.

    REBOUND, NOT REWRITTEN, and the reason is a boundary rather than a taste: the
    caller (`ru_pii.detect_structured`) is outside this family's write scope, and
    the telecom family's own body is preserved above it as `_raw_telecom_detect`.
    A value whose identity is LETTERS — a UUID's hex, a ЕЛС's Cyrillic series —
    must not be read through a fold meant for digits, and both families have such
    values; asking the SAME leased cue table for both is what keeps the two from
    drifting apart."""
    spans = _raw_telecom_detect(raw_text)
    spans.extend(detect_utility_raw(raw_text))
    return spans
