"""Russian structured-ID recognizers: regex + checksum (zero ML, ~100% precision).

Checksum algorithms confirmed in research (СНИЛС mod 101, ИНН weight vectors, Luhn).
Validation is what kills false positives, so a bare digit run only counts as PII
if its checksum passes.
"""

import re

from pseudex.fuzzy import within_one_typo

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
#
# THE RUN IS READ WHOLE; THE CARD GRAMMAR BELOW DECIDES WHAT IS INSIDE IT. The
# shape used to be «16..19 digits between word boundaries», which bit sixteen
# digits out of the MIDDLE of a longer run — «1234 5678 9012 3456 7890», an order
# number, was masked as its first sixteen. Refusing every run longer than a card
# then swung the other way and lost BOTH cards of «<card> <card>». Consuming the
# run whole is what stops a second match from starting inside it; how many cards
# it holds is decided once, in `_card_pieces`.
_CARD_RE = re.compile(r"(?<!\d)\d(?:[ -]{0,2}\d)*\b")
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
# THE CUE TYPES THE NUMBER, AND A CHECKSUM ONLY GATES A BARE ONE. A customer
# who mistypes one digit of their СНИЛС has still typed their СНИЛС — ten of
# the eleven digits are real — and the checksum gate sent it to the model in
# the clear (live v4: four of four `validate` cases built with a broken
# digit). The checksum earns its keep on a number standing alone; behind the
# word «снилс» the evidence is the word. The cue tolerates the one-edit
# spellings the deny lists already tolerate.
_SNILS_CUE_RE = re.compile(
    r"(?i:с\s?н\s?и\s?л\s?с|силс|снилз|снилсс|снил\b)\D{0,12}?(\d{3}[ -]?\d{3}[ -]?\d{3}[ -]?\d{2})(?!\d)")
_INN_CUE_RE = re.compile(r"(?i:\bинн\b)\D{0,12}?(\d{12})(?!\d)")
# THE CUE NAMES A CARD, NOT ANY WORD THAT CONTAINS ONE. `карт\w*` typed
# «картина», «картотека», «картон», «картошка» — the number after them was masked
# because the WORD matched — and `card\b` did the same to «postcard» and
# «discard», which END in it. Both are word boundaries rather than a longer word
# list: the noun in its own forms (with the diminutive) takes `\b` on BOTH sides,
# and a hyphen followed by a LETTER is a compound («карт-бланш»), never the
# separator a form prints. «карт» alone stays, because that is how a form field
# abbreviates it, and «карта-4012» still matches — a hyphen before a DIGIT is a
# separator.
_CARD_CUE = (r"(?i:\bкарт(?:а|ы|е|у|ой|ою|ам|ами|ах)?\b(?!-[а-яё])"
             r"|\bкарточ\w*|\bcard\b)")
# THE CUE OPENS A WHOLE RUN, NOT FOUR GROUPS OF FOUR. Capturing exactly sixteen
# digits masked an eighteen-digit card as its first sixteen and left the tail —
# « 02» — in the clear, and the lookahead that was meant to stop that treated a
# SECOND card as a continuation and refused both. The regex only says where the
# run begins and ends; `_card_pieces` says where the cards in it do.
_CARD_CUE_RE = re.compile(rf"{_CARD_CUE}\D{{0,16}}?(\d(?:[ -]{{0,2}}\d)*)")


# --------------------------------------------------------------- card grammar
#
# A CARD IS 13..19 DIGITS, A RUN MAY HOLD SEVERAL OF THEM, AND THE GROUPING IS THE
# ONLY EVIDENCE THERE IS. So the grammar is a segmentation over the run, with an
# explicit score and a refusal policy, and it reads in a fixed order:
#
#   * THE RUN IS ONE NUMBER written in one grouping that TILES EXACTLY into 13..19
#     -digit pieces. «<16> <16>» is two cards; an eighteen-digit card written
#     fours-plus-two is ONE; a twenty-nine-digit run whose last separator was lost
#     is a sixteen and a thirteen once the merged group is cut in the width the
#     sender's OTHER groups established. A run that does not tile is not a card
#     however long it is, which is what keeps a twenty-digit СЧЁТ whole.
#   * THE RUN IS ONE CARD AND ONE NEIGHBOUR. The card is at one END — a card in the
#     middle leaves two residues and no reading for them — and the residue must be
#     a number in its own right: one whole group, or several of one width that
#     differs from the card's. «<7-digit order> <card>» and «<card> <7-digit
#     order>» both read, and so does «<5> <5> <card>», because the two fives are
#     ONE number and their boundary with the fours is a change of grouping.
#
# A 1..3-DIGIT GROUP GLUED TO A CARD IS THE SAME STRING as a longer card
# («…1239 12» is also an eighteen-digit card), and the longer-card reading wins,
# because a separate number there is exactly the tail leak this grammar exists to
# remove. That is the FIRST reading, not a special case: the run tiles as one card.
#
# THE ONE PLACE A CUE DOES NOT OUTRANK THE CHECKSUM. A residue written in the
# card's OWN width is not evidence — a uniform twenty-digit run is either «card +
# one group» or «one group + card» and the string cannot say which — so the
# checksum decides: the window that passes Luhn is the card. With NEITHER passing
# the run is refused whole; with BOTH (one coincidence in a hundred) `_one_span`
# breaks the tie toward the card the cue introduces.
#
# WHAT IS DELIBERATELY NOT READ, because the string does not carry the evidence:
#   * Reading 2 trusts the sender's OWN boundaries and never a cut the step made;
#     only the exact cover uses those. A card-shaped window bitten out of a longer
#     number is the whole defect this grammar replaced.
#   * A CARD-SHAPED group wider than the sender's width is a card whose separator
#     was lost or the end of one number and the start of another, and only a cover
#     tells them apart. With no cover the run is refused WHOLE, because either
#     partial reading leaves some of those digits in the model's hands.
#   * A run whose groups are uniform and whose card-shaped windows fail Luhn is
#     refused. It costs an unmasked card; biting would hand the model a card carved
#     out of a number that is not one. Written down because a policy nobody wrote
#     down is indistinguishable from a bug.
_CARD_LENGTHS = range(13, 20)
_CARD_MIN = min(_CARD_LENGTHS)
_CARD_MAX = max(_CARD_LENGTHS)
# A run longer than this many digits is refused whole rather than truncated, so the
# cap can never leave a card half-masked. It also bounds the work below.
_CARD_RUN_CAP = _CARD_MAX * 8


def _digit_groups(chunk: str, base: int) -> list[tuple[int, int]]:
    """(start, end) of every digit group of `chunk`, offset into the whole text."""
    return [(base + match.start(), base + match.end())
            for match in re.finditer(r"\d+", chunk)]


def _grouping_step(groups: list[tuple[int, int]]) -> int | None:
    """The width the sender grouped in: the commonest width a card may have.

    TWO occurrences, not one. A single group is a number, not a convention, and
    letting a lone short group set the step is how a card got re-cut at a width
    nobody wrote — «<16> <2>» cut the sixteen in twos, the run «tiled», and the
    neighbour was swallowed into an eighteen-digit card.
    """
    counts: dict[int, int] = {}
    for start, end in groups:
        width = end - start
        if width <= _CARD_MAX:
            counts[width] = counts.get(width, 0) + 1
    if not counts:
        return None
    best = max(counts.values())
    return (min(width for width, count in counts.items() if count == best)
            if best >= 2 else None)


def _card_atoms(groups: list[tuple[int, int]], cut_wide: bool,
                ) -> list[tuple[int, int, int, bool]]:
    """(start, end, group index, whole group?) — every boundary a card may use.

    A group the sender separated is a boundary already. A group WIDER than the
    width the sender's OTHER groups established has lost a separator, and is cut
    in that width («4012 3456 7890 1239…» continues in fours), because that is how
    the digits either side of the missing separator were meant to be grouped.
    These cuts are licensed ONLY by the exact-cover reading, which uses them while
    covering the whole run and so leaves no digit behind; the card-and-neighbour
    reading never uses one, which is what stops a card-shaped window being bitten
    out of a long number. `cut_wide` is False on the bare path, which has no cue to
    license even that.
    """
    step = _grouping_step(groups) if cut_wide else None
    atoms: list[tuple[int, int, int, bool]] = []
    for index, (start, end) in enumerate(groups):
        width = end - start
        if step is not None and step < width:
            at = start
            while at < end:
                stop = min(at + step, end)
                atoms.append((at, stop, index, stop - at == width))
                at = stop
        else:
            atoms.append((start, end, index, True))
    return atoms


def _uniform(atoms: list[tuple[int, int, int, bool]], first: int, last: int,
             step: int | None) -> bool:
    """Whether one number's worth of atoms is written in ONE grouping.

    The sender's own step is the reference, not the piece's own commonest width:
    every group at that width, or those groups and ONE short trailing remainder —
    «4012 3456 7890 1234 565» is a nineteen-digit card, and «4012 3456 7890 1234 5»
    a seventeen-digit one. A short group in the MIDDLE means two widths the sender
    did not write as one number, and a piece that spans one is not that number —
    «12345 67890 4012 3456 7890 1239» once read its first three groups as a
    fourteen-digit card and left the real card in the clear. A range inside a single
    group is uniform by construction: the cut came from the step the surrounding
    groups established, not from a guess about the digits.
    """
    if len({atoms[index][2] for index in range(first, last)}) == 1:
        return True
    widths = [atoms[index][1] - atoms[index][0] for index in range(first, last)]
    if step is None:
        return len(set(widths)) == 1
    if all(width == step for width in widths):
        return True
    return (len(widths) >= 2 and all(width == step for width in widths[:-1])
            and widths[-1] < step)


def _lost_separator(groups: list[tuple[int, int]], step: int | None) -> bool:
    """Whether a CARD-SHAPED group is wider than the sender's own width.

    Such a group is either a card whose separator was lost or the end of one
    number and the start of another, and only an exact cover can tell them apart.
    When there is no cover, using part of it either way leaves some of the
    customer's digits in the model's hands, so the run is refused whole — the
    deliberate cost recorded in the grammar comment.
    """
    return step is not None and any(
        step < end - start <= _CARD_MAX for start, end in groups)


def _dominant_width(groups: list[tuple[int, int]],
                    atoms: list[tuple[int, int, int, bool]],
                    first: int, last: int) -> int:
    """The width of the groups a card piece is written in, commonest first."""
    counts: dict[int, int] = {}
    for index in {atoms[position][2] for position in range(first, last)}:
        width = groups[index][1] - groups[index][0]
        counts[width] = counts.get(width, 0) + 1
    best = max(counts.values())
    return min(width for width, count in counts.items() if count == best)


def _residue_kind(groups: list[tuple[int, int]],
                  atoms: list[tuple[int, int, int, bool]],
                  first: int, last: int, card_width: int) -> str | None:
    """What a residue proves about the number beside the card.

    None = not a number and the reading is refused; «grouping» = its width is
    evidence on its own; «same» = it is written in the card's own width, so only a
    checksum can separate the two readings. Every atom here is a whole group — the
    card-and-neighbour reading works on the sender's own boundaries, never on a
    cut the step made — so a residue is a count of the groups the sender wrote.
    """
    width = sum(atoms[index][1] - atoms[index][0] for index in range(first, last))
    if width >= _CARD_MIN:
        return None
    taken = {atoms[index][2] for index in range(first, last)}
    widths = [groups[group][1] - groups[group][0] for group in taken]
    if len(widths) == 1:
        return "same" if widths[0] == card_width else "grouping"
    if len(set(widths)) == 1 and widths[0] != card_width:
        return "grouping"
    return None


def _card_cover(atoms: list[tuple[int, int, int, bool]], step: int | None,
                ) -> list[tuple[int, int]]:
    """Reading 1: the run tiles EXACTLY into 13..19-digit pieces, or nothing.

    NOT GREEDY, and the difference is reachable: a thirty-two-digit run of fours
    covers as 16+16, and a twenty-nine-digit one whose last separator was lost
    covers as 16+13 or as 13+16 — taking the shortest chunk first would strand the
    other. `reachable[i]` is «the first i atoms are coverable», filled left to
    right; the sizes are then read back from the END, each step taking the SHORTEST
    feasible chunk, so the result is deterministic rather than dependent on which
    cover happened to be found first.
    """
    span = len(atoms)
    reachable = [False] * (span + 1)
    reachable[0] = True
    for first in range(span):
        if not reachable[first]:
            continue
        width = 0
        for last in range(first, span):
            width += atoms[last][1] - atoms[last][0]
            if width > _CARD_MAX:
                break
            if width >= _CARD_MIN and _uniform(atoms, first, last + 1, step):
                reachable[last + 1] = True
    if not reachable[span]:
        return []
    pieces: list[tuple[int, int]] = []
    at = span
    while at:
        width = 0
        for first in range(at - 1, -1, -1):
            width += atoms[first][1] - atoms[first][0]
            if width > _CARD_MAX:
                break
            if (width >= _CARD_MIN and reachable[first]
                    and _uniform(atoms, first, at, step)):
                pieces.append((atoms[first][0], atoms[at - 1][1]))
                at = first
                break
        else:
            return []
    pieces.reverse()
    return pieces


def _one_span(pool: list[tuple[bool, int, int]]) -> list[tuple[int, int]]:
    """The span the pool agrees on, or the one the cue introduces.

    One candidate in the winning class is the answer. Two mean the string carries
    two readings of the same evidence, and the tie-break is explicit rather than
    arbitrary: the card the customer named is the one that STARTS where the cue's
    run starts, so the leftmost window wins; a tie on the start takes the longer
    one. «карта 4012 3456 7890 1239 2024» is the case that forces this — the
    shifted window «3456 7890 1239 2024» passes Luhn too (one coincidence in a
    hundred), and only the cue's adjacency says which of the two was named.
    """
    if not pool:
        return []
    anchored = [item for item in pool if item[0]] or pool
    best = min(anchored, key=lambda item: (item[1], item[1] - item[2]))
    start, end = best[1], best[2]
    return [(start, end)]


def _card_with_neighbour(groups: list[tuple[int, int]],
                         atoms: list[tuple[int, int, int, bool]],
                         chunk: str, base: int, step: int | None,
                         ) -> list[tuple[int, int]]:
    """Reading 2: one card at one end and one number beside it, or nothing.

    The evidence is ORDERED, which is the explicit score: a residue whose width
    differs from the card's proves a boundary by itself, and only a residue in the
    card's own width needs the checksum. The class with the stronger evidence wins
    outright; inside it `_one_span` resolves the remaining ties and refuses a run
    that leaves none of its candidates standing.
    """
    span = len(atoms)
    evidence: list[tuple[bool, int, int]] = []
    checksum: list[tuple[bool, int, int]] = []
    for first in range(span):
        width = 0
        for last in range(first, span):
            width += atoms[last][1] - atoms[last][0]
            if width > _CARD_MAX:
                break
            if width < _CARD_MIN:
                continue
            if (first == 0) == (last + 1 == span):
                continue  # a whole run is `_card_cover`'s; two residues have no reading
            if not _uniform(atoms, first, last + 1, step):
                continue
            res_first, res_last = (last + 1, span) if first == 0 else (0, first)
            kind = _residue_kind(groups, atoms, res_first, res_last,
                                 _dominant_width(groups, atoms, first, last + 1))
            if kind is None:
                continue
            start, end = atoms[first][0], atoms[last][1]
            anchored = first == 0 or atoms[first][3]
            if kind == "grouping":
                evidence.append((anchored, start, end))
            elif validate_luhn(chunk[start - base:end - base]):
                checksum.append((anchored, start, end))
    return _one_span(evidence) if evidence else _one_span(checksum)


def _card_pieces(chunk: str, base: int, cut_wide: bool) -> list[tuple[int, int]]:
    """The card numbers inside ONE maximal digit run, as (start, end) spans.

    `chunk` is the run as written (separators and all) and `base` its offset in the
    whole text, so a piece's digits can be re-read for the checksum. `cut_wide`
    allows a card-shaped group with a lost separator to be cut; the bare path must
    not have it, because with no cue a long run is an order number and the cut is
    what would bite a card out of it.
    """
    if sum(1 for char in chunk if char.isdigit()) > _CARD_RUN_CAP:
        return []
    groups = _digit_groups(chunk, base)
    if not groups:
        return []
    # READING 1 FIRST, and on the cue path with the step's cuts available: a run
    # that tiles exactly is safe by construction, every digit of it covered. The
    # bare path has no cuts, so its tiling is the sender's own groups.
    step = _grouping_step(groups)
    atoms = _card_atoms(groups, cut_wide)
    covered = _card_cover(atoms, step)
    if covered:
        return covered
    if cut_wide and _lost_separator(groups, step):
        # A card-shaped group was cut and no tiling used it, so its digits cannot
        # be split without leaving some of them behind. Nothing in this run is read.
        return []
    # READING 2 on the sender's own boundaries only — a cut the step made is
    # licensed by a whole-run tiling, never by a card-and-neighbour guess.
    return _card_with_neighbour(groups, _card_atoms(groups, False), chunk, base, step)


_PASSPORT_SHAPE_RE = re.compile(r"\b\d{2}[\s-]?\d{2}[\s-]?\d{6}\b")
_SNILS_SHAPE_RE = re.compile(r"\b\d{3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{2}\b")
_CUE_TAIL_RE = re.compile(r"([а-яё]+)\W{0,12}$")


def _damaged_cue_before(text: str, start: int, cues: tuple[str, ...]) -> bool:
    match = _CUE_TAIL_RE.search(text[max(0, start - 30):start].lower())
    if match is None:
        return False
    word = re.sub(r"([а-яё])\1+", r"\1", match.group(1))
    return any(word.startswith(cue) or (len(word) >= 4 and within_one_typo(word[:len(cue)], cue))
               for cue in cues)


_PASSPORT_CTX_RE = re.compile(
    r"(?i:пас{1,2}п{1,2}орт\w*)\D{0,16}?(\d{2}[\s-]?\d{2}[\s-]?\d{6})\b")
# «серия 4607 номер 238914» — the two halves named separately, with words
# between them, so neither the plain shape nor the cue pattern above can see it.
# Both numbers are masked; the words are not, being nobody's data.
_PASSPORT_PARTS_RE = re.compile(
    r"(?i)сери\w*\s*:?\s*(\d{4})\D{1,12}?(\d{6})\b")
_DATE_RE = re.compile(r"\b\d{2}[.\-/]\d{2}[.\-/]\d{4}\b")
# THE FORMAT EVERY MACHINE WRITES, and the one we could not read. A tool result
# comes back as JSON and JSON dates are ISO: «"birth_date": "1955-09-21"». The
# pattern above wants the day first, so 59 dates of birth on AgentPII v3 went to
# the model in the clear — the single largest hole in DOB, and it lives on the
# leg where data arrives from the customer's own systems.
#
# Bounded hard on purpose: a four-digit year beginning 19 or 20, a month 01-12
# and a day 01-31. A looser pattern would read «заказ 2024-15-90» as a date.
_ISO_DATE_RE = re.compile(
    r"(?<!\d)(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)")
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
        # THE BARE POLICY IS UNCHANGED — sixteen digits and a valid checksum —
        # and the pieces are what make it survive a run that holds more than one
        # of them. A run that is not a card sequence yields no pieces, so a
        # twenty-digit account is still refused whole.
        for start, end in _card_pieces(match.group(), match.start(), cut_wide=False):
            run = text[start:end]
            if len(_digits(run)) == 16 and validate_luhn(run):
                spans.append(Span(start, end, "CARD", run))
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
    for entity_type, pattern in (("SNILS", _SNILS_CUE_RE), ("INN", _INN_CUE_RE)):
        for match in pattern.finditer(text):
            spans.append(Span(match.start(1), match.end(1), entity_type, match.group(1)))
    # A CUE CAN TYPE SEVERAL CARDS. The run after it is read once and split by
    # the card grammar; the cue is the evidence, so no checksum is asked for here
    # — a mistyped card the customer named is still their card.
    for match in _CARD_CUE_RE.finditer(text):
        for start, end in _card_pieces(match.group(1), match.start(1), cut_wide=True):
            spans.append(Span(start, end, "CARD", text[start:end]))
    # THE CUE ITSELF MAY BE DAMAGED — «паспрот 0312943300», «сннилс 40621994460»,
    # «паспоот 4119424336» — and the shape alone is refused on purpose (a bare
    # ten-digit number collides with everything). One typo or a stretched
    # letter in the cue is still the cue.
    for entity_type, shape, cues in (
            ("PASSPORT", _PASSPORT_SHAPE_RE, ("паспорт", "пасспорт")),
            ("SNILS", _SNILS_SHAPE_RE, ("снилс",))):
        for match in shape.finditer(text):
            if _damaged_cue_before(text, match.start(), cues):
                spans.append(Span(match.start(), match.end(), entity_type, match.group()))
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
    for match in _ISO_DATE_RE.finditer(text):
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
