"""Extract the Russian name dictionaries into data files we own.

`names.py` shipped a compact seed list with a note to swap in the full
dictionaries in production. Measured against NEREL — an externally annotated
corpus — that seed list caught 72% of person mentions; the misses were almost
entirely names it had never heard of.

The dictionaries come from the `russiannames` package (32k given names, 375k
surnames, 48k patronymics, each with a frequency count). They are EXTRACTED into
plain text files under `licensing/data/` rather than imported at runtime, for
two reasons:

  * the licensing layer leases detection assets into the customer's container
    instead of shipping them on disk, and a pip dependency cannot be leased;
  * a build step lets us filter the data, and the raw tail needs filtering —
    it contains single characters and transliteration artefacts that would
    become false positives.

After regenerating, rebuild the bundle (`python3 -m licensing.pack`) — its version
is the content hash, so a changed dictionary is a new bundle version by itself.

usage: python3 build_name_dicts.py [--min-surname-count 2]
"""

import argparse
import sys
from pathlib import Path

# Written into the LICENSING package, not into the engine. These dictionaries are
# the product: they are packed into the leased bundle and must never end up on a
# customer's disk, so the one place they may live is the side that never ships.
_OUT = Path(__file__).resolve().parent.parent / "licensing" / "data"


def _drop_ordinary_words(words: list[str]) -> list[str]:
    """Remove entries that are ordinary Russian words.

    The dictionary contains real names that are also common nouns — `майор`,
    `роман`, `вера`, `муза`. Matching those would mask `начнём роман с клиентом`
    and `вера в успех`, i.e. trade recall for the over-masking that breaks tool
    calls. They are dropped from the BULK dictionary only; the curated seed list
    in names.py still carries the common given names among them, so a person
    called Вера is still caught by the path that always handled her."""
    import pymorphy3

    morph = pymorphy3.MorphAnalyzer()
    kept = []
    for word in words:
        parse = morph.parse(word)[0]
        name_tagged = {"Name", "Surn", "Patr"} & set(parse.tag.grammemes)
        if parse.is_known and not name_tagged:
            continue
        kept.append(word)
    return kept


def _clean(values, min_length: int) -> list[str]:
    """Keep plausible Cyrillic name forms, lowercased and de-duplicated."""
    out = set()
    for value in values:
        if not isinstance(value, str):
            continue
        word = value.strip().lower().strip("-")
        if len(word) < min_length:
            continue
        # EVERY letter must be Cyrillic. "any Cyrillic" was tried and let through
        # source-data homoglyphs like `cавельев` (Latin c + Cyrillic tail), which
        # would never match real text yet bloat the dictionary. Latin-script names
        # are handled by their own rule, not here.
        if not all(("а" <= char <= "я" or char == "ё" or char == "-") for char in word):
            continue
        out.add(word)
    return sorted(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    # Surnames have a very long tail (375k); the rare end is dominated by
    # one-off spellings and OCR noise. Given names are kept in full — 32k is
    # small and given-name variety is exactly what the seed list lacked.
    parser.add_argument("--min-surname-count", type=int, default=2)
    args = parser.parse_args()

    try:
        import pandas as pd
        import russiannames
    except ImportError as error:
        raise SystemExit(
            "needs the source dictionaries: pip install russiannames pandas pyarrow"
        ) from error

    data = Path(russiannames.__file__).parent / "data"
    _OUT.mkdir(parents=True, exist_ok=True)

    names = pd.read_parquet(data / "names.parquet")
    surnames = pd.read_parquet(data / "surnames.parquet")
    surnames = surnames[surnames["count"] >= args.min_surname_count]

    written = {}
    for filename, values, min_length in (
        ("first_names.txt", names["text"], 2),
        # Female forms are separate entries in the source and are what actually
        # appears in Russian text about women, so both columns are taken.
        ("surnames.txt", list(surnames["text"]) + list(surnames["f_form"]), 3),
    ):
        cleaned = _drop_ordinary_words(_clean(values, min_length))
        (_OUT / filename).write_text("\n".join(cleaned), encoding="utf-8")
        written[filename] = len(cleaned)

    for filename, count in written.items():
        size = (_OUT / filename).stat().st_size / 1024
        print(f"{filename:<18}{count:>8} entries{size:>10.0f} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
