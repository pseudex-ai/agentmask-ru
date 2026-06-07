"""Layer 0: offset-safe text normalization to defeat obfuscation before detection.

Every substitution is 1 char -> 1 char (length-preserving), so detection offsets
map straight back to the ORIGINAL text — no fragile remapping. NFKC is NOT used
for the homoglyph fold (it does not map Cyrillic «О» U+041E -> 0; different
script). Instead a TARGETED look-alike->digit fold is applied ONLY next to digits,
so real Cyrillic in names is never touched.
"""

import re

_DASH_RE = re.compile("[‐‑‒–—―−­]")  # ‐‑‒–—―−, soft hyphen
_SPACE_RE = re.compile("[         ]")
_ZW_RE = re.compile("[​‌‍﻿]")

# Cyrillic / Greek / Latin glyphs that look like digits.
_LOOKALIKE: dict[str, str] = {
    "О": "0", "о": "0", "O": "0", "o": "0", "Ο": "0", "о": "0",
    "З": "3", "з": "3",
    "б": "6", "Б": "6",
    "Ч": "4", "ч": "4",
    "I": "1", "l": "1", "І": "1", "і": "1",
    "B": "8", "В": "8",
}


def normalize(text: str) -> str:
    """Return text with dashes/spaces/zero-width canonicalized and digit
    look-alikes folded to ASCII digits next to numbers. Same length as input."""
    text = _DASH_RE.sub("-", text)
    text = _SPACE_RE.sub(" ", text)
    text = _ZW_RE.sub(" ", text)  # replace (not delete) -> length preserved
    chars = list(text)
    for index, char in enumerate(chars):
        replacement = _LOOKALIKE.get(char)
        if replacement is None:
            continue
        prev = _neighbor(chars, index, -1)
        nxt = _neighbor(chars, index, 1)
        if prev.isdigit() or nxt.isdigit() or prev in "+()":
            chars[index] = replacement
    return "".join(chars)


def _neighbor(chars: list[str], index: int, step: int) -> str:
    """Nearest non-space character in the given direction, or empty string."""
    position = index + step
    while 0 <= position < len(chars):
        if not chars[position].isspace():
            return chars[position]
        position += step
    return ""
