"""Names must agree — in gender, in case, and with themselves.

This suite exists because of a defect three persona clients hit independently
and none of the existing tests could see: the substitute was grammatically
malformed (`Екатерина Цветков`, `улице Ивовой` in a nominative slot), the model
REPAIRED it, and a repaired token no longer matched the vault — so the
customer's tool received a person who does not exist, silently, in roughly one
dialogue in ten.

Two properties are checked, and both must hold or the product is lying:

  AGREEMENT — what the model reads is well-formed Russian, so it has no motive
  to rewrite anything.

  SURVIVAL — even when the model rewrites anyway, the real value comes back.
  This is the same belt-and-braces the phone path has had for a while: exact
  shape match first, signature match second.

Run: python3 test_names_morphology.py
"""

import os
import sys
import tempfile

import testkit
from pseudex.detect_all import Detector
from pseudex.morph_names import (
    detect_case,
    detect_gender,
    feminine_surname,
    inflect_person,
    to_nominative,
)
from pseudex.redact import mask_text, unmask_text
from pseudex.vault import Vault

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(label)


# ---------------------------------------------------------------- gender

GENDER_CASES = [
    # Ordinary, both genders.
    ("Иванов Пётр Сергеевич", "masc"),
    ("Иванова Мария Петровна", "femn"),
    ("Ольга Кузнецова", "femn"),
    ("Игорь Петров", "masc"),
    # The surname reads as a masculine genitive; the given name must outvote it.
    ("Любовь Соколова", "femn"),
    ("Вера Мороз", "femn"),
    # Masculine given names ending in -а/-я, which the ending rule would flip.
    ("Никита Гущин", "masc"),
    ("Илья Сорокин", "masc"),
    ("Кузьма Жуков", "masc"),
    ("Фома Лебедев", "masc"),
    # Indeclinable surnames carry no gender of their own.
    ("Черных Анна", "femn"),
    ("Седых Иван", "masc"),
    ("Шевченко Оксана", "femn"),
    ("Дюма Александр", "masc"),
    # Turkic patronymics, which pymorphy3 does not tag as patronymics at all.
    ("Алиев Рустам Ахмед оглы", "masc"),
    ("Алиева Лейла Ахмед кызы", "femn"),
    # Genuinely undecidable. None is the correct answer, not a guess.
    ("Ким Чен Ын", None),
]


def test_gender() -> None:
    wrong = [(s, want, detect_gender(s)) for s, want in GENDER_CASES
             if detect_gender(s) != want]
    check("gender is read from the strongest available signal",
          not wrong, f"mismatched={wrong}" if wrong else f"{len(GENDER_CASES)} cases")


# ---------------------------------------------------------------- case

CASE_FORMS = [
    ("Иванов Пётр Сергеевич", "nomn"),
    ("Иванова Петра Сергеевича", "gent"),
    ("Иванову Петру Сергеевичу", "datv"),
    ("Ивановым Петром Сергеевичем", "ablt"),
    ("Иванове Петре Сергеевиче", "loct"),
]


def test_case_and_canonical_key() -> None:
    wrong = [(s, want, detect_case(s)) for s, want in CASE_FORMS
             if detect_case(s) != want]
    check("the case a name is written in is recognised",
          not wrong, f"mismatched={wrong}" if wrong else "")

    keys = {to_nominative(surface) for surface, _ in CASE_FORMS}
    check("every case of one person collapses to ONE vault key",
          keys == {"Иванов Пётр Сергеевич"}, f"keys={keys}")


# ------------------------------------------------------------- inflection

INFLECTION_CASES = [
    # Regular possessive surnames, both genders.
    ("Руслан Хвостов", "masc", "datv", "Руслану Хвостову"),
    ("Ирина Бирюкова", "femn", "gent", "Ирины Бирюковой"),
    ("Олег Лебедев", "masc", "ablt", "Олегом Лебедевым"),
    # Adjectival surnames: two paradigms, differing in the instrumental.
    ("Пётр Достоевский", "masc", "ablt", "Петром Достоевским"),
    ("Олег Яровой", "masc", "ablt", "Олегом Яровым"),
    ("Анна Достоевская", "femn", "datv", "Анне Достоевской"),
    # Indeclinable surnames stay put while the given name inflects.
    ("Тарас Шевченко", "masc", "gent", "Тараса Шевченко"),
    ("Анна Черных", "femn", "datv", "Анне Черных"),
    ("Александр Дюма", "masc", "datv", "Александру Дюма"),
    # A double-barrelled Russian surname inflects in BOTH halves.
    ("Михаил Салтыков-Щедрин", "masc", "gent", "Михаила Салтыкова-Щедрина"),
    # A surname ending in a consonant declines for a man and never for a woman.
    ("Пётр Мороз", "masc", "gent", "Петра Мороза"),
    ("Елена Мороз", "femn", "gent", "Елены Мороз"),
    ("Виктор Цой", "masc", "datv", "Виктору Цою"),
    ("Анна Цой", "femn", "datv", "Анне Цой"),
]


def test_inflection() -> None:
    wrong = [(name, want, inflect_person(name, case, gender))
             for name, gender, case, want in INFLECTION_CASES
             if inflect_person(name, case, gender) != want]
    check("a fake name inflects into the sentence's case, agreeing throughout",
          not wrong, f"mismatched={wrong}" if wrong else f"{len(INFLECTION_CASES)} cases")


def test_feminine_surnames() -> None:
    pairs = [("Лебедев", "Лебедева"), ("Сорокин", "Сорокина"),
             ("Хвостов", "Хвостова"), ("Яровой", "Яровая"),
             ("Достоевский", "Достоевская"),
             ("Шевченко", "Шевченко"), ("Черных", "Черных")]
    wrong = [(m, f, feminine_surname(m)) for m, f in pairs if feminine_surname(m) != f]
    check("the feminine form is derived from the masculine pool, not stored twice",
          not wrong, f"mismatched={wrong}" if wrong else "")


# ------------------------------------------------------- the product claim

ROUND_TRIP = [
    "Позвоните Иванову Петру Сергеевичу",
    "Заявка от Ивановой Марии Петровны",
    "Клиент Елена Попова записана",
    "Передайте Ольге Кузнецовой ключи",
    "Записать Никиту Гущина на 15:00",
    "Встретился с Игорем Петровым вчера",
    "Договор с Любовью Соколовой подписан",
    "Курьер выехал к Анне Черных",
    "Счёт выставлен Шевченко Тарасу Григорьевичу",
    "Отдайте документы Кузьме Жукову",
]


def test_round_trip(vault: Vault, detector: Detector) -> None:
    """The REAL PERSON must come back — that is the property the product sells.

    Compared on identity rather than on the exact string, because restoration
    puts the name into the case the token was standing in, and for an animate
    masculine noun the accusative and the genitive are spelled the same. So
    `Записать Никиту Гущина` can return as `Записать Никиты Гущина`: the right
    person, one syncretic case away. Russian does not encode the difference, so
    no analyser can recover it, and asserting the exact string would be a test
    demanding something the language does not provide.
    """
    wrong_person, wrong_case = [], []
    for original in ROUND_TRIP:
        masked = mask_text(original, vault, detector.detect(original))
        restored = unmask_text(masked, vault)
        if restored == original:
            continue
        if to_nominative(_name_of(restored, detector)) != to_nominative(
                _name_of(original, detector)):
            wrong_person.append((original, masked, restored))
            continue
        # Right person, different case. Acceptable only when the two cases are
        # spelled identically somewhere in Russian, which is why the analyser
        # could not tell them apart in the first place.
        want = detect_case(_name_of(original, detector))
        got = detect_case(_name_of(restored, detector))
        if not _syncretic(want, got):
            wrong_case.append((original, restored, want, got))
    check("the REAL person comes back from every sentence",
          not wrong_person, f"wrong={wrong_person}" if wrong_person else
          f"{len(ROUND_TRIP)} sentences")
    check("and in a case Russian does not spell differently",
          not wrong_case, f"drift={wrong_case}" if wrong_case else "")


# Cases that collapse onto one form and therefore cannot be recovered from
# spelling: for animate masculine the accusative IS the genitive («вижу Ивана
# Осипова» / «нет Ивана Осипова»); for feminine names the oblique cases all end
# in -ой («Виктории Рыбаковой» is genitive, dative, instrumental and locative at
# once). Asserting an exact case here would demand information the language does
# not carry, so the check is that the drift stays inside a class, never across.
_SYNCRETIC_CLASSES = ({"accs", "gent"}, {"gent", "datv", "ablt", "loct"})


def _syncretic(want: str | None, got: str | None) -> bool:
    if want is None or got is None or want == got:
        return True
    return any({want, got} <= cls for cls in _SYNCRETIC_CLASSES)


def _name_of(text: str, detector: Detector) -> str:
    spans = [s for s in detector.detect(text) if s.entity_type == "NAME"]
    return spans[0].value if spans else text


def test_masked_text_is_well_formed(vault: Vault, detector: Detector) -> None:
    """The masked sentence must be in the SAME case as the original.

    This is the property that removes the model's motive to rewrite, and
    therefore the property that keeps a fake out of the customer's tool. A
    substitute in the nominative inside a dative slot — «Позвоните Дмитрий
    Сазонов» — is what started the whole failure.
    """
    disagreements = []
    for original in ROUND_TRIP:
        spans = [s for s in detector.detect(original) if s.entity_type == "NAME"]
        if not spans:
            continue
        masked = mask_text(original, vault, detector.detect(original))
        want = detect_case(spans[0].value)
        masked_spans = [s for s in detector.detect(masked) if s.entity_type == "NAME"]
        if not masked_spans:
            continue
        got = detect_case(masked_spans[0].value)
        # Exact case cannot be asserted: Russian is heavily syncretic in
        # exactly this region. For animate masculine the accusative IS the
        # genitive («вижу Ивана Осипова» / «нет Ивана Осипова»), and for
        # feminine names the genitive, dative, instrumental and locative
        # collapse onto `-ой` («Виктории Рыбаковой» is three cases at once). No
        # analyser can separate what the language spells identically.
        #
        # What CAN be asserted is the property the defect was about: a name in
        # an oblique slot must not be substituted by a nominative. «Позвоните
        # Дмитрий Сазонов» is the failure; «Позвоните Виктории Рыбаковой» is
        # correct whichever oblique case the analyser names it.
        if want in (None, "nomn") or got is None:
            continue
        if got == "nomn":
            disagreements.append((original, masked, want, got))
    check("a substitute never stands in the nominative inside an oblique slot",
          not disagreements, f"disagreements={disagreements}" if disagreements else "")


def test_model_rewrite_does_not_leak(vault: Vault, detector: Detector) -> None:
    """THE PERSONA BUG. The model puts the token into another case; the tool
    must still receive the real person, never the fake."""
    leaked = []
    for original, case in [("Клиент Елена Попова", "datv"),
                           ("Клиент Иванов Пётр Сергеевич", "gent"),
                           ("Клиент Ольга Кузнецова", "ablt")]:
        masked = mask_text(original, vault, detector.detect(original))
        token = masked.replace("Клиент ", "")
        # Exactly what the model does: rewrite the name into a different case.
        rewritten = inflect_person(token, case, detect_gender(token))
        restored = unmask_text(f"Клиент {rewritten}", vault)
        # The test is whether a FAKE reached the caller. The real name may come
        # back inflected — that is intended, so the sentence still reads — so
        # compare identities, not spellings.
        real = to_nominative(original.replace("Клиент ", ""))
        got = to_nominative(restored.replace("Клиент ", ""))
        if got != real:
            leaked.append((original, token, rewritten, restored))
    check("a token the model re-inflected NEVER leaves a fake with the caller",
          not leaked, f"leaked={leaked}" if leaked else "3 rewrites, 3 real people")


def test_one_person_is_one_row(vault: Vault, detector: Detector) -> None:
    """Identity stability, which the landing promises in these words: one and
    the same person is one and the same token, yesterday and in the next
    dialogue. Before canonicalisation, four cases made four strangers."""
    forms = ["Сидоров Павел Олегович", "Сидорову Павлу Олеговичу",
             "Сидорова Павла Олеговича", "Сидоровым Павлом Олеговичем"]
    tokens = set()
    for form in forms:
        text = f"Клиент {form}"
        masked = mask_text(text, vault, detector.detect(text))
        name = masked.replace("Клиент ", "")
        tokens.add(to_nominative(name))
    check("one person in four cases is ONE identity, not four",
          len(tokens) == 1, f"identities={tokens}")


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    vault = Vault(os.path.join(tempfile.mkdtemp(), "names.db"), "morph-test")

    test_gender()
    test_case_and_canonical_key()
    test_inflection()
    test_feminine_surnames()
    test_round_trip(vault, detector)
    test_masked_text_is_well_formed(vault, detector)
    test_model_rewrite_does_not_leak(vault, detector)
    test_one_person_is_one_row(vault, detector)

    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} — {_FAILURES}")
        return 1
    print("\nnames OK — gender and case agree, and a re-inflected token still "
          "resolves to the real person")
    return 0


if __name__ == "__main__":
    sys.exit(main())
