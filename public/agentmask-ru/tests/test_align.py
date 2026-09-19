"""The alignment's failure modes, each one a case that scored wrongly once.

Everything the benchmark publishes rests on `project`: it decides whether a
value was hidden, whether it was hidden completely, and what the scripted
model copies into the tool call. These are the shapes that broke it.
"""

from agentmask_ru.align import project, rewrite_ratio


def test_a_placeholder_hides_the_value() -> None:
    sub = project("тел 89071234567 заказ 123", "тел <PHONE_1> заказ 123", 4, 15)
    assert sub.text == "<PHONE_1>"
    assert sub.altered and sub.covered


def test_a_digit_inside_the_placeholder_does_not_split_the_span() -> None:
    # «1» appears in both «89071234567» and «<PHONE_1>»; a raw opcode list
    # matches it and reports three blocks, which used to leave the
    # substitute as a fragment.
    sub = project("номер 89071234561", "номер <PHONE_1>", 6, 17)
    assert sub.text == "<PHONE_1>"


def test_an_untouched_value_is_not_altered() -> None:
    sub = project("тел 89071234567", "тел 89071234567", 4, 15)
    assert not sub.altered and not sub.covered


def test_reformatting_digits_protects_nothing() -> None:
    # A masker that strips the separators has not hidden the phone: the
    # model reads the same eleven digits.
    sub = project("тел 8 907 123 45 67", "тел 89071234567", 4, 19)
    assert not sub.altered


def test_folding_yo_protects_nothing() -> None:
    sub = project("зовут Ёлкина Анна", "зовут Елкина Анна", 6, 17)
    assert not sub.altered


def test_a_partly_masked_name_is_a_leak_the_leak_line_cannot_see() -> None:
    # «Кузнецов Дмитрий» masked as «Кузнецов <NAME_1>»: altered, so the leak
    # line counts it as protected — and the surname went to the model in the
    # clear, which is what the coverage line exists to say.
    sub = project("клиент Кузнецов Дмитрий звонил", "клиент Кузнецов <NAME_1> звонил", 7, 23)
    assert sub.altered
    assert not sub.covered


def test_two_values_merged_into_one_placeholder_both_count_as_altered() -> None:
    original = "иван петров и мария сидорова"
    masked = "<PERSON_1>"
    first = project(original, masked, 0, 11)
    second = project(original, masked, 14, 28)
    assert first.altered and second.altered


def test_a_deleted_value_is_altered_and_covered() -> None:
    sub = project("тел 89071234567 ок", "тел  ок", 4, 15)
    assert sub.text == ""
    assert sub.altered and sub.covered


def test_rewrite_ratio_sees_changes_outside_the_spans() -> None:
    inside_only = rewrite_ratio("тел 89071234567 заказ 123", "тел <PHONE_1> заказ 123", [(4, 15)])
    everything = rewrite_ratio("тел 89071234567 заказ 123", "ТЕЛЕФОН СКРЫТ, ЗАКАЗ СКРЫТ", [(4, 15)])
    assert inside_only == 0.0
    assert everything > 0.3


def test_coverage_is_about_pieces_not_characters() -> None:
    # A format-preserving substitute shares the plus, the seven and the
    # dashes with the real phone. Counting characters called that a partial
    # leak and marked every realistic fake as uncovered.
    from agentmask_ru.align import surviving_pieces

    assert surviving_pieces("+7 907 123-45-67", "+7 935 476-22-11") == []
    assert surviving_pieces("Кузнецов Дмитрий", "Кузнецов Валентин") == ["кузнецов"]
    fpe = project("тел +7 907 123-45-67 ок", "тел +7 935 476-22-11 ок", 4, 20)
    assert fpe.altered and fpe.covered
