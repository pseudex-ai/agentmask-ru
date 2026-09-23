"""THE RIGHT GATEWAY, simulated — the instrument's own acceptance probe.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.perfect              # the acceptance tier, ~2 s
    python3 -m bench.agentpii5.perfect --tier max   # the whole corpus, ~14 s

THIS FILE PRINTS NUMBERS; IT JUDGES NOTHING. The floors those numbers must
clear live in `test_perfect.BOUNDS`, and the command that CHECKS them on the
corpus every published figure comes from is

    python3 -m bench.agentpii5.test_perfect --tier max   # ~3 min

which is the run to make before any number of this benchmark is quoted. Reading
the table below and nodding is what left `answer_real` at 636/637 for five
rounds with nothing in the repository able to say so.

Every metric line of this benchmark answers «did the gateway do what the
product promises». A line that a RIGHT gateway cannot earn is a broken line,
and until round 5 the evidence that our lines can be earned lived in a scratch
file under `/tmp` that needed THREE corrections to become honest — two of them
probe bugs worth twelve points of `round_trip` / `end_to_end` /
`multi_all_out`. Nobody could re-check the claim, which is the one thing a
private benchmark cannot afford. So the probe moved here, beside the code it
certifies.

WHAT THIS IS. For every `CaseV5` of the corpus it builds the `ArmRunV5` that a
gateway doing exactly the right thing — and an agent obeying the case — would
leave behind: every declared hop performed, every value masked on the way in,
every value restored on the way out in the agent's own form, one substitute per
identity for the whole conversation. Then it runs the package's OWN
`observe.observe` and `metrics.METRIC_FUNCTIONS` over those records.

WHAT THIS IS NOT. Nothing here computes a verdict. The simulation only writes
records; every number comes from the package's own code, so a probe that
flattered the gateway could not also move a metric. It calls no model, opens no
socket and never imports the engine — it is the corpus, the tool registry and
arithmetic.

THE THREE CORRECTIONS ARE THE SPECIFICATION (§2). Each is a statement about
what a right gateway does, each is labelled with what the probe printed while
it was wrong, and each has a test that falls when it is reverted
(`test_perfect.py`). Read them before changing anything here: they are the
places where a plausible simulation charges the gateway for the probe's own
bookkeeping.

THE OTHER HALF lives in `test_perfect.py`: SIX wrong gateways must FAIL the
same bounds this one clears. An acceptance test a wrong gateway can also pass
is not an acceptance test.

AND THE MINT IS PART OF THE SPECIFICATION TOO (§1bis). A substitute the model
reads has to be a WORD, not a string of the right length: a letter-mangled fake
is in no dictionary, pymorphy3 will only guess at it, and `NAME.gram_case` —
the most expensive feature §8.4 names — then abstains on every name in the run.
Measured before the pool: 6 200 of 6 200 NAME substitutes silent against 93 of
6 200 real values, so «a right gateway takes form_hOUT whole» was earned with
that feature switched off and a gateway answering a case of its own choosing
walked past the line. `test_perfect.test_readable_fakes_are_load_bearing` is
that sentence made checkable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from pymorphy3.analyzer import Parse

from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.parts import name_parts
from bench.agentpii4.schema import Ladder, PiiItem, tier
from bench.agentpii5 import contracts, form, metrics, observe
from bench.agentpii5.contracts import (ArmRunV5, CaseV5, Line, MentionRecord, RunObservation,
                                       ToolResultRecord)
from bench.agentpii5.form_tables import NAME_PARTICLES
from bench.agentpii5.metrics import parts_of
from bench.agentpii5.schema import case_v5_from_json
from bench.agentpii5.tools import REGISTRY_V5, expected_leaf_value, spec_v5_for

HERE = pathlib.Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.v5.json"
LADDER_PATH = HERE / "ladder.json"

# The six v4 level lines (`action` … `verbatim`) compare the gateway arm with a
# CONTROL arm and need two `PairVerdict`s, so a single-arm probe cannot measure
# them at all and they carry no metric function here. This tuple is what
# `test_perfect.py` demands a bound for — all of it, and nothing outside it.
SINGLE_ARM_METRICS: tuple[str, ...] = tuple(
    name for name in contracts.METRIC_NAMES if name in metrics.METRIC_FUNCTIONS)


# --- §1 the substitute a right gateway mints ---------------------------------------
#
# Same shape, same notation, same part count, a different lexeme. This is not a
# copy of `pseudex/vault.py` — it is the PROMISE that code makes, written out
# offline, and each rule below exists because breaking it made the simulation
# invent a gateway defect that only belonged to the simulation.

_CYR_MAP = str.maketrans(
    "абвгдежзийклмнопрстуфхцчшщъыьэюя",
    "оевзыджлнпрбткмафухчцшщъисьэюягд")
_LAT_MAP = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ovezydjlnpbrtkmafuhcwsxqig")

# The generic vocabulary an address wears. `pseudex` replaces the street NAME
# and leaves «улица», «кв», «переулок» standing, and `observe.GENERIC_ROLES`
# exempts them from the needles; a mint that mangled them would hand the
# splitter a string with no markers and invent a miss.
_GENERIC_TOKENS = frozenset((
    "улица", "ул", "проспект", "пр", "пркт", "переулок", "пер", "шоссе", "ш",
    "бульвар", "б", "бул", "проезд", "площадь", "пл", "набережная", "наб",
    "тупик", "аллея", "линия", "квартал", "микрорайон", "мкр", "дом", "д",
    "корпус", "корп", "к", "строение", "стр", "квартира", "кв", "офис", "оф",
    "подъезд", "этаж", "литера", "лит", "город", "г", "гор", "село", "с",
    "посёлок", "поселок", "пос", "п", "деревня", "дер", "область", "обл",
    "район", "р", "рн", "край", "республика", "респ"))

_DIGIT_TYPES: tuple[str, ...] = ("PHONE", "CARD", "SNILS", "INN", "PASSPORT", "OGRN", "PLATE")
_DATE_TYPES: tuple[str, ...] = ("DOB", "DATE")
# The address roles, in the order a written Russian address states them.
_ROLE_ORDER: tuple[str, ...] = ("city", "street_type", "street", "house", "flat")
_NAME_ROLES: tuple[str, ...] = ("surname", "given", "patronymic")
# The roles whose disappearance from a minted surface means the substitute can
# no longer be SPLIT the way the real value is — and then every role-aware
# needle stops finding it, for reasons that belong to this file.
_SPLIT_ROLES: tuple[str, ...] = ("street", "surname", "given", "patronymic")
_WORD = re.compile(r"[^\W\d_]+|\d+|\W+|_", re.UNICODE)


# --- §1bis the NAME pool: a substitute has to be a WORD -------------------------------
#
# WHY THE LETTER-MANGLED FAKE BELOW IS NOT ENOUGH FOR A NAME. `_fake_word`
# writes «удфгей» for «сергей»: same length, same script, same case class, and
# in no dictionary anywhere. pymorphy3 answers about such a string by GUESSING
# from its ending, `form._word_readings` refuses a guess (`parse.is_known`),
# and so NAME.gram_case — the most expensive feature spec §8.4 names — printed
# `unknown` on EVERY name this probe minted: 6 200 of 6 200 substitutes
# measured silent, against 93 of 6 200 real values. «A right gateway takes
# form_hOUT whole» was therefore earned with that feature switched off, and a
# gateway that answers a case of its own choosing walked free.
# `test_perfect.test_readable_fakes_are_load_bearing` reverts this section and
# shows exactly that.
#
# WHAT THE ENGINE DOES, AND SO DOES THIS. `pseudex/vault.py` mints a name out
# of the leased gazetteer — a real surname, a real given name, of the same
# gender (`docs/tz-name-gender-canonical.md`) — and inflects it into the form
# the customer wrote. The pool below is that promise written out offline: real
# lexemes pymorphy3 knows, DISJOINT from every name the corpus uses, so a
# substitute can never be read as the value it replaces.

# ONE analyzer for the process, and it is the comparator's own. pymorphy3 loads
# its dictionary from disk; a second instance here would load it twice to
# answer the same questions `form` asks, and a mint read by one analyzer and
# compared by another is two readings of one word.
_ANALYZER = form._ANALYZER

# Masculine surnames. The feminine ones are these plus «а» — a rule of the
# language, not a second table that has to be kept in step with the first.
#
# THREE RULES EVERY ENTRY OBEYS, and each one was written by a number the probe
# printed while it was broken. `test_perfect.test_pool_is_fit_to_mint_from`
# checks all three entry by entry, so a rebuilt corpus says which word to drop
# instead of leaving a reader to work it out from a coverage of 0.9975.
#
#  * IT SHARES NO STEM WITH A NAME OF THE CORPUS, in either direction. A NAME
#    needle is a four-letter STEM (`observe.value_needles`), so the given name
#    «Тарас» in a masked tool result answers the leak needle of the surname
#    «Тарасова», and the probe reports a leak the gateway never committed —
#    measured: coverage 2023/2028, toolresult_masked 313/317, doc_masked 15/17.
#    «Виктория» against «Викторовна» is the same collision.
#  * IT OCCURS IN NO VALUE OF THE CORPUS, in any of its six forms. «Лев» sits
#    inside «поЛЕВая» and «Панов» inside «стеПАНОВич», and a `whole` needle is
#    a substring search: `residual` then reports a substitute reaching the
#    customer out of a street the gateway restored correctly.
#  * ITS FIRST FOUR LETTERS DO NOT MOVE WHEN IT IS INFLECTED. The stem needle
#    is those four letters, so «Зоя» read by the model and «Зою» written into
#    the tool are two values as far as every needle is concerned, and the hop
#    reads `unmasked`. That rules out everything under five letters, and
#    «Павел», whose vowel is fleeting (павел → павла).
_SURNAME_STEMS: tuple[str, ...] = (
    "мельников", "титов", "гусев", "зайцев", "комаров", "рябов", "шилов", "щукин",
    "голубев", "дроздов", "селезнев", "тетерин", "бобров", "куликов", "журавлев",
    "сорокин", "скворцов", "чижов", "грачев", "филатов", "карпов", "ершов",
    "окунев", "линев", "бычков", "барсуков", "волков", "киселев", "макаров",
    "ковалев", "ильин", "гуляев", "пономарев")
# Given names of BOTH readings the splitters know: ones a surname regex does
# not touch («антон») and ones it does («юрий», «арина» — «-ий», «-ин»). Both
# have to be here, because the pick must read the way the word it replaces
# reads, and «Аркадий» reads as surname-shaped to `form` while «Иван» does not.
_GIVEN_M: tuple[str, ...] = (
    "антон", "вадим", "даниил", "денис", "матвей", "никита", "роман", "тимофей",
    "филипп", "ярослав", "макар", "мирон", "прохор", "тихон", "назар", "трофим",
    "родион", "елисей", "платон", "всеволод", "геннадий", "георгий", "григорий")
_GIVEN_F: tuple[str, ...] = (
    "дарья", "диана", "ксения", "надежда", "оксана", "раиса", "татьяна", "варвара",
    "вероника", "елизавета", "жанна", "клавдия", "лариса", "маргарита", "алиса",
    "анастасия", "ульяна", "алина", "ангелина", "антонина", "галина", "екатерина",
    "карина", "кристина", "регина", "альбина")
_PATRONYMIC_M: tuple[str, ...] = (
    "антонович", "глебович", "егорович", "денисович", "романович", "матвеевич",
    "тимофеевич", "филиппович", "вадимович", "маркович", "назарович", "платонович",
    "макарович", "прохорович", "родионович", "трофимович", "ильич")
_PATRONYMIC_F: tuple[str, ...] = (
    "антоновна", "глебовна", "егоровна", "денисовна", "романовна", "матвеевна",
    "тимофеевна", "филипповна", "вадимовна", "марковна", "назаровна", "платоновна",
    "макаровна", "прохоровна", "родионовна", "трофимовна", "ильинична")

_POOL: dict[tuple[str, str], tuple[str, ...]] = {
    ("surname", "m"): _SURNAME_STEMS,
    ("surname", "f"): tuple(stem + "а" for stem in _SURNAME_STEMS),
    ("given", "m"): _GIVEN_M,
    ("given", "f"): _GIVEN_F,
    ("patronymic", "m"): _PATRONYMIC_M,
    ("patronymic", "f"): _PATRONYMIC_F,
}

# The word a lone candidate is read BESIDE. Both readers of a name read a
# PHRASE — `form.name_order` has nothing to say about one word except
# «single», and `parts.name_parts` lets the neighbour decide — so the only way
# to ask them what ONE word carries is to stand the same second word after the
# candidate and after the original. A surname that is in neither the pool nor
# the corpus, so the anchor can never be confused with what it anchors.
_ROLE_ANCHOR: str = "ефремов"


def _role_of(word: str) -> str:
    """surname / given / patronymic, read by the instrument's OWN splitter.

    Not by pymorphy3, although it is right here: the readers that will meet
    this substitute are `parts.name_parts` — which every leak and round-trip
    needle goes through — and `form.name_order`. A fake whose role only the
    ANALYSER agrees about would be split differently from the value it
    replaces, and the probe would be charging the gateway for its own mint.
    """
    return next(iter(name_parts(word)), "")


def _reads_alike(candidate: str, word: str) -> bool:
    """Do the two words carry the same role for BOTH readers of a name."""
    return (_role_of(candidate) == _role_of(word)
            and form.name_order(f"{candidate} {_ROLE_ANCHOR}")
            == form.name_order(f"{word} {_ROLE_ANCHOR}"))


def _known_name_parses(word: str) -> list[Parse]:
    """The parses pymorphy3 KNOWS for this word, a personal-name reading first.

    `is_known` is the whole point. The analyser answers about an unknown string
    by predicting from its ending, out of a table that does not contain the
    word, and `form._word_readings` refuses that prediction on the comparator's
    side. Minting against a reading the comparator will never accept is minting
    against nothing.
    """
    parses = [parse for parse in _ANALYZER.parse(word)
              if parse.is_known and parse.tag.case is not None]
    named = [parse for parse in parses
             if any(tag in parse.tag for tag in ("Surn", "Name", "Patr"))]
    return named or parses


def _surface_parse(word: str, gender: str) -> Parse | None:
    """What form the word the CUSTOMER wrote is in, read under the gender the
    CORPUS says the person has.

    The gender is evidence and the analyser has none: «Громова» is the feminine
    surname in the nominative and the masculine one in the genitive, and the
    top parse is the second. Read that way, the substitute was inflected into a
    genitive nobody wrote, stopped reading as a surname, and fell back to the
    letter-mangled fake for every entry of the pool — 3 612 of the corpus's
    surnames are feminine and all of them are spelled like a masculine
    genitive.
    """
    parses = _known_name_parses(word)
    if gender:
        same = [parse for parse in parses
                if parse.tag.gender is not None and str(parse.tag.gender) == gender]
        parses = same or parses
    return parses[0] if parses else None


def _lexeme_parse(word: str) -> Parse | None:
    """The NOMINATIVE reading of a pool lexeme, and it has to be asked for.

    Every string this is handed is a nominative — an entry of `_POOL`, or the
    canonical mint built out of them — but the analyser does not know that, and
    it reads «Мельникова» as the FEMININE nominative and the MASCULINE genitive
    with equal confidence. Taking its top parse put a feminine surname into the
    masculine lexeme's genitive and handed «Ворониной» the form «Мельникова»:
    a gender the substitute never had, in a case the customer never wrote.
    """
    parses = _known_name_parses(word)
    nominative = [parse for parse in parses if str(parse.tag.case) == "nomn"]
    chosen = nominative or parses
    return chosen[0] if chosen else None


def _worn_case(word: str, like: str) -> str:
    """`word` capitalised the way `like` is — the substitute must not move
    NAME.case_class, which is a feature of its own."""
    letters = [char for char in like if char.isalpha()]
    if not letters:
        return word
    if len(letters) > 1 and all(char.isupper() for char in letters):
        return word.upper()
    return word[:1].upper() + word[1:] if letters[0].isupper() else word


def gram_gender(gender: str) -> str:
    """The corpus's «m» / «f» as the grammeme pymorphy3 prints. "" for a type
    that carries no gender at all — an address has none."""
    return {"m": "masc", "f": "femn"}.get(gender, "")


def worn_by_morphology(fake: str, surface: str, gender: str) -> str:
    """`fake` — a pool lexeme — in the grammatical form `surface` wears.

    The fake is read as the NOMINATIVE it is (`_lexeme_parse`) and the surface
    as whatever the customer wrote (`_surface_parse`); the case, and the number
    when the surface names one, cross over. Nothing else does — the gender is
    the pool entry's own, because the bucket it came from was chosen by the
    item's gender.

    "" when pymorphy3 knows neither side, or when the lexeme has no such form.
    The caller then keeps the shared-prefix rule and the feature abstains,
    exactly as it did before this pool existed.
    """
    read = _surface_parse(surface, gram_gender(gender))
    if read is None:
        return ""
    lexeme = _lexeme_parse(fake)
    if lexeme is None:
        return ""
    grammemes = {str(read.tag.case)}
    if read.tag.number is not None:
        grammemes.add(str(read.tag.number))
    worn = lexeme.inflect(grammemes)
    return "" if worn is None else _worn_case(worn.word, surface)


def role_in(word: str, parts: dict[str, str]) -> str:
    """The role this word plays IN THE VALUE IT BELONGS TO — the corpus's own
    answer where it has one, the shape reading where it has not.

    A WORD ALONE DOES NOT CARRY ITS ROLE, and reading it alone cost two items
    of one person the same fake. `name_parts("миллер")` answers `given`,
    because a lone word that wears no surname suffix is a given name; inside
    «миллер валерий» the very same splitter answers `surname`, because the
    OTHER word is the given one. Bucketed by the lone reading, «миллер» and
    «валерий» drew from one pool and collided on «геннадий геннадий» — one
    person written as one word twice, which `parts` then counts as a form the
    gateway changed (measured: form_hOUT 2802/2812 on medium, four cases).
    `parts` is what the corpus BUILT the value from, so it is the answer, and
    the shape reading is what is left for a surface no part spells — an
    inflected mention, which `worn_like` overwrites anyway.
    """
    folded = _fold(word)
    for role in _NAME_ROLES:
        if parts.get(role) and _fold(parts[role]) == folded:
            return role
    return _role_of(word)


def pool_pick(word: str, gender: str, role: str, taken: frozenset[str]) -> tuple[str, str]:
    """(the pool lexeme this word takes, that lexeme in the word's own form) —
    or ("", "") when the pool holds nothing that READS the way this word reads:
    a foreign surname, a particle, an initial, a word pymorphy3 does not know.
    The caller then keeps the letter-mangled fake and `gram_case` abstains, as
    it did for every name before this pool existed.

    A SINGLE LETTER IS NEVER A LEXEME. «П.» is an initial and «m» is the note
    the corpus keeps a name's gender in; expanding either into a full name
    would move NAME.initials and invent parts nobody wrote.

    THE NEAREST LENGTH WINS, and that is §1's promise («same shape, a different
    lexeme») applied to a pool instead of a letter map. `_fake_word` preserved
    the length exactly and the answer aligner never had to guess; a five-letter
    fake for an eight-letter name lets `difflib` slide a sentence boundary and
    hand ONE item's window two data («букин — записано. Пункт 2: новиков»).

    `taken` is the four-letter STEMS `name_pool_map` has already spent in this
    conversation; see there for why the assignment cannot be a function of the
    word alone, and why it is spent by stem rather than by word.
    """
    if len(word) < 2 or word.casefold() in NAME_PARTICLES:
        return "", ""
    pool = [one for one in _POOL.get((role, gender), ()) if _stem(one) not in taken]
    if not pool:
        return "", ""
    start = int.from_bytes(
        hashlib.blake2s(word.casefold().encode("utf-8"), digest_size=4).digest(),
        "big") % len(pool)
    rotated = [pool[(start + step) % len(pool)] for step in range(len(pool))]
    for candidate in sorted(rotated, key=lambda one: abs(len(one) - len(word))):
        worn = worn_by_morphology(candidate, word.casefold(), gender)
        if worn and _reads_alike(worn, word.casefold()):
            return candidate, worn
    return "", ""


def name_pool_map(items: Sequence[PiiItem]) -> dict[str, str]:
    """Every NAME word of ONE conversation and the fake it wears, lower case.

    WHY THE ASSIGNMENT BELONGS TO THE CONVERSATION AND NOT TO THE WORD. A pool
    is finite, so a pick keyed on the word alone is a hash, and a hash
    collides: «Соколова» and «Воронина» — the customer of `rag-035` and a
    stranger in a retrieved chunk — both drew «Макарова», and
    `rag_identity_kept` read exactly what its own words describe, «the
    gateway deciding two people are one». No local rule can see that coming;
    an assignment that walks the conversation's items in order and never
    spends an entry twice cannot produce it at all. It is also what
    `pseudex/vault.py` does — one substitute per canonical, guarded against
    collision at mint time — so the simulation is closer to the product for
    the same change.

    SPENT BY STEM, NOT BY WORD, because a needle is a stem. «Новиков Игорь»
    drew «Макаров Макар» — two entries, two lexemes, one four-letter stem —
    and the answer aligner, narrowing the raw side by the substitute's
    needles, could not tell which of the two words was the given name: one
    corpus hop of 15 796, and the only one left on `form_hOUT`.

    The key is the word AS WRITTEN, which is correction 1's whole premise:
    «пётр» and «петра» are two keys and draw two lexemes, so a probe that
    mints the surface and the canonical independently hands the model one fake
    and the tool another. `worn_like` is what reconciles them.
    """
    spent: set[str] = set()
    out: dict[str, str] = {}
    for item in items:
        if item.type != "NAME":
            continue
        gender = item.parts.get("gender", "")
        for text in (item.canonical, item.value, *item.parts.values()):
            for token in _WORD.findall(text):
                key = token.casefold()
                if not token.isalpha() or key in out:
                    continue
                role = role_in(token, item.parts)
                lexeme, worn = pool_pick(token, gender, role, frozenset(spent))
                if not lexeme:
                    continue
                spent.add(_stem(lexeme))
                out[key] = worn
    return out


def _keep_tail(word: str) -> int:
    """How many trailing characters a fake KEEPS.

    A Russian role is read off the suffix — «-ович» a patronymic, «-ова» a
    surname, «-ой» the dative — and `metrics.parts_of` and the grammatical-case
    reading both work from it. A fake that mangles the ending is not a fake of
    the same shape: it is a word of no shape at all.
    """
    if len(word) >= 7:
        return 4
    if len(word) >= 5:
        return 3
    return 0


def _fake_word(word: str) -> str:
    """Same length, same script, same case class, different letters."""
    out: list[str] = []
    for char in word:
        if not char.isalpha():
            out.append(char)
            continue
        low = char.lower()
        if "а" <= low <= "я" or low == "ё":
            new = low.translate(_CYR_MAP)
        elif "a" <= low <= "z":
            new = low.translate(_LAT_MAP)
        else:
            new = low
        out.append(new.upper() if char.isupper() else new)
    return "".join(out)


def _fake_stem(word: str) -> str:
    """A different lexeme wearing the SAME ending."""
    tail = _keep_tail(word)
    return _fake_word(word) if not tail else _fake_word(word[:-tail]) + word[-tail:]


def _shift_digits(text: str, by: int) -> str:
    return "".join(str((int(c) + by) % 10) if c.isdigit() else c for c in text)


def _fake_digits(text: str, pii_type: str) -> str:
    """Shift every digit, keep the separators — and keep the COUNTRY digit of
    an eleven-digit phone, so the substitute's canonical, its surface and its
    `digits` part all carry ONE digit signature. Minting them independently is
    how a simulation invents a gateway defect that is only its own bookkeeping.
    """
    positions = [i for i, char in enumerate(text) if char.isdigit()]
    keep = set()
    if pii_type == "PHONE" and len(positions) == 11 and text[positions[0]] in "78":
        keep.add(positions[0])
    return "".join(char if (not char.isdigit() or i in keep) else str((int(char) + 3) % 10)
                   for i, char in enumerate(text))


def _fake_date(text: str) -> str:
    """Shift the DAY by +1 inside 1..28 and the YEAR by +1: a fake date that is
    still a date, so every notation of it folds the way the real one does."""
    def day(match: re.Match[str]) -> str:
        return f"{(int(match.group(0)) % 28) + 1:0{len(match.group(0))}d}"

    def year(match: re.Match[str]) -> str:
        return str(int(match.group(0)) + 1)

    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text.strip())
    if iso:
        return f"{int(iso.group(1)) + 1:04d}-{iso.group(2)}-{(int(iso.group(3)) % 28) + 1:02d}"
    return re.sub(r"^\s*\d{1,2}(?=[.\-/ ])", day,
                  re.sub(r"\b(19|20)\d{2}\b", year, text))


def _fake_words(text: str) -> str:
    """NAME, LOC and anything else: word for word, digits shifted, generic
    words left standing."""
    out: list[str] = []
    for token in _WORD.findall(text):
        if token.isalpha():
            out.append(token if token.casefold() in _GENERIC_TOKENS else _fake_stem(token))
        elif token.isdigit():
            out.append(_shift_digits(token, 3))
        else:
            out.append(token)
    return "".join(out)


def _fake_name_words(text: str, fakes: dict[str, str]) -> str:
    """A NAME, word for word, out of the conversation's pool assignment — and
    out of `_fake_stem` for a word the pool could not mirror, which is where
    `gram_case` keeps abstaining."""
    out: list[str] = []
    for token in _WORD.findall(text):
        if token.isalpha():
            fake = fakes.get(token.casefold(), "")
            out.append(_worn_case(fake, token) if fake else _fake_stem(token))
        elif token.isdigit():
            out.append(_shift_digits(token, 3))
        else:
            out.append(token)
    return "".join(out)


def mint(pii_type: str, surface: str, canonical: str, parts: dict[str, str],
         fakes: dict[str, str]) -> tuple[str, str, dict[str, str]]:
    """(substitute surface, substitute canonical, substitute parts). `fakes` is
    the conversation's NAME assignment (`name_pool_map`) and nothing else reads
    it."""
    if pii_type in _DATE_TYPES:
        return (_fake_date(surface), _fake_date(canonical),
                {role: _fake_date(value) for role, value in parts.items()})
    if pii_type in _DIGIT_TYPES:
        return (_fake_digits(surface, pii_type), _fake_digits(canonical, pii_type),
                {role: (_fake_digits(value, pii_type) if any(c.isdigit() for c in value)
                        else _fake_word(value))
                 for role, value in parts.items()})
    if pii_type == "NAME":
        # THE GENDER IS THE ITEM'S, NOT THE WORD'S. «Иванова» is the feminine
        # surname and the masculine genitive at once, so a mint reading the
        # gender off each word would hand ONE person a masculine surname and a
        # feminine patronymic. `parts["gender"]` is what the corpus BUILT the
        # value from, and it is the same for every word of it. The `gender`
        # part itself is a one-letter note, which `pool_pick` refuses, so it
        # keeps travelling through `_fake_stem` as it always did.
        return (_fake_name_words(surface, fakes), _fake_name_words(canonical, fakes),
                {role: _fake_name_words(value, fakes) for role, value in parts.items()})
    if pii_type == "EMAIL":
        # WHAT THE PRODUCT ACTUALLY MINTS (`pseudex/vault.py`): eight letters at
        # `example.ru`. Keeping the customer's domain would leave «yandex.ru»
        # standing in the masked text, and `pieces_of` counts a domain as a
        # piece of the value — a simulation that kept it would report a leak
        # the gateway does not commit.
        local = "".join(_fake_word(char) for char in (canonical.partition("@")[0] + "abcdefgh")[:8])
        return local + "@example.ru", local + "@example.ru", {"local": local,
                                                              "domain": "example.ru"}
    return (_fake_words(surface), _fake_words(canonical),
            {role: _fake_words(value) for role, value in parts.items()})


@dataclass(frozen=True)
class Substitute:
    """The minted fake, shaped like a `PiiItem` so that `expected_leaf_value`
    reads its parts the way it reads the real one. One per identity, for the
    whole conversation — which is what `consistency` and `stability` ask."""

    id: str
    type: str
    identity: str
    value: str
    canonical: str
    parts: dict[str, str] = field(default_factory=dict)


# --- §2 the three corrections that ARE the specification ----------------------------


def _fold(word: str) -> str:
    return word.lower().replace("ё", "е")


def _stem(word: str) -> str:
    """The four folded letters a NAME needle is made of (`observe.value_
    needles`). Two words with one stem are one value to every needle."""
    return _fold(word)[:4]


def worn_like(fake_canonical: str, real_canonical: str, real_surface: str,
              gender: str) -> str:
    """CORRECTION 1 — ONE MINT PER ITEM, WORN IN THE SURFACE'S GRAMMATICAL FORM.

    A right gateway mints ONE substitute per identity and INFLECTS it; the
    model reads «аёхфу» where the customer wrote «петру», and the SAME lexeme
    «аёхф» comes back in the argument.

    WHAT IT COST WHEN IT WAS WRONG. Minting twice — once from the surface, once
    from the canonical — looks harmless and is not: `_keep_tail` reads the
    ending off the word's LENGTH, so «пётр» (4) and «петра» (5) fall in
    different classes and come back as two UNRELATED fakes — «аёхф» and
    «адтра», which this file still prints if you ask it. The fake the model
    read then shares no stem with the fake in the argument, `carries_any` says
    the leaf holds no substitute, and the hop reads `unmasked`: the probe
    charging the gateway for its own bookkeeping. MEASURED, with this reverted:
    twelve leaves off `round_trip` and off `end_to_end`, twelve turns off
    `multi_all_out` over the whole corpus (three of each on the acceptance
    tier — `test_perfect.test_correction_one_is_load_bearing`).

    So: take the ONE minted canonical and wear the surface's form. Word counts
    must line up; when they do not the caller keeps the plain mint ("" is
    returned).

    TWO WAYS TO WEAR A FORM, AND THE FIRST ONE IS THE REAL ONE. A pool lexeme
    is a WORD — «антон» has a dative and pymorphy3 writes it — so the
    substitute the model reads is a form of a word, which is the only kind of
    string `form.name_gram_case_same` can read a case off (§1bis). A word the
    pool could not mirror has no dative anywhere, so it keeps the shared-prefix
    rule: the prefix the real canonical and the real surface share is taken
    from the FAKE, and the rest of the ending from the SURFACE.
    """
    fakes = _WORD.findall(fake_canonical)
    reals = _WORD.findall(real_canonical)
    surfaces = _WORD.findall(real_surface)
    if not len(fakes) == len(reals) == len(surfaces):
        return ""
    out: list[str] = []
    for fake, real, surface in zip(fakes, reals, surfaces):
        if not fake.isalpha():
            out.append(surface)
            continue
        worn = worn_by_morphology(fake, surface, gender)
        if worn:
            out.append(worn)
            continue
        common = 0
        for left, right in zip(_fold(real), _fold(surface)):
            if left != right:
                break
            common += 1
        out.append(fake[:common] + surface[common:])
    return "".join(out)


def compose_free_leaf(values: Sequence[str]) -> str:
    """CORRECTION 2 — ONE SENTENCE PER FREE-TEXT LEAF, CARRYING EVERY HOP THAT
    LEAF DECLARES.

    `escalate_to_human.summary` is handed a NAME, a PHONE and a LOC. A free
    leaf is prose: a right agent writes all three into it, and a right gateway
    restores all three.

    WHAT IT COST WHEN IT WAS WRONG. Writing ONE value per leaf path kept only
    the LAST hop of such a leaf, and the other hops read as values the gateway
    dropped. 135 of the corpus's 928 chain transitions land on a shared free
    leaf (`notify_sms.text` 75, `escalate_to_human.summary` 36,
    `ticket_create.text` 24) and that is exactly where `chain_value`'s 36
    misses came from over the whole corpus — a probe artifact that would have
    sent us fixing a gateway that is not broken. FIX-4's per-transition
    measurement composed the prose properly and found 0 of 210 free-leaf
    transitions unhittable. (`test_perfect.test_correction_two_is_load_bearing`)
    """
    kept = [value for value in values if value]
    if not kept:
        return ""
    if len(kept) == 1:
        return kept[0]
    return "Клиент " + ", ".join(kept) + "."


def request_of_message(index: int) -> int:
    """CORRECTION 3 — `request_index` IS COUNTED PER PUSH, as `GatewayV5._push`
    counts it: one per message the gateway hands the model, system prompt
    excluded.

    WHAT IT COST WHEN IT WAS WRONG. A message and the tool result of the same
    TURN are two model requests. Numbering both by the turn collapses them, and
    then `stability` — «the substitute did not change BETWEEN requests» — sees
    one request per item, drops every item out of its denominator and prints
    0/0. A line that cannot fire certifies nothing.
    (`test_perfect.test_correction_three_is_load_bearing`)
    """
    return index + 1


def request_of_result(message_count: int, seq: int) -> int:
    """The other half of correction 3: a result is pushed AFTER the turn's
    message, so it rides a LATER request than the message that provoked it."""
    return message_count + seq + 1


# --- §3 the run a right gateway and a right agent leave behind ----------------------


def unflatten(flat: dict[str, str]) -> dict[str, object]:
    """Dotted leaf paths back into the nested argument object a tool receives."""
    out: dict[str, object] = {}
    for path, value in flat.items():
        node = out
        parts = path.split(".")
        for key in parts[:-1]:
            node = node.setdefault(key, {})       # type: ignore[assignment]
        node[parts[-1]] = value
    return out


def _leaf_pair(item: PiiItem, substitute: Substitute, tool: str, path: str) -> tuple[str, str]:
    """(what the agent WROTE — the substitute in the leaf's own notation,
    what the gateway RESTORED — the real value in the same notation)."""
    spec = spec_v5_for(tool, path) if tool in REGISTRY_V5 else None
    if spec is None:
        return substitute.canonical or substitute.value, item.canonical or item.value
    return expected_leaf_value(substitute, spec), expected_leaf_value(item, spec)


def _lost_roles(item: PiiItem, surface: str) -> bool:
    """Does the minted surface still SPLIT into the roles the item declares?"""
    got = parts_of(item.type, surface)
    return any(item.parts.get(role) and role not in got for role in _SPLIT_ROLES)


def _address_from_parts(parts: dict[str, str]) -> str:
    bits: list[str] = []
    for role in _ROLE_ORDER:
        value = parts.get(role)
        if value:
            bits.append("кв " + value if role == "flat" else value)
    return " ".join(bits)


def _substitute_for(item: PiiItem, fakes: dict[str, str]) -> Substitute:
    """The one fake this item wears everywhere it is mentioned."""
    # A DICTATED value is replaced by a WRITTEN fake. `pseudex.vault` mints
    # `_fake_phone()` / `_fake_snils()` whatever the surface was; `looks_dictated`
    # decides only what is RESTORED to the tool, never what the model is shown.
    # Minting a spoken-shaped substitute here would simulate a product that
    # does not exist — and it is why `form_hIN` cannot be 100 % for a right
    # gateway (docs/known-issues.md Б27).
    written = item.canonical if item.spoken else item.value
    surface, canonical, parts = mint(item.type, written, item.canonical,
                                     dict(item.parts), fakes)
    if item.type in ("NAME", "LOC") and not item.spoken and written != item.canonical:
        worn = worn_like(canonical, item.canonical, written, item.parts.get("gender", ""))
        if worn:
            surface = worn
    # A DICTATED ADDRESS is replaced by a WRITTEN one. «садовая сорок шесть
    # квартира семьдесят девять» is the item's canonical, and mangling it word
    # by word leaves a string `metrics.parts_of` cannot split — so the
    # substitute would carry no street needle for reasons belonging to this
    # simulation. The engine mints a written fake; so does this.
    if item.type == "LOC" and _lost_roles(item, surface):
        surface = canonical = _address_from_parts(parts)
    if item.type == "NAME" and _lost_roles(item, surface):
        surface = canonical = " ".join(parts[role] for role in _NAME_ROLES if parts.get(role))
    return Substitute(id=item.id, type=item.type, identity=item.identity,
                      value=surface, canonical=canonical, parts=parts)


def _masked_messages(case: CaseV5, subs: dict[str, Substitute]
                     ) -> tuple[dict[int, tuple[tuple[int, int], ...]], list[MentionRecord]]:
    """Every message the conversation pushed: the spans the gateway replaced,
    and what the model read in each of them."""
    masked: dict[int, tuple[tuple[int, int], ...]] = {}
    mentions: list[MentionRecord] = []
    for index, _message in enumerate(case.base.messages):
        spans: list[tuple[int, int]] = []
        for item in case.base.pii:
            if item.where.kind == "message" and item.where.msg == index:
                spans.append((item.where.start, item.where.end))
                mentions.append(MentionRecord(item_id=item.id, msg=index, result_seq=-1,
                                              substitute=subs[item.id].value,
                                              request_index=request_of_message(index)))
        masked[index] = tuple(sorted(spans))
    return masked, mentions


def _tool_results(case: CaseV5, items: dict[str, PiiItem], subs: dict[str, Substitute]
                  ) -> tuple[list[ToolResultRecord], list[MentionRecord]]:
    """The tool results the case declares, rendered real and masked.

    `ToolResultRecord.pieces` are the gateway's replaced spans in `text_real`
    coordinates (`observe.covering_piece` compares them with `spans_real`),
    each with the substitute that slot got and the type the gateway assigned.
    """
    by_result: dict[tuple[int, str, int], list[str]] = {}
    for hop in case.hops:
        if hop.kind == "IN" and hop.owner in ("tool", "document"):
            by_result.setdefault((hop.turn, hop.tool_name, hop.call_ordinal), []).append(hop.item_id)
    declared = {(ret.tool_name, ret.call_ordinal): ret for ret in case.returns}
    records: list[ToolResultRecord] = []
    mentions: list[MentionRecord] = []
    for seq, ((turn, tool, ordinal), read_ids) in enumerate(sorted(by_result.items())):
        # EVERY DECLARED item of this result, even one no hop reads: a value the
        # result renders and nobody consumes still reaches the model.
        ret = declared.get((tool, ordinal))
        ids = list(dict.fromkeys(read_ids + list(ret.result_item_ids if ret else ())))
        real_parts: list[str] = []
        masked_parts: list[str] = []
        spans_real: dict[str, tuple[int, int]] = {}
        pieces: list[tuple[int, int, str, str]] = []
        for item_id in ids:
            item = items.get(item_id)
            if item is None:
                continue
            fake = subs[item_id]
            prefix = f"{item_id}: " if real_parts else ""
            start_real = sum(len(part) for part in real_parts) + len(prefix)
            real_parts.append(prefix + item.canonical + "\n")
            masked_parts.append(prefix + fake.canonical + "\n")
            spans_real[item_id] = (start_real, start_real + len(item.canonical))
            pieces.append((start_real, start_real + len(item.canonical), fake.canonical, item.type))
        records.append(ToolResultRecord(
            tool_name=tool, seq=seq, call_ordinal=ordinal, turn=turn,
            return_form=(ret.return_form if ret else "flat_json"),
            text_real="".join(real_parts), text_masked="".join(masked_parts),
            spans_real=spans_real, pieces=tuple(pieces), forced=False))
        for item_id in spans_real:
            mentions.append(MentionRecord(
                item_id=item_id, msg=-1, result_seq=seq, substitute=subs[item_id].canonical,
                request_index=request_of_result(len(case.base.messages), seq)))
    return records, mentions


def _calls(case: CaseV5, items: dict[str, PiiItem], subs: dict[str, Substitute]
           ) -> tuple[list[ObservedCall], list[int]]:
    """The tool calls the case declares, each leaf holding what the agent wrote
    and what the gateway restored."""
    by_call: dict[tuple[int, str, int], list[contracts.Hop]] = {}
    for hop in case.hops:
        if hop.kind == "OUT" and hop.owner in contracts.ACTING_OUT_OWNERS and hop.tool_name:
            by_call.setdefault((hop.turn, hop.tool_name, hop.call_ordinal), []).append(hop)
    calls: list[ObservedCall] = []
    turns: list[int] = []
    for (turn, tool, ordinal), hops in sorted(by_call.items()):
        written: dict[str, str] = {}
        restored: dict[str, str] = {}
        by_path: dict[str, list[contracts.Hop]] = {}
        for hop in hops:
            by_path.setdefault(hop.path, []).append(hop)
        for path, path_hops in by_path.items():
            pairs = [_leaf_pair(items[hop.item_id], subs[hop.item_id], tool, hop.path)
                     for hop in path_hops if hop.item_id in items]
            if not pairs:
                continue
            spec = spec_v5_for(tool, path) if tool in REGISTRY_V5 else None
            if len(pairs) > 1 and spec is not None and spec.kind == "free":
                written[path] = compose_free_leaf([one for one, _other in pairs])
                restored[path] = compose_free_leaf([other for _one, other in pairs])
            else:
                # A single hop, or a NON-free leaf carrying two: the second is a
                # corpus shape no agent can honour — one slot, one value — and
                # the last hop wins, as it does in the record of a live run.
                written[path], restored[path] = pairs[-1]
        calls.append(ObservedCall(name=tool, written=unflatten(written),
                                  restored=unflatten(restored), residual={},
                                  refusal_path="", refusal_rule="", parsed=None, seq=len(calls)))
        turns.append(turn)
    return calls, turns


def _answer(case: CaseV5, items: dict[str, PiiItem], subs: dict[str, Substitute]
            ) -> tuple[str, str]:
    """(the reply as the model wrote it — substitutes still in it,
    the reply as the customer reads it — real values restored).

    EACH DATUM IN ITS OWN SENTENCE, with unchanged words around it. Two values
    written side by side («Готово. X. Y.») align as ONE `replace` run, land in
    ONE `AttributedSpan`, and `answer_pair` then narrows the region by
    occurrences — which is how a whole phone once came back as «+79037654».
    That was the probe's prose, not the gateway's work.
    """
    raw = ["Готово."]
    real = ["Готово."]
    for number, hop in enumerate(
            [hop for hop in case.hops if hop.kind == "OUT" and hop.owner == "answer"], start=1):
        item = items.get(hop.item_id)
        if item is None:
            continue
        raw.append(f" Пункт {number}: {subs[hop.item_id].value} — записано.")
        real.append(f" Пункт {number}: {item.value} — записано.")
    return "".join(raw), "".join(real)


def simulate(case: CaseV5) -> ArmRunV5:
    """The `ArmRunV5` a right gateway and a right agent leave behind on `case`."""
    items = {item.id: item for item in case.base.pii}
    fakes = name_pool_map(case.base.pii)
    subs = {item.id: _substitute_for(item, fakes) for item in case.base.pii}
    masked_spans, message_mentions = _masked_messages(case, subs)
    results, result_mentions = _tool_results(case, items, subs)
    calls, call_turns = _calls(case, items, subs)
    reply_raw, reply = _answer(case, items, subs)
    base = ArmRun(case_id=case.base.id, arm="I", repeat=0, calls=tuple(calls), state=(),
                  reply=reply, termination="done", cost_usd=0.0,
                  substitutes={item_id: (fake.value, dict(fake.parts))
                               for item_id, fake in subs.items()},
                  masked_spans=masked_spans)
    return ArmRunV5(
        base=base, reply_raw=reply_raw,
        # The control arm writes the same answer; a right gateway does not
        # rewrite the agent's prose, which is what `rewrite_ratio_v5` asks.
        control_reply=reply + " ",
        tool_results=tuple(results), mentions=tuple(message_mentions + result_mentions),
        turn_replies=(reply,), call_turns=tuple(call_turns),
        # Correction 3 again, at the level of the whole run: one request per
        # push, messages and results alike.
        request_count=max(len(case.base.messages) + len(results), 1),
        stream_mismatch=False, reply_whole=reply if case.streaming else "", turn_residual=0)


# --- §4 running it ------------------------------------------------------------------


def load_cases(path: pathlib.Path) -> list[CaseV5]:
    return [case_v5_from_json(row)
            for row in json.loads(path.read_text(encoding="utf-8"))["corpus"]]


def load_ladder(path: pathlib.Path) -> Ladder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ladder(version=int(raw["version"]), seed=int(raw["seed"]),
                  corpus_sha256=str(raw["corpus_sha256"]),
                  tiers={name: tuple(ids) for name, ids in dict(raw["tiers"]).items()})


def cases_of_tier(cases: Sequence[CaseV5], ladder: Ladder, name: str) -> list[CaseV5]:
    """The tier's cases, in corpus order. `max` is every case, so the ladder is
    not consulted and a probe over the whole corpus needs no frozen list."""
    if name == "max":
        return list(cases)
    picked = {one.id for one in tier([case.base for case in cases], ladder, name)}
    return [case for case in cases if case.base.id in picked]


def observations(cases: Sequence[CaseV5]) -> tuple[RunObservation, ...]:
    """One observation per case, through the package's OWN observer.

    No `except` here on purpose: an observer that raises on a record a right
    gateway would leave is a finding, not a case to skip. A probe that skipped
    it would report the metrics of the cases that happened to work.
    """
    return tuple(observe.observe(case, simulate(case), None, None) for case in cases)


def measure(cases: Sequence[CaseV5]) -> dict[str, Line]:
    """Every single-arm metric line over the simulated run."""
    seen = observations(cases)
    return {name: metrics.METRIC_FUNCTIONS[name](seen) for name in SINGLE_ARM_METRICS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", default=str(CORPUS_PATH))
    parser.add_argument("--ladder", default=str(LADDER_PATH))
    parser.add_argument("--tier", default="medium",
                        choices=("nano", "small", "medium", "large", "holdout", "max"))
    args = parser.parse_args()
    cases = cases_of_tier(load_cases(pathlib.Path(args.corpus)),
                          load_ladder(pathlib.Path(args.ladder)), args.tier)
    lines = measure(cases)
    print(f"perfect gateway · tier {args.tier} · {len(cases)} cases\n")
    print(f"{'metric':26s} {'hits':>7s}/{'total':<7s} rate")
    for name in SINGLE_ARM_METRICS:
        line = lines[name]
        print(f"{name:26s} {line.hits:7d}/{line.total:<7d} "
              f"{(line.rate if line.total else 0):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
