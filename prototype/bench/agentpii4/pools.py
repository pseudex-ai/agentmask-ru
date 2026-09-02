"""Shared PII pools, generators, numeral spelling and register noise.

WHY THIS MODULE EXISTS. v3 has no shared pool: every family carries its own
private copy of the names, the streets, the checksummed generators and the
numeral spellers, and importing any of them executes a read of
`~/.cache/pseudex-bench/speech_rudevices.jsonl` at module load. A fifth
in-place copy would be one more list that has to stay equal to four others.
This file is lifted from `families/direct.py` and `families/spoken_id.py`,
minus the import-time I/O, and is the ONE place v4 draws a value from.

TWO INVARIANTS EVERY VALUE HERE OBEYS:

  * every identifier passes its own published checksum. A ground truth
    claiming a document that is not one would score a checksum-gated detector
    as wrong for being right;
  * every spoken rendering parses back to the digits it was built from
    (`parse_numerals`), or the draw is refused. A rendering a listener cannot
    resolve is a ground truth the message did not carry.

Declined forms are written out rather than computed: computing them needs the
morphology the gateway itself is measured on, and a pool declined by pymorphy3
would hand the corpus the engine's own opinion as ground truth.

Nothing here imports `pseudex`. The benchmark's own values must not be built
by the instrument they measure.
"""
import random
import re
from dataclasses import dataclass


class BuildError(ValueError):
    """A generator produced something the corpus may not carry."""


# --- numbers as words -----------------------------------------------------

UNITS: tuple[str, ...] = ("ноль", "один", "два", "три", "четыре", "пять",
                          "шесть", "семь", "восемь", "девять")
TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
TENS: tuple[str, ...] = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят",
                         "шестьдесят", "семьдесят", "восемьдесят", "девяносто")
HUNDREDS: tuple[str, ...] = ("", "сто", "двести", "триста", "четыреста",
                             "пятьсот", "шестьсот", "семьсот", "восемьсот",
                             "девятьсот")
ORDINALS: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой", "седьмой",
    "восьмой", "девятый", "десятый", "одиннадцатый", "двенадцатый")

# Measured on the call corpus: 22.9% of every «-десят» form arrives contracted,
# and numerals arrive truncated mid-word. The norm of the register, not an
# adversarial perturbation. Every variant parses back through `parse_numerals`.
ASR_VARIANTS: dict[str, tuple[str, ...]] = {
    "пятьдесят": ("песят", "пеесят", "пяесят", "пейсят", "пясят"),
    "шестьдесят": ("шеесят", "шейсят", "шесят"),
    "восемьдесят": ("восемесят",),
    "тридцать": ("триц", "тридц", "трис"),
    "девяносто": ("девяно",),
    "семьсот": ("семест",),
    "восемьсот": ("восемест", "восемьст"),
    "триста": ("тристо", "трииста"),
    "шестьсот": ("шессот",),
    "восемь": ("восем", "восемсь"),
    "пять": ("пяять",),
    "четыре": ("четыыре",),
    "одиннадцать": ("одинадцать",),
}
_VARIANT_TO_CANONICAL: dict[str, str] = {
    variant: canonical
    for canonical, variants in ASR_VARIANTS.items() for variant in variants}
_ZERO_WORDS: frozenset[str] = frozenset({"ноль", "нуль"})
_UNIT_VALUE: dict[str, int] = {word: value for value, word in enumerate(UNITS) if value}
_TEEN_VALUE: dict[str, int] = {word: 10 + offset for offset, word in enumerate(TEENS)}
_TENS_VALUE: dict[str, int] = {word: tens * 10 for tens, word in enumerate(TENS) if word}
_HUNDRED_VALUE: dict[str, int] = {
    word: hundreds * 100 for hundreds, word in enumerate(HUNDREDS) if word}


def spell_cardinal(value: int) -> str:
    """0..999 in words. Masculine nominative, which is what a house number is."""
    if not 0 <= value <= 999:
        raise BuildError(f"{value} is outside the range this register spells")
    if value < 10:
        return UNITS[value]
    if value < 20:
        return TEENS[value - 10]
    words: list[str] = []
    hundreds, rest = divmod(value, 100)
    if hundreds:
        words.append(HUNDREDS[hundreds])
    if rest >= 20:
        tens, unit = divmod(rest, 10)
        words.append(TENS[tens])
        if unit:
            words.append(UNITS[unit])
    elif rest >= 10:
        words.append(TEENS[rest - 10])
    elif rest:
        words.append(UNITS[rest])
    return " ".join(words)


def spell_ordinal(value: int) -> str:
    if not 1 <= value <= 12:
        raise BuildError(f"no spoken ordinal for {value} in this pool")
    return ORDINALS[value]


def _spell_chunk(chunk: str) -> tuple[str, ...]:
    """One group of one to three digits, as a caller says it.

    A leading zero is its own word — «ноль сорок два» for 042 — because that
    is how the corpus does it and because it keeps the group's WIDTH readable
    to the parser, which is what makes the digits recoverable at all.
    """
    if not 1 <= len(chunk) <= 3 or not chunk.isdigit():
        raise BuildError(f"a spoken group is one to three digits, not {chunk!r}")
    words: list[str] = []
    body = chunk
    while len(body) > 1 and body[0] == "0":
        words.append("ноль")
        body = body[1:]
    value = int(body)
    if len(body) == 3:
        words.append(HUNDREDS[value // 100])
        if value % 100:
            words.extend(spell_cardinal(value % 100).split())
    elif len(body) == 2:
        words.extend(spell_cardinal(value).split())
    else:
        words.append(UNITS[value])
    return tuple(words)


def spell_groups(digits: str, sizes: tuple[int, ...]) -> tuple[str, ...]:
    """A digit string cut into groups and spoken.

    The cut is NOT free: «триста» followed by «сорок два» is heard as 342, so a
    group ending in a bare hundreds or tens word swallows the next group's
    head. Callers redraw until `parse_numerals` gives the digits back.
    """
    if sum(sizes) != len(digits):
        raise BuildError(f"group sizes {sizes} do not add up to {len(digits)} digits")
    words: list[str] = []
    position = 0
    for size in sizes:
        words.extend(_spell_chunk(digits[position:position + size]))
        position += size
    return tuple(words)


def parse_numerals(words: tuple[str, ...]) -> str:
    """Greedy left-to-right, exactly as a listener does it.

    «ноль» never joins the group in front of it. A hundreds word opens a
    three-wide group and may absorb a tens word and then a unit; a tens word
    opens a two-wide group and may absorb a unit; a teen and a unit close
    immediately. Everything else raises: a numeral this parser does not know
    inside a value means the ground truth was written by a speller the check
    does not cover.
    """
    digits: list[str] = []
    index = 0
    while index < len(words):
        word = _VARIANT_TO_CANONICAL.get(words[index], words[index])
        if word in _ZERO_WORDS:
            digits.append("0")
            index += 1
            continue
        if word in _HUNDRED_VALUE:
            value = _HUNDRED_VALUE[word]
            index += 1
            if index < len(words):
                following = _VARIANT_TO_CANONICAL.get(words[index], words[index])
                if following in _TENS_VALUE:
                    value += _TENS_VALUE[following]
                    index += 1
                    if index < len(words):
                        third = _VARIANT_TO_CANONICAL.get(words[index], words[index])
                        if third in _UNIT_VALUE:
                            value += _UNIT_VALUE[third]
                            index += 1
                elif following in _TEEN_VALUE:
                    value += _TEEN_VALUE[following]
                    index += 1
                elif following in _UNIT_VALUE:
                    value += _UNIT_VALUE[following]
                    index += 1
            digits.append(f"{value:03d}")
            continue
        if word in _TENS_VALUE:
            value = _TENS_VALUE[word]
            index += 1
            if index < len(words):
                following = _VARIANT_TO_CANONICAL.get(words[index], words[index])
                if following in _UNIT_VALUE:
                    value += _UNIT_VALUE[following]
                    index += 1
            digits.append(f"{value:02d}")
            continue
        if word in _TEEN_VALUE:
            digits.append(f"{_TEEN_VALUE[word]:02d}")
            index += 1
            continue
        if word in _UNIT_VALUE:
            digits.append(str(_UNIT_VALUE[word]))
            index += 1
            continue
        raise BuildError(f"{word!r} is not a numeral this pool can decode")
    return "".join(digits)


def spell_year(year: int) -> str:
    """«восемьдесят пятого года» — a year is spoken as an ordinal in the genitive."""
    tail = year % 100
    tens, unit = divmod(tail, 10)
    genitive = ("", "первого", "второго", "третьего", "четвёртого", "пятого",
                "шестого", "седьмого", "восьмого", "девятого")
    if tail == 0:
        return "двухтысячного"
    if 10 <= tail < 20:
        return TEENS[tail - 10] + "го"
    if unit == 0:
        return {2: "двадцатого", 3: "тридцатого", 4: "сорокового",
                5: "пятидесятого", 6: "шестидесятого", 7: "семидесятого",
                8: "восьмидесятого", 9: "девяностого"}[tens]
    return f"{TENS[tens]} {genitive[unit]}" if tens >= 2 else genitive[unit]


def asr_noise(words: tuple[str, ...], stream: random.Random,
              share: float) -> tuple[str, ...]:
    """Decoder slips at the measured rate. Every slip stays decodable."""
    noised: list[str] = []
    for word in words:
        variants = ASR_VARIANTS.get(word)
        if variants and stream.random() < share:
            noised.append(stream.choice(variants))
        else:
            noised.append(word)
    return tuple(noised)


# --- keyboard damage, a different thing from ASR damage --------------------

_ADJACENT: dict[str, str] = {
    "й": "цф", "ц": "йу", "у": "цк", "к": "уе", "е": "кн", "н": "ег",
    "г": "нш", "ш": "гщ", "щ": "шз", "з": "щх", "х": "зъ",
    "ф": "йы", "ы": "фв", "в": "ыа", "а": "вп", "п": "ар", "р": "по",
    "о": "рл", "л": "од", "д": "лж", "ж": "дэ", "э": "ж",
    "я": "ыч", "ч": "яс", "с": "чм", "м": "си", "и": "мт", "т": "иь",
    "ь": "тб", "б": "ью", "ю": "б",
}


def typo(word: str, stream: random.Random) -> str:
    """Exactly one keyboard-shaped edit; never two."""
    if len(word) < 4:
        return word
    kind = stream.choice(("swap", "drop", "double", "transpose"))
    position = stream.randrange(1, len(word) - 1)
    if kind == "swap" and word[position] in _ADJACENT:
        return word[:position] + stream.choice(_ADJACENT[word[position]]) + word[position + 1:]
    if kind == "drop":
        return word[:position] + word[position + 1:]
    if kind == "double":
        return word[:position] + word[position] + word[position:]
    return word[:position] + word[position + 1] + word[position] + word[position + 2:]


def phonetic_slip(word: str, stream: random.Random) -> str:
    """A transcription error INSIDE a value — «лермонтого», «кузнецого»."""
    if word.endswith("ова"):
        return word[:-3] + "ого"
    vowels = [index for index, letter in enumerate(word[2:-2], start=2)
              if letter in "аеиоуыэюяё"]
    if not vowels:
        return word
    position = stream.choice(vowels)
    return word[:position] + word[position + 1:]


_PARTICLE_HOSTS: frozenset[str] = frozenset({
    "адрес", "фамилия", "телефон", "приезжай", "приезжайте", "записывай",
    "какой", "звоните", "номер", "запишите"})


def speech_noise(word: str, stream: random.Random) -> str:
    """A glued particle or a stretched vowel on an ORDINARY word beside a value."""
    if not word or " " in word:
        return word
    roll = stream.randrange(100)
    if roll < 12 and word in _PARTICLE_HOSTS:
        return word + "то"
    if roll < 26:
        vowels = [index for index, letter in enumerate(word) if letter in "аеиоуыэюяё"]
        if vowels:
            position = vowels[-1]
            return word[:position + 1] + word[position] + word[position + 1:]
    return word


# --- people ---------------------------------------------------------------

@dataclass(frozen=True)
class Person:
    """Each part is (nominative, dative, accusative), written out by hand."""

    surname: tuple[str, str, str]
    given: tuple[str, str, str]
    patronymic: tuple[str, str, str]
    short_patronymic: str
    gender: str          # "m" | "f"


MALE: tuple[Person, ...] = (
    Person(("букин", "букину", "букина"), ("сергей", "сергею", "сергея"),
           ("иванович", "ивановичу", "ивановича"), "иваныч", "m"),
    Person(("васильев", "васильеву", "васильева"), ("иван", "ивану", "ивана"),
           ("павлович", "павловичу", "павловича"), "палыч", "m"),
    Person(("кукушкин", "кукушкину", "кукушкина"), ("валерий", "валерию", "валерия"),
           ("михайлович", "михайловичу", "михайловича"), "михалыч", "m"),
    Person(("ерохин", "ерохину", "ерохина"), ("пётр", "петру", "петра"),
           ("николаевич", "николаевичу", "николаевича"), "николаич", "m"),
    Person(("вольнов", "вольнову", "вольнова"), ("евгений", "евгению", "евгения"),
           ("александрович", "александровичу", "александровича"), "алексаныч", "m"),
    Person(("битюков", "битюкову", "битюкова"), ("олег", "олегу", "олега"),
           ("викторович", "викторовичу", "викторовича"), "викторыч", "m"),
    Person(("фомин", "фомину", "фомина"), ("вячеслав", "вячеславу", "вячеслава"),
           ("степанович", "степановичу", "степановича"), "степаныч", "m"),
    Person(("миллер", "миллеру", "миллера"), ("валерий", "валерию", "валерия"),
           ("леонидович", "леонидовичу", "леонидовича"), "леонидыч", "m"),
    Person(("заболотный", "заболотному", "заболотного"), ("руслан", "руслану", "руслана"),
           ("фёдорович", "фёдоровичу", "фёдоровича"), "фёдорыч", "m"),
    Person(("сергеев", "сергееву", "сергеева"), ("кирилл", "кириллу", "кирилла"),
           ("сергеевич", "сергеевичу", "сергеевича"), "сергеич", "m"),
    Person(("лебедев", "лебедеву", "лебедева"), ("максим", "максиму", "максима"),
           ("константинович", "константиновичу", "константиновича"), "константиныч", "m"),
    Person(("кузнецов", "кузнецову", "кузнецова"), ("дмитрий", "дмитрию", "дмитрия"),
           ("андреевич", "андреевичу", "андреевича"), "", "m"),
    Person(("морозов", "морозову", "морозова"), ("леонид", "леониду", "леонида"),
           ("давидович", "давидовичу", "давидовича"), "давидыч", "m"),
    Person(("новиков", "новикову", "новикова"), ("игорь", "игорю", "игоря"),
           ("валентинович", "валентиновичу", "валентиновича"), "", "m"),
    Person(("громов", "громову", "громова"), ("артём", "артёму", "артёма"),
           ("витальевич", "витальевичу", "витальевича"), "", "m"),
    Person(("захаров", "захарову", "захарова"), ("владислав", "владиславу", "владислава"),
           ("юрьевич", "юрьевичу", "юрьевича"), "", "m"),
)

FEMALE: tuple[Person, ...] = (
    Person(("павлова", "павловой", "павлову"), ("тамара", "тамаре", "тамару"),
           ("владимировна", "владимировне", "владимировну"), "", "f"),
    Person(("битюкова", "битюковой", "битюкову"), ("зинаида", "зинаиде", "зинаиду"),
           ("николаевна", "николаевне", "николаевну"), "николавна", "f"),
    Person(("новикова", "новиковой", "новикову"), ("наталья", "наталье", "наталью"),
           ("валентиновна", "валентиновне", "валентиновну"), "", "f"),
    Person(("полякова", "поляковой", "полякову"), ("валентина", "валентине", "валентину"),
           ("ивановна", "ивановне", "ивановну"), "", "f"),
    Person(("кузнецова", "кузнецовой", "кузнецову"), ("ольга", "ольге", "ольгу"),
           ("дмитриевна", "дмитриевне", "дмитриевну"), "", "f"),
    Person(("лебедева", "лебедевой", "лебедеву"), ("ирина", "ирине", "ирину"),
           ("петровна", "петровне", "петровну"), "", "f"),
    Person(("воронина", "ворониной", "воронину"), ("елена", "елене", "елену"),
           ("сергеевна", "сергеевне", "сергеевну"), "", "f"),
    Person(("тарасова", "тарасовой", "тарасову"), ("алла", "алле", "аллу"),
           ("анатольевна", "анатольевне", "анатольевну"), "", "f"),
    Person(("громова", "громовой", "громову"), ("марина", "марине", "марину"),
           ("борисовна", "борисовне", "борисовну"), "", "f"),
    Person(("фёдорова", "фёдоровой", "фёдорову"), ("юлия", "юлии", "юлию"),
           ("викторовна", "викторовне", "викторовну"), "", "f"),
    Person(("соколова", "соколовой", "соколову"), ("анна", "анне", "анну"),
           ("игоревна", "игоревне", "игоревну"), "", "f"),
    Person(("миллер", "миллер", "миллер"), ("валерия", "валерии", "валерию"),
           ("леонидовна", "леонидовне", "леонидовну"), "", "f"),
)

FOREIGN: tuple[Person, ...] = (
    Person(("ким", "киму", "кима"), ("виктор", "виктору", "виктора"), ("", "", ""), "", "m"),
    Person(("мкртчян", "мкртчяну", "мкртчяна"), ("ашот", "ашоту", "ашота"), ("", "", ""), "", "m"),
    Person(("тагиев", "тагиеву", "тагиева"), ("рустам", "рустаму", "рустама"), ("", "", ""), "", "m"),
    Person(("саркисян", "саркисяну", "саркисяна"), ("карен", "карену", "карена"), ("", "", ""), "", "m"),
    Person(("абдуллаев", "абдуллаеву", "абдуллаева"), ("тимур", "тимуру", "тимура"), ("", "", ""), "", "m"),
    Person(("валиахметов", "валиахметову", "валиахметова"), ("ильдар", "ильдару", "ильдара"), ("", "", ""), "", "m"),
    Person(("мамедова", "мамедовой", "мамедову"), ("лейла", "лейле", "лейлу"), ("", "", ""), "", "f"),
    Person(("джонсон", "джонсону", "джонсона"), ("майкл", "майклу", "майкла"), ("", "", ""), "", "m"),
)

DIMINUTIVES: tuple[tuple[str, str, str], ...] = (
    ("ирочка", "ирочке", "ирочку"), ("витёк", "витьку", "витька"),
    ("серёжа", "серёже", "серёжу"), ("наташа", "наташе", "наташу"),
    ("женя", "жене", "женю"), ("вася", "васе", "васю"), ("паша", "паше", "пашу"),
    ("коля", "коле", "колю"), ("даша", "даше", "дашу"), ("миша", "мише", "мишу"),
)
ROLES: tuple[str, ...] = ("сторож", "полковник", "дежурный", "дежурная",
                          "мастер", "начальник", "менеджер")
KINSHIP_MALE: tuple[str, ...] = ("дядя", "брат", "папа", "муж", "сын")
KINSHIP_FEMALE: tuple[str, ...] = ("тётя", "мама", "сестра", "жена", "дочь")


# --- places ---------------------------------------------------------------

STREET_FEM: tuple[str, ...] = (
    "вольная", "кирочная", "мончегорская", "школьная", "зеленоградская",
    "химзаводская", "союзная", "нижняя", "клубная", "базисная", "депутатская",
    "совхозная", "вишнёвая", "садовая", "центральная", "лесная", "новая",
    "подлесная", "солнечная", "рабочая", "заречная", "полевая", "луговая",
)
STREET_GENITIVE: tuple[str, ...] = (
    "лермонтова", "комиссарова", "чапаева", "калашникова", "грибоедова",
    "гагарина", "кирова", "энгельса", "ленина", "маяковского", "шумайлова",
    "репина", "тельмана", "дзержинского", "добролюбова", "барышникова",
    "челюскинцев", "пушкина", "некрасова", "толстого", "коммунаров",
)
STREET_MASC: tuple[str, ...] = (
    "смольный", "загородный", "северный", "комсомольский", "зелёный",
    "светлый", "октябрьский", "строительный",
)
STREET_NEUTER: tuple[str, ...] = (
    "воткинское", "заречное", "симферопольское", "ярославское", "ленинградское",
)
STREET_TYPES_HOUSE: tuple[str, ...] = ("улица", "переулок", "проезд", "проспект", "бульвар")

# The ten cities of the corpus, with the postal zone (first three digits of the
# index, Почта России) and the IANA zone. These two columns are what a DERIVED
# field is checked against, and they are a benchmark asset: extend the table,
# never guess. A substitute city outside it yields `derived(unverifiable)`.
CITIES: dict[str, tuple[str, str, str]] = {
    # city: (region, postal zone, IANA timezone)
    "ижевск": ("Удмуртская Республика", "426", "Europe/Samara"),
    "воткинск": ("Удмуртская Республика", "427", "Europe/Samara"),
    "глазов": ("Удмуртская Республика", "427", "Europe/Samara"),
    "сарапул": ("Удмуртская Республика", "427", "Europe/Samara"),
    "можга": ("Удмуртская Республика", "427", "Europe/Samara"),
    "абакан": ("Республика Хакасия", "655", "Asia/Krasnoyarsk"),
    "колпино": ("Санкт-Петербург", "196", "Europe/Moscow"),
    "сортавала": ("Республика Карелия", "186", "Europe/Moscow"),
    "краснодар": ("Краснодарский край", "350", "Europe/Moscow"),
    "самара": ("Самарская область", "443", "Europe/Samara"),
    # The vault's own fake-city pool and other cities a model may write.
    "москва": ("Москва", "1", "Europe/Moscow"),
    "санкт-петербург": ("Санкт-Петербург", "19", "Europe/Moscow"),
    "казань": ("Республика Татарстан", "420", "Europe/Moscow"),
    "екатеринбург": ("Свердловская область", "620", "Asia/Yekaterinburg"),
    "новосибирск": ("Новосибирская область", "630", "Asia/Novosibirsk"),
    "нижний новгород": ("Нижегородская область", "603", "Europe/Moscow"),
    "челябинск": ("Челябинская область", "454", "Asia/Yekaterinburg"),
    "омск": ("Омская область", "644", "Asia/Omsk"),
    "ростов-на-дону": ("Ростовская область", "344", "Europe/Moscow"),
    "уфа": ("Республика Башкортостан", "450", "Asia/Yekaterinburg"),
    "пермь": ("Пермский край", "614", "Asia/Yekaterinburg"),
    "воронеж": ("Воронежская область", "394", "Europe/Moscow"),
    "волгоград": ("Волгоградская область", "400", "Europe/Volgograd"),
    "красноярск": ("Красноярский край", "660", "Asia/Krasnoyarsk"),
    "тверь": ("Тверская область", "170", "Europe/Moscow"),
    "тула": ("Тульская область", "300", "Europe/Moscow"),
    "калуга": ("Калужская область", "248", "Europe/Moscow"),
    "рязань": ("Рязанская область", "390", "Europe/Moscow"),
    "брянск": ("Брянская область", "241", "Europe/Moscow"),
    "орёл": ("Орловская область", "302", "Europe/Moscow"),
    "курск": ("Курская область", "305", "Europe/Moscow"),
    "томск": ("Томская область", "634", "Asia/Tomsk"),
    "псков": ("Псковская область", "180", "Europe/Moscow"),
    "торжок": ("Тверская область", "172", "Europe/Moscow"),
    "кинешма": ("Ивановская область", "155", "Europe/Moscow"),
    "одоев": ("Тульская область", "301", "Europe/Moscow"),
    "чернь": ("Тульская область", "301", "Europe/Moscow"),
    "еловцк": ("", "", ""),
}
HOUSE_LETTERS: tuple[str, ...] = ("а", "б", "в")


@dataclass(frozen=True)
class Address:
    street: str
    street_type: str   # "" when the value carries no type word
    house: int
    letter: str        # "" when none
    entrance: int      # 0 when none
    flat: int          # 0 when none
    korpus: int        # 0 when none
    city: str          # "" when the value does not name one


def street_for(street_type: str, stream: random.Random) -> str:
    if street_type == "шоссе":
        return stream.choice(STREET_NEUTER)
    if street_type in ("переулок", "проезд", "проспект", "бульвар"):
        return stream.choice(STREET_MASC + STREET_GENITIVE)
    return stream.choice(STREET_FEM + STREET_GENITIVE)


def draw_address(stream: random.Random, city: str, with_flat: bool,
                 with_entrance: bool, with_type: bool) -> Address:
    street_type = stream.choice(STREET_TYPES_HOUSE) if with_type else ""
    return Address(
        street=street_for(street_type or "улица", stream),
        street_type=street_type,
        house=stream.choice((stream.randrange(1, 30), stream.randrange(1, 100),
                             stream.randrange(100, 200))),
        letter=stream.choice(HOUSE_LETTERS) if stream.random() < 0.12 else "",
        entrance=stream.randrange(1, 8) if with_entrance else 0,
        flat=stream.randrange(1, 250) if with_flat else 0,
        korpus=stream.randrange(1, 6) if (not with_flat and stream.random() < 0.15) else 0,
        city=city,
    )


# --- identifiers, every one passing its own checksum ------------------------

def snils_digits(stream: random.Random) -> str:
    """Nine digits plus the mod-101 control pair."""
    while True:
        digits = "".join(str(stream.randrange(10)) for _ in range(9))
        if len(set(digits)) == 1 or int(digits) <= 1001998:
            continue
        total = sum(int(digit) * (9 - index) for index, digit in enumerate(digits))
        if total < 100:
            control = total
        elif total in (100, 101):
            control = 0
        else:
            control = total % 101
            if control in (100, 101):
                control = 0
        return f"{digits}{control:02d}"


def inn12_digits(stream: random.Random) -> str:
    """A TWELVE-digit ИНН: a natural person's."""
    first = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    second = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    body = [stream.randrange(1, 10)] + [stream.randrange(10) for _ in range(9)]
    eleventh = sum(digit * weight for digit, weight in zip(body, first)) % 11 % 10
    body.append(eleventh)
    twelfth = sum(digit * weight for digit, weight in zip(body, second)) % 11 % 10
    body.append(twelfth)
    return "".join(str(digit) for digit in body)


def card_digits(stream: random.Random) -> str:
    """Sixteen digits that pass Luhn, on a real Russian BIN."""
    prefix = stream.choice(("2202", "4276", "5469", "2200"))
    body = prefix + "".join(str(stream.randrange(10)) for _ in range(11))
    total = 0
    for index, digit in enumerate(reversed(body)):
        value = int(digit)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return body + str((10 - total % 10) % 10)


def passport_digits(stream: random.Random) -> tuple[str, str]:
    """(series, number). The series' first two digits are a region code, the
    next two the issue year — a real shape, so a strict parser has something
    to check beyond «four digits»."""
    region = stream.choice(("45", "46", "40", "41", "18", "94", "36", "03"))
    year = stream.choice(("05", "08", "10", "12", "14", "17", "19", "21"))
    return f"{region}{year}", f"{stream.randint(100000, 999999)}"


def mobile_digits(stream: random.Random) -> str:
    """Ten digits after the country code, on a live Russian mobile DEF code."""
    code = stream.choice(("916", "926", "903", "905", "909", "912", "919", "922",
                          "925", "927", "929", "950", "951", "952", "960", "961",
                          "962", "963", "964", "965", "977", "982", "985", "987",
                          "988", "989", "999"))
    return code + "".join(str(stream.randrange(10)) for _ in range(7))


def bik_and_account(stream: random.Random) -> tuple[str, str]:
    """(БИК, расчётный счёт) with the account key valid against the БИК.

    The key is digit 9 of the account, computed over the last three digits of
    the БИК concatenated with the account, weights 7-1-3 repeating, mod 10 — the
    rule every Russian bank validates on transfer.
    """
    bik = "04" + stream.choice(("4525", "4030", "6577", "5401", "0349", "1900")) \
        + stream.choice(("225", "653", "674", "593", "978", "602"))
    while True:
        body = list(stream.choice(("40817", "40702", "40802")) + "810"
                    + "".join(str(stream.randrange(10)) for _ in range(11)))
        body.insert(8, "0")
        digits = bik[-3:] + "".join(body)
        weights = (7, 1, 3)
        total = sum(int(digit) * weights[index % 3] for index, digit in enumerate(digits))
        key = (total * 3) % 10
        body[8] = str(key)
        account = "".join(body)
        check = bik[-3:] + account
        if sum(int(d) * weights[i % 3] for i, d in enumerate(check)) % 10 == 0:
            return bik, account


def draw_dob(stream: random.Random) -> tuple[int, int, int]:
    return stream.randrange(1, 29), stream.randrange(1, 13), stream.randrange(1955, 2004)


PLATE_LETTERS = "АВЕКМНОРСТУХ"
PLATE_SPOKEN = {"А": "а", "В": "вэ", "Е": "е", "К": "ка", "М": "эм", "Н": "эн",
                "О": "о", "Р": "эр", "С": "эс", "Т": "тэ", "У": "у", "Х": "ха"}
PLATE_REGIONS = ("18", "77", "99", "16", "59", "23", "63")


def draw_plate(stream: random.Random) -> tuple[str, str, str, str]:
    return (stream.choice(PLATE_LETTERS), f"{stream.randint(100, 999)}",
            "".join(stream.choice(PLATE_LETTERS) for _ in range(2)),
            stream.choice(PLATE_REGIONS))


EMAIL_DOMAINS: tuple[str, ...] = ("mail.ru", "yandex.ru", "gmail.com", "list.ru", "bk.ru")
SPOKEN_DOMAINS: dict[str, str] = {
    "mail.ru": "мейл точка ру", "yandex.ru": "яндекс точка ру",
    "gmail.com": "джимейл точка ком", "list.ru": "лист точка ру",
    "bk.ru": "бэ ка точка ру",
}
MONTHS: tuple[str, ...] = ("января", "февраля", "марта", "апреля", "мая", "июня",
                           "июля", "августа", "сентября", "октября", "ноября", "декабря")
MONTH_ORDINALS: tuple[str, ...] = (
    "", "первое", "второе", "третье", "четвёртое", "пятое", "шестое", "седьмое",
    "восьмое", "девятое", "десятое", "одиннадцатое", "двенадцатое", "тринадцатое",
    "четырнадцатое", "пятнадцатое", "шестнадцатое", "семнадцатое", "восемнадцатое",
    "девятнадцатое", "двадцатое", "двадцать первое", "двадцать второе",
    "двадцать третье", "двадцать четвёртое", "двадцать пятое", "двадцать шестое",
    "двадцать седьмое", "двадцать восьмое")

# Simple ASCII transliteration for e-mail local parts (what a person types for
# a mailbox, not a passport). The passport tables live in `derive.py`.
_MAIL_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def mail_translit(word: str) -> str:
    return "".join(_MAIL_TRANSLIT.get(letter, letter) for letter in word)


# --- renderers: one value, one register, the parts it was built from ---------

@dataclass(frozen=True)
class Rendered:
    """A value as it appears, as a CRM would store it, and the typed parts it
    was BUILT from. `parts` is the ground truth a field-level comparison needs
    and it is never recovered from `surface` — it is what produced `surface`."""

    surface: str
    canonical: str
    spoken: bool
    parts: dict[str, str]


REGISTERS: tuple[str, ...] = ("clean", "chat", "sloppy", "voice_raw", "voice_itn")
SPEECH_REGISTERS: tuple[str, ...] = ("voice_raw", "voice_itn")


def _number(value: int, register: str, stream: random.Random, noisy: bool) -> str:
    if register != "voice_raw":
        return str(value)
    spoken = spell_cardinal(value)
    return " ".join(asr_noise(tuple(spoken.split()), stream, 0.23)) if noisy else spoken


def render_address(address: Address, register: str, stream: random.Random,
                   noisy: bool) -> Rendered:
    """The address in one register, with the typed parts kept beside it.

    For every register but `clean` the canonical IS the surface. The typed
    parts are what a CRM field would hold: house as digits, flat as digits,
    entrance as digits, street name without the type word.
    """
    street = address.street
    if register == "sloppy" and stream.random() < 0.5:
        street = typo(street, stream)
    elif noisy and register == "voice_raw" and stream.random() < 0.2:
        street = phonetic_slip(street, stream)
    parts: dict[str, str] = {"street": street}
    if address.street_type:
        parts["street_type"] = address.street_type
    parts["house"] = f"{address.house}{address.letter}"
    if address.flat:
        parts["flat"] = str(address.flat)
    if address.entrance:
        parts["entrance"] = str(address.entrance)
    if address.korpus:
        parts["building"] = str(address.korpus)
    if address.city:
        parts["city"] = address.city

    if register == "clean":
        tokens = [address.city.capitalize() + "," if address.city else ""]
        head = (f"{address.street_type} {street.capitalize()}" if address.street_type
                else street.capitalize())
        tokens.append(f"{head}, {address.house}{address.letter}")
        if address.korpus:
            tokens.append(f"корп. {address.korpus}")
        if address.entrance:
            tokens.append(f"подъезд {address.entrance}")
        if address.flat:
            tokens.append(f"кв. {address.flat}")
        surface = " ".join(token for token in tokens if token).replace(" ,", ",")
        return Rendered(surface=surface, canonical=surface, spoken=False, parts=parts)

    tokens: list[str] = []
    if address.city:
        tokens.append(address.city)
    if address.street_type:
        tokens.append(address.street_type)
    tokens.append(street)
    if register in SPEECH_REGISTERS and stream.random() < 0.3:
        tokens.append("дом")
    tokens.append(_number(address.house, register, stream, noisy))
    if address.letter:
        tokens.append(address.letter)
    if address.korpus:
        tokens.extend(("корпус", _number(address.korpus, register, stream, False)))
    if address.entrance:
        if register in SPEECH_REGISTERS:
            tokens.extend((spell_ordinal(address.entrance), "подъезд"))
        else:
            tokens.extend(("подъезд", str(address.entrance)))
    if address.flat:
        tokens.extend(("квартира" if register in SPEECH_REGISTERS else stream.choice(("кв", "квартира")),
                       _number(address.flat, register, stream, False)))
    if register in ("chat", "sloppy") and stream.random() < 0.25:
        # «гагарина88кв152» — the marker glued to the house number.
        joined: list[str] = []
        skip = False
        for index, token in enumerate(tokens):
            if skip:
                skip = False
                continue
            if token in ("кв", "квартира") and index + 1 < len(tokens) and joined:
                joined[-1] = f"{joined[-1]}кв{tokens[index + 1]}"
                skip = True
            else:
                joined.append(token)
        tokens = joined
    surface = " ".join(tokens)
    return Rendered(surface=surface, canonical=surface,
                    spoken=register == "voice_raw", parts=parts)


_CASE_INDEX: dict[str, int] = {"nom": 0, "dat": 1, "acc": 2}


def render_name(person: Person, layout: tuple[str, ...], grammar: str,
                register: str, damage: str, stream: random.Random,
                diminutive: tuple[str, str, str] = ("", "", "")) -> Rendered:
    """A name in one register; canonical = the nominative of what was said.

    A part the register DAMAGED keeps its damage in the canonical: reversing
    a typo would demand the intended word, the information the damage
    destroyed. `parts` carries the nominative per slot.
    """
    index = _CASE_INDEX[grammar]
    surfaces: list[str] = []
    canonicals: list[str] = []
    parts: dict[str, str] = {}
    damaged = stream.randrange(len(layout)) if damage != "none" else -1
    for position, slot in enumerate(layout):
        if slot == "surname":
            surface, nominative = person.surname[index], person.surname[0]
        elif slot == "given":
            surface, nominative = person.given[index], person.given[0]
        elif slot == "patronymic":
            surface, nominative = person.patronymic[index], person.patronymic[0]
        elif slot == "short":
            surface = nominative = person.short_patronymic
        elif slot == "diminutive":
            surface, nominative = diminutive[index], diminutive[0]
        else:
            raise BuildError(f"unknown name slot {slot!r}")
        if not surface:
            continue
        if position == damaged:
            surface = typo(surface, stream) if damage == "typo" else phonetic_slip(surface, stream)
            nominative = surface
        if register == "clean":
            surface, nominative = surface.capitalize(), nominative.capitalize()
        surfaces.append(surface)
        canonicals.append(nominative)
        parts[slot] = nominative
    if not surfaces:
        raise BuildError("a name layout produced no parts at all")
    parts["gender"] = person.gender
    return Rendered(surface=" ".join(surfaces), canonical=" ".join(canonicals),
                    spoken=False, parts=parts)


_GROUPINGS: dict[str, tuple[tuple[int, ...], ...]] = {
    "PHONE": ((1, 3, 3, 2, 2), (1, 3, 2, 2, 2, 1), (1, 3, 3, 3, 1)),
    "SNILS": ((3, 3, 3, 2), (2, 2, 2, 2, 3)),
    "INN": ((3, 3, 3, 3), (2, 2, 2, 2, 2, 2)),
    "CARD": ((2,) * 8, (2, 2, 3, 1, 2, 2, 2, 2)),
    "PASSPORT": ((2, 2, 3, 3), (2, 2, 2, 2, 2)),
}


def spoken_digits(kind: str, digits: str, stream: random.Random,
                  noise: float) -> str:
    """Digits as a caller says them, redrawn until they parse back.

    A PHONE is spoken with a leading «восемь», never «плюс семь»; the digit
    string passed in is the ten digits after the country code.
    """
    body = "8" + digits if kind == "PHONE" else digits
    for _ in range(200):
        sizes = stream.choice(_GROUPINGS[kind])
        words = asr_noise(spell_groups(body, sizes), stream, noise)
        if parse_numerals(words) == body:
            return " ".join(words)
    raise BuildError(f"could not render a decodable {kind} in 200 draws")


def render_phone(digits: str, register: str, stream: random.Random,
                 noise: float) -> Rendered:
    """Ten digits after the country code, in the register's form."""
    parts = {"digits": digits}
    canonical = f"+7{digits}"
    if register == "voice_raw":
        spoken = spoken_digits("PHONE", digits, stream, noise)
        return Rendered(surface=spoken, canonical=canonical, spoken=True, parts=parts)
    if register == "clean":
        return Rendered(surface=f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}",
                        canonical=canonical, spoken=False, parts=parts)
    written = stream.choice((
        f"8{digits}", f"+7{digits}",
        f"8 {digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:]}",
        f"8-{digits[:3]}-{digits[3:6]}-{digits[6:8]}-{digits[8:]}",
    ))
    return Rendered(surface=written, canonical=canonical, spoken=False, parts=parts)


def render_snils(digits: str, register: str, stream: random.Random, noise: float) -> Rendered:
    parts = {"digits": digits}
    if register == "voice_raw":
        spoken = spoken_digits("SNILS", digits, stream, noise)
        return Rendered(surface=spoken, canonical=f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}",
                        spoken=True, parts=parts)
    written = (f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
               if register != "sloppy" else digits)
    return Rendered(surface=written, canonical=written, spoken=False, parts=parts)


def render_inn(digits: str, register: str, stream: random.Random, noise: float) -> Rendered:
    parts = {"digits": digits}
    if register == "voice_raw":
        spoken = spoken_digits("INN", digits, stream, noise)
        return Rendered(surface=spoken, canonical=digits, spoken=True, parts=parts)
    return Rendered(surface=digits, canonical=digits, spoken=False, parts=parts)


def render_card(digits: str, register: str, stream: random.Random, noise: float) -> Rendered:
    parts = {"digits": digits}
    if register == "voice_raw":
        spoken = spoken_digits("CARD", digits, stream, noise)
        return Rendered(surface=spoken, canonical=digits, spoken=True, parts=parts)
    if register in ("clean", "chat"):
        written = " ".join(digits[index:index + 4] for index in range(0, 16, 4))
        return Rendered(surface=written, canonical=written, spoken=False, parts=parts)
    return Rendered(surface=digits, canonical=digits, spoken=False, parts=parts)


def render_passport(series: str, number: str, register: str,
                    stream: random.Random, noise: float) -> Rendered:
    parts = {"series": series, "number": number}
    if register == "voice_raw":
        spoken = spoken_digits("PASSPORT", series + number, stream, noise)
        return Rendered(surface=spoken, canonical=f"{series} {number}", spoken=True, parts=parts)
    if register in ("clean", "chat", "voice_itn"):
        return Rendered(surface=f"{series} {number}", canonical=f"{series} {number}",
                        spoken=False, parts=parts)
    return Rendered(surface=f"{series}{number}", canonical=f"{series}{number}",
                    spoken=False, parts=parts)


def render_plate(plate: tuple[str, str, str, str], register: str) -> Rendered:
    first, digits, pair, region = plate
    parts = {"letter": first, "digits": digits, "pair": pair, "region": region}
    if register == "voice_raw":
        spoken = " ".join((PLATE_SPOKEN[first], spell_cardinal(int(digits)),
                           " ".join(PLATE_SPOKEN[letter] for letter in pair),
                           spell_cardinal(int(region))))
        return Rendered(surface=spoken, canonical=spoken, spoken=True, parts=parts)
    written = f"{first}{digits}{pair}{region}"
    if register in ("chat", "sloppy"):
        written = written.lower()
    return Rendered(surface=written, canonical=written, spoken=False, parts=parts)


def render_dob(day: int, month: int, year: int, register: str) -> Rendered:
    parts = {"iso": f"{year:04d}-{month:02d}-{day:02d}"}
    canonical = f"{day:02d}.{month:02d}.{year}"
    if register == "voice_raw":
        spoken = " ".join((MONTH_ORDINALS[day], MONTHS[month - 1], spell_year(year), "года"))
        return Rendered(surface=spoken, canonical=canonical, spoken=True, parts=parts)
    if register == "voice_itn":
        return Rendered(surface=f"{day:02d} {month:02d} {year}", canonical=canonical,
                        spoken=False, parts=parts)
    return Rendered(surface=canonical, canonical=canonical, spoken=False, parts=parts)


def render_email(local: str, domain: str, spoken_local: str, register: str) -> Rendered:
    parts = {"local": local, "domain": domain}
    if register == "voice_raw":
        spoken = " ".join((spoken_local, "собака", SPOKEN_DOMAINS[domain]))
        return Rendered(surface=spoken, canonical=spoken, spoken=True, parts=parts)
    written = f"{local}@{domain}"
    return Rendered(surface=written, canonical=written, spoken=False, parts=parts)


# --- self-check -------------------------------------------------------------

def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _snils_ok(digits: str) -> bool:
    body, control = digits[:9], int(digits[9:])
    total = sum(int(d) * (9 - i) for i, d in enumerate(body))
    if total < 100:
        expected = total
    elif total in (100, 101):
        expected = 0
    else:
        expected = total % 101
        if expected in (100, 101):
            expected = 0
    return expected == control


def _inn12_ok(digits: str) -> bool:
    first = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    second = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    body = [int(d) for d in digits]
    return (sum(d * w for d, w in zip(body[:10], first)) % 11 % 10 == body[10]
            and sum(d * w for d, w in zip(body[:11], second)) % 11 % 10 == body[11])


def _account_ok(bik: str, account: str) -> bool:
    weights = (7, 1, 3)
    check = bik[-3:] + account
    return sum(int(d) * weights[i % 3] for i, d in enumerate(check)) % 10 == 0


def main() -> int:
    stream = random.Random(4)
    failures = 0
    for _ in range(300):
        if not _snils_ok(snils_digits(stream)):
            failures += 1
        if not _inn12_ok(inn12_digits(stream)):
            failures += 1
        if not _luhn_ok(card_digits(stream)):
            failures += 1
        bik, account = bik_and_account(stream)
        if not _account_ok(bik, account) or len(account) != 20 or not re.fullmatch(r"04\d{7}", bik):
            failures += 1
    print(f"checksums: {'PASS' if not failures else f'FAIL ({failures})'}")

    round_trips = 0
    for _ in range(300):
        for kind, digits in (("PHONE", mobile_digits(stream)),
                             ("SNILS", snils_digits(stream)),
                             ("INN", inn12_digits(stream)),
                             ("CARD", card_digits(stream)),
                             ("PASSPORT", "".join(passport_digits(stream)))):
            spoken = spoken_digits(kind, digits, stream, 0.23)
            body = "8" + digits if kind == "PHONE" else digits
            if parse_numerals(tuple(spoken.split())) != body:
                round_trips += 1
    print(f"spoken round trips: {'PASS' if not round_trips else f'FAIL ({round_trips})'}")

    for value in (1, 7, 12, 19, 20, 21, 47, 100, 101, 110, 199, 342, 999):
        if parse_numerals(tuple(spell_cardinal(value).split())) != str(value).zfill(len(str(value))):
            parsed = parse_numerals(tuple(spell_cardinal(value).split()))
            if int(parsed) != value:
                print(f"FAIL cardinal {value} -> {spell_cardinal(value)!r} -> {parsed!r}")
                failures += 1
    print("cardinals: PASS" if not failures else "")

    for register in REGISTERS:
        address = draw_address(stream, "ижевск", True, True, True)
        rendered = render_address(address, register, stream, register == "voice_raw")
        if not rendered.surface or rendered.parts["house"] != f"{address.house}{address.letter}":
            print(f"FAIL address {register}: {rendered}")
            failures += 1
        name = render_name(FEMALE[0], ("surname", "given", "patronymic"), "dat", register, "none", stream)
        if name.parts["surname"] != "павлова" and register != "clean":
            print(f"FAIL name {register}: {name}")
            failures += 1
    print("renderers: PASS" if not failures else f"renderers: FAIL ({failures})")
    return 1 if failures or round_trips else 0


if __name__ == "__main__":
    raise SystemExit(main())
