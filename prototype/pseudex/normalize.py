"""Layer 0: offset-safe text normalization to defeat obfuscation before detection.

Every substitution is 1 char -> 1 char (length-preserving), so detection offsets
map straight back to the ORIGINAL text — no fragile remapping. NFKC is NOT used
for the homoglyph fold (it does not map Cyrillic «О» U+041E -> 0; different
script). Instead a TARGETED look-alike->digit fold is applied ONLY next to digits,
so real Cyrillic in names is never touched.
"""

import re

from pseudex.assets import ASSETS

_DASH_RE = re.compile("[‐‑‒–—―−­]")  # ‐‑‒–—―−, soft hyphen
_SPACE_RE = re.compile("[         ]")
_ZW_RE = re.compile("[​‌‍﻿]")

# The digit look-alike table is LEASED (pseudex/assets.py): WHICH glyphs an
# obfuscator actually substitutes is a tuned list, not a published fact.


# Latin letters that are visually identical to a Cyrillic one. Unlike the digit
# look-alike table this is NOT leased: that one is a tuned guess at what an
# obfuscator substitutes, while this is the published Unicode confusables set for
# the Cyrillic/Latin pair — an algorithm input, not our research.
#
# The fold exists because of a typing accident, not an attack. A keyboard that
# switches layout mid-word produces «пpоспект», «yлица», «Прoфсоюзная»; the words
# are indistinguishable on screen and invisible to every Cyrillic pattern. Chat
# traffic is full of them: on AgentPII-RU's sloppy register they accounted for
# every remaining address miss.
_LATIN_TO_CYRILLIC = {
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у",
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М",
    "O": "О", "P": "Р", "T": "Т", "X": "Х", "Y": "У",
}


def _fold_latin_in_cyrillic(chars: list[str]) -> None:
    """Fold Latin look-alikes INSIDE a Cyrillic word. Mutates in place, 1:1.

    The guard is that the run must already hold at least two real Cyrillic
    letters. Without it every English word made of these letters — `code`,
    `type`, `access` — would be rewritten into Cyrillic, and an email address, a
    URL or an API key would be destroyed. Two Cyrillic letters is enough to say
    the word is Russian and the Latin one is the accident.
    """
    n = len(chars)
    index = 0
    while index < n:
        if not (chars[index].isalpha()):
            index += 1
            continue
        end = index
        while end < n and chars[end].isalpha():
            end += 1
        run = chars[index:end]
        cyrillic = sum(1 for c in run if "\u0400" <= c <= "\u04FF")
        if cyrillic >= 2:
            for k in range(index, end):
                if chars[k] in _LATIN_TO_CYRILLIC:
                    chars[k] = _LATIN_TO_CYRILLIC[chars[k]]
        index = end


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
    lookalike = ASSETS.get().lookalike
    chars = list(text)
    n = len(chars)
    index = 0
    while index < n:
        if not _in_region_alpha(chars[index], lookalike):
            index += 1
            continue
        end = index
        while end < n and _in_region_alpha(chars[end], lookalike):
            end += 1
        if sum(1 for c in chars[index:end] if c.isdigit()) >= 5:
            for k in range(index, end):
                if chars[k] in lookalike:
                    chars[k] = lookalike[chars[k]]
        index = end
    _fold_latin_in_cyrillic(chars)
    return "".join(chars)


_SEPARATORS = frozenset(" -+()")


def _in_region_alpha(char: str, lookalike: dict[str, str]) -> bool:
    """A char that can be part of a phone/ID number region."""
    return char.isdigit() or char in lookalike or char in _SEPARATORS
