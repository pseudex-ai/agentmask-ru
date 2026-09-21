"""The person judge: one name up to inflection and word order, never two people.

Every pair below is a verdict the string judge got wrong on a real run —
or a pair the lemma judge must NOT be fooled by.
"""

from agentmask_ru.person import looks_like_person, same_person


def test_the_customer_in_the_accusative_is_the_tool_s_nominative() -> None:
    # «это рушан есин … пиши на есина рушана»: the tool got the person in
    # the nominative; a string judge read «есина» as a feminine surname.
    assert same_person("есина рушана", "Рушан Есин")


def test_one_substitute_in_two_cases_is_one_substitute() -> None:
    assert same_person("Харитон Рыбаков", "Харитона Рыбакова")
    assert same_person("Котову Надежду", "Надежда Котова")
    assert same_person("Бирюковой Еве", "Ева Бирюкова")


def test_a_different_person_shares_no_lemma() -> None:
    assert not same_person("Харитон Рыбаков", "Игнатий Калинець")
    assert not same_person("Юдину Беллу", "Беклемишева Ильназа")
    assert not same_person("Иван Петров", "Иван Сидоров")


def test_a_fringe_parse_does_not_glue_two_people() -> None:
    # «Иванов» is also the genitive plural of «Иван» at a score of 0.009,
    # «Петров» of «Пётр» at 0.053; with those readings admitted these two
    # became one person.
    assert not same_person("Иван Петров", "Пётр Иванов")


def test_half_a_name_is_not_the_name() -> None:
    assert not same_person("Иван Петров", "Иван")


def test_only_a_name_shape_is_judged_here() -> None:
    assert looks_like_person("Рушан Есин")
    assert looks_like_person("тэдди ермилин")
    assert not looks_like_person("<PERSON_1>")
    assert not looks_like_person("улица Ленина 5")
    assert not looks_like_person("Ivan Petrov")
