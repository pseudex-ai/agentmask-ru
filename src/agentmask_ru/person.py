"""One person, however the words are inflected or ordered.

The round-trip judge compared strings, and a string judge cannot read
Russian: «есина рушана» (the customer, accusative, surname first) and
«Рушан Есин» (what the tool received) are one person, while «есина» on its
own also reads as a feminine surname in the nominative — so a masker that
resolved the person CORRECTLY was scored as a loss, and its two inflections
of one substitute («Харитон Рыбаков», «Харитона Рыбакова») as two different
substitutes. Fifteen round trips and every second-mention case of one
system on the first corpus.

THE RULE IS NEUTRAL: two names are the same person when they have the same
number of words and the words pair up so that each pair shares a lemma
candidate. A placeholder («<PERSON_1>») equals itself exactly, as before; a
different person shares no lemma. Word order is ignored on purpose — a CRM
field holds «Есин Рушан» and «Рушан Есин» as one record.

EVERY parse is a candidate, not the first one. pymorphy3 ranks «рыбакова»
as a feminine surname first; the masculine genitive is the third reading.
Taking only the top parse would repeat the judge's original mistake with a
better-looking tool. Fringe readings are dropped, though: «Иванов» also
parses as the genitive plural of «Иван» at a score of 0.009, and with it
«Иван Петров» and «Пётр Иванов» became one person. Genuine readings of an
ambiguous form split the score evenly (three at 0.333 for «рыбакова»), so
anything under 0.1 is a reading the dictionary itself does not believe in.
"""

import re
from functools import lru_cache

_MIN_SCORE = 0.1

_WORD = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)?")


@lru_cache(maxsize=1)
def _analyzer():  # type: ignore[no-untyped-def]
    import pymorphy3  # noqa: PLC0415 — imported lazily so the harness starts without it

    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=65536)
def lemmas(word: str) -> frozenset[str]:
    """Every normal form pymorphy3 offers for the word, plus the word itself."""
    folded = word.casefold().replace("ё", "е")
    forms = {folded}
    for parse in _analyzer().parse(folded):
        if parse.score >= _MIN_SCORE:
            forms.add(parse.normal_form.replace("ё", "е"))
    return frozenset(forms)


def words_of(text: str) -> list[str]:
    return _WORD.findall(text)


def looks_like_person(text: str) -> bool:
    """Only Cyrillic words, one to four of them, nothing else in between —
    the shape of a name. Anything with digits, Latin or punctuation inside
    is judged by the other rules."""
    stripped = text.strip()
    if not stripped:
        return False
    words = words_of(stripped)
    if not 1 <= len(words) <= 4:
        return False
    return re.fullmatch(r"[А-Яа-яЁё\s-]+", stripped) is not None


def same_person(left: str, right: str) -> bool:
    """The same name up to inflection and word order (see the module docstring)."""
    a, b = words_of(left), words_of(right)
    if not a or len(a) != len(b):
        return False
    remaining = [lemmas(w) for w in b]
    for word in a:
        mine = lemmas(word)
        match = next((i for i, other in enumerate(remaining) if mine & other), None)
        if match is None:
            return False
        remaining.pop(match)
    return True
