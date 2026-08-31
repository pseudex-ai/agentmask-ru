"""AgentPII-RU v2 — `indirect`: the datum the customer never states.

«на какой адрес я заказал в прошлый раз», «перезвоните мне на тот же номер»,
«оформите как в прошлый раз». Nobody writes the address down. The agent looks it
up, the customer's own CRM hands it back, it is masked ON THE WAY TO THE MODEL,
the model puts the substitute into `update_delivery_address`, and the real value
has to arrive at the tool.

WHY THIS IS A FAMILY AND NOT A SCENARIO. Every earlier set of ours — v1 in full,
`make_dataset`, `make_dirty` — puts the gold value in the USER's text, so the
round trip only ever walks `user -> model -> tool`. Here the path is
`tool -> model -> tool`, and it shares no code with the first one except the
vault: the value never passed through the normalisation the user leg applies, so
a fold that repairs a Cyrillic О inside a phone, or a canonicalisation that reads
an oblique case, has simply not run on it. A gateway can be perfect on the user
leg and lose this one.

THREE THINGS THIS FAMILY REFUSES TO DO, each because the alternative measures
something else:

  * **the lookup key is never personal data.** The customer cites an ORDER
    NUMBER, and the assistant's lookup call carries that. Keying the lookup on
    the caller's phone would put a user-stated value back in the case and quietly
    turn half the family into `transfer` wearing a new name.
  * **the CRM does not speak the customer's register.** `voice_raw` is how the
    CALLER reaches us; a support system does not start writing house numbers in
    words because the customer phoned instead of typed. The register acts on the
    user's turns and on the partial mention — which is where it decides whether
    linking fires at all — and the tool result stays wire-form JSON in every one.
  * **the partial mention is generated from the record, never matched against
    it.** «на ленина, как обычно» is derived from the address the CRM will
    return, so the pair is the same place by construction. Searching a finished
    record for a street the template happened to use would make the ground truth
    depend on a string search, which is the defect v1's `_canonical_name` shipped.

THE PARTIAL MENTION IS THE POINT OF HALF THE SHAPES. «на Ленина, как обычно»
carries a street and no house number: legally it identifies nobody (152-ФЗ ст. 3
п. 1 — hundreds of buildings stand on it), so its `duty` is `optional` and it may
claim no `tool_param`. What it CAN claim is a `LinkExpectation`: the gateway must
resolve it against the fuller address that came back from the tool, inside this
one conversation, or the model sees two unrelated places and answers about the
wrong one. That is `_linked_place`'s reason to exist, and until now nothing but a
unit test has exercised it from a tool result.

`identity` AND `LinkExpectation` SAY DIFFERENT THINGS HERE, and the difference
is what a scorer has to respect. `identity` groups mentions that carry the SAME
information and must therefore receive the same substitute — this family gives
every item its own, because no two mentions in it are the same string. A `same`
link is the weaker and more interesting claim: two mentions at DIFFERENT
granularity that name one referent, «ленина» against «125077, Москва, улица
Ленина, дом 14, квартира 8». The gateway is not being asked to hand back one
identical string for both; it is being asked to resolve the shorter against the
longer inside this conversation, so that the street the model reads in the
partial mention is the street of the address it already saw. Scoring a `same`
link by string equality of substitutes would fail a correct gateway, and scoring
it by nothing would let a real merge hide there.

`asr_digits` IS SET ON EVERY `voice_raw` CASE HERE, and that is not a way around
the register gate. The gate scans `user` AND `tool` messages together, and a tool
message is a CRM record: it carries digits because CRMs do. The two honest
alternatives are worse — spelling the CRM's house number in words invents a
system no vendor ships, and dropping the house number turns every `voice_raw`
address case into an `optional` one, deleting the family's required PII in the
register that needs it most. So the flag is declared and a STRICTER local rule
takes over: a `voice_raw` user turn built here may not contain a digit at all,
and `_declare_asr_digits` raises if one appears.
"""

import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass

from bench.agentpii2.schema import (
    REGISTERS,
    Case,
    ExpectedCall,
    LinkExpectation,
    Negative,
    PiiItem,
    ToolSchema,
)

FAMILY = "indirect"

# Two forms, from the design doc: the datum that comes back is a PLACE or a
# PERSON. They fail differently — an address is a long string the model may
# re-format on its way into an argument, a name is a short one the model may
# decline — so a family that mixed them would report one number for two defects.
ADDRESS_SHAPES: tuple[str, ...] = (
    "repeat_delivery",   # nothing is stated: the record is the only source
    "partial_street",    # «на ленина, как обычно» — street, no house: optional
    "two_orders",        # two records come back; a partial mention picks one
)
PERSON_SHAPES: tuple[str, ...] = (
    "callback_same_number",  # the phone is in the record and nowhere else
    "same_recipient",        # name + phone + email, three params, one call
    "partial_person",        # «да, Марии» — a declined given name links back
)


# --- pools ----------------------------------------------------------------
#
# Authored from what a Russian support conversation contains. Overlap with the
# leased gazetteer is unavoidable (Russian names are Russian names) but no entry
# is here BECAUSE we detect it.
#
# The fourth element is the Latin stem the CRM would build a mailbox from. It is
# stored rather than transliterated: a transliteration function is a second thing
# that can be wrong, and it would put «fyodorov» or «fedorov» into ground truth
# depending on a rule nobody checked. The fifth is grammatical gender, and it is
# here because the templates carry a pronoun — «ей и звоните» about a man is a
# sentence no Russian speaker produces, and a corpus that ships it is testing the
# gateway on text from outside the language it claims to measure. Foreign names
# are exactly where a rule would fail, which is why this is a table too.

MALE: tuple[tuple[str, str, str, str, str], ...] = (
    ("Иванов", "Пётр", "Сергеевич", "ivanov", "m"),
    ("Соколов", "Игорь", "Валентинович", "sokolov", "m"),
    ("Кузнецов", "Дмитрий", "Андреевич", "kuznetsov", "m"),
    ("Морозов", "Алексей", "Николаевич", "morozov", "m"),
    ("Волков", "Сергей", "Павлович", "volkov", "m"),
    ("Лебедев", "Максим", "Олегович", "lebedev", "m"),
    ("Новиков", "Артём", "Витальевич", "novikov", "m"),
    ("Фёдоров", "Кирилл", "Романович", "fedorov", "m"),
)
FEMALE: tuple[tuple[str, str, str, str, str], ...] = (
    ("Иванова", "Мария", "Львовна", "ivanova", "f"),
    ("Соколова", "Анна", "Игоревна", "sokolova", "f"),
    ("Кузнецова", "Ольга", "Дмитриевна", "kuznetsova", "f"),
    ("Морозова", "Екатерина", "Сергеевна", "morozova", "f"),
    ("Лебедева", "Ирина", "Петровна", "lebedeva", "f"),
    ("Новикова", "Светлана", "Юрьевна", "novikova", "f"),
    ("Фёдорова", "Юлия", "Андреевна", "fedorova", "f"),
)
# Hostile to suffix rules on purpose: no -ов/-ев/-ин on most of them, several
# non-Slavic, one indeclinable given name («Ань»). Drawn at a flat rate in every
# shape rather than concentrated anywhere — a shop's foreign customers are not an
# adversarial case, they are Tuesday, and hiding them in one corner would let a
# summary number look healthy over the population it fails on.
FOREIGN: tuple[tuple[str, str, str, str, str], ...] = (
    ("Ким", "Виктор", "", "kim", "m"),
    ("Тагиев", "Рустам", "", "tagiev", "m"),
    ("Мкртчян", "Ашот", "", "mkrtchyan", "m"),
    ("Гулиев", "Эльдар", "", "guliev", "m"),
    ("Абдуллаев", "Тимур", "", "abdullaev", "m"),
    ("Саркисян", "Карен", "", "sarkisyan", "m"),
    ("Нгуен", "Ань", "", "nguyen", "f"),
    ("Мамедова", "Лейла", "", "mamedova", "f"),
    ("Валиахметов", "Ильдар", "", "valiahmetov", "m"),
    ("Джонсон", "Майкл", "", "johnson", "m"),
    ("Ли", "Чен", "", "li", "m"),
)
FOREIGN_SHARE = 0.3

# The dative of every given name above, written out rather than derived. Russian
# given names have irregulars («Пётр» → «Петру», not «Пётру») and indeclinables
# («Ань»), and a rule that gets one wrong puts a form nobody writes into GROUND
# TRUTH, where it is scored as if it were real Russian. A table is checkable by a
# native speaker in ten seconds; a rule is not.
DATIVE: dict[str, str] = {
    "Пётр": "Петру", "Игорь": "Игорю", "Дмитрий": "Дмитрию", "Алексей": "Алексею",
    "Сергей": "Сергею", "Максим": "Максиму", "Артём": "Артёму", "Кирилл": "Кириллу",
    "Мария": "Марии", "Анна": "Анне", "Ольга": "Ольге", "Екатерина": "Екатерине",
    "Ирина": "Ирине", "Светлана": "Светлане", "Юлия": "Юлии",
    "Виктор": "Виктору", "Рустам": "Рустаму", "Ашот": "Ашоту", "Эльдар": "Эльдару",
    "Тимур": "Тимуру", "Карен": "Карену", "Ань": "Ань", "Лейла": "Лейле",
    "Ильдар": "Ильдару", "Майкл": "Майклу", "Чен": "Чену",
}

# Street names that do not decline in the shapes below: «улица Ленина» keeps
# «Ленина» wherever it stands, so the partial mention can be built by dropping
# the type word and nothing else. «Ленинский проспект» would need a case form and
# would put a second variable — declension — into a family that is measuring
# linking, not morphology.
STREETS: tuple[tuple[str, str], ...] = (
    ("улица Ленина", "Ленина"), ("улица Пушкина", "Пушкина"),
    ("улица Гагарина", "Гагарина"), ("улица Чехова", "Чехова"),
    ("улица Лермонтова", "Лермонтова"), ("улица Некрасова", "Некрасова"),
    ("улица Кирова", "Кирова"), ("улица Толстого", "Толстого"),
    ("улица Строителей", "Строителей"), ("улица Космонавтов", "Космонавтов"),
)
# City with its real postal-index prefix. Paired rather than drawn apart: an
# index is part of the address string the round trip demands back verbatim, and
# «628352, Самара» is a value no CRM in the country holds. The corpus is allowed
# to invent a customer; inventing a geography puts an impossible string into
# ground truth and makes a plausible repair by the gateway look like damage.
CITIES: tuple[tuple[str, str], ...] = (
    ("Москва", "125"), ("Санкт-Петербург", "190"), ("Казань", "420"),
    ("Екатеринбург", "620"), ("Новосибирск", "630"), ("Краснодар", "350"),
    ("Самара", "443"), ("Нижний Новгород", "603"), ("Пермь", "614"),
    ("Воронеж", "394"),
)
# Real Russian mobile prefixes: a phone that libphonenumber refuses is a phone
# our own ground truth invented, and the miss would be the corpus's.
MOBILE_PREFIXES: tuple[str, ...] = ("916", "926", "903", "985", "917", "999", "905")


# --- numerals, for the register that has no digits ------------------------
#
# Measured on OpenSTT `asr_calls_2_val`, 12 950 human transcripts of real Russian
# phone calls: zero contain a digit, 9.1% contain a number written out. The
# templates below are built on what those transcripts actually look like —
# «улица лермонтова тридцать восемь», «дом восемьдесят», «сорок один ноль девять
# шестьдесят семь это наш телефон» — not on a belief about what ASR emits.

_ONES: tuple[str, ...] = (
    "ноль", "один", "два", "три", "четыре",
    "пять", "шесть", "семь", "восемь", "девять",
)
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS: tuple[str, ...] = (
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят",
    "шестьдесят", "семьдесят", "восемьдесят", "девяносто",
)


def _spell_number(value: int) -> str:
    """A house number as a caller says it. Masculine — «дом один», «дом два».

    Only ever applied to house numbers, never to flats: «квартира одна» and
    «квартира один» are both heard, and a corpus that picked one would be
    asserting a fact about Russian that no corpus of ours measured.
    """
    if value < 10:
        return _ONES[value]
    if value < 20:
        return _TEENS[value - 10]
    tens, ones = divmod(value, 10)
    return _TENS[tens] if not ones else f"{_TENS[tens]} {_ONES[ones]}"


def _spell_digits(digits: str) -> str:
    """An order number read out one digit at a time, the way people read codes."""
    return " ".join(_ONES[int(digit)] for digit in digits)


# --- writing errors -------------------------------------------------------
#
# The distribution is RuSpellGold's (RussianNLP, Apache 2.0, 1711 human-corrected
# pairs, 2112 corrections): one-letter substitution 950 — of which ё→е is 499 —
# then a dropped letter 626, then a stray character 463. The Latin layout slip is
# kept as the minority it is: vivid, and hardly present in edited text.

_PHONETIC: tuple[tuple[str, str], ...] = (
    ("ё", "е"), ("ё", "е"), ("ё", "е"),
    ("а", "о"), ("и", "е"), ("о", "а"), ("е", "и"),
    ("о", "у"), ("я", "и"), ("т", "д"), ("з", "с"),
)
_LATIN_TWINS: dict[str, str] = {
    "о": "o", "а": "a", "е": "e", "с": "c", "р": "p", "у": "y", "х": "x",
}


def _one_error(text: str, rng: random.Random) -> str:
    """One realistic writing error in a literal chunk of a message.

    Applied BEFORE assembly, never after. A pass over a finished message changes
    its length and silently invalidates every span already computed against it —
    the corpus keeps scoring, and scores wrongly.
    """
    roll = rng.random()
    if roll < 0.45:
        for source, target in rng.sample(_PHONETIC, len(_PHONETIC)):
            positions = [i for i, ch in enumerate(text) if ch == source]
            if positions:
                index = rng.choice(positions)
                return text[:index] + target + text[index + 1:]
        return text
    if roll < 0.75:
        positions = [i for i, ch in enumerate(text) if ch.isalpha() and i > 0]
        if not positions:
            return text
        index = rng.choice(positions)
        return text[:index] + text[index + 1:]
    if roll < 0.90:
        positions = [i for i, ch in enumerate(text) if ch == " " and i > 0]
        if not positions:
            return text
        index = rng.choice(positions)
        return text[:index] + text[index + 1:]
    positions = [i for i, ch in enumerate(text) if ch in _LATIN_TWINS]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + _LATIN_TWINS[text[index]] + text[index + 1:]


def _spoil_literals(parts: list[object], rng: random.Random) -> list[object]:
    """One error, in one literal chunk. Tracked slots are never touched here.

    A slot's text IS the ground truth, so an error inside it has to move the
    canonical form with it — that is `_spoil_pair`'s job and it needs both
    strings. Spoiling a slot from here would leave the ground truth claiming a
    spelling the message no longer carries.
    """
    candidates = [i for i, part in enumerate(parts)
                  if isinstance(part, str) and len(part.strip()) >= 8]
    if not candidates:
        return parts
    index = rng.choice(candidates)
    spoiled = list(parts)
    spoiled[index] = _one_error(str(parts[index]), rng)
    return spoiled


def _spoil_pair(surface: str, canonical: str,
                rng: random.Random) -> tuple[str, str]:
    """One error applied to BOTH forms, at a position they share.

    A typo the customer made lives in the word they wrote AND in the canonical
    form of the word they wrote: «Мрии» is the dative of «Мрия», not of «Мария».
    Spoiling only the surface would demand the repaired spelling back — the exact
    defect that made 162 of v1's 183 sloppy round-trip failures the corpus's own
    rather than the gateway's.

    The edit is confined to the COMMON PREFIX (compared case-insensitively, since
    a messenger lower-cases the surface and a CRM does not), which is the stem the
    two forms share. Outside it the two strings differ and the same edit would
    mean two different words.
    """
    limit = 0
    for left, right in zip(surface.casefold(), canonical.casefold()):
        if left != right:
            break
        limit += 1
    if limit < 2:
        return surface, canonical
    stem = surface[:limit]
    if "ё" in stem.casefold():
        index = stem.casefold().index("ё")
    else:
        index = rng.randrange(1, limit)
    if surface[index].casefold() == "ё":
        return (surface[:index] + "е" + surface[index + 1:],
                canonical[:index] + "е" + canonical[index + 1:])
    return (surface[:index] + surface[index + 1:],
            canonical[:index] + canonical[index + 1:])


# --- assembly -------------------------------------------------------------
#
# One message in wire form, and the offsets of the values inside it. Named
# aliases because both travel together through every builder below and the
# inline forms pushed the signatures past the point of being readable.

_Message = dict[str, object]
_Spans = dict[str, tuple[int, int]]

def assemble(parts: list[object]) -> tuple[str, _Spans]:
    """Build a message and the offsets of its tracked slots in one pass.

    A plain `str` is literal text; a `(name, value)` tuple is a slot whose span is
    recorded. Offsets are computed DURING assembly and never by searching the
    finished string: a search finds the first occurrence, and a record that names
    the same street twice would then carry a span pointing at the wrong one.
    """
    out: list[str] = []
    spans: _Spans = {}
    cursor = 0
    for part in parts:
        if isinstance(part, tuple):
            name, value = part
            if name in spans:
                raise ValueError(f"slot {name!r} assembled twice")
            spans[str(name)] = (cursor, cursor + len(str(value)))
            out.append(str(value))
            cursor += len(str(value))
        else:
            text = str(part)
            out.append(text)
            cursor += len(text)
    return "".join(out), spans


def _object_parts(fields: tuple[tuple[str, object], ...]) -> list[object]:
    """Wire-form JSON as assembly parts, so a value's span is known as it is written.

    The record is serialised HERE rather than by `json.dumps` at score time,
    because the envelope's `content` is a string and masking runs over it flat: a
    scorer that chose its own separators would move every offset in the family.
    Validity is not assumed — `_tool_message` parses the finished string back.
    """
    parts: list[object] = ["{"]
    for index, (key, value) in enumerate(fields):
        if index:
            parts.append(", ")
        parts.append(f'"{key}": "')
        parts.append(value)
        parts.append('"')
    parts.append("}")
    return parts


def _array_parts(records: tuple[list[object], ...]) -> list[object]:
    parts: list[object] = ["["]
    for index, record in enumerate(records):
        if index:
            parts.append(", ")
        parts.extend(record)
    parts.append("]")
    return parts


def _tool_message(call_id: str, parts: list[object]) -> tuple[_Message, _Spans]:
    """A tool result message, with its slot offsets, checked to be real JSON."""
    text, spans = assemble(parts)
    json.loads(text)          # a hand-built record that does not parse is a bug
    return {"role": "tool", "tool_call_id": call_id, "content": text}, spans


def _call_message(call_id: str, name: str,
                  arguments: dict[str, str]) -> _Message:
    """The assistant's lookup call.

    It is SCRIPTED, and the corpus says so: a replay harness lets the model make
    this call itself and injects the tool result; an offline scorer masks the
    transcript as it stands. Either way its arguments carry no personal data —
    the lookup key is an order number — so nothing here can leak by being
    replayed as written.

    IT PASSES THE NUMBER AS THE CUSTOMER SAID IT, not as the CRM stores it. On
    the phone that is «один пять ноль четыре»; the record answers with «A-1504».
    Demanding the stored form here would score the model on inverse text
    normalisation plus a prefix nobody told it, in an argument the round-trip
    axis does not even look at — `pii_items` is empty because an order number is
    not personal data. The SECOND call is the opposite: by then the record has
    been read, so it carries the stored form and nothing else would be right.
    """
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name,
                         "arguments": json.dumps(arguments, ensure_ascii=False)},
        }],
    }


# --- tools ----------------------------------------------------------------

def _tool(name: str, description: str, params: dict[str, tuple[str, str]],
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


TOOLS: dict[str, ToolSchema] = {
    "find_orders": _tool(
        "find_orders", "Найти прошлые заказы клиента по номеру заказа.",
        {"order_id": ("string", "Номер заказа, например A-4471")},
        ["order_id"]),
    "find_customer": _tool(
        "find_customer", "Найти карточку клиента по номеру его заказа.",
        {"order_id": ("string", "Номер заказа")},
        ["order_id"]),
    "schedule_delivery": _tool(
        "schedule_delivery", "Поставить доставку по указанному адресу.",
        {"order_id": ("string", "Номер заказа"),
         "address": ("string", "Адрес доставки с домом и квартирой"),
         "date": ("string", "Желаемая дата доставки")},
        ["order_id", "address"]),
    "update_delivery_address": _tool(
        "update_delivery_address", "Изменить адрес доставки у заказа.",
        {"order_id": ("string", "Номер заказа"),
         "address": ("string", "Новый адрес с домом и квартирой"),
         "recipient_name": ("string", "ФИО получателя, если он меняется")},
        ["order_id", "address"]),
    "schedule_callback": _tool(
        "schedule_callback", "Поставить обратный звонок клиенту.",
        {"phone": ("string", "Телефон для звонка"),
         "name": ("string", "ФИО клиента"),
         "when": ("string", "Когда позвонить")},
        ["phone"]),
    "add_contact": _tool(
        "add_contact", "Добавить контакт в CRM.",
        {"name": ("string", "ФИО контакта"),
         "phone": ("string", "Телефон"),
         "email": ("string", "Электронная почта")},
        ["name", "phone"]),
    "cancel_order": _tool(
        "cancel_order", "Отменить заказ.",
        {"order_id": ("string", "Номер заказа"),
         "reason": ("string", "Причина отмены")},
        ["order_id"]),
    "list_products": _tool(
        "list_products", "Найти товары в каталоге.",
        {"query": ("string", "Поисковый запрос")},
        ["query"]),
}


def _tools_for(lookup: str, action: str) -> list[ToolSchema]:
    """The offered set: the two the task needs, plus two that fit and are wrong.

    Never a single tool. A one-tool prompt lets a model succeed by having nowhere
    else to go, which hides whether an implausible substitute damaged its ability
    to CHOOSE — and choosing is the half of the product a masked value can break
    without breaking any argument.
    """
    return [TOOLS[lookup], TOOLS[action], TOOLS["cancel_order"],
            TOOLS["list_products"]]


# --- drawn values ---------------------------------------------------------

@dataclass(frozen=True)
class _Person:
    surname: str
    first: str
    patronymic: str
    latin: str
    gender: str

    @property
    def dative_pronoun(self) -> str:
        return "ей" if self.gender == "f" else "ему"

    @property
    def full(self) -> str:
        """As a CRM stores it: surname first, nominative, patronymic when known."""
        return " ".join(p for p in (self.surname, self.first, self.patronymic) if p)


@dataclass(frozen=True)
class _Place:
    city: str
    street: str
    short: str
    house: int
    flat: int
    index: str

    @property
    def written(self) -> str:
        """As a CRM stores it. The postal index rides INSIDE the address span, so
        its six digits are claimed ground truth rather than an unlabelled shape
        the mechanical audit would refuse the case for."""
        return (f"{self.index}, {self.city}, {self.street}, "
                f"дом {self.house}, квартира {self.flat}")


@dataclass(frozen=True)
class _Body:
    """One case's parts, before the frame (id, register, scope) goes round them."""

    messages: list[_Message]
    pii: list[PiiItem]
    negatives: list[Negative]
    links: list[LinkExpectation]
    calls: list[ExpectedCall]
    tools: list[ToolSchema]


def _digits(rng: random.Random, count: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(count))


def _person(rng: random.Random) -> _Person:
    pool = FOREIGN if rng.random() < FOREIGN_SHARE else (MALE + FEMALE)
    return _Person(*rng.choice(pool))


def _place(rng: random.Random) -> _Place:
    street, short = rng.choice(STREETS)
    city, index_prefix = rng.choice(CITIES)
    return _Place(city=city, street=street, short=short,
                  house=rng.randrange(2, 90), flat=rng.randrange(2, 200),
                  index=index_prefix + _digits(rng, 3))


def _phone(rng: random.Random) -> tuple[str, str]:
    """(as the CRM writes it, canonical). Canonical is +7 and nothing else."""
    digits = rng.choice(MOBILE_PREFIXES) + _digits(rng, 7)
    written = f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}"
    return written, "+7" + digits


def _email(person: _Person, rng: random.Random) -> str:
    if rng.random() < 0.5:
        return f"{person.latin}@mail.ru"
    return f"{person.latin}_{rng.randrange(10, 99)}@yandex.ru"


def _order_pair(rng: random.Random, register: str) -> tuple[str, str]:
    """(the number as the CUSTOMER cites it, the number as the CRM stores it).

    Two strings, deliberately. The customer's channel decides how a code is
    written — spoken digit by digit on the phone, lower-cased in a messenger —
    while the record keeps one canonical form. Both are negatives: a gateway that
    masks the order number the customer just asked about has broken the
    conversation as surely as one that leaks.
    """
    digits = _digits(rng, 4)
    stored = f"A-{digits}"
    if register == "clean":
        return stored, stored
    if register == "chat":
        return f"a-{digits}", stored
    if register == "sloppy":
        return f"A{digits}", stored
    if register == "voice_itn":
        return digits, stored
    return _spell_digits(digits), stored


def _partial_street(place: _Place, register: str,
                    rng: random.Random) -> tuple[str, str]:
    """«на ленина, как обычно» — the street with no house number.

    Built FROM the record, so the pair is the same place by construction. The
    surface is what the channel writes; the canonical is the surface, because a
    street name in these templates is already the form a system would store —
    there is no case to undo and inventing a fuller one would demand a city the
    message never carried.
    """
    if register == "clean":
        return f"улице {place.short}", f"улице {place.short}"
    if register == "sloppy":
        surface, canonical = _spoil_pair(place.short.lower(), place.short, rng)
        return surface, canonical
    return place.short.lower(), place.short


def _partial_address(place: _Place, register: str) -> str:
    """The same mention WITH a house number — a building, so `required`."""
    if register == "clean":
        return f"улице {place.short}, дом {place.house}"
    if register == "voice_raw":
        return f"{place.short.lower()} {_spell_number(place.house)}"
    return f"{place.short.lower()} {place.house}"


def _item(item_id: str, kind: str, value: str, spans: _Spans,
          slot: str, msg: int, identity: str, duty: str,
          tool_param: str | None, canonical: str) -> PiiItem:
    start, end = spans[slot]
    return PiiItem(id=item_id, type=kind, value=value, start=start, end=end,
                   canonical=canonical, msg=msg, identity=identity, duty=duty,
                   tool_param=tool_param)


def _user_message(parts: list[object], register: str,
                  rng: random.Random) -> tuple[_Message, _Spans]:
    """Assemble a user turn, spoiling literals first when the channel is sloppy."""
    prepared = _spoil_literals(parts, rng) if register == "sloppy" else parts
    text, spans = assemble(prepared)
    return {"role": "user", "content": text}, spans


# --- address shapes -------------------------------------------------------

def _repeat_delivery(rng: random.Random, register: str) -> _Body:
    """«привезите то же самое ещё раз» — the address is stated NOWHERE.

    The purest form of the family: strip the tool result and the case contains no
    personal data at all. A gateway that never masks an inbound tool message
    scores a perfect recall here and hands the model a real address anyway.
    """
    place = _place(rng)
    spoken, stored = _order_pair(rng, register)
    track = _digits(rng, 14)

    if register == "clean":
        parts: list[object] = [
            "Здравствуйте! Заказ ", ("order", spoken),
            " — привезите то же самое ещё раз, адрес доставки прежний."]
    elif register == "chat":
        parts = ["здравствуйте заказ ", ("order", spoken),
                 " привезите то же ещё раз адрес тот же что был"]
    elif register == "sloppy":
        parts = ["здравствуйте заказ ", ("order", spoken),
                 " привезите тоже самое ещё раз адрес прежний"]
    elif register == "voice_itn":
        parts = ["алло здравствуйте у меня заказ ", ("order", spoken),
                 " привезите пожалуйста то же самое ещё раз адрес прежний"]
    else:
        parts = ["алло здравствуйте у меня заказ ", ("order", spoken),
                 " привезите пожалуйста то же самое ещё раз адрес прежний"]

    user, _ = _user_message(parts, register, rng)
    call_id = "call_lookup"
    lookup = _call_message(call_id, "find_orders", {"order_id": spoken})
    record, spans = _tool_message(call_id, _object_parts((
        ("order_id", stored),
        ("status", "доставлен"),
        ("track", track),
        ("address", ("address", place.written)),
    )))

    pii = [_item("addr", "LOC", place.written, spans, "address", msg=2,
                 identity="place", duty="required", tool_param="address",
                 canonical=place.written)]
    negatives = [Negative(spoken, "номер заказа, названный клиентом", 0),
                 Negative(stored, "номер заказа в записи CRM", 2),
                 Negative(track, "трек-номер отправления", 2)]
    calls = [
        ExpectedCall("find_orders", 0, {"order_id": spoken}, []),
        ExpectedCall("schedule_delivery", 2,
                     {"order_id": stored, "address": place.written}, ["addr"]),
    ]
    return _Body([user, lookup, record], pii, negatives, [], calls,
                 _tools_for("find_orders", "schedule_delivery"))


def _partial_street_shape(rng: random.Random, register: str) -> _Body:
    """«поменяйте адрес — на ленина, как обычно».

    The customer names the street and stops. That mention identifies nobody, so
    it is `optional` and claims no tool param; what it claims is a LINK to the
    full address the CRM returns, and the gateway has to resolve it inside this
    conversation or the model reads two unrelated places.
    """
    place = _place(rng)
    spoken, stored = _order_pair(rng, register)
    mention, canonical = _partial_street(place, register, rng)

    if register == "clean":
        parts: list[object] = [
            "Поменяйте, пожалуйста, адрес доставки в заказе ", ("order", spoken),
            " — на ", ("street", mention), ", как обычно."]
    elif register == "chat":
        parts = ["поменяйте адрес в заказе ", ("order", spoken), " на ",
                 ("street", mention), " как обычно"]
    elif register == "sloppy":
        parts = ["поменяйте адрес доставки в заказе ", ("order", spoken), " на ",
                 ("street", mention), " как всегда"]
    elif register == "voice_itn":
        parts = ["поменяйте мне адрес в заказе ", ("order", spoken),
                 " давайте на ", ("street", mention), " как всегда возите"]
    else:
        parts = ["поменяйте мне адрес в заказе ", ("order", spoken),
                 " давайте на ", ("street", mention), " как всегда возите"]

    user, user_spans = _user_message(parts, register, rng)
    call_id = "call_lookup"
    lookup = _call_message(call_id, "find_orders", {"order_id": spoken})
    record, spans = _tool_message(call_id, _object_parts((
        ("order_id", stored),
        ("address", ("address", place.written)),
        ("status", "доставлен"),
    )))

    pii = [
        _item("street", "LOC", user["content"][slice(*user_spans["street"])],
              user_spans, "street", msg=0, identity="street_only",
              duty="optional", tool_param=None, canonical=canonical),
        _item("addr", "LOC", place.written, spans, "address", msg=2,
              identity="place", duty="required", tool_param="address",
              canonical=place.written),
    ]
    links = [LinkExpectation(
        left="street", right="addr", kind="same", case="",
        why="одна и та же улица: частичное упоминание клиента обязано "
            "разрешиться против полного адреса из CRM в пределах ЭТОГО разговора "
            "— иначе модель видит два несвязанных места и подтверждает не то")]
    negatives = [Negative(spoken, "номер заказа, названный клиентом", 0),
                 Negative(stored, "номер заказа в записи CRM", 2)]
    calls = [
        ExpectedCall("find_orders", 0, {"order_id": spoken}, []),
        ExpectedCall("update_delivery_address", 2,
                     {"order_id": stored, "address": place.written}, ["addr"]),
    ]
    return _Body([user, lookup, record], pii, negatives, links, calls,
                 _tools_for("find_orders", "update_delivery_address"))


def _two_orders(rng: random.Random, register: str) -> _Body:
    """Two past orders come back and the customer picks one by street and house.

    The `different` half of the linking claim lives here. Two addresses in one
    record set are two places: one substitute for both would send the courier to
    an address the customer did not choose, and the conversation would read as if
    it had worked. The streets are drawn distinct on purpose — two houses on ONE
    street inside a conversation is the shape where our own single-candidate rule
    refuses to link either, and demanding a link there would score the gateway on
    a decision it is right to decline.
    """
    first_place = _place(rng)
    second_place = _place(rng)
    while second_place.short == first_place.short:
        second_place = _place(rng)
    spoken, stored = _order_pair(rng, register)
    other_stored = f"A-{_digits(rng, 4)}"
    mention = _partial_address(first_place, register)

    if register == "clean":
        parts: list[object] = [
            "Подскажите, на какой адрес был мой прошлый заказ ", ("order", spoken),
            "? Нужно повторить."]
        pick: list[object] = ["Да, на ", ("pick", mention), " — туда и везите."]
    elif register == "chat":
        parts = ["а на какой адрес был прошлый заказ ", ("order", spoken),
                 " надо повторить"]
        pick = ["да на ", ("pick", mention), " туда и везите"]
    elif register == "sloppy":
        parts = ["подскажите на какой адрес был прошлый заказ ", ("order", spoken),
                 " нужно повторить"]
        pick = ["да на ", ("pick", mention), " туда и везите"]
    elif register == "voice_itn":
        parts = ["скажите а на какой адрес был прошлый заказ ", ("order", spoken),
                 " мне надо повторить"]
        pick = ["ну да на ", ("pick", mention), " вот туда и везите"]
    else:
        parts = ["скажите а на какой адрес был прошлый заказ ", ("order", spoken),
                 " мне надо повторить"]
        pick = ["ну да на ", ("pick", mention), " вот туда и везите"]

    user, _ = _user_message(parts, register, rng)
    call_id = "call_lookup"
    lookup = _call_message(call_id, "find_orders", {"order_id": spoken})
    record, spans = _tool_message(call_id, _array_parts((
        _object_parts((("order_id", stored),
                       ("address", ("first", first_place.written)))),
        _object_parts((("order_id", other_stored),
                       ("address", ("second", second_place.written)))),
    )))
    chosen, chosen_spans = _user_message(pick, register, rng)

    pii = [
        _item("addr_a", "LOC", first_place.written, spans, "first", msg=2,
              identity="place_a", duty="required", tool_param="address",
              canonical=first_place.written),
        _item("addr_b", "LOC", second_place.written, spans, "second", msg=2,
              identity="place_b", duty="required", tool_param=None,
              canonical=second_place.written),
        _item("pick", "LOC", chosen["content"][slice(*chosen_spans["pick"])],
              chosen_spans, "pick", msg=3, identity="picked", duty="required",
              tool_param=None,
              canonical=chosen["content"][slice(*chosen_spans["pick"])]),
    ]
    links = [
        LinkExpectation(left="addr_a", right="addr_b", kind="different", case="",
                        why="два разных адреса одного клиента: одна подмена на "
                            "оба означает курьера по чужому адресу при том, что "
                            "разговор выглядит успешным"),
        LinkExpectation(left="pick", right="addr_a", kind="same", case="",
                        why="клиент выбрал первый адрес улицей и домом; "
                            "связывание обязано сработать именно с ним, а "
                            "единственность кандидата обеспечена разными улицами"),
    ]
    negatives = [Negative(spoken, "номер заказа, названный клиентом", 0),
                 Negative(stored, "номер заказа в записи CRM", 2),
                 Negative(other_stored, "номер второго заказа", 2)]
    calls = [
        ExpectedCall("find_orders", 0, {"order_id": spoken}, []),
        ExpectedCall("schedule_delivery", 3,
                     {"order_id": stored, "address": first_place.written},
                     ["addr_a"]),
    ]
    return _Body([user, lookup, record, chosen], pii, negatives, links, calls,
                 _tools_for("find_orders", "schedule_delivery"))


# --- person shapes --------------------------------------------------------

def _callback_same_number(rng: random.Random, register: str) -> _Body:
    """«перезвоните мне на тот же номер» — the phone exists only in the CRM.

    The phone is the one type a checksum holds on the user leg, and here it never
    walks that leg: it arrives already formatted by a system, is masked inbound,
    and has to come back dialable. A substitute that resolves to nothing is a call
    that is never made and a customer who is never told why.
    """
    person = _person(rng)
    written_phone, canonical_phone = _phone(rng)
    spoken, stored = _order_pair(rng, register)

    if register == "clean":
        parts: list[object] = [
            "Перезвоните мне, пожалуйста, на тот же номер, что и в прошлый раз. "
            "Заказ ", ("order", spoken), "."]
    elif register == "chat":
        parts = ["перезвоните на тот же номер что и в прошлый раз заказ ",
                 ("order", spoken)]
    elif register == "sloppy":
        parts = ["перезвоните мне на тот же номер что и в прошлый раз, заказ ",
                 ("order", spoken)]
    elif register == "voice_itn":
        parts = ["перезвоните мне пожалуйста на тот же номер что и в прошлый раз "
                 "заказ ", ("order", spoken)]
    else:
        parts = ["перезвоните мне пожалуйста на тот же номер что и в прошлый раз "
                 "заказ ", ("order", spoken)]

    user, _ = _user_message(parts, register, rng)
    call_id = "call_lookup"
    lookup = _call_message(call_id, "find_customer", {"order_id": spoken})
    record, spans = _tool_message(call_id, _object_parts((
        ("order_id", stored),
        ("name", ("name", person.full)),
        ("phone", ("phone", written_phone)),
        ("channel", "телефон"),
    )))

    pii = [
        _item("name", "NAME", person.full, spans, "name", msg=2,
              identity="person", duty="required", tool_param="name",
              canonical=person.full),
        _item("phone", "PHONE", written_phone, spans, "phone", msg=2,
              identity="person_phone", duty="required", tool_param="phone",
              canonical=canonical_phone),
    ]
    negatives = [Negative(spoken, "номер заказа, названный клиентом", 0),
                 Negative(stored, "номер заказа в записи CRM", 2)]
    calls = [
        ExpectedCall("find_customer", 0, {"order_id": spoken}, []),
        ExpectedCall("schedule_callback", 2,
                     {"phone": canonical_phone, "name": person.full},
                     ["phone", "name"]),
    ]
    return _Body([user, lookup, record], pii, negatives, [], calls,
                 _tools_for("find_customer", "schedule_callback"))


def _same_recipient(rng: random.Random, register: str) -> _Body:
    """«добавьте получателя из заказа в контакты» — three params, one call.

    The email is here and nowhere else in the family: a Latin string inside a
    Latin-keyed JSON field, which is the shape that lost `{"passport": …}`
    entirely once, because the cue vocabulary holds the Russian word and not the
    English one.
    """
    person = _person(rng)
    written_phone, canonical_phone = _phone(rng)
    email = _email(person, rng)
    spoken, stored = _order_pair(rng, register)
    track = _digits(rng, 14)

    if register == "clean":
        parts: list[object] = [
            "Добавьте получателя из заказа ", ("order", spoken),
            " в контакты, данные у вас есть."]
    elif register == "chat":
        parts = ["добавьте получателя из заказа ", ("order", spoken),
                 " в контакты данные у вас есть"]
    elif register == "sloppy":
        parts = ["добавте получателя из заказа ", ("order", spoken),
                 " в контакты, данные же есть у вас"]
    elif register == "voice_itn":
        parts = ["добавьте пожалуйста получателя из заказа ", ("order", spoken),
                 " к себе в контакты данные у вас есть"]
    else:
        parts = ["добавьте пожалуйста получателя из заказа ", ("order", spoken),
                 " к себе в контакты данные у вас есть"]

    user, _ = _user_message(parts, register, rng)
    call_id = "call_lookup"
    lookup = _call_message(call_id, "find_customer", {"order_id": spoken})
    record, spans = _tool_message(call_id, _object_parts((
        ("order_id", stored),
        ("track", track),
        ("name", ("name", person.full)),
        ("phone", ("phone", written_phone)),
        ("email", ("email", email)),
    )))

    pii = [
        _item("name", "NAME", person.full, spans, "name", msg=2,
              identity="person", duty="required", tool_param="name",
              canonical=person.full),
        _item("phone", "PHONE", written_phone, spans, "phone", msg=2,
              identity="person_phone", duty="required", tool_param="phone",
              canonical=canonical_phone),
        _item("email", "EMAIL", email, spans, "email", msg=2,
              identity="person_email", duty="required", tool_param="email",
              canonical=email),
    ]
    negatives = [Negative(spoken, "номер заказа, названный клиентом", 0),
                 Negative(stored, "номер заказа в записи CRM", 2),
                 Negative(track, "трек-номер отправления", 2)]
    calls = [
        ExpectedCall("find_customer", 0, {"order_id": spoken}, []),
        ExpectedCall("add_contact", 2,
                     {"name": person.full, "phone": canonical_phone,
                      "email": email}, ["name", "phone", "email"]),
    ]
    return _Body([user, lookup, record], pii, negatives, [], calls,
                 _tools_for("find_customer", "add_contact"))


def _partial_person(rng: random.Random, register: str) -> _Body:
    """«да, Марии, ей и звоните» — a declined given name against the full record.

    The person half of the partial mention, and the one that reaches morphology:
    the customer writes a dative, the canonical form of what they wrote is the
    nominative, and a gateway that returns «Марии» to a CRM field has written a
    person who does not exist. The link says the two mentions are one человек;
    the round trip says the value that reaches the tool is the CRM's own string.
    """
    person = _person(rng)
    written_phone, canonical_phone = _phone(rng)
    spoken, stored = _order_pair(rng, register)
    dative = DATIVE.get(person.first, person.first)
    canonical_given = person.first
    if register in ("chat", "voice_itn", "voice_raw"):
        mention = dative.lower()
    elif register == "sloppy":
        mention, canonical_given = _spoil_pair(dative, person.first, rng)
    else:
        mention = dative

    if register == "clean":
        parts: list[object] = [
            "Позвоните по заказу ", ("order", spoken),
            " тому же человеку, что и в прошлый раз."]
        pick: list[object] = ["Да, ", ("given", mention),
                              f", {person.dative_pronoun} и звоните."]
    elif register == "chat":
        parts = ["позвоните по заказу ", ("order", spoken),
                 " тому же человеку что и в прошлый раз"]
        pick = ["да ", ("given", mention),
                f" {person.dative_pronoun} и звоните"]
    elif register == "sloppy":
        parts = ["позвоните по заказу ", ("order", spoken),
                 " тому же человеку что и в прошлый раз"]
        pick = ["да ", ("given", mention),
                f" {person.dative_pronoun} и звоните"]
    elif register == "voice_itn":
        parts = ["позвоните там по заказу ", ("order", spoken),
                 " тому же человеку что и в прошлый раз"]
        pick = ["ну да ", ("given", mention),
                f" {person.dative_pronoun} и звоните"]
    else:
        parts = ["позвоните там по заказу ", ("order", spoken),
                 " тому же человеку что и в прошлый раз"]
        pick = ["ну да ", ("given", mention),
                f" {person.dative_pronoun} и звоните"]

    user, _ = _user_message(parts, register, rng)
    call_id = "call_lookup"
    lookup = _call_message(call_id, "find_customer", {"order_id": spoken})
    record, spans = _tool_message(call_id, _object_parts((
        ("order_id", stored),
        ("name", ("name", person.full)),
        ("phone", ("phone", written_phone)),
    )))
    chosen, chosen_spans = _user_message(pick, register, rng)

    pii = [
        _item("name", "NAME", person.full, spans, "name", msg=2,
              identity="person", duty="required", tool_param="name",
              canonical=person.full),
        _item("phone", "PHONE", written_phone, spans, "phone", msg=2,
              identity="person_phone", duty="required", tool_param="phone",
              canonical=canonical_phone),
        _item("given", "NAME", chosen["content"][slice(*chosen_spans["given"])],
              chosen_spans, "given", msg=3, identity="person_given",
              duty="required", tool_param=None, canonical=canonical_given),
    ]
    links = [LinkExpectation(
        left="given", right="name", kind="same", case="",
        why="одно и то же лицо: клиент назвал имя из карточки в дательном "
            "падеже, и подмена обязана совпасть с той, что модель уже видела в "
            "результате инструмента — иначе в разговоре два человека")]
    negatives = [Negative(spoken, "номер заказа, названный клиентом", 0),
                 Negative(stored, "номер заказа в записи CRM", 2)]
    calls = [
        ExpectedCall("find_customer", 0, {"order_id": spoken}, []),
        ExpectedCall("schedule_callback", 3,
                     {"phone": canonical_phone, "name": person.full},
                     ["phone", "name"]),
    ]
    return _Body([user, lookup, record, chosen], pii, negatives, links, calls,
                 _tools_for("find_customer", "schedule_callback"))


BUILDERS: dict[str, Callable[[random.Random, str], _Body]] = {
    "repeat_delivery": _repeat_delivery,
    "partial_street": _partial_street_shape,
    "two_orders": _two_orders,
    "callback_same_number": _callback_same_number,
    "same_recipient": _same_recipient,
    "partial_person": _partial_person,
}


# --- the frame ------------------------------------------------------------

_DIGIT = re.compile(r"\d")
_DIGIT_RUN = re.compile(r"\d{2,}")


def _declare_asr_digits(messages: list[_Message], register: str) -> bool:
    """Whether the case declares digits, and the stricter rule underneath it.

    The schema's register gate scans `user` and `tool` messages together, so a
    CRM record drags a `voice_raw` case over it. The declaration is honest — the
    digits are there and they are deliberate — but it switches the gate off, so
    the property that actually matters is checked HERE and it is stronger than
    the gate: a spoken turn may not contain a digit at all, not even one, because
    zero of 12 950 real call transcripts do.
    """
    if register != "voice_raw":
        return False
    spoken = " ".join(str(message["content"]) for message in messages
                      if message.get("role") == "user")
    if _DIGIT.search(spoken):
        raise ValueError(f"voice_raw user turn carries a digit: {spoken!r}")
    written = " ".join(str(message["content"]) for message in messages
                       if message.get("role") == "tool")
    return bool(_DIGIT_RUN.search(written))


def _case(rng: random.Random, form: str, register: str, index: int) -> Case:
    shapes = ADDRESS_SHAPES if form == "address" else PERSON_SHAPES
    shape = shapes[index % len(shapes)]
    body = BUILDERS[shape](rng, register)
    case_id = f"indirect-{shape}-{register}-{index:02d}"
    return Case(
        id=case_id,
        family=FAMILY,
        scenario=shape,
        register=register,
        # NOT a crossed dimension here — the design doc crosses difficulty only
        # inside `transfer`, and in this family the family IS the difficulty. The
        # field is mandatory, so it states the one label that describes every case
        # honestly: several entities, non-PII numbers beside them, and a value
        # that never passed through the user leg.
        difficulty="hard",
        length_rung="short",
        # Half the cases hand the gateway a conversation id and half make it
        # DERIVE one, because those are different code paths and the derived one
        # is what a customer gateway with no conversation field triggers. It is
        # weaker here than anywhere: `conversation_key` reads the first two
        # messages, and the second is an assistant tool call whose content is
        # empty, so the whole identity rests on the opening turn.
        conversation_id=f"conv-{case_id}" if index % 2 == 0 else "",
        relation="equality",
        messages=body.messages,
        tools=body.tools,
        pii=body.pii,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        negatives=body.negatives,
        links=body.links,
        calls=body.calls,
        asr_digits=_declare_asr_digits(body.messages, register),
    )


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases, deterministic from `rng`.

    The order is set-major — one set is every (form, register) pair — so any
    prefix that is a multiple of ten is balanced across both axes. The tier
    ladder is a frozen prefix of the whole corpus and does its own balancing, but
    a family whose own prefix is lopsided makes a truncated development run
    silently register-skewed, and that is free to prevent here.
    """
    cases: list[Case] = []
    index = 0
    while len(cases) < count:
        for form in ("address", "person"):
            for register in REGISTERS:
                if len(cases) == count:
                    return cases
                cases.append(_case(rng, form, register, index))
        index += 1
    return cases


def main() -> int:
    """Build the family and validate it against the schema. Prints, returns 1 on
    any problem — a generator whose spans disagree with its own text keeps
    producing numbers, and the numbers are false."""
    from bench.agentpii2.schema import case_characters, validate

    cases = build(random.Random(20260830), 100)
    problems = [problem for case in cases for problem in validate(case)]
    by_register: dict[str, int] = {}
    by_shape: dict[str, int] = {}
    for case in cases:
        by_register[case.register] = by_register.get(case.register, 0) + 1
        by_shape[case.scenario] = by_shape.get(case.scenario, 0) + 1
    print(f"случаев:      {len(cases)}")
    print(f"по регистрам: {by_register}")
    print(f"по формам:    {by_shape}")
    items = [item for case in cases for item in case.pii]
    print(f"обязательных: {sum(1 for i in items if i.duty == 'required')}")
    print(f"необязательных: {sum(1 for i in items if i.duty == 'optional')}")
    print(f"негативов:    {sum(len(c.negatives) for c in cases)}")
    print(f"связей:       {sum(len(c.links) for c in cases)}")
    print(f"длина:        {min(case_characters(c) for c in cases)}-"
          f"{max(case_characters(c) for c in cases)} символов")
    print(f"с id разговора: {sum(1 for c in cases if c.conversation_id)}")
    if problems:
        print(f"НЕВАЛИДНО — {len(problems)} проблем:")
        for problem in problems[:20]:
            print(f"  {problem}")
        return 1
    print("схема: без замечаний")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
