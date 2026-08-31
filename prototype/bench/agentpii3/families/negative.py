"""AgentPII-RU v3 — the NEGATIVE family. Nothing here may be masked.

THE QUESTION: the customer says something that LOOKS like personal data and is
not, and the agent has to put it into a tool call unchanged. Without this family
the benchmark measures recall and says nothing about its price.

WHY OVER-MASKING IS NOT THE MIRROR OF A LEAK, and why it needs its own family
rather than a precision column bolted onto the others. A leak is silent: the
value reaches the model and the conversation carries on looking correct. An
over-mask is LOUD AND BROKEN — a masked order number does not find the order, a
masked amount makes the invoice wrong, a masked room number sends the visitor to
the wrong floor. Both cost the customer, and only one of them is visible to the
detect axis. That is why every case here carries an EXPECTED CALL with the value
in it OPEN: a corpus that only said «do not mask this» would be passed by a
gateway that does nothing at all, and `MAX_NEGATIVE_ONLY_SHARE` exists because
that is a real way to be wrong.

WHERE THE MATERIAL COMES FROM, and it is the whole reason this family is worth
its 110 cases: **62 of them are utterances a living person said.** SOVA
RuDevices (CC BY 4.0, so the text ships) hand-annotated in
`rudevices_addresses.json`, class «не адрес» — read once by the address
annotator and once again here, and every reply carrying a person was dropped on
the second reading. No generator would have written «пушкина дом колотушкина»,
«ну х з как у вас но типа у меня строение глаза», «привет ты из дом ру» or «это
была декларация за первый квартал», and those four are exactly the shapes that
break an address detector: a surname beside «дом», the words «строение» and
«квартал» doing their ordinary jobs, a provider's brand name built out of the
word «дом».

THE MEASURED GROUND THIS FAMILY STANDS ON, from `mined/calls_grammar.json` and
`mined/dispatch_grammar.json`:

    число рядом с «кабинет» / «отделение»        528 реплик — крупнейший источник
    «улица» как двор, погода, прогулка            73
    «квартира» как жильё                          51
    число плюс единица измерения                 995
    голый подъезд без улицы                       15
    «проезд» как плата за поездку                 10

The largest false-positive source in this register is not an exotic string. It
is a number standing next to the word «кабинет», and it occurs 528 times.

WHAT IS A NEGATIVE AND WHAT IS `optional`, because the two are one edit apart and
the difference is the whole precision measurement. A negative may not be masked:
masking it is an error and it breaks the call. An `optional` item MAY be masked
without penalty — «улица вязов» with no house number identifies nobody (152-ФЗ
ст. 3 п. 1: hundreds of buildings stand on a street), so a gateway that masks it
is not wrong and a gateway that leaves it is not leaking. The eleven bare-street
cases carry exactly that, as `duty="optional"` with NO `tool_param`, and their
judged argument is deliberately a DIFFERENT value: an argument that may
legitimately arrive masked cannot be judged, and judging it would manufacture a
failure out of a permitted choice.

THE NOTE ARGUMENT IS A WHOLE-STRING CLAIM, AND IT IS STRONGER THAN THE LABELLED
SPANS ON PURPOSE. `log_note.text` carries the customer's utterance exactly as
said — a support operator writing the caller's own words into the ticket is a
real product shape, and it is the only tool that fits an utterance with no
structured slot in it («на улице погода хорошая» has no field to go in). A
gateway that masks something inside such an utterance that nobody labelled has
still broken the note, so the round-trip axis will fail where `false_masks`
reports nothing.

That asymmetry is intended, and it is paid for in two places rather than
asserted. `_audit_verbatim` refuses an utterance in which ANY number — not the
schema's run of four — stands outside a claimed span, because the note demands
every one of them back; `_audit_authored` does the same for every string this
module writes, after an agent turn saying «подождите пожалуйста одну минуту»
and a room line ending «на девять утра» had quietly put a maskable value in
four cases. And FOUR of the 62 are refused the note claim outright, by name:
«монро» is a surname, «рио де жанейро» and «овишен красноярье» are places,
«папа джонс» is a brand built from a person, and masking one of those is a
defensible call rather than a defect. All four carry a structured slot instead,
so none of them loses its judged argument.

WHAT THIS FAMILY DOES NOT DO. It writes no `required` personal datum at all, so
it contributes nothing to recall and nothing to `type_denominators`. That is the
definition of the family and also its bound: `validate_corpus` caps
negative-only cases at a tenth of the corpus, because each of them is passed by
a gateway that masks nothing.

THE LEGAL-ENTITY BUCKET, stated out loud because it is the one place the fixed
vocabulary does not fit. A company's ИНН and КПП are not personal data — Recital
14 puts the legal person outside the regulation and 152-ФЗ arrives at the same
place through its definition of the subject as a natural person — but
`schema.NEGATIVE_FAMILIES` has no entry for it and inventing one belongs to the
schema, not to a family module. They are filed under `order_number`, the
«document number that must not be masked» bucket, and `Negative.why` names the
reason so a reader is never left to infer it from the label.
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
    Case,
    ExpectedCall,
    FinalAnswer,
    InvalidCase,
    Message,
    Negative,
    PiiItem,
    Provenance,
    Source,
    ToolSchema,
    NUMERAL_WORDS,
    require_valid,
    unsafe_filler,
    validate,
)

FAMILY = "negative"
MODULE = "negative"
TARGET: int = 110

CACHE = Path.home() / ".cache" / "pseudex-bench"
RUDEVICES = CACHE / "speech_rudevices.jsonl"
LABELS = CACHE / "rudevices_addresses.json"
MINED = Path(__file__).resolve().parent.parent / "mined"

LICENCE = "CC BY 4.0"
CORPUS = "speech_rudevices"
# Rides with the corpus and not only with this file, for the same reason the ГАР
# attribution rides in the leased bundle: the consumer gets the set, never the
# repository.
ATTRIBUTION = "SOVA Dataset / RuDevices, распространяется по CC BY 4.0"
# 250 replies read out of the 4805 that carry a number. Every share over that
# layer is nineteen times smaller than it looks if this is dropped.
NUMBER_SAMPLE_WEIGHT = 19.22


# --- the mined grammars ----------------------------------------------------
#
# A shape id is CHECKED against the files, never trusted. A typo in a pattern
# string would make `Provenance.shape` name nothing, and «the form came from
# real speech» would be back to being an assertion — which is the state 1070 of
# v2's 1334 cases were in.

def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. The mined grammars are built by "
            f"bench/agentpii3/mine_calls.py and mine_dispatch.py; this family "
            f"cannot invent the shapes they carry.")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _known_shapes() -> frozenset[str]:
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


# The shapes this family may cite, and every one of them either carries NO
# personal data in the mined catalogue or carries the very ambiguity the case is
# about. `S_PAIR` and `S_RUN` are the two that DO carry something in the
# catalogue — a numeral run is the shape of a dictated identifier — and that is
# the point: the same run is an order number as often as it is an address, and
# the corpus has to hold both readings or the engine learns the wrong one.
S_STREET_NO_HOUSE = _shape(
    "улица <название> без номера дома — НЕ персональные данные, "
    "маскировать нечего")
S_TAIL_NO_STREET = _shape(
    "дом <число> / квартира <число> без улицы — сам по себе никого не определяет")
S_BRANCH = _shape(
    "<порядковое> кабинет / отделение — число рядом с местом, которое адресом "
    "НЕ является")
S_ROOM = _shape(
    "<порядковое числительное> кабинет — число, которое персональными данными "
    "не является")
S_TIME = _shape("в <число> ноль ноль — время; ноли проговариваются словом")
S_RUN = _shape("непрерывный пробег числительных длиной 4-8 слов, без единой цифры")
S_PAIR = _shape(
    "<число> <число> — самая частая длина пробега; дом, квартира, кабинет, дата")
S_ATTENTION = _shape("оклик перед значением: слушай, слышь, смотри, значит, короче")
S_HESITATION = _shape(
    "реплика открывается заминкой: эээ / ааа / нуу / иии, дальше значение")
S_REPEAT = _shape(
    "слово повторено подряд: «да да», «ноль ноль», «алло алло», «стоп стоп»")
S_OPENING = _shape("открытие звонка: алло / алё / аллё, дальше сразу представление")
S_ADDRESSING = _shape(
    "обращение вместо имени: молодой человек, девушка, мужчина, женщина, товарищ")
S_DICTATION = _shape(
    "диктовка вслух: «записывай», «записал», «пишите» — значение стоит рядом")
S_ECHO = _shape(
    "переспрос: «ещё раз», «повторите», «не слышу» — и значение звучит второй раз")


# --- corpus access ---------------------------------------------------------

@dataclass(frozen=True)
class _Utterance:
    key: str
    line: int
    text: str
    sha256: str


# (text, key, line, sha256, stratum, ((value, family, why-slug), ...))
_Verbatim = tuple[str, str, int, str, str, tuple[tuple[str, str, str], ...]]
# (text, key, line, sha256, stratum, the hand-annotated bare street)
_Bare = tuple[str, str, int, str, str, str]
# (text, key, line, sha256)
_Filler = tuple[str, str, int, str]


def _load_utterances() -> dict[str, _Utterance]:
    """Every distinct RuDevices reply, keyed by blake2b-6 of its own text.

    No fallback when the file is absent. A benchmark that quietly builds a
    smaller corpus because a source was missing reports a number for a set
    nobody can name, which is worse than not building at all.
    """
    if not RUDEVICES.exists():
        raise FileNotFoundError(
            f"{RUDEVICES} is missing. The speech corpora are not in the "
            f"repository; fetch RuDevices into ~/.cache/pseudex-bench/ before "
            f"building. Nothing here has a text-free fallback: 62 of the 110 "
            f"cases ARE those utterances.")
    table: dict[str, _Utterance] = {}
    with RUDEVICES.open(encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            text = str(json.loads(raw)["text"])
            key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
            if key in table:
                continue
            table[key] = _Utterance(
                key=key, line=number, text=text,
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    return table


def _source(text: str, key: str, line: int, sha256: str) -> Source:
    return Source(corpus=CORPUS, key=key, line=line, sha256=sha256,
                  licence=LICENCE)


def _locate(text: str, needle: str) -> tuple[int, int]:
    """The one place a span is FOUND rather than built, and it is bounded.

    A hand annotation names a substring of an UNCHANGED utterance; locating it
    is how such an annotation is READ, not a derivation from a generated
    string. The rule it may not break is that the string was never rewritten —
    so a needle occurring twice, or not at all, raises rather than picking one.
    """
    first = text.find(needle)
    if first < 0:
        raise InvalidCase(f"{needle!r} is not in {text!r}")
    if text.find(needle, first + 1) >= 0:
        raise InvalidCase(
            f"{needle!r} occurs twice in {text!r}; an annotation that does not "
            f"say WHICH one cannot be turned into an offset")
    return first, first + len(needle)


# --- message assembly ------------------------------------------------------
#
# Ground truth is what the generator BUILT. Every authored span below is
# recorded while the string is laid down, and no case searches its own finished
# text for a value it placed there. v2's predecessor matched by substring and
# lost every part a register transform had touched — 162 of 183 sloppy failures
# were that one bug, twice.

@dataclass(frozen=True)
class _Glue:
    """A piece appended with no space before it: a comma, a full stop."""

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
# A number in this register is a run of words, never a digit, and the tables are
# written out rather than pulled from a library so the contracted forms the
# register actually produces sit beside the canonical ones.

# 22.9% of every «-десят» form in the call corpus arrives contracted. That is
# the NORM of the register, not an oddity, and a pool that ships only the
# dictionary form measures the easy half of it. Applied to the dictated value
# itself, before the message is assembled, so the span recorded is the span of
# the string that was actually laid down.
# Read by the two guards further down. `NUMERAL_WORDS` is the schema's own list,
# so a number this module cannot see is a number `audit_unlabelled` cannot see
# either, and the two cannot drift apart.
_WORDS = re.compile(r"[а-яёa-z]+", re.IGNORECASE)
_NUMERALS = NUMERAL_WORDS

_CONTRACTED: dict[str, str] = {
    "пятьдесят": "песят",
    "шестьдесят": "шеесят",
    "семьдесят": "семесят",
    "восемьдесят": "восемесят",
}


def _contract(text: str, rng: random.Random) -> str:
    """Apply the measured contraction rate to a dictated number."""
    return " ".join(_CONTRACTED[word] if word in _CONTRACTED
                    and rng.random() < 0.229 else word
                    for word in text.split())


# --- the verbatim material -------------------------------------------------
#
# 62 utterances a living person said, from the hand annotation's «не адрес»
# class. FROZEN as literals — text, key, line and digest travel together — so
# the pool cannot drift when the mining filter is tuned, and `hydrate` can
# refuse a source that shifted underneath the offsets.
#
# The reasons live in one dictionary rather than beside each span: a reason
# written once is written once, and the table stays narrow enough to read.

_WHY: dict[str, str] = {
    "city_reference_1":
        "город как место события: сотни тысяч зданий, никого не "
        "определяет (152-ФЗ ст. 3 п. 1)",
    "city_reference_2":
        "микрорайон как часть города, без дома",
    "entrance_no_street_1":
        "порядковое плюс «подъезд» — форма адресного хвоста, но улицы "
        "в реплике нет",
    "entrance_no_street_2":
        "этаж без дома и без улицы — хвост адреса, которого нет",
    "fare_1":
        "«проезд» здесь плата за поездку, а не тип улицы",
    "fare_2":
        "«проезд» без имени и без дома — плата, а не улица",
    "flat_as_home_1":
        "порядковое плюс «квартиру» — форма адресного хвоста, а речь "
        "про покупку жилья",
    "flat_as_home_2":
        "«квартира» без номера — жильё, а не адресный хвост",
    "measure_1":
        "срок, а не номер дома",
    "measure_2":
        "длительность, а не номер",
    "measure_3":
        "расстояние, а не номер дома",
    "measure_4":
        "число плюс единица измерения — то же вето, что защищает "
        "«территория завода пять гектаров»",
    "measure_5":
        "длительность выступления",
    "measure_6":
        "срок",
    "measure_7":
        "время в пути",
    "order_number_1":
        "продиктованный номер заказа — дефект, который однажды уехал "
        "в прод: маскировался каждый",
    "order_number_2":
        "второй номер заказа в той же реплике, с обрезанным "
        "числительным «девяноста»",
    "order_number_3":
        "порядковый номер заказа в очереди",
    "quantity_1":
        "слово «телефон» стоит прямо перед числом, и число это цена, "
        "а не номер",
    "quantity_child_age":
        "возраст ребёнка в годах — персональными данными возраст "
        "становится от девяноста, а не здесь",
    "measure_delay":
        "опоздание в минутах: длительность, а не номер",
    "quantity_10":
        "пробег из трёх числительных подряд — по форме продиктованный "
        "идентификатор, по смыслу вилка суммы",
    "quantity_11":
        "цена пробегом из трёх числительных",
    "quantity_12":
        "порядковый номер круга",
    "quantity_13":
        "баллы экзамена",
    "quantity_14":
        "сто рублей на слух; слово «счёта» рядом не делает это "
        "номером счёта",
    "quantity_2":
        "цена фермы, а не номер",
    "quantity_3":
        "«карты» здесь видеокарты: слово-подсказка есть, банковской "
        "карты нет",
    "quantity_4":
        "цена",
    "quantity_5":
        "слово «номеров» рядом с числом, но это счёт гостиничных "
        "номеров",
    "quantity_6":
        "вилка цены за килограмм",
    "quantity_7":
        "возраст: персональными данными он становится от девяноста, а "
        "не здесь",
    "quantity_8":
        "количество штук",
    "quantity_9":
        "цена часа",
    "room_number_1":
        "число рядом с «кабинет» и «отделение» — 528 реплик корпуса "
        "звонков, крупнейший источник ложных срабатываний регистра",
    "room_number_2":
        "номер кабинета — не персональные данные, но маска ломает "
        "вызов: посетителя направят не туда",
    "street_no_name_1":
        "«улица» без имени — про погоду и двор, а не про адрес; самая "
        "частая ложная маска этого регистра",
    "street_no_name_10":
        "название провайдера, а не дом с номером",
    "street_no_name_11":
        "корпус прибора, а не корпус дома",
    "street_no_name_12":
        "идиома: фамилия плюс «дом» без номера — форма адреса без "
        "адреса",
    "street_no_name_13":
        "слово «адрес» произнесено, значения за ним нет",
    "street_no_name_2":
        "прилагательное плюс «улице» — ровно форма безмаркерной "
        "улицы, но дома нет и здание не определено",
    "street_no_name_3":
        "слова-подсказки «улицу» и «номер телефона» звучат, а "
        "значений за ними нет ни одного",
    "street_no_name_4":
        "поговорка, а не адрес",
    "street_no_name_5":
        "«тупик» — и тип улицы из списка ГАР, и обычное слово; здесь "
        "второе",
    "street_no_name_6":
        "тип улицы без имени и без дома",
    "street_no_name_7":
        "площадка, а не площадь: тип места, который адресный словарь "
        "читает как свой",
    "street_no_name_8":
        "«строение» здесь про устройство глаза, а не про корпус "
        "здания",
    "street_no_name_9":
        "квартал — и тип застройки, и период отчётности; здесь "
        "декларация",
    "time_of_day_1":
        "время парой числительных — по форме неотличимо от дома с "
        "квартирой",
    "time_of_day_2":
        "время с самоисправлением посередине",
    "time_of_day_3":
        "время, а порядковое «первого» рядом с числом читается как "
        "дом",
    "time_of_day_4":
        "время суток",
}

_TRAPS: tuple[_Verbatim, ...] = (
    ('на улице погода хорошая',
     'f44fdb7d1d17', 102, 'b27b98452ff6630e94aee1310c302db36ddd126322396d7db19e5142dd90e349', 'marker',
     (('улице', 'street_no_name', 'street_no_name_1'),)),
    ('на улице солнышко светит тепло',
     '9ef8b06372f0', 5565, 'f8cd3ea4caf8698e418b120cc6a97583ffd806cd826d7005057f86bbda7d1329', 'marker',
     (('улице', 'street_no_name', 'street_no_name_1'),)),
    ('тепло на улице реально тепло',
     '967ac2df0380', 38009, '86668f88b328389e304f16f4ddf35ab400845851bf816e8f975dac9b80603b68', 'marker',
     (('улице', 'street_no_name', 'street_no_name_1'),)),
    ('дождливо на улице однако',
     'c5c4989bc5e1', 40390, '7064e388cfb022ac4c73756f8149595203814dd387a759420d16fbbaa5def975', 'marker',
     (('улице', 'street_no_name', 'street_no_name_1'),)),
    ('на центральной улице поэтому',
     '1d6baeabab01', 17673, '14ddcb636f11bc2c7cba5ab41f4c6cf6b6e418771a959df06a753fb1060eefd4', 'marker',
     (('центральной улице', 'street_no_name', 'street_no_name_2'),)),
    ('если вы скажете улицу я вам скажу номер телефона куда звонить',
     '420882b66523', 5968, 'f8829eafcd560d928f90246e85fe861cc9d772171079399af2cc3d950147656b', 'marker',
     (('улицу', 'street_no_name', 'street_no_name_3'),)),
    ('когда-нибудь и на моей улице будет праздник',
     '353bf79e7b66', 2067, '3355da6a91d48c92f371692f6a44ca7904d106cfb28ba42f864704d7bae4a16c', 'marker',
     (('улице', 'street_no_name', 'street_no_name_4'),)),
    ('немножко в тупике',
     'b8425b1e2a05', 21860, '4721d361d0a413a745b88934351b99c11f1147ae477bf1d3be5e76209e5fb6db', 'marker',
     (('тупике', 'street_no_name', 'street_no_name_5'),)),
    ('вот это вот проспект просто',
     '349df99c504f', 15173, 'd15a74718e0f0bdb969a33530006a9ba7ff95ca0ee78b959f7bfed183046a55b', 'marker',
     (('проспект', 'street_no_name', 'street_no_name_6'),)),
    ('а это вот площадка',
     '05b5f84c5ee7', 18307, 'b16762ce952741a5bb27409be935678bfcc163d1205f236005712f4e43e1f057', 'marker',
     (('площадка', 'street_no_name', 'street_no_name_7'),)),
    ('ну х з как у вас но типа у меня строение глаза то есть',
     '8800bb1e705c', 12542, '304ea3864c6e3346eeea5833168be75beef31a050ee9df4d2ff3febe71259b0e', 'marker',
     (('строение', 'street_no_name', 'street_no_name_8'),)),
    ('это была декларация за первый квартал и эта же галоч',
     '04acf56a6243', 10688, '3ae1564ff4b90e18803b7cea26c2f1652ec9593fee3eef0d52a7b3071e8e7fdb', 'marker',
     (('первый квартал', 'street_no_name', 'street_no_name_9'),)),
    ('привет ты из дом ру',
     '534314cc2650', 7575, 'bc146ab0ef27ef246049524eaf9e3bd161d41300f842d08a2be642651538d523', 'marker',
     (('дом ру', 'street_no_name', 'street_no_name_10'),)),
    ('а корпус пластик или металл отсюда не видно',
     '3d9633bb3e80', 8572, 'ba51e107e37f9577072a7c185701077d3df7404b9fb2c284f0f8190f7ca67154', 'marker',
     (('корпус', 'street_no_name', 'street_no_name_11'),)),
    ('пушкина дом колотушкина',
     'a868c98fba90', 19340, '6a17ce0de1e8d3c0566e26bb81ba1b98381ecb3c2eb76d19af8763449c4a017f', 'marker',
     (('пушкина дом колотушкина', 'street_no_name', 'street_no_name_12'),)),
    ('а ребёнка то мне два было с этого адреса',
     'cb9165285db7', 2015, '0bf7e1d666df1ac2600e20808ac416042df3a7b047c8426d7227b83470e43f5d', 'random',
     (('два', 'quantity', 'quantity_child_age'),
      ('с этого адреса', 'street_no_name', 'street_no_name_13'),)),
    ('с дедушкой только только мы подумали купим-ка вторую квартиру понимаешь',
     'd9916a032e6a', 476, 'f589b396cef7ea1d0329eee095296a4e14a31c9014a4b5ec459ea50769b20b4e', 'marker',
     (('вторую квартиру', 'flat_as_home', 'flat_as_home_1'),)),
    ('ты берёшь одну квартиру',
     '40028f5a8e62', 4258, '9cefc9214a6465db1266062dfa6b7c3f7130e51c5a95a48190c29a5e656416d3', 'marker',
     (('одну квартиру', 'flat_as_home', 'flat_as_home_2'),)),
    ('у них в квартире хорошо убрано все чисто всегда',
     '4e5cec97859d', 31182, 'bdc9ce8c3b92f464f751ccd8ce27565a004f7fe927b38536a694188ee00cd8b5', 'marker',
     (('квартире', 'flat_as_home', 'flat_as_home_2'),)),
    ('и в двадцать лет у каждой советской семьи будет отдельная квартира',
     'a0d6953061b7', 4058, '50f35b54f4c16f09fa16194ef25195f24afc558766bec489fc163a825b2c2a21', 'marker',
     (
      ('отдельная квартира', 'flat_as_home', 'flat_as_home_2'),
      ('двадцать лет', 'measure', 'measure_1'),
     )),
    ('в моей квартире',
     '40941c356552', 22403, '275bb103e44ae2931365ba6ca6f507b733bdb4e44dec29e3ea61da4f05be9a34', 'marker',
     (('квартире', 'flat_as_home', 'flat_as_home_2'),)),
    ('что за азбука морзе что происходит в этом доме в этой квартире',
     '7be8d4d6ee0b', 7473, '995a5abe8145ac715c72d3a493e2b6956adf9404ffe108fc627f5510afd5c033', 'marker',
     (('в этой квартире', 'flat_as_home', 'flat_as_home_2'),)),
    ('шестой подъезд',
     '4bdd1d967905', 5564, '873c45edbe6511a1c6c2b47b0acba8f782a8e2996d5282e0653654c69b08239b', 'marker',
     (('шестой подъезд', 'entrance_no_street', 'entrance_no_street_1'),)),
    ('четвёртый подъезд',
     '508abb93c464', 9993, '368b3c87c5d979299fb67981d815d034bcc0d76f8614d2538868686bf7848d26', 'marker',
     (('четвёртый подъезд', 'entrance_no_street', 'entrance_no_street_1'),)),
    ('второй подъезд',
     '40c43e4fb028', 18622, '0ef44fb4384b3240ae6bf82d707bf8a2bbbb639a2742930954ccb6f126dd1895', 'marker',
     (('второй подъезд', 'entrance_no_street', 'entrance_no_street_1'),)),
    ('первый подъезд',
     '5fa00bf1574b', 31519, '674239dcb70bdec4a6993d5b3ec3b61c716e8392323696aefd650e2f99d2053c', 'marker',
     (('первый подъезд', 'entrance_no_street', 'entrance_no_street_1'),)),
    ('последний подъезд',
     '37b598c2f420', 35496, '071d8f0252fd067415df246997dac811b11ddf305f7288e246c3c76148633779', 'marker',
     (('последний подъезд', 'entrance_no_street', 'entrance_no_street_1'),)),
    ('первый подъезд от школы',
     '281a1accb977', 893, 'd71f9d2368b580d7b54bc0657a73b465b0d28eb5e3ace548bf373e74ae297b87', 'marker',
     (('первый подъезд', 'entrance_no_street', 'entrance_no_street_1'),)),
    ('я на одиннадцатом этаже ха-ха',
     '9eb1bd7e6f03', 5052, '5d9ef526b1ed054664fa1da162c3ff043e2b4f2fe9f53470bfc8a1188c4717bb', 'marker',
     (
      ('на одиннадцатом этаже', 'entrance_no_street', 'entrance_no_street_2'),
     )),
    ('реально просто возьму и спрыгнул со второго этажа',
     '555d03040b3e', 22104, 'a5afeacc37f92f0825db5f274eb8d06dfa51f9d6286700adfc15afdcd9b5791f', 'marker',
     (('со второго этажа', 'entrance_no_street', 'entrance_no_street_2'),)),
    ('начальнику второго отделения прибыть в триста четырнадцатый кабинет в понедельник',
     '442d8c4e840c', 6183, '9248072c9b0be4af12d122ecbbf22a2c830ea90ac39f6166a6942614aea62718', 'random',
     (
      ('второго отделения', 'room_number', 'room_number_1'),
      ('триста четырнадцатый кабинет', 'room_number', 'room_number_2'),
     )),
    ('у нас нет начальника второго отделения',
     '63620e73d295', 14514, '25a145c80bf9cd71f39a8f8b6f47ba0ab61648561c49d93b5c8236b6133590ba', 'random',
     (('второго отделения', 'room_number', 'room_number_1'),)),
    ('овишен красноярье заказ шестнадцать восемьдесят девять опоздаю на пять минут заказ шестнадцать девяноста пять опоздаю на пятнадцать минут',
     'c487152462d0', 9395, '365a60d026f3af54951e6e9c9fe186eed4e99ba46cae790d6f8435a0282408bf', 'random',
     (
      ('шестнадцать восемьдесят девять', 'order_number', 'order_number_1'),
      ('шестнадцать девяноста пять', 'order_number', 'order_number_2'),
      ('пять минут', 'measure', 'measure_delay'),
      ('пятнадцать минут', 'measure', 'measure_delay'),
     )),
    ('и седьмой заключительный заказ папа джонс',
     '75433f297461', 16359, '01735fee310f91234ccc497d9a729f19e79da2def0e915ceebc1731a2a06b68c', 'random',
     (('седьмой', 'order_number', 'order_number_3'),)),
    ('ну короче пятьдесят рублей проезд пятьдесят рублей ты тратишь на маску и перчатки',
     'c326eaf9e368', 8451, '98b262d943a75ccb6805fd79f7eb47be01e33d8829fbf4e72e9cc10801194e85', 'marker',
     (('пятьдесят рублей проезд пятьдесят рублей', 'fare', 'fare_1'),)),
    ('или проезд',
     '3e5138d55e8b', 8140, 'da7cba973d952f11d8f11017d0153826a7b5caf533e76ce7ab73fd9eeafe6dc1', 'marker',
     (('проезд', 'fare', 'fare_2'),)),
    ('так как я собираюсь ну я решила раз мой телефон за пятнадцать тысяч',
     'd54b01f06c23', 2220, 'dfcbbfd5856010a1a6aa21807675ceb92b590d56a2a795bc12df79774c6e3f3a', 'random',
     (('пятнадцать тысяч', 'quantity', 'quantity_1'),)),
    ('я посчитал вот это ферма за тридцать тысяч на пяти картах в общем это с',
     '57a92812791e', 929, 'bda739f192860a9d514e96b860152fd2848eece25ec24afcd03718521a9a7735', 'random',
     (
      ('тридцать тысяч', 'quantity', 'quantity_2'),
      ('пяти картах', 'quantity', 'quantity_3'),
     )),
    ('нет в четверг на пятнадцать пятнадцать и на улице я так поняла репетиция у нас будет',
     '1dc1cf4bf5cc', 19204, '296ce118d7ac43138233c5f2d19b3c136c01c5e769836282ed87791a41b7afec', 'marker',
     (
      ('пятнадцать пятнадцать', 'time_of_day', 'time_of_day_1'),
      ('улице', 'street_no_name', 'street_no_name_1'),
     )),
    ('не знаю но смотрите по я сейчас в квартиру потом в четыре четыре тридцать',
     'a671af8e80f8', 38667, '824908e3fc195650dc5164f6773cb198ba1c13a9434f85161292ae6ba3d8f335', 'marker',
     (
      ('квартиру', 'flat_as_home', 'flat_as_home_2'),
      ('четыре четыре тридцать', 'time_of_day', 'time_of_day_2'),
     )),
    ('двадцать минут первого и я почему-то сказал да приезжай',
     'e3ebc6be88ed', 5746, 'cbed259289e55db242902c921ef58b9bb2179a93bfc52a641712950333198112', 'random',
     (('двадцать минут первого', 'time_of_day', 'time_of_day_3'),)),
    ('у меня время пять утра мне через два часа на работу',
     '16c3d633e8c1', 42255, 'fc269c30217c7ec823f8fb18695a987a0573df999704b6dffa7609e82b0e1b31', 'random',
     (
      ('пять утра', 'time_of_day', 'time_of_day_4'),
      ('два часа', 'measure', 'measure_2'),
     )),
    ('в рио де жанейро стоит статуя христу-искупителю',
     '634b936f4e8e', 40470, 'bf88440e7c2a2979b1ec824adb617846bbb279b5102fc8d482522a7600b17918', 'random',
     (('рио де жанейро', 'city_reference', 'city_reference_1'),)),
    ('второй микрорайон и это мой район',
     'eca1299f1945', 9789, 'afbc74e79a66103b5c35b7391e4ef01ab70d7734268d4e4a7468b082fa5992b4', 'marker',
     (('второй микрорайон', 'city_reference', 'city_reference_2'),)),
    ('а она с друзьями в другой веранде сидела там метров через сто',
     'b6165bc2f987', 10592, '038780ce27663d454a2a9aa4020476c183f95750fd5da09f1eb92901e6f6b4f3', 'random',
     (('метров через сто', 'measure', 'measure_3'),)),
    ('а который вот этот вот вы за четыреста взяли он на семьдесят мегабит',
     'c1876e83a83c', 22372, 'b285fe20c70649f0fb502137032975a1f146b061bb82a18f32644029d92bb29f', 'random',
     (
      ('четыреста', 'quantity', 'quantity_4'),
      ('семьдесят мегабит', 'measure', 'measure_4'),
     )),
    ('и я потом узнала семьдесят номеров были откуплены на тот момент полностью под них отель и в тоже время',
     'f1f45dd289fc', 29403, '44c5f3b870aacadddc30a112047c3ddf6e873fe9e5b8c72aabfcb32ec9f99ac9', 'random',
     (('семьдесят номеров', 'quantity', 'quantity_5'),)),
    ('ну рублей там двадцать пять тире тридцать за килограмм а что',
     '5ef35311e0a8', 33667, '0af6da45c65717a9d00b3b158c1774d5b9d44054166e7c07bc488a0f0b7e7b47', 'random',
     (('двадцать пять тире тридцать', 'quantity', 'quantity_6'),)),
    ('привет мне двадцать один год',
     'b7d663bd936a', 35715, 'dcb0a831679ea3b14e0027d98568b0415bacafd9fe6f73f3062b218b6260a3a5', 'random',
     (('двадцать один год', 'quantity', 'quantity_7'),)),
    ('подготовить презентацию клуба на десять тридцать минут',
     '4a24535c9fa2', 3019, 'd6c6f64b4784a90abc9a95fb3aa360f9112a0e569f6dbc1e388a94fdffdb011c', 'random',
     (('десять тридцать минут', 'measure', 'measure_5'),)),
    ('четыре ореха тоже нормально',
     '92db38ae7707', 18110, 'dfc83ebe141d929687da57ca359c996175d31b2659b4bf2011d2faaba2f568d4', 'random',
     (('четыре ореха', 'quantity', 'quantity_8'),)),
    ('монро будние дни восемьсот рублей в час',
     'b3d5577e0978', 24081, '3c846e32c4b057231f167e27fa13725304832d676868d718cb8a0669643bfe7f', 'random',
     (('восемьсот рублей', 'quantity', 'quantity_9'),)),
    ('будут тридцать пять рублей сдирать',
     'a7f6df559b44', 3929, 'ce555e4e2a72445bc236a83779e925da0782c907d0965336e747382bbe7df067', 'random',
     (('тридцать пять рублей', 'quantity', 'quantity_4'),)),
    ('на четыре дня максимум',
     '7ec7fe318be5', 42443, '5d0234472685cadb5db9eb97fcef025fb59c3a2952ff457f02278670e29deca5', 'random',
     (('четыре дня', 'measure', 'measure_6'),)),
    ('тут пешком конечно дойти мне минут семь',
     '334e50733c49', 9832, '2e0a01bdad53bbb54fdcdd9a17e6b0b984e140d5d60586632bcaa392db1a3a1d', 'random',
     (('минут семь', 'measure', 'measure_7'),)),
    ('три года мм вообще не сдвигался со своего веса',
     'fa6d53842382', 12493, 'dde2c649ee0f9b1a0d24d06ef845fc35d2326b472f21a710a84ced36d93fd3e4', 'random',
     (('три года', 'measure', 'measure_6'),)),
    ('да ещё всего за какие-то восемь лет',
     '2b3d757c2719', 41557, '5553d5106904e596fceb47f46177e5ca45f1c851513603c72f1aa8f957376061', 'random',
     (('восемь лет', 'measure', 'measure_6'),)),
    ('двести триста тысяч',
     'd7a03ff6ae5a', 34456, '3ebd5c1935a3f2f18831b07c5f484790c608a3a146ecaa3b5154c510ac2575b3', 'random',
     (('двести триста тысяч', 'quantity', 'quantity_10'),)),
    ('припиши там ещё всего лишь за девятьсот девяносто девять рублей',
     'ff44640a10ff', 34258, 'd24e8427862549cfb1988a4270eb242cefe8379ee9c5dfc709b2aa76eacf497d', 'random',
     (('девятьсот девяносто девять рублей', 'quantity', 'quantity_11'),)),
    ('ну тридцать третий круг и',
     '0bfb45165fef', 29871, '33f4dc738916640b5efdb0e7e7d46ab748d7570c4fec8a4b06ca588e8f426464', 'random',
     (('тридцать третий', 'quantity', 'quantity_12'),)),
    ('ну либо же если экзамен там как пятьдесят баллов распределяются',
     '85661180d3f2', 23460, '9207ec547a7aa4d83e7c3cdb402afd790d4c9203668a334cec9edeac4e715468', 'random',
     (('пятьдесят баллов', 'quantity', 'quantity_13'),)),
    ('привет куда делся стольник со счёта',
     '889b318d2efb', 22051, 'acd20b3e34e8a46a30fbbe5fdd0b2b56936f0d9098cd00dd1397069024f84e25', 'random',
     (('стольник', 'quantity', 'quantity_14'),)),
)

# --- the bare streets, which are NOT negatives ------------------------------
#
# «улица вязов», «партизанский проспект» — a street with no house number, from
# the annotation's own «улица без номера» class, spans included. Hundreds of
# buildings stand on a street, so under 152-ФЗ ст. 3 п. 1 it identifies nobody:
# masking it is not an error and missing it is not a leak. `duty="optional"`,
# no `tool_param`, and never judged — an argument that may legitimately arrive
# masked cannot be a round-trip claim.

_BARE: tuple[_Bare, ...] = (
    ('так поедем на улицу марата',
     '693981cfcb5c', 4056, '3df8db4fe7f995c47e205a664772b3678b377a442c8eff5784344314871d4c91', 'marker', 'улицу марата'),
    ('улица вязов',
     '18282600ee2d', 8745, 'a7ff3ce23947f6fb92dab08f1531d72e06420145f8257efed4573a0ff92ed842', 'marker', 'улица вязов'),
    ('как пройти на улицу пушкина',
     '5bb404941ce3', 11463, '0968d2c6ae1a48e24f520b30fb9276f8f3ba1d522fe077b3a92dfeafaaa282d0', 'marker', 'улицу пушкина'),
    ('на бульваре героев',
     'd0469f6afec7', 19508, '30cafae55519dbd1b03d86f2f29138495e094382c240f02a10c153bdbf5a0e66', 'marker', 'бульваре героев'),
    ('в газовом переулке',
     'aba90b365deb', 21509, '9ee34e37235bdb0446ab6515494f87e521f815c574b70211192d7b9307f78598', 'marker', 'газовом переулке'),
    ('улица сабурова',
     '470eb45c5636', 27714, '3c401888a45a9ab4dbb072784729b61bcac333a14ee64451b2cb13c0ee17be6b', 'marker', 'улица сабурова'),
    ('партизанский проспект далеко от тебя',
     '140cb4654967', 40931, '71c8503541aa10860bf06aa4a099c9e035a2564057ca7d58df8ce3ffbeda9e8f', 'marker', 'партизанский проспект'),
    ('до воткинское шоссе остановка ударная',
     'f31dbfbd2490', 20285, '119e218fc6d6229b67ff05ae8046441de4c90786f9b6bf3542e63c1aa2a4604b', 'marker', 'воткинское шоссе'),
    ('могу вам предложить ещё на болшевском шоссе ещё у нас есть',
     '483046ed5b43', 4480, '012a748d318517c81e1c4e229a50ff589e1e4907d5eb38a3edd40cf980e9d2d4', 'marker', 'болшевском шоссе'),
    ('может быстро ответить а может очень долго вот сегодня сидели на горького одному',
     '91f0f75868fe', 33377, '1b7536263df8cd2b328bdf7ff9b43a9066e56adccff17cc3c86c544538c4c56e', 'random', 'горького'),
    ('а в другом месте на улице молостовых в филиале и даже близко метро то нужно ехать на автомобиле вот ну как-то так',
     'fb27c0938df7', 13995, '00e1b088a7daf37cae6604785364bd89478e5bd6d5f6f5a75ea6c045d92d438b', 'marker', 'улице молостовых'),
)

# --- filler ----------------------------------------------------------------
#
# Real speech, because nine replies in ten in the live corpora carry no
# personal data at all (1.995% of calls, 0.939% of RuDevices) and a long
# transcript authored by a generator carries a value in every second line —
# which inflates recall and precision at once.
#
# Selected mechanically and then read by hand: 55-150 characters, no digit, no
# numeral word, no address vocabulary, no patronymic tail, no common given
# name, no Latin, and a profanity block-list. The filter is deliberately BLIND
# to our recognizers and deliberately far too strict — over-rejecting filler
# costs nothing and biases nothing, because filler carries no gold, so the
# selection-bias rule that governs MEASURED material does not reach it. The
# direction is what makes it safe: a strict filter can only remove ballast, it
# can never decide what gets labelled.

_FILLER: tuple[_Filler, ...] = (
    ('мы включили просто английский режим и на английском языке', '443776deaa84', 8, '3a71d79d319f77b436268c2eab4578f529b508e5234def409665d3de987b86a9'),
    ('зачем нужен хлеб нарезка если самому можно взять и нарезать этот хлеб', 'd1b88cf530d0', 16, '211d67b695c8573d81f31df049cf64c47222616c62b61c651bc0b4bee857252f'),
    ('магазины без нас ничто ну почти также как мы без магазинов', '5a29b6820855', 59, '578cc867ba0c56e3d41e45bfaf7812596cc77dcbac3035beadcf2769ca997355'),
    ('сейчас ещё не знаю что делать типа если я увольняюсь сейчас', 'dab33b152256', 81, 'e3e6efc5166f37d842a40a926ed507c33632a8218e283bed43b390e1fc041a23'),
    ('есть у меня копия или то есть куда мне надо зайти чтобы это увидеть', 'f83dd1e8ca0b', 100, '89774db6748b130622aa5ad023cbc590de3984893c740fe22070f07ad6f58ba4'),
    ('пользоваться как пользователи то есть там им на компанию будет выдано например', '4e4cb0a8eddf', 154, 'c26819948db04f1c47da10ba720e68984201aca4453f6a3c82c5f1cecd361527'),
    ('ой мне через несколько минут выходить ну ладно в принципе нормально а у тебя что нового', '497cc0eedd02', 155, '00bd3f904e235ce6234731edfd74de4002d16f189362ea90b132c7220b767013'),
    ('я сегодня надела все самое лучшее украшение достала вчера', 'f77550218870', 163, '2e6bf04f56ec819ecd46b0363b8624b391890010adad5e56989d971637009fea'),
    ('не ври не ври я могу сейчас этот открыть если ты не удалил', 'c070e93e1fcd', 174, 'be0ddad4806660378488b4ea146e4b766dd4284232c6643931fd885a010455c9'),
    ('у такая вода доступна не только элите но и обычным людям', 'ea1293325bef', 185, 'd6809e846afb5909f65791d00cc6dd83d9ca180aba5731ce3a071b63763c4f05'),
    ('мне казалось что кто-то ввинтил в люстру новые лампочки более сильные', 'd76ff591baaa', 193, '2608f4c815d911a3d1976b03e736239a152fa8ba56b828970959f21a2f045254'),
    ('серийный номер не меняется после сброса он то есть серийный номер', '7bcb85e3b93c', 216, 'ffddab4151a2e2fbe096c0db3b0d02c8566979d063cca1af5669d3468747d1c1'),
    ('он всегда в чате вообще запрещают такое писать потому что', '50a67a1bbc65', 225, 'c20b753688e8272d0a26ac1581dc1b556421adf7b37c5f4a80a1fa717fe935ca'),
    ('по русскому сегодня на изложении сказали что типа не будет завтра литературы', '8b3d27eda8f6', 254, '53f771d8e27170f622a8d7f3fd9d40943d0cc04917c2e1c74aadb979c2151f03'),
    ('ну так пригласи кого-нибудь из своего города в этот чат', '316966a16b32', 260, 'db8280a340b94040fe86d347fb55ab46ab9e57cb75c48ebd8f8bf6f6d0bb8cf2'),
    ('ты не понял меня я доволен ботом он мне кажется кажется лучше его уже не найти', '5158c70a6da1', 272, '1b2b5724b958683280e47e5f7b154c9a553d264ab65b78e754ce11ee66024558'),
    ('их все не могут открыть похоже создатель данной таблицы', 'b78214d1ea39', 283, 'a37f1fc179f27180a79f584470a0e4690b74fe94b485e7710c1aed441eba5327'),
    ('а мы на самом деле про раковину под которую влезла стиралка больше говорим', '2846517f5782', 292, 'b78da2fcc6e7a8e8dafc1a34abe98e552e76d84d2df0922be0933f89e8d3ff96'),
    ('аа ну получается одни не оригинальные с проставками а другие оригинальные', '854c280b225b', 325, '8845cfe95ac86140db7d004a9998da781381771e5054a488c120e5f18f236b4f'),
    ('это я что-то неправильно сказала я уже плохо помню это давно было ну по-моему я так запомнила', '1da2d93d092a', 333, '07039863db544b6bf188a06ec8dbdd3550b66f348fdeef9e0526db478e4ef591'),
    ('картина стала конечно получше но не так что бы прям прогрессивно', 'aaa053b85b13', 323, '9e8d3765c475bb9c782963695466536d883ed9f0f82ac8de366ac5a20a0ed3a5'),
    ('значит у него тоже есть какой-то разум правильно какое-то сознание', '209216034e09', 363, '2777f60db518ea80ee0151ea3d9cfae80d745f43aaeaa134609c6386189b71e1'),
    ('ну а мне кажется сейчас такое время что скорее наоборот', 'dee1141ed642', 400, '018c851baa88a9436286b2478e27517d8d5658534651cda5bd1d9ca362c55f11'),
    ('ну поэтому чтобы я его там как-то находил если мне нужно будет', '00cb79971362', 407, 'eb6e21920c7f1d10dbec62f8c0668aeadd0ea7a70b5498f831e77f502b777a20'),
    ('что-то мне скучно сидеть в машине хоть ролики что-ли посмотреть я не знаю', '0f43cdb6ed39', 430, 'b3abfaea4087ca424daa3291c6095173ff1d9d5b9560f46dcd24c6f07a5e550a'),
    ('очень здорово что вот этими именно мыслями делятся участники тоже', 'e6765d19a5f6', 500, 'c67831dbee67cba504d429dbbf5d81fc29fa389aacb12696c95512687124f933'),
    ('вот это бинго была прикольная игра с этими билетами нормально мне понравилась', '4c2fed5a5932', 524, '115599735cb2ed79e7e0bea7342ff28a6f4ffe3a642b300bd7543e137f7bee1e'),
    ('не получается так что кто-то там что-то забыл затупил там', '1f3a207e3a45', 526, 'eca035dd40f436c3d2882e26453d7406ecd8db20c05eaab3a085995a529658e9'),
    ('сейчас её проводят практически все крупные провайдеры и почтовые сервисы', '7ce7d57eacd3', 583, '861c66e0eda6bd5f6b52344165c145c368fe0e8f2ad0d2a72cb58036e0d34555'),
    ('сейчас возьму специально короче выкручу децибелы максимум', '6ecd1377e7ca', 613, 'eabaf06104caabfdd6898ec745f6d1fb45a9ac114e781cd2cab3a464c1014fac'),
    ('на вот он галочку соответственно можно будет снять тогда мы это делать не будем', '14f3066718fd', 619, '800ff1a76bdedbce233d7b8d36459ee82f18f28a04599c4563da21d3df8ee397'),
    ('кто создал этот файл какой компьютер это сделал как это посмотреть чтобы мне убедиться что это ну моё', 'd799691639d5', 627, '43eee9e42d9ffd40e80cd7f7fe62b36d8f76c0c9245c56bfb652e0739e3b34cd'),
    ('спасибо потому что голос диктора радио но всё равно спасибо', '0cb6f083ae48', 634, 'e121ee96038959fc84b52835b5979030891d477f9f9157ee80b40ceb9bb48ffd'),
    ('и по факту вот возьми сейчас подумай сколько людей делает покупки в интернете', 'bf129bfe42c9', 652, '684bdd95e53a7c348b40659a942fc60c99f375029745fb95ae835de5ce438fcd'),
    ('чтоо когда было свободное время то думаю вот сейчас поиграю', '8410edbf132e', 661, 'e279cd7ec1a25ddd1bc99c06bae1f8806598f7f19a6a224d6d25acf23a3936a3'),
    ('вот всё правильно урезанная понимаешь разделяй и властвуй', '4aac40ed5a25', 691, '1d17e9b23e7552a2e42254cdfd6596d11260fc65382b739e3659d7bca8f5f332'),
    ('я вообще-то прошу прямых доказательств твоих доводов о мифологии', 'e4008b816143', 716, 'a0946423b559e4bc93f96ed1762dd8a7441b2d9daddd34d31e229159c5f0a20b'),
    ('наверное в каждом музей искусства есть реально копия этой статуи', 'a2c197c5ffe8', 720, '5a8cd1f228f2f1dc073e835565aed2d4c300e677c8f15b34f2996f6d54fc463e'),
    ('и может быть где-то ещё прислушаются и начнут делать удобный город', '257aefee372b', 722, '6a2b4e05181b02196befa4e3835a5e97a0947ee8086ba3ebf657044e14402b81'),
    ('и он растёт с каждым годом рост оборотов компании продолжается', '734b5a628d61', 733, 'c7b1a6dfbd8fc9ceb93aed3e4aaa74ace75cb2a5b199cfd3e2f26b36c0a69ba5'),
    ('клянусь что за фигня короче у меня все гифки сохраняются', '737631a20a25', 753, 'c5a4784383a0d7fe637775e32f89dea09ccea6346818ceb7a9df7e69bd1cdc0f'),
    ('нам это будет удобнее быстрее и экономнее чем возиться ээ с пересылками', '8c2b69651860', 761, 'b17471fdd2601b461113cf2cbe7aad22e499cea5b28fa67e7925d04b579f56ef'),
    ('большинство людей с которыми я общаюсь и которые не относятся к', '0eebd751dcc2', 767, 'e62e6179821cf82fdabe3f9f13580c5fdf095c905aacbf4859b121e1ed280d90'),
    ('но в итоге она мало того что оглушит так ещё и выдаст очень жёсткую вспышку', '43fb2fcbe65f', 779, '4d235a215b750ef65a149e15cfc75a7f3e93fd27be454a16aef33e0dfa721e89'),
    ('я сделал этот вывод исходя из твоей точки зрения ты высказался мне всё понятно', 'c06742597596', 782, '800d56681ed2d8302bb39e84c974d520f4e4e00211087d98ea37c010597d5cc2'),
    ('смотри говорит как так это сложно да может быть сложно на самом деле', 'c3ec9c8434fa', 796, 'a092ad2c28fd0c642e9385912eb69d2b4a253890cfb4d5bac3a1fbf41db407b7'),
    ('когда ты прокрашиваешь ты приблизительно понимаешь какую тебе делать форму', 'e018d2fff341', 801, '8ff53a0fbb27819ea5a2e9cad77f389288f769a8c8fa763761cf0f5bfc1974d1'),
    ('вообще может у меня нет вилки руками я его не поем естественно', 'c5627cb71eb1', 855, '47555e880dcfb1a95f5180b797a06d85bb5ae03bbfc4205259168c214049a8d6'),
    ('я её сняла потому что она висела прямо у меня над головой', '20502094a778', 856, 'a72856987b525a069b312c88fcc99d95ba97849bddac59d598c04e2094389caa'),
    ('если тебе скину от этого пользы никакой не будет ты какую-то фигню начнёшь делать', 'fe0deea70080', 934, 'a982e3c6126dcacf793f78b2cbe624515b819a2817b5f13850852f485aadb612'),
    ('а мне кажется скорее всего они перешли на тот же режим что и ютуб что они', 'ba610f5ed163', 8395, '0fbcc810ef03008b17bf985ff337e8246b9d06bf9c81e9536f9a397a637b6e49'),
    ('больше ответственности и обязанностей тем выше находится человек который должен тебя контролировать', '20c2a764621d', 5288, '61712dd055eba04edfd53d8c886d55aeb3907927777b8a849228fe12441436f7'),
    ('то что тебя плохо слышно в других приложениях это тоже минус', '1527f997360b', 29465, '712bcf800df413d0073460499ea4a3d2a5850189496a8cea6c069b24776ad943'),
    ('вот мебель мы можем привезти свою вполне себе но сейчас выбрали спать на диване', '24eb7005d2f1', 25220, 'bc4d29e2d7e678d9555c32f3d2f026d7f93619ccb1eb3b7f21dd5959a323899c'),
    ('вообще там кстати много повыставляли всего в ашане по скидончику', '340696053d9a', 3977, '96b9da4139312357eb282e0581ba8d8e82f185f5ee4ef0e1e1f2132f94b0ab06'),
    ('ничего кроме того что они там есть а каким образом они попали туда', '264e06b0a3c2', 13754, 'bb4a4ff9f679ead6005eef16df66e276604214870b9f43e855163bf7299915c3'),
    ('спросила можно ли проконсультироваться добрый день можно но немного позже', '7cdbbc5d0d84', 5082, 'fb464702db3f75fcaf8381a045882da2a3f2bdbdbe6ba54ce0685e0d46658f89'),
    ('это моё решение приводить новых читателей или не приводить нам дали партнёрку как бонус', 'bcfdf4006b77', 24588, '4f41c4f240c5f46fbe0af7efca66a5596fee21dc308bc25fc28071996e037450'),
    ('ну в любом случае шансов больше хотя конечно и прибыль меньше', '41686341fa40', 36347, 'dc95d1f2a7eda6a3e139a8654119f6512bc81d482a8eb1bfd98785a905caa3b2'),
    ('это не совсем правильно понял что именно я имел в виду тогда', '3dcf25a4907d', 3558, 'b13d8235ec8ff353acfb7062b8ca56e92a5c1c877ed2b55c95afd1899c428e5f'),
    ('просто у меня типа не грузилось и я это отправляла ещё до того как вы отгадали', '4e77896d8a3e', 33889, '14a8b39a07ebb2e0fb240321000ddc4cba84ad92085b72c2736bbeddd4873d7c'),
    ('и в данном случае только твоя фантазия тебе подсказывает какой должен быть этот человек', '7c63af98f1b2', 12602, '12c7b7924bf60512e201ad2352062998e6cef7ce2ba8672d7232caafc0bb8dd2'),
    ('потому что ты бы там такие вопросы не задавал но мне ты их задаёшь зачем', '981b22a7b656', 32151, 'c3bf1238e47cbb64de00dc09afbe897cc761517ccf31f07540941e9124ebbd8d'),
    ('и это всё становится ещё более сложным когда ты просто сталкиваешься с тем', 'f0b717c1170e', 7424, '34db14a9304e43d630ef4d2c0e6b0f6a91b86cf49e1584def45b8f9751305264'),
    ('а яндекс музыка так не может этим ходил одним ухом слышу тебя', 'ac4f65b6b913', 24283, '8708c948fc55ae2a0184c4b273957d5271245b5720d63caae2b666543970e5f3'),
    ('смотри там будет это ещё не все там ещё много чего надо будет сделать', '6f3120c1867b', 32395, '4d0bf79a1d88056b1e5d267121dac9f04806d9d0dcbb30b0f58769af5cd8a07f'),
    ('ну можно также без модов поиграть если тебе не понравится но типа', '50b1d8e7046e', 39636, 'd233c9a64ce6434e9942c0164250f7daed86a42ab79d46c370ab9e116fadb8e7'),
    ('в телеграм захожу и вижу то что там очень много сообщений непрочитанных и', 'f39e14e148b2', 10109, '0197d4c5c7833f21e486d71bb849e2d7bf17beeef88eee83501e2f1e04ecdcdc'),
    ('так и всё вместе примерно диапазон по выручке в месяц сколько это приносит', 'd2227c02d1f1', 33693, 'a246bd1148d5330037f79617b0281e4cdabfd9616532eb757c59165a9b5ad1df'),
    ('чудеса с такой лёгкостью с такой лёгкостью входит в вашу жизнь', 'd7f373606aef', 10538, 'b4ec1dd2ed523385fa03e65b3133d7b6c3ecbb24377229ae6091e8b8bfe11c56'),
    ('за счёт таких сделок и создаётся действительно крупный капитал', 'e8a4543d5f5a', 21576, '4448e4f73c782a29ca809cc1d9f2416df0e02265e63c5c2139a4f143485fa613'),
    ('как он сказал ах да извините я забыл вам сразу прозвонить сообщить', 'f71e7e8af6ab', 31639, '0f7b66d914df448d8cf9617df17ad16e9530188d8afe3fa76d8ed2b975392237'),
    ('кстати получается они у меня сняли деньги и в будущем возвратят немного больше чем я отдавал', 'd1660146460b', 3612, '3ba13166e2567b66d08ab32ccbcc1c754c6ebe4c56f62109ec7a82018d344f1f'),
    ('везде всё нормально было по счётчикам типа везде как бы в плюс они росли', 'f2cd57ee01be', 3458, '3eb90f8d8bcc8057418c0c35d1e022e1d7da54076a55232044f126253a5783cd'),
    ('вот это противоположная сторона нашему входу этого же здания', '1b6c79ee546c', 35811, '139d0197fdcccc25b2017d25d77bc52cd3ce17c38c23ba45dd13dc23434bc5a8'),
    ('вот мы сегодня да на работе как вы угадали пили мы чай пили мы кофе', '5769a9ec439e', 11624, '2fa34869bd8c58777a76a086601b9871980d6f91b2b1908f547d45391f2de3c8'),
    ('мелкий был у нас была такая штука горена по моему она называлась', 'a962a1c35f7a', 27045, 'ffc30443660ff69e4829c0d6426babdfb69f4deb472a12522913de2d70b111bc'),
    ('так как у меня ну итальянский ещё свободный соответственно и финансовый баланс меня взяли на его позицию', '16870b3b47ad', 14203, 'd72d8748646ad7a56a79ef4700a54a27ea4138b9162b25970c1b8a33f3e90e91'),
    ('короче я думаю что я б швейцарию больше полюбил чем дубай скорее всего ну по крайней мере', '1f636323d346', 4566, 'a8d80bd15e14975915dc9f5dff02e13523e3300a003b7e7d55d54132053b02e9'),
    ('крупных западных корпорациях даже нанимают талантливых блогеров для ведения блогов организации', 'd2f4fe6418c6', 30393, '9915732f4345fe67a02ff97b42b942246f742b7f8dae8319a1f86e6086eace2f'),
    ('ну с очень большой вероятностью ладно это покроет особенно вот если мы говорим про сейчашнее время', 'c45148877f49', 26069, '592d756dd8eadfd79bced228912e41c5eef45c70fa3eb82169f31738cd5e7039'),
    ('хочется вас действительно поблагодарить и все лицо в вашем всех сотрудников за ту работу', '25af1197b538', 16462, '45c8a4e12df8bfcec20eca0dde02cd4ea8eabd223215b6a01ed94fc984df22c7'),
    ('и потом по итогам говорить что они теперь очень несчастливы и так далее', '26ff55500975', 4170, 'd6af29207952458619e0ff138c2b33b739f39bdcd3380165236de519b6b89812'),
    ('гран туризма тоже очень крутой симулятор по этому симулятору', 'bffe10aed85d', 24427, '2d4a6cf5053ecb2d46eff11558de6500ca76147f8500335f0b1518edebf15f80'),
    ('нет стрелочки ну с телефона кидал скриншоты там нет стрелочки которая', '37d0f7535792', 2224, 'e8f48358846cdda2cf88eaff52ac2854cd4997b94cb828bffa274c567270142a'),
    ('мы покупаем для себя любимых набор витаминов или там кому что нужно', '739fe4ace9af', 33144, '4aece5b40d28a59ec8ce9dc2675159401603ed5ffea16446871963211f7797cc'),
    ('по этой теме так что это реально безграничная тема и психология довольно интересная штука поскольку', 'b740248f39ba', 34546, 'cb440abf17985fb0e0b1f98057a7c6e2326e5750289eee1484631b946c3e61fc'),
    ('вот я здесь хотя и недавно но примерно уже представляю что в чате происходит', '368372613f2d', 33575, '33021f299e73bf2c1ec808cb1878187f8f8a1e3aa32dfd7eca7b9ebf1117668c'),
    ('который проходил в золотом якоре это потрясающее мероприятие', 'c05293032a00', 15376, '5885eeeff9abd56b8668d1e4a739e4a2412698a36cc970893e8defba979e9fdc'),
    ('мм в любом случае то что ты сходила это было полезная история я думаю что', '0534317ccd83', 27489, '3f57636f77ffa0efa47749937efe3cbab16fd3baa360af13f57ce75d84fd477e'),
    ('но я уже говорил о том что такого ответа не находится если ты его видишь', 'c562717acaeb', 40592, '0df768bf089d5e2e9bf58fc6ce16ec826e013ef0957b9ae130e73802172d6c85'),
    ('ну почему не по пути ну мы же просто просто дружим понимаешь', '73aea0417155', 17776, '8948a6934910b2529fc7126e4f321d45e36522431c66255b0d40aa2188e2518c'),
    ('не то что вот прямо в ближайшее время типа сидим вот сейчас надо там', '7c4269ae1d6c', 37593, '235430e184b8576050b7017a371bee9e1eb3d239ead295c8fc11db49235671f3'),
    ('математике но как бы с другой стороны в принципе вдруг мне понравится быть инженером', 'b25e6509373b', 5235, 'eff38b3329a6986648fa2a090329c4889412ae95542f0cbb286b82aeafe31c86'),
    ('ээ я хотел узнать как аа обратиться к начальнику договорного отдела как фамилия имя отчество', 'c6456620c387', 3513, 'a3880a4b787df49e0622a05c1639bce08fa19f637cfa6ec178ceef408ba028ae'),
)

# --- the authored traps ----------------------------------------------------
#
# Values come in PAIRS — dictated and written — rather than being computed from
# an integer, because the two forms of «три четырнадцатый кабинет» and «кабинет
# 314» are the same number said in two channels and a numeral generator gets one
# of them subtly wrong every time. Pairing them also keeps the `voice_itn`
# register honest: ITN restores the digits an ASR heard, it does not rewrite the
# sentence around them.

@dataclass(frozen=True)
class _Line:
    """One authored utterance around one (or two) values that must not be masked."""

    prefix: str
    spoken: str
    typed: str
    mid: str        # words between the two values, "" when there is only one
    spoken2: str
    typed2: str
    suffix: str
    shape: str      # overrides the kind's shape; "" means the kind's own


@dataclass(frozen=True)
class _Kind:
    """A trap family, its tool slot, and the sentences it appears in.

    `shape` is the mined pattern this utterance's FORM reproduces, or "" when
    the kind belongs to a written channel neither speech corpus records — a
    track number, an article, a company's ИНН. Those cases are `template` and
    say so; citing a spoken numeral shape for a typed order number would be the
    kind of unfalsifiable provenance claim v3 exists to end.
    """

    family: str
    family2: str    # the SECOND value's family; «КПП» is not a measurement
    why: str
    why2: str
    shape: str
    tool: str
    slot: str
    slot2: str
    system: str
    lines: tuple[_Line, ...]


_SYS_OFFICE = ("Ты оператор бюро пропусков. Направляешь посетителей и "
               "вызываешь инструменты. Отвечай коротко.")
_SYS_SUPPORT = ("Ты оператор клиентской поддержки. Записываешь обращение "
                "дословно и вызываешь инструменты. Отвечай коротко.")
_SYS_SHOP = ("Ты оператор интернет-магазина. Работаешь с заказами и "
             "вызываешь инструменты. Отвечай коротко.")
_SYS_DISPATCH = ("Ты оператор службы такси. Принимаешь заявки и вызываешь "
                 "инструменты. Отвечай коротко.")


def _line_of(prefix: str, spoken: str, typed: str, suffix: str) -> _Line:
    """One value, no second, and the kind's own shape."""
    return _Line(prefix, spoken, typed, "", "", "", suffix, "")


_KINDS: dict[str, _Kind] = {
    "room": _Kind(
        family2="", family="room_number",
        why="номер кабинета — не персональные данные, а маска ломает вызов: "
            "посетителя направят не туда",
        why2="", shape=S_ROOM, tool="route_visit", slot="room", slot2="",
        system=_SYS_OFFICE,
        lines=(
            _line_of("зайдите в", "три четырнадцатый кабинет", "кабинет 314",
                     "там всё лежит"),
            _line_of("пропуск в", "четыре двенадцатый кабинет", "кабинет 412",
                     "пропустите пожалуйста"),
            _line_of("подойдите в", "два одиннадцатый кабинет", "кабинет 211",
                     "это налево от лифта"),
            _line_of("нам в", "пять двадцатый кабинет", "кабинет 520",
                     "если он открыт"),
        )),
    "branch": _Kind(
        family2="", family="room_number",
        why="число рядом с «отделение» — вместе с «кабинетом» это 528 реплик "
            "корпуса звонков, крупнейший источник ложных срабатываний регистра",
        why2="", shape=S_BRANCH, tool="route_visit", slot="branch", slot2="",
        system=_SYS_OFFICE,
        lines=(
            _line_of("это из", "второго отделения", "отделение 2",
                     "нас там ждут"),
            _line_of("передайте в", "третьего отделения", "отделение 3",
                     "они сами заберут"),
            _line_of("мы от", "пятого отделения", "отделение 5", "как обычно"),
            _line_of("документы для", "шестого отделения", "отделение 6",
                     "заберите на входе"),
        )),
    "time": _Kind(
        family2="", family="time_of_day",
        why="время суток: ноли проговариваются словом, и пара числительных по "
            "форме неотличима от дома с квартирой",
        why2="", shape=S_TIME, tool="book_slot", slot="time", slot2="",
        system=_SYS_OFFICE,
        lines=(
            _line_of("подъехать надо", "к девяти ноль ноль", "к 9 00",
                     "раньше не пустят"),
            _line_of("нам", "к десяти ноль ноль", "к 10 00", "не позже"),
            _line_of("приём", "в четырнадцать ноль ноль", "в 14 00",
                     "по записи"),
            _Line("запишите", "на восемь тридцать", "на 8 30", "",
                  "", "", "если есть место", S_PAIR),
        )),
    "order": _Kind(
        family2="", family="order_number",
        why="продиктованный номер заказа — дефект, который однажды уехал в "
            "прод: маскировался каждый, и заказ переставал находиться",
        why2="", shape=S_RUN, tool="find_order", slot="order_id", slot2="",
        system=_SYS_SHOP,
        lines=(
            _line_of("это по заказу", "сорок один ноль девять шестьдесят семь",
                     "410967", "посмотрите что с ним"),
            _line_of("номер заказа", "двадцать два ноль восемь пятнадцать",
                     "220815", "он всё ещё не собран"),
            _line_of("заказ", "шестьдесят три ноль ноль сорок два", "630042",
                     "его так и не собрали"),
            _line_of("по заказу", "семнадцать девяносто четыре ноль пять",
                     "179405", "что там по срокам"),
        )),
    "quantity": _Kind(
        family2="", family="quantity",
        why="количество, а не номер: число, за которым стоит считаемое слово, "
            "никого не определяет",
        why2="", shape="", tool="quote_price", slot="amount", slot2="",
        system=_SYS_SHOP,
        lines=(
            _line_of("возьмём", "пять литров", "5 литров", "хватит на месяц"),
            _line_of("скидка", "двадцать процентов", "20 процентов",
                     "она ещё действует"),
            _line_of("у нас", "двенадцать филиалов", "12 филиалов",
                     "везде одинаково"),
            _line_of("это будет", "пятьсот рублей", "500 рублей",
                     "с доставкой"),
        )),
    "measure": _Kind(
        family2="", family="measure",
        why="число плюс единица измерения — то же вето, что защищает "
            "«территория завода пять гектаров» от чтения как адреса",
        why2="", shape="", tool="book_slot", slot="duration", slot2="",
        system=_SYS_SHOP,
        lines=(
            _line_of("участок", "пять гектаров", "5 гектаров",
                     "весь под паром"),
            _line_of("хранение", "на пятнадцать суток", "на 15 суток",
                     "дальше платно"),
            _line_of("ехать", "два часа сорок минут", "2 часа 40 минут",
                     "если без пробок"),
            _line_of("склад", "сто двадцать квадратных метров",
                     "120 квадратных метров", "больше не надо"),
        )),
    "fare": _Kind(
        family2="", family="fare",
        why="«проезд» здесь плата за поездку, а не тип улицы из списка ГАР",
        why2="", shape="", tool="fare_lookup", slot="amount", slot2="",
        system=_SYS_DISPATCH,
        lines=(
            _line_of("а", "проезд пятьдесят рублей", "проезд 50 рублей",
                     "или больше стало"),
            _line_of("у вас", "проезд тридцать два рубля", "проезд 32 рубля",
                     "я правильно помню"),
            _line_of("платим", "за проезд шестьдесят", "за проезд 60",
                     "наличными"),
        )),
    "city": _Kind(
        family2="measure", family="city_reference",
        why="город как место, а не как чей-то адрес: город не берёт номера "
            "дома, поэтому это вето, а не голос",
        why2="число рядом с названием города — не номер дома, а величина",
        shape="", tool="city_info", slot="city", slot2="figure",
        system=_SYS_SUPPORT,
        lines=(
            _Line("а в", "сочи", "сочи", "сейчас", "двадцать пять градусов",
                  "25 градусов", "купаться можно", ""),
            _Line("у нас в", "москве", "москве", "уже", "двенадцать филиалов",
                  "12 филиалов", "и все работают", ""),
            _Line("в", "казани", "казани", "открыли", "восемь пунктов выдачи",
                  "8 пунктов выдачи", "за год", ""),
        )),
    "tail": _Kind(
        family2="", family="entrance_no_street",
        why="хвост адреса без улицы: дом, квартира, подъезд или этаж сами по "
            "себе не определяют никого",
        why2="", shape=S_TAIL_NO_STREET, tool="route_visit", slot="room",
        slot2="", system=_SYS_DISPATCH,
        lines=(
            _line_of("это", "дом пять квартира двенадцать", "дом 5 квартира 12",
                     "улицу я не помню"),
            _line_of("мы в", "квартире сорок шесть", "квартире 46",
                     "дом какой не скажу"),
            _line_of("стою", "у шестого подъезда", "у подъезда 6",
                     "адрес не мой я в гостях"),
            _line_of("мы на", "девятом этаже", "9 этаже", "лифт не работает"),
        )),
    "flat": _Kind(
        family2="", family="flat_as_home",
        why="«квартира» без номера — жильё, а не адресный хвост",
        why2="", shape="", tool="log_note", slot="text", slot2="",
        system=_SYS_SUPPORT,
        lines=(
            _line_of("я", "квартиру", "квартиру", "снимаю а не покупал"),
            _line_of("мы", "квартиру", "квартиру", "так и не купили"),
            _line_of("надо", "квартиру", "квартиру", "убрать перед приездом"),
        )),
    "street": _Kind(
        family2="", family="street_no_name",
        why="«улица» без имени — двор, погода, прогулка; самая частая ложная "
            "маска этого регистра",
        why2="", shape="", tool="log_note", slot="text", slot2="",
        system=_SYS_SUPPORT,
        lines=(
            _line_of("на", "улице", "улице", "холодно я подожду внутри"),
            _line_of("по всему", "кварталу", "кварталу", "свет погас"),
            _line_of("выйди на", "улицу", "улицу", "я тебя не вижу"),
        )),
    "track": _Kind(
        family2="", family="order_number",
        why="трек-номер посылки — реквизит отправления, а не человека",
        why2="", shape="", tool="track_parcel", slot="track", slot2="",
        system=_SYS_SHOP,
        lines=(
            _line_of("трек", "", "80099612345678", "посылка не двигается"),
            _line_of("отследите", "", "45012398765432", "она где-то застряла"),
            _line_of("трек номер", "", "12300945671234", "ничего не понятно"),
        )),
    "article": _Kind(
        family2="", family="order_number",
        why="артикул товара — реквизит номенклатуры, а не человека",
        why2="", shape="", tool="find_article", slot="article", slot2="",
        system=_SYS_SHOP,
        lines=(
            _line_of("артикул", "", "АРТ-4590112", "он ещё в наличии"),
            _line_of("нужен", "", "SKU-778120", "он ещё есть"),
            _line_of("по артикулу", "", "112004458", "цену скажите"),
        )),
    "contract": _Kind(
        family2="", family="order_number",
        why="номер договора — реквизит документа; «догвор» с опечаткой ломает "
            "и подсказку, и разбор",
        why2="", shape="", tool="check_contract", slot="contract", slot2="",
        system=_SYS_SUPPORT,
        lines=(
            _line_of("договор", "", "44-ФЗ/2024-118", "он у вас есть"),
            _line_of("по договору", "", "ДГ-2023-00471", "что там с актом"),
            _line_of("номер договора", "", "778/12-АБ", "продлеваем"),
        )),
    "code": _Kind(
        family2="", family="order_number",
        why="код подтверждения — одноразовый реквизит операции, не человека",
        why2="", shape="", tool="confirm_code", slot="code", slot2="",
        system=_SYS_SUPPORT,
        lines=(
            _line_of("код", "", "4821", "он пришёл только что"),
            _line_of("код подтверждения", "", "907364", "срок минута"),
            _line_of("прислали код", "", "55120", "он не подходит"),
        )),
    "flight": _Kind(
        family2="", family="order_number",
        why="номер рейса — реквизит перевозки, а не пассажира",
        why2="", shape="", tool="flight_status", slot="flight", slot2="",
        system=_SYS_SUPPORT,
        lines=(
            _line_of("рейс", "", "SU 1402", "он задерживается"),
            _line_of("по рейсу", "", "DP 407", "что с посадкой"),
            _line_of("рейс номер", "", "U6 289", "во сколько прилёт"),
        )),
    "company": _Kind(
        family2="order_number", family="order_number",
        why="ИНН юридического лица идентифицирует ОРГАНИЗАЦИЮ: Recital 14 "
            "выводит юрлицо из-под регламента, 152-ФЗ приходит туда же через "
            "определение субъекта как физлица",
        why2="КПП — реквизит постановки на учёт организации, у физлица его "
             "нет вовсе",
        shape="", tool="check_company", slot="inn", slot2="kpp",
        system=_SYS_SUPPORT,
        lines=(
            _Line("Проверьте контрагента:", "", "ИНН 7707083893", "и",
                  "", "КПП 770701001", "перед оплатой.", ""),
            _Line("Реквизиты поставщика:", "", "ИНН 7728168971", "плюс",
                  "", "КПП 772801001", "счёт выставлен.", ""),
        )),
    "gost": _Kind(
        family2="", family="order_number",
        why="номер стандарта — публичный реквизит документа",
        why2="", shape="", tool="find_article", slot="article", slot2="",
        system=_SYS_SHOP,
        lines=(
            _line_of("нужен по", "", "ГОСТ 33222-2015", "у вас такой есть"),
            _line_of("маркировка", "", "ГОСТ Р 51074-2003", "она обязательна"),
        )),
}


# --- tools -----------------------------------------------------------------
#
# Every tool here takes the customer's value AS SPOKEN and one argument that is
# NOT judged. The unjudged one is the point τ²-bench makes with `compare_args`
# and it is the whole reason `ExpectedCall.judged_args` exists: `note` is the
# model's own wording and comparing it would fail a gateway for a choice the
# model made, while `room`, `order_id` and `amount` carry what the customer
# said and are the only things this benchmark has an opinion about.

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


_TOOLS: dict[str, ToolSchema] = {
    "log_note": _tool(
        "log_note", "Записать реплику клиента в обращение ДОСЛОВНО.",
        {"text": "реплика клиента без изменений", "channel": "канал обращения"}),
    "route_visit": _tool(
        "route_visit", "Направить посетителя внутри здания.",
        {"room": "кабинет, этаж или адресный хвост, как назвал посетитель",
         "branch": "отделение или подразделение", "note": "комментарий"}),
    "book_slot": _tool(
        "book_slot", "Записать на время.",
        {"time": "время, как его назвал клиент",
         "duration": "длительность, срок или мера", "note": "комментарий"}),
    "find_order": _tool(
        "find_order", "Найти заказ по номеру, который назвал клиент.",
        {"order_id": "номер заказа как он прозвучал", "note": "комментарий"}),
    "quote_price": _tool(
        "quote_price", "Посчитать сумму или количество.",
        {"amount": "сумма или количество как его назвал клиент",
         "count": "второе количество, если клиент назвал два",
         "note": "комментарий"}),
    "fare_lookup": _tool(
        "fare_lookup", "Уточнить стоимость проезда.",
        {"amount": "стоимость проезда как её назвал клиент",
         "note": "комментарий"}),
    "city_info": _tool(
        "city_info", "Справка по городу или району.",
        {"city": "город или район",
         "figure": "число, названное рядом с городом — градусы, филиалы, склады",
         "note": "комментарий"}),
    "track_parcel": _tool(
        "track_parcel", "Отследить посылку по трек-номеру.",
        {"track": "трек-номер отправления", "note": "комментарий"}),
    "find_article": _tool(
        "find_article", "Найти позицию по артикулу или номеру стандарта.",
        {"article": "артикул или номер стандарта", "note": "комментарий"}),
    "check_contract": _tool(
        "check_contract", "Найти договор по номеру.",
        {"contract": "номер договора", "note": "комментарий"}),
    "confirm_code": _tool(
        "confirm_code", "Проверить код подтверждения.",
        {"code": "код подтверждения", "note": "комментарий"}),
    "flight_status": _tool(
        "flight_status", "Статус рейса.",
        {"flight": "номер рейса", "note": "комментарий"}),
    "check_company": _tool(
        "check_company", "Проверить контрагента-юрлицо по реквизитам.",
        {"inn": "ИНН организации", "kpp": "КПП организации",
         "note": "комментарий"}),
}

# The family → (tool, slot) map the verbatim cases route by. `street_no_name`
# and `flat_as_home` are absent on purpose: an utterance about the weather has
# no structured field to go into, and `log_note` is the honest answer for it.
_SLOT: dict[str, tuple[str, str]] = {
    "room_number": ("route_visit", "room"),
    "entrance_no_street": ("route_visit", "room"),
    "time_of_day": ("book_slot", "time"),
    "measure": ("book_slot", "duration"),
    "order_number": ("find_order", "order_id"),
    "quantity": ("quote_price", "amount"),
    "fare": ("fare_lookup", "amount"),
    "city_reference": ("city_info", "city"),
}
# The second slot of the same tool, used when one utterance carries two values
# the same tool consumes. «начальнику второго отделения прибыть в триста
# четырнадцатый кабинет» is one sentence with two of them and both have to
# arrive open, or the case measures half of what it holds.
_ALT_SLOT: dict[tuple[str, str], str] = {
    ("route_visit", "room"): "branch",
    ("book_slot", "time"): "duration",
    ("quote_price", "amount"): "count",
}


# --- transcript construction ----------------------------------------------

@dataclass(frozen=True)
class _Draft:
    messages: list[Message]
    pii: list[PiiItem]
    negatives: list[Negative]


def _new_draft() -> _Draft:
    return _Draft(messages=[], pii=[], negatives=[])


def _add(draft: _Draft, role: str, text: str, source: Source | None) -> int:
    draft.messages.append(Message(role=role, content=text, source=source,
                                  name=""))
    return len(draft.messages) - 1


_AGENT_TURNS: tuple[str, ...] = (
    "угу слушаю вас",
    "да я на линии говорите",
    "хорошо записала подождите пожалуйста минуту",
    "понимаю вас",
    "ага",
    "сейчас гляну по системе",
    "поняла вас",
    "да да я слушаю",
    "минуту пожалуйста я тут смотрю",
    "принято",
    "хорошо я всё записала",
    "понятно",
)


def _fill(draft: _Draft, pairs: int, pool: tuple[_Filler, ...],
          rng: random.Random) -> None:
    """`pairs` exchanges of ordinary conversation carrying nothing.

    Drawn WITHOUT replacement inside one case: a repeated string is a mask-cache
    hit, and that is a claim a case may make deliberately, never one the filler
    should make by accident.
    """
    used = {message.content for message in draft.messages}
    available = [entry for entry in pool if entry[0] not in used]
    if pairs > len(available):
        raise InvalidCase(f"{pairs} filler pairs asked of {len(available)}")
    for text, key, line, sha in rng.sample(available, pairs):
        _add(draft, "user", text, _source(text, key, line, sha))
        _add(draft, "assistant", rng.choice(_AGENT_TURNS), None)


_DEEP_FLOOR: int = 4_100


def _fill_to_floor(draft: _Draft, pool: tuple[_Filler, ...],
                   rng: random.Random) -> None:
    """Keep talking until the transcript clears the `deep` character floor.

    A fixed pair count cannot clear it — the utterances have real lengths, and a
    draw of forty short ones lands under the floor while forty long ones land
    well over. Padding to the floor is what makes `deep` mean one thing in every
    case rather than «about forty replies, whatever that came to».
    """
    used = {message.content for message in draft.messages}
    available = [entry for entry in pool if entry[0] not in used]
    rng.shuffle(available)
    for text, key, line, sha in available:
        if sum(len(m.content) for m in draft.messages) >= _DEEP_FLOOR:
            return
        _add(draft, "user", text, _source(text, key, line, sha))
        _add(draft, "assistant", rng.choice(_AGENT_TURNS), None)
    raise InvalidCase(
        f"the filler pool ran out before the deep floor of {_DEEP_FLOOR} "
        f"characters; widen the pool rather than lowering the floor — a `deep` "
        f"rung under it is a `long` case wearing the wrong label")


def _finish(case_id: str, register: str, context: str, provenance: Provenance,
            cluster: str, conversation_id: str, draft: _Draft,
            tools: tuple[ToolSchema, ...], calls: tuple[ExpectedCall, ...],
            final: FinalAnswer, annotators: int, note: str) -> Case:
    return require_valid(Case(
        id=case_id, family=FAMILY, register=register, context=context,
        provenance=provenance, cluster=cluster,
        conversation_id=conversation_id, messages=tuple(draft.messages),
        tools=tools, pii=tuple(draft.pii), negatives=tuple(draft.negatives),
        links=(), calls=calls, final=final, preceded_by="",
        annotators=annotators, adjudicated=False, note=note))


def _note_call(text: str, channel: str, index: int) -> ExpectedCall:
    """The claim every case makes: the customer's words reach the ticket intact.

    A WHOLE-STRING claim, and deliberately stronger than the labelled spans — a
    gateway that masks something in this utterance that nobody labelled has
    still broken the note, and the note is what the operator reads. It is the
    only tool that fits an utterance with no structured field in it, which is
    most of what people actually say.
    """
    return ExpectedCall(name="log_note",
                        arguments={"text": text, "channel": channel},
                        judged_args=("text",), pii_items=(), after_msg=index)


def _slot_calls(negatives: list[Negative], index: int) -> list[ExpectedCall]:
    """The structured half: every value in the field a tool would consume it in.

    ONE CALL PER TOOL where the slots differ, and a SECOND CALL of the same tool
    where they collide. «начальнику второго отделения прибыть в триста
    четырнадцатый кабинет» is one sentence with two room values and the branch
    slot takes the second; «заказ шестнадцать восемьдесят девять … заказ
    шестнадцать девяноста пять» is one sentence with two order numbers and there
    is no second order slot, so it is two calls. Dropping the leftover — which is
    what a single-call rule does — would leave a labelled negative with no judged
    argument, and then the case measures half of what it holds.

    Values whose family has no slot at all (the weather, a flat as a dwelling)
    return nothing: they are covered by the note, which is the honest answer for
    an utterance with no structured field in it.
    """
    calls: list[ExpectedCall] = []
    pending: dict[str, list[dict[str, str]]] = {}
    for negative in negatives:
        route = _SLOT.get(negative.family)
        if route is None:
            continue
        # A structured slot takes a VALUE, not a clause. «пятьдесят рублей
        # проезд пятьдесят рублей» is one span only because the price is said
        # twice and a repeated string has no single offset; putting that whole
        # phrase into `fare_lookup.amount` would be a call nobody makes.
        #
        # The test is a REPEATED NON-NUMERAL word, not a word count. A word
        # count of four looked right and quietly dropped «сорок один ноль
        # девять шестьдесят семь» — a six-word dictated order number, which is
        # the single defect this family exists for. A number said aloud is long
        # by nature; a clause is what repeats its nouns. «к девяти ноль ноль»
        # repeats «ноль» and stays, because a numeral repeating is how a number
        # is spoken.
        content = [word for word in _WORDS.findall(negative.value.lower())
                   if word not in _NUMERALS]
        if len(content) != len(set(content)):
            continue
        tool, slot = route
        # «второго отделения» and «триста четырнадцатый кабинет» share a family
        # and must not share a field; the branch slot exists for exactly that.
        if tool == "route_visit" and "отделен" in negative.value:
            slot = "branch"
        properties = _TOOLS[tool]["function"]["parameters"]["properties"]
        rows = pending.setdefault(tool, [{}])
        for row in rows:
            place = slot
            if place in row:
                place = _ALT_SLOT.get((tool, slot), "")
            if not place or place in row or place not in properties:
                continue
            row[place] = negative.value
            break
        else:
            rows.append({slot: negative.value})
    for tool, rows in pending.items():
        for row in rows:
            if not row:
                continue
            arguments = dict(row)
            arguments["note"] = "клиент назвал это сам"
            calls.append(ExpectedCall(
                name=tool, arguments=arguments, judged_args=tuple(row),
                pii_items=(), after_msg=index))
    return calls


def _kind_call(kind: "_Kind", values: tuple[str, ...],
               index: int) -> ExpectedCall | None:
    """The authored half, routed by the KIND rather than by the family.

    A company's ИНН and a dictated order number are both filed under
    `order_number` — the schema's vocabulary has no legal-entity bucket — so
    routing them by family would put the ИНН into `find_order.order_id`, which
    is not a call anybody would make. The kind knows its own tool and says so.
    """
    if kind.tool == "log_note":
        return None
    slots = [slot for slot in (kind.slot, kind.slot2) if slot]
    arguments = {slot: value for slot, value in zip(slots, values) if value}
    if not arguments:
        return None
    judged = tuple(arguments)
    arguments["note"] = "клиент назвал это сам"
    return ExpectedCall(name=kind.tool, arguments=arguments,
                        judged_args=judged, pii_items=(), after_msg=index)


def _tools_for(calls: tuple[ExpectedCall, ...]) -> tuple[ToolSchema, ...]:
    """Only the tools a case actually offers. A schema list is not a catalogue."""
    names: list[str] = []
    for call in calls:
        if call.name not in names:
            names.append(call.name)
    return tuple(_TOOLS[name] for name in names)


# --- openers ---------------------------------------------------------------
#
# The wrapper a real utterance arrives in, and each one names the mined shape it
# reproduces. `<число> кабинет` has a shape of its own; «пять литров» does not,
# so for those kinds the OPENER is what the provenance cites — the form came
# from speech even where the value is a pool draw, and `Provenance.shape` has to
# say which of the two it is talking about.
_OPENERS: tuple[tuple[str, str], ...] = (
    ("слушай", S_ATTENTION),
    ("слышь", S_ATTENTION),
    ("короче", S_ATTENTION),
    ("значит", S_ATTENTION),
    ("эээ", S_HESITATION),
    ("нуу", S_HESITATION),
    ("ааа", S_HESITATION),
    ("алло алло", S_REPEAT),
    ("да да", S_REPEAT),
    ("алё", S_OPENING),
    ("девушка", S_ADDRESSING),
    ("молодой человек", S_ADDRESSING),
    ("записывай", S_DICTATION),
    ("пишите", S_DICTATION),
    ("ещё раз повторяю", S_ECHO),
)

# Typed channels have no mined opener catalogue behind them and do not pretend
# to: these cases are `template` and the register gate is what keeps them
# lower-case, so a `clean` case cannot hide here.
_TYPED_OPENERS: tuple[str, ...] = ("", "слушайте", "добрый день", "привет")

_TYPO_KEYS: dict[str, str] = {
    "а": "ф", "в": "ы", "е": "к", "и": "м", "к": "е", "м": "и", "н": "г",
    "о": "л", "р": "п", "с": "ч", "т": "ь", "у": "ц", "л": "о", "п": "р",
}


def _typo(word: str, rng: random.Random) -> str:
    """A keyboard error, not a phonetic one.

    `sloppy` and `voice_raw` are separate registers because their errors have
    different causes and break different things: ASR mangles a word by sound
    («триц», «песят», «лермонтого»), a keyboard by adjacency («Кзнецов»). It is
    applied to the words AROUND the value and never inside it — a typo in an
    order number is a different order, and the case would then be asking the
    gateway to preserve a value the customer did not give.
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


def _sloppy(text: str, rng: random.Random) -> str:
    if not text:
        return text
    words = text.split()
    position = rng.randrange(len(words))
    words[position] = _typo(words[position], rng)
    return " ".join(words)


_CHANNELS: tuple[str, ...] = ("телефон", "чат", "почта")

# A typed `short` case may not be padded with speech. The filler pool is real
# RuDevices audio transcript, and a chat thread with a spoken reply in the
# middle of it is a case nobody would recognise as their own traffic — the
# register gate would still pass it, because `has_capital` and `has_punct` are
# ANY over the user turns, which is exactly the kind of gap a gate cannot see.
# Authored, and lower case in the two chat registers so a `clean` case cannot
# smuggle its capital in through the tail.
_TYPED_TAIL: dict[str, str] = {
    "chat": "жду ответа спасибо",
    "sloppy": "жду отвте спасибо",
    "clean": "Жду подтверждения.",
}


# --- the verbatim cases ----------------------------------------------------

# The whole-string note claim is refused on FOUR of the 62, and naming them is
# cheaper than pretending they are safe. Each carries a proper noun that a
# reasonable NER will tag — «монро» is a surname, «рио де жанейро» and «овишен
# красноярье» are places, «папа джонс» is a brand built from a person — and
# masking one of those is a defensible call, not a defect. Judging the whole
# string there would fail a gateway for something this corpus does not label and
# has no opinion about. All four carry a structured slot instead, so none of
# them loses its judged argument.
_NOTE_UNSAFE: frozenset[str] = frozenset({
    "634b936f4e8e", "b3d5577e0978", "c487152462d0", "75433f297461",
})


def _system_for(family: str) -> str:
    return {
        "room_number": _SYS_OFFICE,
        "entrance_no_street": _SYS_OFFICE,
        "order_number": _SYS_SHOP,
        "quantity": _SYS_SHOP,
        "measure": _SYS_SHOP,
        "fare": _SYS_DISPATCH,
        "time_of_day": _SYS_OFFICE,
    }.get(family, _SYS_SUPPORT)


def _verbatim_case(index: int, entry: _Verbatim, rng: random.Random) -> Case:
    """One real utterance, unchanged, with the trap inside it labelled.

    `solo`, and that is not a shortcut: a real reply IS one message, and
    assembling several of them into a transcript would make the case something
    the annotator never read. The value of these 62 is precisely that nobody
    wrote them — «пушкина дом колотушкина» and «это была декларация за первый
    квартал» are shapes no generator invents and every address detector trips
    over.
    """
    text, key, line, sha, stratum, spans = entry
    draft = _new_draft()
    _add(draft, "system", _system_for(spans[0][1]), None)
    index_user = _add(draft, "user", text, _source(text, key, line, sha))
    for value, family, why in spans:
        start, end = _locate(text, value)
        draft.negatives.append(Negative(value=value, start=start, end=end,
                                        msg=index_user, family=family,
                                        why=_WHY[why]))
    calls: list[ExpectedCall] = []
    if key not in _NOTE_UNSAFE:
        calls.append(
            _note_call(text, _CHANNELS[index % len(_CHANNELS)], index_user))
    calls.extend(_slot_calls(draft.negatives, index_user))
    if not calls:
        raise InvalidCase(
            f"{key}: no judged argument — a negative nothing carries into a "
            f"call is a claim that over-masking is free")
    families = sorted({negative.family for negative in draft.negatives})
    return _finish(
        case_id=f"neg-v{index:02d}", register="voice_raw", context="solo",
        provenance=Provenance(
            kind="verbatim", corpus=CORPUS, key=key, shape="",
            selection=stratum, licence=LICENCE,
            weight=NUMBER_SAMPLE_WEIGHT if stratum == "random" else 1.0),
        cluster=f"neg-v-{key}", conversation_id="",
        draft=draft, tools=_tools_for(tuple(calls)), calls=tuple(calls),
        final=FinalAnswer((), (), ""), annotators=1,
        note=f"настоящая реплика, не тронутая: маскировать в ней нечего "
             f"({', '.join(families)}), страта {stratum}")


# --- the bare-street cases -------------------------------------------------

# What the customer says AFTER the bare street. Authored, because the second
# turn has to carry a value the round trip can judge, and the street itself
# cannot be that value: it is `optional`, so a gateway masking it is right.
_BARE_FOLLOWUP: tuple[str, ...] = (
    "tail", "room", "time", "quantity", "branch", "measure", "fare", "order",
    "tail", "room", "time",
)


def _bare_case(index: int, entry: _Bare, rng: random.Random) -> Case:
    """A street with no house number: `optional`, and never judged.

    The claim this case makes is the one the corpus would otherwise never make.
    «улица вязов» identifies nobody — 152-ФЗ ст. 3 п. 1, hundreds of buildings
    stand on a street — so masking it is not an error and missing it is not a
    leak. It goes in its own column, never into recall, and its value reaches no
    judged argument: an argument that may legitimately arrive masked cannot be a
    round-trip claim, and judging it would manufacture a failure out of a
    permitted choice.

    NOT `verbatim`, and the difference matters: the first message IS a real
    utterance and its span is the hand annotation, but the second is authored,
    so the case as a whole does not claim to be something a human said. `key`
    names the utterance the optional value came from.
    """
    text, key, line, sha, stratum, street = entry
    kind = _KINDS[_BARE_FOLLOWUP[index % len(_BARE_FOLLOWUP)]]
    row = kind.lines[index % len(kind.lines)]
    cluster = f"neg-b-{key}"
    draft = _new_draft()
    _add(draft, "system", _SYS_DISPATCH, None)
    index_street = _add(draft, "user", text, _source(text, key, line, sha))
    start, end = _locate(text, street)
    draft.pii.append(PiiItem(
        id="s1", type="LOC", value=street, canonical=street, start=start,
        end=end, msg=index_street, identity=f"{cluster}-place",
        duty="optional", value_source="corpus", spoken=True, tool_param=""))
    _add(draft, "assistant",
         "а дом какой" if kind.family == "entrance_no_street"
         else "угу слушаю вас", None)
    opener = _OPENERS[index % len(_OPENERS)]
    follow, spans = _line((opener[0], row.prefix, (row.spoken, "v"), row.suffix))
    index_follow = _add(draft, "user", follow, None)
    draft.negatives.append(Negative(
        value=row.spoken, start=spans["v"][0], end=spans["v"][1],
        msg=index_follow, family=kind.family, why=kind.why))
    calls: list[ExpectedCall] = [
        _note_call(follow, _CHANNELS[index % len(_CHANNELS)], index_follow)]
    calls.extend(_slot_calls(
        [n for n in draft.negatives if n.msg == index_follow], index_follow))
    return _finish(
        case_id=f"neg-b{index:02d}", register="voice_raw", context="short",
        provenance=Provenance(
            kind="recombined", corpus=CORPUS, key=key,
            shape=S_STREET_NO_HOUSE, selection=stratum, licence=LICENCE,
            weight=NUMBER_SAMPLE_WEIGHT if stratum == "random" else 1.0),
        cluster=cluster,
        conversation_id=f"conv-{cluster}" if index % 2 else "",
        draft=draft, tools=_tools_for(tuple(calls)), calls=tuple(calls),
        final=FinalAnswer((), (), ""), annotators=1,
        note="голая улица без номера дома: маскировать её не ошибка и "
             "пропустить не утечка — колонка `optional`, и судится не она")


# --- the authored cases ----------------------------------------------------

@dataclass(frozen=True)
class _Spec:
    kind: str
    register: str
    context: str
    compare: bool


def _authored_case(position: int, occurrence: int, spec: _Spec,
                   pool: tuple[_Filler, ...], rng: random.Random) -> Case:
    """One authored utterance in one register, at one depth.

    The value is a pool draw and the FORM is a mined shape — either the value's
    own (`<порядковое числительное> кабинет`) or, where the value has none, the
    opener's (`оклик перед значением`). The typed registers cite neither and are
    `template`: no speech corpus records a chat thread, and claiming a spoken
    numeral shape for a typed article number would be exactly the unfalsifiable
    provenance v3 exists to end.
    """
    kind = _KINDS[spec.kind]
    row = kind.lines[occurrence % len(kind.lines)]
    speech = spec.register in ("voice_raw", "voice_itn")
    spoken = spec.register == "voice_raw"
    value = _contract(row.spoken, rng) if spoken else row.typed
    value2 = _contract(row.spoken2, rng) if spoken else row.typed2
    if not value:
        raise InvalidCase(
            f"{spec.kind} has no dictated form and cannot appear in "
            f"{spec.register}: a written requisite said aloud is a different "
            f"case and belongs to `spoken_id`, not here")
    if spec.register == "clean":
        opener, shape = "", ""
    elif speech:
        opener, shape = _OPENERS[occurrence % len(_OPENERS)]
    else:
        opener, shape = _TYPED_OPENERS[occurrence % len(_TYPED_OPENERS)], ""

    prefix, mid, suffix = row.prefix, row.mid, row.suffix
    if spec.register == "sloppy":
        prefix, suffix = _sloppy(prefix, rng), _sloppy(suffix, rng)

    parts: list[object] = [opener, prefix, (value, "v")]
    if value2:
        parts += [mid, (value2, "v2")]
    parts.append(suffix)
    text, spans = _line(tuple(parts))

    draft = _new_draft()
    _add(draft, "system", kind.system, None)
    if spec.context == "long":
        _fill(draft, 4, pool, rng)
    elif spec.context == "deep":
        _fill_to_floor(draft, pool, rng)
    elif spec.context == "short" and not spec.compare and speech:
        _fill(draft, 1, pool, rng)
    index_user = _add(draft, "user", text, None)
    draft.negatives.append(Negative(
        value=value, start=spans["v"][0], end=spans["v"][1], msg=index_user,
        family=kind.family, why=kind.why))
    if value2:
        draft.negatives.append(Negative(
            value=value2, start=spans["v2"][0], end=spans["v2"][1],
            msg=index_user, family=kind.family2 or kind.family,
            why=kind.why2 or kind.why))

    answer = ""
    rival_call: ExpectedCall | None = None
    if spec.compare:
        # The сверка turn: a DIFFERENT value of the same kind, and the agent has
        # to say they are not the same. If the gateway masked both and handed
        # back one substitute for two values — a linking bug — the model answers
        # «да» and the case catches a defect no span comparison can see.
        other = kind.lines[(occurrence + 1) % len(kind.lines)]
        rival = _contract(other.spoken, rng) if spoken else other.typed
        if rival == value:
            raise InvalidCase(f"{spec.kind}: сверка needs two distinct values")
        _add(draft, "assistant", "поняла записала" if speech else
             "принято, записал" if spec.register == "clean" else "принято", None)
        head = "а вы записали"
        query, qspans = _line((head, (rival, "r"), "да" if speech else ""))
        index_rival = _add(draft, "user", query, None)
        draft.negatives.append(Negative(
            value=rival, start=qspans["r"][0], end=qspans["r"][1],
            msg=index_rival, family=kind.family, why=kind.why))
        # The сверка turn gets its OWN note call. The closed answer already
        # catches a gateway that folded two values into one substitute, but an
        # answer is not an argument: the owner's rule is that every value which
        # may not be masked reaches a tool OPEN, and a negative measured only by
        # a yes/no would be the one exception nobody could see.
        rival_call = _note_call(
            query, _CHANNELS[(position + 1) % len(_CHANNELS)], index_rival)
        answer = "нет"
    elif spec.context == "short" and not speech:
        _add(draft, "assistant", "принято, проверяю", None)
        _add(draft, "user", _TYPED_TAIL[spec.register], None)

    calls: list[ExpectedCall] = [
        _note_call(text, _CHANNELS[position % len(_CHANNELS)], index_user)]
    if rival_call is not None:
        calls.append(rival_call)
    extra = _kind_call(kind, (value, value2), index_user)
    if extra is not None:
        calls.append(extra)
    cluster = f"neg-{spec.kind}-{spec.register}"
    provenance = (
        Provenance(kind="recombined", corpus=CORPUS, key="",
                   shape=row.shape or kind.shape or shape,
                   selection="authored",
                   licence=LICENCE, weight=1.0)
        if speech else
        Provenance(kind="template", corpus="authored", key="", shape="",
                   selection="authored", licence="authored", weight=1.0))
    return _finish(
        case_id=f"neg-a{position:02d}", register=spec.register,
        context=spec.context, provenance=provenance, cluster=cluster,
        conversation_id=f"conv-{cluster}-{position}" if position % 3 else "",
        draft=draft, tools=_tools_for(tuple(calls)), calls=tuple(calls),
        final=FinalAnswer((), (), answer), annotators=0,
        note=f"{spec.kind}: значение, которое маскировать нельзя, идёт в "
             f"аргумент открытым; регистр {spec.register}, ступень "
             f"{spec.context}" + (", со сверкой" if spec.compare else ""))


# --- the plan --------------------------------------------------------------
#
# Written out rather than sampled, because the composition IS the argument: 62
# verbatim cases, 11 optional streets, 19 recombined speech cases across all
# four depths, and 18 typed cases for the reqisites no speech corpus records.
# A sampler would make «which registers does this family cover» a question you
# answer by running it.
_PLAN: tuple[_Spec, ...] = (
    _Spec("room", "voice_raw", "solo", False),
    _Spec("branch", "voice_itn", "solo", False),
    _Spec("time", "voice_raw", "short", True),
    _Spec("order", "voice_raw", "short", True),
    _Spec("quantity", "voice_itn", "short", False),
    _Spec("measure", "voice_itn", "short", False),
    _Spec("fare", "voice_raw", "short", False),
    _Spec("city", "voice_raw", "short", False),
    _Spec("tail", "voice_itn", "long", False),
    _Spec("flat", "voice_raw", "long", False),
    _Spec("street", "voice_raw", "long", False),
    _Spec("room", "voice_itn", "long", True),
    _Spec("order", "voice_itn", "long", False),
    _Spec("quantity", "voice_raw", "long", False),
    _Spec("time", "voice_itn", "long", True),
    _Spec("branch", "voice_itn", "long", False),
    _Spec("room", "voice_raw", "deep", False),
    _Spec("order", "voice_itn", "deep", True),
    _Spec("measure", "voice_itn", "deep", False),
    _Spec("track", "chat", "solo", False),
    _Spec("article", "chat", "solo", False),
    _Spec("contract", "chat", "short", False),
    _Spec("code", "chat", "short", False),
    _Spec("flight", "chat", "solo", False),
    _Spec("company", "clean", "short", False),
    _Spec("gost", "chat", "solo", False),
    _Spec("order", "chat", "short", True),
    _Spec("room", "chat", "solo", False),
    _Spec("quantity", "chat", "short", True),
    _Spec("measure", "chat", "short", False),
    _Spec("fare", "chat", "solo", False),
    _Spec("city", "chat", "short", False),
    _Spec("track", "sloppy", "solo", False),
    _Spec("order", "sloppy", "short", False),
    _Spec("article", "sloppy", "short", False),
    _Spec("contract", "sloppy", "solo", False),
    _Spec("company", "clean", "short", False),
)


# --- build -----------------------------------------------------------------

def _audit_verbatim() -> None:
    """Fail closed on a frozen utterance that stopped being what it claims.

    Mechanical, on the schema's own probes and never on our recognizers — this
    guard has to stay true when detection changes, or the independence rule is
    decoration. What it CANNOT check is whether a person is named in one, and
    that is stated rather than papered over: those 62 were read by the address
    annotator once and by hand here a second time, and every reply carrying a
    person was dropped on the second reading.
    """
    problems: list[str] = []
    for text, key, line, sha, stratum, spans in _TRAPS:
        if any(character.isdigit() for character in text):
            problems.append(f"{key}: a voice_raw utterance carries a digit")
        if any(character in ".,;:!?" for character in text):
            problems.append(f"{key}: sentence punctuation in a voice_raw case")
        if text[:1].isupper():
            problems.append(f"{key}: a voice_raw case opens with a capital")
        if stratum not in ("marker", "random"):
            problems.append(f"{key}: unknown stratum {stratum!r}")
        characters = list(text)
        for value, _family, why in spans:
            if why not in _WHY:
                problems.append(f"{key}: no reason written for {value!r}")
            start, end = _locate(text, value)
            for position in range(start, end):
                characters[position] = " "
        # EVERY numeral, not a run of four. The schema's threshold governs a
        # corpus whose text nobody controls; here the note claim judges the
        # WHOLE utterance, so a price or a duration standing outside a claimed
        # span would be demanded back by the round trip and reported by nothing
        # on the detect axis. «ну короче пятьдесят рублей проезд пятьдесят
        # рублей» was exactly that until the span was widened to cover both.
        left = [word for word in _WORDS.findall("".join(characters).lower())
                if word in _NUMERALS]
        if left:
            problems.append(f"{key}: numeral words outside every claimed span: "
                            f"{left} — the note judges the whole string")
    if problems:
        raise InvalidCase("\n".join(problems))


def _audit_authored() -> None:
    """No number may stand in an authored string that nothing claims.

    The lines, the openers, the agent's turns and the typed tails are ours to
    write, so an unclaimed number in one of them is a corpus defect and not a
    fact about the register. It cost four cases before this guard existed: the
    agent said «подождите пожалуйста одну минуту» and a room line ended «на
    девять утра», so a gateway masking either would have failed a round trip
    while `false_masks` reported nothing.
    """
    problems: list[str] = []
    strings: list[tuple[str, str]] = [
        (name, part)
        for name, kind in _KINDS.items()
        for row in kind.lines
        for part in (row.prefix, row.mid, row.suffix)]
    strings += [("opener", text) for text, _shape_id in _OPENERS]
    strings += [("typed opener", text) for text in _TYPED_OPENERS]
    strings += [("agent", text) for text in _AGENT_TURNS]
    strings += [("tail", text) for text in _TYPED_TAIL.values()]
    strings += [("assistant", "а дом какой"), ("assistant", "угу слушаю вас"),
                ("assistant", "поняла записала"), ("assistant", "принято"),
                ("assistant", "принято, проверяю"),
                ("assistant", "принято, записал")]
    for where, text in strings:
        if any(character.isdigit() for character in text):
            problems.append(f"{where}: authored string {text!r} carries a digit")
        left = [word for word in _WORDS.findall(text.lower())
                if word in _NUMERALS]
        if left:
            problems.append(f"{where}: authored string {text!r} carries {left}, "
                            f"which no span claims")
    if problems:
        raise InvalidCase("\n".join(problems))


def _audit_filler() -> None:
    """Filler that carries anything the ground truth omits is not neutral.

    The whole screen is `schema.unsafe_filler`, and calling it rather than
    restating it is the point. This module used to check a digit and a numeral
    run of one; it had no name check and no street check, and neither did four
    of its neighbours, each in its own way. One screen in one place is what makes
    a name added for one family protect all eleven.
    """
    problems: list[str] = []
    for text, key, _line, _sha in _FILLER:
        reason = unsafe_filler(text)
        if reason:
            problems.append(f"{key}: {reason} — {text!r}")
    if problems:
        raise InvalidCase("\n".join(problems))


def _verify_sources(table: dict[str, _Utterance]) -> None:
    """The frozen tables against the corpus on disk. A shift RAISES.

    A benchmark that keeps scoring after its source moved underneath it is
    worse than one that stops, because the numbers still look like numbers.
    """
    problems: list[str] = []
    rows: list[tuple[str, str, int, str]] = [
        (text, key, line, sha) for text, key, line, sha, _s, _v in _TRAPS]
    rows += [(text, key, line, sha) for text, key, line, sha, _s, _b in _BARE]
    rows += list(_FILLER)
    for text, key, line, sha in rows:
        utterance = table.get(key)
        if utterance is None:
            problems.append(f"{key} is not in RuDevices any more")
        elif utterance.text != text or utterance.sha256 != sha:
            problems.append(f"{key} no longer hashes to {sha[:12]}")
        elif utterance.line != line:
            problems.append(f"{key} moved from line {line} to {utterance.line}")
    if problems:
        raise InvalidCase("\n".join(problems))


def _verify_annotation() -> None:
    """The frozen bare-street spans against the annotation they were read from.

    The trap spans below are OURS — the annotator ruled on addresses, not on
    what else a reply holds — but the eleven `optional` streets are the hand
    label itself, span included, and a frozen copy of somebody else's judgement
    has to be checked against it. This is `corpus_digest`'s lesson at one file's
    scale: a re-labelling that keeps the keys moves the ground truth and leaves
    every name in place, and a pin that hashes only names stays green while the
    truth walks away underneath it.
    """
    if not LABELS.exists():
        raise FileNotFoundError(
            f"{LABELS} is missing. The bare-street spans are a hand annotation "
            f"and this module carries a frozen copy of it; without the original "
            f"there is nothing to check the copy against.")
    rows = {str(row["key"]): row
            for row in json.loads(LABELS.read_text(encoding="utf-8"))}
    problems: list[str] = []
    for _text, key, _line, _sha, stratum, street in _BARE:
        row = rows.get(key)
        if row is None:
            problems.append(f"{key}: gone from the annotation")
            continue
        if row["label"] != "улица без номера":
            problems.append(f"{key}: re-labelled «{row['label']}» — it is no "
                            f"longer the `optional` class this case is built on")
        if street not in [str(span) for span in row.get("spans", [])]:
            problems.append(f"{key}: the annotation no longer carries the span "
                            f"{street!r}")
        expected = "random" if row["filter"] == "number-sample" else "marker"
        if stratum != expected:
            problems.append(f"{key}: stratum {stratum} against the "
                            f"annotation's {expected} — the weight is wrong")
    if problems:
        raise InvalidCase("\n".join(problems))


def _dimensions(case: Case) -> frozenset[tuple[str, str]]:
    """What a case closes, for the trim below."""
    pairs = {("register", case.register), ("context", case.context),
             ("provenance", case.provenance.kind),
             ("selection", case.provenance.selection)}
    pairs |= {("negative", negative.family) for negative in case.negatives}
    pairs |= {("tool", call.name) for call in case.calls}
    pairs |= {("duty", item.duty) for item in case.pii}
    if case.final.answer:
        pairs.add(("axis", "answer"))
    return frozenset(pairs)


def _trim(cases: list[Case], count: int) -> list[Case]:
    """A smaller run that still closes every dimension. Greedy cover, then fill.

    A prefix would answer a different question at every size — v2's ladder was
    exactly that, and only its largest rung closed anything. File order is kept
    so a trimmed run and a full one score in the same vault order.
    """
    if count >= len(cases):
        return cases
    wanted: set[tuple[str, str]] = set()
    for case in cases:
        wanted |= _dimensions(case)
    chosen: list[int] = []
    covered: set[tuple[str, str]] = set()
    remaining = list(range(len(cases)))
    while remaining and covered != wanted and len(chosen) < count:
        best = max(remaining,
                   key=lambda i: (len(_dimensions(cases[i]) - covered), -i))
        if not _dimensions(cases[best]) - covered:
            break
        chosen.append(best)
        covered |= _dimensions(cases[best])
        remaining.remove(best)
    for index in remaining:
        if len(chosen) >= count:
            break
        chosen.append(index)
    if len(chosen) < count:
        raise InvalidCase(f"cannot cut {count} cases out of {len(cases)}")
    return [cases[index] for index in sorted(chosen)]


def build(seed: int, count: int) -> list[Case]:
    """Every case this family contributes, in file order. Deterministic in `seed`.

    The stream is the family's own — `random.Random(f"v3:{FAMILY}:{seed}")` — so
    the output does not move when a module built before this one changes how
    many draws it makes.
    """
    if count > TARGET:
        raise InvalidCase(
            f"{count} cases asked of a family planned at {TARGET}; the material "
            f"is 62 hand-read utterances and it does not stretch. Add cases by "
            f"reading more of the annotation, not by drawing the same four "
            f"templates again.")
    table = _load_utterances()
    _verify_sources(table)
    _verify_annotation()
    _audit_verbatim()
    _audit_authored()
    _audit_filler()
    rng = random.Random(f"v3:{FAMILY}:{seed}")
    cases: list[Case] = [
        _verbatim_case(index, entry, rng)
        for index, entry in enumerate(_TRAPS)]
    cases += [_bare_case(index, entry, rng)
              for index, entry in enumerate(_BARE)]
    seen: dict[str, int] = {}
    for position, spec in enumerate(_PLAN):
        occurrence = seen.get(spec.kind, 0)
        seen[spec.kind] = occurrence + 1
        cases.append(_authored_case(position, occurrence, spec, _FILLER, rng))
    return _trim(cases, count)


def main() -> None:
    cases = build(20260830, TARGET)
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
    print(f"register         {tally(lambda c: c.register)}")
    print(f"context          {tally(lambda c: c.context)}")
    print(f"provenance       {tally(lambda c: c.provenance.kind)}")
    print(f"selection        {tally(lambda c: c.provenance.selection)}")
    speech = sum(1 for c in cases if c.register in ("voice_raw", "voice_itn"))
    real = sum(1 for c in cases
               if c.provenance.kind in ("verbatim", "recombined"))
    print(f"speech share     {speech / total:.1%}")
    print(f"real-form share  {real / total:.1%}")
    negatives: dict[str, int] = {}
    values: dict[str, set[str]] = {}
    for case in cases:
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
            values.setdefault(negative.family, set()).add(
                negative.value.casefold())
    print("negatives        " + ", ".join(
        f"{family} {count} ({len(values[family])} различных)"
        for family, count in sorted(negatives.items())))
    print(f"negative spans   {sum(negatives.values())}")
    optional = sum(1 for c in cases for i in c.pii if i.duty == "optional")
    print(f"optional LOC     {optional}")
    judged: dict[str, int] = {}
    for case in cases:
        for call in case.calls:
            for argument in call.judged_args:
                key = f"{call.name}.{argument}"
                judged[key] = judged.get(key, 0) + 1
    print(f"judged arguments {dict(sorted(judged.items()))}")
    answers = sum(1 for c in cases if c.final.answer)
    print(f"closed answers   {answers}")
    print(f"note refused on  {len(_NOTE_UNSAFE)} утверждений: "
          f"{sorted(_NOTE_UNSAFE)}")
    calls = sum(len(case.calls) for case in cases)
    reachable = sum(1 for case in cases for negative in case.negatives
                    if any(negative.value in call.arguments[argument]
                           for call in case.calls
                           for argument in call.judged_args))
    spans = sum(len(case.negatives) for case in cases)
    print(f"calls            {calls}, судимых аргументов "
          f"{sum(len(c.judged_args) for case in cases for c in case.calls)}")
    print(f"негативов в судимом аргументе {reachable} из {spans} — "
          f"над-маскирование ломает вызов, а не только портит точность")


if __name__ == "__main__":
    main()
