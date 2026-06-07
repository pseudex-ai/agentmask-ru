"""Make natasha use pymorphy3 instead of the unmaintained pymorphy2.

pymorphy2 needs `pkg_resources` (removed from modern setuptools / Python 3.14),
so `MorphVocab()` (and thus AddrExtractor) crashes with it. pymorphy3 exposes the
same `MorphAnalyzer(result_type=...)` / `Parse` API, so aliasing the import names
makes natasha construct a pymorphy3 analyzer transparently.

IMPORT THIS BEFORE ANY `from natasha import ...` so the alias is active when
`natasha.morph.vocab` binds to `pymorphy2.analyzer` at module-load time.
Verified-in-the-wild fix (evenikkal/hhanalyst, RussianNLP/DRAGON pair the same).
"""

import sys

import pymorphy3
import pymorphy3.analyzer

sys.modules["pymorphy2"] = pymorphy3
sys.modules["pymorphy2.analyzer"] = pymorphy3.analyzer
