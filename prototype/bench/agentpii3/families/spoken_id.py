"""AgentPII-RU v3 — семейство `spoken_id`: идентификатор, продиктованный вслух.

ЭТО ИЗМЕРЕННЫЙ ДЕФЕКТ, А НЕ ГИПОТЕЗА. В корпусе v2 лежало 133 телефона,
произнесённых словами; движок нашёл ИЗ НИХ НОЛЬ. Карта, СНИЛС, ИНН и паспорт —
по девять словесных каждый, найдено столько же. Причина не в пороге и не в
словаре: libphonenumber разбирает цифры, а контрольные суммы (mod 101, веса ИНН,
Луна) считаются по цифрам, и в реплике «восемь девятьсот шестнадцать шестьсот
сорок два восемьдесят пять пятьдесят» цифр нет ни одной. Целый класс
идентификаторов невидим для каждого распознавателя, который у нас есть.

Ни один письменный корпус этого показать не может: в тексте цифра — это цифра.
Поэтому семейство существует отдельно, а не как «ещё один регистр» внутри
`transfer`: там словесное значение было бы одной ячейкой плана, и при любой
пересборке оно первым выпало бы в пользу более представительной формы.

ЧТО ЗДЕСЬ ИЗМЕРЯЕТСЯ, по трём осям и только по ним:

  1. ДЕТЕКЦИЯ. Нашли ли пробег числительных как идентификатор, нашли ли ЦЕЛИКОМ
     (полнота и покрытие печатаются врозь — «восемь девятьсот шестнадцать»,
     найденное без хвоста, это и полнота, и семь утёкших цифр), и не съели ли
     соседний пробег, который персональными данными не является.
  2. КРУГ. Дошло ли значение до аргумента инструмента В ЦИФРАХ. Это контракт, а
     не придирка: CRM, биллинг и банковский шлюз не принимают «сорок один ноль
     девять», и шлюз, который вернул словесную форму, вызов не выполнил.
  3. ОТВЕТ. Не прочитал ли агент номер документа обратно пользователю цифрами
     там, где системная инструкция это прямо запрещает.

ГРАНИЦЫ С СОСЕДНИМИ СЕМЕЙСТВАМИ, проведённые намеренно:

  * `wordnum` берёт СЛОВЕСНЫЙ НОМЕР ДОМА в адресе. Здесь адресов нет вовсе —
     иначе два семейства мерили бы один и тот же дефект подмены места, и ни одно
     не отвечало бы за него.
  * `repair` берёт САМОИСПРАВЛЕНИЕ («восемь девятьсот пятнадцать а нет
     шестнадцать»). Здесь его нет, и это отказ по существу: у исправленного
     пробега эталон неоднозначен — где кончается ошибочная часть, решает
     слушатель, а бенчмарк не имеет права требовать того, чего в реплике не
     было. ПЕРЕСПРОС здесь есть (значение названо дважды ЦЕЛИКОМ, 165 таких
     реплик в корпусе звонков): две полные формы неоднозначности не создают, и
     это ровно тот случай, где связывание проверяемо.
  * `negative` берёт реплики, где маскировать нечего вообще. Здесь негатив
     всегда СТОИТ РЯДОМ с настоящим идентификатором и часто продиктован тем же
     способом — «заказ четыре восемь два семь» в одном предложении с картой.
     Это и есть трудный случай: замаскированный номер заказа не утекает, он
     ЛОМАЕТ вызов, и увидеть это можно только когда оба пробега в одной реплике.

ПОЧЕМУ ЭТАЛОН — ЦИФРЫ, И ПОЧЕМУ ЭТО НЕ НАРУШАЕТ ПРАВИЛО «ЭТАЛОН ЕСТЬ ФОРМА ТОГО,
ЧТО СКАЗАНО». Правило запрещает требовать обратно ИНФОРМАЦИЮ, которой в реплике
не было: реплика без отчества не должна требовать отчества. Здесь информация вся
на месте — «восемь девятьсот шестнадцать» несёт ровно цифры 8916 и ничего
больше, и переход к ним детерминирован. Чтобы это была проверяемая правда, а не
обещание, модуль держит собственный жадный разбор числительных слева направо и
ПРОВЕРЯЕТ КАЖДОЕ значение перед тем, как положить его в корпус: если словесная
форма не разбирается обратно в те же цифры, сборка падает. Разбор — не фильтр
отбора: ни один случай он не выбрасывает, он только запрещает класть в эталон
то, чего из сказанного не следует.

ЧТО СДЕЛАНО, ЧТОБЫ НАБОР НЕ ДЕЛИЛ СИГНАЛЫ С ДЕТЕКТОРОМ. Формы взяты из
`mined/calls_grammar.json` — из грамматики, добытой на 12 950 живых репликах, а
не из представления автора о том, как диктуют. Оттуда же взяты и пропорции:
гистограмма длин пробега (2→453, 3→132, 4→33, 5→29, 6→14, 7→5, 8→1), доля
стянутых «-десят» форм (22.9%), обрезанные числительные, удвоенный «ноль».
Ничего из этого не выбиралось по тому, находит движок такую форму или нет —
сегодня он не находит ни одной, так что выбирать было бы не из чего, и это самая
честная гарантия независимости, какая у семейства может быть.

ЧТО СЮДА НАМЕРЕННО НЕ ПОЛОЖЕНО:

  * КЛАВИАТУРНАЯ ОПЕЧАТКА ВНУТРИ ЧИСЛИТЕЛЬНОГО. В регистре `sloppy` шум идёт по
     словам-подсказкам («пасспорт», «тилефона», «фамилиа») и по обрамлению, а
     пробег остаётся целым. Причина не в осторожности: испорченное клавиатурой
     числительное делает эталон невыводимым из написанного, и требовать цифру
     обратно значило бы требовать исправления орфографии. Заодно это самый
     ценный зонд регистра — CLAUDE.md уже знает, что «пасспорт» и «догвор»
     выключают охрану, которую даёт слово-подсказка.
  * УДВОЕНИЕ «НОЛЬ» ТАМ, ГДЕ НОЛЬ ОДИН. «ноль ноль» в корпусе звучит 69 раз, но
     кладётся сюда только когда в цифрах действительно два нуля. Удвоение как
     оговорка сделало бы эталон неоднозначным, а неоднозначному в корпусе места
     нет — ручная разметка выбросила пятнадцать реплик ровно по этой причине.
  * ЛИТЕРАТУРНЫЙ РЕГИСТР СВЕРХ ШЕСТИ СЛУЧАЕВ. Их 6 из 190 (3.2%), они несут
     только типы, которых речевые корпуса не содержат, и помечены `template`.
     Они существуют, чтобы показать, что на письменной расшифровке мы не
     сломались, — и ни для чего больше.
"""

import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):            # `python3 families/spoken_id.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii3.schema import (  # noqa: E402
    Case,
    ExpectedCall,
    FinalAnswer,
    LinkExpectation,
    Message,
    Negative,
    PiiItem,
    Provenance,
    Source,
    ToolSchema,
    case_characters,
    digits_of,
    unsafe_filler,
    distinct_values,
    same_value,
    type_denominators,
    validate,
)

FAMILY: str = "spoken_id"
MODULE: str = "spoken_id"
TARGET: int = 190


class BuildError(RuntimeError):
    """The corpus cannot be built as claimed. Raised, never worked around."""


# --- corpora --------------------------------------------------------------
#
# Not in the repository and not in /tmp, which is wiped on reboot — NEREL was
# lost that way twice. RuDevices is CC BY 4.0, so its text may ship; the calls
# corpus is CC BY-NC 4.0 and only its MINED GRAMMAR is used here, never a line of
# its text.

CACHE = Path.home() / ".cache" / "pseudex-bench"
RUDEVICES = CACHE / "speech_rudevices.jsonl"
MINED = Path(__file__).resolve().parent.parent / "mined"

RUDEVICES_LICENCE: str = "CC BY 4.0"
CALLS_LICENCE: str = "CC BY-NC 4.0"
ATTRIBUTION: str = (
    "SOVA Dataset / RuDevices, CC BY 4.0 (текст реплик-заполнителей); "
    "формы диктовки — из грамматики, добытой на OpenSTT asr_calls_2_val, "
    "CC BY-NC 4.0 (текст не переносится)")


# --- the mined grammar ----------------------------------------------------
#
# A shape id is checked against the mined file rather than trusted. A typo in the
# pattern string would make `Provenance.shape` name nothing, and «the form came
# from real speech» would be back to being an assertion nobody can check — which
# is the state 1070 of v2's 1334 cases were in.

def _known_shapes() -> frozenset[str]:
    path = MINED / "calls_grammar.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. The dictation shapes are mined by "
            f"bench/agentpii3/mine_calls.py; this family will not invent them.")
    with path.open(encoding="utf-8") as handle:
        grammar = json.load(handle)
    return frozenset(str(entry["pattern"]) for entry in grammar["shapes"])


SHAPES: frozenset[str] = _known_shapes()


def _shape(pattern: str) -> str:
    if pattern not in SHAPES:
        raise BuildError(
            f"shape {pattern!r} is not in mined/calls_grammar.json; a "
            f"`recombined` case whose shape names nothing is a template wearing "
            f"a better label")
    return pattern


# The seven forms this family draws on, by the name the mined file gives them.
# Counts in the comments are the mined ones, so a reader can check the mix
# against the corpus instead of against taste.
S_PAIRS = _shape(                                                       # 7
    "телефон — пробегом числительных парами: «сорок один ноль девять шестьдесят "
    "семь», без «плюс семь»")
S_RUN = _shape(                                                         # 83
    "непрерывный пробег числительных длиной 4-8 слов, без единой цифры")
S_ZERO = _shape(                                                        # 95
    "ноль внутри номера произносится словом и часто удваивается: «ноль ноль»")
S_CONTRACTED = _shape(                                                  # 21
    "пятьдесят → песят / пеесят / пяесят, шестьдесят → шеесят / шейсят / шесят")
S_TRUNCATED = _shape(                                                   # 8
    "числительное обрезано на середине: триц, тридц, трис, девяно, семест")
S_DICTATION = _shape(                                                   # 41
    "диктовка вслух: «записывай», «записал», «пишите» — значение стоит рядом")
S_REASK = _shape(                                                       # 165
    "переспрос: «ещё раз», «повторите», «не слышу» — и значение звучит второй раз")

# Name shapes. The dictation almost never arrives without somebody attached to
# it — «это иванов записывай номер» — and the mined counts say which forms of
# naming are real.
S_NAME_THIS = _shape("это <имя>")                                       # 11
S_NAME_SURNAME = _shape("<фамилия>")                                    # 350
S_NAME_MY_SURNAME = _shape("моя фамилия <фамилия>")                     # 3
S_NAME_CALLED = _shape("меня зовут <имя>")                              # 4
S_NAME_GIVEN_PATR = _shape("<имя> <отчество>")                          # 109
S_NAME_FIO = _shape("<фамилия> <имя> <отчество>")                       # 23
S_NAME_ROLE = _shape(
    "<должность или звание> <фамилия> — сторож васильев, полковник заболотный, "
    "дежурная новикова")                                                # 75


# --- numerals -------------------------------------------------------------
#
# Spelling and parsing are two halves of ONE claim: that the digits demanded at
# the tool follow from the words that were said. They are written together, and
# `_check_roundtrip` asserts the claim for every value the family emits.

_UNITS: tuple[str, ...] = (
    "ноль", "один", "два", "три", "четыре",
    "пять", "шесть", "семь", "восемь", "девять")
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать")
_TENS: dict[int, str] = {
    2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
    6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"}
_HUNDREDS: dict[int, str] = {
    1: "сто", 2: "двести", 3: "триста", 4: "четыреста", 5: "пятьсот",
    6: "шестьсот", 7: "семьсот", 8: "восемьсот", 9: "девятьсот"}

# The decoder's own errors, taken from `lexicon.asr_error` of the mined file and
# not from imagination. 22.9% of every «-десят» form in the call corpus arrives
# contracted, and numerals arrive truncated mid-word. Every variant here is also
# in `schema.NUMERAL_WORDS`, so a run carrying one is still SEEN by the corpus
# audit — a variant the audit cannot see would be a hole dressed as realism.
_ASR_VARIANTS: dict[str, tuple[str, ...]] = {
    "пятьдесят": ("песят", "пеесят", "пяесят", "пейсят", "пясят"),
    "шестьдесят": ("шеесят", "шейсят", "шесят"),
    "восемьдесят": ("восемесят",),
    "тридцать": ("триц", "тридц", "трис"),
    "девяносто": ("девяно",),
    "семьсот": ("семест",),
    "восемьсот": ("восемест", "восемьст"),
    "триста": ("тристо", "трииста"),
    "шестьсот": ("шессот",),
    "восемь": ("восем", "восемсь"),
    "пять": ("пяять",),
    "четыре": ("четыыре",),
}

# The way back. Built from the table above rather than restated: two lists that
# have to stay equal are one list and a bug waiting for the second edit.
_VARIANT_TO_CANONICAL: dict[str, str] = {
    variant: canonical
    for canonical, variants in _ASR_VARIANTS.items()
    for variant in variants}

_ZERO_WORDS: frozenset[str] = frozenset({"ноль", "нуль"})
_UNIT_VALUE: dict[str, int] = {
    word: value for value, word in enumerate(_UNITS) if value}
_TEEN_VALUE: dict[str, int] = {
    word: 10 + offset for offset, word in enumerate(_TEENS)}
_TENS_VALUE: dict[str, int] = {word: tens * 10 for tens, word in _TENS.items()}
_HUNDRED_VALUE: dict[str, int] = {
    word: hundreds * 100 for hundreds, word in _HUNDREDS.items()}


def _canonical_numeral(word: str) -> str:
    return _VARIANT_TO_CANONICAL.get(word, word)


def _spell_under_hundred(value: int) -> tuple[str, ...]:
    if value < 10:
        return (_UNITS[value],)
    if value < 20:
        return (_TEENS[value - 10],)
    tens, unit = divmod(value, 10)
    if unit:
        return (_TENS[tens], _UNITS[unit])
    return (_TENS[tens],)


def _spell_chunk(chunk: str) -> tuple[str, ...]:
    """One group of one to three digits, as a caller says it.

    A leading zero is its own word — «ноль сорок два» for 042 — because that is
    how the corpus does it and because it keeps the group's WIDTH readable to the
    parser, which is what makes the digits recoverable at all.
    """
    if not 1 <= len(chunk) <= 3 or not chunk.isdigit():
        raise BuildError(f"a spoken group is one to three digits, not {chunk!r}")
    words: list[str] = []
    body = chunk
    while len(body) > 1 and body[0] == "0":
        words.append("ноль")
        body = body[1:]
    value = int(body)
    if len(body) == 3:
        words.append(_HUNDREDS[value // 100])
        if value % 100:
            words.extend(_spell_under_hundred(value % 100))
    elif len(body) == 2:
        words.extend(_spell_under_hundred(value))
    else:
        words.append(_UNITS[value])
    return tuple(words)


def _parse_numerals(words: tuple[str, ...]) -> str:
    """Greedy left-to-right, exactly as a listener does it.

    «ноль» never joins the group in front of it: «сто ноль» is a hundred and then
    a zero, never «сто» with nothing added, and refusing the join is what removes
    the only ambiguity a leading zero could create.

    A hundreds word opens a three-wide group and may absorb a tens word and then
    a unit; a tens word opens a two-wide group and may absorb a unit; a teen and
    a unit close immediately. Everything else raises, because a numeral this
    parser does not know inside a value means the ground truth was written by a
    speller the check does not cover.
    """
    digits: list[str] = []
    index = 0
    while index < len(words):
        word = _canonical_numeral(words[index])
        if word in _ZERO_WORDS:
            digits.append("0")
            index += 1
            continue
        if word in _HUNDRED_VALUE:
            value = _HUNDRED_VALUE[word]
            index += 1
            if index < len(words):
                following = _canonical_numeral(words[index])
                if following in _TENS_VALUE:
                    value += _TENS_VALUE[following]
                    index += 1
                    if index < len(words):
                        third = _canonical_numeral(words[index])
                        if third in _UNIT_VALUE:
                            value += _UNIT_VALUE[third]
                            index += 1
                elif following in _TEEN_VALUE:
                    value += _TEEN_VALUE[following]
                    index += 1
                elif following in _UNIT_VALUE:
                    value += _UNIT_VALUE[following]
                    index += 1
            digits.append(f"{value:03d}")
            continue
        if word in _TENS_VALUE:
            value = _TENS_VALUE[word]
            index += 1
            if index < len(words):
                following = _canonical_numeral(words[index])
                if following in _UNIT_VALUE:
                    value += _UNIT_VALUE[following]
                    index += 1
            digits.append(f"{value:02d}")
            continue
        if word in _TEEN_VALUE:
            digits.append(f"{_TEEN_VALUE[word]:02d}")
            index += 1
            continue
        if word in _UNIT_VALUE:
            digits.append(str(_UNIT_VALUE[word]))
            index += 1
            continue
        raise BuildError(f"{word!r} is not a numeral this family can decode")
    return "".join(digits)


def _spell_groups(digits: str, sizes: tuple[int, ...]) -> tuple[str, ...]:
    """A digit string cut into groups and spoken.

    The cut is NOT free: «триста» followed by «сорок два» is heard as 342, so a
    group ending in a bare hundreds or tens word swallows the next group's head.
    The generator does not paper over that — it redraws the value until the
    rendering parses back — because a rendering a listener cannot resolve is a
    ground truth the message did not carry.
    """
    if sum(sizes) != len(digits):
        raise BuildError(
            f"group sizes {sizes} do not add up to {len(digits)} digits")
    words: list[str] = []
    position = 0
    for size in sizes:
        words.extend(_spell_chunk(digits[position:position + size]))
        position += size
    return tuple(words)


def _asr_noise(words: tuple[str, ...], stream: random.Random,
               share: float) -> tuple[str, ...]:
    """Decoder slips, at the measured rate. Every slip stays decodable."""
    noised: list[str] = []
    for word in words:
        variants = _ASR_VARIANTS.get(word)
        if variants and stream.random() < share:
            noised.append(stream.choice(variants))
        else:
            noised.append(word)
    return tuple(noised)


def _check_roundtrip(spoken: str, canonical: str, kind: str, where: str) -> None:
    """The claim the family rests on, asserted for every emitted value.

    Judged by `schema.same_value`, not by string equality, and the difference is
    the point: only a PHONE may legitimately change its leading country code, so
    «восемь девятьсот…» decoding to 8916… satisfies a canonical of +7916…, while
    a СНИЛС differing in its first two digits is a different citizen. Restating
    that rule here instead of importing it is how v2 came to compare the last ten
    digits of everything.
    """
    parsed = _parse_numerals(tuple(spoken.split()))
    if not same_value(parsed, canonical, kind):
        raise BuildError(
            f"{where}: «{spoken}» decodes to {parsed!r}, the ground truth says "
            f"{canonical!r} — a benchmark may not demand digits the utterance "
            f"does not carry")


# --- the identifiers ------------------------------------------------------
#
# Values are TEMPLATE by construction and say so (`PiiItem.value_source`). Every
# one of these types occurs zero or near-zero times in either speech corpus —
# measured in `mined/reference_distribution.json` — so mining cannot reach them.
# The SENTENCE around them is still a mined one, which is the whole point of
# keeping `Provenance.kind` and `value_source` as two fields.

def _snils_digits(stream: random.Random) -> str:
    """Nine digits plus the mod-101 check. A real СНИЛС, not a minted fake.

    The vault mints fakes that deliberately FAIL their own checksum, so a valid
    one here can never collide with a substitute — and a gold value that failed
    its checksum would be testing the recognizer on something no citizen has.
    """
    body = "".join(str(stream.randint(0, 9)) for _ in range(9))
    while len(set(body)) < 3:            # 001-001-998 has its own special rule
        body = "".join(str(stream.randint(0, 9)) for _ in range(9))
    total = sum(int(digit) * (9 - position) for position, digit in enumerate(body))
    if total < 100:
        check = total
    elif total in (100, 101):
        check = 0
    else:
        remainder = total % 101
        check = 0 if remainder in (100, 101) else remainder
    return f"{body}{check:02d}"


def _inn_digits(stream: random.Random) -> str:
    """Twelve digits of a personal ИНН, both check digits computed."""
    body = "".join(str(stream.randint(0, 9)) for _ in range(10))
    first_weights = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    second_weights = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    eleventh = sum(int(d) * w for d, w in zip(body, first_weights)) % 11 % 10
    with_eleventh = f"{body}{eleventh}"
    twelfth = sum(int(d) * w
                  for d, w in zip(with_eleventh, second_weights)) % 11 % 10
    return f"{with_eleventh}{twelfth}"


def _card_digits(stream: random.Random) -> str:
    """Sixteen digits closing under Luhn, on a real Russian BIN."""
    bins = ("220070", "427644", "546901", "553691", "415482", "639002")
    body = stream.choice(bins) + "".join(
        str(stream.randint(0, 9)) for _ in range(9))
    total = 0
    for position, digit in enumerate(reversed(body)):
        value = int(digit)
        if position % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return f"{body}{(10 - total % 10) % 10}"


def _passport_digits(stream: random.Random) -> str:
    """Series and number, ten digits. The series' first two are a real region."""
    regions = ("45", "40", "18", "63", "54", "66", "36", "78", "16", "50")
    return (f"{stream.choice(regions)}{stream.randint(10, 24):02d}"
            f"{stream.randint(100000, 999999)}")


def _mobile_digits(stream: random.Random) -> str:
    """Eleven digits with a leading 8 — the form 128 of v2's 133 phones took."""
    codes = ("916", "926", "903", "905", "912", "917", "919", "951", "962", "981")
    return f"8{stream.choice(codes)}{stream.randint(1000000, 9999999)}"


def _local_digits(stream: random.Random) -> str:
    """Six digits: the city number the call corpus actually carries.

    «сорок один ноль девять шестьдесят семь» = 41-09-67, three pairs, and «плюс
    семь» is not said once in 12 950 replies. A corpus that only ever dictated
    mobiles would be testing the shape we imagined instead of the shape mined.
    """
    return f"{stream.randint(2, 7)}{stream.randint(10000, 99999)}"


# --- the value, as said and as demanded -----------------------------------

@dataclass(frozen=True)
class _Value:
    """One identifier in both of its forms, plus what the tool must receive.

    `spoken` is the surface — what the caller said, decoder slips included.
    `canonical` is what a CRM stores. They are different strings on purpose and
    the round trip is judged against the second, because that is the contract a
    tool has; `schema.classify_break` names a value that comes back in words
    `renumbered`, which is the diagnosis, not a pass.
    """

    kind: str
    spoken: str
    canonical: str
    shape: str


_GROUPINGS_MOBILE: tuple[tuple[int, ...], ...] = (
    (1, 3, 3, 2, 2),          # 8 / 916 / 642 / 85 / 50 — the commonest
    (1, 3, 2, 2, 2, 1),
    (1, 3, 3, 3, 1),
    (1,) * 11,                # digit by digit, when the line is bad
)
_GROUPINGS_LOCAL: tuple[tuple[int, ...], ...] = ((2, 2, 2), (1,) * 6, (3, 3))
_GROUPINGS_SNILS: tuple[tuple[int, ...], ...] = (
    (3, 3, 3, 2), (1,) * 11, (2, 2, 2, 2, 3))
_GROUPINGS_INN: tuple[tuple[int, ...], ...] = (
    (3, 3, 3, 3), (2, 2, 2, 2, 2, 2), (1,) * 12)
_GROUPINGS_CARD: tuple[tuple[int, ...], ...] = (
    (2,) * 8, (2, 2, 3, 1, 2, 2, 2, 2), (3, 1, 2, 2, 2, 2, 2, 2))
_GROUPINGS_PASSPORT: tuple[tuple[int, ...], ...] = (
    (2, 2, 3, 3), (2, 2, 2, 2, 2), (1,) * 10)

_GROUPINGS: dict[str, tuple[tuple[int, ...], ...]] = {
    "PHONE": _GROUPINGS_MOBILE,
    "SNILS": _GROUPINGS_SNILS,
    "INN": _GROUPINGS_INN,
    "CARD": _GROUPINGS_CARD,
    "PASSPORT": _GROUPINGS_PASSPORT,
}
_DIGIT_MAKER = {
    "PHONE": _mobile_digits,
    "SNILS": _snils_digits,
    "INN": _inn_digits,
    "CARD": _card_digits,
    "PASSPORT": _passport_digits,
}


def _canonical_of(kind: str, digits: str) -> str:
    """The machine form a Russian back office actually stores."""
    if kind == "PHONE":
        if len(digits) == 11:
            return f"+7{digits[1:]}"
        return digits
    if kind == "SNILS":
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:11]}"
    if kind == "CARD":
        return " ".join(digits[i:i + 4] for i in range(0, 16, 4))
    if kind == "PASSPORT":
        return f"{digits[0:4]} {digits[4:10]}"
    return digits


def _draw_numeric(kind: str, stream: random.Random,
                  noise: float) -> _Value:
    """A numeric identifier and the words it was said in.

    Redraws until the rendering parses back to the same digits. The redraw is not
    a filter on which cases exist — every case still exists, only its digits move
    — and without it a group ending in a bare «триста» would swallow the head of
    the next one and the ground truth would ask for digits nobody said.
    """
    maker = _DIGIT_MAKER[kind]
    groupings = _GROUPINGS[kind]
    for _ in range(400):
        digits = maker(stream)
        sizes = stream.choice(groupings)
        words = _asr_noise(_spell_groups(digits, sizes), stream, noise)
        spoken = " ".join(words)
        if _parse_numerals(words) == digits:
            shape = S_PAIRS if kind == "PHONE" and max(sizes) == 2 else S_RUN
            if any(word in _ZERO_WORDS for word in words):
                shape = S_ZERO
            if any(word in _VARIANT_TO_CANONICAL for word in words):
                shape = (S_CONTRACTED
                         if any(_VARIANT_TO_CANONICAL.get(w, "").endswith("десят")
                                for w in words)
                         else S_TRUNCATED)
            return _Value(kind=kind, spoken=spoken,
                          canonical=_canonical_of(kind, digits), shape=shape)
    raise BuildError(
        f"could not render a decodable {kind} in 400 draws; the grouping table "
        f"and the parser have gone out of step")


def _spoken_digits(value: _Value) -> str:
    """The digits a CALLER pronounces, which are not always the stored ones.

    A Russian mobile is stored as +7… and said as «восемь…»; nobody says «плюс
    семь» — zero times in 12 950 replies. `schema.same_value` forgives exactly
    that one substitution and only for a phone, so the re-say has to make it
    deliberately rather than inherit it.
    """
    digits = digits_of(value.canonical)
    if value.kind == "PHONE" and len(digits) == 11:
        return f"8{digits[1:]}"
    return digits


def _regroup(value: _Value, stream: random.Random) -> _Value:
    """The same identifier said a second time, cut differently.

    A caller who was not heard the first time says it digit by digit the second
    time, and that is the form the corpus shows. It matters here beyond realism:
    the two mentions share nothing on the surface, so a gateway that links them
    has linked by VALUE and not by string, which is what `LinkExpectation` asks.
    """
    digits = _spoken_digits(value)
    already = tuple(_canonical_numeral(word) for word in value.spoken.split())
    groupings = [(1,) * len(digits)]
    groupings += [sizes for sizes in _GROUPINGS.get(value.kind, ())
                  if sum(sizes) == len(digits) and max(sizes) > 1]
    for sizes in groupings:
        words = _spell_groups(digits, sizes)
        # A re-say that lands on the same cut is the same string twice, and a
        # gateway can pass it by matching text. Compared after the decoder slips
        # are folded away, or «восемсь» against «восемь» would count as a
        # different cut when the caller said the identical thing.
        if words == already or _parse_numerals(words) != digits:
            continue
        return _Value(kind=value.kind, spoken=" ".join(words),
                      canonical=value.canonical, shape=S_REASK)
    raise BuildError(f"no decodable re-grouping for {value.canonical!r}")


def _draw_local_phone(stream: random.Random, noise: float) -> _Value:
    for _ in range(400):
        digits = _local_digits(stream)
        sizes = stream.choice(_GROUPINGS_LOCAL)
        words = _asr_noise(_spell_groups(digits, sizes), stream, noise)
        if _parse_numerals(words) == digits:
            return _Value(kind="PHONE", spoken=" ".join(words),
                          canonical=digits,
                          shape=S_PAIRS if sizes == (2, 2, 2) else S_RUN)
    raise BuildError("could not render a decodable local number in 400 draws")


# --- the identifiers that are not a bare numeral run ----------------------

_DAY_GENITIVE: tuple[str, ...] = (
    "", "первого", "второго", "третьего", "четвёртого", "пятого", "шестого",
    "седьмого", "восьмого", "девятого", "десятого", "одиннадцатого",
    "двенадцатого", "тринадцатого", "четырнадцатого", "пятнадцатого",
    "шестнадцатого", "семнадцатого", "восемнадцатого", "девятнадцатого",
    "двадцатого", "двадцать первого", "двадцать второго", "двадцать третьего",
    "двадцать четвёртого", "двадцать пятого", "двадцать шестого",
    "двадцать седьмого", "двадцать восьмого")
_MONTH_GENITIVE: tuple[str, ...] = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня", "июля",
    "августа", "сентября", "октября", "ноября", "декабря")
_TENS_ORDINAL_GENITIVE: dict[int, str] = {
    4: "сорокового", 5: "пятидесятого", 6: "шестидесятого",
    7: "семидесятого", 8: "восьмидесятого", 9: "девяностого"}
_UNIT_ORDINAL_GENITIVE: tuple[str, ...] = (
    "", "первого", "второго", "третьего", "четвёртого", "пятого", "шестого",
    "седьмого", "восьмого", "девятого")


def _draw_dob(stream: random.Random) -> _Value:
    """A birth date said the way a person says it, never read off a form.

    «двенадцатого марта восемьдесят пятого года» — the century is not spoken and
    is not demanded back as information: 40-99 is unambiguously 19xx in a date of
    birth given today, which is the same kind of determinism the numeral parser
    provides for the digit types.
    """
    day = stream.randint(1, 28)
    month = stream.randint(1, 12)
    year_short = stream.randint(45, 99)
    tens, unit = divmod(year_short, 10)
    year_words = (f"{_TENS[tens]} {_UNIT_ORDINAL_GENITIVE[unit]}" if unit
                  else _TENS_ORDINAL_GENITIVE[tens])
    spoken = (f"{_DAY_GENITIVE[day]} {_MONTH_GENITIVE[month]} "
              f"{year_words} года")
    return _Value(kind="DOB", spoken=spoken,
                  canonical=f"{day:02d}.{month:02d}.19{year_short}",
                  shape=S_RUN)


_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}

_DOMAINS_SPOKEN: tuple[tuple[str, str], ...] = (
    ("мэйл точка ру", "mail.ru"),
    ("яндекс точка ру", "yandex.ru"),
    ("джимейл точка ком", "gmail.com"),
    ("бэ ка точка ру", "bk.ru"),
    ("рамблер точка ру", "rambler.ru"),
)


def _translit(word: str) -> str:
    return "".join(_TRANSLIT.get(letter, letter) for letter in word.lower())


def _draw_email(surname: str, stream: random.Random) -> _Value:
    """«иванов собака мэйл точка ру». No digit, no @ sign, no dot.

    Every anchor an email recognizer has — the at sign, the dot, the top-level
    domain — is a WORD here. This is the type where the spoken register removes
    not one signal but all of them at once.
    """
    spoken_domain, domain = stream.choice(_DOMAINS_SPOKEN)
    local = _translit(surname)
    return _Value(kind="EMAIL", spoken=f"{surname.lower()} собака {spoken_domain}",
                  canonical=f"{local}@{domain}", shape=S_DICTATION)


_PLATE_LETTERS: tuple[tuple[str, str], ...] = (
    ("А", "а"), ("В", "вэ"), ("Е", "е"), ("К", "ка"), ("М", "эм"), ("Н", "эн"),
    ("О", "о"), ("Р", "эр"), ("С", "эс"), ("Т", "тэ"), ("У", "у"), ("Х", "ха"))
_PLATE_REGIONS: tuple[str, ...] = (
    "77", "99", "78", "16", "54", "66", "36", "63", "43", "18")


def _draw_plate(stream: random.Random) -> _Value:
    """«эм сто пятьдесят два эн эр регион девяносто девять» → М152НР99."""
    first, first_spoken = stream.choice(_PLATE_LETTERS)
    second, second_spoken = stream.choice(_PLATE_LETTERS)
    third, third_spoken = stream.choice(_PLATE_LETTERS)
    number = f"{stream.randint(100, 999)}"
    region = stream.choice(_PLATE_REGIONS)
    spoken = (f"{first_spoken} {' '.join(_spell_chunk(number))} "
              f"{second_spoken} {third_spoken} регион "
              f"{' '.join(_spell_chunk(region))}")
    return _Value(kind="PLATE", spoken=spoken,
                  canonical=f"{first}{number}{second}{third}{region}",
                  shape=S_DICTATION)


# --- people ---------------------------------------------------------------
#
# A small authored pool. It is small on purpose and the count of DISTINCT values
# is printed beside the count of occurrences: one name said by seven callers is
# one value and seven occurrences, and an interval over occurrences is narrower
# than the truth and narrower in our favour.

@dataclass(frozen=True)
class _Person:
    given: str
    patronymic: str
    surname: str
    female: bool
    short_patronymic: str      # «палыч», «иваныч»; "" when the pair has none
    surname_dative: str        # «букину» — the addressee is in an oblique case


_PEOPLE: tuple[_Person, ...] = (
    _Person("Сергей", "Павлович", "Букин", False, "палыч", "букину"),
    _Person("Игорь", "Иванович", "Кузнецов", False, "иваныч", "кузнецову"),
    _Person("Валерий", "Михайлович", "Миллер", False, "михалыч", "миллеру"),
    _Person("Вячеслав", "Степанович", "Фомин", False, "степаныч", "фомину"),
    _Person("Роман", "Викторович", "Ерохин", False, "викторыч", "ерохину"),
    _Person("Евгений", "Николаевич", "Вольнов", False, "николаич", "вольнову"),
    _Person("Олег", "Фёдорович", "Заболотный", False, "фёдорыч", "заболотному"),
    _Person("Артём", "Сергеевич", "Кукушкин", False, "сергеич", "кукушкину"),
    _Person("Денис", "Леонидович", "Тарасов", False, "леонидыч", "тарасову"),
    _Person("Павел", "Константинович", "Бабаев", False, "константиныч", "бабаеву"),
    _Person("Никита", "Давидович", "Лебедев", False, "давидыч", "лебедеву"),
    _Person("Тимур", "Алексеевич", "Шагиев", False, "алексеич", "шагиеву"),
    _Person("Руслан", "Маратович", "Гилязов", False, "", "гилязову"),
    _Person("Ашот", "Артурович", "Саркисян", False, "", "саркисяну"),
    _Person("Леонид", "Аркадьевич", "Птицын", False, "", "птицыну"),
    _Person("Тамара", "Ивановна", "Полякова", True, "", "поляковой"),
    _Person("Валентина", "Ивановна", "Новикова", True, "", "новиковой"),
    _Person("Лидия", "Викторовна", "Битюкова", True, "", "битюковой"),
    _Person("Нина", "Васильевна", "Сорокина", True, "", "сорокиной"),
    _Person("Зинаида", "Николаевна", "Абрамова", True, "", "абрамовой"),
    _Person("Марина", "Борисовна", "Дроздова", True, "", "дроздовой"),
    _Person("Олеся", "Петровна", "Гончарова", True, "", "гончаровой"),
    _Person("Любовь", "Андреевна", "Ковалёва", True, "", "ковалёвой"),
    _Person("Регина", "Ильинична", "Хайруллина", True, "", "хайруллиной"),
    _Person("Наталья", "Юрьевна", "Ситникова", True, "", "ситниковой"),
    _Person("Алиса", "Германовна", "Черкасова", True, "", "черкасовой"),
)

# «дежурный», «полковник», «сторож» stand in front of a surname 75 times in the
# mined corpus and are NOT part of the name: a span that swallows the rank has
# masked a word that identifies nobody and lost the boundary of the one that does.
_ROLES: tuple[str, ...] = (
    "дежурный", "полковник", "сторож", "дежурная", "подполковник", "майор",
    "капитан", "лейтенант")


@dataclass(frozen=True)
class _Name:
    """A named person as one span: the surface said, the canonical demanded."""

    surface: str
    canonical: str
    shape: str
    lead: str        # the words in front that are NOT part of the span


def _name_forms(person: _Person, stream: random.Random) -> _Name:
    """One of the mined ways of naming somebody, drawn at the mined frequency.

    The weights are the mined counts, so «<фамилия>» alone dominates exactly as
    it does in the corpus (350 of 815 mentions). A uniform draw would have
    invented a register in which people introduce themselves in full, which is
    the register v2 measured and this one does not exist.
    """
    weighted: tuple[tuple[str, int], ...] = (
        ("surname", 35), ("given", 25), ("given_patr", 14), ("fio", 8),
        ("this_given", 6), ("role_surname", 8), ("my_surname", 4), ("called", 4),
    )
    total = sum(weight for _, weight in weighted)
    cut = stream.randrange(total)
    running = 0
    form = weighted[-1][0]
    for candidate, weight in weighted:
        running += weight
        if cut < running:
            form = candidate
            break
    if form == "given_patr" and not person.short_patronymic:
        form = "given"
    if form == "surname":
        return _Name(person.surname.lower(), person.surname, S_NAME_SURNAME, "")
    if form == "given":
        return _Name(person.given.lower(), person.given, S_NAME_THIS, "")
    if form == "given_patr":
        # The contracted patronymic is the only form template generation never
        # produces and the corpus produces constantly. «палыч» determines
        # «Павлович» — nothing is invented by asking for the full form back.
        return _Name(f"{person.given.lower()} {person.short_patronymic}",
                     f"{person.given} {person.patronymic}", S_NAME_GIVEN_PATR, "")
    if form == "fio":
        return _Name(
            f"{person.surname.lower()} {person.given.lower()} "
            f"{person.patronymic.lower()}",
            f"{person.surname} {person.given} {person.patronymic}",
            S_NAME_FIO, "")
    if form == "this_given":
        return _Name(person.given.lower(), person.given, S_NAME_THIS, "это")
    if form == "role_surname":
        return _Name(person.surname.lower(), person.surname, S_NAME_ROLE,
                     stream.choice(_ROLES))
    if form == "my_surname":
        return _Name(person.surname.lower(), person.surname, S_NAME_MY_SURNAME,
                     "моя фамилия")
    return _Name(person.given.lower(), person.given, S_NAME_CALLED, "меня зовут")


def _name_written(person: _Person, stream: random.Random) -> _Name:
    """A typed channel: the surface already IS the canonical."""
    if stream.randrange(3):
        return _Name(f"{person.surname} {person.given}",
                     f"{person.surname} {person.given}", S_NAME_FIO, "")
    return _Name(person.surname, person.surname, S_NAME_SURNAME, "")


# --- negatives ------------------------------------------------------------
#
# Half the precision measurement, and in this register the largest false-positive
# source is known and counted: a number standing beside «кабинет» or «отделение»
# occurs 528 times in the call corpus. These are authored from those counts, and
# they are dictated the SAME WAY the identifier is — which is the only
# arrangement under which «masked the order number» and «found the card» can be
# told apart.

@dataclass(frozen=True)
class _Negative:
    family: str
    lead: str          # words in front, outside the span
    spoken: str        # the span, in words
    typed: str         # the span, once a transcriber has normalised it
    why: str


def _spoken_number(value: int, sizes: tuple[int, ...]) -> str:
    digits = "".join(f"{value:0{sum(sizes)}d}")
    return " ".join(_spell_groups(digits, sizes))


def _order_negative(stream: random.Random) -> _Negative:
    """The defect that shipped once: a dictated order number, masked.

    It does not leak — nobody's privacy is in it — it BREAKS the call, and the
    customer's own gateway log shows an order that does not exist.
    """
    lead = stream.choice(("номер заказа", "заказ", "трек номер", "артикул",
                          "код подтверждения", "заявка"))
    value = stream.randint(1000, 9999)
    sizes = stream.choice(((1, 1, 1, 1), (2, 2)))
    return _Negative("order_number", lead, _spoken_number(value, sizes),
                     str(value),
                     "номер заказа — не персональные данные; замаскированный, он "
                     "не утекает, а ломает вызов инструмента")


def _room_negative(stream: random.Random) -> _Negative:
    """«три четырнадцатый кабинет» — 528 of these in 12 950 replies.

    Every negative in this family carries a NON-NUMERAL lead, and that is
    structural rather than stylistic: a negative whose first word is a numeral,
    placed straight after a dictated identifier, makes the boundary between the
    two runs a matter of opinion — and a corpus may not ask a gateway to guess
    what its own annotator could not decide.
    """
    variant = stream.randrange(3)
    if variant == 0:
        return _Negative(
            "room_number", "а я жду в", "три четырнадцатый кабинет", "314 кабинет",
            "порядковое рядом с кабинетом — самый частый ложный срабатыватель "
            "этого регистра")
    if variant == 1:
        return _Negative(
            "room_number", "приходите во", "второе отделение", "2 отделение",
            "отделение — место, а не адрес человека")
    return _Negative("room_number", "подойдите в", "шестое окно", "6 окно",
                     "окно приёма — номер, который никого не определяет")


_HOUR_SPOKEN: dict[int, str] = {
    8: "восемь", 9: "девять", 10: "десять", 11: "одиннадцать", 12: "двенадцать",
    13: "тринадцать", 14: "четырнадцать", 15: "пятнадцать", 16: "шестнадцать",
    17: "семнадцать", 18: "восемнадцать", 19: "девятнадцать"}
_HOUR_DATIVE: dict[int, str] = {
    8: "восьми", 9: "девяти", 10: "десяти", 11: "одиннадцати", 12: "двенадцати",
    13: "тринадцати", 14: "четырнадцати", 15: "пятнадцати", 16: "шестнадцати",
    17: "семнадцати", 18: "восемнадцати", 19: "девятнадцати"}


def _time_negative(stream: random.Random) -> _Negative:
    """«к девяти ноль ноль» — 66 of these, and the zeros are words.

    The commonest numeral run in the corpus that carries nothing at all. It is
    also the one a digit-blind spoken-identifier recognizer is most likely to
    swallow, since «девять ноль ноль» is exactly the shape of three dictated
    digits.
    """
    # The normalised form carries no colon. ITN restores digits, not punctuation
    # — the measured share of any sentence punctuation across 53 324 utterances
    # is zero, and a transcriber that inserted one would be a different product.
    hour = stream.randint(8, 19)
    if stream.randrange(2):
        return _Negative("time_of_day", "к", f"{_HOUR_DATIVE[hour]} ноль ноль",
                         f"{hour} 00",
                         "время с проговоренными нолями — пробег числительных, "
                         "который персональными данными не является")
    return _Negative("time_of_day", "в", f"{_HOUR_SPOKEN[hour]} тридцать",
                     f"{hour} 30", "время встречи — не идентификатор")


def _quantity_negative(stream: random.Random) -> _Negative:
    variant = stream.randrange(3)
    if variant == 0:
        count = stream.randint(2, 9)
        unit = stream.choice(("коробки", "штуки", "упаковки", "места"))
        return _Negative("quantity", "всего", f"{_UNITS[count]} {unit}",
                         f"{count} {unit}", "количество — не идентификатор")
    if variant == 1:
        thousands = stream.randint(2, 9)
        return _Negative("quantity", "сумма",
                         f"{_UNITS[thousands]} тысячи рублей",
                         f"{thousands}000 рублей",
                         "сумма к оплате — не персональные данные")
    return _Negative("quantity", "у нас", "двенадцать филиалов", "12 филиалов",
                     "число филиалов — не адрес и не человек")


def _measure_negative(stream: random.Random) -> _Negative:
    variant = stream.randrange(2)
    if variant == 0:
        return _Negative("measure", "ехать", "сто двадцать километров",
                         "120 километров",
                         "расстояние с единицей измерения — не дом и не номер")
    return _Negative("measure", "территория", "пять гектаров", "5 гектаров",
                     "площадь территории — не адрес человека")


def _city_negative(stream: random.Random) -> _Negative:
    city = stream.choice(("новосибирске", "перми", "казани", "самаре",
                          "воронеже", "ижевске"))
    return _Negative("city_reference", "я сейчас в", city, city,
                     "город как место разговора никого не определяет "
                     "(152-ФЗ ст. 3 п. 1)")


def _entrance_negative(stream: random.Random) -> _Negative:
    ordinal = stream.choice(("втором", "третьем", "шестом", "четвёртом"))
    lead = "жду во" if ordinal.startswith("в") else "жду в"
    return _Negative("entrance_no_street", lead, f"{ordinal} подъезде",
                     f"{ordinal} подъезде",
                     "подъезд без улицы сам по себе никого не определяет")


def _fare_negative(stream: random.Random) -> _Negative:
    return _Negative("fare", "проезд", "сто рублей", "100 рублей",
                     "«проезд» здесь плата, а не тип улицы")


_NEGATIVE_MAKERS = (
    _order_negative, _room_negative, _time_negative, _quantity_negative,
    _measure_negative, _city_negative, _entrance_negative, _fare_negative)


def _draw_negatives(count: int, stream: random.Random) -> tuple[_Negative, ...]:
    """`count` negatives of DISTINCT families, order first at least half the time.

    The order number is over-represented against a uniform draw and that is a
    decision: it is the only negative in this family that also reaches a JUDGED
    argument, so it is the one that turns over-masking into a visible broken call
    rather than a line in a precision table.
    """
    makers = list(_NEGATIVE_MAKERS)
    stream.shuffle(makers)
    if stream.randrange(2):
        makers.remove(_order_negative)
        makers.insert(0, _order_negative)
    return tuple(maker(stream) for maker in makers[:count])


def _draw_other_negatives(count: int, stream: random.Random) -> tuple[_Negative, ...]:
    """Negatives for a case that ALREADY carries an order number.

    Two order numbers in one reply would be one observation counted twice, and
    the second one would push a genuinely different false-positive family — the
    cabinet, the time, the fare — out of the case that had room for it.
    """
    makers = [maker for maker in _NEGATIVE_MAKERS if maker is not _order_negative]
    stream.shuffle(makers)
    return tuple(maker(stream) for maker in makers[:count])


# --- register transforms --------------------------------------------------
#
# `sloppy` misspells the CUE WORDS and nothing else. A keyboard slip inside a
# numeral would make the ground truth unrecoverable from what was written, and a
# benchmark may not demand information the message did not carry; the cue word is
# also the more valuable target, because a misspelt cue is a documented way to
# switch off the guard a cue provides («пасспорт», «догвор»).

_MISSPELT: dict[str, str] = {
    "пожалуйста": "пожалуста",
    "телефона": "тилефона",
    "телефон": "тилефон",
    "паспорт": "пасспорт",
    "паспорта": "пасспорта",
    "записывайте": "записывате",
    "записывай": "записывай",
    "фамилия": "фамилиа",
    "здравствуйте": "здраствуйте",
    "диктую": "дикутю",
    "номер": "номре",
    "карты": "крты",
    "снилс": "снилис",
    "продиктую": "продикутю",
}


def _misspell(text: str, stream: random.Random) -> str:
    """One cue word per line, at most. Two would read as machine noise."""
    words = text.split()
    candidates = [index for index, word in enumerate(words) if word in _MISSPELT]
    if not candidates:
        return text
    chosen = stream.choice(candidates)
    words[chosen] = _MISSPELT[words[chosen]]
    return " ".join(words)


# --- line assembly --------------------------------------------------------
#
# Offsets are produced BY CONSTRUCTION and never by `text.find(value)`. The
# searched offset is derived from the finished string, and the finished string is
# what the register transform already rewrote — 162 of v2's 183 sloppy failures
# were that one mistake, made twice.

_GLUE: frozenset[str] = frozenset(",.:;!?")


@dataclass(frozen=True)
class _Piece:
    text: str
    tag: str          # "" when the piece carries no claim


def _plain(text: str) -> _Piece:
    return _Piece(text, "")


def _line(pieces: tuple[_Piece, ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    text = ""
    spans: dict[str, tuple[int, int]] = {}
    for piece in pieces:
        if not piece.text:
            continue
        if text and piece.text[0] not in _GLUE:
            text += " "
        start = len(text)
        text += piece.text
        if piece.tag:
            if piece.tag in spans:
                raise BuildError(f"tag {piece.tag!r} used twice in one line")
            spans[piece.tag] = (start, len(text))
    return text, spans


@dataclass(frozen=True)
class _Msg:
    role: str
    pieces: tuple[_Piece, ...]
    name: str
    source: Source | None


def _materialise(messages: tuple[_Msg, ...]
                 ) -> tuple[tuple[Message, ...], dict[str, tuple[int, int, int]]]:
    built: list[Message] = []
    located: dict[str, tuple[int, int, int]] = {}
    for index, message in enumerate(messages):
        text, spans = _line(message.pieces)
        for tag, (start, end) in spans.items():
            if tag in located:
                raise BuildError(f"tag {tag!r} used in two messages")
            located[tag] = (index, start, end)
        built.append(Message(role=message.role, content=text,
                             source=message.source, name=message.name))
    return tuple(built), located


# --- the filler, and it is real speech ------------------------------------
#
# RuDevices is CC BY 4.0 so its text ships, and every filler message carries its
# `Source` with a digest: a re-downloaded corpus whose lines shifted would
# silently move offsets, and `hydrate` refuses rather than going on printing
# numbers.
#
# The filter is a CONTENT filter and deliberately weaker than a detector. Its job
# is to keep an unclaimed personal datum out of filler, where the corpus would be
# wrong and the gateway would take the blame. Over-rejecting costs nothing: the
# pool is twenty thousand replies and the family draws a hundred.

_OBSCENE = re.compile(
    r"(?:^|[^а-яё])"
    r"(?:а|и|по|за|на|до|от|при|раз|вы|пере|про|под|об|из|ни|не|у|с|о)?[ъь]?"
    r"(?:бля|пизд|ху[йяеёиюы]|[её]б|сук[аиуе]|говн|жоп|срат|дроч|мудак|пидор|"
    r"ссан|шлюх|проститут|наркот|кокаин|героин|изнасил|труп|убийств|педоф|"
    r"суицид|сис[ьк]|член|отсас|сосал|сос[её]т|трах|секс|эрот|минет|аналь|"
    r"оргазм|порн|голая|голый|голым|интим|презерв|задниц|писюн|письк|хер[аоуы]|"
    r"залуп|крови|мочи|топор|напал|убил|убью|драк|мент[аыоу]|полиц|застрел|"
    r"зареж|повес|тюрьм|нарк|пьян|бухл|водк)")

# Words that mean the reply is ABOUT a person, a place or a number. Anything they
# hit is thrown away whether or not it actually carries a datum.
_TOPICAL = re.compile(
    r"\b(фамили\w*|отчеств\w*|зов[уё]т\w*|телефон\w*|адрес\w*|улиц\w*|"
    r"дом|дома|доме|домов|квартир\w*|подъезд\w*|паспорт\w*|снилс\w*|инн|"
    r"карт[аыуе]|номер\w*|дежурн\w*|полковник\w*|сторож\w*|майор|капитан|"
    r"лейтенант|генерал|дяд[яию]|т[её]т[яию]|мама|папа|брат|сестра|город\w*|"
    r"позов\w*|передай\w*|рубл\w*|тысяч\w*|миллион\w*|кабинет\w*|отделен\w*|"
    r"подъезж\w*|прибы\w*|гварди\w*|проспект\w*|шоссе|переул\w*|набережн\w*|"
    r"площад\w*|[а-яё]{4,}(ской|ская|ского|скую|ском))\b")

_PATRONYMIC_ISH = re.compile(r"[а-яё]*(ович|евич|овна|евна|ична|иныч|аныч|алыч|ыч)\b")
_LATIN = re.compile(r"[A-Za-z]")
_PUNCT = re.compile(r"[.,;:!?]")

# Given-name stems, matched as a token prefix. The list cannot be complete —
# Russian has thousands of diminutives — which is why it sits beside three other
# refusals rather than being trusted alone.
_NAME_STEMS: tuple[str, ...] = tuple("""
александр алексе анатол андре антон аркад арсен артём артем богдан борис вадим
валент валер васил виктор витал владим владисл вячесл геннад георг григор данил
денис дмитр евген егор ефим захар иван игор игнат илья иннокент кирилл констант
лев леон макс матве михаил никит никол олег павел пётр петр роман рустам руслан
семён семен серг станисл степан тарас тимур фёдор федор филипп эдуард юрий яков
ярослав анна алла ал[ёе]н анастас ангел вар вер викт галин дарь диан екатерин
елен елизавет жанн зинаид зо инн ирин карин катер кристин ксен лари лидь лил
люб людмил маргарит марин мари надежд наталь нин окс ольг полин раис регин
светл софь тамар татьян ульян юли яна вася ваня саша паша маша даша женя коля
миша сер[её]ж дима толя витя гриша л[её]ша тоня люда галя нюра валя костя слава
рома юра каролин тимош шамил олес наташ ленк славик витёк ирочк
""".split())
_NAMEY = re.compile(r"\b(?:" + "|".join(_NAME_STEMS) + r")[а-яё]{0,4}\b")


def _usable_filler(text: str) -> bool:
    """A reply that may stand beside a value without claiming anything.

    THE SCREEN IS `schema.unsafe_filler`, called and not restated. Five families
    each kept a private copy of this idea with a private name list, so «оксана»
    was in one of them and in none of the others; one place is what makes a word
    added once protect all eleven. `_NAMEY` survives beside it and is not
    redundant — it knows the hypocorisms («ленк», «наташ») that no gold span in
    this corpus carries, so the attested vocabulary cannot hold them.
    """
    if not 16 <= len(text) <= 78:
        return False
    if not 3 <= len(text.split()) <= 13:
        return False
    if any(character.isupper() for character in text):
        return False
    if _LATIN.search(text) or _PUNCT.search(text):
        return False
    if unsafe_filler(text):
        return False
    return not (_OBSCENE.search(text) or _TOPICAL.search(text)
                or _PATRONYMIC_ISH.search(text) or _NAMEY.search(text))


def _load_filler() -> tuple[tuple[str, str, int], ...]:
    """(key, text, 1-based line) for every reply that may stand beside a value."""
    if not RUDEVICES.exists():
        raise FileNotFoundError(
            f"{RUDEVICES} is missing. Fetch SOVA RuDevices into "
            f"~/.cache/pseudex-bench/ before building; the long context of this "
            f"family is real speech and no generated stand-in is accepted.")
    rows: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    with RUDEVICES.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = str(json.loads(line)["text"])
            if text in seen or not _usable_filler(text):
                continue
            seen.add(text)
            key = hashlib.blake2b(text.encode("utf-8"), digest_size=6).hexdigest()
            rows.append((key, text, line_number))
    if len(rows) < 500:
        raise BuildError(
            f"only {len(rows)} usable filler replies; the content filter and the "
            f"corpus have gone out of step and the long rung would repeat itself")
    return tuple(rows)


FILLER: tuple[tuple[str, str, int], ...] = _load_filler()


def _filler_message(row: tuple[str, str, int]) -> _Msg:
    key, text, line = row
    source = Source(corpus="speech_rudevices", key=key, line=line,
                    sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    licence=RUDEVICES_LICENCE)
    return _Msg("user", (_plain(text),), "", source)


# --- what the operator says back ------------------------------------------
#
# Short, digit-free and numeral-free on purpose: `schema.audit_unlabelled` scans
# assistant turns too, and an operator who says «до четырнадцати ноль ноль»
# would be putting an unclaimed run into the case.

_ACK_VOICE: tuple[str, ...] = (
    "ага записываю", "так угу", "записал", "минуточку", "да да слушаю",
    "понял вас", "хорошо принял", "угу пишу", "секунду", "так записываю",
    "да слышу вас", "ага понял")
_ACK_CHAT: tuple[str, ...] = (
    "принял", "записываю", "ок секунду", "понял, оформляю", "минуту")
_OPENERS_VOICE: tuple[str, ...] = (
    "алло", "аллё", "алё да", "алло здравствуйте", "да алло", "аллё слушаю")
_HAILS: tuple[str, ...] = ("слушай", "слышь", "смотри", "значит", "короче", "вот")
_HESITATION: tuple[str, ...] = ("эээ", "ааа", "нуу", "иии", "", "", "")

_DICTATION_CUES: dict[str, tuple[str, ...]] = {
    "PHONE": ("записывай номер телефона", "телефон записывайте", "пишите телефон",
              "диктую номер", "номер такой", "телефон мой"),
    "SNILS": ("снилс диктую", "записывайте снилс", "номер снилс такой",
              "снилс мой"),
    "INN": ("инн диктую", "записывайте инн", "инн такой"),
    "CARD": ("карта диктую номер", "номер карты записывайте", "карту диктую",
             "номер карты такой"),
    "PASSPORT": ("паспорт диктую", "записывайте паспорт", "паспортные данные",
                 "серия и номер паспорта"),
    "DOB": ("дата рождения", "родился", "родилась", "день рождения"),
    "EMAIL": ("почта такая", "записывайте почту", "электронка"),
    "PLATE": ("машина номер", "госномер", "номер машины"),
}

_CUE_TYPED: dict[str, tuple[str, ...]] = {
    "PHONE": ("телефон", "номер телефона", "тел"),
    "SNILS": ("снилс",), "INN": ("инн",), "CARD": ("номер карты", "карта"),
    "PASSPORT": ("паспорт", "паспортные данные"),
    "DOB": ("дата рождения",), "EMAIL": ("почта", "email"),
    "PLATE": ("госномер",),
}


# --- tools ----------------------------------------------------------------

def _tool(name: str, description: str,
          params: tuple[tuple[str, str, str], ...],
          required: tuple[str, ...]) -> ToolSchema:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    param: {"type": kind, "description": text}
                    for param, kind, text in params},
                "required": list(required),
            },
        },
    }


_T_CALLBACK = _tool(
    "schedule_callback", "Поставить обратный звонок клиенту.",
    (("name", "string", "Имя клиента как в карточке."),
     ("phone", "string", "Номер телефона в формате +7XXXXXXXXXX."),
     ("slot", "string", "Когда перезвонить.")),
    ("phone",))
_T_ORDER = _tool(
    "create_order", "Оформить заказ на клиента.",
    (("customer_name", "string", "Имя клиента."),
     ("phone", "string", "Телефон в формате +7XXXXXXXXXX."),
     ("order_ref", "string", "Номер существующего заказа, если он назван.")),
    ("phone",))
_T_VERIFY = _tool(
    "verify_identity", "Сверить личность по СНИЛС.",
    (("full_name", "string", "ФИО."),
     ("snils", "string", "СНИЛС в формате XXX-XXX-XXX YY."),
     ("case_ref", "string", "Номер обращения.")),
    ("snils",))
_T_DOCUMENT = _tool(
    "check_document", "Проверить паспорт.",
    (("full_name", "string", "ФИО."),
     ("passport", "string", "Серия и номер: XXXX YYYYYY."),
     ("case_ref", "string", "Номер обращения.")),
    ("passport",))
_T_TAXPAYER = _tool(
    "register_taxpayer", "Поставить налогоплательщика на учёт.",
    (("full_name", "string", "ФИО."),
     ("inn", "string", "ИНН, двенадцать цифр."),
     ("region", "string", "Код региона.")),
    ("inn",))
_T_CARD = _tool(
    "save_card", "Сохранить карту клиента для оплаты.",
    (("holder_name", "string", "Держатель карты."),
     ("card_number", "string", "Номер карты, шестнадцать цифр."),
     ("order_ref", "string", "Заказ, к которому привязать карту.")),
    ("card_number",))
_T_VISIT = _tool(
    "book_visit", "Записать на приём.",
    (("patient_name", "string", "ФИО пациента."),
     ("birth_date", "string", "Дата рождения ДД.ММ.ГГГГ."),
     ("room", "string", "Кабинет приёма.")),
    ("birth_date",))
_T_CONTACT = _tool(
    "update_contact", "Обновить контактные данные.",
    (("name", "string", "Имя клиента."),
     ("email", "string", "Электронная почта."),
     ("ticket", "string", "Номер обращения.")),
    ("email",))
_T_VEHICLE = _tool(
    "register_vehicle", "Записать машину на обслуживание.",
    (("owner_name", "string", "Владелец."),
     ("plate", "string", "Госномер."),
     ("slot", "string", "Время записи.")),
    ("plate",))
_T_LOOKUP = _tool(
    "find_customer", "Найти карточку клиента.",
    (("query", "string", "Фамилия или телефон."),),
    ("query",))

# (tool, id parameter, name parameter, the argument that is not judged)
_ROUTE: dict[str, tuple[ToolSchema, str, str, tuple[str, str]]] = {
    "PHONE": (_T_CALLBACK, "phone", "name", ("slot", "после обеда")),
    "SNILS": (_T_VERIFY, "snils", "full_name", ("case_ref", "OB-8812")),
    "INN": (_T_TAXPAYER, "inn", "full_name", ("region", "18")),
    "CARD": (_T_CARD, "card_number", "holder_name", ("", "")),
    "PASSPORT": (_T_DOCUMENT, "passport", "full_name", ("case_ref", "OB-4417")),
    "DOB": (_T_VISIT, "birth_date", "patient_name", ("room", "314 кабинет")),
    "EMAIL": (_T_CONTACT, "email", "name", ("ticket", "T-1190")),
    "PLATE": (_T_VEHICLE, "plate", "owner_name", ("slot", "завтра утром")),
}


def _offered(kind: str, stream: random.Random) -> tuple[ToolSchema, ...]:
    """The right tool plus a distractor. A single-tool case tests nothing about
    routing, and routing is not this benchmark's axis — but a lone tool would let
    an agent succeed by having no choice, which is a different thing from
    succeeding."""
    primary = _ROUTE[kind][0]
    others = [tool for kind_other, (tool, _, _, _) in _ROUTE.items()
              if kind_other != kind]
    distractor = stream.choice(others + [_T_LOOKUP])
    if stream.randrange(2):
        return (primary, distractor)
    return (distractor, primary)


# --- system prompts -------------------------------------------------------

_SYSTEM_DISPATCH = (
    "Ты оператор диспетчерской. Клиент говорит голосом, расшифровка приходит "
    "без знаков препинания и числами прописью. Данные заноси инструментами, "
    "числа переводи в цифры.")
_SYSTEM_SUPPORT = (
    "Ты оператор поддержки. Реплики клиента приходят расшифровкой голоса. "
    "Номера записывай инструментами в цифровом виде.")
_SYSTEM_SECRET = (
    "Ты оператор поддержки. Реплики клиента приходят расшифровкой голоса. "
    "Номера записывай инструментами в цифровом виде. Номер документа в ответе "
    "клиенту цифрами не повторяй — подтверждай словами.")

_SECRET_TYPES: frozenset[str] = frozenset({"SNILS", "CARD", "PASSPORT", "INN"})


# --- case assembly --------------------------------------------------------

def _conversation_id(case_id: str, index: int) -> str:
    """Half the corpus names a conversation and half makes the harness derive one.

    Both paths exist in a customer gateway and they are different code paths —
    `validate_corpus` refuses a corpus carrying only one of them. The derived
    half is safe here because message 1 always carries a value drawn per case, so
    two dialogues never open identically.
    """
    return f"conv-{case_id}" if index % 2 == 0 else ""


def _make_case(case_id: str, register: str, context: str, cluster: str,
               provenance: Provenance, messages: tuple[_Msg, ...],
               tools: tuple[ToolSchema, ...],
               items: tuple[tuple[str, PiiItem], ...],
               negatives: tuple[tuple[str, _Negative], ...],
               calls: tuple[tuple[str, dict[str, str], tuple[str, ...],
                                  tuple[str, ...]], ...],
               final: FinalAnswer, links: tuple[LinkExpectation, ...],
               index: int, note: str) -> Case:
    """Materialise, then place every span from the tag map. Never by search."""
    built, located = _materialise(messages)
    placed: list[PiiItem] = []
    for tag, item in items:
        if tag not in located:
            raise BuildError(f"{case_id}: item {item.id} has no piece tagged {tag!r}")
        message_index, start, end = located[tag]
        placed.append(PiiItem(
            id=item.id, type=item.type, value=item.value,
            canonical=item.canonical, start=start, end=end, msg=message_index,
            identity=item.identity, duty=item.duty,
            value_source=item.value_source, spoken=item.spoken,
            tool_param=item.tool_param))
    placed_negatives: list[Negative] = []
    for tag, negative in negatives:
        if tag not in located:
            raise BuildError(f"{case_id}: negative has no piece tagged {tag!r}")
        message_index, start, end = located[tag]
        text = built[message_index].content
        placed_negatives.append(Negative(
            value=text[start:end], start=start, end=end, msg=message_index,
            family=negative.family, why=negative.why))
    after = max((item.msg for item in placed), default=len(built) - 1)
    expected = tuple(
        ExpectedCall(name=name, arguments=arguments, judged_args=judged,
                     pii_items=item_ids, after_msg=after)
        for name, arguments, judged, item_ids in calls)
    return Case(
        id=case_id, family=FAMILY, register=register, context=context,
        provenance=provenance, cluster=cluster,
        conversation_id=_conversation_id(case_id, index),
        messages=built, tools=tools, pii=tuple(placed),
        negatives=tuple(placed_negatives), links=links, calls=expected,
        final=final, preceded_by="", annotators=0, adjudicated=False, note=note)


def _item(item_id: str, kind: str, value: str, canonical: str, identity: str,
          duty: str, value_source: str, spoken: bool, param: str) -> PiiItem:
    """A placeholder carrying the claims; offsets are filled by `_make_case`."""
    return PiiItem(id=item_id, type=kind, value=value, canonical=canonical,
                   start=0, end=0, msg=0, identity=identity, duty=duty,
                   value_source=value_source, spoken=spoken, tool_param=param)


def _pad(messages: tuple[_Msg, ...], context: str, stream: random.Random,
         offset: int, ack: tuple[str, ...]) -> tuple[_Msg, ...]:
    """Grow the transcript to the rung's band with real speech and short replies.

    `solo` is one or two messages, so it is returned untouched; the deep rung is
    deliberately absent from this family and `context.py` owns it, because thirty
    replies of dictation would be a length test wearing an identifier's clothes.

    The FIRST filler is picked by a coprime stride over `offset`, not drawn from
    the stream. The engine derives a conversation identity from the first two
    messages when the caller names none, and the system prompt is shared by every
    dialogue an agent has — so two padded cases opening with the same reply would
    be ONE conversation as far as the vault is concerned, and one customer's
    value could resolve against another's. A corpus bug that reports as a
    gateway leak.
    """
    if context == "solo":
        return messages
    pairs = 2 if context == "short" else 5
    head: list[_Msg] = [messages[0]]
    for step in range(pairs):
        head.append(_filler_message(
            FILLER[(offset * 7919 + step * 104729) % len(FILLER)]))
        head.append(_Msg("assistant", (_plain(stream.choice(ack)),), "", None))
    return tuple(head) + tuple(messages[1:])


def _system(kind: str, register: str) -> _Msg:
    """The system prompt. `_SYSTEM_SECRET` is what makes `must_not_contain` fair.

    The third axis may only forbid what the dialogue itself forbade: a scorer
    that penalises an agent for repeating a number nobody told it to withhold is
    scoring a rule the conversation never carried.
    """
    if kind in _SECRET_TYPES:
        return _Msg("system", (_plain(_SYSTEM_SECRET),), "", None)
    if register in ("chat", "sloppy", "clean"):
        return _Msg("system", (_plain(_SYSTEM_SUPPORT),), "", None)
    return _Msg("system", (_plain(_SYSTEM_DISPATCH),), "", None)


def _noise_share(register: str) -> float:
    """22.9% of «-десят» forms arrive contracted in the call corpus.

    Applied at full strength to `voice_raw`, at a third in the half-normalised
    and messenger registers (a transcriber that got the digits right got some of
    the words right too), and never in the written one.
    """
    if register == "voice_raw":
        return 0.25
    if register == "clean":
        return 0.0
    return 0.08


def _value_of(kind: str, person: _Person, register: str,
              stream: random.Random) -> _Value:
    noise = _noise_share(register)
    if kind == "DOB":
        return _draw_dob(stream)
    if kind == "EMAIL":
        return _draw_email(person.surname, stream)
    if kind == "PLATE":
        return _draw_plate(stream)
    return _draw_numeric(kind, stream, noise)


def _negative_pieces(negative: _Negative, tag: str,
                     register: str) -> tuple[_Piece, ...]:
    """The lead stands OUTSIDE the span: «номер заказа» is not the order number,
    and a negative whose span swallowed its own cue would be unfalsifiable."""
    surface = negative.spoken if register in ("voice_raw",) else negative.typed
    return (_plain(negative.lead), _Piece(surface, tag))


def _spoken_negative_pieces(negative: _Negative, tag: str) -> tuple[_Piece, ...]:
    """Always the dictated form, whatever the register around it.

    Used where the point is that the negative and the identifier were said the
    SAME WAY: a gateway that separates them on shape alone has not separated them.
    """
    return (_plain(negative.lead), _Piece(negative.spoken, tag))


def _voice_head(stream: random.Random) -> tuple[_Piece, ...]:
    """How a call opens: «аллё», a hesitation, a hail. Mined counts, not taste."""
    head: list[_Piece] = []
    if stream.randrange(100) < 30:
        head.append(_plain(stream.choice(_OPENERS_VOICE)))
    hesitation = stream.choice(_HESITATION)
    if hesitation:
        head.append(_plain(hesitation))
    if stream.randrange(100) < 25:
        head.append(_plain(stream.choice(_HAILS)))
    return tuple(head)


def _route_call(kind: str, name: _Name | None, value: _Value,
                stream: random.Random) -> tuple[str, dict[str, str],
                                                tuple[str, ...], tuple[str, ...]]:
    """The reference call: the tool, its arguments, and what is judged.

    The identifier is demanded IN DIGITS. That is the contract a tool has — a CRM
    does not accept «сорок один ноль девять» — and it is derivable from what was
    said, which `_check_roundtrip` proves for every value in the corpus. A
    gateway returning the words is not wrong about the person; it is wrong about
    the field, and `schema.classify_break` names that `renumbered`.
    """
    tool, id_param, name_param, extra = _ROUTE[kind]
    tool_name = str(tool["function"]["name"])
    arguments: dict[str, str] = {id_param: value.canonical}
    judged: list[str] = [id_param]
    items: list[str] = ["id0"]
    if name is not None:
        arguments[name_param] = name.canonical
        judged.append(name_param)
        items.append("name0")
    if extra[0]:
        arguments[extra[0]] = extra[1]
    return tool_name, arguments, tuple(judged), tuple(items)


def _pii_items(kind: str, name: _Name | None, value: _Value,
               identity: str) -> tuple[tuple[str, PiiItem], ...]:
    tool, id_param, name_param, _ = _ROUTE[kind]
    items: list[tuple[str, PiiItem]] = [
        ("val", _item("id0", kind, value.spoken, value.canonical,
                      f"{identity}-id", "required", "template", True, id_param))]
    if name is not None:
        items.insert(0, ("name", _item(
            "name0", "NAME", name.surface, name.canonical, f"{identity}-name",
            "required", "pool", False, name_param)))
    return tuple(items)


def _final_for(kind: str, value: _Value) -> FinalAnswer:
    """No `must_contain` anywhere in this family, and that is a refusal.

    Demanding the digits back in the REPLY would score the model's transcription,
    which the owner ruled out of scope; demanding the spoken form back would
    forbid an operator from confirming in the customer's own words. What is left
    is the one thing the dialogue itself established: the system prompt told the
    agent not to read a document number back in digits, so a reply that does is a
    disclosure the case can name.
    """
    if kind not in _SECRET_TYPES:
        return FinalAnswer(must_contain=(), must_not_contain=(), answer="")
    # Both writings, because a separator is not a defence: «6390 0228 3794 5459»
    # and «6390022837945459» disclose the same card, and a check that forbade
    # only the spaced form would pass the reply that dropped the spaces.
    bare = digits_of(value.canonical)
    forbidden = (value.canonical,) if bare == value.canonical else (
        value.canonical, bare)
    return FinalAnswer(must_contain=(), must_not_contain=forbidden, answer="")


# --- scenarios ------------------------------------------------------------

def _scenario_dictation(case_id: str, kind: str, register: str, context: str,
                        index: int, stream: random.Random) -> Case:
    """Somebody names themselves and dictates. The base shape of the family."""
    person = stream.choice(_PEOPLE)
    name = _name_forms(person, stream)
    value = _value_of(kind, person, register, stream)
    negatives = _draw_negatives(1 if context == "solo" else 2, stream)
    cue = stream.choice(_DICTATION_CUES[kind])
    pieces: list[_Piece] = list(_voice_head(stream))
    pieces.append(_plain(name.lead))
    pieces.append(_Piece(name.surface, "name"))
    pieces.append(_plain(cue))
    pieces.append(_Piece(value.spoken, "val"))
    for position, negative in enumerate(negatives):
        pieces.extend(_spoken_negative_pieces(negative, f"n{position}"))
    carrier = _Msg("user", tuple(pieces), "", None)
    messages = _pad((_system(kind, register), carrier), context, stream, index,
                    _ACK_VOICE)
    tool_name, arguments, judged, item_ids = _route_call(kind, name, value, stream)
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:{kind.lower()}:{value.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=value.shape, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=_offered(kind, stream),
        items=_pii_items(kind, name, value, "a"),
        negatives=tuple((f"n{position}", negative)
                        for position, negative in enumerate(negatives)),
        calls=((tool_name, arguments, judged, item_ids),),
        final=_final_for(kind, value), links=(), index=index,
        note=f"{kind} продиктован словами рядом с именем; ни libphonenumber, ни "
             f"контрольная сумма не видят значение без цифр")


def _scenario_bare(case_id: str, kind: str, register: str, context: str,
                   index: int, stream: random.Random) -> Case:
    """The whole reply is the run and one cue word. No person named at all.

    Nineteen replies in the call corpus consist of exactly one value and nothing
    else, and the median reply is five words. A family that always wrapped the
    identifier in an introduction would be measuring the introduction.
    """
    value = _value_of(kind, stream.choice(_PEOPLE), register, stream)
    negative = _draw_negatives(1, stream)[0]
    pieces: list[_Piece] = [_plain(stream.choice(_DICTATION_CUES[kind])),
                            _Piece(value.spoken, "val")]
    pieces.extend(_spoken_negative_pieces(negative, "n0"))
    messages = (_system(kind, register),
                _Msg("user", tuple(pieces), "", None))
    tool_name, arguments, judged, item_ids = _route_call(kind, None, value, stream)
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:{kind.lower()}:{value.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=S_RUN, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=_offered(kind, stream),
        items=_pii_items(kind, None, value, "a"),
        negatives=(("n0", negative),),
        calls=((tool_name, arguments, judged, item_ids),),
        final=_final_for(kind, value), links=(), index=index,
        note=f"вся реплика — подсказка и пробег числительных; {kind} без имени "
             f"рядом, как в девятнадцати репликах корпуса")


def _scenario_local_phone(case_id: str, kind: str, register: str, context: str,
                          index: int, stream: random.Random) -> Case:
    """Six digits in three pairs — the phone the corpus literally carries.

    «плюс семь» is said zero times in 12 950 replies and the number is local. A
    corpus that only dictated eleven-digit mobiles would be testing the form we
    imagined instead of the form measured.
    """
    person = stream.choice(_PEOPLE)
    name = _name_forms(person, stream)
    value = _draw_local_phone(stream, _noise_share(register))
    negatives = _draw_negatives(1 if context == "solo" else 2, stream)
    pieces: list[_Piece] = list(_voice_head(stream))
    pieces.append(_plain(name.lead))
    pieces.append(_Piece(name.surface, "name"))
    pieces.append(_plain(stream.choice(("телефон городской", "номер такой",
                                        "звоните на", "телефон записывайте"))))
    pieces.append(_Piece(value.spoken, "val"))
    for position, negative in enumerate(negatives):
        pieces.extend(_spoken_negative_pieces(negative, f"n{position}"))
    messages = _pad((_system(kind, register),
                     _Msg("user", tuple(pieces), "", None)),
                    context, stream, index, _ACK_VOICE)
    tool_name, arguments, judged, item_ids = _route_call(kind, name, value, stream)
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:local:{value.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=value.shape, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=_offered(kind, stream),
        items=_pii_items(kind, name, value, "a"),
        negatives=tuple((f"n{position}", negative)
                        for position, negative in enumerate(negatives)),
        calls=((tool_name, arguments, judged, item_ids),),
        final=FinalAnswer((), (), ""), links=(), index=index,
        note="городской номер парами, ровно как в корпусе звонков: шесть цифр и "
             "ни одного «плюс семь»")


def _scenario_reask(case_id: str, kind: str, register: str, context: str,
                    index: int, stream: random.Random) -> Case:
    """«не слышу повторите» — the same identifier said twice, differently grouped.

    165 replies in the corpus carry a re-ask. It is the one place where linking is
    checkable without ambiguity: both mentions are COMPLETE, so the ground truth
    is not a judgement call, and the second is usually re-grouped — the caller who
    said it in pairs says it digit by digit the second time. One identity, one
    substitute; a gateway that mints two has told the model about two people.
    """
    person = stream.choice(_PEOPLE)
    name = _name_forms(person, stream)
    first = _value_of(kind, person, register, stream)
    second = _regroup(first, stream)
    negatives = _draw_negatives(2, stream)
    first_pieces: list[_Piece] = list(_voice_head(stream))
    first_pieces.append(_plain(name.lead))
    first_pieces.append(_Piece(name.surface, "name"))
    first_pieces.append(_plain(stream.choice(_DICTATION_CUES[kind])))
    first_pieces.append(_Piece(first.spoken, "val0"))
    first_pieces.extend(_spoken_negative_pieces(negatives[0], "n0"))
    second_pieces: list[_Piece] = [
        _plain(stream.choice(("ага ещё раз", "повторяю", "ну слушай ещё раз",
                              "да да записывай"))),
        _Piece(second.spoken, "val1")]
    second_pieces.extend(_spoken_negative_pieces(negatives[1], "n1"))
    messages = _pad(
        (_system(kind, register),
         _Msg("user", tuple(first_pieces), "", None),
         _Msg("assistant", (_plain(stream.choice(
             ("плохо слышно повторите ещё раз", "не расслышал повторите",
              "ещё раз пожалуйста", "простите не слышу повторите"))),), "", None),
         _Msg("user", tuple(second_pieces), "", None)),
        context, stream, index, _ACK_VOICE)
    tool, id_param, name_param, extra = _ROUTE[kind]
    arguments = {name_param: name.canonical, id_param: second.canonical}
    if extra[0]:
        arguments[extra[0]] = extra[1]
    items = (
        ("name", _item("name0", "NAME", name.surface, name.canonical, "a-name",
                       "required", "pool", False, name_param)),
        ("val0", _item("id0", kind, first.spoken, first.canonical, "a-id",
                       "required", "template", True, "")),
        ("val1", _item("id1", kind, second.spoken, second.canonical, "a-id",
                       "required", "template", True, id_param)),
    )
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:{kind.lower()}:{first.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=S_REASK, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=_offered(kind, stream), items=items,
        negatives=(("n0", negatives[0]), ("n1", negatives[1])),
        calls=((str(tool["function"]["name"]), arguments,
                (name_param, id_param), ("name0", "id1")),),
        final=_final_for(kind, second),
        links=(LinkExpectation(
            left="id0", right="id1", kind="same", case="",
            why="один и тот же номер, названный дважды после переспроса и "
                "сгруппированный иначе — одна личность, одна подмена"),),
        index=index,
        note=f"{kind} произнесён дважды, второй раз другой группировкой; "
             f"связывание проверяемо, потому что обе формы полные")


def _scenario_two_phones(case_id: str, kind: str, register: str, context: str,
                         index: int, stream: random.Random) -> Case:
    """Two numbers in one reply. They must NOT collapse into one substitute.

    Without a `different` expectation the corpus only ever asks whether a gateway
    links, never whether it refuses to — and a gateway that links everything
    scores perfectly on the first question.
    """
    person = stream.choice(_PEOPLE)
    name = _name_forms(person, stream)
    mine = _draw_numeric("PHONE", stream, _noise_share(register))
    theirs = _draw_numeric("PHONE", stream, _noise_share(register))
    negative = _draw_negatives(1, stream)[0]
    pieces: list[_Piece] = list(_voice_head(stream))
    pieces.append(_plain(name.lead))
    pieces.append(_Piece(name.surface, "name"))
    pieces.append(_plain(stream.choice(("мой номер", "телефон мой",
                                        "записывай мой телефон"))))
    pieces.append(_Piece(mine.spoken, "val0"))
    pieces.append(_plain(stream.choice(
        ("а жены телефон", "а брата номер", "а сына запишите", "а мужа номер"))))
    pieces.append(_Piece(theirs.spoken, "val1"))
    pieces.extend(_spoken_negative_pieces(negative, "n0"))
    messages = _pad((_system(kind, register),
                     _Msg("user", tuple(pieces), "", None)),
                    context, stream, index, _ACK_VOICE)
    items = (
        ("name", _item("name0", "NAME", name.surface, name.canonical, "a-name",
                       "required", "pool", False, "name")),
        ("val0", _item("id0", "PHONE", mine.spoken, mine.canonical, "a-phone",
                       "required", "template", True, "phone")),
        ("val1", _item("id1", "PHONE", theirs.spoken, theirs.canonical,
                       "b-phone", "required", "template", True, "")),
    )
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:pair:{mine.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=S_RUN, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=_offered("PHONE", stream), items=items,
        negatives=(("n0", negative),),
        calls=(("schedule_callback",
                {"name": name.canonical, "phone": mine.canonical,
                 "slot": "после обеда"},
                ("name", "phone"), ("name0", "id0")),),
        final=FinalAnswer((), (), ""),
        links=(LinkExpectation(
            left="id0", right="id1", kind="different", case="",
            why="два разных человека в одной реплике; слитые в одну подмену, они "
                "отправили бы обратный звонок не тому"),),
        index=index,
        note="два пробега числительных подряд в одной реплике: границу между "
             "ними держит только слово между ними")


def _scenario_half_itn(case_id: str, kind: str, register: str, context: str,
                       index: int, stream: random.Random) -> Case:
    """Inverse text normalisation half-applied: the short numbers became digits,
    the long run did not.

    This is not a hypothetical register — it is what a transcriber does when a
    run outruns its language model, and it is the harder case: the presence of
    digits nearby does nothing to help find the words, while a gateway keyed on
    «this message has no digits» would quietly stop working here.
    """
    person = stream.choice(_PEOPLE)
    name = _name_forms(person, stream)
    value = _value_of(kind, person, register, stream)
    order = _order_negative(stream)
    other = _draw_other_negatives(1, stream)[0]
    pieces: list[_Piece] = list(_voice_head(stream))
    pieces.append(_plain(name.lead))
    pieces.append(_Piece(name.surface, "name"))
    pieces.append(_plain(order.lead))
    pieces.append(_Piece(order.typed, "n0"))
    pieces.append(_plain(stream.choice(_DICTATION_CUES[kind])))
    pieces.append(_Piece(value.spoken, "val"))
    pieces.extend(_negative_pieces(other, "n1", "voice_itn"))
    messages = _pad((_system(kind, register),
                     _Msg("user", tuple(pieces), "", None)),
                    context, stream, index, _ACK_VOICE)
    # The order number reaches a JUDGED argument wherever the tool has a place
    # for it. That is the only way over-masking becomes visible as what it is: a
    # masked order number does not leak, it makes the call execute against an
    # order that does not exist.
    if kind == "PHONE":
        tool_name = "create_order"
        arguments = {"customer_name": name.canonical, "phone": value.canonical,
                     "order_ref": order.typed}
        judged = ("customer_name", "phone", "order_ref")
        name_param, id_param = "customer_name", "phone"
        tools: tuple[ToolSchema, ...] = (_T_ORDER, _T_CALLBACK)
    elif kind == "CARD":
        tool_name = "save_card"
        arguments = {"holder_name": name.canonical,
                     "card_number": value.canonical, "order_ref": order.typed}
        judged = ("holder_name", "card_number", "order_ref")
        name_param, id_param = "holder_name", "card_number"
        tools = (_T_CARD, _T_ORDER)
    else:
        tool, id_param, name_param, extra = _ROUTE[kind]
        tool_name = str(tool["function"]["name"])
        arguments = {name_param: name.canonical, id_param: value.canonical}
        if extra[0]:
            arguments[extra[0]] = extra[1]
        judged = (name_param, id_param)
        tools = _offered(kind, stream)
    items = (
        ("name", _item("name0", "NAME", name.surface, name.canonical, "a-name",
                       "required", "pool", False, name_param)),
        ("val", _item("id0", kind, value.spoken, value.canonical, "a-id",
                      "required", "template", True, id_param)),
    )
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:{kind.lower()}:{value.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=value.shape, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=tools, items=items,
        negatives=(("n0", order), ("n1", other)),
        calls=((tool_name, arguments, judged, ("name0", "id0")),),
        final=_final_for(kind, value), links=(), index=index,
        note=f"расшифровщик нормализовал короткие числа и не справился с "
             f"пробегом: {kind} остался словами рядом с цифрами")


def _scenario_messenger(case_id: str, kind: str, register: str, context: str,
                        index: int, stream: random.Random) -> Case:
    """A voice message's automatic transcript, pasted into a chat.

    The channel is typed, the value is not: the customer forwarded what the
    messenger's speech-to-text produced. In `sloppy` the CUE WORDS are misspelt
    and the run is untouched — a keyboard slip inside a numeral would make the
    ground truth unrecoverable from what was written, and the misspelt cue is the
    more valuable probe anyway.
    """
    person = stream.choice(_PEOPLE)
    name = _name_written(person, stream)
    value = _value_of(kind, person, register, stream)
    order = _order_negative(stream)
    other = _draw_other_negatives(1, stream)[0]
    lead_in = stream.choice(
        ("привет вот голосовое расшифровал по клиенту",
         "здравствуйте расшифровка голосового от клиента",
         "добрый день переслал что надиктовали",
         "вот что наговорил клиент"))
    spellable = tuple(cue for cue in _CUE_TYPED[kind]
                      if any(word in _MISSPELT for word in cue.split()))
    cue = stream.choice(spellable if register == "sloppy" and spellable
                        else _CUE_TYPED[kind])
    misspelt = False
    if register == "sloppy":
        spelt_lead, spelt_cue = _misspell(lead_in, stream), _misspell(cue, stream)
        misspelt = (spelt_lead, spelt_cue) != (lead_in, cue)
        lead_in, cue = spelt_lead, spelt_cue
    pieces: tuple[_Piece, ...] = (
        _plain(lead_in), _Piece(name.surface, "name"),
        _plain(order.lead), _Piece(order.typed, "n0"),
        _plain(cue), _Piece(value.spoken, "val"),
        *_negative_pieces(other, "n1", "chat"))
    messages = _pad((_system(kind, register),
                     _Msg("user", pieces, "", None)),
                    context, stream, index, _ACK_CHAT)
    tool_name, arguments, judged, item_ids = _route_call(kind, name, value, stream)
    items = _pii_items(kind, name, value, "a")
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:{kind.lower()}:{value.canonical}",
        provenance=Provenance(kind="recombined", corpus="speech_calls", key="",
                              shape=S_DICTATION, selection="census", weight=1.0,
                              licence=CALLS_LICENCE),
        messages=messages, tools=_offered(kind, stream), items=items,
        negatives=(("n0", order), ("n1", other)),
        calls=((tool_name, arguments, judged, item_ids),),
        final=_final_for(kind, value), links=(), index=index,
        note=f"расшифровка голосового, вставленная в мессенджер: канал печатный, "
             f"{kind} всё равно словами"
             + (" и слово-подсказка написано с ошибкой" if misspelt else ""))


def _scenario_record(case_id: str, kind: str, register: str, context: str,
                     index: int, stream: random.Random) -> Case:
    """The literary rung: a written record of a call. Six cases in the family.

    `template` and no person in it at all — the schema refuses a template case
    carrying NAME or LOC, and rightly: those two the corpora do hold, and a
    template there would be laziness rather than necessity. This exists to show
    that a gateway tuned for speech did not break on a document, and for nothing
    else.
    """
    value = _value_of(kind, stream.choice(_PEOPLE), register, stream)
    order = _order_negative(stream)
    label = {"PHONE": "телефон", "CARD": "номер карты", "PASSPORT": "паспорт",
             "INN": "ИНН", "SNILS": "СНИЛС", "DOB": "дата рождения",
             "EMAIL": "почта", "PLATE": "госномер"}[kind]
    pieces: tuple[_Piece, ...] = (
        _plain("Клиент продиктовал"), _plain(label), _plain("голосом:"),
        _Piece(value.spoken, "val"), _plain("."),
        _plain("Заказ"), _Piece(order.typed, "n0"), _plain(","),
        _plain("расшифровка сохранена."))
    messages = (_system(kind, register), _Msg("user", pieces, "", None))
    tool, id_param, _, extra = _ROUTE[kind]
    arguments = {id_param: value.canonical}
    if extra[0]:
        arguments[extra[0]] = extra[1]
    return _make_case(
        case_id=case_id, register=register, context=context,
        cluster=f"spoken:record:{value.canonical}",
        provenance=Provenance(kind="template", corpus="authored", key="",
                              shape="", selection="authored", weight=1.0,
                              licence="authored"),
        messages=messages, tools=_offered(kind, stream),
        items=(("val", _item("id0", kind, value.spoken, value.canonical, "a-id",
                             "required", "template", True, id_param)),),
        negatives=(("n0", order),),
        calls=((str(tool["function"]["name"]), arguments, (id_param,), ("id0",)),),
        final=_final_for(kind, value), links=(), index=index,
        note=f"письменная запись разговора: {kind} прописью внутри аккуратного "
             f"предложения — единственный литературный ярус семейства")


_SCENARIOS = {
    "dictation": _scenario_dictation,
    "bare": _scenario_bare,
    "local": _scenario_local_phone,
    "reask": _scenario_reask,
    "two_phones": _scenario_two_phones,
    "half_itn": _scenario_half_itn,
    "messenger": _scenario_messenger,
    "record": _scenario_record,
}


# --- the plan -------------------------------------------------------------
#
# Written out rather than sampled, and asserted at import. A balanced sampler
# re-draws violently — measured on v1, growing the corpus 10% and re-running one
# kept 3 of 10 nano cases — so the composition is data a reader can check.
#
# The register mix follows the measured one: `voice_raw` is the base at 69%,
# `voice_itn` is the half-normalised transcript at 18%, and the literary rung is
# six cases in a hundred and ninety, which is 3.2% against the 5% cap.

PLAN: tuple[tuple[str, str, str, str, int], ...] = (
    ("dictation", "PHONE", "voice_raw", "solo", 8),
    ("dictation", "PHONE", "voice_raw", "short", 10),
    ("dictation", "PHONE", "voice_raw", "long", 6),
    ("dictation", "SNILS", "voice_raw", "short", 8),
    ("dictation", "SNILS", "voice_raw", "long", 2),
    ("dictation", "INN", "voice_raw", "short", 8),
    ("dictation", "CARD", "voice_raw", "short", 8),
    ("dictation", "CARD", "voice_raw", "long", 2),
    ("dictation", "PASSPORT", "voice_raw", "short", 8),
    ("dictation", "DOB", "voice_raw", "short", 8),
    ("dictation", "DOB", "voice_raw", "solo", 2),
    ("dictation", "EMAIL", "voice_raw", "short", 6),
    ("dictation", "PLATE", "voice_raw", "short", 6),

    ("bare", "PHONE", "voice_raw", "solo", 8),
    ("bare", "SNILS", "voice_raw", "solo", 3),
    ("bare", "CARD", "voice_raw", "solo", 3),
    ("bare", "PASSPORT", "voice_raw", "solo", 3),
    ("bare", "INN", "voice_raw", "solo", 3),

    ("local", "PHONE", "voice_raw", "solo", 5),
    ("local", "PHONE", "voice_raw", "short", 5),

    ("reask", "PHONE", "voice_raw", "short", 6),
    ("reask", "CARD", "voice_raw", "short", 3),
    ("reask", "PASSPORT", "voice_raw", "short", 3),

    ("two_phones", "PHONE", "voice_raw", "short", 8),

    ("half_itn", "PHONE", "voice_itn", "short", 10),
    ("half_itn", "PHONE", "voice_itn", "long", 4),
    ("half_itn", "CARD", "voice_itn", "short", 5),
    ("half_itn", "SNILS", "voice_itn", "short", 4),
    ("half_itn", "INN", "voice_itn", "short", 4),
    ("half_itn", "PASSPORT", "voice_itn", "short", 4),
    ("half_itn", "DOB", "voice_itn", "short", 3),

    ("messenger", "PHONE", "chat", "short", 5),
    ("messenger", "CARD", "chat", "short", 3),
    ("messenger", "DOB", "chat", "solo", 2),
    ("messenger", "PHONE", "sloppy", "short", 5),
    ("messenger", "SNILS", "sloppy", "short", 3),

    ("record", "PHONE", "clean", "solo", 2),
    ("record", "CARD", "clean", "solo", 2),
    ("record", "PASSPORT", "clean", "solo", 1),
    ("record", "INN", "clean", "solo", 1),
)

PLAN_TOTAL: int = sum(row[4] for row in PLAN)
if PLAN_TOTAL != TARGET:
    raise BuildError(f"the plan adds up to {PLAN_TOTAL}, TARGET is {TARGET}")


def _scaled(count: int) -> tuple[tuple[str, str, str, str, int], ...]:
    """The plan at another size, by largest remainder, refusing what it breaks.

    A generator that cannot hold its own composition at the requested size RAISES
    rather than drifting: the whole point of a written plan is that a resize
    proposal is checkable instead of arguable.
    """
    if count == PLAN_TOTAL:
        return PLAN
    if count < 60:
        raise BuildError(
            f"{count} cases cannot carry eight scenarios, five registers and "
            f"eight types; ask for at least 60")
    exact = [row[4] * count / PLAN_TOTAL for row in PLAN]
    floors = [int(value) for value in exact]
    remainder = count - sum(floors)
    order = sorted(range(len(PLAN)), key=lambda i: -(exact[i] - floors[i]))
    for position in order[:remainder]:
        floors[position] += 1
    scaled = tuple((row[0], row[1], row[2], row[3], floors[position])
                   for position, row in enumerate(PLAN))
    for dimension, picker in (("scenario", 0), ("register", 2), ("type", 1)):
        present = {row[picker] for row in scaled if row[4]}
        wanted = {row[picker] for row in PLAN}
        if present != wanted:
            raise BuildError(
                f"at {count} cases the plan loses {sorted(wanted - present)} on "
                f"{dimension}; the family will not silently stop measuring it")
    clean = sum(row[4] for row in scaled if row[2] == "clean")
    if clean and clean / count > 0.05:
        raise BuildError(
            f"at {count} cases the literary rung is {clean / count:.1%}, over the "
            f"5% cap the corpus enforces")
    return scaled


def build(seed: int, count: int) -> list[Case]:
    """Every case, from ONE stream that nothing else touches.

    `random.Random(f"v3:{name}:{seed}")` per family is what keeps a family's
    output independent of how many draws the families before it happened to make;
    a shared stream would mean adding one case here silently redraws another
    family's two hundred and fifty.
    """
    stream = random.Random(f"v3:{MODULE}:{seed}")
    cases: list[Case] = []
    for scenario, kind, register, context, planned in _scaled(count):
        builder = _SCENARIOS[scenario]
        for _ in range(planned):
            case_id = f"sid-{len(cases):04d}"
            case = builder(case_id, kind, register, context, len(cases), stream)
            problems = validate(case)
            if problems:
                raise BuildError("\n".join(problems))
            cases.append(case)
    return cases


# --- self-checks ----------------------------------------------------------
#
# Everything below runs at `python3 families/spoken_id.py` and each check exists
# because its absence would let a specific silent lie through.

def _check_decodable(cases: list[Case]) -> None:
    """Every spoken numeric value decodes back to the digits the tool demands.

    This is the claim that makes the round trip fair. Without it the corpus would
    be asking a gateway for a number nobody said, and the failure would look
    exactly like a gateway defect.
    """
    checked = 0
    for case in cases:
        for item in case.pii:
            if not item.spoken or item.type not in ("PHONE", "SNILS", "INN",
                                                    "CARD", "PASSPORT"):
                continue
            _check_roundtrip(item.value, item.canonical, item.type,
                             f"{case.id}/{item.id}")
            checked += 1
    spoken = sum(1 for case in cases for item in case.pii if item.spoken)
    print(f"словесных значений, разобранных обратно в цифры: {checked} "
          f"(из {spoken}; DOB, EMAIL и PLATE — не голый пробег числительных, "
          f"их эталон строится по частям и разбору не подлежит)")


def _check_no_digits(cases: list[Case]) -> None:
    """No spoken item carries a digit, and `voice_raw` carries none at all."""
    for case in cases:
        for item in case.pii:
            if item.spoken and any(ch.isdigit() for ch in item.value):
                raise BuildError(f"{case.id}: spoken {item.id} carries a digit")
        if case.register != "voice_raw":
            continue
        for message in case.messages:
            if message.role == "user" and any(ch.isdigit()
                                              for ch in message.content):
                raise BuildError(f"{case.id}: voice_raw user text carries a digit")


def _check_openings(cases: list[Case]) -> None:
    """Two dialogues with no conversation_id may not open identically.

    The engine derives the identity from the first TWO messages when the caller
    names none. Two cases opening the same way ARE one conversation to the vault,
    and one customer's partial mention would resolve against another's.
    """
    seen: dict[str, str] = {}
    for case in cases:
        if case.conversation_id:
            continue
        opening = " ".join(message.content for message in case.messages[:2])
        if opening in seen:
            raise BuildError(
                f"{case.id} opens exactly as {seen[opening]}; with no "
                f"conversation_id the harness would treat them as one dialogue")
        seen[opening] = case.id
    print(f"выводимых идентификаторов разговора: {len(seen)}, столкновений: 0")


def _check_negatives_reachable(cases: list[Case]) -> None:
    """Over-masking has to become a BROKEN CALL somewhere, not only a table row.

    `false_masks` says the gateway masked something it must not. The judged
    `order_ref` says what that costs: the tool executed against an order that
    does not exist. Both numbers, never one.
    """
    judged = sum(1 for case in cases for call in case.calls
                 if "order_ref" in call.judged_args)
    if not judged:
        raise BuildError(
            "no case sends a negative into a judged argument; over-masking would "
            "then only ever be a precision figure and never a broken call")
    print(f"негативов, доходящих до судимого аргумента: {judged}")


def _check_json(cases: list[Case]) -> None:
    from bench.agentpii3.schema import case_from_json, corpus_digest
    for case in cases:
        rebuilt = case_from_json(json.loads(json.dumps(case.to_json())))
        if corpus_digest([rebuilt]) != corpus_digest([case]):
            raise BuildError(f"{case.id} does not survive its own json round trip")
    print("json: каждый случай восстановлен в тот же дайджест")


def main() -> int:
    cases = build(20260830, TARGET)
    problems: list[str] = []
    for case in cases:
        problems.extend(validate(case))

    def tally(pick) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in cases:
            counts[pick(case)] = counts.get(pick(case), 0) + 1
        return dict(sorted(counts.items(), key=lambda pair: -pair[1]))

    total = len(cases)
    print(f"источники       {ATTRIBUTION}")
    print(f"случаев         {total}")
    print(f"кластеров       {len({case.cluster for case in cases})}")
    print(f"регистр         {tally(lambda c: c.register)}")
    print(f"контекст        {tally(lambda c: c.context)}")
    print(f"происхождение   {tally(lambda c: c.provenance.kind)}")
    print(f"отбор           {tally(lambda c: c.provenance.selection)}")
    print(f"форма           {tally(lambda c: c.provenance.shape or '(нет)')}")
    speech = sum(1 for case in cases
                 if case.register in ("voice_raw", "voice_itn"))
    real = sum(1 for case in cases
               if case.provenance.kind in ("verbatim", "recombined"))
    clean = sum(1 for case in cases if case.register == "clean")
    print(f"речь            {speech}/{total} = {speech / total:.1%} (пол 50%)")
    print(f"форма из речи   {real}/{total} = {real / total:.1%} (пол 70%)")
    print(f"литературный    {clean}/{total} = {clean / total:.1%} (потолок 5%)")

    denominators = type_denominators(cases)
    distinct = distinct_values(cases)
    print("\nтип        обязательных  различных   (повтор — не наблюдение)")
    for kind in sorted(denominators):
        mark = "" if denominators[kind] >= 5 else "   < 5, печатается счётом"
        print(f"  {kind:<9} {denominators[kind]:>10}  "
              f"{distinct.get(kind, 0):>9}{mark}")

    negatives: dict[str, int] = {}
    for case in cases:
        for negative in case.negatives:
            negatives[negative.family] = negatives.get(negative.family, 0) + 1
    print(f"\nнегативов       {sum(negatives.values())} "
          f"{dict(sorted(negatives.items()))}")
    links: dict[str, int] = {}
    for case in cases:
        for link in case.links:
            links[link.kind] = links.get(link.kind, 0) + 1
    print(f"связей          {dict(sorted(links.items()))}")
    print(f"вызовов         {sum(len(case.calls) for case in cases)}   "
          f"с must_not_contain "
          f"{sum(1 for case in cases if case.final.must_not_contain)}")
    print(f"словесных ПД    "
          f"{sum(1 for c in cases for i in c.pii if i.spoken)}")
    print(f"длина           {min(case_characters(c) for c in cases)}-"
          f"{max(case_characters(c) for c in cases)} символов")

    print()
    _check_decodable(cases)
    _check_no_digits(cases)
    _check_openings(cases)
    _check_negatives_reachable(cases)
    _check_json(cases)

    if problems:
        print(f"\nНЕВАЛИДНО — {len(problems)} проблем:")
        for problem in problems[:30]:
            print(f"  {problem}")
        return 1
    print("схема: без замечаний")

    print("\nПРИМЕРЫ")
    for position in (0, 30, 70, 110, 150, 175, 186):
        case = cases[position]
        carrier = max(item.msg for item in case.pii)
        print(f"  [{case.id}] {case.register}/{case.context}/"
              f"{case.provenance.kind}  {case.provenance.shape[:52]}")
        print(f"    {case.messages[carrier].content}")
        for item in case.pii:
            print(f"      {item.type:<8} {item.value!r} -> {item.canonical!r}"
                  f"{' (прописью)' if item.spoken else ''}")
        for negative in case.negatives:
            print(f"      негатив  {negative.value!r} [{negative.family}]")
        for call in case.calls:
            print(f"      вызов    {call.name}{call.arguments} "
                  f"судится {call.judged_args}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
