"""Форма, в которой АГЕНТ написал подмену, наложенная на настоящее значение.

СОДЕРЖИМОЕ ПРИНАДЛЕЖИТ ВОЛТУ, ФОРМА — АГЕНТУ. Обещание продукта — не влиять на
работу агента никак, и регистр букв это ровно то, на что мы влияли: волт хранит
имя канонически, то есть строчными, а `_pick_value` отдавал канон в аргумент
инструмента. Контроль писал в CRM «Ким Виктор», плечо шлюза — «ким виктор»: 262
расхождения полей на живом прогоне 07.09, задето 217 троек из 834 — самый
крупный единичный класс во всём прогоне.

ЭТО НЕ ТО ЖЕ САМОЕ, ЧТО ПАДЕЖ, и разница измерена. Согласовать значение с
падежом подмены нельзя: «ленина пятьдесят» приходило из инструмента как «ленина
пятидесяти» — номер дома в родительном, которого не найдёт ни одна CRM. Регистр
такой цены не несёт: он ничего не меняет в том, ЧТО написано, только в том, как
оно выглядит, и ни один справочник не ищет с учётом регистра.

НИ ОДИН НАШ ПИСЬМЕННЫЙ КОРПУС ЭТОГО НЕ ВИДИТ. Скриптовый агент копирует подмену
дословно, поэтому подмена и настоящее значение приходят в одном регистре и
расхождения не возникает вовсе; класс живёт только там, где модель ПРИБИРАЕТ за
клиентом — а клиент диктует голосом и строчными.
"""
import re

_HYPHEN = re.compile(r"-")


def cased_like(value: str, model: str) -> str:
    """`value` в том регистре, которым АГЕНТ написал стоявшую здесь подмену.

    Пословно и позиционно: слово настоящего значения берёт регистр слова
    подмены на том же месте. Когда слов у нас больше, лишние берут регистр
    ПОСЛЕДНЕГО слова модели — «Иван» и «Пётр» в «Иванов Пётр Сергеевич»
    пишутся одинаково, и продолжать ряд честнее, чем оборвать его на середине.
    """
    ours = value.split()
    theirs = model.split()
    if not ours or not theirs:
        return value
    out = [_cased_word(word, theirs[min(i, len(theirs) - 1)]) for i, word in enumerate(ours)]
    return " ".join(out)


def case_class(text: str) -> str:
    """The letter-case class of a whole name: «lower» («игорь анфалов»),
    «upper» («ИГОРЬ АНФАЛОВ»), otherwise «title» — which includes a name with
    a lower-case particle («Алиев Рустам Ахмед оглы»). A NAME is cased as a
    whole, not word by word: mirroring «оглы» onto the fake's patronymic
    produced «Гущин Юрий Валентин андреевич», a run the capitalised-word
    windows could not read back, and the fake patronymic reached the prose."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "title"
    if all(ch.islower() for ch in letters):
        return "lower"
    if len(letters) > 1 and all(ch.isupper() for ch in letters):
        return "upper"
    return "title"


def name_cased_like(value: str, model: str) -> str:
    """`value` in the letter-case CLASS of `model`. The same class keeps
    `value` exactly as it is — a customer's «Алиев Рустам Ахмед оглы» keeps
    its particle when the agent kept Title case; a different class is
    applied whole: lower, upper, or every word capitalised. So an agent that
    did not change the class gets the customer's own spelling back, and one
    that did gets its own."""
    kind = case_class(model)
    if kind == case_class(value):
        return value
    if kind == "lower":
        return value.lower()
    if kind == "upper":
        return value.upper()
    return " ".join("-".join(part[:1].upper() + part[1:] for part in _HYPHEN.split(word))
                    for word in value.split())


def _cased_word(word: str, model: str) -> str:
    """Одно слово в регистре одного слова модели.

    ЗАГЛАВНЫЕ ТРЕБУЮТ ДВУХ БУКВ. Односимвольное «Д» в «Д. 5» — это маркер, а не
    капс, и по нему нельзя решать, что агент кричит.
    """
    letters = [ch for ch in model if ch.isalpha()]
    if not letters or not word:
        return word
    if len(letters) > 1 and all(ch.isupper() for ch in letters):
        return word.upper()
    if letters[0].isupper():
        # Дефис склеивает один токен, и обе его половины — имена собственные:
        # «Санкт-Петербург», «Жан-Клод», «Миклухо-Маклая».
        return "-".join(part[:1].upper() + part[1:] for part in _HYPHEN.split(word))
    if all(ch.islower() for ch in letters):
        return word.lower()
    return word


def main() -> int:
    failures = 0
    for value, model, want in (
        ("ким виктор", "Рыбаков Родион", "Ким Виктор"),
        ("ким виктор", "РЫБАКОВ РОДИОН", "КИМ ВИКТОР"),
        ("Ким Виктор", "рыбаков родион", "ким виктор"),
        ("павлова тамара владимировна", "Рыбаков Родион", "Павлова Тамара Владимировна"),
        ("санкт-петербург", "Краснодар", "Санкт-Петербург"),
        ("солнечная", "Ольховая", "Солнечная"),
        ("солнечная", "ольховая", "солнечная"),
        # Один инициал — маркер, а не капс: «Д.» не делает «СОЛНЕЧНАЯ».
        ("солнечная", "Д", "Солнечная"),
        ("", "Ольховая", ""),
        ("солнечная", "", "солнечная"),
    ):
        got = cased_like(value, model)
        if got != want:
            failures += 1
            print(f"FAIL cased_like({value!r}, {model!r}) = {got!r}, wanted {want!r}")
    for value, model, want in (
        ("Гущин Юрий Валентин Андреевич", "Алиев Рустам Ахмед оглы", "Гущин Юрий Валентин Андреевич"),
        ("Гущин Юрий", "игорь анфалов", "гущин юрий"),
        ("Гущин Юрий", "ИГОРЬ АНФАЛОВ", "ГУЩИН ЮРИЙ"),
        ("Алиев Рустам Ахмед оглы", "Гущин Юрий Валентин Андреевич", "Алиев Рустам Ахмед оглы"),
        ("Алиев Рустам Ахмед оглы", "гущин юрий валентин андреевич", "алиев рустам ахмед оглы"),
        ("игорь анфалов", "Георгий Рыбаков", "Игорь Анфалов"),
        ("игорь анфалов", "георгий рыбаков", "игорь анфалов"),
        ("санкт-петербургский иван", "Георгий Рыбаков", "Санкт-Петербургский Иван"),
    ):
        got = name_cased_like(value, model)
        if got != want:
            failures += 1
            print(f"FAIL name_cased_like({value!r}, {model!r}) = {got!r}, wanted {want!r}")
    print("agent_form: PASS" if not failures else f"agent_form: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
