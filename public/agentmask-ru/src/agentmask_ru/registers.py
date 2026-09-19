"""How the same personal datum is written in different registers.

Every synthetic PII corpus is implicitly written in one register — the tidy
one its generator produces — and a detector tuned on it meets support chat
and fails. Three registers here, ordered by distance from a form:

  clean   «Петров Иван Сергеевич», «+7 907 123-45-67», «г. Казань, ул. Большая Садовая, д. 12, кв. 5»
  chat    «иван петров», «89071234567», «казань большая садовая 12 кв 5»
  sloppy  the chat form plus ONE generic slip: two letters swapped, a letter
          dropped, a Latin twin of a Cyrillic letter, a separator lost

THE SLOPPY REGISTER IS DELIBERATELY GENERIC. A mined table of real typos
(which letters people actually confuse, at which rates) would make this a
sharper instrument — and would also encode a detector's tuning into the
benchmark. The one-edit rule is what any reader can reproduce from the
description alone.

GROUND TRUTH IS WHAT WAS WRITTEN. The value with the slip in it is the value
the tool is owed: a gateway that «repairs» the customer's phone has changed
the customer's data.
"""

import random
from dataclasses import dataclass

from agentmask_ru.pools import Person, Street

# Cyrillic letters with a visually identical Latin twin — the slip a mixed
# keyboard layout produces.
_LATIN_TWIN: dict[str, str] = {"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Х": "X"}

# A minimal, conventional transliteration for e-mail local parts. Not a
# standard anybody restores by; the local part is never a ground-truth NAME.
_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "-": "",
}
_EMAIL_DOMAINS: tuple[str, ...] = ("mail.ru", "yandex.ru", "gmail.com", "bk.ru", "rambler.ru", "inbox.ru")
_MONTHS_GEN: tuple[str, ...] = (
    "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
_STREET_ABBR: dict[str, str] = {
    "улица": "ул.", "переулок": "пер.", "проспект": "просп.", "шоссе": "ш.", "бульвар": "б-р", "набережная": "наб.",
    "площадь": "пл.", "проезд": "пр-д", "аллея": "ал.", "тупик": "туп.",
}


@dataclass(frozen=True)
class Rendered:
    value: str           # as written in the message
    cue: str             # the cue word the template may put in front, register-appropriate
    shape_broken: bool   # a slip destroyed the shape a pattern would match


# --- one generic slip --------------------------------------------------------

def slip(word: str, rng: random.Random) -> str:
    """Apply exactly one slip to a Cyrillic word of four letters or more;
    shorter words come back unchanged (a slip in «Ли» is a different name)."""
    letters = [i for i, ch in enumerate(word) if ch.isalpha()]
    if len(letters) < 4:
        return word
    kind = rng.choice(("swap", "drop", "twin"))
    inner = letters[1:-1]
    if kind == "swap":
        i = rng.choice(inner[:-1]) if len(inner) > 1 else inner[0]
        j = i + 1
        if j < len(word) and word[j].isalpha():
            chars = list(word)
            chars[i], chars[j] = chars[j], chars[i]
            return "".join(chars)
        return word
    if kind == "drop":
        i = rng.choice(inner)
        return word[:i] + word[i + 1:]
    twins = [i for i in letters if word[i] in _LATIN_TWIN]
    if not twins:
        i = rng.choice(inner)
        return word[:i] + word[i + 1:]
    i = rng.choice(twins)
    return word[:i] + _LATIN_TWIN[word[i]] + word[i + 1:]


def slip_digits(value: str, rng: random.Random) -> tuple[str, bool]:
    """One slip in a digit string, and whether it BREAKS THE SHAPE.

    A Cyrillic «О» standing in for a zero breaks every digit pattern — the
    value stops looking like a phone to a regex, which is why a benchmark
    has to say so: a naive masker misses it for a reason that is about the
    register, not about the masker being careless. Losing or gaining a
    separator does not break the shape, so it returns False.
    """
    zeros = [i for i, ch in enumerate(value) if ch == "0"]
    if zeros and rng.random() < 0.5:
        i = rng.choice(zeros)
        return value[:i] + "О" + value[i + 1:], True
    if " " in value or "-" in value:
        seps = [i for i, ch in enumerate(value) if ch in " -"]
        i = rng.choice(seps)
        return value[:i] + value[i + 1:], False
    digits = [i for i, ch in enumerate(value) if ch.isdigit()]
    i = rng.choice(digits[2:-2])
    return value[:i] + " " + value[i:], True


# --- names ----------------------------------------------------------------

def name_parts(person: Person, register: str, rng: random.Random) -> tuple[str, ...]:
    """The written parts of a name in register order. Clean writes Ф И О or
    И О Ф; chat writes «имя фамилия» in lower case; sloppy is chat with one
    slip in one part."""
    if register == "clean":
        if person.patronymic and rng.random() < 0.6:
            return (person.surname.name, person.given.name, person.patronymic)
        return (person.given.name, person.surname.name)
    parts = (person.given.name.lower(), person.surname.name.lower())
    if register == "sloppy":
        which = rng.randrange(2)
        slipped = slip(parts[which], rng)
        return (slipped, parts[1]) if which == 0 else (parts[0], slipped)
    return parts


def render_name(person: Person, register: str, rng: random.Random) -> Rendered:
    parts = name_parts(person, register, rng)
    return Rendered(value=" ".join(parts), cue="ФИО" if register == "clean" else "меня зовут", shape_broken=False)


def given_only(person: Person, register: str, rng: random.Random) -> Rendered:
    """A first-name-only mention, as a customer signs a chat message."""
    name = person.given.name if register == "clean" else person.given.name.lower()
    if register == "sloppy":
        name = slip(name, rng)
    return Rendered(value=name, cue="", shape_broken=False)


# A schoolbook declension of the two name parts a support agent inflects.
# Deliberately shallow: masculine -ов/-ев/-ин and feminine -ова/-ева/-ина
# surnames, given names by their last letter. Anything else (Смит, Ким,
# Билык) stays as written, which is also what Russian does with them.

def _decline_given(name: str, gender: str, case: str) -> str:
    low = name.lower()
    if gender == "m":
        if low.endswith("й"):
            return name[:-1] + {"gen": "я", "acc": "я", "dat": "ю"}[case]
        if low.endswith("ь"):
            return name[:-1] + {"gen": "я", "acc": "я", "dat": "ю"}[case]
        if low.endswith("а"):
            return name[:-1] + {"gen": "ы", "acc": "у", "dat": "е"}[case]
        if low.endswith("я"):
            return name[:-1] + {"gen": "и", "acc": "ю", "dat": "е"}[case]
        if low[-1] in "бвгджзклмнпрстфхцчшщ":
            return name + {"gen": "а", "acc": "а", "dat": "у"}[case]
        return name
    if low.endswith("а"):
        return name[:-1] + {"gen": "ы", "acc": "у", "dat": "е"}[case]
    if low.endswith("я"):
        return name[:-1] + {"gen": "и", "acc": "ю", "dat": "е"}[case]
    return name


def _decline_surname(name: str, gender: str, case: str) -> str:
    low = name.lower()
    if gender == "m" and low.endswith(("ов", "ев", "ёв", "ин", "ын")):
        return name + {"gen": "а", "acc": "а", "dat": "у"}[case]
    if gender == "m" and low.endswith(("ский", "цкий")):
        return name[:-2] + {"gen": "ого", "acc": "ого", "dat": "ому"}[case]
    if gender == "f" and low.endswith(("ова", "ева", "ёва", "ина", "ына")):
        return name[:-1] + {"gen": "ой", "acc": "у", "dat": "ой"}[case]
    if gender == "f" and low.endswith(("ская", "цкая")):
        return name[:-2] + {"gen": "ой", "acc": "ую", "dat": "ой"}[case]
    return name


def declined_name(person: Person, case: str, lower: bool) -> str:
    """«Петрова Ивана» / «петрову ивану» — surname first, as a form field or
    an agent's confirmation would have it."""
    surname = _decline_surname(person.surname.name, person.gender, case)
    given = _decline_given(person.given.name, person.gender, case)
    text = f"{surname} {given}"
    return text.lower() if lower else text


# --- phones and structured identifiers ------------------------------------

def render_phone(digits10: str, register: str, rng: random.Random) -> Rendered:
    a, b, c, d = digits10[:3], digits10[3:6], digits10[6:8], digits10[8:]
    if register == "clean":
        value = rng.choice((f"+7 {a} {b}-{c}-{d}", f"+7 ({a}) {b}-{c}-{d}", f"8 ({a}) {b}-{c}-{d}"))
        return Rendered(value=value, cue="телефон", shape_broken=False)
    value = rng.choice((f"8{digits10}", f"+7{digits10}", f"8 {a} {b}{c}{d}", f"8{a}{b}{c}{d}"))
    broken = False
    if register == "sloppy":
        value, broken = slip_digits(value, rng)
    return Rendered(value=value, cue="тел", shape_broken=broken)


def reformat_phone(written: str, rng: random.Random) -> str:
    """What a model does to a phone it copies: strips the separators and
    swaps the prefix. Used by the `reformat` policy, on the SUBSTITUTE."""
    digits = "".join(ch for ch in written if ch.isdigit())
    if len(digits) == 11 and digits[0] in "78":
        national = digits[1:]
    elif len(digits) == 10:
        national = digits
    else:
        return written
    return rng.choice((f"8{national}", f"+7{national}", f"+7 {national[:3]} {national[3:6]} {national[6:8]} {national[8:]}"))


def render_email(person: Person, rng: random.Random) -> Rendered:
    local = "".join(_TRANSLIT.get(ch, ch) for ch in person.given.name.lower()) + "." + \
        "".join(_TRANSLIT.get(ch, ch) for ch in person.surname.name.lower())
    if rng.random() < 0.5:
        local += str(rng.randint(70, 99))
    return Rendered(value=f"{local}@{rng.choice(_EMAIL_DOMAINS)}", cue="почта", shape_broken=False)


def render_snils(value: str, register: str, rng: random.Random) -> Rendered:
    if register == "clean":
        return Rendered(value=value, cue="СНИЛС", shape_broken=False)
    digits = "".join(ch for ch in value if ch.isdigit())
    written = rng.choice((digits, f"{digits[:3]} {digits[3:6]} {digits[6:9]} {digits[9:]}"))
    broken = register != "clean"   # the bare digit run already lost the dashes a pattern keys on
    if register == "sloppy":
        written, _ = slip_digits(written, rng)
    return Rendered(value=written, cue="снилс", shape_broken=broken)


def render_inn(value: str, register: str, rng: random.Random) -> Rendered:
    written = value
    broken = False
    if register == "sloppy":
        written, broken = slip_digits(written, rng)
    return Rendered(value=written, cue="ИНН" if register == "clean" else "инн", shape_broken=broken)


def render_passport(value: str, register: str, rng: random.Random) -> Rendered:
    if register == "clean":
        return Rendered(value=value, cue="паспорт", shape_broken=False)
    digits = "".join(ch for ch in value if ch.isdigit())
    written = rng.choice((digits, f"{digits[:4]} {digits[4:]}", f"{digits[:2]} {digits[2:4]} {digits[4:]}"))
    broken = False
    if register == "sloppy":
        written, broken = slip_digits(written, rng)
    return Rendered(value=written, cue="паспорт", shape_broken=broken)


def render_card(value: str, register: str, rng: random.Random) -> Rendered:
    if register == "clean":
        return Rendered(value=value, cue="карта", shape_broken=False)
    digits = value.replace(" ", "")
    written = rng.choice((digits, value))
    broken = False
    if register == "sloppy":
        written, broken = slip_digits(written, rng)
    return Rendered(value=written, cue="карта", shape_broken=broken)


def render_dob(date: tuple[int, int, int], register: str, rng: random.Random) -> Rendered:
    day, month, year = date
    if register == "clean":
        return Rendered(value=f"{day:02d}.{month:02d}.{year}", cue="дата рождения", shape_broken=False)
    written = rng.choice((f"{day:02d}.{month:02d}.{year}", f"{day}.{month}.{year % 100:02d}", f"{day} {_MONTHS_GEN[month - 1]} {year}"))
    if register == "sloppy":
        written = written.replace(".", "/") if "." in written else written
    return Rendered(value=written, cue="др" if register != "clean" else "дата рождения", shape_broken=False)


# --- addresses --------------------------------------------------------------

def render_address(city: str, street: Street, house: int, flat: int, register: str, rng: random.Random) -> Rendered:
    if register == "clean":
        abbr = _STREET_ABBR[street.type]
        value = rng.choice((
            f"г. {city}, {abbr} {street.name}, д. {house}, кв. {flat}",
            f"{city}, {street.type} {street.name}, дом {house}, квартира {flat}",
            f"{abbr} {street.name}, {house}, кв. {flat}",
        ))
        return Rendered(value=value, cue="адрес", shape_broken=False)
    name = street.name.lower()
    if register == "sloppy":
        words = name.split()
        i = rng.randrange(len(words))
        words[i] = slip(words[i], rng)
        name = " ".join(words)
    value = rng.choice((
        f"{city.lower()} {name} {house} кв {flat}",
        f"{name} {house} кв {flat}",
        f"{street.type} {name} д{house} кв{flat}",
    ))
    return Rendered(value=value, cue="адрес", shape_broken=False)
