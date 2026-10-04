"""A date written the way ANOTHER date is written.

«2 июня 1975» was masked as «19.07.1975»: the substitute changed the
notation before the agent saw it, an agent that copies verbatim copied
digits, and the tool received «02.06.1975» for a customer who wrote the
month in words — 25 of 27 dates of birth on the public benchmark, every one
of them «repaired» into a form nobody had written. The same rule as for
names and addresses: the form belongs to the customer on the way in and to
the agent on the way out; ours appears nowhere.

`render_like(canonical, like)` writes the canonical «dd.mm.yyyy» in the
notation of `like`: the separator, the zero-padding of day and month, a
two-digit year, the ISO order, a month in words with the year present or
absent and a «г.»/«года» kept, or — for a date said entirely in words — the
spelling `spoken.date_to_words` already produces. A notation this module
does not read falls back to the canonical, which is exactly what happened
before for every date.
"""

import re

from pseudex import spoken

_NUMERIC = re.compile(r"^\s*(\d{1,4})([./ -])(\d{1,2})\2(\d{1,4})\s*$")
_MONTH_WORD = re.compile(r"(?i)^\s*(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?(\s*(?:г\.|года|год|г))?\s*$")
_CANONICAL = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")

# The month in the case a date takes it: «2 июня». The stems are the
# reader's (`spoken._MONTH_STEMS`); the endings are the genitive's.
_MONTH_GEN: dict[int, str] = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня", 7: "июля",
    8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}
_MONTH_NOM: dict[int, str] = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь", 7: "июль",
    8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
}


def _pad_like(number: int, sample: str, formal: bool) -> str:
    """Zero-padded when the sample was («09»), or when the notation is the
    formal «dd.mm.yyyy» and the sample had two digits anyway; a «19» beside
    a month in words says nothing about padding, and people write «2 июня»."""
    if sample.startswith("0") or (formal and len(sample) == 2):
        return f"{number:02d}"
    return str(number)


def notation_of(text: str) -> str | None:
    """The notation class a date is written in: «numeric:<sep>:<year digits>»,
    «iso», «month-word», «spoken»; None for anything else."""
    numeric = _NUMERIC.match(text)
    if numeric:
        first, sep, _middle, last = numeric.groups()
        return "iso" if len(first) == 4 else f"numeric:{sep}:{len(last)}"
    worded = _MONTH_WORD.match(text)
    if worded and spoken._month_value(worded.group(2).lower().replace("ё", "е")) is not None:
        return "month-word"
    if not any(ch.isdigit() for ch in text) and spoken.date_from_words(text):
        return "spoken"
    return None


def same_notation(left: str, right: str) -> bool:
    """Both written the same way — then the customer's own words stay, not a
    re-rendering of them: «двадцать первое сентября» is not rewritten as
    «двадцать первого сентября» just because the agent wrote a spoken fake."""
    kind = notation_of(left)
    return kind is not None and kind == notation_of(right)


def render_like(canonical: str, like: str) -> str:
    """`canonical` («dd.mm.yyyy») in the notation of `like`; the canonical
    itself when `like` is not a notation this module reads."""
    match = _CANONICAL.match(canonical.strip())
    if not match:
        return canonical
    day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
    numeric = _NUMERIC.match(like)
    if numeric:
        first, sep, middle, last = numeric.groups()
        if len(first) == 4:                                   # ISO: yyyy-mm-dd
            return f"{year}{sep}{_pad_like(month, middle, True)}{sep}{_pad_like(day, last, True)}"
        formal = len(last) == 4
        shown_year = year[-2:] if len(last) == 2 else year
        return (f"{_pad_like(day, first, formal)}{sep}{_pad_like(month, middle, formal)}"
                f"{sep}{shown_year}")
    worded = _MONTH_WORD.match(like)
    if worded and spoken._month_value(worded.group(2).lower().replace("ё", "е")) is not None:
        sample_month = worded.group(2)
        table = _MONTH_NOM if sample_month.lower().replace("ё", "е") in _MONTH_NOM.values() else _MONTH_GEN
        month_text: str = table[month]
        if sample_month.isupper():
            month_text = month_text.upper()
        elif sample_month[:1].isupper():
            month_text = month_text.capitalize()
        parts = [_pad_like(day, worded.group(1), False), month_text]
        if worded.group(3):
            parts.append(year)
        text = " ".join(parts)
        return text + (worded.group(4) or "")
    if not any(ch.isdigit() for ch in like) and spoken.date_from_words(like):
        words = spoken.date_to_words(canonical, like)
        if words:
            return words
    return canonical


def main() -> int:
    failures = 0
    for canonical, like, want in (
        ("19.07.1975", "2 июня 1975", "19 июля 1975"),
        ("02.06.1975", "19 июля 1975", "2 июня 1975"),
        ("02.06.1975", "19 июля 1975 г.", "2 июня 1975 г."),
        ("02.06.1975", "19 июля 1975 года", "2 июня 1975 года"),
        ("02.06.1975", "19 июля", "2 июня"),
        ("15.09.1982", "10.4.82", "15.9.82"),
        ("10.04.1982", "15.09.82", "10.04.82"),
        ("10.04.1982", "15.09.1982", "10.04.1982"),
        ("10.04.1982", "1982-09-15", "1982-04-10"),
        ("10.04.1982", "15/09/1982", "10/04/1982"),
        ("10.04.1982", "15-09-1982", "10-04-1982"),
        ("10.04.1982", "01 марта 1990", "10 апреля 1982"),
        ("10.04.1982", "чепуха", "10.04.1982"),
        ("не дата", "2 июня 1975", "не дата"),
    ):
        got = render_like(canonical, like)
        if got != want:
            failures += 1
            print(f"FAIL render_like({canonical!r}, {like!r}) = {got!r}, wanted {want!r}")
    for left, right, want in (
        ("двадцать первое сентября восьмидесятого года", "четырнадцатого марта восемьдесят седьмого года", True),
        ("2 июня 1975", "19 июля 1975", True),
        ("10.4.82", "15.9.82", True),
        ("10.04.1982", "15.9.82", False),
        ("10.04.1982", "1982-09-15", False),
        ("2 июня 1975", "19.07.1975", False),
    ):
        got = same_notation(left, right)
        if got != want:
            failures += 1
            print(f"FAIL same_notation({left!r}, {right!r}) = {got!r}, wanted {want!r}")
    for canonical, like, want in ():
        got = render_like(canonical, like)
        if got != want:
            failures += 1
            print(f"FAIL render_like({canonical!r}, {like!r}) = {got!r}, wanted {want!r}")
    print("date_form: PASS" if not failures else f"date_form: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
