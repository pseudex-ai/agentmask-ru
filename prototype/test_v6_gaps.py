"""G7 follow-up — the two v6 detection gaps, positive AND negative in one run.

WHAT THIS SUITE IS FOR. `G7-DETECTION-SWEEP.md` found two independent defects on
the 55-type v6 corpus and this is their RED-then-GREEN witness:

  (1) TYPE-LABEL ALIGNMENT. The value was masked, the TYPE was not: the span
      carried the engine's v5-internal label (`OMS`, `OGRN`, `EPTS`,
      `LOYALTY`, `ACCOUNT`, `VEHICLE_DOC`, `IP`) while the registry and the
      benchmark's `typed` axis read the v6 id (`OMS_ENP`, `OGRNIP`,
      `EPTS_NUMBER`, `LOYALTY_CARD_NUMBER`, `BANK_ACCOUNT`, `PTS_NUMBER`,
      `STS_NUMBER`, `IP_ADDRESS`). Every one of those types scored 0% recall
      with 94–100% coverage — the worst reading of a benchmark, where the
      value is gone and the number still says missed.

  (2) SIX REAL GAPS at 0% coverage, i.e. the VALUE reached the model: IMEI
      bare, MAC solid-hex, IP_ADDRESS squeezed, FSSP_IP_NO squeezed,
      EMPLOYMENT_CONTRACT_NUMBER glued, REFERRAL_NUMBER behind the bare
      «направление» cue.

THE FOUR CONTROLS EVERY POSITIVE CARRIES, because a rule proved only on what it
must find is a rule nobody knows the rest of:

  * POSITIVE, in the corpus's own register (squeezed separators, glyph-folded
    twins) AND in the registry's printed form;
  * NEGATIVE from ordinary business Russian — the numbers that live beside
    these words and must stay open;
  * NO FUZZY NUMERALS: one digit changed in an IMEI is a different device, never
    a typo of the valid vector (`spoken.py`'s rule for every checksum);
  * TYPED OVER BARE: a bare checksum reading must lose to the cue that names the
    type — an ОГРНИП that also passes Luhn is an ОГРНИП, not an IMEI.

    python3 test_v6_gaps.py
"""

import sys

import testkit
from pseudex import ru_pii_v6 as v6
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_text
from pseudex.vault import Vault

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(label)


def _vault() -> Vault:
    return Vault(":memory:", "v6-gaps")


def _found(detector: Detector, text: str, entity_type: str, value: str) -> bool:
    return any(span.entity_type == entity_type
               and text[span.start:span.end] == value
               for span in detector.detect(text))


def _found_any(detector: Detector, text: str) -> bool:
    return bool(detector.detect(text))


def _types_found(detector: Detector, text: str) -> list[tuple[str, str]]:
    return [(span.entity_type, span.value) for span in detector.detect(text)]


def _corrupt_last(value: str) -> str:
    for index in range(len(value) - 1, -1, -1):
        char = value[index]
        if char.isdigit():
            return value[:index] + ("0" if char != "0" else "1") + value[index + 1:]
    raise AssertionError(f"nothing to corrupt in {value!r}")


# ------------------------------------------------------------------ (1) labels
#
# EVERY ROW IS A SPAN THE ENGINE ALREADY PRODUCED AND MASKED BEFORE G7; what
# moved is `entity_type` alone. The legacy alias is asserted to be exactly what
# the registry's own `engine_labels` declares, so the bridge cannot drift into
# a second, private vocabulary: a value masked under the v6 id but restored
# under another name is the class of defect this test exists for.
#
# (v6 id, legacy engine label, a cue-typed text, the value)
LABEL_ROWS: list[tuple[str, str, str, str]] = [
    ("OMS_ENP", "OMS", "полис ОМС 6613186091390990", "6613186091390990"),
    ("OMS_ENP", "OMS", '{"enp": "6613186091390990"}', "6613186091390990"),
    ("OGRNIP", "OGRN", "ОГРНИП 231948757491188", "231948757491188"),
    ("OGRNIP", "OGRN", '{"ogrnip": "231948757491188"}', "231948757491188"),
    ("EPTS_NUMBER", "EPTS", "номер ЭПТС 287702287921741", "287702287921741"),
    ("EPTS_NUMBER", "EPTS", '{"epts": "287702287921741"}', "287702287921741"),
    ("LOYALTY_CARD_NUMBER", "LOYALTY",
     "карта лояльности 852808414852538885", "852808414852538885"),
    ("LOYALTY_CARD_NUMBER", "LOYALTY",
     '{"loyalty_card": "5393363387501"}', "5393363387501"),
    ("BANK_ACCOUNT", "ACCOUNT", "расчётный счёт 40817810899910004312",
     "40817810899910004312"),
    ("BANK_ACCOUNT", "ACCOUNT", '{"account": "40817810099910004312"}',
     "40817810099910004312"),
    ("PTS_NUMBER", "VEHICLE_DOC", "ПТС 77 УК 123456", "77 УК 123456"),
    ("PTS_NUMBER", "VEHICLE_DOC", '{"pts_number": "77УК123456"}', "77УК123456"),
    ("STS_NUMBER", "VEHICLE_DOC", "СТС 77 12 345678", "77 12 345678"),
    ("STS_NUMBER", "VEHICLE_DOC", '{"sts_number": "7712 345678"}', "7712 345678"),
    ("IP_ADDRESS", "IP", "IP 95.165.12.34", "95.165.12.34"),
    ("IP_ADDRESS", "IP", '{"client_ip": "95.165.12.34"}', "95.165.12.34"),
]


def test_span_label_is_the_registry_id(detector: Detector) -> None:
    """The masked span NAMES the record the benchmark names.

    RED before G7: every row below returned the legacy label, so a benchmark
    that compares `span.entity_type` to the gold id scored 0% recall while the
    value itself was gone — 35/35 СТС, 36/36 ОГРНИП, 34/34 ОМС, 37/37 ЭПТС."""
    problems: list[str] = []
    for type_id, legacy, text, value in LABEL_ROWS:
        found = _types_found(detector, text)
        if not _found(detector, text, type_id, value):
            problems.append(f"{type_id}: {text!r} -> {found}")
        if any(label == legacy for label, _ in found) and legacy != type_id:
            problems.append(f"{type_id}: the legacy label {legacy!r} is still emitted")
    check("every masked span carries the v6 registry id",
          not problems, "; ".join(problems) if problems else f"{len(LABEL_ROWS)} spans")


def test_engine_label_bridge_is_total_and_exact() -> None:
    """`engine_label` is what keeps the vault on one vocabulary.

    The bridge has to be TOTAL (an unmapped label comes back unchanged, or every
    one of the other 47 v6 types would silently lose its mint branch) and it has
    to be EXACT (the legacy spelling is the vault's row key, so a second name
    would fork one document into two identities)."""
    problems: list[str] = []
    for type_id, legacy, _, _ in LABEL_ROWS:
        if v6.engine_label(type_id) != legacy:
            problems.append(f"{type_id} -> {v6.engine_label(type_id)!r}, "
                            f"expected {legacy!r}")
    for unchanged in ("IBAN", "LOAN_UID", "NAME", "PHONE",
                      "MAC", "UTILITY_ACCOUNT"):
        if v6.engine_label(unchanged) != unchanged:
            problems.append(f"{unchanged} was remapped to "
                            f"{v6.engine_label(unchanged)!r}")
    check("the label bridge is total and the legacy spelling is exact",
          not problems, "; ".join(problems) if problems
          else f"{len(LABEL_ROWS)} bridged, 8 unchanged")


# ------------------------------------------------------------- (2) real gaps
#
# THE CORPUS REGISTER IS SQUEEZED: `_squeeze` removes " -/:№" and the
# glyph-fold maps the Latin twins of Cyrillic letters, so «00:1A:2B:3C:4D:5E»
# reaches the message as «001A2B3C4D5E» and «1234567/25/77001-ИП» as
# «12345672577001ИП». Each row has BOTH spellings, because the registry's
# grammar is the printed one and the customer's traffic is the other.

GAP_POSITIVES: list[tuple[str, str, str]] = [
    # IMEI — the bare fifteen-digit Luhn (the corpus writes «вот номер …»).
    ("IMEI", "вот номер 404552178070951", "404552178070951"),
    ("IMEI", "IMEI 526018159083010", "526018159083010"),
    ("IMEI", "имей 260531793113837", "260531793113837"),
    # MAC — solid 12-hex (the corpus) and the registry's three grouped forms.
    ("MAC", "mac FCF3C2CFA5AC", "FCF3C2CFA5AC"),
    ("MAC", "MAC 00:1A:2B:3C:4D:5E", "00:1A:2B:3C:4D:5E"),
    ("MAC", "мак-адрес 001A.2B3C.4D5E", "001A.2B3C.4D5E"),
    ("MAC", "физический адрес 00-1A-2B-3C-4D-5E", "00-1A-2B-3C-4D-5E"),
    # IP_ADDRESS — the squeezed quad (the corpus) and the dotted one.
    ("IP_ADDRESS", "ip 201730173", "201730173"),
    ("IP_ADDRESS", "ip 1612154255", "1612154255"),
    ("IP_ADDRESS", "айпи 1369714947", "1369714947"),
    ("IP_ADDRESS", "IP 95.165.12.34", "95.165.12.34"),
    # FSSP_IP_NO — squeezed (the corpus) and dashed; the «СД» twin is folded.
    ("FSSP_IP_NO", "ип № 8428999731188ИП", "8428999731188ИП"),
    ("FSSP_IP_NO", "ип № 093219041CД", "093219041CД"),
    ("FSSP_IP_NO", "исполнительное производство 1234567/25/77001-ИП",
     "1234567/25/77001-ИП"),
    # EMPLOYMENT_CONTRACT_NUMBER — glued (the corpus writes the glyph-folded
    # «TД…») and the registry's two separated samples.
    ("EMPLOYMENT_CONTRACT_NUMBER", "трудовой договор TД202569917", "TД202569917"),
    ("EMPLOYMENT_CONTRACT_NUMBER", "трудовой договор ТД-2024/00123", "ТД-2024/00123"),
    ("EMPLOYMENT_CONTRACT_NUMBER", "номер трудового договора 145-ТД", "145-ТД"),
    # REFERRAL_NUMBER — the bare «направление» cue the registry names.
    ("REFERRAL_NUMBER", "направление 0880964241962", "0880964241962"),
    ("REFERRAL_NUMBER", "направление 057-2024-001234", "057-2024-001234"),
]


def test_gap_types_are_detected(detector: Detector) -> None:
    """RED before G7: all twenty rows returned `[]` — the value reached the
    model. MAC/IP/FSSP were named in the sweep's cause 3, IMEI and
    EMPLOYMENT_CONTRACT_NUMBER at 0% coverage, REFERRAL at 0% coverage behind
    the cue the corpus actually writes."""
    problems: list[str] = []
    for type_id, text, value in GAP_POSITIVES:
        if not _found(detector, text, type_id, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    check("the six gap types are detected under their own id",
          not problems, "; ".join(problems) if problems
          else f"{len(GAP_POSITIVES)} positives")


def test_gap_types_round_trip(detector: Detector) -> None:
    """DETECTED IS NOT PROTECTED. A span whose substitute cannot be resolved
    hands the customer's tool a FAKE value — worse than a miss — so every gap
    type is driven through mask → unmask and the real value must come back."""
    problems: list[str] = []
    vault = _vault()
    for type_id, text, value in GAP_POSITIVES:
        spans = detector.detect(text)
        masked = mask_text(text, vault, spans)
        if value in masked:
            problems.append(f"{type_id}: the real value is still in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{type_id}: {masked!r} -> {restored!r} "
                            f"(expected {value!r})")
    check("every gap type is masked and restored", not problems,
          "; ".join(problems) if problems else f"{len(GAP_POSITIVES)} round trips")


# THE FOUR TYPES THE SWEEP FOUND AT 0% COVERAGE AND THE BRIEF DID NOT NAME, added
# after the classification in DELTA.json showed they are 137 of the 284 remaining
# message-level leaks — 48% of everything still reaching the model, and the same
# defect class as the six (a shape that reads only the registry's printed
# separators while the corpus writes the squeezed register). The brief named six
# because G7's prose named six; the measurement named ten.
EXTRA_POSITIVES: list[tuple[str, str, str]] = [
    # CADASTRAL_NUMBER — «43:72:743493:8225» squeezed to 11–16 digits.
    ("CADASTRAL_NUMBER", "кадастровый номер 43727434938225", "43727434938225"),
    ("CADASTRAL_NUMBER", "кадастровый номер 19672103858", "19672103858"),
    # the separated form, a DIFFERENT number on purpose: see the two-notation
    # residual pinned by `test_known_two_notation_residual` below.
    ("CADASTRAL_NUMBER", "кадастровый номер 77:01:0001001:1234", "77:01:0001001:1234"),
    # COURT_CASE_NO_SOU — «2-13/2015» squeezed to a 6–12 digit run.
    ("COURT_CASE_NO_SOU", "дело № 77298282030", "77298282030"),
    ("COURT_CASE_NO_SOU", "дело № 6076990", "6076990"),
    ("COURT_CASE_NO_SOU", "дело № 2-13/2015", "2-13/2015"),
    # ARBITRAZH_CASE_NO — «А11-14094/2024» squeezed to the type letter + digits.
    ("ARBITRAZH_CASE_NO", "дело № A1114094", "A1114094"),
    ("ARBITRAZH_CASE_NO", "дело № A862183461631", "A862183461631"),
    ("ARBITRAZH_CASE_NO", "дело № А31-2840/2013", "А31-2840/2013"),
    # APP_DEVICE_ID — the bare English «device id», both registry forms.
    ("APP_DEVICE_ID", "device id 063278036263771365", "063278036263771365"),
    ("APP_DEVICE_ID", "device id E944AD90169EF7D287E3CDCF8D0EB95E",
     "E944AD90169EF7D287E3CDCF8D0EB95E"),
    ("APP_DEVICE_ID", "appmetrica_device_id 123456789012345678",
     "123456789012345678"),
]


def test_sweep_found_four_more_zero_coverage_types(detector: Detector) -> None:
    """The same RED-then-GREEN as the named six, on the four the classification
    put at the top of the residual: each scored 0% recall AND 0% coverage before,
    i.e. the value reached the model."""
    problems: list[str] = []
    for type_id, text, value in EXTRA_POSITIVES:
        if not _found(detector, text, type_id, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    check("the four 0%-coverage types the classification found are detected",
          not problems, "; ".join(problems) if problems
          else f"{len(EXTRA_POSITIVES)} positives")


def test_extra_types_round_trip(detector: Detector) -> None:
    problems: list[str] = []
    vault = _vault()
    for type_id, text, value in EXTRA_POSITIVES:
        masked = mask_text(text, vault, detector.detect(text))
        if value in masked:
            problems.append(f"{type_id}: the real value is still in {masked!r}")
            continue
        if value not in unmask_text(masked, vault):
            problems.append(f"{type_id}: {masked!r} does not restore to {value!r}")
    check("the four extra types are masked and restored", not problems,
          "; ".join(problems) if problems else f"{len(EXTRA_POSITIVES)} round trips")


# THE NEGATIVES COME FROM ORDINARY BUSINESS RUSSIAN, NOT FROM INVENTED EDGES.
# Each one is a sentence where the shape or the cue is PRESENT and the value is
# still not a person's identifier. The thin half of a widening is here: MAC's
# bare hex is a PREFIX of a 32-hex UUID, IP's squeezed quad is four digits of
# any number, «направление» is a direction, «кадастровый номер» introduces prose.
GAP_NEGATIVES: list[str] = [
    # «ip» followed by digits that are NOT four octets
    "ip 999999999",
    "ip 0000000000",
    # «направление» as a direction, not a referral number
    "направление деятельности обсудим завтра",
    "направление в отдел продаж",
    # a contract word without a contract number
    "трудовой договор подпишем позже",
    "трудовой договор расторгнут по соглашению сторон",
    # a settlement account of a legal entity (the v6 negative family)
    "корр. счёт 30101810400000000225",
    "расчётный счёт 40702810600000001234",
    "казначейский счёт 03100643000000000123",
    # the four added types: cue present, no value
    "кадастровый номер участка обсудим",
    "дело № 12345",
    "дело № обсудим позже",
    "номер дела в суде",
    "device id 123456789",
    "device id указан в карточке",
    # ordinary business numbers beside the gap cues must stay open
    "заказ 40455 от 12.03.2026",
    "артикул 201730173",
]


def test_known_two_notation_residual(detector: Detector) -> None:
    """A KNOWN LIMITATION, PINNED SO IT FLIPS RED WHEN IT IS FIXED.

    ONE VALUE IN TWO NOTATIONS: if a number is first seen squeezed and later with
    its separators, the vault keeps ONE row (correct) but the token was minted in
    the FIRST notation, and the second mention renders it in the source's form —
    which the OUT leg cannot map back, because the row's token string is the
    other notation. The real value stays in the vault (no leak, no fake to the
    tool in the sense of a wrong value — the FAKE is echoed back), but the tool
    would receive the substitute instead of the real number.

    IT IS NOT INTRODUCED HERE. The same pair fails identically for a pre-existing
    type: an IBAN written glued and then in groups of four
    (`IBAN RU94…25` -> `RU76…57` laid as `RU76 0000 …`) does not resolve either,
    and that path existed before this change. Enabling the squeezed cadastral
    register is only what made the pair reachable for THIS type. The assertion
    below states today's behaviour, so the day the OUT leg learns the notation
    the test fails and the residual is closed rather than forgotten."""
    vault = _vault()
    first = "кадастровый номер 43727434938225"
    second = "кадастровый номер 43:72:7434938:225"
    mask_text(first, vault, detector.detect(first))
    masked = mask_text(second, vault, detector.detect(second))
    token = masked.split()[-1]
    restored = unmask_text(masked, vault)
    problems: list[str] = []
    if token == "43:72:7434938:225":
        problems.append("the second notation was not masked at all")
    if "43:72:7434938:225" in restored:
        # The limitation has been FIXED: flip the pin.
        problems.append("the two-notation residual is CLOSED — update this pin "
                        "(and the IBAN twin) to assert resolution")
    check("the known two-notation residual is pinned, not hidden", not problems,
          "; ".join(problems) if problems
          else f"masked {token!r}, OUT leg echoes the substitute (pre-existing)")


def test_card_cue_literal_is_shared_not_copied() -> None:
    """TWO READINGS OF ONE RULE MUST NOT DRIFT.

    The bare IMEI stands down when a card cue named the run, and that guard
    spells the card cue out again in `ru_pii_v6` (`ru_pii` cannot be imported
    from there without a cycle). A copied literal is a second value that has to
    stay equal to the first, so this pins the equality rather than trusting it —
    the failure mode is a card cue the guard stops recognising, i.e. the
    displacement defect coming back silently."""
    from pseudex import ru_pii
    problems: list[str] = []
    if v6._IMEI_CARD_CUE != ru_pii._CARD_CUE:
        problems.append(f"the card cue drifted: {v6._IMEI_CARD_CUE!r} != "
                        f"{ru_pii._CARD_CUE!r}")
    check("the card cue the IMEI guard reads is ru_pii's own", not problems,
          "; ".join(problems) if problems else "1 literal, one home")


def test_mac_is_not_a_uuid_prefix(detector: Detector) -> None:
    """THE BOUNDARY, NOT THE OMISSION, KEEPS A 12-HEX MAC OFF A 32-HEX UUID.

    The solid 12-hex MAC was refused for years because it is a prefix of the
    UUID that MOBILE_AD_ID's squeezed form claims. The value has to be read, so
    the guarantee moved into the shape's boundaries: inside a 32-hex token the
    MAC's `(?<!hex)`/`(?!hex)` see a hex neighbour and refuse. This is that
    property, asserted where it matters — the UUID-bearing sentence."""
    problems: list[str] = []
    text = "device id E944AD90169EF7D287E3CDCF8D0EB95E"
    if any(span.entity_type == "MAC" for span in detector.detect(text)):
        problems.append("a 12-hex MAC was read out of a 32-hex UUID")
    if not _found(detector, text, "APP_DEVICE_ID", "E944AD90169EF7D287E3CDCF8D0EB95E"):
        problems.append("the UUID itself was not typed APP_DEVICE_ID")
    check("a solid MAC does not match inside a 32-hex UUID", not problems,
          "; ".join(problems) if problems else "1 UUID, 0 MAC readings")


def test_gap_shapes_do_not_over_mask(detector: Detector) -> None:
    """THE HALF A CARELESS WIDENING LOSES. Each negative carries the cue or the
    shape of a gap type and is not one: the glued MAC is a UUID's own prefix,
    the squeezed quad is any digit run, «направление» is a word."""
    problems = [text for text in GAP_NEGATIVES if _found_any(detector, text)]
    check("the widened shapes do not steal ordinary business text",
          not problems, "; ".join(problems) if problems
          else f"{len(GAP_NEGATIVES)} negatives")


def test_no_fuzzy_numerals_on_the_bare_imei(detector: Detector) -> None:
    """A ONE-DIGIT CHANGE IS A DIFFERENT DEVICE, NOT A TYPO.

    The bare IMEI is the one value in this change whose anchor is its own check
    digit, so it is the one that could be forgiven for reading a near-miss as a
    typo. It must not: a corrupt fifteen-digit run is not typed at all, and a
    corrupt value behind the CUE is masked AS ITSELF, never resolved to the
    valid vector it is one edit away from."""
    problems: list[str] = []
    valid = "404552178070951"
    if not v6.validate_imei(valid):
        problems.append("the control vector does not validate")
    broken = _corrupt_last(valid)
    if v6.validate_imei(broken):
        problems.append("the corrupted vector still validates")
    # THE ASSERTION IS ABOUT THE IMEI READING, NOT ABOUT «NO SPAN AT ALL». The
    # mutant `404552178070950` happens to be a valid ОГРНИП (mod 13), and the v5
    # bare ОГРНИП recognizer masking it is `COV-INTEGRATION-KEEP-V5`, not fuzzy
    # matching. What must not happen is the IMEI reading.
    typed = _types_found(detector, f"код {broken}")
    if any(label == "IMEI" for label, _ in typed):
        problems.append(f"a corrupt bare run was typed IMEI: {typed}")
    if _found(detector, f"IMEI {broken}", "IMEI", valid):
        problems.append("a corrupt IMEI was resolved to the valid one")
    check("a mutating IMEI check digit is not read as a typo", not problems,
          "; ".join(problems) if problems
          else f"mutant typed as {sorted({label for label, _ in typed}) or 'nothing'}")


def test_typed_over_bare() -> None:
    """THE CUE BEATS THE BARE CHECKSUM, AND ONLY THE CUE.

    A fifteen-digit run can be several records at once: the corpus generator
    refuses an IMEI that is also a valid ОГРНИП, and this asserts the
    arbitration the other way round — a value that IS an ОГРНИП behind its own
    cue must be typed ОГРНИП even though it may pass Luhn, and an ЭПТС behind
    «эптс» is an ЭПТС even though the bare IMEI reading is valid on it.

    BOTH HALVES IN ONE RUN: the same fifteen digits WITHOUT the cue are the bare
    IMEI (that is what makes this "typed over bare" rather than "typed only")."""
    detector = Detector()
    problems: list[str] = []
    cases = [
        ("ОГРНИП", "231948757491188", "OGRNIP"),
        ("номер ЭПТС", "287702287921741", "EPTS_NUMBER"),
        ("IMEI", "526018159083010", "IMEI"),
    ]
    for cue, value, type_id in cases:
        found = _types_found(detector, f"{cue} {value}")
        if not any(label == type_id for label, _ in found):
            problems.append(f"{type_id}: cued -> {found}")
    # The bare reading exists exactly where the registry puts it: a valid IMEI
    # stands alone, and a value whose Luhn is broken does not.
    if not _found(detector, "вот номер 404552178070951", "IMEI", "404552178070951"):
        problems.append("the bare IMEI positive is not found without a cue")
    # An ОГРНИП behind its cue is not also reported as an IMEI.
    if any(label == "IMEI" for label, _ in _types_found(detector,
                                                        "ОГРНИП 231948757491188")):
        problems.append("the cued ОГРНИП was also typed IMEI")
    check("the cue beats the bare checksum on the same fifteen digits",
          not problems, "; ".join(problems) if problems else "3 cued, 1 bare, 1 exclusion")


def test_glued_forms_do_not_swallow_the_neighbour() -> None:
    """THE SHAPE ENDS WHERE THE VALUE ENDS. The glued alternatives
    (`[А-ЯЁA-Zа-яё]{1,3}\\d{4,12}` for a contract, `\\d{8,14}(?:ИП|СД)` for an
    ФССП number) are read off the corpus's squeezed register, and their risk is a
    span that runs on into the next token. Both are token-bounded; this pins it
    on a value standing immediately before another number."""
    detector = Detector()
    problems: list[str] = []
    for text, type_id, value in (
            ("трудовой договор TД202569917 табельный номер 8074257247",
             "EMPLOYMENT_CONTRACT_NUMBER", "TД202569917"),
            ("ип № 892257134ИП электронный билет 55389256232",
             "FSSP_IP_NO", "892257134ИП"),
            ("mac 709A3BD5DD61 карта лояльности 234722300737",
             "MAC", "709A3BD5DD61"),
    ):
        spans = detector.detect(text)
        hit = [span for span in spans if span.entity_type == type_id]
        if not hit:
            problems.append(f"{type_id}: not found -> {_types_found(detector, text)}")
            continue
        if text[hit[0].start:hit[0].end] != value:
            problems.append(f"{type_id}: span is "
                            f"{text[hit[0].start:hit[0].end]!r}, expected {value!r}")
    check("a glued shape stops at the value's own boundary", not problems,
          "; ".join(problems) if problems else "3 neighbours")


# ------------------------------------------------ the raw cue pass (03.10.2026)
#
# WHAT THIS SECTION IS FOR. After the six named gaps were closed, the sweep's own
# per-type table named the NEXT five and every one of them was the same defect or
# its neighbour:
#
#   * the VALUE was read off the NORMALIZED text, so `normalize()`'s digit fold
#     corrupted a claim number's «В», a certificate's Latin «X» and a УИД's hex
#     «B» — four families, 31 message-level misses, all masked with the WRONG
#     characters in the vault;
#   * the CUE had to be spelled exactly as the lease spells it, so the sloppy
#     register's «прпоуск», «исполгительный литс», «лиицевой счёт» reached nothing
#     (another 30);
#   * two mentions of one type were joined by «и ещё», and only the cued one was
#     read (22 more);
#   * the ГИС ЖКХ series is MIXED-SCRIPT and the shape demanded one script, so 29
#     of 34 spans were missed altogether.
#
# Every positive below is one of those; every negative is the over-mask the same
# mechanism would buy if it were a little less bounded, and the first run of each
# mechanism DID buy one until the bound was added (the negative names it).


def test_raw_cue_pass_keeps_the_customer_characters(detector: Detector) -> None:
    """THE SPAN'S VALUE IS THE TEXT'S OWN SUBSTRING, NOT THE FOLDED ONE.

    `normalize()` is applied before every recognizer and folds look-alikes inside
    digit-dense runs: «В-924-378871/82» → «8-924-…», «IXУВ928243» → «IХУВ928243»
    (the Latin `X` inside a two-Cyrillic run), «…E471DBB5» → «…E471D88 5» for a
    УИД's hex `B`. The value is still masked when read from the normalized text,
    which is why the sweep's HONEST axis is not enough here — what the vault keys
    and what the round trip returns is the span's VALUE. Asserted on the value AND
    through mask/unmask, because the second is the one the customer's tool sees."""
    problems: list[str] = []
    cases = (
        ("INSURANCE_CLAIM_NUMBER", "номер убытка В-924-378871/82", "В-924-378871/82"),
        ("CIVIL_ACT_CERT", "свидетельство о браке IXУВ928243", "IXУВ928243"),
        ("BIRTH_CERT", "свидетельство о рождении XЕЕ949793", "XЕЕ949793"),
        ("LOAN_UID", "мой уид 0B74B21F47A239D00175421C2E471DBB5",
         "0B74B21F47A239D00175421C2E471DBB5"),
    )
    for type_id, text, value in cases:
        hit = [span for span in detector.detect(text) if span.value == value]
        if not hit:
            problems.append(f"{type_id}: the span value is not the text -> "
                            f"{_types_found(detector, text)}")
            continue
        vault = _vault()
        restored = unmask_text(mask_text(text, vault, hit), vault)
        if value not in restored:
            problems.append(f"{type_id}: mask/unmask lost the characters -> "
                            f"{restored!r}")
    check("the raw cue pass keeps the customer's own characters", not problems,
          "; ".join(problems) if problems else f"{len(cases)} fold classes")


def test_damaged_cue_is_read_and_intact_cue_wins(detector: Detector) -> None:
    """ONE TYPO (OR ONE STRETCHED LETTER) IN THE CUE IS STILL THE CUE — AND AN
    INTACT CUE IS STILL STRONGER EVIDENCE THAN A DAMAGED ONE.

    The positives are the corpus's own sloppy register, one edit each. The negatives
    are the over-mask the rule bought on its first run: «ОМС» is one substitution
    from «ДМС» and «ПАС» from «ПТС», so a damaged reading must never displace an
    INTACT one over the same characters, and a stem under five letters tolerates a
    transposition only. THAT SECOND CLAUSE HAS A MEASURED PRICE and it is asserted
    rather than hidden: «gid» for «gaid» is a DELETION on a four-letter stem, and it
    stays unread (three corpus mentions pay for not reading every abbreviation as
    every other)."""
    problems: list[str] = []
    positives = (
        ("ACCESS_PASS_NUMBER", "прпоуск 3486241", "3486241"),
        ("ACCESS_PASS_NUMBER", "пропукс 550421262", "550421262"),
        ("EXEC_DOC_NO", "исполгительный литс KM229294152", "KM229294152"),
        ("RESIDENCE_PERMIT", "вид на жиельство 823974061", "823974061"),
        ("SUBSCRIBER_ACCOUNT", "лиицевой счёт 61338412", "61338412"),
        ("SCHOOL_CERT_NUMBER", "атьестат 74059414622497", "74059414622497"),
        ("MOBILE_AD_ID", "gaid CE10C8C8F3E8D91A8093B46F75299FAB",
         "CE10C8C8F3E8D91A8093B46F75299FAB"),
    )
    for type_id, text, value in positives:
        if not _found(detector, text, type_id, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    # THE INTACT CUE WINS ITS OWN CHARACTERS.
    if not _found(detector, "полис ОМС 6613186091390990", "OMS_ENP",
                  "6613186091390990"):
        problems.append("a damaged DMS reading displaced the intact ОМС cue")
    if not _found(detector, "паспорт 45 09 123456", "PASSPORT", "45 09 123456"):
        problems.append("a damaged СТС reading displaced the intact ПАСПОРТ cue")
    check("a damaged cue is read, an intact cue is stronger", not problems,
          "; ".join(problems) if problems
          else f"{len(positives)} damaged cues + 2 intact wins")


def test_cue_literal_and_coordinated_list(detector: Detector) -> None:
    """TWO BOUNDS ON THE SAME MECHANISM, EACH BOUGHT BY A FALSE POSITIVE.

    (1) A CUE'S «№» IS PART OF THE CUE. The leased branch «договор … №» extracts to
        the word «договор» alone once the escapes go, and `test_hard_cases`'s own
        negative «договор 9455 480555 оплачен» came back as a credit contract. The
        literal is required beside the words.

    (2) A CUE TYPES A COORDINATED LIST, AND THE MARKER IS THE «ANOTHER ONE» SET.
        «<value> и ещё <value>» is two mentions of one type (the corpus writes 22 of
        them); a bare «,» is not a marker, because «л/с 12345678, 50000 руб.» is an
        account followed by an amount."""
    problems: list[str] = []
    if not _found(detector, "договор № 9455 480555 оплачен", "LOAN_CONTRACT_NUMBER",
                  "9455 480555"):
        problems.append("the «№» branch of the contract cue does not fire")
    if _found_any(detector, "договор 9455 480555 оплачен"):
        problems.append("a bare «договор» still types an ordinary reference")
    for type_id, text, value in (
            ("ACCESS_PASS_NUMBER", "пропуск 123456 и ещё 654321", "654321"),
            ("INSURANCE_CLAIM_NUMBER", "номер убытка В-924-378871/82 и ещё В-269-613933/17",
             "В-269-613933/17"),
            ("ICCID", "iccid 8910414756468071005 а также 8930360898821307304",
             "8930360898821307304")):
        if not _found(detector, text, type_id, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    stray = detector.detect("рабочий счёт 40817810698202940437, 50000 рублей списано")
    if any(span.start <= 42 < span.end or span.start <= 46 < span.end
           for span in stray):
        problems.append(f"a comma continued the list into an amount -> "
                        f"{[(s.entity_type, s.value) for s in stray]}")
    check("a cue literal is required and a coordinated list is read", not problems,
          "; ".join(problems) if problems else "2 positives + 1 literal + 1 comma")


def test_leased_cue_sources_all_parse() -> None:
    """THE RAW PASS RE-READS THE LEASE'S OWN (cue, shape) PAIR, SO THE PAIR MUST
    PARSE FOR EVERY ENTRY.

    `_ctx_cue_and_shape` recovers the two halves from the compiled pattern's source
    — `pseudex/assets.py`'s builder is the only place they are joined — and a
    builder change that stopped parsing would silently cost the widened gap and the
    damaged-cue reading for that entry. This pin makes that loud."""
    from pseudex.assets import ASSETS
    problems: list[str] = []
    entries = ASSETS.get().ru_pii.ctx_patterns
    for entity_type, pattern in entries:
        cues, shape = v6._ctx_cue_and_shape(pattern)
        if not cues or not shape:
            problems.append(f"{entity_type}: the (cue, shape) pair does not parse")
            continue
        if v6._raw_ctx_for(pattern) is None:
            problems.append(f"{entity_type}: the cue source does not recompile")
    if not any(entity_type in v6.RAW_CUED_LABELS for entity_type, _ in entries):
        problems.append("the raw pass answers for none of the leased entries")
    check("every leased cue source re-parses for the raw pass", not problems,
          "; ".join(problems) if problems else f"{len(entries)} entries")


def test_gis_series_is_script_tolerant_and_squeezed(detector: Detector) -> None:
    """ГИС ЖКХ ЕЛС: MIXED SCRIPT AND THE SQUEEZED 13/18 FORM (29 of 34 missed).

    The record's own `value_notation` is `glyph_fold` and its `needle_kinds` name
    `glyph`: the two series letters are ONE series typed on two layouts, so «20ЯM»
    (Cyrillic Я, Latin M) is the same document as «20ЯМ». And the corpus renders the
    registry's 13/18-character forms with the separators squeezed out, which is the
    same squeeze the other v6 cards already read."""
    problems: list[str] = []
    for text, value in (("елс 20ЯM566083", "20ЯM566083"),
                        ("елс 02TШ826055116346", "02TШ826055116346"),
                        ("ЕЛС 60АА000593-01", "60АА000593-01"),
                        ("ЕЛС 60AA000593-01-2024", "60AA000593-01-2024")):
        if not _found(detector, text, "GIS_ZHKH_ELS", value):
            problems.append(f"{text!r} -> {_types_found(detector, text)}")
    # A FOLDED SERIES IS NOT THE CUSTOMER'S SERIES: the raw path is the only
    # reading, and the normalized spelling must not be typed twice.
    spans = detector.detect("ЕЛС 60ВВ000593-01")
    if not any(span.value == "60ВВ000593-01" for span in spans):
        problems.append(f"the raw reading of a folded series is missing -> "
                        f"{[(s.entity_type, s.value) for s in spans]}")
    check("the ЕЛС series is script-tolerant and reads the squeezed form",
          not problems, "; ".join(problems) if problems else "4 forms + 1 folded")


def test_shapes_widened_on_measured_bounds(detector: Detector) -> None:
    """THREE SHAPES WIDENED TO THE RECORD'S OWN FACTS, AND EACH WIDENING NAMED
    WITH THE NEGATIVE THAT BOUNDS IT.

      * ACCESS_PASS_NUMBER: the registry states no floor («цифры печатного
        пропуска», sample «0034561» = 7) and the corpus draws 4–10. The floor is
        FOUR (03.10.2026 — it was five): the three remaining misses of this type
        were four-digit printed passes. The YEAR is refused by the WORD, not by a
        length floor — «пропуск на 2024 год» carries «год» and stays open, while
        «пропуск 1985» (a pass whose digits merely look like a year) is read.
      * CREDIT_SUBJECT_CODE: «4–15 знаков: цифры + буквы ОДНОГО алфавита» admits a
        code drawn as CAPITALS only, which is 5 of the 7 misses. Lowercase prose is
        not a code — and the whole shape is compiled `(?i:…)`, so the capitals are
        scoped `(?-i:…)` or «будет», «двух» and «телефон» become codes.
      * UTILITY_ACCOUNT vs SUBSCRIBER_ACCOUNT: the two records share the cue AND the
        digit run, so the ONLY decidable split is the registry's own bounds — six
        and seven digits are the utility record's alone (SUBSCRIBER starts at
        eight). 14 of the corpus's 35 utility mentions are that."""
    problems: list[str] = []
    if not _found(detector, "пропуск 73226", "ACCESS_PASS_NUMBER", "73226"):
        problems.append("the five-digit pass is not read")
    if not _found(detector, "пропуск 8178", "ACCESS_PASS_NUMBER", "8178"):
        problems.append("the four-digit printed pass is not read")
    if _found_any(detector, "пропуск на 2024 год"):
        problems.append("a four-digit year behind «пропуск» is typed as a pass")
    if _found_any(detector, "пропуск на 2024 г."):
        problems.append("a four-digit year written «2024 г.» is a pass again")
    if not _found(detector, "пропуск 1985", "ACCESS_PASS_NUMBER", "1985"):
        problems.append("a year-LOOKING four-digit pass is denied with the year")
    if not _found(detector, "код субъекта АСПЗГ", "CREDIT_SUBJECT_CODE", "АСПЗГ"):
        problems.append("an all-capital subject code is not read")
    if _found_any(detector, "код субъекта указан в договоре"):
        problems.append("lowercase prose is typed as a subject code")
    if not _found(detector, "лицевой счёт 1234567", "UTILITY_ACCOUNT", "1234567"):
        problems.append("a seven-digit account is not the utility record")
    if not _found(detector, "лицевой счёт 12345678", "SUBSCRIBER_ACCOUNT",
                  "12345678"):
        problems.append("an eight-digit account stopped being the operator's")
    if _found_any(detector, "лицевой счёт закрыт"):
        problems.append("a cue with no value masks a word")
    check("the three measured widens hold and their negatives hold", not problems,
          "; ".join(problems) if problems else "3 positives + 4 negatives")


# =================== the v6 yellow zone (P2, 03.10.2026) ====================
#
# SIX REGISTRY TYPES READ BELOW 100% honest on `bench/agentpii5/detect_sweep.py`,
# and this is the RED-then-GREEN witness for the part of that deficit a recognizer
# can close. THE DEFICIT HAS TWO KINDS AND THE SWEEP'S PER-TYPE TABLE CANNOT TELL
# THEM APART, which is why every row of GATE.json reports `scored` beside `gt`:
#
#   * A REAL LEAK — the value is in the frame's text and comes back unmasked.
#     PNR (all-letter locators) and ACCESS_PASS_NUMBER (four-digit passes) were the
#     only two, 4 + 6 gold occurrences. FIXED here; the number rises.
#   * A FRAME GAP — the gold item is a SEED record (`where.kind == "seed"`) whose
#     clean value is absent from every scanned text because the corpus stored a
#     mixed-script/squeezed rendering of it on the user turn. `scored` sits below
#     `gt` and `honest == scored`: the engine masks EVERY occurrence the frame
#     carries. PTS_NUMBER (47/71), EXEC_DOC_NO (43/71), GIS_ZHKH_ELS (37/69) and
#     APP_DEVICE_ID (52/68) are that, and no recognizer can move them — the
#     comparison that would have to change is the sweep's own `norm()`, which this
#     change may not touch. Their real-world misses are still closed below (a PTS
#     series behind «серия», «исполнительный №», a glyph-folded APP UUID), because
#     a leak outside the corpus is a leak.
#
# THE NEGATIVES ARE THE POINT OF EVERY ROW, and each is the one the shape could
# plausibly have bought: a year, a Russian word, an ordinary business number.
YELLOW_POSITIVES: list[tuple[str, str, str]] = [
    # PNR — an all-letter GDS locator behind the LATIN cue (4 gold occurrences).
    ("PNR", "pnr VGBBS", "VGBBS"),
    ("PNR", "pnr ZXLGUT", "ZXLGUT"),
    # the alphanumeric reading is untouched by the new alternative
    ("PNR", "PNR LYG9T", "LYG9T"),
    ("PNR", "код бронирования 2ZYVAL", "2ZYVAL"),
    # PTS_NUMBER — the series behind «серия» with no «ПТС» anywhere.
    ("PTS_NUMBER", "серия 13 ОГ 695459", "13 ОГ 695459"),
    ("PTS_NUMBER", "серия 13ОГ695459", "13ОГ695459"),
    ("PTS_NUMBER", "ПТС 77 УК 123456", "77 УК 123456"),
    # EXEC_DOC_NO — «исполнительный № …» with no «лист»/«документ».
    ("EXEC_DOC_NO", "исполнительный № ХО 332743690", "ХО 332743690"),
    ("EXEC_DOC_NO", "исполнительный лист ХО 332743690", "ХО 332743690"),
    # APP_DEVICE_ID — the glyph-folded UUID (a Cyrillic А where the Latin A stood).
    ("APP_DEVICE_ID", "device id E944АD90-169E-F7D2-87E3-CDCF8D0EB95E",
     "E944АD90-169E-F7D2-87E3-CDCF8D0EB95E"),
    ("APP_DEVICE_ID", "device id A225FE22F95E2C311E3371C809DF18ED",
     "A225FE22F95E2C311E3371C809DF18ED"),
    # GIS_ZHKH_ELS — the mixed-script series (already tolerant; pinned here so the
    # yellow zone's own witness carries its one already-green row).
    ("GIS_ZHKH_ELS", "елс 20ЯM566083", "20ЯM566083"),
    ("GIS_ZHKH_ELS", "ЕЛС 20ЯМ566083", "20ЯМ566083"),
    # ACCESS_PASS_NUMBER — the four-digit printed pass.
    ("ACCESS_PASS_NUMBER", "пропуск 8178", "8178"),
    ("ACCESS_PASS_NUMBER", "номер пропуска 0763", "0763"),
    ("ACCESS_PASS_NUMBER", "карта доступа 5504", "5504"),
    ("ACCESS_PASS_NUMBER", "пропуск 0034561", "0034561"),
]

YELLOW_NEGATIVES: list[tuple[str, str]] = [
    # PNR: a Russian word after a Russian cue, and a plain «no value» sentence.
    ("PNR", "PNR не найден"),
    ("PNR", "номер брони уточните"),
    ("PNR", "бронь отеля"),
    # the reason the all-letter alternative lives behind the LATIN cue only
    ("PNR", "бронь HOTEL"),
    # ACCESS: the year, in both notations the deny names.
    ("ACCESS_PASS_NUMBER", "пропуск на 2024 год"),
    ("ACCESS_PASS_NUMBER", "пропуск на 2024 г."),
    ("ACCESS_PASS_NUMBER", "карта доступа не работает"),
    # PTS: the passport's series — four digits, no letter group.
    ("PTS_NUMBER", "серия 1234 номер 567890"),
    ("PTS_NUMBER", "ПТС не найден"),
    # EXEC: the cue with no document number at all.
    ("EXEC_DOC_NO", "исполнительный лист не найден"),
]


def test_yellow_zone_is_closed_without_over_masking(detector: Detector) -> None:
    """THE YELLOW ZONE, POSITIVE AND NEGATIVE IN ONE RUN: a rule proved only on
    what it must find is a rule nobody knows the rest of."""
    problems: list[str] = []
    for type_id, text, value in YELLOW_POSITIVES:
        if not _found(detector, text, type_id, value):
            problems.append(f"{type_id}: {text!r} -> {_types_found(detector, text)}")
    for type_id, text in YELLOW_NEGATIVES:
        spans = detector.detect(text)
        if any(span.entity_type == type_id for span in spans):
            problems.append(f"{type_id}: OVER-MASK on {text!r} -> "
                            f"{[(s.entity_type, s.value) for s in spans]}")
    check("the yellow zone is closed and its negatives are untouched",
          not problems, "; ".join(problems) if problems
          else f"{len(YELLOW_POSITIVES)} positives + {len(YELLOW_NEGATIVES)} negatives")


def test_yellow_zone_round_trips(detector: Detector) -> None:
    """A RECOGNIZER WITHOUT A RESTORER HANDS THE TOOL A FAKE. Every new reading is
    driven mask → unmask on the real pipeline, and the vault's own token scan must
    find the substitute it minted (the PNR all-letter and four-digit pass readings
    are new TOKEN shapes, so this is the row that would catch a shape the
    recognizer knows and the restorer does not)."""
    problems: list[str] = []
    for type_id, text, value in YELLOW_POSITIVES:
        vault = _vault()
        spans = detector.detect(text)
        masked = mask_text(text, vault, spans)
        if value in masked:
            problems.append(f"{type_id}: the real value is still in {masked!r}")
            continue
        restored = unmask_text(masked, vault)
        if value not in restored:
            problems.append(f"{type_id}: {masked!r} -> {restored!r} "
                            f"(expected {value!r})")
    check("every yellow-zone reading is masked and restored", not problems,
          "; ".join(problems) if problems
          else f"{len(YELLOW_POSITIVES)} round trips")


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    test_span_label_is_the_registry_id(detector)
    test_engine_label_bridge_is_total_and_exact()
    test_gap_types_are_detected(detector)
    test_gap_types_round_trip(detector)
    test_sweep_found_four_more_zero_coverage_types(detector)
    test_extra_types_round_trip(detector)
    test_mac_is_not_a_uuid_prefix(detector)
    test_card_cue_literal_is_shared_not_copied()
    test_known_two_notation_residual(detector)
    test_gap_shapes_do_not_over_mask(detector)
    test_no_fuzzy_numerals_on_the_bare_imei(detector)
    test_typed_over_bare()
    test_glued_forms_do_not_swallow_the_neighbour()
    test_raw_cue_pass_keeps_the_customer_characters(detector)
    test_damaged_cue_is_read_and_intact_cue_wins(detector)
    test_cue_literal_and_coordinated_list(detector)
    test_leased_cue_sources_all_parse()
    test_gis_series_is_script_tolerant_and_squeezed(detector)
    test_shapes_widened_on_measured_bounds(detector)
    test_yellow_zone_is_closed_without_over_masking(detector)
    test_yellow_zone_round_trips(detector)
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: " + "; ".join(_FAILURES))
        return 1
    print("G7 gaps OK — labels are the registry ids, six types detect, mask and restore")
    return 0


if __name__ == "__main__":
    sys.exit(main())
