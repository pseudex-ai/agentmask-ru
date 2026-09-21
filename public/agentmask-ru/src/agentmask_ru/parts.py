"""Cutting a value into the parts a tool wants — one rule for the gold and
for the scripted agent.

A CRM card does not take «Иванов Пётр Сергеевич» in one field; it takes
`last_name`, `first_name`, `middle_name`. A courier form takes `street`,
`house`, `flat`. The agent has to cut what it was shown, and here the
maskers part company: a format-preserving substitute («Рыбаков Родион
Павлович», «улица Полевая 52, кв. 194») cuts the way the original cuts; a
placeholder («<PERSON_1>», «[ADDRESS]») cannot be cut at all, and the whole
of it lands in the first field with the others empty. The corpus records the
gold parts cut by THIS rule from the ORIGINAL, and the policy cuts the
SUBSTITUTE by the same rule, so a difference between the two is a difference
in what the masker showed, never in how the benchmark read it.

The name rule is positional: the case says which position of the written name
is which part («Ф И О» in a form, «имя фамилия» in a chat), because a
Russian speaker reads the order off the register and the substitute mirrors
the original position for position. The address rule is a regex over the
shapes the registers write: a house number after «д.»/«дом»/bare, a flat
after «кв»/«квартира», the street in front, a city in front of that.
"""

import re

_FLAT = re.compile(r"(?i)\b(?:кв\.?|квартира)\s*(\d+\s*[а-яё]?)\s*$")
_HOUSE = re.compile(r"(?i)(?:\b(?:д\.?|дом)\s*)?(\d+\s*[а-яё]?)\s*,?\s*$")
_CITY_FIRST = re.compile(r"^\s*(?:г\.?\s*)?([А-ЯЁа-яё-]+)\s*,\s*(.+)$")


def cut_name(shown: str, order: tuple[str, ...]) -> dict[str, str]:
    """`shown` split by whitespace into the parts named by `order`, position
    for position. Fewer words than parts — a placeholder, or a masker that
    dropped a part — fill the first positions and leave the rest empty; more
    words are joined into the last part, so nothing is silently lost."""
    words = shown.split()
    out: dict[str, str] = {name: "" for name in order}
    if not words:
        return out
    if len(words) <= len(order):
        for name, word in zip(order, words):
            out[name] = word
        return out
    head = len(order) - 1
    for name, word in zip(order[:head], words[:head]):
        out[name] = word
    out[order[-1]] = " ".join(words[head:])
    return out


def cut_address(shown: str, with_city: bool) -> dict[str, str]:
    """`shown` cut into `city` (when the case wrote one), `street`, `house`,
    `flat`. A string the rule cannot read (a placeholder) goes whole into
    `street`, the numbers stay empty."""
    text = shown.strip()
    out: dict[str, str] = {"street": "", "house": "", "flat": ""}
    if with_city:
        out = {"city": "", **out}
    flat = _FLAT.search(text)
    if flat:
        out["flat"] = flat.group(1).strip()
        text = text[:flat.start()].rstrip(" ,")
    house = _HOUSE.search(text)
    if house and house.group(1):
        out["house"] = house.group(1).strip()
        text = text[:house.start()].rstrip(" ,")
    if with_city:
        city = _CITY_FIRST.match(text)
        if city:
            out["city"] = city.group(1)
            text = city.group(2)
        else:
            # A chat address puts the city first without a comma: the first
            # word is the city when the case says a city was written.
            first, _, rest = text.partition(" ")
            if rest:
                out["city"], text = first, rest
    out["street"] = text.strip(" ,")
    return out
