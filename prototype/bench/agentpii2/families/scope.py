"""The `scope` family — where conversation-scoped linking STOPS.

WHAT THIS FAMILY ASKS, and it is two questions that must be asked apart. A
partial mention («Ленина, 14», «Игорю») is resolvable only against a fuller one
said earlier, and `docs/tz-agentpii2.md` §3.7 splits the demand in two:

  within   the fuller mention is in the SAME conversation. Linking MUST happen,
           or the partial gets its own substitute and the model is handed two
           addresses where the customer named one.
  across   the fuller mention is in a DIFFERENT conversation of the same tenant.
           Linking MUST NOT happen, or one customer's address resolves inside
           another customer's dialogue.

WHY IT IS NOT `compare`. `compare` asks whether the mechanism works; `scope` asks
where it stops. CLAUDE.md states the reason the two cannot be one number: at
tenant scale «Ленина 14» has a dozen owners, the single-candidate rule refuses
every time, and the mechanism is not careful but dead. One change bought both the
meaning and the safety, so a regression in either direction hides inside a
success in the other unless they are measured separately.

WHY EVERY CASE IS HALF OF A PAIR. «These two must NOT merge» cannot be stated
inside one case: one case is one conversation, and `conversation_id` is a field
on the case. So the unit here is a LEAD case that states the full value and a
FOLLOW case that states only the partial, joined by `Case.preceded_by` and by a
`LinkExpectation` whose `case` reaches back. This family is the only consumer of
either field in the corpus, which is what §3.7 means by «единственная причина, по
которой `preceded_by` существует».

THREE VEHICLES, AND THE THIRD IS A CONTROL ARM, not a third topic.

  place   «Ленина, 14» against «г. Москва, ул. Ленина, д. 14, кв. 7». The engine's
          `place_parts` index is conversation-scoped and expires after a day, so
          `within` must link and `across` must not.
  person  «Игорю» / «Соколову» against «Соколов Игорь Валентинович». A LINKED row
          is stored under a conversation-scoped canonical, so the same split
          applies — through a different mechanism (morphology and the linked-row
          key rather than the single-candidate place rule), which is why it is a
          separate vehicle and not more place cases.
  phone   the same subscriber written «+7 916…» and «916…». THIS ONE CLAIMS `same`
          IN BOTH DIRECTIONS, and the asymmetry is the point. The vault is keyed
          `(customer, canonical)` — tenant-wide, by documented design — so two
          conversations naming one phone SHOULD receive one substitute. Without
          this arm a gateway that simply stopped linking would satisfy every
          `across` claim in the family and score perfectly on exactly the failure
          the family exists to detect. It is the same move `rank` makes with
          `frequency`: an arm that a broken instrument cannot pass.

WHAT THE GROUND TRUTH DOES NOT CLAIM. A FULL address and a FULL phone are keyed
plainly and deliberately reach one substitute for ever, across conversations —
CLAUDE.md: «Full addresses keep the plain key: one place, one substitute, for
ever.» So no case here demands that two full mentions stay apart. Writing that
claim would manufacture a failure out of a design decision, which is the
benchmark equivalent of tuning the corpus to the detector with the sign flipped.

BOTH SCOPE PATHS. `within` must carry an explicit `conversation_id`: two separate
cases can only share a scope by being handed one. `across` alternates — half with
two explicit and different ids, half with none at all, so the engine derives the
identity from each transcript's first two messages. The derived path is what a
customer gateway with no conversation field actually triggers and it is weaker on
purpose; a family that only exercised the explicit one would leave the weaker
half of the mechanism unmeasured.

AUTHORSHIP, stated because it matters to how the numbers are read: the other
seven families were each written by a dedicated author against the design doc.
This one was written by the corpus assembler, after `validate_corpus` refused a
corpus with a family missing. It is the smallest thing that makes the family's
two claims falsifiable, not the full 60-case treatment §3.7 describes — the
difficulty axis is not crossed, and there is no case where the partial mention
lands inside a long transcript.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii2.schema import (  # noqa: E402
    REGISTERS, Case, ExpectedCall, LinkExpectation, Negative, PiiItem,
)
from bench.agentpii2.tools import tools_for  # noqa: E402

FAMILY = "scope"
DIRECTIONS: tuple[str, ...] = ("within", "across")
VEHICLES: tuple[str, ...] = ("place", "person", "phone")

# One pair per (direction, vehicle, register): 2 x 3 x 5 = 30 pairs, 60 cases.
_CELLS: tuple[tuple[str, str, str], ...] = tuple(
    (direction, vehicle, register)
    for direction in DIRECTIONS
    for vehicle in VEHICLES
    for register in REGISTERS)

_SYSTEM: str = ("Ты оператор интернет-магазина. Работай с заказом через "
                "предложенные инструменты и не переспрашивай лишнего.")

# --- the numerals, written out rather than rendered ------------------------
#
# A table, for the same reason `toolresult.py` and `context.py` keep one: a
# renderer's mistake would enter the GROUND TRUTH, where it is not a rendering
# bug but a wrong answer the corpus then demands. Every form here is checkable by
# eye, and nothing outside the table is ever spoken.
_DIGIT_WORDS: dict[str, str] = {
    "0": "ноль", "1": "один", "2": "два", "3": "три", "4": "четыре",
    "5": "пять", "6": "шесть", "7": "семь", "8": "восемь", "9": "девять",
}
_NUMBER_WORDS: dict[str, str] = {
    "3": "три", "5": "пять", "7": "семь", "8": "восемь", "12": "двенадцать",
    "14": "четырнадцать", "19": "девятнадцать", "21": "двадцать один",
    "25": "двадцать пять", "41": "сорок один", "60": "шестьдесят",
    "88": "восемьдесят восемь",
}
_PREFIX_WORDS: dict[str, str] = {
    "916": "девятьсот шестнадцать", "903": "девятьсот три",
    "925": "девятьсот двадцать пять", "926": "девятьсот двадцать шесть",
    "909": "девятьсот девять", "985": "девятьсот восемьдесят пять",
    "999": "девятьсот девяносто девять", "921": "девятьсот двадцать один",
    "951": "девятьсот пятьдесят один", "962": "девятьсот шестьдесят два",
}


def _digits(value: str) -> str:
    return " ".join(_DIGIT_WORDS[character] for character in value)


def _number(value: str) -> str:
    return _NUMBER_WORDS[value]


# --- the pools -------------------------------------------------------------
#
# EVERY PAIR GETS A VALUE NOBODY ELSE IN THE CORPUS USES, and that is a
# correctness requirement rather than variety. The pools were drawn against
# the canonical values of all seven sibling families and every clash removed:
# «Соколов Игорь Валентинович» was minted by six of them, and a street named
# «Чехова» by three, which would have let another family's mention join the
# candidate set that this family's single-candidate rule is being measured on.
# `build.py`'s `value_collisions` is what keeps that true as families change. The whole corpus is scored through
# one tenant vault, so two pairs sharing an address would let one pair's LEAD
# satisfy the other pair's link — a `within` success manufactured by the corpus,
# or an `across` violation charged to a gateway that was right. Ten values per
# vehicle, one per (direction, register) cell, no repeats.
#
# The streets are deliberately a mix of surname-derived («Чехова», «Гоголя») and
# adjectival («Заречная», «Полевая»). Both are ordinary in Russian address lines
# and they fail differently: the first is where `ADDR` has to outrank `NAME`, the
# second is where a marker-less street has to be admitted at all.
_PLACES: tuple[tuple[str, str, str, str, str], ...] = (
    # city,      type,        street,       house, flat
    ("Москва",   "улица",     "Ольховая",   "14",  "7"),
    ("Казань",   "улица",     "Заречная",   "8",   "12"),
    ("Самара",   "переулок",  "Гоголя",     "25",  "3"),
    ("Пермь",    "улица",     "Полевая",    "3",   "88"),
    ("Тверь",    "улица",     "Липовая",    "41",  "21"),
    ("Омск",     "улица",     "Луговая",    "7",   "14"),
    ("Тула",     "улица",     "Рябиновая",  "12",  "5"),
    ("Курск",    "проезд",    "Речной",     "60",  "8"),
    ("Брянск",   "улица",     "Тургенева",  "19",  "25"),
    ("Псков",    "улица",     "Боровая",    "5",   "41"),
)

# Surname, given name, patronymic, given-name dative, surname dative. The dative
# forms are written out for the same reason the numerals are: pymorphy3 would
# produce them, but a wrong one would enter the ground truth and the corpus would
# demand a form nobody said.
_PEOPLE: tuple[tuple[str, str, str, str, str], ...] = (
    ("Голубев",   "Леонид",    "Аркадьевич",  "Леониду",   "Голубеву"),
    ("Юдина",     "Галина",    "Тимофеевна",  "Галине",    "Юдиной"),
    ("Шилов",     "Тимофей",   "Егорович",    "Тимофею",   "Шилову"),
    ("Ершова",    "Лидия",     "Семёновна",   "Лидии",     "Ершовой"),
    ("Пестов",    "Матвей",    "Родионович",  "Матвею",    "Пестову"),
    ("Латышева",  "Нина",      "Аркадьевна",  "Нине",      "Латышевой"),
    ("Тюрин",     "Егор",      "Валерьевич",  "Егору",     "Тюрину"),
    ("Одинцова",  "Ульяна",    "Львовна",     "Ульяне",    "Одинцовой"),
    ("Бажанов",   "Всеволод",  "Юрьевич",     "Всеволоду", "Бажанову"),
    ("Крутикова", "Раиса",     "Григорьевна", "Раисе",     "Крутиковой"),
)

# Real Russian mobile prefixes, so libphonenumber accepts the number as dialable
# and the digit legs of the corpus measure detection rather than a malformed
# shape. Seven digits after the prefix, all distinct across the pool.
_PHONES: tuple[tuple[str, str], ...] = (
    ("916", "2148803"), ("903", "7712045"), ("925", "3390617"),
    ("926", "5024871"), ("909", "8163592"), ("985", "4471268"),
    ("999", "6205734"), ("921", "1748306"), ("951", "9036142"),
    ("962", "5581470"),
)

# Order numbers. FOUR DIGITS, never six or more: `audit_unlabelled` scans for
# runs of six and a longer order number would need claiming as a negative in
# every message it appeared in, which is bookkeeping the case does not need.
# They are declared as negatives anyway — «do not mask the number the customer
# just asked about» is a real demand and the commonest false mask in the wild.
_ORDERS: tuple[str, ...] = (
    "4471", "8123", "2059", "6714", "3388", "9042", "5176", "7630",
    "1295", "4807", "6538", "2914", "8360", "5723", "1084", "9451",
    "3607", "7218", "4962", "6035", "2481", "8790", "5314", "1657",
    "9028", "3745", "6182", "4593", "7806", "2370", "8149", "5928",
    "1463", "9705", "3251", "6874", "4018", "7592", "2836", "5107",
    "8465", "1739", "9284", "3960", "6512", "4327", "7051", "2698",
    "5843", "1076", "9317", "3489", "6720", "4165", "7934", "2502",
    "8671", "5240", "1893", "9556",
)


def _assemble(chunks: list[object]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Build a message and record every marked span's offsets AS IT IS BUILT.

    A plain string is literal text; a `(key, text)` tuple is text whose offsets
    are recorded under `key`. Searching the finished string instead would find
    the first occurrence, and a message that names one street twice — «Чехова, 14
    … на Чехова» — would then carry a span pointing at the wrong one. Every other
    family in this corpus computes offsets the same way and for the same reason.
    """
    parts: list[str] = []
    marks: dict[str, tuple[int, int]] = {}
    position = 0
    for chunk in chunks:
        if isinstance(chunk, str):
            parts.append(chunk)
            position += len(chunk)
            continue
        key, text = chunk  # type: ignore[misc]
        if key in marks:
            raise ValueError(f"span {key!r} marked twice in one message")
        marks[str(key)] = (position, position + len(str(text)))
        parts.append(str(text))
        position += len(str(text))
    return "".join(parts), marks


# --- register surfaces -----------------------------------------------------
#
# REGISTER LIVES IN THE TEMPLATE AND IN THE SLOT VALUES, never in a pass over the
# finished string. A post-assembly transform changes length and silently moves
# every offset computed before it, and the ground truth then points a few
# characters to the left while the benchmark keeps printing numbers.
#
# The seven Latin letters with a Cyrillic twin. `sloppy` swaps exactly one, and
# WHERE it swaps is a decision the family makes per vehicle rather than
# uniformly: inside the span for a place (a street name survives one wrong letter
# and the detector's fuzzy street arm is what must catch it), and inside the CUE
# WORD for a person (the nominative of a typo'd oblique form is not derivable
# from any table, so a typo in the name would put a guess into the ground truth —
# the same reason `comparison.py` keeps sloppy's error budget off its names).
_TWINS: dict[str, str] = {"а": "a", "с": "c", "е": "e", "р": "p",
                          "о": "o", "х": "x", "у": "y"}


def _latinise(word: str) -> str:
    """One Cyrillic letter replaced by its Latin twin, the first that has one."""
    for index, character in enumerate(word):
        twin = _TWINS.get(character.lower())
        if twin:
            return word[:index] + twin + word[index + 1:]
    raise ValueError(f"{word!r} holds no letter with a Latin twin; the sloppy "
                     f"register cannot be produced from the pool as written")


def _place_full(register: str, place: tuple[str, str, str, str, str]) -> str:
    city, kind, street, house, flat = place
    if register == "clean":
        return f"г. {city}, {kind} {street}, д. {house}, кв. {flat}"
    if register == "chat":
        return f"{city.lower()} {street.lower()} {house} кв {flat}"
    if register == "sloppy":
        return f"г. {city}, {kind} {street}, д. {house}, кв. {flat}"
    if register == "voice_itn":
        return f"{city} {kind} {street} {house} квартира {flat}"
    return (f"{city.lower()} {kind} {street.lower()} {_number(house)} "
            f"квартира {_number(flat)}")


def _place_partial(register: str, place: tuple[str, str, str, str, str]) -> str:
    _, _, street, house, _ = place
    if register == "clean":
        return f"{street}, {house}"
    if register == "chat":
        return f"{street.lower()} {house}"
    if register == "sloppy":
        return f"{_latinise(street.lower())} {house}"
    if register == "voice_itn":
        return f"{street} {house}"
    return f"{street.lower()} {_number(house)}"


def _person_full(register: str, person: tuple[str, str, str, str, str]) -> str:
    surname, given, patronymic, _, _ = person
    if register == "clean":
        return f"{surname} {given} {patronymic}"
    if register == "chat":
        # A messenger drops the patronymic, and the ground truth must not ask for
        # it back: the canonical form is of WHAT WAS WRITTEN, not of the identity.
        return f"{surname.lower()} {given.lower()}"
    if register == "sloppy":
        return f"{surname} {given} {patronymic}"
    return f"{surname.lower()} {given.lower()} {patronymic.lower()}"


def _person_partial(register: str, person: tuple[str, str, str, str, str],
                    by_surname: bool) -> tuple[str, str]:
    """The oblique partial and its nominative canonical.

    TWO SUB-SHAPES, alternated by pair. A given name in the dative («Игорю») and
    a surname in the dative («Соколову») reach the nominative through different
    machinery — CLAUDE.md records that a guard placed inside `to_nominative`
    fixed «Иванова» and broke «Тарасова» at the same time, and that a surname
    alone may not decide gender. Measuring only one of them would leave the other
    to be found by a customer.
    """
    surname, given, _, given_dative, surname_dative = person
    written, nominative = ((surname_dative, surname) if by_surname
                           else (given_dative, given))
    if register in ("chat", "voice_itn", "voice_raw"):
        return written.lower(), nominative.lower()
    return written, nominative


def _phone_full(register: str, phone: tuple[str, str]) -> tuple[str, str]:
    """The surface and the canonical a CRM would hold.

    `voice_raw` IS THE EXCEPTION AND IT IS DELIBERATE. `same_value` compares by
    digits whenever the expected value carries six or more of them, so a canonical
    of «+79162148803» against a gateway that only ever saw «восемь девятьсот
    шестнадцать…» fails every spoken phone even on a perfect round trip. The
    spoken surface is the canonical there, exactly as `carryover.py` decided, and
    the item claims no tool param — non-detection is scored on the coverage axis
    and the round trip does not also get to claim it.
    """
    prefix, rest = phone
    canonical = f"+7{prefix}{rest}"
    if register == "clean":
        return f"+7 {prefix} {rest[:3]}-{rest[3:5]}-{rest[5:]}", canonical
    if register == "chat":
        return f"8{prefix}{rest}", canonical
    if register == "sloppy":
        # A Cyrillic О standing in for a zero, which `normalize` folds because it
        # sits inside a digit-dense run. Where the number has no zero the twin
        # lands on the last digit's neighbour instead of being skipped, so the
        # register is never silently absent.
        spoiled = f"8-{prefix}-{rest[:3]}-{rest[3:5]}-{rest[5:]}"
        return spoiled.replace("0", "О", 1) if "0" in rest else spoiled, canonical
    if register == "voice_itn":
        return f"8 {prefix} {rest[:3]} {rest[3:5]} {rest[5:]}", canonical
    spoken = f"восемь {_PREFIX_WORDS[prefix]} {_digits(rest)}"
    return spoken, spoken


def _phone_partial(register: str, phone: tuple[str, str]) -> tuple[str, str]:
    """The same subscriber without the country code — the partial the vault's
    canonicalisation is supposed to collapse onto the full one."""
    prefix, rest = phone
    canonical = f"+7{prefix}{rest}"
    if register == "clean":
        return f"{prefix} {rest[:3]}-{rest[3:5]}-{rest[5:]}", canonical
    if register == "chat":
        return f"{prefix}{rest}", canonical
    if register == "sloppy":
        return f"{prefix}-{rest[:3]}-{rest[3:5]}-{rest[5:]}", canonical
    if register == "voice_itn":
        return f"{prefix} {rest[:3]} {rest[3:5]} {rest[5:]}", canonical
    spoken = f"{_PREFIX_WORDS[prefix]} {_digits(rest)}"
    return spoken, spoken


def _order(register: str, number: str) -> str:
    """The order number as this register writes it. Spelled out in `voice_raw`,
    where it becomes the register's own over-masking trap: a bare run of number
    words standing next to address language."""
    return _digits(number) if register == "voice_raw" else number


# --- the pair --------------------------------------------------------------

_LEAD_TEXT: dict[tuple[str, str], str] = {
    # «на г. Москва, улица Чехова» is not Russian, and neither is «на Луговая, 7»
    # — the preposition wants an oblique case the pool does not carry. Careful
    # writing solves it with the cue «по адресу»; chat and dictation solve it by
    # dropping the preposition, which is what people actually type and say. Both
    # are kept, so the CUE WORD is present in `clean` and `sloppy` and absent in
    # the other three — a difficulty gradient that follows the register rather
    # than being imposed on it, and one a reader of the per-register table must
    # know about before attributing the gap to the register alone.
    ("place", "clean"): "Здравствуйте! Заказ {order}, доставку оформите по адресу: {value}.",
    ("place", "chat"): "привет заказ {order} доставка {value}",
    ("place", "sloppy"): "Здравствуйте! Заказ {order}, дoставку оформите по адресу: {value}.",
    ("place", "voice_itn"): "здравствуйте заказ {order} доставка {value}",
    ("place", "voice_raw"): "здравствуйте заказ {order} доставка {value}",
    ("person", "clean"): "Заказ {order}, получатель {value}.",
    ("person", "chat"): "заказ {order} получатель {value}",
    ("person", "sloppy"): "Заказ {order}, пoлучатель {value}.",
    ("person", "voice_itn"): "заказ {order} получатель {value}",
    ("person", "voice_raw"): "заказ {order} получатель {value}",
    ("phone", "clean"): "Заказ {order}, мой телефон {value}.",
    ("phone", "chat"): "заказ {order} мой номер {value}",
    ("phone", "sloppy"): "Заказ {order}, мой тeлефон {value}.",
    ("phone", "voice_itn"): "заказ {order} мой телефон {value}",
    ("phone", "voice_raw"): "заказ {order} мой телефон {value}",
}

_FOLLOW_TEXT: dict[tuple[str, str], str] = {
    ("place", "clean"): "Заказ {order}, привезите по адресу {value}, после обеда.",
    ("place", "chat"): "заказ {order} привезите {value} после обеда",
    ("place", "sloppy"): "Заказ {order}, привезите по адресу {value}, после обеда.",
    ("place", "voice_itn"): "заказ {order} привезите {value} после обеда",
    ("place", "voice_raw"): "заказ {order} привезите {value} после обеда",
    ("person", "clean"): "Заказ {order}, звонили {value} — что решили?",
    ("person", "chat"): "заказ {order} звонили {value} что решили",
    ("person", "sloppy"): "Заказ {order}, звoнили {value} — что решили?",
    ("person", "voice_itn"): "заказ {order} звонили {value} что решили",
    ("person", "voice_raw"): "заказ {order} звонили {value} что решили",
    ("phone", "clean"): "Заказ {order}, перезвоните на {value}.",
    ("phone", "chat"): "заказ {order} перезвоните на {value}",
    ("phone", "sloppy"): "Заказ {order}, перeзвоните на {value}.",
    ("phone", "voice_itn"): "заказ {order} перезвоните на {value}",
    ("phone", "voice_raw"): "заказ {order} перезвоните на {value}",
}

# Primary tool and two distractors, per vehicle and per leg. NAMED rather than
# taken off the top of the registry — see `tools.tools_for`, where v1's
# insertion-order slice is the defect being avoided.
_TOOLS: dict[tuple[str, str], tuple[str, tuple[str, str]]] = {
    ("place", "lead"): ("update_delivery_address",
                        ("check_order_status", "escalate_ticket")),
    ("place", "follow"): ("schedule_delivery",
                          ("update_delivery_address", "check_order_status")),
    ("person", "lead"): ("lookup_order",
                         ("check_order_status", "escalate_ticket")),
    ("person", "follow"): ("lookup_order",
                           ("check_order_status", "escalate_ticket")),
    ("phone", "lead"): ("check_order_status",
                        ("update_delivery_address", "escalate_ticket")),
    ("phone", "follow"): ("schedule_callback",
                          ("check_order_status", "escalate_ticket")),
}

_PARAM: dict[tuple[str, str], str] = {
    ("place", "lead"): "address", ("place", "follow"): "address",
    ("person", "lead"): "customer_name", ("person", "follow"): "customer_name",
    ("phone", "lead"): "phone", ("phone", "follow"): "phone",
}

_TYPE: dict[str, str] = {"place": "LOC", "person": "NAME", "phone": "PHONE"}


def _message(vehicle: str, register: str, leg: str, order_surface: str,
             value: str) -> tuple[str, tuple[int, int], tuple[int, int]]:
    """The user turn, the value's offsets, and the order number's offsets.

    Both spans are recorded during assembly. The order number is a NEGATIVE and
    its offsets are not stored in the case — `Negative` carries a value, not a
    span — but they are computed anyway so the builder can refuse a template
    where the order number happens to land inside the labelled value. That
    collision is invisible to `validate()`, since both claims are individually
    correct, and it makes a search-based over-masking check report a false mask
    against a gateway that did nothing wrong.
    """
    template = (_LEAD_TEXT if leg == "lead" else _FOLLOW_TEXT)[(vehicle, register)]
    head, rest = template.split("{order}", 1)
    middle, tail = rest.split("{value}", 1)
    text, marks = _assemble([head, ("order", order_surface), middle,
                             ("value", value), tail])
    order_span, value_span = marks["order"], marks["value"]
    if order_span[0] < value_span[1] and order_span[1] > value_span[0]:
        raise ValueError(f"{vehicle}/{register}/{leg}: the order number lands "
                         f"inside the labelled value")
    if text.count(order_surface) != 1:
        raise ValueError(f"{vehicle}/{register}/{leg}: {order_surface!r} occurs "
                         f"more than once, so the negative cannot name one place")
    return text, value_span, order_span


def _case(direction: str, vehicle: str, register: str, leg: str, index: int,
          order: str, value: str, canonical: str, conversation: str,
          preceded_by: str, link: LinkExpectation | None) -> Case:
    """One leg of a pair. Both legs are ordinary cases in every other respect —
    the pairing lives entirely in `preceded_by` and in the link."""
    order_surface = _order(register, order)
    text, span, _ = _message(vehicle, register, leg, order_surface, value)
    param = _PARAM[(vehicle, leg)]
    # A SPOKEN PHONE CLAIMS NO TOOL PARAM. `carryover.py` set this precedent and
    # the reason survives here unchanged: demanding the dialable form back makes
    # every voice_raw phone a constant failure that reads as corruption, and
    # accepting the words back rewards a gateway that detected nothing. The
    # coverage axis scores it; the round trip does not also get to.
    spoken_phone = vehicle == "phone" and register == "voice_raw"
    item = PiiItem(
        id="value",
        type=_TYPE[vehicle],
        value=value,
        start=span[0],
        end=span[1],
        canonical=canonical,
        msg=1,
        identity=vehicle,
        duty="required",
        tool_param=None if spoken_phone else param,
    )
    primary, distractors = _TOOLS[(vehicle, leg)]
    # THE CALL CARRIES THE ORDER NUMBER AS THE CUSTOMER SAID IT, spelled words
    # included. Demanding the digit form in `voice_raw` would score the model on
    # inverse text normalisation in an argument the round trip never inspects —
    # an order number is not personal data. `indirect.py` made the same call for
    # the same reason.
    arguments: dict[str, str | int | float] = {param: canonical}
    if primary != "schedule_callback":
        arguments["order_id"] = order_surface
    calls = [] if spoken_phone else [ExpectedCall(
        name=primary, after_msg=1, arguments=arguments, pii_items=["value"])]
    return Case(
        id=f"{FAMILY}-{direction}-{vehicle}-{register}-{leg}-{index:02d}",
        family=FAMILY,
        scenario=f"{direction}_{vehicle}",
        register=register,
        # NOT CROSSED, and the constant says so rather than leaving the cases
        # looking easy. The design doc crosses difficulty inside `transfer` only:
        # elsewhere the family IS the difficulty, and a reader slicing this
        # corpus by difficulty must not read a uniform label as a measurement.
        difficulty="hard",
        length_rung="short",
        conversation_id=conversation,
        relation="equality",
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": text}],
        tools=tools_for(primary, distractors),
        pii=[item],
        preceded_by=preceded_by,
        annotators=0,
        adjudicated=False,
        negatives=[Negative(
            value=order_surface,
            why="номер заказа — не персональные данные, и он нужен модели в "
                "открытом виде, чтобы позвать инструмент",
            msg=1)],
        links=[] if link is None else [link],
    )


def _pair(direction: str, vehicle: str, register: str, index: int,
          explicit: bool) -> list[Case]:
    """A lead and a follow, in that order.

    THE ORDER IS LOAD-BEARING. `validate_corpus` refuses a `preceded_by` that
    points forward, because a vault group is scored in file order and a forward
    reference would be scored against an empty vault — the follow would find no
    earlier mention to link to and the family's positive claim would fail for a
    reason that has nothing to do with scope.
    """
    # THE SLOT IS STATED, not taken from the cell index. `within` draws the
    # first five of each pool and `across` the last five, so no two pairs of
    # one vehicle can ever share a value however `_CELLS` is later ordered.
    # Deriving it from `index % 10` happened to work and would have broken
    # silently the first time a register or a vehicle was added.
    slot = (0 if direction == "within" else 5) + REGISTERS.index(register)
    orders = _ORDERS[2 * index], _ORDERS[2 * index + 1]
    if vehicle == "place":
        place = _PLACES[slot]
        full, partial = _place_full(register, place), _place_partial(register, place)
        lead_value, lead_canonical = full, full
        follow_value, follow_canonical = partial, partial
    elif vehicle == "person":
        person = _PEOPLE[slot]
        full = _person_full(register, person)
        partial, nominative = _person_partial(register, person, bool(index % 2))
        lead_value, lead_canonical = full, full
        follow_value, follow_canonical = partial, nominative
    else:
        phone = _PHONES[slot]
        lead_value, lead_canonical = _phone_full(register, phone)
        follow_value, follow_canonical = _phone_partial(register, phone)

    # THE PHONE ARM LINKS IN BOTH DIRECTIONS, and it is the control. The vault is
    # keyed `(customer, canonical)` — tenant-wide by documented design — so
    # «+7 916…» and «916…» collapse to one key whatever conversation they were
    # said in. Without an arm that MUST link across conversations, a gateway that
    # had simply stopped linking would satisfy every `across` claim in this
    # family and score perfectly on the failure the family exists to detect.
    kind = "same" if direction == "within" or vehicle == "phone" else "different"
    why = {
        ("within", "same"):
            "частичное упоминание разрешается против полного в ТОМ ЖЕ разговоре "
            "— иначе модель получает два адреса там, где клиент назвал один",
        ("across", "different"):
            "то же частичное упоминание в ДРУГОМ разговоре: связать его значит "
            "отдать адрес одного клиента в диалог другого",
        ("across", "same"):
            "контрольное плечо: канонизация телефона общая для тенанта, поэтому "
            "эти два обязаны слиться — шлюз, переставший связывать вовсе, "
            "проходит все остальные требования across и валит это",
    }[(direction, kind)]

    lead_id = f"{FAMILY}-{direction}-{vehicle}-{register}-lead-{index:02d}"
    if direction == "within":
        # A SHARED SCOPE CAN ONLY BE HANDED OVER, never derived: two cases derive
        # two identities from two different transcripts by construction, so the
        # positive direction has no derived form and claiming one would be a
        # requirement the mechanism cannot meet.
        lead_scope = follow_scope = f"scope-{vehicle}-{register}-{index:02d}"
    elif explicit:
        lead_scope = f"scope-a-{vehicle}-{register}-{index:02d}"
        follow_scope = f"scope-b-{vehicle}-{register}-{index:02d}"
    else:
        lead_scope = follow_scope = ""
    return [
        _case(direction, vehicle, register, "lead", index, orders[0],
              lead_value, lead_canonical, lead_scope, "", None),
        _case(direction, vehicle, register, "follow", index, orders[1],
              follow_value, follow_canonical, follow_scope, lead_id,
              LinkExpectation(left="value", right="value", kind=kind,
                              case=lead_id, why=why)),
    ]


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases of the `scope` family. Two per pair, leads first.

    `rng` IS ACCEPTED AND UNUSED, like `speech.build`'s and for a related reason:
    there is nothing to draw. Every value in the family is assigned by cell so
    that no two pairs can share one — a shared address across pairs would let one
    pair's lead satisfy another pair's link, which is a corpus bug that reports as
    a gateway result. A seeded shuffle would buy variety and cost that guarantee.

    `count` must be EVEN and at most 60: a lone lead states no claim and a lone
    follow points at a case that is not in the file, which `validate_corpus`
    refuses by name.
    """
    if count < 0 or count % 2:
        raise ValueError(f"{FAMILY}: count must be a non-negative even number, "
                         f"got {count}; a case here is half of a pair")
    if count > 2 * len(_CELLS):
        raise ValueError(f"{FAMILY}: holds {2 * len(_CELLS)} cases "
                         f"({len(_CELLS)} pairs), {count} asked for")
    cases: list[Case] = []
    for index, (direction, vehicle, register) in enumerate(_CELLS):
        if len(cases) >= count:
            break
        cases.extend(_pair(direction, vehicle, register, index,
                           explicit=bool(index % 2)))
    return cases[:count]


SCOPE_CASE_COUNT: int = 2 * len(_CELLS)


def main() -> int:
    from bench.agentpii2.schema import case_characters, validate

    cases = build(random.Random(20260830), SCOPE_CASE_COUNT)
    problems = [problem for case in cases for problem in validate(case)]
    sizes = [case_characters(case) for case in cases]
    kinds: dict[str, int] = {}
    for case in cases:
        for link in case.links:
            kinds[link.kind] = kinds.get(link.kind, 0) + 1
    print(f"{FAMILY}: {len(cases)} cases ({len(_CELLS)} pairs)")
    print(f"   characters   {min(sizes)}-{max(sizes)} (short band is 0-400)")
    print(f"   links        {kinds}")
    print(f"   explicit id  {sum(1 for c in cases if c.conversation_id)}, "
          f"derived {sum(1 for c in cases if not c.conversation_id)}")
    print(f"   problems     {len(problems)}")
    for problem in problems[:20]:
        print(f"     {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
