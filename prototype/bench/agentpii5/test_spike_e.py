"""Класс Е (прибор) — the RED-then-GREEN test of `SPIKE-Е.md`, Е-1…Е-7.

    cd prototype && source .venv/bin/activate
    && PYTHONDONTWRITEBYTECODE=1 python3 -m bench.agentpii5.test_spike_e

WHY IT EXISTS. The instrument answered ONE symbol to THREE different questions
(`observe._out_status` returned `unmasked` for «the agent wrote nothing», «the
engine deliberately kept the settlement» and «a third value stands here») and
put THREE different populations into ONE denominator, so `end_to_end 41%` read
as a statement about the trajectory of a free agent rather than about the
engine. Until the causes are split, no engine fix can move the headline: the
signal drowns in the noise (DIAGNOSIS §Рефрейм).

THE GUARDS ARE THE POINT AS MUCH AS THE SPLIT. `C3`/`C5`/`C7` demand that the
headline denominators did NOT shrink. A treatment that narrows `end_to_end`
under its own name reproduces v4's D3 defect («a triple with nothing to compare
passed all five levels») and would let a counting fix be read as an engine
improvement — exactly what `actual_hops.py:124-126` forbids.

NOTHING HERE RUNS AN AGENT, THE ENGINE OR THE NETWORK. Every record is written
by hand with the builders of `fixtures.py`; the REAL observer and the REAL
metric functions are the things under test.
"""
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii5 import contracts
from bench.agentpii5 import report as report_mod
from bench.agentpii5.contracts import ArmRunV5, CaseV5, HopObservation
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    REAL_NAME,
    _call,
    _case,
    _hop,
    _in_message,
    _in_seed,
    _item,
    _run,
    _with_calls,
    _with_subs,
)
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.observe import ObserveError, observe

# One person and one address, written out so a reader can check every expected
# number against the values instead of against a builder's defaults.
NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
LOC = _item("p4", "LOC", "Ижевск, улица Клубная, 85", "Ижевск, улица Клубная, 85", "i1",
            _in_seed("s1", "address"))
SURNAME = "Иванова"
OTHER_SURNAME = "Сидорова"
CITY = "Ижевск"
CITY_FAKE = "Самара"
FAKE_LOC = "Самара, улица Луговая, 10"

# The statuses the split introduces, and the two closed populations the new
# lines read. Named here so a rename in `contracts` reddens this file.
SPLIT_STATUSES: tuple[str, ...] = ("engine_kept", "not_masked", "leaf_foreign")
NEW_LINES: tuple[str, ...] = (
    "end_to_end_written", "out_written", "out_no_mint", "out_engine_kept", "out_not_masked",
    "out_leaf_foreign", "multi_all_out_written", "chain_value_written", "chain_form_written")
NEW_NON_DIAGNOSTIC: tuple[str, ...] = (
    "end_to_end_written", "multi_all_out_written", "chain_value_written", "chain_form_written")
NULLARY = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")


def _obs(case: CaseV5, run: ArmRunV5, index: int = 0) -> HopObservation:
    """The DECLARED hop `index` as the real observer saw it.

    Read by declared index and not by position: a run that made a call the case
    never declared gets an EXTRA hop appended (`observe._extra_call_hops`), and
    indexing the tuple would score the extra one."""
    hops = observe(case, run, None, None).hops
    found = [hop for hop in hops if hop.declared and hop.hop.hop_index == index]
    if len(found) != 1:
        raise AssertionError(f"{case.base.id}: {len(found)} declared hops at index {index}")
    return found[0]


def _lines(case: CaseV5, run: ArmRunV5) -> dict[str, object]:
    """Every metric's `Line` on one observation."""
    observation = observe(case, run, None, None)
    return {name: function((observation,)) for name, function in METRIC_FUNCTIONS.items()}


def _cell(line: object) -> tuple[int, int]:
    return (line.hits, line.total)  # type: ignore[attr-defined]


# --- A: the empty slot is not a miss of the gateway ------------------------------------

def _empty_slot_case(optional: bool) -> tuple[CaseV5, ArmRunV5]:
    """A call the agent MADE whose slot is empty: the tool was invoked, the
    leaf was left blank. It was `unmasked` before this round — the fact about
    the AGENT that `out_absent` exists for, one level down."""
    hop = replace(NULLARY, optional=optional)
    case = _case("spike-a", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_calls(_run("spike-a"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": ""}},
        {"contact": {"last_name": ""}}, {}, "", 0),), (0,))
    return case, run


def test_a1_empty_slot_in_a_call_the_agent_made_is_absent() -> list[str]:
    """A1. The agent CALLED the tool and wrote nothing in the leaf: the fact is
    about the agent, and the leaf is `absent` — not a gateway miss."""
    case, run = _empty_slot_case(optional=False)
    got = _obs(case, run)
    if got.status != "absent":
        return [f"an empty slot inside a MADE call read {got.status!r}, must be 'absent'"]
    if got.verdict is not None:
        return ["an `absent` leaf carries no verdict — nothing was compared"]
    return []


def test_a2_an_optional_hop_skipped_by_the_leaf_counts_nowhere() -> list[str]:
    """A2. `contracts.Hop.optional` promises «an optional hop that did not
    happen is not observed and counts nowhere»; `_out_answer` already obeyed it
    and `_out_call` read `optional` only when the CALL was missing, so an empty
    slot inside a made call went into `form_hOUT`'s denominator. v4's D3 in
    miniature: the agent does less work and the rate drops."""
    case, run = _empty_slot_case(optional=True)
    problems: list[str] = []
    if observe(case, run, None, None).hops:
        problems.append("an optional hop the agent skipped was still observed")
    lines = _lines(case, run)
    for name in ("end_to_end", "end_to_end_written", "form_hOUT", "out_absent"):
        if _cell(lines[name]) != (0, 0):
            problems.append(f"{name} counts a hop that counts nowhere: {_cell(lines[name])}")
    return problems


# --- B: one status, one fact -----------------------------------------------------------

def _engine_kept_case() -> tuple[CaseV5, ArmRunV5]:
    """The settlement inside an address, LEFT REAL on purpose
    (`pseudex/vault.py::_settlement_of`), with the mint recorded for the same
    entity. The engine was awake and deliberately protected nothing here."""
    hop = _hop("OUT", "tool_arg", "p4", 0, 0, "courier_book", 0, -1, "address.locality")
    case = _case("spike-b-kept", "single", ("адрес",), (LOC,), (hop,))
    run = _with_subs(_with_calls(_run("spike-b-kept"), (_call(
        "courier_book", {"address": {"locality": CITY}},
        {"address": {"locality": CITY}}, {}, "", 0),), (0,)), {"p4": FAKE_LOC})
    return case, run


def _not_masked_case() -> tuple[CaseV5, ArmRunV5]:
    """A PASSTHROUGH: the gateway minted nothing for this entity and the agent
    wrote the correct real surname. There was nothing to restore."""
    hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("spike-b-none", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_calls(_run("spike-b-none"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": SURNAME}},
        {"contact": {"last_name": SURNAME}}, {}, "", 0),), (0,))
    return case, run


def _leaf_foreign_case() -> tuple[CaseV5, ArmRunV5]:
    """A THIRD value in the leaf: neither the substitute of this datum nor the
    customer's own. `form_match` cannot see it (`verdict is None`,
    `produced == reference`), so before this round the fact had no name."""
    hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    case = _case("spike-b-foreign", "single", (REAL_NAME,), (NAME,), (hop,))
    run = _with_subs(_with_calls(_run("spike-b-foreign"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": OTHER_SURNAME}},
        {"contact": {"last_name": OTHER_SURNAME}}, {}, "", 0),), (0,)), {"p1": FAKE_NAME})
    return case, run


def test_b1_b2_b3_the_three_causes_are_three_statuses() -> list[str]:
    """B1/B2/B3. The three facts that shared the word `unmasked`: the engine
    deliberately kept a generic part, the engine never minted, and a foreign
    value arrived. Three answers, three statuses — and each one names a
    different owner (product ruling / the IN leg / the agent)."""
    problems: list[str] = []
    want = {
        "engine_kept": _obs(*_engine_kept_case()),
        "not_masked": _obs(*_not_masked_case()),
        "leaf_foreign": _obs(*_leaf_foreign_case()),
    }
    for status, got in want.items():
        if got.status != status:
            problems.append(f"{status}: the observer says {got.status!r} "
                            f"(produced={got.produced!r} reference={got.reference!r})")
    if len({one.status for one in want.values()}) != 3:
        problems.append("two of the three causes still share a status")
    return problems


def test_b4_hop_statuses_carries_the_split() -> list[str]:
    """B4. The closed vocabulary a replay is read against must name every
    status the observer EMITS, and the two populations the new lines read must
    be subsets of it. `unmasked` stays declared — it is still what the ANSWER
    leg emits and what every saved artifact on disk carries (`records.py` checks
    this vocabulary on READ), and dropping it would take a replay down."""
    problems: list[str] = []
    for status in SPLIT_STATUSES:
        if status not in contracts.HOP_STATUSES:
            problems.append(f"HOP_STATUSES does not carry {status!r}")
    for name in ("OUT_HOP_WRITTEN_STATUSES", "OUT_HOP_RESTORABLE_STATUSES"):
        population = getattr(contracts, name, None)
        if not isinstance(population, frozenset):
            problems.append(f"contracts.{name} is not a declared frozenset")
            continue
        outside = sorted(population - set(contracts.HOP_STATUSES))
        if outside:
            problems.append(f"contracts.{name} names statuses outside HOP_STATUSES: {outside}")
    if "unmasked" not in contracts.HOP_STATUSES:
        problems.append("`unmasked` was removed from the closed vocabulary; a saved run "
                        "carrying it would no longer read back")
    restorable = contracts.OUT_HOP_RESTORABLE_STATUSES
    if not restorable < contracts.OUT_HOP_WRITTEN_STATUSES:
        problems.append("the restorable population is not a proper subset of the written one")
    if "engine_kept" in restorable or "not_masked" in restorable:
        problems.append("a leaf the engine had nothing to restore is in the honest denominator")
    return problems


def test_b5_a_passthrough_is_not_masked_and_an_exception_is_engine_kept() -> list[str]:
    """B5. The two halves of «no substitute stood in the leaf» that must never
    be merged: a passthrough gateway gets `not_masked`, an engine that left a
    generic part true ON PURPOSE gets `engine_kept`. Only the second needs the
    mint record — and that is why a handwritten run without `substitutes`
    cannot earn it (SPIKE-Е risk 3)."""
    problems: list[str] = []
    case, run = _engine_kept_case()
    if _obs(case, run).status != "engine_kept":
        problems.append("the deliberately-kept settlement is not `engine_kept`")
    case, run = _engine_kept_case()
    stripped = _with_subs(run, {})
    if _obs(case, stripped).status != "not_masked":
        problems.append("without a mint record the same leaf must fall to `not_masked` — "
                        "`engine_kept` is proved by the mint, never by the role alone")
    case, run = _not_masked_case()
    if _obs(case, run).status != "not_masked":
        problems.append("the passthrough leaf is not `not_masked`")
    return problems


# --- C: the denominators are split, never narrowed -------------------------------------

def _mixed_case() -> tuple[CaseV5, ArmRunV5]:
    """ONE leaf the agent wrote with the substitute (the engine restored it) and
    TWO leaves it never wrote. `end_to_end` is 1/3 and stays 1/3 (C7)."""
    first = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    second = _hop("OUT", "tool_arg", "p1", 1, 0, "crm_upsert_contact", 1, -1, "contact.first_name")
    third = _hop("OUT", "tool_arg", "p1", 2, 0, "crm_upsert_contact", 2, -1, "contact.middle_name")
    case = _case("spike-c-mixed", "single", (REAL_NAME,), (NAME,), (first, second, third))
    run = _with_subs(_with_calls(_run("spike-c-mixed"), (_call(
        "crm_upsert_contact", {"contact": {"last_name": "Пахомова"}},
        {"contact": {"last_name": SURNAME}}, {}, "", 0),), (0,)), {"p1": FAKE_NAME})
    return case, run


def test_c1_the_split_is_declared_as_lines_beside_the_strict_ones() -> list[str]:
    """C1. The decomposition is not a footnote: every count of the funnel and
    the honest share are REGISTERED lines, so the report prints them and the
    gate can refuse them. Registering a line means contracts.METRICS (what it
    counts) AND metrics.METRIC_FUNCTIONS (that it is counted) — two registries
    that `test_metrics.test_every_metric_registered` keeps equal."""
    problems: list[str] = []
    for name in NEW_LINES:
        if name not in contracts.METRIC_NAMES:
            problems.append(f"{name}: not declared in contracts.METRICS")
        if name not in METRIC_FUNCTIONS:
            problems.append(f"{name}: declared but not counted")
    for name in NEW_NON_DIAGNOSTIC:
        if name in contracts.DIAGNOSTIC_METRIC_NAMES:
            problems.append(f"{name}: a share of the engine cannot be a diagnostic")
    if "end_to_end_written" not in contracts.PUBLIC_METRIC_NAMES:
        problems.append("end_to_end_written is not a PUBLIC line — the honest share of the "
                        "round trip is exactly what must be published")
    return problems


def test_c2_every_new_line_is_printed_and_ships_three_fixtures() -> list[str]:
    """C2. A registered line the report does not place is a number nobody
    reads, and a line without the three fixture kinds is REFUSED by
    `report.gate_all` — which marks the whole report «НЕПОЛНЫЙ» for a
    non-diagnostic line and hides it in the diagnostics block for a diagnostic
    one. So: printed beside its strict sibling, and gated."""
    from bench.agentpii5.fixtures import FIXTURES

    problems: list[str] = []
    if report_mod.beside_of("end_to_end")[:1] != ("end_to_end_written",):
        problems.append(f"end_to_end's sibling is not printed first under it: "
                        f"{report_mod.beside_of('end_to_end')}")
    for strict, sibling in (("form_hOUT", "out_absent"), ("answer_real", "answer_optional_only"),
                            ("multi_all_out", "multi_all_out_written"),
                            ("chain_value", "chain_value_written"),
                            ("chain_form", "chain_form_written")):
        if sibling not in report_mod.beside_of(strict):
            problems.append(f"{sibling} is not printed under {strict}")
    for name in NEW_LINES:
        fixtures = FIXTURES.get(name)
        if not fixtures:
            problems.append(f"{name}: no fixtures — the report refuses it")
            continue
        kinds = sorted(fixture.kind for fixture in fixtures)
        if kinds != sorted(contracts.FIXTURE_KINDS):
            problems.append(f"{name}: fixture kinds {kinds}")
    return problems


def test_c3_guard_multi_all_out_still_counts_a_turn_nobody_wrote() -> list[str]:
    """GUARD. `multi_all_out` is a ratio over TURNS. A turn in which the agent
    wrote nothing is a MISS of the turn (g02: 55 of 56), and the honest sibling
    may not change that: if the strict line moved here, the whole comparison
    between the two would be a comparison of two different populations."""
    first = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
    second = _hop("OUT", "tool_arg", "p1", 1, 0, "crm_upsert_contact", 1, -1, "contact.first_name")
    case = _case("spike-c3", "parallel", (REAL_NAME,), (NAME,), (first, second))
    run = _run("spike-c3")
    lines = _lines(case, run)
    problems: list[str] = []
    if _cell(lines["multi_all_out"]) != (0, 1):
        problems.append(f"multi_all_out on a turn nobody wrote: {_cell(lines['multi_all_out'])}")
    if _cell(lines["multi_all_out_written"]) != (0, 0):
        problems.append("a turn with nothing written is not in the honest denominator, "
                        f"got {_cell(lines['multi_all_out_written'])}")
    return problems


def test_c4_the_honest_line_reads_1_of_1_on_the_written_leaf() -> list[str]:
    """C4. The same run that prints 1/3 on the strict headline prints 1/1 on
    the share of the engine: the only leaf the engine was asked about came back
    right, and the two the agent never wrote are a fact about the agent."""
    case, run = _mixed_case()
    lines = _lines(case, run)
    problems: list[str] = []
    if _cell(lines["end_to_end_written"]) != (1, 1):
        problems.append(f"end_to_end_written: {_cell(lines['end_to_end_written'])}, want 1/1")
    if _cell(lines["out_written"]) != (1, 3):
        problems.append(f"out_written: {_cell(lines['out_written'])}, want 1/3")
    return problems


def test_c5_guard_end_to_end_keeps_a_passthrough_at_zero() -> list[str]:
    """GUARD (F1.3). A passthrough scores 0 on `end_to_end`, never «н/п» and
    never 100: the strict denominator is the corpus's declaration, and narrowing
    it is how a protected-nothing gateway buys a good number."""
    case, run = _not_masked_case()
    problems: list[str] = []
    lines = _lines(case, run)
    if _cell(lines["end_to_end"]) != (0, 1):
        problems.append(f"end_to_end on a passthrough: {_cell(lines['end_to_end'])}")
    if _cell(lines["end_to_end_written"]) != (0, 0):
        problems.append(f"the honest denominator of a passthrough must be empty: "
                        f"{_cell(lines['end_to_end_written'])}")
    if _cell(lines["out_not_masked"]) != (1, 1):
        problems.append(f"out_not_masked: {_cell(lines['out_not_masked'])}")
    return problems


def test_c6_the_city_leaf_has_a_share_of_zero_of_zero_and_a_printed_exception() -> list[str]:
    """C6. `address.locality` cannot become `observed` by construction
    (`vault._settlement_of` keeps the settlement real), so on a lone city hop
    the honest share is «н/п» — not 100 % and not 0 — and the exception is a
    printed count, never a silent subtraction (SPIKE-Е risk 2)."""
    case, run = _engine_kept_case()
    lines = _lines(case, run)
    problems: list[str] = []
    if _cell(lines["end_to_end_written"]) != (0, 0):
        problems.append(f"a hop that cannot be restored must print «н/п», "
                        f"got {_cell(lines['end_to_end_written'])}")
    if _cell(lines["out_engine_kept"]) != (1, 1):
        problems.append(f"the exception was not printed: {_cell(lines['out_engine_kept'])}")
    if _cell(lines["end_to_end"]) != (0, 1):
        problems.append(f"the strict line must still hold the city hop as a miss: "
                        f"{_cell(lines['end_to_end'])}")
    return problems


def test_c7_c8_c9_guard_the_headline_denominator_and_publish_the_truth() -> list[str]:
    """C7/C8/C9. ONE run: the strict headline keeps the corpus timetable (1/3),
    the honest share is published beside it (1/1), and `out_absent` stops
    under-counting — before this round it printed 0/3 on a run with two
    unwritten leaves, because they were `unmasked` and not `absent`."""
    case, run = _mixed_case()
    lines = _lines(case, run)
    problems: list[str] = []
    if _cell(lines["end_to_end"]) != (1, 3):
        problems.append(f"GUARD: the headline denominator moved: {_cell(lines['end_to_end'])}")
    if _cell(lines["end_to_end_written"]) != (1, 1):
        problems.append(f"end_to_end_written: {_cell(lines['end_to_end_written'])}")
    if _cell(lines["out_absent"]) != (2, 3):
        problems.append(f"out_absent under-counts the unwritten leaves: "
                        f"{_cell(lines['out_absent'])}")
    return problems


# --- D: reachability is a property of the corpus ----------------------------------------

def test_d1_d2_a_leaf_the_product_keeps_real_cannot_be_required() -> list[str]:
    """D1/D2. `courier_book.address.locality` and
    `delivery_create_order.to_location.city` are `required=True, role='city'`,
    and `vault._settlement_of` keeps the settlement real BY PRODUCT DECISION —
    so a REQUIRED hop on that leaf is a promise no correct gateway can keep
    (g07: «a hop that cannot become observed by construction»). The corpus's own
    builders decide optionality, and they must read the role beside the schema.

    The negative controls are the two other shapes: a required non-generic leaf
    stays required, and a non-required leaf stays optional."""
    from bench.agentpii5.scenarios5.common import arg_hop

    problems: list[str] = []
    for index, (tool, path) in enumerate((("courier_book", "address.locality"),
                                          ("delivery_create_order", "to_location.city"))):
        hop = arg_hop("p4", index, 7, tool, 0, path, -1, "")
        if not hop.optional:
            problems.append(f"{tool}.{path}: required hop on a leaf the product keeps real")
    required_not_generic = arg_hop("p4", 9, 7, "courier_book", 0, "address.street", -1, "")
    if required_not_generic.optional:
        problems.append("a required non-generic leaf became optional")
    optional_not_generic = arg_hop("p4", 10, 7, "courier_book", 0, "address.porch", -1, "")
    if not optional_not_generic.optional:
        problems.append("a non-required leaf stopped being optional")
    return []


# --- E: the authorial leaf equivalence --------------------------------------------------

def test_e1_a_declared_hop_is_satisfied_by_the_equivalent_leaf_the_agent_wrote() -> list[str]:
    """Е-6. The case declared `courier_book.address.locality`; the agent wrote
    the same settlement into `crm_upsert_contact.contact.address.city` in the
    same turn. The datum crossed once and came back once — the instrument read
    it `absent` (g08: 25 of 30) because it looked for the corpus's TOOL NAME
    instead of the semantic leaf."""
    declared = _hop("OUT", "tool_arg", "p4", 0, 0, "courier_book", 0, -1, "address.locality")
    case = _case("spike-e1", "single", ("адрес",), (LOC,), (declared,))
    run = _with_subs(_with_calls(_run("spike-e1"), (_call(
        "crm_upsert_contact", {"contact": {"address": {"city": CITY_FAKE}}},
        {"contact": {"address": {"city": CITY}}}, {}, "", 0),), (0,)), {"p4": FAKE_LOC})
    got = _obs(case, run)
    problems: list[str] = []
    if got.status != "observed":
        problems.append(f"the equivalent leaf was not read: status {got.status!r} "
                        f"(produced={got.produced!r} reference={got.reference!r})")
    elif CITY not in got.produced:
        problems.append(f"the real settlement did not arrive: {got.produced!r}")
    lines = _lines(case, run)
    if _cell(lines["end_to_end"]) != (1, 1):
        problems.append(f"the strict line did not credit the crossing: "
                        f"{_cell(lines['end_to_end'])}")
    return problems


def test_e2_two_equivalent_leaves_with_different_values_make_the_rule_fall() -> list[str]:
    """Е-6, the half that keeps the table honest. When two semantically equal
    leaves carry DIFFERENT values, the instrument must refuse to choose: picking
    one would credit a value the agent may not have carried (SPIKE-Е risk 5).
    The read is a raise, not a silent preference."""
    declared = _hop("OUT", "tool_arg", "p4", 0, 0, "courier_book", 0, -1, "address.locality")
    case = _case("spike-e2", "single", ("адрес",), (LOC,), (declared,))
    run = _with_subs(_with_calls(_run("spike-e2"), (
        _call("crm_upsert_contact", {"contact": {"address": {"city": CITY_FAKE}}},
              {"contact": {"address": {"city": CITY}}}, {}, "", 0),
        _call("delivery_create_order", {"to_location": {"city": "Омск"}},
              {"to_location": {"city": "Омск"}}, {}, "", 1)), (0, 0)), {"p4": FAKE_LOC})
    try:
        observed = observe(case, run, None, None)
    except ObserveError as error:
        return [] if "equivalent" in str(error).lower() or "equal" in str(error).lower() else [
            f"the refusal does not say why: {error}"]
    return [f"two equal leaves with different values were resolved by preference: "
            f"{[(hop.hop.tool_name, hop.status) for hop in observed.hops]}"]


def test_e4_a_claimed_leaf_is_one_crossing_and_not_two_hops() -> list[str]:
    """Е-6, the accounting half. The crossing the declared hop was satisfied by
    is ONE crossing: the undeclared-hop scan used to see the same call the
    proven equivalence now claims (`observe.claimed`), and counting it twice
    would inflate every hop-level denominator by exactly the population the
    table was written for (g08's 25 of 30)."""
    declared = _hop("OUT", "tool_arg", "p4", 0, 0, "courier_book", 0, -1, "address.locality")
    case = _case("spike-e4", "single", ("адрес",), (LOC,), (declared,))
    run = _with_subs(_with_calls(_run("spike-e4"), (_call(
        "crm_upsert_contact", {"contact": {"address": {"city": CITY_FAKE}}},
        {"contact": {"address": {"city": CITY}}}, {}, "", 0),), (0,)), {"p4": FAKE_LOC})
    observation = observe(case, run, None, None)
    problems: list[str] = []
    if len(observation.hops) != 1:
        problems.append(f"one crossing read as {len(observation.hops)} hops: "
                        f"{[(hop.hop.tool_name, hop.declared) for hop in observation.hops]}")
    lines = _lines(case, run)
    # `residual` adds one term per OBSERVATION on top of one per leaf, so one
    # crossing in one run is 2/2 and not 1/1 — the arithmetic of its own
    # denominator, not a second hop.
    for name, want in (("form_hOUT", (1, 1)), ("out_written", (1, 1)), ("residual", (2, 2))):
        if _cell(lines[name]) != want:
            problems.append(f"{name}: {_cell(lines[name])}, want {want}")
    return problems


def test_e5_two_spellings_of_one_value_are_one_candidate() -> list[str]:
    """Е-6, the negative control of E2. «Самара» and «самара» in two equivalent
    leaves are ONE value written twice, not two: a rule that refused over the
    tool's capitalisation would stop a live run on a case difference and would
    be measuring the notation rather than the datum."""
    declared = _hop("OUT", "tool_arg", "p4", 0, 0, "courier_book", 0, -1, "address.locality")
    case = _case("spike-e5", "single", ("адрес",), (LOC,), (declared,))
    run = _with_subs(_with_calls(_run("spike-e5"), (
        _call("crm_upsert_contact", {"contact": {"address": {"city": CITY_FAKE}}},
              {"contact": {"address": {"city": CITY}}}, {}, "", 0),
        _call("delivery_create_order", {"to_location": {"city": CITY_FAKE.lower()}},
              {"to_location": {"city": CITY}}, {}, "", 1)), (0, 0)), {"p4": FAKE_LOC})
    got = _obs(case, run)
    if got.status != "observed":
        return [f"one value in two spellings was refused: status {got.status!r}"]
    return []


def test_e3_the_equivalence_table_is_closed_and_authorial() -> list[str]:
    """Е-6. The table folds leaves that carry the SAME datum in the SAME role —
    it is grounded in the registry's own `FieldSpec.pii_type` / `.role`, never
    in a guess off the tool name (an `actual_hops` warning: matching by tool
    name «can tie a re-search, a second delivery, or data the agent had not been
    given to the wrong event»). Checked on the landed registry AND shown to
    fail on a broken copy — a rule that cannot go red is decoration."""
    from bench.agentpii5.tools import spec_v5_for

    problems: list[str] = []
    landed = contracts.equivalence_problems(spec_v5_for)
    if landed:
        problems.append(f"the landed table violates its own rules: {landed}")
    broken = (("city", ("courier_book.address.locality", "courier_book.address.street")),)
    if not contracts.equivalence_problems(spec_v5_for, broken):
        problems.append("two leaves of DIFFERENT roles in one class were accepted")
    ghost = (("city", ("courier_book.address.locality", "nowhere.at.all")),)
    if not contracts.equivalence_problems(spec_v5_for, ghost):
        problems.append("a leaf no tool carries was accepted")
    if not contracts.equivalence_problems(spec_v5_for, (("city", ("a.b",)),)):
        problems.append("a class of one leaf was accepted — a class that folds nothing")
    return []


# --- the runner ------------------------------------------------------------------------

def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("a1_empty_slot_is_absent", test_a1_empty_slot_in_a_call_the_agent_made_is_absent),
        ("a2_optional_hop_counts_nowhere",
         test_a2_an_optional_hop_skipped_by_the_leaf_counts_nowhere),
        ("b1_b2_b3_three_causes_three_statuses",
         test_b1_b2_b3_the_three_causes_are_three_statuses),
        ("b4_hop_statuses_carries_the_split", test_b4_hop_statuses_carries_the_split),
        ("b5_passthrough_and_exception_apart",
         test_b5_a_passthrough_is_not_masked_and_an_exception_is_engine_kept),
        ("c1_the_split_is_declared", test_c1_the_split_is_declared_as_lines_beside_the_strict_ones),
        ("c2_printed_and_gated", test_c2_every_new_line_is_printed_and_ships_three_fixtures),
        ("c3_guard_multi_all_out", test_c3_guard_multi_all_out_still_counts_a_turn_nobody_wrote),
        ("c4_honest_line_reads_one_of_one",
         test_c4_the_honest_line_reads_1_of_1_on_the_written_leaf),
        ("c5_guard_passthrough_is_zero", test_c5_guard_end_to_end_keeps_a_passthrough_at_zero),
        ("c6_city_is_zero_of_zero_with_the_exception_printed",
         test_c6_the_city_leaf_has_a_share_of_zero_of_zero_and_a_printed_exception),
        ("c7_c8_c9_headline_guard_and_the_truth",
         test_c7_c8_c9_guard_the_headline_denominator_and_publish_the_truth),
        ("d1_d2_generic_role_is_optional",
         test_d1_d2_a_leaf_the_product_keeps_real_cannot_be_required),
        ("e1_equivalent_leaf_satisfies_the_hop",
         test_e1_a_declared_hop_is_satisfied_by_the_equivalent_leaf_the_agent_wrote),
        ("e2_two_equal_leaves_with_two_values_fall",
         test_e2_two_equivalent_leaves_with_different_values_make_the_rule_fall),
        ("e3_the_table_is_closed_and_authorial", test_e3_the_equivalence_table_is_closed_and_authorial),
        ("e4_a_claimed_leaf_is_one_hop", test_e4_a_claimed_leaf_is_one_crossing_and_not_two_hops),
        ("e5_two_spellings_of_one_value", test_e5_two_spellings_of_one_value_are_one_candidate),
    )
    failures: list[str] = []
    for name, check in checks:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 - the exception IS the failure
            problems = [f"raised {error!r}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print(f"spike_e: {'PASS' if not failures else 'FAIL'} "
          f"({len(checks) - len({one.split(':')[0] for one in failures})}/{len(checks)} passed)")
    if failures:
        print("\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
