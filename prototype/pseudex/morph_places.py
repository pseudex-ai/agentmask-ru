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
# «КВАРТИРА» IS NOT «КВАРТАЛ», AND FIVE LETTERS CANNOT TELL THEM APART. The
# generic scan below matches a street type by its first five characters, so
# «кварт» made every flat marker into a street type: «химзаводская пять квартира
# пятнадцать» minted «квартира Сосновый 66», a phrase that names nothing. The
# prefix rule is right for «переулочек» and wrong here, and only a list of the
# words that are PARTS of an address rather than TYPES of street can say so.
_NOT_A_STREET_TYPE = frozenset({
    "квартира", "квартиры", "квартире", "квартиру", "квартирой", "кв",
    "подъезд", "подъезда", "подъезде", "этаж", "этажа", "этаже",
    "корпус", "корпуса", "строение", "строения", "офис", "офиса",
    "помещение", "помещения", "комната", "комнаты",
})
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


# THE NUMERALS A HOUSE NUMBER IS SAID WITH. Not the full grammar — that lives in
# `spoken.py` and is about parsing a value; here the only question is whether a
# number was uttered at all, so a word list is exactly the right instrument.
_NUMERAL_WORD = (r"(?:ноль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять"
                 r"|десять|одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать"
                 r"|шестнадцать|семнадцать|восемнадцать|девятнадцать|двадцать|тридцать"
                 r"|сорок|пятьдесят|шестьдесят|семьдесят|восемьдесят|девяносто|сто"
                 r"|двести|триста|четыреста|пятьсот|шестьсот|семьсот|восемьсот|девятьсот)")
_SPOKEN_HOUSE = re.compile(rf"(?i)\b{_NUMERAL_WORD}\b")
# «квартира пятнадцать», «подъезд первый» — the marker decides, and the ordinal
# is admitted because an entrance is named with one.
_SPOKEN_FLAT = re.compile(
    rf"(?i)\b(?:кв|квартир\w*|офис\w*|оф|подъезд\w*|этаж\w*)\.?\s*"
    rf"(?:{_NUMERAL_WORD}|перв\w+|втор\w+|трет\w+|четв[её]рт\w+|пят\w+|шест\w+"
    rf"|седьм\w+|восьм\w+|девят\w+|десят\w+|последн\w+|углов\w+)\b")


def looks_like_street(value: str) -> bool:
    """Whether this span names a street rather than a settlement.

    Decides which KIND of fake to mint. Substituting a city for a street (or the
    reverse) changes what the sentence means, and the model notices: «доставка в
    Кинешме» where the customer wrote a street is a different delivery.
    """
    if _STREET_MARKER.search(value) or _HOUSE.search(value):
        return True
    # A bare house number after a WORD is a street too: «Ленинский проспект 42»
    # has a marker, «Тверская 7» does not.
    #
    # Case-insensitive, and that is the fix rather than the risk. The capital
    # used to be required, so the lower-case «мира 7» a customer types in chat
    # was judged a SETTLEMENT and got a city for a substitute — «а на мира 7
    # когда привезёте?» came back «а на Задонска когда привезёте?». Nothing here
    # decides whether the value is an address; detection already did. This only
    # chooses which KIND of address to mint, and there a missing capital is not
    # evidence of anything.
    # AND A BARE HOUSE NUMBER SAID ALOUD IS STILL A HOUSE NUMBER. The rule above
    # asks for a DIGIT, so «школьная пятьдесят девять» was judged a settlement
    # and got a settlement for a substitute — «Сортавала» where a street with a
    # door had stood. Worse than a wrong kind: a one-word substitute pulls the
    # case-agreement machinery onto the whole restored value, and «ленина
    # пятьдесят» came back from the tool as «ленина пятидесяти».
    #
    # This is the same defect as `place_shape`'s, in the branch that runs first,
    # and fixing only one of them fixes nothing: that one decides what the
    # substitute is MADE of, this one decides whether a street is being minted
    # at all.
    return bool(re.search(rf"(?i)[а-яё]{{3,}}\s+(?:\d|{_NUMERAL_WORD})", value))


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
        # A NUMBER IS A NUMBER WHETHER IT IS WRITTEN OR SAID. The docstring above
        # has always promised that numbers are left alone, and the test for one
        # was `stripped[0].isdigit()` — so «д. 5» was safe and «пятьдесят» was
        # not. On a corpus of real speech the restored value came back from the
        # tool as «ленина пятидесяти», a house number in the genitive, which is
        # not a thing anybody says and not a value any CRM will match.
        if (not stripped or stripped == "," or stripped[0].isdigit()
                or _SPOKEN_HOUSE.fullmatch(stripped.lower())):
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
        # A NUMBER IS A NUMBER WHETHER IT IS WRITTEN OR SAID — same rule as in
        # `phrase_to_nominative`, and the docstring above has always promised it.
        # The test was `stripped[0].isdigit()`, so «д. 5» was safe and
        # «пятьдесят» was not: the restored address came back from the tool as
        # «ленина пятидесяти», a house number in the genitive, which nobody says
        # and no CRM will match.
        if (not stripped or stripped == "," or stripped[0].isdigit()
                or _SPOKEN_HOUSE.fullmatch(stripped.lower())):
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


# Notation words that mean the same slot however they are written. The key must
# not care whether the customer typed «дом 42», «д. 42» or «д.42» — it is one
# building either way, and keying them apart made one address into three.
_SLOT_ALIASES: dict[str, str] = {
    # «дом» DROPS OUT of the key entirely. A bare number after a street IS the
    # house, so «улица Тверская 5» and «ул. Тверская, д. 5» are one address and
    # keeping the marker made them two. «кв», «к» and «стр» stay, because there
    # the marker is what says WHICH number it is.
    "дом": "", "дома": "", "д": "", "владение": "", "вл": "",
    "квартира": "кв", "кв": "кв", "офис": "кв", "оф": "кв",
    "помещение": "кв", "пом": "кв", "комната": "кв", "комн": "кв",
    # NO BARE «к» AND NO BARE «с». Both are prepositions before they are
    # «корпус» and «строение», and aliasing them turned «с Ленинского
    # проспекта» into a key that began with a building section.
    "корпус": "к", "корп": "к", "кор": "к",
    "строение": "стр", "стр": "стр",
    "город": "", "г": "", "гор": "",
}
# Prepositions carry no part of an address and change with the sentence around
# it. Left in, «на Ленинском проспекте» and «Ленинский проспект» were two rows.
_PREPOSITIONS = frozenset({"на", "в", "во", "по", "с", "со", "у", "до", "от",
                           "из", "за", "к", "ко", "о", "об", "при", "около"})
# NOT split on «-»: «пр-т» and «б-р» are single words in the abbreviation table,
# and splitting them meant they never matched it — so «пр-т» and «проспект»
# stayed two different addresses.
_KEY_SPLIT_RE = re.compile(r"[\s,;./№#]+")


def address_key(phrase: str) -> str:
    """A structural signature of an address, for the VAULT KEY only.

    One address written nine ways was nine rows, so the model met nine
    addresses: «Москва, Ленинский проспект, д. 42» / «дом 42» / «д.42» /
    «пр-т» / lower case / «на Ленинском проспекте» each keyed on itself. Names
    got a canonical key long ago; addresses never did — `canonicalize` had no
    LOC branch at all and used the raw surface.

    Safe to normalise as hard as this because `detokenize` returns the ORIGINAL
    for every type except NAME: what the customer's tool receives is still the
    string they wrote. Only the row it finds changes.

    Built by SLOT, not by sorting words: the city goes first if there is one,
    then the street type, then the name, then the numbers in the order they were
    written. House 42 flat 118 and house 118 flat 42 are different addresses.
    """
    # Prepositions come off BEFORE normalisation: they are what makes
    # `phrase_to_nominative` read «на Ленинском» as a stem rather than an
    # adjective, so stripping them afterwards would be too late.
    stripped = " ".join(word for word in phrase.strip().split()
                        if word.strip(",.").casefold() not in _PREPOSITIONS)
    parts: list[str] = []
    for raw in _KEY_SPLIT_RE.split((stripped or phrase.strip())
                                   .casefold().replace("ё", "е")):
        if not raw or raw in _PREPOSITIONS:
            continue
        alias = _SLOT_ALIASES.get(raw)
        if alias is not None:
            if alias:
                parts.append(alias)
            continue
        full = _GENERIC_SHORT.get(raw)
        if full:
            parts.append(full[0])
            continue
        # THE LEMMA, not `phrase_to_nominative`. A key does not need a correct
        # nominative, it needs a STABLE one — and the lemma is stable where the
        # nominative is not: «Ленинском» normalises to «ленинск» through the
        # phrase path and to «ленинский» through the lemma, «проспекта» to
        # «проспекта» and to «проспект». Three writings of one address were
        # three rows because of exactly that.
        # A glued type word is split HERE, in the key, where being wrong costs
        # nothing: «ленинскийпроспект» and «ленинский проспект» are one street
        # and were two rows. Detection already finds the glued form; only the
        # key could not see through it.
        for generic in _GENERIC:
            if raw.endswith(generic) and len(raw) > len(generic) + 2:
                stem = raw[:-len(generic)]
                parses = MORPH.parse(stem)
                parts.append(parses[0].normal_form if parses else stem)
                parts.append(generic)
                break
        else:
            parses = MORPH.parse(raw) if not raw.isdigit() else []
            parts.append(parses[0].normal_form if parses else raw)
    # A city named anywhere goes to the front, so «Москва, X» and «X, Москва»
    # are one address. Everything else keeps the order it was written in.
    # The city first, then the street TYPE, then everything else in the order it
    # was written. Russian puts the type on either side — «улица Тверская» and
    # «Тверская улица» are one street — so its position cannot be part of the
    # key. The numbers keep their order: house 42 flat 118 is not house 118
    # flat 42.
    city = [part for part in parts if _CITY_RE.match(part)]
    rest = [part for part in parts if not _CITY_RE.match(part)]
    generic = [part for part in rest if part in _GENERIC]
    tail = [part for part in rest if part not in _GENERIC]
    return " ".join(city + generic[:1] + tail)


def _has_city(phrase: str) -> bool:
    """Whether the address names a settlement as well as a street.

    A NAMED LIST WAS THE FIRST ATTEMPT AND IS THE WRONG SHAPE. It held the
    obvious cities and missed «Валдай», so «Живу на Валдае, улица Мира 4» was
    read as street-only, the substitute came back without a city, and the
    restoration window no longer lined up with the token — an address that
    failed to restore because of which towns happened to be on a list.
    //
    The structural signal is what the writing itself shows: a capitalised word
    that is not a street-type word, standing before a comma, at the head of the
    phrase. That is where a settlement goes in a Russian address, whatever it is
    called. The explicit marker («г.», «город») still counts on its own.
    """
    if re.search(r"(?i)\b(?:г|гор|город|пос|посёлок|поселок|село|дер|станиц)\.?\s", phrase):
        return True
    head = phrase.split(",", 1)[0].strip()
    if "," not in phrase or not head:
        return False
    words = re.findall(r"[А-ЯЁа-яё]+", head)
    if not words or len(words) > 2:
        return False
    # EVERY word of the head is checked, not just the first. «Ленинском
    # проспекте, дом 10» puts a capitalised word before a comma and is a STREET,
    # not a settlement — the generic that follows says so. Checking only the
    # first word read it as a city, the substitute grew a city the original never
    # had, and the restoration window stopped lining up.
    if any(word.lower() in _GENERIC or _GENERIC_STEMS.match(word.lower())
           for word in words):
        return False
    return words[0][:1].isupper()


def generic_full(written: str) -> str:
    """The full street-type word behind whatever the customer wrote.

    Word ORDER depends on the type, not on how it was abbreviated: «Тополиный
    проспект» and «пр-т Тополиный» both read naturally, «проспект Тополиный»
    less so. Resolving the abbreviation is how the generator can decide order
    without a second table of its own.
    """
    return _GENERIC_SHORT.get(written.lower().rstrip("."), (written.lower(), ""))[0]



def street_house_key(phrase: str) -> str:
    """The part of an address that a SHORTER mention of it still carries.

    «Москва, ул. Ленина, д. 14» and «ленина 14» are the same place written at
    two levels of detail, and the vault keys them apart — one canonicalises to
    `москва улица ленин 14`, the other to `ленин 14`. So the model met two
    addresses and, asked «вы находитесь на Ленина 14?», compared a masked
    address against a different masked address and answered no.

    This is the key they SHARE: the address key with the city and the street
    type removed, leaving the street's stem and the numbers. The city is
    recognised by morphology (`Geox`) rather than by a leased list of cities —
    the dictionary already carries the toponyms, and a second list would be a
    second thing to keep true.

    IT DELIBERATELY COLLIDES. «Ленина 14» in Moscow and «Ленина 14» in Kazan
    produce the SAME key, and that is the point rather than a flaw: the caller
    links only when the key has exactly one owner, so a street name that exists
    in every Russian city refuses to link instead of guessing which city. A key
    that separated them by city could not be computed from a mention that never
    named one.
    """
    kept: list[str] = []
    for token in address_key(phrase).split():
        # THE KEY STOPS AT THE FLAT. A short mention is short precisely because
        # it left the finer parts out: «мира 7» has to find «г. Казань, ул.
        # Мира, д. 7, кв. 12», and with «кв 12» still in the key it never did.
        # Street and house are what both writings of one place always carry.
        if token in ("кв", "к", "стр"):
            break
        if token in _GENERIC:
            continue
        if any("Geox" in parse.tag for parse in MORPH.parse(token)):
            continue
        kept.append(token)
    return " ".join(kept)


_FLAT_TAIL = re.compile(
    r"(?i)[\s,]*\b(?:кв|квартир\w*|оф|офис\w*|пом|помещени\w*|комн\w*"
    r"|под[ъь]езд\w*|эт|этаж\w*)\.?\s*\d+[а-яё]?\s*$")


def strip_flat(phrase: str) -> str:
    """The same address without its flat, or unchanged if it has none.

    Mirrors what the mention was made of, the same rule the substitute generator
    already follows for the city, the street type and the gender. A person who
    wrote «мира 7» must not be shown «ул. Пихтовой 93, кв. 15» — a flat number
    they never mentioned is a more specific address than the sentence carried,
    and a model reading a mismatch is a model that edits it.
    """
    return _FLAT_TAIL.sub("", phrase).rstrip(" ,")


def strip_leading_city(phrase: str) -> str:
    """The same address with its leading city dropped, or unchanged if none.

    Used to render a SHORT mention of a place we already substituted: the person
    wrote «ленина 14», so what the model should see is the street and house of
    their substitute, not the full «г. Тверь, улица Тополиная, 46». A mention
    that named no city must not come back naming one — that is a different
    address, and the model reads it as one.
    """
    head, _, tail = phrase.partition(",")
    if not tail:
        return phrase
    # DECIDED BY STRUCTURE, NOT BY DICTIONARY. Morphology was the obvious gate
    # and it is the wrong one here: this runs on the SUBSTITUTE, and our fake
    # cities are real but small («Венёв», «Бологое», «Кинешма»), so pymorphy
    # does not tag them `Geox` and the city was never stripped — the short
    # mention came back with a city it never had.
    #
    # The head of an address is its city exactly when it carries neither a
    # street-type word nor a number: «г. Москва» and «Венёв» qualify, «улица
    # Тополиная» and «Тверская 7» do not.
    lowered = head.lower()
    if any(char.isdigit() for char in head):
        return phrase
    if any(word.strip(" .") in _GENERIC or _GENERIC_SHORT.get(word.strip(" ."))
           for word in lowered.split()):
        return phrase
    return tail.strip(" ,")

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
    # A HOUSE NUMBER SAID ALOUD IS STILL A HOUSE NUMBER. Every question below
    # was decided by `re.search(r"\d", phrase)`, so «школьная пятьдесят девять»
    # answered «no house» and the generator produced a bare settlement name —
    # «Сортавала» — where an address with a door had stood. Measured on a corpus
    # built from real transcripts, that is the largest single loss on the
    # tool-call axis: LOC reaches its argument in 66% of cases against 98% for
    # every type whose substitute keeps its shape, because a one-word substitute
    # also drags the case-agreement machinery onto the whole restored value —
    # «ленина пятьдесят» came back as «ленина пятидесяти».
    spoken_house = _SPOKEN_HOUSE.search(phrase) is not None
    spoken_flat = _SPOKEN_FLAT.search(phrase) is not None
    # Abbreviations first, and kept VERBATIM: a customer who wrote «пр-т» reads
    # a substitute that says «проспект» as a different address, and expanding it
    # is a change we make for no reason.
    for short, (full, sex) in _GENERIC_SHORT.items():
        if re.search(rf"(?i)\b{re.escape(short)}\.?(?=\s|$)", phrase):
            return {
                "generic": short,
                "gender": sex,
                "has_city": _has_city(phrase),
                "has_house": bool(re.search(r"\d", phrase)) or spoken_house,
                "has_flat": bool(re.search(r"(?i)\b(?:кв|квартир|офис|оф)\.?\s*\d", phrase))
                            or spoken_flat,
            }
    for token in re.findall(r"[А-Яа-яЁё]+", phrase):
        lowered = token.lower()
        if lowered in _GENERIC:
            generic, gender = token, _GENERIC[lowered]
            break
        if lowered in _NOT_A_STREET_TYPE:
            continue
        for full, sex in _GENERIC.items():
            if lowered.startswith(full[:5]) and len(full) > 5:
                generic, gender = token, sex
                break
        if generic:
            break
    return {
        "generic": generic,
        "gender": gender,
        "has_city": _has_city(phrase),
        "has_house": bool(re.search(r"\d", phrase)) or spoken_house,
        "has_flat": bool(re.search(r"(?i)\b(?:кв|квартир|офис|оф)\.?\s*\d", phrase))
                    or spoken_flat,
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
    stems, digits = signature_parts(phrase)
    return "|".join(sorted(stems)) + "|" + "".join(digits)


def signature_parts(phrase: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Основы и числа фразы по отдельности — то, из чего склеен ключ выше.

    ВЫДЕЛЕНО, ЧТОБЫ ЧАСТЬ АДРЕСА МОЖНО БЫЛО ИСКАТЬ. Ключ целой фразы не находит
    фрагмент по построению: он несёт ВСЕ цифры, поэтому «улица Тополиная» даёт
    `тополиный|`, а «49» даёт `|49`, и ни один из них не равен складскому
    `тополиный|49`. Схемы инструментов адрес именно разбирают — `street`,
    `house`, `entrance` отдельными полями, — и на живом прогоне это 50 из 54
    неразрешённых аргументов. Части индексируются отдельно, и фрагмент ищется
    по ним.

    Родовые слова («улица», «ул.», «дом») выброшены из обеих половин: они не
    отличают один адрес от другого и меняются от того, как модель перепишет
    фразу.
    """
    digits = tuple(re.findall(r"\d+", phrase))
    stems: list[str] = []
    for token in re.findall(r"[А-Яа-яЁё]+", phrase):
        lowered = token.lower()
        if (lowered in _GENERIC or lowered in _SIGNATURE_NOISE
                or _GENERIC_STEMS.match(lowered)):
            continue
        parses = MORPH.parse(token)
        if not parses:
            stems.append(lowered)
            continue
        geo = [p for p in parses if "Geox" in p.tag.grammemes]
        best = max(geo or parses, key=lambda p: p.score)
        stems.append(best.normal_form.lower())
    return tuple(stems), digits


# The generic word in any of its forms — dropped from the signature because it
# inflects the most and carries no identity of its own.
_GENERIC_STEMS = re.compile(
    r"(?i)^(?:улиц|проспект|переул|переулк|бульвар|шоссе|проезд|площад|"
    r"набережн|алле|лини|просек|тупик|квартал|микрорайон)"
)

# СЛОВА, КОТОРЫЕ НЕ ОТЛИЧАЮТ ОДИН АДРЕС ОТ ДРУГОГО. Сокращения родовых слов и
# структурные маркеры записи. Выкидываются ТОЛЬКО из сигнатуры и ТОЛЬКО точным
# совпадением, а не префиксом, как `_GENERIC_STEMS`: односимвольный префикс «д»
# съел бы «Дзержинского», а «к» — «Кирова».
#
# ПОЧЕМУ ЭТО ВАЖНО. Модель переписывает адрес своими словами, и «улица» у неё
# становится «ул.», а перед номером появляется «д.». В сигнатуре «ул» оставалось
# основой, а «д» pymorphy3 нормализует в «далее» — так «улица Тополиная 49» и
# «ул. Тополиная, д. 49» получали РАЗНЫЕ ключи, восстановление промахивалось, и
# подмена уходила в инструмент клиента. 35 из 43 случаев, когда агент назвал
# клиенту фейковый адрес как его собственный.
_SIGNATURE_NOISE = frozenset({
    "ул", "пр", "прт", "пр-т", "просп", "пер", "наб", "б", "бр", "б-р", "ш",
    "пл", "мкр", "туп",
    "дом", "д", "корпус", "корп", "кор", "к", "строение", "стр", "владение",
    "вл", "квартира", "кв", "офис", "оф", "помещение", "пом", "комната",
    "комн", "литер", "лит", "подъезд", "под", "этаж",
})


# --- разбор НАСТОЯЩЕГО адреса на роли ---------------------------------------

_ORDINAL_WORD = (r"(?:перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|десят"
                 r"|одиннадцат|двенадцат|последн|углов)\w*")
# ДЛИННОЕ ПЕРЕД КОРОТКИМ, И ЭТО НЕ КОСМЕТИКА. «пять» — префикс «пятьдесят», а
# «два» — «двести»: при обычном порядке альтернатив «сто пятьдесят семь»
# разбирается как «сто пять», и дом уезжает в инструмент другим числом. То же
# правило уже записано про распознавание произнесённого номера дома.
_NUMERAL_LONGEST = "|".join(sorted(
    ("ноль", "один", "одна", "два", "две", "три", "четыре", "пять", "шесть",
     "семь", "восемь", "девять", "десять", "одиннадцать", "двенадцать",
     "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать",
     "восемнадцать", "девятнадцать", "двадцать", "тридцать", "сорок",
     "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто", "сто",
     "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот",
     "восемьсот", "девятьсот"), key=len, reverse=True))
_WORD_NUMBER = re.compile(
    rf"(?i)\b(?:{_NUMERAL_LONGEST})\b(?:\s+\b(?:{_NUMERAL_LONGEST})\b)*"
    rf"(?:\s+[а-яё](?![а-яё]))?")
# ЛИТЕРА ОТДЕЛЬНЫМ СЛОВОМ — ЧАСТЬ НОМЕРА ДОМА. «садовая 89 а», «барамзиной 112
# а»: без этого разбор считал дом законченным на цифре, обрезка ориентира резала
# «а» вместе с хвостом, и буква настоящего дома уходила к модели открытым
# текстом. Слитную форму («89а») паттерн знал и раньше. Двусмысленность «а» как
# союза снимается НИЖЕ по потоку, в `_trim_tail`, где видно следующее слово.
_DIGIT_NUMBER = re.compile(r"\d+(?:/\d+)?(?:[а-яё]\b|\s+[а-яё](?![а-яё]))?")
_ORDINAL_ONLY = re.compile(rf"(?i)\b{_ORDINAL_WORD}\b")
_HOUSE_MARKER = re.compile(r"(?i)\b(?:дом|д|влад\w*|вл)\.?")
_PART_MARKERS: tuple[tuple[str, str], ...] = (
    ("flat", r"кв|кварт\w*|офис\w*|оф"),
    ("entrance", r"подъезд\w*|под"),
    ("floor", r"этаж\w*"),
    ("building", r"корп\w*|кор|стр|строен\w*|литер\w*|лит"),
)


def _number_at(text: str, position: int) -> re.Match[str] | None:
    """Число (цифрами или словами), начинающееся сразу за `position`."""
    gap = re.match(r"[\s,.]*", text[position:])
    at = position + (gap.end() if gap else 0)
    for pattern in (_DIGIT_NUMBER, _WORD_NUMBER):
        found = pattern.match(text, at)
        if found is not None:
            return found
    return None


def split_roles(phrase: str) -> dict[str, str]:
    """Настоящий адрес, разложенный на street / house / flat / entrance / …

    ЗАЧЕМ. Схема инструмента просит части адреса отдельными полями, и вернуть
    туда целую фразу нельзя: в `house` поедет улица, а в `street` — улица с
    домом и подъездом. Раскладывать надо так же, как раскладывает человек,
    заполняющий форму.

    МАРКЕР ЗАБИРАЕТ ЧИСЛО СПРАВА, А ПОРЯДКОВОЕ — СЛЕВА. «кв. 58» пишут, «первый
    подъезд» говорят, и сторона зависит от того, числительное это или
    порядковое. Слева допускается ТОЛЬКО порядковое: разрешить там любое число
    значило бы, что «заречная сорок пять второй подъезд» отдаёт подъезду «сорок
    пять второй» вместе с домом.

    Дом — первое число, которое не забрал ни один маркер. Улица — всё, что
    стоит до него.
    """
    text = phrase.strip()
    claimed: list[tuple[int, int]] = []
    out: dict[str, str] = {}
    for role, marker in _PART_MARKERS:
        for hit in re.finditer(rf"(?i)\b(?:{marker})\.?(?![а-яё])", text):
            after = _number_at(text, hit.end())
            if after is not None:
                claimed.append((hit.start(), after.end()))
                out.setdefault(role, after.group().strip())
                continue
            before = list(_ORDINAL_ONLY.finditer(text[:hit.start()]))
            if before and not text[before[-1].end():hit.start()].strip():
                claimed.append((before[-1].start(), hit.end()))
                out.setdefault(role, before[-1].group().strip())
    house = None
    for pattern in (_DIGIT_NUMBER, _WORD_NUMBER):
        for number in pattern.finditer(text):
            if any(start <= number.start() < end for start, end in claimed):
                continue
            if house is None or number.start() < house.start():
                house = number
            break
    if house is not None:
        out["house"] = house.group().strip()
        head = text[:house.start()]
        marker = _HOUSE_MARKER.search(head)
        if marker is not None and not head[marker.end():].strip(" ,."):
            head = head[:marker.start()]
        street = head.strip().strip(" ,.")
        if street:
            out["street"] = street
    elif not claimed:
        out["street"] = text
    return out


_CITY_LEAD = re.compile(r"^[А-ЯЁ][а-яё-]+,\s+")
_TAIL_MARKER = re.compile(
    r"(?i),?\s*\b(?:кв|кварт\w*|офис\w*|оф|подъезд\w*|под|этаж\w*)\b")


def reduce_address(phrase: str, keep_city: bool, keep_tail: bool) -> str:
    """Адрес, урезанный до тех частей, которые НАЗВАЛИ.

    Режет исходную строку, а не пересобирает её из кусков: у настоящего адреса
    своя пунктуация и свои маркеры («д. 19, кв. 76»), и склейка частей пробелом
    превратила бы его в «19 76». Голова — город перед запятой, хвост — всё,
    начиная с маркера квартиры, подъезда или этажа.
    """
    out = phrase.strip()
    if not keep_city:
        head = _CITY_LEAD.match(out)
        if head is not None:
            out = out[head.end():]
    if not keep_tail:
        tail = _TAIL_MARKER.search(out)
        if tail is not None:
            out = out[:tail.start()]
    return out.strip().strip(" ,.")
