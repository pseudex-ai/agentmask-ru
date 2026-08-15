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
