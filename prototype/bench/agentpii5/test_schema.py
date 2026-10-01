"""Every rule of `schema.py`, shown to FAIL on a case built to break it.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_schema

THE SHAPE OF EVERY RULE TEST, AND WHY. A valid case is built — by the real
`CaseBuilderV5`, not by hand, so the builder is under test too — and
`validate_v5` says nothing about it. Then ONE field is replaced, and the test
asserts the rule ids that appear are EXACTLY the one being broken. Asserting
only «the id is present» would pass a validator that reports every rule on
every case, and a validator that cannot be quiet cannot accuse.

THE CORPUS RULES NEED A CORPUS THAT PASSES THEM. A synthetic 1600-case corpus
is built to satisfy K01–K15 with nothing to report, and each `test_kNN` breaks
one thing in a copy of it. Without the clean corpus the tests would be run
against a baseline already full of problems, where a rule that stopped working
is invisible — the defect class this repository calls «an instrument that
cannot fail».

K12 is not tested here because `schema.py` does not implement it: it is a claim
about `ladder.json`, and `test_build.test_holdout_frozen` owns it.

`common.py` is tested here too (the register mix, the plate renderer, the
builder's own guards): it is the other half of this component and
`test_schema.py` is the only test file the spine ships.
"""
import json
import random
import sys
from dataclasses import replace

from bench.agentpii4 import pools
from bench.agentpii4.pools import BuildError
from bench.agentpii4.schema import (Case, Expectation, InvalidCase, Locus, Message, PiiItem,
                                    Provenance, SeedRecord, TraceRow)
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema as s
from bench.agentpii5.contracts import (BranchSpec, CaseV5, DocumentSpec, ForcedError, Hop,
                                       LoopSpec, MemorySpec, PickSpec, RagSpec,
                                       ReturnExpectation)
from bench.agentpii5.mock import BackendV5
from bench.agentpii5.scenarios5 import common
from bench.agentpii5.scenarios5.common import NOW_V5

SYNTHETIC_SIZE: int = 1600
# 6 + 3 + 6 + 3 + 2 = 20, and `REGISTER_SHARES` now adds to 1.00 (ruling R-16),
# so 9 : 6 : 3 : 2 out of twenty IS the ratio — voice 45%, chat 30%, sloppy 15%,
# clean 10%, each exactly on target rather than inside a band. Position 0 is
# `voice_raw`, which is what the streaming rule below leans on.
SYNTHETIC_REGISTERS: tuple[str, ...] = (
    ("voice_raw",) * 6 + ("voice_itn",) * 3 + ("chat",) * 6 + ("sloppy",) * 3 + ("clean",) * 2)


# --- the valid case, built by the real builder --------------------------------

def _valid_case() -> CaseV5:
    """One `single` case with the minimal loop: the customer gives a phone, the
    agent looks the card up, the answer reads the name back."""
    ctx = common.ctx_for("single", 5, 0, "chat")
    drawn = common.draw(ctx, city="Самара", with_flat=True, with_entrance=False,
                        with_type=True, foreign=False)
    builder = common.new_builder(
        ctx, "crm", tools=("crm_find_contact", "notify_sms"),
        reachable=("crm_find_contact", "notify_sms"), primary_identity="p1",
        cluster="NAME:fixture", note="фикстура test_schema", extras=(common.MEMORY_CLAUSE,))
    draft = builder.draft()
    draft.say("здравствуйте найдите карточку по телефону")
    draft.value("ph", common.phone(ctx, drawn.phone))
    turn = builder.user(draft, {"ph": ("PHONE", "p1", "required", False)})
    # `contact_seed` is v4's and takes «a builder»: it calls `builder.seed(...)`,
    # which `CaseBuilderV5` re-exposes with v4's signature. Passing the v5
    # builder here is the assertion that generator_a may do the same.
    common.contact_seed("c1", drawn, "Самара", ctx, builder, "p1")
    said = [item for item in builder.v4.pii if item.where.kind == "message"][0]
    seeds = [item for item in builder.v4.pii if item.where.kind == "seed"]
    seed_phone = [item for item in seeds if item.type == "PHONE"][0]
    seed_name = [item for item in seeds if item.where.path == "last_name"][0]
    builder.declare_hop(Hop("IN", "user", said.id, 0, turn, "", -1, "", -1, "", False))
    builder.declare_hop(Hop("OUT", "tool_arg", said.id, 1, turn, "crm_find_contact", 0, "",
                            0, "query.phone", False))
    builder.declare_hop(Hop("IN", "tool", seed_phone.id, 2, turn, "crm_find_contact", 0, "",
                            -1, "contacts[].phone", False))
    builder.declare_hop(Hop("OUT", "answer", seed_name.id, 3, turn, "", -1, "", 2, "", True))
    # A fifth hop nothing sources and which sources nothing: the tests of R04
    # need a hop they can break without also breaking somebody's chain, and a
    # second value in the answer is what a real reply carries anyway.
    builder.declare_hop(Hop("OUT", "answer", seed_phone.id, 4, turn, "", -1, "", -1, "", True))
    builder.expect_return(ReturnExpectation("crm_find_contact", 0, "list",
                                            (seed_phone.id, seed_name.id)))
    return builder.build("single")


VALID: CaseV5 = _valid_case()


def _ids(problems: list[str]) -> set[str]:
    """The rule ids a report names, so a test can say «exactly these»."""
    return {problem.split()[0] for problem in problems}


def _expect(case: CaseV5, rule: str) -> list[str]:
    """`case` violates `rule` and nothing else."""
    problems = s.validate_v5(case)
    seen = _ids(problems)
    if seen != {rule}:
        return [f"{rule}: report names {sorted(seen) or 'nothing'}\n    "
                + "\n    ".join(problems[:6])]
    return []


# --- R01 … R21 -----------------------------------------------------------------

def test_valid_case_is_quiet() -> list[str]:
    """The positive atom every negative below is measured against."""
    problems = s.validate_v5(VALID)
    if problems:
        return ["a case the builder accepted still has problems:\n    "
                + "\n    ".join(problems[:8])]
    if not VALID.has_result or len(VALID.hops) < c.MIN_HOPS_WITH_RESULT:
        return [f"the fixture is not the minimal loop: has_result={VALID.has_result}, "
                f"{len(VALID.hops)} hops"]
    return []


def test_r01() -> list[str]:
    return _expect(replace(VALID, behaviour="не поведение"), "R01")


def test_r02() -> list[str]:
    """v4's own per-case validator is CALLED, not reimplemented: an empty note
    is v4's rule and must still be reported, under R02."""
    return _expect(replace(VALID, base=replace(VALID.base, note="")), "R02")


def test_r03() -> list[str]:
    broken = list(VALID.hops)
    broken[1] = replace(broken[1], hop_index=7)
    return _expect(replace(VALID, hops=tuple(broken)), "R03")


def test_r03_owner_direction() -> list[str]:
    """An IN hop with an OUT owner is not «an unknown owner» — both names are
    in the vocabulary, and only the pairing is wrong."""
    broken = list(VALID.hops)
    broken[0] = replace(broken[0], owner="answer")
    return _expect(replace(VALID, hops=tuple(broken)), "R03")


def test_r04() -> list[str]:
    broken = list(VALID.hops)
    broken[4] = replace(broken[4], item_id="i-nobody")
    return _expect(replace(VALID, hops=tuple(broken)), "R04")


def test_r04_turn() -> list[str]:
    """Turn 0 is the system prompt, which no hop may open."""
    broken = list(VALID.hops)
    broken[4] = replace(broken[4], turn=0)
    return _expect(replace(VALID, hops=tuple(broken)), "R04")


def test_r05() -> list[str]:
    """An IN/tool hop carrying a value the CUSTOMER said, not the backend."""
    said = VALID.hops[0].item_id
    broken = list(VALID.hops)
    broken[2] = replace(broken[2], item_id=said)
    return _expect(replace(VALID, hops=tuple(broken)), "R05")


def test_r05_undeclared_return() -> list[str]:
    return _expect(replace(VALID, returns=()), "R05")


def test_r06() -> list[str]:
    broken = list(VALID.hops)
    broken[3] = replace(broken[3], source_hop=3)
    return _expect(replace(VALID, hops=tuple(broken)), "R06")


def test_r07() -> list[str]:
    return _expect(replace(VALID, has_result=False), "R07")


def test_r07_min_hops() -> list[str]:
    """R07's SECOND half: a case that reaches a result carries the whole minimal
    loop, not a corner of it.

    C-004: `MIN_HOPS_WITH_RESULT` appeared at schema.py:176 and in an assertion
    ABOUT the fixture, and in no negative anywhere — so the clause «a case with
    has_result carries at least MIN_HOPS_WITH_RESULT hops» had never been shown
    to fire. Dropping the OUT/tool_arg leg leaves a case that still has an
    IN/tool and an OUT/answer hop, so `has_result` stays true and only the count
    can catch it.
    """
    dropped = {hop.hop_index for hop in VALID.hops
               if hop.kind == "OUT" and hop.owner == "tool_arg"}
    spare = [hop.hop_index for hop in VALID.hops
             if hop.kind == "OUT" and hop.owner == "answer"]
    dropped.add(spare[-1])                      # one answer hop is still an answer
    kept = [hop for hop in VALID.hops if hop.hop_index not in dropped]
    if len(kept) >= c.MIN_HOPS_WITH_RESULT:
        return [f"the fixture still has {len(kept)} hops without its argument leg; "
                f"the negative cannot fire"]
    renumbered = tuple(replace(hop, hop_index=index, source_hop=-1)
                       for index, hop in enumerate(kept))
    short = replace(VALID, hops=renumbered)
    if not s.has_result(renumbered):
        return ["dropping the argument leg also dropped the result; R07's first half "
                "would fire instead of its second"]
    return _expect(short, "R07")


def test_r08() -> list[str]:
    broken = list(VALID.hops)
    broken[1] = replace(broken[1], tool_name="tool_nobody_offers")
    return _expect(replace(VALID, hops=tuple(broken)), "R08")


def test_r08_ordinal() -> list[str]:
    """A hop with no tool cannot have an ordinal inside a call that never was."""
    broken = list(VALID.hops)
    broken[0] = replace(broken[0], call_ordinal=0)
    return _expect(replace(VALID, hops=tuple(broken)), "R08")


def test_r09() -> list[str]:
    broken = list(VALID.hops)
    broken[1] = replace(broken[1], parallel_group="g1")
    return _expect(replace(VALID, hops=tuple(broken)), "R09")


def test_r10() -> list[str]:
    forced = ForcedError("crm_find_contact", 0, "phone_not_e164", VALID.hops[0].item_id,
                         "поле phone «{value}» должно быть в формате E.164")
    return _expect(replace(VALID, forced=(forced,)), "R10")


def test_r10_two_slots() -> list[str]:
    """`retry_same_tool` with a template that echoes the value twice: the mock
    would write it twice and the echo hop would count once."""
    forced = ForcedError("crm_find_contact", 0, "phone_not_e164", VALID.hops[0].item_id,
                         "поле phone «{value}» неверно: {value}")
    case = replace(VALID, behaviour="retry_same_tool", forced=(forced,))
    problems = s.validate_v5(case)
    if _ids(problems) != {"R10"} or not any("value slots" in one for one in problems):
        return [f"R10 two-slot template: {sorted(_ids(problems))} / {problems[:4]}"]
    return []


def test_r11() -> list[str]:
    return _expect(replace(VALID, behaviour="same_tool_other_target"), "R11")


def test_r12() -> list[str]:
    return _expect(replace(VALID, behaviour="sequential_chain"), "R12")


def test_r13() -> list[str]:
    missing = _expect(replace(VALID, behaviour="fanout_pick"), "R13")
    lonely = PickSpec("crm_find_contact", ("p1",), "p1", "notify_sms")
    body = _expect(replace(VALID, behaviour="fanout_pick", pick=lonely), "R13")
    return missing + body


def test_r14() -> list[str]:
    missing = _expect(replace(VALID, behaviour="branching"), "R14")
    same = BranchSpec("crm_find_contact", True, "notify_sms", "notify_sms")
    body = _expect(replace(VALID, behaviour="branching", branch=same), "R14")
    return missing + body


def test_r15() -> list[str]:
    missing = _expect(replace(VALID, behaviour="user_in_loop"), "R15")
    said = [item for item in VALID.base.pii if item.where.kind == "message"][0]
    with_value = LoopSpec("crm_find_contact", 1, 2, f"да, это {said.value}", "notify_sms")
    body = _expect(replace(VALID, behaviour="user_in_loop", loop=with_value), "R15")
    return missing + body


def _loop_case(act_owner: str, act_tool: str, act_path: str) -> CaseV5:
    """`VALID` with a second user turn and an acting hop in it, so «show →
    confirm → act» has the two turns the rule reads."""
    confirm = "да, это я"
    messages = VALID.base.messages + (
        Message(role="user", content=confirm, source=None, name=""),)
    # v4's `validate` wants every message covered by trace rows with no gap —
    # the confirmation carries no value, so one `said` row spans the whole of it.
    trace = VALID.base.trace + (TraceRow(msg=2, key="said", start=0, end=len(confirm),
                                         origin="authored"),)
    base = replace(VALID.base, messages=messages, trace=trace,
                   tools=VALID.base.tools + (act_tool,),
                   expects=replace(VALID.base.expects,
                                   reachable_tools=VALID.base.expects.reachable_tools + (act_tool,)))
    carried = VALID.hops[2]            # the IN/tool hop the act carries forward
    act = Hop(kind="OUT", owner=act_owner, item_id=carried.item_id, hop_index=len(VALID.hops),
              turn=2, tool_name=act_tool, call_ordinal=0, parallel_group="",
              source_hop=carried.hop_index, path=act_path, optional=False)
    return replace(VALID, base=base, behaviour="user_in_loop", hops=VALID.hops + (act,),
                   loop=LoopSpec("crm_find_contact", 1, 2, confirm, act_tool))


def test_r15_summary_acts() -> list[str]:
    """Ruling R-31: a handover acts through a SUMMARY leaf, and the old rule —
    «an OUT/tool_arg hop at or after confirm_turn» — refused it. Both atoms
    here: the summary act is accepted, and a loop that acts through nothing at
    all is still refused, so the widening did not empty the rule."""
    acted = _loop_case("summary", "escalate_to_human", "summary")
    problems = s.validate_v5(acted)
    failures = ([f"a loop that acts through a summary leaf was refused: {problems[:4]}"]
                if problems else [])
    idle = replace(acted, hops=acted.hops[:-1])
    failures += _expect(idle, "R15")
    return failures


def test_acting_owners_come_from_contracts() -> list[str]:
    """F4.13: R15's «the agent acted» owners are `contracts.ACTING_OUT_OWNERS`
    itself, not a copy of it.

    WHY IDENTITY AND NOT EQUALITY. `metrics._transitions` decides what a chain
    is by the same tuple, and a local copy here would be equal on the day it was
    written and one edit away from the corpus and the metric disagreeing about
    which OUT hops are acts. Equality would pass over exactly that drift until
    somebody changed one of the two.
    """
    problems: list[str] = []
    if s.ACTING_OUT_OWNERS is not c.ACTING_OUT_OWNERS:
        problems.append(f"schema restates the acting owners ({s.ACTING_OUT_OWNERS}) instead "
                        f"of importing them from contracts ({c.ACTING_OUT_OWNERS})")
    # THE NEGATIVE: a copy with the same contents, which equality would accept
    # and this check must not. Built through a list because `tuple(x)` hands
    # back `x` itself for a tuple — the copy has to be a real one for the
    # demonstration to mean anything.
    copy = tuple(list(c.ACTING_OUT_OWNERS))
    if copy != c.ACTING_OUT_OWNERS or copy is c.ACTING_OUT_OWNERS:
        problems.append("an equal copy of the owners could not be built, so this check "
                        "was never shown telling a copy from the original")
    return problems


def test_r16() -> list[str]:
    missing = _expect(replace(VALID, behaviour="memory_anaphora"), "R16")
    said = VALID.hops[0].item_id
    # The «recall» turn is the turn the value was written in — both halves of
    # R16 fire: the order and the re-writing.
    rewritten = MemorySpec(said, VALID.hops[0].turn, VALID.hops[0].turn, "pronoun")
    case = replace(VALID, memory=(rewritten,))
    problems = s.validate_v5(case)
    body: list[str] = []
    if _ids(problems) != {"R16"} or not any("again" in one for one in problems):
        body = [f"R16 re-written recall: {sorted(_ids(problems))} / {problems[:4]}"]
    return missing + body


def test_r17() -> list[str]:
    missing = _expect(replace(VALID, behaviour="rag"), "R17")
    own = RagSpec("kb_search", 1, ("c1",), (), ())
    body = _expect(replace(VALID, behaviour="rag", rag=own), "R17")
    return missing + body


def _seed_item() -> PiiItem:
    return [item for item in VALID.base.pii if item.where.kind == "seed"][0]


def _document_case(document: DocumentSpec) -> CaseV5:
    """`VALID` with a second seed record, so «the records this document
    renders» is a choice rather than the only record there is — and an OUT hop
    into `extract_to_tool` for every extracted item, which H4.1's rule demands
    and which a well-formed document family writes anyway."""
    other = SeedRecord(id="other", table="documents", fields={"path": "/upload/x.csv"},
                       pii_ids=())
    base = replace(VALID.base, seed_records=VALID.base.seed_records + (other,))
    hops = list(VALID.hops)
    for item_id in document.extracted_item_ids:
        hops.append(Hop("OUT", "template", item_id, len(hops), VALID.hops[0].turn,
                        document.extract_to_tool, 0, "", -1, "text", False))
    return replace(VALID, base=base, behaviour="document", document=document,
                   hops=tuple(hops))


def test_r18() -> list[str]:
    missing = _expect(replace(VALID, behaviour="document"), "R18")
    item = _seed_item()
    one_row = DocumentSpec("d1", "crm_find_contact", "csv", 1, (item.where.record,),
                           "notify_sms", (item.id,))
    body = _expect(replace(VALID, behaviour="document", document=one_row), "R18")
    return missing + body


def test_r18_records_are_seed_records() -> list[str]:
    """The positive atom first, then the two ways `record_ids` can be wrong
    (ruling R-30). Without the positive one, «R18 fires» would also be true of
    a rule that refused every document ever written."""
    item = _seed_item()
    good = DocumentSpec("d1", "crm_find_contact", "free_text", 1, (item.where.record,),
                        "notify_sms", (item.id,))
    problems = s.validate_v5(_document_case(good))
    failures = ([f"a well-formed document was refused: {problems[:4]}"] if problems else [])
    nowhere = replace(good, record_ids=("no-such-record",))
    failures += _expect(_document_case(nowhere), "R18")
    empty = replace(good, record_ids=())
    failures += _expect(_document_case(empty), "R18")
    return failures


def test_r18_extracted_items_belong_to_those_records() -> list[str]:
    """The weak check R-30 replaced — «a seed item» — passed this case: the
    document claims to extract a value that lives in the caller's own CRM card,
    a record the file does not render, and every OUT hop on it would have been
    charged to the gateway as a document extraction nobody made."""
    item = _seed_item()
    stranger = DocumentSpec("d1", "crm_find_contact", "free_text", 1, ("other",),
                            "notify_sms", (item.id,))
    return _expect(_document_case(stranger), "R18")


def test_r18_extracted_item_has_somewhere_to_go() -> list[str]:
    """H4.1: `doc_extracted` counts one OUT hop into `extract_to_tool` per
    extracted item, so an item the case gives the agent no field for sits in
    the denominator for ever — 50 of 375 did, and the line's ceiling was 86.7%
    with nothing wrong with the gateway. The positive atom first: the same
    document WITH the hop is quiet, so the rule is not «R18 refuses every
    document»."""
    item = _seed_item()
    good = DocumentSpec("d1", "crm_find_contact", "free_text", 1, (item.where.record,),
                        "notify_sms", (item.id,))
    failures = ([f"a document whose extraction has a hop was refused: {problems[:4]}"]
                if (problems := s.validate_v5(_document_case(good))) else [])
    nowhere = replace(_document_case(good), hops=VALID.hops)
    failures += _expect(nowhere, "R18")
    # The hop exists but writes into ANOTHER tool: `doc_extracted` reads
    # `tool_name == extract_to_tool` and would not see it either.
    elsewhere = list(VALID.hops) + [Hop("OUT", "tool_arg", item.id, len(VALID.hops),
                                        VALID.hops[0].turn, "crm_find_contact", 0, "", -1,
                                        "query.last_name", False)]
    failures += _expect(replace(_document_case(good), hops=tuple(elsewhere)), "R18")
    return failures


def test_r19() -> list[str]:
    broken = replace(VALID.returns[0], return_form="какая-то")
    return _expect(replace(VALID, returns=(broken,)), "R19")


def test_r19_reads_the_registry_when_it_exists() -> list[str]:
    """R19's strong half is «a form THIS tool declares». While the tools
    component is unwritten `_declared_return_forms` is None and the weak half
    runs; the moment `REGISTRY_V5` imports, a form outside the tool's own list
    must be refused. The test asserts whichever half is live, so it goes red
    when tools lands and R19 was left weak."""
    declared = s._declared_return_forms()
    if declared is None:
        return []
    forms = declared.get("crm_find_contact")
    if forms is None:
        return ["REGISTRY_V5 exists but has no crm_find_contact"]
    outside = [form for form in c.RETURN_FORMS if form not in forms]
    if not outside:
        return ["crm_find_contact declares every return form; pick another tool here"]
    broken = replace(VALID.returns[0], return_form=outside[0])
    return _expect(replace(VALID, returns=(broken,)), "R19")


def test_r20() -> list[str]:
    return _expect(replace(VALID, streaming=True), "R20")


def test_r21() -> list[str]:
    """A `notify_sms.text` leaf is a TEMPLATE hop; declaring it as an ordinary
    argument moves it into the wrong `form_hOUT` line."""
    broken = list(VALID.hops)
    broken[1] = replace(broken[1], tool_name="notify_sms", path="text")
    return _expect(replace(VALID, hops=tuple(broken)), "R21")


def test_r21_the_other_way() -> list[str]:
    """…and an ordinary leaf declared as a template hop is the same mistake."""
    broken = list(VALID.hops)
    broken[1] = replace(broken[1], owner="template")
    return _expect(replace(VALID, hops=tuple(broken)), "R21")


def _address_case() -> tuple[CaseV5, str]:
    """One `single` case whose customer states an address and the acting call is
    `courier_book`; the address item id rides back for the R22 mutation."""
    ctx = common.ctx_for("single", 5, 0, "chat")
    drawn = common.draw(ctx, city="Самара", with_flat=True, with_entrance=False,
                        with_type=True, foreign=False)
    builder = common.new_builder(
        ctx, "delivery", tools=("courier_book", "crm_upsert_contact"),
        reachable=("courier_book",), primary_identity="p1",
        cluster="LOC:fixture", note="фикстура R22", extras=(common.MEMORY_CLAUSE,))
    draft = builder.draft()
    draft.say("курьера на адрес ")
    draft.value("a", common.address(ctx, drawn.address))
    turn = builder.user(draft, {"a": ("LOC", "p1.home", "required", False)})
    said = [item for item in builder.v4.pii if item.where.kind == "message"][0]
    builder.declare_hop(Hop("IN", "user", said.id, 0, turn, "", -1, "", -1, "", False))
    builder.declare_hop(Hop("OUT", "tool_arg", said.id, 1, turn, "courier_book", 0, "",
                            0, "address.street", False))
    return builder.build("single"), said.id


def _correction_case() -> tuple[CaseV5, str]:
    """One `single` case whose customer states an address and then corrects it:
    two message LOC items of one identity in one message, the first cancelled by
    the second — `_superseded_ids`'s shape. Both items are `stale=False` so v4's
    own validator does not refuse «a stale item outside a correction case»; the
    supersession R23 reads is the STRUCTURAL fact, not the author's flag."""
    ctx = common.ctx_for("single", 5, 0, "chat")
    drawn = common.draw(ctx, city="Самара", with_flat=True, with_entrance=False,
                        with_type=True, foreign=False)
    wrong = replace(drawn.address, house=drawn.address.house + 27)
    builder = common.new_builder(ctx, "delivery", tools=("courier_book",),
                                 reachable=("courier_book",), primary_identity="p1",
                                 cluster="LOC:fixture", note="фикстура R23",
                                 extras=(common.MEMORY_CLAUSE,))
    draft = builder.draft()
    draft.say("курьера на адрес ")
    draft.value("a_old", common.address(ctx, wrong))
    draft.say(" ой нет ")
    draft.value("a_new", common.address(ctx, drawn.address))
    turn = builder.user(draft, {"a_old": ("LOC", "p1.addr", "required", False),
                                "a_new": ("LOC", "p1.addr", "required", False)})
    message_items = [item for item in builder.v4.pii if item.where.kind == "message"]
    cancelled = message_items[0].id
    current = message_items[1].id
    builder.declare_hop(Hop("IN", "user", cancelled, 0, turn, "", -1, "", -1, "", False))
    builder.declare_hop(Hop("IN", "user", current, 1, turn, "", -1, "", -1, "", False))
    builder.declare_hop(Hop("OUT", "tool_arg", current, 2, turn, "courier_book", 0, "",
                            1, "address.street", False))
    return builder.build("single"), cancelled


def test_r22() -> list[str]:
    """Two DIFFERENT leaves of one semantic class on one (turn, item) — the
    corpus's own builders keep only the canonical one (`revise._arguments`), so
    the validator must refuse the case that names both (SPIKE-Е, Е-6)."""
    case, item = _address_case()
    if s.validate_v5(case):
        return ["the address fixture itself is not quiet:\n    "
                + "\n    ".join(s.validate_v5(case)[:5])]
    hops = list(case.hops)
    hops.append(Hop("OUT", "tool_arg", item, 2, hops[1].turn, "crm_upsert_contact", 0, "",
                    hops[1].source_hop, "contact.address.street", False))
    return _expect(replace(case, hops=tuple(hops)), "R22")


def test_r23() -> list[str]:
    """A REQUIRED OUT hop on a message item a later word of the customer
    cancelled: the correct agent writes the corrected value, so the hop on the
    cancelled one can never become `observed` (SPIKE-Е, Е-4)."""
    case, cancelled = _correction_case()
    if s._superseded_ids(case.base) != {cancelled}:
        return [f"the fixture supersedes {s._superseded_ids(case.base)}, want {{{cancelled}}}"]
    if s.validate_v5(case):
        return ["the correction fixture itself is not quiet:\n    "
                + "\n    ".join(s.validate_v5(case)[:5])]
    hops = list(case.hops)
    hops[2] = replace(hops[2], item_id=cancelled)
    return _expect(replace(case, hops=tuple(hops)), "R23")


# --- the synthetic corpus -------------------------------------------------------

def _fake_item(item_id: str, kind: str, identity: str, seeded: bool) -> PiiItem:
    where = (Locus("seed", -1, 0, 0, "r1", item_id) if seeded
             else Locus("message", 1, 0, 1, "", ""))
    return PiiItem(id=item_id, type=kind, identity=identity, value=item_id,
                   canonical=item_id, parts={"x": "y"}, where=where,
                   duty="required", spoken=False, stale=False)


def _fake_base(index: int, register: str, users: int) -> Case:
    """A v4 `Case` shaped only for the CORPUS rules.

    It is not built by the generator and would not survive `v4.validate` — and
    it must not be: the corpus rules read counts, shares and ids, and building
    1600 real cases in a unit test would make the test a corpus build.
    """
    items: list[PiiItem] = [
        _fake_item(f"n{index}a", "NAME", "A", False), _fake_item(f"n{index}b", "NAME", "A", True),
        _fake_item(f"l{index}a", "LOC", "A.home", False), _fake_item(f"l{index}b", "LOC", "A.home", True),
        _fake_item(f"p{index}", "PHONE", "A", True)]
    if index % 2 == 0:
        items.append(_fake_item(f"d{index}", "DOB", "A", True))
    if index % 3 == 0:
        items.append(_fake_item(f"e{index}", "EMAIL", "A", True))
    if index % 16 == 0:
        items.append(_fake_item(f"c{index}", "CARD", "A", True))
    if index % 20 == 0:
        items.append(_fake_item(f"s{index}", "SNILS", "A", True))
    if index % 20 == 1:
        items.append(_fake_item(f"t{index}", "PASSPORT", "A", True))
    if index % 20 == 2:
        items.append(_fake_item(f"i{index}", "INN", "A", True))
    if index % 20 == 3:
        items.append(_fake_item(f"g{index}", "PLATE", "A", True))
    items.append(_fake_item(f"m{index}", "NAME", "B", False))
    messages = [Message(role="system", content="s", source=None, name="")]
    messages.extend(Message(role="user", content=f"u{turn}", source=None, name="")
                    for turn in range(users))
    return Case(
        id=f"syn-{index:04d}", kind="chain", register=register,
        provenance=Provenance(kind="template", corpus="authored", key="", shape="",
                              selection="authored", weight=1.0, licence="authored"),
        cluster=f"PHONE:{index % 120}", conversation_id=f"conv-{index}" if index % 2 == 0 else "",
        now=common.NOW_V5, messages=tuple(messages),
        tools=("crm_find_contact", "notify_sms"), seed_records=(), pii=tuple(items), plain=(),
        negatives=(), expects=Expectation(reachable_tools=("crm_find_contact", "notify_sms"),
                                          primary_identity="A", must_contain=(),
                                          must_not_contain=(), validate_types=()),
        trace=(), note="synthetic")


def _fake_hops(index: int, behaviour: str, family_index: int, with_result: bool) -> tuple[Hop, ...]:
    """Owner coverage K13 asks for: the four of the minimal loop everywhere,
    and each rarer owner in two behaviours so the «≥ 2 behaviours» half of the
    rule has something to count."""
    hops: list[Hop] = [
        Hop("IN", "user", f"n{index}a", 0, 1, "", -1, "", -1, "", False),
        Hop("OUT", "tool_arg", f"n{index}a", 1, 1, "crm_find_contact", 0, "", 0, "query.last_name", False)]
    if with_result:
        hops.append(Hop("IN", "tool", f"n{index}b", 2, 1, "crm_find_contact", 0, "", -1,
                        "contacts[].last_name", False))
        hops.append(Hop("OUT", "answer", f"n{index}b", 3, 1, "", -1, "", 2, "", True))
    extra = len(hops)
    if behaviour == "document" or (behaviour == "rag" and family_index < 6):
        hops.append(Hop("IN", "document", f"l{index}b", extra, 1, "crm_find_contact", 0, "",
                        -1, "rows[].street", False))
        extra += 1
    if behaviour == "memory_anaphora" or (behaviour == "user_in_loop" and family_index < 6):
        hops.append(Hop("IN", "memory", f"n{index}a", extra, 1, "", -1, "", -1, "", False))
        extra += 1
    if (behaviour == "single" or behaviour == "parallel") and family_index < 6:
        hops.append(Hop("OUT", "template", f"n{index}a", extra, 1, "notify_sms", 0, "", 0,
                        "text", False))
        extra += 1
    if (behaviour == "sequential_chain" or behaviour == "branching") and family_index < 6:
        hops.append(Hop("OUT", "summary", f"n{index}a", extra, 1, "crm_add_note", 0, "", 0,
                        "text", False))
    return tuple(hops)


def _synthetic_corpus() -> list[CaseV5]:
    """A corpus that satisfies K01–K15 with nothing to report."""
    plan: list[tuple[str, int]] = [
        (behaviour, round(SYNTHETIC_SIZE * c.BEHAVIOUR_SHARES[behaviour]))
        for behaviour in c.BEHAVIOURS]
    if sum(count for _behaviour, count in plan) != SYNTHETIC_SIZE:
        raise BuildError(f"the synthetic plan adds to "
                         f"{sum(count for _b, count in plan)}, not {SYNTHETIC_SIZE}")
    cases: list[CaseV5] = []
    index = 0
    for behaviour, count in plan:
        for family_index in range(count):
            revised = index < c.V4_CORPUS_SIZE
            # K10: of the 834 revised, exactly 455 reached a tool result — the
            # rest of the corpus always does, which keeps K03 above 75%.
            with_result = (index < c.V4_CASES_WITH_RESULT) if revised else True
            users = 5 if behaviour == "memory_anaphora" and family_index < 10 else 1
            base = _fake_base(index, SYNTHETIC_REGISTERS[index % len(SYNTHETIC_REGISTERS)], users)
            hops = _fake_hops(index, behaviour, family_index, with_result)
            memory: tuple[MemorySpec, ...] = ()
            if behaviour == "memory_anaphora":
                kinds = tuple(kind for kind in c.ANAPHORA_KINDS if kind != "none")
                anaphora = kinds[family_index % len(kinds)]
                if family_index < 10:
                    memory = (MemorySpec(f"n{index}a", 1, 3, anaphora),
                              MemorySpec(f"l{index}a", 1, 4, anaphora),
                              MemorySpec(f"m{index}", 2, 5, anaphora))
                else:
                    memory = (MemorySpec(f"n{index}a", 1, 1, anaphora),)
            document = None
            if behaviour == "document":
                fmt = c.DOCUMENT_FORMATS[family_index % len(c.DOCUMENT_FORMATS)]
                document = DocumentSpec(f"d{index}", "crm_find_contact", fmt,
                                        2 if fmt == "csv" else 1, (f"d{index}",),
                                        "notify_sms", (f"n{index}b",))
            returns: tuple[ReturnExpectation, ...] = ()
            if with_result:
                # K15: two items of ONE identity in one call.
                returns = (ReturnExpectation("crm_find_contact", 0, "list",
                                             (f"n{index}b", f"p{index}")),)
            cases.append(CaseV5(
                base=base, behaviour=behaviour, hops=hops, returns=returns, forced=(),
                memory=memory, pick=None, branch=None, loop=None, rag=None, document=document,
                has_result=with_result,
                streaming=index % len(SYNTHETIC_REGISTERS) == 0,
                revised_from_v4=revised, v6=None))
            index += 1
    return cases


CORPUS: list[CaseV5] = _synthetic_corpus()
REGISTRY_NAMES: tuple[str, ...] = ("crm_find_contact", "notify_sms")


def _corpus_ids(cases: list[CaseV5]) -> set[str]:
    return _ids(s.validate_corpus_v5(cases, REGISTRY_NAMES))


def _corpus_expect(cases: list[CaseV5], rule: str) -> list[str]:
    seen = _corpus_ids(cases)
    if seen != {rule}:
        problems = s.validate_corpus_v5(cases, REGISTRY_NAMES)
        return [f"{rule}: report names {sorted(seen) or 'nothing'}\n    "
                + "\n    ".join(problems[:6])]
    return []


def test_synthetic_corpus_is_quiet() -> list[str]:
    """The positive atom for K01–K15: a corpus that satisfies every rule, so a
    rule that stopped working has nothing to hide behind."""
    problems = s.validate_corpus_v5(CORPUS, REGISTRY_NAMES)
    if problems:
        return ["the synthetic corpus should satisfy every corpus rule:\n    "
                + "\n    ".join(problems[:10])]
    return []


def test_k01() -> list[str]:
    """Two halves. The BAND cannot be broken in isolation — a corpus of 200 is
    under every floor there is — so it is asserted by its own message; the
    duplicate id is checked as «exactly K01» on a corpus that is otherwise
    whole, and the case duplicated is one v5 wrote, so K10 keeps its count."""
    problems: list[str] = []
    small = s.validate_corpus_v5(CORPUS[:200], REGISTRY_NAMES)
    if not any(one.startswith("K01") and "band" in one for one in small):
        problems.append(f"K01 said nothing about a corpus of 200: {small[:3]}")
    fresh = next(case for case in CORPUS if not case.revised_from_v4 and case.has_result)
    problems.extend(_corpus_expect(CORPUS + [fresh], "K01"))
    return problems


def test_k02_floor_not_ceiling() -> list[str]:
    """A family ABOVE its share is not a problem — `single` and
    `sequential_chain` overshoot by design because the revised v4 corpus
    supplies them. A family BELOW its floor is."""
    over = list(CORPUS)
    moved = 0
    for position, case in enumerate(over):
        if case.behaviour == "retry_same_tool" and moved < 40:
            over[position] = replace(case, behaviour="single")
            moved += 1
    problems: list[str] = []
    if _corpus_ids(over):
        problems.append(f"K02 fired on a family over its share: "
                        f"{s.validate_corpus_v5(over, REGISTRY_NAMES)[:4]}")
    under = list(CORPUS)
    moved = 0
    for position, case in enumerate(under):
        if case.behaviour == "retry_same_tool" and moved < 50:
            under[position] = replace(case, behaviour="single")
            moved += 1
    problems.extend(_corpus_expect(under, "K02"))
    return problems


def test_k03() -> list[str]:
    """Below 75% with a tool result. The cases flipped are the ones v5 wrote,
    not the revised v4 ones, so K10's own count stays right."""
    broken = list(CORPUS)
    flipped = 0
    for position, case in enumerate(broken):
        if not case.revised_from_v4 and case.has_result and flipped < 120:
            broken[position] = replace(case, has_result=False)
            flipped += 1
    return _corpus_expect(broken, "K03")


def test_k04() -> list[str]:
    """K04 is a claim about the v5-AUTHORED cases only (ruling R-09), and this
    test proves BOTH halves of that: turning every voice case of the authored
    block into `chat` fires it, and doing the same to the REVISED block — whose
    registers v4 froze and no v5 decision can move — must not."""
    problems: list[str] = []
    authored_broken = [replace(case, base=replace(case.base, register="chat"))
                       if not case.revised_from_v4 and position % 20 < 9 else case
                       for position, case in enumerate(CORPUS)]
    problems.extend(_corpus_expect(authored_broken, "K04"))
    revised_broken = [replace(case, base=replace(case.base, register="chat"))
                      if case.revised_from_v4 else case for case in CORPUS]
    if "K04" in _corpus_ids(revised_broken):
        problems.append("K04 fired on the revised block, which v4 froze")
    return problems


def test_k05() -> list[str]:
    """INN is carried by no case. K06 stays quiet because v4 carried none either
    — the two rules answer different questions and must not fire together."""
    broken = [replace(case, base=replace(
        case.base, pii=tuple(item for item in case.base.pii if item.type != "INN")))
        for case in CORPUS]
    return _corpus_expect(broken, "K05")


def test_k06() -> list[str]:
    """DOB and not PHONE: the synthetic returns name the phone item, and
    deleting it would take K15 down with K06 — two rules failing together is
    two rules neither of which was tested."""
    broken = [replace(case, base=replace(
        case.base, pii=tuple(item for item in case.base.pii if item.type != "DOB")))
        for case in CORPUS]
    return _corpus_expect(broken, "K06")


def test_k07() -> list[str]:
    """`notify_sms` is offered by every case and reachable in none."""
    broken = [replace(case, base=replace(case.base, expects=replace(
        case.base.expects, reachable_tools=("crm_find_contact",))))
        for case in CORPUS]
    return _corpus_expect(broken, "K07")


def test_k08() -> list[str]:
    broken = [replace(case, base=replace(case.base, cluster=f"PHONE:{position}"))
              for position, case in enumerate(CORPUS)]
    return _corpus_expect(broken, "K08")


def test_k09() -> list[str]:
    broken = [replace(case, base=replace(case.base, conversation_id="")) for case in CORPUS]
    return _corpus_expect(broken, "K09")


def test_k10() -> list[str]:
    """One case of the 834 that stops claiming to be one."""
    broken = list(CORPUS)
    for position, case in enumerate(broken):
        if case.revised_from_v4 and not case.has_result:
            broken[position] = replace(case, revised_from_v4=False)
            break
    return _corpus_expect(broken, "K10")


def test_k11() -> list[str]:
    broken = list(CORPUS)
    dropped = 0
    for position, case in enumerate(broken):
        if case.streaming and dropped < 30:
            broken[position] = replace(case, streaming=False)
            dropped += 1
    return _corpus_expect(broken, "K11")


def test_k13() -> list[str]:
    """No case declares a `template` hop any more."""
    broken = [replace(case, hops=tuple(hop for hop in case.hops if hop.owner != "template"))
              for case in CORPUS]
    return _corpus_expect(broken, "K13")


def test_k13_one_behaviour() -> list[str]:
    """`summary` survives in enough cases but only inside ONE behaviour — the
    half of K13 a plain count would miss."""
    broken = [replace(case, hops=tuple(hop for hop in case.hops if hop.owner != "summary"))
              if case.behaviour == "branching" else case
              for case in CORPUS]
    problems = s.validate_corpus_v5(broken, REGISTRY_NAMES)
    if _ids(problems) != {"K13"} or not any("behaviours" in one for one in problems):
        return [f"K13 spread: {sorted(_ids(problems))} / {problems[:4]}"]
    return []


def test_k14() -> list[str]:
    """No `scan` document in the corpus."""
    broken = [replace(case, document=replace(case.document, format="csv", record_count=2))
              if case.document is not None and case.document.format == "scan" else case
              for case in CORPUS]
    return _corpus_expect(broken, "K14")


def test_k14_long_memory() -> list[str]:
    """Every memory case keeps its anaphora but loses the long dialogues."""
    broken = [replace(case, memory=case.memory[:1]) if len(case.memory) > 1 else case
              for case in CORPUS]
    problems = s.validate_corpus_v5(broken, REGISTRY_NAMES)
    if _ids(problems) != {"K14"} or not any("MemorySpecs" in one for one in problems):
        return [f"K14 long memory: {sorted(_ids(problems))} / {problems[:4]}"]
    return []


def test_k15() -> list[str]:
    broken = [replace(case, returns=tuple(
        replace(one, result_item_ids=one.result_item_ids[:1]) for one in case.returns))
        for case in CORPUS]
    return _corpus_expect(broken, "K15")


def test_k16() -> list[str]:
    """A vertical OFFERED and never read back — the clinic's own shape.

    The break is the defect as it actually stood: `patient_find` is put in front
    of the agent by one case and nothing in the corpus crosses an IN/tool hop of
    the clinic. Before K16 that corpus passed every rule, and a vertical whose
    return notation is checked by nothing looked covered because its OUT hops
    counted — 584 of them.
    """
    broken = list(CORPUS)
    first = broken[0]
    broken[0] = replace(first, base=replace(
        first.base, tools=(*first.base.tools, "patient_find")))
    return _corpus_expect(broken, "K16")


def test_k16_is_silent_on_a_writing_vertical() -> list[str]:
    """The other side, and the reason the rule names the exemption out loud: a
    vertical whose tools all WRITE owes no reading. `notify_sms` is offered by
    every synthetic case and the messaging row of §2 asks for an OUT/template
    hop, not an IN/tool one — a rule that demanded one there would be demanding a
    result the real services do not return."""
    if "K16" in _corpus_ids(CORPUS):
        return [f"K16 fired on a corpus whose only other vertical writes: "
                f"{[one for one in s.validate_corpus_v5(CORPUS, REGISTRY_NAMES) if one.startswith('K16')]}"]
    return []


def test_k17() -> list[str]:
    """An IN/tool hop on a leaf the registry does not declare.

    THE HALF THAT MAKES A DELETION HURT. V06 keeps a declaration reachable; this
    keeps it necessary — remove `contacts[].last_name` from `crm_find_contact`'s
    `result_pii` and the corpus that crosses it goes red. Five declared paths
    lived through a whole release because neither half existed.
    """
    broken = list(CORPUS)
    first = broken[0]
    hops = tuple(replace(hop, path="contacts[].nickname")
                 if hop.kind == "IN" and hop.owner == "tool" else hop
                 for hop in first.hops)
    broken[0] = replace(first, hops=hops)
    return _corpus_expect(broken, "K17")


def test_k17_erases_the_array_index() -> list[str]:
    """A hop that crossed the SECOND row of a list is the same leaf as the
    first. Without the erasure every list result in the corpus would be a K17
    violation, and a rule that is red on everything is read by nobody."""
    broken = list(CORPUS)
    first = broken[0]
    hops = tuple(replace(hop, path="contacts[3].last_name")
                 if hop.kind == "IN" and hop.owner == "tool" else hop
                 for hop in first.hops)
    broken[0] = replace(first, hops=hops)
    if "K17" in _corpus_ids(broken):
        return ["K17 fired on an indexed occurrence of a declared leaf"]
    return []


# --- serialisation ---------------------------------------------------------------

def test_json_round_trip() -> list[str]:
    raw = s.case_v5_to_json(VALID)
    back = s.case_v5_from_json(json.loads(json.dumps(raw, ensure_ascii=False)))
    if back != VALID:
        return [f"round trip changed the case: {back.base.id} vs {VALID.base.id}"]
    if s.corpus_digest_v5([VALID]) != s.corpus_digest_v5([back]):
        return ["round trip changed the digest"]
    if s.corpus_digest_v5([VALID]) == s.corpus_digest_v5([replace(VALID, streaming=True)]):
        return ["the digest ignores a v5 field"]
    return []


def test_has_result() -> list[str]:
    problems: list[str] = []
    if not s.has_result(VALID.hops):
        problems.append("the minimal loop is not a result")
    if s.has_result(VALID.hops[:2]):
        problems.append("two hops are not a result")
    if s.has_result(tuple(hop for hop in VALID.hops if hop.owner != "answer")):
        problems.append("a loop with no answer is not a result")
    return problems


# --- common.py ---------------------------------------------------------------------

def test_registers_v5_mix() -> list[str]:
    """`clean` must not round to zero in a small family, and the shares must be
    the spec's in a large one."""
    problems: list[str] = []
    rng = random.Random("registers")
    tiny = common.registers_for(5, rng)
    if set(tiny) != set(c.REGISTERS):
        problems.append(f"a family of five lost a register: {sorted(set(tiny))}")
    large = common.registers_for(100, rng)
    counts = {register: large.count(register) for register in c.REGISTERS}
    for register, share in common.REGISTER_MIX_V5:
        want = share * 100
        if abs(counts[register] - want) > 1:
            problems.append(f"register {register}: {counts[register]} of 100, want {want}")
    try:
        common.registers_for(0, rng)
        problems.append("a family of zero cases was given registers")
    except BuildError:
        pass
    return problems


def test_plate() -> list[str]:
    problems: list[str] = []
    canonical = "А123ВС77"
    for register in c.REGISTERS:
        ctx = common.ctx_for("plate", 1, 0, register)
        rendered = common.plate(ctx, canonical)
        if rendered.canonical != canonical:
            problems.append(f"{register}: canonical {rendered.canonical!r}")
        if rendered.parts != {"series": "А", "digits": "123", "letters": "ВС", "region": "77"}:
            problems.append(f"{register}: parts {rendered.parts}")
        if rendered.spoken != (register == "voice_raw"):
            problems.append(f"{register}: spoken flag {rendered.spoken}")
        if rendered.spoken and any(char.isdigit() for char in rendered.surface):
            problems.append(f"{register}: a dictated plate carries a digit")
    voice = common.plate(common.ctx_for("plate", 1, 0, "voice_raw"), canonical)
    if voice.surface != "а сто двадцать три вэ эс семьдесят семь":
        problems.append(f"voice_raw surface {voice.surface!r}")
    chat = common.plate(common.ctx_for("plate", 1, 0, "chat"), canonical)
    if chat.surface != "а123вс 77":
        problems.append(f"chat surface {chat.surface!r}")
    for bad in ("А123ВС", "Z123ВС77", "А12ХВС77", "А123ВСxx"):
        try:
            common.plate(common.ctx_for("plate", 1, 0, "chat"), bad)
            problems.append(f"{bad!r} was accepted as a plate")
        except BuildError:
            pass
    return problems


def test_plate_spoken_parses() -> list[str]:
    """Every dictated plate the pool can draw decodes back to its digits.

    THE TWO NUMERAL RUNS ARE CHECKED APART, and that is not a convenience: run
    them together and «девятьсот» + «девяносто девять» is heard as 999, because
    a hundreds word absorbs the tens word after it. On the plate the two letters
    sit between them, which is what keeps «К900АН99» decodable — so the test
    asserts the word ORDER as well as the decoding, or it would be checking a
    property the surface does not actually have.

    The expectation is built from the canonical string by position, not from
    `Rendered.parts`, so a renderer that mislabels its own parts still fails.
    """
    problems: list[str] = []
    rng = random.Random("plates")
    ctx = common.ctx_for("plate", 1, 0, "voice_raw")
    for _ in range(200):
        text = common.plate_text(rng)
        series, digits, letters, region = text[0], text[1:4], text[4:6], text[6:]
        digit_words = pools.spell_groups(digits, (len(digits),))
        region_words = pools.spell_groups(region, (len(region),))
        expected = ((pools.PLATE_SPOKEN[series],) + digit_words
                    + tuple(pools.PLATE_SPOKEN[letter] for letter in letters) + region_words)
        rendered = common.plate(ctx, text)
        if tuple(rendered.surface.split()) != expected:
            problems.append(f"{text}: {rendered.surface!r} is not {' '.join(expected)!r}")
        if pools.parse_numerals(digit_words) != digits:
            problems.append(f"{text}: digits run does not decode to {digits!r}")
        if pools.parse_numerals(region_words) != region:
            problems.append(f"{text}: region run does not decode to {region!r}")
    return problems


def test_system_prompt_v5() -> list[str]:
    problems: list[str] = []
    text = common.system_prompt_v5("crm", common.NOW_V5, (common.PARALLEL_CLAUSE,
                                                          common.BRANCH_CLAUSE))
    if common.PARALLEL_CLAUSE not in text or common.BRANCH_CLAUSE not in text:
        problems.append("a clause did not reach the prompt")
    if common.NOW_V5 not in text:
        problems.append("the prompt does not fix today's date")
    for bad_role in ("support", ""):
        try:
            common.system_prompt_v5(bad_role, common.NOW_V5, ())
            problems.append(f"role {bad_role!r} was accepted")
        except BuildError:
            pass
    try:
        common.system_prompt_v5("crm", common.NOW_V5, ("",))
        problems.append("an empty clause was accepted")
    except BuildError:
        pass
    return problems


def _fresh_builder() -> common.CaseBuilderV5:
    ctx = common.ctx_for("single", 5, 1, "chat")
    return common.new_builder(ctx, "crm", tools=("crm_find_contact",),
                              reachable=("crm_find_contact",), primary_identity="p1",
                              cluster="NAME:b", note="фикстура", extras=())


def test_builder_guards() -> list[str]:
    problems: list[str] = []
    builder = _fresh_builder()
    if builder.next_hop_index() != 0:
        problems.append("a fresh builder does not start at hop 0")
    try:
        builder.declare_hop(Hop("IN", "user", "i1", 4, 1, "", -1, "", -1, "", False))
        problems.append("a hop declared out of order was accepted")
    except InvalidCase:
        pass
    builder.set_loop(LoopSpec("crm_find_contact", 1, 2, "да", "crm_find_contact"))
    try:
        builder.set_loop(LoopSpec("crm_find_contact", 1, 2, "да", "crm_find_contact"))
        problems.append("a second loop spec overwrote the first")
    except InvalidCase:
        pass
    return problems


def test_builder_refuses_an_invalid_case() -> list[str]:
    """The builder's whole promise: a case that would break a rule never
    becomes a `CaseV5`."""
    builder = _fresh_builder()
    draft = builder.draft()
    draft.say("здравствуйте найдите иванова")
    draft.value("nm", common.name(builder.ctx, common.draw(
        builder.ctx, city="Самара", with_flat=True, with_entrance=False,
        with_type=True, foreign=False).person, ("surname",), "nom", False))
    builder.user(draft, {"nm": ("NAME", "p1", "required", False)})
    said = [item for item in builder.v4.pii if item.where.kind == "message"][0]
    builder.declare_hop(Hop("IN", "user", said.id, 0, 1, "", -1, "", -1, "", False))
    try:
        builder.build("не поведение")
    except InvalidCase as error:
        return [] if "R01" in str(error) else [f"the builder raised without R01: {error}"]
    return ["the builder accepted a case with an unknown behaviour"]


def test_prose_seed() -> list[str]:
    """A prose backend row is written in the shape the mock READS: a
    `{field}` template beside the columns it names, each item keyed by the bare
    column name — that is the path `mock._template_pieces` tags by."""
    builder = _fresh_builder()
    drawn = common.draw(builder.ctx, city="Самара", with_flat=True, with_entrance=False,
                        with_type=True, foreign=False)
    who = common.name(builder.ctx, drawn.person, ("surname", "given"), "nom", False)
    tel = common.phone(builder.ctx, drawn.phone)
    ids = common.chunk_seed("k1", "Заметка по теме {topic}: клиент {who} просил "
                                   "перезвонить на {tel}.",
                            {"who": who, "tel": tel},
                            {"who": ("NAME", "p1"), "tel": ("PHONE", "p1")},
                            {"topic": "возврат"}, builder)
    problems: list[str] = []
    record = builder.v4.seeds[0]
    if record.table != "kb_chunks":
        problems.append(f"table {record.table!r}")
    if set(ids) != {"who", "tel"}:
        problems.append(f"the seed returned paths {sorted(ids)}")
    for item in builder.v4.pii:
        if item.where.kind != "seed":
            continue
        if str(record.fields.get(item.where.path, "")) != item.value:
            problems.append(f"{item.id}: column {item.where.path!r} does not hold {item.value!r}")
    # The rendered chunk is what the agent reads, and every declared item must
    # be tagged in it: an untagged value is a hop that can never be observed.
    backend = BackendV5(NOW_V5, (), {})
    backend.seed_record(record.table, record.id, dict(record.fields))
    for path, item_id in ids.items():
        backend.seed_item(record.table, record.id, path, item_id)
    log = backend.call("kb_search", {"query": drawn.person.surname[0], "k": 3})
    for item_id in ids.values():
        if item_id not in log.result_spans:
            problems.append(f"{item_id} carries no span in the rendered chunk")
    # A slot the caller forgot to type is refused, and so is a template with no
    # slot for a value the caller passed.
    for values, typed, why in (
            ({"who": who}, {}, "a slot with no declared type"),
            ({"nobody": who}, {"nobody": ("NAME", "p1")}, "a value the template never names")):
        try:
            common.chunk_seed("k2", "Клиент {who}.", values, typed, {}, builder)
            problems.append(f"{why} was accepted")
        except BuildError:
            pass
    return problems


def test_seed_surface_is_the_column() -> list[str]:
    """A seed item's WRITTEN SURFACE is what its column holds — for a nested
    CSV row as much as for a flat one — and a column holding nothing is
    refused rather than written out as «None».

    310 items shipped with the surface «None» because v4's `_seed_field` walks
    «.» alone and answers a path it cannot walk with None, which v4's own
    validator then demanded the item equal. The surface is not cosmetic: it is
    what `needles_of` indexes, so «none» became an own-stem exemption of every
    document case and matched the literal word in any reply."""
    builder = _fresh_builder()
    drawn = common.draw(builder.ctx, city="Самара", with_flat=True, with_entrance=False,
                        with_type=True, foreign=False)
    fields: dict[str, object] = {"rows": {"0": common.csv_row_fields(drawn)}}
    typed = common.csv_row_typed(0, drawn, "p1")
    ids = common.seeded(builder, "doc-1", "documents", fields, typed)
    problems: list[str] = []
    if set(ids) != set(typed):
        problems.append(f"the seed returned paths {sorted(ids)}, not {sorted(typed)}")
    for item in builder.v4.pii:
        if item.where.kind != "seed":
            continue
        want = str(common.field_at(fields, item.where.path))
        if item.value != want:
            problems.append(f"{item.id}: surface {item.value!r}, column holds {want!r}")
        if item.value.strip().lower() in common.PLACEHOLDER_SURFACES:
            problems.append(f"{item.id}: placeholder surface {item.value!r} reached the case")
    # THE NEGATIVE: a column that holds nothing is a refusal, not a surface.
    empty = _fresh_builder()
    try:
        common.seeded(empty, "doc-2", "documents", {"rows": {"0": {"last_name": ""}}},
                      {"rows.0.last_name": ("NAME", "p1", pools.Rendered(
                          "", "морозов", False, {"surname": "морозов"}))})
        problems.append("a column holding nothing was written out as a surface")
    except BuildError:
        pass
    # THE SECOND NEGATIVE: the LIST shape the rows used to have. v4's validator
    # walks «.» alone, so the surface it demands is the string «None» and the
    # one this package writes is the cell — the case cannot be built at all,
    # which is how the mapping earns its place.
    listed = _fresh_builder()
    listed_drawn = common.draw(listed.ctx, city="Самара", with_flat=True, with_entrance=False,
                               with_type=True, foreign=False)
    common.seeded(listed, "doc-3", "documents",
                  {"rows": [common.csv_row_fields(listed_drawn)]},
                  {"rows[0].last_name": common.csv_row_typed(
                      0, listed_drawn, "p1")[common.csv_row_path("0", "last_name")]})
    draft = listed.draft()
    draft.say("здравствуйте загрузите первого клиента")
    draft.value("ph", common.phone(listed.ctx, listed_drawn.phone))
    turn = listed.user(draft, {"ph": ("PHONE", "p1", "required", False)})
    said = [item for item in listed.v4.pii if item.where.kind == "message"][0]
    listed.declare_hop(Hop("IN", "user", said.id, 0, turn, "", -1, "", -1, "", False))
    try:
        listed.build("single")
        problems.append("a case whose CSV rows are a LIST was built; v4's own validator "
                        "resolves such a path to None and would demand it as the surface")
    except InvalidCase as error:
        if "R02" not in str(error) or "seed field" not in str(error):
            problems.append(f"the list shape was refused for another reason: {error}")
    return problems


def test_v4_kind_table() -> list[str]:
    """Every behaviour wears a v4 kind, and only kinds v4 knows.

    `CaseV5.base` is validated by v4 (R02), so a behaviour missing from the
    table would make `Case.kind` the behaviour's own name and every case of
    that family red. The three kinds v4 validates FURTHER are excluded: a v5
    case wearing `correction` would owe v4 a stale item it does not have.
    """
    problems: list[str] = []
    missing = [one for one in c.BEHAVIOURS if one not in common.V4_KIND_FOR_BEHAVIOUR]
    if missing:
        problems.append(f"behaviours with no v4 kind: {missing}")
    for behaviour, kind in common.V4_KIND_FOR_BEHAVIOUR.items():
        if kind not in c.V4_SCENARIO_KINDS:
            problems.append(f"{behaviour!r} wears {kind!r}, which v4 does not know")
        if kind in ("correction", "summary", "validate"):
            problems.append(f"{behaviour!r} wears {kind!r}, which v4 validates further")
    return problems


def test_clean_register_case() -> list[str]:
    """A worked example of the register v4 never generated.

    v4's own mix puts `clean` at 0.0; v5 puts it at 10%, and v3's register gate
    (reached through R02) refuses a `clean` case without a capital AND sentence
    punctuation. The recipe is `opener` at the front and `punct` at the back —
    asserted here rather than described, so a family can copy something that
    runs.
    """
    ctx = common.ctx_for("single", 9, 2, "clean")
    drawn = common.draw(ctx, city="Самара", with_flat=True, with_entrance=False,
                        with_type=True, foreign=False)
    builder = common.new_builder(
        ctx, "crm", tools=("crm_find_contact",), reachable=("crm_find_contact",),
        primary_identity="p1", cluster="NAME:clean", note="clean", extras=())
    draft = builder.draft()
    draft.say(common.opener(ctx))
    draft.say("найдите карточку по телефону")
    draft.value("ph", common.phone(ctx, drawn.phone))
    draft.punct(".")
    turn = builder.user(draft, {"ph": ("PHONE", "p1", "required", False)})
    said = [item for item in builder.v4.pii if item.where.kind == "message"][0]
    builder.declare_hop(Hop("IN", "user", said.id, 0, turn, "", -1, "", -1, "", False))
    builder.declare_hop(Hop("OUT", "tool_arg", said.id, 1, turn, "crm_find_contact", 0, "",
                            0, "query.phone", False))
    try:
        case = builder.build("single")
    except InvalidCase as error:
        return [f"a clean case written the v4 way was refused: {error}"]
    return [] if case.base.register == "clean" else ["the case lost its register"]


def test_no_pseudex() -> list[str]:
    """The instrument must be able to fail the engine, and an import is the
    first way it stops being able to."""
    loaded = sorted(name for name in sys.modules
                    if name.startswith(c.FORBIDDEN_IMPORT_PREFIX))
    return [f"importing the spine loaded {loaded}"] if loaded else []


CHECKS: tuple[object, ...] = (
    test_valid_case_is_quiet, test_r01, test_r02, test_r03, test_r03_owner_direction,
    test_r04, test_r04_turn, test_r05, test_r05_undeclared_return, test_r06, test_r07,
    test_r07_min_hops,
    test_r08, test_r08_ordinal, test_r09, test_r10, test_r10_two_slots, test_r11, test_r12,
    test_r13, test_r14, test_r15, test_r15_summary_acts,
    test_acting_owners_come_from_contracts, test_r16, test_r17, test_r18,
    test_r18_records_are_seed_records, test_r18_extracted_items_belong_to_those_records,
    test_r18_extracted_item_has_somewhere_to_go, test_r19,
    test_r19_reads_the_registry_when_it_exists, test_r20, test_r21, test_r21_the_other_way,
    test_r22, test_r23,
    test_synthetic_corpus_is_quiet, test_k01, test_k02_floor_not_ceiling, test_k03, test_k04,
    test_k05, test_k06, test_k07, test_k08, test_k09, test_k10, test_k11, test_k13,
    test_k13_one_behaviour, test_k14, test_k14_long_memory, test_k15,
    test_k16, test_k16_is_silent_on_a_writing_vertical, test_k17,
    test_k17_erases_the_array_index,
    test_json_round_trip, test_has_result,
    test_registers_v5_mix, test_plate, test_plate_spoken_parses, test_system_prompt_v5,
    test_builder_guards, test_builder_refuses_an_invalid_case, test_prose_seed,
    test_seed_surface_is_the_column, test_v4_kind_table, test_clean_register_case,
    test_no_pseudex,
)


def main() -> int:
    failures: list[str] = []
    for check in CHECKS:
        name = check.__name__  # type: ignore[attr-defined]
        for problem in check():  # type: ignore[operator]
            failures.append(f"{name}: {problem}")
    print(f"schema: {len(CHECKS)} проверок · "
          + ("PASS" if not failures else f"FAIL ({len(failures)})"))
    for failure in failures[:40]:
        print(f"  {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
