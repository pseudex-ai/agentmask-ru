"""Identifiers DICTATED ALOUD — a phone, a card, a СНИЛС with no digit in sight.

WHY THIS FILE EXISTS. Every recognizer in the engine waits for `\\d`, and a
transcript of speech has none: a person says «восемь девятьсот шестнадцать
шестьсот сорок два восемьдесят пять пятьдесят». Measured on AgentPII-RU v3,
which is built from real transcripts: 281 identifiers dictated aloud, and the
engine found NONE of them. On the v2 corpus the same probe found 133 spoken
phones and zero hits.

That is a leak, not an inconvenience. A phone number is the identifier a courier
calls, and it reached the model in the clear every time somebody spoke it.

THE SAFETY IS BORROWED, NOT INVENTED. This module only turns words into a digit
string; whether that digit string is an identifier is decided by the SAME
validators the digit path uses — Luhn for a card, mod 101 for a СНИЛС, the
weight vectors for an ИНН, libphonenumber for a phone. Nothing here is a new
rule about what counts as personal data, and that is deliberate: the checksum is
what makes a run of ordinary Russian words safe to claim.

Measured false-positive rate of the run scanner alone, before any checksum:
one hit in 9300 utterances of real speech and zero in 2691 sentences of news
prose. The single speech hit is «девять одиннадцать триста четырнадцать
пятьдесят пятнадцать» — a person genuinely dictating digits, from the
military-registration prank calls that fill the OpenSTT corpus.

WHAT COMES BACK IS WHAT WAS SAID. The span covers the WORDS, and detokenisation
returns them verbatim. The engine does not normalise speech into digits on the
customer's behalf: the benchmark's own expected tool call carries the spoken
form, because that is what the operator typed into the CRM.
"""

import re

from pseudex.assets import ASSETS
from pseudex.detect import Span
from pseudex.ru_pii import validate_inn, validate_luhn, validate_snils

# The numeral vocabulary, split by the grammar rather than listed flat, because
# the grammar is what makes the parse unambiguous. «сто девятнадцать» is 119 and
# not 100 followed by 19, and a flat list cannot say so.
_UNITS: dict[str, int] = {
    "ноль": 0, "нуль": 0, "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
    "девять": 9,
}
_TEENS: dict[str, int] = {
    "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19,
}
_TENS: dict[str, int] = {
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
}
_HUNDREDS: dict[str, int] = {
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500,
    "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}

# TRANSCRIPTS MISSPELL NUMERALS, and refusing the misspelling refuses the whole
# identifier: one bad word in a run of eleven kills every digit after it. The
# table is LEASED (`assets.spoken.numeral_typos`) because which broken forms a
# transcriber produces is something we mined out of somebody else's corpora —
# the PARSE below is published grammar and stays in the engine.
#
# FUZZY MATCHING IS FORBIDDEN HERE AND IT WAS MEASURED. Across 58 983 distinct
# words of prose and speech, 99 ordinary words sit within ONE edit of a numeral,
# among them «есть» (1947 occurrences) beside «шесть», «опять» beside «пять»,
# «ночь» beside «ноль». Distance-1 would not merely admit noise — it would
# CORRUPT the digits inside a real number, and a wrong digit string is worse
# than a missing one: it can pass a checksum and mask the wrong thing.
_ALL_NUMERALS = set(_UNITS) | set(_TEENS) | set(_TENS) | set(_HUNDREDS)
# Публичное имя того же множества: `run_to_digits` ждёт прогон, УЖЕ признанный
# числительным, и на чужом слове падает по ключу. Вызывающий обязан проверить
# состав, и проверять его должно то же множество, по которому идёт разбор.
CARDINALS = frozenset(_ALL_NUMERALS)

_UNIT_WORDS = "|".join(sorted(_UNITS, key=len, reverse=True))
_TEEN_WORDS = "|".join(sorted(_TEENS, key=len, reverse=True))
_TEN_WORDS = "|".join(sorted(set(_TENS) | set(_TEENS), key=len, reverse=True))
_HUNDRED_WORDS = "|".join(sorted(set(_HUNDREDS) | set(_TENS) | set(_TEENS) | set(_UNITS),
                                 key=len, reverse=True))


# A word that may stand INSIDE a dictated run without ending it. People say
# «ноль ноль» and pause with «эээ», and a transcript keeps both.
_FILLER = frozenset({"эээ", "ээ", "ммм", "мм", "аа", "ааа", "нуу", "ну", "вот"})

_WORD_RE = re.compile(r"[а-яё]+", re.IGNORECASE)


def _canonical(word: str) -> str | None:
    low = word.lower().replace("ё", "е")
    for table in (_UNITS, _TEENS, _TENS, _HUNDREDS):
        for key in table:
            if key.replace("ё", "е") == low:
                return key
    fixed = ASSETS.get().spoken.numeral_typos.get(low)
    return fixed if fixed else None


def _group(words: list[str], index: int) -> tuple[int, int]:
    """One numeral group, greedy left to right.

    Russian builds a number as hundreds + (teen | tens + unit | unit), and the
    group ends the moment the next word cannot continue it. That is what makes
    «восемь девятьсот шестнадцать» parse as 8 then 916 rather than as one
    number: «девятьсот» opens a new hundreds group, and «восемь» before it was
    already closed.
    """
    # НОЛЬ НИКОГДА НЕ ПРОДОЛЖАЕТ ГРУППУ, И ЭТО НЕ ТОНКОСТЬ. По-русски «двадцать
    # ноль» не значит двадцать — так диктуют две цифры подряд. А сложение через
    # `_UNITS` съедало слово целиком, потому что прибавляло к группе ноль:
    # «карта двести двадцать ноль семьдесят…» превращалась в 220|70|…, и в
    # инструмент уезжала карта из ПЯТНАДЦАТИ цифр вместо шестнадцати. Такая
    # карта не проходит Луна, и клиент видит отказ платежа без объяснения.
    #
    # Проверяется здесь, в начале группы, а не в двух ветках ниже: ноль
    # самостоятелен всегда — и после десятков, и после сотен, и сам по себе.
    word = words[index]
    if _UNITS.get(word) == 0:
        return 0, index + 1
    if word in _HUNDREDS:
        total = _HUNDREDS[word]
        index += 1
        if index < len(words) and words[index] in _TEENS:
            return total + _TEENS[words[index]], index + 1
        if index < len(words) and words[index] in _TENS:
            total += _TENS[words[index]]
            index += 1
            if (index < len(words) and words[index] in _UNITS
                and _UNITS[words[index]] != 0):
                total += _UNITS[words[index]]
                index += 1
            return total, index
        if (index < len(words) and words[index] in _UNITS
                and _UNITS[words[index]] != 0):
            return total + _UNITS[words[index]], index + 1
        return total, index
    if word in _TEENS:
        return _TEENS[word], index + 1
    if word in _TENS:
        total = _TENS[word]
        index += 1
        if (index < len(words) and words[index] in _UNITS
                and _UNITS[words[index]] != 0):
            total += _UNITS[words[index]]
            index += 1
        return total, index
    return _UNITS[word], index + 1


def run_to_digits(words: list[str]) -> str:
    """Concatenate a run of numeral groups into the digit string that was said.

    Concatenation, not addition: «восемь девятьсот шестнадцать» is the start of
    a phone number, not the sum 924. What a person dictating an identifier
    produces is a sequence of groups, and each group contributes its own digits
    in order.
    """
    out: list[str] = []
    index = 0
    while index < len(words):
        value, index = _group(words, index)
        out.append(str(value))
    return "".join(out)


def numeral_runs(text: str) -> list[tuple[int, int, list[str]]]:
    """Maximal runs of numeral words, with the offsets they occupy in `text`.

    A run is broken by any word that is neither a numeral nor a filler. Fillers
    are carried through but never start or end a run: «восемь эээ девятьсот» is
    one number said with a hesitation, and «эээ» on its own is not the start of
    anything.
    """
    runs: list[tuple[int, int, list[str]]] = []
    start: int | None = None
    stop = 0
    words: list[str] = []
    for match in _WORD_RE.finditer(text):
        canonical = _canonical(match.group(0))
        if canonical is not None:
            if start is None:
                start = match.start()
            stop = match.end()
            words.append(canonical)
            continue
        if start is not None and match.group(0).lower() in _FILLER:
            continue
        if start is not None and words:
            runs.append((start, stop, words))
        start, words = None, []
    if start is not None and words:
        runs.append((start, stop, words))
    return runs


# A cue that types a digit string which carries no checksum of its own. The
# passport and the plate have no arithmetic to lean on, so the word standing
# before them is the only evidence — the same rule the digit path already uses,
# and the reason «Паспортные данные: 4518123456» needed a sixteen-character
# window there.
_PASSPORT_CUE = re.compile(
    r"(?i)(паспорт\w*|пасспорт\w*|документ\w*|удостовер\w*|серия\b)[^.!?]{0,40}$")


def _classify(digits: str, before: str) -> str | None:
    """Which identifier this digit string is, decided by the SAME rules the
    digit path uses and in the order of how much each one proves.

    СНИЛС FIRST among the eleven-digit shapes, because its checksum is a
    property of the number itself while a phone's validity is a property of a
    numbering plan. A string that satisfies mod 101 and also looks like a phone
    is far more likely to be the СНИЛС somebody just read out.
    """
    length = len(digits)
    if length == 11 and validate_snils(digits):
        return "SNILS"
    if length in (10, 12) and validate_inn(digits):
        return "INN"
    if 13 <= length <= 19 and validate_luhn(digits):
        return "CARD"
    if length == 11 and digits[0] in "78" and digits[1] == "9":
        return "PHONE"
    if length == 10 and digits[0] == "9":
        return "PHONE"
    if length == 10 and _PASSPORT_CUE.search(before):
        return "PASSPORT"
    return None


# Below this many words a run is a quantity, a time or a house number, and the
# checksums are not consulted at all. Ten digits need at least four groups in
# any human dictation; three words never reach a plausible identifier and the
# floor keeps the scanner off «двадцать два ноль восемь».
_MIN_WORDS = 4


def detect_spoken_ids(text: str) -> list[Span]:
    """Identifiers dictated as words, typed by the checksum that validates them."""
    spans: list[Span] = []
    for start, stop, words in numeral_runs(text):
        if len(words) < _MIN_WORDS:
            continue
        digits = run_to_digits(words)
        entity = _classify(digits, text[:start])
        if entity is None:
            continue
        spans.append(Span(start, stop, entity, text[start:stop]))
    return spans


# --- почта и госномер, произнесённые вслух -------------------------------
#
# Ни у одной из этих двух форм нет ШАБЛОНА, а не отбора кандидатов: «воронина
# собака яндекс точка ру» и «эс восемьсот двадцать четыре у у восемнадцать» не
# похожи ни на что, что ищут существующие ветки, поэтому находится ровно ноль.
# Обе формы узкие, и в этом их безопасность — «собака» между двумя словами и
# перед «точка» не встречается в обычной речи, а буква-число-две буквы-регион
# есть ГОСТовская форма номера и больше ничья.

# «собака» — @, «точка» — точка. Обе стороны обязаны быть словами, иначе это
# просто разговор про собаку.
_SPOKEN_EMAIL = re.compile(
    r"(?i)\b([а-яёa-z][а-яёa-z0-9-]{1,30})\s+собак[аи]\s+"
    r"([а-яёa-z][а-яёa-z0-9-]{1,20})\s+точк[аи]\s+([а-яёa-z]{2,4})\b")

# ГОСТ допускает двенадцать букв, и только их — те, у которых есть латинский
# двойник. Названия букв вслух: «эс», «вэ», «ха», «ка», «эм», «эн», «эр», «тэ»,
# и четыре, которые называются собой: «а», «е», «о», «у».
_PLATE_LETTER = r"(?:а|вэ|ве|е|ка|эм|эн|о|эр|эс|тэ|у|ха)"
_SPOKEN_PLATE = re.compile(
    rf"(?i)\b{_PLATE_LETTER}\s+(?:{_HUNDRED_WORDS})(?:\s+(?:{_TEN_WORDS}))?"
    rf"(?:\s+(?:{_UNIT_WORDS}))?\s+{_PLATE_LETTER}\s+{_PLATE_LETTER}"
    rf"(?:\s+регион\w*)?\s+(?:{_TEN_WORDS}|{_HUNDRED_WORDS})"
    rf"(?:\s+(?:{_UNIT_WORDS}))?\b")


# Практическая романизация, которой русские логины и пишутся: «х» как h, «ц»
# как c, «щ» как sch. Не ГОСТ и не ICAO — те дают «kh» и «shch», а почтовые
# сервисы при регистрации предлагают именно эту.
_EMAIL_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}
# Как называют почтовые домены и зоны вслух. Публичные бренды, не наша тюнинг-
# лексика, и живут рядом с образцом, который «собаку» и «точку» уже называет.
_EMAIL_DOMAIN_SOUND: dict[str, str] = {
    "мэйл": "mail", "мейл": "mail", "майл": "mail",
    "джимейл": "gmail", "джимэйл": "gmail", "гмейл": "gmail",
    "яндекс": "yandex", "рамблер": "rambler", "инбокс": "inbox",
    "лист": "list", "аутлук": "outlook", "хотмейл": "hotmail",
}
_EMAIL_TLD_SOUND: dict[str, str] = {
    "ру": "ru", "ком": "com", "нет": "net", "орг": "org", "рф": "рф",
}


def email_from_words(phrase: str) -> str:
    """Почта, продиктованная вслух, в той форме, в какой её примет почтовый ящик.

    ЭТО РЕКОНСТРУКЦИЯ, А НЕ ПЕРЕВОД, и разница честная. Логин человека — то, что
    он сам когда-то выбрал: «ситникова» могла зарегистрироваться как
    `sitnikova`, `sitnikoff` или `s.sitnikova`, и по звучанию фамилии этого не
    узнать. Мы восстанавливаем самое частое написание.

    Почему всё равно лучше слов: в поле `email` уезжало «ситникова собака мэйл
    точка ру», и вызов инструмента не срабатывал НИКОГДА. Реконструкция
    срабатывает в большинстве случаев, а в прозе клиент по-прежнему слышит свою
    же фразу — разделение то же, что для падежа и продиктованных цифр.

    Пустая строка означает «фразу разобрать не удалось», и тогда прежний путь
    остаётся в силе.
    """
    match = _SPOKEN_EMAIL.search(phrase)
    if match is None:
        return ""
    local, domain, tld = (group.lower() for group in match.groups())
    local_latin = "".join(_EMAIL_TRANSLIT.get(letter, letter) for letter in local)
    domain_latin = _EMAIL_DOMAIN_SOUND.get(domain) or "".join(
        _EMAIL_TRANSLIT.get(letter, letter) for letter in domain)
    zone = _EMAIL_TLD_SOUND.get(tld, tld)
    if not local_latin or not domain_latin or not zone:
        return ""
    return f"{local_latin}@{domain_latin}.{zone}"


def detect_spoken_email(text: str) -> list[Span]:
    """«воронина собака яндекс точка ру» — почта, продиктованная вслух."""
    return [Span(m.start(), m.end(), "EMAIL", m.group(0))
            for m in _SPOKEN_EMAIL.finditer(text)]


# Как называют букву госномера вслух. Алфавит ГОСТа выбран так, что у каждой
# буквы есть латинский двойник, поэтому список короткий и закрытый.
_PLATE_LETTER_SOUND: dict[str, str] = {
    "а": "А", "вэ": "В", "ве": "В", "е": "Е", "ка": "К", "эм": "М", "эн": "Н",
    "о": "О", "эр": "Р", "эс": "С", "тэ": "Т", "у": "У", "ха": "Х",
}


def plate_from_words(phrase: str) -> str:
    """Госномер, продиктованный вслух, в той форме, в какой его ждёт ГИБДД.

    ЗАЧЕМ. Каноническая форма для PLATE — это `value.upper()`, и для написанного
    номера она верна. Для произнесённого она возвращает РУССКУЮ ФРАЗУ: «а
    двести шестьдесят три о ка регион шестьдесят шесть» уезжало в аргумент
    инструмента вместо «А263ОК66». Ни одна база ГИБДД такого не примет, и агент
    здесь ни при чём — он получил подмену номером и номер же передал.

    Разбор идёт по той же форме, что и распознавание: буква, число, две буквы,
    регион. Числа переводит `run_to_digits` — та же функция, что и для телефона,
    так что второго перевода слов в цифры в движке не заводится.
    """
    words = [word for word in re.findall(r"[а-яёa-z]+", phrase.lower())
             if word not in ("регион", "регионе", "региона")]
    letters: list[str] = []
    numbers: list[str] = []
    run: list[str] = []
    for word in words:
        if word in _PLATE_LETTER_SOUND and not run:
            letters.append((word, len(numbers)))
            continue
        if word in _UNITS or word in _TEENS or word in _TENS or word in _HUNDREDS:
            run.append(word)
            continue
        if run:
            numbers.append(run_to_digits(run))
            run = []
        if word in _PLATE_LETTER_SOUND:
            letters.append((word, len(numbers)))
    if run:
        numbers.append(run_to_digits(run))
    if len(letters) != 3 or len(numbers) != 2:
        return ""
    head = _PLATE_LETTER_SOUND[letters[0][0]]
    pair = "".join(_PLATE_LETTER_SOUND[letters[index][0]] for index in (1, 2))
    return f"{head}{numbers[0]}{pair}{numbers[1]}"


def detect_spoken_plate(text: str) -> list[Span]:
    """«эс восемьсот двадцать четыре у у восемнадцать» — госномер вслух.

    Форма ГОСТа целиком: буква, три цифры, две буквы, регион. Ничего короче не
    принимается — усечённая форма совпала бы с обычной речью, а полная не
    совпадает ни с чем.
    """
    return [Span(m.start(), m.end(), "PLATE", m.group(0))
            for m in _SPOKEN_PLATE.finditer(text)]
