"""Build a message and the offsets of its tracked slots in one pass.

A plain `str` is literal text; a `Slot` is a value whose span is recorded.
Computing offsets DURING assembly rather than by searching the finished string
is what keeps the ground truth honest: a search finds the first occurrence,
and a message that mentions the same phone twice would then carry a span
pointing at the wrong one. There is deliberately no post-processing pass over
the finished message — stripping a comma after assembly shifts every span
computed before it, and a corpus whose spans sit one character to the left
still scores, and scores wrongly. Register belongs in the template and in the
slot values, both chosen before this function counts a single character.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    key: str
    value: str


@dataclass(frozen=True)
class Assembled:
    text: str
    spans: dict[str, tuple[int, int]]


def assemble(parts: list[str | Slot]) -> Assembled:
    out: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for part in parts:
        if isinstance(part, Slot):
            if part.key in spans:
                raise ValueError(f"slot {part.key!r} used twice in one message")
            spans[part.key] = (cursor, cursor + len(part.value))
            out.append(part.value)
            cursor += len(part.value)
        else:
            out.append(part)
            cursor += len(part)
    return Assembled(text="".join(out), spans=spans)
