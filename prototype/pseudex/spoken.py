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
import time

from pseudex.assets import ASSETS
from pseudex.agent_form import cased_like
from pseudex.fuzzy import within_one_typo
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


def is_numeral_word(word: str) -> bool:
    """A number word — spelled right, or as the leased typo table says a
    transcript misspells it. The one test every reader of a spoken number
    should ask, so that «сто семьдесят четыыре» is one house to the role
    splitter, the key and the digit run alike."""
    low = word.lower().replace("ё", "е")
    if low in _FOLDED_NUMERALS or low in _DOUBLED_NUMERALS:
        return True
    return ASSETS.is_loaded and low in ASSETS.get().spoken.numeral_typos


def numeral_alternation() -> str:
    """Every number word the engine can read now, longest first, for a regex —
    the leased misspellings included when a bundle is loaded."""
    words = set(_ALL_NUMERALS) | set(_DOUBLED_NUMERALS)
    if ASSETS.is_loaded:
        words |= set(ASSETS.get().spoken.numeral_typos)
    return "|".join(sorted(words, key=len, reverse=True))


_FOLDED_NUMERALS = {word.replace("ё", "е") for word in _ALL_NUMERALS}


def _doubled_forms() -> dict[str, str]:
    """Every numeral with ONE letter doubled, mapped to the numeral.

    «пяять», «четыыре», «двадцатть» — a held key or a stretched vowel in a
    transcript, and the commonest damage a spoken number carries. This is not
    the distance-1 matching the module forbids: a doubling never turns one
    word into another («есть» is a substitution away from «шесть», not a
    doubling), and none of the 296 forms is a word pymorphy3 knows — checked
    at the time of writing, and cheap to check again.
    """
    out: dict[str, str] = {}
    for word in _ALL_NUMERALS:
        folded = word.replace("ё", "е")
        for index in range(len(folded)):
            form = folded[:index + 1] + folded[index] + folded[index + 1:]
            if form not in _FOLDED_NUMERALS:
                out.setdefault(form, word)
    return out


_DOUBLED_NUMERALS = _doubled_forms()


def canonical_numeral(word: str) -> str | None:
    """The numeral this word is — itself, or the one the leased typo table says
    the transcript meant; None for a word that is not a numeral."""
    return _canonical(word)


def _canonical(word: str) -> str | None:
    low = word.lower().replace("ё", "е")
    for table in (_UNITS, _TEENS, _TENS, _HUNDREDS):
        for key in table:
            if key.replace("ё", "е") == low:
                return key
    doubled = _DOUBLED_NUMERALS.get(low)
    if doubled:
        return doubled
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


# A DATE SAID ALOUD: «двадцать первое сентября восьмидесятого года», «первого
# марта тысяча девятьсот девяносто первого». The day is an ordinal (a cardinal
# ten plus an ordinal unit above twenty), the month a calendar word, the year
# a cardinal thousand and hundred followed by an ordinal, or an ordinal alone
# for the century a speaker leaves out. Calendar words are grammar, not tuning.
_ORDINAL_STEMS: dict[str, int] = {
    "перв": 1, "втор": 2, "трет": 3, "четверт": 4, "четвёрт": 4, "пят": 5, "шест": 6,
    "седьм": 7, "восьм": 8, "девят": 9, "десят": 10, "одиннадцат": 11, "двенадцат": 12,
    "тринадцат": 13, "четырнадцат": 14, "пятнадцат": 15, "шестнадцат": 16,
    "семнадцат": 17, "восемнадцат": 18, "девятнадцат": 19, "двадцат": 20, "тридцат": 30,
    "сороков": 40, "пятидесят": 50, "шестидесят": 60, "семидесят": 70, "восьмидесят": 80,
    "девяност": 90, "сот": 100, "двухсот": 200, "трёхсот": 300, "трехсот": 300,
    "четырёхсот": 400, "четырехсот": 400, "пятисот": 500, "шестисот": 600, "семисот": 700,
    "восьмисот": 800, "девятисот": 900, "тысячн": 1000, "двухтысячн": 2000,
}
_MONTH_STEMS: tuple[tuple[str, int], ...] = (
    ("январ", 1), ("феврал", 2), ("март", 3), ("апрел", 4), ("ма", 5), ("июн", 6), ("июл", 7),
    ("август", 8), ("сентябр", 9), ("октябр", 10), ("ноябр", 11), ("декабр", 12))
_THOUSANDS = {"тысяча": 1000, "тысячи": 1000, "тысяч": 1000}


def _ordinal_value(word: str) -> int | None:
    for stem in sorted(_ORDINAL_STEMS, key=len, reverse=True):
        if word.startswith(stem) and len(word) - len(stem) <= 4:
            return _ORDINAL_STEMS[stem]
    return None


def _month_value(word: str) -> int | None:
    for stem, number in _MONTH_STEMS:
        if word.startswith(stem) and (stem != "ма" or word in ("мая", "май", "маю", "мае")):
            return number
    return None


def date_from_words(phrase: str) -> str:
    """«dd.mm.yyyy» for a date said in words, or "" when the words are not one."""
    words = [w for w in _WORD_RE.findall(phrase.lower().replace("ё", "е")) if w not in ("года", "год", "г")]
    # Only the stem's «ё» is restored: replacing every «е» gave «чётвёртоё», a
    # word no table holds, and «четвёртое августа» was not a date at all.
    words = [w.replace("четверт", "четвёрт", 1) if w in ("четвертого", "четвертое") else w for w in words]
    month_at = next((i for i, w in enumerate(words) if _month_value(w) is not None), None)
    if month_at is None or month_at == 0:
        return ""
    day = 0
    for word in words[:month_at]:
        if word in _TENS:
            day += _TENS[word]
        else:
            value = _ordinal_value(word) if word not in _UNITS and word not in _TEENS else _UNITS.get(word, _TEENS.get(word))
            if value is None:
                return ""
            day += value
    if not 1 <= day <= 31:
        return ""
    month = _month_value(words[month_at])
    year = 0
    tail = words[month_at + 1:]
    if tail and tail[0].isdigit():
        year = int(tail[0])
    elif tail:
        index = 0
        while index < len(tail):
            word = tail[index]
            if word in _UNITS or word in _HUNDREDS or word in _TENS or word in _TEENS:
                value = _UNITS.get(word, _HUNDREDS.get(word, _TENS.get(word, _TEENS.get(word, 0))))
                if index + 1 < len(tail) and tail[index + 1] in _THOUSANDS:
                    year += value * 1000
                    index += 2
                    continue
                year += value
            elif word in _THOUSANDS:
                year += 1000
            else:
                value = _ordinal_value(word)
                if value is None:
                    return ""
                year += value
            index += 1
        if year < 100:
            # The century left unsaid: «восьмидесятого года» is 1980, «пятого
            # года» is 2005 — a two-digit year not yet reached belongs to the
            # previous century.
            year += 2000 if year <= int(__import__("time").localtime().tm_year) % 100 else 1900
    if not 1900 <= year <= 2100:
        return "" if tail else f"{day:02d}.{month:02d}"
    return f"{day:02d}.{month:02d}.{year}"


# THE WAY BACK: a date in WORDS, for a substitute that replaces a date the
# customer SAID. «родился одиннадцатого сентября пятьдесят пятого» was masked
# as «родился 28.03.1972 пятьдесят пятого» (seed-6060 run, 9 of 9 spoken dates
# of birth): a digit date in a spoken sentence, and the year left outside the
# span standing next to a substitute that carries another year. The register
# is part of what the model reads; a substitute in another register is a
# substitute the model notices, and what it notices it edits.
_ORDINAL_GEN: dict[int, str] = {
    1: "первого", 2: "второго", 3: "третьего", 4: "четвёртого", 5: "пятого", 6: "шестого",
    7: "седьмого", 8: "восьмого", 9: "девятого", 10: "десятого", 11: "одиннадцатого",
    12: "двенадцатого", 13: "тринадцатого", 14: "четырнадцатого", 15: "пятнадцатого",
    16: "шестнадцатого", 17: "семнадцатого", 18: "восемнадцатого", 19: "девятнадцатого",
    20: "двадцатого", 30: "тридцатого", 40: "сорокового", 50: "пятидесятого",
    60: "шестидесятого", 70: "семидесятого", 80: "восьмидесятого", 90: "девяностого",
}
_TENS_CARD: dict[int, str] = {20: "двадцать", 30: "тридцать", 40: "сорок", 50: "пятьдесят",
                              60: "шестьдесят", 70: "семьдесят", 80: "восемьдесят", 90: "девяносто"}
_MONTH_GEN: dict[int, str] = {1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
                              7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября",
                              12: "декабря"}


def _ordinal_gen(value: int) -> str:
    """«двадцать первого» for 21, «пятидесятого» for 50 — the genitive ordinal
    a Russian date is said in, for 1..99."""
    if value in _ORDINAL_GEN:
        return _ORDINAL_GEN[value]
    tens, unit = value - value % 10, value % 10
    return f"{_TENS_CARD[tens]} {_ORDINAL_GEN[unit]}"


def _day_ordinal_like(day: int, like: str) -> str:
    """Preserve the neuter nominative day in dates such as 'fourth of August'.

    Only the ordinal immediately before the month supplies case evidence;
    the year's genitive ordinal must not override it. Compound days inflect
    their final word only. This is rendering, never a new date recognizer.
    """
    words: list[str] = _WORD_RE.findall(like.lower())
    month_index: int | None = next(
        (index for index, word in enumerate(words) if _month_value(word) is not None), None)
    rendered: str = _ordinal_gen(day)
    if month_index is None or month_index == 0:
        return rendered
    sample: str = words[month_index - 1]
    if _ordinal_value(sample) is None or not sample.endswith(("ое", "ье", "ее")):
        return rendered
    # The soft ordinal is 'третьего' -> 'третье'; hard ordinals use -ое.
    return rendered[:-2] if rendered.endswith("третьего") else rendered[:-3] + "ое"


def date_to_words(canonical: str, like: str) -> str:
    """«dd.mm.yyyy» (or «dd.mm») said the way `like` says its own date: the
    century spelled out when `like` spells it («тысяча девятьсот …»), two
    digits otherwise («пятьдесят пятого»), «года» appended when `like` says
    it. "" when the canonical is not a date. Every output reads back through
    `date_from_words` to the same canonical — the module's self-test proves it."""
    match = re.fullmatch(r"(\d{2})\.(\d{2})(?:\.(\d{4}))?", canonical.strip())
    if not match:
        return ""
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return ""
    words = [_day_ordinal_like(day, like), _MONTH_GEN[month]]
    if match.group(3):
        year = int(match.group(3))
        century, short = divmod(year, 100)
        # THE CENTURY IS SPELLED WHEN TWO DIGITS WOULD READ BACK WRONG. «двадцать
        # шестого» is 2026 to `date_from_words` and to a listener — a year not
        # yet reached belongs to the previous century — so a person born in
        # 1926 is said with the century whatever the customer's own habit was.
        now = time.localtime().tm_year % 100
        ambiguous = (century == 19 and short <= now) or (century == 20 and short > now)
        spelled = "тысяч" in like.lower() or ambiguous
        if century == 20:
            if short == 0:
                words.append("двухтысячного")
            elif spelled:
                words.extend(["две", "тысячи", _ordinal_gen(short)])
            else:
                words.append(_ordinal_gen(short))
        elif century == 19:
            if short == 0:
                words.append("тысяча девятисотого")
            elif spelled:
                words.extend(["тысяча", "девятьсот", _ordinal_gen(short)])
            else:
                words.append(_ordinal_gen(short))
        else:
            return ""
        if re.search(r"\bгод", like.lower()):
            words.append("года")
    return " ".join(words)


def run_to_digits(words: list[str]) -> str:
    """Concatenate a run of numeral groups into the digit string that was said.

    Concatenation, not addition: «восемь девятьсот шестнадцать» is the start of
    a phone number, not the sum 924. What a person dictating an identifier
    produces is a sequence of groups, and each group contributes its own digits
    in order.
    """
    # The leased misspellings are read as the numerals they are, so a caller
    # that admitted «триц» through `is_numeral_word` gets 30 and not a KeyError.
    words = [_canonical(word) or word for word in words]
    out: list[str] = []
    index = 0
    while index < len(words):
        value, index = _group(words, index)
        out.append(str(value))
    return "".join(out)


def _spell_identifier_group(digits: str) -> str:
    """Spell up to three digits, retaining every leading zero as a digit."""
    zeroes: int = len(digits) - len(digits.lstrip("0"))
    words: list[str] = ["ноль"] * zeroes
    remaining: int = int(digits)
    for table in (_HUNDREDS, _TEENS, _TENS, _UNITS):
        if table is _TEENS and remaining >= 20:
            continue
        values: list[int] = sorted(set(table.values()), reverse=True)
        for value in values:
            if value and remaining >= value:
                words.append(next(word for word, number in table.items() if number == value))
                remaining -= value
                break
    return " ".join(words)


def _rendered_words(target: str, value: int, spoken: list[str]) -> list[str]:
    """The canonical words one dictated group renders to: the sender's own
    while the digits are unchanged, the spelled-out target otherwise."""
    return list(spoken) if target == str(value) else _spell_identifier_group(target).split()


def _absorbs(closing: str, opening: str) -> bool:
    """Whether the greedy parse reads two neighboring groups as ONE number.

    `_group` extends a hundreds word with a teen, a tens or a unit, and a tens
    word with a unit; a unit, a teen or «ноль» closes a group outright. So an
    open boundary is exactly a hundreds/tens word before a word it can still
    take — and it fails SILENTLY: the words stay numerals, only the digits
    become somebody else's number. This is the one place the grammar is
    consulted; leaving it to the readback guard alone can see that a layout
    broke but not which boundary to repair.
    """
    if closing in _HUNDREDS:
        return ((opening in _UNITS and _UNITS[opening] != 0)
                or opening in _TEENS or opening in _TENS)
    if closing in _TENS:
        return opening in _UNITS and _UNITS[opening] != 0
    return False


def _slices_like_model(digits: str, values: list[int],
                       spoken: list[list[str]]) -> list[str] | None:
    """Split `digits` at the model's group widths, lending the group before an
    open boundary one digit to the group after it.

    The sender's grouping stands wherever it can. Where it cannot — a target
    group whose spelling ends in «двадцать» before a one-digit group — the
    boundary moves one digit LEFT: «220» + «2» becomes «22» + «02». The borrowed
    digit leads the next group, which closes it, because a group opening with a
    tens/teen/unit word is exactly what a preceding hundreds word swallows and
    «ноль» is what it cannot. Only a boundary that is open moves, so a run whose
    digits did not change keeps the sender's words group for group; the
    regrouped tail is the smallest repair that reads back. None when no
    regrouping of these widths represents the digits.

    Each move carries exactly one digit one group to the right, so the number of
    moves is bounded by (digits × groups) and the loop cannot run away; the
    readback guard in `digits_in_words_like` still decides what is returned.
    """
    slices: list[str] = []
    at: int = 0
    for value in values:
        width: int = len(str(value))
        slices.append(digits[at:at + width])
        at += width
    if at != len(digits):
        return None
    for _ in range(len(digits) * len(slices) + 1):
        spelled: list[list[str]] = [_rendered_words(slices[index], values[index], spoken[index])
                                    for index in range(len(slices))]
        open_at: int | None = next(
            (index for index in range(len(slices) - 1)
             if _absorbs(spelled[index][-1], spelled[index + 1][0])), None)
        if open_at is None:
            return slices
        # A one-digit group has nothing to lend, and a three-digit group always
        # OPENS closed (a hundreds word or «ноль»), so neither can be the far
        # side of an open boundary. The guards keep a later grammar change from
        # turning this into a silent infinite loop rather than a refusal.
        if len(slices[open_at]) < 2 or len(slices[open_at + 1]) > 2:
            return None
        slices[open_at], slices[open_at + 1] = (
            slices[open_at][:-1], slices[open_at][-1] + slices[open_at + 1])
    return None


def digits_in_words_like(digits: str, model: str) -> str | None:
    """Render known digits in a whole dictated run's grouping and letter case.

    This is presentation only: it never recognizes an identifier or chooses
    its owner. Group widths come from the existing numeral grammar, not from
    a phone-specific 1/3/3/2/2 layout. An unrepresentable layout returns None;
    in particular, neighboring groups must not merge into a different number.
    """
    lexical: list[re.Match[str]] = list(_WORD_RE.finditer(model))
    if not digits.isascii() or not digits.isdigit() or not lexical or any(char.isdigit() for char in model):
        return None
    matches: list[re.Match[str]] = []
    words: list[str] = []
    for match in lexical:
        canonical: str | None = _canonical(match.group())
        if canonical is None:
            if match.group().lower() in _FILLER:
                continue
            return None
        matches.append(match)
        words.append(canonical)
    if len(run_to_digits(words)) != len(digits):
        return None
    # The digit split is decided for the WHOLE run before a word is written: a
    # boundary that has to move moves into the group after it, and a repair
    # chosen group by group could not see that.
    spans: list[tuple[int, int, int]] = []
    index: int = 0
    while index < len(words):
        value, end = _group(words, index)
        spans.append((index, end, value))
        index = end
    slices: list[str] | None = _slices_like_model(
        digits, [value for _, _, value in spans], [words[start:end] for start, end, _ in spans])
    if slices is None:
        return None
    rendered: list[str] = []
    text_at: int = 0
    for (start, end, value), target in zip(spans, slices, strict=True):
        low, high = matches[start].start(), matches[end - 1].end()
        surface: str = model[low:high]
        # Inter-group hesitations remain in the untouched gaps. An internal
        # hesitation cannot be relocated into a differently sized word group
        # without a separate alignment rule; do not silently erase it.
        if target != str(value) and any(
                word.group().lower() in _FILLER for word in _WORD_RE.finditer(surface)):
            return None
        replacement: str = surface if target == str(value) else cased_like(
            _spell_identifier_group(target), surface)
        rendered.extend((model[text_at:low], replacement))
        text_at = high
    rendered.append(model[text_at:])
    result: str = "".join(rendered)
    readback: list[str] = [word for match in _WORD_RE.finditer(result)
                           if (word := _canonical(match.group())) is not None]
    return result if run_to_digits(readback) == digits else None


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


def _cue_near(before: str, cues: tuple[str, ...]) -> bool:
    """A cue word in the last few words before the run — as written, stretched
    («паспоорт»), or one typo away («паспрот»)."""
    words = _WORD_RE.findall(before.lower())[-4:]
    for raw in words:
        word = re.sub(r"([а-яё])\1+", r"\1", raw)
        for cue in cues:
            if word.startswith(cue) or (len(word) >= 4 and within_one_typo(word[:len(cue)], cue)):
                return True
    return False


# THE STRETCH-ABSORBING COLLAPSE ABOVE EATS A CUE THAT IS MADE OF A DOUBLED
# LETTER. `_cue_near` folds «паспоорт» back to «паспорт» by deleting the repeat —
# and the initialism «инн» is nothing BUT a repeat, so it collapsed to «ин», no
# cue started with that, and the INN branch below could never fire however the
# customer spelled it. Measured on the pristine bytes: «инн <twelve dictated
# digits, one misheard>» reached the model in the clear.
#
# The digit path has always read this token exactly (`_INN_CUE_RE` is `\bинн\b`),
# so the spoken path reads the same token the same way: the word as written, not
# its de-stretched residue. The fold stays for every cue that needs it — a
# misspelt or held key still matches through `_cue_near`.
def _cue_exact_near(before: str, cue: str) -> bool:
    """A cue word in the last few words before the run, spelled as itself."""
    return any(word == cue for word in _WORD_RE.findall(before.lower())[-4:])


# THE CARD CUE IS THE DIGIT PATH'S, WORD FOR WORD. `ru_pii._CARD_CUE` types the
# run behind «карта» with NO checksum — a mistyped card the customer named is
# still their card — and the spoken path had no such branch at all: a card
# dictated with one digit misheard failed Luhn and went out in the clear, while
# the same card TYPED with one digit wrong was masked. The vocabulary and the
# refusals are copied rather than re-invented: «картина», «картон» and
# «картотека» share the first letters and are refused by the digit path, so they
# are refused here; the stem «карточ-» is admitted because «карточка» is the
# diminutive the digit path admits.
_CARD_CUE_WORDS = frozenset((
    "карт", "карта", "карты", "карте", "карту", "картой", "картою", "картам",
    "картами", "картах", "card", "cards",
))
_CARD_CUE_STEM = "карточ"
# A HYPHEN JOINED TO A LETTER IS A COMPOUND, NOT A SEPARATOR — the digit path's
# cue is `\bкарт\b(?!-[а-яё])` for exactly this reason: «карт-бланш» contains the
# word «карт» and is nobody's card. `_WORD_RE` splits at the hyphen, so the cue
# reader tokenizes compounds whole.
_CUE_WORD_RE = re.compile(r"[а-яё]+(?:-[а-яё]+)*")


def _card_cue_near(before: str) -> bool:
    """The card cue in the last few words before the run, the digit path's forms."""
    for word in _CUE_WORD_RE.findall(before.lower())[-4:]:
        if word in _CARD_CUE_WORDS or word.startswith(_CARD_CUE_STEM):
            return True
    for word in re.findall(r"[a-z]+", before.lower())[-4:]:
        if word in _CARD_CUE_WORDS:
            return True
    return False


def _classify(digits: str, before: str) -> str | None:
    """Which identifier this digit string is, decided by the SAME rules the
    digit path uses and in the order of how much each one proves.

    СНИЛС FIRST among the eleven-digit shapes, because its checksum is a
    property of the number itself while a phone's validity is a property of a
    numbering plan. A string that satisfies mod 101 and also looks like a phone
    is far more likely to be the СНИЛС somebody just read out.
    """
    length = len(digits)
    # THE CUE OUTRANKS A COINCIDENTAL CHECKSUM. «паспорт ноль три четырнадцать
    # …» satisfied the ten-digit ИНН weights by chance and went out as an ИНН;
    # a dictated СНИЛС with one digit misheard failed mod 101 and went out in
    # the clear. Behind the word the evidence is the word (same rule as the
    # digit path's `_SNILS_CUE_RE`), and the word may be stretched or mistyped.
    if length == 10 and _cue_near(before, ("паспорт", "пасспорт", "документ", "удостоверение", "серия")):
        return "PASSPORT"
    if length == 11 and _cue_near(before, ("снилс",)):
        return "SNILS"
    # «инн» IS READ AS THE TOKEN, not through the collapse — see `_cue_exact_near`.
    # Ten digits as well as twelve, because the SPEAKER'S WORD is the evidence in
    # both: the digit path demands the checksum too for a ten-digit ИНН, but the
    # spoken path's own rule is the one written above for СНИЛС — behind the word
    # the evidence is the word — and P05 protects a wrong personal number as the
    # number that was said. The digit leg is left as it is: that is a cross-leg
    # policy call, not this file's.
    if length in (10, 12) and _cue_exact_near(before, "инн"):
        return "INN"
    # …BUT THE CUE THE CUSTOMER SAID OUTRANKS A CHECKSUM THAT HAPPENS TO
    # HOLD. «телефон восемь девятьсот пятьдесят сто шестьдесят двадцать
    # десять» satisfies mod 101 one time in a hundred, and that one time the
    # number was minted as a СНИЛС, restored as one, and the agent's phone
    # validator refused every call (fresh-seed v4, chain-014).
    if length == 11 and digits[0] in "78" and digits[1] == "9" and _cue_near(
            before, ("телефон", "тел", "номер", "мобильн", "сотов", "звонит", "позвон")):
        return "PHONE"
    if length == 11 and validate_snils(digits):
        return "SNILS"
    if length in (10, 12) and validate_inn(digits):
        return "INN"
    if 13 <= length <= 19 and validate_luhn(digits):
        return "CARD"
    # A CARD THE SPEAKER NAMED NEEDS NO CHECKSUM — the digit path's rule, and the
    # branch the spoken path was missing. Placed AFTER a passing Luhn so a valid
    # card keeps the checksum's own reading; it can only add the number the
    # customer called a card and the arithmetic could not confirm.
    if 13 <= length <= 19 and _card_cue_near(before):
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


# Имя буквы, которым её НАЗЫВАЮТ. Обратная к `_PLATE_LETTER_SOUND`, и таблица
# отдельная намеренно: у «В» два произношения («вэ» и «ве»), а писать нужно
# одно — то, которое читает обратно тот же `_PLATE_LETTER_SOUND`.
_PLATE_LETTER_WORD: dict[str, str] = {
    "А": "а", "В": "вэ", "Е": "е", "К": "ка", "М": "эм", "Н": "эн",
    "О": "о", "Р": "эр", "С": "эс", "Т": "тэ", "У": "у", "Х": "ха",
}
_PLATE_CONTENT = re.compile(r"^([A-Za-zА-Яа-яЁё])(\d{3})([A-Za-zА-Яа-яЁё]{2})(\d{2,3})$")
_PLATE_LATIN_TO_CYR = str.maketrans("ABEKMHOPCTYXabekmhopctyx", "АВЕКМНОРСТУХавекмнорстух")


def plate_in_words_like(plate: str, model: str) -> str | None:
    """Госномер, ПРОИЗНЕСЁННЫЙ так, как произносят его в `model`.

    ОБРАТНАЯ К `plate_from_words`, и это требование обратимости, а не удобство:
    подмена, наследующая диктовку источника, должна читаться обратно, иначе она
    перестаёт разрешаться. Числа пишет `_spell_identifier_group` — та же
    функция, которой чеканятся цифровые группы в диктовке телефона, а буквы
    называет `_PLATE_LETTER_WORD`.

    ЧТЕНИЕ ПРОВЕРЯЕТСЯ ЗДЕСЬ ЖЕ. `plate_from_words` — единственный читатель этой
    формы, и если он не возвращает исходный номер, рендер отказывается: лучше
    письменная форма, чем фраза, которую никто не прочитает.
    """
    content = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]", "", plate)
    match = _PLATE_CONTENT.fullmatch(content)
    if match is None:
        return None
    head, digits, pair, region = match.groups()
    head, pair = head.upper(), pair.upper()
    if any(letter.upper() not in _PLATE_LETTER_WORD for letter in (head, pair[0], pair[1])):
        return None
    words = [_PLATE_LETTER_WORD[head], _spell_identifier_group(digits),
             _PLATE_LETTER_WORD[pair[0]], _PLATE_LETTER_WORD[pair[1]]]
    if re.search(r"(?i)\bрегион", model):
        words.append("регион")
    words.append(_spell_identifier_group(region))
    text = " ".join(words)
    if plate_from_words(text) != content.upper().translate(_PLATE_LATIN_TO_CYR):
        return None
    return cased_like(text, model)


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


def main() -> int:
    """Self-test: every spoken date reads back to the canonical it was made from."""
    import time as _time
    failures = 0
    year_now = _time.localtime().tm_year
    for year in (1930, 1955, 1960, 1980, 1987, 1999, 2000, 2005, 2010, 2021, year_now % 100 + 1900):
        for day in (1, 3, 4, 11, 17, 20, 21, 28, 30, 31):
            for month in (1, 5, 9, 12):
                canonical = f"{day:02d}.{month:02d}.{year}"
                for like in ("одиннадцатого сентября пятьдесят пятого", "двадцать третьего марта тысяча девятьсот восемьдесят второго года"):
                    words = date_to_words(canonical, like)
                    back = date_from_words(words)
                    if back != canonical:
                        failures += 1
                        if failures <= 8:
                            print(f"FAIL {canonical} -> {words!r} -> {back!r}")
    if date_to_words("17.08", "родился семнадцатого августа") != "семнадцатого августа":
        failures += 1
        print("FAIL a date without a year stays without one")
    print("spoken: PASS" if not failures else f"spoken: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
