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
    covered: bool       # no character of the span survived untouched


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


def project(original: str, masked: str, start: int, end: int) -> Substitute:
    """Read the masked text where `original[start:end]` used to be."""
    value = original[start:end]
    parts = blocks(original, masked)
    b_start: int | None = None
    b_end: int | None = None
    untouched = 0
    for block in parts:
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
            # masked side: the masker decided that region as a whole.
            low, high = block.b1, block.b2
        b_start = low if b_start is None else min(b_start, low)
        b_end = high if b_end is None else max(b_end, high)
    if b_start is None or b_end is None:
        return Substitute(text="", altered=True, covered=True)
    text = masked[b_start:b_end]
    altered = not _same_value(text, value)
    return Substitute(text=text, altered=altered, covered=altered and untouched == 0)


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
