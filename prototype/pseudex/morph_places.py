"""Russian place morphology: nominative form, case agreement, street vs city.

The same problem the names module solved, one type over. A fake address read
`улице Тополиной, 21` wherever it landed — a dative phrase pasted into a
nominative slot — and a bare city arrived as `Кинешме`, which is a case, not a
name. The landing promises «валидный по виду адрес», and a courier system
validating that would reject it on sight.

WHY THE POOL IS STORED OBLIQUE. The leased vocabulary holds `Берёзовой` and
`Зеленограде`, because it was written to slot into `улице …` and `в …`. That is
data we lease and do not want to re-cut for a code change, so the nominative is
DERIVED here — `Берёзовой -> Берёзовая`, `Зеленограде -> Зеленоград` — and the
phrase is then inflected into whatever case the original was written in.

THE RULE THAT IS NOT A HEURISTIC: a component already in the genitive is frozen.
`улица Ленина` must not become `улицы Лениной` — the name of the street is a
person's name in the genitive and does not agree with anything. Adjectival names
(`Тверская`, `Берёзовая`) agree with the generic word and inflect normally.
"""

import functools
import re

from pseudex.morph import MORPH

# Generic words that head a Russian address, with the gender each one imposes on
# an adjectival name: `улица Тверская` (feminine) but `проспект Ленинский`
# (masculine). Getting this wrong is what produces `проспект Тверская`.
_GENERIC: dict[str, str] = {
    "улица": "femn", "площадь": "femn", "набережная": "femn", "аллея": "femn",
    "линия": "femn", "просека": "femn",
    "проспект": "masc", "переулок": "masc", "проезд": "masc", "бульвар": "masc",
    "тупик": "masc", "квартал": "masc", "микрорайон": "masc",
    "шоссе": "neut",  # indeclinable
}
_INDECLINABLE_GENERIC = frozenset({"шоссе"})

_STREET_MARKER = re.compile(
    r"(?i)\b(?:ул|улиц\w*|пр-?т|проспект\w*|пер|переул\w*|наб|набережн\w*|"
    r"б-?р|бульвар\w*|ш|шоссе|проезд\w*|площад\w*|пл|аллея|линия|мкр|микрорайон\w*)\b"
)
_HOUSE = re.compile(r"(?i)\b(?:д|дом|к|корп|корпус|стр|строение|влад)\.?\s*\d")


def looks_like_street(value: str) -> bool:
    """Whether this span names a street rather than a settlement.

    Decides which KIND of fake to mint. Substituting a city for a street (or the
    reverse) changes what the sentence means, and the model notices: «доставка в
    Кинешме» where the customer wrote a street is a different delivery.
    """
    if _STREET_MARKER.search(value) or _HOUSE.search(value):
        return True
    # A bare house number after a capitalised word is a street too:
    # «Ленинский проспект 42» has a marker, «Тверская 7» does not.
    return bool(re.search(r"[А-ЯЁ][а-яё]+\s+\d", value))


@functools.lru_cache(maxsize=4096)
def to_nominative(word: str) -> str:
    """Nominative of a single place word, preferring a geographic reading.

    `Geox` matters: without it `Гатчине` can parse as something else entirely,
    and the pool is full of small towns that only a geographic tag disambiguates.
    """
    parses = MORPH.parse(word)
    geo = [p for p in parses if "Geox" in p.tag.grammemes]
    best = max(geo or parses, key=lambda p: p.score)
    nominative = best.inflect({"nomn"})
    if nominative is None:
        return word
    return _match_capitalisation(word, nominative.word)


def _match_capitalisation(source: str, produced: str) -> str:
    if not source or not produced:
        return produced
    if source[0].isupper():
        return produced[0].upper() + produced[1:]
    return produced


def _is_genitive(word: str) -> bool:
    """A name already in the genitive — `Ленина`, `Победы`, `Энтузиастов`.

    Frozen rather than inflected: it is a possessive, not an agreeing adjective,
    and the single most visible failure of naive address inflection is turning
    `улица Ленина` into `улицы Лениной`.
    """
    parses = MORPH.parse(word)
    if not parses:
        return False
    best = max(parses, key=lambda p: p.score)
    return best.tag.case == "gent" and "ADJF" not in best.tag.grammemes


def phrase_to_nominative(phrase: str) -> str:
    """Normalise a whole place phrase to the nominative — the vault key.

    Separate from `inflect_place(..., "nomn")`, which returns its input
    untouched because it assumes it is ALREADY nominative. Using that as the key
    meant `улицу Абрикосовую, 8` keyed on itself and never matched the stored
    `улица Абрикосовая, 8`, so an inflected address was never resolved.
    """
    out: list[str] = []
    for token in re.split(r"(\s+|,)", phrase):
        stripped = token.strip()
        if not stripped or stripped == "," or stripped[0].isdigit():
            out.append(token)
            continue
        if _is_genitive(stripped):
            out.append(token)
            continue
        out.append(to_nominative(stripped))
    return "".join(out)


def inflect_place(phrase: str, case: str) -> str:
    """Put a nominative place phrase into `case`, keeping agreement.

    Only the generic word and an agreeing adjective move. Numbers, abbreviations
    and genitive names are left exactly as they are — inflecting those is how
    addresses turn into nonsense.
    """
    if case == "nomn":
        return phrase
    gender: str | None = None
    out: list[str] = []
    for token in re.split(r"(\s+|,)", phrase):
        stripped = token.strip()
        if not stripped or stripped == "," or stripped[0].isdigit():
            out.append(token)
            continue
        lowered = stripped.lower()
        if lowered in _GENERIC:
            gender = _GENERIC[lowered]
            out.append(token if lowered in _INDECLINABLE_GENERIC
                       else _inflect_word(stripped, case, None))
            continue
        if _is_genitive(stripped):
            out.append(token)
            continue
        out.append(_inflect_word(stripped, case, gender))
    return "".join(out)


def _inflect_word(word: str, case: str, gender: str | None) -> str:
    parses = MORPH.parse(word)
    if not parses:
        return word
    # A geographic reading first, for the same reason `to_nominative` does it:
    # `Луга` is a town and also the genitive of `луг`, and the meadow does not
    # inflect the way the town does.
    geo = [p for p in parses if "Geox" in p.tag.grammemes]
    if geo:
        parses = geo
    if gender is not None:
        agreeing = [p for p in parses if p.tag.gender == gender]
        parses = agreeing or parses
    best = max(parses, key=lambda p: p.score)
    grammemes = {case} if gender is None else {case, gender}
    inflected = best.inflect(grammemes) or best.inflect({case})
    if inflected is None:
        return word
    return _match_capitalisation(word, inflected.word)


def detect_case(phrase: str) -> str | None:
    """The case a place phrase is written in, decided by its generic word first.

    The generic word is the reliable signal: `улице` is unambiguously dative
    while the name beside it (`Тополиной`) is four cases at once.
    """
    tally: dict[str, float] = {}
    for token in phrase.split():
        stripped = token.strip(",.")
        weight = 3.0 if stripped.lower() in _GENERIC else 1.0
        for parse in MORPH.parse(stripped):
            if parse.tag.case:
                tally[parse.tag.case] = tally.get(parse.tag.case, 0.0) + parse.score * weight
    if not tally:
        return None
    return max(tally, key=lambda case: tally[case])


def match_signature(phrase: str) -> str:
    """A key that survives inflection, built like the phone digit signature.

    Morphological NORMALISATION was tried first and is too fragile for places:
    the phrase has variable structure (generic word, name, house number, or a
    bare settlement), and every shape needed its own rule. A hand-rolled list of
    endings was tried second and is worse — stripping is asymmetric, so `Валдай`
    and `Валдае` reduce to different stems.

    The LEMMA is the right answer, and it is what the dictionary is for:
    `Светлогорском` and `Светлогорск` both lemmatise to `светлогорск`, `Гатчине`
    and `Гатчина` to `гатчина`, `Еловой` and `Еловая` to `еловый`. The house
    number is appended because two streets can share a stem, and it is a number,
    so no inflection touches it.
    """
    digits = "".join(ch for ch in phrase if ch.isdigit())
    stems: list[str] = []
    for token in re.findall(r"[А-Яа-яЁё]+", phrase):
        lowered = token.lower()
        if lowered in _GENERIC or _GENERIC_STEMS.match(lowered):
            continue
        parses = MORPH.parse(token)
        if not parses:
            stems.append(lowered)
            continue
        geo = [p for p in parses if "Geox" in p.tag.grammemes]
        best = max(geo or parses, key=lambda p: p.score)
        stems.append(best.normal_form.lower())
    return "|".join(sorted(stems)) + "|" + digits


# The generic word in any of its forms — dropped from the signature because it
# inflects the most and carries no identity of its own.
_GENERIC_STEMS = re.compile(
    r"(?i)^(?:улиц|проспект|переул|переулк|бульвар|шоссе|проезд|площад|"
    r"набережн|алле|лини|просек|тупик|квартал|микрорайон)"
)
