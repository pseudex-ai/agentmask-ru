"""Quasi-identifiers (HIPAA Safe Harbor classes that our direct-PII layers miss):
birth date/year in birth context, age >= 90, and medical (special category under
152-ФЗ) via an МКБ-10-style term gazetteer. Detect-and-mask (a single message has
no equivalence class, so k-anonymity is undefined — per dd4-C).
"""

import re

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
    r"\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b"
    r"|(?<!\d)(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)")
_AGE_RE = re.compile(r"\b(\d{2,3})\s*(?:лет|года|год)\b")

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


def _birth_context_near(low: str, start: int, end: int, birth_ctx: tuple[str, ...]) -> bool:
    """True if a birth cue sits in the SAME CLAUSE as this date.

    A plain proximity window is not enough: in `Заказ приедет 1 сентября, а я
    родился 7 июля` the cue `родился` is close to BOTH dates, so the delivery
    date gets masked too — and that breaks the delivery tool call, which is
    exactly the damage this product must not cause. Clipping each window at the
    nearest comma keeps the cue bound to its own clause.

    Periods are deliberately NOT treated as boundaries: the most common cue is
    the abbreviation `д.р.`, and splitting on `.` would throw it away."""
    before = low[max(0, start - 24):start].rsplit(",", 1)[-1].rsplit(";", 1)[-1]
    after = low[end:end + 16].split(",", 1)[0].split(";", 1)[0]
    return any(ctx in before or ctx in after for ctx in birth_ctx)


def detect_quasi(text: str) -> list[Span]:
    quasi = ASSETS.get().quasi
    spans: list[Span] = []
    low = text.lower()
    for match in _YEAR_RE.finditer(text):
        window = low[max(0, match.start() - 25): match.end() + 25]
        if any(ctx in window for ctx in quasi.birth_ctx):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in _NUM_DATE_RE.finditer(text):
        if _birth_context_near(low, match.start(), match.end(), quasi.birth_ctx):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in quasi.text_date.finditer(text):
        if _birth_context_near(low, match.start(), match.end(), quasi.birth_ctx):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in _AGE_RE.finditer(text):
        if int(match.group(1)) >= 90:  # HIPAA: ages over 89 are identifiers
            spans.append(Span(match.start(), match.end(), "AGE", match.group()))
    for match in quasi.medical.finditer(text):
        spans.append(Span(match.start(), match.end(), "MEDICAL", match.group()))
    return spans
