"""NAME case: is the WRITTEN form nominative, or is the OBSERVER gender-blind?

`test_names_morphology.py::test_masked_text_is_well_formed` reported

    FAIL  a substitute never stands in the nominative inside an oblique slot
    disagreements=[('Записать Никиту Гущина на 15:00',
                    'Записать Гордея Жукова на 15:00', 'accs', 'nomn')]

This file answers the question that failure raises and nothing else. It is a
regression set for the OBSERVER, not an engine fix: the masked sentence
«Записать Гордея Жукова на 15:00» is correct animate-accusative Russian, and
the verdict `nomn` comes from the check re-reading the substitute with the
gender-blind `morph_names.detect_case` while the mask leg wrote it through the
gender-and-case-aware `read_person` (`redact.py`, `_person_in_case_of` and the
NAME branch above it).

Why the two disagree, in one line: `detect_case` SUMS pymorphy scores over the
parts with no gender constraint, and the feminine NOMINATIVE reading of the
surname `-ова/-ева/-ина` (0.70) outweighs the masculine genitive (0.20) and
accusative (0.10) readings of the very same spelling, while the masculine given
name's accusative is syncretic with its own genitive and carries no nominative
reading to outvote it. `read_person` intersects the parts' readings and is told
the case the sentence governs, so it returns `('masc', 'accs')`.

The written form is the only one Russian offers for that person, and this file
proves it with LITERAL expectations written by hand, not derived from the
engine: the forced substitute, the masked sentence and the restored sentence are
all spelled out below. Randomness is frozen only where an exact output is
asserted (`unittest.mock.patch` on `pseudex.vault._fake_name`, the same pivot
`test_phone_hop_form.py` uses); the morphology controls need no freezing.

The controls cover the other given-name and surname ambiguities, so a future
change cannot pass here by weakening the check:

  * `Ивана Кузнецова` — the SAME surname spelling read as a masculine genitive,
    correct blind, because the given name's genitive score outvotes the
    feminine nominative;
  * `Ольга Кузнецова` / `Ольгу Кузнецову` — the feminine nominative and
    accusative of that spelling;
  * `Евгения Тарасова` — a spelling that IS a feminine nominative person and a
    masculine accusative person at once: no gender-blind reader can separate
    them, and the sentence's governed case is the only evidence there is;
  * `Анне Черных` — an indeclinable surname, where the blind reader is right;
  * `Иванову Петру Сергеевичу` — three-part agreement, where the blind reader
    is right;
  * `Гордей Жуков` placed in an accusative slot — a REAL nominative, which both
    readers must still flag. Without this one the check would be vacuous.

Run from `prototype/`:

    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python \
        test_name_case_regression.py
"""

from unittest.mock import patch

import testkit
from pseudex import vault as _vault
from pseudex.detect_all import Detector
from pseudex.morph_names import (
    detect_case,
    detect_gender,
    feminine_surname,
    inflect_person,
    read_person,
    survives_round_trip,
)
from pseudex.redact import mask_text, unmask_text
from pseudex.vault import Vault

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(label)


def _name_span(detector: Detector, text: str):
    spans = [s for s in detector.detect(text) if s.entity_type == "NAME"]
    return spans[0] if spans else None


# ---------------------------------------------------------------------------
# 1. The observer's own limit: gender-blind `detect_case` vs the joint reader.
# ---------------------------------------------------------------------------

# (surface, gender-blind verdict, the case the sentence governs, joint reading)
# Every expectation is a literal. The four `nomn` rows are the misread class
# that made the sibling suite flake (Б21): a masculine accusative whose given
# name has no nominative-contesting score and whose surname is spelled like a
# feminine nominative.
OBSERVER_CASES = [
    # The reported one.
    ("Гордея Жукова", "nomn", "accs", ("masc", "accs")),
    # Same class, four more pool draws the engine really mints.
    ("Льва Наумова", "nomn", "accs", ("masc", "accs")),
    ("Вячеслава Жукова", "nomn", "accs", ("masc", "accs")),
    ("Артёма Жукова", "nomn", "accs", ("masc", "accs")),
    # A spelling that is a feminine nominative AND a masculine accusative:
    # gender-blind reading cannot be right for both, the governed case decides.
    ("Евгения Тарасова", "nomn", "accs", ("masc", "accs")),
    # The blind reader is RIGHT here, because the given name carries the case.
    ("Никиту Гущина", "accs", "accs", ("masc", "accs")),
    ("Ивана Кузнецова", "gent", "gent", ("masc", "gent")),
    ("Ольгу Кузнецову", "accs", "accs", ("femn", "accs")),
    ("Анне Черных", "datv", "datv", ("femn", "datv")),
    ("Иванову Петру Сергеевичу", "datv", "datv", ("masc", "datv")),
    ("Иван Кузнецов", "nomn", "nomn", ("masc", "nomn")),
]

# The mirror-image controls: a REAL nominative (or a feminine person) that a
# weakened observer must still not call oblique.
NOMINATIVE_CASES = [
    ("Гордей Жуков", "nomn"),
    ("Никита Гущин", "nomn"),
    ("Вера Мещерякова", "nomn"),
    ("Ольга Кузнецова", "nomn"),
]


def test_observer_is_gender_blind() -> None:
    # The verdicts that made the sibling suite flake, as literals.
    for surface, blind, governed, joint in OBSERVER_CASES:
        check(f"blind detect_case({surface!r}) == {blind}",
              detect_case(surface) == blind, f"got {detect_case(surface)!r}")
        check(f"joint read_person({surface!r}, ({governed!r},)) == {joint}",
              read_person(surface, (governed,)) == joint,
              f"got {read_person(surface, (governed,))!r}")
        # The genders the two readers answer with ARE different where it
        # matters: `Гордея Жукова` is read masculine by the joint reader and
        # tallied as a feminine nominative by the blind one.
        if blind == "nomn" and joint[1] != "nomn":
            check(f"detect_case({surface!r}, 'masc') is oblique",
                  detect_case(surface, "masc") in ("gent", "accs"),
                  f"got {detect_case(surface, 'masc')!r}")

    for surface, want in NOMINATIVE_CASES:
        check(f"a real nominative stays nominative: {surface!r}",
              detect_case(surface) == want, f"got {detect_case(surface)!r}")

    # NON-VACUOUS: a genuine nominative placed in an accusative slot is still
    # flagged by the joint reader — the replacement observer catches the defect
    # the sibling suite was written for.
    for nominative in ("Гордей Жуков", "Никита Гущин"):
        check(f"a nominative in an oblique slot is still caught: {nominative!r}",
              read_person(nominative, ("accs",)) == ("masc", "nomn"),
              f"got {read_person(nominative, ('accs',))!r}")


# ---------------------------------------------------------------------------
# 2. The product path: public mask/unmask with literal expected strings.
# ---------------------------------------------------------------------------

# (sentence, forced substitute, masked sentence, restored sentence,
#  the case the sentence governs)
FORCED = [
    # The reported failure. The substitute is minted nominative «Гордей Жуков»
    # and written accusative — the only form Russian offers for this person.
    ("Записать Никиту Гущина на 15:00", "Гордей Жуков",
     "Записать Гордея Жукова на 15:00", "Записать Никиту Гущина на 15:00", "accs"),
    # The rest of the pool-draw class, same sentence.
    ("Записать Никиту Гущина на 15:00", "Лев Наумов",
     "Записать Льва Наумова на 15:00", "Записать Никиту Гущина на 15:00", "accs"),
    ("Записать Никиту Гущина на 15:00", "Евгений Тарасов",
     "Записать Евгения Тарасова на 15:00", "Записать Никиту Гущина на 15:00", "accs"),
    # A feminine nominative must stay a nominative.
    ("Клиент Ольга Кузнецова", "Вера Жукова",
     "Клиент Вера Жукова", "Клиент Ольга Кузнецова", "nomn"),
    # A masculine nominative must stay a nominative.
    ("Клиент Иван Кузнецов", "Гордей Жуков",
     "Клиент Гордей Жуков", "Клиент Иван Кузнецов", "nomn"),
    # Feminine dative; the feminine surname is the derived form the engine
    # actually mints («Жуков» → «Жукова»), not the masculine entry.
    ("Передайте Ольге Кузнецовой ключи", "Вера Жукова",
     "Передайте Вере Жуковой ключи", "Передайте Ольге Кузнецовой ключи", "datv"),
    # Masculine instrumental, two parts agreeing.
    ("Встретился с Игорем Петровым вчера", "Гордей Жуков",
     "Встретился с Гордеем Жуковым вчера", "Встретился с Игорем Петровым вчера", "ablt"),
]


def test_written_form_is_oblique_and_round_trips(detector: Detector) -> None:
    for sentence, fake, masked_want, restored_want, governed in FORCED:
        vault = Vault(":memory:", "name-case-regression")
        with patch("pseudex.vault._fake_name", return_value=fake):
            masked = mask_text(sentence, vault, detector.detect(sentence))
        restored = unmask_text(masked, vault)
        check(f"mask({sentence!r}) == {masked_want!r}", masked == masked_want, f"got {masked!r}")
        check(f"unmask round trip of {sentence!r}", restored == restored_want, f"got {restored!r}")

        span = _name_span(detector, masked)
        if span is None:
            check(f"the substitute is detected again: {masked!r}", False, "no NAME span")
            continue
        check(f"the sentence governs {governed!r} for {masked!r}",
              governed in span.cases, f"span cases={span.cases!r}")
        # The gender may come back None — `detect_gender` declines on some
        # oblique pairs — but the CASE is the whole question here, and the
        # reader may never name it the nominative.
        joint = read_person(span.value, span.cases)
        check(f"the joint reader agrees: {span.value!r}",
              joint[1] == governed and joint[0] in (detect_gender(fake), None),
              f"got {joint!r}")
        if governed != "nomn":
            # The claim under test, stated without trusting either reader:
            # the written form is exactly what the engine's own inflector
            # produces for the governed case, and it is NOT the minted
            # nominative.
            check(f"the written form is the {governed} of the substitute: {span.value!r}",
                  span.value == inflect_person(fake, governed, detect_gender(fake)),
                  f"inflect={inflect_person(fake, governed, detect_gender(fake))!r}")
            check(f"the written form is not the minted nominative: {span.value!r}",
                  span.value != fake, f"both are {fake!r}")


# ---------------------------------------------------------------------------
# 3. The forced draws are real pool members, not fixtures.
# ---------------------------------------------------------------------------


def test_forced_substitutes_are_mintable() -> None:
    gender_pool = _vault._first_names_by_gender(_vault.ASSETS.version)
    surnames = _vault.ASSETS.get().fakes.last
    for sentence, fake, *_ in FORCED:
        given, surname = fake.split()
        gender = "femn" if given in gender_pool["femn"] else "masc"
        reachable_given = given in gender_pool[gender]
        # A feminine substitute is derived from the masculine pool, never a
        # second list; a masculine one is drawn as it stands.
        reachable_surname = surname in surnames or feminine_surname(surname) in surnames \
            or any(feminine_surname(s) == surname for s in surnames)
        check(f"the engine can really mint {fake!r}",
              reachable_given and reachable_surname,
              f"given={reachable_given} surname={reachable_surname}")
        check(f"{fake!r} passes the engine's own inflection gate",
              survives_round_trip(fake, gender),
              f"survives_round_trip({fake!r}, {gender!r})="
              f"{survives_round_trip(fake, gender)}")


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()

    test_observer_is_gender_blind()
    test_written_form_is_oblique_and_round_trips(detector)
    test_forced_substitutes_are_mintable()

    if _FAILURES:
        print(f"\nFAILED: {len(_FAILURES)} — {_FAILURES}")
        return 1
    print("\nname case regression OK — the substitute is written in the sentence's "
          "case, and the gender-blind observer is the side that was wrong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
