"""What a model does to a value it puts into a JSON argument — one habit per
type, deterministic, applied to the SUBSTITUTE it was shown.

A real model fills `name` with a Title-case nominative, `phone` with
«+7XXXXXXXXXX», `dob` with ISO, `card` with bare digits; it never copies a
chat message's «есина рушана» or «2 июня 1975» as written. `rewriter` is that
model. A placeholder («<PERSON_1>») carries no form to rewrite and passes
through unchanged — which is why a placeholder gateway scores the same under
both agents, and a format-preserving one is measured on both.
"""

import datetime as _dt
import re

from agentmask_ru.person import _analyzer, looks_like_person

_MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7,
    "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}
_PLACEHOLDER = re.compile(r"^\s*[<\[{(].*[>\]})]\s*$|^[A-Z][A-Z_]{2,}\d*$")
_GENERIC = {"улица", "улицы", "улицу", "улице", "ул", "проспект", "проспекта", "пр", "переулок", "переулка", "пер",
            "бульвар", "бульвара", "шоссе", "набережная", "набережной", "площадь", "площади", "проезд", "проезда",
            "дом", "д", "кв", "квартира", "корпус", "корп", "строение", "стр", "подъезд", "г", "город"}


def _is_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDER.match(text.strip()))


_FEMN_SURNAME = ("ова", "ева", "ёва", "ина", "ына", "ская", "цкая", "ая")


def _gender_of(words: list[str]) -> str | None:
    """The person's gender as a model reads it: an unambiguous feminine
    surname ending decides outright («Пастухова»), else the given name's
    `Name` parse, else any surname parse."""
    for word in words:
        w = word.casefold().replace("ё", "е")
        if any(w.endswith(suf.replace("ё", "е")) for suf in _FEMN_SURNAME):
            return "femn"
    votes: dict[str, int] = {"masc": 0, "femn": 0}
    for word in words:
        for parse in _analyzer().parse(word.casefold()):
            if "Name" in parse.tag and parse.tag.gender in votes and parse.score >= 0.1:
                votes[parse.tag.gender] += 2
                break
    if not any(votes.values()):
        for word in words:
            for parse in _analyzer().parse(word.casefold()):
                if "Surn" in parse.tag and parse.tag.gender in votes and parse.score >= 0.1:
                    votes[parse.tag.gender] += 1
                    break
    if votes["masc"] == votes["femn"]:
        return None
    return max(votes, key=votes.get)


def _nominative(word: str, gender: str | None) -> str:
    """The nominative a model writes for one word of a name. A model does not
    invent morphology it is unsure of: a word that already reads as a
    nominative name part, or has no confident name parse, is kept AS WRITTEN
    and only Title-cased («Салихат», «Дормедонтов» stay). Only a word that
    confidently reads as an OBLIQUE name part is turned to the nominative
    («Рыбакова» → «Рыбаков», «Харитона» → «Харитон»), agreeing with the
    person's gender so a feminine surname is not made masculine."""
    def titled(w: str) -> str:
        return w[:1].upper() + w[1:]
    parses = [p for p in _analyzer().parse(word.casefold())
              if p.score >= 0.1 and ("Surn" in p.tag or "Name" in p.tag or "Patr" in p.tag)]
    if not parses:
        return titled(word)
    if any("nomn" in p.tag for p in parses):
        return titled(word)
    oblique = [p for p in parses if gender is None or p.tag.gender in (gender, None)]
    chosen = oblique[0] if oblique else parses[0]
    form = chosen.inflect({"nomn", gender} if gender else {"nomn"}) or chosen.inflect({"nomn"})
    return titled(form.word if form is not None else word.casefold())


_LATIN_FOLD = str.maketrans("aAeEoOpPcCyYxXHKMTBaeopcyx", "аАеЕоОрРсСуУхХНКМТВаеорсух")


def rewrite_name(text: str) -> str:
    # A real model reads «григоровa» (a Latin «a» in a Cyrillic word) as the
    # Russian word and Title-cases it; the fold lets `looks_like_person` see it.
    folded = text.translate(_LATIN_FOLD)
    if not looks_like_person(folded):
        return text
    words = folded.split()
    gender = _gender_of(words)
    return " ".join(_nominative(word, gender) for word in words)


def rewrite_phone(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return text


def rewrite_date(text: str) -> str:
    t = text.strip()
    m = re.fullmatch(r"(\d{1,2})[./ -](\d{1,2})[./ -](\d{2,4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(y) if len(y) == 4 else (2000 + int(y) if int(y) <= _dt.date.today().year % 100 else 1900 + int(y))
        return f"{year:04d}-{mo:02d}-{d:02d}"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return t
    m = re.fullmatch(r"(?i)(\d{1,2})\s+([а-яё]+)\s+(\d{4})(?:\s*(?:г\.|года|год))?", t)
    if m:
        mo = _MONTHS.get(m.group(2).lower()[:3])
        if mo:
            return f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(1)):02d}"
    return text


def rewrite_digits(text: str, groups: tuple[int, ...], sep: str) -> str:
    digits = re.sub(r"\D", "", text)
    if len(digits) != sum(groups):
        return text
    out, pos = [], 0
    for size in groups:
        out.append(digits[pos:pos + size]); pos += size
    return sep.join(out)


def rewrite_address(text: str) -> str:
    t = re.sub(r"(?i)\bкв\.?\s*(?=\d)", "кв. ", text)
    t = re.sub(r"(?i)\bд\.?\s*(?=\d)", "д. ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return " ".join(w[:1].upper() + w[1:] if re.match(r"[а-яё]", w) and w.rstrip(".,").lower() not in _GENERIC else w
                    for w in t.split())


def rewrite(kind: str, shown: str) -> str:
    """The model's habitual notation for a value of `kind`, applied to what it
    was shown; a placeholder passes through."""
    if _is_placeholder(shown):
        return shown
    if kind == "NAME":
        return rewrite_name(shown)
    if kind == "PHONE":
        return rewrite_phone(shown)
    if kind == "DOB":
        return rewrite_date(shown)
    if kind == "CARD":
        return rewrite_digits(shown, (16,), "")
    if kind == "SNILS":
        digits = re.sub(r"\D", "", shown)
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}" if len(digits) == 11 else shown
    if kind == "PASSPORT":
        return rewrite_digits(shown, (2, 2, 6), " ")
    if kind == "EMAIL":
        return shown.lower()
    if kind == "ADDRESS":
        return rewrite_address(shown)
    return shown
