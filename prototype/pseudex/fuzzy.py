"""One-edit matching, shared by the name layer and the address layer.

Both layers need the same two things — "is this word one typo away from
something in a leased dictionary" and "which bucket do I have to look in" — and
before this module the name layer owned the only copy. A second copy in
`address.py` would be a second place for the bucket key and the distance rule to
drift apart, and they must not: the bucket key is only correct BECAUSE it agrees
with the distance rule about what a single edit can do.

TWO DISTANCES, NOT ONE WITH A FLAG. `within_one_edit` is plain Levenshtein-1;
`within_one_typo` also admits ONE adjacent transposition (Damerau-1). They are
separate functions because they are used where different evidence is available:

  * the name layer has ONE dictionary signal plus "unknown to morphology", so it
    stays on the narrower distance — the transposition neighbourhood of a 197k
    dictionary is extra surface for no measured gain there;
  * the street layer conjoins THREE signals (a type word, the vocabulary, and
    address intent), so it can afford the wider one — and it needs it, because
    measured on the noise ladder half the damage to a street name is a
    transposition rather than a deletion. «уилце» is not one Levenshtein edit
    from «улиц»; it is one keystroke away from it.
"""

import hashlib
from array import array
from bisect import bisect_left

import numpy



def within_one_edit(word: str, other: str) -> bool:
    """Levenshtein distance ≤ 1, decided without building a matrix.

    Stops at the SECOND difference. The whole-word scan it replaced was the
    difference between 13.65 ms and a fraction of one on a large bucket: almost
    every candidate differs immediately, and finishing the word to learn that is
    work spent on a decision already made.
    """
    if abs(len(word) - len(other)) > 1:
        return False
    if len(word) == len(other):
        seen = False
        for left, right in zip(word, other):
            if left == right:
                continue
            if seen:
                return False
            seen = True
        return True
    shorter, longer = (word, other) if len(word) < len(other) else (other, word)
    index = 0
    while index < len(shorter) and shorter[index] == longer[index]:
        index += 1
    return shorter[index:] == longer[index + 1:]


def within_one_typo(word: str, other: str) -> bool:
    """Damerau-Levenshtein ≤ 1: one insert, delete, substitute OR SWAP.

    The swap is the addition, and it is not a nicety. A phone keyboard and a
    hurried hand produce transpositions at about the same rate as dropped
    letters — measured on the noise ladder's own corruption model, which makes
    the two equally likely — and plain Levenshtein calls a transposition TWO
    edits, so «уилце», «улиец», «порспекте» and «гагариан» were all invisible
    to a rule written to tolerate one.

    Only ADJACENT pairs swap. Allowing a swap at a distance would make every
    anagram a match, and «Ленина»/«Нелина» is not a typo of anything.
    """
    if within_one_edit(word, other):
        return True
    if len(word) != len(other):
        return False
    differences = [index for index, (left, right) in enumerate(zip(word, other))
                   if left != right]
    return (len(differences) == 2
            and differences[1] == differences[0] + 1
            and word[differences[0]] == other[differences[1]]
            and word[differences[1]] == other[differences[0]])


def deletion_keys(word: str) -> tuple[str, ...]:
    """The word itself and every string one deletion away from it.

    THE DELETION NEIGHBOURHOOD, and it replaces a first-three/last-three bucket
    index that did not do what its own docstring promised. Two strings are within
    one edit — insert, delete, substitute OR transpose — exactly when their
    deletion neighbourhoods intersect, so indexing both sides by this set makes
    the lookup COMPLETE rather than merely usually right.

    Measured on our own dictionaries (223 544 entries, 39 600 single corruptions,
    `bench/blocking_recall.py`), the scheme it replaces reached the source word
    only:

        length 3   12.6%      length 5   77.9%      length 7+  100%
        length 4   46.2%      length 6   95.1%      overall     96.6%

    which is not a rounding error but a class: given names are 49.2% six letters
    or shorter against 18.8% for surnames, so their blocking recall was 90.2%
    while surnames sat at 97.3%. «ольга» -> «олга» is the canonical miss — a
    deletion at index 2, where the prefix and suffix windows overlap and the edit
    destroys both keys at once.

    The old arithmetic ("an edit at position p is caught by the first key when
    p >= 3 and by the last when p < len - 3") is sound for insert, delete and
    substitute, and it was written before the distance function gained
    transpositions: a swap at position 2 of a six-letter word corrupts prefix and
    suffix together, which is the missing 4.9% at that length.

    Mor-Fraenkel (1982); the same construction SymSpell popularised. Boytsov's
    comparative study measures it fastest of fourteen methods at k=1 on synthetic
    RUSSIAN at our exact scale (0.2M entries, average length 10.5) —
    http://boytsov.info/pubs/jea2011.pdf, Table VII. Measured here: 5.1 candidates
    verified per lookup against 2812.6, and 3.3 us against 245.0.

    The price is index size — 9x the vocabulary in postings rather than 2x — and
    at our scale that is two million small strings, which is nothing. The 140x
    blowup this construction is known for is a k<=2 figure; at k=1 the index is
    (average length + 1) x N by construction.
    """
    keys = [word]
    keys.extend(word[:i] + word[i + 1:] for i in range(len(word)))
    return tuple(dict.fromkeys(keys))


# A 64-bit digest of a key, not the key itself. The deletion neighbourhood is
# complete but LARGE — 1.58 million keys over our name dictionaries — and a
# Python dict of that many strings costs 456 MB of resident memory, measured, per
# worker. At one worker per core that is the whole machine spent on an index.
#
# Hashing loses nothing here because a hit is VERIFIED afterwards by
# `within_one_typo` against the real string: a collision costs one extra distance
# computation and can never produce a wrong answer. That is the property that
# makes the compact form free rather than a trade.
_DIGEST = hashlib.blake2b


def _key_digest(key: str) -> int:
    return int.from_bytes(_DIGEST(key.encode(), digest_size=8).digest(), "big")


def _typed(code: str, values) -> array:
    """A stdlib array filled from a numpy buffer without going through ints."""
    out = array(code)
    out.frombytes(values.tobytes())
    return out


class DeletionIndex:
    """A deletion-neighbourhood index in three flat arrays.

    Keys are sorted 64-bit digests searched by bisection; postings are indices
    into the vocabulary, laid out end to end with an offset per key — the shape a
    sparse matrix uses, for the same reason. Nothing here holds a Python object
    per entry, which is where the 456 MB went.

    Measured on the name dictionaries: 1.58 M keys and 1.98 M postings in 27 MB
    against 456 MB, with lookup unchanged in behaviour and faster in practice
    because a bisection over one array beats hashing a string and chasing a
    bucket of pointers.
    """

    __slots__ = ("_words", "_keys", "_offsets", "_postings")

    def __init__(self, words) -> None:
        # BUILT THROUGH FLAT ARRAYS, NOT A DICT OF LISTS. The retained index is
        # 39 MB either way, but a dict keyed by 1.58 million digests with a list
        # per key peaks at 454 MB while it is being filled — and the peak is what
        # a worker actually needs at startup, N of them at once on one machine.
        # Two numpy arrays plus one argsort peak at about a tenth of that.
        self._words: tuple[str, ...] = tuple(words)
        digests = numpy.fromiter(
            (_key_digest(key) for word in self._words for key in deletion_keys(word)),
            dtype=numpy.uint64)
        positions = numpy.fromiter(
            (position for position, word in enumerate(self._words)
             for _ in deletion_keys(word)),
            dtype=numpy.uint32, count=len(digests))
        order = numpy.argsort(digests, kind="stable")
        digests, positions = digests[order], positions[order]
        del order
        # One entry per DISTINCT digest, with the run of postings that share it.
        starts = numpy.flatnonzero(
            numpy.concatenate(([True], digests[1:] != digests[:-1])))
        # `frombytes`, not `tolist()`: the latter materialises a Python int per
        # entry on the way in, which is most of what the peak was.
        self._keys = _typed("Q", numpy.ascontiguousarray(digests[starts]))
        self._offsets = _typed("Q", numpy.append(starts, len(digests)).astype(numpy.uint64))
        self._postings = _typed("I", positions)

    def candidates(self, key: str):
        """Vocabulary entries filed under this exact key."""
        digest = _key_digest(key)
        at = bisect_left(self._keys, digest)
        if at == len(self._keys) or self._keys[at] != digest:
            return ()
        return tuple(self._words[i]
                     for i in self._postings[self._offsets[at]:self._offsets[at + 1]])


def build_index(words) -> DeletionIndex:
    """Index a vocabulary by its deletion neighbourhood for one-edit lookup."""
    return DeletionIndex(words)


def lookup(word: str, index: DeletionIndex) -> bool:
    """Whether one Damerau edit reaches something in the index."""
    for key in deletion_keys(word):
        for candidate in index.candidates(key):
            if candidate != word and within_one_typo(word, candidate):
                return True
    return False
