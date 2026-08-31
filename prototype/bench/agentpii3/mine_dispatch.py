"""Mine the reply grammar of a taxi dispatcher out of SOVA RuDevices.

Two tiers, kept apart on purpose:

  gold   — the 156 address values a human labelled in rudevices_addresses.json.
           Every shape count here is verified. This is what a generator may copy.
  mined  — the same shape extractor run over all 41 342 replies with a
           conservative candidate rule. Bigger, noisier, and marked as such:
           it tells you which forms are COMMON, not which strings are addresses.

The two are never summed. The gold layer is itself two strata with different
sampling (see rudevices_addresses.README.md) and those are not summed either.
"""

import json
import re
import collections
from typing import Iterator

CORPUS = "/Users/igor/.cache/pseudex-bench/speech_rudevices.jsonl"
LABELS = "/Users/igor/.cache/pseudex-bench/rudevices_addresses.json"
OUT = "/Users/igor/Projects/Obscura/prototype/bench/agentpii3/mined/dispatch_grammar.json"

# ASR output has no digits and no punctuation: every number is spelled out, and
# the recogniser's own misspellings are part of the register, so they are listed
# rather than normalised away.
UNITS: frozenset[str] = frozenset(
    """ноль нуль один одна одно два две три четыре пять шесть семь восемь девять
    десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать
    семнадцать восемнадцать девятнадцать двадцать тридцать сорок пятьдесят
    шестьдесят семьдесят восемьдесят девяносто сто двести триста четыреста
    пятьсот шестьсот семьсот восемьсот девятьсот тысяча""".split()
)
NUM_TYPOS: frozenset[str] = frozenset(
    """одинадцать одинадцатый девяеносто девяноста девянасто пятдесят шестдесят
    восимь читыре тритцать двацать сомь""".split()
)
CARDINALS: frozenset[str] = UNITS | NUM_TYPOS

ORDINALS: frozenset[str] = frozenset(
    """первый первая первое первого второй вторая второе третий третья третье
    четвёртый четвертый четвёртая пятый пятая шестой шестая седьмой седьмая
    восьмой восьмая восьмое девятый девятая десятый десятая одиннадцатый
    двенадцатый тринадцатый четырнадцатый пятнадцатый пятнадцатая шестнадцатый
    семнадцатый восемнадцатый девятнадцатый двадцатый последний последняя
    угловой угловая крайний крайняя средний средняя дальний ближний
    четвёрьый четверьтый""".split()
)

STREET_TYPES: frozenset[str] = frozenset(
    """улица улице улицу улицы ул шоссе переулок переулке переулка проезд проезде
    проезда проспект проспекте проспекта бульвар бульваре набережная набережной
    набережный площадь площади тупик аллея тракт квартал микрорайон""".split()
)
SETTLEMENT_TYPES: frozenset[str] = frozenset(
    """посёлок поселок посёлке деревня деревне село селе город городе городок
    район районе станция снт кооператив""".split()
)
MARKERS: frozenset[str] = frozenset(
    """подъезд подъезда подъезде корпус корпуса квартира квартиры квартире дом
    дома доме строение строения этаж этажа литер литера вход входа блок
    номер""".split()
)
HOUSE_LETTERS: frozenset[str] = frozenset("абвгдежзик")

GREET: frozenset[str] = frozenset(
    """здравствуйте здравствуй здрасте здрасьте привет алло алё але аллё добрый
    доброе доброго день вечер утро ночи""".split()
)
ADDRESSEE: frozenset[str] = frozenset(
    """девушка девушки молодой человек оператор диспетчер мужчина женщина""".split()
)
FILLER: frozenset[str] = frozenset(
    """а аа ааа э ээ эээ м мм ммм ну вот так значит оо ой эт это как бы да
    пожалуйста скажите извините слушайте""".split()
)
INTENT: frozenset[str] = frozenset(
    """поедем поеду едем еду поехали поедет поедите подъезжайте подъедет подать
    подайте нахожусь находимся находится буду будем стою стоим ждём ждем жду
    забрать заберите приезжайте приедет приехать вызвать надо нужно машину такси
    едим ехать""".split()
)

TOKEN = re.compile(r"[а-яёa-z]+", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def classify(word: str, prev: str) -> str:
    """One token -> one grammar symbol. `prev` only decides the house letter."""
    if word in STREET_TYPES:
        return "TYPE"
    if word in SETTLEMENT_TYPES:
        return "SETTLE"
    if word in MARKERS:
        return "MARK"
    if word in CARDINALS:
        return "NUM"
    if word in ORDINALS:
        return "ORD"
    if len(word) == 1 and word in HOUSE_LETTERS and prev in ("NUM", "LET"):
        return "LET"
    return "NAME"


RENDER: dict[str, str] = {
    "NAME": "<улица>",
    "NUM": "<число прописью>",
    "ORD": "<порядковое>",
    "LET": "<литера>",
}
TYPE_LEMMA: dict[str, str] = {
    "улице": "улица", "улицу": "улица", "улицы": "улица", "ул": "улица",
    "переулке": "переулок", "переулка": "переулок",
    "проезде": "проезд", "проезда": "проезд",
    "проспекте": "проспект", "проспекта": "проспект",
    "бульваре": "бульвар", "набережной": "набережная", "набережный": "набережная",
    "площади": "площадь",
    "подъезда": "подъезд", "подъезде": "подъезд", "корпуса": "корпус",
    "квартиры": "квартира", "квартире": "квартира",
    "дома": "дом", "доме": "дом", "строения": "строение", "этажа": "этаж",
    "литер": "литера", "входа": "вход",
    # «подъезд номер три» — «номер» is a marker word, not a street name

    "поселок": "посёлок", "посёлке": "посёлок", "деревне": "деревня",
    "селе": "село", "городе": "город", "районе": "район",
}


def shape(value: str) -> str:
    """Address value -> pattern string. Runs of one symbol collapse to one slot."""
    words = tokens(value)
    syms: list[str] = []
    out: list[str] = []
    prev = ""
    for w in words:
        s = classify(w, prev)
        syms.append(s)
        prev = s
    for i, (w, s) in enumerate(zip(words, syms)):
        if s in ("TYPE", "SETTLE", "MARK"):
            out.append(TYPE_LEMMA.get(w, w))
            continue
        if i > 0 and syms[i - 1] == s:
            continue  # a run of numerals is ONE number said aloud
        out.append(RENDER[s])
    return " ".join(out)


def role(word: str) -> str:
    if word in GREET:
        return "greet"
    if word in ADDRESSEE:
        return "addressee"
    if word in INTENT:
        return "intent"
    if word in FILLER:
        return "filler"
    return "other"


def reply_shape(text: str, spans: list[str]) -> str:
    """Whole reply -> coarse shape: what surrounds the address values."""
    low = text.lower()
    parts: list[str] = []
    cursor = 0
    for sp in spans:
        idx = low.find(sp.lower(), cursor)
        if idx < 0:
            continue
        parts.append(segment(low[cursor:idx]))
        parts.append("<АДРЕС>")
        cursor = idx + len(sp)
    parts.append(segment(low[cursor:]))
    return " ".join(p for p in parts if p)


def segment(chunk: str) -> str:
    words = tokens(chunk)
    if not words:
        return ""
    roles = [role(w) for w in words]
    seen: list[str] = []
    for r in roles:
        tag = {"greet": "<приветствие>", "addressee": "<обращение>",
               "intent": "<намерение>", "filler": "<филлер>", "other": "<хвост>"}[r]
        if not seen or seen[-1] != tag:
            seen.append(tag)
    return " ".join(seen)


def carried_types(pattern: str) -> list[str]:
    out = ["LOC"]
    if "квартира" in pattern:
        out.append("LOC:квартира")
    if "подъезд" in pattern:
        out.append("LOC:подъезд")
    return out


def load_labels() -> list[dict[str, object]]:
    with open(LABELS, encoding="utf-8") as fh:
        return json.load(fh)


def load_corpus() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    with open(CORPUS, encoding="utf-8") as fh:
        for line in fh:
            t = json.loads(line)["text"]
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def candidates(text: str) -> Iterator[str]:
    """Conservative address candidate: a non-numeral word followed by numerals,
    with a street type or a marker somewhere in the window. Precision is NOT the
    goal — this layer measures which FORMS are frequent, and the gold layer says
    which of them are real."""
    words = tokens(text)
    syms = []
    prev = ""
    for w in words:
        s = classify(w, prev)
        syms.append(s)
        prev = s
    i = 0
    while i < len(words):
        if syms[i] == "NAME" and i + 1 < len(words) and syms[i + 1] == "NUM":
            j = i + 1
            while j < len(words) and syms[j] in ("NUM", "LET", "ORD", "MARK", "TYPE"):
                j += 1
            start = i
            if start > 0 and syms[start - 1] in ("TYPE", "SETTLE"):
                start -= 1
            if any(s in ("TYPE", "MARK") for s in syms[start:j]):
                yield " ".join(words[start:j])
            i = j
        else:
            i += 1
