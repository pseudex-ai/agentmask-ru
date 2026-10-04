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

from pseudex import agent_form, spoken
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
    "подъезд", "подъезда", "подъезде",
    "подьезд", "подьезда", "подьезде",
    "этаж", "этажа", "этаже",
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
    "комната", "комн", "литер", "лит", "подъезд", "подьезд", "под", "этаж",
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
    rf"(?i)\b(?:кв|квартир\w*|офис\w*|оф|под[ъь]езд\w*|этаж\w*)\.?\s*"
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
    # THE DIRECTORY FORM PUTS A COMMA BEFORE THE HOUSE. «Краснодар, центральная,
    # 100» is how DaData and every CRM export write an address; with the comma
    # the name-then-number test failed, the tool result's address was judged a
    # SETTLEMENT, and the model saw a bare city where it had just asked about a
    # street (live v4, `compare`).
    return bool(re.search(rf"(?i)[а-яё]{{3,}},?\s+(?:\d|{_NUMERAL_WORD})", value))


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

    ONLY A DICTIONARY-KNOWN GENITIVE. pymorphy guesses a `Geox` genitive for an
    unknown word before it guesses the adjective — «Зацепская»'s top parse was a
    NOUN-genitive of a place nobody has heard of, and freezing it there left
    `на улице Зацепская` instead of `…Зацепской` (E05). «Ленина»/«Комиссарова»
    are real genitives in the dictionary and stay frozen.
    """
    parses = MORPH.parse(word)
    if not parses:
        return False
    best = max(parses, key=lambda p: p.score)
    return (best.is_known and best.tag.case == "gent"
            and "ADJF" not in best.tag.grammemes)


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


_INFLECTABLE_POS = frozenset({"ADJF", "NOUN", "PRTF", "NUMR"})


def _inflect_word(word: str, case: str, gender: str | None) -> str:
    parses = MORPH.parse(word)
    if not parses:
        return word
    # ONLY A FULL FORM THE DICTIONARY KNOWS IS INFLECTED. «ленна» — a typo of
    # «Ленина» admitted by the fuzzy arm — is in the dictionary as the SHORT
    # adjective of «ленный», and bending it through that lemma restored the
    # customer's street as «ленную». A predicted paradigm for an unknown word
    # is the same guess from the other side. A word with no full-form reading
    # (adjective, noun, participle) from the dictionary is left as written.
    if not any(parse.is_known and parse.tag.POS in _INFLECTABLE_POS for parse in parses):
        # …UNLESS THE GUESS IS A REGULAR ADJECTIVE. «Зацепская» is absent from
        # OpenCorpora, but -ская declines like every other feminine adjective,
        # so the guessed ADJF parse is not the same gamble as a noun's paradigm
        # (nouns are unpredictable, adjectives are not). The short-form trap
        # above is `ADJS`, which this explicitly excludes — only the FULL
        # adjective `ADJF` is admitted here.
        guessed = [p for p in parses if p.tag.POS == "ADJF"]
        if not guessed:
            return word
        parses = guessed
    return _inflect_parses(word, case, gender, parses)


def _inflect_parses(word: str, case: str, gender: str | None, parses) -> str:
    """Inflect `word` to `case` along the best of `parses` (already filtered).

    The ALREADY-IN-TARGET-CASE check lives HERE, over the parses that survived
    the trust gate, and against EVERY one of them before the geographic and
    gender filters: those filters exist to pick which paradigm to inflect along,
    and either can discard the very parse that proves no inflection is needed
    («Ленинском» has a masculine locative reading a feminine filter drops). The
    gate matters — «Зацепская» carries a spurious `Geox` genitive GUESS that the
    old check saw as "already genitive" and froze, leaving `на улице Зацепская`
    (E05).
    """
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


# HEAD markers only — the city's and the street type's. A tail abbreviation
# («д.», «кв.», «корп.») sits inside inflected sentences all the time («на
# проспекте Жасминовом 176, корп. 9»), and read as a record it put a
# nominative substitute into an oblique slot; the head is what does not
# decline: «на ул. Тверская», never «на ул. Тверской».
_ABBREVIATED_MARKER_RE = re.compile(r"(?i)(?:^|[\s,])(?:г|гор|ул|пр-т|пр-кт|просп|пер|наб|пл|б-р|ш|мкр)\.?(?=[\s,]|$)")


def detect_case(phrase: str) -> str | None:
    """The case a place phrase is written in, decided by its generic word first.

    The generic word is the reliable signal: `улице` is unambiguously dative
    while the name beside it (`Тополиной`) is four cases at once.
    """
    # AN ABBREVIATED MARKER IS A RECORD, NOT A SENTENCE. «г Глазов, ул Кирова,
    # д 79» is how a directory writes an address; «Кирова» is a genitive by
    # nature and out-voted the abbreviations, which decline in no case, so the
    # substitute went to the model as «Глазова, ул. Сосновой 20» — the real
    # town's name bent into a genitive it never had.
    if _ABBREVIATED_MARKER_RE.search(phrase):
        return "nomn"
    # THE GENERIC WORD DECIDES ALONE when there is one. The name beside it is
    # either an adjective that agrees (no new information) or a frozen genitive
    # («Ленина», «Победы») that out-voted it: «на улице Ленина 1 кв 11» read as
    # the genitive, went to the model as «улицы Пихтовой 165» and came back as
    # «улицы Ленина» — the commonest address form in the language, wrong both
    # ways. Among the generic's own readings («улице» is dative and locative
    # alike) the locative wins: an address is said with «на» and «в».
    generic: dict[str, float] = {}
    for token in phrase.split():
        stripped = token.strip(",.")
        parses = MORPH.parse(stripped)
        if stripped.lower() in _GENERIC or any(parse.normal_form in _GENERIC for parse in parses):
            for parse in parses:
                if parse.normal_form in _GENERIC and parse.tag.case and parse.tag.number != "plur":
                    generic[parse.tag.case] = generic.get(parse.tag.case, 0.0) + parse.score
    if generic:
        # A masculine inanimate generic («проезд», «проспект», «бульвар») has
        # one form for the nominative and the accusative; the nominative is
        # the reading, or «я в можга проезд пушкина» minted «в Можгу».
        if "nomn" in generic and "accs" in generic:
            generic["accs"] = 0.0
        return max(generic, key=lambda case: (generic[case], -_CASE_PREFERENCE.index(case)
                                              if case in _CASE_PREFERENCE else -99))
    tally: dict[str, float] = {}
    for token in phrase.split():
        stripped = token.strip(",.")
        for parse in MORPH.parse(stripped):
            if parse.tag.case:
                tally[parse.tag.case] = tally.get(parse.tag.case, 0.0) + parse.score
    if not tally:
        return None
    return max(tally, key=lambda case: tally[case])


_CASE_PREFERENCE = ("loct", "nomn", "accs", "datv", "gent", "ablt")


def _has_generic_word(phrase: str) -> bool:
    """Whether the phrase names its street TYPE — «улица», «проезд», «бульвар».

    The same test `detect_case` uses to decide it can read the case off the
    generic word, asked as a question instead of as a side effect."""
    for token in phrase.split():
        stripped = token.strip(",.")
        if stripped.lower() in _GENERIC:
            return True
        if any(parse.normal_form in _GENERIC for parse in MORPH.parse(stripped)):
            return True
    return False


def _agrees_with_a_dropped_generic(phrase: str) -> bool:
    """Whether some word of the phrase is a FEMININE adjective.

    That is the only shape a street name takes when it agrees with an «улица»
    the customer did not write: «улица Тверская» → «на Тверской 7». Every other
    marker-less name — a surname («Заболоцкого»), a genitive plural
    («Комиссаров»), a noun («Победы») — is frozen and carries no case of the
    sentence at all."""
    for token in phrase.split():
        stripped = token.strip(",.")
        if not any(character.isalpha() for character in stripped):
            continue
        for parse in MORPH.parse(stripped):
            if parse.tag.POS == "ADJF" and parse.tag.gender == "femn" and parse.score >= 0.1:
                return True
    return False


def street_case(phrase: str) -> str | None:
    """The case an address phrase stands in, for the legs that lay a SUBSTITUTE
    into a form. `detect_case` answers the same question for a SETTLEMENT and
    keeps its answer — see `city_case`.

    A FROZEN GENITIVE IS THE STREET'S NAME, NOT A CASE OF THE SENTENCE.
    «заболоцкого 81 кв 51», «чернышевского 29», «комиссаров 56» have no generic
    word and no abbreviated marker, so `detect_case` falls through to a vote
    over the words — and a street named after a person votes genitive or
    accusative every time, because that IS how it is written in the nominative.
    Read as an oblique mention, the substitute was inflected and shown as a
    tidied canon («улицы Вязовой 59, кв. 127»); a rewriting agent had nothing to
    normalise, copied it, and the customer's own raw string came back where the
    agent's form was owed. The chat register — the bulk of real traffic — is
    exactly the shape that has neither marker nor generic word.

    THE ONE SHAPE THAT DOES CARRY THE SENTENCE'S CASE is an adjective agreeing
    with the dropped «улица», and it is feminine because that word is: «на
    Тверской 7» must still be shown inflected, or the model reads broken Russian
    and rewrites the token. So the oblique reading survives for an agreeing
    adjective and for nothing else.
    """
    case = detect_case(phrase)
    if case is None or case == "nomn":
        return case
    if _has_generic_word(phrase):
        return case
    return case if _agrees_with_a_dropped_generic(phrase) else None


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
    "кабинет": "кв", "каб": "кв",
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

# МЕЛКИЕ ЧАСТИ АДРЕСА — ИЗМЕНЯЕМЫЕ, И КЛЮЧ ДЕРЖИТ ИХ РОЛЬ, А НЕ ИХ ЗНАЧЕНИЕ.
#
# D-081: тождество подмены адреса — улица И дом, а квартира, подъезд, этаж и
# корпус/строение это ИЗМЕНЯЕМЫЕ ЧАСТИ. Человек сменил квартиру — это не новый
# фейк, поэтому ЗНАЧЕНИЕ мелкой части из ключа уходит: «Лермонтова 38 кв 7» и
# «Лермонтова 38 кв 42» дают один ключ и одну подмену, а диктовка «дом тридцать
# восемь» встречается с «дом 38».
#
# РОЛЬ ПРИ ЭТОМ ОСТАЁТСЯ В КЛЮЧЕ, И ЭТО НЕ НЕДОСМОТР. Три вещи держатся на ней
# одновременно, и каждая измерена:
#   * «мира семь» и «Мира 7 кв 3» — одна улица, но РАЗНАЯ конкретность: первое
#     упоминание не назвало квартиры, и подмена не смеет её показать
#     (`strip_flat`, test_product: «two short candidates mean a guess»);
#   * связывание полного и короткого написания (`_linked_place`,
#     `_extends_linked_place`) требует РОВНО ОДНОГО короткого владельца, а
#     владельцев различает именно набор ролей;
#   * поиск владельца фрагмента (`place_owner`) несёт роль в вопросе, поэтому
#     «дом 41» и «кв 41» — разные вопросы.
# ИЗМЕНЯЕМАЯ ЧАСТЬ НЕ ВХОДИТ В ТОЖДЕСТВО ВООБЩЕ (D-081): ни маркер, ни значение.
# «энгельса 54» и «энгельса 54 кв 189» — одно ядро, квартира рендерится отдельной
# частью (place_parts); иначе «система подтвердила другой адрес» и модель дублирует
# заказ. «корп»/«кор»/«строен» — корпус/строение, та же изменяемая часть.
_MUTABLE_KEY_MARKERS = frozenset({"кв", "к", "стр", "корп", "кор", "строен",
                                   "подъезд", "подьезд", "этаж"})
# A lone Cyrillic letter (not «я» — the pronoun), the house litera «145 а».
_LONE_LITERA = re.compile(r"[а-ё](?![а-яё])")

# СЛОВА, ПОСЛЕ КОТОРЫХ ЧИСЛО-СЛОВО — ЭТО НОМЕР ДОМА. Список тот же, что
# `_SLOT_ALIASES` отправляет в пустоту («дом» в ключе не остаётся: голое число
# за улицей и есть дом), и он читается здесь ДО выкидывания маркера — иначе
# «дом восемь» и «дом 8» остались бы двумя тождествами.
_HOUSE_KEY_MARKERS = frozenset({"дом", "дома", "д", "владение", "вл"})


def _fold_spoken_cardinals(tokens: list[str]) -> list[str]:
    """Продиктованные числа — в цифры, но НЕ любой ценой.

    D-081 требует, чтобы «дом тридцать восемь» и «дом 38» были одним
    тождеством. Свернуть при этом ЛЮБОЕ число-слово нельзя: `test_product`
    держит пин `address_key("центральная сто") == "центральный сто"` —
    «сохранённая каноническая форма не двигается», потому что смена ключа
    переразмечает строки, отчеканенные раньше. Поэтому правило узкое и
    позиционное:

      * РЯД из двух и более числительных («тридцать восемь», «сорок два»)
        сворачивается всегда — сам по себе он и есть одно число, и как голое
        число за улицей он читается однозначно;
      * ОДИНОЧНОЕ числительное («восемь», «сто») сворачивается только тогда,
        когда перед ним стоит МАРКЕР ДОМА («дом восемь», «д. восемь»): там
        написание само говорит, что это номер дома, и слова-числительного в
        ключе быть не должно.

    Числа, записанные цифрами, не трогаются вовсе.
    """
    out: list[str] = []
    index = 0
    while index < len(tokens):
        word = tokens[index]
        if not spoken.is_numeral_word(word):
            out.append(word)
            index += 1
            continue
        stop = index
        while stop < len(tokens) and spoken.is_numeral_word(tokens[stop]):
            stop += 1
        run = tokens[index:stop]
        after_house = (index > 0
                       and tokens[index - 1].strip(",.").casefold() in _HOUSE_KEY_MARKERS)
        if len(run) > 1 or after_house:
            folded = spoken.run_to_digits(run) or " ".join(run)
            # D-081: a dictated house with a litera folds to the SAME key as the
            # digit form. The phrase-level regexes glue «145 а» only where a
            # DIGIT sits before the letter; a dictated «сто сорок пять а» folds
            # to «145» HERE and the «а» is the next token, so it must glue here
            # too, or «дом сто сорок пять а» and «дом 145а» stay two identities.
            # Glued only when the run was a HOUSE number (after_house) and the
            # letter is a lone non-«я», followed by a mutable-part marker (short
            # or full) or by the end — the same license the digit path grants.
            if (after_house and isinstance(folded, str) and folded.isdigit()
                    and stop < len(tokens) and _LONE_LITERA.fullmatch(tokens[stop])):
                nxt = tokens[stop + 1].strip(",.").casefold() if stop + 1 < len(tokens) else ""
                if (not nxt or nxt in _MUTABLE_KEY_MARKERS
                        or nxt.startswith(("квартир", "строен", "подъезд", "подьезд", "этаж", "корп"))):
                    folded += tokens[stop]
                    stop += 1
            out.append(folded)
        else:
            out.extend(run)
        index = stop
    return out
# NOT split on «-»: «пр-т» and «б-р» are single words in the abbreviation table,
# and splitting them meant they never matched it — so «пр-т» and «проспект»
# stayed two different addresses.
_KEY_SPLIT_RE = re.compile(r"[\s,;./№#]+")


# THE REGISTER WRITES THE REGION FIRST, AND NOBODY SAYS IT. A DaData / ФИАС
# record reads «Самарская область, г Самара, ул Луговая, д 10»; the customer
# who lives there says «Самара, Луговая 10» or just «луговая 10». The region
# clauses are the same place written at a level of detail no mention from a
# person carries, so the key, the roles and the shape all read PAST them.
# Measured on the live v4 run: every `address_suggest` answer keyed with the
# region inside («самарский самара область луговой 10») and never met the
# customer's own mention, so the model was handed a second substitute for the
# address it had just asked about.
#
# A federal city before a MARKED settlement («Санкт-Петербург, г Колпино») is a
# region too — Колпино is the town, the city is its subject. Without the
# marker the leading city is the city.
_REGION_WORDS = (r"(?:область|обл|край|республика|респ|автономн\w*\s+округ|автономн\w*\s+область"
                 r"|ао|округ|район|р-н|муниципальн\w*\s+район|городск\w*\s+округ)")
_REGION_CLAUSE = re.compile(
    rf"(?i)\s*(?:респ(?:ублика)?\.?\s+[А-ЯЁа-яё-]+|[А-ЯЁа-яё-]+(?:\s+[А-ЯЁа-яё-]+)?\s+{_REGION_WORDS}\.?)\s*,\s*")
_FEDERAL_CITY_CLAUSE = re.compile(r"\s*(?:Москва|Санкт-Петербург|Севастополь)\s*,\s*")
# No `^`: these are applied with `match(phrase, pos)`, which anchors at `pos`
# on its own, and a caret would refuse every clause after the first.
_MARKED_SETTLEMENT = re.compile(
    r"(?i)(?:г|гор|город|пос|посёлок|поселок|с|село|дер|деревня|ст|станица|рп|пгт|х|хутор|аул)\.?\s+[А-ЯЁа-яё]")


def region_prefix_end(phrase: str) -> int:
    """Where the leading region / district clauses end; 0 when there are none."""
    pos = 0
    while True:
        match = _REGION_CLAUSE.match(phrase, pos)
        if match is None:
            match = _FEDERAL_CITY_CLAUSE.match(phrase, pos)
            if match is None or not _MARKED_SETTLEMENT.match(phrase, match.end()):
                break
        pos = match.end()
    return pos


# A word that INTRODUCES the settlement in the written register. «с», «д» and
# «п» are left out on purpose: they are a preposition, the house marker and a
# bare letter far more often than село, деревня and посёлок.
_CITY_MARKERS = frozenset({"г", "гор", "город", "пос", "посёлок", "поселок", "село", "дер",
                           "деревня", "станица", "пгт", "рп", "хутор", "аул"})


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

    Built by SLOT, not by sorting words: the city goes first if there is one, then
    the street NAME, the numbers in the order they were written, and the street
    TYPE word LAST.

    РОДОВОЕ СЛОВО — ЧАСТЬ ТОЖДЕСТВА, И ЭТО РЕШЕНИЕ ВЛАДЕЛЬЦА. «переулок
    Пушкина» и «улица Пушкина» — ДВА РАЗНЫХ МЕСТА (в Казани так и есть), и
    сливать их в одну строку значит отдать инструменту чужой адрес без права
    это заметить. Обратная сторона — «то же место, написанное с типом и без» —
    закрывается ОТДЕЛЬНЫМ правилом связывания (`_same_place_written_differently`
    ищет строку по той же основе, тому же дому и тому же типу, а не по ключу),
    поэтому одно место по-прежнему получает одну подмену, а два разных с
    одинаковым названием — две. Раньше тип выбрасывался из ключа, и это ровно
    то, что владелец отменил.

    ТИП СТОИТ ПОСЛЕДНИМ, И ЭТО НЕ КОСМЕТИКА. Написание БЕЗ типа — это префикс
    написания с типом («…мончегорский 10 кв 54» ⊂ «…мончегорский 10 кв 54
    переулок»), поэтому связывание пары читается ДИАПАЗОНОМ по индексу
    `(customer, canonical)` (`vault._place_family_owner`) и работает даже там,
    где разговора нет вовсе: «одно место — одна подмена навсегда и между
    разговорами» — записанный контракт, а не свойство разговора. Со слотом в
    середине того же вопроса без перебора всех строк заказчика не задать.
    `street_house_key` и `_place_identity` читают ключ по-прежнему: обе
    выбрасывают родовые слова, где бы те ни стояли.
    """
    # Prepositions come off BEFORE normalisation: they are what makes
    # `phrase_to_nominative` read «на Ленинском» as a stem rather than an
    # adjective, so stripping them afterwards would be too late.
    phrase = phrase[region_prefix_end(phrase):] or phrase
    # ЛИТЕРА, НАПИСАННАЯ ОТДЕЛЬНЫМ СЛОВОМ, — ЧАСТЬ НОМЕРА ДОМА, А НЕ ПРЕДЛОГ.
    # «толстого 34 в» и «г Краснодар, ул Толстого, д 34» — РАЗНЫЕ дома, а список
    # предлогов ниже съедал «в» (и «с», «к», «о» — ровно те буквы, которыми
    # пишут литеру), и оба дома получали один ключ. Дальше уже никакое сравнение
    # не может их различить: ключ тождества слил разные дома, и курьер поехал на
    # 34 вместо 34в (g06 P4, search_rank-008).
    #
    # Правило узкое и позиционное: буква, стоящая СРАЗУ ЗА ЦИФРОЙ и за которой
    # нет ничего, кроме конца строки или разделителя, — литера. «в квартиру» и
    # «с Ленинского» не трогаются: за буквой там идёт слово, а не разделитель.
    phrase = _SPACED_LITERA_RE.sub(r"\1", phrase)
    # «152кв7» and «152 кв 7» are one flat: the glued marker is split before the
    # key is built, so both writings meet in one row.
    phrase = _SPACED_LITERA_GLUED_RE.sub(r"\1\2", phrase)
    phrase = _GLUED_MARKER_RE.sub(r"\1 \2 \3", phrase)
    # «д 65, к 1», «65 с 2»: a bare «к» or «с» BETWEEN two numbers is корпус or
    # строение, not the preposition the list below drops — the register writes
    # exactly this, and the spoken «корпус один» keyed with «к» while the
    # record's «к 1» lost it.
    phrase = _MARKER_BETWEEN_NUMBERS_RE.sub(lambda m: f"{m.group(1)} {'корп' if m.group(2).lower() == 'к' else 'стр'} {m.group(3)}", phrase)
    stripped = " ".join(word for word in phrase.strip().split()
                        if word.strip(",.").casefold() not in _PREPOSITIONS)
    parts: list[str] = []
    # РОДОВЫЕ СЛОВА СТРОКИ, РАЗРЕШЁННЫЕ К ПОЛНОЙ ФОРМЕ: отдельный слот ключа
    # (см. доккомментарий). «ул» и «улица» дают одно «улица», «пр-т» и
    # «проспект» — одно «проспект», поэтому сокращение не расщепляет место.
    types: list[str] = []
    # THE CITY IS FOUND BY STRUCTURE, NOT ONLY BY THE LIST BELOW. A settlement
    # marker names the next word («г Можга»), and a leading word morphology
    # knows only as a place is one too («можга проезд пушкина 89»). `_CITY_RE`
    # stays for the big cities written bare after the street («ул. Ленина 5,
    # Казань»), which the two structural signals cannot see.
    cities: list[str] = []
    previous = ""
    # «ул Маяковского 82, Можга» — the settlement written LAST, after the
    # house, as a one-word clause morphology knows only as a place.
    tail = phrase.strip().rsplit(",", 1)
    trailing_city = (_KEY_SPLIT_RE.sub("", tail[1].strip().casefold().replace("ё", "е"))
                     if len(tail) == 2 and " " not in tail[1].strip() else "")
    if trailing_city and not _is_settlement_word(trailing_city):
        trailing_city = ""
    tokens = _KEY_SPLIT_RE.split((stripped or phrase.strip()).casefold().replace("ё", "е"))
    # ДИКТОВКА — ТА ЖЕ АДРЕСНАЯ ФРАЗА, ЧТО И ЦИФРЫ (D-081). «дом тридцать
    # восемь» и «дом 38» — один дом, и пока числа-слова оставались словами,
    # это были два тождества и две подмены. Свёртка идёт ДО разбора по слотам
    # (`_fold_spoken_cardinals`: ряд числительных сворачивается всегда, одиночное
    # — за маркером дома, см. её доккомментарий и пин `test_product`).
    # Числа, записанные цифрами, свёртка не трогает.
    tokens = _fold_spoken_cardinals(tokens)
    # ДВУСЛОВНЫЙ ГОРОД БЕЗ ЗАПЯТОЙ. Городом считался только ПЕРВЫЙ токен, и
    # «нижний новгород проезд калашникова 12» разбиралось как улица «нижний
    # новгород проезд калашникова»: город уезжал в поле `street` карточки
    # заказчика (живой прогон 07.09, long_support-021). С запятой всё работало,
    # без — нет; это тот же зазор, что стоил ФИО с датой рождения.
    #
    # ПРИЛАГАТЕЛЬНОЕ ПЕРЕД ТОПОНИМОМ, И ТОЛЬКО ОНО. «Нижний Новгород»,
    # «Великий Новгород», «Старый Оскол», «Нижний Тагил», «Сергиев Посад» —
    # весь класс устроен одинаково. Улицу это съесть не может: у улицы после
    # первого слова стоит РОДОВОЕ слово («проезд»), а не топоним, и
    # `_is_settlement_word` родовые слова отвергает первой же строкой.
    compound_city = -1
    if len(tokens) > 1 and tokens[0] and tokens[1] and _is_settlement_word(tokens[1]):
        parses = MORPH.parse(tokens[0])
        if (parses and all(parse.tag.POS == "ADJF" for parse in parses[:3])
                and not _is_settlement_word(tokens[0])):
            compound_city = 1
    # Идёт ли за только что прочитанным маркером изменяемой части её значение.
    drop_value = False
    for index, raw in enumerate(tokens):
        if not raw or raw in _PREPOSITIONS:
            continue
        if drop_value:
            # ЗНАЧЕНИЕ ИЗМЕНЯЕМОЙ ЧАСТИ В ТОЖДЕСТВО НЕ ВХОДИТ (D-081), и
            # выбрасывается оно ЗДЕСЬ, сразу за своим маркером. Значение может
            # быть и ДИКТОВАННЫМ («кв семь»), поэтому числом-словом оно тоже
            # отбрасывается — иначе «квартира семь» и «квартира 7» разошлись бы
            # ключами ровно там, где D-081 требует их встречи. Токен, который
            # ни цифра, ни числительное, значит маркер стоял без значения
            # («…, кв»), и тогда не выбрасывается ничего: следующий токен — уже
            # другая часть.
            if raw[:1].isdigit() or spoken.is_numeral_word(raw):
                previous = raw
                continue
            drop_value = False
        names_city = (previous in _CITY_MARKERS or (index == 0 and _is_settlement_word(raw))
                      or (compound_city == 1 and index in (0, 1))
                      or (raw == trailing_city))
        previous = raw
        alias = _SLOT_ALIASES.get(raw)
        if alias is not None:
            if alias:
                # «второй подъезд» — порядковое ПЕРЕД маркером это та же
                # изменяемая часть, а не улица: `street_house_key` снимает его
                # ровно так же, иначе «…второй подъезд 3» и «…подъезд 3» — два
                # написания одного места.
                if (alias in _MUTABLE_KEY_MARKERS and parts
                        and _ORDINAL_ONLY.fullmatch(parts[-1])
                        and not spoken.is_numeral_word(parts[-1])):
                    parts.pop()
                if alias in _MUTABLE_KEY_MARKERS:
                    # ИЗМЕНЯЕМАЯ ЧАСТЬ НЕ ВХОДИТ В ТОЖДЕСТВО (D-081): ни маркер
                    # «кв», ни значение. Квартира/подъезд/этаж рендерятся
                    # отдельной частью поверх того же ядра (place_parts).
                    drop_value = True
                else:
                    parts.append(alias)
            continue
        if raw in _MUTABLE_KEY_MARKERS:
            # «подъезд»/«этаж» в `_SLOT_ALIASES` не лежат и до этой строки
            # доезжают как обычное слово; они тоже не входят в тождество.
            if (parts and _ORDINAL_ONLY.fullmatch(parts[-1])
                    and not spoken.is_numeral_word(parts[-1])):
                parts.pop()
            drop_value = True
            continue
        full = _GENERIC_SHORT.get(raw)
        if full:
            types.append(full[0])
            continue
        if raw in _GENERIC:
            types.append(raw)
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
                types.append(generic)
                break
        else:
            # A DIGIT-LED TOKEN IS A NUMBER, whatever letter is glued to it.
            # pymorphy read «160в» as a verb and lemmatised it to «160ть», so
            # the house with a litera was a key nothing else could reach.
            # A NUMBER WORD IS KEPT AS THE NUMERAL IT IS — «четыыре» is
            # «четыре», not the lemma «четыыр» pymorphy invents for it — so a
            # dictated house with a slip keys with the same house said right.
            numeral = spoken.canonical_numeral(raw)
            if numeral is not None:
                parts.append(numeral)
                continue
            parses = MORPH.parse(raw) if not raw[:1].isdigit() else []
            # AN UNKNOWN WORD KEEPS ITS SPELLING. pymorphy guesses a lemma for
            # a word it does not know, and the guess is noise: «вишёнвая» (a
            # slip for Вишнёвая) became the verb «вишенвать», «пушкна» the
            # town «пушкно» — keys no register record could ever meet, so the
            # customer's mistyped street and the directory's answer were two
            # places (live v4, compare-014 / 034: «адрес не найден»).
            parts.append(parses[0].normal_form if parses and parses[0].is_known else raw)
            if names_city:
                cities.append(parts[-1])
    # A city named anywhere goes to the front, so «Москва, X» and «X, Москва»
    # are one address. Everything else keeps the order it was written in, and the
    # TYPE word closes the key. The numbers keep their order: house 42 flat 118
    # is not house 118 flat 42.
    city = [part for part in parts if part in cities or _CITY_RE.match(part)]
    rest = [part for part in parts if part not in city]
    tail = [part for part in rest if part not in _GENERIC]
    # РОДОВОЕ СЛОВО В КЛЮЧЕ — ЭТО СЛОТ, А НЕ ОФОРМЛЕНИЕ (решение владельца):
    # «переулок Пушкина» и «улица Пушкина» — два места и две подмены, а одно
    # место, написанное с типом и без, связывается отдельным правилом
    # (`vault._same_place_written_differently` по разговору и
    # `vault._place_family_owner` по самому ключу: написание без типа — префикс
    # написания с типом, потому что тип стоит ПОСЛЕДНИМ). Слово хранится
    # РАЗРЕШЁННЫМ («ул» и «улица» — одно «улица»), иначе сокращение расщепило бы
    # одно место на два.
    #
    # ё IS FOLDED IN THE KEY, AFTER lemmatisation too: the input was folded
    # before the lemma and pymorphy handed back «вишнёвый» with its ё, so the
    # customer's «вишенвая» and the register's «Вишнёвая» never met.
    return " ".join(city + tail + types).replace("ё", "е")


def key_type(canonical: str) -> tuple[str, ...]:
    """Родовые слова КЛЮЧА адреса — слот тождества, добавленный решением владельца.

    `address_key` уже разрешил их к полной форме («ул» → «улица»), поэтому
    сравнение здесь — сравнение самих типов, а не их написаний. Читается тем,
    кто решает вопрос СВЯЗЫВАНИЯ (`vault._same_place_written_differently`):
    «переулок Пушкина» и «улица Пушкина» — два места, а «переулок Мончегорская
    10» и «Мончегорская 10» — одно, написанное с типом и без.

    ХВОСТ-ПОДПИСЬ ЧАСТЕЙ СНИМАЕТСЯ (W8): строка второй квартиры того же дома
    несёт «…\\x1fflat=42», и без снятия последнее слово («улица\\x1fflat=42») не
    было бы родовым — тип этого места пропадал бы, и связывание связало бы
    разные места.
    """
    canonical = strip_parts_key(canonical)
    return tuple(word for word in canonical.split() if word in _GENERIC)


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
    phrase = phrase[region_prefix_end(phrase):] or phrase
    if re.search(r"(?i)\b(?:г|гор|город|пос|посёлок|поселок|село|дер|станиц)\.?\s", phrase):
        return True
    head = phrase.split(",", 1)[0].strip()
    if "," not in phrase:
        # NO COMMA, NO CAPITAL — SPEECH. «можга проезд пушкина восемьдесят
        # девять»: the detector put the settlement into the span (pymorphy tags
        # «можга» Geox whatever its case), but this reader wanted a capital and
        # a comma, so the substitute was minted WITHOUT a city and the agent
        # asked «в каком городе?» in every gateway arm (live v4, derive-034).
        # A leading word that morphology knows only as a place — Geox, and no
        # surname or adjective reading («тверская», «пушкина» carry both) —
        # names the settlement. Nothing about span boundaries changes here.
        return _leading_settlement(phrase) is not None
    if not head:
        return False
    tail = phrase.rsplit(",", 1)[1].strip()
    if tail and " " not in tail and re.fullmatch(r"[А-ЯЁа-яё-]+", tail) \
            and _is_settlement_word(tail.casefold().replace("ё", "е")):
        return True
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
    # A lower-case head before the comma («москва, садовая 46», the chat
    # register) is admitted by morphology, exactly as the comma-less form is.
    return words[0][:1].isupper() or _leading_settlement(head) is not None


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
    # ГОРОД НАЗЫВАЕТ `split_roles`, А МОРФОЛОГИЯ — ТОЛЬКО ПОДСТРАХОВКА. Ветка
    # ниже узнаёт город по грамматеме `Geox`, и словарь знает Краснодар, но не
    # знает Одоев: ключ справочной формы «Тульская область, г Одоев, ул
    # Центральная, д 100» получался «одоев центральный 100» и не встречался с
    # «центральный 100» от клиента. Тогда одному адресу чеканились ДВЕ подмены,
    # модель спрашивала справочник про «Жасминовую 142», получала «Тополиную
    # 161» и отвечала клиенту, что адрес не найден: на живом прогоне 07.09 это
    # четыре из шести случаев, где плечо шлюза вообще не оформило заявку, и
    # −91pp у семьи `tool_chain`.
    #
    # `split_roles` разбирает ту же фразу и уже знает, где город: он берёт и
    # маркер («г Одоев»), и позицию («Краснодар, центральная, 100»). Вторая
    # читалка той же фразы разошлась бы с первой, как расходятся все вторые
    # читалки в этом файле, — что здесь и произошло.
    city = split_roles(phrase).get("city", "")
    # Двусловный город («Нижний Новгород») снимается целиком: ключ обязан быть
    # улицей и домом, иначе две записи одного адреса не встретятся.
    city_lemmas = [to_nominative(word).lower().replace("ё", "е")
                   for word in city.split()] if city else []
    city_skipped = False
    tokens = address_key(phrase).split()
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        # THE KEY STOPS AT THE FLAT. A short mention is short precisely because
        # it left the finer parts out: «мира 7» has to find «г. Казань, ул.
        # Мира, д. 7, кв. 12», and with «кв 12» still in the key it never did.
        # Street and house are what both writings of one place always carry.
        # The entrance and the floor are finer parts too, and speech puts the
        # ordinal BEFORE the marker («второй подъезд»), so it is popped.
        if token in _SHORT_KEY_STOP:
            # «второй подъезд» — the ordinal before an ENTRANCE or FLOOR marker
            # only; before «кв» the previous word is the house number, and a
            # cardinal is never popped («девять» read as an ordinal left
            # «восемьдесят девять» keyed as 80).
            if (token in ("подъезд", "под", "этаж") and kept
                    and _ORDINAL_ONLY.fullmatch(kept[-1]) and not spoken.is_numeral_word(kept[-1])):
                kept.pop()
            break
        if token in _GENERIC:
            continue
        # ONLY THE LEADING PLACE WORD IS THE CITY. «Пушкин», «Киров», «Калинин»
        # are towns AND the commonest street names; dropping every Geox token
        # left «можга проезд пушкина 89» keyed as «89» — a key that would link
        # any house 89 in the conversation to this address.
        # …AND A CITY TAKES NO HOUSE NUMBER. «кирова 79» opens with a word
        # morphology calls a town (Киров), and dropping it keyed the customer's
        # street as «79» — a key the directory's «г Глазов, ул Кирова, д 79»
        # («киров 79») never met, so the record the model had just asked for
        # came back as a second substitute and the model reported the address
        # as not found (live v4 04.09, the Б8-echo residue). A leading place
        # word followed directly by a number is the street.
        if (not kept and city_lemmas and following
                and not following[:1].isdigit() and not spoken.is_numeral_word(following)
                and token == city_lemmas[0]):
            city_lemmas.pop(0)
            city_skipped = not city_lemmas
            continue
        if (not kept and not city_skipped and following
                and not following[:1].isdigit() and not spoken.is_numeral_word(following)
                and any("Geox" in parse.tag for parse in MORPH.parse(token))):
            city_skipped = True
            continue
        # A lone letter after a number is the house litera, and the glued
        # written form («100а») has already lost it in `address_key`.
        if len(token) == 1 and token.isalpha() and kept and kept[-1][-1:].isdigit():
            continue
        # The glued litera («160в») is now kept by `address_key`; the short
        # mention «полевая 160 в» lost its separate one above, so both key
        # to the bare number here.
        if len(token) > 1 and token[:-1].isdigit() and token[-1].isalpha():
            token = token[:-1]
        kept.append(token)
    # THE HOUSE NUMBER IS SAID IN WORDS AND WRITTEN IN DIGITS, and the two
    # mentions of one place are one place: «центральная сто» from the customer,
    # «Краснодар, центральная, 100» back from the directory. Lemmatisation
    # keeps «сто» a word, so the keys never met and the same address was
    # minted twice inside one conversation (live v4, 30 of 42 `compare`
    # triples). Folded HERE and not in `address_key`: that one is the stored
    # canonical, and re-keying every existing row is not on the table.
    return " ".join(_fold_cardinals(kept))


# «ПОДЬЕЗД» — ТО ЖЕ СЛОВО БЕЗ ТВЁРДОГО ЗНАКА, и для КЛЮЧА это не мелочь:
# `address_key` обрывается на первой мелкой части, и «Победы 81 подьезд 3»
# ключевалось «победа 81 подьезд 3» вместо «победа 81». Ключ подмены,
# отчеканенной с запятой («…, подъезд 22»), обрывается правильно, поэтому
# длинное окно восстановления не находило владельца, побеждало короткое —
# на «доме», — и в инструмент уезжал НАСТОЯЩИЙ дом с ФАЛЬШИВЫМ подъездом.
_SHORT_KEY_STOP = frozenset({"кв", "к", "стр", "подъезд", "подьезд", "под", "этаж"})
# ЛИТЕРА ДОМА ОТДЕЛЬНЫМ СЛОВОМ: «34 в» — это дом 34в, а не предлог «в». Буква
# склеивается с числом ДО выкидывания предлогов, и только когда за ней нет
# ничего, кроме конца строки или разделителя: «в квартиру» и «с Ленинского»
# остаются предлогами, потому что за буквой там стоит слово.
_SPACED_LITERA_RE = re.compile(r"(?i)(?<=\d)\s+([а-яё])(?=\s*(?:$|[,;.]))")
_GLUED_MARKER_RE = re.compile(r"(?i)(\d[а-яё]?)(кв|к|стр|корп)\.?(\d)")
# ЛИТЕРА ПЕРЕД МАРКЕРОМ В ЛЮБОЙ ПОЗИЦИИ: «34 в кв 9» — дом 34в, квартира 9, а
# не «34» и предлог «в». Буква склеивается с числом ДО выкидывания предлогов и
# тогда, когда за ней стоит маркер с пробелом — раньше lookahead требовал маркер
# ВПЛОТНУЮ («34 вкв 9») и цифру вплотную («кв9»), и отдельно написанная литера
# перед «кв»/«корп» съедалась списком предлогов, сливая два разных дома в один
# ключ (g06 P4). Пробел разрешён по обе стороны маркера («в кв 9», «в кв. 9»,
# «вкв9»), потому что все три — одна и та же литера и один и тот же маркер.
_SPACED_LITERA_GLUED_RE = re.compile(r"(?i)(\d)\s+([а-яё])(?=\s*(?:кв|к|стр|корп)\.?\s*\d)")
_MARKER_BETWEEN_NUMBERS_RE = re.compile(r"(?i)(\d[а-яё]?)[\s,]+([кс])\.?\s+(\d)")


def _settlement_gaz() -> frozenset[str]:
    """The leased settlements pymorphy reads only as a surname — «одоев», «венёв»,
    «белёв». Morphology says «surname», but a word on this list is a real town, so
    `_is_settlement_word` and `_leading_settlement` accept it where an address
    structure licenses it. Empty without a bundle, so `address_key` and
    `street_house_key` degrade to morphology-only outside a lease (the same
    fallback `address._fuzzy_intent` takes)."""
    from pseudex.assets import ASSETS
    return ASSETS.get().address.settlement_gaz if ASSETS.is_loaded else frozenset()


def _is_settlement_word(word: str) -> bool:
    """`_leading_settlement` for one already-lowered token: a place to
    morphology and nothing else — no surname, no adjective, no street type.

    The dictionary overrides the surname veto: «одоев» carries `Surn` and no
    `Geox`, yet it names a town, so a word on the leased settlement gazetteer is a
    settlement even though morphology reads it as a surname. The caller still
    demands the address structure, so the override cannot promote a bare word."""
    if word in _GENERIC or _GENERIC_STEMS.match(word) or word[:1].isdigit():
        return False
    if word in _settlement_gaz():
        return True
    parses = MORPH.parse(word)
    if not any("Geox" in parse.tag.grammemes for parse in parses):
        return False
    return not any("Surn" in parse.tag.grammemes or parse.tag.POS == "ADJF" for parse in parses)


def _fold_cardinals(tokens: list[str]) -> list[str]:
    """Maximal runs of cardinal words become their digits; the rest is kept."""
    out: list[str] = []
    run: list[str] = []
    for token in tokens:
        if spoken.is_numeral_word(token):
            run.append(token)
            continue
        if run:
            out.append(spoken.run_to_digits(run) or " ".join(run))
            run = []
        out.append(token)
    if run:
        out.append(spoken.run_to_digits(run) or " ".join(run))
    return out


_FLAT_TAIL = re.compile(
    r"(?i)[\s,]*(?:\b|(?<=\d))(?:кв|квартир\w*|оф|офис\w*|пом|помещени\w*|комн\w*"
    r"|каб|кабинет\w*|под[ъь]езд\w*|эт|этаж\w*)\.?\s*\d+[а-яё]?\s*$")


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
    r"""What the written address is MADE OF, so a substitute can be made of the
    same things.

    «Новосибирск, Красный проспект, 25» replaced by «улица Лавандовая, 46» loses
    the city and turns a проспект into an улица. Neither broke the round trip —
    but the model is reading a different KIND of address than the sentence was
    built around, and a model that notices is a model that edits. Same argument
    as gender and case for names; this is the address half of it.

    Returns the generic word to reuse verbatim (with the gender it imposes), and
    whether a city, a house number, an entrance and a flat were present.

    ЧАСТИ СЧИТАЕТ `split_roles`, А НЕ ВТОРАЯ ПАРА РЕГУЛЯРОК. Здесь стояли свои,
    и они были слабее: «квартира 58» не проходило (`квартир` без `\w*` не
    доедало окончание), а «второй подъезд» не проходило нигде — маркер там
    стоит ПОСЛЕ порядкового, и это основная форма русской диспетчерской речи.
    Подъезда в результате не было ни в одном ответе, поэтому подмена его
    ПРОСТО ТЕРЯЛА: «улица клубная дом 160 второй подъезд» превращалось в
    «улица Сиреневая 166», модель не видела подъезда и не могла положить его в
    аргумент, и настоящий подъезд не доезжал до диспетчера никогда.

    `split_roles` эти же формы уже разбирает правильно — он для того и написан.
    Две читалки одной фразы расходятся ровно так, как разошлись эти.
    """
    roles = split_roles(phrase) if phrase else {}
    has_house = "house" in roles
    has_flat = "flat" in roles
    has_entrance = "entrance" in roles
    has_building = "building" in roles
    # ЭТАЖ — ТАКАЯ ЖЕ ЧАСТЬ, КАК ПОДЪЕЗД, и он обязан доехать до подмены.
    # Без него `_decorate_place` его НЕ ЧЕКАНИЛ, `in_form_of` выкладывал на
    # место этажа одну маркерную строку («…, 87, этаж»), и номер этажа
    # ИСЧЕЗАЛ из маскированного текста: схема инструмента просит `floor`,
    # модель видит «этаж» без числа и кладёт в поле пустоту. 2 значения
    # PII-Bench и та же дыра в инструменте, что была у подъезда (см.
    # `_fake_place`).
    has_floor = "floor" in roles
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
    # Abbreviations first, and kept VERBATIM: a customer who wrote «пр-т» reads
    # a substitute that says «проспект» as a different address, and expanding it
    # is a change we make for no reason.
    for short, (full, sex) in _GENERIC_SHORT.items():
        if re.search(rf"(?i)\b{re.escape(short)}\.?(?=\s|$)", phrase):
            return {
                "generic": short,
                "gender": sex,
                "has_city": _has_city(phrase),
                "has_house": has_house,
                "has_flat": has_flat,
                "has_entrance": has_entrance,
                "has_building": has_building,
                "has_floor": has_floor,
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
        "has_house": has_house,
        "has_flat": has_flat,
        "has_entrance": has_entrance,
        "has_building": has_building,
        "has_floor": has_floor,
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

def is_generic_word(word: str) -> bool:
    """Родовое слово улицы или структурный маркер записи — «улица», «ул.», «д.».

    Публичная обёртка над двумя списками, которые уже есть: вторая пара
    регулярок для того же вопроса разошлась бы с этой, как расходятся все
    вторые читалки в этом файле.
    """
    return bool(_GENERIC_STEMS.match(word)) or word.lower().strip(".") in _SIGNATURE_NOISE


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
    "комн", "литер", "лит", "подъезд", "подьезд", "под", "этаж",
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
    rf"(?:\s+[а-яёА-ЯЁ](?![а-яёА-ЯЁ]))?")


@functools.lru_cache(maxsize=4)
def _word_number_for(version: str) -> re.Pattern[str]:
    """`_WORD_NUMBER` with the leased misspellings of the numerals folded in:
    «дом сто семьдесят четыыре» stopped at «семьдесят», the flat became the
    house and the real house went to the tool as 170 (scripted v4, four of
    the last eight diverging triples). Keyed on the bundle version so a fresh
    lease rebuilds it."""
    alternation = spoken.numeral_alternation()
    # A ONE-LETTER PREPOSITION IN FRONT OF WHAT IT GOVERNS IS NOT A LITERA.
    # «бульвар комиссарова двадцать семь в третий подъезд» read as house «27в»
    # here even after the detector's own pattern learnt better, because the
    # roles are cut by THIS pattern and the detector's is only the span. The
    # test is the word after the letter: an ordinal («в третий», «к пятому»)
    # or a marker in an oblique case («в квартиру», «к дому») — a litera is
    # followed by neither, and a marker in the nominative («в квартира двести
    # двадцать девять», a real call) keeps the letter a litera. Only the
    # letters that are prepositions are tested: «двадцать пять а третий
    # подъезд» keeps its «а».
    return re.compile(
        rf"(?i)\b(?:{alternation})\b(?:\s+\b(?:{alternation})\b)*"
        rf"(?:\s+(?![вксуо]\s+{_PREP_GOVERNS})[а-яёА-ЯЁ](?![а-яёА-ЯЁ]))?")


_PREP_GOVERNS = (r"(?:" + _ORDINAL_WORD + r"|квартир[уе]|под[ъь]езд[еу]|дом[еу]|корпус[еу]"
                 r"|этаж[еу]|строени[ие]|офис[еу]|помещени[ие])\b")


def _word_number() -> re.Pattern[str]:
    from pseudex.assets import ASSETS
    return _word_number_for(ASSETS.version or "") if ASSETS.is_loaded else _WORD_NUMBER
# ЛИТЕРА ОТДЕЛЬНЫМ СЛОВОМ — ЧАСТЬ НОМЕРА ДОМА. «садовая 89 а», «барамзиной 112
# а»: без этого разбор считал дом законченным на цифре, обрезка ориентира резала
# «а» вместе с хвостом, и буква настоящего дома уходила к модели открытым
# текстом. Слитную форму («89а») паттерн знал и раньше. Двусмысленность «а» как
# союза снимается НИЖЕ по потоку, в `_trim_tail`, где видно следующее слово.
# THE REGISTER WRITES THE LITERA IN CAPITALS. ФИАС / DaData spell «д 10А», and
# a lower-case class stopped the house at «10» — the «А» fell outside the
# role, outside the key, and outside the detector's span.
# …AND «к» OR «с» BEFORE A NUMBER IS A MARKER, NOT A LITERA. «д 65 к 1» read
# as house «65 к», the корпус had no role, and `_trim_landmark` cut the «1»
# off the span as a landmark — the directory record keyed without its корпус
# and the model was handed a second substitute for the place it had just
# asked about.
# …AND THE LITERA MAY BE GLUED TO THE FLAT MARKER: «зеленоградская 8 бкв150»,
# «тельмана 99 вкв196» is how a phone keyboard writes «8б, кв. 150». The
# litera is one letter followed by the end, a separator or a glued marker.
_DIGIT_NUMBER = re.compile(r"\d+(?:/\d+)?(?:[а-яёА-ЯЁ](?=$|[\s,.;]|кв\d|к\d|стр\d)"
                           r"|\s+(?![кс]\.?\s*\d)[а-яёА-ЯЁ](?=$|[\s,.;]|кв\d|к\d|стр\d))?")
_ORDINAL_ONLY = re.compile(rf"(?i)\b{_ORDINAL_WORD}\b")
_HOUSE_MARKER = re.compile(r"(?i)\b(?:дом|д|влад\w*|вл)\.?")
_HOUSE_MARKER_TAIL = re.compile(r"(?i)\b(?:дом|д|влад\w*|вл)\.?[\s,.]*$")
# «ПОДЬЕЗД» — ТО ЖЕ СЛОВО, ЧТО «ПОДЪЕЗД», И ЧАТ ПИШЕТ ЕГО БЕЗ ТВЁРДОГО ЗНАКА.
# «ул. Чехова 30 корпус 5 кв 12 подьезд 1» — живая строка PII-Bench: маркер
# узнавался только с «ъ», подъезд не становился РОЛЬЮ, и `_trim_landmark` резал
# спан на «кв 12» — десять символов настоящего адреса уезжали к модели
# открытым текстом. `_FLAT_TAIL` и `_SPOKEN_FLAT` мягкий знак знают давно;
# здесь его не было.
#
# «ЭТАЖ» ЗНАЛ ТОЛЬКО МАРКЕР-ПЕРЕД-ЧИСЛОМ («3 этаж» не разбиралось вовсе), а
# «кв. 87, 3 подъезд» — это ХВОСТ-ЧИСЛО-ПЕРЕД-МАРКЕРОМ, основная форма
# диспетчерской речи рядом с «подъезд 3». Обе формы разбирает `role_spans`
# ниже; маркер тут тот же, что у `_ADDRESS_FIXED` и `_SIGNATURE_NOISE`.
_PART_MARKERS: tuple[tuple[str, str], ...] = (
    ("flat", r"кв|кварт\w*|офис\w*|оф|помещени\w*|пом|комн\w*|кабинет\w*|каб"),
    ("entrance", r"под[ъь]езд\w*|под"),
    ("floor", r"этаж\w*"),
    ("building", r"корп\w*|кор|стр|строен\w*|литер\w*|лит|к(?=\.?\s*\d)|с(?=\.?\s*\d)"),
)
# ЧИСЛО ПЕРЕД МАРКЕРОМ И ЕГО ПРАВАЯ ГРАНИЦА. Порядковое окончание допущено
# («3-й подъезд»), потому что так пишут и в чате. ПРОБЕЛ В ГРУППУ НЕ ВХОДИТ:
# он стоял в ней (`\s*$`), и граница роли съедала его — `in_form_of` выкладывал
# подмену на «3 » вместо «3», маскированная строка приходила «24подъезд», а
# восстановление клало настоящее число В ТУ ЖЕ слитную форму. Круг расходился на
# одном пробеле, и это 8 значений PII-Bench.
_NUMBER_THEN_MARKER = re.compile(
    r"(?i)(\d{1,3})(?:\s*-\s*(?:ый|ий|ой|ая|ое|ья|й|я|е))?(?=\s*,?\s*$)")
# РОЛЬ ХВОСТА, НАЗВАННАЯ ЧИСЛОМ ПЕРЕД МАРКЕРОМ, СЧИТАЕТСЯ ТОЛЬКО ПОСЛЕ
# РАЗДЕЛИТЕЛЯ. «, 3 подъезд» — роль; «Победы 81 подьезд 3» — дом 81 и подъезд
# 3, и без этого условия «81 подъезд» забрал бы СЕБЕ роль подъезда, домом стало
# бы «3», а настоящий дом уехал бы в инструмент как номер подъезда.
_TAIL_AFTER_SEPARATOR = re.compile(r"[,.;:]\s*$")


# ПОРЯДКОВОЕ ОКОНЧАНИЕ ПОСЛЕ ЧИСЛА. Длинное перед коротким — иначе «ый»
# обрезалось бы до «й» и следующее слово читалось бы с середины.
_ORDINAL_SUFFIX = re.compile(r"(?i)\d+\s*-\s*(?:ый|ий|ая|ое|ья|й|я|е)")
# «Д» — МАРКЕР ДОМА ТОЛЬКО ОТДЕЛЬНЫМ СЛОВОМ. `_HOUSE_MARKER_TAIL` опирается на
# `\b`, а он срабатывает и после дефиса: в «пр-д 4-й Вешняковский» «д» от
# «проезда» читалось как «дом», и порядковый префикс названия снова уезжал в
# номер дома. Левая граница здесь своя, а не в общем маркере: тот стоит в
# `$`-якоре и правит границу улицы у КАЖДОГО «пр-д N», что этой правкой не
# покупается и не измерено.
_HOUSE_MARKER_WORD_TAIL = re.compile(r"(?i)(?<![А-Яа-яЁё-])(?:дом|д|влад\w*|вл)\.?[\s,.]*$")


def _heads_a_numbered_street(text: str, position: int) -> bool:
    """Число в начале НАЗВАНИЯ улицы, а не номер дома.

    «ул. 3-я Победиловская, д. 77, кв. 113» отдавало `house='3'` и
    `street='ул'`: дом берётся как ПЕРВОЕ число, которое не забрал ни один
    маркер, а порядковый префикс названия — такое же число. Отсюда две поломки
    от одной причины: `in_form_of` резал строку клиента по этим ролям и
    вставлял части фейка внутрь настоящего названия, а схема, просящая
    `street`/`house` по отдельности, получала в CRM «ул. Ул» и дом «3».

    ДВА ПРИЗНАКА, И ОБА НУЖНЫ. За числом идёт СЛОВО (иначе «дом 5-й» — это
    дом), и перед числом НЕ СТОИТ маркер дома (иначе «дом 5-й корпус 2»
    потеряло бы свой дом). Родовое слово перед числом, наоборот, признак
    улицы — «3-я линия 5» и «5-я просека 12» существуют, поэтому следующее
    слово НЕ проверяется на родовое: там оно и есть название.
    """
    # CARDINAL «N лет X» — «40 лет Победы», «30 лет Октября»: число возглавляет
    # НАЗВАНИЕ улицы, а не дом. Без этого «40» читалось домом, «лет» сворачивалось
    # в «год» внутри ключа, а age-gate маскировал «40 лет» как возраст — адрес
    # разрывался на AGE «40 лет» + LOC «Победы 12» (P2).
    if re.match(r"\d+\s*(?:лет|года|год)\b[\s,]*[А-Яа-яЁё]", text[position:]):
        return _HOUSE_MARKER_WORD_TAIL.search(text[:position]) is None
    ordinal = _ORDINAL_SUFFIX.match(text, position)
    if ordinal is None:
        return False
    if re.match(r"[\s,]+[А-Яа-яЁё]", text[ordinal.end():]) is None:
        return False
    return _HOUSE_MARKER_WORD_TAIL.search(text[:position]) is None


def _number_at(text: str, position: int) -> re.Match[str] | None:
    """Число (цифрами или словами), начинающееся сразу за `position`."""
    gap = re.match(r"[\s,.]*", text[position:])
    at = position + (gap.end() if gap else 0)
    for pattern in (_DIGIT_NUMBER, _word_number()):
        found = pattern.match(text, at)
        if found is not None:
            return found
    return None


def split_roles(phrase: str) -> dict[str, str]:
    """Настоящий адрес, разложенный на street / street_type / street_name / house / …

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

    РОДОВОЕ СЛОВО — СВОЯ РОЛЬ, А НЕ ПОЗИЦИЯ (Б-1). У фразы, которую написал
    клиент, оно ЕСТЬ или его НЕТ — это содержание, а не оформление, — и схема
    инструмента спрашивает его отдельным полем (`street_type`, `streetType`).
    Пока роли не было, лист `street_type` читался как лист УЛИЦЫ
    (`field_role('street_type') == ('street','street')`) и получал всю улицу
    целиком, тогда как соседний лист `street` получал её же без типа: одна
    улица уезжала в инструмент дважды, а тип терялся (g02/m-112). `street`
    остаётся ЦЕЛОЙ фразой — её читают все, кому форма нужна целиком (рендерер
    улицы, ключи, сплайс), — а `street_type`/`street_name` выделяются из неё
    как под-роли; потребитель, который сплайсит по `role_spans`, их не видит
    вовсе, поэтому подстановка целой роли не ломается.
    """
    roles = {role: phrase[start:end].strip()
             for role, (start, end) in role_spans(phrase).items()}
    street = roles.get("street", "")
    if street:
        words = street.split()
        types = [word for word in words if is_generic_word(word)]
        if types:
            roles["street_type"] = " ".join(types)
        name = " ".join(word for word in words if not is_generic_word(word))
        if name:
            roles["street_name"] = name
    return roles


# ПОД-РОЛИ УЛИЦЫ: они не самостоятельные части схемы, а половины роли `street`.
# Тот, кто собирает роль из `role_spans` (рендерер формы), их пропускает — тип
# едет внутри самой улицы, — а тот, кто раскладывает адрес по ПОЛЯМ схемы, их
# и спрашивает.
_STREET_SUB_ROLES = ("street_type", "street_name")


def role_spans(phrase: str) -> dict[str, tuple[int, int]]:
    """Те же роли, но ГРАНИЦАМИ в исходной строке.

    Нужны, чтобы восстанавливать адрес В ФОРМЕ, КОТОРОЙ ПОЛЬЗУЕТСЯ АГЕНТ:
    подставить настоящие части внутрь его собственной строки, не переписывая её
    своей пунктуацией и своими маркерами. Границы для этого обязательны — по
    одним лишь строкам частей нельзя сказать, где в «ул. Липовая, д. 119, кв.
    10» кончается дом и начинается квартира.
    """
    body = phrase[region_prefix_end(phrase):] or phrase
    offset = len(phrase) - len(body) + (len(body) - len(body.lstrip()))
    text = body.strip()
    claimed: list[tuple[int, int]] = []
    out: dict[str, tuple[int, int]] = {}
    for role, marker in _PART_MARKERS:
        # `(?<=\d)` beside `\b`: «152кв7» glues the marker to the house and
        # there is no word boundary between a digit and a letter.
        for hit in re.finditer(rf"(?i)(?:\b|(?<=\d)|(?<=\d[а-яё])|(?<=\d\s[а-яё]))(?:{marker})\.?(?![а-яё])", text):
            after = _number_at(text, hit.end())
            if after is not None:
                claimed.append((hit.start(), after.end()))
                out.setdefault(role, (after.start(), after.end()))
                continue
            before = list(_ORDINAL_ONLY.finditer(text[:hit.start()]))
            if before and not text[before[-1].end():hit.start()].strip():
                claimed.append((before[-1].start(), hit.end()))
                out.setdefault(role, (before[-1].start(), before[-1].end()))
                continue
            # ЧИСЛО ПЕРЕД МАРКЕРОМ: «, 3 подъезд», «, 2 под», «, 3-й этаж».
            # Порядковое слово ветка выше берёт с самого начала; здесь —
            # ЦИФРА, и потому нужно ещё одно свидетельство, что число называет
            # ЧАСТЬ, а не дом: РАЗДЕЛИТЕЛЬ перед ним. «кв. 87, 3 подъезд» —
            # роль; «Победы 81 подьезд 3» — дом 81 (число стоит за словом
            # улицы, без разделителя) и подъезд 3, который забрала ветка
            # «число после маркера» выше.
            if role not in ("entrance", "floor"):
                continue
            number = _NUMBER_THEN_MARKER.search(text[:hit.start()])
            if number is not None and _TAIL_AFTER_SEPARATOR.search(text[:number.start()]):
                claimed.append((number.start(), hit.end()))
                out.setdefault(role, (number.start(), number.end()))
    house = None
    for pattern in (_DIGIT_NUMBER, _word_number()):
        for number in pattern.finditer(text):
            if any(start <= number.start() < end for start, end in claimed):
                continue
            if _heads_a_numbered_street(text, number.start()):
                continue
            if house is None or number.start() < house.start():
                house = number
            break
    if house is not None:
        out["house"] = (house.start(), house.end())
        head_end = house.start()
        # THE LAST marker before the number, not the first. `search` took
        # the «Д» of «Добролюбова» and the «Влад» of «Владимирская», found
        # text after them, and left the real «д» inside the street.
        marker = _HOUSE_MARKER_TAIL.search(text[:head_end])
        if marker is not None:
            head_end = marker.start()
        head = text[:head_end]
        start = head_end - len(head.rstrip(" ,."))
        street = head.rstrip(" ,.")
        if street.strip():
            out["street"] = (len(street) - len(street.lstrip()), head_end - start)
    elif not claimed:
        out["street"] = (0, len(text))
    # ГОРОД — СВОЯ РОЛЬ, А НЕ НАЧАЛО УЛИЦЫ. «Москва, ул. Ленина 14» отдавал в
    # поле `street` строку «Москва, ул. Ленина» — и CRM клиента получала город
    # внутри улицы. Признак тот же, что у `_CITY_OF_TOKEN` на стороне
    # восстановления: заглавное слово (или «г. Пермь») перед первой запятой, без
    # цифр и без слова-типа улицы. Строчный «москва, садовая 46» сюда не входит
    # намеренно — без заглавной запятая одна не отличает город от улицы.
    if "street" in out:
        s_start, s_end = out["street"]
        street_text = text[s_start:s_end]
        city = _LEADING_CITY.match(street_text)
        if city is not None and city.end() < s_end - s_start:
            out["city"] = (s_start + city.start(1), s_start + city.end(1))
            rest = text[s_start + city.end():s_end]
            out["street"] = (s_start + city.end() + (len(rest) - len(rest.lstrip())), s_end)
        else:
            # The spoken form: a lower-case settlement with no comma, decided
            # by morphology alone (see `_has_city`). The street keeps its type
            # word: «можга проезд пушкина» -> city «можга», street «проезд пушкина».
            settlement = _leading_settlement(street_text)
            if settlement is not None and settlement.end() < len(street_text):
                out["city"] = (s_start + settlement.start(1), s_start + settlement.end(1))
                rest = street_text[settlement.end():]
                out["street"] = (s_start + settlement.end() + (len(rest) - len(rest.lstrip())), s_end)
    # ГОРОД В КОНЦЕ — ТОЖЕ ЧАСТЬ АДРЕСА, И ЭТО УЖЕ БЫЛО РЕШЕНО РЯДОМ.
    #
    # «ул. Садовая 23, Екатеринбург»: адрес найден, а последнее слово ушло
    # открытым текстом — `_trim_landmark` считает всё после последней роли
    # ориентиром и резал город. Ключ волта (`address_key`) читает ровно этот
    # хвост с самого начала: `trailing_city` — одно слово после последней
    # запятой, принятое `_is_settlement_word`. Читатель ролей не читал, и одна
    # фраза давала КЛЮЧ С ГОРОДОМ и СПАН БЕЗ НЕГО — то самое расхождение,
    # которое доккомментарий `split_roles` называет «один разбор на всех».
    #
    # Признак тот же и он узкий: одно слово, после последней запятой,
    # морфология знает его ТОЛЬКО как место. «ленина 14, Пушкин» городом не
    # станет (у «Пушкин» есть разбор-фамилия), поэтому человек после адреса
    # по-прежнему остаётся человеком.
    if "city" not in out:
        head, sep, tail = text.rpartition(",")
        word = tail.strip()
        if sep and word and " " not in word and _is_settlement_word(
                word.casefold().replace("ё", "е")):
            at = len(head) + len(sep) + tail.index(word)
            out["city"] = (at, at + len(word))
    return {role: (start + offset, end + offset) for role, (start, end) in out.items()}


_LEADING_WORD = re.compile(r"^\s*([А-ЯЁа-яё][А-ЯЁа-яё-]+),?(?=\s|$)")


def _leading_settlement(phrase: str) -> re.Match[str] | None:
    """The first word, when morphology knows it ONLY as a place.

    pymorphy tags settlements Geox regardless of case, and no city gazetteer is
    leased on purpose (address.py: the dictionary already makes the separation).
    A word with a surname or adjective reading beside Geox is a street name in
    disguise — «тверская», «пушкина», «ленина» — and is refused. A street-type
    word in first position is never a settlement.
    """
    match = _LEADING_WORD.match(phrase)
    if match is None:
        return None
    word = match.group(1)
    low = word.lower()
    if low in _GENERIC or _GENERIC_STEMS.match(low):
        return None
    # ДВУСЛОВНЫЙ ГОРОД БЕЗ ЗАПЯТОЙ. Настоящим было только ПЕРВОЕ слово, и
    # «нижний новгород проезд калашникова 12» разбиралось как улица «нижний
    # новгород проезд калашникова»: город уезжал в поле `street` карточки
    # заказчика (живой прогон 07.09, long_support-021). С запятой работало,
    # без — нет; тот же зазор, что стоил ФИО с датой рождения.
    #
    # ПРИЛАГАТЕЛЬНОЕ ПЕРЕД ТОПОНИМОМ, И ТОЛЬКО ОНО: «Нижний Новгород»,
    # «Великий Новгород», «Старый Оскол», «Нижний Тагил», «Сергиев Посад» —
    # весь класс устроен одинаково. Улицу это съесть не может: после первого
    # слова улицы стоит РОДОВОЕ слово, а не топоним, и вторым словом здесь
    # обязан быть топоним по той же строгой мерке, что и первым.
    if all(parse.tag.POS == "ADJF" for parse in MORPH.parse(word)):
        second = _LEADING_WORD.match(phrase[match.end():].lstrip())
        if second is not None and _is_settlement_word(second.group(1).lower()):
            shift = len(phrase[match.end():]) - len(phrase[match.end():].lstrip())
            return re.compile(
                r"(?s)(" + re.escape(word + phrase[match.end():match.end() + shift]
                                     + second.group(1)) + r")").match(phrase)
        return None
    parses = MORPH.parse(word)
    # A SURNAME-COLLIDING SETTLEMENT MAY PASS WITHOUT `Geox`. «одоев», «венёв»,
    # «белёв» are towns pymorphy reads only as a surname, so the Geox gate below
    # refused them and the city never joined its street. The leased gazetteer
    # admits them, and the checks BELOW — a street-type word or a comma right
    # after — are what still keep a bare «одоев» from being read as a place:
    # without either signal the surname veto at the bottom returns None.
    if (not any("Geox" in parse.tag.grammemes for parse in parses)
            and word.lower() not in _settlement_gaz()):
        return None
    # A PREDICTED place reading — the word is not in the dictionary — counts
    # only with the structure a settlement stands in: a comma or a street-type
    # word after it. «лугвая сто шестнадцать» is a mistyped street that
    # pymorphy3 guessed to be a town, and the address grew a city it never had.
    if not any(parse.is_known for parse in parses):
        rest_ = phrase[match.end():].lstrip().split()
        next_ = rest_[0].lower().strip(".,") if rest_ else ""
        if not (match.group(0).rstrip().endswith(",") or next_ in _GENERIC or _GENERIC_STEMS.match(next_)):
            return None
    # A TYPE WORD RIGHT AFTER IT SETTLES THE ROLE: «глазов проспект
    # маяковского» — Глазов is a surname too, but a person is never followed
    # by «проспект <name>», a town is. Without this the substitute was
    # minted without the city the customer named.
    rest = phrase[match.end():].lstrip().split()
    following = rest[0].lower().strip(".,") if rest else ""
    after_type = rest[1].strip(".,") if len(rest) > 1 else ""
    if (following and (following in _GENERIC or _GENERIC_STEMS.match(following))
            and after_type and not after_type[:1].isdigit() and not spoken.is_numeral_word(after_type)):
        # …and the type word is followed by the STREET'S NAME, not a number:
        # «пушкина улица 5» is a street written name-first, «глазов проспект
        # маяковского» is a town before a street.
        return match
    # A COMMA RIGHT AFTER THE WORD, WITH A CLAUSE BEHIND IT, is how a record
    # writes its city: «глазов, дзержинского, 19». Nobody writes a person that
    # way, so the surname reading does not veto here — without this the CRM
    # card's address lost its city and the city LEAF was shown the whole
    # substitute (live v4, chain-009: «"city": "улица Каштановая 101, кв. 199"»).
    if match.group(0).rstrip().endswith(",") and rest:
        return match
    if any("Surn" in parse.tag.grammemes or parse.tag.POS == "ADJF" for parse in parses):
        return None
    return match


_LEADING_CITY = re.compile(
    r"^(?:[гГ]\.?\s*)?([А-ЯЁ][А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)*(?:\s[А-ЯЁ][А-ЯЁа-яё]+)?),\s*(?=\S)")
_STREET_TYPE_LEAD = re.compile(
    r"(?i)^(?:ул\.?|улица|улице|улицу|пр-т|пр\.?|просп\.?|проспект\w*|пер\.?|переулок|переулк\w*|"
    r"б-р|бульвар\w*|ш\.?|шоссе|пл\.?|площад\w*|наб\.?|набережн\w*|проезд\w*|тупик\w*|аллея|аллее)\s+")


# WHICH FIELD HOLDS WHICH PART OF AN ADDRESS — one list for both legs. The
# restorer reads a tool call's `address.locality` / `street` / `building`; the
# detector reads a tool RESULT's `city` / `street` / `house`. The vocabulary
# is the structure of delivery schemas (CDEK, Yandex, DaData), not tuned data.
FIELD_ROLES: tuple[tuple[str, str], ...] = (
    ("street", "street"), ("house", "house"), ("building", "house"),
    ("flat", "flat"), ("apartment", "flat"), ("apt", "flat"), ("sflat", "flat"),
    ("entrance", "entrance"), ("porch", "entrance"), ("floor", "floor"),
    # The settlement is a field of its own in every delivery schema (CDEK
    # `city`, Yandex `locality`); without a role here a bare fake city in it
    # was never asked about and reached the tool as «Сортавала».
    ("city", "city"), ("locality", "city"), ("town", "city"), ("settlement", "city"),
    # THE NAMES THE SAME PART GOES BY IN THE SCHEMAS PEOPLE ACTUALLY WRITE (W1).
    # `_join_one_address` rewrites only the leaves whose role it can READ FROM
    # THE FIELD NAME, so a part spelled in a name this table does not carry is
    # never rewritten — it stays the FAKE while its neighbours are restored, and
    # the tool receives half a real address under a 200. Measured: `build` and
    # `corpus` (`{"street","build","corpus","entrance","floor","flat"}`) stayed
    # fake in both legs. The list stays NARROW and word-for-word: every entry is
    # a spelling of an address part — a transliteration of the Russian word, an
    # abbreviation the delivery schemas use, or the CDEK/DaData spelling — and
    # not an English word that merely CAN mean one. `block`, `case`, `room` and
    # `home` are DELIBERATELY absent for that reason: in a legal or hotel schema
    # they name a case number, a corridor and a hotel room, and typing them as
    # an address part is how a customer's own number becomes a house.
    ("build", "house"), ("dom", "house"), ("sbuild", "house"), ("nbuild", "house"),
    ("housenumber", "house"), ("house_number", "house"),
    ("kv", "flat"), ("kvartira", "flat"), ("nflat", "flat"),
    ("corpus", "building"), ("korpus", "building"),
    ("podezd", "entrance"), ("etazh", "floor"),
    ("ulica", "street"), ("ulitsa", "street"), ("sstreet", "street"),
    ("streetname", "street"), ("street_name", "street"),
)
# СОСТАВНОЕ ИМЯ РОЛИ: «street_type» / «streetType» — ДВА СЛОВА, А НЕ ОДНО, и по
# одному слову его не узнать. `FIELD_ROLES` держит одиночные слова, поэтому
# составное имя проверяется парой соседних токенов; «type» само по себе роли НЕ
# получает — в объекте с адресом оно с тем же успехом значит «тип заявки».
_COMPOUND_ROLES: tuple[tuple[str, str, str], ...] = (
    ("street", "type", "street_type"), ("street", "kind", "street_type"),
)
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def field_tokens(name: str) -> list[str]:
    """Имя поля токенами: `_`, `.` и camelCase — все три разделителя схем.

    ТОЧКА ТОЖЕ РАЗДЕЛИТЕЛЬ. `courier_book.address.street` — путь, а не имя:
    пока точка не резалась, `field_role` возвращал («», «») для целого листа,
    роль у него не находилась, он восстанавливался одиночным текстовым проходом
    мимо соединения адреса — и тип улицы терялся (g02/m-112). Тот же лист,
    написанный вложенным объектом, соединение находило.
    """
    return [token for token in _CAMEL_RE.sub("_", name).lower()
            .replace(".", "_").split("_") if token]


def field_role(name: str) -> tuple[str, str]:
    """(the schema word that names the part, its role) for a field, or ("", "")."""
    parts = field_tokens(name)
    for index, word in enumerate(parts):
        for first, second, role in _COMPOUND_ROLES:
            if word == first and index + 1 < len(parts) and parts[index + 1] == second:
                return f"{first}_{second}", role
    for word, role in FIELD_ROLES:
        if word in parts:
            return word, role
    return "", ""


def field_prefix(name: str) -> str:
    """Приставка, которой схема различает ДВА адреса в одном вызове.

    `book_ride` просит `pickup_street`/`pickup_house` и
    `dropoff_street`/`dropoff_house`: скопом они дают двух владельцев, правило
    единственного отказывает, и не разрешается ни один адрес. Приставка — это
    то, что остаётся от имени, когда из него вынуто СЛОВО РОЛИ; считается она
    по тем же токенам, что и роль, поэтому `address.street`,
    `address.street_type` и `streetType` попадают в одну группу, а `pickup_*`
    и `dropoff_*` — в разные.
    """
    words = frozenset(word for word, _ in FIELD_ROLES) | {"type", "kind"}
    return "_".join(token for token in field_tokens(name) if token not in words)


def role_of_field(name: str) -> str:
    """The address part a schema field holds, or "" for a field that holds none."""
    return field_role(name)[1]


SETTLEMENT_MARKER_RE = re.compile(
    r"(?i)^(?:г|гор|город|пос|посёлок|поселок|село|дер|деревня|станица|пгт|рп|хутор|аул)\.?\s+")


def city_case(phrase: str) -> str | None:
    """The case of the settlement alone. `detect_case` reads the whole phrase
    and a nominative street outvotes an oblique city: «Валдае, улица Мира 4»
    is nominative to it, and the substitute came out «Живу на Валдай, …»."""
    city = SETTLEMENT_MARKER_RE.sub("", split_roles(phrase).get("city", "").strip(" ,."))
    return detect_case(city) if city else None


def address_from_fields(fields: dict[str, str]) -> str:
    """The address a record spells out field by field, written as one line
    in the register's order — the string the vault keys and mints for."""
    out: list[str] = []
    if fields.get("city"):
        out.append(fields["city"])
    out.append(fields["street"])
    out.append(fields["house"])
    if fields.get("building"):
        out.append(f"корп. {fields['building']}")
    if fields.get("entrance"):
        out.append(f"подъезд {fields['entrance']}")
    if fields.get("floor"):
        out.append(f"этаж {fields['floor']}")
    if fields.get("flat"):
        out.append(f"кв. {fields['flat']}")
    return ", ".join(out)


def part_in_form_of(agent_part: str, real_part: str, role: str) -> str:
    """Одна часть адреса, вписанная в форму, которой пользуется агент.

    То же правило, что `in_form_of` для целой фразы, но для ОДНОГО поля схемы.
    Агент написал в `house` цифры — настоящий дом, сказанный словами, уходит
    цифрами («шестьдесят три» -> «63»); написал улицу без слова-типа — слово-тип
    настоящей улицы снимается («ул. Ленина» -> «Ленина»); написал со словом-типом
    — его слово остаётся перед настоящим названием. Измерено на скриптовом
    агенте: «двадцать три» в `building` отвергалось парсером Яндекс Доставки как
    `house_format`, а «Москва, ул. Ленина» в `street` уезжало городом в улицу.
    """
    if role in ("house", "flat", "entrance", "floor", "building"):
        if _ANY_DIGIT.search(agent_part) and not _ANY_DIGIT.search(real_part):
            return _part_to_digits(real_part) or real_part
        return real_part
    if role == "street":
        # THE CUSTOMER'S STREET, AS WRITTEN — the type word is his or absent,
        # never ours. `real_part` already carries the customer's own form
        # («бисертская» bare, «ул Ленина» with his marker); the agent's part
        # carries OUR fake's marker («улица Вязовая»), which is not the
        # customer's choice. Laying the fake's «улица» onto the real street
        # gave a tool «улица Бисертская» for a customer who wrote a bare
        # «бисертская» — us adding a word he did not write. The type word is
        # content the customer either wrote or did not, so it comes from the
        # record, not from the substitute the model happened to copy.
        return real_part.strip()
    if role == "street_type":
        # РОДОВОЕ СЛОВО — СВОЯ ЧАСТЬ, И СОДЕРЖИМОЕ ЕЁ — ИЗ ЗАПИСИ. Клиент написал
        # «переулок» или не написал ничего; подмена, которую скопировал агент,
        # несёт НАШ тип — но он зеркалит клиентский, поэтому в поле уезжает
        # именно слово записи («переулок»), а не «бульвар» из подмены. Форма
        # (сокращение ли) — агентская, как и у всякой части адреса: написал он
        # «ул» — уходит сокращение той же полной формы; написал полное слово —
        # уходит полное.
        written = agent_part.strip().strip(".")
        real = real_part.strip()
        if written and written.lower() in _GENERIC_SHORT and real:
            for short, (full, _sex) in _GENERIC_SHORT.items():
                if full == real.lower().strip("."):
                    return short
        return real
    # CITY AND ANY OTHER TEXT ROLE — the customer's part as written. A city
    # («Самара») has no marker to strip and no digits to convert; it goes to
    # the tool verbatim, in the agent's case (the caller applies it). Without
    # this branch the city role fell through to an implicit `None` and the
    # restore crashed the moment a `city` field was asked.
    return real_part.strip()


_ANY_DIGIT = re.compile(r"\d")
_ORDINAL_TO_INT: dict[str, int] = {
    "перв": 1, "втор": 2, "трет": 3, "четв": 4, "пят": 5, "шест": 6,
    "седьм": 7, "восьм": 8, "девят": 9, "десят": 10, "одиннадцат": 11,
    "двенадцат": 12,
}
_TRAILING_LITERA = re.compile(r"\s+([а-яё])$")


def house_digits(part: str) -> str:
    """Номер дома цифрами, как бы он ни был написан — «пятьдесят девять» -> «59».

    Публичная обёртка над `_part_to_digits`: разряд номера дома нужен чеканке
    (`vault._house_like`), а вторая читалка тех же форм разошлась бы с этой
    ровно так, как расходятся все вторые читалки в этом файле.
    """
    return _part_to_digits(part)


def _part_to_digits(part: str) -> str:
    """Часть адреса, сказанная словами, — цифрами. Литера дома остаётся буквой.

    Порядковое («первый подъезд») числительным не является, поэтому его таблица
    отдельная и по ОСНОВЕ: «четвёртый», «четвертого», «четвёртом» — одно и то же
    число, а падеж здесь ничего не значит.
    """
    text = part.strip()
    if not text or _ANY_DIGIT.search(text):
        return text
    litera = ""
    tail = _TRAILING_LITERA.search(text)
    if tail is not None:
        litera, text = tail.group(1), text[:tail.start()]
    # КОЛИЧЕСТВЕННОЕ ПРОБУЕТСЯ ПЕРВЫМ, И ПОРЯДОК ЗДЕСЬ — ЭТО ПРАВИЛЬНОСТЬ НОМЕРА
    # ДОМА. Основа «шест» открывает и «шестой», и «шестнадцать»: при обратном
    # порядке «воронцовский шестнадцать» уезжало в CRM домом номер 6.
    words = re.findall(r"[а-яё]+", text.lower())
    # `run_to_digits` ждёт прогон, УЖЕ признанный числительным, и на чужом слове
    # падает по ключу — поэтому состав проверяется здесь, а не ловится исключение.
    if words and all(spoken.is_numeral_word(word) for word in words):
        digits = spoken.run_to_digits(words)
        if digits:
            return f"{digits}{litera}"
    for stem, value in _ORDINAL_TO_INT.items():
        if text.lower().startswith(stem) and _ORDINAL_ONLY.fullmatch(text):
            return f"{value}{litera}"
    return part.strip()


_WORD_OF_DIGIT = {
    "0": "ноль", "1": "один", "2": "два", "3": "три", "4": "четыре",
    "5": "пять", "6": "шесть", "7": "семь", "8": "восемь", "9": "девять",
    "10": "десять", "11": "одиннадцать", "12": "двенадцать",
    "13": "тринадцать", "14": "четырнадцать", "15": "пятнадцать",
    "16": "шестнадцать", "17": "семнадцать", "18": "восемнадцать",
    "19": "девятнадцать", "20": "двадцать", "30": "тридцать", "40": "сорок",
    "50": "пятьдесят", "60": "шестьдесят", "70": "семьдесят",
    "80": "восемьдесят", "90": "девяносто", "100": "сто", "200": "двести",
    "300": "триста", "400": "четыреста", "500": "пятьсот", "600": "шестьсот",
    "700": "семьсот", "800": "восемьсот", "900": "девятьсот",
}


def _spell_number(digits: str) -> str:
    """Целое число словами: «81» -> «восемьдесят один». Пусто, если не выходит."""
    if not digits.isdigit() or not 0 < int(digits) < 1000:
        return ""
    rest, words = int(digits), []
    for size in (100, 10, 1):
        if rest == 0:
            break
        if str(rest) in _WORD_OF_DIGIT:
            words.append(_WORD_OF_DIGIT[str(rest)])
            rest = 0
            break
        chunk = rest - rest % size
        if chunk:
            words.append(_WORD_OF_DIGIT[str(chunk)])
            rest -= chunk
    return " ".join(words)


def _like(part: str, model: str) -> str:
    """Настоящая часть в том СТИЛЕ ЧИСЛА, которым написана часть модели."""
    if not model:
        return part
    if _ANY_DIGIT.search(model):
        return _part_to_digits(part)
    if _ANY_DIGIT.search(part):
        spelled = _spell_number(re.sub(r"\D", "", part))
        litera = part[len(re.sub(r"\D", "", part)):].strip()
        if spelled:
            return f"{spelled} {litera}".strip()
    # И РЕГИСТР ТОЖЕ АГЕНТСКИЙ. Город хранится в волте строчным, потому что
    # ключ ищется без учёта регистра; агент пишет «Краснодар», а в CRM
    # уезжало «краснодар».
    return agent_form.cased_like(part, model)


def _agent_type(model: str) -> tuple[int, str]:
    """(позиция родового слова в строке писавшего, само слово) или (-1, "").

    ЗАМЕНИЛ `_leading_generic`, КОТОРЫЙ ЧИТАЛ ТОЛЬКО НАЧАЛО СТРОКИ. «Садовая
    улица» (тип в конце) считалась отсутствием типа — а «название первым» это
    обычная форма подмены, которую чеканит `_fake_place` для «проспекта» и
    «бульвара» (голова собирается как `<название> <тип>`). На такой строке типа
    не находилось ни у подмены, ни у настоящей улицы, и обе ноги теряли его
    СИММЕТРИЧНО: клиенту показывали «Барбарисовый» вместо «Барбарисовый
    переулок», инструменту отдавали «Светлый» вместо «Светлый переулок» — то
    есть «переулок Пушкина» и «улица Пушкина» становились неразличимы для CRM
    (g02/m-074, m-112).
    """
    for index, word in enumerate(model.split()):
        if is_generic_word(word):
            return index, word
    return -1, ""


def _street_like(street: str, model: str) -> str:
    """Настоящая улица в форме АГЕНТА: его тип (или его отсутствие) + название.

    Форма принадлежит агенту, СОДЕРЖИМОЕ — записи клиента, и тип улицы —
    содержимое: клиент либо написал «улица», либо нет. Отсюда три правила, и
    все три измерены:

    * Клиент написал улицу БЕЗ типа («бисертская», «луговая») — типа в аргументе
      не будет, даже если агент скопировал наш фейк «улица Вязовая» дословно.
      Мы не дописываем слово, которого в записи клиента нет: «улица Бисертская»
      на голую «бисертскую» — это МЫ добавили «улица» (25 адресов «по полям»).
    * Агент поставил тип ПЕРЕД названием — уходит ЕГО маркер: клиент «улица»,
      агент сократил до «ул.» — уходит «ул.». Это его нотация, и она несёт его
      сокращение и его регистр.
    * Агент поставил тип ПОСЛЕ названия (или написал улицу без типа) — слово
      берётся ИЗ ЗАПИСИ, в позиции агента. Позиция «название первым» — обычная
      для подмены, и тип в ней стоит на своём естественном месте; слово же —
      содержание записи, а не то, что агент скопировал из нашей подмены.
      Агент вовсе опустил тип — уходит одно название (запись его не добавит).

    `street` — роль настоящего адреса (тип у неё есть ⇔ клиент его написал);
    `model` — та же роль в строке агента (несёт его маркер, сокращение и
    РЕГИСТР: агент написал подмену «Вязовая» с заглавной — настоящее «мончгорская»
    уходит «Мончгорская», как и всякая часть адреса через `_like`).

    ВЕДУЩИЙ МАРКЕР — ВСЕГДА МАРКЕР АГЕНТА, и он остаётся даже тогда, когда в
    записи клиента типа нет вовсе: «ул. Родниковой, д. 9» модель собрала сама,
    из голого листа «родниковой», и «ул.» — её собственное обозначение, а не
    наше (E04/tool_chain-017). Тип в СЕРЕДИНЕ строки так не работает: там он
    стоит на месте, которое запись занимает своим словом.
    """
    case: str | None = street_case(model)
    inflected: str = inflect_place(street, case) if case not in (None, "nomn") else street
    words = inflected.split()
    named = [w for w in words if not is_generic_word(w)]
    real_name = " ".join(named) if named else street
    record_type = [w for w in words if is_generic_word(w)]
    position, agent_word = _agent_type(model)
    if position == 0:
        result = f"{agent_word} {real_name}"
    elif position > 0 and record_type:
        result = f"{real_name} {record_type[-1]}"
    else:
        result = real_name
    return agent_form.cased_like(result, model)

def in_form_of(value: str, surface: str) -> str:
    """Настоящий адрес, вписанный В ФОРМУ, КОТОРОЙ ПОЛЬЗУЕТСЯ АГЕНТ.

    ЧТО БЫЛО НЕ ТАК. Восстановление подставляло вместо подмены нашу строку
    целиком, и форма приходила наша: клиент диктует «гусева восемьдесят один
    квартира сто семнадцать», модель кладёт в аргумент «ул. Липовая, д. 119,
    кв. 10» — письменную форму нашей же подмены, — а обратно уезжало
    «гусева восемьдесят один квартира сто семнадцать», которое CRM не исполнит.
    Своя каноническая форма чинит это ровно наполовину: она не ломает CRM, но
    ломает то, что агент передавал, и навязывает нашу пунктуацию его схеме.

    ФОРМА ПРИНАДЛЕЖИТ АГЕНТУ, СОДЕРЖИМОЕ — ВОЛТУ. Строка модели разбирается на
    роли с границами, и каждая часть заменяется настоящей ВНУТРИ неё: маркеры,
    порядок и пунктуация остаются агентские, стиль числа — тоже («д. 119» ->
    «д. 81», «сто девятнадцать» -> «восемьдесят один»).

    ЧАСТЬ, КОТОРОЙ У НАСТОЯЩЕГО АДРЕСА НЕТ, УДАЛЯЕТСЯ. Модель дописала
    квартиру, которой клиент не называл, — оставить её значит отдать
    инструменту выдуманное значение под видом настоящего.

    ЧАСТЬ, КОТОРОЙ НЕТ У МОДЕЛИ, НЕ ДОПИСЫВАЕТСЯ, и это то же правило с другой
    стороны. Схема инструмента может просить улицу и дом без подъезда — агент
    тогда пишет их и только их, — и дописанный нами «подъезд 2» ломает ровно то,
    что мы обещали не ломать. Форма принадлежит агенту целиком: и то, что в ней
    есть, и то, чего в ней нет.
    """
    surface = surface.strip()
    if not surface:
        return value
    theirs = role_spans(surface)
    ours = split_roles(value)
    # A resolved address can be projected onto numeric roles alone. Requiring
    # a street on the sender side expands a lone flat into the entire address.
    if not theirs or "street" not in ours:
        return value
    spans: list[tuple[int, int, str]] = []
    for role, (start, end) in sorted(theirs.items(), key=lambda item: item[1][0]):
        model_part = surface[start:end]
        if role not in ours:
            # Хвостовой маркер уходит вместе со своим числом; иначе в строке
            # остаётся «, кв.» без номера.
            spans.append((_marker_start(surface, start), end, ""))
            continue
        spans.append((start, end,
                      _street_like(ours[role], model_part) if role == "street"
                      else _like(ours[role], model_part)))
    out = _splice_parts(surface, spans)
    return re.sub(r"\s{2,}", " ", out).strip().strip(",").strip()


_MARKER_BEFORE = re.compile(
    r"(?i),?\s*\b(?:кв|кварт\w*|офис\w*|оф|помещени\w*|пом|комн\w*|кабинет\w*|каб"
    r"|под[ъь]езд\w*|под|этаж\w*"
    r"|корп\w*|кор|стр|строен\w*|литер\w*|лит|дом|д)\.?\s*$")


def _marker_start(text: str, start: int) -> int:
    """Начало маркера, стоящего вплотную перед частью, или сама часть."""
    hit = _MARKER_BEFORE.search(text[:start])
    return hit.start() if hit is not None else start


def _splice_parts(text: str, spans: list[tuple[int, int, str]]) -> str:
    out, last = [], 0
    for start, end, piece in sorted(spans):
        if start < last:
            continue
        out.append(text[last:start])
        out.append(piece)
        last = end
    out.append(text[last:])
    return "".join(out)


_CITY_LEAD = re.compile(r"^[А-ЯЁ][а-яё-]+,\s+")
_TAIL_MARKER = re.compile(
    r"(?i),?\s*\b(?:кв|кварт\w*|офис\w*|оф|помещени\w*|пом|комн\w*|кабинет\w*|каб"
    r"|под[ъь]езд\w*|под|этаж\w*)\b")


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


# =====================================================================================
# D-081 (W8): АДРЕС — ЯДРО И РАСТУЩИЕ НА НЁМ ЧАСТИ.
# =====================================================================================
# РЕШЕНИЕ ВЛАДЕЛЬЦА (OWNER-DECISIONS-PHASE4B.md, кластер A): тождество адреса —
# УЛИЦА И ДОМ, и оно ОДНО. Корпус/строение, подъезд, этаж и квартира — ИЗМЕНЯЕМЫЕ
# ЧАСТИ на том же ядре: две квартиры в одном доме получают ОДНУ подменную улицу и
# дом, но РАЗНЫЕ подменные квартиры, поэтому два разных человека в одном доме
# остаются различимыми, а поправка «ой не та квартира» не чеканит новый адрес.
#
# ЧИТАТЕЛЬ ОДИН. Части разбирает `split_roles` (та же пара `role_spans` +
# маркеры, которой `in_form_of` выкладывает подмену в форму клиента), а диктовку
# сворачивает `house_digits` — вторая читалка той же фразы разошлась бы с первой,
# как расходятся в этом файле все вторые читалки.
MUTABLE_PLACE_ROLES: tuple[str, ...] = ("building", "entrance", "floor", "flat")
# РАЗДЕЛИТЕЛЬ ХВОСТА-ПОДПИСИ ЧАСТЕЙ. \x1f не встречается в адресной фразе, а
# хвост стоит ПОСЛЕ обычного ключа, поэтому диапазонные чтения по
# `(customer, canonical)` — и префиксные (`vault._real_place_with_stem_locked`:
# «canonical LIKE <основа>%»), и слотовые (`vault._place_family_owner`) — видят
# строку там же, где видели её без частей. Читатели тождества и типа снимают
# хвост сами (`strip_parts_key`), поэтому тип места не теряется.
PART_SEPARATOR = "\x1f"
# МАРКЕР, СТОЯЩИЙ ПОСЛЕ ЧИСЛА. «3 подъезд», «2 корпус» — основная форма
# диспетчерской речи, и без неё `core_phrase` оставлял бы маркер в ядре.
_MARKER_AFTER = re.compile(
    r"(?i)^[\s,]*\b(?:под[ъь]езд\w*|под|этаж\w*|эт|корп\w*|кор|стр\w*|строен\w*"
    r"|литер\w*|лит|кабинет\w*|каб)\.?")


def mutable_parts(phrase: str) -> dict[str, str]:
    """Изменяемые части адреса: роль -> значение ЦИФРАМИ («семь» -> «7»).

    Пустая часть (маркер без числа) ролью не становится: «…, кв» не называет
    квартиры, и подмены ей не чеканится.
    """
    roles = split_roles(phrase)
    out: dict[str, str] = {}
    for role in MUTABLE_PLACE_ROLES:
        value = house_digits((roles.get(role) or "").strip())
        if value:
            out[role] = value
    return out


def core_phrase(phrase: str) -> str:
    """Тот же адрес БЕЗ изменяемых частей: город, улица, дом.

    Хвост, названный ролью, вырезается ЦЕЛИКОМ — и маркер, стоящий перед числом
    («, квартира 7»), и маркер, стоящий после него («3 подъезд»): оставленный
    маркер сделал бы из ядра второе тождество.
    """
    spans = role_spans(phrase)
    drops: list[tuple[int, int]] = []
    for role in MUTABLE_PLACE_ROLES:
        span = spans.get(role)
        if span is None:
            continue
        start, end = span
        start = min(start, _marker_start(phrase, start))
        after = _MARKER_AFTER.match(phrase[end:])
        if after is not None:
            end += after.end()
        drops.append((start, end))
    if not drops:
        return phrase
    out: list[str] = []
    last = 0
    for start, end in sorted(drops):
        if start < last:
            continue
        out.append(phrase[last:start])
        last = end
    out.append(phrase[last:])
    text = "".join(out)
    text = re.sub(r"[ \t]*,[ \t]*(?=[,;]|$)", "", text)
    text = re.sub(r"[\s,;]+$", "", text)
    text = re.sub(r"^[\s,;]+", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def place_core_key(phrase: str) -> str:
    """ТОЖДЕСТВО адреса (D-081): улица и дом, и ничего кроме.

    Ключ улицы, дома и города — тот же `address_key`, построенный на фразе без
    изменяемых частей, поэтому упоминание без частей («улица Лермонтова дом 38»)
    даёт РОВНО этот ключ и встречается со своей полной формой, а упоминание с
    квартирой или корпусом — тот же ключ, но строка волта у него своя
    (`place_parts_key`).
    """
    core = core_phrase(phrase)
    return address_key(core if core.strip() else phrase)


def parts_signature(parts: dict[str, str]) -> str:
    """Подпись изменяемых частей: роль=значение, в русском порядке.

    Она и есть то, чем различаются строки одного дома: «flat=7» и «flat=42» —
    разные строки, а одно значение дважды — одна и та же.
    """
    return PART_SEPARATOR.join(f"{role}={parts[role]}"
                               for role in MUTABLE_PLACE_ROLES if role in parts)


def place_parts_key(phrase: str) -> str:
    """КЛЮЧ СТРОКИ ВОЛТА, КОГДА ЧАСТИ НАЗВАНЫ: обычный ключ адреса + подпись.

    Ключ адреса (`address_key`) значения частей выбрасывает — по решению
    владельца это тождество. Но СТРОКЕ волта их мало: два человека в одном доме
    обязаны быть ДВУМЯ строками, и упоминание БЕЗ частей обязано отличаться от
    упоминания С частями — иначе короткое «Энгельса 54» наследует фантомную
    квартиру от «Энгельса 54 кв 189» (тот же обычный ключ после identity-split).
    Поэтому КАЖДАЯ подпись частей получает хвост-подпись. ХВОСТ, А НЕ ПРЕФИКС:
    `canonical LIKE «<основа>%»` (`vault._real_place_with_stem_locked`) обязан эту
    строку видеть.
    """
    plain = address_key(phrase)
    parts = mutable_parts(phrase)
    if not parts:
        return plain
    return f"{plain}{PART_SEPARATOR}{parts_signature(parts)}"


def strip_parts_key(canonical: str) -> str:
    """Ключ строки волта без хвоста-подписи частей — то, что читают тождество и тип."""
    head, separator, _rest = canonical.partition(PART_SEPARATOR)
    return head if separator else canonical
