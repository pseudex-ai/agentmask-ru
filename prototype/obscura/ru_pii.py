"""Russian structured-ID recognizers: regex + checksum (zero ML, ~100% precision).

Checksum algorithms confirmed in research (СНИЛС mod 101, ИНН weight vectors, Luhn).
Validation is what kills false positives, so a bare digit run only counts as PII
if its checksum passes.
"""

import re

from obscura.detect import Span


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def validate_snils(text: str) -> bool:
    digits = _digits(text)
    if len(digits) != 11:
        return False
    base = [int(c) for c in digits[:9]]
    control = int(digits[9:])
    total = sum(num * (9 - index) for index, num in enumerate(base))
    if total < 100:
        check = total
    elif total in (100, 101):
        check = 0
    else:
        check = total % 101
        if check == 100:
            check = 0
    return check == control


def validate_inn(text: str) -> bool:
    digits = _digits(text)
    if len(digits) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        control = sum(int(digits[i]) * weights[i] for i in range(9)) % 11 % 10
        return control == int(digits[9])
    if len(digits) == 12:
        weights_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        weights_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        control_11 = sum(int(digits[i]) * weights_11[i] for i in range(10)) % 11 % 10
        control_12 = sum(int(digits[i]) * weights_12[i] for i in range(11)) % 11 % 10
        return control_11 == int(digits[10]) and control_12 == int(digits[11])
    return False


def validate_luhn(text: str) -> bool:
    digits = _digits(text)
    if len(digits) < 13:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        num = int(char)
        if index % 2 == 1:
            num *= 2
            if num > 9:
                num -= 9
        total += num
    return total % 10 == 0


_SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}[ -]\d{2}\b")
_SNILS_NODASH_RE = re.compile(r"\b\d{11}\b")
_INN_RE = re.compile(r"\b\d{12}\b|\b\d{10}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){15,18}\d\b")
# Passport requires a separator (серия номер) — bare 10 digits collides with
# everything (phone/INN/order), so we trade a little recall for precision.
_PASSPORT_RE = re.compile(r"\b\d{2}\s\d{2}\s\d{6}\b|\b\d{4}\s\d{6}\b")
_PASSPORT_CTX_RE = re.compile(r"(?i:паспорт\w*)\D{0,8}(\d{2}\s?\d{2}\s?\d{6})\b")
_DATE_RE = re.compile(r"\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b")


def detect_structured(text: str) -> list[Span]:
    """Detect RU structured IDs, gated by checksum where one exists."""
    spans: list[Span] = []
    for match in _SNILS_RE.finditer(text):
        if validate_snils(match.group()):
            spans.append(Span(match.start(), match.end(), "SNILS", match.group()))
    for match in _SNILS_NODASH_RE.finditer(text):
        if validate_snils(match.group()):
            spans.append(Span(match.start(), match.end(), "SNILS", match.group()))
    for match in _CARD_RE.finditer(text):
        if validate_luhn(match.group()) and len(_digits(match.group())) in (16,):
            spans.append(Span(match.start(), match.end(), "CARD", match.group()))
    for match in _INN_RE.finditer(text):
        if not validate_inn(match.group()):
            continue
        # INN-12 (физлицо) has two check digits -> strong, trust the checksum.
        # INN-10 (юрлицо) has one check digit (~10% of random 10-digit numbers
        # pass) -> too weak alone; require an "инн/контрагент" context word so a
        # coincidental order/phone number is not mislabeled as an INN.
        if len(_digits(match.group())) == 10:
            window = text[max(0, match.start() - 20): match.end() + 5].lower()
            if not any(w in window for w in ("инн", "контрагент", "налогоплательщ", "реквизит")):
                continue
        spans.append(Span(match.start(), match.end(), "INN", match.group()))
    for match in _PASSPORT_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "PASSPORT", match.group()))
    # No-separator passport is ambiguous alone; trust it when "паспорт" precedes.
    for match in _PASSPORT_CTX_RE.finditer(text):
        spans.append(Span(match.start(1), match.end(1), "PASSPORT", match.group(1)))
    for match in _DATE_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "DATE", match.group()))
    return spans
