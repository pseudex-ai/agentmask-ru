"""How the same personal datum is actually written by different people.

THIS IS THE POINT OF THE BENCHMARK. Every synthetic PII corpus is implicitly
written in one register — the tidy one a generator produces — and a detector
tuned on it scores well and then meets a support chat. The same phone is
«+7 916 214-88-03» in a web form, «89162148803» in a messenger, «8-916-214-88-О3»
when someone's keyboard slipped into Cyrillic, and «8 916 214 88 03» after
speech-to-text has stripped every separator it had.

The four registers are drawn from what those channels do to text, not from what
our detector currently survives:

  clean   a web form or a copy-paste from a document. Capitalised, punctuated,
          full patronymic, canonical separators.
  chat    a messenger. Lower case, patronymic dropped, separators dropped,
          city dropped because "everyone knows", run-on clauses.
  sloppy  typing errors that survive into production: a Latin letter inside a
          Cyrillic word (the `o`/`о` and `a`/`а` pairs are indistinguishable on
          screen), a Cyrillic `О` typed for a zero, missing spaces.
  voice   speech-to-text. Digits survive as digits — modern ASR normalises them
          — but punctuation, capitals and sentence boundaries do not, and filler
          words the speaker used are transcribed verbatim.

NAMES INCLUDE FOREIGN ONES ON PURPOSE. Measured on NEREL, our recall on Russian
names is 81% and nearly every miss is foreign (Обама, Месси, Акихито). A corpus
of only Russian surnames would hide that, and a Russian shop with foreign
customers is not an edge case.
"""

import random

# --- source pools ---------------------------------------------------------
#
# Authored from the domain, not from the detector's vocabulary. Overlap with the
# leased gazetteer is unavoidable — Russian names are Russian names — but no
# entry is here BECAUSE we detect it, which is the independence that matters.

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
# Deliberately hostile to suffix rules: no -ов/-ев/-ин, several non-Slavic.
FOREIGN: tuple[tuple[str, str, str], ...] = (
    ("Ким", "Виктор", ""), ("Тагиев", "Рустам", ""), ("Мкртчян", "Ашот", ""),
    ("Шевчук", "Олесь", ""), ("Гулиев", "Эльдар", ""), ("Абдуллаев", "Тимур", ""),
    ("Саркисян", "Карен", ""), ("Нгуен", "Ань", ""), ("Мамедова", "Лейла", ""),
    ("Валиахметов", "Ильдар", ""), ("Джонсон", "Майкл", ""), ("Ли", "Чен", ""),
)
DIMINUTIVE: dict[str, str] = {
    "Пётр": "Петя", "Дмитрий": "Дима", "Алексей": "Лёша", "Сергей": "Серёжа",
    "Максим": "Макс", "Мария": "Маша", "Анна": "Аня", "Ольга": "Оля",
    "Екатерина": "Катя", "Татьяна": "Таня", "Светлана": "Света",
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

# Non-PII values that share a shape with personal data. Every case carries some.
ORDER_PREFIXES: tuple[str, ...] = ("A-", "№", "ORD-", "Z", "")


# --- per-register rendering ----------------------------------------------

def render_name(surname: str, first: str, patronymic: str, register: str,
                rng: random.Random) -> str:
    """A person's name as this channel would carry it."""
    if register == "clean":
        return " ".join(part for part in (surname, first, patronymic) if part)
    if register == "chat":
        # Patronymic is the first thing a messenger drops, and capitals go with
        # it. A detector that needs «Иванов Пётр Сергеевич» to fire sees nothing.
        name = f"{surname} {first}" if rng.random() < 0.6 else f"{first} {surname}"
        return name.lower()
    if register == "sloppy":
        base = f"{surname} {first}"
        return _latin_slip(base, rng)
    # voice: ASR keeps the words, drops the capitals, and often drops the surname
    # when the speaker only said a first name.
    if rng.random() < 0.3:
        return first.lower()
    return f"{first} {surname}".lower()


def render_phone(digits: str, register: str, rng: random.Random) -> str:
    """`digits` is ten digits without a country code."""
    a, b, c, d = digits[:3], digits[3:6], digits[6:8], digits[8:]
    if register == "clean":
        return f"+7 {a} {b}-{c}-{d}"
    if register == "chat":
        return rng.choice([f"8{digits}", f"+7{digits}", f"8 {a} {b} {c} {d}"])
    if register == "sloppy":
        # A Cyrillic О typed where a zero belongs is the single commonest
        # obfuscation that is not an obfuscation — it is a keyboard slip.
        formatted = f"8-{a}-{b}-{c}-{d}"
        return formatted.replace("0", "О", 1) if "0" in formatted else formatted
    return f"8 {a} {b} {c} {d}"      # voice: separators become spaces


def render_address(city: str, street: str, house: int, flat: int,
                   register: str, rng: random.Random) -> str:
    if register == "clean":
        return f"{city}, {street}, д. {house}, кв. {flat}"
    if register == "chat":
        # City dropped: in a shop's own chat the city is assumed.
        return f"{street.lower()} {house} кв {flat}"
    if register == "sloppy":
        return _latin_slip(f"{street} {house}кв{flat}", rng)
    return f"{street.lower()} {house} квартира {flat}"


def render_passport(series: str, number: str, register: str) -> str:
    if register == "clean":
        return f"{series} {number}"
    if register in ("chat", "sloppy"):
        return f"{series}{number}"
    return f"{series} {number}"


def render_snils(digits: str, register: str) -> str:
    body, check = digits[:9], digits[9:]
    if register == "clean":
        return f"{body[:3]}-{body[3:6]}-{body[6:9]} {check}"
    return digits


def render_card(digits: str, register: str) -> str:
    if register == "clean":
        return " ".join(digits[i:i + 4] for i in range(0, 16, 4))
    return digits


def _latin_slip(text: str, rng: random.Random) -> str:
    """Swap one Cyrillic letter for its identical-looking Latin twin.

    Not an attack — a real typing accident on a keyboard that switched layout
    mid-word. The result is indistinguishable on screen and breaks any matcher
    that assumes a Cyrillic word is Cyrillic all the way through.
    """
    twins = {"о": "o", "а": "a", "е": "e", "с": "c", "р": "p", "у": "y",
             "х": "x", "О": "O", "А": "A", "Е": "E", "С": "C", "Р": "P"}
    positions = [i for i, ch in enumerate(text) if ch in twins]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + twins[text[index]] + text[index + 1:]


# --- assembly -------------------------------------------------------------

def assemble(parts: list[object]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Build a message and the offsets of its tracked slots in one pass.

    A plain `str` is literal text; a `(name, value)` tuple is a slot whose span
    is recorded. Computing offsets during assembly rather than by searching the
    finished string is what keeps ground truth honest: a search finds the FIRST
    occurrence, and a message that mentions the same phone twice would then carry
    a span pointing at the wrong one.
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


# NOTE: there is deliberately NO post-processing pass over the finished message.
# An earlier version stripped punctuation after assembly, which changes the
# string length and silently invalidates every span computed before it — a
# corpus whose ground truth points a few characters to the left still scores,
# and scores wrongly. Register belongs in the template and in the slot values,
# both of which are chosen before `assemble` counts a single character.
