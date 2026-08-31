"""AgentPII-RU v3 — the CONTEXT-DEPTH module. Four rungs, one question.

`schema.py` refuses `length` as a family and it is right to: depth measured on
its own measures only itself. Depth has to CROSS the other families, so this
module writes cases in `transfer`, `compare`, `indirect`, `crowd` and `result`
and varies ONE thing across them — how far back the personal datum was said.

THE OWNER'S FOUR RUNGS, and the message counts are `schema.CONTEXT_RUNGS`:

    solo   1-2 messages     без контекста
    short  3-8              малый
    long   9-30             средний
    deep   31-200, ≥4000 chars   большой

Banded by MESSAGES and not by characters, and the character floor rides only on
`deep`. Both halves are forced by the register: the median utterance in the two
speech corpora is 35-38 characters (`mined/reference_distribution.json`), so a
character band would put four different things in one rung across five
registers, and thirty two-word replies would otherwise pass for a long context.
The floor is 4000 because that is the smallest transcript in which the owner's
shape — «названо в первых репликах, двадцать-сорок реплик разговора, косвенная
ссылка в конце» — actually fits: forty filler replies at the measured mean of 45
characters is 1800, and the reply the agent makes to each of them roughly
doubles it.

WHY THE MATCHED QUARTET IS THE CENTRAL DESIGN. 160 of the 250 cases here are 40
QUARTETS: the same person, the same address, the same sentence shape, the same
register, at all four depths, under ONE cluster. A difference between two rungs
of a quartet cannot be a difference of value, form or register, because those
are held fixed — it is depth. Free-standing cases at one depth cannot say that,
and v2's depth story was exactly that kind of uncontrolled comparison.

`solo` is the floor and it is deliberately NOT identical to the others: with
nothing before it there is no referring expression to make, so the call is made
from the single utterance. `short` is the matched near-control — it carries the
same closing reference as `long` and `deep` — and the three of them differ in
distance only.

WHAT DEPTH ACTUALLY LOADS, which is why this module exists at all. A long
transcript is not interesting for being long. It is the only place where three
mechanisms are under load at once:

  * **the mask cache**, which is per-worker, keyed on RAW content and carries
    the conversation in `content_key`. A growing transcript re-sends every
    earlier message on every turn, so at `deep` one case is dozens of cache
    lookups over the same strings.
  * **the conversation scope**, `Vault.for_conversation`. A partial mention
    («ленина», no house) resolving against a fuller one said forty replies
    earlier is the single-candidate rule at its longest reach.
  * **the already-minted token**: the person named in message 1 and named again
    in message 80 must reach the model as ONE substitute. Every quartet case
    below `solo`, every `compare` case and every `echo` case carries that claim
    as a `LinkExpectation.same`; the `crowd` cases and the second row of a
    `result` payload carry the opposite claim — two people, two substitutes —
    as `different`, because a corpus that only ever asks whether the gateway
    links never asks whether it refuses to. `indirect` carries neither, and
    deliberately: there the value is never said twice, so a link expectation
    would be a claim about a mention that does not exist.

FILLER IS REAL SPEECH, AND IT IS ALSO A MEASUREMENT. The owner's rule: «наполнитель
бери из настоящей речи, а не из литературы: это разговор, а не эссе». Every
filler utterance here is an unchanged SOVA RuDevices reply (CC BY 4.0, so the
text may ship) carried by `Source` and verified by sha256 at hydrate time.

Filler that quietly contains something PII-shaped is not neutral: the gateway
masks it, the scorer counts a false mask, and the corpus was wrong — so the
filler pool is built by REJECTING every utterance any independent probe fires
on, and then read by hand. The rejection is deliberately far too strict (a
frequency floor throws away every rare word, which is where a proper noun
hides). Over-rejecting filler costs nothing and biases nothing: filler carries
no gold, so the selection-bias rule that governs MEASURED material
(`Provenance.selection`, and the first voice set that reported 100% where the
truth was 38.6%) does not reach it. The direction is what makes it safe — a
strict filter can only remove ballast, never decide what gets labelled.

Nine replies in ten in the live corpora carry no personal data at all (1.995%
of calls, 0.939% of RuDevices). A `deep` case here is two or three PII-bearing
messages among eighty, which is that density and not a corpus where every line
carries a name.

WHAT THIS MODULE DOES NOT DO. It writes no `spoken_id`, `wordnum`, `repair`,
`negative` or `scope` cases — those families belong to their own modules and
folding them in here would average two questions into one number. Its types are
NAME, LOC, PHONE and DOB; EMAIL and the checksum identifiers are template types
whose sentences have to come from a register they do not occur in, which is a
different module's problem and not a depth question.
"""

import hashlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii3.schema import (  # noqa: E402
    Case,
    ExpectedCall,
    FinalAnswer,
    InvalidCase,
    LinkExpectation,
    Message,
    Negative,
    PiiItem,
    Provenance,
    Source,
    ToolSchema,
    unsafe_filler,
    unsafe_outside,
    require_valid,
    validate,
)

_CACHE = Path.home() / ".cache" / "pseudex-bench"
_RUDEVICES = _CACHE / "speech_rudevices.jsonl"
_LABELS = _CACHE / "rudevices_addresses.json"
_LICENCE = "CC BY 4.0"
_CORPUS = "speech_rudevices"

# SOVA Dataset / RuDevices, распространяется по CC BY 4.0. The attribution rides
# with the corpus and not only in a document, for the same reason the ГАР line
# rides in the bundle: the consumer gets the set, never the repository.
ATTRIBUTION = "SOVA Dataset / RuDevices, CC BY 4.0"


# --- corpus access ---------------------------------------------------------

@dataclass(frozen=True)
class _Utterance:
    key: str
    line: int
    text: str
    sha256: str


def _load_utterances() -> dict[str, _Utterance]:
    """Every distinct RuDevices reply, keyed by blake2b-6 of its own text.

    No fallback if the file is missing. A benchmark that quietly builds a
    smaller corpus because a source was absent reports a number for a set
    nobody can name, which is worse than not building.
    """
    if not _RUDEVICES.exists():
        raise FileNotFoundError(
            f"{_RUDEVICES} is missing. The speech corpora are not in the "
            f"repository; fetch RuDevices into ~/.cache/pseudex-bench/ before "
            f"building. Nothing in this module has a text-free fallback: the "
            f"forms ARE the corpus.")
    table: dict[str, _Utterance] = {}
    with _RUDEVICES.open(encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            text = str(json.loads(raw)["text"])
            key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
            if key in table:
                continue
            table[key] = _Utterance(
                key=key, line=number, text=text,
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    return table


def _load_labels() -> list[dict[str, object]]:
    """The hand annotation. Read for its SPANS, never re-derived."""
    if not _LABELS.exists():
        raise FileNotFoundError(
            f"{_LABELS} is missing. The gold address spans are hand-made and "
            f"cannot be recomputed here — recomputing them with a probe is the "
            f"exact defect `Provenance.selection` exists to record.")
    return json.loads(_LABELS.read_text(encoding="utf-8"))


def _source(utterance: _Utterance) -> Source:
    return Source(corpus=_CORPUS, key=utterance.key, line=utterance.line,
                  sha256=utterance.sha256, licence=_LICENCE)


def _locate(text: str, needle: str) -> tuple[int, int]:
    """The one place a span is FOUND rather than built, and it is bounded.

    A hand annotation names a substring of an UNCHANGED utterance; locating it
    is how such an annotation is read, not a derivation from a generated string.
    The rule it must not break is that the string was never rewritten — so a
    needle occurring twice, or not at all, raises instead of picking one.
    """
    first = text.find(needle)
    if first < 0:
        raise InvalidCase(f"{needle!r} is not in {text!r}")
    if text.find(needle, first + 1) >= 0:
        raise InvalidCase(
            f"{needle!r} occurs twice in {text!r}; a hand annotation that does "
            f"not say WHICH one cannot be turned into an offset")
    return first, first + len(needle)


# --- message assembly ------------------------------------------------------
#
# Ground truth is what the generator BUILT. Every span below is recorded while
# the string is laid down, and no case searches its own finished text for a
# value it placed. v2's predecessor matched by substring and lost every part a
# register transform had touched — 162 of 183 sloppy failures were that bug.

@dataclass(frozen=True)
class _Glue:
    """A piece appended with no space before it.

    `space_after` is explicit because the two callers want opposite things and
    a guess would be wrong for one of them: a comma in the `clean` register is
    followed by a space, while a JSON fragment closing a quote and opening the
    next key is not. A tool result assembled with the wrong one carries the
    customer's value with a leading space inside a JSON string, which is a
    corpus defect that would be scored as a gateway one.
    """

    text: str
    space_after: bool


def _line(parts: tuple[object, ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    """One message from labelled parts, with every tagged span recorded."""
    pieces: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    space_before = False
    for part in parts:
        if isinstance(part, _Glue):
            pieces.append(part.text)
            cursor += len(part.text)
            space_before = part.space_after
            continue
        text = part[0] if isinstance(part, tuple) else str(part)
        if not text:
            continue
        if pieces and space_before:
            pieces.append(" ")
            cursor += 1
        if isinstance(part, tuple):
            tag = part[1]
            if tag in spans:
                raise InvalidCase(f"tag {tag!r} used twice in one message")
            spans[tag] = (cursor, cursor + len(text))
        pieces.append(text)
        cursor += len(text)
        space_before = True
    return "".join(pieces), spans


# --- numerals --------------------------------------------------------------
#
# A house number in this register is a run of words, never a digit. The tables
# are written out rather than generated from a library so the contracted forms
# the register actually produces sit beside the canonical ones.

_UNITS: tuple[str, ...] = (
    "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять")
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
_TENS: tuple[str, ...] = (
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто")
_HUNDREDS: tuple[str, ...] = (
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
    "семьсот", "восемьсот", "девятьсот")
_ORDINALS: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой",
    "седьмой", "восьмой", "девятый", "десятый")

# 22.9% of every «-десят» form in the call corpus arrives contracted. That is
# the norm of the register, not an oddity, and a generator that writes only the
# dictionary form measures the easy half of it.
_CONTRACTED: dict[str, str] = {
    "пятьдесят": "песят",
    "шестьдесят": "шеесят",
    "семьдесят": "семесят",
    "восемьдесят": "восемесят",
}


def _words(number: int) -> str:
    """A cardinal, masculine nominative, as a house number is said."""
    if not 1 <= number <= 999:
        raise InvalidCase(f"{number} is outside the house-number range")
    out: list[str] = []
    hundreds, rest = divmod(number, 100)
    if hundreds:
        out.append(_HUNDREDS[hundreds])
    if 10 <= rest <= 19:
        out.append(_TEENS[rest - 10])
    else:
        tens, units = divmod(rest, 10)
        if tens:
            out.append(_TENS[tens])
        if units:
            out.append(_UNITS[units])
    return " ".join(out)


def _contract(text: str, rng: random.Random) -> str:
    """Apply the measured contraction rate to a spoken number."""
    words = []
    for word in text.split():
        if word in _CONTRACTED and rng.random() < 0.229:
            words.append(_CONTRACTED[word])
        else:
            words.append(word)
    return " ".join(words)


def _ordinal(number: int) -> str:
    if not 1 <= number <= 10:
        raise InvalidCase(f"{number} is outside the entrance range")
    return _ORDINALS[number]


# --- the address pool ------------------------------------------------------
#
# Street NAMES are real, from the hand-annotated gold spans of RuDevices. Two
# thirds of them carry no street-type word, which is the measured majority
# shape (113 of 169, 66.9%): a generator that writes «улица Ленина дом 50»
# measures the easy half. `stratum` follows the annotation's own two layers —
# `marker` was selected by the words the detector also reads and is biased
# upward by construction; `random` is the unbiased sample, weight 19.22.

@dataclass(frozen=True)
class _Street:
    name: str
    marked: bool
    stratum: str
    key: str


_STREETS_MARKER: tuple[tuple[str, bool], ...] = (
    ("абазисная", False), ("армейская", False), ("барамзиной", False),
    ("баранова", False), ("берша", False), ("буммашевская", False),
    ("воровского", False), ("восточная", False), ("выставочная", False),
    ("гагарина", False), ("грибоедова", False), ("деревообделочная", False),
    ("дзержинского", False), ("зеленоградская", False), ("калашникова", False),
    ("кирова", False), ("клубная", False), ("коммунаров", False),
    ("котовского", False), ("красина", False), ("ломоносова", False),
    ("люхвинцева", False), ("майская", False), ("маяковского", False),
    ("металлистов", False), ("молодёжная", False), ("напойма", False),
    ("орджоникидзе", False), ("павлова", False), ("петрова", False),
    ("полевая", False), ("ракетная", False), ("репина", False),
    ("советская", False), ("совхозная", False), ("союзная", False),
    ("тимирязева", False), ("труда", False), ("ухтомская", False),
    ("фронтовая", False), ("фруктовая", False), ("химзаводская", False),
    ("циолковского", False), ("школьная", False), ("шумайлова", False),
    ("энгельса", False), ("карла маркса", False), ("степана разина", False),
    ("восьмое марта", False), ("десять лет октября", False),
    ("сорок лет победы", False), ("седьмая подлесная", False),
    ("улица ленина", True), ("улица садовая", True), ("улица камская", True),
    ("улица телегина", True), ("улица сабурова", True),
    ("улица вишнёвая", True), ("улица деловая", True),
    ("улица чайковского", True), ("улица строителей", True),
    ("воткинское шоссе", True), ("заречное шоссе", True),
    ("проезд чапаева", True), ("проезд некрасова", True),
    ("проезд халтурина", True), ("проезд бабушкина", True),
    ("проспект калашникова", True), ("переулок загородный", True),
    ("переулок северный", True), ("переулок смольный", True),
    ("переулок сосновый", True), ("переулок транспортный", True),
    ("воронцовский бульвар", True), ("русская набережная", True),
)

# The unbiased layer: ten street names whose gold utterance was drawn at random
# from the numeral-bearing stratum, not selected by a street word. Without
# these every speech-derived LOC in this module would come from the layer the
# detector's own cues chose, and `validate_corpus` says so out loud.
_STREETS_RANDOM: tuple[tuple[str, str], ...] = (
    ("гусева", "d83451460edf"),
    ("пушкинская", "df83e38ac8ad"),
    ("нижняя", "e168d68bc1d4"),
    ("удмуртская", "137c7b8f643b"),
    ("депутатская", "471075b93ce8"),
    ("бумашевская", "2a9b7616def2"),
    ("комсомольская", "e3fe28fdab75"),
    ("барышникова", "7f8ab6ad073f"),
    ("ленина", "11bd07922fb7"),
    ("карла маркса", "96343396fd6a"),
)


def _written_streets(streets: tuple[_Street, ...]) -> tuple[_Street, ...]:
    """Streets whose NAME is one word, for the two capitalised registers.

    «карла маркса» and «сорок лет победы» have no mechanical title case — the
    real orthography is «Карла Маркса» and «Сорок лет Победы», and no rule
    produces both. Rather than ship a wrong capital in the register whose whole
    point is that it is written correctly, the multi-word names stay in the
    speech registers, where they are lower case and where 72% of this module
    lives anyway.
    """
    return tuple(
        street for street in streets
        if len([word for word in street.name.split()
                if word not in _STREET_TYPE_WORDS]) == 1)


def _street_pool() -> tuple[_Street, ...]:
    marker = tuple(_Street(name=name, marked=marked, stratum="marker", key="")
                   for name, marked in _STREETS_MARKER)
    unbiased = tuple(_Street(name=name, marked=False, stratum="random", key=key)
                     for name, key in _STREETS_RANDOM)
    return marker + unbiased


def _selection(street: _Street) -> str:
    """How a RECOMBINED case entered the set, and why it is never `random`.

    A weight is a property of a SAMPLE. A sentence assembled from a pooled
    street name and an authored mention is not a sample of anything, so it may
    not carry the 19.22 inverse fraction that belongs to the utterances read
    out of the numeral stratum — inflating a stratum weight in our own favour
    is the arithmetic version of the bias this field exists to record.

    What survives is the direction of the bias. A street name that reached this
    module through the MARKER gold layer was surfaced by the words the detector
    also reads, and the case says so. Everything else was written, and
    `authored` is the accurate word for it: the mention shapes are mined, but
    no utterance was selected to produce them, so no cue chose them either.
    Only `_verbatim_cases` carries `random` and its weight, because only there
    is there a sampling fraction to carry.
    """
    return "marker" if street.stratum == "marker" else "authored"


# Only the words that name a KIND of street. Deliberately not the schema's
# `STREET_TYPE_WORDS`, which is a shape probe for the unlabelled audit and
# holds inflected forms this pool never produces.
_STREET_TYPE_WORDS: frozenset[str] = frozenset(
    "улица проезд проспект переулок шоссе бульвар набережная посёлок городок "
    "площадь".split())


@dataclass(frozen=True)
class _Addr:
    street: _Street
    house: int
    letter: str      # «пятьдесят девять а» — a separate word, 18 of 169
    entrance: int    # ordinal BEFORE the marker, 82 against 60 the other way
    flat: int


def _draw_address(streets: tuple[_Street, ...], rng: random.Random) -> _Addr:
    street = rng.choice(streets)
    house = rng.choice((1, 2, 3, 4, 5, 7, 8, 10, 12, 14, 16, 19, 21, 24, 28,
                        31, 35, 39, 42, 47, 53, 58, 63, 66, 71, 78, 85, 92,
                        108, 116, 126, 138, 145, 166, 192, 227, 284))
    letter = rng.choice(("", "", "", "", "", "", "", "", "а", "б")) \
        if house > 1 else ""
    entrance = rng.choice((0, 0, 1, 1, 2, 3, 4, 5)) if not letter else \
        rng.choice((0, 1, 2))
    flat = rng.choice((0, 0, 0, 4, 9, 12, 15, 27, 46, 58))
    if entrance and flat:
        flat = 0
    return _Addr(street=street, house=house, letter=letter,
                 entrance=entrance, flat=flat)


def _render_address(addr: _Addr, register: str, rng: random.Random) -> str:
    """The surface form of one address in one register. Built, never parsed."""
    if register == "voice_raw":
        out = [addr.street.name, _contract(_words(addr.house), rng)]
        if addr.letter:
            out.append(addr.letter)
        if addr.entrance:
            out.append(f"{_ordinal(addr.entrance)} подъезд")
        elif addr.flat:
            out.append(f"квартира {_words(addr.flat)}")
        return " ".join(out)
    if register == "voice_itn":
        out = [addr.street.name, str(addr.house)]
        if addr.letter:
            out.append(addr.letter)
        if addr.entrance:
            out.append(f"{_ordinal(addr.entrance)} подъезд")
        elif addr.flat:
            out.append(f"квартира {addr.flat}")
        return " ".join(out)
    if register in ("chat", "sloppy"):
        # The ordinal-before-marker order is a property of SPEECH (82 against
        # 60 in the corpus). Typed, «4 3 подъезд» is two bare numbers with
        # nothing telling them apart, so the marker leads here — and the flat
        # is what a typed message actually carries.
        out = [addr.street.name, str(addr.house)]
        if addr.letter:
            out.append(addr.letter)
        if addr.flat:
            out.append(f"кв {addr.flat}")
        elif addr.entrance:
            out.append(f"подъезд {addr.entrance}")
        return " ".join(out)
    if register == "clean":
        # «улица Ленина», not «Улица ленина»: the type word stays lower case
        # and the NAME takes the capital, which is what a form writes. The
        # capital that the register gate looks for is the first character of
        # the message, and the sentence around this supplies it.
        head = " ".join(word if word in _STREET_TYPE_WORDS else word.capitalize()
                        for word in addr.street.name.split())
        house = f"д. {addr.house}{addr.letter}" if addr.letter \
            else f"д. {addr.house}"
        tail = f", кв. {addr.flat}" if addr.flat else ""
        return f"{head}, {house}{tail}"
    raise InvalidCase(f"unknown register {register!r}")


# --- the people pool -------------------------------------------------------
#
# The slot order is not fixed and the corpus says so: surname alone 350, given
# alone 255, given+patronymic 109, patronymic alone 29, given+surname 23,
# surname+given+patronymic 23. 15% of mentions arrive in an oblique case, and
# the commonest word in front of a surname is not a cue but a job title —
# сторож, полковник, дежурная — 75 against 20 for «меня зовут».
#
# The diminutives are here by hand because the TZ says they must be: neither a
# name dictionary nor pymorphy3 calls «ирочка», «витёк» or «серёжа» a name, so
# a whole way of naming a person reaches no benchmark that draws from either.

@dataclass(frozen=True)
class _Person:
    given: str
    given_dative: str
    given_accusative: str
    surname: str
    surname_dative: str
    patronymic: str
    female: bool


_PEOPLE: tuple[_Person, ...] = (
    _Person("игорь", "игорю", "игоря", "букин", "букину", "петрович", False),
    _Person("сергей", "сергею", "сергея", "ерохин", "ерохину", "палыч", False),
    _Person("дмитрий", "дмитрию", "дмитрия", "вольнов", "вольнову", "иваныч", False),
    _Person("михаил", "михаилу", "михаила", "кукушкин", "кукушкину", "саныч", False),
    _Person("андрей", "андрею", "андрея", "битюков", "битюкову", "михалыч", False),
    _Person("николай", "николаю", "николая", "фомин", "фомину", "сергеич", False),
    _Person("павел", "павлу", "павла", "миллер", "миллеру", "степаныч", False),
    _Person("алексей", "алексею", "алексея", "бабаев", "бабаеву", "николаич", False),
    _Person("виктор", "виктору", "виктора", "сергеев", "сергееву", "фёдорыч", False),
    _Person("роман", "роману", "романа", "арсентьев", "арсентьеву", "викторыч", False),
    _Person("ирина", "ирине", "ирину", "павлова", "павловой", "анатольевна", True),
    _Person("наталья", "наталье", "наталью", "кузнецова", "кузнецовой", "валентиновна", True),
    _Person("ольга", "ольге", "ольгу", "волкова", "волковой", "петровна", True),
    _Person("татьяна", "татьяне", "татьяну", "рудакова", "рудаковой", "юрьевна", True),
    _Person("елена", "елене", "елену", "станкевич", "станкевичу", "николаевна", True),
    _Person("светлана", "светлане", "светлану", "кочарян", "кочаряну", "ивановна", True),
    _Person("анна", "анне", "анну", "солонская", "солонской", "денисовна", True),
    _Person("юлия", "юлии", "юлию", "потёмкина", "потёмкиной", "григорьевна", True),
    # The hand-laid diminutives. «витёк» declines to «витька», which is exactly
    # the pair that makes the round trip hard: what the tool must receive is
    # what a CRM would store, and that is the nominative.
    _Person("ирочка", "ирочке", "ирочку", "аширбаева", "аширбаевой", "маратовна", True),
    _Person("витёк", "витьку", "витька", "лебедев", "лебедеву", "борисыч", False),
    _Person("серёжа", "серёже", "серёжу", "гаврилов", "гаврилову", "алексеич", False),
    _Person("наташа", "наташе", "наташу", "белова", "беловой", "олеговна", True),
    _Person("санёк", "саньку", "санька", "тарасов", "тарасову", "вадимыч", False),
    _Person("танюха", "танюхе", "танюху", "исаева", "исаевой", "робертовна", True),
    _Person("константин", "константину", "константина", "гуляев", "гуляеву", "эдуардыч", False),
    _Person("артём", "артёму", "артёма", "щербаков", "щербакову", "ильич", False),
    _Person("денис", "денису", "дениса", "зайцев", "зайцеву", "олегович", False),
    _Person("максим", "максиму", "максима", "мельник", "мельнику", "лукич", False),
    _Person("евгений", "евгению", "евгения", "савельев", "савельеву", "аркадьич", False),
    _Person("леонид", "леониду", "леонида", "чернов", "чернову", "тарасыч", False),
    _Person("василий", "василию", "василия", "дроздов", "дроздову", "матвеич", False),
    _Person("руслан", "руслану", "руслана", "хайруллин", "хайруллину", "маратович", False),
    _Person("галина", "галине", "галину", "субботина", "субботиной", "сергеевна", True),
    _Person("людмила", "людмиле", "людмилу", "цветкова", "цветковой", "григорьевна", True),
    _Person("вера", "вере", "веру", "нечаева", "нечаевой", "макаровна", True),
    _Person("зинаида", "зинаиде", "зинаиду", "горбунова", "горбуновой", "николаевна", True),
    _Person("оксана", "оксане", "оксану", "дьяконова", "дьяконовой", "тимофеевна", True),
    _Person("лариса", "ларисе", "ларису", "шестакова", "шестаковой", "юрьевна", True),
    _Person("марина", "марине", "марину", "пантелеева", "пантелеевой", "витальевна", True),
    _Person("жанна", "жанне", "жанну", "коновалова", "коноваловой", "эдуардовна", True),
    _Person("лёха", "лёхе", "лёху", "сомов", "сомову", "прокопыч", False),
    _Person("женька", "женьке", "женьку", "устинов", "устинову", "терентьич", False),
)

# The contracted patronymic is a property of SPEECH — палыч, михалыч, иваныч,
# сергеич, fifteen distinct contracted forms in the call corpus. A delivery
# form writes it out, so the `clean` register expands it: «Вольнов Дмитрий
# Иваныч» on a printed order is the wrong register wearing the right shape.
_PATRONYMIC_FULL: dict[str, str] = {
    "палыч": "павлович", "михалыч": "михайлович", "иваныч": "иванович",
    "саныч": "александрович", "сергеич": "сергеевич",
    "степаныч": "степанович", "николаич": "николаевич",
    "фёдорыч": "фёдорович", "викторыч": "викторович",
    "борисыч": "борисович", "алексеич": "алексеевич",
    "вадимыч": "вадимович", "прокопыч": "прокопьевич",
    "терентьич": "терентьевич", "эдуардыч": "эдуардович",
    "аркадьич": "аркадьевич", "тарасыч": "тарасович",
    "матвеич": "матвеевич",
}


# «сторож битюкова», «дежурная павлова». The title licenses the surname; it is
# not part of it, and the span stops where the name starts.
_TITLES: tuple[str, ...] = (
    "сторож", "дежурный", "дежурная", "полковник", "мастер", "диспетчер",
    "старший", "бригадир",
)
_KINSHIP: tuple[str, ...] = ("дядя", "тётя", "брат", "сестра")


@dataclass(frozen=True)
class _Mention:
    """One way of naming one person: the surface, and what a CRM would store."""

    prefix: str      # a title or a cue standing before the name, never in it
    surface: str     # exactly the characters the span covers
    canonical: str   # the nominative of what was actually said
    suffix: str
    shape: str       # the mined shape this mention reproduces


def _name_mention(person: _Person, register: str, rng: random.Random) -> _Mention:
    """Draw a mention, with the mined shape weights.

    The shape catalogue is `mined/calls_grammar.json`; the weights are its own
    counts. Nothing here searches a finished string: the surface and the
    canonical are both written by this function and travel together.
    """
    roll = rng.random()
    if register == "clean":
        patronymic = _PATRONYMIC_FULL.get(person.patronymic, person.patronymic)
        surface = (f"{person.surname.capitalize()} {person.given.capitalize()} "
                   f"{patronymic.capitalize()}")
        return _Mention("", surface, surface, "",
                        "<фамилия> <имя> <отчество>")
    if roll < 0.34:
        return _Mention("", person.surname, person.surname, "",
                        "<фамилия> — одна, без имени")
    if roll < 0.58:
        return _Mention("", person.given, person.given, "",
                        "<имя> — одно, без фамилии")
    if roll < 0.68:
        surface = f"{person.given} {person.patronymic}"
        return _Mention("", surface, surface, "", "<имя> <отчество>")
    if roll < 0.76:
        title = rng.choice(_TITLES)
        return _Mention(title, person.surname, person.surname, "",
                        "<должность или звание> <фамилия>")
    if roll < 0.82:
        surface = f"{person.given} {person.surname}"
        return _Mention("", surface, surface, "", "<имя> <фамилия>")
    if roll < 0.88:
        surface = f"{person.surname} {person.given} {person.patronymic}"
        return _Mention("", surface, surface, "",
                        "<фамилия> <имя> <отчество>")
    if roll < 0.92:
        return _Mention("это", person.given, person.given, "", "это <имя>")
    if roll < 0.96:
        return _Mention("меня зовут", person.given, person.given, "",
                        "меня зовут <имя>")
    kin = rng.choice(_KINSHIP)
    return _Mention(kin, person.given, person.given, "", "<родство> <имя>")


def _oblique_mention(person: _Person, rng: random.Random) -> _Mention:
    """The 15% of mentions that arrive declined.

    «к букину прибыть», «позовите ирочку». The canonical is the nominative and
    the expected tool argument is the canonical — a declined name written into
    a customer's CRM is the defect, and it has the same shape as a repair.
    """
    if rng.random() < 0.5:
        return _Mention("к", person.surname_dative, person.surname,
                        "прибыть машину туда же куда в прошлый раз",
                        "к <фамилия> — адресат в дательном")
    return _Mention("позовите", person.given_accusative, person.given,
                    "и машину туда же куда в прошлый раз",
                    "<имя> — одно, без фамилии")


# --- phones and dates ------------------------------------------------------
#
# TEMPLATE VALUES inside RECOMBINED FORMS, and `PiiItem.value_source` is what
# says so: neither corpus dictates a phone number, so the digits are ours while
# the sentence around them is a real dispatcher's. Conflating the two fields
# cost v2 a whole family.

def _phone(rng: random.Random) -> tuple[str, str, str]:
    """(chat surface, clean surface, canonical). Digits only — never spoken.

    A phone said in words belongs to `spoken_id`, which owns that defect. Here
    it would average 133 unfindable values into a thousand findable ones and
    the zero would read as noise, which is exactly what happened in v2.
    """
    code = rng.choice((912, 916, 925, 926, 951, 962, 987, 999))
    body = rng.randrange(1000000, 9999999)
    digits = f"{code}{body}"
    canonical = f"+7{digits}"
    return (f"8 {digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:]}",
            f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}",
            canonical)


def _birthdate(rng: random.Random) -> str:
    day = rng.randrange(1, 29)
    month = rng.randrange(1, 13)
    year = rng.randrange(1948, 2004)
    return f"{day:02d}.{month:02d}.{year}"


# --- negatives -------------------------------------------------------------
#
# Half the precision measurement, and it is not the same thing as `optional`:
# an optional value may be masked without penalty, a negative may not be masked
# at all. The room-number family is here because it is the largest measured
# false-positive source in this register — 528 utterances in the call corpus
# put a number beside «кабинет» or «отделение».

@dataclass(frozen=True)
class _Trap:
    prefix: str
    value: str
    suffix: str
    family: str
    why: str


# «к девяти ноль ноль» — the hour arrives in the dative and the zeros as words.
# Only the hours whose dative form the schema's own numeral list holds are used:
# a form outside it would make the unlabelled-shape audit see a shorter run than
# the sentence carries, and this trap exists to be seen.
_HOUR_DATIVE: tuple[tuple[int, str], ...] = (
    (2, "двум"), (3, "трём"), (5, "пяти"), (6, "шести"), (7, "семи"),
    (8, "восьми"), (9, "девяти"), (10, "десяти"),
)
# «три четырнадцатый кабинет» is room 314 said the way rooms are said: the
# hundreds as a cardinal, the rest as an ordinal.
_ROOM_TAIL: tuple[str, ...] = (
    "одиннадцатый", "двенадцатый", "тринадцатый", "четырнадцатый",
    "пятнадцатый", "двадцатый",
)


def _spoken_traps(rng: random.Random) -> tuple[_Trap, ...]:
    hundreds = rng.randrange(2, 6)
    hour = rng.choice(_HOUR_DATIVE)[1]
    order = rng.randrange(2, 10) * 100 + rng.randrange(2, 10) * 10
    branches = rng.randrange(3, 10)
    ward = rng.choice(("второго", "третьего", "пятого", "шестого"))
    return (
        _Trap("зайдите в",
              f"{_words(hundreds)} {rng.choice(_ROOM_TAIL)} кабинет", "",
              "room_number",
              "число рядом с «кабинет» — 528 таких реплик в корпусе звонков"),
        _Trap("это из", f"{ward} отделения", "", "room_number",
              "«второго отделения» — вторая половина тех же 528"),
        _Trap("подъехать надо", f"к {hour} ноль ноль", "",
              "time_of_day", "время, нули проговариваются словом"),
        _Trap("это по заказу", f"{_words(order)}", "", "order_number",
              "продиктованный номер заказа — дефект, который однажды уехал в прод"),
        _Trap("у них там", f"{_words(branches)} филиалов", "", "quantity",
              "количество, а не адрес и не человек"),
    )


def _typed_traps(rng: random.Random) -> tuple[_Trap, ...]:
    return (
        _Trap("зайдите в кабинет", f"{rng.randrange(101, 520)}", "",
              "room_number", "номер кабинета цифрами"),
        _Trap("номер заказа", f"{rng.randrange(1000, 9999)}", "",
              "order_number", "номер заказа, который маскировать нельзя"),
        _Trap("подъехать к", f"{rng.randrange(8, 20)} 30", "", "time_of_day",
              "время суток"),
        _Trap("у нас", f"{rng.randrange(3, 20)} филиалов", "", "quantity",
              "количество филиалов"),
    )


# Verbatim traps: the utterance is a real RuDevices reply and the trap inside
# it is what a live human actually said. No generator would have written these
# — «на улице погода хорошая» is the commonest false mask in the register and
# it exists only because somebody said it.
_VERBATIM_TRAPS: tuple[tuple[str, str, str, str], ...] = (
    ("f44fdb7d1d17", "улице", "street_no_name",
     "«улица» без имени — говорят про погоду, не про адрес"),
    ("40028f5a8e62", "квартиру", "flat_as_home",
     "«квартира» без номера — жильё, а не адресный хвост"),
    ("4bdd1d967905", "шестой подъезд", "entrance_no_street",
     "порядковое плюс подъезд, но улицы в реплике нет"),
    ("9ef8b06372f0", "улице", "street_no_name",
     "«улица» как двор и погода — самая частая ложная маска регистра"),
    ("2b2cf61a6292", "квартиру", "flat_as_home",
     "«квартира» как жильё: разговор про то, кому она достанется"),
    ("508abb93c464", "четвёртый подъезд", "entrance_no_street",
     "адресный хвост без адреса"),
)


# --- filler ----------------------------------------------------------------
#
# Read by hand, one at a time. The keys are frozen here so the pool cannot
# drift when the mechanical filter is tuned: a filler set that changes shape
# under you changes every `deep` case's character count and its rung with it.
#
# One key has been REPLACED rather than dropped, for that reason. `18ff6141bce9`
# («…в последний момент будет рассказывать») fails the shared screen, because
# «последний» is in `schema.FILLER_STOPWORDS` — the corpus's own gold calls
# «улица Последняя» a street, and the stopword list is deliberately uncurated.
# `f116e244efe2` stands in its place at 78 characters against 80, so the deep
# cases keep their length and the rung they were built for.

_FILLER_LONG: tuple[str, ...] = (
    "01ea920b3468", "02245f5b22f7", "03e05470ad0f", "0428e9b6f2c6",
    "05b08612890a", "0622eb2e9bb7", "0999cbb53ed1", "0a6e69ca6c32",
    "0b22aff09389", "0e98ba6558aa", "1466e01eb2b4", "14ad28165302",
    "16bb8542b2a8", "170543bebab9", "179f7e680f2b", "f116e244efe2",
    "1910604fa90a", "19d54d8b2632", "1bbb800237af", "1c69639d31c9",
    "1dbbba919396", "1ed59af79e1b", "201fef5d21a0", "21b823dac6c4",
    "231ced2489a9", "2557e708c4e1", "26bb23dd8346", "270c06d87086",
    "2a895861830e", "2b080e88e281", "2dc7b5b386f4", "2f08e44911b3",
    "2f838844b173", "2f9da6a64e58", "2fc716944a51", "324cfd5fcde4",
    "3261104c23cb", "3521db9ecaa6", "35f91f3ea31f", "368372613f2d",
    "36c9ce959bb7", "379ae43b169f", "37b2ae82b9da", "3975b0e6aced",
    "3c68a783ee52", "3cf5c1f4c77c", "3dea1445ecb0", "3df4b1416a15",
    "3fed84cb8d88", "416900384969", "418b9db19fdd", "43c831ddc6b8",
    "44496986590e", "44af15b88b93", "44d96d8e4399", "46ef001016a8",
    "480efeb7360a", "49194d781151", "4531a748d085", "4994c582fa9b",
    "497cc0eedd02", "49dc92920fdb", "4a8d79d2b20c", "4c1e2d3d7177",
    "4c3e21077ae4", "4d417cbe019c", "4dbba69b9c10", "4e25cfac1f02",
    "4f136289a46d", "4fc4c9923310", "511d2d710ba6", "5158c70a6da1",
    "520e500f23c5", "529ccbfb869a", "5484d61b7ccd", "559598465481",
    "574c986d2651", "593eafac6aac", "59598d779e31", "5f0f66225f19",
    "60e52ab11603", "61c0c5ecb1bb", "62698bfd1213", "6332db1eb0ec",
    "656ea0a85556", "6939ee30ea5c", "6ad84569118d", "6c579d70f164",
    "6d7b43d0aea3", "6e3c0d2c0798", "6e7d1ccf2fb1", "6e884b417942",
    "6f3dd24179bf", "716edf08503e", "73c45b2b4c68", "74c032c2445b",
    "76050ea8dba8", "77da5355352a", "7846af4157fb",
)

_FILLER_SHORT: tuple[str, ...] = (
    "000ff8025247", "0033e22565c7", "005e7a2bdadd", "00fb0bc7d8c9",
    "0108aea9b865", "011baa9542e1", "011fbbe7cbc1", "013e3e92eda9",
    "0143db4bfda7", "015f929632f7", "0190cd4fc852", "01ee368b8d55",
    "022e5fead67f", "023848355913", "024347f0ed72", "02596f470854",
    "026714704fb7", "02873bf95c59", "02c81d53828f", "02d9452f5512",
    "02ee4fe97790", "030f264c8ae1", "0317a0ac8257", "0318ad3b399b",
    "0344a21dfb64", "0348092192f4", "035272b9c584", "037877c751b0",
    "038b41bf34c2", "03a997f658f1", "03cad8dcd266", "03e9593a0902",
    "03f425b99a15", "03fc9f33b1f6", "042c57f5e3be", "0435d1f308ae",
    "043f84abcfc4", "0452d88f28cc", "047c1eaaf23a", "049926943910",
    "04993382bd6b", "049c986d80ea", "04a83ede67fa", "04ab945976dc",
    "04b358b93f62", "0554212495a4", "056693fc4269", "0566de03327f",
    "05757c33c76c", "0592f1b9405f", "05bb603235df", "05cf7b6ebb47",
    "05e164b3a1b8", "06108243abc2", "062586e77dcf", "062f367c6368",
    "06325ec6f02f", "063e275d955b", "068381b94128", "069acbf83662",
    "06cadd87242c", "06d349108d79", "06d78ccb9963", "06f3155b886e",
    "06f9fee8467e", "0708d6d11768", "0715bb25b7d9", "0720e99ca36d",
    "0738f7dec5f1", "0748b30f004a", "074b75939a54", "076cf40d2e8b",
    "0786ca835cc7", "07b133d00f9f", "07bdb72e1374", "07d6debcc5ad",
)

# The agent's own turns. Authored, and kept in the register the customer is
# speaking: a voice agent's reply is transcribed the same way theirs is.
_AGENT_TURNS: tuple[str, ...] = (
    "угу слушаю вас",
    "да я на линии говорите",
    "хорошо записала подождите пожалуйста одну минуту",
    "понимаю вас",
    "ага",
    "да конечно",
    "сейчас гляну по системе",
    "хорошо",
    "поняла вас",
    "это бывает",
    "да да я слушаю",
    "ясно спасибо что рассказали",
    "минуту пожалуйста я тут смотрю",
    "ну да так и есть",
    "принято",
    "согласна с вами",
    "хорошо я всё записала",
    "да я вас поняла продолжайте",
    "понятно",
    "ладно хорошо",
)

_SYSTEM_DISPATCH = (
    "Ты оператор службы такси. Принимаешь заявки голосом и вызываешь "
    "инструменты для подачи машины. Отвечай коротко."
)
_SYSTEM_ORDER = (
    "Ты оператор службы доставки. Оформляешь заказы и вызываешь инструменты. "
    "Отвечай коротко."
)


# --- tools -----------------------------------------------------------------
#
# Parameter names are shared across the tools on purpose: an item claims ONE
# `tool_param`, so a value consumed by two calls needs the same name in both,
# and a corpus whose schemas disagree about it cannot express `indirect` at all.

def _tool(name: str, description: str,
          properties: dict[str, str]) -> ToolSchema:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": "string", "description": text}
                               for key, text in properties.items()},
                "required": list(properties),
            },
        },
    }


_SEND_CAR = _tool(
    "send_car", "Подать машину по адресу.",
    {"address": "адрес подачи", "passenger_name": "имя пассажира",
     "phone": "телефон пассажира", "note": "комментарий"})
_FIND_LAST_TRIP = _tool(
    "find_last_trip", "Найти последнюю поездку пассажира.",
    {"passenger_name": "имя пассажира"})
_CREATE_ORDER = _tool(
    "create_order", "Оформить заказ доставки.",
    {"address": "адрес доставки", "passenger_name": "имя получателя",
     "phone": "телефон", "birthdate": "дата рождения", "note": "комментарий"})
_FIND_CUSTOMER = _tool(
    "find_customer", "Найти клиента в CRM.",
    {"passenger_name": "имя клиента"})

_TOOLS_DISPATCH: tuple[ToolSchema, ...] = (_SEND_CAR, _FIND_LAST_TRIP)
_TOOLS_ORDER: tuple[ToolSchema, ...] = (_CREATE_ORDER, _FIND_CUSTOMER)


# --- transcript construction ----------------------------------------------

@dataclass(frozen=True)
class _Draft:
    """A case under construction: messages plus the claims made about them."""

    messages: list[Message]
    pii: list[PiiItem]
    negatives: list[Negative]


def _new_draft() -> _Draft:
    return _Draft(messages=[], pii=[], negatives=[])


def _add(draft: _Draft, role: str, text: str, source: Source | None,
         name: str) -> int:
    draft.messages.append(Message(role=role, content=text, source=source,
                                  name=name))
    return len(draft.messages) - 1


def _filler_pair(draft: _Draft, utterance: _Utterance, reply: str) -> None:
    _add(draft, "user", utterance.text, _source(utterance), "")
    _add(draft, "assistant", reply, None, "")


def _trap_pair(draft: _Draft, trap: _Trap, reply: str) -> None:
    text, spans = _line((trap.prefix, (trap.value, "t"), trap.suffix))
    index = _add(draft, "user", text, None, "")
    start, end = spans["t"]
    draft.negatives.append(Negative(value=trap.value, start=start, end=end,
                                    msg=index, family=trap.family,
                                    why=trap.why))
    _add(draft, "assistant", reply, None, "")


def _verbatim_trap_pair(draft: _Draft, utterance: _Utterance, needle: str,
                        family: str, why: str, reply: str) -> None:
    index = _add(draft, "user", utterance.text, _source(utterance), "")
    start, end = _locate(utterance.text, needle)
    draft.negatives.append(Negative(value=needle, start=start, end=end,
                                    msg=index, family=family, why=why))
    _add(draft, "assistant", reply, None, "")


def _unused(draft: _Draft, band: tuple[_Utterance, ...]) -> list[_Utterance]:
    seen = {message.content for message in draft.messages}
    return [utterance for utterance in band if utterance.text not in seen]


def _fill(draft: _Draft, pairs: int, band: tuple[_Utterance, ...],
          rng: random.Random) -> None:
    """`pairs` exchanges of ordinary conversation carrying nothing.

    Drawn without replacement inside one case, so a transcript never repeats
    itself by accident — a repeated string is a mask-cache HIT and that is a
    claim some cases make deliberately (`_echo_case`), never one the filler
    should make by itself.
    """
    available = _unused(draft, band)
    if pairs > len(available):
        raise InvalidCase(f"{pairs} filler pairs asked of {len(available)} "
                          f"unused utterances")
    for utterance in rng.sample(available, pairs):
        _filler_pair(draft, utterance, rng.choice(_AGENT_TURNS))


def _fill_to_floor(draft: _Draft, floor: int, band: tuple[_Utterance, ...],
                   rng: random.Random) -> None:
    """Keep talking until the transcript clears the `deep` character floor.

    A fixed filler count cannot clear it: the utterances have real lengths and
    a draw of forty short ones lands under 4000 while a draw of forty long ones
    lands well over. Padding to the floor is what makes `deep` mean the same
    thing in every case rather than «forty replies, whatever that came to».
    """
    available = _unused(draft, band)
    rng.shuffle(available)
    for utterance in available:
        if sum(len(message.content) for message in draft.messages) >= floor:
            return
        _filler_pair(draft, utterance, rng.choice(_AGENT_TURNS))
    raise InvalidCase(
        f"the filler pool ran out before the deep floor of {floor} characters; "
        f"widen the pool rather than lowering the floor — a `deep` rung under "
        f"it is a `long` case wearing the wrong label")


_DEEP_FLOOR: int = 4_100


def _finish(case_id: str, family: str, register: str, context: str,
            provenance: Provenance, cluster: str, conversation_id: str,
            draft: _Draft, tools: tuple[ToolSchema, ...],
            links: tuple[LinkExpectation, ...],
            calls: tuple[ExpectedCall, ...], final: FinalAnswer,
            annotators: int, note: str) -> Case:
    return require_valid(Case(
        id=case_id, family=family, register=register, context=context,
        provenance=provenance, cluster=cluster,
        conversation_id=conversation_id,
        messages=tuple(draft.messages), tools=tools, pii=tuple(draft.pii),
        negatives=tuple(draft.negatives), links=links, calls=calls,
        final=final, preceded_by="", annotators=annotators, adjudicated=False,
        note=note))


# --- the quartet -----------------------------------------------------------

_QUARTET_RUNGS: tuple[tuple[str, int, int], ...] = (
    # (rung, filler pairs, trap pairs) — the counts that land inside the bands
    ("solo", 0, 0),
    ("short", 1, 0),
    ("long", 5, 1),
    ("deep", 38, 2),
)


def _quartet(index: int, register: str,
             streets: tuple[_Street, ...], long_band: tuple[_Utterance, ...],
             short_band: tuple[_Utterance, ...],
             traps: tuple[_Utterance, ...], rng: random.Random) -> list[Case]:
    """One value-set at all four depths, under one cluster.

    Everything except the depth is frozen before the loop: the same person, the
    same address, the same opening utterance, the same expected call. A
    difference between two of these four cases is a difference of depth and
    nothing else, which is the only way the axis answers anything.
    """
    person = _PEOPLE[index % len(_PEOPLE)]
    addr = _draw_address(streets, rng)
    address = _render_address(addr, register, rng)
    mention = _name_mention(person, register, rng)
    late = _oblique_mention(person, rng)
    cluster = f"ctx-q{index:02d}"
    tools = _TOOLS_DISPATCH if index % 2 else _TOOLS_ORDER
    call_name = "send_car" if index % 2 else "create_order"
    all_traps = _spoken_traps(rng) if register == "voice_raw" \
        else _typed_traps(rng)
    # One trap rides INSIDE the opening utterance at every rung, `solo`
    # included. Two reasons and both matter: `solo` allows two messages, so a
    # separate trap turn would push it into `short` and the floor of the ladder
    # would stop existing — and without it the forty `solo` cases would demand
    # nothing of precision, while their three deeper siblings would. A rung
    # that measures a different thing from the others is not a rung.
    inline_trap = all_traps[index % len(all_traps)]
    trap_pool = tuple(trap for trap in all_traps if trap is not inline_trap)
    system = _SYSTEM_DISPATCH if index % 2 else _SYSTEM_ORDER

    cases: list[Case] = []
    for rung, pairs, trap_count in _QUARTET_RUNGS:
        draft = _new_draft()
        _add(draft, "system", system, None, "")
        opening, spans = _line((mention.prefix, (mention.surface, "name"),
                                mention.suffix, (address, "addr"),
                                inline_trap.prefix,
                                (inline_trap.value, "trap")))
        opened = _add(draft, "user", opening, None, "")
        name_start, name_end = spans["name"]
        addr_start, addr_end = spans["addr"]
        draft.negatives.append(Negative(
            value=inline_trap.value, start=spans["trap"][0],
            end=spans["trap"][1], msg=opened, family=inline_trap.family,
            why=inline_trap.why))
        draft.pii.append(PiiItem(
            id="n1", type="NAME", value=mention.surface,
            canonical=mention.canonical, start=name_start, end=name_end,
            msg=opened, identity=f"{cluster}-person", duty="required",
            value_source="pool", spoken=False, tool_param="passenger_name"))
        draft.pii.append(PiiItem(
            id="a1", type="LOC", value=address, canonical=address,
            start=addr_start, end=addr_end, msg=opened,
            identity=f"{cluster}-place", duty="required",
            value_source="corpus", spoken=register == "voice_raw",
            tool_param="address"))

        links: tuple[LinkExpectation, ...] = ()
        if rung != "solo":
            _add(draft, "assistant", "поняла записала", None, "")
            band = long_band if rung == "deep" else short_band
            traps_here = list(rng.sample(list(trap_pool), trap_count)) \
                if trap_count else []
            verbatim_trap = traps[index % len(traps)] if rung == "deep" else None
            _fill(draft, pairs // 2 if traps_here else pairs, band, rng)
            for trap in traps_here:
                _trap_pair(draft, trap, rng.choice(_AGENT_TURNS))
            if verbatim_trap is not None:
                needle, family_name, why = _VERBATIM_TRAP_INDEX[verbatim_trap.key]
                _verbatim_trap_pair(draft, verbatim_trap, needle, family_name,
                                    why, rng.choice(_AGENT_TURNS))
            if traps_here:
                _fill(draft, pairs - pairs // 2, band, rng)
            if rung == "deep":
                _fill_to_floor(draft, _DEEP_FLOOR, band, rng)
            closing, closing_spans = _line(
                (late.prefix, (late.surface, "name"), late.suffix))
            closed = _add(draft, "user", closing, None, "")
            late_start, late_end = closing_spans["name"]
            draft.pii.append(PiiItem(
                id="n2", type="NAME", value=late.surface,
                canonical=late.canonical, start=late_start, end=late_end,
                msg=closed, identity=f"{cluster}-person", duty="required",
                value_source="pool", spoken=False, tool_param=""))
            links = (LinkExpectation(
                left="n1", right="n2", kind="same", case="",
                why="один человек назван дважды в одном разговоре — одна "
                    "подмена, иначе модель получила двух людей"),)

        call = ExpectedCall(
            name=call_name,
            arguments={"passenger_name": mention.canonical,
                       "address": address},
            judged_args=("passenger_name", "address"),
            pii_items=("n1", "a1"), after_msg=opened)
        cases.append(_finish(
            case_id=f"ctx-q{index:02d}-{rung}", family="transfer",
            register=register, context=rung,
            provenance=Provenance(
                kind="recombined", corpus=_CORPUS,
                key=addr.street.key, shape=mention.shape,
                selection=_selection(addr.street), licence=_LICENCE,
                weight=1.0),
            cluster=cluster,
            conversation_id=f"conv-{cluster}-{rung}" if index % 3 else "",
            draft=draft, tools=tools, links=links, calls=(call,),
            final=FinalAnswer((), (), ""),
            annotators=0,
            note=f"матчированная четвёрка {cluster}: то же значение, та же "
                 f"форма, тот же регистр — меняется только глубина ({rung})"))
    return cases


_VERBATIM_TRAP_INDEX: dict[str, tuple[str, str, str]] = {
    key: (needle, family, why) for key, needle, family, why in _VERBATIM_TRAPS}


# --- the specials ----------------------------------------------------------

def _compare_case(index: int, register: str, streets: tuple[_Street, ...],
                  band: tuple[_Utterance, ...], rng: random.Random) -> Case:
    """A partial mention, resolved against a fuller one said long ago.

    This is `Vault.for_conversation` at its longest reach: «ленина» with no
    house resolves against «ленина сорок два» from the top of the transcript
    only inside ONE conversation, and the single-candidate rule is what keeps
    that safe. Judged as the gateway's linking, never as the model's judgement.
    """
    addr = _draw_address(streets, rng)
    address = _render_address(addr, register, rng)
    person = _PEOPLE[(index * 5) % len(_PEOPLE)]
    mention = _name_mention(person, register, rng)
    cluster = f"ctx-cmp{index:02d}"
    deep = index % 2 == 0
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_DISPATCH, None, "")
    opening, spans = _line((mention.prefix, (mention.surface, "name"),
                            (address, "addr")))
    opened = _add(draft, "user", opening, None, "")
    draft.pii.append(PiiItem(
        id="n1", type="NAME", value=mention.surface,
        canonical=mention.canonical, start=spans["name"][0],
        end=spans["name"][1], msg=opened, identity=f"{cluster}-person",
        duty="required", value_source="pool", spoken=False,
        tool_param="passenger_name"))
    draft.pii.append(PiiItem(
        id="a1", type="LOC", value=address, canonical=address,
        start=spans["addr"][0], end=spans["addr"][1], msg=opened,
        identity=f"{cluster}-place", duty="required", value_source="corpus",
        spoken=register == "voice_raw", tool_param="address"))
    _add(draft, "assistant", "хорошо записала", None, "")
    _fill(draft, 30 if deep else 6, band, rng)
    for trap in rng.sample(list(_spoken_traps(rng) if register == "voice_raw"
                                else _typed_traps(rng)), 2):
        _trap_pair(draft, trap, rng.choice(_AGENT_TURNS))
    if deep:
        _fill_to_floor(draft, _DEEP_FLOOR, band, rng)
    # The partial mention: a street with no house identifies nobody on its own,
    # which is why it is `optional` and may not claim a tool parameter. What it
    # claims instead is the LINK.
    # «а я же на нижняя записан» is not Russian and «на нижней» would demand a
    # prepositional this module cannot build for an arbitrary street name. The
    # nominative form real callers use needs no case at all.
    question, qspans = _line(("а это же", (addr.street.name, "part"), "да"))
    asked = _add(draft, "user", question, None, "")
    draft.pii.append(PiiItem(
        id="a2", type="LOC", value=addr.street.name,
        canonical=addr.street.name, start=qspans["part"][0],
        end=qspans["part"][1], msg=asked, identity=f"{cluster}-place",
        duty="optional", value_source="corpus", spoken=False, tool_param=""))
    links = (
        LinkExpectation(
            left="a1", right="a2", kind="same", case="",
            why="частичное упоминание обязано разрешиться против более полного "
                "внутри одного разговора — иначе модель отвечает про другую улицу"),
    )
    call = ExpectedCall(
        name="send_car",
        arguments={"passenger_name": mention.canonical, "address": address},
        judged_args=("passenger_name", "address"), pii_items=("n1", "a1"),
        after_msg=opened)
    return _finish(
        case_id=f"ctx-cmp{index:02d}", family="compare", register=register,
        context="deep" if deep else "long",
        provenance=Provenance(
            kind="recombined", corpus=_CORPUS, key=addr.street.key,
            shape="<АДРЕС>", selection=_selection(addr.street),
            licence=_LICENCE, weight=1.0),
        cluster=cluster,
        conversation_id=f"conv-{cluster}" if index % 2 else "",
        draft=draft, tools=_TOOLS_DISPATCH, links=links, calls=(call,),
        final=FinalAnswer((), (), "да"),
        annotators=0,
        note="частичное упоминание улицы через десятки реплик после полного — "
             "область разговора на максимальном плече")


def _crowd_case(index: int, register: str, streets: tuple[_Street, ...],
                band: tuple[_Utterance, ...], rng: random.Random) -> Case:
    """Two people, one transcript, thirty replies apart.

    The only source of `other_person` inside one conversation: the tool returns
    200 and acts on a real human who is not the one the message was about. The
    `different` link is the claim the corpus would otherwise never make — it
    would ask only whether the gateway links, never whether it refuses to.
    """
    first = _PEOPLE[(index * 7) % len(_PEOPLE)]
    second = _PEOPLE[(index * 7 + 11) % len(_PEOPLE)]
    addr_one = _draw_address(streets, rng)
    addr_two = _draw_address(streets, rng)
    address_one = _render_address(addr_one, register, rng)
    address_two = _render_address(addr_two, register, rng)
    mention_one = _name_mention(first, register, rng)
    mention_two = _name_mention(second, register, rng)
    cluster = f"ctx-crowd{index:02d}"
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_DISPATCH, None, "")
    text_one, spans_one = _line((mention_one.prefix,
                                 (mention_one.surface, "name"),
                                 (address_one, "addr")))
    msg_one = _add(draft, "user", text_one, None, "")
    draft.pii.append(PiiItem(
        id="n1", type="NAME", value=mention_one.surface,
        canonical=mention_one.canonical, start=spans_one["name"][0],
        end=spans_one["name"][1], msg=msg_one, identity=f"{cluster}-first",
        duty="required", value_source="pool", spoken=False,
        tool_param="passenger_name"))
    draft.pii.append(PiiItem(
        id="a1", type="LOC", value=address_one, canonical=address_one,
        start=spans_one["addr"][0], end=spans_one["addr"][1], msg=msg_one,
        identity=f"{cluster}-first-place", duty="required",
        value_source="corpus", spoken=register == "voice_raw",
        tool_param="address"))
    _add(draft, "assistant", "поняла записала", None, "")
    _fill(draft, 30, band, rng)
    for trap in rng.sample(list(_spoken_traps(rng) if register == "voice_raw"
                                else _typed_traps(rng)), 2):
        _trap_pair(draft, trap, rng.choice(_AGENT_TURNS))
    _fill_to_floor(draft, _DEEP_FLOOR, band, rng)
    text_two, spans_two = _line(("а ещё вторую машину",
                                 (mention_two.surface, "name"),
                                 (address_two, "addr")))
    msg_two = _add(draft, "user", text_two, None, "")
    draft.pii.append(PiiItem(
        id="n2", type="NAME", value=mention_two.surface,
        canonical=mention_two.canonical, start=spans_two["name"][0],
        end=spans_two["name"][1], msg=msg_two, identity=f"{cluster}-second",
        duty="required", value_source="pool", spoken=False,
        tool_param="passenger_name"))
    draft.pii.append(PiiItem(
        id="a2", type="LOC", value=address_two, canonical=address_two,
        start=spans_two["addr"][0], end=spans_two["addr"][1], msg=msg_two,
        identity=f"{cluster}-second-place", duty="required",
        value_source="corpus", spoken=register == "voice_raw",
        tool_param="address"))
    links = (
        LinkExpectation(
            left="n1", right="n2", kind="different", case="",
            why="два разных человека в одном разговоре обязаны получить разные "
                "подмены — иначе инструмент вызовут на другого человека"),
        LinkExpectation(
            left="a1", right="a2", kind="different", case="",
            why="два разных адреса, разведённые тридцатью репликами"),
    )
    calls = (
        ExpectedCall(name="send_car",
                     arguments={"passenger_name": mention_one.canonical,
                                "address": address_one},
                     judged_args=("passenger_name", "address"),
                     pii_items=("n1", "a1"), after_msg=msg_one),
        ExpectedCall(name="send_car",
                     arguments={"passenger_name": mention_two.canonical,
                                "address": address_two},
                     judged_args=("passenger_name", "address"),
                     pii_items=("n2", "a2"), after_msg=msg_two),
    )
    return _finish(
        case_id=f"ctx-crowd{index:02d}", family="crowd", register=register,
        context="deep",
        provenance=Provenance(
            kind="recombined", corpus=_CORPUS, key=addr_one.street.key,
            shape="<АДРЕС> <намерение> <АДРЕС>",
            selection=_selection(addr_one.street), licence=_LICENCE,
            weight=1.0),
        cluster=cluster, conversation_id=f"conv-{cluster}", draft=draft,
        tools=_TOOLS_DISPATCH, links=links, calls=calls,
        final=FinalAnswer((), (address_two,), ""),
        annotators=0,
        note="двое в одном разговоре, разведённые сорока репликами: чей адрес "
             "чей после того, как между ними прошёл весь диалог")


def _indirect_case(index: int, register: str, streets: tuple[_Street, ...],
                   band: tuple[_Utterance, ...], rng: random.Random) -> Case:
    """The value is never said. It arrives in a tool result and must come back.

    The only family whose expected argument cannot be derived from the user's
    words at all — and at `deep` it is also the case where the datum the second
    call carries entered the transcript AFTER forty replies of conversation.
    """
    person = _PEOPLE[(index * 3) % len(_PEOPLE)]
    addr = _draw_address(streets, rng)
    address = _render_address(addr, "chat", rng)
    mention = _name_mention(person, register, rng)
    cluster = f"ctx-ind{index:02d}"
    deep = index % 2 == 0
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_DISPATCH, None, "")
    opening, spans = _line((mention.prefix, (mention.surface, "name"),
                            "машину надо"))
    opened = _add(draft, "user", opening, None, "")
    draft.pii.append(PiiItem(
        id="n1", type="NAME", value=mention.surface,
        canonical=mention.canonical, start=spans["name"][0],
        end=spans["name"][1], msg=opened, identity=f"{cluster}-person",
        duty="required", value_source="pool", spoken=False,
        tool_param="passenger_name"))
    _add(draft, "assistant", "поняла сейчас посмотрю", None, "")
    _fill(draft, 32 if deep else 5, band, rng)
    for trap in rng.sample(list(_spoken_traps(rng) if register == "voice_raw"
                                else _typed_traps(rng)), 1):
        _trap_pair(draft, trap, rng.choice(_AGENT_TURNS))
    if deep:
        _fill_to_floor(draft, _DEEP_FLOOR, band, rng)
    result, rspans = _line((_Glue('{"passenger": "', False),
                            (mention.canonical, "who"),
                            _Glue('", "last_address": "', False),
                            (address, "addr"), _Glue('", "trips": 4}', False)))
    tool_msg = _add(draft, "tool", result, None, "find_last_trip")
    draft.pii.append(PiiItem(
        id="a1", type="LOC", value=address, canonical=address,
        start=rspans["addr"][0], end=rspans["addr"][1], msg=tool_msg,
        identity=f"{cluster}-place", duty="required", value_source="corpus",
        spoken=False, tool_param="address"))
    # THE PASSENGER'S NAME COMES BACK IN THE SAME RESULT, and it was not claimed.
    # The address beside it was, so the case demanded masking of one half of a
    # card and said nothing about the other — a gateway masking both was charged
    # a false mask for the name. The inbound leg is where this family lives; a
    # ground truth that reads only the outbound half of it measures half a
    # product.
    #
    # SAME `identity` as `n1`: one person, one substitute, and the pair is what
    # makes «the model saw the same fake in the user turn and in the tool result»
    # a checkable claim rather than two unrelated spans.
    draft.pii.append(PiiItem(
        id="n2", type="NAME", value=mention.canonical,
        canonical=mention.canonical, start=rspans["who"][0],
        end=rspans["who"][1], msg=tool_msg, identity=f"{cluster}-person",
        duty="required", value_source="pool", spoken=False, tool_param=""))
    _add(draft, "user", "да туда же и подавайте", None, "")
    calls = (
        ExpectedCall(name="find_last_trip",
                     arguments={"passenger_name": mention.canonical},
                     judged_args=("passenger_name",), pii_items=("n1",),
                     after_msg=opened),
        ExpectedCall(name="send_car",
                     arguments={"passenger_name": mention.canonical,
                                "address": address},
                     judged_args=("passenger_name", "address"),
                     pii_items=("n1", "a1"), after_msg=tool_msg),
    )
    return _finish(
        case_id=f"ctx-ind{index:02d}", family="indirect", register=register,
        context="deep" if deep else "long",
        provenance=Provenance(
            kind="recombined", corpus=_CORPUS, key="",
            shape="<имя> — одно, без фамилии", selection="authored",
            licence=_LICENCE, weight=1.0),
        cluster=cluster, conversation_id="" if index % 2 else f"conv-{cluster}",
        draft=draft, tools=_TOOLS_DISPATCH, links=(), calls=calls,
        final=FinalAnswer((address,), (), ""),
        annotators=0,
        note="значение приходит ИЗ ответа инструмента после десятков реплик и "
             "обязано вернуться настоящим в следующий вызов")


def _result_case(index: int, register: str, streets: tuple[_Street, ...],
                 band: tuple[_Utterance, ...], rng: random.Random) -> Case:
    """The CRM answers with somebody else's row in the same payload.

    `must_not_contain` is the axis nobody has: over WebArena's 812 cases
    `must_include` appears 639 times and `must_not` exactly zero. Here it holds
    a REAL value whose appearance in the reply is a disclosure.
    """
    person = _PEOPLE[(index * 13) % len(_PEOPLE)]
    other = _PEOPLE[(index * 13 + 5) % len(_PEOPLE)]
    addr = _draw_address(streets, rng)
    other_addr = _draw_address(streets, rng)
    address = _render_address(addr, "chat", rng)
    other_address = _render_address(other_addr, "chat", rng)
    mention = _name_mention(person, register, rng)
    cluster = f"ctx-res{index:02d}"
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_ORDER, None, "")
    opening, spans = _line((mention.prefix, (mention.surface, "name"),
                            "заказ мой посмотрите"))
    opened = _add(draft, "user", opening, None, "")
    draft.pii.append(PiiItem(
        id="n1", type="NAME", value=mention.surface,
        canonical=mention.canonical, start=spans["name"][0],
        end=spans["name"][1], msg=opened, identity=f"{cluster}-person",
        duty="required", value_source="pool", spoken=False,
        tool_param="passenger_name"))
    _add(draft, "assistant", "минуту смотрю", None, "")
    _fill(draft, 30, band, rng)
    for trap in rng.sample(list(_typed_traps(rng)), 1):
        _trap_pair(draft, trap, rng.choice(_AGENT_TURNS))
    _fill_to_floor(draft, _DEEP_FLOOR, band, rng)
    result, rspans = _line((_Glue('[{"name": "', False),
                            (mention.canonical, "n"),
                            _Glue('", "address": "', False), (address, "a"),
                            _Glue('"}, {"name": "', False),
                            (other.surname, "on"),
                            _Glue('", "address": "', False),
                            (other_address, "oa"), _Glue('"}]', False)))
    tool_msg = _add(draft, "tool", result, None, "find_customer")
    draft.pii.append(PiiItem(
        id="n2", type="NAME", value=mention.canonical,
        canonical=mention.canonical, start=rspans["n"][0], end=rspans["n"][1],
        msg=tool_msg, identity=f"{cluster}-person", duty="required",
        value_source="pool", spoken=False, tool_param=""))
    draft.pii.append(PiiItem(
        id="a1", type="LOC", value=address, canonical=address,
        start=rspans["a"][0], end=rspans["a"][1], msg=tool_msg,
        identity=f"{cluster}-place", duty="required", value_source="corpus",
        spoken=False, tool_param="address"))
    draft.pii.append(PiiItem(
        id="n3", type="NAME", value=other.surname, canonical=other.surname,
        start=rspans["on"][0], end=rspans["on"][1], msg=tool_msg,
        identity=f"{cluster}-other", duty="required", value_source="pool",
        spoken=False, tool_param=""))
    draft.pii.append(PiiItem(
        id="a2", type="LOC", value=other_address, canonical=other_address,
        start=rspans["oa"][0], end=rspans["oa"][1], msg=tool_msg,
        identity=f"{cluster}-other-place", duty="required",
        value_source="corpus", spoken=False, tool_param=""))
    _add(draft, "user", "и подтвердите пожалуйста адрес доставки", None, "")
    call = ExpectedCall(
        name="create_order",
        arguments={"passenger_name": mention.canonical, "address": address},
        judged_args=("passenger_name", "address"), pii_items=("n1", "a1"),
        after_msg=tool_msg)
    return _finish(
        case_id=f"ctx-res{index:02d}", family="result", register=register,
        context="deep",
        provenance=Provenance(
            kind="recombined", corpus=_CORPUS, key="",
            shape="<фамилия> — одна, без имени", selection="authored",
            licence=_LICENCE, weight=1.0),
        cluster=cluster, conversation_id=f"conv-{cluster}", draft=draft,
        tools=_TOOLS_ORDER,
        links=(LinkExpectation(
            left="n1", right="n2", kind="same", case="",
            why="имя, названное клиентом, и имя, вернувшееся из CRM, — один "
                "человек и обязаны прийти к модели одной подменой"),
               LinkExpectation(
            left="n1", right="n3", kind="different", case="",
            why="вторая строка ответа CRM — другой клиент; слить их значит "
                "выдать чужие данные за данные звонящего")),
        calls=(call,),
        final=FinalAnswer((address,), (other_address, other.surname), ""),
        annotators=0,
        note="CRM возвращает две строки, вторая — чужая; в ответе клиенту она "
             "появиться не имеет права")


def _echo_case(index: int, register: str, streets: tuple[_Street, ...],
               band: tuple[_Utterance, ...], rng: random.Random) -> Case:
    """The same utterance, word for word, at the top and at the bottom.

    A mask cache keyed on RAW content sees the second copy as a hit. That is
    the intended behaviour and the claim here is what must survive it: one
    value, one substitute, forty replies apart. It is the cheapest possible
    probe for a cache that has quietly become per-conversation-blind, and the
    only one that does not need the engine's internals to state.
    """
    person = _PEOPLE[(index * 17) % len(_PEOPLE)]
    addr = _draw_address(streets, rng)
    address = _render_address(addr, register, rng)
    mention = _name_mention(person, register, rng)
    cluster = f"ctx-echo{index:02d}"
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_DISPATCH, None, "")
    text, spans = _line((mention.prefix, (mention.surface, "name"),
                         (address, "addr")))
    first = _add(draft, "user", text, None, "")
    draft.pii.append(PiiItem(
        id="n1", type="NAME", value=mention.surface,
        canonical=mention.canonical, start=spans["name"][0],
        end=spans["name"][1], msg=first, identity=f"{cluster}-person",
        duty="required", value_source="pool", spoken=False,
        tool_param="passenger_name"))
    draft.pii.append(PiiItem(
        id="a1", type="LOC", value=address, canonical=address,
        start=spans["addr"][0], end=spans["addr"][1], msg=first,
        identity=f"{cluster}-place", duty="required", value_source="corpus",
        spoken=register == "voice_raw", tool_param="address"))
    _add(draft, "assistant", "поняла", None, "")
    _fill(draft, 34, band, rng)
    for trap in rng.sample(list(_spoken_traps(rng) if register == "voice_raw"
                                else _typed_traps(rng)), 2):
        _trap_pair(draft, trap, rng.choice(_AGENT_TURNS))
    _fill_to_floor(draft, _DEEP_FLOOR, band, rng)
    second = _add(draft, "user", text, None, "")
    draft.pii.append(PiiItem(
        id="n2", type="NAME", value=mention.surface,
        canonical=mention.canonical, start=spans["name"][0],
        end=spans["name"][1], msg=second, identity=f"{cluster}-person",
        duty="required", value_source="pool", spoken=False, tool_param=""))
    draft.pii.append(PiiItem(
        id="a2", type="LOC", value=address, canonical=address,
        start=spans["addr"][0], end=spans["addr"][1], msg=second,
        identity=f"{cluster}-place", duty="required", value_source="corpus",
        spoken=register == "voice_raw", tool_param=""))
    links = (
        LinkExpectation(left="n1", right="n2", kind="same", case="",
                        why="та же строка сказана дважды — кеш масок обязан "
                            "отдать ту же подмену, а не отчеканить вторую"),
        LinkExpectation(left="a1", right="a2", kind="same", case="",
                        why="тот же адрес дословно, сорок реплик спустя"),
    )
    call = ExpectedCall(
        name="send_car",
        arguments={"passenger_name": mention.canonical, "address": address},
        judged_args=("passenger_name", "address"), pii_items=("n1", "a1"),
        after_msg=first)
    return _finish(
        case_id=f"ctx-echo{index:02d}", family="transfer", register=register,
        context="deep",
        provenance=Provenance(
            kind="recombined", corpus=_CORPUS, key=addr.street.key,
            shape="<АДРЕС>", selection=_selection(addr.street),
            licence=_LICENCE, weight=1.0),
        cluster=cluster, conversation_id="", draft=draft,
        tools=_TOOLS_DISPATCH, links=links, calls=(call,),
        final=FinalAnswer((), (), ""),
        annotators=0,
        note="дословный повтор реплики через сорок обменов: кеш масок под "
             "нагрузкой, одна подмена на два вхождения")


# --- verbatim cases --------------------------------------------------------

def _verbatim_cases(table: dict[str, _Utterance],
                    labels: list[dict[str, object]]) -> list[Case]:
    """Real utterances, unchanged, with the hand annotation as ground truth.

    The strongest material this module has and the only material whose ground
    truth nobody here wrote. They sit at `solo` because a real utterance is one
    message: assembling several of them into a transcript would make the case
    something the annotator never saw.

    These are the only cases in this module that declare NO negative, and the
    reason is the same one: a trap written into a real utterance is no longer a
    real utterance. Precision is measured on the other 224 cases, where the
    text is ours to write and the trap is honest.

    Both strata are represented and the weights say which is which. The marker
    layer was chosen by the words the detector reads and the probe recalls
    97.2% inside it against 0.0% outside; a corpus carrying only that layer
    reports on the half it was selected for.
    """
    cases: list[Case] = []
    wanted = [row for row in labels if row["label"] == "адрес с номером"
              and not unsafe_outside(
                  str(row["text"]),
                  [str(v) for v in row["spans"]])]  # type: ignore[union-attr]
    ordered = sorted(wanted, key=lambda row: (str(row["filter"]),
                                              str(row["key"])))
    random_layer = [row for row in ordered if row["filter"] == "number-sample"]
    marker_layer = [row for row in ordered if row["filter"] == "marker"][:13]
    for position, row in enumerate(random_layer + marker_layer):
        key = str(row["key"])
        utterance = table.get(key)
        if utterance is None:
            raise InvalidCase(
                f"annotation key {key} is not in the corpus — the source moved "
                f"under the labels and every span in this case is now wrong")
        spans = [str(value) for value in row["spans"]]  # type: ignore[union-attr]
        draft = _new_draft()
        _add(draft, "system", _SYSTEM_DISPATCH, None, "")
        index = _add(draft, "user", utterance.text, _source(utterance), "")
        # EVERY span the annotation claims, not `spans[0]`. Eleven of the
        # annotated rows carry two addresses — «восточная девять пятый подъезд
        # поедем на ленина сто сорок шесть» is a pickup and a destination — and
        # taking the first made the second real address ground truth's silence
        # about a value that is in the text. The annotator wrote both down; a
        # builder that reads one of them is throwing away the only material here
        # whose truth nobody in this repository decided.
        #
        # The first is what the tool consumes: `send_car` takes ONE address, and
        # inventing a second parameter to justify claiming the second span would
        # be writing a tool schema to fit the ground truth. `tool_param=""` is
        # the field's own word for «present, and no tool consumes it».
        for order, span in enumerate(spans):
            start, end = _locate(utterance.text, span)
            draft.pii.append(PiiItem(
                id=f"a{order + 1}", type="LOC", value=span, canonical=span,
                start=start, end=end, msg=index,
                identity=f"caller-place-{order + 1}", duty="required",
                value_source="corpus", spoken=True,
                tool_param="address" if order == 0 else ""))
        first = spans[0]
        stratum = "random" if row["filter"] == "number-sample" else "marker"
        call = ExpectedCall(
            name="send_car", arguments={"address": first},
            judged_args=("address",), pii_items=("a1",), after_msg=index)
        cases.append(_finish(
            case_id=f"ctx-verb{position:02d}", family="transfer",
            register="voice_raw", context="solo",
            provenance=Provenance(
                kind="verbatim", corpus=_CORPUS, key=key, shape="",
                selection=stratum, licence=_LICENCE,
                weight=19.22 if stratum == "random" else 1.0),
            cluster=f"ctx-verb-{key}", conversation_id="", draft=draft,
            tools=_TOOLS_DISPATCH, links=(), calls=(call,),
            final=FinalAnswer((), (), ""), annotators=1,
            note=f"настоящая реплика, не тронутая: эталон — ручная разметка, "
                 f"страта {stratum}"))
    return cases


# --- the written registers -------------------------------------------------

_TYPO_KEYS: dict[str, str] = {
    "а": "ф", "в": "ы", "е": "к", "и": "м", "к": "е", "м": "и", "н": "г",
    "о": "л", "р": "п", "с": "ч", "т": "ь", "у": "ц", "л": "о", "п": "р",
}


def _typo(word: str, rng: random.Random) -> str:
    """A keyboard error, not a phonetic one.

    `sloppy` and `voice_raw` are separate registers because their errors have
    different causes and break different things: ASR mangles a word by sound
    («триц», «песят», «лермонтого»), a keyboard by adjacency («Кзнецов»).
    """
    if len(word) < 4:
        return word
    position = rng.randrange(1, len(word) - 1)
    roll = rng.random()
    if roll < 0.4:
        return word[:position] + word[position + 1:]
    if roll < 0.7:
        return (word[:position] + word[position + 1] + word[position]
                + word[position + 2:])
    replacement = _TYPO_KEYS.get(word[position], word[position])
    return word[:position] + replacement + word[position + 1:]


def _written_case(index: int, register: str, streets: tuple[_Street, ...],
                  rng: random.Random) -> Case:
    """`chat`, `sloppy` and `clean`, at the two shallow rungs.

    `clean` is capped at a twentieth of the corpus and exists to prove we did
    not break on it — it is not a register this product meets. It is kept
    shallow on purpose: there is no literary filler to build a `deep` case out
    of, and inventing forty literary replies would spend the whole budget on
    text nobody says.
    """
    person = _PEOPLE[(index * 11) % len(_PEOPLE)]
    addr = _draw_address(_written_streets(streets), rng)
    address = _render_address(addr, register, rng)
    mention = _name_mention(person, register, rng)
    # The typo is applied HERE, before the message is assembled, so the ground
    # truth is the string this function put down. Reading it back out of the
    # finished text is the bug that cost v2 162 of its 183 sloppy failures.
    #
    # `canonical` for `sloppy` is the misspelt form, not the correct one: the
    # ground truth is the canonical form of WHAT WAS WRITTEN, and a gateway
    # cannot invent «Кузнецова» out of «Кзнецова» — demanding it would score
    # the product on information the message never carried.
    surface = _typo(mention.surface, rng) if register == "sloppy" \
        else mention.surface
    canonical = surface if register == "sloppy" else mention.canonical
    chat_phone, clean_phone, phone_canonical = _phone(rng)
    phone = clean_phone if register == "clean" else chat_phone
    cluster = f"ctx-w{index:02d}"
    short = index % 2 == 0
    typed = _typed_traps(rng)
    # A delivery form does not say «зайдите в кабинет». The order number is the
    # trap that belongs in this register, and it is the one that shipped as a
    # real defect: every dictated order number was being masked.
    trap = next(item for item in typed if item.family == "order_number") \
        if register == "clean" else rng.choice(typed)
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_ORDER, None, "")
    # At `solo` the trap has to ride inside the one utterance the rung allows:
    # a second message would put the case in `short` and quietly change which
    # rung it is reporting on.
    inline: tuple[object, ...] = () if short else (
        (trap.prefix, (trap.value, "trap")) if register != "clean"
        else (_Glue(",", True), trap.prefix, (trap.value, "trap"), _Glue(".", True)))
    if register == "clean":
        parts: tuple[object, ...] = (
            "Заказ на имя:", (surface, "name"), _Glue(",", True),
            "адрес доставки:", (address, "addr"), _Glue(",", True), "телефон:",
            (phone, "phone")) + (inline or (_Glue(".", True),))
    elif register == "sloppy":
        parts = ("заказ на", (surface, "name"), "адрес",
                 (address, "addr"), "тел", (phone, "phone")) + inline
    else:
        parts = ("оформите на", (surface, "name"), "адрес",
                 (address, "addr"), "телефон", (phone, "phone")) + inline
    text, spans = _line(parts)
    opened = _add(draft, "user", text, None, "")
    draft.pii.append(PiiItem(
        id="n1", type="NAME", value=surface, canonical=canonical,
        start=spans["name"][0], end=spans["name"][1], msg=opened,
        identity=f"{cluster}-person", duty="required", value_source="pool",
        spoken=False, tool_param="passenger_name"))
    draft.pii.append(PiiItem(
        id="a1", type="LOC", value=address, canonical=address,
        start=spans["addr"][0], end=spans["addr"][1], msg=opened,
        identity=f"{cluster}-place", duty="required", value_source="corpus",
        spoken=False, tool_param="address"))
    draft.pii.append(PiiItem(
        id="p1", type="PHONE", value=phone, canonical=phone_canonical,
        start=spans["phone"][0], end=spans["phone"][1], msg=opened,
        identity=f"{cluster}-phone", duty="required", value_source="template",
        spoken=False, tool_param="phone"))
    if short:
        _add(draft, "assistant", "принято, оформляю"
             if register == "clean" else "принято оформляю", None, "")
        trap_text, trap_spans = _line((trap.prefix, (trap.value, "t")))
        trap_index = _add(draft, "user", trap_text, None, "")
        draft.negatives.append(Negative(
            value=trap.value, start=trap_spans["t"][0],
            end=trap_spans["t"][1], msg=trap_index, family=trap.family,
            why=trap.why))
    else:
        draft.negatives.append(Negative(
            value=trap.value, start=spans["trap"][0], end=spans["trap"][1],
            msg=opened, family=trap.family, why=trap.why))
    call = ExpectedCall(
        name="create_order",
        arguments={"passenger_name": canonical, "address": address,
                   "phone": phone_canonical},
        judged_args=("passenger_name", "address", "phone"),
        pii_items=("n1", "a1", "p1"), after_msg=opened)
    return _finish(
        case_id=f"ctx-w{index:02d}", family="transfer", register=register,
        context="short" if short else "solo",
        provenance=Provenance(
            # `authored`, not the street's stratum. Nobody selected this
            # sentence — the written registers have no mined shape catalogue
            # behind them, and the only corpus-derived thing in it is the
            # street name. Calling it `marker` would say the PHONE in the same
            # message had been surfaced by an address cue, which is not a
            # claim anything supports.
            kind="recombined", corpus=_CORPUS, key=addr.street.key,
            shape=mention.shape, selection="authored",
            licence=_LICENCE, weight=1.0),
        cluster=cluster, conversation_id=f"conv-{cluster}" if short else "",
        draft=draft, tools=_TOOLS_ORDER, links=(), calls=(call,),
        final=FinalAnswer((), (), ""),
        annotators=0,
        note=f"письменный регистр {register} на мелкой ступени — контроль, "
             f"что глубина, а не регистр, объясняет разницу")


def _template_case(index: int, rng: random.Random) -> Case:
    """A form nobody spoke, carrying only types no speech corpus holds.

    `template` is permitted exactly here and the schema enforces it: a case
    carrying NAME or LOC may not be a template, because mining reaches both.
    Phone and date of birth it does not reach — neither corpus dictates a
    number — so their sentences are written, declared, and reported apart.
    """
    chat_phone, clean_phone, phone_canonical = _phone(rng)
    birthdate = _birthdate(rng)
    trap = next(item for item in _typed_traps(rng)
                if item.family == "order_number")
    cluster = f"ctx-tpl{index:02d}"
    clean = index % 2 == 0
    draft = _new_draft()
    _add(draft, "system", _SYSTEM_ORDER, None, "")
    if clean:
        parts: tuple[object, ...] = (
            "Телефон для связи:", (clean_phone, "phone"), _Glue(",", True),
            "дата рождения", (birthdate, "dob"), _Glue(",", True),
            trap.prefix, (trap.value, "trap"), _Glue(".", True))
    else:
        parts = ("телефон", (chat_phone, "phone"), "др", (birthdate, "dob"),
                 trap.prefix, (trap.value, "trap"))
    text, spans = _line(parts)
    opened = _add(draft, "user", text, None, "")
    draft.negatives.append(Negative(
        value=trap.value, start=spans["trap"][0], end=spans["trap"][1],
        msg=opened, family=trap.family, why=trap.why))
    phone = clean_phone if clean else chat_phone
    draft.pii.append(PiiItem(
        id="p1", type="PHONE", value=phone, canonical=phone_canonical,
        start=spans["phone"][0], end=spans["phone"][1], msg=opened,
        identity=f"{cluster}-phone", duty="required", value_source="template",
        spoken=False, tool_param="phone"))
    draft.pii.append(PiiItem(
        id="d1", type="DOB", value=birthdate, canonical=birthdate,
        start=spans["dob"][0], end=spans["dob"][1], msg=opened,
        identity=f"{cluster}-dob", duty="required", value_source="template",
        spoken=False, tool_param="birthdate"))
    call = ExpectedCall(
        name="create_order",
        arguments={"phone": phone_canonical, "birthdate": birthdate},
        judged_args=("phone", "birthdate"), pii_items=("p1", "d1"),
        after_msg=opened)
    return _finish(
        case_id=f"ctx-tpl{index:02d}", family="transfer",
        register="clean" if clean else "chat", context="solo",
        provenance=Provenance(
            kind="template", corpus="authored", key="", shape="",
            selection="authored", licence="authored", weight=1.0),
        cluster=cluster, conversation_id="", draft=draft, tools=_TOOLS_ORDER,
        links=(), calls=(call,), final=FinalAnswer((), (), ""),
        annotators=0,
        note="шаблон разрешён только здесь: телефон и дата рождения не "
             "встречаются ни в одном из речевых корпусов")


# --- the build -------------------------------------------------------------

# The register of each quartet. `family` is not a column here because every
# quartet is a `transfer` by construction — the customer states the datum and
# one call consumes it — and depth crosses the other families through the
# specials below. A column that is constant is a column that says nothing.
_QUARTET_REGISTERS: tuple[str, ...] = (
    "voice_raw", "voice_raw", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_itn",
    "voice_raw", "chat", "voice_raw", "voice_raw", "voice_raw",
)


def build(seed: int) -> list[Case]:
    """Every case this module owns, in file order. Deterministic in `seed`."""
    rng = random.Random(f"v3:context:{seed}")
    table = _load_utterances()
    labels = _load_labels()
    streets = _street_pool()

    long_band = tuple(_require(table, key) for key in _FILLER_LONG)
    short_band = tuple(_require(table, key) for key in _FILLER_SHORT)
    _audit_filler(long_band + short_band)
    traps = tuple(_require(table, key) for key, _, _, _ in _VERBATIM_TRAPS)

    cases: list[Case] = list(_verbatim_cases(table, labels))
    for index, register in enumerate(_QUARTET_REGISTERS):
        cases.extend(_quartet(index, register, streets, long_band,
                              short_band, traps, rng))
    for index in range(12):
        cases.append(_compare_case(index, "voice_raw" if index % 3 else "chat",
                                   streets, long_band, rng))
    for index in range(10):
        cases.append(_crowd_case(index, "voice_raw" if index % 3 else "chat",
                                 streets, long_band, rng))
    for index in range(10):
        cases.append(_indirect_case(index, "chat" if index % 2 else "voice_raw",
                                    streets, long_band, rng))
    for index in range(6):
        cases.append(_result_case(index, "chat", streets, long_band, rng))
    for index in range(6):
        cases.append(_echo_case(index, "voice_raw" if index % 2 else "chat",
                                streets, long_band, rng))
    for index in range(14):
        register = ("clean", "sloppy", "sloppy", "clean")[index % 4]
        cases.append(_written_case(index, register, streets, rng))
    # Six, not four: `MIN_TYPE_DENOMINATOR` is five, and a type below it may be
    # printed only as a count. Four DOB items would make this module's date
    # column unreportable by the corpus's own rule.
    for index in range(6):
        cases.append(_template_case(index, rng))
    return cases


def _require(table: dict[str, _Utterance], key: str) -> _Utterance:
    utterance = table.get(key)
    if utterance is None:
        raise InvalidCase(
            f"filler key {key} is not in RuDevices any more. The pool is frozen "
            f"by hand; a vanished key means the corpus moved, and re-picking "
            f"silently would change every `deep` case's length.")
    return utterance


def _audit_filler(band: tuple[_Utterance, ...]) -> None:
    """Fail closed on filler that carries anything the ground truth omits.

    The whole screen is `schema.unsafe_filler`, and calling it rather than
    restating it is the point. This module used to check a digit and a numeral
    run of one; it had no name check and no street check, and neither did four
    of its neighbours, each in its own way. One screen in one place is what makes
    a name added for one family protect all eleven.
    """
    problems: list[str] = []
    for utterance in band:
        reason = unsafe_filler(utterance.text)
        if reason:
            problems.append(f"{utterance.key}: {reason} — {utterance.text!r}")
    if problems:
        raise InvalidCase("\n".join(problems))


def main() -> None:
    cases = build(20260830)
    problems: list[str] = []
    for case in cases:
        problems.extend(validate(case))
    if problems:
        print("\n".join(problems[:40]))
        raise SystemExit(f"{len(problems)} problems")

    def tally(pick) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in cases:
            counts[pick(case)] = counts.get(pick(case), 0) + 1
        return dict(sorted(counts.items(), key=lambda pair: -pair[1]))

    total = len(cases)
    print(f"attribution      {ATTRIBUTION}")
    print(f"cases            {total}")
    print(f"clusters         {len({case.cluster for case in cases})}")
    print(f"family           {tally(lambda c: c.family)}")
    print(f"register         {tally(lambda c: c.register)}")
    print(f"context          {tally(lambda c: c.context)}")
    print(f"provenance       {tally(lambda c: c.provenance.kind)}")
    print(f"selection        {tally(lambda c: c.provenance.selection)}")
    speech = sum(1 for c in cases if c.register in ("voice_raw", "voice_itn"))
    real = sum(1 for c in cases
               if c.provenance.kind in ("verbatim", "recombined"))
    print(f"speech share     {speech / total:.1%}")
    print(f"real-form share  {real / total:.1%}")
    types: dict[str, int] = {}
    values: dict[str, set[str]] = {}
    for case in cases:
        for item in case.pii:
            if item.duty != "required":
                continue
            types[item.type] = types.get(item.type, 0) + 1
            values.setdefault(item.type, set()).add(item.canonical.casefold())
    print("required items   " + ", ".join(
        f"{kind} {count} ({len(values[kind])} различных)"
        for kind, count in sorted(types.items())))
    negatives: dict[str, int] = {}
    for case in cases:
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print(f"negatives        {dict(sorted(negatives.items()))}")


if __name__ == "__main__":
    main()
