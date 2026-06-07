"""Quasi-identifiers (HIPAA Safe Harbor classes that our direct-PII layers miss):
birth date/year in birth context, age >= 90, and medical (special category under
152-ФЗ) via an МКБ-10-style term gazetteer. Detect-and-mask (a single message has
no equivalence class, so k-anonymity is undefined — per dd4-C).
"""

import re

from obscura.detect import Span

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_BIRTH_CTX = ("рожд", "г.р", "г р", "родил", "д.р", "появил на свет")
_AGE_RE = re.compile(r"\b(\d{2,3})\s*(?:лет|года|год)\b")
# МКБ-10-style common diagnosis stems (inflection-tolerant via \w*).
_MEDICAL_RE = re.compile(
    r"\b(?:диабет|гиперт|астм|онколог|рак|вич|спид|туберкул|гепатит|депресс|"
    r"шизофрен|ковид|covid|инсульт|инфаркт|эпилепс|бронхит|пневмони|артрит|"
    r"гастрит|псориаз|деменци|аутизм|бесплоди)\w*",
    re.IGNORECASE,
)


def detect_quasi(text: str) -> list[Span]:
    spans: list[Span] = []
    low = text.lower()
    for match in _YEAR_RE.finditer(text):
        window = low[max(0, match.start() - 25): match.end() + 25]
        if any(ctx in window for ctx in _BIRTH_CTX):
            spans.append(Span(match.start(), match.end(), "DOB", match.group()))
    for match in _AGE_RE.finditer(text):
        if int(match.group(1)) >= 90:  # HIPAA: ages over 89 are identifiers
            spans.append(Span(match.start(), match.end(), "AGE", match.group()))
    for match in _MEDICAL_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "MEDICAL", match.group()))
    return spans
