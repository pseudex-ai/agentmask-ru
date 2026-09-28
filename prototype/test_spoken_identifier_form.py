"""Spoken identifiers retain digit grouping and case through public swap seams."""

import json
import re
from unittest.mock import patch

import testkit
from pseudex import spoken
from pseudex.detect_all import Detector
from pseudex.detect import Span
from pseudex.redact import mask_text, residual_tokens, surviving_substitutes, unmask_arguments, unmask_text
from pseudex.spoken import numeral_runs, run_to_digits
from pseudex.vault import Vault, canonicalize


# --- every numeric family v5 meets, at every length it arrives in --------------
#
# A dictated identifier must come back as the SAME NUMBER in the sender's own
# spoken grouping — for every family and every length the engine accepts, not
# only for the phone this file started with. THE SUBSTITUTE'S LENGTH IS PART OF
# THE FORM: an ИНН dictated with twelve digits and answered with ten is another
# document, and a card dictated with eighteen and answered with sixteen is a
# card the customer's own validator refuses. The fixtures are literal dictations
# and the fake is the real generator, UNPATCHED — a pinned fake would hide
# exactly the length this set exists to check.
_DICTATED_FAMILIES: tuple[tuple[str, str, str], ...] = (
    ("PHONE-11", "89265478238",
     "восемь девятьсот двадцать шесть пятьсот сорок семь восемьдесят два тридцать восемь"),
    ("PHONE-10", "9265478238",
     "девятьсот двадцать шесть пятьсот сорок семь восемьдесят два тридцать восемь"),
    ("SNILS-11", "11223344595",
     "снилс сто двенадцать двести тридцать три четыреста сорок пять девяносто пять"),
    ("INN-10", "7707083893",
     "инн семьсот семьдесят семьсот восемь тридцать восемь девяносто три"),
    ("INN-12", "500100732259",
     "инн пятьсот сто семьсот тридцать два двести пятьдесят девять"),
    ("PASSPORT-10", "4509123456",
     "паспорт сорок пять ноль девять сто двадцать три четыреста пятьдесят шесть"),
    ("CARD-16", "0123456789012347",
     "карта ноль двенадцать триста сорок пять шестьсот семьдесят восемь "
     "девятьсот один двадцать три сорок семь"),
    ("CARD-18", "012345678901234502",
     "карта ноль двенадцать триста сорок пять шестьсот семьдесят восемь "
     "девятьсот один двести тридцать четыре пятьсот два"),
    ("CARD-19", "0123456789012345002",
     "карта ноль двенадцать триста сорок пять шестьсот семьдесят восемь "
     "девятьсот один двести тридцать четыре пятьдесят ноль два"),
)


def _family_rows(detector: Detector) -> list[tuple[str, str, str]]:
    """One dictated member of each family, through the public swap seams."""
    out: list[tuple[str, str, str]] = []
    for label, identity, dictated in _DICTATED_FAMILIES:
        kind: str = label.split("-")[0]
        vault: Vault = Vault(":memory:", "spoken-identifiers").for_conversation(label)
        spans: list[Span] = detector.detect(dictated)
        out.append((label + " detected as " + kind,
                    str(any(span.entity_type == kind for span in spans)), "True"))
        shown: str = mask_text(dictated, vault, spans)
        form: tuple[str, str, str] | None = next(
            ((shown_form, original, entity) for shown_form, original, entity in vault.shown_forms()
             if entity == kind), None)
        if form is None:
            out.append((label + " substitute recorded", "no shown form", "one shown form"))
            continue
        substitute, original, _ = form
        fake: str | None = vault.peek_token(original, kind)
        # The substitute's own identity, read the way the restorer reads it.
        fake_digits: str = _digits(canonicalize(kind, fake)) if fake else ""
        # The identity the REAL mention parses to — for a ten-digit phone that is
        # an eleven-digit E.164, for an ИНН it is its own twelve digits. The mint
        # must follow THIS, never the surface digit count.
        real_digits: str = _digits(canonicalize(kind, identity))
        # The form the sender would write: no ASCII digit may survive in it.
        out.append((label + " substitute is the spoken form",
                    str(not any(char.isdigit() for char in substitute)), "True"))
        out.append((label + " minted length follows the parsed identity",
                    str(len(fake_digits)), str(len(real_digits))))
        # What the SHOWN form denotes, read with the module's own numeral
        # grammar: the sender dictated N digits and must read back N. A numeric
        # fallback denotes none, so a substitute that stopped being spoken fails
        # here as well as on the row above.
        out.append((label + " substitute denotes the sender's digit count",
                    str(len(_denoted_digits(substitute))), str(len(identity))))
        out.append((label + " substitute reads back to the fake identity",
                    str(_digits(canonicalize(kind, substitute))), fake_digits))
        out.append((label + " answer keeps the sender's words",
                    unmask_text(shown, vault), dictated))
        out.append((label + " tool keeps the sender's words", json.loads(unmask_arguments(
            json.dumps({"v": shown}, ensure_ascii=False), vault))["v"], dictated))
    return out


def _denoted_digits(substitute: str) -> str:
    """The digits a SPOKEN substitute stands for, through the module's grammar.

    Read, never authored: the expectation above is the literal the sender
    dictated, and this only asks what the engine's own numeral reader makes of
    the form it produced.
    """
    return "".join(run_to_digits(words) for _start, _stop, words in numeral_runs(substitute))


def _refusal_rows(detector: Detector) -> list[tuple[str, str, str]]:
    """The ambiguity this slice still refuses, and the form evidence it keeps.

    A hesitation INSIDE a numeral group cannot be relocated into a differently
    sized group without inventing a reading — «триста эээ сорок пять» is one
    group of 345 with a pause in the middle. The engine must SAY SO: the
    substitute falls back to the numeric token (visible), and the way back gives
    the customer's canonical digits rather than a word form nobody dictated.
    This is the one deliberate refusal in the set; it is pinned so a later
    change cannot silently start guessing.
    """
    out: list[tuple[str, str, str]] = []
    hesitant: str = ("карта ноль двенадцать триста эээ сорок пять шестьсот семьдесят восемь "
                     "девятьсот один двадцать три сорок семь")
    vault: Vault = Vault(":memory:", "spoken-identifiers").for_conversation("refusal")
    with patch("pseudex.vault._fake_card", return_value="0987 6543 2109 8765"):
        shown: str = mask_text(hesitant, vault, detector.detect(hesitant))
    out.append(("internal hesitation stays explicit: numeric substitute",
                shown, "карта 0987 6543 2109 8765"))
    out.append(("internal hesitation answer: canonical, never a guessed reading",
                unmask_text(shown, vault), "карта 0123 4567 8901 2347"))
    # THE FEMININE UNIT, recorded rather than guessed at. People read a card
    # aloud with the feminine «одна»/«две» (the noun is feminine), and the
    # renderer spells «один»/«два». A literal case is not red: where the digit
    # is UNCHANGED the sender's own word survives verbatim (below), where it
    # changes the masculine default is spelled, and BOTH read back to the same
    # digit — «одна» and «один» are the same numeral to `_canonical`. Mirroring
    # a gender habit inferred from other groups would be a new guess about the
    # sender, which is the one thing this module refuses to do.
    feminine: str = ("карта ноль двенадцать триста сорок пять шестьсот семьдесят восемь "
                     "девятьсот одна двадцать три сорок семь")
    fem_vault: Vault = Vault(":memory:", "spoken-identifiers").for_conversation("feminine")
    with patch("pseudex.vault._fake_card", return_value="0112223339014455"):
        fem_shown: str = mask_text(feminine, fem_vault, detector.detect(feminine))
    out.append(("feminine unit survives where its digit did not change",
                fem_shown, "карта ноль одиннадцать двести двадцать два триста тридцать три "
                           "девятьсот одна сорок четыре пятьдесят пять"))
    out.append(("feminine unit answer reads back to the dictation",
                unmask_text(fem_shown, fem_vault), feminine))
    return out


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def main() -> int:
    testkit.load_dev_bundle()
    detector: Detector = Detector()
    real: str = "восемь девятьсот шестнадцать двести четырнадцать восемьдесят восемь ноль три"
    fake: str = "восемь девятьсот семьдесят девять пятьсот пятьдесят пять тридцать три два два"
    digits_real: str = "восемь девять один шесть два один четыре восемь восемь ноль три"
    digits_fake: str = "восемь девять семь девять пять пять пять три три два два"
    rows: list[tuple[str, str, str]] = []
    for label, source, expected in (
        ("groups", real, fake),
        ("single digits", digits_real, digits_fake),
        ("uppercase", real.upper(), fake.upper()),
    ):
        vault: Vault = Vault(":memory:", "spoken-identifiers").for_conversation(label)
        with patch("pseudex.vault._fake_phone", return_value="+79795553322"):
            shown: str = mask_text(source, vault, detector.detect(source))
        rows.append((label + " IN", shown, expected))
        for written, wanted in ((expected, source), (digits_fake, digits_real), ("+79795553322", "+79162148803")):
            argument: str = json.dumps({"phone": written}, ensure_ascii=False)
            restored: str = json.loads(unmask_arguments(argument, vault))["phone"]
            rows.append((label + " tool " + written, restored, wanted))
            rows.append((label + " answer " + written, unmask_text(written, vault), wanted))
        remasked: str = mask_text(expected, vault, detector.detect(expected))
        rows.append((label + " no second mint", remasked, expected))
        rows.append((label + " residual before", str(expected in residual_tokens(expected, vault)), "True"))
        rows.append((label + " surviving before", str(expected in surviving_substitutes(expected, expected, vault, True)), "True"))
        rows.append((label + " no residual after", str(surviving_substitutes(expected, source, vault, True)), "[]"))
    original_snils: str = "сто двенадцать двести тридцать три четыреста сорок пять девяносто пять"
    shown_snils: str = "ноль ноль три ноль ноль четыре пятьсот шестьдесят семь восемьдесят девять"
    document: Vault = Vault(":memory:", "spoken-identifiers").for_conversation("document")
    with patch("pseudex.vault._fake_snils", return_value="003-004-567 89"):
        masked_snils: str = mask_text(original_snils, document, [Span(0, len(original_snils), "SNILS", original_snils)])
    rows.append(("SNILS leading zeros IN", masked_snils, shown_snils))
    rows.append(("SNILS copied words", unmask_text(shown_snils, document), original_snils))
    rows.append(("SNILS tool copied words", json.loads(unmask_arguments(
        json.dumps({"snils": shown_snils}, ensure_ascii=False), document))["snils"], original_snils))
    changed_snils: str = "ноль ноль три ноль ноль четыре пять шесть семь восемь девять"
    wanted_snils: str = "один один два два три три четыре четыре пять девять пять"
    rows.append(("SNILS changed words answer", unmask_text(changed_snils, document), wanted_snils))
    rows.append(("SNILS changed words tool", json.loads(unmask_arguments(
        json.dumps({"snils": changed_snils}, ensure_ascii=False), document))["snils"], wanted_snils))
    zero_document: Vault = Vault(":memory:", "spoken-identifiers").for_conversation("zero-document")
    with patch("pseudex.vault._fake_snils", return_value="113-224-335 96"):
        mask_text("001-002-003 18", zero_document, [Span(0, 14, "SNILS", "001-002-003 18")])
    zero_written: str = "один один три два два четыре три три пять девять шесть"
    zero_wanted: str = "ноль ноль один ноль ноль два ноль ноль три один восемь"
    rows.append(("SNILS real leading zeros answer", unmask_text(zero_written, zero_document), zero_wanted))
    rows.append(("SNILS real leading zeros tool", json.loads(unmask_arguments(
        json.dumps({"snils": zero_written}, ensure_ascii=False), zero_document))["snils"], zero_wanted))
    # These inputs were never remembered verbatim: they exercise derived speech,
    # including a hesitation between unambiguous single-digit groups.
    for label, written, wanted in (
        ("national", "девять семь девять пять пять пять три три два два",
         "девять один шесть два один четыре восемь восемь ноль три"),
        ("hesitation", "восемь эээ девять семь девять пять пять пять три три два два",
         "восемь эээ девять один шесть два один четыре восемь восемь ноль три"),
    ):
        phone: Vault = Vault(":memory:", "spoken-identifiers").for_conversation(label)
        with patch("pseudex.vault._fake_phone", return_value="+79795553322"):
            mask_text("+79162148803", phone, detector.detect("+79162148803"))
        rows.append((label + " derived answer", unmask_text(written, phone), wanted))
        rows.append((label + " derived tool", json.loads(unmask_arguments(
            json.dumps({"phone": written}, ensure_ascii=False), phone))["phone"], wanted))
    # A WHOLE RUN THE SENDER DICTATED IN UNEVEN GROUPS, carrying the leased
    # typos «шеесят» and «триц», against a fake whose fourth group ends in
    # «двадцать» before a one-digit tail. «двести двадцать» and «два» read back
    # as ONE group of 222, so the tail cannot stand where the sender put it: the
    # boundary moves one digit left («двадцать два» + «ноль два»), which the
    # greedy parse cannot swallow. Before that rule the whole substitute fell
    # back to digits and the customer's own dictated words never came back.
    dictated: str = ("восемь девятьсот шеесят шестьсот двадцать два "
                     "шестьсот триц девять четыре")
    regrouped: str = ("восемь девятьсот шестьдесят семь шестьсот двенадцать "
                      "двадцать два ноль два")
    regroup_vault: Vault = Vault(":memory:", "spoken-identifiers").for_conversation("regroup")
    with patch("pseudex.vault._fake_phone", return_value="+79676122202"):
        shown_regroup: str = mask_text(dictated, regroup_vault, detector.detect(dictated))
    rows.append(("regrouped tail IN", shown_regroup, regrouped))
    rows.append(("regrouped tail answer", unmask_text(shown_regroup, regroup_vault), dictated))
    rows.append(("regrouped tail tool", json.loads(unmask_arguments(
        json.dumps({"phone": shown_regroup}, ensure_ascii=False), regroup_vault))["phone"], dictated))
    rows.extend(_family_rows(detector))
    rows.extend(_refusal_rows(detector))
    # C02: a malformed country-code sign is not a form the vault may splice
    # under. «+8…» and «++…» must come back unchanged (never a real/fake hybrid).
    malformed: Vault = Vault(":memory:", "spoken-identifiers").for_conversation("malformed")
    with patch("pseudex.vault._fake_phone", return_value="+79795553322"):
        mask_text("+79162148803", malformed, detector.detect("+79162148803"))
    for written in ("+89795553322", "++79795553322", "++7 979 555 33 22"):
        rows.append(("malformed tool " + written,
                     json.loads(unmask_arguments(
                         json.dumps({"phone": written}, ensure_ascii=False), malformed))["phone"],
                     written))
        rows.append(("malformed answer " + written, unmask_text(written, malformed), written))
    # C02 G4: spoken EMAIL and PLATE reconstruction (wired into detect_all but
    # never tested) must produce the written form a mail box / ГИБДД accepts.
    spoken_email = "ситникова собака мэйл точка ру"
    spoken_plate = "а двести шестьдесят три о ка регион шестьдесят шесть"
    rows.append(("spoken email -> written", spoken.email_from_words(spoken_email), "sitnikova@mail.ru"))
    rows.append(("spoken plate -> written", spoken.plate_from_words(spoken_plate), "А263ОК66"))
    rows.append(("spoken email detected", str(bool(spoken.detect_spoken_email(spoken_email))), "True"))
    rows.append(("spoken plate detected", str(bool(spoken.detect_spoken_plate(spoken_plate))), "True"))
    failed: list[tuple[str, str, str]] = [row for row in rows if row[1] != row[2]]
    for label, actual, expected in failed:
        print(f"FAIL {label}: {actual!r} != {expected!r}")
    print(f"spoken_identifier_form: {len(rows) - len(failed)}/{len(rows)}")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
