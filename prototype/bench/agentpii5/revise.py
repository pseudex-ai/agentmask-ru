"""The 834 v4 cases, read from disk and given a v5 half — mechanically.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_revise

WHAT A REVISION IS AND WHAT IT MUST NEVER BE. v4's corpus is the BASELINE half
of v5: the same 834 cases, the same messages, the same items, the same seeds,
the same trace, byte for byte. This module adds the v5 declarations beside them
and changes nothing inside `Case` — `test_revise.test_messages_byte_identical`
compares `case.base.to_json()` with what `corpus.json` held. A revision that
rewrote one message would make the v4 baseline and the v5 treatment two
different measurements wearing one number.

THE HOPS ARE DERIVED, NOT AUTHORED. v4 declared WHAT a case carries and WHICH
tools it may reach; it never declared which value crosses where, because v4 had
no hop model. So the derivation reads the two things v4 does carry — the item
loci and the tool registry's own field list — and writes the crossings they
imply. Three approximations are forced by what v4 did not record, and each one
is named where it is made rather than buried:

  1. A v4 case does not say WHICH TURN a call happens in. The OUT hops are put
     on the LAST user message, because that is the turn `harness.call_turns`
     matches when an agent answers at the end of the dialogue — which is what
     these cases were built for.
  2. A v4 case does not say which RETURN FORM a tool answered with. The form is
     the tool's first declared one, widened to `list` when several records
     matched. The harness records the ACTUAL form and `build.py --check` prints
     every disagreement as a corpus defect (ruling R-17).
  3. A v4 case does not say which ARGUMENT an identity leaf was filled from.
     The derivation prefers a SEED item the case already reads back from another
     tool — that is the chain `sequential_chain` is about — and falls back to
     what the customer said.

A BEHAVIOUR IS NEVER CLAIMED WITHOUT ITS STRUCTURE. `V4_KIND_TO_BEHAVIOUR` maps
a v4 kind to the behaviour its cases usually show, but a case with no seed
records cannot chain (R12 needs a result to feed an argument), a case with one
seeded identity cannot fan out (R13 needs two candidates), and a case whose
second user message repeats a value cannot be a confirmation loop (R15). Those
cases become `single`, the DOWNGRADE IS RECORDED with its reason, and
`build.py --check` prints the table. Claiming the behaviour anyway would put
cases into a family's denominator that cannot exhibit what the family measures —
the v4 defect «a triple with nothing to compare passed all five levels», in a
new coat.

ONE THING HERE READS A FINISHED MESSAGE, AND IT IS A REFUSAL RATHER THAN A
DERIVATION. `_loop_spec` asks whether the confirming turn contains an item value
(`item.value in message.content`) — the same question R15 asks, asked early so a
case that would fail it becomes `single` instead of raising. No offset and no
ground truth is recovered from a string anywhere in this file; `build.py`'s
widened `prove_no_search` watches `scenarios5/`, where values are WRITTEN, and
nothing there searches either.

NOTHING HERE IMPORTS `pseudex`.
"""
import json
from collections.abc import Container, Sequence
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4.pools import BuildError
from bench.agentpii4.schema import Case, PiiItem, SeedRecord, case_from_json
from bench.agentpii4.tools import FieldSpec
from bench.agentpii5 import mock
from bench.agentpii5.contracts import (GENERIC_PIECE_ROLES, BranchSpec, CaseV5, Hop, LoopSpec,
                                       MemorySpec, PickSpec, ReturnExpectation, SPEECH_REGISTERS,
                                       V4_KIND_TO_BEHAVIOUR, hop_owner_of_leaf)
from bench.agentpii5.observe import values_equal
from bench.agentpii5.schema import has_result, validate_v5
from bench.agentpii5.tools import REGISTRY_V5, expected_leaf_value, spec_v5_for

V4_CORPUS: Path = Path(__file__).resolve().parent.parent / "agentpii4" / "corpus.json"
# One streaming case in every `STREAMING_EVERY` eligible ones (a speech register
# with a tool result). K11 wants ≥ 60 across the corpus and the revised half is
# where most speech cases live; one in three of ~250 eligible puts the count
# comfortably over without making streaming the default reading of a voice case.
STREAMING_EVERY: int = 3
# Why a case left `sequential_chain` under R-49. Named rather than written into
# the branch because `build.py --check` counts the downgrades BY REASON, and
# «no argument is fed by another tool's result» (v4 offered no second tool that
# reads anything) and this one (the only hand-over was a write of a value the
# customer had just stated) are two different facts about the corpus.
MUTATING_REASON: str = ("the only hand-over fed a MUTATING tool, whose argument is the "
                        "value the customer stated (R-49)")


@dataclass(frozen=True)
class Revision:
    """One revised case and what had to be approximated to produce it."""

    case: CaseV5
    downgraded_from: str          # "" when the mapped behaviour survived
    reason: str                   # "" when nothing was downgraded


def load_v4_corpus() -> list[Case]:
    """The 834 as `corpus.json` holds them. Read, never rebuilt: rebuilding
    would run v4's generators and any drift in them would silently become a
    different baseline (v4's own `--check` learned this on 06.09)."""
    if not V4_CORPUS.exists():
        raise BuildError(f"{V4_CORPUS} is missing; v5 is v4 plus a half and cannot be "
                         f"built without it")
    raw = json.loads(V4_CORPUS.read_text(encoding="utf-8"))
    return [case_from_json(row) for row in raw["corpus"]]


def revise(cases: Sequence[Case]) -> list[CaseV5]:
    """Every v4 case with its v5 half, or a refusal naming every one that failed.

    RAISES RATHER THAN DROPS. K10 counts exactly `V4_CORPUS_SIZE` revised cases,
    so a silently dropped case is a corpus that fails a rule three steps later
    with no clue which case caused it. `build.py --allow-drop` is the one path
    that continues, and it prints the ids and leaves K10 red.
    """
    revised, problems = revise_reporting(cases)
    if problems:
        raise BuildError(f"{len(problems)} v4 cases could not be revised:\n  "
                         + "\n  ".join(problems))
    return [revision.case for revision in revised]


def revise_reporting(cases: Sequence[Case]) -> tuple[list[Revision], list[str]]:
    """`revise` without the refusal: the revisions that succeeded and one line
    per case that did not. `build.py` uses this so it can print the whole list
    instead of the first failure."""
    revisions: list[Revision] = []
    problems: list[str] = []
    eligible = 0
    for case in cases:
        stream = False
        if case.register in SPEECH_REGISTERS and case.seed_records:
            eligible += 1
            stream = eligible % STREAMING_EVERY == 0
        try:
            revisions.append(_revise_one(case, stream))
        except BuildError as error:
            problems.append(f"{case.id} ({case.kind}): {error}")
    return revisions, problems


# --- one case -------------------------------------------------------------------

def _revise_one(case: Case, streaming: bool) -> Revision:
    """The whole derivation for one case, DECLARED TWICE.

    THE FIRST DRAFT IS A QUESTION AND THE SECOND IS THE ANSWER. v4 recorded
    which tools a case offers, never which values a call actually brings back,
    so the first pass declares every crossing the registry's leaf list IMPLIES
    and the second declares only the ones the real backend RENDERED when the
    draft's own calls were made (`mock.drive_returns`). Before the proof, 42% of
    the revised half's IN/tool hops were crossings the mock never produces —
    permanent gateway misses the corpus had invented, and 132 cases claiming a
    tool loop with no observable crossing in it at all.
    """
    draft = _declare(case, _readers(case), {}, {}, streaming)
    rendered = _rendered(draft)
    kept = {tool: [(item, path) for item, path in pairs
                   if item.id in rendered.get((tool, 0), {})]
            for tool, pairs in _readers(case).items()}
    revised, downgraded, reason = _finish(
        case, {tool: pairs for tool, pairs in kept.items() if pairs},
        {call.tool_name: call.form for call in mock.drive_returns(draft) if call.form},
        rendered, streaming)
    problems = validate_v5(revised)
    if problems:
        raise BuildError("; ".join(problems))
    return Revision(case=revised, downgraded_from=downgraded, reason=reason)


def _rendered(draft: CaseV5) -> dict[tuple[str, int], dict[str, str]]:
    """(tool, ordinal) → {item id: the text that call's result printed for it}."""
    return {(call.tool_name, call.call_ordinal): dict(call.rendered)
            for call in mock.drive_returns(draft)}


def _finish(case: Case, reads: dict[str, list[tuple[PiiItem, str]]], forms: dict[str, str],
            rendered: dict[tuple[str, int], dict[str, str]], streaming: bool
            ) -> tuple[CaseV5, str, str]:
    """The proven declaration plus the behaviour it can carry."""
    declared = _declare(case, reads, forms, rendered, streaming)
    behaviour, downgraded, reason, pick, branch, loop = _behaviour_of(
        case, declared.behaviour, declared.hops, declared.loop, reads,
        _said_over_chained(case, reads))
    return (CaseV5(base=declared.base, behaviour=behaviour, hops=declared.hops,
                   returns=declared.returns, forced=(), memory=declared.memory,
                   pick=pick, branch=branch, loop=loop if behaviour == "user_in_loop" else None,
                   rag=None, document=None, has_result=declared.has_result,
                   streaming=declared.streaming, revised_from_v4=True),
            downgraded, reason)


def _declare(case: Case, reads: dict[str, list[tuple[PiiItem, str]]], forms: dict[str, str],
             rendered: dict[tuple[str, int], dict[str, str]], streaming: bool) -> CaseV5:
    """One pass of the derivation, in the order the hops must be declared: what
    the customer said, what a tool returned, what went into the next call, what
    the answer carried. `forms` and `rendered` are what the backend did with the
    previous pass; empty on the first, where nothing has been driven yet."""
    hops: list[Hop] = []
    in_hop: dict[str, int] = {}
    user_turns = [index for index, message in enumerate(case.messages) if message.role == "user"]
    if not user_turns:
        raise BuildError("no user message; every hop opens at one")
    first_turn, last_turn = user_turns[0], user_turns[-1]

    for item in case.pii:
        if item.where.kind != "message":
            continue
        in_hop[item.id] = len(hops)
        hops.append(Hop(kind="IN", owner="user", item_id=item.id, hop_index=len(hops),
                        turn=item.where.msg, tool_name="", call_ordinal=-1, parallel_group="",
                        source_hop=-1, path="", optional=False))

    returns: list[ReturnExpectation] = []
    for tool in sorted(reads):
        for item, path in reads[tool]:
            in_hop[item.id] = len(hops)
            hops.append(Hop(kind="IN", owner="tool", item_id=item.id, hop_index=len(hops),
                            turn=first_turn, tool_name=tool, call_ordinal=0, parallel_group="",
                            source_hop=-1, path=path, optional=False))
        returns.append(ReturnExpectation(
            tool, 0,
            forms.get(tool) or _return_form(tool, {item.where.record
                                                   for item, _path in reads[tool]}),
            tuple(item.id for item, _path in reads[tool])))

    behaviour = V4_KIND_TO_BEHAVIOUR[case.kind]
    loop = _loop_spec(case, user_turns) if behaviour == "user_in_loop" else None
    show_turn = loop.show_turn if loop is not None else last_turn

    answered = _answer_items(case, reads)
    answer_hops: list[Hop] = []
    for item in answered:
        source = in_hop.get(item.id, -1)
        answer_hops.append(Hop(kind="OUT", owner="answer", item_id=item.id,
                               hop_index=-1, turn=show_turn, tool_name="", call_ordinal=-1,
                               parallel_group="", source_hop=source, path="",
                               optional=item.canonical not in case.expects.must_contain))

    argument_hops: list[Hop] = []
    for tool, path, item in _arguments(case, in_hop, reads):
        spec = spec_v5_for(tool, path)
        if spec is None:
            raise BuildError(f"{tool} has no leaf {path!r}")
        # REACHABILITY (SPIKE-Е, Е-4): the schema says whether a call may omit
        # the leaf, the PRODUCT says which leaves it never masks. A generic
        # role (`contracts.GENERIC_PIECE_ROLES` — the settlement inside an
        # address, the generic street word) is kept real by
        # `pseudex/vault.py::_settlement_of`, so a REQUIRED hop there can never
        # become `observed` and would be a miss by construction.
        argument_hops.append(Hop(kind="OUT", owner=hop_owner_of_leaf(tool, path),
                                 item_id=item.id, hop_index=-1, turn=last_turn,
                                 tool_name=tool, call_ordinal=0, parallel_group="",
                                 source_hop=_source_of(item, spec, hops, in_hop, rendered),
                                 path=path,
                                 optional=(not spec.required) or spec.role in GENERIC_PIECE_ROLES))

    # The answer comes before the arguments for `user_in_loop` (it is what the
    # confirmation is about) and after them everywhere else, which is the order
    # a reader of the hop list expects: ask, call, answer.
    ordered = (answer_hops + argument_hops) if loop is not None else (argument_hops + answer_hops)
    for hop in ordered:
        hops.append(Hop(kind=hop.kind, owner=hop.owner, item_id=hop.item_id,
                        hop_index=len(hops), turn=hop.turn, tool_name=hop.tool_name,
                        call_ordinal=hop.call_ordinal, parallel_group=hop.parallel_group,
                        source_hop=hop.source_hop, path=hop.path, optional=hop.optional))

    reached = has_result(tuple(hops))
    return CaseV5(base=case, behaviour=behaviour, hops=tuple(hops), returns=tuple(returns),
                  forced=(), memory=_memory_specs(loop, answered), pick=None, branch=None,
                  loop=loop, rag=None, document=None, has_result=reached,
                  streaming=streaming and reached, revised_from_v4=True)


def _source_of(item: PiiItem, spec: FieldSpec, hops: Sequence[Hop], in_hop: dict[str, int],
               rendered: dict[tuple[str, int], dict[str, str]]) -> int:
    """The IN hop an OUT leaf carries forward — declared only when the source
    result REALLY PRINTED the value the leaf will hold.

    `chain_value` compares the text at the OUT leaf with the text of the source
    IN hop's span, so «the result of A fed the argument of B» is a claim about
    two strings being one value. Declared from the leaf list alone it was false
    twice over: the street item's IN span reads «толстого» while the leaf
    `contact.address.city` holds «омск», and the surname item's span reads
    «букин» while `contact.first_name` holds «сергей» — 1 240 of 5 441 revised
    transitions that no gateway could satisfy, against 520 that could.
    """
    source = in_hop.get(item.id, -1)
    if source < 0 or source >= len(hops):
        return -1
    origin = hops[source]
    if origin.kind != "IN" or origin.owner != "tool":
        return source
    printed = rendered.get((origin.tool_name, origin.call_ordinal), {}).get(item.id, "")
    wanted = expected_leaf_value(item, spec)
    return source if printed and wanted and _same_value(item.type, printed, wanted) else -1


def _same_value(pii_type: str, left: str, right: str) -> bool:
    """Two spellings of one value — A THIN CALLER OF THE ONE PREDICATE.

    THIS USED TO BE A THIRD COPY, and its own docstring promised «a hop this
    accepts is a hop that line can hit» while it already disagreed with the line
    it promised to agree with: it folded the digit signature for a private
    `DIGIT_TYPES` tuple that INCLUDED PLATE and DOB, while `metrics.value_matches`
    folded nothing. Measured by the spike's RED test on PLATE, SNILS and INN:
    `revise._same_value` said True where the value line said False, three times
    out of three — a hop the corpus declared reachable counted as a hand-over the
    gateway broke. The private tuple is deleted (SPIKE-Ж, Ж-4): the reading is
    `contracts.VALUE_NORMALISERS` and the predicate is
    `observe.values_equal`, so a hop this accepts is a hop that line can hit by
    construction, not by discipline."""
    return values_equal(pii_type, left, right)


# How a confirmation refers BACK to the value it confirms, by the type of that
# value: «да, это он» about a person, «на тот же телефон», «на тот адрес», and a
# bare pronoun for everything else. The vocabulary is `ANAPHORA_KINDS`.
ANAPHORA_BY_TYPE: dict[str, str] = {
    "NAME": "same_person", "PHONE": "same_phone", "LOC": "same_address"}


def _memory_specs(loop: LoopSpec | None, answered: Sequence[PiiItem]) -> tuple[MemorySpec, ...]:
    """The value the loop SHOWS and the confirmation refers back to.

    `user_in_loop` IS A MEMORY FAMILY AND DECLARED NONE. The agent shows a value
    at `show_turn` and the customer confirms it at `confirm_turn` without
    repeating it — the definition of an anaphoric recall — yet
    `memory_consistency`'s population in the family whose whole shape is a value
    held across two turns was empty (C-048). The item is the one the answer hop
    SHOWED, because that is the value being confirmed.
    """
    if loop is None or not answered:
        return ()
    shown = answered[0]
    return (MemorySpec(item_id=shown.id, first_turn=loop.show_turn,
                       recall_turn=loop.confirm_turn,
                       anaphora=ANAPHORA_BY_TYPE.get(shown.type, "pronoun")),)


# --- what a tool returns ----------------------------------------------------------

def _readers(case: Case) -> dict[str, list[tuple[PiiItem, str]]]:
    """Which offered tool reads which seed item back, and at which leaf.

    MATCHED BY THE REGISTRY'S OWN LEAF LIST, not by a table of tables. A seed
    item lives at a dotted path inside its record (`address.street`); a tool
    declares the dotted leaves its result carries (`contacts[].address.street`).
    A leaf reads a seed field when it ENDS with that path — array indexes erased
    — which is the same rule the mock's own renderer follows, so the corpus and
    the backend cannot disagree about which value a result contains.

    REACHABLE TOOLS FIRST, then the rest of the offered ones. `reachable_tools`
    is v4's statement of what the agent is expected to call; a case whose
    reachable set reads none of its seeds would otherwise have no tool result at
    all, and K10 counts exactly 455 revised cases that reach one.
    """
    by_record: dict[str, SeedRecord] = {record.id: record for record in case.seed_records}
    reads: dict[str, list[tuple[PiiItem, str]]] = {}
    taken: set[str] = set()
    for pool in (case.expects.reachable_tools, case.tools):
        for item in case.pii:
            if item.where.kind != "seed" or item.id in taken:
                continue
            if item.where.record not in by_record:
                raise BuildError(f"item {item.id} names seed {item.where.record!r}, "
                                 f"which the case does not carry")
            for tool in pool:
                leaf = _leaf_for(tool, item.where.path)
                if leaf is None:
                    continue
                reads.setdefault(tool, []).append((item, leaf))
                taken.add(item.id)
                break
    return reads


def _leaf_for(tool: str, path: str) -> str | None:
    """The result leaf of `tool` that carries a seed field at `path`, or None."""
    spec = REGISTRY_V5.get(tool)
    if spec is None:
        return None
    for leaf in spec.base.result_pii:
        bare = leaf.replace("[]", "")
        if bare == path or bare.endswith(f".{path}"):
            return leaf
    return None


def _return_form(tool: str, records: set[str]) -> str:
    """Which form the call answered in — an approximation, and named as one.

    A tool that declares `list` and matched SEVERAL records answered `list`;
    otherwise the first form it declares. v4 recorded neither the call nor its
    shape, so this cannot be read off the case; the harness records the mock's
    ACTUAL form and `build.py --check` prints every disagreement (ruling R-17).
    """
    spec = REGISTRY_V5.get(tool)
    if spec is None:
        raise BuildError(f"{tool} has no ToolSpecV5")
    forms = tuple(one.form for one in spec.return_forms)
    if not forms:
        raise BuildError(f"{tool} declares no return form")
    if len(records) > 1 and "list" in forms:
        return "list"
    return forms[0]


def _answer_items(case: Case, reads: dict[str, list[tuple[PiiItem, str]]]) -> list[PiiItem]:
    """What the reply to the customer carries back.

    THE PRIMARY IDENTITY FIRST, and every read seed item when the case seeds
    nobody under it. A seeded case with no OUT/answer hop would have
    `has_result` False, and K10 pins exactly 455 revised cases that reach a
    result — so «the primary identity happened not to be the seeded one» must
    not be able to move that count.
    """
    read_items = [item for pairs in reads.values() for item, _leaf in pairs]
    primary = [item for item in read_items if item.identity == case.expects.primary_identity]
    return primary if primary else read_items[:2]


# --- what goes into the next call --------------------------------------------------

def _arguments(case: Case, in_hop: dict[str, int],
               reads: dict[str, list[tuple[PiiItem, str]]]) -> list[tuple[str, str, PiiItem]]:
    """(tool, leaf, item) for every identity argument the case can fill.

    ONE ITEM PER LEAF, and a seed item read from ANOTHER tool wins over what the
    customer said. That preference is the whole of R12: an argument fed by a
    result is the chain, and filling every leaf from the message would make
    `sequential_chain` a family with no chains in it.
    """
    read_by: dict[str, str] = {item.id: tool for tool, pairs in reads.items()
                               for item, _leaf in pairs}
    out: list[tuple[str, str, PiiItem]] = []
    for tool in case.expects.reachable_tools:
        spec = REGISTRY_V5.get(tool)
        if spec is None:
            continue
        for field in spec.base.fields:
            if field.kind != "identity" or not field.pii_type:
                continue
            item = _argument_item(case, field, in_hop, read_by, tool)
            if item is not None:
                out.append((tool, field.path, item))
    return out


def _argument_item(case: Case, field: FieldSpec, in_hop: Container[str],
                   read_by: dict[str, str], tool: str) -> PiiItem | None:
    """The value that fills one leaf: a result of a DIFFERENT tool if the case
    has one for the primary identity, else what was said — and the other way
    round on a MUTATING tool.

    THE LEAF'S ROLE DECIDES, NOT ONLY ITS TYPE. `expected_leaf_value` is "" for
    an item that carries no part for the role, and such an item cannot be the
    value of that leaf — the surname item on `contact.first_name` was 300 hops
    nothing could satisfy.

    THE IDENTITY IS THE WHOLE IDENTITY. Splitting on the first dot made
    `p0.other2` and `p0` one person, and 150 OUT hops then wrote a stranger's
    value into the customer's record; a suffix names a DIFFERENT person in v4's
    `lookup_list` families and the same person's other address in others, so the
    only safe reading is the exact one, plus the suffixes the primary itself
    carries.

    `said` WINS ON A MUTATING TOOL (R-49). A write is what the customer asked
    for: «запишите новый телефон …» puts the value of the MESSAGE into
    `crm_upsert_contact.contact.phone`, while the earlier lookup returned the
    OLD one. Declaring the update's argument as fed by that result claims a
    hand-over the case contradicts — the agent that does what the customer asked
    would miss `chain_value` on every one of those hops, and the agent that
    satisfied it would have written the stale value back into the record. A read
    keeps the chain preference: there the result IS where the argument comes
    from, which is what `sequential_chain` measures.
    """
    primary = case.expects.primary_identity
    candidates = _candidates(case, field, in_hop, primary)
    said = _said_of(candidates)
    if said and _is_mutating(tool):
        return said[0]
    chained = _chained_of(candidates, read_by, tool)
    if chained:
        return chained[0]
    return said[0] if said else None


def _candidates(case: Case, field: FieldSpec, in_hop: Container[str],
                primary: str) -> list[PiiItem]:
    """Every item of the case that could BE the value of this leaf: the right
    type, the right person, a part for the leaf's role, and an IN hop it can be
    sourced from."""
    return [item for item in case.pii
            if item.type == field.pii_type and item.id in in_hop
            and _same_person(case, item.identity, primary)
            and expected_leaf_value(item, field)]


def _chained_of(candidates: Sequence[PiiItem], read_by: dict[str, str],
                tool: str) -> list[PiiItem]:
    """The candidates another tool's result brings back."""
    return [item for item in candidates if read_by.get(item.id, "") not in ("", tool)]


def _said_of(candidates: Sequence[PiiItem]) -> list[PiiItem]:
    """The candidates the customer themselves put into a message."""
    return [item for item in candidates if item.where.kind == "message"]


def _is_mutating(tool: str) -> bool:
    """Does this tool WRITE? Read off the registry's own `mutating` flag rather
    than a list of names here: a second list would be a second opinion about
    what a write is, and the one the model is shown is the registry's."""
    spec = REGISTRY_V5.get(tool)
    return spec is not None and spec.base.mutating


def _said_over_chained(case: Case, reads: dict[str, list[tuple[PiiItem, str]]]) -> bool:
    """Did R-49 take at least one leaf of this case off a chain?

    ASKED SO THE DOWNGRADE CAN NAME ITS REASON. A `sequential_chain` case whose
    ONLY transition was an update fed by the lookup that found the old value
    leaves the family, and «no argument is fed by another tool's result» would
    read as «v4 offered no second tool» — two different facts under one line in
    `build --check`.
    """
    read_by = {item.id: tool for tool, pairs in reads.items() for item, _leaf in pairs}
    hopped = _hopped_ids(case, reads)
    primary = case.expects.primary_identity
    for tool in case.expects.reachable_tools:
        spec = REGISTRY_V5.get(tool)
        if spec is None or not spec.base.mutating:
            continue
        for field in spec.base.fields:
            if field.kind != "identity" or not field.pii_type:
                continue
            candidates = _candidates(case, field, hopped, primary)
            if _chained_of(candidates, read_by, tool) and _said_of(candidates):
                return True
    return False


def _hopped_ids(case: Case, reads: dict[str, list[tuple[PiiItem, str]]]) -> set[str]:
    """The items `_declare` gives an IN hop to — what the customer said and what
    a tool reads back. The same membership `_declare`'s `in_hop` holds, derived
    from the same two sources so the two cannot disagree about which item an
    argument may be sourced from."""
    return ({item.id for item in case.pii if item.where.kind == "message"}
            | {item.id for pairs in reads.values() for item, _leaf in pairs})


def _same_person(case: Case, identity: str, primary: str) -> bool:
    """One person's several loci («p0», «p0.home», «p0.sugg1») against ANOTHER
    person under the same stem («p0.other2», «p0.courier»).

    THE STEM CANNOT TELL THEM APART AND THE CASE CAN. `identity.split(".")[0]`
    made the three distinct Букины of a `lookup_list` case one person, and 150
    OUT hops wrote a stranger's value into the customer's record. What
    separates them is whether the sub-identity carries a NAME OF ITS OWN: over
    the 834, `home` / `sugg` / `addr` / `new` / `dir` carry only places
    (1 105 sub-identities, not one NAME between them) and `other` / `courier`
    carry a name each (42) — because a person is named and a place is not.
    """
    if identity == primary:
        return True
    if not identity.startswith(f"{primary}."):
        return False
    return not any(item.identity == identity and item.type == "NAME" for item in case.pii)


# --- the behaviour, claimed only with its structure ---------------------------------

def _behaviour_of(case: Case, behaviour: str, hops: Sequence[Hop], loop: LoopSpec | None,
                  reads: dict[str, list[tuple[PiiItem, str]]], said_over_chained: bool
                  ) -> tuple[str, str, str, PickSpec | None, BranchSpec | None,
                             LoopSpec | None]:
    """The behaviour this case can actually exhibit, and why it is not the
    mapped one when it is not."""
    if behaviour == "sequential_chain":
        if _chains(hops):
            return behaviour, "", "", None, None, None
        return "single", behaviour, (MUTATING_REASON if said_over_chained
                                     else "no argument is fed by another tool's result"), \
            None, None, None
    if behaviour == "fanout_pick":
        pick = _pick_spec(case, reads)
        if pick is not None:
            return behaviour, "", "", pick, None, None
        return "single", behaviour, "fewer than two seeded identities to choose between", \
            None, None, None
    if behaviour == "branching":
        branch = _branch_spec(case)
        if branch is not None:
            return behaviour, "", "", None, branch, None
        return "single", behaviour, "fewer than three offered tools to branch between", \
            None, None, None
    if behaviour == "user_in_loop":
        if loop is not None and _loop_hops_present(hops, loop):
            return behaviour, "", "", None, None, loop
        return "single", behaviour, "no value-free confirming turn with an act after it", \
            None, None, None
    return behaviour, "", "", None, None, None


def _chains(hops: Sequence[Hop]) -> bool:
    """R12: some OUT hop is sourced by an IN/tool hop of a DIFFERENT tool."""
    for hop in hops:
        if hop.kind != "OUT" or not hop.tool_name or not 0 <= hop.source_hop < len(hops):
            continue
        source = hops[hop.source_hop]
        if source.kind == "IN" and source.owner == "tool" and source.tool_name != hop.tool_name:
            return True
    return False


def _pick_spec(case: Case, reads: dict[str, list[tuple[PiiItem, str]]]) -> PickSpec | None:
    """R13: two seeded identities carrying a value of the same type, a tool that
    listed them and another that acts on the one chosen.

    THE TARGET IS NOT ALWAYS `expects.primary_identity`, and refusing the ones
    where it is not would have thrown away 87 of the 117 fan-outs v4 already
    has. v4's address families (`compare`, `search_rank`) seed only the
    SUGGESTIONS — `p0.sugg0` … `p0.sugg4` — and the customer `p0` carries no
    seed item at all; the pick is among the suggestions, which is exactly the
    fan-out the family is named for. So the target is the primary identity when
    it is seeded and the first seeded identity otherwise, and R13's own demand
    («the target is one of the candidates») is what keeps that honest.
    """
    primary = case.expects.primary_identity
    seeds = [item for item in case.pii if item.where.kind == "seed"]
    if not seeds:
        return None
    target = primary if any(item.identity == primary for item in seeds) else seeds[0].identity
    target_types = {item.type for item in seeds if item.identity == target}
    if not target_types:
        return None
    candidates = [target]
    for item in seeds:
        if item.identity != target and item.type in target_types \
                and item.identity not in candidates:
            candidates.append(item.identity)
    if len(candidates) < 2 or not reads:
        return None
    list_tool = sorted(reads)[0]
    act = [tool for tool in case.tools if tool != list_tool]
    if not act:
        return None
    return PickSpec(list_tool=list_tool, candidate_identities=tuple(candidates),
                    target_identity=target, act_tool=act[0])


def _branch_spec(case: Case) -> BranchSpec | None:
    """R14: a probe and two DIFFERENT offered tools to branch between."""
    if len(case.tools) < 3:
        return None
    probe = case.expects.reachable_tools[0] if case.expects.reachable_tools else case.tools[0]
    rest = [tool for tool in case.tools if tool != probe]
    if len(rest) < 2:
        return None
    return BranchSpec(probe_tool=probe, seed_present=bool(case.seed_records),
                      then_tool=rest[0], else_tool=rest[1])


def _loop_spec(case: Case, user_turns: Sequence[int]) -> LoopSpec | None:
    """R15: a second user message that confirms WITHOUT repeating a value.

    The phrase is the message's own text, not a phrase invented here — a
    revision must describe the case it revises, and a confirmation the dialogue
    never contained would make `LoopSpec.confirm_phrase` fiction the metrics
    then read as fact.

    «CARRIES A VALUE» IS A LOCUS, NOT A SUBSTRING. This used to ask
    `item.value in case.messages[turn].content`, which is the one search in a
    corpus builder the whole `prove_no_search` machinery exists to forbid — and
    it is answerable exactly: v4 wrote every item into a message through
    `Writer` and recorded WHICH message in `Locus.msg`. The register transform
    may have rewritten the surface, so the substring test could also be WRONG
    about a turn it had rewritten.
    """
    if len(user_turns) < 2 or not case.seed_records:
        return None
    # THE LAST VALUE-FREE TURN, NOT THE SECOND ONE. A `long_clinic` dialogue
    # spends its middle turns adding data («дата рождения 10.03.1973») and its
    # last ones deciding («давайте на утро записывайте»); taking the second turn
    # by position downgraded all forty-five of them, because the second turn is
    # where the birth date arrives. The confirmation is the last turn that says
    # nothing new, and it is also the turn the act follows.
    spoken = {item.where.msg for item in case.pii if item.where.kind == "message"}
    free = [turn for turn in user_turns[1:] if turn not in spoken]
    if not free:
        return None
    confirm_turn = free[-1]
    # THE USER TURN BEFORE THE CONFIRMATION, found by comparing turn numbers.
    # `user_turns.index(confirm_turn)` said the same thing and is a scan of a
    # built structure — the shape `prove_no_search` watches for, and the watch
    # now covers this file.
    show_turn = [turn for turn in user_turns if turn < confirm_turn][-1]
    phrase = case.messages[confirm_turn].content
    reachable = case.expects.reachable_tools or case.tools
    act = [tool for tool in case.tools if tool != reachable[0]]
    if not act:
        return None
    return LoopSpec(find_tool=reachable[0], show_turn=show_turn, confirm_turn=confirm_turn,
                    confirm_phrase=phrase, act_tool=act[0])


def _loop_hops_present(hops: Sequence[Hop], loop: LoopSpec) -> bool:
    """R15's two structural demands, checked before the behaviour is claimed."""
    shown = any(hop.kind == "OUT" and hop.owner == "answer" and hop.turn == loop.show_turn
                for hop in hops)
    acted = any(hop.kind == "OUT" and hop.owner == "tool_arg" and hop.turn >= loop.confirm_turn
                for hop in hops)
    return shown and acted


def main() -> int:
    """`python3 -m bench.agentpii5.revise` — revise the 834 and report."""
    cases = load_v4_corpus()
    revisions, problems = revise_reporting(cases)
    print(f"revised {len(revisions)} of {len(cases)}; "
          f"{sum(1 for one in revisions if one.case.has_result)} reach a result; "
          f"{sum(1 for one in revisions if one.case.streaming)} stream")
    downgrades: dict[str, int] = {}
    for one in revisions:
        if one.downgraded_from:
            downgrades[f"{one.downgraded_from}: {one.reason}"] = \
                downgrades.get(f"{one.downgraded_from}: {one.reason}", 0) + 1
    for label in sorted(downgrades):
        print(f"  понижено {downgrades[label]:>4} · {label}")
    for problem in problems[:20]:
        print(f"  ОТКАЗ {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
