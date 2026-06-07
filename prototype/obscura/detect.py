"""PII detection — prototype stage 1: regex + checksum only, zero ML.

Identifiers (phone, email, and later СНИЛС/ИНН/паспорт/карта) are detected by
deterministic rules with near-100% recall. ML NER for ФИО/адрес is a later stage.
"""

import re
from dataclasses import dataclass

import phonenumbers


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    entity_type: str
    value: str


# RU phone: +7 / 8 followed by 10 digits with optional separators.
_PHONE_RE = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
)
# Bare mobile without country code (10 digits starting with 9). Privacy-biased:
# masking a rare 9-prefixed order number is safer than leaking a real phone.
_BARE_PHONE_RE = re.compile(r"\b9\d{9}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def detect_pii(text: str) -> list[Span]:
    """Return non-overlapping PII spans found in text. Pure function.

    Phones: Google libphonenumber (handles formats/dashes/fullwidth) at POSSIBLE
    leniency for recall, UNION with our regexes as backup. (Homoglyph letters are
    already folded to digits upstream by normalize().)"""
    spans: list[Span] = []
    for match in phonenumbers.PhoneNumberMatcher(text, "RU", leniency=phonenumbers.Leniency.VALID):
        spans.append(Span(match.start, match.start + len(match.raw_string), "PHONE", match.raw_string))
    for match in _PHONE_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "PHONE", match.group()))
    for match in _BARE_PHONE_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "PHONE", match.group()))
    for match in _EMAIL_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "EMAIL", match.group()))
    return _resolve_overlaps(spans)


def _resolve_overlaps(spans: list[Span]) -> list[Span]:
    """Greedily keep the earliest, longest non-overlapping spans."""
    ordered = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    kept: list[Span] = []
    last_end = -1
    for span in ordered:
        if span.start >= last_end:
            kept.append(span)
            last_end = span.end
    return kept
