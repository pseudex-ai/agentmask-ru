"""N1 — the v6 registry families the engine now supports natively.

FIVE SECTIONS, one per family, each APPENDED to the one before it: the eleven
checksum-carrying types (§checksum), the eight identity documents (§identity),
the six legal/court records (§legal), the ten finance/insurance/medical records
(§finance) and the eight telecom/device records (§telecom).

Each family answers the same three questions per type, and each is a separate
question with its own failing witness:

  RECOGNIZE — the value is found, and the TYPE is the one the source names (a
  mistyped IBAN is an IBAN; a licence mistaken for a phone puts a fake phone in
  the customer's field; an insurance claim mistaken for a court case puts a fake
  case number there).

  MINT — the substitute is FORMAT-PRESERVING and, where the registry publishes a
  checksum, INHERITS THE SOURCE'S VALIDITY (`COV-CHECKSUM-INHERIT`,
  OWNER-DECISIONS.md:23): a valid source mints a valid fake, a faulty source
  mints a faulty one, and the substituted value never equals the source. The
  engine never re-mints until the checksum FAILS — that is the historical R6-39
  rule the owner rejected (V1 SPEC §5).

  RESTORE — the real value comes back on the OUT leg, in the AGENT'S explicit
  notation, and a substitute that could not be resolved is NAMED as a residual
  rather than trusted.

Reference vectors for the checksum family are the published arithmetic, computed
independently (`work/V0/evidence/frozen/pypath/bench/agentpii5/checksum_v6.py`)
and hardcoded here so this suite does not import the benchmark package the
product must not depend on.

    python3 test_pii_v6.py
"""

import json
import re
import sys
import tempfile

import testkit
from pseudex import ru_pii_v6 as v6
from pseudex.assets import ASSETS
from pseudex.detect_all import Detector
from pseudex.normalize import normalize
from pseudex.redact import (mask_text, surviving_substitutes, unmask_arguments,
                            unmask_text)
from pseudex.structured import detect_structured_kv
from pseudex.vault import Vault, token_re

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(label)


# --- reference vectors (independent arithmetic) ------------------------------
#
# Every value below was minted by the frozen validator's own check-digit
# routine, and `_corrupt` breaks exactly ONE alphanumeric position so the
# negative control carries the same shape and the same length.

VALID: dict[str, str] = {
    "IMEI": "526018159083010",
    "OMS_ENP": "6613186091390990",
    "ICCID": "6030824628194821990",
    "OGRNIP": "231948757491188",
    "EPTS_NUMBER": "287702287921741",
    "UIN": "79711471049746507524",
    "UIN25": "9170342366712768426846565",
    "VIN": "952SVA0422CF17579",
    "IBAN": "RU9404980574640602810700000000025",
    "LOAN_UID": "a13043b0-26c4-8bbf-33fe-ff9243a8f506-0",
    "LOYALTY_CARD_NUMBER": "852808414852538885",
    "LOYALTY_13": "5393363387501",
}

# The bank account's key is a (account, BIK) PAIR. The benchmark's own
# convention pins the BIK the registry sample was minted against; the engine
# inherits a BIK from the field context when one is there and otherwise proves
# the account cannot belong to a real pair (see `is_business_account`).
_BANK_BIK = "049805746"
_BANK_ACCOUNT = "40602810700000000025"

# The registry's own engine labels for three of the eleven types. The family is
# native either way; these three already had an engine name and v5 semantics
# that must not move (`COV-INTEGRATION-KEEP-V5`).
LABEL = {
    "BANK_ACCOUNT": "ACCOUNT",
    "OGRNIP": "OGRN",
    "OMS_ENP": "OMS",
    "EPTS_NUMBER": "EPTS",
    "LOYALTY_CARD_NUMBER": "LOYALTY",
}


def _corrupt_last(value: str) -> str:
    """The same value with its LAST alphanumeric position changed — the check
    position for every type whose checksum is a trailing character."""
    for index in range(len(value) - 1, -1, -1):
        char = value[index]
        if char.isdigit():
            replacement = "0" if char != "0" else "1"
            return value[:index] + replacement + value[index + 1:]
        if char in "abcdef":
            return value[:index] + ("a" if char != "a" else "b") + value[index + 1:]
        if char in "ABCDEF":
            return value[:index] + ("A" if char != "A" else "B") + value[index + 1:]
        if char in "XYZ":
            return value[:index] + ("A" if char != "A" else "B") + value[index + 1:]
    raise AssertionError(f"nothing to corrupt in {value!r}")


def _corrupt_key(account: str) -> str:
    """A bank account with its KEY digit (position 9) changed — the only
    position the ЦБ 515 pair check reads."""
    return account[:8] + ("0" if account[8] != "0" else "1") + account[9:]


def _vault() -> Vault:
    return Vault(":memory:", "n1-checksum")


def _found(detector: Detector, text: str, entity_type: str, value: str) -> bool:
    return any(span.entity_type == entity_type
               and text[span.start:span.end] == value
               for span in detector.detect(text))


def _types_found(detector: Detector, text: str) -> list[tuple[str, str]]:
    return [(span.entity_type, span.value) for span in detector.detect(text)]


# ---------------------------------------------------------------- validators

def test_validators(detector: Detector) -> None:
    """Each engine validator agrees with the published arithmetic, and a
    one-digit change flips it. A validator that accepted the corrupted form
    would be no gate at all — the mutation the acceptance asks for."""
    cases = [
        ("IMEI", "validate_imei", VALID["IMEI"]),
        ("OMS_ENP", "validate_oms_enp", VALID["OMS_ENP"]),
        ("ICCID", "validate_iccid", VALID["ICCID"]),
        ("OGRNIP", "validate_ogrnip", VALID["OGRNIP"]),
        ("EPTS_NUMBER", "validate_epts_number", VALID["EPTS_NUMBER"]),
        ("UIN", "validate_uin", VALID["UIN"]),
        ("VIN", "validate_vin", VALID["VIN"]),
        ("IBAN", "validate_iban", VALID["IBAN"]),
        ("LOAN_UID", "validate_loan_uid", VALID["LOAN_UID"]),
        ("LOYALTY_CARD_NUMBER", "validate_loyalty_card_number",
         VALID["LOYALTY_CARD_NUMBER"]),
    ]
    problems: list[str] = []
    for type_id, name, value in cases:
        validator = getattr(v6, name)
        if not validator(value):
            problems.append(f"{type_id}: valid vector rejected")
        broken = _corrupt_last(value)
        if validator(broken):
            problems.append(f"{type_id}: corrupt vector accepted ({broken})")
    if not v6.validate_uin(VALID["UIN25"]):
        problems.append("UIN: 25-digit vector rejected")
    if not v6.validate_loyalty_card_number(VALID["LOYALTY_13"]):
        problems.append("LOYALTY: 13-digit vector rejected")
    if not v6.validate_account(_BANK_ACCOUNT, _BANK_BIK):
        problems.append("BANK_ACCOUNT: registry sample rejected for its BIK")
    if v6.validate_account(_corrupt_key(_BANK_ACCOUNT), _BANK_BIK):
        problems.append("BANK_ACCOUNT: corrupt key accepted")
    check("every validator accepts its vector and rejects the one-digit change",
          not problems, "; ".join(problems) if problems else f"{len(cases) + 5} vectors")


def test_typed_invalid_path() -> None:
    """TYPED_INVALID = COV-TYPED-INVALID. Behind a cue the evidence IS the cue:
    a customer who mistypes one digit of their ОМС has still typed their ОМС,
    and the checksum gate must not send it to the model in the clear. The SAME
    string with no cue stays unmasked — a bare 16-digit run is an order number."""
    detector = Detector()
    problems: list[str] = []
    for cue, type_id, value, label in (
            # THE LABEL IS THE REGISTRY ID (G7, 02.10.2026). The span used to
            # carry the engine's internal alias (`OMS`, `OGRN`, `EPTS`,
            # `LOYALTY`) and the benchmark's `typed` axis read the record id;
            # `ru_pii_v6.engine_label` translates back for the vault, so the
            # masking, the mint and the restore are unchanged and only the span's
            # name moved.
            ("полис ОМС ", "OMS_ENP", VALID["OMS_ENP"], "OMS_ENP"),
            ("УИН ", "UIN", VALID["UIN"], "UIN"),
            ("IMEI ", "IMEI", VALID["IMEI"], "IMEI"),
            ("ОГРНИП ", "OGRNIP", VALID["OGRNIP"], "OGRNIP"),
            ("номер ЭПТС ", "EPTS_NUMBER", VALID["EPTS_NUMBER"], "EPTS_NUMBER"),
            ("карта лояльности ", "LOYALTY_CARD_NUMBER",
             VALID["LOYALTY_CARD_NUMBER"], "LOYALTY_CARD_NUMBER"),
            ("ICCID ", "ICCID", VALID["ICCID"], "ICCID"),
    ):
        broken = _corrupt_last(value)
        text = cue + broken
        if not _found(detector, text, label, broken):
            problems.append(f"{type_id}: faulty value behind its cue leaked")
        bare = f"код {broken}"
        if _types_found(detector, bare):
            problems.append(f"{type_id}: bare faulty value was typed "
                            f"{_types_found(detector, bare)}")
    check("a faulty value behind its own cue is protected, bare is not",
          not problems, "; ".join(problems) if problems else "7 types")


# --------------------------------------------------------------- recognize

CUE_TEXTS: list[tuple[str, str, str, str]] = [
    # (type_id, label, text, value that must be typed). THE LABEL COLUMN IS THE
    # SPAN'S LABEL AND SINCE G7 IT IS THE REGISTRY ID for the eight aligned
    # records (`engine_labels` named the old alias); the two columns are kept so
    # a reader can see the pair rather than infer it.
    ("BANK_ACCOUNT", "BANK_ACCOUNT", "расчётный счёт 40817810899910004312",
     "40817810899910004312"),
    ("BANK_ACCOUNT", "BANK_ACCOUNT", "{\"account\": \"40817810099910004312\"}",
     "40817810099910004312"),
    ("IBAN", "IBAN", "IBAN RU9404980574640602810700000000025",
     "RU9404980574640602810700000000025"),
    ("IBAN", "IBAN", "{\"iban\": \"KZ86125KZT5004100100\"}", "KZ86125KZT5004100100"),
    ("LOAN_UID", "LOAN_UID",
     "УИД a13043b0-26c4-8bbf-33fe-ff9243a8f506-0",
     "a13043b0-26c4-8bbf-33fe-ff9243a8f506-0"),
    ("LOAN_UID", "LOAN_UID",
     "{\"loan_uid\": \"a13043b0-26c4-8bbf-33fe-ff9243a8f506-0\"}",
     "a13043b0-26c4-8bbf-33fe-ff9243a8f506-0"),
    ("OMS_ENP", "OMS_ENP", "полис ОМС 6613186091390990", "6613186091390990"),
    ("OMS_ENP", "OMS_ENP", "{\"enp\": \"6613186091390990\"}", "6613186091390990"),
    ("IMEI", "IMEI", "IMEI 526018159083010", "526018159083010"),
    ("IMEI", "IMEI", "{\"imei\": \"526018159083010\"}", "526018159083010"),
    ("ICCID", "ICCID", "ICCID 6030824628194821990", "6030824628194821990"),
    ("ICCID", "ICCID", "{\"iccid\": \"6030824628194821990\"}",
     "6030824628194821990"),
    ("EPTS_NUMBER", "EPTS_NUMBER", "номер ЭПТС 287702287921741", "287702287921741"),
    ("EPTS_NUMBER", "EPTS_NUMBER", "{\"epts\": \"287702287921741\"}", "287702287921741"),
    ("OGRNIP", "OGRNIP", "ОГРНИП 231948757491188", "231948757491188"),
    ("UIN", "UIN", "УИН 79711471049746507524", "79711471049746507524"),
    ("UIN", "UIN", "{\"uin\": \"9170342366712768426846565\"}",
     "9170342366712768426846565"),
    ("LOYALTY_CARD_NUMBER", "LOYALTY_CARD_NUMBER",
     "карта лояльности 852808414852538885", "852808414852538885"),
    ("LOYALTY_CARD_NUMBER", "LOYALTY_CARD_NUMBER",
     "{\"loyalty_card\": \"5393363387501\"}", "5393363387501"),
    # «VIN» alone is tagged a person by the NER (three capitals), so the cue
    # used here is the Russian one the registry also names.
    ("VIN", "VIN", "номер кузова 952SVA0422CF17579", "952SVA0422CF17579"),
]

# THE PRINTED GROUPINGS ARE PART OF THE GRAMMAR, not decoration: the registry
# card names «слитно, 4×4» for ОМС and «4×5» for an account, and a shape that
# demands the glued form is the shape the customer who copies off their own
# document does not have. The label is the registry id (G7).
GROUPED_TEXTS: list[tuple[str, str, str]] = [
    ("OMS_ENP", "полис ОМС 6613 1860 9139 0990", "6613 1860 9139 0990"),
    ("BANK_ACCOUNT", "расчётный счёт 4081 7810 8999 1000 4312",
     "4081 7810 8999 1000 4312"),
    ("OGRNIP", "ОГРНИП 231 948 757 491 188", "231 948 757 491 188"),
    ("ICCID", "ICCID 6030 8246 2819 4821 990", "6030 8246 2819 4821 990"),
    ("LOYALTY_CARD_NUMBER", "карта лояльности 8528 0841 4852 5388 85",
     "8528 0841 4852 5388 85"),
]


def test_recognize_cued_and_keyed(detector: Detector) -> None:
    """Cue context and field-key context both type the value, on the real
    pipeline (`Detector.detect`), not on a unit call to the recognizer."""
    problems: list[str] = []
    for type_id, label, text, value in CUE_TEXTS:
        if not _found(detector, text, label, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    check("cued and field-keyed values are recognized with the right type",
          not problems, "; ".join(problems) if problems else f"{len(CUE_TEXTS)} texts")


def test_recognize_grouped_notation(detector: Detector) -> None:
    """The registry's printed groupings (ОМС «4×4», an account «4×5», an ОГРНИП
    «324 77 000012345 5») are recognized whole — and the ROUND TRIP keeps the
    digits, which is the only thing the customer's tool needs back."""
    problems: list[str] = []
    vault = _vault()
    for label, text, value in GROUPED_TEXTS:
        if not _found(detector, text, label, value):
            problems.append(f"{label}: {text!r} -> {_types_found(detector, text)}")
            continue
        masked = mask_text(text, vault, detector.detect(text))
        restored = unmask_text(masked, vault)
        if _digits(value) not in _digits(restored):
            problems.append(f"{label}: digits lost {masked!r} -> {restored!r}")
    check("printed groupings are recognized and round-trip", not problems,
          "; ".join(problems) if problems else f"{len(GROUPED_TEXTS)} groupings")


def test_bare_checksum_anchor(detector: Detector) -> None:
    """The distinct-shape types stand alone; the digit-only weak ones do not.

    A bare positive is allowed only where the anchor is more than the value: an
    IBAN's country code is a closed registry the source must belong to, and a
    LOAN_UID is a 32-hex UUID plus its control character. A bare 15/16/20-digit
    run is an order or a tracking number, and `bare_typed=False` on every v6
    record says so — VIN and ОГРНИП keep their v5 bare-checksum behaviour
    (`COV-INTEGRATION-KEEP-V5`)."""
    problems: list[str] = []
    bare_positive = [
        ("IBAN", "IBAN", VALID["IBAN"]),
        ("LOAN_UID", "LOAN_UID", VALID["LOAN_UID"]),
        ("VIN", "VIN", VALID["VIN"]),
        ("OGRNIP", "OGRN", VALID["OGRNIP"]),
    ]
    for type_id, label, value in bare_positive:
        if not _found(detector, f"значение {value} конец", label, value):
            problems.append(f"{type_id}: bare valid value missed")
    # The same shapes with the checksum broken and NO cue are negatives.
    bare_negative = [
        ("IBAN", _corrupt_last(VALID["IBAN"])),
        ("LOAN_UID", _corrupt_last(VALID["LOAN_UID"])),
        ("IMEI", _corrupt_last(VALID["IMEI"])),
        ("ICCID", _corrupt_last(VALID["ICCID"])),
        ("OMS_ENP", _corrupt_last(VALID["OMS_ENP"])),
        ("UIN", _corrupt_last(VALID["UIN"])),
        ("LOYALTY_CARD_NUMBER", _corrupt_last(VALID["LOYALTY_CARD_NUMBER"])),
    ]
    for type_id, value in bare_negative:
        found = _types_found(detector, f"значение {value} конец")
        if found:
            problems.append(f"{type_id}: bare corrupt value typed {found}")
    check("bare positives only where the shape anchors them", not problems,
          "; ".join(problems) if problems else "4 positives, 7 negatives")


def test_business_accounts_stay_open(detector: Detector) -> None:
    """The v6 negative families `CORR_ACCOUNT`, `LEGAL_ACCOUNT`,
    `TREASURY_ACCOUNT`. A legal entity's account identifies no data subject
    (152-ФЗ ст. 3 п. 1 / GDPR Recital 14) and masking it breaks the customer's
    own payment flow — the same line that removed 13-digit ОГРН from the engine."""
    detector = Detector()
    negatives = [
        "корр. счёт 30101810400000000225",
        "расчётный счёт 40702810600000001234",
        "казначейский счёт 03100643000000000123",
        "казначейский счёт 40102810900000000123",
    ]
    problems = [text for text in negatives
                if any(span.entity_type == "ACCOUNT"
                       for span in detector.detect(text))]
    check("business accounts are not typed as a person's account",
          not problems, "; ".join(problems) if problems else f"{len(negatives)} negatives")


def test_no_fuzzy_numerals(detector: Detector) -> None:
    """A ONE-EDIT NUMERAL IS NOT THE VALUE. The engine mines typos for NAMES,
    and that machinery must not reach a checksum: «526018159083011» is not a
    mistyped IMEI, it is a different number. Behind the cue it is still masked
    (a typed-invalid value is the customer's), but as ITSELF — never resolved to
    the valid vector it is one edit away from."""
    problems: list[str] = []
    for type_id, label, value in (("IMEI", "IMEI", VALID["IMEI"]),
                                  ("ICCID", "ICCID", VALID["ICCID"]),
                                  ("UIN", "UIN", VALID["UIN"])):
        broken = _corrupt_last(value)
        if v6.validate(type_id, broken):
            problems.append(f"{type_id}: corrupt value validates")
        # The corrupt value must not be reported as the valid one.
        if _found(detector, f"IMEI {broken}", label, value):
            problems.append(f"{type_id}: corrupt value resolved to the valid one")
    check("a mutating checksum is not read as a typo of another value",
          not problems, "; ".join(problems) if problems else "3 types")


# ------------------------------------------------------------------- mint

MINT_CASES: list[tuple[str, str]] = [
    ("BANK_ACCOUNT", "40817810099910004312"),
    ("IBAN", VALID["IBAN"]),
    ("LOAN_UID", VALID["LOAN_UID"]),
    ("OGRNIP", VALID["OGRNIP"]),
    ("OMS_ENP", VALID["OMS_ENP"]),
    ("VIN", VALID["VIN"]),
    ("EPTS_NUMBER", VALID["EPTS_NUMBER"]),
    ("UIN", VALID["UIN"]),
    ("UIN", VALID["UIN25"]),
    ("IMEI", VALID["IMEI"]),
    ("ICCID", VALID["ICCID"]),
    ("LOYALTY_CARD_NUMBER", VALID["LOYALTY_CARD_NUMBER"]),
    ("LOYALTY_CARD_NUMBER", VALID["LOYALTY_13"]),
]


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def test_mint_inherits_validity() -> None:
    """COV-CHECKSUM-INHERIT. A valid source mints a VALID fake of the same
    shape; a faulty source mints a faulty fake. The substitute is never the
    source, and the engine never re-mints until the checksum fails — the old
    R6-39 rule the owner rejected."""
    problems: list[str] = []
    for type_id, original in MINT_CASES:
        vault = _vault()
        if type_id == "BANK_ACCOUNT":
            # THE PAIR CHECK NEEDS THE BIK. The pipeline has no BIK channel, so
            # there the promise is the SHAPE (checked here); the verdict
            # inheritance is checked below with an explicit BIK, which is where
            # it is computable at all. See TYPES.md for the honest limit.
            fake = vault.tokenize(original, "ACCOUNT")
            if fake == original:
                problems.append("BANK_ACCOUNT: substitute equals the source")
            if not v6.validate_bank_account_shape(fake):
                problems.append(f"BANK_ACCOUNT: shape-invalid fake {fake!r}")
            continue
        valid_source = v6.validate(type_id, original)
        if not valid_source:
            problems.append(f"{type_id}: the source vector is not valid")
            continue
        fake = vault.tokenize(original, LABEL.get(type_id, type_id))
        if fake == original:
            problems.append(f"{type_id}: substitute equals the source")
        if type_id in ("IMEI", "ICCID", "OMS_ENP", "OGRNIP", "EPTS_NUMBER",
                       "UIN", "LOYALTY_CARD_NUMBER") \
                and len(_digits(fake)) != len(_digits(original)):
            problems.append(f"{type_id}: digit count changed "
                            f"{len(_digits(original))} -> {len(_digits(fake))}")
        if not v6.validate(type_id, fake):
            problems.append(f"{type_id}: VALID source minted an INVALID fake {fake!r}")
    # The pair check, where it IS computable: the same account, one BIK.
    good = v6.mint("BANK_ACCOUNT", _BANK_ACCOUNT, _BANK_BIK)
    if not v6.validate_account(good, _BANK_BIK):
        problems.append(f"BANK_ACCOUNT: valid source + its BIK minted {good!r}")
    bad = v6.mint("BANK_ACCOUNT", _corrupt_key(_BANK_ACCOUNT), _BANK_BIK)
    if v6.validate_account(bad, _BANK_BIK):
        problems.append(f"BANK_ACCOUNT: faulty source was repaired into {bad!r}")
    check("a valid source mints a valid fake of the same shape",
          not problems, "; ".join(problems) if problems else f"{len(MINT_CASES)} mints")


def test_mint_mirrors_faults() -> None:
    """«Ошибочный исходник не исправлять подменой» (OWNER-DECISIONS.md:23) —
    and the input the live engine actually meets is the faulty one: a customer
    reading a number out loud drops a digit. The substitute keeps the fault."""
    problems: list[str] = []
    for type_id, original in MINT_CASES:
        if type_id == "BANK_ACCOUNT":
            continue  # paired checksum: the fault line is the account shape below
        broken = _corrupt_last(original)
        if v6.validate(type_id, broken):
            problems.append(f"{type_id}: the fault vector is valid")
            continue
        fake = _vault().tokenize(broken, LABEL.get(type_id, type_id))
        if v6.validate(type_id, fake):
            problems.append(f"{type_id}: faulty source was REPAIRED into {fake!r}")
    check("a faulty source mints a faulty fake", not problems,
          "; ".join(problems) if problems else f"{len(MINT_CASES) - 1} types")


def test_mint_safe_ranges() -> None:
    """Per-type safe-range proofs (OWNER-DECISIONS.md:23 «генерация и
    безопасные диапазоны доказываются отдельно по типам»). Where the source
    format admits a value that cannot belong to anybody, the fake uses it; where
    it does not (a UUID, a proprietary loyalty number), the proof is recorded
    as the collision argument in TYPES.md instead of being faked here."""
    problems: list[str] = []
    for _ in range(50):
        imei = _vault().tokenize("000000000000000", "IMEI")
        if not imei.startswith("00"):
            problems.append(f"IMEI RBI is assigned: {imei}")
        break
    for _ in range(50):
        iccid = _vault().tokenize(VALID["ICCID"], "ICCID")
        if not iccid.startswith(("890", "897")):
            problems.append(f"ICCID country prefix unexpected: {iccid}")
        break
    for _ in range(50):
        oms = _vault().tokenize(VALID["OMS_ENP"], "OMS")
        if not oms.startswith("000"):
            problems.append(f"OMS region code assigned: {oms}")
        break
    for _ in range(50):
        ogrnip = _vault().tokenize(VALID["OGRNIP"], "OGRN")
        if ogrnip[3:5] != "00":
            problems.append(f"OGRNIP region code assigned: {ogrnip}")
        break
    for _ in range(50):
        vin = _vault().tokenize(VALID["VIN"], "VIN")
        if not vin.startswith("0"):
            problems.append(f"VIN region assigned: {vin}")
        break
    for _ in range(50):
        iban = _vault().tokenize(VALID["IBAN"], "IBAN")
        if not iban.startswith("RU") or not v6.validate_iban(iban):
            problems.append(f"IBAN fake invalid or foreign: {iban}")
        elif iban[4:13] != "000000000":
            problems.append(f"IBAN bank code is assigned: {iban}")
        break
    for _ in range(50):
        uin = _vault().tokenize(VALID["UIN"], "UIN")
        if not uin.startswith("000"):
            problems.append(f"UIN administrator code assigned: {uin}")
    for _ in range(50):
        account = _vault().tokenize("40817810899910004312", "ACCOUNT")
        if not account.startswith(("408", "423", "424", "425", "426")):
            problems.append(f"account balance prefix is not a personal one: {account}")
        break
    check("minted fakes come from proven-safe ranges", not problems,
          "; ".join(problems) if problems else "7 range families")


# ----------------------------------------------------------------- restore

def test_roundtrip_text_args_and_stream() -> None:
    """The real value comes back on every OUT shape the product has: prose, a
    tool argument, and a streamed chunk. A substitute that fails to resolve is
    a FAKE reaching the customer's tool with a 200 and an empty log."""
    detector = Detector()
    vault = _vault()
    problems: list[str] = []
    for type_id, label, text, value in CUE_TEXTS:
        if text.startswith("{"):
            continue
        spans = detector.detect(text)
        masked = mask_text(text, vault, spans)
        if value in masked:
            problems.append(f"{type_id}: value still standing in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{type_id}: {value!r} did not return from {masked!r}")
    # A TOOL ARGUMENT is JSON, and the tool call must parse after restoration.
    payload = json.dumps({"iban": VALID["IBAN"], "imei": VALID["IMEI"],
                          "uin": VALID["UIN"], "enp": VALID["OMS_ENP"]},
                         ensure_ascii=False)
    masked = mask_text(payload, vault, detector.detect(payload))
    opened = unmask_arguments(masked, vault)
    if VALID["IBAN"] not in opened or VALID["IMEI"] not in opened:
        problems.append(f"argument leg lost a value: {masked!r} -> {opened!r}")
    if not json.loads(opened):
        problems.append(f"argument leg is not JSON after restore: {opened!r}")
    # STREAM: a chunk that carries the substitute whole.
    chunk = f"полис {mask_text('полис ' + VALID['OMS_ENP'], vault, detector.detect('полис ' + VALID['OMS_ENP']))}"
    from pseudex.redact import unmask_stream_chunk
    emitted, carry = unmask_stream_chunk(chunk, "", vault, flush=True)
    if VALID["OMS_ENP"] not in emitted + carry:
        problems.append(f"stream leg lost the value: {emitted + carry!r}")
    check("restore works on prose, tool arguments and streamed chunks",
          not problems, "; ".join(problems) if problems else "3 legs")


def test_notation_preserved() -> None:
    """P02/класс А: the FORM belongs to the agent, the CONTENT to the vault.
    A model that regroups the substitute gets the real digits in ITS grouping —
    never the customer's stale presentation, and never a silent re-format."""
    detector = Detector()
    problems: list[str] = []
    cases = [
        ("IMEI", VALID["IMEI"]),
        ("ICCID", VALID["ICCID"]),
        ("UIN", VALID["UIN"]),
    ]
    for type_id, value in cases:
        vault = _vault()
        text = f"{type_id} {value}"
        masked = mask_text(text, vault, detector.detect(text))
        fake = masked.split(" ", 1)[1]
        digits = _digits(fake)
        grouped = " ".join(digits[i:i + 4] for i in range(0, len(digits), 4))
        restored = unmask_text(f"{type_id} {grouped}", vault)
        real = restored.split(" ", 1)[1]
        if _digits(real) != _digits(value):
            problems.append(f"{type_id}: content lost: {grouped!r} -> {restored!r}")
        if real == value:
            problems.append(f"{type_id}: the customer's notation was restored "
                            f"instead of the agent's: {real!r}")
        if " " not in real:
            problems.append(f"{type_id}: the agent's grouping was dropped: {real!r}")
    check("the agent's notation is preserved on the way back", not problems,
          "; ".join(problems) if problems else f"{len(cases)} groupings")


def test_token_shapes_v6() -> None:
    """THE LOAD-BEARING INVARIANT, extended to the family. `unmask_text` finds
    tokens by SHAPE, so a minted shape that escapes `token_re` is a substitute
    that never resolves — a FAKE in the customer's tool with a 200. VIN was not
    in the v5 shape list at all, which is exactly how this failure looks."""
    samples = {
        "BANK_ACCOUNT": ("ACCOUNT", "40817810899910004312"),
        "OGRNIP": ("OGRN", VALID["OGRNIP"]),
        "OMS_ENP": ("OMS", VALID["OMS_ENP"]),
        "IBAN": ("IBAN", VALID["IBAN"]),
        "LOAN_UID": ("LOAN_UID", VALID["LOAN_UID"]),
        "EPTS_NUMBER": ("EPTS", VALID["EPTS_NUMBER"]),
        "UIN": ("UIN", VALID["UIN"]),
        "IMEI": ("IMEI", VALID["IMEI"]),
        "ICCID": ("ICCID", VALID["ICCID"]),
        "LOYALTY_CARD_NUMBER": ("LOYALTY", VALID["LOYALTY_CARD_NUMBER"]),
        "VIN": ("VIN", VALID["VIN"]),
    }
    problems: list[str] = []
    for type_id, (label, original) in samples.items():
        vault = _vault()
        for _ in range(50):
            token = vault.tokenize(original, label)
            if not token_re().fullmatch(token):
                problems.append(f"{type_id}: {token!r} escapes token_re")
                break
    check("every minted v6 token is matched by token_re in full", not problems,
          "; ".join(problems) if problems else f"{len(samples)} types x50 samples")


def test_unresolved_substitute_is_named() -> None:
    """`residual_tokens`/`surviving_substitutes`: a substitute this run minted
    that is still standing after restoration must be NAMED, not trusted
    silently. The only way to name it is for the token SHAPE to be a candidate
    the restorer looked at — which is why the shapes live next to the minters."""
    detector = Detector()
    problems: list[str] = []
    for cue, type_id, value in (("IBAN ", "IBAN", VALID["IBAN"]),
                                ("IMEI ", "IMEI", VALID["IMEI"]),
                                ("УИД ", "LOAN_UID", VALID["LOAN_UID"])):
        vault = _vault()
        text = cue + value
        masked = mask_text(text, vault, detector.detect(text))
        fake = masked[len(cue):]
        if not token_re().fullmatch(fake):
            problems.append(f"{type_id}: the minted shape is not a restorer "
                            f"candidate ({fake!r})")
            continue
        # Nothing resolved (the agent rewrote the substitute into something the
        # vault cannot answer for) — the leftover must be named.
        seen = surviving_substitutes(masked, masked, vault, for_tool=False)
        if fake not in seen:
            problems.append(f"{type_id}: leftover {fake!r} not named ({seen})")
    check("an unresolved substitute is reported as a residual", not problems,
          "; ".join(problems) if problems else "3 types")


# ======================= N1 identity family (eight document types) ============
#
# The registry's eight records with `generated_checksum == ""`. There is no
# arithmetic to inherit here, so the mechanism under test is the OTHER half of the
# delegation: GRAMMAR + TYPED CONTEXT -> recognition, format-preserving mint,
# notation on both legs, restore, residual. Three of the eight carry
# `grammar_status == "ГРАММАТИКА?"` and their shape is recorded as
# GRAMMAR_UNASSERTED — a conservative cue/key-anchored rule, never an invented
# validator.

# (type_id, engine label, text, value that must be typed)
IDENTITY_CASED: list[tuple[str, str, str, str]] = [
    ("INTL_PASSPORT", "INTL_PASSPORT", "загранпаспорт 75 1234567", "75 1234567"),
    ("INTL_PASSPORT", "INTL_PASSPORT", "биометрический паспорт 75-1234567",
     "75-1234567"),
    ("INTL_PASSPORT", "INTL_PASSPORT", '{"intl_passport": "750123456"}',
     "750123456"),
    ("BIRTH_CERT", "BIRTH_CERT", "свидетельство о рождении IV-МЮ № 123456",
     "IV-МЮ № 123456"),
    ("BIRTH_CERT", "BIRTH_CERT", "СОР II-АГ №123456", "II-АГ №123456"),
    ("BIRTH_CERT", "BIRTH_CERT", '{"birth_cert_number": "IV-МЮ № 123456"}',
     "IV-МЮ № 123456"),
    ("CIVIL_ACT_CERT", "BIRTH_CERT", "свидетельство о браке I-АГ № 672731",
     "I-АГ № 672731"),
    ("CIVIL_ACT_CERT", "BIRTH_CERT", "о расторжении брака II-БЮ № 123456",
     "II-БЮ № 123456"),
    ("CIVIL_ACT_CERT", "BIRTH_CERT", "свидетельство о смерти IV-ХХ № 123456",
     "IV-ХХ № 123456"),
    ("CIVIL_ACT_CERT", "BIRTH_CERT",
     '{"marriage_certificate": "I-АГ № 672731"}', "I-АГ № 672731"),
    ("RESIDENCE_PERMIT", "RESIDENCE_PERMIT", "вид на жительство 82 1234567",
     "82 1234567"),
    ("RESIDENCE_PERMIT", "RESIDENCE_PERMIT", "ВНЖ 82.1234567", "82.1234567"),
    ("RESIDENCE_PERMIT", "RESIDENCE_PERMIT", '{"vnzh": "831234567"}',
     "831234567"),
    ("MILITARY_ID", "MILITARY_ID", "военный билет АК № 1234567", "АК № 1234567"),
    ("MILITARY_ID", "MILITARY_ID", '{"military_id": "АК1234567"}', "АК1234567"),
    ("DRIVER_LICENSE", "DRIVER_LICENSE", "вод. удостоверение 99 12 345678",
     "99 12 345678"),
    ("DRIVER_LICENSE", "DRIVER_LICENSE",
     '{"driver_license": "99 12 345678"}', "99 12 345678"),
    ("PTS_NUMBER", "PTS_NUMBER", "ПТС 77 УК 123456", "77 УК 123456"),
    ("PTS_NUMBER", "PTS_NUMBER", "паспорт транспортного средства 77-УК-123456",
     "77-УК-123456"),
    ("PTS_NUMBER", "PTS_NUMBER", '{"pts_number": "77УК123456"}', "77УК123456"),
    ("STS_NUMBER", "STS_NUMBER", "СТС 77 12 345678", "77 12 345678"),
    ("STS_NUMBER", "STS_NUMBER", "СТС 77-12-345678", "77-12-345678"),
    ("STS_NUMBER", "STS_NUMBER", '{"sts_number": "7712 345678"}',
     "7712 345678"),
]

# One source per engine label, for the mint's own properties.
IDENTITY_MINT_SOURCES: list[tuple[str, str]] = [
    ("INTL_PASSPORT", "75 1234567"),
    ("INTL_PASSPORT", "751234567"),
    ("BIRTH_CERT", "IV-МЮ № 123456"),
    ("BIRTH_CERT", "I-АГ №672731"),
    ("MILITARY_ID", "АК № 1234567"),
    ("MILITARY_ID", "AK1234567"),
    ("RESIDENCE_PERMIT", "82 1234567"),
    ("RESIDENCE_PERMIT", "831234567"),
    ("DRIVER_LICENSE", "99 12 345678"),
    ("VEHICLE_DOC", "77 УК 123456"),
    ("VEHICLE_DOC", "77 12 345678"),
]

# Per-type facts the registry states, asserted rather than assumed.
IDENTITY_ROMAN = ("I", "V", "X", "L", "C", "D", "M")


def _alnum(value: str) -> str:
    return "".join(char for char in value if char.isalnum())


def _class_of(char: str) -> str:
    return "d" if char.isdigit() else "a"


def test_identity_grammar_unasserted_is_recorded() -> None:
    """THE THREE `ГРАММАТИКА?` TYPES ARE RECORDED, NOT PAPERED OVER.

    Приказ Минюста 167 (the composition of a certificate's series) was not
    obtained, so BIRTH_CERT / CIVIL_ACT_CERT / RESIDENCE_PERMIT keep a
    conservative cue/key-anchored shape and the module says so in one named
    constant. The other five are `ГОТОВ`. Nothing here is a checksum: the registry
    gives these eight `generated_checksum == ""`, and no validator may be invented
    for them — `mint_identity` must be total over junk instead of raising."""
    problems: list[str] = []
    if len(v6.IDENTITY_TYPES) != 8:
        problems.append(f"{len(v6.IDENTITY_TYPES)} identity types, expected 8")
    if v6.GRAMMAR_UNASSERTED != frozenset(
            ("BIRTH_CERT", "CIVIL_ACT_CERT", "RESIDENCE_PERMIT")):
        problems.append(f"GRAMMAR_UNASSERTED is {sorted(v6.GRAMMAR_UNASSERTED)}")
    for type_id in v6.IDENTITY_TYPES:
        if hasattr(v6, f"validate_{type_id.lower()}"):
            problems.append(f"{type_id}: an invented validator exists")
    for junk in ("", "   ", "абв", "0", "-", "№", "х" * 40, "?!№"):
        for type_id in v6.IDENTITY_TYPES:
            fake = v6.mint_identity(v6.IDENTITY_LABEL[type_id], junk)
            if not fake:
                problems.append(f"{type_id}: total mint returned nothing for {junk!r}")
    check("the grammar-uncertain types are named and no validator is invented",
          not problems, "; ".join(problems) if problems else "8 types, 3 unasserted")


def test_identity_cued_and_keyed(detector: Detector) -> None:
    """Cue context and field-key context both type the value, on the REAL pipeline
    (`Detector.detect`), with the engine label the registry names."""
    problems: list[str] = []
    for type_id, label, text, value in IDENTITY_CASED:
        if not _found(detector, text, label, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    check("identity documents are recognized by cue and by field key",
          not problems, "; ".join(problems) if problems else f"{len(IDENTITY_CASED)} texts")


def test_identity_typed_invalid_no_gate() -> None:
    """COV-TYPED-INVALID FOR A GRAMMAR TYPE. There is no checksum to reject a
    mistyped document, and the cue is the evidence: «СТС 00 00 000000» behind its
    own cue is still the customer's certificate. The mechanism must not grow a
    validator that would send it to the model in the clear."""
    detector = Detector()
    negatives = [
        ("СТС 00 00 000000", "STS_NUMBER"),
        ("ВНЖ 82 0000000", "RESIDENCE_PERMIT"),
        ("военный билет ХХ № 0000000", "MILITARY_ID"),
        ("свидетельство о браке I-АА № 000000", "BIRTH_CERT"),
        ("ПТС 00 ХХ 000000", "PTS_NUMBER"),
    ]
    problems = [text for text, label in negatives
                if not any(span.entity_type == label for span in detector.detect(text))]
    check("a document with junk content behind its cue is still protected",
          not problems, "; ".join(problems) if problems else f"{len(negatives)} negatives")


def test_identity_bare_is_not_typed(detector: Detector) -> None:
    """`bare_typed=False` on all eight records: a bare value is NOT typed by this
    family. The two documented exceptions are asserted POSITIVELY so they cannot
    be mistaken for the rule: a bare BIRTH_CERT shape is typed by the v5 bare
    recognizer (`COV-INTEGRATION-KEEP-V5`), and a bare ПТС shape is read as a
    PLATE — masked, but not as a document."""
    problems: list[str] = []
    bare_negatives = [
        ("82 1234567", "RESIDENCE_PERMIT"),
        ("АК № 1234567", "MILITARY_ID"),
        ("77 УК 123456", "VEHICLE_DOC"),
        ("75 1234567", "INTL_PASSPORT"),
        ("99 12 345678", "DRIVER_LICENSE"),
    ]
    for value, label in bare_negatives:
        text = f"значение {value} конец"
        if any(span.entity_type == label for span in detector.detect(text)):
            problems.append(f"{label}: bare {value!r} was typed")
    # …and the exceptions, stated rather than hidden:
    if not _found(detector, "значение IV-МЮ № 123456 конец", "BIRTH_CERT",
                  "IV-МЮ № 123456"):
        problems.append("BIRTH_CERT: the kept v5 bare recognizer stopped working")
    check("a bare document number is not typed by the identity family",
          not problems, "; ".join(problems) if problems else "5 negatives + 1 kept v5")


def test_identity_mint_is_format_preserving() -> None:
    """THE FORMAT IS THE WHOLE PROMISE OF THIS FAMILY. There is no checksum to
    inherit, so what must be preserved is the shape: the number of alphanumeric
    characters, the CLASS of each one (digit stays digit, letter stays letter), the
    separators and the letter case. Four facts the registry states are asserted
    separately: a certificate's leading group is a ROMAN numeral of the same
    length, a ВНЖ's series is 82/83, a ПТС keeps letters and a СТС keeps none."""
    problems: list[str] = []
    for label, source in IDENTITY_MINT_SOURCES:
        for _ in range(50):
            fake = v6.mint_identity(label, source)
            if fake == source:
                problems.append(f"{label}: substitute equals the source")
                break
            if _alnum(fake) != _alnum(fake):
                break
            if [_class_of(char) for char in _alnum(fake)] != \
                    [_class_of(char) for char in _alnum(source)]:
                problems.append(f"{label}: character classes changed "
                                f"{source!r} -> {fake!r}")
                break
            if [char for char in fake if not char.isalnum()] != \
                    [char for char in source if not char.isalnum()]:
                problems.append(f"{label}: separators changed "
                                f"{source!r} -> {fake!r}")
                break
            if len(_alnum(fake)) != len(_alnum(source)):
                problems.append(f"{label}: length changed "
                                f"{len(_alnum(source))} -> {len(_alnum(fake))}")
                break
            if label == "RESIDENCE_PERMIT" and _alnum(fake)[:2] not in ("82", "83"):
                problems.append(f"{label}: series left the grammar: {fake!r}")
                break
            if label == "BIRTH_CERT":
                # The leading group is a ROMAN numeral of the SAME LENGTH. Read it
                # off the raw spellings: `_alnum` has already dropped the hyphen.
                head = source.split("-", 1)[0]
                fake_head = fake.split("-", 1)[0]
                if len(fake_head) != len(head) or not all(
                        char in IDENTITY_ROMAN for char in fake_head):
                    problems.append(f"{label}: series is not a same-length Roman "
                                    f"numeral {source!r} -> {fake!r}")
                    break
    check("an identity substitute keeps classes, separators and case",
          not problems, "; ".join(problems) if problems
          else f"{len(IDENTITY_MINT_SOURCES)} sources x50")


def test_identity_roundtrip_three_legs() -> None:
    """The real document comes back on every OUT shape the product has: prose, a
    tool argument that must still parse, and a streamed chunk. A substitute that
    fails to resolve is a FAKE in the customer's tool with a 200."""
    detector = Detector()
    problems: list[str] = []
    for type_id, label, text, value in IDENTITY_CASED:
        if text.startswith("{"):
            continue
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{type_id}: value still standing in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{type_id}: {value!r} did not return from {masked!r}")
    payload = json.dumps({"pts": "77 УК 123456", "vnzh": "82 1234567",
                          "military_id": "АК № 1234567",
                          "birth_cert": "IV-МЮ № 123456"}, ensure_ascii=False)
    vault = _vault()
    masked = mask_text(payload, vault, detector.detect(payload))
    opened = unmask_arguments(masked, vault)
    for value in ("77 УК 123456", "82 1234567", "АК № 1234567", "IV-МЮ № 123456"):
        if value not in opened:
            problems.append(f"argument leg lost {value!r}: {masked!r} -> {opened!r}")
    if not json.loads(opened):
        problems.append(f"argument leg is not JSON after restore: {opened!r}")
    chunk_text = "военный билет АК № 1234567"
    vault = _vault()
    masked = mask_text(chunk_text, vault, detector.detect(chunk_text))
    from pseudex.redact import unmask_stream_chunk
    emitted, carry = unmask_stream_chunk(masked, "", vault, flush=True)
    if "АК № 1234567" not in emitted + carry:
        problems.append(f"stream leg lost the value: {emitted + carry!r}")
    check("identity documents restore on prose, tool arguments and streams",
          not problems, "; ".join(problems) if problems else "3 legs")


def test_identity_notation_both_legs() -> None:
    """P02 / «explicit agent form». The notation belongs to whoever wrote the
    mention: the CUSTOMER's separators are mirrored onto the substitute on the way
    in, and the AGENT's regrouping is mirrored onto the real value on the way
    back. Content never changes."""
    detector = Detector()
    problems: list[str] = []
    for text, value in (("загранпаспорт 75-1234567", "75-1234567"),
                        ("СТС 7712-345678", "7712-345678"),
                        ("ВНЖ 82.1234567", "82.1234567")):
        vault = _vault()
        spans = detector.detect(text)
        if len(spans) != 1:
            problems.append(f"{text!r}: {len(spans)} spans, expected 1")
            continue
        span = spans[0]
        masked = mask_text(text, vault, spans)
        # The span's own offsets, not a split on the first space: a cue is a phrase.
        fake = masked[span.start:span.end]
        if [char for char in fake if not char.isalnum()] != \
                [char for char in value if not char.isalnum()]:
            problems.append(f"IN: the customer's separators were not mirrored "
                            f"({value!r} -> {fake!r})")
            continue
        # The agent regroups the substitute into THREE characters, a separator,
        # then the rest; the real digits must come back in THAT grouping.
        digits = _alnum(fake)
        regrouped = digits[:3] + "-" + digits[3:]
        rewritten = text[:span.start] + regrouped + text[span.end:]
        restored = unmask_text(rewritten, vault)
        real = restored[span.start:span.start + len(regrouped)]
        if _alnum(real) != _alnum(value):
            problems.append(f"OUT: content lost for {value!r}: {restored!r}")
        elif real == value:
            problems.append(f"OUT: the customer's notation was restored instead "
                            f"of the agent's ({real!r})")
        elif real[3] != "-":
            problems.append(f"OUT: the agent's grouping was dropped ({real!r})")
    check("the customer's notation comes in and the agent's goes out",
          not problems, "; ".join(problems) if problems else "3 documents")


def test_identity_token_shapes() -> None:
    """`unmask_text` finds tokens by SHAPE, so a minted shape that escapes
    `token_re` is a substitute that never resolves — a FAKE in the customer's tool
    with a 200. This family's shapes are minted and matched from one tuple, and
    the spaced INTL_PASSPORT the v5 list could not see is the witness."""
    problems: list[str] = []
    for label, source in IDENTITY_MINT_SOURCES:
        vault = _vault()
        for _ in range(50):
            token = vault.tokenize(source, label)
            if not token_re().fullmatch(token):
                problems.append(f"{label}: {token!r} escapes token_re")
                break
    check("every minted identity token is matched by token_re in full",
          not problems, "; ".join(problems) if problems
          else f"{len(IDENTITY_MINT_SOURCES)} sources x50 samples")


def test_identity_same_digits_are_not_one_document() -> None:
    """A DIGIT-ONLY SIGNATURE WOULD LET TWO ПТС ANSWER FOR EACH OTHER. «77 УК
    123456» and «77 ХК 123456» share every digit; a signature that dropped the
    letters would key them to one row, and the customer's tool would receive the
    other car's document. The registry's own `value_notation` for ПТС is
    "glyph_fold" — letters included."""
    detector = Detector()
    vault = _vault()
    problems: list[str] = []
    first, second = "ПТС 77 УК 123456", "ПТС 77 ХК 123456"
    masked_first = mask_text(first, vault, detector.detect(first))
    masked_second = mask_text(second, vault, detector.detect(second))
    if masked_first == masked_second:
        problems.append("two documents with the same digits share one substitute")
    if unmask_text(masked_first, vault) != first:
        problems.append(f"the first document came back wrong: "
                        f"{unmask_text(masked_first, vault)!r}")
    if unmask_text(masked_second, vault) != second:
        problems.append(f"the second document came back wrong: "
                        f"{unmask_text(masked_second, vault)!r}")
    check("two document numbers that share a digit run stay two documents",
          not problems, "; ".join(problems) if problems else "2 ПТС, 2 rows")


def test_identity_reformatted_substitute_resolves() -> None:
    """THE SECOND LINE OF DEFENCE. A model that rewrites our substitute — drops the
    separators, changes the case — no longer matches its minted shape, and the
    fake then reaches the tool. The identity signature (content, letters included,
    LABEL in the key) resolves it, exactly as the plate signature does."""
    problems: list[str] = []
    for label, value in (("VEHICLE_DOC", "77 УК 123456"),
                         ("MILITARY_ID", "АК № 1234567"),
                         ("BIRTH_CERT", "IV-МЮ № 123456"),
                         ("INTL_PASSPORT", "75 1234567")):
        vault = _vault()
        fake = vault.tokenize(value, label)
        squeezed = _alnum(fake)
        restored = unmask_text(f"номер {squeezed}", vault)
        if _alnum(value) not in _alnum(restored):
            problems.append(f"{value!r}: squeezed substitute {squeezed!r} did not "
                            f"resolve ({restored!r})")
    check("a substitute the agent reformatted still resolves", not problems,
          "; ".join(problems) if problems else "4 documents")


def test_identity_no_fuzzy_numerals() -> None:
    """NO FUZZY MATCHING REACHES AN IDENTIFIER. The engine mines one-edit typos for
    NAMES; a document number one digit away from another is a DIFFERENT document,
    not a typo of the first. Restoring the neighbour's real value under the agent's
    bent substitute would name a person who was never in the dialogue."""
    detector = Detector()
    problems: list[str] = []
    for text, value in (("ВНЖ 82 1234567", "82 1234567"),
                        ("загранпаспорт 75 1234567", "75 1234567"),
                        ("СТС 77 12 345678", "77 12 345678")):
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        head = text.split(" ", 1)[0]
        fake = masked[len(head) + 1:]
        digits = re.sub(r"\D", "", fake)
        bent = digits[:-1] + ("0" if digits[-1] != "0" else "1")
        restored = unmask_text(f"{head} {bent}", vault)
        if re.sub(r"\D", "", value) in re.sub(r"\D", "", restored):
            problems.append(f"{value!r}: a one-digit variant resolved to the real "
                            f"document ({restored!r})")
    check("a one-digit change is a different document, not a typo",
          not problems, "; ".join(problems) if problems else "3 documents")


def test_identity_unresolved_substitute_is_named() -> None:
    """A substitute this run minted that is still standing after restoration must
    be NAMED, not trusted silently. Only a token the restorer looked at can be
    named, which is why the shapes live next to the minters."""
    problems: list[str] = []
    for label, value in (("VEHICLE_DOC", "77 УК 123456"),
                         ("MILITARY_ID", "АК № 1234567"),
                         ("RESIDENCE_PERMIT", "82 1234567"),
                         ("INTL_PASSPORT", "75 1234567")):
        vault = _vault()
        fake = vault.tokenize(value, label)
        text = f"номер {fake}"
        if not token_re().fullmatch(fake):
            problems.append(f"{label}: the minted shape is not a restorer "
                            f"candidate ({fake!r})")
            continue
        # Nothing resolved — the agent rewrote the substitute into a string the
        # vault cannot answer for — so the leftover must be named.
        seen = surviving_substitutes(text, text, vault, for_tool=False)
        if fake not in seen:
            problems.append(f"{label}: leftover {fake!r} not named ({seen})")
    check("an unresolved identity substitute is reported as a residual",
          not problems, "; ".join(problems) if problems else "4 documents")


def test_identity_no_overmask() -> None:
    """THE CUE IS THE EVIDENCE, AND A WORD ALONE IS NOT A NUMBER. These sentences
    name the document kind without carrying one, and the family must leave them
    untouched — over-masking is the failure the customer sees first."""
    detector = Detector()
    negatives = [
        "протокол о расторжении брака № 12345/2026",
        "свидетельство о поверке № 1234",
        "ПТС образца 2020 года",
        "вид на жительство оформляется 5 лет",
        "военный билет выдан в 2015 году",
        "паспорт транспортного средства утерян",
        "СТС на автомобиль переоформлен",
        "загранпаспорт действителен до 2030 года",
    ]
    problems = [text for text in negatives if detector.detect(text)]
    check("a document kind named without a number is not masked", not problems,
          "; ".join(problems) if problems else f"{len(negatives)} negatives")


def test_identity_labels_follow_the_registry() -> None:
    """THE LABEL IS THE ENGINE'S NAME FOR A TYPE, and five of the eight already had
    one (`engine_labels`). Two label facts are asserted rather than assumed: ПТС
    and СТС are the SAME engine label VEHICLE_DOC (the registry says so, and the
    mint tells them apart by the source's own letters), and CIVIL_ACT_CERT shares
    BIRTH_CERT until the Lead's priority entry can split them (DELTA.json carries
    the handoff)."""
    problems: list[str] = []
    expected = {
        "INTL_PASSPORT": "INTL_PASSPORT",
        "BIRTH_CERT": "BIRTH_CERT",
        "CIVIL_ACT_CERT": "BIRTH_CERT",
        "RESIDENCE_PERMIT": "RESIDENCE_PERMIT",
        "MILITARY_ID": "MILITARY_ID",
        "DRIVER_LICENSE": "DRIVER_LICENSE",
        "PTS_NUMBER": "VEHICLE_DOC",
        "STS_NUMBER": "VEHICLE_DOC",
    }
    for type_id, label in expected.items():
        if v6.IDENTITY_LABEL.get(type_id) != label:
            problems.append(f"{type_id}: label {v6.IDENTITY_LABEL.get(type_id)!r}, "
                            f"expected {label!r}")
    if set(v6.LABEL_IDENTITY_TYPES["VEHICLE_DOC"]) != {"PTS_NUMBER", "STS_NUMBER"}:
        problems.append("VEHICLE_DOC does not cover exactly ПТС and СТС")
    check("the engine label of each identity type is the registry's",
          not problems, "; ".join(problems) if problems else "8 types")


# ======================= N1 legal family (six court/legal types) ==============
#
# The registry's six legal records with `generated_checksum == ""`. The mechanism
# is GRAMMAR + TYPED CONTEXT and nothing else, one of the six carries
# `grammar_status == "ГРАММАТИКА?"`, and ALL SIX are `bare_typed=False` — so the
# cue or the field key is the whole evidence and no bare anchor exists.

# (engine label, text, value that must be typed with that label)
LEGAL_CASED: list[tuple[str, str, str]] = [
    ("COURT_CASE_UID", "УИД 77OS0000-02-2026-000001-52",
     "77OS0000-02-2026-000001-52"),
    ("COURT_CASE_UID", "уникальный идентификатор дела 77RS0000-01-2025-000123-11",
     "77RS0000-01-2025-000123-11"),
    # The registry's own FORM pair: a УИД typed with the Cyrillic twins is the
    # SAME case as the Latin one (`value_notation: glyph_fold`).
    ("COURT_CASE_UID", "УИД 77ОС0000-02-2026-000001-52",
     "77ОС0000-02-2026-000001-52"),
    ("COURT_CASE_UID", '{"case_uid": "77OS0000-02-2026-000001-52"}',
     "77OS0000-02-2026-000001-52"),
    ("ARBITRAZH_CASE_NO", "по делу А31-2840/2013", "А31-2840/2013"),
    ("ARBITRAZH_CASE_NO", "арбитражное дело А40-123456/2024", "А40-123456/2024"),
    ("ARBITRAZH_CASE_NO", "дело о банкротстве А56-12345-1/2023",
     "А56-12345-1/2023"),
    ("ARBITRAZH_CASE_NO", "по делу 12АП-3456/2024", "12АП-3456/2024"),
    ("ARBITRAZH_CASE_NO", "по делу Ф07-1234/2025", "Ф07-1234/2025"),
    ("ARBITRAZH_CASE_NO", "по делу С01-1234/2024", "С01-1234/2024"),
    ("ARBITRAZH_CASE_NO", '{"arbitrcase": "А31-2840/2013"}', "А31-2840/2013"),
    ("COURT_CASE_NO_SOU", "гражданское дело 2-13/2015", "2-13/2015"),
    ("COURT_CASE_NO_SOU", "по делу М-1234/2024", "М-1234/2024"),
    ("COURT_CASE_NO_SOU", "судебный приказ 2а-456/2026", "2а-456/2026"),
    ("COURT_CASE_NO_SOU", '{"case_number": "2-13/2015"}', "2-13/2015"),
    ("FSSP_IP_NO", "ИП № 1234567/25/77001-ИП", "1234567/25/77001-ИП"),
    ("FSSP_IP_NO", "исполнительное производство 12345/24/77001-СД",
     "12345/24/77001-СД"),
    ("FSSP_IP_NO", "исполнительное производство 12/34/56/78", "12/34/56/78"),
    ("FSSP_IP_NO", '{"fssp_ip": "1234567/25/77001-ИП"}', "1234567/25/77001-ИП"),
    ("EXEC_DOC_NO", "исполнительный лист ФС 012345678", "ФС 012345678"),
    ("EXEC_DOC_NO", "серия ФС 123456789", "ФС 123456789"),
    ("EXEC_DOC_NO", '{"exec_list_number": "ФС 012345678"}', "ФС 012345678"),
    ("CADASTRAL_NUMBER", "кадастровый номер 77:01:0001001:1234",
     "77:01:0001001:1234"),
    ("CADASTRAL_NUMBER", "КН 50:20:0010203:5", "50:20:0010203:5"),
    ("CADASTRAL_NUMBER", '{"cadastral_number": "77:01:0001001:1234"}',
     "77:01:0001001:1234"),
]

# One source per registry type, in the spellings the six grammars allow.
LEGAL_MINT_SOURCES: list[tuple[str, str]] = [
    ("COURT_CASE_UID", "77OS0000-02-2026-000001-52"),
    ("COURT_CASE_UID", "77ОС0000-02-2026-000001-52"),
    ("COURT_CASE_UID", "77os0000-02-2026-000001-52"),
    ("ARBITRAZH_CASE_NO", "А31-2840/2013"),
    ("ARBITRAZH_CASE_NO", "А56-12345-1/2023"),
    ("ARBITRAZH_CASE_NO", "12АП-3456/2024"),
    ("ARBITRAZH_CASE_NO", "Ф07-1234/2025"),
    ("ARBITRAZH_CASE_NO", "С01-1234/2024"),
    ("ARBITRAZH_CASE_NO", "A31-2840/2013"),
    ("COURT_CASE_NO_SOU", "2-13/2015"),
    ("COURT_CASE_NO_SOU", "2а-456/2026"),
    ("COURT_CASE_NO_SOU", "М-1234/2024"),
    ("FSSP_IP_NO", "1234567/25/77001-ИП"),
    ("FSSP_IP_NO", "12345/24/77001-СД"),
    ("FSSP_IP_NO", "12/34/56/78"),
    ("EXEC_DOC_NO", "ФС 012345678"),
    ("EXEC_DOC_NO", "АБ №123456789"),
    ("EXEC_DOC_NO", "фс012345678"),
    ("CADASTRAL_NUMBER", "77:01:0001001:1234"),
    ("CADASTRAL_NUMBER", "50:20:0010203:5"),
    ("CADASTRAL_NUMBER", "77 01 0001001 1234"),
]

# Bare shapes. The registry gives every one of the six `bare_typed=False`, so the
# shape alone types NOTHING — and a bare cadastral or case number is exactly the
# over-masking a table of ordinary numbers would collect.
LEGAL_BARE: tuple[str, ...] = (
    "77:01:0001001:1234",
    "А31-2840/2013",
    "77OS0000-02-2026-000001-52",
    "1234567/25/77001-ИП",
    "ФС 012345678",
    "2-13/2015",
)

# A cue is not a number. None of these carries a shape, and the family must
# leave every one of them alone.
LEGAL_NEGATIVES: tuple[str, ...] = (
    "дело № 12345/2026",
    "кадастровый номер уточняется",
    "исполнительное производство не возбуждалось",
    "исполнительный лист утерян",
    "дело рассмотрено в 2024 году",
    "судебный приказ отменён",
    "по делу вынесено решение",
    "серия документа не указана",
    "номер дела уточните в канцелярии",
    "ИП Иванов зарегистрирован в 2020 году",
)


def test_legal_grammar_unasserted_is_recorded() -> None:
    """THE ONE `ГРАММАТИКА?` TYPE IS RECORDED, NOT PAPERED OVER.

    EXEC_DOC_NO's series composition was not asserted (ПП № 579 describes the
    blank), so its shape is the registry's grammar verbatim and the module names
    it in one constant. None of the six carries a checksum, so no validator may
    be invented for any of them — and `mint_legal` must be total over junk rather
    than raising, because a renderer that raises is a 5xx on the masking path."""
    problems: list[str] = []
    if len(v6.LEGAL_TYPES) != 6:
        problems.append(f"{len(v6.LEGAL_TYPES)} legal types, expected 6")
    if v6.LEGAL_GRAMMAR_UNASSERTED != frozenset(("EXEC_DOC_NO",)):
        problems.append(f"LEGAL_GRAMMAR_UNASSERTED is "
                        f"{sorted(v6.LEGAL_GRAMMAR_UNASSERTED)}")
    for type_id in v6.LEGAL_TYPES:
        if hasattr(v6, f"validate_{type_id.lower()}"):
            problems.append(f"{type_id}: an invented validator exists")
    for junk in ("", "   ", "абв", "0", "-", "№", "х" * 40, "?!№", "нет данных"):
        for type_id in v6.LEGAL_TYPES:
            fake = v6.mint_legal(v6.LEGAL_LABEL[type_id], junk)
            if not fake:
                problems.append(f"{type_id}: total mint returned nothing for "
                                f"{junk!r}")
    check("the grammar-uncertain legal type is named and no validator is invented",
          not problems, "; ".join(problems) if problems else "6 types, 1 unasserted")


def test_legal_cued_and_keyed(detector: Detector) -> None:
    """Cue context and field-key context both type the value, on the REAL pipeline
    (`Detector.detect`), with the engine label the registry names."""
    problems: list[str] = []
    for label, text, value in LEGAL_CASED:
        if not _found(detector, text, label, value):
            problems.append(f"{label}: {text!r} -> {_types_found(detector, text)}")
    check("legal identifiers are recognized by cue and by field key",
          not problems, "; ".join(problems) if problems else f"{len(LEGAL_CASED)} texts")


def test_legal_typed_invalid_no_gate(detector: Detector) -> None:
    """COV-TYPED-INVALID FOR A GRAMMAR TYPE. There is no checksum to reject an
    implausible case number, and the cue is the evidence: a region «00», a year
    «0000» or a court code no court uses is still the customer's identifier and
    must be protected rather than corrected."""
    problems: list[str] = []
    for label, text, value in (
            ("COURT_CASE_UID", "УИД 00ZZ0000-00-0000-000000-00",
             "00ZZ0000-00-0000-000000-00"),
            ("ARBITRAZH_CASE_NO", "по делу А00-0/0000", "А00-0/0000"),
            ("FSSP_IP_NO", "ИП № 0/00/00000-ИП", "0/00/00000-ИП"),
            ("CADASTRAL_NUMBER", "кадастровый номер 00:00:000000:0",
             "00:00:000000:0")):
        if not _found(detector, text, label, value):
            problems.append(f"{label}: {text!r} -> {_types_found(detector, text)}")
    check("an implausible legal number behind its cue is still protected",
          not problems, "; ".join(problems) if problems else "4 negatives")


def test_legal_bare_is_not_typed(detector: Detector) -> None:
    """`bare_typed=False` ON ALL SIX, ASSERTED RATHER THAN ASSUMED. A bare shape
    types nothing: the colon form is an ordinary table cell, the case number is a
    fraction, and claiming either would buy recall with other people's data."""
    problems = [text for text in LEGAL_BARE
                if any(span.entity_type in v6.LEGAL_LABELS
                       for span in detector.detect(text))]
    check("a bare legal shape is not typed by this family", not problems,
          "; ".join(problems) if problems else f"{len(LEGAL_BARE)} bare shapes")


def test_legal_mint_is_format_preserving() -> None:
    """THE SUBSTITUTE KEEPS THE SOURCE'S FORMAT EXACTLY: separator layout,
    character classes, digit count, letter case and script — and the digits the
    GRAMMAR pins (the СИП «С01») stay. There is no checksum to inherit, so format
    is the whole contract, and a fake of the wrong shape is a value the customer's
    own validator refuses."""
    problems: list[str] = []
    for label, source in LEGAL_MINT_SOURCES:
        for _ in range(50):
            fake = v6.mint_legal(label, source)
            if fake == source:
                problems.append(f"{label}: the fake equals the source {source!r}")
                break
            if [c for c in fake if not c.isalnum()] != \
                    [c for c in source if not c.isalnum()]:
                problems.append(f"{label}: separators changed {source!r} -> {fake!r}")
                break
            if [c.isdigit() for c in fake] != [c.isdigit() for c in source]:
                problems.append(f"{label}: classes changed {source!r} -> {fake!r}")
                break
            if [c.isupper() for c in fake if c.isalpha()] != \
                    [c.isupper() for c in source if c.isalpha()]:
                problems.append(f"{label}: case changed {source!r} -> {fake!r}")
                break
            if [c.isascii() for c in fake if c.isalpha()] != \
                    [c.isascii() for c in source if c.isalpha()]:
                problems.append(f"{label}: script changed {source!r} -> {fake!r}")
                break
            resolved = v6.legal_label_for_source(source, label)
            if not v6.LEGAL_SHAPES[resolved].fullmatch(fake):
                problems.append(f"{label}: {fake!r} is not its own shape "
                                f"({source!r})")
                break
    for _ in range(100):
        fake = v6.mint_legal("ARBITRAZH_CASE_NO", "С01-1234/2024")
        if not fake.startswith(("С01", "C01")):
            problems.append(f"СИП pinned digits lost: {fake!r}")
            break
    check("a legal substitute keeps classes, separators, case and script",
          not problems, "; ".join(problems) if problems
          else f"{len(LEGAL_MINT_SOURCES)} sources x50")


def test_legal_roundtrip_three_legs() -> None:
    """The real identifier comes back on every OUT shape the product has: prose, a
    tool argument that must still parse, and a streamed chunk. A substitute that
    fails to resolve is a FAKE in the customer's tool with a 200."""
    detector = Detector()
    problems: list[str] = []
    for label, text, value in LEGAL_CASED:
        if text.startswith("{"):
            continue
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{label}: value still standing in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{label}: {value!r} did not return from {masked!r}")
    payload = json.dumps({"case_uid": "77OS0000-02-2026-000001-52",
                          "case_number": "2-13/2015",
                          "fssp_ip": "1234567/25/77001-ИП",
                          "cadastral_number": "77:01:0001001:1234"},
                         ensure_ascii=False)
    vault = _vault()
    masked = mask_text(payload, vault, detector.detect(payload))
    opened = unmask_arguments(masked, vault)
    for value in ("77OS0000-02-2026-000001-52", "2-13/2015",
                  "1234567/25/77001-ИП", "77:01:0001001:1234"):
        if value not in opened:
            problems.append(f"argument leg lost {value!r}: {masked!r} -> {opened!r}")
    if not json.loads(opened):
        problems.append(f"argument leg is not JSON after restore: {opened!r}")
    # THE CUE-AND-TOKEN WITNESS: a proceeding number written right after «ИП №»
    # puts another family's token shape over the cue and the first group, and the
    # family's own scan is what keeps the round trip whole (see the comment in
    # `redact._restore_tokens_spans`).
    chunk_text = "ИП № 1234567/25/77001-ИП"
    vault = _vault()
    masked = mask_text(chunk_text, vault, detector.detect(chunk_text))
    from pseudex.redact import unmask_stream_chunk
    emitted, carry = unmask_stream_chunk(masked, "", vault, flush=True)
    if "1234567/25/77001-ИП" not in emitted + carry:
        problems.append(f"stream leg lost the value: {emitted + carry!r}")
    check("legal identifiers restore on prose, tool arguments and streams",
          not problems, "; ".join(problems) if problems else "3 legs")


def test_legal_notation_both_legs() -> None:
    """P02. The notation belongs to whoever wrote the mention: the CUSTOMER's
    separators are mirrored onto the substitute on the way in, and the AGENT's
    regrouping is mirrored onto the real value on the way back.

    The regrouping tested is the one the GRAMMAR supports: a cadastral number and
    a УИД both name their separators as a closed class (the registry's
    `form_features`), so an agent that writes «77-01-0001001-1234» or
    «77OS0000 02 2026 000001 52» has chosen a form we can honour. A case number
    whose «-» and «/» are STRUCTURE has no regrouping to honour, and inventing one
    would be re-formatting the value rather than restoring it."""
    detector = Detector()
    problems: list[str] = []
    for text, label, value, source_sep in (
            ("кадастровый номер 77:01:0001001:1234", "CADASTRAL_NUMBER",
             "77:01:0001001:1234", ":"),
            ("УИД 77OS0000-02-2026-000001-52", "COURT_CASE_UID",
             "77OS0000-02-2026-000001-52", "-")):
        vault = _vault()
        spans = [s for s in detector.detect(text) if s.entity_type == label]
        if len(spans) != 1:
            problems.append(f"{text!r}: {len(spans)} spans, expected 1")
            continue
        span = spans[0]
        masked = mask_text(text, vault, spans)
        fake = masked[span.start:span.end]
        if {c for c in fake if not c.isalnum()} != {source_sep}:
            problems.append(f"IN: the customer's separators were not mirrored "
                            f"({value!r} -> {fake!r})")
            continue
        # THE AGENT'S OWN FORM: the same content, the separator the grammar's
        # closed list allows and the customer did not use.
        agent_surface = fake.replace(source_sep, " ")
        rewritten = text[:span.start] + agent_surface + text[span.end:]
        restored = unmask_text(rewritten, vault)
        real = restored[span.start:span.start + len(agent_surface)]
        if _alnum(real) != _alnum(value):
            problems.append(f"OUT: content lost for {value!r}: {restored!r}")
        elif real == value:
            problems.append(f"OUT: the customer's notation was restored instead "
                            f"of the agent's ({real!r})")
        elif " " not in real:
            problems.append(f"OUT: the agent's grouping was dropped ({real!r})")
    check("the customer's legal notation comes in and the agent's goes out",
          not problems, "; ".join(problems) if problems else "2 identifiers")


def test_legal_token_shapes() -> None:
    """`unmask_text` finds tokens by SHAPE, so a minted shape that escapes
    `token_re` is a substitute that never resolves — a FAKE in the customer's tool
    with a 200. The family's shapes are minted and matched from one tuple, and the
    spaced cadastral is the witness the bare-digit list cannot see."""
    problems: list[str] = []
    for label, source in LEGAL_MINT_SOURCES:
        vault = _vault()
        for _ in range(50):
            token = vault.tokenize(source, label)
            if not token_re().fullmatch(token):
                problems.append(f"{label}: {token!r} escapes token_re")
                break
    check("every minted legal token is matched by token_re in full",
          not problems, "; ".join(problems) if problems
          else f"{len(LEGAL_MINT_SOURCES)} sources x50 samples")


def test_legal_reformatted_substitute_resolves() -> None:
    """THE SECOND LINE OF DEFENCE. A model that rewrites our substitute — drops
    the separators, changes the case — no longer matches its minted shape, and the
    fake then reaches the tool. The legal signature (content, letters included,
    the court-case pair keyed by its GROUP) resolves it, exactly as the identity
    signature does. A SQUEEZED CADASTRAL has no letters at all and is resolved by
    the digit signature instead, which is why it is in `vault._NUMERIC_TYPES`."""
    problems: list[str] = []
    for label, value in (("COURT_CASE_UID", "77OS0000-02-2026-000001-52"),
                         ("ARBITRAZH_CASE_NO", "А31-2840/2013"),
                         ("EXEC_DOC_NO", "ФС 012345678"),
                         ("FSSP_IP_NO", "1234567/25/77001-ИП"),
                         ("CADASTRAL_NUMBER", "77:01:0001001:1234")):
        vault = _vault()
        fake = vault.tokenize(value, label)
        squeezed = _alnum(fake)
        restored = unmask_text(f"номер {squeezed}", vault)
        if _alnum(value) not in _alnum(restored):
            problems.append(f"{label}: squeezed substitute {squeezed!r} did not "
                            f"resolve ({restored!r})")
    # AN UPPER-CASED SUBSTITUTE, the other rewriting an agent does.
    vault = _vault()
    fake = vault.tokenize("А31-2840/2013", "ARBITRAZH_CASE_NO")
    restored = unmask_text(f"номер {fake.upper()}", vault)
    if _alnum("А31-2840/2013") not in _alnum(restored):
        problems.append(f"upper-cased substitute did not resolve ({restored!r})")
    check("a substitute the agent reformatted still resolves", not problems,
          "; ".join(problems) if problems else "5 identifiers")


def test_legal_no_fuzzy_numerals() -> None:
    """NO FUZZY MATCHING REACHES A LEGAL NUMBER. A case number one digit away from
    another is a DIFFERENT case, not a typo of the first. Restoring the
    neighbour's real value under the agent's bent substitute would name a
    proceeding that was never in the dialogue."""
    detector = Detector()
    problems: list[str] = []
    for text, label, value in (("гражданское дело 2-13/2015", "COURT_CASE_NO_SOU",
                                "2-13/2015"),
                               ("по делу А31-2840/2013", "ARBITRAZH_CASE_NO",
                                "А31-2840/2013"),
                               ("кадастровый номер 77:01:0001001:1234",
                                "CADASTRAL_NUMBER", "77:01:0001001:1234")):
        vault = _vault()
        spans = [s for s in detector.detect(text) if s.entity_type == label]
        if len(spans) != 1:
            problems.append(f"{label}: {len(spans)} spans in {text!r}, expected 1")
            continue
        masked = mask_text(text, vault, spans)
        span = spans[0]
        fake = masked[span.start:span.end]
        digits = re.sub(r"\D", "", fake)
        bent = digits[:-1] + ("0" if digits[-1] != "0" else "1")
        candidate = _alnum(fake)[:3] + bent[3:] if label != "CADASTRAL_NUMBER" \
            else bent
        restored = unmask_text(f"{text[:span.start]}{candidate}", vault)
        if re.sub(r"\D", "", value) in re.sub(r"\D", "", restored) and \
                re.sub(r"\D", "", value) != re.sub(r"\D", "", candidate):
            problems.append(f"{value!r}: a one-digit variant resolved to the real "
                            f"identifier ({restored!r})")
    check("a one-digit change is a different case, not a typo", not problems,
          "; ".join(problems) if problems else "3 identifiers")


def test_legal_unresolved_substitute_is_named() -> None:
    """A substitute this run minted that is still standing after restoration must
    be NAMED, not trusted silently. Only a token the restorer looked at can be
    named, which is why the shapes live next to the minters."""
    problems: list[str] = []
    for label, value in (("COURT_CASE_UID", "77OS0000-02-2026-000001-52"),
                         ("ARBITRAZH_CASE_NO", "А31-2840/2013"),
                         ("FSSP_IP_NO", "1234567/25/77001-ИП"),
                         ("CADASTRAL_NUMBER", "77:01:0001001:1234")):
        vault = _vault()
        fake = vault.tokenize(value, label)
        text = f"номер {fake}"
        if not token_re().fullmatch(fake):
            problems.append(f"{label}: the minted shape is not a restorer "
                            f"candidate ({fake!r})")
            continue
        seen = surviving_substitutes(text, text, vault, for_tool=False)
        if fake not in seen:
            problems.append(f"{label}: leftover {fake!r} not named ({seen})")
    check("an unresolved legal substitute is reported as a residual",
          not problems, "; ".join(problems) if problems else "4 identifiers")


def test_legal_no_overmask(detector: Detector) -> None:
    """THE CUE IS THE EVIDENCE, AND A WORD ALONE IS NOT A NUMBER. These sentences
    name a legal document kind without carrying one, and the family must leave
    them untouched — over-masking is the failure the customer sees first. (A NAME
    another recognizer finds here is that recognizer's business; this test asserts
    only that no LEGAL label was claimed.)"""
    problems = [text for text in LEGAL_NEGATIVES
                if any(span.entity_type in v6.LEGAL_LABELS
                       for span in detector.detect(text))]
    check("a legal document kind named without a number is not masked",
          not problems, "; ".join(problems) if problems
          else f"{len(LEGAL_NEGATIVES)} negatives")


def test_legal_labels_follow_the_registry() -> None:
    """THE LABEL IS THE ENGINE'S NAME FOR A TYPE, and all six records carry
    `engine_labels == ()` — so every label is the registry's type id VERBATIM. Two
    labels for one type would make the v6 metric unable to separate them, and one
    label for two types makes one of them unscoreable; the arbitration is recorded
    rather than hidden: the court-case pair keeps TWO labels and ONE identity key."""
    problems: list[str] = []
    expected = {
        "COURT_CASE_UID": "COURT_CASE_UID",
        "ARBITRAZH_CASE_NO": "ARBITRAZH_CASE_NO",
        "COURT_CASE_NO_SOU": "COURT_CASE_NO_SOU",
        "FSSP_IP_NO": "FSSP_IP_NO",
        "EXEC_DOC_NO": "EXEC_DOC_NO",
        "CADASTRAL_NUMBER": "CADASTRAL_NUMBER",
    }
    for type_id, label in expected.items():
        if v6.LEGAL_LABEL.get(type_id) != label:
            problems.append(f"{type_id}: label {v6.LEGAL_LABEL.get(type_id)!r}, "
                            f"expected {label!r}")
    if set(v6.LEGAL_LABEL) != set(expected):
        problems.append(f"LEGAL_LABEL covers {sorted(v6.LEGAL_LABEL)}")
    # ONE IDENTITY KEY for the two court-case labels: the same case reached
    # through a generic field key and through a cue must not mint two substitutes.
    if v6.legal_signature("А31-2840/2013", "ARBITRAZH_CASE_NO") != \
            v6.legal_signature("А31-2840/2013", "COURT_CASE_NO_SOU"):
        problems.append("the court-case pair does not share one identity key")
    if v6.legal_signature("2-13/2015", "FSSP_IP_NO") == \
            v6.legal_signature("2-13/2015", "COURT_CASE_NO_SOU"):
        problems.append("unrelated legal types share one identity key")
    check("the engine label of each legal type is the registry's",
          not problems, "; ".join(problems) if problems else "6 types, 1 shared pair")


def test_legal_generic_key_does_not_reshape_the_source() -> None:
    """THE KEY TYPES, THE SOURCE DECIDES THE SHAPE. `case_number` is given to
    COURT_CASE_NO_SOU (the ordinary general-jurisdiction reading), but an
    ARBITRAZH-shaped number that arrives under that key must keep ITS OWN shape —
    re-shaping it into «N-N/YYYY» would hand the customer's validator a case
    number that is not one. And the two readings of the SAME case must be ONE
    substitute, or the model meets one document twice under two numbers."""
    detector = Detector()
    problems: list[str] = []
    vault = _vault()
    cued = "по делу А31-2840/2013"
    keyed = '{"case_number": "А31-2840/2013"}'
    cued_spans = detector.detect(cued)
    keyed_spans = detector.detect(keyed)
    if not cued_spans or not keyed_spans:
        check("a generic field key cannot re-shape or fork a legal number", False,
              f"the cue path found {len(cued_spans)} spans and the key path "
              f"{len(keyed_spans)}")
        return
    masked_cued = mask_text(cued, vault, cued_spans)
    masked_keyed = mask_text(keyed, vault, keyed_spans)
    span = cued_spans[0]
    fake_cued = masked_cued[span.start:span.end]
    keyed_span = keyed_spans[0]
    fake_keyed = masked_keyed[keyed_span.start:keyed_span.end]
    if fake_cued != fake_keyed:
        problems.append(f"one case, two substitutes: {fake_cued!r} vs {fake_keyed!r}")
    if not v6.LEGAL_SHAPES["ARBITRAZH_CASE_NO"].fullmatch(fake_keyed):
        problems.append(f"the key re-shaped the source: {fake_keyed!r}")
    if unmask_text(masked_keyed, vault) != keyed:
        problems.append(f"the keyed mention did not round-trip: "
                        f"{unmask_text(masked_keyed, vault)!r}")
    check("a generic field key cannot re-shape or fork a legal number",
          not problems, "; ".join(problems) if problems else "1 case, 2 readings")


def test_legal_shapes_do_not_steal_the_other_families() -> None:
    """TWO FAMILIES, ONE ALTERNATION, AND A MEASURED COLLISION. The masked FSSP
    proceeding «ИП № 4542450/74/44664-ИП» made the identity MILITARY_ID shape
    match the cue and the first group; the family's own restore scan is what keeps
    its token reversible. The other direction is asserted here TOO: every identity
    and checksum sample from the two families above still round-trips with the
    legal shapes present in `token_re`."""
    detector = Detector()
    problems: list[str] = []
    for text, label, value in (
            ("военный билет АК № 1234567", "MILITARY_ID", "АК № 1234567"),
            ("СТС 77 12 345678", "VEHICLE_DOC", "77 12 345678"),
            ("загранпаспорт 75 1234567", "INTL_PASSPORT", "75 1234567"),
            ("СНИЛС 112-233-445 95", "SNILS", "112-233-445 95"),
            ("IMEI 526018159083010", "IMEI", "526018159083010"),
            ("ИП № 1234567/25/77001-ИП", "FSSP_IP_NO", "1234567/25/77001-ИП")):
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{label}: {value!r} still standing in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{label}: {value!r} did not return ({restored!r})")
    check("the legal shapes do not steal the identity or checksum tokens",
          not problems, "; ".join(problems) if problems else "6 round trips")


# ===================== N1 finance/insurance/medical family (ten types) ========
#
# The registry's ten records with `generated_checksum == ""` in the finance /
# insurance / medical group. There is no arithmetic to inherit, so the mechanism
# under test is GRAMMAR + TYPED CONTEXT -> recognition, a format-preserving mint,
# the notation on both legs, restore, residual. TWO of the ten carry
# `grammar_status == "ГРАММАТИКА?"` (OSAGO_POLICY, REFERRAL_NUMBER) and their
# shape is recorded as GRAMMAR_UNASSERTED — a conservative cue/key-anchored rule,
# never an invented validator. EIGHT are free-form («национальной НЕТ»), so the
# shapes are the conservative shape rule `ru_pii_v6 §finance` states.

# (type_id, engine label, text, value that must be typed)
FINANCE_CASED: list[tuple[str, str, str, str]] = [
    ("LOAN_CONTRACT_NUMBER", "LOAN_CONTRACT_NUMBER",
     "кредитный договор № 2701079819", "2701079819"),
    ("LOAN_CONTRACT_NUMBER", "LOAN_CONTRACT_NUMBER",
     "по договору займа 12-345678/2025", "12-345678/2025"),
    ("LOAN_CONTRACT_NUMBER", "LOAN_CONTRACT_NUMBER",
     '{"loan_id": "МФО-2025-0012345"}', "МФО-2025-0012345"),
    ("CREDIT_SUBJECT_CODE", "CREDIT_SUBJECT_CODE",
     "код субъекта кредитной истории Qw7rT2", "Qw7rT2"),
    ("CREDIT_SUBJECT_CODE", "CREDIT_SUBJECT_CODE",
     '{"credit_history_code": "Аб12вГ"}', "Аб12вГ"),
    ("DMS_POLICY", "DMS_POLICY", "полис ДМС 001SB12345678", "001SB12345678"),
    ("DMS_POLICY", "DMS_POLICY",
     '{"dms_policy": "ДМС-1234567/25"}', "ДМС-1234567/25"),
    ("OSAGO_POLICY", "OSAGO_POLICY", "полис ОСАГО ХХХ 0123456789",
     "ХХХ 0123456789"),
    ("OSAGO_POLICY", "OSAGO_POLICY", "е-ОСАГО ХХХ№0123456789", "ХХХ№0123456789"),
    ("OSAGO_POLICY", "OSAGO_POLICY",
     '{"osago_series": "XXX 0123456789"}', "XXX 0123456789"),
    ("KASKO_POLICY", "KASKO_POLICY", "полис КАСКО AI123456789", "AI123456789"),
    ("KASKO_POLICY", "KASKO_POLICY",
     '{"kasko_policy": "7100-12345678"}', "7100-12345678"),
    ("INSURANCE_CLAIM_NUMBER", "INSURANCE_CLAIM_NUMBER",
     "номер убытка У-671-475136/25", "У-671-475136/25"),
    ("INSURANCE_CLAIM_NUMBER", "INSURANCE_CLAIM_NUMBER",
     '{"claim_number": "0012345678-001"}', "0012345678-001"),
    ("MEDCARD_NUMBER", "MEDCARD_NUMBER", "номер медкарты 12345/2024",
     "12345/2024"),
    ("MEDCARD_NUMBER", "MEDCARD_NUMBER",
     '{"medcard": "12345/2024"}', "12345/2024"),
    ("ELN_NUMBER", "ELN_NUMBER", "больничный 900012345678", "900012345678"),
    ("ELN_NUMBER", "ELN_NUMBER", '{"lnCode": "900012345678"}',
     "900012345678"),
    ("PRESCRIPTION_NUMBER", "PRESCRIPTION_NUMBER",
     "номер рецепта 45 0012345678", "45 0012345678"),
    ("PRESCRIPTION_NUMBER", "PRESCRIPTION_NUMBER",
     '{"prescription_id": "45 0012345678"}', "45 0012345678"),
    ("REFERRAL_NUMBER", "REFERRAL_NUMBER",
     "номер направления 057-2024-001234", "057-2024-001234"),
    ("REFERRAL_NUMBER", "REFERRAL_NUMBER",
     '{"referral_id": "057-2024-001234"}', "057-2024-001234"),
]

# One source per engine label, for the mint's own properties. The forms are the
# registry's own samples plus the separator, prefix and case variants its grammar
# names.
FINANCE_MINT_SOURCES: list[tuple[str, str]] = [
    ("LOAN_CONTRACT_NUMBER", "12-345678/2025"),
    ("LOAN_CONTRACT_NUMBER", "2701079819"),
    ("LOAN_CONTRACT_NUMBER", "МФО-2025-0012345"),
    ("LOAN_CONTRACT_NUMBER", "0045-Р-123456789"),
    ("CREDIT_SUBJECT_CODE", "Qw7rT2"),
    ("CREDIT_SUBJECT_CODE", "Аб12вГ"),
    ("DMS_POLICY", "001SB12345678"),
    ("DMS_POLICY", "ДМС-1234567/25"),
    ("DMS_POLICY", "12345678901234"),
    ("OSAGO_POLICY", "ХХХ 0123456789"),
    ("OSAGO_POLICY", "ХХХ№0123456789"),
    ("OSAGO_POLICY", "XXX 0123456789"),
    ("KASKO_POLICY", "AI123456789"),
    ("KASKO_POLICY", "7100-12345678"),
    ("KASKO_POLICY", "КАСКО-001-2025-0001234"),
    ("INSURANCE_CLAIM_NUMBER", "У-671-475136/25"),
    ("INSURANCE_CLAIM_NUMBER", "0012345678-001"),
    ("INSURANCE_CLAIM_NUMBER", "ОСАГО-25-123456"),
    ("MEDCARD_NUMBER", "12345/2024"),
    ("MEDCARD_NUMBER", "12345 2024"),
    ("ELN_NUMBER", "900012345678"),
    ("PRESCRIPTION_NUMBER", "45 0012345678"),
    ("PRESCRIPTION_NUMBER", "450012345678"),
    ("REFERRAL_NUMBER", "057-2024-001234"),
]

# The registry's samples ALONE, with no cue and no key. `bare_typed=False` on all
# ten, so none of them may be typed by this family.
FINANCE_BARE: tuple[tuple[str, str], ...] = (
    ("12-345678/2025", "LOAN_CONTRACT_NUMBER"),
    ("Qw7rT2", "CREDIT_SUBJECT_CODE"),
    ("001SB12345678", "DMS_POLICY"),
    ("ХХХ 0123456789", "OSAGO_POLICY"),
    ("AI123456789", "KASKO_POLICY"),
    ("У-671-475136/25", "INSURANCE_CLAIM_NUMBER"),
    ("12345/2024", "MEDCARD_NUMBER"),
    ("900012345678", "ELN_NUMBER"),
    ("45 0012345678", "PRESCRIPTION_NUMBER"),
    ("057-2024-001234", "REFERRAL_NUMBER"),
)

# A DOCUMENT KIND NAMED WITHOUT A NUMBER. Over-masking is the failure the customer
# sees first, and this family's cues are ordinary Russian words.
FINANCE_NEGATIVES: tuple[str, ...] = (
    "история болезни длится год",
    "направление в отдел продаж",
    "страховое дело закрыто",
    "полис ДМС оформлен",
    "номер направления уточните в регистратуре",
    "рецепт выписан врачом",
    "договор № 1234 от 15.05.2025",
    "код субъекта не указан",
    "код подтверждения 4521",
    "больничный закрыт 15 мая",
    "талон 778-2034",
    "чек №35417",
    "сумма 4990 р",
    "артикул 256gb",
    "счёт № 1234 от 15.05.2025",
)

# Cue-and-key sources whose content is implausible. The cue is the evidence, so
# every one of them must still be protected — a family that grew a validator for
# a free-form number would send them to the model in the clear.
FINANCE_TYPED_INVALID: tuple[tuple[str, str, str], ...] = (
    ("LOAN_CONTRACT_NUMBER", "кредитный договор № 00-000000/0000",
     "00-000000/0000"),
    ("CREDIT_SUBJECT_CODE", "код субъекта Zz0000", "Zz0000"),
    ("DMS_POLICY", "полис ДМС 000000000000", "000000000000"),
    ("OSAGO_POLICY", "полис ОСАГО ХХХ 0000000000", "ХХХ 0000000000"),
    ("KASKO_POLICY", "полис КАСКО 00-00000000", "00-00000000"),
    ("INSURANCE_CLAIM_NUMBER", "номер убытка 0-000-000000/00",
     "0-000-000000/00"),
    ("MEDCARD_NUMBER", "номер медкарты 0000/0000", "0000/0000"),
    ("ELN_NUMBER", "больничный 000000000000", "000000000000"),
    ("PRESCRIPTION_NUMBER", "номер рецепта 00 0000000000", "00 0000000000"),
    ("REFERRAL_NUMBER", "номер направления 000-0000-000000",
     "000-0000-000000"),
)


def test_finance_grammar_unasserted_is_recorded() -> None:
    """THE TWO `ГРАММАТИКА?` TYPES ARE RECORDED, NOT PAPERED OVER, AND THE ONE
    `pd_context` RULE IS RECORDED AS UNIMPLEMENTED.

    OSAGO_POLICY's primary source was not obtained (РСА refused TLS, НСИС answered
    403) and REFERRAL_NUMBER's national grammar is «НЕ установлена», so both keep
    a conservative cue/key-anchored shape and the module names them in one
    constant. None of the ten carries a checksum, so no validator may be invented
    for any of them — and `mint_finance` must be total over junk rather than
    raising, because a renderer that raises is a 5xx on the masking path.

    OSAGO_POLICY's `pd_context` is OD-22 — «объектный номер: позитив при
    владельце-физлице, в контексте юрлица — негатив». NO OWNER SIGNAL EXISTS in
    this pipeline, so the rule can be recorded and cannot be implemented; the test
    asserts it is RECORDED (a silent drop would be the fabrication)."""
    problems: list[str] = []
    if len(v6.FINANCE_TYPES) != 10:
        problems.append(f"{len(v6.FINANCE_TYPES)} finance types, expected 10")
    if v6.FINANCE_GRAMMAR_UNASSERTED != frozenset(
            ("OSAGO_POLICY", "REFERRAL_NUMBER")):
        problems.append(f"FINANCE_GRAMMAR_UNASSERTED is "
                        f"{sorted(v6.FINANCE_GRAMMAR_UNASSERTED)}")
    if v6.FINANCE_PD_CONTEXT != {"OSAGO_POLICY": "OD-22"}:
        problems.append(f"FINANCE_PD_CONTEXT is {v6.FINANCE_PD_CONTEXT}")
    if v6.FINANCE_GRAMMAR_UNASSERTED <= set(v6.FINANCE_PD_CONTEXT):
        problems.append("a grammar-unasserted type carries a pd_context rule")
    for type_id in v6.FINANCE_TYPES:
        if hasattr(v6, f"validate_{type_id.lower()}"):
            problems.append(f"{type_id}: an invented validator exists")
    for junk in ("", "   ", "абв", "0", "-", "№", "х" * 40, "?!№", "нет данных"):
        for type_id in v6.FINANCE_TYPES:
            fake = v6.mint_finance(type_id, junk)
            if not fake:
                problems.append(f"{type_id}: total mint returned nothing for "
                                f"{junk!r}")
    check("the grammar-uncertain finance types are named and no validator is "
          "invented", not problems, "; ".join(problems) if problems
          else "10 types, 2 unasserted, 1 pd_context recorded")


def test_finance_cued_and_keyed(detector: Detector) -> None:
    """Cue context and field-key context both type the value, on the REAL pipeline
    (`Detector.detect`), with the engine label the registry names."""
    problems: list[str] = []
    for type_id, label, text, value in FINANCE_CASED:
        if not _found(detector, text, label, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    check("finance identifiers are recognized by cue and by field key",
          not problems, "; ".join(problems) if problems
          else f"{len(FINANCE_CASED)} texts")


def test_finance_typed_invalid_no_gate(detector: Detector) -> None:
    """COV-TYPED-INVALID FOR A FREE-FORM NUMBER. There is no checksum to reject an
    implausible value, and the cue is the evidence: an all-zero policy behind its
    own cue is still the customer's policy. The mechanism must not grow a
    validator that would send it to the model in the clear."""
    problems = [text for _label, text, _value in FINANCE_TYPED_INVALID
                if not any(span.entity_type in v6.FINANCE_LABELS
                           for span in detector.detect(text))]
    check("an implausible finance value behind its cue is still protected",
          not problems, "; ".join(problems) if problems
          else f"{len(FINANCE_TYPED_INVALID)} negatives")


def test_finance_bare_is_not_typed(detector: Detector) -> None:
    """`bare_typed=False` ON ALL TEN, ASSERTED RATHER THAN ASSUMED. A bare shape
    types nothing: eight of these records are free-form numbers, and claiming one
    bare would buy recall with other people's order numbers."""
    problems = [value for value, _label in FINANCE_BARE
                if any(span.entity_type in v6.FINANCE_LABELS
                       for span in detector.detect(f"значение {value} конец"))]
    check("a bare finance shape is not typed by this family", not problems,
          "; ".join(problems) if problems else f"{len(FINANCE_BARE)} bare shapes")


def test_finance_mint_is_format_preserving() -> None:
    """THE SUBSTITUTE KEEPS THE SOURCE'S FORMAT EXACTLY: separator layout,
    character classes, digit count, letter count, letter case and script — and it
    keeps its own label's shape. There is no checksum to inherit, so format is the
    whole contract, and a fake of the wrong shape is a value the customer's own
    validator refuses."""
    problems: list[str] = []
    for label, source in FINANCE_MINT_SOURCES:
        for _ in range(50):
            fake = v6.mint_finance(label, source)
            if fake == source:
                problems.append(f"{label}: the fake equals the source {source!r}")
                break
            if [c for c in fake if not c.isalnum()] != \
                    [c for c in source if not c.isalnum()]:
                problems.append(f"{label}: separators changed {source!r} -> {fake!r}")
                break
            if [c.isdigit() for c in fake] != [c.isdigit() for c in source]:
                problems.append(f"{label}: classes changed {source!r} -> {fake!r}")
                break
            if [c.isupper() for c in fake if c.isalpha()] != \
                    [c.isupper() for c in source if c.isalpha()]:
                problems.append(f"{label}: case changed {source!r} -> {fake!r}")
                break
            if [c.isascii() for c in fake if c.isalpha()] != \
                    [c.isascii() for c in source if c.isalpha()]:
                problems.append(f"{label}: script changed {source!r} -> {fake!r}")
                break
            resolved = v6.finance_label_for_source(source, label)
            if not v6.FINANCE_SHAPES[resolved].fullmatch(fake):
                problems.append(f"{label}: {fake!r} is not its own shape "
                                f"({source!r})")
                break
    check("a finance substitute keeps classes, separators, case and script",
          not problems, "; ".join(problems) if problems
          else f"{len(FINANCE_MINT_SOURCES)} sources x50")


def test_finance_roundtrip_three_legs() -> None:
    """The real identifier comes back on every OUT shape the product has: prose, a
    tool argument that must still parse, and a streamed chunk. A substitute that
    fails to resolve is a FAKE in the customer's tool with a 200."""
    detector = Detector()
    problems: list[str] = []
    for _type_id, label, text, value in FINANCE_CASED:
        if text.startswith("{"):
            continue
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{label}: value still standing in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{label}: {value!r} did not return from {masked!r}")
    payload = json.dumps({"loan_id": "12-345678/2025",
                          "osago_series": "ХХХ 0123456789",
                          "lnCode": "900012345678",
                          "medcard": "12345/2024",
                          "claim_number": "У-671-475136/25"},
                         ensure_ascii=False)
    vault = _vault()
    masked = mask_text(payload, vault, detector.detect(payload))
    opened = unmask_arguments(masked, vault)
    for value in ("12-345678/2025", "ХХХ 0123456789", "900012345678",
                  "12345/2024", "У-671-475136/25"):
        if value not in opened:
            problems.append(f"argument leg lost {value!r}: {masked!r} -> {opened!r}")
    if not json.loads(opened):
        problems.append(f"argument leg is not JSON after restore: {opened!r}")
    from pseudex.redact import unmask_stream_chunk
    chunk_text = "полис ОСАГО ХХХ 0123456789"
    vault = _vault()
    masked = mask_text(chunk_text, vault, detector.detect(chunk_text))
    emitted, carry = unmask_stream_chunk(masked, "", vault, flush=True)
    if "ХХХ 0123456789" not in emitted + carry:
        problems.append(f"stream leg lost the value: {emitted + carry!r}")
    check("finance identifiers restore on prose, tool arguments and streams",
          not problems, "; ".join(problems) if problems else "3 legs")


def test_finance_token_shapes() -> None:
    """`unmask_text` finds tokens by SHAPE, so a minted shape that escapes
    `token_re` is a substitute that never resolves — a FAKE in the customer's tool
    with a 200. The family's shapes are minted and matched from one tuple, and the
    family's own alternation is what keeps the free-form ones alive when another
    family's pattern matches AROUND them."""
    problems: list[str] = []
    for label, source in FINANCE_MINT_SOURCES:
        vault = _vault()
        for _ in range(50):
            token = vault.tokenize(source, label)
            if not token_re().fullmatch(token):
                problems.append(f"{label}: {token!r} escapes token_re")
                break
            if not v6.FINANCE_TOKEN_RE.fullmatch(token):
                problems.append(f"{label}: {token!r} escapes FINANCE_TOKEN_RE")
                break
    check("every minted finance token is matched by both token scans",
          not problems, "; ".join(problems) if problems
          else f"{len(FINANCE_MINT_SOURCES)} sources x50 samples")


def test_finance_reformatted_substitute_resolves() -> None:
    """THE SECOND LINE OF DEFENCE. A model that rewrites our substitute — drops
    the separators, changes the case — no longer matches its minted shape, and the
    fake then reaches the tool. The finance signature (content, letters included,
    the label part of the key) resolves a letter-bearing token, and the DIGIT
    signature resolves a token with no letter at all, which is why every finance
    label is in `vault._NUMERIC_TYPES`."""
    problems: list[str] = []
    for label, value in (("LOAN_CONTRACT_NUMBER", "12-345678/2025"),
                         ("CREDIT_SUBJECT_CODE", "Qw7rT2"),
                         ("DMS_POLICY", "001SB12345678"),
                         ("OSAGO_POLICY", "ХХХ 0123456789"),
                         ("KASKO_POLICY", "AI123456789"),
                         ("INSURANCE_CLAIM_NUMBER", "У-671-475136/25"),
                         ("MEDCARD_NUMBER", "12345/2024"),
                         ("ELN_NUMBER", "900012345678"),
                         ("PRESCRIPTION_NUMBER", "45 0012345678"),
                         ("REFERRAL_NUMBER", "057-2024-001234")):
        vault = _vault()
        fake = vault.tokenize(value, label)
        squeezed = _alnum(fake)
        restored = unmask_text(f"номер {squeezed}", vault)
        if _alnum(value) not in _alnum(restored):
            problems.append(f"{label}: squeezed substitute {squeezed!r} did not "
                            f"resolve ({restored!r})")
        upper = fake.upper()
        restored_upper = unmask_text(f"номер {upper}", vault)
        if _alnum(value) not in _alnum(restored_upper):
            problems.append(f"{label}: upper-cased substitute {upper!r} did not "
                            f"resolve ({restored_upper!r})")
    check("a substitute the agent reformatted still resolves", not problems,
          "; ".join(problems) if problems else "10 identifiers x2 rewritings")


def test_finance_notation_both_legs() -> None:
    """P02. The notation belongs to whoever wrote the mention: the CUSTOMER's
    separators are mirrored onto the substitute on the way in, and the AGENT's
    regrouping is mirrored onto the real value on the way back. The regrouping
    tested is the one the shape supports — the separators the registry's
    `form_features` name as presentation."""
    detector = Detector()
    problems: list[str] = []
    for text, label, value, source_sep, agent_sep in (
            ("номер медкарты 12345/2024", "MEDCARD_NUMBER", "12345/2024",
             "/", " "),
            ("номер направления 057-2024-001234", "REFERRAL_NUMBER",
             "057-2024-001234", "-", "/"),
            ("номер рецепта 45 0012345678", "PRESCRIPTION_NUMBER",
             "45 0012345678", " ", "/")):
        vault = _vault()
        spans = [s for s in detector.detect(text) if s.entity_type == label]
        if len(spans) != 1:
            problems.append(f"{text!r}: {len(spans)} spans, expected 1")
            continue
        span = spans[0]
        masked = mask_text(text, vault, spans)
        fake = masked[span.start:span.end]
        if {c for c in fake if not c.isalnum()} != {source_sep}:
            problems.append(f"IN: the customer's separators were not mirrored "
                            f"({value!r} -> {fake!r})")
            continue
        agent_surface = fake.replace(source_sep, agent_sep)
        rewritten = text[:span.start] + agent_surface + text[span.end:]
        restored = unmask_text(rewritten, vault)
        real = restored[span.start:span.start + len(agent_surface)]
        if _alnum(real) != _alnum(value):
            problems.append(f"OUT: content lost for {value!r}: {restored!r}")
        elif real == value:
            problems.append(f"OUT: the customer's notation was restored instead "
                            f"of the agent's ({real!r})")
        elif agent_sep not in real:
            problems.append(f"OUT: the agent's grouping was dropped ({real!r})")
    check("the customer's finance notation comes in and the agent's goes out",
          not problems, "; ".join(problems) if problems else "3 identifiers")


def test_finance_no_fuzzy_numerals() -> None:
    """NO FUZZY MATCHING REACHES A FINANCE NUMBER. A policy number one digit away
    from another is a DIFFERENT policy, not a typo of the first. Restoring the
    neighbour's real value under the agent's bent substitute would name a contract
    that was never in the dialogue."""
    problems: list[str] = []
    for label, first, second in (
            ("DMS_POLICY", "001SB12345678", "001SB12345679"),
            ("INSURANCE_CLAIM_NUMBER", "У-671-475136/25", "У-671-475136/26")):
        vault = _vault()
        vault.tokenize(first, label)
        vault.tokenize(second, label)
        fake = vault.tokenize(first, label)
        bent = fake[:-1] + ("0" if fake[-1] != "0" else "1")
        restored = unmask_text(f"номер {bent}", vault)
        if second in restored:
            problems.append(f"{label}: a one-digit change restored the OTHER "
                            f"value ({restored!r})")
    # TWO POLICIES THAT SHARE A DIGIT RUN ARE NOT ONE POLICY: the identity key
    # carries the label AND the letters, so no two types answer for each other.
    if v6.finance_signature("12345/2024", "MEDCARD_NUMBER") == \
            v6.finance_signature("12345/2024", "PRESCRIPTION_NUMBER"):
        problems.append("two finance types share one identity key")
    check("a one-digit change is a different document, not a typo", not problems,
          "; ".join(problems) if problems else "2 identifiers")


def test_finance_unresolved_substitute_is_named() -> None:
    """A FAKE THAT REACHES THE TOOL MUST BE VISIBLE. Every substitute this family
    mints has to be a candidate the residual question looked at — and the family's
    records are free-form numbers, so a token can begin right after a cue word
    whose tail looks like a plate («полис ДМС 437BX87160487»). Without the family's
    own scan the whole substitute is never a candidate and the leftover is reported
    as nothing."""
    detector = Detector()
    problems: list[str] = []
    for _type_id, label, text, value in FINANCE_CASED:
        if text.startswith("{"):
            continue
        vault = _vault()
        spans = detector.detect(text)
        masked = mask_text(text, vault, spans)
        if value not in text or value in masked:
            continue
        fake = masked[text.index(value):text.index(value) + len(value)]
        seen = surviving_substitutes(masked, masked, vault, for_tool=False)
        if fake not in seen:
            problems.append(f"{label}: leftover {fake!r} not named ({seen})")
    check("an unresolved finance substitute is reported as a residual",
          not problems, "; ".join(problems) if problems else "10 identifiers")


def test_finance_no_overmask(detector: Detector) -> None:
    """THE CUE IS THE EVIDENCE, AND A WORD ALONE IS NOT A NUMBER. These sentences
    name a document kind without carrying one, and the family must leave them
    untouched — over-masking is the failure the customer sees first."""
    problems = [text for text in FINANCE_NEGATIVES
                if any(span.entity_type in v6.FINANCE_LABELS
                       for span in detector.detect(text))]
    check("a finance document kind named without a number is not masked",
          not problems, "; ".join(problems) if problems
          else f"{len(FINANCE_NEGATIVES)} negatives")


def test_finance_dates_are_not_swallowed(detector: Detector) -> None:
    """A TYPED SPAN CONTAINS THE DATE SPAN AND THEREFORE REPLACES IT. These
    records are the ones whose cues sit next to a date in ordinary clinical and
    insurance writing — «история болезни 12.03.2020», «направление на МРТ
    01.02.2026». Without the shape's date lookahead the customer's DATE is dropped
    and the model is handed a fake medcard number where the date stood, and the
    agent's date field receives a number. The date must survive BOTH as not being
    typed by this family and through the round trip."""
    problems: list[str] = []
    for text, value in (("история болезни 12.03.2020", "12.03.2020"),
                        ("направление на МРТ 01.02.2026", "01.02.2026"),
                        ("больничный 2026-03-12", "2026-03-12"),
                        ("номер рецепта 15.05.2025", "15.05.2025")):
        spans = detector.detect(text)
        if any(span.entity_type in v6.FINANCE_LABELS for span in spans):
            problems.append(f"{text!r}: a finance type claimed the date "
                            f"({_types_found(detector, text)})")
            continue
        vault = _vault()
        masked = mask_text(text, vault, spans)
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{text!r}: the date did not survive the round trip "
                            f"({masked!r} -> {restored!r})")
    check("a date behind a finance cue is not swallowed by the number shape",
          not problems, "; ".join(problems) if problems else "4 dates")


def test_finance_token_never_swallows_a_following_number() -> None:
    """A FREE-FORM SHAPE IS GREEDY, AND A GREEDY SHAPE THAT CROSSES A SPACE IS A
    SUBSTITUTE THAT NEVER RESOLVES. The shape language allows a LETTER group
    between two digits («001SB12345678», «МФО-2025-0012345») but allows a SPACE to
    join AT MOST TWO groups, so a number written directly before another number
    cannot be read as one token. Measured rather than argued: every minted token is
    followed by a space and four digits, and the real value must still come back."""
    detector = Detector()
    problems: list[str] = []
    for label, text, value in (
            ("MEDCARD_NUMBER", "номер медкарты 12345/2024 5000", "12345/2024"),
            ("PRESCRIPTION_NUMBER", "номер рецепта 45 0012345678 5000",
             "45 0012345678"),
            ("LOAN_CONTRACT_NUMBER", "по договору займа 12-345678/2025 5000",
             "12-345678/2025"),
            ("DMS_POLICY", "полис ДМС 001234567890123 01.01.2025",
             "001234567890123")):
        vault = _vault()
        spans = [s for s in detector.detect(text)
                 if s.entity_type == label and text[s.start:s.end] == value]
        if len(spans) != 1:
            problems.append(f"{label}: the value is not one span "
                            f"({_types_found(detector, text)})")
            continue
        masked = mask_text(text, vault, spans)
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{label}: the value did not return ({restored!r})")
        if "5000" in text and "5000" not in restored:
            problems.append(f"{label}: the following number was swallowed "
                            f"({restored!r})")
    check("a finance token never swallows the number standing after it",
          not problems, "; ".join(problems) if problems else "4 texts")


def test_finance_labels_follow_the_registry() -> None:
    """THE LABEL IS THE ENGINE'S NAME FOR A TYPE, and all ten records carry
    `engine_labels == ()` — so every label is the registry's type id VERBATIM. Two
    labels for one type would make the v6 metric unable to separate them; one label
    for two types makes one of them unscoreable. Both are asserted."""
    problems: list[str] = []
    expected = {
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
    for type_id, label in expected.items():
        if v6.FINANCE_LABEL.get(type_id) != label:
            problems.append(f"{type_id}: label {v6.FINANCE_LABEL.get(type_id)!r}, "
                            f"expected {label!r}")
    if set(v6.FINANCE_LABEL) != set(expected):
        problems.append(f"FINANCE_LABEL covers {sorted(v6.FINANCE_LABEL)}")
    if set(v6.FINANCE_LABELS) != set(expected):
        problems.append(f"FINANCE_LABELS covers {sorted(v6.FINANCE_LABELS)}")
    # THE REGISTRY'S OWN FACTS, READ RATHER THAN RESTATED: the samples parse with
    # their own shape, and the `glyph` needle is what decides the fold.
    for type_id, sample in v6.FINANCE_SAMPLE.items():
        if not v6.FINANCE_SHAPES[type_id].fullmatch(sample):
            problems.append(f"{type_id}: the registry sample {sample!r} does not "
                            f"parse with its own shape")
    expected_fold = frozenset(
        type_id for type_id, kinds in v6.FINANCE_NEEDLE_KINDS.items()
        if "glyph" in kinds)
    if v6._FINANCE_GLYPH_FOLD != expected_fold:
        problems.append(f"glyph fold is {sorted(v6._FINANCE_GLYPH_FOLD)}")
    if v6.FINANCE_LABELS & {"OSAGO", "DMS", "KASKO", "MEDCARD", "ELN",
                            "PRESCRIPTION", "REFERRAL", "CLAIM"}:
        problems.append("a finance type was given a v5 engine alias")
    check("the engine label of each finance type is the registry's",
          not problems, "; ".join(problems) if problems else "10 types, 0 aliases")


def test_finance_shapes_do_not_steal_the_other_families() -> None:
    """FOUR FAMILIES, ONE FREE-FORM SHAPE LANGUAGE, AND A MEASURED COLLISION. The
    finance records are digits with separators, so their patterns would claim any
    number that another family already matched — a twenty-digit account, a
    sixteen-digit ОМС, a ten-digit ИНН. The patterns are appended AFTER every
    specific one, and this test asserts the other direction too: the v5, checksum,
    identity and legal samples all still round-trip with the finance shapes
    present."""
    detector = Detector()
    problems: list[str] = []
    for text, value in (
            ("счёт 40817810099910004312", "40817810099910004312"),
            ("ОМС 6613186091390990", "6613186091390990"),
            ("ИНН 7707083893", "7707083893"),
            ("СНИЛС 112-233-445 95", "112-233-445 95"),
            ("IMEI 526018159083010", "526018159083010"),
            ("загранпаспорт 75 1234567", "75 1234567"),
            ("СТС 77 12 345678", "77 12 345678"),
            ("военный билет АК № 1234567", "АК № 1234567"),
            ("ИП № 1234567/25/77001-ИП", "1234567/25/77001-ИП"),
            ("кадастровый номер 77:01:0001001:1234", "77:01:0001001:1234"),
            ("УИД 77OS0000-02-2026-000001-52", "77OS0000-02-2026-000001-52")):
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{value!r} still standing in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{value!r} did not return ({restored!r})")
    check("the finance shapes do not steal the other families' tokens",
          not problems, "; ".join(problems) if problems else "11 round trips")


def test_finance_key_typed_spelling_stays_reversible() -> None:
    """A FIELD KEY TYPES THE WHOLE VALUE WITH NO SHAPE CHECK, so a value can arrive
    written in separators no finance shape admits — «{"medcard": "123 456 789"}».
    `mint_finance` then answers from the registry's SAMPLE (correctly: it must not
    echo the source), and mirroring the source's separators onto that sample made
    the TOKEN unwritable in the family's own shapes — neither `token_re` nor
    `FINANCE_TOKEN_RE` matched it, and the FAKE reached the customer's tool with a
    200. The minted token must be matchable for EVERY spelling a key can deliver,
    which is what this measures over the shapes' own accepted set AND outside it."""
    detector = Detector()
    problems: list[str] = []
    for label, value in (("MEDCARD_NUMBER", "123 456 789"),
                         ("MEDCARD_NUMBER", "12.34.56.78"),
                         ("DMS_POLICY", "00 11 22 33 44 55"),
                         ("REFERRAL_NUMBER", "0 5 7 2 0 2 4")):
        vault = _vault()
        token = vault.tokenize(value, label)
        if not token_re().fullmatch(token):
            problems.append(f"{label}: {value!r} minted {token!r}, which escapes "
                            f"token_re")
        elif not v6.FINANCE_TOKEN_RE.fullmatch(token):
            problems.append(f"{label}: {value!r} minted {token!r}, which escapes "
                            f"FINANCE_TOKEN_RE")
        elif token == value:
            problems.append(f"{label}: the fake equals the source {value!r}")
    # …AND THE KEY PATH ITSELF, ON THE REAL PIPELINE.
    payload = '{"medcard": "123 456 789"}'
    vault = _vault()
    spans = detector.detect(payload)
    if not any(s.entity_type == "MEDCARD_NUMBER" for s in spans):
        problems.append(f"the key did not type the value ({_types_found(detector, payload)})")
    else:
        masked = mask_text(payload, vault, spans)
        opened = unmask_arguments(masked, vault)
        if "123 456 789" not in opened:
            problems.append(f"the key-typed value did not resolve: "
                            f"{masked!r} -> {opened!r}")
    check("a key-typed finance spelling stays reversible", not problems,
          "; ".join(problems) if problems else "4 spellings + 1 payload")


def test_finance_policy_key_overlap_is_recorded() -> None:
    """A KNOWN CROSS-TYPE COLLISION, PINNED SO IT CANNOT BE MISTAKEN FOR THE
    RULE. `policy_number` is the registry's key for THREE finance policies at once
    and the checksum family already landed it as ОМС, so the shared key keeps its
    v5 meaning and each finance policy is reached by its own distinctive key. The
    same overlap existed in prose: the ОМС cue «полис» fires on «полис ДМС …» and
    the ОМС span won the equal-boundary overlap at priority 7 against the finance
    family's default 1 — masked, but a wrong LABEL, and a fake ОМС ENP minted into
    a ДМС field. The Lead's integration added `PRIORITY["DMS_POLICY"] = 8`, which
    is above the checksum tier on purpose (the cue says ОМС is not what this is),
    and this check is that entry's mutation witness: remove it and the label falls
    back to ОМС while the value stays masked."""
    detector = Detector()
    problems: list[str] = []
    vault = _vault()
    # The shared field key keeps its v5 meaning — which since G7 is the registry
    # id `OMS_ENP` on the span, while the vault's row still carries `OMS`
    # (`ru_pii_v6.engine_label`). The label MOVED; the meaning did not.
    payload = '{"policy_number": "6613186091390990"}'
    spans = detector.detect(payload)
    if not any(s.entity_type == "OMS_ENP" for s in spans):
        problems.append(f"the shared `policy_number` key no longer types ОМС "
                        f"({_types_found(detector, payload)})")
    if any(s.entity_type in v6.FINANCE_LABELS for s in spans):
        problems.append("the shared `policy_number` key was re-pointed to a "
                        "finance type")
    # The prose overlap: a 16-digit ДМС number behind «полис» is masked, and the
    # ДМС label now wins it.
    text = "полис ДМС 1234567890123456"
    spans = detector.detect(text)
    masked = mask_text(text, vault, spans)
    if "1234567890123456" in masked:
        problems.append("the overlapping ДМС number leaked")
    if not any(s.entity_type == "DMS_POLICY" for s in spans):
        problems.append(f"the ДМС label did not win its own cue overlap "
                        f"({_types_found(detector, text)})")
    # A DISTINCTIVE finance cue has no such competitor and types correctly.
    if not _found(detector, "полис ДМС 001SB12345678", "DMS_POLICY",
                  "001SB12345678"):
        problems.append("a letter-bearing ДМС number behind its own cue is not "
                        "typed DMS_POLICY")
    check("the shared policy key is kept and the ДМС prose overlap is resolved",
          not problems, "; ".join(problems) if problems
          else "1 shared key, 1 resolved overlap, 1 clean cue")


# ==================== N1 telecom/device family (eight types) ==================
#
# The registry's eight telecom / device records, all `generated_checksum == ""`.
# There is no arithmetic to inherit, so the mechanism under test is GRAMMAR +
# TYPED CONTEXT -> recognition, a format-preserving mint, the notation on both
# legs, restore, residual. NONE of the eight is `ГРАММАТИКА?` — the family is the
# first with no unasserted type at all — and `TELECOM_GRAMMAR_UNASSERTED` exists
# so that fact is READ rather than inferred from a missing name.
#
# ONE ENGINE LABEL IS SHARED WITH v5 (`IP_ADDRESS -> IP`) and TWO shapes already
# had a bare v5 anchor (MAC's colon form, IPv4). That is why the negatives here
# are split: a bare sample of the six NEW labels must stay untyped, while the two
# v5 anchors are recorded as the engine's existing behaviour rather than asserted
# absent.

# (type_id, engine label, text, value, mechanism)
TELECOM_CASED: list[tuple[str, str, str, str, str]] = [
    ("IMSI", "IMSI", "IMSI 250991234567890", "250991234567890", "cue"),
    ("IMSI", "IMSI",
     "международный идентификатор абонента 250 99 1234567890",
     "250 99 1234567890", "cue"),
    ("IMSI", "IMSI", '{"imsi": "250991234567890"}', "250991234567890", "key"),
    ("MAC", "MAC", "MAC 00:1A:2B:3C:4D:5E", "00:1A:2B:3C:4D:5E", "cue"),
    ("MAC", "MAC", "мак-адрес 001A.2B3C.4D5E", "001A.2B3C.4D5E", "cue"),
    ("MAC", "MAC", "физический адрес 00-1A-2B-3C-4D-5E",
     "00-1A-2B-3C-4D-5E", "cue"),
    ("MAC", "MAC", '{"mac_address": "00:1A:2B:3C:4D:5E"}',
     "00:1A:2B:3C:4D:5E", "key"),
    ("IP_ADDRESS", "IP_ADDRESS", "IP 95.165.12.34", "95.165.12.34", "cue"),
    ("IP_ADDRESS", "IP_ADDRESS", "айпи 198.18.0.1", "198.18.0.1", "cue"),
    ("IP_ADDRESS", "IP_ADDRESS", "ip-адрес 2001:db8::1", "2001:db8::1", "cue"),
    ("IP_ADDRESS", "IP_ADDRESS", "ip-адрес ::ffff:192.168.1.1",
     "::ffff:192.168.1.1", "cue"),
    ("IP_ADDRESS", "IP_ADDRESS", '{"client_ip": "95.165.12.34"}',
     "95.165.12.34", "key"),
    ("IP_ADDRESS", "IP_ADDRESS", '{"remote_addr": "2001:db8::1"}',
     "2001:db8::1", "key"),
    ("ESIA_OID", "ESIA_OID", "ЕСИА 1000123456", "1000123456", "cue"),
    ("ESIA_OID", "ESIA_OID", "Госуслуги ID 1000123456", "1000123456", "cue"),
    ("ESIA_OID", "ESIA_OID", '{"personOid": "1000123456"}',
     "1000123456", "key"),
    ("MOBILE_AD_ID", "MOBILE_AD_ID",
     "GAID 6d92078a-8246-4ba4-ae5b-76104861e7dc",
     "6d92078a-8246-4ba4-ae5b-76104861e7dc", "cue"),
    ("MOBILE_AD_ID", "MOBILE_AD_ID",
     "IDFA 6D92078A-8246-4CA4-AE5C-76104861E7DC",
     "6D92078A-8246-4CA4-AE5C-76104861E7DC", "cue"),
    ("MOBILE_AD_ID", "MOBILE_AD_ID",
     "рекламный идентификатор 6D92078A82464CA4AE5C76104861E7DC",
     "6D92078A82464CA4AE5C76104861E7DC", "cue"),
    ("MOBILE_AD_ID", "MOBILE_AD_ID",
     '{"ios_ifa": "6D92078A-8246-4CA4-AE5C-76104861E7DC"}',
     "6D92078A-8246-4CA4-AE5C-76104861E7DC", "key"),
    ("APP_DEVICE_ID", "APP_DEVICE_ID",
     "appmetrica_device_id 123456789012345678", "123456789012345678", "cue"),
    ("APP_DEVICE_ID", "APP_DEVICE_ID",
     "идентификатор устройства 6D92078A-8246-4CA4-AE5C-76104861E7DC",
     "6D92078A-8246-4CA4-AE5C-76104861E7DC", "cue"),
    ("APP_DEVICE_ID", "APP_DEVICE_ID", '{"device_id": "123456789012345678"}',
     "123456789012345678", "key"),
    ("METRICA_CLIENT_ID", "METRICA_CLIENT_ID",
     "ClientID 250987654321098765", "250987654321098765", "cue"),
    ("METRICA_CLIENT_ID", "METRICA_CLIENT_ID",
     "_ym_uid 250987654321098765", "250987654321098765", "cue"),
    ("METRICA_CLIENT_ID", "METRICA_CLIENT_ID",
     '{"client_id": "250987654321098765"}', "250987654321098765", "key"),
    ("SUBSCRIBER_ACCOUNT", "SUBSCRIBER_ACCOUNT",
     "лицевой счёт 123456789012", "123456789012", "cue"),
    ("SUBSCRIBER_ACCOUNT", "SUBSCRIBER_ACCOUNT", "л/с 12345678", "12345678",
     "cue"),
    ("SUBSCRIBER_ACCOUNT", "SUBSCRIBER_ACCOUNT",
     '{"personal_account": "123456789012"}', "123456789012", "key"),
]

# The registry's own samples with NO cue and NO key, split by what the ENGINE
# already did before this family landed.
#   `bare_typed=False` on all eight, so none of these may be typed BY THIS FAMILY.
TELECOM_BARE_NEW: tuple[tuple[str, str], ...] = (
    ("250991234567890", "IMSI"),
    ("1000123456", "ESIA_OID"),
    ("12345678", "SUBSCRIBER_ACCOUNT"),
    ("250987654321098765", "METRICA_CLIENT_ID"),
)
#   …and the two the v5 recognizers ALREADY anchor bare. Recorded, never asserted
#   absent: `COV-INTEGRATION-KEEP-V5` keeps them, and this family only extends
#   them with the notations v5 cannot read.
TELECOM_BARE_V5_ANCHORED: tuple[tuple[str, str], ...] = (
    ("00:1A:2B:3C:4D:5E", "MAC"),
    ("95.165.12.34", "IP"),
)

# A DEVICE/SUBSCRIPTION WORD WITH NO VALUE. Over-masking is what the customer sees
# first, and these cues are ordinary Russian words.
TELECOM_NEGATIVES: tuple[str, ...] = (
    "лицевой счёт закрыт",
    "л/с уточните в приложении",
    "MAC-адрес устройства неизвестен",
    "физический адрес доставки уточните",
    "IP-адрес сервера изменился",
    "айпи не отвечает",
    "ЕСИА подтвердила вход",
    "рекламный идентификатор сброшен",
    "идентификатор устройства не найден",
    "ClientID не задан",
    "номер договора абонента уточняется",
    "заказ 1234567890 от 15.05.2025",
    "артикул 123456789012",
    "версия 95.165.12",
    "серия 1234 номер 567890",
)

# Cue context carrying an implausible value. The cue IS the evidence, so every one
# must stay protected — a family that grew a validator for an arithmetic-free
# record would send them to the model in the clear.
TELECOM_TYPED_INVALID: tuple[tuple[str, str, str], ...] = (
    ("IMSI", "IMSI 250000000000000", "250000000000000"),
    ("MAC", "MAC 00:00:00:00:00:00", "00:00:00:00:00:00"),
    ("IP_ADDRESS", "IP 0.0.0.0", "0.0.0.0"),
    ("ESIA_OID", "ЕСИА 0000000000", "0000000000"),
    ("MOBILE_AD_ID", "GAID 00000000-0000-0000-0000-000000000000",
     "00000000-0000-0000-0000-000000000000"),
    ("APP_DEVICE_ID", "идентификатор устройства 000000000000000000",
     "000000000000000000"),
    ("METRICA_CLIENT_ID", "ClientID 000000000000000000",
     "000000000000000000"),
    ("SUBSCRIBER_ACCOUNT", "лицевой счёт 00000000", "00000000"),
)

# One source per label, in every notation the record's own grammar names.
TELECOM_MINT_SOURCES: list[tuple[str, str]] = [
    ("IMSI", "250991234567890"),
    ("IMSI", "250 99 1234567890"),
    ("IMSI", "250-99-1234567890"),
    ("MAC", "00:1A:2B:3C:4D:5E"),
    ("MAC", "00-1a-2b-3c-4d-5e"),
    ("MAC", "001A.2B3C.4D5E"),
    ("MAC", "00:1А:2В:3С:4D:5Е"),
    ("IP_ADDRESS", "95.165.12.34"),
    ("IP_ADDRESS", "2001:db8::1"),
    ("IP_ADDRESS", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
    ("IP_ADDRESS", "::ffff:192.168.1.1"),
    ("ESIA_OID", "1000123456"),
    ("MOBILE_AD_ID", "6D92078A-8246-4CA4-AE5C-76104861E7DC"),
    ("MOBILE_AD_ID", "6d92078a82464ca4ae5c76104861e7dc"),
    ("APP_DEVICE_ID", "123456789012345678"),
    ("APP_DEVICE_ID", "6D92078A-8246-4CA4-AE5C-76104861E7DC"),
    ("METRICA_CLIENT_ID", "250987654321098765"),
    ("SUBSCRIBER_ACCOUNT", "123456789012"),
]


def _telecom_engine(type_id: str) -> str:
    return v6.TELECOM_LABEL.get(type_id, type_id)


def _telecom_type(engine_label: str) -> str:
    return v6.LABEL_TO_TELECOM.get(engine_label, engine_label)


def _telecom_reserved_tail(label: str, source: str) -> bool:
    """Whether `mint_telecom`'s answer for this source comes from the reserved
    IPv4 pool — the one case where the alphanumeric layout is not the source's."""
    return label == "IP_ADDRESS" and not (
        v6._TC_IPV6_SHAPE.fullmatch(source.strip())
        and not v6._TC_IPV6_MAPPED.match(source.strip()))


def test_telecom_registry_facts_are_recorded() -> None:
    """THE FAMILY'S OWN FACTS, ASSERTED RATHER THAN ASSUMED.

    None of the eight is `ГРАММАТИКА?` (`TELECOM_GRAMMAR_UNASSERTED` is EMPTY —
    the constant exists so a reader sees that rather than inferring it), and none
    carries a checksum, so no validator may be invented and the mint must be
    TOTAL over junk rather than raising. The five `pd_context` rules are RECORDED
    and NOT implemented — no owner signal exists in this pipeline, and a
    fabricated discriminator would be the failure GOAL-BRIEF §7 forbids.

    The DIGIT BOUNDS are asserted as the registry's own facts, per record: IMSI
    `≤15` on MCC «250», the operator account's `типично 8–12`, Метрика's 18-digit
    issuer sample. Where the registry states no length (ESIA_OID: «\d+; длина не
    установлена») the constant carries the SAMPLE's floor and the receipt says
    so."""
    problems: list[str] = []
    if len(v6.TELECOM_TYPES) != 8:
        problems.append(f"{len(v6.TELECOM_TYPES)} telecom types, expected 8")
    if v6.TELECOM_GRAMMAR_UNASSERTED:
        problems.append("a telecom record is marked ГРАММАТИКА? — the registry "
                        f"gives none ({sorted(v6.TELECOM_GRAMMAR_UNASSERTED)})")
    if v6.TELECOM_PD_CONTEXT.get("ESIA_OID", "").split(";")[0] != "direct":
        problems.append("ESIA_OID's `direct` pd_context is not recorded")
    for type_id in ("IP_ADDRESS", "MOBILE_AD_ID", "APP_DEVICE_ID",
                    "METRICA_CLIENT_ID"):
        if "indirect" not in v6.TELECOM_PD_CONTEXT.get(type_id, ""):
            problems.append(f"{type_id}: the OD-24 pd_context is not recorded")
    if set(v6.TELECOM_PD_CONTEXT) & {"IMSI", "SUBSCRIBER_ACCOUNT"}:
        problems.append("a record whose registry pd_context is empty carries one")
    if v6.TELECOM_DIGIT_COUNTS["IMSI"] != frozenset((13, 14, 15)):
        problems.append("the IMSI digit bound is not 13–15")
    if v6.TELECOM_DIGIT_COUNTS["SUBSCRIBER_ACCOUNT"] != frozenset(range(8, 13)):
        problems.append("the operator-account bound is not the registry's 8–12")
    if v6.TELECOM_DIGIT_COUNTS["METRICA_CLIENT_ID"] != frozenset((18,)):
        problems.append("the Метрика bound is not the issuer's 18")
    for type_id in v6.TELECOM_TYPES:
        if hasattr(v6, f"validate_{type_id.lower()}"):
            problems.append(f"{type_id}: an invented validator exists")
    for junk in ("", "   ", "абв", "0", "-", "№", "х" * 40, "?!№", "нет данных"):
        for type_id in v6.TELECOM_TYPES:
            if not v6.mint_telecom(type_id, junk):
                problems.append(f"{type_id}: total mint returned nothing for "
                                f"{junk!r}")
    check("the telecom registry facts are recorded and no validator is invented",
          not problems, "; ".join(problems) if problems
          else "8 types, 0 unasserted, 5 pd_context recorded")


def test_telecom_cued_and_keyed(detector: Detector) -> None:
    """Cue context and field-key context both type the value, on the REAL pipeline
    (`Detector.detect`), with the engine label the registry names (`IP_ADDRESS`
    keeps the v5 label `IP`, which is the registry's own `engine_labels`)."""
    problems: list[str] = []
    for type_id, engine, text, value, mechanism in TELECOM_CASED:
        if not _found(detector, text, engine, value):
            problems.append(f"{type_id}/{mechanism}: {text!r} -> "
                            f"{_types_found(detector, text)}")
    check("telecom identifiers are recognized by cue and by field key",
          not problems, "; ".join(problems) if problems
          else f"{len(TELECOM_CASED)} texts")


def test_telecom_typed_invalid_no_gate(detector: Detector) -> None:
    """COV-TYPED-INVALID FOR AN ARITHMETIC-FREE RECORD. There is no checksum to
    reject an implausible value and the cue is the evidence, so an all-zero MAC or
    a 250-prefixed zero IMSI behind its own cue is still the customer's value."""
    problems = [text for _label, text, _value in TELECOM_TYPED_INVALID
                if not any(span.entity_type in v6.TELECOM_LABELS
                           for span in detector.detect(text))]
    check("an implausible telecom value behind its cue is still protected",
          not problems, "; ".join(problems) if problems
          else f"{len(TELECOM_TYPED_INVALID)} negatives")


def test_telecom_bare_is_not_typed(detector: Detector) -> None:
    """`bare_typed=False` ON ALL EIGHT, READ PER TYPE.

    For the six records with no v5 anchor not ONE bare sample may be typed by this
    family — and `TELECOM_BARE_V5_ANCHORED` records the two that the ENGINE
    already anchors bare (a colon MAC, an IPv4 quad), which is v5 authority this
    family must not remove and cannot pretend does not exist. The second half of
    the check is the measured one: it asserts the v5 anchors STILL fire, so a
    change that quietly disabled them would be red here."""
    problems = [value for value, _label in TELECOM_BARE_NEW
                if any(span.entity_type in v6.TELECOM_LABELS
                       for span in detector.detect(f"значение {value} конец"))]
    for value, label in TELECOM_BARE_V5_ANCHORED:
        if not _found(detector, f"значение {value} конец", label, value):
            problems.append(f"the v5 bare anchor for {label} stopped firing on "
                            f"{value!r}")
    check("a bare telecom sample is not typed by this family (and the two v5 "
          "anchors stay)", not problems, "; ".join(problems) if problems
          else f"{len(TELECOM_BARE_NEW)} bare + "
               f"{len(TELECOM_BARE_V5_ANCHORED)} v5 anchors")


def test_telecom_mint_is_format_preserving() -> None:
    """THE SUBSTITUTE KEEPS THE SOURCE'S FORMAT: separator layout, character
    classes, letter case, script and the label's own shape. There is no checksum
    to inherit, so format is the whole contract.

    TWO PROPERTIES ARE PER-FAMILY AND BOTH ARE ASSERTED AS THE FAMILY'S RULE
    RATHER THAN THE DOCUMENT FAMILIES':
      * a HEX field may draw a letter where the source had a digit and vice versa
        (`00:1A:…` -> `0F:71:…`): the SHAPE is what the customer's validator
        reads, and every alphanumeric position stays alphanumeric;
      * an IPv4 fake comes from the RESERVED RFC 2544 range and therefore has its
        own octet lengths — the separators are the source's, the digits are the
        reservation's."""
    problems: list[str] = []
    for label, source in TELECOM_MINT_SOURCES:
        for _ in range(25):
            fake = v6.mint_telecom(label, source)
            if not fake or fake == source:
                problems.append(f"{label}: {source!r} -> {fake!r}")
                break
            if [c for c in fake if not c.isalnum()] != \
                    [c for c in source if not c.isalnum()]:
                problems.append(f"{label}: separators changed {source!r} -> {fake!r}")
                break
            if [c.isalnum() for c in fake] != [c.isalnum() for c in source] \
                    and not _telecom_reserved_tail(label, source):
                # AN IPv4 FAKE IS THE FAMILY'S ONE EXCEPTION, and it is
                # deliberate: it comes from the reserved RFC 2544 pool, whose
                # octets have their own lengths, so the alphanumeric layout
                # legitimately differs. The separator layout (asserted above) and
                # the label's own shape (asserted below) are what must hold. The
                # IPv4-MAPPED IPv6 form is the same exception for the same
                # reason: its dotted TAIL is the address.
                problems.append(
                    f"{label}: alnum layout changed {source!r} -> {fake!r}")
                break
            if label in ("MAC", "MOBILE_AD_ID", "APP_DEVICE_ID", "IP_ADDRESS") and \
                    not all(c in "0123456789abcdefABCDEF"
                            for c in fake if c.isalnum()):
                problems.append(f"{label}: a non-hex character in {fake!r}")
                break
            pattern = v6.telecom_shape(label)
            if pattern is None or not pattern.fullmatch(fake):
                problems.append(f"{label}: {fake!r} is not its own shape "
                                f"({source!r})")
                break
    check("a telecom substitute keeps classes, separators, case and script",
          not problems, "; ".join(problems) if problems
          else f"{len(TELECOM_MINT_SOURCES)} sources x25")


def test_telecom_roundtrip_three_legs() -> None:
    """The real value comes back on every OUT shape the product has: prose, a tool
    argument that must still parse, and a streamed chunk. A substitute that fails
    to resolve is a FAKE in the customer's tool with a 200."""
    detector = Detector()
    problems: list[str] = []
    for type_id, _engine, text, value, mechanism in TELECOM_CASED:
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{type_id}/{mechanism}: {value!r} still standing in "
                            f"{masked!r}")
            continue
        if unmask_text(masked, vault) != text:
            problems.append(f"{type_id}/{mechanism}: {text!r} did not come back "
                            f"({unmask_text(masked, vault)!r})")
    check("telecom identifiers round-trip in prose", not problems,
          "; ".join(problems) if problems else f"{len(TELECOM_CASED)} texts")

    problems = []
    for type_id, _engine, text, value, mechanism in TELECOM_CASED:
        if mechanism != "key":
            continue
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        opened = unmask_arguments(masked, vault)
        try:
            json.loads(opened)
        except Exception as exc:                                    # noqa: BLE001
            problems.append(f"{type_id}: the tool argument stopped parsing "
                            f"({exc!r})")
            continue
        if value not in opened:
            problems.append(f"{type_id}: {value!r} did not return ({opened!r})")
    check("telecom identifiers round-trip in a tool argument", not problems,
          "; ".join(problems) if problems else "key samples parse and restore")


def test_telecom_token_shapes() -> None:
    """Every shape `mint_telecom` can be shown in is matched by `token_re` AND by
    the family's own alternation. A token shape that escapes the restorer stops
    being reversible and a FAKE reaches the customer's tool — the invariant the
    checksum family's `TOKEN_PATTERNS` already states.

    THE FAMILY'S OWN SCAN IS LOAD-BEARING HERE, not decorative: a UUID with
    hyphens is matched by the v5 `NAME`/digit patterns AROUND it, so
    `finditer` on `token_re` alone would hand the restorer fragments. That is why
    `TELECOM_TOKEN_RE` exists and why this test asks it directly."""
    problems: list[str] = []
    for label, source in TELECOM_MINT_SOURCES:
        engine = "IP" if label == "IP_ADDRESS" else label
        for _ in range(25):
            token = Vault(":memory:", "shapes").tokenize(source, engine)
            if not token:
                problems.append(f"{label}: no token for {source!r}")
                break
            if not token_re().fullmatch(token):
                problems.append(f"{label}: {token!r} escapes token_re "
                                f"({source!r})")
                break
            if not v6.TELECOM_TOKEN_RE.fullmatch(token):
                problems.append(f"{label}: {token!r} escapes TELECOM_TOKEN_RE "
                                f"({source!r})")
                break
    check("every telecom token shape is matchable", not problems,
          "; ".join(problems) if problems
          else f"{len(TELECOM_MINT_SOURCES)} sources x25")


def test_telecom_reformatted_substitute_resolves() -> None:
    """THE AGENT'S NOTATION IS NOT OUR TOKEN'S. A model lower-cases a UUID,
    rewrites a MAC's separators and re-cases an IPv6 address; none of those
    changes the content, so every one of them must still resolve by the family's
    CONTENT signature (`telecom_signature`). The fake is read from the text that
    was actually masked — never re-minted — so the test measures the production
    path."""
    detector = Detector()
    problems: list[str] = []
    for engine, text, value, rewrite in (
            ("MOBILE_AD_ID", "GAID 6D92078A-8246-4CA4-AE5C-76104861E7DC",
             "6D92078A-8246-4CA4-AE5C-76104861E7DC", lambda t: t.lower()),
            ("MAC", "MAC 00:1A:2B:3C:4D:5E", "00:1A:2B:3C:4D:5E",
             lambda t: t.replace(":", "-")),
            ("MAC", "мак-адрес 001A.2B3C.4D5E", "001A.2B3C.4D5E",
             lambda t: t.replace(".", "-")),
            ("IP", "ip-адрес 2001:db8::1", "2001:db8::1",
             lambda t: t.upper())):
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        head, tail = text[:text.index(value)], text[text.index(value) + len(value):]
        fake = masked[len(head):len(masked) - len(tail)] if tail else masked[len(head):]
        if not fake or fake == value:
            problems.append(f"{engine}: nothing was masked in {text!r}")
            continue
        rewritten = rewrite(fake)
        restored = unmask_text(head + rewritten + tail, vault)

        def content(text: str) -> str:
            return "".join(ch for ch in text.casefold() if ch.isalnum())

        if content(rewritten) == content(restored) or \
                content(value) not in content(restored):
            problems.append(f"{engine}: fake {fake!r} rewritten {rewritten!r} -> "
                            f"{restored!r}")
    check("a reformatted telecom substitute resolves", not problems,
          "; ".join(problems) if problems else "4 rewrites")


def test_telecom_same_hex_is_one_device_and_a_different_one_is_not() -> None:
    """THE SIGNATURE IS CONTENT, SEPARATORS AND CASE INCLUDED. `00:1A:…`,
    `00-1a-…`, `001A.…` and the Cyrillic-typed twins are ONE device, while a
    one-hex-digit change is a DIFFERENT one — and a digit-only signature would let
    two devices that share a digit run answer for each other."""
    problems: list[str] = []
    one = v6.telecom_signature("00:1A:2B:3C:4D:5E", "MAC")
    for other in ("00-1a-2b-3c-4d-5e", "001A.2B3C.4D5E",
                  "00:1А:2В:3С:4D:5Е"):
        if v6.telecom_signature(other, "MAC") != one:
            problems.append(f"{other!r} is not the same device as {one!r}")
    if v6.telecom_signature("00:1A:2B:3C:4D:5F", "MAC") == one:
        problems.append("a one-character change did not change the device")
    check("one device has one signature and a different one has another",
          not problems, "; ".join(problems) if problems else "1 device, 1 twins")


def test_telecom_recorded_label_is_among_the_readings() -> None:
    """THE AMBIGUITY IS MEASURED, NOT HOPED AWAY. Six records share five shapes, so
    one spelling can be several labels — and the restorer keeps a hit only when
    the vault's recorded label is among the readings of the spelling. This test
    asserts, for every mint source, that the label the vault WOULD record is in
    `telecom_signatures`, which is exactly the condition the lookup depends on."""
    problems: list[str] = []
    for label, source in TELECOM_MINT_SOURCES:
        readings = {_telecom_type(name)
                    for name, _sig in v6.telecom_signatures(source)}
        if label not in readings and not (
                label == "APP_DEVICE_ID" and v6.v6_uuid_squeezed(source)):
            problems.append(f"{source!r}: {label} is not among "
                            f"{sorted(readings)}")
    # …and the two readings that ARE genuinely ambiguous are recorded.
    ambiguous = {name for name, _sig in v6.telecom_signatures("1000123456")}
    if not {"ESIA_OID", "SUBSCRIBER_ACCOUNT"} <= ambiguous:
        problems.append("the 10-digit reading is not recorded as ambiguous")
    readings_18 = {name for name, _sig in v6.telecom_signatures("123456789012345678")}
    if not {"APP_DEVICE_ID", "METRICA_CLIENT_ID"} <= readings_18:
        problems.append("the 18-digit reading is not recorded as ambiguous")
    check("the recorded label is among the readings of every source",
          not problems, "; ".join(problems) if problems
          else f"{len(TELECOM_MINT_SOURCES)} sources, 2 ambiguities recorded")


def test_telecom_no_fuzzy_numerals() -> None:
    """A ONE-CHARACTER CHANGE IS A DIFFERENT VALUE, AND NOTHING FUZZY MAY JOIN
    THEM. The registry's `needle_kinds` say `whole`/`digits`; nothing here may
    reach a neighbour by distance, or two subscribers would answer for each
    other's account."""
    problems: list[str] = []
    base = "123456789012"
    for other in ("123456789013", "223456789012", "12345678901"):
        if v6.telecom_signature(other) == v6.telecom_signature(base):
            problems.append(f"{other!r} collapses onto {base!r}")
    for other in ("6D92078A-8246-4CA4-AE5C-76104861E7DC",
                  "6D92078A-8246-4CA4-AE5C-76104861E7DD"):
        pass
    if v6.telecom_signature("6D92078A-8246-4CA4-AE5C-76104861E7DC") == \
            v6.telecom_signature("6D92078A-8246-4CA4-AE5C-76104861E7DD"):
        problems.append("two UUIDs differing in one character share a signature")
    detector = Detector()
    for text, value, engine in (("лицевой счёт 123456789012", "123456789012",
                                 "SUBSCRIBER_ACCOUNT"),
                                ("IMSI 250991234567890", "250991234567890",
                                 "IMSI")):
        if not _found(detector, text, engine, value):
            problems.append(f"{value!r} is not recognized at all")
    check("a one-character change is a different value", not problems,
          "; ".join(problems) if problems else "no fuzzy join")


def test_telecom_unresolved_substitute_is_named() -> None:
    """AN UNRESOLVED SUBSTITUTE MUST BE VISIBLE, NOT TRUSTED.

    A well-formed JSON body or a fluent sentence with a FAKE in it is otherwise
    indistinguishable from a correct one, so the product names what it could not
    resolve. The residual is sharper than «the value did not come back»: what is
    reported is a substitute THIS RUN MINTED and that is still standing (see the
    rule in `redact.surviving_substitutes`), so the candidate has to be a real
    mint of this vault.

    THE WITNESS HERE IS EXACTLY THAT: mint THIS vault's substitute for the value,
    then hand the restorer the substitute of a DIFFERENT value of the same type.
    It is ours by origin, it is shape-valid, it resolves to nothing — and the
    residual must name it rather than leave a plausible-looking fake in the
    customer's field."""
    detector = Detector()
    problems: list[str] = []
    for type_id, engine, text, value, _mechanism in TELECOM_CASED:
        if engine not in ("MAC", "MOBILE_AD_ID", "APP_DEVICE_ID", "IP"):
            continue
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        head, tail = text[:text.index(value)], text[text.index(value) + len(value):]
        # a substitute THIS vault minted, for a value it did not mint it for
        stray = vault.tokenize(
            {"MAC": "AA:BB:CC:DD:EE:FF",
             "MOBILE_AD_ID": "11111111-2222-3333-4444-555555555555",
             "APP_DEVICE_ID": "111111111122222222",
             "IP": "10.20.30.40"}[engine], engine)
        if not stray or stray == value:
            problems.append(f"{type_id}: could not obtain a stray substitute")
            continue
        restored = unmask_text(head + stray + tail, vault)
        residual = surviving_substitutes(head + stray + tail, restored, vault, False)
        if stray in restored and not residual:
            problems.append(f"{type_id}: the stray substitute {stray!r} was "
                            f"neither restored nor named")
    check("an unresolved telecom substitute is named as a residual",
          not problems, "; ".join(problems) if problems else "4 shapes")


def test_telecom_no_overmask(detector: Detector) -> None:
    """A WORD WITHOUT A NUMBER MASKS NOTHING. This family's cues are ordinary
    Russian words and its shapes are digit runs, so the two together are where an
    over-mask would live."""
    problems = [text for text in TELECOM_NEGATIVES
                if any(span.entity_type in v6.TELECOM_LABELS
                       for span in detector.detect(text))]
    check("a telecom cue with no value masks nothing", not problems,
          "; ".join(problems) if problems else f"{len(TELECOM_NEGATIVES)} texts")


def test_telecom_shapes_do_not_steal_the_other_families() -> None:
    """FIVE FAMILIES, ONE PIPELINE. This family's shapes are digit runs and hex,
    so they would claim any number another family already matched — a 20-digit
    account, a 16-digit ОМС, a 10-digit ИНН, a 15-digit ОГРНИП, an IMEI. The
    samples of every family still round-trip with the telecom shapes present."""
    detector = Detector()
    problems: list[str] = []
    for text, value in (
            ("счёт 40817810099910004312", "40817810099910004312"),
            ("ОМС 6613186091390990", "6613186091390990"),
            ("ИНН 7707083893", "7707083893"),
            ("СНИЛС 112-233-445 95", "112-233-445 95"),
            ("IMEI 526018159083010", "526018159083010"),
            ("ICCID 6030824628194821990", "6030824628194821990"),
            ("ОГРНИП 231948757491188", "231948757491188"),
            ("загранпаспорт 75 1234567", "75 1234567"),
            ("СТС 77 12 345678", "77 12 345678"),
            ("военный билет АК № 1234567", "АК № 1234567"),
            ("ИП № 1234567/25/77001-ИП", "1234567/25/77001-ИП"),
            ("кадастровый номер 77:01:0001001:1234", "77:01:0001001:1234"),
            ("УИД 77OS0000-02-2026-000001-52", "77OS0000-02-2026-000001-52"),
            ("полис ДМС 001SB12345678", "001SB12345678"),
            ("полис ОСАГО ХХХ 0123456789", "ХХХ 0123456789"),
            ("VIN 952SVA0422CF17579", "952SVA0422CF17579"),
            ("IBAN RU9404980574640602810700000000025",
             "RU9404980574640602810700000000025")):
        vault = _vault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{value!r} still standing in {masked!r}")
            continue
        if value not in unmask_text(masked, vault):
            problems.append(f"{value!r} did not come back "
                            f"({unmask_text(masked, vault)!r})")
    check("the telecom shapes do not steal the other families' values",
          not problems, "; ".join(problems) if problems else "18 round trips")


def test_telecom_key_typed_spelling_stays_reversible() -> None:
    """A FIELD KEY TYPES THE WHOLE VALUE WITH NO SHAPE CHECK, so a value can arrive
    in a spelling no telecom shape admits. The mint then answers from the
    registry's SAMPLE (correctly — it must not echo the source), and a mirrored
    sample that escaped every shape would be a fake the restorer can never see.
    The guard is the family's own shape question; this measures it over spellings
    INSIDE and OUTSIDE the accepted set."""
    detector = Detector()
    problems: list[str] = []
    for label, value in (("MAC", "001A2B3C4D5E"),
                         ("MAC", "00 1A 2B 3C 4D 5E"),
                         ("MAC", "00.1A.2B.3C.4D.5E"),
                         ("IMSI", "250991234567890"),
                         ("IP_ADDRESS", "2001:DB8::1"),
                         ("MOBILE_AD_ID", "6D92078A82464CA4AE5C76104861E7DC")):
        vault = _vault()
        engine = "IP" if label == "IP_ADDRESS" else label
        token = vault.tokenize(value, engine)
        if not token_re().fullmatch(token):
            problems.append(f"{label}: {value!r} minted {token!r}, which escapes "
                            f"token_re")
        elif not v6.TELECOM_TOKEN_RE.fullmatch(token):
            problems.append(f"{label}: {value!r} minted {token!r}, which escapes "
                            f"TELECOM_TOKEN_RE")
        elif token == value:
            problems.append(f"{label}: the fake equals the source {value!r}")
    payload = '{"mac_address": "00.1A.2B.3C.4D.5E"}'
    vault = _vault()
    spans = detector.detect(payload)
    if not any(span.entity_type == "MAC" for span in spans):
        problems.append(f"the key did not type the value "
                        f"({_types_found(detector, payload)})")
    else:
        opened = unmask_arguments(mask_text(payload, vault, spans), vault)
        if "00.1A.2B.3C.4D.5E" not in opened:
            problems.append(f"the key-typed value did not resolve: {opened!r}")
    check("a key-typed telecom spelling stays reversible", not problems,
          "; ".join(problems) if problems else "6 spellings + 1 payload")


def test_telecom_uuid_in_json_key_round_trips() -> None:
    """THE KEY PATH READS THE RAW VALUE, AND THIS PIN FAILS IF THE SEAM GOES.

    `detect_structured_kv` read the NORMALIZED text, and `normalize()` folds digit
    look-alikes inside any run holding five or more real digits — a UUID is such a
    run, so its `B` became `8` BEFORE the key path saw it. The MASK was safe (a
    substitute stood where the value stood) but the vault held the folded string,
    so the customer's tool received `…AE58…` for a value written `…AE5B…`.

    The Lead's integration closed it in two places, and both are asserted here:
    `detect_all` hands the RAW text to the key path (`structured.detect_structured_kv`),
    and `ru_pii.detect_structured` supersedes the folded cue reading for every
    family the raw entry point answers for. The REWRITTEN leg is asserted
    separately because the copied leg is served by `shown_forms` for some
    spellings and would have hidden the defect. Reverting either half is RED."""
    detector = Detector()
    raw = "6D92078A-8246-4BA4-AE5B-76104861E7DC"
    cases = (
        (f'{{"google_aid": "{raw}"}}', raw),
        (f'{{"device_id": "{raw}"}}', raw),
        (f'{{"customer_id": "{raw}"}}', raw),
        ("GAID " + raw, raw),
        ("идентификатор устройства " + raw, raw),
        ("customer id 6D92078A-8246-4CA4-AE5B-76104861E7DC",
         "6D92078A-8246-4CA4-AE5B-76104861E7DC"),
        ("логин lO12345", "lO12345"),
    )
    problems: list[str] = []
    for text, value in cases:
        vault = Vault(":memory:", "n1-telecom-raw").for_conversation("conv-1")
        masked = mask_text(text, vault, detector.detect(text))
        copied = unmask_text(masked, vault)
        if copied != text:
            problems.append(f"the copied leg lost the literal: {text!r} -> {copied!r}")
        # A substitute the agent re-types: read the fake out of what was actually
        # masked (never re-minted), drop the separators, and restore.
        head, tail = text[:text.index(value)], text[text.index(value) + len(value):]
        fake = masked[len(head):len(masked) - len(tail)] if tail else masked[len(head):]
        if not fake or fake == value:
            problems.append(f"nothing was masked in {text!r}")
            continue
        rewritten = "".join(ch for ch in fake if ch.isalnum())
        restored = unmask_text(head + rewritten + tail, vault)
        if _alnum(value).casefold() not in _alnum(restored).casefold():
            problems.append(f"the rewritten leg did not restore the value: "
                            f"{text!r}, fake {fake!r} -> {restored!r}")
    check("a UUID behind a key or a cue round-trips on the raw reading",
          not problems, "; ".join(problems) if problems
          else f"{len(cases)} spellings, copied and rewritten")


# ================================================================== utility ===
#
# THE SIXTH FAMILY: the twelve utility / account / education / travel records —
# GIS_ZHKH_ELS, UTILITY_ACCOUNT, CDP_CUSTOMER_ID, LOGIN, DIPLOMA_NUMBER,
# SCHOOL_CERT_NUMBER, STUDENT_ID_NUMBER, ACCESS_PASS_NUMBER,
# EMPLOYEE_TAB_NUMBER, EMPLOYMENT_CONTRACT_NUMBER, PNR, E_TICKET_NUMBER. None
# carries a checksum, three are `ГРАММАТИКА?` and two carry a `pd_context`;
# every one of those facts is asserted here rather than assumed.
#
# (type_id, engine label, text, value, mechanism) — the engine label is the
# registry's own type id for all twelve (`engine_labels == ()`), so the two
# columns are equal on purpose and the metric can separate the types.
UTILITY_CASED: list[tuple[str, str, str, str, str]] = [
    ("GIS_ZHKH_ELS", "GIS_ZHKH_ELS", "ЕЛС 60АА000593-01",
     "60АА000593-01", "cue"),
    ("GIS_ZHKH_ELS", "GIS_ZHKH_ELS",
     "единый лицевой счёт 60АА000593-01-2024", "60АА000593-01-2024", "cue"),
    ("GIS_ZHKH_ELS", "GIS_ZHKH_ELS", "идентификатор ЖКУ 60АА000593-01",
     "60АА000593-01", "cue"),
    ("GIS_ZHKH_ELS", "GIS_ZHKH_ELS", '{"els": "60АА000593-01"}',
     "60АА000593-01", "key"),
    # A CYRILLIC SERIES WHOSE LETTERS ARE DIGIT LOOK-ALIKES. `normalize()` folds
    # «60ВВ000593-01» to «6088000593-01»; the shape requires letters in the series
    # slots precisely so the folded spelling cannot match, and the family's raw
    # path is the reading that keeps the customer's own value.
    ("GIS_ZHKH_ELS", "GIS_ZHKH_ELS", "ЕЛС 60ВВ000593-01",
     "60ВВ000593-01", "cue-raw"),
    ("UTILITY_ACCOUNT", "UTILITY_ACCOUNT", "ЖКХ 1234567890",
     "1234567890", "cue"),
    ("UTILITY_ACCOUNT", "UTILITY_ACCOUNT", "л/с 12-34АБ", "12-34АБ", "cue"),
    ("UTILITY_ACCOUNT", "UTILITY_ACCOUNT", "абонентский номер АБ-123456",
     "АБ-123456", "cue"),
    ("UTILITY_ACCOUNT", "UTILITY_ACCOUNT", '{"abonent_id": "1234567890"}',
     "1234567890", "key"),
    ("UTILITY_ACCOUNT", "UTILITY_ACCOUNT", '{"лицевой_счет": "12-34АБ"}',
     "12-34АБ", "key"),
    ("CDP_CUSTOMER_ID", "CDP_CUSTOMER_ID", "ID клиента c-000184523",
     "c-000184523", "cue"),
    ("CDP_CUSTOMER_ID", "CDP_CUSTOMER_ID", '{"customer_id": "c-000184523"}',
     "c-000184523", "key"),
    ("CDP_CUSTOMER_ID", "CDP_CUSTOMER_ID", '{"external_id": "123456789"}',
     "123456789", "key"),
    ("LOGIN", "LOGIN", "логин ivanov_d85", "ivanov_d85", "cue"),
    ("LOGIN", "LOGIN", "имя пользователя a.b-c", "a.b-c", "cue"),
    ("LOGIN", "LOGIN", '{"username": "ivanov_d85"}', "ivanov_d85", "key"),
    ("DIPLOMA_NUMBER", "DIPLOMA_NUMBER", "диплом 107724 0001234",
     "107724 0001234", "cue"),
    ("DIPLOMA_NUMBER", "DIPLOMA_NUMBER", "бланк диплома 1077240001234",
     "1077240001234", "cue"),
    ("DIPLOMA_NUMBER", "DIPLOMA_NUMBER",
     '{"diploma_number": "107724 0001234"}', "107724 0001234", "key"),
    ("SCHOOL_CERT_NUMBER", "SCHOOL_CERT_NUMBER", "аттестат 07705000012345",
     "07705000012345", "cue"),
    ("SCHOOL_CERT_NUMBER", "SCHOOL_CERT_NUMBER",
     "номер аттестата 07705000012345", "07705000012345", "cue"),
    ("SCHOOL_CERT_NUMBER", "SCHOOL_CERT_NUMBER",
     '{"attestat_number": "07705000012345"}', "07705000012345", "key"),
    ("STUDENT_ID_NUMBER", "STUDENT_ID_NUMBER", "студенческий билет 21-0345",
     "21-0345", "cue"),
    ("STUDENT_ID_NUMBER", "STUDENT_ID_NUMBER",
     '{"student_id": "21-0345"}', "21-0345", "key"),
    ("ACCESS_PASS_NUMBER", "ACCESS_PASS_NUMBER", "пропуск 0034561",
     "0034561", "cue"),
    ("ACCESS_PASS_NUMBER", "ACCESS_PASS_NUMBER", "бейдж 1A2B3C4D",
     "1A2B3C4D", "cue"),
    ("ACCESS_PASS_NUMBER", "ACCESS_PASS_NUMBER", '{"badge_id": "0034561"}',
     "0034561", "key"),
    ("EMPLOYEE_TAB_NUMBER", "EMPLOYEE_TAB_NUMBER", "табельный номер 004512",
     "004512", "cue"),
    ("EMPLOYEE_TAB_NUMBER", "EMPLOYEE_TAB_NUMBER", "табельный 0000-00412",
     "0000-00412", "cue"),
    ("EMPLOYEE_TAB_NUMBER", "EMPLOYEE_TAB_NUMBER", '{"tab_number": "004512"}',
     "004512", "key"),
    ("EMPLOYMENT_CONTRACT_NUMBER", "EMPLOYMENT_CONTRACT_NUMBER",
     "трудовой договор 145-ТД", "145-ТД", "cue"),
    ("EMPLOYMENT_CONTRACT_NUMBER", "EMPLOYMENT_CONTRACT_NUMBER",
     "номер трудового договора ТД-2024/017", "ТД-2024/017", "cue"),
    ("EMPLOYMENT_CONTRACT_NUMBER", "EMPLOYMENT_CONTRACT_NUMBER",
     '{"labor_contract_no": "145-ТД"}', "145-ТД", "key"),
    ("PNR", "PNR", "PNR 2ZYVAL", "2ZYVAL", "cue"),
    ("PNR", "PNR", "код бронирования 2ZYVAL", "2ZYVAL", "cue"),
    ("PNR", "PNR", '{"pnr": "2ZYVAL"}', "2ZYVAL", "key"),
    ("E_TICKET_NUMBER", "E_TICKET_NUMBER", "электронный билет 5552412345678",
     "5552412345678", "cue"),
    ("E_TICKET_NUMBER", "E_TICKET_NUMBER", '{"ticket_number": "5552412345678"}',
     "5552412345678", "key"),
]

# The registry's own samples with NO cue and NO key. `bare_typed=False` on all
# twelve, so none of them may be typed by THIS family.
UTILITY_BARE: tuple[tuple[str, str], ...] = (
    ("60АА000593-01", "GIS_ZHKH_ELS"),
    ("1234567890", "UTILITY_ACCOUNT"),
    ("c-000184523", "CDP_CUSTOMER_ID"),
    ("ivanov_d85", "LOGIN"),
    ("107724 0001234", "DIPLOMA_NUMBER"),
    ("07705000012345", "SCHOOL_CERT_NUMBER"),
    ("21-0345", "STUDENT_ID_NUMBER"),
    ("0034561", "ACCESS_PASS_NUMBER"),
    ("004512", "EMPLOYEE_TAB_NUMBER"),
    ("145-ТД", "EMPLOYMENT_CONTRACT_NUMBER"),
    ("2ZYVAL", "PNR"),
    ("5552412345678", "E_TICKET_NUMBER"),
)

# A CUE (OR A KEY) WITH NO VALUE. Over-masking is what the customer sees first,
# and these cues are ordinary Russian words.
UTILITY_NEGATIVES: tuple[str, ...] = (
    "ЕЛС уточните в квитанции",
    "единый лицевой счёт закрыт",
    "идентификатор ЖКУ не найден",
    "идентификатор платёжного документа уточняется",
    "л/с уточните в приложении",
    "ЖКХ 2024",
    "ID клиента не задан",
    "клиентский ID уточняется",
    "логин забыт",
    "имя пользователя уточните",
    "диплом выдан в 2024 году",
    "аттестат о среднем общем образовании",
    "студенческий билет потерян",
    "пропуск на 2024 год",
    "карта доступа не работает",
    "табельный номер уточняется",
    "трудовой договор расторгнут 01.01.2024",
    "номер трудового договора уточняется",
    "PNR не найден",
    "номер брони уточните",
    "номер билета смотрите в письме",
    "заказ 1234567890 от 15.05.2025",
    "артикул 123456789012",
    "версия 95.165.12",
    "серия 1234 номер 567890",
    "счёт 40817810099910004312",
)

# An IMPLAUSIBLE value behind its own cue. There is no checksum to reject it and
# the cue IS the evidence (COV-TYPED-INVALID), so every one must stay protected —
# a family that grew a validator for an arithmetic-free record would send them to
# the model in the clear.
UTILITY_TYPED_INVALID: tuple[tuple[str, str, str], ...] = (
    ("GIS_ZHKH_ELS", "ЕЛС 00ЯЯ000000-00", "00ЯЯ000000-00"),
    ("UTILITY_ACCOUNT", "ЖКХ 000000000000", "000000000000"),
    ("CDP_CUSTOMER_ID", "ID клиента c-000000000", "c-000000000"),
    ("LOGIN", "логин user0000", "user0000"),
    ("DIPLOMA_NUMBER", "диплом 100000 0000000", "100000 0000000"),
    ("SCHOOL_CERT_NUMBER", "аттестат 00000000000000", "00000000000000"),
    ("STUDENT_ID_NUMBER", "студенческий билет 00-0000", "00-0000"),
    ("ACCESS_PASS_NUMBER", "пропуск 0000000", "0000000"),
    ("EMPLOYEE_TAB_NUMBER", "табельный номер 000000", "000000"),
    ("EMPLOYMENT_CONTRACT_NUMBER", "трудовой договор 0000-ТД", "0000-ТД"),
    ("PNR", "PNR 0A000A", "0A000A"),
    ("E_TICKET_NUMBER", "электронный билет 0000000000000", "0000000000000"),
)

# One source per label, in the notations the record's own grammar names.
# (`case_exact`: whether the mint must keep the source's letter CASE character by
# character — false only for the mixed-case UUID, where the shared
# `render_like_atomic` capitalises a hyphen group's head, exactly as it does for
# the telecom family's UUIDs.)
UTILITY_MINT_SOURCES: list[tuple[str, str, bool]] = [
    ("GIS_ZHKH_ELS", "60АА000593-01", True),
    ("GIS_ZHKH_ELS", "60АА000593", True),
    ("GIS_ZHKH_ELS", "60АА000593-01-2024", True),
    ("UTILITY_ACCOUNT", "1234567890", True),
    ("UTILITY_ACCOUNT", "12-34АБ", True),
    ("UTILITY_ACCOUNT", "АБ-123456", True),
    ("CDP_CUSTOMER_ID", "c-000184523", True),
    ("CDP_CUSTOMER_ID", "6D92078A-8246-4CA4-AE5B-76104861E7DC", False),
    ("CDP_CUSTOMER_ID", "123456789", True),
    ("LOGIN", "ivanov_d85", True),
    ("LOGIN", "a.b-c", True),
    ("DIPLOMA_NUMBER", "107724 0001234", True),
    ("DIPLOMA_NUMBER", "1077240001234", True),
    ("SCHOOL_CERT_NUMBER", "07705000012345", True),
    ("STUDENT_ID_NUMBER", "21-0345", True),
    ("STUDENT_ID_NUMBER", "210345", True),
    ("ACCESS_PASS_NUMBER", "0034561", True),
    ("ACCESS_PASS_NUMBER", "1A2B3C4D", True),
    ("ACCESS_PASS_NUMBER", "1A2B3C4D5E6F70", True),
    ("EMPLOYEE_TAB_NUMBER", "004512", True),
    ("EMPLOYEE_TAB_NUMBER", "0000-00412", True),
    ("EMPLOYMENT_CONTRACT_NUMBER", "145-ТД", True),
    ("EMPLOYMENT_CONTRACT_NUMBER", "ТД-2024/017", True),
    ("PNR", "2ZYVAL", True),
    ("E_TICKET_NUMBER", "5552412345678", True),
]


def _uvault() -> Vault:
    return Vault(":memory:", "n1-utility")


def _alpha_script(char: str) -> str:
    return "cyr" if "\u0400" <= char <= "\u04FF" else "lat"


def test_utility_registry_facts_are_recorded() -> None:
    """THE FAMILY'S OWN FACTS, ASSERTED RATHER THAN ASSUMED.

    None of the twelve carries a checksum, so no validator may be invented and the
    mint must be TOTAL over junk rather than raising. THREE records are
    `ГРАММАТИКА?` (`UTILITY_GRAMMAR_UNASSERTED`) and TWO carry a `pd_context`
    («indirect; premises payer account») — the two `pd_context` rules are RECORDED
    and NOT implemented, because no premises/owner signal exists in this pipeline
    and a fabricated discriminator is the failure GOAL-BRIEF §7 forbids.

    THE DIGIT-ONLY SET IS READ FROM THE SHAPES, NOT FROM A HAND LIST: a label may
    sit in `UTILITY_DIGIT_LABELS` only when no value its shape accepts contains a
    letter, which is what makes the plain digit key safe for it."""
    problems: list[str] = []
    if len(v6.UTILITY_TYPES) != 12:
        problems.append(f"{len(v6.UTILITY_TYPES)} utility types, expected 12")
    unasserted = sorted(v6.UTILITY_GRAMMAR_UNASSERTED)
    if unasserted != ["E_TICKET_NUMBER", "PNR", "STUDENT_ID_NUMBER"]:
        problems.append(f"ГРАММАТИКА? records are {unasserted}")
    if sorted(v6.UTILITY_PD_CONTEXT) != ["GIS_ZHKH_ELS", "UTILITY_ACCOUNT"]:
        problems.append(f"pd_context records are {sorted(v6.UTILITY_PD_CONTEXT)}")
    for type_id in v6.UTILITY_TYPES:
        if hasattr(v6, f"validate_{type_id.lower()}"):
            problems.append(f"{type_id}: an invented validator exists")
    for junk in ("", "   ", "абв", "0", "-", "№", "х" * 40, "?!№", "нет данных"):
        for type_id in v6.UTILITY_TYPES:
            try:
                if not v6.mint_utility(type_id, junk):
                    problems.append(f"{type_id}: total mint returned nothing for "
                                    f"{junk!r}")
            except Exception as exc:                                # noqa: BLE001
                problems.append(f"{type_id}: mint raised on {junk!r}: {exc!r}")
    # THE FIVE DIGIT-ONLY LABELS HAVE NO LETTER IN THE SHAPE THAT PRODUCES THEM.
    for type_id in v6.UTILITY_DIGIT_LABELS:
        letters = [c for c in v6._UTILITY_SHAPE_TEXT[type_id]
                   if c.isalpha() and c not in "АЯЁаяёAZtz"]
        # the shape text mentions letters only in classes; a *value* is what
        # matters, so ask the shape over a battery of samples and mutations.
        for sample in (v6.UTILITY_SAMPLE[type_id],):
            pattern = v6.UTILITY_SHAPES[type_id]
            if not pattern.fullmatch(sample):
                problems.append(f"{type_id}: its own sample is not its shape")
            if any(ch.isalpha() for ch in sample):
                problems.append(f"{type_id}: a digit-only label has a letter in "
                                f"its sample {sample!r}")
    if v6.UTILITY_DIGIT_LABELS & v6.UTILITY_ATOMIC_LABELS:
        problems.append("the digit-only and letter-bearing sets overlap")
    if v6.UTILITY_DIGIT_LABELS | v6.UTILITY_ATOMIC_LABELS != v6.UTILITY_LABELS:
        problems.append("the two identity sets do not cover the twelve")
    if not set(v6.UTILITY_SAMPLE) == set(v6.UTILITY_TYPES):
        problems.append("a registry sample is missing")
    if set(v6.UTILITY_DIGIT_COUNTS) - set(v6.UTILITY_TYPES):
        problems.append("a digit bound names an unknown type")
    check("the utility registry facts are recorded and no validator is invented",
          not problems, "; ".join(problems) if problems
          else f"12 types, {len(unasserted)} unasserted, "
               f"{len(v6.UTILITY_PD_CONTEXT)} pd_context recorded")


def test_utility_cued_and_keyed(detector: Detector) -> None:
    """Cue context and field-key context both type the value, on the REAL pipeline
    (`Detector.detect`), with the registry's own label (no aliases)."""
    problems: list[str] = []
    for type_id, engine, text, value, mechanism in UTILITY_CASED:
        if not _found(detector, text, engine, value):
            problems.append(f"{type_id}/{mechanism}: {text!r} -> "
                            f"{_types_found(detector, text)}")
    check("utility identifiers are recognized by cue and by field key",
          not problems, "; ".join(problems) if problems
          else f"{len(UTILITY_CASED)} texts")


def test_utility_typed_invalid_no_gate(detector: Detector) -> None:
    """COV-TYPED-INVALID FOR AN ARITHMETIC-FREE RECORD: the cue is the evidence,
    so an all-zero ЕЛС or a zero RFID UID behind its own cue is still the
    customer's value."""
    problems = [text for _label, text, _value in UTILITY_TYPED_INVALID
                if not any(span.entity_type in v6.UTILITY_LABELS
                           for span in detector.detect(text))]
    check("an implausible utility value behind its cue is still protected",
          not problems, "; ".join(problems) if problems
          else f"{len(UTILITY_TYPED_INVALID)} negatives")


def test_utility_bare_is_not_typed(detector: Detector) -> None:
    """`bare_typed=False` ON ALL TWELVE, READ PER TYPE: not one bare sample may be
    typed by this family."""
    problems = [value for value, _label in UTILITY_BARE
                if any(span.entity_type in v6.UTILITY_LABELS
                       for span in detector.detect(f"значение {value} конец"))]
    check("a bare utility sample is not typed by this family", not problems,
          "; ".join(problems) if problems else f"{len(UTILITY_BARE)} samples")


def test_utility_mint_is_format_preserving() -> None:
    """THE SUBSTITUTE KEEPS THE SOURCE'S FORMAT: separator layout, character
    classes (digit position by digit position), letter case, script and the
    label's own shape. There is no checksum to inherit, so format is the whole
    contract.

    THREE FACTS ARE PER-LABEL AND ASSERTED AS THE FAMILY'S RULE rather than the
    document families':
      * a HEX record draws its letters from A–F — a UUID or an RFID UID drawn
        from A–Z stops being hex and stops being a candidate for the restorer;
      * a DIPLOMA keeps its two GRAMMAR digits (the leading «1» and the 0–4
        organisation type): re-drawing them mints a string that is not a diploma
        number at all;
      * a login keeps its dots and underscores, because they are the handle."""
    problems: list[str] = []
    for label, source, case_exact in UTILITY_MINT_SOURCES:
        for _ in range(25):
            fake = v6.mint_utility(label, source)
            if not fake or fake == source:
                problems.append(f"{label}: {source!r} -> {fake!r}")
                break
            if [c for c in fake if not c.isalnum()] != \
                    [c for c in source if not c.isalnum()]:
                problems.append(f"{label}: separators changed {source!r} -> {fake!r}")
                break
            if [c.isdigit() for c in fake] != [c.isdigit() for c in source]:
                problems.append(f"{label}: the digit layout changed "
                                f"{source!r} -> {fake!r}")
                break
            if case_exact and [c.isalpha() for c in fake] != \
                    [c.isalpha() for c in source]:
                problems.append(f"{label}: the letter layout changed "
                                f"{source!r} -> {fake!r}")
                break
            if case_exact and [(_alpha_script(c), c.isupper())
                               for c in fake if c.isalpha()] != \
                    [(_alpha_script(c), c.isupper())
                     for c in source if c.isalpha()]:
                problems.append(f"{label}: script or case changed "
                                f"{source!r} -> {fake!r}")
                break
            if label in ("CDP_CUSTOMER_ID", "ACCESS_PASS_NUMBER") and \
                    not all(c in "0123456789abcdefABCDEF"
                            for c in fake if c.isalnum()):
                problems.append(f"{label}: a non-hex character in {fake!r}")
                break
            if label == "DIPLOMA_NUMBER":
                if fake[0] != "1" or fake[1] not in "01234":
                    problems.append(f"{label}: the grammar digits moved "
                                    f"{source!r} -> {fake!r}")
                    break
            pattern = v6.UTILITY_SHAPES[label]
            if not pattern.fullmatch(fake):
                problems.append(f"{label}: {fake!r} is not its own shape "
                                f"({source!r})")
                break
    check("a utility substitute keeps classes, separators, case and script",
          not problems, "; ".join(problems) if problems
          else f"{len(UTILITY_MINT_SOURCES)} sources x25")


def test_utility_roundtrip_three_legs() -> None:
    """The real value comes back on every OUT shape the product has: prose, a tool
    argument that must still parse, and a streamed chunk. A substitute that fails
    to resolve is a FAKE in the customer's tool with a 200."""
    detector = Detector()
    problems: list[str] = []
    for type_id, _engine, text, value, mechanism in UTILITY_CASED:
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{type_id}/{mechanism}: {value!r} still standing in "
                            f"{masked!r}")
            continue
        if unmask_text(masked, vault) != text:
            problems.append(f"{type_id}/{mechanism}: {text!r} did not come back "
                            f"({unmask_text(masked, vault)!r})")
    check("utility identifiers round-trip in prose", not problems,
          "; ".join(problems) if problems else f"{len(UTILITY_CASED)} texts")

    problems = []
    for type_id, _engine, text, value, mechanism in UTILITY_CASED:
        if mechanism != "key":
            continue
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        opened = unmask_arguments(masked, vault)
        try:
            json.loads(opened)
        except Exception as exc:                                    # noqa: BLE001
            problems.append(f"{type_id}: the tool argument stopped parsing "
                            f"({exc!r})")
            continue
        if value not in opened:
            problems.append(f"{type_id}: {value!r} did not return ({opened!r})")
    check("utility identifiers round-trip in a tool argument", not problems,
          "; ".join(problems) if problems else "key samples parse and restore")

    from pseudex.redact import unmask_stream_chunk
    problems = []
    for type_id, _engine, text, value, _mechanism in UTILITY_CASED:
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        emitted, carry = unmask_stream_chunk(masked + " ", "", vault, flush=True)
        if value not in emitted + carry:
            problems.append(f"{type_id}: the stream leg lost {value!r} "
                            f"({emitted + carry!r})")
    check("utility identifiers round-trip in a streamed chunk", not problems,
          "; ".join(problems) if problems else f"{len(UTILITY_CASED)} texts")


def test_utility_token_shapes() -> None:
    """Every shape `mint_utility` can be shown in is matched by `token_re` AND by
    the family's own alternation. A token shape that escapes the restorer stops
    being reversible and a FAKE reaches the customer's tool — the invariant the
    checksum family's `TOKEN_PATTERNS` already states.

    THE FAMILY'S OWN SCAN IS LOAD-BEARING HERE, not decorative: its patterns stand
    LAST in `vault._token_re` (they are cue/key-typed rather than format-anchored),
    so the ОГРН length claims a thirteen-digit ticket before them."""
    problems: list[str] = []
    for label, source, _case_exact in UTILITY_MINT_SOURCES:
        for _ in range(25):
            token = _uvault().tokenize(source, label)
            if not token:
                problems.append(f"{label}: no token for {source!r}")
                break
            if not token_re().fullmatch(token):
                problems.append(f"{label}: {token!r} escapes token_re "
                                f"({source!r})")
                break
            if not v6.UTILITY_TOKEN_RE.fullmatch(token):
                problems.append(f"{label}: {token!r} escapes UTILITY_TOKEN_RE "
                                f"({source!r})")
                break
    check("every utility token shape is matchable", not problems,
          "; ".join(problems) if problems
          else f"{len(UTILITY_MINT_SOURCES)} sources x25")


def test_utility_reformatted_substitute_resolves() -> None:
    """THE AGENT'S NOTATION IS NOT OUR TOKEN'S. A model strips a login's dot,
    re-cases a ЕЛС series, rewrites a tab number's separator; none of those
    changes the content, so every one must still resolve by the family's CONTENT
    signature (`utility_signature`). The fake is read from the text that was
    actually masked — never re-minted — so the test measures the production
    path."""
    detector = Detector()
    problems: list[str] = []
    for engine, text, value, label, rewrite in (
            ("GIS_ZHKH_ELS", "ЕЛС 60АА000593-01", "60АА000593-01",
             "GIS_ZHKH_ELS", lambda t: t.lower()),
            ("LOGIN", "логин ivanov_d85", "ivanov_d85",
             "LOGIN", lambda t: t.upper()),
            ("EMPLOYEE_TAB_NUMBER", "табельный номер 004512", "004512",
             "EMPLOYEE_TAB_NUMBER", lambda t: t[:3] + "-" + t[3:]),
            ("DIPLOMA_NUMBER", "диплом 107724 0001234", "107724 0001234",
             "DIPLOMA_NUMBER", lambda t: t.replace(" ", "")),
            ("ACCESS_PASS_NUMBER", "бейдж 1A2B3C4D", "1A2B3C4D",
             "ACCESS_PASS_NUMBER", lambda t: t.lower())):
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        head = text[:text.index(value)]
        tail = text[text.index(value) + len(value):]
        fake = masked[len(head):len(masked) - len(tail)] if tail else masked[len(head):]
        if not fake or fake == value:
            problems.append(f"{engine}: nothing was masked in {text!r}")
            continue
        rewritten = rewrite(fake)
        restored = unmask_text(head + rewritten + tail, vault)
        came_back = restored[len(head):len(restored) - len(tail)] if tail else restored[len(head):]
        # THE CONTENT, NOT THE SPELLING: the agent's re-grouping and re-casing are
        # its own notation, and what must not move is the value it names.
        if not came_back or v6.utility_signature(came_back, label) != \
                v6.utility_signature(value, label):
            problems.append(f"{engine}: fake {fake!r} rewritten {rewritten!r} -> "
                            f"{restored!r}")
    check("a reformatted utility substitute resolves", not problems,
          "; ".join(problems) if problems else "5 rewrites")


def test_utility_grammar_unasserted_is_recorded() -> None:
    """THE `ГРАММАТИКА?` RECORDS ARE NAMED, and their shapes are exactly what the
    registry's own samples and grammar notes prove. This test asserts the SET (so
    a reader sees which three, not how many) and that no permissive invented regex
    stands where the registry says the form was not obtained."""
    problems: list[str] = []
    if v6.UTILITY_GRAMMAR_UNASSERTED != frozenset(
            ("STUDENT_ID_NUMBER", "PNR", "E_TICKET_NUMBER")):
        problems.append(f"{sorted(v6.UTILITY_GRAMMAR_UNASSERTED)}")
    # E_TICKET_NUMBER claims ONLY the air form the registry states: thirteen digits.
    if not v6.UTILITY_SHAPES["E_TICKET_NUMBER"].fullmatch("5552412345678"):
        problems.append("the air-ticket form is not claimed")
    if v6.UTILITY_SHAPES["E_TICKET_NUMBER"].fullmatch("555241234567"):
        problems.append("a twelve-digit run is claimed for a rail ticket whose "
                        "numbering the registry does not establish")
    # STUDENT_ID_NUMBER's digit-only reading starts at five: a four-digit YEAR
    # after the cue must stay a year.
    if v6.UTILITY_SHAPES["STUDENT_ID_NUMBER"].fullmatch("2024"):
        problems.append("a four-digit year is claimed as a student id")
    # PNR requires a letter AND a digit: «бронь отеля» is five Cyrillic letters.
    if v6.UTILITY_SHAPES["PNR"].fullmatch("отеля"):
        problems.append("a Cyrillic word is claimed as a booking locator")
    if not v6.UTILITY_SHAPES["PNR"].fullmatch("2ZYVAL"):
        problems.append("the Amadeus sample is not claimed")
    check("the ГРАММАТИКА? utility records are recorded and invented regexes are "
          "absent", not problems, "; ".join(problems) if problems
          else f"{len(v6.UTILITY_GRAMMAR_UNASSERTED)} unasserted")


def test_utility_no_fuzzy_numerals() -> None:
    """A ONE-CHARACTER CHANGE IS A DIFFERENT VALUE, AND NOTHING FUZZY MAY JOIN
    THEM. The registry's `needle_kinds` say `whole`/`digits`/`squeezed`; nothing
    here may reach a neighbour by distance, or two students would answer for each
    other's record."""
    problems: list[str] = []
    for one, other in (
            (v6.utility_signature("60АА000593-01", "GIS_ZHKH_ELS"),
             v6.utility_signature("60АВ000593-01", "GIS_ZHKH_ELS")),
            (v6.utility_signature("2ZYVAL", "PNR"),
             v6.utility_signature("2ZYVAM", "PNR")),
            (v6.utility_signature("21-0345", "STUDENT_ID_NUMBER"),
             v6.utility_signature("21-0346", "STUDENT_ID_NUMBER")),
            (v6.utility_signature("107724 0001234", "DIPLOMA_NUMBER"),
             v6.utility_signature("107724 0001235", "DIPLOMA_NUMBER"))):
        if not one or one == other:
            problems.append(f"{one!r} collapses onto {other!r}")
    # THE SEPARATORS ARE PRESENTATION AND THE LETTERS ARE NOT: one ЕЛС written
    # two ways is one row, and a one-letter change is a different document.
    same = {"60АА000593-01", "60АА000593 01", "60АА00059301"}
    signatures = {v6.utility_signature(v, "GIS_ZHKH_ELS") for v in same}
    if len(signatures) != 1:
        problems.append(f"one ЕЛС in three notations is {len(signatures)} rows")
    # AND THE LABEL IS PART OF THE KEY where the identity is letters.
    if v6.utility_signature("145-ТД", "EMPLOYMENT_CONTRACT_NUMBER") == \
            v6.utility_signature("145-ТД", "UTILITY_ACCOUNT"):
        problems.append("two registry records share one canonical")
    check("a one-character change is a different value", not problems,
          "; ".join(problems) if problems else "no fuzzy join")


def test_utility_notation_both_legs() -> None:
    """P02: THE FORM BELONGS TO THE WRITER, THE CONTENT TO THE VAULT.

    ON THE WAY IN the fake carries the CUSTOMER's separators and case, so a model
    that copies it copies exactly what the customer wrote. ON THE WAY OUT the real
    value comes back in the AGENT's form — a tool argument written in the agent's
    own case or grouping must not hand the customer's stale presentation back.

    THE CASE IS THE NOTATION for a letter-bearing record (its separators are the
    registry's, not the writer's), and the SEPARATORS are the notation for a
    digit-only one; both axes are measured, because each is the only one the other
    cannot see."""
    detector = Detector()
    problems: list[str] = []
    # THE IN LEG runs on a cue, where the customer's own spelling is what the model
    # is shown. THE OUT LEG runs on a FIELD KEY and a TOOL ARGUMENT — the leg where
    # the agent rewrites the substitute in its own form and the value must follow
    # the AGENT, which is the direction the cue path cannot show (there the same
    # real value is also reachable through the cued-number seam).
    cases = [
        ("GIS_ZHKH_ELS", "ЕЛС 60аа000593", "60аа000593", '{"els": "60аа000593"}'),
        ("LOGIN", "логин ivanov_d85", "ivanov_d85",
         '{"username": "ivanov_d85"}'),
        ("EMPLOYMENT_CONTRACT_NUMBER", "трудовой договор 145-тд", "145-тд",
         '{"labor_contract_no": "145-тд"}'),
    ]
    for label, text, customer, payload in cases:
        match = re.search(re.escape(customer), text)
        if match is None:
            problems.append(f"{label}: the fixture does not carry {customer!r}")
            continue
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        fake = masked[match.start():]
        if not fake or fake == customer:
            problems.append(f"{label}: nothing was masked in {text!r}")
            continue
        # THE IN LEG: the customer's separators AND the customer's letter case.
        if [c for c in fake if not c.isalnum()] != \
                [c for c in customer if not c.isalnum()]:
            problems.append(f"{label}: the customer's separators were not shown "
                            f"({customer!r} -> {fake!r})")
        if [c.isupper() for c in fake if c.isalpha()] != \
                [c.isupper() for c in customer if c.isalpha()]:
            problems.append(f"{label}: the customer's case was not shown "
                            f"({customer!r} -> {fake!r})")
        # THE OUT LEG: THE AGENT REWRITES THE FAKE — its own case over the
        # SUBSTITUTE's content, which is the only way this axis is measurable. A
        # check that filled the field with the REAL value could not tell "restored
        # in the agent's form" from "never restored": the agent's string would read
        # as the answer either way. Here the fake's content and the customer's
        # differ, so an unresolved substitute is visible.
        agent_written = fake.upper()
        vault = _uvault()
        masked = mask_text(payload, vault, detector.detect(payload))
        key = list(json.loads(payload))[0]
        # A FIELD KEY THAT WAS CONSUMED AS A VALUE IS A FAILURE, NOT A CRASH: a
        # bare shape (the weakened-context mutation compiles the cues away) can
        # mask the key itself, and a test that raises there reports less than one
        # that names it.
        try:
            opened_fake = json.loads(masked)[key]
        except (ValueError, KeyError):
            problems.append(f"{label}: the field key {key!r} did not survive the "
                            f"mask ({masked!r})")
            continue
        if not opened_fake:
            problems.append(f"{label}: the key did not mask {payload!r}")
            continue
        agent_written = opened_fake.upper()
        opened = unmask_arguments(masked.replace(opened_fake, agent_written), vault)
        back = json.loads(opened)[key]
        if v6.utility_signature(back, label) == \
                v6.utility_signature(opened_fake, label):
            problems.append(f"{label}: the substitute {opened_fake!r} was left "
                            f"standing ({back!r})")
            continue
        if v6.utility_signature(back, label) != v6.utility_signature(customer, label):
            problems.append(f"{label}: the content moved "
                            f"({customer!r} -> {back!r})")
        if [c for c in back if not c.isalnum()] != \
                [c for c in agent_written if not c.isalnum()]:
            problems.append(f"{label}: the agent's separators were dropped "
                            f"({agent_written!r} -> {back!r})")
        if [c.isupper() for c in back if c.isalpha()] != \
                [c.isupper() for c in agent_written if c.isalpha()]:
            problems.append(f"{label}: the agent's case was dropped "
                            f"({agent_written!r} -> {back!r})")
    check("the customer's notation is shown and the agent's is restored",
          not problems, "; ".join(problems) if problems
          else f"{len(cases)} documents, both legs")


def test_utility_unresolved_substitute_is_named() -> None:
    """AN UNRESOLVED SUBSTITUTE MUST BE VISIBLE, NOT TRUSTED.

    The witness is exactly the rule `redact.surviving_substitutes` states: a
    substitute THIS vault minted for a value it did not mint it for, standing
    after restoration, must be named — a well-formed sentence or a parsing JSON
    body with a FAKE in it is otherwise indistinguishable from a correct one."""
    detector = Detector()
    problems: list[str] = []
    strays = {
        "LOGIN": "our_login_1",
        "GIS_ZHKH_ELS": "11АБ223344-55",
        "CDP_CUSTOMER_ID": "c-999888777",
        "EMPLOYMENT_CONTRACT_NUMBER": "777-ТД",
        "PNR": "9ABCDE",
        "DIPLOMA_NUMBER": "107724 9999999",
        "ACCESS_PASS_NUMBER": "99887766",
    }
    for type_id, _engine, text, value, _mechanism in UTILITY_CASED:
        if type_id not in strays:
            continue
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        if value not in text:
            continue
        head, tail = text[:text.index(value)], text[text.index(value) + len(value):]
        stray = vault.tokenize(strays[type_id], type_id)
        if not stray or stray == value:
            problems.append(f"{type_id}: could not obtain a stray substitute")
            continue
        restored = unmask_text(head + stray + tail, vault)
        residual = surviving_substitutes(head + stray + tail, restored, vault, False)
        if stray in restored and not residual:
            problems.append(f"{type_id}: the stray substitute {stray!r} was "
                            f"neither restored nor named")
    check("an unresolved utility substitute is named as a residual",
          not problems, "; ".join(problems) if problems
          else f"{len(strays)} shapes")


def test_utility_no_overmask(detector: Detector) -> None:
    """A CUE WITH NO VALUE MASKS NOTHING. This family's cues are ordinary Russian
    words — «диплом», «пропуск», «бронь» — and its shapes are digit runs and
    handles, so the two together are where an over-mask would live."""
    problems = [text for text in UTILITY_NEGATIVES
                if any(span.entity_type in v6.UTILITY_LABELS
                       for span in detector.detect(text))]
    check("a utility cue with no value masks nothing", not problems,
          "; ".join(problems) if problems else f"{len(UTILITY_NEGATIVES)} texts")


def test_utility_shared_cue_arbitration_is_recorded(detector: Detector) -> None:
    """THE ONE CUE TWO REGISTRY RECORDS SHARE, AND THE READING THAT WINS.

    `SUBSCRIBER_ACCOUNT` (telecom) and `UTILITY_ACCOUNT` (this family) both carry
    «лицевой счёт», «л/с», «ЛС» and the same 6–12 digit space — the registry
    declares two records for one phrase, one per industry. The telecom entry
    stands earlier in the leased `CTX_TYPES`, so an exact tie answers
    `SUBSCRIBER_ACCOUNT`; this family's shot at the same words is the
    LETTER-BEARING form the telecom shape cannot read, and its own cue «ЖКХ».
    Pinning the arbitration keeps it a recorded decision instead of an accident —
    and making this family win the digit run is a PRIORITY question for the Lead's
    table, not an edit in the lease."""
    problems: list[str] = []
    for text, value, want in (
            ("лицевой счёт 123456789012", "123456789012", "SUBSCRIBER_ACCOUNT"),
            ("л/с 12345678", "12345678", "SUBSCRIBER_ACCOUNT"),
            ("ЖКХ 1234567890", "1234567890", "UTILITY_ACCOUNT"),
            ("л/с 12-34АБ", "12-34АБ", "UTILITY_ACCOUNT"),
            ("абонентский номер АБ-123456", "АБ-123456", "UTILITY_ACCOUNT"),
            ('{"abonent_id": "1234567890"}', "1234567890", "UTILITY_ACCOUNT")):
        found = _found(detector, text, want, value)
        if not found:
            problems.append(f"{text!r}: {want} did not answer "
                            f"({_types_found(detector, text)})")
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{text!r}: the value leaked ({masked!r})")
        elif value not in unmask_text(masked, vault):
            problems.append(f"{text!r}: did not restore "
                            f"({unmask_text(masked, vault)!r})")
    check("the shared «лицевой счёт» cue is arbitrated and recorded",
          not problems, "; ".join(problems) if problems
          else "6 texts, telecom keeps the digit run")


def test_utility_shapes_do_not_steal_the_other_families() -> None:
    """SIX FAMILIES, ONE PIPELINE. This family's digit runs and handles would
    claim any number another family already matched — a 20-digit account, a
    16-digit ОМС, a 10-digit ИНН, a 15-digit ОГРНИП, a MAC — and its keys would
    re-point a bank account. The samples of every family still round-trip with
    these shapes present."""
    detector = Detector()
    problems: list[str] = []
    for text, value in (
            ("счёт 40817810099910004312", "40817810099910004312"),
            ("ОМС 6613186091390990", "6613186091390990"),
            ("ИНН 7707083893", "7707083893"),
            ("СНИЛС 112-233-445 95", "112-233-445 95"),
            ("IMEI 526018159083010", "526018159083010"),
            ("ICCID 6030824628194821990", "6030824628194821990"),
            ("ОГРНИП 231948757491188", "231948757491188"),
            ("загранпаспорт 75 1234567", "75 1234567"),
            ("СТС 77 12 345678", "77 12 345678"),
            ("военный билет АК № 1234567", "АК № 1234567"),
            ("ИП № 1234567/25/77001-ИП", "1234567/25/77001-ИП"),
            ("кадастровый номер 77:01:0001001:1234", "77:01:0001001:1234"),
            ("УИД 77OS0000-02-2026-000001-52", "77OS0000-02-2026-000001-52"),
            ("полис ДМС 001SB12345678", "001SB12345678"),
            ("полис ОСАГО ХХХ 0123456789", "ХХХ 0123456789"),
            ("VIN 952SVA0422CF17579", "952SVA0422CF17579"),
            ("IBAN RU9404980574640602810700000000025",
             "RU9404980574640602810700000000025"),
            ("ЕЛС 60АА000593-01", "60АА000593-01"),
            ("диплом 107724 0001234", "107724 0001234"),
            ("трудовой договор 145-ТД", "145-ТД"),
            ("PNR 2ZYVAL", "2ZYVAL")):
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{value!r} still standing in {masked!r}")
            continue
        if value not in unmask_text(masked, vault):
            problems.append(f"{value!r} did not come back "
                            f"({unmask_text(masked, vault)!r})")
    check("the utility shapes do not steal the other families' values",
          not problems, "; ".join(problems) if problems else "21 round trips")


def test_utility_key_typed_spelling_stays_reversible() -> None:
    """A FIELD KEY TYPES THE WHOLE VALUE WITH NO SHAPE CHECK, so a value can
    arrive in a spelling no utility shape admits. The mint then answers from the
    registry's SAMPLE (correctly — it must not echo the source), and a mirrored
    sample that escaped every shape would be a fake the restorer can never see.
    The guard is the family's own shape question; this measures it over spellings
    INSIDE and OUTSIDE the accepted set."""
    detector = Detector()
    problems: list[str] = []
    for label, value in (("ACCESS_PASS_NUMBER", "00 1A 2B 3C 4D"),
                         ("LOGIN", "user name"),
                         ("CDP_CUSTOMER_ID", "12345"),
                         ("UTILITY_ACCOUNT", "1 2 3 4 5 6"),
                         ("EMPLOYEE_TAB_NUMBER", "12345")):
        token = _uvault().tokenize(value, label)
        if not token_re().fullmatch(token):
            problems.append(f"{label}: {value!r} minted {token!r}, which escapes "
                            f"token_re")
        elif not v6.UTILITY_TOKEN_RE.fullmatch(token):
            problems.append(f"{label}: {value!r} minted {token!r}, which escapes "
                            f"UTILITY_TOKEN_RE")
        elif token == value:
            problems.append(f"{label}: the fake equals the source {value!r}")
    for key, label, value in (("access_card_id", "ACCESS_PASS_NUMBER",
                               "00 1A 2B 3C 4D"),
                              ("username", "LOGIN", "user name"),
                              ("customer_id", "CDP_CUSTOMER_ID", "12345")):
        payload = json.dumps({key: value}, ensure_ascii=False)
        vault = _uvault()
        spans = detector.detect(payload)
        if not any(span.entity_type == label for span in spans):
            problems.append(f"the key {key!r} did not type the value "
                            f"({_types_found(detector, payload)})")
            continue
        opened = unmask_arguments(mask_text(payload, vault, spans), vault)
        try:
            opened_value = json.loads(opened).get(key)
        except ValueError:
            problems.append(f"the key-typed payload stopped parsing: {opened!r}")
            continue
        if opened_value != value:
            problems.append(f"the key-typed {value!r} did not resolve: {opened!r}")
    check("a key-typed utility spelling stays reversible", not problems,
          "; ".join(problems) if problems else "5 spellings + 3 payloads")


def test_utility_lease_and_module_shapes_agree() -> None:
    """THE LEASED CUE TABLE AND THE MODULE'S OWN SHAPES ARE TWO READINGS OF ONE
    FACT, and a drift between them is silent: the recognizer would accept a value
    the mint then shapes differently (or the reverse), and the round trip would
    fail on exactly the values neither the sample nor the tests happened to name.
    So every entry this family puts in `CTX_TYPES` is compared with the module's
    compiled shape over a battery of notations."""
    import licensing.assets_source as source
    problems: list[str] = []
    entries = [entry for entry in source.CTX_TYPES
               if entry[0] in v6.UTILITY_LABELS]
    seen: set[str] = set()
    leased_by_type: dict[str, list[re.Pattern[str]]] = {}
    for entity_type, _cues, shape in entries:
        seen.add(entity_type)
        try:
            leased_by_type.setdefault(entity_type, []).append(
                re.compile(rf"(?i:{shape})"))
        except re.error as exc:
            problems.append(f"{entity_type}: the leased shape does not compile "
                            f"({exc!r})")
    # THE UNION IS THE COMPARISON, not one entry against one shape: a label may
    # hold SEVERAL entries on purpose (UTILITY_ACCOUNT splits the shared cues from
    # its own «ЖКХ»), and what must not drift is the recognizer's aggregate shape
    # against the shape the mint produces.
    for entity_type, patterns in leased_by_type.items():
        module = v6.UTILITY_SHAPES[entity_type]
        for candidate in _shape_battery(entity_type):
            leased_ok = any(pattern.fullmatch(candidate) for pattern in patterns)
            module_ok = bool(module.fullmatch(candidate))
            if leased_ok != module_ok:
                problems.append(
                    f"{entity_type}: {candidate!r} is "
                    f"{'accepted' if leased_ok else 'refused'} by the lease and "
                    f"{'accepted' if module_ok else 'refused'} by the module")
    missing = sorted(set(v6.UTILITY_LABELS) - seen)
    if missing:
        problems.append(f"no cue entry for {missing}")
    check("the leased shapes and the module's shapes agree", not problems,
          "; ".join(problems) if problems
          else f"{len(entries)} entries over one battery")


def _shape_battery(type_id: str) -> tuple[str, ...]:
    """The values the lease/module comparison runs on: the registry's own sample,
    every notation the record's grammar names, and the mutations that separate two
    readings (a separator moved, a length moved by one, a letter dropped)."""
    sample = v6.UTILITY_SAMPLE[type_id]
    extra: dict[str, tuple[str, ...]] = {
        "GIS_ZHKH_ELS": ("60АА000593", "60АА000593-01-2024", "60AA000593-01",
                         "60А000593-01", "6088000593-01"),
        "UTILITY_ACCOUNT": ("123456", "123456789012", "12-34АБ", "АБ-123456",
                            "123456АБ", "договор 875", "12345"),
        "CDP_CUSTOMER_ID": ("c-000184523", "c000184523",
                            "6D92078A-8246-4BA4-AE5B-76104861E7DC",
                            "6d92078a82464ba4ae5b76104861e7dc", "12345678",
                            "123456789"),
        "LOGIN": ("ivanov_d85", "a.b-c", "ab1", "12345", "user name", "ab"),
        "DIPLOMA_NUMBER": ("107724 0001234", "1077240001234", "207724 0001234",
                           "107724 000123"),
        "SCHOOL_CERT_NUMBER": ("07705000012345", "7705000012345"),
        "STUDENT_ID_NUMBER": ("21-0345", "210345", "2024", "12345678901"),
        "ACCESS_PASS_NUMBER": ("0034561", "1A2B3C4D", "1A2B3C4D5E6F70",
                               "1234567890123"),
        "EMPLOYEE_TAB_NUMBER": ("004512", "0000-00412", "2024-2025", "12345"),
        "EMPLOYMENT_CONTRACT_NUMBER": ("145-ТД", "ТД-2024/017", "ТД2024",
                                       "01.01.2024"),
        "PNR": ("2ZYVAL", "2ZYVAL1", "12345", "ABCDEF", "отеля"),
        "E_TICKET_NUMBER": ("5552412345678", "555241234567"),
    }
    return (sample,) + extra.get(type_id, ())


def test_utility_fold_gap_is_closed_on_both_paths() -> None:
    """THE RECORDED FOLD GAP IS CLOSED, AND THIS PIN FAILS IF IT REOPENS.

    `normalize()` folds digit look-alikes inside any run holding five or more real
    digits, and four of this family's shapes ACCEPT the folded spelling — a UUID's
    `B` becomes `8` and stays hex, a login's `O` becomes `0` and stays a handle, an
    RFID UID's `B` becomes `8`, a mixed account's `О` becomes `0`. The cue path
    already ran on the RAW text (`detect_telecom`), but the supersede rule in
    `ru_pii.detect_structured` was keyed on `TELECOM_LABELS` alone, so the
    NORMALIZED span survived beside the raw one and the vault held the folded
    string: a REWRITTEN substitute resolved to a value the customer never wrote.
    The rule now keys on every family the raw entry point answers for, and the KEY
    path reads the raw value (`structured.detect_structured_kv`). Two spellings
    where the fold removes the match entirely are IMMUNE and asserted so: a ЕЛС
    series and an employment contract reached only through the raw path."""
    detector = Detector()
    problems: list[str] = []
    # IMMUNE: the folded spelling cannot match, so the raw path is the only reading.
    for text, value in (("ЕЛС 60ВВ000593-01", "60ВВ000593-01"),
                        ("трудовой договор О-12345", "О-12345")):
        vault = _uvault()
        masked = mask_text(text, vault, detector.detect(text))
        if value not in unmask_text(masked, vault):
            problems.append(f"the raw path is not immune for {text!r}: "
                            f"{unmask_text(masked, vault)!r}")
    # COPY AND REWRITE: the literal spelling comes back on BOTH legs, where it
    # used to come back folded on the rewritten one. The fake is read out of what
    # was actually masked, then the separators an agent re-types are dropped.
    for text, value in (("customer id 6D92078A-8246-4CA4-AE5B-76104861E7DC",
                         "6D92078A-8246-4CA4-AE5B-76104861E7DC"),
                        ("логин lO12345", "lO12345"),
                        ("бейдж B1234567", "B1234567")):
        vault = Vault(":memory:", "n1-utility").for_conversation("conv-1")
        masked = mask_text(text, vault, detector.detect(text))
        if unmask_text(masked, vault) != text:
            problems.append(f"the copied leg lost the literal for {text!r}")
        head, tail = text[:text.index(value)], text[text.index(value) + len(value):]
        fake = masked[len(head):len(masked) - len(tail)] if tail else masked[len(head):]
        if not fake or fake == value:
            problems.append(f"nothing was masked in {text!r}")
            continue
        rewritten = "".join(ch for ch in fake if ch.isalnum())
        restored = unmask_text(head + rewritten + tail, vault)
        if _alnum(value).casefold() not in _alnum(restored).casefold():
            problems.append(f"the recorded fold gap REOPENED for {text!r}: "
                            f"fake {fake!r} -> {restored!r}")
    check("the utility fold gap is closed on the cue and key paths",
          not problems, "; ".join(problems) if problems
          else "2 immune spellings, 3 spellings on both legs")


# ===================== N1 lead integration (composition seams) ===============
#
# THE HANDOFFS THE FAMILIES LEFT TO THE LEAD, RESOLVED IN THE SEAMS ONLY: the
# leased priority table, the structured KV raw seam, the raw-cue supersede rule
# and the one argument in `detect_all`. No recognizer, mint or restore body was
# touched, so every family card still describes its own mechanism — and each entry
# below names the handoff it answers.
#
# TWO HANDOFFS ARE RECORDED AS NOT-TAKEN rather than silently dropped:
#   * CIVIL_ACT_CERT gets its own PRIORITY LINE (7, BIRTH_CERT's rank) but NOT its
#     own engine label: the split needs the identity mint dispatch (vault.py) and
#     the identity signature reading (redact.py), which are family bodies this
#     integration is forbidden to edit. Handing the label over without them would
#     mint an unformatted substitute and lose the reformatted-substitute resolve.
#   * the shared «лицевой счёт»/«л/с» cue still answers SUBSCRIBER_ACCOUNT (the
#     telecom family, earlier in the leased cue table). Both readings are v6
#     registry types, the value is masked either way, and flipping the winner is
#     a product decision rather than a defect — the utility family's own test
#     pins the status quo.

# The v5 core ranks, written out because "do not renumber the v5 core" is a
# property of this integration and a future edit must be able to SEE it.
V5_CORE_PRIORITY: dict[str, int] = {
    "SECRET": 8,
    "OMS": 7, "ACCOUNT": 7, "DRIVER_LICENSE": 7, "VEHICLE_DOC": 7,
    "INTL_PASSPORT": 7, "OGRN": 7, "BIRTH_CERT": 7,
    "SNILS": 6, "INN": 6, "CARD": 6, "VIN": 6,
    "MAC": 5, "PHONE": 5, "EMAIL": 5, "IP": 5, "PLATE": 5, "ADDR": 4,
    "NAME": 3, "DOB": 3, "DATE": 2, "PASSPORT": 2, "LOC": 2,
}

# The v6 entries this integration ADDS — one per handoff that named a concrete
# arbitration. The checksum family's eight new labels and the legal family's six
# asked for an entry too, and both handoffs say no OVERLAP was measured: their
# values win through `context.suppress` and the typed-over-bare filter, and an
# entry with no failing witness would be an untested arbitration. That decision is
# recorded in DELTA.json.
V6_ADDED_PRIORITY: dict[str, int] = {
    "DMS_POLICY": 8,        # above OMS: «полис ДМС …» is a ДМС, not an ОМС
    "MILITARY_ID": 7,       # above PLATE: the separator-free «АК1234567» form
    "CIVIL_ACT_CERT": 7,    # defensive: BIRTH_CERT's rank, ready for the split
    "GIS_ZHKH_ELS": 6, "UTILITY_ACCOUNT": 6, "CDP_CUSTOMER_ID": 6,
    "LOGIN": 6, "DIPLOMA_NUMBER": 6, "SCHOOL_CERT_NUMBER": 6,
    "STUDENT_ID_NUMBER": 6, "ACCESS_PASS_NUMBER": 6,
    "EMPLOYEE_TAB_NUMBER": 6, "EMPLOYMENT_CONTRACT_NUMBER": 6,
    "PNR": 6, "E_TICKET_NUMBER": 6,
    # THE G7 LABEL ALIGNMENT. Each one carries the rank its OLD spelling already
    # had (OMS/ACCOUNT/OGRN/VEHICLE_DOC were 7, IP was 5), and IP_ADDRESS is the
    # one that MOVES: to 6, because the squeezed reading of an address is a bare
    # digit run that libphonenumber reads as a PHONE, and at a tie `_resolve`
    # keeps the span appended first. A missing entry here is a label regression,
    # not a cosmetic one — STS_NUMBER is a ten-digit 2-2-6 run.
    "BANK_ACCOUNT": 7, "OGRNIP": 7, "OMS_ENP": 7, "EPTS_NUMBER": 7,
    "LOYALTY_CARD_NUMBER": 7, "PTS_NUMBER": 7, "STS_NUMBER": 7,
    "IP_ADDRESS": 6,
}


def test_priority_table_composition() -> None:
    """THE v5 CORE IS NOT RENUMBERED AND EVERY HANDED-OVER v6 ENTRY IS PRESENT.

    The leased table is the arbiter of every overlap, so a missing entry means a
    v6 label silently falls back to 1 — below every bare v5 shape. This check is
    the table-level half of the mutation witnesses below: deleting an entry is RED
    here even before the behaviour is measured."""
    table = ASSETS.get().priority
    problems: list[str] = []
    for label, rank in V5_CORE_PRIORITY.items():
        if table.get(label) != rank:
            problems.append(f"v5 core renumbered: {label}={table.get(label)!r}, "
                            f"expected {rank}")
    for label, rank in V6_ADDED_PRIORITY.items():
        if table.get(label) != rank:
            problems.append(f"{label}={table.get(label)!r}, expected {rank}")
    # The arbitrations the ranks exist for, stated as an ORDER rather than as a
    # number, so the intent survives a renumbering of the whole table.
    if table.get("DMS_POLICY", 0) <= table.get("OMS", 0):
        problems.append("DMS_POLICY does not outrank OMS")
    if table.get("MILITARY_ID", 0) <= table.get("PLATE", 0):
        problems.append("MILITARY_ID does not outrank PLATE")
    if table.get("LOGIN", 0) <= table.get("NAME", 0):
        problems.append("LOGIN does not outrank NAME")
    check("the priority table keeps the v5 core and carries the v6 entries",
          not problems, "; ".join(problems) if problems
          else f"{len(V5_CORE_PRIORITY)} v5 + {len(V6_ADDED_PRIORITY)} v6 entries")


def test_priority_v6_arbitration(detector: Detector) -> None:
    """THE CASES THE RANKS WERE ADDED FOR, AND THE CASES THEY MUST NOT BREAK.

    Every positive is a case where the v6 label lost the arbitration at the
    default rank of 1; every negative is a value the SAME shapes must not steal at
    the new rank. The negatives are the half a careless widening loses."""
    problems: list[str] = []
    positives = [
        ("военник АК1234567", "MILITARY_ID", "АК1234567"),
        ("военник АК 1234567", "MILITARY_ID", "АК 1234567"),
        ("полис ДМС 1234567890123456", "DMS_POLICY", "1234567890123456"),
        ("полис ДМС 000000000000000", "DMS_POLICY", "000000000000000"),
        ("логин ivan.petrov", "LOGIN", "ivan.petrov"),
    ]
    for text, label, value in positives:
        if not _found(detector, text, label, value):
            problems.append(f"{label}: {text!r} -> {_types_found(detector, text)}")
    # NO STEALING. A bare plate shape is still a plate; the ОМС cue is still ОМС;
    # an ОГРНИП is still an ОГРНИП; the shared «л/с» cue still arbitrates to the
    # telecom label (the utility family's recorded decision).
    negatives = [
        ("АК 1234567", "PLATE"),
        ("полис ОМС 6613186091390990", "OMS_ENP"),
        ("ОГРНИП 231948757491188", "OGRNIP"),
        ("л/с 12345678", "SUBSCRIBER_ACCOUNT"),
    ]
    for text, label in negatives:
        if not any(s.entity_type == label for s in detector.detect(text)):
            problems.append(f"{label}: {text!r} was stolen -> "
                            f"{_types_found(detector, text)}")
    check("the v6 priority entries win their own overlaps and steal nothing",
          not problems, "; ".join(problems) if problems
          else f"{len(positives)} positives, {len(negatives)} negatives")


def test_civil_act_cert_shares_the_certificate_rank(detector: Detector) -> None:
    """CIVIL_ACT_CERT'S PRIORITY LINE IS ADDED; ITS LABEL SPLIT IS NOT.

    The record shares the engine label BIRTH_CERT, so the certificate shape is
    typed at rank 7 and nothing loses; the entry is what makes the split safe the
    day it lands. The split itself needs the identity mint dispatch (`vault.py`)
    and the identity signature reading (`redact.py`) — family bodies outside this
    integration's scope — so what is asserted here is the RANK and the fact that a
    civil-act witness is still typed by the shared identity label. WHEN THE SPLIT
    LANDS, update this pin: it is the one that notices."""
    table = ASSETS.get().priority
    problems: list[str] = []
    if table.get("CIVIL_ACT_CERT") != table.get("BIRTH_CERT"):
        problems.append(f"CIVIL_ACT_CERT={table.get('CIVIL_ACT_CERT')!r} does not "
                        f"carry BIRTH_CERT's rank {table.get('BIRTH_CERT')!r}")
    if not _found(detector, "свидетельство о браке I-АГ № 672731",
                  "BIRTH_CERT", "I-АГ № 672731"):
        problems.append("a civil-act certificate is no longer typed by the shared "
                        "identity label")
    check("CIVIL_ACT_CERT carries its own priority line, the label split deferred",
          not problems, "; ".join(problems) if problems
          else "rank 7 beside BIRTH_CERT, shared label still types")


def test_structured_kv_raw_seam() -> None:
    """THE KEY PATH READS THE RAW VALUE — the seam, at the module boundary.

    `detect_structured_kv(norm)` is unchanged and still returns the NORMALIZED
    value, so every existing caller keeps its behaviour; passing the raw text at
    the same offsets returns the customer's own characters. This is the pin that
    fails if the seam silently disappears: without it the JSON key path folds a
    UUID's `B` to `8` again."""
    raw = "6D92078A-8246-4BA4-AE5B-76104861E7DC"
    text = f'{{"google_aid": "{raw}"}}'
    norm = normalize(text)
    problems: list[str] = []
    if len(norm) != len(text):
        problems.append("normalize() is no longer 1:1 — the seam's premise")
    folded = detect_structured_kv(norm)
    if not folded:
        problems.append("the key path stopped typing the value at all")
    elif "AE58" not in folded[0].value:
        problems.append(f"the normalized reading is not folded ({folded[0].value!r}) "
                        "— the seam cannot be shown to matter")
    seamed = detect_structured_kv(norm, text)
    if not seamed:
        problems.append("the seamed key path types nothing")
    elif seamed[0].value != raw:
        problems.append(f"the seamed key path returned {seamed[0].value!r}, "
                        f"expected {raw!r}")
    elif folded and (seamed[0].start, seamed[0].end) != \
            (folded[0].start, folded[0].end):
        problems.append("the seam moved the span — offsets must be shared")
    check("the structured KV raw seam reads the value and leaves the norm path",
          not problems, "; ".join(problems) if problems
          else "norm folded, raw exact, same offsets")


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    test_validators(detector)
    test_typed_invalid_path()
    test_recognize_cued_and_keyed(detector)
    test_recognize_grouped_notation(detector)
    test_bare_checksum_anchor(detector)
    test_business_accounts_stay_open(detector)
    test_no_fuzzy_numerals(detector)
    test_mint_inherits_validity()
    test_mint_mirrors_faults()
    test_mint_safe_ranges()
    test_roundtrip_text_args_and_stream()
    test_notation_preserved()
    test_token_shapes_v6()
    test_unresolved_substitute_is_named()
    # --- N1 identity family -------------------------------------------------
    test_identity_grammar_unasserted_is_recorded()
    test_identity_cued_and_keyed(detector)
    test_identity_typed_invalid_no_gate()
    test_identity_bare_is_not_typed(detector)
    test_identity_mint_is_format_preserving()
    test_identity_roundtrip_three_legs()
    test_identity_notation_both_legs()
    test_identity_token_shapes()
    test_identity_same_digits_are_not_one_document()
    test_identity_reformatted_substitute_resolves()
    test_identity_no_fuzzy_numerals()
    test_identity_unresolved_substitute_is_named()
    test_identity_no_overmask()
    test_identity_labels_follow_the_registry()
    # --- N1 legal family ----------------------------------------------------
    test_legal_grammar_unasserted_is_recorded()
    test_legal_cued_and_keyed(detector)
    test_legal_typed_invalid_no_gate(detector)
    test_legal_bare_is_not_typed(detector)
    test_legal_mint_is_format_preserving()
    test_legal_roundtrip_three_legs()
    test_legal_notation_both_legs()
    test_legal_token_shapes()
    test_legal_reformatted_substitute_resolves()
    test_legal_no_fuzzy_numerals()
    test_legal_unresolved_substitute_is_named()
    test_legal_no_overmask(detector)
    test_legal_labels_follow_the_registry()
    test_legal_generic_key_does_not_reshape_the_source()
    test_legal_shapes_do_not_steal_the_other_families()
    # --- N1 finance family ---------------------------------------------------
    test_finance_grammar_unasserted_is_recorded()
    test_finance_cued_and_keyed(detector)
    test_finance_typed_invalid_no_gate(detector)
    test_finance_bare_is_not_typed(detector)
    test_finance_mint_is_format_preserving()
    test_finance_roundtrip_three_legs()
    test_finance_token_shapes()
    test_finance_reformatted_substitute_resolves()
    test_finance_notation_both_legs()
    test_finance_no_fuzzy_numerals()
    test_finance_unresolved_substitute_is_named()
    test_finance_no_overmask(detector)
    test_finance_dates_are_not_swallowed(detector)
    test_finance_token_never_swallows_a_following_number()
    test_finance_labels_follow_the_registry()
    test_finance_shapes_do_not_steal_the_other_families()
    test_finance_key_typed_spelling_stays_reversible()
    test_finance_policy_key_overlap_is_recorded()
    # --- N1 telecom/device family --------------------------------------------
    test_telecom_registry_facts_are_recorded()
    test_telecom_cued_and_keyed(detector)
    test_telecom_typed_invalid_no_gate(detector)
    test_telecom_bare_is_not_typed(detector)
    test_telecom_mint_is_format_preserving()
    test_telecom_roundtrip_three_legs()
    test_telecom_token_shapes()
    test_telecom_reformatted_substitute_resolves()
    test_telecom_same_hex_is_one_device_and_a_different_one_is_not()
    test_telecom_recorded_label_is_among_the_readings()
    test_telecom_no_fuzzy_numerals()
    test_telecom_unresolved_substitute_is_named()
    test_telecom_no_overmask(detector)
    test_telecom_shapes_do_not_steal_the_other_families()
    test_telecom_key_typed_spelling_stays_reversible()
    test_telecom_uuid_in_json_key_round_trips()

    test_utility_registry_facts_are_recorded()
    test_utility_cued_and_keyed(detector)
    test_utility_typed_invalid_no_gate(detector)
    test_utility_bare_is_not_typed(detector)
    test_utility_mint_is_format_preserving()
    test_utility_roundtrip_three_legs()
    test_utility_token_shapes()
    test_utility_reformatted_substitute_resolves()
    test_utility_grammar_unasserted_is_recorded()
    test_utility_no_fuzzy_numerals()
    test_utility_notation_both_legs()
    test_utility_unresolved_substitute_is_named()
    test_utility_no_overmask(detector)
    test_utility_shared_cue_arbitration_is_recorded(detector)
    test_utility_shapes_do_not_steal_the_other_families()
    test_utility_key_typed_spelling_stays_reversible()
    test_utility_lease_and_module_shapes_agree()
    test_utility_fold_gap_is_closed_on_both_paths()
    # --- N1 lead integration (composition seams) -----------------------------
    test_priority_table_composition()
    test_priority_v6_arbitration(detector)
    test_civil_act_cert_shares_the_certificate_rank(detector)
    test_structured_kv_raw_seam()
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: " + "; ".join(_FAILURES))
        return 1
    print("v6 checksum family OK — 11 types recognize, mint and restore")
    print("v6 identity family OK — 8 types recognize, mint and restore")
    print("v6 legal family OK — 6 types recognize, mint and restore")
    print("v6 finance family OK — 10 types recognize, mint and restore")
    print("v6 telecom family OK — 8 types recognize, mint and restore")
    print("v6 utility family OK — 12 types recognize, mint and restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
