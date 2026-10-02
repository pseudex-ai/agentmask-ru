"""C1 — ВРЕМЕННЫЕ СЕКРЕТЫ: CARD_VERIFICATION_CODE и ISSUER_OTP.

Владельческое решение `EX-O-SECRET-1` («Всё семейство, часть — описательно»)
измеряет ДВА класса: код проверки карты и одноразовый код эмитента. TOTP/2FA,
recovery-коды, коды авторизации операции и PIN остаются НАЗВАННЫМ ПРОБЕЛОМ
(NOT_MEASURED) — их фикстуры обязаны оставаться открытыми, и §gap это проверяет.

Что здесь проверяется, по секциям, и каждая секция называет своё падающее
свидетельство:

  §red       — девять RED-свойств C0 (`work/C0/RED.log`), каждое тем самым
               фикстуром, который его воспроизвёл. RED-6 закрыт С ГРАНИЦЕЙ: см.
               `test_red6_two_classes_with_the_accepted_cue`.
  §negative  — десять жёстких негативов и четыре контроля в ТОМ ЖЕ прогоне, что
               и позитивы: полнота без точности покупается одной строкой.
  §length    — ОБЪЯВЛЕННОЕ множество длин по алиасу (3 для CVV2/CVC2/CSC, 4 для
               CID/4DBC) и НЕОБЪЯВЛЕННАЯ длина ISSUER_OTP.
  §mint      — формат-сохранение, отсутствие ведущего нуля (иначе некавыченное
               числовое поле JSON перестаёт разбираться), крошечный домен.
  §restore   — текст / аргументы / поток, форма агента, названный остаток.
  §collision — отказ крошечного домена (O-SECRET-8) и то, что осталось открытым.
  §gap       — NOT_MEASURED-семейства видны как пробел, а не закрыты молчанием.
  §mutants   — три мутации, каждая ОБЯЗАНА покрасить эту же сюиту.

ЗНАЧЕНИЯ СИНТЕТИЧЕСКИЕ, из блока C0 `FIXTURES.json`; ничего не собрано, не
транзакции и не из реального инструмента.

    python3 test_cvc_otp.py
"""

import dataclasses
import json
import re
import sys

import testkit
from pseudex import cvc
from pseudex.assets import ASSETS, RuPiiAssets, StructuredAssets
from pseudex.detect_all import Detector
from pseudex.redact import (mask_text, surviving_substitutes, unmask_arguments,
                            unmask_stream_chunk, unmask_text)
from pseudex.ru_pii import validate_luhn
from pseudex.structured import detect_structured_kv
from pseudex.vault import Vault

CVC = cvc.CARD_VERIFICATION_CODE
OTP = cvc.ISSUER_OTP

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(label)


def note(line: str) -> None:
    print(f"      {line}")


# --- the C0 fixtures, verbatim -------------------------------------------------
#
# (id, text, target, expected type, kind). Copied from `work/C0/FIXTURES.json` so
# this suite and the RED evidence name the same strings.

POSITIVES: tuple[tuple[str, str, str, str], ...] = (
    ("POS-CVC-001", '{"cvc": "314"}', "314", CVC),
    ("POS-CVC-002", '{"cvv2": "042"}', "042", CVC),
    ("POS-CVC-003", '{"cid": "0000"}', "0000", CVC),
    ("POS-CVC-004", '{"card": {"number": "4111111111111111", "cvc": "999"}}', "999", CVC),
    ("POS-CVC-005", "CVV: 314", "314", CVC),
    ("POS-CVC-006", "cvc 314", "314", CVC),
    ("POS-CVC-007", "защитный код карты 042", "042", CVC),
    ("POS-CVC-008",
     '{"card": {"number": "4111111111111111", "cvc": "042"}, '
     '"card2": {"number": "4111111111111112", "cvc": "314"}}', "042", CVC),
    ("POS-OTP-001", "код подтверждения из смс 991991", "991991", OTP),
    ("POS-OTP-002", "одноразовый код 042042", "042042", OTP),
    ("POS-OTP-003", '{"otp": "000000"}', "000000", OTP),
    ("POS-OTP-004", "3-D Secure код 999999", "999999", OTP),
)

HARD_NEGATIVES: tuple[tuple[str, str], ...] = (
    ("NEG-JSON-1", '{"order_code": "314"}'),
    ("NEG-JSON-2", '{"status": "042"}'),
    ("NEG-JSON-3", '{"code": "314"}'),
    ("NEG-FORM-1", "код товара: 314"),
    ("NEG-PROSE-1", "заказ 314"),
    ("NEG-PROSE-2", "квартира 042"),
    ("NEG-PROSE-3", "код 314"),
    ("NEG-OTP-1", "номер заказа 991991"),
    ("NEG-OTP-2", "артикул 042042"),
    ("NEG-OTP-3", '{"sms_count": "000000"}'),
)

MALFORMED: tuple[tuple[str, str, str], ...] = (
    ("MAL-CVC-001", '{"cvc": "31"}', "31"),
    ("MAL-CVC-002", '{"cvc": "31B"}', "31B"),
)

FORM_FIDELITY: tuple[tuple[str, str, str], ...] = (
    ("FORM-CVC-001", "cvv:314", "314"),
    ("FORM-CVC-002", "CVV   314", "314"),
    ("FORM-CVC-003", "cvc 000", "000"),
)

CANDIDATES: tuple[tuple[str, str], ...] = (
    ("CAND-TOTP-001", "код 2FA 042042"),
    ("CAND-REC-001", "резервный код AAAA-0002"),
)


def _vault(name: str) -> Vault:
    return Vault(":memory:", name).for_conversation("c1")


def _typed(detector: Detector, text: str, value: str) -> list[str]:
    """Types a detector gives to THIS value in THIS text (not to any span)."""
    return [span.entity_type for span in detector.detect(text) if span.value == value]


# --- §red ---------------------------------------------------------------------

def test_red1_fielded_cvc(detector: Detector) -> None:
    for fixture_id, text, target, expected in POSITIVES[:4] + (POSITIVES[6],):
        types = _typed(detector, text, target)
        check(f"RED-1 {fixture_id}: {target} under its field name is typed",
              expected in types, f"types={types}")


def test_red2_form_field_with_colon(detector: Detector) -> None:
    types = _typed(detector, "CVV: 314", "314")
    check("RED-2 'CVV: 314' — a form label types its value",
          CVC in types, f"types={types}")


def test_red3_unquoted_json_number(detector: Detector) -> None:
    # THE STRUCTURAL GAP, asked of the layer that owns the regex rather than of
    # the whole pipeline: `{"cvc": 314}` is an unquoted JSON number.
    spans = detect_structured_kv('{"cvc": 314}')
    types = [span.entity_type for span in spans if span.value == "314"]
    check("RED-3 '{\"cvc\": 314}' — the unquoted numeric form is typed",
          CVC in types, f"types={types}")


def test_red4_issuer_otp(detector: Detector) -> None:
    for fixture_id, text, target, expected in POSITIVES[8:]:
        types = _typed(detector, text, target)
        check(f"RED-4 {fixture_id}: the one-time code is typed {OTP}",
              expected in types, f"types={types}")


def test_red5_malformed_is_masked_not_passed(detector: Detector) -> None:
    vault = _vault("red5")
    for fixture_id, text, target in MALFORMED:
        spans = detector.detect(text)
        covered = [span for span in spans
                   if text[span.start:span.end] == target]
        check(f"RED-5 {fixture_id}: the malformed value under the field is masked",
              bool(covered), f"spans={[(s.entity_type, s.value) for s in spans]}")
        masked = mask_text(text, vault, spans)
        check(f"RED-5 {fixture_id}: it never travels in the clear",
              target not in masked, f"masked={masked!r}")
        check(f"RED-5 {fixture_id}: masked as OPAQUE, not as a fake of the class",
              all(span.entity_type == "OPAQUE" for span in covered),
              f"types={[span.entity_type for span in covered]}")


def test_red6_two_classes_with_the_accepted_cue(detector: Detector) -> None:
    """RED-6: one card code and one issuer OTP in ONE utterance, DIFFERENT classes.

    CLOSED WITH A BOUNDARY, and the boundary is named rather than papered over.
    The property is demonstrated on the cue set this engine accepts. The C0
    fixture writes the bare «код подтверждения» — and TWO independent pinned
    suites forbid it as PII (`test_hard_cases`: «код подтверждения 112233»;
    `test_pii_v6` FINANCE_NEGATIVES: «код подтверждения 4521»), while C0 leaves
    that fork OWNER_PENDING (O-SECRET-2). So the engine keeps the boundary those
    cases fixed — a one-time or channel qualifier is required — and RED-6 is
    PARTIAL against the fixture's exact wording. Both halves are asserted below:
    the property with the accepted cue, and the fixture's actual outcome.
    """
    text = "cvc 314, код подтверждения из смс 991991"
    types = {span.value: span.entity_type for span in detector.detect(text)}
    check("RED-6 (accepted cue): the card code and the one-time code in one "
          "utterance receive DIFFERENT classes",
          types.get("314") == CVC and types.get("991991") == OTP,
          f"{types}")
    negative = "cvc 314, код подтверждения 991991"
    types = {span.value: span.entity_type for span in detector.detect(negative)}
    check("RED-6 (exact C0 fixture): the CARD CODE half is typed CVC",
          types.get("314") == CVC, f"{types}")
    check("RED-6 (exact C0 fixture): bare «код подтверждения» stays open — the "
          "O-SECRET-2 boundary, not a defect",
          "991991" not in types, f"{types}")
    print("      BOUNDARY: RED-6 partial — the bare «код подтверждения» cue is "
          "rejected by two pinned negative suites; O-SECRET-2 decides it.")


def test_red7_two_card_objects(detector: Detector) -> None:
    fixture = POSITIVES[7][1]
    vault = _vault("red7")
    spans = detector.detect(fixture)
    codes = [span for span in spans if span.entity_type == CVC]
    check("RED-7 two card objects: BOTH codes are typed", len(codes) == 2,
          f"{[(s.value, s.entity_type) for s in spans]}")
    masked = mask_text(fixture, vault, spans)
    # PER-OBJECT BINDING IS STRUCTURAL, NOT A GUESS: a row is keyed by the VALUE,
    # and `_is_free_token` refuses a substitute equal to any row of this customer,
    # so one substitute never stands for two different real codes — two objects
    # cannot exchange values. Two DIFFERENT codes therefore get two substitutes.
    fakes = re.findall(r'"cvc": "(\d+)"', masked)
    check("RED-7 two different codes get two different substitutes",
          len(set(fakes)) == 2 and "042" not in fakes and "314" not in fakes,
          f"fakes={fakes}")
    check("RED-7 the round trip is exact for both objects",
          unmask_text(masked, vault) == fixture, f"{unmask_text(masked, vault)!r}")


def test_red8_never_a_redacted_marker_in_a_numeric_field(detector: Detector) -> None:
    vault = _vault("red8")
    spans = detector.detect('{"cvc": "314"}')
    masked = mask_text('{"cvc": "314"}', vault, spans)
    value = json.loads(masked)["cvc"]
    check("RED-8 a card-code field renders card-code shaped, never REDACTED…",
          bool(re.fullmatch(r"[1-9]\d{2}", value)), f"substitute={value!r}")
    check("RED-8 the substitute is not the missing-renderer fallback",
          "REDACTED" not in value, f"substitute={value!r}")


def test_red9_compound_key_is_not_mistyped_as_card(detector: Detector) -> None:
    vault = _vault("red9")
    for text in ('{"card_cvc": "314"}', '{"cardcvc": "314"}'):
        types = _typed(detector, text, "314")
        check(f"RED-9 {text}: the compound authoritative key types CVC, not CARD",
              types == [CVC], f"types={types}")
    masked = mask_text('{"card_cvc": "314"}', vault, detector.detect('{"card_cvc": "314"}'))
    value = json.loads(masked)["card_cvc"]
    check("RED-9 the substitute has the SOURCE's length, never sixteen digits",
          len(value) == 3, f"substitute={value!r}")
    check("RED-9 the substitute is not a card number", not re.fullmatch(r"\d{16}", value),
          f"substitute={value!r}")


# --- §negative ----------------------------------------------------------------

def test_negatives_and_controls_stay_green(detector: Detector) -> None:
    for fixture_id, text in HARD_NEGATIVES:
        types = [span.entity_type for span in detector.detect(text)
                 if span.entity_type in cvc.LABEL_SET]
        check(f"{fixture_id}: stays OPEN in the same run as the positives",
              not types, f"types={types}")
    controls = (
        ('{"password": "hunter2"}', "SECRET", "hunter2"),
        ('{"card": "4111111111111111"}', "CARD", "4111111111111111"),
        ("4111 1111 1111 1111", "CARD", "4111 1111 1111 1111"),
    )
    for text, expected, target in controls:
        types = _typed(detector, text, target)
        check(f"control: {text!r} still types {expected}", expected in types,
              f"types={types}")
    check("the fixture set protects exactly the two declared classes",
          all(any(span.entity_type == expected for span in detector.detect(text))
              for _id, text, _target, expected in POSITIVES))


def test_forbidden_discriminators(detector: Detector) -> None:
    # P05 / OWNER-DECISIONS Q3 and the C0 forbidden list, as four witnesses.
    for text in ("заказ 314", "квартира 042", "номер 999", "позиция 12",
                 "4111111111111111 314", "счёт 991991 042042"):
        types = [span.entity_type for span in detector.detect(text)
                 if span.entity_type in cvc.LABEL_SET]
        check(f"forbidden: a bare digit run / PAN proximity does not type the "
              f"class — {text!r}", not types, f"types={types}")
    for text in ('{"code": "314"}', '{"код": "314"}', "код 314", "код 3141"):
        types = [span.entity_type for span in detector.detect(text)
                 if span.entity_type in cvc.LABEL_SET]
        check(f"forbidden: the generic cue alone types nothing — {text!r}",
              not types, f"types={types}")


# --- §length ------------------------------------------------------------------

def test_declared_length_set_per_alias(detector: Detector) -> None:
    expected = {"cvc": 3, "cvv": 3, "cvv2": 3, "csc": 3, "cav2": 3,
                "card_cvc": 3, "card_code": 3, "security_code": 3,
                "cid": 4, "4dbc": 4}
    for alias, size in expected.items():
        check(f"declared set: {alias} -> {size} digit(s)",
              cvc.field_lengths(alias) == (size,), f"{cvc.field_lengths(alias)}")
    check("no unbounded 3..4 set: the two lengths are declared SEPARATELY",
          cvc.field_lengths("cvv") == (3,) and cvc.field_lengths("cid") == (4,))


def test_length_mismatch_under_a_key_is_masked_not_passed(detector: Detector) -> None:
    vault = _vault("length")
    for text, target in (('{"cvc": "3140"}', "3140"), ('{"cid": "314"}', "314")):
        spans = detector.detect(text)
        covered = [span for span in spans if span.value == target]
        check(f"a length outside the declared set is masked, not passed: {text!r}",
              bool(covered) and all(s.entity_type == "OPAQUE" for s in covered),
              f"{[(s.entity_type, s.value) for s in spans]}")
        check(f"and it never travels in the clear: {text!r}",
              target not in mask_text(text, vault, spans))
    # THE DECLARED SET IS WHAT THE CUE HONOURS TOO: «cvv 0420» is four digits
    # under a THREE-digit alias, so the cue does not claim it (and a malformed
    # value under a CUE is not demoted — the cue is not the customer's field, and
    # every digit run after a cue would swallow a card PAN and a year). Recorded
    # in TYPES.md §length as the one place the key path is stricter than the cue
    # path.
    types = [span.entity_type for span in detector.detect("cvv 0420")]
    check("the cue honours the declared set: 'cvv 0420' is not a three-digit CVC",
          CVC not in types, f"types={types}")
    check("…and a 4-digit CID cue does claim four digits",
          CVC in [s.entity_type for s in detector.detect("cid 0420")])


def test_otp_length_is_unasserted(detector: Detector) -> None:
    # NO LENGTH IS DECLARED FOR ISSUER_OTP ANYWHERE, and the field path takes the
    # value AS WRITTEN — every one of these is typed, so no width was invented.
    widths = (4, 5, 6, 7, 8, 10, 12)
    vault = _vault("otplen")
    for width in widths:
        value = "".join(str((index + width) % 10) for index in range(width))
        text = json.dumps({"otp": value})
        types = _typed(detector, text, value)
        check(f"unasserted length: an {width}-digit issuer OTP field is typed",
              types == [OTP], f"types={types}")
        masked = mask_text(text, vault, detector.detect(text))
        substitute = json.loads(masked)["otp"]
        check(f"unasserted length: the {width}-digit substitute keeps the width",
              len(substitute) == width, f"substitute={substitute!r}")
    check("nothing in the engine declares an OTP length",
          not hasattr(cvc, "OTP_LENGTHS") and not hasattr(cvc, "OTP_ALIAS_LENGTHS"))


# --- §mint --------------------------------------------------------------------

def test_mint_is_format_preserving(detector: Detector) -> None:
    vault = _vault("mint")
    samples = (("cvc", "314", 3), ("cvc", "042", 3), ("cvc", "000", 3),
               ("cid", "0000", 4), ("cid", "9999", 4))
    for key, source, size in samples:
        text = json.dumps({key: source})
        masked = mask_text(text, vault, detector.detect(text))
        substitute = json.loads(masked)[key]
        check(f"mint {key}={source!r}: length and shape preserved",
              len(substitute) == size and substitute.isdigit(),
              f"substitute={substitute!r}")
        check(f"mint {key}={source!r}: never equal to the source", substitute != source,
              f"substitute={substitute!r}")
        check(f"mint {key}={source!r}: never a card — Luhn cannot hold on {size} digits",
              not validate_luhn(substitute))
        check(f"mint {key}={source!r}: no separator, so it is not card-shaped",
              " " not in substitute and substitute.isascii())


def test_mint_never_leads_with_zero(detector: Detector) -> None:
    """WHY, measured rather than asserted: `{"cvc": 314}` is an unquoted JSON
    number and masking happens on the TEXT, so a substitute beginning with zero
    leaves `{"cvc": 042}` behind — an object `json.loads` refuses, which the model
    cannot read back and the tool never receives. The source MAY carry a leading
    zero (it is a legal value and `{"cvc": "042"}` is typed); the substitute
    simply never produces one. Recorded in TYPES.md §mint as the one place the
    substitute is narrower than the source's form."""
    for entity_type, original in ((CVC, "314"), (CVC, "0000"), (OTP, "042042")):
        drawn = [cvc.mint(entity_type, original) for _ in range(200)]
        check(f"mint {entity_type}({original!r}) never starts with zero",
              all(value[0] != "0" for value in drawn), f"sample={drawn[:5]}")
        check(f"mint {entity_type}({original!r}) keeps the width",
              {len(value) for value in drawn} == {len(original)})
    broken = {"cvc": "042"}
    check("witness: the rejected alternative would not parse",
          _json_fails('{"cvc": 042}'), f'{broken} vs {{"cvc": 042}}')
    check("the drawn substitute DOES parse in the unquoted field",
          json.loads('{"cvc": %s}' % cvc.mint(CVC, "314"))["cvc"] > 0)


def _json_fails(text: str) -> bool:
    try:
        json.loads(text)
        return False
    except json.JSONDecodeError:
        return True


def test_mint_unquoted_json_field_stays_parseable(detector: Detector) -> None:
    vault = _vault("jsonnum")
    for _ in range(50):
        masked = mask_text('{"cvc": 314, "otp": 991991}', vault,
                           detector.detect('{"cvc": 314, "otp": 991991}'))
        try:
            parsed = json.loads(masked)
        except json.JSONDecodeError as error:  # pragma: no cover - the defect
            check("unquoted numeric fields stay valid JSON", False,
                  f"{masked!r}: {error}")
            return
        if not isinstance(parsed["cvc"], int) or not isinstance(parsed["otp"], int):
            check("unquoted numeric fields keep their JSON type", False, f"{masked!r}")
            return
    check("unquoted numeric fields stay valid JSON and keep their type over 50 mints",
          True, f"last={masked!r}")


def test_tiny_domain_fails_loudly() -> None:
    """A 3-digit substitute space is a THOUSAND values (900 without a leading
    zero), and each mint consumes one as a key and one as a substitute. The
    failure must be LOUD and bounded — a RuntimeError the gateway turns into a
    5xx — never a hung request and never a reused substitute. The measured
    capacity is printed; the assertion is only the bound, so this test does not
    pin a number that a different pool would move."""
    vault = _vault("tiny")
    minted = 0
    raised: RuntimeError | None = None
    try:
        for index in range(2000):
            vault.tokenize(f"{index % 1000:03d}", CVC)
            minted += 1
    except RuntimeError as error:
        raised = error
    check("the tiny domain fails CLOSED (RuntimeError, not a wrong value)",
          raised is not None and "token pool" in str(raised), f"raised={raised}")
    check("…and it fails BOUNDED, well inside the declared domain", minted < 1000,
          f"minted={minted}")
    note(f"MEASURED tiny-domain capacity of one customer on this run: "
         f"{minted} distinct card codes before the loud refusal")


# --- §restore -----------------------------------------------------------------

def test_round_trip_text_args_stream(detector: Detector) -> None:
    vault = _vault("hop")
    for fixture_id, text, target, expected in POSITIVES:
        spans = detector.detect(text)
        masked = mask_text(text, vault, spans)
        check(f"{fixture_id}: the value never reaches the model",
              target not in masked or expected not in [s.entity_type for s in spans],
              f"masked={masked!r}")
        check(f"{fixture_id}: text leg restores exactly", unmask_text(masked, vault) == text,
              f"{unmask_text(masked, vault)!r}")
        check(f"{fixture_id}: args leg restores exactly",
              unmask_arguments(masked, vault) == text,
              f"{unmask_arguments(masked, vault)!r}")
    text = "код подтверждения из смс 991991"
    masked = mask_text(text, vault, detector.detect(text))
    # ONE CARRY PER STREAM, the contract of `/unmask_chunk`: the tail is withheld
    # so a substitute split across two SSE deltas is still replaced.
    cut = 14
    emitted, carry = unmask_stream_chunk(masked[:cut], "", vault, False)
    emitted += unmask_stream_chunk(carry + masked[cut:] + " спасибо", "", vault, True)[0]
    check("stream leg restores across a split chunk",
          "991991" in emitted and "спасибо" in emitted, f"emitted={emitted!r}")


def test_args_leg_numeric_field(detector: Detector) -> None:
    vault = _vault("numfield")
    unmasked = unmask_arguments('{"cvc": 314}', vault)
    check("args leg: an UNQUOTED numeric card-code field is restored",
          json.loads(unmasked)["cvc"] == 314, f"{unmasked!r}")
    masked = mask_text('{"cvc": 314}', vault, detector.detect('{"cvc": 314}'))
    check("args leg: the substitute is a JSON number, not a string",
          isinstance(json.loads(masked)["cvc"], int), f"{masked!r}")
    check("args leg: round trip through both legs",
          unmask_arguments(masked, vault) == '{"cvc": 314}',
          f"{unmask_arguments(masked, vault)!r}")


def test_form_is_inherited(detector: Detector) -> None:
    vault = _vault("form")
    for fixture_id, text, target in FORM_FIDELITY:
        masked = mask_text(text, vault, detector.detect(text))
        check(f"{fixture_id}: the value slot keeps the customer's own writing",
              target not in masked and len(re.findall(r"\d+", masked)) >= 1,
              f"masked={masked!r}")
        check(f"{fixture_id}: the surrounding form is byte-identical",
              _form_skeleton(masked) == _form_skeleton(text.replace(target, "X" * len(target))),
              f"{masked!r}")
        check(f"{fixture_id}: restored exactly", unmask_text(masked, vault) == text,
              f"{unmask_text(masked, vault)!r}")


def _form_skeleton(text: str) -> str:
    return re.sub(r"\d+", lambda m: "X" * len(m.group()), text)


def test_residual_is_named_not_trusted(detector: Detector) -> None:
    vault = _vault("residual")
    masked = mask_text('{"cvc": "314"}', vault, detector.detect('{"cvc": "314"}'))
    token = json.loads(masked)["cvc"]
    # A substitute the class does not licence — a business field with the same
    # digits — is NOT resolved, and it is NAMED rather than emitted as a value.
    for text in (f'{{"quantity": "{token}"}}', f"заказ {token}", f'{{"cvc": "{token}"}}'):
        restored = unmask_text(text, vault)
        residual = surviving_substitutes(text, restored, vault, False)
        if token in text and "cvc" in text:
            check(f"a licensed substitute resolves: {text!r}", "314" in restored,
                  f"{restored!r}")
        else:
            check(f"an unlicensed substitute is left standing: {text!r}",
                  restored == text, f"{restored!r}")
            check(f"…and NAMED as a residual: {text!r}", token in residual,
                  f"residual={residual}")


# --- §collision ---------------------------------------------------------------

def test_tiny_domain_refusal(detector: Detector) -> None:
    """O-SECRET-8: value-only pairing is forbidden for a 1000-value domain.

    The engine's guard is that a substitute may never equal a value the customer
    already holds (`_is_free_token`), which keeps substitute↔value one-to-one —
    so two objects can never exchange VALUES. The refusal is the context gate on
    the way back: a substitute resolves only where the class is named.
    """
    vault = _vault("collision")
    masked = mask_text('{"cvc": "314"}', vault, detector.detect('{"cvc": "314"}'))
    token = json.loads(masked)["cvc"]
    check("the mint never equals a value the customer already holds",
          token != "314", f"token={token!r}")
    check("the substitute is not reused for a different real code",
          vault.tokenize("999", CVC) != token, f"{vault.tokenize('999', CVC)!r}")
    check("a licensed occurrence resolves",
          "314" in unmask_text(f'{{"cvc": "{token}"}}', vault))
    check("an occurrence the class does not licence does NOT resolve to the real "
          "code — the explicit refusal",
          "314" not in unmask_text(f'{{"quantity": "{token}"}}', vault))


def test_fork_o_secret_8_mask_direction_is_pinned(detector: Detector) -> None:
    """THE UNRESOLVED HALF, PINNED RATHER THAN HIDDEN.

    With a 1000-value domain, a REAL code equal to a substitute this dialogue
    already showed is indistinguishable from the echo of that substitute, and the
    engine's echo guard (`is_minted_token`) treats it as ours: the real value is
    then NOT masked. That is a leak in the mask direction, it is the exact
    collision A7 names, and the owner has not decided it (O-SECRET-8). This test
    asserts the CURRENT behaviour so the residual cannot change silently, and
    prints it as a residual — it does NOT claim the behaviour is correct.
    """
    vault = _vault("fork8")
    masked = mask_text('{"cvc": "314"}', vault, detector.detect('{"cvc": "314"}'))
    token = json.loads(masked)["cvc"]
    re_masked = mask_text(f'{{"cvc": "{token}"}}', vault, detector.detect(f'{{"cvc": "{token}"}}'))
    check("O-SECRET-8 (residual): a real value equal to a shown substitute in the "
          "SAME conversation is treated as the echo", re_masked == f'{{"cvc": "{token}"}}',
          f"{re_masked!r}")
    note("RESIDUAL O-SECRET-8: mask-direction forward collision is NOT resolved; "
         "it needs per-(field,operation) binding, which is the owner's fork.")


# --- §gap ---------------------------------------------------------------------

def test_pending_families_are_visible_gaps() -> None:
    detector = Detector()
    for fixture_id, text in CANDIDATES:
        types = [span.entity_type for span in detector.detect(text)
                 if span.entity_type in cvc.LABEL_SET]
        check(f"{fixture_id}: OWNER_PENDING — stays open, not silently closed",
              not types, f"types={types}")
    pending = ("TOTP_2FA", "RECOVERY_CODE", "TRANSACTION_AUTH_CODE", "CARD_PIN")
    check("the module declares exactly the two measured classes",
          cvc.LABELS == (CVC, OTP), f"{cvc.LABELS}")
    key_values = set(ASSETS.get().structured.key_type.values())
    check("no engine label exists for a pending family",
          not (set(pending) & key_values), f"{sorted(set(pending) & key_values)}")
    check("priority table carries no pending label",
          not (set(pending) & set(ASSETS.get().priority)))
    for text in ('{"pin": "1234"}', '{"totp": "123456"}',
                 '{"recovery_code": "AAAA-0002"}',
                 '{"transaction_auth_code": "123456"}',
                 '{"card_expiry": "12/29"}'):
        types = [span.entity_type for span in detector.detect(text)
                 if span.entity_type in cvc.LABEL_SET]
        check(f"outside the class: {text!r} is not typed as a temporary secret",
              not types, f"types={types}")
    note("GAP NOT_MEASURED: TOTP/2FA, RECOVERY_CODE, TRANSACTION_AUTH_CODE, "
         "CARD_PIN — documented, no denominator asserted, no RED executed")


# --- §lease wiring -------------------------------------------------------------

def test_lease_wiring_is_complete() -> None:
    assets = ASSETS.get()
    key_type = assets.structured.key_type
    cvc_keys = [key for key, value in key_type.items() if value == CVC]
    otp_keys = [key for key, value in key_type.items() if value == OTP]
    check("the lease names card-code fields", bool(cvc_keys), f"{sorted(cvc_keys)}")
    check("the lease names issuer-OTP fields", bool(otp_keys), f"{sorted(otp_keys)}")
    undeclared = sorted(key for key in cvc_keys if not cvc.field_lengths(key))
    check("EVERY leased card-code key declares a length — a key with no declared "
          "length is a hole, not an unknown", not undeclared, f"{undeclared}")
    labels = {entity_type for entity_type, _ in assets.ru_pii.ctx_patterns}
    check("the lease carries cues for both classes", cvc.LABEL_SET <= labels,
          f"{sorted(cvc.LABEL_SET - labels)}")
    for label in cvc.LABELS:
        token = cvc.mint(label, "314")
        check(f"a renderer exists for {label} (never REDACTED…)", "REDACTED" not in token,
              f"{token!r}")
    unreachable = sorted(alias for alias in cvc.CVC_ALIAS_LENGTHS
                         if not any(key.startswith(alias) for key in cvc_keys))
    check("every declared alias is reachable from the lease — an alias the map "
          "cannot be asked about is dead weight", not unreachable, f"{unreachable}")


# --- §mutants ------------------------------------------------------------------

def _mutants(detector: Detector) -> None:
    """THREE MUTATIONS, EACH OF WHICH MUST TURN THE CHECKS ABOVE RED.

    A suite that cannot fail is not an instrument. Each mutation is applied to
    the smallest real knob — the leased key map, the leased cue patterns, the
    renderer — the same check functions from the sections above are re-run, and
    the mutation is reverted. `check` is the single sink, so a mutation is
    "killed" exactly when it adds a failure.
    """
    saved = ASSETS._current
    assets = ASSETS.get()

    def run(name: str, mutation, failing_check) -> None:
        before = len(_FAILURES)
        ASSETS._current = mutation
        try:
            failing_check(detector)
        finally:
            ASSETS._current = saved
        kills = len(_FAILURES) - before
        del _FAILURES[before:]
        check(f"mutation {name}: killed", kills > 0, f"new failures={kills}")

    # MUTANT A — the CVC key dropped from the leased map. RED-9 is what this
    # reproduces: `card_cvc` falls back to the `card` stem and types CARD.
    def drop_keys():
        structured = assets.structured
        dropped = {key for key, value in structured.key_type.items()
                   if value in cvc.LABEL_SET}
        return dataclasses.replace(
            assets, structured=StructuredAssets(
                key_type={key: value for key, value in structured.key_type.items()
                          if key not in dropped},
                key_stems=tuple((key, value) for key, value in structured.key_stems
                                if key not in dropped),
                composites=structured.composites))

    def keyed_check(det: Detector) -> None:
        types = _typed(det, '{"cvc": "314"}', "314")
        check("MUTANT-A fielded CVC protected", CVC in types, f"types={types}")
        types = _typed(det, '{"card_cvc": "314"}', "314")
        check("MUTANT-A card_cvc not mistyped as CARD", types == [CVC], f"types={types}")

    run("A (CVC key dropped)", drop_keys(), keyed_check)

    # MUTANT B — a bare digit run accepted as the class. Every same-glyph
    # business negative must go red at once.
    def bare_runs():
        ru = assets.ru_pii
        bare = re.compile(r"((?<!\d)\d{3,4}(?!\d))")
        return dataclasses.replace(
            assets, ru_pii=RuPiiAssets(
                ctx_patterns=ru.ctx_patterns + ((CVC, bare),),
                inn_context=ru.inn_context))

    def bare_check(det: Detector) -> None:
        opened = [text for _fixture_id, text in HARD_NEGATIVES
                  if any(span.entity_type in cvc.LABEL_SET for span in det.detect(text))]
        check("MUTANT-B every same-glyph negative stays open", not opened,
              f"opened={opened}")

    run("B (bare digit run accepted)", bare_runs(), bare_check)

    # MUTANT C — the 3-digit substitute replaced by a 16-digit card number: RED-9's
    # executed consequence.
    original_mint = cvc.mint

    def card_fake(entity_type: str, original: str) -> str:
        return "0162727135052316"

    def card_check(det: Detector) -> None:
        vault = _vault("mutant-c")
        masked = mask_text('{"cvc": "314"}', vault, det.detect('{"cvc": "314"}'))
        value = json.loads(masked)["cvc"]
        check("MUTANT-C substitute length equals the source length", len(value) == 3,
              f"substitute={value!r}")
        check("MUTANT-C substitute is not a CARD shape",
              not re.fullmatch(r"\d{16}", value), f"substitute={value!r}")

    cvc.mint = card_fake
    try:
        run("C (3 digits -> 16-digit card fake)", assets, card_check)
    finally:
        cvc.mint = original_mint


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    print("--- §red (C0/RED.log, the nine properties) ---")
    test_red1_fielded_cvc(detector)
    test_red2_form_field_with_colon(detector)
    test_red3_unquoted_json_number(detector)
    test_red4_issuer_otp(detector)
    test_red5_malformed_is_masked_not_passed(detector)
    test_red6_two_classes_with_the_accepted_cue(detector)
    test_red7_two_card_objects(detector)
    test_red8_never_a_redacted_marker_in_a_numeric_field(detector)
    test_red9_compound_key_is_not_mistyped_as_card(detector)
    print("--- §negative (positives and negatives in ONE run) ---")
    test_negatives_and_controls_stay_green(detector)
    test_forbidden_discriminators(detector)
    print("--- §length ---")
    test_declared_length_set_per_alias(detector)
    test_length_mismatch_under_a_key_is_masked_not_passed(detector)
    test_otp_length_is_unasserted(detector)
    print("--- §mint ---")
    test_mint_is_format_preserving(detector)
    test_mint_never_leads_with_zero(detector)
    test_mint_unquoted_json_field_stays_parseable(detector)
    test_tiny_domain_fails_loudly()
    print("--- §restore (text / args / stream) ---")
    test_round_trip_text_args_stream(detector)
    test_args_leg_numeric_field(detector)
    test_form_is_inherited(detector)
    test_residual_is_named_not_trusted(detector)
    print("--- §collision (O-SECRET-8) ---")
    test_tiny_domain_refusal(detector)
    test_fork_o_secret_8_mask_direction_is_pinned(detector)
    print("--- §gap (NOT_MEASURED) ---")
    test_pending_families_are_visible_gaps()
    print("--- §lease wiring ---")
    test_lease_wiring_is_complete()
    print("--- §mutants (the suite must be able to fail) ---")
    _mutants(detector)
    print()
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} — {_FAILURES}")
        return 1
    print("CVC/ISSUER_OTP OK — 2 classes recognized, minted and restored; "
          "TOTP/recovery/transaction-auth/PIN left as a NAMED gap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
