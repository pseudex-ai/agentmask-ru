"""High-recall Russian address detection (problem B).

No single local tool catches marker-less RU addresses at high recall, so recall
comes from the UNION of three sources, merged into maximal spans:

  1. Natasha AddrExtractor (Yargy grammar, via pymorphy3) — marker-bearing parts
     (город/улица/дом/квартира/посёлок/индекс), incl. marker-LAST streets.
  2. Broadened regex anchors — street types in both orders, house/корпус/строение,
     микрорайон, settlements, apartments, compact forms ("д12", "д5к2") that
     AddrExtractor misses.
  3. Morphology-gated marker-less streets ("Ленина 5", "Советская 8"): a
     Capitalized token tagged Surn/ADJF/Geox (or in a street gazetteer) + a
     1-3 digit house number. The name is also caught by NAME detection; this
     rule additionally masks the trailing house number.

Adjacent candidates are merged into one LOC span and a trailing bare house
number is swallowed. PRECISION: a merged span survives only if it holds a CORE
part (street/house/микрорайон/marker-less-street) — a lone city or lone
apartment is dropped (so "магазин в Москве" stays unmasked). A negative
dictionary kills square-meters ("5 кв.м") and abbreviations ("и т.д.").
"""

import re

from obscura import _morph_compat  # noqa: F401  (aliases pymorphy2->pymorphy3 before natasha)
from natasha import AddrExtractor, MorphVocab

from obscura.detect import Span
from obscura.names import _MORPH

_EXTRACTOR = AddrExtractor(MorphVocab())

# --- street-name gazetteer for toponyms with no morphological signal (genitive
# nouns Pushkin would miss): "улица Мира", "8 Марта", "проспект Победы" ---
_STREET_GAZ = {
    "мира", "победы", "октября", "космонавтов", "строителей", "энтузиастов",
    "дружбы", "свободы", "труда", "молодёжи", "юности", "гвардии", "марта", "мая",
    "ленина", "гагарина", "пушкина", "кирова", "жукова",
}

# --- a candidate is CORE (can stand alone) or SUPPORT (only counts when merged
# with a core). City/settlement/apt/index are SUPPORT so lone cities stay free. ---
_CORE_PART = ("улиц", "дом", "микрорайон", "проспект", "переул", "проезд",
              "бульвар", "набереж", "шоссе", "площад", "владени")


def _part_is_core(part_type: str) -> bool:
    return any(key in part_type for key in _CORE_PART)


# Street type markers (used marker-first AND marker-last); each only fires next
# to a Capitalized name, so a bare "пл"/"пр" can't match.
_ST = (
    r"(?:улиц\w+|ул\.?|проспект\w*|просп\.?|пр-?кт\.?|пр-?т\.?|переул\w+|пер\.?"
    r"|проезд\w*|пр-д|бульвар\w*|б-р|набережн\w+|наб\.?|шоссе|ш\.|площад\w+|пл\.?"
    r"|тупик\w*|туп\.?|алле\w+|лини\w+|квартал\w*|кв-л|тракт\w*|просек\w*)"
)
# The street/settlement markers below are case-insensitive (ул/Ул), but the NAME
# must be truly Capitalized — `(?-i:...)` keeps the capital case-sensitive even
# inside an IGNORECASE pattern, so "пер" in "перезвоните" can't grab a lowercase
# tail and "площадью 5 кв" can't pass as a street.
_NAME = r"(?-i:[А-ЯЁ])[а-яё]+(?:[\s-](?-i:[А-ЯЁ])[а-яё]+){0,2}"
_CAP = r"(?:\d+[-\s]?[а-яё]{0,2}\s+)?" + _NAME
_TOK = r"(?:(?<=^)|(?<=[\s,;(№#]))"  # token must start fresh -> excludes "т.д"

_STREET_FIRST = re.compile(rf"\b{_ST}\s*\.?\s*{_CAP}", re.IGNORECASE)
_STREET_LAST = re.compile(rf"{_CAP}\s+{_ST}\b", re.IGNORECASE)
_HOUSE = re.compile(
    _TOK + r"(?:дом|д|владени\w*|вл|уч\w*)\.?\s*№?\s*\d+(?:[а-яёА-ЯЁ](?!\d)|/\d+|-\d+)?"
    r"(?:\s*(?:корпус|корп|кор|к)\.?\s*\d+[а-яёА-ЯЁ]?)?"
    r"(?:\s*(?:строени\w*|стр|с)\.?\s*\d+[а-яёА-ЯЁ]?)?"
    r"(?:\s*(?:литер\w*|лит)\.?\s*[а-яёa-z]\b)?",
    re.IGNORECASE,
)
_APT = re.compile(
    _TOK + r"(?:квартир\w*|кв|офис\w*|оф|помещени\w*|пом|комнат\w*|комн)\.?\s*\d+",
    re.IGNORECASE,
)
_MKR = re.compile(
    r"\b(?:микрорайон\w*|мкрн|мкр)\.?\s*(?:[А-ЯЁ][а-яё]+|\d+[а-яё]?)", re.IGNORECASE
)
_SETTLEMENT = re.compile(
    _TOK + r"(?:город|гор|г|посёлок|поселок|пос|п|село|деревн\w*|дер|станиц\w*|ст"
    r"|хутор\w*|пгт|снт|днп)\.?\s*" + _NAME,
    re.IGNORECASE,
)
_INDEX = re.compile(r"\b\d{6}\b")
# Marker-less street + house number. Captures an optional leading number
# ("8 Марта"), 1-3 Capitalized words ("Карла Маркса", "26 Бакинских Комиссаров"),
# then a 1-3 digit house number with an OPTIONAL letter (upper OR lower: "174В")
# or "/N" form. A trailing negative-lookahead replaces \b so the uppercase house
# letter is not orphaned.
_MARKERLESS = re.compile(
    r"(?:(?<=^)|(?<=[\s,;(]))"
    r"(?P<num>\d+[-\s]?[яейои]?\s+)?"
    r"(?P<words>[А-ЯЁ][а-яё]+(?:[\s-][А-ЯЁ][а-яё]+){0,2})"
    r"\s+(\d{1,3}[А-ЯЁа-яё]?(?:/\d+)?)(?![0-9A-Za-zА-Яа-яёЁ])"
)
# Address context (Presidio-style enhancement): when nearby, a marker-less
# Capitalized/numbered "name + house" is accepted even with no morphology signal
# ("1905 года 12", "Миклухо-Маклая 6"). Universal RU address vocabulary, not
# tied to any one phrasing.
_ADDR_CTX = re.compile(
    r"адрес|доставк|курьер|приехать|привез|проживает|прописк|получател|посылк"
    r"|живу|квартир|заберите", re.IGNORECASE
)
_PREP_BEFORE = re.compile(r"\b(?:на|по|в|у)\s+$", re.IGNORECASE)
# Tails of numbered streets ("улица 1905 года", "8 марта"): generic RU pattern.
_NUMBERED_TAIL = (
    "года", "год", "лет", "марта", "мая", "января", "февраля", "апреля", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря", "партсъезда",
)
# Numbered street whose name word is lowercase ("1905 года 12") — the capital-name
# path (_MARKERLESS) can't see it, so match the number + a known numbered tail.
_NUM_NAME = r"\d{1,4}[-\s]?[яейои]?\s+(?:" + "|".join(_NUMBERED_TAIL) + r")"
_NUMBERED_ST = re.compile(
    r"(?:(?<=^)|(?<=[\s,;(]))(" + _NUM_NAME + r")"
    r"\s+(\d{1,3}[А-ЯЁа-яё]?(?:/\d+)?)(?![0-9A-Za-zА-Яа-яёЁ])",
    re.IGNORECASE,
)
# Numbered street with the type marker present ("1905 года тупик", "ул. 1905
# года") — the street type makes it unambiguously an address (not "событие 1905
# года"), so the numbered NAME is masked too, not just the house number.
_NUMBERED_MARKED = re.compile(
    r"(?:(?<=^)|(?<=[\s,;(]))(" + _NUM_NAME + r")\s+" + _ST + r"\b"
    r"|\b" + _ST + r"\s*\.?\s*(" + _NUM_NAME + r")",
    re.IGNORECASE,
)
# "т.д"/"т.п" must be the standalone abbreviation, not the "т" inside "ст." etc.
_NEG = re.compile(r"кв\.?\s*м|(?<![а-яёА-ЯЁ])т\.\s*[дпке]\b", re.IGNORECASE)
_GAP = re.compile(r"[\s,.;\-/№#()]*")
_TRAIL_HOUSE = re.compile(r"[\s,]+\d{1,4}[а-яё]?(?:/\d+)?\b")


def _word_is_street(word: str) -> bool:
    low = word.lower()
    if low in _STREET_GAZ:
        return True
    tag = _MORPH.parse(word)[0].tag
    if "Name" in tag and "Surn" not in tag:  # a bare first name is not a street
        return False
    return "Surn" in tag or "ADJF" in tag or "Geox" in tag


def _is_street_name(phrase: str) -> bool:
    """Street-name if ANY word (or hyphen part) looks like a toponym/surname/adj."""
    for word in re.split(r"[\s-]", phrase):
        if word and _word_is_street(word):
            return True
    return False


def _natasha_candidates(text: str) -> list[tuple[int, int, bool]]:
    out: list[tuple[int, int, bool]] = []
    for match in _EXTRACTOR(text):
        part_type = getattr(match.fact, "type", None) or ""
        out.append((match.start, match.stop, _part_is_core(part_type)))
    return out


def _regex_candidates(text: str) -> list[tuple[int, int, bool]]:
    out: list[tuple[int, int, bool]] = []
    for rx in (_STREET_FIRST, _STREET_LAST, _HOUSE, _MKR):
        for m in rx.finditer(text):
            out.append((m.start(), m.end(), True))   # core
    for rx in (_APT, _SETTLEMENT, _INDEX):
        for m in rx.finditer(text):
            out.append((m.start(), m.end(), False))  # support
    for m in _MARKERLESS.finditer(text):
        # words is always Capitalized here. Accept if it has a morphological
        # street signal, is a numbered street ("8 Марта"), or sits in an address
        # context (Presidio-style enhancement for signal-less "Миклухо-Маклая 6").
        before = text[:m.start()]
        has_ctx = bool(_ADDR_CTX.search(before)) or bool(_PREP_BEFORE.search(before))
        if _is_street_name(m.group("words")) or m.group("num") or has_ctx:
            out.append((m.start(), m.end(), True))   # core (street + house number)
    for m in _NUMBERED_ST.finditer(text):  # lowercase numbered names ("1905 года 12")
        out.append((m.start(), m.end(), True))
    for m in _NUMBERED_MARKED.finditer(text):  # "1905 года тупик" / "ул. 1905 года"
        out.append((m.start(), m.end(), True))
    return out


def _merge(cands: list[tuple[int, int, bool]], text: str) -> list[tuple[int, int, bool]]:
    cands = sorted(cands)
    groups: list[list[object]] = []
    for start, stop, core in cands:
        if groups:
            gs, ge, gcore = groups[-1]
            joinable = start <= ge or (start - ge <= 4 and _GAP.fullmatch(text[ge:start]) is not None)
            if joinable:
                groups[-1] = [gs, max(ge, stop), gcore or core]
                continue
        groups.append([start, stop, core])
    return [(g[0], g[1], g[2]) for g in groups]


def _strip(start: int, stop: int, text: str) -> tuple[int, int]:
    while start < stop and text[start] in " ,.;-/№#()":
        start += 1
    while stop > start and text[stop - 1] in " ,.;-/№#()":
        stop -= 1
    return start, stop


def detect_address(text: str) -> list[Span]:
    cands = _natasha_candidates(text) + _regex_candidates(text)
    if not cands:
        return []
    spans: list[Span] = []
    for start, stop, core in _merge(cands, text):
        if not core:
            continue
        trail = _TRAIL_HOUSE.match(text[stop:])  # swallow "ул. Садовая, 3"
        if trail and re.search(r"[А-Яа-яёЁ]$", text[:stop]):
            stop += trail.end()
        start, stop = _strip(start, stop, text)
        value = text[start:stop]
        if not value or _NEG.search(value):
            continue
        spans.append(Span(start, stop, "LOC", value))
    return spans
