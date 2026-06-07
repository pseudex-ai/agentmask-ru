"""Name gazetteer + morphology gate — fixes what RU NER misses/over-tags.

NER (trained on capitalized news) misses lowercase diminutives ("света"),
Latin-script names ("Ivan Petrov"), and initials ("Сидоров И.И."), while
over-tagging sentence-initial verbs ("Оформите") as persons.

This module adds a gazetteer (known first names + diminutives + their Latin
transliterations) and a gate: a single-token NER person is kept only if it is a
known name or has a Russian surname shape — otherwise dropped.

NOTE: the name list here is a compact, representative seed. In production swap in
the full RussianNameVariants / russiannames dictionaries (32k names) — same code.
"""

import re

from obscura.detect import Span

_FIRST_NAMES = [
    "александр", "алексей", "анатолий", "андрей", "антон", "артур", "борис",
    "вадим", "валентин", "валерий", "василий", "виктор", "виталий", "владимир",
    "владислав", "вячеслав", "геннадий", "георгий", "глеб", "григорий", "даниил",
    "денис", "дмитрий", "евгений", "егор", "иван", "игорь", "илья", "кирилл",
    "константин", "леонид", "максим", "марк", "михаил", "никита", "николай",
    "олег", "павел", "пётр", "петр", "роман", "руслан", "сергей", "станислав",
    "степан", "тимофей", "фёдор", "федор", "юрий", "ярослав",
    "александра", "алёна", "алина", "алиса", "анастасия", "анна", "валентина",
    "валерия", "вера", "вероника", "виктория", "галина", "дарья", "екатерина",
    "елена", "елизавета", "ирина", "карина", "кристина", "ксения", "лариса",
    "любовь", "людмила", "маргарита", "марина", "мария", "надежда", "наталья",
    "нина", "оксана", "ольга", "полина", "светлана", "софия", "татьяна", "юлия",
]
_DIMINUTIVES = [
    "саша", "лёша", "леша", "толя", "андрюша", "тоша", "вадик", "валя", "вася",
    "витя", "вова", "влад", "слава", "гена", "гоша", "гриша", "даня", "дениска",
    "дима", "женя", "ваня", "игорёк", "костя", "лёня", "макс", "миша", "коля",
    "паша", "петя", "рома", "сергунь", "серёжа", "сережа", "стёпа", "юра",
    "настя", "аня", "валя", "вика", "галя", "даша", "катя", "лена", "лиза",
    "ира", "кристи", "ксюша", "люба", "люда", "рита", "маша", "надя", "наташа",
    "оля", "поля", "света", "соня", "таня", "юля",
]
_SURNAME_SUFFIXES = (
    "ов", "ова", "ев", "ева", "ёв", "ёва", "ин", "ина", "ын", "ына",
    "ский", "ская", "цкий", "цкая", "ко", "ук", "юк", "ян", "дзе", "швили", "ич",
)

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit(text: str) -> str:
    return "".join(_TRANSLIT.get(char, char) for char in text.lower())


_NAME_SET = set(_FIRST_NAMES) | set(_DIMINUTIVES)
_NAME_SET |= {_translit(name) for name in _NAME_SET}

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")
_INITIALS_RE = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?")
_LATIN_PAIR_RE = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b")


def is_known_name(word: str) -> bool:
    return word.lower() in _NAME_SET


def is_surname_shaped(word: str) -> bool:
    low = word.lower()
    return len(low) > 4 and low.endswith(_SURNAME_SUFFIXES)


# Sentence-initial imperatives / fillers NER mislabels as a person or place.
_STOPWORDS = {
    "доставьте", "оформите", "проверьте", "запишите", "уточните", "верните",
    "отмените", "перенесите", "подскажите", "помогите", "скажите", "найдите",
    "сделайте", "добавьте", "измените", "пришлите", "не", "да", "здравствуйте",
    "спасибо", "пожалуйста", "клиент", "заказ",
}


def keep_location(value: str) -> bool:
    """Gate for an NER location span: drop single-token imperatives/fillers."""
    parts = value.split()
    if len(parts) >= 2:
        return True
    return parts[0].lower() not in _STOPWORDS


def keep_person(value: str) -> bool:
    """Gate for an NER person span: keep multi-token names, known names, or
    surname-shaped tokens; drop bare unknown words (verb over-tags)."""
    parts = value.split()
    if len(parts) >= 2:
        return True
    return is_known_name(parts[0]) or is_surname_shaped(parts[0])


def gazetteer_names(text: str) -> list[Span]:
    """Catch names NER misses: known names (any case), Latin pairs, initials."""
    spans: list[Span] = []
    for match in _WORD_RE.finditer(text):
        if match.group().lower() in _NAME_SET:
            spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    for match in _LATIN_PAIR_RE.finditer(text):
        if match.group(1).lower() in _NAME_SET:
            spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    for match in _INITIALS_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    return spans
