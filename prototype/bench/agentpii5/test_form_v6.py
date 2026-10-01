"""The v6 form comparator's own test — one isolating pair per feature, plus the
agreeing pair, the empty side and determinism (R6-13, tz-agentpii6.md §5.6).

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_form_v6

Every v6 record carries `form_features`; this file proves, per (type, feature),
that the extractor can actually fire — a pair whose `differs` is EXACTLY that
feature — and that it is not firing by accident — an agreeing pair, an empty
side and a second call that returns the same verdict. The isolating pair is the
negative fixture for every OTHER feature of the type: a `separators` that also
moved `grouping`, or a `case_class` that fired on a letterless string, would
change the set away from the singleton and this file goes red.

Follows the v5 convention (`main() -> int`, 1 on failure, no pytest).
"""
import re
import traceback
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5 import contracts
from bench.agentpii5 import form
from bench.agentpii5.contracts import FIELD_SEP
from bench.agentpii5.pii_types import ORIGIN_V6, TYPE_REGISTRY, TypeSpec

V6: tuple[TypeSpec, ...] = tuple(record for record in TYPE_REGISTRY if record.origin == ORIGIN_V6)

# A grouping list that is only {solid, other} cannot be isolated from
# `separators`: `solid` means one chunk with no separator, `other` means chunks
# WITH a separator, so the two move together by construction. These pairs are
# reported as a two-feature difference, the same honest minimum the v5 test
# grants LOC.city_present/city_position.
_COUPLED_GROUPING: frozenset[str] = frozenset({
    "ICCID", "IMSI", "EPTS_NUMBER", "UIN", "ELN_NUMBER", "SCHOOL_CERT_NUMBER",
    "E_TICKET_NUMBER", "METRICA_CLIENT_ID", "ESIA_OID", "PNR",
})

# The digit count that is OUT of the grammar's range, one per digit_count type.
# Written as a count (not a rule) because the isolating pair only needs to cross
# the boundary; the extractor's own rule lives in form_v6._DIGIT_COUNT_RULES.
_DIGIT_COUNT_OUT: dict[str, int] = {
    "IMEI": 14, "ICCID": 18, "IMSI": 16, "OMS_ENP": 15, "BANK_ACCOUNT": 19,
    "OGRNIP": 14, "EPTS_NUMBER": 14, "UIN": 19, "ELN_NUMBER": 13,
    "SCHOOL_CERT_NUMBER": 13, "E_TICKET_NUMBER": 12, "METRICA_CLIENT_ID": 17,
    "LOYALTY_CARD_NUMBER": 12,
}

# (type, feature) -> (produced, reference) that differ ONLY in `script`. Hand-
# written because the mutation is «swap a letter to its look-alike in the other
# alphabet, same case», and the letter to swap is each type's own: a «mixed»
# sample (BIRTH_CERT's Roman+Cyrillic series) must move the whole letter part,
# a letterless sample (CADASTRAL) must gain one.
_SCRIPT_PAIRS: dict[str, tuple[str, str]] = {
    "VIN": ("ХТАGFK330LY123456", "XTAGFK330LY123456"),
    "PTS_NUMBER": ("77 UK 123456", "77 УК 123456"),
    "GIS_ZHKH_ELS": ("60AA000593-01", "60АА000593-01"),
    "MILITARY_ID": ("AK № 1234567", "АК № 1234567"),
    "OSAGO_POLICY": ("XXX 0123456789", "ХХХ 0123456789"),
    "BIRTH_CERT": ("IV-MU № 123456", "IV-МЮ № 123456"),
    "CIVIL_ACT_CERT": ("I-AG № 672731", "I-АГ № 672731"),
    "EXEC_DOC_NO": ("FS 012345678", "ФС 012345678"),
    "PNR": ("2ZУVAL", "2ZYVAL"),
    "IBAN": ("РU0304452522540817810538091310419", "RU0304452522540817810538091310419"),
    "COURT_CASE_UID": ("77ОС0000-02-2026-000001-52", "77OS0000-02-2026-000001-52"),
    "ARBITRAZH_CASE_NO": ("A31-2840/2013", "А31-2840/2013"),
    "COURT_CASE_NO_SOU": ("2А-13/2015", "2A-13/2015"),
    "FSSP_IP_NO": ("1234567/25/77001-IP", "1234567/25/77001-ИП"),
    "CADASTRAL_NUMBER": ("А77:01:0001001:1234", "A77:01:0001001:1234"),
}

# The case_class pair for a type whose SAMPLE is letterless would collapse if
# derived from the sample, so the isolating pair is a fixed letter pair in two
# cases — it moves ONLY `case_class` (script stays latin, grouping stays solid,
# padding stays none, digit_count stays other) for every type that carries it.
_CASE_CLASS_PAIR: tuple[str, str] = ("AB", "ab")

_SEPARATOR_RUN = re.compile(r"[\s.\-/:№]+")


def _named_groupings(record: TypeSpec) -> tuple[str, ...]:
    for feature, labels in record.feature_labels:
        if feature == "grouping":
            return tuple(label for label in labels if label not in ("solid", "other"))
    return ()


def _grouping_pair(record: TypeSpec) -> tuple[str, str]:
    """Two strings with the SAME separator (a space) and different group sizes:
    one names the record's first grouping, the other is `other` by construction
    (the last group is one character longer, a length no grammar names)."""
    sizes = [int(part) for part in _named_groupings(record)[0].split("-")]
    reference = " ".join("X" * size for size in sizes)
    shifted = sizes[:-1] + [sizes[-1] + 1]
    produced = " ".join("X" * size for size in shifted)
    return produced, reference


def _padding_pair(record: TypeSpec) -> tuple[str, str]:
    """The §5.2 example pair, «004512» / «4512»: padded vs unpadded. Every
    padding type reads only separators/case_class/padding (IP_ADDRESS reads
    notation too), and both sides are letterless digit strings — `none` case,
    `none` separators, `other` notation — so ONLY `padding` moves."""
    return "004512", "4512"


def _digit_count_pair(record: TypeSpec) -> tuple[str, str]:
    """Two solid digit strings, one in range (the sample) and one out. ESIA_OID's
    grammar is `\\d+`, so its out-of-range form is NO digits — a letter string —
    not a different digit count."""
    if record.id == "ESIA_OID":
        return "abc", record.sample
    return "9" * _DIGIT_COUNT_OUT[record.id], record.sample


def _by_fields_pair(record: TypeSpec) -> tuple[str, str]:
    """The solid form against itself with FIELD_SEP inserted. FIELD_SEP is not a
    separator any other feature reads, so grouping/separators stay `solid`/`none`
    on both sides and only `by_fields` moves."""
    solid = _SEPARATOR_RUN.sub("", record.sample)
    return solid[:1] + FIELD_SEP + solid[1:], solid


def _isolating_pair(record: TypeSpec, feature: str) -> tuple[str, str] | None:
    """(produced, reference) differing in exactly `feature`, or None for the
    coupled grouping (whose pair differs in {grouping, separators})."""
    if feature == "grouping":
        if not _named_groupings(record):
            return None
        return _grouping_pair(record)
    if feature == "separators":
        # One grouped shape in two separator spellings; every type's grouping
        # reads [2,2] as `other` (no grammar names 2-2), so grouping agrees.
        return "A1 B2", "A1-B2"
    if feature == "case_class":
        return _CASE_CLASS_PAIR
    if feature == "script":
        return _SCRIPT_PAIRS[record.id]
    if feature == "by_fields":
        return _by_fields_pair(record)
    if feature == "padding":
        return _padding_pair(record)
    if feature == "digit_count":
        return _digit_count_pair(record)
    if feature == "notation":
        return "192.168.10.24", "2001:db8::1"
    raise ValueError(f"no isolating-pair builder for v6 feature {feature!r}")


def _expected_differs(record: TypeSpec, feature: str) -> frozenset[str]:
    if feature == "grouping" and not _named_groupings(record):
        return frozenset({"grouping", "separators"})
    return frozenset({feature})


def _all_pairs() -> tuple[tuple[str, str, str, str, frozenset[str]], ...]:
    """(type, produced, reference, feature-under-test, the EXACT differs set)."""
    out: list[tuple[str, str, str, str, frozenset[str]]] = []
    for record in V6:
        for feature in record.form_features:
            pair = _isolating_pair(record, feature)
            if pair is None:
                produced, reference = "XXXX", "XX XX"
            else:
                produced, reference = pair
            out.append((record.id, produced, reference, feature,
                        _expected_differs(record, feature)))
    return tuple(out)


def test_isolating_pairs() -> list[str]:
    failures: list[str] = []
    for kind, produced, reference, feature, expected in _all_pairs():
        actual = form.form_match(kind, produced, reference).differs
        if actual != expected:
            failures.append(f"{kind}.{feature}: {produced!r} vs {reference!r} — "
                            f"expected {sorted(expected)}, got {sorted(actual)}")
    return failures


def test_agreeing_pairs() -> list[str]:
    failures: list[str] = []
    for record in V6:
        verdict = form.form_match(record.id, record.sample, record.sample)
        if not verdict.same:
            failures.append(f"{record.id}: its own sample differs from itself: "
                            f"{sorted(verdict.differs)}")
    return failures


def test_empty_side() -> list[str]:
    failures: list[str] = []
    for record in V6:
        features = frozenset(record.form_features)
        for empty in ("", "   "):
            verdict = form.form_match(record.id, empty, record.sample)
            if verdict.same or verdict.differs != features:
                failures.append(f"{record.id}: empty produced differs on "
                                f"{sorted(verdict.differs)}, not every feature")
            mirrored = form.form_match(record.id, record.sample, empty)
            if mirrored.same or mirrored.differs != features:
                failures.append(f"{record.id}: empty REFERENCE did not differ on "
                                f"every feature — the rule is not one-sided")
    return failures


def test_determinism() -> list[str]:
    failures: list[str] = []
    for kind, produced, reference, feature, _expected in _all_pairs():
        first = form.form_match(kind, produced, reference)
        second = form.form_match(kind, produced, reference)
        if first != second:
            failures.append(f"{kind}.{feature}: {first} then {second}")
    return failures


def test_labels_closed() -> list[str]:
    """Every label an extractor produces on the samples and the isolating pairs
    is a label `FEATURE_LABELS` declares — the v6 half of `test_form.py`'s
    closure check, which only ever feeds v5 strings to the extractors."""
    failures: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for record in V6:
        seen.add((record.id, record.sample, "sample"))
        for feature in record.form_features:
            pair = _isolating_pair(record, feature)
            strings = ("XXXX", "XX XX") if pair is None else pair
            seen.add((record.id, strings[0], feature))
            seen.add((record.id, strings[1], feature))
    for kind, text, _origin in seen:
        for feature, label in form.features_of(kind, text).items():
            allowed = contracts.FEATURE_LABELS[(kind, feature)]
            families = tuple(one[:-1] for one in allowed if one.endswith("*"))
            if label in allowed or any(label.startswith(family) for family in families):
                continue
            failures.append(f"{kind}.{feature}({text!r}) = {label!r} outside {allowed}")
    return failures


def test_no_pseudex() -> list[str]:
    failures: list[str] = []
    loaded = sorted(name for name in __import__("sys").modules
                    if name.split(".")[0] == "pseudex")
    if loaded:
        failures.append(f"importing the v6 comparator loaded {loaded}")
    source = Path(__import__("bench.agentpii5.form_v6", fromlist=["x"]).__file__).read_text("utf-8")
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(("from pseudex", "import pseudex")):
            failures.append(f"form_v6.py:{number} imports the engine: {stripped}")
    return failures


_TESTS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("isolating_pairs", test_isolating_pairs),
    ("agreeing_pairs", test_agreeing_pairs),
    ("empty_side", test_empty_side),
    ("determinism", test_determinism),
    ("labels_closed", test_labels_closed),
    ("no_pseudex", test_no_pseudex),
)


def main() -> int:
    failures: list[str] = []
    for name, test in _TESTS:
        found: list[str] = []
        try:
            found = test()
        except Exception as error:               # noqa: BLE001 — appended below, never hidden
            frame = traceback.extract_tb(error.__traceback__)[-1]
            found.append(f"raised {type(error).__name__}: {error} "
                         f"at {Path(frame.filename).name}:{frame.lineno}")
        print(f"  {name:20} {'ok' if not found else 'FAIL'}")
        failures.extend(f"{name}: {one}" for one in found)
    pairs = sum(len(record.form_features) for record in V6)
    print(f"form_v6: {len(V6)} types, {pairs} (type, feature) pairs")
    print("form_v6: PASS" if not failures else "form_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
