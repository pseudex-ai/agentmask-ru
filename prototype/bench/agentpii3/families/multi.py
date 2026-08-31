"""Family `crowd` — several people in one dialogue, and whose datum is whose.

THE QUESTION THIS FAMILY ASKS, and no other family can ask it: the gateway must
give ONE person ONE substitute across every way they are named, and TWO people
TWO substitutes even when their surnames are identical. Both halves are claims
and both can be violated, so both are written down. A gateway that stopped
linking anything at all passes every `same` check by accident — it never merges
what must not be merged — which is why `LinkExpectation.different` carries at
least as much of this family's mass as `same` does.

WHY IT IS WORTH ITS OWN 250 CASES. `crowd` is the only place inside ONE
conversation where the `other_person` outcome can occur: the restored value is a
REAL value belonging to a real human who is not the one the conversation was
about. The tool returns 200, the JSON is well formed, the round trip resolves,
and nothing anywhere else in this benchmark can see it. Detection scores it as
found; the answer axis sees a plausible sentence.

THE REGISTER IS THE POINT, AND IT IS THE THING v2 GOT BACKWARDS. Measured over
53 324 human transcriptions of Russian phone and dispatch speech: zero carry a
digit, zero carry sentence punctuation, 0.028% start with a capital, the median
utterance is 5 words. So «Оформите, пожалуйста, заказ на Фёдорова Кирилла
Романовича, адрес доставки: Краснодар, проспект Мира, д. 5, кв. 100» is not a
hard case in this product's traffic — it is a sentence that does not occur in it.
Here `voice_raw` is the base register (55% of the family), `clean` is 3% and
exists only to show we did not break on it.

EVERY CASE IS `recombined`, and that is forced rather than chosen. The schema
permits `template` only for a case whose required types the speech corpora do
not hold, and NAME and LOC are exactly the two types they do hold — so a
template here would be laziness with a field to hide behind. Forms come from
`mined/calls_grammar.json` (name shapes, mined over all 12 950 OpenSTT replies)
and `mined/dispatch_grammar.json` (address value and reply shapes, from 650
hand-labelled SOVA RuDevices utterances). `verbatim` is unreachable for this
family and saying why matters: the hand annotation labels ONE utterance at a
time, and a dialogue with two people in it is not one utterance. What IS
verbatim here is the filler — see below.

THE FILLER IS REAL SPEECH, NOT AN IMITATION OF IT. Nine replies in ten in the
live corpora carry no personal data at all (measured floor: 1.995% of call
replies, 0.939% of dispatch replies do), and a long case whose every line
carries PII inflates recall and precision at once. So the padding in a SPOKEN
`short`, `long` or `deep` case is 57 utterances lifted VERBATIM from SOVA
RuDevices — CC BY 4.0, redistributable — each carrying its `Source` (corpus,
key, line, sha256) so a reader can go and look at the line it came from. Every
one of them was read by hand before it went in: any utterance naming a person or
an address was dropped, because an unlabelled name in filler scores a gateway
that was right as having over-masked. The hand annotation's own «не адрес»
verdict is the first filter, not the last. Twenty-one of the 57 carry a declared
NEGATIVE — «на улице погода хорошая», «первый подъезд от школы», «начальнику
второго отделения прибыть в триста четырнадцатый кабинет» — so the padding is
also the precision half of the measurement rather than dead weight.

A TYPED case gets typed padding, authored here, because neither speech corpus
contains a support thread and real dispatch speech dropped into a messenger
would be the same register error this version exists to fix.

    SOVA Dataset / RuDevices, CC BY 4.0 — see `ATTRIBUTION`. The attribution
    rides with the corpus, not only with this repository, for the same reason the
    ГАР attribution rides in the bundle: the reader gets the dataset, not the
    source tree.

NOT ONE CHARACTER OF OpenSTT IS REPRODUCED. `asr_calls_2_val` is CC BY-NC 4.0 —
measurable, not shippable — so what this module takes from it is SHAPE
(«<фамилия> <имя> <отчество>», «к <фамилия>», «<должность> <фамилия>») and
frequency, never text. `Provenance.licence` still names CC BY-NC 4.0 on those
cases: the honest record of where the form's evidence came from, and a build
that wants to ship only CC BY 4.0 provenance can filter on it rather than guess.

WHAT THE GROUND TRUTH DEMANDS BACK, and the one asymmetry in it:

  * A DECLINED NAME IS DEMANDED IN THE NOMINATIVE. «позвоните Игорю» coming back
    as «Игорю» is a declined name written into a customer's CRM, and the gateway
    canonicalises to the nominative BY DESIGN. So `canonical` is the nominative
    of the parts that were actually said — no patronymic is demanded from a
    message that carried none.
  * NOTHING ELSE IS NORMALISED. A spoken house number comes back spelled out, a
    Latin twin comes back as it was typed, a stray space inside a surname comes
    back where it was. The gateway is not a normaliser and we never sold one;
    `classify_break` already names `renumbered`, `lookalike_repaired` and
    `space_repaired` separately, which is the honest place for those outcomes —
    a corpus that demanded the repaired form would score a product nobody bought.

IDENTITY DENOTES THE HUMAN; THE SCORED CLAIM IS THE LINK. Two mentions of one
person share `PiiItem.identity`, because that is what the word means. What is
SCORED is `LinkExpectation`, and it is graded:

    same       the later mention is a PARTIAL of a fuller one already said in
               this conversation («пётр сергеевич» after «поляков пётр
               сергеевич», «букину» after «букин иван»). The single-candidate
               rule inside one conversation is a documented promise.
    different  two people. Includes the case that breaks naive linking — two
               people sharing a surname — and it is never merged into one number
               with `same`.
    unjudged   a diminutive or a nickname («петя» for «Пётр Сергеевич»). Nobody
               sells nickname co-reference, so demanding the link would score the
               gateway on information the conversation never carried, and
               silently accepting either answer would let a real merge hide
               there. Such a mention never carries a `tool_param`, so a scorer
               can never turn it into a round-trip failure.

TWO PEOPLE WITH THE SAME SURNAME ARE NEVER GIVEN THE SAME SURFACE FORM. «сторож
букин» and «полковник букин» are two humans and one string; demanding two
substitutes for one string is demanding telepathy, and a case that does it
measures the corpus's carelessness. The pairs here differ by at least a given
name or by gender («букин иван» / «букина ольга»), so the distinction is present
in the text the gateway actually sees.

SEEDING. `build(seed, count)` takes an INT and makes its own
`random.Random(f"v3:crowd:{seed}")`, so this family's output does not move when
another family adds a template — a single shared generator would make every
family depend on how many draws the families before it happened to make.
"""

import hashlib
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii3.schema import (  # noqa: E402
    Case, ExpectedCall, FinalAnswer, LinkExpectation, Message, Negative,
    PiiItem, Provenance, Source, ToolSchema, validate,
)

FAMILY: str = "crowd"

# Rides with the corpus, not only with this file. The filler below is quoted
# verbatim and the licence asks for the credit in the place the user receives.
ATTRIBUTION: str = (
    "Filler utterances: SOVA Dataset / RuDevices (bond005/sova_rudevices), "
    "CC BY 4.0. Name and address FORMS: shape statistics mined from OpenSTT "
    "asr_calls_2_val (CC BY-NC 4.0) and SOVA RuDevices (CC BY 4.0); no OpenSTT "
    "text is reproduced."
)

# Shape ids naming an entry in the mined grammar files. The calls file gives its
# shapes real ids; the dispatch file gives patterns, so the pattern IS the id —
# it is the string a reader greps for, which is what `shape` is for.
# `Provenance.shape` holds ONE of these, and for a case carrying both a name and
# an address it holds the ADDRESS: that is the mined VALUE shape, it comes with a
# sampling stratum, and it is the claim a reader can check against a count. The
# name shapes a case draws from — `name.s` 350, `name.n` 255, `name.np` 109,
# `name.snp` 23, `name.ns` 23, `name.sn` 7 — are named here where the case is
# name-led and nowhere else.
_SHAPE_NAME_S = "calls:name.s"
_SHAPE_NAME_SN = "calls:name.sn"
_SHAPE_NAME_SNP = "calls:name.snp"
_SHAPE_NAME_ROLE = "calls:name.role_before"
_SHAPE_NAME_K = "calls:name.cue.к.s"
_SHAPE_ADDR_NAKED = "dispatch.value:<улица> <число прописью>"
_SHAPE_ADDR_ENTRANCE = "dispatch.value:<улица> <число прописью> <порядковое> подъезд"
_SHAPE_ADDR_TYPE = "dispatch.value:улица <улица> <число прописью>"
_SHAPE_ADDR_LETTER = "dispatch.value:<улица> <число прописью> <литера>"
_SHAPE_ADDR_HOUSE = "dispatch.value:улица <улица> дом <число прописью>"
_SHAPE_TWO_POINTS = "dispatch.reply:<АДРЕС> <намерение> <АДРЕС>"

# `selection` says HOW the evidence for a form entered the set, and it is the
# most expensive lesson in this project turned into a field. The first voice set
# admitted an utterance only when «улица» or «дом» was present — the very words
# the engine reads — and reported 100% where the truth was 38.6%.
#
#   census  the calls grammar: name shapes counted over all 12 950 replies.
#   marker  the dispatch gold stratum: a CENSUS of the utterances holding a
#           street-type word or a house marker. Complete, and biased upward by
#           construction, so an address value carrying a marker says `marker`.
#   random  the dispatch number-sample stratum: 250 drawn at random from the 4805
#           remaining, weight 19.22. A bare «<улица> <число>» — 66.9% of all
#           address values — is attested HERE, unbiased, so that is where the
#           naked shape is attributed.
_WEIGHT_NUMBER_SAMPLE: float = 19.22


# --- the pools ------------------------------------------------------------
#
# Authored, not lifted: a name is a fact rather than an expression, and lifting
# names out of a CC BY-NC corpus to put them in a shipped file would be the one
# thing that licence forbids. The SHAPES are mined; the fillers of those shapes
# are these.
#
# THE 28 SURNAMES THE ENGINE MINTS AS SUBSTITUTES ARE EXCLUDED (Лебедев, Жуков,
# Тихонов, Котов, Сорокин, Беляев, Гущин, Ершов, Зимин, Карпов, Лужин,
# Мещеряков, Наумов, Осипов, Панов, Рыбаков, Сазонов, Тарасов, Устинов, Фомин,
# Хвостов, Цветков, Чижов, Шилов, Щукин, Юдин, Яровой, Бирюков). A real value
# equal to a fake one would make `same_value` return True for a leak, and the
# corpus would report the worst outcome as the best. Same reason the streets
# below avoid the tree-and-nature adjectives the vault draws its fake streets
# from — Берёзовой, Вишнёвой, Сиреневой, Полевой, Луговой and the rest.


@dataclass(frozen=True)
class _Person:
    """One human, in the forms the register actually produces.

    `short_patronymic` is not decoration: fifteen distinct contracted forms
    occur in the call corpus (палыч, михалыч, иваныч, николаич, степаныч …) and
    a generator that only writes «Павлович» measures a form the traffic does not
    have. `diminutive` is hand-laid for the same reason — «ирочку», «витёк» and
    «серёжа» are in the speech and in no name dictionary.
    """

    given: str
    surname: str            # THIS person's nominative surname, lower case
    patronymic: str         # masculine nominative, lower case
    short_patronymic: str   # contracted form, "" when the pool has none
    diminutive: str
    female: bool
    invariant: bool         # the surname does not inflect for gender (Миллер)


_MEN: tuple[_Person, ...] = (
    _Person("иван", "букин", "сергеевич", "сергеич", "ваня", False, False),
    _Person("пётр", "поляков", "андреевич", "андреич", "петя", False, False),
    _Person("кирилл", "фёдоров", "романович", "", "кирюха", False, False),
    _Person("валерий", "вольнов", "павлович", "палыч", "валера", False, False),
    _Person("роман", "ерохин", "михайлович", "михалыч", "рома", False, False),
    _Person("олег", "битюков", "иванович", "иваныч", "олежа", False, False),
    _Person("леонид", "кукушкин", "степанович", "степаныч", "лёня", False, False),
    _Person("ашот", "тагиев", "рубенович", "", "ашотик", False, False),
    _Person("шамиль", "валиахметов", "ринатович", "", "шамильчик", False, False),
    _Person("ильдар", "габдрахманов", "маратович", "", "ильдарчик", False, False),
    _Person("дмитрий", "кузнецов", "викторович", "викторыч", "дима", False, False),
    _Person("сергей", "громов", "николаевич", "николаич", "серёжа", False, False),
    _Person("николай", "савельев", "фёдорович", "фёдорыч", "коля", False, False),
    _Person("артём", "копылов", "олегович", "", "тёма", False, False),
    _Person("вадим", "шестаков", "юрьевич", "", "вадик", False, False),
    _Person("руслан", "гаврилов", "маратович", "", "русик", False, False),
    _Person("тимур", "миллер", "рашидович", "", "тимурчик", False, True),
    _Person("глеб", "широков", "антонович", "", "глебка", False, False),
    _Person("егор", "самойлов", "денисович", "", "егорка", False, False),
    _Person("виктор", "лыткин", "аркадьевич", "", "витёк", False, False),
    _Person("павел", "худяков", "борисович", "", "паша", False, False),
    _Person("василий", "симонов", "егорович", "", "вася", False, False),
    _Person("эльдар", "назаров", "тимурович", "", "эльдарчик", False, False),
    _Person("станислав", "заболотный", "игоревич", "", "славик", False, False),
    _Person("аркадий", "дементьев", "львович", "", "аркаша", False, False),
    _Person("матвей", "ушаков", "родионович", "", "матвейка", False, False),
)

_WOMEN: tuple[_Person, ...] = (
    _Person("ирина", "савельева", "сергеевна", "", "ирочка", True, False),
    _Person("ольга", "букина", "андреевна", "", "оля", True, False),
    _Person("тамара", "полякова", "владимировна", "", "тома", True, False),
    _Person("валентина", "громова", "ивановна", "", "валя", True, False),
    _Person("наталья", "ерохина", "павловна", "", "наташа", True, False),
    _Person("галина", "кукушкина", "степановна", "", "галя", True, False),
    _Person("зинаида", "битюкова", "николаевна", "", "зина", True, False),
    _Person("полина", "копылова", "олеговна", "", "поля", True, False),
    _Person("олеся", "широкова", "антоновна", "", "леся", True, False),
    _Person("марина", "лыткина", "аркадьевна", "", "маринка", True, False),
    _Person("алиса", "гаврилова", "маратовна", "", "алиска", True, False),
    _Person("жанна", "назарова", "тимуровна", "", "жанночка", True, False),
    _Person("лариса", "худякова", "борисовна", "", "лара", True, False),
    _Person("нина", "симонова", "егоровна", "", "нинка", True, False),
    _Person("юлия", "шестакова", "юрьевна", "", "юля", True, False),
    _Person("дарья", "самойлова", "денисовна", "", "даша", True, False),
    _Person("елена", "дементьева", "львовна", "", "ленка", True, False),
    _Person("вера", "ушакова", "родионовна", "", "верочка", True, False),
    _Person("тахмина", "миллер", "рашидовна", "", "тахминочка", True, True),
    _Person("светлана", "заболотная", "игоревна", "", "светка", True, False),
)

# Streets, the way the two corpora actually name them: an ADJECTIVE (вольная,
# кирочная, школьная, клубная) or a SURNAME IN THE GENITIVE (лермонтова,
# комиссарова, гагарина) — 14 against 28 in the call corpus, and nothing else.
# Two thirds of address values carry no street-type word at all, so the type
# word is drawn separately and usually absent.
_STREETS_ADJ: tuple[str, ...] = (
    "школьная", "клубная", "нижняя", "союзная", "вольная", "кирочная",
    "мончегорская", "зеленоградская", "подлесная", "базисная", "наличная",
    "депутатская", "химзаводская", "советская", "пушкинская", "загородная",
    "деревообделочная", "буммашевская", "заречная", "северная",
)
_STREETS_GEN: tuple[str, ...] = (
    "ленина", "гагарина", "кирова", "чапаева", "энгельса", "калашникова",
    "грибоедова", "шумайлова", "коммунаров", "машиностроителей", "дзержинского",
    "котовского", "халтурина", "маяковского", "ломоносова", "орджоникидзе",
    "тимирязева", "баранова", "гусева", "лермонтова", "комиссарова",
    "челюскинцев", "берша", "напойма", "тельмана", "чайковского",
)
_STREET_TYPES: tuple[str, ...] = ("улица", "проспект", "переулок", "проезд", "шоссе")
_ENTRANCES: tuple[str, ...] = (
    "первый", "второй", "третий", "четвёртый", "пятый", "шестой", "седьмой",
    "восьмой", "последний", "угловой",
)
_HOUSE_LETTERS: tuple[str, ...] = ("а", "б", "в")


@dataclass(frozen=True)
class _Place:
    """An address value, held as PARTS so the surface can be built per register.

    Held as parts and never as a finished string: the ground truth is derived
    from what the generator BUILT, and a register that rewrites the string after
    the offsets were computed is the defect that cost v1 162 of its 183 sloppy
    failures.
    """

    street: str
    type_word: str      # "" two thirds of the time, which is the measured share
    house: int
    letter: str
    entrance: str       # ordinal, "" when absent; stands BEFORE «подъезд» (82:60)
    flat: int           # 0 = not said
    marker: bool        # the word «дом» is spoken


# --- numerals -------------------------------------------------------------
#
# There is no digit anywhere in either speech corpus: every number is a word.
# The contractions are not noise — 22.9% of every «-десят» form arrives
# contracted — and the truncations are what an ASR does to a numeral it half
# heard (9 of 44 call addresses carry an error INSIDE the value).

_UNITS: tuple[str, ...] = (
    "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять", "десять", "одиннадцать", "двенадцать", "тринадцать",
    "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать",
    "девятнадцать",
)
_TENS: dict[int, str] = {
    2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят", 6: "шестьдесят",
    7: "семьдесят", 8: "восемьдесят", 9: "девяносто",
}
_HUNDREDS: dict[int, str] = {1: "сто", 2: "двести", 3: "триста"}

# Measured contraction table. Every target is in `schema.NUMERAL_WORDS`, so a
# contracted numeral stays visible to `numeral_run` and to the unlabelled-shape
# audit — a contraction that hid a numeral run would be a corpus that cannot
# audit itself.
_CONTRACTIONS: dict[str, tuple[str, ...]] = {
    "пятьдесят": ("песят", "пеесят", "пяесят"),
    "шестьдесят": ("шеесят", "шейсят", "шесят"),
    "восемьдесят": ("восемесят",),
}
_TRUNCATIONS: dict[str, tuple[str, ...]] = {
    "тридцать": ("триц", "тридц"),
    "триста": ("тристо", "трииста"),
    "девяносто": ("девяно",),
    "восемь": ("восем", "восемсь"),
    "четыре": ("четыыре",),
}


def _spell(number: int) -> str:
    """A house number as it is said. Masculine, which is what «дом» takes."""
    if number <= 0 or number > 399:
        raise ValueError(f"house number out of the range the pool draws: {number}")
    words: list[str] = []
    hundreds, rest = divmod(number, 100)
    if hundreds:
        words.append(_HUNDREDS[hundreds])
    if rest >= 20:
        tens, unit = divmod(rest, 10)
        words.append(_TENS[tens])
        if unit:
            words.append(_UNITS[unit])
    elif rest:
        words.append(_UNITS[rest])
    return " ".join(words)


def _asr_noise(text: str, rng: random.Random) -> str:
    """Contract or truncate one numeral word, at the measured rates.

    Applied to the VALUE, because that is where the corpus puts it: «лермонтова
    триц восемь», «воткинское шоссе сто тридцать восемь а». A generator that
    keeps its values clean and dirties only the words around them measures the
    easy half of its own register.
    """
    words = text.split()
    for index, word in enumerate(words):
        if word in _CONTRACTIONS and rng.random() < 0.229:
            words[index] = rng.choice(_CONTRACTIONS[word])
            return " ".join(words)
    if rng.random() < 0.12:
        for index, word in enumerate(words):
            if word in _TRUNCATIONS:
                words[index] = rng.choice(_TRUNCATIONS[word])
                return " ".join(words)
    return " ".join(words)


# --- morphology, by rule and by exception ---------------------------------
#
# Two cases are needed and only two: the dative («передайте букину», «к
# зинаиде») and the accusative («запишите ирину», «оформите на букина»). 15% of
# name mentions in the call corpus are oblique — 124 of 815 — so a corpus that
# only ever writes the nominative measures a form the traffic does not have.
#
# THE RULES BELOW ARE NOT A DECLENSION ENGINE. They are correct for the pool
# above and nothing more, and the two irregular members carry their forms
# explicitly rather than being smuggled through a rule that would then be wrong
# about a name nobody added yet.

_IRREGULAR: dict[str, tuple[str, str]] = {
    "пётр": ("петру", "петра"),
    "витёк": ("витьку", "витька"),
    "лёня": ("лёне", "лёню"),
    "павел": ("павлу", "павла"),
}


def _dative(word: str) -> str:
    if word in _IRREGULAR:
        return _IRREGULAR[word][0]
    if word.endswith("ия"):
        return word[:-1] + "и"
    if word.endswith("ья"):
        return word[:-1] + "е"
    if word.endswith(("а", "я")):
        return word[:-1] + "е"
    if word.endswith("й"):
        return word[:-1] + "ю"
    if word.endswith("ь"):
        return word[:-1] + "ю"
    return word + "у"


def _accusative(word: str) -> str:
    if word in _IRREGULAR:
        return _IRREGULAR[word][1]
    # «-а» takes «-у» and «-я» takes «-ю», and collapsing them is not a typo
    # that reads as one: «олу» is not a word, and a value nobody would say makes
    # the round trip a test of this file's Russian rather than of the gateway.
    if word.endswith("я"):
        return word[:-1] + "ю"
    if word.endswith("а"):
        return word[:-1] + "у"
    if word.endswith("й"):
        return word[:-1] + "я"
    if word.endswith("ь"):
        return word[:-1] + "я"
    return word + "а"


def _surname_base(surname: str) -> str:
    """«кукушкина» and «кукушкин» share a base; «миллер» is its own."""
    if surname.endswith("ая"):
        return surname[:-2]
    if surname.endswith("а"):
        return surname[:-1]
    return surname


def _feminine_surname(surname: str, invariant: bool) -> str:
    """The woman's nominative of a man's surname: «букин» → «букина».

    Needed in ONE place — the same-surname scenario, where a woman is given a
    man's surname so that two humans can share one and still be told apart — and
    nowhere else, because every woman in the pool carries her own form already.
    Applying it to a pool entry was a real defect: «заболотная» does not end in
    «а», so the naive rule produced «заболотнаяа» and every case built on her
    carried a string no Russian would say.

    The feminine form is not a spelling variant of the masculine one, it is the
    string the customer said, and «букин иван» / «букина ольга» is the whole
    point of that scenario: two humans whose surnames differ by one letter and
    who must not collapse into one substitute.
    """
    if invariant:
        return surname
    if surname.endswith(("ый", "ий", "ой")):
        return surname[:-2] + "ая"
    return surname + "а"


def _decline(word: str, case: str) -> str:
    if case == "nom":
        return word
    if case == "dat":
        return _dative(word)
    if case == "acc":
        return _accusative(word)
    raise ValueError(f"unknown case {case!r}; the corpus writes nom, dat, acc")


def _decline_surname(surname: str, female: bool, invariant: bool,
                     case: str) -> str:
    """A surname does NOT decline like a noun, and three ways it differs matter.

    «Кукушкиной» and not «Кукушкине»: a feminine surname in -ова/-ина is an
    ADJECTIVE and takes adjectival endings, which the noun rule gets wrong in
    the dative and right in the accusative — the kind of half-correctness that
    survives a spot check. «Заболотному» and not «Заболотныйу», for the same
    reason on the masculine side. And a woman's non-Slavic surname does not
    decline at all: «Тахмину Миллер», never «Тахмину Миллера».

    This matters here more than anywhere else in the corpus, because the ground
    truth demands the NOMINATIVE back. A surface form no Russian would say makes
    the round trip a test of the corpus's grammar rather than of the gateway.
    """
    if case == "nom":
        return surname
    if invariant:
        if female:
            return surname
        return surname + ("у" if case == "dat" else "а")
    if female:
        if surname.endswith("ая"):
            return surname[:-2] + ("ой" if case == "dat" else "ую")
        return surname[:-1] + ("ой" if case == "dat" else "у")
    if surname.endswith(("ый", "ой", "ий")):
        return surname[:-2] + ("ому" if case == "dat" else "ого")
    return surname + ("у" if case == "dat" else "а")


def _patronymic(person: _Person, contracted: bool) -> str:
    """The pool stores each person's own patronymic, so gender needs no rule.

    The contracted form is drawn only when the pool has one: fifteen distinct
    contractions occur in the call corpus (палыч, михалыч, иваныч, николаич,
    степаныч, викторыч, яныч …) and deriving them would invent forms nobody
    says, which is the same error as deriving a patronymic from a given name.
    """
    if contracted and person.short_patronymic:
        return person.short_patronymic
    return person.patronymic


# --- name surfaces --------------------------------------------------------
#
# Slot order is NOT fixed, and the measured counts say so: surname alone 350,
# given alone 255, given+patronymic 109, surname+given+patronymic 23,
# given+surname 23, patronymic alone 29. A generator that always writes «Фамилия
# Имя Отчество» is writing a form the register produces once in thirty-five
# times.

def _name_parts(person: _Person, shape: str,
                contracted: bool) -> tuple[tuple[str, str], ...]:
    """The words of a mention as (word, role), in the order they are said.

    Tagged with the role rather than positionally: a surname declines by
    different rules from a given name, and the slot order is NOT fixed in this
    register — surname alone 350, given alone 255, given+patronymic 109,
    surname+given+patronymic 23, given+surname 23.
    """
    surname = person.surname
    if shape == "s":
        return ((surname, "surname"),)
    if shape == "n":
        return ((person.given, "given"),)
    if shape == "dim":
        return ((person.diminutive, "given"),)
    if shape == "sn":
        return ((surname, "surname"), (person.given, "given"))
    if shape == "ns":
        return ((person.given, "given"), (surname, "surname"))
    if shape == "np":
        return ((person.given, "given"),
                (_patronymic(person, contracted), "patronymic"))
    if shape == "snp":
        return ((surname, "surname"), (person.given, "given"),
                (_patronymic(person, contracted), "patronymic"))
    raise ValueError(f"unknown name shape {shape!r}")


def _name_surface(person: _Person, shape: str, case: str, contracted: bool,
                  register: str) -> str:
    """The string as it appears in the message. Declined part by part, by role.

    Russian declines every part of a full name, and a corpus that declines only
    the last word writes something no one says.
    """
    words = [
        _decline_surname(word, person.female, person.invariant, case)
        if role == "surname" else _decline(word, case)
        for word, role in _name_parts(person, shape, contracted)
    ]
    if register == "clean":
        return " ".join(word.capitalize() for word in words)
    return " ".join(words)


def _name_canonical(person: _Person, shape: str, contracted: bool) -> str:
    """What a CRM stores: the nominative of the parts that WERE said.

    Not the full identity. A message with no patronymic must not demand one
    back — that scores the gateway on information the conversation never carried,
    and it is the single most expensive ground-truth bug this benchmark has had.
    """
    return " ".join(word.capitalize()
                    for word, _ in _name_parts(person, shape, contracted))


# --- address surfaces -----------------------------------------------------

def _place_surface(place: _Place, register: str, rng: random.Random) -> str:
    """The address value as it is said or typed, built from the parts.

    The ordinal stands BEFORE the marker («первый подъезд»), 82 against 60, and
    the house letter is a separate word after the number, 18 of 169. Both are
    measured shapes, not stylistic choices.

    THE CANONICAL FORM OF AN ADDRESS IS THIS STRING, unchanged. Turning
    «школьная пятьдесят девять» into «Школьная 59» would demand a transcription
    the gateway never promised, and `classify_break` already has a name for a
    value that came back renumbered — it is an outcome to count, not a
    requirement to impose. The one thing the corpus does demand back is the
    nominative of a declined NAME, which the gateway canonicalises by design.
    """
    spoken = register in ("voice_raw",)
    words: list[str] = []
    if place.type_word:
        words.append(place.type_word)
    words.append(place.street.capitalize() if register == "clean" else place.street)
    if place.marker:
        words.append("д." if register == "clean" else "дом")
    words.append(_spell(place.house) if spoken else str(place.house))
    if place.letter:
        words.append(place.letter)
    if place.flat:
        words.append("кв." if register == "clean" else "квартира")
        words.append(_spell(place.flat) if spoken else str(place.flat))
    if place.entrance:
        words.append(place.entrance)
        words.append("подъезд")
    text = " ".join(words)
    if spoken:
        return _asr_noise(text, rng)
    return text


def _place_provenance(place: _Place) -> tuple[str, str, float]:
    """(shape id, selection, weight) for an address value.

    THE STRATUM IS DECIDED BY THE VALUE, not by taste. A bare «<улица> <число>»
    — 66.9% of all address values — is attested in the RANDOM number-sample
    stratum, 250 utterances drawn from the 4805 that no marker selects, so it
    carries that stratum's inverse sampling fraction. A value carrying a street
    type word, a house marker, a letter or an entrance is attested only in the
    marker stratum, which is a census of the utterances holding exactly the cues
    the detector reads and is therefore biased upward by construction.
    Summed without the weight, the marker layer would get nineteen times the
    mass it earned — and it is the layer we are good at.
    """
    if place.entrance:
        return (_SHAPE_ADDR_ENTRANCE, "marker", 1.0)
    if place.marker:
        return (_SHAPE_ADDR_HOUSE, "marker", 1.0)
    if place.type_word:
        return (_SHAPE_ADDR_TYPE, "marker", 1.0)
    if place.letter:
        return (_SHAPE_ADDR_LETTER, "marker", 1.0)
    return (_SHAPE_ADDR_NAKED, "random", _WEIGHT_NUMBER_SAMPLE)


def _street_genitive(street: str) -> str:
    """«клубная» → «клубной», «лермонтова» → «лермонтова».

    A street is named two ways in this register and only two — by an adjective
    or by a surname already in the genitive — so one rule covers the first and
    the second needs none.
    """
    if street.endswith("ая"):
        return street[:-2] + "ой"
    if street.endswith("яя"):
        return street[:-2] + "ей"
    return street


# --- the assembler --------------------------------------------------------
#
# EVERY OFFSET IS COMPUTED DURING ASSEMBLY. Nothing here ever searches a
# finished string: a search finds the FIRST occurrence, and a message naming the
# same surname twice — which this family does on purpose — would then carry a
# span pointing at the wrong one.


@dataclass(frozen=True)
class _Ctx:
    """What every builder needs and none of them may change.

    Carried rather than passed as five arguments because the register decides
    the text, the text decides the offsets, and a builder that received them
    separately could write one line in one register and the next in another.
    """

    case_id: str
    cluster: str
    register: str
    context: str
    conversation_id: str
    rng: random.Random


@dataclass(frozen=True)
class _Slot:
    text: str
    tag: str    # "" for a word nothing claims
    tail: str   # punctuation glued after the value and never inside its span


def _S(text: str, tag: str, tail: str) -> _Slot:
    return _Slot(text=text, tag=tag, tail=tail)


def _plain(text: str) -> _Slot:
    return _Slot(text=text, tag="", tail="")


def _line(slots: tuple[_Slot, ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Join with single spaces; return the text and every tagged span."""
    pieces: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for slot in slots:
        if not slot.text:
            continue
        if slot.tag:
            if slot.tag in spans:
                raise ValueError(f"duplicate slot tag {slot.tag!r} in one line")
            spans[slot.tag] = (cursor, cursor + len(slot.text))
        pieces.append(slot.text + slot.tail)
        cursor += len(slot.text) + len(slot.tail) + 1
    return " ".join(pieces), spans


# `sloppy` is chat plus KEYBOARD errors, and the distinction from `voice_raw`'s
# noise is the whole reason there are two registers: an ASR mishears a numeral
# («триц восемь»), a thumb misses a key («оформте»). A generator that gave both
# registers the same noise would be measuring one register twice.
_SLOPPY_FORMS: tuple[str, ...] = ("drop", "double", "swap")


def _sloppy_word(word: str, rng: random.Random) -> str:
    if len(word) < 5:
        return word
    form = rng.choice(_SLOPPY_FORMS)
    index = rng.randrange(1, len(word) - 1)
    if form == "drop":
        return word[:index] + word[index + 1:]
    if form == "double":
        return word[:index] + word[index] + word[index:]
    return word[:index] + word[index + 1] + word[index] + word[index + 2:]


def _concat(parts: tuple[tuple[str, str], ...]
            ) -> tuple[str, dict[str, tuple[int, int]]]:
    """Join with NO separator; return the text and every tagged span.

    For machine text — a serialised tool result — where the punctuation around a
    value is the format's and not the sentence's. THE SPAN COVERS THE VALUE AND
    NOT ITS QUOTES: a detector reading `{"фио": "Тагиев Ашот"}` marks the name,
    not the JSON string literal, so a span that swallowed the quotes would score
    a perfectly correct mask as `partial` — the coverage rule turned against the
    gateway by the corpus's own carelessness.
    """
    pieces: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for text, tag in parts:
        if tag:
            if tag in spans:
                raise ValueError(f"duplicate tag {tag!r} in one serialised value")
            spans[tag] = (cursor, cursor + len(text))
        pieces.append(text)
        cursor += len(text)
    return "".join(pieces), spans


def _compose(ctx: _Ctx, slots: tuple[_Slot, ...]
             ) -> tuple[str, dict[str, tuple[int, int]]]:
    """Assemble a user line in this case's register.

    The typo lands on the words AROUND the value, never inside it, and it is
    applied BEFORE assembly — so every offset is still computed from the string
    that ends up in the case, never repaired afterwards. A pass over a finished
    message would change its length and silently invalidate every span computed
    before it: the corpus keeps scoring, and scores wrongly.

    A value carrying its own damage is the `broken_name` scenario's business,
    and it says so there rather than happening here by accident.
    """
    if ctx.register != "sloppy":
        return _line(slots)
    noised = tuple(
        slot if slot.tag or ctx.rng.random() > 0.3
        else _Slot(" ".join(_sloppy_word(word, ctx.rng)
                            for word in slot.text.split()),
                   slot.tag, slot.tail)
        for slot in slots)
    return _line(noised)


# --- filler ---------------------------------------------------------------
#
# 57 utterances, verbatim, SOVA RuDevices, CC BY 4.0, each with the line it sits
# on and the digest of its text. Hand-read: every one that named a person, a
# street or a number sequence was dropped, because an unlabelled name in filler
# is scored as a false mask against a gateway that was right — the corpus's
# error, printed as the product's.
#
# The negative spans are DATA, not the result of a search, and `validate` checks
# each one against the text it points into.

@dataclass(frozen=True)
class _Filler:
    """One verbatim RuDevices utterance and everything needed to check it.

    `line` and `sha256` are not bookkeeping. A re-downloaded corpus whose lines
    shifted by one would leave every negative offset here pointing at the wrong
    characters while the benchmark went on printing numbers; the digest is what
    `schema.hydrate` refuses on.

    `negatives` holds (start, end, family, why) — offsets as DATA, computed once
    and checked by `validate` against the text they point into, never found by
    searching the finished string at build time.
    """

    key: str
    line: int
    sha256: str
    text: str
    negatives: tuple[tuple[int, int, str, str], ...]


_FILLER: tuple[_Filler, ...] = (
    _Filler("f44fdb7d1d17", 102,
     "b27b98452ff6630e94aee1310c302db36ddd126322396d7db19e5142dd90e349",
     "на улице погода хорошая",
     ((0, 8, "street_no_name", "«улица» без названия — это погода, а не адрес"),)),
    _Filler("281a1accb977", 893,
     "d71f9d2368b580d7b54bc0657a73b465b0d28eb5e3ace548bf373e74ae297b87",
     "первый подъезд от школы",
     ((0, 14, "entrance_no_street", "подъезд без улицы никого не определяет"),)),
    _Filler("40028f5a8e62", 4258,
     "9cefc9214a6465db1266062dfa6b7c3f7130e51c5a95a48190c29a5e656416d3",
     "ты берёшь одну квартиру",
     ((15, 23, "flat_as_home", "квартира без номера — покупка, а не адрес"),)),
    _Filler("9eb1bd7e6f03", 5052,
     "5d9ef526b1ed054664fa1da162c3ff043e2b4f2fe9f53470bfc8a1188c4717bb",
     "я на одиннадцатом этаже ха-ха",
     ((2, 23, "room_number", "этаж без дома и улицы"),)),
    _Filler("63620e73d295", 14514,
     "25a145c80bf9cd71f39a8f8b6f47ba0ab61648561c49d93b5c8236b6133590ba",
     "у нас нет начальника второго отделения",
     ((21, 38, "room_number",
       "номер отделения — самый частый ложный адрес в этом регистре"),)),
    _Filler("442d8c4e840c", 6183,
     "9248072c9b0be4af12d122ecbbf22a2c830ea90ac39f6166a6942614aea62718",
     "начальнику второго отделения прибыть в триста четырнадцатый кабинет в понедельник",
     ((39, 67, "room_number", "порядковое + кабинет: 528 таких в корпусе звонков"),)),
    _Filler("c326eaf9e368", 8451,
     "98b262d943a75ccb6805fd79f7eb47be01e33d8829fbf4e72e9cc10801194e85",
     "ну короче пятьдесят рублей проезд пятьдесят рублей ты тратишь на маску и перчатки",
     ((27, 33, "fare", "«проезд» здесь плата, а не тип улицы"),)),
    _Filler("1d6baeabab01", 17673,
     "14ddcb636f11bc2c7cba5ab41f4c6cf6b6e418771a959df06a753fb1060eefd4",
     "на центральной улице поэтому",
     ((0, 20, "street_no_name", "улица названа прилагательным без номера дома"),)),
    _Filler("353bf79e7b66", 2067,
     "3355da6a91d48c92f371692f6a44ca7904d106cfb28ba42f864704d7bae4a16c",
     "когда-нибудь и на моей улице будет праздник",
     ((15, 28, "street_no_name", "поговорка, а не адрес"),)),
    _Filler("fc4455cf033e", 6247,
     "4be9737052528b5fb247a681cb8ef30b8fe64cade75d8bc7e5ced6ddff88d13c",
     "ночь по улицам прошла",
     ((5, 14, "street_no_name",
       "улицы во множественном числе — не место жительства"),)),
    _Filler("99da25065f2f", 20289,
     "232c2ba8f638798ba06bbd2a2c6b1724de04d58007f92736df4618c4d670a97b",
     "вышел на улицу пахнет",
     ((6, 14, "street_no_name", "выйти на улицу"),)),
    _Filler("c5c4989bc5e1", 40390,
     "7064e388cfb022ac4c73756f8149595203814dd387a759420d16fbbaa5def975",
     "дождливо на улице однако",
     ((9, 17, "street_no_name", "погода"),)),
    _Filler("9ef8b06372f0", 5565,
     "f8cd3ea4caf8698e418b120cc6a97583ffd806cd826d7005057f86bbda7d1329",
     "на улице солнышко светит тепло",
     ((0, 8, "street_no_name", "погода"),)),
    _Filler("2b2cf61a6292", 3446,
     "c2409b71f595aeb36f69d4745b414e175c8eb7fa456f0d267adf076521ef7de9",
     "хочет прожить как-то дальше оставить квартиру там",
     ((37, 45, "flat_as_home", "квартира как жильё"),)),
    _Filler("4e5cec97859d", 31182,
     "bdc9ce8c3b92f464f751ccd8ce27565a004f7fe927b38536a694188ee00cd8b5",
     "у них в квартире хорошо убрано все чисто всегда",
     ((6, 16, "flat_as_home", "квартира как жильё"),)),
    _Filler("fe32d526fa84", 670,
     "cef08288060146cd160e0789c39ec523d247c24f22ff80e679a1e89ca55ac058",
     "потом домой мыть посуду полы стирать убирать в своей квартире и готовить кушать радость",
     ((45, 61, "flat_as_home", "квартира как жильё"),)),
    _Filler("a0d6953061b7", 4058,
     "50f35b54f4c16f09fa16194ef25195f24afc558766bec489fc163a825b2c2a21",
     "и в двадцать лет у каждой советской семьи будет отдельная квартира",
     ((48, 66, "flat_as_home", "квартира как жильё"),)),
    _Filler("f062d62cd543", 4433,
     "54670773a593624b482b57e8a6ac72c3f43059a44345f2ab7ac0539a33fcf3e1",
     "даже банально в своей квартире которая сейчас снимаю которую я выбыирала",
     ((14, 30, "flat_as_home", "квартира как жильё"),)),
    _Filler("cc3dc9748be0", 18155,
     "e1c050984be93d49e8dd9b645f2d95837c62dfc3fe6559ce7e96bdc8e33ccd3d",
     "иду обратно я же живу на последнем этаже и между моим и последним стоит тётка курит при чём она стоит ближе к моему буквально две ступеньки вверх",
     ((22, 40, "room_number", "этаж без дома и улицы"),)),
    _Filler("084cd724a3b4", 2203,
     "319e2ef5c98fcdf20fc9394ac762b12860e9c55bd0bed7788826f32c701cf8f2",
     "то есть верхний этаж его если делать то скорее всего лёгкие сборной и чисто под ну офисные размещение наверное тоже будет не торговый зал",
     ((8, 20, "room_number", "этаж в рассказе"),)),
    _Filler("4087ff95a6e0", 35875,
     "3a5e4b93ae29cea9191a8e3f771028d5f5f88ea708cf29804265fd74fb3d8ddb",
     "их постепенно проходят весь подъезд спускаясь вниз",
     ((23, 35, "entrance_no_street", "подъезд без улицы"),)),
    _Filler("05b5f84c5ee7", 18307,
     "b16762ce952741a5bb27409be935678bfcc163d1205f236005712f4e43e1f057",
     "а это вот площадка", ()),
    _Filler("b377197a6b8c", 19325,
     "a2930ed1592bf87891328743b6b6f649d183dfb56c7f59cec20d2665472a5f07",
     "я пришла на детскую площадку сижу на лавочке принце и скучаю", ()),
    _Filler("66dae33d8515", 40103,
     "5187752631ee934066ae508627fccb612f6cdc9a977cc7f4ebd79cb233fb478d",
     "площадки лучше чем", ()),
    _Filler("7fcb932d7cc5", 37160,
     "a2266efc361c96b5ed3f2b27d51448747cfedd21e4b4aa48976e4f2a29ba3145",
     "просто открой двери", ()),
    _Filler("eca1299f1945", 9789,
     "afbc74e79a66103b5c35b7391e4ef01ab70d7734268d4e4a7468b082fa5992b4",
     "второй микрорайон и это мой район", ()),
    _Filler("3d9633bb3e80", 8572,
     "ba51e107e37f9577072a7c185701077d3df7404b9fb2c284f0f8190f7ca67154",
     "а корпус пластик или металл отсюда не видно", ()),
    _Filler("5603f86d5770", 28366,
     "ea8a5f94d6f2fc3775e5a0766b88385509081b684cecf2eda091f4b127a11dbd",
     "и искать по три часа слово нужное", ()),
    _Filler("dd0eeb114bf2", 38274,
     "f12d00b7e5f08c491a66fc282b764f6941f43b135e73871d9ba3613c2e3d06eb",
     "ну во-первых мне нужно выходить а во-вторых", ()),
    _Filler("349df99c504f", 15173,
     "d15a74718e0f0bdb969a33530006a9ba7ff95ca0ee78b959f7bfed183046a55b",
     "вот это вот проспект просто", ()),
    _Filler("92db38ae7707", 18110,
     "dfc83ebe141d929687da57ca359c996175d31b2659b4bf2011d2faaba2f568d4",
     "четыре ореха тоже нормально", ()),
    _Filler("3a25a059369c", 1799,
     "aa510c33a1b29c418c20dca53b33fe55abb9d44bf7478373c1a725cc21298682",
     "когда ты обсуждаешь одно и тоже несколько раз", ()),
    _Filler("d17a6d911be5", 34463,
     "25de990d6fd54255d5b9441eeeef1be43d17337ca891e86e30ce48c5aa2f783f",
     "ну так одно другому не мешает поэтому я как бы", ()),
    _Filler("1f9d2e08989b", 16439,
     "c37003e45049fb568555246a86c96ac2a778126fd74ed6a8484810c17a5dc630",
     "подождите подождите подождите стоп стоп стоп стоп", ()),
    _Filler("52e1748bf2a5", 10691,
     "53cfb0a0ce38958547963aa5b133d701b5ff26f8826ebf60181dc6efef5846d3",
     "считаю что я думал что вы один и тот же человек", ()),
    _Filler("6d554d5b2db1", 29230,
     "46c3ad6d7293151e1e97b58f08a0dc1f35f3278185b2cb1e379d9ace43fc8449",
     "полы блестели рамы двери сверкали белизной", ()),
    _Filler("14600bef45a4", 12534,
     "51caa24e6c2b5976d486aadb9b1351e66e30ff9ec77bf5eb26c0f7cfad4b9150",
     "и что каждая сторона рассчитывает на победу", ()),
    _Filler("2e447abca0ed", 26806,
     "22d1041264ece2e4ce972de4441d488bdea8598f1f7140081142be8de78c1b47",
     "в-третьих всё это в целом отнимает время", ()),
    _Filler("c4c78bf77775", 23341,
     "a461fbd4f8aa9d2ba413c137f8e92d54c74b744a8ef8e9f34535d75dc5e1adb1",
     "во время поездки из одного города в другой", ()),
    _Filler("95ebe1342a83", 2665,
     "2c73832179d46710bef400082566c69736d811387b9f3c8e2f59696de4b12007",
     "в доме частном живёшь ээ или в квартире в этом скворечники ха ха вот мне мне чем чем", ()),
    _Filler("99b70d44e1c7", 40718,
     "2d8f0c0d002621e4f806150a1e059b4181550057b15b40c64e330bdb4ad475fc",
     "это может быть метро это может быть самолёт это может быть площадь", ()),
    _Filler("e2c53598c239", 2891,
     "869d10e71f547a18f1fffe5083d2f9bec8a48de7943796212222a40305a8b05a",
     "одного из детей которые занимались на площадке и сказала следующее", ()),
    _Filler("d42dffa6a079", 2116,
     "7684df0e0814edcdb89472147ecaf06d46eebad6ad2b2693bf88953e7db0dfcc",
     "ровно также работает терапия панических атак когда мы идём на улицу мы идём в", ()),
    _Filler("54721ca289ee", 15105,
     "92e42247c5ab9c52bad66c414bcd50edf4e9e9da8442728242fec6389691da85",
     "то есть вот есть какой-то этаж и там какие-то цели а выше я просто вижу что там что-то есть и туда", ()),
    _Filler("070aa438469d", 36506,
     "03f24b45525ca58ad5ac25014f8489e92723a497dd33081b52eaca57d04280de",
     "и вообще ребята я что-то не понял времени уже вечера на улице ещё светло", ()),
    _Filler("1fe3cc554e46", 30840,
     "8ee4c96ea3af383b056a3b3e232999c49303d955989f5d2b7d4d29c3cfc43b1b",
     "народу на улице нормально так люди перестали бояться вируса выдать", ()),
    _Filler("8ced8c158920", 3215,
     "9c3b9a68c39271ab287df933aec61b4da9651543bf022acd65fa33a6a04a4a86",
     "продаются обезличенные идентификаторы рекламных площадок всякие гаиды и дефа", ()),
    _Filler("349f401f5fee", 21690,
     "445b34d11b9490f7fe7b6336bcb75d745be23f3dcf49057630f1804ca73947ee",
     "и возникает некоторая такая обида потому что и ты как-то вот столько сил вкладывал и вот люди столько сил вкладывают", ()),
    _Filler("3c9da5050288", 35564,
     "d5915cc6d9562d4744a1f7bcb3853a40fc724dd05f1cafcc13de180b8b0e2ac5",
     "ээ вот это рисовала на улице ээ вот это вот я рисовала на огрызке это я рисовала недавно", ()),
    _Filler("100038e4711c", 7014,
     "e2e9102ac88139fff6a043a52b28164e283fe252c7631914bcc082e0f90e459e",
     "это как допустим кто-то говорит что одноклассники для него более удобно чем вконтакте хотя объективно говоря", ()),
    _Filler("5a6400586e81", 3301,
     "8681ed796a101659098ea72ce5cd3db3da7fc2d2f4eced94ab0a11836b88bb5f",
     "только времени тратят на уборку а потом жалуется ну что же я ничего не успеваю сделать работа дом дом работа", ()),
    _Filler("855984768305", 5155,
     "2e0a64d5c540c908f958d00adcf7f95cccc2a9959d8daa248d46b780b7ad78a4",
     "они были даже чуть меньше одна была почти такая же другая прямо вообще маленькая на одного человека там еле-еле поместится", ()),
    _Filler("39d57b9e422e", 17623,
     "3e01f3f0ec6f45f41c97a977a254bee1cf643e8eea96ce3c220fe0db098880f3",
     "поэтому я показываю кручу чтобы этот клик снизить то есть стоимость клика в зависимости от спрашиваемости", ()),
    _Filler("6920b30639de", 42,
     "8bf2ab9697dd944eaf6b4e563d351567ac74dab6c3358ffb89053a75423cc1d0",
     "и такое ощущение что мы знакомы вообще просто триста лет это как я разговариваю например с тобой", ()),
    _Filler("33ea70764d0c", 20162,
     "074a8c7ade5b2df77b93d92ba3cb9a4dd1d1de9ce248bd4669c0de3762f4fd97",
     "блин ну правда если бы у нас было четыре смены как я выше аудио записала было бы круто", ()),
    _Filler("30b8272c4b28", 39654,
     "f4da8b92cb45ecfd629069f013745ecf1c5d424f22862097a4cfcb2bc4e11b17",
     "с двенадцати ночи до утра это было бы прикольно", ()),
    _Filler("6b0ebd93a70f", 23537,
     "9c9c84d01cd5e0da655066afb0c40df4846ea108790ac0dae7b5c121985785b2",
     "во всех поисковиках квартир а-ля циан и яндекс", ()),
)

# Chat and sloppy cases get chat filler: real-speech padding in a typed thread
# would be a register error of the same family this whole version exists to fix.
# Authored — a typed support thread is not in either speech corpus — and of
# MIXED LENGTH on purpose: a pool of one-word replies cannot reach the `deep`
# rung's character floor without three hundred messages, and thirty two-word
# replies are exactly what that floor exists to refuse.
_CHAT_FILLER: tuple[str, ...] = (
    "ок",
    "спасибо",
    "а когда примерно",
    "хорошо жду",
    "понял",
    "сколько это будет стоить",
    "можно пораньше",
    "да всё верно",
    "а оплата при получении или картой заранее нужно будет платить",
    "ага",
    "подскажите ещё раз что там по срокам получается и когда примерно ждать",
    "я на связи",
    "давайте так если не успеваете сегодня то перенесите на завтра только "
    "предупредите заранее пожалуйста а то я на работе буду весь день",
    "договорились",
    "у меня ещё вопрос по прошлому заказу там всё нормально прошло или что-то "
    "надо уточнять я просто не помню закрывали мы его или нет",
    "а если никого не будет дома что тогда делают курьеры оставляют у соседей "
    "или везут обратно на склад",
    "понятно спасибо большое буду ждать тогда",
    "ещё уточню пожалуйста можно ли поменять время уже после оформления или "
    "проще отменить и сделать новый",
)

# What the operator says back. PII-free on purpose: an assistant turn that
# repeated a name would need labelling of its own, and the corpus scripts
# history rather than behaviour.
_OPERATOR: tuple[str, ...] = (
    "слушаю вас", "да записываю", "хорошо записал", "минуту сейчас посмотрю",
    "принято", "уточните пожалуйста", "сейчас найду", "понял записываю",
    "секунду", "да да записал",
)

_OPENERS: tuple[str, ...] = (
    "алло", "аллё", "алё", "здравствуйте", "добрый день", "а", "аа", "ну",
    "слушай", "значит", "вот", "", "", "",
)


# --- tools ----------------------------------------------------------------
#
# The tool is where this benchmark stops being a NER corpus: a labelled span
# says «this is a name», and a `tool_param` says «this name is the argument the
# agent passes to `create_delivery.recipient_name`, and the value that arrives
# there must be the real one».
#
# TWO PEOPLE, TWO PARAMETERS, always. A tool with one name field cannot express
# the failure this family exists to catch, because the two substitutes would
# never have a place to swap.

def _tool(name: str, description: str, params: tuple[tuple[str, str], ...],
          required: tuple[str, ...]) -> ToolSchema:
    """`required` is explicit and not «everything»: a call that omits a declared
    required argument is a call the schema said could not happen, and the corpus
    would be scoring the model for obeying it."""
    unknown = [key for key in required if key not in dict(params)]
    if unknown:
        raise ValueError(f"tool {name}: required names unknown parameters {unknown}")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": "string", "description": text}
                    for key, text in params
                },
                "required": list(required),
            },
        },
    }


_T_DELIVERY = _tool(
    "create_delivery", "Оформить доставку: кто заказал, кому и куда везти.",
    (("customer_name", "ФИО заказчика в именительном падеже"),
     ("recipient_name", "ФИО получателя в именительном падеже"),
     ("address", "адрес доставки так, как его назвал клиент"),
     ("order_id", "номер заказа, если он назван")),
    ("customer_name", "recipient_name", "address"))
_T_ORDER = _tool(
    "create_order", "Оформить один заказ на одного получателя.",
    (("recipient_name", "ФИО получателя в именительном падеже"),
     ("address", "адрес доставки так, как его назвал клиент")),
    ("recipient_name", "address"))
_T_RIDE = _tool(
    "book_ride", "Заказать машину: кого забрать, откуда и куда.",
    (("passenger_name", "имя пассажира"),
     ("pickup", "адрес подачи"),
     ("dropoff", "адрес назначения")),
    ("passenger_name", "pickup", "dropoff"))
_T_NOTIFY = _tool(
    "notify_person", "Передать сообщение одному человеку от другого.",
    (("to_name", "кому передать"),
     ("from_name", "от кого"),
     ("subject", "тема, без персональных данных")),
    ("to_name", "from_name"))
_T_UPDATE = _tool(
    "update_client", "Изменить карточку клиента.",
    (("client_name", "ФИО клиента"),
     ("address", "адрес"),
     ("phone", "телефон")),
    ("client_name",))
_T_FIND = _tool(
    "find_client", "Найти клиента по фамилии. Возвращает список совпадений.",
    (("surname", "фамилия для поиска"),), ("surname",))
_T_SCHEDULE = _tool(
    "schedule_visit", "Записать мастера к клиенту.",
    (("client_name", "ФИО клиента"),
     ("master_name", "ФИО мастера"),
     ("address", "адрес визита")),
    ("client_name", "master_name", "address"))


# --- drawing an instance --------------------------------------------------


@dataclass(frozen=True)
class _Instance:
    """Everything a cluster of cases shares: the same people, the same places.

    Drawn ONCE per cluster and rendered into one to three registers, so a
    cluster is what the schema says it is — several cases derived from one
    instance — and an error bar over clusters is not an error bar over the same
    address said three times.
    """

    left: _Person
    right: _Person
    place_left: _Place
    place_right: _Place
    order_number: tuple[int, ...]
    phone_left: str
    phone_right: str
    serial: int


def _draw_place(rng: random.Random) -> _Place:
    # Two thirds of address values carry no street-type word: 113 of 169 in the
    # dispatch corpus, 26 of 44 in the calls corpus. A generator writing «улица
    # Ленина дом 50» measures the easy half of its own register.
    type_word = "" if rng.random() < 0.67 else rng.choice(_STREET_TYPES)
    street = (rng.choice(_STREETS_ADJ) if rng.random() < 0.33
              else rng.choice(_STREETS_GEN))
    return _Place(
        street=street,
        type_word=type_word,
        house=rng.choice((1, 2, 3, 5, 7, 8, 10, 12, 14, 19, 20, 22, 24, 28, 29,
                          30, 31, 33, 38, 39, 40, 45, 50, 53, 56, 58, 59, 66,
                          68, 71, 72, 75, 78, 81, 87, 92, 98, 108, 116, 126,
                          138, 145, 186)),
        letter=rng.choice(_HOUSE_LETTERS) if rng.random() < 0.107 else "",
        entrance=rng.choice(_ENTRANCES) if rng.random() < 0.34 else "",
        flat=(rng.choice((2, 4, 9, 12, 15, 18, 27, 33, 46, 55))
              if rng.random() < 0.2 else 0),
        marker=rng.random() < 0.12,
    )


def _draw_phone(rng: random.Random) -> str:
    return "9" + "".join(str(rng.randrange(10)) for _ in range(9))


def _draw_instance(rng: random.Random, serial: int, same_surname: bool) -> _Instance:
    if same_surname:
        # Two humans, one surname, and the surface forms differ — by a given
        # name, or by the feminine -а that the customer actually said. A pair
        # with IDENTICAL surface would be a demand for telepathy.
        man = rng.choice(_MEN)
        if rng.random() < 0.5:
            other = rng.choice([p for p in _MEN if p.given != man.given])
            right = _Person(other.given, man.surname, other.patronymic,
                            other.short_patronymic, other.diminutive, False,
                            man.invariant)
        else:
            woman = rng.choice(_WOMEN)
            right = _Person(woman.given,
                            _feminine_surname(man.surname, man.invariant),
                            woman.patronymic, woman.short_patronymic,
                            woman.diminutive, True, man.invariant)
        left = man
    else:
        # Compared on the BASE, not on the string. The pool pairs «кукушкин»
        # with «кукушкина» on purpose, and a plain inequality let that pair fall
        # into scenarios whose note claims two unrelated people — a hard case
        # appearing at random in the control group. The collision is worth
        # testing and it belongs where a case says it is being tested.
        left = rng.choice(list(_MEN) + list(_WOMEN))
        base = _surname_base(left.surname)
        right = rng.choice([p for p in list(_MEN) + list(_WOMEN)
                            if _surname_base(p.surname) != base])
    return _Instance(
        left=left,
        right=right,
        place_left=_draw_place(rng),
        place_right=_draw_place(rng),
        order_number=tuple(rng.randrange(10, 99) for _ in range(3)),
        phone_left=_draw_phone(rng),
        phone_right=_draw_phone(rng),
        serial=serial,
    )


# --- negatives that live inside the PII-bearing message --------------------
#
# A `solo` case has no filler to hang a negative on, and a case with no negative
# measures only half of what it should: our own generated sets reported 100%
# precision while «Счёт 1234 от 15.05.2025» was being masked, because they held
# no ordinary business text. In this register the equivalent is a number beside
# «кабинет» or «заказ», and it occurs 528 times in the call corpus.

def _order_negative(instance: _Instance, register: str) -> tuple[str, str, str]:
    """(cue, value, family) — a dictated order number that must stay in the clear.

    The defect this guards against SHIPPED once: every dictated order number was
    being masked, and no literary corpus could see it, because in written text a
    digit is a digit and the numeral run never happens.
    """
    parts = instance.order_number
    if register == "voice_raw":
        value = " ".join(_spell(part) for part in parts)
    elif register == "voice_itn":
        value = " ".join(str(part) for part in parts)
    elif register == "sloppy":
        value = "".join(str(part) for part in parts)
    else:
        value = "-".join(str(part) for part in parts)
    return ("номер заказа", value, "order_number")


def _room_negative(rng: random.Random, register: str) -> tuple[str, str, str]:
    room = rng.choice((14, 108, 214, 314, 402))
    if register == "voice_raw":
        ordinal = {14: "четырнадцатый", 108: "сто восьмой", 214: "двести четырнадцатый",
                   314: "триста четырнадцатый", 402: "четыреста второй"}[room]
        return ("подойти в", f"{ordinal} кабинет", "room_number")
    return ("подойти в", f"кабинет {room}", "room_number")


def _time_negative(rng: random.Random, register: str) -> tuple[str, str, str]:
    """«к девяти ноль ноль» — 66 of these in the call corpus, and none is PII.

    The colon is a register decision, not a formatting one: ITN restores digits
    and not punctuation, so `voice_itn` says «к 9 00» and only a typed register
    writes «9:00».
    """
    hour = rng.choice((8, 9, 10, 11, 14, 17))
    if register == "voice_raw":
        spoken = {8: "восьми", 9: "девяти", 10: "десяти", 11: "одиннадцати",
                  14: "четырнадцати", 17: "семнадцати"}[hour]
        return ("подъехать", f"к {spoken} ноль ноль", "time_of_day")
    if register == "voice_itn":
        return ("подъехать", f"к {hour} 00", "time_of_day")
    return ("подъехать", f"к {hour}:00", "time_of_day")


def _quantity_negative(rng: random.Random, register: str) -> tuple[str, str, str]:
    """«две коробки» — a count beside a noun, and nothing about anybody.

    «коробка» is feminine, so two of them are «две» and not «два». The spelled
    numeral is masculine everywhere else in this file because a house number
    takes «дом», and a generator that reused it here would put a form nobody
    says into the one span the corpus insists must NOT be masked.
    """
    count = rng.choice((2, 3, 5, 12))
    noun = "коробки" if count in (2, 3, 4) else "коробок"
    if register == "voice_raw":
        spoken = "две" if count == 2 else _spell(count)
        return ("всего", f"{spoken} {noun}", "quantity")
    return ("всего", f"{count} {noun}", "quantity")


def _route_negative(rng: random.Random, register: str) -> tuple[str, str, str]:
    """A place that is not an address, and a distance that is not a number.

    «поедем по городу» and «до южной автостанции» are verbatim dispatch tails: a
    city or a landmark used as a place reference identifies nobody, and masking
    one breaks the sentence the driver needs. The distance is the same class as
    «территория завода пять гектаров» — a unit of measure after a number is what
    tells a house number from a quantity, and consumer Russian is full of it.
    """
    if rng.random() < 0.5:
        return ("", rng.choice(("поедем по городу", "до южной автостанции",
                                "поеду на областную улицу")), "city_reference")
    if register == "voice_raw":
        distance = rng.choice(("сто двадцать", "сорок", "восемьдесят"))
    else:
        distance = rng.choice(("120", "40", "80"))
    return ("ехать", f"{distance} километров", "measure")


# --- writing errors, applied to ONE value ---------------------------------
#
# The `broken_name` scenario is the reason this family reaches into the
# character level at all: a surname reaching the model half-masked is a leak
# that scores as recall, and the three ways it happens in real traffic are a
# stray space, a missing one, and a Latin letter with a Cyrillic twin.

_LATIN_TWIN: dict[str, str] = {
    "а": "a", "с": "c", "е": "e", "р": "p", "о": "o", "х": "x", "у": "y",
}


def _split_word(word: str, rng: random.Random) -> str:
    """«фёдоров» → «фёдо ров». An ASR word boundary in the wrong place."""
    if len(word) < 5:
        return word
    cut = rng.randrange(3, len(word) - 1)
    return word[:cut] + " " + word[cut:]


def _latin_twin(word: str, rng: random.Random) -> str:
    """One Cyrillic letter replaced by its Latin look-alike."""
    positions = [i for i, ch in enumerate(word) if ch in _LATIN_TWIN]
    if not positions:
        return word
    index = rng.choice(positions)
    return word[:index] + _LATIN_TWIN[word[index]] + word[index + 1:]


# --- case assembly --------------------------------------------------------


def _identity(ctx: _Ctx, who: str, what: str) -> str:
    # One identity is one substitute, and a person's NAME and their ADDRESS are
    # two identities: they receive two substitutes, and the linking axis
    # compares substitutes. `validate` refuses an identity spanning two types.
    return f"{ctx.case_id}/{who}/{what}"


def _msg(role: str, text: str) -> Message:
    return Message(role=role, content=text, source=None, name="")


def _filler_msg(entry: _Filler) -> Message:
    return Message(
        role="user", content=entry.text,
        source=Source(corpus="speech_rudevices", key=entry.key, line=entry.line,
                      sha256=entry.sha256, licence="CC BY 4.0"),
        name="")


def _typed_filler(register: str, text: str) -> str:
    """Filler in the register the case is written in.

    A `clean` case padded with lower-case chat would still pass the register
    gate — it only asks whether SOME user message carries a capital and SOME
    punctuation — and would still be a document with chat in the middle of it.
    Applied to filler only: filler carries no offsets, so capitalising it moves
    nothing, while the same transform over a value-bearing line would invalidate
    every span computed before it.
    """
    if register != "clean":
        return text
    return text[:1].upper() + text[1:] + "."


def _pad(messages: list[Message], negatives: list[Negative], ctx: _Ctx,
         want_messages: int, want_chars: int) -> None:
    """Grow the transcript with real, PII-free speech until the rung is met.

    Nine replies in ten in the live corpora carry no personal data. A `deep`
    case whose every line carries PII is not a long context, it is a short one
    repeated, and it inflates recall and precision at the same time.
    """
    speech = ctx.register in ("voice_raw", "voice_itn")
    offset = ctx.rng.randrange(len(_FILLER))
    step = 0
    while (len(messages) < want_messages
           or sum(len(m.content) for m in messages) < want_chars):
        if len(messages) > 190:
            raise ValueError(f"{ctx.case_id}: filler cannot reach the rung")
        if speech:
            entry = _FILLER[(offset + step) % len(_FILLER)]
            index = len(messages)
            messages.append(_filler_msg(entry))
            for start, end, family, why in entry.negatives:
                negatives.append(Negative(value=entry.text[start:end],
                                          start=start, end=end, msg=index,
                                          family=family, why=why))
        else:
            messages.append(_msg("user", _typed_filler(
                ctx.register, _CHAT_FILLER[(offset + step) % len(_CHAT_FILLER)])))
        messages.append(_msg("assistant", _typed_filler(
            ctx.register, _OPERATOR[(offset + step) % len(_OPERATOR)])))
        step += 1
    # The corpus never ends on an assistant turn: that turn is what the run
    # produces, and a scripted one there would be the answer under test.
    if messages[-1].role == "assistant":
        messages.pop()


def _rung_targets(context: str) -> tuple[int, int]:
    if context == "solo":
        return (0, 0)
    if context == "short":
        return (5, 0)
    if context == "long":
        return (13, 0)
    if context == "deep":
        return (36, 4_300)
    raise ValueError(f"unknown context rung {context!r}")


def _opener(ctx: _Ctx) -> str:
    if ctx.register in ("voice_raw", "voice_itn"):
        return ctx.rng.choice(_OPENERS)
    if ctx.register == "clean":
        return "Здравствуйте."
    return ctx.rng.choice(("", "", "привет", "здравствуйте"))


def _system_prompt(register: str) -> str:
    if register == "clean":
        return ("Ты оператор службы доставки. Оформляй заказы вызовом "
                "инструментов и не выдумывай данные, которых нет в диалоге.")
    return ("ты оператор службы доставки оформляй заказы вызовом инструментов "
            "и не выдумывай данные которых нет в диалоге")


def _sep(ctx: _Ctx) -> str:
    """The comma a typed register allows and a spoken one never carries."""
    if ctx.register in ("chat", "clean"):
        return ","
    return ""


# --- the seven scenarios --------------------------------------------------
#
# Each is a QUESTION about identity that the others cannot ask. They differ in
# WHICH linking claim they can violate, not in what they are about.


def _scenario_orderer(ctx: _Ctx, instance: _Instance) -> Case:
    """Заказчик и получатель — разные люди, и адрес принадлежит получателю.

    The commonest crowd shape in delivery traffic, and the one where a merge is
    silent: both people are named in one breath, the tool takes both, and a
    gateway that hands the courier the wrong human returns 200.
    """
    rng = ctx.rng
    register = ctx.register
    orderer, recipient = instance.left, instance.right
    place = instance.place_right
    shape_left = rng.choice(("sn", "ns", "s"))
    shape_right = rng.choice(("ns", "sn", "n"))
    left_surface = _name_surface(orderer, shape_left, "acc", False, register)
    right_surface = _name_surface(recipient, shape_right, "dat", False, register)
    place_surface = _place_surface(place, register, rng)
    cue, negative_value, negative_family = _order_negative(instance, register)

    verb = "оформите заказ на" if register != "clean" else "Оформите заказ на"
    slots = (
        _plain(_opener(ctx)), _plain(verb),
        _S(left_surface, "left", _sep(ctx)),
        _plain("а везти"), _S(right_surface, "right", ""),
        _plain("на"), _S(place_surface, "place", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", "." if register == "clean" else ""),
    )
    text, spans = _compose(ctx, slots)
    messages: list[Message] = [_msg("system", _system_prompt(register)),
                              _msg("user", text)]
    user_index = 1
    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans["neg"][0], end=spans["neg"][1],
                 msg=user_index, family=negative_family,
                 why="номер заказа диктуется вслух и персональными "
                     "данными не является")]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    left_item = PiiItem(
        id="left_name", type="NAME", value=left_surface,
        canonical=_name_canonical(orderer, shape_left, False),
        start=spans["left"][0], end=spans["left"][1], msg=user_index,
        identity=_identity(ctx, "left", "name"), duty="required",
        value_source="pool", spoken=False, tool_param="customer_name")
    right_item = PiiItem(
        id="right_name", type="NAME", value=right_surface,
        canonical=_name_canonical(recipient, shape_right, False),
        start=spans["right"][0], end=spans["right"][1], msg=user_index,
        identity=_identity(ctx, "right", "name"), duty="required",
        value_source="pool", spoken=False, tool_param="recipient_name")
    place_item = PiiItem(
        id="right_place", type="LOC", value=place_surface,
        canonical=place_surface,
        start=spans["place"][0], end=spans["place"][1], msg=user_index,
        identity=_identity(ctx, "right", "place"), duty="required",
        value_source="pool", spoken=register == "voice_raw",
        tool_param="address")
    call = ExpectedCall(
        name="create_delivery",
        arguments={"customer_name": left_item.canonical,
                   "recipient_name": right_item.canonical,
                   "address": place_item.canonical,
                   "order_id": negative_value},
        judged_args=("customer_name", "recipient_name", "address"),
        pii_items=("left_name", "right_name", "right_place"),
        after_msg=user_index)
    shape, selection, weight = _place_provenance(place)
    return _case(
        ctx, messages, (_T_DELIVERY, _T_FIND),
        (left_item, right_item, place_item), tuple(negatives),
        (LinkExpectation(left="left_name", right="right_name", kind="different",
                         case="",
                         why="заказчик и получатель — разные люди; одна подмена "
                             "на двоих означает курьера у чужой двери"),),
        (call,),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        shape, "speech_rudevices", selection, weight, "CC BY 4.0",
        "заказчик и получатель названы в одной реплике: две личности, две "
        "подмены, и слияние возвращает 200 с чужим человеком в аргументе")


def _scenario_relative(ctx: _Ctx, instance: _Instance) -> Case:
    """«запишите на меня а везите жене» — два имени и две точки маршрута.

    The measured dispatch shape «<АДРЕС> <намерение> <АДРЕС>»: every tenth reply
    carries two route points, 15 of 154. Here the two points belong to two
    people, so a gateway that links the two addresses — they are both the same
    customer's, after all — sends the car to the wrong one of them.
    """
    rng = ctx.rng
    register = ctx.register
    speaker, other = instance.left, instance.right
    # The kinship word and the pronoun agree with the OTHER person's gender.
    # «везти надо мужу она иван» is a sentence nobody says, and a corpus that
    # writes it is measuring the gateway on text the register never produces.
    kin = (rng.choice(("жене", "маме", "сестре", "дочери", "тёще"))
           if other.female
           else rng.choice(("мужу", "брату", "отцу", "сыну", "тестю")))
    pronoun = "она" if other.female else "он"
    shape_left = rng.choice(("ns", "sn", "snp"))
    left_surface = _name_surface(speaker, shape_left, "nom", rng.random() < 0.4,
                                register)
    right_surface = _name_surface(other, "n", "nom", False, register)
    pickup = _place_surface(instance.place_left, register, rng)
    dropoff = _place_surface(instance.place_right, register, rng)
    cue, negative_value, negative_family = _time_negative(rng, register)
    route_cue, route_value, route_family = _route_negative(rng, register)

    head = "запишите на меня" if register != "clean" else "Запишите на меня"
    slots = (
        _plain(_opener(ctx)), _plain(head),
        _S(left_surface, "left", _sep(ctx)),
        _plain("я на"), _S(pickup, "pickup", ""),
        _plain(f"а везти надо {kin} {pronoun}"),
        _S(right_surface, "right", ""),
        _plain("на"), _S(dropoff, "dropoff", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", _sep(ctx)),
        _plain(route_cue),
        _S(route_value, "route", "." if register == "clean" else ""),
    )
    text, spans = _compose(ctx, slots)
    messages: list[Message] = [_msg("user", text)]
    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans["neg"][0], end=spans["neg"][1],
                 msg=0, family=negative_family,
                 why="время подачи — не персональные данные, а ноли "
                     "проговариваются словом"),
        Negative(value=route_value, start=spans["route"][0],
                 end=spans["route"][1], msg=0, family=route_family,
                 why="город как ориентир и расстояние с единицей измерения: "
                     "ни то, ни другое никого не определяет"),
    ]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    items = (
        PiiItem(id="left_name", type="NAME", value=left_surface,
                canonical=_name_canonical(speaker, shape_left, False),
                start=spans["left"][0], end=spans["left"][1], msg=0,
                identity=_identity(ctx, "left", "name"), duty="required",
                value_source="pool", spoken=False, tool_param=""),
        PiiItem(id="right_name", type="NAME", value=right_surface,
                canonical=_name_canonical(other, "n", False),
                start=spans["right"][0], end=spans["right"][1], msg=0,
                identity=_identity(ctx, "right", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="passenger_name"),
        PiiItem(id="pickup", type="LOC", value=pickup,
                canonical=pickup,
                start=spans["pickup"][0], end=spans["pickup"][1], msg=0,
                identity=_identity(ctx, "left", "place"), duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param="pickup"),
        PiiItem(id="dropoff", type="LOC", value=dropoff,
                canonical=dropoff,
                start=spans["dropoff"][0], end=spans["dropoff"][1], msg=0,
                identity=_identity(ctx, "right", "place"), duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param="dropoff"),
    )
    call = ExpectedCall(
        name="book_ride",
        arguments={"passenger_name": items[1].canonical,
                   "pickup": items[2].canonical,
                   "dropoff": items[3].canonical},
        judged_args=("passenger_name", "pickup", "dropoff"),
        pii_items=("right_name", "pickup", "dropoff"), after_msg=0)
    links = (
        LinkExpectation(left="left_name", right="right_name", kind="different",
                        case="",
                        why="говорящий и родственник — разные люди, "
                            "названные в одной реплике"),
        LinkExpectation(left="pickup", right="dropoff", kind="different", case="",
                        why="две точки маршрута одного заказа принадлежат разным "
                            "людям; слитые в одну подмену они меняются местами молча"),
    )
    return _case(
        ctx, messages, (_T_RIDE, _T_DELIVERY), items, tuple(negatives), links,
        (call,), FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        _SHAPE_TWO_POINTS, "speech_rudevices", "marker", 1.0, "CC BY 4.0",
        "две точки маршрута в одной реплике принадлежат двум людям — измеренная "
        "форма, каждая десятая адресная реплика диспетчерской")


def _scenario_many_forms(ctx: _Ctx, instance: _Instance) -> Case:
    """Один человек, названный четырьмя способами, и второй рядом с ним.

    «поляков пётр сергеевич» → «пётр сергеевич» → «поляков» → «петя». The first
    three are PARTIALS of a fuller mention already made inside this conversation
    and the single-candidate rule is a documented promise, so they are `same`.
    The diminutive is `unjudged`: nobody sells nickname co-reference, and a
    corpus that demanded it would be scoring a feature nobody bought.

    The second person is not decoration. A gateway that answers `same` by never
    separating anybody passes the whole family without it.
    """
    rng = ctx.rng
    register = ctx.register
    hero, other = instance.left, instance.right
    place = instance.place_left
    full = _name_surface(hero, "snp", "nom", rng.random() < 0.4, register)
    partial = _name_surface(hero, "np", "nom", rng.random() < 0.4, register)
    bare = _name_surface(hero, "s", "nom", False, register)
    nick = _name_surface(hero, "dim", "acc", False, register)
    other_shape = rng.choice(("s", "sn"))
    other_surface = _name_surface(other, other_shape, "acc", False, register)
    place_surface = _place_surface(place, register, rng)
    cue, negative_value, negative_family = _room_negative(rng, register)

    messages: list[Message] = [_msg("system", _system_prompt(register))]
    text1, spans1 = _compose(ctx, (
        _plain(_opener(ctx)), _plain("это" if register != "clean" else "Это"),
        _S(full, "full", "." if register == "clean" else ""),
    ))
    messages.append(_msg("user", text1))
    messages.append(_msg("assistant", _OPERATOR[instance.serial % len(_OPERATOR)]))
    text2, spans2 = _compose(ctx, (
        _plain("пришлите мастера" if register != "clean" else "Пришлите мастера"),
        _S(other_surface, "other", ""),
        _plain("на"), _S(place_surface, "place", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", "." if register == "clean" else ""),
    ))
    messages.append(_msg("user", text2))
    user2 = len(messages) - 1
    messages.append(_msg("assistant",
                         _OPERATOR[(instance.serial + 3) % len(_OPERATOR)]))
    text3, spans3 = _compose(ctx, (
        _S(partial, "partial", ""),
        _plain("будет ждать" if register != "clean" else "будет ждать"),
        _plain("а если не дозвонитесь то"), _S(bare, "bare", ""),
        _plain("на месте" + ("." if register == "clean" else "")),
    ))
    messages.append(_msg("user", text3))
    user3 = len(messages) - 1
    text4, spans4 = _compose(ctx, (
        _plain("и" if register != "clean" else "И"),
        _S(nick, "nick", ""),
        _plain("не тревожьте лишний раз" + ("." if register == "clean" else "")),
    ))
    messages.append(_msg("user", text4))
    user4 = len(messages) - 1

    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans2["neg"][0],
                 end=spans2["neg"][1], msg=user2, family=negative_family,
                 why="номер кабинета — самый частый ложный адрес этого регистра")]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    hero_identity = _identity(ctx, "hero", "name")
    items = (
        PiiItem(id="full", type="NAME", value=full,
                canonical=_name_canonical(hero, "snp", False),
                start=spans1["full"][0], end=spans1["full"][1], msg=1,
                identity=hero_identity, duty="required", value_source="pool",
                spoken=False, tool_param="client_name"),
        PiiItem(id="other", type="NAME", value=other_surface,
                canonical=_name_canonical(other, other_shape, False),
                start=spans2["other"][0], end=spans2["other"][1], msg=user2,
                identity=_identity(ctx, "other", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="master_name"),
        PiiItem(id="place", type="LOC", value=place_surface,
                canonical=place_surface,
                start=spans2["place"][0], end=spans2["place"][1], msg=user2,
                identity=_identity(ctx, "hero", "place"), duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param="address"),
        PiiItem(id="partial", type="NAME", value=partial,
                canonical=_name_canonical(hero, "np", False),
                start=spans3["partial"][0], end=spans3["partial"][1], msg=user3,
                identity=hero_identity, duty="required", value_source="pool",
                spoken=False, tool_param=""),
        PiiItem(id="bare", type="NAME", value=bare,
                canonical=_name_canonical(hero, "s", False),
                start=spans3["bare"][0], end=spans3["bare"][1], msg=user3,
                identity=hero_identity, duty="required", value_source="pool",
                spoken=False, tool_param=""),
        PiiItem(id="nick", type="NAME", value=nick,
                canonical=_name_canonical(hero, "dim", False),
                start=spans4["nick"][0], end=spans4["nick"][1], msg=user4,
                identity=hero_identity, duty="required", value_source="pool",
                spoken=False, tool_param=""),
    )
    call = ExpectedCall(
        name="schedule_visit",
        arguments={"client_name": items[0].canonical,
                   "master_name": items[1].canonical,
                   "address": items[2].canonical},
        judged_args=("client_name", "master_name", "address"),
        pii_items=("full", "other", "place"), after_msg=user2)
    links = (
        LinkExpectation(left="full", right="partial", kind="same", case="",
                        why="«имя отчество» — частичное упоминание более полного, "
                            "названного выше в этом же разговоре"),
        LinkExpectation(left="full", right="bare", kind="same", case="",
                        why="голая фамилия разрешается против полного упоминания "
                            "внутри одного разговора — правило единственного кандидата"),
        LinkExpectation(left="full", right="nick", kind="unjudged", case="",
                        why="уменьшительное — не частичное упоминание; связывание "
                            "по прозвищу никто не обещал, и требовать его значило "
                            "бы судить по сведениям, которых в разговоре нет"),
        LinkExpectation(left="full", right="other", kind="different", case="",
                        why="клиент и мастер — разные люди; шлюз, переставший "
                            "связывать вообще, проходит все `same` и валится здесь"),
    )
    return _case(
        ctx, messages, (_T_SCHEDULE, _T_FIND), items, tuple(negatives), links,
        (call,), FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        _SHAPE_NAME_SNP, "speech_calls", "census", 1.0, "CC BY-NC 4.0",
        "один человек назван четырьмя способами, второй стоит рядом: `same` для "
        "частичных, `unjudged` для уменьшительного, `different` для второго")


def _scenario_same_surname(ctx: _Ctx, instance: _Instance) -> Case:
    """Два человека с одной фамилией, каждый со своим адресом.

    The pair that breaks naive linking: «букин иван» and «букина ольга» share
    every character of the surname and are two humans. A gateway keyed on the
    surname alone gives them one substitute, and then the courier, the invoice
    and the CRM row all go to whichever of them the vault saw first.
    """
    rng = ctx.rng
    register = ctx.register
    first, second = instance.left, instance.right
    left_surface = _name_surface(first, "sn", "acc", False, register)
    right_surface = _name_surface(second, "sn", "acc", False, register)
    left_place = _place_surface(instance.place_left, register, rng)
    right_place = _place_surface(instance.place_right, register, rng)
    cue, negative_value, negative_family = _quantity_negative(rng, register)

    head = "записывайте два адреса" if register != "clean" else "Записывайте два адреса"
    slots = (
        _plain(_opener(ctx)), _plain(head),
        _S(left_surface, "left", ""), _plain("на"),
        _S(left_place, "left_place", _sep(ctx)),
        _plain("а"), _S(right_surface, "right", ""), _plain("на"),
        _S(right_place, "right_place", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", "." if register == "clean" else ""),
    )
    text, spans = _compose(ctx, slots)
    messages: list[Message] = [_msg("user", text)]
    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans["neg"][0], end=spans["neg"][1],
                 msg=0, family=negative_family,
                 why="количество коробок — не персональные данные")]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    # TWO CALLS OF ONE TOOL, and the pair is the point. Expected calls are
    # matched UNORDERED — tau2-bench searches the whole trajectory per expected
    # action, BFCL's checker is an unordered multiset and its own
    # `method_invoke_order_checker` is committed commented out — so a gateway
    # that swapped the two people fails on the ARGUMENTS and not on the order,
    # which is the only thing this family is entitled to judge.
    items = (
        PiiItem(id="left_name", type="NAME", value=left_surface,
                canonical=_name_canonical(first, "sn", False),
                start=spans["left"][0], end=spans["left"][1], msg=0,
                identity=_identity(ctx, "left", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="recipient_name"),
        PiiItem(id="left_place", type="LOC", value=left_place,
                canonical=left_place,
                start=spans["left_place"][0], end=spans["left_place"][1], msg=0,
                identity=_identity(ctx, "left", "place"), duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param="address"),
        PiiItem(id="right_name", type="NAME", value=right_surface,
                canonical=_name_canonical(second, "sn", False),
                start=spans["right"][0], end=spans["right"][1], msg=0,
                identity=_identity(ctx, "right", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="recipient_name"),
        PiiItem(id="right_place", type="LOC", value=right_place,
                canonical=right_place,
                start=spans["right_place"][0], end=spans["right_place"][1], msg=0,
                identity=_identity(ctx, "right", "place"), duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param="address"),
    )
    calls = (
        ExpectedCall(name="create_order",
                     arguments={"recipient_name": items[0].canonical,
                                "address": items[1].canonical},
                     judged_args=("recipient_name", "address"),
                     pii_items=("left_name", "left_place"), after_msg=0),
        ExpectedCall(name="create_order",
                     arguments={"recipient_name": items[2].canonical,
                                "address": items[3].canonical},
                     judged_args=("recipient_name", "address"),
                     pii_items=("right_name", "right_place"), after_msg=0),
    )
    links = (
        LinkExpectation(left="left_name", right="right_name", kind="different",
                        case="",
                        why="одна фамилия, два человека: имена в тексте разные, "
                            "поэтому различение возможно и обязано состояться"),
        LinkExpectation(left="left_place", right="right_place", kind="different",
                        case="", why="разные адреса двух однофамильцев"),
    )
    shape, selection, weight = _place_provenance(instance.place_left)
    return _case(
        ctx, messages, (_T_ORDER,), items, tuple(negatives), links, calls,
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        shape, "speech_rudevices", selection, weight, "CC BY 4.0",
        "два однофамильца в одной реплике: слияние по фамилии отправляет заказ "
        "не тому человеку, и инструмент вернёт 200")


def _scenario_bare_surname(ctx: _Ctx, instance: _Instance) -> Case:
    """Двое, названные ТОЛЬКО фамилией и только строчными буквами.

    350 of 815 name mentions in the call corpus are a lone surname, and the bulk
    surname dictionary is capital-only, so this is where a lower-case surname
    leaks whole. The cue word licenses the neighbour, it does not name it:
    «передайте букину» must mask, «фамилия клиента не указана» must not.

    THE CLOSED QUESTION AT THE END IS DECIDED BY THE GATEWAY, NOT BY THE MODEL,
    which is the only reason it is allowed to be here. Two people got two
    substitutes: the model sees two names and answers «нет». If the gateway
    merged them it sees one name twice and answers «да» — confidently, with a
    clean round trip and nothing in any log. That is the observable consequence
    of a `different` claim, and without one the claim is only ever checked
    against tool arguments the model may never produce.
    """
    rng = ctx.rng
    register = ctx.register
    to_person, from_person = instance.left, instance.right
    # The rank agrees with the caller. «звонил дежурный Назарова» is two
    # disagreements in three words, and the measured lexicon has the feminine
    # form in it — дежурный 24, полковник 24, сторож 15, дежурная 4 — so writing
    # the masculine one for a woman is a choice the corpus made, not a gap in it.
    # A rank before a surname is the COMMONEST thing standing in front of a name
    # in this register: 75 occurrences against 20 for «меня зовут».
    role = (rng.choice(("дежурная", "", "")) if from_person.female
            else rng.choice(("дежурный", "полковник", "сторож", "майор",
                             "мастер", "")))
    called = "звонила" if from_person.female else "звонил"
    to_surface = _name_surface(to_person, "s", "dat", False, register)
    from_surface = _name_surface(from_person, "s", "nom", False, register)
    cue, negative_value, negative_family = _room_negative(rng, register)

    # A STREET WITH NO HOUSE NUMBER IDENTIFIES NOBODY — hundreds of buildings
    # stand on it, one step more specific than the city that already identifies
    # nobody under 152-ФЗ ст. 3 п. 1. So it is `optional`: masking it is not an
    # error, missing it is not a leak, and it is counted in its own column. That
    # is not the same thing as a negative, which may not be masked at all.
    bare_street = _street_genitive(instance.place_left.street)
    carries_street = rng.random() < 0.5
    head = "передайте" if register != "clean" else "Передайте"
    slots = (
        _plain(_opener(ctx)), _plain(head), _S(to_surface, "to", ""),
        _plain(f"что {called}" + (" " + role if role else "")),
        _S(from_surface, "from", _sep(ctx)),
        _plain(("она где-то в районе" if from_person.female
                else "он где-то в районе") if carries_street else ""),
        _S(bare_street if carries_street else "", "street", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", "." if register == "clean" else ""),
    )
    text, spans = _compose(ctx, slots)
    messages: list[Message] = [_msg("user", text)]
    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans["neg"][0], end=spans["neg"][1],
                 msg=0, family=negative_family,
                 why="кабинет рядом с двумя фамилиями — приманка "
                     "для адресного детектора")]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    # Asked LAST, after the padding, because the answer axis judges the reply to
    # the final turn. A question buried mid-transcript would be answered by a
    # message the corpus itself scripted over.
    if register == "voice_raw":
        question = "скажи это один и тот же человек или разные"
    elif register == "voice_itn":
        question = "скажи это один и тот же человек или 2 разных"
    elif register == "clean":
        question = "Это один и тот же человек?"
    else:
        question = "это один и тот же человек?"
    messages.append(_msg("user", question))

    items = (
        PiiItem(id="to_name", type="NAME", value=to_surface,
                canonical=_name_canonical(to_person, "s", False),
                start=spans["to"][0], end=spans["to"][1], msg=0,
                identity=_identity(ctx, "to", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="to_name"),
        PiiItem(id="from_name", type="NAME", value=from_surface,
                canonical=_name_canonical(from_person, "s", False),
                start=spans["from"][0], end=spans["from"][1], msg=0,
                identity=_identity(ctx, "from", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="from_name"),
    ) + ((
        PiiItem(id="street", type="LOC", value=bare_street,
                canonical=bare_street.capitalize(),
                start=spans["street"][0], end=spans["street"][1], msg=0,
                identity=_identity(ctx, "from", "street"), duty="optional",
                value_source="pool", spoken=False, tool_param=""),
    ) if carries_street else ())
    call = ExpectedCall(
        name="notify_person",
        arguments={"to_name": items[0].canonical, "from_name": items[1].canonical,
                   "subject": "обратный звонок"},
        judged_args=("to_name", "from_name"),
        pii_items=("to_name", "from_name"), after_msg=0)
    links = (
        LinkExpectation(left="to_name", right="from_name", kind="different",
                        case="",
                        why="две голые фамилии строчными: адресат в дательном и "
                            "звонивший в именительном — разные люди"),
    )
    return _case(
        ctx, messages, (_T_NOTIFY,), items, tuple(negatives), links, (call,),
        # `must_contain` is deliberately empty and the reason is Russian: the
        # reply says «передал Букиной», and demanding the nominative «Букина»
        # inside free text would fail a correct answer on an inflection the
        # corpus itself asked for. The closed answer carries this axis instead,
        # because «да»/«нет» has no surface form to get wrong.
        FinalAnswer(must_contain=(), must_not_contain=(), answer="нет"),
        _SHAPE_NAME_ROLE if role else _SHAPE_NAME_K, "speech_calls", "census",
        1.0, "CC BY-NC 4.0",
        "оба человека названы только фамилией и только строчными — самая частая "
        "форма имени в живой речи и самая слабая для словаря")


def _scenario_broken_name(ctx: _Ctx, instance: _Instance) -> Case:
    """Одна фамилия написана сломанно, вторая — нет.

    Three ways it happens in the traffic and all three are here: a stray space
    inside a surname («фёдо ров»), a missing one («ВалиахметовИльдар»), and a
    Latin letter with a Cyrillic twin. The measurement is COVERAGE, not recall:
    «Фёдо ров Кирилл» detected as «Кирилл» counts as found while half the
    surname reaches the model in the clear.
    """
    rng = ctx.rng
    register = ctx.register
    broken_person, plain_person = instance.left, instance.right
    # THE DAMAGE HAS TO MATCH THE CHANNEL. A word boundary in the wrong place is
    # what an ASR does — «фёдо ров» — and it is the only one of the three that
    # can occur in a spoken register. A missing space and a Latin letter with a
    # Cyrillic twin are keyboard artifacts and cannot reach a transcript, so a
    # voice case carrying one would be measuring a shape the channel cannot
    # produce.
    kind = ("split" if register in ("voice_raw", "voice_itn")
            else rng.choice(("split", "glued", "twin")))
    surname = broken_person.surname
    given = broken_person.given
    if kind == "split":
        broken = _split_word(surname, rng) + " " + given
    elif kind == "glued":
        broken = (surname.capitalize() + given.capitalize()
                  if register in ("chat", "sloppy", "clean")
                  else surname + given)
    else:
        broken = _latin_twin(surname, rng) + " " + given
    plain_surface = _name_surface(plain_person, "sn", "nom", False, register)
    place_surface = _place_surface(instance.place_left, register, rng)
    cue, negative_value, negative_family = _order_negative(instance, register)

    head = "получатель" if register != "clean" else "Получатель"
    slots = (
        _plain(_opener(ctx)), _plain(head), _S(broken, "broken", _sep(ctx)),
        _plain("заказчик"), _S(plain_surface, "plain", _sep(ctx)),
        _plain("адрес"), _S(place_surface, "place", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", "." if register == "clean" else ""),
    )
    text, spans = _compose(ctx, slots)
    messages: list[Message] = [_msg("user", text)]
    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans["neg"][0], end=spans["neg"][1],
                 msg=0, family=negative_family,
                 why="номер заказа рядом со сломанной фамилией — "
                     "то, что маскировалось целиком")]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    # `canonical` is the surface, NOT the repaired form. The gateway
    # canonicalises case, which it sells; it does not promise to repair
    # typography, and `classify_break` names `space_repaired` and
    # `lookalike_repaired` separately so a repair is counted rather than
    # demanded.
    items = (
        PiiItem(id="broken_name", type="NAME", value=broken, canonical=broken,
                start=spans["broken"][0], end=spans["broken"][1], msg=0,
                identity=_identity(ctx, "broken", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="recipient_name"),
        PiiItem(id="plain_name", type="NAME", value=plain_surface,
                canonical=_name_canonical(plain_person, "sn", False),
                start=spans["plain"][0], end=spans["plain"][1], msg=0,
                identity=_identity(ctx, "plain", "name"), duty="required",
                value_source="pool", spoken=False, tool_param="customer_name"),
        PiiItem(id="place", type="LOC", value=place_surface,
                canonical=place_surface,
                start=spans["place"][0], end=spans["place"][1], msg=0,
                identity=_identity(ctx, "broken", "place"), duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param="address"),
    )
    call = ExpectedCall(
        name="create_delivery",
        arguments={"customer_name": items[1].canonical,
                   "recipient_name": items[0].canonical,
                   "address": items[2].canonical,
                   "order_id": negative_value},
        judged_args=("customer_name", "recipient_name", "address"),
        pii_items=("plain_name", "broken_name", "place"), after_msg=0)
    links = (
        LinkExpectation(left="broken_name", right="plain_name", kind="different",
                        case="",
                        why="сломанное написание не повод склеить двух людей: "
                            "половина фамилии, дошедшая до модели, — утечка, "
                            "которую полнота засчитает как находку"),
    )
    return _case(
        ctx, messages, (_T_DELIVERY,), items, tuple(negatives), links, (call,),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        _SHAPE_NAME_SN, "speech_calls", "census", 1.0, "CC BY-NC 4.0",
        f"фамилия сломана способом «{kind}», второй человек написан обычно: "
        f"мера здесь — покрытие, а не полнота")


def _scenario_crm_rows(ctx: _Ctx, instance: _Instance) -> Case:
    """Инструмент возвращает ДВЕ карточки, и вторая — чужая.

    Personal data arriving FROM the customer's system and masked on the way TO
    the model: the third leg of the contract. The forbidden value is a real
    human's row that the search happened to return, and `must_not_contain` is the
    only place in this benchmark — and, over WebArena's 812 official cases, the
    only place anywhere — where a claim about ABSENCE is written down.
    """
    rng = ctx.rng
    register = ctx.register
    wanted, stranger = instance.left, instance.right
    surname_query = _name_surface(wanted, "s", "nom", False, register)
    wanted_full = _name_canonical(wanted, "sn", False)
    stranger_full = _name_canonical(stranger, "sn", False)
    # The CRM row is written by the customer's own system, not by the customer,
    # so it carries capitals and digits whatever the voice did. The register gate
    # judges user messages only, and this one is neither.
    wanted_place = _place_surface(instance.place_left, "clean", rng)
    stranger_place = _place_surface(instance.place_right, "clean", rng)
    wanted_phone = "+7" + instance.phone_left
    stranger_phone = "+7" + instance.phone_right

    head = ("найдите клиента по фамилии" if register != "clean"
            else "Найдите клиента по фамилии")
    cue, negative_value, negative_family = _order_negative(instance, register)
    text0, spans0 = _compose(ctx, (
        _plain(_opener(ctx)), _plain(head),
        _S(surname_query, "query", _sep(ctx)),
        _plain(cue), _S(negative_value, "neg", "." if register == "clean" else ""),
    ))
    messages: list[Message] = [_msg("user", text0)]

    # The tool result is stored SERIALISED, because that is exactly what the
    # gateway sees: `content` in the envelope is a string and masking runs over
    # it as flat text. Storing an object and serialising at score time would let
    # the scorer's separator choices move every offset in the family.
    row_text, row_spans = _concat((
        ('{"клиенты": [{"фио": "', ""), (wanted_full, "n1"),
        ('", "адрес": "', ""), (wanted_place, "a1"),
        ('", "телефон": "', ""), (wanted_phone, "p1"),
        ('"}, {"фио": "', ""), (stranger_full, "n2"),
        ('", "адрес": "', ""), (stranger_place, "a2"),
        ('", "телефон": "', ""), (stranger_phone, "p2"),
        ('"}]}', ""),
    ))
    messages.append(Message(role="tool", content=row_text, source=None,
                            name="find_client"))
    tool_index = len(messages) - 1

    tail = ("оформите доставку первому а второго не трогайте"
            if register != "clean"
            else "Оформите доставку первому, второго не трогайте.")
    messages.append(_msg("user", tail))
    negatives: list[Negative] = [
        Negative(value=negative_value, start=spans0["neg"][0],
                 end=spans0["neg"][1], msg=0, family=negative_family,
                 why="номер заказа, продиктованный рядом с фамилией: маскировать "
                     "его — сломать поиск, которым агент и должен воспользоваться")]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    items = (
        PiiItem(id="query", type="NAME", value=surname_query,
                canonical=_name_canonical(wanted, "s", False),
                start=spans0["query"][0], end=spans0["query"][1], msg=0,
                identity=_identity(ctx, "wanted", "name"), duty="required",
                value_source="pool", spoken=False, tool_param=""),
        PiiItem(id="row1_name", type="NAME", value=wanted_full,
                canonical=wanted_full,
                start=row_spans["n1"][0], end=row_spans["n1"][1], msg=tool_index,
                identity=_identity(ctx, "wanted", "row_name"), duty="required",
                value_source="pool", spoken=False, tool_param="client_name"),
        PiiItem(id="row1_place", type="LOC", value=wanted_place,
                canonical=wanted_place,
                start=row_spans["a1"][0], end=row_spans["a1"][1], msg=tool_index,
                identity=_identity(ctx, "wanted", "row_place"), duty="required",
                value_source="pool", spoken=False, tool_param="address"),
        PiiItem(id="row1_phone", type="PHONE", value=wanted_phone,
                canonical=wanted_phone,
                start=row_spans["p1"][0], end=row_spans["p1"][1], msg=tool_index,
                identity=_identity(ctx, "wanted", "row_phone"), duty="required",
                value_source="template", spoken=False, tool_param="phone"),
        PiiItem(id="row2_name", type="NAME", value=stranger_full,
                canonical=stranger_full,
                start=row_spans["n2"][0], end=row_spans["n2"][1], msg=tool_index,
                identity=_identity(ctx, "stranger", "row_name"), duty="required",
                value_source="pool", spoken=False, tool_param=""),
        PiiItem(id="row2_place", type="LOC", value=stranger_place,
                canonical=stranger_place,
                start=row_spans["a2"][0], end=row_spans["a2"][1], msg=tool_index,
                identity=_identity(ctx, "stranger", "row_place"), duty="required",
                value_source="pool", spoken=False, tool_param=""),
        PiiItem(id="row2_phone", type="PHONE", value=stranger_phone,
                canonical=stranger_phone,
                start=row_spans["p2"][0], end=row_spans["p2"][1], msg=tool_index,
                identity=_identity(ctx, "stranger", "row_phone"),
                duty="required", value_source="template", spoken=False,
                tool_param=""),
    )
    call = ExpectedCall(
        name="update_client",
        arguments={"client_name": items[1].canonical,
                   "address": items[2].canonical,
                   "phone": items[3].canonical},
        judged_args=("client_name", "address", "phone"),
        pii_items=("row1_name", "row1_place", "row1_phone"),
        after_msg=tool_index)
    links = (
        LinkExpectation(left="row1_name", right="row2_name", kind="different",
                        case="",
                        why="две карточки, вернувшиеся на один поиск, — два "
                            "человека; слитые в одну подмену они меняются "
                            "местами внутри JSON, и инструмент вернёт 200"),
        LinkExpectation(left="query", right="row1_name", kind="unjudged", case="",
                        why="фамилия в запросе прозвучала ДО ответа CRM и "
                            "подходит обеим карточкам: правило единственного "
                            "кандидата обязано отказаться, и отказ здесь — "
                            "правильное поведение, а не промах"),
    )
    return _case(
        ctx, messages, (_T_FIND, _T_UPDATE), items, tuple(negatives), links,
        (call,),
        FinalAnswer(must_contain=(),
                    must_not_contain=(items[4].value, items[5].value,
                                      items[6].value),
                    answer=""),
        _SHAPE_NAME_S, "speech_calls", "authored", 1.0, "CC BY-NC 4.0",
        "поиск вернул две карточки: одна нужна, вторая — чужой человек, "
        "разглашение которого нельзя увидеть никакой другой осью")


_SCENARIOS: tuple[tuple[str, object, tuple[str, ...]], ...] = (
    ("orderer", _scenario_orderer, ("solo", "short", "long", "deep")),
    ("relative", _scenario_relative, ("solo", "short", "long")),
    ("many_forms", _scenario_many_forms, ("short", "long", "deep")),
    ("same_surname", _scenario_same_surname, ("solo", "short", "long", "deep")),
    ("bare_surname", _scenario_bare_surname, ("solo", "short", "long")),
    ("broken_name", _scenario_broken_name, ("solo", "short", "long")),
    ("crm_rows", _scenario_crm_rows, ("short", "long", "deep")),
)

# The quotas. `crowd` is 130 of the 1600-case corpus in the plan and this module
# is asked for 250, because names and addresses carry the most mass and this is
# where a linking defect can hide; `build` scales the quotas to whatever `count`
# it is given rather than hard-coding either number.
_QUOTA: dict[str, int] = {
    "orderer": 45, "relative": 40, "many_forms": 45, "same_surname": 35,
    "bare_surname": 30, "broken_name": 30, "crm_rows": 25,
}

# Registers, in the family's measured proportion rather than a uniform one. The
# base register of this product is speech; `clean` is 3.2% and exists to show we
# did not break on it.
_REGISTER_MIX: tuple[tuple[str, int], ...] = (
    ("voice_raw", 138), ("chat", 52), ("voice_itn", 30), ("sloppy", 22),
    ("clean", 8),
)


# Context depth crosses the scenarios rather than being one of them: the case
# the owner described — «ПД названы двадцать реплик назад» — is a `crowd` case
# at `long`, not a family of its own. The mix is the corpus plan's (40/30/20/10)
# renormalised over whatever rungs a scenario can honestly carry; `many_forms`
# needs four mentions and cannot be `solo`, and a tool result needs a turn to
# arrive in.
_CONTEXT_WEIGHTS: dict[str, int] = {"solo": 40, "short": 30, "long": 20, "deep": 10}


def _draw_context(rng: random.Random, allowed: tuple[str, ...]) -> str:
    weights = [_CONTEXT_WEIGHTS[rung] for rung in allowed]
    return rng.choices(allowed, weights=weights, k=1)[0]


def _case(ctx: _Ctx, messages: list[Message], tools: tuple[ToolSchema, ...],
          items: tuple[PiiItem, ...], negatives: tuple[Negative, ...],
          links: tuple[LinkExpectation, ...], calls: tuple[ExpectedCall, ...],
          final: FinalAnswer, shape: str, corpus: str, selection: str,
          weight: float, licence: str, note: str) -> Case:
    """Pack one case. Every field explicit — the schema has no defaults, so that
    «this case declares no negatives» and «the author forgot them» cannot be the
    same JSON."""
    return Case(
        id=ctx.case_id,
        family=FAMILY,
        register=ctx.register,
        context=ctx.context,
        provenance=Provenance(kind="recombined", corpus=corpus, key="",
                              shape=shape, selection=selection, weight=weight,
                              licence=licence),
        cluster=ctx.cluster,
        conversation_id=ctx.conversation_id,
        messages=tuple(messages),
        tools=tools,
        pii=items,
        negatives=negatives,
        links=links,
        calls=calls,
        final=final,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        note=note,
    )


def build(seed: int, count: int) -> list[Case]:
    """The family, deterministic in `seed`.

    `seed` IS AN INT. The generator is made here — `random.Random(f"v3:crowd:
    {seed}")` — so this family's draws do not move when another family adds a
    template; a shared stream would make every family depend on how many draws
    the families before it happened to make, and the corpus would stop being
    comparable to its own previous version for a reason unrelated to the corpus.
    """
    if isinstance(seed, random.Random):
        raise TypeError(
            "build(seed, count) takes an int seed, not a random.Random: this "
            "family derives its own stream so that its cases do not move when "
            "another family changes")
    rng = random.Random(f"v3:{FAMILY}:{seed}")

    total_quota = sum(_QUOTA.values())
    quotas = {name: max(1, round(_QUOTA[name] * count / total_quota))
              for name in _QUOTA}
    # Rounding never gets to change the total: the largest scenario absorbs the
    # difference, so `build(seed, 250)` returns 250 cases and not 249.
    drift = count - sum(quotas.values())
    quotas["orderer"] += drift
    if quotas["orderer"] < 1:
        raise ValueError(f"count {count} is too small to carry seven scenarios")

    # The mix is scaled, never truncated. Cutting the tail of the list would
    # drop `clean` first — it is the smallest and it is last — and a family that
    # silently loses a register at a smaller `count` is a family whose ladder
    # cannot close on register at the rung that needs it most.
    registers: list[str] = []
    for name, share in _REGISTER_MIX:
        registers += [name] * max(1, round(share * count / 250))
    while len(registers) < count:
        registers.append("voice_raw")
    while len(registers) > count:
        registers.remove("voice_raw")
    rng.shuffle(registers)

    cases: list[Case] = []
    position = 0
    serial = 0
    for name, builder, contexts in _SCENARIOS:
        remaining = quotas[name]
        while remaining > 0:
            instance = _draw_instance(rng, serial, name == "same_surname")
            serial += 1
            group = min(remaining, rng.choice((1, 1, 2, 2, 3)))
            cluster = f"crowd:{name}:{instance.serial:04d}"
            for _ in range(group):
                register = registers[position]
                context = _draw_context(rng, contexts)
                ctx = _Ctx(
                    case_id=f"crowd-{name}-{position:03d}",
                    cluster=cluster,
                    register=register,
                    context=context,
                    conversation_id=(f"conv-crowd-{position:03d}"
                                     if position % 5 < 3 else ""),
                    rng=rng,
                )
                cases.append(builder(ctx, instance))  # type: ignore[operator]
                position += 1
                remaining -= 1
                if remaining == 0:
                    break
    return cases


def main() -> int:
    """Build the family and refuse it if anything in it does not hold.

    Run directly — the repo has no test runner and every eval is a script with a
    `main()`:

        python3 bench/agentpii3/families/multi.py
    """
    cases = build(20260830, 250)
    problems: list[str] = []
    for case in cases:
        problems.extend(validate(case))
    registers: dict[str, int] = {}
    contexts: dict[str, int] = {}
    links: dict[str, int] = {}
    types: dict[str, int] = {}
    negatives: dict[str, int] = {}
    values: dict[str, set[str]] = {}
    for case in cases:
        registers[case.register] = registers.get(case.register, 0) + 1
        contexts[case.context] = contexts.get(case.context, 0) + 1
        for link in case.links:
            links[link.kind] = links.get(link.kind, 0) + 1
        for item in case.pii:
            types[item.type] = types.get(item.type, 0) + 1
            if item.duty == "required":
                values.setdefault(item.type, set()).add(item.canonical.casefold())
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print(f"cases            {len(cases)}")
    print(f"clusters         {len({case.cluster for case in cases})}")
    print(f"registers        {dict(sorted(registers.items()))}")
    print(f"contexts         {dict(sorted(contexts.items()))}")
    print(f"links            {dict(sorted(links.items()))}")
    print(f"items by type    {dict(sorted(types.items()))}")
    print("distinct values  "
          f"{ {kind: len(seen) for kind, seen in sorted(values.items())} }")
    print(f"negatives        {dict(sorted(negatives.items()))}")
    print(f"characters       {sum(len(m.content) for c in cases for m in c.messages)}")
    digest = hashlib.sha256(
        "".join(case.id for case in cases).encode("utf-8")).hexdigest()
    print(f"id digest        {digest[:12]}")
    if problems:
        print(f"\nINVALID — {len(problems)} problems")
        for problem in problems[:40]:
            print(f"  {problem}")
        return 1
    print("\nevery case valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
