"""Family `wordnum` — an address whose house number is a WORD.

THE DEFECT THIS FAMILY EXISTS FOR, measured on the live engine before a line of
it was written: «школьная пятьдесят девять» is handed to the model as
«Сортавала» — a bare settlement name, no house at all. Detection fires, the
round trip resolves, and the only place the loss is visible is the SHAPE of the
string the model was given: `place_shape` decides whether an address carries a
house by looking for `\\d`, and a spoken house number has no digit in it. The
second half of the same defect: in «химзаводская пять квартира пятнадцать» the
word taken for the street's generic type is «квартира».

WHY IT IS A FAMILY AND NOT A CORNER OF `transfer`. It breaks a DIFFERENT
mechanism from every other defect in this benchmark. Detection is right. The
vault is right. The substitution is what degrades, and recall cannot see that at
all — a family whose failures are invisible to the axis that dominates the
corpus has to be counted apart or its 170 cases are averaged into a thousand
that pass.

HOW IT BECOMES MEASURABLE ON AXIS 2 — the whole point of the family:

    THE TOOL TAKES `street` AND `house` AS SEPARATE PARAMETERS.

A model shown «Сортавала» cannot fill `house`, because it was never shown a
house. So a defect that lives in the shape of a fake becomes an argument that
is missing, wrong, or invented — an outcome the round trip can name. The tools
here also take `said_as`, the whole address exactly as the customer said it,
which is what a dispatch system stores beside its parsed fields anyway; that
parameter is what gives every case a `PiiItem.tool_param` and keeps
`classify_break` reachable.

Both hooks are populated on every call in this file, and that is deliberate
rather than thorough. `ExpectedCall.pii_items` names the whole value and is what
a per-item scorer walks; `judged_args` names the PARTS and is where this
family's defect actually shows. A scorer that walked only `pii_items` would see
`said_as` come back correct and report the case clean while `house` never
arrived — the tau2-bench shape the schema's `judged_axes` was written against, a
zone that exists with nothing in it. If only one of the two can be read, read
`judged_args`.

WHAT THE GROUND TRUTH DEMANDS, and it is the owner's sentence: THE SPAN WHOLE.
«школьная пятьдесят девять а первый подъезд» is ONE gold LOC item covering the
letter and the entrance, because an address found up to the letter is an address
half leaked, and `span_verdict` grades that `partial` only if the item claims
the whole of it. Splitting the address into a street item and a house item would
score a gateway that masked «школьная» and left «пятьдесят девять» in the clear
as fully covered on one item and missing on another, and the two numbers would
average into something that looks like a near miss.

WHAT IT DOES NOT DEMAND. The canonical form of an address is the string that was
said, unchanged. «школьная пятьдесят девять» does not have to come back as
«Школьная 59» — nobody sold a transcriber, `classify_break` already has the name
`renumbered` for a value that came back in digits, and demanding the repaired
form would score a product that does not exist. The one thing the corpus insists
on is that the number said as a word arrives as that word.

REGISTER, AND WHY `voice_itn` IS HERE AT ALL. In a pure `voice_raw` reply there
is not one digit anywhere, so «every number in this text is a word» is a free
signal a gateway could lean on without ever deciding anything about THIS number.
`voice_itn` takes the signal away: inverse text normalisation has converted the
numbers it was confident about — a cued order number, a time — and left the bare
cardinal standing after an unknown proper noun, which is exactly where an ITN
model has no evidence that the word is a quantity rather than part of the name.
So the reply carries digits AND the house is still a word, and the gateway has
to decide per number. Same reason `chat`, `sloppy` and `clean` each carry a few:
a house number in words is a register phenomenon, and if the engine only fails
on it when nothing else in the message is a digit, that is a different bug from
the one we measured.

`clean` is three cases out of 170 and it is not decoration: Russian legal and
dispatch paperwork spells numbers out on purpose («дом пятьдесят девять»), so
the literary register can carry this shape without being contrived, and if the
substitution fails there too then the defect is in the shape probe rather than in
the register.

EVERY CASE IS `recombined`. The schema permits `template` only where the speech
corpora cannot reach, and LOC is the type they hold best — 169 hand-labelled
address values. The forms come from `mined/dispatch_grammar.json` (value shapes
and reply shapes, from 650 hand-labelled SOVA RuDevices utterances) and
`mined/calls_grammar.json` (the call corpus's address shapes, mined over 12 950
OpenSTT replies); the values are drawn from pools built out of the vocabulary
those corpora actually use.

THE VERBATIM LAYER IS DELIBERATELY LEFT TO `direct`. There are 154 hand-labelled
address replies and `direct` already builds 64 cases on them. Building more here
would measure the same utterances a second time in a second family, and a repeat
is not an observation — the cluster machinery bounds that inside a family and
cannot see across families. What this module takes from the annotation is the
FILLER and the NEGATIVES: replies a human read and called «не адрес».

    SOVA Dataset / RuDevices, CC BY 4.0 — see `ATTRIBUTION`. The credit rides
    with the corpus and not only with this repository, for the same reason the
    ГАР attribution rides in the bundle: the reader receives the dataset, not the
    source tree. Not one character of OpenSTT is reproduced — CC BY-NC 4.0 is
    measurable and not shippable, so what comes from it is SHAPE and frequency.

WHAT THIS FAMILY REFUSES TO CLAIM. `FinalAnswer.must_not_contain` is empty in
every case here, and that is an argument rather than an omission: every value a
`wordnum` reply could carry is the customer's own address, so forbidding its
appearance would be a claim about how the model phrases a confirmation, not
about the gateway. The families that can state a forbidden disclosure honestly
are `result` and `crowd`, where the value belongs to somebody else. What this
family DOES put on the answer axis is `must_contain`: the confirmation has to
carry the customer's real address back, so a substitute presented to the
customer as their own address is `substitute_shown` — the outcome the owner
named, and the one a plausible fake address is never noticed as.

SEEDING. `build(seed, count)` takes an INT and makes `random.Random(f"v3:
wordnum:{seed}")`, so this family's draws do not move when another family adds a
scenario.
"""

import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii3.schema import (  # noqa: E402
    Case, ExpectedCall, FinalAnswer, InvalidCase, LinkExpectation, Message,
    Negative, PiiItem, Provenance, Source, ToolSchema, numeral_run,
    unsafe_filler, unsafe_person, validate,
)

FAMILY: str = "wordnum"

# The planned size. `build` scales every quota to whatever `count` it is given
# rather than hard-coding this number twice.
TARGET: int = 170

CACHE = Path.home() / ".cache" / "pseudex-bench"
SPEECH = CACHE / "speech_rudevices.jsonl"
LABELS = CACHE / "rudevices_addresses.json"
MINED = Path(__file__).resolve().parent.parent / "mined"

RUDEVICES_LICENCE: str = "CC BY 4.0"
ATTRIBUTION: str = (
    "Filler and negative utterances: SOVA Dataset / RuDevices "
    "(bond005/sova_rudevices), CC BY 4.0. Address FORMS: shape statistics mined "
    "from SOVA RuDevices (CC BY 4.0) and OpenSTT asr_calls_2_val (CC BY-NC 4.0); "
    "no OpenSTT text is reproduced."
)

# RuDevices' number layer is 250 utterances read out of the 4805 that no marker
# selects. Every share over it is nineteen times smaller than it looks unless
# `schema.weighted_rate` is given this number, and the layer it would otherwise
# be summed with — the marker census — is the layer we are good at.
NUMBER_SAMPLE_WEIGHT: float = 19.22


# --- the mined grammars ---------------------------------------------------
#
# A shape id is CHECKED against the files rather than trusted. A typo in a
# pattern string would leave `Provenance.shape` naming nothing, and «the form
# came from real speech» would be back to being an assertion nobody can verify —
# which is the state 1070 of v2's 1334 cases were in.

def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. The mined grammars are built by "
            f"bench/agentpii3/build_grammar.py; this family cannot invent the "
            f"shapes they carry.")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _known_shapes() -> frozenset[str]:
    """Every pattern string the two mined files publish."""
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
    return frozenset(names)


SHAPES = _known_shapes()


def _shape(pattern: str) -> str:
    if pattern not in SHAPES:
        raise InvalidCase(
            f"shape {pattern!r} is in neither mined grammar; a `recombined` case "
            f"whose shape names nothing is a template wearing a better label")
    return pattern


# Value shapes, by the name the dispatch file gives them. The counts beside them
# are what the hand annotation found, and they are why the quotas below are what
# they are: 53 of 169 address values are «<улица> <число> <порядковое> подъезд»
# and only 10 are «улица <улица> <число>».
S_NAKED = _shape("<улица> <число прописью>")
S_ENTRANCE = _shape("<улица> <число прописью> <порядковое> подъезд")
S_LETTER = _shape("<улица> <число прописью> <литера>")
S_LETTER_ENTRANCE = _shape("<улица> <число прописью> <литера> <порядковое> подъезд")
S_FLAT = _shape("<улица> <число прописью> квартира <число прописью>")
S_KORPUS = _shape("<улица> <число прописью> корпус <число прописью>")
S_STROENIE = _shape("<улица> <число прописью> строение <число прописью>")
S_KORPUS_ORD = _shape("<улица> <число прописью> <порядковое> корпус")
S_STREET_WORD = _shape("улица <улица> <число прописью>")
S_STREET_DOM = _shape("улица <улица> дом <число прописью>")
S_PEREULOK = _shape("переулок <улица> <число прописью>")
S_PEREULOK_DOM = _shape("переулок <улица> дом <число прописью>")
S_PROEZD = _shape("проезд <улица> <число прописью>")
S_PROSPEKT = _shape("проспект <улица> <число прописью>")
S_SHOSSE = _shape("<улица> шоссе <число прописью>")
S_SHOSSE_LETTER = _shape("<улица> шоссе <число прописью> <литера>")
S_NABEREZHNAYA = _shape("<улица> набережная <число прописью>")
S_BULVAR = _shape("<улица> бульвар <число прописью>")
S_DOM = _shape("<улица> дом <число прописью>")
S_PODYEZD_NOMER = _shape("<улица> <число прописью> подъезд номер <число прописью>")

# Reply shapes: how the utterance is built AROUND the value. 95 of 169 values
# open the reply with nothing in front of them, which is why `_opener` returns
# the empty string more often than anything else.
R_BARE = _shape("<АДРЕС>")
R_GREETING = _shape("<приветствие> <АДРЕС>")
R_TAIL = _shape("<АДРЕС> <хвост>")
R_FILLER = _shape("<филлер> <АДРЕС>")
R_INTENT = _shape("<намерение> <АДРЕС>")
R_ADDRESS_TO_ADDRESS = _shape("<АДРЕС> <намерение> <АДРЕС>")
R_INTENT_TAIL = _shape("<АДРЕС> <намерение> <хвост>")

# From the call corpus, where the same shapes were mined independently over
# 12 950 replies. Named separately because `Provenance.corpus` differs and a
# case built on a call-corpus shape must say CC BY-NC 4.0 even though not one
# character of that corpus is reproduced.
S_CALL_NAKED = _shape("<улица> <число прописью> — ни слова-типа улицы, ни слова «дом»")
S_CALL_TYPE_LAST = _shape("<улица> <тип улицы> <число прописью>")
S_CALL_TYPE_FIRST = _shape("<тип улицы> <улица> <число прописью>")
S_CALL_FRACTION = _shape("<улица> <число> дробь <число>")
# The two-number house — «карла маркса четыре семнадцать», «нижняя три
# четыре» — was mined in the call corpus under the loose shape and nowhere
# under a tighter one. Naming the tight shape it does not have would be the
# same lie as naming no shape at all, only harder to catch.
S_CALL_LOOSE = _shape(
    "<улица> ... <число> — без слова-типа улицы (маркер дома может быть)")
S_CALL_LETTER = _shape("<улица> <число прописью> <одна буква>")
S_CALL_DOM = _shape("<улица> дом <число> [корпус|строение|этаж <число>]")
S_CALL_ASR = _shape(
    "ошибка расшифровки ВНУТРИ значения: «лермонтова триц восемь», "
    "«лермонтого тридцать восемь»")


# --- the speech corpus ----------------------------------------------------

def _load_speech() -> dict[str, tuple[int, str]]:
    """key -> (1-based line, text). The key is blake2b-6, as the labels use.

    Duplicated utterances keep their FIRST line: a reader going to look at the
    source wants a line that holds the text, and the later copies do too.
    """
    if not SPEECH.exists():
        raise FileNotFoundError(
            f"{SPEECH} is missing. Fetch SOVA RuDevices into "
            f"~/.cache/pseudex-bench/ before building; the filler and the "
            f"negatives in this family are real speech and there is no "
            f"generated stand-in for them.")
    by_key: dict[str, tuple[int, str]] = {}
    with SPEECH.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            text = str(json.loads(line)["text"])
            key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
            if key not in by_key:
                by_key[key] = (index, text)
    return by_key


def _load_labels() -> tuple[dict[str, object], ...]:
    if not LABELS.exists():
        raise FileNotFoundError(
            f"{LABELS} is missing. The «не адрес» verdict on every filler line "
            f"in this family is a human's, and there is no mechanical stand-in "
            f"for it.")
    with LABELS.open(encoding="utf-8") as handle:
        return tuple(json.load(handle))


SPEECH_BY_KEY = _load_speech()
LABEL_ROWS = _load_labels()


def _source(key: str) -> Source:
    line, text = SPEECH_BY_KEY[key]
    return Source(corpus="speech_rudevices", key=key, line=line,
                  sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                  licence=RUDEVICES_LICENCE)


# --- what may stand as unlabelled filler ----------------------------------
#
# NOT a PII detector, and deliberately weaker than one. Its job is to keep a
# stray personal datum out of text that nothing claims, because an unclaimed
# name in filler scores as a false mask against a gateway that was right — the
# corpus's error printed as the product's. Over-rejecting costs nothing: the
# hand-labelled «не адрес» pool is 472 replies and this family needs a few
# hundred.

_OBSCENE = re.compile(
    r"(?:^|[^а-яё])"
    r"(?:по|за|на|до|от|при|раз|вы|пере|про|под|об|из|ни|не|у|с|о)?[ъь]?"
    r"(?:бля|пизд|ху[йяеёиюы]|[её]б|сук[аиуе]|говн|жоп|срат|дроч|мудак|пидор|"
    r"ссан|шлюх|проститут|наркот|кокаин|героин|изнасил|труп|убийств|педоф|"
    r"суицид|сис[ьк]|член|отсас|сосал|сос[её]т|трах|секс|эрот|минет|аналь|"
    r"оргазм|порн|голая|голый|голым|интим|презерв|задниц|писюн|письк|хер[аоуы]|"
    r"залуп)")

# A patronymic tail, a rank and a kinship word are the three things that stand
# in front of a name in this register — 75 «<должность> <фамилия>» against 20
# «меня зовут <имя>» in the call corpus — so a filler line carrying one is
# dropped whether or not the name after it is in any list.
_PATRONYMIC_ISH = re.compile(
    r"\w*(ович|евич|овна|евна|ична|иныч|аныч|алыч|ыч)\b|"
    r"\b(сторож|полковник|дежурн\w+|подполковник|майор|капитан|лейтенант|"
    r"генерал|дядя|тётя|тетя|фамили\w+|отчеств\w+)\b")

# Given names and diminutives that occur in ordinary RuDevices chatter. Authored
# and matched as whole tokens. The list cannot be complete — Russian has more
# hypocorisms than any list holds — and the residual is stated rather than
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
вика вике вику аня ане аню галя гале галю вова вове вову толя толе толю
славик рома ромы роме санёк санек тёма тема витёк витек ирочка ирочку гуля
максим максима максиму олег олега олегу иван ивана ивану пётр петр петра петру
""".split())
# Declined forms are generated rather than listed: a list with «димон» and
# without «димону» let the reply naming him into filler unclaimed. The junk this
# produces («оляу») matches nothing and costs nothing.
_FILLER_NAME_TOKENS = _FILLER_NAME_TOKENS | frozenset(
    name + ending for name in _FILLER_NAME_TOKENS
    for ending in ("а", "у", "е", "ы", "и", "ой", "ей", "ем", "ом", "ю"))

_WORD_TOKEN = re.compile(r"[а-яё]+")


def _looks_personal(text: str) -> bool:
    if _PATRONYMIC_ISH.search(text):
        return True
    return any(word in _FILLER_NAME_TOKENS for word in _WORD_TOKEN.findall(text))


def _usable_filler(text: str) -> bool:
    """A reply that may stand as filler nothing claims.

    THE SCREEN IS `schema.unsafe_filler`, called and not restated. Five families
    each kept a private copy of this idea with a private name list, so «оксана»
    was in one of them and in none of the others; one place is what makes a word
    added once protect all eleven.

    THE RESIDUAL, STATED RATHER THAN HIDDEN. Words like «дом», «этаж» and
    «микрорайон» stand in this corpus's ordinary chatter constantly, and only
    the five declared traps claim any of them. A reply saying «все я захотел дом
    мне нужен дом» is filler nothing claims: a gateway that masked «дом» there
    would be over-masking, and this family would not count it. So the false-mask
    number over `wordnum` is a LOWER BOUND on the over-masking rate, not an
    estimate of it — the family that estimates it is `negative`, which is a
    census of these replies rather than padding drawn from them. Filtering them
    out instead would be worse: «вот я ночевала в подъезде два дня» IS this
    register, and padding scrubbed of it would be a dialogue nobody had.
    """
    if len(text) < 24 or _OBSCENE.search(text) or _looks_personal(text):
        return False
    return not unsafe_filler(text)


# --- the negatives that ride in the filler --------------------------------
#
# THE TRAP VOCABULARY IS DECLARED HERE AND IS NOT TAKEN FROM OUR RECOGNIZERS.
# Its job is to point at the word inside a reply a human already judged «не
# адрес»; a probe built from the detector would only ever find what the detector
# finds, which is the mistake that made the first voice set report 100% where
# the truth was 38.6%.
#
# NARROWER than the trap set the other families use, and narrowed on purpose:
# these are the five that wear THIS family's shape — a place word with a number
# beside it, or an address tail with no address in front of it. A negative that
# is merely a false positive somewhere else belongs in the family that measures
# it, and counting the same utterance in two families is one observation printed
# twice.
_TRAPS: tuple[tuple[str, str, str], ...] = (
    # The bare «в подъезде» arm is not decoration: an address tail with no
    # address in front of it is this family's own shape with the value removed,
    # and the corpus is full of it — people live in подъезды and talk about
    # them. Without the arm those replies would sit in filler claimed by
    # nothing, and a gateway masking one would be neither penalised nor caught.
    ("entrance_no_street",
     r"\b(перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|последн|углов)\w*"
     r"\s+подъезд\w*\b|\bподъезд[еуы]?\b",
     "хвост адреса без адреса: порядковое с подъездом, или голый «подъезд» — "
     "ровно та форма, которой кончается каждое второе адресное значение этого "
     "корпуса, только без улицы перед ней"),
    ("room_number",
     r"\b(перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|одиннадцат)\w*"
     r"\s+(этаж\w*|кабинет\w*|отделени\w*)\b",
     "порядковое рядом с этажом, кабинетом или отделением: 528 таких реплик в "
     "корпусе звонков, крупнейший источник ложных срабатываний регистра"),
    # THE LOOKAHEAD IS LOAD-BEARING AND IT IS THE MINED REGEX, not a tightened
    # copy of it. Without it «улица кузнечная дом» matches, and that reply is a
    # street WITH a name — `optional` under 152-ФЗ ст. 3 п. 1, never a negative.
    # A wrongly declared negative is worse than a missing one: it fails a
    # gateway that was right, and the failure looks exactly like over-masking.
    ("street_no_name",
     r"\bна улиц[еу]\b|\bпо улиц[еа]м\b|\bулиц[аы]\b(?!\s+[а-яё]+\s)",
     "«улица» без имени — двор, погода, прогулка; слово-тип улицы есть, "
     "улицы нет"),
    ("flat_as_home", r"\bквартир[аыуе]\b|\bквартирой\b",
     "«квартира» без номера — покупка, аренда, уборка; тот же маркер, которым "
     "кончается «химзаводская пять квартира пятнадцать»"),
    ("fare", r"\bпроезд\b",
     "«проезд» как плата за поездку, а не как тип улицы — а «проезд чапаева "
     "семьдесят один» в этом же корпусе адрес"),
)


def _filler_rows() -> tuple[tuple[str, str], ...]:
    """(key, text) for every «не адрес» reply that may stand as UNCLAIMED filler.

    Disjoint from `NEGATIVE_ROWS` by construction, and that is the point rather
    than tidiness: a reply holding «на улицу» is a trap whether or not this case
    chose to declare it, and the same string appearing sometimes as a claimed
    negative and sometimes as silent padding would make the false-mask count
    depend on which slot the padding loop happened to put it in. Every trap in
    this family's text is claimed.
    """
    traps = tuple(re.compile(pattern) for _, pattern, _ in _TRAPS)
    rows: list[tuple[str, str]] = []
    for row in LABEL_ROWS:
        if row.get("label") != "не адрес":
            continue
        text = str(row["text"])
        if not _usable_filler(text):
            continue
        if any(trap.search(text) for trap in traps):
            continue
        rows.append((str(row["key"]), text))
    if len(rows) < 120:
        raise InvalidCase(
            f"only {len(rows)} usable filler replies survive the content "
            f"filters; a `deep` case needs about seventy of them and repeating "
            f"one dialogue's padding would make the rung a short case said "
            f"twice")
    return tuple(rows)


def _negative_rows() -> tuple[tuple[str, str, int, int, str, str], ...]:
    """(key, text, start, end, family, why) over replies a human called «не адрес».

    The offsets are found by matching the trap against the text, and that is
    allowed HERE and nowhere else in this file: the string is verbatim and no
    register transform will ever rewrite it, so the objection the schema raises
    against a searched offset — that it is derived from a string something else
    already rewrote — does not apply. Every one of them is checked against the
    text again by `schema.validate`.
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
                or unsafe_person(text) or numeral_run(text) >= 4
                or any(character.isdigit() for character in text)):
            continue
        for family, pattern, why in compiled:
            match = pattern.search(text)
            if match:
                rows.append((str(row["key"]), text, match.start(), match.end(),
                             family, why))
                break
    if len(rows) < 30:
        raise InvalidCase(
            f"only {len(rows)} verbatim negatives survive; the precision half "
            f"of this family would then rest on authored text alone")
    return _round_robin(rows)


def _round_robin(rows: list[tuple[str, str, int, int, str, str]]
                 ) -> tuple[tuple[str, str, int, int, str, str], ...]:
    """Interleave the negatives by family, one from each in turn.

    The natural counts are 58 / 36 / 7 / 7 / 2, and padding taken in file order
    would use «на улице погода хорошая» sixty times and «первый подъезд от
    школы» twice — measuring the commonest trap over and over and the two that
    wear THIS family's own shape almost never. The corpus's real frequency is
    not lost by doing this: it is carried by the `negative` family, which is a
    census of exactly these replies, and the per-family counts are printed by
    `main` either way.

    Deterministic: file order inside a family, family order by first appearance.
    A shuffle here would move every `deep` case's padding on a re-run for no
    reason anyone could name.
    """
    by_family: dict[str, list[tuple[str, str, int, int, str, str]]] = {}
    for row in rows:
        by_family.setdefault(row[4], []).append(row)
    interleaved: list[tuple[str, str, int, int, str, str]] = []
    index = 0
    while len(interleaved) < len(rows):
        for family in by_family:
            bucket = by_family[family]
            if index < len(bucket):
                interleaved.append(bucket[index])
        index += 1
    return tuple(interleaved)


FILLER_ROWS = _filler_rows()
NEGATIVE_ROWS = _negative_rows()


# --- numbers as words -----------------------------------------------------
#
# There is not one digit in either speech corpus: every number is a word. This
# is the shape no written corpus can produce — in text a digit is a digit — and
# it is why the defect this family exists for was invisible to every set we had.

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
# Masculine, which is what «подъезд» and «корпус» take. «первое подъезд» is not
# Russian, and a value nobody would say makes the round trip a test of this
# file's grammar rather than of the gateway.
_ORDINALS: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой", "седьмой",
    "восьмой", "девятый", "десятый")

# Measured on the call corpus: 22.9% of every «-десят» form arrives contracted.
# This is the norm of the register, not an adversarial perturbation, so it is
# applied by rate. Every target is in `schema.NUMERAL_WORDS`, so a contracted
# numeral stays visible to `numeral_run` and to the unlabelled-shape audit — a
# contraction that hid a numeral run would be a corpus that cannot audit itself.
_CONTRACTED: dict[str, tuple[str, ...]] = {
    "пятьдесят": ("песят", "пеесят", "пяесят", "пейсят"),
    "шестьдесят": ("шеесят", "шейсят", "шесят"),
    "восемьдесят": ("восемесят",),
}
# From the mined near-miss table: only forms a human transcriber actually wrote
# down. 9 of the 44 call-corpus addresses carry an error INSIDE the value, so a
# generator that keeps its values clean and dirties only the words around them
# is measuring the easy half of its own register.
_TRUNCATED: dict[str, tuple[str, ...]] = {
    "три": ("триц", "трис"),
    "тридцать": ("триц", "тридц"),
    "восемь": ("восем", "восемсь"),
    "девяносто": ("девяно", "девяеносто"),
    "триста": ("тристо", "трииста"),
    "четыре": ("четыыре",),
    "одиннадцать": ("одинадцать",),
    "четвёртый": ("четвёрьый",),
}


def _spell_cardinal(value: int) -> str:
    """0..999 in words, masculine nominative — what a house number is."""
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
    if not 1 <= value <= 10:
        raise ValueError(f"no spoken ordinal for {value} in this pool")
    return _ORDINALS[value]


def _asr_damage(text: str, rng: random.Random) -> str:
    """Contract or truncate ONE numeral word, at the measured rates.

    Applied to the value and not to the words around it, because that is where
    the corpus puts it: «лермонтова триц восемь», «карла маркса триста
    девяеносто семь», «майская восемь четвёрьый подъезд».
    """
    words = text.split()
    for index, word in enumerate(words):
        if word in _CONTRACTED and rng.random() < 0.229:
            words[index] = rng.choice(_CONTRACTED[word])
            return " ".join(words)
    if rng.random() < 0.12:
        for index, word in enumerate(words):
            if word in _TRUNCATED:
                words[index] = rng.choice(_TRUNCATED[word])
                return " ".join(words)
    return " ".join(words)


# A vowel or a consonant lost inside the STREET NAME, which is a different
# damage from a mangled numeral and breaks a different thing: «лермонтого» for
# «лермонтова» leaves the number intact and takes the name out of every street
# vocabulary. 14 replies in the call corpus carry it.
_STREET_SLIPS: dict[str, str] = {
    "лермонтова": "лермонтого",
    "барышникова": "барышникого",
    "базисная": "абазисная",
    "буммашевская": "бумашевская",
    "калашникова": "калашникого",
    "дзержинского": "держинского",
    "маяковского": "маяковкого",
    "тимирязева": "тимирязива",
}


# --- places ---------------------------------------------------------------
#
# Streets, the way the two corpora actually name them: an ADJECTIVE (вольная,
# кирочная, школьная, клубная) or a SURNAME IN THE GENITIVE (лермонтова,
# комиссарова, гагарина) — 14 against 28 in the call corpus, and nothing else.
#
# THE THIRTY STREETS THE VAULT MINTS AS SUBSTITUTES ARE EXCLUDED — the tree and
# nature adjectives, Берёзовой through Родниковой, and with them the two the
# real corpus happens to share with that pool («вишнёвая», «полевая»). A real
# value equal to a fake one makes `same_value` return True for a leak, and the
# corpus would report the worst outcome as the best.

_STREETS_ADJ: tuple[str, ...] = (
    "школьная", "клубная", "нижняя", "союзная", "вольная", "кирочная",
    "мончегорская", "зеленоградская", "подлесная", "базисная", "наличная",
    "депутатская", "химзаводская", "советская", "пушкинская", "загородная",
    "деревообделочная", "буммашевская", "заречная", "северная", "майская",
    "фруктовая", "выставочная", "восточная", "молодёжная", "армейская",
    "ракетная", "фронтовая", "удмуртская", "камская", "совхозная",
)
_STREETS_GEN: tuple[str, ...] = (
    "ленина", "гагарина", "кирова", "чапаева", "энгельса", "калашникова",
    "грибоедова", "шумайлова", "коммунаров", "машиностроителей", "дзержинского",
    "котовского", "халтурина", "маяковского", "ломоносова", "орджоникидзе",
    "тимирязева", "баранова", "гусева", "лермонтова", "комиссарова",
    "челюскинцев", "берша", "напойма", "тельмана", "чайковского",
    "барышникова", "барамзиной", "люхвинцева", "металлистов", "воровского",
    "красина", "петрова", "павлова", "репина", "сабурова", "телегина",
    "ухтомского", "циолковского", "некрасова", "бабушкина",
)
# Two-word street names, and they are not a curiosity: «карла маркса», «сорок
# лет победы», «десять лет октября», «восьмое марта», «пятьдесят лет влксм» are
# 9 of the 169 hand-labelled values. The last three open with a NUMERAL, so the
# street name itself is part of the numeral run — which is exactly the shape a
# scanner that stops at the first number gets wrong.
_STREETS_MULTI: tuple[str, ...] = (
    "карла маркса", "степана разина", "сорок лет победы", "десять лет октября",
    "восьмое марта", "пятьдесят лет влксм", "пятьдесят лет октября",
    "городок строителей", "новый арбат", "третья тверская",
)
# Type words, and the tail-position ones are separate because they stand AFTER
# the name: «воткинское шоссе», «русская набережная», «воронцовский бульвар».
_TYPES_LEADING: tuple[str, ...] = ("улица", "переулок", "проезд", "проспект")
_TYPES_TRAILING: tuple[str, ...] = ("шоссе", "набережная", "бульвар")
# Street names that only ever take a trailing type word. «воткинское» is not a
# street, «воткинское шоссе» is.
_STREETS_TRAILING: dict[str, tuple[str, ...]] = {
    "шоссе": ("воткинское", "заречное", "болшевское", "южное"),
    "набережная": ("русская", "северная"),
    "бульвар": ("воронцовский", "приморский"),
}
# Names that take a LEADING type word and read as nothing without it.
_STREETS_LEADING: dict[str, tuple[str, ...]] = {
    "переулок": ("смольный", "сосновый", "загородный", "северный",
                 "транспортный", "набережный"),
    "проезд": ("чапаева", "халтурина", "комсомольский", "некрасова",
               "бабушкина"),
    "проспект": ("калашникова", "строителей", "ленина"),
    "улица": ("вараксино", "деловая", "садовая", "телегина", "сабурова",
              "дербеневская", "железнодорожная", "центральная", "арбатская"),
}

_ENTRANCE_ORDINALS: tuple[int, ...] = (1, 1, 1, 1, 2, 2, 2, 3, 4, 5, 6, 7, 8)
_ENTRANCE_WORDS: tuple[str, ...] = ("последний", "угловой")
# «подъезд номер три» takes a CARDINAL and «третий подъезд» takes an ordinal.
# The two forms are the same fact in two grammars — 82 ordinal-first against 60
# marker-first across the whole corpus — and writing «подъезд номер третий»
# would put a string nobody says into the one span the case is about.
_ORDINAL_TO_CARDINAL: dict[str, str] = {
    "первый": "один", "второй": "два", "третий": "три", "четвёртый": "четыре",
    "пятый": "пять", "шестой": "шесть", "седьмой": "семь", "восьмой": "восемь",
    "девятый": "девять", "десятый": "десять",
}
_HOUSE_LETTERS: tuple[str, ...] = ("а", "а", "а", "б", "б", "в")

# House numbers, drawn from the numbers the hand annotation actually carries.
# The tail runs to 421, because «карла маркса четыреста двадцать один восьмой
# подъезд» is a real utterance and a four-word house number is where a scanner
# that assumes two words stops early.
_HOUSES: tuple[int, ...] = (
    1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 16, 17, 19, 20, 22, 23, 24, 26, 27,
    28, 29, 30, 31, 32, 33, 35, 36, 37, 39, 40, 41, 43, 45, 46, 47, 48, 50, 52,
    53, 55, 56, 57, 58, 59, 63, 66, 67, 71, 72, 73, 74, 75, 78, 81, 84, 85, 87,
    92, 95, 98, 99, 100, 103, 106, 108, 116, 120, 121, 125, 126, 128, 138, 145,
    146, 148, 155, 157, 166, 172, 173, 185, 186, 192, 226, 227, 232, 239, 253,
    265, 268, 284, 397, 421,
)
# Flats. The three-digit ones are the point of half the flat cases: «квартира
# двести двадцать девять» is four numeral words after a marker, and a span that
# stops at the marker leaves a number in the clear that identifies one door.
_FLATS: tuple[int, ...] = (2, 4, 9, 12, 15, 18, 27, 33, 46, 55, 66, 102, 148,
                           199, 229, 315)


@dataclass(frozen=True)
class _Place:
    """An address held as PARTS, never as a finished string.

    The ground truth is derived from what the generator BUILT. A register that
    rewrites the string after the offsets were computed is the defect that cost
    v1 162 of its 183 sloppy failures — twice, once on names and once on
    addresses.

    `house_second` is the second number of «карла маркса четыре семнадцать» and
    of «нижняя три четыре»: a house number that is two numbers, which nothing in
    a written corpus produces. `fraction` is «два дробь восемь». They are
    separate fields because they are said differently and a scanner that gets
    one right can still get the other wrong.
    """

    street: str
    type_word: str        # "" for two thirds of values, which is the measured share
    type_trailing: bool   # «воткинское шоссе», type AFTER the name
    marker: bool          # the word «дом» is spoken
    house: int
    house_second: int     # 0 = absent
    fraction: int         # 0 = absent
    letter: str           # "" | «а» | «б» | «в»
    building_kind: str    # "" | «корпус» | «строение»
    building: int
    building_ordinal: bool   # «первый корпус» rather than «корпус один»
    flat: int             # 0 = not said
    entrance: str         # "" | «первый» … | «последний» | «угловой»
    entrance_numbered: bool  # «подъезд номер три» rather than «третий подъезд»
    slipped: bool         # the street name itself carries an ASR slip


@dataclass(frozen=True)
class _Rendered:
    """A finished address and the parts it was built from.

    `parts` is what the expected tool call passes, and it is taken from HERE and
    never by cutting the finished string apart. That is the whole discipline: an
    argument recovered by searching the surface is an argument the register
    transform has already rewritten.
    """

    text: str
    parts: dict[str, str]
    shape: str
    selection: str
    weight: float
    corpus: str
    licence: str


def _spoken_number(value: int, register: str) -> str:
    """A number as this family says it, which is ALWAYS in words.

    That is the family's definition and it does not bend per register. In
    `voice_itn` inverse text normalisation has converted the numbers it had a
    cue for — an order number, a time — and left the bare cardinal standing
    after an unknown proper noun, which is where an ITN model has no evidence
    that the word is a quantity rather than part of the name. In `chat` the
    person is typing back what they were told. In `clean` a Russian document
    spells the number out by convention.
    """
    if register not in ("voice_raw", "voice_itn", "chat", "sloppy", "clean"):
        raise ValueError(f"unknown register {register!r}")
    return _spell_cardinal(value)


def _render_place(place: _Place, register: str, rng: random.Random) -> _Rendered:
    """Lay the address down, in order, and keep every part.

    ORDER IS MEASURED, not stylistic. The ordinal stands BEFORE the marker («первый
    подъезд») 82 times against 60 the other way; the house letter is a separate
    word after the number 18 times in 169; the type word is absent in 113 of 169.
    """
    words: list[str] = []
    parts: dict[str, str] = {}

    street = place.street
    # A slipped street name is what an ASR does to a word it half heard, so it
    # belongs to the registers an ASR produced. A typed register damages words
    # by the keyboard instead — `_compose` — and a document does not damage them
    # at all; giving all five the same noise would measure one register twice.
    if (place.slipped and street in _STREET_SLIPS
            and register in ("voice_raw", "voice_itn")):
        street = _STREET_SLIPS[street]

    if place.type_word and not place.type_trailing:
        words.append(place.type_word)
    words.append(street)
    if place.type_word and place.type_trailing:
        words.append(place.type_word)
    parts["street"] = (f"{place.type_word} {street}"
                       if place.type_word and not place.type_trailing
                       else f"{street} {place.type_word}"
                       if place.type_word else street)

    if place.marker:
        words.append("дом")
    house_words = [_spoken_number(place.house, register)]
    if place.fraction:
        house_words += ["дробь", _spoken_number(place.fraction, register)]
    elif place.house_second:
        house_words.append(_spoken_number(place.house_second, register))
    words += house_words
    parts["house"] = " ".join(house_words)

    if place.letter:
        words.append(place.letter)
        parts["letter"] = place.letter

    if place.building_kind:
        if place.building_ordinal:
            words += [_spell_ordinal(place.building), place.building_kind]
            parts["building"] = f"{_spell_ordinal(place.building)} {place.building_kind}"
        else:
            words += [place.building_kind, _spoken_number(place.building, register)]
            parts["building"] = f"{place.building_kind} {_spoken_number(place.building, register)}"

    if place.flat:
        words += ["квартира", _spoken_number(place.flat, register)]
        parts["flat"] = _spoken_number(place.flat, register)

    if place.entrance:
        # «последний» and «угловой» have no cardinal, so they keep the ordinal
        # form whatever the draw said: the numbered variant is a grammar, not a
        # decoration, and forcing it would produce «подъезд номер последний».
        cardinal = _ORDINAL_TO_CARDINAL.get(place.entrance, "")
        if place.entrance_numbered and cardinal:
            words += ["подъезд", "номер", cardinal]
            parts["entrance"] = cardinal
        else:
            words += [place.entrance, "подъезд"]
            parts["entrance"] = place.entrance

    text = " ".join(words)
    # ASR damage lands INSIDE the value and only in the register that produces
    # it phonetically. `sloppy` gets keyboard damage instead, and it lands on
    # the words around the value — see `_compose`.
    if register == "voice_raw":
        damaged = _asr_damage(text, rng)
        if damaged != text:
            # Re-cut the parts from the SAME construction rather than from the
            # damaged string: the damage may fall on the house or on the flat,
            # and a part recovered by slicing the surface would be the register
            # transform deciding the ground truth.
            parts = _reparts(parts, damaged, text.split())
            text = damaged
    if register == "clean":
        text, parts = _clean_form(place, street, register)

    shape, selection, weight, corpus, licence = _place_provenance(place)
    return _Rendered(text=text, parts=parts, shape=shape, selection=selection,
                     weight=weight, corpus=corpus, licence=licence)


def _reparts(parts: dict[str, str], damaged: str,
             original: list[str]) -> dict[str, str]:
    """Carry a one-word ASR substitution through into the parts.

    Exactly one word changed — `_asr_damage` returns after its first edit — so
    the mapping is positional and total. Done by index and never by string
    search: two occurrences of «три» in «нижняя три четыре» would otherwise both
    be rewritten by a `replace`, and the part would stop being what the message
    says.
    """
    changed = damaged.split()
    if len(changed) != len(original):
        raise InvalidCase(
            "ASR damage changed the word count of an address value; every part "
            "offset downstream would be wrong and the case would still score")
    swap = {index for index in range(len(changed))
            if changed[index] != original[index]}
    if not swap:
        return parts
    rebuilt: dict[str, str] = {}
    for name, value in parts.items():
        pieces = value.split()
        start = _sublist_index(original, pieces)
        if start < 0:
            rebuilt[name] = value
            continue
        rebuilt[name] = " ".join(changed[start:start + len(pieces)])
    return rebuilt


def _sublist_index(haystack: list[str], needle: list[str]) -> int:
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start:start + len(needle)] == needle:
            return start
    return -1


def _clean_form(place: _Place, street: str,
                register: str) -> tuple[str, dict[str, str]]:
    """The literary rendering: capitals, commas, full words.

    «улица Школьная, дом пятьдесят девять, первый подъезд». The number stays in
    words because that is the convention this register genuinely has — Russian
    contracts and acts spell it out — so the literary case tests the same defect
    rather than a different one, which is the only thing that makes it worth a
    slot out of the corpus's twenty.
    """
    pieces: list[str] = []
    parts: dict[str, str] = {}
    # ONLY THE FIRST WORD. «Сорок Лет Победы» is not how the name is written —
    # the official form capitalises «Победы» and nothing else — and a transcript
    # is lower case throughout, so which of the inner words is a proper noun is
    # not recoverable from it. A clerk typing a document from a phone call has
    # exactly this problem and solves it the same way; `str.title()` invents a
    # capitalisation the source never carried.
    name = street[:1].upper() + street[1:]
    if place.type_word and not place.type_trailing:
        pieces.append(f"{place.type_word} {name}")
        parts["street"] = f"{place.type_word} {name}"
    elif place.type_word:
        pieces.append(f"{name} {place.type_word}")
        parts["street"] = f"{name} {place.type_word}"
    else:
        pieces.append(name)
        parts["street"] = name

    house_words = [_spoken_number(place.house, register)]
    if place.fraction:
        house_words += ["дробь", _spoken_number(place.fraction, register)]
    elif place.house_second:
        house_words.append(_spoken_number(place.house_second, register))
    house = " ".join(house_words)
    parts["house"] = house
    # The literary register writes «дом» whether or not the speaker said it,
    # which is exactly what makes it literary: a form fills its own fields. The
    # spoken registers keep `place.marker` because there the word is either said
    # or it is not, and 12% of the corpus's values say it.
    pieces.append(f"дом {house}")

    if place.letter:
        pieces[-1] = pieces[-1] + f" {place.letter}"
        parts["letter"] = place.letter
    if place.building_kind:
        pieces.append(f"{place.building_kind} "
                      f"{_spoken_number(place.building, register)}")
        parts["building"] = (f"{place.building_kind} "
                             f"{_spoken_number(place.building, register)}")
    if place.flat:
        pieces.append(f"квартира {_spoken_number(place.flat, register)}")
        parts["flat"] = _spoken_number(place.flat, register)
    if place.entrance:
        # The literary register writes one form of each field and not the
        # variants speech has: «подъезд номер три» and «первый корпус» are
        # spoken word order, and a document that reproduced them would be a
        # transcript with commas in it.
        pieces.append(f"{place.entrance} подъезд")
        parts["entrance"] = place.entrance
    return ", ".join(pieces), parts


def _place_provenance(place: _Place) -> tuple[str, str, float, str, str]:
    """(shape, selection, weight, corpus, licence) — decided BY THE VALUE.

    A bare «<улица> <число>» is 66.9% of all address values and is attested in
    the RANDOM number-sample stratum, 250 utterances drawn from the 4805 that no
    marker selects, so it carries that stratum's inverse sampling fraction. A
    value carrying a street type word, a house marker, a letter, a flat or an
    entrance is attested only in the marker stratum, which is a census of
    exactly the utterances holding the cues the detector reads and is biased
    upward by construction. Summed without the weight, the marker layer gets
    nineteen times the mass it earned — and it is the layer we are good at.
    """
    if place.fraction or place.house_second:
        # The two-number house is a CALL-corpus shape: «улица дзержинского два
        # дробь восемь» and «карла маркса четыре семнадцать». Attested there,
        # named there, and the licence says so even though no text is taken.
        shape = S_CALL_FRACTION if place.fraction else S_CALL_LOOSE
        return (shape, "census", 1.0, "speech_calls", "CC BY-NC 4.0")
    if place.entrance and place.letter:
        return (S_LETTER_ENTRANCE, "marker", 1.0, "speech_rudevices",
                RUDEVICES_LICENCE)
    if place.entrance:
        shape = S_PODYEZD_NOMER if place.entrance_numbered else S_ENTRANCE
        return (shape, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    if place.flat:
        return (S_FLAT, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    if place.building_kind == "строение":
        return (S_STROENIE, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    if place.building_kind:
        shape = S_KORPUS_ORD if place.building_ordinal else S_KORPUS
        return (shape, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    if place.letter:
        shape = S_SHOSSE_LETTER if place.type_word == "шоссе" else S_LETTER
        return (shape, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    if place.type_word:
        shape = {
            "улица": S_STREET_DOM if place.marker else S_STREET_WORD,
            "переулок": S_PEREULOK_DOM if place.marker else S_PEREULOK,
            "проезд": S_PROEZD,
            "проспект": S_PROSPEKT,
            "шоссе": S_SHOSSE,
            "набережная": S_NABEREZHNAYA,
            "бульвар": S_BULVAR,
        }[place.type_word]
        return (shape, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    if place.marker:
        return (S_DOM, "marker", 1.0, "speech_rudevices", RUDEVICES_LICENCE)
    # The naked street. 66.9% of the corpus's address values and the only shape
    # attested in the unbiased stratum, which is why it carries the weight and
    # why it is the largest scenario below.
    return (S_NAKED, "random", NUMBER_SAMPLE_WEIGHT, "speech_rudevices",
            RUDEVICES_LICENCE)


def _draw_street(rng: random.Random) -> tuple[str, str, bool]:
    """(street, type_word, type_trailing).

    Two thirds of values carry NO type word — 113 of 169 in the dispatch corpus,
    26 of 44 in the calls corpus. A generator writing «улица Ленина дом 50»
    measures the easy half of its own register, and this family's whole subject
    is what happens when the generic word is missing and the number is a word.
    """
    draw = rng.random()
    if draw < 0.669:
        pool = (_STREETS_ADJ if rng.random() < 0.34
                else _STREETS_GEN if rng.random() < 0.85 else _STREETS_MULTI)
        return (rng.choice(pool), "", False)
    if draw < 0.80:
        kind = rng.choice(_TYPES_TRAILING)
        return (rng.choice(_STREETS_TRAILING[kind]), kind, True)
    kind = rng.choice(_TYPES_LEADING)
    return (rng.choice(_STREETS_LEADING[kind]), kind, False)


def _free_street(rng: random.Random) -> str:
    """A street name that stands on its own, with no type word to lean on.

    «смольный» is not a street and «приморский» is not a street — «переулок
    смольный» and «приморский бульвар» are. A scenario that forces the type word
    off therefore has to redraw the NAME as well; stripping the word off a bound
    name writes a value no Russian would say, and the round trip stops measuring
    the gateway and starts measuring this file's vocabulary.
    """
    draw = rng.random()
    if draw < 0.34:
        return rng.choice(_STREETS_ADJ)
    if draw < 0.90:
        return rng.choice(_STREETS_GEN)
    return rng.choice(_STREETS_MULTI)


def _blank_place(rng: random.Random) -> _Place:
    street, type_word, trailing = _draw_street(rng)
    return _Place(
        street=street, type_word=type_word, type_trailing=trailing,
        marker=rng.random() < 0.12, house=rng.choice(_HOUSES), house_second=0,
        fraction=0, letter="", building_kind="", building=0,
        building_ordinal=False, flat=0, entrance="", entrance_numbered=False,
        slipped=False)


def _with(place: _Place, **changes: object) -> _Place:
    return _Place(**{**vars(place), **changes})   # type: ignore[arg-type]


def _draw_entrance(rng: random.Random) -> str:
    if rng.random() < 0.08:
        return rng.choice(_ENTRANCE_WORDS)
    return _spell_ordinal(rng.choice(_ENTRANCE_ORDINALS))


# --- keyboard damage, which is a different thing from ASR damage ----------
#
# `sloppy` is chat plus KEYBOARD errors, and keeping it apart from `voice_raw`
# is the reason there are two noisy registers: an ASR mishears a numeral («триц
# восемь»), a thumb misses a key («оформте»). A generator giving both registers
# the same noise measures one register twice.

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


# --- the words around the value -------------------------------------------
#
# From `dispatch_grammar.json`. 95 of 169 values open the reply with nothing in
# front of them and 159 of 169 carry no preposition, so the commonest opener in
# this register is the empty string — which is precisely the case a marker-less
# street with no preposition and no capital has to survive.

_OPENERS: tuple[str, ...] = (
    "", "", "", "", "", "", "", "", "", "",
    "здравствуйте", "здравствуйте", "здравствуйте", "здравствуйте",
    "алло здравствуйте", "доброе утро", "а", "аа", "оо", "девушка",
    "девушка добрый вечер", "алло девушка здравствуйте", "так", "але а",
    "а вот а", "здравствуйте а", "а здравствуйте", "алло",
)
_PREPOSITIONS: tuple[str, ...] = ("", "", "", "", "", "", "", "", "", "",
                                  "на", "по")
_INTENTS: tuple[str, ...] = ("поедем", "поеду", "поедем на", "едем на",
                             "едим на", "поедем на")
# Verbatim tails from the annotation. PII-free by inspection: a shop, a gate, a
# clinic department, a district — a place reference identifies nobody, and
# masking one breaks the sentence the driver needs.
_TAILS: tuple[str, ...] = (
    "частный дом", "магазин магнит", "столовая", "приёмное отделение",
    "заправка башнефть", "западная проходная", "магазин продукты служебный вход",
    "центральный вход мвеу", "новостройка со стороны стройки",
    "красный дом", "в этот торговый центр куб", "ветлечебница на рентген",
    "ленинский район частный дом", "магазин пешеход", "к билайну во дворы",
)
_OPERATOR: tuple[str, ...] = (
    "слушаю", "да записываю", "хорошо записал", "минуту сейчас посмотрю",
    "принято", "уточните пожалуйста", "сейчас найду", "поняла записываю",
    "секунду", "машина будет", "да да записал", "хорошо",
)
# Typed padding for the registers a dispatch transcript cannot pad. Real speech
# dropped into a messenger would be the same register error this version exists
# to fix, so a typed case gets typed filler.
_CHAT_FILLER: tuple[str, ...] = (
    "подскажите пожалуйста сколько ждать машину обычно в это время",
    "а можно оплатить картой водителю или только наличными",
    "у меня коляска войдёт в багажник или нужен универсал",
    "если я задержусь на пару минут машина подождёт или уедет",
    "а детское кресло можно заказать отдельно к поездке",
    "скажите пожалуйста водитель позвонит когда подъедет или просто напишет",
    "мне надо будет заехать по дороге на пять минут это как считается",
    "а если я отменю сейчас с меня спишут что нибудь",
    "хорошо тогда я жду внизу и выйду когда позвонит",
    "ещё вопрос можно ли поменять адрес уже после оформления",
    "а животное перевозить можно кошка в переноске",
    "спасибо большое всё понятно буду ждать тогда",
    "подскажите а тариф фиксированный или по счётчику считается",
    "у нас домофон не работает так что позвоните на телефон пожалуйста",
    "а можно чтобы водитель не курил в салоне это важно",
    "и последнее сколько примерно по времени ехать в час пик",
)


# --- authored negatives, standing beside the address ----------------------
#
# A `solo` case has no filler to hang a negative on, and a case without one
# measures half of what it should: our own generated sets reported 100%
# precision while «Счёт 1234 от 15.05.2025» was being masked, because they held
# no ordinary business text. In THIS register the equivalent is a number beside
# «кабинет», «заказ» or «ноль ноль», and it occurs 528 times in the call corpus.
#
# Every one of them is a number said the same way the house number is said, so
# a gateway cannot separate them by shape — only by what stands next to them.

@dataclass(frozen=True)
class _NegativeChunk:
    cue: str
    value: str
    family: str
    why: str


def _order_negative(rng: random.Random, register: str) -> _NegativeChunk:
    """A dictated order number. The defect this guards against SHIPPED once.

    Every dictated order number was being masked, and no literary corpus could
    see it: in written text a digit is a digit and the numeral run never
    happens.
    """
    parts = tuple(rng.randrange(10, 99) for _ in range(3))
    if register in ("voice_raw", "chat", "clean"):
        value = " ".join(_spell_cardinal(part) for part in parts)
    elif register == "voice_itn":
        value = " ".join(str(part) for part in parts)
    else:
        value = "".join(str(part) for part in parts)
    return _NegativeChunk(
        cue="заказ номер", value=value, family="order_number",
        why="номер заказа диктуется тем же пробегом числительных, что и номер "
            "дома, и персональными данными не является")


def _room_negative(rng: random.Random, register: str) -> _NegativeChunk:
    """«приёмное отделение», «двенадцатый кабинет» — a place with a number.

    265 replies in the call corpus put an ordinal in front of «кабинет» or
    «отделение». It is the single largest false-positive source of this
    register, and it is the same shape as «первый подъезд».
    """
    room = rng.choice((3, 5, 8, 12, 14, 108, 214, 314))
    if register in ("voice_raw", "chat", "clean"):
        spoken = {3: "третий", 5: "пятый", 8: "восьмой", 12: "двенадцатый",
                  14: "четырнадцатый", 108: "сто восьмой",
                  214: "двести четырнадцатый", 314: "триста четырнадцатый"}[room]
        value = f"{spoken} кабинет"
    else:
        value = f"кабинет {room}"
    return _NegativeChunk(
        cue="нам в", value=value, family="room_number",
        why="порядковое перед «кабинет» — та же форма, что «первый подъезд», и "
            "никого не определяет")


def _time_negative(rng: random.Random, register: str) -> _NegativeChunk:
    """«к девяти ноль ноль» — 66 of these in the call corpus, and none is PII.

    The colon is a register decision and not a formatting one: ITN restores
    digits, not punctuation, so `voice_itn` says «к 9 00» and only a typed
    register writes «9:00».
    """
    hour = rng.choice((8, 9, 10, 11, 14, 17))
    if register in ("voice_raw", "chat", "clean"):
        spoken = {8: "восьми", 9: "девяти", 10: "десяти", 11: "одиннадцати",
                  14: "четырнадцати", 17: "семнадцати"}[hour]
        value = f"к {spoken} ноль ноль"
    elif register == "voice_itn":
        value = f"к {hour} 00"
    else:
        value = f"к {hour}:00"
    return _NegativeChunk(
        cue="подъезжайте", value=value, family="time_of_day",
        why="время: ноли проговариваются словом, и пробег числительных здесь "
            "такой же, как у номера дома")


def _quantity_negative(rng: random.Random, register: str) -> _NegativeChunk:
    """«у нас ребёнок шесть месяцев» — a verbatim dispatch tail.

    A count beside a noun, and nothing about anybody. The noun decides the
    numeral's gender, so «две сумки» and not «два сумки»: a negative that reads
    as broken Russian is a negative a reader stops trusting, and these are the
    half of the measurement nobody checks by eye otherwise.
    """
    choice = rng.randrange(4)
    if choice == 0:
        # 5 through 20 take «месяцев»; 2, 3 and 4 take «месяца», and a negative
        # that reads as broken Russian is a negative a reader stops trusting.
        # The counts are picked so one form covers them all rather than a rule
        # being written for a table with four entries.
        count = rng.choice((5, 6, 8, 10, 11))
        word = (_spell_cardinal(count)
                if register in ("voice_raw", "chat", "clean") else str(count))
        return _NegativeChunk(
            cue="у нас", value=f"ребёнок {word} месяцев", family="quantity",
            why="возраст ребёнка в месяцах — счёт, а не адрес; дословный хвост "
                "из разметки диспетчерской")
    if choice == 1:
        count = rng.choice((2, 3, 4))
        word = ("две" if count == 2 else _spell_cardinal(count)) \
            if register in ("voice_raw", "chat", "clean") else str(count)
        return _NegativeChunk(
            cue="с нами", value=f"{word} сумки", family="quantity",
            why="счёт предметов: «сумка» женского рода, поэтому «две», и это "
                "не номер дома")
    if choice == 2:
        count = rng.choice((40, 80, 120))
        word = (_spell_cardinal(count)
                if register in ("voice_raw", "chat", "clean") else str(count))
        return _NegativeChunk(
            cue="ехать примерно", value=f"{word} километров", family="measure",
            why="единица измерения после числа — то, чем номер дома отличается "
                "от количества")
    return _NegativeChunk(
        cue="", value=rng.choice(("поедем по городу", "до южной автостанции",
                                  "поеду на областную улицу")),
        family="city_reference",
        why="город или ориентир как место, а не как чей-то адрес")


def _fare_negative(rng: random.Random, register: str) -> _NegativeChunk:
    """«проезд» as the fare — and «проезд чапаева семьдесят один» is an address.

    One word, two readings, and both occur in this corpus. The value is the word
    alone because that is what a gateway would mask.
    """
    amount = rng.choice((150, 200, 250))
    word = (_spell_cardinal(amount)
            if register in ("voice_raw", "chat", "clean") else str(amount))
    return _NegativeChunk(
        cue="сколько будет", value="проезд", family="fare",
        why=f"«проезд» как плата (около {word} рублей), а не тип улицы")


def _street_word_negative(rng: random.Random, register: str) -> _NegativeChunk:
    """«на улице холодно» — the type word with no street behind it."""
    return _NegativeChunk(
        cue="", value=rng.choice(("на улице холодно", "на улице дождь",
                                  "на улице ветер")),
        family="street_no_name",
        why="слово-тип улицы без имени: двор, погода — маскировать нечего")


def _forbidden(*values: str) -> frozenset[str]:
    """Negative families this case's own value would make ambiguous.

    «сколько будет проезд» beside «проезд комсомольский двести тридцать два» is
    two readings of one word in one message, and a corpus that cannot say which
    span it means scores its own carelessness as the gateway's. The collision is
    worth testing and it belongs in the family whose cases are ABOUT it — here it
    is noise, because a false mask on either span would be indistinguishable from
    a correct one on the other.

    Derived from the finished value rather than declared per scenario: a
    scenario's own draw can put «квартира» or «проезд» into a value its author
    did not expect, and a declared list would then be silently wrong.
    """
    joined = " ".join(values).lower()
    forbid: set[str] = set()
    if "проезд" in joined:
        forbid.add("fare")
    if "улиц" in joined:
        forbid.add("street_no_name")
    if "квартир" in joined:
        forbid.add("flat_as_home")
    return frozenset(forbid)


_NEGATIVE_DRAWS: tuple[object, ...] = (
    _order_negative, _order_negative, _room_negative, _time_negative,
    _quantity_negative, _quantity_negative, _fare_negative,
    _street_word_negative,
)


def _draw_negative(rng: random.Random, register: str,
                   forbid: frozenset[str]) -> _NegativeChunk:
    """One negative that does not collide with the address beside it.

    `forbid` names the negative families this case's own value would make
    ambiguous: «сколько будет проезд» next to «проезд чапаева семьдесят один»
    is two readings of one word in one message, and a corpus that cannot say
    which span it means is a corpus scoring its own carelessness.

    IN `voice_itn` THE NEGATIVE IS WHERE THE DIGIT COMES FROM, and that is the
    register's definition rather than a trick to satisfy its gate. Inverse text
    normalisation converts the numbers it has a cue for — an order number, a
    time, a count — and leaves the bare cardinal standing after an unknown
    proper noun, which is where the model has no evidence that the word is a
    quantity rather than part of the name. So a digit-free negative would leave
    the reply with no digit anywhere, and the case would be a `voice_raw` case
    wearing another register's label.
    """
    for _ in range(24):
        chunk = _NEGATIVE_DRAWS[rng.randrange(len(_NEGATIVE_DRAWS))](
            rng, register)                          # type: ignore[operator]
        if chunk.family in forbid:
            continue
        if register == "voice_itn" and not any(ch.isdigit() for ch in chunk.value):
            continue
        return chunk
    raise InvalidCase("every negative family is forbidden for this case")


# --- tools ----------------------------------------------------------------
#
# THIS IS WHERE THE FAMILY STOPS BEING A NER CORPUS. A labelled span says «this
# is an address». `street` and `house` as separate parameters say «and the model
# has to be able to tell them apart in what you handed it» — which a substitute
# that dropped the house cannot support, however well it detokenises.
#
# `said_as` is not a convenience. It is what a dispatch system stores beside its
# parsed fields, it is the argument a `PiiItem` can legally claim (the schema
# demands the passed value be the item's own `value` or `canonical`), and it is
# what keeps `classify_break` — `renumbered`, `truncated`, `inflected` — reachable
# on every case in this file.

def _tool(name: str, description: str, params: tuple[tuple[str, str], ...],
          required: tuple[str, ...]) -> ToolSchema:
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
                "properties": {key: {"type": "string", "description": text}
                               for key, text in params},
                "required": list(required),
            },
        },
    }


_SAID_AS = ("said_as",
            "адрес целиком, дословно как его произнёс клиент, включая номер "
            "дома, литеру и подъезд")
_HOUSE = ("house",
          "номер дома так, как его назвал клиент: цифрой, если он сказал цифру, "
          "и словами, если он сказал словами")

_T_DISPATCH = _tool(
    "dispatch_car", "Подать машину по адресу клиента.",
    (("street", "название улицы вместе со словом-типом, если оно прозвучало"),
     _HOUSE,
     ("entrance", "номер подъезда, если он назван"),
     _SAID_AS,
     ("comment", "комментарий водителю, без персональных данных")),
    ("street", "house", "said_as"))
_T_COURIER = _tool(
    "send_courier", "Отправить курьера по адресу.",
    (("street", "название улицы вместе со словом-типом, если оно прозвучало"),
     _HOUSE,
     ("letter", "литера дома отдельной буквой, если она названа"),
     ("flat", "номер квартиры, если он назван"),
     _SAID_AS,
     ("order_id", "номер заказа, если он назван")),
    ("street", "house", "said_as"))
_T_BUILDING = _tool(
    "register_building", "Записать адрес объекта в карточку заявки.",
    (("street", "название улицы вместе со словом-типом, если оно прозвучало"),
     _HOUSE,
     ("building", "корпус или строение, если оно названо"),
     ("entrance", "номер подъезда, если он назван"),
     _SAID_AS),
    ("street", "house", "said_as"))
_T_ROUTE = _tool(
    "book_ride", "Заказать поездку: откуда забрать и куда везти.",
    (("pickup_street", "улица подачи"),
     ("pickup_house", "номер дома подачи так, как его назвал клиент"),
     ("pickup_said_as", "адрес подачи целиком, дословно"),
     ("dropoff_street", "улица назначения"),
     ("dropoff_house", "номер дома назначения так, как его назвал клиент"),
     ("dropoff_said_as", "адрес назначения целиком, дословно"),
     ("comment", "комментарий, без персональных данных")),
    ("pickup_street", "pickup_house", "pickup_said_as"))
_T_ADDRESS = _tool(
    "save_address", "Сохранить адрес клиента одной строкой, как он его назвал.",
    (("address", "адрес целиком, дословно как его произнёс клиент"),
     ("comment", "комментарий, без персональных данных")),
    ("address",))
_T_VISIT = _tool(
    "schedule_visit", "Записать выезд по адресу и подтвердить его клиенту.",
    (("address", "адрес целиком, дословно как его произнёс клиент"),
     ("when", "время, если оно названо")),
    ("address",))
# Offered beside the real tool so the model has a choice and the corpus is not
# a one-button test. Never expected: a call to it is the model's business.
_T_LOOKUP = _tool(
    "lookup_street", "Найти улицу в справочнике по названию.",
    (("query", "название улицы"),), ("query",))


# --- assembly -------------------------------------------------------------
#
# EVERY OFFSET IS COMPUTED DURING ASSEMBLY. Nothing here searches a finished
# string: a message naming two addresses — which this family does on purpose —
# would otherwise point both spans at the first one.

@dataclass(frozen=True)
class _Ctx:
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
    tail: str   # punctuation glued after the value, never inside its span


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


def _compose(ctx: _Ctx, slots: tuple[_Slot, ...]
             ) -> tuple[str, dict[str, tuple[int, int]]]:
    """Assemble one user line in this case's register.

    The keyboard typo lands on the words AROUND the value and it is applied
    BEFORE assembly, so every offset is computed from the string that ends up in
    the case and never repaired afterwards. A pass over a finished message would
    change its length and silently invalidate every span computed before it: the
    corpus keeps scoring, and scores wrongly. Damage INSIDE the value is the
    business of `_asr_damage`, which is phonetic and belongs to `voice_raw`.
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


def _sep(ctx: _Ctx) -> str:
    """The comma a typed register allows and a spoken one never carries."""
    return "," if ctx.register == "clean" else ""


def _stop(ctx: _Ctx) -> str:
    return "." if ctx.register == "clean" else ""


def _opener(ctx: _Ctx) -> str:
    if ctx.register in ("voice_raw", "voice_itn"):
        return ctx.rng.choice(_OPENERS)
    if ctx.register == "clean":
        return "Здравствуйте."
    return ctx.rng.choice(("", "", "привет", "здравствуйте"))


def _system_prompt(register: str) -> str:
    if register == "clean":
        return ("Ты оператор службы такси и доставки. Оформляй заявки вызовом "
                "инструментов; номер дома клиент может назвать словами — "
                "передавай его так, как он прозвучал, и не выдумывай данных, "
                "которых нет в диалоге.")
    return ("ты оператор службы такси и доставки оформляй заявки вызовом "
            "инструментов номер дома клиент может назвать словами передавай его "
            "так как он прозвучал и не выдумывай данных которых нет в диалоге")


def _msg(role: str, text: str) -> Message:
    return Message(role=role, content=text, source=None, name="")


def _filler_msg(key: str, text: str) -> Message:
    return Message(role="user", content=text, source=_source(key), name="")


def _typed_filler(register: str, text: str) -> str:
    """Filler in the register the case is written in.

    A `clean` case padded with lower-case chat would still pass the register
    gate — it only asks whether SOME user message carries a capital and SOME
    carries punctuation — and would still be a document with chat in the middle
    of it. Applied to authored filler only: verbatim filler carries a digest and
    rewriting it would make `hydrate` refuse the case it came from.
    """
    if register != "clean":
        return text
    return text[:1].upper() + text[1:] + "."


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


def _pad(messages: list[Message], negatives: list[Negative], ctx: _Ctx,
         want_messages: int, want_chars: int) -> None:
    """Grow the transcript with real, PII-free speech until the rung is met.

    Nine replies in ten in the live corpora carry no personal data at all — the
    measured floor is 0.939% for dispatch — so a `deep` case whose every line
    carries an address is not a long context, it is a short one repeated, and it
    inflates recall and precision at the same time.

    A third of the padding carries a DECLARED NEGATIVE, so the filler is the
    precision half of the measurement rather than dead weight: «первый подъезд
    от школы» and «на улице погода хорошая» are the two forms this family's own
    values wear, said by people who meant neither.
    """
    speech = ctx.register in ("voice_raw", "voice_itn")
    offset = ctx.rng.randrange(len(FILLER_ROWS))
    neg_offset = ctx.rng.randrange(len(NEGATIVE_ROWS))
    step = 0
    while (len(messages) < want_messages
           or sum(len(m.content) for m in messages) < want_chars):
        if len(messages) > 190:
            raise ValueError(f"{ctx.case_id}: filler cannot reach the rung")
        if speech and step % 3 == 2:
            key, text, start, end, family, why = NEGATIVE_ROWS[
                (neg_offset + step) % len(NEGATIVE_ROWS)]
            index = len(messages)
            messages.append(_filler_msg(key, text))
            negatives.append(Negative(value=text[start:end], start=start,
                                      end=end, msg=index, family=family,
                                      why=why))
        elif speech:
            key, text = FILLER_ROWS[(offset + step) % len(FILLER_ROWS)]
            messages.append(_filler_msg(key, text))
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


def _identity(ctx: _Ctx, who: str) -> str:
    # One identity is one substitute. Two route points are two identities even
    # though one customer said both, because they receive two substitutes and
    # the linking axis compares substitutes.
    return f"{ctx.case_id}/{who}/place"


def _case(ctx: _Ctx, messages: list[Message], tools: tuple[ToolSchema, ...],
          items: tuple[PiiItem, ...], negatives: tuple[Negative, ...],
          links: tuple[LinkExpectation, ...], calls: tuple[ExpectedCall, ...],
          final: FinalAnswer, rendered: _Rendered, note: str) -> Case:
    """Pack one case. Every field explicit — the schema has no defaults, so that
    «this case declares no negatives» and «the author forgot them» cannot be the
    same JSON."""
    return Case(
        id=ctx.case_id,
        family=FAMILY,
        register=ctx.register,
        context=ctx.context,
        provenance=Provenance(kind="recombined", corpus=rendered.corpus, key="",
                              shape=rendered.shape,
                              selection=rendered.selection,
                              weight=rendered.weight,
                              licence=rendered.licence),
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


def _place_item(item_id: str, ctx: _Ctx, rendered: _Rendered,
                span: tuple[int, int], msg: int, who: str, duty: str,
                tool_param: str) -> PiiItem:
    """The gold item: THE WHOLE ADDRESS, one span.

    `canonical` is the string that was said. Turning «школьная пятьдесят девять»
    into «Школьная 59» would demand a transcription nobody sold, and
    `classify_break` already names `renumbered` for a value that comes back in
    digits — an outcome to count, not a requirement to impose.
    """
    return PiiItem(
        id=item_id, type="LOC", value=rendered.text, canonical=rendered.text,
        start=span[0], end=span[1], msg=msg, identity=_identity(ctx, who),
        duty=duty, value_source="pool",
        spoken=not any(ch.isdigit() for ch in rendered.text),
        tool_param=tool_param)


def _judged(parts: dict[str, str], names: tuple[str, ...],
            prefix: str) -> tuple[dict[str, str], tuple[str, ...]]:
    """The arguments a correct agent passes, taken from what was BUILT.

    `names` is the parameter order the tool declares; a part the value does not
    carry is neither passed nor judged, because judging an argument the message
    never gave would score the gateway on information the conversation did not
    have — the ground-truth bug that cost 162 of v1's 183 sloppy failures.
    """
    arguments: dict[str, str] = {}
    judged: list[str] = []
    for name in names:
        if name not in parts:
            continue
        arguments[f"{prefix}{name}"] = parts[name]
        judged.append(f"{prefix}{name}")
    return arguments, tuple(judged)


# --- the seven scenarios --------------------------------------------------
#
# Each asks a question the others cannot. They differ in WHICH part of the
# address the substitution has to preserve, and in whether the tool can see that
# part at all.

def _scenario_naked(ctx: _Ctx, place: _Place) -> Case:
    """«барышникова шестьдесят три первый подъезд» — no type word, no digits.

    The core shape of the register and the exact string the measured defect was
    found on. 100 of the 156 marker-stratum address values name the street with
    a bare word, and 66.9% of all of them carry no street-type word at all: a
    generator writing «улица Ленина дом 50» measures the easy half.
    """
    rng = ctx.rng
    rendered = _render_place(place, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register, _forbidden(rendered.text))
    slots = (
        _plain(_opener(ctx)), _plain(rng.choice(_PREPOSITIONS)),
        _S(rendered.text, "place", _sep(ctx)),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    item = _place_item("place", ctx, rendered, spans["place"], 1, "customer",
                       "required", "said_as")
    arguments, judged = _judged(rendered.parts, ("street", "house", "entrance"), "")
    arguments["said_as"] = rendered.text
    return _case(
        ctx, messages, (_T_DISPATCH, _T_LOOKUP), (item,), tuple(negatives), (),
        (ExpectedCall(name="dispatch_car", arguments=arguments,
                      judged_args=judged + ("said_as",), pii_items=("place",),
                      after_msg=1),),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        rendered,
        "голая улица и номер дома прописью — форма, на которой замерена подмена "
        "без дома: модель, увидевшая голое название города, не может заполнить "
        "house, потому что дома ей не показали")


def _scenario_flat(ctx: _Ctx, place: _Place) -> Case:
    """«химзаводская пять квартира пятнадцать» — the second half of the defect.

    Here the word taken for the street's generic type is «квартира». The address
    carries no street-type word, so the only generic word in it is the flat
    marker, and a probe that reads the last marker it finds reads that one. The
    tool takes `flat` separately, so a substitute that folded the flat into the
    street has nowhere to put it.
    """
    rng = ctx.rng
    rendered = _render_place(place, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register, _forbidden(rendered.text))
    slots = (
        _plain(_opener(ctx)), _plain(rng.choice(("", "", "поедем", "поеду"))),
        _S(rendered.text, "place", _sep(ctx)),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    item = _place_item("place", ctx, rendered, spans["place"], 1, "customer",
                       "required", "said_as")
    arguments, judged = _judged(
        rendered.parts, ("street", "house", "letter", "flat"), "")
    arguments["said_as"] = rendered.text
    return _case(
        ctx, messages, (_T_COURIER, _T_LOOKUP), (item,), tuple(negatives), (),
        (ExpectedCall(name="send_courier", arguments=arguments,
                      judged_args=judged + ("said_as",), pii_items=("place",),
                      after_msg=1),),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        rendered,
        "квартира прописью после голой улицы: единственное родовое слово в "
        "значении — «квартира», и именно им подмена определяет тип улицы")


def _scenario_letter(ctx: _Ctx, place: _Place) -> Case:
    """«воткинское шоссе сто тридцать восемь а поедем по городу».

    The house letter is a separate word — 18 of 169 values — and «а» is also the
    commonest conjunction in the language. A span that stops at the number leaks
    the letter, which is the difference between two doors; a span that swallows
    the conjunction masks a word that is not personal data. Half of these are
    followed by an intent word starting with «поедем», so the two readings of
    «а» stand next to each other.
    """
    rng = ctx.rng
    rendered = _render_place(place, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register, _forbidden(rendered.text))
    tail = rng.choice(_TAILS)
    slots = (
        _plain(_opener(ctx)), _plain(rng.choice(_PREPOSITIONS)),
        _S(rendered.text, "place", _sep(ctx)), _plain(tail),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    item = _place_item("place", ctx, rendered, spans["place"], 1, "customer",
                       "required", "said_as")
    arguments, judged = _judged(rendered.parts, ("street", "house", "entrance"), "")
    arguments["said_as"] = rendered.text
    arguments["comment"] = tail
    return _case(
        ctx, messages, (_T_DISPATCH, _T_LOOKUP), (item,), tuple(negatives), (),
        (ExpectedCall(name="dispatch_car", arguments=arguments,
                      judged_args=judged + ("said_as",), pii_items=("place",),
                      after_msg=1),),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        rendered,
        "литера дома отдельным словом: найденный до буквы адрес — это утёкшая "
        "буква, а «а» здесь читается и как литера, и как союз")


def _scenario_two_points(ctx: _Ctx, place: _Place) -> Case:
    """«химзаводская пять квартира пятнадцать поедем гагарина пятьдесят».

    Every tenth reply carries two route points — 15 of 154 — and both are spoken
    addresses in one breath. Two places are two identities and must receive two
    substitutes: a gateway that links them (they are, after all, the same
    customer's) sends the car from a door to itself. A third of them name the
    second point WITHOUT a house number, and that one is `optional` — a street
    with no house identifies nobody under 152-ФЗ ст. 3 п. 1, so masking it is
    not an error and missing it is not a leak, and it is counted in its own
    column.
    """
    rng = ctx.rng
    second = _blank_place(rng)
    bare_street = rng.random() < 0.33
    if bare_street:
        # The verbatim second points that carry no number all carry a type word
        # — «поедем переулок северный», «поеду на областную улицу», «поедем
        # посёлок октябрьский». A bare «грибоедова» would be a surname in the
        # genitive as readily as a street, and putting that ambiguity into an
        # `optional` item hides it: an optional item is in a column nobody reads
        # closely, which is the wrong place for a hard case.
        kind = rng.choice(_TYPES_LEADING + _TYPES_TRAILING)
        pool = (_STREETS_LEADING.get(kind) or _STREETS_TRAILING[kind])
        second = _with(second, street=rng.choice(pool), type_word=kind,
                       type_trailing=kind in _TYPES_TRAILING)
    else:
        second = _with(second, house=rng.choice(_HOUSES))
        if rng.random() < 0.3:
            second = _with(second, entrance=_draw_entrance(rng))
    pickup = _render_place(place, ctx.register, rng)
    if bare_street:
        # A street with no number: rendered by hand rather than through
        # `_render_place`, because that function's whole contract is that a
        # value carries a house and the parts it returns say so.
        name = (second.street[:1].upper() + second.street[1:]
                if ctx.register == "clean" else second.street)
        drop_text = (f"{second.type_word} {name}" if second.type_word
                     and not second.type_trailing
                     else f"{name} {second.type_word}" if second.type_word
                     else name)
        dropoff = _Rendered(text=drop_text, parts={"street": drop_text},
                            shape=pickup.shape, selection=pickup.selection,
                            weight=pickup.weight, corpus=pickup.corpus,
                            licence=pickup.licence)
    else:
        dropoff = _render_place(second, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register,
                           _forbidden(pickup.text, dropoff.text))
    # «едим на гагарина пятьдесят» is the connector the register produces and it
    # governs a case this file does not decline; in the spoken registers that is
    # correct because it is what people say, and in `clean` it would be a
    # document written in dispatch grammar. The literary register gets the
    # literary connector instead of a declension rule for two words.
    connector = ("затем" if ctx.register == "clean"
                 else rng.choice(_INTENTS))
    slots = (
        _plain(_opener(ctx)), _S(pickup.text, "pickup", _sep(ctx)),
        _plain(connector), _S(dropoff.text, "dropoff", _sep(ctx)),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))

    pickup_item = _place_item("pickup", ctx, pickup, spans["pickup"], 1,
                              "pickup", "required", "pickup_said_as")
    dropoff_item = _place_item(
        "dropoff", ctx, dropoff, spans["dropoff"], 1, "dropoff",
        "optional" if bare_street else "required",
        "" if bare_street else "dropoff_said_as")
    arguments, judged = _judged(pickup.parts, ("street", "house"), "pickup_")
    arguments["pickup_said_as"] = pickup.text
    judged = judged + ("pickup_said_as",)
    items = ("pickup",)
    if not bare_street:
        drop_args, drop_judged = _judged(dropoff.parts, ("street", "house"),
                                         "dropoff_")
        arguments.update(drop_args)
        arguments["dropoff_said_as"] = dropoff.text
        judged = judged + drop_judged + ("dropoff_said_as",)
        items = ("pickup", "dropoff")
    return _case(
        ctx, messages, (_T_ROUTE, _T_LOOKUP), (pickup_item, dropoff_item),
        tuple(negatives),
        (LinkExpectation(
            left="pickup", right="dropoff", kind="different", case="",
            why="две точки маршрута — два места; одна подмена на обе означает "
                "машину, которая едет от двери к той же двери"),),
        (ExpectedCall(name="book_ride", arguments=arguments,
                      judged_args=judged, pii_items=items, after_msg=1),),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        pickup,
        "две точки маршрута в одной реплике, обе с номером дома прописью: "
        "связывание их в одну подмену не видно ни детекцией, ни ответом")


def _scenario_type_word(ctx: _Ctx, place: _Place) -> Case:
    """«улица дербеневская двадцать четыре строение пять», «даев переулок тринадцать».

    The type word is present, and it stands before the name as often as after it
    («воткинское шоссе», «русская набережная»). With a building after the house
    the value carries three numbers in words and two generic markers, which is
    where a probe reading «the last marker» and one reading «the first» disagree.
    """
    rng = ctx.rng
    rendered = _render_place(place, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register, _forbidden(rendered.text))
    slots = (
        _plain(_opener(ctx)), _plain(rng.choice(_PREPOSITIONS)),
        _S(rendered.text, "place", _sep(ctx)),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    item = _place_item("place", ctx, rendered, spans["place"], 1, "customer",
                       "required", "said_as")
    arguments, judged = _judged(
        rendered.parts, ("street", "house", "building", "entrance"), "")
    arguments["said_as"] = rendered.text
    return _case(
        ctx, messages, (_T_BUILDING, _T_LOOKUP), (item,), tuple(negatives), (),
        (ExpectedCall(name="register_building", arguments=arguments,
                      judged_args=judged + ("said_as",), pii_items=("place",),
                      after_msg=1),),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        rendered,
        "слово-тип улицы есть, но номер дома всё равно словом, и корпус со "
        "строением ставят рядом второе родовое слово")


def _scenario_fraction(ctx: _Ctx, place: _Place) -> Case:
    """«улица дзержинского два дробь восемь», «нижняя три четыре».

    A house number that is TWO numbers. Nothing in a written corpus produces it
    — a written address writes «2/8» and a scanner reads one token — and here it
    is four numeral words with an ordinary word in the middle. The tool takes
    the address as ONE string, so this is where `renumbered` and `truncated` are
    reachable per item rather than per parameter.
    """
    rng = ctx.rng
    rendered = _render_place(place, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register, _forbidden(rendered.text))
    slots = (
        _plain(_opener(ctx)), _plain(rng.choice(("", "", "я на", "нахожусь на"))),
        _S(rendered.text, "place", _sep(ctx)),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    item = _place_item("place", ctx, rendered, spans["place"], 1, "customer",
                       "required", "address")
    return _case(
        ctx, messages, (_T_ADDRESS, _T_LOOKUP), (item,), tuple(negatives), (),
        (ExpectedCall(name="save_address",
                      arguments={"address": rendered.text, "comment": ""},
                      judged_args=("address",), pii_items=("place",),
                      after_msg=1),),
        FinalAnswer(must_contain=(), must_not_contain=(), answer=""),
        rendered,
        "номер дома из двух чисел прописью: письменный корпус пишет «2/8» одним "
        "токеном и этой формы не производит вовсе")


def _scenario_confirm(ctx: _Ctx, place: _Place) -> Case:
    """The agent has to read the address back — the answer axis.

    THE FAILURE THIS CATCHES IS THE ONE THE OWNER NAMED: the customer is handed
    a substitute and told it is their own address. Nobody notices a plausible
    fake address, which is what makes it worse than a raw token surviving.
    `must_contain` is the real value, and the vault knows both strings exactly —
    the advantage this benchmark has over every LLM-judged one, whose judge
    cannot know which string was real.

    `must_not_contain` is deliberately EMPTY here and everywhere in this family:
    every value a `wordnum` reply could carry is the customer's own, so
    forbidding one would be a claim about how the model phrases a confirmation
    rather than about the gateway.
    """
    rng = ctx.rng
    rendered = _render_place(place, ctx.register, rng)
    chunk = _draw_negative(rng, ctx.register, _forbidden(rendered.text))
    ask = ("Повторите пожалуйста адрес, я хочу проверить."
           if ctx.register == "clean"
           else "повторите пожалуйста адрес я хочу проверить")
    slots = (
        _plain(_opener(ctx)), _plain(rng.choice(_PREPOSITIONS)),
        _S(rendered.text, "place", _sep(ctx)),
        _plain(chunk.cue), _S(chunk.value, "neg", _stop(ctx)),
    )
    text, spans = _compose(ctx, slots)
    messages = [_msg("system", _system_prompt(ctx.register)), _msg("user", text)]
    negatives = [Negative(value=chunk.value, start=spans["neg"][0],
                          end=spans["neg"][1], msg=1, family=chunk.family,
                          why=chunk.why)]
    _pad(messages, negatives, ctx, *_rung_targets(ctx.context))
    # The request to read it back is the LAST user turn, so the reply under test
    # is an answer to it and not to something twenty replies ago.
    messages.append(_msg("user", ask))
    item = _place_item("place", ctx, rendered, spans["place"], 1, "customer",
                       "required", "address")
    return _case(
        ctx, messages, (_T_VISIT, _T_LOOKUP), (item,), tuple(negatives), (),
        (ExpectedCall(name="schedule_visit",
                      arguments={"address": rendered.text, "when": ""},
                      judged_args=("address",), pii_items=("place",),
                      after_msg=1),),
        FinalAnswer(must_contain=(rendered.text,), must_not_contain=(),
                    answer=""),
        rendered,
        "клиент просит повторить адрес: подстановка, выданная за его "
        "собственный адрес, — самый тихий из исходов, потому что правдоподобный "
        "фальшивый адрес не замечает никто")


# --- drawing the value for each scenario ----------------------------------
#
# The shape of the place is what makes a scenario what it is, so it is drawn
# HERE and the scenario builders receive a finished `_Place`. That keeps the
# sentence-building and the value-drawing apart: a scenario that drew its own
# value could drift into building a different shape from the one its docstring
# claims, and nothing would notice.

def _place_naked(rng: random.Random) -> _Place:
    place = _blank_place(rng)
    place = _with(place, type_word="", type_trailing=False,
                  street=_free_street(rng))
    if rng.random() < 0.55:
        place = _with(place, entrance=_draw_entrance(rng),
                      entrance_numbered=rng.random() < 0.08)
    if rng.random() < 0.10 and place.street in _STREET_SLIPS:
        place = _with(place, slipped=True)
    return place


def _place_flat(rng: random.Random) -> _Place:
    place = _with(_blank_place(rng), type_word="", type_trailing=False,
                  street=_free_street(rng), marker=rng.random() < 0.25,
                  flat=rng.choice(_FLATS))
    if rng.random() < 0.2:
        place = _with(place, entrance=_draw_entrance(rng))
    return place


def _place_letter(rng: random.Random) -> _Place:
    place = _blank_place(rng)
    if rng.random() < 0.45:
        kind = rng.choice(_TYPES_TRAILING)
        place = _with(place, street=rng.choice(_STREETS_TRAILING[kind]),
                      type_word=kind, type_trailing=True)
    else:
        place = _with(place, type_word="", type_trailing=False,
                      street=_free_street(rng))
    place = _with(place, letter=rng.choice(_HOUSE_LETTERS), marker=False)
    if rng.random() < 0.4:
        place = _with(place, entrance=_draw_entrance(rng))
    return place


def _place_type_word(rng: random.Random) -> _Place:
    if rng.random() < 0.5:
        kind = rng.choice(_TYPES_LEADING)
        place = _with(_blank_place(rng), street=rng.choice(_STREETS_LEADING[kind]),
                      type_word=kind, type_trailing=False,
                      marker=rng.random() < 0.35)
    else:
        kind = rng.choice(_TYPES_TRAILING)
        place = _with(_blank_place(rng),
                      street=rng.choice(_STREETS_TRAILING[kind]),
                      type_word=kind, type_trailing=True, marker=False)
    draw = rng.random()
    if draw < 0.4:
        place = _with(place, building_kind=rng.choice(("корпус", "строение")),
                      building=rng.choice((1, 2, 3, 4, 5)),
                      building_ordinal=rng.random() < 0.15)
    elif draw < 0.65:
        place = _with(place, entrance=_draw_entrance(rng))
    return place


def _place_fraction(rng: random.Random) -> _Place:
    place = _with(_blank_place(rng), marker=False)
    if rng.random() < 0.5:
        place = _with(place, fraction=rng.choice((1, 2, 3, 4, 5, 8, 17)))
    else:
        place = _with(place, house_second=rng.choice((1, 2, 3, 4, 5, 17, 19)))
    if rng.random() < 0.35:
        place = _with(place, entrance=_draw_entrance(rng))
    return place


def _place_confirm(rng: random.Random) -> _Place:
    place = _place_naked(rng)
    if rng.random() < 0.3:
        place = _with(place, flat=rng.choice(_FLATS))
    return place


# --- the plan -------------------------------------------------------------
#
# The quotas follow the measured shape distribution rather than a uniform one:
# 53 of 169 hand-labelled values are «<улица> <число> <порядковое> подъезд» and
# 16 are the bare «<улица> <число>», so the two of them together are the largest
# scenario by a wide margin. `two_points` is 15 of 154 replies and gets the
# share that ratio earns it.

_SCENARIOS: tuple[tuple[str, object, object, tuple[str, ...]], ...] = (
    ("naked", _scenario_naked, _place_naked,
     ("solo", "short", "long", "deep")),
    ("flat", _scenario_flat, _place_flat, ("solo", "short", "long", "deep")),
    ("letter", _scenario_letter, _place_letter, ("solo", "short", "long")),
    ("two_points", _scenario_two_points, _place_naked,
     ("solo", "short", "long", "deep")),
    ("type_word", _scenario_type_word, _place_type_word,
     ("solo", "short", "long", "deep")),
    ("fraction", _scenario_fraction, _place_fraction, ("solo", "short")),
    ("confirm", _scenario_confirm, _place_confirm, ("short", "long", "deep")),
)

_QUOTA: dict[str, int] = {
    "naked": 48, "flat": 24, "letter": 20, "two_points": 22, "type_word": 20,
    "fraction": 14, "confirm": 22,
}

# `voice_raw` is the base register of this product and of this family. `clean`
# is three cases and exists to show the defect is in the shape probe rather than
# in the register — Russian paperwork spells the house number out by convention,
# so the literary case can carry the same shape without being contrived.
_REGISTER_MIX: tuple[tuple[str, int], ...] = (
    ("voice_raw", 120), ("voice_itn", 30), ("chat", 10), ("sloppy", 7),
    ("clean", 3),
)

_CONTEXT_WEIGHTS: dict[str, int] = {"solo": 40, "short": 30, "long": 20, "deep": 10}


def _draw_context(rng: random.Random, allowed: tuple[str, ...]) -> str:
    weights = [_CONTEXT_WEIGHTS[rung] for rung in allowed]
    return rng.choices(allowed, weights=weights, k=1)[0]


def build(seed: int, count: int) -> list[Case]:
    """The family, deterministic in `seed`.

    `seed` IS AN INT. The generator is made here, so this family's draws do not
    move when another family adds a scenario; a stream threaded through six
    generators would make every family depend on how many draws the families
    before it happened to make, and the corpus would stop being comparable to
    its own previous version for a reason unrelated to the corpus.
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
    # difference, so `build(seed, 170)` returns 170 cases and not 169.
    quotas["naked"] += count - sum(quotas.values())
    if quotas["naked"] < 1:
        raise ValueError(f"count {count} is too small to carry seven scenarios")

    # The mix is SCALED, never truncated. Cutting the tail of the list would
    # drop `clean` first — it is the smallest and it is last — and a family that
    # silently loses a register at a smaller `count` is a family whose ladder
    # cannot close on register at the rung that needs it most.
    registers: list[str] = []
    for name, share in _REGISTER_MIX:
        registers += [name] * max(1, round(share * count / TARGET))
    while len(registers) < count:
        registers.append("voice_raw")
    while len(registers) > count:
        registers.remove("voice_raw")
    rng.shuffle(registers)

    cases: list[Case] = []
    position = 0
    serial = 0
    for name, builder, drawer, contexts in _SCENARIOS:
        remaining = quotas[name]
        while remaining > 0:
            place = drawer(rng)                     # type: ignore[operator]
            serial += 1
            # One drawn value renders into one to three cases and they share a
            # cluster: error bars are computed over clusters, because one
            # address said three ways is one value and three occurrences, and an
            # interval over occurrences is narrower than the truth in our
            # favour.
            group = min(remaining, rng.choice((1, 1, 2, 2, 3)))
            cluster = f"wordnum:{name}:{serial:04d}"
            for _ in range(group):
                ctx = _Ctx(
                    case_id=f"wordnum-{name}-{position:03d}",
                    cluster=cluster,
                    register=registers[position],
                    context=_draw_context(rng, contexts),
                    # Both scope paths have to be exercised: a caller that hands
                    # us a conversation id and a caller that has none, which is
                    # a different code path in the gateway and is what a
                    # customer gateway without a conversation field triggers.
                    conversation_id=(f"conv-wordnum-{position:03d}"
                                     if position % 5 < 3 else ""),
                    rng=rng,
                )
                cases.append(builder(ctx, place))   # type: ignore[operator]
                position += 1
                remaining -= 1
                if remaining == 0:
                    break
    return cases


def main() -> int:
    """Build the family and refuse it if anything in it does not hold.

    Run directly — the repo has no test runner and every eval is a script with a
    `main()`:

        python3 bench/agentpii3/families/wordnum.py
    """
    cases = build(20260830, TARGET)
    problems: list[str] = []
    for case in cases:
        problems.extend(validate(case))
    registers: dict[str, int] = {}
    contexts: dict[str, int] = {}
    selections: dict[str, int] = {}
    duties: dict[str, int] = {}
    negatives: dict[str, int] = {}
    values: set[str] = set()
    spoken = 0
    items = 0
    for case in cases:
        registers[case.register] = registers.get(case.register, 0) + 1
        contexts[case.context] = contexts.get(case.context, 0) + 1
        selections[case.provenance.selection] = (
            selections.get(case.provenance.selection, 0) + 1)
        for item in case.pii:
            items += 1
            duties[item.duty] = duties.get(item.duty, 0) + 1
            spoken += int(item.spoken)
            if item.duty == "required":
                values.add(item.canonical.casefold())
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print(f"cases            {len(cases)}")
    print(f"clusters         {len({case.cluster for case in cases})}")
    print(f"registers        {dict(sorted(registers.items()))}")
    print(f"contexts         {dict(sorted(contexts.items()))}")
    print(f"selection        {dict(sorted(selections.items()))}")
    print(f"LOC items        {items}  ({dict(sorted(duties.items()))})")
    print(f"spoken values    {spoken} of {items}")
    print(f"distinct values  {len(values)}")
    print(f"negatives        {dict(sorted(negatives.items()))}")
    print(f"answer axis      {sum(1 for c in cases if c.final.must_contain)}")
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
