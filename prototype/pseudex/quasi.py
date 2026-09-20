"""Quasi-identifiers (HIPAA Safe Harbor classes that our direct-PII layers miss):
birth date/year in birth context, age >= 90, and medical (special category under
152-ФЗ) via an МКБ-10-style term gazetteer. Detect-and-mask (a single message has
no equivalence class, so k-anonymity is undefined — per dd4-C).
"""

import re

from pseudex.fuzzy import within_one_typo

from pseudex.assets import ASSETS
from pseudex.detect import Span

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
# ЧИСЛОВАЯ ДАТА В РОДИЛЬНОМ КОНТЕКСТЕ — ЭТО ДАТА РОЖДЕНИЯ, А НЕ «ДАТА». Раньше
# её типизировал слой structured как DATE, и это засчитывалось промахом
# справедливо: пересечение чужого типа — не полнота, а дата рождения под меткой
# «дата» теряет ровно то, что делает её персональными данными. Хуже того, из
# всей даты маскировался только ГОД — «родился 21.09.1955» отдавало модели день
# и месяц. 23 значения на AgentPII v3.
_NUM_DATE_RE = re.compile(
    r"\b\d{2}[.\-/ ]\d{2}[.\-/ ]\d{4}\b"
    # ОДНА ЦИФРА В ДНЕ ИЛИ МЕСЯЦЕ И ДВУЗНАЧНЫЙ ГОД — та же дата, написанная от
    # руки: «10.4.82», «1.4.1982», «26.10.02». Раньше не матчилось вовсе, а
    # «1.4.1982» отдавало DOB только на ГОД — день и месяц уходили к модели
    # открытыми, то есть значение рвалось пополам (публичный бенчмарк, 27 дат
    # из 50). Разделитель здесь только знаковый: пробел оставлен ТОЛЬКО
    # двузначной форме выше, иначе «заказ 1 2 34» стало бы датой.
    r"|\b\d{1,2}[.\-/]\d{1,2}[.\-/](?:\d{4}|\d{2})\b"
    r"|(?<!\d)(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)")
# Год, стоящий ХВОСТОМ полной даты: «…от 25.07.2026». Такой год не является
# отдельной датой рождения, даже если подсказка рождения стоит в том же
# предложении, — иначе год документной даты уезжает в маску отдельным спаном и
# ломает реквизит договора (публичный бенчмарк, DOB '2026' из «от 25.07.2026»).
_YEAR_TAIL_OF_DATE = re.compile(r"\d{1,2}[.\-/ ]\d{1,2}[.\-/ ]$")
_AGE_RE = re.compile(r"\b(\d{2,3})\s*(?:лет|года|год)\b")
# A stretched pronoun («оон», «онаа») is the same pronoun: the voice register
# holds a vowel, and a date of birth was lost to it.
_PERSON_BEFORE_DATE_RE = re.compile(r"(?:^|[^а-яё])(?:о+н|о+на+|ему+|ей|его|её|пациент\w*|клиент\w*|ребён\w*|ребен\w*)\s*(?:-\s*)?$")

# The birth cues, the month names and the medical stem list are LEASED. The
# written-out day+month pattern is assembled from the leased months when the
# bundle loads.
#
# A written-out date is only ever accepted inside birth context — the same gate
# the year uses. Outside it a date is a delivery slot or an appointment, not
# personal data, and masking those would break the very tool calls the product
# exists to keep working.
#
# Without it only the YEAR was masked in `Родился 12 марта 1985 года`, leaving
# the day and month on the wire — a partial date of birth is still identifying —
# and `Мой д.р. 12 марта` was missed entirely.


# A SENTENCE END IS A PERIOD, A SPACE AND A CAPITAL. The abbreviation «д.р.»
# writes periods with no space («д.р») or with a digit after («д.р. 12»), and a
# capital never follows either — so this separates a new sentence from the one
# abbreviation the cue list depends on, without a list of abbreviations to keep
# true. The same test the address cue already uses (CLAUDE.md, «A cue word
# reaches 60 characters and never across a sentence end»).
_SENTENCE_END = re.compile(r"[.!?]\s+(?=[А-ЯЁA-Z])")


def sentence_window(text: str, start: int, end: int, back: int, forward: int) -> str:
    """The text around a span, clipped at the sentence ends on both sides.

    Shared by the two gates that ask «is a birth cue near this date» — the DOB
    typer here and the bare-date gate in `context` — because the defect was in
    both and one window is one rule."""
    before = _SENTENCE_END.split(text[max(0, start - back):start])[-1]
    after = _SENTENCE_END.split(text[end:end + forward])[0]
    return (before + " " + after).lower()


# «и др.» — «и другие», а не дата рождения. Единственное живое столкновение
# словесной подсказки «др», и оно снимается тем, что перед ней стоит союз.
_AND_OTHERS = re.compile(r"\bи\s*$")


def _word_cue_before(before: str) -> bool:
    """Подсказка-СЛОВО, стоящая непосредственно перед датой.

    Только ПЕРЕД: «др 13.01.1991» — это дата рождения, а «13.01.1991 и др.» —
    перечисление. И только не после союза «и», который превращает «др» в
    «другие». Обе оговорки дешевле, чем подстрочный поиск, который зацепил бы
    «адрес» и «друг».
    """
    words = ASSETS.get().quasi.birth_ctx_words
    if words is None:
        return False
    for match in words.finditer(before):
        if not _AND_OTHERS.search(before[:match.start()]):
            return True
    return False


def _birth_context_near(text: str, low: str, start: int, end: int,
                        birth_ctx: tuple[str, ...]) -> bool:
    """True if a birth cue sits in the SAME CLAUSE and the SAME SENTENCE as this date.

    A plain proximity window is not enough: in `Заказ приедет 1 сентября, а я
    родился 7 июля` the cue `родился` is close to BOTH dates, so the delivery
    date gets masked too — and that breaks the delivery tool call, which is
    exactly the damage this product must not cause. Clipping each window at the
    nearest comma keeps the cue bound to its own clause.

    AND AT THE SENTENCE END, because a host's own instruction is written in
    sentences: «…возраст и пол пациента вычисли сам из даты рождения и имени.
    Сегодня 2026-09-02.» — the cue is the HOST telling the agent what to derive,
    and the date after it is TODAY. Masked, it moved the model's notion of today
    by months and every relative date the agent computed («на пятницу», «в
    четверг») moved with it: the clinic slot was booked in March instead of
    September (r2 run, 10 triples, and both controls agreed every time). A bare
    date is not personal data; a date in the next sentence is not in the cue's
    context either.

    Periods alone are still NOT boundaries: the commonest cue is the
    abbreviation `д.р.`, and splitting on every `.` would throw it away — see
    `_SENTENCE_END` for what separates the two."""
    window = text[max(0, start - 24):start]
    window = _SENTENCE_END.split(window)[-1]
    before = window.lower().rsplit(",", 1)[-1].rsplit(";", 1)[-1]
    tail = text[end:end + 16]
    tail = _SENTENCE_END.split(tail)[0]
    after = tail.lower().split(",", 1)[0].split(";", 1)[0]
    if any(ctx in before or ctx in after for ctx in birth_ctx):
        return True
    if _word_cue_before(before):
        return True
    # «дата рожжения 28.04.1975», «рдилась 22.04.1994»: the cue mistyped is
    # still the cue — one typo, judged on the same words the list holds.
    for token in re.findall(r"[а-яё]+", before + " " + after):
        word = re.sub(r"([а-яё])\1+", r"\1", token)
        if len(word) >= 5 and any(within_one_typo(word[:len(cue)], cue)
                                  for cue in ("рождения", "родился", "родилась", "рожден")):
            return True
    return False


def detect_quasi(text: str) -> list[Span]:
    quasi = ASSETS.get().quasi
    spans: list[Span] = []
    low = text.lower()
    for match in _YEAR_RE.finditer(text):
        if _YEAR_TAIL_OF_DATE.search(text[max(0, match.start() - 6):match.start()]):
            continue
        window = low[max(0, match.start() - 25): match.end() + 25]
        if any(ctx in window for ctx in quasi.birth_ctx):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in _NUM_DATE_RE.finditer(text):
        # A DATE SAID RIGHT AFTER THE PERSON IS THEIR DATE OF BIRTH. «запишите
        # к неврологу букина сергея ивановича он 19 12 1992» carries no birth
        # cue at all — the pronoun is the cue: nothing else about a person is
        # given as a full date in the same breath. Bounded to the pronoun
        # standing directly before the date, so «счёт от 19 12 1992» and a
        # date after a verb stay what they are.
        if (_birth_context_near(text, low, match.start(), match.end(), quasi.birth_ctx)
                or _PERSON_BEFORE_DATE_RE.search(low[max(0, match.start() - 24):match.start()])):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in quasi.text_date.finditer(text):
        if (_birth_context_near(text, low, match.start(), match.end(), quasi.birth_ctx)
                or _PERSON_BEFORE_DATE_RE.search(low[max(0, match.start() - 24):match.start()])):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in _AGE_RE.finditer(text):
        if int(match.group(1)) >= 90:  # HIPAA: ages over 89 are identifiers
            spans.append(Span(match.start(), match.end(), "AGE", match.group()))
    for match in quasi.medical.finditer(text):
        spans.append(Span(match.start(), match.end(), "MEDICAL", match.group()))
    return spans
