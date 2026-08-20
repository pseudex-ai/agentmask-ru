"""Russian structured-ID recognizers: regex + checksum (zero ML, ~100% precision).

Checksum algorithms confirmed in research (СНИЛС mod 101, ИНН weight vectors, Luhn).
Validation is what kills false positives, so a bare digit run only counts as PII
if its checksum passes.
"""

import re

from pseudex.assets import ASSETS
from pseudex.detect import Span


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


def validate_ogrn(text: str) -> bool:
    """ОГРН (13) / ОГРНИП (15) carry a check digit, so the shape alone is not
    trusted: a bare 13-digit run is otherwise indistinguishable from an order or
    tracking number."""
    digits = _digits(text)
    if len(digits) == 13:
        return int(digits[:12]) % 11 % 10 == int(digits[12])
    if len(digits) == 15:
        return int(digits[:14]) % 13 % 10 == int(digits[14])
    return False


# --- Types below are CONTEXT-ANCHORED on purpose ---------------------------
# Their digit shapes collide with each other and with ordinary business numbers:
# a driver's licence, a vehicle registration and a passport are all `NN NN
# NNNNNN`, and a 20-digit run could be an account or an internal reference.
# Shape alone would either miss them or mask every long number in the dialogue.
# The cue word is what makes the type — and the TYPE matters, not just the
# masking: mistyping a licence as a phone replaces it with a fake PHONE, and the
# model then reads a phone number where a document should be.
#
# The cue vocabulary is LEASED (pseudex/assets.py); the checksum algorithms and
# the published digit shapes below stay in the engine, because a regulation
# anyone can look up is not something a customer needs a subscription for.

# Russian plate: only the 12 Cyrillic letters that look like Latin are legal, so
# the shape IS distinctive enough to stand without a cue word.
# BOTH ALPHABETS, and that is the whole point. The twelve letters permitted on a
# Russian plate — АВЕКМНОРСТУХ — were chosen precisely because they have Latin
# look-alikes, so an operator typing without switching layout produces
# `E777KX102`, which is the same plate and used to be invisible to us. A persona
# client whose product is a CRM for car services put the share at "about ten
# percent of traffic", and those ten percent went to the model unmasked and
# silently — in exactly the data type they came to us for.
_PLATE_LETTERS = "АВЕКМНОРСТУХавекмнорстухABEKMHOPCTYXabekmhopctyx"

# Types from ГОСТ Р 50577. The first line is an ordinary car; the rest were
# absent, and a car service sees them daily.
_PLATE_RE = re.compile("|".join([
    # Тип 1 — легковые: А123ВС77 / А123ВС777
    rf"\b[{_PLATE_LETTERS}]\s?\d{{3}}\s?[{_PLATE_LETTERS}]{{2}}\s?\d{{2,3}}\b",
    # Тип 1Б — такси и маршрутные: АА123 77
    rf"\b[{_PLATE_LETTERS}]{{2}}\s?\d{{3}}\s?\d{{2,3}}\b",
    # Тип 1А — прицепы: АВ1234 77
    rf"\b[{_PLATE_LETTERS}]{{2}}\s?\d{{4}}\s?\d{{2,3}}\b",
    # Тип 2 — мотоциклы: 1234 АВ 77
    rf"\b\d{{4}}\s?[{_PLATE_LETTERS}]{{2}}\s?\d{{2,3}}\b",
]))
# Two-letter Russian words built ONLY from the ГОСТ plate alphabet. «счёт 1234 от
# 15.05.2025» — one of the commonest phrases in Russian business writing — parsed
# as a type-2 motorcycle plate: four digits, two "plate letters", a region code.
# Every invoice-and-date line in the language was being partly masked.
#
# The gate is on CASE, not on the word alone. A plate is written in capitals
# («1234 ТУ 77»); the prose word is lower case («1234 от 15»). Denying the word
# regardless of case would cost real plates, because «ту», «те», «на» are all
# legitimate letter pairs on a real registration. Denying only the lower-case
# form costs a sloppily typed plate and saves every invoice date — and a missed
# lower-case plate is one value, while an eaten invoice number is every document
# the customer has.
_PLATE_DENY_LOWER = frozenset((
    "от", "на", "но", "то", "во", "ко", "со", "не", "ну", "он", "ох", "ах", "ух",
    "ум", "ус", "ор", "ер", "та", "те", "ту", "ма", "ме", "му", "ка", "ку", "ва",
    "ре", "ро", "ру", "са", "се", "су", "ем", "ес", "мы", "ты",
))
# MAC: six hex pairs. Distinctive enough to stand alone — no other value in a
# support conversation is written this way.
_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")

# VIN, ISO 3779: 17 characters, and I/O/Q are excluded precisely so they cannot
# be confused with 1/0. That exclusion is what makes the shape checkable.
_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_VIN_CUE = re.compile(r"(?i)\b(?:vin|вин|кузов\w*|шасси|автомобил\w*|машин\w*)\b")
_VIN_VALUES = {**{str(d): d for d in range(10)},
               **{c: v for c, v in zip("ABCDEFGH", range(1, 9))},
               **{c: v for c, v in zip("JKLMNP", (1, 2, 3, 4, 5, 7))},
               "R": 9, **{c: v for c, v in zip("STUVWXYZ", range(2, 10))}}
_VIN_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)


def vin_check_digit_valid(vin: str) -> bool:
    """The ISO 3779 check digit at position 9.

    Mandatory in North America, frequently wrong or absent elsewhere — so a
    failed check is NOT proof the string is not a VIN. It is used the way the
    INN-10 checksum is used: a pass lets the value stand alone, a failure sends
    it to the context gate instead of rejecting it outright.
    """
    if len(vin) != 17:
        return False
    total = sum(_VIN_VALUES.get(c, 0) * w for c, w in zip(vin, _VIN_WEIGHTS))
    remainder = total % 11
    expected = "X" if remainder == 10 else str(remainder)
    return vin[8] == expected


def detect_vehicle_ids(text: str) -> list[Span]:
    """MAC addresses and VINs.

    A VIN with a valid check digit stands alone. One without needs a cue word
    nearby, because a 17-character alphanumeric run is also what an order code,
    a build hash prefix or a warehouse label looks like — masking those would
    take the customer's own identifiers out of their agent's reach.
    """
    spans = [Span(m.start(), m.end(), "MAC", m.group()) for m in _MAC_RE.finditer(text)]
    for match in _VIN_RE.finditer(text):
        value = match.group()
        if not vin_check_digit_valid(value):
            window = text[max(0, match.start() - 40):match.start()]
            if not _VIN_CUE.search(window):
                continue
        spans.append(Span(match.start(), match.end(), "VIN", value))
    return spans


_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
                      r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b")
# Свидетельство о рождении: roman series + two Cyrillic letters + number.
_BIRTH_CERT_RE = re.compile(r"\b[IVX]{1,4}-[А-ЯЁ]{2}\s?№?\s?\d{6}\b")
# ОГРНИП ONLY — FIFTEEN DIGITS. The thirteen-digit ОГРН belongs to a LEGAL
# person, and a legal person has no data subject: 152-ФЗ ст. 3 п. 1 defines
# personal data through a физическое лицо, and GDPR Recital 14 excludes data of
# legal persons in as many words, contact details included.
#
# Masking it was not caution, it was damage. A customer's agent looking a
# counterparty up by ОГРН received a FAKE one and found nothing — we broke their
# own document flow to protect something the law does not protect, and the
# failure looked like the tool being broken rather than like us.
#
# ОГРНИП stays, and the length is the whole distinction: an individual
# entrepreneur IS a natural person, and their registration number identifies
# them. Two numbers, one shape family, opposite answers.
_OGRNIP_RE = re.compile(r"\b\d{15}\b")

# SPACES ARE A SEPARATOR TOO, and on the green card itself the number is printed
# «112 233 445 95». Requiring dashes meant the form a customer copies off their
# own document was the one form we did not find. The separator repeats because
# copy-paste doubles it: «112-233-445  95» is the same СНИЛС.
_SNILS_RE = re.compile(r"\b\d{3}[ -]\s*\d{3}[ -]\s*\d{3}[ -]\s*\d{2}\b")
_SNILS_NODASH_RE = re.compile(r"\b\d{11}\b")
_INN_RE = re.compile(r"\b\d{12}\b|\b\d{10}\b")
# A REPEATED SEPARATOR is what copy-paste out of a table produces, and the
# single optional one refused it: «4276  3800 1234 5679» is the same card.
_CARD_RE = re.compile(r"\b(?:\d[ -]{0,2}){15,18}\d\b")
# Passport requires a separator (серия номер) — bare 10 digits collides with
# everything (phone/INN/order), so we trade a little recall for precision.
_PASSPORT_RE = re.compile(r"\b\d{2}\s+\d{2}\s+\d{6}\b|\b\d{4}\s+\d{6}\b")
# `с{1,2}` and `п{1,2}` absorb the doubled-consonant typo, which is the single
# commonest way Russians misspell this word: «пасспорт» outnumbers every other
# variant. Found on AgentPII-RU, where it cost 25% of passport recall in the
# sloppy register — the number was there and the cue beside it was misspelt.
# The window after the cue word is SIXTEEN characters, not eight. «Паспортные
# данные: 4518123456» is the commonest phrasing there is and it needs nine —
# the number was missed by ONE character. A hyphen joins the space as a
# separator («4607-238914»), which is how a form field renders it.
_PASSPORT_CTX_RE = re.compile(
    r"(?i:пас{1,2}п{1,2}орт\w*)\D{0,16}?(\d{2}[\s-]?\d{2}[\s-]?\d{6})\b")
# «серия 4607 номер 238914» — the two halves named separately, with words
# between them, so neither the plain shape nor the cue pattern above can see it.
# Both numbers are masked; the words are not, being nobody's data.
_PASSPORT_PARTS_RE = re.compile(
    r"(?i)сери\w*\s*:?\s*(\d{4})\D{1,12}?(\d{6})\b")
_DATE_RE = re.compile(r"\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b")
# THE SAME DATE WITH ITS SEPARATORS GONE. «24.12.1967» typed without dots is
# «24121967» — eight digits and no shape left — so a date a chat wrote without
# punctuation went to the model in the clear while the dotted one beside it was
# protected. Found by the noise ladder: every date it loses at the punctuation
# rung is this one.
#
# Emitted as an ordinary DATE and judged by the SAME association rule, not by a
# birth cue of its own. That matters: the golden set writes «снилс … карта …
# дата 21011979», where what makes the date personal is the identifier standing
# beside it, exactly as `context._date_is_personal` already decides for the
# dotted form. A second, narrower gate here would have been a second answer to a
# question this codebase has already answered once.
#
# Never adjacent to another digit, so it cannot bite a chunk out of an unspaced
# card number.
_GLUED_DATE_RE = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)")


def _reads_as_date(day: str, month: str, year: str) -> bool:
    """Whether these eight digits can be a date at all.

    This is what keeps ordinary eight-digit numbers out before the association
    rule is even asked: an order or article number has to land on a day of
    01-31, a month of 01-12 AND a year a living person could carry.
    """
    return (1 <= int(day) <= 31 and 1 <= int(month) <= 12
            and 1900 <= int(year) <= 2026)


def detect_structured(text: str) -> list[Span]:
    """Detect RU structured IDs, gated by checksum where one exists."""
    ru_pii = ASSETS.get().ru_pii
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
            if not any(w in window for w in ru_pii.inn_context):
                continue
        spans.append(Span(match.start(), match.end(), "INN", match.group()))
    for match in _PASSPORT_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "PASSPORT", match.group()))
    # No-separator passport is ambiguous alone; trust it when "паспорт" precedes.
    for match in _PASSPORT_CTX_RE.finditer(text):
        spans.append(Span(match.start(1), match.end(1), "PASSPORT", match.group(1)))
    for match in _PASSPORT_PARTS_RE.finditer(text):
        for group in (1, 2):
            spans.append(Span(match.start(group), match.end(group),
                              "PASSPORT", match.group(group)))
    for match in _DATE_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "DATE", match.group()))
    for match in _GLUED_DATE_RE.finditer(text):
        if _reads_as_date(*match.groups()):
            spans.append(Span(match.start(), match.end(), "DATE", match.group()))
    for entity_type, pattern in ru_pii.ctx_patterns:
        for match in pattern.finditer(text):
            spans.append(Span(match.start(1), match.end(1), entity_type, match.group(1)))
    for match in _OGRNIP_RE.finditer(text):
        if validate_ogrn(match.group()):
            spans.append(Span(match.start(), match.end(), "OGRN", match.group()))
    for match in _IPV4_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "IP", match.group()))
    for match in _BIRTH_CERT_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "BIRTH_CERT", match.group()))
    return spans


def detect_plates(raw_text: str) -> list[Span]:
    """Vehicle plates, matched on the RAW text rather than the normalized one.

    normalize() folds digit-lookalike letters (Б->6, В->8) inside digit-dense
    runs to defeat obfuscated phone numbers — and a plate is exactly such a run,
    so `А123БВ777` arrives here as `А12368777` and stops looking like a plate.
    Lowercase plates survived only by accident (fewer lookalikes in the run),
    which is what exposed this.

    Safe because normalize() is length-preserving 1:1, so offsets taken from the
    raw text index identically into the normalized text every other layer used."""
    spans: list[Span] = []
    for match in _PLATE_RE.finditer(raw_text):
        letters = "".join(c for c in match.group() if c.isalpha())
        if letters.islower() and letters in _PLATE_DENY_LOWER:
            continue
        spans.append(Span(match.start(), match.end(), "PLATE", match.group()))
    return spans
