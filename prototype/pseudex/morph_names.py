"""Russian personal-name morphology: gender, case, nominative form, inflection.

WHY THIS EXISTS. A fake that disagrees with itself — `Екатерина Цветков`,
`Руслан Хвостова` for a woman — makes the language model REPAIR it, and a
repaired token no longer matches the vault, so the customer's tool receives a
person who does not exist. Persona runs hit this in roughly one dialogue in ten
and it fails silently. The cure is upstream of detokenization: give the model
nothing to fix.

It also gives the vault a case-invariant key. Without one, `Иванов Пётр`,
`Иванову Петру` and `Иванова Петра` are three different people, the agent's
memory fills with strangers, and the protected-value counter multiplies.

THE ONE RULE THAT MATTERS: never trust `parse(word)[0]`. pymorphy3's first
reading for a name is routinely the wrong part of speech —

    Иванова          -> lemma "иванов",  masc, GENITIVE   (it is a woman, nominative)
    Черных           -> lemma "чёрный"   (the adjective "black")
    Седых            -> lemma "седой"    (the adjective "grey-haired")
    Салтыков-Щедрин  -> lemma "салтык-щедрина"

Filtering to parses tagged `Surn`/`Name`/`Patr` fixes all but the last class.
This module never looks at an unfiltered first parse.

This is ALGORITHM, so it ships in the engine. The name pools it inflects are
tuned data and stay in the leased bundle — see `docs/tz-license-packaging.md`.
"""

import functools
import re

# The SHARED analyzer, never a second one. `pseudex/morph.py` exists precisely
# to keep one instance per process — a second MorphAnalyzer loads the whole
# dictionary again, and this module is imported by the vault, which every worker
# loads. Measured cost of the duplicate that was here first: +20 MB per worker,
# multiplied by the worker count.
from pseudex.assets import ASSETS
from pseudex.fuzzy import within_one_typo
from pseudex.morph import MORPH as _MORPH

# The grammemes that mark a parse as part of a personal name. A parse without
# one of these is some other word that happens to be spelled the same, which is
# the entire failure mode described above.
_NAME_TAGS = frozenset({"Surn", "Name", "Patr"})

# Patronymic suffixes, longest first so -овна is not matched as -вна.
_PATR_FEMN = ("овна", "евна", "ична", "инична",
              # Turkic patronymics: pymorphy3 does not tag these `Patr` at all
              # (`кызы` is not recognised as a word), so the suffix list is the
              # only signal we have for them.
              "кызы", "гызы", "кизи", "кзы")
_PATR_MASC = ("ович", "евич", "ич", "оглы", "улы", "уулу", "углы", "угли")

# Feminine surnames end in these; the masculine counterpart drops the vowel.
# Used only when morphology gives no gender at all, and only as a hint.
_SURN_FEMN = ("ова", "ева", "ина", "ына", "ская", "цкая", "ая", "яя")

_CASES = ("nomn", "gent", "datv", "accs", "ablt", "loct")

# Masculine given names ending in -а/-я. The ending is otherwise a reliable
# feminine signal for Russian given names, and these are the exceptions that
# would flip a man to a woman. pymorphy3 knows them, so this list only guards
# the fallback path — but the fallback is exactly where a wrong answer becomes
# a wrong gender for a real customer.
_MASC_NAMES_IN_A = frozenset({
    "никита", "лука", "фома", "кузьма", "савва", "данила", "гаврила", "илья",
    "миша", "юра", "костя", "дима", "серёжа", "сережа", "ваня", "петя", "коля",
})

# The regular possessive-surname paradigm, applied when pymorphy3 has no `Surn`
# reading for a word. It is not a guess: -ов/-ев/-ин/-ын surnames decline as a
# closed and exceptionless system, and the dictionary simply does not contain
# every surname in Russia. Without this, `Хвостов` reads as the genitive plural
# of `хвост` and never inflects, so the text says `Позвоните Руслана Хвостов` —
# the exact disagreement that makes a model rewrite the name.
_SUFFIX_ENDINGS = {
    "masc": {"nomn": "", "gent": "а", "datv": "у", "accs": "а", "ablt": "ым", "loct": "е"},
    "femn": {"nomn": "а", "gent": "ой", "datv": "ой", "accs": "у", "ablt": "ой", "loct": "ой"},
}
_POSSESSIVE_SUFFIXES = ("ов", "ев", "ёв", "ин", "ын")

# Adjectival surnames (Достоевский / Достоевская) follow the adjective
# paradigm, which is equally regular and equally likely to be missing.
# Adjectival surnames come in TWO paradigms and conflating them is wrong in the
# instrumental: Достоевский -> Достоевск+им, but Яровой -> Яров+ым. Only the
# ending is ever stripped — never the `ск`/`цк`, which belongs to the stem, or
# `Достоевский` turns into `Достоевая`.
_ADJ_SOFT = {   # -ский / -цкий / -ний
    "masc": {"nomn": "ий", "gent": "ого", "datv": "ому", "accs": "ого", "ablt": "им", "loct": "ом"},
    "femn": {"nomn": "ая", "gent": "ой", "datv": "ой", "accs": "ую", "ablt": "ой", "loct": "ой"},
}
_ADJ_HARD = {   # -ой (stressed: Яровой, Толстой) / -ый (Белый)
    "masc": {"nomn": "ый", "gent": "ого", "datv": "ому", "accs": "ого", "ablt": "ым", "loct": "ом"},
    "femn": {"nomn": "ая", "gent": "ой", "datv": "ой", "accs": "ую", "ablt": "ой", "loct": "ой"},
}
# (tail to strip, paradigm). Longest first so `ский` is not clipped as `ий`.
_ADJECTIVAL_TAILS = (
    ("ский", _ADJ_SOFT), ("ская", _ADJ_SOFT),
    ("цкий", _ADJ_SOFT), ("цкая", _ADJ_SOFT),
    ("ой", _ADJ_HARD), ("ый", _ADJ_HARD), ("ая", _ADJ_HARD), ("ий", _ADJ_SOFT),
)


def _paradigm_inflect(word: str, case: str, gender: str) -> str | None:
    """Inflect by suffix rule. Returns None when no rule applies."""
    lowered = word.lower()
    stem: str | None = None

    for suffix in _POSSESSIVE_SUFFIXES:
        if lowered.endswith(suffix):
            stem = word
            break
        if gender == "femn" and lowered.endswith(suffix + "а"):
            stem = word[:-1]
            break
    if stem is not None:
        return stem + _SUFFIX_ENDINGS[gender][case]

    for tail, paradigm in _ADJECTIVAL_TAILS:
        if not lowered.endswith(tail):
            continue
        # `ский`/`ская` share the `ск` stem, so strip only the two-letter
        # adjective ending and leave `ск` where it belongs.
        strip = 2 if len(tail) == 4 else len(tail)
        if len(word) - strip < 3:
            # Too short to be a surname stem; a common word that merely ends
            # in `-ой` should not be inflected as one.
            continue
        # Stress is not recoverable from spelling — `Яровой` and `Белый` are the
        # same paradigm with different stress — so asking for the masculine
        # nominative of a word that already IS one would turn Яровой into
        # Яровый. Return it untouched instead of guessing.
        if case == "nomn" and gender == "masc" and tail in ("ой", "ый", "ий"):
            return word
        return word[:-strip] + paradigm[gender][case]
    return None


def _name_parses(word: str) -> list:
    """Parses that pymorphy3 itself considers part of a personal name — and,
    when it offers NONE, the feminine first-declension readings it holds under
    another label. «София» is in OpenCorpora only as the city (`Geox`), and that
    reading declines exactly like the name; with no name parse the word was
    called indeclinable everywhere at once, so «к Анне Черных» was masked as
    «к София Пановой» (the given name frozen in the nominative while the surname
    moved), the way back read the case off the surname alone, and «Софии Пановой»
    keyed as «Софии Панова». One door, used by every reader of a name part:
    case, gender, nominative, inflection. Feminine and first declension only
    (lemma in -а/-я, known to the dictionary) — that is where a name shares its
    paradigm with a common noun; a masculine word with no name reading is still
    left alone (Б21).
    """
    parses = _MORPH.parse(word)
    named = [p for p in parses if _NAME_TAGS & set(p.tag.grammemes)]
    if named or word.lower() in _MASC_NAMES_IN_A:
        return named
    return [p for p in parses
            if p.tag.POS == "NOUN" and p.tag.gender == "femn" and p.tag.number == "sing"
            and p.is_known and p.normal_form.endswith(("а", "я"))]


@functools.lru_cache(maxsize=8192)
def _is_invariant(word: str, gender: str | None = None,
                  case: str | None = None) -> bool:
    """Whether the word refuses to decline — Дюма, Черных, Шевченко, Седых.

    Read off the morphology rather than a list: an indeclinable surname parses
    into every case with the SAME form, so inflecting it and getting the input
    back is the definition, not a heuristic. A list would be permanently
    incomplete — foreign surnames arrive faster than anyone maintains a file.
    """
    parses = _name_parses(word)
    if case is not None:
        # A word that HAS a reading in the span's case is being used in that
        # case, so it declines. Without this, `Марку` inside `Марку Яровому`
        # keeps the indeclinable-surname reading pymorphy3 offers first and is
        # never normalised back to `Марк`.
        in_case = [p for p in parses if p.tag.case == case]
        if in_case and case != "nomn":
            return False
    if gender is not None:
        matching = [p for p in parses if p.tag.gender in (gender, None)]
        # A FEMININE surname ending in a consonant — Цой, Кисель, Мороз, Ким —
        # simply has no feminine reading, and Russian does not decline it. The
        # dangerous default is to fall through to the masculine paradigm, which
        # turns Ольга Кисель into Ольге Киселю. Absence of a feminine reading is
        # itself the answer.
        if gender == "femn" and parses and not matching:
            return True
        if matching:
            parses = matching
    # `Fixd` is OpenCorpora's own marker for a word that does not decline, and
    # it is exact where a heuristic is not: Дюма, Гюго, Живаго, Шевченко,
    # Пикадилли and the FEMININE readings of Ким/Мороз/Ковальчук/Черных all
    # carry it, and Иванов does not. Checking the tag beats inflecting and
    # comparing, which cannot tell "does not decline" from "declines to itself".
    if any("Fixd" in parse.tag.grammemes for parse in parses):
        return True
    if not parses:
        # No name reading. If the word still ends like a regular Russian
        # surname, the suffix paradigm applies and it is NOT invariant — that
        # is the `Хвостов` case, absent from the dictionary but perfectly
        # regular. Otherwise treating it as invariant is the safe default:
        # leaving a surname alone is a cosmetic loss, while inflecting it by a
        # guessed paradigm produces a word that does not exist (Седых -> седой).
        for gender in ("masc", "femn"):
            if _paradigm_inflect(word, "datv", gender) is not None:
                return False
        return True
    best = parses[0]
    for case in _CASES:
        inflected = best.inflect({case})
        if inflected is not None and inflected.word.lower() != word.lower():
            return False
    return True


def _gender_from_patronymic(word: str) -> str | None:
    lowered = word.lower()
    if lowered.endswith(_PATR_FEMN):
        return "femn"
    if lowered.endswith(_PATR_MASC):
        return "masc"
    return None


def name_shape(surface: str) -> tuple[str, ...]:
    """Which parts the written name has, IN THE ORDER they appear.

    Returns a tuple over «surn», «name», «patr» and «init» — an initial like
    «П.» — so a substitute can be built with the same number of words in the
    same arrangement. «Иванов Пётр Сергеевич» is (surn, name, patr); «пётр
    иванов» is (name, surn); «Иванов П.С.» is (surn, init, init).

    WHY SHAPE AND NOT JUST TYPE. A three-part name replaced by a two-part one
    changes the sentence the model is reading: the word count differs from what
    the surrounding text was built around, and a model that notices a mismatch
    is a model that rewrites it — which is precisely how a token stops resolving.
    Same argument as gender and case; this is the third axis of the same rule.

    A part that cannot be classified is reported as «name», the least
    destructive guess: an unknown word replaced by a given name still reads as a
    person, while replacing it with a patronymic would not.
    """
    shape: list[str] = []
    guessed: list[int] = []          # indexes that fell to the «name» default
    for part in surface.split():
        stripped = part.strip(".,")
        if not stripped:
            continue
        # Initials arrive both as separate tokens («П. С.») and glued («П.С.»),
        # so the test is on composition, not on length — but composition alone
        # said an all-caps WORD was a run of glued initials. «АФИНОГЕНОВА
        # СВЕТЛАНА», the way every 1C export writes a name, came back as
        # nineteen invented initials: the model was handed «Я. Т. Е. А. …» where
        # a customer's name belongs, and no tool call could carry that person.
        #
        # An initial is one letter that stands for a name we were not told, so
        # what marks it is the DOT, not the case. Two letters need a dot between
        # them or they are an abbreviation («ПС»), and beyond three letters
        # nothing is an initial at all.
        letters = sum(1 for ch in part if ch.isalpha())
        dots = part.count(".")
        if (letters and letters <= 3 and dots >= letters - 1
                and all(ch.isupper() or ch == "." for ch in part)):
            shape.extend(["init"] * letters)
            continue
        lowered = stripped.casefold()
        # Checked on the LEMMA as well as the surface: a patronymic in an oblique
        # case («Сергеевичу») does not end in the suffix, so the surface test
        # alone read it as a given name and the substitute got two of those.
        lemma = max(_MORPH.parse(stripped), key=lambda parse: parse.score).normal_form
        if (lowered.endswith(_PATR_FEMN) or lowered.endswith(_PATR_MASC)
                or lemma.endswith(_PATR_FEMN) or lemma.endswith(_PATR_MASC)):
            shape.append("patr")
            continue
        parses = _MORPH.parse(stripped)
        # A SURNAME READING ONLY WHEN IT BEATS THE GIVEN-NAME ONE. `any(Surn)`
        # was enough for every real surname — they carry no `Name` reading at all
        # — and wrong for the handful of given names that also exist as
        # surnames. «Регина» scores 0.33 both ways, so the arbitrary winner was
        # «surn», and «Иванова Регина Павловна» came out shaped (surn, surn,
        # patr). Both real parts then mapped to the SAME slot of the substitute,
        # the derived token was already taken by the surname, and the given name
        # was minted a second identity: one person, two pseudonyms, in the same
        # dialogue.
        #
        # A tie means morphology has no opinion, and where it has none the
        # position it is being asked about — a part of a person's name — makes
        # the given name the better default.
        best_surn = max((parse.score for parse in parses
                         if "Surn" in parse.tag.grammemes), default=0.0)
        best_name = max((parse.score for parse in parses
                         if "Name" in parse.tag.grammemes), default=0.0)
        if best_surn and best_surn > best_name:
            shape.append("surn")
            continue
        shape.append("name")
        if not best_name:
            guessed.append(len(shape) - 1)
    # DOCUMENT ORDER FOR A WORD MORPHOLOGY DOES NOT KNOW. «миллер валерий»,
    # «ерохин пётр», «мещеряков савва»: the surname is absent from pymorphy's
    # dictionary, falls to the «name» default, and the phrase reads as two given
    # names. The substitute is then minted given-first, the positional pairing
    # hands `last_name` the given name — measured on the live run as «валерий»
    # and «артём» written into a CRM's surname field. When exactly ONE part is
    # such a guess and another part carries a real given-name reading, the
    # guess is the surname. Two unknowns stay as they are: nothing separates
    # «цхведиани нино» from «нино цхведиани», and a wrong guess would be
    # applied to every fake built from it.
    if len(guessed) == 1 and any(role == "name" and index not in guessed
                                 for index, role in enumerate(shape)):
        shape[guessed[0]] = "surn"
    return tuple(shape)


def has_given_name(surface: str) -> bool:
    """Whether any part of this span reads as a given name or a patronymic.

    The question behind it is "is there anything here that can be TRUSTED about
    gender". Surnames cannot: «-ова» scores higher as a man's genitive than as a
    woman's nominative, so a span whose given name carries a typo («Кузнецова
    Ольго») has nothing but that misleading score to go on.

    One definition, two users — `detect_gender` skips its vote when this is
    false, and `to_nominative` only then reads the case in the decided gender.
    Applying that filter unconditionally cost more than it won: where the gender
    is itself a guess (foreign names), filtering the parses by it left a case
    tally with nothing sensible in it and «Ким Викдор» canonicalised to «Ким
    Викдоры». Measured on AgentPII-RU: -14 round trips.
    """
    return any("Name" in parse.tag.grammemes or "Patr" in parse.tag.grammemes
               for part in surface.split() for parse in _name_parses(part))


def detect_gender(surface: str) -> str | None:
    """Gender of a person named by this span, or None if genuinely unknown.

    Evidence in order of strength, and the order is not arbitrary:

    1. THE PATRONYMIC. `-овна`/`-ович` is a closed, regular system with no
       ambiguity — pymorphy3 scores these 1.00 while it scores `Иванова`
       0.48/0.22 between two readings. If a patronymic is present, nothing else
       gets a vote.
    2. Morphology of the remaining parts, but only from name-tagged parses.
    3. The surname's ending, as a last resort.

    Returning None is a real answer: `Дюма Саша` has no reliable gender, and
    guessing produces the disagreement this module exists to prevent.
    """
    parts = surface.split()
    for part in parts:
        gender = _gender_from_patronymic(part)
        if gender is not None:
            return gender

    # A LONE SURNAME THE VAULT KEYS AS FEMININE MUST NOT BE MINTED AS MASCULINE.
    # «Иванова» loses the vote below by more than the 1.5x margin — the genitive
    # prior is that strong — but `canonicalize` has already decided, on the same
    # evidence, that this word names a woman in the nominative. Two answers to
    # one question is how a row stored for her gets a substitute minted for him.
    lone = lone_nominative_gender(surface)
    if lone is not None:
        return lone

    # A GIVEN NAME outvotes a surname, and by a wide margin. Given names encode
    # gender directly and almost without exception; surnames are structurally
    # ambiguous, because `-ова` is both a feminine nominative and a masculine
    # genitive, and pymorphy3's prior favours the genitive — in ordinary text
    # "Соколова" is usually "belonging to Sokolov". Inside a span we have
    # already decided names a person, that prior is exactly backwards.
    #
    # Without this weighting `Любовь Соколова` comes out masculine, on the
    # strength of a genitive reading of the surname over a correct reading of
    # one of the most unambiguously feminine names in Russian.
    votes: dict[str, float] = {"masc": 0.0, "femn": 0.0}
    named = has_given_name(surface)
    for part in parts:
        parses = _name_parses(part)
        if not parses:
            # A word the dictionary does not carry still votes if it is shaped
            # like a given name. Russian female given names end in -а/-я, and
            # the masculine exceptions are a closed list. Without this, a fake
            # first name absent from OpenCorpora — София is one, and it is in
            # our own pool — leaves the surname to decide, and a surname in
            # `-ева` reads as a masculine genitive.
            lowered = part.lower()
            if lowered in _MASC_NAMES_IN_A:
                votes["masc"] += 3.0
            elif lowered.endswith(("а", "я")) and len(lowered) > 3:
                votes["femn"] += 2.0
            continue
        # A WORD THAT CAN BE A SURNAME VOTES AS ONE. OpenCorpora tags the
        # masculine genitive «Мещерякова» as `Name` too, and with the given
        # name's weight that reading beat «Вера» (whose name reading scores
        # 0.3 against the common noun «вера»): the pair came out masculine,
        # the model's rewrite got a masculine ending, and the fake surname
        # reached the tool (Б21). The structural ambiguity the comment above
        # describes belongs to the WORD, whatever label its readings carry.
        surname_shaped = any("Surn" in parse.tag.grammemes for parse in parses)
        for parse in parses:
            if parse.tag.gender not in ("masc", "femn"):
                continue
            weight = 3.0 if "Name" in parse.tag.grammemes and not surname_shaped else 1.0
            votes[parse.tag.gender] += parse.score * weight
    # A SURNAME ALONE MAY NOT WIN THIS VOTE, however decisively it scores. When
    # no part yielded a given name or a patronymic — which is what a typo in the
    # given name produces, and `Кузнецова Ольго` is one — the only voter left is
    # a surname, and `-ова` scores masculine-genitive above feminine-nominative.
    # The whole span was then canonicalised to «Кузнецов Ольго» and the customer's
    # tool called with a man.
    #
    # Skipping to the ending check is not a weaker answer: for a surname the
    # ending IS the reliable signal, and the vote is the unreliable one. Where a
    # given name does exist it still decides, so «Иванова Петра» keeps reading as
    # the man Пётр.
    if named:
        if votes["masc"] > votes["femn"] * 1.5:
            return "masc"
        if votes["femn"] > votes["masc"] * 1.5:
            return "femn"

    for part in parts:
        if part.lower().endswith(_SURN_FEMN):
            return "femn"

    if not named:
        if votes["masc"] > votes["femn"] * 1.5:
            return "masc"
        if votes["femn"] > votes["masc"] * 1.5:
            return "femn"
    # Last resort, and only for a GIVEN name: Russian female given names end in
    # -а/-я, with a closed set of masculine exceptions listed above. This is
    # what rescues names the dictionary does not carry — София among them, which
    # is in our own fake pool.
    for part in parts:
        lowered = part.lower()
        if lowered in _MASC_NAMES_IN_A:
            return "masc"
        if lowered.endswith(("а", "я")) and len(lowered) > 3:
            return "femn"
    return None


def detect_case(surface: str, gender: str | None = None) -> str | None:
    """The grammatical case this span is written in, or None if undetermined.

    Decided by agreement across parts: `Иванову Петру Сергеевичу` is dative in
    all three, which is far stronger evidence than any single word, since
    individual name forms are famously ambiguous (`Иванова` is both masculine
    genitive and feminine nominative).
    """
    tally: dict[str, float] = {}
    for part in surface.split():
        for parse in _name_parses(part):
            # READ IN THE GENDER ALREADY DECIDED. «Кузнецова Ольго» — a woman
            # whose given name carries a typo, so nothing but the surname votes —
            # tallies as genitive, because `-ова` scores higher as the man's
            # genitive than as the woman's nominative. The span was then
            # "restored" to «Кузнецов Ольго» and the tool called with a man.
            #
            # Her gender is not in doubt by the time this runs: `detect_gender`
            # has already answered, on the surname's ending, which for a surname
            # is the reliable signal. Letting the case be decided by readings
            # that contradict that answer is the same defect one step later.
            if gender and parse.tag.gender and parse.tag.gender != gender:
                continue
            # A PERSON IS NEVER PLURAL, so a plural reading is not evidence
            # about their case. «Тагиев», «Ань», «Екатерин» and «Улесь» are all
            # read as GENITIVE PLURAL of an invented singular — «Тагии», «Ани»,
            # «Екатерины», «Улеси» — and each of those votes was enough to carry
            # the span into a conversion it did not need. The vault then keyed
            # the person under a name that does not exist, and that name is what
            # the customer's tool received.
            if parse.tag.number == "plur":
                continue
            # THE VOCATIVE IS NOT HOW A NAME IS WRITTEN DOWN. It survives in
            # Russian only as address — «мам!», «пап!», «Тань!» — and never in a
            # form, an order or a CRM field. «Ань», a Vietnamese given name, has
            # nothing left but a vocative reading once the plural ones are gone,
            # and on that alone it was converted to «Аня»: a different person,
            # sent to the customer's tool, twelve times in one corpus.
            if parse.tag.case == "voct":
                continue
            # AN UNKNOWN WORD'S CASE IS A GUESS, NOT A READING. pymorphy predicts
            # out-of-vocabulary words from their suffix, so it answers rather
            # than declines — and for a misspelt given name («Юлыя», «Марея») it
            # answers genitive singular with a confident-looking score. The
            # answer is about a word that does not exist.
            #
            # The cost of refusing is one of QUALITY, not correctness: a rare
            # name written in two cases gets two vault rows, so the model may
            # meet one person twice. The cost of accepting is a person who does
            # not exist reaching a tool. This repo has ranked those before.
            if not parse.is_known:
                continue
            if parse.tag.case:
                tally[parse.tag.case] = tally.get(parse.tag.case, 0.0) + parse.score
    if not tally:
        return None
    return max(tally, key=lambda case: tally[case])


# Отчества, которые строятся не по правилу. Это опубликованные исключения
# русского словообразования, а не наша подгонка: «Михаил» даёт «Михайлович», а
# не «Михаилович», и так же ведут себя ещё семь имён.
_IRREGULAR_PATRONYMIC: dict[str, str] = {
    "михаил": "михайлович", "гавриил": "гаврилович", "даниил": "данилович",
    "илья": "ильич", "никита": "никитич", "фома": "фомич",
    "кузьма": "кузьмич", "лука": "лукич", "савва": "саввич",
    "пётр": "петрович", "петр": "петрович", "лев": "львович",
    "павел": "павлович",
}


def cases_spelled_as(surface: str, gender: str | None) -> set[str]:
    """Every case this written name could be in — the cases whose form is
    spelled EXACTLY like `surface`. «Виктории Мещеряковой» is the genitive,
    the dative and the prepositional at once; `detect_case` picks one by
    pymorphy3's prior (genitive), which is a guess dressed as a reading. The
    restorer uses this set to prefer the case the customer actually wrote in
    when the model's form does not decide it (Б21: «к Анне Черных» came back
    «к Анны Черных»).
    """
    nominative = to_nominative(surface)
    return {case for case in _CASES
            if inflect_person(nominative, case, gender).casefold() == surface.casefold()}


def full_patronymic(word: str) -> str:
    """Разговорное отчество в полной форме: «Иваныч» -> «Иванович».

    ЗАЧЕМ. Живая речь почти всегда сокращает отчество — «Викторыч», «Алексеич»,
    «Михалыч», — и мы возвращали в поле `patronymic` ровно то, что услышали. В
    CRM это поле полное, и запись не находится. 14 случаев из 61 расхождения по
    именам — больше любой другой причины.

    ПРОВЕРЯЕТСЯ ПО СЛОВАРЮ ИМЁН, А НЕ ПО ФОРМЕ СЛОВА. «-ыч» на конце есть у
    «калач», «сволочь» и у фамилии «Пенкрыч»; отчеством слово делает то, что за
    вычетом окончания остаётся ИМЕНЕМ из арендуемого словаря. Пустая строка —
    «это не отчество», и тогда слово остаётся как было.
    """
    low = word.casefold()
    if low.endswith("ович") or low.endswith("евич") or low.endswith("ич") is False:
        if not low.endswith("ыч"):
            return ""
    stem = low[:-2] if low.endswith(("ыч", "ич")) else ""
    if not stem:
        return ""
    # ИСКЛЮЧЕНИЯ ПЕРВЫМИ, И В ОДНОЙ ПРАВКЕ ОТ ОСНОВЫ. «Михалыч» даёт основу
    # «михал», которая сама лежит в словаре имён — по общему правилу вышло бы
    # «Михалович». Список исключений мал и закрыт, поэтому одна правка до него
    # безопасна: «павлыч» -> «Павлович», «михалыч» -> «Михайлович».
    close = [name for name in _IRREGULAR_PATRONYMIC
             if name == stem or within_one_typo(stem, name)]
    if len(close) == 1:
        return _match_capitalisation(word, _IRREGULAR_PATRONYMIC[close[0]])
    names = ASSETS.get().names
    # ДЛИННЫЙ КАНДИДАТ ПЕРЕД КОРОТКИМ. «алексеич» даёт основу «алексе», и она
    # тоже нашлась в словаре — по ней вышло бы «Алексеович». Настоящее имя здесь
    # «Алексей», и оно длиннее.
    # И КАНДИДАТ ОБЯЗАН БЫТЬ МУЖСКИМ ИМЕНЕМ. Отчество даётся по отцу, а словарь
    # на 28 тысяч имён содержит и «Константина», и «Ивань» — по ним выходило
    # «Константинич» и «Иваневич». Род спрашивается у морфологии, а не
    # угадывается по окончанию: «Никита» и «Лука» мужские и кончаются на «а».
    for candidate in (stem + "й", stem + "ь", stem + "а", stem):
        if candidate not in names.dict_first:
            continue
        # И ИМЕННО В ИМЕНИТЕЛЬНОМ. «Константина» — это родительный от
        # «Константин», мужского рода и с пометой имени: без падежа проверка его
        # пропускала и строила «Константинич».
        if not any(parse.tag.gender == "masc" and parse.tag.case == "nomn"
                   and "Name" in parse.tag.grammemes
                   for parse in _MORPH.parse(candidate)):
            continue
        if candidate.endswith(("й", "ь")):
            built = candidate[:-1] + "евич"
        elif candidate.endswith(("а", "я")):
            built = candidate[:-1] + "ич"
        else:
            built = candidate + "ович"
        return _match_capitalisation(word, built)
    return ""


# WHAT THE WORD BEFORE A NAME SAYS ABOUT ITS CASE. Grammar, not tuning: a
# preposition governs a closed set of cases, and the handful of verbs are the
# ones a dispatcher, a clinic and a CRM agent use on a person. A colon after
# the word («имя: Марина») is a form field, and a form field is nominative.
_GOVERNOR_CASES: dict[str, tuple[str, ...]] = {
    "в": ("accs", "loct"), "во": ("accs", "loct"), "на": ("accs", "loct"),
    "к": ("datv",), "ко": ("datv",), "по": ("datv",),
    "у": ("gent",), "для": ("gent",), "от": ("gent",), "без": ("gent",), "до": ("gent",),
    "из": ("gent",), "после": ("gent",), "около": ("gent",), "возле": ("gent",),
    "кроме": ("gent",), "вместо": ("gent",), "против": ("gent",), "ради": ("gent",),
    "среди": ("gent",), "из-за": ("gent",), "насчёт": ("gent",), "насчет": ("gent",),
    "с": ("ablt", "gent"), "со": ("ablt", "gent"),
    "о": ("loct",), "об": ("loct",), "обо": ("loct",), "при": ("loct",),
    "за": ("accs", "ablt"), "под": ("accs", "ablt"), "перед": ("ablt",), "над": ("ablt",),
    "между": ("ablt",), "про": ("accs",), "через": ("accs",), "сквозь": ("accs",),
    # «на имя X», «от имени X»
    "имя": ("gent", "accs"), "имени": ("gent", "accs"),
    # a subject or an apposition: «это Иванова», «получатель Иванова», «зовут Марина»
    "это": ("nomn",), "зовут": ("nomn", "ablt"), "получатель": ("nomn",), "клиент": ("nomn",),
    "пациент": ("nomn",), "заказчик": ("nomn",), "абонент": ("nomn",), "фамилия": ("nomn",),
    "фио": ("nomn",), "отправитель": ("nomn",), "гражданин": ("nomn",), "гражданка": ("nomn",),
}
_ACCUSATIVE_VERBS = ("запиш", "запис", "оформ", "добав", "завед", "завест", "найд", "найт",
                     "вызов", "вызв", "приглас", "прим", "зарегистр", "внес", "удал", "провер",
                     "сверь", "свер", "ищ", "жд", "ожида", "встреч", "пропуст", "отмет")
_DATIVE_VERBS = ("позвон", "перезвон", "напиш", "напис", "сообщ", "переда", "отправ", "скаж",
                 "ответ", "помог", "верн", "покаж", "перечисл", "отда", "напомн", "объясн")
_GOVERNOR_RE = re.compile(r"([а-яё-]+)([\s:,—–-]*)$")


def governing_cases(text: str, start: int) -> tuple[str, ...]:
    """The cases the word standing before `start` allows the name to be in,
    or () when nothing there governs it."""
    match = _GOVERNOR_RE.search(text[:start].lower())
    if match is None:
        return ()
    word, separator = match.group(1), match.group(2)
    # A STRETCHED GOVERNOR IS THE SAME GOVERNOR. Voice transcripts double a
    # vowel — «наа имяя петра», «этоо новикова» — and the word then matched
    # nothing, so the name was read alone. A doubled letter never makes
    # another word of these.
    word = re.sub(r"([а-яё])\1+", r"\1", word)
    if ":" in separator:
        return ("nomn",)
    if "," in separator or "—" in separator or "–" in separator:
        return ()
    cases = _GOVERNOR_CASES.get(word)
    if cases is not None:
        return cases
    if word.startswith(_ACCUSATIVE_VERBS):
        return ("accs",)
    if word.startswith(_DATIVE_VERBS):
        return ("datv",)
    return ()


def _patronymic_gender_any_case(parts: list[str]) -> str | None:
    """The gender a patronymic names, in WHATEVER case it stands: «Борисовну» is
    the accusative of Борисовна and can only be a woman, and the nominative
    endings alone let it through unread (live v4, derive-036: a woman minted
    as a man)."""
    for part in parts:
        gender = _gender_from_patronymic(part)
        if gender is not None:
            return gender
        genders = {p.tag.gender for p in _name_parses(part)
                   if "Patr" in p.tag.grammemes and p.tag.gender in ("masc", "femn")}
        if len(genders) == 1:
            return next(iter(genders))
    return None


def read_person(surface: str, cases: tuple[str, ...],
                lone_rule: bool = True) -> tuple[str | None, str | None]:
    """ONE reading of the whole name — (gender, case) — chosen so that EVERY
    word supports it, with the word in front of the name breaking a tie.

    Gender and case were decided by two separate votes, and a tie in one
    silently picked the other's loser: «фёдорову юлию» is the accusative of a
    woman AND the dative of a man in both words, the case vote fell on the
    dative by list order and the gender on nothing, so the vault keyed the
    woman as «фёдоров юлий» and minted her substitute in the dative. Read as
    one pair, the two words agree on exactly two readings, and «доставку НА
    фёдорову юлию» leaves one. A patronymic fixes the gender first, in any
    case it stands in; a word with no name reading abstains rather than voting
    for a guess. Returns what `detect_gender` / `detect_case` return when no
    joint reading exists, so nothing that worked before works differently.
    """
    parts = surface.split()
    fixed = _patronymic_gender_any_case(parts)
    per_part: list[dict[tuple[str, str], float]] = []
    for part in parts:
        readings: dict[tuple[str, str], float] = {}
        for parse in _name_parses(part):
            if (not parse.is_known or parse.tag.number == "plur" or parse.tag.case in (None, "voct")
                    or parse.tag.gender not in ("masc", "femn")):
                continue
            weight = 3.0 if "Name" in parse.tag.grammemes else 1.0
            key = (parse.tag.gender, parse.tag.case)
            readings[key] = max(readings.get(key, 0.0), parse.score * weight)
        if readings:
            per_part.append(readings)
    if not per_part:
        gender = fixed or detect_gender(surface)
        return gender, detect_case(surface, None if has_given_name(surface) else gender)
    candidates = set(per_part[0])
    for readings in per_part[1:]:
        candidates &= set(readings)
    if fixed:
        candidates = {c for c in candidates if c[0] == fixed}
    if cases:
        governed = {c for c in candidates if c[1] in cases}
        if governed:
            candidates = governed
    if not candidates:
        gender = fixed or detect_gender(surface)
        return gender, detect_case(surface, None if has_given_name(surface) else gender)
    if lone_rule and len(candidates) > 1 and not cases and len(parts) == 1:
        # The lone-word rule the vault's key already lives by: a single
        # «Иванова» is a woman in the nominative, not a man in the genitive.
        # NOT for `to_nominative` (`lone_rule=False`): that one also reduces
        # the model's inflected FAKE, and a fake surname that stops reducing
        # stops resolving — the model writes «Тарасова», `name_key` misses,
        # the substitute reaches the tool. Every masculine one-word substitute
        # failed its own round trip that way and silently became two words.
        lone = lone_nominative_gender(surface)
        if lone is not None and any(c[0] == lone for c in candidates):
            candidates = {c for c in candidates if c[0] == lone}
    # A TIE IS BROKEN TOWARDS THE NOMINATIVE FOR A REAL VALUE (a lone
    # «Иванова» stays herself) AND AWAY FROM IT FOR A FAKE (`lone_rule=False`):
    # the model's «Тарасова» is the genitive of our «Тарасов», and a reading
    # that keeps it nominative keeps it from resolving.
    # …and for a fake the ENDING says the gender first («лебедеву» is a
    # woman's accusative, not a man's dative), which is the old `detect_gender`
    # signal a surname alone was always read by.
    # …и «одно слово» здесь — это одно ГОЛОСУЮЩЕЕ слово, а не один пробел.
    # «росица пчёлкина»: имя морфологии неизвестно и разборов не даёт, так что
    # решает фамилия одна — ровно тот случай, для которого подсказка по
    # окончанию и написана, — но проверка смотрела на `parts` и видела два
    # слова. Подсказка не применялась, тай-брейк уводил от именительного, и
    # женщина канонизировалась в «Росица Пчёлкин»: в CRM уходил другой
    # человек. Найдено публичным бенчмарком AgentMask-RU.
    voting_parts = len(per_part)
    hinted = detect_gender(surface) if not lone_rule and voting_parts == 1 else None
    best = max(candidates, key=lambda c: (sum(r.get(c, 0.0) for r in per_part),
                                          (c[0] == hinted) if hinted else False,
                                          (c[1] == "nomn") if lone_rule else (c[1] != "nomn"),
                                          -_CASES.index(c[1])))
    return best


def to_nominative_governed(surface: str, cases: tuple[str, ...]) -> str:
    """`to_nominative` with the cases the sentence allows — see `read_person`
    and the rules recorded in `to_nominative`."""
    if not cases:
        return to_nominative(surface)
    gender, case = read_person(surface, cases, lone_rule=False)
    if case in (None, "nomn"):
        return surface
    return " ".join(_part_to_nominative(part, gender, case) for part in surface.split())


def to_nominative(surface: str) -> str:
    """The nominative form — the vault's case-invariant key for a person.

    Exactly parallel to what `canonicalize` already does for phone numbers:
    +7…/8…/no-separators collapse to one key by digit signature, and now
    Иванов/Иванову/Ивановым collapse to one key by lemma. The vault gets one
    row per PERSON instead of one per grammatical form.

    Capitalisation of the input is preserved part by part, because the caller
    may show this to a human.
    """
    # ONE READING FOR GENDER AND CASE, see `read_person`: two separate votes
    # let a tie in one pick the other's loser («фёдорову юлию» — the dative of
    # a man by list order, the woman by every word).
    gender, case = read_person(surface, (), lone_rule=False)
    # The case of the WHOLE span, decided by agreement across its parts, then
    # imposed on each part. Analysing a word alone loses the one fact that
    # disambiguates it: pymorphy3 reads `Марку` as an indeclinable surname and
    # `Яровым` as the surname `Яров`, both perfectly legal in isolation and both
    # wrong inside `Марку Яровому`. Parts of a name agree, so the agreement is
    # evidence — and without using it, canonicalisation is unstable and one
    # person splits into several vault rows again.
    # The gender is handed to the case decision ONLY when no given name was
    # there to decide it — see `has_given_name` (inside `read_person` now).
    # NO EVIDENCE OF AN OBLIQUE CASE MEANS NO CONVERSION. Agreement across the
    # parts is the evidence, and it is already computed; when it says nominative
    # — or says nothing — the safest form is the one the customer wrote.
    #
    # Converting anyway is not free. pymorphy3 reaches the nominative through the
    # LEMMA, and for a surname outside its dictionary it invents a paradigm:
    # «Тагиев» came back «Тагии», «Ань» came back «Ани». Both were already
    # nominative and needed nothing. The vault then keyed the person under a name
    # that does not exist, and that name is what the customer's tool received.
    #
    # Caught by the round-trip axis of AgentPII-RU. Detection scored 100% on
    # every one of these cases — no detection metric could have seen it.
    if case in (None, "nomn"):
        return surface
    # A LONE SYNCRETIC SURNAME CANNOT BE RESOLVED HERE, and must not be.
    # «Иванова» is the feminine nominative of Иванова and the masculine genitive
    # of Иванов; pymorphy3 ranks the masculine reading first, so a woman named
    # here alone is canonicalised to a man's name. Refusing to convert when the
    # nominative reading names another gender was tried, and it is wrong for a
    # deeper reason than it looks: THIS FUNCTION IS ALSO THE KEY. `name_key`
    # reduces a token to its nominative so a token the model inflected still
    # resolves, and a surname that stops reducing stops resolving — the model
    # writes «Тарасова», the lookup misses, and the fake reaches the tool. That
    # is a leak of correctness to save one of quality, which is backwards.
    #
    # The evidence needed lives outside morphology (a cue word, an earlier full
    # name in the vault), so the repair belongs where that evidence is — see
    # `Vault._linked_token`, which matches a mention against the parts of a name
    # already stored, by surface as well as by canonical.
    out: list[str] = []
    for part in surface.split():
        out.append(_part_to_nominative(part, gender, case))
    return " ".join(out)


def lone_nominative_gender(surface: str) -> str | None:
    """The gender this LONE word names, when it is already a nominative of a
    gender its oblique reading does not share. None when there is no such tie.

    «Иванова» reads as the feminine nominative of Иванова and as the masculine
    genitive of Иванов. Both are legal, pymorphy3 scores the masculine one
    higher, and a single word carries no agreement to break the tie — `detect_case`
    decides by agreement ACROSS parts, and for one part that degenerates to the
    score.

    Only a gender FLIP counts, not every ambiguity: «Марии» is the genitive and
    the dative of the same woman, so it still reduces to «Мария» and one person
    keeps one row.

    USED BY THE VAULT'S KEY AND BY `detect_gender`, AND THEY MUST AGREE. If the
    key decides «Иванова» names a woman while the gender vote says man, the row
    is stored for her and the substitute minted for him — the disagreement this
    module exists to prevent, manufactured internally.

    NOT USED BY `to_nominative`. Applying it inside that function also applied it
    to fake names, and a fake surname that stops reducing stops RESOLVING — the
    model writes «Тарасова», the token index misses, and the substitute reaches
    the tool. Measured: every one of the 28 pool surnames failed
    `survives_round_trip` that way.
    """
    parts = surface.split()
    if len(parts) != 1:
        return None
    case = detect_case(surface)
    if case in (None, "nomn"):
        return None
    parses = _name_parses(parts[0])
    nominative = {parse.tag.gender for parse in parses if parse.tag.case == "nomn"}
    oblique = {parse.tag.gender for parse in parses if parse.tag.case == case}
    if len(nominative) != 1 or not oblique or not nominative.isdisjoint(oblique):
        return None
    gender = next(iter(nominative))
    return gender if gender in ("masc", "femn") else None


def _part_to_nominative(part: str, gender: str | None,
                        case: str | None = None) -> str:
    if _is_invariant(part, gender, case):
        return part
    parses = _name_parses(part)
    if not parses:
        return part
    # Prefer the parse that agrees with BOTH facts established for the whole
    # span. Gender disambiguates `Иванова` between "of Ivanov" and "Ivanova";
    # case disambiguates `Марку` between a dative given name and a nominative
    # foreign surname. Case is the stronger of the two here, so it is tried
    # first and gender narrows what remains.
    chosen = _best_parse(parses, gender, case, part)
    # ALREADY NOMINATIVE — return untouched. Inflecting a form to the case it is
    # already in is not a no-op in pymorphy3: it goes through the lemma, and for
    # a surname the lemma is the MASCULINE one. «Иванова Мария Львовна» came back
    # as «Иванов Мария», i.e. the vault's canonical key named a different person
    # than the one the customer wrote, and the tool was called with it.
    #
    # Found by the round-trip axis of AgentPII-RU, which is the only place it
    # could be found: detection was perfect on every one of these.
    if chosen.tag.case == "nomn":
        return part
    # Gender is NOT put into the target here, and a stem-similarity guard was
    # tried and removed. Both looked prudent and both did harm: forcing gender
    # turned «Руслану» into «Руслана» whenever gender detection guessed wrong,
    # and a prefix guard blocks «Петру» -> «Пётр», where the stem legitimately
    # changes е/ё. The two gates that DO work are structural — no conversion
    # without evidence of an oblique case, and no conversion of a part already
    # nominative — and they leave nothing for a heuristic to repair.
    nominative = chosen.inflect({"nomn"})
    if nominative is None:
        return part
    return _match_capitalisation(part, nominative.word)


def inflect_person(nominative: str, case: str, gender: str | None) -> str:
    """Put a nominative full name into `case`, keeping every part agreeing.

    This is the half that removes the model's motive to rewrite: text reads
    `Позвоните Руслану Хвостову`, not `Позвоните Руслан Хвостов`. A part that
    will not inflect is left alone rather than mangled — an untouched surname
    still reads as Russian, an invented paradigm does not.
    """
    if case == "nomn":
        return nominative
    out: list[str] = []
    for part in nominative.split():
        out.append(_part_inflected(part, case, gender))
    return " ".join(out)


def _informative(candidates: list, surface: str):
    """Prefer a reading that says the word is INFLECTED over one that says nothing.

    pymorphy3 carries indeclinable foreign given names, and «Анне» is one — the
    French Anne, whose every case is «анне». It ties at 0.12 with the dative of
    «Анна», so the pick was arbitrary and it landed on the indeclinable one:
    «Гончаровой Анне Дмитриевне» canonicalised to «Гончарова Анне Дмитриевна», a
    form nobody writes, and the surname and patronymic came back nominative
    around a dative middle.

    Inside a span the other parts have already established an oblique case. A
    reading whose lemma equals the surface adds no information to that; one whose
    lemma differs does. Where nothing declines — a genuinely indeclinable name —
    the list is unchanged and the caller keeps what it had.
    """
    lowered = surface.casefold()
    informative = [p for p in candidates if p.normal_form.casefold() != lowered]
    return informative[0] if informative else candidates[0]


def _best_parse(parses: list, gender: str | None, case: str | None,
                surface: str = ""):
    """The reading that agrees with the span, falling back as evidence runs out."""
    if case is not None:
        both = [p for p in parses if p.tag.case == case
                and (gender is None or p.tag.gender in (gender, None))]
        if both:
            return _informative(both, surface) if surface else both[0]
        by_case = [p for p in parses if p.tag.case == case]
        if by_case:
            return by_case[0]
    if gender is not None:
        by_gender = [p for p in parses if p.tag.gender == gender]
        if by_gender:
            return by_gender[0]
    return parses[0]


def _part_inflected(part: str, case: str, gender: str | None) -> str:
    if _is_invariant(part, gender):
        return part
    parses = _name_parses(part)
    if not parses:
        ruled = _paradigm_inflect(part, case, gender or "masc")
        return ruled if ruled is not None else part
    chosen = parses[0]
    if gender is not None:
        for parse in parses:
            if parse.tag.gender == gender:
                chosen = parse
                break
    inflected = chosen.inflect({case})
    if inflected is None:
        ruled = _paradigm_inflect(part, case, gender or "masc")
        return ruled if ruled is not None else part
    return _match_capitalisation(part, inflected.word)


def _match_capitalisation(source: str, produced: str) -> str:
    """pymorphy3 returns lowercase; names are written capitalised.

    Hyphenated surnames need each element capitalised (Салтыков-Щедрин), which
    `str.capitalize()` gets wrong on its own.
    """
    if not source or not produced:
        return produced
    if source.isupper():
        return produced.upper()
    if source[0].isupper():
        return "-".join(piece.capitalize() for piece in produced.split("-"))
    return produced


_WORD = re.compile(r"[А-ЯЁа-яё][А-ЯЁа-яё-]+")


def looks_like_person(surface: str) -> bool:
    """Whether this span could be a personal name at all.

    Used by the detokenizer to decide what is worth normalising, so it is
    deliberately cheap and permissive: a false positive costs one lookup that
    finds nothing, a false negative costs a fake value delivered to a tool.
    """
    parts = surface.split()
    if not (1 <= len(parts) <= 4):
        return False
    return all(_WORD.fullmatch(part) for part in parts)


def given_name_gender(name: str) -> str | None:
    """Gender of a GIVEN name alone, from a `Name`-tagged parse only.

    Separate from `detect_gender` because that one reasons about a whole span
    and would happily read a lone surname; here the caller knows it is holding
    a first name and wants no other evidence considered.
    """
    for parse in _MORPH.parse(name):
        if "Name" in parse.tag.grammemes and parse.tag.gender in ("masc", "femn"):
            return parse.tag.gender
    return None


def feminine_surname(masculine: str) -> str:
    """The feminine nominative of a masculine surname — Лебедев -> Лебедева.

    Derived instead of stored so the leased name pool stays a single list of
    masculine forms: a second list would double what has to be tuned and could
    drift out of correspondence with the first.
    """
    if _is_invariant(masculine, "masc"):
        return masculine
    ruled = _paradigm_inflect(masculine, "nomn", "femn")
    if ruled is not None:
        return ruled
    for parse in _name_parses(masculine):
        feminine = parse.inflect({"femn", "nomn"})
        if feminine is not None:
            return _match_capitalisation(masculine, feminine.word)
    return masculine


def survives_round_trip(name: str, gender: str) -> bool:
    """Whether every case of this name normalises back to the name itself.

    A token is only useful if we can still recognise it after the model has
    inflected it. Some surnames break that: pymorphy3 has no paradigm linking
    `Яровым` back to `Яровой`, so a name built on it would be minted, inflected
    into a sentence, and then fail to resolve — delivering a fake to a tool,
    the exact failure this whole module exists to prevent.

    Checking is cheap and self-healing: it holds whatever the leased pool
    contains today to the standard the code needs, instead of assuming the two
    stay in step.
    """
    for case in _CASES:
        if to_nominative(inflect_person(name, case, gender)) != name:
            return False
    return True
