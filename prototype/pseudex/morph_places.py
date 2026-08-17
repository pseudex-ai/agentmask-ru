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
# Structural words of an address notation. They stay nominative whatever case
# the phrase around them takes — «на улице Ленина, дом 10, корпус 3» — the same
# way a genitive street name stays genitive. Inflecting them produced «доме 10»
# where the customer had written «дом 10», so the restored text no longer
# matched what was masked.
_ADDRESS_FIXED = frozenset({
    "дом", "дома", "д", "корпус", "корп", "кор", "к", "строение", "стр",
    "владение", "вл", "квартира", "кв", "офис", "оф", "помещение", "пом",
    "комната", "комн", "литер", "лит", "подъезд", "под", "этаж",
})

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
    """Carry the source's capitals onto the inflected form.

    Per HYPHEN-SEPARATED part, not just the first letter: «Санкт-Петербург»
    inflected and re-capitalised on the first character alone came back
    «Санкт-петербурге», which is a different-looking city.
    """
    if not source or not produced:
        return produced
    out = produced
    if source[0].isupper():
        out = out[0].upper() + out[1:]
    if "-" in source and "-" in out:
        source_parts = source.split("-")
        out_parts = out.split("-")
        for index in range(1, min(len(source_parts), len(out_parts))):
            if source_parts[index][:1].isupper() and out_parts[index]:
                out_parts[index] = out_parts[index][0].upper() + out_parts[index][1:]
        out = "-".join(out_parts)
    return out


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
        if lowered in _ADDRESS_FIXED or _is_genitive(stripped):
            out.append(token)
            continue
        out.append(_inflect_word(stripped, case, gender))
    return "".join(out)


def _inflect_word(word: str, case: str, gender: str | None) -> str:
    parses = MORPH.parse(word)
    if not parses:
        return word
    # ALREADY IN THE TARGET CASE — leave it, and check that against EVERY
    # reading, before the geographic and gender filters below. Those filters
    # exist to pick which paradigm to inflect along, and either of them can
    # discard the very parse that proves no inflection is needed: «Ленинском»
    # has a masculine locative reading that a feminine filter drops, and the
    # word was then inflected a second time into «Ленинске».
    if any(parse.tag.case == case for parse in parses):
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
    # ALREADY IN THE TARGET CASE — leave it. Inflecting a form to the case it
    # already holds is not a no-op in pymorphy3: it goes through the lemma, and
    # «Санкт-Петербурге» came back «Санкт-Петербургее». Exactly the defect the
    # name canonicaliser had, on the address side; the same rule fixes it.
    if best.tag.case == case:
        return word
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


# Written forms of the generic word that carry no letters to match on. Mapped to
# the gender they impose, so an adjectival name can still be made to agree.
_GENERIC_SHORT: dict[str, tuple[str, str]] = {
    "пр-т": ("проспект", "masc"), "пр-кт": ("проспект", "masc"),
    "просп": ("проспект", "masc"), "б-р": ("бульвар", "masc"),
    "ул": ("улица", "femn"), "пер": ("переулок", "masc"),
    "наб": ("набережная", "femn"), "пл": ("площадь", "femn"),
    "ш": ("шоссе", "neut"), "мкр": ("микрорайон", "masc"),
}
_CITY_RE = re.compile(r"(?i)\b(?:г\.|город|Москв|Санкт|Петербург|Новосиб|Екатеринб"
                      r"|Казан|Краснодар|Самар|Нижн|Ростов|Уф[аы]|Пермь|Челябинск"
                      r"|Омск|Волгоград|Воронеж|Тюмен|Сочи|Кинешм)")


def place_gender(phrase: str) -> str | None:
    """The gender of the head place word, preferring a geographic reading."""
    for token in re.findall(r"[А-ЯЁа-яё]+", phrase):
        if token.lower() in _GENERIC or _GENERIC_STEMS.match(token.lower()):
            continue
        parses = MORPH.parse(token)
        geo = [p for p in parses if "Geox" in p.tag.grammemes]
        best = max(geo or parses, key=lambda parse: parse.score)
        if best.tag.gender:
            return best.tag.gender
    return None


def generic_forms() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(full words, abbreviations) of the street-type vocabulary.

    Exported so `vault.TOKEN_RE` can be assembled from the SAME source the
    substitute generator draws on. Keeping two hand-written lists of the same
    vocabulary is how they drift apart, and a TOKEN_RE that has drifted fails to
    recognise a token the model echoed back — the fake then reaches the tool.
    """
    return tuple(_GENERIC), tuple(_GENERIC_SHORT)


def generic_full(written: str) -> str:
    """The full street-type word behind whatever the customer wrote.

    Word ORDER depends on the type, not on how it was abbreviated: «Тополиный
    проспект» and «пр-т Тополиный» both read naturally, «проспект Тополиный»
    less so. Resolving the abbreviation is how the generator can decide order
    without a second table of its own.
    """
    return _GENERIC_SHORT.get(written.lower().rstrip("."), (written.lower(), ""))[0]


def place_shape(phrase: str) -> dict[str, object]:
    """What the written address is MADE OF, so a substitute can be made of the
    same things.

    «Новосибирск, Красный проспект, 25» replaced by «улица Лавандовая, 46» loses
    the city and turns a проспект into an улица. Neither broke the round trip —
    but the model is reading a different KIND of address than the sentence was
    built around, and a model that notices is a model that edits. Same argument
    as gender and case for names; this is the address half of it.

    Returns the generic word to reuse verbatim (with the gender it imposes), and
    whether a city, a house number and a flat were present.
    """
    generic = ""
    gender = "femn"
    # Abbreviations first, and kept VERBATIM: a customer who wrote «пр-т» reads
    # a substitute that says «проспект» as a different address, and expanding it
    # is a change we make for no reason.
    for short, (full, sex) in _GENERIC_SHORT.items():
        if re.search(rf"(?i)\b{re.escape(short)}\.?(?=\s|$)", phrase):
            return {
                "generic": short,
                "gender": sex,
                "has_city": bool(_CITY_RE.search(phrase)),
                "has_house": bool(re.search(r"\d", phrase)),
                "has_flat": bool(re.search(r"(?i)\b(?:кв|квартир|офис|оф)\.?\s*\d", phrase)),
            }
    for token in re.findall(r"[А-Яа-яЁё]+", phrase):
        lowered = token.lower()
        if lowered in _GENERIC:
            generic, gender = token, _GENERIC[lowered]
            break
        for full, sex in _GENERIC.items():
            if lowered.startswith(full[:5]) and len(full) > 5:
                generic, gender = token, sex
                break
        if generic:
            break
    return {
        "generic": generic,
        "gender": gender,
        "has_city": bool(re.search(r"(?i)\b(?:г\.|город|Москв|Санкт|Новосиб|Екатеринб"
                                   r"|Казан|Краснодар|Самар|Нижн|Ростов|Уф[аы]|Пермь"
                                   r"|Челябинск|Омск|Волгоград|Воронеж)", phrase)),
        "has_house": bool(re.search(r"\d", phrase)),
        "has_flat": bool(re.search(r"(?i)\b(?:кв|квартир|офис|оф)\.?\s*\d", phrase)),
    }


def agree_with_generic(name: str, gender: str) -> str:
    """Put an adjectival street name into the gender its generic word imposes.

    `проспект Тополиная` is what happens without this — the substitute pool is
    written feminine because most generics are, and reusing the original's
    generic word means the name must follow it.
    """
    parses = _MORPH_PARSE(name)
    if not parses:
        return name
    best = max(parses, key=lambda parse: parse.score)
    inflected = best.inflect({"nomn", gender})
    if inflected is None:
        return name
    return _match_capitalisation(name, inflected.word)


def _MORPH_PARSE(word: str):
    return MORPH.parse(word)


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
