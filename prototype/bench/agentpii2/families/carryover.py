"""Family `transfer` — v1's ten scenarios, carried into the v2 schema.

WHAT THIS FAMILY ASKS: the customer states a datum in a message, one tool
consumes it, did the REAL value arrive. That is the whole of v1, and it is
carried here rather than rewritten so that a v2 number can be read against a v1
number without a footnote about what moved.

WHY IT IS STILL THE BIGGEST FAMILY. It is the only one where a per-TYPE rate is
estimable: every other family is built around a mechanism, not around the
inventory of types. CARD and PLATE live in one scenario each, which at 3 sets per
cell is 45 gold values per type and 9 per register — just above the suppression
floor of five that `schema.type_denominators` states. Fewer and the per-type
table stops existing; more and the corpus is v1 with a new cover.

CARRIED VERBATIM, because each one was paid for by a defect:

  * offsets computed DURING assembly, never by searching the finished string. A
    search finds the FIRST occurrence, and a message naming the same phone twice
    then carries a span pointing at the wrong one.
  * no post-processing pass over a finished message. Stripping punctuation after
    the fact changes the length and silently invalidates every span computed
    before it; the corpus still scores, and scores wrongly. Register lives in the
    template and in the slot values, both chosen before a single character is
    counted.
  * `canonical` is the canonical form of WHAT WAS WRITTEN. A chat message with no
    patronymic must not demand one back. v1 reconstructed it by matching clean
    parts against the surface and lost every part a register had touched — 162 of
    its 183 sloppy round-trip failures were the corpus, not the gateway.
  * every identifier passes its own checksum (СНИЛС mod-101, ИНН weights, card
    Luhn), or the ground truth claims a document that is not one and a
    checksum-gated detector is scored as wrong for being right.
  * foreign names appear at EVERY difficulty. A shop's foreign customers are not
    an edge case, they are Tuesday, and hiding them in `adversarial` lets a
    summary number look healthy while the population it fails on is ordinary.

CHANGED, and each change is a v1 defect rather than a preference:

  1. `msg` indexes ALL messages. v1's `turn` indexed user turns, so the second
     user message of a dialogue was turn 1 and message 2. Nothing in v1 could
     address anything else; here the number is the message index.
  2. `ExpectedCall.arguments` carries the SAME value the round trip demands —
     `item.canonical`. v1 fixed the «demand back what was written» rule in the
     pii items and left the old full-identity form in `expected_call`, so one
     argument had two contradictory ground truths: the chat message wrote
     «кузнецов дмитрий» and the call demanded «Кузнецов Дмитрий Андреевич».
  3. `send_invoice` carries a TWELVE-digit ИНН. A ten-digit ИНН identifies an
     organisation, and an organisation is not a subject of personal data — 152-ФЗ
     defines the subject as a natural person, and `bench/eval_piibench.py`
     already prints two headline numbers over exactly this. A twelve-digit ИНН
     belongs to a physical person (ИП included), so the type survives in the
     inventory and the label stops claiming something the law does not.
  4. The dialogue scenarios state their identity claims with
     `LinkExpectation` instead of by omission. `split_name_bare` in particular
     was «no identity», which reads identically in JSON to «an identity we
     deliberately do not demand»; it is `unjudged` now, in writing.
  5. `duty`. One `optional` item exists here — a street named as a landmark with
     no house number, which identifies nobody (hundreds of buildings stand on it)
     and is therefore neither a leak when missed nor an error when masked.

THE VOICE REGISTER, AND THE PART DELIBERATELY LEFT ALONE. v1 had one `voice`
register built on the sentence «modern ASR normalises digits». That was belief,
not measurement, and `schema.py` records the measurement that refutes it: zero of
12 950 human transcripts of real Russian calls contain a digit. v1's register is
carried UNCHANGED as `voice_itn` — commercial ASR does ship inverse text
normalisation and does emit «+7 916…», so the register is real, it was merely
mislabelled as the only one. `voice_raw` here is a synthetic approximation of
verbatim speech: numbers in words, no digits, no punctuation. It is NOT evidence
about what real ASR emits, and it does not pretend to be — that evidence is the
`speech` family, which is built from hand-annotated transcripts of real calls.
This family's job is to say what happens to a KNOWN datum spoken aloud; the
speech family's job is to say what a real call actually contains.

INDEPENDENCE. Every template, pool and negative here is authored from the domain
— what a Russian support conversation contains — never from a list of what our
detector finds. Overlap with the leased gazetteer is unavoidable (Russian names
are Russian names); nothing is here BECAUSE we detect it.
"""

import random
from dataclasses import dataclass

from bench.agentpii2.schema import (
    DIFFICULTIES,
    REGISTERS,
    Case,
    ExpectedCall,
    LinkExpectation,
    Negative,
    PiiItem,
    message_text,
)

FAMILY = "transfer"

# --- source pools ---------------------------------------------------------
#
# Ported from v1 `registers.py`. The foreign pool is deliberately hostile to
# suffix rules: no -ов/-ев/-ин, several non-Slavic, because a rule that reaches
# names through a suffix reports a healthy number and fails the customers a
# Russian shop actually has.

MALE: tuple[tuple[str, str, str], ...] = (
    ("Иванов", "Пётр", "Сергеевич"), ("Соколов", "Игорь", "Валентинович"),
    ("Кузнецов", "Дмитрий", "Андреевич"), ("Морозов", "Алексей", "Николаевич"),
    ("Волков", "Сергей", "Павлович"), ("Лебедев", "Максим", "Олегович"),
    ("Новиков", "Артём", "Витальевич"), ("Фёдоров", "Кирилл", "Романович"),
    ("Григорьев", "Никита", "Львович"), ("Захаров", "Владислав", "Юрьевич"),
)
FEMALE: tuple[tuple[str, str, str], ...] = (
    ("Иванова", "Мария", "Львовна"), ("Соколова", "Анна", "Игоревна"),
    ("Кузнецова", "Ольга", "Дмитриевна"), ("Морозова", "Екатерина", "Сергеевна"),
    ("Волкова", "Татьяна", "Ивановна"), ("Лебедева", "Ирина", "Петровна"),
    ("Новикова", "Светлана", "Юрьевна"), ("Фёдорова", "Юлия", "Андреевна"),
)
FOREIGN: tuple[tuple[str, str, str], ...] = (
    ("Ким", "Виктор", ""), ("Тагиев", "Рустам", ""), ("Мкртчян", "Ашот", ""),
    ("Шевчук", "Олесь", ""), ("Гулиев", "Эльдар", ""), ("Абдуллаев", "Тимур", ""),
    ("Саркисян", "Карен", ""), ("Нгуен", "Ань", ""), ("Мамедова", "Лейла", ""),
    ("Валиахметов", "Ильдар", ""), ("Джонсон", "Майкл", ""), ("Ли", "Чен", ""),
)

# The dative of every given name above, written out rather than derived. Russian
# given names have irregulars («Пётр» → «Петру», not «Пётру») and indeclinables
# («Ань»), and a rule that gets one wrong puts a form nobody writes into the
# GROUND TRUTH, where it is scored as if it were real Russian. A table is
# checkable by a native speaker in ten seconds; a rule is not.
DATIVE: dict[str, str] = {
    "Пётр": "Петру", "Игорь": "Игорю", "Дмитрий": "Дмитрию",
    "Алексей": "Алексею", "Сергей": "Сергею", "Максим": "Максиму",
    "Артём": "Артёму", "Кирилл": "Кириллу", "Никита": "Никите",
    "Владислав": "Владиславу", "Мария": "Марии", "Анна": "Анне",
    "Ольга": "Ольге", "Екатерина": "Екатерине", "Татьяна": "Татьяне",
    "Ирина": "Ирине", "Светлана": "Светлане", "Юлия": "Юлии",
    "Виктор": "Виктору", "Рустам": "Рустаму", "Ашот": "Ашоту",
    "Олесь": "Олесю", "Эльдар": "Эльдару", "Тимур": "Тимуру",
    "Карен": "Карену", "Ань": "Ань", "Лейла": "Лейле",
    "Ильдар": "Ильдару", "Майкл": "Майклу", "Чен": "Чену",
}

STREETS: tuple[str, ...] = (
    "Ленинский проспект", "улица Тверская", "проспект Мира", "улица Пушкина",
    "Кутузовский проспект", "улица Гагарина", "Профсоюзная улица",
    "улица Строителей", "переулок Сивцев Вражек", "бульвар Энтузиастов",
)
CITIES: tuple[str, ...] = (
    "Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск",
    "Нижний Новгород", "Краснодар", "Самара",
)
ORDER_PREFIXES: tuple[str, ...] = ("A-", "№", "ORD-", "Z", "")

# Spoken forms of the order prefix, for `voice_raw`. «№» is read as a word, and a
# Latin prefix is read letter by letter — which is what the transcript carries.
_PREFIX_SPOKEN: dict[str, str] = {
    "A-": "а", "№": "номер", "ORD-": "о эр дэ", "Z": "зет", "": "",
}

# A mailbox and a domain have a spoken form and a written one, and they are not
# derivable from each other: «acme.ru» is read «акме точка ру» by a Russian
# speaker and no transliteration rule we could write produces that reliably.
_MAILBOXES: tuple[tuple[str, str], ...] = (
    ("info", "инфо"), ("buh", "бух"), ("office", "офис"), ("zakaz", "заказ"),
)
_DOMAINS: tuple[tuple[str, str], ...] = (
    ("acme.ru", "акме точка ру"), ("romashka.ru", "ромашка точка ру"),
    ("torgdom.ru", "торгдом точка ру"),
)

# The twelve letters a Russian plate may carry (those that look the same in Latin
# and Cyrillic), with how each is said aloud.
_PLATE_LETTERS = "АВЕКМНОРСТУХ"
_PLATE_SPOKEN: dict[str, str] = {
    "А": "а", "В": "вэ", "Е": "е", "К": "ка", "М": "эм", "Н": "эн",
    "О": "о", "Р": "эр", "С": "эс", "Т": "тэ", "У": "у", "Х": "ха",
}


# --- numbers in words, for `voice_raw` ------------------------------------
#
# Needed because the register is defined by the ABSENCE of digits, and the
# schema's register gate enforces it. Everything below is a table or a fold over
# a table: a native speaker can check it, which a rule producing «одна тысяч» or
# «двадцать первого» from arithmetic cannot be.

_UNITS_M: tuple[str, ...] = (
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять",
)
_UNITS_F: tuple[str, ...] = (
    "ноль", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять",
)
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS: tuple[str, ...] = (
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто",
)
_HUNDREDS: tuple[str, ...] = (
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
    "семьсот", "восемьсот", "девятьсот",
)
_ORD_DAY: tuple[str, ...] = (
    "", "первого", "второго", "третьего", "четвёртого", "пятого", "шестого",
    "седьмого", "восьмого", "девятого", "десятого", "одиннадцатого",
    "двенадцатого", "тринадцатого", "четырнадцатого", "пятнадцатого",
    "шестнадцатого", "семнадцатого", "восемнадцатого", "девятнадцатого",
    "двадцатого",
)
_MONTHS_GEN: tuple[str, ...] = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня", "июля",
    "августа", "сентября", "октября", "ноября", "декабря",
)


def _below_thousand(value: int, feminine: bool) -> str:
    """0-999 in words. `feminine` exists for «одна тысяча» and «две тысячи»."""
    if value == 0:
        return "ноль"
    words: list[str] = []
    if value >= 100:
        words.append(_HUNDREDS[value // 100])
        value %= 100
    if 10 <= value < 20:
        words.append(_TEENS[value - 10])
        value = 0
    elif value >= 20:
        words.append(_TENS[value // 10])
        value %= 10
    if value:
        words.append(_UNITS_F[value] if feminine else _UNITS_M[value])
    return " ".join(words)


def _thousand_noun(count: int) -> str:
    if count % 100 in (11, 12, 13, 14):
        return "тысяч"
    last = count % 10
    if last == 1:
        return "тысяча"
    if last in (2, 3, 4):
        return "тысячи"
    return "тысяч"


def _amount_words(value: int) -> str:
    """A sum of money as it is said. «одна тысяча» is dropped to «тысяча»,
    because nobody says the first word and the ground truth is what was said."""
    if value < 1000:
        return _below_thousand(value, False)
    thousands, rest = divmod(value, 1000)
    head = ("тысяча" if thousands == 1
            else f"{_below_thousand(thousands, True)} {_thousand_noun(thousands)}")
    return head if not rest else f"{head} {_below_thousand(rest, False)}"


def _group_words(group: str) -> str:
    """One group of a dictated number, e.g. a phone's «916» or «03».

    A LEADING ZERO IS SPOKEN, one «ноль» per zero, and the rest is a numeral:
    «03» is «ноль три» and «007» is «ноль ноль семь». Reading the group as
    `int(group)` would silently delete the zeros, and a phone that lost a digit
    is a phone the round trip can never repair.
    """
    stripped = group.lstrip("0")
    zeros = ["ноль"] * (len(group) - len(stripped))
    if not stripped:
        return " ".join(zeros)
    return " ".join(zeros + [_below_thousand(int(stripped), False)])


def _digit_words(digits: str) -> str:
    """Digit by digit — how a document number is dictated over the phone.

    Grouped readings exist («сорок пять восемнадцать») and differ between
    speakers, between document types and between call centres. Digit by digit is
    the one an operator asks for, it is unambiguous, and it needs no gender or
    case table per group — which is where an invented reading would put forms
    nobody says into the ground truth.
    """
    return " ".join(_UNITS_M[int(digit)] for digit in digits)


def _date_words(day: int, month: int) -> str:
    """«пятнадцатого мая». The year is dropped because speech drops it."""
    ordinal = _ORD_DAY[day] if day <= 20 else f"двадцать {_ORD_DAY[day - 20]}"
    return f"{ordinal} {_MONTHS_GEN[month]}"


# --- checksums ------------------------------------------------------------
#
# Identifiers in the corpus must be VALID, or the ground truth claims a document
# that is not one and a checksum-gated detector is scored as wrong for being
# right. The algorithms are published; using the same ones the engine validates
# with is unavoidable and harmless — a checksum has exactly one definition, so
# this is not the corpus reading the detector.

def _digits(rng: random.Random, count: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(count))


def _snils(rng: random.Random) -> str:
    body = _digits(rng, 9)
    total = sum(int(digit) * (9 - index) for index, digit in enumerate(body))
    if total in (100, 101):
        check = 0
    elif total > 101:
        total %= 101
        check = 0 if total in (100, 101) else total
    else:
        check = total
    return body + f"{check:02d}"


def _inn12(rng: random.Random) -> str:
    """A PHYSICAL person's ИНН — twelve digits, two check digits.

    Ten digits would be an organisation's, and an organisation is not a subject
    of personal data: 152-ФЗ defines the subject as a natural person and Recital
    14 puts the GDPR in the same place. v1 labelled a ten-digit ИНН as personal
    data and the corpus therefore demanded a mask the law does not.
    """
    body = _digits(rng, 10)
    eleventh = sum(int(d) * w for d, w in
                   zip(body, (7, 2, 4, 10, 3, 5, 9, 4, 6, 8))) % 11 % 10
    twelfth = sum(int(d) * w for d, w in
                  zip(body + str(eleventh),
                      (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))) % 11 % 10
    return f"{body}{eleventh}{twelfth}"


def _card(rng: random.Random) -> str:
    body = "4" + _digits(rng, 14)
    total = 0
    for index, digit in enumerate(reversed(body)):
        value = int(digit)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return body + str((10 - total % 10) % 10)


def _phone_digits(rng: random.Random) -> str:
    return rng.choice(("916", "926", "903", "985", "917")) + _digits(rng, 7)


# --- the sloppy register --------------------------------------------------
#
# MEASURED, not invented. v1's first version applied one error type — a Latin
# letter typed inside a Cyrillic word — chosen because it is vivid and defeats a
# Cyrillic-only matcher. Then RuSpellGold (RussianNLP, Apache 2.0, 1711
# human-corrected pairs) was counted, and that error barely appears. What
# Russians actually produce, over 2112 corrections:
#
#     замена одной буквы   950   ё->е 499 of them, then а->о, и->е, о->а, е->и
#     пропущенная буква    626   с, н, е, т, ь most often
#     лишний символ        463   mostly a stray space or comma
#
# The commonest is not a typo at all: «ё» written as «е» is ordinary Russian
# practice and it lands directly on names — Пётр, Фёдоров, Алёна, Семён. The
# layout slip stays in as the minority it is: RuSpellGold's sources are edited
# text, where a layout slip is corrected before publication, and no public corpus
# of Russian keyboard-layout errors exists to settle its true weight.
_PHONETIC_SUBS: tuple[tuple[str, str], ...] = (
    ("ё", "е"), ("ё", "е"), ("ё", "е"),
    ("а", "о"), ("и", "е"), ("о", "а"), ("е", "и"), ("ъ", "ь"),
    ("о", "у"), ("и", "ы"), ("я", "и"), ("т", "д"), ("з", "с"),
)
_LATIN_TWINS: dict[str, str] = {
    "о": "o", "а": "a", "е": "e", "с": "c", "р": "p", "у": "y", "х": "x",
    "О": "O", "А": "A", "Е": "E", "С": "C", "Р": "P",
}


def _substitute_letter(text: str, rng: random.Random) -> str:
    for source, target in rng.sample(_PHONETIC_SUBS, len(_PHONETIC_SUBS)):
        positions = [i for i, char in enumerate(text) if char.lower() == source]
        if not positions:
            continue
        index = rng.choice(positions)
        replacement = target.upper() if text[index].isupper() else target
        return text[:index] + replacement + text[index + 1:]
    return text


def _drop_letter(text: str, rng: random.Random) -> str:
    # Never the first character: a dropped initial changes the word so much that
    # the case stops being about a typo and becomes a different word.
    positions = [i for i, char in enumerate(text) if char.isalpha() and i > 0]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + text[index + 1:]


def _stray_space(text: str, rng: random.Random) -> str:
    positions = [i for i, char in enumerate(text) if char == " "]
    if positions and rng.random() < 0.5:
        index = rng.choice(positions)          # a space that got lost
        return text[:index] + text[index + 1:]
    inner = [i for i in range(2, len(text) - 2) if text[i].isalpha()]
    if not inner:
        return text
    index = rng.choice(inner)                  # one that should not be there
    return text[:index] + " " + text[index:]


def _layout_slip(text: str, rng: random.Random) -> str:
    positions = [i for i, char in enumerate(text) if char in _LATIN_TWINS]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + _LATIN_TWINS[text[index]] + text[index + 1:]


def _one_writing_error(text: str, rng: random.Random) -> str:
    """One realistic writing error, drawn from the measured distribution."""
    roll = rng.random()
    if roll < 0.45:
        return _substitute_letter(text, rng)
    if roll < 0.75:
        return _drop_letter(text, rng)
    if roll < 0.90:
        return _stray_space(text, rng)
    return _layout_slip(text, rng)


# --- per-register rendering ----------------------------------------------

def _render_name(surname: str, first: str, patronymic: str, register: str,
                 rng: random.Random) -> str:
    if register == "clean":
        return " ".join(part for part in (surname, first, patronymic) if part)
    if register == "chat":
        # The patronymic is the first thing a messenger drops, and the capitals
        # go with it. A detector needing «Иванов Пётр Сергеевич» sees nothing.
        name = f"{surname} {first}" if rng.random() < 0.6 else f"{first} {surname}"
        return name.lower()
    if register == "sloppy":
        return _one_writing_error(f"{surname} {first}", rng)
    # Both voice registers: ASR keeps the words and drops the capitals, and the
    # speaker often gave only a first name. Nothing numeric is involved, so the
    # two halves of the split agree here — which is the point of splitting on
    # digits rather than on channel.
    if rng.random() < 0.3:
        return first.lower()
    return f"{first} {surname}".lower()


def _render_phone(digits: str, register: str, rng: random.Random) -> str:
    """`digits` is ten digits with no country code."""
    a, b, c, d = digits[:3], digits[3:6], digits[6:8], digits[8:]
    if register == "clean":
        return f"+7 {a} {b}-{c}-{d}"
    if register == "chat":
        return rng.choice([f"8{digits}", f"+7{digits}", f"8 {a} {b} {c} {d}"])
    if register == "sloppy":
        # A Cyrillic О typed where a zero belongs is the commonest obfuscation
        # that is not one — it is a keyboard slip, and normalisation folds it.
        formatted = f"8-{a}-{b}-{c}-{d}"
        return formatted.replace("0", "О", 1) if "0" in formatted else formatted
    if register == "voice_itn":
        return f"8 {a} {b} {c} {d}"
    return " ".join(["восемь", _group_words(a), _group_words(b),
                     _group_words(c), _group_words(d)])


def _render_address(city: str, street: str, house: int, flat: int,
                    register: str, rng: random.Random) -> str:
    if register == "clean":
        return f"{city}, {street}, д. {house}, кв. {flat}"
    if register == "chat":
        # City dropped: in a shop's own chat the city is assumed.
        return f"{street.lower()} {house} кв {flat}"
    if register == "sloppy":
        return _one_writing_error(f"{street} {house}кв{flat}", rng)
    if register == "voice_itn":
        return f"{street.lower()} {house} квартира {flat}"
    return (f"{street.lower()} дом {_below_thousand(house, False)} "
            f"квартира {_below_thousand(flat, False)}")


def _render_passport(series: str, number: str, register: str) -> str:
    if register in ("chat", "sloppy"):
        return f"{series}{number}"
    if register == "voice_raw":
        return _digit_words(series + number)
    return f"{series} {number}"


def _render_snils(digits: str, register: str) -> str:
    if register == "clean":
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
    if register == "voice_raw":
        return _digit_words(digits)
    return digits


def _render_card(digits: str, register: str) -> str:
    if register == "clean":
        return " ".join(digits[i:i + 4] for i in range(0, 16, 4))
    if register == "voice_raw":
        return _digit_words(digits)
    return digits


def _render_inn(digits: str, register: str) -> str:
    if register == "voice_raw":
        return _digit_words(digits)
    return digits


def _render_email(mailbox: tuple[str, str], domain: tuple[str, str],
                  suffix: str, register: str) -> str:
    # The spoken form carries no digits in the mailbox: a person dictating an
    # address says «инфо собака ромашка точка ру», and inventing digits there
    # would be inventing a habit to make the register look harder.
    if register == "voice_raw":
        return f"{mailbox[1]} собака {domain[1]}"
    return f"{mailbox[0]}{suffix}@{domain[0]}"


def _render_order(prefix: str, digits: str, register: str) -> str:
    if register != "voice_raw":
        return f"{prefix}{digits}"
    spoken = _PREFIX_SPOKEN[prefix]
    body = _digit_words(digits)
    return f"{spoken} {body}" if spoken else body


def _render_plate(letters: str, digits: str, region: str, register: str) -> str:
    if register != "voice_raw":
        return f"{letters[0]}{digits}{letters[1:]}{region}"
    return " ".join([_PLATE_SPOKEN[letters[0]], _group_words(digits),
                     _PLATE_SPOKEN[letters[1]], _PLATE_SPOKEN[letters[2]],
                     _group_words(region)])


def _render_date(day: int, month: int, register: str) -> str:
    if register == "voice_raw":
        return _date_words(day, month)
    return f"{day:02d}.{month:02d}.2025"


def _render_number(value: str, register: str) -> str:
    """A bare non-personal number — a ticket, a contract, a build."""
    return _digit_words(value) if register == "voice_raw" else value


def _render_amount(value: int, register: str) -> str:
    return _amount_words(value) if register == "voice_raw" else str(value)


# --- assembly -------------------------------------------------------------

def _assemble(parts: list[object]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Build a message and the offsets of its tracked slots in ONE pass.

    A plain `str` is literal text; a `(name, value)` tuple is a slot whose span is
    recorded. Computing offsets during assembly rather than by searching the
    finished string is what keeps the ground truth honest: a search finds the
    FIRST occurrence, and a message mentioning the same phone twice would then
    carry a span pointing at the wrong one.

    There is deliberately NO post-processing pass afterwards. An earlier version
    stripped punctuation after assembly, which changes the string length and
    silently invalidates every span computed before it — a corpus whose ground
    truth points a few characters to the left still scores, and scores wrongly.
    """
    out: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for part in parts:
        if isinstance(part, tuple):
            name, value = part
            spans[name] = (cursor, cursor + len(value))
            out.append(value)
            cursor += len(value)
        else:
            text = str(part)
            out.append(text)
            cursor += len(text)
    return "".join(out), spans


def _item(item_id: str, kind: str, text: str,
          spans: dict[str, tuple[int, int]], slot: str, canonical: str,
          param: str | None, msg: int, identity: str, duty: str) -> PiiItem:
    start, end = spans[slot]
    return PiiItem(id=item_id, type=kind, value=text[start:end], start=start,
                   end=end, canonical=canonical, msg=msg, identity=identity,
                   duty=duty, tool_param=param)


# --- tool schemas ---------------------------------------------------------
#
# The part no other benchmark has: schemas whose ARGUMENT is a Russian passport
# number that must arrive intact at a system which will reject a malformed one.
# BFCL's tools move files; tau-bench's book flights with synthetic English names.
#
# Plain OpenAI function-calling JSON, so the corpus replays against any provider
# with no translation layer and a competing gateway is scored on it without
# adopting anything of ours.

def _tool(name: str, description: str, params: dict[str, tuple[str, str]],
          required: list[str]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": kind, "description": text}
                    for key, (kind, text) in params.items()
                },
                "required": required,
            },
        },
    }


_TOOLS: dict[str, dict[str, object]] = {
    "create_order": _tool(
        "create_order",
        "Оформить заказ на клиента и отправить его в доставку.",
        {"customer_name": ("string", "ФИО получателя как в паспорте"),
         "phone": ("string", "Контактный телефон получателя"),
         "address": ("string", "Адрес доставки с домом и квартирой"),
         "items": ("string", "Артикулы товаров через запятую")},
        ["customer_name", "phone", "address"]),
    "book_appointment": _tool(
        "book_appointment",
        "Записать клиента на приём в выбранный филиал.",
        {"client_name": ("string", "ФИО клиента"),
         "phone": ("string", "Телефон для подтверждения записи"),
         "birth_date": ("string", "Дата рождения в формате ДД.ММ.ГГГГ"),
         "service": ("string", "Название услуги")},
        ["client_name", "phone"]),
    "check_order_status": _tool(
        "check_order_status",
        "Узнать статус заказа по его номеру и телефону покупателя.",
        {"order_id": ("string", "Номер заказа, например A-4471"),
         "phone": ("string", "Телефон, указанный при оформлении")},
        ["order_id", "phone"]),
    "update_delivery_address": _tool(
        "update_delivery_address",
        "Изменить адрес доставки у существующего заказа.",
        {"order_id": ("string", "Номер заказа"),
         "address": ("string", "Новый адрес с домом и квартирой"),
         "recipient_name": ("string", "ФИО получателя, если он меняется")},
        ["order_id", "address"]),
    "verify_identity": _tool(
        "verify_identity",
        "Проверить личность клиента по документам перед выдачей займа.",
        {"full_name": ("string", "ФИО полностью"),
         "passport": ("string", "Серия и номер паспорта РФ"),
         "snils": ("string", "Номер СНИЛС"),
         "inn": ("string", "ИНН физического лица")},
        ["full_name", "passport"]),
    "issue_refund": _tool(
        "issue_refund",
        "Вернуть деньги на карту, с которой была оплата.",
        {"card_number": ("string", "Номер карты для возврата"),
         "amount": ("number", "Сумма возврата в рублях"),
         "customer_name": ("string", "ФИО держателя карты")},
        ["card_number", "amount"]),
    "register_vehicle": _tool(
        "register_vehicle",
        "Записать автомобиль на сервисное обслуживание.",
        {"plate": ("string", "Государственный регистрационный номер"),
         "vin": ("string", "VIN автомобиля, 17 символов"),
         "owner_name": ("string", "ФИО владельца"),
         "owner_phone": ("string", "Телефон владельца")},
        ["plate", "owner_phone"]),
    "send_invoice": _tool(
        "send_invoice",
        "Выставить счёт индивидуальному предпринимателю и отправить на почту.",
        {"email": ("string", "Электронная почта для отправки счёта"),
         "inn": ("string", "ИНН плательщика — физического лица или ИП"),
         "company_name": ("string", "Наименование плательщика"),
         "amount": ("number", "Сумма счёта в рублях")},
        ["email", "inn", "amount"]),
    "add_contact": _tool(
        "add_contact",
        "Добавить контакт в CRM.",
        {"name": ("string", "ФИО контакта"),
         "phone": ("string", "Телефон"),
         "email": ("string", "Электронная почта")},
        ["name", "phone"]),
    "escalate_ticket": _tool(
        "escalate_ticket",
        "Передать обращение старшему специалисту с контактами клиента.",
        {"customer_name": ("string", "ФИО клиента"),
         "phone": ("string", "Телефон для обратной связи"),
         "summary": ("string", "Краткое описание проблемы")},
        ["customer_name", "phone", "summary"]),
}

_TOOL_ORDER: tuple[str, ...] = tuple(_TOOLS)


def _tools_for(primary: str) -> list[dict[str, object]]:
    """The offered tool set: the right tool and two distractors.

    Always more than one. A single-tool prompt lets a model succeed by having
    nowhere else to go, which hides whether masking damaged its ability to
    CHOOSE — and choosing is where an implausible substitute does its damage.

    The distractors ROTATE with the primary's position rather than being the
    first two names in the table, as v1 took them. Constant distractors are a
    constant confound on the transparency axis: whatever the model does with
    `create_order` in the menu, it does in every case.
    """
    others = [name for name in _TOOL_ORDER if name != primary]
    start = _TOOL_ORDER.index(primary)
    picked = [others[(start + offset) % len(others)] for offset in (0, 1)]
    return [_TOOLS[primary]] + [_TOOLS[name] for name in picked]


# --- difficulty -----------------------------------------------------------
#
# WHAT V1 ACTUALLY ENCODED, said plainly: difficulty was a weight on the foreign
# name pool and nothing else — the templates for `easy`, `hard` and
# `adversarial` were identical strings. That is marked here rather than
# silently redefined, because a difficulty axis rebuilt from scratch would make
# v1's per-difficulty numbers and v2's incomparable for reasons that have nothing
# to do with the gateway.
#
# What is added is the smallest thing that makes the labels mean what the schema
# says they mean: a TAIL clause, appended before assembly so no span moves.
#
#   easy         no tail. v1's template, untouched.
#   hard         an adjacent non-PII document number — the shape that makes a
#                detector answer «number near a person, therefore personal».
#   adversarial  one trap out of ordinary Russian business writing: a document
#                date, a floor area, a company as payer. None of the three is
#                personal data and all three are commonplace; they are authored
#                from what such a message contains, not from a list of our own
#                known false positives.
#
# `dwelling` says whether the scenario is already talking about somebody's flat.
# The floor-area trap is only drawn where it is, because «Где мой заказ? Площадь
# квартиры 90 кв.м» is not a sentence anybody writes, and a corpus that reads as
# nonsense stops being evidence about real traffic no matter how the spans line
# up. The other two traps fit any support message.

def _tail(rng: random.Random, register: str, difficulty: str,
          dwelling: bool) -> tuple[list[object], list[tuple[str, str]]]:
    if difficulty == "easy":
        return [], []
    if difficulty == "hard":
        ticket = _render_number(_digits(rng, 4), register)
        if register == "clean":
            return [" Заявка ", ticket, ", две позиции."], [
                (ticket, "номер заявки")]
        return [" заявка ", ticket, " две позиции"], [(ticket, "номер заявки")]
    return _adversarial_tail(rng, register, dwelling)


def _adversarial_tail(rng: random.Random, register: str,
                      dwelling: bool) -> tuple[list[object], list[tuple[str, str]]]:
    trap = rng.randrange(3 if dwelling else 2)
    if trap == 0:
        date = _render_date(rng.randrange(1, 28), rng.randrange(1, 13), register)
        why = "дата документа, не дата рождения"
        if register == "clean":
            return [" Счёт от ", date, " уже оплачен."], [(date, why)]
        return [" счет от ", date, " уже оплачен"], [(date, why)]
    if trap == 1:
        # NO NAME FROM `_DOMAINS` HERE. «Ромашка» stood in this pool and in
        # `romashka.ru`, so in `voice_raw` — where the address is spoken as
        # «заказ собака ромашка точка ру» — the negative was a substring of a
        # labelled email every ninth draw. The redraw guard caught it; a pool
        # that cannot collide means it never has to.
        company = rng.choice(("Заря", "Вектор", "Оптима"))
        why = "юрлицо, а не физическое лицо"
        if register == "clean":
            return [" Плательщик — ООО «", company, "»."], [(company, why)]
        return [" платит ооо ", company.lower()], [(company.lower(), why)]
    size = rng.randrange(28, 96)
    why = "площадь, не номер"
    if register == "voice_raw":
        area = f"{_below_thousand(size, False)} квадратных метров"
        return [" площадь квартиры ", area], [(area, why)]
    metres = f"{size} кв.м"
    if register == "clean":
        return [" Площадь квартиры ", metres, "."], [(metres, why)]
    return [" площадь квартиры ", metres], [(metres, why)]


# --- scenario helpers -----------------------------------------------------

def _person(rng: random.Random, difficulty: str) -> tuple[str, str, str]:
    """Foreign names at EVERY difficulty, not only the hard one.

    A shop's foreign customers are not an adversarial case — they are Tuesday.
    Hiding them in `adversarial` would let a summary number look healthy while
    the population it fails on is ordinary. Measured on NEREL, our recall on
    Russian names sat at 81% and nearly every miss was foreign.
    """
    pool = MALE + FEMALE
    weight = 0.4 if difficulty == "adversarial" else 0.2
    if rng.random() < weight:
        pool = FOREIGN
    return rng.choice(pool)


def _order(rng: random.Random, register: str) -> str:
    return _render_order(rng.choice(ORDER_PREFIXES), _digits(rng, 4), register)


@dataclass(frozen=True)
class _Built:
    """What a scenario builder returns before it becomes a `Case`.

    Data, in the same shape the schema states its own data: six values that
    would otherwise be a six-tuple read positionally by everyone who touches it.
    """

    messages: list[dict[str, object]]
    pii: list[PiiItem]
    negatives: list[Negative]
    links: list[LinkExpectation]
    calls: list[ExpectedCall]
    tool: str


def _negatives(pairs: list[tuple[str, str]], msg: int) -> list[Negative]:
    return [Negative(value=value, why=why, msg=msg) for value, why in pairs]


# --- scenarios: one user message, one call --------------------------------

def _create_order(rng: random.Random, register: str, difficulty: str) -> _Built:
    surname, first, patronymic = _person(rng, difficulty)
    name = _render_name(surname, first, patronymic, register, rng)
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)
    city, street = rng.choice(CITIES), rng.choice(STREETS)
    house, flat = rng.randrange(1, 90), rng.randrange(1, 250)
    address = _render_address(city, street, house, flat, register, rng)
    order = _order(rng, register)

    if register == "clean":
        parts: list[object] = [
            "Оформите, пожалуйста, заказ ", order, " на ", ("name", name),
            ", телефон ", ("phone", phone), ", адрес доставки: ",
            ("address", address), "."]
    elif register == "chat":
        parts = ["оформите заказ ", order, " на ", ("name", name), " тел ",
                 ("phone", phone), " адрес ", ("address", address)]
    elif register == "sloppy":
        parts = ["заказ ", order, " оформите на ", ("name", name), ", т ",
                 ("phone", phone), ", ", ("address", address)]
    else:
        parts = ["так значит заказ ", order, " на ", ("name", name),
                 " телефон ", ("phone", phone), " адрес ", ("address", address)]

    # A STREET WITH NO HOUSE NUMBER, named as a landmark. It identifies nobody —
    # hundreds of buildings stand on it, one step more specific than the city
    # that 152-ФЗ ст. 3 п. 1 already leaves outside — so masking it is not an
    # error and missing it is not a leak. `duty = optional`, and it may claim no
    # tool param: a value the round trip demands back cannot also be one we did
    # not require masked.
    landmark = ""
    if difficulty == "adversarial":
        landmark = rng.choice([s for s in STREETS if s != street])
        if register == "clean":
            parts += [" Ориентир — ", ("landmark", landmark), "."]
        else:
            parts += [" ориентир ", ("landmark", landmark.lower())]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, True)
    text, spans = _assemble(parts + tail_parts)

    items = [
        _item("name", "NAME", text, spans, "name", name, "customer_name", 0,
              "customer", "required"),
        _item("phone", "PHONE", text, spans, "phone", f"+7{phone_digits}"
              if register != "voice_raw" else phone, "phone", 0,
              "customer_phone", "required"),
        _item("address", "LOC", text, spans, "address", address, "address", 0,
              "delivery", "required"),
    ]
    if landmark:
        items.append(_item("landmark", "LOC", text, spans, "landmark",
                           text[slice(*spans["landmark"])], None, 0,
                           "landmark", "optional"))
    call = ExpectedCall(
        name="create_order", after_msg=0,
        arguments={"customer_name": items[0].canonical,
                   "phone": items[1].canonical,
                   "address": items[2].canonical},
        pii_items=["name", "phone", "address"])
    return _Built(messages=[{"role": "user", "content": text}], pii=items,
                  negatives=_negatives([(order, "номер заказа")] + tail_negatives, 0),
                  links=[], calls=[call], tool="create_order")


def _check_order_status(rng: random.Random, register: str,
                        difficulty: str) -> _Built:
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)
    order = _order(rng, register)
    track = _render_number(_digits(rng, 14), register)

    if register == "clean":
        parts: list[object] = [
            "Здравствуйте! Где мой заказ ", order, "? Трек-номер ", track,
            ", телефон при оформлении ", ("phone", phone), "."]
    elif register == "chat":
        parts = ["привет где заказ ", order, " трек ", track, " телефон ",
                 ("phone", phone)]
    elif register == "sloppy":
        parts = ["где заказ ", order, "?? трек ", track, " тлф ", ("phone", phone)]
    else:
        parts = ["здравствуйте я хотел узнать про заказ ", order, " трек номер ",
                 track, " мой телефон ", ("phone", phone)]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [_item("phone", "PHONE", text, spans, "phone",
                   f"+7{phone_digits}" if register != "voice_raw" else phone,
                   "phone", 0, "customer_phone", "required")]
    call = ExpectedCall(name="check_order_status", after_msg=0,
                        arguments={"order_id": order,
                                   "phone": items[0].canonical},
                        pii_items=["phone"])
    # A fourteen-digit track sits right beside an eleven-digit phone. This is the
    # pair that produced real false positives before the phone gate existed.
    return _Built(
        messages=[{"role": "user", "content": text}], pii=items,
        negatives=_negatives([(order, "номер заказа"), (track, "трек-номер")]
                             + tail_negatives, 0),
        links=[], calls=[call], tool="check_order_status")


def _verify_identity(rng: random.Random, register: str, difficulty: str) -> _Built:
    surname, first, patronymic = _person(rng, difficulty)
    name = _render_name(surname, first, patronymic, register, rng)
    series, number = _digits(rng, 4), _digits(rng, 6)
    passport = _render_passport(series, number, register)
    snils_digits = _snils(rng)
    snils = _render_snils(snils_digits, register)
    build_number = _render_number(_digits(rng, 6), register)

    if register == "clean":
        parts: list[object] = [
            "Клиент ", ("name", name), ", паспорт ", ("passport", passport),
            ", СНИЛС ", ("snils", snils), ". Версия анкеты ", build_number, "."]
    elif register == "chat":
        parts = ["клиент ", ("name", name), " паспорт ", ("passport", passport),
                 " снилс ", ("snils", snils), " анкета ", build_number]
    elif register == "sloppy":
        # A misspelt cue word disables the guard that word provides, and
        # «пасспорт» is what people type.
        parts = [("name", name), " пасспорт ", ("passport", passport), " снилс ",
                 ("snils", snils), " сборка ", build_number]
    else:
        parts = ["клиент ", ("name", name), " паспорт ", ("passport", passport),
                 " снилс ", ("snils", snils), " версия анкеты ", build_number]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [
        _item("name", "NAME", text, spans, "name", name, "full_name", 0,
              "client", "required"),
        _item("passport", "PASSPORT", text, spans, "passport",
              f"{series} {number}" if register != "voice_raw" else passport,
              "passport", 0, "client_passport", "required"),
        _item("snils", "SNILS", text, spans, "snils",
              snils_digits if register != "voice_raw" else snils, "snils", 0,
              "client_snils", "required"),
    ]
    call = ExpectedCall(name="verify_identity", after_msg=0,
                        arguments={"full_name": items[0].canonical,
                                   "passport": items[1].canonical,
                                   "snils": items[2].canonical},
                        pii_items=["name", "passport", "snils"])
    return _Built(
        messages=[{"role": "user", "content": text}], pii=items,
        negatives=_negatives([(build_number, "номер сборки анкеты")]
                             + tail_negatives, 0),
        links=[], calls=[call], tool="verify_identity")


def _issue_refund(rng: random.Random, register: str, difficulty: str) -> _Built:
    surname, first, patronymic = _person(rng, difficulty)
    name = _render_name(surname, first, patronymic, register, rng)
    card_digits = _card(rng)
    card = _render_card(card_digits, register)
    amount = rng.randrange(500, 40000)
    amount_text = _render_amount(amount, register)
    invoice = _render_number(_digits(rng, 4), register)

    if register == "clean":
        parts: list[object] = [
            "Верните ", amount_text, " рублей по счёту ", invoice, " на карту ",
            ("card", card), ", держатель ", ("name", name), "."]
    elif register == "chat":
        parts = ["верните ", amount_text, " по счёту ", invoice, " на карту ",
                 ("card", card), " держатель ", ("name", name)]
    elif register == "sloppy":
        parts = ["возврат ", amount_text, "р счет ", invoice, " карта ",
                 ("card", card), " ", ("name", name)]
    else:
        parts = ["верните пожалуйста ", amount_text, " рублей по счёту ", invoice,
                 " на карту ", ("card", card), " держатель ", ("name", name)]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [
        _item("card", "CARD", text, spans, "card",
              card_digits if register != "voice_raw" else card, "card_number", 0,
              "holder_card", "required"),
        _item("name", "NAME", text, spans, "name", name, "customer_name", 0,
              "holder", "required"),
    ]
    call = ExpectedCall(name="issue_refund", after_msg=0,
                        arguments={"card_number": items[0].canonical,
                                   "amount": amount,
                                   "customer_name": items[1].canonical},
                        pii_items=["card", "name"])
    return _Built(
        messages=[{"role": "user", "content": text}], pii=items,
        negatives=_negatives([(amount_text, "сумма"), (invoice, "номер счёта")]
                             + tail_negatives, 0),
        links=[], calls=[call], tool="issue_refund")


def _register_vehicle(rng: random.Random, register: str, difficulty: str) -> _Built:
    surname, first, patronymic = _person(rng, difficulty)
    name = _render_name(surname, first, patronymic, register, rng)
    letters = "".join(rng.choice(_PLATE_LETTERS) for _ in range(3))
    plate_digits, region = _digits(rng, 3), _digits(rng, 2)
    plate = _render_plate(letters, plate_digits, region, register)
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)
    doc_date = _render_date(rng.randrange(1, 28), rng.randrange(1, 13), register)

    if register == "clean":
        parts: list[object] = [
            "Запишите на сервис автомобиль ", ("plate", plate), ", владелец ",
            ("name", name), ", телефон ", ("phone", phone), ". Заказ-наряд от ",
            doc_date, "."]
    elif register == "chat":
        parts = ["запишите машину ", ("plate", plate), " владелец ", ("name", name),
                 " тел ", ("phone", phone), " наряд от ", doc_date]
    elif register == "sloppy":
        parts = ["машина ", ("plate", plate), " ", ("name", name), " ",
                 ("phone", phone), " наряд от ", doc_date]
    else:
        parts = ["запишите машину ", ("plate", plate), " владелец ", ("name", name),
                 " телефон ", ("phone", phone), " заказ наряд от ", doc_date]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [
        _item("plate", "PLATE", text, spans, "plate", plate, "plate", 0,
              "vehicle", "required"),
        _item("name", "NAME", text, spans, "name", name, "owner_name", 0,
              "owner", "required"),
        _item("phone", "PHONE", text, spans, "phone",
              f"+7{phone_digits}" if register != "voice_raw" else phone,
              "owner_phone", 0, "owner_phone", "required"),
    ]
    call = ExpectedCall(name="register_vehicle", after_msg=0,
                        arguments={"plate": items[0].canonical,
                                   "owner_name": items[1].canonical,
                                   "owner_phone": items[2].canonical},
                        pii_items=["plate", "name", "phone"])
    # A document date beside personal data: the shape that made every invoice
    # date look like a date of birth until the association gate existed.
    return _Built(
        messages=[{"role": "user", "content": text}], pii=items,
        negatives=_negatives([(doc_date, "дата заказ-наряда, не дата рождения")]
                             + tail_negatives, 0),
        links=[], calls=[call], tool="register_vehicle")


def _send_invoice(rng: random.Random, register: str, difficulty: str) -> _Built:
    inn_digits = _inn12(rng)
    inn = _render_inn(inn_digits, register)
    mailbox, domain = rng.choice(_MAILBOXES), rng.choice(_DOMAINS)
    email = _render_email(mailbox, domain, _digits(rng, 2), register)
    amount = rng.randrange(5000, 900000)
    amount_text = _render_amount(amount, register)
    contract = _render_number(_digits(rng, 4), register)

    if register == "clean":
        parts: list[object] = [
            "Выставьте счёт ИП по договору ", contract, " на сумму ", amount_text,
            " рублей, ИНН ", ("inn", inn), ", почта ", ("email", email), "."]
    elif register == "chat":
        parts = ["счет ип по договору ", contract, " на ", amount_text, " инн ",
                 ("inn", inn), " почта ", ("email", email)]
    elif register == "sloppy":
        # «догвор» — a misspelt cue word, and the cue is what types the number
        # standing next to it.
        parts = ["выставите счет ип догвор ", contract, " ", amount_text, "р инн ",
                 ("inn", inn), " ", ("email", email)]
    else:
        parts = ["выставьте счёт ип по договору ", contract, " на сумму ",
                 amount_text, " рублей инн ", ("inn", inn), " почта ",
                 ("email", email)]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [
        _item("inn", "INN", text, spans, "inn",
              inn_digits if register != "voice_raw" else inn, "inn", 0,
              "payer_inn", "required"),
        _item("email", "EMAIL", text, spans, "email", email, "email", 0,
              "payer_email", "required"),
    ]
    call = ExpectedCall(name="send_invoice", after_msg=0,
                        arguments={"inn": items[0].canonical,
                                   "email": items[1].canonical,
                                   "amount": amount},
                        pii_items=["inn", "email"])
    return _Built(
        messages=[{"role": "user", "content": text}], pii=items,
        negatives=_negatives([(contract, "номер договора"), (amount_text, "сумма")]
                             + tail_negatives, 0),
        links=[], calls=[call], tool="send_invoice")


# --- scenarios: a conversation, for the consistency axis -------------------
#
# Support is a CONVERSATION. The same customer is named in the first message and
# referred to again two turns later in a shorter form — «Иванов Пётр Сергеевич»,
# then «Петру». The product's own claim is that both receive the same substitute
# and that a second person in the same message receives a different one.
#
# THESE FOUR CARRY NO `ExpectedCall`, exactly as v1 carried no `expected_call`
# for them. The text asks for something a single tool in the offered set cannot
# satisfy («оформите заказ … и перезвоните после шести»), and inventing a call
# would state a contract the conversation never made — which is the tau-bench
# trap in reverse: a ground truth nobody can satisfy fails a correct agent. The
# values are still checked, because `tool_param` is what the round-trip axis
# reads; `calls` is what the transparency axis reads.

def _same_person_twice(rng: random.Random, register: str, difficulty: str) -> _Built:
    surname, first, patronymic = _person(rng, difficulty)
    full = _render_name(surname, first, patronymic, register, rng)
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)
    order = _order(rng, register)

    if register == "clean":
        first_parts: list[object] = [
            "Оформите заказ ", order, " на ", ("name", full), ", телефон ",
            ("phone", phone), "."]
        second_parts: list[object] = [
            "И перезвоните ", ("again", first), " после шести, пожалуйста."]
    elif register == "chat":
        first_parts = ["оформите заказ ", order, " на ", ("name", full), " тел ",
                       ("phone", phone)]
        second_parts = ["и наберите ", ("again", first.lower()), " после шести"]
    elif register == "sloppy":
        first_parts = ["заказ ", order, " на ", ("name", full), ", т ",
                       ("phone", phone)]
        second_parts = ["наберите ", ("again", first), " вечером"]
    else:
        first_parts = ["значит заказ ", order, " на ", ("name", full), " телефон ",
                       ("phone", phone)]
        second_parts = ["и позвоните ", ("again", first.lower()), " после шести"]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    turn_one, spans_one = _assemble(first_parts + tail_parts)
    turn_two, spans_two = _assemble(second_parts)
    messages: list[dict[str, object]] = [
        {"role": "user", "content": turn_one},
        {"role": "assistant", "content": "Заказ принят. Что-то ещё?"},
        {"role": "user", "content": turn_two},
    ]
    items = [
        _item("name", "NAME", turn_one, spans_one, "name", full, "customer_name",
              0, "customer", "required"),
        _item("phone", "PHONE", turn_one, spans_one, "phone",
              f"+7{phone_digits}" if register != "voice_raw" else phone, "phone",
              0, "customer_phone", "required"),
        # The short second mention consumes no argument — the message asks for a
        # callback, not a field — but it must reach the model as the SAME fake
        # person, and that is what the link below states.
        _item("again", "NAME", turn_two, spans_two, "again", first, None, 2,
              "customer", "required"),
    ]
    link = LinkExpectation(
        left="name", right="again", kind="same", case="",
        why="один человек назван дважды в одном разговоре: полной формой и "
            "коротким именем — подмена обязана быть одной")
    return _Built(messages=messages, pii=items,
                  negatives=_negatives([(order, "номер заказа")] + tail_negatives, 0),
                  links=[link], calls=[], tool="create_order")


def _two_people(rng: random.Random, register: str, difficulty: str) -> _Built:
    """Two DIFFERENT people in one message. They must not collapse into one."""
    a_surname, a_first, a_patronymic = _person(rng, difficulty)
    b_surname, b_first, b_patronymic = _person(rng, difficulty)
    while b_surname == a_surname:
        b_surname, b_first, b_patronymic = _person(rng, difficulty)
    payer = _render_name(a_surname, a_first, a_patronymic, register, rng)
    recipient = _render_name(b_surname, b_first, b_patronymic, register, rng)
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)

    if register == "clean":
        parts: list[object] = [
            "Плательщик — ", ("payer", payer), ", а получатель ",
            ("recipient", recipient), ", телефон получателя ", ("phone", phone), "."]
    elif register == "chat":
        parts = ["плачу я ", ("payer", payer), " а получит ",
                 ("recipient", recipient), " тел ", ("phone", phone)]
    elif register == "sloppy":
        parts = ["плательщик ", ("payer", payer), ", получатель ",
                 ("recipient", recipient), ", т ", ("phone", phone)]
    else:
        parts = ["плательщик ", ("payer", payer), " получатель ",
                 ("recipient", recipient), " телефон ", ("phone", phone)]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [
        _item("payer", "NAME", text, spans, "payer", payer, None, 0, "payer",
              "required"),
        _item("recipient", "NAME", text, spans, "recipient", recipient,
              "customer_name", 0, "recipient", "required"),
        _item("phone", "PHONE", text, spans, "phone",
              f"+7{phone_digits}" if register != "voice_raw" else phone, "phone",
              0, "recipient_phone", "required"),
    ]
    link = LinkExpectation(
        left="payer", right="recipient", kind="different", case="",
        why="два разных человека в одном сообщении: один токен на двоих отдал бы "
            "инструменту чужого человека, и это хуже, чем разделить одного")
    return _Built(messages=[{"role": "user", "content": text}], pii=items,
                  negatives=_negatives(tail_negatives, 0), links=[link], calls=[],
                  tool="create_order")


def _split_name_anchored(rng: random.Random, register: str,
                         difficulty: str) -> _Built:
    """One person named in PARTS THAT ARE NOT ADJACENT: «с Игорем, фамилия Волков».

    Every other scenario names a person in one contiguous run, so the corpus
    could not produce this shape at all — it came from a persona running the real
    product, who noticed the two halves becoming two spans.

    The full name arrives FIRST, which is what makes the claim testable: with an
    anchor in the vault the two later halves are unambiguously the same person,
    so linking them is REQUIRED rather than guessed.
    """
    surname, first, patronymic = _person(rng, difficulty)
    full = _render_name(surname, first, patronymic, register, rng)
    dative = DATIVE[first]
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)
    order = _order(rng, register)

    if register == "clean":
        first_parts: list[object] = [
            "Оформите заказ ", order, " на ", ("full", full), ", телефон ",
            ("phone", phone), "."]
        second_parts: list[object] = [
            "И свяжитесь с ", ("given", dative), ", фамилия ",
            ("surname", surname), ", после шести."]
    elif register == "chat":
        first_parts = ["оформите заказ ", order, " на ", ("full", full), " тел ",
                       ("phone", phone)]
        second_parts = ["наберите ", ("given", dative.lower()), " фамилия ",
                        ("surname", surname.lower()), " вечером"]
    elif register == "sloppy":
        first_parts = ["заказ ", order, " на ", ("full", full), ", т ",
                       ("phone", phone)]
        second_parts = ["наберите ", ("given", dative), ", фамилия ",
                        ("surname", surname), " вечром"]
    else:
        first_parts = ["значит заказ ", order, " на ", ("full", full), " телефон ",
                       ("phone", phone)]
        second_parts = ["и позвоните ", ("given", dative.lower()), " фамилия ",
                        ("surname", surname.lower()), " после шести"]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    turn_one, spans_one = _assemble(first_parts + tail_parts)
    turn_two, spans_two = _assemble(second_parts)
    messages: list[dict[str, object]] = [
        {"role": "user", "content": turn_one},
        {"role": "assistant", "content": "Записал. Что-то ещё?"},
        {"role": "user", "content": turn_two},
    ]
    # BOTH HALVES FEED THE SAME ARGUMENT and both are checked by the round trip
    # for it: the agent assembles one `customer_name` out of them, so a half that
    # comes back as somebody else is a wrong call even when the other half is
    # perfect. A lone surname is exactly where that happened — «Иванова» resolved
    # to «Иванов», a man.
    #
    # The given name is demanded back in the NOMINATIVE while the surface is
    # dative. That is the one place the corpus asks for a form other than the one
    # written, and it is deliberate: «позвоните Игорю» coming back as «Игорю» is
    # a declined name written into the customer's CRM.
    items = [
        _item("full", "NAME", turn_one, spans_one, "full", full, "customer_name",
              0, "person", "required"),
        _item("phone", "PHONE", turn_one, spans_one, "phone",
              f"+7{phone_digits}" if register != "voice_raw" else phone, "phone",
              0, "person_phone", "required"),
        _item("given", "NAME", turn_two, spans_two, "given", first,
              "customer_name", 2, "person", "required"),
        _item("surname", "NAME", turn_two, spans_two, "surname", surname,
              "customer_name", 2, "person", "required"),
    ]
    links = [
        LinkExpectation(left="full", right="given", kind="same", case="",
                        why="полное имя прозвучало раньше, якорь в волте есть — "
                            "половина однозначно тот же человек"),
        LinkExpectation(left="full", right="surname", kind="same", case="",
                        why="то же самое для фамилии, названной отдельным словом "
                            "после слова-подсказки"),
    ]
    return _Built(messages=messages, pii=items,
                  negatives=_negatives([(order, "номер заказа")] + tail_negatives, 0),
                  links=links, calls=[], tool="create_order")


def _split_name_bare(rng: random.Random, register: str, difficulty: str) -> _Built:
    """The split mention with NO earlier full name to anchor it.

    Carries no identity and an `unjudged` link: with nothing in the vault to tie
    the halves together, linking them would be a guess, and merging two people is
    worse than splitting one. Demanding a link here would score the gateway on
    information the conversation never carried; silently accepting either answer
    would let a real merge hide there, which is why the claim is written down as
    `unjudged` rather than left out.

    What it DOES demand is detection of both halves. A cued surname arriving in
    lower case («фамилия волков») is the shape the chat register actually carries,
    and a missed one is not a consistency defect — it is a leak.
    """
    surname, first, patronymic = _person(rng, difficulty)
    dative = DATIVE[first]
    phone_digits = _phone_digits(rng)
    phone = _render_phone(phone_digits, register, rng)

    if register == "clean":
        parts: list[object] = [
            "Свяжитесь с ", ("given", dative), ", фамилия ", ("surname", surname),
            ", телефон ", ("phone", phone), "."]
    elif register == "chat":
        parts = ["наберите ", ("given", dative.lower()), " фамилия ",
                 ("surname", surname.lower()), " тел ", ("phone", phone)]
    elif register == "sloppy":
        parts = ["позвоните ", ("given", dative), " фамилия ", ("surname", surname),
                 ", т ", ("phone", phone)]
    else:
        parts = ["позвоните пожалуйста ", ("given", dative.lower()), " фамилия ",
                 ("surname", surname.lower()), " телефон ", ("phone", phone)]

    tail_parts, tail_negatives = _tail(rng, register, difficulty, False)
    text, spans = _assemble(parts + tail_parts)
    items = [
        _item("given", "NAME", text, spans, "given", first, "customer_name", 0,
              "", "required"),
        _item("surname", "NAME", text, spans, "surname", surname,
              "customer_name", 0, "", "required"),
        _item("phone", "PHONE", text, spans, "phone",
              f"+7{phone_digits}" if register != "voice_raw" else phone, "phone",
              0, "", "required"),
    ]
    link = LinkExpectation(
        left="given", right="surname", kind="unjudged", case="",
        why="полной формы в разговоре не звучало: связать не с чем, и требовать "
            "связывания значило бы судить шлюз по сведениям, которых не было")
    return _Built(messages=[{"role": "user", "content": text}], pii=items,
                  negatives=_negatives(tail_negatives, 0), links=[link], calls=[],
                  tool="create_order")


# --- the grid -------------------------------------------------------------

_BUILDERS = {
    "create_order": _create_order,
    "check_order_status": _check_order_status,
    "verify_identity": _verify_identity,
    "issue_refund": _issue_refund,
    "register_vehicle": _register_vehicle,
    "send_invoice": _send_invoice,
    "same_person_twice": _same_person_twice,
    "two_people": _two_people,
    "split_name_anchored": _split_name_anchored,
    "split_name_bare": _split_name_bare,
}
SCENARIOS: tuple[str, ...] = tuple(_BUILDERS)

# 10 x 5 x 3 = 150 cells. The design size is 3 sets per cell, 450 cases.
_CELLS: tuple[tuple[str, str, str], ...] = tuple(
    (scenario, register, difficulty)
    for scenario in SCENARIOS
    for register in REGISTERS
    for difficulty in DIFFICULTIES
)


# How many times a cell may be redrawn before the generator gives up. Eight is
# far past any plausible run of collisions (each is well under 1%), so hitting
# the ceiling means the templates changed, not that the dice were unkind.
_MAX_REDRAWS = 8


def _negative_inside_span(case: Case) -> str:
    """A negative whose text falls inside a labelled span, or "".

    THIS IS A CORPUS BUG, NOT A GATEWAY ONE, and it is invisible to `validate`:
    both the item and the negative are individually correct. It happens when two
    random numbers collide — a four-digit invoice number appearing inside a
    sixteen-digit card, or, in `voice_raw`, four spelled-out digits appearing
    inside a spelled-out phone. The scorer's over-masking check finds the
    negative by SEARCHING the text (it has no offsets), lands inside the masked
    card, and reports a false mask that never happened.

    Roughly one case in a thousand, which is exactly the rate at which a defect
    survives review and then explains a stubborn 99.9%.
    """
    for negative in case.negatives:
        text = message_text(case, negative.msg)
        start = text.find(negative.value)
        while start >= 0:
            end = start + len(negative.value)
            for item in case.pii:
                if (item.msg == negative.msg
                        and start < item.end and end > item.start):
                    return (f"negative {negative.value!r} falls inside item "
                            f"{item.id} ({item.value!r})")
            start = text.find(negative.value, start + 1)
    return ""


def _case(rng: random.Random, scenario: str, register: str, difficulty: str,
          index: int) -> Case:
    for _ in range(_MAX_REDRAWS):
        built = _BUILDERS[scenario](rng, register, difficulty)
        case = Case(
            id=f"{FAMILY}-{scenario}-{register}-{difficulty}-{index:02d}",
            family=FAMILY, scenario=scenario, register=register,
            difficulty=difficulty, length_rung="short",
            # DERIVED, not given. The design doc does not cross this family with
            # the conversation-scope dimension — a single-turn case has nothing
            # to scope — so it takes the form a customer gateway with no
            # conversation field actually triggers, and `conversation_key` keeps
            # the cases apart by their own first messages. One shared explicit id
            # would put every case in one scope and let one dialogue's link
            # resolve inside another.
            conversation_id="",
            relation="equality", messages=built.messages,
            tools=_tools_for(built.tool), pii=built.pii, preceded_by="",
            annotators=0, adjudicated=False, negatives=built.negatives,
            links=built.links, calls=built.calls, expected_choice="",
            expected_answer="", asr_digits=False)
        if not _negative_inside_span(case):
            return case
    raise ValueError(
        f"{FAMILY}: {scenario}/{register}/{difficulty} collided {_MAX_REDRAWS} "
        f"times — a negative kept landing inside a labelled span, which at this "
        f"rate is a template that puts one there rather than a run of bad draws")


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases, deterministic from `rng`, uniform over the grid.

    THE COUNT MUST BE A MULTIPLE OF THE GRID, and the refusal is deliberate. The
    family's only claim that no other family can make is a per-TYPE rate, and
    that arithmetic rests on every cell holding the same number of cases: an
    off-grid count silently gives some scenario one more instance than another
    and the per-register table stops being comparable to itself. A smaller run is
    what the frozen tier ladder is for — it takes a prefix of the whole corpus,
    which is a different thing from building a smaller corpus.

    Cases are emitted INTERLEAVED — one full pass over the grid, then the next —
    so that a consumer which cuts the head of the file still sees every scenario
    and every register. That defect is measured: `bench/agentrun/runner.py
    --limit 150` over v1's scenario-major file reached 4 of its 10 scenarios.
    """
    if count <= 0 or count % len(_CELLS):
        below = max(count // len(_CELLS), 1) * len(_CELLS)
        raise ValueError(
            f"{FAMILY}: count must be a positive multiple of {len(_CELLS)} "
            f"({len(SCENARIOS)} scenarios x {len(REGISTERS)} registers x "
            f"{len(DIFFICULTIES)} difficulties), got {count}; the nearest valid "
            f"counts are {below} and {below + len(_CELLS)}")
    per_cell = count // len(_CELLS)
    return [_case(rng, scenario, register, difficulty, index)
            for index in range(per_cell)
            for scenario, register, difficulty in _CELLS]


__all__ = ["FAMILY", "SCENARIOS", "DIFFICULTIES", "build"]
