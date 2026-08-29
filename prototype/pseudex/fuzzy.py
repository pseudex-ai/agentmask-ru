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

import itertools


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


def bucket_keys(word: str) -> tuple[str, str]:
    """The two keys a word is indexed under, and looked up by.

    An edit at position p is caught by the FIRST-three key when p ≥ 3 and by the
    LAST-three key when p < len − 3, so any single edit in a word of six letters
    or more lands in at least one of them. The last-three key is prefixed with a
    NUL so the two key spaces cannot collide — «ова» as a beginning and «ова» as
    an ending are different questions.

    The caller pairs these with a LENGTH, and that part is not optional: a
    single edit moves a length by at most one, so a bucket holding every «…ова»
    in a dictionary spends almost all of its work on candidates the length alone
    ruled out. Measured on the name layer, that was 13.65 ms for one word.
    """
    return word[:3], "\0" + word[-3:]


def candidate_lengths(word: str) -> tuple[int, int, int]:
    """The three bucket lengths a one-edit neighbour of `word` can have."""
    return len(word) - 1, len(word), len(word) + 1


def build_index(words) -> dict[tuple[str, int], tuple[str, ...]]:
    """Bucket a vocabulary by (key, length) for one-edit lookup.

    Returns tuples rather than lists so the index is read-only once built: it is
    cached across requests and shared between threads, and a caller that
    appended to a bucket would corrupt every later lookup."""
    index: dict[tuple[str, int], list[str]] = {}
    for word in words:
        for key in bucket_keys(word):
            index.setdefault((key, len(word)), []).append(word)
    return {key: tuple(value) for key, value in index.items()}


def lookup(word: str, index: dict[tuple[str, int], tuple[str, ...]]) -> bool:
    """Whether one Damerau edit reaches something in the index."""
    for key, length in itertools.product(bucket_keys(word), candidate_lengths(word)):
        for candidate in index.get((key, length), ()):
            if candidate != word and within_one_typo(word, candidate):
                return True
    return False
