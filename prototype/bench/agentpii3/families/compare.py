"""The `compare` family — a question about the EQUALITY of two protected values,
which is the one question reversible pseudonymisation cannot carry.

ESTABLISHED, AND STATED HERE SO NOBODY READS THIS FAMILY AS A BUG REPORT: this
class of dialogue is STRUCTURALLY INCOMPATIBLE with reversible pseudonymisation.
The family exists so that the incompatibility has a NUMBER, not so that it has a
fix. The argument is short and it does not depend on our implementation:

  * masking is a function from a real value to a substitute;
  * equality of two mentions therefore survives if and only if the gateway's
    canonicalisation agrees with the human's notion of «the same address»;
  * «г. Воронеж, улица Ленина, д. 25» and «ленина двадцать пять» are the same
    place to a human and two different strings to any canonicaliser that has not
    been told this conversation is about one flat;
  * where the two do not agree, the model is asked whether two strings it can
    see are the same, and the information needed to answer was destroyed BEFORE
    the model was called. No amount of model competence recovers it.

Linking narrows the gap (a partial mention resolving against a fuller one inside
ONE conversation) but cannot close it: the same rule at tenant scale finds a
dozen owners for «Ленина 14» and refuses every time, so the scope that makes the
rule mean anything is the scope that bounds what it can mean. What is measurable
is HOW MUCH of the gap is closed, and in which direction the residue falls —
under-linking (two substitutes for one place, the agent says «нет» to a customer
who is standing where they said they were) or over-linking (one substitute for
two places, the agent says «да» and the car goes to the wrong house). Those are
opposite failures with opposite fixes and one number cannot hold both.

THE CASE THE OWNER DESCRIBED, in his words: «агент спрашивает: а вы находитесь на
Ленина 14? ... агент возвращается: вы находитесь на Пушкина 18? Он такой — нет,
мы находимся на Ленина 14, а Ленина 14 уже закрыта как ПД, и она возвращается.
Агент отвечает: мы находимся на Пушкина 18. То есть вообще бредятина.» That is
the `three_turn` arm below, and it is the only arm with an assistant turn inside
the transcript: the agent's own previous reply re-enters the request and is
masked again, so a gateway whose second masking disagrees with its first has a
dialogue that diverges from itself. Nothing in the round trip errors, nothing
leaks, the tool returns 200 — and the customer is told they live somewhere else.

TWO NUMBERS, AND STRICT IS THE HEADLINE (`score_answer` below is part of the
contract, for the same reason `same_value` lives in the schema — a scorer that
invents its own parser invents its own number):

    STRICT   the parsed answer equals `Case.final.answer`. Nothing else passes.
    SOFT     a refusal («не могу подтвердить», «уточните») also passes.

They are printed side by side and never merged. A gateway that breaks linking so
badly that the model stops answering is meaningfully better than one that makes
it answer wrongly with confidence, and only the gap between the two says which
of those the product has. A confident wrong answer passes neither.

WHERE THE FORM COMES FROM. Every arm but one is `recombined`: the sentence shape
is an entry in `mined/dispatch_grammar.json` or `mined/calls_grammar.json` and the
claim is checked from both ends: `_verify_shapes()` refuses at import if a
declared id is not in those files, and `_verify_emitted_shapes()` refuses at
build if a case claims an id the inventory does not declare. That is what makes
«the form came from real speech» a claim somebody can check rather than an
assertion — 1070 of v2's 1334 cases carried the assertion with nothing behind
it, and there was no way to tell from the file. The mined reply shape
«<филлер> <хвост> <АДРЕС> <филлер>», whose single recorded example is «а вы
находитесь зеленоградская тридцать девять корпус один да», is the owner's case
occurring in the wild; it is used verbatim as the skeleton of `three_turn`.

The `verbatim` arm is stronger still: fifteen real SOVA RuDevices replies in
which one caller names TWO destinations, unchanged, with the hand annotation's
spans. CC BY 4.0, so the text ships. Their equality question is the only authored
part, and `Case.note` says so on each.

WHAT THIS FAMILY DELIBERATELY DOES NOT MINT. No СНИЛС, ИНН, card or passport: a
value carried by its own checksum measures the checksum, not the link, and
`detect_structured` finds it whatever the register does to the prose around it.
The numeric vehicle here is the phone, because its canonicalisation («+7 999…»
and «8 999…» collapsing to one key) is a documented, deliberate piece of gateway
behaviour and therefore a fair thing to ask about. No `must_not_contain` either:
this family's closed question is about the customer's OWN data, and forbidding a
disclosure that the case never sets up would be decoration. That axis belongs to
`result` and `crowd`, which is where a third party's row actually arrives.

REGISTER LIVES IN THE SLOT VALUES AND THE TEMPLATE, never in a pass over the
finished string. An earlier corpus stripped punctuation after assembly, which
changes length and silently moves every span computed before it; the ground truth
then points a few characters left and the benchmark goes on printing numbers.
Offsets here are counted by `_line` as each message is built, and every item's
`value` is the string the builder PUT there — never `text.find(...)`. The single
exception is `verbatim`, where there is no builder: the annotation gives
span text over an utterance nothing rewrote, and `_VERBATIM` is refused at import
if a span text does not occur in its reply EXACTLY ONCE.

THE ENTRY POINT is `build(seed, count)`. It owns its RNG —
`random.Random(f"v3:{FAMILY}:{seed}")` — so the family is reproducible on its own
and does not depend on how many draws the modules before it happened to make.
"""

import hashlib
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

FAMILY = "compare"
TARGET = 250

# Rides WITH THE CORPUS, not only in this file. ФНС's open-data licence taught
# the same lesson on the ГАР side: the consumer receives a dataset, never a
# repository, so an attribution that lives only in the source tree has not been
# given. The `verbatim` arm is the only place somebody else's words are carried,
# and this is the line that must travel with them.
ATTRIBUTION: str = ("SOVA Dataset / RuDevices, распространяется по CC BY 4.0")

_MINED = Path(__file__).resolve().parent.parent / "mined"

# The refusal markers `score_answer` accepts as an abstention. Deliberately
# short: a long list turns «не могу» inside an otherwise decisive sentence into
# free credit, and the soft number is supposed to be the ceiling on honest
# uncertainty, not on hedging.
_REFUSALS: tuple[str, ...] = (
    "не могу подтвердить", "не могу сказать", "не уверен", "не уверена",
    "уточните", "уточните пожалуйста", "не располагаю", "затрудняюсь",
    "недостаточно данных", "не могу определить",
)


# --- pools ----------------------------------------------------------------
#
# STREETS ARE REAL, and they are real from the shippable corpus only: every name
# below is a hand-annotated address value in SOVA RuDevices (CC BY 4.0). An
# invented street pool would put the address arm on a vocabulary nobody speaks,
# and the ГАР cut measurement says exactly where that goes wrong — the commonest
# Russian street names ARE ordinary words, and a pool of pretty ones would test
# the easy half.
#
# Split by HOW THE NAME IS BUILT, because the mined grammar says the language has
# only two ways and they behave differently under morphology: an adjective
# («вольная», «мончегорская») and a surname in the genitive («лермонтова»,
# «комиссарова»). Measured 14 against 28 in the dispatch corpus, so the genitive
# pool is drawn twice as often.
_STREET_GENITIVE: tuple[str, ...] = (
    "ленина", "калашникова", "барышникова", "тимирязева", "дзержинского",
    "баранова", "кирова", "коммунаров", "энгельса", "павлова", "чапаева",
    "репина", "халтурина", "телегина", "петрова", "бабушкина", "металлистов",
    "красина", "котовского", "шумайлова", "циолковского", "некрасова",
    "сабурова", "маяковского", "ломоносова", "орджоникидзе", "гусева",
    "воровского", "гагарина", "грибоедова", "машиностроителей", "строителей",
    "лермонтова", "комиссарова", "челюскинцев", "барамзиной", "люхвинцева",
    "ухтомского", "воткинское", "заречное",
)
_STREET_ADJECTIVE: tuple[str, ...] = (
    "пушкинская", "клубная", "удмуртская", "нижняя", "союзная", "восточная",
    "буммашевская", "подлесная", "садовая", "школьная", "вишнёвая", "майская",
    "совхозная", "деловая", "полевая", "выставочная", "камская", "базисная",
    "химзаводская", "зеленоградская", "фруктовая", "фронтовая", "ракетная",
    "молодёжная", "русская", "армейская", "комсомольская", "деревообделочная",
    "ключевая", "транспортная", "смольный", "загородный", "северный",
    "воронцовский", "сосновый",
)
# Only the nine the dispatch corpus produced. Not the 42-type ГАР list: this is
# a generator's vocabulary, not a recognizer's, and a type word the register
# never says would put the address in a form nobody speaks.
# FOUR, and the list is short because it is a list of MINED SHAPES rather than of
# Russian street types. «бульвар Гагарина 95» is a real address and «улица
# Гагарина дом 95» is a real address, but only the second has a value shape in
# `mined/dispatch_grammar.json`, and a `Provenance.shape` that names a pattern
# the grammar cannot show is the assertion this field exists to abolish.
_TYPE_BEFORE: tuple[str, ...] = ("улица", "переулок", "проспект", "проезд")
# «улица» and «переулок» take the «дом» marker in the mined shapes; «проспект»
# and «проезд» take the bare number. Rendering them all alike would produce one
# form the corpus has and three it does not.
_TYPE_WITH_HOUSE_MARKER: frozenset[str] = frozenset({"улица", "переулок"})
# «воткинское шоссе», «заречное шоссе» — the only type word the corpus puts
# AFTER the name, and it takes an adjectival name.
_TYPE_AFTER: str = "шоссе"
_SHOSSE_NAMES: frozenset[str] = frozenset({"воткинское", "заречное"})

# A city said in FRONT of an address is `optional`, never `required`, and that
# is a legal category rather than a hedge: a settlement identifies nobody under
# 152-ФЗ ст. 3 п. 1, so masking it is not an error and missing it is not a leak.
# Folding it into the required span would punish a gateway for correctly leaving
# it alone — and the owner's own example, «г. Воронеж, улица Ленина, д. 25»
# against «ленина двадцать пять», is exactly the shape that tempts you to.
# «Сочи» is deliberately absent: it is the `city_reference` NEGATIVE, where the
# same word is a place reference and masking it IS an error.
_CITIES: tuple[str, ...] = (
    "воронеж", "ижевск", "казань", "самара", "пермь", "тверь", "курск",
    "брянск", "орёл", "рязань",
)

# NAMES ARE AUTHORED, and that is the licence-safe choice rather than a lazy one:
# the surnames the call corpus produced are under CC BY-NC and its text may not
# ship, while a common Russian given name is nobody's expression. What IS taken
# from the mining is the SHAPE inventory — which slots are filled, in what order,
# how often a patronymic contracts — and the hand-laid diminutives the grammar
# says a dictionary will never supply («ирочку», «витёк», «серёжа»).
_GIVEN_M: tuple[str, ...] = (
    "игорь", "олег", "сергей", "андрей", "дмитрий", "максим", "кирилл",
    "руслан", "тимур", "антон", "павел", "роман", "никита", "артём",
    "василий", "валерий", "леонид", "юрий", "борис", "виктор",
)
_GIVEN_F: tuple[str, ...] = (
    "марина", "ольга", "елена", "наталья", "ирина", "светлана", "анна",
    "татьяна", "лариса", "галина", "вера", "зинаида", "полина", "алина",
)
# Common Russian surnames, authored. NOT the ones the call grammar prints as
# examples: those are OpenSTT text under CC BY-NC, and while a single surname is
# nobody's expression, a pool that cannot be traced to a non-shippable corpus is
# one fewer question to answer about a file the customer receives.
_SURNAME_M: tuple[str, ...] = (
    "кузнецов", "соколов", "лебедев", "ковалёв", "тарасов", "никитин",
    "зайцев", "богданов", "воронов", "фомин", "макаров", "андреев",
    "степанов", "громов", "миронов", "савельев",
)
_PATRONYMIC_M: tuple[str, ...] = (
    "иванович", "петрович", "сергеевич", "николаевич", "валентинович",
    "михайлович", "степанович", "львович", "павлович", "александрович",
    "фёдорович", "викторович",
)
_PATRONYMIC_F: tuple[str, ...] = (
    "ивановна", "петровна", "сергеевна", "николаевна", "валентиновна",
    "михайловна",
)
# «Отчество стягивается: палыч, михалыч, иваныч …» — fifteen distinct contracted
# forms in the call corpus, and template generation has none of them at all.
_PATRONYMIC_SHORT: dict[str, str] = {
    "павлович": "палыч", "иванович": "иваныч", "михайлович": "михалыч",
    "степанович": "степаныч", "александрович": "саныч", "викторович": "викторыч",
    "николаевич": "николаич", "сергеевич": "сергеич", "фёдорович": "фёдорыч",
}
# Laid in by hand on the grammar's own instruction: neither the name dictionary
# nor pymorphy3 calls these a name, so without this line a whole way of naming a
# person never reaches the benchmark.
_DIMINUTIVE: dict[str, str] = {
    "ирина": "ирочка", "сергей": "серёжа", "виктор": "витёк",
    "евгения": "женя", "василий": "вася", "наталья": "наташа",
    "александр": "саша", "павел": "паша", "мария": "маша",
    "николай": "коля", "валерий": "валера", "роман": "рома",
}

# Genitive/dative/accusative of a masculine given name, spelled out rather than
# derived: this module must not import a morphology engine, and «Игорь → Игорю»
# is the exact form the round trip is measured on. A generator that guessed
# would be measuring its own guess.
_OBLIQUE_M: dict[str, str] = {
    "игорь": "игорю", "олег": "олегу", "сергей": "сергею", "андрей": "андрею",
    "дмитрий": "дмитрию", "максим": "максиму", "кирилл": "кириллу",
    "руслан": "руслану", "тимур": "тимуру", "антон": "антону",
    "павел": "павлу", "роман": "роману", "никита": "никите", "артём": "артёму",
    "василий": "василию", "валерий": "валерию", "леонид": "леониду",
    "юрий": "юрию", "борис": "борису", "виктор": "виктору",
}
_OBLIQUE_F: dict[str, str] = {
    "марина": "марине", "ольга": "ольге", "елена": "елене",
    "наталья": "наталье", "ирина": "ирине", "светлана": "светлане",
    "анна": "анне", "татьяна": "татьяне", "лариса": "ларисе",
    "галина": "галине", "вера": "вере", "зинаида": "зинаиде",
    "полина": "полине", "алина": "алине",
}

# Real Russian mobile prefixes, so a number that reaches libphonenumber is
# dialable and the gateway's phone recognizer is being asked a fair question.
_MOBILE_PREFIX: tuple[str, ...] = (
    "916", "903", "926", "985", "999", "951", "967", "977", "905", "915",
)


# --- numbers said aloud ---------------------------------------------------
#
# A written corpus cannot produce this shape at all, which is why the two engine
# defects v3 exists for were invisible to v2 BY CONSTRUCTION. Spelling is done
# here, from the integer, so the ground truth is what the builder PUT in the
# string; reading a number back out of a finished sentence is the mistake that
# cost v2's sloppy register 162 of its 183 failures.
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
    "седьмой", "восьмой", "девятый", "десятый",
)
# «пятьдесят → песят, шестьдесят → шеесят» — 22.9% of every -десят form in the
# call corpus arrives contracted. That is the NORM of this register, not an
# exotic corner, and a generator that only emits the canonical form measures a
# dialect nobody speaks on the phone.
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
    to the digits beside it, so the canonical form stays the number that was
    meant while the surface is the one that was said.
    """
    words = spoken.split()
    for index, word in enumerate(words):
        if word in _CONTRACTION and rng.random() < 0.23:
            words[index] = _CONTRACTION[word]
    return " ".join(words)


def _spell_phone(digits: str) -> str:
    """Eleven digits as a dictated run: «восемь девятьсот шестнадцать …».

    Grouped 1-3-3-2-2, which is `num.phone_by_pairs` plus the observation that a
    three-digit group is said as one number. No «плюс семь»: the mined shape says
    so explicitly and the corpus never produced one.
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
    alphabetic and different — a mutation that silently returns the input turns
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
        out = word[:position] + word[position + 1] + word[position] + word[position + 2:]
    else:
        letter = _NEIGHBOUR.get(word[position], word[position])
        out = word[:position] + letter + word[position + 1:]
    if out == word or not out.isalpha():
        return word
    return out


def _typo_phrase(phrase: str, rng: random.Random) -> str:
    """A typo in exactly one word of a multi-word value.

    One, not several: «Фёдо ров Кирилл» needed four signals to be reachable and
    two errors in one value is a string no reader would repair either, so a case
    built that way measures nothing anybody has to get right.
    """
    words = phrase.split(" ")
    candidates = [i for i, word in enumerate(words) if len(word) >= 4]
    if not candidates:
        return phrase
    index = rng.choice(candidates)
    words[index] = _typo(words[index], rng)
    return " ".join(words)


# --- negatives ------------------------------------------------------------
#
# HALF THE PRECISION MEASUREMENT, and in this register they are not a
# formality: a number standing beside «кабинет» or «отделение» occurs 528 times
# in the call corpus and is the single largest false-positive source there. Our
# own generated sets reported 100% precision while «Счёт 1234 от 15.05.2025» was
# being masked — they were not wrong, they held no ordinary business text. These
# are the spoken equivalent, and every one of them is a family the mining named.
#
# The `spoken` column carries no digit and the `written` column carries no
# capital, because a negative has to be legal in the register it is dropped into
# or `_register_problems` refuses the case that carries it.
@dataclass(frozen=True)
class _Neg:
    family: str
    spoken: str
    written: str
    clean: str
    carrier: str
    why: str


_NEGATIVES: tuple[_Neg, ...] = (
    _Neg("room_number", "три четырнадцатый кабинет", "кабинет 314",
         "кабинет 314", "нам надо в",
         "номер кабинета стоит рядом с числом и адресом не является"),
    _Neg("room_number", "второго отделения", "второго отделения",
         "второго отделения", "мы из",
         "отделение — место, но не чей-то адрес"),
    _Neg("time_of_day", "к девяти ноль ноль", "к 9 00", "к 9:00", "подача",
         "время; ноли проговариваются словом и дают пробег числительных"),
    _Neg("time_of_day", "в восемь ноль ноль", "в 8 00", "в 8:00", "выезжаем",
         "время подачи, не номер"),
    _Neg("entrance_no_street", "шестой подъезд", "шестой подъезд",
         "шестой подъезд", "выйдем в",
         "адресный хвост без адреса — улицы в реплике нет"),
    _Neg("street_no_name", "улице", "улице", "улице", "мы стоим на",
         "«улица» без названия — двор, погода, прогулка"),
    _Neg("street_no_name", "улицам", "улицам", "улицам", "тут не пройти по",
         "«по улицам ходить» — не адрес"),
    _Neg("flat_as_home", "квартиру", "квартиру", "квартиру", "мы недавно сняли",
         "«квартира» без номера — жильё, покупка, уборка"),
    _Neg("order_number", "заказ триста двенадцать", "заказ 312", "заказ 312",
         "это", "продиктованный номер заказа — тот самый дефект, который "
         "однажды уехал в продакшн"),
    _Neg("order_number", "заказ сорок семь", "заказ 47", "заказ 47", "это",
         "короткий номер заказа рядом с адресом"),
    _Neg("quantity", "двенадцать филиалов", "12 филиалов", "12 филиалов",
         "у нас", "количество, не номер дома"),
    _Neg("quantity", "пять коробок", "5 коробок", "5 коробок", "везём",
         "количество мест в багажнике"),
    _Neg("fare", "проезд пятьдесят рублей", "проезд 50 рублей",
         "проезд 50 рублей", "у вас теперь",
         "«проезд» здесь плата, а не тип улицы"),
    _Neg("city_reference", "сочи", "сочи", "Сочи", "мы вообще не из",
         "город как место, а не как чей-то адрес"),
    _Neg("measure", "пять гектаров", "5 гектаров", "5 гектаров", "там участок",
         "единица измерения после числа — не номер дома"),
    _Neg("measure", "двадцать квадратов", "20 квадратов", "20 квадратов",
         "там всего", "площадь квартиры, не её номер"),
)


def _negative_text(negative: _Neg, register: str) -> str:
    if register == "voice_raw":
        return negative.spoken
    if register == "clean":
        return negative.clean
    return negative.written


# --- filler ---------------------------------------------------------------
#
# NINE REPLIES IN TEN CARRY NO PERSONAL DATA AT ALL — 1.995% at the call corpus
# and 0.939% at the dispatch one. A long case whose every line holds a datum is
# not this register, and it inflates recall and precision at the same time. The
# filler is therefore REAL: hand-labelled «не адрес» replies from SOVA RuDevices,
# CC BY 4.0, which is the licence that lets them ship.
#
# Filtered mechanically, and the filter is stated because a filler line that
# quietly holds an unlabelled datum is a leak the corpus cannot see: no digit, no
# Latin, no numeral run of two or more, none of the words a negative family is
# built on (those belong in `negatives` with a span, not loose in the prose), no
# given name from the pool above, and no obscenity — the register is real, but
# reproducing it inside a customer-facing report buys nothing the measurement
# needs.
_FILLER_PATH: Path = Path.home() / ".cache" / "pseudex-bench" / "rudevices_addresses.json"
_SPEECH_PATH: Path = Path.home() / ".cache" / "pseudex-bench" / "speech_rudevices.jsonl"

_OBSCENE: tuple[str, ...] = (
    "бля", "хуй", "хуё", "хуе", "пизд", "еба", "ёба", "ебы", "ёбы", "ебан",
    "ёбан", "нахуй", "похуй", "заеб", "мудак", "гандон", "срат", "говн",
    "педик", "пидор", "пидар", "шлюх", "трахн", "жоп", "нахер", "сук",
)
_NEG_WORDS: tuple[str, ...] = (
    "улиц", "квартир", "подъезд", "проезд", "корпус", "кабинет", "отделен",
    "этаж", "дом", "заказ", "гектар", "квадрат", "рубл",
)

# Written by hand for the two registers the speech corpora cannot supply. Short,
# neutral, and carrying nothing a recognizer could reasonably want.
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
            f"{_FILLER_PATH} is missing; the compare family draws its filler from "
            f"the hand-labelled RuDevices rows and will not invent it — see "
            f"CLAUDE.md for how to restore ~/.cache/pseudex-bench/")
    rows = json.loads(_FILLER_PATH.read_text(encoding="utf-8"))
    names = set(_GIVEN_M) | set(_GIVEN_F) | set(_DIMINUTIVE.values())
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


# --- the two real utterances that ARE the case ----------------------------
#
# Fifteen SOVA RuDevices replies in which ONE caller names TWO destinations,
# hand-annotated, unchanged. CC BY 4.0 — the text ships, which is why this arm
# exists here and not against the call corpus.
#
# Offsets are found by searching, and that is allowed HERE and nowhere else: the
# rule against searching exists because a register transform rewrites the string
# under the ground truth, and nothing rewrote these. The search is made safe by
# `_verify_verbatim()`, which refuses at import if a span text does not occur in
# its reply exactly once, and by `Source.sha256`, which refuses at score time if
# the corpus line moved.
#
# The reply strings are NOT wrapped: they are the corpus text, byte for byte,
# and a line break inserted for a style rule would silently change what
# `Source.sha256` is a digest of.
#
# `cluster` is shared by the two near-duplicate replies («едим на» / «едем на»,
# the same two addresses): one value pair said twice is one observation and two
# occurrences, and an interval computed over the occurrences is narrower than the
# truth in our favour.
_VERBATIM: tuple[dict[str, Any], ...] = (
    {"key": "62206419ecd8", "line": 1950, "cluster": "v01",
     "text": "здравствуйте аа воткинское шоссе сто тридцать восемь а поедем на энгельса сто двадцать шесть",
     "spans": ("воткинское шоссе сто тридцать восемь а", "энгельса сто двадцать шесть"),
     "optional": ()},
    {"key": "f8e0e9c968b5", "line": 3628, "cluster": "v02",
     "text": "переулок смольный дом десять напойма двадцать три",
     "spans": ("переулок смольный дом десять", "напойма двадцать три"),
     "optional": ()},
    {"key": "a83cd9b97433", "line": 8521, "cluster": "v03",
     "text": "посёлок русь переулок набережный пять совхозная десять",
     "spans": ("посёлок русь переулок набережный пять", "совхозная десять"),
     "optional": ()},
    {"key": "5ad0ecdf766f", "line": 9726, "cluster": "v04",
     "text": "калашникова семь первый подъезд поеду грибоедова тридцать а",
     "spans": ("калашникова семь первый подъезд", "грибоедова тридцать а"),
     "optional": ()},
    {"key": "db3742086174", "line": 11142, "cluster": "v05",
     "text": "улица ленина двадцать девять поедем проезд халтурина пятнадцать",
     "spans": ("улица ленина двадцать девять", "проезд халтурина пятнадцать"),
     "optional": ()},
    {"key": "43e6ab18ef7c", "line": 16406, "cluster": "v06",
     "text": "девушка добрый вечер химзаводская пять квартира пятнадцать поедем гагарина пятьдесят",
     "spans": ("химзаводская пять квартира пятнадцать", "гагарина пятьдесят"),
     "optional": ()},
    {"key": "886fb8679321", "line": 17269, "cluster": "v07",
     "text": "клубная шестьдесят восемь корпус четыре едим на кирова пять",
     "spans": ("клубная шестьдесят восемь корпус четыре", "кирова пять"),
     "optional": ()},
    {"key": "93054101c1da", "line": 38033, "cluster": "v07",
     "text": "клубная шестьдесят восемь корпус четыре едем на кирова пять",
     "spans": ("клубная шестьдесят восемь корпус четыре", "кирова пять"),
     "optional": ()},
    {"key": "4991bc930096", "line": 26115, "cluster": "v08",
     "text": "ленина сто шестнадцать третий подъезд едем на котовского девятнадцать а",
     "spans": ("ленина сто шестнадцать третий подъезд", "котовского девятнадцать а"),
     "optional": ()},
    {"key": "3e395c7268e9", "line": 28072, "cluster": "v09",
     "text": "сорок лет победы дом семьдесят восемь пятый подъезд поедем проезд комсомольский двадцать восемь",
     "spans": ("сорок лет победы дом семьдесят восемь пятый подъезд",
               "проезд комсомольский двадцать восемь"),
     "optional": ()},
    {"key": "2a34885ffd4f", "line": 28424, "cluster": "v10",
     "text": "здравствуйте нижняя двенадцать первый подъезд поедем шумайлова двадцать у нас ребёнок шесть месяцев",
     "spans": ("нижняя двенадцать первый подъезд", "шумайлова двадцать"),
     "optional": ()},
    {"key": "606861992a6c", "line": 31120, "cluster": "v11",
     "text": "воткинское шоссе девяносто два четвёртый подъезд поеду дзержинского двенадцать",
     "spans": ("воткинское шоссе девяносто два четвёртый подъезд", "дзержинского двенадцать"),
     "optional": ()},
    {"key": "f3d72927f6ea", "line": 36189, "cluster": "v12",
     "text": "ломоносова пять б поедем пятнадцатая улица дом десять",
     "spans": ("ломоносова пять б", "пятнадцатая улица дом десять"),
     "optional": ()},
    # «заречное шоссе» is a street with NO house number: it identifies nobody, so
    # it is `optional` — masking it is not an error and missing it is not a leak.
    # Left unlabelled it would be an unclaimed address in a case that claims to
    # know where all of them are.
    {"key": "7c2fd659f0a3", "line": 37957, "cluster": "v13",
     "text": "советская двадцать поедем на заречное шоссе а потом клубная пятьдесят семь",
     "spans": ("советская двадцать", "клубная пятьдесят семь"),
     "optional": ("заречное шоссе",)},
    {"key": "0d4937c2e089", "line": 38956, "cluster": "v14",
     "text": "восточная девять пятый подъезд поедем на ленина сто сорок шесть",
     "spans": ("восточная девять пятый подъезд", "ленина сто сорок шесть"),
     "optional": ()},
)


def _verify_verbatim() -> None:
    """Refuse a verbatim row whose span is ambiguous or whose text has drifted.

    TWO CHECKS, and they answer different questions. A span occurring twice makes
    the offset a guess and a span occurring never means the annotation and the
    text have already come apart — both are silent when offsets are searched,
    which is the only place this module searches at all.

    The second reads the CORPUS and compares. `Source.line` and `Source.sha256`
    are claims about a file, and a claim nothing checks is how a benchmark keeps
    printing numbers after the ground under it moved; the table below is copied
    text, and copied text is exactly what goes stale.
    """
    for row in _VERBATIM:
        text = str(row["text"])
        for span in tuple(row["spans"]) + tuple(row["optional"]):
            if text.count(span) != 1:
                raise InvalidCase(
                    f"verbatim {row['key']}: span {span!r} occurs "
                    f"{text.count(span)} times in its reply — the offset would "
                    f"be a guess")
        key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
        if key != row["key"]:
            raise InvalidCase(
                f"verbatim row keyed {row['key']} hashes to {key}; the text and "
                f"the annotation key disagree")
    if not _SPEECH_PATH.exists():
        raise InvalidCase(
            f"{_SPEECH_PATH} is missing; the verbatim arm claims a line number "
            f"in it and will not ship a claim it cannot check")
    wanted = {int(row["line"]): str(row["text"]) for row in _VERBATIM}
    with _SPEECH_PATH.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if number not in wanted:
                continue
            actual = json.loads(line)["text"]
            if actual != wanted[number]:
                raise InvalidCase(
                    f"line {number} of {_SPEECH_PATH.name} reads {actual!r}, the "
                    f"verbatim table says {wanted[number]!r} — the corpus shifted "
                    f"and every offset built from it is now wrong")
            del wanted[number]
    if wanted:
        raise InvalidCase(
            f"lines {sorted(wanted)} are past the end of {_SPEECH_PATH.name}")


# --- mined shape ids ------------------------------------------------------
#
# Every id this module can put in `Provenance.shape`, checked against the mined
# files at import. The field's whole purpose is that «the form came from real
# speech» be CHECKABLE — 1070 of v2's 1334 cases asserted it with nothing behind
# the assertion — so an id that has drifted out of the grammar must stop the
# build rather than ship as a claim.
# Every id this module can put in `Provenance.shape`, checked against the mined
# files at import AND against what `build` actually emitted. The field's whole
# purpose is that «the form came from real speech» be CHECKABLE — 1070 of v2's
# 1334 cases asserted it with nothing behind the assertion — so an id that has
# drifted out of the grammar, or one this inventory lists and nothing emits, must
# stop the build rather than ship as a claim.
#
# THE ID NAMES THE SHAPE THE CASE FOLLOWS, and for most arms that is the VALUE
# shape: a case follows two mined patterns at once — «улица <улица> дом <число
# прописью>» is what the datum looks like, `disc.self_correction` is what the
# sentence around it does — and the value shape is the one the detector actually
# meets. `three_turn` is the exception and it is not an inconsistency: there the
# EXCHANGE is the case, and its skeleton is a mined reply shape whose single
# recorded example is the owner's own scenario occurring in the wild.
_SHAPES: tuple[str, ...] = (
    "dispatch.value:улица <улица> дом <число прописью>",
    "dispatch.value:переулок <улица> дом <число прописью>",
    "dispatch.value:проспект <улица> <число прописью>",
    "dispatch.value:проезд <улица> <число прописью>",
    "dispatch.value:<улица> <число прописью>",
    "dispatch.value:<улица> <число прописью> <литера>",
    "dispatch.value:<улица> <число прописью> <порядковое> подъезд",
    "dispatch.value:<улица> <число прописью> <литера> <порядковое> подъезд",
    "dispatch.value:<улица> шоссе <число прописью>",
    "dispatch.value:<улица> шоссе <число прописью> <литера>",
    "dispatch.reply:<филлер> <хвост> <АДРЕС> <филлер>",
    "calls:name.n",
    "calls:name.s",
    "calls:name.ns",
    "calls:name.np",
    "calls:name.snp",
    "calls:name.cue.это.n",
    "calls:name.cue.меня_зовут.n",
    "calls:num.phone_by_pairs",
    "calls:disc.dictation",
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


def _verify_shapes() -> None:
    missing = sorted(set(_SHAPES) - _known_shapes())
    if missing:
        raise InvalidCase(
            f"these shape ids are not in mined/: {missing} — the family would "
            f"claim a form the grammar cannot show")


def _verify_emitted_shapes(cases: list[Case]) -> None:
    """Every shape a case CLAIMS must be declared and must be in the grammar.

    The import-time check proves the inventory is honest; this one proves the
    cases used the inventory. Without it a renderer could drift onto a pattern
    nobody declared and the claim would go out unverified — which is exactly the
    state v2 was in, only with a nicer field name.

    The reverse — a declared id that nothing emitted — is REPORTED by `main` and
    not raised. Some shapes are rare by construction (a house letter is 11% of
    draws, «шоссе» is two street names in seventy-five) and a build that fails
    because a seed happened not to draw one would be a brittle test of the RNG
    rather than of the inventory.
    """
    claimed = {case.provenance.shape for case in cases if case.provenance.shape}
    stray = sorted(claimed - set(_SHAPES))
    if stray:
        raise InvalidCase(f"cases claim undeclared shapes: {stray}")


# --- tools ----------------------------------------------------------------
#
# Three, and every one of them takes a personal value as an argument, which is
# what separates this from a NER corpus: the question is not «is this a phone»
# but «does the phone the tool receives dial the customer». `source` and
# `channel` are passed and NOT judged, on purpose — τ²-bench's `compare_args`
# exists because a benchmark that compares every argument fails a gateway for a
# model's choice of page size.
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


_TOOL_PICKUP = _tool(
    "confirm_pickup", "Подтвердить адрес подачи машины.",
    {"address": "Адрес подачи, как его назвал клиент.",
     "entrance": "Подъезд, если назван.",
     "source": "Канал обращения."},
    ("address",))
_TOOL_CLIENT = _tool(
    "find_client", "Найти карточку клиента по имени или телефону.",
    {"name": "Имя клиента.", "phone": "Телефон клиента.",
     "channel": "Канал обращения."},
    ())
_TOOL_RECORD = _tool(
    "lookup_client_address", "Прочитать адрес, записанный в карточке клиента.",
    {"client_id": "Идентификатор карточки."},
    ("client_id",))

_TOOLS_PLACE: tuple[dict[str, Any], ...] = (_TOOL_PICKUP, _TOOL_CLIENT)
_TOOLS_PERSON: tuple[dict[str, Any], ...] = (_TOOL_CLIENT, _TOOL_PICKUP)
_TOOLS_RECORD: tuple[dict[str, Any], ...] = (_TOOL_PICKUP, _TOOL_RECORD)

# The integrator's own prompt. No personal data in it — the corpus does not test
# whether a system message is masked, because whether it is depends on the
# deployment leg and `validate` refuses an item that sits in one.
_SYSTEM_DISPATCH = (
    "ты диспетчер службы такси. подтверждай адрес подачи и вызывай "
    "confirm_pickup, когда адрес известен точно. на прямой вопрос отвечай "
    "одним словом: да или нет."
)
_SYSTEM_SUPPORT = (
    "ты оператор поддержки. проверяй данные клиента инструментами. на прямой "
    "вопрос отвечай одним словом: да или нет."
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
    `clean` register can write «Ленина, 25» without a stray space and without a
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


def _msg(key: str, role: str, pieces: tuple[_Piece, ...], name: str,
         source: Source | None) -> _Msg:
    text, marks = _line(pieces)
    return _Msg(key=key, role=role, text=text, marks=marks, name=name,
                source=source)


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
    adjective: bool
    type_word: str     # "" | one of _TYPE_BEFORE | "шоссе" (which goes after)
    house: int
    entrance: int      # 0 = not said
    letter: str        # "" | "а" | "б" | "в"
    city: str          # the settlement, said in front of the street or not
    city_said: bool


def _type_words_for(street: str) -> tuple[str, ...]:
    """Type words that AGREE with this street name. «Проезд Ракетная» is not Russian.

    The corpus builds a street name in one of two ways and each takes a
    different set of type words: a genitive surname takes any of them («улица
    Ленина», «проспект Калашникова», «переулок Смольный»), a feminine adjective
    takes only «улица», and a masculine one takes the masculine types. Drawing
    the type word freely produced «Набережная Ракетная», which is not a form any
    recognizer will ever meet and therefore not a form worth measuring on.
    """
    if street in _SHOSSE_NAMES:
        return (_TYPE_AFTER,)
    if street.endswith(("ая", "яя")):
        return ("улица",)
    if street.endswith(("ый", "ий", "ой")):
        return ("переулок", "проезд")
    return _TYPE_BEFORE


def _draw_place(rng: random.Random, avoid: str) -> _Place:
    """One address. Two thirds of the MENTIONS have no street-type word.

    «113 из 169 в диспетчерской (66.9%), 26 из 44 в звонках» carry no type word
    at all. That share is carried by the `partial` form, which is the majority of
    the mentions this family emits — every comparison has at least one of them,
    and two of them where the values differ.

    A place with no type word is given an ENTRANCE, so that its marked form is
    still distinguishable from its bare one. Without that rule the two mentions
    of a `same` case would render identically and the case would ask nothing:
    «ленина двадцать пять» twice is not a comparison, it is a repetition.
    """
    if rng.random() < 0.667:
        street = rng.choice(_STREET_GENITIVE)
        adjective = False
    else:
        street = rng.choice(_STREET_ADJECTIVE)
        adjective = True
    if street == avoid:
        street = rng.choice(_STREET_ADJECTIVE if adjective else _STREET_GENITIVE)
    if street in _SHOSSE_NAMES:
        type_word = _TYPE_AFTER
    elif rng.random() < 0.45:
        type_word = rng.choice(_type_words_for(street))
    else:
        type_word = ""
    house = rng.choice((rng.randrange(1, 30), rng.randrange(1, 100),
                        rng.randrange(100, 200)))
    entrance = (rng.randrange(1, 8) if not type_word
                else (rng.randrange(1, 8) if rng.random() < 0.2 else 0))
    letter = rng.choice(("а", "б", "в")) if rng.random() < 0.11 else ""
    city = rng.choice(_CITIES)
    return _Place(street=street, adjective=adjective, type_word=type_word,
                  house=house, entrance=entrance, letter=letter, city=city,
                  city_said=rng.random() < 0.15)


def _place_shape(place: _Place, form: str) -> str:
    """The mined value shape this rendering instantiates. One shape, exactly.

    Every branch names a pattern that IS in `mined/dispatch_grammar.json` — this
    function and `_place_words` are written from the same four rules, so the id
    cannot drift from the string it describes. `_verify_shapes()` proves the
    other half: that each of these ids is still in the grammar file.
    """
    if form == "partial":
        return ("dispatch.value:<улица> <число прописью> <литера>" if place.letter
                else "dispatch.value:<улица> <число прописью>")
    if place.type_word == _TYPE_AFTER:
        return ("dispatch.value:<улица> шоссе <число прописью> <литера>"
                if place.letter
                else "dispatch.value:<улица> шоссе <число прописью>")
    if place.type_word == "улица":
        return "dispatch.value:улица <улица> дом <число прописью>"
    if place.type_word == "переулок":
        return "dispatch.value:переулок <улица> дом <число прописью>"
    if place.type_word == "проспект":
        return "dispatch.value:проспект <улица> <число прописью>"
    if place.type_word == "проезд":
        return "dispatch.value:проезд <улица> <число прописью>"
    return ("dispatch.value:<улица> <число прописью> <литера> <порядковое> подъезд"
            if place.letter
            else "dispatch.value:<улица> <число прописью> <порядковое> подъезд")


def _place_words(place: _Place, form: str, house: str) -> list[str]:
    """The word sequence of one rendering, with the house number already spelled.

    Shared by every register, so the shape id, the canonical and the three
    surfaces cannot disagree about which parts were said. The literary renderer
    differs from the spoken one in PUNCTUATION and CASE, never in content.
    """
    if form == "partial":
        return [place.street, house] + ([place.letter] if place.letter else [])
    if place.type_word == _TYPE_AFTER:
        return ([place.street, _TYPE_AFTER, house]
                + ([place.letter] if place.letter else []))
    if place.type_word in _TYPE_WITH_HOUSE_MARKER:
        return [place.type_word, place.street, "дом", house]
    if place.type_word:
        return [place.type_word, place.street, house]
    words = [place.street, house] + ([place.letter] if place.letter else [])
    return words + [_ORDINAL_M[place.entrance], "подъезд"]


def _render_place(place: _Place, form: str, register: str,
                  rng: random.Random) -> str:
    """The address as one string, in one register, in one of two forms.

    `full` is the marked form — a type word, «дом» where the mined shape has one,
    or the entrance where there is no type word. `partial` is the bare «<улица>
    <число>» that two thirds of the corpus uses and that a marker filter cannot
    see at all; it is also the mention whose resolution against a fuller one
    earlier in the SAME conversation is the whole subject of this family.
    """
    if register == "clean":
        return _render_place_clean(place, form)
    spoken = register == "voice_raw"
    house = (_contract(_spell_int(place.house), rng) if spoken
             else str(place.house))
    text = " ".join(_place_words(place, form, house))
    if register == "sloppy":
        text = _typo_phrase(text, rng)
    return text


def _render_place_clean(place: _Place, form: str) -> str:
    """The web-form rendering: capitals, commas, abbreviations.

    BUILT from the same four rules as `_place_words`, not post-processed from the
    spoken string. An earlier version capitalised and inserted commas by
    rewriting the finished text, which is the same class of mistake as searching
    it for offsets: the rule the rewrite encodes drifts from the rule that
    produced the words. The type word stays lower case, because that is how an
    address line is written — «улица Ленина», not «Улица Ленина».
    """
    street = place.street.capitalize()
    house = f"{place.house}{place.letter}"
    if form == "partial":
        return f"{street}, {house}"
    if place.type_word == _TYPE_AFTER:
        return f"{street} {_TYPE_AFTER}, {house}"
    if place.type_word in _TYPE_WITH_HOUSE_MARKER:
        return f"{place.type_word} {street}, д. {house}"
    if place.type_word:
        return f"{place.type_word} {street}, {house}"
    return f"{street}, {house}, подъезд {place.entrance}"


def _render_city(place: _Place, register: str) -> str:
    """The settlement in front of the street, in the register that says it.

    A mined shape in both corpora: «Колпино улица культуры восемь», «посёлок русь
    переулок набережный пять». It is a separate span with duty `optional`, not
    part of the address value.
    """
    if register == "clean":
        return f"г. {place.city.capitalize()}"
    return place.city


def _place_canonical(place: _Place, form: str) -> str:
    """What a CRM would store OF WHAT WAS SAID. Never more than that.

    It IS the literary rendering of the same word list, and that is the point
    rather than a shortcut: a canonical assembled independently can claim a part
    the mention never carried, which is the ground truth scoring the gateway on
    information the conversation did not have — 162 of v2's 183 sloppy failures
    were one version of it, and «а подъезд?» would be the next.

    The round trip is judged against `PiiItem.value` in any case. A gateway
    returns the real value it stored, and demanding a tidy postal string back
    would fail every correct implementation on every voice case.
    """
    return _render_place_clean(place, form)


# --- rendering a person ---------------------------------------------------

@dataclass(frozen=True)
class _Person:
    given: str
    surname: str
    patronymic: str
    female: bool


def _draw_person(rng: random.Random, female: bool) -> _Person:
    """One person. The slot order is not fixed and neither is the slot count.

    Measured on the call corpus: a surname alone 350, a given name alone 255,
    given + patronymic 109, surname + given + patronymic 23, given + surname 23,
    a patronymic ON ITS OWN 29. A generator that always emits «Фамилия Имя
    Отчество» is testing one of six shapes.
    """
    if female:
        given = rng.choice(_GIVEN_F)
        patronymic = rng.choice(_PATRONYMIC_F)
        surname = rng.choice(_SURNAME_M) + "а"
    else:
        given = rng.choice(_GIVEN_M)
        patronymic = rng.choice(_PATRONYMIC_M)
        surname = rng.choice(_SURNAME_M)
    return _Person(given=given, surname=surname, patronymic=patronymic,
                   female=female)


def _render_person(person: _Person, form: str, register: str,
                   rng: random.Random) -> tuple[str, str, str]:
    """(text, mined shape id, canonical) for one way of naming this person.

    THE CANONICAL IS BUILT FROM THE SAME PARTS. A reply that carried a given name
    and a patronymic must not have a surname demanded back — that is the ground
    truth scoring the gateway on information the conversation never had, and
    AgentPII-RU has paid for it once already.

    `oblique` is 15% of the mentions in the call corpus (124 of 815) and it is
    the form a name dictionary in the nominative cannot see: «будьте добры
    ирочку», «к букину прибыть», «зинаиде николаевне». It is also the form whose
    round trip has to come BACK in the nominative, which is where a guard placed
    on the wrong side of `to_nominative` once sent a fake to the tool — so its
    canonical is the nominative and nothing else.
    """
    if form == "full":
        words = (person.surname, person.given, person.patronymic)
        shape = "calls:name.snp"
    elif form == "given_surname":
        words = (person.given, person.surname)
        shape = "calls:name.ns"
    elif form == "given_patronymic":
        patronymic = person.patronymic
        if not person.female and rng.random() < 0.35:
            patronymic = _PATRONYMIC_SHORT.get(patronymic, patronymic)
        words = (person.given, patronymic)
        shape = "calls:name.np"
    elif form == "given":
        words = (person.given,)
        shape = "calls:name.n"
    elif form == "surname":
        words = (person.surname,)
        shape = "calls:name.s"
    elif form == "oblique":
        table = _OBLIQUE_F if person.female else _OBLIQUE_M
        words = (table[person.given],)
        shape = "calls:name.n"
    elif form == "diminutive":
        words = (_DIMINUTIVE.get(person.given, person.given),)
        shape = "calls:name.n"
    else:
        raise InvalidCase(f"unknown name form {form!r}")
    canonical = " ".join(
        (person.given if form == "oblique" else word).capitalize()
        for word in words)
    text = " ".join(words)
    if register == "clean":
        text = " ".join(word.capitalize() for word in text.split(" "))
    if register == "sloppy":
        text = _typo_phrase(text, rng)
    return text, shape, canonical


# --- rendering a phone ----------------------------------------------------

def _draw_phone(rng: random.Random) -> str:
    """Eleven digits on a real Russian mobile prefix, no leading zero in a group.

    Real prefixes because libphonenumber is the first recognizer that sees it,
    and no leading zeros because a group like «05» is said «ноль пять» and the
    spelling table has one rule per group, not two.
    """
    return "8" + rng.choice(_MOBILE_PREFIX) + \
        str(rng.randrange(100, 1000)) + str(rng.randrange(10, 100)) + \
        str(rng.randrange(10, 100))


def _render_phone(digits: str, form: str, register: str,
                  rng: random.Random) -> str:
    """One of the shapes the SAME number arrives in.

    «+7 999…» and «8 999…» collapsing to one vault key is documented, deliberate
    behaviour, which is what makes the phone a fair vehicle for this family: the
    equality it is asked about is one the gateway has promised to preserve.
    """
    body = digits[1:]
    if form == "spoken":
        return _spell_phone(digits)
    if form == "plus_spaced":
        return f"+7 {body[:3]} {body[3:6]}-{body[6:8]}-{body[8:]}"
    if form == "eight_spaced":
        return f"8 {body[:3]} {body[3:6]} {body[6:8]} {body[8:]}"
    if form == "flat":
        return digits
    if form == "plus_flat":
        return f"+7{body}"
    raise InvalidCase(f"unknown phone form {form!r}")


def _phone_canonical(digits: str) -> str:
    return f"+7{digits[1:]}"


# --- the words around the value -------------------------------------------
#
# Drawn from the mined openers, where 101 of 154 address replies begin with NO
# introduction at all (65.6%). A generator that always says «здравствуйте, мой
# адрес» is writing a form the corpus produced twenty-six times out of a hundred
# and fifty-four, and it is the form a cue-word gate finds easiest.
_OPENERS_SPOKEN: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("а", 4), ("алло здравствуйте", 3),
    ("доброе утро", 2), ("здравствуйте а", 2), ("аа", 2), ("а здравствуйте", 2),
    ("девушка", 1), ("алло", 1), ("так", 1), ("ээ", 1),
)
_OPENERS_CLEAN: tuple[str, ...] = (
    "Добрый день.", "Здравствуйте.", "",
)
# A messenger opens differently from a phone call, and «девушка» typed into a
# chat window is a form the traffic does not contain. Weighted the same way — a
# little over half of the messages open with nothing.
_OPENERS_TYPED: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("привет", 12), ("добрый день", 8),
    ("а", 4),
)

_QUESTION: dict[str, dict[str, tuple[str, ...]]] = {
    "place": {
        "spoken": ("это тот же дом или нет", "это один и тот же адрес",
                   "это тот же адрес да или нет"),
        "typed": ("это тот же дом или нет?", "это один и тот же адрес?",
                  "это тот же адрес да или нет?"),
        "clean": ("это тот же адрес?", "это один и тот же дом?"),
    },
    "place3": {
        "spoken": ("это одно и то же место или нет",
                   "это один и тот же адрес или нет"),
        "typed": ("это одно и то же место или нет?",),
        "clean": ("это одно и то же место?",),
    },
    "person": {
        "spoken": ("это тот же человек или нет", "это один и тот же человек"),
        "typed": ("это тот же человек или нет?",),
        "clean": ("это один и тот же человек?",),
    },
    "phone": {
        "spoken": ("это один и тот же номер или нет", "это тот же номер"),
        "typed": ("это один и тот же номер или нет?",),
        "clean": ("это один и тот же номер?",),
    },
    "record": {
        "spoken": ("это тот же адрес что у вас записан или нет",),
        "typed": ("это тот же адрес что у вас записан или нет?",),
        "clean": ("это тот же адрес, который у вас записан?",),
    },
}


def _register_key(register: str) -> str:
    if register == "clean":
        return "clean"
    if register == "voice_raw" or register == "voice_itn":
        return "spoken"
    return "typed"


def _question(topic: str, register: str, rng: random.Random) -> str:
    return rng.choice(_QUESTION[topic][_register_key(register)])


def _opener(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_OPENERS_CLEAN)
    table = (_OPENERS_SPOKEN if register in ("voice_raw", "voice_itn")
             else _OPENERS_TYPED)
    population = [text for text, _ in table]
    weights = [count for _, count in table]
    return rng.choices(population, weights=weights, k=1)[0]


# The literary register writes ONE sentence, not two run together. «Вишнёвая,
# д. 10 Это тот же адрес?» is what a naive concatenation produces, and a `clean`
# case that reads like a bug report cannot show that we did not break on
# documents — which is the only reason the register has a budget at all.
_VALUE_LEAD_CLEAN: dict[str, str] = {
    "place": "Адрес подачи:", "place3": "Адрес подачи:",
    "person": "Клиент:", "phone": "Телефон:", "record": "Адрес подачи:",
}


def _value_lead(topic: str, register: str) -> str:
    return _VALUE_LEAD_CLEAN[topic] if register == "clean" else ""


def _stop(register: str) -> str:
    """The full stop that closes a literary sentence, and nothing elsewhere."""
    return "." if register == "clean" else ""


def _dash(register: str) -> str:
    """The dash that joins the repeated value to the question it is asked about."""
    return "—" if register == "clean" else ""


def _lead(kind: str, register: str) -> str:
    """The words that reopen a value already said. Real, not invented.

    `disc.re_ask` (165) and `disc.self_correction` (209) are the two commonest
    ways a value is said a second time in the call corpus, and they are the only
    two this family needs: a comparison IS a value said twice.
    """
    table = {
        "second": {"spoken": "а", "typed": "а", "clean": "А"},
        "correct": {"spoken": "подождите вы сказали", "typed": "подождите вы сказали",
                    "clean": "Подождите, вы сказали"},
        "insist": {"spoken": "нет я же сказал", "typed": "нет я же сказал",
                   "clean": "Нет, я же сказал:"},
    }
    return table[kind][_register_key(register)]


# --- negatives on the wire ------------------------------------------------

def _negative_clause(rng: random.Random, register: str,
                     tag: str) -> tuple[tuple[_Piece, ...], _Neg]:
    """One negative with the sentence that carries it, as pieces.

    The carrier is prose and is NOT part of the span: a gateway that masks
    «нам надо в» has not made an error anybody can name, while one that masks
    «три четырнадцатый кабинет» has broken the ride.

    `voice_itn` draws only from the negatives that carry a digit. The register is
    DEFINED by inverse text normalisation being on, and the schema refuses a
    voice_itn case with no digit in its user text as «a voice_raw case in
    disguise» — for the name arm, where the value itself has no digits, the
    negative is the only thing that can honestly supply one.
    """
    choices = _NEGATIVES
    if register == "voice_itn":
        choices = tuple(negative for negative in _NEGATIVES
                        if any(ch.isdigit() for ch in negative.written))
    negative = rng.choice(choices)
    carrier = negative.carrier
    text = _negative_text(negative, register)
    if register == "clean":
        return (_Piece("", carrier.capitalize()), _Piece(tag, text),
                _Piece("", ".")), negative
    return (_Piece("", carrier), _Piece(tag, text)), negative


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


@dataclass(frozen=True)
class _NegSpec:
    msg_key: str
    tag: str
    family: str
    why: str


_MIN_DEEP_CHARS_MARGIN: int = 4_400


def _long_filler(pool: tuple[str, ...]) -> tuple[str, ...]:
    """The long half of the pool, for the `deep` rung.

    MIN_DEEP_CHARS exists so that thirty two-word replies cannot pass for a long
    context. Padding a deep case with the median utterance satisfies the letter
    of that rule and breaks its intent — it reaches four thousand characters by
    stacking a hundred and thirty tiny turns, which is the same short context
    with more of it. The long half reaches the floor in about sixty.
    """
    ordered = sorted(pool, key=len, reverse=True)
    return tuple(ordered[:max(40, len(ordered) // 2)])


def _filler_pair(index: int, register: str, rng: random.Random,
                 pool: tuple[str, ...]) -> tuple[_Msg, _Msg]:
    """One customer turn that carries nothing and one operator acknowledgement."""
    if register == "clean":
        said = rng.choice(_FILLER_CLEAN)
        ack = rng.choice(_ACK_CLEAN)
    else:
        said = rng.choice(pool)
        ack = rng.choice(_ACK_SPOKEN)
        if register == "sloppy" and rng.random() < 0.4:
            said = _typo_phrase(said, rng)
    return (
        _msg(f"f{index}u", "user", (_Piece("", said),), "", None),
        _msg(f"f{index}a", "assistant", (_Piece("", ack),), "", None),
    )


def _pad(opening: tuple[_Msg, ...], closing: tuple[_Msg, ...], context: str,
         register: str, rng: random.Random,
         pool: tuple[str, ...]) -> tuple[_Msg, ...]:
    """Insert filler BETWEEN the first mention and the question.

    Between, not before: the depth this family cares about is the distance from
    the value to the question about it, and filler stacked in front of both
    lengthens the transcript without lengthening anything that matters.
    """
    if context in ("solo", "short"):
        pairs = 0 if context == "solo" else rng.randrange(0, 3)
    elif context == "long":
        pairs = rng.randrange(4, 13)
    else:
        pairs = 15
        pool = _long_filler(pool)
    middle: list[_Msg] = []
    index = 0
    # A `three_turn` case opens its closing with the AGENT speaking. Filler that
    # ends on an acknowledgement would put two assistant turns back to back,
    # which is not a transcript any gateway ever receives.
    trim_ack = bool(closing) and closing[0].role == "assistant"
    while True:
        total = len(opening) + len(middle) + len(closing)
        characters = sum(len(message.text)
                         for message in tuple(opening) + tuple(middle) + tuple(closing))
        if index >= pairs and (context != "deep"
                               or (total >= 33 and characters >= _MIN_DEEP_CHARS_MARGIN)):
            break
        if total >= 190:
            raise InvalidCase(
                f"padding a `{context}` case ran past 190 messages without "
                f"reaching {_MIN_DEEP_CHARS_MARGIN} characters; the filler pool "
                f"is too short for this rung")
        middle.extend(_filler_pair(index, register, rng, pool))
        index += 1
    if trim_ack and middle and middle[-1].role == "assistant":
        middle.pop()
    return tuple(opening) + tuple(middle) + tuple(closing)


def _finish(case_id: str, spec: "_Spec", messages: tuple[_Msg, ...],
            tools: tuple[dict[str, Any], ...], items: tuple[_ItemSpec, ...],
            negatives: tuple[_NegSpec, ...], links: tuple[LinkExpectation, ...],
            calls: tuple[ExpectedCall, ...], answer: str,
            provenance: Provenance, cluster: str, conversation_id: str,
            annotators: int, note: str) -> Case:
    """Resolve every span from the marks the builder recorded, then REFUSE or return.

    `validate` runs here rather than in `build`, so a broken case names itself at
    the moment it was constructed instead of arriving in a list of two hundred.
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
        conversation_id=conversation_id,
        messages=tuple(
            Message(role=message.role, content=message.text,
                    source=message.source, name=message.name)
            for message in messages),
        tools=tools,
        pii=tuple(pii),
        negatives=tuple(negative_rows),
        links=links,
        calls=calls,
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=answer),
        preceded_by="",
        annotators=annotators,
        adjudicated=False,
        note=note,
    )
    problems = validate(case)
    if problems:
        raise InvalidCase("\n".join(problems))
    return case


# --- the arms -------------------------------------------------------------

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
    that share a cluster must therefore share the value, and an interval computed
    over cases rather than clusters is narrower than the truth in our favour.
    """
    return random.Random(f"v3:{FAMILY}:{spec.seed}:{spec.arm}:draw{spec.draw}")


def _case_rng(spec: _Spec) -> random.Random:
    """The RNG that picks SURFACE. Keyed by the case, so registers differ."""
    return random.Random(f"v3:{FAMILY}:{spec.seed}:{spec.arm}:case{spec.index}")


def _system(text: str) -> _Msg:
    return _msg("sys", "system", (_Piece("", text),), "", None)


def _provenance(shape: str, corpus: str, selection: str,
                weight: float) -> Provenance:
    """`licence` is the licence of the TEXT THIS CASE CARRIES, not of the mining.

    A recombined case's sentence is ours — the mined artefact it follows is a
    PATTERN, and a pattern is not the expression a licence covers. `corpus` still
    names where the form was observed, so the two fields say two true things
    rather than one blurred one. Only `verbatim` carries somebody else's words,
    and only there does the corpus licence ride along.
    """
    return Provenance(kind="recombined", corpus=corpus, key="", shape=shape,
                      selection=selection, weight=weight, licence="authored")


def _pickup_call(value: str, item_id: str, after: int) -> ExpectedCall:
    return ExpectedCall(
        name="confirm_pickup",
        arguments={"address": value, "source": "телефон"},
        judged_args=("address",), pii_items=(item_id,), after_msg=after)


def _client_call(param: str, value: str, item_id: str,
                 after: int) -> ExpectedCall:
    return ExpectedCall(
        name="find_client",
        arguments={param: value, "channel": "телефон"},
        judged_args=(param,), pii_items=(item_id,), after_msg=after)


def _arm_place_same(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """One place, two forms, and the question is whether the gateway made it one.

    The FULL mention comes first and the PARTIAL second, and that order is the
    whole mechanism rather than a stylistic choice: the rule under test resolves
    a partial mention against a FULLER ONE SAID EARLIER inside one conversation,
    so a partial-then-full case would demand a link the rule correctly refuses
    and would fail a gateway for being right.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    place = _draw_place(draw, "")
    register = spec.register
    full = _render_place(place, "full", register, rng)
    partial = _render_place(place, "partial", register, rng)
    canonical_full = _place_canonical(place, "full")
    canonical_partial = _place_canonical(place, "partial")
    city = _render_city(place, register) if place.city_said else ""
    city_piece = (_Piece("c1", city),) if city else ()
    negative_pieces, negative = _negative_clause(rng, register, "n1")
    question = _question("place", register, rng)
    lead = _lead("second", register)
    opener = _opener(register, rng)

    if spec.context == "solo":
        messages = (
            _system(_SYSTEM_DISPATCH),
            _msg("first", "user",
                 (_Piece("", opener), _Piece("", _value_lead("place", register)),
                  *city_piece, _Piece("", "," if city and register == "clean"
                                      else ""),
                  _Piece("a1", full), _Piece("", _stop(register)),
                  *negative_pieces, _Piece("", lead), _Piece("a2", partial),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
    else:
        opening = (
            _system(_SYSTEM_DISPATCH),
            _msg("first", "user",
                 (_Piece("", opener), _Piece("", _value_lead("place", register)),
                  *city_piece, _Piece("", "," if city and register == "clean"
                                      else ""),
                  _Piece("a1", full), _Piece("", _stop(register)),
                  *negative_pieces), "", None),
        )
        closing = (
            _msg("ask", "user",
                 (_Piece("", lead), _Piece("a2", partial),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)

    first_key = "first"
    second_key = "first" if spec.context == "solo" else "ask"
    items = [
        _ItemSpec("a1", first_key, "a1", "LOC", full, canonical_full, "place.a",
                  "required", "pool", register == "voice_raw", "address"),
        _ItemSpec("a2", second_key, "a2", "LOC", partial, canonical_partial,
                  "place.a", "required", "pool", register == "voice_raw", ""),
    ]
    if city:
        items.append(_ItemSpec(
            "c1", first_key, "c1", "LOC", city, place.city.capitalize(),
            "place.city", "optional", "pool", register == "voice_raw", ""))
    items = tuple(items)
    return _finish(
        case_id=f"cmp-same-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=items,
        negatives=(_NegSpec(first_key, "n1", negative.family, negative.why),),
        links=(LinkExpectation(
            "a1", "a2", "same", "",
            "одно место названо дважды: полной формой и голой «улица+номер», "
            "которой две трети корпуса и пользуется"),),
        calls=(_pickup_call(full, "a1", len(messages) - 1),),
        answer="да",
        provenance=_provenance(_place_shape(place, "full"), "speech_rudevices",
                               "marker", 1.0),
        cluster=f"compare:same:{spec.draw:03d}",
        conversation_id=(f"cmp-same-{spec.index:03d}"
                         if spec.index % 2 == 0 else ""),
        annotators=0,
        note="полная и голая форма одного адреса; «да» возможно только если шлюз "
             "выдал обеим одну подмену",
    )


def _arm_place_diff(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """Two places, and the question is whether the gateway kept them apart.

    Both mentions are the BARE «<улица> <число>» shape, which is the owner's own
    example («ленина двадцать пять» против «ленина двадцать восемь») and the
    stratum a marker filter cannot see — so the arm carries `selection="random"`
    and the sampling weight that goes with it.

    Over-linking here is the expensive direction: one substitute for two houses
    makes the agent answer «да» and the car goes to the wrong door, and
    `classify_break` will name it `other_person` because the other value is in
    the same case.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    place_a = _draw_place(draw, "")
    if draw.random() < 0.6:
        house = place_a.house
        while house == place_a.house:
            house = max(1, place_a.house + draw.choice((-9, -5, -3, 3, 5, 11)))
        place_b = _Place(street=place_a.street, adjective=place_a.adjective,
                         type_word=place_a.type_word, house=house, entrance=0,
                         letter="", city=place_a.city, city_said=False)
        why = "тот же дом, но соседний номер — форма, в которой каноникализация "
        why += "чаще всего склеивает два адреса в один"
    else:
        place_b = _draw_place(draw, place_a.street)
        why = "две разные улицы в одном разговоре"
    register = spec.register
    first = _render_place(place_a, "partial", register, rng)
    second = _render_place(place_b, "partial", register, rng)
    if first == second:
        raise InvalidCase(f"{spec.arm} {spec.index}: two mentions rendered alike")
    negative_pieces, negative = _negative_clause(rng, register, "n1")
    question = _question("place", register, rng)
    lead = _lead("correct", register)
    opener = _opener(register, rng)

    if spec.context == "solo":
        messages = (
            _system(_SYSTEM_DISPATCH),
            _msg("first", "user",
                 (_Piece("", opener), _Piece("", _value_lead("place", register)),
                  _Piece("a1", first), _Piece("", _stop(register)),
                  *negative_pieces, _Piece("", lead), _Piece("a2", second),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
    else:
        opening = (
            _system(_SYSTEM_DISPATCH),
            _msg("first", "user",
                 (_Piece("", opener), _Piece("", _value_lead("place", register)),
                  _Piece("a1", first), _Piece("", _stop(register)),
                  *negative_pieces), "", None),
        )
        closing = (
            _msg("ask", "user",
                 (_Piece("", lead), _Piece("a2", second),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)

    first_key = "first"
    second_key = "first" if spec.context == "solo" else "ask"
    items = (
        _ItemSpec("a1", first_key, "a1", "LOC", first,
                  _place_canonical(place_a, "partial"),
                  "place.a", "required", "pool", register == "voice_raw",
                  "address"),
        _ItemSpec("a2", second_key, "a2", "LOC", second,
                  _place_canonical(place_b, "partial"), "place.b", "required",
                  "pool", register == "voice_raw", ""),
    )
    return _finish(
        case_id=f"cmp-diff-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=items,
        negatives=(_NegSpec(first_key, "n1", negative.family, negative.why),),
        links=(LinkExpectation("a1", "a2", "different", "", why),),
        calls=(_pickup_call(first, "a1", len(messages) - 1),),
        answer="нет",
        provenance=_provenance(_place_shape(place_a, "partial"),
                               "speech_rudevices", "random", 19.22),
        cluster=f"compare:diff:{spec.draw:03d}",
        conversation_id=(f"cmp-diff-{spec.index:03d}"
                         if spec.index % 2 == 0 else ""),
        annotators=0,
        note="два адреса в одном разговоре; «да» здесь означает, что шлюз склеил "
             "их в одну личность",
    )


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


def _arm_three_turn(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """THE OWNER'S CASE. The agent comes back with the wrong place and insists.

    «агент возвращается: вы находитесь на Пушкина 18? Он такой — нет, мы
    находимся на Ленина 14 … Агент отвечает: мы находимся на Пушкина 18.»

    The assistant turn is scripted because the corpus scripts HISTORY — and this
    arm is the only one that needs one, because the thing under test is what
    happens when the agent's own previous reply re-enters the request. That reply
    is masked again on the way in, so a gateway whose second masking disagrees
    with its first has a dialogue that diverges from itself while every axis
    except this question reports clean.

    The address the agent came back with is `optional`: it belongs to nobody in
    this conversation, so masking it is not an error and missing it is not a
    leak. It still gets an identity and a `different` link, because merging it
    with the customer's own address is exactly the failure being counted.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    place = _draw_place(draw, "")
    wrong = _draw_place(draw, place.street)
    register = spec.register
    form = "full" if spec.index % 2 == 0 else "partial"
    said = _render_place(place, form, register, rng)
    proposed = _render_place(wrong, "partial", register, rng)
    negative_pieces, negative = _negative_clause(rng, register, "n1")
    question = _prose(_question("place3", register, rng), register, rng)
    opener = _opener(register, rng)
    insist = _prose(_lead("insist", register), register, rng)
    reask_head = ("А вы находитесь" if register == "clean"
                  else "а вы находитесь")
    reask_tail = "?" if register in ("chat", "sloppy", "clean") else "да"

    opening = (
        _system(_SYSTEM_DISPATCH),
        _msg("first", "user",
             (_Piece("", opener), _Piece("", _value_lead("place3", register)),
              _Piece("a1", said), _Piece("", _stop(register)),
              *negative_pieces), "", None),
    )
    closing = (
        _msg("reask", "assistant",
             (_Piece("", reask_head), _Piece("b", proposed),
              _Piece("", reask_tail)), "", None),
        _msg("ask", "user",
             (_Piece("", insist), _Piece("a2", said),
              _Piece("", _dash(register)), _Piece("", question)), "", None),
    )
    messages = _pad(opening, closing, spec.context, register, rng, pool)
    canonical = _place_canonical(place, form)
    items = (
        _ItemSpec("a1", "first", "a1", "LOC", said, canonical, "place.a",
                  "required", "pool", register == "voice_raw", "address"),
        _ItemSpec("b", "reask", "b", "LOC", proposed,
                  _place_canonical(wrong, "partial"),
                  "place.b", "optional", "pool", register == "voice_raw", ""),
        _ItemSpec("a2", "ask", "a2", "LOC", said, canonical, "place.a",
                  "required", "pool", register == "voice_raw", ""),
    )
    selection = "marker" if form == "full" else "random"
    weight = 1.0 if form == "full" else 19.22
    return _finish(
        case_id=f"cmp-three-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=items,
        negatives=(_NegSpec("first", "n1", negative.family, negative.why),),
        links=(
            LinkExpectation("a1", "a2", "same", "",
                            "клиент повторил свой адрес слово в слово; две "
                            "подмены на нём означают, что второе маскирование "
                            "не согласилось с первым"),
            LinkExpectation("a1", "b", "different", "",
                            "адрес, который назвал агент, не адрес клиента — "
                            "слияние здесь и есть «бредятина»"),
        ),
        calls=(_pickup_call(said, "a1", len(messages) - 1),),
        answer="нет",
        provenance=_provenance("dispatch.reply:<филлер> <хвост> <АДРЕС> <филлер>",
                               "speech_rudevices", selection, weight),
        cluster=f"compare:three:{spec.draw:03d}",
        conversation_id=(f"cmp-three-{spec.index:03d}"
                         if spec.index % 2 == 0 else ""),
        annotators=0,
        note="трёхходовый случай владельца: агент переспрашивает чужим адресом, "
             "клиент поправляет своим, вопрос — совпадают ли они",
    )


def _arm_name(spec: _Spec, pool: tuple[str, ...], same: bool) -> Case:
    """«тебя Игорь зовут?» — one person named twice, or two people named once each.

    The `same` arm leans on canonicalisation: a name in an oblique case is 15% of
    the mentions in the call corpus (124 of 815) and the form a nominative
    dictionary cannot see. The `different` arm includes the pair a surname alone
    cannot separate — «кузнецов» against «кузнецова», a man and a woman — which
    is where a guard on the wrong side of `to_nominative` once collapsed two
    people into one.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    gender_pair = (not same) and draw.random() < 0.4

    if same:
        pairs = (("full", "given"), ("full", "surname"),
                 ("given_surname", "oblique"), ("given_patronymic", "given"),
                 ("given", "oblique"), ("given", "diminutive"))
        first_form, second_form = draw.choice(pairs)
        female = draw.random() < 0.4
        person = _draw_person(draw, female)
        if second_form == "diminutive" and person.given not in _DIMINUTIVE:
            person = _Person(given=draw.choice(
                [name for name in (_GIVEN_F if female else _GIVEN_M)
                 if name in _DIMINUTIVE] or [person.given]),
                surname=person.surname, patronymic=person.patronymic,
                female=female)
            if person.given not in _DIMINUTIVE:
                second_form = "oblique"
        other = person
    elif gender_pair:
        person = _draw_person(draw, False)
        other = _Person(given=draw.choice(_GIVEN_F), surname=person.surname + "а",
                        patronymic=draw.choice(_PATRONYMIC_F), female=True)
        first_form = second_form = "surname"
    else:
        person = _draw_person(draw, draw.random() < 0.4)
        other = _draw_person(draw, draw.random() < 0.4)
        while other.given == person.given:
            other = _draw_person(draw, other.female)
        first_form, second_form = draw.choice(
            (("given", "given"), ("full", "given_surname"),
             ("given_surname", "given_surname")))

    first, first_shape, first_canonical = _render_person(
        person, first_form, register, rng)
    second, _, second_canonical = _render_person(
        other, second_form, register, rng)
    if first == second:
        raise InvalidCase(f"{spec.arm} {spec.index}: both mentions rendered alike")

    cue = draw.choice(("", "", "это", "меня зовут", "говорит"))
    if cue == "это" and first_form == "given":
        first_shape = "calls:name.cue.это.n"
    elif cue == "меня зовут" and first_form == "given":
        first_shape = "calls:name.cue.меня_зовут.n"
    if register == "clean" and cue:
        cue = cue.capitalize()
    negative_pieces, negative = _negative_clause(rng, register, "n1")
    question = _prose(_question("person", register, rng), register, rng)
    lead = _prose(_lead("second" if same else "correct", register), register, rng)
    opener = "" if cue else _opener(register, rng)

    if spec.context == "solo":
        messages = (
            _system(_SYSTEM_SUPPORT),
            _msg("first", "user",
                 (_Piece("", opener), _Piece("", cue),
                  _Piece("", "" if cue else _value_lead("person", register)),
                  _Piece("a1", first), _Piece("", _stop(register)),
                  *negative_pieces, _Piece("", lead), _Piece("a2", second),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
    else:
        opening = (
            _system(_SYSTEM_SUPPORT),
            _msg("first", "user",
                 (_Piece("", opener), _Piece("", cue),
                  _Piece("", "" if cue else _value_lead("person", register)),
                  _Piece("a1", first), _Piece("", _stop(register)),
                  *negative_pieces), "", None),
        )
        closing = (
            _msg("ask", "user",
                 (_Piece("", lead), _Piece("a2", second),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)

    first_key = "first"
    second_key = "first" if spec.context == "solo" else "ask"
    items = (
        _ItemSpec("a1", first_key, "a1", "NAME", first, first_canonical,
                  "person.a", "required", "pool", False, "name"),
        _ItemSpec("a2", second_key, "a2", "NAME", second, second_canonical,
                  "person.a" if same else "person.b", "required", "pool", False,
                  ""),
    )
    kind = "same" if same else "different"
    why = ("один человек, названный дважды — во втором упоминании форма другая"
           if same else
           ("фамилия мужчины и фамилия женщины отличаются одной буквой; "
            "склеивание здесь звонит не тому человеку" if gender_pair else
            "два разных человека в одном разговоре"))
    return _finish(
        case_id=f"cmp-name-{kind[:4]}-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=(_NegSpec(first_key, "n1", negative.family, negative.why),),
        links=(LinkExpectation("a1", "a2", kind, "", why),),
        calls=(_client_call("name", first, "a1", len(messages) - 1),),
        answer="да" if same else "нет",
        provenance=_provenance(first_shape, "speech_calls", "census", 1.0),
        cluster=f"compare:name-{kind}:{spec.draw:03d}",
        conversation_id=(f"cmp-name-{spec.index:03d}"
                         if spec.index % 2 == 0 else ""),
        annotators=0,
        note=("одна личность в двух формах имени" if same else
              "две личности; «да» означает, что шлюз выдал им одну подмену"),
    )


def _arm_phone(spec: _Spec, pool: tuple[str, ...], same: bool) -> Case:
    """The one equality the gateway has PROMISED to preserve.

    «+7 999…» and «8 999…» collapsing to one vault key is documented, deliberate
    behaviour, so asking whether two writings of one number reach the model as
    one substitute is a fair question with a right answer — unlike the address,
    where the honest finding is that no canonicaliser can be expected to know.

    A sixth of the `same` cases put the SECOND mention in words. That mention
    carries no digit at all, and the digit form is deliberately said FIRST: if
    the two do link, the tool receives the value stored first, and demanding the
    spelled-out form back would fail a gateway for doing the right thing.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    digits = _draw_phone(draw)
    # A number SPELLED OUT is what a transcriber writes, not what a customer
    # types, so the dictated form is confined to the ASR register. Elsewhere
    # it would be a shape the traffic does not contain.
    dictated = same and register == "voice_itn"
    first_form = draw.choice(("plus_spaced", "eight_spaced", "flat"))
    if same:
        second_form = "spoken" if dictated else draw.choice(
            tuple(form for form in ("plus_spaced", "eight_spaced", "flat",
                                    "plus_flat") if form != first_form))
        other_digits = digits
    else:
        other_digits = _draw_phone(draw)
        while other_digits[-10:] == digits[-10:]:
            other_digits = _draw_phone(draw)
        second_form = draw.choice(("plus_spaced", "eight_spaced", "flat"))
    first = _render_phone(digits, first_form, register, rng)
    second = _render_phone(other_digits, second_form, register, rng)
    cue = draw.choice(("мой номер", "телефон", "записывай", "мой телефон"))
    if register == "clean":
        cue = cue.capitalize()
    negative_pieces, negative = _negative_clause(rng, register, "n1")
    question = _prose(_question("phone", register, rng), register, rng)
    lead = _prose(_lead("second" if same else "correct", register), register, rng)

    if spec.context == "solo":
        messages = (
            _system(_SYSTEM_SUPPORT),
            _msg("first", "user",
                 (_Piece("", cue), _Piece("", ":" if register == "clean" else ""),
                  _Piece("a1", first), _Piece("", _stop(register)),
                  *negative_pieces, _Piece("", lead), _Piece("a2", second),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
    else:
        opening = (
            _system(_SYSTEM_SUPPORT),
            _msg("first", "user",
                 (_Piece("", cue), _Piece("", ":" if register == "clean" else ""),
                  _Piece("a1", first), _Piece("", _stop(register)),
                  *negative_pieces), "", None),
        )
        closing = (
            _msg("ask", "user",
                 (_Piece("", lead), _Piece("a2", second),
                  _Piece("", _dash(register)), _Piece("", question)),
                 "", None),
        )
        messages = _pad(opening, closing, spec.context, register, rng, pool)

    first_key = "first"
    second_key = "first" if spec.context == "solo" else "ask"
    items = (
        _ItemSpec("a1", first_key, "a1", "PHONE", first,
                  _phone_canonical(digits), "phone.a", "required", "template",
                  False, "phone"),
        _ItemSpec("a2", second_key, "a2", "PHONE", second,
                  _phone_canonical(other_digits),
                  "phone.a" if same else "phone.b", "required", "template",
                  second_form == "spoken", ""),
    )
    kind = "same" if same else "different"
    return _finish(
        case_id=f"cmp-phone-{kind[:4]}-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PERSON, items=items,
        negatives=(_NegSpec(first_key, "n1", negative.family, negative.why),),
        links=(LinkExpectation(
            "a1", "a2", kind, "",
            "один номер в двух написаниях — каноникализация обещает свести их к "
            "одному ключу" if same else "два разных номера в одном разговоре"),),
        calls=(_client_call("phone", first, "a1", len(messages) - 1),),
        answer="да" if same else "нет",
        provenance=_provenance(
            "calls:num.phone_by_pairs" if dictated else "calls:disc.dictation",
            "speech_calls", "census", 1.0),
        cluster=f"compare:phone-{kind}:{spec.draw:03d}",
        conversation_id=(f"cmp-phone-{spec.index:03d}"
                         if spec.index % 2 == 0 else ""),
        annotators=0,
        note=("продиктованный словами номер рядом с цифровым" if dictated else
              ("один номер, два написания" if same else "два разных номера")),
    )


def _arm_verbatim(spec: _Spec, pool: tuple[str, ...]) -> Case:
    """A real caller naming TWO destinations in one unchanged reply.

    The strongest provenance the corpus has: the text is a SOVA RuDevices
    utterance, CC BY 4.0, unaltered, with the spans a human annotator drew. The
    only authored part is the equality question, and the `note` on every case
    says so — a `verbatim` label that quietly covered an authored sentence would
    be the same overclaim the provenance field exists to prevent.
    """
    rng = _case_rng(spec)
    row = _VERBATIM[spec.index % len(_VERBATIM)]
    text = str(row["text"])
    marks: dict[str, tuple[int, int]] = {}
    for position, span in enumerate(tuple(row["spans"])):
        start = text.index(span)
        marks[f"a{position + 1}"] = (start, start + len(span))
    for position, span in enumerate(tuple(row["optional"])):
        start = text.index(span)
        marks[f"o{position + 1}"] = (start, start + len(span))
    source = Source(corpus="speech_rudevices", key=str(row["key"]),
                    line=int(row["line"]),
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    licence="CC BY 4.0")
    said = _Msg(key="first", role="user", text=text, marks=marks, name="",
                source=source)
    negative_pieces, negative = _negative_clause(rng, "voice_raw", "n1")
    question = _question("place", "voice_raw", rng)

    opening = (_system(_SYSTEM_DISPATCH), said)
    closing = (
        _msg("aside", "user", negative_pieces, "", None),
        _msg("ask", "user", (_Piece("", question),), "", None),
    )
    messages = _pad(opening, closing, spec.context, "voice_raw", rng, pool)

    spans = tuple(row["spans"])
    items = [
        _ItemSpec("a1", "first", "a1", "LOC", spans[0], spans[0], "place.a",
                  "required", "corpus", True, "address"),
        _ItemSpec("a2", "first", "a2", "LOC", spans[1], spans[1], "place.b",
                  "required", "corpus", True, ""),
    ]
    for position, span in enumerate(tuple(row["optional"])):
        items.append(_ItemSpec(
            f"o{position + 1}", "first", f"o{position + 1}", "LOC", span, span,
            f"place.o{position + 1}", "optional", "corpus", True, ""))
    return _finish(
        case_id=f"cmp-verb-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_PLACE, items=tuple(items),
        negatives=(_NegSpec("aside", "n1", negative.family, negative.why),),
        links=(LinkExpectation(
            "a1", "a2", "different", "",
            "две точки маршрута в одной настоящей реплике: каждая десятая "
            "адресная реплика диспетчерской несёт их две"),),
        calls=(_pickup_call(spans[0], "a1", len(messages) - 1),),
        answer="нет",
        provenance=Provenance(
            kind="verbatim", corpus="speech_rudevices", key=str(row["key"]),
            shape="", selection="marker", weight=1.0, licence="CC BY 4.0"),
        cluster=f"compare:verbatim:{row['cluster']}",
        conversation_id="" if spec.index % 2 else f"cmp-verb-{spec.index:03d}",
        annotators=1,
        note="настоящая реплика SOVA RuDevices, не изменённая; вопрос о "
             "равенстве двух её адресов дописан",
    )


def _arm_record(spec: _Spec, pool: tuple[str, ...], same: bool) -> Case:
    """The address on file, arriving from the CRM and compared with the spoken one.

    The third leg of the contract inside this family's question: the value the
    agent compares against did not come from the customer's mouth, it came back
    from the customer's own system and was masked on the way TO the model. A
    gateway that masks the inbound row into a substitute unrelated to the one it
    minted for the spoken mention makes the comparison unanswerable in a way that
    no user-side test can see.
    """
    draw = _draw_rng(spec)
    rng = _case_rng(spec)
    register = spec.register
    place = _draw_place(draw, "")
    stored_place = place if same else _draw_place(draw, place.street)
    said = _render_place(place, "full", register, rng)
    stored = _render_place_clean(stored_place, "full")
    stored = stored[0].upper() + stored[1:]
    negative_pieces, negative = _negative_clause(rng, register, "n1")
    question = _prose(_question("record", register, rng), register, rng)
    opener = _opener(register, rng)

    head = '{"client_id": "'
    client_id = f"c-{4000 + spec.index}"
    middle = '", "address": "'
    tail = '"}'
    content = head + client_id + middle + stored + tail
    record = _Msg(
        key="crm", role="tool", text=content,
        marks={"n2": (len(head), len(head) + len(client_id)),
               "b": (len(head) + len(client_id) + len(middle),
                     len(head) + len(client_id) + len(middle) + len(stored))},
        name="lookup_client_address", source=None)

    opening = (
        _system(_SYSTEM_DISPATCH),
        _msg("first", "user", (_Piece("", opener), *negative_pieces), "", None),
    )
    closing = (
        _msg("ask", "user",
             (_Piece("", _value_lead("record", register)), _Piece("a1", said),
              _Piece("", _dash(register)), _Piece("", question)), "", None),
        record,
    )
    messages = _pad(opening, closing, spec.context, register, rng, pool)
    items = (
        _ItemSpec("a1", "ask", "a1", "LOC", said,
                  _place_canonical(place, "full"),
                  "place.a", "required", "pool", register == "voice_raw",
                  "address"),
        _ItemSpec("b", "crm", "b", "LOC", stored,
                  _place_canonical(stored_place, "full"),
                  "place.a" if same else "place.b", "required", "pool", False,
                  ""),
    )
    kind = "same" if same else "different"
    return _finish(
        case_id=f"cmp-rec-{kind[:4]}-{spec.index:03d}",
        spec=spec, messages=messages, tools=_TOOLS_RECORD, items=items,
        negatives=(
            _NegSpec("first", "n1", negative.family, negative.why),
            _NegSpec("crm", "n2", "order_number",
                     "внутренний идентификатор карточки — не персональные данные"),
        ),
        links=(LinkExpectation(
            "a1", "b", kind, "",
            "сказанный адрес и записанный в карточке — одно место в двух "
            "написаниях" if same else
            "в карточке лежит устаревший адрес; клиент переехал"),),
        calls=(_pickup_call(said, "a1", len(messages) - 1),),
        answer="да" if same else "нет",
        provenance=_provenance(_place_shape(place, "full"), "speech_rudevices",
                               "marker", 1.0),
        cluster=f"compare:record-{kind}:{spec.draw:03d}",
        conversation_id=(f"cmp-rec-{spec.index:03d}"
                         if spec.index % 2 == 0 else ""),
        annotators=0,
        note="адрес из карточки клиента приходит ответом инструмента и "
             "сравнивается с произнесённым",
    )


# --- the plan -------------------------------------------------------------
#
# ARM, COUNT, ALLOWED REGISTERS, ALLOWED CONTEXT RUNGS. Ordered most-constrained
# first, because the allocator is greedy and a free arm can always absorb what a
# constrained one could not take.
#
# The constraints are facts about the arms, not preferences. `verbatim` is a real
# ASR utterance and cannot be re-registered without ceasing to be verbatim. The
# phone arm cannot be `voice_raw`, because the schema refuses a digit there and a
# phone whose every mention is spelled out is the `spoken_id` family's question,
# not this one. `three_turn` needs four messages and `record` needs three, so
# neither fits the `solo` band.
_ARM_PLAN: tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...] = (
    ("verbatim", 15, ("voice_raw",), ("short", "long", "deep")),
    ("record_same", 7, ("voice_itn", "chat"), ("short", "long")),
    ("record_diff", 8, ("voice_raw", "voice_itn", "chat"), ("short", "long")),
    ("phone_same", 18, ("voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long")),
    ("phone_diff", 12, ("voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long")),
    ("three_turn", 45,
     ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("short", "long", "deep")),
    ("name_same", 25, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
    ("name_diff", 20, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
    ("place_diff", 45, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
    ("place_same", 55, ("voice_raw", "voice_itn", "chat", "sloppy", "clean"),
     ("solo", "short", "long", "deep")),
)

# Measured against 53 324 real utterances rather than chosen: speech is the base
# of this product's traffic and the literary register is the corner. `clean` here
# is 4%, inside the corpus-wide 5% cap, and it exists only to show we did not
# break on a web form.
_REGISTER_MIX: tuple[tuple[str, int], ...] = (
    ("voice_raw", 137), ("voice_itn", 37), ("chat", 45), ("sloppy", 21),
    ("clean", 10),
)
_CONTEXT_MIX: tuple[tuple[str, int], ...] = (
    ("solo", 90), ("short", 92), ("long", 52), ("deep", 16),
)

# A literary case has no real filler to pad with — the speech corpora supply
# every non-PII line this family uses, and ten authored sentences repeated sixty
# times is not a long context, it is one sentence sixty times.
_NO_DEEP: frozenset[str] = frozenset({"clean"})


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

    WEIGHTED BY WHAT REMAINS, not greedy on the largest. Greedy was the first
    version and it starved every small quota until the end of the list: the
    literary register — ten cases in two hundred and fifty — landed entirely on
    the last arm, so `clean` existed in the corpus and crossed nothing. A rung of
    the ladder is supposed to close every dimension, and a register that only
    ever occurs with one arm cannot help it.

    Arms are still processed most-constrained-first, which is what keeps the
    weighted draw feasible: an arm that can only take `voice_raw` has taken its
    share before an arm that can take anything starts.
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


# Arms whose value pool is thin enough that pairing two cases onto one draw
# would show up as a distinct-value count nobody should trust. The place arms
# keep the pairing — it is what makes `cluster` mean something, and «one address
# said by seven callers is one value and seven occurrences» is a rule this corpus
# has to be able to demonstrate on itself.
_ONE_DRAW_PER_CASE: frozenset[str] = frozenset({
    "verbatim", "name_same", "name_diff", "phone_same", "phone_diff",
    "record_same", "record_diff",
})


_ARMS: dict[str, Any] = {
    "place_same": _arm_place_same,
    "place_diff": _arm_place_diff,
    "three_turn": _arm_three_turn,
    "name_same": lambda spec, pool: _arm_name(spec, pool, True),
    "name_diff": lambda spec, pool: _arm_name(spec, pool, False),
    "phone_same": lambda spec, pool: _arm_phone(spec, pool, True),
    "phone_diff": lambda spec, pool: _arm_phone(spec, pool, False),
    "verbatim": _arm_verbatim,
    "record_same": lambda spec, pool: _arm_record(spec, pool, True),
    "record_diff": lambda spec, pool: _arm_record(spec, pool, False),
}


def build(seed: int, count: int) -> list[Case]:
    """Every case this family contributes, in file order.

    The RNG is the family's own — `random.Random(f"v3:{FAMILY}:{seed}")` — so the
    output does not move when a module built before this one changes how many
    draws it makes. Every case is validated at construction: a corpus that
    refuses late tells you which two hundred cases might be wrong, and a family
    that refuses early tells you which one is.
    """
    _verify_shapes()
    _verify_verbatim()
    pool = _filler_pool()
    rng = random.Random(f"v3:{FAMILY}:{seed}")
    cases = [_ARMS[spec.arm](spec, pool) for spec in _plan(seed, count, rng)]
    if count == TARGET:
        _verify_emitted_shapes(cases)
    return cases


# --- the scoring contract -------------------------------------------------
#
# HERE, not in the scorer, for the same reason `same_value` is in the schema: a
# scorer that invents its own parser invents its own number, and the two numbers
# this family reports are the only thing it has to say.

def classify_answer(text: str | None) -> str:
    """One of «да», «нет», `refusal`, `absent`.

    ORDER MATTERS AND IT IS NOT ARBITRARY. A reply that OPENS with да or нет has
    answered, whatever it hedges afterwards: the customer reads the first word
    and acts on it, so «Нет, я не могу подтвердить» to a question whose answer is
    «да» is a wrong answer delivered, not an abstention, and it earns no soft
    credit. Only a reply that does not open with one is searched for a refusal.

    `absent` is a MODEL outcome, not a gateway one, and it is the reason
    `score_answer` cannot be read alone: it passes neither number, so a suite
    where the model simply stopped answering looks exactly like a suite where the
    gateway broke every link. The count is printed beside the two rates for that
    reason, the way τ²-bench prints `infra_error_count` beside its metrics.
    """
    if text is None:
        return "absent"
    stripped = text.strip().lower().lstrip("«\"'—- ")
    if stripped.startswith("да"):
        return "да"
    if stripped.startswith("нет"):
        return "нет"
    if any(marker in stripped for marker in _REFUSALS):
        return "refusal"
    flattened = f" {stripped.replace(',', ' ').replace('.', ' ')} "
    for word in ("нет", "да"):
        if f" {word} " in flattened:
            return word
    return "absent"


def score_answer(case: Case, reply: str | None) -> tuple[bool, bool]:
    """(strict, soft) for one case's final assistant text. STRICT IS THE HEADLINE.

    STRICT   the parsed answer equals `case.final.answer`. Nothing else passes.
    SOFT     a refusal also passes.

    Printed side by side and never merged. A gateway that breaks linking so badly
    that the model stops answering is meaningfully better than one that makes it
    answer wrongly with confidence, and only the gap says which the product has.
    A confident wrong answer passes neither.

    AND NEITHER NUMBER MAY BE PRINTED WITHOUT THE `answer_absent` COUNT. A reply
    that parses to nothing fails both, so a model that stopped answering and a
    gateway that broke every link produce the same pair of rates; only the third
    number tells them apart, and it is the model's, not ours.
    """
    if not case.final.answer:
        raise InvalidCase(f"{case.id}: no closed answer to score against")
    parsed = classify_answer(reply)
    strict = parsed == case.final.answer
    return strict, strict or parsed == "refusal"


def answer_verdict(case: Case, reply: str | None) -> str:
    """The closed question's outcome as one of the schema's `ANSWER_VERDICTS`.

    Only the closed-question part. `substitute_shown` and `token_shown` are
    decided by the caller against the vault and take no ground truth, which is
    this benchmark's advantage over every LLM-judged one — the judge cannot know
    which string was real and we do.
    """
    parsed = classify_answer(reply)
    if parsed == case.final.answer:
        return "clean"
    if parsed in ("absent", "refusal"):
        return "answer_absent"
    return "answer_wrong"


# --- self-check -----------------------------------------------------------

def main() -> int:
    """Build the family and print what it actually contains.

    Prints the composition rather than a pass line, because the failure this
    module can have and still «pass» is a mix that drifted: v2 described its
    register split in a design document and shipped the opposite one, and the
    only thing that would have caught it is a build that says out loud what it
    made.
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
    print("answer     ", tally(lambda c: c.final.answer))
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
    print(f"spoken items {spoken}")
    print("gold items ", dict(sorted(type_denominators(cases).items())))
    print("distinct   ", distinct_values(cases))
    print(f"clusters   {len({case.cluster for case in cases})}")
    unused = sorted(set(_SHAPES)
                    - {case.provenance.shape for case in cases})
    print(f"shapes declared and not emitted at this seed: {len(unused)}")
    for shape in unused:
        print(f"  {shape}")
    longest = max(cases, key=lambda c: sum(len(m.content) for m in c.messages))
    print(f"longest    {longest.id}: {len(longest.messages)} messages, "
          f"{sum(len(m.content) for m in longest.messages)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
