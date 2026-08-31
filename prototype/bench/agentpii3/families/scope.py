"""The `scope` family — the conversation boundary, measured in BOTH directions
and with a control arm that tells «не связал» apart from «сломан».

WHY THIS FAMILY CANNOT BE ONE CASE. Every other family states its claim inside a
single transcript. This one cannot: «эти два упоминания обязаны слиться» and «эти
два упоминания обязаны НЕ слиться» are claims about what one tenant vault does
across TWO conversations, and a case carries exactly one `conversation_id`. So a
unit here is a PAIR of cases joined by `preceded_by`, scored in file order
against one vault — the only construction in the schema that can say «these two
must stay apart» at all.

THE MECHANISM UNDER TEST, stated from the product side rather than from ours. A
partial mention («Луговая, 7») may resolve against a fuller one said earlier —
«г. Омск, улица Луговая, д. 7, кв. 14» — but only inside ONE conversation. The
bound is arithmetic, not caution: that street and that house number exist in
every Russian city, so at tenant scope the single-candidate rule finds a dozen
owners and refuses every time. The scope is what makes the rule mean anything AND
what makes it safe, and both halves have to be measured or the number is a
half-truth.

FOUR ARMS, AND THE LAST TWO ARE THE POINT.

  within   the partial mention arrives in the SAME conversation as the fuller
           one. It must reach the model as one entity. A gateway that never
           links fails here and nowhere else in this family's first half.
  across   the same partial mention arrives in a DIFFERENT conversation. It must
           NOT link: linking hands one customer's building to another customer's
           dialogue, and the car goes to a door nobody in that dialogue named.
  phone    THE CONTROL. A phone canonicalises across the whole TENANT by
           design — «+7 999…» and «8 999…» collapse to one key so the model sees
           a stable identity across turns — so the same number in two
           conversations must link. This is a different mechanism from the one
           `within` exercises, not a second look at it: one is a
           conversation-scoped projection of an address, the other is a
           tenant-wide canonical key, and either can be broken while the other
           works.
  full     THE SECOND CONTROL, for the tenant-wide half of the ADDRESS rule. A
           full address keeps the plain key: one place, one substitute, for ever
           and across conversations.

EVERY ARM EARNS ITS PLACE, and the way to see it is to ask what each broken
gateway scores. Written as a table because it is the argument for the family's
composition, and without it the two controls look like padding:

                                   within  across  phone  full
  never links at all                 ✗       ✓       ✗      ✗
  links everything, tenant-wide      ✓       ✗       ✓      ✓
  scopes EVERYTHING to conversation  ✓       ✓       ✗      ✗
  correct                            ✓       ✓       ✓      ✓

The third row is the dangerous one and it is the reason both controls exist: it
is the obvious fix somebody reaches for after `across` fails, it satisfies the
whole first half of this family, and only an arm that demands linking ACROSS a
boundary can see it. Eighteen of the fifty cases are therefore control arms —
five `phone` pairs and four `full` pairs against nine `across` and seven
`within`.

WHY A `transfer` CASE IS EMITTED FROM HERE, and it is one case out of fifty-one.
`schema.validate` refuses a `scope` case with an empty `preceded_by` — every half
of every pair must name a predecessor sharing its vault. A dependency graph in
which every node has a parent needs a root, and a root cannot be a `scope` case
without an infinite regress. The root therefore carries no scope claim, and a
case with no scope claim is not a scope case: it is one customer stating personal
data that one call consumes, which is the definition of `transfer`. Pointing the
root into another module's ids was the alternative and was rejected — this module
cannot verify an id it does not build, and a pin that nothing checks is how a
benchmark goes on printing numbers after the ground moved.

THE SHAPE OF THE DEPENDENCY IS A SHALLOW TREE, NOT A CHAIN. Every anchor points
at the root; every probe points at its own anchor. A chain would have been the
lazier construction and it makes a TIER unrunnable: the ladder cuts subsets, and
a nano rung holding pair 24 would have had to drag the twenty-three pairs before
it into the vault to be scored at all. Two levels means a probe costs exactly two
cases.

WHICH AXIS DECIDES WHAT, because reading this family off the round-trip rate
alone would be reading it wrong:

  * the LINK axis is the primary measurement here. `LinkExpectation.kind` is
    `same` or `different`, `LinkExpectation.case` names the other conversation,
    and the comparison is between the SUBSTITUTES the gateway minted. A linked
    partial mention is not handed the fuller substitute verbatim — it is handed
    the corresponding PART of it — so «one value» means one identity, never one
    string, and a scorer that tests the substitutes for string equality is
    testing something this family never claimed.
  * the ROUND TRIP catches the worst outcome and only the worst: an over-linking
    gateway hands the tool a real address belonging to the OTHER conversation's
    customer, which `classify_break` names `other_person`. For that name to be
    reachable a scorer must feed BOTH the surface value and the canonical of the
    chain's items into `other_values`; the `across` probes therefore ALSO forbid
    the anchor's real address in the final answer, so the same failure is caught
    a second time by machinery that takes no scorer cooperation at all.
  * the ANSWER axis carries that `must_not_contain`. It is the axis WebArena's
    812 official cases use zero times, and it is the only one that names a
    disclosure rather than an omission.

REGISTER. Speech is the base and it is the base here too: 36 of the 50 cases are
`voice_raw` or `voice_itn`, two are literary. The phone arm cannot be `voice_raw`
— the schema refuses a digit there, and a number spelled out is the `spoken_id`
family's question, not this one's — so it lives in the registers that carry
digits. Every register transform is applied WHILE the string is built; nothing
here searches a finished message for a value it already knows it put there, which
is the bug that ate 162 of v2's 183 sloppy failures.

THE FORM COMES FROM THE MINED GRAMMAR AND THE CLAIM IS CHECKED FROM BOTH ENDS.
`_verify_shapes()` refuses at import if a declared id is not in `mined/`;
`_verify_emitted_shapes()` refuses at build if a case claims an id the inventory
does not declare. The commonest reply shape in the dispatch corpus is the address
ALONE — 59 of 154 replies, no greeting, no verb — and that is what a probe says.

THE ENTRY POINT is `build(seed, count)`, where `count` is the number of SCOPE
cases and the returned list is one longer than that, because of the root.
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
    LinkExpectation, Message, Negative, PiiItem, Provenance,
    distinct_values, type_denominators, validate,
)

FAMILY = "scope"
# SCOPE cases. `build` returns TARGET + 1, the extra one being the root the
# schema's own «a scope case needs a predecessor» rule forces into existence.
TARGET = 50
ROOT_ID = "sc-tenant-000"
# The root is not a `scope` case and the docstring says why at length. Named
# here as a constant rather than written inline, so the one place the family
# steps outside its own label is greppable.
ROOT_FAMILY = "transfer"

# Rides WITH THE CORPUS. The street vocabulary below is the hand-annotated
# address value set of SOVA RuDevices, and a consumer receives a dataset rather
# than a repository — an attribution that lives only in a source tree has not
# been given.
ATTRIBUTION: str = "SOVA Dataset / RuDevices, распространяется по CC BY 4.0"

_MINED = Path(__file__).resolve().parent.parent / "mined"
_FILLER_PATH: Path = (Path.home() / ".cache" / "pseudex-bench"
                      / "rudevices_addresses.json")


# --- pools ----------------------------------------------------------------
#
# STREETS ARE REAL and they come from the shippable corpus only. An invented
# street pool would put this family on a vocabulary nobody speaks, and the ГАР
# cut measurement says where that goes wrong: the commonest Russian street names
# ARE ordinary words, so a pool of pretty ones tests the easy half.
#
# Split by HOW THE NAME IS BUILT, because the mined grammar says the language has
# two ways and only two: a feminine adjective, or a surname in the genitive.
# Masculine adjectival names («смольный», «загородный») are deliberately absent —
# they take «переулок»/«проезд» and not «улица», and a generator that draws the
# type word freely produces «улица Смольный», which is not a form any recognizer
# will ever meet and therefore not a form worth measuring on.
_STREET_GENITIVE: tuple[str, ...] = (
    "ленина", "калашникова", "барышникова", "тимирязева", "баранова",
    "кирова", "коммунаров", "энгельса", "павлова", "чапаева", "репина",
    "халтурина", "телегина", "петрова", "бабушкина", "металлистов",
    "красина", "шумайлова", "циолковского", "некрасова", "сабурова",
    "маяковского", "ломоносова", "гусева", "воровского", "гагарина",
    "грибоедова", "машиностроителей", "строителей", "лермонтова",
    "комиссарова", "челюскинцев", "барамзиной", "люхвинцева",
)
_STREET_ADJECTIVE: tuple[str, ...] = (
    "луговая", "пушкинская", "клубная", "удмуртская", "нижняя", "союзная",
    "восточная", "буммашевская", "подлесная", "садовая", "школьная",
    "вишнёвая", "майская", "совхозная", "деловая", "полевая", "выставочная",
    "камская", "базисная", "химзаводская", "зеленоградская", "фруктовая",
    "фронтовая", "ракетная", "молодёжная", "русская", "армейская",
    "комсомольская", "ключевая", "транспортная",
)

# The settlement is an `optional` span, never part of the required address and
# never a required item of its own: a city identifies nobody under 152-ФЗ ст. 3
# п. 1, so masking it is not an error and missing it is not a leak. It is said
# in front of the address in the anchor and NEVER in the probe, because a
# mention that already names its city is not a short mention — it is either the
# whole address or a different place, and the whole subject of this family is
# what happens to the short one.
#
# The two halves of an `across` pair are deliberately in DIFFERENT cities. The
# probe never says so — that is what makes it a partial mention — but it is the
# fact the requirement rests on: «Луговая, 7» in Тверь is not «Луговая, 7» in
# Омск, and a gateway that merges them has sent a car to another city's building.
_CITIES: tuple[str, ...] = (
    "омск", "воронеж", "ижевск", "казань", "самара", "пермь", "тверь",
    "курск", "брянск", "орёл", "рязань", "томск", "калуга", "псков",
)

# NAMES ARE AUTHORED, and that is the licence-safe choice rather than a lazy
# one: the surnames the call corpus produced are CC BY-NC and its text may not
# ship. What IS taken from the mining is the SHAPE inventory — which slots are
# filled and how often a patronymic contracts.
_GIVEN_M: tuple[str, ...] = (
    "игорь", "олег", "сергей", "андрей", "дмитрий", "максим", "кирилл",
    "руслан", "тимур", "антон", "павел", "роман", "никита", "артём",
    "василий", "валерий", "леонид", "юрий", "борис", "виктор",
)
_GIVEN_F: tuple[str, ...] = (
    "марина", "ольга", "елена", "наталья", "ирина", "светлана", "анна",
    "татьяна", "лариса", "галина", "вера", "зинаида", "полина", "алина",
)
# Thirty-two, and the size is a requirement rather than generosity: twenty-five
# units draw a surname WITHOUT REPLACEMENT, and a pool a corpus can exhaust is a
# permanent failure for whoever asks for one case more. That has happened twice
# in this product — addresses at 33, gender-invariant surnames at 6 — so the
# floor is checked at the pool and not discovered in a stack trace.
_SURNAME_M: tuple[str, ...] = (
    "кузнецов", "соколов", "лебедев", "ковалёв", "тарасов", "никитин",
    "зайцев", "богданов", "воронов", "фомин", "макаров", "андреев",
    "степанов", "громов", "миронов", "савельев", "щербаков", "белов",
    "поляков", "гордеев", "суханов", "малышев", "исаев", "гущин",
    "шилов", "кузьмин", "агафонов", "лыткин", "бурмистров", "шестаков",
    "кондратьев", "юдин",
)
_PATRONYMIC_M: tuple[str, ...] = (
    "иванович", "петрович", "сергеевич", "николаевич", "валентинович",
    "михайлович", "степанович", "львович", "павлович", "александрович",
)
_PATRONYMIC_F: tuple[str, ...] = (
    "ивановна", "петровна", "сергеевна", "николаевна", "валентиновна",
    "михайловна",
)
# «Отчество стягивается: палыч, михалыч, иваныч …» — fifteen distinct contracted
# forms in the call corpus, and template generation has none of them at all.
_PATRONYMIC_SHORT: dict[str, str] = {
    "павлович": "палыч", "иванович": "иваныч", "михайлович": "михалыч",
    "степанович": "степаныч", "александрович": "саныч",
    "николаевич": "николаич", "сергеевич": "сергеич",
}

# Real Russian mobile prefixes, so a number that reaches libphonenumber is
# dialable and the phone control is asking a fair question.
_MOBILE_PREFIX: tuple[str, ...] = (
    "916", "903", "926", "985", "999", "951", "967", "977", "905", "915",
)


# --- numbers said aloud ---------------------------------------------------
#
# Spelling is done HERE, from the integer, so the ground truth is what the
# builder PUT in the string. A written corpus cannot produce this shape at all —
# in text a digit is a digit — which is why the address defect this benchmark
# exists for was invisible to v2 by construction.
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
# Masculine, because «подъезд» is masculine and the mined shape puts the ordinal
# in front of it — 82 replies against 60 with the order reversed.
_ORDINAL_M: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой",
    "седьмой", "восьмой", "девятый",
)
# 22.9% of every «-десят» form in the call corpus arrives contracted. That is the
# NORM of this register, not a corner of it, and a generator emitting only the
# canonical forms measures a dialect nobody speaks on the phone.
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

    Four kinds and nothing else. The result is checked to be alphabetic and
    different — a mutation that silently returns its input turns the `sloppy`
    register into `chat` and the corpus would not notice.
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

    One, not several: a string with two errors in it is one no reader would
    repair either, so a case built that way measures nothing anybody has to get
    right.
    """
    words = phrase.split(" ")
    candidates = [index for index, word in enumerate(words) if len(word) >= 4]
    if not candidates:
        return phrase
    index = rng.choice(candidates)
    words[index] = _typo(words[index], rng)
    return " ".join(words)


# --- negatives ------------------------------------------------------------
#
# HALF THE PRECISION MEASUREMENT, and in this register they are not a formality:
# a number standing beside «кабинет» or «отделение» occurs 528 times in the call
# corpus and is the single largest false-positive source there. All ten families
# `schema.NEGATIVE_FAMILIES` names are represented below, because a generator
# left to its own taste writes the three it finds easy.
#
# The `spoken` column carries no digit and the `written` column carries no
# capital, because a negative must be LEGAL IN THE REGISTER it is dropped into
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
    _Neg("flat_as_home", "квартиру", "квартиру", "квартиру",
         "мы недавно сняли",
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
    _Neg("measure", "пять гектаров", "5 гектаров", "5 гектаров",
         "там участок",
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


def _digit_negatives() -> tuple[_Neg, ...]:
    """The negatives that carry a digit in their written form. For `voice_itn`.

    NOT because the case would otherwise hold no digit — in this family the
    address or the phone always supplies one, and `_register_problems` would be
    satisfied. Because a negative rendered in its SPOKEN form inside a `voice_itn`
    message is a line the register could not have produced: inverse text
    normalisation ran over the whole utterance, so «три четырнадцатый кабинет»
    standing in it is `voice_raw` text wearing another label, and the
    false-positive it probes for would be the wrong register's false positive.
    """
    return tuple(negative for negative in _NEGATIVES
                 if any(character.isdigit() for character in negative.written))


# --- filler ---------------------------------------------------------------
#
# NINE REPLIES IN TEN CARRY NO PERSONAL DATA AT ALL — a measured floor of 1.995%
# at the call corpus and 0.939% at the dispatch one. A long case whose every line
# holds a datum is not this register, and it inflates recall and precision at the
# same time. The filler is therefore REAL: hand-labelled «не адрес» replies from
# SOVA RuDevices, CC BY 4.0, which is the licence that lets them ship.
#
# The filter is stated because a filler line quietly holding an unlabelled datum
# is a leak the corpus cannot see: no digit, no Latin, no numeral run of two or
# more, none of the words a negative family is built on (those belong in
# `negatives` with a span, not loose in the prose), no name from the pools above,
# and no obscenity — the register is real, but reproducing it inside a
# customer-facing report buys nothing the measurement needs.
_OBSCENE: tuple[str, ...] = (
    "бля", "хуй", "хуё", "хуе", "пизд", "еба", "ёба", "ебы", "ёбы", "ебан",
    "ёбан", "нахуй", "похуй", "заеб", "мудак", "гандон", "срат", "говн",
    "педик", "пидор", "пидар", "шлюх", "трахн", "жоп", "нахер", "сук",
)
_NEG_WORDS: tuple[str, ...] = (
    "улиц", "квартир", "подъезд", "проезд", "корпус", "кабинет", "отделен",
    "этаж", "дом", "заказ", "гектар", "квадрат", "рубл", "филиал", "короб",
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
    "Давайте так и оформим.",
    "Буду ждать вашего ответа сегодня.",
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

    Fail-closed rather than falling back to authored prose. A corpus whose filler
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
            f"{_FILLER_PATH} is missing; the scope family draws its filler from "
            f"the hand-labelled RuDevices rows and will not invent it — see "
            f"CLAUDE.md for how to restore ~/.cache/pseudex-bench/")
    rows = json.loads(_FILLER_PATH.read_text(encoding="utf-8"))
    names = set(_GIVEN_M) | set(_GIVEN_F) | set(_SURNAME_M)
    kept: list[str] = []
    for row in rows:
        if row["label"] != "не адрес":
            continue
        text = str(row["text"])
        if any(character.isdigit() or character == "@"
               or ("a" <= character.lower() <= "z") for character in text):
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


def _long_filler(pool: tuple[str, ...]) -> tuple[str, ...]:
    """The long half of the pool, for the `deep` rung.

    `MIN_DEEP_CHARS` exists so that thirty two-word replies cannot pass for a
    long context. Padding a deep case with the median utterance satisfies the
    letter of that rule and breaks its intent — it reaches four thousand
    characters by stacking a hundred and thirty tiny turns, which is the same
    short context with more of it.
    """
    ordered = sorted(pool, key=len, reverse=True)
    return tuple(ordered[:max(40, len(ordered) // 2)])


# --- mined shape ids ------------------------------------------------------
#
# Every id this module can put in `Provenance.shape`, checked against the mined
# files at import AND against what `build` actually emitted. The field's whole
# purpose is that «the form came from real speech» be CHECKABLE — 1070 of v2's
# 1334 cases asserted it with nothing behind the assertion — so an id that has
# drifted out of the grammar, or one this inventory lists and nothing emits, must
# stop the build rather than ship as a claim.
#
# THE ID NAMES THE VALUE SHAPE. A case follows two mined patterns at once — the
# address is «<улица> <число прописью> <порядковое> подъезд», the sentence around
# it is `dispatch.reply:<АДРЕС>` — and the value shape is the one the detector
# actually meets.
_SHAPES: tuple[str, ...] = (
    # The anchor's fuller mention. All four are `gold_marker_stratum` entries.
    "dispatch.value:улица <улица> дом <число прописью>",
    "dispatch.value:<улица> <число прописью> <порядковое> подъезд",
    "dispatch.value:<улица> <число прописью> квартира <число прописью>",
    "dispatch.value:<улица> <число прописью> корпус <число прописью>",
    # The probe's bare mention. Present in BOTH the marker stratum (16) and the
    # random number sample (13), which is what lets the probes carry the random
    # stratum's weight honestly.
    "dispatch.value:<улица> <число прописью>",
    # The phone control. Dictation is how a number reaches a dispatcher at all.
    # `calls:num.phone_by_pairs` is deliberately NOT here: it is the number said
    # in numeral words, which carries no digit, and a phone with no digit is the
    # `spoken_id` family's question. Declaring an id this family cannot emit
    # would put an unverifiable claim back into the field that exists to abolish
    # them.
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
    cases used it. Without it a renderer could drift onto a pattern nobody
    declared and the claim would go out unverified — which is exactly the state
    v2 was in, only with a nicer field name. The reverse (a declared id nothing
    emitted) is REPORTED by `main` and not raised: some shapes are rare by
    construction and a build that failed because a seed did not draw one would be
    a brittle test of the RNG.
    """
    claimed = {case.provenance.shape for case in cases if case.provenance.shape}
    stray = sorted(claimed - set(_SHAPES))
    if stray:
        raise InvalidCase(f"cases claim undeclared shapes: {stray}")


# --- tools ----------------------------------------------------------------
#
# Two, and both take a personal value as an argument — which is what separates
# this from a NER corpus: the question is not «is this an address» but «does the
# car go to the door this conversation named». `comment` and `text` are passed
# and NOT judged, following τ²-bench's `compare_args`, because a benchmark that
# compares every argument fails a gateway for a model's choice of wording.
def _tool(name: str, description: str, properties: dict[str, str],
          required: tuple[str, ...]) -> dict[str, Any]:
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
    "create_ride", "Создать заказ такси на названный адрес подачи.",
    {"address": "Адрес подачи, как его назвал клиент.",
     "client": "Имя клиента, если названо.",
     "comment": "Примечание для водителя."},
    ("address",))
_TOOL_NOTIFY = _tool(
    "notify_client", "Позвонить клиенту по названному номеру.",
    {"phone": "Телефон клиента.", "text": "Что сказать."},
    ("phone",))

# Both tools are offered in every case. Which one the model reaches for is model
# behaviour, and the owner ruled model behaviour out of this benchmark; what is
# measured is what arrives in the argument when it does reach for one.
_TOOLS: tuple[dict[str, Any], ...] = (_TOOL_RIDE, _TOOL_NOTIFY)

_SYSTEM_DISPATCH = (
    "ты диспетчер службы такси. подтверждай адрес подачи и вызывай create_ride, "
    "когда адрес известен. для звонка клиенту вызывай notify_client."
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


_GLUE: frozenset[str] = frozenset(",.?!:;")


def _line(pieces: tuple[_Piece, ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Join pieces with single spaces and report where each tagged one landed.

    A piece opening with punctuation is GLUED to what came before it, so the
    `clean` register can write «Луговая, 7» without a stray space and without a
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


def _msg(key: str, role: str, pieces: tuple[_Piece, ...]) -> _Msg:
    text, marks = _line(pieces)
    return _Msg(key=key, role=role, text=text, marks=marks)


def _locate(messages: tuple[_Msg, ...], key: str,
            tag: str) -> tuple[int, int, int]:
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
    house: int
    flat: int         # 0 = not said
    entrance: int     # 0 = not said
    korpus: int       # 0 = not said
    marked: bool      # «улица … дом …» rather than a bare number
    city: str


def _draw_place(rng: random.Random, street: str, city: str) -> _Place:
    """One address, on a street the caller hands in so units cannot collide.

    THE STREET IS NOT DRAWN HERE. Twenty-five units share one tenant vault, and
    two units on the same street with the same house number would make the
    corpus's own claim ambiguous: a partial mention would have two owners, the
    single-candidate rule would correctly refuse to link, and the `within` arm
    would fail a gateway for being right. `_streets_for` allocates them without
    replacement instead.

    FOUR FULLER FORMS, all of them `gold_marker_stratum` shapes, because the
    thing that makes a mention «fuller» differs and the projection has to survive
    all of them: a street type plus «дом», an entrance, a flat, a building.
    """
    house = rng.choice((rng.randrange(1, 30), rng.randrange(1, 100),
                        rng.randrange(100, 200)))
    form = rng.randrange(4)
    return _Place(
        street=street, house=house,
        flat=rng.randrange(1, 200) if form == 2 else 0,
        entrance=rng.randrange(1, 10) if form == 1 else 0,
        korpus=rng.randrange(1, 6) if form == 3 else 0,
        marked=form == 0, city=city)


def _place_shape(place: _Place, form: str) -> str:
    """The mined value shape this rendering instantiates. One shape, exactly.

    Written from the same four rules as `_place_words`, so the id cannot drift
    from the string it describes. `_verify_shapes()` proves the other half — that
    each of these ids is still in the grammar file.
    """
    if form == "partial":
        return "dispatch.value:<улица> <число прописью>"
    if place.marked:
        return "dispatch.value:улица <улица> дом <число прописью>"
    if place.entrance:
        return "dispatch.value:<улица> <число прописью> <порядковое> подъезд"
    if place.flat:
        return "dispatch.value:<улица> <число прописью> квартира <число прописью>"
    return "dispatch.value:<улица> <число прописью> корпус <число прописью>"


def _place_words(place: _Place, form: str, house: str, tail: str) -> list[str]:
    """The word sequence of one rendering, numbers already spelled or written.

    Shared by every register, so the shape id, the canonical and the three
    surfaces cannot disagree about which parts were said. The literary renderer
    differs in PUNCTUATION and CASE, never in content.
    """
    if form == "partial":
        return [place.street, house]
    if place.marked:
        return ["улица", place.street, "дом", house]
    if place.entrance:
        return [place.street, house, tail, "подъезд"]
    if place.flat:
        return [place.street, house, "квартира", tail]
    return [place.street, house, "корпус", tail]


def _place_numbers(place: _Place, register: str,
                   rng: random.Random) -> tuple[str, str]:
    """(house, tail) rendered ONCE per unit and reused by both halves.

    RENDERED ONCE, AND THAT IS A CORRECTNESS REQUIREMENT rather than a saving.
    `_contract` fires on 23% of «-десят» forms — the measured rate — with its own
    draw, so calling it twice for one house number produces «пятьдесят» in the
    anchor and «песят» in the probe. The two mentions then no longer share a
    street-and-house surface at all, and both of this family's claims collapse in
    opposite directions: `across` gets its refusal for free because nothing could
    have linked those strings, and `within` demands a link nothing could make.
    A defect that makes the corpus agree with every gateway is the worst kind,
    because it looks like a result.

    The entrance takes an ORDINAL and the flat and the building take cardinals.
    Getting that wrong produces «пятый квартира», which is not Russian and would
    put the arm on a form no recognizer will ever meet.
    """
    spoken = register == "voice_raw"
    house = (_contract(_spell_int(place.house), rng) if spoken
             else str(place.house))
    if place.entrance:
        # The ordinal is a WORD in every register, which is not an oversight:
        # «пятый подъезд» is how the number is written down too, and the mined
        # shape puts the ordinal in front of the marker 82 times against 60.
        return house, _ORDINAL_M[place.entrance]
    if place.flat:
        return house, (_contract(_spell_int(place.flat), rng) if spoken
                       else str(place.flat))
    if place.korpus:
        return house, (_contract(_spell_int(place.korpus), rng) if spoken
                       else str(place.korpus))
    return house, ""


def _render_place(place: _Place, form: str, register: str, house: str,
                  tail: str) -> str:
    """The address as one string, in one register, in one of two forms.

    `full` is the marked mention the anchor makes. `partial` is the bare «<улица>
    <число>» that two thirds of the dispatch corpus uses, that a marker filter
    cannot see at all, and whose resolution against a fuller mention is the whole
    subject of this family.

    NO TYPO IS APPLIED TO AN ADDRESS HERE, and the `sloppy` register still means
    something: it lands on the PROSE, through `_prose`. A misspelt street name
    breaks linking for a reason that has nothing to do with the conversation
    boundary — that is what `bench/eval_noise_by_type.py` measures, on a ladder
    built for it — and putting it inside this family would make a boundary
    failure and a spelling failure the same number. What `sloppy` is asked here
    is the thing it can answer: a cue word may be misspelt, and «пасспорт» and
    «догвор» disabled the guards those words provide.
    """
    if register == "clean":
        return _render_place_clean(place, form)
    return " ".join(_place_words(place, form, house, tail))


def _render_place_clean(place: _Place, form: str) -> str:
    """The web-form rendering: capitals, commas, abbreviations.

    BUILT from the same four rules as `_place_words`, not post-processed from the
    spoken string. Capitalising and inserting commas by rewriting a finished text
    is the same class of mistake as searching it for offsets: the rule the
    rewrite encodes drifts from the rule that produced the words. The type word
    stays lower case, because that is how an address line is written — «улица
    Луговая», not «Улица Луговая».
    """
    street = place.street.capitalize()
    if form == "partial":
        return f"{street}, {place.house}"
    if place.marked:
        return f"улица {street}, д. {place.house}"
    if place.entrance:
        return f"{street}, {place.house}, подъезд {place.entrance}"
    if place.flat:
        return f"{street}, {place.house}, кв. {place.flat}"
    return f"{street}, {place.house}, корп. {place.korpus}"


def _place_canonical(place: _Place, form: str) -> str:
    """What a CRM would store OF WHAT WAS SAID. Never more than that.

    It IS the literary rendering of the same word list, and that is the point
    rather than a shortcut: a canonical assembled independently can claim a part
    the mention never carried, which is the ground truth scoring the gateway on
    information the conversation did not have. 162 of v2's 183 sloppy failures
    were one version of it.
    """
    return _render_place_clean(place, form)


def _render_city(place: _Place, register: str) -> str:
    """The settlement in front of the street, in the register that says it."""
    if register == "clean":
        return f"г. {place.city.capitalize()}"
    return place.city


# --- rendering a person ---------------------------------------------------

@dataclass(frozen=True)
class _Person:
    given: str
    surname: str
    patronymic: str
    female: bool


def _people_for(units: int, rng: random.Random) -> list[_Person]:
    """One person per unit, and NO GIVEN NAME OR SURNAME USED TWICE.

    DISTINCTNESS IS NOT TIDINESS HERE, it is the difference between measuring the
    gateway and measuring the corpus. A name links across the whole tenant when
    exactly ONE candidate matches it, and all fifty cases run against one store:
    two units sharing «Игорь» make each one's tool call reachable from the
    other's dialogue, which is a real `other_person` produced by this file rather
    than by the product — and after the numbers are printed there is no way to
    tell the two apart. The first version indexed the pools with `index %
    len(pool)`, a per-arm counter went round twice, and eighteen distinct names
    stood behind twenty-six gold items.

    Drawn WITHOUT REPLACEMENT and refused when the pool is too small, because a
    pool a corpus can exhaust is a permanent failure for whoever asks for one
    case more. Only the parts a mention can carry ALONE need to be unique — a
    given name and a surname; `_render_person` never emits a patronymic on its
    own, so nothing keys on one.
    """
    women = units // 3
    men = units - women
    if men > len(_GIVEN_M) or women > len(_GIVEN_F) or units > len(_SURNAME_M):
        raise InvalidCase(
            f"{units} units need {men} male and {women} female given names and "
            f"{units} surnames; the pools hold {len(_GIVEN_M)}, "
            f"{len(_GIVEN_F)} and {len(_SURNAME_M)}")
    given_m = rng.sample(_GIVEN_M, men)
    given_f = rng.sample(_GIVEN_F, women)
    surnames = rng.sample(_SURNAME_M, units)
    people: list[_Person] = []
    for index in range(units):
        female = index % 3 == 2 and bool(given_f)
        given = given_f.pop() if female else given_m.pop()
        patronymic = (rng.choice(_PATRONYMIC_F) if female
                      else rng.choice(_PATRONYMIC_M))
        if not female and rng.random() < 0.5:
            patronymic = _PATRONYMIC_SHORT.get(patronymic, patronymic)
        people.append(_Person(
            given=given,
            # The feminine surname is the masculine one plus «а», and the
            # masculine base is used once, so «Кузнецова» and «Кузнецов» never
            # both stand in this file — `to_nominative` collapses the pair, and
            # a corpus that mints both has written the ambiguity itself.
            surname=surnames[index] + ("а" if female else ""),
            patronymic=patronymic, female=female))
    return people


def _render_person(person: _Person, form: str, register: str,
                   rng: random.Random) -> tuple[str, str]:
    """(text, canonical) for one way of naming this person.

    THE CANONICAL IS BUILT FROM THE SAME PARTS. A reply that carried a given name
    and a patronymic must not have a surname demanded back — that is the ground
    truth scoring the gateway on information the conversation never had, and
    AgentPII-RU has paid for it once already.

    Measured on the call corpus: a surname alone 350, a given name alone 255,
    given + patronymic 109, surname + given + patronymic 23. A generator that
    always emits «Фамилия Имя Отчество» is testing one of six shapes.

    THE CANONICAL IS BUILT BEFORE THE TYPO, so a `sloppy` «сухнова» canonicalises
    to «Суханова». That is a claim about IDENTITY and not about what must come
    back: the expected call passes `value`, the string as written, so nothing
    demands a repaired name from the gateway. What the corrected form buys is
    that `distinct_values` counts one person rather than two — the count printed
    beside every rate to stop a repeated value looking like a fresh observation.
    """
    if form == "given":
        words = (person.given,)
    elif form == "given_patronymic":
        words = (person.given, person.patronymic)
    elif form == "surname":
        words = (person.surname,)
    elif form == "full":
        words = (person.surname, person.given, person.patronymic)
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

def _draw_phone(rng: random.Random) -> str:
    """Eleven digits on a real Russian mobile prefix, no leading zero in a group.

    Real prefixes because libphonenumber is the first recognizer that sees it,
    and no leading zeros because a group like «05» is said «ноль пять» and the
    spelling table has one rule per group, not two.
    """
    return ("8" + rng.choice(_MOBILE_PREFIX) + str(rng.randrange(100, 1000))
            + str(rng.randrange(10, 100)) + str(rng.randrange(10, 100)))


def _render_phone(digits: str, form: str) -> str:
    """One of the shapes the SAME number arrives in.

    «+7 999…» and «8 999…» collapsing to one vault key is documented, deliberate
    gateway behaviour, which is what makes the phone a fair control: the equality
    it is asked about is one the product has promised to preserve, and it is
    promised at TENANT scope rather than at conversation scope.
    """
    body = digits[1:]
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
# From the mined dispatch lexicon, weighted as it was counted. 101 of 154 address
# replies begin with NO introduction at all (65.6%), and the single commonest
# reply shape in the corpus is the address ALONE — 59 of 154. A generator that
# always says «здравствуйте, мой адрес» writes the form a cue-word gate finds
# easiest and the corpus produced twenty-six times in a hundred and fifty-four.
_OPENERS_SPOKEN: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("а", 4), ("алло здравствуйте", 3),
    ("доброе утро", 2), ("здравствуйте а", 2), ("аа", 2),
    ("а здравствуйте", 2), ("девушка", 1), ("алло", 1), ("так", 1), ("ээ", 1),
)
_OPENERS_TYPED: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("привет", 12), ("добрый день", 8),
    ("а", 4),
)
_OPENERS_CLEAN: tuple[str, ...] = ("Добрый день.", "Здравствуйте.", "")

# `context_before_the_value.immediately_before_the_value` — 95 of 169 mentions
# have nothing in front of them at all, and what does appear is a verb of motion
# or a bare preposition.
_INTENT_SPOKEN: tuple[tuple[str, int], ...] = (
    ("", 95), ("поедем", 6), ("поеду", 4), ("на", 9), ("поедем на", 2),
    ("я нахожусь на", 2), ("едем на", 2), ("по", 1),
)
_INTENT_CLEAN: tuple[str, ...] = ("Адрес подачи:", "Подача:")

# `tails_after_the_address.verbatim_tails`, minus every one carrying a numeral —
# an unclaimed numeral run of four is what `audit_unlabelled` refuses, and in
# this register it is the shape of a dictated identifier.
_TAILS_SPOKEN: tuple[str, ...] = (
    "частный дом", "магазин магнит", "столовая", "красный дом",
    "новостройка со стороны стройки", "заправка башнефть",
    "магазин продукты служебный вход", "поедем по городу",
    "центральный вход", "во дворы",
)
_TAILS_CLEAN: tuple[str, ...] = (
    "Частный дом.", "Вход со двора.", "Домофон не работает.",
)

# `calls:disc.dictation` — «записывай», «пишите», «записал». The words a number
# arrives behind, and the only ones this family needs: a control arm is a value
# said a second time in another conversation.
_DICTATION_TYPED: tuple[str, ...] = (
    "запишите", "записывайте", "пишите", "мой номер", "телефон",
)
_DICTATION_CLEAN: tuple[str, ...] = (
    "Мой номер:", "Телефон для связи:",
)


def _prose(text: str, register: str, rng: random.Random) -> str:
    """A writing error in the words AROUND the value, for the `sloppy` register.

    Applied to prose and NOT to values, which is the opposite of the obvious
    choice and is what makes `sloppy` measurable in this family at all — see
    `_render_place`. It is also the half of the register that matters most here:
    a cue word may be misspelt, and «пасспорт» and «догвор» disabled the guards
    that word provides.
    """
    if register != "sloppy" or not text or rng.random() > 0.5:
        return text
    return _typo_phrase(text, rng)


def _weighted(table: tuple[tuple[str, int], ...], rng: random.Random) -> str:
    population = [text for text, _ in table]
    weights = [count for _, count in table]
    return rng.choices(population, weights=weights, k=1)[0]


def _opener(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_OPENERS_CLEAN)
    if register in ("voice_raw", "voice_itn"):
        return _weighted(_OPENERS_SPOKEN, rng)
    return _prose(_weighted(_OPENERS_TYPED, rng), register, rng)


def _intent(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_INTENT_CLEAN)
    return _prose(_weighted(_INTENT_SPOKEN, rng), register, rng)


def _tail(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_TAILS_CLEAN)
    return _prose(rng.choice(_TAILS_SPOKEN), register, rng)


def _dictation(register: str, rng: random.Random) -> str:
    if register == "clean":
        return rng.choice(_DICTATION_CLEAN)
    return _prose(rng.choice(_DICTATION_TYPED), register, rng)


def _stop(register: str) -> str:
    """The full stop that closes a literary sentence, and nothing elsewhere."""
    return "." if register == "clean" else ""


def _negative_clause(negative: _Neg, register: str, tag: str,
                     rng: random.Random) -> tuple[_Piece, ...]:
    """One negative with the sentence that carries it, as pieces.

    The carrier is prose and is NOT part of the span: a gateway that masks «нам
    надо в» has made no error anybody can name, while one that masks «три
    четырнадцатый кабинет» has broken the ride.
    """
    text = _negative_text(negative, register)
    if register == "clean":
        return (_Piece("", negative.carrier.capitalize()), _Piece(tag, text),
                _Piece("", "."))
    # The NEGATIVE ITSELF is never mistyped. «три четырнадцатый кабинет» with a
    # letter dropped is a different claim — that the gateway must leave a
    # misspelt cabinet number alone — and it belongs to the noise ladder, not to
    # a family about the conversation boundary.
    return (_Piece("", _prose(negative.carrier, register, rng)),
            _Piece(tag, text))


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


# `MIN_DEEP_CHARS` is 4000 and this is the margin the padder aims at. A case that
# lands exactly on the floor becomes invalid the moment a register transform
# shortens one word, and the failure would read as a schema bug rather than as a
# padding bug.
_MIN_DEEP_CHARS_MARGIN: int = 4_400


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
    return (_msg(f"f{index}u", "user", (_Piece("", said),)),
            _msg(f"f{index}a", "assistant", (_Piece("", ack),)))


def _pad(opening: tuple[_Msg, ...], closing: tuple[_Msg, ...], context: str,
         register: str, rng: random.Random,
         pool: tuple[str, ...]) -> tuple[_Msg, ...]:
    """Insert filler BETWEEN the mention and the end of the conversation.

    Between, not before: what this family stretches is the distance from the
    value to the moment the tool is called, and filler stacked in front of the
    value lengthens the transcript without lengthening anything that matters.
    """
    if context in ("solo", "short"):
        pairs = 0 if context == "solo" else rng.randrange(1, 3)
    elif context == "long":
        pairs = rng.randrange(4, 13)
    else:
        pairs = 15
        pool = _long_filler(pool)
    middle: list[_Msg] = []
    index = 0
    while True:
        total = len(opening) + len(middle) + len(closing)
        characters = sum(len(message.text) for message
                         in tuple(opening) + tuple(middle) + tuple(closing))
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
    return tuple(opening) + tuple(middle) + tuple(closing)


def _finish(case_id: str, family: str, register: str, context: str,
            messages: tuple[_Msg, ...], items: tuple[_ItemSpec, ...],
            negatives: tuple[_NegSpec, ...],
            links: tuple[LinkExpectation, ...],
            calls: tuple[ExpectedCall, ...], final: FinalAnswer,
            provenance: Provenance, cluster: str, conversation_id: str,
            preceded_by: str, note: str) -> Case:
    """Resolve every span from the marks the builder recorded, then REFUSE or return.

    `validate` runs HERE rather than in `build`, so a broken case names itself at
    the moment it was constructed instead of arriving inside a list of fifty.
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
        family=family,
        register=register,
        context=context,
        provenance=provenance,
        cluster=cluster,
        conversation_id=conversation_id,
        messages=tuple(
            Message(role=message.role, content=message.text, source=None,
                    name="")
            for message in messages),
        tools=_TOOLS,
        pii=tuple(pii),
        negatives=tuple(negative_rows),
        links=links,
        calls=calls,
        final=final,
        preceded_by=preceded_by,
        annotators=0,
        adjudicated=False,
        note=note,
    )
    problems = validate(case)
    if problems:
        raise InvalidCase("\n".join(problems))
    return case


def _provenance(shape: str, corpus: str, selection: str,
                weight: float) -> Provenance:
    """`licence` is the licence of the TEXT THIS CASE CARRIES, not of the mining.

    A recombined case's sentence is ours — the mined artefact it follows is a
    PATTERN, and a pattern is not the expression a licence covers. `corpus` still
    names where the form was observed, so the two fields say two true things
    rather than one blurred one.
    """
    return Provenance(kind="recombined", corpus=corpus, key="", shape=shape,
                      selection=selection, weight=weight, licence="authored")


# --- the units ------------------------------------------------------------

@dataclass(frozen=True)
class _Unit:
    arm: str
    index: int
    seed: int
    register_a: str
    register_b: str
    context_a: str
    context_b: str
    # The street and the person are allocated in `_plan`, without replacement
    # across the whole family, and handed in rather than drawn per case. Fifty
    # cases share one tenant vault, so a value repeated between two units is an
    # ambiguity this file wrote and then measured the gateway on.
    street: str
    person: _Person
    city_a: str
    city_b: str


def _value_rng(unit: _Unit) -> random.Random:
    """The RNG that picks VALUES. Shared by both halves of the pair.

    A pair is ONE value and TWO occurrences, which is why the two cases also
    share a `cluster`: an interval computed over occurrences rather than over
    clusters is narrower than the truth, and narrower in our favour.
    """
    return random.Random(f"v3:{FAMILY}:{unit.seed}:{unit.arm}:value{unit.index}")


def _surface_rng(unit: _Unit, half: str) -> random.Random:
    """The RNG that picks SURFACE. Keyed by the half, so the two differ."""
    return random.Random(
        f"v3:{FAMILY}:{unit.seed}:{unit.arm}:{half}{unit.index}")


def _system() -> _Msg:
    return _msg("sys", "system", (_Piece("", _SYSTEM_DISPATCH),))


def _conversation(unit: _Unit, half: str) -> str:
    """The conversation identity this half is scored under. THE WHOLE CLAIM.

    `within` HANDS BOTH HALVES THE SAME ID and every other arm hands them
    different ones. That single line is what each arm is asking; get it wrong and
    the family still builds, still validates, and measures the opposite of what
    it says — the `within` pair would be two conversations demanding a link the
    product correctly refuses, and a correct gateway would score zero on it.

    THE CONTROL ARM DERIVES ITS IDENTITY AND THE ADDRESS ARMS ARE HANDED ONE, and
    the split is a decision rather than variety for its own sake. The address
    arms' whole claim is about which conversation a mention belongs to, and a
    derived identity would make the corpus's requirement depend on a hashing rule
    the harness owns — `conversation_key` reads the first two messages, and two
    cases sharing a system prompt and an opener would silently become one
    conversation. The phone control claims something TENANT-wide, which is true
    however the conversation is identified, so it is the one place the derived
    path can be exercised without putting a claim at risk. `validate_corpus`
    demands the corpus hold both kinds and this family holds both by itself.
    """
    if unit.arm == "phone":
        return ""
    if unit.arm == "within":
        return f"sc-within-{unit.index:02d}"
    return f"sc-{unit.arm}-{unit.index:02d}-{half}"


def _address_pieces(register: str, opener: str, intent: str, city: str,
                    value: str, tag: str) -> tuple[_Piece, ...]:
    """The opening user turn of an address case, as pieces.

    The city rides as its own tagged piece so it can be an `optional` item: a
    settlement identifies nobody, so masking it is not an error and missing it is
    not a leak, and folding it into the required span would punish a gateway for
    correctly leaving it alone.
    """
    city_pieces: tuple[_Piece, ...] = ()
    if city:
        city_pieces = (_Piece("c1", city),
                       _Piece("", "," if register == "clean" else ""))
    return (_Piece("", opener), _Piece("", intent), *city_pieces,
            _Piece(tag, value), _Piece("", _stop(register)))


def _ride_call(address: str, client: str, address_item: str, client_item: str,
               after: int) -> ExpectedCall:
    """The reference call. `comment` is passed and not judged, on purpose."""
    arguments = {"address": address, "comment": "телефон"}
    judged = ["address"]
    items = [address_item]
    if client:
        arguments["client"] = client
        judged.append("client")
        items.append(client_item)
    return ExpectedCall(name="create_ride", arguments=arguments,
                        judged_args=tuple(judged), pii_items=tuple(items),
                        after_msg=after)


def _notify_call(phone: str, item_id: str, after: int) -> ExpectedCall:
    return ExpectedCall(
        name="notify_client",
        arguments={"phone": phone, "text": "перезвонить по заказу"},
        judged_args=("phone",), pii_items=(item_id,), after_msg=after)


def _root_case(seed: int) -> Case:
    """The tenant's earlier conversation, and the root of the dependency tree.

    NOT A `scope` CASE, and the docstring at the top of this module argues it at
    length: the schema refuses a `scope` case with no predecessor, a tree needs a
    root, and a root carrying no scope claim is by definition not a scope case.
    What it IS is one customer stating personal data that one call consumes,
    which is `transfer`.

    It earns its place beyond the bookkeeping. It puts a third customer's
    address, phone and name into the vault BEFORE any pair runs, so no arm below
    is measured against an empty store — and an empty store is the one state in
    which a linking bug cannot show itself at all.
    """
    rng = random.Random(f"v3:{FAMILY}:{seed}:root")
    person = _Person(given="геннадий", surname="орехов",
                     patronymic="аркадьевич", female=False)
    place = _Place(street="привокзальная", house=12, flat=0, entrance=0,
                   korpus=0, marked=True, city="иркутск")
    digits = "89031457788"
    register = "chat"
    house, tail = _place_numbers(place, register, rng)
    address = _render_place(place, "full", register, house, tail)
    name, name_canonical = _render_person(person, "given_patronymic", register,
                                          rng)
    phone = _render_phone(digits, "eight_spaced")
    negative = _NEGATIVES[8]
    opening = (
        _system(),
        _msg("first", "user",
             (_Piece("", "здравствуйте"), _Piece("", "это"),
              _Piece("n1", name), _Piece("", "адрес"),
              _Piece("a1", address), _Piece("", "телефон"),
              _Piece("p1", phone))),
    )
    closing = (
        _msg("last", "user",
             _negative_clause(negative, register, "g1", rng)),
    )
    messages = _pad(opening, closing, "short", register, rng, _filler_pool())
    items = (
        _ItemSpec("n1", "first", "n1", "NAME", name, name_canonical,
                  "root.person", "required", "pool", False, "client"),
        _ItemSpec("a1", "first", "a1", "LOC", address,
                  _place_canonical(place, "full"), "root.place", "required",
                  "pool", False, "address"),
        _ItemSpec("p1", "first", "p1", "PHONE", phone, _phone_canonical(digits),
                  "root.phone", "required", "template", False, ""),
    )
    return _finish(
        case_id=ROOT_ID, family=ROOT_FAMILY, register=register,
        context="short", messages=messages, items=items,
        negatives=(_NegSpec("last", "g1", negative.family, negative.why),),
        links=(), calls=(_ride_call(address, name, "a1", "n1",
                                    len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("dispatch.value:улица <улица> дом <число прописью>",
                               "speech_rudevices", "marker", 1.0),
        cluster="scope:root", conversation_id="sc-tenant-000",
        preceded_by="",
        note="корень дерева зависимостей семейства: разговор, который лежит в "
             "вольте раньше всех пар, и единственный случай модуля без "
             "притязания на границу разговора",
    )


def _address_pair(unit: _Unit, pool: tuple[str, ...],
                  kind: str) -> list[Case]:
    """An anchor and a probe. `kind` is `within`, `across` or `full`.

    THE ANCHOR IS THE SAME CASE IN ALL THREE and that is what makes the family a
    measurement rather than three unrelated tests: one conversation, one fuller
    mention, one tool call. What varies is the SECOND case — whose conversation
    it belongs to, and how much of the address it repeats — so a difference in
    the result is a difference in the boundary and in nothing else.

      within  the probe is the SAME conversation and says only «<улица>
              <число>». The gateway must reach back through the vault, not
              through the transcript: the probe's own messages never carried the
              flat, the entrance or the city, so a gateway that links inside one
              request and forgets between them fails here and passes everything
              else in this file.
      across  the probe is a DIFFERENT conversation, in a different city, and
              says exactly the same words. Linking hands one customer's building
              to another customer's dialogue.
      full    the probe is a DIFFERENT conversation and repeats the WHOLE
              address, character for character. A full address keeps the plain
              key, so this must link — and it is the arm that fails a gateway
              which «fixed» `across` by scoping every address to its
              conversation.
    """
    values = _value_rng(unit)
    place = _draw_place(values, unit.street, unit.city_a)
    person = unit.person

    rng_a = _surface_rng(unit, "a")
    rng_b = _surface_rng(unit, "b")
    # ONE rendering of the house number for the whole unit. `_place_numbers`
    # says at length why calling it per half is a defect that makes the corpus
    # agree with every gateway.
    house, tail = _place_numbers(place, unit.register_a, values)
    full_a = _render_place(place, "full", unit.register_a, house, tail)
    name_a, name_canonical = _render_person(
        person, values.choice(("given_patronymic", "full", "given",
                               "surname")), unit.register_a, rng_a)

    # BOTH HALVES OF AN ADDRESS UNIT ARE IN ONE REGISTER, forced in `_plan`, and
    # the reason is that a mismatch would make both claims unmeasurable in
    # opposite directions. «улица Петрова, д. 147» and «петрова сто сорок семь»
    # do not share a street-and-house key at all, so the `across` unit would get
    # its refusal for free — the gateway could not have linked them if it wanted
    # to, and an arm whose negative requirement is satisfied by construction is a
    # rubber stamp. The `within` unit would fail the other way: it demands a link
    # the gateway is now unable to make, so a correct implementation scores zero.
    probe_register = unit.register_b
    if kind == "full":
        # `full` reuses the anchor's string rather than rendering a second one.
        # Rendering twice would be equivalent today and is a hostage to the next
        # change: the claim is that ONE PLACE gets one substitute across
        # conversations, and the moment any per-render draw is reintroduced the
        # two halves become two strings and the arm quietly starts asking about
        # canonicalisation instead.
        probe_value = full_a
        probe_place_form = "full"
    else:
        probe_value = _render_place(place, "partial", probe_register, house,
                                    tail)
        probe_place_form = "partial"

    anchor = _address_anchor(unit, pool, place, full_a, name_a, name_canonical,
                             rng_a, kind)
    probe = _address_probe(unit, pool, place, probe_value, probe_place_form,
                           probe_register, full_a, rng_b, kind)
    return [anchor, probe]


def _address_anchor(unit: _Unit, pool: tuple[str, ...], place: _Place,
                    value: str, name: str, name_canonical: str,
                    rng: random.Random, kind: str) -> Case:
    """The conversation that says the address in full, and calls the tool on it."""
    register = unit.register_a
    context = unit.context_a
    city = _render_city(place, register)
    negative = rng.choice(_NEGATIVES if register != "voice_itn"
                          else _digit_negatives())
    opener = _opener(register, rng)
    intent = _intent(register, rng)
    name_lead = "это" if register != "clean" else "Клиент:"
    opening = (
        _system(),
        _msg("first", "user",
             (*_address_pieces(register, opener, intent, city, value, "a1"),
              _Piece("", name_lead), _Piece("n1", name),
              _Piece("", _stop(register)))),
    )
    closing = (
        _msg("last", "user",
             (*_negative_clause(negative, register, "g1", rng),
              _Piece("", _tail(register, rng)),
              _Piece("", _stop(register)))),
    )
    if context == "solo":
        messages = (
            _system(),
            _msg("first", "user",
                 (*_address_pieces(register, opener, intent, city, value, "a1"),
                  _Piece("", name_lead), _Piece("n1", name),
                  _Piece("", _stop(register)),
                  *_negative_clause(negative, register, "g1", rng))),
        )
        negative_key = "first"
    else:
        messages = _pad(opening, closing, context, register, rng, pool)
        negative_key = "last"
    items = [
        _ItemSpec("a1", "first", "a1", "LOC", value,
                  _place_canonical(place, "full"), f"{unit.arm}{unit.index:02d}.place",
                  "required", "pool", register == "voice_raw", "address"),
        _ItemSpec("n1", "first", "n1", "NAME", name, name_canonical,
                  f"{unit.arm}{unit.index:02d}.person", "required", "pool", False, "client"),
    ]
    if city:
        items.append(_ItemSpec(
            "c1", "first", "c1", "LOC", city, place.city.capitalize(),
            f"{unit.arm}{unit.index:02d}.city", "optional", "pool",
            register == "voice_raw", ""))
    return _finish(
        case_id=f"sc-{kind}-{unit.index:02d}-a", family=FAMILY,
        register=register, context=context, messages=messages,
        items=tuple(items),
        negatives=(_NegSpec(negative_key, "g1", negative.family, negative.why),),
        links=(),
        calls=(_ride_call(value, name, "a1", "n1", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance(_place_shape(place, "full"), "speech_rudevices",
                               "marker", 1.0),
        cluster=f"scope:{kind}:{unit.index:02d}",
        conversation_id=_conversation(unit, "a"),
        preceded_by=ROOT_ID,
        note=f"якорь пары «{kind}»: полное упоминание адреса в своём разговоре, "
             f"на которое ссылается вторая половина",
    )


def _address_probe(unit: _Unit, pool: tuple[str, ...], place: _Place,
                   value: str, form: str, register: str, anchor_value: str,
                   rng: random.Random, kind: str) -> Case:
    """The second conversation. The claim lives here and nowhere else."""
    context = unit.context_b
    negative = rng.choice(_NEGATIVES if register != "voice_itn"
                          else _digit_negatives())
    opener = _opener(register, rng)
    intent = _intent(register, rng)
    # The probe NEVER says the city. A mention that names its settlement is not a
    # short mention — it is the whole address or a different place — and the
    # subject of this family is what happens to the short one.
    opening = (
        _system(),
        _msg("first", "user",
             _address_pieces(register, opener, intent, "", value, "b1")),
    )
    closing = (
        _msg("last", "user",
             (*_negative_clause(negative, register, "g1", rng),
              _Piece("", _tail(register, rng)),
              _Piece("", _stop(register)))),
    )
    if context == "solo":
        messages = (
            _system(),
            _msg("first", "user",
                 (*_address_pieces(register, opener, intent, "", value, "b1"),
                  *_negative_clause(negative, register, "g1", rng))),
        )
        negative_key = "first"
    else:
        messages = _pad(opening, closing, context, register, rng, pool)
        negative_key = "last"

    if kind == "within":
        link_kind = "same"
        why = ("частичное упоминание в ТОМ ЖЕ разговоре, где раньше прозвучал "
               "полный адрес: обязано разрешиться в ту же сущность")
        note = ("вторая реплика того же разговора называет только улицу и дом; "
                "полный адрес звучал в первой половине пары и в этом случае его "
                "нет — связать можно только через вольт")
        forbidden: tuple[str, ...] = ()
    elif kind == "across":
        link_kind = "different"
        why = ("то же частичное упоминание, но ДРУГОЙ разговор и другой город: "
               "связать значит отдать адрес одного клиента в диалог другого")
        # The city is named in the NOTE and never in the text, and that is the
        # conservative reading rather than an omission. The probe cannot say its
        # settlement — a mention that names one is not a partial mention — and
        # putting it in a distant sentence instead would ask a detection question
        # (does the address span swallow it) inside a family about the
        # conversation boundary. So the fact the requirement rests on is
        # recorded where a human reading the case can find it.
        note = (f"та же улица и тот же дом, что у якоря, но разговор другой и "
                f"клиент из другого города ({unit.city_b} против "
                f"{unit.city_a}); связывание здесь отправляет машину к чужому "
                f"подъезду")
        # THE SECOND DETECTOR FOR ONE FAILURE, and it needs no cooperation from
        # the scorer. An over-link is supposed to surface on the round trip as
        # `other_person`, but that name is only reachable if the scorer feeds the
        # chain's SURFACE values into `other_values` alongside the canonicals —
        # `classify_break` compares against whatever it was handed. Forbidding
        # the anchor's real address in the final reply catches the same
        # disclosure through machinery that takes no such cooperation. Deduped
        # because in the literary register the surface and the canonical are one
        # string, and a forbidden value listed twice reads as two findings.
        forbidden = tuple(dict.fromkeys(
            (anchor_value, _place_canonical(place, "full"))))
    else:
        link_kind = "same"
        why = ("ПОЛНЫЙ адрес повторён в другом разговоре: полный адрес держит "
               "плоский ключ, одно место — одна подмена, навсегда")
        note = ("контрольное плечо: шлюз, замкнувший на разговор ВСЕ адреса, "
                "проходит «через границу» и падает здесь")
        forbidden = ()

    items = (
        _ItemSpec("b1", "first", "b1", "LOC", value,
                  _place_canonical(place, form),
                  f"{unit.arm}{unit.index:02d}.probe", "required", "pool",
                  register == "voice_raw", "address"),
    )
    return _finish(
        case_id=f"sc-{kind}-{unit.index:02d}-b", family=FAMILY,
        register=register, context=context, messages=messages, items=items,
        negatives=(_NegSpec(negative_key, "g1", negative.family, negative.why),),
        links=(LinkExpectation("b1", "a1", link_kind,
                               f"sc-{kind}-{unit.index:02d}-a", why),),
        calls=(_ride_call(value, "", "b1", "", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=forbidden,
                          answer=""),
        # A bare «<улица> <число>» is the RANDOM stratum of the dispatch
        # annotation — 250 replies read out of 4805 — and its weight is the
        # inverse sampling fraction. Carried rather than dropped because the
        # marker stratum, the one selected by the words the detector reads, would
        # otherwise take nineteen times the weight it has earned.
        provenance=_provenance(
            _place_shape(place, form), "speech_rudevices",
            "marker" if form == "full" else "random",
            1.0 if form == "full" else 19.22),
        cluster=f"scope:{kind}:{unit.index:02d}",
        conversation_id=_conversation(unit, "b"),
        preceded_by=f"sc-{kind}-{unit.index:02d}-a",
        note=note,
    )


def _phone_pair(unit: _Unit, pool: tuple[str, ...]) -> list[Case]:
    """THE CONTROL. One number, two conversations, and it must stay one identity.

    WITHOUT THIS ARM THE FAMILY MEASURES NOTHING. A gateway that has stopped
    linking altogether — the cache disabled, the vault lookup broken, a
    conversation scope applied to every type — satisfies every `across`
    requirement in this file, because «did not link» and «correctly refused to
    link» produce the same observation. Here they do not: a phone canonicalises
    across the whole tenant by design, «+7 999…» and «8 999…» collapsing to one
    key so the model sees a stable identity across turns, so a gateway that
    stopped linking fails here and only here.

    The two halves say the number in DIFFERENT shapes, which is what makes the
    claim about canonicalisation rather than about string equality. `same_value`
    compares a phone on its last ten digits — the country code is the one thing a
    phone may legitimately change — so the round trip stays `ok` whichever
    surface the vault stored first, and the LINK axis carries the measurement
    alone.
    """
    values = _value_rng(unit)
    digits = _draw_phone(values)
    person = unit.person
    rng_a = _surface_rng(unit, "a")
    rng_b = _surface_rng(unit, "b")
    form_a, form_b = values.sample(
        ["plus_spaced", "eight_spaced", "flat", "plus_flat"], 2)
    phone_a = _render_phone(digits, form_a)
    phone_b = _render_phone(digits, form_b)
    name_a, name_canonical = _render_person(person, "given_patronymic",
                                            unit.register_a, rng_a)

    anchor = _phone_case(
        unit, pool, "a", unit.register_a, unit.context_a, phone_a, digits,
        name_a, name_canonical, rng_a, ())
    probe = _phone_case(
        unit, pool, "b", unit.register_b, unit.context_b, phone_b, digits,
        "", "", rng_b,
        (LinkExpectation(
            "p1", "p1", "same", f"sc-phone-{unit.index:02d}-a",
            "один номер в двух написаниях и в двух разговорах: каноникализация "
            "телефона обещана на весь тенант, а не на разговор"),))
    return [anchor, probe]


def _phone_case(unit: _Unit, pool: tuple[str, ...], half: str, register: str,
                context: str, phone: str, digits: str, name: str,
                name_canonical: str, rng: random.Random,
                links: tuple[LinkExpectation, ...]) -> Case:
    """One half of the phone control.

    The name rides on the anchor with NO tool parameter and no link claim. It is
    there for two reasons and neither is decoration: a support call that names
    nobody is not a register anybody speaks, and this is the only place in the
    family where a NAME reaches the corpus under the `census` selection — a type
    whose every speech-derived instance came from the `marker` stratum has been
    measured on utterances chosen by the words the detector reads.
    """
    negative = rng.choice(_digit_negatives())
    opener = _opener(register, rng)
    lead = _dictation(register, rng)
    name_pieces: tuple[_Piece, ...] = ()
    if name:
        name_pieces = (_Piece("", "это" if register != "clean" else "Клиент:"),
                       _Piece("n1", name), _Piece("", _stop(register)))
    head = (_Piece("", opener), *name_pieces, _Piece("", lead),
            _Piece("p1", phone), _Piece("", _stop(register)))
    if context == "solo":
        messages = (
            _system(),
            _msg("first", "user",
                 (*head, *_negative_clause(negative, register, "g1", rng))),
        )
        negative_key = "first"
    else:
        messages = _pad(
            (_system(), _msg("first", "user", head)),
            (_msg("last", "user", _negative_clause(negative, register, "g1", rng)),),
            context, register, rng, pool)
        negative_key = "last"
    items = [
        _ItemSpec("p1", "first", "p1", "PHONE", phone, _phone_canonical(digits),
                  f"{unit.arm}{unit.index:02d}.phone.{half}", "required", "template", False,
                  "phone"),
    ]
    if name:
        items.append(_ItemSpec(
            "n1", "first", "n1", "NAME", name, name_canonical,
            f"{unit.arm}{unit.index:02d}.person", "required", "pool", False, ""))
    return _finish(
        case_id=f"sc-phone-{unit.index:02d}-{half}", family=FAMILY,
        register=register, context=context, messages=messages,
        items=tuple(items),
        negatives=(_NegSpec(negative_key, "g1", negative.family, negative.why),),
        links=links,
        calls=(_notify_call(phone, "p1", len(messages) - 1),),
        final=FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        provenance=_provenance("calls:disc.dictation", "speech_calls",
                               "census", 1.0),
        cluster=f"scope:phone:{unit.index:02d}",
        conversation_id=_conversation(unit, half),
        preceded_by=(ROOT_ID if half == "a"
                     else f"sc-phone-{unit.index:02d}-a"),
        note=("контрольное плечо, первая половина: номер названный в одном "
              "разговоре" if half == "a" else
              "контрольное плечо: тот же номер в другом разговоре обязан "
              "СВЯЗАТЬСЯ — иначе «не связал» неотличимо от «сломан»"),
    )


# --- the plan -------------------------------------------------------------
#
# ARM, UNITS, and the constraints are facts about the arms rather than
# preferences. The phone arm cannot be `voice_raw`: the schema refuses a digit
# there, and a number spelled out is the `spoken_id` family's question. The
# `full` arm renders both halves alike, so the two registers must agree.
#
# ORDERED MOST-CONSTRAINED FIRST, because the allocator drains one global quota
# and a free arm can always absorb what a constrained one could not take. Written
# the other way round it deadlocks rather than drifting, which is the better of
# the two failures and is how this ordering was found: `phone` refuses
# `voice_raw` and `voice_raw` is 28 of the 50 cases, so `within` and `across`
# had eaten every digit-carrying register before the control arm was reached.
_ARM_PLAN: tuple[tuple[str, int], ...] = (
    ("full", 4),
    ("phone", 5),
    ("across", 9),
    ("within", 7),
)

_ARM_REGISTERS: dict[str, tuple[str, ...]] = {
    # An address unit spends ONE register on TWO cases; the phone unit spends two
    # registers on two cases, which is its whole point. `full` additionally
    # refuses `sloppy`: its two halves carry the identical string, and two
    # different customers typing the identical typo is not a thing that happens.
    "within": ("voice_raw", "voice_itn", "chat", "sloppy"),
    "across": ("voice_raw", "voice_itn", "chat", "sloppy"),
    "full": ("voice_raw", "voice_itn", "chat"),
    "phone": ("voice_itn", "chat", "sloppy", "clean"),
}

# TWO MIXES, ALLOCATED SEPARATELY, because the two kinds of unit spend registers
# in different units of account: an address unit is one register over two cases,
# a phone unit is two registers over two cases. One shared quota was the first
# version and it deadlocks on parity — the phone arm leaves `clean` at one, no
# address unit can spend an odd case, and the allocator raises on a draw that
# happened to go that way. Two exact mixes cannot.
#
# The address mix is in UNITS and the phone mix is in CASES. Their sum is the
# published register split, and `main` prints the split that was actually built
# rather than the one intended — v2 described a mix in a design document and
# shipped the opposite.
#
#     voice_raw 28   voice_itn 8   chat 9   sloppy 3   clean 2   = 50
#     speech 36/50 = 72% (floor 50%)      clean 2/50 = 4% (cap 5%)
#
# `clean` lives entirely on the phone arm: it is two cases, an address unit
# would cost both of them, and the literary register earns its budget better by
# proving the boundary survives a web form than by spending it on one pair.
_ADDRESS_UNIT_MIX: tuple[tuple[str, int], ...] = (
    ("voice_raw", 14), ("voice_itn", 2), ("chat", 3), ("sloppy", 1),
)
_PHONE_CASE_MIX: tuple[tuple[str, int], ...] = (
    ("voice_itn", 4), ("chat", 3), ("sloppy", 1), ("clean", 2),
)
_CONTEXT_MIX: tuple[tuple[str, int], ...] = (
    ("solo", 20), ("short", 18), ("long", 8), ("deep", 4),
)

# The bases the two register mixes are scaled from. DERIVED rather than written
# down, because a hand-written base and an arm plan are two numbers that have to
# stay equal, and the one that drifts is silent.
_PHONE_UNITS: int = dict(_ARM_PLAN)["phone"]
_ADDRESS_UNITS: int = TARGET // 2 - _PHONE_UNITS


def _check_mixes() -> None:
    """Refuse at import if a mix stopped summing to what it is scaled from.

    An off-by-one here does not raise anywhere else: `_scaled` would quietly
    stretch or trim the mix and the family would ship a register split nobody
    chose. That is the v2 failure exactly — a composition described in one place
    and produced in another — so it is checked where it is written.
    """
    address = sum(count for _, count in _ADDRESS_UNIT_MIX)
    phone = sum(count for _, count in _PHONE_CASE_MIX)
    context = sum(count for _, count in _CONTEXT_MIX)
    units = sum(count for _, count in _ARM_PLAN)
    if units * 2 != TARGET:
        raise InvalidCase(f"the arm plan builds {units * 2} cases, TARGET is "
                          f"{TARGET}")
    if address != _ADDRESS_UNITS:
        raise InvalidCase(f"the address register mix covers {address} units, "
                          f"the arm plan has {_ADDRESS_UNITS}")
    if phone != _PHONE_UNITS * 2:
        raise InvalidCase(f"the phone register mix covers {phone} cases, the "
                          f"arm plan has {_PHONE_UNITS * 2}")
    if context != TARGET:
        raise InvalidCase(f"the context mix covers {context} cases, TARGET is "
                          f"{TARGET}")
    if "voice_raw" in dict(_PHONE_CASE_MIX):
        raise InvalidCase(
            "the phone mix offers voice_raw; the schema refuses a digit there "
            "and a number spelled out is the `spoken_id` family's question")


_check_mixes()
# A literary case has no real filler to pad with: the speech corpora supply every
# non-PII line this family uses, and ten authored sentences repeated sixty times
# is not a long context, it is one sentence sixty times.
_NO_DEEP: frozenset[str] = frozenset({"clean"})


def _scaled(mix: tuple[tuple[str, int], ...], total: int,
            base: int) -> dict[str, int]:
    """Scale a mix to `total`, keeping the sum exact."""
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


def _allocate(slots: tuple[tuple[str, ...], ...], quota: dict[str, int],
              rng: random.Random) -> list[str]:
    """Hand each slot a value from its allowed set, draining a global quota.

    WEIGHTED BY WHAT REMAINS, not greedy on the largest. Greedy starves every
    small quota until the end of the list — the literary register, two cases in
    fifty, would land entirely on the last arm, and then `clean` would exist in
    the corpus while crossing nothing. A rung of the ladder is supposed to close
    every dimension, and a register that only ever occurs with one arm cannot
    help it.

    Slots are handed in MOST-CONSTRAINED FIRST, which is what keeps the weighted
    draw feasible: an arm that can take three registers has taken its share
    before one that can take five starts.
    """
    out: list[str] = []
    for allowed in slots:
        live = [name for name in allowed if quota.get(name, 0) > 0]
        if not live:
            raise InvalidCase(
                f"no quota left for any of {allowed}; the mix and the arm "
                f"constraints disagree")
        pick = rng.choices(live, weights=[quota[name] for name in live], k=1)[0]
        quota[pick] -= 1
        out.append(pick)
    return out


def _streets_for(units: int, rng: random.Random) -> list[str]:
    """A distinct street per unit.

    WITHOUT REPLACEMENT, and the reason is the vault rather than variety. All
    fifty cases run against one tenant store; two units on the same street with
    the same house number give a partial mention two owners, the single-candidate
    rule then correctly refuses to link, and the `within` arm fails a gateway
    that did exactly the right thing. A corpus bug of that shape is
    indistinguishable from a product defect once the numbers are printed.

    BOTH NAMING PATTERNS ARE IN THE POOL and the mix is left to the draw: the
    dispatch corpus builds a street name in two ways and only two — a feminine
    adjective (14) or a surname in the genitive (28) — and a family that drew
    only one of them would measure the half where morphology behaves.
    """
    pool = list(_STREET_ADJECTIVE) + list(_STREET_GENITIVE)
    if len(pool) < units:
        raise InvalidCase(
            f"{units} units need {units} distinct street names and the pool "
            f"holds {len(pool)}; a pool a corpus can exhaust is a corpus that "
            f"silently starts repeating values")
    return rng.sample(pool, units)


def _plan(seed: int, count: int, rng: random.Random) -> tuple[_Unit, ...]:
    """Arm, registers, context rungs, streets and people. Deterministic in `seed`.

    THE TWO HALVES OF AN ADDRESS UNIT SHARE A REGISTER AND THE TWO HALVES OF A
    PHONE UNIT DO NOT, and both are requirements rather than taste. An address
    pair exists to ask whether the same street and house number, said the same
    way, is one identity or two; rendered in two registers the two mentions no
    longer share a street-and-house key, and then `across` gets its refusal for
    free while `within` demands a link nothing could have made. A phone pair
    exists to ask the opposite — whether ONE number in TWO shapes survives as one
    identity — so there the shapes must differ or the arm is asking about string
    equality.

    Context is a per-CASE decision everywhere: the two halves are two
    conversations and there is no reason they should be the same length.
    """
    if count % 2:
        raise InvalidCase(
            f"{FAMILY} builds pairs and {count} is odd; a half pair states no "
            f"claim, because «these two must not be linked» needs both of them")
    units = count // 2
    arm_counts = _scaled(_ARM_PLAN, units, TARGET // 2)
    arms: list[str] = []
    for name, _ in _ARM_PLAN:
        arms.extend([name] * arm_counts[name])

    phone_units = sum(1 for arm in arms if arm == "phone")
    address_arms = [arm for arm in arms if arm != "phone"]
    address_registers = _allocate(
        tuple(_ARM_REGISTERS[arm] for arm in address_arms),
        _scaled(_ADDRESS_UNIT_MIX, len(address_arms), _ADDRESS_UNITS), rng)
    phone_registers = _allocate(
        tuple(_ARM_REGISTERS["phone"] for _ in range(phone_units * 2)),
        _scaled(_PHONE_CASE_MIX, phone_units * 2, _PHONE_UNITS * 2), rng)

    registers: list[tuple[str, str]] = []
    address_cursor = phone_cursor = 0
    for arm in arms:
        if arm == "phone":
            registers.append((phone_registers[phone_cursor],
                              phone_registers[phone_cursor + 1]))
            phone_cursor += 2
        else:
            register = address_registers[address_cursor]
            address_cursor += 1
            registers.append((register, register))

    context_slots = tuple(
        tuple(rung for rung, _ in _CONTEXT_MIX
              if not (rung == "deep" and register in _NO_DEEP))
        for pair in registers for register in pair)
    rungs = _allocate(context_slots, _scaled(_CONTEXT_MIX, count, TARGET), rng)

    streets = _streets_for(units, rng)
    people = _people_for(units, rng)
    # TWO CITIES, AND THE PAIR IS DELIBERATELY SPLIT BETWEEN THEM. The `across`
    # probe never says its settlement — that is what makes it a partial mention —
    # but the requirement rests on the fact that it has a different one: «Луговая,
    # 7» in Тверь is not «Луговая, 7» in Омск, and a gateway that merges them has
    # sent a car to another city's building.
    cities = rng.sample(_CITIES, 2)

    plan: list[_Unit] = []
    seen: dict[str, int] = {}
    for position, arm in enumerate(arms):
        index = seen.get(arm, 0)
        seen[arm] = index + 1
        plan.append(_Unit(
            arm=arm, index=index, seed=seed,
            register_a=registers[position][0],
            register_b=registers[position][1],
            context_a=rungs[position * 2],
            context_b=rungs[position * 2 + 1],
            street=streets[position], person=people[position],
            city_a=cities[0], city_b=cities[1]))
    return tuple(plan)


def build(seed: int, count: int) -> list[Case]:
    """Every case this family contributes, in file order.

    FILE ORDER IS A SCORING DECISION HERE, not an accident: `preceded_by` must
    name a case that comes EARLIER, so the root is emitted first and every
    anchor before its own probe. `validate_corpus` refuses a forward reference,
    which is the version of this rule that survives somebody reordering the
    list.

    The returned list is `count + 1` long. The extra case is the root, and the
    module docstring argues why the schema forces it into existence.

    The RNG is the family's own — `random.Random(f"v3:{FAMILY}:{seed}")` — so the
    output does not move when a module built before this one changes how many
    draws it makes. Every case is validated at construction: a corpus that
    refuses late tells you which fifty cases might be wrong, and a family that
    refuses early tells you which one is.
    """
    _verify_shapes()
    pool = _filler_pool()
    rng = random.Random(f"v3:{FAMILY}:{seed}")
    cases: list[Case] = [_root_case(seed)]
    for unit in _plan(seed, count, rng):
        if unit.arm == "phone":
            cases.extend(_phone_pair(unit, pool))
        else:
            cases.extend(_address_pair(unit, pool, unit.arm))
    _verify_pairs(cases)
    if count == TARGET:
        _verify_emitted_shapes(cases)
    return cases


def _reachable(anchor_value: str, probe_value: str) -> bool:
    """Whether the probe's words are a SUBSEQUENCE of the anchor's.

    THE LINK HAS TO BE POSSIBLE BEFORE ITS PRESENCE OR ABSENCE MEANS ANYTHING.
    Every failure this family has had was a version of one mistake: the two
    mentions of one address were rendered independently, so a contraction («песят»
    against «пятьдесят») or a typo landed on one of them, the two no longer
    shared a street-and-house surface, and both claims dissolved — `across` got
    its refusal for free and `within` demanded a link nothing could make.

    A subsequence and not a substring, because the fuller mention interleaves
    markers: «улица петрова дом сто сорок семь» carries «дом» between the street
    and the house, and «петрова сто сорок семь» is still every word of it in
    order. Word-level and not character-level, because that is the granularity a
    street-and-house key is built at.
    """
    anchor_words = anchor_value.casefold().split()
    position = 0
    for word in probe_value.casefold().split():
        while position < len(anchor_words) and anchor_words[position] != word:
            position += 1
        if position == len(anchor_words):
            return False
        position += 1
    return True


def _verify_pairs(cases: list[Case]) -> None:
    """Refuse a family whose own claims do not hold. Six checks, six past bugs.

    They are here rather than in a test file because a generator that can produce
    a broken corpus and a validator that runs somewhere else are two things that
    have to stay in step. `schema.validate` already checked every case against
    itself; these are the claims that only exist ACROSS cases, which is exactly
    what the per-case gate is structurally unable to see — and this is the only
    family in the corpus whose whole subject lives there.
    """
    by_id = {case.id: case for case in cases}
    position = {case.id: index for index, case in enumerate(cases)}
    scope_cases = [case for case in cases if case.family == FAMILY]

    for case in scope_cases:
        if case.preceded_by not in by_id:
            raise InvalidCase(
                f"{case.id}: preceded_by {case.preceded_by!r} is not emitted by "
                f"this module; the pair would be scored against an empty vault")
        if position[case.preceded_by] >= position[case.id]:
            raise InvalidCase(
                f"{case.id}: preceded_by {case.preceded_by!r} comes later in "
                f"file order")

    # A `same` and a `different` claim that could be satisfied by the same
    # behaviour is not a claim. Every probe must name a link, and the family must
    # carry both kinds — a file with only `different` claims is passed by a
    # gateway that never links at all.
    kinds = {link.kind for case in scope_cases for link in case.links}
    if kinds != {"same", "different"}:
        raise InvalidCase(
            f"the family carries link kinds {sorted(kinds)}; without BOTH, «не "
            f"связал» and «сломан» are one observation")

    # Two units on one street with one house number give a partial mention two
    # owners. The single-candidate rule then correctly refuses to link and the
    # `within` arm fails a gateway that was right.
    keys: dict[str, str] = {}
    for case in scope_cases:
        for item in case.pii:
            if item.type != "LOC" or item.duty != "required":
                continue
            key = item.canonical.casefold()
            owner = case.cluster
            if keys.setdefault(key, owner) != owner:
                raise InvalidCase(
                    f"address {item.canonical!r} is claimed by two clusters "
                    f"({keys[key]} and {owner}); a partial mention with two "
                    f"owners makes the corpus's own requirement unsatisfiable")

    for case in scope_cases:
        for link in case.links:
            if not link.case:
                continue
            anchor = by_id[link.case]
            probe_value = next(item.value for item in case.pii
                               if item.id == link.left)
            anchor_values = {item.value for item in anchor.pii
                             if item.type == "LOC" and item.duty == "required"}

            # THE CONVERSATION IDENTITY IS THE CLAIM. `within` is the one arm
            # whose halves share it; every other arm exists because they do not.
            # Get this line wrong and the family still builds, still validates,
            # and measures the opposite of what it says.
            wants_same = case.id.startswith("sc-within-")
            if not case.conversation_id and not anchor.conversation_id:
                # The derived path. The harness reads the FIRST TWO MESSAGES to
                # invent an identity — a system prompt is shared by every
                # dialogue an agent has, so the opener is all that separates
                # them — and two halves whose first two messages matched would
                # silently become one conversation. Only the phone control is
                # allowed here, because its claim is tenant-wide and true either
                # way; asserting the difference anyway keeps that permission
                # from turning into a place where a real claim could hide.
                if wants_same:
                    raise InvalidCase(
                        f"{case.id}: a `within` pair cannot derive its "
                        f"conversation identity — the claim IS the identity")
                head = [message.content for message in case.messages[:2]]
                anchor_head = [message.content
                               for message in anchor.messages[:2]]
                if head == anchor_head:
                    raise InvalidCase(
                        f"{case.id}: the first two messages match the anchor's, "
                        f"so a derived conversation identity makes these one "
                        f"conversation and the pair spans no boundary")
            elif (case.conversation_id == anchor.conversation_id) is not wants_same:
                raise InvalidCase(
                    f"{case.id}: conversation {case.conversation_id!r} against "
                    f"the anchor's {anchor.conversation_id!r} — this arm needs "
                    f"them {'equal' if wants_same else 'different'}")

            if not anchor_values:
                continue
            # The two halves of a `full` unit must carry the identical string;
            # the two halves of the other address arms must not, or the fuller
            # mention is not fuller and the pair asks nothing.
            if case.id.startswith("sc-full-"):
                if probe_value not in anchor_values:
                    raise InvalidCase(
                        f"{case.id}: the `full` control repeats {probe_value!r}, "
                        f"which the anchor never said as written")
                continue
            if probe_value in anchor_values:
                raise InvalidCase(
                    f"{case.id}: the probe says exactly what the anchor said, "
                    f"so there is no partial mention to resolve")
            # And the partial must still be REACHABLE from the fuller one, or
            # the arm is graded on a link that was never possible.
            if not any(_reachable(value, probe_value) for value in anchor_values):
                raise InvalidCase(
                    f"{case.id}: {probe_value!r} is not a word-subsequence of "
                    f"any address the anchor said ({sorted(anchor_values)}); "
                    f"nothing could link them, so «не связал» and «правильно "
                    f"отказался» are the same observation")


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
    scope_cases = [case for case in cases if case.family == FAMILY]
    print(f"{FAMILY}: {len(scope_cases)} cases + {len(cases) - len(scope_cases)}"
          f" root ({ROOT_FAMILY})")

    def tally(key: Any) -> str:
        counts: dict[str, int] = {}
        for case in scope_cases:
            counts[key(case)] = counts.get(key(case), 0) + 1
        return "  ".join(f"{name} {count} ({count / len(scope_cases):.0%})"
                         for name, count in sorted(counts.items()))

    print("register   ", tally(lambda c: c.register))
    print("context    ", tally(lambda c: c.context))
    print("provenance ", tally(lambda c: c.provenance.kind))
    print("selection  ", tally(lambda c: c.provenance.selection))
    print("arm        ", tally(lambda c: c.id.split("-")[1]))
    print("conv id    ", tally(lambda c: "given" if c.conversation_id else "derived"))
    real = sum(1 for case in cases
               if case.provenance.kind in ("verbatim", "recombined"))
    print(f"форма из речи {real}/{len(cases)} = {real / len(cases):.1%}")

    links: dict[str, int] = {}
    for case in cases:
        for link in case.links:
            links[f"{link.kind}/{'cross' if link.case else 'inner'}"] = (
                links.get(f"{link.kind}/{'cross' if link.case else 'inner'}", 0)
                + 1)
    print("links      ", "  ".join(f"{k} {v}" for k, v in sorted(links.items())))

    negatives: dict[str, int] = {}
    for case in cases:
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print("negatives  ", "  ".join(f"{k} {v}"
                                   for k, v in sorted(negatives.items())))
    missing = [name for name in
               ("street_no_name", "flat_as_home", "entrance_no_street",
                "room_number", "time_of_day", "order_number", "quantity",
                "fare", "city_reference", "measure")
               if name not in negatives]
    print(f"negative families not emitted at this seed: {missing}")

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
    forbidden = sum(len(case.final.must_not_contain) for case in cases)
    print(f"must_not_contain values {forbidden}")
    longest = max(cases, key=lambda c: sum(len(m.content) for m in c.messages))
    print(f"longest    {longest.id}: {len(longest.messages)} messages, "
          f"{sum(len(m.content) for m in longest.messages)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
