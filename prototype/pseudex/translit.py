"""Transliteration and initials of a name — the DERIVED forms a model writes.

A model asked for a cardholder or a `name_latin` field transliterates the
substitute it read, and asked for initials it abbreviates it; neither string
is the token, so neither resolved, and the customer's tool or the customer's
reply received «TSVETKOV VSEVOLOD» and «Ж.М.» derived from a person who does
not exist (59 of 355 replies on the v4 small run). The vault indexes these
forms at mint time — a few rows per person — and the restore leg answers with
the SAME derivation of the real value.

Four tables, because four standards are in daily use and a Russian document
or card may carry any of them: ICAO Doc 9303 (МВД since 2014 for passports),
ГОСТ 7.79-2000 system B, the 2010 МВД table, and the everyday spelling that
banks and CRMs print. `bench/agentpii4/derive.py` holds its own copy on
purpose — the instrument must not agree with the engine by construction.
"""
from __future__ import annotations

ICAO: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "ie", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
GOST_B: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "cz", "ч": "ch", "ш": "sh", "щ": "shh",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
MVD_2010: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "tc", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
COMMON: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
TABLES: tuple[dict[str, str], ...] = (ICAO, GOST_B, MVD_2010, COMMON)


def apply(table: dict[str, str], word: str) -> str:
    """One word through one table, lowercase, letters only."""
    out = "".join(table.get(letter, letter) for letter in word.lower())
    return "".join(ch for ch in out if ch.isalpha())


def variants(word: str) -> frozenset[str]:
    """Every Latin spelling of one Cyrillic word under the four tables."""
    if not word or not any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in word):
        return frozenset()
    return frozenset(apply(table, word) for table in TABLES)


def table_for(cyrillic: str, latin: str) -> dict[str, str] | None:
    """The table that spells `cyrillic` as `latin`, or None."""
    wanted = "".join(ch for ch in latin.lower() if ch.isalpha())
    for table in TABLES:
        if apply(table, cyrillic) == wanted:
            return table
    return None


def match_case(pattern: str, produced: str) -> str:
    """`produced` in the letter case `pattern` uses: all caps, capitalised, or lower."""
    letters = [ch for ch in pattern if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return produced.upper()
    if letters and letters[0].isupper():
        return produced[:1].upper() + produced[1:]
    return produced


def squeezed_initials(words: tuple[str, ...]) -> str:
    """«жм» for («Жанна», «Михайловна») — the index key of a pair of initials."""
    return "".join(word[:1].lower() for word in words if word)
