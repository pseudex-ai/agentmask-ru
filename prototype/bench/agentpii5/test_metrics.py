"""`metrics.py` pinned: the registry, the denominators, and the controls it must ignore.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_metrics

The per-metric arithmetic is pinned by `fixtures.py` and run as a test by
`test_fixtures.py`; this file pins the promises that live BETWEEN metrics —
that every declared name has a function, that the public denominators are the
public ones, that a form line does not move when the v4 verdicts do, and that
an empty population prints «н/п» rather than 0%.
"""
import sys
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii3.schema import Negative
from bench.agentpii4.compare import LevelVerdict, PairVerdict
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import Hop, HopObservation, MentionRecord, RagSpec
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    FIXTURES,
    OTHER_NAME,
    REAL_NAME,
    REAL_PHONE,
    _case,
    _hop,
    _in_message,
    _in_seed,
    _item,
    _obs,
    _result,
    _run,
    _seen,
    _with_masked,
    _with_mentions,
    _with_results,
    _with_subs,
)
from bench.agentpii5.contracts import DocumentSpec
from bench.agentpii5.observe import observe
from bench.agentpii5.metrics import (
    HOP_AXES,
    HOP_SLICEABLE,
    METRIC_FUNCTIONS,
    answer_value_ok,
    by_axis,
    leaf_value_ok,
    prints_on_axis,
    returned_as_item,
)
from bench.agentpii5.tools import REGISTRY_V5, expected_leaf_value

NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
PHONE = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(0, 15, 27))


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_every_metric_registered() -> list[str]:
    """C-007. Every name the contracts declare, minus the six v4 paired levels
    (printed by v4's own report, not as a `Line`), has a function here."""
    want = set(contracts.METRIC_NAMES) - set(contracts.V4_LEVEL_NAMES)
    have = set(METRIC_FUNCTIONS)
    problems: list[str] = []
    if have - want:
        problems.append(f"metrics nobody declared: {sorted(have - want)}")
    if want - have:
        problems.append(f"declared metrics with no function: {sorted(want - have)}")
    for name in contracts.V4_LEVEL_NAMES:
        if name in have:
            problems.append(f"{name} is a v4 PAIRED level and must not be a v5 Line")
    return problems


def _form_case() -> tuple[object, object]:
    hop = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    case = _case("m-form", "single", (REAL_NAME,), (NAME,), (hop,))
    return case, hop


def test_form_lines_ignore_controls() -> list[str]:
    """C-017. The form check lives INSIDE arm I. v4 compared I with C and the
    comparison cancels form — two live models normalise a name the same way —
    so a form line that moved with `ic` would be v4's blind spot restored."""
    case, hop = _form_case()
    run = _run("m-form")
    blind = _obs(case, run, (_seen(case, hop, "NAME", "Орлову Ивану", "Орлов Иван"),))
    levels = LevelVerdict(tools=True, tools_sub="", keys=True, keys_sub="", state=True,
                          state_verbatim=True, state_diff=(), comparable=frozenset({"state"}))
    paired = replace(blind, ic=PairVerdict("IC", levels, (), ()),
                     cc=PairVerdict("CC", levels, (), ()))
    problems: list[str] = []
    for name in ("form_hIN", "form_hOUT", "chain_form", "answer_real"):
        left, right = METRIC_FUNCTIONS[name]((blind,)), METRIC_FUNCTIONS[name]((paired,))
        if (left.hits, left.total) != (right.hits, right.total):
            problems.append(f"{name} moved when the v4 verdicts were attached: "
                            f"{left.hits}/{left.total} vs {right.hits}/{right.total}")
    line = METRIC_FUNCTIONS["form_hIN"]((blind,))
    if (line.hits, line.total) != (0, 1):
        problems.append(f"the fixture cannot fail: form_hIN printed {line.hits}/{line.total}")
    return problems


def _chain(case_id: str, out_item: str, items: tuple[object, ...],
           produced: str) -> object:
    source = _hop("IN", "tool", "p1", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
    target = Hop(kind="OUT", owner="tool_arg", item_id=out_item, hop_index=1, turn=0,
                 tool_name="delivery_create_order", call_ordinal=0, parallel_group="",
                 source_hop=0, path="recipient.name", optional=False)
    case = _case(case_id, "sequential_chain", ("…",), items, (source, target))
    return _obs(case, _run(case_id), (_seen(case, source, "NAME", FAKE_NAME, REAL_NAME),
                                      _seen(case, target, "NAME", produced, FAKE_NAME)))


def test_chain_transitions() -> list[str]:
    """C-015. A transition is a declared OUT hop whose `source_hop` points at
    an IN/tool hop of ANOTHER tool. Same tool → no transition; no `source_hop`
    → no transition. The denominator is the case's declaration, so an agent
    that skipped the second call cannot shrink it."""
    other = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    kept = _chain("m-ch-1", "p1", (NAME,), REAL_NAME)
    problems: list[str] = []
    line = METRIC_FUNCTIONS["chain_value"]((kept,))
    if (line.hits, line.total) != (1, 1):
        problems.append(f"a kept value is 1/1, got {line.hits}/{line.total}")
    crossed = _chain("m-ch-2", "p9", (NAME, other), REAL_NAME)
    line = METRIC_FUNCTIONS["chain_value"]((crossed,))
    if (line.hits, line.total) != (0, 1):
        problems.append("a transition carrying another identity's hop must be a miss, "
                        f"got {line.hits}/{line.total}")
    same_tool = replace(kept.case, hops=(
        kept.case.hops[0], replace(kept.case.hops[1], tool_name="crm_find_contact")))
    folded = replace(kept, case=same_tool, hops=(
        kept.hops[0], replace(kept.hops[1], hop=replace(kept.hops[1].hop,
                                                        tool_name="crm_find_contact"))))
    line = METRIC_FUNCTIONS["chain_value"]((folded,))
    if line.total != 0:
        problems.append(f"a tool feeding its own result is not a chain, got total {line.total}")
    return problems


def test_rag_identity_kept() -> list[str]:
    """C-061. Two ways for a foreign identity to be mixed with the customer,
    and both must count: the stranger's real value in the customer's argument,
    and the customer's substitute standing where the stranger's value stood."""
    mine = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_seed("s1", "name"))
    theirs = _item("p9", "NAME", OTHER_NAME, OTHER_NAME, "i2", _in_seed("s2", "name"))
    out = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("m-rag", "rag", ("…",), (mine, theirs), (out,))
    case = replace(case, rag=RagSpec("kb_search", 2, ("s1", "s2"), ("i2",), ("p1",)))
    clean = _obs(case, _run("m-rag"), (_seen(case, out, "NAME", REAL_NAME, FAKE_NAME),))
    bled = _obs(case, _run("m-rag"), (_seen(case, out, "NAME", OTHER_NAME, FAKE_NAME),))
    text = f"Менеджер: {OTHER_NAME}."
    span = (10, 10 + len(OTHER_NAME))
    merged_run = _with_subs(_with_results(_run("m-rag"), (_result(
        "kb_search", 0, 0, "chunks", text, text, {"p9": span},
        ((span[0], span[1], FAKE_NAME, "NAME"),), False),)), {"p1": FAKE_NAME})
    merged = _obs(case, merged_run, (_seen(case, out, "NAME", REAL_NAME, FAKE_NAME),))
    problems: list[str] = []
    for label, one, want in (("clean", clean, 1), ("bled", bled, 0), ("merged", merged, 0)):
        line = METRIC_FUNCTIONS["rag_identity_kept"]((one,))
        if (line.hits, line.total) != (want, 1):
            problems.append(f"{label}: expected {want}/1, got {line.hits}/{line.total}")
    return problems


def test_public_denominators() -> list[str]:
    """C-168. One observation set, every public total asserted against the
    population `score.py` names — not against whatever the code happened to
    collect. A denominator nobody stated is a denominator that drifts."""
    in_user = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    in_tool = _hop("IN", "tool", "p2", 1, 0, "crm_find_contact", 0, -1, "contacts[].phone")
    out_name = _hop("OUT", "tool_arg", "p1", 2, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    out_phone = _hop("OUT", "tool_arg", "p2", 3, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    negative = Negative(value="TRK-1", start=40, end=45, msg=0, family="order_no", why="трек")
    case = _case("m-pub", "single", (f"{REAL_NAME}, {REAL_PHONE}, TRK-1",), (NAME, PHONE),
                 (in_user, in_tool, out_name, out_phone))
    case = replace(case, base=replace(case.base, negatives=(negative,)))
    span = (0, len(REAL_PHONE))
    run = _with_masked(_with_mentions(_with_results(_run("m-pub"), (_result(
        "crm_find_contact", 0, 0, "single", REAL_PHONE, "+79990001122", {"p2": span},
        ((span[0], span[1], "+79990001122", "PHONE"),), False),)),
        (MentionRecord("p1", 0, -1, FAKE_NAME, 0), MentionRecord("p1", 2, -1, FAKE_NAME, 1))),
        {0: ((0, len(REAL_NAME)),)})
    one = _obs(case, run, (
        _seen(case, in_user, "NAME", FAKE_NAME, REAL_NAME),
        _seen(case, in_tool, "PHONE", "+79990001122", REAL_PHONE),
        _seen(case, out_name, "NAME", REAL_NAME, FAKE_NAME),
        _seen(case, out_phone, "PHONE", REAL_PHONE, "+79990001122")))
    want = {"leak": 2, "coverage": 2, "typed": 1, "round_trip": 1, "round_trip_repaired": 1,
            "end_to_end": 2, "overmask": 1, "consistency": 1, "stability": 1}
    problems: list[str] = []
    for name, total in want.items():
        got = METRIC_FUNCTIONS[name]((one,)).total
        if got != total:
            problems.append(f"{name}: denominator {got}, the public one is {total}")
    # `round_trip` is over items the gateway ALTERED and a tool consumes;
    # `end_to_end` over ALL of them. Folding the two is how a passthrough
    # scores 100% on a line meant to say the data was protected.
    if METRIC_FUNCTIONS["round_trip"]((one,)).total == METRIC_FUNCTIONS["end_to_end"]((one,)).total:
        problems.append("round_trip and end_to_end got the same denominator on a set built "
                        "so that exactly one item was altered")
    return problems


def test_empty_is_na() -> list[str]:
    """A metric with nothing to say prints `Line(name, 0, 0)` and the report
    prints «н/п». Returning 0/1 instead would say the gateway failed something
    it was never asked to do."""
    problems: list[str] = []
    for name, function in sorted(METRIC_FUNCTIONS.items()):
        line = function(())
        if (line.hits, line.total) != (0, 0):
            problems.append(f"{name} on no observations printed {line.hits}/{line.total}")
        if line.name != name:
            problems.append(f"{name} returned a Line named {line.name!r}")
        if line.rate != 0.0 or line.certified is not None:
            problems.append(f"{name}: an empty line must not certify anything")
    return problems


def test_axes_split_hops_not_observations() -> list[str]:
    """C-080. A hop-level axis splits the HOPS: `form_hOUT` by `pii_type` must
    count a NAME hop under NAME and nowhere else. Splitting the observations
    instead would put every hop of a mixed case into every bucket."""
    in_name = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    in_phone = _hop("IN", "user", "p2", 1, 0, "", -1, -1, "")
    case = _case("m-axis", "single", ("…",), (NAME, PHONE), (in_name, in_phone))
    one = _obs(case, _run("m-axis"), (_seen(case, in_name, "NAME", FAKE_NAME, REAL_NAME),
                                      _seen(case, in_phone, "PHONE", REAL_PHONE, REAL_PHONE)))
    buckets = by_axis((one,), "pii_type")
    problems: list[str] = []
    if sorted(buckets) != ["NAME", "PHONE"]:
        problems.append(f"pii_type buckets are {sorted(buckets)}")
    for bucket, rows in buckets.items():
        line = METRIC_FUNCTIONS["form_hIN"](rows)
        if line.total != 1:
            problems.append(f"{bucket}: {line.total} hops in a bucket that holds one")
    if sorted(by_axis((one,), "behaviour")) != ["single"]:
        problems.append("an observation-level axis must not split the hops")
    try:
        by_axis((one,), "не ось")
        problems.append("an unknown axis was accepted")
    except ValueError:
        pass
    return problems


def _rich() -> object:
    """One observation with hops of two types, two owners and one tool — the
    smallest input on which a hop axis can move a denominator."""
    in_name = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    in_phone = _hop("IN", "user", "p2", 1, 0, "", -1, -1, "")
    out_name = _hop("OUT", "tool_arg", "p1", 2, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    out_phone = _hop("OUT", "tool_arg", "p2", 3, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    case = _case("m-rich", "single", (f"{REAL_NAME}, {REAL_PHONE}",), (NAME, PHONE),
                 (in_name, in_phone, out_name, out_phone))
    run = _with_masked(_run("m-rich"), {0: ((0, len(REAL_NAME)),)})
    return _obs(case, run, (
        _seen(case, in_name, "NAME", FAKE_NAME, REAL_NAME),
        _seen(case, in_phone, "PHONE", "+79990001122", REAL_PHONE),
        _seen(case, out_name, "NAME", "Иванова", "Пахомова"),
        _seen(case, out_phone, "PHONE", REAL_PHONE, "+79990001122")))


def test_hop_axis_totals_sum() -> list[str]:
    """A line printed inside a HOP bucket must be one a hop axis can split.

    `by_axis` on a hop axis hands every bucket a COPY of the observation
    carrying only that bucket's hops, so a metric whose denominator comes from
    `one.run` or `one.case` counts the same answer, turn or document once per
    bucket and the column adds up to more units than the corpus holds. The
    criterion is mechanical and it is checked here rather than declared: for a
    line `metrics.HOP_SLICEABLE` allows, the bucket totals must equal the
    whole line's total on every hop axis."""
    rows = (_rich(),)
    problems: list[str] = []
    for name in sorted(METRIC_FUNCTIONS):
        whole = METRIC_FUNCTIONS[name](rows).total
        for axis in HOP_AXES:
            parts = sum(METRIC_FUNCTIONS[name](bucket).total
                        for bucket in by_axis(rows, axis).values())
            allowed = prints_on_axis(name, axis)
            if allowed and parts != whole:
                problems.append(f"{name} by {axis}: buckets total {parts}, the line totals {whole} "
                                f"— it must not be in HOP_SLICEABLE")
            if not allowed and name in HOP_SLICEABLE:
                problems.append(f"{name}: HOP_SLICEABLE and prints_on_axis disagree on {axis}")
    if prints_on_axis("answer_real", "pii_type"):
        problems.append("answer_real is per ANSWER; a hop axis must not print it")
    if not prints_on_axis("answer_real", "register"):
        problems.append("an observation-level axis prints every line")
    return problems


def test_leaf_value_is_the_part() -> list[str]:
    """C-168 bis. A tool leaf that asks for a PART is scored against that part.

    `contact.last_name` takes the surname and `contact.phone` takes the digits;
    comparing either with the WHOLE canonical made a PERFECT gateway a miss,
    and `end_to_end` / `round_trip` / `multi_all_out` / `doc_extracted` /
    `chain_value` topped out at 76.8%. The third hop is the other half of the
    rule: a role the item has no part for cannot be satisfied by any string, so
    it is a miss and not a silent hit."""
    surname = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    phone = _hop("OUT", "tool_arg", "p2", 1, 0, "crm_upsert_contact", 0, -1, "contact.phone")
    patronymic = _hop("OUT", "tool_arg", "p1", 2, 0, "crm_upsert_contact", 0, -1,
                      "contact.middle_name")
    case = _case("m-leaf", "single", ("…",), (NAME, PHONE), (surname, phone, patronymic))
    perfect = _obs(case, _run("m-leaf"), (
        _seen(case, surname, "NAME", "Иванова", "Пахомова"),
        _seen(case, phone, "PHONE", "8 916 402-11-87", "8 999 000-11-22"),
        _seen(case, patronymic, "NAME", "Сергеевна", "Олеговна")))
    line = METRIC_FUNCTIONS["end_to_end"]((perfect,))
    problems: list[str] = []
    if (line.hits, line.total) != (2, 3):
        problems.append(f"the surname and the re-notated phone are the values those leaves ask "
                        f"for, the patronymic is not in the value at all: got {line.hits}/{line.total}")
    whole = _obs(case, _run("m-leaf"), (
        _seen(case, surname, "NAME", REAL_NAME, "Пахомова"),
        _seen(case, phone, "PHONE", REAL_PHONE, "8 999 000-11-22"),
        _seen(case, patronymic, "NAME", "", "")))
    line = METRIC_FUNCTIONS["end_to_end"]((whole,))
    if line.hits != 1:
        problems.append("the WHOLE name written into a surname field is not that leaf's value: "
                        f"got {line.hits}/{line.total}")
    return problems


# One sample value per PII type the registry's leaves ask for, in the notation
# a CRM stores. Written out rather than taken from a case, because this check
# has to hold for every (tool, path) of the registry and not for the types one
# corpus happens to carry.
LEAF_SAMPLES: dict[str, str] = {
    "NAME": "Иванова Елена Сергеевна",
    "PHONE": "+79164021187",
    "LOC": "Ижевск, улица Клубная, 85, кв. 12",
    "DOB": "14.03.1987",
    "EMAIL": "elena@example.ru",
    "CARD": "4276380123456789",
    "SNILS": "112-233-445 95",
    "INN": "165712345678",
    "PASSPORT": "9402 123456",
    "PLATE": "А123ВС18",
}
# Another person's value of each type — the same shape, a different datum.
OTHER_SAMPLES: dict[str, str] = {
    "NAME": "Пахомова Ольга Петровна",
    "PHONE": "+79990001122",
    "LOC": "Самара, улица Луговая, 10, кв. 3",
    "DOB": "02.11.1974",
    "EMAIL": "olga@example.com",
    "CARD": "5536913812345670",
    "SNILS": "998-877-665 44",
    "INN": "770112345678",
    "PASSPORT": "1122 334455",
    "PLATE": "В456СТ77",
}


def test_answer_is_scored_on_what_it_NAMED() -> list[str]:  # noqa: N802 - the claim is the name
    """An answer carries the PART it needs, declined — and that is the value.

    `_answer_hop_right` demanded the item's WHOLE canonical, byte for byte
    through `value_repaired`: the F1.1 defect the tool leg was rid of, left
    standing on the answer leg, where it is worse. «Передал Ивановой» for
    «Иванова Елена Петровна» and «Курьер поедет на Клубную 85» for «Ижевск,
    улица Клубная, 85, кв 14» are CORRECT answers, and over the corpus's own
    797 required answer hops 530 of them — 66% — were scored wrong. A line a
    perfect gateway cannot earn measures nothing.

    THE OTHER HALF IS WHAT KEEPS IT ABLE TO FAIL: another person's value, in
    the same declension, in the same span, is a WRONG value, and a partial
    mention of this person's is not."""
    person = _item("p1", "NAME", "Иванова Елена Петровна", "Иванова Елена Петровна", "i1",
                   _in_message(0, 0, 22))
    address = _item("p4", "LOC", "Ижевск, улица Клубная, 85, кв 14",
                    "Ижевск, улица Клубная, 85, кв 14", "i1", _in_message(0, 0, 31))
    stranger = _item("p9", "NAME", "Пахомова Ольга", "Пахомова Ольга", "i2", _in_seed("s2", "name"))
    phone = _item("p2", "PHONE", "+79164021187", "+79164021187", "i1", _in_message(0, 0, 12))
    case = _case("m-ans", "single", ("…",), (person, address, stranger, phone), ())
    one = _obs(case, _run("m-ans"), ())
    problems: list[str] = []
    right = (("the whole name", person, "Иванова Елена Петровна"),
             ("surname and given, declined", person, "Ивановой Елене"),
             ("the surname alone, declined", person, "Ивановой"),
             ("the given name alone, declined", person, "Елене"),
             ("the street and house, no city", address, "Клубную 85"),
             ("the street alone", address, "Клубную"),
             ("the phone renotated", phone, "8 (916) 402-11-87"))
    for label, item, produced in right:
        if not answer_value_ok(one, item, produced):
            problems.append(f"a correct answer naming {label} was scored WRONG: {produced!r}")
    wrong = (("another person, same declension", person, "Пахомовой Ольге"),
             ("another person's surname", person, "Пахомовой"),
             ("another person's street", address, "Лесную 12"),
             ("another phone", phone, "8 (999) 000-11-22"),
             ("nothing at all", person, "   "))
    for label, item, produced in wrong:
        if answer_value_ok(one, item, produced):
            problems.append(f"a wrong answer ({label}) was scored RIGHT: {produced!r}")
    # A span that carries this person AND a stranger is not this person's
    # value: the two stand in different places and one of them is not ours.
    if answer_value_ok(one, person, "Ивановой Елене и Пахомовой Ольге"):
        problems.append("a span carrying a stranger beside the customer was scored right")
    return problems


def test_leaf_value_has_one_definition() -> list[str]:
    """R-53. `tools.expected_leaf_value` decides what a leaf expects and
    `metrics.leaf_value_ok` only compares — over EVERY (tool, path) of
    `REGISTRY_V5`, not over the handful a fixture exercises.

    The two used to be written twice (`parts.get(role)` here, `item.parts.get(
    spec.role)` there) and two rules that must stay equal are one edit away
    from disagreeing about every value line at once. The negative is in the
    same loop: another person's value of the same type must NOT satisfy the
    leaf, or the check would pass on a function that returns True."""
    problems: list[str] = []
    for tool, spec in sorted(REGISTRY_V5.items()):
        for field in spec.base.fields:
            sample = LEAF_SAMPLES.get(field.pii_type)
            if sample is None:
                continue
            item = _item("p1", field.pii_type, sample, sample, "i1", _in_seed("s1", "f"))
            wanted = expected_leaf_value(item, field)
            if not wanted:
                # The item carries no part for this role (an `entrance` a
                # plain address does not have): the leaf is unsatisfiable and
                # `leaf_value_ok` must say so rather than wave it through.
                if leaf_value_ok(item, tool, field.path, sample):
                    problems.append(f"{tool}.{field.path}: no part for role {field.role!r} and "
                                    f"the metric accepted the whole value")
                continue
            if not leaf_value_ok(item, tool, field.path, wanted):
                problems.append(f"{tool}.{field.path}: tools says the leaf expects {wanted!r} and "
                                f"the metric scores it as the wrong value")
            other = _item("p2", field.pii_type, OTHER_SAMPLES[field.pii_type],
                          OTHER_SAMPLES[field.pii_type], "i2", _in_seed("s2", "f"))
            intruder = expected_leaf_value(other, field)
            if intruder and leaf_value_ok(item, tool, field.path, intruder):
                problems.append(f"{tool}.{field.path}: another person's {field.pii_type} "
                                f"({intruder!r}) satisfied this leaf")
    return problems


def test_chain_target_is_read_as_an_item() -> list[str]:
    """The hand-over's target is a STRING — what tool A returned — and it goes
    through the same definition by being read as an item. A chain leaf that
    asks for a part must therefore be satisfied by that part of the returned
    value, and by nothing else."""
    returned = "Иванова Елена Сергеевна"
    source = _item("s1", "NAME", returned, returned, "i1", _in_seed("r1", "name"))
    item = returned_as_item(source, returned)
    problems: list[str] = []
    if not leaf_value_ok(item, "crm_upsert_contact", "contact.last_name", "Иванова"):
        problems.append("the surname of the returned value did not satisfy contact.last_name")
    if leaf_value_ok(item, "crm_upsert_contact", "contact.last_name", returned):
        problems.append("the WHOLE returned name satisfied a surname leaf")
    if item.identity or item.id:
        problems.append("a returned value must carry no identity — it is in no such population")
    # H1.6. THE ROLES COME FROM THE SOURCE'S DECLARATION, NEVER FROM THE
    # STRING. `parts_of` reads a surname off its SUFFIX, and «заболотный»
    # wears none: re-guessing called a correct hand-over the wrong value on
    # four transitions of the committed corpus, and the class grows with every
    # regeneration that draws a name the suffix table does not know.
    plain = replace(_item("s2", "NAME", "заболотный", "заболотный", "i1", _in_seed("r1", "name")),
                    parts={"surname": "заболотный"})
    if not leaf_value_ok(returned_as_item(plain, "заболотный"),
                         "clinic_book", "patient.last_name", "заболотный"):
        problems.append("a surname with no surname suffix failed its own leaf")
    return problems


def test_coverage_of_a_value_no_message_carried() -> list[str]:
    """H1.3. A seed value has `Locus(kind='seed', msg=-1)`, so «was its message
    span masked» is a question about nothing: `masked_spans.get(-1)` is `()`
    and the hop was a forced miss whatever the gateway did — 70 declared hops
    of the corpus, and a perfect gateway's ceiling at 11660/11730. It is
    decided the way the hop was OBSERVED instead: no piece of the real value
    may survive in what the model actually read."""
    seed = _item("p5", "NAME", REAL_NAME, REAL_NAME, "i1", _in_seed("s1", "name"))
    hop = _hop("IN", "memory", "p5", 0, 3, "", -1, -1, "")
    case = _case("m-seed", "memory_anaphora", ("а", "б", "в", "г"), (seed,), (hop,))
    problems: list[str] = []
    for label, substitute, want in (("a fake was carried", FAKE_NAME, 1),
                                    ("the REAL value was carried", REAL_NAME, 0)):
        run = _with_mentions(_with_masked(_with_subs(_run("m-seed"), {"p5": substitute}),
                                          {0: (), 1: (), 2: (), 3: ()}),
                             (MentionRecord("p5", 0, -1, substitute, 1),))
        got = METRIC_FUNCTIONS["coverage"]((observe(case, run, None, None),))
        if (got.hits, got.total) != (want, 1):
            problems.append(f"seed coverage, {label}: {got.hits}/{got.total}, wanted {want}/1")
    return problems


def test_consistency_counts_a_tool_result_as_a_place() -> list[str]:
    """H1.4. Every tool-result mention carries `msg == -1`, so a population
    keyed on `msg` alone folded EVERY result into one place — and since no
    corpus item is both said in a message and echoed by a tool, the line had an
    EMPTY population on all 1 736 cases and could print nothing but «н/п». A
    public line that can only print «н/п» is the instrument that cannot fail."""
    case = _case("m-cons", "single", (REAL_NAME,), (NAME,), ())
    two_results = (MentionRecord("p1", -1, 0, FAKE_NAME, 1),
                   MentionRecord("p1", -1, 1, OTHER_NAME, 2))
    one_result = (MentionRecord("p1", -1, 0, FAKE_NAME, 1),
                  MentionRecord("p1", -1, 1, FAKE_NAME, 2))
    problems: list[str] = []
    for label, mentions, want in (("two substitutes", two_results, (0, 1)),
                                  ("one substitute", one_result, (1, 1))):
        got = METRIC_FUNCTIONS["consistency"]((
            _obs(case, _with_mentions(_run("m-cons"), mentions), ()),))
        if (got.hits, got.total) != want:
            problems.append(f"{label} across two tool results: {got.hits}/{got.total}, "
                            f"wanted {want[0]}/{want[1]}")
    return problems


def test_doc_extracted_counts_what_the_case_asks_for() -> list[str]:
    """H1.5. Two families name an extracted item the corpus gives the agent
    NOWHERE to put — no OUT hop into `extract_to_tool` at all — so 50 of 375
    items could not be hits whatever the gateway or the agent did and the
    ceiling was 86.7 %, which is exactly what a perfect gateway printed. A
    denominator with an unreachable floor in it is the mirror of v4's D1."""
    item = _item("p6", "NAME", REAL_NAME, REAL_NAME, "i1", _in_seed("d1", "name"))
    document = DocumentSpec(doc_id="d1", read_tool="file_read", format="free_text",
                            record_count=1, record_ids=("d1",),
                            extract_to_tool="crm_upsert_contact", extracted_item_ids=("p6",))
    problems: list[str] = []
    case = replace(_case("m-doc", "document", ("файл",), (item,), ()), document=document)
    got = METRIC_FUNCTIONS["doc_extracted"]((_obs(case, _run("m-doc"), ()),))
    if got.total != 0:
        problems.append(f"an item the case declares no extraction hop for is in the "
                        f"denominator: {got.hits}/{got.total}")
    hop = _hop("OUT", "tool_arg", "p6", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    asked = replace(_case("m-doc-2", "document", ("файл",), (item,), (hop,)), document=document)
    empty = METRIC_FUNCTIONS["doc_extracted"]((_obs(asked, _run("m-doc-2"), ()),))
    if (empty.hits, empty.total) != (0, 1):
        problems.append(f"a declared extraction the agent never made must be a MISS in the "
                        f"denominator, got {empty.hits}/{empty.total}")
    return problems


def test_a_free_leaf_is_satisfied_when_the_value_survives() -> list[str]:
    """H1.7. `notify_sms.text` is PROSE the agent composes around the value —
    «Здравствуйте, Миллер Валерий! Ваш заказ принят.» — and byte equality with
    the whole canonical is False by construction: 210 of `chain_value`'s 938
    declared transitions (22.4 %) landed on such a leaf and no gateway could
    earn them. It stays able to fail: another value, or none."""
    item = _item("p7", "NAME", "Миллер Валерий", "Миллер Валерий", "i1",
                 _in_message(0, 0, 14))
    problems: list[str] = []
    if not leaf_value_ok(item, "notify_sms", "text",
                         "Здравствуйте, Миллер Валерий! Ваш заказ принят."):
        problems.append("a free leaf carrying the value did not satisfy it")
    if leaf_value_ok(item, "notify_sms", "text", "Здравствуйте! Ваш заказ принят."):
        problems.append("a free leaf carrying NO value satisfied it")
    if leaf_value_ok(item, "notify_sms", "text", "Здравствуйте, Сидоров Пётр!"):
        problems.append("a free leaf carrying ANOTHER value satisfied it")
    return problems


def test_memory_stability_is_gone() -> list[str]:
    """J1.2. The line is REMOVED, and the removal is pinned rather than
    remembered.

    It asked whether a `MemorySpec` value's substitute changed between
    requests, and its population was empty on the whole corpus: 619 of 619
    memory specs have every mention in ONE request, because a `MentionRecord`
    is written once per message and a `MemorySpec` recall is anaphoric — it
    spells no value. It printed 0/0 for the perfect gateway and for every one
    of the 23 wrong gateways, so it could not go red, and H1.4's rule («a
    public line that can only print «н/п» is worse than no line») decides it.
    The check runs in three places at once because a name left in any ONE of
    them comes back as a line the report tries to print."""
    problems: list[str] = []
    if "memory_stability" in METRIC_FUNCTIONS:
        problems.append("memory_stability is registered again — its population is empty by "
                        "construction (J1.2)")
    if "memory_stability" in contracts.METRIC_NAMES:
        problems.append("memory_stability is declared in contracts.METRICS again")
    if "memory_stability" in FIXTURES:
        problems.append("memory_stability has fixtures again — they build by hand the only "
                        "population the line can ever have")
    # The other side of the assertion: `stability` and `memory_consistency` —
    # the two lines that DO ask this question, of populations that exist — are
    # still here, or «the name is gone» would pass on an empty registry.
    for survivor in ("stability", "memory_consistency"):
        if survivor not in METRIC_FUNCTIONS:
            problems.append(f"{survivor} went with it: the question is no longer asked at all")
    return problems


def test_answer_real_excludes_an_answer_that_obliges_nothing() -> list[str]:
    """J1.1 — v4's «all() over an empty list», on the leg the customer reads.

    A case may declare answer hops and oblige none of them; `required` is then
    empty, `all([])` is True, and a reply the gateway never touched has no
    substitute to be residual either. The pre-J1.1 body counted that a HIT, so
    a FULL PASSTHROUGH printed 720/1357 = 53.1% on the line named «the answer
    carries the real value». Such a case is outside the denominator, and
    `answer_optional_only` prints how many were left out."""
    optional = replace(_hop("OUT", "answer", "p1", 0, 0, "", -1, -1, ""), optional=True)
    required = _hop("OUT", "answer", "p1", 1, 0, "", -1, -1, "")
    problems: list[str] = []

    lax = _case("m-ar-lax", "single", ("…",), (NAME,), (optional,))
    passthrough = _obs(lax, _run("m-ar-lax"), (HopObservation(
        case_id="m-ar-lax", repeat=0, hop=optional, declared=True, pii_type="NAME",
        produced=REAL_NAME, reference=REAL_NAME, status="unmasked", verdict=None),))
    line = METRIC_FUNCTIONS["answer_real"]((passthrough,))
    if (line.hits, line.total) != (0, 0):
        problems.append(f"an answer that obliges nothing printed {line.hits}/{line.total}: "
                        f"a passthrough must not be able to score on it")
    excluded = METRIC_FUNCTIONS["answer_optional_only"]((passthrough,))
    if (excluded.hits, excluded.total) != (1, 1):
        problems.append(f"the exclusion was not printed: answer_optional_only "
                        f"{excluded.hits}/{excluded.total}")

    # The other side: a case that DOES oblige a hop is judged, so «excluded»
    # cannot have become «excluded always».
    strict = _case("m-ar-strict", "single", ("…",), (NAME,), (required,))
    honest = _obs(strict, _run("m-ar-strict"),
                  (_seen(strict, required, "NAME", REAL_NAME, REAL_NAME),))
    judged = METRIC_FUNCTIONS["answer_real"]((honest,))
    if (judged.hits, judged.total) != (1, 1):
        problems.append(f"a required answer hop is no longer judged: {judged.hits}/{judged.total}")
    if METRIC_FUNCTIONS["answer_optional_only"]((honest,)).hits != 0:
        problems.append("a case with a required hop was counted as an exclusion")
    # And an answer nobody declared is in NEITHER population: the corpus asks
    # the agent to name nothing, so there is no answer to judge and none to
    # exclude.
    silent = _obs(_case("m-ar-none", "single", ("…",), (NAME,), ()), _run("m-ar-none"), ())
    if METRIC_FUNCTIONS["answer_optional_only"]((silent,)).total != 0:
        problems.append("a case with no answer hop at all entered the exclusion population")
    return problems


def test_spoken_axis_tells_dictated_from_written() -> list[str]:
    """J1.3 / Б27. `form_hIN` prints 94.31% for a PERFECT gateway and the whole
    residue is dictated values: our engine mints a WRITTEN fake for a value the
    customer said aloud, so the substitute cannot wear the source's form. That
    is an ENGINE finding (`docs/known-issues.md` Б27), and without the slice
    the caption reads as an instrument defect.

    The bucket is `PiiItem.spoken` — what the corpus says about the SOURCE —
    and it is a HOP axis, so a case carrying one dictated and one written value
    splits into two buckets that add up to the whole line."""
    written_item = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, 13))
    said = replace(_item("p2", "NAME", "Орлов Иван", "Орлов Иван", "i2", _in_message(0, 20, 30)),
                   spoken=True)
    written_hop = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
    said_hop = _hop("IN", "user", "p2", 1, 0, "", -1, -1, "")
    case = _case("m-spoken", "single", ("…",), (written_item, said), (written_hop, said_hop))
    one = _obs(case, _run("m-spoken"),
               (_seen(case, written_hop, "NAME", FAKE_NAME, REAL_NAME),
                _seen(case, said_hop, "NAME", "Пахомова Ольга", "Орлов Иван")))
    problems: list[str] = []
    if "spoken" not in contracts.AXES:
        problems.append("`spoken` is not an axis: the residue of form_hIN cannot be read")
    if "spoken" not in HOP_AXES:
        problems.append("`spoken` is not a HOP axis: it would split observations, not hops")
    buckets = by_axis((one,), "spoken")
    if sorted(buckets) != ["написано", "продиктовано"]:
        problems.append(f"the buckets are {sorted(buckets)}, expected written and dictated")
        return problems
    for bucket, expected in (("написано", "p1"), ("продиктовано", "p2")):
        got = sorted(hop.hop.item_id for row in buckets[bucket] for hop in row.hops)
        if got != [expected]:
            problems.append(f"{bucket}: hops {got}, expected [{expected!r}]")
    whole = METRIC_FUNCTIONS["form_hIN"]((one,)).total
    parts = sum(METRIC_FUNCTIONS["form_hIN"](rows).total for rows in buckets.values())
    if parts != whole:
        problems.append(f"form_hIN by spoken: buckets total {parts}, the line totals {whole}")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("every_metric_registered", test_every_metric_registered),
        ("form_lines_ignore_controls", test_form_lines_ignore_controls),
        ("chain_transitions", test_chain_transitions),
        ("rag_identity_kept", test_rag_identity_kept),
        ("public_denominators", test_public_denominators),
        ("empty_is_na", test_empty_is_na),
        ("axes_split_hops_not_observations", test_axes_split_hops_not_observations),
        ("hop_axis_totals_sum", test_hop_axis_totals_sum),
        ("leaf_value_is_the_part", test_leaf_value_is_the_part),
        ("answer_is_scored_on_what_it_NAMED", test_answer_is_scored_on_what_it_NAMED),
        ("leaf_value_has_one_definition", test_leaf_value_has_one_definition),
        ("chain_target_is_read_as_an_item", test_chain_target_is_read_as_an_item),
        ("memory_stability_is_gone", test_memory_stability_is_gone),
        ("answer_real_excludes_an_answer_that_obliges_nothing",
         test_answer_real_excludes_an_answer_that_obliges_nothing),
        ("spoken_axis_tells_dictated_from_written", test_spoken_axis_tells_dictated_from_written),
        ("coverage_of_a_value_no_message_carried", test_coverage_of_a_value_no_message_carried),
        ("consistency_counts_a_tool_result_as_a_place",
         test_consistency_counts_a_tool_result_as_a_place),
        ("doc_extracted_counts_what_the_case_asks_for",
         test_doc_extracted_counts_what_the_case_asks_for),
        ("a_free_leaf_is_satisfied_when_the_value_survives",
         test_a_free_leaf_is_satisfied_when_the_value_survives),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("metrics: PASS" if not failures else "metrics: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
