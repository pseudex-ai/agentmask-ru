"""Finite verbs do not prove that a following personal name is an object."""

import json
from unittest.mock import patch

import testkit
from pseudex import morph_names
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault


def main() -> int:
    testkit.load_dev_bundle()
    detector: Detector = Detector()
    examples: tuple[tuple[str, str, str], ...] = (
        ("посылку примет громова марина", "Смирнова Анна", "Громова Марина"),
        ("заказ проверит громова марина", "Смирнова Анна", "Громова Марина"),
        ("прими громову марину", "Смирнова Анна", "Громова Марина"),
        ("примите громову марину", "Смирнова Анна", "Громова Марина"),
        ("позвоните громовой марине", "Смирнова Анна", "Громова Марина"),
        ("менеджер позвонит громовой марине", "Смирнова Анна", "Громова Марина"),
        ("оператор пригласит громову марину", "Смирнова Анна", "Громова Марина"),
        ("система найдёт громову марину", "Смирнова Анна", "Громова Марина"),
        ("курьер примет громову марину", "Смирнова Анна", "Громова Марина"),
        ("передайте марину посылку", "Смирнов Антон", "Марин"),
        # A MASCULINE name in the accusative after a 3per verb with an explicit
        # subject must not be re-read as a feminine nominative: «система найдёт
        # Иванова Петра» is the man, not «Иванова Петра» the woman (E03 regression).
        ("система найдёт иванова петра", "Смирнов Антон", "Иванов Пётр"),
        # …and the subject need not be inanimate: animate subjects whose
        # accusative differs from the nominative («оператор», «менеджер») fill
        # the slot too, even though pymorphy also knows an inanimate homograph.
        ("оператор пригласит иванова петра", "Смирнов Антон", "Иванов Пётр"),
        ("менеджер пригласит иванова петра", "Смирнов Антон", "Иванов Пётр"),
        # …nor unambiguous: an inanimate noun whose accusative equals its
        # nominative («сервис», «приложение») is still the subject; the NAME's
        # own masculine reading decides the object, not the pre-verbal noun.
        ("сервис найдёт иванова петра", "Смирнов Антон", "Иванов Пётр"),
        ("приложение найдёт иванова петра", "Смирнов Антон", "Иванов Пётр"),
    )
    failures: list[str] = []
    for index, (text, fake, expected) in enumerate(examples):
        vault: Vault = Vault(":memory:", "name-subject").for_conversation(str(index))
        spans = [span for span in detector.detect(text) if span.entity_type == "NAME"]
        if len(spans) != 1:
            failures.append(f"span count {len(spans)} for {text!r}")
            continue
        with patch("pseudex.vault._fake_name", return_value=fake):
            mask_text(text, vault, spans)
        written: str = json.dumps({"name": fake}, ensure_ascii=False)
        restored = json.loads(unmask_arguments(written, vault))["name"]
        if restored != expected:
            failures.append(f"{text!r}: {restored!r} != {expected!r}")
    # Imperatives and infinitives fix the case by their stem alone; a third-
    # person finite verb needs the NAME to decide subject vs object.
    governors: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("прими ", "", ("accs",)), ("примите ", "", ("accs",)),
        ("найти ", "", ("accs",)), ("позвоните ", "", ("datv",)),
        ("посылку примет ", "громова марина", ("nomn", "accs")),
        ("заказ проверит ", "громова марина", ("nomn", "accs")),
        ("система найдёт ", "иванова петра", ("accs",)),
        ("оператор пригласит ", "иванова петра", ("accs",)),
        ("менеджер пригласит ", "иванова петра", ("accs",)),
        ("сервис найдёт ", "иванова петра", ("accs",)),
        ("приложение найдёт ", "иванова петра", ("accs",)),
    )
    for text, surface, expected_cases in governors:
        actual = morph_names.governing_cases(text + surface, len(text), surface)
        if actual != expected_cases:
            failures.append(f"governor {text!r}+{surface!r}: {actual} != {expected_cases}")
    # The surname's feminine nominative reading must not outweigh a known
    # masculine identity when the model changes the case of the whole name.
    rewritten: Vault = Vault(":memory:", "name-rewrite").for_conversation("one")
    original: str = "Клиент Никита Гущин"
    with patch("pseudex.vault._fake_name", return_value="Гордей Жуков"):
        mask_text(original, rewritten, detector.detect(original))
    forms: tuple[tuple[str, str], ...] = (
        ("Телефон Гордея Жукова", "Телефон Никиты Гущина"),
        ("Телефон Гордей Жуков", "Телефон Никита Гущин"),
    )
    for written, expected in forms:
        actual_text: str = unmask_text(written, rewritten)
        if actual_text != expected:
            failures.append(f"rewritten name {written!r}: {actual_text!r} != {expected!r}")
    for failure in failures:
        print("FAIL", failure)
    print(f"name_subject_form: {len(examples) + len(governors) + len(forms) - len(failures)}/"
          f"{len(examples) + len(governors) + len(forms)} checks passed")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
