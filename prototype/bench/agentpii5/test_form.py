"""The form comparator's own test — and it is built to be able to fail.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_form

Every fixture below states the EXACT set of features the two strings must
disagree on, not «they differ». That is deliberate and it is what makes the
table a negative fixture for every feature it leaves out: a `case_class` that
quietly fired on a hyphenated surname, a `gram_case` that read a Latin
rendering as nominative, a `city_present` that grew a city out of a field
separator — each one is a set that no longer matches, in the pair built for a
different feature entirely. A table of «these differ somehow» would have
passed all three bugs, and all three were real while this file was written.

Three further claims the table alone cannot make:

  * COVERAGE — for every feature of every type there is a pair whose `differs`
    is exactly that feature (`_ISOLATING`), so no feature can be registered,
    never fire, and still be reported as measured. `city_present` is the one
    exemption and it is named with its reason: dropping the city moves
    `city_position` too, so the smallest achievable set is the pair.
  * CLOSURE — every label an extractor produces is a label `FEATURE_LABELS`
    declares. Two people writing two components cannot then disagree about
    what «title case» is, and the adversarial fixtures of `form_hIN`/`form_hOUT`
    can name the label they expect.
  * INDEPENDENCE — importing the comparator loads no `pseudex` module, and its
    source contains no such import. An instrument that asks the engine whether
    the engine is right cannot fail the engine (C-026).
"""
import sys
import traceback
from pathlib import Path
from types import ModuleType

from bench.agentpii5 import contracts
from bench.agentpii5.contracts import FIELD_SEP as SEP

Pair = tuple[str, str, str, frozenset[str]]


def _pairs() -> tuple[Pair, ...]:
    """(type, produced, reference, the EXACT set of differing features).

    The NAME/PHONE/LOC/DOB/EMAIL/CARD/SNILS/INN/PASSPORT/PLATE rows the brief
    names are here verbatim; the rest exist to isolate a feature the brief's
    minimum leaves bundled with another."""
    date_rows: tuple[tuple[str, str, frozenset[str]], ...] = (
        ("14.03.1987", "14.03.1987", frozenset()),
        ("14.03.1987", "14/03/87", frozenset({"notation", "separator", "year_len"})),
        ("14 марта 1987", "14.03.1987", frozenset({"notation", "separator", "month_form"})),
        ("4.3.1987", "04.03.1987", frozenset({"padding"})),
        ("1987-03-14", "14.03.1987", frozenset({"notation", "separator"})),
        # ISO against a dotless, hyphenated d-m-y: same separator, same
        # padding, same year, same numeric month — `notation` alone.
        ("1987-03-14", "14-03-1987", frozenset({"notation"})),
        ("14 03 1987", "14-03-1987", frozenset({"separator"})),
        ("14.03.87", "14.03.1987", frozenset({"year_len"})),
        ("14 марта 1987", "14 март 1987", frozenset({"month_form"})),
    )
    rows: list[Pair] = [
        # --- NAME
        ("NAME", "Иванов Пётр", "Иванов Пётр", frozenset()),
        ("NAME", "иванов пётр", "Иванов Пётр", frozenset({"case_class"})),
        ("NAME", "ИВАНОВ ПЁТР", "Иванов Пётр", frozenset({"case_class"})),
        ("NAME", "Иванову Петру", "Иванов Пётр", frozenset({"gram_case"})),
        ("NAME", "Пётр Иванов", "Иванов Пётр", frozenset({"order"})),
        ("NAME", "Иванов Пётр Сергеевич", "Иванов Пётр", frozenset({"parts"})),
        ("NAME", "Иванов П.", "Иванов Пётр", frozenset({"initials"})),
        ("NAME", "Иванов П.С.", "Иванов Пётр", frozenset({"initials"})),
        ("NAME", "Ivanov Petr", "Иванов Пётр", frozenset({"script"})),
        ("NAME", "Petrov Iurii", "Petrov Yuriy", frozenset({"script"})),
        ("NAME", "Иванов-Петров Пётр", "Иванов Пётр", frozenset({"hyphen_particle"})),
        # A particle is written lower case in Russian, so it moves
        # `case_class` too — the expectation says so rather than being
        # loosened to «differs somehow».
        ("NAME", "фон Иванов Пётр", "Иванов Пётр Сергеевич",
         frozenset({"hyphen_particle", "order", "case_class"})),
        # --- PHONE
        ("PHONE", "+7 916 123-45-67", "+7 916 123-45-67", frozenset()),
        ("PHONE", "+7 916 123-45-67", "8 916 123-45-67", frozenset({"prefix"})),
        ("PHONE", "+79161234567", "+7 916 123 45 67", frozenset({"grouping", "separators"})),
        ("PHONE", "+7 (916) 123-45-67", "+7 916 123-45-67", frozenset({"parens"})),
        ("PHONE", "+7 916 123 4567", "+7 916 123 45 67", frozenset({"grouping"})),
        ("PHONE", "+7 916 123 45 67", "+7-916-123-45-67", frozenset({"separators"})),
        ("PHONE", "79161234567", "9161234567", frozenset({"prefix"})),
        # --- LOC
        ("LOC", "ул. Ленина, д. 14, кв. 3", "ул. Ленина, д. 14, кв. 3", frozenset()),
        ("LOC", "ул. Ленина, д. 14, кв. 3", "улица Ленина, дом 14, квартира 3",
         frozenset({"generic", "house_marker", "flat_marker"})),
        ("LOC", "Ленина 14", "ул. Ленина 14", frozenset({"generic"})),
        ("LOC", "Самара, Ленина 14", "Ленина 14, Самара", frozenset({"city_position"})),
        ("LOC", "Ленина 14", "Самара, Ленина 14",
         frozenset({"city_present", "city_position", "commas"})),
        ("LOC", "Ленина" + SEP + "14", "Ленина 14", frozenset({"by_fields"})),
        ("LOC", "Ленина 14 корп. 2", "Ленина 14", frozenset({"building_entrance_markers"})),
        ("LOC", "ленина 14", "Ленина 14", frozenset({"case_class"})),
        ("LOC", "Ленина улица 14", "улица Ленина 14", frozenset({"generic_position"})),
        ("LOC", "Ленина д. 14", "Ленина д.14", frozenset({"house_marker"})),
        ("LOC", "Ленина 14, кв. 3", "Ленина 14, кв.3", frozenset({"flat_marker"})),
        ("LOC", "Ленина 14, кв. 3", "Ленина 14 кв. 3", frozenset({"commas"})),
        # A settlement marker with no comma: the smallest pair that can move
        # `city_present` — see `_ISOLATING`.
        ("LOC", "г. Самара Ленина 14", "Ленина 14",
         frozenset({"city_present", "city_position"})),
        ("LOC", "Ленина 14 стр. 2 эт. 3", "Ленина 14 корп. 2",
         frozenset({"building_entrance_markers"})),
        # --- EMAIL
        ("EMAIL", "ivan@mail.ru", "ivan@mail.ru", frozenset()),
        ("EMAIL", "Ivan@Mail.ru", "ivan@mail.ru", frozenset({"case_class"})),
        ("EMAIL", "IVAN@MAIL.RU", "ivan@mail.ru", frozenset({"case_class"})),
        # --- CARD
        ("CARD", "2200 1234 5678 9010", "2200 1234 5678 9010", frozenset()),
        ("CARD", "2200 1234 5678 9010", "2200123456789010", frozenset({"grouping", "separator"})),
        ("CARD", "2200 1234 5678 9010", "22 00 12 34 56 78 90 10", frozenset({"grouping"})),
        ("CARD", "2200 1234 5678 9010", "2200-1234-5678-9010", frozenset({"separator"})),
        # --- SNILS
        ("SNILS", "112-233-445 95", "112-233-445 95", frozenset()),
        ("SNILS", "112-233-445 95", "11223344595", frozenset({"separators"})),
        ("SNILS", "112 233 445 95", "11223344595", frozenset({"separators"})),
        # --- INN
        ("INN", "7707083893", "7707083893", frozenset()),
        ("INN", "7707083893", "770708389312", frozenset({"length"})),
        ("INN", "7707 083893", "7707083893", frozenset({"separators"})),
        # --- PASSPORT
        ("PASSPORT", "45 09 123456", "45 09 123456", frozenset()),
        ("PASSPORT", "45 09 123456", "4509 123456", frozenset({"series_number_split"})),
        ("PASSPORT", "4509123456", "4509 123456", frozenset({"series_number_split"})),
        # --- PLATE
        ("PLATE", "А123ВС 77", "А123ВС 77", frozenset()),
        ("PLATE", "а123вс 77", "А123ВС 77", frozenset({"case_class"})),
        ("PLATE", "А123ВС77", "А123ВС 77", frozenset({"spaces", "region_sep"})),
        ("PLATE", "А123 ВС-77", "А123 ВС 77", frozenset({"region_sep"})),
        ("PLATE", "А 123ВС77", "А123ВС777", frozenset({"spaces"})),
    ]
    for kind in ("DOB", "DATE"):
        rows.extend((kind, produced, reference, differs)
                    for produced, reference, differs in date_rows)
    return tuple(rows)


PAIRS: tuple[Pair, ...] = _pairs()

# Strings that appear in no pair but must still label inside the closed set:
# the `other` corners of the marker features, which real traffic produces and
# no fixture pair isolates.
EXTRA_STRINGS: tuple[tuple[str, str], ...] = (
    ("LOC", "Ленина влд. 14"),
    ("LOC", "Ленина 14, оф. 3"),
    ("LOC", "Ленина 14 лит. А"),
    ("LOC", "Самара" + SEP + "Ленина" + SEP + "14"),
    ("LOC", "Ленина, г. Самара, 14"),
    ("LOC", "14"),
    ("NAME", "Пётр"),
    ("NAME", "И.О. Иванов"),
    ("NAME", "IVANOV"),
    ("NAME", "Щукин Юрий Оглы Иванов"),
    ("PHONE", "123"),
    ("DOB", "14032003"),
    ("DOB", "в марте 1987"),
    ("DOB", "не дата"),
    ("PLATE", "а123вс-77"),
    ("CARD", "2200 1234 567 89010"),
    ("CARD", "2200.1234.5678.9010"),
    ("SNILS", "112/233/445 95"),
    ("INN", "7707-083893"),
    ("PASSPORT", "45 09 12 34 56"),
    # Letterless strings: `case_class` and `script` must label them `none`
    # (R-05), which `test_labels_closed` pins inside the closed set and
    # `test_letterless_abstains` pins as an abstention rather than agreement.
    ("NAME", "7"),
    ("EMAIL", "@.,"),
    ("PLATE", "123 77"),
)

# (type, feature, string, label) — corners no PAIR isolates and no other check
# names. Every row is a NEGATIVE fixture for the branch that used to swallow
# it: `other` for PHONE.prefix and CARD.separator (R-07) and `none` for the
# letterless case/script (R-05) each replaced a fall-through that made two
# unlike strings agree.
CORNERS: tuple[tuple[str, str, str, str], ...] = (
    ("PHONE", "prefix", "123", "other"),
    ("PHONE", "prefix", "+44 20 7123 4567", "other"),
    ("PHONE", "prefix", "9161234567", "bare"),
    ("PHONE", "prefix", "89161234567", "eight"),
    ("CARD", "separator", "2200.1234.5678.9010", "other"),
    ("CARD", "separator", "2200/1234/5678/9010", "other"),
    ("CARD", "separator", "2200 1234 5678 9010", "space"),
    ("CARD", "separator", "2200-1234-5678-9010", "hyphen"),
    ("CARD", "separator", "2200123456789010", "none"),
    ("NAME", "case_class", "7", "none"),
    ("NAME", "script", "7", "none"),
    ("LOC", "case_class", "14", "none"),
    ("EMAIL", "case_class", "@.,", "none"),
    ("PLATE", "case_class", "123 77", "none"),
)

# The smallest `differs` set that isolates a feature. A singleton everywhere
# but one place: `city_present` cannot move alone — an address either has a
# city segment or has none, and «none» is also a `city_position`. The spec
# names «city_present/city_position» as ONE pair describing the city–street
# order, so the pair is the honest minimum; writing a singleton here would be
# a promise the fixture table could not keep.
_ISOLATING: dict[tuple[str, str], frozenset[str]] = {
    ("LOC", "city_present"): frozenset({"city_present", "city_position"}),
}


def _isolating(kind: str, feature: str) -> frozenset[str]:
    return _ISOLATING.get((kind, feature), frozenset({feature}))


def test_no_pseudex(form: ModuleType) -> list[str]:
    failures: list[str] = []
    loaded = sorted(name for name in sys.modules if name.split(".")[0] == "pseudex")
    if loaded:
        failures.append(f"importing the comparator loaded {loaded}")
    for module in (form, sys.modules["bench.agentpii5.form_tables"]):
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        for number, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("from pseudex", "import pseudex")):
                failures.append(f"{module.__name__}:{number} imports the engine: {stripped}")
    return failures


def test_extractor_keys_equal_contract(form: ModuleType) -> list[str]:
    declared = set(contracts.feature_pairs())
    built = set(form.FEATURE_EXTRACTORS)
    if built == declared:
        return []
    return [f"extractor keys differ from the contract: "
            f"missing {sorted(declared - built)}, extra {sorted(built - declared)}"]


def _all_strings() -> tuple[tuple[str, str], ...]:
    seen: list[tuple[str, str]] = []
    for kind, produced, reference, _ in PAIRS:
        seen.extend(((kind, produced), (kind, reference)))
    seen.extend(EXTRA_STRINGS)
    return tuple(dict.fromkeys(seen))


def test_labels_closed(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind, text in _all_strings():
        for feature, label in form.features_of(kind, text).items():
            allowed = contracts.FEATURE_LABELS[(kind, feature)]
            families = tuple(one[:-1] for one in allowed if one.endswith("*"))
            if label in allowed or any(label.startswith(family) for family in families):
                continue
            failures.append(f"{kind}.{feature}({text!r}) = {label!r} is outside {allowed}")
    return failures


def test_verdict_consistency(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind, produced, reference, _ in PAIRS:
        verdict = form.form_match(kind, produced, reference)
        if verdict.same != (not verdict.differs):
            failures.append(f"{kind} {produced!r}/{reference!r}: same={verdict.same} "
                            f"with differs={sorted(verdict.differs)}")
        outside = verdict.differs - set(contracts.FORM_FEATURES[kind])
        if outside:
            failures.append(f"{kind} {produced!r}/{reference!r}: differs names {sorted(outside)}")
    return failures


def test_expected_pairs(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind, produced, reference, expected in PAIRS:
        actual = form.form_match(kind, produced, reference).differs
        if actual != expected:
            failures.append(f"{kind} {produced!r} vs {reference!r}: "
                            f"expected {sorted(expected)}, got {sorted(actual)}")
    return failures


def test_deterministic(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind, produced, reference, _ in PAIRS:
        first = form.form_match(kind, produced, reference)
        second = form.form_match(kind, produced, reference)
        if first != second:
            failures.append(f"{kind} {produced!r}/{reference!r}: {first} then {second}")
    return failures


def test_symmetry_of_features(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind, produced, reference, _ in PAIRS:
        forward = form.form_match(kind, produced, reference).differs
        backward = form.form_match(kind, reference, produced).differs
        if forward != backward:
            failures.append(f"{kind} {produced!r}/{reference!r}: {sorted(forward)} one way, "
                            f"{sorted(backward)} the other")
    return failures


def _type_features(form: ModuleType, kind: str) -> list[str]:
    """For every feature of `kind`: a pair that isolates it, and a pair that
    does NOT name it. Without the second half a comparator that returned every
    feature on every pair would pass the first."""
    failures: list[str] = []
    rows = [row for row in PAIRS if row[0] == kind]
    if not any(not row[3] for row in rows):
        failures.append(f"{kind}: no pair the comparator calls the SAME")
    for feature in contracts.FORM_FEATURES[kind]:
        wanted = _isolating(kind, feature)
        if not any(form.form_match(kind, produced, reference).differs == wanted
                   for _, produced, reference, _ in rows):
            failures.append(f"{kind}.{feature}: no pair whose differs is exactly {sorted(wanted)}")
        if not any(feature not in form.form_match(kind, produced, reference).differs
                   for _, produced, reference, _ in rows):
            failures.append(f"{kind}.{feature}: no pair on which it agrees")
    return failures


def test_name_features(form: ModuleType) -> list[str]:
    return _type_features(form, "NAME")


def test_phone_features(form: ModuleType) -> list[str]:
    return _type_features(form, "PHONE")


def test_loc_features(form: ModuleType) -> list[str]:
    return _type_features(form, "LOC")


def test_date_features(form: ModuleType) -> list[str]:
    return _type_features(form, "DOB") + _type_features(form, "DATE")


def test_email_features(form: ModuleType) -> list[str]:
    return _type_features(form, "EMAIL")


def test_card_features(form: ModuleType) -> list[str]:
    return _type_features(form, "CARD")


def test_snils_features(form: ModuleType) -> list[str]:
    return _type_features(form, "SNILS")


def test_inn_features(form: ModuleType) -> list[str]:
    return _type_features(form, "INN")


def test_passport_features(form: ModuleType) -> list[str]:
    return _type_features(form, "PASSPORT")


def test_plate_features(form: ModuleType) -> list[str]:
    return _type_features(form, "PLATE")


def test_by_fields_sentinel(form: ModuleType) -> list[str]:
    """FIELD_SEP decides `by_fields`, and it is not a comma: a multi-field
    value was never one string, and reading its sentinel as punctuation would
    make `commas` and `city_present` answer for a character the customer never
    typed."""
    failures: list[str] = []
    fielded = form.features_of("LOC", "Самара" + SEP + "Ленина" + SEP + "14")
    written = form.features_of("LOC", "Самара, Ленина, 14")
    if fielded["by_fields"] != "fields":
        failures.append(f"FIELD_SEP did not make by_fields `fields`: {fielded['by_fields']}")
    if written["by_fields"] != "string":
        failures.append(f"a comma made by_fields {written['by_fields']!r}")
    if fielded["commas"] != "no":
        failures.append("FIELD_SEP was counted as a comma")
    if form.features_of("LOC", "Ленина 14")["by_fields"] != "string":
        failures.append("a plain string is not `string`")
    # The sentinel still segments: the city is found across fields exactly as
    # it is across commas.
    if fielded["city_present"] != written["city_present"] or \
            fielded["city_position"] != written["city_position"]:
        failures.append(f"fields and commas disagree about the city: "
                        f"{fielded['city_present']}/{fielded['city_position']} vs "
                        f"{written['city_present']}/{written['city_position']}")
    return failures


def test_unknown_type_raises(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind in ("ORG", "", "name", "DOB "):
        for call, label in ((lambda: form.form_match(kind, "a", "b"), "form_match"),
                            (lambda: form.features_of(kind, "a"), "features_of")):
            try:
                call()
            except ValueError as error:
                if kind not in str(error):
                    failures.append(f"{label}({kind!r}) raised without naming the type: {error}")
            else:
                failures.append(f"{label}({kind!r}) returned instead of raising")
    try:
        form._signature_holds("nonsense", "yu", "yuriy", ["yuriy"])
    except ValueError:
        pass
    else:
        failures.append("_signature_holds accepted an unknown condition kind")
    return failures


def test_abstain_is_closed_and_one_sided(form: ModuleType) -> list[str]:
    """The features that abstain, and the proof that abstaining does not hide
    a difference the same feature CAN see. A wildcard nobody bounded is how a
    comparator stops being able to fail.

    THE REGISTRY IS `contracts.FORM_ABSTAIN` AND THE COMPARATOR HAS NO COPY
    (ruling R-05): a local `ABSTAIN_LABELS` would be a second list that has to
    stay equal to the first, and the observer slices its lines by the same
    features. Both the module and its source are read: a dict rebuilt under
    another name would pass a `hasattr` check, and an alias bound only at
    import time leaves no assignment in the source."""
    failures: list[str] = []
    source = Path(form.__file__ or "").read_text(encoding="utf-8")
    if hasattr(form, "ABSTAIN_LABELS"):
        failures.append("the comparator still exports its own ABSTAIN_LABELS")
    if any(line.startswith("ABSTAIN_LABELS") for line in source.splitlines()):
        failures.append("the comparator still assigns ABSTAIN_LABELS")
    if "FORM_ABSTAIN.get(" not in source:
        failures.append("the comparator does not read contracts.FORM_ABSTAIN")
    for (kind, feature), label in contracts.FORM_ABSTAIN.items():
        if label not in contracts.FEATURE_LABELS[(kind, feature)]:
            failures.append(f"{kind}.{feature} abstains on {label!r}, which is not a label")
        if (kind, feature) not in form.FEATURE_EXTRACTORS:
            failures.append(f"{kind}.{feature} abstains but has no extractor")
    # Abstaining side: no verdict. Both sides present: the verdict is made.
    if "gram_case" in form.form_match("NAME", "Ivanov Petr", "Иванову Петру").differs:
        failures.append("gram_case judged a Latin rendering against a Russian case")
    if "gram_case" not in form.form_match("NAME", "Иванову Петру", "Иванов Пётр").differs:
        failures.append("gram_case stopped seeing a real case difference")
    if "generic_position" in form.form_match("LOC", "Ленина 14", "ул. Ленина 14").differs:
        failures.append("generic_position judged an address with no generic word")
    if "generic_position" not in form.form_match("LOC", "Ленина улица 14", "улица Ленина 14").differs:
        failures.append("generic_position stopped seeing a real position difference")
    return failures


def test_corner_labels(form: ModuleType) -> list[str]:
    """Every row of `CORNERS`: the exact label, named. `test_labels_closed`
    only asks whether a label is inside the set, so a `prefix` that answered
    `bare` for «123» would pass it — this is the check that fails."""
    failures: list[str] = []
    for kind, feature, text, expected in CORNERS:
        actual = form.FEATURE_EXTRACTORS[(kind, feature)](text)
        if actual != expected:
            failures.append(f"{kind}.{feature}({text!r}) = {actual!r}, expected {expected!r}")
    return failures


def test_letterless_abstains(form: ModuleType) -> list[str]:
    """A string with no letters agrees with NOTHING about case or script.

    The pairs below are the ones the old vacuous labels made same: «14»
    answered `lower` like «ленина», «7» answered `cyrillic` like «Пётр». Both
    halves are checked — the feature abstains where one side is letterless,
    and still fires where both sides carry letters."""
    failures: list[str] = []
    silent: tuple[tuple[str, str, str, str], ...] = (
        ("LOC", "case_class", "14", "ленина 14"),
        ("LOC", "case_class", "14", "Ленина 14"),
        ("NAME", "case_class", "7", "Иванов"),
        ("NAME", "script", "7", "Ivanov"),
        ("EMAIL", "case_class", "@.,", "ivan@mail.ru"),
        ("PLATE", "case_class", "123 77", "А123ВС 77"),
    )
    for kind, feature, letterless, lettered in silent:
        differs = form.form_match(kind, letterless, lettered).differs
        if feature in differs:
            failures.append(f"{kind}.{feature} judged the letterless {letterless!r} "
                            f"against {lettered!r}")
    loud: tuple[tuple[str, str, str, str], ...] = (
        ("LOC", "case_class", "ленина 14", "Ленина 14"),
        ("NAME", "case_class", "иванов", "Иванов"),
        ("NAME", "script", "Ivanov", "Иванов"),
        ("EMAIL", "case_class", "IVAN@MAIL.RU", "ivan@mail.ru"),
        ("PLATE", "case_class", "а123вс 77", "А123ВС 77"),
    )
    for kind, feature, produced, reference in loud:
        differs = form.form_match(kind, produced, reference).differs
        if feature not in differs:
            failures.append(f"{kind}.{feature} stopped seeing a real difference between "
                            f"{produced!r} and {reference!r}")
    return failures


def test_features_of_covers_the_type(form: ModuleType) -> list[str]:
    failures: list[str] = []
    for kind, features in contracts.FORM_FEATURES.items():
        labelled = form.features_of(kind, "Иванов Пётр")
        if tuple(labelled) != features:
            failures.append(f"features_of({kind}) returned {tuple(labelled)}, expected {features}")
    return failures


_TESTS = (
    test_no_pseudex,
    test_extractor_keys_equal_contract,
    test_labels_closed,
    test_verdict_consistency,
    test_expected_pairs,
    test_deterministic,
    test_symmetry_of_features,
    test_name_features,
    test_phone_features,
    test_loc_features,
    test_date_features,
    test_email_features,
    test_card_features,
    test_snils_features,
    test_inn_features,
    test_passport_features,
    test_plate_features,
    test_by_fields_sentinel,
    test_unknown_type_raises,
    test_abstain_is_closed_and_one_sided,
    test_corner_labels,
    test_letterless_abstains,
    test_features_of_covers_the_type,
)


def main() -> int:
    from bench.agentpii5 import form

    failures: list[str] = []
    for test in _TESTS:
        # A check that CRASHES is a red check, not the end of the run: a
        # missing extractor raises a KeyError three checks after the one
        # written to name it, and aborting there would hide every check
        # behind it. The cause is printed with its frame, never swallowed.
        #
        # THE FAILURE IS APPENDED, NOT ASSIGNED, and that is not style:
        # `e2e/lint_tests.py` decides whether a broad `except` records or
        # swallows by looking for a `check`/`append`/`fail` call or a `raise`
        # INSIDE the handler, and a rule that read the comment instead would
        # be no rule at all — the handler that cost us a paying customer's 403
        # also had a comment naming the real reason.
        found: list[str] = []
        try:
            found = test(form)
        except Exception as error:                      # noqa: BLE001 - appended below, never hidden
            frame = traceback.extract_tb(error.__traceback__)[-1]
            found.append(f"raised {type(error).__name__}: {error} "
                         f"at {Path(frame.filename).name}:{frame.lineno}")
        print(f"  {test.__name__:42} {'ok' if not found else 'FAIL'}")
        failures.extend(f"{test.__name__}: {one}" for one in found)
    print(f"form: {len(PAIRS)} pairs, {len(form.FEATURE_EXTRACTORS)} extractors")
    print("form: PASS" if not failures else "form: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
