"""The `length` family: the datum is named early and asked for late.

WHAT THIS FAMILY IS FOR. v1's whole corpus fit in 159 characters, so nothing in
it ever asked whether a substitute still resolves after thirty intervening
messages — which is the shape of every real support dialogue. Three mechanisms
are load-bearing in production and were unloaded in v1 by construction:

  * the **mask cache**, which is keyed on RAW content and is what stops a
    growing transcript costing O(n^2). It cannot be exercised by a corpus whose
    cases have one message.
  * **`content_key`'s conversation component**, without which the cache serves
    one conversation's link to every later one. A corpus that never sets a
    `conversation_id` and never varies it cannot see that.
  * **`is_minted_token`** — the rule that a substitute already handed to the
    model must not be masked again. CLAUDE.md records that the content cache
    hides this from the obvious test and that the failure appears only when a
    token arrives inside other surrounding text, i.e. in a long dialogue and
    nowhere else.

FOUR SIZES, THREE RUNGS. The brief asks for empty / small / medium / large; the
schema bands three (`short` 0-400, `medium` 1200-4000, `long` 12000-24000) and
`validate()` refuses anything else. Empty and small are the two shapes of the
`short` rung and alternate inside it: `empty` is one user message that states
the datum and consumes it immediately — the control arm, which is what makes a
regression at `long` attributable to length rather than to the scenario — and
`small` is the same exchange with a read-back and a follow-up.

WHAT MAKES A LONG CASE INTERESTING IS NOT ITS LENGTH. Padding tests nothing. In
every case here the datum is stated in the FIRST message and the final user turn
refers to it obliquely — «на тот же номер», «на тот же адрес», «наберите Петру»
— so the value that must reach the tool never appears near the call. Between
them stand real support exchanges carrying distractors: two other people with
their own names and phones, a bare street that identifies nobody, order and
track numbers, and invoice dates that are not dates of birth.

REPEATED ASSISTANT BOILERPLATE IS DELIBERATE. Identical content re-sent inside a
growing transcript is the mask cache's hit path; a corpus in which every message
is unique measures the miss path only, and the two have different bugs.

THE ROUND-TRIP DENOMINATOR IS NOT THE SAME IN EVERY REGISTER, and a scorer must
print it rather than assume it. In `voice_raw` the customer's phone is spelled
out in words — measured on OpenSTT `asr_calls_2_val`, zero of 12 950 real call
transcripts carry a digit — and it is labelled `required` gold with **no**
`tool_param`. The alternative was tried on paper and rejected twice over:
demanding the dialable form back makes one fifth of the corpus a constant
failure that reads as corruption, and accepting the words back rewards a gateway
that detected nothing. Non-detection is already scored, on the axis that exists
for it; the round trip does not get to claim it too. Names and addresses carry
the round trip in that register, and ASR gives us both as words we can handle.

NOT HERE ON PURPOSE: tool-result messages. Personal data arriving FROM the
customer's CRM is the `result` family's question, and duplicating it would be
cost without signal — the rule the taxonomy was cut by.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bench.agentpii2.schema import (
    Case,
    ExpectedCall,
    LinkExpectation,
    Negative,
    PiiItem,
)

# The family name in the schema is `length`; this module is `context.py` because
# the axis it builds is context LENGTH, and the two names must not drift apart —
# `validate()` refuses any family outside `FAMILIES`.
FAMILY = "length"

# Difficulty is NOT crossed here (docs/tz-agentpii2.md §4): a long context is
# difficult by construction, and crossing three difficulties over three rungs
# would spend 24 cells re-measuring what `transfer` already measures for less.
# The constant is `hard` and it is a label, not a knob.
DIFFICULTY = "hard"

RUNGS: tuple[str, ...] = ("short", "medium", "long")

# Mid-band targets, in characters over the whole case. Aiming at the middle
# rather than at the floor is what keeps a case inside its band when the last
# filler exchange overshoots: an exchange is at most ~600 characters and both
# bands are thousands wide.
_TARGET: dict[str, int] = {"short": 0, "medium": 2_600, "long": 16_500}

# How much prose one assistant reply carries at each rung. A long case built out
# of forty two-line replies would be forty turns of nothing; a real support
# session at 16k characters is a few dozen exchanges where the agent explains a
# policy in a paragraph.
_REPLY_SENTENCES: dict[str, tuple[int, int]] = {"medium": (1, 2), "long": (3, 5)}


# --- people ---------------------------------------------------------------
#
# Authored from the domain: who walks into a Russian shop's support chat. The
# overlap with any gazetteer is unavoidable — Russian names are Russian names —
# but nothing is here BECAUSE it is detected.

@dataclass(frozen=True)
class _Person:
    surname: str
    given: str
    patronymic: str
    dative: str      # written out, never derived — see the note below


# THE DATIVE IS A TABLE, NOT A RULE. Russian given names have irregulars
# («Пётр» -> «Петру», not «Пётру») and indeclinables («Ань»), and a rule that
# gets one wrong writes a form nobody says into the GROUND TRUTH, where it is
# scored as though it were real Russian. A table is checkable by a native
# speaker in ten seconds; a rule is not.
_RU_MEN: tuple[_Person, ...] = (
    _Person("Иванов", "Пётр", "Сергеевич", "Петру"),
    _Person("Соколов", "Игорь", "Валентинович", "Игорю"),
    _Person("Кузнецов", "Дмитрий", "Андреевич", "Дмитрию"),
    _Person("Морозов", "Алексей", "Николаевич", "Алексею"),
    _Person("Волков", "Сергей", "Павлович", "Сергею"),
    _Person("Лебедев", "Максим", "Олегович", "Максиму"),
    _Person("Новиков", "Артём", "Витальевич", "Артёму"),
    _Person("Фёдоров", "Кирилл", "Романович", "Кириллу"),
    _Person("Григорьев", "Никита", "Львович", "Никите"),
    _Person("Захаров", "Владислав", "Юрьевич", "Владиславу"),
    _Person("Панов", "Роман", "Игоревич", "Роману"),
    _Person("Дорофеев", "Андрей", "Викторович", "Андрею"),
)
_RU_WOMEN: tuple[_Person, ...] = (
    _Person("Иванова", "Мария", "Львовна", "Марии"),
    _Person("Соколова", "Анна", "Игоревна", "Анне"),
    _Person("Кузнецова", "Ольга", "Дмитриевна", "Ольге"),
    _Person("Морозова", "Екатерина", "Сергеевна", "Екатерине"),
    _Person("Волкова", "Татьяна", "Ивановна", "Татьяне"),
    _Person("Лебедева", "Ирина", "Петровна", "Ирине"),
    _Person("Новикова", "Светлана", "Юрьевна", "Светлане"),
    _Person("Фёдорова", "Юлия", "Андреевна", "Юлии"),
    _Person("Панова", "Наталья", "Олеговна", "Наталье"),
    _Person("Зуева", "Елена", "Борисовна", "Елене"),
)
# Deliberately hostile to suffix rules: no -ов/-ев/-ин, several non-Slavic. A
# shop's foreign customers are not an adversarial case, they are Tuesday, so
# this pool is drawn from at EVERY rung and in every register — measured on
# NEREL, nearly every name our detector misses is one of these.
_FOREIGN: tuple[_Person, ...] = (
    _Person("Ким", "Виктор", "", "Виктору"),
    _Person("Тагиев", "Рустам", "", "Рустаму"),
    _Person("Мкртчян", "Ашот", "", "Ашоту"),
    _Person("Шевчук", "Олесь", "", "Олесю"),
    _Person("Гулиев", "Эльдар", "", "Эльдару"),
    _Person("Абдуллаев", "Тимур", "", "Тимуру"),
    _Person("Саркисян", "Карен", "", "Карену"),
    _Person("Нгуен", "Ань", "", "Ань"),
    _Person("Мамедова", "Лейла", "", "Лейле"),
    _Person("Валиахметов", "Ильдар", "", "Ильдару"),
    _Person("Джонсон", "Майкл", "", "Майклу"),
    _Person("Ли", "Чен", "", "Чену"),
)

_STREETS: tuple[str, ...] = (
    "Ленинский проспект", "улица Тверская", "проспект Мира", "улица Пушкина",
    "Кутузовский проспект", "улица Гагарина", "Профсоюзная улица",
    "улица Строителей", "бульвар Энтузиастов", "Садовая улица",
    "улица Металлургов", "проспект Вернадского",
)
# THE PREPOSITIONAL OF EVERY STREET, written out for the same reason the dative
# of every given name is: «мой офис на улица Гагарина» is not Russian, and a
# corpus that writes it is measuring a detector on a sentence nobody would send.
# The declension of a street name depends on the TYPE word («на Ленинском
# проспекте», «на Профсоюзной улице», «на улице Тверской») and on whether the
# name itself declines with it, so a rule would need the gender and the
# agreement; a table of twelve is checkable at a glance.
_STREET_PREPOSITIONAL: dict[str, str] = {
    "Ленинский проспект": "Ленинском проспекте",
    "улица Тверская": "улице Тверской",
    "проспект Мира": "проспекте Мира",
    "улица Пушкина": "улице Пушкина",
    "Кутузовский проспект": "Кутузовском проспекте",
    "улица Гагарина": "улице Гагарина",
    "Профсоюзная улица": "Профсоюзной улице",
    "улица Строителей": "улице Строителей",
    "бульвар Энтузиастов": "бульваре Энтузиастов",
    "Садовая улица": "Садовой улице",
    "улица Металлургов": "улице Металлургов",
    "проспект Вернадского": "проспекте Вернадского",
}

_CITIES: tuple[str, ...] = (
    "Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск",
    "Нижний Новгород", "Краснодар", "Самара",
)
_PHONE_PREFIXES: tuple[str, ...] = ("916", "926", "903", "985", "917", "999")


# --- speech ---------------------------------------------------------------
#
# `voice_raw` is verbatim ASR and carries NO digits. Everything numeric in it is
# a word, which is why the register exists at all: a phone in digits is held by
# libphonenumber's checksum and a phone in words is held by nothing we have.

_ONES: tuple[str, ...] = (
    "ноль", "один", "два", "три", "четыре",
    "пять", "шесть", "семь", "восемь", "девять")
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
_TENS: dict[int, str] = {
    2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
    6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"}
_HUNDREDS: dict[int, str] = {
    1: "сто", 2: "двести", 3: "триста", 4: "четыреста", 5: "пятьсот",
    6: "шестьсот", 7: "семьсот", 8: "восемьсот", 9: "девятьсот"}


def _spell_int(value: int) -> str:
    """0-999 in words. Nominative, which is how a number is read aloud alone."""
    if not 0 <= value <= 999:
        raise ValueError(f"only 0-999 is spelled here, got {value}")
    if value < 10:
        return _ONES[value]
    if value < 20:
        return _TEENS[value - 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        return _TENS[tens] if not ones else f"{_TENS[tens]} {_ONES[ones]}"
    hundreds, rest = divmod(value, 100)
    return _HUNDREDS[hundreds] if not rest else f"{_HUNDREDS[hundreds]} {_spell_int(rest)}"


def _spell_group(group: str) -> str:
    """One dictated group of a phone number.

    A LEADING ZERO IS READ DIGIT BY DIGIT. «03» is «ноль три» and never «три»:
    the zero is information, and dropping it here would put a nine-digit phone
    into the ground truth of a corpus that claims to carry ten.
    """
    if group.startswith("0"):
        return " ".join(_ONES[int(digit)] for digit in group)
    return _spell_int(int(group))


def _spell_phone(digits: str) -> str:
    """Ten national digits, dictated the way the groups are said on a call."""
    return " ".join((
        "восемь", _spell_group(digits[:3]), _spell_group(digits[3:6]),
        _spell_group(digits[6:8]), _spell_group(digits[8:])))


# --- sloppy ---------------------------------------------------------------
#
# MEASURED, not invented. Counted over RuSpellGold's 2112 human corrections:
# 950 single-letter substitutions (ё->е is 499 of them), 626 dropped letters,
# 463 stray characters. The commonest Russian «typo» is not a typo — «ё» written
# as «е» is ordinary practice, and it lands straight on names: Пётр, Фёдоров.
# The vivid Latin-layout slip that the first version of this register was built
# entirely from barely appears, so it stays as the minority it is.
_PHONETIC: tuple[tuple[str, str], ...] = (
    ("ё", "е"), ("ё", "е"), ("ё", "е"),
    ("а", "о"), ("и", "е"), ("о", "а"), ("е", "и"), ("ъ", "ь"),
    ("о", "у"), ("и", "ы"), ("я", "и"), ("т", "д"), ("з", "с"),
)
_LATIN_TWINS: dict[str, str] = {
    "о": "o", "а": "a", "е": "e", "с": "c", "р": "p", "у": "y", "х": "x",
    "О": "O", "А": "A", "Е": "E", "С": "C", "Р": "P"}


# A SINGLE-LETTER EDIT OVER RUSSIAN PROSE PRODUCES OBSCENITIES, at a low rate
# and reliably enough to matter for a corpus meant to be published: the first
# run of this generator turned «товар» into «твар», and «сутки» is one dropped
# letter from another. Enumerating what an edit COULD produce is hopeless, so
# the guard runs the other way — the slipped text is rejected if any of its
# words lands in this list, and a rejected slip is retried and then abandoned.
# Whole words for the ones an accident reaches; roots for the ones no reader
# would forgive appearing at all.
_UNFORTUNATE_WORDS: frozenset[str] = frozenset({
    "твар", "твари", "тварь", "сука", "суки", "суке", "сук", "жопа", "жопе",
    "жоп", "срак", "срака", "гнида", "гнид", "дура", "дурак", "мудак", "муда",
    "хер", "херу", "хрен", "бля", "пидр", "чмо", "быдло", "урод", "тупой",
})
_UNFORTUNATE_ROOTS: tuple[str, ...] = (
    "хуй", "хуе", "хуё", "пизд", "ебат", "ебал", "ебан", "ебу", "бляд",
    "гандон", "залуп", "мудак", "уёб",
)
_WORD_EDGES = " .,!?;:—«»\"()-\n"


def _is_publishable(text: str) -> bool:
    for word in text.lower().split():
        stripped = word.strip(_WORD_EDGES)
        if stripped in _UNFORTUNATE_WORDS:
            return False
        if any(root in stripped for root in _UNFORTUNATE_ROOTS):
            return False
    return True


def _slip(text: str, rng: random.Random) -> str:
    """One realistic writing error, drawn from the measured distribution.

    EVERY BRANCH LEAVES DIGITS ALONE. A stray space inside a track number would
    break the negative that claims it, and a dropped digit inside a phone would
    change what the ground truth is even about — the register is about how
    people WRITE, and a corrupted identifier is a different experiment.

    A slip that produces an unpublishable word is retried and then given up on.
    Giving up returns the CLEAN text, which costs one sloppy case its typo — a
    cheaper price than a benchmark nobody will put in front of a customer.
    """
    for _ in range(6):
        roll = rng.random()
        if roll < 0.45:
            slipped = _substitute_letter(text, rng)
        elif roll < 0.75:
            slipped = _drop_letter(text, rng)
        elif roll < 0.90:
            slipped = _stray_space(text, rng)
        else:
            slipped = _layout_slip(text, rng)
        if _is_publishable(slipped):
            return slipped
    return text


def _substitute_letter(text: str, rng: random.Random) -> str:
    for source, target in rng.sample(_PHONETIC, len(_PHONETIC)):
        positions = [i for i, ch in enumerate(text) if ch.lower() == source]
        if not positions:
            continue
        index = rng.choice(positions)
        replacement = target.upper() if text[index].isupper() else target
        return text[:index] + replacement + text[index + 1:]
    return text


def _drop_letter(text: str, rng: random.Random) -> str:
    # Never the first character: a dropped initial stops being a typo and
    # becomes a different word, which is a different experiment.
    positions = [i for i, ch in enumerate(text) if ch.isalpha() and i > 0]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + text[index + 1:]


def _stray_space(text: str, rng: random.Random) -> str:
    positions = [i for i, ch in enumerate(text) if ch == " "]
    if positions and rng.random() < 0.5:
        index = rng.choice(positions)
        return text[:index] + text[index + 1:]
    inner = [i for i in range(2, len(text) - 2) if text[i].isalpha()]
    if not inner:
        return text
    index = rng.choice(inner)
    return text[:index] + " " + text[index:]


def _layout_slip(text: str, rng: random.Random) -> str:
    """A Latin letter typed inside a Cyrillic word — the keyboard layout slipped."""
    positions = [i for i, ch in enumerate(text) if ch in _LATIN_TWINS]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + _LATIN_TWINS[text[index]] + text[index + 1:]


# --- register rendering ---------------------------------------------------

_SPEECH_DROP = str.maketrans({ch: None for ch in ".,!?;:—«»\"()"})
_SPOKEN_FILLERS: tuple[str, ...] = ("ну ", "вот ", "значит ", "это самое ")


def _prose(text: str, register: str, rng: random.Random) -> str:
    """A literal segment of a message, as this channel would carry it.

    THIS RUNS BEFORE ASSEMBLY AND ONLY ON LITERAL SEGMENTS. A post-processing
    pass over a finished message changes its length and silently invalidates
    every span already computed against it — the corpus keeps scoring, and
    scores wrongly. Slot values never pass through here: they were rendered in
    their own register-specific way and their exact surface is the ground truth.

    Leading and trailing spaces are preserved verbatim. They are what separates
    a cue word from the slot next to it, and collapsing them would glue
    «телефон» onto the number and move the span by one.
    """
    if register == "clean" or not text.strip(" "):
        return text
    lead = text[:len(text) - len(text.lstrip(" "))]
    trail = text[len(text.rstrip(" ")):]
    core = text.strip(" ").lower()
    if register in ("chat", "sloppy"):
        core = core.replace(",", "").rstrip(".")
    else:
        core = core.translate(_SPEECH_DROP).replace("-", " ")
        core = " ".join(core.split())
        if rng.random() < 0.18:
            core = rng.choice(_SPOKEN_FILLERS) + core
    return lead + core + trail


def _render_name(person: _Person, register: str, rng: random.Random) -> str:
    if register == "clean":
        return " ".join(p for p in (person.surname, person.given,
                                    person.patronymic) if p)
    if register == "chat":
        # The patronymic is the first thing a messenger drops, and the capitals
        # go with it. A detector that needs «Иванов Пётр Сергеевич» sees nothing.
        order = (f"{person.surname} {person.given}" if rng.random() < 0.6
                 else f"{person.given} {person.surname}")
        return order.lower()
    if register == "sloppy":
        return _slip(f"{person.surname} {person.given}", rng)
    return f"{person.given} {person.surname}".lower()


def _render_phone(digits: str, register: str, rng: random.Random) -> str:
    a, b, c, d = digits[:3], digits[3:6], digits[6:8], digits[8:]
    if register == "clean":
        return f"+7 {a} {b}-{c}-{d}"
    if register == "chat":
        return rng.choice((f"8{digits}", f"+7{digits}", f"8 {a} {b} {c} {d}"))
    if register == "sloppy":
        # A Cyrillic О typed where a zero belongs is the commonest obfuscation
        # that is not an obfuscation — it is a keyboard slip, and it survives
        # into production because it is invisible on screen.
        formatted = f"8-{a}-{b}-{c}-{d}"
        return formatted.replace("0", "О", 1) if "0" in formatted else formatted
    if register == "voice_itn":
        return f"8 {a} {b} {c} {d}"
    return _spell_phone(digits)


def _render_echo_phone(digits: str, register: str) -> str:
    """The agent reading the number back — in a DIFFERENT format on purpose.

    «+7 916 214-88-03» said back as «89162148803» is one subscriber written two
    ways, and collapsing them to one key is exactly what `Vault.canonicalize`
    claims to do. Echoing the identical string would make the `same` link on
    this pair a test of string equality and nothing else.
    """
    if register == "voice_raw":
        return _spell_phone(digits)
    if register == "voice_itn":
        return f"8 {digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:]}"
    return f"8{digits}"


def _render_address(city: str, street: str, house: int, flat: int,
                    register: str, rng: random.Random) -> str:
    if register == "clean":
        return f"{city}, {street}, д. {house}, кв. {flat}"
    if register == "chat":
        # The city is dropped: in a shop's own chat it is assumed, and a ground
        # truth that names it anyway scores the gateway on a word nobody wrote.
        return f"{street.lower()} {house} кв {flat}"
    if register == "sloppy":
        return _slip(f"{street} {house}кв{flat}", rng)
    if register == "voice_itn":
        return f"{street.lower()} {house} квартира {flat}"
    return (f"{street.lower()} дом {_spell_int(house)} "
            f"квартира {_spell_int(flat)}")


def _render_bare_street(street: str, register: str) -> str:
    """A street with no house number — `optional` by law, not by uncertainty.

    152-ФЗ ст. 3 п. 1 is about an identified or identifiable person and hundreds
    of buildings stand on улица Пушкина. `bench/voice` already split this and
    measured what folding the two together costs: one number of 71% that was
    really 94% on the addresses and 47% on the bare streets.

    IT IS WRITTEN IN THE PREPOSITIONAL, because it stands after «на» and that is
    the case Russian puts it in. That also makes it the harder half of the type:
    the delivery address in this family is nominative with a house number, so
    the two LOC items differ in inflection as well as in legal class.

    NO SLIP IN `sloppy`. The surface is already inflected, and stacking a typo on
    top would ask a gateway to undo two transforms at once to reach the
    canonical — a demand nothing else in the corpus makes.
    """
    surface = _STREET_PREPOSITIONAL[street]
    return surface if register == "clean" else surface.lower()


# --- tools ----------------------------------------------------------------
#
# Plain OpenAI function-calling JSON so the corpus replays against any provider
# with no translation layer. Names and parameters match v1's inventory on
# purpose: this family changes the CONTEXT the call sits in, not the contract,
# and a renamed parameter would make the two versions incomparable.

def _tool(name: str, description: str,
          params: dict[str, tuple[str, str]],
          required: list[str]) -> dict[str, Any]:
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


_TOOLS: dict[str, dict[str, Any]] = {
    "escalate_ticket": _tool(
        "escalate_ticket",
        "Передать обращение старшему специалисту с контактами клиента.",
        {"customer_name": ("string", "ФИО клиента"),
         "phone": ("string", "Телефон для обратной связи"),
         "order_id": ("string", "Номер заказа, если он известен"),
         "summary": ("string", "Краткое описание проблемы")},
        ["customer_name", "phone", "summary"]),
    "update_delivery_address": _tool(
        "update_delivery_address",
        "Изменить адрес доставки у существующего заказа.",
        {"order_id": ("string", "Номер заказа"),
         "address": ("string", "Новый адрес с домом и квартирой"),
         "recipient_name": ("string", "ФИО получателя, если он меняется")},
        ["order_id", "address"]),
    "check_order_status": _tool(
        "check_order_status",
        "Узнать статус заказа по его номеру и телефону покупателя.",
        {"order_id": ("string", "Номер заказа"),
         "phone": ("string", "Телефон, указанный при оформлении")},
        ["order_id", "phone"]),
    "create_order": _tool(
        "create_order",
        "Оформить заказ на клиента и отправить его в доставку.",
        {"customer_name": ("string", "ФИО получателя"),
         "phone": ("string", "Контактный телефон получателя"),
         "address": ("string", "Адрес доставки с домом и квартирой"),
         "items": ("string", "Артикулы товаров через запятую")},
        ["customer_name", "phone", "address"]),
}


def _tools_for(primary: str) -> list[dict[str, Any]]:
    """Always more than one tool.

    A single-tool prompt lets a model succeed by having nowhere else to go,
    which hides whether masking damaged its ability to CHOOSE — and choosing is
    where an implausible substitute does its damage.
    """
    others = [name for name in _TOOLS if name != primary][:2]
    return [_TOOLS[primary]] + [_TOOLS[name] for name in others]


# --- filler ---------------------------------------------------------------
#
# What a Russian support conversation is actually made of between the moment the
# customer states their data and the moment they refer back to it. Nothing here
# is padding in the sense the brief warns about: every exchange is text a
# gateway must mask nothing in, which is the over-masking axis running for free
# over thousands of characters per case.

_QUESTIONS: tuple[str, ...] = (
    "А доставка в субботу возможна?",
    "Оплатить можно картой курьеру?",
    "Сколько обычно идёт доставка по городу?",
    "Упаковка надёжная? Там стекло.",
    "Чек будет бумажный или электронный?",
    "Можно поменять цвет на серый?",
    "Гарантия на этот товар какая?",
    "А самовывоз у вас есть?",
    "Если меня не будет дома, что делать?",
    "Можно перенести доставку на понедельник?",
    "А в выходные вы работаете?",
    "Курьер предупредит заранее?",
    "Можно оплатить при получении?",
    "Скидка по промокоду сохранится?",
    "Товар точно в наличии?",
    "А если не подойдёт, вернуть можно?",
    "Подъезд у меня без домофона, как быть?",
    "Можно попросить позвонить, а не писать?",
    "Вы работаете с юридическими лицами?",
    "А доставка платная?",
    "Подъём на этаж входит в стоимость?",
    "Долго ждать возврат денег?",
    "А можно оставить у консьержа?",
    "Товар точно оригинальный?",
    "Рассрочка у вас есть?",
    "Можно счёт на организацию?",
    "Курьер поднимет на этаж?",
    "Сколько ждать возврат на карту?",
    "А коробка большая?",
    "Инструкция на русском есть?",
    "Можно доплатить бонусами?",
    "А если товар пришёл битый?",
    "Вы перезваниваете или пишете?",
    "Когда будет уценка?",
    "Можно забронировать до завтра?",
    "А в пригород возите?",
    "Ночью не звоните, надеюсь?",
    "Подарочную упаковку сделаете?",
    "Сертификат пришлёте?",
    "Можно частичный отказ у двери?",
)

_SENTENCES: tuple[str, ...] = (
    "Доставка по городу занимает обычно два рабочих дня, по области чуть дольше.",
    "Курьер связывается с получателем заранее и согласовывает удобное время.",
    "Оплатить можно картой курьеру, наличными или онлайн по ссылке.",
    "Электронный чек уходит на почту сразу после оплаты.",
    "Если товар не подошёл, вернуть его можно в течение двух недель без объяснения причин.",
    "Возврат денег приходит на ту же карту, с которой была оплата.",
    "Гарантия производителя действует год, талон лежит внутри упаковки.",
    "Хрупкие позиции мы кладём в короб с наполнителем и помечаем стикером.",
    "Самовывоз доступен из пункта выдачи рядом с метро, он работает до девяти вечера.",
    "Перенести доставку можно не позднее чем за сутки до выбранной даты.",
    "В выходные мы тоже возим, но окна доставки заполняются быстрее.",
    "Если дома никого не будет, заказ можно передать любому человеку, который назовёт номер.",
    "Промокод применяется к корзине целиком и не суммируется с другими скидками.",
    "Наличие обновляется раз в час, поэтому редкие позиции лучше бронировать.",
    "Подъём на этаж бесплатный, если в доме есть лифт.",
    "Без домофона курьер позвонит на телефон, указанный в заказе.",
    "Для юридических лиц мы выставляем счёт и работаем по договору.",
    "Доставка бесплатная от определённой суммы, ниже неё считается по тарифу.",
    "Заявку я уже отметил, коллеги увидят её в системе.",
    "Если появятся вопросы, напишите нам в этот же чат.",
    "Комплектность мы проверяем на складе перед отправкой.",
    "Курьер может подождать не больше пятнадцати минут.",
    "Обмен на другой цвет оформляется как возврат и новый заказ.",
    "Сборку и установку мы не делаем, но можем порекомендовать подрядчика.",
    "Статус заказа виден в личном кабинете и обновляется автоматически.",
    "Если курьер не дозвонится, он оставит заказ в ближайшем пункте выдачи.",
    "Сроки на праздничной неделе сдвигаются, мы предупреждаем об этом заранее.",
    "Претензию по качеству мы принимаем в свободной форме, фотографии помогают.",
    "Если в заказе несколько позиций, мы стараемся собрать их в одну отправку.",
    "Крупногабаритный товар везёт отдельная машина, время согласуют накануне.",
    "Курьер не поднимается выше первого этажа, если лифт не работает.",
    "При получении можно вскрыть упаковку и проверить внешний вид.",
    "Отказаться от части заказа можно у двери, курьер оформит это на месте.",
    "Деньги за отказ возвращаются тем же способом, каким была оплата.",
    "На карту возврат идёт до десяти рабочих дней, это сроки банка, не наши.",
    "Наличными курьер сдачу даёт, но про крупную купюру лучше предупредить.",
    "Подарочная упаковка бесплатная, её нужно отметить в комментарии к заказу.",
    "Сертификат на товар мы можем прислать отдельным файлом.",
    "Если позиция закончилась после оформления, менеджер предложит замену.",
    "Бронь держится сутки, потом товар возвращается в общий остаток.",
    "Пункты выдачи по субботам работают короче, чем в будни.",
    "Доставка в пригород считается по отдельному тарифу и зависит от расстояния.",
    "Мы не звоним ночью, все звонки только в дневное время.",
    "Уведомления приходят в чат, дублировать их по почте не обязательно.",
    "Скидка постоянного покупателя начисляется автоматически при следующем заказе.",
    "Бонусами можно оплатить часть суммы, но не всю.",
    "Товар с уценкой возврату по общим правилам не подлежит, это есть в карточке.",
    "Инструкция на русском вложена в коробку, электронная версия есть на сайте.",
    "Если коробка пришла помятой, зафиксируйте это при курьере.",
    "Сроки сборки заказа мы считаем в рабочих днях, выходные не входят.",
    "Менеджер перезванивает в течение часа в рабочее время.",
    "Жалобу можно оставить здесь же, я передам её руководителю смены.",
)

# A number in prose, and the reason it is here: every one of these is a NEGATIVE
# — PII-shaped and not personal data — so a gateway that masks it has broken the
# conversation as surely as one that leaks. The value is a separate literal part
# so no register transform can touch it: lowercasing «A-4471» or stripping the
# dots out of «15.05.2025» would leave the negative unfindable in its own
# message, and `validate` would refuse the case for a reason that is not the one.
_NUMBER_TOPICS: tuple[tuple[str, str, int, str], ...] = (
    ("Трек-номер вашей посылки ", ", по нему видно весь путь.", 14, "трек-номер"),
    ("Артикул этой позиции ", ", он же указан на коробке.", 5, "артикул товара"),
    ("Счёт ", " уже сформирован, оплатить можно по нему.", 6, "номер счёта"),
    ("Обращение ", " я передал старшему специалисту.", 6, "номер обращения"),
    ("Пункт выдачи ", " на первом этаже торгового центра.", 3, "номер пункта выдачи"),
)

# A DATE THAT IS NOT A DATE OF BIRTH, standing near a person's data. A bare date
# becomes personal by association, and a document word directly before it wins
# over a person elsewhere in the sentence — this is the shape that made every
# invoice date look like a birthday before the association gate existed.
_DATE_TOPICS: tuple[tuple[str, str, str], ...] = (
    ("Счёт от ", " уже отправлен на почту бухгалтерии.",
     "дата счёта, не дата рождения"),
    ("Акт от ", " подпишем при получении.", "дата акта, не дата рождения"),
)


# --- drafts ---------------------------------------------------------------

@dataclass(frozen=True)
class _Slot:
    """One tracked value and everything the ground truth says about it."""

    item_id: str
    type: str
    canonical: str
    identity: str
    duty: str
    tool_param: str | None


@dataclass(frozen=True)
class _Draft:
    """One message before its offsets exist.

    `parts` holds literal strings and `(item_id, surface)` pairs. Offsets are
    computed once, in `_materialize`, by walking this list — never by searching
    the finished string. A search finds the FIRST occurrence, and a message that
    names the same phone twice would then carry a span pointing at the wrong one.
    """

    role: str
    parts: tuple[object, ...]
    slots: tuple[_Slot, ...]
    negatives: tuple[tuple[str, str], ...]


def _compose(role: str, pieces: list[object], register: str,
             rng: random.Random,
             negatives: tuple[tuple[str, str], ...] = ()) -> _Draft:
    """Render one message's literal segments and keep its slots intact.

    THE SLIP LANDS ON AT MOST ONE SEGMENT, AND ONLY IN A USER TURN. RuSpellGold
    counts about one correction per sentence, so slipping every segment would
    build a register nobody writes in; and the assistant is a bot, which does
    not misspell its own policy text. Applying it uniformly would make `sloppy`
    a test of noise tolerance rather than of how people type.
    """
    rendered: list[object] = []
    slots: list[_Slot] = []
    prose_positions: list[int] = []
    for piece in pieces:
        if isinstance(piece, tuple):
            slot, surface = piece
            slots.append(slot)
            rendered.append((slot.item_id, surface))
            continue
        text = _prose(str(piece), register, rng)
        if len(text.strip()) >= 6 and not any(ch.isdigit() for ch in text):
            prose_positions.append(len(rendered))
        rendered.append(text)
    if register == "sloppy" and role == "user" and prose_positions:
        index = rng.choice(prose_positions)
        rendered[index] = _slip(str(rendered[index]), rng)
    return _Draft(role=role, parts=tuple(rendered), slots=tuple(slots),
                  negatives=negatives)


def _draft_length(draft: _Draft) -> int:
    return sum(len(part) if isinstance(part, str) else len(part[1])
               for part in draft.parts)


def _materialize(drafts: list[_Draft]) -> tuple[
        list[dict[str, object]], list[PiiItem], list[Negative]]:
    """Turn drafts into messages, computing every offset during assembly."""
    messages: list[dict[str, object]] = []
    pii: list[PiiItem] = []
    negatives: list[Negative] = []
    for index, draft in enumerate(drafts):
        out: list[str] = []
        spans: dict[str, tuple[int, int]] = {}
        cursor = 0
        for part in draft.parts:
            if isinstance(part, tuple):
                item_id, surface = part
                spans[item_id] = (cursor, cursor + len(surface))
                out.append(surface)
                cursor += len(surface)
            else:
                out.append(part)
                cursor += len(part)
        text = "".join(out)
        messages.append({"role": draft.role, "content": text})
        for slot in draft.slots:
            start, end = spans[slot.item_id]
            pii.append(PiiItem(
                id=slot.item_id, type=slot.type, value=text[start:end],
                start=start, end=end, canonical=slot.canonical, msg=index,
                identity=slot.identity, duty=slot.duty,
                tool_param=slot.tool_param))
        for value, why in draft.negatives:
            negatives.append(Negative(value=value, why=why, msg=index))
    return messages, pii, negatives


# --- value generation -----------------------------------------------------

def _digits(rng: random.Random, count: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(count))


def _phone_digits(rng: random.Random, taken: frozenset[str]) -> str:
    """Ten national digits, never colliding with one already in the case.

    Two people sharing a phone would make the `different` link between them
    unscoreable: the gateway would be right to give one substitute, and the
    ground truth would call that a merge.
    """
    for _ in range(64):
        digits = rng.choice(_PHONE_PREFIXES) + _digits(rng, 7)
        if digits not in taken:
            return digits
    raise RuntimeError("phone pool exhausted; widen _PHONE_PREFIXES")


def _order_id(rng: random.Random, avoid: str) -> str:
    """Four digits, no letters and no «№».

    DIGITS ONLY IS A CONSTRAINT, NOT A STYLE. Every register transform here
    lowercases and strips punctuation from literal segments, so an order id
    carrying a letter would come out of `chat` as a different string from the
    one the negative claims. Digits survive every transform unchanged.

    It also may not appear inside the customer's phone: a negative claiming a
    span inside a gold value makes the over-masking count unreadable.
    """
    for _ in range(64):
        candidate = _digits(rng, 4)
        if candidate not in avoid:
            return candidate
    raise RuntimeError("order id pool exhausted")


def _pick_person(rng: random.Random, taken: frozenset[str]) -> _Person:
    pool = _FOREIGN if rng.random() < 0.25 else _RU_MEN + _RU_WOMEN
    for _ in range(64):
        person = rng.choice(pool)
        if person.surname not in taken:
            return person
        pool = _FOREIGN if rng.random() < 0.25 else _RU_MEN + _RU_WOMEN
    raise RuntimeError("person pool exhausted")


# --- the three oblique shapes ---------------------------------------------
#
# The datum is stated in message 0 and the last user turn refers to it without
# repeating it. Which datum is referred back to is what separates the three, and
# they rotate so that no register cell measures only one of them.
_SCENARIOS: tuple[str, ...] = (
    "late_callback",     # «перезвоните на тот же номер» -> the phone from msg 0
    "late_address",      # «на тот же адрес»             -> the address from msg 0
    "late_short_name",   # «наберите Петру»              -> an inflected short form
)


def _head_pieces(name: str, phone: str, address: str, order: str,
                 register: str, slots: dict[str, _Slot]) -> tuple[
                     list[object], tuple[tuple[str, str], ...]]:
    """Message 0: everything the customer states, once, at the top.

    Returns PIECES rather than a message because the `empty` shape has to fold
    the head and the tail into a single user turn, and composing twice would
    put a message boundary where the shape says there is none.
    """
    name_piece = (slots["name0"], name)
    phone_piece = (slots["phone0"], phone)
    address_piece = (slots["addr0"], address)
    negatives: tuple[tuple[str, str], ...] = (
        () if not order else ((order, "номер заказа"),))
    if register == "clean":
        pieces = ["Здравствуйте! Оформил у вас заказ ", order, " на имя ",
                  name_piece, ", телефон ", phone_piece, ", доставка: ",
                  address_piece, "."]
    elif register in ("chat", "sloppy"):
        pieces = ["здравствуйте оформил заказ ", order, " на ", name_piece,
                  " тел ", phone_piece, " доставка ", address_piece]
    elif register == "voice_itn":
        pieces = ["здравствуйте я оформил заказ ", order, " на ", name_piece,
                  " телефон ", phone_piece, " доставка ", address_piece]
    else:
        # voice_raw: no order number, because a real call transcript carries no
        # digits and spelling a four-digit id out loud is not what people do
        # with it — they say «мой заказ». The `order_id` argument goes with it.
        pieces = ["здравствуйте я оформил у вас заказ на ", name_piece,
                  " телефон ", phone_piece, " доставка ", address_piece]
        negatives = ()
    return pieces, negatives


def _read_back(name: str, phone: str, order: str, register: str,
               rng: random.Random, slots: dict[str, _Slot],
               with_phone: bool) -> _Draft:
    """The agent repeating the customer's own data back at them.

    This is the mention that makes the family's claim testable at all: it is the
    same person written by a different hand, in a different phone format, and
    the product's promise is that both reach the model as ONE substitute.

    At the `short` rung the phone is left out. With it the `voice_raw` case —
    where a phone is seventy characters of words — walks straight out of the
    0-400 band, and a short read-back is what a short exchange actually gets.
    """
    name_piece = (slots["name1"], name)
    pieces: list[object]
    if register == "clean":
        pieces = ["Записал. Заказ ", order, " на ", name_piece]
        if with_phone:
            pieces += [", телефон ", (slots["phone1"], phone)]
        pieces += ["."]
    elif register in ("chat", "sloppy"):
        pieces = ["записал заказ ", order, " на ", name_piece]
        if with_phone:
            pieces += [" телефон ", (slots["phone1"], phone)]
    elif register == "voice_itn":
        pieces = ["записал заказ ", order, " на ", name_piece]
        if with_phone:
            pieces += [" повторяю номер ", (slots["phone1"], phone)]
    else:
        pieces = ["записал заказ на ", name_piece]
        if with_phone:
            pieces += [" повторяю ваш номер ", (slots["phone1"], phone)]
    negatives: tuple[tuple[str, str], ...] = (
        ((order, "номер заказа"),) if order and register != "voice_raw" else ())
    return _compose("assistant", pieces, register, rng, negatives)


def _tail_pieces(scenario: str, person: _Person, register: str,
                 slots: dict[str, _Slot]) -> list[object]:
    """The last user turn. It refers to the datum and never repeats it.

    Except in `late_short_name`, where what it repeats is a SHORT INFLECTED form
    — «наберите Петру». That mention is its own item and its canonical is the
    nominative, because turning a declined mention back into the form a CRM
    stores is the gateway's job and the one CLAUDE.md records as having reached
    a customer's system wrong.
    """
    if scenario == "late_callback":
        if register == "clean":
            pieces: list[object] = [
                "Перезвоните мне, пожалуйста, на тот же номер — я весь день на связи."]
        elif register in ("chat", "sloppy"):
            pieces = ["перезвоните на тот же номер пожалуйста я весь день на связи"]
        else:
            pieces = ["и перезвоните мне на тот же номер пожалуйста я весь день на связи"]
        return pieces
    if scenario == "late_address":
        if register == "clean":
            pieces = ["Доставьте, пожалуйста, на тот же адрес, "
                      "что я назвал в начале, только в субботу."]
        elif register in ("chat", "sloppy"):
            pieces = ["доставьте на тот же адрес что я назвал в начале только в субботу"]
        else:
            pieces = ["и доставьте на тот же адрес что я называл в начале только в субботу"]
        return pieces
    dative = person.dative if register == "clean" else person.dative.lower()
    piece = (slots["late_name"], dative)
    if register == "clean":
        pieces = ["И наберите ", piece, ", пожалуйста, после шести."]
    elif register in ("chat", "sloppy"):
        pieces = ["и наберите ", piece, " после шести пожалуйста"]
    else:
        pieces = ["и наберите ", piece, " после шести пожалуйста"]
    return pieces


# --- distractors ----------------------------------------------------------
#
# OTHER PEOPLE'S DATA, in the middle of the transcript. Without them a long case
# only asks whether one substitute survives; with them it also asks whether the
# gateway kept three people apart over sixteen thousand characters, which is the
# failure that reaches a real human being who was never part of the conversation.

def _courier_block(name: str, phone: str, register: str, rng: random.Random,
                   slots: dict[str, _Slot]) -> list[_Draft]:
    question = "Курьер сам позвонит перед приездом?"
    name_piece = (slots["courier_name"], name)
    phone_piece = (slots["courier_phone"], phone)
    if register == "clean":
        reply: list[object] = ["Да, курьер ", name_piece,
                               " наберёт вас за час, его номер ", phone_piece, "."]
    elif register in ("chat", "sloppy"):
        reply = ["да курьер ", name_piece, " наберёт за час его номер ", phone_piece]
    elif register == "voice_itn":
        reply = ["да курьер ", name_piece, " наберёт вас за час его номер ", phone_piece]
    else:
        reply = ["да курьер ", name_piece, " наберёт вас за час его номер ", phone_piece]
    return [_compose("user", [question], register, rng),
            _compose("assistant", reply, register, rng)]


def _colleague_block(name: str, register: str, rng: random.Random,
                     slots: dict[str, _Slot]) -> list[_Draft]:
    piece = (slots["colleague_name"], name)
    if register == "clean":
        question: list[object] = ["Если меня не будет дома, заказ примет коллега ",
                                  piece, "."]
    else:
        question = ["если меня не будет дома заказ примет коллега ", piece]
    reply = ["Хорошо, отметил это в заказе. Курьер спросит номер заказа у того, "
             "кто откроет дверь."]
    return [_compose("user", question, register, rng),
            _compose("assistant", reply, register, rng)]


def _bare_street_block(surface: str, register: str, rng: random.Random,
                       slots: dict[str, _Slot]) -> list[_Draft]:
    piece = (slots["opt_street"], surface)
    if register == "clean":
        question: list[object] = ["Мой офис на ", piece,
                                  ", если что, могу забрать сам."]
    else:
        question = ["мой офис на ", piece, " если что могу забрать сам"]
    reply = ["Самовывоз тоже доступен, пункт выдачи работает до девяти вечера."]
    return [_compose("user", question, register, rng),
            _compose("assistant", reply, register, rng)]


def _dealer(pool: tuple[str, ...],
            rng: random.Random) -> Callable[[int], list[str]]:
    """Deal from a shuffled bag, reshuffling when it empties.

    NOT `rng.choice`, and the difference is visible in a long case. A 16 500
    character transcript draws about 190 sentences; sampling with replacement
    from 52 gave one sentence NINE times in a single conversation, which reads
    as padding and earns the criticism that the length is fake. A bag caps every
    sentence at ceil(draws / pool) and spends the pool evenly.

    The bag is local to one case and closed over, which is why this is not
    global state: two cases built from the same rng deal the same order.
    """
    bag: list[str] = []

    def deal(count: int) -> list[str]:
        nonlocal bag
        out: list[str] = []
        while len(out) < count:
            if not bag:
                bag = list(pool)
                rng.shuffle(bag)
            out.append(bag.pop())
        return out

    return deal


def _filler_exchange(register: str, rng: random.Random, rung: str,
                     with_number: bool,
                     deal_question: Callable[[int], list[str]],
                     deal_sentence: Callable[[int], list[str]]) -> list[_Draft]:
    """One ordinary support exchange: a short question, a policy answer.

    `with_number` seeds a negative. It is refused in `voice_raw` because a real
    call transcript carries no digits at all — 0 of 12 950 measured — and a
    number topic there would be a `chat` case wearing a voice label, which is
    the exact confusion the register split exists to end.
    """
    question = deal_question(1)[0]
    low, high = _REPLY_SENTENCES[rung]
    reply = " ".join(deal_sentence(rng.randint(low, high)))
    drafts = [_compose("user", [question], register, rng)]
    if not with_number:
        drafts.append(_compose("assistant", [reply], register, rng))
        return drafts
    if register in ("clean", "chat", "sloppy") and rng.random() < 0.35:
        before, after, why = rng.choice(_DATE_TOPICS)
        value = (f"{rng.randrange(1, 29):02d}.{rng.randrange(1, 13):02d}."
                 f"{rng.choice((2025, 2026))}")
    else:
        before, after, width, why = rng.choice(_NUMBER_TOPICS)
        value = _digits(rng, width)
    drafts.append(_compose("assistant", [reply + " ", before, value, after],
                           register, rng, ((value, why),)))
    return drafts


# --- the case -------------------------------------------------------------

def _slots_for(person: _Person, name: str, phone_digits: str, address: str,
               courier_name: str, courier_digits: str, colleague_name: str,
               opt_street: str, opt_street_nominative: str, register: str,
               scenario: str) -> dict[str, _Slot]:
    """Every tracked value's ground truth, decided before a character is written.

    CANONICAL IS THE FORM AS WRITTEN, except where an oblique case was written
    on purpose. A register drops parts — a messenger drops the patronymic, a
    call drops the surname — and it never inflects, so what was written IS the
    canonical form of what was written. v1 reconstructed it by matching clean
    parts against the surface and thereby deleted from the ground truth every
    part a register had touched: «Иванов Петр», with е for ё, demanded «Иванов»
    back. 162 of its 183 sloppy round-trip failures were that, not the gateway.

    The phone is the exception in the other direction, and only where it has
    digits: «8 916…» and «+7 916…» are one subscriber, `canonicalize` collapses
    them, and the CRM stores the +7 form. In `voice_raw` there are no digits to
    collapse, so the surface stands and the round trip does not ask for it.
    """
    spoken_phone = register == "voice_raw"
    phone_canonical = (_spell_phone(phone_digits) if spoken_phone
                       else f"+7{phone_digits}")
    courier_canonical = (_spell_phone(courier_digits) if spoken_phone
                         else f"+7{courier_digits}")
    name_param = ("recipient_name" if scenario == "late_address"
                  else "customer_name")
    return {
        "name0": _Slot("name0", "NAME", name, "cust_name", "required", name_param),
        # A later mention of the same person is a mention to be masked, not the
        # argument: the agent builds the call from the first, full statement.
        "name1": _Slot("name1", "NAME", name, "cust_name", "required", None),
        # `update_delivery_address` has no phone parameter, so in that
        # scenario the phone is stated, must be masked, and is consumed by
        # nothing. Claiming a param the offered tool does not declare would make
        # the round trip demand a value the contract has nowhere to put.
        "phone0": _Slot("phone0", "PHONE", phone_canonical, "cust_phone",
                        "required",
                        None if spoken_phone or scenario == "late_address"
                        else "phone"),
        "phone1": _Slot("phone1", "PHONE", phone_canonical, "cust_phone",
                        "required", None),
        "addr0": _Slot("addr0", "LOC", address, "cust_addr", "required",
                       "address" if scenario == "late_address" else None),
        # The inflected short form. Its canonical is the nominative given name —
        # this is the one place in the family where the gateway is asked to
        # UNDO a case, and it is asked because «позвоните Игорю» coming back as
        # «Игорю» is a declined name written into a customer's CRM.
        "late_name": _Slot("late_name", "NAME", person.given, "cust_name",
                           "required", "customer_name"),
        "courier_name": _Slot("courier_name", "NAME", courier_name,
                              "courier_name", "required", None),
        "courier_phone": _Slot("courier_phone", "PHONE", courier_canonical,
                               "courier_phone", "required", None),
        "colleague_name": _Slot("colleague_name", "NAME", colleague_name,
                                "colleague_name", "required", None),
        # `optional` is a legal category, not doubt: a street with no house
        # number identifies nobody, so masking it is not an error and missing it
        # is not a leak. It may never claim a tool param — `validate` refuses
        # that pairing, and rightly: a value the round trip demands back cannot
        # also be one we declared safe to leave alone.
        "opt_street": _Slot("opt_street", "LOC", opt_street_nominative,
                            "opt_street", "optional", None),
    }


def _build_case(rng: random.Random, rung: str, register: str,
                index: int) -> Case:
    scenario = _SCENARIOS[index % len(_SCENARIOS)]
    # `empty` and `small` are the two shapes of the short rung. The empty one is
    # a single message — the datum stated and consumed with no context at all —
    # and it is the control arm that makes a drop at `long` attributable to
    # length rather than to the scenario.
    empty = rung == "short" and index % 2 == 0

    person = _pick_person(rng, frozenset())
    courier = _pick_person(rng, frozenset({person.surname}))
    colleague = _pick_person(rng, frozenset({person.surname, courier.surname}))
    phone_digits = _phone_digits(rng, frozenset())
    courier_digits = _phone_digits(rng, frozenset({phone_digits}))
    city = rng.choice(_CITIES)
    street = rng.choice(_STREETS)
    other_street = rng.choice([s for s in _STREETS if s != street])
    house, flat = rng.randrange(1, 90), rng.randrange(1, 250)
    order = "" if register == "voice_raw" else _order_id(rng, phone_digits)

    name = _render_name(person, register, rng)
    phone = _render_phone(phone_digits, register, rng)
    echo_phone = _render_echo_phone(phone_digits, register)
    address = _render_address(city, street, house, flat, register, rng)
    courier_name = _render_name(courier, register, rng)
    courier_phone = _render_phone(courier_digits, register, rng)
    colleague_name = _render_name(colleague, register, rng)
    opt_street = _render_bare_street(other_street, register)

    slots = _slots_for(person, name, phone_digits, address, courier_name,
                       courier_digits, colleague_name, opt_street,
                       other_street, register, scenario)

    head_pieces, head_negatives = _head_pieces(name, phone, address, order,
                                               register, slots)
    tail_pieces = _tail_pieces(scenario, person, register, slots)
    if empty:
        # ONE MESSAGE, head and tail folded together. The oblique reference then
        # points at a value stated in the same turn, which is the control the
        # other two rungs are read against: a drop at `long` means length, not
        # scenario, only if the same scenario holds at zero context.
        drafts: list[_Draft] = [_compose(
            "user", head_pieces + [" "] + tail_pieces, register, rng,
            head_negatives)]
        tail = None
    else:
        drafts = [_compose("user", head_pieces, register, rng, head_negatives)]
        drafts.append(_read_back(name, echo_phone, order, register, rng, slots,
                                 with_phone=rung != "short"))
        tail = _compose("user", tail_pieces, register, rng)

    if rung != "short":
        pending: list[list[_Draft]] = [
            _courier_block(courier_name, courier_phone, register, rng, slots),
            _colleague_block(colleague_name, register, rng, slots),
            _bare_street_block(opt_street, register, rng, slots),
        ]
        thresholds = [0.2, 0.5, 0.78]
        budget = (_TARGET[rung] - sum(_draft_length(d) for d in drafts)
                  - _draft_length(tail)
                  - sum(_draft_length(d) for block in pending for d in block))
        deal_question = _dealer(_QUESTIONS, rng)
        deal_sentence = _dealer(_SENTENCES, rng)
        written = 0
        step = 0
        while written < budget:
            block = _filler_exchange(register, rng, rung,
                                     step % 4 == 3 and register != "voice_raw",
                                     deal_question, deal_sentence)
            drafts.extend(block)
            written += sum(_draft_length(d) for d in block)
            step += 1
            while pending and thresholds and written >= budget * thresholds[0]:
                drafts.extend(pending.pop(0))
                thresholds.pop(0)
        for block in pending:
            drafts.extend(block)
        # A repeated, IDENTICAL assistant line: the mask cache's hit path, which
        # a corpus of unique messages never touches. It carries no personal data
        # on purpose — what is being exercised is the content key, not recall.
        drafts.append(_compose(
            "assistant", ["Секунду, уточняю по вашему заказу."], register, rng))
        drafts.append(_compose(
            "user", ["Хорошо, жду."], register, rng))
        drafts.append(_compose(
            "assistant", ["Секунду, уточняю по вашему заказу."], register, rng))
    if tail is not None:
        drafts.append(tail)

    # A slot that no draft used must not become a ground-truth item claiming a
    # span in a message it is not in. The dict above is the FULL inventory; the
    # drafts decide which of it was written, and `_materialize` reads the spans
    # off the drafts, so an unused slot simply never appears.
    messages, pii, negatives = _materialize(drafts)
    by_id = {item.id: item for item in pii}

    primary = ("update_delivery_address" if scenario == "late_address"
               else "escalate_ticket")
    consumed = [item_id for item_id in
                ("name0", "addr0", "phone0", "late_name")
                if item_id in by_id and by_id[item_id].tool_param]
    arguments: dict[str, str | int | float] = {}
    for item_id in consumed:
        item = by_id[item_id]
        # `late_name` and `name0` feed the SAME argument, and both are checked
        # against it: the agent assembles one name from what the dialogue said,
        # so a half that comes back as somebody else is a wrong call even when
        # the other half is perfect.
        if item.tool_param not in arguments:
            arguments[str(item.tool_param)] = item.canonical
    if order:
        arguments["order_id"] = order
    if primary == "escalate_ticket" and "phone" not in arguments:
        # voice_raw: the phone is stated and must be masked, but nothing we have
        # turns words into a dialable number, so the corpus states the value the
        # tool ought to receive WITHOUT demanding the round trip for it.
        arguments["phone"] = by_id["phone0"].canonical

    calls = [ExpectedCall(name=primary, after_msg=len(messages) - 1,
                          arguments=arguments, pii_items=consumed)]

    links: list[LinkExpectation] = []
    for identity, why in (("cust_name", "один клиент, названный дважды — "
                                        "одна подмена"),
                          ("cust_phone", "один номер в двух форматах — "
                                         "одна подмена")):
        mentions = [item.id for item in pii if item.identity == identity]
        if len(mentions) >= 2:
            links.append(LinkExpectation(left=mentions[0], right=mentions[-1],
                                         kind="same", case="", why=why))
    if "courier_name" in by_id:
        links.append(LinkExpectation(
            left="name0", right="courier_name", kind="different", case="",
            why="клиент и курьер — разные люди, слияние отдало бы данные "
                "одного другому"))
    if "opt_street" in by_id:
        links.append(LinkExpectation(
            left="addr0", right="opt_street", kind="unjudged", case="",
            why="улицу без номера дома маскировать не обязательно, поэтому "
                "пары подмен может не быть вовсе"))

    # BOTH SCOPE FORMS, alternating. Being handed a conversation id and deriving
    # one from the transcript are different code paths, and the derived one is
    # what a customer gateway with no conversation field actually triggers.
    # `conversation_key` reads the first TWO messages, so an `empty` case — one
    # message — exercises the weakest form of it, which is the point.
    conversation = ("" if index % 4 in (1, 2) else
                    f"conv-length-{rung}-{register}-{index:03d}")

    return Case(
        id=f"length-{rung}-{register}-{index:03d}",
        family=FAMILY,
        scenario=f"{scenario}_{'empty' if empty else rung}",
        register=register,
        difficulty=DIFFICULTY,
        length_rung=rung,
        conversation_id=conversation,
        relation="equality",
        messages=messages,
        tools=_tools_for(primary),
        pii=pii,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        negatives=negatives,
        links=links,
        calls=calls,
    )


# The fifteen cells of this family, walked diagonally. 3 and 5 are coprime, so
# `(RUNGS[i % 3], REGISTERS[i % 5])` enumerates all fifteen exactly once — and
# any PREFIX of that walk is balanced: k cases cover the rungs k/3 apart and the
# registers k/5 apart. A truncated run therefore stays estimable instead of
# being three rungs of one register, which is what `--limit` did to v1.
_REGISTERS: tuple[str, ...] = (
    "clean", "chat", "sloppy", "voice_itn", "voice_raw")
_CELLS: tuple[tuple[str, str], ...] = tuple(
    (RUNGS[i % len(RUNGS)], _REGISTERS[i % len(_REGISTERS)])
    for i in range(len(RUNGS) * len(_REGISTERS)))


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases of the `length` family, balanced over rung x register.

    Deterministic from `rng` alone: every draw goes through it and nothing reads
    a clock, an environment variable or the filesystem. The design size is 150
    (3 rungs x 5 registers x 10), which is `_CELLS` walked ten times.
    """
    if count < 0:
        raise ValueError(f"count must not be negative, got {count}")
    cases: list[Case] = []
    for position in range(count):
        rung, register = _CELLS[position % len(_CELLS)]
        cases.append(_build_case(rng, rung, register,
                                 position // len(_CELLS)))
    return cases


def main() -> int:
    """Build the design size and check it against the schema.

    A generator whose spans disagree with its own text keeps producing numbers,
    and the numbers are false — so this runs `validate` rather than eyeballing
    the output, and it is the thing to run after editing a template.

        python3 -m bench.agentpii2.families.context
    """
    from bench.agentpii2.schema import case_characters, validate

    cases = build(random.Random(20260830), 150)
    problems = [problem for case in cases for problem in validate(case)]
    for problem in problems[:20]:
        print(f"  {problem}")
    print(f"случаев:      {len(cases)}")
    print(f"размеченных:  {sum(len(c.pii) for c in cases)} "
          f"(обязательных {sum(1 for c in cases for i in c.pii if i.duty == 'required')})")
    print(f"негативов:    {sum(len(c.negatives) for c in cases)}")
    print(f"связей:       {sum(len(c.links) for c in cases)}")
    for rung in RUNGS:
        sizes = [case_characters(c) for c in cases if c.length_rung == rung]
        counts = [len(c.messages) for c in cases if c.length_rung == rung]
        print(f"  {rung:<7} {len(sizes)} шт, {min(sizes)}-{max(sizes)} символов, "
              f"{min(counts)}-{max(counts)} сообщений")
    print(f"проблем:      {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
