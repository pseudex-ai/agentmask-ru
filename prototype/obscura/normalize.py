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
    # Fold look-alikes to digits ONLY inside a phone/ID-like region: a maximal run
    # of [digits | look-alikes | phone separators] containing >=5 real digits.
    # This catches obfuscated phones/IDs even when the look-alike sits at a group
    # boundary ("8-924-45О-56-12", "8 935 О44 69 47"), while a short house letter
    # ("156Б" -> 3 digits) and any alphabetic word ("Циолковского") — whose real
    # letters break the run — are left untouched.
    chars = list(text)
    n = len(chars)
    index = 0
    while index < n:
        if not _in_region_alpha(chars[index]):
            index += 1
            continue
        end = index
        while end < n and _in_region_alpha(chars[end]):
            end += 1
        if sum(1 for c in chars[index:end] if c.isdigit()) >= 5:
            for k in range(index, end):
                if chars[k] in _LOOKALIKE:
                    chars[k] = _LOOKALIKE[chars[k]]
        index = end
    return "".join(chars)


_SEPARATORS = frozenset(" -+()")


def _in_region_alpha(char: str) -> bool:
    """A char that can be part of a phone/ID number region."""
    return char.isdigit() or char in _LOOKALIKE or char in _SEPARATORS
