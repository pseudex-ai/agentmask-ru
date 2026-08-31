"""Family `transfer` — the customer says a datum, one tool has to receive it.

THE QUESTION: a person states personal data in a message, exactly one call
consumes it, and the only thing asked is whether the REAL value arrived. Nine
other families exist to isolate a mechanism; this one is the base every mechanism
is read against, and it is where names and addresses live in bulk because that is
where the engine's remaining defects are.

WHAT V2 DID HERE AND WHY IT IS NOT REPEATED. v2's version of this family was 450
counter-variants of four sentences — «улица Чехова, дом 29, квартира 66» and
«улица Чехова, дом 43, квартира 46» differ by an increment. Measured over 53 324
human transcripts of Russian phone and dispatch speech, the register those
sentences are written in does not occur: zero utterances carry a digit, zero
carry sentence punctuation, 0.028% start with a capital. The corpus was measuring
one shape many times and calling it coverage.

HOW THE FORM IS OBTAINED HERE, and the split is the whole design:

  * 355 of the 450 cases are `recombined`, and the SHAPE of every one of their
    value-bearing utterances is an entry in `mined/calls_grammar.json` or
    `mined/dispatch_grammar.json`, cited by its exact pattern string. `_shape()`
    refuses an id the mined files do not carry, so «the form came from real
    speech» is checked mechanically rather than asserted — the state 1070 of
    v2's 1334 cases were in. The draw follows the MINED frequency, not a uniform
    one: a lone surname outnumbers ФИО 350 to 23, and flattening that measures
    the rare shape as often as the common one.
  * 70 cases are `verbatim`: the utterance IS a real RuDevices reply and the gold
    span is the hand annotation over that exact string. RuDevices is CC BY 4.0 so
    the text ships. OpenSTT (`speech_calls`) is CC BY-NC and NO text from it
    reaches a message here — only shape names, which are descriptions and not
    speech. `schema.validate` refuses a message carrying non-shippable text, and
    it also refuses one carried by reference, so a CC BY-NC utterance cannot be
    made to pass either way; that is why the verbatim layer is RuDevices only.
  * 25 cases are `template` — a document number in a written channel — and the
    schema permits that only for a type mining cannot reach, so those cases
    carry no person at all: a `template` claiming NAME or LOC is refused,
    because the corpora do hold those two and a template there is laziness.
  * values come from authored pools, never from the leased gazetteer. Overlap
    with it is unavoidable — Russian names are Russian names — but nothing is
    here BECAUSE we detect it. Declensions are written out by hand rather than
    computed: a pool declined by pymorphy3 would hand the corpus the engine's
    own opinion as ground truth.

WHAT THE REGISTER TRANSFORM MAY AND MAY NOT DO. Every surface is built ONCE, in
its target register, before a single offset is counted. There is no pass over a
finished message: stripping punctuation afterwards changes the length and
silently invalidates every span computed before it, and the corpus goes on
scoring. `_compose` is the only place a message string comes into existence and
it returns the offsets it just laid down.

GROUND TRUTH IS WHAT THE GENERATOR BUILT. `PiiItem.value` is the string this
module placed; `canonical` is derived from the PARTS it placed, never by matching
anything against the finished text. Two rules follow and both were bought:

  * a name said in an oblique case canonicalises to the nominative («букину» →
    «букин»), because that is the value a CRM stores and accepting the declined
    form is the leniency that hid «позвоните Игорю» → «Игорю» for a whole
    version. A part the register MUTATED — an ASR slip or a keyboard typo — is
    never «corrected» back: the gateway cannot know the intended word, and a
    ground truth that demands it scores the gateway on information the message
    never carried.
  * a spoken number stays spoken. «школьная пятьдесят девять» must come back as
    itself; demanding «школьная 59» would demand a transliteration nothing in the
    product performs, and `classify_break` already has a name for the gateway
    doing it — `renumbered`.

TWO DEFECTS THIS FAMILY IS BUILT TO EXPRESS, both invisible to any written
corpus because in text a digit is a digit:

  * a house number said as a word. The substitute picker looks for `\\d`, so
    «школьная пятьдесят девять» is handed to the model as a bare settlement name
    and the shape of the string is the only place it shows. `wordnum` isolates
    it; here it simply occurs, at the rate the register produces it.
  * an identifier dictated aloud. libphonenumber and every checksum wait for
    digits, so a phone, a card, a СНИЛС or a passport said in words is found by
    nothing at all. Each rare type therefore gets BOTH forms — the digits a form
    would carry and the words a mouth produces.

NEGATIVES ARE NOT DECORATION. Every case carries at least one, because the
largest false-positive source in this register is measured and known: a number
standing beside «кабинет» or «отделение» occurs 528 times in the call corpus, and
a dictated order number is the defect that shipped once. In the verbatim layer
the negative is a second hand-labelled reply — «не адрес» is a human judgement,
and the trap word inside it is located with a declared vocabulary, not with our
recognizers.

SELECTION IS DECLARED, because the most expensive mistake this project made was
a voice set that admitted an utterance only when it contained «улица» or «дом» —
the very words the engine reads. It reported 100% where the truth was 38.6%. So:
a shape taken from the dispatch marker stratum says `marker`, one from its
random 250-of-4805 layer says `random` and carries weight 19.22, and a shape
mined by reading a whole corpus says `census`. `validate_corpus` refuses a type
whose speech-derived material is marker-only, and this family is the reason that
rule can pass at all for LOC.
"""

import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # running the module directly, as the repo does
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
    case_characters,
    numeral_run,
    unsafe_filler,
    unsafe_outside,
    unsafe_person,
    validate,
)

FAMILY = "transfer"
MODULE = "direct"

# The corpora and the mined grammars. Not in the repository and not in /tmp,
# which is wiped on reboot — NEREL was lost that way twice.
CACHE = Path.home() / ".cache" / "pseudex-bench"
SPEECH = CACHE / "speech_rudevices.jsonl"
LABELS = CACHE / "rudevices_addresses.json"
MINED = Path(__file__).resolve().parent.parent / "mined"

RUDEVICES_LICENCE = "CC BY 4.0"
RUDEVICES_ATTRIBUTION = "SOVA Dataset / RuDevices, распространяется по CC BY 4.0"
# 250 replies read out of the 4805 that carry a number: every share over that
# layer is nineteen times smaller than it looks if this is dropped.
NUMBER_SAMPLE_WEIGHT = 19.22


# --- the mined grammars ---------------------------------------------------
#
# A shape id is checked against the files rather than trusted. A typo in a
# pattern string would make `Provenance.shape` name nothing, and «the form came
# from real speech» would be back to being an assertion.

def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. The mined grammars are built by "
            f"bench/agentpii3/mine_calls.py and mine_dispatch.py; this family "
            f"cannot invent the shapes they carry.")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _known_shapes() -> frozenset[str]:
    """Every pattern string both mined files publish."""
    calls = _read_json(MINED / "calls_grammar.json")
    dispatch = _read_json(MINED / "dispatch_grammar.json")
    names: set[str] = set()
    for entry in calls["shapes"]:                       # type: ignore[index]
        names.add(str(entry["pattern"]))
    for stratum in dispatch["value_shapes"].values():   # type: ignore[union-attr]
        for entry in stratum:
            names.add(str(entry["pattern"]))
    for entry in dispatch["reply_shapes"]:              # type: ignore[index]
        names.add(str(entry["pattern"]))
    for entry in dispatch["name_forms"]["shapes"]:      # type: ignore[index]
        names.add(str(entry["pattern"]))
    return frozenset(names)


SHAPES = _known_shapes()


def _shape(pattern: str) -> str:
    if pattern not in SHAPES:
        raise InvalidCase(
            f"shape {pattern!r} is in neither mined grammar; a `recombined` case "
            f"whose shape names nothing is a template wearing a better label")
    return pattern


# Shapes this module draws on, by the name the mined files give them. Grouped by
# where they were mined, because that is what `selection` has to say.
S_ADDR_ENTRANCE = _shape("<улица> <число прописью> <порядковое> подъезд")
S_ADDR_BARE = _shape("<улица> <число прописью>")
S_ADDR_STREET_WORD = _shape("улица <улица> <число прописью>")
S_ADDR_LETTER = _shape("<улица> <число прописью> <литера>")
S_ADDR_KORPUS = _shape("<улица> <число прописью> корпус <число прописью>")
S_ADDR_LETTER_ENTRANCE = _shape(
    "<улица> <число прописью> <литера> <порядковое> подъезд")
S_ADDR_PROEZD = _shape("проезд <улица> <число прописью>")
S_ADDR_PROSPEKT = _shape("проспект <улица> <число прописью>")
S_ADDR_PEREULOK_DOM = _shape("переулок <улица> дом <число прописью>")
S_ADDR_STREET_DOM = _shape("улица <улица> дом <число прописью>")
S_ADDR_SHOSSE = _shape("<улица> шоссе <число прописью>")
S_ADDR_FLAT = _shape("<улица> <число прописью> квартира <число прописью>")
S_ADDR_STROENIE = _shape("<улица> <число прописью> строение <число прописью>")

S_CALL_NAKED = _shape("<улица> <число прописью> — ни слова-типа улицы, ни слова «дом»")
S_CALL_TYPE_FIRST = _shape("<тип улицы> <улица> <число прописью>")
S_CALL_TYPE_LAST = _shape("<улица> <тип улицы> <число прописью>")
S_CALL_DOM = _shape("<улица> дом <число> [корпус|строение|этаж <число>]")
S_CALL_FLAT = _shape("<улица> <число> квартира <число>")
S_CALL_CITY = _shape("<город> <тип улицы> <улица> <число>")
S_CALL_LETTER = _shape("<улица> <число прописью> <одна буква>")
S_CALL_ASR = _shape(
    "ошибка расшифровки ВНУТРИ значения: «лермонтова триц восемь», "
    "«лермонтого тридцать восемь»")

S_NAME_SURNAME = _shape("<фамилия>")
S_NAME_GIVEN = _shape("<имя>")
S_NAME_GIVEN_PATR = _shape("<имя> <отчество>")
S_NAME_PATR = _shape("<отчество>")
S_NAME_GIVEN_SURNAME = _shape("<имя> <фамилия>")
S_NAME_FIO = _shape("<фамилия> <имя> <отчество>")
S_NAME_SURNAME_GIVEN = _shape("<фамилия> <имя>")
S_NAME_GIVEN_PATR_SURNAME = _shape("<имя> <отчество> <фамилия>")
S_NAME_THIS = _shape("это <имя>")
S_NAME_DATIVE = _shape("к <фамилия>")
S_NAME_CALLED = _shape("меня зовут <имя>")
S_NAME_CALLED_PATR = _shape("меня зовут <имя> <отчество>")
S_NAME_MY_SURNAME = _shape("моя фамилия <фамилия>")
S_NAME_SURNAME_CUE = _shape("фамилия <фамилия>")
S_NAME_SPEAKS = _shape("говорит <имя>")
S_NAME_ROLE = _shape(
    "<должность или звание> <фамилия> — сторож васильев, полковник заболотный, "
    "дежурная новикова")
S_NAME_KIN = _shape("<родство> <имя> — дядя валера, тётя варя")

S_PHONE_PAIRS = _shape(
    "телефон — пробегом числительных парами: «сорок один ноль девять шестьдесят "
    "семь», без «плюс семь»")
S_PHONE_RUN = _shape("непрерывный пробег числительных длиной 4-8 слов, без единой цифры")
S_DICTATION = _shape(
    "диктовка вслух: «записывай», «записал», «пишите» — значение стоит рядом")



# --- the speech corpus ----------------------------------------------------

def _load_speech() -> tuple[dict[str, tuple[int, str]], tuple[str, ...]]:
    """key -> (1-based line, text), plus the text in file order.

    The key is blake2b-6 of the utterance, which is what the annotation files
    use. Duplicated utterances keep their FIRST line: a human going to look at
    the source wants a line that holds the text, and the later copies do too.
    """
    if not SPEECH.exists():
        raise FileNotFoundError(
            f"{SPEECH} is missing. Fetch SOVA RuDevices into "
            f"~/.cache/pseudex-bench/ before building; this family is 70 cases "
            f"of real speech and will not substitute generated speech for it.")
    by_key: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    with SPEECH.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            text = str(json.loads(line)["text"])
            order.append(text)
            key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
            if key not in by_key:
                by_key[key] = (index, text)
    return by_key, tuple(order)


def _load_labels() -> tuple[dict[str, object], ...]:
    if not LABELS.exists():
        raise FileNotFoundError(
            f"{LABELS} is missing. The verbatim layer's ground truth IS that "
            f"hand annotation; there is no generated stand-in for it.")
    with LABELS.open(encoding="utf-8") as handle:
        return tuple(json.load(handle))


SPEECH_BY_KEY, SPEECH_ORDER = _load_speech()
LABEL_ROWS = _load_labels()


def _source(key: str) -> Source:
    line, text = SPEECH_BY_KEY[key]
    return Source(corpus="speech_rudevices", key=key, line=line,
                  sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                  licence=RUDEVICES_LICENCE)


# --- filtering the corpus for filler and for negatives ---------------------
#
# NOT a PII detector and deliberately weaker than one. Its job is to keep a
# stray personal datum out of unlabelled filler, where it would score as a false
# mask against a gateway that was right. Over-rejecting costs nothing here.

# The corpus ships, so the filler has to be text a customer can be shown. This
# is a CONTENT filter, not a detection one: it decides what may stand beside a
# labelled value, and over-rejecting costs nothing — the pool is 22 000 replies
# and the family draws a few hundred.
#
# Anchored at a word start or a known prefix rather than matched as a bare
# substring: «ебу» inside «требую» and «ебё» inside «ребёнок» are the false
# positives that arrangement produces, and the second one hit a hand-annotated
# address reply. The prefix list is what makes «похую» and «заебал» reachable
# without reaching into ordinary words.
_OBSCENE = re.compile(
    r"(?:^|[^а-яё])"
    r"(?:по|за|на|до|от|при|раз|вы|пере|про|под|об|из|ни|не|у|с|о)?[ъь]?"
    r"(?:бля|пизд|ху[йяеёиюы]|[её]б|сук[аиуе]|говн|жоп|срат|дроч|мудак|пидор|"
    r"ссан|шлюх|проститут|наркот|кокаин|героин|изнасил|труп|убийств|педоф|"
    r"суицид|сис[ьк]|член|отсас|сосал|сос[её]т|трах|секс|эрот|минет|аналь|"
    r"оргазм|порн|голая|голый|голым|интим|презерв|задниц|писюн|письк|хер[аоуы]|"
    r"залуп)")

_PATRONYMIC_ISH = re.compile(
    r"\w*(ович|евич|овна|евна|ична|иныч|аныч|алыч|ыч)\b|"
    r"\b(сторож|полковник|дежурн\w+|подполковник|майор|капитан|лейтенант|"
    r"генерал|дядя|тётя|тетя|фамили\w+|отчеств\w+)\b")
# Given names and diminutives that occur in ordinary RuDevices chatter. Authored
# and checked as a whole token: a filler line naming a person carries a datum
# nobody claimed, and an unclaimed datum in filler is the corpus being wrong
# while the gateway takes the blame. The list cannot be complete — Russian has
# more hypocorisms than any list holds — and the residual is stated rather than
# hidden: a name that slips through is claimed by nothing, so it scores neither
# as a leak nor as a false mask, and the cost is honesty rather than a number.
_FILLER_NAME_TOKENS = frozenset("""
оля олю оле саша сашу саше сашка маша машу маше даша дашу даше
женя жене женю вася васе васю вован паша паше пашу коля коле колю миша мише мишу
наташа наташе наташу лена лене лену ира ире иру таня тане таню света свете свету
серёжа серёже серёжу сережа сереже сережу серёга серега серёге витя вите витю
игорь игоря игорю андрей андрея андрею сергей сергея сергею дима диме диму димой
димон алексей алексея лёха леха лёхе антон антона антону артём артёма артему
никита никиты юля юле юлю катя кате катю ксюша ксюше настя насте настю
вика вике вику аня ане аню баша галя гале галю вова вове вову толя толе толю
славик рома ромы роме санёк санек тёма тема витёк витек ирочка ирочку гуля
максим максима максиму олег олега олегу иван ивана ивану пётр петр петра петру
""".split())
# Declined forms are generated rather than listed: «димон» was in the list and
# «димону» was not, and the reply naming him went into filler unclaimed. The
# junk this produces («оляу») matches nothing and costs nothing; the
# over-rejection it produces («света» is also the genitive of light) costs one
# filler line out of twenty-two thousand.
_FILLER_NAME_TOKENS = _FILLER_NAME_TOKENS | frozenset(
    name + ending for name in _FILLER_NAME_TOKENS
    for ending in ("а", "у", "е", "ы", "и", "ой", "ей", "ем", "ом", "ю"))

_WORD_TOKEN = re.compile(r"[а-яё]+")


def _looks_personal(text: str) -> bool:
    if _PATRONYMIC_ISH.search(text):
        return True
    return any(word in _FILLER_NAME_TOKENS for word in _WORD_TOKEN.findall(text))


def _usable_filler(text: str) -> bool:
    """A reply that may stand as unlabelled filler.

    THE SCREEN IS `schema.unsafe_filler`, called and not restated. Five families
    each kept a private copy of this idea with a private name list, so «оксана»
    was in one of them and in none of the others; one place is what makes a word
    added once protect all eleven.

    `_looks_personal` survives beside it and is not redundant: it knows the
    diminutives («димон», «ксюша») that no gold span in this corpus ever carries,
    so the attested vocabulary cannot contain them.
    """
    if len(text) < 24 or _OBSCENE.search(text) or _looks_personal(text):
        return False
    return not unsafe_filler(text)


# --- numbers as words -----------------------------------------------------
#
# The register has no digits at all, so a number IS a run of numeral words and
# every value that carries one has to be spelled here. A written corpus cannot
# produce this shape, which is exactly why both of the defects this version
# exists for were invisible until now.

_UNITS: tuple[str, ...] = ("ноль", "один", "два", "три", "четыре", "пять",
                           "шесть", "семь", "восемь", "девять")
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
_TENS: tuple[str, ...] = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят",
                          "шестьдесят", "семьдесят", "восемьдесят", "девяносто")
_HUNDREDS: tuple[str, ...] = ("", "сто", "двести", "триста", "четыреста",
                              "пятьсот", "шестьсот", "семьсот", "восемьсот",
                              "девятьсот")
_ORDINALS: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой", "седьмой",
    "восьмой", "девятый", "десятый", "одиннадцатый", "двенадцатый")
# «восьмой отделение» is not Russian. The ordinal agrees with the noun it stands
# in front of, and a negative that reads as broken text is a negative a reader
# stops trusting — which is the whole point of writing them from real replies.
_ORDINALS_NEUTER: tuple[str, ...] = (
    "", "первое", "второе", "третье", "четвёртое", "пятое", "шестое", "седьмое",
    "восьмое", "девятое", "десятое", "одиннадцатое", "двенадцатое")

# Measured on the call corpus: 22.9% of every «-десят» form arrives contracted,
# and numerals arrive truncated mid-word. This is the norm of the register, not
# an adversarial perturbation, so it is applied by rate and not by difficulty.
_CONTRACTED: dict[str, tuple[str, ...]] = {
    "пятьдесят": ("песят", "пеесят", "пяесят", "пейсят"),
    "шестьдесят": ("шеесят", "шейсят", "шесят"),
    "восемьдесят": ("восемесят",),
}
# From `calls_grammar.json` -> lexicon.asr_error.near_misses_by_canonical. Only
# the forms a human transcriber actually wrote down.
_ASR_SLIPS: dict[str, tuple[str, ...]] = {
    "три": ("триц", "тридц", "трис"),
    "тридцать": ("триц", "тридц"),
    "восемь": ("восем", "восемсь"),
    "девяносто": ("девяно", "девяеносто"),
    "триста": ("тристо", "трииста"),
    "четыре": ("четыыре",),
    "пять": ("пяять",),
    "шесть": ("шесят",),
    "десять": ("деся",),
    "семьсот": ("семест",),
    "восемьсот": ("восемест", "восемьст"),
    "шестьсот": ("шессот",),
    "одиннадцать": ("одинадцать",),
}


def _spell_cardinal(value: int) -> str:
    """0..999 in words. Masculine nominative, which is what a house number is."""
    if not 0 <= value <= 999:
        raise ValueError(f"{value} is outside the range this register spells")
    if value < 10:
        return _UNITS[value]
    if value < 20:
        return _TEENS[value - 10]
    words: list[str] = []
    hundreds, rest = divmod(value, 100)
    if hundreds:
        words.append(_HUNDREDS[hundreds])
    if rest >= 20:
        tens, unit = divmod(rest, 10)
        words.append(_TENS[tens])
        if unit:
            words.append(_UNITS[unit])
    elif rest >= 10:
        words.append(_TEENS[rest - 10])
    elif rest:
        words.append(_UNITS[rest])
    return " ".join(words)


def _spell_ordinal(value: int) -> str:
    if not 1 <= value <= 12:
        raise ValueError(f"no spoken ordinal for {value} in this pool")
    return _ORDINALS[value]


def _spell_pairs(digits: str) -> str:
    """A number dictated in pairs, which is how a phone is said aloud.

    «сорок один ноль девять шестьдесят семь» = 41-09-67. A leading zero is
    spoken as a word of its own and is often doubled — that «ноль ноль» is 95
    occurrences in the call corpus and is why a digit-shaped pattern sees
    nothing here.
    """
    spoken: list[str] = []
    for index in range(0, len(digits) - 1, 2):
        pair = int(digits[index:index + 2])
        if digits[index] == "0":
            spoken.append(_UNITS[0])
            spoken.append(_UNITS[int(digits[index + 1])])
        else:
            spoken.append(_spell_cardinal(pair))
    if len(digits) % 2:
        spoken.append(_UNITS[int(digits[-1])])
    return " ".join(spoken)


def _spell_singles(digits: str) -> str:
    return " ".join(_UNITS[int(digit)] for digit in digits)


def _spell_triples(digits: str) -> str:
    """Three at a time, which is how a СНИЛС or an ИНН is read off a card."""
    spoken: list[str] = []
    for index in range(0, len(digits), 3):
        group = digits[index:index + 3]
        if len(group) == 3 and group[0] != "0":
            spoken.append(_spell_cardinal(int(group)))
        else:
            spoken.append(_spell_singles(group))
    return " ".join(spoken)


def _asr_noise(spoken: str, stream: random.Random) -> str:
    """One mined slip or contraction inside a spoken number.

    Applied to the VALUE, which is where the corpus found it: 9 of 44 address
    values in the call corpus carry a transcription error inside the value
    itself, not beside it.
    """
    words = spoken.split()
    positions = [index for index, word in enumerate(words)
                 if word in _CONTRACTED or word in _ASR_SLIPS]
    if not positions:
        return spoken
    position = stream.choice(positions)
    word = words[position]
    table = _CONTRACTED.get(word) or _ASR_SLIPS[word]
    words[position] = stream.choice(table)
    return " ".join(words)


# --- keyboard damage, which is a different thing from ASR damage ----------
#
# `sloppy` and `voice_raw` are separate registers because their errors have
# different shapes and break different things: ASR fails phonetically («триц»,
# «песят», «лермонтого»), a keyboard fails by adjacency («Кзнецов»).

_ADJACENT: dict[str, str] = {
    "й": "цф", "ц": "йу", "у": "цк", "к": "уе", "е": "кн", "н": "ег",
    "г": "нш", "ш": "гщ", "щ": "шз", "з": "щх", "х": "зъ",
    "ф": "йы", "ы": "фв", "в": "ыа", "а": "вп", "п": "ар", "р": "по",
    "о": "рл", "л": "од", "д": "лж", "ж": "дэ", "э": "ж",
    "я": "ыч", "ч": "яс", "с": "чм", "м": "си", "и": "мт", "т": "иь",
    "ь": "тб", "б": "ью", "ю": "б",
}


def _typo(word: str, stream: random.Random) -> str:
    """Exactly one keyboard-shaped edit. Never two: two edits leave the deletion
    neighbourhood a one-edit index can reach, and the corpus would then be
    demanding a capability nobody claims."""
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


# --- people ---------------------------------------------------------------
#
# Authored from the domain: what a Russian service conversation contains.
# Declined forms are written out rather than computed, because computing them
# needs the morphology the gateway itself is being measured on — a pool declined
# by pymorphy3 would hand the corpus the engine's own opinion as ground truth.
#
# Each part is (nominative, dative, accusative). Dative is the addressee form
# («к букину», «позовите ирочку» is accusative), and 15% of real mentions are
# oblique — 124 of 815 in the call corpus.

@dataclass(frozen=True)
class Person:
    surname: tuple[str, str, str]
    given: tuple[str, str, str]
    patronymic: tuple[str, str, str]
    short_patronymic: str
    gender: str


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

# Deliberately hostile to a suffix rule: no -ов/-ев/-ин, several non-Slavic,
# because a shop's foreign customers are Tuesday and a rule that reaches names
# through a Russian suffix reports a healthy number while failing them.
FOREIGN: tuple[Person, ...] = (
    Person(("ким", "киму", "кима"), ("виктор", "виктору", "виктора"), ("", "", ""), "", "m"),
    Person(("мкртчян", "мкртчяну", "мкртчяна"), ("ашот", "ашоту", "ашота"), ("", "", ""), "", "m"),
    Person(("тагиев", "тагиеву", "тагиева"), ("рустам", "рустаму", "рустама"), ("", "", ""), "", "m"),
    Person(("саркисян", "саркисяну", "саркисяна"), ("карен", "карену", "карена"), ("", "", ""), "", "m"),
    Person(("абдуллаев", "абдуллаеву", "абдуллаева"), ("тимур", "тимуру", "тимура"), ("", "", ""), "", "m"),
    Person(("валиахметов", "валиахметову", "валиахметова"), ("ильдар", "ильдару", "ильдара"), ("", "", ""), "", "m"),
    Person(("нгуен", "нгуену", "нгуена"), ("ань", "ань", "ань"), ("", "", ""), "", "m"),
    Person(("мамедова", "мамедовой", "мамедову"), ("лейла", "лейле", "лейлу"), ("", "", ""), "", "f"),
    Person(("шевчук", "шевчуку", "шевчука"), ("олесь", "олесю", "олеся"), ("", "", ""), "", "m"),
    Person(("джонсон", "джонсону", "джонсона"), ("майкл", "майклу", "майкла"), ("", "", ""), "", "m"),
    Person(("ли", "ли", "ли"), ("чен", "чену", "чена"), ("", "", ""), "", "m"),
    Person(("аширбаев", "аширбаеву", "аширбаева"), ("дадахон", "дадахону", "дадахона"),
           ("абдулазизович", "абдулазизовичу", "абдулазизовича"), "", "m"),
)

# Put in by hand, and the mined file says why: «ирочку», «витёк», «серёжа» are
# in the corpus and NEITHER the name dictionary NOR pymorphy3 calls them names,
# so without a hand-laid pool a whole way of naming a person never reaches the
# benchmark at all.
DIMINUTIVES: tuple[tuple[str, str, str], ...] = (
    ("ирочка", "ирочке", "ирочку"),
    ("витёк", "витьку", "витька"),
    ("серёжа", "серёже", "серёжу"),
    ("наташа", "наташе", "наташу"),
    ("женя", "жене", "женю"),
    ("вася", "васе", "васю"),
    ("паша", "паше", "пашу"),
    ("коля", "коле", "колю"),
    ("славик", "славику", "славика"),
    ("ленка", "ленке", "ленку"),
    ("даша", "даше", "дашу"),
    ("миша", "мише", "мишу"),
    ("валера", "валере", "валеру"),
    ("гуля", "гуле", "гулю"),
    ("фарик", "фарику", "фарика"),
    ("янчик", "янчику", "янчика"),
)

# The commonest thing standing in front of a surname is not a cue word but a
# rank: 75 occurrences against 20 for «меня зовут». A cue LICENSES its
# neighbour, it does not name it, so the role word is never inside the span.
ROLES: tuple[str, ...] = ("сторож", "полковник", "дежурный", "дежурная",
                          "подполковник", "майор", "капитан", "лейтенант",
                          "мастер", "начальник")
KINSHIP_MALE: tuple[str, ...] = ("дядя", "брат", "папа")
KINSHIP_FEMALE: tuple[str, ...] = ("тётя", "мама", "сестра")


# --- places ---------------------------------------------------------------
#
# Two thirds of the address values in both corpora carry NO street-type word at
# all — 113 of 169 in dispatch, 26 of 44 in the calls — so a generator writing
# «улица Ленина дом 50» measures the easy half. The street itself is named two
# ways and only two: an adjective, or a surname in the genitive (14 against 28).

STREET_FEM: tuple[str, ...] = (
    "вольная", "кирочная", "мончегорская", "школьная", "зеленоградская",
    "химзаводская", "союзная", "нижняя", "клубная", "базисная", "депутатская",
    "совхозная", "вишнёвая", "садовая", "центральная", "лесная", "новая",
    "подлесная", "солнечная", "рабочая", "заречная", "полевая", "луговая",
    "наличная", "деревообделочная",
)
STREET_GENITIVE: tuple[str, ...] = (
    "лермонтова", "комиссарова", "чапаева", "калашникова", "грибоедова",
    "гагарина", "кирова", "энгельса", "ленина", "маяковского", "шумайлова",
    "репина", "тельмана", "дзержинского", "добролюбова", "барышникова",
    "челюскинцев", "пушкина", "некрасова", "толстого", "берша", "коммунаров",
)
STREET_MASC: tuple[str, ...] = (
    "смольный", "загородный", "северный", "комсомольский", "зелёный",
    "светлый", "октябрьский", "строительный",
)
STREET_NEUTER: tuple[str, ...] = (
    "воткинское", "заречное", "симферопольское", "ярославское", "ленинградское",
)
CITIES: tuple[str, ...] = (
    "ижевск", "абакан", "колпино", "сортавала", "воткинск", "глазов",
    "сарапул", "можга", "краснодар", "самара",
)
HOUSE_LETTERS: tuple[str, ...] = ("а", "б", "в")


@dataclass(frozen=True)
class Address:
    street: str
    street_type: str   # "" when the value carries no type word at all
    house: int
    letter: str        # "" when none
    entrance: int      # 0 when none
    flat: int          # 0 when none
    korpus: int        # 0 when none
    stroenie: int      # 0 when none
    city: str          # "" when the value does not name one


def _street_for(street_type: str, stream: random.Random) -> str:
    if street_type == "шоссе":
        return stream.choice(STREET_NEUTER)
    if street_type in ("переулок", "проезд", "проспект", "бульвар"):
        return stream.choice(STREET_MASC + STREET_GENITIVE)
    return stream.choice(STREET_FEM + STREET_GENITIVE)


# --- identifiers ----------------------------------------------------------
#
# Every one passes its own published checksum. A ground truth claiming a
# document that is not one would score a checksum-gated detector as wrong for
# being right, which is the opposite of what this benchmark is for.

def _snils(stream: random.Random) -> str:
    """Nine digits plus the mod-101 control pair."""
    while True:
        digits = "".join(str(stream.randrange(10)) for _ in range(9))
        if len(set(digits)) == 1:
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


def _inn12(stream: random.Random) -> str:
    """A TWELVE-digit ИНН, which belongs to a natural person.

    A ten-digit one identifies an organisation, and an organisation is not a
    subject of personal data — 152-ФЗ defines the subject as a natural person and
    Recital 14 says the same thing on the other side of the border. ИП keeps the
    twelve-digit form, so the type survives without the label claiming something
    the law does not.
    """
    first = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    second = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    body = [stream.randrange(10) for _ in range(10)]
    eleventh = sum(digit * weight for digit, weight in zip(body, first)) % 11 % 10
    body.append(eleventh)
    twelfth = sum(digit * weight for digit, weight in zip(body, second)) % 11 % 10
    body.append(twelfth)
    return "".join(str(digit) for digit in body)


def _card(stream: random.Random) -> str:
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


def _passport(stream: random.Random) -> tuple[str, str]:
    return (f"{stream.randint(1000, 9999)}",
            f"{stream.randint(100000, 999999)}")


_PLATE_LETTERS = "АВЕКМНОРСТУХ"
_PLATE_SPOKEN = {"А": "а", "В": "вэ", "Е": "е", "К": "ка", "М": "эм", "Н": "эн",
                 "О": "о", "Р": "эр", "С": "эс", "Т": "тэ", "У": "у", "Х": "ха"}
_PLATE_REGIONS = ("18", "77", "99", "16", "59", "23", "63")


def _plate(stream: random.Random) -> tuple[str, str, str, str]:
    """(first letter, three digits, two letters, region), kept apart so the
    spoken form can be built from the same parts rather than parsed back out."""
    return (stream.choice(_PLATE_LETTERS),
            f"{stream.randint(100, 999)}",
            "".join(stream.choice(_PLATE_LETTERS) for _ in range(2)),
            stream.choice(_PLATE_REGIONS))


_MONTHS: tuple[str, ...] = ("января", "февраля", "марта", "апреля", "мая",
                            "июня", "июля", "августа", "сентября", "октября",
                            "ноября", "декабря")
_MONTH_ORDINALS: tuple[str, ...] = (
    "", "первое", "второе", "третье", "четвёртое", "пятое", "шестое", "седьмое",
    "восьмое", "девятое", "десятое", "одиннадцатое", "двенадцатое",
    "тринадцатое", "четырнадцатое", "пятнадцатое", "шестнадцатое",
    "семнадцатое", "восемнадцатое", "девятнадцатое", "двадцатое",
    "двадцать первое", "двадцать второе", "двадцать третье", "двадцать четвёртое",
    "двадцать пятое", "двадцать шестое", "двадцать седьмое", "двадцать восьмое")

_EMAIL_DOMAINS: tuple[str, ...] = ("mail.ru", "yandex.ru", "gmail.com",
                                   "list.ru", "inbox.ru", "bk.ru")
_SPOKEN_DOMAINS: dict[str, str] = {
    "mail.ru": "мейл точка ру",
    "yandex.ru": "яндекс точка ру",
    "gmail.com": "джимейл точка ком",
    "list.ru": "лист точка ру",
    "inbox.ru": "инбокс точка ру",
    "bk.ru": "бэ ка точка ру",
}
_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit(word: str) -> str:
    return "".join(_TRANSLIT.get(letter, letter) for letter in word)


_SPOKEN_LATIN: dict[str, str] = {
    "a": "а", "b": "бэ", "c": "цэ", "d": "дэ", "e": "е", "f": "эф", "g": "гэ",
    "h": "аш", "i": "и", "j": "джей", "k": "ка", "l": "эл", "m": "эм",
    "n": "эн", "o": "о", "p": "пэ", "q": "ку", "r": "эр", "s": "эс", "t": "тэ",
    "u": "у", "v": "вэ", "w": "дубль вэ", "x": "икс", "y": "игрек", "z": "зет",
}


# --- laying a message down, once, with its offsets ------------------------

def _compose(pieces: tuple[tuple[str, str], ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Concatenate chunks and return the spans of the keyed ones.

    THE ONLY PLACE A MESSAGE STRING IS CREATED. Nothing edits a finished message
    afterwards: a later pass that strips punctuation or lowercases changes the
    length and every offset laid down before it goes on pointing at the wrong
    characters while the corpus keeps scoring.
    """
    text = ""
    spans: dict[str, tuple[int, int]] = {}
    for chunk, key in pieces:
        if key:
            if key in spans:
                raise InvalidCase(f"chunk key {key!r} used twice in one message")
            spans[key] = (len(text), len(text) + len(chunk))
        text += chunk
    return text, spans


def _spaced(items: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
    """Join chunks with single spaces, dropping empties.

    An item is either a bare string (no span) or a (text, key) pair. Empty
    strings vanish, which is what lets a shape carry an optional slot without the
    caller counting spaces.
    """
    pieces: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            chunk, key = item, ""
        else:
            chunk, key = item  # type: ignore[misc]
        if not chunk:
            continue
        if pieces:
            pieces.append((" ", ""))
        pieces.append((chunk, key))
    return tuple(pieces)


@dataclass(frozen=True)
class Rendered:
    """A value as it appears, and as a CRM would store it."""

    surface: str
    canonical: str
    spoken: bool


SPEECH_REGISTERS = ("voice_raw", "voice_itn")


def _number(value: int, register: str, stream: random.Random, noisy: bool) -> str:
    """A cardinal in the register's own notation.

    `voice_raw` has no digits at all — zero of 53 324 measured utterances carry
    one — so the number is words there and nowhere else is it words.
    """
    if register != "voice_raw":
        return str(value)
    spoken = _spell_cardinal(value)
    return _asr_noise(spoken, stream) if noisy else spoken


def _entrance(value: int, register: str) -> str:
    """«первый подъезд», with the ordinal BEFORE the marker.

    Measured: 82 that way against 60 the other, so the common order is the one
    the corpus is built on.
    """
    if register in SPEECH_REGISTERS:
        return f"{_spell_ordinal(value)} подъезд"
    return f"подъезд {value}"


def _address_tokens(address: Address, shape: str, register: str,
                    stream: random.Random) -> tuple[str, ...]:
    """The address as an ordered token list, per the mined shape it follows."""
    noisy = shape == S_CALL_ASR
    street = address.street
    if noisy:
        street = _phonetic_slip(street, stream)
    elif register == "sloppy" and stream.randrange(100) < 55:
        # A keyboard breaks the street too, not only the person. «Кзнецов» and
        # «леннина» are the same defect in two places, and a corpus that damages
        # only names measures half of it.
        street = _typo(street, stream)
    house = _number(address.house, register, stream, noisy)
    if shape in (S_ADDR_BARE, S_CALL_NAKED):
        return (street, house)
    if shape == S_ADDR_ENTRANCE:
        return (street, house, _entrance(address.entrance, register))
    if shape == S_ADDR_STREET_WORD:
        return ("улица", street, house)
    if shape in (S_ADDR_LETTER, S_CALL_LETTER):
        return (street, house, address.letter)
    if shape == S_ADDR_LETTER_ENTRANCE:
        return (street, house, address.letter, _entrance(address.entrance, register))
    if shape == S_ADDR_KORPUS:
        return (street, house, "корпус", _number(address.korpus, register, stream, False))
    if shape == S_ADDR_STROENIE:
        return (street, house, "строение", _number(address.stroenie, register, stream, False))
    if shape == S_ADDR_PROEZD:
        return ("проезд", street, house)
    if shape == S_ADDR_PROSPEKT:
        return ("проспект", street, house)
    if shape == S_ADDR_PEREULOK_DOM:
        return ("переулок", street, "дом", house)
    if shape == S_ADDR_STREET_DOM:
        return ("улица", street, "дом", house)
    if shape == S_ADDR_SHOSSE:
        return (street, "шоссе", house)
    if shape in (S_ADDR_FLAT, S_CALL_FLAT):
        return (street, house, "квартира", _number(address.flat, register, stream, False))
    if shape == S_CALL_TYPE_FIRST:
        return (address.street_type, street, house)
    if shape == S_CALL_TYPE_LAST:
        return (street, address.street_type, house)
    if shape == S_CALL_DOM:
        return (street, "дом", house)
    if shape == S_CALL_CITY:
        return (address.city, address.street_type, street, house)
    if shape == S_CALL_ASR:
        return (street, house)
    raise InvalidCase(f"no address layout for shape {shape!r}")


def _phonetic_slip(word: str, stream: random.Random) -> str:
    """A transcription error INSIDE a value — «лермонтого», «кузнецого».

    9 of 44 address values in the call corpus carry one, and it lands inside the
    value rather than beside it. Streets and surnames share the function because
    they share the shape: half the street names in this register ARE surnames in
    the genitive. Never corrected in `canonical` — the gateway cannot know the
    intended word and neither can a scorer, so demanding it back would score the
    gateway on information the damage destroyed.
    """
    if word.endswith("ова"):
        return word[:-3] + "ого"
    vowels = [index for index, letter in enumerate(word[2:-2], start=2)
              if letter in "аеиоуыэюяё"]
    if not vowels:
        return word
    position = stream.choice(vowels)
    return word[:position] + word[position + 1:]


_GLUED_MARKERS: dict[str, str] = {"квартира": "кв", "корпус": "к"}


def _glue_markers(tokens: tuple[str, ...], stream: random.Random) -> tuple[str, ...]:
    """«гагарина88кв152» — the marker is usually glued to the house number.

    Typed Russian addresses run the flat marker straight into the number, and the
    engine paid for that once: the pattern demanded whitespace before the marker,
    so the flat fell outside the span and went to the model inside an address
    whose street was already masked.
    """
    if stream.randrange(100) >= 25:
        return tokens
    glued: list[str] = list(tokens)
    for position in range(len(glued) - 2, 0, -1):
        short = _GLUED_MARKERS.get(glued[position])
        if short and glued[position - 1].isdigit() and glued[position + 1].isdigit():
            glued[position - 1:position + 2] = [
                f"{glued[position - 1]}{short}{glued[position + 1]}"]
    return tuple(glued)


# Two things this register does to ordinary words, and both are frequent enough
# to be the norm rather than an adversarial trick: a particle glued to the tail
# (394 occurrences) and a stretched vowel (383). Applied only to words AROUND a
# value — inside one, the damage is `_asr_noise`, which uses the forms a human
# transcriber actually wrote.
_PARTICLE_HOSTS: frozenset[str] = frozenset({
    "адрес", "фамилия", "телефон", "приезжай", "приезжайте", "записывай",
    "какой", "звоните", "номер"})


def _speech_noise(word: str, stream: random.Random) -> str:
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


def _render_address(address: Address, shape: str, register: str,
                    stream: random.Random) -> Rendered:
    """The address surface, and the canonical form a CRM would keep.

    For every register but `clean` the canonical IS the surface: the value the
    vault stores is the string that was said, and demanding «школьная 59» back
    from «школьная пятьдесят девять» would demand a conversion the product does
    not perform — `classify_break` calls a gateway that does it `renumbered`.
    """
    if register == "clean":
        return _render_address_clean(address, shape, stream)
    tokens = tuple(token for token in _address_tokens(address, shape, register,
                                                      stream) if token)
    if register in ("chat", "sloppy"):
        tokens = _glue_markers(tokens, stream)
    surface = " ".join(tokens)
    spoken = register == "voice_raw"
    return Rendered(surface=surface, canonical=surface, spoken=spoken)


def _render_address_clean(address: Address, shape: str,
                          stream: random.Random) -> Rendered:
    """The literary form: same slot ORDER, document typography.

    Kept to one case in twenty by the corpus plan and it exists to show we did
    not break on a web form, not because the traffic looks like this — measured,
    it does not. The order stays the shape's, so `Provenance.shape` still names
    something this string obeys; only the punctuation and the capitals are the
    register's.
    """
    tokens = [token for token in _address_tokens(address, shape, "clean", stream)
              if token]
    rendered = tokens[0].capitalize()
    for token in tokens[1:]:
        first = token.split()[0]
        rendered += (", " if first in ("дом", "корпус", "строение", "квартира",
                                       "подъезд") else " ") + token
    return Rendered(surface=rendered, canonical=rendered, spoken=False)


# --- names ----------------------------------------------------------------
#
# The slot order is not fixed and the corpus says so: surname alone 350, given
# alone 255, given + patronymic 109, ФИО 23, given + surname 23, patronymic
# alone 29. A generator that always writes «Фамилия Имя Отчество» is measuring
# one of six shapes.

_CASE_INDEX: dict[str, int] = {"nom": 0, "dat": 1, "acc": 2}


def _name_part(person: Person, slot: str, grammar: str,
               diminutive: tuple[str, str, str]) -> tuple[str, str]:
    """(surface form, nominative form) for one slot."""
    index = _CASE_INDEX[grammar]
    if slot == "surname":
        return person.surname[index], person.surname[0]
    if slot == "given":
        return person.given[index], person.given[0]
    if slot == "patronymic":
        return person.patronymic[index], person.patronymic[0]
    if slot == "short":
        # A contracted patronymic is a spoken form and is not declined here:
        # «палыч» has no nominative other than itself in this pool.
        return person.short_patronymic, person.short_patronymic
    if slot == "diminutive":
        return diminutive[index], diminutive[0]
    raise InvalidCase(f"unknown name slot {slot!r}")


def _render_name(person: Person, layout: tuple[str, ...], grammar: str,
                 register: str, damage: str, diminutive: tuple[str, str, str],
                 stream: random.Random) -> Rendered:
    """A name in one register, with the canonical built from the SAME parts.

    `canonical` is the nominative of what was said and nothing more. A message
    with no patronymic must not demand one back — that scores the gateway on
    information the conversation never carried, and it was 162 of v1's 183
    sloppy failures.

    A part the register DAMAGED keeps its damage in the canonical. Reversing an
    ASR slip or a typo would demand the intended word, which is exactly the
    information the damage destroyed.
    """
    surfaces: list[str] = []
    canonicals: list[str] = []
    damaged = stream.randrange(len(layout)) if damage != "none" else -1
    for position, slot in enumerate(layout):
        surface, nominative = _name_part(person, slot, grammar, diminutive)
        if not surface:
            continue
        if position == damaged:
            surface = (_typo(surface, stream) if damage == "typo"
                       else _phonetic_slip(surface, stream))
            nominative = surface
        if register == "clean":
            surface = surface.capitalize()
            nominative = nominative.capitalize()
        surfaces.append(surface)
        canonicals.append(nominative)
    if not surfaces:
        raise InvalidCase("a name layout produced no parts at all")
    return Rendered(surface=" ".join(surfaces), canonical=" ".join(canonicals),
                    spoken=False)


# --- the rest of the types ------------------------------------------------

def _render_phone(digits: str, register: str, stream: random.Random) -> Rendered:
    """Ten digits, in the form the register produces.

    The spoken form carries NO digit, which is the whole point: libphonenumber
    and every checksum wait for digits, so a dictated number is found by nothing
    at all today. Measured on v2's corpus: 133 spoken phones, 0 detected.
    """
    canonical = f"+7{digits}"
    if register == "voice_raw":
        code, first, rest = digits[:3], digits[3:6], digits[6:]
        spoken = " ".join(("восемь", _spell_cardinal(int(code)),
                           _spell_cardinal(int(first)), _spell_pairs(rest)))
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    if register == "clean":
        return Rendered(surface=f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}",
                        canonical=canonical, spoken=False)
    written = stream.choice((
        f"8{digits}", f"+7{digits}", f"8 {digits[:3]} {digits[3:6]} {digits[6:8]} {digits[8:]}",
        f"+7{digits[:3]}{digits[3:6]}{digits[6:]}",
    ))
    return Rendered(surface=written, canonical=canonical, spoken=False)


def _render_snils(digits: str, register: str) -> Rendered:
    if register == "voice_raw":
        spoken = " ".join((_spell_triples(digits[:9]), _spell_cardinal(int(digits[9:]))))
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    written = f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
    return Rendered(surface=written, canonical=written, spoken=False)


def _render_inn(digits: str, register: str) -> Rendered:
    if register == "voice_raw":
        spoken = _spell_triples(digits)
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    return Rendered(surface=digits, canonical=digits, spoken=False)


def _render_card(digits: str, register: str) -> Rendered:
    if register == "voice_raw":
        spoken = _spell_pairs(digits)
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    if register in ("clean", "chat"):
        written = " ".join(digits[index:index + 4] for index in range(0, 16, 4))
        return Rendered(surface=written, canonical=written, spoken=False)
    return Rendered(surface=digits, canonical=digits, spoken=False)


def _render_passport(series: str, number: str, register: str) -> Rendered:
    if register == "voice_raw":
        spoken = " ".join((_spell_pairs(series), _spell_triples(number)))
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    if register in ("clean", "chat"):
        return Rendered(surface=f"{series} {number}", canonical=f"{series} {number}",
                        spoken=False)
    return Rendered(surface=f"{series}{number}", canonical=f"{series}{number}",
                    spoken=False)


def _render_plate(plate: tuple[str, str, str, str], register: str) -> Rendered:
    first, digits, pair, region = plate
    if register == "voice_raw":
        spoken = " ".join((
            _PLATE_SPOKEN[first], _spell_cardinal(int(digits)),
            " ".join(_PLATE_SPOKEN[letter] for letter in pair),
            _spell_cardinal(int(region))))
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    written = f"{first}{digits}{pair}{region}"
    if register in ("chat", "sloppy"):
        written = written.lower()
    return Rendered(surface=written, canonical=written, spoken=False)


def _spell_year(year: int) -> str:
    """«восемьдесят пятого года» — a year is spoken as an ordinal in the genitive.

    Written out because there is no cheap way back from a cardinal: «пять»
    becomes «пятого», not «пятьго», and a corpus that spells it wrong is testing
    a string no Russian speaker produces.
    """
    tail = year % 100
    tens, unit = divmod(tail, 10)
    genitive = ("", "первого", "второго", "третьего", "четвёртого", "пятого",
                "шестого", "седьмого", "восьмого", "девятого")
    if tail == 0:
        return "двухтысячного"
    if 10 <= tail < 20:
        return _TEENS[tail - 10] + "го"
    if unit == 0:
        return {2: "двадцатого", 3: "тридцатого", 4: "сорокового",
                5: "пятидесятого", 6: "шестидесятого", 7: "семидесятого",
                8: "восьмидесятого", 9: "девяностого"}[tens]
    return f"{_TENS[tens]} {genitive[unit]}" if tens >= 2 else genitive[unit]


def _render_dob(day: int, month: int, year: int, register: str) -> Rendered:
    if register == "voice_raw":
        spoken = " ".join((_MONTH_ORDINALS[day], _MONTHS[month - 1],
                           _spell_year(year), "года"))
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    canonical = f"{day:02d}.{month:02d}.{year}"
    if register == "voice_itn":
        # ITN restores digits, not punctuation — a dotted date in a register
        # defined by having none would be a `clean` case wearing another label.
        return Rendered(surface=f"{day:02d} {month:02d} {year}",
                        canonical=canonical, spoken=False)
    return Rendered(surface=canonical, canonical=canonical, spoken=False)


def _render_email(local: str, domain: str, spoken_local: str,
                  register: str) -> Rendered:
    """An address, and the way a mouth produces one.

    Dictated aloud the local part is a WORD, not a spelling drill: «букин собака
    мейл точка ру». Spelling it letter by letter is what a person does only when
    the word is not obvious, and building the whole pool that way would measure
    the rarer half.
    """
    if register == "voice_raw":
        spoken = " ".join((spoken_local, "собака", _SPOKEN_DOMAINS[domain]))
        return Rendered(surface=spoken, canonical=spoken, spoken=True)
    written = f"{local}@{domain}"
    return Rendered(surface=written, canonical=written, spoken=False)


# --- negatives ------------------------------------------------------------
#
# Half of the precision measurement, and the biggest false-positive source in
# this register is measured rather than guessed: a number standing beside
# «кабинет» or «отделение» occurs 528 times in the call corpus. A dictated order
# number is the other one — that defect shipped once.
#
# The span is EXPLICIT and laid down during assembly, never found afterwards
# with `text.find`: a searched offset is derived from the finished string, and
# the finished string is what the register already rewrote.

@dataclass(frozen=True)
class NegativeChunk:
    """A non-personal value with the shape of one, split around its own span.

    `before` and `after` exist so that `_compose` can key the middle chunk: the
    offset is laid down while the message is being built, never recovered from
    the finished string afterwards. A searched offset finds the FIRST occurrence,
    and a message naming «пять» twice then points at the wrong one.
    """

    before: str
    value: str
    after: str
    family: str
    why: str

    def pieces(self, key: str) -> tuple[object, ...]:
        return (self.before, (self.value, key), self.after)


# Russian agreement, because «3 гектаров» is not a sentence anybody writes and a
# negative that reads as broken text is a negative a reader distrusts.
QUANTITY_UNITS: tuple[tuple[str, str, str], ...] = (
    ("коробка", "коробки", "коробок"), ("штука", "штуки", "штук"),
    ("филиал", "филиала", "филиалов"), ("человек", "человека", "человек"),
    ("место", "места", "мест"))
MEASURE_UNITS: tuple[tuple[str, str, str], ...] = (
    ("градус", "градуса", "градусов"), ("километр", "километра", "километров"),
    ("метр", "метра", "метров"), ("гектар", "гектара", "гектаров"))


def _plural(count: int, forms: tuple[str, str, str]) -> str:
    tail, hundred = count % 10, count % 100
    if tail == 1 and hundred != 11:
        return forms[0]
    if 2 <= tail <= 4 and not 12 <= hundred <= 14:
        return forms[1]
    return forms[2]


def _negative_chunk(kind: str, register: str, stream: random.Random) -> NegativeChunk:
    """One non-personal value with a personal shape, in the register's notation."""
    if kind == "order_number":
        number = stream.randint(101, 899)
        value = _number(number, register, stream, False)
        word = "заказ"
        return NegativeChunk(word, value, "", "order_number",
                             "номер заказа — не персональные данные; продиктованный "
                             "вслух он маскировался целиком, и это уже отгружалось")
    if kind == "room_number":
        room = stream.randint(2, 12)
        place = stream.choice(("кабинет", "отделение"))
        # Only `voice_raw` spells a number; ITN is defined by turning it back
        # into a digit, and a word-form here would leave the case with none.
        if register == "voice_raw":
            ordinal = (_ORDINALS_NEUTER[room] if place == "отделение"
                       else _spell_ordinal(room))
            value = f"{ordinal} {place}"
        else:
            value = f"{room} {place}"
        return NegativeChunk("", value, "", "room_number",
                             "число рядом с кабинетом или отделением — 528 таких "
                             "реплик в корпусе звонков, крупнейший источник ложных "
                             "срабатываний этого регистра")
    if kind == "time_of_day":
        hour = stream.choice((8, 9, 10, 11, 12))
        if register == "voice_raw":
            spoken = {8: "восьми", 9: "девяти", 10: "десяти", 11: "одиннадцати",
                      12: "двенадцати"}[hour]
            return NegativeChunk("к", f"{spoken} ноль ноль", "", "time_of_day",
                                 "время; ноли проговариваются словом и дают тот же "
                                 "пробег числительных, что и номер")
        # No colon: `_SENTENCE_PUNCT` counts one, and two of the five registers
        # are defined by carrying no sentence punctuation at all.
        return NegativeChunk("к", f"{hour} часам", "", "time_of_day",
                             "время, а не номер")
    if kind == "quantity":
        count = stream.randint(2, 12)
        unit = _plural(count, stream.choice(QUANTITY_UNITS))
        value = f"{_number(count, register, stream, False)} {unit}"
        return NegativeChunk("", value, "", "quantity",
                             "числительное с единицей счёта — не номер дома")
    if kind == "measure":
        count = stream.randint(2, 40)
        unit = _plural(count, stream.choice(MEASURE_UNITS))
        value = f"{_number(count, register, stream, False)} {unit}"
        return NegativeChunk("", value, "", "measure",
                             "число с единицей измерения: «территория пять гектаров» "
                             "проходит все адресные признаки и адресом не является")
    if kind == "city_reference":
        city = stream.choice(CITIES)
        surface = city.capitalize() if register == "clean" else city
        return NegativeChunk("город", surface, "", "city_reference",
                             "город как место, а не как чей-то адрес; под 152-ФЗ "
                             "ст. 3 п. 1 он никого не определяет")
    if kind == "street_no_name":
        # Four phrasings, not one. Sixty copies of a single sentence is the v2
        # defect applied to the precision half: it would measure one string many
        # times and print the count as coverage.
        before, value, after = stream.choice((
            ("на", "улице", "холодно"), ("на", "улице", "дождь"),
            ("по", "улицам", "не пройти"), ("выйду на", "улицу", "подожду")))
        return NegativeChunk(before, value, after, "street_no_name",
                             "«улица» без имени — двор, погода, прогулка; "
                             "73 таких реплики в корпусе диспетчерской")
    if kind == "flat_as_home":
        before, value, after = stream.choice((
            ("", "квартиру", "снимаю"), ("", "квартиру", "убираю"),
            ("в", "квартире", "холодно"), ("", "квартиру", "недавно купили")))
        return NegativeChunk(before, value, after, "flat_as_home",
                             "«квартира» без номера — жильё, а не адрес")
    if kind == "entrance_no_street":
        number = stream.randint(2, 8)
        ordinal = (_spell_ordinal(number) if register == "voice_raw"
                   else f"подъезд {number}")
        return NegativeChunk("", f"{ordinal} подъезд" if register == "voice_raw"
                             else ordinal, "", "entrance_no_street",
                             "адресный хвост без адреса: улицы в реплике нет")
    if kind == "fare":
        before, value, after = stream.choice((
            ("", "проезд", "пятьдесят рублей"), ("", "проезд", "подорожал"),
            ("", "проезд", "оплатил картой"), ("за", "проезд", "наличными")))
        return NegativeChunk(before, value, after, "fare",
                             "«проезд» как плата, а не как тип улицы")
    raise InvalidCase(f"unknown negative kind {kind!r}")


# Negatives that may sit beside an address without becoming ambiguous. A bare
# «шестой подъезд» next to a real street is not a negative, it is part of the
# address, so those kinds are reserved for cases carrying no place at all.
NEG_WITH_ADDRESS: tuple[str, ...] = ("order_number", "room_number", "time_of_day",
                                     "quantity", "measure", "fare")
NEG_WITHOUT_ADDRESS: tuple[str, ...] = NEG_WITH_ADDRESS + (
    "city_reference", "street_no_name", "flat_as_home", "entrance_no_street")
# `voice_itn` is DEFINED by inverse text normalisation being on, so a case in it
# has to carry a digit somewhere; with none it is a `voice_raw` case in
# disguise, and the schema says so in as many words. These are the negative
# kinds that bring a number with them.
NEG_WITH_DIGITS: frozenset[str] = frozenset({
    "order_number", "room_number", "time_of_day", "quantity", "measure"})


def _negative_kinds(register: str, beside_address: bool) -> tuple[str, ...]:
    kinds = NEG_WITH_ADDRESS if beside_address else NEG_WITHOUT_ADDRESS
    if register != "voice_itn":
        return kinds
    return tuple(kind for kind in kinds if kind in NEG_WITH_DIGITS)


# --- the words around the value -------------------------------------------
#
# Verbatim from the two mined lexicons. The openers are the dispatch corpus's
# own distribution: 101 of 154 address replies open with NOTHING, which is why
# the empty string is in the pool and is drawn most often.

# The dispatch corpus's own opening distribution over its 154 address replies:
# 101 of them open with NOTHING. A generator that always writes «здравствуйте»
# is inventing a politeness the register does not have, and the empty opening is
# also the hardest one — there is no cue word in front of the value at all.
OPENERS: tuple[tuple[str, int], ...] = (
    ("", 101), ("здравствуйте", 27), ("а", 4), ("алло здравствуйте", 3),
    ("доброе утро", 2), ("здравствуйте а", 2), ("аа", 2), ("а здравствуйте", 2),
    ("алло", 1), ("девушка", 1), ("так", 1), ("ээ", 1), ("але а", 1),
    ("эээ", 4), ("ааа", 3), ("нуу", 2), ("слушай", 3), ("слышь", 1),
    ("значит", 2), ("короче", 2),
)
TAILS: tuple[str, ...] = (
    "поедем по городу", "частный дом", "до южной автостанции", "магазин магнит",
    "столовая", "заправка башнефть", "красный дом", "магазин пешеход",
    "новостройка со стороны стройки", "центральный вход",
)
ADDRESS_CUES: tuple[str, ...] = (
    "адрес", "по адресу", "я живу", "приезжайте", "записывай", "находится",
    "подъезжай", "приезжай", "адрес говорю",
)
PHONE_CUES: tuple[str, ...] = ("телефон", "номер телефона", "мой номер",
                               "перезвоните", "записывай телефон")
CONFIRMS: tuple[str, ...] = ("записал", "принял", "хорошо записываю", "так записал",
                             "ага записываю", "понял записываю")
FILLER_USER: tuple[str, ...] = (
    "ну что там", "долго ещё ждать", "а когда примерно", "ага понятно",
    "да да слушаю", "ну давайте", "хорошо жду", "а машина далеко",
    "ой подождите секунду", "всё нормально слышно", "секунду не отвлекайтесь",
    "я вас слушаю", "тут связь пропадала", "повторите пожалуйста",
    "нет всё в порядке", "давайте дальше", "я на месте жду", "сколько это займёт",
    "мне бы побыстрее", "ладно понял вас", "а можно попозже",
    "спасибо что дождались", "я перезвоню если что", "ничего страшного подожду",
)


# --- tools ----------------------------------------------------------------
#
# The schema is the PROVIDER's contract and is written out in full rather than
# generated, because a corpus that can only be replayed against our own harness
# is our opinion about ourselves.

def _tool(name: str, description: str,
          params: tuple[tuple[str, str], ...],
          required: tuple[str, ...]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    field: {"type": "string", "description": text}
                    for field, text in params
                },
                "required": list(required),
            },
        },
    }


TOOL_RIDE = _tool(
    "create_ride", "Оформить подачу машины по адресу клиента.",
    (("address", "адрес подачи целиком, как его назвал клиент"),
     ("destination", "куда ехать, если названо"),
     ("passenger_name", "имя пассажира"),
     ("phone", "телефон пассажира"),
     ("comment", "комментарий диспетчера: заказ, время, приметы")),
    ("address",))
TOOL_DELIVERY = _tool(
    "create_delivery", "Оформить доставку заказа получателю.",
    (("recipient_name", "получатель"), ("address", "адрес доставки"),
     ("phone", "телефон получателя"), ("order_id", "номер заказа")),
    ("recipient_name", "address"))
TOOL_VISIT = _tool(
    "book_visit", "Записать пациента на приём.",
    (("patient_name", "пациент"), ("birth_date", "дата рождения"),
     ("phone", "телефон"), ("address", "адрес пациента"),
     ("room", "кабинет приёма")),
    ("patient_name",))
TOOL_IDENTITY = _tool(
    "verify_identity", "Проверить личность клиента по документам.",
    (("full_name", "фамилия имя отчество, как названо"),
     ("passport", "серия и номер паспорта"), ("snils", "номер СНИЛС"),
     ("case_id", "номер обращения")),
    ("full_name",))
TOOL_CARD = _tool(
    "save_card", "Привязать карту к договору.",
    (("card_number", "номер карты"), ("holder_name", "держатель карты")),
    ("card_number",))
TOOL_CONTACT = _tool(
    "update_contact", "Обновить контактные данные абонента.",
    (("name", "имя абонента"), ("phone", "телефон"), ("email", "почта"),
     ("ticket", "номер обращения")),
    ("name",))
TOOL_VEHICLE = _tool(
    "register_vehicle", "Записать машину на сервис.",
    (("plate", "госномер"), ("owner_name", "владелец"), ("phone", "телефон"),
     ("slot", "время записи")),
    ("plate",))
TOOL_TAXPAYER = _tool(
    "register_taxpayer", "Завести плательщика по ИНН.",
    (("full_name", "фамилия имя отчество"), ("inn", "ИНН физического лица"),
     ("region", "код региона")),
    ("inn",))
TOOL_CALLBACK = _tool(
    "schedule_callback", "Поставить обратный звонок.",
    (("name", "как обращаться"), ("phone", "телефон для звонка"),
     ("slot", "во сколько перезвонить")),
    ("phone",))
TOOL_LOOKUP = _tool(
    "find_client", "Найти клиента в базе.",
    (("surname", "фамилия"), ("phone", "телефон, если назван")),
    ("surname",))


@dataclass(frozen=True)
class Domain:
    key: str
    system: str
    tools: tuple[dict[str, object], ...]


DOMAINS: dict[str, Domain] = {
    "taxi": Domain("taxi",
                   "Ты диспетчер службы такси. Принимаешь заказ голосом, "
                   "оформляешь подачу инструментом create_ride. Адрес клади в "
                   "инструмент ровно так, как его назвал клиент.",
                   (TOOL_RIDE, TOOL_LOOKUP)),
    "delivery": Domain("delivery",
                       "Ты оператор службы доставки. Оформляешь заказ "
                       "инструментом create_delivery.",
                       (TOOL_DELIVERY, TOOL_LOOKUP)),
    "clinic": Domain("clinic",
                     "Ты регистратор клиники. Записываешь пациента "
                     "инструментом book_visit.",
                     (TOOL_VISIT,)),
    "bank": Domain("bank",
                   "Ты оператор банка. Личность проверяешь инструментом "
                   "verify_identity, карту привязываешь save_card. Номера "
                   "документов вслух не повторяй.",
                   (TOOL_IDENTITY, TOOL_CARD)),
    "telecom": Domain("telecom",
                      "Ты оператор связи. Контакты абонента правишь "
                      "инструментом update_contact.",
                      (TOOL_CONTACT, TOOL_CALLBACK)),
    "autoservice": Domain("autoservice",
                          "Ты приёмщик автосервиса. Машину записываешь "
                          "инструментом register_vehicle.",
                          (TOOL_VEHICLE,)),
    "tax": Domain("tax",
                  "Ты помощник бухгалтера. Плательщика заводишь инструментом "
                  "register_taxpayer.",
                  (TOOL_TAXPAYER,)),
}


# --- drafts: a message before it knows where in the dialogue it sits -------

@dataclass(frozen=True)
class ItemSeed:
    """A gold item minus its offsets, which only `_compose` may hand out."""

    id: str
    type: str
    value: str
    canonical: str
    identity: str
    duty: str
    value_source: str
    spoken: bool
    tool_param: str


@dataclass(frozen=True)
class ItemDraft:
    seed: ItemSeed
    start: int
    end: int


@dataclass(frozen=True)
class NegDraft:
    value: str
    start: int
    end: int
    family: str
    why: str


@dataclass(frozen=True)
class MessageDraft:
    role: str
    content: str
    source: Source | None
    name: str
    items: tuple[ItemDraft, ...]
    negatives: tuple[NegDraft, ...]


@dataclass(frozen=True)
class CallSpec:
    name: str
    arguments: dict[str, str]
    judged_args: tuple[str, ...]
    item_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    register: str
    context: str
    provenance: Provenance
    cluster: str
    conversation_id: str
    domain: Domain
    drafts: tuple[MessageDraft, ...]
    calls: tuple[CallSpec, ...]
    final: FinalAnswer
    links: tuple[LinkExpectation, ...]
    annotators: int
    note: str


def _draft(pieces: tuple[object, ...], seeds: tuple[tuple[str, ItemSeed], ...],
           negatives: tuple[tuple[str, NegativeChunk], ...],
           source: Source | None, terminator: str) -> MessageDraft:
    """Lay a user line down and read its offsets off the composition.

    The equality check is not paranoia: a mis-keyed chunk is the one corpus bug
    that produces a plausible case with ground truth pointing at the wrong
    characters, and it reports as a gateway failure for ever.
    """
    laid = _spaced(pieces)
    if terminator:
        laid = laid + ((terminator, ""),)
    text, spans = _compose(laid)
    items: list[ItemDraft] = []
    for key, seed in seeds:
        start, end = spans[key]
        if text[start:end] != seed.value:
            raise InvalidCase(
                f"chunk {key!r} holds {text[start:end]!r} but the seed says "
                f"{seed.value!r}")
        items.append(ItemDraft(seed=seed, start=start, end=end))
    claims: list[NegDraft] = []
    for key, chunk in negatives:
        start, end = spans[key]
        if text[start:end] != chunk.value:
            raise InvalidCase(f"negative chunk {key!r} does not hold its value")
        claims.append(NegDraft(value=chunk.value, start=start, end=end,
                               family=chunk.family, why=chunk.why))
    return MessageDraft(role="user", content=text, source=source, name="",
                        items=tuple(items), negatives=tuple(claims))


# --- filler ---------------------------------------------------------------
#
# Nine replies in ten carry no personal data at all — the measured floor is
# 1.995% in the calls and 0.939% in the dispatch corpus. A long case whose every
# line holds a datum is not this register and inflates recall and precision at
# the same time, so the filler is real speech that claims nothing.

def _filler_pool() -> tuple[tuple[str, ...], tuple[str, ...]]:
    annotated = {str(row["key"]) for row in LABEL_ROWS}
    short: list[str] = []
    long: list[str] = []
    for text in dict.fromkeys(SPEECH_ORDER):
        key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
        if key in annotated or not _usable_filler(text):
            continue
        (long if len(text) >= 110 else short).append(text)
    return tuple(short), tuple(long)


FILLER_SHORT, FILLER_LONG = _filler_pool()


def _filler_message(register: str, long_form: bool, stream: random.Random) -> Message:
    """One customer line that carries nothing.

    In the speech registers it is a real RuDevices reply, carried with its source
    and its digest: CC BY 4.0, so the text ships. In `clean` it is authored,
    because the register is defined by capitals and full stops and a verbatim ASR
    line has neither.
    """
    if register == "clean":
        line = stream.choice(FILLER_USER)
        return Message(role="user", content=f"{line.capitalize()}.", source=None,
                       name="")
    pool = FILLER_LONG if long_form else FILLER_SHORT
    text = stream.choice(pool)
    return Message(role="user", content=text, source=_source(
        hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()), name="")


# The operator talks too, and in a long call they talk in paragraphs. Authored,
# because the corpus is one side of a dispatch line and holds no operator turns;
# long ones exist so a `deep` case reaches its character floor in forty messages
# instead of ninety — the floor is about how much text a context holds, not about
# how many times somebody said «ага».
OPERATOR_LONG: tuple[str, ...] = (
    "хорошо я вас понял сейчас посмотрю что у нас есть по свободным машинам и "
    "сразу отвечу подождите пожалуйста",
    "так записываю всё что вы говорите если я где-то ошибусь вы меня поправьте "
    "потому что связь сегодня не очень хорошая",
    "секундочку у меня тут система немного подвисает сейчас прогрузится и я всё "
    "оформлю как надо не отключайтесь",
    "да да я слушаю вас продолжайте говорите я записываю всё подряд а потом уже "
    "разберёмся что куда и в каком порядке",
    "понял вас сейчас уточню у старшего смены и вернусь буквально через пару "
    "минут только не кладите трубку",
    "хорошо тогда давайте так я пока оформлю то что есть а недостающее вы мне "
    "потом продиктуете когда вспомните",
)


def _anchor_filler(case_id: str, register: str, long_form: bool) -> Message:
    """The first filler line, chosen by the case's own ordinal.

    The engine derives a conversation identity from the first TWO messages when
    the caller names none, and the first of those is a system prompt shared by
    every dialogue an agent has. Two cases whose second message also matched
    would BE one conversation as far as the vault is concerned, and one
    customer's partial mention would resolve against another's — a corpus bug
    that reports as a gateway leak. Indexing by the ordinal makes the second
    message distinct by construction rather than by luck.
    """
    ordinal = int(case_id.rsplit("-", 1)[1])
    if register == "clean":
        # A pair of indices, so the opening is unique across the whole family
        # rather than modulo the pool: 298 and 348 landed on the same line and
        # the two cases shared a derived conversation.
        size = len(FILLER_USER)
        first = FILLER_USER[ordinal % size]
        second = FILLER_USER[(ordinal // size) % size]
        return Message(role="user",
                       content=f"{first.capitalize()}. {second.capitalize()}.",
                       source=None, name="")
    pool = FILLER_LONG if long_form else FILLER_SHORT
    text = pool[ordinal % len(pool)]
    return Message(role="user", content=text, source=_source(
        hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()), name="")


def _operator_message(register: str, long_form: bool,
                      stream: random.Random) -> Message:
    if long_form:
        line = stream.choice(OPERATOR_LONG)
    else:
        line = stream.choice(CONFIRMS + ("сейчас посмотрю", "минуту",
                                         "да слушаю вас", "хорошо", "понял вас",
                                         "уточняю"))
    if register == "clean":
        return Message(role="assistant", content=f"{line.capitalize()}.",
                       source=None, name="")
    return Message(role="assistant", content=line, source=None, name="")


def _place(spec: CaseSpec,
           stream: random.Random) -> tuple[tuple[Message, ...], tuple[int, ...]]:
    """The whole transcript, and where the value-bearing lines landed in it.

    The positions are RETURNED rather than searched for afterwards. Looking a
    draft up by its own text would break the moment a filler reply happened to
    repeat it, and «the ground truth points at the wrong message» is a corpus
    bug that reads exactly like a gateway failure.

    The last message is never an assistant turn — that turn is what the run
    produces, and a scripted one there would be the answer under test. Tail
    filler is therefore added as (assistant, user) pairs.
    """
    system = Message(role="system", content=spec.domain.system, source=None, name="")
    body = [Message(role=draft.role, content=draft.content, source=draft.source,
                    name=draft.name) for draft in spec.drafts]
    if spec.context == "solo":
        if len(body) != 1:
            raise InvalidCase(f"{spec.case_id}: `solo` holds one line, not {len(body)}")
        return (system, *body), (1,)

    head_pairs, tail_pairs, long_form = {
        "short": (1, 0, False),
        "long": (4, 1, False),
        "deep": (9, 2, True),
    }[spec.context]

    def render(head: int, tail: int) -> tuple[tuple[Message, ...], tuple[int, ...]]:
        messages = [system]
        for position in range(head):
            messages.append(
                _anchor_filler(spec.case_id, spec.register, long_form)
                if position == 0
                else _filler_message(spec.register, long_form, stream))
            messages.append(_operator_message(spec.register, long_form, stream))
        # The operator answers BETWEEN the customer's lines. Two value-bearing
        # user turns back to back is legal on the wire and is not how a call
        # goes, and the second mention in a `same` link only means anything if
        # something happened in between.
        placed: list[int] = []
        for position, message in enumerate(body):
            if position:
                messages.append(_operator_message(spec.register, long_form, stream))
            placed.append(len(messages))
            messages.append(message)
        for _ in range(tail):
            messages.append(_operator_message(spec.register, long_form, stream))
            messages.append(_filler_message(spec.register, long_form, stream))
        return tuple(messages), tuple(placed)

    messages, positions = render(head_pairs, tail_pairs)
    if spec.context != "deep":
        return messages, positions
    # `deep` carries a character floor as well as a message count, because the
    # median utterance here is 36 characters and thirty two-word replies are not
    # a long context. Grown rather than guessed: the pool's line lengths vary.
    while len(messages) < 33 or sum(len(m.content) for m in messages) < 4_300:
        head_pairs += 1
        if head_pairs > 45:
            raise InvalidCase(f"{spec.case_id}: `deep` could not reach the "
                              f"character floor within 60 messages")
        messages, positions = render(head_pairs, tail_pairs)
    return messages, positions


def _build_case(spec: CaseSpec, stream: random.Random) -> Case:
    messages, positions = _place(spec, stream)

    items: list[PiiItem] = []
    negatives: list[Negative] = []
    for index, draft in enumerate(spec.drafts):
        position = positions[index]
        for item in draft.items:
            seed = item.seed
            items.append(PiiItem(
                id=seed.id, type=seed.type, value=seed.value,
                canonical=seed.canonical, start=item.start, end=item.end,
                msg=position, identity=seed.identity, duty=seed.duty,
                value_source=seed.value_source, spoken=seed.spoken,
                tool_param=seed.tool_param))
        for negative in draft.negatives:
            negatives.append(Negative(value=negative.value, start=negative.start,
                                      end=negative.end, msg=position,
                                      family=negative.family, why=negative.why))

    position_of = {item.id: item.msg for item in items}
    calls = tuple(ExpectedCall(
        name=call.name, arguments=call.arguments, judged_args=call.judged_args,
        pii_items=call.item_ids,
        after_msg=max(position_of[item_id] for item_id in call.item_ids))
        for call in spec.calls)

    return Case(
        id=spec.case_id, family=FAMILY, register=spec.register,
        context=spec.context, provenance=spec.provenance, cluster=spec.cluster,
        conversation_id=spec.conversation_id, messages=messages,
        tools=spec.domain.tools, pii=tuple(items), negatives=tuple(negatives),
        links=spec.links, calls=calls, final=spec.final, preceded_by="",
        annotators=spec.annotators, adjudicated=False, note=spec.note)


# --- the verbatim layer ---------------------------------------------------
#
# The one place a message's text is not this module's: it is a RuDevices reply
# and the gold span is the hand annotation over that exact string. Offsets are
# located by scanning forward from the previous span rather than by a bare
# `find`, so a reply naming two places does not point both spans at the first.

def _verbatim_addresses() -> tuple[tuple[str, str, tuple[tuple[int, int], ...], str], ...]:
    """(key, text, spans, stratum) for every hand-labelled address reply."""
    rows: list[tuple[str, str, tuple[tuple[int, int], ...], str]] = []
    for row in LABEL_ROWS:
        if row.get("label") != "адрес с номером" or not row.get("spans"):
            continue
        text = str(row["text"])
        # A hand annotation says what it CLAIMS and is silent about the rest.
        # 7 of 168 annotated rows carry a surname or a second address outside
        # their span, and neither can be repaired by claiming it — ground truth
        # is what the generator built, never what a search of the finished string
        # finds. So the row is refused. `schema.unsafe_outside` is the same screen
        # the audit condemns filler with, applied where the material is chosen.
        if unsafe_outside(text, [str(s) for s in row["spans"]]):  # type: ignore[union-attr]
            continue
        offsets: list[tuple[int, int]] = []
        cursor = 0
        for span in row["spans"]:            # type: ignore[union-attr]
            found = text.find(str(span), cursor)
            if found < 0:
                raise InvalidCase(
                    f"annotation {row['key']} claims {span!r}, which its own text "
                    f"does not contain — the labels and the corpus have drifted")
            offsets.append((found, found + len(str(span))))
            cursor = found + len(str(span))
        rows.append((str(row["key"]), text, tuple(offsets), str(row["filter"])))
    return tuple(rows)


def _verbatim_streets() -> tuple[tuple[str, str, tuple[tuple[int, int], ...], str], ...]:
    """The `улица без номера` layer: a street nobody lives at yet.

    Hundreds of buildings stand on it, so it identifies nobody under 152-ФЗ
    ст. 3 п. 1 — `optional`, in its own column, never folded into recall. This
    is the class that made one number read 71% while the two halves were 94%
    and 47%.
    """
    rows: list[tuple[str, str, tuple[tuple[int, int], ...], str]] = []
    for row in LABEL_ROWS:
        if row.get("label") != "улица без номера" or not row.get("spans"):
            continue
        text = str(row["text"])
        # A hand annotation says what it CLAIMS and is silent about the rest.
        # 7 of 168 annotated rows carry a surname or a second address outside
        # their span, and neither can be repaired by claiming it — ground truth
        # is what the generator built, never what a search of the finished string
        # finds. So the row is refused. `schema.unsafe_outside` is the same screen
        # the audit condemns filler with, applied where the material is chosen.
        if unsafe_outside(text, [str(s) for s in row["spans"]]):  # type: ignore[union-attr]
            continue
        offsets: list[tuple[int, int]] = []
        cursor = 0
        for span in row["spans"]:            # type: ignore[union-attr]
            found = text.find(str(span), cursor)
            if found < 0:
                continue
            offsets.append((found, found + len(str(span))))
            cursor = found + len(str(span))
        if offsets:
            rows.append((str(row["key"]), text, tuple(offsets), str(row["filter"])))
    return tuple(rows)


# The trap vocabulary, declared here and NOT taken from our recognizers. Its job
# is to point at the word inside a reply a human already judged «не адрес»; a
# probe built from the detector would only ever find what the detector finds,
# which is the mistake that made the first voice set report 100% for 38.6%.
_TRAPS: tuple[tuple[str, str, str], ...] = (
    ("entrance_no_street",
     r"\b(перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|последн|углов)\w*"
     r"\s+подъезд\w*\b",
     "порядковое с подъездом, но улицы в реплике нет — адресный хвост без адреса"),
    ("room_number",
     r"\b(перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|одиннадцат)\w*"
     r"\s+(этаж\w*|кабинет\w*|отделени\w*)\b",
     "число рядом с этажом, кабинетом или отделением: 528 таких реплик в корпусе "
     "звонков, крупнейший источник ложных срабатываний"),
    ("street_no_name", r"\bна улиц[еу]\b|\bпо улиц[еа]м\b|\bулиц[аыу]\b",
     "«улица» без имени — двор, погода, прогулка"),
    ("flat_as_home", r"\bквартир[аыуе]\b|\bквартирой\b",
     "«квартира» без номера — покупка, аренда, уборка"),
    ("fare", r"\bпроезд\b", "«проезд» как плата, а не как тип улицы"),
    ("quantity",
     r"\b(один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять|"
     r"двадцать|тридцать|сорок|пятьдесят|сто|двести)\s+"
     r"(лет|года|год|минут|минуты|рублей|рубля|раз|раза|тысяч|тысячи|процентов|"
     r"дня|дней|часа|часов|недели|месяца|месяцев|человек|штук|штуки)\b",
     "числительное с единицей счёта — не номер дома"),
    ("measure",
     r"\b(один|два|три|четыре|пять|шесть|семь|восемь|девять|десять|двадцать|сто)"
     r"\s+(метров|метра|километров|километра|градусов|килограмм|грамм|гектаров|"
     r"литра|литров)\b",
     "число с единицей измерения — не номер дома"),
)


def _verbatim_negatives() -> tuple[tuple[str, str, int, int, str, str], ...]:
    """(key, text, start, end, family, why) over replies a human called «не адрес».

    Two filters beyond the label, and both are about what the corpus may ship
    rather than about detection: obscenity, and any reply that looks like it
    names a person. An unlabelled name in a negative reply is a datum nobody
    claimed, and it would score as a false mask against a gateway that was right.
    """
    compiled = tuple((family, re.compile(pattern), why)
                     for family, pattern, why in _TRAPS)
    rows: list[tuple[str, str, int, int, str, str]] = []
    for row in LABEL_ROWS:
        if row.get("label") != "не адрес":
            continue
        text = str(row["text"])
        # `unsafe_person` and NOT `unsafe_filler`: these rows are chosen
        # BECAUSE they hold something address-shaped, so the street half of the
        # screen would empty the trap pool. A person in them is still a leak.
        if (_OBSCENE.search(text) or _looks_personal(text)
                or unsafe_person(text) or numeral_run(text) >= 4):
            continue
        for family, pattern, why in compiled:
            match = pattern.search(text)
            if match:
                rows.append((str(row["key"]), text, match.start(), match.end(),
                             family, why))
                break
    return tuple(rows)


VERBATIM_ADDRESSES = _verbatim_addresses()
VERBATIM_STREETS = _verbatim_streets()
VERBATIM_NEGATIVES = _verbatim_negatives()


def _negative_draft(row: tuple[str, str, int, int, str, str]) -> MessageDraft:
    key, text, start, end, family, why = row
    return MessageDraft(
        role="user", content=text, source=_source(key), name="", items=(),
        negatives=(NegDraft(value=text[start:end], start=start, end=end,
                            family=family, why=why),))


def _verbatim_provenance(key: str, stratum: str) -> Provenance:
    """`marker` and `random` are not interchangeable and the weight says so.

    The marker layer was selected by the same surface cues the detector reads and
    is biased upward by construction; the number layer is 250 read out of 4805,
    so every share over it is nineteen times smaller than it looks unless
    `weighted_rate` is given the 19.22.
    """
    if stratum == "marker":
        return Provenance(kind="verbatim", corpus="speech_rudevices", key=key,
                          shape="", selection="marker", weight=1.0,
                          licence=RUDEVICES_LICENCE)
    return Provenance(kind="verbatim", corpus="speech_rudevices", key=key,
                      shape="", selection="random", weight=NUMBER_SAMPLE_WEIGHT,
                      licence=RUDEVICES_LICENCE)


# --- drawing values -------------------------------------------------------

def _weighted(rows: tuple[tuple[object, int], ...], stream: random.Random) -> object:
    """A draw that follows the MINED frequency, not a uniform one.

    Uniform would give «фамилия имя отчество» the same mass as a lone surname,
    and the corpus counts them 23 against 350. A generator that flattens the
    distribution measures the rare shape as often as the common one and reports
    an average that describes neither.
    """
    total = sum(weight for _, weight in rows)
    ticket = stream.randrange(total)
    running = 0
    for value, weight in rows:
        running += weight
        if ticket < running:
            return value
    return rows[-1][0]


# Shape, draw weight, corpus, selection, sampling weight. The dispatch shares
# are the marker stratum's own counts; the number layer contributes the one
# shape it holds, and it is the reason LOC is not a marker-only type.
ADDRESS_SHAPES: tuple[tuple[tuple[str, str, str, float], int], ...] = (
    ((S_ADDR_ENTRANCE, "speech_rudevices", "marker", 1.0), 53),
    ((S_ADDR_BARE, "speech_rudevices", "marker", 1.0), 16),
    ((S_ADDR_STREET_WORD, "speech_rudevices", "marker", 1.0), 10),
    ((S_ADDR_PROEZD, "speech_rudevices", "marker", 1.0), 5),
    ((S_ADDR_PROSPEKT, "speech_rudevices", "marker", 1.0), 4),
    ((S_ADDR_LETTER, "speech_rudevices", "marker", 1.0), 4),
    ((S_ADDR_KORPUS, "speech_rudevices", "marker", 1.0), 4),
    ((S_ADDR_LETTER_ENTRANCE, "speech_rudevices", "marker", 1.0), 3),
    ((S_ADDR_PEREULOK_DOM, "speech_rudevices", "marker", 1.0), 3),
    ((S_ADDR_STREET_DOM, "speech_rudevices", "marker", 1.0), 3),
    ((S_ADDR_SHOSSE, "speech_rudevices", "marker", 1.0), 3),
    ((S_ADDR_BARE, "speech_rudevices", "random", NUMBER_SAMPLE_WEIGHT), 26),
    ((S_ADDR_FLAT, "speech_rudevices", "census", 1.0), 6),
    ((S_ADDR_STROENIE, "speech_rudevices", "census", 1.0), 4),
)
# The calls corpus was read whole by the miner, so its shapes are `census`. Its
# central fact is `naked_values`: 26 of 44 address values carry neither a street
# type word nor «дом».
CALL_ADDRESS_SHAPES: tuple[tuple[tuple[str, str, str, float], int], ...] = (
    ((S_CALL_NAKED, "speech_calls", "census", 1.0), 26),
    ((S_CALL_DOM, "speech_calls", "census", 1.0), 10),
    ((S_CALL_TYPE_LAST, "speech_calls", "census", 1.0), 8),
    ((S_CALL_TYPE_FIRST, "speech_calls", "census", 1.0), 6),
    ((S_CALL_ASR, "speech_calls", "census", 1.0), 9),
    ((S_CALL_LETTER, "speech_calls", "census", 1.0), 5),
    ((S_CALL_FLAT, "speech_calls", "census", 1.0), 3),
    ((S_CALL_CITY, "speech_calls", "census", 1.0), 2),
)

_LETTER_SHAPES = (S_ADDR_LETTER, S_ADDR_LETTER_ENTRANCE, S_CALL_LETTER)
_ENTRANCE_SHAPES = (S_ADDR_ENTRANCE, S_ADDR_LETTER_ENTRANCE)
_FLAT_SHAPES = (S_ADDR_FLAT, S_CALL_FLAT)


def _address_for_shape(shape: str, stream: random.Random) -> Address:
    if shape in (S_CALL_TYPE_FIRST, S_CALL_TYPE_LAST, S_CALL_CITY):
        street_type = str(_weighted((("улица", 14), ("проспект", 4),
                                     ("переулок", 3), ("бульвар", 2),
                                     ("проезд", 2)), stream))
    elif shape == S_ADDR_PROEZD:
        street_type = "проезд"
    elif shape == S_ADDR_PROSPEKT:
        street_type = "проспект"
    elif shape == S_ADDR_PEREULOK_DOM:
        street_type = "переулок"
    elif shape in (S_ADDR_STREET_WORD, S_ADDR_STREET_DOM):
        street_type = "улица"
    elif shape == S_ADDR_SHOSSE:
        street_type = "шоссе"
    else:
        street_type = ""
    return Address(
        street=_street_for(street_type, stream), street_type=street_type,
        house=stream.randint(1, 160),
        letter=stream.choice(HOUSE_LETTERS) if shape in _LETTER_SHAPES else "",
        entrance=stream.randint(1, 8) if shape in _ENTRANCE_SHAPES else 0,
        flat=stream.randint(1, 99) if shape in _FLAT_SHAPES else 0,
        korpus=stream.randint(1, 6) if shape == S_ADDR_KORPUS else 0,
        stroenie=stream.randint(1, 5) if shape == S_ADDR_STROENIE else 0,
        city=stream.choice(CITIES) if shape == S_CALL_CITY else "")


NAME_LAYOUTS: tuple[tuple[tuple[tuple[str, ...], str], int], ...] = (
    ((("surname",), S_NAME_SURNAME), 350),
    ((("given",), S_NAME_GIVEN), 255),
    ((("given", "patronymic"), S_NAME_GIVEN_PATR), 109),
    ((("diminutive",), S_NAME_GIVEN), 70),
    ((("given", "short"), S_NAME_GIVEN_PATR), 45),
    ((("patronymic",), S_NAME_PATR), 29),
    ((("given", "surname"), S_NAME_GIVEN_SURNAME), 23),
    ((("surname", "given", "patronymic"), S_NAME_FIO), 23),
    ((("surname", "given"), S_NAME_SURNAME_GIVEN), 7),
    ((("given", "patronymic", "surname"), S_NAME_GIVEN_PATR_SURNAME), 4),
)

# Prefix, grammatical case, the shape the prefix itself is, whether it demands a
# surname. «@role» and «@kin» draw a word: the commonest thing in front of a
# surname is not a cue but a rank — 75 occurrences against 20 for «меня зовут».
NAME_WRAPPERS: tuple[tuple[tuple[str, str, str, bool], int], ...] = (
    ((("", "nom", "", False)), 60),
    ((("@role", "nom", S_NAME_ROLE, True)), 22),
    ((("меня зовут", "nom", S_NAME_CALLED, False)), 12),
    ((("это", "nom", S_NAME_THIS, False)), 10),
    ((("к", "dat", S_NAME_DATIVE, True)), 9),
    ((("моя фамилия", "nom", S_NAME_MY_SURNAME, True)), 7),
    ((("фамилия", "nom", S_NAME_SURNAME_CUE, True)), 7),
    ((("говорит", "nom", S_NAME_SPEAKS, False)), 6),
    ((("передайте", "dat", S_NAME_DATIVE, False)), 6),
    ((("@kin", "nom", S_NAME_KIN, False)), 5),
    ((("будьте добры", "acc", S_NAME_GIVEN, False)), 5),
    ((("запишите на", "acc", S_NAME_GIVEN, False)), 5),
)


def _draw_person(stream: random.Random,
                 needs_patronymic: bool) -> tuple[Person, tuple[str, str, str]]:
    pool = _weighted(((MALE, 45), (FEMALE, 35), (FOREIGN, 20)), stream)
    person = stream.choice(pool)          # type: ignore[arg-type]
    if needs_patronymic and not person.patronymic[0]:
        person = stream.choice(MALE + FEMALE)
    return person, stream.choice(DIMINUTIVES)


def _name_message(person: Person, layout: tuple[str, ...], shape: str,
                  register: str, stream: random.Random,
                  diminutive: tuple[str, str, str]) -> tuple[str, Rendered, str]:
    """(prefix words, the rendered name, the shape that names this form)."""
    wrapper = _weighted(NAME_WRAPPERS, stream)
    prefix, grammar, wrapper_shape, needs_surname = wrapper  # type: ignore[misc]
    if needs_surname and "surname" not in layout:
        prefix, grammar, wrapper_shape = "", "nom", ""
    if register in ("sloppy", "clean"):
        # Written registers name a person in the nominative; the oblique forms
        # are a property of speech, where 15% of mentions arrive declined.
        grammar = "nom"
    if prefix == "@role":
        prefix = stream.choice(ROLES)
    elif prefix == "@kin":
        # «брат ольга» is not a thing anybody says. The kinship word agrees with
        # the person it stands in front of, and getting that wrong makes the
        # sentence read as generated, which is the whole failure mode of v2.
        prefix = stream.choice(KINSHIP_MALE if person.gender == "m"
                               else KINSHIP_FEMALE)
    prefix = _around(prefix, register, stream)
    damage = {"sloppy": "typo", "voice_raw": "none"}.get(register, "none")
    if register == "voice_raw" and stream.randrange(100) < 12:
        damage = "asr"
    if prefix == "меня зовут" and ("patronymic" in layout or "short" in layout):
        wrapper_shape = S_NAME_CALLED_PATR
    rendered = _render_name(person, layout, grammar, register, damage,
                            diminutive, stream)
    return prefix, rendered, wrapper_shape or shape


def _seed(case_id: str, slot: str, kind: str, rendered: Rendered, duty: str,
          value_source: str, tool_param: str) -> ItemSeed:
    return ItemSeed(id=f"{slot}", type=kind, value=rendered.surface,
                    canonical=rendered.canonical,
                    identity=f"{case_id}:{slot}", duty=duty,
                    value_source=value_source, spoken=rendered.spoken,
                    tool_param=tool_param)


# --- scenarios ------------------------------------------------------------
#
# Each returns a CaseSpec. None of them consults the detector to decide what to
# label: the ground truth is what the builder placed, which is the only
# construction under which «what could never get into this set» is answerable.

def _conversation_id(case_id: str, index: int) -> str:
    """Half the corpus names its conversation, half makes the harness derive one.

    Both paths exist in the product — a customer gateway with no conversation
    field triggers the derived one — and a corpus carrying only one of them
    leaves the other untested. `validate_corpus` refuses a corpus that does.
    """
    return f"conv-{case_id}" if index % 2 == 0 else ""


def _opener(register: str, stream: random.Random) -> str:
    if register == "clean":
        return ""
    return _around(str(_weighted(OPENERS, stream)), register, stream)


def _around(word: str, register: str, stream: random.Random) -> str:
    """Damage applied to the words BESIDE a value, never inside one.

    Only in `voice_raw`: the stretched vowel and the glued particle are what a
    human transcriber writes down when a mouth produces them, and they exist in
    no written register at all.
    """
    if register != "voice_raw":
        return word
    return _speech_noise(word, stream)


def _scenario_verbatim(case_id: str, register: str, context: str, index: int,
                       row: tuple[str, str, tuple[tuple[int, int], ...], str],
                       negative: tuple[str, str, int, int, str, str],
                       stream: random.Random) -> CaseSpec:
    key, text, offsets, stratum = row
    items: list[ItemDraft] = []
    for position, (start, end) in enumerate(offsets):
        value = text[start:end]
        items.append(ItemDraft(
            seed=ItemSeed(id=f"loc{position}", type="LOC", value=value,
                          canonical=value, identity=f"{case_id}:loc{position}",
                          duty="required", value_source="corpus", spoken=True,
                          tool_param="address" if position == 0 else "destination"),
            start=start, end=end))
    draft = MessageDraft(role="user", content=text, source=_source(key), name="",
                         items=tuple(items), negatives=())
    arguments = {"address": items[0].seed.value}
    judged = ["address"]
    consumed = ["loc0"]
    if len(items) > 1:
        arguments["destination"] = items[1].seed.value
        judged.append("destination")
        consumed.append("loc1")
    arguments["comment"] = "по звонку"
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=_verbatim_provenance(key, stratum),
        cluster=f"rudevices:{key}", conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS["taxi"], drafts=(draft, _negative_draft(negative)),
        calls=(CallSpec(name="create_ride", arguments=arguments,
                        judged_args=tuple(judged), item_ids=tuple(consumed)),),
        final=FinalAnswer(must_contain=(items[0].seed.value,) if index % 3 == 0 else (),
                          must_not_contain=(), answer=""),
        links=(), annotators=1,
        note=f"настоящая реплика диспетчерской ({stratum}), адрес размечен "
             f"вручную; вторая реплика — размеченный человеком «не адрес»")


def _scenario_verbatim_street(case_id: str, register: str, context: str,
                              index: int,
                              row: tuple[str, str, tuple[tuple[int, int], ...], str],
                              negative: tuple[str, str, int, int, str, str],
                              stream: random.Random) -> CaseSpec:
    key, text, offsets, stratum = row
    start, end = offsets[0]
    value = text[start:end]
    draft = MessageDraft(
        role="user", content=text, source=_source(key), name="",
        items=(ItemDraft(seed=ItemSeed(
            id="loc0", type="LOC", value=value, canonical=value,
            identity=f"{case_id}:loc0", duty="optional", value_source="corpus",
            spoken=True, tool_param=""), start=start, end=end),),
        negatives=())
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=_verbatim_provenance(key, stratum),
        cluster=f"rudevices:{key}", conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS["taxi"], drafts=(draft, _negative_draft(negative)),
        calls=(), final=FinalAnswer((), (), ""), links=(), annotators=1,
        note="улица без номера: сотни зданий стоят на ней, никого не определяет — "
             "маскировать не ошибка, пропустить не утечка, колонка своя")


def _address_draft(case_id: str, slot: str, register: str, shape: str,
                   address: Address, tool_param: str, negative_kind: str,
                   stream: random.Random) -> MessageDraft:
    rendered = _render_address(address, shape, register, stream)
    negative = _negative_chunk(negative_kind, register, stream)
    cue = ("" if stream.randrange(100) < 55
           else _around(stream.choice(ADDRESS_CUES), register, stream))
    tail = "" if stream.randrange(100) < 70 else stream.choice(TAILS)
    if register == "clean":
        pieces: tuple[object, ...] = (
            "Адрес", (rendered.surface, "loc"), *negative.pieces("neg"))
        terminator = "."
    else:
        pieces = (_opener(register, stream), cue, (rendered.surface, "loc"), tail,
                  *negative.pieces("neg"))
        terminator = ""
    seed = _seed(case_id, slot, "LOC", rendered, "required", "pool", tool_param)
    return _draft(pieces, (("loc", seed),), (("neg", negative),), None, terminator)


def _scenario_address(case_id: str, register: str, context: str, index: int,
                      table: tuple[tuple[tuple[str, str, str, float], int], ...],
                      stream: random.Random) -> CaseSpec:
    shape, corpus, selection, weight = _weighted(table, stream)  # type: ignore[misc]
    address = _address_for_shape(shape, stream)
    negative_kind = stream.choice(_negative_kinds(register, True))
    domain_key = str(_weighted((("taxi", 6), ("delivery", 3), ("clinic", 1)), stream))
    tool = {"taxi": ("create_ride", "address"),
            "delivery": ("create_delivery", "address"),
            "clinic": ("book_visit", "address")}[domain_key]
    draft = _address_draft(case_id, "loc0", register, shape, address, tool[1],
                           negative_kind, stream)
    value = draft.items[0].seed.canonical
    arguments = {tool[1]: value}
    if tool[0] == "create_delivery":
        arguments["order_id"] = "A-4471"
    elif tool[0] == "create_ride":
        arguments["comment"] = "по звонку"
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=Provenance(kind="recombined", corpus=corpus, key="", shape=shape,
                              selection=selection, weight=weight,
                              licence=RUDEVICES_LICENCE if corpus == "speech_rudevices"
                              else "CC BY-NC 4.0"),
        cluster=f"addr:{value}", conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS[domain_key], drafts=(draft,),
        calls=(CallSpec(name=tool[0], arguments=arguments, judged_args=(tool[1],),
                        item_ids=("loc0",)),),
        final=FinalAnswer(must_contain=(value,) if index % 4 == 0 else (),
                          must_not_contain=(), answer=""),
        links=(), annotators=0,
        note=f"адрес формой «{shape}» из {corpus}, значения из пулов; "
             f"негатив рядом — {negative_kind}")


def _scenario_name(case_id: str, register: str, context: str, index: int,
                   stream: random.Random) -> CaseSpec:
    layout, layout_shape = _weighted(NAME_LAYOUTS, stream)  # type: ignore[misc]
    person, diminutive = _draw_person(
        stream, needs_patronymic="patronymic" in layout or "short" in layout)
    if "short" in layout and not person.short_patronymic:
        person = stream.choice(tuple(p for p in MALE if p.short_patronymic))
    prefix, rendered, shape = _name_message(person, layout, layout_shape, register,
                                            stream, diminutive)
    negative_kind = stream.choice(_negative_kinds(register, False))
    negative = _negative_chunk(negative_kind, register, stream)
    if register == "clean":
        pieces: tuple[object, ...] = (prefix.capitalize() or "Клиент",
                                      (rendered.surface, "name"),
                                      *negative.pieces("neg"))
        terminator = "."
    else:
        pieces = (_opener(register, stream), prefix, (rendered.surface, "name"),
                  *negative.pieces("neg"))
        terminator = ""
    if layout == ("surname",):
        domain_key, tool_name, param = "delivery", "find_client", "surname"
    else:
        domain_key, tool_name, param = str(_weighted(
            (("telecom|update_contact|name", 4), ("clinic|book_visit|patient_name", 3),
             ("delivery|create_delivery|recipient_name", 2),
             ("telecom|schedule_callback|name", 2)), stream)).split("|")
    seed = _seed(case_id, "name0", "NAME", rendered, "required", "pool", param)
    draft = _draft(pieces, (("name", seed),), (("neg", negative),), None, terminator)
    arguments = {param: rendered.canonical}
    if tool_name == "create_delivery":
        arguments["order_id"] = "A-4471"
    if tool_name == "schedule_callback":
        arguments["slot"] = "после обеда"
    drafts = [draft]
    links: list[LinkExpectation] = []
    if context != "solo" and stream.randrange(100) < 35:
        # The same person named twice, in two different forms. One identity must
        # reach the model as ONE substitute; a gateway that mints two has broken
        # the dialogue without erroring, and nothing else in the corpus sees it.
        second = _render_name(person, layout, "dat" if register in SPEECH_REGISTERS
                              else "nom", register, "none", diminutive, stream)
        again = _negative_chunk(stream.choice(_negative_kinds(register, False)),
                                register, stream)
        second_seed = ItemSeed(
            id="name1", type="NAME", value=second.surface,
            canonical=second.canonical, identity=f"{case_id}:name0",
            duty="required", value_source="pool", spoken=False, tool_param="")
        second_pieces: tuple[object, ...] = (
            ("Ещё раз" if register == "clean" else "ещё раз"),
            (second.surface, "name"), *again.pieces("neg"))
        drafts.append(_draft(second_pieces, (("name", second_seed),),
                             (("neg", again),), None,
                             "." if register == "clean" else ""))
        links.append(LinkExpectation(
            left="name0", right="name1", kind="same", case="",
            why="один человек назван дважды в одном разговоре: одна личность — "
                "одна подмена, и это решает шлюз, а не модель"))
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=shape, selection="census", weight=1.0,
                              licence="CC BY-NC 4.0"),
        cluster=f"name:{rendered.canonical}",
        conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS[domain_key], drafts=tuple(drafts),
        calls=(CallSpec(name=tool_name, arguments=arguments, judged_args=(param,),
                        item_ids=("name0",)),),
        final=FinalAnswer(must_contain=(rendered.canonical,) if index % 5 == 0 else (),
                          must_not_contain=(), answer=""),
        links=tuple(links), annotators=0,
        note=f"имя формой «{shape}», слоты {'+'.join(layout)}; "
             f"негатив — {negative_kind}")


def _scenario_name_address(case_id: str, register: str, context: str, index: int,
                           stream: random.Random) -> CaseSpec:
    """A person and a place in one dialogue — the ordinary shape of an order.

    In about two cases in five the place belongs to somebody ELSE (a recipient),
    which is the only way this family states a `different` link: two people, two
    substitutes, and a gateway that merges them writes one customer's row for the
    other one.
    """
    shape, corpus, selection, weight = _weighted(
        ADDRESS_SHAPES + CALL_ADDRESS_SHAPES, stream)   # type: ignore[misc]
    address = _address_for_shape(shape, stream)
    layout, layout_shape = _weighted(NAME_LAYOUTS, stream)   # type: ignore[misc]
    person, diminutive = _draw_person(
        stream, needs_patronymic="patronymic" in layout or "short" in layout)
    if "short" in layout and not person.short_patronymic:
        person = stream.choice(tuple(p for p in MALE if p.short_patronymic))
    prefix, rendered_name, name_shape = _name_message(
        person, layout, layout_shape, register, stream, diminutive)
    rendered_place = _render_address(address, shape, register, stream)
    negative = _negative_chunk(stream.choice(_negative_kinds(register, True)),
                               register, stream)
    name_seed = _seed(case_id, "name0", "NAME", rendered_name, "required", "pool",
                      "recipient_name")
    place_seed = _seed(case_id, "loc0", "LOC", rendered_place, "required", "pool",
                       "address")
    if register == "clean":
        pieces: tuple[object, ...] = (
            "Доставка на имя", (rendered_name.surface, "name"), ", адрес",
            (rendered_place.surface, "loc"), *negative.pieces("neg"))
        terminator = "."
    else:
        pieces = (_opener(register, stream), prefix,
                  (rendered_name.surface, "name"),
                  "" if stream.randrange(100) < 50 else stream.choice(ADDRESS_CUES),
                  (rendered_place.surface, "loc"), *negative.pieces("neg"))
        terminator = ""
    draft = _draft(pieces, (("name", name_seed), ("loc", place_seed)),
                   (("neg", negative),), None, terminator)
    links: list[LinkExpectation] = []
    drafts = [draft]
    if context != "solo" and stream.randrange(100) < 40:
        other, other_diminutive = _draw_person(stream, needs_patronymic=False)
        other_rendered = _render_name(other, ("given", "surname"), "nom", register,
                                      "none", other_diminutive, stream)
        second_negative = _negative_chunk(
            stream.choice(_negative_kinds(register, False)), register, stream)
        other_seed = ItemSeed(
            id="name1", type="NAME", value=other_rendered.surface,
            canonical=other_rendered.canonical, identity=f"{case_id}:name1",
            duty="required", value_source="pool", spoken=False, tool_param="")
        second_pieces: tuple[object, ...] = (
            ("Заказ примет" if register == "clean" else "заберёт"),
            (other_rendered.surface, "name"), *second_negative.pieces("neg"))
        drafts.append(_draft(second_pieces, (("name", other_seed),),
                             (("neg", second_negative),), None,
                             "." if register == "clean" else ""))
        links.append(LinkExpectation(
            left="name0", right="name1", kind="different", case="",
            why="два разных человека в одном разговоре обязаны получить РАЗНЫЕ "
                "подмены; слияние отдаёт строку одного клиента в дело другого"))
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=Provenance(kind="recombined", corpus=corpus, key="", shape=shape,
                              selection=selection, weight=weight,
                              licence=RUDEVICES_LICENCE if corpus == "speech_rudevices"
                              else "CC BY-NC 4.0"),
        cluster=f"pair:{rendered_name.canonical}:{rendered_place.canonical}",
        conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS["delivery"], drafts=tuple(drafts),
        calls=(CallSpec(name="create_delivery",
                        arguments={"recipient_name": rendered_name.canonical,
                                   "address": rendered_place.canonical,
                                   "order_id": "A-4471"},
                        judged_args=("recipient_name", "address"),
                        item_ids=("name0", "loc0")),),
        final=FinalAnswer(must_contain=(rendered_place.canonical,)
                          if index % 4 == 0 else (), must_not_contain=(), answer=""),
        links=tuple(links), annotators=0,
        note=f"имя «{name_shape}» и адрес «{shape}» в одной реплике — "
             f"обычная форма заказа")


def _scenario_phone(case_id: str, register: str, context: str, index: int,
                    stream: random.Random) -> CaseSpec:
    """A phone, and in the speech register it is a run of numeral words.

    Measured on v2's corpus: 133 phones dictated aloud, of which the engine found
    ZERO. libphonenumber waits for digits and there are none, so the type is
    invisible in the register where it is commonest.
    """
    digits = f"9{stream.randint(10, 99)}{stream.randint(1000000, 9999999)}"
    rendered = _render_phone(digits, register, stream)
    layout, layout_shape = _weighted(NAME_LAYOUTS, stream)   # type: ignore[misc]
    person, diminutive = _draw_person(
        stream, needs_patronymic="patronymic" in layout or "short" in layout)
    if "short" in layout and not person.short_patronymic:
        person = stream.choice(tuple(p for p in MALE if p.short_patronymic))
    prefix, rendered_name, name_shape = _name_message(
        person, layout, layout_shape, register, stream, diminutive)
    negative = _negative_chunk(stream.choice(_negative_kinds(register, False)),
                               register, stream)
    cue = _around(stream.choice(PHONE_CUES), register, stream)
    name_seed = _seed(case_id, "name0", "NAME", rendered_name, "required", "pool",
                      "name")
    phone_seed = _seed(case_id, "phone0", "PHONE", rendered, "required", "template",
                       "phone")
    if register == "clean":
        pieces: tuple[object, ...] = (
            "Запишите", (rendered_name.surface, "name"), ", телефон",
            (rendered.surface, "phone"), *negative.pieces("neg"))
        terminator = "."
    else:
        pieces = (_opener(register, stream), prefix,
                  (rendered_name.surface, "name"), cue,
                  (rendered.surface, "phone"), *negative.pieces("neg"))
        terminator = ""
    draft = _draft(pieces, (("name", name_seed), ("phone", phone_seed)),
                   (("neg", negative),), None, terminator)
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=S_PHONE_PAIRS if register == "voice_raw"
                              else S_DICTATION,
                              selection="census", weight=1.0, licence="CC BY-NC 4.0"),
        cluster=f"phone:{rendered.canonical}",
        conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS["telecom"], drafts=(draft,),
        calls=(CallSpec(name="schedule_callback",
                        arguments={"name": rendered_name.canonical,
                                   "phone": rendered.canonical,
                                   "slot": "после обеда"},
                        judged_args=("name", "phone"),
                        item_ids=("name0", "phone0")),),
        final=FinalAnswer((), (), ""), links=(), annotators=0,
        note="телефон рядом с именем; в voice_raw он идёт пробегом числительных "
             "и ни одна контрольная сумма его не видит")


# The rare types, and every one of them gets BOTH forms. A dictated identifier
# is found by nothing today, and a corpus that only ever writes them in digits
# cannot say so.
RARE_TYPES: tuple[str, ...] = ("SNILS", "INN", "CARD", "PASSPORT", "PLATE",
                               "DOB", "EMAIL")


def _rare_value(kind: str, person: Person, register: str,
                stream: random.Random) -> tuple[Rendered, str, str, str]:
    """(rendered, domain key, tool name, tool parameter)."""
    if kind == "SNILS":
        return (_render_snils(_snils(stream), register), "bank", "verify_identity",
                "snils")
    if kind == "INN":
        return (_render_inn(_inn12(stream), register), "tax", "register_taxpayer",
                "inn")
    if kind == "CARD":
        return (_render_card(_card(stream), register), "bank", "save_card",
                "card_number")
    if kind == "PASSPORT":
        series, number = _passport(stream)
        return (_render_passport(series, number, register), "bank",
                "verify_identity", "passport")
    if kind == "PLATE":
        return (_render_plate(_plate(stream), register), "autoservice",
                "register_vehicle", "plate")
    if kind == "DOB":
        return (_render_dob(stream.randint(1, 28), stream.randint(1, 12),
                            stream.randint(1945, 2006), register), "clinic",
                "book_visit", "birth_date")
    if kind == "EMAIL":
        local = _translit(person.surname[0]) + str(stream.randint(1, 99))
        domain = stream.choice(_EMAIL_DOMAINS)
        spoken_local = (person.surname[0] if stream.randrange(100) < 65
                        else " ".join(_SPOKEN_LATIN[letter] for letter
                                      in _translit(person.surname[0])[:5]))
        return (_render_email(local, domain, spoken_local, register), "telecom",
                "update_contact", "email")
    raise InvalidCase(f"unknown rare type {kind!r}")


def _scenario_rare_named(case_id: str, register: str, context: str, index: int,
                         kind: str, stream: random.Random) -> CaseSpec:
    """A rare identifier inside a MINED wrapper, with the person who owns it.

    The value is template — neither speech corpus carries these types in usable
    quantity, and inventing that they do would be worse than saying so. The
    sentence around it is a real dictation shape, because a type measured in a
    register it never appears in is not measured.
    """
    layout, layout_shape = _weighted(NAME_LAYOUTS, stream)   # type: ignore[misc]
    person, diminutive = _draw_person(
        stream, needs_patronymic="patronymic" in layout or "short" in layout)
    if "short" in layout and not person.short_patronymic:
        person = stream.choice(tuple(p for p in MALE if p.short_patronymic))
    rendered, domain_key, tool_name, param = _rare_value(kind, person, register,
                                                         stream)
    prefix, rendered_name, name_shape = _name_message(
        person, layout, layout_shape, register, stream, diminutive)
    name_param = {"verify_identity": "full_name", "register_taxpayer": "full_name",
                  "save_card": "holder_name", "register_vehicle": "owner_name",
                  "book_visit": "patient_name", "update_contact": "name"}[tool_name]
    negative = _negative_chunk(stream.choice(_negative_kinds(register, False)),
                               register, stream)
    dictation = _around(stream.choice(("записывай", "пишите", "записываю",
                                       "диктую")), register, stream)
    if register == "clean":
        pieces: tuple[object, ...] = (
            "Клиент", (rendered_name.surface, "name"), ",",
            (rendered.surface, "value"), *negative.pieces("neg"))
        terminator = "."
    else:
        pieces = (_opener(register, stream), prefix,
                  (rendered_name.surface, "name"), dictation,
                  (rendered.surface, "value"), *negative.pieces("neg"))
        terminator = ""
    name_seed = _seed(case_id, "name0", "NAME", rendered_name, "required", "pool",
                      name_param)
    value_seed = _seed(case_id, "id0", kind, rendered, "required", "template", param)
    draft = _draft(pieces, (("name", name_seed), ("value", value_seed)),
                   (("neg", negative),), None, terminator)
    arguments = {name_param: rendered_name.canonical, param: rendered.canonical}
    if tool_name == "verify_identity":
        arguments["case_id"] = "OB-8812"
    if tool_name == "register_vehicle":
        arguments["slot"] = "завтра утром"
    if tool_name == "register_taxpayer":
        arguments["region"] = "18"
    forbidden = (rendered.canonical,) if kind in ("PASSPORT", "SNILS", "CARD") else ()
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=S_PHONE_RUN if register == "voice_raw"
                              else S_DICTATION,
                              selection="census", weight=1.0,
                              licence="CC BY-NC 4.0"),
        cluster=f"{kind.lower()}:{rendered.canonical}",
        conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS[domain_key], drafts=(draft,),
        calls=(CallSpec(name=tool_name, arguments=arguments,
                        judged_args=(name_param, param),
                        item_ids=("name0", "id0")),),
        final=FinalAnswer(must_contain=(), must_not_contain=forbidden, answer=""),
        links=(), annotators=0,
        note=f"{kind} шаблонным значением внутри добытой формы диктовки; "
             f"в voice_raw он произнесён словами и цифр не несёт")


def _scenario_rare_form(case_id: str, register: str, context: str, index: int,
                        kind: str, stream: random.Random) -> CaseSpec:
    """A document number in a written channel, and NO name anywhere.

    `template` is permitted only where mining cannot reach, and the schema
    refuses one carrying NAME or LOC — those two the corpora do hold, and a
    template there would be laziness rather than necessity. So this case has no
    person in it at all: a form, a chat with support, a line from an application.
    """
    person = stream.choice(MALE + FEMALE)
    rendered, domain_key, tool_name, param = _rare_value(kind, person, register,
                                                         stream)
    negative = _negative_chunk(stream.choice(_negative_kinds(register, False)),
                               register, stream)
    label = {"SNILS": "снилс", "INN": "инн", "CARD": "карта", "PASSPORT": "паспорт",
             "PLATE": "госномер", "DOB": "дата рождения", "EMAIL": "почта"}[kind]
    if register == "clean":
        pieces: tuple[object, ...] = (
            label.capitalize(), (rendered.surface, "value"),
            *negative.pieces("neg"))
        terminator = "."
    else:
        pieces = (label, (rendered.surface, "value"), *negative.pieces("neg"))
        terminator = ""
    seed = _seed(case_id, "id0", kind, rendered, "required", "template", param)
    draft = _draft(pieces, (("value", seed),), (("neg", negative),), None, terminator)
    arguments = {param: rendered.canonical}
    if tool_name == "verify_identity":
        arguments["case_id"] = "OB-8812"
    if tool_name == "register_vehicle":
        arguments["slot"] = "завтра утром"
    if tool_name == "register_taxpayer":
        arguments["region"] = "18"
    if tool_name == "book_visit":
        arguments["room"] = "3 кабинет"
    if tool_name == "update_contact":
        arguments["ticket"] = "T-1190"
    forbidden = (rendered.canonical,) if kind in ("PASSPORT", "SNILS", "CARD") else ()
    return CaseSpec(
        case_id=case_id, register=register, context=context,
        provenance=Provenance(kind="template", corpus="authored", key="", shape="",
                              selection="authored", weight=1.0, licence="authored"),
        cluster=f"form:{kind.lower()}:{rendered.canonical}",
        conversation_id=_conversation_id(case_id, index),
        domain=DOMAINS[domain_key], drafts=(draft,),
        calls=(CallSpec(name=tool_name, arguments=arguments, judged_args=(param,),
                        item_ids=("id0",)),),
        final=FinalAnswer(must_contain=(), must_not_contain=forbidden, answer=""),
        links=(), annotators=0,
        note=f"{kind} в письменном канале, без имени: шаблон разрешён только там, "
             f"куда мининг не достаёт")


# --- the plan -------------------------------------------------------------
#
# Written out rather than sampled, and the totals are asserted at import. A
# balanced sampler re-draws violently — measured on v1, growing the corpus 10%
# and re-running one kept 3 of 10 nano cases — so the composition is data a
# reader can check against the corpus plan in `docs/tz-agentpii3.md` §6.
#
# The register mix is the measured one, not a taste: `voice_raw` is the BASE
# register of this product at 55%, and `clean` is one case in twenty-five
# because zero of 53 324 real utterances look like it.

PLAN: tuple[tuple[str, str, str, int], ...] = (
    ("verbatim_addr", "voice_raw", "short", 34),
    ("verbatim_addr", "voice_raw", "long", 20),
    ("verbatim_addr", "voice_raw", "deep", 10),
    ("verbatim_street", "voice_raw", "short", 6),

    ("addr_dispatch", "voice_raw", "solo", 20),
    ("addr_dispatch", "voice_raw", "short", 10),
    ("addr_dispatch", "voice_raw", "long", 8),
    ("addr_dispatch", "voice_raw", "deep", 7),
    ("addr_dispatch", "voice_itn", "solo", 8),
    ("addr_dispatch", "voice_itn", "short", 4),
    ("addr_dispatch", "voice_itn", "long", 3),
    ("addr_dispatch", "chat", "solo", 5),
    ("addr_dispatch", "chat", "short", 3),
    ("addr_dispatch", "chat", "long", 2),
    ("addr_dispatch", "sloppy", "solo", 2),
    ("addr_dispatch", "sloppy", "short", 2),
    ("addr_dispatch", "clean", "short", 1),

    ("addr_calls", "voice_raw", "solo", 14),
    ("addr_calls", "voice_raw", "short", 8),
    ("addr_calls", "voice_raw", "long", 7),
    ("addr_calls", "voice_raw", "deep", 5),
    ("addr_calls", "voice_itn", "solo", 3),
    ("addr_calls", "voice_itn", "short", 2),
    ("addr_calls", "voice_itn", "long", 1),
    ("addr_calls", "voice_itn", "deep", 2),
    ("addr_calls", "chat", "solo", 4),
    ("addr_calls", "chat", "short", 2),
    ("addr_calls", "chat", "long", 2),
    ("addr_calls", "sloppy", "solo", 2),
    ("addr_calls", "sloppy", "long", 1),
    ("addr_calls", "clean", "solo", 1),

    ("name_only", "voice_raw", "solo", 21),
    ("name_only", "voice_raw", "short", 14),
    ("name_only", "voice_raw", "long", 12),
    ("name_only", "voice_raw", "deep", 7),
    ("name_only", "voice_itn", "solo", 5),
    ("name_only", "voice_itn", "short", 3),
    ("name_only", "voice_itn", "long", 2),
    ("name_only", "chat", "solo", 9),
    ("name_only", "chat", "short", 6),
    ("name_only", "chat", "long", 4),
    ("name_only", "chat", "deep", 3),
    ("name_only", "sloppy", "solo", 4),
    ("name_only", "sloppy", "short", 3),
    ("name_only", "sloppy", "long", 1),
    ("name_only", "clean", "solo", 2),
    ("name_only", "clean", "short", 2),
    ("name_only", "clean", "long", 1),

    ("name_addr", "voice_raw", "solo", 7),
    ("name_addr", "voice_raw", "short", 5),
    ("name_addr", "voice_raw", "long", 4),
    ("name_addr", "voice_raw", "deep", 4),
    ("name_addr", "voice_itn", "solo", 4),
    ("name_addr", "voice_itn", "short", 3),
    ("name_addr", "voice_itn", "long", 3),
    ("name_addr", "chat", "solo", 4),
    ("name_addr", "chat", "short", 4),
    ("name_addr", "chat", "deep", 4),
    ("name_addr", "sloppy", "solo", 3),
    ("name_addr", "sloppy", "short", 2),
    ("name_addr", "clean", "short", 2),
    ("name_addr", "clean", "long", 1),

    ("phone", "voice_raw", "solo", 7),
    ("phone", "voice_raw", "short", 4),
    ("phone", "voice_raw", "long", 4),
    ("phone", "voice_raw", "deep", 3),
    ("phone", "voice_itn", "solo", 6),
    ("phone", "voice_itn", "short", 4),
    ("phone", "voice_itn", "long", 2),
    ("phone", "chat", "solo", 5),
    ("phone", "chat", "short", 3),
    ("phone", "chat", "long", 2),
    ("phone", "sloppy", "solo", 2),
    ("phone", "sloppy", "short", 1),
    ("phone", "clean", "solo", 1),
    ("phone", "clean", "short", 1),

    ("rare_named", "voice_raw", "solo", 4),
    ("rare_named", "voice_raw", "short", 3),
    ("rare_named", "voice_itn", "solo", 4),
    ("rare_named", "voice_itn", "short", 3),
    ("rare_named", "voice_itn", "long", 1),
    ("rare_named", "chat", "solo", 6),
    ("rare_named", "chat", "short", 4),
    ("rare_named", "chat", "long", 2),
    ("rare_named", "sloppy", "solo", 2),
    ("rare_named", "sloppy", "short", 1),
    ("rare_named", "clean", "solo", 1),
    ("rare_named", "clean", "short", 1),

    ("rare_form", "voice_itn", "solo", 3),
    ("rare_form", "voice_itn", "short", 2),
    ("rare_form", "chat", "solo", 8),
    ("rare_form", "chat", "short", 4),
    ("rare_form", "chat", "long", 2),
    ("rare_form", "sloppy", "solo", 2),
    ("rare_form", "sloppy", "short", 1),
    ("rare_form", "clean", "solo", 2),
    ("rare_form", "clean", "short", 1),
)

PLAN_TOTAL: int = sum(row[3] for row in PLAN)


def _apportion(weights: dict[str, int], total: int) -> dict[str, int]:
    """Largest remainder. The shares land exactly and nothing is lost to rounding."""
    mass = sum(weights.values())
    exact = {name: weight * total / mass for name, weight in weights.items()}
    sizes = {name: int(value) for name, value in exact.items()}
    order = sorted(exact, key=lambda name: (-(exact[name] - int(exact[name])), name))
    position = 0
    while sum(sizes.values()) < total:
        sizes[order[position % len(order)]] += 1
        position += 1
    return sizes


def _scaled_plan(count: int) -> tuple[tuple[str, str, str, int], ...]:
    """The plan at another size, with the composition preserved.

    Apportioned by REGISTER first, then by context inside each register, then
    across the scenarios inside each cell. A flat largest-remainder over the 103
    rows with a floor of one per row would make the floor itself the composition
    — at 120 that put `clean` at 11% against the 3.8% it promises — and a
    measurement whose register mix quietly changes with its size is v2's failure
    in another costume.

    The canonical size is PLAN_TOTAL. A different one is a different measurement
    and the ids move, which is why `Ladder` pins the corpus digest rather than
    this family's word for it.
    """
    if count == PLAN_TOTAL:
        return PLAN
    if count > PLAN_TOTAL:
        raise InvalidCase(
            f"this family is written for {PLAN_TOTAL} cases and was asked for "
            f"{count}; growing it means adding shapes, not repeating draws")
    registers: dict[str, int] = {}
    for row in PLAN:
        registers[row[1]] = registers.get(row[1], 0) + row[3]
    if count < len(registers) * len(CONTEXT_NAMES):
        raise InvalidCase(
            f"{count} cases cannot cross five registers with four context rungs; "
            f"a cell that vanishes silently un-closes a tier")
    per_register = _apportion(registers, count)

    sizes: dict[tuple[str, str, str], int] = {}
    for register, register_total in per_register.items():
        contexts: dict[str, int] = {}
        for row in PLAN:
            if row[1] == register:
                contexts[row[2]] = contexts.get(row[2], 0) + row[3]
        for context, context_total in _apportion(contexts, register_total).items():
            scenarios = {row[0]: row[3] for row in PLAN
                         if row[1] == register and row[2] == context}
            for scenario, size in _apportion(scenarios, context_total).items():
                sizes[(scenario, register, context)] = size
    scaled = tuple((row[0], row[1], row[2], sizes[(row[0], row[1], row[2])])
                   for row in PLAN)
    for axis in (1, 2):
        planned = _axis_shares(PLAN, axis)
        actual = _axis_shares(scaled, axis)
        for name, share in planned.items():
            if abs(actual.get(name, 0.0) - share) > 0.02:
                raise InvalidCase(
                    f"at {count} cases the composition this family promises "
                    f"cannot hold: {name} would be {actual.get(name, 0.0):.1%} "
                    f"against {share:.1%}. Ask for {PLAN_TOTAL}, or change the "
                    f"plan deliberately")
    return tuple(row for row in scaled if row[3])


def _axis_shares(rows: tuple[tuple[str, str, str, int], ...],
                 axis: int) -> dict[str, float]:
    total = sum(row[3] for row in rows)
    counts: dict[str, float] = {}
    for row in rows:
        counts[row[axis]] = counts.get(row[axis], 0.0) + row[3]
    return {name: value / total for name, value in counts.items()}


CONTEXT_NAMES: tuple[str, ...] = ("solo", "short", "long", "deep")


def _verbatim_order() -> tuple[tuple[str, str, tuple[tuple[int, int], ...], str], ...]:
    """The unbiased layer first, so a shorter run still holds it.

    Thirteen of the 154 hand-labelled address replies come from the random
    250-of-4805 sample and the other 141 from the marker stratum. If a scaled
    run took a prefix of the marker layer alone, LOC would be a marker-only type
    and `validate_corpus` would refuse the corpus — correctly, because that set
    can only show what the detector already finds.
    """
    number = [row for row in VERBATIM_ADDRESSES if row[3] != "marker"]
    marker = [row for row in VERBATIM_ADDRESSES if row[3] == "marker"]
    return tuple(sorted(number, key=lambda row: row[0])
                 + sorted(marker, key=lambda row: row[0]))


def _rare_kind(register: str, used: dict[str, int],
               spoken: dict[str, int]) -> str:
    """Which rare type this slot carries.

    Two rules, and the second is the reason this family exists at all. The first
    keeps every type above MIN_TYPE_DENOMINATOR — a plain cycle would starve one,
    because an e-mail cannot appear in `voice_itn` (that register is defined by
    having no sentence punctuation and an address is a dot) and a fixed rotation
    loses a slot every time it lands there.

    The second: a `voice_raw` slot goes to whichever type has the FEWEST spoken
    instances so far, so every rare type gets at least one. A dictated
    identifier is found by nothing today — libphonenumber and every checksum
    wait for digits — and a corpus that gives five of the seven types a spoken
    form and forgets the other two cannot say so about those two.
    """
    allowed = tuple(kind for kind in RARE_TYPES
                    if not (kind == "EMAIL" and register == "voice_itn"))
    if register == "voice_raw":
        return min(allowed, key=lambda kind: (spoken.get(kind, 0),
                                              used.get(kind, 0),
                                              RARE_TYPES.index(kind)))
    return min(allowed, key=lambda kind: (used.get(kind, 0),
                                          RARE_TYPES.index(kind)))


def build(seed: int, count: int) -> list[Case]:
    """The family, deterministically.

    The stream is seeded from the module name as well as the run seed, so adding
    a shape here cannot redraw another family's cases: a shared generator makes
    every family's output depend on how many draws the ones before it happened to
    make, and the corpus stops being comparable to its own previous version for a
    reason that has nothing to do with the corpus.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError(
            f"build(seed, count) takes an integer seed, got {type(seed).__name__}; "
            f"the stream is random.Random(f'v3:{MODULE}:{{seed}}') and a "
            f"non-integer would make it depend on an object's id")
    stream = random.Random(f"v3:{MODULE}:{seed}")
    addresses = _verbatim_order()
    streets = tuple(sorted(VERBATIM_STREETS, key=lambda row: row[0]))
    negatives = tuple(sorted(VERBATIM_NEGATIVES, key=lambda row: row[0]))
    if not addresses or not streets or not negatives:
        raise InvalidCase("the hand annotation carries no usable rows; the "
                          "verbatim layer cannot be generated from anything else")

    cases: list[Case] = []
    address_cursor = 0
    street_cursor = 0
    negative_cursor = 0
    rare_used: dict[str, int] = {}
    rare_spoken: dict[str, int] = {}
    for scenario, register, context, size in _scaled_plan(count):
        for _ in range(size):
            index = len(cases)
            case_id = f"{MODULE}-{index + 1:04d}"
            if scenario == "verbatim_addr":
                spec = _scenario_verbatim(
                    case_id, register, context, index,
                    addresses[address_cursor % len(addresses)],
                    negatives[negative_cursor % len(negatives)], stream)
                address_cursor += 1
                negative_cursor += 1
            elif scenario == "verbatim_street":
                spec = _scenario_verbatim_street(
                    case_id, register, context, index,
                    streets[street_cursor % len(streets)],
                    negatives[negative_cursor % len(negatives)], stream)
                street_cursor += 1
                negative_cursor += 1
            elif scenario == "addr_dispatch":
                spec = _scenario_address(case_id, register, context, index,
                                         ADDRESS_SHAPES, stream)
            elif scenario == "addr_calls":
                spec = _scenario_address(case_id, register, context, index,
                                         CALL_ADDRESS_SHAPES, stream)
            elif scenario == "name_only":
                spec = _scenario_name(case_id, register, context, index, stream)
            elif scenario == "name_addr":
                spec = _scenario_name_address(case_id, register, context, index,
                                              stream)
            elif scenario == "phone":
                spec = _scenario_phone(case_id, register, context, index, stream)
            elif scenario == "rare_named":
                kind = _rare_kind(register, rare_used, rare_spoken)
                rare_used[kind] = rare_used.get(kind, 0) + 1
                if register == "voice_raw":
                    rare_spoken[kind] = rare_spoken.get(kind, 0) + 1
                spec = _scenario_rare_named(case_id, register, context, index,
                                            kind, stream)
            elif scenario == "rare_form":
                kind = _rare_kind(register, rare_used, rare_spoken)
                rare_used[kind] = rare_used.get(kind, 0) + 1
                if register == "voice_raw":
                    rare_spoken[kind] = rare_spoken.get(kind, 0) + 1
                spec = _scenario_rare_form(case_id, register, context, index,
                                           kind, stream)
            else:
                raise InvalidCase(f"unknown scenario {scenario!r}")
            case = _build_case(spec, stream)
            problems = validate(case)
            if problems:
                raise InvalidCase("\n".join(problems))
            cases.append(case)
    return cases


# --- self-check -----------------------------------------------------------
#
# There is no pytest in this repository: every eval is a script with a `main()`.
# This one prints the composition rather than asserting it silently, because the
# numbers a reader has to check against the corpus plan are the composition, and
# a green dot says nothing about whether 55% of the corpus is really speech.

def _breakdown(cases: list[Case], key: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        name = str(key(case))            # type: ignore[operator]
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda row: -row[1]))


def main() -> None:
    cases = build(20260830, PLAN_TOTAL)
    total = len(cases)
    print(f"AgentPII-RU v3 · семейство {FAMILY} · модуль {MODULE}.py")
    print(RUDEVICES_ATTRIBUTION + " — атрибуция едет с набором, а не только "
          "в документации: пользователь получает корпус, а не репозиторий")
    print(f"{total} случаев, все прошли schema.validate\n")

    print("РЕГИСТР            ", _breakdown(cases, lambda c: c.register))
    print("КОНТЕКСТ           ", _breakdown(cases, lambda c: c.context))
    print("ПРОИСХОЖДЕНИЕ      ", _breakdown(cases, lambda c: c.provenance.kind))
    print("СТРАТА ОТБОРА      ", _breakdown(cases, lambda c: c.provenance.selection))
    print("ИСТОЧНИК ФОРМЫ     ", _breakdown(cases, lambda c: c.provenance.corpus))

    speech = sum(1 for c in cases if c.register in SPEECH_REGISTERS) / total
    clean = sum(1 for c in cases if c.register == "clean") / total
    real = sum(1 for c in cases
               if c.provenance.kind in ("verbatim", "recombined")) / total
    print(f"\nречь {speech:.1%} (пол корпуса 50%) · литературный {clean:.1%} "
          f"(потолок 5%) · форма из речи {real:.1%} (пол 70%)")

    required: dict[str, int] = {}
    distinct: dict[str, set[str]] = {}
    optional = 0
    spoken = 0
    for case in cases:
        for item in case.pii:
            if item.duty != "required":
                optional += 1
                continue
            required[item.type] = required.get(item.type, 0) + 1
            distinct.setdefault(item.type, set()).add(item.canonical.casefold())
            if item.spoken:
                spoken += 1
    print("\nТИП        вхождений  различных значений")
    for kind in sorted(required, key=lambda k: -required[k]):
        print(f"  {kind:9s} {required[kind]:9d} {len(distinct[kind]):8d}")
    print(f"  optional  {optional:9d}")
    print(f"  из них произнесены словами (spoken): {spoken}")

    negatives: dict[str, int] = {}
    for case in cases:
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print("\nНЕГАТИВЫ           ", dict(sorted(negatives.items(),
                                               key=lambda row: -row[1])))
    print("БЕЗ НЕГАТИВОВ      ",
          sum(1 for c in cases if not c.negatives), "случаев")
    print("ТОЛЬКО НЕГАТИВНЫЕ  ",
          sum(1 for c in cases
              if not any(i.duty == "required" for i in c.pii)), "случаев")

    links: dict[str, int] = {}
    for case in cases:
        for link in case.links:
            links[link.kind] = links.get(link.kind, 0) + 1
    print("СВЯЗЫВАНИЕ         ", links)
    print("ЗОНЫ               ", _breakdown(
        cases, lambda c: ",".join(("detect",) + (("roundtrip",) if c.calls else ())
                                  + (("answer",) if (c.final.must_contain
                                                     or c.final.must_not_contain
                                                     or c.final.answer) else ()))))

    deep = [c for c in cases if c.context == "deep"]
    if deep:
        sizes = sorted(case_characters(c) for c in deep)
        print(f"\ndeep: {len(deep)} случаев, символов {sizes[0]}–{sizes[-1]}, "
              f"сообщений {min(len(c.messages) for c in deep)}–"
              f"{max(len(c.messages) for c in deep)}")

    # The engine derives a conversation identity from the first TWO messages when
    # the caller names none, and a system prompt is shared by every dialogue an
    # agent has. Two cases opening identically ARE one conversation as far as the
    # vault is concerned, and one customer's partial mention would then resolve
    # against another's — a corpus bug that reports as a gateway leak.
    seen: dict[str, str] = {}
    collisions = 0
    for case in cases:
        if case.conversation_id:
            continue
        opening = " ".join(m.content for m in case.messages[:2])
        if opening in seen:
            collisions += 1
            print(f"  СТОЛКНОВЕНИЕ: {case.id} открывается как {seen[opening]}")
        seen[opening] = case.id
    print(f"выводимых идентификаторов разговора: {len(seen)}, "
          f"столкновений: {collisions}")

    print("\nПРИМЕРЫ")
    samples = [cases[0], cases[64], cases[130], cases[210], cases[300],
               cases[380], cases[430], cases[-1]]
    for case in samples:
        carrier = case.pii[0].msg if case.pii else case.negatives[0].msg
        user = case.messages[carrier]
        print(f"  [{case.id}] {case.register}/{case.context}/"
              f"{case.provenance.kind}/{case.provenance.selection}")
        print(f"    {user.content[:110]}")
        for item in case.pii:
            print(f"      {item.type:8s} {item.value!r} -> {item.canonical!r}"
                  f"{' (spoken)' if item.spoken else ''}")
        for negative in case.negatives:
            print(f"      негатив  {negative.value!r} [{negative.family}]")
        for call in case.calls:
            print(f"      вызов    {call.name}{call.arguments}")


if __name__ == "__main__":
    main()
