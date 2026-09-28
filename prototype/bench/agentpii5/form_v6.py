"""The v6 form extractors, one per (v6 type, feature) pair.

`form.py` owns the comparator and the v5 extractors; this file owns every
extractor a v6 record of `pii_types.TYPE_REGISTRY` names in `form_features`,
registered in a dict of exactly the same shape as `form.FEATURE_EXTRACTORS`
(`(type, feature) -> str`). `form.py` merges the two in ONE line (§5.1: the
v5 extractors stay the same objects; the new ones live here).

WHY A SEPARATE FILE AND NOT A REWRITE OF `form.py`. The v5 extractors are
pinned by `test_form.py` and by the v5 regression («производные = литералы»):
merging the v6 pairs into the same dict must not move a single v5 object, and a
separate module makes that the visible fact — `form.py` only gains one merge
line, never a re-ordering of its own table.

THE FEATURES ARE THE CLOSED §5.2 SET, AND MOST ARE SHARED. Eight feature names
exist across the 55 v6 records; seven of them have one semantics for every type
that carries them (`separators`, `case_class`, `script`, `by_fields`,
`padding`, `digit_count`, `notation`), so they are one pure function each,
registered under every (type, feature) key that declares them. `grouping` is
the per-type one: its labels are a closed list per type (the registry's
`feature_labels`), and the reading of «what the value is split into» has two
shapes — separator-delimited chunks (most types) and digit/letter runs (the one
type whose grammar mixes the two with no separator, GIS_ZHKH_ELS) plus a
trailing-check-char special case for LOAN_UID.

PURE AND ENGINE-FREE. No `pseudex`, no I/O, no `pymorphy3` (nothing here reads
Russian morphology), deterministic. A letterless string answers `none` for
`case_class` and `script` — the label `contracts.FORM_ABSTAIN` names as the
abstain, so `form_match` lets a letterless side say nothing rather than agree
with every lettered one (the same R-05 rule the v5 extractors follow).

Run the tests: cd prototype && source .venv/bin/activate
                && python3 -m bench.agentpii5.test_form_v6
"""
import re
from collections.abc import Callable
from functools import partial
from ipaddress import IPv6Address

from bench.agentpii5 import contracts
from bench.agentpii5.pii_types import ORIGIN_V6, TYPE_REGISTRY, TypeSpec

# --- shared readers --------------------------------------------------------------------

# A digit run: the pieces `padding` and `digit_count` measure.
_DIGIT_RUN = re.compile(r"\d+")

# A letter run, any script. `[^\W\d_]` is «word character, not a digit, not the
# underscore» — the underscore is a field/handle character, not a letter, and
# counting it would make `case_class` read `mixed` on a login handle.
_LETTER_RUN = re.compile(r"[^\W\d_]")


def _letters(text: str) -> list[str]:
    return [char for char in text if char.isalpha()]


def _digits(text: str) -> str:
    return "".join(char for char in text if char.isdigit())


def _is_cyrillic(char: str) -> bool:
    # U+0400…U+04FF: the Cyrillic block, the Ukrainian І (U+0406) included —
    # «І» is the one look-alike the registry cards name explicitly.
    return "Ѐ" <= char <= "ӿ"


def _is_latin(char: str) -> bool:
    return "a" <= char.lower() <= "z"


# --- the shared extractors -------------------------------------------------------------

# The characters that separate a value's groups, mapped to the closed §5.2
# label. Anything else — an underscore, a hash — is not a group separator and is
# simply ignored: the list is CLOSED, and an out-of-list character must not
# smuggle in a second spelling of «separated».
_SEPARATOR_LABELS: dict[str, str] = {
    " ": "space", "-": "hyphen", ".": "dot", "/": "slash", ":": "colon", "№": "numsign",
}


def separators(text: str) -> str:
    """none / space / hyphen / dot / slash / colon / numsign / mixed — the set
    of separator characters between the value's groups."""
    found = {_SEPARATOR_LABELS[char] for char in text if char in _SEPARATOR_LABELS}
    if not found:
        return "none"
    return found.pop() if len(found) == 1 else "mixed"


def case_class(text: str) -> str:
    """lower / upper / mixed / none. `none` on a letterless string is the
    abstain (§5.2): no letters, no case to read, and no agreement either."""
    letters = _letters(text)
    if not letters:
        return "none"
    if all(char.islower() for char in letters):
        return "lower"
    if all(char.isupper() for char in letters):
        return "upper"
    return "mixed"


def script(text: str) -> str:
    """cyrillic / latin / mixed / none. `none` on a letterless string, for the
    same reason as `case_class`: «ХТА…» against «XTA…» is a real difference,
    «14» against «XTAGFK…» is a side with nothing to say."""
    letters = _letters(text)
    if not letters:
        return "none"
    cyrillic = any(_is_cyrillic(char) for char in letters)
    latin = any(_is_latin(char) for char in letters)
    if cyrillic and latin:
        return "mixed"
    return "cyrillic" if cyrillic else "latin"


def by_fields(text: str) -> str:
    """fields / string. `contracts.FIELD_SEP` is the sentinel that joins the
    leaves of a value the tool schema DECOMPOSED (series and number in separate
    fields); it is not a character the customer typed, so nothing else reads it
    as one."""
    return "fields" if contracts.FIELD_SEP in text else "string"


def padding(text: str) -> str:
    """padded / unpadded / none. A digit run longer than one that starts with
    «0» is a leading zero («004512» vs «4512»); a single «0» is the value zero,
    not padding, so «192.168.0.1» stays unpadded. `none` when there is no digit
    to pad at all."""
    runs = _DIGIT_RUN.findall(text)
    if not runs:
        return "none"
    return "padded" if any(len(run) > 1 and run.startswith("0") for run in runs) else "unpadded"


# IPv4 written as four octets, leading zeros allowed. `ipaddress.IPv4Address`
# REJECTS leading zeros (Python 3.9.5+), so the notation reading cannot use it
# for the `v4_padded` case and owns its regex instead.
_IPV4 = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def notation(text: str) -> str:
    """v4_dotted / v4_padded / v6_full / v6_compressed / other — the writing of
    an IP_ADDRESS. IPv4 is decided by the octets' own spelling (a leading zero
    in any octet is `v4_padded`); IPv6 by whether the address is compressed
    («::») or written with all eight groups. Anything else is `other`."""
    value = text.strip()
    if _IPV4.fullmatch(value):
        octets = value.split(".")
        return ("v4_padded"
                if any(len(octet) > 1 and octet.startswith("0") for octet in octets)
                else "v4_dotted")
    try:
        IPv6Address(value)
    except ValueError:
        return "other"
    return "v6_compressed" if "::" in value else "v6_full"


# --- grouping --------------------------------------------------------------------------

# The characters that split a value into groups for `grouping`. An EXPLICIT
# space, not `\s`: `\s` also matches `contracts.FIELD_SEP` (U+001F), and a
# by-fields value «75<SEP>1234567» must read as ONE solid group — the field
# boundary is what `by_fields` names, not a written separator the customer
# typed. The `№` numsign is a separator AND may carry a trailing space
# («АК № 1234567»), so it is its own member of the class.
_GROUP_SEP = re.compile(r"[ .\-/:№]+")


def _separator_grouping(labels: frozenset[str], text: str) -> str:
    """The lengths of the separator-delimited chunks, joined by «-».

    `solid` is one chunk with no separator at all; a joined label that is not a
    declared grouping of this type is `other` — the honest answer for a split
    this grammar does not name, never a silent fall-through to the last one.
    """
    chunks = [chunk for chunk in _GROUP_SEP.split(text.strip()) if chunk]
    if len(chunks) == 1:
        return "solid"
    joined = "-".join(str(len(chunk)) for chunk in chunks)
    return joined if joined in labels else "other"


_CLASS_RUN = re.compile(r"\d+|[^\W\d_]+")


def _class_grouping(labels: frozenset[str], text: str) -> str:
    """The lengths of the digit/letter runs, joined by «-».

    For the ONE type whose grammar is an inherent letter/digit structure with no
    separator between them (GIS_ZHKH_ELS: «60АА000593-01» = 2 digits, 2 letters,
    6 digits, 2 digits), a separator split would read the whole «60АА000593»
    as one chunk and lose the structure the grouping feature exists to name.
    """
    runs = _CLASS_RUN.findall(text)
    if len(runs) == 1:
        return "solid"
    joined = "-".join(str(len(run)) for run in runs)
    return joined if joined in labels else "other"


def _loan_uid_grouping(labels: frozenset[str], text: str) -> str:
    """LOAN_UID is a UUID body (8-4-4-4-12) plus a trailing «-» + check hex. The
    check character is NOT a group — the registry's grouping is the UUID's own —
    so a six-chunk split whose last chunk is one character drops it before naming
    the grouping. A dashless 33-hex value is `solid`."""
    chunks = [chunk for chunk in _GROUP_SEP.split(text.strip()) if chunk]
    if len(chunks) == 1:
        return "solid"
    if len(chunks) == 6 and len(chunks[-1]) == 1:
        chunks = chunks[:-1]
    joined = "-".join(str(len(chunk)) for chunk in chunks)
    return joined if joined in labels else "other"


# The types whose grouping reads the digit/letter structure rather than the
# separator chunks. Deliberately one entry: every other letter+digit type (PTS,
# BIRTH_CERT, MILITARY_ID, …) puts a separator between its letter and digit
# groups, so a separator split already names them.
_CLASS_GROUPING_TYPES: frozenset[str] = frozenset({"GIS_ZHKH_ELS"})


def _grouping_labels(record: TypeSpec) -> frozenset[str]:
    """The named groupings of one record — its `grouping` labels minus the
    `solid`/`other` sentinels every list carries. Read from the registry so a
    label can never drift out of sync with `feature_labels`."""
    for feature, labels in record.feature_labels:
        if feature == "grouping":
            return frozenset(label for label in labels if label not in ("solid", "other"))
    return frozenset()


def _grouping_extractor(record: TypeSpec):
    """The per-type `grouping` extractor, closed over the record's labels."""
    labels = _grouping_labels(record)
    if record.id == "LOAN_UID":
        return partial(_loan_uid_grouping, labels)
    if record.id in _CLASS_GROUPING_TYPES:
        return partial(_class_grouping, labels)
    return partial(_separator_grouping, labels)


# --- digit_count -----------------------------------------------------------------------

# «as_grammar» iff the digit count falls in the type's grammar range, from the
# `length` field of each record. Written as one rule per type rather than parsed
# out of the prose `length` string: a range is a semantic fact, and a regex over
# «≤15», «20|25» or «не установлена» would be a second, lossy source of truth.
_DIGIT_COUNT_RULES: dict[str, Callable[[int], bool]] = {
    "IMEI": lambda n: n == 15,
    "ICCID": lambda n: n in (19, 20),
    "IMSI": lambda n: 0 < n <= 15,
    "OMS_ENP": lambda n: n == 16,
    "BANK_ACCOUNT": lambda n: n == 20,
    "OGRNIP": lambda n: n == 15,
    "EPTS_NUMBER": lambda n: n == 15,
    "UIN": lambda n: n in (20, 25),
    "ELN_NUMBER": lambda n: 0 < n <= 12,
    "SCHOOL_CERT_NUMBER": lambda n: n == 14,
    "E_TICKET_NUMBER": lambda n: n == 13,
    "METRICA_CLIENT_ID": lambda n: n == 18,
    "ESIA_OID": lambda n: n > 0,          # grammar is `\d+`: any digits, none is `other`
    "LOYALTY_CARD_NUMBER": lambda n: 13 <= n <= 18,
}


def _digit_count_extractor(rule: Callable[[int], bool]):
    def extractor(text: str) -> str:
        return "as_grammar" if rule(len(_digits(text))) else "other"
    return extractor


# --- the registry ----------------------------------------------------------------------

# One extractor per (v6 type, feature) pair, assembled from the registry so the
# key set is exactly the v6 half of `contracts.feature_pairs()` — the merge in
# `form.py` then makes the union equal, and `test_form.py`'s key check pins it.
FEATURE_EXTRACTORS: dict[tuple[str, str], contracts.FeatureExtractor] = {}

for _record in TYPE_REGISTRY:
    if _record.origin != ORIGIN_V6:
        continue
    for _feature in _record.form_features:
        if _feature == "grouping":
            _extractor = _grouping_extractor(_record)
        elif _feature == "separators":
            _extractor = separators
        elif _feature == "case_class":
            _extractor = case_class
        elif _feature == "script":
            _extractor = script
        elif _feature == "by_fields":
            _extractor = by_fields
        elif _feature == "padding":
            _extractor = padding
        elif _feature == "digit_count":
            _extractor = _digit_count_extractor(_DIGIT_COUNT_RULES[_record.id])
        elif _feature == "notation":
            _extractor = notation
        else:  # pragma: no cover - a closed list; this is the loud failure
            raise ValueError(
                f"form_v6: no extractor for v6 feature {_feature!r} of type "
                f"{_record.id!r}; the closed §5.2 set is grouping/separators/"
                f"case_class/script/by_fields/padding/digit_count/notation")
        FEATURE_EXTRACTORS[(_record.id, _feature)] = _extractor
