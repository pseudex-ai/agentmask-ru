"""What the model actually saw where a value used to be.

The harness knows the original message and the gold spans; the masker hands
back a masked message. To score anything we must project each gold span onto
the masked text and read what stands there — the SUBSTITUTE. Everything the
benchmark measures rests on this projection, so it is written to be boring
and its failure modes are unit tests.

METHOD. `difflib.SequenceMatcher` over the two strings, then three repairs
that a raw opcode list gets wrong on this data:

  1. A tiny `equal` run inside a replacement is noise. «89071234567» against
     «<PHONE_1>» matches the «1» in the middle and splits one replacement
     into three; runs shorter than three characters between two non-equal
     blocks are folded into the replacement.
  2. A gold boundary that lands inside a non-equal block snaps to that
     block's masked edges — the masker replaced a region, and the substitute
     is that whole region.
  3. ALTERED IS DECIDED BY COMPARISON, NOT BY OPCODES. A masker that only
     normalises whitespace, or «ё» to «е», changes the opcodes and protects
     nothing. `norm` folds those away and the value counts as altered only
     if it survives the fold as a different string.

REWRITE RATIO. Characters changed OUTSIDE the gold and negative spans, over
all such characters. A masker that rewrites the whole sentence would make
every projection meaningless, so the harness records the ratio and the
report prints it; above 0.3 the case is flagged rather than silently scored.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

_MIN_EQUAL_RUN = 3


def norm(text: str) -> str:
    """Fold the differences that protect nobody: unicode form, case, «ё»,
    and runs of whitespace."""
    folded = unicodedata.normalize("NFC", text).casefold().replace("ё", "е")
    return " ".join(folded.split())


@dataclass(frozen=True)
class Block:
    tag: str        # "equal" | "replace" | "delete" | "insert"
    a1: int
    a2: int
    b1: int
    b2: int


@dataclass(frozen=True)
class Substitute:
    """What stands in the masked text where a gold span used to be."""

    text: str
    altered: bool       # the masker put something else there
    covered: bool       # no PIECE of the real value survived into it
    shared: bool        # another gold span sits in the same changed block


def blocks(original: str, masked: str) -> list[Block]:
    raw = SequenceMatcher(None, original, masked, autojunk=False).get_opcodes()
    merged: list[Block] = []
    for tag, a1, a2, b1, b2 in raw:
        block = Block(tag, a1, a2, b1, b2)
        # Fold a short `equal` run that sits between two changed blocks.
        if (
            block.tag == "equal"
            and (a2 - a1) < _MIN_EQUAL_RUN
            and merged
            and merged[-1].tag != "equal"
        ):
            previous = merged.pop()
            merged.append(Block("replace", previous.a1, a2, previous.b1, b2))
            continue
        if merged and merged[-1].tag != "equal" and block.tag != "equal":
            previous = merged.pop()
            merged.append(Block("replace", previous.a1, a2, previous.b1, b2))
            continue
        merged.append(block)
    return merged


def project_many(original: str, masked: str, spans: list[tuple[int, int]]) -> list[Substitute]:
    """Project several gold spans of ONE message at once.

    WHY THIS EXISTS AND `project` ALONE IS NOT ENOUGH. Two gold spans that
    sit next to each other — an address and the name right after it — are
    replaced by substitutes that also sit next to each other, and difflib
    sees ONE changed block covering both. Asked separately, each span then
    claims the whole block, so the name comes back as «. 101 Алиса
    Фролова»: the tail of the address plus the name. The scripted model
    copies that into the tool call and the round trip fails for a reason
    that is entirely the instrument's.

    So a block covering more than one gold span is DIVIDED between them,
    at the nearest word boundary to the proportional point, and every span
    that had to share is marked `shared`.

    THE MARK IS THE POINT, NOT THE SPLIT. No alignment can know where one
    substitute ends inside a single replacement; the division keeps one
    span from swallowing its neighbour's substitute, but the result is a
    guess. An instrument that cannot attribute a value must not score it,
    so the harness excludes shared items from the round-trip lines and the
    report prints how many there were.
    """
    if not spans:
        return []
    order = sorted(range(len(spans)), key=lambda i: spans[i][0])
    parts = blocks(original, masked)
    # (span index, block index) -> the slice of that block's masked side
    # this span may read. Only blocks shared by two or more spans appear.
    shares: dict[tuple[int, int], tuple[int, int]] = {}
    for b, block in enumerate(parts):
        if block.tag == "equal":
            continue
        inside = [i for i in order if spans[i][0] < block.a2 and block.a1 < spans[i][1]]
        if len(inside) < 2:
            continue
        span_a = block.a2 - block.a1
        span_b = block.b2 - block.b1
        cuts = [block.b1]
        for i in inside[:-1]:
            share = (min(spans[i][1], block.a2) - block.a1) / span_a if span_a else 0.0
            cuts.append(_snap(masked, block.b1 + round(share * span_b), block.b1, block.b2))
        cuts.append(block.b2)
        for k, i in enumerate(inside):
            shares[(i, b)] = (cuts[k], cuts[k + 1])
    return [
        _project_one(original, masked, parts, start, end,
                     {b: v for (i, b), v in shares.items() if i == index},
                     tuple(s for j, s in enumerate(spans) if j != index))
        for index, (start, end) in enumerate(spans)
    ]


def _snap(text: str, position: int, low: int, high: int) -> int:
    """Move a cut to the nearest word boundary inside [low, high].

    A proportional cut lands wherever the arithmetic says — in the middle
    of «кв. 101», giving one span «кв. 1» and the next «01». Substitutes
    are separated by whitespace like everything else, so the nearest space
    is a better guess than the exact ratio, and it keeps a number whole.
    """
    for distance in range(0, high - low + 1):
        for candidate in (position - distance, position + distance):
            if candidate in (low, high):
                return candidate
            # Cut AFTER the space: the left span keeps its last word, the
            # right one starts at its first, and neither carries the gap.
            if low < candidate < high and text[candidate].isspace():
                return candidate
    return position


def project(original: str, masked: str, start: int, end: int) -> Substitute:
    """Read the masked text where `original[start:end]` used to be."""
    return _project_one(original, masked, blocks(original, masked), start, end, {}, ())


def _project_one(original: str, masked: str, parts: list[Block], start: int, end: int,
                 shares: dict[int, tuple[int, int]], neighbours: tuple[tuple[int, int], ...]) -> Substitute:
    value = original[start:end]
    b_start: int | None = None
    b_end: int | None = None
    untouched = 0
    for index, block in enumerate(parts):
        if block.a2 <= start or block.a1 >= end:
            continue
        if block.tag == "equal":
            overlap_a1 = max(block.a1, start)
            overlap_a2 = min(block.a2, end)
            untouched += overlap_a2 - overlap_a1
            low = block.b1 + (overlap_a1 - block.a1)
            high = block.b1 + (overlap_a2 - block.a1)
        else:
            # A changed block that touches the span contributes all of its
            # masked side: the masker decided that region as a whole. When
            # another gold span shares this block, only this span's share.
            low, high = shares.get(index, (block.b1, block.b2))
        b_start = low if b_start is None else min(b_start, low)
        b_end = high if b_end is None else max(b_end, high)
    if b_start is None or b_end is None:
        return Substitute(text="", altered=True, covered=True, shared=bool(shares))
    # A PURE INSERT TOUCHING THE SPAN BELONGS TO IT. difflib matched «мит»
    # between «ханна смит» and «Дмитрий Ковалёв» — three coincidental letters
    # — so the substitute ended at «Дмит» and the rest of the name arrived as
    # an insert just past the span's end. The scripted model then copied a
    # fragment into the tool call and the round trip failed for a reason that
    # belongs entirely to the instrument. An insert is zero-width on the
    # original side, so it can only be claimed by a span it touches; one that
    # touches a NEIGHBOUR's boundary too is left alone rather than stolen.
    for block in parts:
        if block.tag != "insert" or block.a1 != block.a2:
            continue
        if not start <= block.a1 <= end:
            continue
        if any(other_start <= block.a1 <= other_end for other_start, other_end in neighbours):
            continue
        if block.b1 == b_end:
            b_end = block.b2
        elif block.b2 == b_start:
            b_start = block.b1
    text = masked[b_start:b_end].strip()
    altered = not _same_value(text, value)
    return Substitute(text=text, altered=altered, covered=altered and not surviving_pieces(value, text),
                      shared=bool(shares))


def digits_of(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


# Characters that only format a number: a phone may gain or lose any of
# them and still be the same phone. A LETTER is not one of them, which is
# what keeps «8 935 7476622-ерунда» from passing as the number.
_SEPARATORS = frozenset(" -()+.,\u00a0\t")


def is_number_like(text: str) -> bool:
    """True when the text is digits and separators only."""
    stripped = [ch for ch in text if ch not in _SEPARATORS]
    return bool(stripped) and all(ch.isdigit() for ch in stripped)


def _same_value(produced: str, value: str) -> bool:
    """Is what stands there still the value, for protection purposes?

    Beyond the `norm` fold, a number that kept its digits is still that
    number: a masker that turns «8 907 123 45 67» into «89071234567» has
    reformatted the phone, not hidden it, and the model can read it. Six
    digits is the floor — below that the digits are a house number or an
    amount, where an equal digit string is a coincidence, not an identity.
    Both sides must be number-LIKE: a value with letters attached is not
    the same number in another format.
    """
    if norm(produced) == norm(value):
        return True
    value_digits = digits_of(value)
    if len(value_digits) < 6 or not is_number_like(value) or not is_number_like(produced):
        return False
    return digits_of(produced) == value_digits


# A piece worth calling a leak: a word of three letters or more, or a run of
# three digits or more. Shorter than that and the «survivor» is a preposition
# or the «+7» every Russian phone starts with.
_PIECE = re.compile(r"[^\W\d_]{3,}|\d{3,}", re.UNICODE)


def surviving_pieces(value: str, substitute: str) -> list[str]:
    """Pieces of the real value that are still readable in the substitute.

    COVERAGE CANNOT BE A CHARACTER COUNT. A format-preserving substitute
    shares characters with the value by construction — «+7 907 123-45-67»
    and «+7 935 476-22-11» agree on the plus, the seven and every dash —
    and a character-level rule would call that a partial leak. What leaks
    is a PIECE: «Кузнецов Дмитрий» masked as «Кузнецов <NAME_1>» hands the
    model the surname, and that is what this finds.
    """
    folded = norm(substitute)
    return [piece for piece in _PIECE.findall(norm(value)) if piece in folded]


def rewrite_ratio(original: str, masked: str, protected: list[tuple[int, int]]) -> float:
    """Share of characters changed outside the protected spans."""
    inside = set()
    for start, end in protected:
        inside.update(range(start, end))
    outside_total = len(original) - len(inside)
    if outside_total <= 0:
        return 0.0
    changed = 0
    for block in blocks(original, masked):
        if block.tag == "equal":
            continue
        changed += sum(1 for i in range(block.a1, block.a2) if i not in inside)
    return changed / outside_total
