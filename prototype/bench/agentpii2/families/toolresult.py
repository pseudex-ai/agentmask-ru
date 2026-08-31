"""`result` and `rank`: personal data that ARRIVES in a tool result.

THE THIRD LEG. v1 had none of this: every gold value stood in a user turn, so
the corpus only ever walked «пользователь → модель → инструмент». Here the
customer's own CRM hands the model an address that appeared in no user turn, and
the demand is that it be masked ON THE WAY IN. That path shares no code with the
first except the vault, and it fails in ways the first cannot: the text was
written by a machine, so it carries Latin keys, `null`, an em dash for an empty
field, and a ФИО glued into one token — and none of it ever passed through the
normalisation a human's typing gets.

TWO FAMILIES, ONE MODULE, because they are one mechanism seen from two sides:

  `result`  ONE record comes back and must be masked inbound. Detection only —
            no expected call. The split from `indirect` is deliberate and stated
            in the design doc: this asks «замаскировано ли на входе», that asks
            «вернулось ли настоящее на выходе», and a defect passes one while
            failing the other.
  `rank`    FIVE records come back so the model can order them. The expected
            outcome is NOT that the model picks correctly — it cannot, and the
            corpus exists to give that a number rather than a fix — but that the
            gateway does not silently corrupt the ranking.

HOW THE RANKING FAILURE IS MADE VISIBLE, which is the whole design of the second
half. Three things are arranged so that a wrong answer names its own cause:

  1. Every candidate is a separate gold item with its own identity, and
     consecutive candidates carry a `different` LinkExpectation. If the gateway
     hands two candidates ONE substitute — which is exactly what an address
     linker with a loose scope does to five houses on one street — the model is
     choosing between four things where there were five, and the corpus says so
     without ever asking the model a question.
  2. The action call consumes ONLY the correct candidate's item, so the scorer
     compares what arrived against `expected_choice`.
  3. Every OTHER candidate is in `case.pii` too, which is what makes
     `classify_break`'s `other_person` reachable here. A model that ranks noise
     and picks candidate three calls the tool with a REAL address belonging to a
     different customer — the worst outcome the product has, and the only way to
     see it is to have the other four canonical values written down.

`frequency` is the control arm and belongs to no other family: «с какого номера
чаще всего заказывали» is derived from EQUALITY alone, so a correct gateway
preserves it. Without it a uniformly zero `rank` row cannot be told from a broken
instrument.

WHAT THE REGISTER MEANS HERE, because it is not what it means anywhere else. A
CRM does not make typos. It makes `null`, «—», truncated fields and a ФИО in one
token. So the register governs two different surfaces at once: the customer's own
turn (ordinary speech or typing) and the FORM THE VALUE WAS CAPTURED IN before
the CRM stored it. A record fed by a messenger holds lower-case names and no
patronymic; a record fed by a voice bot with inverse text normalisation off holds
the transcript verbatim in its note field.

Which forces one declaration and one local gate:

  * a `voice_raw` case whose tool result carries STRUCTURED fields sets
    `asr_digits`, because a CRM writes a phone as digits no matter how the call
    was transcribed. That flag exists for exactly this and using it is not a
    bypass — so the property the schema's gate protects is kept by a stricter
    local one: NO user turn of a `voice_raw` case may contain a digit at all.
  * the `prose` shape at `voice_raw` needs no flag: the note field IS the
    transcript, so the whole case is digit-free, down to the order number the
    caller reads out in words. That is the case a generator would never think to
    write and the one seven real call recordings say we fail.

`voice_itn` and `voice_raw` user turns are THE SAME SENTENCE wherever a number
is spoken in both — the branch code, the invoice sum, the house being compared
against, the ticket number. Anything else and the split measures two different
utterances and calls the difference inverse text normalisation. The exception is
where verbatim speech would not carry the identifier at all: nobody recites an
order number in words when they can say «мой заказ», so there the turn differs
because the channel differs, which is the register doing its own work.

WHAT IS NOT HERE, and where it lives instead. No expected call in `result` — the
lookup is already in the transcript and asking the model to re-make it would
score the model, not the gateway. No PII in any assistant tool-call argument: the
audit gate cannot see inside `arguments` (it reads `content`), so an unclaimed
personal value there would be invisible to the corpus's own honesty check, and
the rule is that every lookup argument is an id. No system message: whether one
is masked depends on the deployment leg, and `validate()` refuses a gold item
sitting in one.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii2.schema import (  # noqa: E402
    LENGTH_RUNGS, REGISTERS, Case, ExpectedCall, LinkExpectation, Negative,
    PiiItem, ToolSchema, case_characters, validate)

# --- the plan -------------------------------------------------------------
#
# 3 shapes x 5 registers x 10 = 150 `result`, 4 relations x 5 registers x 3 = 60
# `rank`. Difficulty is NOT crossed: the design doc crosses it only inside
# `transfer`, and here the family is the difficulty. Every case therefore carries
# the same value, and a reader slicing the corpus by difficulty must not read
# this pile as a measurement.

_SHAPES: tuple[str, ...] = ("json_object", "json_list", "prose")
_RELATIONS: tuple[str, ...] = ("similarity", "ordering", "prefix", "frequency")
_RESULT_REPEATS = 10
_RANK_REPEATS = 3
_DIFFICULTY = "hard"
_LENGTH_RUNG = "short"


# --- pools ----------------------------------------------------------------
#
# Authored from the domain — what a Russian SMB's CRM holds — never from a list
# of what our detector currently finds. Overlap with the leased gazetteer is
# unavoidable (Russian names are Russian names) but no entry is here BECAUSE we
# detect it.
#
# FOREIGN NAMES ARE NOT AN ADVERSARIAL CASE. Difficulty is uncrossed in this
# family, so the v1 rule «foreign names appear at every difficulty» becomes
# «foreign names appear at a steady rate in every register and every shape». A
# shop with foreign customers is Tuesday, and hiding them anywhere would let a
# summary number look healthy about a population it fails on.

_MALE: tuple[tuple[str, str, str], ...] = (
    ("Иванов", "Пётр", "Сергеевич"), ("Кузнецов", "Дмитрий", "Андреевич"),
    ("Морозов", "Алексей", "Николаевич"), ("Волков", "Сергей", "Павлович"),
    ("Лебедев", "Максим", "Олегович"), ("Фёдоров", "Кирилл", "Романович"),
    ("Григорьев", "Никита", "Львович"), ("Соколов", "Игорь", "Валентинович"),
)
_FEMALE: tuple[tuple[str, str, str], ...] = (
    ("Иванова", "Мария", "Львовна"), ("Кузнецова", "Ольга", "Дмитриевна"),
    ("Морозова", "Екатерина", "Сергеевна"), ("Волкова", "Татьяна", "Ивановна"),
    ("Лебедева", "Ирина", "Петровна"), ("Фёдорова", "Юлия", "Андреевна"),
)
# Deliberately hostile to suffix rules: no -ов/-ев/-ин, several non-Slavic.
_FOREIGN: tuple[tuple[str, str, str], ...] = (
    ("Ким", "Виктор", ""), ("Тагиев", "Рустам", ""), ("Мкртчян", "Ашот", ""),
    ("Гулиев", "Эльдар", ""), ("Абдуллаев", "Тимур", ""),
    ("Саркисян", "Карен", ""), ("Нгуен", "Ань", ""), ("Мамедова", "Лейла", ""),
    ("Валиахметов", "Ильдар", ""), ("Джонсон", "Майкл", ""), ("Ли", "Чен", ""),
)

# A household on one account: two full names sharing a surname stem, plus a
# third stored as an initial. The PAIR is the point — canonicalisation that
# folds «Кузнецова» into «Кузнецов» hands ONE substitute to two living people,
# and the `different` link is what turns that into a failed case instead of a
# silently plausible one.
_HOUSEHOLDS: tuple[tuple[tuple[str, str, str], tuple[str, str, str], str], ...] = (
    (("Кузнецова", "Ольга", "Дмитриевна"), ("Кузнецов", "Дмитрий", "Андреевич"),
     "Кузнецов А."),
    (("Морозова", "Екатерина", "Сергеевна"), ("Морозов", "Алексей", "Николаевич"),
     "Морозов И."),
    (("Волкова", "Татьяна", "Ивановна"), ("Волков", "Сергей", "Павлович"),
     "Волков П."),
    (("Фёдорова", "Юлия", "Андреевна"), ("Фёдоров", "Кирилл", "Романович"),
     "Фёдоров С."),
    (("Мамедова", "Лейла", ""), ("Мамедов", "Руслан", ""), "Мамедов Т."),
)

# (canonical form with its type word, bare form as a messenger writes it).
_STREETS: tuple[tuple[str, str], ...] = (
    ("улица Тверская", "тверская"), ("улица Гагарина", "гагарина"),
    ("проспект Мира", "мира"), ("Ленинский проспект", "ленинский"),
    ("улица Строителей", "строителей"), ("улица Пушкина", "пушкина"),
    ("бульвар Энтузиастов", "энтузиастов"), ("Профсоюзная улица", "профсоюзная"),
)
# The multi-candidate cases print one street FIVE times, and the whole case has
# to fit the 400-character `short` band. Long names are excluded there and only
# there — a budget, stated, rather than a silently truncated address.
_SHORT_STREETS: tuple[tuple[str, str], ...] = (
    ("улица Гагарина", "гагарина"), ("улица Пушкина", "пушкина"),
    ("проспект Мира", "мира"), ("улица Ленина", "ленина"),
)
_CITIES: tuple[str, ...] = ("Москва", "Санкт-Петербург", "Казань",
                            "Екатеринбург", "Новосибирск", "Краснодар")

# Numbers a caller reads out. A TABLE rather than a thousands renderer, for the
# reason v1's DATIVE table gives: a native speaker checks a table in ten seconds
# and cannot check a rule at all, and a wrong form here goes into the GROUND
# TRUTH, where it is scored as if it were real Russian.
_ORDER_NUMBERS: tuple[tuple[str, str], ...] = (
    ("5301", "пять тысяч триста один"),
    ("4471", "четыре тысячи четыреста семьдесят один"),
    ("2210", "две тысячи двести десять"),
    ("3908", "три тысячи девятьсот восемь"),
    ("7145", "семь тысяч сто сорок пять"),
)
_AMOUNTS: tuple[tuple[int, str], ...] = (
    (15900, "пятнадцать тысяч девятьсот"),
    (24500, "двадцать четыре тысячи пятьсот"),
    (39800, "тридцать девять тысяч восемьсот"),
)
_EMAILS: tuple[str, ...] = (
    "kuznetsova.o@mail.ru", "dmitry.v@yandex.ru", "o.moroz@inbox.ru",
    "t.kim88@gmail.com", "lejla.m@list.ru",
)

_ONES: tuple[str, ...] = ("ноль", "один", "два", "три", "четыре", "пять",
                          "шесть", "семь", "восемь", "девять")
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
_TENS: tuple[str, ...] = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят",
                          "шестьдесят", "семьдесят", "восемьдесят", "девяносто")
_HUNDREDS: tuple[str, ...] = ("", "сто", "двести", "триста", "четыреста",
                              "пятьсот", "шестьсот", "семьсот", "восемьсот",
                              "девятьсот")


def _words(number: int) -> str:
    """A cardinal 0-999 in words, masculine.

    Gender shows only on 1 and 2, so house and flat numbers in the voice
    registers are drawn from a pool that ends in neither — «квартира двадцать
    один» is a form nobody says, and putting it in the ground truth would score
    the gateway against invented Russian.
    """
    if not 0 <= number <= 999:
        raise ValueError(f"only 0-999 is spelled out here, got {number}")
    if number < 10:
        return _ONES[number]
    if number < 20:
        return _TEENS[number - 10]
    said: list[str] = []
    if number >= 100:
        said.append(_HUNDREDS[number // 100])
        number %= 100
    if 10 <= number < 20:
        said.append(_TEENS[number - 10])
    else:
        if number >= 20:
            said.append(_TENS[number // 10])
            number %= 10
        if number:
            said.append(_ONES[number])
    return " ".join(said)


def _spoken_phone(digits: str) -> str:
    """«восемь девятьсот шестнадцать двести четырнадцать восемьдесят восемь ноль три».

    The grouping is how a Russian speaker reads a mobile number aloud, and the
    last pair goes digit by digit when it starts with a zero — «ноль три», never
    «три».
    """
    tail = digits[8:]
    spoken_tail = (f"{_ONES[0]} {_ONES[int(tail[1])]}" if tail[0] == "0"
                   else _words(int(tail)))
    return (f"восемь {_words(int(digits[0:3]))} {_words(int(digits[3:6]))} "
            f"{_words(int(digits[6:8]))} {spoken_tail}")


# --- checksums ------------------------------------------------------------
#
# Every identifier the corpus claims must pass its own checksum, or the ground
# truth claims a document that is not one and a checksum-gated detector is right
# to reject it. Scoring that as a miss would measure the corpus's carelessness.
# The algorithms are published; a checksum has one definition.

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


def _inn12(rng: random.Random, region: str) -> str:
    """A twelve-digit ИНН — an individual's, with the region in the first two.

    Twelve digits and not ten on purpose. A ten-digit ИНН identifies a LEGAL
    ENTITY, which Recital 14 puts outside the regulation and 152-ФЗ reaches the
    same place through its definition of the subject as a natural person. An
    ИП's ИНН is a person's, so it is the only one this corpus may label as
    personal data — and the region code the `prefix` relation asks about is the
    first two digits of it.
    """
    body = region + _digits(rng, 8)
    first = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    eleventh = sum(int(d) * w for d, w in zip(body, first)) % 11 % 10
    body += str(eleventh)
    second = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    twelfth = sum(int(d) * w for d, w in zip(body, second)) % 11 % 10
    return body + str(twelfth)


def _card(rng: random.Random) -> str:
    body = "4276" + _digits(rng, 11)
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


def _passport(rng: random.Random) -> tuple[str, str]:
    """Series and number. The Russian passport carries no checksum at all, so
    there is nothing to satisfy and nothing to fake — only the shape."""
    return rng.choice(("4509", "4518", "6304", "7811")), _digits(rng, 6)


# --- writing errors -------------------------------------------------------
#
# Applied to a SLOT VALUE before assembly, never to a finished message. A
# post-processing pass changes the string's length and silently invalidates
# every offset computed before it — the corpus keeps scoring and scores wrongly.
#
# The distribution is v1's, measured over 2112 human corrections in RuSpellGold:
# one letter substituted 950 (ё→е 499 of them), one letter dropped 626, one
# character too many 463. The commonest is not a typo at all — «ё» written as
# «е» is ordinary Russian practice and it lands directly on Пётр and Фёдоров.

_SUBSTITUTIONS: tuple[tuple[str, str], ...] = (
    ("ё", "е"), ("ё", "е"), ("ё", "е"),
    ("а", "о"), ("и", "е"), ("о", "а"), ("е", "и"), ("я", "и"), ("т", "д"),
)
_LATIN_TWINS: dict[str, str] = {"о": "o", "а": "a", "е": "e", "с": "c",
                                "р": "p", "у": "y", "х": "x", "О": "O",
                                "А": "A", "Е": "E", "С": "C", "Р": "P"}


def _typo(text: str, rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.45:
        for source, target in rng.sample(_SUBSTITUTIONS, len(_SUBSTITUTIONS)):
            positions = [i for i, ch in enumerate(text) if ch.lower() == source]
            if not positions:
                continue
            index = rng.choice(positions)
            replacement = target.upper() if text[index].isupper() else target
            return text[:index] + replacement + text[index + 1:]
        return text
    if roll < 0.80:
        # Never the first character: a dropped initial stops being a typo and
        # becomes a different word.
        positions = [i for i, ch in enumerate(text) if ch.isalpha() and i > 0]
        if not positions:
            return text
        index = rng.choice(positions)
        return text[:index] + text[index + 1:]
    positions = [i for i, ch in enumerate(text) if ch in _LATIN_TWINS]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + _LATIN_TWINS[text[index]] + text[index + 1:]


# --- rendering ------------------------------------------------------------
#
# `_crm_*` write a STRUCTURED field: a machine wrote it, so it is normalised,
# and its register says how the value was captured before the CRM stored it.
# `_note_*` write free text in a note field, which a human or a transcript
# wrote — that is the only surface in this family where a typo belongs.

def _person(rng: random.Random) -> tuple[str, str, str]:
    if rng.random() < 0.3:
        return rng.choice(_FOREIGN)
    return rng.choice(_MALE + _FEMALE)


def _crm_name(surname: str, first: str, patronymic: str, register: str,
              rng: random.Random) -> str:
    """The caller passes the parts the FIELD holds — a list view carries no
    patronymic — so there is no flag here switching between two shapes."""
    parts = [part for part in (surname, first, patronymic) if part]
    if register == "clean":
        return " ".join(parts)
    if register == "chat":
        return " ".join(parts).lower()
    if register == "sloppy":
        # The two artifacts a CRM really produces: an import that lost its
        # separators, and a field truncated to an initial.
        if rng.random() < 0.5:
            return "".join(parts)
        return f"{surname} {first[0]}."
    return " ".join(parts).lower()


def _note_name(surname: str, first: str, patronymic: str, register: str,
               rng: random.Random) -> str:
    parts = [part for part in (surname, first, patronymic) if part]
    if register == "clean":
        return " ".join(parts)
    if register == "sloppy":
        return _typo(f"{surname} {first}", rng)
    return f"{surname} {first}".lower()


def _human_phone(digits: str, register: str, rng: random.Random) -> str:
    """A phone as a PERSON writes or says it — a user turn, or a note field an
    operator typed. Never a structured field: those are `_crm_phone`."""
    a, b, c, d = digits[:3], digits[3:6], digits[6:8], digits[8:]
    if register == "clean":
        return f"+7 {a} {b}-{c}-{d}"
    if register == "chat":
        return f"8{digits}"
    if register == "sloppy":
        dashed = f"8-{a}-{b}-{c}-{d}"
        # A Cyrillic О typed where a zero belongs is the commonest obfuscation
        # that is not one — it is a keyboard slip, and normalisation folds it.
        if "0" in dashed:
            return dashed.replace("0", "О", 1)
        return dashed.replace("-", "", 1)
    if register == "voice_itn":
        return f"8 {a} {b} {c} {d}"
    return _spoken_phone(digits)


def _crm_phone(digits: str, register: str) -> str:
    """A STRUCTURED phone field, and it is register-invariant on purpose.

    A CRM normalises on save — that is the one thing every CRM does — so the
    stored form is E.164 whatever the channel wrote, and the exception is an
    import that dropped the plus. That invariance is what gives the case its
    claim: the caller's «89162148803» and the stored «+79162148803» are one
    subscriber, and CLAUDE.md records that collapsing them to one key is the
    vault's job. If the two strings were identical the link would be satisfied
    by a gateway that does nothing at all.
    """
    if register == "sloppy":
        return f"7{digits}"        # an import that dropped the plus
    return f"+7{digits}"


def _crm_address(city: str, street_full: str, street_bare: str, house: int,
                 flat: int, register: str) -> str:
    if register == "clean":
        return f"{city}, {street_full}, д. {house}, кв. {flat}"
    if register == "chat":
        return f"{street_bare} {house} кв {flat}"
    if register == "sloppy":
        return f"г {city} {street_full} д{house}"
    if register == "voice_itn":
        return f"{street_bare} {house} квартира {flat}"
    return f"{street_bare} {house} кв {flat}"


def _spoken_address(street_bare: str, house: int, flat: int) -> str:
    return f"{street_bare} {_words(house)} квартира {_words(flat)}"


def _candidate_address(street_full: str, street_bare: str, house: int,
                       register: str) -> str:
    """One line of a search result: street and house, no city and no flat.

    Five of these plus a question have to fit 400 characters, and a search
    within one city does not repeat the city on every row.
    """
    if register == "clean":
        return f"{street_full}, д. {house}"
    if register == "sloppy":
        return f"{street_full} д{house}"
    if register == "voice_itn":
        return f"{street_bare} дом {house}"
    return f"{street_bare} {house}"


def _house(rng: random.Random, register: str) -> int:
    if register in ("voice_itn", "voice_raw"):
        return rng.choice([n for n in range(3, 99) if n % 10 not in (1, 2)])
    return rng.randrange(1, 99)


def _flat(rng: random.Random, register: str) -> int:
    if register in ("voice_itn", "voice_raw"):
        return rng.choice([n for n in range(3, 240) if n % 10 not in (1, 2)])
    return rng.randrange(1, 240)


def _render_document(kind: str, register: str,
                     rng: random.Random) -> tuple[str, str, str]:
    """(json key, wire value, gold type). The key is LATIN and that is the point.

    CLAUDE.md records the defect this shape found once already: `{"passport":
    "4509123456"}` was lost entirely because the cue list holds «паспорт» and not
    the Latin `passport`, while the same number after the Russian word was
    masked. A CRM's own field names are English far more often than not.
    """
    if kind == "passport":
        series, number = _passport(rng)
        value = f"{series} {number}" if register == "clean" else series + number
        return "passport", value, "PASSPORT"
    if kind == "snils":
        digits = _snils(rng)
        value = (f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
                 if register == "clean" else digits)
        return "snils", value, "SNILS"
    if kind == "inn":
        return "inn", _inn12(rng, rng.choice(("77", "78", "50", "23"))), "INN"
    if kind == "email":
        return "email", rng.choice(_EMAILS), "EMAIL"
    if kind == "card":
        digits = _card(rng)
        value = (" ".join(digits[i:i + 4] for i in range(0, 16, 4))
                 if register == "clean" else digits)
        return "card", value, "CARD"
    raise ValueError(f"unknown document kind {kind!r}")


_DOCUMENTS: tuple[str, ...] = ("passport", "snils", "inn", "email", "card")


# --- assembly -------------------------------------------------------------

def _assemble(parts: list[object]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Build a message and the offsets of its tracked slots in ONE pass.

    A plain `str` is literal text; a `(name, value)` tuple is a slot whose span
    is recorded. Offsets are computed while the string is being built and never
    by searching the finished one: a search finds the FIRST occurrence, and this
    family puts the same phone in three records of one array, where the second
    and third spans would then both point at the first.
    """
    out: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for part in parts:
        if isinstance(part, tuple):
            name, value = part
            if name in spans:
                raise ValueError(f"slot {name!r} assembled twice")
            spans[name] = (cursor, cursor + len(value))
            out.append(value)
            cursor += len(value)
        else:
            text = str(part)
            out.append(text)
            cursor += len(text)
    return "".join(out), spans


def _record(fields: list[tuple[str, object]]) -> list[object]:
    """One JSON object as a PARTS LIST, so a slot inside it keeps its offset.

    `json.dumps` would be shorter and would hand the ground truth a string
    nobody counted characters against. The schema stores wire form because that
    is what the gateway sees — the envelope's `content` is a string and masking
    runs over it flat — so the wire form is what the offsets must index.

    A field's value is either a list of parts (quoted here) or a literal already
    in wire form: a quoted string, a number, or `null`.
    """
    parts: list[object] = ["{"]
    for index, (key, value) in enumerate(fields):
        if index:
            parts.append(",")
        parts.append(f'"{key}":')
        if isinstance(value, list):
            parts.append('"')
            for piece in value:
                text = piece[1] if isinstance(piece, tuple) else str(piece)
                if '"' in text or "\\" in text:
                    raise ValueError(f"value {text!r} would break the JSON")
                parts.append(piece)
            parts.append('"')
        else:
            parts.append(str(value))
    parts.append("}")
    return parts


def _array(records: list[list[tuple[str, object]]]) -> list[object]:
    parts: list[object] = ["["]
    for index, fields in enumerate(records):
        if index:
            parts.append(",")
        parts.extend(_record(fields))
    parts.append("]")
    return parts


def _tool_call(call_id: str, name: str,
               arguments: dict[str, str]) -> dict[str, object]:
    """The assistant's lookup. ITS ARGUMENTS ARE IDS AND NEVER PERSONAL DATA.

    `audit_unlabelled` reads `content`, so anything in `arguments` is invisible
    to the corpus's own honesty gate; a personal value here could never be
    claimed by a gold item, because offsets index `content`.
    """
    for value in arguments.values():
        if any(character.isdigit() for character in value) and len(value) > 8:
            raise ValueError(f"lookup argument {value!r} looks like a value, "
                             f"not an id")
    return {"role": "assistant", "content": "",
            "tool_calls": [{"id": call_id, "type": "function",
                            "function": {"name": name,
                                         "arguments": json.dumps(
                                             arguments, ensure_ascii=False)}}]}


def _tool_result(call_id: str, name: str, content: str) -> dict[str, object]:
    return {"role": "tool", "tool_call_id": call_id, "name": name,
            "content": content}


# --- tools ----------------------------------------------------------------

def _schema(name: str, description: str, params: dict[str, tuple[str, str]],
            required: list[str]) -> ToolSchema:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": kind, "description": text}
                               for key, (kind, text) in params.items()},
                "required": required,
            },
        },
    }


_TOOLS: dict[str, ToolSchema] = {
    "find_customer": _schema(
        "find_customer", "Найти карточку клиента по номеру заказа.",
        {"order_id": ("string", "Номер заказа")}, ["order_id"]),
    "list_contacts": _schema(
        "list_contacts", "Показать контакты, привязанные к аккаунту.",
        {"account_id": ("string", "Идентификатор аккаунта")}, ["account_id"]),
    "get_ticket_note": _schema(
        "get_ticket_note", "Прочитать заметку оператора по обращению.",
        {"ticket_id": ("string", "Номер обращения")}, ["ticket_id"]),
    "list_order_addresses": _schema(
        "list_order_addresses", "Показать адреса из прошлых заказов клиента.",
        {"order_id": ("string", "Номер текущего заказа"),
         "period": ("string", "Период выборки")}, ["order_id"]),
    "list_clients": _schema(
        "list_clients", "Показать клиентов филиала с датами рождения.",
        {"branch": ("string", "Код филиала")}, ["branch"]),
    "list_partners": _schema(
        "list_partners", "Показать партнёров-ИП с их ИНН.",
        {"period": ("string", "Период выборки")}, ["period"]),
    "list_recent_orders": _schema(
        "list_recent_orders", "Показать последние заказы с телефонами.",
        {"period": ("string", "Период выборки")}, ["period"]),
    "update_delivery_address": _schema(
        "update_delivery_address", "Изменить адрес доставки у заказа.",
        {"order_id": ("string", "Номер заказа"),
         "address": ("string", "Новый адрес с домом"),
         "recipient_name": ("string", "ФИО получателя")},
        ["order_id", "address"]),
    "book_appointment": _schema(
        "book_appointment", "Записать клиента на приём.",
        {"client_name": ("string", "ФИО клиента"),
         "phone": ("string", "Телефон для подтверждения"),
         "birth_date": ("string", "Дата рождения в формате ДД.ММ.ГГГГ"),
         "service": ("string", "Название услуги")}, ["client_name"]),
    "send_invoice": _schema(
        "send_invoice", "Выставить счёт и отправить его получателю.",
        {"inn": ("string", "ИНН получателя счёта"),
         "company_name": ("string", "Наименование получателя"),
         "amount": ("number", "Сумма счёта в рублях"),
         "email": ("string", "Почта для отправки")}, ["inn", "amount"]),
    "notify_customer": _schema(
        "notify_customer", "Отправить клиенту сообщение по телефону.",
        {"phone": ("string", "Телефон клиента"),
         "text": ("string", "Текст сообщения")}, ["phone", "text"]),
}


def _tools_for(names: tuple[str, ...]) -> list[ToolSchema]:
    """Always more than one tool.

    A single-tool prompt lets a model succeed by having nowhere else to go,
    which hides whether masking damaged its ability to CHOOSE — and choosing is
    where an implausible substitute does its damage.
    """
    if len(names) < 2:
        raise ValueError(f"a case must offer at least two tools, got {names}")
    return [_TOOLS[name] for name in names]


# --- shared pieces --------------------------------------------------------

def _item(item_id: str, kind: str, slot: str, spans: dict[str, tuple[int, int]],
          text: str, canonical: str, msg: int, identity: str, duty: str,
          tool_param: str | None) -> PiiItem:
    start, end = spans[slot]
    return PiiItem(id=item_id, type=kind, value=text[start:end], start=start,
                   end=end, canonical=canonical, msg=msg, identity=identity,
                   duty=duty, tool_param=tool_param)


def _phone_canonical(digits: str) -> str:
    """A phone's canonical form is its dialable one, whatever the channel wrote.

    This is NOT the rule «ground truth is what was written» being bent. That
    rule protects a message from being asked for information it never carried —
    a chat with no patronymic must not demand one back. A number read out in
    words carries every digit; writing it as +7 invents nothing, and it is what
    a CRM stores and what the vault canonicalises to.
    """
    return f"+7{digits}"


def _case(case_id: str, family: str, scenario: str, register: str,
          relation: str, messages: list[dict[str, object]],
          tools: list[ToolSchema], pii: list[PiiItem],
          negatives: list[Negative], links: list[LinkExpectation],
          calls: list[ExpectedCall], expected_choice: str,
          asr_digits: bool) -> Case:
    """Assemble and check the three invariants `validate()` cannot see.

    The register gate in the schema joins user AND tool messages, so it cannot
    tell a caller's digits from a CRM's. The property it was protecting —
    verbatim speech carries no digits — is kept here instead, on the user turns
    alone, and it is checked rather than declared.

    The band is checked too. A case that fell out of `short` would be caught by
    `validate()`, but by then it is a corpus with a hole in it; a generator that
    cannot hold its own budget should stop.

    And a negative must name one string in one place — see below. That one is
    not a style rule: measured over 400 seeds, a five-digit invoice sum landed
    inside a twelve-digit ИНН in two of them, and «не маскируй эту сумму» then
    pointed at two strings with no way to say which.
    """
    if register == "voice_raw":
        for index, message in enumerate(messages):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if not isinstance(content, str):
                raise TypeError(f"{case_id}: message {index} has no wire form")
            if any(character.isdigit() for character in content):
                raise ValueError(
                    f"{case_id}: a voice_raw user turn carries a digit "
                    f"({content!r}); 0 of 12 950 real call transcripts do")
    # A declared negative must occur EXACTLY ONCE in each message that declares
    # it and NOWHERE else. Otherwise «this must not be masked» points at two
    # strings and the scorer picks one — which is not a wrong number, it is an
    # unfalsifiable one.
    declared: dict[str, set[int]] = {}
    for negative in negatives:
        declared.setdefault(negative.value, set()).add(negative.msg)
    for value, owners in declared.items():
        for index, message in enumerate(messages):
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError(f"{case_id}: message {index} has no wire form")
            occurrences = content.count(value)
            if index in owners and occurrences != 1:
                raise ValueError(f"{case_id}: negative {value!r} occurs "
                                 f"{occurrences} times in message {index}")
            if index not in owners and occurrences:
                raise ValueError(f"{case_id}: negative {value!r} also occurs in "
                                 f"message {index}, which does not claim it")
    case = Case(
        id=case_id, family=family, scenario=scenario, register=register,
        difficulty=_DIFFICULTY, length_rung=_LENGTH_RUNG,
        conversation_id=f"conv-{case_id}", relation=relation, messages=messages,
        tools=tools, pii=pii, preceded_by="", annotators=0, adjudicated=False,
        negatives=negatives, links=links, calls=calls,
        expected_choice=expected_choice, expected_answer="",
        asr_digits=asr_digits)
    # Read from the schema, never restated: a band this module carried as its
    # own number would keep passing after the schema moved it, which is the
    # drift `test_perf_masking.py` documents for a copied auth token.
    size = case_characters(case)
    if not LENGTH_RUNGS[_LENGTH_RUNG][0] <= size <= LENGTH_RUNGS[_LENGTH_RUNG][1]:
        raise ValueError(f"{case_id}: {size} characters is outside the "
                         f"{_LENGTH_RUNG} band {LENGTH_RUNGS[_LENGTH_RUNG]}; "
                         f"shorten the template, never the ground truth")
    return case


# --- `result`: one record comes back --------------------------------------

def _case_json_object(rng: random.Random, register: str, index: int) -> Case:
    """A lookup returns ONE customer's record, Latin keys and all.

    The customer states their own phone in the user turn and the CRM returns the
    same subscriber in another format. That pair is the family's cheapest real
    claim: one substitute for both, which is the vault's documented
    canonicalisation (+7 / 8 / bare digits collapse to one key) seen from
    outside. At `voice_raw` the pair is `unjudged` instead — the spoken form and
    the stored one are the same subscriber, but demanding one substitute would
    count a detection miss twice, once as a miss and once as a broken link.
    """
    surname, first, patronymic = _person(rng)
    phone = _phone_digits(rng)
    street_full, street_bare = rng.choice(_STREETS)
    city = rng.choice(_CITIES)
    house, flat = _house(rng, register), _flat(rng, register)
    order_digits, _ = rng.choice(_ORDER_NUMBERS)
    order = f"A-{order_digits}"
    doc_key, doc_value, doc_type = _render_document(
        _DOCUMENTS[index % len(_DOCUMENTS)], register, rng)

    user_phone = _human_phone(phone, register, rng)
    if register == "clean":
        user_parts: list[object] = [
            "Здравствуйте! Мой номер ", ("uphone", user_phone),
            ", посмотрите, пожалуйста, что записано по заказу ", order, "."]
    elif register == "chat":
        user_parts = ["мой номер ", ("uphone", user_phone),
                      " гляньте что записано по заказу ", order]
    elif register == "sloppy":
        user_parts = ["мой номер ", ("uphone", user_phone),
                      " посмотрите што записано по заказу ", order]
    elif register == "voice_itn":
        user_parts = ["алло да мой номер ", ("uphone", user_phone),
                      " посмотрите что там записано по заказу ", order]
    else:
        # A caller reciting a phone in words AND an order number in words is
        # 200 characters of one breath, and nobody does it: they identify by
        # the number they are calling from and say «мой заказ». The order id
        # reaches the lookup from the assistant's own arguments, where it
        # belongs — it was never something the caller had to pronounce.
        user_parts = ["алло мой номер ", ("uphone", user_phone),
                      " что там по моему заказу"]
    user_text, user_spans = _assemble(user_parts)

    # The claim this case makes is that two DIFFERENT strings are one
    # subscriber. If the caller's form and the stored form were the same
    # string, the link would be satisfied by a gateway that does nothing, and
    # the case would keep scoring while measuring nothing at all.
    stored_phone = _crm_phone(phone, register)
    if stored_phone == user_phone:
        raise ValueError(f"{register}: the stored phone is written exactly as "
                         f"the caller wrote it, so the link is free")

    fields: list[tuple[str, object]] = [
        ("customer", [("customer",
                       _crm_name(surname, first, patronymic, register, rng))]),
        ("phone", [("phone", stored_phone)]),
        ("address", [("address", _crm_address(city, street_full, street_bare,
                                              house, flat, register))]),
        (doc_key, [("doc", doc_value)]),
        ("order", f'"{order}"'),
    ]
    if register == "sloppy":
        # The two empty-field forms a CRM export really carries. They live in
        # one register rather than all five because the record has a character
        # budget and an empty field is the least of what it has to demonstrate.
        fields.extend([("note", "null"), ("status", '"—"')])
    record_text, record_spans = _assemble(_record(fields))

    user_identity = "phone-said" if register == "voice_raw" else "phone"
    pii = [
        _item("up", "PHONE", "uphone", user_spans, user_text,
              _phone_canonical(phone), 0, user_identity, "required", None),
        _item("cn", "NAME", "customer", record_spans, record_text,
              record_text[slice(*record_spans["customer"])], 2, "person",
              "required", None),
        _item("cp", "PHONE", "phone", record_spans, record_text,
              _phone_canonical(phone), 2, "phone", "required", None),
        _item("ca", "LOC", "address", record_spans, record_text,
              record_text[slice(*record_spans["address"])], 2, "place",
              "required", None),
        _item("cd", doc_type, "doc", record_spans, record_text,
              record_text[slice(*record_spans["doc"])], 2, "document",
              "required", None),
    ]
    link_kind = "unjudged" if register == "voice_raw" else "same"
    why = ("сказан прописью и сохранён цифрами: тот же абонент, но требовать "
           "одну подмену значило бы посчитать пропуск детекции дважды"
           if register == "voice_raw" else
           "тот же абонент назван клиентом и возвращён из CRM в другом формате")
    return _case(
        case_id=f"result-json_object-{register}-{index:03d}", family="result",
        scenario="lookup_record", register=register, relation="equality",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "find_customer", {"order_id": order}),
            _tool_result("c1", "find_customer", record_text),
        ],
        tools=_tools_for(("find_customer", "update_delivery_address",
                          "notify_customer")),
        pii=pii,
        negatives=([Negative(order, "номер заказа", 2)]
                   + ([] if register == "voice_raw"
                      else [Negative(order, "номер заказа", 0)])),
        links=[LinkExpectation("up", "cp", link_kind, "", why)],
        calls=[], expected_choice="", asr_digits=register == "voice_raw")


def _case_json_list(rng: random.Random, register: str, index: int) -> Case:
    """A lookup returns an ARRAY: three people on one account, one phone.

    Two claims in one case and they pull in opposite directions. The three
    people must get three substitutes — «Кузнецова Ольга» and «Кузнецов
    Дмитрий» differ by a gender suffix, and the canonicalisation that folds one
    into the other would give a mother and a son one identity. The one household
    phone must get ONE substitute across all three rows, because it is one
    subscriber. A gateway can fail either half on its own.
    """
    female, male, initial = _HOUSEHOLDS[index % len(_HOUSEHOLDS)]
    phone = _phone_digits(rng)
    account = f"AC-{rng.randrange(1000, 9999)}"
    ids = [f"K-{number}" for number in rng.sample(range(100, 999), 3)]

    if register == "clean":
        user_parts: list[object] = [
            "Добрый день! Покажите, кто привязан к аккаунту ", account, "."]
    elif register == "chat":
        user_parts = ["покажите кто привязан к аккаунту ", account]
    elif register == "sloppy":
        user_parts = ["покажите кто привязан к акаунту ", account]
    elif register == "voice_itn":
        user_parts = ["алло посмотрите пожалуйста кто привязан к аккаунту ",
                      account]
    else:
        user_parts = ["алло посмотрите пожалуйста кто у меня привязан к аккаунту"]
    user_text, user_spans = _assemble(user_parts)

    # A list view carries no patronymic — that is what a list view is, and five
    # records with one have to fit 400 characters besides.
    names = [_crm_name(female[0], female[1], "", register, rng),
             _crm_name(male[0], male[1], "", register, rng),
             initial if register == "clean" else initial.lower()]
    stored_phone = _crm_phone(phone, register)
    records = [[("id", f'"{ids[position]}"'),
                ("name", [(f"name{position}", names[position])]),
                ("phone", [(f"phone{position}", stored_phone)])]
               for position in range(3)]
    array_text, array_spans = _assemble(_array(records))

    pii: list[PiiItem] = []
    for position in range(3):
        pii.append(_item(
            f"n{position}", "NAME", f"name{position}", array_spans, array_text,
            names[position], 2, f"person-{position}", "required", None))
        pii.append(_item(
            f"p{position}", "PHONE", f"phone{position}", array_spans,
            array_text, _phone_canonical(phone), 2, "phone", "required", None))
    negatives = [Negative(value, "внутренний идентификатор карточки", 2)
                 for value in ids]
    if register != "voice_raw":
        negatives.append(Negative(account, "номер аккаунта", 0))
    links = [
        LinkExpectation("n0", "n1", "different", "",
                        "мать и сын: одна фамилия с разным родовым окончанием, "
                        "и это два человека"),
        LinkExpectation("n1", "n2", "different", "",
                        "полное имя и другая карточка с инициалом — разные люди"),
        LinkExpectation("p0", "p1", "same", "",
                        "один домашний номер в трёх карточках — один абонент"),
    ]
    return _case(
        case_id=f"result-json_list-{register}-{index:03d}", family="result",
        scenario="lookup_household", register=register, relation="equality",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "list_contacts", {"account_id": account}),
            _tool_result("c1", "list_contacts", array_text),
        ],
        tools=_tools_for(("list_contacts", "notify_customer",
                          "book_appointment")),
        pii=pii, negatives=negatives, links=links, calls=[],
        expected_choice="", asr_digits=register == "voice_raw")


def _case_prose(rng: random.Random, register: str, index: int) -> Case:
    """A free-text note field: the ordinary text path over machine-stored text.

    Two variants, alternating, and the alternation is the `duty` split made
    concrete. A note naming a street AND a house number identifies a building,
    so it is `required`. A note saying the customer lives somewhere on Тверская
    identifies nobody — hundreds of buildings stand on it, one step more
    specific than the city 152-ФЗ ст. 3 п. 1 already puts outside — so it is
    `optional`, counted in its own column and never folded into recall. The
    decision is mechanical (is there a house number?), which is why this case
    needs no second annotator.

    At `voice_raw` this is the only shape that needs no `asr_digits`: the note
    IS the transcript, so the whole case is digit-free down to the order number
    the caller reads out in words.
    """
    surname, first, patronymic = _person(rng)
    phone = _phone_digits(rng)
    street_full, street_bare = rng.choice(_STREETS)
    city = rng.choice(_CITIES)
    house, flat = _house(rng, register), _flat(rng, register)
    ticket_digits, ticket_words = rng.choice(_ORDER_NUMBERS)
    ticket = f"T-{ticket_digits}"
    said_ticket = ticket_words if register == "voice_raw" else ticket

    if register == "clean":
        user_parts: list[object] = [
            "Поднимите, пожалуйста, заметку по обращению ", said_ticket, "."]
    elif register == "chat":
        user_parts = ["поднимите заметку по обращению ", said_ticket]
    elif register == "sloppy":
        user_parts = ["поднимите заметку по обращеню ", said_ticket]
    elif register == "voice_itn":
        user_parts = ["алло поднимите заметку по обращению ", said_ticket]
    else:
        user_parts = ["алло поднимите пожалуйста заметку по обращению ",
                      said_ticket]
    user_text, user_spans = _assemble(user_parts)

    name = _note_name(surname, first, patronymic, register, rng)
    with_house = index % 2 == 0
    if with_house:
        address = (_spoken_address(street_bare, house, flat)
                   if register == "voice_raw"
                   else _crm_address(city, street_full, street_bare, house,
                                     flat, register))
    else:
        address = street_full if register in ("clean", "sloppy") else street_bare

    if with_house and register == "clean":
        note_parts: list[object] = [
            "Клиент ", ("name", name), " просит перенести доставку на субботу. "
            "Адрес: ", ("addr", address), ". Телефон ",
            ("phone", _human_phone(phone, register, rng)), "."]
    elif with_house and register == "chat":
        note_parts = ["клиент ", ("name", name), " просит перенести доставку "
                      "адрес ", ("addr", address), " тел ",
                      ("phone", _human_phone(phone, register, rng))]
    elif with_house and register == "sloppy":
        note_parts = ["клиет ", ("name", name), " просит перенести доставку "
                      "адрес ", ("addr", address), " тел ",
                      ("phone", _human_phone(phone, register, rng))]
    elif with_house and register == "voice_itn":
        note_parts = ["был звонок клиент ", ("name", name),
                      " просит оставить у консьержа адрес ", ("addr", address),
                      " телефон ", ("phone", _human_phone(phone, register, rng))]
    elif with_house:
        note_parts = ["был звонок клиент зовут ", ("name", name),
                      " просит оставить у консьержа адрес ", ("addr", address),
                      " перезвонить после шести"]
    elif register == "clean":
        note_parts = ["Клиент ", ("name", name), " перезвонит позже. Адрес: ",
                      ("addr", address), ", номер дома не указан. Телефон ",
                      ("phone", _human_phone(phone, register, rng)), "."]
    elif register == "chat":
        note_parts = ["клиент ", ("name", name), " перезвонит позже адрес ",
                      ("addr", address), " номер дома не указан тел ",
                      ("phone", _human_phone(phone, register, rng))]
    elif register == "sloppy":
        note_parts = ["клиет ", ("name", name), " перезвонит позже адрес ",
                      ("addr", address), " номер дома не указан тел ",
                      ("phone", _human_phone(phone, register, rng))]
    elif register == "voice_itn":
        note_parts = ["клиент ", ("name", name), " перезвонит позже в адресе "
                      "только улица ", ("addr", address),
                      " номер дома не указан телефон ",
                      ("phone", _human_phone(phone, register, rng))]
    else:
        note_parts = ["клиент зовут ", ("name", name), " перезвонит позже в "
                      "адресе только улица ", ("addr", address),
                      " номер дома не указан"]
    note_text, note_spans = _assemble(note_parts)

    pii = [_item("nn", "NAME", "name", note_spans, note_text, name, 2, "person",
                 "required", None),
           _item("na", "LOC", "addr", note_spans, note_text, address, 2, "place",
                 "required" if with_house else "optional", None)]
    if "phone" in note_spans:
        pii.append(_item("np", "PHONE", "phone", note_spans, note_text,
                         _phone_canonical(phone), 2, "phone", "required", None))
    return _case(
        case_id=f"result-prose-{register}-{index:03d}", family="result",
        scenario="ticket_note", register=register, relation="equality",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "get_ticket_note", {"ticket_id": ticket}),
            _tool_result("c1", "get_ticket_note", note_text),
        ],
        tools=_tools_for(("get_ticket_note", "update_delivery_address",
                          "notify_customer")),
        pii=pii,
        negatives=[Negative(said_ticket, "номер обращения", 0)],
        links=[], calls=[], expected_choice="", asr_digits=False)


# --- `rank`: five records come back and must be ordered -------------------

def _rank_negatives(ids: list[str], why: str) -> list[Negative]:
    return [Negative(value, why, 2) for value in ids]


def _different_chain(item_ids: list[str], why: str) -> list[LinkExpectation]:
    """Consecutive `different` links across the candidates.

    A chain and not all ten pairs: the defect this states is a linker collapsing
    NEIGHBOURING candidates into one substitute, and ten pairs would report one
    collapse as four failures.
    """
    return [LinkExpectation(item_ids[position], item_ids[position + 1],
                            "different", "", why)
            for position in range(len(item_ids) - 1)]


def _case_rank_similarity(rng: random.Random, register: str,
                          index: int) -> Case:
    """Five addresses on ONE street; which is nearest to a given house.

    Nearest is computable before masking and noise after it: the substitute is
    drawn independently, so neither the street nor the house number survives as
    a distance. `expected_choice` is the house three away; the others are 11, 17,
    23 and 31 away, so the correct answer is unique with a margin no rounding
    can close.

    Five houses on one street is also the hardest case the address linker meets:
    its single-candidate rule must resolve NONE of them, and the `different`
    chain is what says so.
    """
    street_full, street_bare = rng.choice(_SHORT_STREETS)
    target = rng.choice((40, 45, 50, 55, 60, 65))
    candidates = [(target + rng.choice((-1, 1)) * offset, offset == 3)
                  for offset in (3, 11, 17, 23, 31)]
    rng.shuffle(candidates)
    order_digits, order_words = rng.choice(_ORDER_NUMBERS)
    order = f"A-{order_digits}"
    past_orders = [f"A-{number}" for number in
                   rng.sample([n for n in range(1000, 9999)
                               if str(n) != order_digits], 5)]

    if register == "clean":
        user_parts: list[object] = [
            "По новому заказу ", order, " поставьте доставку на ближайший к дому ",
            str(target), " адрес из прошлых."]
    elif register == "chat":
        user_parts = ["по новому заказу ", order, " поставьте доставку на тот из "
                      "прошлых адресов что ближе к дому ", str(target)]
    elif register == "sloppy":
        user_parts = ["по новому заказу ", order, " поставте доставку на тот из "
                      "прошлых адресов что ближе к дому ", str(target)]
    elif register == "voice_itn":
        user_parts = ["значит по новому заказу ", order, " поставьте доставку на "
                      "тот адрес из прошлых который ближе к дому ", str(target)]
    else:
        user_parts = ["значит по новому заказу поставьте доставку на тот адрес "
                      "из прошлых который ближе к дому ", _words(target)]
    user_text, _ = _assemble(user_parts)

    addresses = [_candidate_address(street_full, street_bare, house, register)
                 for house, _ in candidates]
    records = [[("order", f'"{past_orders[position]}"'),
                ("address", [(f"addr{position}", addresses[position])])]
               for position in range(5)]
    array_text, array_spans = _assemble(_array(records))

    winner = next(position for position, (_, is_winner) in enumerate(candidates)
                  if is_winner)
    pii = [_item(f"a{position}", "LOC", f"addr{position}", array_spans,
                 array_text, addresses[position], 2, f"place-{position}",
                 "required", "address" if position == winner else None)
           for position in range(5)]
    return _case(
        case_id=f"rank-similarity-{register}-{index:03d}", family="rank",
        scenario="nearest_address", register=register, relation="similarity",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "list_order_addresses",
                       {"order_id": order, "period": "год"}),
            _tool_result("c1", "list_order_addresses", array_text),
        ],
        tools=_tools_for(("list_order_addresses", "update_delivery_address",
                          "notify_customer")),
        pii=pii,
        negatives=(_rank_negatives(past_orders, "номер прошлого заказа")
                   + ([Negative(order, "номер текущего заказа", 0)]
                      if register != "voice_raw" else [])),
        links=_different_chain([f"a{position}" for position in range(5)],
                               "пять разных домов на одной улице: слить их в "
                               "одну подмену — уничтожить сам вопрос"),
        calls=[ExpectedCall(
            name="update_delivery_address", after_msg=2,
            arguments={"order_id": order, "address": addresses[winner]},
            pii_items=[f"a{winner}"])],
        expected_choice=f"a{winner}", asr_digits=register == "voice_raw")


def _case_rank_ordering(rng: random.Random, register: str, index: int) -> Case:
    """Five clients with dates of birth; which is the oldest.

    Ordering over dates is destroyed the moment each date is replaced by an
    independently drawn one, and a wrong pick books an appointment for a real
    person who is not the one the branch asked about — `classify_break` names
    that `other_person`, and it can only do so because the other four are in
    `case.pii` with their canonical values.
    """
    people = rng.sample(_MALE + _FEMALE + _FOREIGN, 5)
    years = rng.sample([1948, 1957, 1963, 1975, 1988], 5)
    dates = [(rng.randrange(1, 28), rng.randrange(1, 13), year)
             for year in years]
    # Branch codes that cannot occur inside a date in the same case: days stop
    # at 27, months at 12, and the five birth years are fixed.
    branch = rng.choice(("31", "44", "55", "66"))
    said_branch = _words(int(branch)) if register == "voice_raw" else branch
    oldest = years.index(min(years))

    if register == "clean":
        user_parts: list[object] = [
            "Запишите на диспансеризацию самого старшего из клиентов филиала ",
            branch, "."]
    elif register == "chat":
        user_parts = ["запишите на диспансеризацию самого старшего из клиентов "
                      "филиала ", branch]
    elif register == "sloppy":
        user_parts = ["запишите на диспансерзацию самого старшего из клиентов "
                      "филиала ", branch]
    elif register == "voice_itn":
        user_parts = ["запишите на диспансеризацию самого старшего из клиентов "
                      "по филиалу ", branch]
    else:
        user_parts = ["запишите на диспансеризацию самого старшего из клиентов "
                      "по филиалу ", said_branch]
    user_text, _ = _assemble(user_parts)

    names = [_crm_name(surname, first, "", register, rng)
             for surname, first, _ in people]
    # An ISO date is what a CRM import leaves behind, and it is a different
    # shape from the one every Russian form uses. Both belong in the corpus.
    written = [f"{year}-{month:02d}-{day:02d}" if register == "sloppy"
               else f"{day:02d}.{month:02d}.{year}"
               for day, month, year in dates]
    records = [[("name", [(f"name{position}", names[position])]),
                ("birth_date", [(f"born{position}", written[position])])]
               for position in range(5)]
    array_text, array_spans = _assemble(_array(records))

    pii: list[PiiItem] = []
    for position in range(5):
        pii.append(_item(
            f"n{position}", "NAME", f"name{position}", array_spans, array_text,
            names[position], 2, f"person-{position}", "required",
            "client_name" if position == oldest else None))
        pii.append(_item(
            f"d{position}", "DATE", f"born{position}", array_spans, array_text,
            written[position], 2, f"born-{position}", "required",
            "birth_date" if position == oldest else None))
    return _case(
        case_id=f"rank-ordering-{register}-{index:03d}", family="rank",
        scenario="oldest_client", register=register, relation="ordering",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "list_clients", {"branch": branch}),
            _tool_result("c1", "list_clients", array_text),
        ],
        tools=_tools_for(("list_clients", "book_appointment",
                          "notify_customer")),
        pii=pii,
        negatives=[Negative(said_branch, "код филиала", 0)],
        links=_different_chain([f"n{position}" for position in range(5)],
                               "пять разных клиентов филиала"),
        calls=[ExpectedCall(
            name="book_appointment", after_msg=2,
            arguments={"client_name": names[oldest],
                       "birth_date": written[oldest],
                       "service": "диспансеризация"},
            pii_items=[f"n{oldest}", f"d{oldest}"])],
        expected_choice=f"n{oldest}", asr_digits=register == "voice_raw")


def _case_rank_prefix(rng: random.Random, register: str, index: int) -> Case:
    """Five sole traders; which one is registered in Moscow.

    The answer is the first two digits of the ИНН, and a substitute ИНН is
    generated to FAIL its own checksum — it carries no region at all. Twelve
    digits and not ten throughout: a ten-digit ИНН belongs to a legal entity and
    is not personal data, so a corpus that used one would be claiming a
    protection nobody owes.
    """
    surnames = [surname for surname, _, _ in
                rng.sample(_MALE + _FEMALE + _FOREIGN, 5)]
    regions = ["77"] + rng.sample(["50", "78", "66", "23", "61"], 4)
    amount, amount_words = rng.choice(_AMOUNTS)
    said_amount = amount_words if register == "voice_raw" else str(amount)
    # A twelve-digit ИНН contains a five-digit sum about once in two hundred
    # cases, and then «не маскируй эту сумму» would point at two strings. Drawn
    # against the sum rather than declared twice: a coincidence inside a
    # document number is not a second mention of the invoice total.
    inns: list[str] = []
    for region in regions:
        for attempt in range(32):
            candidate = _inn12(rng, region)
            if str(amount) not in candidate:
                inns.append(candidate)
                break
        else:
            raise ValueError(f"no ИНН for region {region} avoids {amount}")
    ordered = [(inns[0], True)] + [(inn, False) for inn in inns[1:]]
    rng.shuffle(ordered)
    moscow = next(position for position, (_, is_moscow) in enumerate(ordered)
                  if is_moscow)

    if register == "clean":
        user_parts: list[object] = [
            "Выставьте счёт на ", str(amount),
            " рублей тому из партнёров-ИП, который зарегистрирован в Москве."]
    elif register == "chat":
        user_parts = ["выставьте счёт на ", str(amount),
                      " тому из ип который московский"]
    elif register == "sloppy":
        user_parts = ["выставте счёт на ", str(amount),
                      " тому из ип который московскй"]
    elif register == "voice_itn":
        user_parts = ["выставьте счёт тому из ип который московский на ",
                      str(amount), " рублей"]
    else:
        user_parts = ["выставьте счёт тому из ип который московский на ",
                      said_amount, " рублей"]
    user_text, _ = _assemble(user_parts)

    records = [[("name", ["ИП ", (f"name{position}", surnames[position])]),
                ("inn", [(f"inn{position}", ordered[position][0])])]
               for position in range(5)]
    array_text, array_spans = _assemble(_array(records))

    pii: list[PiiItem] = []
    for position in range(5):
        pii.append(_item(
            f"n{position}", "NAME", f"name{position}", array_spans, array_text,
            surnames[position], 2, f"trader-{position}", "required", None))
        pii.append(_item(
            f"i{position}", "INN", f"inn{position}", array_spans, array_text,
            ordered[position][0], 2, f"inn-{position}", "required",
            "inn" if position == moscow else None))
    return _case(
        case_id=f"rank-prefix-{register}-{index:03d}", family="rank",
        scenario="moscow_partner", register=register, relation="prefix",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "list_partners", {"period": "квартал"}),
            _tool_result("c1", "list_partners", array_text),
        ],
        tools=_tools_for(("list_partners", "send_invoice", "notify_customer")),
        pii=pii,
        negatives=[Negative(said_amount, "сумма счёта", 0)],
        links=_different_chain([f"i{position}" for position in range(5)],
                               "пять разных ИП: один ИНН на двоих — счёт "
                               "уходит не тому"),
        calls=[ExpectedCall(
            name="send_invoice", after_msg=2,
            arguments={"inn": ordered[moscow][0], "amount": amount},
            pii_items=[f"i{moscow}"])],
        expected_choice=f"i{moscow}", asr_digits=register == "voice_raw")


def _case_rank_frequency(rng: random.Random, register: str, index: int) -> Case:
    """THE CONTROL ARM. Which number ordered most often — derived from equality.

    Every other relation in this family is incompatible with reversible
    pseudonymisation by construction, so a row of zeroes across `rank` would be
    indistinguishable from a broken instrument. Frequency is not: three
    mentions of one number must receive one substitute, the majority survives
    substitution, and a correct gateway scores here. If this is zero too, the
    measurement is wrong before the product is.
    """
    majority = _phone_digits(rng)
    others = [_phone_digits(rng), _phone_digits(rng)]
    slots = ["major"] * 3 + ["minor0", "minor1"]
    rng.shuffle(slots)
    orders = [f"A-{number}" for number in rng.sample(range(1000, 9999), 5)]
    days = rng.choice(("30", "60", "90"))

    if register == "clean":
        user_parts: list[object] = [
            "Перезвоните на тот номер, с которого заказывали чаще всего за ",
            days, " дней."]
    elif register == "chat":
        user_parts = ["перезвоните на тот номер с которого чаще всего "
                      "заказывали за ", days, " дней"]
    elif register == "sloppy":
        user_parts = ["перезвоните на тот номер с которого чаще всего "
                      "заказывли за ", days, " дней"]
    elif register == "voice_itn":
        user_parts = ["перезвоните на тот номер с которого чаще всего "
                      "заказывали за ", days, " дней"]
    else:
        user_parts = ["перезвоните на тот номер с которого чаще всего "
                      "заказывали за ", _words(int(days)), " дней"]
    user_text, _ = _assemble(user_parts)

    digits_at = [majority if slot == "major" else others[int(slot[-1])]
                 for slot in slots]
    written = [_crm_phone(value, register) for value in digits_at]
    records = [[("order", f'"{orders[position]}"'),
                ("phone", [(f"phone{position}", written[position])])]
               for position in range(5)]
    array_text, array_spans = _assemble(_array(records))

    first_major = slots.index("major")
    pii: list[PiiItem] = []
    for position in range(5):
        identity = ("phone-major" if slots[position] == "major"
                    else f"phone-{slots[position]}")
        # Only the FIRST mention of the majority number claims the parameter.
        # The round trip demands the value once; three ids claiming one param
        # would let a scorer count one arrival three times.
        pii.append(_item(
            f"p{position}", "PHONE", f"phone{position}", array_spans,
            array_text, _phone_canonical(digits_at[position]), 2, identity,
            "required", "phone" if position == first_major else None))
    majority_ids = [f"p{position}" for position, slot in enumerate(slots)
                    if slot == "major"]
    minority = next(f"p{position}" for position, slot in enumerate(slots)
                    if slot != "major")
    links = [LinkExpectation(majority_ids[0], other, "same", "",
                             "один и тот же номер в трёх заказах: большинство "
                             "сохраняется только если подмена одна")
             for other in majority_ids[1:]]
    links.append(LinkExpectation(
        majority_ids[0], minority, "different", "",
        "разные номера: слить их — выдумать большинство, которого не было"))
    return _case(
        case_id=f"rank-frequency-{register}-{index:03d}", family="rank",
        scenario="most_frequent_phone", register=register, relation="frequency",
        messages=[
            {"role": "user", "content": user_text},
            _tool_call("c1", "list_recent_orders", {"period": f"{days} дней"}),
            _tool_result("c1", "list_recent_orders", array_text),
        ],
        tools=_tools_for(("list_recent_orders", "notify_customer",
                          "book_appointment")),
        pii=pii,
        negatives=_rank_negatives(orders, "номер заказа"),
        links=links,
        calls=[ExpectedCall(
            name="notify_customer", after_msg=2,
            arguments={"phone": _phone_canonical(majority),
                       "text": "заказ готов к выдаче"},
            pii_items=[majority_ids[0]])],
        expected_choice=majority_ids[0], asr_digits=register == "voice_raw")


# --- the plan and the entry point -----------------------------------------

_RESULT_BUILDERS = {"json_object": _case_json_object,
                    "json_list": _case_json_list,
                    "prose": _case_prose}
_RANK_BUILDERS = {"similarity": _case_rank_similarity,
                  "ordering": _case_rank_ordering,
                  "prefix": _case_rank_prefix,
                  "frequency": _case_rank_frequency}


def _plan(count: int) -> list[tuple[str, str, str, int]]:
    """(family, variant, register, index), ordered so any PREFIX is balanced.

    A truncated run is the normal way this corpus gets used — a tier is a
    prefix, and a developer asking for thirty cases is asking for thirty of
    everything, not for thirty `json_object`s. So the two streams are each
    enumerated index-outermost (one full sweep of registers and variants before
    the second repeat begins) and then interleaved by fair share, which keeps
    the 150:60 ratio at every length rather than only at the end.
    """
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    scale = max(1, -(-count // (_RESULT_REPEATS * len(REGISTERS) * len(_SHAPES)
                                + _RANK_REPEATS * len(REGISTERS)
                                * len(_RELATIONS))))
    streams = [
        [("result", shape, register, index)
         for index in range(_RESULT_REPEATS * scale)
         for shape in _SHAPES
         for register in REGISTERS],
        [("rank", relation, register, index)
         for index in range(_RANK_REPEATS * scale)
         for relation in _RELATIONS
         for register in REGISTERS],
    ]
    ordered: list[tuple[float, str, tuple[str, str, str, int]]] = []
    for stream in streams:
        for position, spec in enumerate(stream):
            ordered.append(((position + 0.5) / len(stream), spec[0], spec))
    ordered.sort(key=lambda entry: (entry[0], entry[1]))
    return [spec for _, _, spec in ordered][:count]


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases of the `result` and `rank` families, in a balanced order.

    Deterministic from the caller's seeded `rng` and from `count` alone: the
    plan is computed before a single random draw, so the n-th case of a run of
    210 is the n-th case of a run of 20 only when the plan agrees — which is why
    the plan is a pure function of `count` and the draws follow it.
    """
    cases: list[Case] = []
    for family, variant, register, index in _plan(count):
        builder = (_RESULT_BUILDERS[variant] if family == "result"
                   else _RANK_BUILDERS[variant])
        cases.append(builder(rng, register, index))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=210)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    cases = build(random.Random(args.seed), args.count)
    problems = [problem for case in cases for problem in validate(case)]

    # Two checks `validate()` structurally cannot make, and both have caught a
    # real corpus bug in this repo's history: ground truth that disagrees with
    # its own text, and a wire form that is not the wire form it claims.
    for case in cases:
        for index, message in enumerate(case.messages):
            content = message["content"]
            if not isinstance(content, str) or not content[:1] in ("{", "["):
                continue
            try:
                json.loads(content)
            except json.JSONDecodeError as error:
                problems.append(f"{case.id}: message {index} is not the JSON it "
                                f"claims to be ({error})")
        for item in case.pii:
            digits = "".join(ch for ch in item.value if ch.isdigit())
            if item.type == "SNILS" and len(digits) == 11:
                body, check = digits[:9], int(digits[9:])
                total = sum(int(d) * (9 - i) for i, d in enumerate(body))
                expected = (0 if total in (100, 101) else total if total < 100
                            else (0 if total % 101 in (100, 101) else total % 101))
                if expected != check:
                    problems.append(f"{case.id}: СНИЛС {item.value!r} fails its "
                                    f"own checksum")
            if item.type == "CARD" and len(digits) == 16:
                total = 0
                for position, digit in enumerate(reversed(digits)):
                    value = int(digit)
                    if position % 2:
                        value *= 2
                        if value > 9:
                            value -= 9
                    total += value
                if total % 10:
                    problems.append(f"{case.id}: карта {item.value!r} fails Luhn")

    # `validate()` demands `expected_choice` only for an INCOMPATIBLE relation,
    # so the control arm — the one case where a correct gateway is supposed to
    # score — is the one place a broken choice would go unnoticed.
    for case in cases:
        if case.family != "rank":
            continue
        if case.expected_choice not in {item.id for item in case.pii}:
            problems.append(f"{case.id}: expected_choice "
                            f"{case.expected_choice!r} is not an item")
        consumed = {item_id for call in case.calls for item_id in call.pii_items}
        if not consumed:
            problems.append(f"{case.id}: a rank case with no consumed item "
                            f"cannot show which value reached the tool")

    by_family: dict[str, int] = {}
    by_register: dict[str, int] = {}
    by_duty: dict[str, int] = {}
    for case in cases:
        by_family[case.family] = by_family.get(case.family, 0) + 1
        by_register[case.register] = by_register.get(case.register, 0) + 1
        for item in case.pii:
            by_duty[item.duty] = by_duty.get(item.duty, 0) + 1

    print(f"случаев:      {len(cases)} {by_family}")
    print(f"по регистрам: {by_register}")
    print(f"ПД:           {sum(len(case.pii) for case in cases)} {by_duty}")
    print(f"негативов:    {sum(len(case.negatives) for case in cases)}")
    print(f"связей:       {sum(len(case.links) for case in cases)}")
    print(f"вызовов:      {sum(len(case.calls) for case in cases)}")
    print(f"символов:     max {max(case_characters(case) for case in cases)} "
          f"(ступень {_LENGTH_RUNG} — {LENGTH_RUNGS[_LENGTH_RUNG]})")
    if problems:
        print(f"НЕВАЛИДНО — {len(problems)} проблем:")
        for problem in problems[:20]:
            print(f"  {problem}")
        return 1
    print("валидно: все случаи прошли schema.validate()")
    if args.out:
        Path(args.out).write_text(
            json.dumps([case.to_json() for case in cases], ensure_ascii=False,
                       indent=1), encoding="utf-8")
        print(f"записано: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
