"""Класс Ж (прибор) — the RED-then-GREEN test of `SPIKE-Ж.md`, Ж-1…Ж-7.

    cd prototype && source .venv/bin/activate
    && PYTHONDONTWRITEBYTECODE=1 python3 -m bench.agentpii5.test_spike_zh

WHAT THE RED WAS. One question — «получил ли этот лист ТО САМОЕ значение» — was
answered by THREE independent copies inside this package, and WHICH copy a hop got
was decided by whether its `FieldSpec.role` was empty:

  * `metrics.value_matches` — `fold(produced) == fold(target)`, with LOC as the
    only exception (metrics.py:115–127 before this change);
  * `observe.part_matches` — digits / ISO / squeeze / fold (observe.py:576–601);
  * `revise._same_value` — a third fold whose own docstring promised «a hop this
    accepts is a hop that line can hit» and which had ALREADY drifted.

The leaves the class-Ж witnesses land on all declare `role=''` —
`vehicle_check.plate`, `snils_verify.snils`, `calendar_free.person` — so they took
the strict copy, and a notation the tool's own parser had ACCEPTED read as the
GATEWAY's miss. Measured in SPIKE-Ж over five archives: 24 PLATE and 9 NAME hops
of 363 role-less OUT hops, plus the SNILS half, where the corpus PROVOKED the
attempt with a message teaching a notation its own parser refuses.

THE GREEN IS FOUR MASS RULES AND NOT A CASE FIX:

  1. ONE TABLE (`contracts.VALUE_NORMALISERS`), ONE PREDICATE
     (`observe.values_equal`), THREE THIN CALLERS — `metrics.value_matches`,
     `observe.part_matches`, `revise._same_value`. NAME is a multiset of parts
     (order is `form_hOUT`'s question), LOC is the roles street / house / flat
     (the settlement is out), PLATE is squeezed, the digital documents are
     digits, a date is ISO, and PHONE carries the PREFIX CLASS beside the last
     ten digits — the one place where the value line deliberately does not
     reduce to the needle layer, because `+7 916…` and `+1 916…` are not one
     number (Ж-1, Ж-3).
  2. THE ROLE PICKS THE TARGET, NEVER THE COMPARATOR: `leaf_value_ok` loses its
     fork, and the role still chooses the PART (`expected_leaf_value`).
  3. `script` IS THE ALPHABET AND `translit` IS THE ROMANIZATION SYSTEM, with
     `FORM_ABSTAIN[('NAME','translit')] = 'latin:unknown'` — the same
     abstention `order` already makes on `other` (Ж-5).
  4. THE TOOL SCHEMA IS THE AUTHORITATIVE NOTATION MARKER
     (`tools.LEAF_NOTATION`), AND NOTHING IS GUESSED BEYOND IT: each
     declaration is proved against the leaf's OWN parser by `notation_problems`
     (V08), and the corpus provocation may not teach a spelling that parser
     refuses (Ж-6, Ж-7).

THE GUARDS ARE AS MUCH THE POINT AS THE RULES, and they are the tripwires the
spike listed as «must stay green» — with the two whose MEANING the fix changes
recorded here rather than deleted:

  * a Cyrillic name answered by a Latin substitute MUST still differ on `script`
    (3 hops in the archives, 202 in g06 — a real class-Г leak);
  * an EMPTY target stays a MISS (the v4 defect «a triple with nothing to compare
    passed all five levels», pinned by `fx_end_to_end_adversarial` point 4);
  * ANOTHER value of the same type never satisfies the leaf, on every reading;
  * `form_hOUT` still names the notation it always named (`spaces`,
    `separators`, `case_class`) — the fix must not move the defect from the
    value line into the form line by DELETING the feature;
  * the LOC copies now AGREE (True/True) where the RED recorded them disagreeing
    (value True / `part_matches` False). That disagreement was the spike's proof
    that «just call `part_matches` from `value_matches`» is not the fix: the
    right rule was the LOC role rule, and it is now IN the shared table. The
    guard that survives is the one that matters — both answers must be RIGHT
    («Ленина 14» against «ленина, 14» IS one address).

NOTHING HERE RUNS AN AGENT, THE ENGINE, THE MODEL OR THE NETWORK. The defect
lives in this package, which by contract never imports `pseudex`;
`bench/agentpii4.tools.parse_snils` is read only as the tool's own ground truth.
"""
from bench.agentpii4.tools import parse_snils
from bench.agentpii5 import contracts, form, metrics, observe, pii_types, revise
from bench.agentpii5.scenarios5.retry_same_tool import _SNILS_MESSAGE
from bench.agentpii5.tools import (
    LEAF_NOTATION,
    LEAF_NOTATION_EVIDENCE,
    NOTATIONS,
    REGISTRY_V5,
    _calendar_free_parse,
    _vehicle_check_parse,
    leaf_notation,
    notation_problems,
    registry_problems,
    spec_v5_for,
)

# One person, one plate, one СНИЛС, one address — written out so every expectation
# below can be checked against the values instead of against a builder's default.
PLATE_PRODUCED, PLATE_CANONICAL = "в 163 оу 23", "В163ОУ23"
SNILS_PRODUCED, SNILS_CANONICAL = "01789723796", "017-897-237 96"
NAME_PRODUCED, NAME_CANONICAL = "Евгений Вольнов", "вольнов евгений"
LOC_PRODUCED, LOC_CANONICAL = "Ленина 14", "ленина, 14"

# The pairs all three former copies must answer ALIKE — and, in `_DIFFERENT`,
# the pairs none of them may accept. A shared table that answers True on the
# negative would be worse than three copies that answered False.
_SAME: tuple[tuple[str, str, str], ...] = (
    ("PLATE", "А 997 ММ 63", "А997ММ63"),
    ("SNILS", SNILS_PRODUCED, SNILS_CANONICAL),
    ("INN", "006073312820", "006 073 312 820"),
    ("CARD", "2200 1234 5678 9010", "2200123456789010"),
    ("PASSPORT", "4509 123456", "4509123456"),
    ("PHONE", "+7 916 402-11-87", "89164021187"),
    ("PHONE", "восемь девятьсот шестнадцать четыреста два одиннадцать восемьдесят семь",
     "+79164021187"),
    ("DOB", "1987-03-14", "14.03.1987"),
    ("NAME", NAME_PRODUCED, NAME_CANONICAL),
    ("LOC", LOC_PRODUCED, LOC_CANONICAL),
)
_DIFFERENT: tuple[tuple[str, str, str], ...] = (
    ("PLATE", "А 997 ММ 63", "А 997 ММ 64"),
    ("SNILS", SNILS_PRODUCED, "017-897-237 95"),
    ("INN", "006073312820", "006073312821"),
    ("CARD", "2200 1234 5678 9010", "2200 1234 5678 9011"),
    ("PASSPORT", "4509 123456", "4509 123457"),
    # THE ONE PLACE THE VALUE LINE IS NOT THE NEEDLE LAYER: the last ten digits
    # are identical and the numbers are not. The needle layer may read this as
    # «the value survived a rewrite» (identification); a LEAF may not (equality).
    ("PHONE", "+1 916 402 1187", "+7 916 402 1187"),
    ("DOB", "1987-03-14", "1987-03-15"),
    ("NAME", "Евгений Вольнов", "Евгений Вольнов Сергеевич"),
    ("LOC", "Ленина 14", "Ленина 15"),
)


def _item(item_id: str, pii_type: str, value: str, canonical: str,
          parts: dict[str, str]) -> object:
    from bench.agentpii4.schema import Locus, PiiItem
    return PiiItem(id=item_id, type=pii_type, identity=item_id, value=value,
                   canonical=canonical, parts=parts,
                   where=Locus(kind="message", msg=0, start=0, end=len(value),
                               record="", path=""),
                   duty="required", spoken=False, stale=False)


# --- Ж-1: one closed table, one predicate, three thin callers --------------------------

# THE V5 SLICE THIS INSTRUMENT IS ABOUT, READ FROM THE LIVE REGISTRY — NEVER
# HAND-COPIED, AND NEVER WIDENED BY INVENTION.
#
# `contracts.VALUE_NORMALISERS` is the v5 value table: eleven rows, one per v5
# type (`_V5_ITEM_TYPES` below is the ten item types of `v4.TYPES`) plus DATE.
# After the V1 registry migration `contracts.TYPES` is `v4.TYPES +
# pii_types.NEW_ITEM_TYPES` (66 ids), so a loop over `contracts.TYPES` demands a
# reading for all 55 v6 records — and there is none, BY DECISION: the v6 value
# comparison reads the registry's own `value_notation` (`metrics._v6_value_matches`),
# it deliberately does not route through this v5 table. Inventing 55 readings to
# satisfy a v5 instrument would be the instrument rewriting the decision it is
# supposed to measure (V1 SPEC §3.2 `INSTRUMENT-FIX-LEAF-READINGS`), so the
# instrument is RE-SCOPED to the slice it was built over.
_V5_ITEM_TYPES: tuple[str, ...] = tuple(
    spec.id for spec in pii_types.TYPE_REGISTRY
    if spec.origin == pii_types.ORIGIN_V5 and spec.item_type)
_V5_SLICE: tuple[str, ...] = _V5_ITEM_TYPES + ("DATE",)


def test_the_table_is_closed_and_every_type_reads_it() -> list[str]:
    """`contracts.VALUE_NORMALISERS` names a reading for EVERY v5-slice type, the
    reading is one the implementation declares, and the names on both sides are
    the same set — a table with a reading nothing implements would be a router to
    `KeyError` in the middle of a run.

    The table is also pinned to EXACTLY the v5 slice: a v6 row appearing here
    would be a reading the v6 decision never took, and it would be caught here
    rather than silently answering for 55 types."""
    problems: list[str] = []
    if set(contracts.VALUE_READINGS) != set(observe.VALUE_READINGS):
        problems.append(f"contracts declares {sorted(contracts.VALUE_READINGS)}, "
                        f"observe implements {sorted(observe.VALUE_READINGS)}")
    if len(_V5_SLICE) != 11 or len(set(_V5_SLICE)) != 11:
        problems.append(f"the v5 slice reads {sorted(_V5_SLICE)} — expected the "
                        f"eleven v5 records (10 item types + DATE)")
    if set(contracts.VALUE_NORMALISERS) != set(_V5_SLICE):
        extra = sorted(set(contracts.VALUE_NORMALISERS) - set(_V5_SLICE))
        missing = sorted(set(_V5_SLICE) - set(contracts.VALUE_NORMALISERS))
        problems.append(f"VALUE_NORMALISERS is not exactly the v5 slice: "
                        f"extra={extra} missing={missing}")
    for pii_type in _V5_SLICE:
        reading = contracts.VALUE_NORMALISERS.get(pii_type)
        if reading is None:
            problems.append(f"{pii_type} has no row: the default would answer silently")
            continue
        if reading not in contracts.VALUE_READINGS:
            problems.append(f"{pii_type} → {reading!r} is not a declared reading")
    # A CLOSED TABLE IS NOT A TABLE OF DEFAULTS. Every reading must be reachable
    # by some type, or the module carries a question nothing asks.
    unused = set(contracts.VALUE_READINGS) - set(contracts.VALUE_NORMALISERS.values())
    if unused:
        problems.append(f"readings no type uses: {sorted(unused)}")
    return problems


def test_the_three_former_copies_answer_alike() -> list[str]:
    """Ж-4: `revise._same_value` promised to agree with the value line and did
    not. One predicate means the agreement is structural, and the negative half
    is what keeps it from being bought by a predicate that says True."""
    problems: list[str] = []
    for pii_type, left, right in _SAME:
        answers = {
            "metrics.value_matches": metrics.value_matches(pii_type, left, right),
            "observe.part_matches": observe.part_matches(pii_type, left, right),
            "metrics.role_matches": metrics.role_matches(pii_type, left, right),
            "revise._same_value": revise._same_value(pii_type, left, right),
        }
        wrong = [name for name, answer in answers.items() if answer is not True]
        if wrong:
            problems.append(f"{pii_type} {left!r} vs {right!r}: {wrong} disagreed — "
                            f"the same value read another way is still the same value")
    for pii_type, left, right in _DIFFERENT:
        answers = {
            "metrics.value_matches": metrics.value_matches(pii_type, left, right),
            "observe.part_matches": observe.part_matches(pii_type, left, right),
            "revise._same_value": revise._same_value(pii_type, left, right),
        }
        wrong = [name for name, answer in answers.items() if answer is not False]
        if wrong:
            problems.append(f"{pii_type} {left!r} vs {right!r}: {wrong} said True — "
                            f"another value of the same type satisfied the leaf")
    return problems


def test_an_empty_side_is_a_miss() -> list[str]:
    """The v4 defect «a triple with nothing to compare passed all five levels».
    `value_matches('SNILS', '', '')` must not become a hit by comparing nothing
    to nothing, and neither must a leaf whose target has no such part."""
    problems: list[str] = []
    for pii_type in contracts.TYPES:
        if metrics.value_matches(pii_type, "", ""):
            problems.append(f"{pii_type}: '' == '' read as one value")
        if metrics.value_matches(pii_type, "", "017-897-237 96"):
            problems.append(f"{pii_type}: an empty produced side read as the value")
    # …and a role the target has NO part for stays a miss through the leaf
    # itself (`fx_end_to_end_adversarial` point 4).
    item = _item("i9", "NAME", "Вольнов Евгений", "вольнов евгений",
                 {"surname": "вольнов", "given": "евгений"})
    if metrics.leaf_value_ok(item, "crm_upsert_contact", "contact.middle_name", "Сергеевич"):
        problems.append("a patronymic the customer never said satisfied middle_name")
    return problems


def test_a_role_picks_the_target_and_not_the_comparator() -> list[str]:
    """Ж-3: the fork is gone. Both a role-less and a role leaf go through the
    same predicate, and the role still chooses the PART — so the whole value
    never satisfies a part leaf, and the part does satisfy it."""
    problems: list[str] = []
    item = _item("i8", "NAME", "Вольнов Евгений", "вольнов евгений",
                 {"surname": "вольнов", "given": "евгений"})
    if not metrics.leaf_value_ok(item, "crm_upsert_contact", "contact.last_name", "Вольнов"):
        problems.append("the surname did not satisfy contact.last_name")
    if metrics.leaf_value_ok(item, "crm_upsert_contact", "contact.last_name", "Евгений Вольнов"):
        problems.append("the WHOLE name satisfied a surname leaf")
    if not metrics.leaf_value_ok(item, "calendar_free", "person", "Евгений Вольнов"):
        problems.append("the role-less whole-value leaf rejected the whole value")
    return problems


# --- Ж-1 on the three witnesses ---------------------------------------------------------

def test_plate_respaced_is_one_value() -> list[str]:
    """`parallel-000/004/008/040`: the tool parsed the plate (it strips spaces and
    upper-cases) and the value line called it wrong for the spacing — which
    `form_hOUT` already owned."""
    problems: list[str] = []
    if not metrics.value_matches("PLATE", PLATE_PRODUCED, PLATE_CANONICAL):
        problems.append("the value line charged the spacing to the value")
    if not observe.part_matches("PLATE", PLATE_PRODUCED, PLATE_CANONICAL):
        problems.append("the needle layer and the value line disagreed")
    verdict = form.form_match("PLATE", PLATE_PRODUCED, PLATE_CANONICAL)
    if not set(verdict.differs) <= {"case_class", "spaces", "region_sep"}:
        problems.append(f"the form line named something that is not notation: "
                        f"{sorted(verdict.differs)}")
    if not verdict.differs:
        problems.append("the form line named NOTHING — the feature was deleted, not the defect")
    if not isinstance(_vehicle_check_parse({"plate": PLATE_PRODUCED}), dict):
        problems.append("the tool's own parser refused the produced spelling")
    item = _item("i1", "PLATE", PLATE_PRODUCED, PLATE_CANONICAL,
                 {"series": "В", "digits": "163", "letters": "ОУ", "region": "23"})
    if not metrics.leaf_value_ok(item, "vehicle_check", "plate", PLATE_PRODUCED):
        problems.append("the role-less leaf still called the same plate wrong")
    return problems


def test_snils_undashed_is_one_value_and_the_tool_still_asks_for_dashes() -> list[str]:
    """`retry_same_tool-006/014/…`: the tool's parser DEMANDS «XXX-XXX-XXX YY»
    and the value line is blind to that — the owner's ruling, spelled out. What
    the ruling does NOT excuse is the corpus provoking the attempt with a message
    teaching the notation the parser refuses (Ж-7)."""
    problems: list[str] = []
    if not metrics.value_matches("SNILS", SNILS_PRODUCED, SNILS_CANONICAL):
        problems.append("the value line charged the separators to the value")
    if form.form_match("SNILS", SNILS_PRODUCED, SNILS_CANONICAL).differs != frozenset({"separators"}):
        problems.append("the form line did not name exactly the separators")
    if not isinstance(parse_snils(SNILS_CANONICAL, "snils_verify", "snils"), str):
        problems.append("the tool's parser refused the dashed canonical")
    if isinstance(parse_snils(SNILS_PRODUCED, "snils_verify", "snils"), str):
        problems.append("the parser now accepts bare digits — the fork's frozen half moved, "
                        "and this test's premise with it")
    # THE PROVOCATION. It must not instruct a spelling the parser refuses.
    taught = _SNILS_MESSAGE.format(value=SNILS_CANONICAL)
    if "XXX-XXX-XXX YY" not in taught:
        problems.append(f"the forced-refusal message teaches no accepted notation: {taught!r}")
    if "одиннадцать цифр" in taught:
        problems.append(f"the message still asks for eleven bare digits: {taught!r}")
    return problems


def test_name_word_order_is_not_the_value() -> list[str]:
    """`calendar_free.person` (9 witnesses): the tool's own parser accepted
    «Ольга Кузнецова», the corpus canonical is the lowercase «вольнов евгений»,
    and the value line charged the ORDER — which `form_hOUT` does not name."""
    problems: list[str] = []
    if not metrics.value_matches("NAME", NAME_PRODUCED, NAME_CANONICAL):
        problems.append("the value line charged the word order to the value")
    if "order" in form.form_match("NAME", NAME_PRODUCED, NAME_CANONICAL).differs:
        problems.append("the form line charged the order too — one defect counted twice")
    if not isinstance(_calendar_free_parse({"person": NAME_PRODUCED, "date": "2026-09-10"}), dict):
        problems.append("the tool's own parser refused the produced word order")
    item = _item("i8", "NAME", NAME_PRODUCED, NAME_CANONICAL,
                 {"surname": "вольнов", "given": "евгений"})
    if not metrics.leaf_value_ok(item, "calendar_free", "person", NAME_PRODUCED):
        problems.append("the role-less leaf still called the same name wrong")
    # THE NEGATIVE: another person is another value, and the multiset comparison
    # must say so. (`parts_of` answers a ROLE→WORD map, so a word repeated in one
    # string is not a multiset member twice — the reading's own limit, named here
    # rather than pinned as if the comparison had claimed it.)
    if metrics.value_matches("NAME", "Евгений Вольнов", "евгений иванов"):
        problems.append("another person's surname satisfied the leaf")
    return problems


def test_the_loc_copies_now_agree_and_are_right() -> list[str]:
    """The RED's tripwire recorded the two copies DISAGREEING on LOC (value True
    / `part_matches` False) as the proof that routing one into the other is not
    the fix. The fix moved the LOC role rule INTO the table, so the disagreement
    is gone — and the guard that survives is that both answers are RIGHT, plus
    the negative that the settlement is not the address."""
    problems: list[str] = []
    if not metrics.value_matches("LOC", LOC_PRODUCED, LOC_CANONICAL):
        problems.append("the value line lost the LOC role rule")
    if not observe.part_matches("LOC", LOC_PRODUCED, LOC_CANONICAL):
        problems.append("the needle layer still disagrees with the value line on LOC "
                        "(the drift the table was built to end)")
    if metrics.value_matches("LOC", "Ленина 15", LOC_CANONICAL):
        problems.append("a different house satisfied the address")
    if metrics.value_matches("LOC", "Ленина", LOC_CANONICAL):
        problems.append("an address with no house satisfied one that has one")
    # THE SETTLEMENT IS NOT THE ADDRESS: a tool that keeps the city in its own
    # field is not a different address, and a different settlement is not the
    # same one. Both directions are the OLD rule, kept.
    if not metrics.value_matches("LOC", "Ижевск, улица Клубная, 85", "улица Клубная, 85"):
        problems.append("a produced side carrying the city failed the role comparison")
    if not metrics.value_matches("LOC", "улица Клубная, 85", "Ижевск, улица Клубная, 85"):
        problems.append("a target carrying the city failed the role comparison")
    return problems


# --- Ж-5: the alphabet and the romanization system are two features ---------------------

def test_script_is_the_alphabet() -> list[str]:
    problems: list[str] = []
    labels = {"cyrillic": "Родион", "latin": "Rodion", "mixed": "Rodion Родион",
              "none": "+79164021187"}
    for want, text in labels.items():
        got = form.name_script(text)
        if got != want:
            problems.append(f"name_script({text!r}) = {got!r}, wanted {want!r}")
    declared = set(contracts.FEATURE_LABELS[("NAME", "script")])
    if declared != set(labels):
        problems.append(f"the closed label set moved: {sorted(declared)}")
    return problems


def test_translit_is_the_romanization_system_and_it_abstains() -> list[str]:
    problems: list[str] = []
    if form.name_translit("Petrov Iurii") != "latin:icao":
        problems.append("«Iurii» is not read as ICAO")
    if form.name_translit("Petrov Yuriy") != "latin:bgn":
        problems.append("«Yuriy» is not read as BGN")
    if form.name_translit("EGOR BOBROV") != "latin:unknown":
        problems.append("a Latin name no table speaks for is not `latin:unknown`")
    if form.name_translit("Родион") != "latin:unknown":
        problems.append("a Cyrillic name claims a romanization system")
    # TWO LATIN STRINGS WITH NO OPINION MUST NOT DIFFER — the 50 misses of g07.
    if not form.form_match("NAME", "DMITRIY KUZNETSOV", "EGOR BOBROV").same:
        problems.append(f"two Latin strings still differ: "
                        f"{sorted(form.form_match('NAME', 'DMITRIY KUZNETSOV', 'EGOR BOBROV').differs)}")
    # …AND TWO SYSTEMS ARE A REAL DIFFERENCE, named by `translit`.
    if form.form_match("NAME", "Petrov Iurii", "Petrov Yuriy").differs != frozenset({"translit"}):
        problems.append("two romanization systems are no longer named")
    # THE GUARD: Cyrillic against Latin MUST stay a `script` difference (class Г),
    # and `translit` must abstain rather than charge the pair a second time.
    mixed = form.form_match("NAME", "Родион", "Rodion")
    if mixed.same or "script" not in mixed.differs:
        problems.append(f"the alphabet feature was deleted: {sorted(mixed.differs)}")
    if "translit" in mixed.differs:
        problems.append("one violation counted twice: `script` AND `translit`")
    if contracts.FORM_ABSTAIN.get(("NAME", "translit")) != "latin:unknown":
        problems.append("the abstention is not declared, so it is a silent skip")
    # THE CLOSED SET: every label any string can produce is declared, so an
    # adversarial fixture can name the label it expects (the `test_form` rule).
    for text in ("Petrov Iurii", "EGOR BOBROV", "Родион", "Rodion Родион"):
        label = form.name_translit(text)
        if label not in contracts.FEATURE_LABELS[("NAME", "translit")]:
            problems.append(f"name_translit({text!r}) = {label!r} is outside the closed set")
    return problems


# --- Ж-6/Ж-7: the tool schema is the authoritative notation marker ----------------------

def test_the_leaf_notation_table_is_declared_and_proven() -> list[str]:
    """A declaration no parser can refuse is not a declaration. V08 proves the
    declared spelling is ACCEPTED and that a demanding notation is the ONLY
    spelling accepted; a mutant must redden it."""
    problems: list[str] = []
    if registry_problems(REGISTRY_V5):
        problems.append(f"the live registry violates its own rules: {registry_problems(REGISTRY_V5)}")
    for (tool, path), notation in sorted(LEAF_NOTATION.items()):
        if notation not in NOTATIONS:
            problems.append(f"{tool}.{path}: {notation!r} is not a declared notation")
        if leaf_notation(tool, path) != notation:
            problems.append(f"{tool}.{path}: the accessor disagrees with the table")
        if (tool, path) not in LEAF_NOTATION_EVIDENCE:
            problems.append(f"{tool}.{path}: declared with nothing proving the parser demands it")
        if spec_v5_for(tool, path) is None:
            problems.append(f"{tool}.{path}: no FieldSpec — the declaration names no leaf")
    if not LEAF_NOTATION:
        problems.append("the table is empty: the marker is not declared anywhere")
    # THE MUTANT, run on a copy so the live table is untouched: a leaf that
    # declares «any» while its parser refuses the other spelling claims more
    # than the schema says, and the rule must say so.
    saved = dict(LEAF_NOTATION)
    try:
        LEAF_NOTATION[("snils_verify", "snils")] = "any"
        red = notation_problems(REGISTRY_V5)
        if not any(one.startswith("V08") for one in red):
            problems.append("a false declaration did not redden V08 — the rule cannot fail")
    finally:
        LEAF_NOTATION.clear()
        LEAF_NOTATION.update(saved)
    return problems


def test_the_value_line_does_not_judge_the_tool_schema() -> list[str]:
    """The owner's ruling, made mechanical: SNILS bare digits against the dashed
    canonical are ONE VALUE for the value line, while the leaf's own parser
    REFUSES the bare form. Both facts stand at once — that is what «the value
    line is notation-blind and the schema is a marker for the OUT substitution»
    means, and a test that let either half disappear would hide which ruling the
    package implements."""
    problems: list[str] = []
    if not metrics.value_matches("SNILS", SNILS_PRODUCED, SNILS_CANONICAL):
        problems.append("the value line judged the tool's schema")
    if isinstance(parse_snils(SNILS_PRODUCED, "snils_verify", "snils"), str):
        problems.append("the parser accepted the bare form, so the fork has no far side")
    if leaf_notation("snils_verify", "snils") != "snils":
        problems.append("the schema marker is not declared where the parser is")
    return problems


def main() -> int:
    checks = (
        ("z1_the_table_is_closed", test_the_table_is_closed_and_every_type_reads_it),
        ("z2_three_copies_answer_alike", test_the_three_former_copies_answer_alike),
        ("z3_an_empty_side_is_a_miss", test_an_empty_side_is_a_miss),
        ("z4_the_role_picks_the_target", test_a_role_picks_the_target_and_not_the_comparator),
        ("z5_plate_respaced_is_one_value", test_plate_respaced_is_one_value),
        ("z6_snils_undashed_is_one_value", test_snils_undashed_is_one_value_and_the_tool_still_asks_for_dashes),
        ("z7_name_order_is_not_the_value", test_name_word_order_is_not_the_value),
        ("z8_the_loc_copies_agree_and_are_right", test_the_loc_copies_now_agree_and_are_right),
        ("z9_script_is_the_alphabet", test_script_is_the_alphabet),
        ("z10_translit_abstains", test_translit_is_the_romanization_system_and_it_abstains),
        ("z11_leaf_notation_is_proven", test_the_leaf_notation_table_is_declared_and_proven),
        ("z12_the_value_line_is_blind", test_the_value_line_does_not_judge_the_tool_schema),
    )
    failures: list[str] = []
    for name, check in checks:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 - the exception IS the failure
            problems = [f"raised {error!r}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    broken = {one.split(":")[0] for one in failures}
    print(f"spike_zh: {'PASS' if not failures else 'FAIL'} "
          f"({len(checks) - len(broken)}/{len(checks)} passed)")
    if failures:
        print("\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
