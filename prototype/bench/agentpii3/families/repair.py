"""The `repair` family — one value said TWICE with a correction between.

WHY IT IS A FAMILY AND NOT A REGISTER TRICK. Two questions are asked here that no
other family can ask, and they pull in opposite directions:

  (a) **The cancelled value is personal data too.** «на ленина четырнадцать, а
      нет, погоди, на ленина сорок» names two flats; the first one was retracted
      by the speaker and NOT by the gateway. Leaving it in the clear because the
      customer changed their mind is a leak with an excuse attached, and it is
      the shape a masker built around «the last mention wins» produces.
  (b) **The tool must receive the SECOND value.** And the gateway is structurally
      inclined to break this one, because the two forms are DESIGNED to be
      similar — the same street with a different house, the same address with a
      different flat, a given name that grew a patronymic. Linking exists to
      resolve «Ленина 14» against a fuller mention said earlier in the same
      conversation; a correction is the one place where the earlier mention is
      the WRONG answer and resolving against it sends the car to the wrong door.

`classify_break` names that outcome without ambiguity: the cancelled value is in
the case, so a restored value equal to it comes back as `other_person` — the tool
executed, returned 200, and acted on a real address that is not the one the
conversation ended on.

WHICH OF THE TWO IS «ДЕЙСТВУЮЩЕЕ». Stated three times, in the three places a
scorer looks, because a case that does not say it is unresolvable:

  * `PiiItem.tool_param` — ONLY the effective item claims one. The cancelled item
    is `required` with no param, which is exactly «mask it, do not expect it
    back».
  * `ExpectedCall.arguments` + `.pii_items` — the argument carries the effective
    canonical and names the effective id.
  * `Case.note` — in words, for the human reading a failure.

That triple is not redundancy for its own sake: `validate` cross-checks all three
(an item claiming a param that no judged argument names is refused, and an
argument that is neither the item's `value` nor its `canonical` is refused), so a
generator that puts the wrong half of a repair into the tool call cannot ship.

WHAT THE LINK COLUMN CLAIMS, PER ARM, and it is not one answer:

  `different`  place_house, place_street, place_flat, name_fix, phone_fix,
               readback — two values, two substitutes. Over-linking here is the
               expensive direction and it is the direction the product leans.
  `same`       re_ask_place, re_ask_name — the operator did not hear and the SAME
               value is said again. A gateway that mints a second substitute for
               a repeated value has broken the identity it exists to preserve,
               and no `different`-only family would notice.
  `unjudged`   name_extend — «анна» then «анна сергеевна». The gateway's rule
               resolves a partial mention against a FULLER ONE SAID EARLIER, and
               here the fuller one comes second, so the rule correctly does not
               fire. Demanding the link would fail a gateway for being right;
               accepting anything would hide a real merge. What is NOT unjudged
               is the round trip: «Анна Сергеевна» has to reach the tool.

THE NEGATIVE THIS FAMILY OWNS. A repair is a SHAPE, and the shape is not evidence
of personal data: «нам к девяти ноль ноль, а нет, к десяти ноль ноль», «заказ
триста двенадцать, то есть триста двадцать», «три четырнадцатый кабинет, в
смысле три пятнадцатый». Every case here carries a REPAIRED NEGATIVE beside its
repaired value, in the same message, so a gateway cannot use «said twice with a
correction between» as a masking cue and pass. In the call corpus a number
standing beside «кабинет» or «отделение» occurs 528 times; this family is where
that number gets said twice.

WHERE THE FORM COMES FROM, and what is NOT here. Every case is `recombined`, and
which mined id it CLAIMS depends on which half of the form carries the case. An
address arm claims the `dispatch.value` pattern its address instantiates, with
the annotation stratum that pattern belongs to — the same convention every other
address-bearing family follows, so a per-shape breakdown across the corpus stays
comparable, and so a bare «<улица> <число>» declares the sampled layer and its
weight of 19.22 instead of borrowing the census the marked forms enjoy. A name or
phone arm claims the DISCOURSE shape — `disc.self_correction` (209),
`disc.re_ask` (165), `name.echo` (46), `err.misheard_name` (1) — because there
the correction IS the observed form: a name has no value pattern beyond «имя» or
«фамилия», and claiming `name.s` would say nothing about what this family does.
Both inventories are checked against `mined/` before a case is built, and the
four discourse shapes are checked to have been EMITTED, because each belongs to
an arm and an unemitted one means an arm stopped running. There is NO `verbatim` arm and
that is a FINDING, not an omission. The shippable corpus (SOVA RuDevices, CC BY
4.0) was swept twice for a correction marker — «то есть», «в смысле», «подожди»,
«а нет», «ой нет», «извините», «перепутал», «стоп» — first with a numeral run on
BOTH sides of it, which returned eleven utterances, then with a repeated content
word across it, which returned about forty. Not one of the fifty names a person
or an address. The nearest real instances are «уже с должна двадцать четвёртого
числа а не двадцать пятого» (a date) and, in the call corpus we may measure with
but not ship, «двести тридцатый а не двести тринадцатый» (a room). So the
MECHANISM is attested in speech and the mechanism ON PERSONAL DATA is not
attested in text we are allowed to distribute — which is exactly why this family
recombines rather than quietly skipping the register, and why a reader should
not take the absence of a `verbatim` arm here as carelessness.

REGISTER. Speech-first by a wider margin than the corpus floor: 60% `voice_raw`,
because a self-correction is a thing a mouth does. `clean` is four cases in a
hundred and ten and exists only to show that a support email saying «прошу
прощения, верный адрес …» does not break.

THE ENTRY POINT is `build(seed, count)`. It owns its RNG —
`random.Random(f"v3:{FAMILY}:{seed}")` — so this family is reproducible on its
own and does not move when a module built before it changes how many draws it
makes.
"""

import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii3.schema import (  # noqa: E402
    unsafe_filler, Case, ExpectedCall, FinalAnswer, InvalidCase,
    LinkExpectation, Message, Negative, PiiItem, Provenance, Source,
    distinct_values, type_denominators, validate,
)

FAMILY = "repair"
TARGET = 110

# The number layer of the RuDevices annotation is 250 read out of 4805, so a
# share computed over it without this factor is wrong by nineteen — and wrong in
# our favour, because the other layer is the one the detector is good at.
NUMBER_SAMPLE_WEIGHT: float = 19.22

# Rides WITH the corpus and not only in this file: the customer receives a
# dataset, never a repository, so an attribution living in the source tree has
# not been given.
ATTRIBUTION: str = "SOVA Dataset / RuDevices, распространяется по CC BY 4.0"

_MINED = Path(__file__).resolve().parent.parent / "mined"
_FILLER_PATH: Path = (Path.home() / ".cache" / "pseudex-bench"
                      / "rudevices_addresses.json")

# The licence NAMED on a recombined case is the corpus the FORM was observed in.
# `compare` argues the other reading — that a pattern is not the expression a
# licence covers — and it is probably right; naming the corpus is the
# conservative version and cannot be wrong, and `direct`, `indirect` and `multi`
# all do it, so the corpus stays internally consistent.
_LICENCE_DISPATCH: str = "CC BY 4.0"
_LICENCE_CALLS: str = "CC BY-NC 4.0"


# --- pools ----------------------------------------------------------------
#
# STREETS ARE REAL and shippable: every name below is a hand-annotated address
# value in SOVA RuDevices. Split by HOW THE NAME IS BUILT, because the mined
# grammar says Russian has two ways and they behave differently under morphology
# — a genitive surname («лермонтова») and an adjective («вольная»), measured 28
# against 14, so the genitive pool is drawn twice as often.
_STREET_GENITIVE: tuple[str, ...] = (
    "ленина", "калашникова", "барышникова", "тимирязева", "дзержинского",
    "баранова", "кирова", "коммунаров", "энгельса", "павлова", "чапаева",
    "репина", "халтурина", "телегина", "петрова", "бабушкина", "металлистов",
    "красина", "котовского", "шумайлова", "циолковского", "некрасова",
    "сабурова", "маяковского", "ломоносова", "орджоникидзе", "гусева",
    "воровского", "гагарина", "грибоедова", "машиностроителей", "строителей",
    "лермонтова", "комиссарова", "челюскинцев", "барамзиной", "люхвинцева",
    "ухтомского", "чехова", "пушкина", "воткинское", "заречное",
)
_STREET_ADJECTIVE: tuple[str, ...] = (
    "пушкинская", "клубная", "удмуртская", "нижняя", "союзная", "восточная",
    "буммашевская", "подлесная", "садовая", "школьная", "вишнёвая", "майская",
    "совхозная", "деловая", "полевая", "выставочная", "камская", "базисная",
    "химзаводская", "зеленоградская", "фруктовая", "фронтовая", "ракетная",
    "молодёжная", "русская", "армейская", "комсомольская", "ключевая",
    "транспортная", "смольный", "загородный", "северный", "воронцовский",
)
# Only the type words the two corpora produced, and each takes the marker the
# mined shape gives it: «улица»/«переулок» take «дом», «проспект»/«проезд» take
# the bare number. Rendering them alike would produce one form the grammar has
# and three it does not.
_TYPE_BEFORE: tuple[str, ...] = ("улица", "переулок", "проспект", "проезд")
_TYPE_WITH_HOUSE_MARKER: frozenset[str] = frozenset({"улица", "переулок"})
_TYPE_AFTER: str = "шоссе"
_SHOSSE_NAMES: frozenset[str] = frozenset({"воткинское", "заречное"})

# A settlement said in front of the street is `optional`, and that is a LEGAL
# category rather than a hedge: a city identifies nobody under 152-ФЗ ст. 3 п. 1,
# so masking it is not an error and missing it is not a leak. Folding it into the
# required span would punish a gateway for correctly leaving it alone. It is a
# separate item with its own span, exactly as the mined `<город> <тип улицы>
# <улица> <число>` shape has it.
#
# «Сочи» and «Самара» are deliberately absent: they are the `city_reference`
# NEGATIVE below, where the same word is a place reference and masking it IS an
# error. One word cannot be optional in one message and forbidden in the next
# without the corpus contradicting itself.
_CITIES: tuple[str, ...] = (
    "воронеж", "ижевск", "казань", "пермь", "тверь", "курск", "брянск",
    "орёл", "рязань", "киров",
)

# NAMES ARE AUTHORED and that is the licence-safe choice rather than a lazy one:
# the surnames the call corpus produced are CC BY-NC and its text may not ship,
# while a common Russian given name is nobody's expression. What IS taken from
# the mining is the SHAPE inventory — which slots are filled, in what order, and
# how often a patronymic contracts.
_GIVEN_M: tuple[str, ...] = (
    "игорь", "олег", "сергей", "андрей", "дмитрий", "максим", "кирилл",
    "руслан", "тимур", "антон", "павел", "роман", "никита", "артём",
    "василий", "валерий", "леонид", "юрий", "борис", "виктор",
)
_GIVEN_F: tuple[str, ...] = (
    "марина", "ольга", "елена", "наталья", "ирина", "светлана", "анна",
    "татьяна", "лариса", "галина", "вера", "зинаида", "полина", "алина",
)
_SURNAME_M: tuple[str, ...] = (
    "кузнецов", "соколов", "лебедев", "ковалёв", "тарасов", "никитин",
    "зайцев", "богданов", "воронов", "фомин", "макаров", "андреев",
    "степанов", "громов", "миронов", "савельев", "белов", "гущин",
)
_PATRONYMIC_M: tuple[str, ...] = (
    "иванович", "петрович", "сергеевич", "николаевич", "валентинович",
    "михайлович", "степанович", "львович", "павлович", "александрович",
    "фёдорович", "викторович",
)
_PATRONYMIC_F: tuple[str, ...] = (
    "ивановна", "петровна", "сергеевна", "николаевна", "валентиновна",
    "михайловна", "павловна", "викторовна",
)
# Fifteen distinct contracted patronymics in the call corpus, and template
# generation produces none of them at all.
_PATRONYMIC_SHORT: dict[str, str] = {
    "павлович": "палыч", "иванович": "иваныч", "михайлович": "михалыч",
    "степанович": "степаныч", "александрович": "саныч",
    "викторович": "викторыч", "николаевич": "николаич",
    "сергеевич": "сергеич", "фёдорович": "фёдорыч",
}

# Real Russian mobile prefixes, so a number that reaches libphonenumber is
# dialable and the phone recognizer is being asked a fair question.
_MOBILE_PREFIX: tuple[str, ...] = (
    "916", "903", "926", "985", "999", "951", "967", "977", "905", "915",
)


# --- numbers said aloud ---------------------------------------------------
#
# A written corpus cannot produce this shape at all — in text a digit is a digit
# — which is why the two engine defects v3 exists for were invisible to v2 BY
# CONSTRUCTION. Spelling happens here, from the integer, so the ground truth is
# what the builder PUT in the string; reading a number back out of a finished
# sentence is the mistake that cost v2's sloppy register 162 of its 183 failures.
_ONES: tuple[str, ...] = (
    "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять", "десять", "одиннадцать", "двенадцать", "тринадцать",
    "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать",
    "девятнадцать",
)
_TENS: tuple[str, ...] = (
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто",
)
_HUNDREDS: tuple[str, ...] = (
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
    "семьсот", "восемьсот", "девятьсот",
)
_ORDINAL_M: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой",
    "седьмой", "восьмой", "девятый",
)
# 22.9% of every «-десят» form in the call corpus arrives contracted. That is
# the NORM of this register, not an exotic corner, and a generator emitting only
# the canonical form measures a dialect nobody speaks on the phone.
_CONTRACTION: dict[str, str] = {
    "пятьдесят": "песят", "шестьдесят": "шеесят", "семьдесят": "семесят",
    "восемьдесят": "восемесят", "тридцать": "триц", "девяносто": "девяно",
}


def _spell_int(value: int) -> str:
    """A cardinal 1..999 in words. Masculine, which is what a house number is."""
    if not 1 <= value <= 999:
        raise ValueError(f"{value} is outside the house-number range 1..999")
    words: list[str] = []
    hundreds, rest = divmod(value, 100)
    if hundreds:
        words.append(_HUNDREDS[hundreds])
    if rest >= 20:
        tens, ones = divmod(rest, 10)
        words.append(_TENS[tens])
        if ones:
            words.append(_ONES[ones])
    elif rest:
        words.append(_ONES[rest])
    return " ".join(words)


def _contract(spoken: str, rng: random.Random) -> str:
    """Apply the register's own contraction to one numeral, sometimes.

    Rate 0.23, from the measured 22.9%. Applied to the SPELLED string and never
    to the integer beside it, so the canonical stays the number that was meant
    while the surface is the one that was said.
    """
    words = spoken.split()
    for index, word in enumerate(words):
        if word in _CONTRACTION and rng.random() < 0.23:
            words[index] = _CONTRACTION[word]
    return " ".join(words)


def _spell_phone(digits: str) -> str:
    """Eleven digits as a dictated run: «восемь девятьсот шестнадцать …».

    Grouped 1-3-3-2-2, which is `num.phone_by_pairs` plus the observation that a
    three-digit group is said as one number. No «плюс семь»: the mined shape
    says so and the corpus never produced one.
    """
    if len(digits) != 11 or not digits.isdigit():
        raise ValueError(f"{digits!r} is not eleven digits")
    groups = (digits[0], digits[1:4], digits[4:7], digits[7:9], digits[9:11])
    return " ".join(_spell_int(int(group)) for group in groups)


# --- the writing errors of the `sloppy` register --------------------------
#
# KEYBOARD-SHAPED, never phonetic. The phonetic errors are already in the two
# speech registers, where they are what the transcriber heard; a typed message
# fails differently, and folding the two would make one of them unmeasurable.
_NEIGHBOUR: dict[str, str] = {
    "а": "в", "б": "ю", "в": "а", "г": "н", "д": "л", "е": "к", "ж": "э",
    "з": "х", "и": "м", "й": "ц", "к": "е", "л": "д", "м": "и", "н": "г",
    "о": "р", "п": "р", "р": "о", "с": "ч", "т": "ь", "у": "ц", "ф": "ы",
    "х": "з", "ц": "у", "ч": "с", "ш": "щ", "щ": "ш", "ы": "ф", "ь": "т",
    "э": "ж", "ю": "б", "я": "ф",
}


def _typo(word: str, rng: random.Random) -> str:
    """One keyboard-shaped error inside one word, or the word unchanged.

    Four kinds and nothing else: a doubled letter, a dropped letter, a
    transposition, an adjacent-key substitution. The result is checked to be
    alphabetic and different — a mutation that silently returns its input turns
    the `sloppy` register into `chat` and the corpus would not notice.
    """
    if len(word) < 4 or not word.isalpha():
        return word
    kind = rng.randrange(4)
    position = rng.randrange(1, len(word) - 1)
    if kind == 0:
        out = word[:position] + word[position] + word[position:]
    elif kind == 1:
        out = word[:position] + word[position + 1:]
    elif kind == 2:
        out = (word[:position] + word[position + 1] + word[position]
               + word[position + 2:])
    else:
        letter = _NEIGHBOUR.get(word[position], word[position])
        out = word[:position] + letter + word[position + 1:]
    if out == word or not out.isalpha():
        return word
    return out


def _typo_phrase(phrase: str, rng: random.Random) -> str:
    """A typo in exactly one word of a multi-word value.

    One, not several: «Фёдо ров Кирилл» needed four signals to be reachable, and
    two errors in one value is a string no reader would repair either, so a case
    built that way measures nothing anybody has to get right.
    """
    words = phrase.split(" ")
    candidates = [index for index, word in enumerate(words) if len(word) >= 4]
    if not candidates:
        return phrase
    index = rng.choice(candidates)
    words[index] = _typo(words[index], rng)
    return " ".join(words)


# --- negatives, and this family's are REPAIRED ----------------------------
#
# HALF THE PRECISION MEASUREMENT, and here they carry a claim no other family
# can make: **a value said twice with a correction between is not thereby
# personal data.** A gateway that learns the repair shape as a masking cue
# passes every positive case in this file and fails every one of these, and no
# single number would separate the two.
#
# Three surfaces per row, because a negative has to be LEGAL in the register it
# is dropped into or `_register_problems` refuses the case carrying it: the
# spoken column has no digit (`voice_raw` allows none), the written column has no
# leading capital, the literary column has both a capital and a full stop.
@dataclass(frozen=True)
class _Neg:
    family: str
    carrier: tuple[str, str]      # (spoken/typed, literary)
    first: tuple[str, str, str]   # (spoken, written, literary) — the cancelled
    second: tuple[str, str, str]  # the corrected one; ("", "", "") = not repaired
    why: str


# Safe to stand in the SAME message as an address. The rejected candidates are
# named because the rejection is the interesting part: «шестой подъезд» and
# «квартиру» next to «ленина сорок» would form «ленина сорок шестой подъезд»,
# which is a real address in the mined grammar — the detector masking it would be
# RIGHT, and the negative would be scoring a correct gateway as a false mask.
# Those live in `_ALONE` and only ever appear where no address does.
_REPAIRED: tuple[_Neg, ...] = (
    _Neg("time_of_day", ("подача", "Подача"),
         ("к девяти ноль ноль", "к 9 00", "к 9:00"),
         ("к десяти ноль ноль", "к 10 00", "к 10:00"),
         "время подачи; ноли проговариваются словом и дают пробег числительных, "
         "а поправка не делает его номером"),
    _Neg("time_of_day", ("выезжаем", "Выезжаем"),
         ("в восемь ноль ноль", "в 8 00", "в 8:00"),
         ("в девять ноль ноль", "в 9 00", "в 9:00"),
         "второе время в той же реплике — час выезда, не идентификатор"),
    _Neg("order_number", ("это", "Это"),
         ("заказ триста двенадцать", "заказ 312", "заказ 312"),
         ("заказ триста двадцать", "заказ 320", "заказ 320"),
         "продиктованный номер заказа — тот самый дефект, который однажды уехал "
         "в продакшн; переспрос его персональным не делает"),
    _Neg("order_number", ("номер заявки", "Номер заявки"),
         ("сорок семь", "47", "47"), ("сорок восемь", "48", "48"),
         "короткая заявка рядом с адресом, названная дважды"),
    _Neg("room_number", ("нам в", "Нам в"),
         ("три четырнадцатый кабинет", "кабинет 314", "кабинет 314"),
         ("три пятнадцатый кабинет", "кабинет 315", "кабинет 315"),
         "номер кабинета — крупнейший источник ложных срабатываний в этом "
         "регистре: 528 случаев числа рядом с «кабинет» или «отделение»"),
    _Neg("room_number", ("мы из", "Мы из"),
         ("второго отделения", "второго отделения", "второго отделения"),
         ("третьего отделения", "третьего отделения", "третьего отделения"),
         "отделение — место, но не чей-то адрес"),
    _Neg("quantity", ("везём", "Везём"),
         ("пять коробок", "5 коробок", "5 коробок"),
         ("шесть коробок", "6 коробок", "6 коробок"),
         "количество мест, не номер дома"),
    _Neg("quantity", ("у нас", "У нас"),
         ("двенадцать филиалов", "12 филиалов", "12 филиалов"),
         ("тринадцать филиалов", "13 филиалов", "13 филиалов"),
         "количество, поправленное вслух"),
    _Neg("fare", ("у вас теперь", "У вас теперь"),
         ("проезд пятьдесят рублей", "проезд 50 рублей", "проезд 50 рублей"),
         ("проезд шестьдесят рублей", "проезд 60 рублей", "проезд 60 рублей"),
         "«проезд» здесь плата, а не тип улицы — и поправленная плата тем более"),
    _Neg("measure", ("там участок", "Там участок"),
         ("пять гектаров", "5 гектаров", "5 гектаров"),
         ("шесть гектаров", "6 гектаров", "6 гектаров"),
         "единица измерения после числа — не номер дома"),
    _Neg("measure", ("там всего", "Там всего"),
         ("двадцать квадратов", "20 квадратов", "20 квадратов"),
         ("тридцать квадратов", "30 квадратов", "30 квадратов"),
         "площадь квартиры, не её номер"),
    _Neg("city_reference", ("мы вообще не из", "Мы вообще не из"),
         ("сочи", "сочи", "Сочи"), ("самары", "самары", "Самары"),
         "город как место, а не как чей-то адрес; поправка меняет город и не "
         "делает его персональным"),
)

# Only ever in a message that carries NO address. Each one would be legally
# absorbed into a neighbouring address span, and a negative a correct gateway
# must mask is not a negative, it is a corpus bug.
_ALONE: tuple[_Neg, ...] = (
    _Neg("street_no_name", ("мы стоим на", "Мы стоим на"),
         ("улице", "улице", "улице"), ("", "", ""),
         "«улица» без названия — двор, погода, прогулка"),
    _Neg("street_no_name", ("тут не пройти по", "Тут не пройти по"),
         ("улицам", "улицам", "улицам"), ("", "", ""),
         "«по улицам ходить» — не адрес"),
    _Neg("flat_as_home", ("мы недавно сняли", "Мы недавно сняли"),
         ("квартиру", "квартиру", "квартиру"), ("", "", ""),
         "«квартира» без номера — жильё, покупка, уборка"),
    _Neg("entrance_no_street", ("выйдем в", "Выйдем в"),
         ("шестой подъезд", "6 подъезд", "6-й подъезд"),
         ("седьмой подъезд", "7 подъезд", "7-й подъезд"),
         "адресный хвост без адреса: улицы в реплике нет, и переспрос её не "
         "добавляет"),
)


def _neg_surface(negative: _Neg, register: str, which: str) -> str:
    column = negative.first if which == "first" else negative.second
    if register == "voice_raw":
        return column[0]
    if register == "clean":
        return column[2]
    return column[1]


def _neg_carrier(negative: _Neg, register: str) -> str:
    return negative.carrier[1] if register == "clean" else negative.carrier[0]


def _pick_negative(rows: tuple[_Neg, ...], register: str, repaired: bool,
                   need_digit: bool, rng: random.Random) -> _Neg:
    """One negative with the arity we need, legal in this register.

    `need_digit` is not a convenience. `voice_itn` is DEFINED by inverse text
    normalisation being ON, and the schema refuses a voice_itn case whose user
    text carries no digit as «a voice_raw case in disguise» — so where the
    protected value is a NAME, the negative is the only thing that can honestly
    supply one and the draw has to narrow. Where the value is an address or a
    phone the digit is already there, and narrowing anyway would quietly delete
    «второго отделения» from the whole register.
    """
    live = [row for row in rows if bool(row.second[0]) == repaired]
    if need_digit and register == "voice_itn":
        live = [row for row in live
                if any(ch.isdigit() for ch in _neg_surface(row, register, "first"))]
    if not live:
        raise InvalidCase(
            f"no {'repaired' if repaired else 'plain'} negative is legal in "
            f"register {register!r}; the table and the register mix disagree")
    return rng.choice(live)


# --- filler ---------------------------------------------------------------
#
# NINE REPLIES IN TEN CARRY NO PERSONAL DATA AT ALL — a measured floor of 1.995%
# at the call corpus and 0.939% at the dispatch one. A long case whose every line
# holds a datum is not this register, and it inflates recall and precision at the
# same time. The filler is therefore REAL: hand-labelled «не адрес» replies from
# SOVA RuDevices, CC BY 4.0, which is the licence that lets them ship.
#
# The filter is stated rather than assumed, because a filler line quietly holding
# an unlabelled datum is a leak the corpus cannot see — the gateway masks it, the
# scorer counts a false mask, and the corpus was wrong. No digit, no Latin, no
# numeral run of two, none of the words a negative family is built on, no pool
# name, no obscenity.
_OBSCENE: tuple[str, ...] = (
    "бля", "хуй", "хуё", "хуе", "пизд", "еба", "ёба", "ебы", "ёбы", "ебан",
    "ёбан", "нахуй", "похуй", "заеб", "мудак", "гандон", "срат", "говн",
    "педик", "пидор", "пидар", "шлюх", "трахн", "жоп", "нахер", "сук",
)
_NEG_WORDS: tuple[str, ...] = (
    "улиц", "квартир", "подъезд", "проезд", "корпус", "кабинет", "отделен",
    "этаж", "дом", "заказ", "гектар", "квадрат", "рубл", "филиал", "коробк",
)

# Written by hand for the two registers the speech corpora cannot supply.
_FILLER_CLEAN: tuple[str, ...] = (
    "Добрый день. Уточните, пожалуйста, сроки.",
    "Спасибо, я подожду ответа.",
    "Мне удобнее вечером, если это возможно.",
    "Хорошо, тогда договорились.",
    "Пока ничего не пришло, проверьте ещё раз.",
    "Извините за задержку, был на встрече.",
    "Понял вас, продолжайте.",
    "Это срочно, поэтому и пишу.",
    "У меня был похожий случай в прошлом месяце.",
    "Давайте так и оформим.",
)
_ACK_SPOKEN: tuple[str, ...] = (
    "поняла", "записываю", "секунду", "да слушаю", "ага", "хорошо",
    "минутку", "так", "приняла", "уточняю",
)
_ACK_CLEAN: tuple[str, ...] = (
    "Принято.", "Секунду, проверяю.", "Хорошо, записал.", "Уточняю.",
    "Понял вас.",
)


def _filler_pool() -> tuple[str, ...]:
    """Real «не адрес» replies, mechanically filtered. Raises if the cache is gone.

    Fail-closed rather than falling back to authored prose: a corpus whose filler
    silently stopped being real would go on printing numbers, and the register is
    the one thing v3 exists to get right.

    THE NAME AND NUMBER SCREEN IS `schema.unsafe_filler`, called and not
    restated. This was the sixth private copy of one idea with a sixth private
    name list, and «иван» was in none of them — «иван забыл закрыть балконную
    дверь» stood in two cases as unclaimed filler. One place is what makes a word
    added once protect all eleven families.
    """
    if not _FILLER_PATH.exists():
        raise InvalidCase(
            f"{_FILLER_PATH} is missing; the repair family draws its filler from "
            f"the hand-labelled RuDevices rows and will not invent it — see "
            f"CLAUDE.md for how to restore ~/.cache/pseudex-bench/")
    rows = json.loads(_FILLER_PATH.read_text(encoding="utf-8"))
    names = set(_GIVEN_M) | set(_GIVEN_F) | set(_SURNAME_M)
    kept: list[str] = []
    for row in rows:
        if row["label"] != "не адрес":
            continue
        text = str(row["text"])
        if any(ch.isdigit() or ch == "@" or ("a" <= ch.lower() <= "z")
               for ch in text):
            continue
        if any(bad in text for bad in _OBSCENE):
            continue
        if any(bad in text for bad in _NEG_WORDS):
            continue
        words = text.split()
        if not 4 <= len(words) <= 20:
            continue
        if any(word in names for word in words):
            continue
        if unsafe_filler(text):
            continue
        kept.append(text)
    if len(kept) < 60:
        raise InvalidCase(
            f"only {len(kept)} filler replies survived the filter; a long case "
            f"cannot be padded with real speech and must not be padded with ours")
    return tuple(kept)


# --- mined shape ids ------------------------------------------------------
#
# TWO INVENTORIES, AND A CASE CLAIMS FROM WHICHEVER HALF CARRIES IT. `_SHAPES`
# holds the discourse patterns — what a correction sounds like — and the name and
# phone arms claim those, because a name has no value pattern beyond «имя» and
# `name.s` would say nothing about what this family does. `_VALUE_SHAPES` holds
# the address patterns the renderer may produce, and the address arms claim
# those, which is the convention every other address-bearing family follows and
# is what keeps a per-shape breakdown across the corpus comparable.
#
# Both are checked against `mined/` before a case is built, so «the form came
# from real speech» is something somebody can verify rather than an assertion —
# 1070 of v2's 1334 cases carried the assertion with nothing behind it and there
# was no way to tell from the file.
_SHAPES: tuple[str, ...] = (
    "calls:disc.self_correction",
    "calls:disc.re_ask",
    "calls:name.echo",
    "calls:err.misheard_name",
)

_VALUE_SHAPES: tuple[str, ...] = (
    "dispatch.value:<улица> <число прописью>",
    "dispatch.value:<улица> <число прописью> <литера>",
    "dispatch.value:<улица> <число прописью> <порядковое> подъезд",
    "dispatch.value:<улица> <число прописью> <литера> <порядковое> подъезд",
    "dispatch.value:<улица> <число прописью> квартира <число прописью>",
    "dispatch.value:улица <улица> дом <число прописью>",
    "dispatch.value:переулок <улица> дом <число прописью>",
    "dispatch.value:проспект <улица> <число прописью>",
    "dispatch.value:проезд <улица> <число прописью>",
    "dispatch.value:<улица> шоссе <число прописью>",
)


def _known_shapes() -> frozenset[str]:
    calls = json.loads((_MINED / "calls_grammar.json").read_text(encoding="utf-8"))
    dispatch = json.loads(
        (_MINED / "dispatch_grammar.json").read_text(encoding="utf-8"))
    known = {f"calls:{shape['id']}" for shape in calls["shapes"]}
    for stratum in dispatch["value_shapes"].values():
        for shape in stratum:
            known.add(f"dispatch.value:{shape['pattern']}")
    for shape in dispatch["reply_shapes"]:
        known.add(f"dispatch.reply:{shape['pattern']}")
    return frozenset(known)


def _claimable() -> frozenset[str]:
    return frozenset(_SHAPES) | frozenset(_VALUE_SHAPES)


def _verify_shapes() -> None:
    missing = sorted(_claimable() - _known_shapes())
    if missing:
        raise InvalidCase(
            f"these shape ids are not in mined/: {missing} — the family would "
            f"claim a form the grammar cannot show")


def _verify_emitted_shapes(cases: list[Case]) -> None:
    """Every claimed shape must be declared, and every declared one emitted.

    Both directions, because they catch different mistakes. A claim the
    inventory does not know is a renderer that drifted; a declaration nothing
    emits is an inventory describing a family that no longer exists.

    Asymmetric on purpose. The four DISCOURSE shapes are structural — one per arm
    group — so an unemitted one means an arm stopped running, and that is worth a
    refusal. A VALUE shape can be rare by construction (a house letter is 11% of
    draws, and a letter with an entrance is 11% of a third), so `main` reports
    those and nothing fails: a build that broke because a seed did not draw one
    would be a brittle test of the RNG rather than of the inventory.
    """
    claimed = {case.provenance.shape for case in cases if case.provenance.shape}
    stray = sorted(claimed - _claimable())
    if stray:
        raise InvalidCase(f"cases claim undeclared shapes: {stray}")
    unused = sorted(set(_SHAPES) - claimed)
    if unused:
        raise InvalidCase(
            f"discourse shapes declared and never emitted: {unused} — each one "
            f"belongs to an arm, so an unemitted one is an arm that stopped")


# --- tools ----------------------------------------------------------------
#
# Two, and both take a personal value as an argument, which is what separates
# this from a NER corpus: the question is not «is this an address» but «does the
# car go to the house the customer ended on». `comment` and `channel` are passed
# and NOT judged, deliberately — τ²-bench's `compare_args` exists because a
# benchmark comparing every argument fails a gateway for a model's choice.
def _tool(name: str, description: str,
          properties: dict[str, str], required: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": "string", "description": text}
                    for key, text in properties.items()
                },
                "required": list(required),
            },
        },
    }


_TOOL_RIDE = _tool(
    "create_ride", "Оформить подачу машины по адресу, который клиент подтвердил.",
    {"address": "Адрес подачи в том виде, на котором клиент остановился.",
     "entrance": "Подъезд, если назван.",
     "comment": "Комментарий диспетчера."},
    ("address",))
_TOOL_CLIENT = _tool(
    "find_client", "Найти карточку клиента по имени или телефону.",
    {"name": "Имя клиента.", "phone": "Телефон клиента.",
     "channel": "Канал обращения."},
    ())

_TOOLS_PLACE: tuple[dict[str, Any], ...] = (_TOOL_RIDE, _TOOL_CLIENT)
_TOOLS_PERSON: tuple[dict[str, Any], ...] = (_TOOL_CLIENT, _TOOL_RIDE)

# The integrator's own prompt. No personal data in it — the corpus does not test
# whether a system message is masked, because whether it is depends on the
# deployment leg and `validate` refuses an item that sits in one.
#
# «на последнем названном значении» is in the prompt on purpose. The family
# measures the GATEWAY, so the model must not be left to guess which half of a
# correction counts; a case that fails because the model chose the cancelled
# value would be scoring model behaviour, which the owner ruled out of scope.
_SYSTEM_DISPATCH = (
    "ты диспетчер службы такси. клиент может поправить себя на ходу — всегда "
    "работай с последним названным значением. вызывай create_ride, когда адрес "
    "подтверждён."
)
_SYSTEM_SUPPORT = (
    "ты оператор поддержки. клиент может поправить себя на ходу — всегда бери "
    "последнее названное значение. проверяй данные клиента инструментами."
)


# --- assembly -------------------------------------------------------------
#
# OFFSETS ARE COUNTED AS THE STRING IS BUILT. Nothing here searches a finished
# message for a value it already knows it put there — that is the bug that ate
# 162 of v2's 183 sloppy failures, twice, and it is invisible from the outside
# because a searched offset is always somewhere.
@dataclass(frozen=True)
class _Piece:
    tag: str     # "" for prose; otherwise the id an item or negative will use
    text: str


@dataclass(frozen=True)
class _Msg:
    key: str                                # stable id, so items survive padding
    role: str
    text: str
    marks: dict[str, tuple[int, int]]
    name: str
    source: Source | None


_GLUE: frozenset[str] = frozenset(",.?!:;")


def _line(pieces: tuple[_Piece, ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Join pieces with single spaces and report where each tagged one landed.

    A piece opening with punctuation is GLUED to what came before it, so the
    literary register can write «Ленина, 25.» without a stray space and without a
    second code path that recomputes offsets afterwards.
    """
    out: list[str] = []
    marks: dict[str, tuple[int, int]] = {}
    position = 0
    for piece in pieces:
        if not piece.text:
            continue
        if out and piece.text[0] not in _GLUE:
            out.append(" ")
            position += 1
        if piece.tag:
            if piece.tag in marks:
                raise InvalidCase(f"tag {piece.tag!r} used twice in one message")
            marks[piece.tag] = (position, position + len(piece.text))
        out.append(piece.text)
        position += len(piece.text)
    return "".join(out), marks


def _msg(key: str, role: str, pieces: tuple[_Piece, ...], name: str) -> _Msg:
    text, marks = _line(pieces)
    return _Msg(key=key, role=role, text=text, marks=marks, name=name,
                source=None)


def _system(text: str) -> _Msg:
    return _msg("sys", "system", (_Piece("", text),), "")


def _locate(messages: tuple[_Msg, ...], key: str, tag: str) -> tuple[int, int, int]:
    """(message index, start, end) for a tagged piece. Raises if it moved."""
    for index, message in enumerate(messages):
        if message.key != key:
            continue
        if tag not in message.marks:
            raise InvalidCase(f"message {key!r} has no tag {tag!r}")
        start, end = message.marks[tag]
        return index, start, end
    raise InvalidCase(f"no message keyed {key!r}")


# --- rendering a place ----------------------------------------------------

@dataclass(frozen=True)
class _Place:
    street: str
    type_word: str     # "" | one of _TYPE_BEFORE | "шоссе" (which goes after)
    house: int
    entrance: int      # 0 = not said
    letter: str        # "" | "а" | "б" | "в"
    flat: int          # 0 = not said


def _type_words_for(street: str) -> tuple[str, ...]:
    """Type words that AGREE with this street name. «Проезд Ракетная» is not Russian.

    A genitive surname takes any of them («улица Ленина», «проспект
    Калашникова»), a feminine adjective takes only «улица», a masculine one takes
    the masculine types. Drawing the type word freely produced «Набережная
    Ракетная», which is not a form any recognizer will ever meet and therefore
    not a form worth measuring on.
    """
    if street in _SHOSSE_NAMES:
        return (_TYPE_AFTER,)
    if street.endswith(("ая", "яя")):
        return ("улица",)
    if street.endswith(("ый", "ий", "ой")):
        return ("переулок", "проезд")
    return _TYPE_BEFORE


def _draw_street(rng: random.Random, avoid: str) -> str:
    """One street name, never the one it is told to avoid.

    Two thirds genitive, one third adjectival — 28 against 14 in the dispatch
    corpus. The `avoid` argument is what keeps a `different` claim honest: two
    mentions that render alike are not a correction, they are a repetition, and
    the case would be asking nothing.
    """
    for _ in range(12):
        pool = _STREET_GENITIVE if rng.random() < 0.667 else _STREET_ADJECTIVE
        street = rng.choice(pool)
        if street != avoid:
            return street
    raise InvalidCase(f"could not draw a street other than {avoid!r}")


def _draw_place(rng: random.Random, form: str, avoid_street: str) -> _Place:
    """One address in one of four mined forms.

    `bare` is two thirds of the corpus — 113 of 169 mentions in the dispatch set
    carry no street-type word at all — and it is also the stratum a marker filter
    cannot see, which is why `_selection_for` weights it as the sampled layer
    rather than the census one.
    """
    street = _draw_street(rng, avoid_street)
    house = rng.choice((rng.randrange(1, 30), rng.randrange(1, 100),
                        rng.randrange(100, 200)))
    letter = rng.choice(("а", "б", "в")) if rng.random() < 0.11 else ""
    if form == "marked":
        return _Place(street=street, type_word=rng.choice(_type_words_for(street)),
                      house=house, entrance=0, letter="", flat=0)
    if form == "entrance":
        return _Place(street=street, type_word="", house=house,
                      entrance=rng.randrange(1, 9), letter=letter, flat=0)
    if form == "flat":
        return _Place(street=street, type_word="", house=house, entrance=0,
                      letter="", flat=rng.randrange(1, 200))
    if form == "bare":
        return _Place(street=street, type_word="", house=house, entrance=0,
                      letter=letter, flat=0)
    raise InvalidCase(f"unknown place form {form!r}")


def _place_shape(place: _Place) -> str:
    """The mined value pattern this place instantiates. One pattern, exactly.

    Written from the same rules as `_place_words`, so the id cannot drift from
    the string it describes, and checked against `_VALUE_SHAPES` here rather than
    only at build: a pattern that is right in the inventory and wrong in the
    renderer is the failure this function exists to make impossible.
    """
    if place.flat:
        shape = "dispatch.value:<улица> <число прописью> квартира <число прописью>"
    elif place.type_word == _TYPE_AFTER:
        shape = "dispatch.value:<улица> шоссе <число прописью>"
    elif place.type_word in _TYPE_WITH_HOUSE_MARKER:
        shape = f"dispatch.value:{place.type_word} <улица> дом <число прописью>"
    elif place.type_word:
        shape = f"dispatch.value:{place.type_word} <улица> <число прописью>"
    elif place.entrance and place.letter:
        shape = ("dispatch.value:<улица> <число прописью> <литера> "
                 "<порядковое> подъезд")
    elif place.entrance:
        shape = "dispatch.value:<улица> <число прописью> <порядковое> подъезд"
    elif place.letter:
        shape = "dispatch.value:<улица> <число прописью> <литера>"
    else:
        shape = "dispatch.value:<улица> <число прописью>"
    if shape not in _VALUE_SHAPES:
        raise InvalidCase(f"renderer produced {shape!r}, which is not declared")
    return shape


def _selection_for(place: _Place) -> tuple[str, float]:
    """Which annotation stratum this rendering would have been read from.

    THE MOST EXPENSIVE LESSON IN THE PROJECT, turned into two lines. The `marker`
    layer is selected by the street-type words and house markers the DETECTOR
    also reads, so a type measured only there is measured on the utterances the
    engine was already good at — the first voice set reported 100% where the
    truth was 38.6%. A bare «<улица> <число>» falls outside it and is weighted by
    the inverse sampling fraction of the layer it does fall in.
    """
    if place.type_word or place.flat or place.entrance:
        return "marker", 1.0
    return "random", NUMBER_SAMPLE_WEIGHT


def _place_words(place: _Place, house: str, flat: str) -> list[str]:
    """The word sequence of one rendering, numbers already spelled.

    Shared by every register, so the shape id, the canonical and the three
    surfaces cannot disagree about which parts were said. The literary renderer
    differs in PUNCTUATION and CASE, never in content.
    """
    if place.flat:
        return [place.street, house, "квартира", flat]
    if place.type_word == _TYPE_AFTER:
        return [place.street, _TYPE_AFTER, house]
    if place.type_word in _TYPE_WITH_HOUSE_MARKER:
        return [place.type_word, place.street, "дом", house]
    if place.type_word:
        return [place.type_word, place.street, house]
    words = [place.street, house] + ([place.letter] if place.letter else [])
    if place.entrance:
        words += [_ORDINAL_M[place.entrance], "подъезд"]
    return words


def _render_place_clean(place: _Place) -> str:
    """The web-form rendering: capitals, commas, abbreviations.

    BUILT from the same rules as `_place_words`, not post-processed from the
    spoken string. An earlier version capitalised and inserted commas by
    rewriting the finished text, which is the same class of mistake as searching
    it for offsets: the rule the rewrite encodes drifts from the rule that
    produced the words. The type word stays lower case, because that is how an
    address line is written — «улица Ленина», not «Улица Ленина».
    """
    street = place.street.capitalize()
    house = f"{place.house}{place.letter}"
    if place.flat:
        return f"{street}, {house}, кв. {place.flat}"
    if place.type_word == _TYPE_AFTER:
        return f"{street} {_TYPE_AFTER}, {house}"
    if place.type_word in _TYPE_WITH_HOUSE_MARKER:
        return f"{place.type_word} {street}, д. {house}"
    if place.type_word:
        return f"{place.type_word} {street}, {house}"
    if place.entrance:
        return f"{street}, {house}, подъезд {place.entrance}"
    return f"{street}, {house}"


def _render_place(place: _Place, register: str, rng: random.Random) -> str:
    """The address as one string, in one register."""
    if register == "clean":
        return _render_place_clean(place)
    spoken = register == "voice_raw"
    house = (_contract(_spell_int(place.house), rng) if spoken
             else str(place.house))
    flat = ""
    if place.flat:
        flat = (_contract(_spell_int(place.flat), rng) if spoken
                else str(place.flat))
    text = " ".join(_place_words(place, house, flat))
    if register == "sloppy":
        text = _typo_phrase(text, rng)
    return text


def _render_city(city: str, register: str) -> str:
    """The settlement in front of the street, in the register that says it."""
    return f"г. {city.capitalize()}" if register == "clean" else city


def _place_canonical(place: _Place) -> str:
    """What a CRM would store OF WHAT WAS SAID. Never more than that.

    It IS the literary rendering of the same word list, and that is the point
    rather than a shortcut: a canonical assembled independently can claim a part
    the mention never carried, and the ground truth would then score the gateway
    on information the conversation did not have.
    """
    return _render_place_clean(place)


# --- rendering a person ---------------------------------------------------

@dataclass(frozen=True)
class _Person:
    given: str
    surname: str
    patronymic: str
    female: bool


def _draw_person(rng: random.Random, female: bool, avoid: str) -> _Person:
    """One person, avoiding a surname already in play.

    The slot COUNT is not fixed and neither is the order — a surname alone 350, a
    given name alone 255, given + patronymic 109, surname + given + patronymic 23
    in the call corpus. A generator that always emits «Фамилия Имя Отчество» is
    testing one of six shapes and the rarest of them.
    """
    for _ in range(12):
        if female:
            person = _Person(given=rng.choice(_GIVEN_F),
                             surname=rng.choice(_SURNAME_M) + "а",
                             patronymic=rng.choice(_PATRONYMIC_F), female=True)
        else:
            person = _Person(given=rng.choice(_GIVEN_M),
                             surname=rng.choice(_SURNAME_M),
                             patronymic=rng.choice(_PATRONYMIC_M), female=False)
        if person.surname != avoid and person.given != avoid:
            return person
    raise InvalidCase(f"could not draw a person unlike {avoid!r}")


def _render_person(person: _Person, form: str, register: str,
                   rng: random.Random) -> tuple[str, str]:
    """(surface, canonical) for one way of naming this person.

    THE CANONICAL IS BUILT FROM THE SAME PARTS. A reply that carried a given name
    and a patronymic must not have a surname demanded back — that is the ground
    truth scoring the gateway on information the conversation never had, and
    AgentPII-RU has paid for it once already.

    Every form here is NOMINATIVE. An oblique mention («позовите игоря») is a
    real and common shape, and it is deliberately not in this family: its round
    trip measures `to_nominative`, which `transfer` and `crowd` already ask
    about, and mixing it in here would make a failed repair and a failed
    declension the same number.
    """
    if form == "surname":
        words = (person.surname,)
    elif form == "given":
        words = (person.given,)
    elif form == "given_patronymic":
        patronymic = person.patronymic
        if not person.female and rng.random() < 0.35:
            patronymic = _PATRONYMIC_SHORT.get(patronymic, patronymic)
        words = (person.given, patronymic)
    elif form == "given_surname":
        words = (person.given, person.surname)
    elif form == "surname_given":
        words = (person.surname, person.given)
    else:
        raise InvalidCase(f"unknown name form {form!r}")
    canonical = " ".join(word.capitalize() for word in words)
    text = " ".join(words)
    if register == "clean":
        text = canonical
    if register == "sloppy":
        text = _typo_phrase(text, rng)
    return text, canonical


# --- rendering a phone ----------------------------------------------------

def _draw_phone(rng: random.Random, avoid: str) -> str:
    """Eleven digits on a real Russian mobile prefix, no leading zero in a group.

    Real prefixes because libphonenumber is the first recognizer that sees it,
    and no leading zeros because a group like «05» is said «ноль пять» and the
    spelling table has one rule per group, not two. `avoid` guarantees the pair
    differs in the last ten digits, which is what `same_value` compares a phone
    on — two numbers differing only in the country code are the SAME number and a
    `different` claim over them would be false.
    """
    for _ in range(24):
        digits = ("8" + rng.choice(_MOBILE_PREFIX)
                  + str(rng.randrange(100, 1000)) + str(rng.randrange(10, 100))
                  + str(rng.randrange(10, 100)))
        if digits[1:] != avoid[1:]:
            return digits
    raise InvalidCase("could not draw a phone unlike the one already in play")


def _render_phone(digits: str, register: str, rng: random.Random) -> str:
    """The shape the number arrives in, per register.

    `voice_raw` is absent from the phone arm's plan, so there is no spelled
    branch here: a number whose every mention is written out is the `spoken_id`
    family's question, and answering it in two places would make one of the two
    unreadable.
    """
    body = digits[1:]
    if register == "clean":
        return f"+7 {body[:3]} {body[3:6]}-{body[6:8]}-{body[8:]}"
    if register == "voice_itn":
        return digits
    return rng.choice((digits, f"8 {body[:3]} {body[3:6]} {body[6:8]} {body[8:]}",
                       f"+7{body}"))


def _phone_canonical(digits: str) -> str:
    return f"+7{digits[1:]}"


# --- the words around the value -------------------------------------------
#
# Drawn from the mined openers, where 101 of 154 address replies begin with NO
# introduction at all (65.6%). A generator that always says «здравствуйте, мой
# адрес» writes the form the corpus produced twenty-six times in a hundred and
# fifty-four, and it is the form a cue-word gate finds easiest.
_OPENERS_SPOKEN: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("а", 4), ("алло здравствуйте", 3),
    ("доброе утро", 2), ("здравствуйте а", 2), ("аа", 2), ("а здравствуйте", 2),
    ("девушка", 1), ("алло", 1), ("так", 1), ("ээ", 1),
)
_OPENERS_TYPED: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("привет", 12), ("добрый день", 8),
    ("а", 4),
)
_OPENERS_CLEAN: tuple[str, ...] = ("Добрый день.", "Здравствуйте.", "")

# `immediately_before_the_value` in the dispatch lexicon: 95 of 169 addresses
# open the reply with nothing at all in front of them, and — separately measured
# — only 10 of 169 carry a PREPOSITION in front of the value («на» 9, «по» 1).
#
# The two numbers have to be honoured together, and the first draft honoured only
# the first: it put «на» in front of a fifth of the addresses and produced «я
# нахожусь на школьная 163», which is not Russian. The corpus's own commonest
# lead-ins are prepositionless and elliptical — «поедем», «поеду», «едем» — and a
# nominative address after those is exactly the dispatch form. The prepositional
# ones stay, at the weight the measurement gives them.
# Every entry is a VERBATIM lexicon key, including the three that put a
# preposition in front of a nominative address — «поедем на ферганская один» is
# what the transcript holds, and an authored «нам на …» in the same shape is not
# evidence of anything, it is us writing the awkward form ourselves.
_INTENT_PLACE: tuple[tuple[str, int], ...] = (
    ("", 159), ("поедем", 6), ("поеду", 4), ("едем на", 2), ("поедем на", 2),
    ("я нахожусь на", 2), ("проедьте пожалуйста по", 1),
)

# THE CORRECTION ITSELF. Weights are the mined counts where the lexicon has them
# — «то есть» 97, «в смысле» 18, «подожди» 10, «стоп» 8 — and the rest are the
# forms `disc.self_correction` names without counting them separately. There are
# 209 self-corrections in the call corpus; a family built on one phrase would be
# measuring that phrase.
_CORRECT_LEAD: tuple[tuple[str, int], ...] = (
    ("то есть", 97), ("а нет", 40), ("подождите", 30), ("ой нет", 22),
    ("в смысле", 18), ("стоп", 8), ("нет погодите", 6), ("ой извините", 5),
    ("а нет погодите", 4), ("нет не так", 3),
)
_CORRECT_LEAD_CLEAN: tuple[str, ...] = (
    "Прошу прощения, ошибся.", "Подождите, я ошиблась.",
    "Нет, поправлю.", "Извините, верный вариант:",
)

# `disc.re_ask` — 165 in the call corpus, and it is the operator's line, not the
# customer's, which is why it lives on the assistant turn.
_REASK: tuple[str, ...] = (
    "ещё раз пожалуйста", "повторите пожалуйста", "не слышу повторите",
    "ещё раз не расслышала", "как как повторите",
)
_REASK_CLEAN: tuple[str, ...] = (
    "Повторите, пожалуйста.", "Не расслышал, повторите.",
)

# The prefix on the SECOND mention when it repeats a value the operator got
# wrong. «нет вы сказали X а надо Y» is the owner's own example of the shape.
_READBACK_LEAD: tuple[str, ...] = (
    "нет вы сказали", "нет вы записали", "не так вы сказали",
)


def _register_key(register: str) -> str:
    if register == "clean":
        return "clean"
    if register in ("voice_raw", "voice_itn"):
        return "spoken"
    return "typed"


def _weighted(table: tuple[tuple[str, int], ...], rng: random.Random) -> str:
    return rng.choices([text for text, _ in table],
                       weights=[count for _, count in table], k=1)[0]


def _opener(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_OPENERS_CLEAN)
    table = (_OPENERS_SPOKEN if register in ("voice_raw", "voice_itn")
             else _OPENERS_TYPED)
    return _weighted(table, rng)


def _intent(register: str, rng: random.Random) -> str:
    if register == "clean":
        return "Адрес подачи:"
    return _weighted(_INTENT_PLACE, rng)


def _correct_lead(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_CORRECT_LEAD_CLEAN)
    return _weighted(_CORRECT_LEAD, rng)


def _stop(register: str) -> str:
    """The full stop that closes a literary sentence, and nothing elsewhere."""
    return "." if register == "clean" else ""


def _ack(register: str, rng: random.Random) -> str:
    return (rng.choice(_ACK_CLEAN) if register == "clean"
            else rng.choice(_ACK_SPOKEN))


# --- the negative on the wire ---------------------------------------------

@dataclass(frozen=True)
class _NegSpec:
    msg_key: str
    tag: str
    family: str
    why: str


def _negative_pieces(negative: _Neg, register: str, msg_key: str,
                     tag: str) -> tuple[tuple[_Piece, ...], tuple[_NegSpec, ...]]:
    """One negative, repaired or not, as pieces plus the specs that locate it.

    The carrier is prose and is NOT part of any span: a gateway that masks «нам
    в» has made no error anybody can name, while one that masks «три
    четырнадцатый кабинет» has broken the ride. The correction lead between the
    two halves is prose for the same reason.
    """
    carrier = _neg_carrier(negative, register)
    first = _neg_surface(negative, register, "first")
    if not negative.second[0]:
        pieces = (_Piece("", carrier), _Piece(tag, first),
                  _Piece("", _stop(register)))
        return pieces, (_NegSpec(msg_key, tag, negative.family, negative.why),)
    second = _neg_surface(negative, register, "second")
    lead = "," if register == "clean" else "а нет"
    pieces = (_Piece("", carrier), _Piece(f"{tag}a", first), _Piece("", lead),
              _Piece("", "нет" if register == "clean" else ""),
              _Piece("", "," if register == "clean" else ""),
              _Piece(f"{tag}b", second), _Piece("", _stop(register)))
    specs = (
        _NegSpec(msg_key, f"{tag}a", negative.family,
                 f"{negative.why}; это ОТМЕНЁННАЯ половина — форма исправления, "
                 f"а не признак персональных данных"),
        _NegSpec(msg_key, f"{tag}b", negative.family, negative.why),
    )
    return pieces, specs


# --- padding to a context rung --------------------------------------------

@dataclass(frozen=True)
class _ItemSpec:
    id: str
    msg_key: str
    tag: str
    type: str
    value: str
    canonical: str
    identity: str
    duty: str
    value_source: str
    spoken: bool
    tool_param: str


_MIN_DEEP_CHARS_MARGIN: int = 4_400


def _long_filler(pool: tuple[str, ...]) -> tuple[str, ...]:
    """The long half of the pool, for the `deep` rung.

    MIN_DEEP_CHARS exists so that thirty two-word replies cannot pass for a long
    context. Padding a deep case with the median utterance satisfies the letter
    of that rule and breaks its intent — it reaches four thousand characters by
    stacking a hundred and thirty tiny turns, which is the same short context
    with more of it.
    """
    ordered = sorted(pool, key=len, reverse=True)
    return tuple(ordered[:max(40, len(ordered) // 2)])


def _filler_pair(index: int, register: str, rng: random.Random,
                 pool: tuple[str, ...]) -> tuple[_Msg, _Msg]:
    """One customer turn that carries nothing and one operator acknowledgement."""
    if register == "clean":
        said = rng.choice(_FILLER_CLEAN)
    else:
        said = rng.choice(pool)
        if register == "sloppy" and rng.random() < 0.4:
            said = _typo_phrase(said, rng)
    return (_msg(f"f{index}u", "user", (_Piece("", said),), ""),
            _msg(f"f{index}a", "assistant", (_Piece("", _ack(register, rng)),), ""))


def _pad(opening: tuple[_Msg, ...], closing: tuple[_Msg, ...], context: str,
         register: str, rng: random.Random,
         pool: tuple[str, ...]) -> tuple[_Msg, ...]:
    """Insert filler BETWEEN the cancelled mention and the corrected one.

    Between, and that is the axis this family adds to the rungs: the question a
    long `repair` case asks is whether the correction is still recognised as a
    correction when twenty replies stand between it and what it corrects. Filler
    stacked in FRONT of both would lengthen the transcript without lengthening
    anything that matters.
    """
    if context in ("solo", "short"):
        pairs = 0 if context == "solo" else rng.randrange(0, 3)
    elif context == "long":
        pairs = rng.randrange(4, 12)
    else:
        pairs = 15
        pool = _long_filler(pool)
    middle: list[_Msg] = []
    index = 0
    while True:
        total = len(opening) + len(middle) + len(closing)
        characters = sum(len(message.text)
                         for message in (*opening, *middle, *closing))
        if index >= pairs and (context != "deep"
                               or (total >= 33
                                   and characters >= _MIN_DEEP_CHARS_MARGIN)):
            break
        if total >= 190:
            raise InvalidCase(
                f"padding a `{context}` case ran past 190 messages without "
                f"reaching {_MIN_DEEP_CHARS_MARGIN} characters; the filler pool "
                f"is too short for this rung")
        middle.extend(_filler_pair(index, register, rng, pool))
        index += 1
    return (*opening, *middle, *closing)


# --- finishing a case -----------------------------------------------------

@dataclass(frozen=True)
class _Spec:
    arm: str
    register: str
    context: str
    index: int
    draw: int
    seed: int


def _draw_rng(spec: _Spec) -> random.Random:
    """The RNG that picks VALUES. Keyed by the draw, so a cluster shares them.

    One address said by seven callers is one value and seven occurrences. Cases
    sharing a cluster must therefore share the value, and an interval computed
    over cases rather than clusters is narrower than the truth in our favour.
    """
    return random.Random(f"v3:{FAMILY}:{spec.seed}:{spec.arm}:draw{spec.draw}")


def _case_rng(spec: _Spec) -> random.Random:
    """The RNG that picks SURFACE. Keyed by the case, so registers differ."""
    return random.Random(f"v3:{FAMILY}:{spec.seed}:{spec.arm}:case{spec.index}")


def _provenance(shape: str, corpus: str, selection: str,
                weight: float) -> Provenance:
    licence = _LICENCE_DISPATCH if corpus == "speech_rudevices" else _LICENCE_CALLS
    return Provenance(kind="recombined", corpus=corpus, key="", shape=shape,
                      selection=selection, weight=weight, licence=licence)


def _conversation_id(case_id: str, index: int) -> str:
    """Half the cases name their conversation and half make the harness derive it.

    `validate_corpus` refuses a corpus that carries only one of the two, and the
    two are DIFFERENT CODE PATHS: a customer gateway with no conversation field
    triggers the derivation, which reads the first two messages and is weaker on
    purpose. A family that only ever hands one over never exercises it.
    """
    return case_id if index % 2 == 0 else ""


def _finish(case_id: str, spec: _Spec, messages: tuple[_Msg, ...],
            tools: tuple[dict[str, Any], ...], items: tuple[_ItemSpec, ...],
            negatives: tuple[_NegSpec, ...], links: tuple[LinkExpectation, ...],
            calls: tuple[ExpectedCall, ...], final: FinalAnswer,
            provenance: Provenance, cluster: str, note: str) -> Case:
    """Resolve every span from the marks the builder recorded, then REFUSE or return.

    `validate` runs HERE and not in `build`, so a broken case names itself at the
    moment it was constructed instead of arriving inside a list of a hundred and
    ten.
    """
    pii: list[PiiItem] = []
    for item in items:
        index, start, end = _locate(messages, item.msg_key, item.tag)
        placed = messages[index].text[start:end]
        if placed != item.value:
            raise InvalidCase(
                f"{case_id}: item {item.id} was built as {item.value!r} and the "
                f"message holds {placed!r} at {start}:{end}")
        pii.append(PiiItem(
            id=item.id, type=item.type, value=item.value,
            canonical=item.canonical, start=start, end=end, msg=index,
            identity=item.identity, duty=item.duty,
            value_source=item.value_source, spoken=item.spoken,
            tool_param=item.tool_param))
    negative_rows: list[Negative] = []
    for negative in negatives:
        index, start, end = _locate(messages, negative.msg_key, negative.tag)
        negative_rows.append(Negative(
            value=messages[index].text[start:end], start=start, end=end,
            msg=index, family=negative.family, why=negative.why))
    case = Case(
        id=case_id,
        family=FAMILY,
        register=spec.register,
        context=spec.context,
        provenance=provenance,
        cluster=cluster,
        conversation_id=_conversation_id(case_id, spec.index),
        messages=tuple(
            Message(role=message.role, content=message.text,
                    source=message.source, name=message.name)
            for message in messages),
        tools=tools,
        pii=tuple(pii),
        negatives=tuple(negative_rows),
        links=links,
        calls=calls,
        final=final,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        note=note,
    )
    problems = validate(case)
    if problems:
        raise InvalidCase("\n".join(problems))
    return case


def _ride_call(value: str, item_id: str, after: int) -> ExpectedCall:
    return ExpectedCall(
        name="create_ride",
        arguments={"address": value, "comment": "по звонку"},
        judged_args=("address",), pii_items=(item_id,), after_msg=after)


def _client_call(param: str, value: str, item_id: str,
                 after: int) -> ExpectedCall:
    return ExpectedCall(
        name="find_client",
        arguments={param: value, "channel": "телефон"},
        judged_args=(param,), pii_items=(item_id,), after_msg=after)


# --- the arms: an address corrected ---------------------------------------
#
# Three ways a Russian caller corrects an address, ordered by how hard the
# resulting pair is to keep apart. Everything about the pair is identical except
# the ONE part that moved, which is deliberate: the merge this family is looking
# for is not a merge of two unrelated strings, it is a canonicaliser deciding
# that «ленина четырнадцать» and «ленина сорок» are one flat because they share
# four fifths of their characters.
_PLACE_MODES: dict[str, str] = {
    "house": "тот же дом, соседний номер — форма, в которой каноникализация "
             "чаще всего склеивает два адреса в один",
    "street": "та же нумерация, другая улица — «вы сказали пушкина, а надо "
              "чехова» из настоящего транскрипта",
    "flat": "тот же дом, другая квартира — две мишени различаются одним "
            "последним словом, и это самая тесная пара в корпусе",
}


def _second_place(place: _Place, mode: str, rng: random.Random) -> _Place:
    """The corrected address, differing from the first in exactly one part."""
    if mode == "house":
        house = place.house
        while house == place.house:
            house = max(1, place.house + rng.choice((-9, -5, -3, 3, 5, 11, 26)))
        return _Place(street=place.street, type_word=place.type_word,
                      house=house, entrance=place.entrance, letter=place.letter,
                      flat=place.flat)
    if mode == "street":
        street = _draw_street(rng, place.street)
        # A street name and its type word have to agree, so a swap that keeps
        # the old type word can produce «проезд Ракетная», which is not Russian
        # and therefore not a form worth measuring on.
        type_word = (place.type_word
                     if place.type_word in _type_words_for(street)
                     else (_type_words_for(street)[0] if place.type_word else ""))
        return _Place(street=street, type_word=type_word, house=place.house,
                      entrance=place.entrance, letter=place.letter,
                      flat=place.flat)
    if mode == "flat":
        flat = place.flat
        while flat == place.flat:
            flat = max(1, place.flat + rng.choice((-11, -6, 6, 9, 13)))
        return _Place(street=place.street, type_word=place.type_word,
                      house=place.house, entrance=place.entrance,
                      letter=place.letter, flat=flat)
    raise InvalidCase(f"unknown place repair mode {mode!r}")


def _arm_place(spec: _Spec, pool: tuple[str, ...], mode: str) -> Case:
    """An address said, retracted, and said again. The family's centre of mass.

    The CANCELLED value is `required` and claims no tool param, which is the
    whole of question (a): mask it, expect nothing back. The CORRECTED one claims
    `create_ride.address`, which is question (b). A gateway that links the two
    into one identity fails (b) with a 200 and a plausible address, and
    `classify_break` calls it `other_person` because the cancelled value is in
    the case and can be compared against.

    Every register but the literary one keeps the two mentions in the SAME
    grammatical shape. A correction that also changes the form («ленина
    четырнадцать» → «улица Ленина, дом 40») would let a gateway pass by noticing
    the shape change rather than the correction, and the traffic does not do
    that: a person repeating themselves repeats themselves.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    form = ("flat" if mode == "flat"
            else draw.choice(("bare", "bare", "bare", "marked", "entrance")))
    place_a = _draw_place(draw, form, "")
    place_b = _second_place(place_a, mode, draw)
    first = _render_place(place_a, register, rng)
    second = _render_place(place_b, register, rng)
    if first == second:
        raise InvalidCase(f"{spec.arm} {spec.index}: both mentions rendered alike")

    spoken = register == "voice_raw"
    negative = _pick_negative(_REPAIRED, register, True, False, rng)
    opener = _opener(register, rng)
    intent = _intent(register, rng)
    lead = _correct_lead(register, rng)
    stop = _stop(register)
    # 15% of the mentions name the settlement first. It is the ONLY `optional`
    # item this family emits and it is here rather than in a name arm because
    # this is where the temptation lives: the owner's own example, «г. Воронеж,
    # улица Ленина, д. 25» against «ленина двадцать пять», is exactly the shape
    # that invites a generator to fold the city into the required span.
    city = _render_city(draw.choice(_CITIES), register) if rng.random() < 0.15 else ""
    city_pieces = ((_Piece("c1", city),
                    _Piece("", "," if register == "clean" else ""))
                   if city else ())

    if spec.context == "solo":
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "one", "n")
        messages: tuple[_Msg, ...] = (
            _system(_SYSTEM_DISPATCH),
            _msg("one", "user",
                 (_Piece("", opener), _Piece("", intent), *city_pieces,
                  _Piece("a1", first), _Piece("", stop), _Piece("", lead),
                  _Piece("a2", second), _Piece("", stop), *negative_pieces), ""),
        )
        first_key = second_key = "one"
    else:
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "fix", "n")
        opening = (
            _system(_SYSTEM_DISPATCH),
            _msg("said", "user",
                 (_Piece("", opener), _Piece("", intent), *city_pieces,
                  _Piece("a1", first), _Piece("", stop)), ""),
            _msg("ack", "assistant", (_Piece("", _ack(register, rng)),), ""),
        )
        closing = (
            # The corrected mention restates the VALUE and not the lead-in.
            # «я нахожусь на школьная 163 … стоп я нахожусь на удмуртская 163»
            # is a generator repeating its own template; a person says the
            # address again and nothing else.
            _msg("fix", "user",
                 (_Piece("", lead),
                  _Piece("", "Верный адрес:" if register == "clean" else ""),
                  _Piece("a2", second), _Piece("", stop), *negative_pieces), ""),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)
        first_key, second_key = "said", "fix"

    items = [
        _ItemSpec("a1", first_key, "a1", "LOC", first, _place_canonical(place_a),
                  "place.cancelled", "required", "pool", spoken, ""),
        _ItemSpec("a2", second_key, "a2", "LOC", second,
                  _place_canonical(place_b), "place.effective", "required",
                  "pool", spoken, "address"),
    ]
    if city:
        items.append(_ItemSpec(
            "c1", first_key, "c1", "LOC", city, city.removeprefix("г. ").capitalize(),
            "place.city", "optional", "pool", spoken, ""))
    selection, weight = _selection_for(place_a)
    # Every third case also judges the reply. The pair of demands is ONE claim:
    # the answer confirms the address the customer ended on and does not confirm
    # the one they took back — which a gateway that merged the two cannot do,
    # because after the merge only one string exists to detokenise to.
    if spec.index % 3 == 0:
        final = FinalAnswer(must_contain=(_place_canonical(place_b),),
                            must_not_contain=(first, _place_canonical(place_a)),
                            answer="")
    else:
        final = FinalAnswer(must_contain=(), must_not_contain=(), answer="")
    return _finish(
        case_id=f"rep-{mode}-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=tuple(items),
        negatives=negative_specs,
        links=(LinkExpectation("a1", "a2", "different", "", _PLACE_MODES[mode]),),
        calls=(_ride_call(_place_canonical(place_b), "a2", len(messages) - 1),),
        final=final,
        provenance=_provenance(_place_shape(place_a), "speech_rudevices",
                               selection, weight),
        cluster=f"repair:{mode}:{spec.draw:03d}",
        note=f"адрес назван, отменён и назван заново ({mode}); отменённый — тоже "
             f"ПД и обязан быть замаскирован, ДЕЙСТВУЮЩИЙ — второй, и именно он "
             f"обязан приехать в create_ride.address")


# --- the words that introduce a name --------------------------------------
#
# Weights are the mined `слова_намерения.имя` counts: «это» 916, «говорит» 76,
# «ваша фамилия» 32, «моя фамилия» 21, «меня зовут» 20. The third-person and
# first-person lists are separate because the two corrections they carry are
# different events — «фамилия кузнецов, а нет, миронов» is naming the wrong
# PERSON, «меня зовут анна, ой, анна сергеевна» is one person adding a part —
# and a shared cue list would let the generator produce «меня зовут кузнецов, а
# нет, миронов», which is a person forgetting their own surname.
_CUE_THIRD: tuple[tuple[str, int], ...] = (
    ("", 60), ("это", 40), ("фамилия", 32), ("на кого оформляем", 6),
    ("клиент", 5), ("записывайте", 6),
)
# NO «моя фамилия» HERE. `name_extend` opens on a bare given name, and «моя
# фамилия ольга» is a sentence the cue itself contradicts — the misuse a
# recogniser would be entitled to hold against us.
_CUE_SELF: tuple[tuple[str, int], ...] = (
    ("меня зовут", 20), ("это", 30), ("говорит", 26),
)

# «фамилия X» and «на кого оформляем X» demand a surname in X. A cue drawn
# without looking at the shape it introduces produced «фамилия василий», which
# is the same class of mistake as an address after a preposition it does not
# take: the generator writing a form the language does not have, and the
# benchmark then measuring the gateway on it.
_CUE_THIRD_GIVEN: tuple[tuple[str, int], ...] = (
    ("", 60), ("это", 40), ("клиент", 5), ("записывайте", 6),
)
_SURNAME_FORMS: frozenset[str] = frozenset({"surname", "given_surname",
                                            "surname_given"})


def _cue_third_for(form: str) -> tuple[tuple[str, int], ...]:
    return _CUE_THIRD if form in _SURNAME_FORMS else _CUE_THIRD_GIVEN
_CUE_CLEAN_THIRD: str = "Клиент:"
_CUE_CLEAN_SELF: str = "Меня зовут"
_CUE_PHONE: tuple[tuple[str, int], ...] = (
    ("телефон", 24), ("мой номер", 12), ("запишите телефон", 8),
    ("номер такой", 4),
)


def _name_cue(table: tuple[tuple[str, int], ...], clean: str, register: str,
              rng: random.Random) -> str:
    return clean if register == "clean" else _weighted(table, rng)


# --- the arms: the operator got it wrong ----------------------------------

def _arm_readback(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """The operator reads the address back wrong and the customer corrects it.

    «вы сказали пушкина, а надо чехова» — the owner's own example, and the only
    arm in this family where personal data sits in an ASSISTANT turn. That
    stratum is nearly empty across the whole corpus (the audit counts it), and it
    is not a curiosity: the agent's own previous reply re-enters the request and
    is masked a second time, so a gateway whose second masking disagrees with its
    first has a dialogue that diverges from itself.

    FOUR items and three link claims, which is the point of the arm. The
    customer's address is said twice and must be ONE identity; the misheard one
    is said twice and must be ANOTHER; and the two must not be joined. A gateway
    that has stopped linking altogether passes both `same` claims by accident
    only if it also fails them, so the three together cannot be satisfied by any
    single degenerate policy.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    form = draw.choice(("bare", "bare", "marked", "entrance"))
    right = _draw_place(draw, form, "")
    wrong = _second_place(right, "street", draw)
    right_text = _render_place(right, register, rng)
    wrong_text = _render_place(wrong, register, rng)
    if right_text == wrong_text:
        raise InvalidCase(f"{spec.arm} {spec.index}: readback rendered alike")
    spoken = register == "voice_raw"
    negative = _pick_negative(_REPAIRED, register, True, False, rng)
    negative_pieces, negative_specs = _negative_pieces(
        negative, register, "fix", "n")
    stop = _stop(register)
    lead = (rng.choice(_READBACK_LEAD) if register != "clean"
            else "Вы записали")
    correction = "а надо" if register != "clean" else ", а нужно"

    opening = (
        _system(_SYSTEM_DISPATCH),
        _msg("said", "user",
             (_Piece("", _opener(register, rng)), _Piece("", _intent(register, rng)),
              _Piece("a1", right_text), _Piece("", stop)), ""),
        _msg("back", "assistant",
             (_Piece("", "записала" if register != "clean" else "Записал:"),
              _Piece("w1", wrong_text), _Piece("", stop),
              _Piece("", "верно" if register != "clean" else "Верно?")), ""),
    )
    closing = (
        _msg("fix", "user",
             (_Piece("", lead), _Piece("w2", wrong_text), _Piece("", correction),
              _Piece("a2", right_text), _Piece("", stop), *negative_pieces), ""),
    )
    messages = _pad(opening, closing, spec.context, register, rng, pool)
    right_canonical = _place_canonical(right)
    items = (
        _ItemSpec("a1", "said", "a1", "LOC", right_text, right_canonical,
                  "place.effective", "required", "pool", spoken, ""),
        _ItemSpec("w1", "back", "w1", "LOC", wrong_text,
                  _place_canonical(wrong), "place.misheard", "required", "pool",
                  spoken, ""),
        _ItemSpec("w2", "fix", "w2", "LOC", wrong_text, _place_canonical(wrong),
                  "place.misheard", "required", "pool", spoken, ""),
        _ItemSpec("a2", "fix", "a2", "LOC", right_text, right_canonical,
                  "place.effective", "required", "pool", spoken, "address"),
    )
    selection, weight = _selection_for(right)
    return _finish(
        case_id=f"rep-back-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=items,
        negatives=negative_specs,
        links=(
            LinkExpectation("a1", "a2", "same", "",
                            "клиент назвал свой адрес дважды — одна подмена"),
            LinkExpectation("w1", "w2", "same", "",
                            "неверно расслышанный адрес тоже прозвучал дважды, и "
                            "он тоже чей-то настоящий"),
            LinkExpectation("a1", "w1", "different", "",
                            "адрес клиента и адрес, который оператор себе "
                            "записал, — разные дома; склейка отправит машину по "
                            "второму"),
        ),
        calls=(_ride_call(right_canonical, "a2", len(messages) - 1),),
        final=FinalAnswer(must_contain=(right_canonical,),
                          must_not_contain=(wrong_text,
                                            _place_canonical(wrong)),
                          answer=""),
        provenance=_provenance(_place_shape(right), "speech_rudevices",
                               selection, weight),
        cluster=f"repair:back:{spec.draw:03d}",
        note="оператор прочитал адрес обратно неверно; ДЕЙСТВУЮЩИЙ — тот, что "
             "клиент назвал сам, и ПД лежат в ассистентской реплике — почти "
             "пустая страта во всём корпусе")


# --- the arms: nothing was corrected, it was simply not heard -------------

def _arm_re_ask_place(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """«ещё раз пожалуйста» — the SAME address, twice. The `same` half of the family.

    Deliberately the mirror image of the correction arms, and the reason this
    family is not measurable with a `different`-only counter: a gateway that
    responds to two mentions of one value with two substitutes has broken the
    identity it exists to preserve, the model then sees a dialogue about two
    addresses, and every `different` claim in the file would still pass.

    The shape claimed here is the DISCOURSE one, not the address pattern, and
    that is not a slip: the two mentions are the same string, so nothing about
    the value distinguishes the case — only the exchange does.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    place = _draw_place(draw, draw.choice(("bare", "bare", "marked", "entrance")),
                        "")
    text = _render_place(place, register, rng)
    spoken = register == "voice_raw"
    negative = _pick_negative(_REPAIRED, register, True, False, rng)
    negative_pieces, negative_specs = _negative_pieces(
        negative, register, "again", "n")
    stop = _stop(register)
    reask = (rng.choice(_REASK_CLEAN) if register == "clean"
             else rng.choice(_REASK))
    # The second mention repeats the value and nothing else, which is what the
    # register does: 19 of 154 address replies in the dispatch corpus are the
    # address and no other word at all.
    opening = (
        _system(_SYSTEM_DISPATCH),
        _msg("said", "user",
             (_Piece("", _opener(register, rng)), _Piece("", _intent(register, rng)),
              _Piece("a1", text), _Piece("", stop)), ""),
        _msg("back", "assistant", (_Piece("", reask),), ""),
    )
    closing = (
        _msg("again", "user",
             (_Piece("a2", text), _Piece("", stop), *negative_pieces), ""),
    )
    messages = _pad(opening, closing, spec.context, register, rng, pool)
    canonical = _place_canonical(place)
    items = (
        _ItemSpec("a1", "said", "a1", "LOC", text, canonical, "place.one",
                  "required", "pool", spoken, ""),
        _ItemSpec("a2", "again", "a2", "LOC", text, canonical, "place.one",
                  "required", "pool", spoken, "address"),
    )
    return _finish(
        case_id=f"rep-reask-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=items,
        negatives=negative_specs,
        links=(LinkExpectation(
            "a1", "a2", "same", "",
            "переспрос: одно и то же значение прозвучало дважды — две подмены "
            "здесь означают, что шлюз потерял личность между репликами"),),
        calls=(_ride_call(canonical, "a2", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:disc.re_ask", "speech_calls", "census", 1.0),
        cluster=f"repair:reask:{spec.draw:03d}",
        note="значение названо дважды без поправки; оба упоминания — один адрес, "
             "и ДЕЙСТВУЮЩЕЕ второе только потому, что оператор записывает его")


def _arm_re_ask_name(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """«кукушкин фамилия кукушкин» — `name.echo`, 46 in the call corpus.

    The same claim as `re_ask_place` on the type that carries the most weight in
    this corpus, and a different failure surface: a surname repeated across two
    turns has to survive canonicalisation identically both times, and
    `to_nominative` is called on the real value each time. A gateway whose
    canonical for a name depends on the words around it produces two keys for one
    person here and nowhere else in the file.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    person = _draw_person(draw, draw.random() < 0.4, "")
    form = draw.choice(("surname", "surname", "given_surname",
                        "given_patronymic"))
    text, canonical = _render_person(person, form, register, rng)
    cue = _name_cue(_cue_third_for(form), _CUE_CLEAN_THIRD, register, rng)
    negative = _pick_negative(_REPAIRED, register, True, True, rng)
    negative_pieces, negative_specs = _negative_pieces(
        negative, register, "again", "n")
    stop = _stop(register)
    reask = (rng.choice(_REASK_CLEAN) if register == "clean"
             else rng.choice(_REASK))
    opening = (
        _system(_SYSTEM_SUPPORT),
        _msg("said", "user",
             (_Piece("", _opener(register, rng)),
              _Piece("", cue), _Piece("n1", text), _Piece("", stop)), ""),
        _msg("back", "assistant", (_Piece("", reask),), ""),
    )
    closing = (
        _msg("again", "user",
             (_Piece("n2", text), _Piece("", stop), *negative_pieces), ""),
    )
    messages = _pad(opening, closing, spec.context, register, rng, pool)
    items = (
        _ItemSpec("n1", "said", "n1", "NAME", text, canonical, "person.one",
                  "required", "pool", False, ""),
        _ItemSpec("n2", "again", "n2", "NAME", text, canonical, "person.one",
                  "required", "pool", False, "name"),
    )
    return _finish(
        case_id=f"rep-echo-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=negative_specs,
        links=(LinkExpectation(
            "n1", "n2", "same", "",
            "имя названо дважды подряд с переспросом между — одна личность и "
            "одна подмена; две означают, что каноникализация зависит от соседей"),),
        calls=(_client_call("name", canonical, "n2", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:name.echo", "speech_calls", "census", 1.0),
        cluster=f"repair:echo:{spec.draw:03d}",
        note="переспрос по имени: одно значение, два упоминания; ДЕЙСТВУЮЩЕЕ — "
             "второе, потому что именно его оператор заносит в карточку")


def _prose(text: str, register: str, rng: random.Random) -> str:
    """A writing error in the words AROUND the value, for the sloppy register.

    Applied to prose and not only to values on purpose: a cue word may be
    misspelt, and «пасспорт» / «догвор» disabled the guards that word provides.
    A `sloppy` case whose only difference from `chat` is a typo inside the value
    would leave that half of the register untested.
    """
    if register != "sloppy" or not text or rng.random() > 0.5:
        return text
    return _typo_phrase(text, rng)


# --- the arms: a person corrected -----------------------------------------

def _arm_name_fix(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """The wrong person was named and the caller names the right one.

    Both mentions use the SAME name shape — two surnames, or two given names, or
    two «имя отчество» — because a correction that also changes the shape lets a
    gateway pass by noticing the shape rather than the correction. Both are
    NOMINATIVE: an oblique mention is a real form and a real problem, and it is
    `transfer`'s, because mixing it in here would make a failed repair and a
    failed `to_nominative` the same number.

    The cue list is third-person only. «меня зовут кузнецов, а нет, миронов» is a
    person forgetting their own surname, which is not what 209 mined
    self-corrections look like.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    female = draw.random() < 0.4
    first_person = _draw_person(draw, female, "")
    second_person = _draw_person(draw, female, first_person.surname)
    form = draw.choice(("surname", "surname", "given", "given_patronymic",
                        "given_surname"))
    first, first_canonical = _render_person(first_person, form, register, rng)
    second, second_canonical = _render_person(second_person, form, register, rng)
    if first == second:
        raise InvalidCase(f"{spec.arm} {spec.index}: both names rendered alike")
    negative = _pick_negative(_REPAIRED, register, True, True, rng)
    cue = _prose(_name_cue(_cue_third_for(form), _CUE_CLEAN_THIRD, register, rng),
                 register, rng)
    lead = _correct_lead(register, rng)
    stop = _stop(register)

    if spec.context == "solo":
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "one", "n")
        messages: tuple[_Msg, ...] = (
            _system(_SYSTEM_SUPPORT),
            _msg("one", "user",
                 (_Piece("", _opener(register, rng)), _Piece("", cue),
                  _Piece("p1", first), _Piece("", stop), _Piece("", lead),
                  _Piece("p2", second), _Piece("", stop), *negative_pieces), ""),
        )
        first_key = second_key = "one"
    else:
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "fix", "n")
        opening = (
            _system(_SYSTEM_SUPPORT),
            _msg("said", "user",
                 (_Piece("", _opener(register, rng)), _Piece("", cue),
                  _Piece("p1", first), _Piece("", stop)), ""),
            _msg("ack", "assistant", (_Piece("", _ack(register, rng)),), ""),
        )
        closing = (
            _msg("fix", "user",
                 (_Piece("", lead), _Piece("p2", second), _Piece("", stop),
                  *negative_pieces), ""),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)
        first_key, second_key = "said", "fix"

    items = (
        _ItemSpec("p1", first_key, "p1", "NAME", first, first_canonical,
                  "person.cancelled", "required", "pool", False, ""),
        _ItemSpec("p2", second_key, "p2", "NAME", second, second_canonical,
                  "person.effective", "required", "pool", False, "name"),
    )
    return _finish(
        case_id=f"rep-name-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=negative_specs,
        links=(LinkExpectation(
            "p1", "p2", "different", "",
            "названы два разных человека, второй отменяет первого; склейка "
            "отдаст в карточку того, кого клиент как раз вычеркнул"),),
        calls=(_client_call("name", second_canonical, "p2", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:disc.self_correction", "speech_calls",
                               "census", 1.0),
        cluster=f"repair:name:{spec.draw:03d}",
        note="назван не тот человек и поправлен; отменённое имя — тоже ПД, "
             "ДЕЙСТВУЮЩЕЕ — второе, и оно обязано приехать в find_client.name")


def _arm_name_hear(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """«фамилию не могу понять букину или пукину или как» — `err.misheard_name`.

    One occurrence in the mined corpus, and it is here because the shape is
    unreproducible by any other route: TWO surnames offered as alternatives, both
    of them real people's names, both of them personal data, and only one of them
    the answer. A gateway that masks the pair as one span leaks nothing but hands
    the model a single substitute where the conversation had a choice; one that
    masks neither leaks two surnames at once.

    Never `solo`: the resolution is the operator asking again and the caller
    picking, and squeezing that into one utterance would produce a sentence
    Russian does not have.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    female = draw.random() < 0.35
    heard = _draw_person(draw, female, "")
    real = _draw_person(draw, female, heard.surname)
    # THE SURNAME AND NOTHING ELSE. The mined utterance is «фамилию не могу
    # понять букину или пукину», and a variant pair carrying given names too
    # would put two whole people in the doubt where the register puts one word.
    wrong, wrong_canonical = _render_person(heard, "surname", register, rng)
    right, right_canonical = _render_person(real, "surname", register, rng)
    if wrong == right:
        raise InvalidCase(f"{spec.arm} {spec.index}: both variants rendered alike")
    negative = _pick_negative(_REPAIRED, register, True, True, rng)
    negative_pieces, negative_specs = _negative_pieces(
        negative, register, "pick", "n")
    stop = _stop(register)
    # «то ли X то ли Y» and «X или Y» are the two Russian ways of offering a
    # pair, and they do not mix: the connector is read off the opening rather
    # than drawn, because «то ли кузнецов или миронов» is a sentence nobody says
    # and a corpus that contains it is measuring its own grammar.
    doubt = ("Не могу разобрать фамилию:" if register == "clean"
             else _prose(rng.choice(("фамилию не могу разобрать то ли",
                                     "не могу понять фамилию",
                                     "фамилию не расслышал то ли")),
                         register, rng))
    between = "то ли" if doubt.endswith("то ли") else "или"
    ask = ("Уточните, пожалуйста, фамилию." if register == "clean"
           else rng.choice(("уточните пожалуйста фамилию",
                            "так какая всё-таки фамилия",
                            "повторите фамилию по буквам")))
    opening = (
        _system(_SYSTEM_SUPPORT),
        _msg("said", "user",
             (_Piece("", _opener(register, rng)), _Piece("", doubt),
              _Piece("p1", wrong), _Piece("", between), _Piece("p2", right),
              _Piece("", stop)), ""),
        _msg("ask", "assistant", (_Piece("", ask),), ""),
    )
    closing = (
        _msg("pick", "user",
             (_Piece("p3", right), _Piece("", stop), *negative_pieces), ""),
    )
    messages = _pad(opening, closing, spec.context, register, rng, pool)
    items = (
        _ItemSpec("p1", "said", "p1", "NAME", wrong, wrong_canonical,
                  "person.misheard", "required", "pool", False, ""),
        _ItemSpec("p2", "said", "p2", "NAME", right, right_canonical,
                  "person.real", "required", "pool", False, ""),
        _ItemSpec("p3", "pick", "p3", "NAME", right, right_canonical,
                  "person.real", "required", "pool", False, "name"),
    )
    return _finish(
        case_id=f"rep-hear-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=negative_specs,
        links=(
            LinkExpectation("p2", "p3", "same", "",
                            "выбранный вариант назван дважды — одна личность"),
            LinkExpectation("p1", "p3", "different", "",
                            "второй вариант — другая фамилия и другой человек, "
                            "и он тоже настоящий"),
        ),
        calls=(_client_call("name", right_canonical, "p3", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(wrong,), answer=""),
        provenance=_provenance("calls:err.misheard_name", "speech_calls",
                               "census", 1.0),
        cluster=f"repair:hear:{spec.draw:03d}",
        note="фамилию не расслышали и вслух перебрали два варианта; ОБА — ПД, "
             "ДЕЙСТВУЮЩИЙ — подтверждённый, и второй вариант нельзя показывать "
             "клиенту в ответе")


def _arm_name_extend(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """«меня зовут анна, ой, извините, анна сергеевна» — the same person, fuller.

    THE LINK IS `unjudged` AND THE ROUND TRIP IS NOT. The gateway's linking rule
    resolves a partial mention against a FULLER ONE SAID EARLIER inside one
    conversation; here the fuller one comes second, so the rule correctly does
    not fire, and demanding the link would fail a gateway for being right while
    accepting anything would hide a real merge. What is not negotiable is that
    «Анна Сергеевна» reaches `find_client.name` — the patronymic is the half a
    CRM search needs and the half a truncation drops.

    A NOTE FOR THE SCORER, because this arm is the one place the break taxonomy
    can mislead: the cancelled value is a PREFIX of the effective one, so a tool
    that receives «Анна» is `truncated`, NOT `other_person`. `other_values` has to
    be built per IDENTITY and both items share one — they are one human. A scorer
    that groups by item instead would report the worst outcome in the taxonomy
    for the mildest defect in the file.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    person = _draw_person(draw, draw.random() < 0.5, "")
    fuller = draw.choice(("given_patronymic", "given_patronymic", "given_surname"))
    short, short_canonical = _render_person(person, "given", register, rng)
    full, full_canonical = _render_person(person, fuller, register, rng)
    negative = _pick_negative(_REPAIRED, register, True, True, rng)
    cue = _prose(_name_cue(_CUE_SELF, _CUE_CLEAN_SELF, register, rng),
                 register, rng)
    lead = _correct_lead(register, rng)
    stop = _stop(register)

    if spec.context == "solo":
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "one", "n")
        messages: tuple[_Msg, ...] = (
            _system(_SYSTEM_SUPPORT),
            _msg("one", "user",
                 (_Piece("", _opener(register, rng)), _Piece("", cue),
                  _Piece("p1", short), _Piece("", stop), _Piece("", lead),
                  _Piece("p2", full), _Piece("", stop), *negative_pieces), ""),
        )
        first_key = second_key = "one"
    else:
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "fix", "n")
        opening = (
            _system(_SYSTEM_SUPPORT),
            _msg("said", "user",
                 (_Piece("", _opener(register, rng)), _Piece("", cue),
                  _Piece("p1", short), _Piece("", stop)), ""),
            _msg("ack", "assistant", (_Piece("", _ack(register, rng)),), ""),
        )
        closing = (
            _msg("fix", "user",
                 (_Piece("", lead), _Piece("p2", full), _Piece("", stop),
                  *negative_pieces), ""),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)
        first_key, second_key = "said", "fix"

    items = (
        _ItemSpec("p1", first_key, "p1", "NAME", short, short_canonical,
                  "person.one", "required", "pool", False, ""),
        _ItemSpec("p2", second_key, "p2", "NAME", full, full_canonical,
                  "person.one", "required", "pool", False, "name"),
    )
    return _finish(
        case_id=f"rep-ext-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=negative_specs,
        links=(LinkExpectation(
            "p1", "p2", "unjudged", "",
            "тот же человек, названный полнее ВТОРЫМ; правило связывания "
            "разрешает частичное упоминание против более полного, названного "
            "РАНЬШЕ, поэтому здесь оно законно не срабатывает — требовать связь "
            "значило бы штрафовать за правоту"),),
        calls=(_client_call("name", full_canonical, "p2", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:disc.self_correction", "speech_calls",
                               "census", 1.0),
        cluster=f"repair:ext:{spec.draw:03d}",
        note="одно имя, названное дважды и во второй раз полнее; связь не "
             "судится, ДЕЙСТВУЮЩЕЕ — полное, и отчество обязано доехать до "
             "инструмента")


# --- the arms: a number corrected -----------------------------------------

def _arm_phone_fix(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """«восемь девятьсот… нет, давайте заново» — a dictated number restarted.

    NO `voice_raw`. A phone whose every mention is spelled out is the `spoken_id`
    family's question, and answering it in two places would make one of the two
    unreadable — a run of failures could then be a repair defect or a spoken-id
    defect and no column would say which.

    The two numbers differ in their LAST TEN DIGITS, enforced at the draw.
    `same_value` compares a phone on its last ten precisely because «+7 999…» and
    «8 999…» are one number, so a pair differing only in the country code would
    make the `different` claim false and the case unpassable.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    first_digits = _draw_phone(draw, "0" * 11)
    second_digits = _draw_phone(draw, first_digits)
    first = _render_phone(first_digits, register, rng)
    second = _render_phone(second_digits, register, rng)
    negative = _pick_negative(_REPAIRED, register, True, False, rng)
    cue = _prose("Телефон:" if register == "clean"
                 else _weighted(_CUE_PHONE, rng), register, rng)
    lead = _correct_lead(register, rng)
    stop = _stop(register)

    if spec.context == "solo":
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "one", "n")
        messages: tuple[_Msg, ...] = (
            _system(_SYSTEM_SUPPORT),
            _msg("one", "user",
                 (_Piece("", _opener(register, rng)), _Piece("", cue),
                  _Piece("f1", first), _Piece("", stop), _Piece("", lead),
                  _Piece("f2", second), _Piece("", stop), *negative_pieces), ""),
        )
        first_key = second_key = "one"
    else:
        negative_pieces, negative_specs = _negative_pieces(
            negative, register, "fix", "n")
        opening = (
            _system(_SYSTEM_SUPPORT),
            _msg("said", "user",
                 (_Piece("", _opener(register, rng)), _Piece("", cue),
                  _Piece("f1", first), _Piece("", stop)), ""),
            _msg("ack", "assistant", (_Piece("", _ack(register, rng)),), ""),
        )
        closing = (
            _msg("fix", "user",
                 (_Piece("", lead), _Piece("f2", second), _Piece("", stop),
                  *negative_pieces), ""),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)
        first_key, second_key = "said", "fix"

    items = (
        _ItemSpec("f1", first_key, "f1", "PHONE", first,
                  _phone_canonical(first_digits), "phone.cancelled", "required",
                  "template", False, ""),
        _ItemSpec("f2", second_key, "f2", "PHONE", second,
                  _phone_canonical(second_digits), "phone.effective", "required",
                  "template", False, "phone"),
    )
    return _finish(
        case_id=f"rep-phone-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=negative_specs,
        links=(LinkExpectation(
            "f1", "f2", "different", "",
            "два разных номера в одной реплике; каноникализация телефона "
            "СХЛОПЫВАЕТ формы одного номера намеренно, и здесь она обязана "
            "остановиться — это два номера, а не две записи одного"),),
        calls=(_client_call("phone", _phone_canonical(second_digits), "f2",
                            len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:disc.self_correction", "speech_calls",
                               "census", 1.0),
        cluster=f"repair:phone:{spec.draw:03d}",
        note="номер продиктован неверно и продиктован заново; ЗНАЧЕНИЕ "
             "шаблонное, ФОРМА — из добытой самокоррекции, ДЕЙСТВУЮЩИЙ номер "
             "второй")


# --- the arm where nothing may be masked ----------------------------------

def _arm_only_negative(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """A repair on something that is not personal data at all.

    THE CLAIM: «сказано дважды с поправкой между» is a SHAPE, and the shape is
    not evidence. A gateway that learned it as a masking cue passes every
    positive case in this file and fails all of these, and one number would never
    separate the two.

    A negative-only case is passed by a gateway that does nothing, which is why
    `MAX_NEGATIVE_ONLY_SHARE` caps them at a tenth of the corpus and why there
    are nine of them here and not thirty. They are still among the most valuable
    cases in the file: 528 real utterances put a number beside «кабинет» or
    «отделение», and no generator would have written a single one of them.

    The `_ALONE` negative is drawn from the table that may NOT stand beside an
    address — «шестой подъезд», «квартиру», «улице». Here there is no address, so
    it is safe, and this is the only arm where those three families are
    reachable at all.
    """
    rng = _case_rng(spec)
    register = spec.register
    plain = _pick_negative(_ALONE, register, False, False, rng)
    # Alternating rather than drawn: `entrance_no_street` is reachable ONLY here
    # (beside an address «шестой подъезд» would be a legal part of it, and a
    # negative a correct gateway must mask is a corpus bug, not a negative), and
    # a uniform draw over thirteen rows left it absent from a whole build one
    # seed in two. A family that exists in the schema and in no case is a column
    # of zeros nobody can tell from a passing one.
    repaired = _pick_negative(
        _ALONE if spec.index % 2 == 0 else _REPAIRED, register, True, True, rng)
    stop = _stop(register)

    if spec.context == "solo":
        plain_pieces, plain_specs = _negative_pieces(plain, register, "one", "p")
        repaired_pieces, repaired_specs = _negative_pieces(
            repaired, register, "one", "n")
        messages: tuple[_Msg, ...] = (
            _system(_SYSTEM_DISPATCH),
            _msg("one", "user",
                 (_Piece("", _opener(register, rng)), *plain_pieces,
                  *repaired_pieces), ""),
        )
    else:
        plain_pieces, plain_specs = _negative_pieces(plain, register, "said", "p")
        repaired_pieces, repaired_specs = _negative_pieces(
            repaired, register, "fix", "n")
        opening = (
            _system(_SYSTEM_DISPATCH),
            _msg("said", "user",
                 (_Piece("", _opener(register, rng)), *plain_pieces), ""),
            _msg("ack", "assistant", (_Piece("", _ack(register, rng)),), ""),
        )
        closing = (
            _msg("fix", "user",
                 (_Piece("", _correct_lead(register, rng)), *repaired_pieces,
                  _Piece("", stop)), ""),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)

    return _finish(
        case_id=f"rep-neg-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=(),
        negatives=plain_specs + repaired_specs, links=(), calls=(),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:disc.self_correction", "speech_calls",
                               "census", 1.0),
        cluster=f"repair:neg:{spec.index:03d}",
        note="поправка на значении, которое персональными данными не является: "
             "шлюз, выучивший форму исправления как признак ПД, проходит все "
             "положительные случаи семейства и валится здесь")


# --- the plan -------------------------------------------------------------
#
# ARM, COUNT, ALLOWED REGISTERS, ALLOWED CONTEXT RUNGS. Ordered MOST-CONSTRAINED
# FIRST, because the allocator is greedy over what remains and a free arm can
# always absorb what a constrained one could not take.
#
# The constraints are facts about the arms, not preferences. `only_negative` has
# nothing to stretch over a long transcript — a case demanding only «ничего не
# маскируй» is not made harder by twenty replies of filler, it is made longer.
# `phone_fix` cannot be `voice_raw` (the schema refuses a digit there, and a
# spelled phone is `spoken_id`'s question). `readback`, both re-asks and
# `name_hear` need an operator turn in the middle and so cannot be `solo`.
_ARM_PLAN: tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...] = (
    ("only_negative", 9, ("voice_raw", "voice_itn", "chat", "sloppy"),
     ("solo", "short")),
    ("phone_fix", 10, ("voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long")),
    ("place_flat", 10, ("voice_raw", "voice_itn", "chat", "sloppy"),
     ("solo", "short", "long")),
    ("name_hear", 5, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("short", "long", "deep")),
    ("re_ask_name", 6, ("voice_raw", "voice_itn", "chat", "sloppy"),
     ("short", "long", "deep")),
    ("re_ask_place", 8, ("voice_raw", "voice_itn", "chat", "sloppy"),
     ("short", "long", "deep")),
    ("readback", 12, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("short", "long", "deep")),
    ("name_extend", 10, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long")),
    ("name_fix", 9, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
    ("place_street", 14, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
    ("place_house", 17, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
)

# 60% speech-raw, which is ABOVE the corpus floor of 50% and deliberately so: a
# self-correction is a thing a mouth does, and the register where it is common is
# the register where the product's traffic lives. `clean` is 3.6% here, inside
# the corpus-wide 5% cap, and it exists only to show that a support email saying
# «прошу прощения, верный адрес …» does not break.
_REGISTER_MIX: tuple[tuple[str, int], ...] = (
    ("voice_raw", 66), ("voice_itn", 17), ("chat", 17), ("sloppy", 6),
    ("clean", 4),
)
_CONTEXT_MIX: tuple[tuple[str, int], ...] = (
    ("solo", 44), ("short", 33), ("long", 22), ("deep", 11),
)

# A literary case has no real filler to pad with — the speech corpus supplies
# every non-PII line this family uses — and ten authored sentences repeated sixty
# times is not a long context, it is one sentence sixty times.
_NO_DEEP: frozenset[str] = frozenset({"clean"})

# Arms whose value pool is thin enough that pairing two cases onto one draw would
# show up as a distinct-value count nobody should trust. The place arms keep the
# pairing: it is what makes `cluster` mean something, and «one address said by
# seven callers is one value and seven occurrences» is a rule this corpus has to
# be able to demonstrate on itself.
_ONE_DRAW_PER_CASE: frozenset[str] = frozenset({
    "phone_fix", "name_hear", "re_ask_name", "name_extend", "name_fix",
    "only_negative",
})


def _scaled(mix: tuple[tuple[str, int], ...], total: int,
            base: int) -> dict[str, int]:
    """Scale a mix to a corpus of `total` cases, keeping the sum exact."""
    scaled = {name: count * total // base for name, count in mix}
    order = [name for name, _ in mix]
    index = 0
    while sum(scaled.values()) < total:
        scaled[order[index % len(order)]] += 1
        index += 1
    while sum(scaled.values()) > total:
        largest = max(order, key=lambda name: scaled[name])
        scaled[largest] -= 1
    return scaled


def _allocate(slots: tuple[tuple[str, tuple[str, ...]], ...],
              quota: dict[str, int], rng: random.Random) -> list[str]:
    """Hand each slot a value from its allowed set, draining a global quota.

    WEIGHTED BY WHAT REMAINS, not greedy on the largest. Greedy starves every
    small quota until the end of the list — the literary register, four cases in
    a hundred and ten, would land entirely on the last arm, so `clean` would
    exist in the corpus and cross nothing. A rung of the ladder is supposed to
    close every dimension, and a register that only ever occurs with one arm
    cannot help it.
    """
    out: list[str] = []
    for _, allowed in slots:
        live = [name for name in allowed if quota.get(name, 0) > 0]
        if not live:
            raise InvalidCase(
                f"no quota left for any of {allowed}; the mix and the arm "
                f"constraints disagree")
        pick = rng.choices(live, weights=[quota[name] for name in live], k=1)[0]
        quota[pick] -= 1
        out.append(pick)
    return out


def _plan(seed: int, count: int, rng: random.Random) -> tuple[_Spec, ...]:
    """Arm, register and context for every case. Deterministic in `seed`."""
    arm_counts = _scaled(
        tuple((name, size) for name, size, _, _ in _ARM_PLAN), count, TARGET)
    slots: list[tuple[str, tuple[str, ...]]] = []
    context_slots: list[tuple[str, tuple[str, ...]]] = []
    for name, _, registers, contexts in _ARM_PLAN:
        for _ in range(arm_counts[name]):
            slots.append((name, registers))
            context_slots.append((name, contexts))
    registers = _allocate(tuple(slots), _scaled(_REGISTER_MIX, count, TARGET), rng)
    contexts = _allocate(
        tuple((name, tuple(rung for rung in allowed
                           if not (rung == "deep" and register in _NO_DEEP)))
              for (name, allowed), register in zip(context_slots, registers)),
        _scaled(_CONTEXT_MIX, count, TARGET), rng)
    specs: list[_Spec] = []
    seen: dict[str, int] = {}
    for (arm, _), register, context in zip(slots, registers, contexts):
        index = seen.get(arm, 0)
        seen[arm] = index + 1
        draw = index if arm in _ONE_DRAW_PER_CASE else index // 2
        specs.append(_Spec(arm=arm, register=register, context=context,
                           index=index, draw=draw, seed=seed))
    return tuple(specs)


_ARMS: dict[str, Any] = {
    "place_house": lambda spec, pool: _arm_place(spec, pool, "house"),
    "place_street": lambda spec, pool: _arm_place(spec, pool, "street"),
    "place_flat": lambda spec, pool: _arm_place(spec, pool, "flat"),
    "readback": _arm_readback,
    "re_ask_place": _arm_re_ask_place,
    "re_ask_name": _arm_re_ask_name,
    "name_fix": _arm_name_fix,
    "name_hear": _arm_name_hear,
    "name_extend": _arm_name_extend,
    "phone_fix": _arm_phone_fix,
    "only_negative": _arm_only_negative,
}


def build(seed: int, count: int) -> list[Case]:
    """Every case this family contributes, in file order.

    The RNG is the family's own — `random.Random(f"v3:{FAMILY}:{seed}")` — so the
    output does not move when a module built before this one changes how many
    draws it makes. Every case is validated at construction: a corpus that
    refuses late tells you which hundred and ten cases might be wrong, and a
    family that refuses early tells you which one is.
    """
    _verify_shapes()
    pool = _filler_pool()
    rng = random.Random(f"v3:{FAMILY}:{seed}")
    cases = [_ARMS[spec.arm](spec, pool) for spec in _plan(seed, count, rng)]
    if count == TARGET:
        _verify_emitted_shapes(cases)
    return cases


# --- self-check -----------------------------------------------------------

def main() -> int:
    """Build the family and print what it actually contains.

    Prints the composition rather than a pass line, because the failure this
    module can have while still «passing» is a mix that drifted: v2 described its
    register split in a design document and shipped the opposite, and the only
    thing that would have caught it is a build that says out loud what it made.
    """
    cases = build(20260830, TARGET)
    print(f"{FAMILY}: {len(cases)} cases")

    def tally(key: Any) -> str:
        counts: dict[str, int] = {}
        for case in cases:
            counts[key(case)] = counts.get(key(case), 0) + 1
        return "  ".join(f"{name} {count} ({count / len(cases):.0%})"
                         for name, count in sorted(counts.items()))

    print("register   ", tally(lambda c: c.register))
    print("context    ", tally(lambda c: c.context))
    print("provenance ", tally(lambda c: c.provenance.kind))
    print("selection  ", tally(lambda c: c.provenance.selection))
    print("shape      ", tally(lambda c: c.provenance.shape))
    real = sum(1 for case in cases
               if case.provenance.kind in ("verbatim", "recombined"))
    print(f"форма из речи {real}/{len(cases)} = {real / len(cases):.1%}")

    links: dict[str, int] = {}
    for case in cases:
        for link in case.links:
            links[link.kind] = links.get(link.kind, 0) + 1
    print("links      ", "  ".join(f"{k} {v}" for k, v in sorted(links.items())))

    negatives: dict[str, int] = {}
    for case in cases:
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print("negatives  ", "  ".join(f"{k} {v}"
                                   for k, v in sorted(negatives.items())))

    spoken = sum(1 for case in cases for item in case.pii if item.spoken)
    cancelled = sum(1 for case in cases for item in case.pii
                    if item.duty == "required" and not item.tool_param)
    effective = sum(1 for case in cases for item in case.pii if item.tool_param)
    optional = sum(1 for case in cases for item in case.pii
                   if item.duty == "optional")
    print(f"spoken items {spoken}")
    print(f"отменённых значений {cancelled}, действующих {effective}")
    print(f"optional (город перед улицей) {optional}")
    print("gold items ", dict(sorted(type_denominators(cases).items())))
    print("distinct   ", distinct_values(cases))
    print(f"clusters   {len({case.cluster for case in cases})}")
    only_negative = sum(1 for case in cases
                        if not any(i.duty == "required" for i in case.pii))
    print(f"негативных без ПД {only_negative} "
          f"({only_negative / len(cases):.1%} этого семейства)")
    assistant_pii = sum(1 for case in cases for item in case.pii
                        if case.messages[item.msg].role == "assistant")
    print(f"ПД в ассистентской реплике {assistant_pii}")
    unused = sorted(set(_VALUE_SHAPES)
                    - {case.provenance.shape for case in cases})
    print(f"адресных шаблонов объявлено и не выпущено на этом зерне: {len(unused)}")
    for shape in unused:
        print(f"  {shape}")
    longest = max(cases, key=lambda c: sum(len(m.content) for m in c.messages))
    print(f"longest    {longest.id}: {len(longest.messages)} messages, "
          f"{sum(len(m.content) for m in longest.messages)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
