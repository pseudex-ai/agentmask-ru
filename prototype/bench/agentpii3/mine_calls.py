"""Mine the GRAMMAR of a spoken reply out of the Russian telephone-call corpora.

Not annotation — FORM. What a Russian speaker actually says on the phone when
dictating personal data: which slots a name mention has and in what order, how an
address arrives without the word "улица", how digits are spoken as numeral words,
which fillers and self-corrections sit around the value, and what an ASR mistake
of a numeral looks like.

Two inputs, both already on disk:

  speech_calls.jsonl    OpenSTT asr_calls_2_val, 12 950 replies. CC BY-NC 4.0 —
                        may be MEASURED, may not be REDISTRIBUTED. Only a form,
                        a count and examples no longer than a single reply each
                        ever leave this script.
  voice_addresses.json  the hand annotation over those same replies: 1373 rows,
                        four classes, `spans` for every address value.

Every shape carries verbatim examples on purpose: a pattern with no instance of
itself is a guess about the language, and AgentPII-RU v2 was built out of exactly
those — 80% of its cases were template output where two addresses differed only
by a counter.
"""

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterator

import pymorphy3

CACHE = Path.home() / ".cache" / "pseudex-bench"
CALLS = CACHE / "speech_calls.jsonl"
ANNOTATION = CACHE / "voice_addresses.json"
REPO = Path(__file__).resolve().parent
DATA = REPO.parent.parent / "licensing" / "data"
OUT = REPO / "mined" / "calls_grammar.json"

LICENSE = "OpenSTT asr_calls_2_val · CC BY-NC 4.0 · измерять можно, отгружать нельзя"

TOKEN = re.compile(r"[а-яёa-z]+")

# Words the dictionaries call a name and this corpus never uses as one. A literal
# list rather than a morphological rule because every rule tried here ("not a
# common noun", "best parse is Name") either kept «пол» or dropped «вася» — the
# ambiguity is lexical, and at 199 distinct hits reading them is cheaper than a
# filter that fails silently.
NOT_A_NAME = frozenset(
    """пол ма ра дык мороз кришна путин путина карлсон царевич углич малах одина
    лица ис тее дада дарова вели нан эмм ата ляма""".split()
)

# Roles, not names — but the word directly in front of a surname in this register
# is a rank or a job far more often than any cue word, so the pair is a form.
ROLE_WORDS = frozenset(
    """полковник подполковник генерал майор капитан лейтенант дежурный дежурная
    дежурному сторож сторожу начальник начальнику участковый оперативный доктор
    товарищ мастер мастера помощник комиссар""".split()
)

KINSHIP_WORDS = frozenset("дядя тётя тетя баба дед мамка мама папа брат сестра".split())

NAME_CUES = (
    "меня зовут",
    "как вас зовут",
    "как тебя зовут",
    "вас зовут",
    "его зовут",
    "её зовут",
    "зовут",
    "моя фамилия",
    "ваша фамилия",
    "фамилия имя отчество",
    "имя отчество",
    "как ваша фамилия",
    "какая фамилия",
    "фамилия",
    "представьтесь",
    "вас беспокоит",
    "беспокоит",
    "будьте добры",
    "позовите",
    "позови",
    "пригласите",
    "передайте",
    "спросите",
    "с вами говорит",
    "говорит",
    "это",
    "к",
)

ADDRESS_CUES = (
    "адрес",
    "по адресу",
    "какой адрес",
    "адрес скажи",
    "адрес говорю",
    "продиктовать",
    "записывай",
    "я живу",
    "живу на",
    "находится",
    "приезжай",
    "приезжайте",
    "приходи",
    "подъезжай",
    "подъедешь",
    "прибыть",
)

STREET_TYPES = (
    "улица",
    "улицу",
    "улице",
    "улицы",
    "улицах",
    "площадь",
    "площади",
    "переулок",
    "переулке",
    "бульвар",
    "бульваре",
    "шоссе",
    "проспект",
    "проспекте",
    "слобода",
    "слободе",
    "проезд",
    "набережная",
    "тупик",
)

HOUSE_MARKERS = (
    "дом",
    "дома",
    "доме",
    "квартира",
    "квартиру",
    "квартире",
    "корпус",
    "строение",
    "этаж",
    "подъезд",
    "подъезде",
    "дробь",
    "литер",
)

CITY_WORDS = ("город", "москва", "колпино", "тюмень", "санктпетербург")

# The spoken numeral vocabulary. A run of these words is how a phone number, a
# house number and a room number all reach the listener, because the corpus
# contains no digit at all.
NUMERAL = re.compile(
    r"^(ноль\w*|нул[ья]\w*|один\w*|одна|одну|одно|дв[ае]\w*|двух\w*|тр[ие]\w*|трёх\w*"
    r"|четыр\w*|четвёрт\w*|четверт\w*|пят\w*|пяти\w*|шест\w*|шесть\w*|сем[ьиынё]\w*"
    r"|седьм\w*|восем\w*|восьм\w*|девят\w*|девян\w*|десят\w*|сорок\w*|сот\w*|ст[оа]\w*"
    r"|двест\w*|трист\w*|тысяч\w*|половин\w*|дроб\w*)$"
)

NUMERAL_CANON = (
    "ноль один два три четыре пять шесть семь восемь девять десять одиннадцать "
    "двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать "
    "восемнадцать девятнадцать двадцать тридцать сорок пятьдесят шестьдесят "
    "семьдесят восемьдесят девяносто сто двести триста четыреста пятьсот "
    "шестьсот семьсот восемьсот девятьсот тысяча"
).split()

CUE_CANON = (
    "адрес улица квартира дом телефон паспорт фамилия зовут отчество проспект "
    "переулок бульвар шоссе площадь корпус подъезд этаж строение здравствуйте "
    "пожалуйста"
).split()

INTERJECTION = re.compile(r"^(э+|а{2,}|м{2,}|ы+|и{3,}|о{3,}|н{3,}|в{3,}|с{3,}|ну{2,})$")

# Hypocoristics as speech actually shortens them. The suffix table deliberately
# omits -на / -ма / -ра / -та: those endings belong to Елена, Тамара, Кристина and
# Марина as much as to Лена and Рома, and admitting them turns every second full
# name into a diminutive.
DIMINUTIVE = re.compile(
    r"^[а-яё]{2,}(ш[ауеи]|с[юяеи]|н[яюеи]|л[яюеи]|ик[ауи]?|[ёо]к|к[ауе]"
    r"|очк[аиуе]|ечк[аиуе]|еньк[аиуе])$"
)


def is_short_vocative(token: str, morph: pymorphy3.MorphAnalyzer, given: frozenset[str]) -> bool:
    """«наташ», «жень», «вась», «паш» — the name with its final vowel bitten off.

    Three gates, and each one was earned. The normal form must be this token plus
    exactly one letter (a consonant-final suffix rule alone matches «владимир»,
    «александр», «иван», which shorten nothing). The token must not itself be a
    dictionary name in the nominative, or «александр» comes back through
    «Александра». And the qualifying reading must be a vocative or a genitive
    plural — the only two the analyzer gives a bitten-off name — or «сталин» and
    «хорин» arrive as the genitive plural of an invented «Сталина».
    """
    if token in given:
        return False
    stem = token.rstrip("ь")
    for parse in morph.parse(token):
        if "Name" not in parse.tag or parse.normal_form == token:
            continue
        # The full form has to be a name the dictionary actually knows, or
        # «хорин» and «субботин» arrive as the genitive plural of a «Хорина» and
        # a «Субботина» that pymorphy3 invented to parse a surname.
        if parse.normal_form not in given:
            continue
        if not parse.normal_form.startswith(stem) or len(parse.normal_form) != len(stem) + 1:
            continue
        if parse.tag.case == "voct" or (parse.tag.number == "plur" and parse.tag.case == "gent"):
            return True
    return False


DISCOURSE_PROBES = (
    "алло",
    "алё",
    "аллё",
    "ой",
    "ага",
    "угу",
    "да да",
    "слушаю",
    "подожди",
    "подождите",
    "стоп",
    "то есть",
    "в смысле",
    "а нет",
    "не то",
    "как его",
    "извините",
    "простите",
    "минуточку",
    "ещё раз",
    "повторите",
    "повтори",
    "не слышу",
    "плохо слышно",
    "записывай",
    "записываю",
    "записал",
    "пишите",
    "продиктовать",
    "скажите пожалуйста",
    "будьте добры",
    "пожалуйста",
    "короче",
    "значит",
    "вот",
    "как бы",
    "это самое",
    "смотри",
    "слушай",
    "слышь",
    "понимаешь",
    "знаете",
    "понимаете",
    "дорогой",
    "молодой человек",
    "девушка",
    "мужчина",
    "женщина",
    "товарищ",
)


def read_calls(path: Path) -> list[str]:
    """The OpenSTT replies, one per line, as the human transcriber wrote them."""
    return [
        json.loads(line)["text"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_annotation(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_wordlist(path: Path) -> frozenset[str]:
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )


def words(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def pick_examples(replies: list[str], count: int) -> list[str]:
    """Up to `count` distinct replies spanning the length range of the form.

    Shortest first, and that is not cosmetic: the generator needs the form NAKED.
    In a thirty-word reply the pattern is buried in argument and the reader has to
    guess which three words were the form; in «вольная семнадцать» there is
    nothing to guess. The longer picks exist so the shape is not mistaken for a
    one-liner — half of these forms arrive inside a sentence.
    """
    unique = sorted(set(replies), key=lambda reply: (len(reply), reply))
    if len(unique) <= count:
        return unique
    positions = [0, len(unique) // 2, len(unique) - 1][:count]
    return [unique[position] for position in positions]


def build_shape(identifier: str, pattern: str, replies: list[str], carries: list[str]) -> dict:
    examples = pick_examples(replies, 3)
    return {
        "id": identifier,
        "pattern": pattern,
        "example": examples[0] if examples else "",
        "examples": examples,
        "count": len(replies),
        "carries": carries,
        "source": LICENSE,
    }


def name_kind(
    word: str, morph: pymorphy3.MorphAnalyzer, given: frozenset[str], surnames: frozenset[str]
) -> str:
    """N given, P patronymic, S surname, empty string for everything else.

    Patronymic is decided by morphology alone: pymorphy3 already carries the
    colloquial contractions («палыч», «михалыч», «иваныч») under `Patr,Infr`, and a
    suffix regex would restate that table and still miss «алексаныч».
    """
    if word in NOT_A_NAME:
        return ""
    parses = morph.parse(word)
    if any("Patr" in parse.tag for parse in parses):
        return "P"
    if word in given and any("Name" in parse.tag for parse in parses):
        return "N"
    if word in surnames and any("Surn" in parse.tag for parse in parses):
        return "S"
    # The leased dictionaries are nominative-only, so «лидию», «геннадия» and
    # «букину» miss on the surface form. Reach them through the normal form of
    # every name-tagged reading — never through parse[0], which picks arbitrarily
    # between «марин» (a man) and «марина» (a woman) at the same score.
    #
    # Gated on the surface word having NO ordinary reading at all. Unbounded, this
    # route admits «из» (119 hits — a preposition whose normal form is the name
    # «Иза»), «любой», «герой», «петь», «ай»: in a 28k dictionary the inflected
    # neighbourhood is dense enough that function words land in it.
    if not all(any(tag in parse.tag for tag in ("Name", "Surn", "Patr")) for parse in parses):
        return ""
    if any("Name" in parse.tag and parse.normal_form in given for parse in parses):
        return "N"
    if any("Surn" in parse.tag and parse.normal_form in surnames for parse in parses):
        return "S"
    return ""


def name_spans(
    texts: list[str], morph: pymorphy3.MorphAnalyzer, given: frozenset[str], surnames: frozenset[str]
) -> Iterator[tuple[str, str, str, str, str]]:
    """Maximal runs of name-ish tokens: (shape, span, left context, right, reply)."""
    for text in texts:
        tokens = words(text)
        kinds = [name_kind(token, morph, given, surnames) for token in tokens]
        index = 0
        while index < len(tokens):
            if not kinds[index]:
                index += 1
                continue
            end = index
            while end + 1 < len(tokens) and kinds[end + 1]:
                end += 1
            yield (
                "".join(kinds[index : end + 1]),
                " ".join(tokens[index : end + 1]),
                " ".join(tokens[max(0, index - 4) : index]),
                " ".join(tokens[end + 1 : end + 3]),
                text,
            )
            index = end + 1


def numeral_runs(texts: list[str]) -> Iterator[tuple[int, str, str, str, str]]:
    """Runs of two or more numeral words: (length, run, left, right, reply)."""
    for text in texts:
        tokens = words(text)
        index = 0
        while index < len(tokens):
            if not NUMERAL.match(tokens[index]):
                index += 1
                continue
            end = index
            while end + 1 < len(tokens) and NUMERAL.match(tokens[end + 1]):
                end += 1
            if end > index:
                yield (
                    end - index + 1,
                    " ".join(tokens[index : end + 1]),
                    " ".join(tokens[max(0, index - 3) : index]),
                    " ".join(tokens[end + 1 : end + 3]),
                    text,
                )
            index = end + 1


def edit_distance(left: str, right: str, cap: int) -> int:
    """Levenshtein, abandoned early — only near-misses are interesting here."""
    if abs(len(left) - len(right)) > cap:
        return cap + 1
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i] + [0] * len(right)
        for j, b in enumerate(right, start=1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b))
        previous = current
    return previous[len(right)]


def register_facts(texts: list[str]) -> dict:
    """What a reply looks like BEFORE any personal data is found in it.

    This is the half AgentPII-RU v2 got backwards: it generated literary lines
    with capitals, commas and digits, and this corpus has none of the three.
    """
    total = len(texts)
    lengths = sorted(len(words(text)) for text in texts)
    return {
        "replies": total,
        "words_mean": round(sum(lengths) / total, 2),
        "words_median": lengths[total // 2],
        "words_p90": lengths[int(total * 0.9)],
        "with_digit": sum(1 for text in texts if any(char.isdigit() for char in text)),
        "with_comma": sum(1 for text in texts if "," in text),
        "with_period": sum(1 for text in texts if "." in text),
        "with_any_punctuation": sum(1 for text in texts if re.search(r"[.,;:!?—-]", text)),
        "with_capital": sum(1 for text in texts if re.search(r"[А-ЯЁ]", text)),
        "starts_with_capital": sum(1 for text in texts if text[:1].isupper()),
        "note": (
            "Ноль цифр, ноль запятых, ноль точек на 12 950 реплик. Заглавная буква "
            "встречается 54 раза и почти всегда ВНУТРИ реплики — расшифровщик так "
            "выделил имя собственное, а не начало предложения. Это и есть регистр: "
            "строки «Краснодар, проспект Мира, д. 5, кв. 100» в нём нет ни одной. "
            "Медиана реплики — 5 слов, то есть значение чаще всего произносится "
            "БЕЗ обрамляющего предложения."
        ),
    }


def name_forms(
    spans: list[tuple[str, str, str, str, str]],
    texts: list[str],
    morph: pymorphy3.MorphAnalyzer,
    given: frozenset[str],
) -> tuple[list[dict], dict]:
    """Shapes of a name mention, plus the vocabulary that stands in front of one."""
    readable = {
        "N": "<имя>",
        "S": "<фамилия>",
        "P": "<отчество>",
        "NP": "<имя> <отчество>",
        "NS": "<имя> <фамилия>",
        "SN": "<фамилия> <имя>",
        "SNP": "<фамилия> <имя> <отчество>",
        "NPS": "<имя> <отчество> <фамилия>",
        "NN": "<имя> <имя>",
        "SS": "<фамилия> <фамилия>",
        "PP": "<отчество> <отчество>",
        "NNP": "<фамилия> <имя> <отчество>",
        "NPN": "<имя> <отчество> <имя>",
    }
    by_shape: dict[str, list[str]] = {}
    for shape, _span, _left, _right, reply in spans:
        by_shape.setdefault(shape, []).append(reply)

    shapes = [
        build_shape(f"name.{shape.lower()}", readable.get(shape, shape), replies, ["NAME"])
        for shape, replies in sorted(by_shape.items(), key=lambda item: -len(item[1]))
    ]

    # A cue plus a shape is the form a generator can emit: «меня зовут» alone says
    # nothing about how many slots follow it, and the shape alone says nothing
    # about what licensed it.
    cue_shapes: dict[tuple[str, str], list[str]] = {}
    for shape, _span, left, _right, reply in spans:
        for cue in NAME_CUES:
            if left == cue or left.endswith(" " + cue):
                cue_shapes.setdefault((cue, shape), []).append(reply)
                break
    shapes += [
        build_shape(
            f"name.cue.{cue.replace(' ', '_')}.{shape.lower()}",
            f"{cue} {readable.get(shape, shape)}",
            replies,
            ["NAME"],
        )
        for (cue, shape), replies in sorted(cue_shapes.items(), key=lambda item: -len(item[1]))
        if len(replies) > 1
    ]

    role_replies: list[str] = []
    kin_replies: list[str] = []
    for _shape, _span, left, _right, reply in spans:
        parts = left.split()
        if not parts:
            continue
        if parts[-1] in ROLE_WORDS:
            role_replies.append(reply)
        elif parts[-1] in KINSHIP_WORDS:
            kin_replies.append(reply)
    shapes.append(
        build_shape(
            "name.role_before",
            "<должность или звание> <фамилия> — сторож васильев, полковник заболотный, дежурная новикова",
            role_replies,
            ["NAME"],
        )
    )
    shapes.append(
        build_shape(
            "name.kinship_before",
            "<родство> <имя> — дядя валера, тётя варя",
            kin_replies,
            ["NAME"],
        )
    )

    # The value said twice in one reply, not adjacent — the listener did not get
    # it the first time and the speaker rephrased around it.
    echo_replies: list[str] = []
    for _shape, span, _left, _right, reply in spans:
        head = span.split()[0]
        tokens = words(reply)
        positions = [index for index, token in enumerate(tokens) if token == head]
        if len(positions) > 1 and positions[-1] - positions[0] > 1:
            echo_replies.append(reply)
    shapes.append(
        build_shape(
            "name.echo",
            "значение названо дважды в одной реплике, с переспросом между: «кукушкин фамилия кукушкин»",
            echo_replies,
            ["NAME"],
        )
    )

    left_word: Counter[str] = Counter()
    for _shape, _span, left, _right, _reply in spans:
        parts = left.split()
        if parts:
            left_word[parts[-1]] += 1

    cues = Counter()
    for cue in NAME_CUES:
        pattern = re.compile(r"(?<![а-яё])" + re.escape(cue) + r"(?![а-яё])")
        cues[cue] = sum(1 for text in texts if pattern.search(text))

    oblique = 0
    oblique_examples: list[str] = []
    contracted: Counter[str] = Counter()
    diminutives: Counter[str] = Counter()
    for _shape, span, _left, _right, _reply in spans:
        head = span.split()[0]
        parses = [
            parse
            for parse in morph.parse(head)
            if any(tag in parse.tag for tag in ("Name", "Surn", "Patr"))
        ]
        cases = {str(parse.tag.case) for parse in parses if parse.tag.case}
        if cases and "nomn" not in cases:
            oblique += 1
            if span not in oblique_examples and len(oblique_examples) < 16:
                oblique_examples.append(span)
        for token in span.split():
            if any("Patr" in parse.tag and "Infr" in parse.tag for parse in morph.parse(token)):
                contracted[token] += 1
                continue
            named = any("Name" in parse.tag for parse in morph.parse(token))
            if (named and DIMINUTIVE.match(token)) or is_short_vocative(token, morph, given):
                diminutives[token] += 1

    lexicon = {
        "left_of_name": dict(left_word.most_common(40)),
        "role_before_surname": dict(
            Counter({w: c for w, c in left_word.items() if w in ROLE_WORDS}).most_common()
        ),
        "kinship_before_name": dict(
            Counter({w: c for w, c in left_word.items() if w in KINSHIP_WORDS}).most_common()
        ),
        "cue_phrases": {cue: count for cue, count in cues.most_common() if count},
        "contracted_patronymics": dict(contracted.most_common()),
        "diminutives": dict(diminutives.most_common()),
        "diminutives_note": (
            "Здесь только те уменьшительные, которые морфология всё же метит "
            "именем: наташ, жень, вась, ленка, славик, фарик, янчик, серёжа, "
            "рома, валера. Формы «ирочку», «ирочка», «витёк» в корпусе есть "
            "(«алло а будьте добры Ирочку», «слушай витёк»), но НИ словарь имён, "
            "ни pymorphy3 их именем не считают — то есть в генератор их надо "
            "класть руками, иначе целый способ назвать человека в бенчмарк не "
            "попадёт."
        ),
        "oblique_mentions": oblique,
        "oblique_examples": oblique_examples,
        "total_mentions": len(spans),
        "note": (
            "Отчество в речи стягивается: палыч, михалыч, иваныч, николаич, "
            "алексаныч, викторыч, дмитрич, степаныч, фёдорыч, сергеич. Полная "
            "форма тоже звучит, но стянутой в шаблонной генерации нет вовсе. "
            "Обращение и адресат идут в косвенном падеже — «будьте добры ирочку», "
            "«к букину прибыть», «нину васильевну», «зинаиде николаевне», — и "
            "словарь имён в именительном такое не видит. Порядок слотов не "
            "фиксирован: и <имя> <отчество>, и <фамилия> <имя> <отчество>, и "
            "<имя> <отчество> <фамилия> встречаются в одном корпусе."
        ),
    }
    return shapes, lexicon


def address_forms(
    annotation: list[dict], texts: list[str], morph: pymorphy3.MorphAnalyzer
) -> tuple[list[dict], dict]:
    """Address shapes, taken from the hand annotation because it carries spans."""
    values: list[tuple[str, str]] = []
    for row in annotation:
        if row["label"] == "адрес с номером":
            for span in row["spans"]:
                values.append((span, row["text"]))

    type_word = re.compile(r"(?<![а-яё])(" + "|".join(STREET_TYPES) + r")(?![а-яё])")
    marker_word = re.compile(r"(?<![а-яё])(" + "|".join(HOUSE_MARKERS) + r")(?![а-яё])")
    city_word = re.compile(r"(?<![а-яё])(" + "|".join(CITY_WORDS) + r")(?![а-яё])")

    buckets: dict[str, list[tuple[str, str]]] = {
        "bare": [],
        "type_first": [],
        "type_after": [],
        "marker": [],
        "letter": [],
        "city": [],
        "whole_reply": [],
        "fraction": [],
        "flat": [],
        "naked": [],
    }
    for span, reply in values:
        tokens = span.split()
        positions = [index for index, token in enumerate(tokens) if type_word.fullmatch(token)]
        if not positions:
            buckets["bare"].append((span, reply))
        elif positions[0] == 0:
            buckets["type_first"].append((span, reply))
        else:
            buckets["type_after"].append((span, reply))
        if marker_word.search(span):
            buckets["marker"].append((span, reply))
        if not positions and not marker_word.search(span):
            buckets["naked"].append((span, reply))
        # A lone Cyrillic letter after the house number is the корпус literal:
        # «двадцать пять а», «семнадцать в». One token, one letter, nothing else.
        if any(len(token) == 1 and token.isalpha() for token in tokens):
            buckets["letter"].append((span, reply))
        if city_word.search(span.lower()):
            buckets["city"].append((span, reply))
        if span.strip() == reply.strip():
            buckets["whole_reply"].append((span, reply))
        if "дробь" in tokens:
            buckets["fraction"].append((span, reply))
        if any(token.startswith("квартир") for token in tokens):
            buckets["flat"].append((span, reply))

    def shape(identifier: str, pattern: str, key: str, carries: list[str]) -> dict:
        rows = buckets[key]
        built = build_shape(identifier, pattern, [reply for _span, reply in rows], carries)
        built["example_values"] = pick_examples([span for span, _reply in rows], 3)
        return built

    shapes = [
        shape("addr.naked", "<улица> <число прописью> — ни слова-типа улицы, ни слова «дом»", "naked", ["ADDRESS"]),
        shape("addr.bare", "<улица> ... <число> — без слова-типа улицы (маркер дома может быть)", "bare", ["ADDRESS"]),
        shape("addr.type_first", "<тип улицы> <улица> <число прописью>", "type_first", ["ADDRESS"]),
        shape("addr.type_after", "<улица> <тип улицы> <число прописью>", "type_after", ["ADDRESS"]),
        shape("addr.marker", "<улица> дом <число> [корпус|строение|этаж <число>]", "marker", ["ADDRESS"]),
        shape("addr.flat", "<улица> <число> квартира <число>", "flat", ["ADDRESS"]),
        shape("addr.house_letter", "<улица> <число прописью> <одна буква>", "letter", ["ADDRESS"]),
        shape("addr.fraction", "<улица> <число> дробь <число>", "fraction", ["ADDRESS"]),
        shape("addr.with_city", "<город> <тип улицы> <улица> <число>", "city", ["ADDRESS", "LOC"]),
        shape(
            "addr.whole_reply",
            "вся реплика — только адрес, ни одного другого слова",
            "whole_reply",
            ["ADDRESS"],
        ),
    ]

    street_only = [row["text"] for row in annotation if row["label"] == "улица без номера"]
    ambiguous = [row["text"] for row in annotation if row["label"] == "неоднозначно"]
    negatives = [row["text"] for row in annotation if row["label"] == "не адрес"]
    shapes.append(
        build_shape(
            "addr.street_no_number",
            "улица <название> без номера дома — НЕ персональные данные, маскировать нечего",
            street_only,
            [],
        )
    )
    shapes.append(
        build_shape(
            "addr.number_only",
            "дом <число> / квартира <число> без улицы — сам по себе никого не определяет",
            ambiguous,
            [],
        )
    )
    corrupt: list[tuple[str, str]] = []
    for span, reply in values:
        for token in span.split():
            if len(token) < 3 or token in NUMERAL_CANON or token in STREET_TYPES:
                continue
            if token in HOUSE_MARKERS or token in CITY_WORDS:
                continue
            if not morph.word_is_known(token) and not NUMERAL.match(token):
                corrupt.append((span, reply))
                break
            if token in ("триц", "тридц", "восем", "лермонтого"):
                corrupt.append((span, reply))
                break
    shapes.append(
        build_shape(
            "addr.corrupted_value",
            "ошибка расшифровки ВНУТРИ значения: «лермонтова триц восемь», «лермонтого тридцать восемь»",
            [reply for _span, reply in corrupt],
            ["ADDRESS"],
        )
    )
    shapes[-1]["example_values"] = pick_examples([span for span, _reply in corrupt], 3)

    shapes.append(
        build_shape(
            "addr.negative_room",
            "<порядковое> кабинет / отделение — число рядом с местом, которое адресом НЕ является",
            [text for text in negatives if "кабинет" in text or "отделени" in text],
            [],
        )
    )

    cues = Counter()
    for cue in ADDRESS_CUES:
        pattern = re.compile(r"(?<![а-яё])" + re.escape(cue) + r"(?![а-яё])")
        cues[cue] = sum(1 for text in texts if pattern.search(text))

    left_word: Counter[str] = Counter()
    right_word: Counter[str] = Counter()
    no_context = 0
    for span, reply in values:
        start = reply.find(span)
        left = reply[:start].split()
        right = reply[start + len(span) :].split()
        if left:
            left_word[left[-1]] += 1
        if right:
            right_word[right[0]] += 1
        if not left and not right:
            no_context += 1

    morphology: Counter[str] = Counter()
    for span, _reply in values:
        tokens = span.split()
        head = tokens[0]
        if head in STREET_TYPES or head in CITY_WORDS or head in HOUSE_MARKERS:
            head = tokens[1] if len(tokens) > 1 else head
        if head.endswith(("ая", "ую", "ой", "ом", "ая")):
            morphology["прилагательное: вольная, кирочная, мончегорская, рублёвском"] += 1
        elif head.endswith(("а", "о", "ы", "и", "ев", "ин", "ого")):
            morphology["фамилия/существительное в родительном: лермонтова, комиссарова, петровки"] += 1
        else:
            morphology["прочее"] += 1

    lexicon = {
        "values": len(values),
        "replies_with_address": sum(1 for row in annotation if row["label"] == "адрес с номером"),
        "naked_values": len(buckets["naked"]),
        "values_with_dom": sum(1 for span, _reply in values if "дом" in span.split()),
        "no_surrounding_context": no_context,
        "cue_phrases": {cue: count for cue, count in cues.most_common() if count},
        "left_of_address": dict(left_word.most_common()),
        "right_of_address": dict(right_word.most_common()),
        "street_head_morphology": dict(morphology),
        "type_words_seen": sorted(
            {token for span, _ in values for token in span.split() if token in STREET_TYPES}
        ),
        "markers_seen": sorted(
            {token for span, _ in values for token in span.split() if token in HOUSE_MARKERS}
        ),
        "note": (
            "Главный факт — в поле naked_values: столько адресных значений не "
            "содержат НИ слова-типа улицы, НИ маркера дома. «вольная семнадцать», "
            "«комиссарова пятьдесят три», «ленина два» — название и число, больше "
            "ничего. Слово «дом» звучит в values_with_dom значениях из values. "
            "И no_surrounding_context реплик состоят ровно из адреса, без единого "
            "другого слова. Падеж согласован «как слышится», а не как в бланке: "
            "«на литейном четыре», «на октябрьскую сто двадцать пять», "
            "«петрозаводской улицу восемнадцать». Улица называется двумя "
            "способами и только двумя: прилагательным (вольная, кирочная, "
            "мончегорская) или фамилией в родительном (лермонтова, комиссарова, "
            "петровки, челюскинцев)."
        ),
    }
    return shapes, lexicon


def number_forms(texts: list[str]) -> tuple[list[dict], dict]:
    runs = list(numeral_runs(texts))
    by_length: Counter[int] = Counter(length for length, _, _, _, _ in runs)

    phone_cue = re.compile(r"(?<![а-яё])(телефон\w*|номер\w*)(?![а-яё])")
    with_phone_cue = [run for run in runs if phone_cue.search(run[2] + " " + run[3])]
    long_runs = [run for run in runs if run[0] >= 4]
    room = [run for run in runs if "кабинет" in run[2] or "кабинет" in run[3]]
    clock = [run for run in runs if run[1].endswith("ноль ноль")]
    pairs = [run for run in runs if run[0] == 2]

    shapes = [
        build_shape(
            "num.phone_by_pairs",
            "телефон — пробегом числительных парами: «сорок один ноль девять шестьдесят семь», без «плюс семь»",
            [run[4] for run in with_phone_cue if run[0] >= 4],
            ["PHONE"],
        ),
        build_shape(
            "num.long_run",
            "непрерывный пробег числительных длиной 4-8 слов, без единой цифры",
            [run[4] for run in long_runs],
            ["PHONE", "ADDRESS"],
        ),
        build_shape(
            "num.pair",
            "<число> <число> — самая частая длина пробега; дом, квартира, кабинет, дата",
            [run[4] for run in pairs],
            ["ADDRESS", "DATE"],
        ),
        build_shape(
            "num.room",
            "<порядковое числительное> кабинет — число, которое персональными данными не является",
            [run[4] for run in room],
            [],
        ),
        build_shape(
            "num.clock",
            "в <число> ноль ноль — время; ноли проговариваются словом",
            [run[4] for run in clock],
            [],
        ),
        build_shape(
            "num.zero_spoken",
            "ноль внутри номера произносится словом и часто удваивается: «ноль ноль»",
            [run[4] for run in runs if " ноль " in " " + run[1] + " "],
            ["PHONE"],
        ),
    ]

    counts: Counter[str] = Counter()
    for text in texts:
        for token in words(text):
            if NUMERAL.match(token):
                counts[token] += 1

    lexicon = {
        "run_length_histogram": {str(length): count for length, count in sorted(by_length.items())},
        "runs_total": len(runs),
        "runs_with_phone_cue": len(with_phone_cue),
        "numeral_tokens_total": sum(counts.values()),
        "top_numeral_tokens": dict(counts.most_common(50)),
        "note": (
            "В корпусе НЕТ ни одной цифры: любое число — числительное прописью. "
            "Телефон произносится группами по две цифры («сорок один ноль девять "
            "шестьдесят семь» = 41-09-67), ноль проговаривается словом, «плюс "
            "семь» не звучит ни разу. Порядковое («триста четырнадцатый») — это "
            "почти всегда кабинет или отделение, то есть НЕ персональные данные; "
            "количественное («тридцать восемь») после названия улицы — дом."
        ),
    }
    return shapes, lexicon


def asr_errors(texts: list[str], morph: pymorphy3.MorphAnalyzer) -> tuple[list[dict], dict]:
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(words(text))

    near_miss: dict[str, dict[str, int]] = {}
    for canonical in NUMERAL_CANON + CUE_CANON:
        # Edit distance alone makes «хуль» a variant of «ноль» and «дядь» a variant
        # of «пять». A decoder error keeps the START of the word — it drops the
        # middle or stops early — so the variant must share the first two letters,
        # or share the first and be shorter than what it corrupts.
        variants = {
            token: count
            for token, count in counts.items()
            if token != canonical
            and len(token) >= 4
            and not morph.word_is_known(token)
            and edit_distance(token, canonical, 2) <= 2
            and (
                token[:2] == canonical[:2]
                or (token[0] == canonical[0] and len(token) < len(canonical))
            )
        }
        if variants:
            near_miss[canonical] = dict(sorted(variants.items(), key=lambda pair: -pair[1])[:8])

    contracted = Counter(
        {
            token: count
            for token, count in counts.items()
            if re.fullmatch(r"(ше|пе|пя|во|се|де|шей|пей)\w*сят\w*", token)
            and not morph.word_is_known(token)
        }
    )
    canonical_desyat = sum(
        counts[token] for token in ("пятьдесят", "шестьдесят", "семьдесят", "восемьдесят")
    )

    truncated = Counter(
        {
            token: counts[token]
            for token in ("триц", "тридц", "трис", "девяно", "семест", "восемест", "восемьст")
            if counts[token]
        }
    )

    dropped = Counter(
        {
            token: counts[token]
            for token in ("восем", "восемсь", "здраствуйте", "тристо", "трииста", "шессот", "лермонтого", "пеесят")
            if counts[token]
        }
    )

    stretched: Counter[str] = Counter()
    for token, count in counts.items():
        if not re.search(r"(.)\1", token):
            continue
        collapsed = re.sub(r"(.)\1+", r"\1", token)
        if collapsed != token and morph.word_is_known(collapsed) and not morph.word_is_known(token):
            stretched[token] = count

    glued: Counter[str] = Counter()
    for token, count in counts.items():
        for particle in ("то", "ка", "нибудь", "либо"):
            if (
                token.endswith(particle)
                and len(token) > len(particle) + 2
                and morph.word_is_known(token[: -len(particle)])
                and not morph.word_is_known(token)
            ):
                glued[token] = count
                break

    interjections = Counter(
        {token: count for token, count in counts.items() if INTERJECTION.fullmatch(token)}
    )

    def replies_with(tokens: list[str]) -> list[str]:
        if not tokens:
            return []
        pattern = re.compile(
            r"(?<![а-яё])(" + "|".join(re.escape(token) for token in tokens) + r")(?![а-яё])"
        )
        return [text for text in texts if pattern.search(text.lower())]

    shapes = [
        build_shape(
            "err.desyat_contraction",
            "пятьдесят → песят / пеесят / пяесят, шестьдесят → шеесят / шейсят / шесят",
            replies_with(list(contracted)),
            ["PHONE", "ADDRESS"],
        ),
        build_shape(
            "err.truncated_numeral",
            "числительное обрезано на середине: триц, тридц, трис, девяно, семест",
            replies_with(list(truncated)),
            ["ADDRESS", "PHONE"],
        ),
        build_shape(
            "err.dropped_letter",
            "буква потеряна: восем, тристо, здраствуйте, лермонтого (в фамилии улицы)",
            replies_with(list(dropped)),
            ["ADDRESS", "NAME"],
        ),
        build_shape(
            "err.stretched_vowel",
            "гласная тянется: чтоо, даа, таак, воот, неет, зовуут, телефоон, четыыре",
            replies_with([token for token, _ in stretched.most_common(30)]),
            [],
        ),
        build_shape(
            "err.glued_particle",
            "частица приклеена: какойто, фамилиято, адресто, звонитето, прибытьто",
            replies_with([token for token, _ in glued.most_common(30)]),
            [],
        ),
        build_shape(
            "err.misheard_name",
            "фамилию не расслышали и вслух перебирают варианты: «букину или пукину или как»",
            [
                text
                for text in texts
                if ("фамили" in text or "зовут" in text)
                and ("не могу понять" in text or "или как" in text or "не расслышал" in text)
            ],
            ["NAME"],
        ),
    ]

    lexicon = {
        "near_misses_by_canonical": near_miss,
        "desyat_contractions": dict(contracted.most_common()),
        "desyat_canonical_total": canonical_desyat,
        "desyat_contracted_share": round(
            sum(contracted.values()) / (sum(contracted.values()) + canonical_desyat), 3
        ),
        "truncated_numerals": dict(truncated.most_common()),
        "dropped_letter": dict(dropped.most_common()),
        "stretched": dict(stretched.most_common(60)),
        "glued_particle": dict(glued.most_common(40)),
        "interjections": dict(interjections.most_common()),
        "note": (
            "Ошибка в речевом корпусе — не опечатка клавиатуры, а ошибка ДЕКОДЕРА "
            "и оговорка говорящего, и она системна. Длинное числительное теряет "
            "середину (пятьдесят → песят), гласная тянется (чтоо, таак), слово "
            "обрывается там, где говорящего перебили (триц, девяно), частица "
            "прирастает к слову (какойто). Каждая пятая форма на -десят приходит "
            "стянутой — это не редкость, это норма регистра."
        ),
    }
    return shapes, lexicon


def discourse(texts: list[str]) -> tuple[list[dict], dict]:
    probes: Counter[str] = Counter()
    matched: dict[str, list[str]] = {}
    for probe in DISCOURSE_PROBES:
        pattern = re.compile(r"(?<![а-яё])" + re.escape(probe) + r"(?![а-яё])")
        hits = [text for text in texts if pattern.search(text)]
        probes[probe] = len(hits)
        matched[probe] = hits

    openers: Counter[str] = Counter()
    repeats: Counter[str] = Counter()
    repeat_replies: list[str] = []
    filler_first: list[str] = []
    for text in texts:
        tokens = words(text)
        if not tokens:
            continue
        openers[tokens[0]] += 1
        if INTERJECTION.fullmatch(tokens[0]):
            filler_first.append(text)
        for index in range(len(tokens) - 1):
            if tokens[index] == tokens[index + 1] and len(tokens[index]) > 1:
                repeats[tokens[index]] += 1
                repeat_replies.append(text)

    shapes = [
        build_shape(
            "disc.filler_prefix",
            "реплика открывается заминкой: эээ / ааа / нуу / иии, дальше значение",
            filler_first,
            [],
        ),
        build_shape(
            "disc.word_repeat",
            "слово повторено подряд: «да да», «ноль ноль», «алло алло», «стоп стоп»",
            repeat_replies,
            [],
        ),
        build_shape(
            "disc.re_ask",
            "переспрос: «ещё раз», «повторите», «не слышу» — и значение звучит второй раз",
            matched["ещё раз"] + matched["повторите"] + matched["не слышу"] + matched["плохо слышно"],
            ["NAME", "ADDRESS", "PHONE"],
        ),
        build_shape(
            "disc.self_correction",
            "самоисправление: «то есть», «в смысле», «подожди», «стоп» — значение переигрывается",
            matched["то есть"]
            + matched["в смысле"]
            + matched["подожди"]
            + matched["подождите"]
            + matched["стоп"]
            + matched["а нет"]
            + matched["не то"],
            ["NAME", "ADDRESS"],
        ),
        build_shape(
            "disc.dictation",
            "диктовка вслух: «записывай», «записал», «пишите» — значение стоит рядом",
            matched["записывай"] + matched["записываю"] + matched["записал"] + matched["пишите"],
            ["ADDRESS", "PHONE", "NAME"],
        ),
        build_shape(
            "disc.greeting",
            "открытие звонка: алло / алё / аллё, дальше сразу представление",
            matched["алло"] + matched["алё"] + matched["аллё"],
            [],
        ),
        build_shape(
            "disc.vocative",
            "обращение вместо имени: молодой человек, девушка, мужчина, женщина, товарищ",
            matched["молодой человек"] + matched["девушка"] + matched["мужчина"] + matched["женщина"] + matched["товарищ"],
            [],
        ),
        build_shape(
            "disc.attention",
            "оклик перед значением: слушай, слышь, смотри, значит, короче",
            matched["слушай"] + matched["слышь"] + matched["смотри"] + matched["значит"] + matched["короче"],
            [],
        ),
    ]

    lexicon = {
        "openers": dict(openers.most_common(45)),
        "markers": {probe: count for probe, count in probes.most_common() if count},
        "immediate_repeats": dict(repeats.most_common(35)),
        "vocatives": {
            probe: probes[probe]
            for probe in (
                "молодой человек",
                "девушка",
                "мужчина",
                "женщина",
                "товарищ",
                "дорогой",
                "слушай",
                "слышь",
            )
        },
        "note": (
            "Реплика почти никогда не начинается со значения: перед ним стоит «ну», "
            "«а», «вот», «так», «значит» или заминка. Повтор слова подряд — 703 "
            "случая, и «ноль ноль» внутри номера от «да да» ничем не отличается "
            "по форме."
        ),
    }
    return shapes, lexicon


def main() -> None:
    morph = pymorphy3.MorphAnalyzer()
    texts = read_calls(CALLS)
    annotation = read_annotation(ANNOTATION)
    given = read_wordlist(DATA / "first_names.txt")
    surnames = read_wordlist(DATA / "surnames.txt")

    spans = list(name_spans(texts, morph, given, surnames))

    name_shapes, name_lexicon = name_forms(spans, texts, morph, given)
    addr_shapes, addr_lexicon = address_forms(annotation, texts, morph)
    num_shapes, num_lexicon = number_forms(texts)
    err_shapes, err_lexicon = asr_errors(texts, morph)
    disc_shapes, disc_lexicon = discourse(texts)

    shapes = name_shapes + addr_shapes + num_shapes + err_shapes + disc_shapes

    document = {
        "meta": {
            "generated": date.today().isoformat(),
            "script": "bench/agentpii3/mine_calls.py",
            "purpose": (
                "Грамматика телефонной реплики: ФОРМА, а не разметка. Вход для "
                "генератора AgentPII-RU v3, где настоящая речь — основа корпуса, "
                "а не меньшинство."
            ),
            "sources": [
                {
                    "file": "speech_calls.jsonl",
                    "corpus": "OpenSTT asr_calls_2_val",
                    "license": "CC BY-NC 4.0",
                    "redistributable": False,
                    "replies": len(texts),
                },
                {
                    "file": "voice_addresses.json",
                    "corpus": "ручная разметка адресов поверх тех же реплик",
                    "license": "CC BY-NC 4.0 (производная от OpenSTT)",
                    "redistributable": False,
                    "rows": len(annotation),
                },
            ],
            "redistribution_rule": (
                "В файл кладётся форма, частота и не более трёх примеров, каждый "
                "длиной ровно в одну реплику. Корпус отсюда не восстанавливается: "
                "примеров тут порядка сотни на 12 950 реплик."
            ),
        },
        "register": register_facts(texts),
        "shapes": shapes,
        "lexicon": {
            "name": name_lexicon,
            "address": addr_lexicon,
            "number": num_lexicon,
            "asr_error": err_lexicon,
            "discourse": disc_lexicon,
        },
        "stats": {
            "replies": len(texts),
            "annotated_rows": len(annotation),
            "name_mentions": len(spans),
            "address_values": addr_lexicon["values"],
            "numeral_runs": num_lexicon["runs_total"],
            "shapes": len(shapes),
            "examples_emitted": sum(len(shape["examples"]) for shape in shapes),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} — {len(shapes)} shapes, {len(spans)} name mentions")


if __name__ == "__main__":
    main()
