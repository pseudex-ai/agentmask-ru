"""The single pymorphy3 analyzer, shared by every module that needs morphology.

It exists as its own module for one reason: `names.py` and `assets.py` both need
it, and `names.py` imports `assets.py`. Keeping the analyzer in `names.py` (where
it used to live) would make that a cycle. Constructing a second analyzer instead
is not an option — it loads the whole dictionary again, ~100 MB per worker.

pymorphy3 is a third-party open dictionary, not a leased asset: it ships inside
the image like natasha's models do.
"""

import pymorphy3

MORPH = pymorphy3.MorphAnalyzer()


def is_stretched_filler(word: str) -> bool:
    """Растянутый речевой филлер: «нуу», «иии», «аааа», «эээ».

    ФОРМА, А НЕ СПИСОК. Живая речь тянет гласную произвольно, и список пришлось
    бы дописывать после каждого корпуса. У филлера не больше двух различных
    букв, он длиннее двух символов и словарю неизвестен — обычного русского
    слова такой формы не существует. «ааа» и «эээ» словарь знает сам и метит
    междометием, их ловит проверка части речи там, где она уместна.

    Живьём филлер попадал ВНУТРЬ спана и уезжал в инструмент вместе со
    значением: «аааа ленина двадцать семь», «иии ерохин».
    """
    # «ии» — one letter held for a beat — is two characters long and a filler
    # all the same; it joined a name as its first word on a fresh corpus.
    if len(word) < 2 or (len(word) == 2 and len(set(word.lower())) != 1) or len(set(word.lower())) > 2:
        return False
    # ONE LETTER HELD is a filler whatever the dictionary says: it knows «ии»
    # as a rare given name, and «ноль два ии саркисян карен» is not her.
    if len(set(word.lower())) == 1:
        return True
    # A LATIN WORD IS NOT JUDGED BY THE RUSSIAN DICTIONARY. «anna», «alla»,
    # «emma», «nell» carry two distinct letters and pymorphy does not know the
    # Latin string, so `parses[0].is_known` called every one of them a filler —
    # and the join that keeps fillers OUT of a name deleted the given-name half
    # before any rule could judge the surname beside it. The dictionary is
    # evidence about the language it describes; asking it about another script
    # answers "unknown", which is not "filler".
    if not any("а" <= char <= "я" or char == "ё" for char in word.lower()):
        return False
    parses = MORPH.parse(word)
    return not (parses and parses[0].is_known)
